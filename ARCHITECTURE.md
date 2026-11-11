# Architecture

jlv is a single-screen Textual app. All state lives in memory on the `App`
as reactive attributes. Widgets subscribe to those attributes and redraw
themselves when they change. Nothing is persisted between runs.

## Layout

```
src/json_logs_viewer/
├── __init__.py            exports main()
├── app.py                 LogViewerApp: state, file loading, filtering,
│                          follow mode, command palette, CLI (main)
├── models.py              LogEntry (pydantic)
├── filter_engine.py       query tokenizer, parser, AST matchers
├── log_reader.py          mmap-based backward line reader
├── log_watcher.py         follow-mode watcher threads
├── clipboard.py           formatting helpers for copy actions
├── constants.py           history limit, copy context size, column width
├── styles.tcss            app-level CSS
├── widgets/
│   ├── log_list.py        LogList: virtual ScrollView, the main list
│   ├── search_bar.py      SearchBar: Input bound to filter_query
│   ├── status_bar.py      StatusBar: file/count labels, toggle buttons,
│   │                      Footer
│   └── feature_summary_modal.py   help modal (`?`)
└── modals/
    ├── detail_modal.py    DetailModal: pretty JSON of one entry
    ├── history_modal.py   HistoryModal: OptionList of past queries
    ├── columns_modal.py   ColumnsModal: SelectionList of fields
    └── file_picker_modal.py   FilePickerModal: DirectoryTree
```

## Screen

```
┌──────────────────────────────────────────────┐
│ LogList (#logs)                     1fr      │
│   [col1 | col2 | ] {"raw": "json line"}      │
├──────────────────────────────────────────────┤
│ SearchBar (#search)    hidden unless focused │
│                        or a query is active  │
├──────────────────────────────────────────────┤
│ StatusBar (#status)                          │
│   File: x  Total: n  Filtered: m  ⏺ FOLLOW   │
│                [Follow] [Aa] [Highlight] [History]
│   Footer (keybindings)                       │
└──────────────────────────────────────────────┘
```

Modals are pushed with `push_screen(..., callback=...)`. Their result is
handled in an `_on_*_selected` callback on the app.

## State (`LogViewerApp` reactives)

| Attribute           | Type             | Meaning                                    |
|---------------------|------------------|--------------------------------------------|
| `logs`              | `list[LogEntry]` | every parsed entry in file order           |
| `filtered_logs`     | `list[LogEntry]` | what LogList shows                         |
| `filter_query`      | `str`            | current query text                         |
| `selected_index`    | `int`            | cursor index into `filtered_logs`          |
| `search_history`    | `list[str]`      | submitted queries, oldest first, max 100   |
| `filepath`          | `str \| None`    | loaded file                                |
| `wrap_log_lines`    | `bool`           | soft wrap vs horizontal scroll             |
| `case_sensitive`    | `bool`           | filter case sensitivity                    |
| `highlight_matches` | `bool`           | highlight mode vs filter mode              |
| `columns`           | `list[str]`      | fields shown as columns                    |
| `follow_mode`       | `bool`           | watcher thread running                     |

`SearchBar` sets `filter_query` on `enter` and appends the query to
`search_history` (skipping an immediate repeat). `HistoryModal` shows the
history newest first.

`logs`, `filter_query`, `case_sensitive` and `highlight_matches` all trigger
`apply_filter()`. In filter mode `filtered_logs` is the matching subset. In
highlight mode `filtered_logs` is `logs` and LogList computes per-row match
flags itself to dim non-matches and drive `n`/`N`.

After each filter change `_restore_selected_log_entry` keeps the cursor on the
same entry, or on the nearest surviving entry in file order.

Lists are always replaced, never mutated in place, so the reactive watchers
fire (e.g. follow mode does `self.logs = [*self.logs, *new_logs]`).

## Data model

```python
class LogEntry(BaseModel):
    line_number: int          # 1-based line in the file
    data: dict[str, Any]      # parsed JSON object
    raw_json: str = ""        # original line, used for display and copy
    timestamp: datetime | None = None
    level: str | None = None
    message: str | None = None
```

A `model_validator` fills `timestamp`, `level` and `message` from the first
matching key in `TIMESTAMP_FIELDS`, `LEVEL_FIELDS` and `MESSAGE_FIELDS`. The
UI does not use these fields yet: filtering, display and copy all work on
`data` and `raw_json`.

## Loading a file

`load_file()` calls `read_lines_backward()` (log_reader.py). It mmaps the
file, counts lines forward with `mm.find(b"\n")`, then walks backwards with
`mm.rfind` to yield `(line_number, text)` pairs. Empty lines and lines that
are not valid UTF-8 are skipped. Each line is parsed with `json.loads`.
Invalid JSON is logged and skipped. The list is reversed into file order,
assigned to `logs`, and the cursor is placed on the last entry.

The size is measured before reading and only that many bytes are read, so
anything appended meanwhile is left for follow mode. `find_line_boundary`
then sets the follow position. It keeps one invariant: `_follow_offset` is
where the first not-yet-consumed line starts, and `_last_line_number` is the
number of file lines before it. An unterminated last line counts as consumed
only if it parsed as JSON. A half-written object can't parse, so follow mode
re-reads it once the writer finishes it.

