"""Clearing the view (x): hide what's loaded, keep the file."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from json_logs_viewer.app import LogViewerApp
from json_logs_viewer.modals.confirm_modal import ConfirmModal


@pytest.fixture
def log_file(tmp_path: Path) -> Path:
    path = tmp_path / "app.jsonl"
    path.write_text(
        "".join(json.dumps({"i": i}) + "\n" for i in range(5)), "utf-8"
    )
    return path


@pytest.mark.asyncio
@pytest.mark.parametrize("key", ["y", "enter"])
async def test_confirming_clears_the_view_not_the_file(
    log_file: Path, key: str
) -> None:
    before = log_file.read_text()
    app = LogViewerApp(file=str(log_file))
    async with app.run_test() as pilot:
        await pilot.pause()

        await pilot.press("x")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmModal)
        await pilot.press(key)
        await pilot.pause()

        assert not isinstance(app.screen, ConfirmModal)
        assert app.logs == []
        assert app.filtered_logs == []
        assert log_file.read_text() == before


@pytest.mark.asyncio
@pytest.mark.parametrize("key", ["n", "escape"])
async def test_cancelling_keeps_everything(log_file: Path, key: str) -> None:
    app = LogViewerApp(file=str(log_file))
    async with app.run_test() as pilot:
        await pilot.pause()

        await pilot.press("x", key)
        await pilot.pause()

        assert not isinstance(app.screen, ConfirmModal)
        assert len(app.logs) == 5


@pytest.mark.asyncio
async def test_follow_shows_only_new_lines_after_clear(log_file: Path) -> None:
    app = LogViewerApp(file=str(log_file), follow=True)
    async with app.run_test() as pilot:
        await pilot.pause()

        await pilot.press("x", "y")
        await pilot.pause()
        app._process_chunk(b'{"i": 5}\n{"i": 6}\n{"i": 7}\n')
        await pilot.pause()

        assert [log.data["i"] for log in app.logs] == [5, 6, 7]
        # Line numbers still refer to the file, not to the cleared view.
        assert [log.line_number for log in app.logs] == [6, 7, 8]
        # The cursor follows the new lines from the empty view.
        assert app.selected_index == 2


@pytest.mark.asyncio
async def test_nothing_to_clear(tmp_path: Path) -> None:
    empty = tmp_path / "empty.jsonl"
    empty.write_text("")
    app = LogViewerApp(file=str(empty))
    async with app.run_test() as pilot:
        await pilot.pause()

        await pilot.press("x")
        await pilot.pause()

        assert not isinstance(app.screen, ConfirmModal)
        messages = [n.message for n in app._notifications]
        assert any("Nothing to clear" in m for m in messages)


@pytest.mark.asyncio
async def test_cursor_follows_new_lines_in_an_empty_file(
    tmp_path: Path,
) -> None:
    """Same rule without a clear: starting empty counts as being at the end."""
    empty = tmp_path / "empty.jsonl"
    empty.write_text("")
    app = LogViewerApp(file=str(empty), follow=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.follow_mode

        app._process_chunk(b'{"i": 0}\n{"i": 1}\n{"i": 2}\n')
        await pilot.pause()

        assert app.selected_index == 2
