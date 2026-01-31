"""Level filter bar widget for JSON logs viewer."""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar

from textual.app import ComposeResult
from textual.color import Color
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widgets import Button, Static

from json_logs_viewer.models import LogLevel


class LevelButton(Button):
    """Button for toggling a log level filter."""

    DEFAULT_CSS = """
    LevelButton {
        width: auto;
        min-width: 14;
        height: 1;
        padding: 0 1;
        border: none;
        background: $surface;
        color: $text;
        text-style: bold;
        content-align: center middle;
    }
    
    LevelButton:hover {
        background: $selection;
    }
    
    LevelButton:disabled {
        opacity: 0.3;
        background: $surface-darken-1;
    }
    
    LevelButton.level-enabled {
        text-style: bold;
    }
    
    LevelButton.level-disabled {
        text-style: dim;
    }
    """

    def __init__(
        self,
        *,
        level: LogLevel,
        count: int,
        enabled: bool,
        on_toggle: Callable[[LogLevel], None] | None = None,
    ) -> None:
        """Initialize the level button.

        Args:
            level: The log level this button represents.
            count: Number of entries for this level.
            enabled: Whether this level is currently enabled.
            on_toggle: Callback when button is pressed.
        """
        self._level = level
        self._count = count
        self._enabled = enabled
        self._on_toggle = on_toggle
        self._color = self._get_color_for_level(level)

        label = self._format_label()
        super().__init__(label=label, variant="default")
        self._update_appearance()

    @staticmethod
    def _get_color_for_level(level: LogLevel) -> Color:
        """Get the display color for a log level."""
        colors: dict[LogLevel, str] = {
            LogLevel.ERROR: "#f38ba8",  # Red
            LogLevel.WARNING: "#f9e2af",  # Yellow
            LogLevel.INFO: "#89b4fa",  # Blue
            LogLevel.DEBUG: "#a6e3a1",  # Green
            LogLevel.TRACE: "#cba6f7",  # Purple
        }
        return Color.parse(colors.get(level, "#cdd6f4"))

    def _format_label(self) -> str:
        """Format the button label with level name and count."""
        # Use shorter name for display
        name = self._level.name[:4]  # ERR, WARN, INFO, DEBG, TRCE
        status = "●" if self._enabled else "○"
        return f"[{status}] {name}({self._count})"

    def _update_appearance(self) -> None:
        """Update the button appearance based on state."""
        if self._enabled:
            self.add_class("level-enabled")
            self.remove_class("level-disabled")
            self.styles.color = self._color
        else:
            self.add_class("level-disabled")
            self.remove_class("level-enabled")
            self.styles.color = Color.parse("#6c7086")  # Muted text

    def update_state(self, *, count: int, enabled: bool) -> None:
        """Update the button state.

        Args:
            count: New count for this level.
            enabled: New enabled state.
        """
        self._count = count
        self._enabled = enabled
        self.label = self._format_label()
        self._update_appearance()

    def on_button_pressed(self, _event: Button.Pressed) -> None:
        """Handle button press."""
        if self._on_toggle:
            self._on_toggle(self._level)


