from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

from rich.console import Console
from rich.segment import Segment
from rich.style import Style
from rich.text import Text
from textual.binding import Binding
from textual.cache import LRUCache
from textual.geometry import Size
from textual.message import Message
from textual.scroll_view import ScrollView
from textual.strip import Strip

from json_logs_viewer.filter_engine import FilterError, parse_filter
from json_logs_viewer.models import LogEntry

if TYPE_CHECKING:
    from json_logs_viewer.app import LogViewerApp

_console = Console()


def _wrap_text(*, text: str, width: int) -> list[str]:
    """Wrap text to given width using Rich's word-aware wrapping.

    Args:
        text: The text to wrap.
        width: Maximum width per line.

    Returns:
        List of wrapped lines.
    """
    if width <= 0:
        return [text]

    rich_text = Text(text)
    wrapped = rich_text.wrap(_console, width=width)
    return [line.plain for line in wrapped]


class LogList(ScrollView):
    """Virtual-scrolling log list using Textual's Line API."""

    can_focus = True

    SCROLLOFF: int = 3

    COMPONENT_CLASSES = {
        "loglist--cursor",
    }

    DEFAULT_CSS = """
    LogList .loglist--cursor {
        background: $block-cursor-background;
    }
    """

    BINDINGS = [
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("up", "cursor_up", "Up", show=False),
        ("h", "scroll_left", "Left"),
        ("l", "scroll_right", "Right"),
        Binding("ctrl+u", "page_up", "Page Up", show=False),
        Binding("ctrl+d", "page_down", "Page Down", show=False),
        Binding("n", "next_match", "Next Match", show=False),
        Binding("N", "prev_match", "Prev Match", show=False),
        ("g", "scroll_top", "Top"),
        ("G", "scroll_bottom", "Bottom"),
        ("enter", "select_cursor", "Details"),
        ("/", "app.focus_search", "Search"),
        ("w", "app.toggle_wrap", "Wrap"),
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
        self._line_width_cache: dict[int, int] = {}
        self._cursor_index: int = 0
        self._max_content_width: int = 0
        self._pending_scroll: bool = False
        self._wrap_mode: bool = False
        self._wrapped_lines: list[tuple[int, int]] = []
        self._entry_start_rows: dict[int, int] = {}
        self._match_flags: list[bool] = []
        self._highlight_mode: bool = False
        self._active_query: str = ""

    def on_mount(self) -> None:
        """Set up watchers for app state changes."""
        if self.app:
            self.watch(
                self.app, "filtered_logs", self._on_filtered_logs_changed
            )
            self.watch(
                self.app, "selected_index", self._on_selected_index_changed
            )
            self.watch(self.app, "wrap_log_lines", self._on_wrap_mode_changed)
            self.watch(
                self.app, "filter_query", self._on_filter_settings_changed
            )
            self.watch(
                self.app, "case_sensitive", self._on_filter_settings_changed
            )
            self.watch(
                self.app,
                "highlight_matches",
                self._on_filter_settings_changed,
            )
            self._recompute_match_flags()
            self.watch(self, "scroll_y", self._on_scroll_y_changed)

    def on_resize(self) -> None:
        """Apply pending scroll when the widget gets its size."""
        self._apply_pending_scroll()
        if self._wrap_mode:
            self._recalculate_wrap()
        self._update_max_width_for_visible_range()
        self._update_virtual_size()

    def _on_scroll_y_changed(self, _: float) -> None:
        """Handle vertical scroll position changes."""
        if not self._wrap_mode:
            self._update_max_width_for_visible_range()
            self._update_virtual_size()

    def _on_wrap_mode_changed(self, wrap_log_lines: bool) -> None:
        """Handle wrap mode toggle."""
        self._wrap_mode = wrap_log_lines
        if wrap_log_lines:
            self._recalculate_wrap()
        else:
            self._wrapped_lines = []
            self._entry_start_rows = {}
        self._update_virtual_size()
        self._scroll_cursor_into_view()
        self.refresh()

    def _get_content_width(self) -> int:
        """Get available content width, accounting for scrollbar if needed."""
        width = self.size.width
        if width <= 0:
            return 80

        if self._wrap_mode and len(self._wrapped_lines) <= self.size.height:
            return width

        return width - 1

    def _recalculate_wrap(self) -> None:
        """Recalculate wrapped line mapping."""
        self._wrapped_lines = []
        self._entry_start_rows = {}

        width = self.size.width
        if width <= 0:
            return

        for entry_idx, log in enumerate(self._log_entries):
            if entry_idx not in self._line_cache:
                self._line_cache[entry_idx] = json.dumps(
                    log.data, ensure_ascii=False
                )

        def build_wrapped_lines(*, content_width: int) -> int:
            total = 0
            for entry_idx in range(len(self._log_entries)):
                text = self._line_cache[entry_idx]
                wrapped = _wrap_text(text=text, width=content_width)
                total += len(wrapped)
            return total

        estimated_lines = build_wrapped_lines(content_width=width)
        needs_scrollbar = estimated_lines > self.size.height
        content_width = width - 1 if needs_scrollbar else width

        current_row = 0
        for entry_idx in range(len(self._log_entries)):
            self._entry_start_rows[entry_idx] = current_row
            text = self._line_cache[entry_idx]
            wrapped = _wrap_text(text=text, width=content_width)
            for sub_line in range(len(wrapped)):
                self._wrapped_lines.append((entry_idx, sub_line))
            current_row += len(wrapped)

    def _update_max_width_for_visible_range(self) -> None:
        """Update max content width based on visible lines in viewport."""
        if not self._log_entries:
            self._max_content_width = 0
            return

        scroll_y = self.scroll_offset.y
        visible_height = self.size.height if self.size.height > 0 else 50

        start_idx = max(0, scroll_y)
        end_idx = min(len(self._log_entries), scroll_y + visible_height)

        if start_idx >= end_idx:
            start_idx = 0
            end_idx = min(len(self._log_entries), visible_height)

        max_width = 0
        for idx in range(start_idx, end_idx):
            if idx in self._line_width_cache:
                max_width = max(max_width, self._line_width_cache[idx])
            elif idx in self._line_cache:
                max_width = max(max_width, len(self._line_cache[idx]))

        self._max_content_width = max_width

    def set_logs(self, *, logs: list[LogEntry]) -> None:
        """Update the log entries and recalculate virtual size."""
        self._log_entries = logs
        self._line_cache = LRUCache(maxsize=2000)
        self._line_width_cache = {}
        self._recompute_match_flags()

        for idx, log in enumerate(logs):
            json_str = json.dumps(log.data, ensure_ascii=False)
            self._line_width_cache[idx] = len(json_str)

        self._update_max_width_for_visible_range()

        if self._wrap_mode:
            self._recalculate_wrap()

        self._update_virtual_size()

        if self._cursor_index >= len(logs):
            self._cursor_index = max(0, len(logs) - 1)

        self.refresh()

    def _on_filter_settings_changed(self, *_: object) -> None:
        self._recompute_match_flags()
        self.refresh()

    def _recompute_match_flags(self) -> None:
        if not self.app:
            self._match_flags = [True] * len(self._log_entries)
            self._highlight_mode = False
            self._active_query = ""
            return

        app = self._app
        self._highlight_mode = app.highlight_matches
        self._active_query = app.filter_query.strip()

        if not self._highlight_mode or not self._active_query:
            self._match_flags = [True] * len(self._log_entries)
            return

        try:
            matcher = parse_filter(
                query=self._active_query,
                case_sensitive=app.case_sensitive,
            )
        except FilterError:
            self._match_flags = [False] * len(self._log_entries)
            return

        self._match_flags = [
            matcher(log_entry) for log_entry in self._log_entries
        ]

    def _style_for_entry(self, *, entry_idx: int, base: Style) -> Style:
        if not self._highlight_mode or not self._active_query:
            return base

        if entry_idx >= len(self._match_flags):
            return base

        if self._match_flags[entry_idx]:
            return base + Style(bold=True)

        return base + Style(dim=True)

    def _update_virtual_size(self) -> None:
        """Set virtual_size based on number of log entries."""
        if self._wrap_mode:
            height = (
                len(self._wrapped_lines)
                if self._wrapped_lines
                else len(self._log_entries)
            )
            width = self.size.width if self.size.width > 0 else 80
            self.styles.overflow_x = "hidden"
        else:
            height = len(self._log_entries)
            width = self._max_content_width + 2
            self.styles.overflow_x = "auto"
        self.virtual_size = Size(width, height)

    def _blank_strip(self) -> Strip:
        """Return a blank strip with an explicit style."""
        width = max(0, self.size.width)
        return Strip([Segment(" " * width, Style())], width)

    def render_line(self, y: int) -> Strip:
        """Render a single line — only called for visible lines."""
        scroll_x, scroll_y = self.scroll_offset

        if self._wrap_mode:
            return self._render_wrapped_line(y=y, scroll_y=scroll_y)

        line_index = y + scroll_y

        if line_index < 0 or line_index >= len(self._log_entries):
            return self._blank_strip()

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
            style = self._style_for_entry(
                entry_idx=line_index, base=self.rich_style or Style()
            )

        display_width = max(self._max_content_width + 2, self.size.width)
        padded = text.ljust(display_width)

        segments = [Segment(padded, style)]
        strip = Strip(segments, display_width)
        strip = strip.crop(scroll_x, scroll_x + self.size.width)
        return strip

    def _render_wrapped_line(self, *, y: int, scroll_y: int) -> Strip:
        """Render a line in wrap mode."""
        row_index = y + scroll_y

        if row_index < 0 or row_index >= len(self._wrapped_lines):
            return self._blank_strip()

        entry_idx, sub_line = self._wrapped_lines[row_index]
        width = self._get_content_width()

        if entry_idx not in self._line_cache:
            log = self._log_entries[entry_idx]
            self._line_cache[entry_idx] = json.dumps(
                log.data, ensure_ascii=False
            )
        text = self._line_cache[entry_idx]

        wrapped = _wrap_text(text=text, width=width)
        if sub_line >= len(wrapped):
            return self._blank_strip()

        line_text = wrapped[sub_line]
        is_highlighted = entry_idx == self._cursor_index
        if is_highlighted:
            style = self.get_component_rich_style("loglist--cursor")
        else:
            style = self._style_for_entry(
                entry_idx=entry_idx, base=self.rich_style or Style()
            )

        padded = line_text.ljust(width)
        segments = [Segment(padded, style)]
        return Strip(segments, width)

    def _get_cursor_row(self) -> int:
        """Get the current virtual row of the cursor."""
        if not self._wrap_mode:
            return self._cursor_index
        return self._entry_start_rows.get(self._cursor_index, 0)

    def _on_filtered_logs_changed(self, filtered_logs: list[LogEntry]) -> None:
        """Update log entries when filtered_logs changes."""
        self.set_logs(logs=filtered_logs)
        if self._app:
            idx = self._app.selected_index
            if idx < len(self._log_entries):
                self._cursor_index = idx
            self._pending_scroll = True
            self.refresh()
            self.call_after_refresh(self._apply_pending_scroll)

    def _apply_pending_scroll(self) -> None:
        if self._pending_scroll:
            self._pending_scroll = False
            self._scroll_cursor_into_view()

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
        if self._wrap_mode and not self._wrapped_lines:
            return

        cursor_row = self._get_cursor_row()
        visible_top = self.scroll_offset.y
        visible_bottom = visible_top + self.size.height - 1
        target_top = cursor_row - self.SCROLLOFF
        target_bottom = cursor_row + self.SCROLLOFF

        if target_top < visible_top:
            self.scroll_to(y=max(0, target_top), animate=False)
        elif target_bottom > visible_bottom:
            self.scroll_to(
                y=max(0, target_bottom - self.size.height + 1), animate=False
            )

    def action_cursor_down(self) -> None:
        if not self._log_entries:
            return

        if self._wrap_mode and self._wrapped_lines:
            cursor_row = self._get_cursor_row()
            for row in range(cursor_row + 1, len(self._wrapped_lines)):
                next_entry, _ = self._wrapped_lines[row]
                if next_entry != self._cursor_index:
                    self._cursor_index = next_entry
                    break
            else:
                self._cursor_index = len(self._log_entries) - 1
        else:
            if self._cursor_index < len(self._log_entries) - 1:
                self._cursor_index += 1

        if self._app:
            self._app.selected_index = self._cursor_index
        self._scroll_cursor_into_view()
        self.refresh()

    def action_cursor_up(self) -> None:
        if not self._log_entries:
            return

        if self._wrap_mode and self._wrapped_lines:
            cursor_row = self._get_cursor_row()
            for row in range(cursor_row - 1, -1, -1):
                prev_entry, _ = self._wrapped_lines[row]
                if prev_entry != self._cursor_index:
                    self._cursor_index = prev_entry
                    break
            else:
                self._cursor_index = 0
        else:
            if self._cursor_index > 0:
                self._cursor_index -= 1

        if self._app:
            self._app.selected_index = self._cursor_index
        self._scroll_cursor_into_view()
        self.refresh()

    def action_page_up(self) -> None:
        """Move cursor half a page up."""
        if not self._log_entries:
            return
        half_page = max(1, self.size.height // 2)
        self._cursor_index = max(0, self._cursor_index - half_page)
        if self._app:
            self._app.selected_index = self._cursor_index
        self._scroll_cursor_into_view()
        self.refresh()

    def action_page_down(self) -> None:
        """Move cursor half a page down."""
        if not self._log_entries:
            return
        half_page = max(1, self.size.height // 2)
        last = len(self._log_entries) - 1
        self._cursor_index = min(last, self._cursor_index + half_page)
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
        if self._wrap_mode and self._wrapped_lines:
            self.scroll_to(y=len(self._wrapped_lines) - 1, animate=False)
        else:
            self.scroll_to(y=last, animate=False)
        self.refresh()

    def action_select_cursor(self) -> None:
        if 0 <= self._cursor_index < len(self._log_entries):
            log = self._log_entries[self._cursor_index]
            self.post_message(self.LogSelected(log_entry=log))

    def _jump_to_match(self, *, forward: bool) -> None:
        """Jump to the next/prev matching entry in highlight mode."""
        if not self._highlight_mode or not self._active_query:
            return
        if not self._log_entries:
            return

        count = len(self._log_entries)
        step = 1 if forward else -1
        for i in range(1, count):
            idx = (self._cursor_index + i * step) % count
            if idx < len(self._match_flags) and self._match_flags[idx]:
                self._cursor_index = idx
                if self._app:
                    self._app.selected_index = idx
                self._scroll_cursor_into_view()
                self.refresh()
                return

    def action_next_match(self) -> None:
        self._jump_to_match(forward=True)

    def action_prev_match(self) -> None:
        self._jump_to_match(forward=False)

    def action_scroll_left(self) -> None:
        if not self._wrap_mode:
            self.scroll_left()

    def action_scroll_right(self) -> None:
        if not self._wrap_mode:
            self.scroll_right()
