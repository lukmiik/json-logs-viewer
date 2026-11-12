from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.content import Content
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, Footer, Label

if TYPE_CHECKING:
    from json_logs_viewer.app import LogViewerApp  # noqa: F401


def _files_label(*, paths: list[str]) -> str:
    """The open file, or the first one and how many more."""
    if not paths:
        return "No file"
    more = len(paths) - 1
    if not more:
        return paths[0]
    return f"{paths[0]} +{more} file" + ("s" if more > 1 else "")


class StatusInfo(Horizontal):
    """Displays file info and log counts."""

    DEFAULT_CSS = """
    StatusInfo {
        height: 1;
        background: $surface;
        color: $text-muted;
        padding: 0 0 0 1;
    }
    #status-left {
        width: 1fr;
        height: 1;
    }
    #status-right {
        width: auto;
        height: 1;
    }
    #status-left Label {
        margin: 0 1 0 0;
    }
    /* When space runs out the file name shrinks (with an ellipsis) so the
       counts and the active query stay readable. */
    #status-filename {
        width: 1fr;
        text-wrap: nowrap;
        text-overflow: ellipsis;
    }
    #status-total, #status-filtered, #status-follow, #status-query {
        width: auto;
        text-wrap: nowrap;
    }
    #status-right Button {
        min-width: 4;
        width: auto;
        height: 1;
        margin: 0 0 0 1;
        padding: 0 1;
        background: $panel;
        color: $text;
        border: none;
    }
    #status-right Button.-active-toggle {
        background: $primary;
        color: $text;
    }
    """

    filename: reactive[str] = reactive("No file")
    total: reactive[int] = reactive(0)
    filtered: reactive[int] = reactive(0)
    case_sensitive: reactive[bool] = reactive(False)
    highlight_matches: reactive[bool] = reactive(False)
    follow_mode: reactive[bool] = reactive(False)
    # Not `query`: that would hide Widget.query().
    active_query: reactive[str] = reactive("")

    def compose(self) -> ComposeResult:
        with Horizontal(id="status-left"):
            yield Label(id="status-filename")
            yield Label(id="status-total")
            yield Label(id="status-filtered")
            yield Label(id="status-follow")
            yield Label(id="status-query")
        with Horizontal(id="status-right"):
            yield Button("Follow", id="status-follow-toggle")
            yield Button("Aa", id="status-case-sensitive")
            yield Button("Highlight", id="status-highlight-matches")
            yield Button("History", id="status-history")

    def _update_labels(self) -> None:
        filename_label = self.query_one("#status-filename", Label)
        # Content: plain text. File names and queries may hold "[/x]",
        # which a str would parse as markup (MarkupError).
        filename_label.update(Content(f"File: {self.filename}"))
        total_label = self.query_one("#status-total", Label)
        total_label.update(f"Total: {self.total}")
        filtered_label = self.query_one("#status-filtered", Label)
        filtered_label.update(f"Filtered: {self.filtered}")
        follow_label = self.query_one("#status-follow", Label)
        follow_label.update("⏺ FOLLOW" if self.follow_mode else "")
        query_label = self.query_one("#status-query", Label)
        if self.active_query:
            mode = "Highlight" if self.highlight_matches else "Filter"
            query_label.update(Content(f"{mode}: {self.active_query}"))
        else:
            query_label.update("")

    def watch_filename(self) -> None:
        if self.is_mounted:
            self._update_labels()

    def watch_total(self) -> None:
        if self.is_mounted:
            self._update_labels()

    def watch_filtered(self) -> None:
        if self.is_mounted:
            self._update_labels()

    def watch_case_sensitive(self) -> None:
        if self.is_mounted:
            self._update_toggles()

    def watch_highlight_matches(self) -> None:
        if self.is_mounted:
            self._update_labels()
            self._update_toggles()

    def watch_active_query(self) -> None:
        if self.is_mounted:
            self._update_labels()

    def watch_follow_mode(self) -> None:
        if self.is_mounted:
            self._update_labels()
            self._update_toggles()

    def on_mount(self) -> None:
        self._update_labels()
        self._update_toggles()

    def _set_toggle_active(self, *, button_id: str, active: bool) -> None:
        button = self.query_one(f"#{button_id}", Button)
        button.set_class(active, "-active-toggle")
        button.variant = "primary" if active else "default"

    def _update_toggles(self) -> None:
        self._set_toggle_active(
            button_id="status-case-sensitive", active=self.case_sensitive
        )
        self._set_toggle_active(
            button_id="status-highlight-matches",
            active=self.highlight_matches,
        )
        self._set_toggle_active(
            button_id="status-follow-toggle", active=self.follow_mode
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if not self.app:
            return

        app = cast("LogViewerApp", self.app)
        if event.button.id == "status-case-sensitive":
            app.case_sensitive = not app.case_sensitive
        elif event.button.id == "status-highlight-matches":
            app.highlight_matches = not app.highlight_matches
        elif event.button.id == "status-follow-toggle":
            app.action_toggle_follow()
        elif event.button.id == "status-history":
            app.action_show_history()


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
            self.watch(self.app, "filepaths", self._update_status)
            self.watch(self.app, "case_sensitive", self._update_status)
            self.watch(self.app, "highlight_matches", self._update_status)
            self.watch(self.app, "follow_mode", self._update_status)
            self.watch(self.app, "filter_query", self._update_status)

    def _update_status(self) -> None:
        if not self.app:
            return
        app = cast("LogViewerApp", self.app)
        info: StatusInfo = self.query_one(StatusInfo)
        info.filename = _files_label(
            paths=[app.source_label(path) for path in app.filepaths]
        )
        info.total = len(app.logs)
        info.filtered = len(app.filtered_logs)
        info.case_sensitive = app.case_sensitive
        info.highlight_matches = app.highlight_matches
        info.follow_mode = app.follow_mode
        info.active_query = app.filter_query.strip()
