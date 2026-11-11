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
async def test_page_down_ctrl_d(many_logs_file: Path) -> None:
    """Test that Ctrl+D moves cursor half a page down."""
    app = LogViewerApp(file=str(many_logs_file))
    async with app.run_test(size=(80, 20)) as pilot:
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        half_page = log_list.size.height // 2

        await pilot.press("g")
        await pilot.pause()
        assert log_list._cursor_index == 0

        await pilot.press("ctrl+d")
        await pilot.pause()
        assert log_list._cursor_index == half_page
        assert app.selected_index == half_page

        await pilot.press("ctrl+d")
        await pilot.pause()
        assert log_list._cursor_index == half_page * 2
        assert app.selected_index == half_page * 2


@pytest.mark.asyncio
async def test_page_up_ctrl_u(many_logs_file: Path) -> None:
    """Test that Ctrl+U moves cursor half a page up."""
    app = LogViewerApp(file=str(many_logs_file))
    async with app.run_test(size=(80, 20)) as pilot:
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        half_page = log_list.size.height // 2

        app.selected_index = 30
        await pilot.pause()
        assert log_list._cursor_index == 30

        await pilot.press("ctrl+u")
        await pilot.pause()
        assert log_list._cursor_index == 30 - half_page
        assert app.selected_index == 30 - half_page

        await pilot.press("ctrl+u")
        await pilot.pause()
        assert log_list._cursor_index == 30 - half_page * 2
        assert app.selected_index == 30 - half_page * 2


@pytest.mark.asyncio
async def test_page_down_clamps_to_last(many_logs_file: Path) -> None:
    """Test that Ctrl+D clamps to the last entry."""
    app = LogViewerApp(file=str(many_logs_file))
    async with app.run_test(size=(80, 20)) as pilot:
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        app.selected_index = 45
        await pilot.pause()

        await pilot.press("ctrl+d")
        await pilot.pause()
        assert log_list._cursor_index == 49
        assert app.selected_index == 49


@pytest.mark.asyncio
async def test_page_up_clamps_to_first(many_logs_file: Path) -> None:
    """Test that Ctrl+U clamps to the first entry."""
    app = LogViewerApp(file=str(many_logs_file))
    async with app.run_test(size=(80, 20)) as pilot:
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        app.selected_index = 3
        await pilot.pause()

        await pilot.press("ctrl+u")
        await pilot.pause()
        assert log_list._cursor_index == 0
        assert app.selected_index == 0


@pytest.mark.asyncio
async def test_page_up_down_noop_on_empty() -> None:
    """Test that Ctrl+U/Ctrl+D do nothing with no logs."""
    app = LogViewerApp()
    async with app.run_test() as pilot:
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        await pilot.press("ctrl+d")
        await pilot.pause()
        assert log_list._cursor_index == 0

        await pilot.press("ctrl+u")
        await pilot.pause()
        assert log_list._cursor_index == 0


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
async def test_max_width_updates_on_scroll(
    varying_width_logs_file: Path,
) -> None:
    """Test that max content width updates based on visible lines."""
    app = LogViewerApp(file=str(varying_width_logs_file))
    async with app.run_test(size=(80, 5)) as pilot:
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        log_list.scroll_to(y=0, animate=False)
        await pilot.pause()

        short_width = len(
            json.dumps(log_list._log_entries[0].data, ensure_ascii=False)
        )
        assert log_list._max_content_width == short_width

        log_list.scroll_to(y=5, animate=False)
        await pilot.pause()

        long_width = len(
            json.dumps(log_list._log_entries[5].data, ensure_ascii=False)
        )
        assert log_list._max_content_width == long_width
        assert long_width > short_width

        log_list.scroll_to(y=7, animate=False)
        await pilot.pause()

        assert log_list._max_content_width == short_width


