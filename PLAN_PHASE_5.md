# Phase 5: Filter Engine & Search - Implementation Plan

## Overview

Implement a recursive descent parser for a flexible filter query language with support
for full-text search, field-specific matching, boolean operators, and two display
modes (filter vs highlight). Filter toggles are located in the StatusBar.

## Query Grammar

| Syntax                      | Description                            |
|-----------------------------|----------------------------------------|
| `plain text`                | Full-text search across `data` field   |
| `field:`                    | Field exists check (matches any value) |
| `field:value`               | Field equals value (partial match)     |
| `field:"value with spaces"` | Quoted value with spaces               |
| `AND` / `OR`                | Boolean operators (case-insensitive)   |
| `NOT`                       | Negation                               |
| `()`                        | Grouping for precedence                |

### Examples

- `error` - Search for "error" in all fields
- `level:ERROR` - Match logs where level field contains "ERROR"
- `level:` - Match logs that have a level field (any value)
- `message:"error occurred"` - Match message containing "error occurred"
- `level:ERROR AND service:api` - Both conditions
- `level:ERROR OR level:WARN` - Either condition
- `NOT level:DEBUG` - Exclude debug logs
- `(level:ERROR OR level:WARN) AND service:api` - Grouped conditions

### Notes

- Field matching only searches `log_entry.data` dict (pre-normalized fields visible to
  user)
- Nested field paths not supported

## Architecture

### 1. Core FilterEngine (`filter_engine.py`)

#### Components

1. **FilterError Exception**
    - Raised for invalid query syntax
    - Displayed via toast notification

2. **Tokenizer**
    - Token types: FIELD, VALUE, QUOTED, AND, OR, NOT, LPAREN, RPAREN, EOF
    - Handles case-insensitive keywords (AND/OR/NOT)
    - Parses `field:value` as FIELD + VALUE tokens
    - Handles `field:"value"` with quoted values (unescaped double quotes)
    - Plain text without `:` becomes full-text search tokens

3. **AST Nodes** (Internal classes)
    - `FieldMatch`: field name and value pattern
    - `FieldExists`: field name only (empty value)
    - `FullText`: search pattern across all fields
    - `And`: left and right expressions
    - `Or`: left and right expressions
    - `Not`: child expression
    - `Group`: nested expression

4. **Parser (Recursive Descent)**
   Grammar with precedence:
   ```
   expr     → term (OR term)*
   term     → factor (AND factor)*
   factor   → NOT factor | primary
   primary  → fulltext | field_match | LPAREN expr RPAREN
   field_match → FIELD COLON (VALUE | QUOTED)?  (value is optional for existence check)
   fulltext → VALUE | QUOTED (when no colon present)
   ```

5. **Matcher Function**
    - Returns `Callable[[LogEntry], bool]`
    - Supports case sensitivity parameter
    - Implements field matching logic:
        - Check against `log_entry.data` dict keys only (pre-normalized fields)
        - Partial (substring) matching for values
        - Field existence check when value is empty
    - Implements full-text search:
        - Serialize entire log entry to string (like raw JSON log line)
        - Search within that single string

#### API

```python
def parse_filter(
        *,
        query: str,
        case_sensitive: bool = False,
) -> Callable[[LogEntry], bool]:
    """Parse filter query and return matcher function.
    
    Args:
        query: Filter query string
        case_sensitive: Whether matching is case-sensitive
        
    Returns:
        Function that takes LogEntry and returns True if it matches
        
    Raises:
        FilterError: If query syntax is invalid
    """
```

### 2. App State Updates (`app.py`)

Add to `LogViewerApp`:

```python
case_sensitive: reactive[bool] = reactive(False)
highlight_matches: reactive[bool] = reactive(False)
```

Update `apply_filter()`:

- Integrate with FilterEngine
- Handle FilterError with toast notification
- Support both filter and highlight modes

### 3. StatusBar Updates (`widgets/status_bar.py`)

**StatusInfo class:**

- Add two toggle buttons in StatusInfo:
    - **"Aa"** (case sensitivity): Shows active state when case-sensitive
    - **"Highlight"** (display mode): Shows active state when in highlight mode
- Buttons toggle corresponding app state reactives
- Default state: case-insensitive, filter mode

**Button behavior:**

- Click to toggle
- Visual feedback for active state
- Watch app state to stay synchronized

### 4. LogList Updates (`widgets/log_list.py`)

**When highlight mode is ON:**

- Display all logs (no filtering)
- Highlight matching text with color
- Dim non-matching rows (lower opacity)
- Match info passed from app

