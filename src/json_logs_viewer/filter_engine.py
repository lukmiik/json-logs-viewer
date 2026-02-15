from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto

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
        if self.pos < len(self.query):
            self.pos += 1
        value = self.query[start + 1 : self.pos - 1]
        self.tokens.append(Token(TokenType.QUOTED, value, start))

    def _read_word_or_field(self) -> None:
        start = self.pos
        while self.pos < len(self.query) and (
            self.query[self.pos].isalnum()
            or self.query[self.pos] in ("-", "_", ".", "@")
        ):
            self.pos += 1
        value = self.query[start : self.pos]

        if self.pos < len(self.query) and self.query[self.pos] == ":":
            self.tokens.append(Token(TokenType.FIELD, value, start))
            self.pos += 1
            self._read_value_after_colon()
        elif value.upper() in self.KEYWORDS:
            keyword_type = TokenType[value.upper()]
            self.tokens.append(Token(keyword_type, value.upper(), start))
        else:
            self.tokens.append(Token(TokenType.VALUE, value, start))

    def _read_value_after_colon(self) -> None:
        self._skip_whitespace()
        if self.pos >= len(self.query):
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
        field_value = log_entry.data.get(self.field)
        if field_value is None:
            return False
        field_str = str(field_value)
        pattern = self.value if case_sensitive else self.value.lower()
        text = field_str if case_sensitive else field_str.lower()
        return pattern in text


@dataclass
class FieldExists(ASTNode):
    field: str

    def match(self, log_entry: LogEntry, case_sensitive: bool) -> bool:
        return self.field in log_entry.data


@dataclass
class FullText(ASTNode):
    value: str

    def match(self, log_entry: LogEntry, case_sensitive: bool) -> bool:
        search_text = self.value if case_sensitive else self.value.lower()
        serialized = _serialize_log_entry(log_entry)
        search_target = serialized if case_sensitive else serialized.lower()
        return search_text in search_target


@dataclass
class And(ASTNode):
    left: ASTNode
    right: ASTNode

    def match(self, log_entry: LogEntry, case_sensitive: bool) -> bool:
        return self.left.match(log_entry, case_sensitive) and self.right.match(
            log_entry, case_sensitive
        )


@dataclass
class Or(ASTNode):
    left: ASTNode
    right: ASTNode

    def match(self, log_entry: LogEntry, case_sensitive: bool) -> bool:
        return self.left.match(log_entry, case_sensitive) or self.right.match(
            log_entry, case_sensitive
        )


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


def _serialize_log_entry(log_entry: LogEntry) -> str:
    parts = [f"{k}={v}" for k, v in log_entry.data.items()]
    return " ".join(parts)


class Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.pos = 0

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

    def _term(self) -> ASTNode:
        node = self._factor()
        while self._current().type == TokenType.AND:
            self._advance()
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

        if self._current().type in (TokenType.VALUE, TokenType.QUOTED):
            value_token = self._advance()
            value = value_token.value
            return FieldMatch(field=field, value=value)

        return FieldExists(field=field)

    def _fulltext(self) -> ASTNode:
        token = self._advance()
        value = token.value
        while self._current().type in (TokenType.VALUE, TokenType.QUOTED):
            next_token = self._advance()
            value += " " + next_token.value
        return FullText(value=value)


def parse_filter(
    *,
    query: str,
    case_sensitive: bool = False,
) -> Callable[[LogEntry], bool]:
    if not query or not query.strip():
        return lambda _: True

    tokenizer = Tokenizer(query)
    tokens = tokenizer.tokenize()
    parser = Parser(tokens)
    ast = parser.parse()

    def matcher(log_entry: LogEntry) -> bool:
        return ast.match(log_entry, case_sensitive)

    return matcher
