from __future__ import annotations

import math
import operator
import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum, auto
from functools import cached_property
from typing import Any

from .field_paths import resolve_field
from .models import LogEntry


class FilterError(Exception):
    """Raised for invalid filter query syntax."""

    pass


class TokenType(Enum):
    FIELD = auto()
    VALUE = auto()
    QUOTED = auto()
    AND = auto()
    OR = auto()
    NOT = auto()
    LPAREN = auto()
    RPAREN = auto()
    OP = auto()
    EOF = auto()


@dataclass
class Token:
    type: TokenType
    value: str
    position: int


class Tokenizer:
    KEYWORDS = {"AND", "OR", "NOT"}

    def __init__(self, query: str) -> None:
        self.query = query
        self.pos = 0
        self.tokens: list[Token] = []

    def tokenize(self) -> list[Token]:
        while self.pos < len(self.query):
            self._skip_whitespace()
            if self.pos >= len(self.query):
                break

            char = self.query[self.pos]

            if char == "(":
                self.tokens.append(Token(TokenType.LPAREN, "(", self.pos))
                self.pos += 1
            elif char == ")":
                self.tokens.append(Token(TokenType.RPAREN, ")", self.pos))
                self.pos += 1
            elif char == '"':
                self._read_quoted()
            elif char.isalnum() or char in ("-", "_", "."):
                self._read_word_or_field()
            else:
                self.pos += 1

        self.tokens.append(Token(TokenType.EOF, "", self.pos))
        return self.tokens

    def _skip_whitespace(self) -> None:
        while self.pos < len(self.query) and self.query[self.pos].isspace():
            self.pos += 1

    def _read_quoted(self) -> None:
        start = self.pos
        self.pos += 1
        while self.pos < len(self.query) and self.query[self.pos] != '"':
            self.pos += 1
        value = self.query[start + 1 : self.pos]
        if self.pos < len(self.query):
            self.pos += 1  # the closing quote; an unclosed one runs to the end
        self.tokens.append(Token(TokenType.QUOTED, value, start))

    def _read_word_or_field(self) -> None:
        start = self.pos
        while self.pos < len(self.query) and self._is_word_char(
            self.query[self.pos]
        ):
            self.pos += 1
        value = self.query[start : self.pos]

        if self.pos < len(self.query) and self.query[self.pos] == ":":
            self.tokens.append(Token(TokenType.FIELD, value, start))
            self.pos += 1
            self._read_value_after_colon()
        elif value.upper() not in self.KEYWORDS and (
            found := self._operator_at(self.pos)
        ):
            # "code>=500" or "code >= 500": a comparison.
            op, end = found
            self.tokens.append(Token(TokenType.FIELD, value, start))
            self.tokens.append(Token(TokenType.OP, op, end - len(op)))
            self.pos = end
            self._read_value_after_operator()
        elif value.upper() in self.KEYWORDS:
            keyword_type = TokenType[value.upper()]
            self.tokens.append(Token(keyword_type, value.upper(), start))
        else:
            self.tokens.append(Token(TokenType.VALUE, value, start))

    _OPERATORS = (">=", "<=", ">", "<")

    def _operator_at(self, pos: int) -> tuple[str, int] | None:
        """The comparison operator at `pos` (after spaces) and its end."""
        while pos < len(self.query) and self.query[pos].isspace():
            pos += 1
        for op in self._OPERATORS:
            if self.query.startswith(op, pos):
                return op, pos + len(op)
        return None

    def _read_value_after_operator(self) -> None:
        self._skip_whitespace()
        if self.pos >= len(self.query):
            return
        if self.query[self.pos] == '"':
            self._read_quoted()
            return
        start = self.pos
        while (
            self.pos < len(self.query)
            and not self.query[self.pos].isspace()
            and self.query[self.pos] not in ("(", ")")
        ):
            self.pos += 1
        self.tokens.append(
            Token(TokenType.VALUE, self.query[start : self.pos], start)
        )

    @staticmethod
    def _is_word_char(char: str) -> bool:
        return char.isalnum() or char in ("-", "_", ".", "@")

    def _next_starts_term(self) -> bool:
        """Whether the word at `pos` is a keyword or a `field:`."""
        end = self.pos
        while end < len(self.query) and self._is_word_char(self.query[end]):
            end += 1
        word = self.query[self.pos : end]
        if not word:
            return False
        if end < len(self.query) and self.query[end] == ":":
            return True
        if word.upper() not in self.KEYWORDS and self._operator_at(end):
            return True
        return word.upper() in self.KEYWORDS

    def _read_value_after_colon(self) -> None:
        after_colon = self.pos
        self._skip_whitespace()
        if self.pos >= len(self.query):
            return
        if self.pos > after_colon and self._next_starts_term():
            # "level: AND x" or "level: service:api": the space ended an
            # existence check; the next word is a term, not the value.
            return

        if self.query[self.pos] == '"':
            self._read_quoted()
        else:
            start = self.pos
            while (
                self.pos < len(self.query)
                and not self.query[self.pos].isspace()
                and self.query[self.pos] not in ("(", ")")
            ):
                self.pos += 1
            value = self.query[start : self.pos]
            if value:
                self.tokens.append(Token(TokenType.VALUE, value, start))