Opening another file through the picker resets the query, toggles, columns
and history first.

## Filtering

`filter_engine.parse_filter(query=..., case_sensitive=...)` returns a
`Callable[[LogEntry], bool]`.

1. `Tokenizer` produces `FIELD`, `VALUE`, `QUOTED`, `AND`, `OR`, `NOT`,
   `LPAREN`, `RPAREN`, `EOF`. A word directly followed by `:` is a field.
2. `Parser` is recursive descent:
   ```
   expr    := term (OR term)*
   term    := factor (AND factor)*
   factor  := NOT factor | primary
   primary := "(" expr ")" | FIELD [VALUE|QUOTED] | (VALUE|QUOTED)+
   ```
   There is no implicit AND. Two terms without an operator raise
   `FilterError`.
3. AST nodes:
   - `FieldMatch`: substring match on `str(data[field])`.
   - `FieldExists`: `field in data`.
   - `FullText`: substring match on `"k=v k=v ..."` built from `data`.
   - `And`, `Or`, `Not`, `Group`.

Field lookup is top-level only.

## LogList (virtual scrolling)

`LogList` is a `ScrollView` that implements the line API (`render_line`).
Only visible rows are rendered, so file size does not affect drawing cost.

- Each row is the optional column prefix (`value.ljust(width) | ...`, widths
  capped at `MAX_COL_WIDTH`) followed by `raw_json`.
- `virtual_size` width is the longest line, which gives horizontal scrolling.
  In wrap mode each entry is pre-wrapped to the viewport width and
  `_entry_start_rows` maps entries to screen rows.
- An `LRUCache` (2000 entries) caches each entry's raw line text.
- The cursor keeps `SCROLLOFF = 3` rows of margin.
- Clicking moves the cursor. Double-click or `enter` posts
  `LogList.LogSelected`, and the app opens `DetailModal`.

## Follow mode

`log_watcher.get_watcher()` returns `PollWatcher` (Linux/Windows: `os.read`
every 50 ms) or `SelectorWatcher` (macOS: kqueue). The watcher runs in a
daemon thread on an fd opened at the stored offset. `_process_chunk` splits
the bytes on `\n` before decoding (so a UTF-8 character cut between reads
stays intact), keeps the trailing partial line in `_follow_buffer`, counts
every line (blank and invalid ones too) for `line_number`, and appends the
parsed entries to `logs`. If the cursor was on the last entry, it follows the
new tail. `_follow_offset` only advances past consumed lines, so resuming
re-reads anything not yet processed.

The watcher thread never calls into the app directly. It posts messages
(`FollowData`, `FollowError`, `FollowedFileReset`) with `post_message`, which
is thread-safe and doesn't wait:

- **Session token.** Each follow session has a `threading.Event`, passed to
  the watcher callbacks with `functools.partial` and carried by every message.
  `_stop_follow` sets it, and handlers ignore messages from any session other
  than `_follow_session`. A chunk still queued when follow stops is dropped
  without moving the offset.
- **Back-pressure.** After posting `FollowData` the watcher waits for the
  message's `consumed` event, so at most one chunk is in flight and a fast
  writer can't make it read unboundedly ahead. It waits in 50 ms slices and
  gives up once the session stops. That way `join()` in `_stop_follow` never
  waits on it. `call_from_thread` would block until the main thread
  answered, which can't happen while the main thread is in `join()`.

When a read returns no data, the watcher checks whether the file was reset:

- **Truncated**: `fstat(fd).st_size` is below the fd's read offset (the
  kernel keeps the offset when another process truncates the file).
- **Rotated**: `stat(path)` names a different device/inode than the open fd
  (e.g. logrotate renamed it and created a new file). If the path is missing
  (mid-rotation) it keeps waiting.

On a reset the watcher stops itself and calls `reset_callback`, which posts
`LogViewerApp.FollowedFileReset` (`post_message` is thread-safe and doesn't
block). The app then reloads the file with `load_file` and restarts follow
mode, so `logs`, line numbers and the partial-line buffer match the new
file.

## Command palette

`get_system_commands` adds: Open file, Toggle line wrap, Toggle
case-sensitive filtering, Toggle highlight mode, Show help, Configure columns,
Toggle follow mode.

## CLI

`main()` (also exposed as `jlv` and `json-logs-viewer`) uses argparse:
`file` (optional), `-f/--follow`, `--serve`. Without a file the app starts
with the file picker.

`textual-serve` is an optional extra (`pip install 'json-logs-viewer[serve]'`).
Without it, `--serve` exits with an install hint instead of a traceback.
`--serve` hands `textual_serve.server.Server` a command string, which it runs
through a shell (`/bin/sh -c`, or `cmd.exe /c` on Windows) for every browser
session. The filename is never put in that string. `main()` stores it in the
`JLV_SERVE_FILE` environment variable, which the child inherits and pops on
start. `build_serve_command` only contains fixed arguments
(`sys.executable -m json_logs_viewer [--follow]`), quoted with `shlex.join`
on POSIX or `subprocess.list2cmdline` on Windows. So no filename can be
parsed as shell syntax on either platform.
