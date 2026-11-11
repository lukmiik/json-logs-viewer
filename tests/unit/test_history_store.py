"""Saving and loading the search history file."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from json_logs_viewer.history_store import (
    default_history_path,
    load_history,
    save_history,
)


def test_default_path_is_in_the_user_data_folder() -> None:
    path = default_history_path()
    assert path.name == "history.json"
    assert path.parent.name == "json-logs-viewer"


def test_round_trip_creates_folders(tmp_path: Path) -> None:
    path = tmp_path / "deep" / "dir" / "history.json"

    save_history(path=path, history=["level:error", "timeout"])

    assert load_history(path=path, limit=100) == ["level:error", "timeout"]
    assert json.loads(path.read_text())["version"] == 1


@pytest.mark.skipif(os.name != "posix", reason="POSIX file modes")
def test_file_is_private(tmp_path: Path) -> None:
    """Queries can hold user IDs or tokens: only the owner may read them."""
    path = tmp_path / "history.json"
    save_history(path=path, history=["user_id:42"])
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


@pytest.mark.parametrize(
    "content",
    [
        None,  # missing file
        "not json",
        '{"version": 1}',
        '{"version": 1, "queries": "nope"}',
        "[1, 2, 3]",
    ],
)
def test_unusable_file_loads_as_empty(
    tmp_path: Path, content: str | None
) -> None:
    path = tmp_path / "history.json"
    if content is not None:
        path.write_text(content)
    assert load_history(path=path, limit=100) == []


def test_load_keeps_strings_and_the_newest_entries(tmp_path: Path) -> None:
    path = tmp_path / "history.json"
    path.write_text(
        json.dumps({"version": 1, "queries": ["a", 2, None, "b", "c", "d"]})
    )
    assert load_history(path=path, limit=2) == ["c", "d"]
