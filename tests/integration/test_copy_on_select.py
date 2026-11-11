"""Selecting text copies it to the clipboard once the selection settles."""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import TextArea
from textual.widgets.text_area import Selection

from json_logs_viewer.app import LogViewerApp
from json_logs_viewer.constants import SELECTION_COPY_DELAY
from json_logs_viewer.widgets.search_bar import SearchBar

SETTLE = SELECTION_COPY_DELAY + 0.3


@pytest.mark.asyncio
@pytest.mark.parametrize("open_key", ["enter", "question_mark"])
async def test_text_area_selection_is_copied_and_cleared(
    sample_jsonl_file: Path, open_key: str
) -> None:
    """The detail view (enter) and the help modal (?) copy a selection."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.press(open_key)
        text_area = app.screen.query_one(TextArea)
        text_area.selection = Selection((0, 0), (2, 0))
        expected = text_area.selected_text
        await pilot.pause(SETTLE)

        assert expected
        assert app.clipboard == expected
        assert text_area.selected_text == ""


@pytest.mark.asyncio
async def test_search_bar_keyboard_selection_is_copied_whole(
    sample_jsonl_file: Path,
) -> None:
    """Shift+arrow selection copies all of it, not one key behind."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.press("slash")
        search_bar = app.query_one(SearchBar)
        search_bar.value = "hello world"
        await pilot.press("home", *["shift+right"] * 5)
        await pilot.pause(SETTLE)

        assert app.clipboard == "hello"
        assert search_bar.selected_text == ""


@pytest.mark.asyncio
async def test_selection_cleared_before_delay_is_not_copied(
    sample_jsonl_file: Path,
) -> None:
    """Text the user deselected in time is not copied."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.press("question_mark")
        text_area = app.screen.query_one(TextArea)
        text_area.selection = Selection((0, 0), (2, 0))
        await pilot.pause()
        text_area.selection = Selection.cursor((0, 0))
        await pilot.pause(SETTLE)

        assert app.clipboard == ""
