# Testing Guidelines

This document describes the testing strategy and architecture for the JSON Logs Viewer project.

## Testing Philosophy

- **Test business logic thoroughly**: Filter engine, log parsing, and data models
- **Test UI interactions**: Keybindings, navigation, modal behavior
- **Test state management**: Reactive updates and data flow
- **No snapshot tests**: Focus on behavioral testing rather than visual regression

## Test Framework Setup

### Dependencies

```toml
[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.21",
]
```

### Configuration

Create `pytest.ini`:

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
```

## Test Directory Structure

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── unit/
│   ├── __init__.py
│   ├── test_log_entry.py    # LogEntry model tests
│   ├── test_filter_engine.py # Filter query parsing
│   └── test_log_watcher.py  # File watching logic
└── integration/
    ├── __init__.py
    ├── test_app.py          # Main app behavior
    ├── test_log_list.py     # LogList widget
    ├── test_search.py       # Search/filter UI
    ├── test_detail_modal.py # Detail view modal
    └── test_history_modal.py # History modal
```

## Unit Tests

### LogEntry Model Tests

Test Pydantic model validation and parsing:

```python
# tests/unit/test_log_entry.py
import pytest
from datetime import datetime
from json_logs_viewer.models import LogEntry


class TestLogEntry:
    def test_parse_valid_json(self) -> None:
        line = '{"time": "2024-01-15T10:30:00Z", "level": "ERROR", "message": "Test"}'
        entry = LogEntry.from_line(1, line)
        
        assert entry.line_number == 1
        assert entry.level == "ERROR"
        assert entry.timestamp is not None
        assert entry.message == "Test"
    
    def test_parse_with_aliases(self) -> None:
        line = '{"severity": "WARN", "msg": "Warning message"}'
        entry = LogEntry.from_line(1, line)
        
        assert entry.level == "WARN"
        assert entry.message is None  # 'msg' not aliased to 'message'
        assert entry.data["msg"] == "Warning message"
    
    def test_parse_invalid_json(self) -> None:
        line = "not valid json"
        entry = LogEntry.from_line(1, line)
        
        assert entry.raw_line == line
        assert entry.data == {}
        assert entry.level is None
    
    def test_extra_fields_allowed(self) -> None:
        line = '{"level": "INFO", "custom_field": "value"}'
        entry = LogEntry.from_line(1, line)
        
        assert entry.data["custom_field"] == "value"
```

### Filter Engine Tests

Test query parsing and filtering logic:

```python
# tests/unit/test_filter_engine.py
import pytest
from json_logs_viewer.filter_engine import parse_filter, FilterError
from json_logs_viewer.models import LogEntry


class TestFilterEngine:
    def test_simple_field_filter(self) -> None:
        query = "level:ERROR"
        filter_fn = parse_filter(query)
        
        error_log = LogEntry.from_line(1, '{"level": "ERROR"}')
        info_log = LogEntry.from_line(2, '{"level": "INFO"}')
        
        assert filter_fn(error_log) is True
        assert filter_fn(info_log) is False
    
    def test_and_operator(self) -> None:
        query = "level:ERROR AND service:api"
        filter_fn = parse_filter(query)
        
        log1 = LogEntry.from_line(1, '{"level": "ERROR", "service": "api"}')
        log2 = LogEntry.from_line(2, '{"level": "ERROR", "service": "web"}')
        
        assert filter_fn(log1) is True
        assert filter_fn(log2) is False
    
    def test_or_operator(self) -> None:
        query = "level:ERROR OR level:WARN"
        filter_fn = parse_filter(query)
        
        error_log = LogEntry.from_line(1, '{"level": "ERROR"}')
        warn_log = LogEntry.from_line(2, '{"level": "WARN"}')
        info_log = LogEntry.from_line(3, '{"level": "INFO"}')
        
        assert filter_fn(error_log) is True
        assert filter_fn(warn_log) is True
        assert filter_fn(info_log) is False
    
    def test_not_operator(self) -> None:
        query = "NOT level:DEBUG"
        filter_fn = parse_filter(query)
        
        debug_log = LogEntry.from_line(1, '{"level": "DEBUG"}')
        info_log = LogEntry.from_line(2, '{"level": "INFO"}')
        
        assert filter_fn(debug_log) is False
        assert filter_fn(info_log) is True
    
    def test_grouping(self) -> None:
        query = "(status:500 OR status:503) AND method:POST"
        filter_fn = parse_filter(query)
        
        log1 = LogEntry.from_line(1, '{"status": 500, "method": "POST"}')
        log2 = LogEntry.from_line(2, '{"status": 500, "method": "GET"}')
        log3 = LogEntry.from_line(3, '{"status": 503, "method": "POST"}')
        
        assert filter_fn(log1) is True
        assert filter_fn(log2) is False
        assert filter_fn(log3) is True
    
    def test_invalid_query_raises_error(self) -> None:
        with pytest.raises(FilterError):
            parse_filter("level:")  # Missing value
```

