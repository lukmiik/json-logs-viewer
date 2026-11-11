"""The column header row above the log list."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from json_logs_viewer.app import LogViewerApp
from json_logs_viewer.widgets.column_header import ColumnHeader
from json_logs_viewer.widgets.log_list import LogList


def _text(widget: ColumnHeader | LogList, y: int = 0) -> str:
    return "".join(segment.text for segment in widget.render_line(y))


@pytest.fixture
def log_file(tmp_path: Path) -> Path:
    path = tmp_path / "app.jsonl"
    path.write_text(
        "".join(
            json.dumps(
                {"level": "INFO", "http": {"status": 200 + i}, "msg": "x" * 90}
            )
            + "\n"
            for i in range(5)
        )
    )
    return path


@pytest.mark.asyncio
async def test_header_hidden_without_columns(log_file: Path) -> None:
    app = LogViewerApp(file=str(log_file))
    async with app.run_test(size=(80, 12)) as pilot:
        await pilot.pause()
        assert not app.query_one(ColumnHeader).display


@pytest.mark.asyncio
async def test_header_names_line_up_with_column_values(log_file: Path) -> None:
    app = LogViewerApp(file=str(log_file))
    async with app.run_test(size=(80, 12)) as pilot:
        await pilot.pause()
        app.columns = ["level", "http.status"]
        await pilot.pause()
        header = app.query_one(ColumnHeader)
        log_list = app.query_one("#logs", LogList)

        assert header.display
        header_text = _text(header)
        row_text = _text(log_list)
        assert header_text.startswith("level | http.status | ")
        assert row_text.startswith("INFO  | 20")
        # Each separator sits in the same column as in the rows.
        assert header_text.index("| ") == row_text.index("| ")

        app.columns = []
        await pilot.pause()
        assert not header.display


@pytest.mark.asyncio
async def test_header_scrolls_sideways_with_the_list(log_file: Path) -> None:
    app = LogViewerApp(file=str(log_file))
    async with app.run_test(size=(80, 12)) as pilot:
        await pilot.pause()
        app.columns = ["level", "http.status"]
        await pilot.pause()
        header = app.query_one(ColumnHeader)
        log_list = app.query_one("#logs", LogList)

        log_list.scroll_to(x=8, animate=False)
        await pilot.pause()

        assert log_list.scroll_offset.x == 8
        assert _text(header).startswith("http.status | ")
        assert _text(log_list)[3:].startswith("         | ")


@pytest.mark.asyncio
async def test_cursor_keeps_its_margin_when_the_header_appears(
    tmp_path: Path,
) -> None:
    """Showing the header makes the list a row shorter; the view follows.

    Before, the cursor was scrolled into view while the list still had its
    old height, so the header took the cursor's bottom margin.
    """
    path = tmp_path / "app.jsonl"
    path.write_text(
        "".join(
            json.dumps({"level": "INFO", "i": i}) + "\n" for i in range(100)
        )
    )
    app = LogViewerApp(file=str(path))
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        log_list = app.query_one("#logs", LogList)
        await pilot.press("g", *"j" * 40)
        await pilot.pause()

        def bottom_margin() -> int:
            bottom = int(log_list.scroll_offset.y) + log_list.size.height - 1
            return bottom - log_list._get_cursor_row()

        assert bottom_margin() == LogList.SCROLLOFF

        await pilot.press("c", "space", "enter")
        await pilot.pause()

        assert app.columns
        assert bottom_margin() >= LogList.SCROLLOFF


@pytest.mark.asyncio
async def test_applying_columns_scrolls_back_to_show_them(
    log_file: Path,
) -> None:
    """After scrolling right, applying columns returns to the left edge.

    Columns are drawn at the start of each line, so they'd be off-screen.
    """
    app = LogViewerApp(file=str(log_file))
    async with app.run_test(size=(80, 12)) as pilot:
        await pilot.pause()
        log_list = app.query_one("#logs", LogList)
        await pilot.press(*"l" * 15)
        await pilot.pause()
        assert log_list.scroll_offset.x > 0

        await pilot.press("c", "space", "enter")
        await pilot.pause()

        assert app.columns
        assert log_list.scroll_offset.x == 0
        assert _text(app.query_one(ColumnHeader)).startswith(app.columns[0])


@pytest.mark.asyncio
async def test_detected_columns_render_whatever_the_field_name(
    tmp_path: Path,
) -> None:
    path = tmp_path / "app.jsonl"
    path.write_text('{"severity": "WARN", "msg": "disk almost full"}\n')
    app = LogViewerApp(file=str(path))
    async with app.run_test(size=(100, 10)) as pilot:
        await pilot.pause()
        app.columns = ["@level", "@message"]
        await pilot.pause()

        header = _text(app.query_one(ColumnHeader))
        row = _text(app.query_one("#logs", LogList))
        assert header.startswith("@level | @message         | ")
        assert row.startswith("WARN   | disk almost full | ")
