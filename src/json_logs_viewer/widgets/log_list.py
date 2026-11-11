from __future__ import annotations

import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

from rich.console import Console
from rich.segment import Segment
from rich.style import Style
from rich.text import Text
from textual.binding import Binding
from textual.cache import LRUCache
from textual.events import Click
from textual.geometry import Size
from textual.message import Message
from textual.scroll_view import ScrollView
from textual.strip import Strip

from json_logs_viewer.clipboard import (
    format_log_as_json,
    format_logs_as_jsonl,
    get_log_with_context,
)
from json_logs_viewer.constants import (
    COLUMN_SEPARATOR,
    COPY_CONTEXT_SIZE,
    MAX_COL_WIDTH,
)
from json_logs_viewer.field_paths import resolve_field
from json_logs_viewer.filter_engine import FilterError, parse_filter
from json_logs_viewer.models import (
    LogEntry,
    appended_entries,
    level_category,
)

if TYPE_CHECKING:
    from json_logs_viewer.app import LogViewerApp

_console = Console()


def _fast_wrap(*, text: str, width: int) -> list[str] | None:
    """Word-wrap simple ASCII text exactly like Rich, or return None.

    Wrap mode wraps every entry to count rows, and Rich's general wrapper
    costs ~1.7 s per 100k lines. For ASCII text with single spaces this
    greedy rfind loop produces identical lines (checked against Rich by
    fuzzing) far faster, and compact JSON (no spaces) is folded into
    width-sized chunks as Rich does. Anything else (non-ASCII widths, tabs,
    runs of spaces, leading/trailing spaces, a long word among spaced text)
    returns None so the caller falls back to Rich.
    """
    if (
        not text.isascii()
        or "  " in text
        or text[:1] == " "
        or text[-1:] == " "
        or "\t" in text
        or "\r" in text
        or "\n" in text
        or "\x0b" in text
        or "\x0c" in text
    ):
        return None
    if " " not in text:
        # Compact JSON: one long "word", which Rich folds into width chunks.
        return [text[i : i + width] for i in range(0, len(text), width)] or [
            ""
        ]
    lines: list[str] = []
    pos = 0
    length = len(text)
    while length - pos > width:
        cut = text.rfind(" ", pos, pos + width + 1)
        if cut <= pos:
            return None  # a word longer than the width: Rich hard-breaks
        # Rich keeps the breaking space on the line when it still fits.
        end = cut + 1 if cut + 1 - pos <= width else cut
        lines.append(text[pos:end])
        pos = cut + 1
    lines.append(text[pos:])
    return lines


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

    fast = _fast_wrap(text=text, width=width)
    if fast is not None:
        return fast
    rich_text = Text(text)
    wrapped = rich_text.wrap(_console, width=width)
    return [line.plain for line in wrapped]


_MISSING = object()


def column_text(*, data: dict[str, Any], column: str) -> str:
    """Text shown in a column: a (dotted) field's value, or "" if absent.

    Strings are shown as they are; anything else as JSON (null, true,
    [1, 2]), matching the line next to it rather than Python's repr.
    """
    if column in data:
        value = data[column]
    elif "." in column:
        value = next(resolve_field(value=data, path=column), _MISSING)
    else:
        value = _MISSING
    if value is _MISSING:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


