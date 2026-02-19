# Phase 9: Column Customization - Implementation Plan

## Goal

Allow users to customize displayed columns with the raw JSON log always visible on the right, and user-selected fields displayed on the left.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Base widget | Keep ScrollView | Efficient virtual scrolling, wrap mode support, full render control |
| Column width | Auto-sized | Calculate from visible content for cleaner display |
| Keybinding | `C` (uppercase) | Consistent with existing patterns (H, Y) |
| Nested fields | Top-level only | Simpler MVP; nested paths = future enhancement |

---

## Architecture

### Data Model

```python
# Reactive state in app.py
columns: reactive[list[str]] = reactive(list)  # Empty = default (raw JSON only)
```

### Visual Layout

**Default (no columns):**
```
{"level":"ERROR","timestamp":"2024-01-15T10:30:00","message":"Connection failed","service":"api"}
```

**With columns `level`, `timestamp`:**
```
ERROR | 2024-01-15T10:30:00 | {"level":"ERROR","timestamp":"2024-01-15T10:30:00","message":"Connection failed",...}
INFO  | 2024-01-15T10:30:01 | {"level":"INFO","timestamp":"2024-01-15T10:30:01","message":"Request received",...}
```

---

## Implementation Steps

### Step 1: Add Column State (`app.py`)

Add new reactive state:

```python
columns: reactive[list[str]] = reactive(list)  # Empty = default (raw JSON only)
```

### Step 2: Add Field Discovery (`app.py`)

```python
from collections import Counter

def discover_fields(self) -> list[str]:
    """Find common field names across all logs, return top 20 by frequency."""
    if not self.logs:
        return []
    field_counts: Counter[str] = Counter()
    for log in self.logs:
        field_counts.update(log.data.keys())
    return [f for f, _ in field_counts.most_common(20)]
```

### Step 3: Modify LogList Rendering (`widgets/log_list.py`)

#### 3.1 Add constants

```python
MAX_COL_WIDTH = 30  # Maximum width for auto-sized columns
COLUMN_SEPARATOR = " | "
```

#### 3.2 Add column width calculation

```python
def _calculate_column_widths(self) -> dict[str, int]:
    """Calculate auto-width for each column based on visible rows."""
    columns = self._app.columns
    if not columns:
        return {}
    
    widths = {col: len(col) for col in columns}  # Minimum = header width
    
    # Sample visible rows for width calculation
    scroll_y = self.scroll_offset.y
    visible_height = self.size.height if self.size.height > 0 else 50
    start_idx = max(0, scroll_y)
    end_idx = min(len(self._log_entries), scroll_y + visible_height)
    
    for i in range(start_idx, end_idx):
        if i >= len(self._log_entries):
            break
        log = self._log_entries[i]
        for col in columns:
            value = str(log.data.get(col, ""))
            widths[col] = max(widths[col], min(len(value), MAX_COL_WIDTH))
    
    return widths
```

#### 3.3 Add column change handler

```python
def _on_columns_changed(self, columns: list[str]) -> None:
    """Handle column configuration changes."""
    self._line_cache.clear()
    self._column_widths = self._calculate_column_widths()
    self._update_virtual_size()
    self.refresh()
```

#### 3.4 Update `on_mount` to watch columns

```python
def on_mount(self) -> None:
    # ... existing watches ...
    self.watch(self.app, "columns", self._on_columns_changed)
    self._column_widths: dict[str, int] = {}
```

#### 3.5 Update `render_line()` to render columns

