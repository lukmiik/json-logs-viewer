# Ralph Tasks

## Project: json-logs-viewer

### Objective

Build a keyboard-centric Textual TUI for viewing JSON/JSONL logs with follow mode,
filtering, and detail view.

### Decisions

- Search syntax: field:value with AND/OR operators
- Theme: catppuccin_mocha
- Single file only
- No non-JSON fallback
- No export feature
- Modifiers: ctrl_only
- Follow mode: cli_and_tui_toggleable
- Testing: tdd_alongside_code

---

## Tasks

- [ ] **T1: Define core data models**
    - Create LogEntry, FilterState, SearchHistoryEntry with full typing and keyword-only
      args
    - Write unit tests alongside
      <promise>READY_FOR_NEXT_TASK</promise>

- [ ] **T2: Implement JSON/JSONL parser**
    - Load file, detect JSON vs JSONL, parse safely, collect invalid lines as skipped
    - Include parser tests
      <promise>READY_FOR_NEXT_TASK</promise>

- [ ] **T3: Create file watcher for follow mode**
    - Track file offset, append new lines, batch UI updates, handle rotation
    - Support --follow CLI flag
    - Include watcher tests
      <promise>READY_FOR_NEXT_TASK</promise>

- [ ] **T4: Build base Textual app shell**
    - App class, screens wiring, Ctrl-only keybindings, Catppuccin Mocha theme CSS
    - CLI argument parsing for --follow
      <promise>READY_FOR_NEXT_TASK</promise>

- [ ] **T5: Implement main log list widget**
    - Scrollable list with level colors, selection, and keyboard navigation
    - Include UI tests
      <promise>READY_FOR_NEXT_TASK</promise>

- [ ] **T6: Implement detail view widget**
    - Formatted JSON view with navigation between entries
    - Include UI tests
      <promise>READY_FOR_NEXT_TASK</promise>

- [ ] **T7: Implement query parser and filter engine**
    - Parse field:value tokens, AND/OR operators, negation, quoted values, numeric
      compare, and apply filters
    - Include filter tests
      <promise>READY_FOR_NEXT_TASK</promise>

- [ ] **T8: Add search bar with history**
    - Input widget, history dropdown, persistence, navigation through history
    - Include tests
      <promise>READY_FOR_NEXT_TASK</promise>

- [ ] **T9: Add level filter bar**
    - Toggle buttons, counts, keyboard shortcuts 1-5/0
    - Include tests
      <promise>READY_FOR_NEXT_TASK</promise>

- [ ] **T10: Add clipboard copy functionality**
    - Copy formatted JSON or raw log line with success toast
    - Include tests
      <promise>READY_FOR_NEXT_TASK</promise>

- [ ] **T11: Integrate follow mode behavior**
    - Auto-scroll when following; pause on manual scroll
    - Toggle via Ctrl+T
    - Include UI tests
      <promise>READY_FOR_NEXT_TASK</promise>

- [ ] **T12: Add GitHub Actions CI**
    - Create GitHub Actions workflow for running pytest and Textual tests on push/PR
      <promise>READY_FOR_NEXT_TASK</promise>

---