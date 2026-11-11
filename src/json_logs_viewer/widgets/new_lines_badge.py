from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual.reactive import reactive
from textual.widgets import Label

if TYPE_CHECKING:
    from textual.events import Click

    from json_logs_viewer.app import LogViewerApp


class NewLinesBadge(Label):
    """Badge "↓ N new lines" at the list's bottom-right, while following.

    Shown when lines arrive below a cursor that isn't on the last line, so
    reading older lines isn't interrupted but nothing arrives unnoticed.
    It sits on its own layer (see styles.tcss), so the list doesn't move.
    Clicking it jumps to the end.
    """

    count: reactive[int] = reactive(0)

    def on_mount(self) -> None:
        self.display = False

    def watch_count(self, count: int) -> None:
        self.display = count > 0
        noun = "line" if count == 1 else "lines"
        self.update(f"↓ {count} new {noun}")

    def on_click(self, event: Click) -> None:
        event.stop()
        cast("LogViewerApp", self.app).action_jump_to_end()
