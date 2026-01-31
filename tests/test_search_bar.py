"""Tests for the search bar widget."""

from __future__ import annotations

from json_logs_viewer.models import SearchHistory, SearchHistoryEntry
from json_logs_viewer.search_bar import SearchBarOverlay, SearchBarWidget


class TestSearchBarWidget:
    """Tests for the SearchBarWidget."""

    def test_basic_creation(self) -> None:
        """Test creating a search bar widget."""
        history = SearchHistory()
        widget = SearchBarWidget(search_history=history)

        assert widget._search_history is history
        assert widget._input is None  # Not mounted yet
        assert widget._history_dropdown is None

    def test_creation_with_callbacks(self) -> None:
        """Test creating a search bar with callbacks."""
        calls: list[str] = []

        def on_search(query: str) -> None:
            calls.append(f"search:{query}")

        def on_cancel() -> None:
            calls.append("cancel")

        widget = SearchBarWidget(
            search_history=SearchHistory(),
            on_search=on_search,
            on_cancel=on_cancel,
        )

        assert widget._on_search is on_search
        assert widget._on_cancel is on_cancel

    def test_show_hide_visibility(self) -> None:
        """Test showing and hiding the search bar."""
        widget = SearchBarWidget()

        # Initially not visible
        assert not widget.is_visible()

        # Show it
        widget.show()
        assert widget.is_visible()
        assert "visible" in widget.classes

        # Hide it
        widget.hide()
        assert not widget.is_visible()
        assert "visible" not in widget.classes

    def test_query_management(self) -> None:
        """Test getting and setting the search query."""
        widget = SearchBarWidget()

        # Before mount, input should return empty
        assert widget.get_query() == ""

        # After mounting (simulated), we can set query
        # But we can't fully test this without actual Textual mounting

    def test_add_to_history_on_submit(self) -> None:
        """Test that searches are added to history."""
        history = SearchHistory()
        search_calls: list[str] = []

        def on_search(query: str) -> None:
            search_calls.append(query)

        widget = SearchBarWidget(
            search_history=history,
            on_search=on_search,
        )

        # Simulate setting query and submitting
        mock_input = type(
            "MockInput", (), {"value": "test query", "blur": lambda self: None}
        )()
        widget._input = mock_input  # type: ignore[assignment]

        widget._submit_search()

        assert len(history.entries) == 1
        assert history.entries[0].query == "test query"
        assert history.entries[0].execution_count == 1

    def test_search_callback_invoked(self) -> None:
        """Test that search callback is invoked on submit."""
        history = SearchHistory()
        search_calls: list[str] = []

        def on_search(query: str) -> None:
            search_calls.append(query)

        widget = SearchBarWidget(
            search_history=history,
            on_search=on_search,
        )

        widget._input = type(
            "MockInput", (), {"value": "my search", "blur": lambda self: None}
        )()  # type: ignore[assignment]
        widget._submit_search()

        assert search_calls == ["my search"]

    def test_cancel_callback_invoked(self) -> None:
        """Test that cancel callback is invoked."""
        cancel_calls: list[str] = []

        def on_cancel() -> None:
            cancel_calls.append("cancelled")

        widget = SearchBarWidget(
            search_history=SearchHistory(),
            on_cancel=on_cancel,
        )

        widget.action_cancel()

        assert cancel_calls == ["cancelled"]

    def test_empty_query_not_added_to_history(self) -> None:
        """Test that empty queries are not added to history."""
        history = SearchHistory()

        widget = SearchBarWidget(search_history=history)
        mock_input = type(
            "MockInput", (), {"value": "   ", "blur": lambda self: None}
        )()  # Whitespace only
        widget._input = mock_input  # type: ignore[assignment]

        widget._submit_search()

        # Empty/whitespace queries should not be added to history
        assert len(history.entries) == 0

    def test_history_navigation_setup(self) -> None:
        """Test that history navigation is set up correctly."""
        history = SearchHistory()
        history.add(query="query1")
        history.add(query="query2")
        history.add(query="query3")

        widget = SearchBarWidget(search_history=history)

        # Initially no history visible
        assert widget._history_index == -1
        assert not widget.history_visible


