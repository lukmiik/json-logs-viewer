"""Open log files: reading them, their follow state, and merging several."""

from __future__ import annotations

import bz2
import gzip
import heapq
import lzma
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BufferedIOBase
from pathlib import Path
from typing import IO, TYPE_CHECKING

from json_logs_viewer.log_reader import find_line_boundary, read_lines_backward
from json_logs_viewer.models import LogEntry, parse_log_line

if TYPE_CHECKING:
    from json_logs_viewer.log_watcher import WatcherBase


@dataclass(eq=False)
class SourceFile:
    """One open log file and its follow-mode state.

    eq=False: compared by identity, so follow messages can carry the
    source they belong to.

    Follow position invariant: `offset` is the byte where the first
    not-yet-consumed line starts and `line_count` the number of lines
    before it. `buffer` holds a partial line read past `offset` but not
    yet terminated.
    """

    path: str
    offset: int = 0
    line_count: int = 0
    buffer: bytes = b""
    watch_file: IO[bytes] | None = None
    watcher: WatcherBase | None = None
    # gzip/bzip2/xz: read whole once; it can't be followed.
    compressed: bool = False
    # The unterminated last line was counted as complete at load; the
    # writer's newline for it is still to come and must not count again.
    awaiting_newline: bool = False

    @property
    def name(self) -> str:
        return Path(self.path).name


# First bytes of each compressed format, and how to open it (each opens in
# binary read mode by default).
_COMPRESSED: list[tuple[bytes, Callable[[Path], BufferedIOBase]]] = [
    (b"\x1f\x8b", gzip.open),
    (b"BZh", bz2.open),
    (b"\xfd7zXZ\x00", lzma.open),
]


def _compressed_opener(path: Path) -> Callable[[Path], BufferedIOBase] | None:
    """How to decompress `path`, or None if it isn't compressed.

    Judged by its first bytes, not its name: rotated logs are often named
    app.jsonl.1.gz, or have no telling suffix at all.
    """
    with path.open("rb") as file:
        head = file.read(6)
    for magic, opener in _COMPRESSED:
        if head.startswith(magic):
            return opener
    return None


def _read_compressed(
    *, path: str, opener: Callable[[Path], BufferedIOBase]
) -> tuple[list[LogEntry], SourceFile]:
    """Decompress and parse in one forward pass.

    No temp file is needed: a compressed file isn't followed, so nothing is
    read from it later.
    """
    logs: list[LogEntry] = []
    with opener(Path(path)) as file:
        for line_number, raw_line in enumerate(file, 1):
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            log = parse_log_line(line=line, line_number=line_number)
            if log is not None:
                log.source = path
                logs.append(log)
    return logs, SourceFile(path=path, compressed=True)


def read_source(*, path: str) -> tuple[list[LogEntry], SourceFile]:
    """Parse every complete JSON line of `path`.

    Lines that aren't JSON objects are skipped. The returned SourceFile is
    positioned after what was read, so follow mode continues from there.
    gzip, bzip2 and xz files are decompressed (and can't be followed).

    Raises:
        OSError: The file can't be read (or is damaged).
        EOFError: A compressed file ends early (cut off).
    """
    file_path = Path(path)
    opener = _compressed_opener(file_path)
    if opener is not None:
        return _read_compressed(path=path, opener=opener)
    # Measure first and read exactly this many bytes, so anything appended
    # while loading is left for follow mode.
    size = file_path.stat().st_size
    logs: list[LogEntry] = []
    for line_number, line_text in read_lines_backward(
        filepath=file_path, size=size
    ):
        log = parse_log_line(line=line_text, line_number=line_number)
        if log is not None:
            log.source = path
            logs.append(log)
    logs.reverse()
    offset, line_count = find_line_boundary(filepath=file_path, size=size)
    awaiting_newline = False
    if offset < size and logs and logs[-1].line_number == line_count + 1:
        # The unterminated last line parsed as JSON, so it is complete (a
        # half-written JSON object can't parse): count it as consumed.
        offset, line_count = size, line_count + 1
        awaiting_newline = True
    return logs, SourceFile(
        path=path,
        offset=offset,
        line_count=line_count,
        awaiting_newline=awaiting_newline,
    )


_BEFORE_ANY_TIME = datetime.min.replace(tzinfo=UTC)


def _time_keys(*, logs: list[LogEntry]) -> Iterator[datetime]:
    """Each log's sort time: its timestamp, or the last one before it.

    A line without a timestamp stays right after its file's previous line.
    """
    last = _BEFORE_ANY_TIME
    for log in logs:
        if log.timestamp is not None:
            stamp = log.timestamp
            last = stamp if stamp.tzinfo else stamp.replace(tzinfo=UTC)
        yield last


def merge_by_time(*, files: list[list[LogEntry]]) -> list[LogEntry]:
    """Interleave several files' logs into one timeline.

    Each file keeps its own order (heapq.merge only interleaves); on equal
    times the file given first comes first.
    """
    if len(files) == 1:
        return files[0]
    keyed = [zip(_time_keys(logs=logs), logs, strict=True) for logs in files]
    return [log for _, log in heapq.merge(*keyed, key=lambda pair: pair[0])]
