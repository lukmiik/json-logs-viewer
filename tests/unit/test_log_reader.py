"""Unit tests for log_reader module."""

from pathlib import Path

from json_logs_viewer.log_reader import read_lines_backward


class TestReadLinesBackward:
    """Tests for read_lines_backward function."""

    def test_reads_lines_in_reverse_order(self, tmp_path: Path) -> None:
        """Test that lines are yielded from end to beginning."""
        log_file = tmp_path / "test.jsonl"
        log_file.write_text("line1\nline2\nline3\n", encoding="utf-8")

        result = list(read_lines_backward(filepath=log_file))

        assert len(result) == 3
        assert result[0] == (3, "line3")
        assert result[1] == (2, "line2")
        assert result[2] == (1, "line1")

    def test_correct_line_numbers(self, tmp_path: Path) -> None:
        """Test that line numbers correspond to original file positions."""
        log_file = tmp_path / "test.jsonl"
        log_file.write_text("first\nsecond\nthird\n", encoding="utf-8")

        result = list(read_lines_backward(filepath=log_file))

        line_numbers = [ln for ln, _ in result]
        assert line_numbers == [3, 2, 1]

    def test_empty_file(self, tmp_path: Path) -> None:
        """Test that empty file yields nothing."""
        log_file = tmp_path / "empty.jsonl"
        log_file.write_text("", encoding="utf-8")

        result = list(read_lines_backward(filepath=log_file))

        assert result == []

    def test_file_with_empty_lines_skipped(self, tmp_path: Path) -> None:
        """Test that empty lines are skipped."""
        log_file = tmp_path / "test.jsonl"
        log_file.write_text("line1\n\nline3\n\n", encoding="utf-8")

        result = list(read_lines_backward(filepath=log_file))

        assert len(result) == 2
        assert result[0] == (3, "line3")
        assert result[1] == (1, "line1")

    def test_single_line_no_trailing_newline(self, tmp_path: Path) -> None:
        """Test file with single line and no trailing newline."""
        log_file = tmp_path / "single.jsonl"
        log_file.write_text("only line", encoding="utf-8")

        result = list(read_lines_backward(filepath=log_file))

        assert len(result) == 1
        assert result[0] == (1, "only line")

    def test_single_line_with_trailing_newline(self, tmp_path: Path) -> None:
        """Test file with single line and trailing newline."""
        log_file = tmp_path / "single.jsonl"
        log_file.write_text("only line\n", encoding="utf-8")

        result = list(read_lines_backward(filepath=log_file))

        assert len(result) == 1
        assert result[0] == (1, "only line")

    def test_unicode_content(self, tmp_path: Path) -> None:
        """Test that Unicode content is handled correctly."""
        log_file = tmp_path / "unicode.jsonl"
        log_file.write_text("hello 你好\nworld 🌍\n", encoding="utf-8")

        result = list(read_lines_backward(filepath=log_file))

        assert len(result) == 2
        assert result[0] == (2, "world 🌍")
        assert result[1] == (1, "hello 你好")

    def test_carriage_return_stripped(self, tmp_path: Path) -> None:
        """Test that carriage return characters are stripped."""
        log_file = tmp_path / "crlf.jsonl"
        log_file.write_text("line1\r\nline2\r\n", encoding="utf-8")

        result = list(read_lines_backward(filepath=log_file))

        assert result[0] == (2, "line2")
        assert result[1] == (1, "line1")

    def test_large_file(self, tmp_path: Path) -> None:
        """Test reading a larger file."""
        log_file = tmp_path / "large.jsonl"
        lines = [
            f'{{"id": {i}, "message": "log entry {i}"}}' for i in range(1, 101)
        ]
        log_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

        result = list(read_lines_backward(filepath=log_file))

        assert len(result) == 100
        assert result[0][0] == 100
        assert result[0][1] == lines[99]
        assert result[99][0] == 1
        assert result[99][1] == lines[0]

    def test_lines_with_special_characters(self, tmp_path: Path) -> None:
        """Test lines containing special characters."""
        log_file = tmp_path / "special.jsonl"
        log_file.write_text(
            '{"key": "value with spaces"}\n{"key": "value\twith\ttabs"}\n',
            encoding="utf-8",
        )

        result = list(read_lines_backward(filepath=log_file))

        assert len(result) == 2
        assert "tabs" in result[0][1]
        assert "spaces" in result[1][1]

    def test_file_without_final_newline(self, tmp_path: Path) -> None:
        """Test file that doesn't end with newline."""
        log_file = tmp_path / "no_final_newline.jsonl"
        log_file.write_text("first\nsecond\nthird", encoding="utf-8")

        result = list(read_lines_backward(filepath=log_file))

        assert len(result) == 3
        assert result[0] == (3, "third")
        assert result[1] == (2, "second")
        assert result[2] == (1, "first")
