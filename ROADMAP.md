# Implementation Roadmap

This roadmap outlines the phased implementation of the JSON Logs Viewer application,
organized by dependencies and logical progression.

**Testing Approach**: Tests are written alongside implementation. Each phase includes
specific test deliverables that must be completed as part of that phase.

---

## Phase 1: Foundation & Project Setup

**Goal**: Establish the project structure and core dependencies.

- [x] Initialize Python project with `uv`
- [x] Install core dependencies:
    - `textual` (TUI framework)
    - `rich` (syntax highlighting)
    - `pydantic` (data validation)
    - `pyperclip` (clipboard)
    - `watchdog` (file watching)
- [x] Install dev dependencies:
    - `pytest`, `pytest-asyncio`
    - `ruff` (linting/formatting)
    - `ty` (type checking)
- [x] Create project directory structure:
  ```
  json_logs_viewer/
  ├── __init__.py
  ├── models.py
  ├── app.py
  ├── widgets/
  │   ├── __init__.py
  │   ├── log_list.py
  │   ├── search_bar.py
  │   └── status_bar.py
  ├── modals/
  │   ├── __init__.py
  │   ├── detail_modal.py
  │   └── history_modal.py
  ├── filter_engine.py
  └── log_watcher.py
  tests/
  ├── __init__.py
  ├── conftest.py
  ├── unit/
  └── integration/
  ```
- [x] Configure `pytest.ini` in `pyproject.toml`
- [x] Set up code quality tools (ruff, ty)
- [x] **Tests**: Verify pytest runs with empty test suite

**Deliverable**: Working project scaffold that passes linting and type checks.

---

## Phase 2: Data Models & State Management

**Goal**: Implement core data structures and reactive state.

- [x] **LogEntry Model** (`models.py`):
    - Pydantic BaseModel with fields:
        - `line_number: int`
        - `data: dict[str, Any]` (parsed JSON data)
        - `timestamp: datetime | None` (auto-detected from: Timestamp, timestamp, time,
          ts, Time, @t)
        - `level: str | None` (auto-detected from: SeverityText, severity, level,
          log_level, Level, loglevel)
        - `message: str | None` (auto-detected from: message, msg, Message, body, event,
          @m)
    - `model_validator(mode="before")` extracts normalized fields before validation using priority-ordered field lists
    - Constructor accepts `line_number` and `data` (dict) directly
    - Returns normalized dict with extracted fields for Pydantic validation

**Testing**:

- [ ] `tests/unit/test_log_entry.py`
    - Test field auto-detection (timestamp from various names, level from various names)
    - Test edge cases (empty JSON, null values)
    - Test `_find_first` helper function with keyword arguments
- [ ] Ensure 100% coverage for models module

**Deliverable**: Data models with unit tests for LogEntry parsing.

---

## Phase 3: File Loading & Basic Display

**Goal**: Load log files and display them in a basic table.

- [ ] **LogViewerApp** (`app.py`):
    - Main Textual App class
    - Initialize AppState
    - Compose method with basic layout
    - Command-line argument parsing (`<file>`, `-f` flag)
    - Method to load file contents into AppState.logs

- [ ] **LogList Widget** (`widgets/log_list.py`):
    - Extend DataTable
    - Display logs from AppState.filtered_logs
    - Configurable columns based on AppState.columns
    - React to state changes (logs, columns, filter changes)
    - Line numbers in first column

- [ ] **Basic CSS**:
    - Minimal styling for DataTable
    - Focus indicators

- [ ] **File Loading**:
    - Read file line by line
    - Parse each line as LogEntry
    - Handle JSON parse errors gracefully
    - Initial load on app start from CLI argument

**Testing**:

- [ ] `tests/integration/test_app.py`
    - Test app mounts successfully
    - Test quit keybinding
    - Test file loading from CLI
- [ ] `tests/integration/test_log_list.py`
    - Test logs displayed in DataTable
    - Test column configuration
    - Test reactive updates when logs change

**Deliverable**: Can open a JSON/JSONL file and display logs in a scrollable table.

