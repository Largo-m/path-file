"""Tests for directory synchronization."""

from __future__ import annotations

from pathlib import Path

import pytest

from path_file.exceptions import SyncConflictError
from path_file.sync import IgnoreMatcher, sync


class TestIgnoreMatcher:
    """Test gitignore-style pattern matching."""

    def test_simple_pattern(self):
        matcher = IgnoreMatcher(["*.tmp"])
        assert matcher.match(Path("file.tmp")) is True
        assert matcher.match(Path("file.txt")) is False

    def test_directory_pattern(self):
        matcher = IgnoreMatcher(["build/"])
        assert matcher.match(Path("build"), is_dir=True) is True
        assert matcher.match(Path("build/file.txt")) is True
        assert matcher.match(Path("src/build"), is_dir=False) is False

    def test_negation(self):
        matcher = IgnoreMatcher(["*.tmp", "!important.tmp"])
        assert matcher.match(Path("file.tmp")) is True
        assert matcher.match(Path("important.tmp")) is False

    def test_load_from_file(self, tmp_dir: Path):
        ignore_file = tmp_dir / ".syncignore"
        ignore_file.write_text("*.tmp\nbuild/\n!important.tmp\n")

        matcher = IgnoreMatcher()
        matcher.load_file(ignore_file)

        assert matcher.match(Path("file.tmp")) is True
        assert matcher.match(Path("important.tmp")) is False


class TestSyncerBasic:
    """Test basic sync operations."""

    def test_sync_source_to_dest(self, tmp_dir: Path):
        src = tmp_dir / "src"
        dest = tmp_dir / "dest"
        src.mkdir()
        dest.mkdir()

        (src / "file1.txt").write_text("content 1")
        (src / "file2.txt").write_text("content 2")

        syncer = sync(src, dest).direction("source_to_dest")
        diff = syncer.compare()

        assert len(diff.to_add) == 2
        assert len(diff.to_update) == 0
        assert len(diff.to_delete) == 0

    def test_sync_detects_modified(self, tmp_dir: Path):
        src = tmp_dir / "src"
        dest = tmp_dir / "dest"
        src.mkdir()
        dest.mkdir()

        (src / "file.txt").write_text("original")
        (dest / "file.txt").write_text("original")

        syncer = sync(src, dest).direction("source_to_dest")
        diff = syncer.compare()

        assert len(diff.unchanged) == 1

        # Modify source
        (src / "file.txt").write_text("modified")

        diff = syncer.compare()
        assert len(diff.to_update) == 1

    def test_sync_delete_extras(self, tmp_dir: Path):
        src = tmp_dir / "src"
        dest = tmp_dir / "dest"
        src.mkdir()
        dest.mkdir()

        (src / "keep.txt").write_text("keep")
        (dest / "keep.txt").write_text("keep")
        (dest / "extra.txt").write_text("delete me")

        syncer = sync(src, dest).direction("source_to_dest").delete_extras(True)
        diff = syncer.compare()

        assert "extra.txt" in [str(p) for p in diff.to_delete]


class TestSyncerBidirectional:
    """Test bidirectional sync."""

    def test_bidirectional_conflict(self, tmp_dir: Path):
        src = tmp_dir / "src"
        dest = tmp_dir / "dest"
        src.mkdir()
        dest.mkdir()

        (src / "conflict.txt").write_text("source version")
        (dest / "conflict.txt").write_text("dest version")

        syncer = sync(src, dest).direction("bidirectional")
        diff = syncer.compare()

        assert len(diff.conflicts) == 1

    def test_bidirectional_no_conflict(self, tmp_dir: Path):
        src = tmp_dir / "src"
        dest = tmp_dir / "dest"
        src.mkdir()
        dest.mkdir()

        (src / "only_src.txt").write_text("src")
        (dest / "only_dest.txt").write_text("dest")
        (src / "same.txt").write_text("identical")
        (dest / "same.txt").write_text("identical")

        syncer = sync(src, dest).direction("bidirectional")
        diff = syncer.compare()

        assert len(diff.conflicts) == 0


