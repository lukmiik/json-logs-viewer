# Architecture Guidelines

## Overview

This document describes the architecture of the JSON Logs Viewer TUI application. The architecture prioritizes simplicity for the MVP with all data stored in memory.

## Design Principles

1. **Simplicity First**: Everything stored in memory, no persistence between sessions
2. **Reactive UI**: Textual's reactive system for state management
3. **Keyboard-Centric**: Vim-like keybindings throughout
4. **Modular Components**: Clear separation between UI, business logic, and data

## Architecture Layers

```
┌─────────────────────────────────────────┐
│              UI Layer                   │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ │
│  │LogList  │ │Detail    │ │Search    │ │
│  │(DataTable)│ │(Modal)   │ │(Input)   │ │
│  └─────────┘ └──────────┘ └────┬─────┘ │
│                                │        │
│  ┌─────────────────────────────▼──────┐ │
│  │ HistoryModal (OptionList)          │ │
│  │ - Searchable list of past queries  │ │
│  │ - Built-in filtering capability    │ │
│  └────────────────────────────────────┘ │
└────────────┬────────────────────────────┘
             │ Reactive Updates
┌────────────▼────────────────────────────┐
│         Application State               │
│  ┌─────────────────────────────────┐   │
│  │  logs: list[LogEntry]           │   │
│  │  filtered_logs: list[LogEntry]  │   │
│  │  filter_query: str              │   │
│  │  columns: list[str]             │   │
│  │  selected_index: int            │   │
│  │  follow_mode: bool              │   │
│  │  search_history: list[str]      │   │
│  └─────────────────────────────────┘   │
└────────────┬────────────────────────────┘
             │
┌────────────▼────────────────────────────┐
│         File Watcher                    │
│  watchdog observer → new lines          │
│  → parse JSON → append to logs          │
└─────────────────────────────────────────┘
```

## Data Model

### LogEntry (Pydantic Model)

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Any

class LogEntry(BaseModel):
    """Represents a single log entry."""
    line_number: int
    raw_line: str
    data: dict[str, Any]
    
    # Common fields with aliases for flexibility
    timestamp: datetime | None = Field(None, alias="time")
    level: str | None = Field(None, alias="severity")
    message: str | None = None
    
    class Config:
        extra = "allow"
```

We use **Pydantic v2** instead of dataclasses because:
- Automatic JSON parsing and validation
- Flexible field aliases (e.g., `time` → `timestamp`)
- Type coercion (strings to datetime)
- Better error handling for malformed logs

### AppState

Central reactive state container:

```python
from textual.reactive import reactive

class AppState:
    """Reactive application state."""
    logs: reactive[list[LogEntry]] = reactive([])
    filtered_logs: reactive[list[LogEntry]] = reactive([])
    filter_query: reactive[str] = reactive("")
    columns: reactive[list[str]] = reactive(["timestamp", "level"])
    selected_index: reactive[int] = reactive(0)
    follow_mode: reactive[bool] = reactive(False)
    search_history: reactive[list[str]] = reactive([])
```

## Filter Query Language

The filter syntax supports field:value pairs with boolean operators:

```
query ::= expression (('AND' | 'OR') expression)*
expression ::= ['NOT'] field ':' value | '(' query ')'
```

### Examples

- `level:ERROR` - Filter by log level
- `level:ERROR AND service:api` - Multiple conditions
- `NOT level:DEBUG` - Negation
- `(status:500 OR status:503) AND method:POST` - Grouping

### Implementation

Simple recursive descent parser that converts queries into filter functions:

```python
def parse_filter(query: str) -> Callable[[LogEntry], bool]:
    """Parse filter query and return filter function."""
    # Returns: lambda log: log.level == "ERROR" and log.data.get("service") == "api"
