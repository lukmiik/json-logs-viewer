"""Text from logs, files and queries is shown as text, never as markup.

Textual parses strings given to labels, toasts, titles and lists as
markup, so "[/api]" (a closing tag with nothing to close) crashed the app.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from textual.widgets import Input

from json_logs_viewer.app import LogViewerApp
from json_logs_viewer.modals.detail_modal import DetailModal
from json_logs_viewer.modals.export_modal import ExportModal
from json_logs_viewer.widgets.status_bar import StatusInfo

ODD = "[/api]"


@pytest.fixture
def log_file(tmp_path: Path) -> Path:
    path = tmp_path / "[b]app.jsonl"
    path.write_text(json.dumps({"path": f"/v1{ODD}/users"}) + "\n")
    return path


@pytest.mark.asyncio
async def test_query_with_brackets(log_file: Path) -> None:
    app = LogViewerApp(file=str(log_file))
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("slash", *f'"{ODD}"', "enter")
        await pilot.pause()

        assert len(app.filtered_logs) == 1
        assert app.query_one(StatusInfo).active_query == f'"{ODD}"'


@pytest.mark.asyncio
async def test_file_name_and_detail_title_with_brackets(
    log_file: Path,
) -> None:
    app = LogViewerApp(file=str(log_file))
    async with app.run_test(size=(160, 30)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, DetailModal)
        title = app.screen.query_one("#detail-dialog").border_title
        assert str(title).endswith("[b]app.jsonl:1")


@pytest.mark.asyncio
async def test_toast_with_brackets(log_file: Path) -> None:
    app = LogViewerApp(file=str(log_file))
    async with app.run_test(notifications=True) as pilot:
        await pilot.pause()
        app.load_files(filepaths=[f"missing{ODD}.jsonl"])
        await pilot.pause()

        assert any(ODD in n.message for n in app._notifications)


@pytest.mark.asyncio
async def test_export_warning_with_brackets(log_file: Path) -> None:
    taken = log_file.with_name(f"out{ODD.replace('/', '_')}.jsonl")
    taken.write_text("x\n")
    app = LogViewerApp(file=str(log_file))
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        assert isinstance(app.screen, ExportModal)
        app.screen.query_one(Input).value = str(taken)
        await pilot.press("enter")
        await pilot.pause()

        warning = app.screen.query_one("#export-warning")
        assert taken.name in str(warning.content)
