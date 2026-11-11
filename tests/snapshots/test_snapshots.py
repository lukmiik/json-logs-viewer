"""Screenshot (SVG) tests of the whole app.

Each test drives the app and compares the screen with an approved SVG in
`__snapshots__/`. When a change is intended, regenerate with
`uv run pytest tests/snapshots --snapshot-update` and review the new images
(open `snapshot_report.html` after a failing run to see the diff).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from textual.pilot import Pilot

from json_logs_viewer.app import LogViewerApp

DATA_DIR = Path(__file__).parent / "data"
SIZE = (100, 24)

SnapCompare = Callable[..., bool]


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> LogViewerApp:
    # The status bar shows the path as given; a bare name keeps snapshots
    # the same on every machine.
    monkeypatch.chdir(DATA_DIR)
    return LogViewerApp(file="app.jsonl")


def test_main_screen(snap_compare: SnapCompare, app: LogViewerApp) -> None:
    assert snap_compare(app, terminal_size=SIZE)


def test_search_bar_open(snap_compare: SnapCompare, app: LogViewerApp) -> None:
    assert snap_compare(app, press=["/", *"level:err"], terminal_size=SIZE)


def test_filter_applied(snap_compare: SnapCompare, app: LogViewerApp) -> None:
    assert snap_compare(
        app, press=["/", *"level:error", "enter"], terminal_size=SIZE
    )


def test_highlight_mode(snap_compare: SnapCompare, app: LogViewerApp) -> None:
    assert snap_compare(
        app, press=["/", *"level:error", "enter", "m"], terminal_size=SIZE
    )


def test_wrap_mode(snap_compare: SnapCompare, app: LogViewerApp) -> None:
    assert snap_compare(app, press=["w"], terminal_size=(60, 24))


def test_columns(snap_compare: SnapCompare, app: LogViewerApp) -> None:
    async def show_columns(pilot: Pilot) -> None:
        app.columns = ["level", "service"]
        await pilot.pause()

    assert snap_compare(app, run_before=show_columns, terminal_size=SIZE)


def test_detail_view(snap_compare: SnapCompare, app: LogViewerApp) -> None:
    # The cursor starts on the last line: go to the top, then to the entry
    # with a nested object.
    assert snap_compare(app, press=["g", *"jjjj", "enter"], terminal_size=SIZE)


def test_help_modal(snap_compare: SnapCompare, app: LogViewerApp) -> None:
    assert snap_compare(app, press=["question_mark"], terminal_size=SIZE)


def test_narrow_status_bar(
    snap_compare: SnapCompare, app: LogViewerApp
) -> None:
    """At 80 columns the file name shrinks first (ellipsis)."""
    assert snap_compare(
        app, press=["/", *"level:error", "enter"], terminal_size=(80, 24)
    )
