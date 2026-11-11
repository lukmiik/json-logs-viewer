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
├── models.py              LogEntry (pydantic), parse_log_line, level_category
├── field_paths.py         resolve_field, leaf_paths: dotted paths in JSON
├── filter_engine.py       query tokenizer, parser, AST matchers
├── log_reader.py          mmap-based backward line reader
├── log_watcher.py         follow-mode watcher threads
├── clipboard.py           formatting helpers for copy actions
├── export.py              default_export_path, write_jsonl (atomic)
├── atomic_file.py         atomic_open: temp file + os.replace
├── history_store.py       search history file: path, load, save
├── selection_copier.py    SelectionCopier: copy a selection once it settles
├── constants.py           history limit, copy context size, column width,
│                          selection copy delay
├── styles.tcss            app-level CSS
├── widgets/
│   ├── log_list.py        LogList: virtual ScrollView, the main list
│   ├── column_header.py   ColumnHeader: column names above the list
│   ├── search_bar.py      SearchBar: Input bound to filter_query
│   └── status_bar.py      StatusBar: file/count labels, toggle buttons,
│                          Footer
└── modals/
    ├── detail_modal.py    DetailModal: pretty, highlighted JSON of one entry
    ├── history_modal.py   HistoryModal: OptionList of past queries
    ├── columns_modal.py   ColumnsModal: SelectionList of field paths
    ├── file_picker_modal.py   FilePickerModal: DirectoryTree
    ├── export_modal.py    ExportModal: target path, overwrite confirm
    ├── confirm_modal.py   ConfirmModal: yes/no question (y/Enter, n/Esc)
    └── help_modal.py      HelpModal: key reference (`?`)
