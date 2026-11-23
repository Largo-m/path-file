"""Tests for search.py content search and _internal/_safety.py guards."""

from __future__ import annotations

from pathlib import Path

import pytest

from path_file._internal._safety import (
    BackupManager,
    confirm_destructive,
    is_same_file,
    is_subpath,
    require_confirm_or_dry_run,
    safe_path,
    validate_dest,
    validate_source,
)
from path_file.exceptions import DestExistsError, DryRunRequiredError, PathflowError
from path_file.search import (
    get_encoding,
    grep,
    grep_text,
    is_text_file,
    search_bytes,
    search_content,
    search_regex,
    search_streaming,
)


def _tree(tmp_dir: Path) -> Path:
    (tmp_dir / "a.txt").write_text("hello world\nsecond line\nERROR: boom\n")
    (tmp_dir / "b.txt").write_text("nothing here\n")
    (tmp_dir / "c.log").write_text("WARNING: careful\nERROR: again\n")
    (tmp_dir / "bin.dat").write_bytes(bytes(range(256)))
    (tmp_dir / "utf16.txt").write_text("wide text", encoding="utf-16")
    (tmp_dir / "empty.txt").write_text("")
    return tmp_dir


def _entries(tmp_dir: Path) -> list:
    from path_file import Entry

    _tree(tmp_dir)
    return [Entry.from_path(p) for p in sorted(tmp_dir.rglob("*"))]


class TestIsTextFile:
    def test_text(self, tmp_dir):
        _tree(tmp_dir)
        assert is_text_file(tmp_dir / "a.txt") is True

    def test_binary(self, tmp_dir):
        _tree(tmp_dir)
        assert is_text_file(tmp_dir / "bin.dat") is False

    def test_empty(self, tmp_dir):
        _tree(tmp_dir)
        assert isinstance(is_text_file(tmp_dir / "empty.txt"), bool)

    def test_name_only(self, tmp_dir):
        (tmp_dir / "script.py").write_text("print(1)")
        assert is_text_file(tmp_dir / "script.py", check_content=False) is True

    def test_missing(self, tmp_dir):
        assert isinstance(is_text_file(tmp_dir / "nope.txt"), bool)


class TestGetEncoding:
    def test_utf8(self, tmp_dir):
        _tree(tmp_dir)
        assert get_encoding(tmp_dir / "a.txt") in ("utf-8", "ascii", "utf-8-sig")

    def test_utf16(self, tmp_dir):
        _tree(tmp_dir)
        assert "16" in get_encoding(tmp_dir / "utf16.txt").lower()

    def test_missing_raises(self, tmp_dir):
        with pytest.raises((OSError, UnicodeDecodeError, LookupError)):
            get_encoding(tmp_dir / "nope.txt")


class TestSearchContent:
    def test_basic(self, tmp_dir):
        results = search_content(_entries(tmp_dir), "ERROR")
        names = {r[0].name for r in results}
        assert "a.txt" in names
        assert "c.log" in names
        assert all(isinstance(r[1], list) for r in results)

    def test_no_match(self, tmp_dir):
        assert not search_content(_entries(tmp_dir), "zzz-not-present")

    def test_case_sensitive(self, tmp_dir):
        results = search_content(_entries(tmp_dir), "error", case_sensitive=True)
        assert not results
        assert search_content(_entries(tmp_dir), "error", case_sensitive=False)


class TestSearchRegex:
    def test_basic(self, tmp_dir):
        results = search_regex(_entries(tmp_dir), r"ERROR: \w+")
        assert results
        assert any(r[1] for r in results)

    def test_groups(self, tmp_dir):
        results = search_regex(_entries(tmp_dir), r"(ERROR|WARNING): (\w+)")
        assert results
        assert any(isinstance(m, tuple) for r in results for m in r[1])


class TestSearchBytes:
    def test_basic(self, tmp_dir):
        assert isinstance(search_bytes(_entries(tmp_dir), b"ERROR"), list)

    def test_binary_pattern(self, tmp_dir):
        assert isinstance(search_bytes(_entries(tmp_dir), b"\xff\xd8"), list)


class TestSearchStreaming:
    def test_basic(self, tmp_dir):
        results = list(search_streaming(_entries(tmp_dir), "ERROR"))
        assert results

    def test_no_match(self, tmp_dir):
        assert not list(search_streaming(_entries(tmp_dir), "zzz-not-present"))


