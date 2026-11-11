"""Integration tests for follow mode."""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, BinaryIO

import pytest

from json_logs_viewer import app as app_module
from json_logs_viewer import log_watcher as log_watcher_module
from json_logs_viewer.app import LogViewerApp
from json_logs_viewer.log_watcher import PollWatcher
from json_logs_viewer.widgets.log_list import LogList
from json_logs_viewer.widgets.status_bar import StatusInfo


@pytest.mark.asyncio
async def test_follow_toggle_updates_state(
    sample_jsonl_file: Path,
) -> None:
    """Pressing 'f' toggles follow_mode on and off."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        assert app.follow_mode is False
        await pilot.press("f")
        await pilot.pause()
        assert app.follow_mode is True

        await pilot.press("f")
        await pilot.pause()
        assert app.follow_mode is False


@pytest.mark.asyncio
async def test_follow_mode_no_file_shows_warning() -> None:
    """Toggling follow without a loaded file shows a warning."""
    app = LogViewerApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        await pilot.press("f")
        await pilot.pause()
        assert app.follow_mode is False


@pytest.mark.asyncio
async def test_follow_mode_indicator_in_status_bar(
    sample_jsonl_file: Path,
) -> None:
    """StatusBar shows follow indicator when follow mode is active."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        info = app.query_one(StatusInfo)
        assert info.follow_mode is False

        await pilot.press("f")
        await pilot.pause()
        assert info.follow_mode is True

        await pilot.press("f")
        await pilot.pause()
        assert info.follow_mode is False