```

## Screen

```
┌──────────────────────────────────────────────┐
│ SearchBar (#search, layer "search")          │
│   floats over the top while focused          │
├╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌┤
│ #logs-pane (Vertical, carries the border)    │
│   ColumnHeader  col1 | col2 |  (if columns)  │
│   LogList (#logs)                   1fr      │
│     [v1   | v2   | ] {"raw": "json line"}    │
├──────────────────────────────────────────────┤
│ StatusBar (#status)                          │
│   File: x  Total: n  Filtered: m  ⏺ FOLLOW   │
│   Filter: <active query>                     │
│                [Follow] [Aa] [Highlight] [History]
│   Footer (keybindings)                       │
└──────────────────────────────────────────────┘
```

The search bar is on its own layer (`MainScreen { layers: default search
_loading _toastrack _tooltips }` in styles.tcss), so showing it never
resizes or moves the list. Textual's internal layers are listed after it:
a layer missing from the list sorts to the bottom, under the bar.

The default screen is `MainScreen`, whose `AUTO_FOCUS = "#logs"` starts
with the list focused. Textual otherwise focuses the first focusable widget
by screen position, which would be the search bar.

Modals are pushed with `push_screen(..., callback=...)`. Their result is
handled in an `_on_*_selected` callback on the app.

Export (`e`) takes `_matching_logs()`: `filtered_logs` in filter mode,
the query's matches in highlight mode. `ExportModal` returns a path
(an existing file needs a second Enter) and `write_jsonl` writes each
entry's `raw_json` to a temp file in the same directory, then
`os.replace`s it, so a failed export never leaves a partial file.

Clear view (`x`, confirmed with `ConfirmModal`) sets `logs = []`. The
follow offset and `_last_line_number` are kept, so follow mode continues
with only new lines, numbered as in the file. An empty view counts as
"cursor on the last line", so the cursor follows the first new lines.

The search bar's visibility follows its focus (`on_focus` shows it,
`on_blur` hides it). After `enter` the filter stays applied, focus returns
to the list and the bar hides. `StatusInfo` then shows the active query as
`Filter: …` (or `Highlight: …` in highlight mode), and `/` reopens the bar
with the query still in it.

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

The history is global and persistent when the app gets a `history_path`
(`main()` passes `history_store.default_history_path()`, from
`platformdirs`, unless `--no-history`; tests pass none, so they never touch
the real file). It is loaded in `on_mount` and saved by
`watch_search_history` on every change: versioned JSON, written through
`atomic_open` (temp file + `os.replace`, mode 0600 since queries can hold
user IDs or tokens). A missing or damaged file loads as empty; a failed save
warns once.

`logs`, `filter_query`, `case_sensitive` and `highlight_matches` all trigger
`apply_filter()`. In filter mode `filtered_logs` is the matching subset. In
highlight mode `filtered_logs` is `logs` and LogList computes per-row match
flags itself to dim non-matches and drive `n`/`N`.

After each filter change `_restore_selected_log_entry` keeps the cursor on the
same entry, or moves it to the nearest surviving line by line number. Because
`filtered_logs` is a subsequence of `logs` in file order, it is sorted by
`line_number`, so this is a binary search (`bisect_left`) rather than a scan.

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
matching key in `TIMESTAMP_FIELDS`, `LEVEL_FIELDS` and `MESSAGE_FIELDS`.
Dotted candidates (`attributes.level`, `log.level`) go through
`resolve_field`, after the top-level names. These are conveniences, so a value
of an unexpected type never rejects the entry: numbers become text (`30` ->
`"30"`), anything else unusable becomes `None`. `parse_log_line` (used by
both loading and follow mode) skips lines that aren't JSON objects.

Only `level` is used so far: `level_category` maps it to `error`, `warning`,
`debug` or `None` (case-insensitive, plus pino's numeric levels) for the
row colours in `LogList`. Filtering, display and copy work on `data` and
`raw_json`.

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

Opening another file through the picker resets the query, toggles and
columns first. The search history is kept (it's shared by all files).

## Filtering

`filter_engine.parse_filter(query=..., case_sensitive=..., newest_timestamp=...)`
returns a `Matcher`: call it with a `LogEntry`. `matcher.relative` is True
when the query uses `last:<duration>`.

1. `Tokenizer` produces `FIELD`, `VALUE`, `QUOTED`, `AND`, `OR`, `NOT`,
   `LPAREN`, `RPAREN`, `EOF`. A word directly followed by `:` is a field.
   Its value may follow after spaces (`level: error`), but a keyword or
   another `field:` there is never taken as the value: `level: AND x`
   is an existence check followed by a term. A word followed by `<`, `<=`,
   `>` or `>=` (spaces allowed) is a `FIELD`, an `OP` and its value.
2. `Parser` is recursive descent:
   ```
   expr    := term (OR term)*
   term    := factor ([AND] factor)*
   factor  := NOT factor | primary
   primary := "(" expr ")" | FIELD [VALUE|QUOTED] | FIELD OP value
            | VALUE | QUOTED
   ```
   `AND` is optional: in `_term`, a token that can start a term (`FIELD`,
   `VALUE`, `QUOTED`, `NOT`, `(`) right after a term means implicit AND, at
   the same precedence as `AND`. Each bare word is its own `FullText` term;
   quotes make a phrase.
3. AST nodes:
   - `FieldMatch`: substring match on `str(value)` of the field.
   - `FieldExists`: the field path reaches at least one value.
   - `FullText`: substring match on `LogEntry.search_text`: the JSON line
     as shown, with `\u` escapes decoded (cached per entry).
   - `Compare`: `field<op>value`. The value is parsed once: a number
     (compares numeric values and numeric strings) or an ISO date/time via
     `datetime.fromisoformat` (compares ISO strings and epoch s/ms; naive
     times are UTC). Anything else is a `FilterError`.
   - `Last`: `last:<n>[smhd]` matches logs whose detected `timestamp` is
     within the window before the newest one. The parser asks
     `newest_timestamp()` (an O(n) scan) only when the query uses it.
     Because the window moves, follow mode re-filters everything for a
     relative query instead of only the appended logs (app and LogList).
   - `And`, `Or`, `Not`, `Group`.

Field paths: a name without `.` is a plain `data.get(name)` (fast path, the
common case). A dotted name goes through `resolve_field`. It yields every
value the path can reach, trying the rest of the path as one key (keys like
`"service.name"`) and then each split point, and fanning out over list
elements. A node matches if any yielded value does.

## LogList (virtual scrolling)

`LogList` is a `ScrollView` that implements the line API (`render_line`).
Only visible rows are rendered, so file size does not affect drawing cost.

- Each row is the optional column prefix (`value.ljust(width) | ...`, widths
  capped at `MAX_COL_WIDTH`) followed by `raw_json`. `column_text` reads a
  column, dotted paths through `resolve_field`, and shows non-strings as
  JSON (`null`, `true`).
- `@timestamp`, `@level` and `@message` (`DETECTED_COLUMNS`) show the raw
  value of the detected field via `models.find_first`, the same lookup that
  fills `LogEntry.timestamp/level/message`. A real field of that name wins
  (ECS logs have a real `@timestamp`, which is also a detected name).
  `discover_fields()` lists them first when any log has them.
- The columns modal offers `discover_fields()`: the 20 most common
  `leaf_paths` (dotted paths to values; objects are descended, lists are
  values). Counting walks every object, so it runs lazily when the modal
  asks, and `_counted_logs` lets follow-mode appends count only new logs.
- `ColumnHeader` is a separate one-line widget above the list (not a row
  inside it, so scrolling and click maths are unchanged). It shows
  `LogList.header_text()`, built with the rows' widths and separator,
  cropped to the list's `scroll_x`, and hides when no columns are set.
- Changing the columns scrolls the list back to the left edge, where the
  columns are drawn.
- `on_resize` scrolls the cursor back into view (with its `SCROLLOFF`
  margin), since a shorter list (header shown, terminal resized) can
  otherwise hide it.
- `_style_for_entry` colours a whole row by its level, using the component
  classes `loglist--level-error/warning/debug` (theme colours `$text-error`,
  `$text-warning`, `$text-muted`), then applies highlight mode's bold/dim.
  The cursor row keeps the cursor style. The full (non-partial) component
  style is used so translucent theme colours are blended with the
  background.
- `virtual_size` width is the longest line, which gives horizontal scrolling.
  In wrap mode each entry is pre-wrapped to the viewport width and
  `_entry_start_rows` maps entries to screen rows. `_wrap_text` matches
  Rich's word wrap, but uses `_fast_wrap` (an `rfind` loop, or fixed chunks
  for compact JSON) for plain ASCII lines. That's ~40x faster on 100k lines
  and fuzz-tested to give identical output; other text falls back to Rich.
  The scrollbar check stops counting rows once the screen is full.
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

Appends are incremental. `models.appended_entries` detects that a new list is
the old one plus a tail, comparing by identity so a reload with equal content
still counts as new. Then `watch_logs` keeps the field counts (anything
else resets them) and filters only the tail with the cached
`_active_matcher`, and `LogList.set_logs` extends the
highlight flags and wrapped rows. Wrap does a full pass instead when the
new entries could change the wrap width: no scrollbar yet, or columns
shown. A follow batch costs ~2 ms at 100k lines instead of re-filtering
everything (18 ms; 61 ms with wrap).

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
