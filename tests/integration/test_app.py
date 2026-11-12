"""Integration tests for LogViewerApp."""

from pathlib import Path

import pytest

from json_logs_viewer.app import LogViewerApp
from json_logs_viewer.widgets.log_list import LogList


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
        assert app._exit  # q asked the app to quit


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


@pytest.mark.asyncio
async def test_log_list_has_focus_on_start(sample_jsonl_file: Path) -> None:
    """Keys like c and / need the list focused, not the search bar."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.focused is app.query_one("#logs", LogList)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("width", "expected"), [(160, 100), (100, 75), (70, 60)]
)
async def test_command_palette_is_centred_not_full_width(
    sample_jsonl_file: Path, width: int, expected: int
) -> None:
    """75% of the screen, kept between 60 and 100 columns, centred."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test(size=(width, 30)) as pilot:
        await pilot.pause()
        await pilot.press("ctrl+p")
        # The palette shows its container only once it's ready.
        await pilot.pause(0.5)

        # The container itself is visibility: hidden (only its contents are
        # drawn, so it has no region); the input row spans its width.
        box = app.screen.query_one("#--input").region
        assert box.width == expected
        assert box.x == (width - expected) // 2
