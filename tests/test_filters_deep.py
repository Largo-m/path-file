"""Deep tests for filter factories and combination helpers."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from path_file import Entry
from path_file.filters import (
    _ContextFilter,
    combine_filters,
    filter_all,
    filter_between_sizes,
    filter_containing_line,
    filter_containing_lines,
    filter_created_newer_than,
    filter_created_older_than,
    filter_created_this_week,
    filter_created_today,
    filter_dirs,
    filter_duplicates_by_hash,
    filter_duplicates_by_name,
    filter_empty,
    filter_executable,
    filter_extension,
    filter_extensions,
    filter_files,
    filter_glob,
    filter_hidden,
    filter_in_folder,
    filter_larger_than,
    filter_matching_content,
    filter_matching_regex_in_content,
    filter_modified_between,
    filter_modified_this_month,
    filter_modified_this_week,
    filter_modified_today,
    filter_name_contains,
    filter_name_ends_with,
    filter_name_matches,
    filter_name_starts_with,
    filter_newer_than,
    filter_not_empty,
    filter_not_in_folder,
    filter_older_than,
    filter_path_contains,
    filter_path_matches,
    filter_readable,
    filter_same_content_as,
    filter_same_size_as,
    filter_smaller_than,
    filter_symlinks,
    filter_unique_by_hash,
    filter_unique_by_name,
    filter_visible,
    filter_writable,
    negate_filter,
)


@pytest.fixture
def entries(tmp_dir: Path) -> list[Entry]:
    (tmp_dir / "a.txt").write_text("hello world")
    (tmp_dir / "b.log").write_text("log entry\nsecond line")
    (tmp_dir / "empty.txt").write_text("")
    (tmp_dir / ".hidden").write_text("secret")
    (tmp_dir / "data.bin").write_bytes(b"\x00\x01")
    sub = tmp_dir / "sub"
    sub.mkdir()
    (sub / "deep.txt").write_text("deep")
    return [Entry.from_path(p) for p in sorted(tmp_dir.rglob("*"))]


def by_name(entries: list[Entry]) -> set[str]:
    return {e.name for e in entries}


class TestTypeFilters:
    def test_filter_files(self, entries):
        assert ".hidden" in by_name([e for e in entries if filter_files()(e)])
        assert "sub" not in by_name([e for e in entries if filter_files()(e)])

    def test_filter_dirs(self, entries):
        assert by_name([e for e in entries if filter_dirs()(e)]) == {"sub"}

    def test_filter_all(self, entries):
        assert all(filter_all()(e) for e in entries)

    def test_filter_symlinks_none(self, entries):
        assert all(not filter_symlinks()(e) for e in entries)


class TestExtensionFilters:
    def test_extension(self, entries):
        got = by_name([e for e in entries if filter_extension("txt")(e)])
        assert "a.txt" in got and "deep.txt" in got

    def test_extension_dot(self, entries):
        got = by_name([e for e in entries if filter_extension(".log")(e)])
        assert "b.log" in got

    def test_extensions_multi(self, entries):
        got = by_name([e for e in entries if filter_extensions("txt", "bin")(e)])
        assert {"a.txt", "data.bin"} <= got

    def test_without_extension(self, entries):
        got = by_name([e for e in entries if filter_extension("txt")(e)])
        assert "b.log" not in got


class TestSizeFilters:
    def test_larger_than(self, entries):
        got = by_name([e for e in entries if filter_larger_than(6)(e)])
        assert "b.log" in got
        assert "empty.txt" not in got

    def test_smaller_than(self, entries):
        got = by_name([e for e in entries if filter_smaller_than(5)(e)])
        assert "empty.txt" in got

    def test_between(self, entries):
        got = by_name([e for e in entries if filter_between_sizes(10, 12)(e)])
        assert "a.txt" in got

    def test_larger_than_str(self, entries):
        got = by_name([e for e in entries if filter_larger_than("1B")(e)])
        assert "b.log" in got


class TestEmptiness:
    def test_empty(self, entries):
        assert by_name([e for e in entries if filter_empty()(e)]) == {"empty.txt"}

    def test_not_empty(self, entries):
        assert "empty.txt" not in by_name([e for e in entries if filter_not_empty()(e)])
        assert "a.txt" in by_name([e for e in entries if filter_not_empty()(e)])


class TestTimeFilters:
    def test_newer_than(self, entries):
        got = by_name([e for e in entries if filter_newer_than("1 minute")(e)])
        assert "a.txt" in got

    def test_older_than(self, entries):
        got = by_name([e for e in entries if filter_older_than("10 years")(e)])
        assert not got  # fresh files are not older than 10 years
        recent = by_name([e for e in entries if filter_older_than("10 seconds")(e)])
        assert not recent

    def test_created_newer_than(self, entries):
        assert isinstance(filter_created_newer_than("1 hour")(entries[0]), bool)

    def test_created_older_than(self, entries):
        assert isinstance(filter_created_older_than("1 hour")(entries[0]), bool)

    def test_modified_between(self, entries):
        past = datetime.now() - timedelta(days=2)
        future = datetime.now() + timedelta(days=2)
        got = by_name([e for e in entries if filter_modified_between(past, future)(e)])
        assert "a.txt" in got

    def test_today_week_month(self, entries):
        assert isinstance(filter_modified_today()(entries[0]), bool)
        assert isinstance(filter_modified_this_week()(entries[0]), bool)
        assert isinstance(filter_modified_this_month()(entries[0]), bool)
        assert isinstance(filter_created_today()(entries[0]), bool)
        assert isinstance(filter_created_this_week()(entries[0]), bool)


class TestNameFilters:
    def test_name_matches(self, entries):
        got = by_name([e for e in entries if filter_name_matches(r"a\.txt")(e)])
        assert got == {"a.txt"}

    def test_name_contains(self, entries):
        got = by_name([e for e in entries if filter_name_contains("txt")(e)])
        assert {"a.txt", "empty.txt"} <= got

    def test_name_contains_case(self, entries):
        got = by_name([e for e in entries if filter_name_contains("TXT", case_sensitive=True)(e)])
        assert not got

    def test_name_starts_with(self, entries):
        got = by_name([e for e in entries if filter_name_starts_with("d")(e)])
        assert "deep.txt" in got

    def test_name_ends_with(self, entries):
        got = by_name([e for e in entries if filter_name_ends_with(".bin")(e)])
        assert "data.bin" in got


class TestPathFilters:
    def test_path_contains(self, entries):
        got = by_name([e for e in entries if filter_path_contains("sub")(e)])
        assert "deep.txt" in got

    def test_path_matches(self, entries):
        got = by_name([e for e in entries if filter_path_matches(r"sub.*")(e)])
        assert "deep.txt" in got

    def test_in_folder_relative_resolves_cwd(self, entries):
        got = by_name([e for e in entries if filter_in_folder("sub")(e)])
        assert not got  # relative folders resolve against the CWD, not the tree

    def test_in_folder_absolute(self, entries, tmp_dir):
        got = by_name([e for e in entries if filter_in_folder(tmp_dir / "sub")(e)])
        assert "deep.txt" in got

    def test_not_in_folder(self, entries, tmp_dir):
        got = by_name([e for e in entries if filter_not_in_folder(tmp_dir / "sub")(e)])
        assert "deep.txt" not in got
        assert "a.txt" in got


class TestVisibilityPermission:
    def test_hidden(self, entries):
        assert by_name([e for e in entries if filter_hidden()(e)]) == {".hidden"}

    def test_visible(self, entries):
        assert ".hidden" not in by_name([e for e in entries if filter_visible()(e)])

    def test_readable_writable(self, entries):
        assert all(filter_readable()(e) for e in entries if e.is_file)
        assert all(filter_writable()(e) for e in entries if e.is_file)

    def test_executable(self, entries):
        assert isinstance(filter_executable()(entries[0]), bool)


class TestContentFilters:
    def test_matching_content(self, entries):
        got = by_name([e for e in entries if filter_matching_content("hello")(e)])
        assert "a.txt" in got

    def test_matching_regex(self, entries):
        got = by_name([e for e in entries if filter_matching_regex_in_content(r"wor.d")(e)])
        assert "a.txt" in got

    def test_containing_line(self, entries):
        got = by_name([e for e in entries if filter_containing_line("second line")(e)])
        assert "b.log" in got

    def test_containing_lines_all(self, entries):
        got = by_name([e for e in entries if filter_containing_lines("hello", "world")(e)])
        assert "a.txt" in got
        assert "b.log" not in got


class TestContextFilters:
    def test_duplicates_by_hash(self, entries):
        f = filter_duplicates_by_hash()
        assert getattr(f, "_needs_context", False) is True
        assert f(entries[0]) is True

    def test_unique_by_hash(self, entries):
        assert filter_unique_by_hash()(entries[0]) is True

    def test_duplicates_by_name(self, entries):
        assert filter_duplicates_by_name()(entries[0]) is True

    def test_unique_by_name(self, entries):
        assert filter_unique_by_name()(entries[0]) is True

    def test_context_filter_direct(self):
        cf = _ContextFilter("duplicates_by_hash", "md5")
        assert cf.mode == "duplicates_by_hash"
        assert cf(Path("x")) is True


class TestSameAsFilters:
    def test_same_size_as(self, entries, tmp_dir):
        ref = tmp_dir / "a.txt"
        got = by_name([e for e in entries if filter_same_size_as(ref)(e)])
        assert "a.txt" in got

    def test_same_size_as_missing(self, entries, tmp_dir):
        ref = tmp_dir / "nope.txt"
        got = by_name([e for e in entries if filter_same_size_as(ref)(e)])
        assert not got

    def test_same_content_as(self, entries, tmp_dir):
        ref = tmp_dir / "a.txt"
        got = by_name([e for e in entries if filter_same_content_as(ref)(e)])
        assert "a.txt" in got

    def test_same_content_as_missing(self, entries, tmp_dir):
        got = by_name([e for e in entries if filter_same_content_as(tmp_dir / "nope.txt")(e)])
        assert not got


class TestGlob:
    def test_glob_name(self, entries):
        got = by_name([e for e in entries if filter_glob("*.txt")(e)])
        assert "a.txt" in got
        assert "b.log" not in got

    def test_glob_path(self, entries):
        got = by_name([e for e in entries if filter_glob("*sub*")(e)])
        assert "deep.txt" in got

    def test_glob_case_sensitive(self, entries):
        got = by_name([e for e in entries if filter_glob("*.TXT", case_sensitive=True)(e)])
        assert not got


class TestCombination:
    def test_and(self, entries):
        combined = combine_filters(filter_files(), filter_extension("txt"), operator="and")
        got = by_name([e for e in entries if combined(e)])
        assert got == {"a.txt", "empty.txt", "deep.txt"}

    def test_or(self, entries):
        combined = combine_filters(filter_extension("log"), filter_extension("bin"), operator="or")
        got = by_name([e for e in entries if combined(e)])
        assert got == {"b.log", "data.bin"}

    def test_negate(self, entries):
        neg = negate_filter(filter_files())
        got = by_name([e for e in entries if neg(e)])
        assert got == {"sub"}

    def test_combine_empty_and(self, entries):
        combined = combine_filters(operator="and")
        assert all(combined(e) for e in entries)
