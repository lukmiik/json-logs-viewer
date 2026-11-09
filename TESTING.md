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
│   ├── test_log_entry.py      LogEntry field auto-detection
│   ├── test_log_reader.py     read_lines_backward edge cases
│   ├── test_log_watcher.py    PollWatcher / SelectorWatcher
│   ├── test_clipboard.py      copy formatting and context window
│   └── test_columns.py        field discovery / counting
├── integration/               full app driven through Pilot
│   ├── conftest.py            temp JSONL fixtures
│   ├── test_app.py
│   ├── test_log_list.py       navigation, scrolling, wrap, highlight, copy
│   ├── test_search_bar.py
│   ├── test_status_bar.py
│   ├── test_detail_modal.py
│   ├── test_history_modal.py
│   ├── test_columns_modal.py
│   ├── test_file_picker_modal.py
│   ├── test_follow_mode.py
│   └── test_feature_summary_modal.py
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
        await pilot.pause()            # let on_mount load the file
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

## Manual testing

`test_files/` has sample data from 15 to 100k lines. For follow mode, run the
generator in one terminal and the app in another:

```bash
uv run python test_files/generate_logs.py test_files/test_follow.jsonl
```

```bash
uv run jlv test_files/test_follow.jsonl -f
```
