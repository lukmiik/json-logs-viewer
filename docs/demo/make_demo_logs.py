"""Write the logs the README recording uses (deterministic).

Usage: uv run python docs/demo/make_demo_logs.py <folder>

Writes api.jsonl and worker.jsonl. With --append, instead appends a few new
api lines slowly to <folder>/api.jsonl, to show follow mode.
"""

from __future__ import annotations

import json
import random
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

START = datetime(2026, 3, 14, 9, 0, 0, tzinfo=UTC)
ENDPOINTS = [
    ("GET", "/api/orders"),
    ("GET", "/api/users/{id}"),
    ("POST", "/api/checkout"),
    ("GET", "/api/products"),
    ("PUT", "/api/cart"),
]
JOBS = ["send_email", "resize_image", "sync_inventory", "charge_card"]


def _stamp(*, moment: datetime) -> str:
    return moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _api_line(*, rng: random.Random, moment: datetime) -> dict[str, object]:
    method, path = rng.choice(ENDPOINTS)
    path = path.replace("{id}", str(rng.randint(100, 999)))
    roll = rng.random()
    status = 200
    level = "info"
    message = f"{method} {path}"
    extra: dict[str, object] = {}
    if roll < 0.07:
        status, level = rng.choice([500, 502, 503]), "error"
        message = f"{method} {path} failed: upstream timeout"
        extra["error"] = {
            "type": "TimeoutError",
            "stack": [
                "payments/client.py:88 in charge",
                "api/checkout.py:142 in create_order",
                "api/server.py:57 in handle",
            ],
        }
    elif roll < 0.17:
        status, level = rng.choice([404, 429]), "warn"
        message = f"{method} {path} rejected"
    elif roll < 0.35:
        level = "debug"
        message = f"cache hit for {path}"
    return {
        "timestamp": _stamp(moment=moment),
        "level": level,
        "message": message,
        "http": {
            "method": method,
            "path": path,
            "status": status,
            "duration_ms": rng.randint(3, 900 if level == "error" else 180),
        },
        "user": {"id": rng.randint(1000, 1100)},
        **extra,
    }


def _worker_line(*, rng: random.Random, moment: datetime) -> dict[str, object]:
    job = rng.choice(JOBS)
    roll = rng.random()
    if roll < 0.05:
        level, message = "error", f"job {job} failed after 3 retries"
    elif roll < 0.15:
        level, message = "warn", f"job {job} retrying"
    else:
        level, message = "info", f"job {job} done"
    return {
        "ts": _stamp(moment=moment),
        "severity": level.upper(),
        "msg": message,
        "job": {"name": job, "attempt": 1 if level == "info" else 3},
    }


def write_logs(*, folder: Path) -> None:
    rng = random.Random(7)
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "api.jsonl").open("w") as api:
        moment = START
        for _ in range(400):
            moment += timedelta(milliseconds=rng.randint(200, 2500))
            api.write(json.dumps(_api_line(rng=rng, moment=moment)) + "\n")
    with (folder / "worker.jsonl").open("w") as worker:
        moment = START
        # Ends before api.jsonl: lines appended to api in follow mode then
        # come after everything already shown (follow doesn't re-sort).
        for _ in range(140):
            moment += timedelta(milliseconds=rng.randint(1000, 6000))
            line = _worker_line(rng=rng, moment=moment)
            worker.write(json.dumps(line) + "\n")


def append_slowly(*, folder: Path) -> None:
    """Append api lines after the newest one, a few per second."""
    rng = random.Random(11)
    path = folder / "api.jsonl"
    last = json.loads(path.read_text().splitlines()[-1])["timestamp"]
    moment = datetime.fromisoformat(last)
    for _ in range(30):
        moment += timedelta(milliseconds=rng.randint(200, 900))
        with path.open("a") as api:
            api.write(json.dumps(_api_line(rng=rng, moment=moment)) + "\n")
        time.sleep(0.25)


if __name__ == "__main__":
    target = Path(sys.argv[1])
    if "--append" in sys.argv:
        append_slowly(folder=target)
    else:
        write_logs(folder=target)
