"""Tests for FileChain core functionality."""

from __future__ import annotations

from pathlib import Path

import path_file as pf


class TestFileChainBasics:
    """Test basic FileChain operations."""

    def test_find_returns_chain(self, tmp_tree: Path):
        chain = pf.find(tmp_tree)
        assert isinstance(chain, pf.FileChain)
        assert chain.count() > 0

    def test_chain_iteration(self, tmp_tree: Path):
        chain = pf.find(tmp_tree)
        entries = list(chain)
        assert all(isinstance(e, pf.Entry) for e in entries)
        assert len(entries) == chain.count()

    def test_chain_len(self, tmp_tree: Path):
        chain = pf.find(tmp_tree)
        assert len(chain) == chain.count()

    def test_chain_repr(self, tmp_tree: Path):
        chain = pf.find(tmp_tree)
        repr_str = repr(chain)
        assert "FileChain" in repr_str
        assert str(chain.count()) in repr_str


class TestFileChainFilters:
    """Test FileChain filter methods."""

    def test_files_filter(self, tmp_tree: Path):
        chain = pf.find(tmp_tree).files()
        entries = chain.to_list()
        assert all(e.is_file for e in entries)
        assert chain.count() > 0

    def test_dirs_filter(self, tmp_tree: Path):
        chain = pf.find(tmp_tree).dirs()
        entries = chain.to_list()
        assert all(e.is_dir for e in entries)

    def test_extension_filter(self, tmp_tree: Path):
        chain = pf.find(tmp_tree).with_extension(".jpg")
        entries = chain.to_list()
        assert all(e.suffix == ".jpg" for e in entries)
        assert chain.count() >= 2  # image1.jpg, image2.jpg, photo1.jpg, photo2.jpg

    def test_extensions_filter(self, tmp_tree: Path):
        chain = pf.find(tmp_tree).with_extensions(".jpg", ".png")
        entries = chain.to_list()
        assert all(e.suffix in (".jpg", ".png") for e in entries)

    def test_without_extension(self, tmp_tree: Path):
        chain = pf.find(tmp_tree).without_extension(".jpg")
        entries = chain.to_list()
        assert all(e.suffix != ".jpg" for e in entries)

    def test_size_filters(self, tmp_tree: Path):
        # larger_than
        chain = pf.find(tmp_tree).files().larger_than("1KB")
        entries = chain.to_list()
        assert all(e.size > 1024 for e in entries)

        # smaller_than
        chain = pf.find(tmp_tree).files().smaller_than("1MB")
        entries = chain.to_list()
        assert all(e.size < 1024 * 1024 for e in entries)

        # between_sizes
        chain = pf.find(tmp_tree).files().between_sizes("1KB", "1MB")
        entries = chain.to_list()
        assert all(1024 < e.size < 1024 * 1024 for e in entries)

    def test_time_filters(self, tmp_tree: Path):
        chain = pf.find(tmp_tree).files().newer_than("1 hour")
        entries = chain.to_list()
        # All fresh files should pass (modified within last hour)
        assert len(entries) > 0

        chain = pf.find(tmp_tree).files().older_than("1 year")
        entries = chain.to_list()
        # Should be empty for fresh files
        assert len(entries) == 0

    def test_name_filters(self, tmp_tree: Path):
        # name_contains
        chain = pf.find(tmp_tree).name_contains("file")
        entries = chain.to_list()
        assert all("file" in e.name.lower() for e in entries)

        # name_starts_with
        chain = pf.find(tmp_tree).name_starts_with("file")
        entries = chain.to_list()
        assert all(e.name.lower().startswith("file") for e in entries)

        # name_ends_with
        chain = pf.find(tmp_tree).name_ends_with(".txt")
        entries = chain.to_list()
        assert all(e.name.endswith(".txt") for e in entries)

        # name_matches (regex)
        chain = pf.find(tmp_tree).name_matches(r"file\d+\.txt")
        entries = chain.to_list()
        assert all(e.name.lower().startswith("file") and e.name.endswith(".txt") for e in entries)

    def test_path_filters(self, tmp_tree: Path):
        chain = pf.find(tmp_tree).path_contains("docs")
        entries = chain.to_list()
        assert all("docs" in str(e.path) for e in entries)

    def test_folder_filters(self, tmp_tree: Path):
        chain = pf.find(tmp_tree).in_folder(tmp_tree / "docs")
        entries = chain.to_list()
        assert all(e.path.is_relative_to(tmp_tree / "docs") for e in entries)

    def test_visibility_filters(self, tmp_tree: Path):
        chain = pf.find(tmp_tree).hidden()
        entries = chain.to_list()
        assert all(e.is_hidden for e in entries)

        chain = pf.find(tmp_tree).visible()
        entries = chain.to_list()
        assert all(not e.is_hidden for e in entries)

    def test_empty_filters(self, tmp_tree: Path):
        chain = pf.find(tmp_tree).empty()
        entries = chain.to_list()
        assert all(e.is_empty for e in entries)

        chain = pf.find(tmp_tree).not_empty()
        entries = chain.to_list()
        assert all(not e.is_empty for e in entries)

    def test_permission_filters(self, tmp_tree: Path):
        chain = pf.find(tmp_tree).readable()
        entries = chain.to_list()
        assert all(e.path.stat().st_mode & 0o400 for e in entries)


