"""jlv reading piped stdin: argument handling in main()."""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from json_logs_viewer import app as app_module
from json_logs_viewer.stdin_pipe import STDIN_LABEL


class FakeApp:
    created: list[dict[str, Any]] = []

    def __init__(self, **kwargs: Any) -> None:  # noqa: ANN401
        FakeApp.created.append(kwargs)

    def run(self) -> None:
        # The copy exists while the app runs.
        stdin_path = FakeApp.created[-1]["stdin_path"]
        assert stdin_path is None or Path(stdin_path).exists()


@pytest.fixture
def piped(monkeypatch: pytest.MonkeyPatch) -> Iterator[int]:
    """Pretend stdin is a pipe; returns the pipe's write end."""
    read_fd, write_fd = os.pipe()
    FakeApp.created = []
    monkeypatch.setattr(app_module, "LogViewerApp", FakeApp)
    monkeypatch.setattr(app_module, "stdin_is_piped", lambda: True)
    monkeypatch.setattr(app_module, "take_over_stdin", lambda: read_fd)
    monkeypatch.setattr(app_module, "default_history_path", lambda: None)
    yield write_fd
    os.close(write_fd)


def _run(monkeypatch: pytest.MonkeyPatch, *args: str) -> dict[str, Any]:
    monkeypatch.setattr(sys, "argv", ["jlv", *args])
    app_module.main()
    return FakeApp.created[-1]


def test_piped_input_without_files(
    piped: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    kwargs = _run(monkeypatch)

    (path,) = kwargs["files"]
    assert Path(path).name == STDIN_LABEL
    assert kwargs["stdin_path"] == path
    assert kwargs["follow"] is True
    # Removed once the app has exited.
    assert not Path(path).parent.exists()


def test_dash_merges_stdin_with_files(
    piped: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    kwargs = _run(monkeypatch, "-", "worker.jsonl")

    assert kwargs["files"] == [kwargs["stdin_path"], "worker.jsonl"]


def test_files_without_dash_leave_stdin_alone(
    piped: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    kwargs = _run(monkeypatch, "app.jsonl")

    assert kwargs["files"] == ["app.jsonl"]
    assert kwargs["stdin_path"] is None
    assert kwargs["follow"] is False


def test_dash_without_piped_input_is_an_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(app_module, "stdin_is_piped", lambda: False)
    monkeypatch.setattr(sys, "argv", ["jlv", "-"])

    with pytest.raises(SystemExit, match="nothing is piped"):
        app_module.main()


def test_serve_cannot_read_stdin(
    piped: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "argv", ["jlv", "--serve", "-"])
    with pytest.raises(SystemExit, match="--serve can't read piped input"):
        app_module.main()


def test_no_terminal_is_a_clear_error(
    piped: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_tty() -> int:
        raise OSError("No such device or address: '/dev/tty'")

    monkeypatch.setattr(app_module, "take_over_stdin", no_tty)
    monkeypatch.setattr(sys, "argv", ["jlv"])
    with pytest.raises(SystemExit, match="can't read piped input"):
        app_module.main()


def test_serve_without_files_ignores_a_non_terminal_stdin(
    piped: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Jlv --serve as a service has no terminal; that isn't a pipe."""
    servers: list[str] = []

    class FakeServer:
        def __init__(self, command: str, *, title: str) -> None:
            servers.append(command)

        def serve(self) -> None:
            pass

    monkeypatch.setattr("textual_serve.server.Server", FakeServer)
    monkeypatch.setattr(sys, "argv", ["jlv", "--serve"])

    app_module.main()

    assert len(servers) == 1


def test_serve_session_without_files_ignores_its_piped_stdin(
    piped: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """textual-serve gives each session a pipe as stdin: that isn't logs."""
    monkeypatch.setenv(app_module.SERVE_FILE_ENV, "[]")

    kwargs = _run(monkeypatch)

    assert kwargs["files"] == []
    assert kwargs["stdin_path"] is None
    assert kwargs["show_picker_on_start"] is True


def test_serve_marks_its_sessions_even_without_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeServer:
        def __init__(self, command: str, *, title: str) -> None:
            pass

        def serve(self) -> None:
            pass

    monkeypatch.delenv(app_module.SERVE_FILE_ENV, raising=False)
    monkeypatch.setattr(app_module, "stdin_is_piped", lambda: False)
    monkeypatch.setattr("textual_serve.server.Server", FakeServer)
    monkeypatch.setattr(sys, "argv", ["jlv", "--serve"])

    app_module.main()

    assert os.environ[app_module.SERVE_FILE_ENV] == "[]"
