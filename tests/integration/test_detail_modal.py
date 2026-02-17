"""Integration tests for DetailModal."""

from pathlib import Path

import pytest

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