```python
def render_line(self, y: int) -> Strip:
    """Render a single line — only called for visible lines."""
    scroll_x, scroll_y = self.scroll_offset

    if self._wrap_mode:
        return self._render_wrapped_line(y=y, scroll_y=scroll_y)

    line_index = y + scroll_y

    if line_index < 0 or line_index >= len(self._log_entries):
        return self._blank_strip()

    if line_index not in self._line_cache:
        log = self._log_entries[line_index]
        self._line_cache[line_index] = json.dumps(
            log.data, ensure_ascii=False
        )
    raw_json = self._line_cache[line_index]

    # Build column prefix
    columns = self._app.columns
    if columns:
        column_parts = []
        for col in columns:
            value = str(self._log_entries[line_index].data.get(col, ""))
            width = self._column_widths.get(col, len(col))
            truncated = value[:width]
            column_parts.append(truncated.ljust(width))
        text = COLUMN_SEPARATOR.join(column_parts) + COLUMN_SEPARATOR + raw_json
    else:
        text = raw_json

    is_highlighted = line_index == self._cursor_index
    if is_highlighted:
        style = self.get_component_rich_style("loglist--cursor")
    else:
        style = self._style_for_entry(
            entry_idx=line_index, base=self.rich_style or Style()
        )

    display_width = max(self._max_content_width + 2, self.size.width)
    padded = text.ljust(display_width)

    segments = [Segment(padded, style)]
    strip = Strip(segments, display_width)
    strip = strip.crop(scroll_x, scroll_x + self.size.width)
    return strip
```

#### 3.6 Update `_render_wrapped_line()` for wrap mode

Similar changes to include columns prefix before wrapped JSON.

#### 3.7 Update `_recalculate_wrap()` to account for column width

```python
def _recalculate_wrap(self) -> None:
    """Recalculate wrapped line mapping."""
    self._wrapped_lines = []
    self._entry_start_rows = {}

    width = self.size.width
    if width <= 0:
        return

    # Calculate column prefix width
    columns = self._app.columns
    column_width = 0
    if columns:
        col_widths = self._calculate_column_widths()
        column_width = sum(col_widths.values()) + len(COLUMN_SEPARATOR) * len(columns)
    
    content_width = max(1, width - column_width - 1)

    for entry_idx, log in enumerate(self._log_entries):
        if entry_idx not in self._line_cache:
            self._line_cache[entry_idx] = json.dumps(
                log.data, ensure_ascii=False
            )

    # ... rest of wrap calculation with adjusted content_width ...
```

### Step 4: Create ColumnsModal (`modals/columns_modal.py`)

```python
from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, SelectionList
from textual.widgets.selection_list import Selection

if TYPE_CHECKING:
    from json_logs_viewer.app import LogViewerApp


class ColumnsModal(ModalScreen[list[str] | None]):
    """Modal screen for selecting which fields to display as columns."""

    DEFAULT_CSS = """
    ColumnsModal {
        align: center middle;
        background: $background 70%;
    }

    ColumnsModal Vertical {
        background: $surface;
        width: 50%;
        height: auto;
        max-height: 80%;
        border: heavy $block-cursor-background;
        padding: 1 2;
    }

    ColumnsModal SelectionList {
        height: auto;
        max-height: 15;
    }

    ColumnsModal Horizontal {
        height: auto;
        margin-top: 1;
        align: center middle;
    }

    ColumnsModal Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Close"),
        ("enter", "apply", "Apply"),
        Binding("space", "toggle", "Toggle", show=False),
    ]

    @property
    def _app(self) -> LogViewerApp:
        return cast("LogViewerApp", self.app)

    def compose(self) -> ComposeResult:
        available = self._app.discover_fields()
        current = self._app.columns
        
        selections = [
            Selection(field, field, initial_state=(field in current))
            for field in available
        ]
        
        with Vertical(id="columns-dialog") as dialog:
            yield SelectionList(*selections, id="column-list")
            with Horizontal():
                yield Button("Reset to Default", id="reset")
                yield Button("Apply", id="apply", variant="primary")
        
        dialog.border_title = "Configure Columns"
        dialog.border_subtitle = "SPACE: toggle | ENTER: apply | ESC: cancel"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "apply":
            self._apply_selection()
        elif event.button.id == "reset":
            self.dismiss([])  # Empty list = reset to default

    def action_toggle(self) -> None:
        selection_list = self.query_one("#column-list", SelectionList)
        selection_list.action_select()

    def action_apply(self) -> None:
        self._apply_selection()

    def _apply_selection(self) -> None:
        selection_list = self.query_one("#column-list", SelectionList)
        selected = [selection.value for selection in selection_list.selected]
        self.dismiss(selected)

    def action_cancel(self) -> None:
        self.dismiss(None)
```

