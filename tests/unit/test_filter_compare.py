"""Comparison operators (<, <=, >, >=) and last:<duration> in queries."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from json_logs_viewer.filter_engine import (
    Compare,
    FieldMatch,
    FilterError,
    Parser,
    Tokenizer,
    TokenType,
    parse_filter,
)
from json_logs_viewer.models import LogEntry


def entry(**data: Any) -> LogEntry:  # noqa: ANN401
    return LogEntry(line_number=1, data=data)


def matches(query: str, **data: Any) -> bool:  # noqa: ANN401
    return parse_filter(query=query)(entry(**data))


class TestTokenizer:
    @pytest.mark.parametrize("query", ["a>=1", "a >= 1", "a>= 1", "a >=1"])
    def test_operator_with_or_without_spaces(self, query: str) -> None:
        tokens = Tokenizer(query).tokenize()
        assert [(t.type, t.value) for t in tokens[:-1]] == [
            (TokenType.FIELD, "a"),
            (TokenType.OP, ">="),
            (TokenType.VALUE, "1"),
        ]

    @pytest.mark.parametrize("op", ["<", "<=", ">", ">="])
    def test_every_operator(self, op: str) -> None:
        ast = Parser(Tokenizer(f"n{op}5").tokenize()).parse()
        assert ast == Compare(field="n", op=op, value="5")

    def test_timestamp_value_keeps_its_colons(self) -> None:
        ast = Parser(Tokenizer("ts>=2024-01-15T10:00:00Z").tokenize()).parse()
        assert ast == Compare(
            field="ts", op=">=", value="2024-01-15T10:00:00Z"
        )

    def test_missing_value_is_an_error(self) -> None:
        with pytest.raises(FilterError, match="value after >="):
            parse_filter(query="a>=")


class TestNumbers:
    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            ("code>=500", True),
            ("code>502", False),
            ("code<503", True),
            ("code<=501", False),
            ("code>=500.5", True),
        ],
    )
    def test_number_field(self, query: str, expected: bool) -> None:
        assert matches(query, code=502) is expected

    def test_numeric_string_and_nested_field(self) -> None:
        assert matches("http.status>=500", http={"status": "504"})

    @pytest.mark.parametrize("value", [True, None, "n/a", {"a": 1}])
    def test_non_numbers_never_match(self, value: object) -> None:
        assert not matches("code>=0", code=value)
        assert not matches("code<0", code=value)

    def test_missing_field_never_matches(self) -> None:
        assert not matches("code>=0", other=1)


class TestDatetimes:
    TS = "2024-01-15T10:30:00Z"

    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            ("ts>=2024-01-15T10:00", True),  # no zone: UTC
            ("ts>=2024-01-15T10:31", False),
            ("ts<2024-01-16", True),  # date only: midnight UTC
            ("ts<2024-01-15", False),
            ("ts>=2024-01-15T11:00+01:00", True),  # = 10:00 UTC
            ("ts>2024-01-15T11:00+02:00", True),  # 09:00 UTC
            ('ts>="2024-01-15 10:00"', True),  # space form, quoted
        ],
    )
    def test_iso_timestamps(self, query: str, expected: bool) -> None:
        assert matches(query, ts=self.TS) is expected

    def test_nanoseconds_and_offsets_in_logs(self) -> None:
        assert matches(
            "ts>=2024-01-15T10:00", ts="2024-01-15T10:00:00.123456789Z"
        )
        assert matches("ts<2024-01-15T10:00", ts="2024-01-15T10:30:00+01:00")

    def test_epoch_seconds_and_milliseconds(self) -> None:
        epoch = datetime(2024, 1, 15, 10, 30, tzinfo=UTC).timestamp()
        assert matches("ts>=2024-01-15T10:00", ts=epoch)
        assert matches("ts>=2024-01-15T10:00", ts=int(epoch * 1000))
        assert not matches("ts>=2024-01-15T11:00", ts=epoch)

    def test_unparseable_log_values_never_match(self) -> None:
        assert not matches("ts>=2024-01-15", ts="yesterday")
        assert not matches("ts<2024-01-15", ts="yesterday")


def test_value_that_is_neither_number_nor_time_is_an_error() -> None:
    with pytest.raises(FilterError, match="number or a date"):
        parse_filter(query="level>=WARN")


def test_combines_with_other_terms() -> None:
    query = "level:error code>=500 OR NOT code<600"
    assert parse_filter(query=query)(entry(level="ERROR", code=503))
    assert not parse_filter(query=query)(entry(level="INFO", code=503))
    assert parse_filter(query=query)(entry(level="INFO", code=700))


class TestLast:
    NEWEST = datetime(2024, 1, 15, 12, 0, tzinfo=UTC)

    def _matcher(self, query: str):  # noqa: ANN202
        return parse_filter(query=query, newest_timestamp=lambda: self.NEWEST)

    @pytest.mark.parametrize(
        ("query", "timestamp", "expected"),
        [
            ("last:15m", "2024-01-15T11:50:00Z", True),
            ("last:15m", "2024-01-15T11:40:00Z", False),
            ("last:2h", "2024-01-15T10:30:00Z", True),
            ("last:30s", "2024-01-15T11:59:45Z", True),
            ("last:1d", "2024-01-14T11:00:00Z", False),
        ],
    )
    def test_window_before_the_newest_log(
        self, query: str, timestamp: str, expected: bool
    ) -> None:
        log = LogEntry(line_number=1, data={"timestamp": timestamp})
        assert self._matcher(query)(log) is expected

    def test_logs_without_timestamp_never_match(self) -> None:
        assert not self._matcher("last:15m")(entry(msg="no time"))

    def test_no_logs_with_timestamps_match_nothing(self) -> None:
        matcher = parse_filter(query="last:15m", newest_timestamp=lambda: None)
        log = LogEntry(line_number=1, data={"timestamp": "2024-01-15T11:59Z"})
        assert not matcher(log)

    def test_a_non_duration_is_a_normal_field_match(self) -> None:
        ast = Parser(Tokenizer("last:week").tokenize()).parse()
        assert ast == FieldMatch(field="last", value="week")

    def test_relative_queries_are_flagged(self) -> None:
        assert self._matcher("level:error last:5m").relative
        assert not self._matcher("level:error").relative