---

## Phase 4: Navigation & Keybindings

**Goal**: Implement Vim-style navigation for the log list.

- [ ] **LogList Navigation**:
    - `j` / `↓` - Move down
    - `k` / `↑` - Move up
    - `gg` - Jump to top (first log)
    - `G` - Jump to bottom (last log)
    - `Enter` - Open detail view (placeholder)
    - `q` - Quit application

- [ ] **Global Keybindings**:
    - `Ctrl+C` - Quit
    - `/` - Focus search (placeholder, just focus)
    - `Ctrl+Shift+P` - Command palette

- [ ] **StatusBar Widget** (`widgets/status_bar.py`):
    - Current file name
    - Total log count / filtered count
    - Current position (line X of Y)
    - Follow mode indicator (placeholder)
    - Help hints

**Testing**:

- [ ] Extend `tests/integration/test_log_list.py`
    - Test `j`/`k` navigation moves cursor
    - Test `gg` jumps to top
    - Test `G` jumps to bottom
    - Test `Enter` opens detail modal
    - Test `q` quits application

**Deliverable**: Fully navigable log list with keyboard controls.

---

## Phase 5: Filter Engine & Search

**Goal**: Implement query parsing and log filtering.

- [ ] **FilterEngine** (`filter_engine.py`):
    - Query grammar:
        - `field:value` - Field matching
        - `AND` / `OR` - Boolean operators
        - `NOT` - Negation
        - `()` - Grouping
    - Recursive descent parser
    - `parse_filter(*, query: str) -> Callable[[LogEntry], bool]`
    - `FilterError` exception for invalid queries

- [ ] **SearchBar Widget** (`widgets/search_bar.py`):
    - Input widget with placeholder
    - History button (opens HistoryModal)
    - Real-time filtering on type (debounced)
    - Submit filter to AppState.filter_query
    - Show validation errors

- [ ] **Filter Integration**:
    - Watch AppState.filter_query changes
    - Recompute filtered_logs when query changes
    - Update LogList display
    - Add successful queries to search_history

- [ ] **Quick Level Filters** (optional):
    - Keybindings for common filters (e.g., `1` for ERROR, `2` for WARN)

**Testing**:

- [ ] `tests/unit/test_filter_engine.py`
    - Test simple field:value matching
    - Test AND operator
    - Test OR operator
    - Test NOT operator
    - Test grouping with parentheses
    - Test invalid query error handling
- [ ] `tests/integration/test_search.py`
    - Test search bar input and focus
    - Test real-time filtering updates LogList
    - Test search history updates

**Deliverable**: Can filter logs with field:value syntax and boolean operators.

---

## Phase 6: Detail View Modal

**Goal**: Display full JSON for selected log entry.

- [ ] **DetailModal** (`modals/detail_modal.py`):
    - ModalScreen for log detail view
    - Pretty-printed JSON with syntax highlighting (Rich JSON)
    - Navigation: `j` (next log), `k` (previous log)
    - Close: `Esc`, `q`
    - Copy buttons (placeholder for Phase 8)
    - Context window display

- [ ] **Integration**:
    - `Enter` in LogList opens DetailModal
    - Pass selected LogEntry to modal
    - Update AppState.selected_index on navigation
    - Modal reacts to index changes

**Testing**:

- [ ] `tests/integration/test_detail_modal.py`
    - Test Enter opens detail modal
    - Test modal displays pretty-printed JSON
    - Test `j`/`k` navigates between logs
    - Test `Esc`/`q` closes modal

**Deliverable**: Can view full JSON details of any log entry with keyboard navigation.

---

## Phase 7: Search History Modal

**Goal**: Browse and reuse previous searches.

- [ ] **HistoryModal** (`modals/history_modal.py`):
    - Extend ModalScreen
    - OptionList displaying AppState.search_history
    - Built-in filtering/search within the list
    - Max 100 entries (in-memory only)
    - Select with Enter, dismiss with selected query
    - Cancel with Escape

