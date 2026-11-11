"""Tests for LogEntry model field auto-detection and edge cases."""

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from json_logs_viewer.models import (
    LEVEL_FIELDS,
    MESSAGE_FIELDS,
    TIMESTAMP_FIELDS,
    LogEntry,
    appended_entries,
    level_category,
)


@pytest.fixture
def base_log_data() -> dict[str, Any]:
    """Provides base log entry structure with nested data dict."""
    return {"line_number": 1, "data": {"some_other_field": "value"}}


class TestTimestampDetection:
    """Test automatic timestamp field detection."""

    @pytest.mark.parametrize("field_name", TIMESTAMP_FIELDS)
    def test_detects_timestamp_from_various_names(
        self, field_name: str, base_log_data: dict[str, Any]
    ) -> None:
        """Timestamp auto-detection from any TIMESTAMP_FIELDS variant."""
        iso_timestamp = "2024-01-15T10:30:00Z"
        base_log_data["data"][field_name] = iso_timestamp

        log_entry = LogEntry(**base_log_data)

        assert log_entry.timestamp == datetime(
            2024, 1, 15, 10, 30, 0, tzinfo=UTC
        )

    def test_priority_order_timestamp(self) -> None:
        """When multiple timestamp fields exist, first in list wins."""
        data: dict[str, Any] = {
            "line_number": 1,
            "data": {
                # Lower priority candidate
                "time": "2024-01-15T11:00:00Z",
                # Higher priority, should win
                "Timestamp": "2024-01-15T10:00:00Z",
            },
        }

        log_entry = LogEntry(**data)

        assert log_entry.timestamp == datetime(
            2024, 1, 15, 10, 0, 0, tzinfo=UTC
        )

    def test_missing_timestamp_returns_none(
        self, base_log_data: dict[str, Any]
    ) -> None:
        """When no timestamp field present, timestamp should be None."""
        log_entry = LogEntry(**base_log_data)

        assert log_entry.timestamp is None


class TestLevelDetection:
    """Test automatic level field detection."""

    @pytest.mark.parametrize("field_name", LEVEL_FIELDS)
    def test_detects_level_from_various_names(
        self, field_name: str, base_log_data: dict[str, Any]
    ) -> None:
        """Level should be auto-detected from any LEVEL_FIELDS variant."""
        base_log_data["data"][field_name] = "ERROR"

        log_entry = LogEntry(**base_log_data)

        assert log_entry.level == "ERROR"

    def test_priority_order_level(self) -> None:
        """When multiple level fields exist, first in list wins."""
        data: dict[str, Any] = {
            "line_number": 1,
            "data": {
                # Lower priority candidate
                "log_level": "WARN",
                # Higher priority (first in LEVEL_FIELDS)
                "SeverityText": "ERROR",
            },
        }

        log_entry = LogEntry(**data)

        assert log_entry.level == "ERROR"

    @pytest.mark.parametrize(
        "data",
        [
            {"attributes": {"level": "error"}},
            {"attributes": {"severity": "error"}},
            {"log": {"level": "error"}},
            {"log.level": "error"},
        ],
        ids=["otel", "otel-severity", "ecs-nested", "ecs-dotted"],
    )
    def test_detects_nested_level(self, data: dict[str, Any]) -> None:
        """Nested level fields (OpenTelemetry attributes, Elastic ECS)."""
        assert LogEntry(line_number=1, data=data).level == "error"

    def test_top_level_field_beats_nested(self) -> None:
        data = {"level": "info", "attributes": {"level": "error"}}
        assert LogEntry(line_number=1, data=data).level == "info"

    def test_missing_level_returns_none(
        self, base_log_data: dict[str, Any]
    ) -> None:
        """When no level field present, level should be None."""
        log_entry = LogEntry(**base_log_data)

        assert log_entry.level is None


