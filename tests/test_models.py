"""Tests for core data models."""

from datetime import datetime

import pytest

from json_logs_viewer.models import (
    FilterPredicate,
    FilterState,
    FilterToken,
    LogEntry,
    LogLevel,
    SearchHistory,
    SearchHistoryEntry,
)


class TestLogLevel:
    """Tests for LogLevel enum."""

    def test_level_values(self) -> None:
        """Test that all levels have correct string values."""
        assert LogLevel.ERROR._value == "error"
        assert LogLevel.WARNING._value == "warning"
        assert LogLevel.INFO._value == "info"
        assert LogLevel.DEBUG._value == "debug"
        assert LogLevel.TRACE._value == "trace"

    def test_level_order(self) -> None:
        """Test that levels have correct display order."""
        assert LogLevel.ERROR.order == 1
        assert LogLevel.WARNING.order == 2
        assert LogLevel.INFO.order == 3
        assert LogLevel.DEBUG.order == 4
        assert LogLevel.TRACE.order == 5

    def test_from_string_exact_match(self) -> None:
        """Test parsing exact level strings."""
        assert LogLevel.from_string("error") == LogLevel.ERROR
        assert LogLevel.from_string("ERROR") == LogLevel.ERROR
        assert LogLevel.from_string("warning") == LogLevel.WARNING
        assert LogLevel.from_string("WARNING") == LogLevel.WARNING
        assert LogLevel.from_string("info") == LogLevel.INFO
        assert LogLevel.from_string("INFO") == LogLevel.INFO

    def test_from_string_whitespace(self) -> None:
        """Test parsing level strings with whitespace."""
        assert LogLevel.from_string("  error  ") == LogLevel.ERROR

    def test_from_string_unknown_defaults_to_info(self) -> None:
        """Test that unknown level strings default to INFO."""
        assert LogLevel.from_string("unknown") == LogLevel.INFO
        assert LogLevel.from_string("") == LogLevel.INFO


class TestLogEntry:
    """Tests for LogEntry dataclass."""

    def test_basic_creation(self) -> None:
        """Test creating a basic log entry."""
        entry = LogEntry(
            raw_line='{"level": "info", "msg": "hello"}',
            parsed_data={"level": "info", "msg": "hello"},
            line_number=1,
        )
        assert entry.raw_line == '{"level": "info", "msg": "hello"}'
        assert entry.parsed_data == {"level": "info", "msg": "hello"}
        assert entry.line_number == 1
        assert entry.timestamp is None
        assert entry.level == LogLevel.INFO
        assert entry.message == ""

    def test_full_creation(self) -> None:
        """Test creating a log entry with all fields."""
        now = datetime.now()
        entry = LogEntry(
            raw_line='{"level": "error", "msg": "failed"}',
            parsed_data={"level": "error", "msg": "failed"},
            line_number=5,
            timestamp=now,
            level=LogLevel.ERROR,
            message="failed",
        )
        assert entry.timestamp == now
        assert entry.level == LogLevel.ERROR
        assert entry.message == "failed"

    def test_invalid_line_number_raises(self) -> None:
        """Test that invalid line numbers raise ValueError."""
        with pytest.raises(ValueError, match="line_number must be a positive"):
            LogEntry(
                raw_line="test",
                parsed_data={},
                line_number=0,
            )

        with pytest.raises(ValueError, match="line_number must be a positive"):
            LogEntry(
                raw_line="test",
                parsed_data={},
                line_number=-1,
            )

    def test_invalid_raw_line_type_raises(self) -> None:
        """Test that non-string raw_line raises TypeError."""
        with pytest.raises(TypeError, match="raw_line must be a string"):
            LogEntry(
                raw_line=123,  # type: ignore[arg-type]
                parsed_data={},
                line_number=1,
            )

    def test_invalid_parsed_data_type_raises(self) -> None:
        """Test that non-dict parsed_data raises TypeError."""
        with pytest.raises(TypeError, match="parsed_data must be a dict"):
            LogEntry(
                raw_line="test",
                parsed_data=[],  # type: ignore[arg-type]
                line_number=1,
            )

    def test_to_formatted_json(self) -> None:
        """Test JSON formatting."""
        entry = LogEntry(
            raw_line='{"key": "value"}',
            parsed_data={"key": "value", "num": 42},
            line_number=1,
        )
        formatted = entry.to_formatted_json()
        assert '"key": "value"' in formatted
        assert '"num": 42' in formatted

    def test_to_formatted_json_custom_indent(self) -> None:
        """Test JSON formatting with custom indent."""
        entry = LogEntry(
            raw_line='{"key": "value"}',
            parsed_data={"key": "value"},
            line_number=1,
        )
        formatted = entry.to_formatted_json(indent=4)
        assert "    " in formatted  # 4-space indent

    def test_get_field_existing(self) -> None:
        """Test getting an existing field."""
        entry = LogEntry(
            raw_line='{"key": "value"}',
            parsed_data={"key": "value", "num": 42},
            line_number=1,
        )
        assert entry.get_field(field_name="key") == "value"
        assert entry.get_field(field_name="num") == 42

    def test_get_field_missing_with_default(self) -> None:
        """Test getting a missing field with default."""
        entry = LogEntry(
            raw_line="{}",
            parsed_data={},
            line_number=1,
        )
        assert entry.get_field(field_name="missing") is None
        assert (
            entry.get_field(field_name="missing", default="default")
            == "default"
        )


