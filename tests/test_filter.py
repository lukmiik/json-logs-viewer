"""Tests for query parser and filter engine."""

from __future__ import annotations

import pytest

from json_logs_viewer.filter import (
    FilterEngine,
    QueryParseError,
    QueryParser,
    create_filter_state,
)
from json_logs_viewer.models import (
    FilterPredicate,
    FilterState,
    FilterToken,
    LogEntry,
    LogLevel,
)


class TestQueryParser:
    """Tests for QueryParser."""

    def test_empty_query(self) -> None:
        """Test parsing empty query returns empty predicates."""
        parser = QueryParser()
        result = parser.parse(query="")
        assert result.predicates == []
        assert result.raw_query == ""

    def test_whitespace_only_query(self) -> None:
        """Test parsing whitespace-only query returns empty predicates."""
        parser = QueryParser()
        result = parser.parse(query="   ")
        assert result.predicates == []

    def test_simple_field_value(self) -> None:
        """Test parsing simple field:value token."""
        parser = QueryParser()
        result = parser.parse(query="level:error")

        assert len(result.predicates) == 1
        assert result.predicates[0].boolean_op == "AND"
        assert len(result.predicates[0].tokens) == 1

        token = result.predicates[0].tokens[0]
        assert token.field == "level"
        assert token.value == "error"
        assert token.operator == "eq"
        assert token.negated is False

    def test_text_search_no_field(self) -> None:
        """Test parsing text search without field."""
        parser = QueryParser()
        result = parser.parse(query="timeout")

        assert len(result.predicates) == 1
        token = result.predicates[0].tokens[0]
        assert token.field is None
        assert token.value == "timeout"

    def test_quoted_value(self) -> None:
        """Test parsing quoted values."""
        parser = QueryParser()
        result = parser.parse(query='message:"connection timeout"')

        token = result.predicates[0].tokens[0]
        assert token.field == "message"
        assert token.value == "connection timeout"

    def test_multiple_tokens_and(self) -> None:
        """Test parsing multiple tokens with implicit AND."""
        parser = QueryParser()
        result = parser.parse(query="level:error message:timeout")

        assert len(result.predicates) == 1
        assert result.predicates[0].boolean_op == "AND"
        assert len(result.predicates[0].tokens) == 2

        token1, token2 = result.predicates[0].tokens
        assert token1.field == "level"
        assert token1.value == "error"
        assert token2.field == "message"
        assert token2.value == "timeout"

    def test_explicit_and_operator(self) -> None:
        """Test parsing with explicit AND operator."""
        parser = QueryParser()
        result = parser.parse(query="level:error AND message:timeout")

        assert len(result.predicates) == 1
        assert result.predicates[0].boolean_op == "AND"

    def test_or_operator(self) -> None:
        """Test parsing with OR operator."""
        parser = QueryParser()
        result = parser.parse(query="level:error OR level:warning")

        # First token defaults to AND, second becomes OR
        assert len(result.predicates) == 2
        assert result.predicates[0].boolean_op == "AND"
        assert result.predicates[1].boolean_op == "OR"

    def test_mixed_and_or_creates_multiple_predicates(self) -> None:
        """Test that mixed AND/OR creates separate predicates."""
        parser = QueryParser()
        result = parser.parse(
            query="level:error OR level:warning AND message:timeout"
        )

        # Creates 3 predicates: AND(level:error), OR(level:warning),
        # AND(message:timeout)
        assert len(result.predicates) == 3
        assert result.predicates[0].boolean_op == "AND"
        assert result.predicates[1].boolean_op == "OR"
        assert result.predicates[2].boolean_op == "AND"

    def test_leading_negation(self) -> None:
        """Test leading negation with !."""
        parser = QueryParser()
        result = parser.parse(query="!level:debug")

        token = result.predicates[0].tokens[0]
        assert token.field == "level"
        assert token.value == "debug"
        assert token.negated is True

    def test_value_negation(self) -> None:
        """Test value negation with field:!value - treated as != operator."""
        parser = QueryParser()
        result = parser.parse(query="level:!debug")

        token = result.predicates[0].tokens[0]
        assert token.field == "level"
        assert token.value == "debug"
        assert token.operator == "ne"  # ! is parsed as "not equal" operator

    def test_exists_check(self) -> None:
        """Test has:field for exists check."""
        parser = QueryParser()
        result = parser.parse(query="has:stacktrace")

        token = result.predicates[0].tokens[0]
        assert token.field == "stacktrace"
        assert token.value == ""
        assert token.operator == "exists"

    def test_exists_with_negation(self) -> None:
        """Test negated exists check."""
        parser = QueryParser()
        result = parser.parse(query="!has:stacktrace")

        token = result.predicates[0].tokens[0]
        assert token.field == "stacktrace"
        assert token.operator == "exists"
        assert token.negated is True

    def test_numeric_greater_than(self) -> None:
        """Test numeric comparison >."""
        parser = QueryParser()
        result = parser.parse(query="duration:>1000")

        token = result.predicates[0].tokens[0]
        assert token.field == "duration"
        assert token.value == "1000"
        assert token.operator == "gt"

    def test_numeric_greater_equal(self) -> None:
        """Test numeric comparison >=."""
        parser = QueryParser()
        result = parser.parse(query="duration:>=1000")

        token = result.predicates[0].tokens[0]
        assert token.operator == "gte"
        assert token.value == "1000"

    def test_numeric_less_than(self) -> None:
        """Test numeric comparison <."""
        parser = QueryParser()
        result = parser.parse(query="duration:<1000")

        token = result.predicates[0].tokens[0]
        assert token.operator == "lt"
        assert token.value == "1000"

    def test_numeric_less_equal(self) -> None:
        """Test numeric comparison <=."""
        parser = QueryParser()
        result = parser.parse(query="duration:<=1000")

        token = result.predicates[0].tokens[0]
        assert token.operator == "lte"

    def test_numeric_not_equal(self) -> None:
        """Test numeric comparison !=."""
        parser = QueryParser()
        result = parser.parse(query="duration:!=1000")

        token = result.predicates[0].tokens[0]
        assert token.operator == "ne"

    def test_invalid_quote_raises_error(self) -> None:
        """Test that unclosed quotes raise parse error."""
        parser = QueryParser()
        with pytest.raises(QueryParseError, match="Invalid quoting"):
            parser.parse(query='message:"unclosed quote')

    def test_complex_query(self) -> None:
        """Test parsing a complex query with multiple features."""
        parser = QueryParser()
        result = parser.parse(
            query=(
                'level:error OR level:warning message:"timeout" duration:>5000'
            )
        )

        # Creates 2 predicates. Second OR predicate has 3 tokens.
        # All tokens after OR stay with OR until another operator.
        assert len(result.predicates) == 2
        assert result.predicates[0].boolean_op == "AND"
        assert result.predicates[1].boolean_op == "OR"
        # Verify the OR predicate has all 3 tokens
        assert len(result.predicates[1].tokens) == 3


