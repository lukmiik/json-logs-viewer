"""Screenshot (SVG) tests of the whole app.

Each test drives the app and compares the screen with an approved SVG in
`__snapshots__/`. When a change is intended, regenerate with
`uv run pytest tests/snapshots --snapshot-update` and review the new images
(open `snapshot_report.html` after a failing run to see the diff).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
from textual.pilot import Pilot

from json_logs_viewer.app import LogViewerApp

DATA_DIR = Path(__file__).parent / "data"
SIZE = (100, 24)

SnapCompare = Callable[..., bool]


def _keys(*keys: str) -> Callable[[Pilot], Awaitable[None]]:
    """Press keys, then let the screen settle before the screenshot.

    Opening a modal or focusing the search bar rebuilds the footer a moment
    later; without the wait the screenshot sometimes caught the footer half
    drawn (about 1 run in 15), making these snapshots flaky.
    """

    async def press(pilot: Pilot) -> None:
        await pilot.press(*keys)
        await pilot.pause(0.3)
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()

    return press


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> LogViewerApp:
    # The status bar shows the path as given; a bare name keeps snapshots
    # the same on every machine.
    monkeypatch.chdir(DATA_DIR)
    return LogViewerApp(file="app.jsonl")


def test_main_screen(snap_compare: SnapCompare, app: LogViewerApp) -> None:
    assert snap_compare(app, terminal_size=SIZE)


def test_search_bar_open(snap_compare: SnapCompare, app: LogViewerApp) -> None:
    assert snap_compare(
        app, run_before=_keys("/", *"level:err"), terminal_size=SIZE
    )


def test_filter_applied(snap_compare: SnapCompare, app: LogViewerApp) -> None:
    assert snap_compare(
        app, run_before=_keys("/", *"level:error", "enter"), terminal_size=SIZE
    )


def test_highlight_mode(snap_compare: SnapCompare, app: LogViewerApp) -> None:
    assert snap_compare(
        app,
        run_before=_keys("/", *"level:error", "enter", "m"),
        terminal_size=SIZE,
    )


def test_wrap_mode(snap_compare: SnapCompare, app: LogViewerApp) -> None:
    assert snap_compare(app, run_before=_keys("w"), terminal_size=(60, 24))


def test_columns(snap_compare: SnapCompare, app: LogViewerApp) -> None:
    async def show_columns(pilot: Pilot) -> None:
        app.columns = ["level", "service", "http.status_code"]
        await pilot.pause()

    assert snap_compare(app, run_before=show_columns, terminal_size=SIZE)


def test_columns_modal(snap_compare: SnapCompare, app: LogViewerApp) -> None:
    """Nested fields are offered by their dotted path."""
    assert snap_compare(app, run_before=_keys("c"), terminal_size=SIZE)


def test_export_modal(snap_compare: SnapCompare, app: LogViewerApp) -> None:
    assert snap_compare(
        app,
        run_before=_keys("/", *"level:error", "enter", "e"),
        terminal_size=SIZE,
    )


def test_clear_confirm(snap_compare: SnapCompare, app: LogViewerApp) -> None:
    assert snap_compare(app, run_before=_keys("x"), terminal_size=SIZE)


def test_command_palette(snap_compare: SnapCompare, app: LogViewerApp) -> None:
    async def open_palette(pilot: Pilot) -> None:
        await pilot.press("ctrl+p")
        await pilot.pause(0.5)  # the palette shows itself once ready
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()

    assert snap_compare(app, run_before=open_palette, terminal_size=SIZE)


def test_two_files_merged(
    snap_compare: SnapCompare, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two files in one timeline, with the @file column and file count."""
    monkeypatch.chdir(DATA_DIR)
    app = LogViewerApp(files=["app.jsonl", "worker.jsonl"])

    async def show_file_column(pilot: Pilot) -> None:
        app.columns = ["@file", "@level"]
        await pilot.pause()

    assert snap_compare(app, run_before=show_file_column, terminal_size=SIZE)


def test_new_lines_badge(snap_compare: SnapCompare, app: LogViewerApp) -> None:
    """Lines arriving below the cursor show the badge; nothing moves."""

    async def read_older_lines_then_append(pilot: Pilot) -> None:
        await pilot.press("k", "k", "k")
        app._process_chunk(b'{"level": "INFO", "message": "new"}\n' * 3)
        await pilot.pause()

    assert snap_compare(
        app, run_before=read_older_lines_then_append, terminal_size=SIZE
    )


def test_detail_view(snap_compare: SnapCompare, app: LogViewerApp) -> None:
    # The cursor starts on the last line: go to the top, then to the entry
    # with a nested object.
    assert snap_compare(
        app, run_before=_keys("g", *"jjjj", "enter"), terminal_size=SIZE
    )


def test_help_modal(snap_compare: SnapCompare, app: LogViewerApp) -> None:
    assert snap_compare(
        app, run_before=_keys("question_mark"), terminal_size=SIZE
    )


def test_narrow_status_bar(
    snap_compare: SnapCompare, app: LogViewerApp
) -> None:
    """At 80 columns the file name shrinks first (ellipsis)."""
    assert snap_compare(
        app,
        run_before=_keys("/", *"level:error", "enter"),
        terminal_size=(80, 24),
    )
