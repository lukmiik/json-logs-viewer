"""Unit tests for filter engine."""

import json

import pytest

from json_logs_viewer.filter_engine import (
    And,
    FieldExists,
    FieldMatch,
    FilterError,
    FullText,
    Group,
    Not,
    Or,
    Parser,
    Token,
    Tokenizer,
    TokenType,
    parse_filter,
)
from json_logs_viewer.models import LogEntry


def make_log(*, line_number: int = 1, **data: object) -> LogEntry:
    """Helper to create a LogEntry with given data."""
    return LogEntry(line_number=line_number, data=data)


class TestTokenizer:
    """Tests for the Tokenizer class."""

    def test_tokenize_field_value(self) -> None:
        """Test tokenizing field:value pattern."""
        tokenizer = Tokenizer("level:ERROR")
        tokens = tokenizer.tokenize()

        assert tokens[0].type == TokenType.FIELD
        assert tokens[0].value == "level"
        assert tokens[1].type == TokenType.VALUE
        assert tokens[1].value == "ERROR"
        assert tokens[2].type == TokenType.EOF

    def test_tokenize_quoted_value(self) -> None:
        """Test tokenizing quoted values."""
        tokenizer = Tokenizer('message:"hello world"')
        tokens = tokenizer.tokenize()

        assert tokens[0].type == TokenType.FIELD
        assert tokens[0].value == "message"
        assert tokens[1].type == TokenType.QUOTED
        assert tokens[1].value == "hello world"

    def test_tokenize_and_keyword(self) -> None:
        """Test tokenizing AND keyword."""
        tokenizer = Tokenizer("level:ERROR AND service:api")
        tokens = tokenizer.tokenize()

        field_tokens = [t for t in tokens if t.type == TokenType.FIELD]
        assert len(field_tokens) == 2
        and_tokens = [t for t in tokens if t.type == TokenType.AND]
        assert len(and_tokens) == 1

    def test_tokenize_or_keyword(self) -> None:
        """Test tokenizing OR keyword."""
        tokenizer = Tokenizer("level:ERROR OR level:WARN")
        tokens = tokenizer.tokenize()

        or_tokens = [t for t in tokens if t.type == TokenType.OR]
        assert len(or_tokens) == 1

    def test_tokenize_not_keyword(self) -> None:
        """Test tokenizing NOT keyword."""
        tokenizer = Tokenizer("NOT level:DEBUG")
        tokens = tokenizer.tokenize()

        not_tokens = [t for t in tokens if t.type == TokenType.NOT]
        assert len(not_tokens) == 1

    def test_tokenize_parentheses(self) -> None:
        """Test tokenizing parentheses."""
        tokenizer = Tokenizer("(level:ERROR OR level:WARN)")
        tokens = tokenizer.tokenize()

        lparen = [t for t in tokens if t.type == TokenType.LPAREN]
        rparen = [t for t in tokens if t.type == TokenType.RPAREN]
        assert len(lparen) == 1
        assert len(rparen) == 1

    def test_tokenize_fulltext_value(self) -> None:
        """Test tokenizing plain text values (full-text search)."""
        tokenizer = Tokenizer("error timeout")
        tokens = tokenizer.tokenize()

        value_tokens = [t for t in tokens if t.type == TokenType.VALUE]
        assert len(value_tokens) == 2
        assert value_tokens[0].value == "error"
        assert value_tokens[1].value == "timeout"

    def test_tokenize_field_without_value(self) -> None:
        """Test tokenizing field: without value (field exists check)."""
        tokenizer = Tokenizer("user:")
        tokens = tokenizer.tokenize()

        assert tokens[0].type == TokenType.FIELD
        assert tokens[0].value == "user"
        assert tokens[1].type == TokenType.EOF

    def test_tokenize_hyphenated_field_name(self) -> None:
        """Test tokenizing field names with hyphens."""
        tokenizer = Tokenizer("content-type:json")
        tokens = tokenizer.tokenize()

        assert tokens[0].type == TokenType.FIELD
        assert tokens[0].value == "content-type"

    def test_tokenize_empty_query(self) -> None:
        """Test tokenizing empty query."""
        tokenizer = Tokenizer("")
        tokens = tokenizer.tokenize()

        assert len(tokens) == 1
        assert tokens[0].type == TokenType.EOF


