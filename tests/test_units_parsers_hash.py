"""Tests for units.py, _internal/_parsers.py and hash.py."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from path_file import Entry
from path_file._internal._parsers import (
    DateTimeParser,
    DurationParser,
    PatternMatcher,
    SizeParser,
    _compile_regex,
    make_glob_filter,
    make_regex_filter,
    make_size_filter,
    make_time_filter,
)
from path_file.exceptions import InvalidDurationError, InvalidSizeError
from path_file.hash import (
    find_duplicates,
    find_duplicates_by_name,
    find_duplicates_quick,
    hash_file,
    hash_file_fast,
    hash_files,
    read_checksums,
    verify_hash,
    verify_hashes,
    write_checksums,
)
from path_file.units import (
    human_ago,
    human_duration,
    human_size,
    parse_datetime,
    parse_duration,
    parse_size,
)


class TestParseSize:
    def test_bytes_plain(self):
        assert parse_size("100") == 100
        assert parse_size(512) == 512
        assert parse_size(1.5) == 1

    def test_units(self):
        assert parse_size("1kb") == 1024
        assert parse_size("1KB") == 1024
        assert parse_size("1kib") == 1024
        assert parse_size("1mb") == 1024**2
        assert parse_size("1MiB") == 1024**2
        assert parse_size("1 GB") == 1024**3
        assert parse_size("1GiB") == 1024**3
        assert parse_size("1tb") == 1024**4
        assert parse_size("1TiB") == 1024**4

    def test_spaces_and_b(self):
        assert parse_size("10 b") == 10
        assert parse_size("10B") == 10

    def test_decimal(self):
        assert parse_size("1.5KB") == 1536
        assert parse_size("2.5 MiB") == int(2.5 * 1024 * 1024)

    def test_invalid(self):
        for bad in ["abc", "10xb", "", "1 2 3"]:
            with pytest.raises((InvalidSizeError, ValueError)):
                parse_size(bad)

    def test_negative(self):
        with pytest.raises((InvalidSizeError, ValueError)):
            parse_size("-5")


class TestHumanSize:
    def test_basic(self):
        assert human_size(0) == "0 B"
        assert human_size(512) == "512 B"
        assert "KiB" in human_size(2048)
        assert "MiB" in human_size(5 * 1024 * 1024)

    def test_binary_and_decimal(self):
        assert human_size(1000, binary=False).endswith("B")
        assert human_size(1024, binary=True) != human_size(1024, binary=False)

    def test_precision(self):
        assert "." in human_size(1536, precision=1)

    def test_large(self):
        assert "GiB" in human_size(3 * 1024**3)


class TestParseDuration:
    def test_seconds(self):
        assert parse_duration("30s") == timedelta(seconds=30)
        assert parse_duration(45) == timedelta(seconds=45)

    def test_compound_units(self):
        assert parse_duration("2h") == timedelta(hours=2)
        assert parse_duration("7d") == timedelta(days=7)
        assert parse_duration("1w") == timedelta(weeks=1)
        assert parse_duration("3m") == timedelta(minutes=3)

    def test_compound_unsupported(self):
        for spec in ["1h30m", "1d2h"]:
            with pytest.raises(InvalidDurationError):
                parse_duration(spec)
        assert parse_duration("7 days") == timedelta(days=7)

    def test_passthrough(self):
        td = timedelta(days=3)
        assert parse_duration(td) is td

    def test_invalid(self):
        for bad in ["abc", "10x", ""]:
            with pytest.raises((InvalidDurationError, ValueError)):
                parse_duration(bad)


class TestHumanDuration:
    def test_basic(self):
        assert "2" in human_duration(timedelta(hours=2))
        assert "s" in human_duration(timedelta(seconds=45))

    def test_short(self):
        out = human_duration(timedelta(days=3, hours=4), short=True)
        assert out

    def test_zero(self):
        assert human_duration(timedelta(0))


class TestParseDatetime:
    def test_iso(self):
        assert parse_datetime("2026-01-15") == datetime(2026, 1, 15)

    def test_now_words(self):
        now = datetime.now()
        assert abs((parse_datetime("now") - now).total_seconds()) < 5

    def test_ago_unsupported(self):
        with pytest.raises(ValueError):
            parse_datetime("3 days ago")

    def test_passthrough(self):
        dt = datetime(2025, 5, 5)
        assert parse_datetime(dt) is dt

    def test_invalid(self):
        with pytest.raises((ValueError, Exception)):
            parse_datetime("not-a-date")


class TestHumanAgo:
    def test_just_now(self):
        assert human_ago(datetime.now())

    def test_ago(self):
        assert human_ago(datetime.now() - timedelta(hours=5))

    def test_future(self):
        assert human_ago(datetime.now() + timedelta(minutes=5))


class TestParsers:
    def test_compile_regex(self):
        compiled = _compile_regex("abc")
        assert compiled.match("abc")

    def test_compile_regex_flags(self):
        import re

        compiled = _compile_regex("abc", re.IGNORECASE)
        assert compiled.match("ABC")

    def test_pattern_matcher_glob(self):
        matcher = PatternMatcher("*.txt")
        assert matcher.match("a.txt")
        assert not matcher.match("a.log")

    def test_pattern_matcher_case(self):
        matcher = PatternMatcher("*.TXT", case_sensitive=True)
        assert not matcher.match("a.txt")

    def test_pattern_matcher_classes(self):
        matcher = PatternMatcher("file[0-9].dat")
        assert matcher.match("file7.dat")
        assert not matcher.match("fileA.dat")

    def test_pattern_matcher_question(self):
        matcher = PatternMatcher("a?c.txt")
        assert matcher.match("abc.txt")
        assert not matcher.match("ac.txt")

    def test_size_parser(self):
        parser = SizeParser()
        assert parser.parse("2KB") == 2048

    def test_duration_parser(self):
        parser = DurationParser()
        assert parser.parse("5m") == timedelta(minutes=5)

    def test_datetime_parser(self):
        parser = DateTimeParser()
        assert isinstance(parser.parse("2026-02-02"), datetime)

    def test_make_glob_filter(self):
        matcher = make_glob_filter("**/*.py")
        assert isinstance(matcher("x/y.py"), bool)

    def test_make_regex_filter(self):
        matcher = make_regex_filter(r"err\d+")
        assert not matcher("error42")
        assert not matcher("warning")
        assert make_regex_filter(r"\d+")("42")

    def test_make_size_filter(self):
        matcher = make_size_filter(min_size=10, max_size=20)
        assert matcher(15)
        assert not matcher(5)

    def test_make_time_filter(self):
        matcher = make_time_filter(min_time=datetime(2020, 1, 1))
        assert matcher(datetime.now())
        assert not matcher(datetime(2019, 1, 1))


class TestHash:
    def test_hash_file_default(self, tmp_dir):
        f = tmp_dir / "a.txt"
        f.write_text("hello")
        digest = hash_file(f)
        assert len(digest) == 64

    def test_hash_file_algorithms(self, tmp_dir):
        f = tmp_dir / "a.txt"
        f.write_text("hello")
        assert len(hash_file(f, algorithm="md5")) == 32
        assert len(hash_file(f, algorithm="sha1")) == 40
        assert len(hash_file(f, algorithm="sha512")) == 128

    def test_hash_file_fast(self, tmp_dir):
        f = tmp_dir / "a.bin"
        f.write_bytes(b"x" * 100)
        fast = hash_file_fast(f)
        assert isinstance(fast, str)

    def test_hash_files(self, tmp_dir):
        for i in range(3):
            (tmp_dir / f"f{i}.txt").write_text(f"data{i}")
        entries = [Entry.from_path(p) for p in sorted(tmp_dir.glob("*.txt"))]
        results = hash_files(entries)
        assert len(results) == 3

    def test_hash_files_parallel_false(self, tmp_dir):
        for i in range(2):
            (tmp_dir / f"p{i}.txt").write_text(f"data{i}")
        entries = [Entry.from_path(p) for p in sorted(tmp_dir.glob("*.txt"))]
        results = hash_files(entries, parallel=False)
        assert len(results) == 2

    def test_hash_file_missing(self, tmp_dir):
        from path_file.exceptions import HashError

        with pytest.raises(HashError):
            hash_file(tmp_dir / "nope.txt")

    def test_verify_hash(self, tmp_dir):
        f = tmp_dir / "a.txt"
        f.write_text("hello")
        digest = hash_file(f)
        assert verify_hash(f, digest)
        assert not verify_hash(f, "0" * 64)

    def test_verify_hashes(self, tmp_dir):
        f1 = tmp_dir / "a.txt"
        f1.write_text("a")
        f2 = tmp_dir / "b.txt"
        f2.write_text("b")
        h1 = hash_file(f1)
        results = verify_hashes({f1: h1, f2: "bad"})
        assert results[f1] is True
        assert results[f2] is False

    def test_find_duplicates(self, tmp_dir):
        (tmp_dir / "x.txt").write_text("same")
        (tmp_dir / "y.txt").write_text("same")
        (tmp_dir / "z.txt").write_text("other")
        entries = [Entry.from_path(p) for p in sorted(tmp_dir.glob("*.txt"))]
        dupes = find_duplicates(entries)
        assert len(dupes) == 1
        assert len(next(iter(dupes.values()))) == 2

    def test_find_duplicates_quick(self, tmp_dir):
        (tmp_dir / "x.txt").write_text("same")
        (tmp_dir / "y.txt").write_text("same")
        (tmp_dir / "z.txt").write_text("other")
        entries = [Entry.from_path(p) for p in sorted(tmp_dir.glob("*.txt"))]
        dupes = find_duplicates_quick(entries)
        assert len(dupes) == 1

    def test_find_duplicates_none(self, tmp_dir):
        (tmp_dir / "a.txt").write_text("1")
        (tmp_dir / "b.txt").write_text("2")
        entries = [Entry.from_path(p) for p in sorted(tmp_dir.glob("*.txt"))]
        assert find_duplicates(entries) == {}

    def test_find_duplicates_by_name(self, tmp_dir):
        (tmp_dir / "sub").mkdir()
        (tmp_dir / "sub" / "dup.txt").write_text("deep")
        (tmp_dir / "dup.txt").write_text("root")
        entries = [Entry.from_path(p) for p in sorted(tmp_dir.rglob("*.txt"))]
        dupes = find_duplicates_by_name(entries)
        assert "dup.txt" in dupes
        assert len(dupes["dup.txt"]) == 2

    def test_write_and_read_checksums(self, tmp_dir):
        (tmp_dir / "a.txt").write_text("a")
        (tmp_dir / "b.txt").write_text("b")
        entries = [Entry.from_path(p) for p in [tmp_dir / "a.txt", tmp_dir / "b.txt"]]
        out = tmp_dir / "SUMS.txt"
        write_checksums(entries, out)
        assert out.exists()
        read_back = read_checksums(out)
        assert len(read_back) == 2

    def test_read_checksums_missing(self, tmp_dir):
        with pytest.raises((OSError, FileNotFoundError)):
            read_checksums(tmp_dir / "nope.txt")

    def test_checksums_roundtrip_verify(self, tmp_dir):
        (tmp_dir / "a.txt").write_text("payload")
        f = tmp_dir / "a.txt"
        out = tmp_dir / "SUMS.txt"
        write_checksums([Entry.from_path(f)], out)
        assert read_checksums(out)[Path("a.txt")] == hash_file(f)
