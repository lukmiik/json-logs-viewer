"""Reading gzip, bzip2 and xz compressed log files."""

from __future__ import annotations

import bz2
import gzip
import lzma
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from json_logs_viewer.modals.file_picker_modal import is_log_file
from json_logs_viewer.sources import read_source

CONTENT = b'{"a": 1}\nnot json\n\n{"a": 2, "s": "\xc5\xbc"}\n'
OPENERS: dict[str, Callable[..., Any]] = {
    ".gz": gzip.open,
    ".bz2": bz2.open,
    ".xz": lzma.open,
}


@pytest.mark.parametrize("suffix", list(OPENERS))
def test_reads_compressed_files(tmp_path: Path, suffix: str) -> None:
    path = tmp_path / f"app.jsonl{suffix}"
    with OPENERS[suffix](path, "wb") as file:
        file.write(CONTENT)

    logs, source = read_source(path=str(path))

    assert [log.line_number for log in logs] == [1, 4]
    assert logs[1].data == {"a": 2, "s": "ż"}
    assert source.compressed


def test_detected_by_content_not_name(tmp_path: Path) -> None:
    path = tmp_path / "rotated-without-suffix"
    with gzip.open(path, "wb") as file:
        file.write(CONTENT)

    logs, source = read_source(path=str(path))

    assert len(logs) == 2
    assert source.compressed


def test_plain_files_are_not_compressed(tmp_path: Path) -> None:
    path = tmp_path / "app.jsonl"
    path.write_bytes(CONTENT)
    assert not read_source(path=str(path))[1].compressed


def test_damaged_file_is_an_error(tmp_path: Path) -> None:
    path = tmp_path / "broken.jsonl.gz"
    path.write_bytes(gzip.compress(CONTENT)[:-10])  # cut off
    with pytest.raises((OSError, EOFError)):
        read_source(path=str(path))


@pytest.mark.parametrize(
    ("name", "shown"),
    [
        ("app.jsonl", True),
        ("app.json", True),
        ("app.jsonl.gz", True),
        ("app.jsonl.1.gz", True),  # logrotate
        ("app.json.bz2", True),
        ("app.jsonl.xz", True),
        ("photo.gz", False),
        ("notes.txt", False),
    ],
)
def test_picker_shows_compressed_logs(name: str, shown: bool) -> None:
    assert is_log_file(Path(name)) is shown
