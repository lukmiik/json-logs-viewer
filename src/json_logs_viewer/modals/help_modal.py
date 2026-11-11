from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import TextArea
from textual.widgets.text_area import Selection

from json_logs_viewer.selection_copier import SelectionCopier


class HelpModal(ModalScreen[None]):
    """Modal with a quick summary of app features."""

    DEFAULT_CSS = """
    HelpModal {
        align: center middle;
        background: $background 70%;
    }

    HelpModal TextArea {
        background: $surface;
        width: 80;
        height: 80%;
        border: heavy $block-cursor-background;
        scrollbar-size: 1 1;
    }
    
    HelpModal TextArea:focus {
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
        self._selection_copier = SelectionCopier(
            owner=self, clear_selection=self._clear_selection
        )

    def compose(self) -> ComposeResult:
        text = (
            "JSON Logs Viewer\n\n"
            "Navigation\n"
            "  j/k, arrows  Move up/down\n"
            "  g/G          Jump to top/bottom\n"
            "  ctrl+d/u     Half page down/up\n"
            "  h/l          Scroll left/right\n"
            "  0/$          Scroll to line start/end\n"
            "  Enter        Open detail view\n"
            "  ctrl+p       Command palette\n"
            "  q            Quit\n\n"
            "Search & Filter\n"
            "  /            Focus search bar, Enter applies\n"
            "  text         Full-text match\n"
            "  field:val    Field-specific match\n"
            "  field:       Field existence check\n"
            "  a.b:val      Nested field (also lists)\n"
            "  f>=500       Compare numbers: < <= > >=\n"
            "  ts>=2024-01-15T10:00   Compare times (UTC)\n"
            "  last:15m     Last 15 min before the newest log\n"
            "  a b          Both terms (space means AND)\n"
            '  "a b"        Exact phrase\n'
            "  AND/OR/NOT   Boolean operators\n"
            "  ()           Grouping\n"
            "  C            Toggle case sensitivity\n"
            "  m            Toggle filter/highlight mode\n"
            "  n/N          Next/previous match (highlight)\n\n"
            "Detail View\n"
            "  Enter        Open pretty-printed JSON detail\n"
            "  j/k          Navigate between logs in detail\n"
            "  ctrl+d/u     Scroll page down/up\n"
            "  g/G          Scroll to top/bottom\n"
            "  Esc/q        Close detail view\n\n"
            "Copy\n"
            "  y            Copy current log as JSON\n"
            "  Y            Copy log with context (5 surrounding)\n"
            "  y/Y          Also work in the detail view\n"
            "  e            Export matching lines to a JSONL file\n"
            "  x            Clear the view (file unchanged; o reloads)\n\n"
            "File\n"
            "  o            Open file picker\n"
            "  f            Toggle follow mode (tail -f)\n"
            "  w            Toggle soft-wrap for long lines\n\n"
            "History & Columns\n"
            "  H            Open search history modal\n"
            "               Select a past query to reapply it\n"
            "               Saved across runs (--no-history: off)\n"
            "  c            Open column configuration modal\n"
            "               Select fields (a.b for nested) as columns\n"
            "               @level/@message/@timestamp: detected fields"
        )
        yield TextArea(text, id="feature-summary-content", read_only=True)

    def on_mount(self) -> None:
        ta = self.query_one("#feature-summary-content", TextArea)
        ta.border_title = "Help"
        ta.border_subtitle = "ESCAPE to dismiss"

    def on_text_area_selection_changed(
        self, event: TextArea.SelectionChanged
    ) -> None:
        self._selection_copier.update(
            selected_text=event.text_area.selected_text
        )

    def _clear_selection(self) -> None:
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
