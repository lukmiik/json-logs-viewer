import json
import operator
from datetime import datetime
from functools import cached_property
from typing import Any

from pydantic import BaseModel, TypeAdapter, ValidationError, model_validator

from json_logs_viewer.field_paths import resolve_field

TIMESTAMP_FIELDS = ["Timestamp", "timestamp", "time", "ts", "Time", "@t"]
LEVEL_FIELDS = [
    "SeverityText",
    "severity",
    "level",
    "log_level",
    "Level",
    "loglevel",
    # Nested, checked after the top-level names: OpenTelemetry-style
    # attributes and Elastic Common Schema ("log.level", nested or dotted).
    "attributes.level",
    "attributes.severity",
    "log.level",
]
MESSAGE_FIELDS = ["message", "msg", "Message", "body", "event", "@m"]


_DATETIME = TypeAdapter(datetime)


def _as_datetime(*, value: Any) -> datetime | None:  # noqa: ANN401
    """Parse `value` like Pydantic would, or None if it isn't a datetime."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return _DATETIME.validate_python(value)
    except ValidationError:
        return None


def _as_text(*, value: Any) -> str | None:  # noqa: ANN401
    """Text for a scalar (`30` -> "30"); None for objects, lists, booleans."""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return None


class LogEntry(BaseModel):
    """Represents a single log entry with automatic field normalization."""

    line_number: int
    data: dict[str, Any]
    raw_json: str = ""

    timestamp: datetime | None = None
    level: str | None = None
    message: str | None = None

    @model_validator(mode="before")
    @classmethod
    def extract_normalized_fields(cls, data: Any) -> dict[str, Any]:  # noqa: ANN401
        if not isinstance(data, dict):
            return data

        log_data = data.get("data")
        if not isinstance(log_data, dict):
            return data

        # These fields are conveniences detected from any logger's format, so
        # a value of an unexpected type becomes None (or text) instead of
        # rejecting the whole entry: one `"level": 30` line used to make
        # the entire file fail to load.
        return {
            **data,
            "timestamp": _as_datetime(
                value=cls._find_first(
                    data=log_data, candidates=TIMESTAMP_FIELDS
                )
            ),
            "level": _as_text(
                value=cls._find_first(data=log_data, candidates=LEVEL_FIELDS)
            ),
            "message": _as_text(
                value=cls._find_first(data=log_data, candidates=MESSAGE_FIELDS)
            ),
        }

    @staticmethod
    def _find_first(
        *, data: dict[str, Any], candidates: list[str]
    ) -> Any | None:  # noqa: ANN401
        for candidate in candidates:
            if candidate in data:
                return data[candidate]
            if "." in candidate:
                # Nested path: first value it reaches, like a field query.
                found = next(resolve_field(value=data, path=candidate), None)
                if found is not None:
                    return found
        return None

    @cached_property
    def search_text(self) -> str:
        r"""Text that full-text search looks in: the line as shown.

        A line with backslashes may hold \u escapes (non-ASCII text in many
        loggers), so it is re-encoded with the characters themselves and
        "łódź" finds "\u0142\u00f3d\u017a". That costs a json.dumps,
        so it is computed once per entry and cached.
        """
        if self.raw_json and "\\" not in self.raw_json:
            return self.raw_json
        return json.dumps(self.data, ensure_ascii=False)


def appended_entries(
    *, old: list[LogEntry], new: list[LogEntry]
) -> list[LogEntry] | None:
    """Return the entries `new` adds after `old`, or None.

    None means `new` is not `old` plus more entries at the end (a reload, a
    filter change), so callers must recompute from scratch. Follow mode
    appends, and this lets them process only the new tail.

    Compares by identity: a reloaded file has equal but new entries, which
    must not count as the same ones, and Pydantic's == would compare every
    field (about 40x slower).
    """
    if not old or len(new) < len(old):
        return None
    if not all(map(operator.is_, old, new)):
        return None
    return new[len(old) :]


def parse_log_line(*, line: str, line_number: int) -> LogEntry | None:
    """Parse one JSONL line, or None if it isn't a JSON object.

    Invalid JSON and valid JSON that isn't an object (`[1, 2]`, `"text"`)
    are both skipped by the callers, so one odd line never stops a file
    from loading.
    """
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return LogEntry(line_number=line_number, data=data, raw_json=line)


_LEVEL_NAMES = {
    "error": (
        "error",
        "err",
        "fatal",
        "critical",
        "crit",
        "panic",
        "alert",
        "emerg",
        "emergency",
        "severe",
        # pino's numeric levels (50 error, 60 fatal)
        "50",
        "60",
    ),
    "warning": ("warn", "warning", "40"),
    "debug": (
        "debug",
        "trace",
        "verbose",
        "fine",
        "finer",
        "finest",
        "10",
        "20",
    ),
}
_LEVEL_CATEGORY = {
    name: category
    for category, names in _LEVEL_NAMES.items()
    for name in names
}


def level_category(*, level: str | None) -> str | None:
    """Map a logger's level name to "error", "warning", "debug" or None.

    None means "show normally" (info, notice, unknown names). Matching
    ignores case and surrounding spaces; numbers are pino's levels.
    """
    if level is None:
        return None
    return _LEVEL_CATEGORY.get(level.strip().lower())
