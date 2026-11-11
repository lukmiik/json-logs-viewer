"""Dotted field paths: listing them and reading values through them."""

from __future__ import annotations

from typing import Any

import pytest

from json_logs_viewer.field_paths import leaf_paths
from json_logs_viewer.widgets.log_list import column_text


def test_leaf_paths_descend_into_objects() -> None:
    data = {
        "message": "hi",
        "attributes": {"level": "error", "http": {"status": 502}},
        "tags": ["a", "b"],
        "empty": {},
    }
    assert list(leaf_paths(value=data)) == [
        "message",
        "attributes.level",
        "attributes.http.status",
        "tags",
        "empty",
    ]


@pytest.mark.parametrize(
    ("data", "column", "text"),
    [
        ({"level": "INFO"}, "level", "INFO"),
        ({"a": {"b": 504}}, "a.b", "504"),
        ({"service.name": "api"}, "service.name", "api"),
        ({"a": {"b": None}}, "a.b", "null"),
        ({"ok": True}, "ok", "true"),
        ({"tags": ["x", "y"]}, "tags", '["x", "y"]'),
        ({"msg": "Zażółć"}, "msg", "Zażółć"),
        ({"level": "INFO"}, "missing", ""),
        ({"a": "not an object"}, "a.b", ""),
    ],
)
def test_column_text(data: dict[str, Any], column: str, text: str) -> None:
    assert column_text(data=data, column=column) == text