**Implementation:**

- New CSS classes: `.match` and `.no-match` for ListItems
- Highlight matching text spans
- Reactive updates when highlight mode or filter changes

**When filter mode is ON (default):**

- Current behavior: show only matching logs

### 5. Filter Integration (`app.py`)

```python
def apply_filter(self) -> None:
    """Apply current filter based on mode."""
    if not self.filter_query:
        self.filtered_logs = self.logs
        return

    try:
        matcher = parse_filter(
            query=self.filter_query,
            case_sensitive=self.case_sensitive,
        )

        if self.highlight_matches:
            # Show all logs, LogList handles highlighting
            self.filtered_logs = self.logs
        else:
            # Filter out non-matching logs
            self.filtered_logs = [log for log in self.logs if matcher(log)]

    except FilterError as e:
        self.notify(str(e), severity="error")
        self.filtered_logs = self.logs
```

## Implementation Order

1. **FilterEngine Core** (`filter_engine.py`)
    - Tokenizer
    - AST nodes
    - Parser
    - Matcher logic
    - FilterError

2. **Unit Tests** (`tests/unit/test_filter_engine.py`)
    - Test each token type
    - Test parser with various queries
    - Test matcher logic
    - Test case sensitivity
    - Test error handling

3. **App State Updates** (`app.py`)
    - Add new reactives
    - Update apply_filter()

4. **StatusBar Toggles** (`widgets/status_bar.py`)
    - Add toggle buttons
    - Connect to app state

5. **LogList Highlighting** (`widgets/log_list.py`)
    - Add CSS classes
    - Implement text highlighting
    - Dim non-matching rows

6. **Integration Tests** (`tests/integration/test_search.py`)
    - Test filter functionality
    - Test toggle buttons
    - Test highlight mode
    - Test case sensitivity

## Testing Strategy

### Unit Tests (`tests/unit/test_filter_engine.py`)

| Test Category    | Cases                             |
|------------------|-----------------------------------|
| Full-text search | Plain text matches any field      |
| Quoted strings   | `"text with spaces"` parsing      |
| Field matching   | `field:value`, partial match      |
| Quoted values    | `field:"value with spaces"`       |
| Field existence  | `field:` matches if field exists  |
| AND operator     | `a AND b` both must match         |
| OR operator      | `a OR b` either must match        |
| NOT operator     | `NOT a` negation                  |
| Grouping         | `(a OR b) AND c` precedence       |
| Case sensitivity | Toggle affects matching           |
| Complex queries  | Nested operators                  |
| Error handling   | Invalid syntax, unbalanced parens |

### Integration Tests (`tests/integration/test_search.py`)

| Test Category  | Cases                              |
|----------------|------------------------------------|
| SearchBar      | Input, focus, debouncing           |
| Filtering      | Real-time updates to LogList       |
| Toggle buttons | Case sensitivity, highlight mode   |
| Highlight mode | Visual feedback, text highlighting |
| Error display  | Toast on invalid query             |
| History        | Queries added on successful filter |

## Files to Create/Modify

### New Files

- `tests/unit/test_filter_engine.py`
- `tests/integration/test_search.py`

### Modified Files

- `src/json_logs_viewer/filter_engine.py` - Full implementation
- `src/json_logs_viewer/app.py` - Add reactives, integrate filter
- `src/json_logs_viewer/widgets/status_bar.py` - Add toggle buttons
- `src/json_logs_viewer/widgets/log_list.py` - Highlight mode support
- `src/json_logs_viewer/styles.tcss` - Add toggle and highlight styles

## UI Design

### StatusBar Toggles

```
[File: app.log] [Total: 1000] [Filtered: 42]  [Aa] [Highlight]
```

- **Aa**: Pressed/active state when case-sensitive
- **Highlight**: Pressed/active state when in highlight mode
- Both in-memory only (no persistence)

### Highlight Mode Visuals

**Matching row:**

- Normal opacity
- Matching text highlighted in yellow/orange

**Non-matching row:**

- Reduced opacity (e.g., 40%)
- No text highlighting

## Success Criteria

- [ ] All query syntax forms work correctly
- [ ] Plain text searches all fields
- [ ] `field:` checks field existence
- [ ] Boolean operators work with proper precedence
- [ ] Case sensitivity toggle affects matching
- [ ] Highlight mode shows all logs with visual indicators
- [ ] Filter mode (default) hides non-matching logs
- [ ] Invalid queries show error toast
- [ ] All tests pass
