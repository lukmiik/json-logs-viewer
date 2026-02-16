"""Integration tests for feature summary modal."""

from pathlib import Path

import pytest
from textual.containers import VerticalScroll
from textual.widgets import Static

from json_logs_viewer.app import LogViewerApp
from json_logs_viewer.widgets.feature_summary_modal import FeatureSummaryModal


@pytest.mark.asyncio
async def test_question_mark_opens_feature_summary_modal(
    sample_jsonl_file: Path,
) -> None:
    """Test that pressing '?' opens the feature summary modal."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()

        log_list = app.query_one("#logs")
        log_list.focus()
        await pilot.pause()

        await pilot.press("?")
        await pilot.pause()

        assert isinstance(app.screen, FeatureSummaryModal)


@pytest.mark.asyncio
async def test_escape_closes_feature_summary_modal(
    sample_jsonl_file: Path,
) -> None:
    """Test that Escape closes the feature summary modal."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_show_feature_summary()
        await pilot.pause()
        assert isinstance(app.screen, FeatureSummaryModal)

        await pilot.press("escape")
        await pilot.pause()

        assert not isinstance(app.screen, FeatureSummaryModal)


@pytest.mark.asyncio
async def test_system_command_opens_feature_summary_modal(
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

        assert isinstance(app.screen, FeatureSummaryModal)


@pytest.mark.asyncio
async def test_modal_displays_expected_content_and_metadata(
    sample_jsonl_file: Path,
) -> None:
    """Test that modal content and help labels are rendered."""
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_show_feature_summary()
        await pilot.pause()

        modal = app.screen
        assert isinstance(modal, FeatureSummaryModal)

        dialog = modal.query_one("#feature-summary-dialog", VerticalScroll)
        content = modal.query_one("#feature-summary-content", Static)

        assert dialog.size.width > 20
        assert dialog.size.height > 5
        assert str(dialog.border_title) == "Help"
        assert str(dialog.border_subtitle) == "ESCAPE to dismiss"
        assert "JSON Logs Viewer" in str(content.content)
