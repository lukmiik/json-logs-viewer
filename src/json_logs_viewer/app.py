from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import threading
from bisect import bisect_left
from collections import Counter
from collections.abc import Iterable
from contextlib import ExitStack
from datetime import datetime
from functools import partial
from itertools import islice
from pathlib import Path
from typing import IO, Any

from textual.app import App, ComposeResult, SystemCommand
from textual.containers import Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.screen import Screen

from json_logs_viewer.constants import SEARCH_HISTORY_LIMIT
from json_logs_viewer.export import default_export_path, write_jsonl
from json_logs_viewer.field_paths import leaf_paths
from json_logs_viewer.filter_engine import (
    FilterError,
    Matcher,
    as_utc,
    parse_filter,
)
from json_logs_viewer.history_store import (
    default_history_path,
    load_history,
    save_history,
)
from json_logs_viewer.log_watcher import WatcherBase, get_watcher
from json_logs_viewer.modals.columns_modal import ColumnsModal
from json_logs_viewer.modals.confirm_modal import ConfirmModal
from json_logs_viewer.modals.detail_modal import DetailModal
from json_logs_viewer.modals.export_modal import ExportModal
from json_logs_viewer.modals.file_picker_modal import (
    FilePickerModal,
    PickedFile,
)
from json_logs_viewer.modals.help_modal import HelpModal
from json_logs_viewer.modals.history_modal import HistoryModal
from json_logs_viewer.models import (
    DETECTED_COLUMNS,
    FILE_COLUMN,
    LogEntry,
    appended_entries,
    find_first,
    parse_log_line,
)
from json_logs_viewer.sources import SourceFile, merge_by_time, read_source
from json_logs_viewer.stdin_pipe import (
    STDIN_ARG,
    STDIN_LABEL,
    StdinCopy,
    stdin_is_piped,
    take_over_stdin,
)
from json_logs_viewer.widgets.column_header import ColumnHeader
from json_logs_viewer.widgets.log_list import LogList
from json_logs_viewer.widgets.search_bar import SearchBar
from json_logs_viewer.widgets.status_bar import StatusBar


def _seq(entry: LogEntry) -> int:
    return entry.seq


