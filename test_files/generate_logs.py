#!/usr/bin/env python3
"""Generate JSONL logs for manual testing of follow mode.

Usage:
    python test_files/generate_logs.py [FILE] [--interval SECONDS]

Clears the file, writes initial logs, then appends new logs indefinitely.
"""

import argparse
import json
import random
import time
from datetime import UTC, datetime
from pathlib import Path

LEVELS = ["DEBUG", "INFO", "INFO", "INFO", "WARN", "ERROR"]
SERVICES = ["api", "db", "auth", "worker", "cache"]
MESSAGES = [
    "Request processed successfully",
    "Connection established",
    "Cache miss for key",
    "Slow query detected",
    "Authentication failed",
    "Rate limit exceeded",
    "Health check passed",
    "Retry attempt",
    "Timeout waiting for response",
    "Invalid input received",
    "Background job completed",
    "Database connection pool exhausted",
    "TLS handshake failed",
    "Message published to queue",
    "Schema validation error",
]

DEFAULT_FILE = "test_files/test_follow.jsonl"


def make_log() -> dict[str, str | int]:
    level = random.choice(LEVELS)
    return {
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "level": level,
        "message": random.choice(MESSAGES),
        "service": random.choice(SERVICES),
        "request_id": f"req-{random.randint(1000, 9999)}",
        "latency_ms": random.randint(1, 500),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "file", nargs="?", default=DEFAULT_FILE, help="Output file"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Seconds between new logs (default: 1.0)",
    )
    parser.add_argument(
        "--initial",
        type=int,
        default=10,
        help="Number of initial logs to write (default: 10)",
    )
    args = parser.parse_args()

    path = Path(args.file)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Clear and write initial logs
    with path.open("w", encoding="utf-8") as f:
        for _ in range(args.initial):
            f.write(json.dumps(make_log()) + "\n")
    print(f"Wrote {args.initial} initial logs to {path}")

    # Append new logs indefinitely
    print(f"Appending a new log every {args.interval}s — press Ctrl+C to stop")
    count = args.initial
    try:
        while True:
            time.sleep(args.interval)
            batch = random.randint(1, 5)
            with path.open("a", encoding="utf-8") as f:
                for _ in range(batch):
                    f.write(json.dumps(make_log()) + "\n")
            count += batch
            print(f"\r  logs written: {count}", end="", flush=True)
    except KeyboardInterrupt:
        print(f"\nStopped. Total logs: {count}")


if __name__ == "__main__":
    main()
