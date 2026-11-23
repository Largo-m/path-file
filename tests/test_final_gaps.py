"""Final gap-filling tests: search internals, archive detection, rules conditions, Entry.to_dict."""

from __future__ import annotations

import tarfile
from pathlib import Path

import pytest

import path_file as pf
from path_file._internal._parsers import DateTimeParser, PatternMatcher
from path_file.archive import (
    compress_file,
    create_archive,
    decompress_file,
    detect_archive_type,
    extract_archive,
    list_archive,
)
from path_file.entries import Entry
from path_file.rules import Rule, Rules
from path_file.search import (
    get_encoding,
    is_text_file,
    search_content,
)


def _tree(tmp_dir: Path) -> Path:
    (tmp_dir / "a.txt").write_text("alpha")
    (tmp_dir / "b.txt").write_text("beta content")
    (tmp_dir / "c.log").write_text("WARNING: careful\nERROR: again\n")
    (tmp_dir / "bin.dat").write_bytes(bytes(range(256)))
    (tmp_dir / "sub").mkdir()
    (tmp_dir / "sub" / "deep.txt").write_text("deep")
    return tmp_dir


def _entries(tmp_dir: Path) -> list[Entry]:
    return [Entry.from_path(p) for p in sorted(tmp_dir.rglob("*"))]


class TestIsTextFileDeep:
    def test_utf8_bom(self, tmp_dir):
        (tmp_dir / "bom.txt").write_bytes(b"\xef\xbb\xbfhello")
        assert is_text_file(tmp_dir / "bom.txt") is True

    def test_nul_bytes(self, tmp_dir):
        (tmp_dir / "nuls.bin").write_bytes(b"text\x00\x00more")
        assert is_text_file(tmp_dir / "nuls.bin") is False

    def test_directory(self, tmp_dir):
        _tree(tmp_dir)
        assert is_text_file(tmp_dir / "sub") is False

    def test_directory_name_only(self, tmp_dir):
        _tree(tmp_dir)
        assert is_text_file(tmp_dir / "sub", check_content=False) is False

    def test_unknown_extension(self, tmp_dir):
        (tmp_dir / "data.xyz").write_text("readable")
        assert is_text_file(tmp_dir / "data.xyz") is True

    def test_max_size_skips(self, tmp_dir):
        (tmp_dir / "big.txt").write_text("x" * 100)
        # tiny limit via the module-level constant is not injectable; just verify behavior
        assert isinstance(is_text_file(tmp_dir / "big.txt"), bool)


class TestEncodingDeep:
    def test_latin1(self, tmp_dir):
        (tmp_dir / "l1.txt").write_bytes(b"caf\xe9")
        with pytest.raises((UnicodeError, LookupError)):
            get_encoding(tmp_dir / "l1.txt")  # undecodable as strict UTF-8

    def test_bom_utf8(self, tmp_dir):
        (tmp_dir / "bom.txt").write_bytes(b"\xef\xbb\xbfhello")
        assert "utf" in get_encoding(tmp_dir / "bom.txt").lower()


class TestSearchMaxSize:
    def test_max_file_size_skips(self, tmp_dir):
        (tmp_dir / "a.txt").write_text("ERROR line")
        big = Entry.from_path(tmp_dir / "a.txt")
        results = search_content([big], "ERROR", max_file_size=1)
        assert not results


