"""Textual TUI application for JSON logs viewer."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from json_logs_viewer.models import (
    FilterState,
    LogEntry,
    LogLevel,
    SearchHistory,
)
from json_logs_viewer.parser import LogParser, ParseResult
from json_logs_viewer.watcher import BatchProcessor, FileWatcher


@dataclass
class AppState:
    """Application state container."""

    file_path: Path | None = None
    parse_result: ParseResult | None = None
    filter_state: FilterState = field(
        default_factory=lambda: FilterState(raw_query="")
    )
    search_history: SearchHistory = field(default_factory=SearchHistory)
    follow_mode: bool = False
    selected_index: int = 0


class LogListWidget(Static):
    """Widget for displaying the list of log entries."""

    DEFAULT_CSS = """
    LogListWidget {
        width: 100%;
        height: 100%;
        overflow-y: auto;
    }
    """

    entries = reactive[list[LogEntry]](lambda: [])
    selected_index: reactive[int] = reactive(0)

    def __init__(self, *, entries: list[LogEntry] | None = None) -> None:
        """Initialize the log list widget."""
        super().__init__()
        self.entries = entries or []

    def watch_entries(self, entries: list[LogEntry]) -> None:
        """React to entries change."""
        self.refresh()

    def watch_selected_index(self, index: int) -> None:
        """React to selection change."""
        self.refresh()

    def render(self) -> str:
        """Render the log list."""
        if not self.entries:
            return "No log entries to display."

        lines: list[str] = []
        for i, entry in enumerate(self.entries):
            prefix = "> " if i == self.selected_index else "  "
            level_color = self._get_level_color(entry.level)
            message = (
                entry.message[:60] + "..."
                if len(entry.message) > 60
                else entry.message
            )
            level_str = entry.level.name[:8]
            line = f"{prefix}[{level_color}]{level_str:8}[/"
            lines.append(f"{line}{level_color}] {message}")

        return "\n".join(lines)

    def _get_level_color(self, level: LogLevel) -> str:
        """Get color for log level."""
        colors = {
            LogLevel.ERROR: "red",
            LogLevel.WARNING: "yellow",
            LogLevel.INFO: "blue",
            LogLevel.DEBUG: "green",
            LogLevel.TRACE: "magenta",
        }
        return colors.get(level, "white")

    def select_next(self) -> None:
        """Select the next entry."""
        if self.entries:
            self.selected_index = min(
                self.selected_index + 1, len(self.entries) - 1
            )

    def select_previous(self) -> None:
        """Select the previous entry."""
        if self.entries:
            self.selected_index = max(self.selected_index - 1, 0)


class MainScreen(Screen):
    """Main screen with log list view."""

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("ctrl+f", "search", "Search", show=True),
        Binding("ctrl+c", "copy", "Copy", show=True),
        Binding("ctrl+t", "toggle_follow", "Follow", show=True),
        Binding("j,down", "cursor_down", "Down", show=False),
        Binding("k,up", "cursor_up", "Up", show=False),
        Binding("enter,l", "view_detail", "Detail", show=False),
        Binding("g", "goto_first", "First", show=False),
        Binding("G", "goto_last", "Last", show=False),
        Binding("1", "toggle_level_error", "Error", show=False),
        Binding("2", "toggle_level_warning", "Warn", show=False),
        Binding("3", "toggle_level_info", "Info", show=False),
        Binding("4", "toggle_level_debug", "Debug", show=False),
        Binding("5", "toggle_level_trace", "Trace", show=False),
        Binding("0", "show_all_levels", "All", show=False),
    ]

    DEFAULT_CSS = """
    MainScreen {
        layout: vertical;
    }

    #header {
        height: 1;
        background: $surface;
        color: $text;
    }

    #log-container {
        height: 1fr;
        background: $surface-darken-1;
    }

    #status-bar {
        height: 1;
        background: $surface;
        color: $text-muted;
    }
    """

    def __init__(self, *, app_state: AppState) -> None:
        """Initialize the main screen."""
        super().__init__()
        self._app_state = app_state
        self._log_list = LogListWidget(entries=[])

    def compose(self) -> ComposeResult:
        """Compose the main screen."""
        yield Header(id="header")
        with Container(id="log-container"):
            yield self._log_list
        yield Footer(id="status-bar")

    def on_mount(self) -> None:
        """Handle mount event."""
        if self._app_state.parse_result:
            self._log_list.entries = self._app_state.parse_result.entries

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()

    def action_search(self) -> None:
        """Open search dialog."""
        pass  # Will be implemented in T8

    def action_copy(self) -> None:
        """Copy selected log entry."""
        pass  # Will be implemented in T10

    def action_toggle_follow(self) -> None:
        """Toggle follow mode."""
        self._app_state.follow_mode = not self._app_state.follow_mode

    def action_cursor_down(self) -> None:
        """Move cursor down."""
        self._log_list.select_next()

    def action_cursor_up(self) -> None:
        """Move cursor up."""
        self._log_list.select_previous()

    def action_view_detail(self) -> None:
        """View detail of selected entry."""
        pass  # Will be implemented in T6

    def action_goto_first(self) -> None:
        """Go to first entry."""
        self._log_list.selected_index = 0

    def action_goto_last(self) -> None:
        """Go to last entry."""
        if self._log_list.entries:
            self._log_list.selected_index = len(self._log_list.entries) - 1

    def action_toggle_level_error(self) -> None:
        """Toggle ERROR level."""
        self._toggle_level(LogLevel.ERROR)

    def action_toggle_level_warning(self) -> None:
        """Toggle WARNING level."""
        self._toggle_level(LogLevel.WARNING)

    def action_toggle_level_info(self) -> None:
        """Toggle INFO level."""
        self._toggle_level(LogLevel.INFO)

    def action_toggle_level_debug(self) -> None:
        """Toggle DEBUG level."""
        self._toggle_level(LogLevel.DEBUG)

    def action_toggle_level_trace(self) -> None:
        """Toggle TRACE level."""
        self._toggle_level(LogLevel.TRACE)

    def action_show_all_levels(self) -> None:
        """Show all log levels."""
        self._app_state.filter_state = FilterState(
            raw_query=self._app_state.filter_state.raw_query,
            parsed_filters=self._app_state.filter_state.parsed_filters,
            enabled_levels=set(LogLevel),
            case_sensitive=self._app_state.filter_state.case_sensitive,
        )

    def _toggle_level(self, level: LogLevel) -> None:
        """Toggle a specific log level."""
        self._app_state.filter_state = (
            self._app_state.filter_state.with_level_toggled(level=level)
        )


class DetailScreen(Screen):
    """Detail screen for viewing formatted JSON."""

    BINDINGS = [
        Binding("escape,h,q", "back", "Back", show=True),
        Binding("j,down", "scroll_down", "Down", show=False),
        Binding("k,up", "scroll_up", "Up", show=False),
        Binding("ctrl+c", "copy", "Copy", show=True),
    ]

    DEFAULT_CSS = """
    DetailScreen {
        layout: vertical;
    }

    #detail-container {
        height: 1fr;
        background: $surface-darken-1;
        padding: 1;
    }

    #json-content {
        width: 100%;
        height: 100%;
        overflow: auto;
    }
    """

    def __init__(self, *, log_entry: LogEntry) -> None:
        """Initialize the detail screen."""
        super().__init__()
        self._log_entry = log_entry

    def compose(self) -> ComposeResult:
        """Compose the detail screen."""
        with Container(id="detail-container"):
            yield Static(
                self._log_entry.to_formatted_json(indent=2),
                id="json-content",
            )

    def action_back(self) -> None:
        """Go back to main screen."""
        self.app.pop_screen()

    def action_copy(self) -> None:
        """Copy the JSON content."""
        pass  # Will be implemented in T10

    def action_scroll_down(self) -> None:
        """Scroll down."""
        content = self.query_one("#json-content", Static)
        if content:
            content.scroll_down()

    def action_scroll_up(self) -> None:
        """Scroll up."""
        content = self.query_one("#json-content", Static)
        if content:
            content.scroll_up()


class LogsApp(App):
    """Main Textual application for viewing JSON logs."""

    CSS = """
    /* Catppuccin Mocha Theme */
    
    /* Base colors */
    $bg: #1e1e2e;
    $surface: #313244;
    $text: #cdd6f4;
    $text-muted: #6c7086;
    $accent: #fab387;
    $border: #45475a;
    $selection: #585b70;
    
    /* Log level colors */
    $error: #f38ba8;
    $warning: #f9e2af;
    $info: #89b4fa;
    $debug: #a6e3a1;
    $trace: #cba6f7;
    
    /* Screen backgrounds */
    Screen {
        background: $bg;
        color: $text;
    }
    
    /* Header styling */
    Header {
        background: $surface;
        color: $text;
        height: 1;
    }
    
    Header.-tall {
        height: 3;
    }
    
    /* Footer styling */
    Footer {
        background: $surface;
        color: $text-muted;
        height: 1;
    }
    
    Footer > .footer-key {
        background: $surface;
        color: $accent;
    }
    
    /* Container styling */
    Container {
        background: $bg;
    }
    
    /* Static content */
    Static {
        background: transparent;
        color: $text;
    }
    
    /* Log list specific */
    LogListWidget {
        background: $bg;
        color: $text;
        scrollbar-color: $surface;
        scrollbar-color-hover: $selection;
        scrollbar-color-active: $accent;
    }
    
    /* Selection styling */
    :focus {
        border: solid $accent;
    }
    
    /* Button styling (for future use) */
    Button {
        background: $surface;
        color: $text;
        border: solid $border;
    }
    
    Button:hover {
        background: $selection;
        border: solid $accent;
    }
    
    Button:focus {
        border: solid $accent;
    }
    """

    def __init__(
        self,
        *,
        file_path: Path | None = None,
        follow_mode: bool = False,
    ) -> None:
        """Initialize the LogsApp.

        Args:
            file_path: Path to the log file to view.
            follow_mode: Whether to start in follow mode.
        """
        super().__init__()
        self._app_state = AppState(
            file_path=file_path,
            follow_mode=follow_mode,
        )
        self._watcher: FileWatcher | None = None
        self._batch_processor: BatchProcessor | None = None

    def on_mount(self) -> None:
        """Handle app mount event."""
        if self._app_state.file_path:
            self._load_file()

        if self._app_state.follow_mode and self._app_state.file_path:
            self._start_watching()

        self.push_screen(MainScreen(app_state=self._app_state))

    def _load_file(self) -> None:
        """Load and parse the log file."""
        if not self._app_state.file_path:
            return

        try:
            parser = LogParser()
            self._app_state.parse_result = parser.parse_file(
                file_path=self._app_state.file_path
            )
        except (FileNotFoundError, PermissionError):
            self._app_state.parse_result = None
            # Will show error in UI

    def _start_watching(self) -> None:
        """Start file watching for follow mode."""
        if not self._app_state.file_path:
            return

        self._watcher = FileWatcher(file_path=self._app_state.file_path)
        self._watcher.start_watching()

        self._batch_processor = BatchProcessor(
            watcher=self._watcher,
            on_entries=self._on_new_entries,
        )

        # Set up periodic check
        self.set_interval(0.5, self._check_for_updates)

    def _check_for_updates(self) -> None:
        """Check for file updates (called periodically)."""
        if self._batch_processor and self._app_state.follow_mode:
            self._batch_processor.process_once()

    def _on_new_entries(self, entries: list[LogEntry]) -> None:
        """Handle new entries from file watcher."""
        if self._app_state.parse_result:
            self._app_state.parse_result.entries.extend(entries)
            # Refresh the screen if visible
            try:
                screen = self.screen
                if isinstance(screen, MainScreen):
                    # Update the log list
                    pass  # Will refresh via reactive
            except NoMatches:
                pass


def main(*, args: list[str] | None = None) -> None:
    """Main entry point for the application.

    Args:
        args: Command line arguments (defaults to sys.argv).
    """
    import argparse
    import sys

    if args is None:
        args = sys.argv[1:]

    desc = "A keyboard-centric Textual TUI for viewing JSON/JSONL logs."
    parser = argparse.ArgumentParser(
        prog="json-logs-viewer",
        description=desc,
    )
    parser.add_argument(
        "file",
        nargs="?",
        type=Path,
        help="Path to the JSON or JSONL log file to view.",
    )
    parser.add_argument(
        "--follow",
        "-f",
        action="store_true",
        help="Start in follow mode (tail -f behavior).",
    )

    parsed = parser.parse_args(args)

    app = LogsApp(
        file_path=parsed.file,
        follow_mode=parsed.follow,
    )
    app.run()


if __name__ == "__main__":
    main()