@pytest.mark.asyncio
async def test_virtual_size_width_updates_on_scroll(
    varying_width_logs_file: Path,
) -> None:
    """Test that virtual_size width changes as user scrolls."""
    app = LogViewerApp(file=str(varying_width_logs_file))
    async with app.run_test(size=(80, 5)) as pilot:
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        log_list.scroll_to(y=0, animate=False)
        await pilot.pause()
        narrow_width = log_list.virtual_size.width

        log_list.scroll_to(y=5, animate=False)
        await pilot.pause()
        wide_width = log_list.virtual_size.width

        assert wide_width > narrow_width

        log_list.scroll_to(y=10, animate=False)
        await pilot.pause()
        medium_width = log_list.virtual_size.width

        assert medium_width < wide_width


@pytest.mark.asyncio
async def test_max_width_does_not_update_in_wrap_mode(
    varying_width_logs_file: Path,
) -> None:
    """Test that max width stays constant in wrap mode."""
    app = LogViewerApp(file=str(varying_width_logs_file))
    async with app.run_test(size=(80, 5)) as pilot:
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        app.wrap_log_lines = True
        await pilot.pause()

        log_list.scroll_to(y=0, animate=False)
        await pilot.pause()
        width_at_top = log_list.virtual_size.width

        log_list.scroll_to(y=5, animate=False)
        await pilot.pause()
        width_at_wide = log_list.virtual_size.width

        assert width_at_top == width_at_wide


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
        app.action_focus_search()
        await pilot.press(*list("level:DEBUG"))
        await pilot.press("enter")
        await pilot.pause()

        assert len(log_list._log_entries) == 1
        assert log_list._cursor_index == 0


@pytest.mark.asyncio
async def test_highlight_mode_keeps_all_logs_and_marks_matches(
    sample_jsonl_file: Path,
) -> None:
    """Test highlight mode shows all logs and tracks matching entries."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()

        app.highlight_matches = True
        app.filter_query = "level:ERROR"
        await pilot.pause()

        log_list = app.query_one("#logs", LogList)
        assert len(log_list._log_entries) == 4
        assert log_list._match_flags == [False, True, False, False]


@pytest.mark.asyncio
async def test_disabling_highlight_mode_clears_match_marking(
    sample_jsonl_file: Path,
) -> None:
    """Test disabling highlight mode restores neutral row styling state."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()

        app.highlight_matches = True
        app.filter_query = "level:ERROR"
        await pilot.pause()

        log_list = app.query_one("#logs", LogList)
        assert log_list._match_flags == [False, True, False, False]

        app.highlight_matches = False
        await pilot.pause()
        assert len(log_list._log_entries) == 1
        assert log_list._match_flags == [True]


@pytest.mark.asyncio
async def test_toggle_highlight_preserves_selected_log_entry(
    many_logs_file: Path,
) -> None:
    """Test highlight toggle keeps the same selected log entry."""
    app = LogViewerApp(file=str(many_logs_file))
    async with app.run_test() as pilot:
        await pilot.pause()

        app.filter_query = "line:4"
        await pilot.pause()

        app.selected_index = len(app.filtered_logs) - 1
        await pilot.pause()
        selected_before = app.filtered_logs[app.selected_index]

        app.action_toggle_highlight_matches()
        await pilot.pause()

        assert app.highlight_matches is True
        assert len(app.filtered_logs) == 50
        assert (
            app.filtered_logs[app.selected_index].data["line"]
            == selected_before.data["line"]
        )

        app.action_toggle_highlight_matches()
        await pilot.pause()

        assert app.highlight_matches is False
        assert (
            app.filtered_logs[app.selected_index].data["line"]
            == selected_before.data["line"]
        )