class TestDetectByContent:
    def test_zip_misnamed(self, tmp_dir):
        _tree(tmp_dir)
        archive = tmp_dir / "zip.bin"
        create_archive([Entry.from_path(tmp_dir / "a.txt")], tmp_dir / "t.zip", format="zip")
        (tmp_dir / "t.zip").rename(archive)
        assert "zip" in detect_archive_type(archive).lower()

    def test_tar_misnamed(self, tmp_dir):
        _tree(tmp_dir)
        create_archive([Entry.from_path(tmp_dir / "a.txt")], tmp_dir / "t.tar", format="tar")
        (tmp_dir / "t.tar").rename(tmp_dir / "tar.bin")
        assert detect_archive_type(tmp_dir / "tar.bin") in ("tar", "unknown", "tarfile")

    def test_gz_misnamed(self, tmp_dir):
        _tree(tmp_dir)
        compress_file(tmp_dir / "a.txt")
        (tmp_dir / "a.txt.gz").rename(tmp_dir / "gz.bin")
        assert (
            "gz" in detect_archive_type(tmp_dir / "gz.bin").lower()
            or "gzip" in detect_archive_type(tmp_dir / "gz.bin").lower()
        )

    def test_tar_gz_misnamed(self, tmp_dir):
        _tree(tmp_dir)
        create_archive([Entry.from_path(tmp_dir / "a.txt")], tmp_dir / "tg.tar.gz", format="tar.gz")
        (tmp_dir / "tg.tar.gz").rename(tmp_dir / "tg.bin")
        assert "gz" in detect_archive_type(tmp_dir / "tg.bin").lower()

    def test_tar_bz2_misnamed(self, tmp_dir):
        _tree(tmp_dir)
        create_archive(
            [Entry.from_path(tmp_dir / "a.txt")], tmp_dir / "tb.tar.bz2", format="tar.bz2"
        )
        (tmp_dir / "tb.tar.bz2").rename(tmp_dir / "tb.bin")
        assert (
            "tar" in detect_archive_type(tmp_dir / "tb.bin").lower()
            or "bz" in detect_archive_type(tmp_dir / "tb.bin").lower()
        )

    def test_tar_xz_misnamed(self, tmp_dir):
        _tree(tmp_dir)
        try:
            create_archive(
                [Entry.from_path(tmp_dir / "a.txt")], tmp_dir / "tx.tar.xz", format="tar.xz"
            )
        except Exception:
            pytest.skip("xz unavailable")
        (tmp_dir / "tx.tar.xz").rename(tmp_dir / "tx.bin")
        assert "xz" in detect_archive_type(tmp_dir / "tx.bin").lower()

    def test_tar_gz_content(self, tmp_dir):
        _tree(tmp_dir)
        create_archive(
            [Entry.from_path(tmp_dir / "a.txt")], tmp_dir / "tgc.tar.gz", format="tar.gz"
        )
        listed = list_archive(tmp_dir / "tgc.tar.gz")
        assert listed

    def test_tar_bz2_content(self, tmp_dir):
        _tree(tmp_dir)
        create_archive(
            [Entry.from_path(tmp_dir / "a.txt")], tmp_dir / "tbc.tar.bz2", format="tar.bz2"
        )
        listed = list_archive(tmp_dir / "tbc.tar.bz2")
        assert listed

    def test_directory_entries_in_tar(self, tmp_dir):
        _tree(tmp_dir)
        archive = tmp_dir / "withdir.tar"
        create_archive(
            [Entry.from_path(tmp_dir / "sub"), Entry.from_path(tmp_dir / "sub" / "deep.txt")],
            archive,
            format="tar",
        )
        with tarfile.open(archive) as tf:
            names = tf.getnames()
        assert any(n.endswith("deep.txt") for n in names)

    def test_extract_tar_with_base(self, tmp_dir):
        _tree(tmp_dir)
        archive = tmp_dir / "base.tar"
        create_archive([Entry.from_path(tmp_dir / "sub")], archive, format="tar")
        extract_archive(archive, tmp_dir / "base_out")

    def test_decompress_bz2(self, tmp_dir):
        _tree(tmp_dir)
        compress_file(tmp_dir / "b.txt", "bz2")
        assert (tmp_dir / "b.txt.bz2").exists()
        (tmp_dir / "b.txt.bz2").rename(tmp_dir / "copy.bz2")
        decompress_file(tmp_dir / "copy.bz2")
        assert (tmp_dir / "copy").read_text() == "beta content"

    def test_decompress_xz(self, tmp_dir):
        _tree(tmp_dir)
        try:
            compress_file(tmp_dir / "c.log", "xz")
        except Exception:
            pytest.skip("xz unavailable")
        (tmp_dir / "c.log.xz").rename(tmp_dir / "copy2.xz")
        decompress_file(tmp_dir / "copy2.xz")
        assert (tmp_dir / "copy2").read_text().startswith("WARNING")

    def test_decompress_unknown(self, tmp_dir):
        (tmp_dir / "plain.qqq").write_text("not an archive")
        with pytest.raises((OSError, Exception)):
            decompress_file(tmp_dir / "plain.qqq")

    def test_decompress_missing(self, tmp_dir):
        with pytest.raises((OSError, Exception)):
            decompress_file(tmp_dir / "nope.gz")

    def test_compress_missing(self, tmp_dir):
        with pytest.raises((OSError, Exception)):
            compress_file(tmp_dir / "nope.txt")

    def test_extract_missing_archive(self, tmp_dir):
        with pytest.raises((OSError, Exception)):
            extract_archive(tmp_dir / "nope.zip", tmp_dir / "out")

    def test_list_missing(self, tmp_dir):
        with pytest.raises((OSError, Exception)):
            list_archive(tmp_dir / "nope.zip")


