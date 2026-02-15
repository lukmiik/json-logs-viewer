"""Integration tests for LogList widget."""

import json
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
        assert log_list._cursor_index == 3

        await pilot.press("j")
        assert app.selected_index == 3
        assert log_list._cursor_index == 3

        await pilot.press("k")
        assert app.selected_index == 2
        assert log_list._cursor_index == 2

        await pilot.press("down", "down", "down")
        assert app.selected_index == 3
        assert log_list._cursor_index == 3

        await pilot.press("up")
        assert app.selected_index == 2
        assert log_list._cursor_index == 2


@pytest.mark.asyncio
async def test_gg_and_G(sample_jsonl_file: Path) -> None:
    """Test g jumps to top and G jumps to bottom."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        app.selected_index = 2
        await pilot.pause()

        await pilot.press("g")
        await pilot.pause()
        assert app.selected_index == 0
        assert log_list._cursor_index == 0

        await pilot.press("G")
        await pilot.pause()
        assert app.selected_index == 3
        assert log_list._cursor_index == 3


@pytest.mark.asyncio
async def test_enter_posts_message(
    sample_jsonl_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that Enter posts LogSelected message with correct log."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    captured: list[Message] = []
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
    """Test that pressing w toggles wrap_log_lines."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        assert app.wrap_log_lines is False

        await pilot.press("w")
        await pilot.pause()
        assert app.wrap_log_lines is True

        await pilot.press("w")
        await pilot.pause()
        assert app.wrap_log_lines is False