class TestFileChainSorting:
    """Test FileChain sorting and limiting."""

    def test_sort_by_name(self, tmp_tree: Path):
        chain = pf.find(tmp_tree).files().sort_by("name")
        entries = chain.to_list()
        names = [e.name for e in entries]
        assert names == sorted(names, key=str.lower)

    def test_sort_by_size(self, tmp_tree: Path):
        chain = pf.find(tmp_tree).files().sort_by("size", desc=True)
        entries = chain.to_list()
        sizes = [e.size for e in entries]
        assert sizes == sorted(sizes, reverse=True)

    def test_sort_by_date(self, tmp_tree: Path):
        chain = pf.find(tmp_tree).files().sort_by("date", desc=True)
        entries = chain.to_list()
        dates = [e.modified for e in entries]
        assert dates == sorted(dates, reverse=True)

    def test_reverse(self, tmp_tree: Path):
        chain = pf.find(tmp_tree).files().sort_by("name").reverse()
        entries = chain.to_list()
        names = [e.name for e in entries]
        assert names == sorted(names, key=str.lower, reverse=True)

    def test_limit(self, tmp_tree: Path):
        chain = pf.find(tmp_tree).files().limit(3)
        assert chain.count() == 3

    def test_skip(self, tmp_tree: Path):
        chain = pf.find(tmp_tree).files().sort_by("name").skip(2)
        entries = chain.to_list()
        all_entries = pf.find(tmp_tree).files().sort_by("name").to_list()
        assert entries == all_entries[2:]

    def test_slice(self, tmp_tree: Path):
        chain = pf.find(tmp_tree).files().sort_by("name").slice(1, 4)
        entries = chain.to_list()
        all_entries = pf.find(tmp_tree).files().sort_by("name").to_list()
        assert entries == all_entries[1:4]


class TestFileChainMaterialization:
    """Test FileChain materialization methods."""

    def test_to_list(self, tmp_tree: Path):
        entries = pf.find(tmp_tree).files().to_list()
        assert isinstance(entries, list)
        assert all(isinstance(e, pf.Entry) for e in entries)

    def test_to_paths(self, tmp_tree: Path):
        paths = pf.find(tmp_tree).files().to_paths()
        assert isinstance(paths, list)
        assert all(isinstance(p, Path) for p in paths)

    def test_to_dict(self, tmp_tree: Path):
        data = pf.find(tmp_tree).files().to_dict()
        assert isinstance(data, list)
        assert all(isinstance(d, dict) for d in data)

    def test_to_json(self, tmp_tree: Path):
        json_str = pf.find(tmp_tree).files().limit(2).to_json()
        assert isinstance(json_str, str)
        import json

        data = json.loads(json_str)
        assert len(data) == 2

    def test_to_csv(self, tmp_tree: Path):
        csv_str = pf.find(tmp_tree).files().limit(2).to_csv()
        assert isinstance(csv_str, str)
        lines = csv_str.strip().split("\n")
        assert len(lines) == 3  # header + 2 rows

    def test_to_table(self, tmp_tree: Path):
        table = pf.find(tmp_tree).files().limit(3).to_table()
        assert isinstance(table, str)
        assert "FILE" in table

    def test_first_last(self, tmp_tree: Path):
        chain = pf.find(tmp_tree).files().sort_by("name")
        first = chain.first()
        last = chain.last()
        assert first is not None
        assert last is not None
        assert first.name <= last.name

    def test_count(self, tmp_tree: Path):
        count = pf.find(tmp_tree).files().count()
        assert isinstance(count, int)
        assert count > 0


class TestFileChainExecutionModifiers:
    """Test FileChain execution modifiers."""

    def test_dry_run(self, tmp_tree: Path):
        chain = pf.find(tmp_tree).files().dry_run(True)
        assert chain._dry_run is True

    def test_parallel(self, tmp_tree: Path):
        chain = pf.find(tmp_tree).files().parallel(4)
        assert chain._parallel == 4

    def test_progress(self, tmp_tree: Path):
        chain = pf.find(tmp_tree).files().progress(True)
        assert chain._progress is True

    def test_verbose_quiet(self, tmp_tree: Path):
        chain = pf.find(tmp_tree).files().verbose(True)
        assert chain._verbose is True

        chain = pf.find(tmp_tree).files().quiet(True)
        assert chain._verbose is False

    def test_on_error(self, tmp_tree: Path):
        chain = pf.find(tmp_tree).files().on_error("skip")
        assert chain._on_error == "skip"

        chain = pf.find(tmp_tree).files().on_error("collect")
        assert chain._on_error == "collect"


class TestFileChainImmutability:
    """Test that FileChain is immutable."""

    def test_filters_return_new_chain(self, tmp_tree: Path):
        chain1 = pf.find(tmp_tree)
        chain2 = chain1.files()
        chain3 = chain2.with_extension(".txt")

        assert chain1 is not chain2
        assert chain2 is not chain3
        assert chain1._filters != chain2._filters
        assert chain2._filters != chain3._filters

    def test_config_returns_new_chain(self, tmp_tree: Path):
        chain1 = pf.find(tmp_tree)
        chain2 = chain1.dry_run(True)
        chain3 = chain1.parallel(4)

        assert chain1 is not chain2
        assert chain1._dry_run != chain2._dry_run
        assert chain1._parallel != chain3._parallel


class TestEntryPoints:
    """Test alternative entry points."""

    def test_scan(self, tmp_tree: Path):
        chain = pf.scan(tmp_tree)
        assert isinstance(chain, pf.FileChain)

    def test_current(self, tmp_tree: Path):
        import os

        original = os.getcwd()
        try:
            os.chdir(tmp_tree)
            chain = pf.current()
            assert chain.count() > 0
        finally:
            os.chdir(original)
