"""Unit tests for clipboard operations."""

import json

from json_logs_viewer.clipboard import (
    format_log_as_json,
    format_logs_as_jsonl,
    get_log_with_context,
)
from json_logs_viewer.constants import COPY_CONTEXT_SIZE
from json_logs_viewer.models import LogEntry


class TestFormatLogAsJson:
    """Tests for format_log_as_json function."""

    def test_formats_single_log_as_pretty_json(self) -> None:
        """Test that a single log entry is formatted as pretty-printed JSON."""
        log_entry = LogEntry(
            line_number=1, data={"level": "INFO", "message": "test"}
        )
        result = format_log_as_json(log_entry=log_entry)
        expected = json.dumps(
            {"level": "INFO", "message": "test"}, indent=2, ensure_ascii=False
        )
        assert result == expected

    def test_handles_unicode(self) -> None:
        """Test that unicode characters are preserved."""
        log_entry = LogEntry(line_number=1, data={"message": "Hello 世界"})
        result = format_log_as_json(log_entry=log_entry)
        assert "世界" in result

    def test_handles_nested_data(self) -> None:
        """Test that nested objects are formatted correctly."""
        log_entry = LogEntry(
            line_number=1,
            data={"user": {"name": "alice", "id": 123}, "items": [1, 2, 3]},
        )
        result = format_log_as_json(log_entry=log_entry)
        parsed = json.loads(result)
        assert parsed["user"]["name"] == "alice"
        assert parsed["items"] == [1, 2, 3]


class TestFormatLogsAsJsonl:
    """Tests for format_logs_as_jsonl function."""

    def test_formats_multiple_logs_as_jsonl(self) -> None:
        """Test that multiple logs are formatted as JSONL."""
        entries = [
            LogEntry(line_number=1, data={"id": 1}),
            LogEntry(line_number=2, data={"id": 2}),
            LogEntry(line_number=3, data={"id": 3}),
        ]
        result = format_logs_as_jsonl(log_entries=entries)
        lines = result.split("\n")
        assert len(lines) == 3
        assert json.loads(lines[0]) == {"id": 1}
        assert json.loads(lines[1]) == {"id": 2}
        assert json.loads(lines[2]) == {"id": 3}

    def test_empty_list_returns_empty_string(self) -> None:
        """Test that empty list returns empty string."""
        result = format_logs_as_jsonl(log_entries=[])
        assert result == ""

    def test_single_entry_no_trailing_newline(self) -> None:
        """Test that single entry has no trailing newline."""
        entries = [LogEntry(line_number=1, data={"test": "value"})]
        result = format_logs_as_jsonl(log_entries=entries)
        assert not result.endswith("\n")


class TestGetLogWithContext:
    """Tests for get_log_with_context function."""

    def test_gets_context_from_middle(self) -> None:
        """Test getting context from the middle of a log list."""
        logs = [LogEntry(line_number=i, data={"line": i}) for i in range(10)]
        result = get_log_with_context(
            logs=logs, current_index=5, context_size=2
        )
        assert len(result) == 5
        assert result[0].data["line"] == 3
        assert result[2].data["line"] == 5
        assert result[4].data["line"] == 7

    def test_handles_start_boundary(self) -> None:
        """Test context at the beginning of the log list."""
        logs = [LogEntry(line_number=i, data={"line": i}) for i in range(10)]
        result = get_log_with_context(
            logs=logs, current_index=1, context_size=5
        )
        assert len(result) == 7
        assert result[0].data["line"] == 0
        assert result[1].data["line"] == 1

    def test_handles_end_boundary(self) -> None:
        """Test context at the end of the log list."""
        logs = [LogEntry(line_number=i, data={"line": i}) for i in range(10)]
        result = get_log_with_context(
            logs=logs, current_index=9, context_size=5
        )
        assert len(result) == 6
        assert result[-1].data["line"] == 9

    def test_handles_first_log(self) -> None:
        """Test context when current log is the first one."""
        logs = [LogEntry(line_number=i, data={"line": i}) for i in range(10)]
        result = get_log_with_context(
            logs=logs, current_index=0, context_size=3
        )
        assert len(result) == 4
        assert result[0].data["line"] == 0
        assert result[-1].data["line"] == 3

    def test_handles_last_log(self) -> None:
        """Test context when current log is the last one."""
        logs = [LogEntry(line_number=i, data={"line": i}) for i in range(10)]
        result = get_log_with_context(
            logs=logs, current_index=9, context_size=3
        )
        assert len(result) == 4
        assert result[0].data["line"] == 6
        assert result[-1].data["line"] == 9

    def test_context_size_zero(self) -> None:
        """Test that context size zero returns only current log."""
        logs = [LogEntry(line_number=i, data={"line": i}) for i in range(10)]
        result = get_log_with_context(
            logs=logs, current_index=5, context_size=0
        )
        assert len(result) == 1
        assert result[0].data["line"] == 5

    def test_default_context_size_constant(self) -> None:
        """Test that COPY_CONTEXT_SIZE is set to a reasonable value."""
        assert COPY_CONTEXT_SIZE == 5
