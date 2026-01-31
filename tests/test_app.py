"""Tests for the Textual app."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from textual.app import App
from textual.screen import Screen

from json_logs_viewer.app import (
    AppState,
    DetailScreen,
    DetailWidget,
    LogListWidget,
    LogsApp,
    MainScreen,
    main,
)
from json_logs_viewer.models import (
    FilterState,
    LogEntry,
    LogLevel,
    SearchHistory,
)
from json_logs_viewer.parser import ParseResult


class DummyApp(App[None]):
    pass


def _attach_app(*, screen: Screen) -> tuple[DummyApp, MagicMock, MagicMock]:
    app: DummyApp = DummyApp()
    copy_mock: MagicMock = MagicMock()
    notify_mock: MagicMock = MagicMock()
    app.copy_to_clipboard = copy_mock  # type: ignore[method-assign]
    app.notify = notify_mock  # type: ignore[method-assign]
    screen._parent = app
    return app, copy_mock, notify_mock


class TestAppState:
    """Tests for AppState dataclass."""

    def test_default_initialization(self) -> None:
        """Test AppState with default values."""
        state = AppState()
        assert state.file_path is None
        assert state.parse_result is None
        assert isinstance(state.filter_state, FilterState)
        assert isinstance(state.search_history, SearchHistory)
        assert state.follow_mode is False
        assert state.selected_index == 0

    def test_custom_initialization(self) -> None:
        """Test AppState with custom values."""
        path = Path("/test/logs.json")
        state = AppState(
            file_path=path,
            follow_mode=True,
            selected_index=5,
        )
        assert state.file_path == path
        assert state.follow_mode is True
        assert state.selected_index == 5


class TestLogListWidget:
    """Tests for LogListWidget."""

    def test_default_initialization(self) -> None:
        """Test LogListWidget with default values."""
        widget = LogListWidget()
        assert widget.entries == []
        assert widget.selected_index == 0

    def test_initialization_with_entries(self) -> None:
        """Test LogListWidget with initial entries."""
        entries = [
            LogEntry(
                raw_line='{"level": "info", "message": "test"}',
                parsed_data={"level": "info", "message": "test"},
                line_number=1,
                level=LogLevel.INFO,
                message="test",
            )
        ]
        widget = LogListWidget(entries=entries)
        assert len(widget.entries) == 1
        assert widget.selected_index == 0

    def test_select_next(self) -> None:
        """Test selecting next entry."""
        entries = [
            LogEntry(
                raw_line='{"level": "info", "message": "test1"}',
                parsed_data={"level": "info", "message": "test1"},
                line_number=1,
                level=LogLevel.INFO,
                message="test1",
            ),
            LogEntry(
                raw_line='{"level": "error", "message": "test2"}',
                parsed_data={"level": "error", "message": "test2"},
                line_number=2,
                level=LogLevel.ERROR,
                message="test2",
            ),
        ]
        widget = LogListWidget(entries=entries)
        assert widget.selected_index == 0

        widget.select_next()
        assert widget.selected_index == 1

        # Should not go past last entry
        widget.select_next()
        assert widget.selected_index == 1

    def test_select_previous(self) -> None:
        """Test selecting previous entry."""
        entries = [
            LogEntry(
                raw_line='{"level": "info", "message": "test1"}',
                parsed_data={"level": "info", "message": "test1"},
                line_number=1,
                level=LogLevel.INFO,
                message="test1",
            ),
            LogEntry(
                raw_line='{"level": "error", "message": "test2"}',
                parsed_data={"level": "error", "message": "test2"},
                line_number=2,
                level=LogLevel.ERROR,
                message="test2",
            ),
        ]
        widget = LogListWidget(entries=entries)
        widget.selected_index = 1

        widget.select_previous()
        assert widget.selected_index == 0

        # Should not go below 0
        widget.select_previous()
        assert widget.selected_index == 0

    def test_select_next_empty_list(self) -> None:
        """Test select_next with empty list."""
        widget = LogListWidget(entries=[])
        widget.select_next()
        assert widget.selected_index == 0

    def test_select_previous_empty_list(self) -> None:
        """Test select_previous with empty list."""
        widget = LogListWidget(entries=[])
        widget.select_previous()
        assert widget.selected_index == 0

    def test_select_first(self) -> None:
        """Test selecting first entry."""
        entries = [
            LogEntry(
                raw_line='{"level": "info", "message": "test1"}',
                parsed_data={"level": "info", "message": "test1"},
                line_number=1,
                level=LogLevel.INFO,
                message="test1",
            ),
            LogEntry(
                raw_line='{"level": "error", "message": "test2"}',
                parsed_data={"level": "error", "message": "test2"},
                line_number=2,
                level=LogLevel.ERROR,
                message="test2",
            ),
        ]
        widget = LogListWidget(entries=entries)
        widget.selected_index = 1

        widget.select_first()
        assert widget.selected_index == 0

    def test_select_last(self) -> None:
        """Test selecting last entry."""
        entries = [
            LogEntry(
                raw_line='{"level": "info", "message": "test1"}',
                parsed_data={"level": "info", "message": "test1"},
                line_number=1,
                level=LogLevel.INFO,
                message="test1",
            ),
            LogEntry(
                raw_line='{"level": "error", "message": "test2"}',
                parsed_data={"level": "error", "message": "test2"},
                line_number=2,
                level=LogLevel.ERROR,
                message="test2",
            ),
        ]
        widget = LogListWidget(entries=entries)
        widget.selected_index = 0

        widget.select_last()
        assert widget.selected_index == 1

    def test_get_selected_entry(self) -> None:
        """Test getting the currently selected entry."""
        entries = [
            LogEntry(
                raw_line='{"level": "info", "message": "test1"}',
                parsed_data={"level": "info", "message": "test1"},
                line_number=1,
                level=LogLevel.INFO,
                message="test1",
            ),
            LogEntry(
                raw_line='{"level": "error", "message": "test2"}',
                parsed_data={"level": "error", "message": "test2"},
                line_number=2,
                level=LogLevel.ERROR,
                message="test2",
            ),
        ]
        widget = LogListWidget(entries=entries)

        # First entry selected by default
        selected = widget.get_selected_entry()
        assert selected is not None
        assert selected.line_number == 1
        assert selected.message == "test1"

        # Select second entry
        widget.select_next()
        selected = widget.get_selected_entry()
        assert selected is not None
        assert selected.line_number == 2
        assert selected.message == "test2"

    def test_get_selected_entry_empty(self) -> None:
        """Test getting selected entry when list is empty."""
        widget = LogListWidget(entries=[])
        selected = widget.get_selected_entry()
        assert selected is None

    def test_level_colors_defined(self) -> None:
        """Test that level colors are properly defined."""
        from textual.color import Color

        widget = LogListWidget()
        assert LogLevel.ERROR in widget.LEVEL_COLORS
        assert LogLevel.WARNING in widget.LEVEL_COLORS
        assert LogLevel.INFO in widget.LEVEL_COLORS
        assert LogLevel.DEBUG in widget.LEVEL_COLORS
        assert LogLevel.TRACE in widget.LEVEL_COLORS

        # Verify colors are Color instances
        for _level, color in widget.LEVEL_COLORS.items():
            assert isinstance(color, Color)

    def test_set_entries_updates_internal_state(self) -> None:
        """Test that set_entries updates internal _entries."""
        widget = LogListWidget()

        entries = [
            LogEntry(
                raw_line='{"level": "info", "message": "test"}',
                parsed_data={"level": "info", "message": "test"},
                line_number=1,
                level=LogLevel.INFO,
                message="test",
            )
        ]

        widget.set_entries(entries=entries)
        assert len(widget._entries) == 1
        assert widget._entries[0].message == "test"


class TestDetailWidget:
    """Tests for DetailWidget."""

    def test_initialization(self) -> None:
        """Test DetailWidget initialization."""
        entry = LogEntry(
            raw_line='{"level": "info", "message": "test"}',
            parsed_data={"level": "info", "message": "test"},
            line_number=1,
            level=LogLevel.INFO,
            message="test",
        )
        widget = DetailWidget(log_entry=entry, indent=2)
        assert widget._log_entry == entry
        assert widget._indent == 2

    def test_get_selected_entry(self) -> None:
        """Test getting the displayed log entry."""
        entry = LogEntry(
            raw_line='{"level": "error", "message": "error message"}',
            parsed_data={"level": "error", "message": "error message"},
            line_number=5,
            level=LogLevel.ERROR,
            message="error message",
        )
        widget = DetailWidget(log_entry=entry)
        assert widget.get_selected_entry() == entry

    def test_format_json_with_colors_simple(self) -> None:
        """Test JSON formatting with simple object."""
        entry = LogEntry(
            raw_line=(
                '{"level": "info", "count": 42, "active": true, "data": null}'
            ),
            parsed_data={
                "level": "info",
                "count": 42,
                "active": True,
                "data": None,
            },
            line_number=1,
        )
        widget = DetailWidget(log_entry=entry)
        formatted = widget._format_json_with_colors(
            entry.parsed_data, indent=2
        )

        # Should contain formatted content with color markup
        assert "level" in formatted
        assert "info" in formatted
        assert "42" in formatted
        assert "true" in formatted
        assert "null" in formatted

    def test_format_json_with_colors_nested(self) -> None:
        """Test JSON formatting with nested objects."""
        entry = LogEntry(
            raw_line=(
                '{"user": {"name": "test", "id": 123}, "items": [1, 2, 3]}'
            ),
            parsed_data={
                "user": {"name": "test", "id": 123},
                "items": [1, 2, 3],
            },
            line_number=1,
        )
        widget = DetailWidget(log_entry=entry)
        formatted = widget._format_json_with_colors(
            entry.parsed_data, indent=2
        )

        # Should contain nested structure
        assert "user" in formatted
        assert "name" in formatted
        assert "test" in formatted
        assert "items" in formatted

    def test_format_value_string_escaping(self) -> None:
        """Test string value escaping."""
        entry = LogEntry(
            raw_line='{"msg": "line1\\nline2"}',
            parsed_data={"msg": "line1\nline2"},
            line_number=1,
        )
        widget = DetailWidget(log_entry=entry)
        formatted = widget._format_value(
            "line1\nline2", indent=2, current_indent=0
        )

        # Newline should be escaped
        assert "\\n" in formatted

    def test_format_empty_dict(self) -> None:
        """Test formatting empty dictionary."""
        entry = LogEntry(
            raw_line="{}",
            parsed_data={},
            line_number=1,
        )
        widget = DetailWidget(log_entry=entry)
        formatted = widget._format_value({}, indent=2, current_indent=0)
        assert formatted == "{}"

    def test_format_empty_list(self) -> None:
        """Test formatting empty list."""
        entry = LogEntry(
            raw_line="[]",
            parsed_data={"items": []},
            line_number=1,
        )
        widget = DetailWidget(log_entry=entry)
        formatted = widget._format_value([], indent=2, current_indent=0)
        assert formatted == "[]"

    def test_colors_defined(self) -> None:
        """Test that syntax highlighting colors are defined."""
        widget = DetailWidget(
            log_entry=LogEntry(raw_line="{}", parsed_data={}, line_number=1)
        )
        expected_colors = [
            "key",
            "string",
            "number",
            "boolean",
            "null",
            "punctuation",
        ]
        for color in expected_colors:
            assert color in widget.COLORS
            assert isinstance(widget.COLORS[color], str)
            assert widget.COLORS[color].startswith("#")


class TestMainScreen:
    """Tests for MainScreen."""

    def test_bindings(self) -> None:
        """Test that MainScreen has expected keybindings."""
        state = AppState()
        screen = MainScreen(app_state=state)

        # Check bindings exist - BINDINGS is a list of tuples
        binding_keys = []
        for b in screen.BINDINGS:
            if isinstance(b, tuple):
                binding_keys.append(b[0])
            else:
                binding_keys.append(b.key)
        assert "ctrl+q" in binding_keys
        assert "ctrl+f" in binding_keys
        assert "ctrl+c" in binding_keys
        assert "ctrl+t" in binding_keys
        assert "j,down" in binding_keys
        assert "k,up" in binding_keys
        assert "enter,l" in binding_keys
        assert "g" in binding_keys
        assert "G" in binding_keys
        assert "1" in binding_keys
        assert "2" in binding_keys
        assert "3" in binding_keys
        assert "4" in binding_keys
        assert "5" in binding_keys
        assert "0" in binding_keys

    def test_initialization(self) -> None:
        """Test MainScreen initialization."""
        state = AppState()
        screen = MainScreen(app_state=state)
        assert screen._app_state == state
        assert isinstance(screen._log_list, LogListWidget)

    @pytest.mark.skip(reason="Requires active app context")
    def test_compose_structure(self) -> None:
        """Test MainScreen compose generates expected structure."""
        state = AppState()
        screen = MainScreen(app_state=state)
        composed = list(screen.compose())

        # Should have Header, Container with LogListWidget, and Footer
        assert len(composed) == 3

    def test_on_detail_navigate(self) -> None:
        """Test detail navigation callback."""
        entries = [
            LogEntry(
                raw_line='{"level": "info"}',
                parsed_data={"level": "info"},
                line_number=1,
            ),
            LogEntry(
                raw_line='{"level": "error"}',
                parsed_data={"level": "error"},
                line_number=2,
            ),
        ]
        state = AppState()
        screen = MainScreen(app_state=state)
        screen._log_list._entries = entries
        screen._log_list.selected_index = 0

        screen._on_detail_navigate(1)
        assert screen._log_list.selected_index == 1


class TestDetailScreen:
    """Tests for DetailScreen."""

    def test_bindings(self) -> None:
        """Test that DetailScreen has expected keybindings."""
        entries = [
            LogEntry(
                raw_line='{"level": "info"}',
                parsed_data={"level": "info"},
                line_number=1,
            )
        ]
        screen = DetailScreen(entries=entries, current_index=0)

        # Check bindings exist
        binding_keys = []
        for b in screen.BINDINGS:
            if isinstance(b, tuple):
                binding_keys.append(b[0])
            else:
                binding_keys.append(b.key)
        assert "escape,h,q" in binding_keys
        assert "j,down" in binding_keys
        assert "k,up" in binding_keys
        assert "n,right" in binding_keys
        assert "p,left" in binding_keys
        assert "ctrl+c" in binding_keys

    def test_initialization(self) -> None:
        """Test DetailScreen initialization."""
        entries = [
            LogEntry(
                raw_line='{"level": "info", "message": "test1"}',
                parsed_data={"level": "info", "message": "test1"},
                line_number=1,
                level=LogLevel.INFO,
                message="test1",
            ),
            LogEntry(
                raw_line='{"level": "error", "message": "test2"}',
                parsed_data={"level": "error", "message": "test2"},
                line_number=2,
                level=LogLevel.ERROR,
                message="test2",
            ),
        ]
        screen = DetailScreen(entries=entries, current_index=1)
        assert screen._entries == entries
        assert screen._current_index == 1
        assert screen._on_navigate is None

    def test_initialization_with_callback(self) -> None:
        """Test DetailScreen initialization with navigation callback."""
        entries = [
            LogEntry(
                raw_line='{"level": "info"}',
                parsed_data={"level": "info"},
                line_number=1,
            )
        ]
        callback_called = False

        def on_navigate(index: int) -> None:
            nonlocal callback_called
            callback_called = True

        screen = DetailScreen(
            entries=entries, current_index=0, on_navigate=on_navigate
        )
        assert screen._on_navigate is on_navigate

    def test_get_header_text(self) -> None:
        """Test header text generation."""
        entries = [
            LogEntry(
                raw_line='{"level": "error", "message": "error occurred"}',
                parsed_data={"level": "error", "message": "error occurred"},
                line_number=42,
                level=LogLevel.ERROR,
                message="error occurred",
            )
        ]
        screen = DetailScreen(entries=entries, current_index=0)
        header = screen._get_header_text()

        assert "Line 42" in header
        assert "ERROR" in header
        assert "error occurred" in header

    def test_get_header_text_long_message(self) -> None:
        """Test header text with long message truncation."""
        entries = [
            LogEntry(
                raw_line='{"message": "a" * 100}',
                parsed_data={"message": "a" * 100},
                line_number=1,
                message="a" * 100,
            )
        ]
        screen = DetailScreen(entries=entries, current_index=0)
        header = screen._get_header_text()

        # Long message should be truncated with "..."
        assert "..." in header

    def test_get_footer_text(self) -> None:
        """Test footer text generation."""
        entries = [
            LogEntry(
                raw_line='{"level": "info"}',
                parsed_data={"level": "info"},
                line_number=1,
            ),
            LogEntry(
                raw_line='{"level": "error"}',
                parsed_data={"level": "error"},
                line_number=2,
            ),
        ]
        screen = DetailScreen(entries=entries, current_index=1)
        footer = screen._get_footer_text()

        assert "Entry 2/2" in footer
        assert "n/p" in footer
        assert "Esc/h/q" in footer

    def test_action_next_entry(self) -> None:
        """Test navigating to next entry."""
        entries = [
            LogEntry(
                raw_line='{"level": "info"}',
                parsed_data={"level": "info"},
                line_number=1,
            ),
            LogEntry(
                raw_line='{"level": "error"}',
                parsed_data={"level": "error"},
                line_number=2,
            ),
        ]
        screen = DetailScreen(entries=entries, current_index=0)

        screen.action_next_entry()
        assert screen._current_index == 1

        # Should not go past last entry
        screen.action_next_entry()
        assert screen._current_index == 1

    def test_action_previous_entry(self) -> None:
        """Test navigating to previous entry."""
        entries = [
            LogEntry(
                raw_line='{"level": "info"}',
                parsed_data={"level": "info"},
                line_number=1,
            ),
            LogEntry(
                raw_line='{"level": "error"}',
                parsed_data={"level": "error"},
                line_number=2,
            ),
        ]
        screen = DetailScreen(entries=entries, current_index=1)

        screen.action_previous_entry()
        assert screen._current_index == 0

        # Should not go below 0
        screen.action_previous_entry()
        assert screen._current_index == 0

    def test_action_next_entry_single_entry(self) -> None:
        """Test next entry with only one entry."""
        entries = [
            LogEntry(
                raw_line='{"level": "info"}',
                parsed_data={"level": "info"},
                line_number=1,
            )
        ]
        screen = DetailScreen(entries=entries, current_index=0)

        screen.action_next_entry()
        assert screen._current_index == 0  # Should stay at 0

    def test_action_previous_entry_first_entry(self) -> None:
        """Test previous entry when at first entry."""
        entries = [
            LogEntry(
                raw_line='{"level": "info"}',
                parsed_data={"level": "info"},
                line_number=1,
            ),
            LogEntry(
                raw_line='{"level": "error"}',
                parsed_data={"level": "error"},
                line_number=2,
            ),
        ]
        screen = DetailScreen(entries=entries, current_index=0)

        screen.action_previous_entry()
        assert screen._current_index == 0  # Should stay at 0

    @pytest.mark.skip(reason="Requires active app context")
    def test_compose_structure(self) -> None:
        """Test DetailScreen compose generates expected structure."""
        entries = [
            LogEntry(
                raw_line='{"level": "info"}',
                parsed_data={"level": "info"},
                line_number=1,
            )
        ]
        screen = DetailScreen(entries=entries, current_index=0)
        composed = list(screen.compose())

        # Should have Static header, Container with DetailWidget, Static footer
        assert len(composed) == 3


class TestLogsApp:
    """Tests for LogsApp."""

    def test_default_initialization(self) -> None:
        """Test LogsApp with default values."""
        app = LogsApp()
        assert app._app_state.file_path is None
        assert app._app_state.follow_mode is False
        assert app._watcher is None
        assert app._batch_processor is None

    def test_initialization_with_file(self) -> None:
        """Test LogsApp with file path."""
        path = Path("/test/logs.json")
        app = LogsApp(file_path=path)
        assert app._app_state.file_path == path

    def test_initialization_with_follow_mode(self) -> None:
        """Test LogsApp with follow mode enabled."""
        path = Path("/test/logs.json")
        app = LogsApp(file_path=path, follow_mode=True)
        assert app._app_state.follow_mode is True

    def test_css_defined(self) -> None:
        """Test that CSS is defined."""
        app = LogsApp()
        assert hasattr(app, "CSS")
        assert "$bg: #1e1e2e" in app.CSS
        assert "$error: #f38ba8" in app.CSS
        assert "$warning: #f9e2af" in app.CSS

    def test_has_catppuccin_colors(self) -> None:
        """Test that Catppuccin Mocha colors are defined."""
        app = LogsApp()
        expected_colors = [
            "#1e1e2e",  # bg
            "#313244",  # surface
            "#cdd6f4",  # text
            "#fab387",  # accent
            "#45475a",  # border
            "#585b70",  # selection
            "#f38ba8",  # error
            "#f9e2af",  # warning
            "#89b4fa",  # info
            "#a6e3a1",  # debug
            "#cba6f7",  # trace
        ]
        for color in expected_colors:
            assert color in app.CSS


class TestCLI:
    """Tests for CLI argument parsing."""

    def test_cli_no_args(self) -> None:
        """Test CLI with no arguments."""
        with patch("json_logs_viewer.app.LogsApp") as mock_app:
            mock_instance = MagicMock()
            mock_app.return_value = mock_instance
            main(args=[])

            mock_app.assert_called_once_with(file_path=None, follow_mode=False)
            mock_instance.run.assert_called_once()

    def test_cli_with_file(self) -> None:
        """Test CLI with file argument."""
        with patch("json_logs_viewer.app.LogsApp") as mock_app:
            mock_instance = MagicMock()
            mock_app.return_value = mock_instance
            main(args=["/path/to/logs.json"])

            mock_app.assert_called_once()
            call_kwargs = mock_app.call_args.kwargs
            assert call_kwargs["file_path"] == Path("/path/to/logs.json")
            assert call_kwargs["follow_mode"] is False

    def test_cli_with_follow_flag(self) -> None:
        """Test CLI with --follow flag."""
        with patch("json_logs_viewer.app.LogsApp") as mock_app:
            mock_instance = MagicMock()
            mock_app.return_value = mock_instance
            main(args=["/path/to/logs.json", "--follow"])

            mock_app.assert_called_once()
            call_kwargs = mock_app.call_args.kwargs
            assert call_kwargs["file_path"] == Path("/path/to/logs.json")
            assert call_kwargs["follow_mode"] is True

    def test_cli_with_follow_short_flag(self) -> None:
        """Test CLI with -f short flag."""
        with patch("json_logs_viewer.app.LogsApp") as mock_app:
            mock_instance = MagicMock()
            mock_app.return_value = mock_instance
            main(args=["/path/to/logs.json", "-f"])

            mock_app.assert_called_once()
            call_kwargs = mock_app.call_args.kwargs
            assert call_kwargs["follow_mode"] is True

    def test_cli_help(self) -> None:
        """Test CLI --help output."""
        with pytest.raises(SystemExit) as exc_info:
            main(args=["--help"])
        assert exc_info.value.code == 0


class TestMainScreenActions:
    """Tests for MainScreen action methods."""

    def test_action_toggle_follow(self) -> None:
        """Test toggle follow action."""
        state = AppState(follow_mode=False)
        screen = MainScreen(app_state=state)

        screen.action_toggle_follow()
        assert state.follow_mode is True

        screen.action_toggle_follow()
        assert state.follow_mode is False

    def test_action_cursor_down(self) -> None:
        """Test cursor down action."""
        entries = [
            LogEntry(
                raw_line='{"level": "info"}',
                parsed_data={"level": "info"},
                line_number=1,
            ),
            LogEntry(
                raw_line='{"level": "error"}',
                parsed_data={"level": "error"},
                line_number=2,
            ),
        ]
        state = AppState()
        screen = MainScreen(app_state=state)
        screen._log_list._entries = entries

        screen.action_cursor_down()
        assert screen._log_list.selected_index == 1

    def test_action_cursor_up(self) -> None:
        """Test cursor up action."""
        entries = [
            LogEntry(
                raw_line='{"level": "info"}',
                parsed_data={"level": "info"},
                line_number=1,
            ),
            LogEntry(
                raw_line='{"level": "error"}',
                parsed_data={"level": "error"},
                line_number=2,
            ),
        ]
        state = AppState()
        screen = MainScreen(app_state=state)
        screen._log_list._entries = entries
        screen._log_list.selected_index = 1

        screen.action_cursor_up()
        assert screen._log_list.selected_index == 0

    def test_action_goto_first(self) -> None:
        """Test goto first action."""
        entries = [
            LogEntry(
                raw_line='{"level": "info"}',
                parsed_data={"level": "info"},
                line_number=1,
            ),
            LogEntry(
                raw_line='{"level": "error"}',
                parsed_data={"level": "error"},
                line_number=2,
            ),
        ]
        state = AppState()
        screen = MainScreen(app_state=state)
        screen._log_list._entries = entries
        screen._log_list.selected_index = 1

        screen.action_goto_first()
        assert screen._log_list.selected_index == 0

    def test_action_goto_last(self) -> None:
        """Test goto last action."""
        entries = [
            LogEntry(
                raw_line='{"level": "info"}',
                parsed_data={"level": "info"},
                line_number=1,
            ),
            LogEntry(
                raw_line='{"level": "error"}',
                parsed_data={"level": "error"},
                line_number=2,
            ),
        ]
        state = AppState()
        screen = MainScreen(app_state=state)
        screen._log_list._entries = entries

        screen.action_goto_last()
        assert screen._log_list.selected_index == 1

    def test_follow_auto_scroll_on_new_entries(self) -> None:
        """Test auto-scroll to latest entry while following."""
        entries = [
            LogEntry(
                raw_line='{"level": "info", "message": "first"}',
                parsed_data={"level": "info", "message": "first"},
                line_number=1,
                level=LogLevel.INFO,
                message="first",
            ),
            LogEntry(
                raw_line='{"level": "error", "message": "second"}',
                parsed_data={"level": "error", "message": "second"},
                line_number=2,
                level=LogLevel.ERROR,
                message="second",
            ),
        ]
        state = AppState(follow_mode=True)
        screen = MainScreen(app_state=state)
        state.parse_result = ParseResult(
            entries=entries,
            skipped_lines=[],
            file_path=Path("/test/logs.jsonl"),
            format_type="jsonl",
        )

        screen.handle_new_entries(entries=entries)

        assert screen._log_list.selected_index == len(entries) - 1

    def test_follow_pauses_on_user_navigation(self) -> None:
        """Test user navigation pauses auto-follow."""
        entries = [
            LogEntry(
                raw_line='{"level": "info", "message": "first"}',
                parsed_data={"level": "info", "message": "first"},
                line_number=1,
                level=LogLevel.INFO,
                message="first",
            ),
            LogEntry(
                raw_line='{"level": "error", "message": "second"}',
                parsed_data={"level": "error", "message": "second"},
                line_number=2,
                level=LogLevel.ERROR,
                message="second",
            ),
        ]
        state = AppState(follow_mode=True)
        screen = MainScreen(app_state=state)
        state.parse_result = ParseResult(
            entries=entries,
            skipped_lines=[],
            file_path=Path("/test/logs.jsonl"),
            format_type="jsonl",
        )

        screen._disable_auto_follow()
        screen.handle_new_entries(entries=entries)

        assert screen._log_list.selected_index == 0

    def test_action_copy_no_selection(self) -> None:
        """Test copy action with no selection."""
        state = AppState()
        screen = MainScreen(app_state=state)
        _, copy_mock, notify_mock = _attach_app(screen=screen)

        screen.action_copy()

        copy_mock.assert_not_called()
        notify_mock.assert_called_once()
        args = notify_mock.call_args.args
        kwargs = notify_mock.call_args.kwargs
        assert args[0] == "No log selected."
        assert kwargs["title"] == "Clipboard"
        assert kwargs["severity"] == "warning"

    def test_action_copy_copies_raw_line(self) -> None:
        """Test copy action copies raw line."""
        entries = [
            LogEntry(
                raw_line='{"level": "info", "message": "test"}',
                parsed_data={"level": "info", "message": "test"},
                line_number=1,
                level=LogLevel.INFO,
                message="test",
            )
        ]
        state = AppState()
        screen = MainScreen(app_state=state)
        screen._log_list._entries = entries
        screen._log_list.selected_index = 0
        _, copy_mock, notify_mock = _attach_app(screen=screen)

        screen.action_copy()

        copy_mock.assert_called_once_with(entries[0].raw_line)
        notify_mock.assert_called_once()
        args = notify_mock.call_args.args
        kwargs = notify_mock.call_args.kwargs
        assert args[0] == "Copied log line to clipboard."
        assert kwargs["title"] == "Clipboard"

    def test_toggle_level_actions(self) -> None:
        """Test level toggle actions."""
        state = AppState()
        screen = MainScreen(app_state=state)

        # Initially all levels should be enabled
        assert LogLevel.ERROR in state.filter_state.enabled_levels

        # Toggle ERROR off
        screen.action_toggle_level_error()
        assert LogLevel.ERROR not in state.filter_state.enabled_levels

        # Toggle ERROR back on
        screen.action_toggle_level_error()
        assert LogLevel.ERROR in state.filter_state.enabled_levels

    def test_show_all_levels_action(self) -> None:
        """Test show all levels action."""
        state = AppState()
        screen = MainScreen(app_state=state)

        # Disable some levels
        state.filter_state = state.filter_state.with_level_toggled(
            level=LogLevel.ERROR
        )
        state.filter_state = state.filter_state.with_level_toggled(
            level=LogLevel.DEBUG
        )

        # Show all should re-enable all
        screen.action_show_all_levels()
        assert LogLevel.ERROR in state.filter_state.enabled_levels
        assert LogLevel.DEBUG in state.filter_state.enabled_levels


class TestDetailScreenActions:
    """Tests for DetailScreen action methods."""

    def test_action_scroll_down_no_widget(self) -> None:
        """Test scroll down when widget not mounted."""
        entries = [
            LogEntry(
                raw_line='{"level": "info"}',
                parsed_data={"level": "info"},
                line_number=1,
            )
        ]
        screen = DetailScreen(entries=entries, current_index=0)
        # Should not raise error when widget is None
        screen.action_scroll_down()

    def test_action_scroll_up_no_widget(self) -> None:
        """Test scroll up when widget not mounted."""
        entries = [
            LogEntry(
                raw_line='{"level": "info"}',
                parsed_data={"level": "info"},
                line_number=1,
            )
        ]
        screen = DetailScreen(entries=entries, current_index=0)
        # Should not raise error when widget is None
        screen.action_scroll_up()

    def test_action_next_entry_updates_display(self) -> None:
        """Test that next entry updates the display state."""
        entries = [
            LogEntry(
                raw_line='{"level": "info", "n": 1}',
                parsed_data={"level": "info", "n": 1},
                line_number=1,
                level=LogLevel.INFO,
                message="first",
            ),
            LogEntry(
                raw_line='{"level": "error", "n": 2}',
                parsed_data={"level": "error", "n": 2},
                line_number=2,
                level=LogLevel.ERROR,
                message="second",
            ),
        ]
        screen = DetailScreen(entries=entries, current_index=0)

        # Verify initial state
        assert screen._current_index == 0

        # Navigate to next
        screen.action_next_entry()
        assert screen._current_index == 1
        # Entry at index 1 should be ERROR level
        assert screen._entries[screen._current_index].level == LogLevel.ERROR

    def test_action_copy_formatted_json(self) -> None:
        """Test copy action copies formatted JSON."""
        entry = LogEntry(
            raw_line='{"level": "info", "message": "test"}',
            parsed_data={"level": "info", "message": "test"},
            line_number=1,
            level=LogLevel.INFO,
            message="test",
        )
        screen = DetailScreen(entries=[entry], current_index=0)
        _, copy_mock, notify_mock = _attach_app(screen=screen)

        screen.action_copy()

        expected = entry.to_formatted_json(indent=2)
        copy_mock.assert_called_once_with(expected)
        notify_mock.assert_called_once()
        args = notify_mock.call_args.args
        kwargs = notify_mock.call_args.kwargs
        assert args[0] == "Copied formatted JSON to clipboard."
        assert kwargs["title"] == "Clipboard"

    def test_action_previous_entry_updates_display(self) -> None:
        """Test that previous entry updates the display state."""
        entries = [
            LogEntry(
                raw_line='{"level": "info", "n": 1}',
                parsed_data={"level": "info", "n": 1},
                line_number=1,
                level=LogLevel.INFO,
                message="first",
            ),
            LogEntry(
                raw_line='{"level": "error", "n": 2}',
                parsed_data={"level": "error", "n": 2},
                line_number=2,
                level=LogLevel.ERROR,
                message="second",
            ),
        ]
        screen = DetailScreen(entries=entries, current_index=1)

        # Verify initial state
        assert screen._current_index == 1
        assert screen._entries[screen._current_index].level == LogLevel.ERROR

        # Navigate to previous
        screen.action_previous_entry()
        assert screen._current_index == 0
        assert screen._entries[screen._current_index].level == LogLevel.INFO
