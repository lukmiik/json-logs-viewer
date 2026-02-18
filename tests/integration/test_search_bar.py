"""Integration tests for SearchBar widget."""

from pathlib import Path

import pytest

from json_logs_viewer.app import LogViewerApp
from json_logs_viewer.widgets import search_bar as search_bar_module
from json_logs_viewer.widgets.log_list import LogList
from json_logs_viewer.widgets.search_bar import SearchBar


@pytest.mark.asyncio
async def test_submit_sets_filter_query(sample_jsonl_file: Path) -> None:
    """Test that submitting a query sets app.filter_query."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        app.action_focus_search()
        await pilot.pause()

        await pilot.press(*list("error"))
        await pilot.press("enter")
        await pilot.pause()

        assert app.filter_query == "error"


@pytest.mark.asyncio
async def test_search_bar_hidden_by_default_without_query(
    sample_jsonl_file: Path,
) -> None:
    """Test that search bar starts hidden when there is no active query."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()
        search_bar = app.query_one("#search", SearchBar)
        assert search_bar.display is False


@pytest.mark.asyncio
async def test_slash_shows_search_bar_and_focuses_it(
    sample_jsonl_file: Path,
) -> None:
    """Test that '/' reveals hidden search bar and focuses it."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        await pilot.press("/")
        await pilot.pause()

        search_bar = app.query_one("#search", SearchBar)
        assert search_bar.display is True
        assert search_bar.has_focus


@pytest.mark.asyncio
async def test_focusing_log_list_hides_empty_search_bar(
    sample_jsonl_file: Path,
) -> None:
    """Test that empty search bar hides after focus leaves it."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        app.action_focus_search()
        await pilot.pause()

        search_bar = app.query_one("#search", SearchBar)
        assert search_bar.display is True
        assert search_bar.has_focus

        search_bar.action_focus_log_list()
        await pilot.pause()

        log_list = app.query_one("#logs", LogList)
        assert log_list.has_focus
        assert search_bar.display is False


@pytest.mark.asyncio
async def test_submit_keeps_input(sample_jsonl_file: Path) -> None:
    """Test that input is preserved after submit so the user can refine it."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        search_bar = app.query_one("#search", SearchBar)
        app.action_focus_search()
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
        app.action_focus_search()
        await pilot.pause()

        await pilot.press(*list("first"))
        await pilot.press("enter")
        await pilot.pause()

        search_bar.value = "second"
        app.action_focus_search()
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
        app.action_focus_search()
        await pilot.pause()

        await pilot.press(*list("same"))
        await pilot.press("enter")
        await pilot.pause()

        await pilot.press("enter")
        await pilot.pause()

        assert app.search_history == ["same"]


@pytest.mark.asyncio
async def test_search_history_limit_15(
    sample_jsonl_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that search history is limited to SEARCH_HISTORY_LIMIT items."""
    monkeypatch.setattr(search_bar_module, "SEARCH_HISTORY_LIMIT", 5)
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        search_bar = app.query_one("#search", SearchBar)
        app.action_focus_search()
        await pilot.pause()

        for i in range(7):
            search_bar.value = f"query{i}"
            app.action_focus_search()
            await pilot.press("enter")
            await pilot.pause()

        assert len(app.search_history) == 5


@pytest.mark.asyncio
async def test_empty_submit_clears_filter(sample_jsonl_file: Path) -> None:
    """Test that submitting empty input clears an active filter."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        search_bar = app.query_one("#search", SearchBar)
        app.action_focus_search()
        await pilot.pause()

        await pilot.press(*list("error"))
        await pilot.press("enter")
        await pilot.pause()
        assert app.filter_query == "error"

        search_bar.value = ""
        app.action_focus_search()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert app.filter_query == ""
        assert app.search_history == ["error"]
        assert search_bar.display is False


@pytest.mark.asyncio
async def test_enter_focuses_log_list(sample_jsonl_file: Path) -> None:
    """Test that pressing Enter in search bar focuses the log list."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        search_bar = app.query_one("#search", SearchBar)
        app.action_focus_search()
        await pilot.pause()
        assert search_bar.has_focus

        await pilot.press(*list("error"))
        await pilot.press("enter")
        await pilot.pause()

        log_list = app.query_one("#logs", LogList)
        assert log_list.has_focus


@pytest.mark.asyncio
async def test_submit_shows_toast_when_query_has_no_matches(
    sample_jsonl_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test submitting an unmatched query shows a warning toast."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    captured_notifications: list[tuple[str, str | None]] = []

    def mock_notify(
        message: str, *, severity: str | None = None, **_: object
    ) -> None:
        captured_notifications.append((message, severity))

    monkeypatch.setattr(app, "notify", mock_notify)

    async with app.run_test() as pilot:
        app.action_focus_search()
        await pilot.pause()

        await pilot.press(*list("message:does-not-exist"))
        await pilot.press("enter")
        await pilot.pause()

    assert ("No logs match the query", "warning") in captured_notifications


@pytest.mark.asyncio
async def test_escape_focuses_log_list(sample_jsonl_file: Path) -> None:
    """Test that pressing Escape in search bar focuses the log list."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        search_bar = app.query_one("#search", SearchBar)
        app.action_focus_search()
        await pilot.pause()
        assert search_bar.has_focus

        await pilot.press("escape")
        await pilot.pause()

        log_list = app.query_one("#logs", LogList)
        assert log_list.has_focus
