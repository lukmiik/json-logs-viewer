from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import threading
from collections import Counter
from collections.abc import Iterable
from contextlib import ExitStack
from functools import partial
from pathlib import Path
from typing import IO, Any

from textual.app import App, ComposeResult, SystemCommand
from textual.message import Message
from textual.reactive import reactive
from textual.screen import Screen

from json_logs_viewer.filter_engine import FilterError, parse_filter
from json_logs_viewer.log_reader import (
    find_line_boundary,
    read_lines_backward,
)
from json_logs_viewer.log_watcher import WatcherBase, get_watcher
from json_logs_viewer.modals.columns_modal import ColumnsModal
from json_logs_viewer.modals.detail_modal import DetailModal
from json_logs_viewer.modals.file_picker_modal import FilePickerModal
from json_logs_viewer.modals.history_modal import HistoryModal
from json_logs_viewer.models import LogEntry
from json_logs_viewer.widgets.feature_summary_modal import FeatureSummaryModal
from json_logs_viewer.widgets.log_list import LogList
from json_logs_viewer.widgets.search_bar import SearchBar
from json_logs_viewer.widgets.status_bar import StatusBar


class LogViewerApp(App):
    CSS_PATH = "styles.tcss"

    # Follow-mode messages are posted from the watcher thread with
    # post_message (thread-safe, doesn't wait). Each carries the follow
    # session it came from; handlers drop messages from a stopped session.

    class FollowData(Message):
        """A chunk of newly appended bytes.

        The watcher waits on `consumed` before reading more (back-pressure).
        """

        def __init__(
            self,
            *,
            chunk: bytes,
            session: threading.Event,
            consumed: threading.Event,
        ) -> None:
            self.chunk = chunk
            self.session = session
            self.consumed = consumed
            super().__init__()

    class FollowedFileReset(Message):
        """The followed file was truncated or rotated."""

        def __init__(self, *, session: threading.Event) -> None:
            self.session = session
            super().__init__()

    class FollowError(Message):
        """The watcher stopped because reading the file failed."""

        def __init__(
            self, *, error: Exception, session: threading.Event
        ) -> None:
            self.error = error
            self.session = session
            super().__init__()

    BINDINGS = [
        ("/", "focus_search", "Search"),
        ("C", "toggle_case_sensitive", "Case"),
        ("m", "toggle_highlight_matches", "Highlight"),
        ("f", "toggle_follow", "Follow"),
        ("question_mark", "show_feature_summary", "Help"),
        ("H", "show_history", "History"),
        ("c", "show_columns", "Columns"),
        ("o", "open_file", "Open"),
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
    follow_mode: reactive[bool] = reactive(False)

    def __init__(
        self,
        *,
        file: str | None = None,
        follow: bool = False,
        show_picker_on_start: bool = False,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        super().__init__(**kwargs)
        self.initial_file = file
        self._initial_follow = follow
        self._show_picker_on_start = show_picker_on_start
        self._last_selected_log_entry: LogEntry | None = None
        self._field_counts: Counter[str] = Counter()
        self._watcher: WatcherBase | None = None
        self._watch_file: IO[bytes] | None = None
        # Follow position invariant: _follow_offset is the byte where the
        # first not-yet-consumed line starts, and _last_line_number is the
        # number of file lines before it. _follow_buffer holds the bytes of
        # a partial line read past _follow_offset but not yet terminated.
        self._follow_buffer: bytes = b""
        self._last_line_number: int = 0
        self._follow_offset: int = 0
        # Identifies the running follow session; set when it stops.
        self._follow_session: threading.Event | None = None

    def compose(self) -> ComposeResult:
        yield LogList(id="logs")
        yield SearchBar(id="search", select_on_focus=False)
        yield StatusBar(id="status")

    def on_mount(self) -> None:
        """Load file if provided via CLI, otherwise open file picker."""
        self._update_search_bar_visibility()
        if self.initial_file:
            self.load_file(filepath=self.initial_file)
            if self._initial_follow:
                self.follow_mode = True
        elif self._show_picker_on_start:
            self.push_screen(
                FilePickerModal(), callback=self._on_file_selected
            )

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

        If new_logs starts with old_logs (follow-mode append), only count the
        new entries. Otherwise, recount from scratch.
        """
        old_len = len(old_logs)
        new_len = len(new_logs)
        # `==`, not `is`: a slice is always a new list, so `is` never matched.
        # List equality checks element identity first, so this is fast.
        if new_len >= old_len > 0 and new_logs[:old_len] == old_logs:
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
            self.notify(f"File not found: {filepath}", severity="error")
            return
        if not path.is_file():
            self.notify(f"Not a file: {filepath}", severity="error")
            return

        log_list = self.query_one("#logs", LogList)
        log_list.loading = True

        logs: list[LogEntry] = []
        try:
            # Measure first and read exactly this many bytes, so anything
            # appended while loading is left for follow mode.
            size = path.stat().st_size
            for line_num, line_text in read_lines_backward(
                filepath=path, size=size
            ):
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
            offset, line_count = find_line_boundary(filepath=path, size=size)
        except Exception as e:
            log_list.loading = False
            self.notify(f"Error reading file: {e}", severity="error")
            return
        self._last_selected_log_entry = None
        self.logs = logs

        self.filepath = filepath
        if offset < size and logs and logs[-1].line_number == line_count + 1:
            # The unterminated last line parsed as JSON, so it is complete
            # (a half-written JSON object can't parse): count it as consumed.
            offset, line_count = size, line_count + 1
        self._follow_offset = offset
        self._last_line_number = line_count
        self._follow_buffer = b""
        self.selected_index = max(0, len(logs) - 1)
        log_list.loading = False
        self.call_after_refresh(log_list._scroll_cursor_into_view)

    def _update_search_bar_visibility(
        self, *, force_visible: bool = False
    ) -> None:
        """Show the search bar only while it is being used.

        An applied filter doesn't keep it open: the status bar shows the
        active query instead, and `/` reopens the bar with it.
        """
        search_bar = self.query_one("#search", SearchBar)
        search_bar.display = force_visible or search_bar.has_focus

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

    def action_open_file(self) -> None:
        """Open file picker modal."""
        if isinstance(self.screen, FilePickerModal):
            return
        self.push_screen(FilePickerModal(), callback=self._on_file_selected)

    def _on_file_selected(self, filepath: str | None) -> None:
        """Handle file selection from picker, resetting all state."""
        if filepath is None:
            return
        if self.follow_mode:
            self.follow_mode = False
        self.filter_query = ""
        self.case_sensitive = False
        self.highlight_matches = False
        self.wrap_log_lines = False
        self.columns = []
        self.search_history = []
        search_bar = self.query_one("#search", SearchBar)
        search_bar.value = ""
        self._update_search_bar_visibility()
        self.load_file(filepath=filepath)

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

    def action_toggle_follow(self) -> None:
        if not self.filepath:
            self.notify("No file loaded", severity="warning")
            return
        self.follow_mode = not self.follow_mode

    def watch_follow_mode(self, follow_mode: bool) -> None:
        if follow_mode:
            self._start_follow()
        else:
            self._stop_follow()

    def _start_follow(self) -> None:
        if not self.filepath or self._watcher is not None:
            return
        self._follow_buffer = b""
        session = threading.Event()
        try:
            # The file must stay open after this method returns, so `with`
            # can't own it. ExitStack closes it if any later step fails;
            # pop_all() keeps it open once everything succeeded.
            with ExitStack() as stack:
                watch_file = stack.enter_context(open(self.filepath, "rb"))
                watch_file.seek(self._follow_offset)
                watcher = get_watcher()
                stack.callback(watcher.close)
                watcher.watch(
                    fileno=watch_file.fileno(),
                    path=self.filepath,
                    callback=partial(self._on_watcher_data, session=session),
                    error_callback=partial(
                        self._on_watcher_error, session=session
                    ),
                    reset_callback=partial(
                        self._on_watcher_reset, session=session
                    ),
                )
                watcher.start()
                stack.pop_all()
        except OSError as error:
            self.notify(f"Can't follow file: {error}", severity="error")
            self.follow_mode = False
            return
        # Only store state once setup fully succeeded.
        self._watch_file = watch_file
        self._watcher = watcher
        self._follow_session = session

    def _stop_follow(self) -> None:
        if self._follow_session is not None:
            # Wakes a watcher waiting for a chunk to be consumed, and marks
            # this session's still-queued messages as stale.
            self._follow_session.set()
            self._follow_session = None
        if self._watcher is not None:
            self._watcher.close()  # signals exit and joins thread
            self._watcher = None
        if self._watch_file is not None:
            # _follow_offset already excludes the buffered partial line (see
            # _process_chunk), so resuming re-reads that line from its start.
            self._watch_file.close()
            self._watch_file = None
        self._follow_buffer = b""

    def _on_watcher_data(
        self, chunk: bytes, *, session: threading.Event
    ) -> None:
        """Called from watcher thread: hand the chunk to the main thread.

        Waits until the chunk is processed so a fast writer can't make the
        watcher read unboundedly ahead (back-pressure, one chunk in flight).
        Unlike call_from_thread, the wait gives up when the session stops,
        so _stop_follow's join() never waits on this thread.
        """
        consumed = threading.Event()
        self.post_message(
            self.FollowData(chunk=chunk, session=session, consumed=consumed)
        )
        while not consumed.wait(timeout=0.05):
            if session.is_set():
                return

    def on_log_viewer_app_follow_data(
        self, message: LogViewerApp.FollowData
    ) -> None:
        try:
            # A chunk from a stopped session wasn't consumed: _follow_offset
            # still points before it, so resuming re-reads those bytes.
            if message.session is self._follow_session:
                self._process_chunk(message.chunk)
        finally:
            message.consumed.set()

    def _on_watcher_error(
        self, error: Exception, *, session: threading.Event
    ) -> None:
        """Called from watcher thread on error; the watcher then exits.

        post_message, not call_from_thread: call_from_thread blocks this
        thread until the main thread is done, but the main thread stops
        follow mode by joining this thread, so both would wait (deadlock
        broken only by the 1 s join timeout).
        """
        self.post_message(self.FollowError(error=error, session=session))

    def on_log_viewer_app_follow_error(
        self, message: LogViewerApp.FollowError
    ) -> None:
        if message.session is not self._follow_session:
            return
        self.notify(str(message.error), severity="error")
        self.follow_mode = False

    def _on_watcher_reset(self, *, session: threading.Event) -> None:
        """Called from watcher thread when the file was truncated/rotated."""
        self.post_message(self.FollowedFileReset(session=session))

    def on_log_viewer_app_followed_file_reset(
        self, message: LogViewerApp.FollowedFileReset
    ) -> None:
        """Reload the file so the list mirrors what is on disk again."""
        if message.session is not self._follow_session or not self.filepath:
            return
        self._stop_follow()
        self.load_file(filepath=self.filepath)
        self._start_follow()
        if self.follow_mode:
            self.notify("File was truncated or rotated; reloaded")

    def _process_chunk(self, chunk: bytes) -> None:
        """Split chunk into lines, parse JSON, append to logs.

        Splits bytes before decoding, so a multi-byte UTF-8 character cut
        between two chunks stays intact in the buffer.
        """
        *lines, self._follow_buffer = (self._follow_buffer + chunk).split(
            b"\n"
        )
        self._follow_offset += sum(len(line) + 1 for line in lines)

        new_logs: list[LogEntry] = []
        for raw_line in lines:
            # Every line counts, so line numbers match the file even when
            # blank or invalid lines are skipped below.
            self._last_line_number += 1
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                log = LogEntry(
                    line_number=self._last_line_number,
                    data=data,
                    raw_json=line,
                )
                new_logs.append(log)
            except json.JSONDecodeError:
                self.log.warning(f"Follow: invalid JSON: {line[:80]}")

        if new_logs:
            was_on_last = self.selected_index == len(self.filtered_logs) - 1
            self.logs = [*self.logs, *new_logs]
            if self.follow_mode and was_on_last:
                self.selected_index = len(self.filtered_logs) - 1

    def on_unmount(self) -> None:
        self._stop_follow()

    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        yield from super().get_system_commands(screen)
        yield SystemCommand(
            "Open file",
            "Browse and open a log file",
            self.action_open_file,
        )
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
        yield SystemCommand(
            "Toggle follow mode",
            "Watch file for new log entries in real-time",
            self.action_toggle_follow,
        )

    def watch_filtered_logs(self) -> None:
        """Ensure selected_index stays in bounds."""
        if self.selected_index >= len(self.filtered_logs):
            self.selected_index = max(0, len(self.filtered_logs) - 1)

    def on_log_list_log_selected(self, event: LogList.LogSelected) -> None:
        """Open detail modal when log is selected."""
        modal = DetailModal(log_entry=event.log_entry)
        self.push_screen(modal)


# The served child gets its file through this variable, never through the
# command string (see build_serve_command).
SERVE_FILE_ENV = "JLV_SERVE_FILE"


def build_serve_command(
    *,
    follow: bool,
    posix: bool = os.name == "posix",
    executable: str = sys.executable,
) -> str:
    """Build the command textual-serve runs for each browser session.

    textual-serve only takes a command string and runs it through a shell
    (`/bin/sh -c` on POSIX, `cmd.exe /c` on Windows). Rather than escape the
    filename for two very different shells, it isn't in the command at all:
    main() passes it in the SERVE_FILE_ENV environment variable, which the
    child inherits. The command holds only fixed arguments plus our own
    interpreter path, quoted for the platform's shell. `-m` runs the same
    interpreter and venv as this process.
    """
    argv = [executable, "-m", "json_logs_viewer"]
    if follow:
        argv.append("--follow")
    return shlex.join(argv) if posix else subprocess.list2cmdline(argv)


def main() -> None:
    """Entry point."""
    # prog: under `python -m` argparse would otherwise print "__main__.py".
    parser = argparse.ArgumentParser(
        prog="jlv", description="JSON Logs Viewer"
    )
    parser.add_argument("file", nargs="?", help="JSONL file to view")
    parser.add_argument(
        "-f", "--follow", action="store_true", help="Follow mode"
    )
    parser.add_argument(
        "--serve", action="store_true", help="Serve app in browser"
    )
    args = parser.parse_args()

    if args.serve:
        try:
            # Optional extra: it pulls in a web server most users don't need.
            from textual_serve.server import Server
        except ImportError:
            sys.exit(
                "jlv: --serve needs the optional 'serve' extra. Install it "
                "with:\n  uv tool install 'json-logs-viewer[serve]'\nor:\n"
                "  pip install 'json-logs-viewer[serve]'"
            )

        if args.file:
            os.environ[SERVE_FILE_ENV] = args.file
        Server(
            build_serve_command(follow=args.follow),
            # Shown on the served page; it defaults to the command string.
            title=f"jlv {Path(args.file).name}" if args.file else "jlv",
        ).serve()
        return

    # Pop, so programs started from the app don't inherit it.
    file = args.file or os.environ.pop(SERVE_FILE_ENV, None)
    app = LogViewerApp(
        file=file,
        follow=args.follow,
        show_picker_on_start=file is None,
    )
    app.run()


if __name__ == "__main__":
    main()
