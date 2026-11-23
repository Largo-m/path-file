"""Tests for archive.py, sync.py and entries.py internals."""

from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path

import pytest

from path_file.archive import (
    ArchiveEntry,
    compress_file,
    create_archive,
    decompress_file,
    detect_archive_type,
    extract_archive,
    list_archive,
)
from path_file.entries import Entry
from path_file.sync import IgnoreMatcher, Syncer, sync


def _tree(tmp_dir: Path) -> Path:
    (tmp_dir / "a.txt").write_text("alpha")
    (tmp_dir / "b.txt").write_text("beta content")
    (tmp_dir / "c.log").write_text("log")
    (tmp_dir / "sub").mkdir()
    (tmp_dir / "sub" / "deep.txt").write_text("deep")
    return tmp_dir


class TestDetectArchiveType:
    def test_zip(self, tmp_dir):
        _tree(tmp_dir)
        archive = tmp_dir / "x.zip"
        create_archive([Entry.from_path(tmp_dir / "a.txt")], archive)
        assert detect_archive_type(archive) in ("zip", "zipfile")

    def test_tar(self, tmp_dir):
        _tree(tmp_dir)
        archive = tmp_dir / "x.tar"
        create_archive([Entry.from_path(tmp_dir / "a.txt")], archive, format="tar")
        assert detect_archive_type(archive) in ("tar", "tarfile")

    def test_tar_gz(self, tmp_dir):
        _tree(tmp_dir)
        archive = tmp_dir / "x.tar.gz"
        create_archive([Entry.from_path(tmp_dir / "a.txt")], archive, format="tar.gz")
        assert "tar" in detect_archive_type(archive)

    def test_unknown(self, tmp_dir):
        (tmp_dir / "plain.txt").write_text("x")
        assert detect_archive_type(tmp_dir / "plain.txt") in ("unknown", "", "text", "none")

    def test_missing(self, tmp_dir):
        assert isinstance(detect_archive_type(tmp_dir / "nope.zip"), str)


class TestCreateExtract:
    def test_zip_roundtrip(self, tmp_dir):
        _tree(tmp_dir)
        archive = tmp_dir / "backup.zip"
        entries = [Entry.from_path(tmp_dir / "a.txt"), Entry.from_path(tmp_dir / "sub")]
        create_archive(entries, archive, format="zip")
        assert zipfile.is_zipfile(archive)
        out = tmp_dir / "unzipped"
        extract_archive(archive, out)
        assert out.exists()

    def test_tar_roundtrip(self, tmp_dir):
        _tree(tmp_dir)
        archive = tmp_dir / "backup.tar"
        entries = [Entry.from_path(tmp_dir / "a.txt"), Entry.from_path(tmp_dir / "b.txt")]
        create_archive(entries, archive, format="tar")
        assert tarfile.is_tarfile(archive)
        out = tmp_dir / "untarred"
        extract_archive(archive, out)
        assert out.exists()

    def test_tar_gz_roundtrip(self, tmp_dir):
        _tree(tmp_dir)
        archive = tmp_dir / "backup.tar.gz"
        entries = [Entry.from_path(tmp_dir / "a.txt")]
        create_archive(entries, archive, format="tar.gz")
        assert tarfile.is_tarfile(archive)
        extract_archive(archive, tmp_dir / "untgz")

    def test_extract_missing(self, tmp_dir):
        with pytest.raises((OSError, Exception)):
            extract_archive(tmp_dir / "nope.zip", tmp_dir / "out")

    def test_list_archive(self, tmp_dir):
        _tree(tmp_dir)
        archive = tmp_dir / "backup.zip"
        create_archive([Entry.from_path(tmp_dir / "a.txt")], archive, format="zip")
        listed = list_archive(archive)
        assert listed
        assert isinstance(listed[0], ArchiveEntry)

    def test_archive_entry_fields(self):
        entry = ArchiveEntry(name="x.txt", size=10, is_dir=False)
        assert entry.name == "x.txt"


class TestCompressDecompress:
    def test_gz_roundtrip(self, tmp_dir):
        _tree(tmp_dir)
        compress_file(tmp_dir / "a.txt", format="gz")
        assert (tmp_dir / "a.txt.gz").exists()
        (tmp_dir / "a.txt.gz").rename(tmp_dir / "copy.gz")
        decompress_file(tmp_dir / "copy.gz")
        assert (tmp_dir / "copy").read_text() == "alpha"

    def test_bz2_roundtrip(self, tmp_dir):
        _tree(tmp_dir)
        compress_file(tmp_dir / "b.txt", format="bz2")
        assert (tmp_dir / "b.txt.bz2").exists()
        (tmp_dir / "b.txt.bz2").rename(tmp_dir / "copy2.bz2")
        decompress_file(tmp_dir / "copy2.bz2")
        assert (tmp_dir / "copy2").read_text() == "beta content"

    def test_xz_roundtrip(self, tmp_dir):
        _tree(tmp_dir)
        try:
            compress_file(tmp_dir / "c.log", format="xz")
        except Exception:
            pytest.skip("xz unavailable")
        assert (tmp_dir / "c.log.xz").exists()
        (tmp_dir / "c.log.xz").rename(tmp_dir / "copy3.xz")
        decompress_file(tmp_dir / "copy3.xz")
        assert (tmp_dir / "copy3").read_text() == "log"


