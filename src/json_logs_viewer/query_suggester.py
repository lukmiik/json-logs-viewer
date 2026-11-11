"""Inline completion for the search bar.

The search bar shows the rest of a suggestion in grey after the cursor;
the right arrow accepts it. Suggestions, first match wins:

1. a past query (newest first) that continues what was typed;
2. for the term being typed: a keyword when it starts with a capital
   letter (AND, OR, NOT), the values seen in a field after `field:`, or a
   field name (most common first).

A suggestion always starts with exactly what was typed (Textual draws only
the part after it), so matching ignores case but keeps the user's text.
"""

from __future__ import annotations

from collections.abc import Callable

from textual.suggester import Suggester

_KEYWORDS = ("AND", "OR", "NOT")


def _current_term_start(value: str) -> int | None:
    """Where the term being typed starts, or None inside a free phrase.

    Terms are separated by unquoted spaces and parentheses.
    """
    start = 0
    in_quote = False
    for index, char in enumerate(value):
        if char == '"':
            in_quote = not in_quote
        elif not in_quote and (char.isspace() or char in "()"):
            start = index + 1
    if in_quote and value[start : start + 1] == '"':
        return None  # "connection ref…: a full-text phrase, nothing to add
    return start


def _complete(*, typed: str, candidates: list[str]) -> str | None:
    """The rest of the first candidate that continues `typed` (any case)."""
    lowered = typed.lower()
    for candidate in candidates:
        if len(candidate) > len(typed) and candidate.lower().startswith(
            lowered
        ):
            return candidate[len(typed) :]
    return None


def _value_candidates(values: list[str], *, quoted: bool) -> list[str]:
    """Values as they'd be typed: bare, or in quotes when they need them."""
    if quoted:
        return [f'"{value}"' for value in values]
    return [
        value
        for value in values
        if value and not any(c.isspace() or c in '()"' for c in value)
    ]


def suggest(
    *,
    value: str,
    history: list[str],
    fields: list[str],
    values: Callable[[str], list[str]],
) -> str | None:
    """The full suggested query for `value`, or None.

    Args:
        value: What is in the search bar.
        history: Past queries, oldest first.
        fields: Field paths, most common first.
        values: Common values of a field, most common first.
    """
    if not value.strip():
        return None
    rest = _complete(typed=value, candidates=list(reversed(history)))
    if rest is not None:
        return value + rest

    start = _current_term_start(value)
    if start is None:
        return None
    term = value[start:]
    if not term or any(char in "<>" for char in term):
        return None

    if ":" in term:
        field, _, typed = term.partition(":")
        quoted = typed.startswith('"')
        rest = _complete(
            typed=typed,
            candidates=_value_candidates(values(field), quoted=quoted),
        )
    else:
        rest = None
        if term[0].isupper():
            rest = _complete(typed=term, candidates=list(_KEYWORDS))
        if rest is None:
            rest = _complete(
                typed=term, candidates=[f"{field}:" for field in fields]
            )
    return None if rest is None else value + rest


class QuerySuggester(Suggester):
    """Feeds suggest() with the app's live history, fields and values.

    Not cached and case-sensitive on Textual's side: the logs change while
    following, and suggest() matches any case itself so accepting a
    suggestion never changes what was typed.
    """

    def __init__(
        self,
        *,
        history: Callable[[], list[str]],
        fields: Callable[[], list[str]],
        values: Callable[[str], list[str]],
    ) -> None:
        super().__init__(use_cache=False, case_sensitive=True)
        self._history = history
        self._fields = fields
        self._values = values

    async def get_suggestion(self, value: str) -> str | None:
        return suggest(
            value=value,
            history=self._history(),
            fields=self._fields(),
            values=self._values,
        )
