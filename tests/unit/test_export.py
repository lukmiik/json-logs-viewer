"""Exporting log lines to a JSONL file."""

from __future__ import annotations

from pathlib import Path

import pytest

from json_logs_viewer.export import default_export_path, write_jsonl
from json_logs_viewer.models import LogEntry


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("/var/log/app.jsonl", "/var/log/app.filtered.jsonl"),
        ("/var/log/app.log", "/var/log/app.filtered.jsonl"),
        ("/var/log/app", "/var/log/app.filtered.jsonl"),
        ("logs/app.json", "logs/app.filtered.jsonl"),
        (None, "export.jsonl"),
    ],
)
def test_default_export_path(source: str | None, expected: str) -> None:
    path = default_export_path(source=Path(source) if source else None)
    assert path == Path(expected)


def _entries(*lines: str) -> list[LogEntry]:
    return [
        LogEntry(line_number=i, data={}, raw_json=line)
        for i, line in enumerate(lines, 1)
    ]


def test_write_jsonl_writes_raw_lines(tmp_path: Path) -> None:
    target = tmp_path / "out.jsonl"
    write_jsonl(path=target, entries=_entries('{"a": 1}', '{"b": "ż"}'))

    assert target.read_text(encoding="utf-8") == '{"a": 1}\n{"b": "ż"}\n'
    assert list(tmp_path.iterdir()) == [target]  # no temp file left over


def test_write_jsonl_replaces_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "out.jsonl"
    target.write_text("old content\n")

    write_jsonl(path=target, entries=_entries('{"new": true}'))

    assert target.read_text() == '{"new": true}\n'


def test_write_jsonl_error_leaves_nothing_behind(tmp_path: Path) -> None:
    target = tmp_path / "missing-dir" / "out.jsonl"

    with pytest.raises(OSError):
        write_jsonl(path=target, entries=_entries('{"a": 1}'))

    assert list(tmp_path.iterdir()) == []
