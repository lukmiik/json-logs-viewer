"""Compressed files are read once; follow mode skips them."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from json_logs_viewer.app import LogViewerApp


@pytest.fixture
def rotated(tmp_path: Path) -> Path:
    path = tmp_path / "app.jsonl.1.gz"
    with gzip.open(path, "wt") as file:
        file.write(json.dumps({"ts": "2024-01-15T09:00:00Z", "msg": "old"}))
        file.write("\n")
    return path


@pytest.fixture
def current(tmp_path: Path) -> Path:
    path = tmp_path / "app.jsonl"
    path.write_text(
        json.dumps({"ts": "2024-01-15T10:00:00Z", "msg": "new"}) + "\n"
    )
    return path


@pytest.mark.asyncio
async def test_follow_watches_only_plain_files(
    rotated: Path, current: Path
) -> None:
    """Rotated archive + live file: the timeline, followed where possible."""
    app = LogViewerApp(files=[str(rotated), str(current)], follow=True)
    async with app.run_test() as pilot:
        await pilot.pause()

        assert [log.data["msg"] for log in app.logs] == ["old", "new"]
        assert app.follow_mode
        watched = {s.path: s.watcher is not None for s in app._sources}
        assert watched == {str(rotated): False, str(current): True}


@pytest.mark.asyncio
async def test_follow_with_only_compressed_files_explains(
    rotated: Path,
) -> None:
    app = LogViewerApp(file=str(rotated), follow=True)
    async with app.run_test(notifications=True) as pilot:
        await pilot.pause()

        assert not app.follow_mode
        messages = [n.message for n in app._notifications]
        assert any("Compressed files can't be followed" in m for m in messages)
