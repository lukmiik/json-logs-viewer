"""Unit tests for add_to_history."""

from json_logs_viewer.widgets.search_bar import add_to_history


def test_appends_new_query() -> None:
    assert add_to_history(history=["a"], query="b", limit=10) == ["a", "b"]


def test_repeated_query_moves_to_end() -> None:
    result = add_to_history(history=["a", "b", "c"], query="a", limit=10)
    assert result == ["b", "c", "a"]


def test_consecutive_repeat_is_unchanged() -> None:
    assert add_to_history(history=["a", "b"], query="b", limit=10) == [
        "a",
        "b",
    ]


def test_limit_drops_oldest() -> None:
    result = add_to_history(history=["a", "b", "c"], query="d", limit=3)
    assert result == ["b", "c", "d"]


def test_returns_new_list() -> None:
    history = ["a"]
    result = add_to_history(history=history, query="b", limit=10)
    assert result is not history
    assert history == ["a"]