class TestIgnoreMatcher:
    def test_empty(self, tmp_dir):
        matcher = IgnoreMatcher()
        assert matcher.match(tmp_dir / "x.txt") is False

    def test_from_patterns(self, tmp_dir):
        matcher = IgnoreMatcher(["*.log", "tmp/"])
        assert matcher.match(tmp_dir / "a.log") is True
        assert matcher.match(tmp_dir / "a.txt") is False

    def test_from_gitignore_file(self, tmp_dir):
        (tmp_dir / ".gitignore").write_text("*.tmp\nbuild/\n")
        matcher = IgnoreMatcher()
        matcher.load_file(tmp_dir / ".gitignore")
        assert matcher.match(tmp_dir / "x.tmp") is True
        assert matcher.match(tmp_dir / "x.txt") is False

    def test_from_gitignore_missing(self, tmp_dir):
        matcher = IgnoreMatcher()
        matcher.load_file(tmp_dir / "nope")
        assert matcher.match(tmp_dir / "x.txt") is False


class TestSyncer:
    def test_sync_creates_files(self, tmp_dir):
        src = tmp_dir / "src"
        dest = tmp_dir / "dest"
        src.mkdir()
        dest.mkdir()
        (src / "a.txt").write_text("data")
        sync(src, dest).execute()
        assert (dest / "a.txt").exists()

    def test_sync_in_sync(self, tmp_dir):
        src = tmp_dir / "src"
        dest = tmp_dir / "dest"
        src.mkdir()
        dest.mkdir()
        (src / "a.txt").write_text("data")
        (dest / "a.txt").write_text("data")
        result = sync(src, dest).execute()
        assert result.count == 0

    def test_sync_updates_changed(self, tmp_dir):
        src = tmp_dir / "src"
        dest = tmp_dir / "dest"
        src.mkdir()
        dest.mkdir()
        (src / "a.txt").write_text("new")
        (dest / "a.txt").write_text("old")
        sync(src, dest).execute()
        assert (dest / "a.txt").read_text() == "new"

    def test_sync_delete_extras(self, tmp_dir):
        src = tmp_dir / "src"
        dest = tmp_dir / "dest"
        src.mkdir()
        dest.mkdir()
        (dest / "extra.txt").write_text("x")
        sync(src, dest).delete_extras(True).execute()
        assert not (dest / "extra.txt").exists()

    def test_sync_dry_run(self, tmp_dir):
        src = tmp_dir / "src"
        dest = tmp_dir / "dest"
        src.mkdir()
        dest.mkdir()
        (src / "a.txt").write_text("data")
        sync(src, dest).dry_run().execute()
        assert not (dest / "a.txt").exists()

    def test_sync_ignore(self, tmp_dir):
        src = tmp_dir / "src"
        dest = tmp_dir / "dest"
        src.mkdir()
        dest.mkdir()
        (src / "a.txt").write_text("data")
        (src / "skip.log").write_text("log")
        sync(src, dest).ignore(["*.log"]).execute()
        assert (dest / "a.txt").exists()
        assert not (dest / "skip.log").exists()

    def test_syncer_is_chain_like(self, tmp_dir):
        src = tmp_dir / "src"
        src.mkdir()
        syncer = sync(src, tmp_dir / "dest")
        assert isinstance(syncer, Syncer)


class TestEntryFeatures:
    def test_entry_properties(self, tmp_dir):
        _tree(tmp_dir)
        entry = Entry.from_path(tmp_dir / "a.txt")
        assert entry.is_file
        assert not entry.is_dir
        assert entry.suffix == ".txt"
        assert entry.stem == "a"
        assert entry.size == 5
        assert entry.size_human

    def test_entry_directory(self, tmp_dir):
        _tree(tmp_dir)
        entry = Entry.from_path(tmp_dir / "sub")
        assert entry.is_dir
        assert not entry.is_file

    def test_entry_hash(self, tmp_dir):
        (tmp_dir / "a.txt").write_text("hello")
        entry = Entry.from_path(tmp_dir / "a.txt")
        assert len(entry.hash_sha256) == 64

    def test_from_path_missing(self, tmp_dir):
        with pytest.raises(FileNotFoundError):
            Entry.from_path(tmp_dir / "nope.txt")

    def test_entry_read_text(self, tmp_dir):
        (tmp_dir / "a.txt").write_text("hello")
        assert Entry.from_path(tmp_dir / "a.txt").read_text() == "hello"

    def test_entry_read_bytes(self, tmp_dir):
        (tmp_dir / "a.bin").write_bytes(b"\x00\x01")
        assert Entry.from_path(tmp_dir / "a.bin").read_bytes() == b"\x00\x01"

    def test_entry_created_accessed(self, tmp_dir):
        (tmp_dir / "a.txt").write_text("x")
        entry = Entry.from_path(tmp_dir / "a.txt")
        assert entry.created is not None
        assert entry.accessed is not None or entry.accessed == entry.modified

    def test_entry_is_hidden(self, tmp_dir):
        (tmp_dir / ".hidden").write_text("x")
        (tmp_dir / "visible.txt").write_text("x")
        assert Entry.from_path(tmp_dir / ".hidden").is_hidden is True
        assert Entry.from_path(tmp_dir / "visible.txt").is_hidden is False

    def test_entry_is_empty(self, tmp_dir):
        (tmp_dir / "empty.txt").write_text("")
        assert Entry.from_path(tmp_dir / "empty.txt").is_empty is True

    def test_from_stat_matches_from_path(self, tmp_dir):
        (tmp_dir / "a.txt").write_text("hello")
        e1 = Entry.from_path(tmp_dir / "a.txt")
        e2 = Entry.from_stat(tmp_dir / "a.txt", (tmp_dir / "a.txt").stat())
        assert e1.size == e2.size
