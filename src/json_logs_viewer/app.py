"""Textual TUI application for JSON logs viewer."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.color import Color
from textual.containers import Container
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static

from json_logs_viewer.filter import FilterEngine, create_filter_state
from json_logs_viewer.models import (
    FilterState,
    LogEntry,
    LogLevel,
    SearchHistory,
)
from json_logs_viewer.parser import LogParser, ParseResult
from json_logs_viewer.search_bar import SearchBarOverlay
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


class LogListWidget(DataTable):
    """Widget for displaying log entries with level colors."""

    DEFAULT_CSS = """
    LogListWidget {
        width: 100%;
        height: 100%;
        border: none;
        background: $bg;
    }
    
    LogListWidget > .datatable--header {
        background: $surface;
        color: $text;
        text-style: bold;
    }
    
    LogListWidget > .datatable--row {
        background: $bg;
        color: $text;
        height: 1;
    }
    
    LogListWidget > .datatable--row:hover {
        background: $surface-darken-1;
    }
    
    LogListWidget:focus > .datatable--row-cursor {
        background: $selection;
    }
    
    LogListWidget > .datatable--row-cursor {
        background: $selection;
    }
    """

    # Catppuccin Mocha colors for log levels
    LEVEL_COLORS: dict[LogLevel, Color] = {
        LogLevel.ERROR: Color.parse("#f38ba8"),  # Red
        LogLevel.WARNING: Color.parse("#f9e2af"),  # Yellow
        LogLevel.INFO: Color.parse("#89b4fa"),  # Blue
        LogLevel.DEBUG: Color.parse("#a6e3a1"),  # Green
        LogLevel.TRACE: Color.parse("#cba6f7"),  # Purple
    }

    selected_index: reactive[int] = reactive(0, always_update=True)

    def __init__(self, *, entries: list[LogEntry] | None = None) -> None:
        """Initialize the log list widget."""
        super().__init__(
            show_cursor=True,
            zebra_stripes=False,
            header_height=1,
            cursor_type="row",
        )
        self._entries: list[LogEntry] = entries or []
        self._internal_update = False

    @property
    def entries(self) -> list[LogEntry]:
        """Return the list of log entries."""
        return list(self._entries)

    def set_entries(self, *, entries: list[LogEntry]) -> None:
        """Set the log entries and refresh the display."""
        self._entries = list(entries)
        if self.is_mounted:
            self._refresh_rows()

    def append_entries(self, *, entries: list[LogEntry]) -> None:
        """Append new entries to the list."""
        self._entries.extend(entries)
        if self.is_mounted:
            for entry in entries:
                self._add_entry_row(entry)

    def on_mount(self) -> None:
        """Set up the table columns on mount."""
        super().on_mount()
        self._setup_columns()
        self._refresh_rows()

    def _setup_columns(self) -> None:
        """Configure table columns."""
        self.add_columns("Level", "Time", "Message", "Line")

    def _refresh_rows(self) -> None:
        """Refresh all table rows from entries."""
        # Guard against refreshing before columns are set up
        if not self.ordered_columns:
            return
        self.clear()
        for entry in self._entries:
            self._add_entry_row(entry)

        # Restore cursor position
        if self._entries and self.selected_index < len(self._entries):
            self.move_cursor(row=self.selected_index)

    def _add_entry_row(self, entry: LogEntry) -> None:
        """Add a single entry as a table row."""
        level_color = self.LEVEL_COLORS.get(
            entry.level, Color.parse("#cdd6f4")
        )

        level_str = entry.level.name[:8]
        timestamp_str = (
            entry.timestamp.strftime("%H:%M:%S")
            if entry.timestamp
            else "--:--:--"
        )
        message_str = (
            entry.message[:60] + "..."
            if len(entry.message) > 60
            else entry.message
        )
        line_str = str(entry.line_number)

        # Create styled cells with rich markup
        level_cell = f"[{level_color.hex}]{level_str:8}[/]"
        time_cell = f"[{timestamp_str}]"
        message_cell = message_str
        line_cell = f"[{line_str}]"

        self.add_row(level_cell, time_cell, message_cell, line_cell)

    def watch_selected_index(self, index: int) -> None:
        """React to selection change."""
        if self._internal_update:
            return
        if self._entries and 0 <= index < len(self._entries):
            self.move_cursor(row=index)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection via DataTable."""
        cursor_row = event.cursor_row
        if cursor_row is not None:
            self._internal_update = True
            self.selected_index = cursor_row
            self._internal_update = False

    def on_data_table_row_highlighted(
        self, event: DataTable.RowHighlighted
    ) -> None:
        """Handle row highlight (cursor movement)."""
        cursor_row = event.cursor_row
        if cursor_row is not None:
            self._internal_update = True
            self.selected_index = cursor_row
            self._internal_update = False

    def select_next(self) -> None:
        """Select the next entry."""
        if self._entries and self.selected_index < len(self._entries) - 1:
            self.selected_index += 1
            self.move_cursor(row=self.selected_index)

    def select_previous(self) -> None:
        """Select the previous entry."""
        if self._entries and self.selected_index > 0:
            self.selected_index -= 1
            self.move_cursor(row=self.selected_index)

    def select_first(self) -> None:
        """Select the first entry."""
        if self._entries:
            self.selected_index = 0
            self.move_cursor(row=0)

    def select_last(self) -> None:
        """Select the last entry."""
        if self._entries:
            self.selected_index = len(self._entries) - 1
            self.move_cursor(row=self.selected_index)

    def get_selected_entry(self) -> LogEntry | None:
        """Get the currently selected log entry."""
        if self._entries and 0 <= self.selected_index < len(self._entries):
            return self._entries[self.selected_index]
        return None


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
        self._search_bar: SearchBarOverlay | None = None
        self._filter_engine = FilterEngine()

    def compose(self) -> ComposeResult:
        """Compose the main screen."""
        yield Header(id="header")

        self._search_bar = SearchBarOverlay(
            search_history=self._app_state.search_history,
            on_search=self._on_search,
            on_cancel=self._on_search_cancel,
        )
        yield self._search_bar

        with Container(id="log-container"):
            yield self._log_list
        yield Footer(id="status-bar")

    def on_mount(self) -> None:
        """Handle mount event."""
        if self._app_state.parse_result:
            self._refresh_entries()

    def _refresh_entries(self) -> None:
        """Refresh the log list with current filters."""
        if not self._app_state.parse_result:
            return

        all_entries = self._app_state.parse_result.entries
        filter_state = self._app_state.filter_state

        # Apply filters
        filtered = self._filter_engine.apply_filters(
            entries=all_entries,
            predicates=filter_state.parsed_filters,
            enabled_levels=filter_state.enabled_levels,
            case_sensitive=filter_state.case_sensitive,
        )

        self._log_list.set_entries(entries=filtered)

    def _on_search(self, query: str) -> None:
        """Handle search submission."""
        if not self._app_state.parse_result:
            return

        # Create new filter state with the query
        new_filter_state = create_filter_state(
            query=query,
            enabled_levels=self._app_state.filter_state.enabled_levels,
        )

        self._app_state.filter_state = new_filter_state
        self._refresh_entries()

    def _on_search_cancel(self) -> None:
        """Handle search cancellation."""
        pass

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()

    def action_search(self) -> None:
        """Open search dialog."""
        if self._search_bar:
            self._search_bar.show()
            self._search_bar.focus_input()

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
        selected = self._log_list.get_selected_entry()
        if selected and self._log_list.entries:
            self.app.push_screen(
                DetailScreen(
                    entries=self._log_list.entries,
                    current_index=self._log_list.selected_index,
                    on_navigate=self._on_detail_navigate,
                )
            )

    def _on_detail_navigate(self, new_index: int) -> None:
        """Handle navigation from detail screen."""
        self._log_list.selected_index = new_index

    def action_goto_first(self) -> None:
        """Go to first entry."""
        self._log_list.select_first()

    def action_goto_last(self) -> None:
        """Go to last entry."""
        self._log_list.select_last()

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