class LogList(ScrollView):
    """Virtual-scrolling log list using Textual's Line API."""

    can_focus = True

    SCROLLOFF: int = 3

    COMPONENT_CLASSES = {
        "loglist--cursor",
        "loglist--level-error",
        "loglist--level-warning",
        "loglist--level-debug",
    }

    # Level colours come from the theme, so they follow theme changes.
    DEFAULT_CSS = """
    LogList .loglist--cursor {
        background: $block-cursor-background;
    }
    LogList .loglist--level-error {
        color: $text-error;
    }
    LogList .loglist--level-warning {
        color: $text-warning;
    }
    LogList .loglist--level-debug {
        color: $text-muted;
    }
    """

    BINDINGS = [
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("up", "cursor_up", "Up", show=False),
        ("h", "scroll_left", "Left"),
        ("l", "scroll_right", "Right"),
        Binding("0", "scroll_line_start", "Line Start", show=False),
        Binding("$", "scroll_line_end", "Line End", show=False),
        Binding("ctrl+u", "page_up", "Half Up"),
        Binding("ctrl+d", "page_down", "Half Down"),
        Binding("n", "next_match", "Next Match", show=False),
        Binding("N", "prev_match", "Prev Match", show=False),
        ("g", "scroll_top", "Top"),
        ("G", "scroll_bottom", "Bottom"),
        ("enter", "select_cursor", "Details"),
        ("/", "app.focus_search", "Search"),
        ("w", "app.toggle_wrap", "Wrap"),
        ("y", "copy_log", "Copy"),
        ("Y", "copy_log_with_context", "Copy+"),
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
        self._wrap_mode: bool = False
        self._wrapped_lines: list[tuple[int, int]] = []
        self._entry_start_rows: dict[int, int] = {}
        self._match_flags: list[bool] = []
        # How _match_flags were computed, so appended entries get the same
        # treatment: a matcher, or one flag for all (no matcher).
        self._flag_matcher: Callable[[LogEntry], bool] | None = None
        self._flag_default: bool = True
        # Width the wrapped rows were computed for, or None when a new
        # entry could change it (see _recalculate_wrap).
        self._wrap_content_width: int | None = None
        self._wrap_widget_width: int = 0
        self._highlight_mode: bool = False
        self._active_query: str = ""
        self._column_widths: dict[str, int] = {}

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
            self.watch(self.app, "columns", self._on_columns_changed)
            self._recompute_match_flags()
            self.watch(self, "scroll_y", self._on_scroll_y_changed)

    def on_resize(self) -> None:
        """Apply pending scroll when the widget gets its size."""
        self._apply_pending_scroll()
        if self._wrap_mode:
            self._recalculate_wrap()
        self._update_max_width_for_visible_range()
        self._update_virtual_size()
        # A shorter list (column header shown, terminal resized) can hide
        # the cursor or eat its margin; keep it in view like a cursor move.
        self._scroll_cursor_into_view()

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

    def _calculate_column_widths(self) -> dict[str, int]:
        """Calculate column widths from all rows, with early termination.

        Stops scanning once every column has reached MAX_COL_WIDTH.
        """
        columns = self._app.columns
        if not columns:
            return {}

        widths = {col: len(col) for col in columns}
        unsettled = {col for col in columns if widths[col] < MAX_COL_WIDTH}

        for log in self._log_entries:
            if not unsettled:
                break
            for col in list(unsettled):
                value = column_text(data=log.data, column=col)
                widths[col] = max(widths[col], min(len(value), MAX_COL_WIDTH))
                if widths[col] >= MAX_COL_WIDTH:
                    unsettled.discard(col)

        return widths

    def header_text(self) -> str:
        """Column names laid out like the column prefix of every row."""
        columns = self._app.columns
        if not columns:
            return ""
        if not self._column_widths:
            self._column_widths = self._calculate_column_widths()
        widths = self._column_widths
        names = [col.ljust(widths.get(col, len(col))) for col in columns]
        return COLUMN_SEPARATOR.join(names) + COLUMN_SEPARATOR

    def _on_columns_changed(self, _: list[str]) -> None:
        """Handle column configuration changes."""
        self._line_cache.clear()
        self._column_widths = self._calculate_column_widths()
        if self._wrap_mode:
            self._recalculate_wrap()
        self._update_virtual_size()
        # Columns are drawn at the start of each line: if the view was
        # scrolled right, the new columns would be off-screen to the left.
        self.scroll_to(x=0, animate=False)
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
        self._wrap_content_width = None

        width = self.size.width
        if width <= 0:
            return

        columns = self._app.columns
        column_width = 0
        if columns:
            col_widths = self._calculate_column_widths()
            column_width = sum(col_widths.values()) + len(
                COLUMN_SEPARATOR
            ) * len(columns)

        def needs_scrollbar(*, content_width: int) -> bool:
            # Only "more rows than fit?" matters, so stop counting as soon
            # as the screen is full instead of wrapping every entry twice.
            total = 0
            for log in self._log_entries:
                wrapped = _wrap_text(text=log.raw_json, width=content_width)
                total += len(wrapped)
                if total > self.size.height:
                    return True
            return False

        json_content_width = max(1, width - column_width)
        has_scrollbar = needs_scrollbar(content_width=json_content_width)
        content_width = width - 1 if has_scrollbar else width
        json_content_width = max(1, content_width - column_width)

        self._wrap_entries(start=0, width=json_content_width)
        # Appending can only keep a scrollbar, so rows stay valid for new
        # entries. Without one, or with columns (their widths depend on
        # every entry), an append may change the width: wrap from scratch.
        if has_scrollbar and not columns:
            self._wrap_content_width = json_content_width
            self._wrap_widget_width = width

    def _wrap_entries(self, *, start: int, width: int) -> None:
        """Append the wrapped rows of the entries from `start` on."""
        current_row = len(self._wrapped_lines)
        for entry_idx in range(start, len(self._log_entries)):
            self._entry_start_rows[entry_idx] = current_row
            text = self._log_entries[entry_idx].raw_json
            row_count = len(_wrap_text(text=text, width=width))
            self._wrapped_lines.extend(
                (entry_idx, sub_line) for sub_line in range(row_count)
            )
            current_row += row_count

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

        # len() of a str is O(1) (the length is stored in the object), so
        # widths are read directly instead of cached per entry.
        self._max_content_width = max(
            len(log.raw_json) for log in self._log_entries[start_idx:end_idx]
        )

    def set_logs(self, *, logs: list[LogEntry]) -> None:
        """Update the log entries and recalculate virtual size."""
        # Follow mode appends: then only the new tail needs match flags and
        # wrapped rows, instead of a pass over every entry per batch.
        old_count = len(self._log_entries)
        appended = appended_entries(old=self._log_entries, new=logs)
        self._log_entries = logs
        self._line_cache = LRUCache(maxsize=2000)
        if appended is None:
            self._recompute_match_flags()
        else:
            self._match_flags.extend(self._flags_for(entries=appended))
        self._update_max_width_for_visible_range()

        if self._wrap_mode:
            if (
                appended is not None
                and self._wrap_content_width is not None
                and self._wrap_widget_width == self.size.width
            ):
                self._wrap_entries(
                    start=old_count, width=self._wrap_content_width
                )
            else:
                self._recalculate_wrap()

        self._update_virtual_size()

        if self._cursor_index >= len(logs):
            self._cursor_index = max(0, len(logs) - 1)

        self.refresh()

    def _on_filter_settings_changed(self, *_: object) -> None:
        self._recompute_match_flags()
        self.refresh()

    def _recompute_match_flags(self) -> None:
        self._flag_matcher = None
        self._flag_default = True
        if not self.app:
            self._highlight_mode = False
            self._active_query = ""
        else:
            app = self._app
            self._highlight_mode = app.highlight_matches
            self._active_query = app.filter_query.strip()
            if self._highlight_mode and self._active_query:
                try:
                    self._flag_matcher = parse_filter(
                        query=self._active_query,
                        case_sensitive=app.case_sensitive,
                    )
                except FilterError:
                    self._flag_default = False
        self._match_flags = self._flags_for(entries=self._log_entries)

    def _flags_for(self, *, entries: list[LogEntry]) -> list[bool]:
        if self._flag_matcher is None:
            return [self._flag_default] * len(entries)
        return [self._flag_matcher(log_entry) for log_entry in entries]

    def _style_for_entry(self, *, entry_idx: int, base: Style) -> Style:
        """Style of a non-cursor row: level colour, then highlight mode."""
        category = level_category(level=self._log_entries[entry_idx].level)
        if category is not None:
            # Not partial: a full style blends translucent theme colours
            # ($text-muted is white at 60%) with the background. A partial
            # style drops the alpha, which turned muted text bright white.
            base = base + self.get_component_rich_style(
                f"loglist--level-{category}"
            )

        if not self._highlight_mode or not self._active_query:
            return base

        if entry_idx >= len(self._match_flags):
            return base

        if self._match_flags[entry_idx]:
            return base + Style(bold=True)

        return base + Style(dim=True)

    def _update_virtual_size(self) -> None:
        """Set virtual_size based on number of log entries."""
        columns = self._app.columns
        column_width = 0
        if columns:
            if not self._column_widths:
                self._column_widths = self._calculate_column_widths()
            column_width = sum(self._column_widths.values()) + len(
                COLUMN_SEPARATOR
            ) * len(columns)

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
            width = self._max_content_width + column_width + 2
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
            self._line_cache[line_index] = log.raw_json
        raw_json = self._line_cache[line_index]

        columns = self._app.columns
        if columns:
            if not self._column_widths:
                self._column_widths = self._calculate_column_widths()
            column_parts = []
            for col in columns:
                value = column_text(
                    data=self._log_entries[line_index].data, column=col
                )
                width = self._column_widths.get(col, len(col))
                truncated = value[:width]
                column_parts.append(truncated.ljust(width))
            text = (
                COLUMN_SEPARATOR.join(column_parts)
                + COLUMN_SEPARATOR
                + raw_json
            )
        else:
            text = raw_json

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
            self._line_cache[entry_idx] = log.raw_json
        text = self._line_cache[entry_idx]

        columns = self._app.columns
        column_prefix = ""
        column_width = 0
        if columns:
            if not self._column_widths:
                self._column_widths = self._calculate_column_widths()
            if sub_line == 0:
                column_parts = []
                for col in columns:
                    value = column_text(
                        data=self._log_entries[entry_idx].data, column=col
                    )
                    col_w = self._column_widths.get(col, len(col))
                    truncated = value[:col_w]
                    column_parts.append(truncated.ljust(col_w))
                column_prefix = (
                    COLUMN_SEPARATOR.join(column_parts) + COLUMN_SEPARATOR
                )
                column_width = len(column_prefix)
            else:
                column_width = sum(self._column_widths.values()) + len(
                    COLUMN_SEPARATOR
                ) * len(columns)
                column_prefix = " " * column_width

        json_content_width = max(1, width - column_width)
        wrapped = _wrap_text(text=text, width=json_content_width)
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

        full_line = column_prefix + line_text
        padded = full_line.ljust(width)
        segments = [Segment(padded, style)]
        return Strip(segments, width)

    def _get_cursor_row(self) -> int:
        """Get the current virtual row of the cursor."""
        if not self._wrap_mode:
            return self._cursor_index
        return self._entry_start_rows.get(self._cursor_index, 0)

    @property
    def _is_at_bottom(self) -> bool:
        """Check if scroll position is at or near the bottom."""
        if not self._log_entries:
            return True
        return self.scroll_offset.y >= self.max_scroll_y - 1

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

        # force=True: Textual ignores a vertical scroll while the widget has
        # no vertical scrollbar, and the scrollbar only appears on the next
        # layout pass. When the content has just grown past the screen
        # (turning wrap on), the scroll would be silently dropped.
        if target_top < visible_top:
            self.scroll_to(y=max(0, target_top), animate=False, force=True)
        elif target_bottom > visible_bottom:
            self.scroll_to(
                y=max(0, target_bottom - self.size.height + 1),
                animate=False,
                force=True,
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

    def on_click(self, event: Click) -> None:
        """Select the log entry under the mouse click."""
        content_y = event.y - self.gutter.top
        row = int(content_y + self.scroll_offset.y)

        if self._wrap_mode and self._wrapped_lines:
            if 0 <= row < len(self._wrapped_lines):
                entry_idx, _ = self._wrapped_lines[row]
            else:
                return
        else:
            entry_idx = row

        if 0 <= entry_idx < len(self._log_entries):
            self._cursor_index = entry_idx
            if self._app:
                self._app.selected_index = entry_idx
            self._scroll_cursor_into_view()
            self.refresh()

            if event.chain == 2:
                self.post_message(
                    self.LogSelected(log_entry=self._log_entries[entry_idx])
                )

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

    def action_scroll_line_start(self) -> None:
        if not self._wrap_mode:
            self.scroll_to(x=0, animate=False)

    def action_scroll_line_end(self) -> None:
        if not self._wrap_mode:
            self.scroll_to(x=self.max_scroll_x, animate=False)

    def action_copy_log(self) -> None:
        """Copy the currently selected log entry to clipboard."""
        if not self._log_entries:
            return
        if not (0 <= self._cursor_index < len(self._log_entries)):
            return

        log_entry = self._log_entries[self._cursor_index]
        text = format_log_as_json(log_entry=log_entry)
        self.app.copy_to_clipboard(text)
        self.notify("Copied log to clipboard")

    def action_copy_log_with_context(self) -> None:
        """Copy the current log entry with surrounding context to clipboard."""
        if not self._log_entries:
            return
        if not (0 <= self._cursor_index < len(self._log_entries)):
            return

        context_logs = get_log_with_context(
            logs=self._log_entries,
            current_index=self._cursor_index,
            context_size=COPY_CONTEXT_SIZE,
        )
        text = format_logs_as_jsonl(log_entries=context_logs)
        self.app.copy_to_clipboard(text)
        count = len(context_logs)
        self.notify(f"Copied {count} logs to clipboard")
