"""Unit tests for launching the app under --serve."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from json_logs_viewer import app as app_module
from json_logs_viewer.app import SERVE_FILE_ENV, build_serve_command

NASTY_NAMES = [
    "my logs.jsonl",
    "x.jsonl; touch PWNED",
    "$(touch PWNED).jsonl",
    "`touch PWNED`.jsonl",
    "$HOME.jsonl",
    "it's.jsonl",
    "-f.jsonl",
    "a & b (100%) ^!.jsonl",
]


def test_posix_command_round_trips() -> None:
    command = build_serve_command(follow=True, posix=True)

    assert shlex.split(command) == [
        sys.executable,
        "-m",
        "json_logs_viewer",
        "--follow",
    ]


def test_windows_command_quotes_interpreter_path() -> None:
    command = build_serve_command(
        follow=False,
        posix=False,
        executable=r"C:\Program Files\Python\python.exe",
    )

    assert command == (
        r'"C:\Program Files\Python\python.exe" -m json_logs_viewer'
    )


@pytest.mark.skipif(os.name != "posix", reason="textual-serve uses /bin/sh")
@pytest.mark.parametrize("name", NASTY_NAMES)
def test_filename_reaches_child_intact_through_real_shell(
    tmp_path: Path, name: str
) -> None:
    """The child gets the exact name and the shell runs nothing extra."""
    command = build_serve_command(follow=False, posix=True)
    assert name not in command
    # Swap the interpreter for a tiny script that prints what it received.
    probe = shlex.join(
        [
            sys.executable,
            "-c",
            "import os, sys; "
            f"print(repr((sys.argv[1:], os.environ[{SERVE_FILE_ENV!r}])))",
        ]
    )
    command = command.replace(shlex.quote(sys.executable), probe, 1)

    result = subprocess.run(
        command,
        shell=True,
        cwd=tmp_path,
        env={**os.environ, SERVE_FILE_ENV: name},
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == repr((["-m", "json_logs_viewer"], name))
    assert not (tmp_path / "PWNED").exists()


def test_main_serve_puts_file_in_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    servers: list[dict[str, str]] = []

    class FakeServer:
        def __init__(self, command: str, *, title: str) -> None:
            servers.append({"command": command, "title": title})

        def serve(self) -> None:
            pass

    monkeypatch.delenv(SERVE_FILE_ENV, raising=False)
    monkeypatch.setattr("textual_serve.server.Server", FakeServer)
    monkeypatch.setattr(
        sys, "argv", ["jlv", "--serve", "-f", "--", "x.jsonl; touch PWNED"]
    )

    app_module.main()

    assert servers == [
        {
            "command": build_serve_command(follow=True),
            "title": "jlv x.jsonl; touch PWNED",
        }
    ]
    assert json.loads(os.environ[SERVE_FILE_ENV]) == ["x.jsonl; touch PWNED"]


def test_main_child_reads_file_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[dict[str, Any]] = []

    class FakeApp:
        def __init__(self, **kwargs: Any) -> None:  # noqa: ANN401
            created.append(kwargs)

        def run(self) -> None:
            pass

    history = Path("/tmp/history.json")
    monkeypatch.setattr(app_module, "LogViewerApp", FakeApp)
    monkeypatch.setattr(app_module, "default_history_path", lambda: history)
    monkeypatch.setenv(SERVE_FILE_ENV, json.dumps(["a & b.jsonl", "c;d"]))
    monkeypatch.setattr(sys, "argv", ["jlv", "--follow"])

    app_module.main()

    assert created == [
        {
            "files": ["a & b.jsonl", "c;d"],
            "follow": True,
            "show_picker_on_start": False,
            "history_path": history,
        }
    ]
    # Consumed, so programs started from the app don't inherit it.
    assert SERVE_FILE_ENV not in os.environ


def test_module_is_runnable_with_python_m() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "json_logs_viewer", "--help"],
        capture_output=True,
        text=True,
        check=True,
    )

    assert "--serve" in result.stdout


def test_serve_without_extra_explains_how_to_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without the [serve] extra, --serve exits with an install hint."""
    # A None entry in sys.modules makes `import textual_serve...` fail.
    monkeypatch.setitem(sys.modules, "textual_serve", None)
    monkeypatch.setitem(sys.modules, "textual_serve.server", None)
    monkeypatch.setattr(sys, "argv", ["jlv", "--serve"])

    with pytest.raises(SystemExit) as exc_info:
        app_module.main()

    message = str(exc_info.value.code)
    assert "json-logs-viewer[serve]" in message


def test_no_history_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    created: list[dict[str, Any]] = []

    class FakeApp:
        def __init__(self, **kwargs: Any) -> None:  # noqa: ANN401
            created.append(kwargs)

        def run(self) -> None:
            pass

    monkeypatch.setattr(app_module, "LogViewerApp", FakeApp)
    monkeypatch.setattr(sys, "argv", ["jlv", "--no-history", "x.jsonl"])

    app_module.main()

    assert created[0]["history_path"] is None


def test_serve_command_passes_no_history_on() -> None:
    command = build_serve_command(follow=False, no_history=True, posix=True)
    assert shlex.split(command)[-1] == "--no-history"
