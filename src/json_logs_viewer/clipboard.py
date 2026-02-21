"""Clipboard operations for log entries."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from json_logs_viewer.models import LogEntry


def format_log_as_json(*, log_entry: LogEntry) -> str:
    """Format a single log entry as pretty-printed JSON.

    Args:
        log_entry: The log entry to format.

    Returns:
        Pretty-printed JSON string.
    """
    return json.dumps(log_entry.data, indent=2, ensure_ascii=False)


def format_logs_as_jsonl(*, log_entries: list[LogEntry]) -> str:
    """Format multiple log entries as JSONL (one JSON per line).

    Args:
        log_entries: The log entries to format.

    Returns:
        JSONL string with one JSON object per line.
    """
    lines = [entry.raw_json for entry in log_entries]
    return "\n".join(lines)


def get_log_with_context(
    *,
    logs: list[LogEntry],
    current_index: int,
    context_size: int,
) -> list[LogEntry]:
    """Get a log entry with surrounding context.

    Args:
        logs: The list of log entries.
        current_index: Index of the current log entry.
        context_size: Number of logs before and after to include.

    Returns:
        List of log entries including context (may be smaller at boundaries).
    """
    start = max(0, current_index - context_size)
    end = min(len(logs), current_index + context_size + 1)
    return logs[start:end]
