from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from textual import events, on
from textual.timer import Timer
from textual.widgets import Input

from json_logs_viewer.constants import SEARCH_HISTORY_LIMIT
from json_logs_viewer.widgets.log_list import LogList

if TYPE_CHECKING:
    from json_logs_viewer.app import LogViewerApp  # noqa: F401


class SearchBar(Input):
    """Search input for filter queries."""

    BINDINGS = [("escape", "focus_log_list", "Focus Log List")]

    def __init__(self, **kwargs: Any) -> None:  # noqa: ANN401
        super().__init__(**kwargs)
        self.placeholder = "Filter logs... (/: focus)"
        self._selection_timer: Timer | None = None
        self._last_selected_text: str = ""

    @on(events.MouseUp)
    @on(events.Key)
    def _check_selection(self, event: events.MouseUp | events.Key) -> None:
        selected_text = self.selected_text
        if selected_text and selected_text != self._last_selected_text:
            self._last_selected_text = selected_text
            if self._selection_timer is not None:
                self._selection_timer.stop()
            self._selection_timer = self.set_timer(
                0.5, self._copy_selection_to_clipboard
            )

    def _copy_selection_to_clipboard(self) -> None:
        self._selection_timer = None
        if self._last_selected_text:
            self.app.copy_to_clipboard(self._last_selected_text)
            self.notify("Copied selection to clipboard")
            self._last_selected_text = ""
            self.cursor_position = self.cursor_position

    def on_input_submitted(self) -> None:
        """Apply filter when Enter pressed."""
        query = self.value.strip()
        if not self.app:
            return
        app = cast("LogViewerApp", self.app)
        app.filter_query = query
        if query:
            history = app.search_history
            if not history or history[-1] != query:
                history.append(query)
                if len(history) > SEARCH_HISTORY_LIMIT:
                    history.pop(0)

        self.action_focus_log_list()

    def action_focus_log_list(self) -> None:
        """Focus the log list."""
        self.app.query_one("#logs", LogList).focus()

    def on_blur(self) -> None:
        """Hide search bar when leaving it with no active query."""
        if not self.app:
            return

        app = cast("LogViewerApp", self.app)
        if not self.value.strip() and not app.filter_query.strip():
            self.display = False