class TestSearchBarWidgetWithHistory:
    """Tests for history-specific functionality."""

    def test_show_history(self) -> None:
        """Test showing history dropdown."""
        history = SearchHistory()
        history.add(query="first")
        history.add(query="second")

        widget = SearchBarWidget(search_history=history)

        # Simulate showing history
        widget._history_dropdown = type(  # type: ignore
            "MockListView",
            (),
            {
                "clear": lambda *args: None,
                "append": lambda *args: None,
                "add_class": lambda *args: None,
                "children": [],
            },
        )()

        widget._show_history()

        assert widget.history_visible
        assert len(widget._history_entries) == 2

    def test_format_history_entry(self) -> None:
        """Test formatting of history entries."""
        widget = SearchBarWidget()

        # Entry with count = 1
        entry1 = SearchHistoryEntry(query="simple query", execution_count=1)
        formatted1 = widget._format_history_entry(entry1)
        assert formatted1 == "simple query"

        # Entry with count > 1
        entry2 = SearchHistoryEntry(query="frequent query", execution_count=5)
        formatted2 = widget._format_history_entry(entry2)
        assert formatted2 == "frequent query (5x)"

    def test_history_navigation_up(self) -> None:
        """Test navigating up through history."""
        history = SearchHistory()
        history.add(query="first")
        history.add(query="second")
        history.add(query="third")

        widget = SearchBarWidget(search_history=history)
        widget._input = type(  # type: ignore
            "MockInput",
            (),
            {"value": "", "cursor_position": 0, "blur": lambda self: None},
        )()

        # Simulate showing history and navigating
        widget._history_entries = list(history.entries)
        widget._history_dropdown = type(  # type: ignore
            "MockListView",
            (),
            {
                "index": None,
                "clear": lambda *args: None,
                "append": lambda *args: None,
                "add_class": lambda *args: None,
                "children": [],
            },
        )()

        # First up press - should show history and select first
        widget.action_history_up()
        assert widget.history_visible
        assert widget._history_index >= 0

    def test_history_select_item(self) -> None:
        """Test selecting a history item."""
        history = SearchHistory()
        history.add(query="selected query")

        widget = SearchBarWidget(search_history=history)
        widget._input = type(  # type: ignore
            "MockInput",
            (),
            {"value": "", "cursor_position": 0},
        )()

        widget._history_entries = list(history.entries)
        widget._select_history_item(0)

        assert widget._input.value == "selected query"  # type: ignore
        assert widget._input.cursor_position == len("selected query")  # type: ignore


class TestSearchBarOverlay:
    """Tests for SearchBarOverlay."""

    def test_basic_creation(self) -> None:
        """Test creating the overlay."""
        overlay = SearchBarOverlay()

        assert overlay._search_bar is not None

    def test_show_hide_overlay(self) -> None:
        """Test showing and hiding the overlay."""
        overlay = SearchBarOverlay()

        # The overlay uses the search bar's visibility
        assert not overlay.is_visible()

        overlay.show()
        assert overlay.is_visible()

        overlay.hide()
        assert not overlay.is_visible()

    def test_overlay_passes_callbacks(self) -> None:
        """Test that overlay passes callbacks to search bar."""
        calls: list[str] = []

        def on_search(query: str) -> None:
            calls.append(f"search:{query}")

        overlay = SearchBarOverlay(on_search=on_search)

        assert overlay._search_bar._on_search is on_search


class TestSearchHistoryIntegration:
    """Tests for search history integration."""

    def test_duplicate_queries_increment_count(self) -> None:
        """Test that duplicate queries increment execution count."""
        history = SearchHistory()

        search_calls: list[str] = []

        def on_search(query: str) -> None:
            search_calls.append(query)

        widget = SearchBarWidget(
            search_history=history,
            on_search=on_search,
        )

        # Submit same query twice
        widget._input = type(  # type: ignore
            "MockInput", (), {"value": "same query", "blur": lambda self: None}
        )()
        widget._submit_search()

        widget._input.value = "same query"  # type: ignore
        widget._submit_search()

        assert len(history.entries) == 1
        assert history.entries[0].query == "same query"
        assert history.entries[0].execution_count == 2

    def test_recent_queries_retrieval(self) -> None:
        """Test getting recent queries from history."""
        history = SearchHistory()

        for i in range(15):
            history.add(query=f"query_{i}")

        recent = history.get_recent(count=10)

        assert len(recent) == 10
        assert recent[0].query == "query_14"
        assert recent[9].query == "query_5"

    def test_history_respects_max_size(self) -> None:
        """Test that history respects max size."""
        history = SearchHistory(max_size=5)

        for i in range(10):
            history.add(query=f"query_{i}")

        assert len(history.entries) == 5
        assert history.entries[0].query == "query_9"
        assert history.entries[4].query == "query_5"