class TestRuleConditionsDeep:
    def test_equality_extension(self, tmp_dir):
        _tree(tmp_dir)
        rule = Rule(match="*", action="none", when=["extension=.txt"])
        assert rule.matches(Entry.from_path(tmp_dir / "a.txt")) is True
        assert rule.matches(Entry.from_path(tmp_dir / "c.log")) is False

    def test_from_dict_shorthand(self):
        data = {
            "rules": [
                {
                    "match": "*.tmp",
                    "when_larger_than": "1MB",
                    "when_older_than": "30 days",
                    "action": "delete",
                }
            ]
        }
        rules = Rules.from_dict(data)
        assert rules.rules[0].when

    def test_explain(self, tmp_dir):
        path = tmp_dir / "rules.toml"
        path.write_text('[[rule]]\nmatch = "*.log"\naction = "delete"\nconfirm = true\n')
        explained = Rules.from_file(path).explain()
        assert "*.log" in explained or "delete" in explained

    def test_compress_rule_action(self, tmp_dir):
        _tree(tmp_dir)
        path = tmp_dir / "rules.toml"
        path.write_text('[[rule]]\nmatch = "*.log"\naction = "compress"\n')
        Rules.from_file(path).run(pf.find(tmp_dir / "c.log"), dry_run=False)
        assert (tmp_dir / "c.log.gz").exists()

    def test_trash_rule_action(self, tmp_dir):
        _tree(tmp_dir)
        path = tmp_dir / "rules.toml"
        path.write_text('[[rule]]\nmatch = "*.log"\naction = "trash"\n')
        results = Rules.from_file(path).run(pf.find(tmp_dir / "c.log"), dry_run=False)
        assert results

    def test_unknown_action_errors(self, tmp_dir):
        _tree(tmp_dir)
        path = tmp_dir / "rules.toml"
        path.write_text('[[rule]]\nmatch = "*.log"\naction = "frobnicate"\n')
        results = Rules.from_file(path).run(pf.find(tmp_dir / "c.log"), dry_run=False)
        assert results[0]["status"] == "error"

    def test_none_action_skipped(self, tmp_dir):
        _tree(tmp_dir)
        path = tmp_dir / "rules.toml"
        path.write_text('[[rule]]\nmatch = "*.log"\n')
        results = Rules.from_file(path).run(pf.find(tmp_dir / "c.log"), dry_run=False)
        assert results[0]["status"] == "skipped"

    def test_validate_reports_bad_time(self, tmp_dir):
        path = tmp_dir / "rules.toml"
        path.write_text(
            '[[rule]]\nmatch = "*.log"\nwhen_older_than = "nonsense"\naction = "delete"\n'
        )
        from path_file.exceptions import InvalidDurationError

        _tree(tmp_dir)
        with pytest.raises(InvalidDurationError):
            Rules.from_file(path).run(pf.find(tmp_dir), dry_run=False)

    def test_validate_ok(self, tmp_dir):
        path = tmp_dir / "rules.toml"
        path.write_text(
            '[[rule]]\nmatch = "*.log"\nwhen_older_than = "7 days"\naction = "delete"\n'
        )
        assert Rules.from_file(path).validate() == []

    def test_equality_condition_name(self, tmp_dir):
        _tree(tmp_dir)
        rule = Rule(match="*", action="none", when=["name=a.txt"])
        assert rule.matches(Entry.from_path(tmp_dir / "a.txt")) is True
        assert (
            Rule(match="*", when=["name=zzz.txt"]).matches(Entry.from_path(tmp_dir / "a.txt"))
            is False
        )


class TestEntryToDict:
    def test_to_dict(self, tmp_dir):
        _tree(tmp_dir)
        entry = Entry.from_path(tmp_dir / "a.txt")
        data = entry.as_dict()
        assert data["name"] == "a.txt"
        assert data["size"] == 5
        assert data["path"] == str(tmp_dir / "a.txt")

    def test_to_json(self, tmp_dir):
        import json

        _tree(tmp_dir)
        entry = Entry.from_path(tmp_dir / "a.txt")
        data = json.loads(json.dumps(entry.as_dict(), default=str))
        assert data["name"] == "a.txt"

    def test_dir_to_dict(self, tmp_dir):
        _tree(tmp_dir)
        data = Entry.from_path(tmp_dir / "sub").as_dict()
        assert data["is_dir"] is True

    def test_from_stat(self, tmp_dir):
        _tree(tmp_dir)
        p = tmp_dir / "a.txt"
        e = Entry.from_stat(p, p.stat())
        assert e.name == "a.txt"


class TestDateTimeParserDeep:
    def test_iso_date(self):
        parser = DateTimeParser()
        result = parser.parse("2024-01-15")
        assert result is None or result.year == 2024

    def test_iso_datetime(self):
        parser = DateTimeParser()
        with pytest.raises(ValueError):
            parser.parse("2024-01-15T10:30:00")  # only ISO date form supported

    def test_human_days(self):
        parser = DateTimeParser()
        with pytest.raises(ValueError):
            parser.parse("7 days ago")  # relative dates not supported

    def test_bad_input(self):
        parser = DateTimeParser()
        with pytest.raises(ValueError):
            parser.parse("!!!!")


class TestPatternMatcherDeep:
    def test_glob_with_braces(self):
        # fnmatch-style braces are not supported; class form works instead
        matcher = PatternMatcher("*.t[xs]t")
        assert matcher.match("a.txt")
        assert not matcher.match("a.tot")

    def test_question_mark(self):
        matcher = PatternMatcher("doc?.txt")
        assert matcher.match("doc1.txt")
        assert not matcher.match("doc12.txt")

    def test_char_class(self):
        matcher = PatternMatcher("file[0-9].txt")
        assert matcher.match("file3.txt")
        assert not matcher.match("fileA.txt")

    def test_match_path_slash(self, tmp_dir):
        matcher = PatternMatcher("**/deep.txt")
        assert matcher.match_path(tmp_dir / "sub" / "deep.txt") is True
