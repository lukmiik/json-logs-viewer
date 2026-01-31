"""Tests for the Textual app."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from json_logs_viewer.app import (
    AppState,
    DetailScreen,
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


class TestDetailScreen:
    """Tests for DetailScreen."""

    def test_bindings(self) -> None:
        """Test that DetailScreen has expected keybindings."""
        entry = LogEntry(
            raw_line='{"level": "info"}',
            parsed_data={"level": "info"},
            line_number=1,
        )
        screen = DetailScreen(log_entry=entry)

        # Check bindings exist - BINDINGS is a list of tuples
        binding_keys = []
        for b in screen.BINDINGS:
            if isinstance(b, tuple):
                binding_keys.append(b[0])
            else:
                binding_keys.append(b.key)
        assert "escape,h,q" in binding_keys
        assert "j,down" in binding_keys
        assert "k,up" in binding_keys
        assert "ctrl+c" in binding_keys

    def test_initialization(self) -> None:
        """Test DetailScreen initialization."""
        entry = LogEntry(
            raw_line='{"level": "info", "message": "test"}',
            parsed_data={"level": "info", "message": "test"},
            line_number=1,
            level=LogLevel.INFO,
            message="test",
        )
        screen = DetailScreen(log_entry=entry)
        assert screen._log_entry == entry

    @pytest.mark.skip(reason="Requires active app context")
    def test_compose_structure(self) -> None:
        """Test DetailScreen compose generates expected structure."""
        entry = LogEntry(
            raw_line='{"level": "info"}',
            parsed_data={"level": "info"},
            line_number=1,
        )
        screen = DetailScreen(log_entry=entry)
        composed = list(screen.compose())

        # Should have Container with Static
        assert len(composed) == 1


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