### Step 5: Update Modal Exports (`modals/__init__.py`)

```python
from json_logs_viewer.modals.columns_modal import ColumnsModal
from json_logs_viewer.modals.detail_modal import DetailModal
from json_logs_viewer.modals.history_modal import HistoryModal

__all__ = ["ColumnsModal", "DetailModal", "HistoryModal"]
```

### Step 6: App Integration (`app.py`)

#### 6.1 Add import

```python
from json_logs_viewer.modals.columns_modal import ColumnsModal
```

#### 6.2 Add binding

```python
BINDINGS = [
    # ... existing bindings ...
    ("C", "show_columns", "Columns"),
]
```

#### 6.3 Add action

```python
def action_show_columns(self) -> None:
    """Open column configuration modal."""
    if isinstance(self.screen, ColumnsModal):
        return
    self.push_screen(ColumnsModal(), callback=self._on_columns_selected)

def _on_columns_selected(self, columns: list[str] | None) -> None:
    """Handle column selection from modal."""
    if columns is None:
        return  # Cancelled
    self.columns = columns
```

#### 6.4 Add system command

```python
def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
    yield from super().get_system_commands(screen)
    # ... existing commands ...
    yield SystemCommand(
        "Configure columns",
        "Select which fields to display as columns",
        self.action_show_columns,
    )
```

---

## File Changes Summary

| File | Action | Description |
|------|--------|-------------|
| `src/json_logs_viewer/modals/columns_modal.py` | CREATE | Modal for column selection |
| `src/json_logs_viewer/modals/__init__.py` | MODIFY | Export ColumnsModal |
| `src/json_logs_viewer/widgets/log_list.py` | MODIFY | Column rendering logic |
| `src/json_logs_viewer/app.py` | MODIFY | State, actions, field discovery |
| `tests/unit/test_columns.py` | CREATE | Unit tests |
| `tests/integration/test_columns_modal.py` | CREATE | Integration tests |

---

## Testing

### Unit Tests (`tests/unit/test_columns.py`)

```python
def test_discover_fields_returns_top_20():
    """Test that discover_fields returns at most 20 fields."""
    # Create logs with 30 unique fields
    # Assert only top 20 by frequency are returned

def test_discover_fields_sorted_by_frequency():
    """Test that fields are sorted by occurrence count."""
    # Create logs with varying field frequencies
    # Assert order matches frequency (most common first)

def test_discover_fields_empty_logs():
    """Test discover_fields with no logs."""
    # Assert returns empty list

def test_column_width_calculation():
    """Test column width is calculated from visible content."""
    # Test min width = header width
    # Test max width cap at MAX_COL_WIDTH
```

### Integration Tests (`tests/integration/test_columns_modal.py`)

```python
async def test_columns_modal_opens_with_C_key():
    """Test that pressing C opens the columns modal."""

async def test_selection_list_displays_available_fields():
    """Test that the SelectionList shows discovered fields."""

async def test_selecting_fields_and_applying():
    """Test selecting fields and applying updates LogList rendering."""

async def test_reset_to_default_clears_columns():
    """Test that Reset button clears all columns."""

async def test_escape_cancels_without_changes():
    """Test that ESC dismisses modal without applying changes."""

async def test_columns_render_on_left_of_json():
    """Test that configured columns appear before raw JSON in LogList."""
```

---

## Edge Cases

1. **Missing field**: If a log entry doesn't have a configured field, show empty/padded space
2. **Empty columns list**: Default behavior - show only raw JSON (current state)
3. **Column width**: Min = field name length, Max = 30 characters
4. **Wrap mode**: Columns stay fixed on left; only raw JSON wraps
5. **No logs loaded**: `discover_fields()` returns empty list

---

## Constants

```python
# In constants.py
MAX_COL_WIDTH = 30  # Maximum width for auto-sized columns
COLUMN_SEPARATOR = " | "
```
