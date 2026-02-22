from __future__ import annotations

import os
import platform
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from selectors import EVENT_READ, DefaultSelector
from threading import Event, Thread


class WatcherBase(ABC):
    """Watches a file for new content appended at the end."""

    def __init__(self) -> None:
        self._fileno: int | None = None
        self._callback: Callable[[bytes], None] | None = None
        self._error_callback: Callable[[Exception], None] | None = None
        self._thread: Thread | None = None
        self._exit_event = Event()

    def watch(
        self,
        *,
        fileno: int,
        callback: Callable[[bytes], None],
        error_callback: Callable[[Exception], None],
    ) -> None:
        """Register a file descriptor to watch."""
        self._fileno = fileno
        self._callback = callback
        self._error_callback = error_callback

    def start(self) -> None:
        """Start the watcher thread."""
        self._thread = Thread(target=self.run, daemon=True)
        self._thread.start()

    def close(self) -> None:
        """Signal the thread to stop and wait for it to finish."""
        self._exit_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    @abstractmethod
    def run(self) -> None:
        """Thread main loop — implemented by subclasses."""
        ...


class PollWatcher(WatcherBase):
    """Poll-based watcher using os.read(). Used on Linux/Windows."""

    _CHUNK_SIZE: int = 64 * 1024
    _POLL_INTERVAL: float = 0.05

    def run(self) -> None:
        assert self._fileno is not None
        assert self._callback is not None
        assert self._error_callback is not None
        fileno = self._fileno
        callback = self._callback
        error_callback = self._error_callback

        while not self._exit_event.is_set():
            try:
                chunk = os.read(fileno, self._CHUNK_SIZE)
                if chunk:
                    callback(chunk)
                else:
                    time.sleep(self._POLL_INTERVAL)
            except Exception as error:
                error_callback(error)
                break


class SelectorWatcher(WatcherBase):
    """Selector-based watcher using kqueue (macOS)."""

    _CHUNK_SIZE: int = 64 * 1024
    _SELECT_TIMEOUT: float = 0.1

    def __init__(self) -> None:
        super().__init__()
        self._selector = DefaultSelector()

    def watch(
        self,
        *,
        fileno: int,
        callback: Callable[[bytes], None],
        error_callback: Callable[[Exception], None],
    ) -> None:
        super().watch(
            fileno=fileno,
            callback=callback,
            error_callback=error_callback,
        )
        self._selector.register(fileno, EVENT_READ)

    def close(self) -> None:
        super().close()
        self._selector.close()

    def run(self) -> None:
        assert self._fileno is not None
        assert self._callback is not None
        assert self._error_callback is not None
        fileno = self._fileno
        callback = self._callback
        error_callback = self._error_callback

        while not self._exit_event.is_set():
            for _key, mask in self._selector.select(
                timeout=self._SELECT_TIMEOUT
            ):
                if self._exit_event.is_set():
                    break
                if mask & EVENT_READ:
                    try:
                        chunk = os.read(fileno, self._CHUNK_SIZE)
                        if chunk:
                            callback(chunk)
                    except Exception as error:
                        error_callback(error)
                        return


def get_watcher() -> WatcherBase:
    """Return the appropriate watcher for the current OS."""
    if platform.system() == "Darwin":
        return SelectorWatcher()
    return PollWatcher()
