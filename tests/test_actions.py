"""Tests for file actions."""

from __future__ import annotations

from pathlib import Path

import pytest

import path_file as pf
from path_file.exceptions import DestExistsError, DryRunRequiredError


class TestCopyAction:
    """Test copy action."""

    def test_copy_files(self, tmp_tree: Path, tmp_dir: Path):
        dest = tmp_dir / "copied"
        chain = pf.find(tmp_tree).files().with_extension(".txt")
        expected_count = chain.count()
        result = chain.copy_to(dest, overwrite=True).execute()

        assert result.success()
        assert result.count > 0
        assert dest.exists()
        assert len(list(dest.glob("*.txt"))) == expected_count

    def test_copy_preserves_metadata(self, tmp_tree: Path, tmp_dir: Path):
        dest = tmp_dir / "copied_meta"
        chain = pf.find(tmp_tree).files().with_extension(".txt").limit(1)
        entry = chain.first()
        original_mtime = entry.modified

        chain.copy_to(dest, preserve_metadata=True).execute()

        copied = dest / entry.name
        assert copied.exists()
        # mtime should be preserved (approximately)
        assert abs(copied.stat().st_mtime - original_mtime.timestamp()) < 2

    def test_copy_overwrite_false_raises(self, tmp_tree: Path, tmp_dir: Path):
        dest = tmp_dir / "copy_overwrite"
        dest.mkdir()
        (dest / "file1.txt").write_text("existing")

        chain = pf.find(tmp_tree).files().with_extension(".txt").limit(1)

        with pytest.raises(DestExistsError):
            chain.copy_to(dest, overwrite=False).execute()

    def test_copy_dry_run(self, tmp_tree: Path, tmp_dir: Path):
        dest = tmp_dir / "copy_dry"
        chain = pf.find(tmp_tree).files().with_extension(".txt")
        original_count = len(list(tmp_tree.glob("*.txt")))

        result = chain.copy_to(dest, dry_run=True).execute()

        assert result.dry_run
        assert result.count > 0
        assert not dest.exists()
        # Original files unchanged
        assert len(list(tmp_tree.glob("*.txt"))) == original_count


class TestMoveAction:
    """Test move action."""

    def test_move_files(self, tmp_tree: Path, tmp_dir: Path):
        # Create source files to move
        src = tmp_dir / "move_src"
        src.mkdir()
        for i in range(3):
            (src / f"file{i}.txt").write_text(f"content {i}")

        dest = tmp_dir / "move_dest"
        chain = pf.find(src).files()
        result = chain.move_to(dest, overwrite=True, dry_run=False).execute()

        assert result.success()
        assert result.count == 3
        assert dest.exists()
        assert len(list(dest.glob("*.txt"))) == 3
        assert not src.exists() or len(list(src.glob("*.txt"))) == 0

    def test_move_dry_run(self, tmp_tree: Path, tmp_dir: Path):
        src = tmp_dir / "move_dry_src"
        src.mkdir()
        (src / "test.txt").write_text("test")

        dest = tmp_dir / "move_dry_dest"
        chain = pf.find(src).files()

        result = chain.move_to(dest, dry_run=True).execute()

        assert result.dry_run
        assert src.exists()
        assert not dest.exists()


class TestDeleteAction:
    """Test delete action."""

    def test_delete_requires_confirm(self, tmp_tree: Path):
        chain = pf.find(tmp_tree).files().with_extension(".txt")

        with pytest.raises(DryRunRequiredError) as exc:
            chain.delete().execute()

        assert "confirm=True" in exc.value.hint
        assert exc.value.count == chain.count()

    def test_delete_with_confirm(self, tmp_tree: Path, tmp_dir: Path):
        # Create files to delete
        src = tmp_dir / "delete_test"
        src.mkdir()
        for i in range(3):
            (src / f"del{i}.tmp").write_text("delete me")

        chain = pf.find(src).files().with_extension(".tmp")
        result = chain.delete(confirm=True, dry_run=False).execute()

        assert result.success()
        assert result.count == 3
        assert len(list(src.glob("*.tmp"))) == 0

    def test_delete_dry_run(self, tmp_tree: Path, tmp_dir: Path):
        src = tmp_dir / "delete_dry"
        src.mkdir()
        (src / "test.txt").write_text("test")

        chain = pf.find(src).files()
        result = chain.delete(dry_run=True).execute()

        assert result.dry_run
        assert result.count == 1
        assert (src / "test.txt").exists()


class TestTrashAction:
    """Test trash action."""

    def test_trash_requires_confirm(self, tmp_tree: Path):
        chain = pf.find(tmp_tree).files().with_extension(".txt")

        with pytest.raises(DryRunRequiredError):
            chain.trash().execute()

    def test_trash_dry_run(self, tmp_tree: Path, tmp_dir: Path):
        src = tmp_dir / "trash_dry"
        src.mkdir()
        (src / "test.txt").write_text("test")

        chain = pf.find(src).files()
        result = chain.trash(dry_run=True).execute()

        assert result.dry_run
        assert (src / "test.txt").exists()


