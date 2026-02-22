# Plan: `:open` Command with File Picker Modal

## Goal

Implement an `:open <file>` command that allows opening a log file at runtime via a
modal with a `DirectoryTree` file browser. When the app is launched without a file
argument, the file picker modal should open automatically on startup.

---

## Design

### New File: `src/json_logs_viewer/modals/file_picker_modal.py`

A `ModalScreen[str | None]` that lets the user browse and select a file.

**Layout:**

```
┌─── Open File ──────────────────────────────────┐
│  DirectoryTree (filtered, scrollable)          │
│    📁 src/                                     │
│    📁 logs/                                    │
│      📄 app.log                                │
│      📄 errors.jsonl                           │
│    📁 test_files/                              │
│      📄 sample.jsonl                           │
│                                                │
│  ENTER: open | ESC: cancel                     │
└────────────────────────────────────────────────┘
```

**Components:**

- `FilteredDirectoryTree` — subclass of `DirectoryTree` that:
  - Filters out hidden files/dirs (names starting with `.`)
  - Starts at the current working directory (`Path.cwd()`)
- Bindings:
  - `enter` on a file → dismiss with `str(path)`
  - `escape` → dismiss with `None`
- Handle `DirectoryTree.FileSelected` message to dismiss with the selected path
- Styling: reuse the same modal pattern as `ColumnsModal` (centered, semi-transparent
  overlay, bordered container)

**Signature:**

```python
class FilePickerModal(ModalScreen[str | None]):
    ...
```

---

### Changes to `src/json_logs_viewer/app.py`

#### 1. New action: `action_open_file`

```python
def action_open_file(self) -> None:
    """Open file picker modal."""
    self.push_screen(FilePickerModal(), callback=self._on_file_selected)
```

#### 2. Callback: `_on_file_selected`

```python
def _on_file_selected(self, filepath: str | None) -> None:
    """Handle file selection from picker."""
    if filepath is None:
        return
    # Stop follow mode if active (watching previous file)
    if self.follow_mode:
        self.follow_mode = False
    self.load_file(filepath=filepath)
```

#### 3. Register command in `get_system_commands`

```python
yield SystemCommand(
    "Open file",
    "Browse and open a log file",
    self.action_open_file,
)
```

#### 4. Add keybinding

```python
("o", "open_file", "Open"),
```

#### 5. Auto-open on startup (no file argument)

Update `on_mount` to push the file picker when no initial file is provided:

```python
def on_mount(self) -> None:
    self._update_search_bar_visibility()
    if self.initial_file:
        self.load_file(filepath=self.initial_file)
    else:
        # No file provided — open file picker immediately
        self.push_screen(FilePickerModal(), callback=self._on_file_selected)
    if self._initial_follow:
        self.follow_mode = True
```

#### 6. Update `load_file` for re-opening

`load_file` already handles the full load flow. Minor adjustments:

- Instead of `self.exit(message=...)` on errors, use `self.notify(..., severity="error")`
  so the app stays running (user can pick another file)
- Reset follow-mode state (`_follow_offset`, `_last_line_number`, etc.) when loading a
  new file

#### 7. Update CLI argument

Make `file` argument optional (already is — `nargs="?"`) — no change needed.

---

### Styling

Add to `FilePickerModal.DEFAULT_CSS` (inline, same pattern as `ColumnsModal`):

```css
FilePickerModal {
    align: center middle;
    background: $background 70%;
}

FilePickerModal Vertical {
    background: $surface;
    width: 60%;
    height: 70%;
    border: heavy $block-cursor-background;
    padding: 1 2;
}

FilePickerModal DirectoryTree {
    height: 1fr;
}
```

---

## Implementation Steps

1. **Create `FilePickerModal`** in `src/json_logs_viewer/modals/file_picker_modal.py`
   - `FilteredDirectoryTree` subclass (filter hidden files)
   - Modal layout with `DirectoryTree` inside a `Vertical` container
   - Handle `DirectoryTree.FileSelected` → dismiss with path string
   - `escape` → dismiss with `None`

2. **Update `app.py`**
   - Import `FilePickerModal`
   - Add `action_open_file` method
   - Add `_on_file_selected` callback
   - Add keybinding `("o", "open_file", "Open")`
   - Register `SystemCommand` in `get_system_commands`
   - Update `on_mount` to auto-open picker when no file provided
   - Change `load_file` error handling from `self.exit()` to `self.notify()` so the
     app stays alive for re-picking

3. **Update `modals/__init__.py`** — no change needed (no re-exports used)

4. **Tests**
   - `tests/unit/test_file_picker_modal.py`:
     - Test modal mounts with DirectoryTree
     - Test hidden files are filtered
     - Test FileSelected dismisses with path string
     - Test escape dismisses with None
   - `tests/integration/test_open_command.py`:
     - Test `o` key opens file picker modal
     - Test command palette "Open file" command
     - Test selecting a file loads it into the app
     - Test app starts with picker when no file argument given
     - Test opening a new file replaces current logs
     - Test follow mode is stopped when opening a new file

---

## Edge Cases

- **Opening while follow mode is active**: stop watcher before loading new file
- **Invalid file selected** (not JSON): show toast error, keep app running
- **Empty directory**: DirectoryTree handles this natively
- **Large directories**: DirectoryTree loads lazily (built-in behavior)
- **Cancel on startup**: app stays open with empty log list (user can press `o` again)
