"""Tests for content search functionality."""

from __future__ import annotations

from pathlib import Path

import path_file as pf
from path_file.search import get_encoding, is_text_file, search_content, search_regex


class TestIsTextFile:
    """Test text file detection."""

    def test_text_files_detected(self, sample_files: Path):
        for f in ["utf8.txt", "ascii.txt", "latin1.txt"]:
            path = sample_files / f
            assert is_text_file(path) is True

    def test_binary_files_rejected(self, sample_files: Path):
        assert is_text_file(sample_files / "binary.bin") is False

    def test_empty_file(self, sample_files: Path):
        # Empty file should be considered text
        assert is_text_file(sample_files / "empty.bin") is True


class TestGetEncoding:
    """Test encoding detection."""

    def test_utf8_detected(self, sample_files: Path):
        assert get_encoding(sample_files / "utf8.txt") == "utf-8"

    def test_latin1_fallback(self, sample_files: Path):
        assert get_encoding(sample_files / "latin1.txt") == "latin-1"


class TestSearchContent:
    """Test search_content function."""

    def test_search_simple_text(self, sample_files: Path):
        # Create a file with known content
        test_file = sample_files / "search_test.txt"
        test_file.write_text("Hello world\nThis is a test\nAnother line")

        entries = pf.find(sample_files).files().to_list()
        results = search_content(entries, "test")

        assert len(results) == 1
        entry, lines = results[0]
        assert entry.path.name == "search_test.txt"
        assert 2 in lines  # Line 2 contains "test"

    def test_search_case_insensitive(self, sample_files: Path):
        test_file = sample_files / "search_case.txt"
        test_file.write_text("HELLO WORLD\nhello world")

        entries = [pf.Entry.from_path(test_file)]
        results = search_content(entries, "hello", case_sensitive=False)

        assert len(results) == 1
        _entry, lines = results[0]
        assert set(lines) == {1, 2}

    def test_search_case_sensitive(self, sample_files: Path):
        test_file = sample_files / "search_case.txt"
        test_file.write_text("HELLO WORLD\nhello world")

        entries = pf.find(sample_files).files().to_list()
        results = search_content(entries, "HELLO", case_sensitive=True)

        assert len(results) == 1
        _entry, lines = results[0]
        assert lines == [1]

    def test_search_multiple_matches(self, sample_files: Path):
        test_file = sample_files / "multi_match.txt"
        test_file.write_text("foo\nbar\nfoo\nbaz\nfoo")

        entries = pf.find(sample_files).files().to_list()
        results = search_content(entries, "foo")

        assert len(results) == 1
        _entry, lines = results[0]
        assert lines == [1, 3, 5]

    def test_search_no_matches(self, sample_files: Path):
        test_file = sample_files / "no_match.txt"
        test_file.write_text("nothing here")

        entries = pf.find(sample_files).files().to_list()
        results = search_content(entries, "xyzzy")

        assert len(results) == 0

    def test_search_skips_binary(self, sample_files: Path):
        entries = pf.find(sample_files).files().to_list()
        results = search_content(entries, "test")

        # Should not crash on binary files
        binary_results = [r for r in results if "binary" in r[0].name]
        assert len(binary_results) == 0


class TestSearchRegex:
    """Test search_regex function."""

    def test_search_regex_basic(self, sample_files: Path):
        test_file = sample_files / "regex_test.txt"
        test_file.write_text("error: something went wrong\nwarning: deprecated\ninfo: all good")

        entries = pf.find(sample_files).files().to_list()
        results = search_regex(entries, r"error|warning")

        assert len(results) == 1
        _entry, matches = results[0]
        assert len(matches) == 2
        assert matches[0][0] == 1  # Line 1
        assert "error" in matches[0][1]
        assert matches[1][0] == 2  # Line 2
        assert "warning" in matches[1][1]

    def test_search_regex_with_groups(self, sample_files: Path):
        test_file = sample_files / "regex_groups.txt"
        test_file.write_text("user: alice\nuser: bob\nadmin: charlie")

        entries = [pf.Entry.from_path(test_file)]
        results = search_regex(entries, r"user: (\w+)")

        assert len(results) == 1
        _entry, matches = results[0]
        assert len(matches) == 2
        assert matches[0][1] == ("alice",)
        assert matches[1][1] == ("bob",)

    def test_search_regex_flags(self, sample_files: Path):
        test_file = sample_files / "regex_flags.txt"
        test_file.write_text("ERROR\nwarning\nInfo")

        entries = pf.find(sample_files).files().to_list()
        import re

        results = search_regex(entries, r"error", flags=re.IGNORECASE)

        assert len(results) == 1
        _entry, matches = results[0]
        assert len(matches) == 1


class TestChainIntegration:
    """Test search integration with FileChain."""

    def test_chain_matching_content(self, sample_files: Path):
        test_file = sample_files / "chain_search.txt"
        test_file.write_text("needle in haystack")

        chain = pf.find(sample_files).files().matching_content("needle")
        entries = chain.to_list()

        assert len(entries) == 1
        assert entries[0].name == "chain_search.txt"

    def test_chain_matching_regex(self, sample_files: Path):
        test_file = sample_files / "chain_regex.txt"
        test_file.write_text("error 404\nwarning 123")

        chain = pf.find(sample_files).files().matching_regex_in_content(r"error \d+")
        entries = chain.to_list()

        assert len(entries) == 1
        assert entries[0].name == "chain_regex.txt"

    def test_chain_containing_line(self, sample_files: Path):
        test_file = sample_files / "chain_line.txt"
        test_file.write_text("line one\nTARGET LINE\nline three")

        chain = pf.find(sample_files).files().containing_line("TARGET")
        entries = chain.to_list()

        assert len(entries) == 1

    def test_chain_containing_lines(self, sample_files: Path):
        test_file = sample_files / "chain_lines.txt"
        test_file.write_text("alpha\nbeta\ngamma")

        chain = pf.find(sample_files).files().containing_lines("alpha", "gamma")
        entries = chain.to_list()

        assert len(entries) == 1
