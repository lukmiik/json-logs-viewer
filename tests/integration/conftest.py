"""Integration test fixtures and utilities."""

import json
from pathlib import Path

import pytest


@pytest.fixture
def sample_jsonl_file(tmp_path: Path) -> Path:
    """Create a sample JSONL file with test log entries."""
    log_file = tmp_path / "sample.jsonl"
    entries = [
        {
            "timestamp": "2024-01-01T12:00:00Z",
            "level": "INFO",
            "message": "Started",
            "service": "api",
            "user": "alice",
        },
        {
            "timestamp": "2024-01-01T12:01:00Z",
            "level": "ERROR",
            "message": "Failed",
            "service": "db",
            "user": "bob",
        },
        {
            "timestamp": "2024-01-01T12:02:00Z",
            "level": "WARN",
            "message": "Slow query",
            "service": "api",
            "latency": "200ms",
        },
        {
            "timestamp": "2024-01-01T12:03:00Z",
            "level": "DEBUG",
            "message": "Debug info",
        },
    ]
    with log_file.open("w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")
    return log_file


@pytest.fixture
def sample_jsonl_entry_count() -> int:
    """Number of entries in sample_jsonl_file fixture."""
    return 4


@pytest.fixture
def many_logs_file(tmp_path: Path) -> Path:
    """Create a JSONL file with many log entries for scroll testing."""
    log_file = tmp_path / "many_logs.jsonl"
    with log_file.open("w", encoding="utf-8") as f:
        for i in range(50):
            entry = {"line": i, "message": f"Log entry {i}"}
            f.write(json.dumps(entry) + "\n")
    return log_file


@pytest.fixture
def many_logs_entry_count() -> int:
    """Number of entries in many_logs_file fixture."""
    return 50


@pytest.fixture
def varying_width_logs_file(tmp_path: Path) -> Path:
    """Create JSONL with logs of varying widths for scroll width tests."""
    log_file = tmp_path / "varying_width.jsonl"
    entries = [
        {"short": "a"},
        {"short": "b"},
        {"short": "c"},
        {"short": "d"},
        {"short": "e"},
        {
            "very_long_field_name": "x" * 100,
            "another_long_field": "y" * 100,
        },
        {"short": "f"},
        {"short": "g"},
        {"short": "h"},
        {"short": "i"},
        {"short": "j"},
        {
            "medium_width": "m" * 50,
        },
        {"short": "k"},
        {"short": "l"},
    ]
    with log_file.open("w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")
    return log_file
