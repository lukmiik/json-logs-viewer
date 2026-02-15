from __future__ import annotations

import mmap
from collections.abc import Iterator
from pathlib import Path


def read_lines_backward(*, filepath: Path) -> Iterator[tuple[int, str]]:
    """Yield (line_number, line_text) from end of file to beginning.

    Uses mmap + rfind for efficient backward scanning.

    Args:
        filepath: Path to the file to read.

    Yields:
        Tuples of (line_number, line_text) starting from the last line.
        Empty lines are skipped.
    """
    with filepath.open("rb") as f:
        size = f.seek(0, 2)
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
                    try:
                        line_text = line_bytes.decode("utf-8").rstrip("\n\r")
                    except UnicodeDecodeError:
                        position = 0
                        continue
                    if line_text:
                        yield (1, line_text)
                    break
                else:
                    line_bytes = mm[newline_pos + 1 : position]
                    try:
                        line_text = line_bytes.decode("utf-8").rstrip("\n\r")
                    except UnicodeDecodeError:
                        position = newline_pos + 1
                        line_num -= 1
                        continue
                    if line_text:
                        yield (line_num, line_text)
                    line_num -= 1
                    position = newline_pos + 1