class TestParser:
    """Tests for the Parser class."""

    def test_parse_field_match(self) -> None:
        """Test parsing simple field:value."""
        tokens = Tokenizer("level:ERROR").tokenize()
        parser = Parser(tokens)
        ast = parser.parse()

        assert isinstance(ast, FieldMatch)
        assert ast.field == "level"
        assert ast.value == "ERROR"

    def test_parse_field_exists(self) -> None:
        """Test parsing field: without value."""
        tokens = Tokenizer("user:").tokenize()
        parser = Parser(tokens)
        ast = parser.parse()

        assert isinstance(ast, FieldExists)
        assert ast.field == "user"

    def test_parse_and(self) -> None:
        """Test parsing AND expression."""
        tokens = Tokenizer("level:ERROR AND service:api").tokenize()
        parser = Parser(tokens)
        ast = parser.parse()

        assert isinstance(ast, And)
        assert isinstance(ast.left, FieldMatch)
        assert isinstance(ast.right, FieldMatch)

    def test_parse_or(self) -> None:
        """Test parsing OR expression."""
        tokens = Tokenizer("level:ERROR OR level:WARN").tokenize()
        parser = Parser(tokens)
        ast = parser.parse()

        assert isinstance(ast, Or)
        assert isinstance(ast.left, FieldMatch)
        assert isinstance(ast.right, FieldMatch)

    def test_parse_not(self) -> None:
        """Test parsing NOT expression."""
        tokens = Tokenizer("NOT level:DEBUG").tokenize()
        parser = Parser(tokens)
        ast = parser.parse()

        assert isinstance(ast, Not)
        assert isinstance(ast.child, FieldMatch)

    def test_parse_grouped_expression(self) -> None:
        """Test parsing grouped expression with parentheses."""
        tokens = Tokenizer(
            "(level:ERROR OR level:WARN) AND service:api"
        ).tokenize()
        parser = Parser(tokens)
        ast = parser.parse()

        assert isinstance(ast, And)
        assert isinstance(ast.left, Group)
        assert isinstance(ast.left.child, Or)

    def test_parse_fulltext(self) -> None:
        """Bare words are separate full-text terms joined by implicit AND."""
        tokens = Tokenizer("error timeout").tokenize()
        parser = Parser(tokens)
        ast = parser.parse()

        assert ast == And(
            left=FullText(value="error"), right=FullText(value="timeout")
        )

    def test_parse_quoted_phrase(self) -> None:
        """Quotes keep words together as one phrase."""
        tokens = Tokenizer('"error timeout"').tokenize()

        assert Parser(tokens).parse() == FullText(value="error timeout")

    def test_parse_error_unexpected_token(self) -> None:
        """Test parser error on unexpected token."""
        tokens = [Token(TokenType.LPAREN, "(", 0), Token(TokenType.EOF, "", 1)]
        parser = Parser(tokens)

        with pytest.raises(FilterError):
            parser.parse()


class TestFieldMatch:
    """Tests for FieldMatch AST node."""

    def test_match_exact(self) -> None:
        """Test matching exact field value."""
        log = make_log(level="ERROR")
        node = FieldMatch(field="level", value="ERROR")

        assert node.match(log, case_sensitive=False) is True

    def test_match_substring(self) -> None:
        """Test matching substring in field value."""
        log = make_log(message="Error occurred in module")
        node = FieldMatch(field="message", value="Error")

        assert node.match(log, case_sensitive=False) is True

    def test_match_case_insensitive(self) -> None:
        """Test case-insensitive matching."""
        log = make_log(level="error")
        node = FieldMatch(field="level", value="ERROR")

        assert node.match(log, case_sensitive=False) is True

    def test_match_case_sensitive(self) -> None:
        """Test case-sensitive matching."""
        log = make_log(level="error")
        node = FieldMatch(field="level", value="ERROR")

        assert node.match(log, case_sensitive=True) is False

    def test_match_missing_field(self) -> None:
        """Test matching when field is missing."""
        log = make_log(level="ERROR")
        node = FieldMatch(field="service", value="api")

        assert node.match(log, case_sensitive=False) is False

    def test_match_numeric_field(self) -> None:
        """Test matching numeric field value (converted to string)."""
        log = make_log(status=200)
        node = FieldMatch(field="status", value="200")

        assert node.match(log, case_sensitive=False) is True


