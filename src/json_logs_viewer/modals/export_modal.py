from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label


class ExportModal(ModalScreen[Path | None]):
    """Ask where to export the matching logs; returns the path or None.

    The path is prefilled. An existing file is only replaced after a second
    Enter on the same path, so an earlier export isn't overwritten by
    accident; editing the path asks again.
    """

    DEFAULT_CSS = """
    ExportModal {
        align: center middle;
        background: $background 70%;
    }

    ExportModal Vertical {
        background: $surface;
        width: 70%;
        height: auto;
        border: heavy $block-cursor-background;
        padding: 1 2;
    }

    ExportModal #export-warning {
        color: $text-warning;
        margin-top: 1;
    }
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, *, default_path: Path, count: int) -> None:
        super().__init__()
        self._default_path = default_path
        self._count = count
        # The existing file the user was warned about; Enter on it again
        # confirms the overwrite.
        self._confirmed: Path | None = None

    def compose(self) -> ComposeResult:
        noun = "line" if self._count == 1 else "lines"
        with Vertical(id="export-dialog") as dialog:
            yield Label(f"Export {self._count} matching {noun} to:")
            yield Input(
                str(self._default_path),
                id="export-path",
                select_on_focus=False,
            )
            yield Label("", id="export-warning")
        dialog.border_title = "Export"
        dialog.border_subtitle = "ENTER: export | ESC: cancel"

    def on_mount(self) -> None:
        path_input = self.query_one("#export-path", Input)
        path_input.focus()
        path_input.cursor_position = len(path_input.value)

    def _warn(self, text: str) -> None:
        self.query_one("#export-warning", Label).update(text)

    def on_input_changed(self, _: Input.Changed) -> None:
        self._confirmed = None
        self._warn("")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            self._warn("Enter a file name.")
            return
        path = Path(text).expanduser()
        if path.is_dir():
            self._warn(f"{path} is a directory. Add a file name.")
            return
        if path.exists() and path != self._confirmed:
            self._confirmed = path
            self._warn(
                f"{path.name} already exists. Enter again to replace it."
            )
            return
        self.dismiss(path)

    def action_cancel(self) -> None:
        self.dismiss(None)
