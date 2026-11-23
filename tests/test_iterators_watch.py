"""Tests for _internal/_iterators.py walking and watch.py watcher."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from path_file._internal._iterators import (
    SymlinkTracker,
    WalkConfig,
    scan_dir,
    walk,
    walk_bfs,
    walk_iterative,
    walk_recursive,
)
from path_file.watch import Watcher, WatchEvent, watch


def _tree(tmp_dir: Path) -> Path:
    (tmp_dir / "a.txt").write_text("a")
    (tmp_dir / "b.log").write_text("b")
    sub = tmp_dir / "sub"
    sub.mkdir()
    (sub / "deep.txt").write_text("deep")
    (sub / "deeper").mkdir()
    (sub / "deeper" / "deepest.txt").write_text("deepest")
    return tmp_dir


class TestWalkModes:
    def test_recursive_default(self, tmp_dir):
        _tree(tmp_dir)
        names = {e.name for e in walk(tmp_dir)}
        assert {"a.txt", "b.log", "sub", "deep.txt", "deepest.txt"} <= names

    def test_max_depth(self, tmp_dir):
        _tree(tmp_dir)
        names = {e.name for e in walk(tmp_dir, max_depth=1)}
        assert "deep.txt" in names
        assert "deepest.txt" not in names

    def test_min_depth(self, tmp_dir):
        _tree(tmp_dir)
        names = {e.name for e in walk(tmp_dir, min_depth=2)}
        assert "a.txt" not in names
        assert "deep.txt" not in names  # depth 1
        assert "deepest.txt" in names  # depth 2

    def test_walk_recursive_direct(self, tmp_dir):
        _tree(tmp_dir)
        entries = list(walk_recursive(Path(tmp_dir)))
        assert any(e.name == "deepest.txt" for e in entries)

    def test_walk_iterative(self, tmp_dir):
        _tree(tmp_dir)
        entries = list(walk_iterative(Path(tmp_dir)))
        assert any(e.name == "a.txt" for e in entries)

    def test_walk_bfs(self, tmp_dir):
        _tree(tmp_dir)
        entries = list(walk_bfs(Path(tmp_dir)))
        assert any(e.name == "deepest.txt" for e in entries)

    def test_breadth_first_via_walk(self, tmp_dir):
        _tree(tmp_dir)
        entries = list(walk(tmp_dir, breadth_first=True))
        assert any(e.name == "a.txt" for e in entries)

    def test_iterative_via_walk(self, tmp_dir):
        _tree(tmp_dir)
        entries = list(walk(tmp_dir, iterative=True))
        assert any(e.name == "a.txt" for e in entries)

    def test_config_object(self, tmp_dir):
        _tree(tmp_dir)
        config = WalkConfig(max_depth=1, min_depth=0)
        names = {e.name for e in walk(tmp_dir, config=config)}
        assert "deepest.txt" not in names

    def test_walk_missing_dir(self, tmp_dir):
        _tree(tmp_dir)
        assert list(walk(tmp_dir / "nope")) == []

    def test_walk_file_root(self, tmp_dir):
        _tree(tmp_dir)
        (tmp_dir / "solo.txt").write_text("x")
        entries = list(walk(tmp_dir / "solo.txt"))
        assert [e.name for e in entries] == ["solo.txt"]


class TestScanDir:
    def test_scan_non_recursive(self, tmp_dir):
        _tree(tmp_dir)
        names = {e.name for e in scan_dir(tmp_dir)}
        assert "a.txt" in names
        assert "deep.txt" not in names

    def test_scan_missing(self, tmp_dir):
        _tree(tmp_dir)
        assert list(scan_dir(tmp_dir / "nope")) == []

    def test_scan_file_path(self, tmp_dir):
        _tree(tmp_dir)
        (tmp_dir / "solo.txt").write_text("x")
        assert list(scan_dir(tmp_dir / "solo.txt")) == []


class TestSymlinkTracker:
    def test_visit_new(self, tmp_dir):
        tracker = SymlinkTracker()
        assert tracker.visit(tmp_dir / "x") is True

    def test_visit_repeat(self, tmp_dir):
        target = tmp_dir / "real.txt"
        target.write_text("x")
        tracker = SymlinkTracker()
        assert tracker.visit(target) is True
        assert tracker.visit(target) is False
        tracker.clear()
        assert tracker.visit(target) is True


class TestWalkSymlinks:
    def test_follow_symlinks(self, tmp_dir):
        real = tmp_dir / "real"
        real.mkdir()
        (real / "inside.txt").write_text("x")
        link = tmp_dir / "linkdir"
        try:
            os.symlink(real, link, target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("symlinks unavailable")
        names = {e.name for e in walk(tmp_dir, follow_symlinks=True)}
        assert "inside.txt" in names

    def test_no_follow_symlinks(self, tmp_dir):
        real = tmp_dir / "real"
        real.mkdir()
        (real / "inside.txt").write_text("x")
        link = tmp_dir / "linkdir"
        try:
            os.symlink(real, link, target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("symlinks unavailable")
        # Default walk lists symlinked dirs but never descends into them
        walked = {str(e.path) for e in walk(tmp_dir)}
        assert str(real / "inside.txt") in walked
        assert str(link / "inside.txt") not in walked
        # Following terminates thanks to the cycle tracker; the link is
        # yielded and its target contents are reachable (resolved paths)
        followed = {str(e.path) for e in walk(tmp_dir, follow_symlinks=True)}
        assert str(link) in followed
        followed_resolved = {str(Path(p).resolve()) for p in followed}
        assert str(link.resolve() / "inside.txt") in followed_resolved


class TestWatcher:
    def test_create(self, tmp_dir):
        watcher = watch(tmp_dir)
        assert isinstance(watcher, Watcher)
        assert watcher.path == Path(tmp_dir).resolve() or watcher.path == Path(tmp_dir)

    def test_filter(self, tmp_dir):
        watcher = watch(tmp_dir).filter("*.txt")
        assert watcher._name_filter is not None
        assert watcher._name_filter("x.txt")

    def test_filter_by(self, tmp_dir):
        watcher = watch(tmp_dir).filter_by(lambda e: True)
        assert watcher._entry_filter is not None

    def test_debounce(self, tmp_dir):
        watcher = watch(tmp_dir).debounce(0.5)
        assert watcher._debounce_seconds == 0.5

    def test_callbacks(self, tmp_dir):
        seen = []
        watcher = (
            watch(tmp_dir)
            .on_new(lambda e: seen.append("new"))
            .on_modified(lambda e: seen.append("mod"))
            .on_deleted(lambda e: seen.append("del"))
            .on_moved(lambda e: seen.append("mov"))
        )
        assert watcher._on_new is not None
        assert watcher._on_modified is not None
        assert watcher._on_deleted is not None
        assert watcher._on_moved is not None

    def test_scan_detects_created(self, tmp_dir):
        (tmp_dir / "a.txt").write_text("a")
        watcher = Watcher(tmp_dir, 0.01)
        watcher._update_snapshot()
        (tmp_dir / "new.txt").write_text("new")
        events = watcher._scan()
        types = {e.type for e in events}
        assert "created" in types

    def test_scan_detects_modified(self, tmp_dir):
        (tmp_dir / "a.txt").write_text("a")
        watcher = Watcher(tmp_dir, 0.01)
        watcher._update_snapshot()
        time.sleep(0.02)
        (tmp_dir / "a.txt").write_text("changed content")
        events = watcher._scan()
        assert any(e.type == "modified" for e in events)

    def test_scan_detects_deleted(self, tmp_dir):
        (tmp_dir / "a.txt").write_text("a")
        watcher = Watcher(tmp_dir, 0.01)
        watcher._update_snapshot()
        (tmp_dir / "a.txt").unlink()
        events = watcher._scan()
        assert any(e.type == "deleted" for e in events)

    def test_run_for(self, tmp_dir):
        seen = []
        watcher = watch(tmp_dir, 0.05).on_new(lambda e: seen.append(e))
        (tmp_dir / "fresh.txt").write_text("f")
        watcher.run_for(0.4)
        assert seen

    def test_run_forever_start_stop(self, tmp_dir):
        seen = []
        watcher = watch(tmp_dir, 0.05).on_new(lambda e: seen.append(e))
        watcher.start()
        (tmp_dir / "later.txt").write_text("l")
        time.sleep(0.4)
        watcher.stop()
        assert seen

    def test_context_manager(self, tmp_dir):
        seen = []
        with watch(tmp_dir, 0.05).on_new(lambda e: seen.append(e)) as watcher:
            (tmp_dir / "ctx.txt").write_text("c")
            watcher.run_for(0.4)
        assert seen

    def test_watch_event_fields(self):
        event = WatchEvent(type="created", path=Path("x"))
        assert event.old_path is None
        assert event.entry is None
        assert event.timestamp

    def test_watch_nonexistent(self, tmp_dir):
        watcher = watch(tmp_dir / "nope", 0.01)
        (tmp_dir).mkdir(exist_ok=True)
        watcher.run_for(0.15)
        assert True