class TestFieldExists:
    """Tests for FieldExists AST node."""

    def test_field_exists(self) -> None:
        """Test when field exists."""
        log = make_log(level="ERROR", message="test")
        node = FieldExists(field="level")

        assert node.match(log, case_sensitive=False) is True

    def test_field_missing(self) -> None:
        """Test when field is missing."""
        log = make_log(message="test")
        node = FieldExists(field="level")

        assert node.match(log, case_sensitive=False) is False


class TestFullText:
    """Tests for FullText AST node."""

    def test_match_in_field_value(self) -> None:
        """Test matching text in any field value."""
        log = make_log(level="ERROR", message="Connection timeout")
        node = FullText(value="timeout")

        assert node.match(log, case_sensitive=False) is True

    def test_match_in_field_name(self) -> None:
        """Test matching text in a field name."""
        log = make_log(level="ERROR")
        node = FullText(value="level")

        assert node.match(log, case_sensitive=False) is True

    def test_match_case_insensitive(self) -> None:
        """Test case-insensitive full-text matching."""
        log = make_log(message="ERROR occurred")
        node = FullText(value="error")

        assert node.match(log, case_sensitive=False) is True

    def test_match_case_sensitive(self) -> None:
        """Test case-sensitive full-text matching."""
        log = make_log(message="error occurred")
        node = FullText(value="ERROR")

        assert node.match(log, case_sensitive=True) is False

    def test_no_match(self) -> None:
        """Test when text not found."""
        log = make_log(level="INFO", message="All good")
        node = FullText(value="ERROR")

        assert node.match(log, case_sensitive=False) is False

    def test_searches_json_as_shown(self) -> None:
        """Null is found as null, not as Python's None."""
        line = '{"user": null, "ok": true}'
        log = LogEntry(line_number=1, data=json.loads(line), raw_json=line)

        assert FullText(value="null").match(log, case_sensitive=True)
        assert FullText(value="true").match(log, case_sensitive=True)
        assert not FullText(value="None").match(log, case_sensitive=False)

    def test_unicode_escapes_are_decoded(self) -> None:
        r"""Text written as \u escapes is found by its characters."""
        line = '{"city": "\\u0141\\u00f3d\\u017a"}'
        log = LogEntry(line_number=1, data=json.loads(line), raw_json=line)

        assert FullText(value="łódź").match(log, case_sensitive=False)
        assert FullText(value="Łódź").match(log, case_sensitive=True)


class TestAnd:
    """Tests for And AST node."""

    def test_both_match(self) -> None:
        """Test when both sides match."""
        log = make_log(level="ERROR", service="api")
        node = And(
            left=FieldMatch(field="level", value="ERROR"),
            right=FieldMatch(field="service", value="api"),
        )

        assert node.match(log, case_sensitive=False) is True

    def test_left_fails(self) -> None:
        """Test when left side fails."""
        log = make_log(level="INFO", service="api")
        node = And(
            left=FieldMatch(field="level", value="ERROR"),
            right=FieldMatch(field="service", value="api"),
        )

        assert node.match(log, case_sensitive=False) is False

    def test_right_fails(self) -> None:
        """Test when right side fails."""
        log = make_log(level="ERROR", service="db")
        node = And(
            left=FieldMatch(field="level", value="ERROR"),
            right=FieldMatch(field="service", value="api"),
        )

        assert node.match(log, case_sensitive=False) is False


