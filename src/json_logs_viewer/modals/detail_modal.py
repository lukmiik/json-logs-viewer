from __future__ import annotations

import json
from bisect import bisect_left
from typing import TYPE_CHECKING, cast

from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.content import Content
from textual.screen import ModalScreen
from textual.widgets import Footer, TextArea
from textual.widgets.text_area import Selection

from json_logs_viewer.clipboard import (
    format_log_as_json,
    format_logs_as_jsonl,
    get_log_with_context,
)
from json_logs_viewer.constants import COPY_CONTEXT_SIZE
from json_logs_viewer.models import LogEntry
from json_logs_viewer.selection_copier import SelectionCopier

if TYPE_CHECKING:
    from textual.app import ComposeResult

    from json_logs_viewer.app import LogViewerApp


def _seq(entry: LogEntry) -> int:
    return entry.seq


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
        Binding("ctrl+d", "scroll_down", "Page Down", show=True),
        Binding("ctrl+u", "scroll_up", "Page Up", show=True),
        Binding("g", "scroll_top", "Top", show=False),
        Binding("G", "scroll_bottom", "Bottom", show=False),
    ]

    def __init__(
        self,
        *,
        log_entry: LogEntry,
    ) -> None:
        super().__init__()
        self.log_entry = log_entry
        self._selection_copier = SelectionCopier(
            owner=self, clear_selection=self._clear_selection
        )

    @property
    def _app(self) -> LogViewerApp:
        return cast("LogViewerApp", self.app)

    def _position(self) -> tuple[int, bool]:
        """Where the shown entry is in the list, and whether it's there.

        Not the app's cursor: follow mode moves that to new lines while
        this is open. The list is sorted by seq, so a binary search finds
        the entry, or where it was if a filter has since dropped it.
        """
        logs = self.logs
        pos = bisect_left(logs, self.log_entry.seq, key=_seq)
        return pos, pos < len(logs) and logs[pos] is self.log_entry

    @property
    def current_index(self) -> int:
        pos, _ = self._position()
        return min(pos, len(self.logs) - 1)

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
            yield TextArea(
                json_str, id="json-content", read_only=True, language="json"
            )
            yield Footer()
        dialog.border_title = Content(self._title())
        dialog.border_subtitle = "j/k: nav | ctrl+d/u: scroll | ESC: close"

    def _show(self, index: int) -> None:
        if 0 <= index < len(self.logs):
            self.current_index = index  # the list's cursor follows
            self.log_entry = self.logs[index]
            self._update_content()

    def action_next_log(self) -> None:
        pos, found = self._position()
        self._show(pos + 1 if found else pos)

    def action_previous_log(self) -> None:
        pos, _ = self._position()
        self._show(pos - 1)

    def _title(self) -> str:
        """Log Detail · <file>:<line>, so merged files stay traceable."""
        entry = self.log_entry
        if not entry.source:
            return "Log Detail"
        source = self._app.source_label(entry.source)
        return f"Log Detail · {source}:{entry.line_number}"

    def _update_content(self) -> None:
        self.query_one("#detail-dialog").border_title = Content(self._title())
        json_widget = self.query_one("#json-content", TextArea)
        json_str = json.dumps(
            self.log_entry.data, indent=2, ensure_ascii=False
        )
        json_widget.text = json_str

    def on_text_area_selection_changed(
        self, event: TextArea.SelectionChanged
    ) -> None:
        self._selection_copier.update(
            selected_text=event.text_area.selected_text
        )

    def _clear_selection(self) -> None:
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

    def action_scroll_down(self) -> None:
        self.query_one("#json-content", TextArea).action_page_down()

    def action_scroll_up(self) -> None:
        self.query_one("#json-content", TextArea).action_page_up()

    def action_scroll_top(self) -> None:
        self.query_one("#json-content", TextArea).action_scroll_home()

    def action_scroll_bottom(self) -> None:
        self.query_one("#json-content", TextArea).action_scroll_end()
