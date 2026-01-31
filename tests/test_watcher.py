"""Tests for file watcher module."""

from pathlib import Path

import pytest

from json_logs_viewer.models import LogEntry, LogLevel
from json_logs_viewer.parser import SkippedLine
from json_logs_viewer.watcher import (
    BatchProcessor,
    FileStats,
    FileWatcher,
    WatchResult,
)


class TestFileStats:
    """Tests for FileStats dataclass."""

    def test_basic_creation(self, tmp_path: Path) -> None:
        """Test creating FileStats with minimal fields."""
        file_path = tmp_path / "test.log"
        stats = FileStats(file_path=file_path)

        assert stats.file_path == file_path
        assert stats.file_size == 0
        assert stats.last_modified == 0.0
        assert stats.inode is None
        assert stats.is_tracked is False

    def test_full_creation(self, tmp_path: Path) -> None:
        """Test creating FileStats with all fields."""
        file_path = tmp_path / "test.log"
        stats = FileStats(
            file_path=file_path,
            file_size=1024,
            last_modified=1234567890.0,
            inode=12345,
            is_tracked=True,
        )

        assert stats.file_path == file_path
        assert stats.file_size == 1024
        assert stats.last_modified == 1234567890.0
        assert stats.inode == 12345
        assert stats.is_tracked is True


class TestWatchResult:
    """Tests for WatchResult dataclass."""

    def test_default_creation(self) -> None:
        """Test creating WatchResult with defaults."""
        result = WatchResult()

        assert result.new_entries == []
        assert result.skipped_lines == []
        assert result.file_rotated is False
        assert result.file_removed is False
        assert result.stats is None

    def test_full_creation(self) -> None:
        """Test creating WatchResult with all fields."""
        entry = LogEntry(
            raw_line='{"level": "info"}',
            parsed_data={"level": "info"},
            line_number=1,
        )
        skipped = SkippedLine(
            line_number=2,
            raw_line="invalid",
            error_message="parse error",
        )
        stats = FileStats(file_path=Path("/test.log"))

        result = WatchResult(
            new_entries=[entry],
            skipped_lines=[skipped],
            file_rotated=True,
            file_removed=True,
            stats=stats,
        )

        assert len(result.new_entries) == 1
        assert len(result.skipped_lines) == 1
        assert result.file_rotated is True
        assert result.file_removed is True
        assert result.stats == stats


