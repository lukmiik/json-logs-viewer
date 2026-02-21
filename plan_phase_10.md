# Phase 10: Follow Mode & File Watching — Implementation Plan

## Goal

Enable real-time log monitoring: when follow mode is active, the app watches the log
file for new lines, parses them as `LogEntry` objects, appends them to `app.logs`, and
auto-scrolls to the bottom so the user always sees the latest output.

---

## Key Decision: stdlib watcher instead of watchdog

Inspired by [Toolong](https://github.com/Textualize/toolong/blob/main/src/toolong/watcher.py)
(by Textual's creator), we use **Python's standard library** instead of `watchdog`:

- **macOS**: `selectors.DefaultSelector` (kqueue-backed) for instant OS-level
  notifications via `SelectorWatcher`
- **Linux/Windows**: Simple polling with `os.read()` / `os.lseek()` via `PollWatcher`,
  sleeping 50ms when idle — negligible CPU cost

**Benefits over watchdog**:
- Zero external dependency (watchdog can be removed from `pyproject.toml`)
- Battle-tested pattern from Toolong, a production Textual log viewer
- Simpler code: ~30 lines per watcher vs watchdog's observer/handler boilerplate
- Works with raw file descriptors — reads only new bytes from current position
- No debounce needed: `os.read()` naturally batches whatever is available

---

## Overview

The implementation spans four areas:

1. **Watcher** — stdlib-based file monitor that detects new bytes appended to a file
2. **Textual integration** — bridging the watcher background thread into Textual's
   async event loop
3. **Auto-scroll behavior** — smart scroll-to-bottom with pause-on-scroll-up
4. **UI indicators** — CLI flag, toggle command, StatusBar indicator

---

## 1. File Watcher (`log_watcher.py`)

New file: `src/json_logs_viewer/log_watcher.py`

### Architecture

Following Toolong's pattern, we implement a base class with two platform-specific
subclasses and a factory function:

```
log_watcher.py
├── WatcherBase (ABC)       — thread lifecycle, shared read logic
├── PollWatcher             — Linux/Windows: poll with os.read + sleep
├── SelectorWatcher         — macOS: selectors.DefaultSelector (kqueue)
└── get_watcher()           — factory returning the right one for the OS
```

### WatcherBase

```python
from abc import ABC, abstractmethod
from threading import Event, Thread
from typing import Callable


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
        """Signal the thread to stop."""
        self._exit_event.set()
        self._thread = None

    @abstractmethod
    def run(self) -> None:
        """Thread main loop — implemented by subclasses."""
        ...
```

### PollWatcher (Linux/Windows)

```python
import os
import time


class PollWatcher(WatcherBase):
    """Poll-based watcher using os.read()."""

    def run(self) -> None:
        chunk_size = 64 * 1024
        fileno = self._fileno
        callback = self._callback
        error_callback = self._error_callback

        while not self._exit_event.is_set():
            try:
                position = os.lseek(fileno, 0, os.SEEK_CUR)
                chunk = os.read(fileno, chunk_size)
                if chunk:
                    callback(chunk)
                else:
                    time.sleep(0.05)
            except Exception as error:
                error_callback(error)
                break
```

### SelectorWatcher (macOS)

```python
from selectors import DefaultSelector, EVENT_READ
import os


class SelectorWatcher(WatcherBase):
    """Selector-based watcher using kqueue (macOS)."""

    def __init__(self) -> None:
        super().__init__()
        self._selector = DefaultSelector()

    def watch(self, *, fileno, callback, error_callback) -> None:
        super().watch(
            fileno=fileno, callback=callback, error_callback=error_callback
        )
        self._selector.register(fileno, EVENT_READ)

    def close(self) -> None:
        super().close()
        self._selector.close()

    def run(self) -> None:
        chunk_size = 64 * 1024
        fileno = self._fileno
        callback = self._callback
        error_callback = self._error_callback

        while not self._exit_event.is_set():
            for key, mask in self._selector.select(timeout=0.1):
                if self._exit_event.is_set():
                    break
                if mask & EVENT_READ:
                    try:
                        chunk = os.read(fileno, chunk_size)
                        if chunk:
                            callback(chunk)
                    except Exception as error:
                        error_callback(error)
                        return
```

### Factory

```python
import platform


def get_watcher() -> WatcherBase:
    """Return the appropriate watcher for the current OS."""
    if platform.system() == "Darwin":
        return SelectorWatcher()
    return PollWatcher()
```

### Key Differences from Toolong

- **Simplified**: We watch a single file, not multiple. The `watch()` method takes one
  file descriptor.
- **Raw bytes callback**: The callback receives `bytes` chunks. The caller (app.py)
  handles decoding, line splitting, and JSON parsing — keeping the watcher generic.
- **No line-break scanning in watcher**: Toolong scans for `\n` offsets because it
  needs random-access line positions. We don't need that — we parse lines sequentially.

---

## 2. Textual Integration (`app.py`)

### Challenge

The watcher runs on a **background thread**, but Textual's reactive system must be
updated on the **main async thread**.

### Solution: `App.call_from_thread()`

Textual provides `app.call_from_thread(callback, *args)` which safely schedules a
callable on the main event loop from a background thread.

### New Instance Attributes

```python
class LogViewerApp(App):
    # Existing reactive (already referenced in architecture, add if missing)
    follow_mode: reactive[bool] = reactive(False)

    # Instance state
    _watcher: WatcherBase | None = None
    _watch_file: IO[bytes] | None = None   # keep the fd open for os.read
    _follow_buffer: str = ""               # partial line buffer
    _last_line_number: int = 0             # for assigning line numbers
```

### File Descriptor Management

The watcher needs a raw file descriptor kept open for `os.read()`. We open the file
in binary mode and seek to the end:

```python
def _start_follow(self) -> None:
    if not self.filepath or self._watcher is not None:
        return
    self._last_line_number = len(self.logs)
    self._follow_buffer = ""
    self._watch_file = open(self.filepath, "rb")
    self._watch_file.seek(0, os.SEEK_END)  # skip existing content

    self._watcher = get_watcher()
    self._watcher.watch(
        fileno=self._watch_file.fileno(),
        callback=self._on_watcher_data,
        error_callback=self._on_watcher_error,
    )
    self._watcher.start()
```

### Processing New Data (Thread Bridge)

```python
def _on_watcher_data(self, chunk: bytes) -> None:
    """Called from watcher thread — bridge to main thread."""
    self.call_from_thread(self._process_chunk, chunk)

def _on_watcher_error(self, error: Exception) -> None:
    """Called from watcher thread on error."""
    self.call_from_thread(self.notify, f"Follow error: {error}", severity="error")
    self.call_from_thread(self._stop_follow)

def _process_chunk(self, chunk: bytes) -> None:
    """Decode chunk, split lines, parse JSON, append to logs. Runs on main thread."""
    try:
        text = self._follow_buffer + chunk.decode("utf-8", errors="replace")
    except Exception:
        return

    # Split into complete lines; keep any trailing partial line in buffer
    if text.endswith("\n"):
        lines = text.split("\n")
        self._follow_buffer = ""
    else:
        parts = text.split("\n")
        lines = parts[:-1]
        self._follow_buffer = parts[-1]

    new_logs: list[LogEntry] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            self._last_line_number += 1
            log = LogEntry(
                line_number=self._last_line_number,
                data=data,
                raw_json=line,
            )
            new_logs.append(log)
        except json.JSONDecodeError:
            self.log.warning(f"Follow: invalid JSON: {line[:80]}")

    if new_logs:
        self.logs = list(self.logs) + new_logs
```

### Stop & Cleanup

```python
def _stop_follow(self) -> None:
    if self._watcher is not None:
        self._watcher.close()
        self._watcher = None
    if self._watch_file is not None:
        self._watch_file.close()
        self._watch_file = None
    self._follow_buffer = ""
```

### Reactive Watcher

```python
def watch_follow_mode(self, follow_mode: bool) -> None:
    if follow_mode:
        self._start_follow()
    else:
        self._stop_follow()
```

### Cleanup on Exit

```python
def on_unmount(self) -> None:
    self._stop_follow()
```

### Toggle Action & Keybinding

```python
BINDINGS = [
    ...
    ("f", "toggle_follow", "Follow"),
]

def action_toggle_follow(self) -> None:
    if not self.filepath:
        self.notify("No file loaded", severity="warning")
        return
    self.follow_mode = not self.follow_mode
```

Add to `get_system_commands()`:

```python
yield SystemCommand(
    "Toggle follow mode",
    "Watch file for new log entries in real-time",
    self.action_toggle_follow,
)
```

### CLI Integration

The `-f` / `--follow` flag already exists in `main()` but is unused. Wire it up:

```python
app = LogViewerApp(file=args.file, follow=args.follow)
```

Update `__init__` to accept `follow`:

```python
def __init__(self, *, file=None, follow: bool = False, **kwargs) -> None:
    super().__init__(**kwargs)
    self.initial_file = file
    self._initial_follow = follow
    ...

def on_mount(self) -> None:
    if self.initial_file:
        self.load_file(filepath=self.initial_file)
    if self._initial_follow:
        self.follow_mode = True
```

---

## 3. Auto-Scroll Behavior (`widgets/log_list.py`)

### Rules

- **When at bottom** + new logs arrive → auto-scroll to show new entries
- **When user scrolls up** → pause auto-scroll (don't yank user away)
- **When user presses `G`** → resume auto-scroll (they're back at bottom)

### Implementation

Modify `_on_filtered_logs_changed`:

```python
def _on_filtered_logs_changed(self, filtered_logs: list[LogEntry]) -> None:
    was_at_bottom = self._is_at_bottom
    self.set_logs(logs=filtered_logs)
    if self._app:
        if was_at_bottom and self._app.follow_mode:
            # Follow mode: jump cursor to newest entry
            new_last = max(0, len(self._log_entries) - 1)
            self._cursor_index = new_last
            self._app.selected_index = new_last
        else:
            idx = self._app.selected_index
            if idx < len(self._log_entries):
                self._cursor_index = idx
        self._pending_scroll = True
        self.refresh()
        self.call_after_refresh(self._apply_pending_scroll)

@property
def _is_at_bottom(self) -> bool:
    """Check if scroll position is at or near the bottom."""
    if not self._log_entries:
        return True
    return self.scroll_offset.y >= self.max_scroll_y - 1
```

---

## 4. StatusBar Updates (`widgets/status_bar.py`)

### Follow Mode Indicator

Add a follow mode label and toggle button:

In `StatusInfo`:

```python
follow_mode: reactive[bool] = reactive(False)

def compose(self) -> ComposeResult:
    with Horizontal(id="status-left"):
        yield Label(id="status-filename")
        yield Label(id="status-total")
        yield Label(id="status-filtered")
        yield Label(id="status-follow")       # NEW

    with Horizontal(id="status-right"):
        yield Button("Follow", id="status-follow-toggle")  # NEW
        yield Button("Aa", id="status-case-sensitive")
        yield Button("Highlight", id="status-highlight-matches")
        yield Button("History", id="status-history")
```

Update `_update_labels`:

```python
follow_label = self.query_one("#status-follow", Label)
follow_label.update("⏺ FOLLOW" if self.follow_mode else "")
```

Wire button:

```python
elif event.button.id == "status-follow-toggle":
    app.follow_mode = not app.follow_mode
```

Update `StatusBar.on_mount` to watch `follow_mode`:

```python
self.watch(self.app, "follow_mode", self._update_status)
```

---

## 5. File Structure Changes

### New Files

| File | Description |
|------|-------------|
| `src/json_logs_viewer/log_watcher.py` | WatcherBase, PollWatcher, SelectorWatcher, get_watcher() |
| `tests/unit/test_log_watcher.py` | Unit tests for watcher |
| `tests/integration/test_follow_mode.py` | Integration tests for follow mode UI |

### Modified Files

| File | Changes |
|------|---------|
| `src/json_logs_viewer/app.py` | follow_mode reactive, watcher lifecycle, `_process_chunk`, toggle action, CLI flag |
| `src/json_logs_viewer/widgets/log_list.py` | `_is_at_bottom` property, auto-scroll in `_on_filtered_logs_changed` |
| `src/json_logs_viewer/widgets/status_bar.py` | Follow indicator label, follow toggle button |
| `pyproject.toml` | Remove `watchdog` from dependencies |

---

## 6. Testing Plan

### Unit Tests: `tests/unit/test_log_watcher.py`

| Test | Description |
|------|-------------|
| `test_poll_watcher_detects_new_bytes` | Append bytes to file, verify callback receives them |
| `test_poll_watcher_sleeps_when_idle` | No new data → no callback, thread stays alive |
| `test_callback_receives_only_new_content` | Start watcher at end of file, append, verify only new bytes in callback |
| `test_handles_read_error` | Simulate read error, verify `error_callback` is called |
| `test_close_stops_thread` | Call `close()`, verify thread exits |
| `test_get_watcher_returns_correct_type` | Verify factory returns PollWatcher on Linux |

**Testing approach**: Use `tmp_path`, open file with `os.open()`, create PollWatcher
directly (avoid platform-gating), write to file with a separate fd, use short
`time.sleep()` to let the poll loop read, assert on captured callback data.

### Integration Tests: `tests/integration/test_follow_mode.py`

| Test | Description |
|------|-------------|
| `test_follow_toggle_updates_state` | Press `f`, verify `app.follow_mode` is True, press again → False |
| `test_follow_mode_indicator_in_status_bar` | Toggle follow, verify StatusBar shows "⏺ FOLLOW" |
| `test_follow_mode_from_cli_flag` | Create app with `follow=True`, verify follow mode is active after mount |
| `test_process_chunk_appends_logs` | Directly call `app._process_chunk()` with valid JSONL bytes, verify `app.logs` grows |
| `test_process_chunk_handles_partial_lines` | Send incomplete line, then complete it in next chunk, verify correct parsing |
| `test_auto_scroll_on_new_logs` | Enable follow, simulate new logs via `_process_chunk`, verify cursor at last entry |
| `test_no_auto_scroll_when_scrolled_up` | Enable follow, scroll up, simulate new logs, verify cursor stays put |

**Testing approach**: Integration tests use `async with app.run_test()`. For new-log
simulation, call `app._process_chunk()` directly (avoids flaky timing with real
polling in CI). Watcher thread behavior is tested in unit tests.

---

## 7. Implementation Order

1. **Implement `log_watcher.py`** — WatcherBase, PollWatcher, SelectorWatcher,
   get_watcher()
2. **Write `tests/unit/test_log_watcher.py`**
3. **Wire up `app.py`** — reactive state, watcher lifecycle, `_process_chunk`,
   toggle action, CLI flag
4. **Update `LogList`** — `_is_at_bottom`, auto-scroll logic
5. **Update `StatusBar`** — follow indicator and toggle button
6. **Write `tests/integration/test_follow_mode.py`**
7. **Remove `watchdog`** from `pyproject.toml` dependencies
8. **Run full test suite** and quality checks (`ruff check`, `ruff format`, `ty check`)

---

## 8. Edge Cases & Considerations

- **Partial lines**: The `_follow_buffer` accumulates bytes until a `\n` is seen.
  This handles log writers that flush mid-line.
- **Large bursts**: `os.read(fileno, 64*1024)` reads up to 64KB at once, naturally
  batching rapid writes. No manual debounce needed.
- **Invalid JSON**: Skipped with a warning log, same as initial file loading.
- **File truncation**: If the file shrinks (log rotation), `os.read()` returns empty
  bytes. The poll watcher sleeps and retries. For MVP this is acceptable — the user
  can toggle follow off/on to re-attach.
- **Memory**: All logs in memory (MVP constraint). Active follow on a high-volume file
  will grow memory. LRU eviction is Phase 14.
- **Filter interaction**: New logs appended to `app.logs` trigger `watch_logs()` →
  `apply_filter()` automatically. Only matching logs appear in `filtered_logs`.
- **Thread safety**: `call_from_thread()` is the only bridge. The watcher callback
  never touches reactive state directly.
- **Existing `watchdog` dep**: Can be removed from `pyproject.toml` since it's not
  used elsewhere in the codebase.
