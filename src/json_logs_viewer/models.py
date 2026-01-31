"""Core data models for JSON logs viewer."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class LogLevel(Enum):
    """Standard log levels with display ordering."""

    ERROR = ("error", 1)
    WARNING = ("warning", 2)
    INFO = ("info", 3)
    DEBUG = ("debug", 4)
    TRACE = ("trace", 5)

    def __init__(self, value: str, order: int) -> None:
        self._value = value
        self._order = order

    @property
    def order(self) -> int:
        """Return display order (lower = higher priority)."""
        return self._order

    @classmethod
    def from_string(cls, level_str: str) -> LogLevel:
        """Parse level string to enum, defaulting to INFO."""
        normalized = level_str.lower().strip()
        for level in cls:
            if level._value == normalized:
                return level
        return cls.INFO


@dataclass(frozen=True, slots=True)
class LogEntry:
    """Represents a single parsed log entry."""

    raw_line: str
    parsed_data: dict[str, Any]
    line_number: int
    timestamp: datetime | None = None
    level: LogLevel = field(default_factory=lambda: LogLevel.INFO)
    message: str = ""

    def __post_init__(self) -> None:
        """Validate required fields after initialization."""
        if not isinstance(self.raw_line, str):
            raise TypeError("raw_line must be a string")
        if not isinstance(self.parsed_data, dict):
            raise TypeError("parsed_data must be a dict")
        if not isinstance(self.line_number, int) or self.line_number < 1:
            raise ValueError("line_number must be a positive integer")

    def to_formatted_json(self, *, indent: int = 2) -> str:
        """Return formatted JSON representation of the parsed data."""
        return json.dumps(self.parsed_data, indent=indent, default=str)

    def get_field(  # noqa: ANN401
        self,
        *,
        field_name: str,
        default: Any = None,  # noqa: ANN401
    ) -> Any:  # noqa: ANN401
        """Safely get a field from parsed data."""
        return self.parsed_data.get(field_name, default)


@dataclass(frozen=True, slots=True)
class FilterToken:
    """Represents a single filter token in a query."""

    field: str | None
    value: str
    operator: str = "eq"  # eq, gt, lt, gte, lte, ne, exists
    negated: bool = False

    def __post_init__(self) -> None:
        """Validate token fields."""
        if self.field is not None and not isinstance(self.field, str):
            raise TypeError("field must be a string or None")
        if not isinstance(self.value, str):
            raise TypeError("value must be a string")
        if self.operator not in (
            "eq",
            "gt",
            "lt",
            "gte",
            "lte",
            "ne",
            "exists",
        ):
            raise ValueError(f"invalid operator: {self.operator}")


@dataclass(frozen=True, slots=True)
class FilterPredicate:
    """Represents a compiled filter predicate with boolean operator."""

    tokens: list[FilterToken]
    boolean_op: str = "AND"  # AND or OR

    def __post_init__(self) -> None:
        """Validate boolean operator."""
        if self.boolean_op not in ("AND", "OR"):
            raise ValueError("boolean_op must be AND or OR")


@dataclass(frozen=True, slots=True)
class FilterState:
    """Represents the current filter configuration."""

    raw_query: str
    parsed_filters: list[FilterPredicate] = field(default_factory=list)
    enabled_levels: set[LogLevel] = field(
        default_factory=lambda: set(LogLevel)
    )
    case_sensitive: bool = False

    def __post_init__(self) -> None:
        """Validate filter state."""
        if not isinstance(self.raw_query, str):
            raise TypeError("raw_query must be a string")
        if not isinstance(self.enabled_levels, set):
            raise TypeError("enabled_levels must be a set")

    def is_level_enabled(self, *, level: LogLevel) -> bool:
        """Check if a specific log level is enabled."""
        return level in self.enabled_levels

    def with_level_toggled(self, *, level: LogLevel) -> FilterState:
        """Return a new FilterState with the level toggled."""
        new_levels = set(self.enabled_levels)
        if level in new_levels:
            new_levels.discard(level)
        else:
            new_levels.add(level)
        return FilterState(
            raw_query=self.raw_query,
            parsed_filters=list(self.parsed_filters),
            enabled_levels=new_levels,
            case_sensitive=self.case_sensitive,
        )


@dataclass(frozen=True, slots=True)
class SearchHistoryEntry:
    """Represents a single search history entry."""

    query: str
    timestamp: datetime = field(default_factory=datetime.now)
    execution_count: int = 1

    def __post_init__(self) -> None:
        """Validate history entry."""
        if not isinstance(self.query, str):
            raise TypeError("query must be a string")
        if (
            not isinstance(self.execution_count, int)
            or self.execution_count < 1
        ):
            raise ValueError("execution_count must be a positive integer")


@dataclass
class SearchHistory:
    """Manages search history with a max size limit."""

    max_size: int = 100
    entries: list[SearchHistoryEntry] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate max size."""
        if not isinstance(self.max_size, int) or self.max_size < 1:
            raise ValueError("max_size must be a positive integer")

    def add(self, *, query: str) -> None:
        """Add a query to history, removing duplicates and respecting max."""
        now = datetime.now()

        # Check if query already exists
        for i, entry in enumerate(self.entries):
            if entry.query == query:
                # Update existing entry with new timestamp and increment count
                self.entries.pop(i)
                self.entries.insert(
                    0,
                    SearchHistoryEntry(
                        query=query,
                        timestamp=now,
                        execution_count=entry.execution_count + 1,
                    ),
                )
                return

        # Add new entry at the beginning
        self.entries.insert(0, SearchHistoryEntry(query=query, timestamp=now))

        # Trim to max size
        if len(self.entries) > self.max_size:
            self.entries = self.entries[: self.max_size]

    def get_recent(self, *, count: int = 10) -> list[SearchHistoryEntry]:
        """Get the most recent search history entries."""
        return self.entries[: min(count, len(self.entries))]

    def clear(self) -> None:
        """Clear all history entries."""
        self.entries.clear()
