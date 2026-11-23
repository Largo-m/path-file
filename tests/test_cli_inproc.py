"""In-process CLI tests: exercises every command via path_file.cli.main(argv)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from path_file import __version__
from path_file.cli import main


def _tree(tmp_dir: Path) -> Path:
    (tmp_dir / "a.txt").write_text("hello")
    (tmp_dir / "b.txt").write_text("hello")
    (tmp_dir / "c.log").write_text("log data")
    (tmp_dir / "sub").mkdir()
    (tmp_dir / "sub" / "d.txt").write_text("deep")
    (tmp_dir / "empty.txt").write_text("")
    return tmp_dir


class TestGlobal:
    def test_version(self, capsys):
        with pytest.raises(SystemExit) as ei:
            main(["--version"])
        assert ei.value.code == 0
        out = capsys.readouterr().out
        assert __version__ in out

    def test_help_root(self):
        with pytest.raises(SystemExit) as ei:
            main(["--help"])
        assert ei.value.code == 0

    def test_help_subcommand(self):
        for cmd in ["find", "copy", "move", "delete", "sync", "rules"]:
            with pytest.raises(SystemExit) as ei:
                main([cmd, "--help"])
            assert ei.value.code == 0

    def test_no_command_prints_help(self, capsys):
        with pytest.raises(SystemExit) as ei:
            main([])
        assert ei.value.code == 2
        captured = capsys.readouterr()
        assert "usage" in (captured.out + captured.err).lower()

    def test_unknown_command(self):
        with pytest.raises(SystemExit):
            main(["nope"])


class TestFind:
    def test_find_basic(self, tmp_dir, capsys):
        _tree(tmp_dir)
        rc = main(["find", str(tmp_dir)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "a.txt" in out
        assert "d.txt" in out

    def test_find_json(self, tmp_dir, capsys):
        _tree(tmp_dir)
        rc = main(["find", str(tmp_dir), "--json", "--ext", "txt"])
        assert rc == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert any("a.txt" in item.get("path", "") for item in data)

    def test_find_filters(self, tmp_dir, capsys):
        _tree(tmp_dir)
        rc = main(["find", str(tmp_dir), "--ext", "log", "--name", "c"])
        assert rc == 0
        assert "c.log" in capsys.readouterr().out

    def test_find_pattern(self, tmp_dir, capsys):
        _tree(tmp_dir)
        rc = main(["find", str(tmp_dir), "--pattern", "*.txt"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "a.txt" in out
        assert "c.log" not in out

    def test_find_regex(self, tmp_dir, capsys):
        _tree(tmp_dir)
        rc = main(["find", str(tmp_dir), "--regex", r"a\.txt$"])
        assert rc == 0
        assert "a.txt" in capsys.readouterr().out

    def test_find_size(self, tmp_dir, capsys):
        (tmp_dir / "big.bin").write_bytes(b"x" * 2048)
        rc = main(["find", str(tmp_dir), "--larger", "1kb"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "big.bin" in out
        assert "a.txt" not in out

    def test_find_quiet_and_verbose(self, tmp_dir, capsys):
        _tree(tmp_dir)
        assert main(["find", str(tmp_dir), "-q"]) == 0
        assert main(["find", str(tmp_dir), "-v"]) == 0

    def test_find_no_recursive(self, tmp_dir, capsys):
        _tree(tmp_dir)
        rc = main(["find", str(tmp_dir), "--no-recursive"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "d.txt" not in out

    def test_find_empty_dir(self, tmp_dir, capsys):
        rc = main(["find", str(tmp_dir)])
        assert rc == 4


class TestReport:
    def test_report_basic(self, tmp_dir, capsys):
        _tree(tmp_dir)
        rc = main(["report", str(tmp_dir)])
        assert rc == 0
        assert (
            "PATH" in capsys.readouterr().out.upper() or "FILES" in capsys.readouterr().out.upper()
        )

    def test_report_by_ext(self, tmp_dir, capsys):
        _tree(tmp_dir)
        assert main(["report", str(tmp_dir), "--by-ext"]) == 0
        assert ".txt" in capsys.readouterr().out

    def test_report_by_size(self, tmp_dir, capsys):
        _tree(tmp_dir)
        assert main(["report", str(tmp_dir), "--by-size"]) == 0

    def test_report_extremes(self, tmp_dir, capsys):
        _tree(tmp_dir)
        assert main(["report", str(tmp_dir), "--extremes"]) == 0
        out = capsys.readouterr().out
        assert "Largest" in out or "SMALL" in out.upper() or "Files" in out

    def test_report_json(self, tmp_dir, capsys):
        _tree(tmp_dir)
        assert main(["report", str(tmp_dir), "--json"]) == 0
        data = json.loads(capsys.readouterr().out)
        assert "chain_size" in data


class TestCopyMove:
    def test_copy_dry_run(self, tmp_dir, capsys):
        _tree(tmp_dir)
        dest = tmp_dir / "backup"
        rc = main(["copy", str(tmp_dir / "a.txt"), str(dest), "-n"])
        assert rc == 0
        assert not dest.exists()

    def test_copy_real(self, tmp_dir):
        _tree(tmp_dir)
        dest = tmp_dir / "backup"
        rc = main(["copy", str(tmp_dir / "a.txt"), str(dest)])
        assert rc == 0
        assert (dest / "a.txt").read_text() == "hello"

    def test_copy_ext_filter(self, tmp_dir):
        _tree(tmp_dir)
        dest = tmp_dir / "backup"
        rc = main(["copy", str(tmp_dir), str(dest), "--ext", "txt"])
        assert rc == 0
        assert (dest / "a.txt").exists()
        assert not (dest / "c.log").exists()

    def test_copy_json(self, tmp_dir, capsys):
        _tree(tmp_dir)
        dest = tmp_dir / "backup"
        assert main(["copy", str(tmp_dir / "a.txt"), str(dest), "--json"]) == 0
        assert "COPY_TO" in capsys.readouterr().out

    def test_copy_overwrite(self, tmp_dir):
        _tree(tmp_dir)
        dest = tmp_dir / "backup"
        (dest).mkdir()
        (dest / "a.txt").write_text("old")
        rc = main(["copy", str(tmp_dir / "a.txt"), str(dest), "--overwrite"])
        assert rc == 0
        assert (dest / "a.txt").read_text() == "hello"

    def test_copy_parallel(self, tmp_dir):
        _tree(tmp_dir)
        dest = tmp_dir / "backup"
        rc = main(["copy", str(tmp_dir), str(dest), "--ext", "txt", "-p", "2"])
        assert rc == 0
        assert (dest / "a.txt").exists()
        assert (dest / "d.txt").exists()

    def test_move(self, tmp_dir):
        _tree(tmp_dir)
        dest = tmp_dir / "moved"
        rc = main(["move", str(tmp_dir / "c.log"), str(dest)])
        assert rc == 0
        assert (dest / "c.log").exists()
        assert not (tmp_dir / "c.log").exists()

    def test_move_dry_run(self, tmp_dir):
        _tree(tmp_dir)
        dest = tmp_dir / "moved"
        rc = main(["move", str(tmp_dir / "c.log"), str(dest), "-n"])
        assert rc == 0
        assert not dest.exists()
        assert (tmp_dir / "c.log").exists()

    def test_move_json(self, tmp_dir, capsys):
        _tree(tmp_dir)
        dest = tmp_dir / "moved"
        assert main(["move", str(tmp_dir / "c.log"), str(dest), "--json"]) == 0
        assert "MOVE_TO" in capsys.readouterr().out


class TestDelete:
    def test_delete_dry_run(self, tmp_dir):
        _tree(tmp_dir)
        rc = main(["delete", str(tmp_dir / "c.log"), "-n"])
        assert rc == 0
        assert (tmp_dir / "c.log").exists()

    def test_delete_requires_confirm(self, tmp_dir, capsys):
        _tree(tmp_dir)
        rc = main(["delete", str(tmp_dir / "c.log")])
        assert rc != 0
        assert (tmp_dir / "c.log").exists()

    def test_delete_confirm(self, tmp_dir):
        _tree(tmp_dir)
        rc = main(["delete", str(tmp_dir / "c.log"), "--confirm"])
        assert rc == 0
        assert not (tmp_dir / "c.log").exists()

    def test_delete_filters(self, tmp_dir):
        _tree(tmp_dir)
        (tmp_dir / "old.tmp").write_bytes(b"x" * 512)
        rc = main(["delete", str(tmp_dir), "--ext", "tmp", "--confirm"])
        assert rc == 0
        assert not (tmp_dir / "old.tmp").exists()

    def test_delete_pattern(self, tmp_dir):
        _tree(tmp_dir)
        rc = main(["delete", str(tmp_dir), "--pattern", "*.log", "--confirm"])
        assert rc == 0
        assert not (tmp_dir / "c.log").exists()

    def test_delete_older_than(self, tmp_dir):
        _tree(tmp_dir)
        import os
        import time

        old = tmp_dir / "ancient.log"
        old.write_text("old")
        past = time.time() - 10 * 86400
        os.utime(old, (past, past))
        rc = main(["delete", str(tmp_dir), "--ext", "log", "--older", "5d", "--confirm"])
        assert rc == 0
        assert not old.exists()

    def test_delete_trash_flag(self, tmp_dir):
        _tree(tmp_dir)
        rc = main(["delete", str(tmp_dir / "c.log"), "--trash", "--confirm"])
        assert rc in (0, 1)


class TestHashDuplicates:
    def test_hash(self, tmp_dir, capsys):
        _tree(tmp_dir)
        assert main(["hash", str(tmp_dir / "a.txt")]) == 0
        out = capsys.readouterr().out
        assert len(out.split()[0]) == 64  # sha256 hex length

    def test_hash_algorithm(self, tmp_dir, capsys):
        _tree(tmp_dir)
        assert main(["hash", str(tmp_dir / "a.txt"), "-a", "md5"]) == 0
        assert len(capsys.readouterr().out.split()[0]) == 32

    def test_hash_json(self, tmp_dir, capsys):
        _tree(tmp_dir)
        assert main(["hash", str(tmp_dir), "--json"]) == 0
        data = json.loads(capsys.readouterr().out)
        assert len(data) >= 5

    def test_duplicates_by_content(self, tmp_dir, capsys):
        _tree(tmp_dir)
        assert main(["duplicates", str(tmp_dir)]) == 0
        out = capsys.readouterr().out
        assert "a.txt" in out and "b.txt" in out

    def test_duplicates_by_name(self, tmp_dir, capsys):
        _tree(tmp_dir)
        (tmp_dir / "sub").mkdir(exist_ok=True)
        (tmp_dir / "sub" / "a.txt").write_text("deep")
        assert main(["duplicates", str(tmp_dir), "--by-name"]) == 0

    def test_duplicates_none(self, tmp_dir, capsys):
        (tmp_dir / "u1.txt").write_text("one")
        (tmp_dir / "u2.txt").write_text("two")
        rc = main(["duplicates", str(tmp_dir), "--json"])
        assert rc == 0


class TestArchiveExtract:
    def test_archive_and_extract(self, tmp_dir, capsys):
        _tree(tmp_dir)
        out = tmp_dir / "out.zip"
        rc = main(["archive", str(tmp_dir / "a.txt"), "-o", str(out), "-f", "zip"])
        assert rc == 0
        assert out.exists()

        dest = tmp_dir / "unzipped"
        rc = main(["extract", str(out), "-o", str(dest)])
        assert rc == 0
        assert (dest / "a.txt").read_text() == "hello"

    def test_archive_formats(self, tmp_dir):
        _tree(tmp_dir)
        for i, fmt in enumerate(["zip", "tar", "tar.gz", "tar.bz2", "tar.xz"]):
            out = tmp_dir / f"arc{i}.{fmt.replace('.', '_')}"
            rc = main(["archive", str(tmp_dir / "a.txt"), "-o", str(out), "-f", fmt])
            assert rc == 0, fmt
            assert out.exists()

    def test_archive_dry_run(self, tmp_dir):
        _tree(tmp_dir)
        out = tmp_dir / "none.zip"
        rc = main(["archive", str(tmp_dir / "a.txt"), "-o", str(out), "-n"])
        assert rc == 0
        assert not out.exists()

    def test_extract_missing(self, tmp_dir, capsys):
        rc = main(["extract", str(tmp_dir / "nope.zip"), "-o", str(tmp_dir / "x")])
        assert rc != 0


class TestSync:
    def test_sync_dry_run(self, tmp_dir):
        src = tmp_dir / "src"
        dest = tmp_dir / "dest"
        src.mkdir()
        dest.mkdir()
        (src / "f.txt").write_text("data")
        rc = main(["sync", str(src), str(dest), "-n"])
        assert rc == 0
        assert not (dest / "f.txt").exists()

    def test_sync_real(self, tmp_dir):
        src = tmp_dir / "src"
        dest = tmp_dir / "dest"
        src.mkdir()
        dest.mkdir()
        (src / "f.txt").write_text("data")
        rc = main(["sync", str(src), str(dest)])
        assert rc == 0
        assert (dest / "f.txt").read_text() == "data"

    def test_sync_delete_extras(self, tmp_dir):
        src = tmp_dir / "src"
        dest = tmp_dir / "dest"
        src.mkdir()
        dest.mkdir()
        (dest / "extra.txt").write_text("junk")
        rc = main(["sync", str(src), str(dest), "--delete-extras"])
        assert rc == 0
        assert not (dest / "extra.txt").exists()

    def test_sync_json(self, tmp_dir, capsys):
        src = tmp_dir / "src"
        dest = tmp_dir / "dest"
        src.mkdir()
        dest.mkdir()
        (src / "f.txt").write_text("data")
        assert main(["sync", str(src), str(dest), "--json"]) == 0
        assert json.loads(capsys.readouterr().out)["action"] == "sync"

    def test_sync_in_sync(self, tmp_dir):
        src = tmp_dir / "src"
        dest = tmp_dir / "dest"
        src.mkdir()
        dest.mkdir()
        (src / "f.txt").write_text("data")
        (dest / "f.txt").write_text("data")
        rc = main(["sync", str(src), str(dest)])
        assert rc == 0  # nothing to do; execute path still succeeds


class TestWatch:
    def test_watch_duration(self, tmp_dir, capsys):
        watched = tmp_dir / "w"
        watched.mkdir()
        rc = main(["watch", str(watched), "--duration", "0.2", "-i", "0.05"])
        assert rc == 0

    def test_watch_on_new_command(self, tmp_dir):
        watched = tmp_dir / "w"
        watched.mkdir()
        rc = main(
            [
                "watch",
                str(watched),
                "--duration",
                "0.2",
                "--on-new",
                "echo new: {}",
            ]
        )
        assert rc == 0


class TestRules:
    def test_rules_dry_run(self, tmp_dir, capsys):
        _tree(tmp_dir)
        rules = tmp_dir / "rules.toml"
        rules.write_text(
            '[[rule]]\nmatch = "*.log"\naction = "delete"\n\n'
            '[[rule]]\nmatch = "*.txt"\naction = "move"\ndest = "' + str(tmp_dir / "txtout") + '"\n'
        )
        rc = main(["rules", str(tmp_dir), "-f", str(rules)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "DRY" in out.upper() or "rule" in out.lower()

    def test_rules_apply(self, tmp_dir):
        _tree(tmp_dir)
        rules = tmp_dir / "rules.toml"
        rules.write_text('[[rule]]\nmatch = "*.log"\naction = "delete"\nconfirm = true\n')
        rc = main(["rules", str(tmp_dir), "-f", str(rules), "--apply"])
        assert rc == 0
        assert not (tmp_dir / "c.log").exists()

    def test_rules_apply_needs_confirm(self, tmp_dir, capsys):
        _tree(tmp_dir)
        rules = tmp_dir / "rules.toml"
        rules.write_text('[[rule]]\nmatch = "*.log"\naction = "delete"\n')
        rc = main(["rules", str(tmp_dir), "-f", str(rules), "--apply"])
        assert rc == 1  # delete rule without confirm=true is refused
        assert (tmp_dir / "c.log").exists()

    def test_rules_invalid_file(self, tmp_dir, capsys):
        rules = tmp_dir / "bad.toml"
        rules.write_text("this is not toml at all [[[\n")
        rc = main(["rules", str(tmp_dir), "-f", str(rules)])
        assert rc != 0

    def test_rules_json(self, tmp_dir, capsys):
        _tree(tmp_dir)
        rules = tmp_dir / "rules.toml"
        rules.write_text('[[rule]]\nmatch = "*.log"\naction = "delete"\n')
        assert main(["rules", str(tmp_dir), "-f", str(rules), "--json"]) == 0
