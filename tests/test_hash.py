"""Tests for hash computation and duplicate detection."""

from __future__ import annotations

from pathlib import Path

import path_file as pf
from path_file.hash import (
    find_duplicates,
    find_duplicates_by_name,
    hash_file,
    hash_files,
    verify_hash,
)


class TestHashFile:
    """Test single file hashing."""

    def test_hash_file_sha256(self, tmp_tree: Path):
        file_path = tmp_tree / "file1.txt"
        hash_val = hash_file(file_path, "sha256")

        assert isinstance(hash_val, str)
        assert len(hash_val) == 64
        assert all(c in "0123456789abcdef" for c in hash_val)

    def test_hash_file_md5(self, tmp_tree: Path):
        file_path = tmp_tree / "file1.txt"
        hash_val = hash_file(file_path, "md5")

        assert len(hash_val) == 32

    def test_hash_file_sha1(self, tmp_tree: Path):
        file_path = tmp_tree / "file1.txt"
        hash_val = hash_file(file_path, "sha1")

        assert len(hash_val) == 40

    def test_hash_consistency(self, tmp_tree: Path):
        file_path = tmp_tree / "file1.txt"
        h1 = hash_file(file_path, "sha256")
        h2 = hash_file(file_path, "sha256")

        assert h1 == h2

    def test_different_files_different_hashes(self, tmp_tree: Path):
        h1 = hash_file(tmp_tree / "file1.txt", "sha256")
        h2 = hash_file(tmp_tree / "file2.txt", "sha256")

        assert h1 != h2

    def test_hash_empty_file(self, tmp_tree: Path):
        hash_val = hash_file(tmp_tree / "empty.txt", "sha256")

        # Empty file SHA256
        assert hash_val == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


class TestHashFiles:
    """Test batch hashing."""

    def test_hash_multiple_files(self, tmp_tree: Path):
        entries = pf.find(tmp_tree).files().limit(5).to_list()
        hashes = hash_files(entries, "sha256")

        assert len(hashes) == 5
        for path, h in hashes.items():
            assert len(h) == 64

    def test_hash_parallel(self, tmp_tree: Path):
        entries = pf.find(tmp_tree).files().limit(10).to_list()
        hashes = hash_files(entries, "sha256", parallel=True, workers=4)

        assert len(hashes) == 10

    def test_hash_skips_directories(self, tmp_tree: Path):
        entries = pf.find(tmp_tree).to_list()  # Includes dirs
        hashes = hash_files(entries, "sha256")

        # Only files should be hashed
        file_entries = [e for e in entries if e.is_file]
        assert len(hashes) == len(file_entries)


class TestFindDuplicates:
    """Test duplicate detection."""

    def test_find_duplicates_by_content(self, tmp_dir: Path):
        # Create duplicate files
        for i in range(3):
            (tmp_dir / f"dup_{i}.txt").write_text("identical content")
        (tmp_dir / "unique.txt").write_text("different content")

        entries = pf.find(tmp_dir).files().to_list()
        dupes = find_duplicates(entries, "sha256")

        assert len(dupes) == 1
        hash_val, group = list(dupes.items())[0]
        assert len(group) == 3

    def test_find_no_duplicates(self, tmp_tree: Path):
        entries = pf.find(tmp_tree).files().to_list()
        dupes = find_duplicates(entries, "sha256")

        # All files in tmp_tree have unique content
        assert len(dupes) == 0

    def test_find_duplicates_min_size(self, tmp_dir: Path):
        (tmp_dir / "small1.txt").write_text("x")
        (tmp_dir / "small2.txt").write_text("x")
        (tmp_dir / "large.txt").write_text("y" * 1000)

        entries = pf.find(tmp_dir).files().to_list()
        dupes = find_duplicates(entries, "sha256", min_size=100)

        # small files should be ignored
        assert len(dupes) == 0

    def test_find_duplicates_by_name(self, tmp_dir: Path):
        (tmp_dir / "file.txt").write_text("content 1")
        (tmp_dir / "subdir").mkdir()
        (tmp_dir / "subdir" / "file.txt").write_text("content 2")
        (tmp_dir / "other.txt").write_text("content 3")

        entries = pf.find(tmp_dir).files().to_list()
        dupes = find_duplicates_by_name(entries)

        assert "file.txt" in dupes
        assert len(dupes["file.txt"]) == 2


class TestVerifyHash:
    """Test hash verification."""

    def test_verify_hash_match(self, tmp_tree: Path):
        file_path = tmp_tree / "file1.txt"
        expected = hash_file(file_path, "sha256")

        assert verify_hash(file_path, expected, "sha256") is True

    def test_verify_hash_mismatch(self, tmp_tree: Path):
        file_path = tmp_tree / "file1.txt"
        wrong_hash = "0" * 64

        assert verify_hash(file_path, wrong_hash, "sha256") is False

    def test_verify_multiple(self, tmp_tree: Path):
        entries = pf.find(tmp_tree).files().limit(3).to_list()
        file_hashes = {e.path: e.hash_sha256 for e in entries}

        results = pf.verify_hashes(file_hashes, "sha256")

        assert all(results.values())


class TestEntryHashProperty:
    """Test Entry.hash_sha256 lazy property."""

    def test_hash_property_cached(self, tmp_tree: Path):
        entry = pf.Entry.from_path(tmp_tree / "file1.txt")

        h1 = entry.hash_sha256
        h2 = entry.hash_sha256

        assert h1 == h2
        assert len(h1) == 64

    def test_hash_property_different_files(self, tmp_tree: Path):
        e1 = pf.Entry.from_path(tmp_tree / "file1.txt")
        e2 = pf.Entry.from_path(tmp_tree / "file2.txt")

        assert e1.hash_sha256 != e2.hash_sha256