class TestSyncerIgnore:
    """Test sync ignore patterns."""

    def test_ignore_pattern(self, tmp_dir: Path):
        src = tmp_dir / "src"
        dest = tmp_dir / "dest"
        src.mkdir()
        dest.mkdir()

        (src / "file.txt").write_text("keep")
        (src / "temp.tmp").write_text("ignore")

        syncer = sync(src, dest).direction("source_to_dest").ignore(["*.tmp"])
        diff = syncer.compare()

        assert len(diff.to_add) == 1
        assert "temp.tmp" not in [str(p) for p in diff.to_add]

    def test_ignore_file(self, tmp_dir: Path):
        src = tmp_dir / "src"
        dest = tmp_dir / "dest"
        src.mkdir()
        dest.mkdir()

        (src / "file.txt").write_text("keep")
        (src / "temp.tmp").write_text("ignore")
        (src / "build").mkdir()
        (src / "build" / "output.bin").write_text("binary")

        ignore_file = src / ".syncignore"
        ignore_file.write_text("*.tmp\nbuild/\n.syncignore\n")

        syncer = sync(src, dest).direction("source_to_dest").ignore_file(ignore_file)
        diff = syncer.compare()

        assert len(diff.to_add) == 1
        assert "file.txt" in [str(p) for p in diff.to_add]


class TestSyncerExecute:
    """Test sync execution."""

    def test_execute_dry_run(self, tmp_dir: Path):
        src = tmp_dir / "src"
        dest = tmp_dir / "dest"
        src.mkdir()
        dest.mkdir()

        (src / "new.txt").write_text("new")

        syncer = sync(src, dest).direction("source_to_dest").dry_run(True)
        result = syncer.execute()

        assert result.dry_run
        assert result.count == 1
        assert not (dest / "new.txt").exists()

    def test_execute_real(self, tmp_dir: Path):
        src = tmp_dir / "src"
        dest = tmp_dir / "dest"
        src.mkdir()
        dest.mkdir()

        (src / "new.txt").write_text("new content")

        syncer = sync(src, dest).direction("source_to_dest").dry_run(False)
        result = syncer.execute()

        assert result.success()
        assert result.count == 1
        assert (dest / "new.txt").exists()
        assert (dest / "new.txt").read_text() == "new content"

    def test_execute_delete_extras(self, tmp_dir: Path):
        src = tmp_dir / "src"
        dest = tmp_dir / "dest"
        src.mkdir()
        dest.mkdir()

        (src / "keep.txt").write_text("keep")
        (dest / "keep.txt").write_text("keep")
        (dest / "extra.txt").write_text("delete")

        syncer = sync(src, dest).direction("source_to_dest").delete_extras(True).dry_run(False)
        result = syncer.execute()

        assert result.success()
        assert not (dest / "extra.txt").exists()
        assert (dest / "keep.txt").exists()


class TestSyncerConflictResolution:
    """Test conflict resolution strategies."""

    def test_conflict_error(self, tmp_dir: Path):
        src = tmp_dir / "src"
        dest = tmp_dir / "dest"
        src.mkdir()
        dest.mkdir()

        (src / "conflict.txt").write_text("src")
        (dest / "conflict.txt").write_text("dest")

        syncer = sync(src, dest).direction("bidirectional").conflict_strategy("error")

        with pytest.raises(SyncConflictError):
            syncer.execute()

    def test_conflict_source_wins(self, tmp_dir: Path):
        src = tmp_dir / "src"
        dest = tmp_dir / "dest"
        src.mkdir()
        dest.mkdir()

        (src / "conflict.txt").write_text("src wins")
        (dest / "conflict.txt").write_text("dest")

        syncer = (
            sync(src, dest)
            .direction("bidirectional")
            .conflict_strategy("source_wins")
            .dry_run(False)
        )
        result = syncer.execute()

        assert result.success()
        assert (dest / "conflict.txt").read_text() == "src wins"

    def test_conflict_newer_wins(self, tmp_dir: Path):
        import time

        src = tmp_dir / "src"
        dest = tmp_dir / "dest"
        src.mkdir()
        dest.mkdir()

        (src / "conflict.txt").write_text("older")
        time.sleep(0.1)
        (dest / "conflict.txt").write_text("newer")

        syncer = (
            sync(src, dest)
            .direction("bidirectional")
            .conflict_strategy("newer_wins")
            .dry_run(False)
        )
        result = syncer.execute()

        assert result.success()
        # dest is newer, so src should be updated
        assert (src / "conflict.txt").read_text() == "newer"


class TestSyncerParallel:
    """Test parallel sync."""

    def test_parallel_sync(self, tmp_dir: Path):
        src = tmp_dir / "src"
        dest = tmp_dir / "dest"
        src.mkdir()
        dest.mkdir()

        for i in range(10):
            (src / f"file{i}.txt").write_text(f"content {i}")

        syncer = sync(src, dest).direction("source_to_dest").parallel(4).dry_run(False)
        result = syncer.execute()

        assert result.success()
        assert result.count == 10
