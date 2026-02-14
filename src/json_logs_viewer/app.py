import argparse
import json
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.reactive import reactive

from json_logs_viewer.models import LogEntry
from json_logs_viewer.widgets.log_list import LogList
from json_logs_viewer.widgets.search_bar import SearchBar
from json_logs_viewer.widgets.status_bar import StatusBar


class LogViewerApp(App):
    CSS_PATH = "styles.tcss"

    logs: reactive[list[LogEntry]] = reactive(list)  # type: ignore[assignment]
    filtered_logs: reactive[list[LogEntry]] = reactive(list)  # type: ignore[assignment]
    filter_query: reactive[str] = reactive("")
    selected_index: reactive[int] = reactive(0)
    search_history: reactive[list[str]] = reactive(list)  # type: ignore[assignment]
    filepath: reactive[str | None] = reactive(None)

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

    def apply_filter(self) -> None:
        """Apply current filter to logs. Phase 3 stub: returns all logs."""
        self.filtered_logs = self.logs

    def load_file(self, *, filepath: str) -> None:
        """Read and parse JSONL file."""
        path = Path(filepath)
        if not path.exists():
            self.exit(message=f"File not found: {filepath}")
            return
        if not path.is_file():
            self.exit(message=f"Not a file: {filepath}")
            return

        logs = []
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

        self.logs = logs
        self.filepath = filepath
        self.selected_index = 0

    def action_focus_search(self) -> None:
        self.query_one("#search", SearchBar).focus()

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
