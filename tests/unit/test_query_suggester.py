"""Inline completion for the search bar: what gets suggested."""

from __future__ import annotations

import pytest

from json_logs_viewer.query_suggester import suggest

FIELDS = ["attributes.level", "attributes.endpoint", "tags.service", "level"]
VALUES = {
    "attributes.level": ["error", "warning"],
    "tags.service": ["billing-api", "auth api"],
}


def run(value: str, history: list[str] | None = None) -> str | None:
    return suggest(
        value=value,
        history=history or [],
        fields=FIELDS,
        values=lambda field: VALUES.get(field, []),
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("attr", "attributes.level:"),  # most common first
        ("attributes.e", "attributes.endpoint:"),
        ("ATTR", "ATTRibutes.level:"),  # matches any case, keeps yours
        ("tags.service:api attr", "tags.service:api attributes.level:"),
        ("(attr", "(attributes.level:"),
        ("NOT attr", "NOT attributes.level:"),
    ],
)
def test_field_names(value: str, expected: str) -> None:
    assert run(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("attributes.level:", "attributes.level:error"),
        ("attributes.level:w", "attributes.level:warning"),
        ("attributes.level:ER", "attributes.level:ERror"),
        ("tags.service:b", "tags.service:billing-api"),
        # A value with a space can only continue an opened quote.
        ('tags.service:"au', 'tags.service:"auth api"'),
    ],
)
def test_values_of_a_field(value: str, expected: str) -> None:
    assert run(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [("level:error O", "level:error OR"), ("A", "AND"), ("N", "NOT")],
)
def test_keywords(value: str, expected: str) -> None:
    assert run(value) == expected


def test_history_comes_first() -> None:
    history = ["tags.service:billing-api", "attributes.level:warning"]
    # Newest history entry that continues what was typed.
    assert run("attr", history=history) == "attributes.level:warning"
    assert run("tags", history=history) == "tags.service:billing-api"


@pytest.mark.parametrize(
    "value",
    [
        "",  # nothing typed
        "zzz",  # nothing matches
        "attributes.level:error",  # complete already
        "attributes.level:error ",  # a space ends the term
        "attributes.level: ",
        "unknown.field:x",  # no known values
        'msg:"connection ref',  # inside a free-text phrase
        "code>=5",  # comparisons take any value
        "lower o",  # keywords only from a capital letter
        "tags.service:a",  # "auth api" needs the quote typed first
    ],
)
def test_nothing_to_suggest(value: str) -> None:
    assert run(value) is None