class ASTNode(ABC):
    @abstractmethod
    def match(self, log_entry: LogEntry, case_sensitive: bool) -> bool:
        pass


@dataclass
class FieldMatch(ASTNode):
    field: str
    value: str

    def match(self, log_entry: LogEntry, case_sensitive: bool) -> bool:
        if "." not in self.field:
            # Fast path, the common case: a plain lookup. Matching runs once
            # per log on every filter change, so avoiding resolve_field's
            # generator here keeps top-level fields as fast as before.
            value = log_entry.data.get(self.field)
            if value is None:
                return False
            if case_sensitive:
                return self.value in str(value)
            return self.value.lower() in str(value).lower()
        return any(
            self._contains(value=value, case_sensitive=case_sensitive)
            for value in resolve_field(value=log_entry.data, path=self.field)
            if value is not None
        )

    def _contains(self, *, value: Any, case_sensitive: bool) -> bool:  # noqa: ANN401
        pattern = self.value if case_sensitive else self.value.lower()
        text = str(value) if case_sensitive else str(value).lower()
        return pattern in text


@dataclass
class FieldExists(ASTNode):
    field: str

    def match(self, log_entry: LogEntry, case_sensitive: bool) -> bool:
        if "." not in self.field:
            return self.field in log_entry.data
        return any(
            True for _ in resolve_field(value=log_entry.data, path=self.field)
        )


@dataclass
class FullText(ASTNode):
    value: str

    def __post_init__(self) -> None:
        # Lowered once per query, not once per log entry.
        self._lowered = self.value.lower()

    def match(self, log_entry: LogEntry, case_sensitive: bool) -> bool:
        if case_sensitive:
            return self.value in log_entry.search_text
        return self._lowered in log_entry.search_text.lower()


def _chain(node: ASTNode, kind: type[ASTNode]) -> list[ASTNode]:
    """The operands of a left-deep chain of `kind`, left to right.

    "a b c" parses to And(And(a, b), c). Walking that chain recursively
    hit Python's recursion limit around 1000 terms (RecursionError); this
    collects the operands in a loop instead.
    """
    rights: list[ASTNode] = []
    while isinstance(node, kind):
        rights.append(node.right)  # type: ignore[attr-defined]
        node = node.left  # type: ignore[attr-defined]
    return [node, *reversed(rights)]


@dataclass
class And(ASTNode):
    left: ASTNode
    right: ASTNode

    @cached_property
    def _operands(self) -> tuple[ASTNode, ...]:
        # Once per query, not per log: matching runs for every entry.
        return tuple(_chain(self, And))

    def match(self, log_entry: LogEntry, case_sensitive: bool) -> bool:
        for operand in self._operands:
            if not operand.match(log_entry, case_sensitive):
                return False
        return True


@dataclass
class Or(ASTNode):
    left: ASTNode
    right: ASTNode

    @cached_property
    def _operands(self) -> tuple[ASTNode, ...]:
        return tuple(_chain(self, Or))

    def match(self, log_entry: LogEntry, case_sensitive: bool) -> bool:
        for operand in self._operands:
            if operand.match(log_entry, case_sensitive):
                return True
        return False


@dataclass
class Not(ASTNode):
    child: ASTNode

    def match(self, log_entry: LogEntry, case_sensitive: bool) -> bool:
        return not self.child.match(log_entry, case_sensitive)


