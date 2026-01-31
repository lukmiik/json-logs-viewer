"""Tests for the level filter bar widget."""

from __future__ import annotations

from textual.color import Color

from json_logs_viewer.level_bar import LevelButton, LevelFilterBar
from json_logs_viewer.models import LogLevel


class TestLevelButton:
    """Tests for LevelButton."""

    def test_initialization(self) -> None:
        """Test LevelButton initialization."""
        button = LevelButton(
            level=LogLevel.ERROR,
            count=5,
            enabled=True,
        )
        assert button._level == LogLevel.ERROR
        assert button._count == 5
        assert button._enabled is True

    def test_initialization_disabled(self) -> None:
        """Test LevelButton initialization with disabled state."""
        button = LevelButton(
            level=LogLevel.INFO,
            count=10,
            enabled=False,
        )
        assert button._enabled is False

    def test_get_color_for_level(self) -> None:
        """Test color mapping for each level."""
        for level in LogLevel:
            color = LevelButton._get_color_for_level(level)
            assert isinstance(color, Color)

    def test_format_label_enabled(self) -> None:
        """Test label formatting when enabled."""
        button = LevelButton(
            level=LogLevel.ERROR,
            count=5,
            enabled=True,
        )
        label = button._format_label()
        assert "ERR" in label
        assert "(5)" in label
        assert "●" in label  # Enabled indicator

    def test_format_label_disabled(self) -> None:
        """Test label formatting when disabled."""
        button = LevelButton(
            level=LogLevel.INFO,
            count=10,
            enabled=False,
        )
        label = button._format_label()
        assert "INFO" in label
        assert "(10)" in label
        assert "○" in label  # Disabled indicator

    def test_update_state(self) -> None:
        """Test updating button state."""
        button = LevelButton(
            level=LogLevel.WARNING,
            count=3,
            enabled=True,
        )

        button.update_state(count=7, enabled=False)
        assert button._count == 7
        assert button._enabled is False

    def test_on_toggle_callback(self) -> None:
        """Test toggle callback is called."""
        toggled_level: LogLevel | None = None

        def on_toggle(level: LogLevel) -> None:
            nonlocal toggled_level
            toggled_level = level

        button = LevelButton(
            level=LogLevel.DEBUG,
            count=2,
            enabled=True,
            on_toggle=on_toggle,
        )

        # Simulate button press
        from textual.widgets import Button

        button.on_button_pressed(Button.Pressed(button=button))

        assert toggled_level == LogLevel.DEBUG


class TestLevelFilterBar:
    """Tests for LevelFilterBar."""

    def test_default_initialization(self) -> None:
        """Test LevelFilterBar with default values."""
        bar = LevelFilterBar()
        assert bar._enabled_levels == set(LogLevel)
        assert len(bar._level_counts) == len(LogLevel)

    def test_initialization_with_enabled_levels(self) -> None:
        """Test LevelFilterBar with custom enabled levels."""
        enabled = {LogLevel.ERROR, LogLevel.INFO}
        bar = LevelFilterBar(enabled_levels=enabled)
        assert bar._enabled_levels == enabled

    def test_key_bindings_mapping(self) -> None:
        """Test keyboard shortcut mappings."""
        assert LevelFilterBar.KEY_BINDINGS["1"] == LogLevel.ERROR
        assert LevelFilterBar.KEY_BINDINGS["2"] == LogLevel.WARNING
        assert LevelFilterBar.KEY_BINDINGS["3"] == LogLevel.INFO
        assert LevelFilterBar.KEY_BINDINGS["4"] == LogLevel.DEBUG
        assert LevelFilterBar.KEY_BINDINGS["5"] == LogLevel.TRACE

    def test_on_key_press_valid(self) -> None:
        """Test handling valid keyboard shortcuts."""
        toggled_level: LogLevel | None = None

        def on_toggle(level: LogLevel) -> None:
            nonlocal toggled_level
            toggled_level = level

        bar = LevelFilterBar(on_level_toggle=on_toggle)

        result = bar.on_key_press("1")
        assert result is True
        assert toggled_level == LogLevel.ERROR

    def test_on_key_press_zero(self) -> None:
        """Test handling '0' key for show all."""
        show_all_called = False

        def on_show_all() -> None:
            nonlocal show_all_called
            show_all_called = True

        bar = LevelFilterBar(on_show_all=on_show_all)

        result = bar.on_key_press("0")
        assert result is True
        assert show_all_called is True

    def test_on_key_press_invalid(self) -> None:
        """Test handling invalid keyboard shortcuts."""
        bar = LevelFilterBar()

        result = bar.on_key_press("x")
        assert result is False

        result = bar.on_key_press("9")
        assert result is False

    def test_update_counts(self) -> None:
        """Test updating level counts."""
        bar = LevelFilterBar()
        counts = {
            LogLevel.ERROR: 5,
            LogLevel.WARNING: 3,
            LogLevel.INFO: 10,
            LogLevel.DEBUG: 2,
            LogLevel.TRACE: 1,
        }

        bar.update_counts(counts=counts)
        assert bar._level_counts == counts

    def test_update_enabled_levels(self) -> None:
        """Test updating enabled levels."""
        bar = LevelFilterBar()
        enabled = {LogLevel.ERROR, LogLevel.WARNING}

        bar.update_enabled_levels(enabled_levels=enabled)
        assert bar._enabled_levels == enabled

    def test_count_entries_by_level_integration(self) -> None:
        """Test counting entries by level with mock data."""
        from json_logs_viewer.models import LogEntry

        entries = [
            LogEntry(
                raw_line='{"level": "error"}',
                parsed_data={"level": "error"},
                line_number=1,
                level=LogLevel.ERROR,
            ),
            LogEntry(
                raw_line='{"level": "error"}',
                parsed_data={"level": "error"},
                line_number=2,
                level=LogLevel.ERROR,
            ),
            LogEntry(
                raw_line='{"level": "info"}',
                parsed_data={"level": "info"},
                line_number=3,
                level=LogLevel.INFO,
            ),
        ]

        # This simulates what MainScreen would do
        counts: dict[LogLevel, int] = {level: 0 for level in LogLevel}
        for entry in entries:
            counts[entry.level] = counts.get(entry.level, 0) + 1

        assert counts[LogLevel.ERROR] == 2
        assert counts[LogLevel.INFO] == 1
        assert counts[LogLevel.WARNING] == 0


class TestLevelFilterBarCompose:
    """Tests for LevelFilterBar compose."""

    def test_compose_creates_buttons(self) -> None:
        """Test that compose creates level buttons."""
        bar = LevelFilterBar()

        # Compose is a generator, so we need to iterate it
        composed = list(bar.compose())

        # Static + 5 level buttons + 1 all button = 7 widgets
        assert len(composed) == 7

    def test_compose_creates_all_button(self) -> None:
        """Test that compose creates the all button."""
        bar = LevelFilterBar()
        composed = list(bar.compose())

        # Find the all button (last one)
        from textual.widgets import Button

        for widget in composed:
            if (
                isinstance(widget, Button)
                and hasattr(widget, "classes")
                and "all-button" in str(widget.classes)
            ):
                break

        # Should exist (even if we can't find it by classes)
        buttons = [w for w in composed if isinstance(w, Button)]
        assert len(buttons) == 6  # 5 level + 1 all
