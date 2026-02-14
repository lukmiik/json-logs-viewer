from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

from textual.message import Message
from textual.widgets import ListItem, ListView, Static

from json_logs_viewer.models import LogEntry

if TYPE_CHECKING:
    from json_logs_viewer.app import LogViewerApp


class LogList(ListView):
    """List view for displaying log entries."""

    can_focus = True

    BINDINGS = ListView.BINDINGS + [
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        ("g", "scroll_top", "Top"),
        ("G", "scroll_bottom", "Bottom"),
        ("enter", "select_cursor", "View Details"),
        ("/", "app.focus_search", "Focus Search"),
        ("q", "app.quit", "Quit"),
    ]

    @property
    def _app(self) -> LogViewerApp:
        return cast("LogViewerApp", self.app)

    class LogSelected(Message):
        """Posted when a log entry is selected."""

        def __init__(self, log_entry: LogEntry) -> None:
            self.log_entry = log_entry
            super().__init__()

    def __init__(self, **kwargs: Any) -> None:  # noqa: ANN401
        super().__init__(**kwargs)
        self._log_entries: list[LogEntry] = []

    def on_mount(self) -> None:
        """Set up watchers for app state changes."""
        if self.app:
            self.watch(
                self.app, "filtered_logs", self._on_filtered_logs_changed
            )
            self.watch(
                self.app, "selected_index", self._on_selected_index_changed
            )

    def _on_filtered_logs_changed(self, filtered_logs: list[LogEntry]) -> None:
        """Rebuild list items when filtered_logs changes."""
        self._log_entries = filtered_logs
        self.clear()
        for log in self._log_entries:
            json_str = json.dumps(log.data, ensure_ascii=False)
            item = ListItem(Static(json_str))
            item.log_entry = log  # type: ignore[attr-defined]
            self.mount(item)
        if self._app:
            idx = self._app.selected_index
            if idx >= len(self._log_entries):
                self._app.selected_index = max(0, len(self._log_entries) - 1)
            else:
                self.index = self._app.selected_index

    def _on_selected_index_changed(self, selected_index: int) -> None:
        """Move cursor to match app.selected_index."""
        if (
            0 <= selected_index < len(self._log_entries)
            and self.index != selected_index
        ):
            self.index = selected_index

    def on_list_view_highlighted(self, _event: ListView.Highlighted) -> None:
        """Update app.selected_index when user navigates."""
        if self._app and self.index is not None:
            self._app.selected_index = self.index

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Post LogSelected message when user presses Enter."""
        if event.item and hasattr(event.item, "log_entry"):
            log_entry = cast(LogEntry, event.item.log_entry)
            self.post_message(self.LogSelected(log_entry))

    def action_scroll_top(self) -> None:
        if self._app:
            self._app.selected_index = 0

    def action_scroll_bottom(self) -> None:
        if self._app:
            self._app.selected_index = max(0, len(self._log_entries) - 1)
