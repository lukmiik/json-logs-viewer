"""Writing files atomically: what happens to links and existing files."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from json_logs_viewer.atomic_file import atomic_open


def _write(path: Path, text: str) -> None:
    with atomic_open(path=path) as file:
        file.write(text)


def test_writing_through_a_symlink_updates_its_target(tmp_path: Path) -> None:
    """Dotfile managers (chezmoi, stow) keep files behind symlinks."""
    target = tmp_path / "real" / "history.json"
    target.parent.mkdir()
    target.write_text("old")
    link = tmp_path / "history.json"
    link.symlink_to(target)

    _write(link, "new")

    assert link.is_symlink()
    assert target.read_text() == "new"
    assert sorted(p.name for p in target.parent.iterdir()) == ["history.json"]


def test_a_dangling_symlink_creates_its_target(tmp_path: Path) -> None:
    target = tmp_path / "missing.json"
    link = tmp_path / "link.json"
    link.symlink_to(target)

    _write(link, "new")

    assert link.is_symlink()
    assert target.read_text() == "new"


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


@pytest.mark.skipif(os.name != "posix", reason="POSIX file modes")
class TestPermissions:
    def test_replacing_a_file_keeps_its_mode(self, tmp_path: Path) -> None:
        path = tmp_path / "export.jsonl"
        path.write_text("old")
        path.chmod(0o644)

        _write(path, "new")

        assert _mode(path) == 0o644

    def test_a_new_file_follows_the_umask(self, tmp_path: Path) -> None:
        old = os.umask(0o027)
        try:
            _write(tmp_path / "new.jsonl", "x")
        finally:
            os.umask(old)
        assert _mode(tmp_path / "new.jsonl") == 0o640

    def test_a_new_file_can_ask_for_a_private_mode(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "history.json"
        with atomic_open(path=path, new_file_mode=0o600) as file:
            file.write("x")
        assert _mode(path) == 0o600
