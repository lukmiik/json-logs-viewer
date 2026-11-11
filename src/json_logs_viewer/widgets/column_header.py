from __future__ import annotations

from typing import TYPE_CHECKING, cast

from rich.segment import Segment
from textual.strip import Strip
from textual.widget import Widget

from json_logs_viewer.widgets.log_list import LogList

if TYPE_CHECKING:
    from json_logs_viewer.app import LogViewerApp


class ColumnHeader(Widget):
    """Column names above the log list, shown only while columns are set.

    A separate one-line widget rather than a row inside LogList, so the
    list's scrolling and click maths stay unchanged. It takes its text and
    horizontal scroll from the list so the names line up with the values.
    """

    DEFAULT_CSS = """
    ColumnHeader {
        height: 1;
        padding: 0 0 0 1;
        color: $text-muted;
        text-style: bold;
    }
    """

    def on_mount(self) -> None:
        app = cast("LogViewerApp", self.app)
        self._log_list = app.query_one("#logs", LogList)
        self.watch(app, "columns", self._on_columns_changed)
        self.watch(self._log_list, "scroll_x", self._on_scroll_x_changed)
        # Column widths follow the lines shown, so redraw when they change.
        self.watch(app, "filtered_logs", self._on_scroll_x_changed)

    def _on_columns_changed(self, columns: list[str]) -> None:
        self.display = bool(columns)
        self.refresh()

    def _on_scroll_x_changed(self, _: float) -> None:
        self.refresh()

    def render_line(self, y: int) -> Strip:
        width = self.size.width
        if y != 0 or width <= 0:
            return Strip.blank(width, self.rich_style)
        scroll_x = int(self._log_list.scroll_offset.x)
        text = self._log_list.header_text()
        visible = text[scroll_x : scroll_x + width].ljust(width)
        return Strip([Segment(visible, self.rich_style)], width)