### Log Watcher Tests

Test file watching and log parsing:

```python
# tests/unit/test_log_watcher.py
import pytest
from unittest.mock import Mock, MagicMock
from json_logs_viewer.log_watcher import LogWatcher


class TestLogWatcher:
    def test_new_lines_trigger_callback(self, tmp_path) -> None:
        log_file = tmp_path / "test.log"
        log_file.write_text('{"level": "INFO", "message": "First"}\n')
        
        callback = Mock()
        watcher = LogWatcher(str(log_file), callback)
        watcher.start()
        
        # Simulate file change
        log_file.write_text('{"level": "INFO", "message": "First"}\n{"level": "ERROR", "message": "Second"}\n')
        
        # Wait for watcher to process
        import time
        time.sleep(0.1)
        
        assert callback.call_count == 1
        assert callback.call_args[0][0].level == "ERROR"
        
        watcher.stop()
```

## UI Integration Tests

Use Textual's `run_test()` method and `Pilot` class for UI testing:

```python
# tests/integration/test_app.py
import pytest
from json_logs_viewer.app import LogViewerApp


class TestLogViewerApp:
    async def test_app_mounts_successfully(self) -> None:
        async with LogViewerApp().run_test() as pilot:
            assert pilot.app is not None
            assert pilot.app.screen is not None
    
    async def test_quit_keybinding(self) -> None:
        async with LogViewerApp().run_test() as pilot:
            await pilot.press("q")
            assert pilot.app.is_running is False
    
    async def test_search_keybinding_focuses_input(self) -> None:
        async with LogViewerApp().run_test() as pilot:
            await pilot.press("/")
            
            from textual.widgets import Input
            focused = pilot.app.focused
            assert isinstance(focused, Input)
```

### LogList Widget Tests

```python
# tests/integration/test_log_list.py
import pytest
from json_logs_viewer.app import LogViewerApp
from json_logs_viewer.models import LogEntry


class TestLogList:
    async def test_logs_displayed_in_table(self) -> None:
        async with LogViewerApp().run_test() as pilot:
            # Add test logs to app state
            logs = [
                LogEntry.from_line(1, '{"level": "INFO", "message": "First"}'),
                LogEntry.from_line(2, '{"level": "ERROR", "message": "Second"}'),
            ]
            pilot.app.state.logs = logs
            
            # Check LogList contains logs
            log_list = pilot.app.query_one("#log-list")
            assert log_list.row_count == 2
    
    async def test_navigation_keys(self) -> None:
        async with LogViewerApp().run_test() as pilot:
            pilot.app.state.logs = [
                LogEntry.from_line(1, '{"level": "INFO", "message": "First"}'),
                LogEntry.from_line(2, '{"level": "INFO", "message": "Second"}'),
            ]
            
            log_list = pilot.app.query_one("#log-list")
            log_list.focus()
            
            await pilot.press("j")
            assert log_list.cursor_row == 1
            
            await pilot.press("k")
            assert log_list.cursor_row == 0
    
    async def test_open_detail_view(self) -> None:
        async with LogViewerApp().run_test() as pilot:
            pilot.app.state.logs = [
                LogEntry.from_line(1, '{"level": "ERROR", "message": "Test"}'),
            ]
            
            await pilot.press("enter")
            
            # Check detail modal is open
            assert len(pilot.app.screen_stack) == 2
```

