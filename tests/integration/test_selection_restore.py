"""Cursor stays on the same line, or the nearest one, across filters."""

from __future__ import annotations

import pytest

from json_logs_viewer.app import LogViewerApp
from json_logs_viewer.models import LogEntry


def _logs(*, keep: set[int]) -> list[LogEntry]:
    """Lines 1..10; the ones in `keep` contain the word "keep"."""
    return [
        LogEntry(
            line_number=n, data={"n": n, "tag": "keep" if n in keep else "x"}
        )
        for n in range(1, 11)
    ]


async def _select_line_then_filter(
    *, app: LogViewerApp, pilot: object, line: int, query: str
) -> int:
    app.filter_query = ""
    await pilot.pause()  # type: ignore[attr-defined]
    app.selected_index = line - 1
    await pilot.pause()  # type: ignore[attr-defined]
    app.filter_query = query
    await pilot.pause()  # type: ignore[attr-defined]
    return app.filtered_logs[app.selected_index].line_number


@pytest.mark.asyncio
async def test_selected_line_kept_when_it_still_matches() -> None:
    app = LogViewerApp()
    async with app.run_test() as pilot:
        app.logs = _logs(keep={2, 5, 7})
        line = await _select_line_then_filter(
            app=app, pilot=pilot, line=5, query="tag:keep"
        )
        assert line == 5


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("keep", "selected", "expected"),
    [
        ({2, 7}, 5, 7),  # 7 is 2 lines away, 2 is 3 away
        ({3, 7}, 5, 3),  # tie: prefer the earlier line
        ({8, 9}, 1, 8),  # before every match
        ({1, 2}, 10, 2),  # after every match
    ],
)
async def test_moves_to_nearest_line_when_filtered_out(
    keep: set[int], selected: int, expected: int
) -> None:
    app = LogViewerApp()
    async with app.run_test() as pilot:
        app.logs = _logs(keep=keep)
        line = await _select_line_then_filter(
            app=app, pilot=pilot, line=selected, query="tag:keep"
        )
        assert line == expected


@pytest.mark.asyncio
async def test_nearest_uses_file_line_numbers_not_list_positions() -> None:
    """Gaps (skipped blank/invalid lines) count as distance."""
    entries = [
        LogEntry(line_number=n, data={"tag": tag})
        for n, tag in [(1, "keep"), (2, "x"), (3, "x"), (40, "keep")]
    ]
    app = LogViewerApp()
    async with app.run_test() as pilot:
        app.logs = entries
        app.selected_index = 2  # line 3: 2 lines from line 1, 37 from 40
        await pilot.pause()
        app.filter_query = "tag:keep"
        await pilot.pause()

        assert app.filtered_logs[app.selected_index].line_number == 1
