"""Inline suggestions in the search bar, with real logs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from textual.pilot import Pilot

from json_logs_viewer.app import LogViewerApp
from json_logs_viewer.widgets.search_bar import SearchBar


@pytest.fixture
def log_file(tmp_path: Path) -> Path:
    path = tmp_path / "app.jsonl"
    path.write_text(
        "".join(
            json.dumps(
                {
                    "request_id": f"req-{i}",
                    "attributes": {"level": ["error", "warning"][i % 2]},
                }
            )
            + "\n"
            for i in range(60)
        )
    )
    return path


async def _type(pilot: Pilot, text: str) -> SearchBar:
    await pilot.press("slash", *text)
    await pilot.pause()
    return pilot.app.query_one(SearchBar)


@pytest.mark.asyncio
async def test_field_then_value_with_right_arrow(log_file: Path) -> None:
    app = LogViewerApp(file=str(log_file))
    async with app.run_test() as pilot:
        bar = await _type(pilot, "attr")
        assert bar._suggestion == "attributes.level:"

        await pilot.press("right")
        assert bar.value == "attributes.level:"

        await pilot.press("w")
        await pilot.pause()
        assert bar._suggestion == "attributes.level:warning"


@pytest.mark.asyncio
async def test_tab_accepts(log_file: Path) -> None:
    app = LogViewerApp(file=str(log_file))
    async with app.run_test() as pilot:
        bar = await _type(pilot, "attr")

        await pilot.press("tab")

        assert bar.value == "attributes.level:"
        assert bar.has_focus


@pytest.mark.asyncio
async def test_many_distinct_values_are_not_suggested(log_file: Path) -> None:
    """60 different request IDs: suggesting one of them is noise."""
    app = LogViewerApp(file=str(log_file))
    async with app.run_test() as pilot:
        bar = await _type(pilot, "request_id:req")
        assert bar._suggestion == ""


@pytest.mark.asyncio
async def test_history_is_suggested(log_file: Path) -> None:
    app = LogViewerApp(file=str(log_file))
    async with app.run_test() as pilot:
        app.search_history = ["attributes.level:error request_id:req-7"]
        bar = await _type(pilot, "attributes.level:error r")
        assert bar._suggestion == "attributes.level:error request_id:req-7"


@pytest.mark.asyncio
async def test_at_sign_fields_are_suggested(tmp_path: Path) -> None:
    path = tmp_path / "ecs.jsonl"
    path.write_text('{"@timestamp": "2024-01-15T10:00:00Z", "message": "m"}\n')
    app = LogViewerApp(file=str(path))
    async with app.run_test() as pilot:
        bar = await _type(pilot, "@t")
        assert bar._suggestion == "@timestamp:"
