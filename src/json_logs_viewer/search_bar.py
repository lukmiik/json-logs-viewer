"""Search bar widget with history support."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container
from textual.events import Key
from textual.reactive import reactive
from textual.widgets import Input, Label, ListItem, ListView, Static

if TYPE_CHECKING:
    from json_logs_viewer.models import SearchHistory, SearchHistoryEntry


class SearchBarWidget(Container):
    """Search bar widget with input and history dropdown."""

    DEFAULT_CSS = """
    SearchBarWidget {
        height: auto;
        background: $surface;
        border: solid $border;
        padding: 0;
        display: none;
    }

    SearchBarWidget.visible {
        display: block;
    }

    SearchBarWidget > #search-input {
        height: 1;
        background: $surface;
        color: $text;
        border: none;
    }

    SearchBarWidget > #search-input:focus {
        border: none;
    }

    SearchBarWidget > #history-dropdown {
        height: auto;
        max-height: 10;
        background: $surface;
        border: solid $border;
        display: none;
    }

    SearchBarWidget > #history-dropdown.visible {
        display: block;
    }

    SearchBarWidget ListItem {
        height: 1;
        background: $surface;
        color: $text;
    }

    SearchBarWidget ListItem:hover {
        background: $selection;
    }

    SearchBarWidget ListItem.--highlight {
        background: $selection;
    }
    """

    current_query: reactive[str] = reactive("", always_update=True)
    history_visible: reactive[bool] = reactive(False, always_update=True)

    def __init__(
        self,
        *,
        search_history: SearchHistory | None = None,
        on_search: Callable[[str], None] | None = None,
        on_cancel: Callable[[], None] | None = None,
    ) -> None:
        """Initialize the search bar widget.

        Args:
            search_history: Optional search history manager.
            on_search: Callback when search submitted (receives query string).
            on_cancel: Callback when search is cancelled.
        """
        super().__init__()
        self._search_history = search_history
        self._on_search = on_search
        self._on_cancel = on_cancel
        self._input: Input | None = None
        self._history_dropdown: ListView | None = None
        self._history_entries: list[SearchHistoryEntry] = []
        self._history_index: int = -1

    def compose(self) -> ComposeResult:
        """Compose the search bar widget."""
        self._input = Input(
            id="search-input",
            placeholder="Search (field:value, AND/OR, !negation)...",
        )
        yield self._input

        self._history_dropdown = ListView(id="history-dropdown")
        yield self._history_dropdown

    def on_mount(self) -> None:
        """Handle mount event."""
        if self._input:
            self._input.focus()

    def show(self) -> None:
        """Show the search bar."""
        self.add_class("visible")
        if self._input:
            self._input.focus()

    def hide(self) -> None:
        """Hide the search bar."""
        self.remove_class("visible")
        self._hide_history()
        if self._input:
            self._input.blur()

    def is_visible(self) -> bool:
        """Check if the search bar is visible."""
        return "visible" in self.classes

    def get_query(self) -> str:
        """Get the current search query."""
        return self._input.value if self._input else ""

    def set_query(self, *, query: str) -> None:
        """Set the search query."""
        if self._input:
            self._input.value = query
            self._input.cursor_position = len(query)

    def _show_history(self) -> None:
        """Show the history dropdown."""
        if not self._history_dropdown or not self._search_history:
            return

        self._history_entries = self._search_history.get_recent(count=10)

        if not self._history_entries:
            return

        self._history_dropdown.clear()
        for entry in self._history_entries:
            label = self._format_history_entry(entry)
            self._history_dropdown.append(ListItem(Label(label)))

        self._history_dropdown.add_class("visible")
        self.history_visible = True
        self._history_index = 0
        if self._history_dropdown.children:
            self._history_dropdown.index = 0

    def _hide_history(self) -> None:
        """Hide the history dropdown."""
        if self._history_dropdown:
            self._history_dropdown.remove_class("visible")
        self.history_visible = False
        self._history_index = -1

    def _format_history_entry(self, entry: SearchHistoryEntry) -> str:
        """Format a history entry for display."""
        count_str = (
            f" ({entry.execution_count}x)" if entry.execution_count > 1 else ""
        )
        return f"{entry.query}{count_str}"

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes."""
        self.current_query = event.value
        # Don't show history on input change, only on up/down navigation

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        self._submit_search()

    def _submit_search(self) -> None:
        """Submit the current search query."""
        query = self.get_query()

        # Add to history
        if self._search_history and query.strip():
            self._search_history.add(query=query)

        # Call the search callback
        if self._on_search:
            self._on_search(query)

        self._hide_history()
        self.hide()

    def action_cancel(self) -> None:
        """Cancel the search."""
        if self._on_cancel:
            self._on_cancel()
        self._hide_history()
        self.hide()

    def action_history_up(self) -> None:
        """Navigate to previous history entry."""
        if not self._search_history:
            return

        if not self.history_visible:
            self._show_history()
            return

        if self._history_index > 0:
            self._history_index -= 1
            self._select_history_item(self._history_index)

    def action_history_down(self) -> None:
        """Navigate to next history entry."""
        if not self.history_visible or not self._history_entries:
            return

        if self._history_index < len(self._history_entries) - 1:
            self._history_index += 1
            self._select_history_item(self._history_index)
        else:
            # Past the end - clear selection and stay at current input
            self._history_index = len(self._history_entries)
            if self._input:
                self._input.value = self.current_query
                self._input.cursor_position = len(self.current_query)

    def _select_history_item(self, index: int) -> None:
        """Select a history item by index."""
        if (
            not self._history_entries
            or index < 0
            or index >= len(self._history_entries)
        ):
            return

        if self._history_dropdown:
            self._history_dropdown.index = index

        entry = self._history_entries[index]
        if self._input:
            self._input.value = entry.query
            self._input.cursor_position = len(entry.query)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle history item selection."""
        if self._history_dropdown and event.item:
            index = self._history_dropdown.index
            if index is not None and 0 <= index < len(self._history_entries):
                entry = self._history_entries[index]
                if self._input:
                    self._input.value = entry.query
                    self._input.cursor_position = len(entry.query)
                self._submit_search()

    def on_key(self, event: Key) -> None:
        """Handle key events."""
        key = event.key

        if key == "escape":
            if self.history_visible:
                self._hide_history()
            else:
                self.action_cancel()
            event.stop()
        elif key == "up":
            if self.history_visible:
                self.action_history_up()
            else:
                self.action_history_up()  # Show history on first up
            event.stop()
        elif key == "down":
            if self.history_visible:
                self.action_history_down()
            event.stop()
        elif key == "enter":
            self._submit_search()
            event.stop()


class SearchBarOverlay(Container):
    """Full-screen overlay container for the search bar."""

    DEFAULT_CSS = """
    SearchBarOverlay {
        layout: vertical;
        width: 100%;
        height: auto;
        background: $surface;
        border-bottom: solid $border;
        padding: 0 1;
    }

    SearchBarOverlay > Static {
        height: 1;
        color: $text-muted;
        content-align: center middle;
    }
    """

    def __init__(
        self,
        *,
        search_history: SearchHistory | None = None,
        on_search: Callable[[str], None] | None = None,
        on_cancel: Callable[[], None] | None = None,
    ) -> None:
        """Initialize the search bar overlay.

        Args:
            search_history: Optional search history manager.
            on_search: Callback when search is submitted.
            on_cancel: Callback when search is cancelled.
        """
        super().__init__()
        self._search_bar = SearchBarWidget(
            search_history=search_history,
            on_search=on_search,
            on_cancel=on_cancel,
        )

    def compose(self) -> ComposeResult:
        """Compose the search bar overlay."""
        help_text = (
            "Search: field:value | AND/OR | !negation | "
            "has:field | >/</>=/<=/!="
        )
        yield Static(help_text)
        yield self._search_bar

    def show(self) -> None:
        """Show the search bar overlay."""
        self._search_bar.show()
        self._search_bar.set_query(query="")

    def hide(self) -> None:
        """Hide the search bar overlay."""
        self._search_bar.hide()

    def is_visible(self) -> bool:
        """Check if the search bar overlay is visible."""
        return self._search_bar.is_visible()

    def focus_input(self) -> None:
        """Focus the search input."""
        self._search_bar.show()

    def get_query(self) -> str:
        """Get the current search query."""
        return self._search_bar.get_query()

    def set_query(self, *, query: str) -> None:
        """Set the search query."""
        self._search_bar.set_query(query=query)
