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
                "- Open and browse JSONL logs in a scrollable list.\n"
                "- Use / to focus the search bar and filter entries.\n"
                "- Filter supports field queries like level:ERROR.\n"
                "- Combine filters with AND / OR / NOT and parentheses.\n"
                "- Toggle line wrapping, case sensitivity, and"
                " highlight mode.\n"
                "- Navigate quickly with j/k, g/G, and arrow keys.",
                id="feature-summary-content",
            )
        dialog.border_title = "Help"
        dialog.border_subtitle = "ESCAPE to dismiss"
