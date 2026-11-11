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
