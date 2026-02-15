# Performance Plan: Virtual Scrolling + Read From End

## Problem

Opening a 10,000-line JSONL file takes ~50 seconds. The bottleneck is **not** file
parsing (40ms) or JSON serialization (21ms) — it's mounting 10,000 `ListItem(Static(...))`
DOM widgets into `ListView`, which takes **~48 seconds**.

Additionally, the app loads all logs oldest-first, then scrolls to the bottom — bad UX
since users want to see the newest logs immediately.

## How It Works Today

```
load_file()                          # app.py:88
  ├─ Read file line-by-line            ~40ms   ✅ fast
  ├─ json.loads + LogEntry() per line  ~40ms   ✅ fast
  ├─ self.logs = logs                  triggers watch_logs → apply_filter
  │   └─ self.filtered_logs = ...      triggers _on_filtered_logs_changed
  │       └─ LogList._on_filtered_logs_changed()    # log_list.py:93
  │           ├─ self.clear()                        # remove old DOM nodes
  │           ├─ for each log:
  │           │   ├─ json.dumps(log.data)            # serialize again
  │           │   └─ self.mount(ListItem(Static()))  # ~48s for 10K items 🔴
  │           └─ _update_min_width()                 # json.dumps AGAIN for all
  └─ self.selected_index = last       triggers scroll to bottom
```

**Problems:**
1. `ListView` + `ListItem(Static(...))` creates a real DOM widget per log line — O(n)
   mount time that scales terribly
2. `json.dumps` is called **3 times** per entry (serialize, mount, min_width)
3. After all widgets mount, we set `selected_index` to the last item, causing a scroll
   traversal through all 10K widgets
4. `_update_min_width()` iterates all entries and calls `json.dumps` again on wrap toggle

## Solution Overview

Two changes:
1. **Replace `ListView` with a `ScrollView`-based virtual list** (Line API) — only render
   visible rows, O(1) mount time regardless of log count
2. **Read file from the end** so the newest logs appear first on screen without scrolling

---

## Phase 1: Virtual ScrollView LogList

Replace the current `ListView`-based `LogList` with a `ScrollView` subclass that uses
Textual's **Line API** (`render_line`). This renders only the visible rows.

### 1.1 New `LogList(ScrollView)` widget

**File:** `src/json_logs_viewer/widgets/log_list.py` (rewrite)

```python
class LogList(ScrollView):
    """Virtual-scrolling log list using Textual's Line API."""

    can_focus = True
    SCROLLOFF: int = 3

    BINDINGS = [...]  # same bindings as today

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._log_entries: list[LogEntry] = []
        self._line_cache: LRUCache[int, str] = LRUCache(maxsize=2000)
        self._cursor_index: int = 0      # which log entry is highlighted

    def set_logs(self, *, logs: list[LogEntry]) -> None:
        """Update the log entries and recalculate virtual size."""
        self._log_entries = logs
        self._line_cache = LRUCache(maxsize=2000)
        self._update_virtual_size()
        # Keep cursor in bounds
        if self._cursor_index >= len(logs):
            self._cursor_index = max(0, len(logs) - 1)
        self.refresh()

    def _update_virtual_size(self) -> None:
        """Set virtual_size based on number of log entries."""
        # Each log = 1 row in virtual space
        # Width = max line length (or terminal width, whichever is larger)
        height = len(self._log_entries)
        width = self.size.width  # will be refined
        self.virtual_size = Size(width, height)

    def render_line(self, y: int) -> Strip:
        """Render a single line — only called for visible lines."""
        scroll_x, scroll_y = self.scroll_offset
        line_index = y + scroll_y

        if line_index < 0 or line_index >= len(self._log_entries):
            return Strip.blank(self.size.width)

        # Get cached JSON string or serialize
        if line_index not in self._line_cache:
            log = self._log_entries[line_index]
            self._line_cache[line_index] = json.dumps(
                log.data, ensure_ascii=False
            )
        text = self._line_cache[line_index]

        # Build styled segments (highlighted if cursor is here)
        is_highlighted = line_index == self._cursor_index
        style = self._get_highlight_style() if is_highlighted else Style()
        segments = [Segment(text, style)]
        strip = Strip(segments, len(text))
        strip = strip.crop(scroll_x, scroll_x + self.size.width)
        return strip
```

