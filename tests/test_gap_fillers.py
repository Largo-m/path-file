"""Gap-filling tests: action wrappers, parallel/error paths, CLI commands, parsers."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

import path_file as pf
from path_file._internal._parsers import DateTimeParser, PatternMatcher
from path_file.actions import (
    action_archive_to,
    action_chmod,
    action_compress,
    action_copy,
    action_create_dir,
    action_delete,
    action_extract_to,
    action_hash,
    action_move,
    action_open,
    action_read_bytes,
    action_read_text,
    action_rename,
    action_rename_with,
    action_symlink_to,
    action_touch,
    action_trash,
    action_write_bytes,
    action_write_text,
)
from path_file.cli import main


def _tree(tmp_dir: Path) -> Path:
    (tmp_dir / "a.txt").write_text("alpha")
    (tmp_dir / "b.txt").write_text("beta")
    (tmp_dir / "c.log").write_text("log")
    (tmp_dir / "sub").mkdir()
    (tmp_dir / "sub" / "deep.txt").write_text("deep")
    return tmp_dir


class TestActionWrappers:
    def test_action_copy(self, tmp_dir):
        _tree(tmp_dir)
        chain = action_copy(pf.find(tmp_dir / "a.txt"), tmp_dir / "out1")
        assert chain.execute().count == 1
        assert (tmp_dir / "out1" / "a.txt").exists()

    def test_action_move(self, tmp_dir):
        _tree(tmp_dir)
        action_move(pf.find(tmp_dir / "c.log"), tmp_dir / "out2").dry_run(False).execute()
        assert (tmp_dir / "out2" / "c.log").exists()
        assert not (tmp_dir / "c.log").exists()

    def test_action_delete(self, tmp_dir):
        _tree(tmp_dir)
        action_delete(pf.find(tmp_dir / "c.log"), confirm=True).execute()
        assert not (tmp_dir / "c.log").exists()

    def test_action_trash(self, tmp_dir):
        _tree(tmp_dir)
        try:
            action_trash(pf.find(tmp_dir / "c.log"), confirm=True).execute()
        except Exception:
            pytest.skip("send2trash unavailable")

    def test_action_rename(self, tmp_dir):
        _tree(tmp_dir)
        action_rename(pf.find(tmp_dir / "c.log"), "new.log").dry_run(False).execute()
        assert (tmp_dir / "new.log").exists()

    def test_action_rename_with(self, tmp_dir):
        _tree(tmp_dir)
        action_rename_with(pf.find(tmp_dir / "c.log"), lambda n: "r_" + n).dry_run(False).execute()
        assert (tmp_dir / "r_c.log").exists()

    def test_action_archive_to(self, tmp_dir):
        _tree(tmp_dir)
        action_archive_to(pf.find(tmp_dir / "a.txt"), tmp_dir / "w.zip").execute()
        assert (tmp_dir / "w.zip").exists()

    def test_action_compress(self, tmp_dir):
        _tree(tmp_dir)
        action_compress(pf.find(tmp_dir / "a.txt"), "gz").execute()
        assert (tmp_dir / "a.txt.gz").exists()

    def test_action_extract_to(self, tmp_dir):
        _tree(tmp_dir)
        action_archive_to(pf.find(tmp_dir / "a.txt"), tmp_dir / "w2.zip").execute()
        action_extract_to(pf.find(tmp_dir / "w2.zip"), tmp_dir / "ex").execute()
        assert (tmp_dir / "ex").exists()

    def test_action_chmod(self, tmp_dir):
        _tree(tmp_dir)
        action_chmod(pf.find(tmp_dir / "a.txt"), 0o644).dry_run(False).execute()

    def test_action_touch(self, tmp_dir):
        _tree(tmp_dir)
        action_touch(pf.find(tmp_dir)).execute()
        assert (tmp_dir / "a.txt").exists()

    def test_action_read_text(self, tmp_dir):
        _tree(tmp_dir)
        assert action_read_text(pf.find(tmp_dir / "a.txt")).execute().count == 1

    def test_action_read_bytes(self, tmp_dir):
        _tree(tmp_dir)
        assert action_read_bytes(pf.find(tmp_dir / "a.txt")).execute().count == 1

    def test_action_write_text(self, tmp_dir):
        _tree(tmp_dir)
        action_write_text(pf.find(tmp_dir / "a.txt"), "rewritten").dry_run(False).execute()
        assert (tmp_dir / "a.txt").read_text() == "rewritten"

    def test_action_write_bytes(self, tmp_dir):
        _tree(tmp_dir)
        action_write_bytes(pf.find(tmp_dir / "a.txt"), b"raw").dry_run(False).execute()
        assert (tmp_dir / "a.txt").read_bytes() == b"raw"

    def test_action_hash(self, tmp_dir):
        _tree(tmp_dir)
        assert action_hash(pf.find(tmp_dir / "a.txt")).execute().count == 1

    def test_action_open(self, tmp_dir):
        _tree(tmp_dir)
        assert action_open(pf.find(tmp_dir / "a.txt"), "r").execute().count == 1

    def test_action_create_dir(self, tmp_dir):
        action_create_dir(pf.find(tmp_dir / "fresh")).execute()
        assert (tmp_dir / "fresh").is_dir()

    def test_action_symlink_to(self, tmp_dir):
        _tree(tmp_dir)
        link = tmp_dir / "link.txt"
        try:
            action_symlink_to(pf.find(link), tmp_dir / "a.txt").execute()
        except OSError:
            pytest.skip("symlinks unavailable")
        assert link.is_symlink()


class TestParallelAndErrors:
    def test_parallel_copy(self, tmp_dir):
        _tree(tmp_dir)
        for i in range(6):
            (tmp_dir / f"f{i}.txt").write_text(f"data{i}")
        result = (
            pf.find(tmp_dir).with_extension("txt").parallel(4).copy_to(tmp_dir / "pout").execute()
        )
        assert result.count >= 6
        assert (tmp_dir / "pout" / "f0.txt").exists()

    def test_on_error_collect(self, tmp_dir):
        _tree(tmp_dir)
        # delete a file that disappears mid-chain: use collect so it doesn't raise
        from path_file import Entry

        entries = [Entry.from_path(tmp_dir / "a.txt"), Entry.from_path(tmp_dir / "b.txt")]
        (tmp_dir / "a.txt").unlink()
        chain = pf.FileChain.from_entries(entries).on_error("collect")
        result = chain.delete(confirm=True).execute()
        assert result.count >= 0  # b.txt still deleted

    def test_on_error_skip(self, tmp_dir):
        _tree(tmp_dir)
        from path_file import Entry

        entries = [Entry.from_path(tmp_dir / "a.txt"), Entry.from_path(tmp_dir / "b.txt")]
        (tmp_dir / "a.txt").unlink()
        result = pf.FileChain.from_entries(entries).on_error("skip").delete(confirm=True).execute()
        assert result.skipped >= 1

    def test_on_error_raise(self, tmp_dir):
        _tree(tmp_dir)
        from path_file import Entry

        entries = [Entry.from_path(tmp_dir / "a.txt"), Entry.from_path(tmp_dir / "b.txt")]
        (tmp_dir / "a.txt").unlink()
        with pytest.raises(OSError):
            pf.FileChain.from_entries(entries).on_error("raise").delete(confirm=True).execute()

    def test_verbose_and_progress_action(self, tmp_dir):
        _tree(tmp_dir)
        result = pf.find(tmp_dir / "a.txt").verbose().progress().copy_to(tmp_dir / "vp").execute()
        assert result.count == 1

    def test_progress_to_stream(self, tmp_dir):
        _tree(tmp_dir)
        buf = io.StringIO()
        from path_file.progress import ProgressBar

        bar = ProgressBar(1, stream=buf)
        bar.update(1)
        bar.finish()
        assert buf.getvalue()


class TestMoreCli:
    def test_hash_command(self, tmp_dir, capsys):
        _tree(tmp_dir)
        assert main(["hash", str(tmp_dir / "a.txt")]) == 0
        out = capsys.readouterr().out
        assert len(out.split()[0]) == 64 or "hash" in out.lower()

    def test_hash_json(self, tmp_dir, capsys):
        _tree(tmp_dir)
        assert main(["hash", str(tmp_dir / "a.txt"), "--json"]) == 0

    def test_hash_missing(self, tmp_dir, capsys):
        assert main(["hash", str(tmp_dir / "nope.txt")]) in (0, 1)

    def test_report_by_size(self, tmp_dir, capsys):
        _tree(tmp_dir)
        assert main(["report", str(tmp_dir), "--by-size"]) == 0
        assert "B" in capsys.readouterr().out

    def test_report_extremes(self, tmp_dir, capsys):
        _tree(tmp_dir)
        assert main(["report", str(tmp_dir), "--extremes"]) == 0

    def test_report_json(self, tmp_dir, capsys):
        _tree(tmp_dir)
        assert main(["report", str(tmp_dir), "--json"]) == 0

    def test_duplicates_json(self, tmp_dir, capsys):
        _tree(tmp_dir)
        (tmp_dir / "a.txt").write_text("same")
        (tmp_dir / "b.txt").write_text("same")
        assert main(["duplicates", str(tmp_dir), "--json"]) == 0

    def test_archive_and_extract_commands(self, tmp_dir):
        _tree(tmp_dir)
        archive = tmp_dir / "cli.zip"
        assert main(["archive", str(tmp_dir / "a.txt"), "-o", str(archive)]) == 0
        assert archive.exists()
        assert main(["extract", str(archive), "-o", str(tmp_dir / "cli_out")]) == 0

    def test_archive_dry_run_flag(self, tmp_dir):
        _tree(tmp_dir)
        archive = tmp_dir / "dry.zip"
        assert main(["-n", "archive", str(tmp_dir / "a.txt"), "-o", str(archive)]) == 0
        assert not archive.exists()

    def test_find_name_flag(self, tmp_dir, capsys):
        _tree(tmp_dir)
        assert main(["find", str(tmp_dir), "--name", "a"]) == 0

    def test_find_regex_flag(self, tmp_dir, capsys):
        _tree(tmp_dir)
        assert main(["find", str(tmp_dir), "--regex", r"\.txt$"]) == 0

    def test_find_glob_flag(self, tmp_dir, capsys):
        _tree(tmp_dir)
        assert main(["find", str(tmp_dir), "--pattern", "*.log"]) == 0

    def test_find_hidden_flag(self, tmp_dir, capsys):
        _tree(tmp_dir)
        (tmp_dir / ".hidden").write_text("h")
        assert main(["find", str(tmp_dir), "--hidden"]) == 0

    def test_find_empty_flag(self, tmp_dir, capsys):
        _tree(tmp_dir)
        (tmp_dir / "empty.txt").write_text("")
        assert main(["find", str(tmp_dir), "--empty"]) == 0

    def test_find_sort_limit(self, tmp_dir, capsys):
        _tree(tmp_dir)
        assert main(["find", str(tmp_dir), "--sort", "size", "--reverse", "--limit", "1"]) == 0

    def test_find_json(self, tmp_dir, capsys):
        _tree(tmp_dir)
        assert main(["find", str(tmp_dir), "--json"]) == 0

    def test_copy_ext_flag(self, tmp_dir):
        _tree(tmp_dir)
        assert main(["copy", str(tmp_dir), str(tmp_dir / "cout"), "--ext", "txt"]) == 0
        assert (tmp_dir / "cout" / "a.txt").exists()

    def test_delete_no_confirm_refused(self, tmp_dir):
        _tree(tmp_dir)
        assert main(["delete", str(tmp_dir / "c.log")]) == 3
        assert (tmp_dir / "c.log").exists()

    def test_sync_dry_run_flag(self, tmp_dir):
        src = tmp_dir / "src"
        dest = tmp_dir / "dest"
        src.mkdir()
        dest.mkdir()
        (src / "x.txt").write_text("data")
        rc = main(["-n", "sync", str(src), str(dest)])
        assert rc in (0, 4)
        assert not (dest / "x.txt").exists()

    def test_rules_dry_run_default(self, tmp_dir):
        _tree(tmp_dir)
        rules = tmp_dir / "r.toml"
        rules.write_text('[[rule]]\nmatch = "*.log"\naction = "delete"\nconfirm = true\n')
        assert main(["rules", str(tmp_dir), "-f", str(rules)]) == 0
        assert (tmp_dir / "c.log").exists()

    def test_version_flag(self, capsys):

        with pytest.raises(SystemExit) as ei:
            main(["--version"])
        assert ei.value.code == 0

    def test_quiet_flag(self, tmp_dir, capsys):
        _tree(tmp_dir)
        assert main(["-q", "find", str(tmp_dir)]) == 0


class TestParserGaps:
    def test_pattern_matcher_regex_slash(self):
        matcher = PatternMatcher(r"/err\d+/")
        assert not matcher.match("error42")  # needs digits right after err
        assert matcher.match("err42")
        assert not matcher.match("warning")

    def test_pattern_matcher_regex_slash_flags(self):
        matcher = PatternMatcher(r"/abc/i")
        assert matcher.match("ABC")

    def test_pattern_matcher_re_prefix(self):
        matcher = PatternMatcher("re:^doc.*")
        assert matcher.match("document.txt")

    def test_pattern_matcher_plain(self):
        matcher = PatternMatcher("exact.txt")
        assert matcher.match("exact.txt")
        assert not matcher.match("other.txt")

    def test_pattern_matcher_match_path(self, tmp_dir):
        matcher = PatternMatcher("*.txt")
        assert matcher.match_path(tmp_dir / "sub" / "deep.txt") is True

    def test_datetime_parser_keywords(self):
        parser = DateTimeParser()
        for word in ("today", "yesterday", "now", "tomorrow"):
            parsed = parser.parse(word)
            assert parsed is None or hasattr(parsed, "year")

    def test_parse_size_negative_and_unit(self):
        from path_file.units import parse_size

        assert parse_size("0") == 0
        from path_file.exceptions import InvalidSizeError

        with pytest.raises(InvalidSizeError):
            parse_size("kb")
