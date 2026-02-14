from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Footer, Label

if TYPE_CHECKING:
    from json_logs_viewer.app import LogViewerApp  # noqa: F401


class StatusInfo(Horizontal):
    """Displays file info and log counts."""

    DEFAULT_CSS = """
    StatusInfo {
        height: 1;
        background: $surface;
        color: $text-muted;
        padding: 0 1;
    }
    StatusInfo Label {
        margin: 0 1 0 0;
    }
    """

    filename: reactive[str] = reactive("No file")
    total: reactive[int] = reactive(0)
    filtered: reactive[int] = reactive(0)

    def compose(self) -> ComposeResult:
        yield Label(id="status-filename")
        yield Label(id="status-total")
        yield Label(id="status-filtered")

    def _update_labels(self) -> None:
        filename_label = self.query_one("#status-filename", Label)
        filename_label.update(f"File: {self.filename}")
        total_label = self.query_one("#status-total", Label)
        total_label.update(f"Total: {self.total}")
        filtered_label = self.query_one("#status-filtered", Label)
        filtered_label.update(f"Filtered: {self.filtered}")

    def watch_filename(self) -> None:
        if self.is_mounted:
            self._update_labels()

    def watch_total(self) -> None:
        if self.is_mounted:
            self._update_labels()

    def watch_filtered(self) -> None:
        if self.is_mounted:
            self._update_labels()

    def on_mount(self) -> None:
        self._update_labels()


class StatusBar(Widget):
    """Status bar with file info, log counts, and key bindings."""

    DEFAULT_CSS = """
    StatusBar {
        height: auto;
        dock: bottom;
    }
    StatusBar Footer {
        dock: none;
        height: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield StatusInfo()
        yield Footer()

    def on_mount(self) -> None:
        """Set up watchers for app state changes."""
        if self.app:
            self.watch(self.app, "logs", self._update_status)
            self.watch(self.app, "filtered_logs", self._update_status)
            self.watch(self.app, "filepath", self._update_status)

    def _update_status(self) -> None:
        if not self.app:
            return
        app = cast("LogViewerApp", self.app)
        info: StatusInfo = self.query_one(StatusInfo)
        info.filename = app.filepath or "No file"
        info.total = len(app.logs)
        info.filtered = len(app.filtered_logs)