**Key points:**
- `virtual_size` is set to `Size(max_width, len(logs))` — Textual adds scrollbars
  automatically
- `render_line(y)` only called for visible lines (~40-50 per screen)
- JSON strings cached in an LRU cache (2000 entries) — evicts old entries, no memory
  bloat
- No DOM widgets created — **O(1) mount time**

### 1.2 Cursor / highlight management

The cursor (highlighted row) is managed internally via `_cursor_index`:

```python
def action_cursor_down(self) -> None:
    if self._cursor_index < len(self._log_entries) - 1:
        self._cursor_index += 1
        self._scroll_cursor_into_view()
        self.refresh()

def action_cursor_up(self) -> None:
    if self._cursor_index > 0:
        self._cursor_index -= 1
        self._scroll_cursor_into_view()
        self.refresh()

def action_scroll_top(self) -> None:
    self._cursor_index = 0
    self.scroll_to(y=0, animate=False)
    self.refresh()

def action_scroll_bottom(self) -> None:
    self._cursor_index = max(0, len(self._log_entries) - 1)
    self.scroll_to(y=self._cursor_index, animate=False)
    self.refresh()

def _scroll_cursor_into_view(self) -> None:
    """Ensure cursor is visible with SCROLLOFF padding."""
    visible_top = self.scroll_offset.y
    visible_bottom = visible_top + self.size.height - 1
    target_top = self._cursor_index - self.SCROLLOFF
    target_bottom = self._cursor_index + self.SCROLLOFF

    if target_top < visible_top:
        self.scroll_to(y=max(0, target_top), animate=False)
    elif target_bottom > visible_bottom:
        self.scroll_to(
            y=target_bottom - self.size.height + 1, animate=False
        )
```

### 1.3 Update `app.py` integration

Instead of the reactive `selected_index` driving `LogList.index`, the app calls
`log_list.set_logs(logs=...)` directly:

```python
# In watch_filtered_logs or _on_filtered_logs_changed callback:
log_list = self.query_one("#logs", LogList)
log_list.set_logs(logs=self.filtered_logs)
```

The `selected_index` reactive on the app syncs with `log_list._cursor_index` via
a message or property, keeping the detail modal and status bar working.

### 1.4 Update `styles.tcss`

Remove all `ListItem`/`ListView`-specific styles. The `ScrollView` doesn't use child
widgets, so styles target `LogList` directly:

```tcss
#logs-scroll {
    /* REMOVE — no longer needed, LogList is its own ScrollView */
}

#logs {
    height: 1fr;
    border: solid $primary;
    scrollbar-size: 1 1;
    padding: 0 0 0 1;
}
```

Remove the outer `ScrollableContainer` from `app.py`'s `compose()` since `ScrollView`
handles its own scrolling:

```python
def compose(self) -> ComposeResult:
    yield SearchBar(id="search")
    yield LogList(id="logs")       # no wrapping ScrollableContainer
    yield StatusBar(id="status")
```

### 1.5 Wrap mode support

For wrap mode, `render_line` changes behavior:
- **No wrap (default):** each log = 1 virtual row, horizontal scroll via `strip.crop()`
- **Wrap mode:** each log may span multiple virtual rows. Calculate wrapped line count
  per entry to set correct `virtual_size.height`. Use a mapping from virtual row →
  (log_index, sub_line) to render correctly.

Wrap mode is more complex, so implement no-wrap first, then add wrap as a follow-up.

### 1.6 LogSelected message (Enter key)

```python
def action_select_cursor(self) -> None:
    if 0 <= self._cursor_index < len(self._log_entries):
        log = self._log_entries[self._cursor_index]
        self.post_message(self.LogSelected(log_entry=log))
```

