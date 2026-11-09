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
assigned to `logs`, and the cursor is placed on the last entry. The file size
is stored as the starting offset for follow mode.

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
daemon thread on an fd opened at the stored offset. It hands byte chunks back
with `call_from_thread`. `_process_chunk` buffers partial lines, parses
complete ones and appends them to `logs`. If the cursor was on the last
entry, it follows the new tail. On stop the current offset is saved so
resuming continues where it left off.

## Command palette

`get_system_commands` adds: Open file, Toggle line wrap, Toggle
case-sensitive filtering, Toggle highlight mode, Show help, Configure columns,
Toggle follow mode.

## CLI

`main()` (also exposed as `jlv` and `json-logs-viewer`) uses argparse:
`file` (optional), `-f/--follow`, `--serve`. `--serve` builds a command
string and hands it to `textual_serve.server.Server`. Without a file the app
starts with the file picker.
