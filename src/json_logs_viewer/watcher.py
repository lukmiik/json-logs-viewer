"""File watcher for real-time log file tailing."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from json_logs_viewer.parser import IncrementalParser, LogParser, SkippedLine

if TYPE_CHECKING:
    from json_logs_viewer.models import LogEntry


@dataclass
class FileStats:
    """Statistics about the watched file."""

    file_path: Path
    file_size: int = 0
    last_modified: float = 0.0
    inode: int | None = None
    is_tracked: bool = False


@dataclass
class WatchResult:
    """Result of a watch check operation."""

    new_entries: list[LogEntry] = field(default_factory=list)
    skipped_lines: list[SkippedLine] = field(default_factory=list)
    file_rotated: bool = False
    file_removed: bool = False
    stats: FileStats | None = None


class FileWatcher:
    """Watches a log file for changes and provides incremental updates.

    Handles file rotation, truncation, and provides batched updates
    suitable for UI consumption in a follow mode context.
    """

    def __init__(
        self,
        *,
        file_path: Path,
        batch_size: int = 100,
        poll_interval: float = 0.1,
    ) -> None:
        """Initialize the file watcher.

        Args:
            file_path: Path to the log file to watch.
            batch_size: Maximum number of entries to return in a single batch.
            poll_interval: Minimum time between file checks in seconds.
        """
        self._file_path = file_path
        self._batch_size = batch_size
        self._poll_interval = poll_interval
        self._last_poll_time: float = 0.0
        self._parser = IncrementalParser(file_path=file_path)
        self._current_stats: FileStats | None = None
        self._log_parser = LogParser()

    @property
    def file_path(self) -> Path:
        """Return the watched file path."""
        return self._file_path

    @property
    def is_following(self) -> bool:
        """Return True if the file is being tracked."""
        return (
            self._current_stats is not None and self._current_stats.is_tracked
        )

    def start_watching(self) -> FileStats | None:
        """Start watching the file and capture initial state.

        Returns:
            FileStats if the file exists and is watchable, None otherwise.
        """
        if not self._file_path.exists():
            return None

        try:
            stat = self._file_path.stat()
            self._current_stats = FileStats(
                file_path=self._file_path,
                file_size=stat.st_size,
                last_modified=stat.st_mtime,
                inode=stat.st_ino,
                is_tracked=True,
            )
            # Initialize parser at current end of file for follow mode
            # (don't parse existing content, only new lines)
            # Count existing lines to set correct line offset
            existing_lines = 0
            if stat.st_size > 0:
                with self._file_path.open("r", encoding="utf-8") as f:
                    existing_lines = sum(1 for _ in f)

            self._parser = IncrementalParser(
                file_path=self._file_path,
                last_position=stat.st_size,
                line_offset=existing_lines,
            )
            return self._current_stats
        except (OSError, PermissionError):
            return None

    def stop_watching(self) -> None:
        """Stop watching the file."""
        self._current_stats = None
        self._parser = IncrementalParser(file_path=self._file_path)

    def check_for_updates(self) -> WatchResult:
        """Check for new lines and return any updates.

        This method respects the poll_interval to avoid excessive I/O.
        If called more frequently than poll_interval, it returns empty results.

        Returns:
            WatchResult containing any new entries, skipped lines,
            and status flags.
        """
        current_time = time.time()
        if current_time - self._last_poll_time < self._poll_interval:
            return WatchResult()

        self._last_poll_time = current_time

        # Check if file still exists
        if not self._file_path.exists():
            if self._current_stats is not None:
                self._current_stats.is_tracked = False
                # Reset parser position so we start fresh if file reappears
                self._parser = IncrementalParser(file_path=self._file_path)
                return WatchResult(
                    file_removed=True,
                    stats=self._current_stats,
                )
            return WatchResult()

        try:
            stat = self._file_path.stat()
        except (OSError, PermissionError):
            return WatchResult()

        # Check for file rotation (different inode or was previously untracked)
        is_rotated = (
            self._current_stats is not None
            and self._current_stats.inode is not None
            and stat.st_ino != self._current_stats.inode
        )
        was_untracked = (
            self._current_stats is not None
            and not self._current_stats.is_tracked
        )

        if is_rotated or was_untracked:
            # File was rotated or reappeared after removal -
            # reset and start from beginning
            self._current_stats = FileStats(
                file_path=self._file_path,
                file_size=stat.st_size,
                last_modified=stat.st_mtime,
                inode=stat.st_ino,
                is_tracked=True,
            )
            self._parser = IncrementalParser(
                file_path=self._file_path,
                last_position=0,
                line_offset=0,
            )

            # Read all content from the new file
            return self._read_all_content(file_rotated=True)

        # Check if file was truncated (size decreased - indicates replacement)
        # or if our read position is past the current file end
        # (file was replaced)
        is_truncated = (
            self._current_stats is not None
            and stat.st_size < self._current_stats.file_size
        )
        position_invalid = self._parser.last_position > stat.st_size

        if is_truncated or position_invalid:
            # File was truncated/rotated/replaced -
            # reset and read from beginning
            self._current_stats = FileStats(
                file_path=self._file_path,
                file_size=stat.st_size,
                last_modified=stat.st_mtime,
                inode=stat.st_ino,
                is_tracked=True,
            )
            self._parser = IncrementalParser(
                file_path=self._file_path,
                last_position=0,
                line_offset=0,
            )

            # Read all content from the replaced file
            return self._read_all_content(file_rotated=True)

        # Update stats
        if self._current_stats is None:
            self._current_stats = FileStats(
                file_path=self._file_path,
                file_size=stat.st_size,
                last_modified=stat.st_mtime,
                inode=stat.st_ino,
                is_tracked=True,
            )
        else:
            self._current_stats.file_size = stat.st_size
            self._current_stats.last_modified = stat.st_mtime
            self._current_stats.inode = stat.st_ino
            self._current_stats.is_tracked = True

        # Read new lines (up to batch_size)
        return self._read_incremental_content()

    def _read_incremental_content(self) -> WatchResult:
        """Read new content incrementally, respecting batch size."""
        all_entries: list[LogEntry] = []
        all_skipped: list[SkippedLine] = []

        while len(all_entries) < self._batch_size:
            entries, skipped, _ = self._parser.read_new_lines()

            if not entries and not skipped:
                break

            all_entries.extend(entries)
            all_skipped.extend(skipped)

            # Check if we've reached batch size
            remaining = self._batch_size - len(all_entries)
            if remaining <= 0:
                break

        # Trim to batch size if we exceeded it
        if len(all_entries) > self._batch_size:
            all_entries = all_entries[: self._batch_size]

        return WatchResult(
            new_entries=all_entries,
            skipped_lines=all_skipped,
            stats=self._current_stats,
        )

    def _read_all_content(self, *, file_rotated: bool = False) -> WatchResult:
        """Read all content from the file (used after rotation)."""
        entries: list[LogEntry] = []
        skipped: list[SkippedLine] = []

        try:
            with self._file_path.open("r", encoding="utf-8") as f:
                content = f.read()

            lines = content.splitlines()
            line_num = 0

            for raw_line in lines[: self._batch_size]:  # Respect batch size
                line_num += 1
                stripped = raw_line.strip()

                if not stripped:
                    continue

                try:
                    data = json.loads(stripped)
                except json.JSONDecodeError as e:
                    skipped.append(
                        SkippedLine(
                            line_number=line_num,
                            raw_line=raw_line[:200],
                            error_message=str(e),
                        )
                    )
                    continue

                if not isinstance(data, dict):
                    skipped.append(
                        SkippedLine(
                            line_number=line_num,
                            raw_line=raw_line[:200],
                            error_message="Parsed data is not a JSON object",
                        )
                    )
                    continue

                entry = self._log_parser._create_entry(
                    data=data, raw_line=raw_line, line_number=line_num
                )
                entries.append(entry)

            # Update parser state
            self._parser.last_position = self._file_path.stat().st_size
            self._parser.line_offset = line_num

        except (OSError, PermissionError):
            pass

        return WatchResult(
            new_entries=entries,
            skipped_lines=skipped,
            file_rotated=file_rotated,
            stats=self._current_stats,
        )

    def get_current_stats(self) -> FileStats | None:
        """Return current file statistics."""
        return self._current_stats


class BatchProcessor:
    """Processes file watcher updates with batching for UI efficiency."""

    def __init__(
        self,
        *,
        watcher: FileWatcher,
        on_entries: Callable[[list[LogEntry]], None] | None = None,
        on_skipped: Callable[[list[SkippedLine]], None] | None = None,
        on_rotation: Callable[[], None] | None = None,
        on_removal: Callable[[], None] | None = None,
    ) -> None:
        """Initialize the batch processor.

        Args:
            watcher: The FileWatcher instance to process updates from.
            on_entries: Callback for new log entries.
            on_skipped: Callback for skipped lines.
            on_rotation: Callback when file is rotated.
            on_removal: Callback when file is removed.
        """
        self._watcher = watcher
        self._on_entries = on_entries
        self._on_skipped = on_skipped
        self._on_rotation = on_rotation
        self._on_removal = on_removal

    def process_once(self) -> bool:
        """Process a single check cycle.

        Returns:
            True if any updates were processed, False otherwise.
        """
        result = self._watcher.check_for_updates()

        had_updates = False

        if result.file_removed and self._on_removal:
            self._on_removal()
            had_updates = True

        if result.file_rotated and self._on_rotation:
            self._on_rotation()
            had_updates = True

        if result.new_entries and self._on_entries:
            self._on_entries(result.new_entries)
            had_updates = True

        if result.skipped_lines and self._on_skipped:
            self._on_skipped(result.skipped_lines)
            had_updates = True

        return had_updates

    def get_watcher(self) -> FileWatcher:
        """Return the underlying file watcher."""
        return self._watcher