class TestMessageDetection:
    """Test automatic message field detection."""

    @pytest.mark.parametrize("field_name", MESSAGE_FIELDS)
    def test_detects_message_from_various_names(
        self, field_name: str, base_log_data: dict[str, Any]
    ) -> None:
        """Message should be auto-detected from any MESSAGE_FIELDS variant."""
        base_log_data["data"][field_name] = "Test log message"

        log_entry = LogEntry(**base_log_data)

        assert log_entry.message == "Test log message"

    def test_priority_order_message(self) -> None:
        """When multiple message fields exist, first in list wins."""
        data: dict[str, Any] = {
            "line_number": 1,
            "data": {
                "msg": "Lower priority message",
                "message": "Higher priority message",
            },
        }

        log_entry = LogEntry(**data)

        assert log_entry.message == "Higher priority message"

    def test_missing_message_returns_none(
        self, base_log_data: dict[str, Any]
    ) -> None:
        """When no message field present, message should be None."""
        log_entry = LogEntry(**base_log_data)

        assert log_entry.message is None


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_data_dict(self) -> None:
        """Empty data dict should create LogEntry with all None fields."""
        data: dict[str, Any] = {"line_number": 1, "data": {}}

        log_entry = LogEntry(**data)

        assert log_entry.timestamp is None
        assert log_entry.level is None
        assert log_entry.message is None
        assert log_entry.line_number == 1
        assert log_entry.data == {}

    def test_null_values_in_fields(self) -> None:
        """Null/None values should be treated as absent."""
        data: dict[str, Any] = {
            "line_number": 1,
            "data": {"timestamp": None, "level": None, "message": None},
        }

        log_entry = LogEntry(**data)

        assert log_entry.timestamp is None
        assert log_entry.level is None
        assert log_entry.message is None

    def test_data_key_not_present(self) -> None:
        """Input without 'data' key should raise ValidationError.

        The 'data' field is required by the model.
        """
        data: dict[str, Any] = {"line_number": 1, "other_field": "value"}

        with pytest.raises(ValidationError):
            LogEntry(**data)

    def test_validator_receives_non_dict_input(self) -> None:
        """When validator receives non-dict input, return it unchanged."""
        # This directly tests the first guard clause
        result = LogEntry.extract_normalized_fields("not a dict")  # type: ignore[arg-type]
        assert result == "not a dict"

    def test_data_field_not_dict(self) -> None:
        """When data field is not a dict, pass through unchanged.

        Pydantic will then raise a ValidationError.
        """
        data: dict[str, Any] = {"line_number": 1, "data": "not a dict"}

        # Validator returns data unchanged, then Pydantic expects dict
        with pytest.raises(ValidationError):
            LogEntry(**data)

    @pytest.mark.parametrize(
        ("data", "level", "message"),
        [
            ({"level": 30, "message": 5}, "30", "5"),
            ({"level": 2.5}, "2.5", None),
            ({"level": True, "message": False}, None, None),
            ({"level": {"name": "x"}, "message": ["a"]}, None, None),
        ],
    )
    def test_non_string_level_and_message_never_reject_the_entry(
        self, data: dict[str, Any], level: str | None, message: str | None
    ) -> None:
        """Numbers become text; objects, lists and booleans become None."""
        log_entry = LogEntry(line_number=1, data=data)

        assert log_entry.level == level
        assert log_entry.message == message
        assert log_entry.data == data

    @pytest.mark.parametrize(
        "value", ["not-a-datetime", True, {"a": 1}, [2024, 1, 1]]
    )
    def test_unparseable_timestamp_is_none(self, value: object) -> None:
        log_entry = LogEntry(line_number=1, data={"timestamp": value})

        assert log_entry.timestamp is None

    def test_original_data_preserved(self) -> None:
        """All original fields in data should be preserved unchanged."""
        data: dict[str, Any] = {
            "line_number": 42,
            "data": {
                "timestamp": "2024-01-15T10:00:00Z",
                "level": "INFO",
                "message": "Test",
                "custom_field_1": "value1",
                "custom_field_2": 123,
                "nested": {"deep": "value"},
            },
        }

        log_entry = LogEntry(**data)

        # Check extracted fields
        assert log_entry.timestamp is not None
        assert log_entry.level == "INFO"
        assert log_entry.message == "Test"
        # Check original data fully preserved
        assert log_entry.data == data["data"]
        assert log_entry.line_number == 42

    def test_unicode_and_special_chars(self) -> None:
        """Should handle Unicode and special characters correctly."""
        data: dict[str, Any] = {
            "line_number": 1,
            "data": {
                "message": 'Test with unicode: 你好 🎉 and "quotes"',
                "level": "INFO",
            },
        }

        log_entry = LogEntry(**data)

        assert log_entry.message == 'Test with unicode: 你好 🎉 and "quotes"'

    def test_all_fields_together(self) -> None:
        """When all three field types present, all should be extracted."""
        data: dict[str, Any] = {
            "line_number": 1,
            "data": {
                "@t": "2024-01-15T10:00:00Z",
                "level": "WARN",
                "@m": "Warning message",
            },
        }

        log_entry = LogEntry(**data)

        assert log_entry.timestamp is not None
        assert log_entry.level == "WARN"
        assert log_entry.message == "Warning message"


