"""Unit tests for the file watcher."""

from __future__ import annotations

import os
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from json_logs_viewer.log_watcher import PollWatcher, get_watcher


@pytest.fixture
def watched_file(tmp_path: Path) -> tuple[Path, int]:
    """Create a file and return (path, write_fd) for appending."""
    filepath = tmp_path / "test.jsonl"
    filepath.write_text('{"msg":"initial"}\n', encoding="utf-8")
    write_fd = os.open(str(filepath), os.O_WRONLY | os.O_APPEND)
    return filepath, write_fd


def test_poll_watcher_detects_new_bytes(
    watched_file: tuple[Path, int],
) -> None:
    """Appending to a file triggers the callback with the new bytes."""
    filepath, write_fd = watched_file
    received: list[bytes] = []

    watcher = PollWatcher()
    read_fd = os.open(str(filepath), os.O_RDONLY)
    os.lseek(read_fd, 0, os.SEEK_END)

    watcher.watch(
        fileno=read_fd,
        callback=received.append,
        error_callback=MagicMock(),
    )
    watcher.start()

    try:
        os.write(write_fd, b'{"msg":"new"}\n')
        time.sleep(0.2)
    finally:
        watcher.close()
        os.close(write_fd)
        os.close(read_fd)

    joined = b"".join(received)
    assert b'{"msg":"new"}' in joined


def test_poll_watcher_no_callback_when_idle(
    watched_file: tuple[Path, int],
) -> None:
    """No callback fired when no new data is written."""
    filepath, write_fd = watched_file
    callback = MagicMock()

    watcher = PollWatcher()
    read_fd = os.open(str(filepath), os.O_RDONLY)
    os.lseek(read_fd, 0, os.SEEK_END)

    watcher.watch(
        fileno=read_fd,
        callback=callback,
        error_callback=MagicMock(),
    )
    watcher.start()

    try:
        time.sleep(0.2)
    finally:
        watcher.close()
        os.close(write_fd)
        os.close(read_fd)

    callback.assert_not_called()


def test_callback_receives_only_new_content(
    watched_file: tuple[Path, int],
) -> None:
    """Watcher started at end of file only receives newly appended data."""
    filepath, write_fd = watched_file
    received: list[bytes] = []

    watcher = PollWatcher()
    read_fd = os.open(str(filepath), os.O_RDONLY)
    os.lseek(read_fd, 0, os.SEEK_END)

    watcher.watch(
        fileno=read_fd,
        callback=received.append,
        error_callback=MagicMock(),
    )
    watcher.start()

    try:
        os.write(write_fd, b'{"msg":"after"}\n')
        time.sleep(0.2)
    finally:
        watcher.close()
        os.close(write_fd)
        os.close(read_fd)

    joined = b"".join(received)
    assert b"initial" not in joined
    assert b"after" in joined


def test_close_stops_thread(
    watched_file: tuple[Path, int],
) -> None:
    """Calling close() stops the watcher thread."""
    filepath, write_fd = watched_file

    watcher = PollWatcher()
    read_fd = os.open(str(filepath), os.O_RDONLY)
    os.lseek(read_fd, 0, os.SEEK_END)

    watcher.watch(
        fileno=read_fd,
        callback=MagicMock(),
        error_callback=MagicMock(),
    )
    watcher.start()

    assert watcher._thread is not None
    thread = watcher._thread
    assert thread.is_alive()

    watcher.close()
    thread.join(timeout=1.0)

    try:
        assert not thread.is_alive()
    finally:
        os.close(write_fd)
        os.close(read_fd)


def test_error_callback_on_bad_fd() -> None:
    """Error callback is triggered when reading from a closed fd."""
    error_callback = MagicMock()

    watcher = PollWatcher()
    # Use an invalid fd that will cause os.read to fail
    bad_fd = os.open("/dev/null", os.O_RDONLY)
    os.close(bad_fd)

    watcher.watch(
        fileno=bad_fd,
        callback=MagicMock(),
        error_callback=error_callback,
    )
    watcher.start()

    time.sleep(0.2)
    watcher.close()

    error_callback.assert_called_once()
    error_arg = error_callback.call_args[0][0]
    assert isinstance(error_arg, OSError)


def test_get_watcher_returns_poll_on_linux() -> None:
    """get_watcher() returns PollWatcher on Linux."""
    import platform

    watcher = get_watcher()
    if platform.system() == "Darwin":
        from json_logs_viewer.log_watcher import SelectorWatcher

        assert isinstance(watcher, SelectorWatcher)
    else:
        assert isinstance(watcher, PollWatcher)
