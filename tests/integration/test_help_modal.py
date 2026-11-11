"""Integration tests for help modal."""

from pathlib import Path

import pytest
from textual.widgets import TextArea

from json_logs_viewer.app import LogViewerApp
from json_logs_viewer.modals.help_modal import HelpModal


@pytest.mark.asyncio
async def test_question_mark_opens_help_modal(
    sample_jsonl_file: Path,
) -> None:
    """Test that pressing '?' opens the help modal."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()

        log_list = app.query_one("#logs")
        log_list.focus()
        await pilot.pause()

        await pilot.press("?")
        await pilot.pause()

        assert isinstance(app.screen, HelpModal)


@pytest.mark.asyncio
async def test_escape_closes_help_modal(
    sample_jsonl_file: Path,
) -> None:
    """Test that Escape closes the help modal."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_show_help()
        await pilot.pause()
        assert isinstance(app.screen, HelpModal)

        await pilot.press("escape")
        await pilot.pause()

        assert not isinstance(app.screen, HelpModal)


@pytest.mark.asyncio
async def test_system_command_opens_help_modal(
    sample_jsonl_file: Path,
) -> None:
    """Test that command palette command exists and opens the modal."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()

        system_commands = list(app.get_system_commands(screen=app.screen))
        summary_title = "Show help"
        command = next(
            cmd for cmd in system_commands if cmd.title == summary_title
        )
        command.callback()
        await pilot.pause()

        assert isinstance(app.screen, HelpModal)


@pytest.mark.asyncio
async def test_modal_displays_expected_content_and_metadata(
    sample_jsonl_file: Path,
) -> None:
    """Test that modal content and help labels are rendered."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_show_help()
        await pilot.pause()

        modal = app.screen
        assert isinstance(modal, HelpModal)

        dialog = modal.query_one("#feature-summary-content", TextArea)

        assert dialog.size.width > 20
        assert dialog.size.height > 5
        assert str(dialog.border_title) == "Help"
        assert str(dialog.border_subtitle) == "ESCAPE to dismiss"
        assert "JSON Logs Viewer" in str(dialog.text)


@pytest.mark.asyncio
async def test_help_modal_css_applies(sample_jsonl_file: Path) -> None:
    """DEFAULT_CSS selects by class name, so a rename must keep it working."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test(size=(120, 40)) as pilot:
        app.action_show_help()
        await pilot.pause()
        text_area = app.screen.query_one(TextArea)
        assert text_area.outer_size.width == 80
