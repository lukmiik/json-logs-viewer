"""Time comparisons and last:<duration> in the running app."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from json_logs_viewer.app import LogViewerApp
from json_logs_viewer.models import LogEntry
from json_logs_viewer.widgets.log_list import LogList


def _line(minute: int) -> str:
    return json.dumps({"timestamp": f"2024-01-15T10:{minute:02d}:00Z"}) + "\n"


@pytest.fixture
def log_file(tmp_path: Path) -> Path:
    path = tmp_path / "app.jsonl"
    path.write_text("".join(_line(minute) for minute in range(0, 60, 10)))
    return path


def _minutes(logs: list[LogEntry]) -> list[int]:
    return [int(log.data["timestamp"][14:16]) for log in logs]


@pytest.mark.asyncio
async def test_timestamp_range(log_file: Path) -> None:
    app = LogViewerApp(file=str(log_file))
    async with app.run_test() as pilot:
        await pilot.pause()
        app.filter_query = "timestamp>=2024-01-15T10:20 timestamp<10:50"
        await pilot.pause()
        # "10:50" alone is not a date: the query is rejected, all shown.
        assert len(app.filtered_logs) == 6

        app.filter_query = (
            "timestamp>=2024-01-15T10:20 timestamp<2024-01-15T10:50"
        )
        await pilot.pause()
        assert _minutes(app.filtered_logs) == [20, 30, 40]


@pytest.mark.asyncio
async def test_last_is_relative_to_the_newest_log(log_file: Path) -> None:
    app = LogViewerApp(file=str(log_file))
    async with app.run_test() as pilot:
        await pilot.pause()
        app.filter_query = "last:15m"
        await pilot.pause()
        assert _minutes(app.filtered_logs) == [40, 50]


@pytest.mark.asyncio
async def test_last_window_slides_in_follow_mode(log_file: Path) -> None:
    """New logs move the window, so older ones drop out of the view."""
    app = LogViewerApp(file=str(log_file))
    async with app.run_test() as pilot:
        await pilot.pause()
        app.filter_query = "last:15m"
        await pilot.pause()

        app._process_chunk(
            (json.dumps({"timestamp": "2024-01-15T11:10:00Z"}) + "\n").encode()
        )
        await pilot.pause()

        stamps = [log.data["timestamp"] for log in app.filtered_logs]
        # The window is now 10:55-11:10, so 10:50 dropped out.
        assert stamps == ["2024-01-15T11:10:00Z"]


@pytest.mark.asyncio
async def test_last_in_highlight_mode(log_file: Path) -> None:
    app = LogViewerApp(file=str(log_file))
    async with app.run_test() as pilot:
        await pilot.pause()
        app.filter_query = "last:15m"
        app.highlight_matches = True
        await pilot.pause()
        log_list = app.query_one("#logs", LogList)
        assert log_list._match_flags == [False] * 4 + [True, True]

        app._process_chunk(
            (json.dumps({"timestamp": "2024-01-15T11:10:00Z"}) + "\n").encode()
        )
        await pilot.pause()
        assert log_list._match_flags == [False] * 6 + [True]
