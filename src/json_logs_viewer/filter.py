"""Query parser and filter engine for log entries."""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from typing import TYPE_CHECKING

from json_logs_viewer.models import FilterPredicate, FilterToken, LogLevel

if TYPE_CHECKING:
    from json_logs_viewer.models import FilterState, LogEntry


class QueryParseError(Exception):
    """Exception raised when query parsing fails."""

    def __init__(self, message: str, position: int = 0) -> None:
        """Initialize with error message and position."""
        self.message = message
        self.position = position
        super().__init__(f"Parse error at position {position}: {message}")


@dataclass(frozen=True)
class ParsedQuery:
    """Result of parsing a query string."""

    predicates: list[FilterPredicate]
    raw_query: str


class QueryParser:
    """Parser for search query syntax.

    Supports:
    - field:value tokens
    - AND/OR operators
    - Negation: !field:value or field:!value
    - Quoted values: message:"connection timeout"
    - Exists check: has:fieldname
    - Numeric comparison: duration:>1000, age:<5, etc.
    - Default text search (tokens without field)
    """

    # Regex for numeric comparison operators
    _NUMERIC_OP_PATTERN = re.compile(r"^([<>]=?|!=?)(.+)$")

    def __init__(self) -> None:
        """Initialize the query parser."""
        pass

    def parse(self, *, query: str) -> ParsedQuery:
        """Parse a query string into filter predicates.

        Args:
            query: The query string to parse.

        Returns:
            ParsedQuery containing the parsed predicates.

        Raises:
            QueryParseError: If the query cannot be parsed.
        """
        if not query or not query.strip():
            return ParsedQuery(predicates=[], raw_query=query)

        # Use shell-like parsing to handle quoted strings
        try:
            tokens = shlex.split(query)
        except ValueError as e:
            raise QueryParseError(
                message=f"Invalid quoting: {e}", position=0
            ) from e

        if not tokens:
            return ParsedQuery(predicates=[], raw_query=query)

        predicates: list[FilterPredicate] = []
        current_tokens: list[FilterToken] = []
        current_op: str | None = None

        i = 0
        while i < len(tokens):
            token = tokens[i]
            upper_token = token.upper()

            if upper_token == "AND":
                # AND operator - commit current group and start new AND group
                if current_tokens:
                    op = current_op if current_op else "AND"
                    predicates.append(
                        FilterPredicate(
                            tokens=list(current_tokens), boolean_op=op
                        )
                    )
                    current_tokens = []
                current_op = "AND"
                i += 1
            elif upper_token == "OR":
                # OR operator - commit current group and start new OR group
                if current_tokens:
                    op = current_op if current_op else "AND"
                    predicates.append(
                        FilterPredicate(
                            tokens=list(current_tokens), boolean_op=op
                        )
                    )
                    current_tokens = []
                current_op = "OR"
                i += 1
            else:
                # Parse the token as a filter
                filter_token = self._parse_token(token=token)
                current_tokens.append(filter_token)
                i += 1

        # Don't forget the last group of tokens
        if current_tokens:
            op = current_op if current_op else "AND"
            predicates.append(
                FilterPredicate(tokens=list(current_tokens), boolean_op=op)
            )

        # Merge adjacent predicates with the same boolean_op
        merged_predicates = self._merge_predicates(predicates)

        return ParsedQuery(predicates=merged_predicates, raw_query=query)

    def _merge_predicates(
        self, predicates: list[FilterPredicate]
    ) -> list[FilterPredicate]:
        """Merge adjacent predicates with the same boolean operator.

        Args:
            predicates: List of predicates to merge.

        Returns:
            List of merged predicates.
        """
        if not predicates:
            return []

        merged: list[FilterPredicate] = [predicates[0]]

        for pred in predicates[1:]:
            last = merged[-1]
            if last.boolean_op == pred.boolean_op:
                # Merge tokens into the last predicate
                merged[-1] = FilterPredicate(
                    tokens=list(last.tokens) + list(pred.tokens),
                    boolean_op=last.boolean_op,
                )
            else:
                merged.append(pred)

        return merged

    def _parse_token(self, *, token: str) -> FilterToken:
        """Parse a single query token into a FilterToken.

        Args:
            token: The token string to parse.

        Returns:
            FilterToken representing the parsed token.
        """
        # Check for leading negation: !field:value or !value
        negated = False
        if token.startswith("!"):
            negated = True
            token = token[1:]

        # Check for has:field (exists check)
        if token.startswith("has:"):
            field = token[4:]
            return FilterToken(
                field=field, value="", operator="exists", negated=negated
            )

        # Split on first colon to get field:value
        if ":" in token:
            colon_idx = token.index(":")
            field = token[:colon_idx]
            value = token[colon_idx + 1 :]

            # Check numeric comparison operators FIRST
            # (before negation check)
            operator = "eq"
            match = self._NUMERIC_OP_PATTERN.match(value)
            if match:
                op_str, num_str = match.groups()
                # Map operator strings
                op_map = {
                    ">": "gt",
                    ">=": "gte",
                    "<": "lt",
                    "<=": "lte",
                    "!=": "ne",
                    "!": "ne",
                }
                if op_str in op_map:
                    operator = op_map[op_str]
                    value = num_str
            elif value.startswith("!"):
                # Check negation: field:!value
                # (only if not already an operator)
                negated = not negated
                value = value[1:]

            return FilterToken(
                field=field, value=value, operator=operator, negated=negated
            )

        # No colon - this is a text search across all fields
        return FilterToken(
            field=None, value=token, operator="eq", negated=negated
        )


