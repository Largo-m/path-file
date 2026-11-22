"""Tests for filter functions."""

from __future__ import annotations

from pathlib import Path

import path_file as pf
from path_file.filters import (
    combine_filters,
    filter_between_sizes,
    filter_dirs,
    filter_empty,
    filter_extension,
    filter_extensions,
    filter_files,
    filter_glob,
    filter_hidden,
    filter_in_folder,
    filter_larger_than,
    filter_modified_today,
    filter_name_contains,
    filter_name_ends_with,
    filter_name_matches,
    filter_name_starts_with,
    filter_newer_than,
    filter_not_empty,
    filter_older_than,
    filter_readable,
    filter_smaller_than,
    filter_symlinks,
    filter_visible,
    filter_without_extension,
    negate_filter,
)


class TestBasicFilters:
    """Test basic type filters."""

    def test_filter_files(self, tmp_tree: Path):
        entries = pf.find(tmp_tree).to_list()
        filtered = [e for e in entries if filter_files()(e)]
        assert all(e.is_file for e in filtered)

    def test_filter_dirs(self, tmp_tree: Path):
        entries = pf.find(tmp_tree).to_list()
        filtered = [e for e in entries if filter_dirs()(e)]
        assert all(e.is_dir for e in filtered)

    def test_filter_symlinks(self, tmp_tree: Path):
        entries = pf.find(tmp_tree).to_list()
        filtered = [e for e in entries if filter_symlinks()(e)]
        # May be empty if no symlinks
        assert all(e.is_symlink for e in filtered)


class TestExtensionFilters:
    """Test extension-based filters."""

    def test_filter_extension(self, tmp_tree: Path):
        entries = pf.find(tmp_tree).to_list()
        filtered = [e for e in entries if filter_extension(".jpg")(e)]
        assert all(e.suffix == ".jpg" for e in filtered)

    def test_filter_extensions(self, tmp_tree: Path):
        entries = pf.find(tmp_tree).to_list()
        filtered = [e for e in entries if filter_extensions(".jpg", ".png")(e)]
        assert all(e.suffix in (".jpg", ".png") for e in filtered)

    def test_filter_without_extension(self, tmp_tree: Path):
        entries = pf.find(tmp_tree).to_list()
        filtered = [e for e in entries if filter_without_extension(".jpg")(e)]
        assert all(e.suffix != ".jpg" for e in filtered)


class TestSizeFilters:
    """Test size-based filters."""

    def test_filter_larger_than(self, tmp_tree: Path):
        entries = pf.find(tmp_tree).files().to_list()
        filtered = [e for e in entries if filter_larger_than("1KB")(e)]
        assert all(e.size > 1024 for e in filtered)

    def test_filter_smaller_than(self, tmp_tree: Path):
        entries = pf.find(tmp_tree).files().to_list()
        filtered = [e for e in entries if filter_smaller_than("1MB")(e)]
        assert all(e.size < 1024 * 1024 for e in filtered)

    def test_filter_between_sizes(self, tmp_tree: Path):
        entries = pf.find(tmp_tree).files().to_list()
        filtered = [e for e in entries if filter_between_sizes("1KB", "1MB")(e)]
        assert all(1024 <= e.size <= 1024 * 1024 for e in filtered)

    def test_filter_empty(self, tmp_tree: Path):
        entries = pf.find(tmp_tree).to_list()
        filtered = [e for e in entries if filter_empty()(e)]
        assert all(e.is_empty for e in filtered)

    def test_filter_not_empty(self, tmp_tree: Path):
        entries = pf.find(tmp_tree).to_list()
        filtered = [e for e in entries if filter_not_empty()(e)]
        assert all(not e.is_empty for e in filtered)


