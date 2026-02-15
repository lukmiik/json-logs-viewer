import argparse
import json
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult, SystemCommand
from textual.reactive import reactive
from textual.screen import Screen

from json_logs_viewer.filter_engine import FilterError, parse_filter
from json_logs_viewer.models import LogEntry
from json_logs_viewer.widgets.log_list import LogList
from json_logs_viewer.widgets.search_bar import SearchBar
from json_logs_viewer.widgets.status_bar import StatusBar


class LogViewerApp(App):
    CSS_PATH = "styles.tcss"

    BINDINGS = [
        ("w", "toggle_wrap", "Toggle Wrap"),
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
        yield SearchBar(id="search")
        yield LogList(id="logs")
        yield StatusBar(id="status")

    def on_mount(self) -> None:
        """Load file if provided via CLI and set initial focus."""
        self.query_one("#logs", LogList).focus()
        if self.initial_file:
            self.load_file(filepath=self.initial_file)

    def watch_logs(self) -> None:
        self.apply_filter()

    def watch_filter_query(self) -> None:
        """Recompute filtered logs when query changes."""
        self.apply_filter()

    def watch_case_sensitive(self) -> None:
        """Recompute filtered logs when case sensitivity changes."""
        self.apply_filter()

    def watch_highlight_matches(self) -> None:
        """Recompute filtered logs when highlight mode changes."""
        self.apply_filter()

    def apply_filter(self) -> None:
        """Apply current filter based on mode."""
        t_start = time.perf_counter()
        if not self.filter_query:
            self.filtered_logs = self.logs
            self.log.info(
                f"[PERF] apply_filter (no query, passthrough): "
                f"{time.perf_counter() - t_start:.3f}s"
            )
            return

        try:
            matcher = parse_filter(
                query=self.filter_query,
                case_sensitive=self.case_sensitive,
            )

            if self.highlight_matches:
                self.filtered_logs = self.logs
            else:
                self.filtered_logs = [log for log in self.logs if matcher(log)]

        except FilterError as e:
            self.notify(str(e), severity="error")
            self.filtered_logs = self.logs
        self.log.info(
            f"[PERF] apply_filter: {time.perf_counter() - t_start:.3f}s "
            f"({len(self.filtered_logs)} results)"
        )

    def load_file(self, *, filepath: str) -> None:
        """Read and parse JSONL file."""
        t_total = time.perf_counter()
        path = Path(filepath)
        if not path.exists():
            self.exit(message=f"File not found: {filepath}")
            return
        if not path.is_file():
            self.exit(message=f"Not a file: {filepath}")
            return

        logs = []
        t_read = time.perf_counter()
        try:
            with path.open("r", encoding="utf-8") as f:
                for idx, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        log = LogEntry(line_number=idx, data=data)
                        logs.append(log)
                    except json.JSONDecodeError as e:
                        self.log.warning(f"Line {idx}: invalid JSON: {e}")
                        continue
        except Exception as e:
            self.exit(message=f"Error reading file: {e}")
            return
        self.log.info(
            f"[PERF] File read + parse: {time.perf_counter() - t_read:.3f}s "
            f"({len(logs)} entries)"
        )

        t_assign = time.perf_counter()
        self.logs = logs
        self.log.info(
            f"[PERF] logs assignment (triggers watch_logs → apply_filter → "
            f"watch_filtered_logs → LogList rebuild): "
            f"{time.perf_counter() - t_assign:.3f}s"
        )

        self.filepath = filepath
        t_select = time.perf_counter()
        self.selected_index = max(0, len(logs) - 1)
        self.log.info(
            f"[PERF] selected_index set to {self.selected_index}: "
            f"{time.perf_counter() - t_select:.3f}s"
        )
        self.log.info(
            f"[PERF] load_file total: {time.perf_counter() - t_total:.3f}s"
        )

    def action_focus_search(self) -> None:
        self.query_one("#search", SearchBar).focus()

    def action_toggle_wrap(self) -> None:
        self.wrap_log_lines = not self.wrap_log_lines

    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        yield from super().get_system_commands(screen)
        yield SystemCommand(
            "Toggle line wrap",
            "Switch between horizontal scroll and soft wrap modes",
            self.action_toggle_wrap,
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