class TestFilterToken:
    """Tests for FilterToken dataclass."""

    def test_basic_creation(self) -> None:
        """Test creating a basic filter token."""
        token = FilterToken(field="level", value="error")
        assert token.field == "level"
        assert token.value == "error"
        assert token.operator == "eq"
        assert token.negated is False

    def test_full_creation(self) -> None:
        """Test creating a filter token with all fields."""
        token = FilterToken(
            field="duration",
            value="1000",
            operator="gt",
            negated=True,
        )
        assert token.field == "duration"
        assert token.value == "1000"
        assert token.operator == "gt"
        assert token.negated is True

    def test_none_field_allowed(self) -> None:
        """Test that None field is allowed for text search."""
        token = FilterToken(field=None, value="search term")
        assert token.field is None

    def test_invalid_operator_raises(self) -> None:
        """Test that invalid operator raises ValueError."""
        with pytest.raises(ValueError, match="invalid operator"):
            FilterToken(field="level", value="error", operator="invalid")

    def test_invalid_field_type_raises(self) -> None:
        """Test that non-string field raises TypeError."""
        with pytest.raises(TypeError, match="field must be a string or None"):
            FilterToken(field=123, value="error")  # type: ignore[arg-type]

    def test_invalid_value_type_raises(self) -> None:
        """Test that non-string value raises TypeError."""
        with pytest.raises(TypeError, match="value must be a string"):
            FilterToken(field="level", value=123)  # type: ignore[arg-type]


class TestFilterPredicate:
    """Tests for FilterPredicate dataclass."""

    def test_basic_creation(self) -> None:
        """Test creating a filter predicate."""
        token = FilterToken(field="level", value="error")
        pred = FilterPredicate(tokens=[token])
        assert pred.tokens == [token]
        assert pred.boolean_op == "AND"

    def test_or_operator(self) -> None:
        """Test creating an OR predicate."""
        token1 = FilterToken(field="level", value="error")
        token2 = FilterToken(field="level", value="warning")
        pred = FilterPredicate(tokens=[token1, token2], boolean_op="OR")
        assert pred.boolean_op == "OR"

    def test_invalid_boolean_op_raises(self) -> None:
        """Test that invalid boolean operator raises ValueError."""
        with pytest.raises(ValueError, match="boolean_op must be AND or OR"):
            FilterPredicate(tokens=[], boolean_op="XOR")


class TestFilterState:
    """Tests for FilterState dataclass."""

    def test_default_creation(self) -> None:
        """Test creating a filter state with defaults."""
        state = FilterState(raw_query="")
        assert state.raw_query == ""
        assert state.parsed_filters == []
        assert state.case_sensitive is False
        assert len(state.enabled_levels) == 5
        assert all(lvl in state.enabled_levels for lvl in LogLevel)

    def test_custom_creation(self) -> None:
        """Test creating a filter state with custom values."""
        token = FilterToken(field="level", value="error")
        pred = FilterPredicate(tokens=[token])
        state = FilterState(
            raw_query="level:error",
            parsed_filters=[pred],
            enabled_levels={LogLevel.ERROR, LogLevel.WARNING},
            case_sensitive=True,
        )
        assert state.raw_query == "level:error"
        assert len(state.parsed_filters) == 1
        assert state.enabled_levels == {LogLevel.ERROR, LogLevel.WARNING}
        assert state.case_sensitive is True

    def test_invalid_raw_query_type_raises(self) -> None:
        """Test that non-string raw_query raises TypeError."""
        with pytest.raises(TypeError, match="raw_query must be a string"):
            FilterState(raw_query=123)  # type: ignore[arg-type]

    def test_is_level_enabled(self) -> None:
        """Test checking if level is enabled."""
        state = FilterState(
            raw_query="",
            enabled_levels={LogLevel.ERROR, LogLevel.WARNING},
        )
        assert state.is_level_enabled(level=LogLevel.ERROR) is True
        assert state.is_level_enabled(level=LogLevel.WARNING) is True
        assert state.is_level_enabled(level=LogLevel.INFO) is False

    def test_with_level_toggled_remove(self) -> None:
        """Test toggling off an enabled level."""
        state = FilterState(
            raw_query="test",
            enabled_levels={LogLevel.ERROR, LogLevel.INFO},
        )
        new_state = state.with_level_toggled(level=LogLevel.ERROR)

        assert LogLevel.ERROR not in new_state.enabled_levels
        assert LogLevel.INFO in new_state.enabled_levels
        assert new_state.raw_query == "test"

    def test_with_level_toggled_add(self) -> None:
        """Test toggling on a disabled level."""
        state = FilterState(
            raw_query="test",
            enabled_levels={LogLevel.INFO},
        )
        new_state = state.with_level_toggled(level=LogLevel.ERROR)

        assert LogLevel.ERROR in new_state.enabled_levels
        assert LogLevel.INFO in new_state.enabled_levels

    def test_with_level_toggled_preserves_other_fields(self) -> None:
        """Test that toggling preserves other filter state fields."""
        token = FilterToken(field="level", value="error")
        pred = FilterPredicate(tokens=[token])
        state = FilterState(
            raw_query="level:error",
            parsed_filters=[pred],
            enabled_levels={LogLevel.ERROR},
            case_sensitive=True,
        )
        new_state = state.with_level_toggled(level=LogLevel.INFO)

        assert new_state.raw_query == "level:error"
        assert len(new_state.parsed_filters) == 1
        assert new_state.case_sensitive is True


