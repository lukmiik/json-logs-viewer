from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.content import Content
from textual.screen import ModalScreen
from textual.widgets import Label, OptionList
from textual.widgets.option_list import Option

if TYPE_CHECKING:
    from json_logs_viewer.app import LogViewerApp


class HistoryModal(ModalScreen[str | None]):
    """Modal screen for browsing and reusing previous search queries."""

    DEFAULT_CSS = """
    HistoryModal {
        align: center middle;
        background: $background 70%;
    }

    HistoryModal Vertical {
        background: $surface;
        width: 60%;
        height: auto;
        max-height: 80%;
        border: heavy $block-cursor-background;
        padding: 1 2;
    }

    HistoryModal OptionList {
        height: auto;
        max-height: 20;
    }

    HistoryModal #history-empty {
        text-align: center;
        color: $text-muted;
        padding: 1 0;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Close"),
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("up", "cursor_up", "Up", show=False),
    ]

    @property
    def _app(self) -> LogViewerApp:
        return cast("LogViewerApp", self.app)

    def compose(self) -> ComposeResult:
        history = list(reversed(self._app.search_history))
        with Vertical(id="history-dialog") as dialog:
            if history:
                # Content: plain text. A str prompt is parsed as markup, so
                # a query holding "[/api]" crashed the list (MarkupError).
                option_list = OptionList(
                    *[Option(Content(query)) for query in history],
                    id="history-list",
                )
                yield option_list
            else:
                yield Label("No search history", id="history-empty")
        dialog.border_title = "Search History"
        dialog.border_subtitle = "ENTER: select | ESC: cancel"

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        """Dismiss with the selected query when Enter is pressed."""
        option = event.option
        self.dismiss(str(option.prompt))

    def check_action(
        self, action: str, parameters: tuple[object, ...]
    ) -> bool | None:
        """Disable cursor actions when there is no list to move in."""
        if action in ("cursor_down", "cursor_up"):
            return bool(self.query("#history-list"))
        return True

    def action_cursor_down(self) -> None:
        option_list = self.query_one("#history-list", OptionList)
        option_list.action_cursor_down()

    def action_cursor_up(self) -> None:
        option_list = self.query_one("#history-list", OptionList)
        option_list.action_cursor_up()

    def action_cancel(self) -> None:
        self.dismiss(None)
