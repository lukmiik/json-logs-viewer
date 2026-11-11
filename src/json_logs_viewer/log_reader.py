from __future__ import annotations

import mmap
from collections.abc import Iterator
from pathlib import Path


def _decode(line_bytes: bytes) -> str:
    """A line as text, with invalid UTF-8 bytes as U+FFFD.

    The whole line used to be dropped; compressed files and follow mode
    already kept it like this.
    """
    return line_bytes.decode("utf-8", errors="replace").rstrip("\n\r")


def read_lines_backward(
    *, filepath: Path, size: int | None = None
) -> Iterator[tuple[int, str]]:
    """Yield (line_number, line_text) from end of file to beginning.

    Uses mmap + rfind for efficient backward scanning.

    Args:
        filepath: Path to the file to read.
        size: Read only the first `size` bytes. Pass the size measured before
            reading so bytes appended meanwhile are left for follow mode.

    Yields:
        Tuples of (line_number, line_text) starting from the last line.
        Empty lines are skipped.
    """
    with filepath.open("rb") as f:
        file_size = f.seek(0, 2)
        size = file_size if size is None else min(size, file_size)
        if size == 0:
            return

        with mmap.mmap(f.fileno(), size, access=mmap.ACCESS_READ) as mm:
            total_lines = 0
            pos = 0
            while pos < size:
                newline_pos = mm.find(b"\n", pos)
                if newline_pos == -1:
                    total_lines += 1
                    break
                total_lines += 1
                pos = newline_pos + 1

            position = size
            line_num = total_lines

            while position > 0:
                newline_pos = mm.rfind(
                    b"\n", 0, position - 1 if position > 1 else 0
                )
                if newline_pos == -1:
                    line_bytes = mm[0:position]
                    line_text = _decode(line_bytes)
                    if line_text:
                        yield (1, line_text)
                    break
                else:
                    line_bytes = mm[newline_pos + 1 : position]
                    line_text = _decode(line_bytes)
                    if line_text:
                        yield (line_num, line_text)
                    line_num -= 1
                    position = newline_pos + 1


def find_line_boundary(*, filepath: Path, size: int) -> tuple[int, int]:
    """Return (offset just past the last newline, newlines before it).

    Only the first `size` bytes are considered. Bytes after the returned
    offset form an unterminated line that may still be being written.
    """
    with filepath.open("rb") as f:
        size = min(size, f.seek(0, 2))
        if size == 0:
            return 0, 0
        with mmap.mmap(f.fileno(), size, access=mmap.ACCESS_READ) as mm:
            offset = mm.rfind(b"\n", 0, size) + 1
        line_count = 0
        f.seek(0)
        remaining = offset
        while remaining:
            chunk = f.read(min(remaining, 1 << 20))
            line_count += chunk.count(b"\n")
            remaining -= len(chunk)
    return offset, line_count
