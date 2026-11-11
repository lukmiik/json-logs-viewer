from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label


class ConfirmModal(ModalScreen[bool]):
    """Ask a yes/no question: y or Enter returns True, n or Esc False."""

    DEFAULT_CSS = """
    ConfirmModal {
        align: center middle;
        background: $background 70%;
    }

    ConfirmModal Vertical {
        background: $surface;
        width: auto;
        max-width: 70%;
        height: auto;
        border: heavy $block-cursor-background;
        padding: 1 2;
    }
    """

    BINDINGS = [
        ("y", "answer(True)", "Yes"),
        ("enter", "answer(True)", "Yes"),
        ("n", "answer(False)", "No"),
        ("escape", "answer(False)", "No"),
    ]

    def __init__(self, *, title: str, question: str) -> None:
        super().__init__()
        self._title = title
        self._question = question

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-dialog") as dialog:
            yield Label(self._question)
        dialog.border_title = self._title
        dialog.border_subtitle = "y/ENTER: yes | n/ESC: no"

    def action_answer(self, answer: bool) -> None:
        self.dismiss(answer)