### Search/Filter Tests

```python
# tests/integration/test_search.py
import pytest
from json_logs_viewer.app import LogViewerApp
from json_logs_viewer.models import LogEntry


class TestSearch:
    async def test_filter_reduces_visible_logs(self) -> None:
        async with LogViewerApp().run_test() as pilot:
            pilot.app.state.logs = [
                LogEntry.from_line(1, '{"level": "INFO", "message": "First"}'),
                LogEntry.from_line(2, '{"level": "ERROR", "message": "Second"}'),
            ]
            
            await pilot.press("/")
            await pilot.press(*list("level:ERROR"))
            await pilot.press("enter")
            
            assert pilot.app.state.filter_query == "level:ERROR"
            assert len(pilot.app.state.filtered_logs) == 1
    
    async def test_search_history_updated(self) -> None:
        async with LogViewerApp().run_test() as pilot:
            await pilot.press("/")
            await pilot.press(*list("level:WARN"))
            await pilot.press("enter")
            
            assert "level:WARN" in pilot.app.state.search_history
```

### Modal Tests

```python
# tests/integration/test_detail_modal.py
import pytest
from json_logs_viewer.app import LogViewerApp
from json_logs_viewer.models import LogEntry


class TestDetailModal:
    async def test_detail_shows_log_content(self) -> None:
        async with LogViewerApp().run_test() as pilot:
            pilot.app.state.logs = [
                LogEntry.from_line(1, '{"level": "ERROR", "message": "Test error"}'),
            ]
            
            await pilot.press("enter")
            
            # Modal should be displayed
            from textual.screen import ModalScreen
            assert isinstance(pilot.app.screen, ModalScreen)
    
    async def test_close_detail_with_escape(self) -> None:
        async with LogViewerApp().run_test() as pilot:
            pilot.app.state.logs = [
                LogEntry.from_line(1, '{"level": "INFO", "message": "Test"}'),
            ]
            
            await pilot.press("enter")
            initial_stack_size = len(pilot.app.screen_stack)
            
            await pilot.press("escape")
            
            assert len(pilot.app.screen_stack) == initial_stack_size - 1
```

## Shared Fixtures

```python
# tests/conftest.py
import pytest
from json_logs_viewer.models import LogEntry


@pytest.fixture
def sample_logs() -> list[LogEntry]:
    """Provide sample log entries for tests."""
    return [
        LogEntry.from_line(1, '{"time": "2024-01-15T10:00:00Z", "level": "INFO", "message": "Application started", "service": "api"}'),
        LogEntry.from_line(2, '{"time": "2024-01-15T10:01:00Z", "level": "DEBUG", "message": "Processing request", "service": "api"}'),
        LogEntry.from_line(3, '{"time": "2024-01-15T10:02:00Z", "level": "ERROR", "message": "Database connection failed", "service": "db"}'),
        LogEntry.from_line(4, '{"time": "2024-01-15T10:03:00Z", "level": "WARN", "message": "High memory usage", "service": "api"}'),
        LogEntry.from_line(5, '{"time": "2024-01-15T10:04:00Z", "level": "INFO", "message": "Request completed", "service": "api", "duration_ms": 150}'),
    ]


@pytest.fixture
def temp_log_file(tmp_path):
    """Create a temporary log file."""
    log_file = tmp_path / "test.log"
    log_file.write_text(
        '{"level": "INFO", "message": "Line 1"}\n'
        '{"level": "ERROR", "message": "Line 2"}\n'
    )
    return str(log_file)
```

## Running Tests

### Run all tests

```bash
uv run pytest
```