@pytest.mark.asyncio
async def test_case_toggle_restores_selection_after_empty_results(
    many_logs_file: Path,
) -> None:
    """Case toggle keeps selected entry when intermediate results are empty."""
    app = LogViewerApp(file=str(many_logs_file))
    async with app.run_test() as pilot:
        await pilot.pause()

        app.filter_query = "message:log"
        await pilot.pause()

        app.selected_index = len(app.filtered_logs) - 1
        await pilot.pause()
        selected_before = app.filtered_logs[app.selected_index]
        assert selected_before.data["line"] == 49

        app.action_toggle_case_sensitive()
        await pilot.pause()

        assert app.case_sensitive is True
        assert app.filtered_logs == []
        assert app.selected_index == 0

        app.action_toggle_case_sensitive()
        await pilot.pause()

        assert app.case_sensitive is False
        assert len(app.filtered_logs) == 50
        assert app.filtered_logs[app.selected_index] is selected_before


@pytest.mark.asyncio
async def test_case_toggle_restores_scroll_after_empty_results(
    many_logs_file: Path,
) -> None:
    """Case toggle keeps cursor visible after temporary empty result set."""
    app = LogViewerApp(file=str(many_logs_file))
    async with app.run_test() as pilot:
        await pilot.pause()

        app.filter_query = "message:log"
        await pilot.pause()

        app.selected_index = len(app.filtered_logs) - 1
        await pilot.pause()

        log_list = app.query_one("#logs", LogList)
        assert log_list._cursor_index == 49
        assert log_list.scroll_y > 0

        app.action_toggle_case_sensitive()
        await pilot.pause()

        assert app.filtered_logs == []

        app.action_toggle_case_sensitive()
        await pilot.pause()

        assert app.filtered_logs[app.selected_index].data["line"] == 49
        assert log_list._cursor_index == 49

        cursor_row = log_list._get_cursor_row()
        visible_top = log_list.scroll_y
        visible_bottom = visible_top + log_list.size.height - 1
        assert visible_top <= cursor_row <= visible_bottom


@pytest.mark.asyncio
async def test_toggle_highlight_off_selects_closest_filtered_log(
    many_logs_file: Path,
) -> None:
    """Test leaving highlight mode picks closest matching entry if needed."""
    app = LogViewerApp(file=str(many_logs_file))
    async with app.run_test() as pilot:
        await pilot.pause()

        app.filter_query = "line:4"
        app.highlight_matches = True
        await pilot.pause()

        app.selected_index = 27
        await pilot.pause()
        selected_before = app.filtered_logs[app.selected_index]
        assert selected_before.data["line"] == 27

        app.action_toggle_highlight_matches()
        await pilot.pause()

        assert app.highlight_matches is False
        assert app.filtered_logs[app.selected_index].data["line"] == 24


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