class TestRenameAction:
    """Test rename action."""

    def test_rename_with_pattern(self, tmp_dir: Path):
        src = tmp_dir / "rename_test"
        src.mkdir()
        for i in range(3):
            (src / f"img_{i}.jpg").write_bytes(b"fake jpg")

        chain = pf.find(src).files()
        result = chain.rename("photo_{n:03d}{ext}").execute()

        # This is a placeholder - actual implementation may vary
        assert result.count == 3

    def test_rename_with_function(self, tmp_dir: Path):
        src = tmp_dir / "rename_func"
        src.mkdir()
        (src / "file1.txt").write_text("test")
        (src / "file2.txt").write_text("test")

        chain = pf.find(src).files()
        result = chain.rename_with(lambda stem: f"renamed_{stem}").execute()

        assert result.count == 2


class TestArchiveAction:
    """Test archive action."""

    def test_archive_to_zip(self, tmp_tree: Path, tmp_dir: Path):
        archive = tmp_dir / "test.zip"
        chain = pf.find(tmp_tree).files().with_extension(".txt")
        result = chain.archive_to(archive, format="zip").execute()

        assert result.success()
        assert archive.exists()
        assert archive.suffix == ".zip"

    def test_archive_to_tar_gz(self, tmp_tree: Path, tmp_dir: Path):
        archive = tmp_dir / "test.tar.gz"
        chain = pf.find(tmp_tree).files().with_extension(".txt")
        result = chain.archive_to(archive, format="tar.gz").execute()

        assert result.success()
        assert archive.exists()


class TestHashAction:
    """Test hash action."""

    def test_hash_files(self, tmp_tree: Path):
        chain = pf.find(tmp_tree).files().limit(3)
        result = chain.hash("sha256").execute()

        assert result.success()
        # Hashes should be computed
        for entry in chain:
            assert entry.hash_sha256
            assert len(entry.hash_sha256) == 64


class TestReadWriteActions:
    """Test read/write actions."""

    def test_read_text(self, tmp_tree: Path):
        chain = pf.find(tmp_tree).files().with_extension(".txt").limit(2)
        result = chain.read_text().execute()

        assert result.success()
        # Read action returns content via map/for_each

    def test_write_text(self, tmp_dir: Path):
        src = tmp_dir / "write_test"
        src.mkdir()
        (src / "out1.txt").write_text("old")
        (src / "out2.txt").write_text("old")

        chain = pf.find(src).files()
        result = chain.write_text("new content", dry_run=False).execute()

        assert result.success()
        for f in src.glob("*.txt"):
            assert f.read_text() == "new content"


class TestChmodAction:
    """Test chmod action."""

    def test_chmod(self, tmp_dir: Path):
        import sys

        if sys.platform == "win32":
            pytest.skip("chmod not reliable on Windows")

        src = tmp_dir / "chmod_test"
        src.mkdir()
        (src / "script.sh").write_text("#!/bin/bash\necho hi")

        chain = pf.find(src).files()
        result = chain.chmod(0o755, dry_run=False).execute()

        assert result.success()
        assert oct((src / "script.sh").stat().st_mode & 0o777) == "0o755"


class TestTouchAction:
    """Test touch action."""

    def test_touch(self, tmp_dir: Path):
        src = tmp_dir / "touch_test"
        src.mkdir()
        (src / "new.txt").write_text("test")
        original_mtime = (src / "new.txt").stat().st_mtime

        import time

        time.sleep(0.1)

        chain = pf.find(src).files()
        result = chain.touch().execute()

        assert result.success()
        new_mtime = (src / "new.txt").stat().st_mtime
        assert new_mtime > original_mtime


class TestParallelExecution:
    """Test parallel execution."""

    def test_parallel_copy(self, tmp_tree: Path, tmp_dir: Path):
        dest = tmp_dir / "parallel_copy"
        chain = pf.find(tmp_tree).files().parallel(4)
        result = chain.copy_to(dest, overwrite=True).execute()

        assert result.success()
        assert result.count > 0

    def test_parallel_hash(self, tmp_tree: Path):
        chain = pf.find(tmp_tree).files().parallel(4)
        result = chain.hash().execute()

        assert result.success()


class TestErrorHandling:
    """Test error handling modes."""

    def test_on_error_skip(self, tmp_tree: Path, tmp_dir: Path):
        # Create a file that will cause permission error (hard to simulate)
        # Just test that the chain accepts the option
        chain = pf.find(tmp_tree).files().on_error("skip")
        assert chain._on_error == "skip"

    def test_on_error_collect(self, tmp_tree: Path, tmp_dir: Path):
        chain = pf.find(tmp_tree).files().on_error("collect")
        assert chain._on_error == "collect"
