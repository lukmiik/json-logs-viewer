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


ODD_LINES = [
    '{"level": "info", "message": "first"}',
    '{"level": 30, "message": "pino-style numeric level"}',
    '{"level": "info", "message": {"nested": true}}',
    '{"timestamp": "not a date", "message": "bad time"}',
    "[1, 2, 3]",
    '"just a string"',
    "not json at all",
    '{"level": "info", "message": "last"}',
]


@pytest.mark.asyncio
async def test_odd_lines_never_stop_a_file_loading(tmp_path: Path) -> None:
    """Unusual field values are kept; non-object lines are skipped."""
    log_file = tmp_path / "odd.jsonl"
    log_file.write_text("\n".join(ODD_LINES) + "\n")
    app = LogViewerApp(file=str(log_file))
    async with app.run_test() as pilot:
        await pilot.pause()

        assert [log.line_number for log in app.logs] == [1, 2, 3, 4, 8]
        assert app.logs[1].level == "30"
        assert app.logs[2].message is None
        assert app.logs[3].timestamp is None


@pytest.mark.asyncio
async def test_odd_lines_in_follow_mode(tmp_path: Path) -> None:
    log_file = tmp_path / "odd.jsonl"
    log_file.write_text("")
    app = LogViewerApp(file=str(log_file))
    async with app.run_test() as pilot:
        await pilot.pause()

        app._process_chunk(("\n".join(ODD_LINES) + "\n").encode())
        await pilot.pause()

        assert app.is_running
        assert [log.line_number for log in app.logs] == [1, 2, 3, 4, 8]