class TestFileWatcher:
    """Tests for FileWatcher class."""

    @pytest.fixture
    def temp_dir(self, tmp_path: Path) -> Path:
        """Provide a temporary directory."""
        return tmp_path

    def test_watcher_initialization(self, temp_dir: Path) -> None:
        """Test FileWatcher initialization."""
        file_path = temp_dir / "test.log"
        watcher = FileWatcher(
            file_path=file_path,
            batch_size=50,
            poll_interval=0.5,
        )

        assert watcher.file_path == file_path
        assert watcher.is_following is False

    def test_start_watching_nonexistent_file(self, temp_dir: Path) -> None:
        """Test starting watch on non-existent file."""
        file_path = temp_dir / "nonexistent.log"
        watcher = FileWatcher(file_path=file_path)

        result = watcher.start_watching()
        assert result is None
        assert watcher.is_following is False

    def test_start_watching_existing_file(self, temp_dir: Path) -> None:
        """Test starting watch on existing file."""
        file_path = temp_dir / "test.log"
        file_path.write_text('{"level": "info", "message": "test"}\n')

        watcher = FileWatcher(file_path=file_path)
        stats = watcher.start_watching()

        assert stats is not None
        assert stats.is_tracked is True
        assert stats.file_size > 0
        assert stats.inode is not None
        assert watcher.is_following is True

    def test_stop_watching(self, temp_dir: Path) -> None:
        """Test stopping the file watcher."""
        file_path = temp_dir / "test.log"
        file_path.write_text('{"level": "info"}\n')

        watcher = FileWatcher(file_path=file_path)
        watcher.start_watching()
        assert watcher.is_following is True

        watcher.stop_watching()
        assert watcher.is_following is False

    def test_check_for_updates_empty_result(self, temp_dir: Path) -> None:
        """Test checking for updates with no new content."""
        file_path = temp_dir / "test.log"
        file_path.write_text('{"level": "info"}\n')

        watcher = FileWatcher(file_path=file_path, poll_interval=0.0)
        watcher.start_watching()

        # First check after start should return nothing (we start at EOF)
        result = watcher.check_for_updates()
        assert len(result.new_entries) == 0

    def test_check_for_updates_new_lines(self, temp_dir: Path) -> None:
        """Test detecting and reading new lines."""
        file_path = temp_dir / "test.log"
        file_path.write_text('{"level": "info", "message": "line1"}\n')

        watcher = FileWatcher(file_path=file_path, poll_interval=0.0)
        watcher.start_watching()

        # Append new line
        with file_path.open("a") as f:
            f.write('{"level": "error", "message": "line2"}\n')

        # Check for updates
        result = watcher.check_for_updates()

        assert len(result.new_entries) == 1
        assert result.new_entries[0].level == LogLevel.ERROR
        assert result.new_entries[0].message == "line2"
        assert result.file_removed is False
        assert result.file_rotated is False

    def test_check_for_updates_multiple_lines(self, temp_dir: Path) -> None:
        """Test reading multiple new lines."""
        file_path = temp_dir / "test.log"
        file_path.write_text('{"level": "info", "message": "line1"}\n')

        watcher = FileWatcher(file_path=file_path, poll_interval=0.0)
        watcher.start_watching()

        # Append multiple lines
        with file_path.open("a") as f:
            f.write('{"level": "error", "message": "line2"}\n')
            f.write('{"level": "warning", "message": "line3"}\n')

        result = watcher.check_for_updates()

        assert len(result.new_entries) == 2
        assert result.new_entries[0].level == LogLevel.ERROR
        assert result.new_entries[1].level == LogLevel.WARNING

    def test_check_for_updates_respects_poll_interval(
        self, temp_dir: Path
    ) -> None:
        """Test that poll interval is respected."""
        file_path = temp_dir / "test.log"
        file_path.write_text('{"level": "info"}\n')

        watcher = FileWatcher(file_path=file_path, poll_interval=1.0)
        watcher.start_watching()

        # First check
        watcher.check_for_updates()

        # Append line
        with file_path.open("a") as f:
            f.write('{"level": "error"}\n')

        # Immediate second check should return empty due to poll interval
        result = watcher.check_for_updates()
        assert len(result.new_entries) == 0

    def test_check_for_updates_file_removed(self, temp_dir: Path) -> None:
        """Test detecting file removal."""
        file_path = temp_dir / "test.log"
        file_path.write_text('{"level": "info"}\n')

        watcher = FileWatcher(file_path=file_path, poll_interval=0.0)
        watcher.start_watching()
        assert watcher.is_following is True

        # Remove the file
        file_path.unlink()

        result = watcher.check_for_updates()

        assert result.file_removed is True

    def test_check_for_updates_file_tracked_after_removal(
        self, temp_dir: Path
    ) -> None:
        """Test that is_tracked is False after file removal."""
        file_path = temp_dir / "test.log"
        file_path.write_text('{"level": "info"}\n')

        watcher = FileWatcher(file_path=file_path, poll_interval=0.0)
        watcher.start_watching()

        file_path.unlink()
        result = watcher.check_for_updates()

        assert result.stats is not None
        assert result.stats.is_tracked is False

    def test_check_for_updates_file_reappears(self, temp_dir: Path) -> None:
        """Test handling file that reappears after removal."""
        file_path = temp_dir / "test.log"
        file_path.write_text('{"level": "info"}\n')

        watcher = FileWatcher(file_path=file_path, poll_interval=0.0)
        watcher.start_watching()

        # Remove and recreate
        file_path.unlink()
        watcher.check_for_updates()

        file_path.write_text('{"level": "error", "message": "new content"}\n')
        result = watcher.check_for_updates()

        # Should detect as file rotation (different inode)
        assert result.file_rotated is True
        assert len(result.new_entries) == 1
        assert result.new_entries[0].level == LogLevel.ERROR

    def test_batch_size_limit(self, temp_dir: Path) -> None:
        """Test that batch size limits the number of entries returned."""
        file_path = temp_dir / "test.log"
        file_path.write_text('{"level": "info", "message": "line1"}\n')

        watcher = FileWatcher(
            file_path=file_path, batch_size=2, poll_interval=0.0
        )
        watcher.start_watching()

        # Append 5 lines
        with file_path.open("a") as f:
            for i in range(5):
                f.write(f'{{"level": "info", "message": "line{i + 2}"}}\n')

        result = watcher.check_for_updates()

        # Should only get 2 entries due to batch size
        assert len(result.new_entries) == 2

    def test_get_current_stats(self, temp_dir: Path) -> None:
        """Test getting current file stats."""
        file_path = temp_dir / "test.log"
        file_path.write_text('{"level": "info"}\n')

        watcher = FileWatcher(file_path=file_path)
        assert watcher.get_current_stats() is None

        watcher.start_watching()
        stats = watcher.get_current_stats()

        assert stats is not None
        assert stats.file_path == file_path
        assert stats.file_size > 0

    def test_check_for_updates_with_invalid_lines(
        self, temp_dir: Path
    ) -> None:
        """Test handling invalid JSON lines during updates."""
        file_path = temp_dir / "test.log"
        file_path.write_text('{"level": "info"}\n')

        watcher = FileWatcher(file_path=file_path, poll_interval=0.0)
        watcher.start_watching()

        # Append valid and invalid lines
        with file_path.open("a") as f:
            f.write('{"level": "error"}\n')
            f.write("invalid json\n")
            f.write('{"level": "warning"}\n')

        result = watcher.check_for_updates()

        assert len(result.new_entries) == 2
        assert len(result.skipped_lines) == 1
        assert result.skipped_lines[0].line_number == 3  # Third new line