class TestTimeFilters:
    """Test time-based filters."""

    def test_filter_newer_than(self, tmp_tree: Path):
        entries = pf.find(tmp_tree).files().to_list()
        filtered = [e for e in entries if filter_newer_than("1 hour")(e)]
        # All fresh files should pass
        assert len(filtered) == len(entries)

    def test_filter_older_than(self, tmp_tree: Path):
        entries = pf.find(tmp_tree).files().to_list()
        filtered = [e for e in entries if filter_older_than("1 year")(e)]
        assert len(filtered) == 0

    def test_filter_modified_today(self, tmp_tree: Path):
        entries = pf.find(tmp_tree).files().to_list()
        filtered = [e for e in entries if filter_modified_today()(e)]
        assert len(filtered) == len(entries)


class TestNamePathFilters:
    """Test name and path filters."""

    def test_filter_name_contains(self, tmp_tree: Path):
        entries = pf.find(tmp_tree).to_list()
        filtered = [e for e in entries if filter_name_contains("file")(e)]
        assert all("file" in e.name.lower() for e in filtered)

    def test_filter_name_starts_with(self, tmp_tree: Path):
        entries = pf.find(tmp_tree).to_list()
        filtered = [e for e in entries if filter_name_starts_with("file")(e)]
        assert all(e.name.lower().startswith("file") for e in filtered)

    def test_filter_name_ends_with(self, tmp_tree: Path):
        entries = pf.find(tmp_tree).to_list()
        filtered = [e for e in entries if filter_name_ends_with(".txt")(e)]
        assert all(e.name.endswith(".txt") for e in filtered)

    def test_filter_name_matches(self, tmp_tree: Path):
        entries = pf.find(tmp_tree).to_list()
        filtered = [e for e in entries if filter_name_matches(r"file\d+\.txt")(e)]
        assert all(e.name.lower().startswith("file") and e.name.endswith(".txt") for e in filtered)

    def test_filter_in_folder(self, tmp_tree: Path):
        entries = pf.find(tmp_tree).to_list()
        filtered = [e for e in entries if filter_in_folder(tmp_tree / "docs")(e)]
        assert all(e.path.is_relative_to(tmp_tree / "docs") for e in filtered)


class TestVisibilityPermissionFilters:
    """Test visibility and permission filters."""

    def test_filter_hidden(self, tmp_tree: Path):
        entries = pf.find(tmp_tree).to_list()
        filtered = [e for e in entries if filter_hidden()(e)]
        assert all(e.is_hidden for e in filtered)

    def test_filter_visible(self, tmp_tree: Path):
        entries = pf.find(tmp_tree).to_list()
        filtered = [e for e in entries if filter_visible()(e)]
        assert all(not e.is_hidden for e in filtered)

    def test_filter_readable(self, tmp_tree: Path):
        entries = pf.find(tmp_tree).to_list()
        filtered = [e for e in entries if filter_readable()(e)]
        assert len(filtered) == len(entries)  # All should be readable


class TestCombineFilters:
    """Test filter combination helpers."""

    def test_combine_filters_and(self, tmp_tree: Path):
        entries = pf.find(tmp_tree).files().to_list()
        f1 = filter_extension(".txt")
        f2 = filter_larger_than("10")
        combined = combine_filters(f1, f2, operator="and")
        filtered = [e for e in entries if combined(e)]
        assert all(e.suffix == ".txt" and e.size > 10 for e in filtered)

    def test_combine_filters_or(self, tmp_tree: Path):
        entries = pf.find(tmp_tree).files().to_list()
        f1 = filter_extension(".txt")
        f2 = filter_extension(".jpg")
        combined = combine_filters(f1, f2, operator="or")
        filtered = [e for e in entries if combined(e)]
        assert all(e.suffix in (".txt", ".jpg") for e in filtered)

    def test_negate_filter(self, tmp_tree: Path):
        entries = pf.find(tmp_tree).files().to_list()
        f = filter_extension(".txt")
        negated = negate_filter(f)
        filtered = [e for e in entries if negated(e)]
        assert all(e.suffix != ".txt" for e in filtered)


class TestGlobFilter:
    """Test glob pattern filter."""

    def test_filter_glob(self, tmp_tree: Path):
        entries = pf.find(tmp_tree).to_list()
        filtered = [e for e in entries if filter_glob("*.txt")(e)]
        assert all(e.name.endswith(".txt") for e in filtered)
