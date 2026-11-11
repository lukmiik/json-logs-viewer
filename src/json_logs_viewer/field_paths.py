from __future__ import annotations

from collections.abc import Iterator
from typing import Any


def resolve_field(*, value: Any, path: str) -> Iterator[Any]:  # noqa: ANN401
    """Yield every value a dotted field path can reach inside `value`.

    "a.b.c" can mean nested keys or keys that contain dots ("service.name"
    in OpenTelemetry), so every reading is tried: the whole rest of the path
    as one key, then each split point. A list applies the path to each
    element. Callers match if any yielded value matches.
    """
    if isinstance(value, list):
        for item in value:
            yield from resolve_field(value=item, path=path)
        return
    if not isinstance(value, dict):
        return
    if path in value:
        yield value[path]
    dot = path.find(".")
    while dot != -1:
        head = path[:dot]
        if head in value:
            yield from resolve_field(value=value[head], path=path[dot + 1 :])
        dot = path.find(".", dot + 1)


def leaf_paths(*, value: dict[str, Any], prefix: str = "") -> Iterator[str]:
    """Yield the dotted path of every value inside a JSON object.

    Objects are descended into ({"a": {"b": 1}} gives "a.b"); lists, empty
    objects and scalars are values. These are the paths offered as columns.
    """
    for key, item in value.items():
        path = f"{prefix}{key}"
        if isinstance(item, dict) and item:
            yield from leaf_paths(value=item, prefix=f"{path}.")
        else:
            yield path
