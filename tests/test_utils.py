"""Tests for utility functions."""

from __future__ import annotations

from pathlib import Path

import pytest

import path_file as pf
from path_file.utils import *


class TestSizeDurationAliases:
    """Test size and duration aliases."""

    def test_size_alias(self):
        assert pf.size("1KB") == 1024
        assert pf.size("1MB") == 1024 * 1024
        assert pf.size(512) == 512

    def test_hsize_alias(self):
        assert pf.hsize(1024) == "1.00 KiB"
        assert pf.hsize(1024 * 1024) == "1.00 MiB"

    def test_duration_alias(self):
        td = pf.duration("1 hour")
        assert td.total_seconds() == 3600


class TestPathUtilities:
    """Test path utility functions."""

    def test_expand(self):
        path = pf.expand("~/test")
        assert path.is_absolute()
        assert "~" not in str(path)

    def test_safe_join(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            result = pf.safe_join("subdir", "file.txt", base=base)
            assert result == base / "subdir" / "file.txt"

    def test_safe_join_escape_raises(self):
        base = Path("/safe")
        with pytest.raises(pf.PathflowError):
            pf.safe_join("..", "escape.txt", base=base)

    def test_mkdir(self):
        with pf.tempdir() as tmp:
            new_dir = pf.mkdir(tmp / "new" / "nested" / "dir")
            assert new_dir.exists()
            assert new_dir.is_dir()

    def test_which(self):
        # Test with a known command
        python_path = pf.which("python")
        assert python_path is not None
        assert python_path.name.startswith("python")

    def test_free_space(self):
        with pf.tempdir() as tmp:
            free = pf.free_space(tmp)
            assert free > 0

    def test_disk_usage(self):
        with pf.tempdir() as tmp:
            total, used, free = pf.disk_usage(tmp)
            assert total > 0
            assert used >= 0
            assert free > 0
            assert total == used + free


class TestTempDir:
    """Test temporary directory context manager."""

    def test_tempdir_context(self):
        with pf.tempdir() as tmp:
            assert tmp.exists()
            assert tmp.is_dir()
            test_file = tmp / "test.txt"
            test_file.write_text("hello")
            assert test_file.exists()

        # Should be cleaned up
        assert not tmp.exists()

    def test_tempdir_prefix_suffix(self):
        with pf.tempdir(prefix="custom_", suffix="_end") as tmp:
            assert "custom_" in tmp.name
            assert tmp.name.endswith("_end")


class TestFileOperations:
    """Test file operation utilities."""

    def test_copy_file(self, tmp_dir: Path):
        src = tmp_dir / "source.txt"
        src.write_text("content")
        dest = tmp_dir / "dest.txt"

        pf.copy_file(src, dest)

        assert dest.exists()
        assert dest.read_text() == "content"

    def test_copy_file_overwrite(self, tmp_dir: Path):
        src = tmp_dir / "source.txt"
        src.write_text("new")
        dest = tmp_dir / "dest.txt"
        dest.write_text("old")

        pf.copy_file(src, dest, overwrite=True)

        assert dest.read_text() == "new"

    def test_copy_file_no_overwrite_raises(self, tmp_dir: Path):
        src = tmp_dir / "source.txt"
        dest = tmp_dir / "dest.txt"
        dest.write_text("existing")

        with pytest.raises(FileExistsError):
            pf.copy_file(src, dest, overwrite=False)

    def test_move_file(self, tmp_dir: Path):
        src = tmp_dir / "source.txt"
        src.write_text("content")
        dest = tmp_dir / "dest.txt"

        pf.move_file(src, dest)

        assert not src.exists()
        assert dest.exists()
        assert dest.read_text() == "content"

    def test_delete_file(self, tmp_dir: Path):
        f = tmp_dir / "to_delete.txt"
        f.write_text("content")

        result = pf.delete_file(f)

        assert result is True
        assert not f.exists()

    def test_delete_file_missing_ok(self, tmp_dir: Path):
        f = tmp_dir / "nonexistent.txt"

        result = pf.delete_file(f, missing_ok=True)

        assert result is False

    def test_delete_dir(self, tmp_dir: Path):
        d = tmp_dir / "to_delete"
        d.mkdir()
        (d / "file.txt").write_text("content")

        result = pf.delete_dir(d)

        assert result is True
        assert not d.exists()

    def test_touch(self, tmp_dir: Path):
        f = tmp_dir / "touched.txt"

        pf.touch(f)

        assert f.exists()

        import time

        time.sleep(0.01)
        original_mtime = f.stat().st_mtime

        pf.touch(f)

        assert f.stat().st_mtime > original_mtime

    def test_read_text_utf8(self, tmp_dir: Path):
        f = tmp_dir / "utf8.txt"
        f.write_text("Hello 世界", encoding="utf-8")

        content = pf.read_text(f)

        assert content == "Hello 世界"

    def test_read_text_fallback(self, tmp_dir: Path):
        f = tmp_dir / "latin1.txt"
        f.write_text("Héllo", encoding="latin-1")

        content = pf.read_text(f)

        assert content == "Héllo"

    def test_write_text_atomic(self, tmp_dir: Path):
        f = tmp_dir / "atomic.txt"

        pf.write_text(f, "content")

        assert f.read_text() == "content"

    def test_write_bytes_atomic(self, tmp_dir: Path):
        f = tmp_dir / "atomic.bin"

        pf.write_bytes(f, b"binary content")

        assert f.read_bytes() == b"binary content"


class TestSymlinks:
    """Test symlink utilities."""

    def test_symlink(self, tmp_dir: Path):
        target = tmp_dir / "target.txt"
        target.write_text("target")
        link = tmp_dir / "link.txt"

        pf.symlink(target, link)

        assert link.is_symlink()
        assert link.read_text() == "target"

    def test_readlink(self, tmp_dir: Path):
        target = tmp_dir / "target.txt"
        target.write_text("target")
        link = tmp_dir / "link.txt"
        link.symlink_to(target)

        result = pf.readlink(link)

        # On Windows, os.readlink may return extended-length paths (\\?\)
        # Normalize both paths for comparison
        result_str = str(result).replace("\\\\?\\", "")
        target_str = str(target)
        assert result_str == target_str

    def test_is_symlink(self, tmp_dir: Path):
        target = tmp_dir / "target.txt"
        target.write_text("target")
        link = tmp_dir / "link.txt"
        link.symlink_to(target)

        assert pf.is_symlink(link) is True
        assert pf.is_symlink(target) is False

    def test_resolve_link(self, tmp_dir: Path):
        target = tmp_dir / "target.txt"
        target.write_text("target")
        link = tmp_dir / "link.txt"
        link.symlink_to(target)

        resolved = pf.resolve_link(link)

        assert resolved == target.resolve()


class TestProcessExecution:
    """Test process execution utilities."""

    def test_run_command(self):
        import sys

        result = pf.run_command([sys.executable, "-c", "print('hello')"])

        assert result.returncode == 0
        assert "hello" in result.stdout

    def test_run_shell(self):
        result = pf.run_shell("echo hello")

        assert result.returncode == 0
        assert "hello" in result.stdout


class TestPathInfo:
    """Test path info utilities."""

    def test_get_size_file(self, tmp_dir: Path):
        f = tmp_dir / "file.txt"
        f.write_text("x" * 1000)

        size = pf.get_size(f)

        assert size == 1000

    def test_get_size_dir(self, tmp_dir: Path):
        (tmp_dir / "a.txt").write_text("x" * 100)
        (tmp_dir / "b.txt").write_text("x" * 200)

        size = pf.get_size(tmp_dir)

        assert size >= 300

    def test_get_size_human(self, tmp_dir: Path):
        f = tmp_dir / "file.txt"
        f.write_text("x" * 1024)

        human = pf.get_size_human(f)

        assert "1.00 KiB" in human or "1.0 KiB" in human

    def test_count_files(self, tmp_dir: Path):
        (tmp_dir / "a.txt").write_text("a")
        (tmp_dir / "b.txt").write_text("b")
        (tmp_dir / "c.jpg").write_bytes(b"x")

        count = pf.count_files(tmp_dir, "*.txt")

        assert count == 2

    def test_find_largest(self, tmp_dir: Path):
        (tmp_dir / "small.txt").write_text("x")
        (tmp_dir / "medium.txt").write_text("x" * 1000)
        (tmp_dir / "large.txt").write_text("x" * 10000)

        largest = pf.find_largest(tmp_dir, 2)

        assert len(largest) == 2
        assert largest[0].name == "large.txt"
        assert largest[1].name == "medium.txt"

    def test_find_oldest_newest(self, tmp_dir: Path):
        import time

        (tmp_dir / "old.txt").write_text("old")
        time.sleep(0.01)
        (tmp_dir / "new.txt").write_text("new")

        oldest = pf.find_oldest(tmp_dir, 1)
        newest = pf.find_newest(tmp_dir, 1)

        assert oldest[0].name == "old.txt"
        assert newest[0].name == "new.txt"


class TestArchiveHelpers:
    """Test archive helper utilities."""

    def test_make_archive(self, tmp_dir: Path):
        src = tmp_dir / "src"
        src.mkdir()
        (src / "file.txt").write_text("content")

        dest = tmp_dir / "archive.zip"
        pf.make_archive(src, dest)

        assert dest.exists()

    def test_extract_archive(self, tmp_dir: Path):
        src = tmp_dir / "src"
        src.mkdir()
        (src / "file.txt").write_text("content")

        archive = tmp_dir / "archive.zip"
        pf.make_archive(src, archive)

        dest = tmp_dir / "extracted"
        pf.extract_archive(archive, dest)

        assert (dest / "file.txt").exists()
        assert (dest / "file.txt").read_text() == "content"


class TestHashHelpers:
    """Test hash helper utilities."""

    def test_hash_file(self, tmp_dir: Path):
        f = tmp_dir / "file.txt"
        f.write_text("content")

        hash_val = pf.hash_file(f)

        assert len(hash_val) == 64

    def test_verify_hash(self, tmp_dir: Path):
        f = tmp_dir / "file.txt"
        f.write_text("content")

        expected = pf.hash_file(f)

        assert pf.verify_hash(f, expected) is True
        assert pf.verify_hash(f, "wrong") is False


class TestMisc:
    """Test miscellaneous utilities."""

    def test_is_binary(self, tmp_dir: Path):
        text_file = tmp_dir / "text.txt"
        text_file.write_text("hello")

        bin_file = tmp_dir / "binary.bin"
        bin_file.write_bytes(bytes(range(256)))

        assert pf.is_binary(text_file) is False
        assert pf.is_binary(bin_file) is True

    def test_get_mime_type(self, tmp_dir: Path):
        f = tmp_dir / "file.txt"
        f.write_text("content")

        mime = pf.get_mime_type(f)

        assert mime == "text/plain"

    def test_get_extension(self):
        assert pf.get_extension("file.txt") == ".txt"
        assert pf.get_extension("file.TXT") == ".txt"
        assert pf.get_extension("file.tar.gz") == ".gz"

    def test_strip_extension(self):
        assert pf.strip_extension("file.txt") == "file"
        assert pf.strip_extension("file.tar.gz") == "file.tar"

    def test_change_extension(self):
        assert pf.change_extension("file.txt", ".md") == Path("file.md")
        assert pf.change_extension("file", ".txt") == Path("file.txt")