- [ ] **Integration**:
    - History button in SearchBar opens modal
    - Selected query populates SearchBar and applies filter
    - Add query to history only when filter is applied successfully

**Testing**:

- [ ] `tests/integration/test_history_modal.py`
    - Test history button opens modal
    - Test OptionList displays search history
    - Test selecting query applies filter
    - Test Escape closes without selection

**Deliverable**: Can access and reuse previous search queries.

---

## Phase 8: Copy Operations

**Goal**: Copy log entries to clipboard.

- [ ] **Clipboard Integration**:
    - Copy single log: `y` in LogList or DetailModal
    - Copy with context: `Y` in DetailModal (configurable N logs before/after)
    - Format as pretty-printed JSON

- [ ] **Copy with Context**:
    - Configuration for context window size (default: 5)
    - Get logs from AppState.logs (not filtered_logs for context)
    - Handle edge cases (beginning/end of file)

- [ ] **Feedback**:
    - Toast notification on successful copy
    - Error handling for clipboard failures

**Testing**:

- [ ] Unit tests for clipboard operations
    - Test single log copy formats correctly
    - Test copy with context includes N surrounding logs
    - Test edge cases (beginning/end of file)
- [ ] Integration tests for copy keybindings (may require mocking clipboard)

**Deliverable**: Can copy logs to system clipboard with optional context.

---

## Phase 9: Column Customization

**Goal**: Allow users to customize displayed columns.

- [ ] **Column Configuration UI**:
    - Command palette command: `:columns`
    - Modal or inline interface to:
        - Add/remove columns from available fields
        - Reorder columns
        - Preview changes

- [ ] **Field Discovery**:
    - Scan existing logs for common fields
    - Show available fields for column selection

- [ ] **Persistence** (in-memory only for MVP):
    - Store in AppState.columns
    - Apply immediately to LogList
    - Reset to defaults option

**Testing**:

- [ ] Unit tests for column configuration
    - Test adding/removing columns
    - Test column reordering
    - Test field discovery from logs
- [ ] Integration tests for column UI

**Deliverable**: Can customize which fields appear as columns in the log list.

---

## Phase 10: Follow Mode & File Watching

**Goal**: Real-time log updates from file changes.

- [ ] **LogWatcher** (`log_watcher.py`):
    - Watchdog-based file monitoring
    - Track file position to read only new lines
    - Callback system for new LogEntry
    - Handle file truncation/rotation (optional)
    - Constructor:
      `__init__(self, *, filepath: str, callback: Callable[[LogEntry], None])`

- [ ] **Follow Mode Integration**:
    - CLI flag `-f` / `--follow`
    - Command palette: `:follow` toggle
    - Auto-scroll to bottom when new logs arrive (if at bottom)
    - Pause follow when user scrolls up, resume on manual scroll to bottom
    - Visual indicator in StatusBar

- [ ] **Performance**:
    - Debounced updates for high-frequency changes
    - Batch multiple new lines

**Testing**:

- [ ] `tests/unit/test_log_watcher.py`
    - Test file watching detects new lines
    - Test callback triggered with LogEntry
    - Test file position tracking
    - Test debouncing/batching
- [ ] Integration tests for follow mode UI
    - Test follow toggle updates state
    - Test auto-scroll behavior

**Deliverable**: Can monitor log files in real-time with follow mode.

---

## Phase 11: Command Palette Commands

**Goal**: Full command palette integration.

- [ ] **Register Commands**:
    - `:open <file>` - Open log file
    - `:follow` - Toggle follow mode
    - `:columns` - Configure columns
    - `:clear` - Clear all logs (with confirmation modal)
    - `:export` - Export filtered view
    - `:quit` - Exit

- [ ] **Command Handlers**:
    - Implement each command's functionality
    - File picker for `:open` (if possible, or text input)
    - Confirmation modal for `:clear`

**Testing**:

- [ ] Integration tests for each command
    - Test `:open` command
    - Test `:follow` toggle
    - Test `:columns` opens configuration
    - Test `:clear` shows confirmation
    - Test `:quit` exits

