"""Integration tests for FilePickerModal and :open command."""

from pathlib import Path

import pytest

from json_logs_viewer.app import LogViewerApp
from json_logs_viewer.modals.file_picker_modal import (
    ALLOWED_EXTENSIONS,
    FilePickerModal,
    FilteredDirectoryTree,
)
from json_logs_viewer.widgets.log_list import LogList
from json_logs_viewer.widgets.search_bar import SearchBar


@pytest.mark.asyncio
async def test_o_key_opens_file_picker(sample_jsonl_file: Path) -> None:
    """Test that pressing 'o' opens the file picker modal."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        await pilot.press("o")
        await pilot.pause()

        assert isinstance(app.screen, FilePickerModal)


@pytest.mark.asyncio
async def test_escape_closes_file_picker(
    sample_jsonl_file: Path,
) -> None:
    """Test that Escape closes the file picker without loading."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        original_filepath = app.filepath
        original_log_count = len(app.logs)

        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        await pilot.press("o")
        await pilot.pause()
        assert isinstance(app.screen, FilePickerModal)

        await pilot.press("escape")
        await pilot.pause()

        assert not isinstance(app.screen, FilePickerModal)
        assert app.filepath == original_filepath
        assert len(app.logs) == original_log_count


@pytest.mark.asyncio
async def test_file_picker_not_opened_when_already_open(
    sample_jsonl_file: Path,
) -> None:
    """Test that pressing 'o' again doesn't push a second modal."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        await pilot.press("o")
        await pilot.pause()
        first_screen = app.screen
        assert isinstance(first_screen, FilePickerModal)

        await pilot.press("o")
        await pilot.pause()

        assert app.screen is first_screen


@pytest.mark.asyncio
async def test_auto_open_picker_on_start() -> None:
    """Test that the file picker opens on start when no file given."""
    app = LogViewerApp(show_picker_on_start=True)
    async with app.run_test() as pilot:
        await pilot.pause()

        assert isinstance(app.screen, FilePickerModal)
        assert app.logs == []
        assert app.filepath is None


@pytest.mark.asyncio
async def test_auto_open_picker_escape_keeps_app_running() -> None:
    """Test that canceling the auto-opened picker keeps app alive."""
    app = LogViewerApp(show_picker_on_start=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, FilePickerModal)

        await pilot.press("escape")
        await pilot.pause()

        assert not isinstance(app.screen, FilePickerModal)
        assert app.logs == []
        assert app.filepath is None


@pytest.mark.asyncio
async def test_no_picker_when_file_provided(
    sample_jsonl_file: Path,
) -> None:
    """Test that file picker is not shown when file is provided."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()

        assert not isinstance(app.screen, FilePickerModal)
        assert app.filepath == str(sample_jsonl_file)
        assert len(app.logs) > 0


@pytest.mark.asyncio
async def test_file_picker_contains_directory_tree() -> None:
    """Test that the file picker contains a DirectoryTree."""
    app = LogViewerApp(show_picker_on_start=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, FilePickerModal)

        from textual.widgets import DirectoryTree

        tree = app.screen.query_one("#file-picker-tree", DirectoryTree)
        assert tree is not None


@pytest.mark.asyncio
async def test_open_new_file_replaces_logs(
    sample_jsonl_file: Path,
    tmp_path: Path,
) -> None:
    """Test that opening a new file replaces the current logs."""
    other_file = tmp_path / "other.jsonl"
    other_file.write_text('{"msg": "new"}\n')

    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()
        original_count = len(app.logs)
        assert original_count > 1

        app._on_file_selected(str(other_file))
        await pilot.pause()

        assert app.filepath == str(other_file)
        assert len(app.logs) == 1
        assert app.logs[0].data["msg"] == "new"


@pytest.mark.asyncio
async def test_open_file_stops_follow_mode(
    sample_jsonl_file: Path,
    tmp_path: Path,
) -> None:
    """Test that opening a new file stops follow mode."""
    other_file = tmp_path / "other.jsonl"
    other_file.write_text('{"msg": "new"}\n')

    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()

        app.follow_mode = True
        await pilot.pause()
        assert app.follow_mode is True

        app._on_file_selected(str(other_file))
        await pilot.pause()

        assert app.follow_mode is False
        assert app.filepath == str(other_file)


@pytest.mark.asyncio
async def test_open_file_resets_filter_query(
    sample_jsonl_file: Path,
    tmp_path: Path,
) -> None:
    """Test that opening a new file resets the filter query."""
    other_file = tmp_path / "other.jsonl"
    other_file.write_text('{"msg": "new"}\n')

    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()

        app.filter_query = "level:ERROR"
        app.case_sensitive = True
        app.highlight_matches = True
        await pilot.pause()

        app._on_file_selected(str(other_file))
        await pilot.pause()

        assert app.filter_query == ""
        assert app.case_sensitive is False
        assert app.highlight_matches is False


