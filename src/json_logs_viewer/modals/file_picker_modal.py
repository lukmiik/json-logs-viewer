from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import DirectoryTree

ALLOWED_EXTENSIONS: set[str] = {".json", ".jsonl"}
COMPRESSED_EXTENSIONS: set[str] = {".gz", ".bz2", ".xz"}


def is_log_file(path: Path) -> bool:
    """Whether the picker lists `path`, judged by its name.

    app.jsonl or app.json, or compressed like app.jsonl.gz and logrotate's
    app.jsonl.1.gz.
    """
    suffixes = path.suffixes
    if not suffixes:
        return False
    if suffixes[-1] in ALLOWED_EXTENSIONS:
        return True
    return suffixes[-1] in COMPRESSED_EXTENSIONS and any(
        suffix in ALLOWED_EXTENSIONS for suffix in suffixes[:-1]
    )


class FilteredDirectoryTree(DirectoryTree):
    """DirectoryTree filtering hidden and non-JSON files."""

    show_hidden: reactive[bool] = reactive(False)

    async def _reload_for_path(self) -> None:
        await super().watch_path()

    # Textual's async watch_path is left un-awaited ("coroutine was never
    # awaited") when the picker closes before it runs; a sync watcher that
    # schedules it avoids that.
    def watch_path(self) -> None:  # ty: ignore[incompatible-method-override]
        self.call_next(self._reload_for_path)

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return [
            path
            for path in paths
            if (self.show_hidden or not path.name.startswith("."))
            and (path.is_dir() or is_log_file(path))
        ]


@dataclass(frozen=True)
class PickedFile:
    """The picker's result: a file, and whether to add it to the open ones."""

    path: str
    add: bool = False


class FilePickerModal(ModalScreen[PickedFile | None]):
    """Modal screen for browsing the filesystem and selecting a file."""

    DEFAULT_CSS = """
    FilePickerModal {
        align: center middle;
        background: $background 70%;
    }

    FilePickerModal Vertical {
        background: $surface;
        width: 70%;
        height: 70%;
        border: heavy $block-cursor-background;
        padding: 1 2;
    }

    FilePickerModal DirectoryTree {
        height: 1fr;
        scrollbar-size: 1 1;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Close"),
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("up", "cursor_up", "Up", show=False),
        ("l", "expand_node", "Expand"),
        ("h", "collapse_node", "Collapse"),
        Binding("G", "scroll_end", "Bottom", show=False),
        (".", "toggle_hidden", "Toggle hidden"),
        ("a", "add_file", "Add to open"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="file-picker-dialog") as dialog:
            yield FilteredDirectoryTree(str(Path.cwd()), id="file-picker-tree")

        dialog.border_title = "Open File"
        dialog.border_subtitle = (
            "ENTER: open | a: add | h/l: collapse/expand | .: hidden | ESC"
        )

    def on_directory_tree_file_selected(
        self, event: DirectoryTree.FileSelected
    ) -> None:
        self.dismiss(PickedFile(path=str(event.path)))

    def action_add_file(self) -> None:
        """Open the highlighted file next to the ones already open."""
        node = self._get_tree().cursor_node
        if node is None or node.data is None or node.allow_expand:
            self.notify("Highlight a file to add", severity="warning")
            return
        self.dismiss(PickedFile(path=str(node.data.path), add=True))

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _get_tree(self) -> FilteredDirectoryTree:
        return self.query_one("#file-picker-tree", FilteredDirectoryTree)

    def action_cursor_down(self) -> None:
        self._get_tree().action_cursor_down()

    def action_cursor_up(self) -> None:
        self._get_tree().action_cursor_up()

    def action_expand_node(self) -> None:
        tree = self._get_tree()
        node = tree.cursor_node
        if node is not None and node.allow_expand and not node.is_expanded:
            node.expand()

    def action_collapse_node(self) -> None:
        tree = self._get_tree()
        node = tree.cursor_node
        if node is not None and node.is_expanded:
            node.collapse()
        elif node is not None and node.parent is not None:
            # Move to parent when already collapsed
            tree.move_cursor(node.parent)

    def action_scroll_end(self) -> None:
        self._get_tree().action_scroll_end()

    def action_toggle_hidden(self) -> None:
        tree = self._get_tree()
        tree.show_hidden = not tree.show_hidden
        tree.reload()
