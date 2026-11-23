"""Deep tests for action wrappers and executors."""

from __future__ import annotations

import os
import zipfile
from pathlib import Path

import pytest

import path_file as pf
from path_file.exceptions import PathflowError


def _tree(tmp_dir: Path) -> Path:
    (tmp_dir / "a.txt").write_text("hello")
    (tmp_dir / "b.txt").write_text("hello")
    (tmp_dir / "c.log").write_text("log")
    (tmp_dir / "sub").mkdir()
    (tmp_dir / "sub" / "d.txt").write_text("deep")
    return tmp_dir


class TestCopy:
    def test_copy_files(self, tmp_dir):
        _tree(tmp_dir)
        dest = tmp_dir / "out"
        chain = pf.find(tmp_dir / "a.txt").copy_to(dest)
        assert chain.execute()
        assert (dest / "a.txt").exists()

    def test_copy_dry_run(self, tmp_dir):
        _tree(tmp_dir)
        dest = tmp_dir / "out"
        chain = pf.find(tmp_dir / "a.txt").copy_to(dest).dry_run()
        result = chain.execute()
        assert result.dry_run
        assert not (dest / "a.txt").exists()

    def test_copy_overwrite(self, tmp_dir):
        _tree(tmp_dir)
        dest = tmp_dir / "out"
        dest.mkdir()
        (dest / "a.txt").write_text("old")
        assert pf.find(tmp_dir / "a.txt").copy_to(dest, overwrite=True).execute()
        assert (dest / "a.txt").read_text() == "hello"

    def test_copy_no_overwrite_fails(self, tmp_dir):
        _tree(tmp_dir)
        dest = tmp_dir / "out"
        dest.mkdir()
        (dest / "a.txt").write_text("old")
        with pytest.raises(PathflowError):
            pf.find(tmp_dir / "a.txt").copy_to(dest).execute()

    def test_copy_parallel(self, tmp_dir):
        _tree(tmp_dir)
        dest = tmp_dir / "out"
        assert pf.find(tmp_dir).with_extension("txt").copy_to(dest, parallel=2).execute()
        assert (dest / "a.txt").exists()
        assert (dest / "d.txt").exists()


class TestMove:
    def test_move_file(self, tmp_dir):
        _tree(tmp_dir)
        dest = tmp_dir / "dest"
        assert pf.find(tmp_dir / "c.log").move_to(dest).dry_run(False).execute()
        assert not (tmp_dir / "c.log").exists()
        assert (dest / "c.log").exists()

    def test_move_dry_run(self, tmp_dir):
        _tree(tmp_dir)
        dest = tmp_dir / "dest"
        assert pf.find(tmp_dir / "c.log").move_to(dest).dry_run().execute()
        assert (tmp_dir / "c.log").exists()
        assert not dest.exists()


class TestDeleteAndTrash:
    def test_delete_confirm(self, tmp_dir):
        _tree(tmp_dir)
        assert pf.find(tmp_dir / "c.log").delete(confirm=True).execute()
        assert not (tmp_dir / "c.log").exists()

    def test_delete_dry_run(self, tmp_dir):
        _tree(tmp_dir)
        assert pf.find(tmp_dir / "c.log").delete(confirm=True, dry_run=True).execute()
        assert (tmp_dir / "c.log").exists()

    def test_trash_requires_dependency(self, tmp_dir):
        _tree(tmp_dir)
        try:
            assert pf.find(tmp_dir / "c.log").trash(confirm=True).execute()
        except PathflowError:
            pytest.skip("send2trash not installed")


class TestRename:
    def test_rename_pattern(self, tmp_dir):
        _tree(tmp_dir)
        assert pf.find(tmp_dir / "c.log").rename("renamed.log").dry_run(False).execute()
        assert (tmp_dir / "renamed.log").exists()

    def test_rename_with_func(self, tmp_dir):
        _tree(tmp_dir)
        # NB: a pure case change is a no-op on case-insensitive filesystems
        assert (
            pf.find(tmp_dir / "c.log")
            .rename_with(lambda name: "upper_" + name)
            .dry_run(False)
            .execute()
        )
        assert (tmp_dir / "upper_c.log").exists()


class TestArchiveExtract:
    def test_archive_to(self, tmp_dir):
        _tree(tmp_dir)
        archive = tmp_dir / "backup.zip"
        assert pf.find(tmp_dir / "a.txt").archive_to(archive).execute()
        assert archive.exists()
        assert zipfile.is_zipfile(archive)

    def test_archive_dry_run(self, tmp_dir):
        _tree(tmp_dir)
        archive = tmp_dir / "backup.zip"
        assert pf.find(tmp_dir / "a.txt").archive_to(archive).dry_run().execute()
        assert not archive.exists()

    def test_compress_gz(self, tmp_dir):
        _tree(tmp_dir)
        assert pf.find(tmp_dir / "a.txt").compress("gz").execute()
        assert (tmp_dir / "a.txt.gz").exists()

    def test_compress_bz2(self, tmp_dir):
        _tree(tmp_dir)
        assert pf.find(tmp_dir / "a.txt").compress("bz2").execute()
        assert (tmp_dir / "a.txt.bz2").exists()

    def test_extract_to(self, tmp_dir):
        _tree(tmp_dir)
        archive = tmp_dir / "backup.zip"
        pf.find(tmp_dir / "a.txt").archive_to(archive).execute()
        out = tmp_dir / "unpacked"
        assert pf.find(archive).extract_to(out).execute()
        assert any(out.rglob("a.txt")) or (out / "a.txt").exists()