```

## Components

### 1. LogViewerApp (Main App)

Entry point and container:
- Holds AppState
- Manages screens and modals
- Registers command palette commands
- Handles global keybindings

### 2. LogList (DataTable Widget)

Main log display:
- Displays filtered_logs from AppState
- Configurable columns based on AppState.columns
- Virtual scrolling for performance
- Vim navigation (j/k, gg/G)

### 3. SearchBar (Input Widget)

Filter input with history:
- Text input for filter queries
- Real-time filtering on type
- History button opens HistoryModal
- `/` keybinding to focus

### 4. HistoryModal (OptionList Widget)

Search history browser using Textual's built-in OptionList:

**Features:**
- Displays past searches from AppState.search_history as selectable options
- Built-in search/filter capability within the OptionList itself
- Keyboard navigation with arrow keys
- Max 100 entries (in-memory only, no persistence between sessions)

**Usage:**
- Opened from SearchBar via history button or keybinding
- Type to filter history items in real-time
- Enter to select a query and apply it
- Esc to close without selection

**Implementation:**
```python
from textual.widgets import OptionList

class HistoryModal(ModalScreen):
    """Modal displaying search history with OptionList."""
    
    def compose(self) -> ComposeResult:
        yield OptionList(*self.app.state.search_history)
        
    def on_option_list_option_selected(self, event) -> None:
        """Handle selection from OptionList."""
        selected_query = event.option.prompt
        self.dismiss(selected_query)
```

### 5. DetailModal (Modal Screen)

Log detail view:
- Pretty-printed JSON with syntax highlighting
- Copy buttons (single log, with context)
- Navigation to next/previous log (j/k)
- Opened with Enter from LogList

### 6. StatusBar

Bottom information bar:
- Current file name
- Follow mode indicator
- Filter status
- Help hints

## File Watching

Simple watchdog-based file monitoring:

```python
class LogWatcher:
    """Watches log file for new entries."""
    
    def __init__(self, filepath: str, callback: Callable[[LogEntry], None]):
        self.filepath = filepath
        self.callback = callback
        
    def start(self) -> None:
        """Start watching file for changes."""
        # Uses watchdog to monitor file
        # Reads new lines on modification
        # Parses each line as LogEntry
        # Calls callback with parsed entry
```

## Command Palette Integration

Textual's builtin command palette (`Ctrl+Shift+P`) provides quick access:

**Registered Commands:**
- `:open <file>` - Open log file
- `:follow` - Toggle follow mode
- `:columns` - Open column configuration
- `:clear` - Clear all logs (with confirmation)
- `:export` - Export filtered view to file
- `:quit` - Exit application

Commands prefixed with `:` for clarity vs search with `/`.

## Copy Operations

Clipboard integration using `pyperclip`:

1. **Copy Single**: Copy selected log as JSON
2. **Copy Multiple**: Select range with visual mode, copy
3. **Copy with Context**: Copy log + configurable context window

## Memory Management

**Current Approach (MVP):**
- All logs stored in memory as LogEntry objects
- Suitable for files up to ~100MB
- No caching or disk offloading

**Future Improvements:**
- LRU cache for memory efficiency
- SQLite index for large files
- Streaming with partial loading

## Keybindings

### Global
- `q` - Quit
- `Ctrl+C` - Quit
- `/` - Focus search
- `Ctrl+Shift+P` - Command palette

### Navigation (LogList)
- `j/↓` - Down
- `k/↑` - Up
- `gg` - Top
- `G` - Bottom
- `Enter` - Open detail view
- `y` - Copy current log

### Detail View
- `j` - Next log
- `k` - Previous log
- `y` - Copy current log
- `Y` - Copy with context
- `Esc/q` - Close

### Search
- `Enter` - Apply filter
- `↑/↓` - Navigate history
- `Tab` - Toggle case sensitivity (future)

## No Persistence

**Explicitly Out of Scope (MVP):**
- No settings file
- No search history persistence between sessions
- No column preference persistence between sessions
- No theme settings

All configuration is in-memory and resets on restart.

## Future Improvements (Post-MVP)

**Performance & Scale:**
- LRU cache for memory efficiency
- SQLite index for large files (>100MB)
- Streaming with partial loading
- Background indexing

**Persistence:**
- Settings file for preferences
- Search history persistence
- Column layout persistence

**Features:**
- Multiple file tabs
- Export formats (CSV, HTML)
- Custom themes
- Plugin system
