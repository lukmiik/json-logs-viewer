from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

from textual.containers import ScrollableContainer
from textual.message import Message
from textual.widgets import ListItem, ListView, Static

from json_logs_viewer.models import LogEntry

if TYPE_CHECKING:
    from json_logs_viewer.app import LogViewerApp


class LogList(ListView):
    """List view for displaying log entries."""

    can_focus = True

    SCROLLOFF: int = 3

    BINDINGS = ListView.BINDINGS + [
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        ("h", "scroll_left", "Left"),
        ("l", "scroll_right", "Right"),
        ("g", "scroll_top", "Top"),
        ("G", "scroll_bottom", "Bottom"),
        ("enter", "select_cursor", "View Details"),
        ("/", "app.focus_search", "Focus Search"),
        ("w", "app.toggle_wrap", "Toggle Wrap"),
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
            self.watch(
                self.app, "wrap_log_lines", self._on_wrap_log_lines_changed
            )
        self._update_wrap_class()

    def _on_wrap_log_lines_changed(self, wrap_log_lines: bool) -> None:
        self._update_wrap_class()
        self._update_min_width()

    def _update_wrap_class(self) -> None:
        if self.app and hasattr(self.app, "wrap_log_lines"):
            app = cast("LogViewerApp", self.app)
            if app.wrap_log_lines:
                self.add_class("-wrap")
            else:
                self.remove_class("-wrap")

    def _update_min_width(self) -> None:
        if not self._app:
            return
        if not self._app.wrap_log_lines:
            max_len = 0
            for log in self._log_entries:
                json_str = json.dumps(log.data, ensure_ascii=False)
                max_len = max(max_len, len(json_str))
            if max_len > 0:
                self.styles.min_width = max_len + 20
            else:
                self.styles.min_width = 0
        else:
            self.styles.min_width = 0

    def _on_filtered_logs_changed(self, filtered_logs: list[LogEntry]) -> None:
        """Rebuild list items when filtered_logs changes."""
        self._log_entries = filtered_logs
        self.clear()
        max_len = 0
        for log in self._log_entries:
            json_str = json.dumps(log.data, ensure_ascii=False)
            max_len = max(max_len, len(json_str))
            item = ListItem(Static(json_str))
            item.log_entry = log  # type: ignore[attr-defined]
            self.mount(item)
        if self._app and not self._app.wrap_log_lines and max_len > 0:
            self.styles.min_width = max_len + 20
        else:
            self.styles.min_width = 0
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

    def _scroll_highlighted_into_view(self) -> None:
        """Scroll parent container with scrolloff padding."""
        if self.index is None or self.index >= len(self.children):
            return
        if self.parent is None:
            return
        container = self.parent
        top_idx = max(0, self.index - self.SCROLLOFF)
        bottom_idx = min(
            len(self.children) - 1,
            self.index + self.SCROLLOFF,
        )
        self.children[top_idx].scroll_visible(animate=False)
        self.children[bottom_idx].scroll_visible(animate=False)
        container.scroll_to_widget(  # type: ignore[union-attr]
            self.children[top_idx],
            animate=False,
        )
        container.scroll_to_widget(  # type: ignore[union-attr]
            self.children[bottom_idx],
            animate=False,
        )

    def watch_index(
        self,
        old_index: int | None,
        new_index: int | None,
    ) -> None:
        """Ensure highlighted item is visible."""
        super().watch_index(old_index, new_index)
        if new_index is not None:
            self.call_after_refresh(
                self._scroll_highlighted_into_view,
            )

    def action_scroll_top(self) -> None:
        if self._app:
            self._app.selected_index = 0
            if self.parent is not None:
                self.call_after_refresh(self._scroll_to_top)

    def _scroll_to_top(self) -> None:
        """Scroll container to the very top."""
        if self.parent is not None:
            container = cast(ScrollableContainer, self.parent)
            container.scroll_to(y=0, animate=False)

    def action_scroll_bottom(self) -> None:
        if self._app:
            self._app.selected_index = max(0, len(self._log_entries) - 1)

    def action_scroll_left(self) -> None:
        """Scroll parent container left horizontally."""
        if self.parent is not None:
            container = cast(ScrollableContainer, self.parent)
            container.scroll_left()

    def action_scroll_right(self) -> None:
        """Scroll parent container right horizontally."""
        if self.parent is not None:
            container = cast(ScrollableContainer, self.parent)
            container.scroll_right()
