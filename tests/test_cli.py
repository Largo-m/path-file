"""Tests for CLI."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


class TestCLIBasics:
    """Test basic CLI functionality."""

    def test_version(self):
        result = subprocess.run(
            [sys.executable, "-m", "path_file", "--version"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "path_file" in result.stdout.lower()

    def test_help(self):
        result = subprocess.run(
            [sys.executable, "-m", "path_file", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "usage" in result.stdout.lower()
        assert "find" in result.stdout
        assert "copy" in result.stdout

    def test_invalid_command(self):
        result = subprocess.run(
            [sys.executable, "-m", "path_file", "invalid"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0


class TestFindCommand:
    """Test find command."""

    def test_find_basic(self, tmp_tree: Path):
        result = subprocess.run(
            [sys.executable, "-m", "path_file", "find", str(tmp_tree)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "file1.txt" in result.stdout

    def test_find_extension(self, tmp_tree: Path):
        result = subprocess.run(
            [sys.executable, "-m", "path_file", "find", str(tmp_tree), "--ext", ".jpg"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "image1.jpg" in result.stdout
        assert "file1.txt" not in result.stdout

    def test_find_larger(self, tmp_tree: Path):
        result = subprocess.run(
            [sys.executable, "-m", "path_file", "find", str(tmp_tree), "--larger", "1MB"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        # Should find large.bin (5MB)
        assert "large.bin" in result.stdout

    def test_find_json(self, tmp_tree: Path):
        result = subprocess.run(
            [sys.executable, "-m", "path_file", "find", str(tmp_tree), "--json", "--limit", "2"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) == 2

    def test_find_no_results(self, tmp_tree: Path):
        result = subprocess.run(
            [sys.executable, "-m", "path_file", "find", str(tmp_tree), "--ext", ".nonexistent"],
            capture_output=True,
            text=True,
        )
        # Exit code 4 for no matches
        assert result.returncode == 4


class TestReportCommand:
    """Test report command."""

    def test_report_basic(self, tmp_tree: Path):
        result = subprocess.run(
            [sys.executable, "-m", "path_file", "report", str(tmp_tree)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "PATHFLOW REPORT" in result.stdout
        assert "Total Entries" in result.stdout

    def test_report_json(self, tmp_tree: Path):
        result = subprocess.run(
            [sys.executable, "-m", "path_file", "report", str(tmp_tree), "--json"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "chain_size" in data
        assert "by_extension" in data


class TestCopyCommand:
    """Test copy command."""

    def test_copy_basic(self, tmp_tree: Path, tmp_dir: Path):
        dest = tmp_dir / "copied"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "path_file",
                "copy",
                str(tmp_tree),
                str(dest),
                "--ext",
                ".txt",
                "--overwrite",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert dest.exists()
        assert len(list(dest.glob("*.txt"))) > 0

    def test_copy_dry_run(self, tmp_tree: Path, tmp_dir: Path):
        dest = tmp_dir / "copied_dry"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "path_file",
                "copy",
                str(tmp_tree),
                str(dest),
                "--ext",
                ".txt",
                "--dry-run",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "DRY RUN" in result.stdout.upper()
        assert not dest.exists()


class TestDeleteCommand:
    """Test delete command."""

    def test_delete_requires_confirm(self, tmp_tree: Path):
        result = subprocess.run(
            [sys.executable, "-m", "path_file", "delete", str(tmp_tree), "--ext", ".txt"],
            capture_output=True,
            text=True,
        )
        # Should fail without --confirm
        assert result.returncode == 3

    def test_delete_with_confirm(self, tmp_tree: Path, tmp_dir: Path):
        # Create test files
        test_dir = tmp_dir / "to_delete"
        test_dir.mkdir()
        (test_dir / "a.txt").write_text("a")
        (test_dir / "b.txt").write_text("b")

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "path_file",
                "delete",
                str(test_dir),
                "--ext",
                ".txt",
                "--confirm",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert not (test_dir / "a.txt").exists()


class TestHashCommand:
    """Test hash command."""

    def test_hash_basic(self, tmp_tree: Path):
        result = subprocess.run(
            [sys.executable, "-m", "path_file", "hash", str(tmp_tree / "file1.txt")],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        # Should output hash and path
        assert len(result.stdout.strip().split()[0]) == 64

    def test_hash_algorithm(self, tmp_tree: Path):
        result = subprocess.run(
            [sys.executable, "-m", "path_file", "hash", str(tmp_tree / "file1.txt"), "-a", "md5"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert len(result.stdout.strip().split()[0]) == 32


class TestArchiveCommand:
    """Test archive command."""

    def test_archive_zip(self, tmp_tree: Path, tmp_dir: Path):
        output = tmp_dir / "test.zip"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "path_file",
                "archive",
                str(tmp_tree),
                "-o",
                str(output),
                "-f",
                "zip",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert output.exists()

    def test_archive_tar_gz(self, tmp_tree: Path, tmp_dir: Path):
        output = tmp_dir / "test.tar.gz"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "path_file",
                "archive",
                str(tmp_tree),
                "-o",
                str(output),
                "-f",
                "tar.gz",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert output.exists()


class TestSyncCommand:
    """Test sync command."""

    def test_sync_dry_run(self, tmp_tree: Path, tmp_dir: Path):
        src = tmp_dir / "sync_src"
        dest = tmp_dir / "sync_dest"
        src.mkdir()
        dest.mkdir()
        (src / "new.txt").write_text("new")

        result = subprocess.run(
            [sys.executable, "-m", "path_file", "sync", str(src), str(dest), "--dry-run"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "new.txt" in result.stdout

    def test_sync_delete_extras(self, tmp_tree: Path, tmp_dir: Path):
        src = tmp_dir / "sync_src"
        dest = tmp_dir / "sync_dest"
        src.mkdir()
        dest.mkdir()
        (src / "keep.txt").write_text("keep")
        (dest / "keep.txt").write_text("keep")
        (dest / "extra.txt").write_text("extra")

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "path_file",
                "sync",
                str(src),
                str(dest),
                "--delete-extras",
                "--dry-run",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "extra.txt" in result.stdout


class TestGlobalFlags:
    """Test global flags."""

    def test_verbose(self, tmp_tree: Path):
        result = subprocess.run(
            [sys.executable, "-m", "path_file", "-v", "find", str(tmp_tree), "--limit", "1"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_quiet(self, tmp_tree: Path):
        result = subprocess.run(
            [sys.executable, "-m", "path_file", "-q", "find", str(tmp_tree), "--limit", "1"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_dry_run_global(self, tmp_tree: Path, tmp_dir: Path):
        dest = tmp_dir / "global_dry"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "path_file",
                "--dry-run",
                "copy",
                str(tmp_tree),
                str(dest),
                "--ext",
                ".txt",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert not dest.exists()