@pytest.mark.asyncio
async def test_scrolloff_behavior(
    sample_jsonl_file: Path,
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

        assert log_list._cursor_index == 3


@pytest.mark.asyncio
async def test_scroll_cursor_into_view_called(
    sample_jsonl_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that _scroll_cursor_into_view is called on cursor movement."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        app.selected_index = 0
        await pilot.pause()

        scroll_called: list[bool] = []

        original_scroll = log_list._scroll_cursor_into_view

        def mock_scroll() -> None:
            scroll_called.append(True)
            return original_scroll()

        monkeypatch.setattr(log_list, "_scroll_cursor_into_view", mock_scroll)

        await pilot.press("j")
        await pilot.pause()

        assert len(scroll_called) > 0


@pytest.mark.asyncio
async def test_horizontal_scroll_hl(sample_jsonl_file: Path) -> None:
    """Test that h/l keys trigger horizontal scrolling."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        assert log_list.has_focus

        log_list.scroll_right()
        await pilot.pause()
        scroll_x_before = log_list.scroll_x

        await pilot.press("h")
        await pilot.pause()
        assert log_list.scroll_x < scroll_x_before

        scroll_x_before = log_list.scroll_x

        await pilot.press("l")
        await pilot.pause()
        assert log_list.scroll_x > scroll_x_before


@pytest.mark.asyncio
async def test_scroll_top_scrolls_to_top(many_logs_file: Path) -> None:
    """Test that pressing 'g' scrolls the viewport to the very top."""
    app = LogViewerApp(file=str(many_logs_file))
    async with app.run_test() as pilot:
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        assert log_list.has_focus

        log_list.scroll_to(y=30, animate=False)
        await pilot.pause()
        assert log_list.scroll_y > 0

        app.selected_index = 25
        await pilot.pause()

        await pilot.press("g")
        await pilot.pause()

        assert app.selected_index == 0
        assert log_list._cursor_index == 0
        assert log_list.scroll_y == 0


@pytest.mark.asyncio
async def test_scroll_bottom_scrolls_to_bottom(many_logs_file: Path) -> None:
    """Test that pressing 'G' scrolls the viewport to the very bottom."""
    app = LogViewerApp(file=str(many_logs_file))
    async with app.run_test() as pilot:
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        assert log_list.has_focus

        app.selected_index = 0
        await pilot.pause()

        await pilot.press("G")
        await pilot.pause()

        last_index = len(log_list._log_entries) - 1
        assert app.selected_index == last_index
        assert log_list._cursor_index == last_index

        max_scroll = log_list.max_scroll_y
        assert log_list.scroll_y == max_scroll


@pytest.mark.asyncio
async def test_virtual_size_matches_log_count(
    sample_jsonl_file: Path,
    sample_jsonl_entry_count: int,
) -> None:
    """Test that virtual_size height equals number of log entries."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test():
        log_list = app.query_one("#logs", LogList)
        assert log_list.virtual_size.height == sample_jsonl_entry_count


@pytest.mark.asyncio
async def test_virtual_size_width_matches_max_content(
    sample_jsonl_file: Path,
) -> None:
    """Test that virtual_size width is based on the longest serialized line."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test():
        log_list = app.query_one("#logs", LogList)
        max_len = max(
            len(json.dumps(log.data, ensure_ascii=False))
            for log in log_list._log_entries
        )
        assert log_list._max_content_width == max_len
        assert log_list.virtual_size.width == max_len + 2


@pytest.mark.asyncio
async def test_render_line_returns_correct_content(
    sample_jsonl_file: Path,
) -> None:
    """Test that render_line produces a strip starting with the JSON text."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        # Scroll to top so line 0 is visible at y=0
        log_list.scroll_to(y=0, animate=False)
        log_list._cursor_index = 0
        await pilot.pause()

        strip = log_list.render_line(0)
        rendered_text = strip.text
        expected = json.dumps(
            log_list._log_entries[0].data, ensure_ascii=False
        )
        # Strip is cropped to viewport width, so check the
        # visible portion matches the start of the JSON text
        visible_len = len(rendered_text.rstrip())
        assert rendered_text.startswith(expected[:visible_len])


@pytest.mark.asyncio
async def test_render_line_blank_for_out_of_bounds(
    sample_jsonl_file: Path,
) -> None:
    """Test render_line returns blank for out-of-bounds."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        log_list = app.query_one("#logs", LogList)
        await pilot.pause()

        # Request a line beyond the log entries
        log_list.scroll_to(y=0, animate=False)
        await pilot.pause()
        # y + scroll_y would be far beyond the entries
        strip = log_list.render_line(len(log_list._log_entries) + 100)
        assert strip.text.strip() == ""


@pytest.mark.asyncio
async def test_line_cache_is_populated(sample_jsonl_file: Path) -> None:
    """Test that render_line populates the LRU cache."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        log_list.scroll_to(y=0, animate=False)
        log_list._cursor_index = 0
        await pilot.pause()

        # Render first line — should populate cache for index 0
        log_list.render_line(0)
        assert 0 in log_list._line_cache


@pytest.mark.asyncio
async def test_set_logs_resets_cache(sample_jsonl_file: Path) -> None:
    """Test that set_logs clears the line cache."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        log_list = app.query_one("#logs", LogList)
        await pilot.pause()

        # Populate cache
        log_list.scroll_to(y=0, animate=False)
        await pilot.pause()
        log_list.render_line(0)
        assert 0 in log_list._line_cache

        # set_logs should reset it
        log_list.set_logs(logs=log_list._log_entries)
        assert 0 not in log_list._line_cache


@pytest.mark.asyncio
async def test_cursor_clamps_when_filtered_logs_shrink(
    sample_jsonl_file: Path,
) -> None:
    """Test that cursor stays in bounds when filter reduces entries."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        # Cursor starts at last entry (index 3)
        assert log_list._cursor_index == 3

        # Apply filter that matches only 1 entry
        search_bar = app.query_one("#search")
        search_bar.focus()
        await pilot.press(*list("level:DEBUG"))
        await pilot.press("enter")
        await pilot.pause()

        assert len(log_list._log_entries) == 1
        assert log_list._cursor_index == 0


@pytest.mark.asyncio
async def test_enter_on_empty_logs_no_crash() -> None:
    """Test that pressing Enter with no logs doesn't crash."""
    app = LogViewerApp()
    async with app.run_test() as pilot:
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        assert len(log_list._log_entries) == 0
        await pilot.press("enter")
        await pilot.pause()
        # No crash is the assertion


@pytest.mark.asyncio
async def test_enter_selects_correct_log_after_navigating(
    sample_jsonl_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that Enter selects the log at the current cursor position."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    captured: list[Message] = []
    async with app.run_test() as pilot:
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        original_post = log_list.post_message

        def mock_post(msg: Message) -> bool:
            captured.append(msg)
            return original_post(msg)

        monkeypatch.setattr(log_list, "post_message", mock_post)

        # Navigate to the first entry
        await pilot.press("g")
        await pilot.pause()
        assert log_list._cursor_index == 0

        await pilot.press("enter")
        await pilot.pause()

        msgs = [m for m in captured if isinstance(m, LogList.LogSelected)]
        assert len(msgs) == 1
        assert msgs[0].log_entry.line_number == 1


@pytest.mark.asyncio
async def test_cursor_starts_at_last_entry(
    sample_jsonl_file: Path,
) -> None:
    """Test that cursor starts at the newest (last) log entry on load."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        log_list = app.query_one("#logs", LogList)
        await pilot.pause()

        last = len(log_list._log_entries) - 1
        assert log_list._cursor_index == last
        assert app.selected_index == last


@pytest.mark.asyncio
async def test_virtual_size_empty_logs() -> None:
    """Test that virtual_size is (2, 0) with no logs."""
    app = LogViewerApp()
    async with app.run_test():
        log_list = app.query_one("#logs", LogList)
        assert log_list.virtual_size.height == 0
        assert log_list.virtual_size.width == 2


class TestWrapMode:
    """Tests for wrap mode functionality."""

    @pytest.mark.asyncio
    async def test_wrap_mode_toggle_populates_wrapped_lines(
        self, sample_jsonl_file: Path
    ) -> None:
        """Test that enabling wrap mode populates _wrapped_lines mapping."""
        app = LogViewerApp(file=str(sample_jsonl_file))
        async with app.run_test() as pilot:
            log_list = app.query_one("#logs", LogList)
            log_list.focus()
            await pilot.pause()

            assert log_list._wrap_mode is False
            assert len(log_list._wrapped_lines) == 0

            await pilot.press("w")
            await pilot.pause()

            assert log_list._wrap_mode is True
            assert len(log_list._wrapped_lines) > 0

    @pytest.mark.asyncio
    async def test_wrap_mode_toggle_clears_wrapped_lines(
        self, sample_jsonl_file: Path
    ) -> None:
        """Test that disabling wrap mode clears _wrapped_lines."""
        app = LogViewerApp(file=str(sample_jsonl_file))
        async with app.run_test() as pilot:
            log_list = app.query_one("#logs", LogList)
            log_list.focus()
            await pilot.pause()

            await pilot.press("w")
            await pilot.pause()
            assert len(log_list._wrapped_lines) > 0

            await pilot.press("w")
            await pilot.pause()
            assert log_list._wrap_mode is False
            assert len(log_list._wrapped_lines) == 0

    @pytest.mark.asyncio
    async def test_wrap_mode_entry_start_rows_populated(
        self, sample_jsonl_file: Path
    ) -> None:
        """Test that _entry_start_rows is populated in wrap mode."""
        app = LogViewerApp(file=str(sample_jsonl_file))
        async with app.run_test() as pilot:
            log_list = app.query_one("#logs", LogList)
            log_list.focus()
            await pilot.pause()

            await pilot.press("w")
            await pilot.pause()

            assert len(log_list._entry_start_rows) == len(
                log_list._log_entries
            )
            assert 0 in log_list._entry_start_rows

    @pytest.mark.asyncio
    async def test_wrap_mode_navigation_jumps_between_entries(
        self, sample_jsonl_file: Path
    ) -> None:
        """Test j/k in wrap mode jumps between entries, not wrapped lines."""
        app = LogViewerApp(file=str(sample_jsonl_file))
        async with app.run_test() as pilot:
            log_list = app.query_one("#logs", LogList)
            log_list.focus()
            await pilot.pause()

            await pilot.press("g")
            await pilot.press("w")
            await pilot.pause()

            start_cursor = log_list._cursor_index
            await pilot.press("j")
            await pilot.pause()
            assert log_list._cursor_index > start_cursor

            await pilot.press("k")
            await pilot.pause()
            assert log_list._cursor_index == start_cursor

    @pytest.mark.asyncio
    async def test_get_cursor_row_in_wrap_mode(
        self, sample_jsonl_file: Path
    ) -> None:
        """Test that _get_cursor_row returns correct row in wrap mode."""
        app = LogViewerApp(file=str(sample_jsonl_file))
        async with app.run_test() as pilot:
            log_list = app.query_one("#logs", LogList)
            log_list.focus()
            await pilot.pause()

            await pilot.press("w")
            await pilot.press("g")
            await pilot.pause()

            cursor_row = log_list._get_cursor_row()
            assert cursor_row == log_list._entry_start_rows.get(0, 0)

    @pytest.mark.asyncio
    async def test_wrap_mode_virtual_size_uses_wrapped_lines_count(
        self, sample_jsonl_file: Path
    ) -> None:
        """Test virtual_size.height equals wrapped lines count in wrap mode."""
        app = LogViewerApp(file=str(sample_jsonl_file))
        async with app.run_test() as pilot:
            log_list = app.query_one("#logs", LogList)
            log_list.focus()
            await pilot.pause()

            await pilot.press("w")
            await pilot.pause()

            wrap_height = log_list.virtual_size.height
            assert wrap_height == len(log_list._wrapped_lines)

    @pytest.mark.asyncio
    async def test_horizontal_scroll_disabled_in_wrap_mode(
        self, sample_jsonl_file: Path
    ) -> None:
        """Test that h/l keys don't scroll horizontally in wrap mode."""
        app = LogViewerApp(file=str(sample_jsonl_file))
        async with app.run_test() as pilot:
            log_list = app.query_one("#logs", LogList)
            log_list.focus()
            await pilot.pause()

            await pilot.press("w")
            await pilot.pause()

            await pilot.press("h")
            await pilot.pause()
            assert log_list.scroll_x == 0

            await pilot.press("l")
            await pilot.pause()
            assert log_list.scroll_x == 0

    @pytest.mark.asyncio
    async def test_wrap_mode_scroll_bottom_uses_wrapped_lines(
        self, sample_jsonl_file: Path
    ) -> None:
        """Test that G scrolls to last wrapped line in wrap mode."""
        app = LogViewerApp(file=str(sample_jsonl_file))
        async with app.run_test() as pilot:
            log_list = app.query_one("#logs", LogList)
            log_list.focus()
            await pilot.pause()

            await pilot.press("w")
            await pilot.press("g")
            await pilot.pause()

            await pilot.press("G")
            await pilot.pause()

            expected_max_scroll = (
                len(log_list._wrapped_lines) - log_list.size.height
            )
            expected_max_scroll = max(0, expected_max_scroll)
            assert log_list.scroll_y >= expected_max_scroll

    @pytest.mark.asyncio
    async def test_wrap_mode_with_empty_logs(self) -> None:
        """Test wrap mode with no logs doesn't crash."""
        app = LogViewerApp()
        async with app.run_test() as pilot:
            log_list = app.query_one("#logs", LogList)
            log_list.focus()
            await pilot.pause()

            await pilot.press("w")
            await pilot.pause()

            assert log_list._wrap_mode is True
            assert len(log_list._wrapped_lines) == 0
            assert len(log_list._entry_start_rows) == 0
