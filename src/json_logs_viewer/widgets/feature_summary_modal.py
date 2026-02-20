from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static


class FeatureSummaryModal(ModalScreen[None]):
    """Modal with a quick summary of app features."""

    DEFAULT_CSS = """
    FeatureSummaryModal {
        align: center middle;
        background: $background 70%;
    }

    FeatureSummaryModal VerticalScroll {
        background: $surface;
        width: auto;
        height: auto;
        min-width: 64;
        max-width: 90%;
        max-height: 90%;
        border: heavy $block-cursor-background;
        padding: 1 2;
    }

    #feature-summary-content {
        width: auto;
    }
    """

    BINDINGS = [("escape", "dismiss", "Close")]

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="feature-summary-dialog") as dialog:
            yield Static(
                "JSON Logs Viewer\n\n"
                "[b]Navigation[/b]\n"
                "  j/k, arrows  Move up/down\n"
                "  gg/G         Jump to top/bottom\n"
                "  Enter        Open detail view\n"
                "  q            Quit\n\n"
                "[b]Search & Filter[/b]\n"
                "  /            Focus search bar\n"
                "  field:val    Field-specific match\n"
                "  field:       Field existence check\n"
                "  AND/OR/NOT   Boolean operators\n"
                "  ()           Grouping\n"
                "  Aa           Toggle case sensitivity\n"
                "  Highlight    Toggle filter/highlight mode\n\n"
                "[b]Detail View[/b]\n"
                "  Enter        Open pretty-printed JSON detail\n"
                "  j/k          Navigate between logs in detail\n"
                "  Esc/q        Close detail view\n\n"
                "[b]Copy[/b]\n"
                "  y            Copy current log as JSON\n"
                "  Y            Copy log with context (5 surrounding)\n\n"
                "[b]History & Columns[/b]\n"
                "  H            Open search history modal\n"
                "               Select a past query to reapply it\n"
                "  c            Open column configuration modal\n"
                "               Add, remove, or reorder displayed columns",
                id="feature-summary-content",
            )
        dialog.border_title = "Help"
        dialog.border_subtitle = "ESCAPE to dismiss"
