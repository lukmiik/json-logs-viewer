"""Integration tests for HistoryModal."""

from pathlib import Path

import pytest
from textual.widgets import OptionList

from json_logs_viewer.app import LogViewerApp
from json_logs_viewer.modals.history_modal import HistoryModal
from json_logs_viewer.widgets.log_list import LogList
from json_logs_viewer.widgets.search_bar import SearchBar


async def _submit_query(
    *, app: LogViewerApp, pilot: object, query: str
) -> None:
    """Helper to submit a search query."""
    search_bar = app.query_one("#search", SearchBar)
    search_bar.value = query
    app.action_focus_search()
    await pilot.pause()  # type: ignore[attr-defined]
    await pilot.press("enter")  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_keybinding_opens_modal(sample_jsonl_file: Path) -> None:
    """Test that H opens the history modal."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        await pilot.press("H")
        await pilot.pause()

        assert isinstance(app.screen, HistoryModal)


@pytest.mark.asyncio
async def test_history_button_opens_modal(sample_jsonl_file: Path) -> None:
    """Test that clicking the History button opens the modal."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()

        await pilot.click("#status-history")
        await pilot.pause()

        assert isinstance(app.screen, HistoryModal)


@pytest.mark.asyncio
async def test_option_list_displays_search_history(
    sample_jsonl_file: Path,
) -> None:
    """Test that OptionList shows search history in reverse order."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await _submit_query(app=app, pilot=pilot, query="first")
        await _submit_query(app=app, pilot=pilot, query="second")
        await _submit_query(app=app, pilot=pilot, query="third")

        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        await pilot.press("H")
        await pilot.pause()

        assert isinstance(app.screen, HistoryModal)
        from textual.widgets import OptionList

        option_list = app.screen.query_one("#history-list", OptionList)
        assert option_list.option_count == 3
        assert str(option_list.get_option_at_index(0).prompt) == "third"
        assert str(option_list.get_option_at_index(1).prompt) == "second"
        assert str(option_list.get_option_at_index(2).prompt) == "first"


@pytest.mark.asyncio
async def test_selecting_query_applies_filter(
    sample_jsonl_file: Path,
) -> None:
    """Test that selecting a query from history applies it as a filter."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await _submit_query(app=app, pilot=pilot, query="level:ERROR")

        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        # Clear the current filter
        search_bar = app.query_one("#search", SearchBar)
        search_bar.value = ""
        app.action_focus_search()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        log_list.focus()
        await pilot.pause()

        await pilot.press("H")
        await pilot.pause()

        assert isinstance(app.screen, HistoryModal)

        # Select the first (and only) option
        await pilot.press("enter")
        await pilot.pause()

        assert not isinstance(app.screen, HistoryModal)
        assert app.filter_query == "level:ERROR"
        assert app.query_one("#search", SearchBar).value == "level:ERROR"


@pytest.mark.asyncio
async def test_escape_closes_without_selection(
    sample_jsonl_file: Path,
) -> None:
    """Test that Escape closes modal without changing the filter."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await _submit_query(app=app, pilot=pilot, query="first")

        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        original_query = app.filter_query

        await pilot.press("H")
        await pilot.pause()
        assert isinstance(app.screen, HistoryModal)

        await pilot.press("escape")
        await pilot.pause()

        assert not isinstance(app.screen, HistoryModal)
        assert app.filter_query == original_query


@pytest.mark.asyncio
async def test_empty_history_shows_message(sample_jsonl_file: Path) -> None:
    """Test that empty history shows a label instead of OptionList."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        await pilot.press("H")
        await pilot.pause()

        assert isinstance(app.screen, HistoryModal)
        from textual.widgets import Label

        empty_label = app.screen.query_one("#history-empty", Label)
        assert "No search history" in str(empty_label.render())