class TestMatchJump:
    """Tests for n/N match jumping in highlight mode."""

    @pytest.mark.asyncio
    async def test_next_match_jumps_to_matching_entry(
        self, sample_jsonl_file: Path
    ) -> None:
        """Test n jumps forward to the next matching entry."""
        app = LogViewerApp(file=str(sample_jsonl_file))
        async with app.run_test() as pilot:
            log_list = app.query_one("#logs", LogList)
            log_list.focus()
            await pilot.pause()

            app.highlight_matches = True
            app.filter_query = "level:ERROR"
            await pilot.pause()

            # Matching entry is at index 1
            await pilot.press("g")
            await pilot.pause()
            assert log_list._cursor_index == 0

            await pilot.press("n")
            await pilot.pause()
            assert log_list._cursor_index == 1
            assert app.selected_index == 1

    @pytest.mark.asyncio
    async def test_prev_match_jumps_to_matching_entry(
        self, sample_jsonl_file: Path
    ) -> None:
        """Test N jumps backward to the previous matching entry."""
        app = LogViewerApp(file=str(sample_jsonl_file))
        async with app.run_test() as pilot:
            log_list = app.query_one("#logs", LogList)
            log_list.focus()
            await pilot.pause()

            app.highlight_matches = True
            app.filter_query = "level:ERROR"
            await pilot.pause()

            # Start at index 3, N should go back to 1
            await pilot.press("G")
            await pilot.pause()
            assert log_list._cursor_index == 3

            await pilot.press("N")
            await pilot.pause()
            assert log_list._cursor_index == 1
            assert app.selected_index == 1

    @pytest.mark.asyncio
    async def test_next_match_wraps_around(
        self, sample_jsonl_file: Path
    ) -> None:
        """Test n wraps from end to beginning."""
        app = LogViewerApp(file=str(sample_jsonl_file))
        async with app.run_test() as pilot:
            log_list = app.query_one("#logs", LogList)
            log_list.focus()
            await pilot.pause()

            app.highlight_matches = True
            app.filter_query = "level:ERROR"
            await pilot.pause()

            # Move cursor past the match at index 1
            app.selected_index = 2
            await pilot.pause()

            await pilot.press("n")
            await pilot.pause()
            # Should wrap around to index 1
            assert log_list._cursor_index == 1

    @pytest.mark.asyncio
    async def test_prev_match_wraps_around(
        self, sample_jsonl_file: Path
    ) -> None:
        """Test N wraps from beginning to end."""
        app = LogViewerApp(file=str(sample_jsonl_file))
        async with app.run_test() as pilot:
            log_list = app.query_one("#logs", LogList)
            log_list.focus()
            await pilot.pause()

            app.highlight_matches = True
            app.filter_query = "level:ERROR"
            await pilot.pause()

            # Start at index 0, N should wrap to 1
            await pilot.press("g")
            await pilot.pause()
            assert log_list._cursor_index == 0

            await pilot.press("N")
            await pilot.pause()
            assert log_list._cursor_index == 1

    @pytest.mark.asyncio
    async def test_match_jump_noop_without_highlight_mode(
        self, sample_jsonl_file: Path
    ) -> None:
        """Test n/N do nothing when highlight mode is off."""
        app = LogViewerApp(file=str(sample_jsonl_file))
        async with app.run_test() as pilot:
            log_list = app.query_one("#logs", LogList)
            log_list.focus()
            await pilot.pause()

            app.filter_query = "level:ERROR"
            await pilot.pause()

            pos = log_list._cursor_index

            await pilot.press("n")
            await pilot.pause()
            assert log_list._cursor_index == pos

            await pilot.press("N")
            await pilot.pause()
            assert log_list._cursor_index == pos

    @pytest.mark.asyncio
    async def test_match_jump_noop_without_query(
        self, sample_jsonl_file: Path
    ) -> None:
        """Test n/N do nothing when filter query is empty."""
        app = LogViewerApp(file=str(sample_jsonl_file))
        async with app.run_test() as pilot:
            log_list = app.query_one("#logs", LogList)
            log_list.focus()
            await pilot.pause()

            app.highlight_matches = True
            await pilot.pause()

            pos = log_list._cursor_index

            await pilot.press("n")
            await pilot.pause()
            assert log_list._cursor_index == pos

    @pytest.mark.asyncio
    async def test_match_jump_noop_on_empty_logs(self) -> None:
        """Test n/N do nothing with no logs loaded."""
        app = LogViewerApp()
        async with app.run_test() as pilot:
            log_list = app.query_one("#logs", LogList)
            log_list.focus()
            await pilot.pause()

            app.highlight_matches = True
            app.filter_query = "level:ERROR"
            await pilot.pause()

            await pilot.press("n")
            await pilot.pause()
            assert log_list._cursor_index == 0

    @pytest.mark.asyncio
    async def test_match_jump_multiple_matches(
        self, sample_jsonl_file: Path
    ) -> None:
        """Test n cycles through multiple matches in order."""
        app = LogViewerApp(file=str(sample_jsonl_file))
        async with app.run_test() as pilot:
            log_list = app.query_one("#logs", LogList)
            log_list.focus()
            await pilot.pause()

            # INFO at 0 and api at 0,2
            app.highlight_matches = True
            app.filter_query = "service:api"
            await pilot.pause()
            assert log_list._match_flags == [
                True,
                False,
                True,
                False,
            ]

            await pilot.press("g")
            await pilot.pause()
            assert log_list._cursor_index == 0

            await pilot.press("n")
            await pilot.pause()
            assert log_list._cursor_index == 2

            await pilot.press("n")
            await pilot.pause()
            # Wraps back to 0
            assert log_list._cursor_index == 0