class FilterEngine:
    """Engine for applying filters to log entries."""

    def __init__(self) -> None:
        """Initialize the filter engine."""
        self._parser = QueryParser()

    def compile_query(self, *, query: str) -> list[FilterPredicate]:
        """Compile a query string into filter predicates.

        Args:
            query: The query string to compile.

        Returns:
            List of FilterPredicate objects.

        Raises:
            QueryParseError: If the query cannot be parsed.
        """
        parsed = self._parser.parse(query=query)
        return parsed.predicates

    def apply_filters(
        self,
        *,
        entries: list[LogEntry],
        predicates: list[FilterPredicate],
        enabled_levels: set[LogLevel] | None = None,
        case_sensitive: bool = False,
    ) -> list[LogEntry]:
        """Apply filters to a list of log entries.

        Args:
            entries: List of log entries to filter.
            predicates: List of filter predicates to apply.
            enabled_levels: Set of enabled log levels (None = all enabled).
            case_sensitive: Whether filtering should be case-sensitive.

        Returns:
            Filtered list of log entries.
        """
        if enabled_levels is None:
            enabled_levels = set(LogLevel)

        result: list[LogEntry] = []

        for entry in entries:
            # First check level filter
            if entry.level not in enabled_levels:
                continue

            # Then check query predicates
            if predicates and not self._matches_predicates(
                entry=entry,
                predicates=predicates,
                case_sensitive=case_sensitive,
            ):
                continue

            result.append(entry)

        return result

    def _matches_predicates(
        self,
        *,
        entry: LogEntry,
        predicates: list[FilterPredicate],
        case_sensitive: bool,
    ) -> bool:
        """Check if an entry matches all predicates.

        Each predicate is checked independently. OR predicates only need
        one token to match, AND predicates need all tokens to match.
        All predicates must match (AND logic between predicates).

        Args:
            entry: The log entry to check.
            predicates: List of predicates to match.
            case_sensitive: Whether matching should be case-sensitive.

        Returns:
            True if the entry matches all predicates.
        """
        for predicate in predicates:
            if not self._matches_predicate(
                entry=entry, predicate=predicate, case_sensitive=case_sensitive
            ):
                return False
        return True

    def _matches_predicate(
        self,
        *,
        entry: LogEntry,
        predicate: FilterPredicate,
        case_sensitive: bool,
    ) -> bool:
        """Check if an entry matches a single predicate.

        Args:
            entry: The log entry to check.
            predicate: The predicate to match.
            case_sensitive: Whether matching should be case-sensitive.

        Returns:
            True if the entry matches the predicate.
        """
        if not predicate.tokens:
            return True

        if predicate.boolean_op == "AND":
            # All tokens must match
            for token in predicate.tokens:
                if not self._matches_token(
                    entry=entry, token=token, case_sensitive=case_sensitive
                ):
                    return False
            return True
        else:  # OR
            # At least one token must match
            for token in predicate.tokens:
                if self._matches_token(
                    entry=entry, token=token, case_sensitive=case_sensitive
                ):
                    return True
            return False

    def _matches_token(
        self,
        *,
        entry: LogEntry,
        token: FilterToken,
        case_sensitive: bool,
    ) -> bool:
        """Check if an entry matches a single filter token.

        Args:
            entry: The log entry to check.
            token: The filter token to match.
            case_sensitive: Whether matching should be case-sensitive.

        Returns:
            True if the entry matches the token.
        """
        result = self._evaluate_token(
            entry=entry, token=token, case_sensitive=case_sensitive
        )
        return not result if token.negated else result

    def _evaluate_token(
        self,
        *,
        entry: LogEntry,
        token: FilterToken,
        case_sensitive: bool,
    ) -> bool:
        """Evaluate a token against an entry (without considering negation).

        Args:
            entry: The log entry to check.
            token: The filter token to evaluate.
            case_sensitive: Whether matching should be case-sensitive.

        Returns:
            True if the token matches (before applying negation).
        """
        if token.operator == "exists":
            return self._check_exists(entry=entry, field=token.field)

        if token.field is None:
            # Text search across all fields
            return self._text_search(
                entry=entry, value=token.value, case_sensitive=case_sensitive
            )

        # Field-specific search
        field_value = self._get_field_value(entry=entry, field=token.field)

        if field_value is None:
            return False

        # Handle numeric comparisons
        if token.operator in ("gt", "gte", "lt", "lte", "ne"):
            return self._numeric_compare(
                field_value=field_value,
                compare_value=token.value,
                operator=token.operator,
            )

        # Equality check (eq or ne which is handled above)
        return self._value_matches(
            field_value=field_value,
            search_value=token.value,
            case_sensitive=case_sensitive,
        )

    def _check_exists(self, *, entry: LogEntry, field: str | None) -> bool:
        """Check if a field exists in the entry.

        Args:
            entry: The log entry to check.
            field: The field name to check.

        Returns:
            True if the field exists and is not None.
        """
        if field is None:
            return False
        value = entry.get_field(field_name=field)
        return value is not None

    def _text_search(
        self, *, entry: LogEntry, value: str, case_sensitive: bool
    ) -> bool:
        """Search for a value across all fields and the raw line.

        Args:
            entry: The log entry to search.
            value: The value to search for.
            case_sensitive: Whether the search should be case-sensitive.

        Returns:
            True if the value is found in any field or the raw line.
        """
        search_term = value if case_sensitive else value.lower()

        # Search in raw line
        raw = entry.raw_line if case_sensitive else entry.raw_line.lower()
        if search_term in raw:
            return True

        # Search in all fields
        for field_val in entry.parsed_data.values():
            str_val = str(field_val)
            if not case_sensitive:
                str_val = str_val.lower()
            if search_term in str_val:
                return True

        return False

    def _get_field_value(
        self, *, entry: LogEntry, field: str | None
    ) -> object | None:
        """Get a field value from an entry.

        Args:
            entry: The log entry.
            field: The field name.

        Returns:
            The field value or None if not found.
        """
        if field is None:
            return None
        return entry.get_field(field_name=field)

    def _value_matches(
        self,
        *,
        field_value: object,
        search_value: str,
        case_sensitive: bool,
    ) -> bool:
        """Check if a field value matches a search value.

        Args:
            field_value: The value from the entry field.
            search_value: The value to search for.
            case_sensitive: Whether matching should be case-sensitive.

        Returns:
            True if the field value matches the search value.
        """
        str_field = str(field_value)

        if not case_sensitive:
            str_field = str_field.lower()
            search_value = search_value.lower()

        # For substring match (default behavior)
        return search_value in str_field

    def _numeric_compare(
        self,
        *,
        field_value: object,
        compare_value: str,
        operator: str,
    ) -> bool:
        """Perform a numeric comparison.

        Args:
            field_value: The value from the entry field.
            compare_value: The value to compare against (as string).
            operator: The comparison operator (gt, gte, lt, lte, ne).

        Returns:
            True if the comparison succeeds.
        """
        try:
            field_num = float(field_value)  # type: ignore[arg-type]
            compare_num = float(compare_value)
        except (ValueError, TypeError):
            # If conversion fails, fall back to string compare
            str_field = str(field_value)
            if operator == "ne":
                return str_field != compare_value
            return False

        if operator == "gt":
            return field_num > compare_num
        if operator == "gte":
            return field_num >= compare_num
        if operator == "lt":
            return field_num < compare_num
        if operator == "lte":
            return field_num <= compare_num
        if operator == "ne":
            return field_num != compare_num

        return False


def create_filter_state(
    *, query: str, enabled_levels: set[LogLevel] | None = None
) -> FilterState:
    """Create a FilterState from a query string.

    Args:
        query: The query string to parse.
        enabled_levels: Set of enabled log levels.

    Returns:
        FilterState with parsed filters.
    """
    # Import here to avoid circular import at module load time
    from json_logs_viewer.models import FilterState

    engine = FilterEngine()
    predicates = engine.compile_query(query=query) if query.strip() else []

    if enabled_levels is None:
        enabled_levels = set(LogLevel)

    return FilterState(
        raw_query=query,
        parsed_filters=predicates,
        enabled_levels=enabled_levels,
        case_sensitive=False,
    )