class MainScreen(Screen[None]):
    """The app's default screen: starts with the log list focused.

    Textual focuses the first focusable widget by screen position, which
    is the search bar once the list sits inside the bordered pane. Set
    here rather than on the App, where every modal would inherit it.
    """

    AUTO_FOCUS = "#logs"


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
            source: SourceFile,
        ) -> None:
            self.chunk = chunk
            self.session = session
            self.consumed = consumed
            self.source = source
            super().__init__()

    class FollowedFileReset(Message):
        """The followed file was truncated or rotated."""

        def __init__(self, *, session: threading.Event) -> None:
            self.session = session
            super().__init__()

    class FollowError(Message):
        """The watcher stopped because reading the file failed."""

        def __init__(
            self,
            *,
            error: Exception,
            session: threading.Event,
            source: SourceFile,
        ) -> None:
            self.error = error
            self.session = session
            self.source = source
            super().__init__()

    BINDINGS = [
        ("/", "focus_search", "Search"),
        ("C", "toggle_case_sensitive", "Case"),
        ("m", "toggle_highlight_matches", "Highlight"),
        ("f", "toggle_follow", "Follow"),
        ("question_mark", "show_help", "Help"),
        ("H", "show_history", "History"),
        ("c", "show_columns", "Columns"),
        ("o", "open_file", "Open"),
        ("e", "export", "Export"),
        # A plain letter: terminals, editors and browsers often take ctrl+l.
        ("x", "clear_view", "Clear"),
    ]

    logs: reactive[list[LogEntry]] = reactive(list)  # type: ignore[assignment]
    filtered_logs: reactive[list[LogEntry]] = reactive(list)  # type: ignore[assignment]
    filter_query: reactive[str] = reactive("")
    selected_index: reactive[int] = reactive(0)
    search_history: reactive[list[str]] = reactive(list)  # type: ignore[assignment]
    # The first open file (None if none); filepaths lists all of them.
    filepath: reactive[str | None] = reactive(None)
    filepaths: reactive[list[str]] = reactive(list)  # type: ignore[assignment]
    wrap_log_lines: reactive[bool] = reactive(False)
    case_sensitive: reactive[bool] = reactive(False)
    highlight_matches: reactive[bool] = reactive(False)
    columns: reactive[list[str]] = reactive(list)  # type: ignore[assignment]
    follow_mode: reactive[bool] = reactive(False)

    def __init__(
        self,
        *,
        file: str | None = None,
        files: list[str] | None = None,
        follow: bool = False,
        show_picker_on_start: bool = False,
        history_path: Path | None = None,
        stdin_path: str | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        super().__init__(**kwargs)
        # `file` for one file; `files` for several (merged by timestamp).
        self.initial_files = files or ([file] if file else [])
        self._initial_follow = follow
        self._show_picker_on_start = show_picker_on_start
        # Where the search history is kept across runs; None keeps it in
        # memory only (tests, --no-history). main() passes the real path.
        self._history_path = history_path
        # The temporary copy of piped stdin, shown as "stdin" (main()).
        self.stdin_path = stdin_path
        self._history_save_warned = False
        self._last_selected_log_entry: LogEntry | None = None
        # Field path counts for the columns modal, filled lazily by
        # discover_fields: logs[:_counted_logs] are already counted.
        self._field_counts: Counter[str] = Counter()
        self._detected_counts: Counter[str] = Counter()
        self._counted_logs: int = 0
        # The matcher behind filtered_logs; None means every log is shown
        # (no query, highlight mode, or an invalid query).
        self._active_matcher: Matcher | None = None
        # The open files, each with its own follow position and watcher.
        self._sources: list[SourceFile] = []
        # Identifies the running follow session (all files' watchers share
        # it); set when it stops.
        self._follow_session: threading.Event | None = None

    def get_default_screen(self) -> Screen[None]:
        return MainScreen(id="_default")

    def compose(self) -> ComposeResult:
        # The pane carries the border so the header sits inside it.
        with Vertical(id="logs-pane"):
            yield ColumnHeader(id="column-header")
            yield LogList(id="logs")
        yield SearchBar(id="search", select_on_focus=False)
        yield StatusBar(id="status")

    def on_mount(self) -> None:
        """Load file if provided via CLI, otherwise open file picker."""
        if self._history_path is not None:
            self.search_history = load_history(
                path=self._history_path, limit=SEARCH_HISTORY_LIMIT
            )
        self._update_search_bar_visibility()
        if self.initial_files:
            self.load_files(filepaths=self.initial_files)
            if self._initial_follow:
                self.follow_mode = True
        elif self._show_picker_on_start:
            self.push_screen(FilePickerModal(), callback=self._on_file_picked)

    def watch_logs(
        self, old_logs: list[LogEntry], logs: list[LogEntry]
    ) -> None:
        appended = appended_entries(old=old_logs, new=logs)
        # Number the entries by position (only the new tail on an append),
        # before filtering, which relies on it to keep the cursor in place.
        first = 0 if appended is None else len(old_logs)
        for seq, log in enumerate(logs[first:], first):
            log.seq = seq
        if appended is None:
            # Not an append: the old counts belong to other logs.
            self._field_counts = Counter()
            self._detected_counts = Counter()
            self._counted_logs = 0
        if appended is None:
            self.apply_filter()
        else:
            self._filter_appended(appended=appended)

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

        self._active_matcher = None
        if not self.filter_query:
            self.filtered_logs = self.logs
            self._restore_selected_log_entry(log_entry=selected_log_entry)
            return

        try:
            matcher = parse_filter(
                query=self.filter_query,
                case_sensitive=self.case_sensitive,
                newest_timestamp=self.newest_timestamp,
            )

            if self.highlight_matches:
                next_filtered_logs = self.logs
            else:
                next_filtered_logs = [log for log in self.logs if matcher(log)]
                self._active_matcher = matcher

            self.filtered_logs = next_filtered_logs
            self._restore_selected_log_entry(log_entry=selected_log_entry)
        except FilterError as e:
            self.notify(str(e), severity="error")
            self.filtered_logs = self.logs
            self._restore_selected_log_entry(log_entry=selected_log_entry)

    def _filter_appended(self, *, appended: list[LogEntry]) -> None:
        """Follow-mode fast path: filter only the newly appended logs.

        Every query or setting change runs apply_filter, so filtered_logs
        and _active_matcher already match the current query; re-filtering
        the whole file on every batch would cost O(n).
        """
        if self._active_matcher is None:
            self.filtered_logs = self.logs
            return
        if self._active_matcher.relative:
            # last:<duration> is anchored at the newest log, so new logs
            # move the window and older ones may drop out: re-filter all.
            self.apply_filter()
            return
        matching = [log for log in appended if self._active_matcher(log)]
        if matching:
            self.filtered_logs = [*self.filtered_logs, *matching]

    def source_label(self, path: str) -> str:
        """How a file is named in the UI: "stdin" for piped input."""
        return STDIN_LABEL if path == self.stdin_path else path

    def newest_timestamp(self) -> datetime | None:
        """The newest detected timestamp: the anchor of last:<duration>."""
        return max(
            (as_utc(log.timestamp) for log in self.logs if log.timestamp),
            default=None,
        )

    def _get_selected_log_entry(self) -> LogEntry | None:
        if 0 <= self.selected_index < len(self.filtered_logs):
            return self.filtered_logs[self.selected_index]
        return None

    def watch_selected_index(self) -> None:
        selected_log_entry = self._get_selected_log_entry()
        if selected_log_entry is not None:
            self._last_selected_log_entry = selected_log_entry

    def discover_fields(self) -> list[str]:
        """Return the 20 most common field paths, nested ones dotted.

        Counting walks every object in every log (~0.3 s for 100k nested
        logs), and only the columns modal needs it, so it happens here on
        demand instead of on every load. Logs counted before stay counted:
        a follow-mode append only counts the new ones.
        """
        for log in islice(self.logs, self._counted_logs, None):
            self._field_counts.update(leaf_paths(value=log.data))
            for name, candidates in DETECTED_COLUMNS.items():
                if (
                    find_first(data=log.data, candidates=candidates)
                    is not None
                ):
                    self._detected_counts[name] += 1
        self._counted_logs = len(self.logs)
        # @timestamp/@level/@message first (when any log has them), then the
        # most common real fields.
        detected = [n for n in DETECTED_COLUMNS if self._detected_counts[n]]
        if len(self._sources) > 1:
            detected.insert(0, FILE_COLUMN)
        common = [
            f
            for f, _ in self._field_counts.most_common(20 + len(detected))
            if f not in detected
        ]
        return detected + common[:20]

    def _restore_selected_log_entry(
        self, *, log_entry: LogEntry | None
    ) -> None:
        """Keep the cursor on `log_entry`, or the nearest line still shown.

        filtered_logs is a subsequence of logs, so it is sorted by `seq`
        (list position): a binary search finds the spot in O(log n) instead
        of scanning every entry (this runs on every filter change).
        """
        filtered = self.filtered_logs
        if log_entry is None or not filtered:
            return
        pos = bisect_left(filtered, log_entry.seq, key=_seq)
        if pos < len(filtered) and filtered[pos] is log_entry:
            self.selected_index = pos
            return
        # Filtered out: the nearest line is a neighbour of the insertion
        # point. Within one file, distance is in file lines, so skipped
        # blank or invalid lines count; across files, in list positions.
        # min() keeps the first on a tie, i.e. the earlier line.
        neighbours = [i for i in (pos - 1, pos) if 0 <= i < len(filtered)]

        def distance(index: int) -> int:
            other = filtered[index]
            if other.source == log_entry.source:
                return abs(other.line_number - log_entry.line_number)
            return abs(other.seq - log_entry.seq)

        self.selected_index = min(neighbours, key=distance)

    def load_file(self, *, filepath: str) -> None:
        """Open one file, replacing whatever is open."""
        self.load_files(filepaths=[filepath])

    def load_files(self, *, filepaths: list[str]) -> None:
        """Open these files, replacing whatever is open.

        Several files are merged into one timeline by timestamp. A file
        that's missing or unreadable is reported and left out.
        """
        log_list = self.query_one("#logs", LogList)
        log_list.loading = True
        files: list[list[LogEntry]] = []
        sources: list[SourceFile] = []
        for filepath in dict.fromkeys(filepaths):  # drop duplicates
            path = Path(filepath)
            if not path.exists():
                self.notify(f"File not found: {filepath}", severity="error")
                continue
            if not path.is_file():
                self.notify(f"Not a file: {filepath}", severity="error")
                continue
            try:
                logs, source = read_source(path=filepath)
            except Exception as e:
                self.notify(f"Error reading file: {e}", severity="error")
                continue
            files.append(logs)
            sources.append(source)
        log_list.loading = False
        if not sources:
            return

        self._sources = sources
        merged = merge_by_time(files=files)
        self._last_selected_log_entry = None
        self.logs = merged
        self.filepaths = [source.path for source in sources]
        self.filepath = sources[0].path
        self.selected_index = max(0, len(merged) - 1)
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

    def action_show_help(self) -> None:
        if isinstance(self.screen, HelpModal):
            return
        self.push_screen(HelpModal())

    def _matching_logs(self) -> list[LogEntry]:
        """The logs the query matches, whether filtering or highlighting.

        In filter mode that is filtered_logs. Highlight mode shows every
        log, so its matches are computed here (an invalid query matches
        everything, as in filter mode).
        """
        if not (self.highlight_matches and self.filter_query.strip()):
            return self.filtered_logs
        try:
            matcher = parse_filter(
                query=self.filter_query,
                case_sensitive=self.case_sensitive,
                newest_timestamp=self.newest_timestamp,
            )
        except FilterError:
            return self.logs
        return [log for log in self.logs if matcher(log)]

    def action_export(self) -> None:
        if isinstance(self.screen, ExportModal):
            return
        entries = self._matching_logs()
        if not entries:
            self.notify("Nothing to export", severity="warning")
            return
        source = Path(self.filepath) if self.filepath else None
        if self.filepath == self.stdin_path:
            # The copy lives in a temp folder deleted on exit: export next
            # to where jlv was started instead.
            source = Path(STDIN_LABEL).absolute()
        self.push_screen(
            ExportModal(
                default_path=default_export_path(
                    source=source, several=len(self._sources) > 1
                ),
                count=len(entries),
            ),
            # The entries are taken now, so what is written matches the
            # count shown even if follow mode appends meanwhile.
            callback=partial(self._on_export_path, entries=entries),
        )

    def _on_export_path(
        self, path: Path | None, *, entries: list[LogEntry]
    ) -> None:
        if path is None:
            return
        try:
            write_jsonl(path=path, entries=entries)
        except OSError as error:
            self.notify(f"Export failed: {error}", severity="error")
            return
        noun = "line" if len(entries) == 1 else "lines"
        self.notify(f"Exported {len(entries)} {noun} to {path}")

    def action_clear_view(self) -> None:
        if isinstance(self.screen, ConfirmModal):
            return
        if not self.logs:
            self.notify("Nothing to clear", severity="warning")
            return
        count = len(self.logs)
        noun = "line" if count == 1 else "lines"
        self.push_screen(
            ConfirmModal(
                title="Clear view",
                question=(
                    f"Clear {count} {noun} from the view?\n"
                    "The file isn't changed; open it again (o) to reload."
                ),
            ),
            callback=self._on_clear_confirmed,
        )

    def _on_clear_confirmed(self, confirmed: bool | None) -> None:
        """Drop the loaded logs; the file and the follow offset stay.

        Follow mode keeps reading from where it was, so only lines written
        after the clear appear, with their real line numbers.
        """
        if not confirmed:
            return
        self.logs = []
        self.selected_index = 0

    def watch_search_history(self, history: list[str]) -> None:
        if self._history_path is None:
            return
        try:
            save_history(path=self._history_path, history=history)
        except OSError as error:
            # Warn once: searching still works, only persistence doesn't.
            if not self._history_save_warned:
                self._history_save_warned = True
                self.notify(
                    f"Couldn't save the search history: {error}",
                    severity="warning",
                )

    def action_clear_history(self) -> None:
        if isinstance(self.screen, ConfirmModal):
            return
        if not self.search_history:
            self.notify("The search history is empty")
            return
        count = len(self.search_history)
        noun = "query" if count == 1 else "queries"
        self.push_screen(
            ConfirmModal(
                title="Clear search history",
                question=f"Forget {count} saved {noun}?",
            ),
            callback=self._on_clear_history_confirmed,
        )

    def _on_clear_history_confirmed(self, confirmed: bool | None) -> None:
        if confirmed:
            self.search_history = []

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
        self.push_screen(FilePickerModal(), callback=self._on_file_picked)

    def _on_file_picked(self, picked: PickedFile | None) -> None:
        if picked is None:
            return
        if picked.add:
            self._add_file(filepath=picked.path)
        else:
            self._on_file_selected(picked.path)

    def _add_file(self, *, filepath: str) -> None:
        """Open one more file next to the open ones, keeping the query.

        Everything is reloaded and merged again; follow mode restarts so the
        new file is watched too.
        """
        if filepath in self.filepaths:
            self.notify(f"Already open: {filepath}", severity="warning")
            return
        following = self.follow_mode
        self._stop_follow()
        self.load_files(filepaths=[*self.filepaths, filepath])
        if following:
            self._start_follow()

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
        # The search history is shared by all files, so it is kept.
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
        if not self._sources:
            self.notify("No file loaded", severity="warning")
            return
        self.follow_mode = not self.follow_mode

    def watch_follow_mode(self, follow_mode: bool) -> None:
        if follow_mode:
            self._start_follow()
        else:
            self._stop_follow()

    def _start_follow(self) -> None:
        """Start one watcher per open file, all in one session."""
        if not self._sources or self._follow_session is not None:
            return
        session = threading.Event()
        try:
            # The files must stay open after this method returns, so `with`
            # can't own them. ExitStack closes everything if any later step
            # fails; pop_all() keeps them open once all succeeded.
            with ExitStack() as stack:
                started: list[tuple[IO[bytes], WatcherBase]] = []
                for source in self._sources:
                    source.buffer = b""
                    watch_file = stack.enter_context(open(source.path, "rb"))
                    watch_file.seek(source.offset)
                    watcher = get_watcher()
                    stack.callback(watcher.close)
                    watcher.watch(
                        fileno=watch_file.fileno(),
                        path=source.path,
                        callback=partial(
                            self._on_watcher_data,
                            session=session,
                            source=source,
                        ),
                        error_callback=partial(
                            self._on_watcher_error,
                            session=session,
                            source=source,
                        ),
                        reset_callback=partial(
                            self._on_watcher_reset, session=session
                        ),
                    )
                    watcher.start()
                    started.append((watch_file, watcher))
                stack.pop_all()
        except OSError as error:
            self.notify(f"Can't follow file: {error}", severity="error")
            self.follow_mode = False
            return
        # Only store state once setup fully succeeded.
        for source, (watch_file, watcher) in zip(
            self._sources, started, strict=True
        ):
            source.watch_file = watch_file
            source.watcher = watcher
        self._follow_session = session

    def _stop_follow(self) -> None:
        if self._follow_session is not None:
            # Wakes watchers waiting for a chunk to be consumed, and marks
            # this session's still-queued messages as stale.
            self._follow_session.set()
            self._follow_session = None
        for source in self._sources:
            if source.watcher is not None:
                source.watcher.close()  # signals exit and joins thread
                source.watcher = None
            if source.watch_file is not None:
                # offset already excludes the buffered partial line (see
                # _process_chunk), so resuming re-reads it from its start.
                source.watch_file.close()
                source.watch_file = None
            source.buffer = b""

    def _on_watcher_data(
        self, chunk: bytes, *, session: threading.Event, source: SourceFile
    ) -> None:
        """Called from watcher thread: hand the chunk to the main thread.

        Waits until the chunk is processed so a fast writer can't make the
        watcher read unboundedly ahead (back-pressure, one chunk in flight).
        Unlike call_from_thread, the wait gives up when the session stops,
        so _stop_follow's join() never waits on this thread.
        """
        consumed = threading.Event()
        self.post_message(
            self.FollowData(
                chunk=chunk, session=session, consumed=consumed, source=source
            )
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
                self._process_chunk(message.chunk, source=message.source)
        finally:
            message.consumed.set()

    def _on_watcher_error(
        self,
        error: Exception,
        *,
        session: threading.Event,
        source: SourceFile,
    ) -> None:
        """Called from watcher thread on error; the watcher then exits.

        post_message, not call_from_thread: call_from_thread blocks this
        thread until the main thread is done, but the main thread stops
        follow mode by joining this thread, so both would wait (deadlock
        broken only by the 1 s join timeout).
        """
        self.post_message(
            self.FollowError(error=error, session=session, source=source)
        )

    def on_log_viewer_app_follow_error(
        self, message: LogViewerApp.FollowError
    ) -> None:
        if message.session is not self._follow_session:
            return
        prefix = f"{message.source.name}: " if len(self._sources) > 1 else ""
        self.notify(f"{prefix}{message.error}", severity="error")
        self.follow_mode = False

    def _on_watcher_reset(self, *, session: threading.Event) -> None:
        """Called from watcher thread when the file was truncated/rotated."""
        self.post_message(self.FollowedFileReset(session=session))

    def on_log_viewer_app_followed_file_reset(
        self, message: LogViewerApp.FollowedFileReset
    ) -> None:
        """Reload the files so the list mirrors what is on disk again."""
        if message.session is not self._follow_session or not self._sources:
            return
        paths = [source.path for source in self._sources]
        self._stop_follow()
        self.load_files(filepaths=paths)
        self._start_follow()
        if self.follow_mode:
            self.notify("File was truncated or rotated; reloaded")

    def _process_chunk(
        self, chunk: bytes, *, source: SourceFile | None = None
    ) -> None:
        """Split chunk into lines, parse JSON, append to logs.

        `source` is the file the bytes came from (default: the first one).
        Splits bytes before decoding, so a multi-byte UTF-8 character cut
        between two chunks stays intact in the buffer. With several files,
        new lines are appended as they arrive rather than re-sorted.
        """
        if source is None:
            source = self._sources[0]
        *lines, source.buffer = (source.buffer + chunk).split(b"\n")
        source.offset += sum(len(line) + 1 for line in lines)

        new_logs: list[LogEntry] = []
        for raw_line in lines:
            # Every line counts, so line numbers match the file even when
            # blank or invalid lines are skipped below.
            source.line_count += 1
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            log = parse_log_line(line=line, line_number=source.line_count)
            if log is None:
                self.log.warning(f"Follow: not a JSON object: {line[:80]}")
                continue
            log.source = source.path
            new_logs.append(log)

        if new_logs:
            # An empty view (new file, or just cleared) counts as being at
            # the end, so the cursor follows the first lines that arrive.
            was_on_last = (
                not self.filtered_logs
                or self.selected_index == len(self.filtered_logs) - 1
            )
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
            self.action_show_help,
        )
        yield SystemCommand(
            "Export matching logs",
            "Save the logs the query matches to a JSONL file",
            self.action_export,
        )
        yield SystemCommand(
            "Clear view",
            "Hide the loaded logs; the file isn't changed",
            self.action_clear_view,
        )
        yield SystemCommand(
            "Clear search history",
            "Forget the saved search queries",
            self.action_clear_history,
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
    no_history: bool = False,
    posix: bool = os.name == "posix",
    executable: str = sys.executable,
) -> str:
    """Build the command textual-serve runs for each browser session.

    textual-serve only takes a command string and runs it through a shell
    (`/bin/sh -c` on POSIX, `cmd.exe /c` on Windows). Rather than escape the
    filename for two very different shells, it isn't in the command at all:
    main() passes the file names (a JSON list) in the SERVE_FILE_ENV
    environment variable, which the
    child inherits. The command holds only fixed arguments plus our own
    interpreter path, quoted for the platform's shell. `-m` runs the same
    interpreter and venv as this process.
    """
    argv = [executable, "-m", "json_logs_viewer"]
    if follow:
        argv.append("--follow")
    if no_history:
        argv.append("--no-history")
    return shlex.join(argv) if posix else subprocess.list2cmdline(argv)


def main() -> None:
    """Entry point."""
    # prog: under `python -m` argparse would otherwise print "__main__.py".
    parser = argparse.ArgumentParser(
        prog="jlv", description="JSON Logs Viewer"
    )
    parser.add_argument(
        "files",
        nargs="*",
        metavar="file",
        help=(
            "JSONL file(s) to view; several are merged by timestamp. "
            "'-' (or piping with no files) reads stdin"
        ),
    )
    parser.add_argument(
        "-f", "--follow", action="store_true", help="Follow mode"
    )
    parser.add_argument(
        "--serve", action="store_true", help="Serve app in browser"
    )
    parser.add_argument(
        "--no-history",
        action="store_true",
        help="Don't read or save the search history file",
    )
    args = parser.parse_args()

    # A --serve browser session gets its files from the environment. Pop
    # it, so programs started from the app don't inherit it.
    served = os.environ.pop(SERVE_FILE_ENV, None)
    files = args.files or (json.loads(served) if served else [])
    # Piped input: "-" among the files, or piping with no files at all
    # (`kubectl logs pod | jlv`). Not guessed for --serve, which may run
    # without a terminal (a service): there only an explicit "-" counts.
    explicit_stdin = STDIN_ARG in files
    if explicit_stdin and args.serve:
        sys.exit(
            "jlv: --serve can't read piped input; save it to a file first"
        )
    if explicit_stdin and not stdin_is_piped():
        sys.exit("jlv: '-' reads piped input, but nothing is piped in")
    wants_stdin = explicit_stdin or (
        not files and not args.serve and stdin_is_piped()
    )

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

        if args.files:
            # A JSON list: file names can contain any separator character.
            os.environ[SERVE_FILE_ENV] = json.dumps(args.files)
        Server(
            build_serve_command(
                follow=args.follow, no_history=args.no_history
            ),
            # Shown on the served page; it defaults to the command string.
            title=f"jlv {Path(args.files[0]).name}" if args.files else "jlv",
        ).serve()
        return

    follow = args.follow
    stdin_copy: StdinCopy | None = None
    if wants_stdin:
        try:
            stdin_copy = StdinCopy(fd=take_over_stdin())
        except OSError as error:
            sys.exit(f"jlv: can't read piped input: {error}")
        stdin_copy.start()
        files = [
            stdin_copy.path if file == STDIN_ARG else file for file in files
        ] or [stdin_copy.path]
        follow = True  # a pipe keeps delivering lines
    try:
        app = LogViewerApp(
            files=files,
            follow=follow,
            show_picker_on_start=not files,
            history_path=None if args.no_history else default_history_path(),
            stdin_path=stdin_copy.path if stdin_copy else None,
        )
        app.run()
    finally:
        if stdin_copy is not None:
            stdin_copy.close()


if __name__ == "__main__":
    main()
