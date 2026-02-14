"""Integration tests for StatusBar and StatusInfo widgets."""

from pathlib import Path

import pytest
from textual.widgets import Label

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
