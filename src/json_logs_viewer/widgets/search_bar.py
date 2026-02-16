from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

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