class TestSearchHistoryEntry:
    """Tests for SearchHistoryEntry dataclass."""

    def test_basic_creation(self) -> None:
        """Test creating a history entry."""
        entry = SearchHistoryEntry(query="test query")
        assert entry.query == "test query"
        assert isinstance(entry.timestamp, datetime)
        assert entry.execution_count == 1

    def test_custom_creation(self) -> None:
        """Test creating a history entry with custom values."""
        now = datetime.now()
        entry = SearchHistoryEntry(
            query="custom",
            timestamp=now,
            execution_count=5,
        )
        assert entry.query == "custom"
        assert entry.timestamp == now
        assert entry.execution_count == 5

    def test_invalid_query_type_raises(self) -> None:
        """Test that non-string query raises TypeError."""
        with pytest.raises(TypeError, match="query must be a string"):
            SearchHistoryEntry(query=123)  # type: ignore[arg-type]

    def test_invalid_count_raises(self) -> None:
        """Test that invalid execution_count raises ValueError."""
        with pytest.raises(
            ValueError, match="execution_count must be a positive"
        ):
            SearchHistoryEntry(query="test", execution_count=0)

        with pytest.raises(
            ValueError, match="execution_count must be a positive"
        ):
            SearchHistoryEntry(query="test", execution_count=-1)


class TestSearchHistory:
    """Tests for SearchHistory class."""

    def test_default_creation(self) -> None:
        """Test creating history with defaults."""
        history = SearchHistory()
        assert history.max_size == 100
        assert history.entries == []

    def test_custom_max_size(self) -> None:
        """Test creating history with custom max size."""
        history = SearchHistory(max_size=50)
        assert history.max_size == 50

    def test_invalid_max_size_raises(self) -> None:
        """Test that invalid max_size raises ValueError."""
        with pytest.raises(ValueError, match="max_size must be a positive"):
            SearchHistory(max_size=0)

        with pytest.raises(ValueError, match="max_size must be a positive"):
            SearchHistory(max_size=-1)

    def test_add_single_entry(self) -> None:
        """Test adding a single entry."""
        history = SearchHistory()
        history.add(query="test query")

        assert len(history.entries) == 1
        assert history.entries[0].query == "test query"
        assert history.entries[0].execution_count == 1

    def test_add_multiple_entries(self) -> None:
        """Test adding multiple entries."""
        history = SearchHistory()
        history.add(query="first")
        history.add(query="second")

        assert len(history.entries) == 2
        assert history.entries[0].query == "second"
        assert history.entries[1].query == "first"

    def test_add_duplicate_moves_to_front(self) -> None:
        """Test that duplicate queries move to front and increment count."""
        history = SearchHistory()
        history.add(query="first")
        history.add(query="second")
        history.add(query="first")

        assert len(history.entries) == 2
        assert history.entries[0].query == "first"
        assert history.entries[0].execution_count == 2
        assert history.entries[1].query == "second"

    def test_add_respects_max_size(self) -> None:
        """Test that history respects max size."""
        history = SearchHistory(max_size=3)
        history.add(query="1")
        history.add(query="2")
        history.add(query="3")
        history.add(query="4")

        assert len(history.entries) == 3
        assert history.entries[0].query == "4"
        assert history.entries[1].query == "3"
        assert history.entries[2].query == "2"
        assert "1" not in [e.query for e in history.entries]

    def test_get_recent_default_count(self) -> None:
        """Test getting recent entries with default count."""
        history = SearchHistory()
        for i in range(20):
            history.add(query=f"query_{i}")

        recent = history.get_recent()
        assert len(recent) == 10
        assert recent[0].query == "query_19"
        assert recent[9].query == "query_10"

    def test_get_recent_custom_count(self) -> None:
        """Test getting recent entries with custom count."""
        history = SearchHistory()
        for i in range(5):
            history.add(query=f"query_{i}")

        recent = history.get_recent(count=3)
        assert len(recent) == 3
        assert recent[0].query == "query_4"
        assert recent[2].query == "query_2"

    def test_get_recent_more_than_available(self) -> None:
        """Test getting more entries than available."""
        history = SearchHistory()
        history.add(query="only")

        recent = history.get_recent(count=10)
        assert len(recent) == 1

    def test_clear(self) -> None:
        """Test clearing history."""
        history = SearchHistory()
        history.add(query="first")
        history.add(query="second")

        history.clear()

        assert history.entries == []