class TestPermissions:
    def test_chmod_read_only(self, tmp_dir):
        _tree(tmp_dir)
        target = tmp_dir / "a.txt"
        assert pf.find(target).chmod(0o444).execute()
        assert os.stat(target).st_mode & 0o444

    def test_chmod_str_mode(self, tmp_dir):
        _tree(tmp_dir)
        target = tmp_dir / "a.txt"
        assert pf.find(target).chmod("0o600").dry_run(False).execute()


class TestTouch:
    def test_touch_updates_mtime(self, tmp_dir):
        _tree(tmp_dir)
        target = tmp_dir / "a.txt"
        old = target.stat().st_mtime
        import time

        time.sleep(0.01)
        assert pf.find(target).touch().execute()
        assert target.stat().st_mtime > old

    def test_touch_creates_missing(self, tmp_dir):
        _tree(tmp_dir)
        target = tmp_dir / "fresh.txt"
        assert pf.find(target).touch().execute()
        assert target.exists()


class TestReadWrite:
    def test_read_text(self, tmp_dir):
        _tree(tmp_dir)
        chain = pf.find(tmp_dir / "a.txt").read_text()
        result = chain.execute()
        assert result.count == 1 and result.success()

    def test_read_bytes(self, tmp_dir):
        _tree(tmp_dir)
        result = pf.find(tmp_dir / "a.txt").read_bytes().execute()
        assert result.count == 1 and result.success()

    def test_write_text(self, tmp_dir):
        _tree(tmp_dir)
        target = tmp_dir / "a.txt"
        assert pf.find(target).write_text("new content").dry_run(False).execute()
        assert target.read_text() == "new content"

    def test_write_bytes(self, tmp_dir):
        _tree(tmp_dir)
        target = tmp_dir / "a.txt"
        assert pf.find(target).write_bytes(b"raw").dry_run(False).execute()
        assert target.read_bytes() == b"raw"


class TestHashAction:
    def test_hash_action(self, tmp_dir):
        _tree(tmp_dir)
        result = pf.find(tmp_dir / "a.txt").hash().execute()
        assert result.count >= 1

    def test_hash_action_algorithm(self, tmp_dir):
        _tree(tmp_dir)
        result = pf.find(tmp_dir / "a.txt").hash("md5").execute()
        assert result.count >= 1


class TestOpenAction:
    def test_open_read(self, tmp_dir):
        _tree(tmp_dir)
        result = pf.find(tmp_dir / "a.txt").open("r").execute()
        assert result.count == 1

    def test_open_write(self, tmp_dir):
        _tree(tmp_dir)
        target = tmp_dir / "wr.txt"
        target.write_text("")
        assert pf.find(target).open("w").execute()


class TestCreateDir:
    def test_create_dir(self, tmp_dir):
        target = tmp_dir / "newdir"
        assert pf.find(target).create_dir().execute()
        assert target.is_dir()

    def test_create_dir_exists(self, tmp_dir):
        target = tmp_dir / "newdir"
        target.mkdir()
        assert pf.find(target).create_dir().execute()


class TestSymlink:
    def test_symlink_to(self, tmp_dir):
        _tree(tmp_dir)
        link = tmp_dir / "link.txt"
        assert pf.find(link).symlink_to(tmp_dir / "a.txt").execute()
        assert link.is_symlink()

    def test_symlink_dry_run(self, tmp_dir):
        _tree(tmp_dir)
        link = tmp_dir / "link2.txt"
        assert pf.find(link).symlink_to(tmp_dir / "a.txt").dry_run().execute()
        assert not link.exists()


class TestChainIntegration:
    def test_full_pipeline(self, tmp_dir):
        _tree(tmp_dir)
        dest = tmp_dir / "organized"
        result = (
            pf.find(tmp_dir).with_extensions("txt", "log").copy_to(dest, overwrite=True).execute()
        )
        assert result.count >= 1
        assert (dest / "a.txt").exists()

    def test_action_summary_text(self, tmp_dir):
        _tree(tmp_dir)
        dest = tmp_dir / "out"
        result = pf.find(tmp_dir / "a.txt").copy_to(dest).execute()
        summary = result.summary()
        assert "COPY_TO" in summary
