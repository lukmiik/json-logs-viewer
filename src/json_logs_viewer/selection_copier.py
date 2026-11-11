from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from json_logs_viewer.constants import SELECTION_COPY_DELAY

if TYPE_CHECKING:
    from textual.timer import Timer
    from textual.widget import Widget


class SelectionCopier:
    """Copy a text selection to the clipboard once it stops changing.

    The owning widget reports every selection change with `update`. While
    the user is still dragging or extending the selection the timer
    restarts, so only the final selection is copied. Clearing the
    selection before the delay cancels the copy.

    A helper object (composition) rather than a mixin: the search bar is an
    Input and the modals are screens, and this keeps the dependencies on the
    owner explicit and typed.
    """

    def __init__(
        self,
        *,
        owner: Widget,
        clear_selection: Callable[[], None],
        delay: float = SELECTION_COPY_DELAY,
    ) -> None:
        self._owner = owner
        self._clear_selection = clear_selection
        self._delay = delay
        self._timer: Timer | None = None
        self._text = ""

    def update(self, *, selected_text: str) -> None:
        """Report the current selection (empty when nothing is selected)."""
        if selected_text == self._text:
            return
        self._text = selected_text
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        if selected_text:
            self._timer = self._owner.set_timer(self._delay, self._copy)

    def _copy(self) -> None:
        self._timer = None
        text, self._text = self._text, ""
        self._owner.app.copy_to_clipboard(text)
        self._owner.notify("Copied selection to clipboard")
        self._clear_selection()
