# JSON Logs Viewer Plan

## Overview
Build a keyboard-centric Textual TUI for viewing JSON/JSONL logs from a
single file, with real-time follow mode, vim-like navigation, field-based
filtering, level toggles, log detail view, clipboard copy, and search history.

## Goals
- JSON/JSONL log viewing from a single file path.
- Real-time updates (tail -f style) with toggleable follow mode.
- Vim-like navigation and keyboard-first workflows.
- Field:value query syntax for fast filtering.
- Quick level filters (ERROR/WARNING/INFO/DEBUG/TRACE).
- Main list view plus detailed JSON view.
- Copy selected log to clipboard.
- Temporal search history.
- Fully tested with Textual builtin testing and pytest.
- Catppuccin Mocha theme.

## Non-Goals
- Multiple file tabs or multi-source input.
- Non-JSON parsing or regex fallback for non-JSON logs.
- Export of filtered results.

## User Decisions
- Search syntax: field:value query.
- Theme: Catppuccin Mocha.
- Single file only.
- No regex fallback for non-JSON.
- No export feature.

## UX and Keybindings
### Keyboard Strategy
- Use only Ctrl modifiers for all shortcuts (no Alt variants).
- Vim-like navigation: j/k, g/G, h/l, / for search.
- Ctrl+ shortcuts for app-level actions.

### Core Bindings
- Quit: Ctrl+Q
- Search: Ctrl+F or /
- Copy selected log: Ctrl+C (formatted JSON)
- Toggle follow mode: Ctrl+T (can also be set via CLI with --follow flag)
- Navigate: j/k, Up/Down
- Page: Ctrl+F/Ctrl+B
- First/Last: g/G
- Detail view: Enter or l
- Back: Esc, h, or q
- Level toggles: 1-5 (ERROR/WARNING/INFO/DEBUG/TRACE), 0 = all
- Search history: Up/Down or Ctrl+P/Ctrl+N while in search

## Search and Filtering
- Query syntax: field:value tokens separated by spaces.
- Quoted values: message:"connection timeout".
- Negation: !level:debug or level:!debug.
- Exists: has:stacktrace.
- Numeric compare: duration:>1000.
- Default text search over all fields for tokens without field.
- Boolean operators: use AND, OR to combine filters (default is AND).
  - Example: level:error OR level:warning message:"timeout"

## Data Model
- LogEntry: raw line, parsed json, timestamp (optional), level, message,
  derived display fields.
- FilterState: raw query, parsed filters, enabled levels, case sensitivity.
- SearchHistory: recent queries with timestamps, max 100.

## Architecture
- Parser: detect JSON vs JSONL; parse lines safely; skip invalid lines.
- Watcher: track file position and append new lines while following.
- Filter engine: compile tokens to filter predicates; cache for reuse.
- UI: main screen with list + search bar + level bar + status bar.
- Detail screen: formatted JSON view for selected log.

## Theme (Catppuccin Mocha)
- Background: #1e1e2e
- Surface: #313244
- Text: #cdd6f4
- Accent: #fab387
- Border: #45475a
- Selection: #585b70
- ERROR: #f38ba8
- WARNING: #f9e2af
- INFO: #89b4fa
- DEBUG: #a6e3a1
- TRACE: #cba6f7

## Testing Strategy
- Tests written alongside code or before (TDD approach), not after.
- Unit tests for parser, filter, history, clipboard as features are built.
- Textual builtin tests for navigation, search, detail view, follow mode alongside UI development.
- Quality checks (ruff check --fix, ruff format, ty check) run after every code change, not as a separate phase.

## Implementation Phases
1. Foundation: models, parser, basic app skeleton + unit tests.
2. UI core: list view, detail view, navigation + UI tests.
3. Filtering: query parser, search bar, level bar + filter tests.
4. Follow mode: watcher, auto-scroll, status indicator + watcher tests.
5. History + copy: search history and clipboard + tests.
6. GitHub Actions: add CI workflow for automated testing.