### 1.7 Horizontal scroll width

Instead of iterating all entries to find `max_len`, compute it lazily or during
`set_logs`:

```python
def set_logs(self, *, logs: list[LogEntry]) -> None:
    self._log_entries = logs
    self._line_cache = LRUCache(maxsize=2000)
    # Compute max width by sampling or iterating once
    max_len = 0
    for log in logs:
        s = json.dumps(log.data, ensure_ascii=False)
        max_len = max(max_len, len(s))
    height = len(logs)
    width = max_len + 2  # small padding
    self.virtual_size = Size(width, height)
    ...
```

This still iterates all entries once for width, but `json.dumps` of 10K items takes
only ~21ms, which is acceptable. The serialized strings are **not** stored here — they're
lazily cached in `render_line` via the LRU cache.

---

## Phase 2: Read From End of File

### Current behavior

```python
# app.py load_file():
with path.open("r") as f:
    for idx, line in enumerate(f, start=1):  # reads from line 1 → last
        ...
self.selected_index = max(0, len(logs) - 1)  # scroll to end after loading
```

This means: parse all 10K lines, build all widgets, then scroll to bottom.

### New behavior: read file backward, display immediately

**Approach:** Read the file **from the end** using backward line scanning, so the
newest logs are parsed and displayed first.

**File:** `src/json_logs_viewer/log_reader.py` (new)

```python
import mmap
from pathlib import Path
from collections.abc import Iterator


def read_lines_backward(*, filepath: Path) -> Iterator[tuple[int, str]]:
    """Yield (line_number, line_text) from end of file to beginning.

    Uses mmap + rfind for efficient backward scanning.
    """
    with filepath.open("rb") as f:
        size = f.seek(0, 2)  # seek to end
        if size == 0:
            return

        with mmap.mmap(f.fileno(), size, access=mmap.ACCESS_READ) as mm:
            # Count total lines first for correct line_number assignment
            total_lines = mm.count(b"\n")
            # If file doesn't end with newline, there's one more line
            if mm[-1] != ord(b"\n"):
                total_lines += 1

            position = size
            line_num = total_lines

            while position > 0:
                # Find previous newline
                newline_pos = mm.rfind(b"\n", 0, position - 1)
                if newline_pos == -1:
                    # First line of file
                    line_bytes = mm[0:position]
                    line_text = line_bytes.decode("utf-8").strip()
                    if line_text:
                        yield (1, line_text)
                    break
                else:
                    line_bytes = mm[newline_pos + 1 : position]
                    line_text = line_bytes.decode("utf-8").strip()
                    if line_text:
                        yield (line_num, line_text)
                        line_num -= 1
                    position = newline_pos + 1
```

### Updated `load_file()` in `app.py`

```python
def load_file(self, *, filepath: str) -> None:
    path = Path(filepath)
    ...
    logs: list[LogEntry] = []
    for line_num, line_text in read_lines_backward(filepath=path):
        try:
            data = json.loads(line_text)
            log = LogEntry(line_number=line_num, data=data)
            logs.append(log)
        except json.JSONDecodeError:
            continue

    # logs is now in reverse order (newest first)
    # Reverse to maintain chronological order in the list
    logs.reverse()
    self.logs = logs
    self.filepath = filepath
    # Cursor starts at the last entry (newest) — no scrolling needed
    self.selected_index = max(0, len(logs) - 1)
```

**Wait — if we reverse anyway, why read backward?**

The real win comes from combining backward reading with **incremental loading**:

### Phase 2b: Incremental display (stretch goal)

Instead of loading all 10K lines then displaying, load in batches and update the UI
progressively:

```python
@work(thread=True)
def load_file_async(self, *, filepath: str) -> None:
    """Load file in a background worker, newest lines first."""
    path = Path(filepath)
    batch: list[LogEntry] = []
    BATCH_SIZE = 500

    for line_num, line_text in read_lines_backward(filepath=path):
        data = json.loads(line_text)
        log = LogEntry(line_number=line_num, data=data)
        batch.append(log)

        if len(batch) >= BATCH_SIZE:
            # Post batch to UI thread
            self.call_from_thread(self._append_logs_batch, batch=batch)
            batch = []

    if batch:
        self.call_from_thread(self._append_logs_batch, batch=batch)
```

