"""The search history file, shared by every log file you open."""

from __future__ import annotations

import json
from pathlib import Path

from platformdirs import user_data_path

from json_logs_viewer.atomic_file import atomic_open

_VERSION = 1


def default_history_path() -> Path:
    """history.json in the per-user data folder for this OS.

    ~/.local/share/json-logs-viewer on Linux (or $XDG_DATA_HOME),
    ~/Library/Application Support/json-logs-viewer on macOS and
    %LOCALAPPDATA%/json-logs-viewer on Windows.
    """
    return user_data_path("json-logs-viewer", appauthor=False) / "history.json"


def load_history(*, path: Path, limit: int) -> list[str]:
    """The saved queries, oldest first; [] if the file is missing or unusable.

    A damaged file must never stop the app from starting, so anything
    unexpected is ignored rather than raised.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(data, dict):
        return []
    queries = data.get("queries")
    if not isinstance(queries, list):
        return []
    return [query for query in queries if isinstance(query, str)][-limit:]


def save_history(*, path: Path, history: list[str]) -> None:
    """Write the history atomically, creating its folder if needed.

    Raises:
        OSError: The folder can't be created or written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # 0600 for a new file: queries can hold user IDs or tokens.
    with atomic_open(path=path, new_file_mode=0o600) as file:
        json.dump(
            {"version": _VERSION, "queries": history},
            file,
            ensure_ascii=False,
            indent=1,
        )
        file.write("\n")