class TestBatchProcessor:
    """Tests for BatchProcessor class."""

    @pytest.fixture
    def temp_dir(self, tmp_path: Path) -> Path:
        """Provide a temporary directory."""
        return tmp_path

    def test_processor_initialization(self, temp_dir: Path) -> None:
        """Test BatchProcessor initialization."""
        file_path = temp_dir / "test.log"
        file_path.write_text('{"level": "info"}\n')

        watcher = FileWatcher(file_path=file_path)
        processor = BatchProcessor(watcher=watcher)

        assert processor.get_watcher() == watcher

    def test_process_once_no_updates(self, temp_dir: Path) -> None:
        """Test processing when no updates available."""
        file_path = temp_dir / "test.log"
        file_path.write_text('{"level": "info"}\n')

        watcher = FileWatcher(file_path=file_path, poll_interval=0.0)
        watcher.start_watching()

        processor = BatchProcessor(watcher=watcher)
        result = processor.process_once()

        assert result is False

    def test_process_once_with_entries_callback(self, temp_dir: Path) -> None:
        """Test processing with entries callback."""
        file_path = temp_dir / "test.log"
        file_path.write_text('{"level": "info"}\n')

        watcher = FileWatcher(file_path=file_path, poll_interval=0.0)
        watcher.start_watching()

        received_entries: list[LogEntry] = []

        def on_entries(entries: list[LogEntry]) -> None:
            received_entries.extend(entries)

        processor = BatchProcessor(watcher=watcher, on_entries=on_entries)

        # Append a line
        with file_path.open("a") as f:
            f.write('{"level": "error", "message": "test"}\n')

        result = processor.process_once()

        assert result is True
        assert len(received_entries) == 1
        assert received_entries[0].level == LogLevel.ERROR

    def test_process_once_with_skipped_callback(self, temp_dir: Path) -> None:
        """Test processing with skipped lines callback."""
        file_path = temp_dir / "test.log"
        file_path.write_text('{"level": "info"}\n')

        watcher = FileWatcher(file_path=file_path, poll_interval=0.0)
        watcher.start_watching()

        received_skipped: list[SkippedLine] = []

        def on_skipped(skipped: list[SkippedLine]) -> None:
            received_skipped.extend(skipped)

        processor = BatchProcessor(watcher=watcher, on_skipped=on_skipped)

        # Append invalid line
        with file_path.open("a") as f:
            f.write("invalid json\n")

        result = processor.process_once()

        assert result is True
        assert len(received_skipped) == 1

    def test_process_once_with_rotation_callback(self, temp_dir: Path) -> None:
        """Test processing with rotation callback."""
        file_path = temp_dir / "test.log"
        file_path.write_text('{"level": "info"}\n')

        watcher = FileWatcher(file_path=file_path, poll_interval=0.0)
        watcher.start_watching()

        rotation_called = False

        def on_rotation() -> None:
            nonlocal rotation_called
            rotation_called = True

        processor = BatchProcessor(watcher=watcher, on_rotation=on_rotation)

        # Remove file and check to mark as untracked
        file_path.unlink()
        processor.process_once()  # Detects removal

        # Recreate file (simulates rotation)
        file_path.write_text('{"level": "error"}\n')
        result = processor.process_once()  # Detects rotation

        assert result is True
        assert rotation_called is True

    def test_process_once_with_removal_callback(self, temp_dir: Path) -> None:
        """Test processing with removal callback."""
        file_path = temp_dir / "test.log"
        file_path.write_text('{"level": "info"}\n')

        watcher = FileWatcher(file_path=file_path, poll_interval=0.0)
        watcher.start_watching()

        removal_called = False

        def on_removal() -> None:
            nonlocal removal_called
            removal_called = True

        processor = BatchProcessor(watcher=watcher, on_removal=on_removal)

        # Remove the file
        file_path.unlink()

        result = processor.process_once()

        assert result is True
        assert removal_called is True

    def test_process_once_multiple_callbacks(self, temp_dir: Path) -> None:
        """Test processing triggers multiple callbacks."""
        file_path = temp_dir / "test.log"
        file_path.write_text('{"level": "info"}\n')

        watcher = FileWatcher(file_path=file_path, poll_interval=0.0)
        watcher.start_watching()

        entries_called = False
        skipped_called = False

        def on_entries(entries: list[LogEntry]) -> None:
            nonlocal entries_called
            entries_called = True

        def on_skipped(skipped: list[SkippedLine]) -> None:
            nonlocal skipped_called
            skipped_called = True

        processor = BatchProcessor(
            watcher=watcher,
            on_entries=on_entries,
            on_skipped=on_skipped,
        )

        # Append valid and invalid lines
        with file_path.open("a") as f:
            f.write('{"level": "error"}\n')
            f.write("invalid json\n")

        result = processor.process_once()

        assert result is True
        assert entries_called is True
        assert skipped_called is True
