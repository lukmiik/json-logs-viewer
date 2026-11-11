"""Exporting the logs the query matches (e) to a JSONL file."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from textual.pilot import Pilot
from textual.widgets import Input, Label

from json_logs_viewer.app import LogViewerApp
from json_logs_viewer.modals.export_modal import ExportModal

LEVELS = ["INFO", "ERROR", "DEBUG", "ERROR", "INFO"]


@pytest.fixture
def log_file(tmp_path: Path) -> Path:
    path = tmp_path / "app.jsonl"
    path.write_text(
        "".join(
            json.dumps({"level": level, "i": i}) + "\n"
            for i, level in enumerate(LEVELS)
        )
    )
    return path


def _exported_levels(path: Path) -> list[str]:
    lines = path.read_text().splitlines()
    return [json.loads(line)["level"] for line in lines]


async def _filter(app: LogViewerApp, pilot: Pilot, query: str) -> None:
    app.filter_query = query
    await pilot.pause()


@pytest.mark.asyncio
async def test_export_writes_filtered_lines(log_file: Path) -> None:
    app = LogViewerApp(file=str(log_file))
    async with app.run_test() as pilot:
        await pilot.pause()
        await _filter(app, pilot, "level:error")

        await pilot.press("e")
        await pilot.pause()
        assert isinstance(app.screen, ExportModal)
        path_input = app.screen.query_one(Input)
        target = log_file.with_name("app.filtered.jsonl")
        assert path_input.value == str(target)

        await pilot.press("enter")
        await pilot.pause()

        assert not isinstance(app.screen, ExportModal)
        assert _exported_levels(target) == ["ERROR", "ERROR"]
        # Lines are written exactly as in the source file.
        source_lines = log_file.read_text().splitlines()
        assert target.read_text().splitlines() == [
            source_lines[1],
            source_lines[3],
        ]


@pytest.mark.asyncio
async def test_highlight_mode_exports_only_matches(log_file: Path) -> None:
    app = LogViewerApp(file=str(log_file))
    async with app.run_test() as pilot:
        await pilot.pause()
        await _filter(app, pilot, "level:error")
        app.highlight_matches = True
        await pilot.pause()
        assert len(app.filtered_logs) == len(LEVELS)  # all shown

        await pilot.press("e", "enter")
        await pilot.pause()

        target = log_file.with_name("app.filtered.jsonl")
        assert _exported_levels(target) == ["ERROR", "ERROR"]


@pytest.mark.asyncio
async def test_existing_file_needs_a_second_enter(log_file: Path) -> None:
    target = log_file.with_name("app.filtered.jsonl")
    target.write_text("keep me\n")
    app = LogViewerApp(file=str(log_file))
    async with app.run_test() as pilot:
        await pilot.pause()

        await pilot.press("e", "enter")
        await pilot.pause()
        assert isinstance(app.screen, ExportModal)
        warning = app.screen.query_one("#export-warning", Label)
        assert "exists" in str(warning.content)
        assert target.read_text() == "keep me\n"

        await pilot.press("enter")
        await pilot.pause()
        assert not isinstance(app.screen, ExportModal)
        assert len(_exported_levels(target)) == len(LEVELS)


@pytest.mark.asyncio
async def test_editing_the_path_resets_the_overwrite_warning(
    log_file: Path,
) -> None:
    target = log_file.with_name("app.filtered.jsonl")
    target.write_text("keep me\n")
    app = LogViewerApp(file=str(log_file))
    async with app.run_test() as pilot:
        await pilot.pause()

        await pilot.press("e", "enter")  # warned
        await pilot.press("backspace", *"l", "enter")  # same name, retyped
        await pilot.pause()

        assert isinstance(app.screen, ExportModal)
        assert target.read_text() == "keep me\n"


@pytest.mark.asyncio
async def test_escape_cancels(log_file: Path) -> None:
    app = LogViewerApp(file=str(log_file))
    async with app.run_test() as pilot:
        await pilot.pause()

        await pilot.press("e", "escape")
        await pilot.pause()

        assert not isinstance(app.screen, ExportModal)
        assert not log_file.with_name("app.filtered.jsonl").exists()


@pytest.mark.asyncio
async def test_nothing_to_export(log_file: Path) -> None:
    app = LogViewerApp(file=str(log_file))
    async with app.run_test() as pilot:
        await pilot.pause()
        await _filter(app, pilot, "level:nope")

        await pilot.press("e")
        await pilot.pause()

        assert not isinstance(app.screen, ExportModal)
        messages = [n.message for n in app._notifications]
        assert any("Nothing to export" in m for m in messages)


@pytest.mark.asyncio
async def test_write_error_is_reported(log_file: Path) -> None:
    app = LogViewerApp(file=str(log_file))
    async with app.run_test() as pilot:
        await pilot.pause()

        await pilot.press("e")
        await pilot.pause()
        path_input = app.screen.query_one(Input)
        path_input.value = str(log_file.parent / "no-such-dir" / "out.jsonl")
        await pilot.press("enter")
        await pilot.pause()

        assert any(
            n.severity == "error" and "Export failed" in n.message
            for n in app._notifications
        )