class TestOr:
    """Tests for Or AST node."""

    def test_both_match(self) -> None:
        """Test when both sides match."""
        log = make_log(level="ERROR", service="api")
        node = Or(
            left=FieldMatch(field="level", value="ERROR"),
            right=FieldMatch(field="service", value="api"),
        )

        assert node.match(log, case_sensitive=False) is True

    def test_left_matches(self) -> None:
        """Test when only left side matches."""
        log = make_log(level="ERROR", service="db")
        node = Or(
            left=FieldMatch(field="level", value="ERROR"),
            right=FieldMatch(field="service", value="api"),
        )

        assert node.match(log, case_sensitive=False) is True

    def test_right_matches(self) -> None:
        """Test when only right side matches."""
        log = make_log(level="INFO", service="api")
        node = Or(
            left=FieldMatch(field="level", value="ERROR"),
            right=FieldMatch(field="service", value="api"),
        )

        assert node.match(log, case_sensitive=False) is True

    def test_neither_matches(self) -> None:
        """Test when neither side matches."""
        log = make_log(level="INFO", service="db")
        node = Or(
            left=FieldMatch(field="level", value="ERROR"),
            right=FieldMatch(field="service", value="api"),
        )

        assert node.match(log, case_sensitive=False) is False


class TestNot:
    """Tests for Not AST node."""

    def test_negates_match(self) -> None:
        """Test NOT negates a matching condition."""
        log = make_log(level="DEBUG")
        node = Not(child=FieldMatch(field="level", value="DEBUG"))

        assert node.match(log, case_sensitive=False) is False

    def test_negates_non_match(self) -> None:
        """Test NOT on non-matching condition."""
        log = make_log(level="ERROR")
        node = Not(child=FieldMatch(field="level", value="DEBUG"))

        assert node.match(log, case_sensitive=False) is True


class TestGroup:
    """Tests for Group AST node."""

    def test_group_preserves_child_match(self) -> None:
        """Test Group delegates to child."""
        log = make_log(level="ERROR")
        node = Group(child=FieldMatch(field="level", value="ERROR"))

        assert node.match(log, case_sensitive=False) is True


class TestParseFilter:
    """Tests for parse_filter function."""

    def test_empty_query_matches_all(self) -> None:
        """Test empty query returns matcher that matches everything."""
        matcher = parse_filter(query="", case_sensitive=False)
        log = make_log(level="ERROR")

        assert matcher(log) is True

    def test_whitespace_only_query_matches_all(self) -> None:
        """Test whitespace-only query matches everything."""
        matcher = parse_filter(query="   ", case_sensitive=False)
        log = make_log(level="ERROR")

        assert matcher(log) is True

    def test_simple_field_match(self) -> None:
        """Test simple field:value filter."""
        matcher = parse_filter(query="level:ERROR", case_sensitive=False)

        assert matcher(make_log(level="ERROR")) is True
        assert matcher(make_log(level="INFO")) is False

    def test_complex_expression(self) -> None:
        """Test complex boolean expression."""
        matcher = parse_filter(
            query="(level:ERROR OR level:WARN) AND service:api",
            case_sensitive=False,
        )

        assert matcher(make_log(level="ERROR", service="api")) is True
        assert matcher(make_log(level="WARN", service="api")) is True
        assert matcher(make_log(level="ERROR", service="db")) is False
        assert matcher(make_log(level="INFO", service="api")) is False

    def test_not_expression(self) -> None:
        """Test NOT expression."""
        matcher = parse_filter(query="NOT level:DEBUG", case_sensitive=False)

        assert matcher(make_log(level="ERROR")) is True
        assert matcher(make_log(level="DEBUG")) is False

    def test_fulltext_search(self) -> None:
        """Test full-text search."""
        matcher = parse_filter(query="timeout error", case_sensitive=False)

        assert matcher(make_log(message="Connection timeout error")) is True
        assert matcher(make_log(message="All good")) is False

    def test_case_sensitivity(self) -> None:
        """Test case sensitivity option."""
        matcher_insensitive = parse_filter(
            query="level:error", case_sensitive=False
        )
        matcher_sensitive = parse_filter(
            query="level:error", case_sensitive=True
        )

        log = make_log(level="ERROR")

        assert matcher_insensitive(log) is True
        assert matcher_sensitive(log) is False


