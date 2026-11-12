from __future__ import annotations

import os
import stat
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import TextIO


def _umask_mode() -> int:
    """The mode a new file normally gets (0666 minus the umask)."""
    umask = os.umask(0)  # reading the umask means setting it...
    os.umask(umask)  # ...so restore it at once
    return 0o666 & ~umask


@contextmanager
def atomic_open(
    *, path: Path, new_file_mode: int | None = None
) -> Generator[TextIO]:
    """Open a text file whose content replaces `path` only on success.

    Writes go to a temporary file in the same directory (a rename is only
    atomic within one filesystem), which then replaces `path` in one step
    with os.replace. If anything fails, `path` keeps its old content and
    the temporary file is removed.

    Replacing a file keeps its permissions; a new file gets
    `new_file_mode`, or the usual umask default. (The temporary file is
    0600, which used to carry over and make an overwritten file private.)

    A symlink is followed: its target gets the new content and the link
    stays (os.replace on the link itself would swap the link for a plain
    file, e.g. breaking a dotfile manager's link).

    Raises:
        OSError: The directory doesn't exist or can't be written.
    """
    path = Path(os.path.realpath(path))
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except FileNotFoundError:
        mode = _umask_mode() if new_file_mode is None else new_file_mode
    fd, tmp_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        os.chmod(fd, mode)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as tmp:
            yield tmp
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise
