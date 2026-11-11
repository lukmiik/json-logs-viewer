"""Integration tests for DetailModal."""

import json
from pathlib import Path

import pytest
from textual.widgets import TextArea

from json_logs_viewer.app import LogViewerApp
from json_logs_viewer.modals.detail_modal import DetailModal
from json_logs_viewer.widgets.log_list import LogList


@pytest.mark.asyncio
async def test_enter_opens_detail_modal(sample_jsonl_file: Path) -> None:
    """Test that Enter opens the detail modal."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, DetailModal)


@pytest.mark.asyncio
async def test_modal_displays_json(sample_jsonl_file: Path) -> None:
    """Test that modal displays pretty-printed JSON."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        app.selected_index = 0
        await pilot.pause()

        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.press("enter")
        await pilot.pause()

        modal = app.screen
        assert isinstance(modal, DetailModal)
        assert modal.log_entry.data["level"] == "INFO"
        assert modal.log_entry.data["service"] == "api"


@pytest.mark.asyncio
async def test_j_navigates_to_next_log(sample_jsonl_file: Path) -> None:
    """Test that j navigates to next log in modal."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        app.selected_index = 0
        await pilot.pause()

        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.press("enter")
        await pilot.pause()

        modal = app.screen
        assert isinstance(modal, DetailModal)
        assert modal.current_index == 0

        await pilot.press("j")
        await pilot.pause()

        assert modal.current_index == 1
        assert modal.log_entry.data["level"] == "ERROR"


@pytest.mark.asyncio
async def test_k_navigates_to_previous_log(sample_jsonl_file: Path) -> None:
    """Test that k navigates to previous log in modal."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        app.selected_index = 2
        await pilot.pause()

        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.press("enter")
        await pilot.pause()

        modal = app.screen
        assert isinstance(modal, DetailModal)
        assert modal.current_index == 2

        await pilot.press("k")
        await pilot.pause()

        assert modal.current_index == 1
        assert modal.log_entry.data["level"] == "ERROR"


@pytest.mark.asyncio
async def test_down_arrow_navigates_to_next_log(
    sample_jsonl_file: Path,
) -> None:
    """Test that down arrow navigates to next log in modal."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        app.selected_index = 0
        await pilot.pause()

        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.press("enter")
        await pilot.pause()

        modal = app.screen
        assert isinstance(modal, DetailModal)
        assert modal.current_index == 0

        await pilot.press("down")
        await pilot.pause()

        assert modal.current_index == 1
        assert modal.log_entry.data["level"] == "ERROR"


@pytest.mark.asyncio
async def test_up_arrow_navigates_to_previous_log(
    sample_jsonl_file: Path,
) -> None:
    """Test that up arrow navigates to previous log in modal."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        app.selected_index = 2
        await pilot.pause()

        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.press("enter")
        await pilot.pause()

        modal = app.screen
        assert isinstance(modal, DetailModal)
        assert modal.current_index == 2

        await pilot.press("up")
        await pilot.pause()

        assert modal.current_index == 1
        assert modal.log_entry.data["level"] == "ERROR"


@pytest.mark.asyncio
async def test_arrow_navigation_does_not_go_past_end(
    sample_jsonl_file: Path,
) -> None:
    """Test that down arrow does not navigate past the last log."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        app.selected_index = 3
        await pilot.pause()

        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.press("enter")
        await pilot.pause()

        modal = app.screen
        assert isinstance(modal, DetailModal)
        assert modal.current_index == 3

        await pilot.press("down")
        await pilot.pause()

        assert modal.current_index == 3


@pytest.mark.asyncio
async def test_arrow_navigation_does_not_go_before_start(
    sample_jsonl_file: Path,
) -> None:
    """Test that up arrow does not navigate before the first log."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        app.selected_index = 0
        await pilot.pause()

        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.press("enter")
        await pilot.pause()

        modal = app.screen
        assert isinstance(modal, DetailModal)
        assert modal.current_index == 0

        await pilot.press("up")
        await pilot.pause()

        assert modal.current_index == 0


@pytest.mark.asyncio
async def test_escape_closes_modal(sample_jsonl_file: Path) -> None:
    """Test that Escape closes the modal."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, DetailModal)

        await pilot.press("escape")
        await pilot.pause()

        assert not isinstance(app.screen, DetailModal)


@pytest.mark.asyncio
async def test_q_closes_modal(sample_jsonl_file: Path) -> None:
    """Test that q closes the modal."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, DetailModal)

        await pilot.press("q")
        await pilot.pause()

        assert not isinstance(app.screen, DetailModal)


