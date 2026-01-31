"""Tests for JSON/JSONL parser."""

import json
from pathlib import Path

import pytest

from json_logs_viewer.models import LogEntry, LogLevel
from json_logs_viewer.parser import (
    IncrementalParser,
    LogParser,
    ParseResult,
    SkippedLine,
)


class TestLogParser:
    """Tests for LogParser class."""

    @pytest.fixture
    def parser(self) -> LogParser:
        """Create a LogParser instance."""
        return LogParser()

    @pytest.fixture
    def temp_dir(self, tmp_path: Path) -> Path:
        """Provide a temporary directory."""
        return tmp_path

    def test_parse_jsonl_file(self, parser: LogParser, temp_dir: Path) -> None:
        """Test parsing a JSONL file."""
        content = """{"level": "info", "message": "hello"}
{"level": "error", "message": "failed"}
{"level": "debug", "message": "details"}"""

        file_path = temp_dir / "test.jsonl"
        file_path.write_text(content)

        result = parser.parse_file(file_path=file_path)

        assert isinstance(result, ParseResult)
        assert result.format_type == "jsonl"
        assert len(result.entries) == 3
        assert len(result.skipped_lines) == 0

        assert result.entries[0].level == LogLevel.INFO
        assert result.entries[0].message == "hello"
        assert result.entries[1].level == LogLevel.ERROR
        assert result.entries[1].message == "failed"
        assert result.entries[2].level == LogLevel.DEBUG

    def test_parse_json_array_file(
        self, parser: LogParser, temp_dir: Path
    ) -> None:
        """Test parsing a JSON array file."""
        content = json.dumps(
            [
                {"level": "info", "message": "first"},
                {"level": "warning", "message": "second"},
            ]
        )

        file_path = temp_dir / "test.json"
        file_path.write_text(content)

        result = parser.parse_file(file_path=file_path)

        assert result.format_type == "json"
        assert len(result.entries) == 2
        assert result.entries[0].level == LogLevel.INFO
        assert result.entries[0].message == "first"
        assert result.entries[1].level == LogLevel.WARNING

    def test_parse_json_object_file(
        self, parser: LogParser, temp_dir: Path
    ) -> None:
        """Test parsing a single JSON object file."""
        content = json.dumps({"level": "error", "message": "critical"})

        file_path = temp_dir / "test.json"
        file_path.write_text(content)

        result = parser.parse_file(file_path=file_path)

        assert result.format_type == "json"
        assert len(result.entries) == 1
        assert result.entries[0].level == LogLevel.ERROR
        assert result.entries[0].message == "critical"

    def test_parse_with_empty_lines(
        self, parser: LogParser, temp_dir: Path
    ) -> None:
        """Test parsing JSONL with empty lines."""
        content = """{"level": "info", "message": "first"}

{"level": "error", "message": "second"}
"""

        file_path = temp_dir / "test.jsonl"
        file_path.write_text(content)

        result = parser.parse_file(file_path=file_path)

        assert len(result.entries) == 2
        assert len(result.skipped_lines) == 0

    def test_parse_with_invalid_json(
        self, parser: LogParser, temp_dir: Path
    ) -> None:
        """Test parsing JSONL with some invalid lines."""
        content = """{"level": "info", "message": "valid"}
this is not json
{"level": "error", "message": "also valid"}
{invalid json}"""

        file_path = temp_dir / "test.jsonl"
        file_path.write_text(content)

        result = parser.parse_file(file_path=file_path)

        assert len(result.entries) == 2
        assert len(result.skipped_lines) == 2
        assert result.skipped_lines[0].line_number == 2
        assert "not json" in result.skipped_lines[0].raw_line
        assert result.skipped_lines[1].line_number == 4

    def test_parse_file_not_found(self, parser: LogParser) -> None:
        """Test that FileNotFoundError is raised for non-existent file."""
        with pytest.raises(FileNotFoundError):
            parser.parse_file(file_path=Path("/nonexistent/path.json"))

    def test_parse_empty_file(self, parser: LogParser, temp_dir: Path) -> None:
        """Test parsing an empty file."""
        file_path = temp_dir / "empty.jsonl"
        file_path.write_text("")

        result = parser.parse_file(file_path=file_path)

        assert result.format_type == "jsonl"
        assert len(result.entries) == 0
        assert len(result.skipped_lines) == 0

    def test_parse_whitespace_only_file(
        self, parser: LogParser, temp_dir: Path
    ) -> None:
        """Test parsing a file with only whitespace."""
        file_path = temp_dir / "whitespace.jsonl"
        file_path.write_text("   \n\t\n   ")

        result = parser.parse_file(file_path=file_path)

        assert len(result.entries) == 0
        assert len(result.skipped_lines) == 0

    def test_parse_array_with_non_objects(
        self, parser: LogParser, temp_dir: Path
    ) -> None:
        """Test parsing JSON array with non-object items."""
        content = json.dumps(["string", 123, {"level": "info"}])

        file_path = temp_dir / "mixed.json"
        file_path.write_text(content)

        result = parser.parse_file(file_path=file_path)

        assert len(result.entries) == 1
        assert len(result.skipped_lines) == 2
        assert result.entries[0].level == LogLevel.INFO

    def test_parse_invalid_json_file(
        self, parser: LogParser, temp_dir: Path
    ) -> None:
        """Test parsing an invalid JSON file."""
        file_path = temp_dir / "invalid.json"
        file_path.write_text("{invalid json content}")

        result = parser.parse_file(file_path=file_path)

        assert result.format_type == "jsonl"
        assert len(result.entries) == 0
        assert len(result.skipped_lines) == 1

    def test_detect_format_json_array(self, parser: LogParser) -> None:
        """Test format detection for JSON array."""
        content = json.dumps([{"level": "info"}])
        assert parser._detect_format(content=content) == "json"

    def test_detect_format_json_object(self, parser: LogParser) -> None:
        """Test format detection for JSON object."""
        content = json.dumps({"level": "info"})
        assert parser._detect_format(content=content) == "json"

    def test_detect_format_jsonl(self, parser: LogParser) -> None:
        """Test format detection for JSONL."""
        content = '{"level": "info"}\n{"level": "error"}'
        assert parser._detect_format(content=content) == "jsonl"

    def test_detect_format_invalid_json(self, parser: LogParser) -> None:
        """Test format detection for invalid JSON starting with [ or {."""
        content = '{"invalid json'
        assert parser._detect_format(content=content) == "jsonl"


