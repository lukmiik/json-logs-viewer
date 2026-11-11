"""Several log files open at once, merged into one timeline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from textual.widgets import DirectoryTree, Input

from json_logs_viewer.app import LogViewerApp
from json_logs_viewer.modals.detail_modal import DetailModal
from json_logs_viewer.modals.export_modal import ExportModal
from json_logs_viewer.modals.file_picker_modal import FilePickerModal
from json_logs_viewer.widgets.log_list import LogList
from json_logs_viewer.widgets.status_bar import StatusInfo


def _write(path: Path, *rows: tuple[str, str]) -> Path:
    path.write_text(
        "".join(
            json.dumps({"timestamp": f"2024-01-15T10:{t}Z", "msg": msg}) + "\n"
            for t, msg in rows
        )
    )
    return path


@pytest.fixture
def api(tmp_path: Path) -> Path:
    return _write(tmp_path / "api.jsonl", ("00:01", "a1"), ("00:05", "a2"))


@pytest.fixture
def worker(tmp_path: Path) -> Path:
    return _write(tmp_path / "worker.jsonl", ("00:02", "w1"), ("00:09", "w2"))


def _msgs(app: LogViewerApp) -> list[str]:
    return [log.data["msg"] for log in app.logs]


@pytest.mark.asyncio
async def test_files_are_merged_by_time(api: Path, worker: Path) -> None:
    app = LogViewerApp(files=[str(api), str(worker)])
    async with app.run_test() as pilot:
        await pilot.pause()

        assert _msgs(app) == ["a1", "w1", "a2", "w2"]
        assert [log.line_number for log in app.logs] == [1, 1, 2, 2]
        assert app.filepaths == [str(api), str(worker)]
        assert app.filepath == str(api)
        filename = app.query_one(StatusInfo).filename
        assert filename == f"{api} +1 file"


@pytest.mark.asyncio
async def test_file_column(api: Path, worker: Path) -> None:
    app = LogViewerApp(files=[str(api), str(worker)])
    async with app.run_test(size=(100, 12)) as pilot:
        await pilot.pause()
        assert app.discover_fields()[0] == "@file"

        app.columns = ["@file"]
        await pilot.pause()
        log_list = app.query_one("#logs", LogList)
        await pilot.press("g")
        await pilot.pause()

        def row(y: int) -> str:
            return "".join(s.text for s in log_list.render_line(y))

        assert row(0).startswith("api.jsonl    | ")
        assert row(1).startswith("worker.jsonl | ")


@pytest.mark.asyncio
async def test_file_column_not_offered_for_one_file(api: Path) -> None:
    app = LogViewerApp(file=str(api))
    async with app.run_test() as pilot:
        await pilot.pause()
        assert "@file" not in app.discover_fields()


@pytest.mark.asyncio
async def test_follow_appends_from_each_file(api: Path, worker: Path) -> None:
    app = LogViewerApp(files=[str(api), str(worker)])
    async with app.run_test() as pilot:
        await pilot.pause()
        api_source, worker_source = app._sources

        app._process_chunk(
            b'{"timestamp": "2024-01-15T10:10:00Z", "msg": "w3"}\n',
            source=worker_source,
        )
        app._process_chunk(
            b'{"timestamp": "2024-01-15T10:11:00Z", "msg": "a3"}\n',
            source=api_source,
        )
        await pilot.pause()

        new = app.logs[-2:]
        assert [log.data["msg"] for log in new] == ["w3", "a3"]
        assert [log.source for log in new] == [str(worker), str(api)]
        assert [log.line_number for log in new] == [3, 3]


@pytest.mark.asyncio
async def test_follow_watches_every_file(api: Path, worker: Path) -> None:
    app = LogViewerApp(files=[str(api), str(worker)], follow=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert all(source.watcher is not None for source in app._sources)

        app.follow_mode = False
        await pilot.pause()
        assert all(source.watcher is None for source in app._sources)


@pytest.mark.asyncio
async def test_picker_adds_a_file_keeping_the_query(
    api: Path, worker: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(api.parent)
    app = LogViewerApp(file=str(api))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        app.filter_query = "msg:2"
        await pilot.pause()

        await pilot.press("o")
        await pilot.pause()
        picker = app.screen
        assert isinstance(picker, FilePickerModal)
        tree = picker.query_one(DirectoryTree)
        await pilot.pause(0.3)  # the tree loads the folder asynchronously
        node = next(
            n for n in tree._tree_lines if str(n.node.label) == worker.name
        )
        tree.move_cursor(node.node)
        await pilot.press("a")
        await pilot.pause()

        assert not isinstance(app.screen, FilePickerModal)
        assert app.filepaths == [str(api), str(worker)]
        assert app.filter_query == "msg:2"
        assert [log.data["msg"] for log in app.filtered_logs] == ["a2", "w2"]


@pytest.mark.asyncio
async def test_export_name_for_several_files(api: Path, worker: Path) -> None:
    app = LogViewerApp(files=[str(api), str(worker)])
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()

        assert isinstance(app.screen, ExportModal)
        expected = api.with_name("combined.filtered.jsonl")
        assert app.screen.query_one(Input).value == str(expected)


@pytest.mark.asyncio
async def test_detail_view_shows_file_and_line(
    api: Path, worker: Path
) -> None:
    app = LogViewerApp(files=[str(api), str(worker)])
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("enter")  # cursor on the last line: w2
        await pilot.pause()
        assert isinstance(app.screen, DetailModal)

        dialog = app.screen.query_one("#detail-dialog")
        assert str(dialog.border_title) == f"Log Detail · {worker}:2"

        await pilot.press("k")  # a2
        await pilot.pause()
        assert str(dialog.border_title) == f"Log Detail · {api}:2"


@pytest.mark.asyncio
async def test_one_file_under_two_names_opens_once(
    api: Path, worker: Path
) -> None:
    other_spelling = api.parent / ".." / api.parent.name / api.name
    link = api.with_name("link.jsonl")
    link.symlink_to(api)
    app = LogViewerApp(files=[str(api), str(other_spelling), str(link)])
    async with app.run_test(notifications=True) as pilot:
        await pilot.pause()
        assert app.filepaths == [str(api)]
        assert _msgs(app) == ["a1", "a2"]

        app._add_file(filepath=str(api.parent / "." / api.name))
        await pilot.pause()

        assert app.filepaths == [str(api)]
        assert any("Already open" in n.message for n in app._notifications)


@pytest.mark.asyncio
async def test_follow_failing_on_one_file_doesnt_freeze(
    api: Path, worker: Path
) -> None:
    """A later file failing to open must not freeze the UI for 1 s.

    A watcher already waiting with data is released, not joined until its
    timeout.
    """
    import time

    app = LogViewerApp(files=[str(api), str(worker)])
    async with app.run_test(notifications=True) as pilot:
        await pilot.pause()
        with api.open("a") as file:
            file.write('{"msg": "pending"}\n')
        worker.unlink()

        started = time.perf_counter()
        app.follow_mode = True
        await pilot.pause()
        elapsed = time.perf_counter() - started

        assert not app.follow_mode
        assert all(source.watcher is None for source in app._sources)
        assert elapsed < 0.5
        assert any("Can't follow" in n.message for n in app._notifications)
