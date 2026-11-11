from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TextIO


@contextmanager
def atomic_open(*, path: Path) -> Iterator[TextIO]:
    """Open a text file whose content replaces `path` only on success.

    Writes go to a temporary file in the same directory (a rename is only
    atomic within one filesystem), which then replaces `path` in one step
    with os.replace. If anything fails, `path` keeps its old content and
    the temporary file is removed. The file is created readable by the
    owner only (mkstemp's 0600).

    Raises:
        OSError: The directory doesn't exist or can't be written.
    """
    fd, tmp_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as tmp:
            yield tmp
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise
