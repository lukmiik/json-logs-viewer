"""The search history survives restarts (history_path) and file changes."""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.pilot import Pilot
from textual.widgets import Input

from json_logs_viewer import history_store
from json_logs_viewer.app import LogViewerApp
from json_logs_viewer.history_store import load_history, save_history
from json_logs_viewer.modals.confirm_modal import ConfirmModal


async def _search(pilot: Pilot, query: str) -> None:
    await pilot.press("/")
    # The search bar keeps the previous query when reopened.
    pilot.app.query_one("#search", Input).value = ""
    await pilot.press(*query, "enter")
    await pilot.pause()


@pytest.mark.asyncio
async def test_history_is_loaded_and_saved(
    sample_jsonl_file: Path, tmp_path: Path
) -> None:
    history_file = tmp_path / "history.json"
    save_history(path=history_file, history=["from last time"])
    app = LogViewerApp(file=str(sample_jsonl_file), history_path=history_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.search_history == ["from last time"]

        await _search(pilot, "error")

    assert load_history(path=history_file, limit=100) == [
        "from last time",
        "error",
    ]


@pytest.mark.asyncio
async def test_opening_another_file_keeps_the_history(
    sample_jsonl_file: Path, tmp_path: Path
) -> None:
    app = LogViewerApp(
        file=str(sample_jsonl_file), history_path=tmp_path / "history.json"
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        await _search(pilot, "error")

        app._on_file_selected(str(sample_jsonl_file))
        await pilot.pause()

        assert app.search_history == ["error"]


@pytest.mark.asyncio
async def test_clear_history_command(
    sample_jsonl_file: Path, tmp_path: Path
) -> None:
    history_file = tmp_path / "history.json"
    save_history(path=history_file, history=["a", "b"])
    app = LogViewerApp(file=str(sample_jsonl_file), history_path=history_file)
    async with app.run_test() as pilot:
        await pilot.pause()

        app.action_clear_history()
        await pilot.pause()
        assert isinstance(app.screen, ConfirmModal)
        await pilot.press("y")
        await pilot.pause()

        assert app.search_history == []
    assert load_history(path=history_file, limit=100) == []


@pytest.mark.asyncio
async def test_without_history_path_nothing_is_written(
    sample_jsonl_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The default (tests, --no-history) keeps history in memory only."""
    real_default = tmp_path / "default" / "history.json"
    monkeypatch.setattr(
        history_store, "default_history_path", lambda: real_default
    )
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()
        await _search(pilot, "error")
        assert app.search_history == ["error"]
    assert not real_default.exists()


@pytest.mark.asyncio
async def test_save_error_warns_and_keeps_working(
    sample_jsonl_file: Path, tmp_path: Path
) -> None:
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("a file where the folder should be")
    app = LogViewerApp(
        file=str(sample_jsonl_file), history_path=blocker / "history.json"
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        await _search(pilot, "error")
        await _search(pilot, "timeout")

        assert app.search_history == ["error", "timeout"]
        warnings = [
            n.message
            for n in app._notifications
            if "search history" in n.message
        ]
        assert len(warnings) == 1  # warned once, not on every query
