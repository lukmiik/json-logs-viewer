"""JSON/JSONL parser for log files."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from json_logs_viewer.models import LogEntry, LogLevel


@dataclass(frozen=True)
class ParseResult:
    """Result of parsing a log file."""

    entries: list[LogEntry]
    skipped_lines: list[SkippedLine]
    file_path: Path
    format_type: str  # "json" or "jsonl"


@dataclass(frozen=True)
class SkippedLine:
    """Represents a line that could not be parsed."""

    line_number: int
    raw_line: str
    error_message: str


class LogParser:
    """Parser for JSON and JSONL log files."""

    def __init__(self) -> None:
        """Initialize the parser."""
        self._level_fields: tuple[str, ...] = (
            "level",
            "log_level",
            "severity",
        )
        self._message_fields: tuple[str, ...] = (
            "message",
            "msg",
            "log_message",
            "text",
        )
        self._timestamp_fields: tuple[str, ...] = (
            "timestamp",
            "time",
            "ts",
            "datetime",
            "date",
        )

    def parse_file(self, *, file_path: Path) -> ParseResult:
        """Parse a JSON or JSONL file.

        Args:
            file_path: Path to the log file to parse.

        Returns:
            ParseResult containing parsed entries and skipped lines.

        Raises:
            FileNotFoundError: If the file does not exist.
            PermissionError: If the file cannot be read.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        content = file_path.read_text(encoding="utf-8")

        # Detect format and parse
        format_type = self._detect_format(content=content)

        if format_type == "json":
            entries, skipped = self._parse_json(
                content=content, file_path=file_path
            )
        else:
            entries, skipped = self._parse_jsonl(
                content=content, file_path=file_path
            )

        return ParseResult(
            entries=entries,
            skipped_lines=skipped,
            file_path=file_path,
            format_type=format_type,
        )

    def _detect_format(self, *, content: str) -> str:
        """Detect if content is JSON or JSONL format.

        Args:
            content: The file content to analyze.

        Returns:
            "json" for single JSON array/object, "jsonl" for line-delimited.
        """
        stripped = content.strip()
        if not stripped:
            return "jsonl"  # Empty file treated as JSONL

        # If starts with [ or { and is valid JSON, treat as JSON
        if stripped[0] in "[{":
            try:
                json.loads(stripped)
                return "json"
            except json.JSONDecodeError:
                pass

        return "jsonl"

    def _parse_json(
        self, *, content: str, file_path: Path
    ) -> tuple[list[LogEntry], list[SkippedLine]]:
        """Parse JSON array or object.

        Args:
            content: JSON content to parse.
            file_path: Path to the source file.

        Returns:
            Tuple of (parsed entries, skipped lines).
        """
        entries: list[LogEntry] = []
        skipped: list[SkippedLine] = []

        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            # Entire file is invalid JSON
            return entries, [
                SkippedLine(
                    line_number=1, raw_line=content[:200], error_message=str(e)
                )
            ]

        if isinstance(data, list):
            # JSON array of log entries
            for i, item in enumerate(data, start=1):
                if isinstance(item, dict):
                    entry = self._create_entry(
                        data=item, raw_line=json.dumps(item), line_number=i
                    )
                    entries.append(entry)
                else:
                    skipped.append(
                        SkippedLine(
                            line_number=i,
                            raw_line=str(item)[:200],
                            error_message="Array item is not a JSON object",
                        )
                    )
        elif isinstance(data, dict):
            # Single JSON object treated as one entry
            entry = self._create_entry(
                data=data,
                raw_line=content.strip(),
                line_number=1,
            )
            entries.append(entry)

        return entries, skipped

    def _parse_jsonl(
        self, *, content: str, file_path: Path
    ) -> tuple[list[LogEntry], list[SkippedLine]]:
        """Parse JSONL (line-delimited JSON).

        Args:
            content: JSONL content to parse.
            file_path: Path to the source file.

        Returns:
            Tuple of (parsed entries, skipped lines).
        """
        entries: list[LogEntry] = []
        skipped: list[SkippedLine] = []

        lines = content.splitlines()

        for line_num, raw_line in enumerate(lines, start=1):
            stripped = raw_line.strip()

            # Skip empty lines
            if not stripped:
                continue

            try:
                data = json.loads(stripped)
            except json.JSONDecodeError as e:
                skipped.append(
                    SkippedLine(
                        line_number=line_num,
                        raw_line=raw_line[:200],
                        error_message=str(e),
                    )
                )
                continue

            if not isinstance(data, dict):
                skipped.append(
                    SkippedLine(
                        line_number=line_num,
                        raw_line=raw_line[:200],
                        error_message="Parsed data is not a JSON object",
                    )
                )
                continue

            entry = self._create_entry(
                data=data, raw_line=raw_line, line_number=line_num
            )
            entries.append(entry)

        return entries, skipped

    def _create_entry(
        self, *, data: dict[str, Any], raw_line: str, line_number: int
    ) -> LogEntry:
        """Create a LogEntry from parsed data.

        Args:
            data: Parsed JSON data.
            raw_line: Original raw line.
            line_number: Line number in the file.

        Returns:
            Constructed LogEntry with extracted fields.
        """
        # Extract level
        level = LogLevel.INFO
        for field_name in self._level_fields:
            if field_name in data:
                level = LogLevel.from_string(str(data[field_name]))
                break

        # Extract message
        message = ""
        for field_name in self._message_fields:
            if field_name in data:
                msg_value = data[field_name]
                message = str(msg_value) if msg_value is not None else ""
                break

        # Extract timestamp
        timestamp: datetime | None = None
        for field_name in self._timestamp_fields:
            if field_name in data:
                ts_value = data[field_name]
                timestamp = self._parse_timestamp(ts_value)
                if timestamp is not None:
                    break

        return LogEntry(
            raw_line=raw_line,
            parsed_data=data,
            line_number=line_number,
            timestamp=timestamp,
            level=level,
            message=message,
        )

    def _parse_timestamp(self, value: object) -> datetime | None:
        """Attempt to parse a timestamp value.

        Args:
            value: The value to parse as timestamp.

        Returns:
            Parsed datetime or None if parsing fails.
        """
        if value is None:
            return None

        if isinstance(value, (int, float)):
            # Assume Unix timestamp
            try:
                # Check if it looks like milliseconds
                if value > 1_000_000_000_000:  # noqa: PLR2004
                    return datetime.fromtimestamp(value / 1000)
                return datetime.fromtimestamp(value)
            except (ValueError, OSError, OverflowError):
                return None

        if isinstance(value, str):
            # Try ISO format first
            try:
                # Handle 'Z' suffix
                normalized = value.replace("Z", "+00:00")
                return datetime.fromisoformat(normalized)
            except ValueError:
                pass

            # Try common formats
            formats = [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f",
            ]
            for fmt in formats:
                try:
                    return datetime.strptime(value, fmt)  # noqa: DTZ007
                except ValueError:
                    continue

        return None


