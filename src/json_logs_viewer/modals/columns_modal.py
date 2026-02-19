from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.events import Key
from textual.screen import ModalScreen
from textual.widgets import SelectionList
from textual.widgets.selection_list import Selection

if TYPE_CHECKING:
    from json_logs_viewer.app import LogViewerApp


class ColumnsModal(ModalScreen[list[str] | None]):
    """Modal screen for selecting which fields to display as columns."""

    DEFAULT_CSS = """
    ColumnsModal {
        align: center middle;
        background: $background 70%;
    }

    ColumnsModal Vertical {
        background: $surface;
        width: 50%;
        height: auto;
        max-height: 80%;
        border: heavy $block-cursor-background;
        padding: 1 2;
    }

    ColumnsModal SelectionList {
        height: auto;
        max-height: 15;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Close"),
        ("r", "reset", "Reset"),
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("up", "cursor_up", "Up", show=False),
        Binding("space", "toggle_selection", "Toggle", show=False),
    ]

    @property
    def _app(self) -> LogViewerApp:
        return cast("LogViewerApp", self.app)

    def compose(self) -> ComposeResult:
        available = self._app.discover_fields()
        current = self._app.columns

        selections = [
            Selection(field, field, initial_state=(field in current))
            for field in available
        ]

        with Vertical(id="columns-dialog") as dialog:
            yield SelectionList(*selections, id="column-list")

        dialog.border_title = "Configure Columns"
        dialog.border_subtitle = (
            "SPACE: toggle | ENTER: apply | r: reset | ESC: cancel"
        )

    def on_key(self, event: Key) -> None:
        if event.key == "enter":
            event.stop()
            self.action_apply()

    def action_toggle_selection(self) -> None:
        selection_list = self.query_one("#column-list", SelectionList)
        selection_list.action_select()

    def action_apply(self) -> None:
        selection_list = self.query_one("#column-list", SelectionList)
        selected = list(selection_list.selected)
        self.dismiss(selected)

    def action_reset(self) -> None:
        self.dismiss([])

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_cursor_down(self) -> None:
        selection_list = self.query_one("#column-list", SelectionList)
        selection_list.action_cursor_down()

    def action_cursor_up(self) -> None:
        selection_list = self.query_one("#column-list", SelectionList)
        selection_list.action_cursor_up()