class TestGrep:
    def test_grep_text(self, tmp_dir):
        out = grep_text(_entries(tmp_dir), "ERROR")
        assert out
        assert all(isinstance(r[0].name, str) for r in out)

    def test_grep_files(self, tmp_dir):
        from path_file import Entry

        _tree(tmp_dir)
        out = grep(
            [Entry.from_path(tmp_dir / "a.txt"), Entry.from_path(tmp_dir / "c.log")], r"ERROR"
        )
        assert out

    def test_grep_empty(self, tmp_dir):
        assert not grep([], "ERROR")


class TestSafetyValidation:
    def test_validate_source_exists(self, tmp_dir):
        (tmp_dir / "a.txt").write_text("x")
        assert validate_source(tmp_dir / "a.txt") == (tmp_dir / "a.txt")

    def test_validate_source_missing(self, tmp_dir):
        with pytest.raises((PathflowError, OSError)):
            validate_source(tmp_dir / "nope.txt")

    def test_validate_dest_new(self, tmp_dir):
        assert validate_dest(tmp_dir / "out") == tmp_dir / "out"

    def test_validate_dest_existing(self, tmp_dir):
        (tmp_dir / "out").mkdir()
        assert validate_dest(tmp_dir / "out", overwrite=True) == tmp_dir / "out"

    def test_validate_dest_conflict(self, tmp_dir):
        (tmp_dir / "out").mkdir()
        with pytest.raises((DestExistsError, PathflowError)):
            validate_dest(tmp_dir / "out", overwrite=False)

    def test_safe_path_inside(self, tmp_dir):
        assert safe_path(tmp_dir / "sub" / "f.txt", tmp_dir).is_relative_to(tmp_dir)

    def test_safe_path_escape(self, tmp_dir):
        with pytest.raises((PathflowError, ValueError)):
            safe_path("../../etc/passwd", tmp_dir)

    def test_is_subpath(self, tmp_dir):
        assert is_subpath(tmp_dir, tmp_dir / "sub") is True
        assert is_subpath(tmp_dir / "sub", tmp_dir) is False

    def test_is_same_file(self, tmp_dir):
        (tmp_dir / "a.txt").write_text("x")
        (tmp_dir / "a_link.txt").symlink_to(tmp_dir / "a.txt")
        assert is_same_file(tmp_dir / "a.txt", tmp_dir / "a_link.txt") is True
        assert is_same_file(tmp_dir / "a.txt", tmp_dir / "a.txt") is True

    def test_is_same_file_different(self, tmp_dir):
        (tmp_dir / "a.txt").write_text("x")
        (tmp_dir / "b.txt").write_text("y")
        assert is_same_file(tmp_dir / "a.txt", tmp_dir / "b.txt") is False


class TestConfirmation:
    def test_confirm_destructive_no(self):
        with pytest.raises(DryRunRequiredError):
            confirm_destructive("delete", 3, 3000, force=False, dry_run=False)

    def test_confirm_destructive_yes(self):
        assert confirm_destructive("delete", 3, 3000, force=True, dry_run=False) is True

    def test_confirm_destructive_dry_run(self):
        assert confirm_destructive("delete", 3, 3000, force=False, dry_run=True) is True
        assert confirm_destructive("delete", 0, 0) is True

    def test_require_confirm_raises(self):
        with pytest.raises(DryRunRequiredError):
            require_confirm_or_dry_run("delete", 3, 3000, False, False)

    def test_require_confirm_ok(self):
        require_confirm_or_dry_run("delete", 3, 3000, True, False)

    def test_require_dry_run_ok(self):
        require_confirm_or_dry_run("delete", 3, 3000, False, True)


class TestBackupManager:
    def test_backup_restore(self, tmp_dir):
        (tmp_dir / "a.txt").write_text("x")
        with BackupManager() as manager:
            (tmp_dir / "a.txt").write_text("changed")
            backup = manager.backup(tmp_dir / "a.txt")
            assert backup.exists()
            (tmp_dir / "a.txt").write_text("changed again")
            manager.restore_all()
            assert (tmp_dir / "a.txt").read_text() == "changed"

    def test_backup_clear(self, tmp_dir):
        (tmp_dir / "a.txt").write_text("x")
        with BackupManager() as manager:
            manager.backup(tmp_dir / "a.txt")
            manager.clear_backups()

    def test_backup_custom_dir(self, tmp_dir):
        (tmp_dir / "a.txt").write_text("x")
        backup_dir = tmp_dir / "backups"
        with BackupManager(backup_dir) as manager:
            manager.backup(tmp_dir / "a.txt")
            assert any(backup_dir.iterdir())