@dataclass
class IncrementalParser:
    """Parser for incrementally appending new lines from a file."""

    file_path: Path
    last_position: int = field(default=0)
    line_offset: int = field(default=0)

    def read_new_lines(self) -> tuple[list[LogEntry], list[SkippedLine], int]:
        """Read new lines appended since last read.

        Returns:
            Tuple of (new entries, skipped lines, new file position).
        """
        entries: list[LogEntry] = []
        skipped: list[SkippedLine] = []

        if not self.file_path.exists():
            return entries, skipped, self.last_position

        current_size = self.file_path.stat().st_size

        # File was truncated/rotated
        if current_size < self.last_position:
            self.last_position = 0
            self.line_offset = 0

        if current_size == self.last_position:
            return entries, skipped, self.last_position

        with self.file_path.open("r", encoding="utf-8") as f:
            f.seek(self.last_position)
            new_content = f.read()
            new_position = f.tell()

        parser = LogParser()
        lines = new_content.splitlines()
        line_num = self.line_offset

        for raw_line in lines:
            line_num += 1
            stripped = raw_line.strip()

            if not stripped:
                continue

            try:
                data = json.loads(stripped)
            except json.JSONDecodeError as e:
                skipped.append(
                    SkippedLine(
                        line_number=line_num,
                        raw_line=raw_line[:200],
                        error_message=str(e),
                    )
                )
                continue

            if not isinstance(data, dict):
                skipped.append(
                    SkippedLine(
                        line_number=line_num,
                        raw_line=raw_line[:200],
                        error_message="Parsed data is not a JSON object",
                    )
                )
                continue

            entry = parser._create_entry(
                data=data, raw_line=raw_line, line_number=line_num
            )
            entries.append(entry)

        self.last_position = new_position
        self.line_offset = line_num

        return entries, skipped, new_position
