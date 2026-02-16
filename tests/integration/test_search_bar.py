"""Integration tests for SearchBar widget."""

from pathlib import Path

import pytest

from json_logs_viewer.app import LogViewerApp
from json_logs_viewer.constants import SEARCH_HISTORY_LIMIT
from json_logs_viewer.widgets.log_list import LogList
from json_logs_viewer.widgets.search_bar import SearchBar


@pytest.mark.asyncio
async def test_submit_sets_filter_query(sample_jsonl_file: Path) -> None:
    """Test that submitting a query sets app.filter_query."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        search_bar = app.query_one("#search", SearchBar)
        search_bar.focus()
        await pilot.pause()

        await pilot.press(*list("error"))
        await pilot.press("enter")
        await pilot.pause()

        assert app.filter_query == "error"


@pytest.mark.asyncio
async def test_submit_keeps_input(sample_jsonl_file: Path) -> None:
    """Test that input is preserved after submit so the user can refine it."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        search_bar = app.query_one("#search", SearchBar)
        search_bar.focus()
        await pilot.pause()

        await pilot.press(*list("query"))
        await pilot.press("enter")
        await pilot.pause()

        assert search_bar.value == "query"


@pytest.mark.asyncio
async def test_submit_adds_to_search_history(sample_jsonl_file: Path) -> None:
    """Test that submitting a query appends to search_history."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        search_bar = app.query_one("#search", SearchBar)
        search_bar.focus()
        await pilot.pause()

        await pilot.press(*list("first"))
        await pilot.press("enter")
        await pilot.pause()

        search_bar.value = "second"
        search_bar.focus()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert app.search_history == ["first", "second"]


@pytest.mark.asyncio
async def test_submit_deduplicates_consecutive_history(
    sample_jsonl_file: Path,
) -> None:
    """Test that duplicate consecutive queries are not added to history."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        search_bar = app.query_one("#search", SearchBar)
        search_bar.focus()
        await pilot.pause()

        await pilot.press(*list("same"))
        await pilot.press("enter")
        await pilot.pause()

        await pilot.press("enter")
        await pilot.pause()

        assert app.search_history == ["same"]


@pytest.mark.asyncio
async def test_search_history_limit_15(sample_jsonl_file: Path) -> None:
    """Test that search history is limited to 15 items."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        search_bar = app.query_one("#search", SearchBar)
        search_bar.focus()
        await pilot.pause()

        for i in range(SEARCH_HISTORY_LIMIT + 5):
            search_bar.value = f"query{i}"
            search_bar.focus()
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()

        assert len(app.search_history) == SEARCH_HISTORY_LIMIT


@pytest.mark.asyncio
async def test_empty_submit_clears_filter(sample_jsonl_file: Path) -> None:
    """Test that submitting empty input clears an active filter."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        search_bar = app.query_one("#search", SearchBar)
        search_bar.focus()
        await pilot.pause()

        await pilot.press(*list("error"))
        await pilot.press("enter")
        await pilot.pause()
        assert app.filter_query == "error"

        search_bar.value = ""
        search_bar.focus()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert app.filter_query == ""
        assert app.search_history == ["error"]


@pytest.mark.asyncio
async def test_enter_focuses_log_list(sample_jsonl_file: Path) -> None:
    """Test that pressing Enter in search bar focuses the log list."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        search_bar = app.query_one("#search", SearchBar)
        search_bar.focus()
        await pilot.pause()
        assert search_bar.has_focus

        await pilot.press(*list("error"))
        await pilot.press("enter")
        await pilot.pause()

        log_list = app.query_one("#logs", LogList)
        assert log_list.has_focus


@pytest.mark.asyncio
async def test_escape_focuses_log_list(sample_jsonl_file: Path) -> None:
    """Test that pressing Escape in search bar focuses the log list."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        search_bar = app.query_one("#search", SearchBar)
        search_bar.focus()
        await pilot.pause()
        assert search_bar.has_focus

        await pilot.press("escape")
        await pilot.pause()

        log_list = app.query_one("#logs", LogList)
        assert log_list.has_focus
