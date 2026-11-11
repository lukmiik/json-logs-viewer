"""Copying piped stdin into a private temporary file."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from json_logs_viewer.stdin_pipe import StdinCopy


def _wait_for(copy: StdinCopy) -> None:
    assert copy.finished.wait(timeout=5)


def test_copies_everything_until_the_pipe_closes() -> None:
    read_fd, write_fd = os.pipe()
    copy = StdinCopy(fd=read_fd)
    copy.start()
    try:
        os.write(write_fd, b'{"a": 1}\n{"a"')
        os.write(write_fd, b": 2}\n")
        os.close(write_fd)
        _wait_for(copy)

        assert Path(copy.path).read_bytes() == b'{"a": 1}\n{"a": 2}\n'
        assert Path(copy.path).name == "stdin"
    finally:
        copy.close()


@pytest.mark.skipif(os.name != "posix", reason="POSIX file modes")
def test_copy_is_private() -> None:
    read_fd, write_fd = os.pipe()
    os.close(write_fd)
    copy = StdinCopy(fd=read_fd)
    try:
        path = Path(copy.path)
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    finally:
        copy.close()


def test_close_removes_the_copy() -> None:
    read_fd, write_fd = os.pipe()
    copy = StdinCopy(fd=read_fd)
    copy.start()
    os.close(write_fd)
    _wait_for(copy)
    folder = Path(copy.path).parent

    copy.close()

    assert not folder.exists()


def test_closing_while_data_still_arrives_is_quiet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Quitting mid-stream used to print a ValueError traceback."""
    import threading
    import time

    errors: list[str] = []
    monkeypatch.setattr(
        threading,
        "excepthook",
        lambda args: errors.append(args.exc_type.__name__),
    )
    read_fd, write_fd = os.pipe()
    copy = StdinCopy(fd=read_fd)
    copy.start()
    stop = threading.Event()

    def writer() -> None:
        while not stop.is_set():
            try:
                os.write(write_fd, b'{"a": 1}\n' * 200)
            except OSError:
                return

    thread = threading.Thread(target=writer, daemon=True)
    thread.start()
    time.sleep(0.2)

    copy.close()
    assert copy.finished.wait(timeout=5)
    stop.set()
    os.close(write_fd)

    assert errors == []
