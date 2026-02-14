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

        assert app.selected_index == 3
        assert log_list.index == 3

        await pilot.press("j")
        assert app.selected_index == 3
        assert log_list.index == 3

        await pilot.press("k")
        assert app.selected_index == 2
        assert log_list.index == 2

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
        assert msgs[0].log_entry.line_number == 4


@pytest.mark.asyncio
async def test_empty_logs() -> None:
    """Test LogList behavior with no logs."""
    app = LogViewerApp()
    async with app.run_test():
        log_list = app.query_one("#logs", LogList)
        assert len(log_list._log_entries) == 0
        assert app.selected_index == 0


@pytest.mark.asyncio
async def test_toggle_wrap_action(sample_jsonl_file: Path) -> None:
    """Test that action_toggle_wrap toggles wrap_log_lines."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test():
        assert app.wrap_log_lines is False

        app.action_toggle_wrap()
        assert app.wrap_log_lines is True

        app.action_toggle_wrap()
        assert app.wrap_log_lines is False


@pytest.mark.asyncio
async def test_toggle_wrap_key(sample_jsonl_file: Path) -> None:
    """Test that pressing w toggles wrap in LogList."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        assert app.wrap_log_lines is False
        assert not log_list.has_class("-wrap")

        await pilot.press("w")
        await pilot.pause()

        assert app.wrap_log_lines is True
        assert log_list.has_class("-wrap")

        await pilot.press("w")
        await pilot.pause()

        assert app.wrap_log_lines is False
        assert not log_list.has_class("-wrap")


@pytest.mark.asyncio
async def test_toggle_wrap_class_added_on_start(
    sample_jsonl_file: Path,
) -> None:
    """Test that -wrap class is added when wrap_log_lines starts True."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    app.wrap_log_lines = True
    async with app.run_test():
        log_list = app.query_one("#logs", LogList)
        assert log_list.has_class("-wrap")


@pytest.mark.asyncio
async def test_scrolloff_behavior(
    sample_jsonl_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that SCROLLOFF is respected when scrolling."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        assert log_list.SCROLLOFF == 3

        await pilot.press("j", "j", "j")
        await pilot.pause()

        assert log_list.index == 3


@pytest.mark.asyncio
async def test_scroll_highlighted_into_view(
    sample_jsonl_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that _scroll_highlighted_into_view is called on index change."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        log_list.index = 0
        app.selected_index = 0
        await pilot.pause()

        scroll_called = []

        original_scroll = log_list._scroll_highlighted_into_view

        def mock_scroll() -> None:
            scroll_called.append(True)
            return original_scroll()

        monkeypatch.setattr(
            log_list, "_scroll_highlighted_into_view", mock_scroll
        )

        await pilot.press("j")
        await pilot.pause()

        assert len(scroll_called) > 0


@pytest.mark.asyncio
async def test_horizontal_scroll_hl(sample_jsonl_file: Path) -> None:
    """Test that h/l keys scroll horizontally."""
    from textual.containers import ScrollableContainer

    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        log_list = app.query_one("#logs", LogList)
        container = app.query_one("#logs-scroll", ScrollableContainer)
        log_list.focus()
        await pilot.pause()

        assert log_list.has_focus

        container.scroll_right()
        await pilot.pause()
        scroll_x_before = container.scroll_x

        await pilot.press("h")
        await pilot.pause()
        assert container.scroll_x < scroll_x_before

        scroll_x_before = container.scroll_x

        await pilot.press("l")
        await pilot.pause()
        assert container.scroll_x > scroll_x_before