@dataclass
class Group(ASTNode):
    child: ASTNode

    def match(self, log_entry: LogEntry, case_sensitive: bool) -> bool:
        return self.child.match(log_entry, case_sensitive)


def as_utc(moment: datetime) -> datetime:
    """A timezone-aware datetime; a naive one is taken as UTC."""
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def parse_moment(value: Any) -> datetime | None:  # noqa: ANN401
    """A log value as a datetime: ISO 8601 text or epoch seconds/ms.

    Naive times are UTC. Anything else gives None (never matches).
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        # Above 1e11 seconds is year 5138: it must be milliseconds.
        seconds = value / 1000 if abs(value) > 1e11 else value
        try:
            return datetime.fromtimestamp(seconds, UTC)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        try:
            return as_utc(datetime.fromisoformat(value.strip()))
        except ValueError:
            return None
    return None


def _as_number(value: Any) -> float | None:  # noqa: ANN401
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            number = float(value)
        except ValueError:
            return None
        return number if math.isfinite(number) else None
    return None


_COMPARISONS: dict[str, Callable[[Any, Any], bool]] = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
}


@dataclass
class Compare(ASTNode):
    """A comparison such as code>=500 or ts<2024-01-16.

    Compares as numbers, or as times if the value is an ISO date/time; any
    other value is a FilterError.
    """

    field: str
    op: str
    value: str
    _number: float | None = field(init=False, repr=False, compare=False)
    _moment: datetime | None = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._compare = _COMPARISONS[self.op]
        self._number = _as_number(self.value)
        self._moment = None
        if self._number is None:
            self._moment = parse_moment(self.value)
            if self._moment is None:
                raise FilterError(
                    f"{self.field}{self.op}{self.value}: compare with a "
                    "number or a date/time like 2024-01-15T10:00"
                )

    def match(self, log_entry: LogEntry, case_sensitive: bool) -> bool:
        data = log_entry.data
        if self.field in data:
            values: Any = (data[self.field],)
        elif "." in self.field:
            values = resolve_field(value=data, path=self.field)
        else:
            return False
        for value in values:
            if self._number is not None:
                number = _as_number(value)
                if number is not None and self._compare(number, self._number):
                    return True
            else:
                moment = parse_moment(value)
                if moment is not None and self._compare(moment, self._moment):
                    return True
        return False


_DURATION = re.compile(r"(\d+)([smhd])")
_UNITS = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}


def _parse_duration(text: str) -> timedelta | None:
    found = _DURATION.fullmatch(text)
    if found is None:
        return None
    try:
        return timedelta(**{_UNITS[found[2]]: int(found[1])})
    except OverflowError:
        # Beyond timedelta's ~2.7 million years: an error, not a crash.
        raise FilterError(f"last:{text}: duration too long") from None


@dataclass
class Last(ASTNode):
    """last:<duration>: logs at most `window` older than the newest one.

    `since` is None when no log has a timestamp; then nothing matches.
    """

    window: timedelta
    since: datetime | None

    def match(self, log_entry: LogEntry, case_sensitive: bool) -> bool:
        timestamp = log_entry.timestamp
        if timestamp is None or self.since is None:
            return False
        return as_utc(timestamp) >= self.since


class Parser:
    def __init__(
        self,
        tokens: list[Token],
        newest_timestamp: Callable[[], datetime | None] | None = None,
    ) -> None:
        self.tokens = tokens
        self.pos = 0
        # last:<duration> needs the newest log's timestamp; it's looked up
        # only if the query uses it (it scans every log).
        self._newest_timestamp = newest_timestamp
        self._newest: datetime | None = None
        self._newest_resolved = False
        self.relative = False

    def parse(self) -> ASTNode:
        node = self._expr()
        if self._current().type != TokenType.EOF:
            raise FilterError(f"Unexpected token: {self._current().value}")
        return node

    def _current(self) -> Token:
        return self.tokens[self.pos]

    def _advance(self) -> Token:
        token = self.tokens[self.pos]
        self.pos += 1
        return token

    def _expect(self, token_type: TokenType) -> Token:
        if self._current().type != token_type:
            raise FilterError(
                f"Expected {token_type.name}, got {self._current().type.name}"
            )
        return self._advance()

    def _expr(self) -> ASTNode:
        node = self._term()
        while self._current().type == TokenType.OR:
            self._advance()
            right = self._term()
            node = Or(left=node, right=right)
        return node

    # Tokens that can begin a term. If one follows a term directly, the
    # two are joined by an implicit AND ("level:error service:api").
    _TERM_START = frozenset(
        {
            TokenType.FIELD,
            TokenType.VALUE,
            TokenType.QUOTED,
            TokenType.NOT,
            TokenType.LPAREN,
        }
    )

    def _term(self) -> ASTNode:
        """Parse terms joined by explicit or implicit AND.

        Implicit AND lives here, at the same precedence as AND, so
        "a OR b c" means "a OR (b AND c)".
        """
        node = self._factor()
        while True:
            if self._current().type == TokenType.AND:
                self._advance()
            elif self._current().type not in self._TERM_START:
                break
            right = self._factor()
            node = And(left=node, right=right)
        return node

    def _factor(self) -> ASTNode:
        if self._current().type == TokenType.NOT:
            self._advance()
            child = self._factor()
            return Not(child=child)
        return self._primary()

    def _primary(self) -> ASTNode:
        token = self._current()

        if token.type == TokenType.LPAREN:
            self._advance()
            node = self._expr()
            self._expect(TokenType.RPAREN)
            return Group(child=node)

        if token.type == TokenType.FIELD:
            return self._field_match()

        if token.type == TokenType.VALUE or token.type == TokenType.QUOTED:
            return self._fulltext()

        raise FilterError(f"Unexpected token: {token.value}")

    def _field_match(self) -> ASTNode:
        field_token = self._expect(TokenType.FIELD)
        field = field_token.value

        if self._current().type == TokenType.OP:
            op = self._advance().value
            if self._current().type not in (TokenType.VALUE, TokenType.QUOTED):
                raise FilterError(f"Expected a value after {op}")
            return Compare(field=field, op=op, value=self._advance().value)

        if self._current().type in (TokenType.VALUE, TokenType.QUOTED):
            value_token = self._advance()
            value = value_token.value
            if field == "last" and (window := _parse_duration(value)):
                return self._last(window=window)
            return FieldMatch(field=field, value=value)

        return FieldExists(field=field)

    def _last(self, *, window: timedelta) -> Last:
        """last:<duration>, anchored at the newest log's timestamp."""
        self.relative = True
        if not self._newest_resolved:
            self._newest_resolved = True
            if self._newest_timestamp is not None:
                self._newest = self._newest_timestamp()
        since = None
        if self._newest is not None:
            try:
                since = as_utc(self._newest) - window
            except OverflowError:
                # Reaches before year 1: every log is in the window.
                since = datetime.min.replace(tzinfo=UTC)
        return Last(window=window, since=since)

    def _fulltext(self) -> ASTNode:
        # One word or one quoted phrase. Adjacent words become separate
        # terms joined by implicit AND in _term; quote them for a phrase.
        return FullText(value=self._advance().value)