@pytest.mark.asyncio
async def test_navigation_updates_app_selected_index(
    sample_jsonl_file: Path,
) -> None:
    """Test that navigation in modal updates app.selected_index."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        app.selected_index = 0
        await pilot.pause()

        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.press("enter")
        await pilot.pause()

        assert app.selected_index == 0

        await pilot.press("j")
        await pilot.pause()

        assert app.selected_index == 1


@pytest.mark.asyncio
async def test_navigation_does_not_go_past_end(
    sample_jsonl_file: Path,
) -> None:
    """Test that j does not navigate past the last log."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        app.selected_index = 3
        await pilot.pause()

        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.press("enter")
        await pilot.pause()

        modal = app.screen
        assert isinstance(modal, DetailModal)
        assert modal.current_index == 3

        await pilot.press("j")
        await pilot.pause()

        assert modal.current_index == 3


@pytest.mark.asyncio
async def test_navigation_does_not_go_before_start(
    sample_jsonl_file: Path,
) -> None:
    """Test that k does not navigate before the first log."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        app.selected_index = 0
        await pilot.pause()

        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.press("enter")
        await pilot.pause()

        modal = app.screen
        assert isinstance(modal, DetailModal)
        assert modal.current_index == 0

        await pilot.press("k")
        await pilot.pause()

        assert modal.current_index == 0


class TestCopyInModal:
    """Tests for copy functionality in DetailModal."""

    @pytest.mark.asyncio
    async def test_y_copies_current_log(self, sample_jsonl_file: Path) -> None:
        """Test that pressing y in modal copies current log to clipboard."""
        copied_text: list[str] = []

        app = LogViewerApp(file=str(sample_jsonl_file))

        def mock_copy(text: str) -> None:
            copied_text.append(text)

        app.copy_to_clipboard = mock_copy  # type: ignore[method-assign]

        async with app.run_test() as pilot:
            app.selected_index = 0
            await pilot.pause()

            log_list = app.query_one("#logs", LogList)
            log_list.focus()
            await pilot.press("enter")
            await pilot.pause()

            modal = app.screen
            assert isinstance(modal, DetailModal)

            await pilot.press("y")
            await pilot.pause()

            assert len(copied_text) == 1
            parsed = json.loads(copied_text[0])
            assert parsed["level"] == "INFO"

    @pytest.mark.asyncio
    async def test_y_copies_after_navigation(
        self, sample_jsonl_file: Path
    ) -> None:
        """Test that y copies correct log after navigating in modal."""
        copied_text: list[str] = []

        app = LogViewerApp(file=str(sample_jsonl_file))

        def mock_copy(text: str) -> None:
            copied_text.append(text)

        app.copy_to_clipboard = mock_copy  # type: ignore[method-assign]

        async with app.run_test() as pilot:
            app.selected_index = 0
            await pilot.pause()

            log_list = app.query_one("#logs", LogList)
            log_list.focus()
            await pilot.press("enter")
            await pilot.pause()

            modal = app.screen
            assert isinstance(modal, DetailModal)

            await pilot.press("j")
            await pilot.pause()
            assert modal.current_index == 1

            await pilot.press("y")
            await pilot.pause()

            assert len(copied_text) == 1
            parsed = json.loads(copied_text[0])
            assert parsed["level"] == "ERROR"

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
            app.selected_index = 1
            await pilot.pause()

            log_list = app.query_one("#logs", LogList)
            log_list.focus()
            await pilot.press("enter")
            await pilot.pause()

            modal = app.screen
            assert isinstance(modal, DetailModal)

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
            await pilot.press("enter")
            await pilot.pause()

            modal = app.screen
            assert isinstance(modal, DetailModal)

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
            app.selected_index = 0
            await pilot.pause()

            log_list = app.query_one("#logs", LogList)
            log_list.focus()
            await pilot.press("enter")
            await pilot.pause()

            modal = app.screen
            assert isinstance(modal, DetailModal)

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
            app.selected_index = 3
            await pilot.pause()

            log_list = app.query_one("#logs", LogList)
            log_list.focus()
            await pilot.press("enter")
            await pilot.pause()

            modal = app.screen
            assert isinstance(modal, DetailModal)

            await pilot.press("Y")
            await pilot.pause()

            assert len(copied_text) == 1
            lines = copied_text[0].split("\n")
            parsed_logs = [json.loads(line) for line in lines]
            assert len(parsed_logs) == 4
            assert parsed_logs[-1]["level"] == "DEBUG"


@pytest.mark.asyncio
async def test_detail_view_highlights_json(sample_jsonl_file: Path) -> None:
    """The JSON is syntax highlighted, also after moving to another log."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.press("enter")
        text_area = app.screen.query_one("#json-content", TextArea)
        assert text_area.language == "json"
        assert text_area.is_syntax_aware

        await pilot.press("k")
        assert text_area.is_syntax_aware
        assert '"level"' in text_area.text