### Run with coverage

```bash
uv run pytest --cov=json_logs_viewer --cov-report=html
```

### Run specific test file

```bash
uv run pytest tests/unit/test_filter_engine.py
```

### Run specific test class

```bash
uv run pytest tests/unit/test_filter_engine.py::TestFilterEngine
```

### Run with verbose output

```bash
uv run pytest -v
```

### Run async tests with auto mode

```bash
uv run pytest --asyncio-mode=auto
```

## Test Patterns and Best Practices

### 1. Test State, Not Implementation

```python
# Good: Test the outcome
async def test_filter_updates_state(self) -> None:
    async with LogViewerApp().run_test() as pilot:
        await pilot.press("/")
        await pilot.press(*list("level:ERROR"))
        await pilot.press("enter")
        
        assert pilot.app.state.filter_query == "level:ERROR"

# Avoid: Testing implementation details
async def test_filter_calls_parse(self) -> None:
    with patch("json_logs_viewer.app.parse_filter") as mock:
        # This is too coupled to implementation
        ...
```

### 2. Use Descriptive Test Names

```python
# Good
def test_parse_filter_with_and_operator_matches_both_conditions():
    ...

# Avoid
def test_filter_1():
    ...
```

### 3. One Assertion Concept Per Test

```python
# Good: Separate concerns
def test_parse_valid_json_extracts_level(self) -> None:
    entry = LogEntry.from_line(1, '{"level": "ERROR"}')
    assert entry.level == "ERROR"

def test_parse_valid_json_extracts_timestamp(self) -> None:
    entry = LogEntry.from_line(1, '{"time": "2024-01-15T10:30:00Z"}')
    assert entry.timestamp is not None
```

### 4. Use Fixtures for Common Setup

```python
@pytest.fixture
def error_log():
    return LogEntry.from_line(1, '{"level": "ERROR", "message": "Test"}')

def test_filter_matches_error(error_log):
    filter_fn = parse_filter("level:ERROR")
    assert filter_fn(error_log) is True
```

### 5. Mock External Dependencies

```python
def test_log_watcher_handles_file_changes(self, tmp_path) -> None:
    # Use tmp_path for file operations
    # Use unittest.mock for external dependencies
    ...
```

### 6. Test Edge Cases

```python
def test_parse_empty_json(self) -> None:
    entry = LogEntry.from_line(1, "{}")
    assert entry.data == {}
    assert entry.level is None

def test_parse_non_json_line(self) -> None:
    entry = LogEntry.from_line(1, "not json")
    assert entry.raw_line == "not json"
    assert entry.data == {}
```

## Code Quality Checks

After making changes, run:

```bash
# Linting
uv run ruff check --fix .

# Formatting
uv run ruff format .

# Type checking
uv run ty check

# Tests
uv run pytest
```

## Continuous Integration

Example GitHub Actions workflow:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Install uv
        uses: astral-sh/setup-uv@v3
      
      - name: Run tests
        run: uv run pytest --cov=json_logs_viewer --cov-report=xml
      
      - name: Run linting
        run: uv run ruff check .
      
      - name: Run type check
        run: uv run ty check
```

## Debugging Tests

### Enable Textual debug mode

```python
async def test_with_debug(self) -> None:
    app = LogViewerApp()
    app.debug = True  # Enable debug output
    async with app.run_test() as pilot:
        ...
```

### Print app state

```python
async def test_debug_state(self) -> None:
    async with LogViewerApp().run_test() as pilot:
        await pilot.press("/")
        
        # Print current state
        print(f"Focused: {pilot.app.focused}")
        print(f"Screen stack: {pilot.app.screen_stack}")
        
        # Use assert False to see output
        assert False, "Debug stop"
```

### Slow down interactions

```python
import asyncio

async def test_with_delay(self) -> None:
    async with LogViewerApp().run_test() as pilot:
        await pilot.press("/")
        await asyncio.sleep(0.5)  # Pause to observe
        await pilot.press("enter")
```