class Matcher:
    """A parsed query: call it with a log entry to test it.

    `relative` is True when the query uses last:<duration>, whose window
    moves as newer logs arrive, so callers must re-filter everything
    instead of only new logs.
    """

    def __init__(
        self, *, ast: ASTNode | None, case_sensitive: bool, relative: bool
    ) -> None:
        self._ast = ast
        self._case_sensitive = case_sensitive
        self.relative = relative

    def __call__(self, log_entry: LogEntry) -> bool:
        if self._ast is None:
            return True
        return self._ast.match(log_entry, self._case_sensitive)


def parse_filter(
    *,
    query: str,
    case_sensitive: bool = False,
    newest_timestamp: Callable[[], datetime | None] | None = None,
) -> Matcher:
    """Parse `query`; raises FilterError for invalid syntax.

    Args:
        newest_timestamp: Returns the newest log timestamp, the anchor of
            last:<duration>. Only called if the query uses it.
    """
    if not query or not query.strip():
        return Matcher(ast=None, case_sensitive=case_sensitive, relative=False)

    tokens = Tokenizer(query).tokenize()
    parser = Parser(tokens, newest_timestamp)
    try:
        ast = parser.parse()
    except RecursionError:
        # Thousands of nested NOTs or parentheses: the recursive-descent
        # parser runs out of stack. Long flat queries are fine.
        raise FilterError("Query is too deeply nested") from None
    return Matcher(
        ast=ast, case_sensitive=case_sensitive, relative=parser.relative
    )
