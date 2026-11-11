# JSON Logs Viewer (`jlv`)

An interactive terminal viewer for JSONL log files, built with
[Textual](https://textual.textualize.io/).

## Features

- Virtual-scrolling log list that stays fast on 100k+ line files.
- Vim-style navigation: `j`/`k`, `g`/`G`, `ctrl+d`/`ctrl+u`, `h`/`l`, `0`/`$`.
- Filter queries with field matching, full-text search and `AND`/`OR`/`NOT`.
- Filter mode (hide non-matches) or highlight mode (dim non-matches, jump
  between matches with `n`/`N`).
- Case-sensitive toggle.
- Soft-wrap toggle for long lines (horizontal scrolling otherwise).
- Detail view with pretty-printed JSON. Mouse-selecting text copies it.
- Copy to the clipboard via OSC 52: `y` copies the log as pretty JSON, `Y`
  copies it plus up to 5 entries before and after as raw JSONL.
- Columns: show any of the 20 most common top-level fields as aligned columns
  in front of each line.
- Follow mode (like `tail -F`) for files that are still being written. If
  the file is truncated or rotated (e.g. by logrotate), it is reloaded.
- File picker to open another file without restarting.
- In-memory search history.
- Can be served in a browser via `textual-serve` (optional `serve` extra).

## Installation

The package is not on PyPI yet. Install from a clone:

```bash
uv tool install .
```

This installs two equivalent commands: `jlv` and `json-logs-viewer`.

`--serve` (browser mode) needs the optional `serve` extra, which adds a web
server stack most users don't need:

```bash
uv tool install '.[serve]'
```

## Usage

```bash
jlv app.jsonl            # open a file
jlv app.jsonl -f         # open and follow new lines
jlv                      # start with the file picker
jlv app.jsonl --serve    # serve the app in a browser
```

Each line must be one JSON object. Blank lines and lines that are not valid
JSON are skipped.

## Filter queries

Press `/` to open the search bar, type a query and press `enter` to apply it.
Submit an empty query to clear the filter.

| Query                                          | Matches                                    |
|------------------------------------------------|--------------------------------------------|
| `error`                                        | `error` anywhere in the log (full text)    |
| `connection refused`                           | both words, anywhere in the log            |
| `"connection refused"`                         | the exact phrase                           |
| `level:error`                                  | field `level` contains `error`             |
| `message:"connection refused"`                 | quoted value with spaces                   |
| `level:`                                       | entries that have a `level` field          |
| `http.status_code:502`                         | nested field `{"http": {"status_code": …}}` |
| `level:error service:api`                      | both conditions (space means AND)          |
| `level:error AND service:api`                  | the same, with explicit `AND`              |
| `level:error OR level:warn`                    | either condition                           |
| `NOT level:debug`                              | negation                                   |
| `(level:error OR level:warn) AND service:api`  | grouping                                   |

Rules:

- Matching is substring-based and case-insensitive by default (`C` toggles).
- Precedence: `NOT` > `AND` > `OR`. Operators are case-insensitive.
- A space between terms means `AND`, at the same precedence as `AND`:
  `a OR b c` is `a OR (b AND c)`. Quote words to match them as a phrase.
- Dotted field names reach into nested objects: `user.id:42` matches
  `{"user": {"id": 42}}`, a top-level key named `user.id`, or a nested key
  with dots like `Resource.service.name` in `{"Resource": {"service.name": …}}`.
  On a list, any element can match: `events.name:retry`.
- An invalid query shows an error toast and leaves the list unfiltered.

## Keybindings

Press `?` in the app for the full list.

| Key                 | Action                                       |
|---------------------|----------------------------------------------|
| `j`/`k`, `↓`/`↑`    | move down/up                                 |
| `g` / `G`           | first / last entry                           |
| `ctrl+d` / `ctrl+u` | half page down / up                          |
| `h`/`l`, `0`/`$`    | scroll left/right, line start/end            |
| `enter`             | open detail view                             |
| `/`                 | focus search bar (`esc` returns to the list) |
| `n` / `N`           | next / previous match (highlight mode)       |
| `C`                 | toggle case-sensitive filtering              |
| `m`                 | toggle highlight mode                        |
| `w`                 | toggle soft wrap                             |
| `y` / `Y`           | copy log / copy log with context             |
| `c`                 | configure columns                            |
| `H`                 | search history                               |
| `f`                 | toggle follow mode                           |
| `o`                 | open file picker                             |
| `?`                 | help                                         |
| `ctrl+p`            | command palette                              |
| `q`                 | quit                                         |

Detail view: `j`/`k` next/previous log, `y`/`Y` copy, `ctrl+d`/`ctrl+u`
scroll, `g`/`G` top/bottom, `esc`/`q` close.

## Development

```bash
uv sync
uv run jlv test_files/sample.jsonl
```

Run with live CSS reloading and the Textual dev console:

```bash
uv run textual console              # in one terminal
uv run textual run --dev -c jlv test_files/sample.jsonl
```

Checks (also run by pre-commit and CI):

```bash
uv run ruff check --fix .
uv run ruff format .
uv run ty check
uv run pytest
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for how the code is organised,
[TESTING.md](TESTING.md) for the test suite, and [RELEASING.md](RELEASING.md)
for publishing.

## License

MIT
