"""Writing the logs a query matches to a JSONL file."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from json_logs_viewer.atomic_file import atomic_open

if TYPE_CHECKING:
    from json_logs_viewer.models import LogEntry


def default_export_path(*, source: Path | None) -> Path:
    """`<name>.filtered.jsonl` beside the open file, else `export.jsonl`."""
    if source is None:
        return Path("export.jsonl")
    return source.with_name(f"{source.stem}.filtered.jsonl")


def write_jsonl(*, path: Path, entries: list[LogEntry]) -> None:
    """Write each entry's original line to `path`, atomically.

    A failure halfway never leaves a half-written or truncated file.

    Raises:
        OSError: The directory doesn't exist or can't be written.
    """
    with atomic_open(path=path) as file:
        for entry in entries:
            file.write(entry.raw_json)
            file.write("\n")
