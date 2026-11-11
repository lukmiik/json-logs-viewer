"""Follow mode: "+N new lines" when the cursor isn't at the end."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from json_logs_viewer.app import LogViewerApp
from json_logs_viewer.widgets.log_list import LogList
from json_logs_viewer.widgets.new_lines_badge import NewLinesBadge


@pytest.fixture
def log_file(tmp_path: Path) -> Path:
    path = tmp_path / "app.jsonl"
    path.write_text(
        "".join(json.dumps({"level": "info", "i": i}) + "\n" for i in range(5))
    )
    return path


def _append(app: LogViewerApp, *levels: str) -> None:
    lines = "".join(json.dumps({"level": level}) + "\n" for level in levels)
    app._process_chunk(lines.encode())


def _badge(app: LogViewerApp) -> NewLinesBadge:
    return app.query_one(NewLinesBadge)


@pytest.mark.asyncio
async def test_no_badge_while_the_cursor_follows(log_file: Path) -> None:
    app = LogViewerApp(file=str(log_file), follow=True)
    async with app.run_test() as pilot:
        await pilot.pause()

        _append(app, "info", "info")
        await pilot.pause()

        assert app.selected_index == len(app.filtered_logs) - 1
        assert not _badge(app).display


@pytest.mark.asyncio
async def test_counts_lines_arriving_below_the_cursor(log_file: Path) -> None:
    app = LogViewerApp(file=str(log_file), follow=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("k", "k")
        cursor = app.selected_index
        list_region = app.query_one("#logs", LogList).region

        _append(app, "info")
        await pilot.pause()
        assert str(_badge(app).content) == "↓ 1 new line"

        _append(app, "info", "error")
        await pilot.pause()
        badge = _badge(app)
        assert badge.display
        assert str(badge.content) == "↓ 3 new lines"
        assert app.selected_index == cursor  # reading isn't interrupted
        # It floats: the list keeps its size.
        assert app.query_one("#logs", LogList).region == list_region


@pytest.mark.asyncio
async def test_only_lines_the_filter_shows_count(log_file: Path) -> None:
    app = LogViewerApp(file=str(log_file), follow=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.filter_query = "level:info"
        await pilot.pause()
        await pilot.press("g")

        _append(app, "error", "info", "error")
        await pilot.pause()

        assert str(_badge(app).content) == "↓ 1 new line"


@pytest.mark.asyncio
@pytest.mark.parametrize("how", ["G", "click", "walk"])
async def test_reaching_the_end_clears_it(log_file: Path, how: str) -> None:
    app = LogViewerApp(file=str(log_file), follow=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("k")
        _append(app, "info", "info")
        await pilot.pause()
        assert _badge(app).display

        if how == "G":
            await pilot.press("G")
        elif how == "click":
            await pilot.click(NewLinesBadge)
        else:
            await pilot.press("j", "j", "j")
        await pilot.pause()

        assert app.selected_index == len(app.filtered_logs) - 1
        assert not _badge(app).display


@pytest.mark.asyncio
async def test_new_lines_after_reaching_the_end_follow_again(
    log_file: Path,
) -> None:
    app = LogViewerApp(file=str(log_file), follow=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("k")
        _append(app, "info")
        await pilot.press("G")
        await pilot.pause()

        _append(app, "info")
        await pilot.pause()

        assert app.selected_index == len(app.filtered_logs) - 1
        assert not _badge(app).display
