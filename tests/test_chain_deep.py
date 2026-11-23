"""Deep tests for FileChain construction, filtering and terminal ops."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import path_file as pf
from path_file.chain import FileChain


def _tree(tmp_dir: Path) -> Path:
    (tmp_dir / "a.txt").write_text("alpha content")
    (tmp_dir / "b.txt").write_text("alpha content")  # duplicate of a
    (tmp_dir / "c.log").write_text("log line")
    (tmp_dir / "empty.txt").write_text("")
    (tmp_dir / ".hidden").write_text("hidden")
    sub = tmp_dir / "sub"
    sub.mkdir()
    (sub / "deep.txt").write_text("deep content")
    (sub / "deep.log").write_text("deep log")
    (sub / "deeper").mkdir()
    (sub / "deeper" / "deepest.txt").write_text("deepest content")
    return tmp_dir


class TestConstruction:
    def test_find_dir(self, tmp_dir):
        chain = pf.find(tmp_dir)
        assert isinstance(chain, FileChain)

    def test_find_str_path(self, tmp_dir):
        assert isinstance(pf.find(str(tmp_dir)), FileChain)

    def test_from_paths(self, tmp_dir):
        _tree(tmp_dir)
        chain = FileChain.from_paths([tmp_dir / "a.txt", tmp_dir / "c.log"])
        names = {e.name for e in chain}
        assert names == {"a.txt", "c.log"}

    def test_from_paths_missing(self, tmp_dir):
        with pytest.raises(FileNotFoundError):
            list(FileChain.from_paths([tmp_dir / "nope.txt"]))

    def test_from_entries(self, tmp_dir):
        _tree(tmp_dir)
        chain = FileChain.from_entries(list(pf.find(tmp_dir / "a.txt")))
        assert chain.count() == 1

    def test_from_entries_empty(self):
        assert list(FileChain.from_entries([])) == []

    def test_iter_protocol(self, tmp_dir):
        _tree(tmp_dir)
        chain = pf.find(tmp_dir / "a.txt")
        assert len(list(iter(chain))) == 1

    def test_len(self, tmp_dir):
        _tree(tmp_dir)
        assert len(pf.find(tmp_dir)) > 0

    def test_repr(self, tmp_dir):
        assert "FileChain" in repr(pf.find(tmp_dir))

    def test_order_dunder(self, tmp_dir):
        _tree(tmp_dir)
        assert pf.find(tmp_dir).count() > 0


class TestTypeFilters:
    def test_files(self, tmp_dir):
        _tree(tmp_dir)
        names = {e.name for e in pf.find(tmp_dir).files()}
        assert "sub" not in names
        assert "deep.txt" in names

    def test_dirs(self, tmp_dir):
        _tree(tmp_dir)
        names = {e.name for e in pf.find(tmp_dir).dirs()}
        assert names == {"sub", "deeper"}

    def test_all(self, tmp_dir):
        _tree(tmp_dir)
        assert pf.find(tmp_dir).all().count() == pf.find(tmp_dir).count()

    def test_symlinks(self, tmp_dir):
        _tree(tmp_dir)
        assert pf.find(tmp_dir).symlinks().count() == 0


class TestExtensionFilters:
    def test_with_extension(self, tmp_dir):
        _tree(tmp_dir)
        names = {e.name for e in pf.find(tmp_dir).with_extension("log")}
        assert names == {"c.log", "deep.log"}

    def test_with_extension_dot(self, tmp_dir):
        _tree(tmp_dir)
        assert "a.txt" in {e.name for e in pf.find(tmp_dir).with_extension(".txt")}

    def test_with_extensions(self, tmp_dir):
        _tree(tmp_dir)
        assert "a.txt" in {e.name for e in pf.find(tmp_dir).with_extensions("txt")}
        assert "c.log" in {e.name for e in pf.find(tmp_dir).with_extensions("txt", "log")}

    def test_without_extension(self, tmp_dir):
        _tree(tmp_dir)
        assert "c.log" not in {e.name for e in pf.find(tmp_dir).without_extension("log")}


class TestSizeFilters:
    def test_larger_than(self, tmp_dir):
        _tree(tmp_dir)
        names = {e.name for e in pf.find(tmp_dir).larger_than(5)}
        assert "c.log" in names

    def test_smaller_than(self, tmp_dir):
        _tree(tmp_dir)
        names = {e.name for e in pf.find(tmp_dir).smaller_than(13)}
        assert "empty.txt" in names

    def test_between_sizes(self, tmp_dir):
        _tree(tmp_dir)
        names = {e.name for e in pf.find(tmp_dir).between_sizes("1B", "1KB")}
        assert "c.log" in names

    def test_empty(self, tmp_dir):
        _tree(tmp_dir)
        assert {e.name for e in pf.find(tmp_dir).empty()} == {"empty.txt"}

    def test_not_empty(self, tmp_dir):
        _tree(tmp_dir)
        assert "empty.txt" not in {e.name for e in pf.find(tmp_dir).not_empty()}


class TestTimeFiltersChain:
    def test_newer_than(self, tmp_dir):
        _tree(tmp_dir)
        assert pf.find(tmp_dir).newer_than("1 minute").count() == pf.find(tmp_dir).count()

    def test_older_than(self, tmp_dir):
        _tree(tmp_dir)
        assert pf.find(tmp_dir).older_than("10 years").count() == 0

    def test_created_newer_than(self, tmp_dir):
        _tree(tmp_dir)
        assert pf.find(tmp_dir).created_newer_than("1 hour").count() == pf.find(tmp_dir).count()

    def test_created_older_than(self, tmp_dir):
        _tree(tmp_dir)
        assert pf.find(tmp_dir).created_older_than("10 years").count() == 0

    def test_modified_between(self, tmp_dir):
        _tree(tmp_dir)
        start = datetime.now() - timedelta(days=1)
        end = datetime.now() + timedelta(days=1)
        assert pf.find(tmp_dir).modified_between(start, end).count() > 0

    def test_created_between_str(self, tmp_dir):
        _tree(tmp_dir)
        assert pf.find(tmp_dir).created_between("2020-01-01", "2100-01-01").count() > 0

    def test_today_week_month(self, tmp_dir):
        _tree(tmp_dir)
        assert pf.find(tmp_dir).modified_today().count() == pf.find(tmp_dir).count()
        assert pf.find(tmp_dir).modified_this_week().count() > 0
        assert pf.find(tmp_dir).modified_this_month().count() > 0
        assert pf.find(tmp_dir).created_today().count() > 0
        assert pf.find(tmp_dir).created_this_week().count() > 0


class TestNameFiltersChain:
    def test_name_matches(self, tmp_dir):
        _tree(tmp_dir)
        assert {e.name for e in pf.find(tmp_dir).name_matches(r"a\.txt")} == {"a.txt"}

    def test_name_matches_regex(self, tmp_dir):
        _tree(tmp_dir)
        names = {e.name for e in pf.find(tmp_dir).name_matches_regex(r"^deep\.")}
        assert names == {"deep.txt", "deep.log"}

    def test_glob(self, tmp_dir):
        _tree(tmp_dir)
        names = {e.name for e in pf.find(tmp_dir).glob("*.log")}
        assert names == {"c.log", "deep.log"}

    def test_name_contains(self, tmp_dir):
        _tree(tmp_dir)
        assert "a.txt" in {e.name for e in pf.find(tmp_dir).name_contains("txt")}

    def test_name_starts_with(self, tmp_dir):
        _tree(tmp_dir)
        assert "a.txt" in {e.name for e in pf.find(tmp_dir).name_starts_with("a")}

    def test_name_ends_with(self, tmp_dir):
        _tree(tmp_dir)
        assert "c.log" in {e.name for e in pf.find(tmp_dir).name_ends_with(".log")}

    def test_path_contains(self, tmp_dir):
        _tree(tmp_dir)
        assert "deep.txt" in {e.name for e in pf.find(tmp_dir).path_contains("sub")}

    def test_path_matches(self, tmp_dir):
        _tree(tmp_dir)
        assert pf.find(tmp_dir).path_matches(r"sub.*").count() == 5

    def test_in_folder(self, tmp_dir):
        _tree(tmp_dir)
        assert pf.find(tmp_dir).in_folder(tmp_dir / "sub").count() == 5

    def test_not_in_folder(self, tmp_dir):
        _tree(tmp_dir)
        assert "deep.txt" not in {e.name for e in pf.find(tmp_dir).not_in_folder(tmp_dir / "sub")}


class TestContentFiltersChain:
    def test_matching_content(self, tmp_dir):
        _tree(tmp_dir)
        assert "a.txt" in {e.name for e in pf.find(tmp_dir).matching_content("alpha")}

    def test_matching_regex_in_content(self, tmp_dir):
        _tree(tmp_dir)
        assert "a.txt" in {e.name for e in pf.find(tmp_dir).matching_regex_in_content(r"alph.")}

    def test_containing_line(self, tmp_dir):
        _tree(tmp_dir)
        assert "c.log" in {e.name for e in pf.find(tmp_dir).containing_line("log line")}

    def test_containing_lines(self, tmp_dir):
        _tree(tmp_dir)
        assert "a.txt" in {e.name for e in pf.find(tmp_dir).containing_lines("alpha", "content")}

    def test_hidden(self, tmp_dir):
        _tree(tmp_dir)
        assert {e.name for e in pf.find(tmp_dir).hidden()} == {".hidden"}

    def test_visible(self, tmp_dir):
        _tree(tmp_dir)
        assert ".hidden" not in {e.name for e in pf.find(tmp_dir).visible()}

    def test_readable_writable(self, tmp_dir):
        _tree(tmp_dir)
        assert pf.find(tmp_dir).readable().count() > 0
        assert pf.find(tmp_dir).writable().count() > 0

    def test_executable(self, tmp_dir):
        _tree(tmp_dir)
        assert isinstance(pf.find(tmp_dir).executable().count(), int)


class TestContextFiltersChain:
    def test_unique_by_hash(self, tmp_dir):
        _tree(tmp_dir)
        names = {e.name for e in pf.find(tmp_dir).files().unique_by_hash()}
        assert "a.txt" not in names  # duplicate content is dropped
        assert "b.txt" not in names
        assert "c.log" in names

    def test_duplicate_content(self, tmp_dir):
        _tree(tmp_dir)
        names = {e.name for e in pf.find(tmp_dir).files().duplicate_content()}
        assert names == {"a.txt", "b.txt"}  # identical content

    def test_unique_by_name(self, tmp_dir):
        _tree(tmp_dir)
        assert "a.txt" in {e.name for e in pf.find(tmp_dir).unique_by_name()}

    def test_duplicates_by_hash_dict(self, tmp_dir):
        _tree(tmp_dir)
        dupes = pf.find(tmp_dir).files().duplicates_by_hash()
        assert any(len(v) == 2 for v in dupes.values())

    def test_duplicates_by_name_dict(self, tmp_dir):
        _tree(tmp_dir)
        dupes = pf.find(tmp_dir).duplicates_by_name()
        assert isinstance(dupes, dict)

    def test_same_size_as(self, tmp_dir):
        _tree(tmp_dir)
        assert "a.txt" in {e.name for e in pf.find(tmp_dir).same_size_as(tmp_dir / "a.txt")}

    def test_same_content_as(self, tmp_dir):
        _tree(tmp_dir)
        assert "b.txt" in {e.name for e in pf.find(tmp_dir).same_content_as(tmp_dir / "a.txt")}


class TestSorting:
    def test_sort_by_name(self, tmp_dir):
        _tree(tmp_dir)
        names = [e.name for e in pf.find(tmp_dir).sort_by("name")]
        assert names == sorted(names, key=str.lower)

    def test_sort_by_size(self, tmp_dir):
        _tree(tmp_dir)
        sizes = [e.size for e in pf.find(tmp_dir).sort_by("size")]
        assert sizes == sorted(sizes) and len(sizes) > 3

    def test_sort_by_date(self, tmp_dir):
        _tree(tmp_dir)
        assert pf.find(tmp_dir).sort_by("date").count() > 0

    def test_sort_by_path(self, tmp_dir):
        _tree(tmp_dir)
        assert pf.find(tmp_dir).sort_by("path").count() > 0

    def test_sort_desc(self, tmp_dir):
        _tree(tmp_dir)
        names = [e.name for e in pf.find(tmp_dir).sort_by("name", desc=True)]
        assert names == sorted(names, key=str.lower, reverse=True)

    def test_reverse(self, tmp_dir):
        _tree(tmp_dir)
        names = [e.name for e in pf.find(tmp_dir).sort_by("name").reverse()]
        assert names == sorted(names, key=str.lower, reverse=True)


class TestSlicing:
    def test_limit(self, tmp_dir):
        _tree(tmp_dir)
        assert pf.find(tmp_dir).limit(2).count() == 2

    def test_skip(self, tmp_dir):
        _tree(tmp_dir)
        assert pf.find(tmp_dir).skip(1).count() == pf.find(tmp_dir).count() - 1

    def test_slice(self, tmp_dir):
        _tree(tmp_dir)
        assert pf.find(tmp_dir).sort_by("name").slice(0, 2).count() == 2

    def test_deduplicate(self, tmp_dir):
        _tree(tmp_dir)
        assert pf.find(tmp_dir).deduplicate().count() == pf.find(tmp_dir).count()


class TestTerminals:
    def test_count_first_last(self, tmp_dir):
        _tree(tmp_dir)
        chain = pf.find(tmp_dir).sort_by("name")
        assert chain.count() == chain.to_list().__len__()
        assert chain.first() is not None
        assert chain.last() is not None

    def test_first_last_empty(self, tmp_dir):
        chain = pf.find(tmp_dir).glob("*.nothing")
        assert chain.first() is None
        assert chain.last() is None

    def test_to_paths(self, tmp_dir):
        _tree(tmp_dir)
        assert all(isinstance(p, Path) for p in pf.find(tmp_dir).to_paths())

    def test_to_dict(self, tmp_dir):
        _tree(tmp_dir)
        data = pf.find(tmp_dir / "a.txt").to_dict()
        assert data[0]["name"] == "a.txt"

    def test_to_json_string(self, tmp_dir):
        _tree(tmp_dir)
        data = json.loads(pf.find(tmp_dir / "a.txt").to_json())
        assert data[0]["name"] == "a.txt"

    def test_to_json_file(self, tmp_dir):
        _tree(tmp_dir)
        out = tmp_dir / "out.json"
        pf.find(tmp_dir / "a.txt").to_json(out)
        assert json.loads(out.read_text())[0]["name"] == "a.txt"

    def test_to_csv(self, tmp_dir):
        _tree(tmp_dir)
        assert "a.txt" in pf.find(tmp_dir).to_csv()

    def test_to_table(self, tmp_dir):
        _tree(tmp_dir)
        assert "a.txt" in pf.find(tmp_dir).to_table()

    def test_report(self, tmp_dir):
        _tree(tmp_dir)
        report = pf.find(tmp_dir).report()
        assert report.file_count >= 5

    def test_preview(self, tmp_dir):
        _tree(tmp_dir)
        pending = pf.find(tmp_dir).copy_to(tmp_dir / "preview_out")
        preview = pending.preview()
        assert "a.txt" in preview
        assert "DRY RUN" in preview
        assert not (tmp_dir / "preview_out").exists()


class TestFunctionalOps:
    def test_for_each(self, tmp_dir):
        _tree(tmp_dir)
        seen: list[str] = []
        result = pf.find(tmp_dir).for_each(lambda e: seen.append(e.name))
        assert len(seen) > 0
        assert isinstance(result, FileChain)

    def test_map(self, tmp_dir):
        _tree(tmp_dir)
        sizes = pf.find(tmp_dir).map(lambda e: e.size)
        assert all(isinstance(s, int) for s in sizes)

    def test_reduce(self, tmp_dir):
        _tree(tmp_dir)
        total = pf.find(tmp_dir).reduce(lambda acc, e: acc + e.size, 0)
        assert total > 0

    def test_execute_without_action(self, tmp_dir):
        _tree(tmp_dir)
        from path_file.exceptions import PathflowError

        with pytest.raises(PathflowError):
            pf.find(tmp_dir / "a.txt").execute()


class TestExecutionModifiers:
    def test_dry_run_flag(self, tmp_dir):
        _tree(tmp_dir)
        chain = pf.find(tmp_dir / "a.txt").copy_to(tmp_dir / "out").dry_run()
        result = chain.execute()
        assert result.dry_run

    def test_parallel_config(self, tmp_dir):
        _tree(tmp_dir)
        assert pf.find(tmp_dir).parallel(2)._parallel == 2

    def test_progress_config(self, tmp_dir):
        _tree(tmp_dir)
        assert pf.find(tmp_dir).progress()._progress is True

    def test_verbose_quiet(self, tmp_dir):
        _tree(tmp_dir)
        assert pf.find(tmp_dir).verbose()._verbose is True
        assert isinstance(pf.find(tmp_dir).quiet().count(), int)

    def test_on_error(self, tmp_dir):
        _tree(tmp_dir)
        assert pf.find(tmp_dir).on_error("collect")._on_error == "collect"

    def test_recursive_false(self, tmp_dir):
        _tree(tmp_dir)
        assert "deep.txt" not in {e.name for e in pf.find(tmp_dir).recursive(False)}

    def test_follow_symlinks(self, tmp_dir):
        _tree(tmp_dir)
        assert pf.find(tmp_dir).follow_symlinks()._follow_symlinks is True

    def test_max_depth_min_depth(self, tmp_dir):
        _tree(tmp_dir)
        assert "deep.txt" not in {e.name for e in pf.find(tmp_dir).max_depth(0)}
        assert pf.find(tmp_dir).min_depth(2).count() > 0

    def test_chaining_returns_new(self, tmp_dir):
        _tree(tmp_dir)
        base = pf.find(tmp_dir)
        assert base.files() is not base
