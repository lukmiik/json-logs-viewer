from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from textual.widgets import Input

from json_logs_viewer.constants import SEARCH_HISTORY_LIMIT
from json_logs_viewer.selection_copier import SelectionCopier
from json_logs_viewer.widgets.log_list import LogList

if TYPE_CHECKING:
    from json_logs_viewer.app import LogViewerApp  # noqa: F401


def add_to_history(*, history: list[str], query: str, limit: int) -> list[str]:
    """Return a new history list with `query` as the most recent entry.

    A query that is already in the history is moved to the end instead of
    being duplicated, so every entry is unique. A new list is returned
    (never mutated in place) so assigning it to a reactive fires watchers.
    """
    return [*(item for item in history if item != query), query][-limit:]


class SearchBar(Input):
    """Search input for filter queries."""

    BINDINGS = [("escape", "focus_log_list", "Focus Log List")]

    def __init__(self, **kwargs: Any) -> None:  # noqa: ANN401
        super().__init__(**kwargs)
        self.placeholder = "Filter logs... (/: focus)"
        self._selection_copier = SelectionCopier(
            owner=self, clear_selection=self._clear_selection
        )

    def watch_selection(self) -> None:
        # Watching the reactive sees every change, from keys and the mouse
        # alike, after it happened (a Key handler runs before the key's
        # binding moves the selection).
        self._selection_copier.update(selected_text=self.selected_text)

    def _clear_selection(self) -> None:
        self.cursor_position = self.cursor_position

    def on_input_submitted(self) -> None:
        """Apply filter when Enter pressed."""
        query = self.value.strip()
        if not self.app:
            return
        app = cast("LogViewerApp", self.app)
        app.filter_query = query
        if query:
            app.search_history = add_to_history(
                history=app.search_history,
                query=query,
                limit=SEARCH_HISTORY_LIMIT,
            )

        self.action_focus_log_list()

    def action_focus_log_list(self) -> None:
        """Focus the log list."""
        self.app.query_one("#logs", LogList).focus()

    def on_blur(self) -> None:
        """Hide the search bar when focus leaves it.

        The input keeps its text, so `/` reopens it with the active query,
        and the status bar shows that query meanwhile.
        """
        self.display = False

    def on_focus(self) -> None:
        # Visibility follows focus: Textual can hand focus back (e.g. when
        # the terminal window is refocused), which must not leave the input
        # focused but invisible.
        self.display = True