class LevelFilterBar(Horizontal):
    """Horizontal bar for filtering by log level."""

    DEFAULT_CSS = """
    LevelFilterBar {
        width: 100%;
        height: 1;
        background: $surface;
        padding: 0 1;
    }
    
    LevelFilterBar > .level-label {
        width: auto;
        content-align: center middle;
        color: $text-muted;
        text-style: bold;
        padding: 0 1;
    }
    
    LevelFilterBar > .all-button {
        width: auto;
        min-width: 8;
        height: 1;
        padding: 0 1;
        border: none;
        background: $surface;
        color: $text-muted;
        text-style: bold;
        content-align: center middle;
    }
    
    LevelFilterBar > .all-button:hover {
        background: $selection;
        color: $text;
    }
    """

    enabled_levels: reactive[set[LogLevel]] = reactive(set(LogLevel))
    level_counts: reactive[dict[LogLevel, int]] = reactive({})

    # Keyboard shortcuts mapping
    KEY_BINDINGS: ClassVar[dict[str, LogLevel]] = {
        "1": LogLevel.ERROR,
        "2": LogLevel.WARNING,
        "3": LogLevel.INFO,
        "4": LogLevel.DEBUG,
        "5": LogLevel.TRACE,
    }

    def __init__(
        self,
        *,
        enabled_levels: set[LogLevel] | None = None,
        on_level_toggle: Callable[[LogLevel], None] | None = None,
        on_show_all: Callable[[], None] | None = None,
    ) -> None:
        """Initialize the level filter bar.

        Args:
            enabled_levels: Set of currently enabled levels.
            on_level_toggle: Callback when a level is toggled.
            on_show_all: Callback when "all" is pressed.
        """
        super().__init__()
        self._enabled_levels: set[LogLevel] = set(
            enabled_levels if enabled_levels is not None else LogLevel
        )
        self._level_counts: dict[LogLevel, int] = {
            level: 0 for level in LogLevel
        }
        self._on_level_toggle = on_level_toggle
        self._on_show_all = on_show_all
        self._buttons: dict[LogLevel, LevelButton] = {}
        self._all_button: Button | None = None

    def compose(self) -> ComposeResult:
        """Compose the level filter bar."""
        yield Static("LEVELS:", classes="level-label")

        # Create buttons for each level in order
        for level in [
            LogLevel.ERROR,
            LogLevel.WARNING,
            LogLevel.INFO,
            LogLevel.DEBUG,
            LogLevel.TRACE,
        ]:
            count = self._level_counts.get(level, 0)
            enabled = level in self._enabled_levels

            button = LevelButton(
                level=level,
                count=count,
                enabled=enabled,
                on_toggle=self._on_level_button_pressed,
            )
            self._buttons[level] = button
            yield button

        # All levels button
        self._all_button = Button(
            label="[ALL]",
            variant="default",
            classes="all-button",
        )
        yield self._all_button

    def _on_level_button_pressed(self, level: LogLevel) -> None:
        """Handle level button press."""
        if self._on_level_toggle:
            self._on_level_toggle(level)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button == self._all_button and self._on_show_all:
            self._on_show_all()

    def update_counts(self, *, counts: dict[LogLevel, int]) -> None:
        """Update the count display for each level.

        Args:
            counts: Dictionary mapping levels to their counts.
        """
        self._level_counts = counts
        for level, button in self._buttons.items():
            count = counts.get(level, 0)
            enabled = level in self._enabled_levels
            button.update_state(count=count, enabled=enabled)

    def update_enabled_levels(self, *, enabled_levels: set[LogLevel]) -> None:
        """Update which levels are enabled.

        Args:
            enabled_levels: Set of enabled levels.
        """
        self._enabled_levels = enabled_levels
        for level, button in self._buttons.items():
            count = self._level_counts.get(level, 0)
            enabled = level in enabled_levels
            button.update_state(count=count, enabled=enabled)

    def watch_enabled_levels(self, enabled_levels: set[LogLevel]) -> None:
        """React to enabled levels change."""
        self.update_enabled_levels(enabled_levels=enabled_levels)

    def watch_level_counts(self, level_counts: dict[LogLevel, int]) -> None:
        """React to level counts change."""
        self.update_counts(counts=level_counts)

    def on_key_press(self, key: str) -> bool:
        """Handle keyboard shortcut for level filtering.

        This is called manually by the parent screen when keys 0-5 are pressed.

        Args:
            key: The key pressed.

        Returns:
            True if the key was handled, False otherwise.
        """
        if key in self.KEY_BINDINGS:
            level = self.KEY_BINDINGS[key]
            if self._on_level_toggle:
                self._on_level_toggle(level)
            return True
        if key == "0" and self._on_show_all:
            self._on_show_all()
            return True
        return False