class TestImplicitAnd:
    """Adjacent terms without an operator are joined with AND."""

    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            (
                "level:error service:api",
                And(
                    left=FieldMatch(field="level", value="error"),
                    right=FieldMatch(field="service", value="api"),
                ),
            ),
            (
                "error level:warn",
                And(
                    left=FullText(value="error"),
                    right=FieldMatch(field="level", value="warn"),
                ),
            ),
            (
                "NOT debug level:error",
                And(
                    left=Not(child=FullText(value="debug")),
                    right=FieldMatch(field="level", value="error"),
                ),
            ),
            (
                "a OR b c",
                Or(
                    left=FullText(value="a"),
                    right=And(
                        left=FullText(value="b"), right=FullText(value="c")
                    ),
                ),
            ),
            (
                "level: (a OR b)",
                And(
                    left=FieldExists(field="level"),
                    right=Group(
                        child=Or(
                            left=FullText(value="a"),
                            right=FullText(value="b"),
                        )
                    ),
                ),
            ),
        ],
    )
    def test_ast(self, query: str, expected: object) -> None:
        assert Parser(Tokenizer(query).tokenize()).parse() == expected

    def test_readme_example_parses_and_matches(self) -> None:
        """The README example that used to raise "Unexpected token: NOT"."""
        matcher = parse_filter(
            query="level:error AND (service:api OR service:web) NOT debug",
            case_sensitive=False,
        )

        assert matcher(make_log(level="ERROR", service="api")) is True
        assert (
            matcher(make_log(level="ERROR", service="web", message="debug"))
            is False
        )
        assert matcher(make_log(level="ERROR", service="db")) is False

    def test_words_match_in_any_order_and_position(self) -> None:
        matcher = parse_filter(
            query="refused connection", case_sensitive=False
        )

        assert matcher(make_log(message="connection was refused")) is True
        assert matcher(make_log(message="connection ok")) is False

    def test_quoted_phrase_needs_exact_sequence(self) -> None:
        matcher = parse_filter(
            query='"connection refused"', case_sensitive=False
        )

        assert matcher(make_log(message="connection refused")) is True
        assert matcher(make_log(message="connection was refused")) is False

    @pytest.mark.parametrize(
        "query", ["level:error AND", "a OR", "NOT", "( a"]
    )
    def test_dangling_operators_still_error(self, query: str) -> None:
        with pytest.raises(FilterError):
            parse_filter(query=query, case_sensitive=False)


NESTED_LOG = LogEntry(
    line_number=1,
    data={
        "SeverityText": "ERROR",
        "Resource": {"service.name": "checkout"},
        "Attributes": {"http": {"status_code": 502}, "user": {"id": 42}},
        "events": [{"name": "retry", "attempt": 1}, {"name": "give_up"}],
        "user.id": "flat-7",
        "tags": ["prod", "eu"],
    },
)


class TestNestedFields:
    """Dotted field paths reach into nested objects and lists."""

    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            ("Attributes.http.status_code:502", True),
            ("Attributes.http.status_code:404", False),
            ("Attributes.user.id:42", True),
            # A key that itself contains dots (OpenTelemetry style).
            ("Resource.service.name:checkout", True),
            # Lists: any element can match.
            ("events.name:give_up", True),
            ("events.name:missing", False),
            ("events.attempt:1", True),
            # A literal top-level dotted key still works.
            ("user.id:flat-7", True),
            ("tags:eu", True),
            ("Attributes.nope:1", False),
            ("SeverityText.x:ERROR", False),
        ],
    )
    def test_field_match(self, query: str, expected: bool) -> None:
        assert parse_filter(query=query)(NESTED_LOG) is expected

    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            ("Attributes.user:", True),
            ("Attributes.user.id:", True),
            ("Resource.service.name:", True),
            ("events.attempt:", True),
            ("Attributes.user.email:", False),
            ("events.nope:", False),
        ],
    )
    def test_field_exists(self, query: str, expected: bool) -> None:
        assert parse_filter(query=query)(NESTED_LOG) is expected

    def test_combines_with_boolean_logic(self) -> None:
        matcher = parse_filter(
            query="Attributes.http.status_code:5 NOT events.name:retry"
        )

        assert matcher(NESTED_LOG) is False

    def test_case_sensitivity_applies_to_values(self) -> None:
        assert parse_filter(query="Resource.service.name:CHECKOUT")(NESTED_LOG)
        assert not parse_filter(
            query="Resource.service.name:CHECKOUT", case_sensitive=True
        )(NESTED_LOG)