class TestLogEntryCreation:
    """Tests for LogEntry creation from parsed data."""

    @pytest.fixture
    def parser(self) -> LogParser:
        """Create a LogParser instance."""
        return LogParser()

    def test_level_field_variants(self, parser: LogParser) -> None:
        """Test extracting level from various field names."""
        test_cases = [
            ({"level": "error"}, LogLevel.ERROR),
            ({"log_level": "warning"}, LogLevel.WARNING),
            ({"severity": "info"}, LogLevel.INFO),
            ({"unknown_field": "value"}, LogLevel.INFO),  # Default
        ]

        for data, expected_level in test_cases:
            entry = parser._create_entry(
                data=data, raw_line=json.dumps(data), line_number=1
            )
            assert entry.level == expected_level

    def test_message_field_variants(self, parser: LogParser) -> None:
        """Test extracting message from various field names."""
        test_cases = [
            ({"message": "hello"}, "hello"),
            ({"msg": "world"}, "world"),
            ({"log_message": "test"}, "test"),
            ({"text": "content"}, "content"),
            ({"other": "field"}, ""),  # Default
        ]

        for data, expected_message in test_cases:
            entry = parser._create_entry(
                data=data, raw_line=json.dumps(data), line_number=1
            )
            assert entry.message == expected_message

    def test_timestamp_iso_format(self, parser: LogParser) -> None:
        """Test parsing ISO format timestamps."""
        data = {"timestamp": "2024-01-15T10:30:45", "level": "info"}
        entry = parser._create_entry(
            data=data, raw_line=json.dumps(data), line_number=1
        )

        assert entry.timestamp is not None
        assert entry.timestamp.year == 2024
        assert entry.timestamp.month == 1
        assert entry.timestamp.day == 15

    def test_timestamp_iso_with_z(self, parser: LogParser) -> None:
        """Test parsing ISO format with Z suffix."""
        data = {"timestamp": "2024-01-15T10:30:45Z", "level": "info"}
        entry = parser._create_entry(
            data=data, raw_line=json.dumps(data), line_number=1
        )

        assert entry.timestamp is not None
        assert entry.timestamp.year == 2024

    def test_timestamp_unix_seconds(self, parser: LogParser) -> None:
        """Test parsing Unix timestamp in seconds."""
        data = {"ts": 1705315845, "level": "info"}
        entry = parser._create_entry(
            data=data, raw_line=json.dumps(data), line_number=1
        )

        assert entry.timestamp is not None
        assert entry.timestamp.year == 2024

    def test_timestamp_unix_milliseconds(self, parser: LogParser) -> None:
        """Test parsing Unix timestamp in milliseconds."""
        data = {"time": 1705315845000, "level": "info"}
        entry = parser._create_entry(
            data=data, raw_line=json.dumps(data), line_number=1
        )

        assert entry.timestamp is not None
        assert entry.timestamp.year == 2024

    def test_timestamp_string_formats(self, parser: LogParser) -> None:
        """Test parsing various string timestamp formats."""
        test_cases = [
            "2024-01-15 10:30:45",
            "2024-01-15 10:30:45.123",
        ]

        for ts_str in test_cases:
            data = {"datetime": ts_str, "level": "info"}
            entry = parser._create_entry(
                data=data, raw_line=json.dumps(data), line_number=1
            )
            assert entry.timestamp is not None
            assert entry.timestamp.year == 2024

    def test_level_case_insensitive(self, parser: LogParser) -> None:
        """Test that level parsing is case insensitive."""
        test_cases = [
            "ERROR",
            "error",
            "Error",
            "  error  ",
        ]

        for level_str in test_cases:
            data = {"level": level_str, "message": "test"}
            entry = parser._create_entry(
                data=data, raw_line=json.dumps(data), line_number=1
            )
            assert entry.level == LogLevel.ERROR

    def test_full_log_entry_attributes(self, parser: LogParser) -> None:
        """Test all LogEntry attributes are correctly set."""
        raw_line = (
            '{"level": "warning", "message": "test message", "extra": "data"}'
        )
        data = {"level": "warning", "message": "test message", "extra": "data"}

        entry = parser._create_entry(
            data=data, raw_line=raw_line, line_number=42
        )

        assert entry.raw_line == raw_line
        assert entry.parsed_data == data
        assert entry.line_number == 42
        assert entry.level == LogLevel.WARNING
        assert entry.message == "test message"