@pytest.mark.asyncio
async def test_modal_not_opened_when_already_open(
    sample_jsonl_file: Path,
) -> None:
    """Test that pressing H again doesn't push a second modal."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        await pilot.press("H")
        await pilot.pause()

        first_screen = app.screen
        assert isinstance(first_screen, HistoryModal)

        await pilot.press("H")
        await pilot.pause()

        assert app.screen is first_screen


@pytest.mark.asyncio
async def test_jk_navigates_option_list(
    sample_jsonl_file: Path,
) -> None:
    """Test that j/k moves the cursor in the OptionList."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await _submit_query(app=app, pilot=pilot, query="first")
        await _submit_query(app=app, pilot=pilot, query="second")
        await _submit_query(app=app, pilot=pilot, query="third")

        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        await pilot.press("H")
        await pilot.pause()

        assert isinstance(app.screen, HistoryModal)
        from textual.widgets import OptionList

        option_list = app.screen.query_one("#history-list", OptionList)
        # OptionList starts with highlighted index 0 ("third")
        assert option_list.highlighted == 0

        await pilot.press("j")
        await pilot.pause()
        assert option_list.highlighted == 1

        await pilot.press("j")
        await pilot.pause()
        assert option_list.highlighted == 2

        await pilot.press("k")
        await pilot.pause()
        assert option_list.highlighted == 1


@pytest.mark.asyncio
async def test_arrow_keys_navigate_option_list(
    sample_jsonl_file: Path,
) -> None:
    """Test that down/up arrow keys move the cursor in the OptionList."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await _submit_query(app=app, pilot=pilot, query="first")
        await _submit_query(app=app, pilot=pilot, query="second")
        await _submit_query(app=app, pilot=pilot, query="third")

        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        await pilot.press("H")
        await pilot.pause()

        assert isinstance(app.screen, HistoryModal)
        from textual.widgets import OptionList

        option_list = app.screen.query_one("#history-list", OptionList)
        assert option_list.highlighted == 0

        await pilot.press("down")
        await pilot.pause()
        assert option_list.highlighted == 1

        await pilot.press("down")
        await pilot.pause()
        assert option_list.highlighted == 2

        await pilot.press("up")
        await pilot.pause()
        assert option_list.highlighted == 1


@pytest.mark.asyncio
async def test_arrow_down_wraps_to_start(
    sample_jsonl_file: Path,
) -> None:
    """Test that down arrow wraps to first option from last."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await _submit_query(app=app, pilot=pilot, query="first")
        await _submit_query(app=app, pilot=pilot, query="second")
        await _submit_query(app=app, pilot=pilot, query="third")

        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        await pilot.press("H")
        await pilot.pause()

        assert isinstance(app.screen, HistoryModal)
        from textual.widgets import OptionList

        option_list = app.screen.query_one("#history-list", OptionList)
        option_list.highlighted = 2
        await pilot.pause()

        await pilot.press("down")
        await pilot.pause()
        assert option_list.highlighted == 0


@pytest.mark.asyncio
async def test_arrow_up_wraps_to_end(
    sample_jsonl_file: Path,
) -> None:
    """Test that up arrow wraps to last option from first."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await _submit_query(app=app, pilot=pilot, query="first")
        await _submit_query(app=app, pilot=pilot, query="second")
        await _submit_query(app=app, pilot=pilot, query="third")

        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        await pilot.press("H")
        await pilot.pause()

        assert isinstance(app.screen, HistoryModal)
        from textual.widgets import OptionList

        option_list = app.screen.query_one("#history-list", OptionList)
        assert option_list.highlighted == 0

        await pilot.press("up")
        await pilot.pause()
        assert option_list.highlighted == 2


@pytest.mark.asyncio
async def test_repeated_query_opens_modal_without_duplicates(
    sample_jsonl_file: Path,
) -> None:
    """Re-submitting an older query must not crash the modal (DuplicateID)."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        for query in ("error", "info", "error"):
            await _submit_query(app=app, pilot=pilot, query=query)

        await pilot.press("H")
        await pilot.pause()

        assert isinstance(app.screen, HistoryModal)
        option_list = app.screen.query_one("#history-list", OptionList)
        prompts = [
            str(option_list.get_option_at_index(i).prompt)
            for i in range(option_list.option_count)
        ]
        assert prompts == ["error", "info"]


@pytest.mark.asyncio
@pytest.mark.parametrize("key", ["j", "k", "down", "up"])
async def test_cursor_keys_on_empty_history_do_not_crash(
    sample_jsonl_file: Path, key: str
) -> None:
    """Cursor keys in an empty history modal must be a no-op."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.press("H")
        await pilot.pause()

        await pilot.press(key)
        await pilot.pause()

        assert isinstance(app.screen, HistoryModal)


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ['msg:"x [/]"', '"[/api/users]"', "m:[b]x"])
async def test_queries_with_brackets_are_plain_text(
    sample_jsonl_file: Path, query: str
) -> None:
    """[...] in a saved query is text, not formatting (it used to crash)."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()
        app.search_history = [query]

        await pilot.press("H")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert app.filter_query == query