@pytest.mark.asyncio
async def test_follow_mode_from_cli_flag(
    sample_jsonl_file: Path,
    sample_jsonl_entry_count: int,
) -> None:
    """App started with follow=True activates follow mode after mount."""
    app = LogViewerApp(file=str(sample_jsonl_file), follow=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.follow_mode is True
        assert len(app.logs) == sample_jsonl_entry_count


@pytest.mark.asyncio
async def test_process_chunk_appends_logs(
    sample_jsonl_file: Path,
    sample_jsonl_entry_count: int,
) -> None:
    """_process_chunk appends parsed log entries to app.logs."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(app.logs) == sample_jsonl_entry_count

        new_entry = json.dumps({"level": "INFO", "message": "new log"})
        app._process_chunk(f"{new_entry}\n".encode())
        await pilot.pause()
        assert len(app.logs) == sample_jsonl_entry_count + 1
        assert app.logs[-1].message == "new log"


@pytest.mark.asyncio
async def test_process_chunk_handles_partial_lines(
    sample_jsonl_file: Path,
    sample_jsonl_entry_count: int,
) -> None:
    """Partial lines are buffered until completed by the next chunk."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()

        # Send partial line — should not produce a log
        app._process_chunk(b'{"level":"WARN","mes')
        await pilot.pause()
        assert len(app.logs) == sample_jsonl_entry_count

        # Complete the line — now it should parse
        app._process_chunk(b'sage":"partial"}\n')
        await pilot.pause()
        assert len(app.logs) == sample_jsonl_entry_count + 1
        assert app.logs[-1].message == "partial"


@pytest.mark.asyncio
async def test_process_chunk_skips_invalid_json(
    sample_jsonl_file: Path,
    sample_jsonl_entry_count: int,
) -> None:
    """Invalid JSON lines are skipped without crashing."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()

        chunk = b'not valid json\n{"level":"INFO","message":"valid"}\n'
        app._process_chunk(chunk)
        await pilot.pause()
        assert len(app.logs) == sample_jsonl_entry_count + 1
        assert app.logs[-1].message == "valid"


@pytest.mark.asyncio
async def test_auto_scroll_on_new_logs(
    sample_jsonl_file: Path,
    sample_jsonl_entry_count: int,
) -> None:
    """In follow mode at bottom, cursor moves to the newest entry."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        # Start at bottom (default after load)
        assert app.selected_index == sample_jsonl_entry_count - 1

        # Enable follow mode
        app.follow_mode = True
        await pilot.pause()

        # Simulate new log arriving
        new_entry = json.dumps({"message": "follow-new"})
        app._process_chunk(f"{new_entry}\n".encode())
        await pilot.pause()
        await pilot.pause()

        assert app.selected_index == len(app.logs) - 1
        assert app.logs[-1].message == "follow-new"


@pytest.mark.asyncio
async def test_no_auto_scroll_when_cursor_not_on_last(
    sample_jsonl_file: Path,
    sample_jsonl_entry_count: int,
) -> None:
    """Cursor stays put if user moved it away from the last entry."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        # Move cursor up from the last entry
        await pilot.press("k")
        await pilot.pause()
        cursor_before = app.selected_index
        assert cursor_before < sample_jsonl_entry_count - 1

        # Enable follow mode
        app.follow_mode = True
        await pilot.pause()

        # Simulate new log arriving
        new_entry = json.dumps({"message": "should-not-scroll"})
        app._process_chunk(f"{new_entry}\n".encode())
        await pilot.pause()
        await pilot.pause()

        # Cursor should remain where the user left it
        assert app.selected_index == cursor_before


@pytest.mark.asyncio
async def test_auto_scroll_with_filter_active(
    sample_jsonl_file: Path,
) -> None:
    """Auto-scroll works with filter active, cursor on last match."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        # Apply a filter
        app.filter_query = "error"
        await pilot.pause()
        filtered_count = len(app.filtered_logs)

        # Move cursor to last filtered entry
        app.selected_index = filtered_count - 1
        await pilot.pause()

        # Enable follow mode
        app.follow_mode = True
        await pilot.pause()

        # Append a matching log
        new_entry = json.dumps({"level": "error", "message": "new error"})
        app._process_chunk(f"{new_entry}\n".encode())
        await pilot.pause()
        await pilot.pause()

        # Cursor should move to the new last filtered entry
        assert len(app.filtered_logs) > filtered_count
        assert app.selected_index == len(app.filtered_logs) - 1
        assert app.filtered_logs[-1].message == "new error"


async def _wait_for_logs(
    *, app: LogViewerApp, pilot: object, predicate: Callable[[], bool]
) -> None:
    """Let the watcher thread and the app's message loop catch up."""
    for _ in range(40):
        await asyncio.sleep(0.05)
        if predicate():
            break
    await pilot.pause()  # type: ignore[attr-defined]


def _write_lines(*, path: Path, tag: str, count: int, mode: str) -> None:
    with path.open(mode, encoding="utf-8") as f:
        for i in range(count):
            f.write(json.dumps({"tag": tag, "i": i}) + "\n")


@pytest.mark.asyncio
async def test_follow_reloads_after_truncation(tmp_path: Path) -> None:
    """After `> app.log`, the list shows only the new file's lines."""
    path = tmp_path / "app.log"
    _write_lines(path=path, tag="old", count=50, mode="w")
    app = LogViewerApp(file=str(path), follow=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(app.logs) == 50

        _write_lines(path=path, tag="new", count=3, mode="w")
        await _wait_for_logs(
            app=app,
            pilot=pilot,
            predicate=lambda: [log.data["tag"] for log in app.logs]
            == ["new"] * 3,
        )

        assert [log.data["i"] for log in app.logs] == [0, 1, 2]
        assert [log.line_number for log in app.logs] == [1, 2, 3]
        assert app.follow_mode is True

        # Following continues on the new file.
        _write_lines(path=path, tag="new", count=1, mode="a")
        await _wait_for_logs(
            app=app, pilot=pilot, predicate=lambda: len(app.logs) == 4
        )
        assert len(app.logs) == 4


@pytest.mark.asyncio
async def test_follow_reloads_after_rotation(tmp_path: Path) -> None:
    """After logrotate-style rename + create, the new file is followed."""
    path = tmp_path / "app.log"
    _write_lines(path=path, tag="old", count=50, mode="w")
    app = LogViewerApp(file=str(path), follow=True)
    async with app.run_test() as pilot:
        await pilot.pause()

        path.rename(tmp_path / "app.log.1")
        _write_lines(path=path, tag="new", count=3, mode="w")
        await _wait_for_logs(
            app=app,
            pilot=pilot,
            predicate=lambda: [log.data["tag"] for log in app.logs]
            == ["new"] * 3,
        )

        assert [log.data["tag"] for log in app.logs] == ["new"] * 3
        assert app.follow_mode is True


async def _wait_for_tags(
    *, app: LogViewerApp, pilot: object, tags: list[str]
) -> None:
    await _wait_for_logs(
        app=app,
        pilot=pilot,
        predicate=lambda: [log.data["tag"] for log in app.logs] == tags,
    )


@pytest.mark.asyncio
async def test_follow_line_numbers_count_blank_and_invalid_lines(
    tmp_path: Path,
) -> None:
    """line_number matches the real file line, skipped lines included."""
    path = tmp_path / "app.log"
    path.write_text('{"tag": "a"}\n\nnot json\n{"tag": "b"}\n')
    app = LogViewerApp(file=str(path), follow=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        with path.open("a") as f:
            f.write('{"tag": "c"}\n\ngarbage\n{"tag": "d"}\n')
        await _wait_for_tags(app=app, pilot=pilot, tags=["a", "b", "c", "d"])

        assert [log.line_number for log in app.logs] == [1, 4, 5, 8]


@pytest.mark.asyncio
async def test_half_written_line_at_load_is_completed_by_follow(
    tmp_path: Path,
) -> None:
    """A line still being written when the file is opened isn't lost."""
    path = tmp_path / "app.log"
    path.write_text('{"tag": "a"}\n{"tag": "b", "msg": "half wr')
    app = LogViewerApp(file=str(path), follow=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert [log.data["tag"] for log in app.logs] == ["a"]

        with path.open("a") as f:
            f.write('itten"}\n{"tag": "c"}\n')
        await _wait_for_tags(app=app, pilot=pilot, tags=["a", "b", "c"])

        assert [log.line_number for log in app.logs] == [1, 2, 3]
        assert app.logs[1].data["msg"] == "half written"


@pytest.mark.asyncio
async def test_toggling_follow_keeps_partial_line(tmp_path: Path) -> None:
    """Turning follow off mid-line and back on doesn't drop that line."""
    path = tmp_path / "app.log"
    path.write_text('{"tag": "a"}\n')
    app = LogViewerApp(file=str(path), follow=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        with path.open("a") as f:
            f.write('{"tag": "b", "msg": "spl')
        await _wait_for_logs(
            app=app, pilot=pilot, predicate=lambda: bool(app._follow_buffer)
        )

        app.follow_mode = False
        await pilot.pause()
        with path.open("a") as f:
            f.write('it"}\n')
        app.follow_mode = True
        await _wait_for_tags(app=app, pilot=pilot, tags=["a", "b"])

        assert app.logs[1].data["msg"] == "split"
        assert app.logs[1].line_number == 2


@pytest.mark.asyncio
async def test_file_without_trailing_newline_is_not_duplicated(
    tmp_path: Path,
) -> None:
    """A complete last line with no trailing newline is loaded once."""
    path = tmp_path / "app.log"
    path.write_text('{"tag": "a"}\n{"tag": "b"}')
    app = LogViewerApp(file=str(path), follow=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert [log.data["tag"] for log in app.logs] == ["a", "b"]
        with path.open("a") as f:
            f.write('{"tag": "c"}\n')
        await _wait_for_logs(
            app=app, pilot=pilot, predicate=lambda: len(app.logs) >= 3
        )
        assert [log.data["tag"] for log in app.logs][:2] == ["a", "b"]
        assert app.logs[-1].line_number == 3


@pytest.mark.asyncio
async def test_process_chunk_utf8_char_split_across_chunks(
    sample_jsonl_file: Path,
) -> None:
    """A multi-byte character split between two reads decodes correctly."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()
        data = '{"message": "caf\u00e9"}\n'.encode()
        split = data.index(b"\xc3") + 1  # between the 2 bytes of the e-acute
        app._process_chunk(data[:split])
        app._process_chunk(data[split:])
        await pilot.pause()

        assert app.logs[-1].message == "caf\u00e9"


@pytest.mark.asyncio
async def test_follow_on_deleted_file_disables_follow_without_crash(
    tmp_path: Path,
) -> None:
    """Pressing f after the file was removed shows an error, no crash."""
    path = tmp_path / "app.log"
    _write_lines(path=path, tag="a", count=2, mode="w")
    app = LogViewerApp(file=str(path))
    async with app.run_test() as pilot:
        await pilot.pause()
        path.unlink()

        app.follow_mode = True
        await pilot.pause()

        assert app.follow_mode is False
        assert app._watcher is None
        assert app._watch_file is None
        assert len(app.logs) == 2


@pytest.mark.asyncio
async def test_follow_setup_failure_closes_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the watcher can't be set up, the opened file is closed again."""
    path = tmp_path / "app.log"
    _write_lines(path=path, tag="a", count=2, mode="w")

    class BrokenWatcher(PollWatcher):
        def watch(self, **_: object) -> None:
            raise OSError("cannot watch")

    monkeypatch.setattr(app_module, "get_watcher", BrokenWatcher)
    opened: list[BinaryIO] = []
    real_open = open

    def tracking_open(*args: Any, **kwargs: Any) -> BinaryIO:  # noqa: ANN401
        handle = real_open(*args, **kwargs)
        opened.append(handle)
        return handle

    monkeypatch.setattr("builtins.open", tracking_open)
    app = LogViewerApp(file=str(path))
    async with app.run_test() as pilot:
        await pilot.pause()
        opened.clear()

        app.follow_mode = True
        await pilot.pause()

        assert app.follow_mode is False
        assert app._watch_file is None
        assert len(opened) == 1
        assert opened[0].closed


@pytest.mark.asyncio
async def test_watcher_read_error_stops_follow_without_stall(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A read error turns follow off promptly (no 1 s join deadlock)."""
    path = tmp_path / "app.log"
    _write_lines(path=path, tag="a", count=2, mode="w")
    fail = threading.Event()
    real_read = os.read

    def flaky_read(fd: int, n: int) -> bytes:
        if fail.is_set():
            raise OSError(5, "Input/output error")
        return real_read(fd, n)

    monkeypatch.setattr(log_watcher_module.os, "read", flaky_read)
    app = LogViewerApp(file=str(path), follow=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        started = time.monotonic()
        fail.set()
        while app.follow_mode and time.monotonic() - started < 3:
            await asyncio.sleep(0.005)
        elapsed = time.monotonic() - started
        await pilot.pause()

        assert app.follow_mode is False
        assert app._watcher is None
        assert app._watch_file is None
        # The poll interval is 50 ms; the old deadlock took the full 1 s.
        assert elapsed < 0.5


def _start_heavy_writer(*, path: Path) -> threading.Event:
    """Append log lines as fast as possible until the event is set."""
    stop = threading.Event()

    def write() -> None:
        with path.open("a", encoding="utf-8") as f:
            while not stop.is_set():
                f.write(json.dumps({"msg": "x" * 200}) + "\n")
                f.flush()

    threading.Thread(target=write, daemon=True).start()
    return stop


@pytest.mark.asyncio
async def test_toggling_follow_off_under_heavy_writes_is_prompt(
    tmp_path: Path,
) -> None:
    """Stopping follow while chunks are in flight doesn't block on join."""
    path = tmp_path / "app.log"
    path.write_text("")
    app = LogViewerApp(file=str(path), follow=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        stop_writer = _start_heavy_writer(path=path)
        try:
            worst = 0.0
            for _ in range(10):
                await asyncio.sleep(0.1)
                started = time.monotonic()
                app.follow_mode = False
                worst = max(worst, time.monotonic() - started)
                app.follow_mode = True
        finally:
            stop_writer.set()

        assert worst < 0.5


@pytest.mark.asyncio
async def test_no_lines_lost_or_duplicated_across_toggles(
    tmp_path: Path,
) -> None:
    """Chunks queued when follow stops are re-read, not lost or doubled."""
    path = tmp_path / "app.log"
    path.write_text("")
    app = LogViewerApp(file=str(path), follow=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        with path.open("a", encoding="utf-8") as f:
            for i in range(20_000):
                f.write(json.dumps({"i": i, "msg": "x" * 50}) + "\n")
        for _ in range(6):
            await asyncio.sleep(0.03)
            app.follow_mode = False
            app.follow_mode = True
        await _wait_for_logs(
            app=app,
            pilot=pilot,
            predicate=lambda: len(app.logs) >= 20_000,
        )

        assert [log.data["i"] for log in app.logs] == list(range(20_000))
        assert [log.line_number for log in app.logs] == list(range(1, 20_001))
