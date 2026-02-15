from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any, cast

from rich.segment import Segment
from rich.style import Style
from textual.cache import LRUCache
from textual.geometry import Size
from textual.message import Message
from textual.scroll_view import ScrollView
from textual.strip import Strip

from json_logs_viewer.models import LogEntry

if TYPE_CHECKING:
    from json_logs_viewer.app import LogViewerApp


class LogList(ScrollView):
    """Virtual-scrolling log list using Textual's Line API."""

    can_focus = True

    SCROLLOFF: int = 3

    COMPONENT_CLASSES = {
        "loglist--cursor",
    }

    DEFAULT_CSS = """
    LogList .loglist--cursor {
        background: $accent;
    }
    """

    BINDINGS = [
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        ("down", "cursor_down", "Down"),
        ("up", "cursor_up", "Up"),
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

        def __init__(self, *, log_entry: LogEntry) -> None:
            self.log_entry = log_entry
            super().__init__()

    def __init__(self, **kwargs: Any) -> None:  # noqa: ANN401
        super().__init__(**kwargs)
        self._log_entries: list[LogEntry] = []
        self._line_cache: LRUCache[int, str] = LRUCache(maxsize=2000)
        self._cursor_index: int = 0
        self._max_content_width: int = 0
        self._pending_scroll: bool = False

    def on_mount(self) -> None:
        """Set up watchers for app state changes."""
        if self.app:
            self.watch(
                self.app, "filtered_logs", self._on_filtered_logs_changed
            )
            self.watch(
                self.app, "selected_index", self._on_selected_index_changed
            )

    def on_resize(self) -> None:
        """Apply pending scroll when the widget gets its size."""
        if self._pending_scroll:
            self._pending_scroll = False
            self._scroll_cursor_into_view()

    def set_logs(self, *, logs: list[LogEntry]) -> None:
        """Update the log entries and recalculate virtual size."""
        t_start = time.perf_counter()
        self._log_entries = logs
        self._line_cache = LRUCache(maxsize=2000)

        max_len = 0
        for log in logs:
            json_str = json.dumps(log.data, ensure_ascii=False)
            max_len = max(max_len, len(json_str))
        self._max_content_width = max_len

        self._update_virtual_size()

        if self._cursor_index >= len(logs):
            self._cursor_index = max(0, len(logs) - 1)

        self.refresh()
        self.log.info(
            f"[PERF] set_logs ({len(logs)} entries): "
            f"{time.perf_counter() - t_start:.3f}s"
        )

    def _update_virtual_size(self) -> None:
        """Set virtual_size based on number of log entries."""
        height = len(self._log_entries)
        width = self._max_content_width + 2
        self.virtual_size = Size(width, height)

    def render_line(self, y: int) -> Strip:
        """Render a single line — only called for visible lines."""
        scroll_x, scroll_y = self.scroll_offset
        line_index = y + scroll_y

        if line_index < 0 or line_index >= len(self._log_entries):
            return Strip.blank(self.size.width)

        if line_index not in self._line_cache:
            log = self._log_entries[line_index]
            self._line_cache[line_index] = json.dumps(
                log.data, ensure_ascii=False
            )
        text = self._line_cache[line_index]

        is_highlighted = line_index == self._cursor_index
        if is_highlighted:
            style = self.get_component_rich_style("loglist--cursor")
        else:
            style = Style()

        # Pad text to fill the full width so highlight covers the whole row
        display_width = max(self._max_content_width + 2, self.size.width)
        padded = text.ljust(display_width)

        segments = [Segment(padded, style)]
        strip = Strip(segments, display_width)
        strip = strip.crop(scroll_x, scroll_x + self.size.width)
        return strip

    def _on_filtered_logs_changed(self, filtered_logs: list[LogEntry]) -> None:
        """Update log entries when filtered_logs changes."""
        self.set_logs(logs=filtered_logs)
        if self._app:
            idx = self._app.selected_index
            if idx < len(self._log_entries):
                self._cursor_index = idx
            # Mark scroll as pending — applied in on_resize when the
            # widget has its actual size, before the first visible paint.
            self._pending_scroll = True
            self.refresh()

    def _on_selected_index_changed(self, selected_index: int) -> None:
        """Move cursor to match app.selected_index."""
        if (
            0 <= selected_index < len(self._log_entries)
            and self._cursor_index != selected_index
        ):
            self._cursor_index = selected_index
            self._scroll_cursor_into_view()
            self.refresh()

    def _scroll_cursor_into_view(self) -> None:
        """Ensure cursor is visible with SCROLLOFF padding."""
        if not self._log_entries:
            return
        visible_top = self.scroll_offset.y
        visible_bottom = visible_top + self.size.height - 1
        target_top = self._cursor_index - self.SCROLLOFF
        target_bottom = self._cursor_index + self.SCROLLOFF

        if target_top < visible_top:
            self.scroll_to(y=max(0, target_top), animate=False)
        elif target_bottom > visible_bottom:
            self.scroll_to(
                y=max(0, target_bottom - self.size.height + 1), animate=False
            )

    def action_cursor_down(self) -> None:
        if self._cursor_index < len(self._log_entries) - 1:
            self._cursor_index += 1
            if self._app:
                self._app.selected_index = self._cursor_index
            self._scroll_cursor_into_view()
            self.refresh()

    def action_cursor_up(self) -> None:
        if self._cursor_index > 0:
            self._cursor_index -= 1
            if self._app:
                self._app.selected_index = self._cursor_index
            self._scroll_cursor_into_view()
            self.refresh()

    def action_scroll_top(self) -> None:
        self._cursor_index = 0
        if self._app:
            self._app.selected_index = 0
        self.scroll_to(y=0, animate=False)
        self.refresh()

    def action_scroll_bottom(self) -> None:
        last = max(0, len(self._log_entries) - 1)
        self._cursor_index = last
        if self._app:
            self._app.selected_index = last
        self.scroll_to(y=last, animate=False)
        self.refresh()

    def action_select_cursor(self) -> None:
        if 0 <= self._cursor_index < len(self._log_entries):
            log = self._log_entries[self._cursor_index]
            self.post_message(self.LogSelected(log_entry=log))

    def action_scroll_left(self) -> None:
        self.scroll_left()

    def action_scroll_right(self) -> None:
        self.scroll_right()
