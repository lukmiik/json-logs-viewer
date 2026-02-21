import argparse
import json
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult, SystemCommand
from textual.reactive import reactive
from textual.screen import Screen

from json_logs_viewer.filter_engine import FilterError, parse_filter
from json_logs_viewer.log_reader import read_lines_backward
from json_logs_viewer.modals.columns_modal import ColumnsModal
from json_logs_viewer.modals.detail_modal import DetailModal
from json_logs_viewer.modals.history_modal import HistoryModal
from json_logs_viewer.models import LogEntry
from json_logs_viewer.widgets.feature_summary_modal import FeatureSummaryModal
from json_logs_viewer.widgets.log_list import LogList
from json_logs_viewer.widgets.search_bar import SearchBar
from json_logs_viewer.widgets.status_bar import StatusBar


class LogViewerApp(App):
    CSS_PATH = "styles.tcss"

    BINDINGS = [
        ("/", "focus_search", "Search"),
        ("C", "toggle_case_sensitive", "Case"),
        ("m", "toggle_highlight_matches", "Highlight"),
        ("question_mark", "show_feature_summary", "Help"),
        ("H", "show_history", "History"),
        ("c", "show_columns", "Columns"),
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
    columns: reactive[list[str]] = reactive(list)  # type: ignore[assignment]

    def __init__(self, *, file: str | None = None, **kwargs: Any) -> None:  # noqa: ANN401
        super().__init__(**kwargs)
        self.initial_file = file
        self._last_selected_log_entry: LogEntry | None = None
        self._field_counts: Counter[str] = Counter()

    def compose(self) -> ComposeResult:
        yield LogList(id="logs")
        yield SearchBar(id="search", select_on_focus=False)
        yield StatusBar(id="status")

    def on_mount(self) -> None:
        """Load file if provided via CLI."""
        self._update_search_bar_visibility()
        if self.initial_file:
            self.load_file(filepath=self.initial_file)

    def watch_logs(
        self, old_logs: list[LogEntry], logs: list[LogEntry]
    ) -> None:
        self._rebuild_field_counts(old_logs=old_logs, new_logs=logs)
        self.apply_filter()

    def watch_filter_query(self) -> None:
        """Recompute filtered logs when query changes."""
        self.apply_filter()
        if (
            self.filter_query.strip()
            and not self.highlight_matches
            and not self.filtered_logs
        ):
            self.notify("No logs match the query", severity="warning")
        self._update_search_bar_visibility()

    def watch_case_sensitive(self) -> None:
        """Recompute filtered logs when case sensitivity changes."""
        self.apply_filter()

    def watch_highlight_matches(self) -> None:
        """Recompute filtered logs when highlight mode changes."""
        self.apply_filter()

    def apply_filter(self) -> None:
        """Apply current filter based on mode."""
        selected_log_entry = (
            self._get_selected_log_entry() or self._last_selected_log_entry
        )

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

    def watch_selected_index(self) -> None:
        selected_log_entry = self._get_selected_log_entry()
        if selected_log_entry is not None:
            self._last_selected_log_entry = selected_log_entry

    def _rebuild_field_counts(
        self, *, old_logs: list[LogEntry], new_logs: list[LogEntry]
    ) -> None:
        """Rebuild or incrementally update the field frequency counter.

        If new_logs is a superset (append), only count the new entries.
        Otherwise, recount from scratch.
        """
        old_len = len(old_logs)
        new_len = len(new_logs)
        if new_len >= old_len > 0 and new_logs[:old_len] is old_logs[:old_len]:
            # Incremental append (follow mode): only count new entries.
            for log in new_logs[old_len:]:
                self._field_counts.update(log.data.keys())
        else:
            # Full replacement: recount everything.
            self._field_counts = Counter()
            for log in new_logs:
                self._field_counts.update(log.data.keys())

    def discover_fields(self) -> list[str]:
        """Return top 20 fields by frequency."""
        return [f for f, _ in self._field_counts.most_common(20)]

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

        log_list = self.query_one("#logs", LogList)
        log_list.loading = True

        logs: list[LogEntry] = []
        try:
            for line_num, line_text in read_lines_backward(filepath=path):
                try:
                    data = json.loads(line_text)
                    log = LogEntry(
                        line_number=line_num, data=data, raw_json=line_text
                    )
                    logs.append(log)
                except json.JSONDecodeError as e:
                    self.log.warning(f"Line {line_num}: invalid JSON: {e}")
                    continue
            logs.reverse()
        except Exception as e:
            log_list.loading = False
            self.exit(message=f"Error reading file: {e}")
            return
        self._last_selected_log_entry = None
        self.logs = logs

        self.filepath = filepath
        self.selected_index = max(0, len(logs) - 1)
        log_list.loading = False

    def _update_search_bar_visibility(
        self, *, force_visible: bool = False
    ) -> None:
        """Show search bar when query is active or explicitly requested."""
        search_bar = self.query_one("#search", SearchBar)
        search_bar.display = force_visible or bool(self.filter_query.strip())

    def action_focus_search(self) -> None:
        self._update_search_bar_visibility(force_visible=True)
        self.query_one("#search", SearchBar).focus()
        self.call_after_refresh(
            self.query_one("#logs", LogList)._scroll_cursor_into_view
        )

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

    def action_show_history(self) -> None:
        if isinstance(self.screen, HistoryModal):
            return
        self.push_screen(HistoryModal(), callback=self._on_history_selected)

    def _on_history_selected(self, query: str | None) -> None:
        if query is None:
            return
        search_bar = self.query_one("#search", SearchBar)
        search_bar.value = query
        self.filter_query = query
        self._update_search_bar_visibility()
        self.query_one("#logs", LogList).focus()

    def action_show_columns(self) -> None:
        """Open column configuration modal."""
        if isinstance(self.screen, ColumnsModal):
            return
        self.push_screen(ColumnsModal(), callback=self._on_columns_selected)

    def _on_columns_selected(self, columns: list[str] | None) -> None:
        """Handle column selection from modal."""
        if columns is None:
            return
        self.columns = columns

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
        yield SystemCommand(
            "Configure columns",
            "Select which fields to display as columns",
            self.action_show_columns,
        )

    def watch_filtered_logs(self) -> None:
        """Ensure selected_index stays in bounds."""
        if self.selected_index >= len(self.filtered_logs):
            self.selected_index = max(0, len(self.filtered_logs) - 1)

    def on_log_list_log_selected(self, event: LogList.LogSelected) -> None:
        """Open detail modal when log is selected."""
        modal = DetailModal(
            log_entry=event.log_entry,
            current_index=self.selected_index,
            logs=self.filtered_logs,
        )
        self.push_screen(modal)


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
