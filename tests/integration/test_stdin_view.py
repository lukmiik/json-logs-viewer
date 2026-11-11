"""Piped input is shown as "stdin", not as its temporary file path."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from textual.widgets import Input

from json_logs_viewer.app import LogViewerApp
from json_logs_viewer.modals.detail_modal import DetailModal
from json_logs_viewer.modals.export_modal import ExportModal
from json_logs_viewer.widgets.log_list import LogList
from json_logs_viewer.widgets.status_bar import StatusInfo


@pytest.fixture
def stdin_copy(tmp_path: Path) -> Path:
    """Stands in for StdinCopy's file: <private temp dir>/stdin."""
    path = tmp_path / "jlv-x" / "stdin"
    path.parent.mkdir()
    path.write_text(
        json.dumps({"msg": "a"}) + "\n" + json.dumps({"msg": "b"}) + "\n"
    )
    return path


@pytest.mark.asyncio
async def test_stdin_is_named_stdin(
    stdin_copy: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    worker = tmp_path / "worker.jsonl"
    worker.write_text(json.dumps({"msg": "w"}) + "\n")
    app = LogViewerApp(
        files=[str(stdin_copy), str(worker)], stdin_path=str(stdin_copy)
    )
    async with app.run_test(size=(100, 12)) as pilot:
        await pilot.pause()

        assert app.query_one(StatusInfo).filename == "stdin +1 file"

        app.columns = ["@file"]
        await pilot.pause()
        rows = {
            "".join(
                s.text for s in app.query_one("#logs", LogList).render_line(y)
            )[:6]
            for y in range(3)
        }
        assert "stdin " in rows

        app.selected_index = next(
            i for i, log in enumerate(app.logs) if log.data["msg"] == "b"
        )
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, DetailModal)
        title = str(app.screen.query_one("#detail-dialog").border_title)
        assert title == "Log Detail · stdin:2"


@pytest.mark.asyncio
async def test_export_from_stdin_defaults_to_the_current_folder(
    stdin_copy: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Not into the temporary folder, which is deleted on exit."""
    monkeypatch.chdir(tmp_path)
    app = LogViewerApp(files=[str(stdin_copy)], stdin_path=str(stdin_copy))
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()

        assert isinstance(app.screen, ExportModal)
        target = Path(app.screen.query_one(Input).value)
        assert target == tmp_path / "stdin.filtered.jsonl"