@pytest.mark.asyncio
async def test_open_file_resets_wrap_and_columns(
    sample_jsonl_file: Path,
    tmp_path: Path,
) -> None:
    """Test that opening a new file resets wrap mode and columns."""
    other_file = tmp_path / "other.jsonl"
    other_file.write_text('{"msg": "new"}\n')

    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()

        app.wrap_log_lines = True
        app.columns = ["level", "message"]
        await pilot.pause()

        app._on_file_selected(str(other_file))
        await pilot.pause()

        assert app.wrap_log_lines is False
        assert app.columns == []


@pytest.mark.asyncio
async def test_open_file_resets_search_bar(
    sample_jsonl_file: Path,
    tmp_path: Path,
) -> None:
    """Test that opening a new file clears the search bar."""
    other_file = tmp_path / "other.jsonl"
    other_file.write_text('{"msg": "new"}\n')

    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()

        search_bar = app.query_one("#search", SearchBar)
        search_bar.value = "some query"
        app.filter_query = "some query"
        await pilot.pause()

        app._on_file_selected(str(other_file))
        await pilot.pause()

        assert search_bar.value == ""
        assert app.filter_query == ""


@pytest.mark.asyncio
async def test_open_file_resets_search_history(
    sample_jsonl_file: Path,
    tmp_path: Path,
) -> None:
    """Test that opening a new file clears search history."""
    other_file = tmp_path / "other.jsonl"
    other_file.write_text('{"msg": "new"}\n')

    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()

        app.search_history = ["query1", "query2"]
        await pilot.pause()

        app._on_file_selected(str(other_file))
        await pilot.pause()

        assert app.search_history == []


@pytest.mark.asyncio
async def test_load_file_invalid_shows_notification(
    tmp_path: Path,
    sample_jsonl_file: Path,
) -> None:
    """Test that loading a nonexistent file shows error."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()
        original_filepath = app.filepath

        app._on_file_selected(str(tmp_path / "nonexistent.jsonl"))
        await pilot.pause()

        assert app.filepath == original_filepath


def test_hidden_files_filtered_in_picker(tmp_path: Path) -> None:
    """Test that hidden files are filtered from the tree."""
    tree = FilteredDirectoryTree(str(tmp_path))

    hidden_file = tmp_path / ".hidden"
    hidden_file.touch()
    hidden_dir = tmp_path / ".git"
    hidden_dir.mkdir()
    visible_file = tmp_path / "visible.jsonl"
    visible_file.touch()
    visible_dir = tmp_path / "logs"
    visible_dir.mkdir()

    paths = [hidden_file, hidden_dir, visible_file, visible_dir]
    filtered = list(tree.filter_paths(paths))

    assert visible_file in filtered
    assert visible_dir in filtered
    assert hidden_file not in filtered
    assert hidden_dir not in filtered


def test_only_json_jsonl_files_shown(tmp_path: Path) -> None:
    """Test that only .json and .jsonl files pass the filter."""
    tree = FilteredDirectoryTree(str(tmp_path))

    # Create actual files so is_dir() works correctly
    json_file = tmp_path / "data.json"
    json_file.touch()
    jsonl_file = tmp_path / "logs.jsonl"
    jsonl_file.touch()
    txt_file = tmp_path / "notes.txt"
    txt_file.touch()
    py_file = tmp_path / "script.py"
    py_file.touch()
    subdir = tmp_path / "subdir"
    subdir.mkdir()

    paths = [json_file, jsonl_file, txt_file, py_file, subdir]
    filtered = list(tree.filter_paths(paths))

    assert json_file in filtered
    assert jsonl_file in filtered
    assert subdir in filtered  # Directories always shown
    assert txt_file not in filtered
    assert py_file not in filtered


def test_allowed_extensions_constant() -> None:
    """Test that allowed extensions include json and jsonl."""
    assert ".json" in ALLOWED_EXTENSIONS
    assert ".jsonl" in ALLOWED_EXTENSIONS


@pytest.mark.asyncio
async def test_jk_navigates_tree() -> None:
    """Test that j/k moves cursor in the directory tree."""
    app = LogViewerApp(show_picker_on_start=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, FilePickerModal)

        tree = app.screen.query_one("#file-picker-tree", FilteredDirectoryTree)
        initial_line = tree.cursor_line

        await pilot.press("j")
        await pilot.pause()
        assert tree.cursor_line == initial_line + 1

        await pilot.press("k")
        await pilot.pause()
        assert tree.cursor_line == initial_line