class DetailWidget(Static):
    """Widget for displaying formatted JSON with syntax highlighting."""

    DEFAULT_CSS = """
    DetailWidget {
        width: 100%;
        height: 100%;
        overflow: auto;
        background: transparent;
    }
    """

    # Catppuccin Mocha colors for JSON syntax highlighting
    COLORS = {
        "key": "#fab387",  # Peach
        "string": "#a6e3a1",  # Green
        "number": "#f9e2af",  # Yellow
        "boolean": "#cba6f7",  # Mauve
        "null": "#f38ba8",  # Red
        "punctuation": "#6c7086",  # Overlay0
    }

    def __init__(
        self,
        *,
        log_entry: LogEntry,
        indent: int = 2,
    ) -> None:
        """Initialize the detail widget.

        Args:
            log_entry: The log entry to display.
            indent: Indentation level for JSON formatting.
        """
        super().__init__()
        self._log_entry = log_entry
        self._indent = indent
        self._formatted_content = ""

    def on_mount(self) -> None:
        """Render the formatted JSON on mount."""
        self._formatted_content = self._format_json_with_colors(
            self._log_entry.parsed_data,
            indent=self._indent,
        )
        self.update(self._formatted_content)

    def _format_json_with_colors(
        self,
        data: dict[str, Any],
        *,
        indent: int = 2,
    ) -> str:
        """Format JSON with syntax highlighting colors.

        Args:
            data: The data to format.
            indent: Indentation level.

        Returns:
            Rich-formatted JSON string with color markup.
        """
        return self._format_value(data, indent=indent, current_indent=0)

    def _format_value(
        self,
        value: Any,
        *,
        indent: int,
        current_indent: int,
    ) -> str:
        """Format a single value with appropriate coloring.

        Args:
            value: The value to format.
            indent: Indentation level.
            current_indent: Current indentation depth.

        Returns:
            Rich-formatted value string.
        """
        if value is None:
            return f"[{self.COLORS['null']}]null[/]"
        elif isinstance(value, bool):
            return f"[{self.COLORS['boolean']}]{str(value).lower()}[/]"
        elif isinstance(value, (int, float)):
            return f"[{self.COLORS['number']}]{value}[/]"
        elif isinstance(value, str):
            escaped = (
                value.replace("\\", "\\\\")
                .replace('"', '\\"')
                .replace("\n", "\\n")
            )
            return f'[{self.COLORS["string"]}]"{escaped}"[/]'
        elif isinstance(value, dict):
            return self._format_dict(
                value, indent=indent, current_indent=current_indent
            )
        elif isinstance(value, list):
            return self._format_list(
                value, indent=indent, current_indent=current_indent
            )
        else:
            return str(value)

    def _format_dict(
        self,
        data: dict[str, Any],
        *,
        indent: int,
        current_indent: int,
    ) -> str:
        """Format a dictionary with syntax highlighting.

        Args:
            data: The dictionary to format.
            indent: Indentation level.
            current_indent: Current indentation depth.

        Returns:
            Rich-formatted dictionary string.
        """
        if not data:
            return "{}"

        inner_indent = " " * (current_indent + indent)
        closing_indent = " " * current_indent

        items = []
        for key, value in data.items():
            formatted_value = self._format_value(
                value,
                indent=indent,
                current_indent=current_indent + indent,
            )
            items.append(
                f'{inner_indent}[{self.COLORS["key"]}]"{key}"[/]'
                f"[{self.COLORS['punctuation']}]:[/] {formatted_value}"
            )

        return "\n".join(
            [f"[{self.COLORS['punctuation']}]{{[/]"]
            + items
            + [f"{closing_indent}[{self.COLORS['punctuation']}]}}[/]"]
        )

    def _format_list(
        self,
        data: list[Any],
        *,
        indent: int,
        current_indent: int,
    ) -> str:
        """Format a list with syntax highlighting.

        Args:
            data: The list to format.
            indent: Indentation level.
            current_indent: Current indentation depth.

        Returns:
            Rich-formatted list string.
        """
        if not data:
            return "[]"

        inner_indent = " " * (current_indent + indent)
        closing_indent = " " * current_indent

        items = []
        for value in data:
            formatted_value = self._format_value(
                value,
                indent=indent,
                current_indent=current_indent + indent,
            )
            items.append(f"{inner_indent}{formatted_value}")

        open_b = "["
        close_b = "]"
        punct = self.COLORS["punctuation"]
        return "\n".join(
            [f"[{punct}]{open_b * 2}[/]"]
            + items
            + [f"{closing_indent}[{punct}]{close_b * 2}[/]"]
        )

    def get_selected_entry(self) -> LogEntry:
        """Return the currently displayed log entry."""
        return self._log_entry


