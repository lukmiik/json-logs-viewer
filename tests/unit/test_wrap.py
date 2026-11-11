"""The fast wrap path must match Rich's word wrapping exactly."""

from __future__ import annotations

import random

import pytest
from rich.console import Console
from rich.text import Text

from json_logs_viewer.widgets.log_list import _fast_wrap, _wrap_text

_console = Console()


def _rich_wrap(*, text: str, width: int) -> list[str]:
    return [line.plain for line in Text(text).wrap(_console, width=width)]


def test_matches_rich_on_random_inputs() -> None:
    """Differential fuzzing: every fast-path result equals Rich's."""
    rng = random.Random(1234)
    spaced = 'abcdefghij{}":,[]_-.0123456789     \t'
    compact = 'abcdefghij{}":,[]_-.0123456789'
    fast_cases = 0
    for i in range(20_000):
        alphabet = spaced if i % 2 else compact
        text = "".join(
            rng.choice(alphabet) for _ in range(rng.randint(0, 150))
        )
        width = rng.randint(1, 80)
        fast = _fast_wrap(text=text, width=width)
        if fast is None:
            continue
        fast_cases += 1
        assert fast == _rich_wrap(text=text, width=width), (text, width)
    assert fast_cases > 1_000  # the guard must not reject everything


@pytest.mark.parametrize(
    "text",
    [
        '{"level": "INFO", "message": "a b c"}',
        '{"compact":"json","no":"spaces"}',
        "",
    ],
)
def test_typical_json_takes_fast_path(text: str) -> None:
    assert _fast_wrap(text=text, width=12) == _rich_wrap(text=text, width=12)


@pytest.mark.parametrize(
    "text",
    [
        '{"msg": "two  spaces"}',
        '{"msg": "tab\there"}',
        ' {"leading": "space"}',
        '{"trailing": "space"} ',
        '{"token": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}',
        '{"msg": "café"}',
        '{"msg": "宽字符"}',
    ],
)
def test_unusual_text_falls_back_to_rich(text: str) -> None:
    assert _fast_wrap(text=text, width=12) is None
    assert _wrap_text(text=text, width=12) == _rich_wrap(text=text, width=12)