class TestIncrementalParser:
    """Tests for IncrementalParser class."""

    @pytest.fixture
    def temp_dir(self, tmp_path: Path) -> Path:
        """Provide a temporary directory."""
        return tmp_path

    def test_read_new_lines_initial(self, temp_dir: Path) -> None:
        """Test reading lines from the beginning of a file."""
        file_path = temp_dir / "test.log"
        file_path.write_text('{"level": "info", "message": "line1"}\n')

        parser = IncrementalParser(
            file_path=file_path, last_position=0, line_offset=0
        )
        entries, skipped, position = parser.read_new_lines()

        assert len(entries) == 1
        assert len(skipped) == 0
        assert position > 0
        assert parser.last_position == position
        assert parser.line_offset == 1

    def test_read_no_new_lines(self, temp_dir: Path) -> None:
        """Test reading when no new lines are available."""
        file_path = temp_dir / "test.log"
        file_path.write_text('{"level": "info", "message": "line1"}\n')

        # First read to get position
        parser = IncrementalParser(
            file_path=file_path, last_position=0, line_offset=0
        )
        entries, skipped, position = parser.read_new_lines()

        # Second read should return nothing
        parser2 = IncrementalParser(
            file_path=file_path, last_position=position, line_offset=1
        )
        entries2, skipped2, position2 = parser2.read_new_lines()

        assert len(entries2) == 0
        assert position2 == position

    def test_read_appended_lines(self, temp_dir: Path) -> None:
        """Test reading newly appended lines."""
        file_path = temp_dir / "test.log"
        file_path.write_text('{"level": "info", "message": "line1"}\n')

        # First read
        parser = IncrementalParser(
            file_path=file_path, last_position=0, line_offset=0
        )
        entries, skipped, position = parser.read_new_lines()

        # Append more lines
        with file_path.open("a") as f:
            f.write('{"level": "error", "message": "line2"}\n')

        # Second read
        parser2 = IncrementalParser(
            file_path=file_path, last_position=position, line_offset=1
        )
        entries2, skipped2, position2 = parser2.read_new_lines()

        assert len(entries2) == 1
        assert entries2[0].level == LogLevel.ERROR
        assert entries2[0].line_number == 2

    def test_read_with_invalid_lines(self, temp_dir: Path) -> None:
        """Test handling invalid lines during incremental read."""
        file_path = temp_dir / "test.log"
        file_path.write_text(
            '{"level": "info", "message": "valid"}\ninvalid json\n'
        )

        parser = IncrementalParser(
            file_path=file_path, last_position=0, line_offset=0
        )
        entries, skipped, position = parser.read_new_lines()

        assert len(entries) == 1
        assert len(skipped) == 1
        assert skipped[0].line_number == 2

    def test_file_tracked_position(self, temp_dir: Path) -> None:
        """Test that parser tracks file position correctly."""
        file_path = temp_dir / "test.log"
        file_path.write_text('{"level": "info", "message": "test"}\n')

        parser = IncrementalParser(
            file_path=file_path, last_position=0, line_offset=0
        )
        entries, skipped, position = parser.read_new_lines()

        assert position == file_path.stat().st_size

    def test_file_nonexistent(self, temp_dir: Path) -> None:
        """Test reading from non-existent file."""
        file_path = temp_dir / "nonexistent.log"

        parser = IncrementalParser(
            file_path=file_path, last_position=0, line_offset=0
        )
        entries, skipped, position = parser.read_new_lines()

        assert len(entries) == 0
        assert len(skipped) == 0


class TestSkippedLine:
    """Tests for SkippedLine dataclass."""

    def test_skipped_line_creation(self) -> None:
        """Test creating a SkippedLine."""
        skipped = SkippedLine(
            line_number=5,
            raw_line='{"invalid',
            error_message="Expecting property name",
        )

        assert skipped.line_number == 5
        assert skipped.raw_line == '{"invalid'
        assert "Expecting" in skipped.error_message


class TestParseResult:
    """Tests for ParseResult dataclass."""

    def test_parse_result_creation(self, tmp_path: Path) -> None:
        """Test creating a ParseResult."""
        entry = LogEntry(
            raw_line='{"level": "info"}',
            parsed_data={"level": "info"},
            line_number=1,
        )
        skipped = SkippedLine(
            line_number=2,
            raw_line="invalid",
            error_message="parse error",
        )

        result = ParseResult(
            entries=[entry],
            skipped_lines=[skipped],
            file_path=tmp_path / "test.log",
            format_type="jsonl",
        )

        assert len(result.entries) == 1
        assert len(result.skipped_lines) == 1
        assert result.format_type == "jsonl"
