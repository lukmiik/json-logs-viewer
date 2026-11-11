"""Integration tests for ColumnsModal."""

from pathlib import Path

import pytest
from textual.widgets import SelectionList

from json_logs_viewer.app import LogViewerApp
from json_logs_viewer.modals.columns_modal import ColumnsModal
from json_logs_viewer.widgets.log_list import LogList


def _prompt(selection_list: SelectionList[str], index: int) -> str:
    return str(selection_list.get_option_at_index(index).prompt)


@pytest.mark.asyncio
async def test_keybinding_opens_modal(sample_jsonl_file: Path) -> None:
    """Test that C (uppercase) opens the columns modal."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        await pilot.press("c")
        await pilot.pause()

        assert isinstance(app.screen, ColumnsModal)


@pytest.mark.asyncio
async def test_selection_list_displays_available_fields(
    sample_jsonl_file: Path,
) -> None:
    """Test that SelectionList shows discovered fields sorted by frequency."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()

        await pilot.press("c")
        await pilot.pause()

        assert isinstance(app.screen, ColumnsModal)
        selection_list = app.screen.query_one("#column-list", SelectionList)

        # Detected fields come first, then real fields by frequency.
        expected_fields = [
            "@timestamp (detected)",
            "@level (detected)",
            "@message (detected)",
            "timestamp",
            "level",
            "message",
            "service",
            "user",
            "latency",
        ]
        actual_fields = [str(opt.prompt) for opt in selection_list.options]
        assert actual_fields == expected_fields


@pytest.mark.asyncio
async def test_selecting_fields_and_applying(
    sample_jsonl_file: Path,
) -> None:
    """Test selecting fields and applying updates LogList rendering."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()

        await pilot.press("c")
        await pilot.pause()

        assert isinstance(app.screen, ColumnsModal)

        await pilot.press("space")
        await pilot.pause()

        await pilot.press("enter")
        await pilot.pause()

        assert not isinstance(app.screen, ColumnsModal)
        assert app.columns == ["@timestamp"]


@pytest.mark.asyncio
async def test_reset_to_default_clears_columns(
    sample_jsonl_file: Path,
) -> None:
    """Test that R key clears all columns."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        app.columns = ["level", "timestamp"]
        await pilot.pause()

        await pilot.press("c")
        await pilot.pause()

        assert isinstance(app.screen, ColumnsModal)

        await pilot.press("r")
        await pilot.pause()

        assert not isinstance(app.screen, ColumnsModal)
        assert app.columns == []


@pytest.mark.asyncio
async def test_escape_cancels_without_changes(
    sample_jsonl_file: Path,
) -> None:
    """Test that ESC dismisses modal without applying changes."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        original_columns = ["level"]
        app.columns = original_columns
        await pilot.pause()

        await pilot.press("c")
        await pilot.pause()

        assert isinstance(app.screen, ColumnsModal)

        await pilot.press("escape")
        await pilot.pause()

        assert not isinstance(app.screen, ColumnsModal)
        assert app.columns == original_columns


@pytest.mark.asyncio
async def test_modal_not_opened_when_already_open(
    sample_jsonl_file: Path,
) -> None:
    """Test that pressing C again doesn't push a second modal."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        await pilot.press("c")
        await pilot.pause()

        first_screen = app.screen
        assert isinstance(first_screen, ColumnsModal)

        await pilot.press("c")
        await pilot.pause()

        assert app.screen is first_screen


@pytest.mark.asyncio
async def test_columns_render_on_left_of_json(
    sample_jsonl_file: Path,
) -> None:
    """Test that configured columns appear before raw JSON in LogList."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()

        app.columns = ["level", "timestamp"]
        await pilot.pause()

        log_list = app.query_one("#logs", LogList)
        assert log_list._column_widths

        assert "level" in log_list._column_widths
        assert "timestamp" in log_list._column_widths


@pytest.mark.asyncio
async def test_jk_navigates_selection_list(
    sample_jsonl_file: Path,
) -> None:
    """Test that j/k moves the cursor in the SelectionList."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()

        await pilot.press("c")
        await pilot.pause()

        assert isinstance(app.screen, ColumnsModal)
        selection_list = app.screen.query_one("#column-list", SelectionList)

        assert selection_list.highlighted == 0
        assert _prompt(selection_list, 0) == "@timestamp (detected)"

        await pilot.press("j")
        await pilot.pause()
        assert selection_list.highlighted == 1
        assert _prompt(selection_list, 1) == "@level (detected)"

        await pilot.press("j")
        await pilot.pause()
        assert selection_list.highlighted == 2
        assert _prompt(selection_list, 2) == "@message (detected)"

        await pilot.press("k")
        await pilot.pause()
        assert selection_list.highlighted == 1
        assert _prompt(selection_list, 1) == "@level (detected)"


@pytest.mark.asyncio
async def test_arrow_keys_navigate_selection_list(
    sample_jsonl_file: Path,
) -> None:
    """Test that down/up arrow keys move the cursor in the SelectionList."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()

        await pilot.press("c")
        await pilot.pause()

        assert isinstance(app.screen, ColumnsModal)
        selection_list = app.screen.query_one("#column-list", SelectionList)

        assert selection_list.highlighted == 0
        assert _prompt(selection_list, 0) == "@timestamp (detected)"

        await pilot.press("down")
        await pilot.pause()
        assert selection_list.highlighted == 1
        assert _prompt(selection_list, 1) == "@level (detected)"

        await pilot.press("up")
        await pilot.pause()
        assert selection_list.highlighted == 0
        assert _prompt(selection_list, 0) == "@timestamp (detected)"


@pytest.mark.asyncio
async def test_field_names_with_brackets_are_plain_text(
    tmp_path: Path,
) -> None:
    """Field names come from the logs; [/x] must not be read as markup."""
    path = tmp_path / "odd.jsonl"
    path.write_text('{"[/x]": 1, "[b]bold": 2}\n')
    app = LogViewerApp(file=str(path))
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()

        selection_list = app.screen.query_one("#column-list", SelectionList)
        assert {_prompt(selection_list, i) for i in range(2)} == {
            "[/x]",
            "[b]bold",
        }
