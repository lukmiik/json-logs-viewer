from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import DirectoryTree

ALLOWED_EXTENSIONS: set[str] = {".json", ".jsonl"}


class FilteredDirectoryTree(DirectoryTree):
    """DirectoryTree filtering hidden and non-JSON files."""

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return [
            path
            for path in paths
            if not path.name.startswith(".")
            and (path.is_dir() or path.suffix in ALLOWED_EXTENSIONS)
        ]


class FilePickerModal(ModalScreen[str | None]):
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
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="file-picker-dialog") as dialog:
            yield FilteredDirectoryTree(str(Path.cwd()), id="file-picker-tree")

        dialog.border_title = "Open File"
        dialog.border_subtitle = (
            "ENTER: open | h/l: collapse/expand | ESC: cancel"
        )

    def on_directory_tree_file_selected(
        self, event: DirectoryTree.FileSelected
    ) -> None:
        self.dismiss(str(event.path))

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