But for the MVP, simply reading all lines and reversing is fine — 40ms parse time is
already fast. The key UX improvement is that with `ScrollView`, the cursor starts at the
bottom and **the view is already there instantly** since `render_line` only renders the
visible viewport at that scroll position.

### Why this solves "start at newest"

With the virtual `ScrollView`:
1. `set_logs(logs=all_10K_entries)` → sets `virtual_size = Size(w, 10000)` (instant)
2. `self._cursor_index = len(logs) - 1` → cursor is at the last entry
3. `self.scroll_to(y=len(logs) - 1, animate=False)` → scroll to bottom (instant, no
   widgets to traverse)
4. `render_line` is called only for the ~40 visible rows at the bottom → instant render

**No waiting for 10K widgets to mount. No scrolling animation. The newest logs are
visible immediately.**

---

## Phase 3: Test Updates

### Tests that need updating

Most integration tests reference `ListView`-specific APIs that will change:

| Test file | What changes |
|---|---|
| `test_log_list.py` | `log_list._log_entries` stays the same. `log_list.index` → `log_list._cursor_index`. Remove `ListItem` assertions. |
| `test_app.py` | `app.selected_index` sync may change — verify cursor position via `log_list._cursor_index`. |
| `test_search_bar.py` | No changes needed — tests SearchBar + app.filter_query, not LogList internals. |
| `test_status_bar.py` | No changes needed — tests StatusInfo reactive properties. |

### Key test updates in `test_log_list.py`

```python
# Before:
assert log_list.index == 3

# After:
assert log_list._cursor_index == 3
```

```python
# Before: checking ListItem count
assert len(log_list.children) == 4

# After: checking internal data
assert len(log_list._log_entries) == 4
```

Navigation tests (`j`/`k`, `g`/`G`) remain conceptually the same but reference
`_cursor_index` instead of `ListView.index`.

The `test_scroll_top_scrolls_to_top` and `test_scroll_bottom_scrolls_to_bottom` tests
need adjustment since `LogList` is now its own `ScrollView` — no outer
`ScrollableContainer` to query. Instead check `log_list.scroll_offset.y`.

### New performance test

```python
@pytest.mark.asyncio
async def test_large_file_loads_fast(large_jsonl_file: Path) -> None:
    """10K entries should load in under 2 seconds."""
    import time
    app = LogViewerApp(file=str(large_jsonl_file))
    t0 = time.perf_counter()
    async with app.run_test() as pilot:
        await pilot.pause()
        elapsed = time.perf_counter() - t0
        log_list = app.query_one("#logs", LogList)
        assert len(log_list._log_entries) == 10_000
        assert elapsed < 2.0  # should be well under this
```

---

## Implementation Order

1. **Phase 1.1–1.3**: New `LogList(ScrollView)` with `render_line`, cursor management,
   app integration. Remove `ScrollableContainer` wrapper.
2. **Phase 1.4**: Update `styles.tcss` — remove `ListItem`/`ListView` styles.
3. **Phase 1.6**: `LogSelected` message on Enter.
4. **Phase 1.7**: Horizontal scroll width calculation.
5. **Phase 3**: Update all tests.
6. **Phase 2**: Add `read_lines_backward` + use in `load_file` (can be done
   independently of Phase 1, but the full UX benefit requires both).
7. **Phase 1.5**: Wrap mode support (follow-up, not blocking).

## Expected Performance After Changes

| Operation (10K entries) | Before | After |
|---|---|---|
| File read + parse | ~40ms | ~40ms (unchanged) |
| Mount/display | **~48s** | **<50ms** (set virtual_size + render ~40 lines) |
| Scroll to bottom | ~seconds | **instant** (scroll_to + render_line) |
| **Total time to interactive** | **~50s** | **<200ms** |
