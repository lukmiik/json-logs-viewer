from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

from rich.json import JSON
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Footer, Static

from json_logs_viewer.models import LogEntry

if TYPE_CHECKING:
    from textual.app import ComposeResult

    from json_logs_viewer.app import LogViewerApp


class DetailModal(ModalScreen[None]):
    """Modal screen for viewing detailed log entry JSON."""

    CSS = """
    DetailModal {
        align: center middle;
        background: $background 70%;
    }

    DetailModal VerticalScroll {
        background: $surface;
        width: 80%;
        height: 80%;
        border: heavy $block-cursor-background;
        padding: 1 2;
    }

    DetailModal #json-content {
        height: 1fr;
        width: 100%;
        overflow: auto;
    }
    """

    BINDINGS = [
        Binding("j", "next_log", "Next", show=True),
        Binding("k", "previous_log", "Previous", show=True),
        Binding("down", "next_log", "Next", show=False),
        Binding("up", "previous_log", "Previous", show=False),
        Binding("escape,q", "dismiss", "Close", show=True),
        Binding("y", "copy_log", "Copy", show=True),
    ]

    def __init__(
        self,
        *,
        log_entry: LogEntry,
        current_index: int,
        logs: list[LogEntry],
    ) -> None:
        super().__init__()
        self.log_entry = log_entry
        self.current_index = current_index
        self.logs = logs

    @property
    def _app(self) -> LogViewerApp:
        return cast("LogViewerApp", self.app)

    def compose(self) -> ComposeResult:
        json_str = json.dumps(
            self.log_entry.data, indent=2, ensure_ascii=False
        )

        with VerticalScroll(id="detail-dialog") as dialog:
            yield Static(JSON(json_str), id="json-content")
            yield Footer()
        dialog.border_title = "Log Detail"
        dialog.border_subtitle = "j/k: navigate | ESC: close"

    def action_next_log(self) -> None:
        if self.current_index < len(self.logs) - 1:
            self.current_index += 1
            self.log_entry = self.logs[self.current_index]
            self._app.selected_index = self.current_index
            self._update_content()

    def action_previous_log(self) -> None:
        if self.current_index > 0:
            self.current_index -= 1
            self.log_entry = self.logs[self.current_index]
            self._app.selected_index = self.current_index
            self._update_content()

    def _update_content(self) -> None:
        json_widget = self.query_one("#json-content", Static)
        json_str = json.dumps(
            self.log_entry.data, indent=2, ensure_ascii=False
        )
        json_widget.update(JSON(json_str))

    def action_copy_log(self) -> None:
        self.notify("Copy feature coming in Phase 8", severity="information")
