"""Integration tests for LogList widget."""

from pathlib import Path

import pytest
from textual.message import Message

from json_logs_viewer.app import LogViewerApp
from json_logs_viewer.widgets.log_list import LogList


@pytest.mark.asyncio
async def test_log_list_builds_items(
    sample_jsonl_file: Path,
    sample_jsonl_entry_count: int,
) -> None:
    """Test that LogList correctly builds list items from logs."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test():
        log_list = app.query_one("#logs", LogList)
        assert len(log_list._log_entries) == sample_jsonl_entry_count
        for log in log_list._log_entries:
            assert log.line_number > 0


@pytest.mark.asyncio
async def test_navigation_jk(sample_jsonl_file: Path) -> None:
    """Test that j/k keys update selected_index and LogList cursor."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        assert app.selected_index == 0
        assert log_list.index == 0

        await pilot.press("j")
        assert app.selected_index == 1
        assert log_list.index == 1

        await pilot.press("k")
        assert app.selected_index == 0
        assert log_list.index == 0

        await pilot.press("down", "down", "down")
        assert app.selected_index == 3
        assert log_list.index == 3

        await pilot.press("up")
        assert app.selected_index == 2
        assert log_list.index == 2


@pytest.mark.asyncio
async def test_gg_and_G(sample_jsonl_file: Path) -> None:
    """Test g jumps to top and G jumps to bottom."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        app.selected_index = 2
        log_list.index = 2

        await pilot.press("g", "g")
        assert app.selected_index == 0
        assert log_list.index == 0

        await pilot.press("G")
        assert app.selected_index == 3
        assert log_list.index == 3


@pytest.mark.asyncio
async def test_enter_posts_message(
    sample_jsonl_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that Enter posts LogSelected message with correct log."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    captured = []
    async with app.run_test() as pilot:
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()
        assert log_list.has_focus

        original_post = log_list.post_message

        def mock_post(msg: Message) -> bool:
            captured.append(msg)
            return original_post(msg)

        monkeypatch.setattr(log_list, "post_message", mock_post)

        await pilot.press("enter")
        await pilot.pause()

        msgs = [m for m in captured if isinstance(m, LogList.LogSelected)]
        assert len(msgs) == 1
        assert msgs[0].log_entry.line_number == 1


@pytest.mark.asyncio
async def test_empty_logs() -> None:
    """Test LogList behavior with no logs."""
    app = LogViewerApp()
    async with app.run_test():
        log_list = app.query_one("#logs", LogList)
        assert len(log_list._log_entries) == 0
        assert app.selected_index == 0
