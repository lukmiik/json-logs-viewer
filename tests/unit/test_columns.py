"""Unit tests for column customization feature."""

from collections import Counter
from pathlib import Path

import pytest

from json_logs_viewer.app import LogViewerApp
from json_logs_viewer.models import DETECTED_COLUMNS, LogEntry
from json_logs_viewer.widgets.log_list import LogList


@pytest.mark.asyncio
async def test_discover_fields_returns_top_20() -> None:
    """Test that discover_fields returns at most 20 fields."""
    app = LogViewerApp()
    async with app.run_test():
        logs = []
        for i in range(30):
            data = {
                f"field_{j}": f"value_{j}" for j in range(i, min(i + 5, 30))
            }
            logs.append(LogEntry(line_number=i, data=data))

        app.logs = logs

        fields = app.discover_fields()

        assert len(fields) <= 20


@pytest.mark.asyncio
async def test_discover_fields_sorted_by_frequency() -> None:
    """Test that fields are sorted by occurrence count."""
    app = LogViewerApp()
    async with app.run_test():
        logs = [
            LogEntry(
                line_number=0,
                data={"level": "INFO", "timestamp": "2024-01-01"},
            ),
            LogEntry(
                line_number=1,
                data={"level": "ERROR", "timestamp": "2024-01-02"},
            ),
            LogEntry(line_number=2, data={"level": "WARN"}),
            LogEntry(line_number=3, data={"level": "DEBUG", "extra": "value"}),
        ]

        app.logs = logs

        fields = app.discover_fields()

        field_counts: Counter[str] = Counter()
        for log in logs:
            field_counts.update(log.data.keys())

        # Detected @ columns come first; real fields follow by frequency.
        real = [f for f in fields if f not in DETECTED_COLUMNS]
        assert real[0] == "level"
        assert real[1] == "timestamp"
        assert "extra" in real


@pytest.mark.asyncio
async def test_discover_fields_empty_logs() -> None:
    """Test discover_fields with no logs."""
    app = LogViewerApp()
    async with app.run_test():
        app.logs = []

        fields = app.discover_fields()

        assert fields == []


@pytest.mark.asyncio
async def test_discover_fields_with_nested_values() -> None:
    """Nested values are offered by their full dotted path."""
    app = LogViewerApp()
    async with app.run_test():
        logs = [
            LogEntry(
                line_number=0,
                data={
                    "level": "INFO",
                    "metadata": {"nested": "value"},
                    "timestamp": "2024-01-01",
                },
            ),
        ]

        app.logs = logs

        fields = app.discover_fields()

        assert "level" in fields
        assert "timestamp" in fields
        assert "metadata.nested" in fields
        assert "metadata" not in fields
        assert "nested" not in fields


@pytest.mark.asyncio
async def test_discover_fields_counts_correctly() -> None:
    """Test that field counts are accurate."""
    app = LogViewerApp()
    async with app.run_test():
        logs = [
            LogEntry(line_number=0, data={"a": 1, "b": 2, "c": 3}),
            LogEntry(line_number=1, data={"a": 1, "b": 2}),
            LogEntry(line_number=2, data={"a": 1}),
        ]

        app.logs = logs

        fields = app.discover_fields()

        assert fields == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_appending_logs_counts_only_new_entries() -> None:
    """Follow-mode appends update the existing counter instead of recounting.

    A full recount replaces ``_field_counts`` with a new Counter, so keeping
    the same object proves the incremental path ran.
    """
    app = LogViewerApp()
    async with app.run_test():
        app.logs = [
            LogEntry(line_number=1, data={"a": 1}),
            LogEntry(line_number=2, data={"a": 1, "b": 2}),
        ]
        app.discover_fields()
        counter = app._field_counts

        app.logs = [*app.logs, LogEntry(line_number=3, data={"b": 1, "c": 2})]
        app.discover_fields()

        assert app._field_counts is counter
        assert app._field_counts == Counter({"a": 2, "b": 2, "c": 1})


@pytest.mark.asyncio
async def test_replacing_logs_recounts_from_scratch() -> None:
    """Loading a different file must drop counts from the old file."""
    app = LogViewerApp()
    async with app.run_test():
        app.logs = [LogEntry(line_number=1, data={"old": 1})]
        app.discover_fields()

        app.logs = [
            LogEntry(line_number=1, data={"new": 1}),
            LogEntry(line_number=2, data={"new": 2}),
        ]

        assert app.discover_fields() == ["new"]
        assert app._field_counts == Counter({"new": 2})


@pytest.mark.asyncio
async def test_loading_logs_does_not_count_fields() -> None:
    """Counting waits until the columns modal asks for fields."""
    app = LogViewerApp()
    async with app.run_test():
        app.logs = [LogEntry(line_number=1, data={"a": {"b": 1}})]

        assert app._field_counts == Counter()
        assert app.discover_fields() == ["a.b"]


@pytest.mark.asyncio
async def test_discover_fields_offers_nested_paths() -> None:
    """Nested objects are offered as dotted paths to their values."""
    app = LogViewerApp()
    async with app.run_test():
        app.logs = [
            LogEntry(
                line_number=i,
                data={
                    "message": "m",
                    "attributes": {"level": "error", "http": {"status": 502}},
                },
            )
            for i in range(3)
        ]

        fields = app.discover_fields()

        assert "attributes.level" in fields
        assert "attributes.http.status" in fields
        assert "attributes" not in fields


@pytest.mark.asyncio
async def test_nested_column_is_rendered(tmp_path: Path) -> None:
    log_file = tmp_path / "app.jsonl"
    log_file.write_text(
        '{"msg": "a", "http": {"status": 504}}\n{"msg": "b"}\n'
    )
    app = LogViewerApp(file=str(log_file))
    async with app.run_test(size=(100, 10)) as pilot:
        await pilot.pause()
        app.columns = ["http.status"]
        await pilot.pause()
        log_list = app.query_one("#logs", LogList)

        def row(y: int) -> str:
            return "".join(s.text for s in log_list.render_line(y)._segments)

        assert row(0).startswith("504         | ")
        assert row(1).startswith("            | ")


@pytest.mark.asyncio
async def test_detected_columns_come_first_when_present() -> None:
    app = LogViewerApp()
    async with app.run_test():
        app.logs = [
            LogEntry(line_number=1, data={"ts": "2024-01-15", "msg": "a"}),
            LogEntry(line_number=2, data={"msg": "b", "extra": 1}),
        ]

        fields = app.discover_fields()

        # No level in these logs, so no @level.
        assert fields[:2] == ["@timestamp", "@message"]
        assert "@level" not in fields
        assert {"ts", "msg", "extra"} <= set(fields)
