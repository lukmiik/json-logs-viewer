from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.timer import Timer
from textual.widgets import TextArea
from textual.widgets.text_area import Selection


class FeatureSummaryModal(ModalScreen[None]):
    """Modal with a quick summary of app features."""

    DEFAULT_CSS = """
    FeatureSummaryModal {
        align: center middle;
        background: $background 70%;
    }

    FeatureSummaryModal TextArea {
        background: $surface;
        width: 80;
        height: 80%;
        border: heavy $block-cursor-background;
        scrollbar-size: 1 1;
    }
    
    FeatureSummaryModal TextArea:focus {
        border: heavy $block-cursor-background;
    }
    """

    BINDINGS = [
        ("escape", "dismiss", "Close"),
        Binding("ctrl+d", "scroll_down", "Page Down", show=True),
        Binding("ctrl+u", "scroll_up", "Page Up", show=True),
        Binding("g", "scroll_top", "Top", show=False),
        Binding("G", "scroll_bottom", "Bottom", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._selection_timer: Timer | None = None
        self._last_selected_text: str = ""

    def compose(self) -> ComposeResult:
        text = (
            "JSON Logs Viewer\n\n"
            "Navigation\n"
            "  j/k, arrows  Move up/down\n"
            "  gg/G         Jump to top/bottom\n"
            "  Enter        Open detail view\n"
            "  q            Quit\n\n"
            "Search & Filter\n"
            "  /            Focus search bar\n"
            "  field:val    Field-specific match\n"
            "  field:       Field existence check\n"
            "  AND/OR/NOT   Boolean operators\n"
            "  ()           Grouping\n"
            "  Aa           Toggle case sensitivity\n"
            "  Highlight    Toggle filter/highlight mode\n\n"
            "Detail View\n"
            "  Enter        Open pretty-printed JSON detail\n"
            "  j/k          Navigate between logs in detail\n"
            "  ctrl+d/u     Scroll page down/up\n"
            "  g/G          Scroll to top/bottom\n"
            "  Esc/q        Close detail view\n\n"
            "Copy\n"
            "  y            Copy current log as JSON\n"
            "  Y            Copy log with context (5 surrounding)\n"
            "  y/Y in detail also works in detail view\n\n"
            "File\n"
            "  o            Open file picker\n"
            "  f            Toggle follow mode (tail -f)\n"
            "  w            Toggle soft-wrap for long lines\n\n"
            "History & Columns\n"
            "  H            Open search history modal\n"
            "               Select a past query to reapply it\n"
            "  c            Open column configuration modal\n"
            "               Add, remove, or reorder displayed columns"
        )
        yield TextArea(text, id="feature-summary-content", read_only=True)

    def on_mount(self) -> None:
        ta = self.query_one("#feature-summary-content", TextArea)
        ta.border_title = "Help"
        ta.border_subtitle = "ESCAPE to dismiss"

    def on_text_area_selection_changed(
        self, event: TextArea.SelectionChanged
    ) -> None:
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
            ta = self.query_one("#feature-summary-content", TextArea)
            ta.selection = Selection.cursor(ta.cursor_location)

    def action_scroll_down(self) -> None:
        self.query_one("#feature-summary-content", TextArea).action_page_down()

    def action_scroll_up(self) -> None:
        self.query_one("#feature-summary-content", TextArea).action_page_up()

    def action_scroll_top(self) -> None:
        self.query_one(
            "#feature-summary-content", TextArea
        ).action_scroll_home()

    def action_scroll_bottom(self) -> None:
        self.query_one(
            "#feature-summary-content", TextArea
        ).action_scroll_end()