class DetailScreen(Screen):
    """Detail screen for viewing formatted JSON with navigation."""

    BINDINGS = [
        Binding("escape,h,q", "back", "Back", show=True),
        Binding("j,down", "scroll_down", "Down", show=False),
        Binding("k,up", "scroll_up", "Up", show=False),
        Binding("n,right", "next_entry", "Next", show=True),
        Binding("p,left", "previous_entry", "Previous", show=True),
        Binding("ctrl+c", "copy", "Copy", show=True),
    ]

    DEFAULT_CSS = """
    DetailScreen {
        layout: vertical;
    }

    #detail-header {
        height: 1;
        background: $surface;
        color: $text;
        text-style: bold;
        content-align: center middle;
        padding: 0 2;
    }

    #detail-container {
        height: 1fr;
        background: $surface-darken-1;
        padding: 1;
    }

    #detail-widget {
        width: 100%;
        height: 100%;
        overflow: auto;
    }

    #detail-footer {
        height: 1;
        background: $surface;
        color: $text-muted;
        content-align: center middle;
    }
    """

    def __init__(
        self,
        *,
        entries: list[LogEntry],
        current_index: int,
        on_navigate: Callable[[int], None] | None = None,
    ) -> None:
        """Initialize the detail screen.

        Args:
            entries: List of all log entries for navigation.
            current_index: Index of the currently displayed entry.
            on_navigate: Optional callback when navigating to a new entry.
        """
        super().__init__()
        self._entries = list(entries)
        self._current_index = current_index
        self._on_navigate = on_navigate
        self._detail_widget: DetailWidget | None = None

    def compose(self) -> ComposeResult:
        """Compose the detail screen."""
        yield Static(
            self._get_header_text(),
            id="detail-header",
        )
        with Container(id="detail-container"):
            self._detail_widget = DetailWidget(
                log_entry=self._entries[self._current_index],
                indent=2,
            )
            yield self._detail_widget
        yield Static(
            self._get_footer_text(),
            id="detail-footer",
        )

    def _get_header_text(self) -> str:
        """Generate header text with entry info."""
        entry = self._entries[self._current_index]
        level_color = LogListWidget.LEVEL_COLORS.get(
            entry.level, Color.parse("#cdd6f4")
        )
        return (
            f"Line {entry.line_number} | "
            f"[{level_color.hex}]{entry.level.name}[/] | "
            f"{entry.message[:50]}{'...' if len(entry.message) > 50 else ''}"
        )

    def _get_footer_text(self) -> str:
        """Generate footer text with navigation info."""
        total = len(self._entries)
        current = self._current_index + 1
        return (
            f"Entry {current}/{total} | n/p or j/k to navigate | "
            f"Esc/h/q to go back"
        )

    def _update_display(self) -> None:
        """Update the display with current entry."""
        if not self._detail_widget or not self._entries:
            return

        entry = self._entries[self._current_index]
        self._detail_widget._log_entry = entry
        self._detail_widget._formatted_content = (
            self._detail_widget._format_json_with_colors(
                entry.parsed_data,
                indent=2,
            )
        )
        self._detail_widget.update(self._detail_widget._formatted_content)

        # Update header and footer
        header = self.query_one("#detail-header", Static)
        header.update(self._get_header_text())
        footer = self.query_one("#detail-footer", Static)
        footer.update(self._get_footer_text())

    def action_back(self) -> None:
        """Go back to main screen."""
        if self._on_navigate:
            self._on_navigate(self._current_index)
        self.app.pop_screen()

    def action_copy(self) -> None:
        """Copy the JSON content."""
        pass  # Will be implemented in T10

    def action_scroll_down(self) -> None:
        """Scroll down."""
        if self._detail_widget:
            self._detail_widget.scroll_down()

    def action_scroll_up(self) -> None:
        """Scroll up."""
        if self._detail_widget:
            self._detail_widget.scroll_up()

    def action_next_entry(self) -> None:
        """Navigate to the next log entry."""
        if self._current_index < len(self._entries) - 1:
            self._current_index += 1
            self._update_display()

    def action_previous_entry(self) -> None:
        """Navigate to the previous log entry."""
        if self._current_index > 0:
            self._current_index -= 1
            self._update_display()


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
