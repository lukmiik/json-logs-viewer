---
name: textual-tests
description: Testing patterns and best practices for Textual TUI applications. Use when writing tests for Textual apps, widgets, screens, or reactive state. Covers unit tests for business logic and UI integration tests using Textual's run_test() and Pilot API. Essential for TUI app testing.
---

# Textual Testing

## Setup

Dependencies:
```toml
[dependency-groups]
dev = ["pytest>=8.0", "pytest-asyncio>=0.21"]
```

pytest.ini:
```ini
[pytest]
asyncio_mode = auto
testpaths = tests
```

## Test Structure

```
tests/
├── conftest.py           # Shared fixtures
├── unit/                 # Business logic
│   ├── test_models.py
│   └── test_engine.py
└── integration/          # UI interactions
    ├── test_app.py
    └── test_widgets.py
```

## Unit Tests

Standard pytest for models, parsers, filters:

```python
def test_parse_valid_json() -> None:
    entry = LogEntry.from_line(1, '{"level": "ERROR"}')
    assert entry.level == "ERROR"

def test_filter_with_and_operator() -> None:
    filter_fn = parse_filter("level:ERROR AND service:api")
    assert filter_fn(error_api_log) is True
    assert filter_fn(error_web_log) is False
```

## UI Integration Tests

Use `run_test()` with async context manager:

```python
async def test_app_mounts() -> None:
    async with MyApp().run_test() as pilot:
        assert pilot.app.screen is not None

async def test_quit_keybinding() -> None:
    async with MyApp().run_test() as pilot:
        await pilot.press("q")
        assert pilot.app.is_running is False

async def test_navigation() -> None:
    async with MyApp().run_test() as pilot:
        pilot.app.state.items = [item1, item2]
        list_widget = pilot.app.query_one("#my-list")
        list_widget.focus()
        
        await pilot.press("j")
        assert list_widget.cursor_row == 1
        
        await pilot.press("k") 
        assert list_widget.cursor_row == 0
```

### Common Patterns

Press keys:
```python
await pilot.press("/")
await pilot.press(*list("search text"))  # Type string
await pilot.press("enter", "escape")
```

Query widgets:
```python
widget = pilot.app.query_one("#widget-id")
widget = pilot.app.query_one(DataTable)
focused = pilot.app.focused
```

Check state:
```python
assert pilot.app.state.filter_query == "level:ERROR"
assert len(pilot.app.screen_stack) == 2  # Modal open
```

Test modals:
```python
async def test_modal_opens() -> None:
    async with MyApp().run_test() as pilot:
        await pilot.press("enter")
        from textual.screen import ModalScreen
        assert isinstance(pilot.app.screen, ModalScreen)
        
        await pilot.press("escape")
        assert len(pilot.app.screen_stack) == 1
```

## Shared Fixtures

```python
# conftest.py
import pytest

@pytest.fixture
def sample_data():
    return [{"level": "INFO"}, {"level": "ERROR"}]

@pytest.fixture
def temp_file(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("content")
    return str(f)
```

## Best Practices

**Test state, not implementation:**
```python
# Good
assert pilot.app.state.value == "expected"

# Avoid
mock.assert_called_once()  # Too coupled
```

**Use descriptive names:**
```python
# Good
def test_filter_reduces_visible_items():

# Avoid  
def test_filter_1():
```

**Mock external dependencies:**
```python
from unittest.mock import Mock

def test_file_watcher(tmp_path):
    callback = Mock()
    watcher = FileWatcher(str(tmp_path / "file"), callback)
    # trigger change...
    assert callback.called
```

**Test edge cases:**
```python
def test_empty_input():
def test_invalid_json():
def test_unicode_content():
```

## Running Tests

```bash
uv run pytest                    # All tests
uv run pytest -v                 # Verbose
uv run pytest tests/unit/        # Specific directory
uv run pytest -k "test_filter"   # Pattern match
uv run pytest --cov=myapp        # With coverage
```

## Debugging

Enable debug mode:
```python
async def test_debug() -> None:
    app = MyApp()
    app.debug = True
    async with app.run_test() as pilot:
        await pilot.press("/")
        print(f"Focused: {pilot.app.focused}")
        assert False, "Debug stop"
```

Add delays:
```python
import asyncio
await asyncio.sleep(0.5)
```

## Code Quality

Always run after changes:
```bash
uv run ruff check --fix .
uv run ruff format .
uv run ty check
uv run pytest
```
