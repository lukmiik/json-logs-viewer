from datetime import datetime
from typing import Any

from pydantic import BaseModel, model_validator

TIMESTAMP_FIELDS = ["Timestamp", "timestamp", "time", "ts", "Time", "@t"]
LEVEL_FIELDS = [
    "SeverityText",
    "severity",
    "level",
    "log_level",
    "Level",
    "loglevel",
]
MESSAGE_FIELDS = ["message", "msg", "Message", "body", "event", "@m"]


class LogEntry(BaseModel):
    """Represents a single log entry with automatic field normalization."""

    line_number: int
    data: dict[str, Any]

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

        return {
            **data,
            "timestamp": cls._find_first(
                data=log_data, candidates=TIMESTAMP_FIELDS
            ),
            "level": cls._find_first(data=log_data, candidates=LEVEL_FIELDS),
            "message": cls._find_first(
                data=log_data, candidates=MESSAGE_FIELDS
            ),
        }

    @staticmethod
    def _find_first(
        *, data: dict[str, Any], candidates: list[str]
    ) -> Any | None:  # noqa: ANN401
        for candidate in candidates:
            if candidate in data:
                return data[candidate]
        return None