class TestCopyLog:
    """Tests for copying logs to clipboard."""

    @pytest.mark.asyncio
    async def test_y_copies_current_log(self, sample_jsonl_file: Path) -> None:
        """Test that pressing y copies the current log to clipboard."""
        copied_text: list[str] = []

        app = LogViewerApp(file=str(sample_jsonl_file))

        def mock_copy(text: str) -> None:
            copied_text.append(text)

        app.copy_to_clipboard = mock_copy  # type: ignore[method-assign]

        async with app.run_test() as pilot:
            log_list = app.query_one("#logs", LogList)
            log_list.focus()
            await pilot.pause()

            await pilot.press("g")
            await pilot.pause()
            assert log_list._cursor_index == 0

            await pilot.press("y")
            await pilot.pause()

            assert len(copied_text) == 1
            parsed = json.loads(copied_text[0])
            assert parsed["level"] == "INFO"
            assert parsed["message"] == "Started"

    @pytest.mark.asyncio
    async def test_y_copies_different_log_after_navigation(
        self, sample_jsonl_file: Path
    ) -> None:
        """Test that y copies the correct log after navigating."""
        copied_text: list[str] = []

        app = LogViewerApp(file=str(sample_jsonl_file))

        def mock_copy(text: str) -> None:
            copied_text.append(text)

        app.copy_to_clipboard = mock_copy  # type: ignore[method-assign]

        async with app.run_test() as pilot:
            log_list = app.query_one("#logs", LogList)
            log_list.focus()
            await pilot.pause()

            await pilot.press("g")
            await pilot.press("j")
            await pilot.pause()
            assert log_list._cursor_index == 1

            await pilot.press("y")
            await pilot.pause()

            assert len(copied_text) == 1
            parsed = json.loads(copied_text[0])
            assert parsed["level"] == "ERROR"

    @pytest.mark.asyncio
    async def test_y_does_nothing_on_empty_logs(self) -> None:
        """Test that y does nothing when there are no logs."""
        copied_text: list[str] = []

        app = LogViewerApp()

        def mock_copy(text: str) -> None:
            copied_text.append(text)

        app.copy_to_clipboard = mock_copy  # type: ignore[method-assign]

        async with app.run_test() as pilot:
            log_list = app.query_one("#logs", LogList)
            log_list.focus()
            await pilot.pause()

            await pilot.press("y")
            await pilot.pause()

            assert len(copied_text) == 0

    @pytest.mark.asyncio
    async def test_shift_y_copies_with_context(
        self, sample_jsonl_file: Path
    ) -> None:
        """Test that pressing Y copies log with context."""
        copied_text: list[str] = []

        app = LogViewerApp(file=str(sample_jsonl_file))

        def mock_copy(text: str) -> None:
            copied_text.append(text)

        app.copy_to_clipboard = mock_copy  # type: ignore[method-assign]

        async with app.run_test() as pilot:
            log_list = app.query_one("#logs", LogList)
            log_list.focus()
            await pilot.pause()

            await pilot.press("g")
            await pilot.press("j")
            await pilot.pause()
            assert log_list._cursor_index == 1

            await pilot.press("Y")
            await pilot.pause()

            assert len(copied_text) == 1
            lines = copied_text[0].split("\n")
            parsed_logs = [json.loads(line) for line in lines]
            assert len(parsed_logs) == 4
            levels = [log["level"] for log in parsed_logs]
            assert levels == ["INFO", "ERROR", "WARN", "DEBUG"]

    @pytest.mark.asyncio
    async def test_shift_y_uses_filtered_logs(
        self, sample_jsonl_file: Path
    ) -> None:
        """Test that Y uses filtered logs, not full logs."""
        copied_text: list[str] = []

        app = LogViewerApp(file=str(sample_jsonl_file))

        def mock_copy(text: str) -> None:
            copied_text.append(text)

        app.copy_to_clipboard = mock_copy  # type: ignore[method-assign]

        async with app.run_test() as pilot:
            app.filter_query = "level:ERROR"
            await pilot.pause()

            assert len(app.filtered_logs) == 1

            log_list = app.query_one("#logs", LogList)
            log_list.focus()
            await pilot.pause()

            await pilot.press("Y")
            await pilot.pause()

            assert len(copied_text) == 1
            lines = copied_text[0].split("\n")
            parsed_logs = [json.loads(line) for line in lines]
            assert len(parsed_logs) == 1
            assert parsed_logs[0]["level"] == "ERROR"

    @pytest.mark.asyncio
    async def test_shift_y_at_start_of_logs(
        self, sample_jsonl_file: Path
    ) -> None:
        """Test that Y handles context at start of logs correctly."""
        copied_text: list[str] = []

        app = LogViewerApp(file=str(sample_jsonl_file))

        def mock_copy(text: str) -> None:
            copied_text.append(text)

        app.copy_to_clipboard = mock_copy  # type: ignore[method-assign]

        async with app.run_test() as pilot:
            log_list = app.query_one("#logs", LogList)
            log_list.focus()
            await pilot.pause()

            await pilot.press("g")
            await pilot.pause()
            assert log_list._cursor_index == 0

            await pilot.press("Y")
            await pilot.pause()

            assert len(copied_text) == 1
            lines = copied_text[0].split("\n")
            parsed_logs = [json.loads(line) for line in lines]
            assert len(parsed_logs) == 4
            assert parsed_logs[0]["level"] == "INFO"

    @pytest.mark.asyncio
    async def test_shift_y_at_end_of_logs(
        self, sample_jsonl_file: Path
    ) -> None:
        """Test that Y handles context at end of logs correctly."""
        copied_text: list[str] = []

        app = LogViewerApp(file=str(sample_jsonl_file))

        def mock_copy(text: str) -> None:
            copied_text.append(text)

        app.copy_to_clipboard = mock_copy  # type: ignore[method-assign]

        async with app.run_test() as pilot:
            log_list = app.query_one("#logs", LogList)
            log_list.focus()
            await pilot.pause()

            await pilot.press("G")
            await pilot.pause()
            assert log_list._cursor_index == 3

            await pilot.press("Y")
            await pilot.pause()

            assert len(copied_text) == 1
            lines = copied_text[0].split("\n")
            parsed_logs = [json.loads(line) for line in lines]
            assert len(parsed_logs) == 4
            assert parsed_logs[-1]["level"] == "DEBUG"

    @pytest.mark.asyncio
    async def test_shift_y_does_nothing_on_empty_logs(self) -> None:
        """Test that Y does nothing when there are no logs."""
        copied_text: list[str] = []

        app = LogViewerApp()

        def mock_copy(text: str) -> None:
            copied_text.append(text)

        app.copy_to_clipboard = mock_copy  # type: ignore[method-assign]

        async with app.run_test() as pilot:
            log_list = app.query_one("#logs", LogList)
            log_list.focus()
            await pilot.pause()

            await pilot.press("Y")
            await pilot.pause()

            assert len(copied_text) == 0


@pytest.mark.asyncio
async def test_max_width_follows_filter(
    varying_width_logs_file: Path,
) -> None:
    """After a filter change the width comes from the visible matches."""
    app = LogViewerApp(file=str(varying_width_logs_file))
    async with app.run_test(size=(80, 5)) as pilot:
        log_list = app.query_one("#logs", LogList)

        app.filter_query = "very_long_field_name:"
        await pilot.pause()
        long_width = len(log_list._log_entries[0].raw_json)
        assert log_list._max_content_width == long_width

        app.filter_query = "short:"
        await pilot.pause()
        assert log_list._max_content_width == len('{"short": "a"}')
