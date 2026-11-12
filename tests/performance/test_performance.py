"""Performance tests for virtual scrolling and log loading."""

import json
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from json_logs_viewer.app import LogViewerApp
from json_logs_viewer.widgets.log_list import LogList

VERY_LARGE_SAMPLE = (
    Path(__file__).parent.parent.parent
    / "test_files"
    / "very_large_sample.jsonl"
)
LARGE_SAMPLE = (
    Path(__file__).parent.parent.parent / "test_files" / "large_sample.jsonl"
)


@pytest.fixture
def large_jsonl_file() -> Path:
    """Return path to 10K line test file."""
    if not VERY_LARGE_SAMPLE.exists():
        raise FileNotFoundError(
            f"Performance test file not found: {VERY_LARGE_SAMPLE}"
        )
    return VERY_LARGE_SAMPLE


@pytest.fixture
def medium_jsonl_file() -> Path:
    """Return path to 1K line test file."""
    if not LARGE_SAMPLE.exists():
        raise FileNotFoundError(
            f"Performance test file not found: {LARGE_SAMPLE}"
        )
    return LARGE_SAMPLE


@pytest.mark.performance
@pytest.mark.asyncio
async def test_large_file_loads_under_3_seconds(
    large_jsonl_file: Path,
) -> None:
    """10K entries should load in under 3 seconds.

    Virtual scroll should make this instant compared to the
    ~50 seconds it took with ListView + DOM widgets.
    """
    app = LogViewerApp(file=str(large_jsonl_file))

    t0 = time.perf_counter()
    async with app.run_test() as pilot:
        await pilot.pause()
        elapsed = time.perf_counter() - t0

        log_list = app.query_one("#logs", LogList)
        assert len(log_list._log_entries) == 10_000
        assert elapsed < 3.0, f"Load took {elapsed:.2f}s, expected < 3.0s"


@pytest.mark.performance
@pytest.mark.asyncio
async def test_only_visible_lines_rendered(
    large_jsonl_file: Path,
) -> None:
    """Verify render_line is only called for visible lines, not all 10K.

    Virtual scroll should only render ~40-50 visible lines,
    not all 10,000 entries.
    """
    app = LogViewerApp(file=str(large_jsonl_file))

    render_count = 0
    original_render = LogList.render_line

    def counting_render(self: LogList, y: int) -> object:
        nonlocal render_count
        render_count += 1
        return original_render(self, y)

    with patch.object(LogList, "render_line", counting_render):
        async with app.run_test() as pilot:
            await pilot.pause()

            log_list = app.query_one("#logs", LogList)
            assert len(log_list._log_entries) == 10_000

            assert render_count < 100, (
                f"render_line called {render_count} times, "
                f"expected < 100 (only visible lines)"
            )


@pytest.mark.performance
@pytest.mark.asyncio
async def test_line_cache_prevents_reserialization(
    medium_jsonl_file: Path,
) -> None:
    """Verify LRU cache prevents redundant json.dumps calls.

    Once a line is cached, scrolling back to it should not
    trigger another json.dumps serialization.
    """
    app = LogViewerApp(file=str(medium_jsonl_file))

    dumps_calls: list[str] = []
    original_dumps = json.dumps

    def counting_dumps(obj: object, **kwargs: Any) -> str:  # noqa: ANN401
        result = original_dumps(obj, **kwargs)
        dumps_calls.append(result[:50])
        return result

    with patch("json.dumps", counting_dumps):
        async with app.run_test() as pilot:
            log_list = app.query_one("#logs", LogList)
            log_list.focus()
            await pilot.pause()

            initial_calls = len(dumps_calls)

            await pilot.press("j", "j", "j", "j", "j")
            await pilot.pause()

            await pilot.press("k", "k", "k", "k", "k")
            await pilot.pause()

            final_calls = len(dumps_calls)

            assert final_calls < initial_calls + 20, (
                f"json.dumps called {final_calls - initial_calls} extra times "
                f"during navigation, cache should prevent re-serialization"
            )


@pytest.mark.performance
@pytest.mark.asyncio
async def test_scroll_to_bottom_instant(
    large_jsonl_file: Path,
) -> None:
    """Scrolling to bottom of 10K file should be instant.

    With virtual scroll, jumping to the last entry should
    not require traversing all 10,000 entries.
    """
    app = LogViewerApp(file=str(large_jsonl_file))

    async with app.run_test() as pilot:
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        log_list.scroll_to(y=0, animate=False)
        log_list._cursor_index = 0
        await pilot.pause()

        t0 = time.perf_counter()
        await pilot.press("G")
        await pilot.pause()
        elapsed = time.perf_counter() - t0

        assert log_list._cursor_index == 9_999
        assert elapsed < 0.5, (
            f"Scroll to bottom took {elapsed:.3f}s, expected < 0.5s"
        )


@pytest.mark.performance
@pytest.mark.asyncio
async def test_line_cache_has_limited_size(
    large_jsonl_file: Path,
) -> None:
    """Verify LRU cache size is bounded, not growing with log count.

    Memory usage should be O(cache_size), not O(log_count).
    The default cache size is 2000 entries.
    """
    app = LogViewerApp(file=str(large_jsonl_file))

    async with app.run_test() as pilot:
        log_list = app.query_one("#logs", LogList)
        log_list.focus()
        await pilot.pause()

        assert len(log_list._log_entries) == 10_000

        max_cache_size = log_list._line_cache.maxsize
        assert max_cache_size == 2000

        for _ in range(50):
            await pilot.press("j")
        await pilot.pause()

        cache_size = len(log_list._line_cache)
        assert cache_size <= max_cache_size, (
            f"Cache has {cache_size} entries, "
            f"should be limited to {max_cache_size}"
        )