**Deliverable**: Full command palette with all documented commands.

---

## Phase 12: Log Management Features

**Goal**: Advanced log operations.

- [ ] **Clear Logs**:
    - `:clear` command
    - Confirmation modal
    - Truncate file on disk (optional, dangerous)
    - Or just clear in-memory view

- [ ] **Export**:
    - `:export` command
    - Save filtered_logs to new JSONL file
    - File picker or input for filename
    - Use `json.dumps()` to serialize `data` field back to JSON

**Testing**:

- [ ] Unit tests for export functionality
    - Test filtered logs export to JSONL
    - Test export uses json.dumps() on data field
- [ ] Integration tests for log management
    - Test clear command shows confirmation modal
    - Test clear removes logs from state

**Deliverable**: Can clear logs and export filtered results.

---

## Phase 13: Polish & Styling

**Goal**: Professional appearance and user experience.

- [ ] **Syntax Highlighting**:
    - Color-coded log levels (ERROR=red, WARN=yellow, INFO=green, DEBUG=blue)
    - JSON syntax highlighting in DetailModal
    - Timestamp formatting

- [ ] **UI Polish**:
    - Consistent spacing and borders
    - Loading indicators for large files
    - Error modals for invalid operations
    - Help screen/modal (? key)

- [ ] **Accessibility**:
    - Clear focus indicators
    - Keyboard shortcuts reference

**Testing**:

- [ ] Visual/styling tests where applicable
    - Test syntax highlighting colors applied
    - Test log level colors (ERROR=red, etc.)
- [ ] Tests for help modal
- [ ] Run full test suite and ensure >80% coverage
- [ ] Manual testing with real-world log files
- [ ] Update documentation

**Deliverable**: Polished, professional UI with consistent styling.

---

## Phase 14: Future Enhancements (Post-MVP)

Features planned for future releases:

- [ ] **Performance**:
    - LRU cache for memory efficiency
    - SQLite index for large files
    - Streaming/partial loading
    - Background indexing

- [ ] **Persistence**:
    - Settings file for preferences
    - Persistent search history
    - Persistent column layouts

- [ ] **Advanced Features**:
    - Multiple file tabs
    - Log aggregation from multiple sources
    - Custom color themes
    - Plugin system for custom parsers
    - Export to CSV, HTML
    - Performance metrics dashboard

---

## Implementation Order Summary

| Phase                   | Priority | Effort | Dependencies |
|-------------------------|----------|--------|--------------|
| 1. Foundation           | P0       | Low    | None         |
| 2. Data Models          | P0       | Low    | Phase 1      |
| 3. File Loading         | P0       | Medium | Phase 2      |
| 4. Navigation           | P0       | Medium | Phase 3      |
| 5. Filter Engine        | P0       | High   | Phase 4      |
| 6. Detail View          | P0       | Medium | Phase 4      |
| 7. History Modal        | P1       | Low    | Phase 5      |
| 8. Copy Operations      | P1       | Low    | Phase 6      |
| 9. Column Customization | P1       | Medium | Phase 3      |
| 10. Follow Mode         | P0       | High   | Phase 3      |
| 11. Command Palette     | P1       | Medium | Various      |
| 12. Log Management      | P2       | Medium | Phase 11     |
| 13. Polish              | P1       | Medium | All above    |
| 14. Future              | P3       | -      | -            |

**Legend**: P0 = Critical, P1 = Important, P2 = Nice to have, P3 = Future

---

## Getting Started

To begin implementation:

1. Start with **Phase 1** to set up the project
2. Implement **Phase 2** (models) before any UI work - write the tests as you implement
3. Complete **Phases 3-6** for a usable MVP (file loading, navigation, filtering, detail
   view)
4. Add **Phase 10** (follow mode) for the core real-time feature
5. Iterate on **Phases 7-13** for feature completeness
6. **Tests are written as the code is implemented** - never leave testing for the end

**Golden Rule**: Each phase must include its tests. No phase is complete without passing
tests.
