# JSON Logs Viewer

A keyboard-centric TUI application for viewing and filtering JSON/JSONL logs, built with [Textual](https://textual.textualize.io/).

## Overview

This application provides a powerful, Vim-like interface for analyzing structured log files in real-time. Designed for developers and DevOps engineers who need to efficiently navigate, filter, and inspect JSON-formatted logs.

## Core Features

### Input & Real-time Updates
- **File Input**: Open JSON or JSONL log files from local filesystem
- **Follow Mode**: Real-time log streaming (`-f` flag) similar to `docker logs -f` or `tail -f`
- **Auto-refresh**: Automatically display new log entries as they are written

### Navigation & Keybindings
- **Vim-style Navigation**: Full keyboard control with intuitive Vim keybindings
  - `j/k` or `↑/↓` - Navigate up/down through log entries
  - `gg/G` - Jump to top/bottom
  - `/` - Open search
  - `q` - Quit
  - `Enter` - Open detailed view
  - Copy operations with keyboard shortcuts

### Search & Filtering
- **Search Bar**: Quick access with `/` key
  - Real-time filtering as you type
  - Field-based filtering with boolean operators
- **Filter Syntax**: `field:value` with AND, OR, NOT support
  - Examples: `level:ERROR`, `level:ERROR AND service:api`, `NOT level:DEBUG`
- **Quick Level Filter**: One-key filtering by log level (ERROR, WARN, INFO, DEBUG, etc.)
- **Search History**: Recent searches accessible via OptionList (in-memory only)

### Display & Layout
- **Main List View**: Truncated log lines in a scrollable table
  - Configurable columns: User-defined fields displayed as columns (e.g., timestamp on left)
  - Syntax highlighting for log levels
  - Line numbers
- **Detailed View**: Full JSON formatting with syntax highlighting
  - Pretty-printed JSON
  - Copy individual fields

### Column Customization
- Define custom columns from any JSON field
- Reorder columns via in-memory configuration
- Default columns: timestamp, level, message

### Copy Operations
- **Copy Single Log**: Copy entire log entry as JSON
- **Copy Multiple**: Select range of logs and copy
- **Copy with Context**: Copy selected log plus N logs before and after (configurable context window)
- **Copy to Clipboard**: System clipboard integration

### Log Management
- **Clear Logs**: Delete all logs from the file (with confirmation)
- **Export**: Save filtered view to new file

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed architecture documentation.

### High-Level Components
- **LogViewerApp**: Main Textual application container
- **LogList**: DataTable widget for log display
- **DetailModal**: Modal screen for detailed JSON view
- **SearchBar**: Filter input with history
- **HistoryModal**: OptionList for search history
- **LogWatcher**: File watching with follow capability
- **FilterEngine**: Query parser and filter functions

### Data Flow
1. LogWatcher monitors file for changes using watchdog
2. New lines parsed as LogEntry (Pydantic models)
3. Logs stored in AppState (in-memory)
4. Filter query applied via FilterEngine
5. Filtered results displayed in LogList
6. Reactive updates propagate automatically

### Command Line Interface

```bash
json-logs-viewer <file>          # Open file
json-logs-viewer <file> -f       # Follow mode
```

### Command Palette

Access with `Ctrl+Shift+P`:
- `:open <file>` - Open log file
- `:follow` - Toggle follow mode
- `:columns` - Configure columns
- `:clear` - Clear all logs
- `:quit` - Exit

## Dependencies

- **textual**: TUI framework
- **rich**: Syntax highlighting and formatting
- **pydantic**: Data validation and JSON parsing
- **pyperclip**: Clipboard operations
- **watchdog**: File change monitoring (follow mode)

## Testing

All features tested with:
- **Textual builtin testing**: UI interactions, navigation, keybindings
- **pytest**: Unit tests for filter engine, log parsing, file operations

## Future Enhancements

- LRU cache for memory efficiency with large files
- Persistent search history
- Persistent column preferences
- Multiple file tabs
- Log aggregation from multiple sources
- Custom color themes
- Plugin system for custom parsers
- Export to different formats (CSV, HTML)
- Performance optimizations for large files (>1GB)
