import argparse
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult, SystemCommand
from textual.reactive import reactive
from textual.screen import Screen

from json_logs_viewer.filter_engine import FilterError, parse_filter
from json_logs_viewer.log_reader import read_lines_backward
from json_logs_viewer.models import LogEntry
from json_logs_viewer.widgets.feature_summary_modal import FeatureSummaryModal
from json_logs_viewer.widgets.log_list import LogList
from json_logs_viewer.widgets.search_bar import SearchBar
from json_logs_viewer.widgets.status_bar import StatusBar


class LogViewerApp(App):
    CSS_PATH = "styles.tcss"

    BINDINGS = [
        ("w", "toggle_wrap", "Toggle Wrap"),
        ("c", "toggle_case_sensitive", "Case Sensitivity"),
        ("m", "toggle_highlight_matches", "Search Highlight"),
        ("question_mark", "show_feature_summary", "Help"),
    ]

    logs: reactive[list[LogEntry]] = reactive(list)  # type: ignore[assignment]
    filtered_logs: reactive[list[LogEntry]] = reactive(list)  # type: ignore[assignment]
    filter_query: reactive[str] = reactive("")
    selected_index: reactive[int] = reactive(0)
    search_history: reactive[list[str]] = reactive(list)  # type: ignore[assignment]
    filepath: reactive[str | None] = reactive(None)
    wrap_log_lines: reactive[bool] = reactive(False)
    case_sensitive: reactive[bool] = reactive(False)
    highlight_matches: reactive[bool] = reactive(False)

    def __init__(self, *, file: str | None = None, **kwargs: Any) -> None:  # noqa: ANN401
        super().__init__(**kwargs)
        self.initial_file = file

    def compose(self) -> ComposeResult:
        yield LogList(id="logs")
        yield SearchBar(id="search", select_on_focus=False)
        yield StatusBar(id="status")

    def on_mount(self) -> None:
        """Load file if provided via CLI."""
        self._update_search_bar_visibility()
        if self.initial_file:
            self.load_file(filepath=self.initial_file)

    def watch_logs(self) -> None:
        self.apply_filter()

    def watch_filter_query(self) -> None:
        """Recompute filtered logs when query changes."""
        self.apply_filter()
        self._update_search_bar_visibility()

    def watch_case_sensitive(self) -> None:
        """Recompute filtered logs when case sensitivity changes."""
        self.apply_filter()

    def watch_highlight_matches(self) -> None:
        """Recompute filtered logs when highlight mode changes."""
        self.apply_filter()

    def apply_filter(self) -> None:
        """Apply current filter based on mode."""
        selected_log_entry = self._get_selected_log_entry()

        if not self.filter_query:
            self.filtered_logs = self.logs
            self._restore_selected_log_entry(log_entry=selected_log_entry)
            return

        try:
            matcher = parse_filter(
                query=self.filter_query,
                case_sensitive=self.case_sensitive,
            )

            if self.highlight_matches:
                next_filtered_logs = self.logs
            else:
                next_filtered_logs = [log for log in self.logs if matcher(log)]

            self.filtered_logs = next_filtered_logs
            self._restore_selected_log_entry(log_entry=selected_log_entry)
        except FilterError as e:
            self.notify(str(e), severity="error")
            self.filtered_logs = self.logs
            self._restore_selected_log_entry(log_entry=selected_log_entry)

    def _get_selected_log_entry(self) -> LogEntry | None:
        if 0 <= self.selected_index < len(self.filtered_logs):
            return self.filtered_logs[self.selected_index]
        return None

    def _restore_selected_log_entry(
        self, *, log_entry: LogEntry | None
    ) -> None:
        if log_entry is None:
            return

        logs_index_by_id = {
            id(candidate): index for index, candidate in enumerate(self.logs)
        }

        for index, candidate in enumerate(self.filtered_logs):
            if candidate is log_entry:
                self.selected_index = index
                return

        if not self.filtered_logs:
            return

        selected_log_index = logs_index_by_id.get(id(log_entry))
        if selected_log_index is None:
            return

        def filtered_distance(*, filtered_index: int) -> int:
            filtered_entry = self.filtered_logs[filtered_index]
            filtered_log_index = logs_index_by_id.get(
                id(filtered_entry), selected_log_index
            )
            return abs(filtered_log_index - selected_log_index)

        closest_filtered_index = min(
            range(len(self.filtered_logs)),
            key=lambda filtered_index: filtered_distance(
                filtered_index=filtered_index
            ),
        )
        self.selected_index = closest_filtered_index

    def load_file(self, *, filepath: str) -> None:
        """Read and parse JSONL file."""
        path = Path(filepath)
        if not path.exists():
            self.exit(message=f"File not found: {filepath}")
            return
        if not path.is_file():
            self.exit(message=f"Not a file: {filepath}")
            return

        logs: list[LogEntry] = []
        try:
            for line_num, line_text in read_lines_backward(filepath=path):
                try:
                    data = json.loads(line_text)
                    log = LogEntry(line_number=line_num, data=data)
                    logs.append(log)
                except json.JSONDecodeError as e:
                    self.log.warning(f"Line {line_num}: invalid JSON: {e}")
                    continue
            logs.reverse()
        except Exception as e:
            self.exit(message=f"Error reading file: {e}")
            return
        self.logs = logs

        self.filepath = filepath
        self.selected_index = max(0, len(logs) - 1)

    def _update_search_bar_visibility(
        self, *, force_visible: bool = False
    ) -> None:
        """Show search bar when query is active or explicitly requested."""
        search_bar = self.query_one("#search", SearchBar)
        search_bar.display = force_visible or bool(self.filter_query.strip())

    def action_focus_search(self) -> None:
        self._update_search_bar_visibility(force_visible=True)
        self.query_one("#search", SearchBar).focus()

    def action_toggle_wrap(self) -> None:
        self.wrap_log_lines = not self.wrap_log_lines

    def action_toggle_case_sensitive(self) -> None:
        self.case_sensitive = not self.case_sensitive

    def action_toggle_highlight_matches(self) -> None:
        self.highlight_matches = not self.highlight_matches

    def action_show_feature_summary(self) -> None:
        if isinstance(self.screen, FeatureSummaryModal):
            return
        self.push_screen(FeatureSummaryModal())

    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        yield from super().get_system_commands(screen)
        yield SystemCommand(
            "Toggle line wrap",
            "Switch between horizontal scroll and soft wrap modes",
            self.action_toggle_wrap,
        )
        yield SystemCommand(
            "Toggle case-sensitive filtering",
            "Switch case-sensitive matching on or off",
            self.action_toggle_case_sensitive,
        )
        yield SystemCommand(
            "Toggle highlight mode",
            "Switch between filter mode and highlight mode",
            self.action_toggle_highlight_matches,
        )
        yield SystemCommand(
            "Show help",
            "Open a modal with a summary of app features",
            self.action_show_feature_summary,
        )

    def watch_filtered_logs(self) -> None:
        """Ensure selected_index stays in bounds."""
        if self.selected_index >= len(self.filtered_logs):
            self.selected_index = max(0, len(self.filtered_logs) - 1)


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(description="JSON Logs Viewer")
    parser.add_argument("file", nargs="?", help="JSONL file to view")
    parser.add_argument(
        "-f", "--follow", action="store_true", help="Follow mode (Phase 10)"
    )
    args = parser.parse_args()

    app = LogViewerApp(file=args.file)
    app.run()


if __name__ == "__main__":
    main()
