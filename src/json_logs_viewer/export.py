"""Writing the logs a query matches to a JSONL file."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from json_logs_viewer.models import LogEntry


def default_export_path(*, source: Path | None) -> Path:
    """`<name>.filtered.jsonl` beside the open file, else `export.jsonl`."""
    if source is None:
        return Path("export.jsonl")
    return source.with_name(f"{source.stem}.filtered.jsonl")


def write_jsonl(*, path: Path, entries: list[LogEntry]) -> None:
    """Write each entry's original line to `path`, atomically.

    The lines go to a temporary file in the same directory, which then
    replaces `path` in one step (`os.replace`), so a failure halfway never
    leaves a half-written or truncated file.

    Raises:
        OSError: The directory doesn't exist or can't be written.
    """
    fd, tmp_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as tmp:
            for entry in entries:
                tmp.write(entry.raw_json)
                tmp.write("\n")
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise
