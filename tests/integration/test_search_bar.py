"""Integration tests for SearchBar widget."""

from pathlib import Path

import pytest
from textual import events

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


@pytest.mark.asyncio
async def test_resubmitting_query_moves_it_to_end(
    sample_jsonl_file: Path,
) -> None:
    """A repeated query is moved to the most recent slot, not duplicated."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        search_bar = app.query_one("#search", SearchBar)
        for query in ("error", "info", "error"):
            search_bar.value = query
            app.action_focus_search()
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()

        assert app.search_history == ["info", "error"]


@pytest.mark.asyncio
async def test_submit_notifies_search_history_watchers(
    sample_jsonl_file: Path,
) -> None:
    """search_history must be reassigned so reactive watchers fire."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    seen: list[list[str]] = []
    async with app.run_test() as pilot:
        app.watch(
            app,
            "search_history",
            lambda history: seen.append(list(history)),
            init=False,
        )
        search_bar = app.query_one("#search", SearchBar)
        search_bar.value = "error"
        app.action_focus_search()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert seen == [["error"]]


async def _submit(*, app: LogViewerApp, pilot: object, query: str) -> None:
    app.action_focus_search()
    await pilot.pause()  # type: ignore[attr-defined]
    app.query_one("#search", SearchBar).value = query
    await pilot.press("enter")  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_submit_hides_search_bar_but_keeps_filter(
    sample_jsonl_file: Path,
) -> None:
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await _submit(app=app, pilot=pilot, query="level:error")

        search_bar = app.query_one("#search", SearchBar)
        assert search_bar.display is False
        assert app.filter_query == "level:error"
        assert app.query_one("#logs", LogList).has_focus


@pytest.mark.asyncio
async def test_slash_reopens_search_bar_with_active_query(
    sample_jsonl_file: Path,
) -> None:
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await _submit(app=app, pilot=pilot, query="level:error")

        await pilot.press("/")
        await pilot.pause()

        search_bar = app.query_one("#search", SearchBar)
        assert search_bar.display is True
        assert search_bar.has_focus
        assert search_bar.value == "level:error"


@pytest.mark.asyncio
async def test_escape_hides_search_bar_and_keeps_filter(
    sample_jsonl_file: Path,
) -> None:
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await _submit(app=app, pilot=pilot, query="level:error")
        await pilot.press("/")
        await pilot.pause()

        await pilot.press("escape")
        await pilot.pause()

        assert app.query_one("#search", SearchBar).display is False
        assert app.filter_query == "level:error"


@pytest.mark.asyncio
async def test_search_bar_visible_again_when_terminal_regains_focus(
    sample_jsonl_file: Path,
) -> None:
    """Focus returning to the input must never leave it invisible."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.press("/", *"lev")
        await pilot.pause()

        app.post_message(events.AppBlur())
        await pilot.pause()
        app.post_message(events.AppFocus())
        await pilot.pause()

        search_bar = app.query_one("#search", SearchBar)
        assert search_bar.has_focus
        assert search_bar.display is True
        assert search_bar.value == "lev"


@pytest.mark.asyncio
@pytest.mark.parametrize("cursor_keys", [["g"], ["g", *"j" * 12], ["G"]])
async def test_opening_search_bar_does_not_move_the_list(
    tmp_path: Path, cursor_keys: list[str]
) -> None:
    """The bar floats over the list (own layer), so no line shifts.

    Docked in the layout, it pushed the list down and shrank it, and the
    cursor-margin scroll then moved lines on open or on close.
    """
    log_file = tmp_path / "app.jsonl"
    log_file.write_text("".join(f'{{"i": {i}}}\n' for i in range(100)))
    app = LogViewerApp(file=str(log_file))
    async with app.run_test(size=(80, 30)) as pilot:
        await pilot.pause()
        log_list = app.query_one("#logs", LogList)
        await pilot.press(*cursor_keys)
        await pilot.pause()

        def layout() -> tuple[object, float]:
            return log_list.region, log_list.scroll_y

        closed = layout()
        await pilot.press("slash")
        await pilot.pause()
        assert app.query_one(SearchBar).display
        assert layout() == closed

        await pilot.press("escape")
        await pilot.pause()
        assert layout() == closed