class TestFilterEngine:
    """Tests for FilterEngine."""

    @pytest.fixture
    def sample_entries(self) -> list[LogEntry]:
        """Create sample log entries for testing."""
        return [
            LogEntry(
                raw_line=(
                    '{"level": "error", "msg": "connection timeout", '
                    '"duration": 5000}'
                ),
                parsed_data={
                    "level": "error",
                    "msg": "connection timeout",
                    "duration": 5000,
                },
                line_number=1,
                level=LogLevel.ERROR,
                message="connection timeout",
            ),
            LogEntry(
                raw_line=(
                    '{"level": "warning", "msg": "slow query", '
                    '"duration": 3000}'
                ),
                parsed_data={
                    "level": "warning",
                    "msg": "slow query",
                    "duration": 3000,
                },
                line_number=2,
                level=LogLevel.WARNING,
                message="slow query",
            ),
            LogEntry(
                raw_line=(
                    '{"level": "info", "msg": "request completed", '
                    '"duration": 100, "trace_id": "abc123"}'
                ),
                parsed_data={
                    "level": "info",
                    "msg": "request completed",
                    "duration": 100,
                    "trace_id": "abc123",
                },
                line_number=3,
                level=LogLevel.INFO,
                message="request completed",
            ),
            LogEntry(
                raw_line='{"level": "debug", "msg": "debug info"}',
                parsed_data={"level": "debug", "msg": "debug info"},
                line_number=4,
                level=LogLevel.DEBUG,
                message="debug info",
            ),
        ]

    def test_empty_predicates_returns_all_entries(
        self, sample_entries: list[LogEntry]
    ) -> None:
        """Test that empty predicates filter returns all entries."""
        engine = FilterEngine()
        result = engine.apply_filters(
            entries=sample_entries,
            predicates=[],
            enabled_levels=set(LogLevel),
        )
        assert len(result) == 4

    def test_filter_by_level_field(
        self, sample_entries: list[LogEntry]
    ) -> None:
        """Test filtering by level field."""
        engine = FilterEngine()
        predicates = engine.compile_query(query="level:error")
        result = engine.apply_filters(
            entries=sample_entries,
            predicates=predicates,
            enabled_levels=set(LogLevel),
        )
        assert len(result) == 1
        assert result[0].level == LogLevel.ERROR

    def test_filter_by_message_substring(
        self, sample_entries: list[LogEntry]
    ) -> None:
        """Test filtering by message substring."""
        engine = FilterEngine()
        predicates = engine.compile_query(query="msg:timeout")
        result = engine.apply_filters(
            entries=sample_entries,
            predicates=predicates,
            enabled_levels=set(LogLevel),
        )
        assert len(result) == 1
        assert "timeout" in result[0].message

    def test_text_search_across_all_fields(
        self, sample_entries: list[LogEntry]
    ) -> None:
        """Test text search across all fields."""
        engine = FilterEngine()
        predicates = engine.compile_query(query="timeout")
        result = engine.apply_filters(
            entries=sample_entries,
            predicates=predicates,
            enabled_levels=set(LogLevel),
        )
        assert len(result) == 1

    def test_filter_with_or_operator(
        self, sample_entries: list[LogEntry]
    ) -> None:
        """Test OR operator filtering within a single predicate."""
        # Note: "level:error OR level:warning" creates two predicates.
        # We manually create OR predicate for testing.
        engine = FilterEngine()

        or_pred = FilterPredicate(
            tokens=[
                FilterToken(field="level", value="error"),
                FilterToken(field="level", value="warning"),
            ],
            boolean_op="OR",
        )
        result = engine.apply_filters(
            entries=sample_entries,
            predicates=[or_pred],
            enabled_levels=set(LogLevel),
        )
        assert len(result) == 2
        assert all(
            e.level in (LogLevel.ERROR, LogLevel.WARNING) for e in result
        )

    def test_filter_with_and_operator(
        self, sample_entries: list[LogEntry]
    ) -> None:
        """Test AND operator filtering."""
        engine = FilterEngine()
        predicates = engine.compile_query(query="level:error duration:5000")
        result = engine.apply_filters(
            entries=sample_entries,
            predicates=predicates,
            enabled_levels=set(LogLevel),
        )
        assert len(result) == 1
        assert result[0].level == LogLevel.ERROR

    def test_filter_with_negation(
        self, sample_entries: list[LogEntry]
    ) -> None:
        """Test negation filtering."""
        engine = FilterEngine()
        predicates = engine.compile_query(query="!level:error")
        result = engine.apply_filters(
            entries=sample_entries,
            predicates=predicates,
            enabled_levels=set(LogLevel),
        )
        assert len(result) == 3
        assert all(e.level != LogLevel.ERROR for e in result)

    def test_filter_with_exists_check(
        self, sample_entries: list[LogEntry]
    ) -> None:
        """Test exists check filtering."""
        engine = FilterEngine()
        predicates = engine.compile_query(query="has:trace_id")
        result = engine.apply_filters(
            entries=sample_entries,
            predicates=predicates,
            enabled_levels=set(LogLevel),
        )
        assert len(result) == 1
        assert result[0].get_field(field_name="trace_id") == "abc123"

    def test_filter_with_numeric_greater_than(
        self, sample_entries: list[LogEntry]
    ) -> None:
        """Test numeric > comparison."""
        engine = FilterEngine()
        predicates = engine.compile_query(query="duration:>1000")
        result = engine.apply_filters(
            entries=sample_entries,
            predicates=predicates,
            enabled_levels=set(LogLevel),
        )
        assert len(result) == 2
        assert all(
            e.get_field(field_name="duration", default=0) > 1000
            for e in result
        )

    def test_filter_with_numeric_less_than(
        self, sample_entries: list[LogEntry]
    ) -> None:
        """Test numeric < comparison."""
        engine = FilterEngine()
        predicates = engine.compile_query(query="duration:<1000")
        result = engine.apply_filters(
            entries=sample_entries,
            predicates=predicates,
            enabled_levels=set(LogLevel),
        )
        assert len(result) == 1
        assert result[0].get_field(field_name="duration") == 100

    def test_level_filter_integration(
        self, sample_entries: list[LogEntry]
    ) -> None:
        """Test that enabled_levels filter works alongside query filters."""
        engine = FilterEngine()
        predicates = engine.compile_query(query="duration:>0")
        result = engine.apply_filters(
            entries=sample_entries,
            predicates=predicates,
            enabled_levels={LogLevel.ERROR, LogLevel.WARNING},
        )
        assert len(result) == 2
        assert all(
            e.level in (LogLevel.ERROR, LogLevel.WARNING) for e in result
        )

    def test_case_sensitive_filter(
        self, sample_entries: list[LogEntry]
    ) -> None:
        """Test case-sensitive filtering."""
        engine = FilterEngine()
        predicates = engine.compile_query(query="msg:TIMEOUT")
        result_sensitive = engine.apply_filters(
            entries=sample_entries,
            predicates=predicates,
            enabled_levels=set(LogLevel),
            case_sensitive=True,
        )
        result_insensitive = engine.apply_filters(
            entries=sample_entries,
            predicates=predicates,
            enabled_levels=set(LogLevel),
            case_sensitive=False,
        )
        assert len(result_sensitive) == 0  # No exact case match
        assert len(result_insensitive) == 1  # Case-insensitive matches

    def test_quoted_value_filter(self, sample_entries: list[LogEntry]) -> None:
        """Test filtering with quoted multi-word values."""
        engine = FilterEngine()
        predicates = engine.compile_query(query='msg:"connection timeout"')
        result = engine.apply_filters(
            entries=sample_entries,
            predicates=predicates,
            enabled_levels=set(LogLevel),
        )
        assert len(result) == 1
        assert result[0].message == "connection timeout"

    def test_nonexistent_field_returns_no_match(
        self, sample_entries: list[LogEntry]
    ) -> None:
        """Test that filtering on nonexistent field returns no match."""
        engine = FilterEngine()
        predicates = engine.compile_query(query="nonexistent:value")
        result = engine.apply_filters(
            entries=sample_entries,
            predicates=predicates,
            enabled_levels=set(LogLevel),
        )
        assert len(result) == 0


class TestCreateFilterState:
    """Tests for create_filter_state helper."""

    def test_create_empty_filter_state(self) -> None:
        """Test creating filter state with empty query."""
        state = create_filter_state(query="")
        assert isinstance(state, FilterState)
        assert state.raw_query == ""
        assert state.parsed_filters == []
        assert len(state.enabled_levels) == 5

    def test_create_filter_state_with_query(self) -> None:
        """Test creating filter state with query."""
        state = create_filter_state(query="level:error")
        assert state.raw_query == "level:error"
        assert len(state.parsed_filters) == 1

    def test_create_filter_state_with_levels(self) -> None:
        """Test creating filter state with custom levels."""
        state = create_filter_state(
            query="",
            enabled_levels={LogLevel.ERROR, LogLevel.WARNING},
        )
        assert state.enabled_levels == {LogLevel.ERROR, LogLevel.WARNING}


class TestQueryParseError:
    """Tests for QueryParseError."""

    def test_error_message(self) -> None:
        """Test error message format."""
        error = QueryParseError(message="Invalid syntax", position=5)
        assert "Parse error at position 5" in str(error)
        assert "Invalid syntax" in str(error)
        assert error.position == 5
        assert error.message == "Invalid syntax"
