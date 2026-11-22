"""Tests for archive operations."""

from __future__ import annotations

from pathlib import Path

import path_file as pf
from path_file.archive import (
    compress_file,
    create_archive,
    decompress_file,
    detect_archive_type,
    extract_archive,
    list_archive,
)


class TestDetectArchiveType:
    """Test archive type detection."""

    def test_detect_zip(self, tmp_dir: Path):
        archive = tmp_dir / "test.zip"
        archive.write_bytes(b"PK\x03\x04" + b"x" * 100)

        assert detect_archive_type(archive) == "zip"

    def test_detect_gz(self, tmp_dir: Path):
        archive = tmp_dir / "test.gz"
        archive.write_bytes(b"\x1f\x8b" + b"x" * 100)

        assert detect_archive_type(archive) == "gz"

    def test_detect_tar_gz_by_extension(self, tmp_dir: Path):
        archive = tmp_dir / "test.tar.gz"
        archive.write_bytes(b"x" * 100)

        assert detect_archive_type(archive) == "tar.gz"

    def test_detect_unknown(self, tmp_dir: Path):
        archive = tmp_dir / "test.unknown"
        archive.write_bytes(b"random")

        assert detect_archive_type(archive) == "unknown"


class TestCreateArchive:
    """Test archive creation."""

    def test_create_zip(self, tmp_tree: Path, tmp_dir: Path):
        archive = tmp_dir / "test.zip"
        entries = pf.find(tmp_tree).files().with_extension(".txt").to_list()

        create_archive(entries, archive, "zip")

        assert archive.exists()
        assert archive.suffix == ".zip"

    def test_create_tar_gz(self, tmp_tree: Path, tmp_dir: Path):
        archive = tmp_dir / "test.tar.gz"
        entries = pf.find(tmp_tree).files().with_extension(".txt").to_list()

        create_archive(entries, archive, "tar.gz")

        assert archive.exists()

    def test_create_tar_bz2(self, tmp_tree: Path, tmp_dir: Path):
        archive = tmp_dir / "test.tar.bz2"
        entries = pf.find(tmp_tree).files().with_extension(".txt").to_list()

        create_archive(entries, archive, "tar.bz2")

        assert archive.exists()

    def test_create_tar_xz(self, tmp_tree: Path, tmp_dir: Path):
        archive = tmp_dir / "test.tar.xz"
        entries = pf.find(tmp_tree).files().with_extension(".txt").to_list()

        create_archive(entries, archive, "tar.xz")

        assert archive.exists()


class TestListArchive:
    """Test listing archive contents."""

    def test_list_zip(self, tmp_tree: Path, tmp_dir: Path):
        archive = tmp_dir / "list_test.zip"
        entries = pf.find(tmp_tree).files().with_extension(".txt").limit(3).to_list()

        create_archive(entries, archive, "zip")
        listed = list_archive(archive)

        assert len(listed) >= 3
        for item in listed:
            assert isinstance(item.name, str)
            assert isinstance(item.size, int)
            assert isinstance(item.is_dir, bool)

    def test_list_tar(self, tmp_tree: Path, tmp_dir: Path):
        archive = tmp_dir / "list_test.tar.gz"
        entries = pf.find(tmp_tree).files().with_extension(".txt").limit(3).to_list()

        create_archive(entries, archive, "tar.gz")
        listed = list_archive(archive)

        assert len(listed) >= 3


class TestExtractArchive:
    """Test archive extraction."""

    def test_extract_zip(self, tmp_tree: Path, tmp_dir: Path):
        archive = tmp_dir / "extract_test.zip"
        entries = pf.find(tmp_tree).files().with_extension(".txt").limit(3).to_list()

        create_archive(entries, archive, "zip")

        dest = tmp_dir / "extracted"
        extracted = extract_archive(archive, dest)

        assert len(extracted) >= 3
        assert all(p.exists() for p in extracted)

    def test_extract_tar_gz(self, tmp_tree: Path, tmp_dir: Path):
        archive = tmp_dir / "extract_test.tar.gz"
        entries = pf.find(tmp_tree).files().with_extension(".txt").limit(3).to_list()

        create_archive(entries, archive, "tar.gz")

        dest = tmp_dir / "extracted"
        extracted = extract_archive(archive, dest)

        assert len(extracted) >= 3

    def test_extract_with_members(self, tmp_tree: Path, tmp_dir: Path):
        archive = tmp_dir / "extract_members.zip"
        entries = pf.find(tmp_tree).files().with_extension(".txt").to_list()

        create_archive(entries, archive, "zip")

        dest = tmp_dir / "extracted"
        # Extract only first file
        first_file = entries[0].name
        extracted = extract_archive(archive, dest, members=[first_file])

        assert len(extracted) == 1
        assert extracted[0].name == first_file


class TestCompressDecompress:
    """Test single file compression/decompression."""

    def test_compress_gz(self, tmp_tree: Path, tmp_dir: Path):
        # gzip needs enough data for compression to actually save space
        src = tmp_tree / "compressible.txt"
        src.write_text("repeat me " * 2000)
        compressed = compress_file(src, "gz")

        assert compressed.exists()
        assert compressed.suffix == ".gz"
        assert compressed.stat().st_size < src.stat().st_size

    def test_compress_bz2(self, tmp_tree: Path, tmp_dir: Path):
        src = tmp_tree / "file1.txt"
        compressed = compress_file(src, "bz2")

        assert compressed.exists()
        assert compressed.suffix == ".bz2"

    def test_compress_xz(self, tmp_tree: Path, tmp_dir: Path):
        src = tmp_tree / "file1.txt"
        compressed = compress_file(src, "xz")

        assert compressed.exists()
        assert compressed.suffix == ".xz"

    def test_compress_keep_original(self, tmp_tree: Path, tmp_dir: Path):
        src = tmp_tree / "file1.txt"
        original_size = src.stat().st_size

        compressed = compress_file(src, "gz", keep_original=True)

        assert src.exists()
        assert compressed.exists()

    def test_decompress_gz(self, tmp_tree: Path, tmp_dir: Path):
        src = tmp_tree / "file1.txt"
        compressed = compress_file(src, "gz", keep_original=True)

        decompressed = decompress_file(compressed)

        assert decompressed.exists()
        assert decompressed.read_text() == src.read_text()

    def test_decompress_keep_original(self, tmp_tree: Path, tmp_dir: Path):
        src = tmp_tree / "file1.txt"
        compressed = compress_file(src, "gz", keep_original=True)

        decompressed = decompress_file(compressed, keep_original=True)

        assert compressed.exists()
        assert decompressed.exists()


class TestChainArchiveActions:
    """Test archive actions via FileChain."""

    def test_chain_archive_to(self, tmp_tree: Path, tmp_dir: Path):
        archive = tmp_dir / "chain.zip"
        chain = pf.find(tmp_tree).files().with_extension(".txt")

        result = chain.archive_to(archive, format="zip").execute()

        assert result.success()
        assert archive.exists()

    def test_chain_compress(self, tmp_tree: Path, tmp_dir: Path):
        chain = pf.find(tmp_tree).files().with_extension(".txt").limit(2)
        entries = chain.to_list()

        result = chain.compress("gz").execute()

        assert result.success()
        for entry in entries:
            compressed = entry.path.with_suffix(entry.path.suffix + ".gz")
            assert compressed.exists()
