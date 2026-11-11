"""Reading log files and merging several into one timeline."""

from __future__ import annotations

from pathlib import Path

from json_logs_viewer.models import LogEntry
from json_logs_viewer.sources import merge_by_time, read_source


def _log(name: str, time: str | None = None) -> LogEntry:
    data: dict[str, object] = {"name": name}
    if time is not None:
        data["timestamp"] = f"2024-01-15T10:{time}Z"
    return LogEntry(line_number=1, data=data)


def _names(logs: list[LogEntry]) -> list[str]:
    return [log.data["name"] for log in logs]


def test_interleaves_files_by_timestamp() -> None:
    api = [_log("api1", "00:01"), _log("api2", "00:05")]
    worker = [_log("w1", "00:02"), _log("w2", "00:03"), _log("w3", "00:09")]

    merged = merge_by_time(files=[api, worker])

    assert _names(merged) == ["api1", "w1", "w2", "api2", "w3"]


def test_line_without_timestamp_stays_after_its_previous_line() -> None:
    api = [_log("api1", "00:01"), _log("api-trace"), _log("api2", "00:05")]
    worker = [_log("w1", "00:02")]

    merged = merge_by_time(files=[api, worker])

    assert _names(merged) == ["api1", "api-trace", "w1", "api2"]


def test_each_file_keeps_its_own_order_even_if_unsorted() -> None:
    api = [_log("late", "00:09"), _log("early", "00:01")]
    worker = [_log("w", "00:05")]

    merged = merge_by_time(files=[api, worker])

    assert _names(merged).index("late") < _names(merged).index("early")


def test_ties_keep_the_order_files_were_given() -> None:
    merged = merge_by_time(files=[[_log("a", "00:01")], [_log("b", "00:01")]])
    assert _names(merged) == ["a", "b"]


def test_mixed_naive_and_aware_timestamps() -> None:
    naive = LogEntry(
        line_number=1, data={"name": "n", "ts": "2024-01-15T10:00"}
    )
    aware = _log("z", "00:30")
    assert _names(merge_by_time(files=[[aware], [naive]])) == ["n", "z"]


def test_read_source_tags_lines_and_positions_follow(tmp_path: Path) -> None:
    path = tmp_path / "app.jsonl"
    path.write_text('{"a": 1}\nnot json\n{"a": 2}\n')

    logs, source = read_source(path=str(path))

    assert [log.line_number for log in logs] == [1, 3]
    assert {log.source for log in logs} == {str(path)}
    assert (source.offset, source.line_count) == (path.stat().st_size, 3)
