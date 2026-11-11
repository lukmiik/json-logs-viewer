"""Integration tests for StatusBar and StatusInfo widgets."""

from pathlib import Path

import pytest
from textual.widgets import Button, Label

from json_logs_viewer.app import LogViewerApp
from json_logs_viewer.widgets.status_bar import StatusBar, StatusInfo


@pytest.mark.asyncio
async def test_status_bar_shows_file_info(
    sample_jsonl_file: Path,
    sample_jsonl_entry_count: int,
) -> None:
    """Test that status bar displays filename, total, and filtered counts."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()

        info = app.query_one(StatusInfo)
        assert info.filename == str(sample_jsonl_file)
        assert info.total == sample_jsonl_entry_count
        assert info.filtered == sample_jsonl_entry_count


@pytest.mark.asyncio
async def test_status_bar_labels_content(
    sample_jsonl_file: Path,
    sample_jsonl_entry_count: int,
) -> None:
    """Test that status bar labels contain the expected text."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()

        info = app.query_one(StatusInfo)
        filename_label = info.query_one("#status-filename", Label)
        total_label = info.query_one("#status-total", Label)
        filtered_label = info.query_one("#status-filtered", Label)

        assert str(sample_jsonl_file) in str(filename_label.render())
        assert str(sample_jsonl_entry_count) in str(total_label.render())
        assert str(sample_jsonl_entry_count) in str(filtered_label.render())


@pytest.mark.asyncio
async def test_status_bar_default_no_file() -> None:
    """Test status bar defaults when no file is loaded."""
    app = LogViewerApp()
    async with app.run_test() as pilot:
        await pilot.pause()

        info = app.query_one(StatusInfo)
        assert info.filename == "No file"
        assert info.total == 0
        assert info.filtered == 0


@pytest.mark.asyncio
async def test_status_bar_composes_children() -> None:
    """Test that StatusBar contains StatusInfo and Footer."""
    app = LogViewerApp()
    async with app.run_test() as pilot:
        await pilot.pause()

        status_bar = app.query_one("#status", StatusBar)
        assert len(status_bar.query(StatusInfo)) == 1


@pytest.mark.asyncio
async def test_status_bar_toggle_buttons_present() -> None:
    """Test that status bar exposes both filter toggle buttons."""
    app = LogViewerApp()
    async with app.run_test() as pilot:
        await pilot.pause()

        info = app.query_one(StatusInfo)
        case_button = info.query_one("#status-case-sensitive", Button)
        highlight_button = info.query_one("#status-highlight-matches", Button)
        assert case_button.label == "Aa"
        assert highlight_button.label == "Highlight"


@pytest.mark.asyncio
async def test_status_bar_toggle_buttons_update_app_state() -> None:
    """Test that clicking toggles updates app reactives."""
    app = LogViewerApp()
    async with app.run_test() as pilot:
        await pilot.pause()

        info = app.query_one(StatusInfo)
        case_button = info.query_one("#status-case-sensitive", Button)
        highlight_button = info.query_one("#status-highlight-matches", Button)

        assert app.case_sensitive is False
        assert app.highlight_matches is False

        await pilot.click(case_button)
        await pilot.pause()
        assert app.case_sensitive is True

        await pilot.click(highlight_button)
        await pilot.pause()
        assert app.highlight_matches is True


@pytest.mark.asyncio
async def test_status_bar_toggle_buttons_follow_app_state() -> None:
    """Test that button active style follows app reactive changes."""
    app = LogViewerApp()
    async with app.run_test() as pilot:
        await pilot.pause()

        info = app.query_one(StatusInfo)
        case_button = info.query_one("#status-case-sensitive", Button)
        highlight_button = info.query_one("#status-highlight-matches", Button)

        assert "-active-toggle" not in case_button.classes
        assert "-active-toggle" not in highlight_button.classes

        app.case_sensitive = True
        app.highlight_matches = True
        await pilot.pause()

        assert "-active-toggle" in case_button.classes
        assert "-active-toggle" in highlight_button.classes


@pytest.mark.asyncio
async def test_status_bar_toggle_keybinds_update_state_and_buttons() -> None:
    """Test keybinds toggle app state and update button active style."""
    app = LogViewerApp()
    async with app.run_test() as pilot:
        await pilot.pause()

        info = app.query_one(StatusInfo)
        case_button = info.query_one("#status-case-sensitive", Button)
        highlight_button = info.query_one("#status-highlight-matches", Button)

        assert app.case_sensitive is False
        assert app.highlight_matches is False
        assert "-active-toggle" not in case_button.classes
        assert "-active-toggle" not in highlight_button.classes

        await pilot.press("C")
        await pilot.pause()
        assert app.case_sensitive is True
        assert "-active-toggle" in case_button.classes

        await pilot.press("m")
        await pilot.pause()
        assert app.highlight_matches is True
        assert "-active-toggle" in highlight_button.classes


def _query_label_text(*, app: LogViewerApp) -> str:
    return str(app.query_one("#status-query", Label).render())


@pytest.mark.asyncio
async def test_status_bar_shows_active_query(sample_jsonl_file: Path) -> None:
    """With the search bar hidden, the status bar shows the active filter."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()
        assert _query_label_text(app=app) == ""

        app.filter_query = "level:error"
        await pilot.pause()
        assert _query_label_text(app=app) == "Filter: level:error"

        app.highlight_matches = True
        await pilot.pause()
        assert _query_label_text(app=app) == "Highlight: level:error"

        app.filter_query = ""
        await pilot.pause()
        assert _query_label_text(app=app) == ""
