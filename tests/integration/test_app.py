"""Integration tests for LogViewerApp."""

from pathlib import Path

import pytest

from json_logs_viewer.app import LogViewerApp


@pytest.mark.asyncio
async def test_app_loads_file(
    sample_jsonl_file: Path,
    sample_jsonl_entry_count: int,
) -> None:
    """Test that the app can load a JSONL file and populate state."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()  # Wait for mount and file load
        assert len(app.logs) == sample_jsonl_entry_count
        assert len(app.filtered_logs) == sample_jsonl_entry_count
        assert app.filepath == str(sample_jsonl_file)
        first = app.logs[0]
        assert first.line_number == 1
        assert first.data["level"] == "INFO"
        assert first.data["service"] == "api"


@pytest.mark.asyncio
async def test_app_without_file() -> None:
    """Test that the app starts successfully without a file."""
    app = LogViewerApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.logs == []
        assert app.filtered_logs == []
        assert app.filepath is None


@pytest.mark.asyncio
async def test_q_quits_app(sample_jsonl_file: Path) -> None:
    """Test that pressing 'q' quits the application."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()
        log_list = app.query_one("#logs")
        log_list.focus()
        await pilot.pause()
        assert log_list.has_focus
        await pilot.press("q")
    assert app._shutdown
