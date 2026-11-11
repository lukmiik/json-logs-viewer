"""Reading logs piped into jlv (`kubectl logs -f pod | jlv`).

Textual reads the keyboard from file descriptor 0. When stdin is a pipe,
take_over_stdin() moves the pipe to another descriptor and puts the
terminal back on 0. StdinCopy then copies the pipe into a private
temporary file, which the app opens in follow mode like any log file.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import threading
from contextlib import suppress
from pathlib import Path

# The file argument that means "read stdin", as in many CLI tools.
STDIN_ARG = "-"
# How the copy is named in the UI instead of its temporary path.
STDIN_LABEL = "stdin"


def stdin_is_piped() -> bool:
    """Whether something is piped in (stdin isn't a terminal)."""
    return sys.stdin is not None and not sys.stdin.isatty()


def take_over_stdin() -> int:
    """Move the piped stdin to a new descriptor; put the terminal on 0.

    Returns the descriptor to read the pipe from.

    Raises:
        OSError: There is no terminal to read the keyboard from (for
            example under cron), or the platform has no /dev/tty.
    """
    if os.name != "posix":
        raise OSError("reading piped input isn't supported on Windows yet")
    pipe_fd = os.dup(0)
    try:
        tty_fd = os.open("/dev/tty", os.O_RDWR)
    except OSError:
        os.close(pipe_fd)
        raise
    os.dup2(tty_fd, 0)
    os.close(tty_fd)
    return pipe_fd


class StdinCopy:
    """Copy a pipe into `<private temp dir>/stdin` in a background thread.

    The folder is created 0700 and the file 0600: piped logs can hold
    secrets. close() deletes both. `finished` is set once the pipe ends.
    """

    def __init__(self, *, fd: int) -> None:
        self._fd = fd
        self._folder = tempfile.mkdtemp(prefix="jlv-")
        self.path = str(Path(self._folder) / STDIN_LABEL)
        # O_EXCL: the folder is new and private, so the file can't exist.
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        out_fd = os.open(self.path, flags, 0o600)
        self._out = os.fdopen(out_fd, "wb", buffering=0)
        self.finished = threading.Event()
        self._thread = threading.Thread(
            target=self._copy, name="jlv-stdin", daemon=True
        )

    def start(self) -> None:
        self._thread.start()

    def _copy(self) -> None:
        try:
            while data := os.read(self._fd, 65536):
                self._out.write(data)
        except (OSError, ValueError):
            # OSError: the pipe broke; what arrived is kept. ValueError:
            # close() closed the copy while data was still arriving (jlv is
            # quitting), which used to print a traceback on exit.
            pass
        finally:
            self.finished.set()

    def close(self) -> None:
        """Stop reading and delete the copy and its folder."""
        for close in (self._out.close, lambda: os.close(self._fd)):
            with suppress(OSError):
                close()
        shutil.rmtree(self._folder, ignore_errors=True)