class TestFindFirstHelper:
    """Test the _find_first static method."""

    def test_accepts_keyword_arguments(self) -> None:
        """_find_first should accept keyword arguments correctly."""
        result = LogEntry._find_first(
            data={"field": "value"}, candidates=["field"]
        )

        assert result == "value"

    def test_empty_candidates_list(self) -> None:
        """Empty candidates list should return None."""
        result = LogEntry._find_first(data={"a": 1}, candidates=[])

        assert result is None

    def test_empty_data_dict(self) -> None:
        """Empty data dict should return None."""
        result = LogEntry._find_first(data={}, candidates=["field1", "field2"])

        assert result is None

    def test_single_candidate_found(self) -> None:
        """Should return value when single candidate exists."""
        result = LogEntry._find_first(
            data={"field1": "value"}, candidates=["field1"]
        )

        assert result == "value"

    def test_multiple_candidates_returns_first_match(self) -> None:
        """Should return value from first matching candidate."""
        data = {"field2": "second", "field1": "first", "field3": "third"}
        candidates = ["field3", "field1", "field2"]

        result = LogEntry._find_first(data=data, candidates=candidates)

        assert result == "third"  # field3 is first in candidates

    def test_no_match_returns_none(self) -> None:
        """Should return None when no candidate matches."""
        data = {"other": "value"}
        result = LogEntry._find_first(
            data=data, candidates=["field1", "field2"]
        )

        assert result is None


class TestAppendedEntries:
    """appended_entries tells a follow-mode append from a replacement."""

    def _logs(self, count: int) -> list[LogEntry]:
        return [
            LogEntry(line_number=i, data={"i": i}, raw_json=f'{{"i": {i}}}')
            for i in range(count)
        ]

    def test_append_returns_new_tail(self) -> None:
        old = self._logs(3)
        extra = self._logs(2)
        assert appended_entries(old=old, new=[*old, *extra]) == extra

    def test_same_entries_append_nothing(self) -> None:
        old = self._logs(3)
        assert appended_entries(old=old, new=list(old)) == []

    def test_reload_with_equal_entries_is_not_an_append(self) -> None:
        """Equal content in new objects (a reload) must be recomputed."""
        assert appended_entries(old=self._logs(3), new=self._logs(4)) is None

    def test_shorter_or_changed_list_is_not_an_append(self) -> None:
        old = self._logs(3)
        assert appended_entries(old=old, new=old[:2]) is None
        assert appended_entries(old=old, new=[old[1], old[0], old[2]]) is None

    def test_empty_old_is_not_an_append(self) -> None:
        assert appended_entries(old=[], new=self._logs(2)) is None


@pytest.mark.parametrize(
    ("level", "category"),
    [
        ("ERROR", "error"),
        ("error", "error"),
        (" Fatal ", "error"),
        ("CRITICAL", "error"),
        ("panic", "error"),
        ("WARN", "warning"),
        ("Warning", "warning"),
        ("DEBUG", "debug"),
        ("trace", "debug"),
        ("INFO", None),
        ("notice", None),
        ("something else", None),
        (None, None),
        # pino's numeric levels, stored as text
        ("10", "debug"),
        ("20", "debug"),
        ("30", None),
        ("40", "warning"),
        ("50", "error"),
        ("60", "error"),
    ],
)
def test_level_category(level: str | None, category: str | None) -> None:
    assert level_category(level=level) == category


class TestDetectionSkipsNulls:
    """A null candidate doesn't stop detection; the next one is used."""

    def test_falls_back_past_null_fields(self) -> None:
        log = LogEntry(
            line_number=1,
            data={
                "timestamp": None,
                "time": "2024-01-01T00:00:00Z",
                "message": None,
                "msg": "hi",
                "level": None,
                "severity": "warn",
            },
        )
        assert log.timestamp is not None
        assert log.message == "hi"
        assert log.level == "warn"

    def test_dotted_candidate_skips_null_readings(self) -> None:
        data = {"log": [{"level": None}, {"level": "warn"}]}
        assert LogEntry(line_number=1, data=data).level == "warn"

    def test_all_null_is_still_none(self) -> None:
        log = LogEntry(line_number=1, data={"level": None, "severity": None})
        assert log.level is None
