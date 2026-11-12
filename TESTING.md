# Testing

Tests use pytest, pytest-asyncio and Textual's `App.run_test()` / `Pilot`.
There are no snapshot tests yet.

```bash
uv run pytest                  # unit + integration (performance excluded)
uv run pytest -m performance   # performance tests only
uv run pytest --cov=json_logs_viewer
```

`pyproject.toml` sets `addopts = "-m 'not performance'"`, so a plain
`pytest` run skips the performance marker.

## Layout

```
tests/
├── unit/                      pure functions and classes, no app
│   ├── test_filter_engine.py  tokenizer, parser, matchers, errors
│   ├── test_log_entry.py      LogEntry fields, appended_entries
│   ├── test_log_reader.py     read_lines_backward edge cases
│   ├── test_log_watcher.py    PollWatcher / SelectorWatcher
│   ├── test_clipboard.py      copy formatting and context window
│   ├── test_columns.py        field discovery / counting
│   ├── test_search_history.py add_to_history
│   ├── test_serve_command.py  --serve command quoting
│   └── test_wrap.py           fast wrap vs Rich (differential fuzzing)
├── integration/               full app driven through Pilot
│   ├── conftest.py            temp JSONL fixtures
│   ├── test_app.py
│   ├── test_log_list.py       navigation, scrolling, wrap, highlight, copy
│   ├── test_search_bar.py
│   ├── test_status_bar.py
│   ├── test_selection_restore.py  cursor kept after filter changes
│   ├── test_copy_on_select.py     debounced copy of selected text
│   ├── test_detail_modal.py
│   ├── test_history_modal.py
│   ├── test_columns_modal.py
│   ├── test_file_picker_modal.py
│   ├── test_help_modal.py
│   └── test_follow_mode.py
├── snapshots/                 SVG screenshots of the whole app
│   ├── test_snapshots.py      main screen, filter, highlight, wrap,
│   │                          columns, detail, help, narrow terminal
│   ├── data/app.jsonl         fixed input, separate from test_files/
│   └── __snapshots__/         approved SVGs (open them in a browser)
└── performance/
    └── test_performance.py    load time, virtual rendering, line cache
```

## Fixtures (`tests/integration/conftest.py`)

| Fixture                   | Content                                      |
|---------------------------|----------------------------------------------|
| `sample_jsonl_file`       | 4 entries with level/service/user fields     |
| `many_logs_file`          | 50 entries, for scrolling                    |
| `varying_width_logs_file` | short and long lines, for horizontal width   |

Each has a matching `*_entry_count` fixture. Files are written to
`tmp_path`. The performance tests use `test_files/large_sample.jsonl`.

## Writing an integration test

```python
@pytest.mark.asyncio
async def test_filter_hides_non_matching(sample_jsonl_file: Path) -> None:
    app = LogViewerApp(file=str(sample_jsonl_file))
    async with app.run_test() as pilot:
        await pilot.pause()  # let on_mount load the file
        await pilot.press("/")
        await pilot.press(*"level:error", "enter")
        await pilot.pause()
        assert [log.data["level"] for log in app.filtered_logs] == ["ERROR"]
```

Guidelines:

- Call `await pilot.pause()` after actions that trigger reactive watchers or
  `call_after_refresh`.
- Assert on app state (`app.filtered_logs`, `app.selected_index`, ...) rather
  than rendered output.
- Follow-mode tests append to the file and wait for the watcher thread, so
  they need short polling loops or pauses.

## Snapshot tests

`snap_compare` (from `pytest-textual-snapshot`) runs the app, applies key
presses or a `run_before` coroutine, and compares the screen with the
approved SVG in `__snapshots__/`. They catch layout and styling changes that
assertions on state miss (CSS, status bar clipping, modal size).

- Missing snapshot or intended change: `uv run pytest tests/snapshots
  --snapshot-update`, then open the changed SVGs and check them before
  committing. An approved snapshot that is wrong makes the test useless.
- Failure: open `snapshot_report.html` for the before/after diff. CI uploads
  it as the `snapshot-report` artifact.
- Keep them deterministic: fixed terminal size, input from
  `tests/snapshots/data/`, and a bare file name (the status bar shows the
  path as given), which the `app` fixture handles with `chdir`.

## Manual testing

`test_files/` has sample data from 15 to 100k lines. For follow mode, run the
generator in one terminal and the app in another:

```bash
uv run python test_files/generate_logs.py test_files/test_follow.jsonl
```

```bash
uv run jlv test_files/test_follow.jsonl -f
```
