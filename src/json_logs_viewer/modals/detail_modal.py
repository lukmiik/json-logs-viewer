from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.timer import Timer
from textual.widgets import Footer, TextArea
from textual.widgets.text_area import Selection

from json_logs_viewer.clipboard import (
    format_log_as_json,
    format_logs_as_jsonl,
    get_log_with_context,
)
from json_logs_viewer.constants import COPY_CONTEXT_SIZE
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
        padding: 0;
        scrollbar-size: 1 1;
    }

    DetailModal #json-content {
        height: 1fr;
        width: 100%;
        border: none;
        background: transparent;
        scrollbar-size-vertical: 1;
        scrollbar-size-horizontal: 1;
    }

    DetailModal #json-content:focus {
        border: none;
    }
    """

    BINDINGS = [
        Binding("j", "next_log", "Next", show=True),
        Binding("k", "previous_log", "Previous", show=True),
        Binding("down", "next_log", "Next", show=False),
        Binding("up", "previous_log", "Previous", show=False),
        Binding("escape,q", "dismiss", "Close", show=True),
        Binding("y", "copy_log", "Copy", show=True),
        Binding("Y", "copy_log_with_context", "Copy+", show=True),
    ]

    def __init__(
        self,
        *,
        log_entry: LogEntry,
    ) -> None:
        super().__init__()
        self.log_entry = log_entry
        self._selection_timer: Timer | None = None
        self._last_selected_text: str = ""

    @property
    def _app(self) -> LogViewerApp:
        return cast("LogViewerApp", self.app)

    @property
    def current_index(self) -> int:
        return self._app.selected_index

    @current_index.setter
    def current_index(self, value: int) -> None:
        self._app.selected_index = value

    @property
    def logs(self) -> list[LogEntry]:
        return self._app.filtered_logs

    def compose(self) -> ComposeResult:
        json_str = json.dumps(
            self.log_entry.data, indent=2, ensure_ascii=False
        )

        with VerticalScroll(id="detail-dialog") as dialog:
            yield TextArea(json_str, id="json-content", read_only=True)
            yield Footer()
        dialog.border_title = "Log Detail"
        dialog.border_subtitle = "j/k: navigate | ESC: close"

    def action_next_log(self) -> None:
        if self.current_index < len(self.logs) - 1:
            self.current_index += 1
            self.log_entry = self.logs[self.current_index]
            self._update_content()

    def action_previous_log(self) -> None:
        if self.current_index > 0:
            self.current_index -= 1
            self.log_entry = self.logs[self.current_index]
            self._update_content()

    def _update_content(self) -> None:
        json_widget = self.query_one("#json-content", TextArea)
        json_str = json.dumps(
            self.log_entry.data, indent=2, ensure_ascii=False
        )
        json_widget.text = json_str

    def on_text_area_selection_changed(
        self, event: TextArea.SelectionChanged
    ) -> None:
        if event.text_area.id == "json-content":
            selected_text = event.text_area.selected_text
            if selected_text and selected_text != self._last_selected_text:
                self._last_selected_text = selected_text
                if self._selection_timer is not None:
                    self._selection_timer.stop()
                self._selection_timer = self.set_timer(
                    0.5, self._copy_selection_to_clipboard
                )

    def _copy_selection_to_clipboard(self) -> None:
        self._selection_timer = None
        if self._last_selected_text:
            self.app.copy_to_clipboard(self._last_selected_text)
            self.notify("Copied selection to clipboard")
            self._last_selected_text = ""
            ta = self.query_one("#json-content", TextArea)
            ta.selection = Selection.cursor(ta.cursor_location)

    def action_copy_log(self) -> None:
        """Copy the current log entry to clipboard."""
        text = format_log_as_json(log_entry=self.log_entry)
        self.app.copy_to_clipboard(text)
        self.notify("Copied log to clipboard")

    def action_copy_log_with_context(self) -> None:
        """Copy the current log entry with surrounding context to clipboard."""
        context_logs = get_log_with_context(
            logs=self.logs,
            current_index=self.current_index,
            context_size=COPY_CONTEXT_SIZE,
        )
        text = format_logs_as_jsonl(log_entries=context_logs)
        self.app.copy_to_clipboard(text)
        count = len(context_logs)
        self.notify(f"Copied {count} logs to clipboard")
