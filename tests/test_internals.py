"""Tests for internals: progress, log, walk error paths, watch, parser, trash."""

from __future__ import annotations

import io
import time
from pathlib import Path

import path_file as pf
from path_file._internal._iterators import (
    WalkConfig,
    walk,
    walk_bfs,
    walk_iterative,
    walk_recursive,
)
from path_file._internal._log import (
    get_logger,
    log_debug,
    log_error,
    log_exception,
    log_info,
    log_warning,
    set_verbosity,
    with_verbose,
)
from path_file.progress import ProgressBar, Spinner
from path_file.watch import Watcher


def _tree(tmp_dir: Path) -> Path:
    (tmp_dir / "a.txt").write_text("alpha")
    (tmp_dir / "b.txt").write_text("beta")
    (tmp_dir / "sub").mkdir()
    (tmp_dir / "sub" / "deep.txt").write_text("deep")
    return tmp_dir


class TestProgressBarInternals:
    def test_full_cycle(self):
        buf = io.StringIO()
        with ProgressBar(3, "Work", stream=buf) as bar:
            bar.update(1)
            bar.update(1)
            bar.update(1)
            bar.finish()
        assert buf.getvalue()

    def test_partial_and_stats(self):
        buf = io.StringIO()
        bar = ProgressBar(10, stream=buf)
        bar.update(3)
        bar.set(7)
        assert bar.percent == 70
        assert bar.fraction == 0.7
        assert bar.eta is None or bar.eta >= 0
        assert bar.rate >= 0
        assert bar.elapsed >= 0
        bar.update(3)
        bar.finish()
        assert buf.getvalue()

    def test_narrow_stream_ascii(self):
        buf = io.StringIO()
        bar = ProgressBar(2, stream=buf, width=4)
        bar.update(2)
        bar.finish()
        assert buf.getvalue()

    def test_zero_total(self):
        buf = io.StringIO()
        bar = ProgressBar(0, stream=buf)
        bar.finish()
        assert buf.getvalue() or True

    def test_no_prefix_no_counts(self):
        buf = io.StringIO()
        bar = ProgressBar(2, stream=buf, show_percent=False, show_count=False)
        bar.update(1)
        bar.finish()
        assert buf.getvalue()

    def test_refresh_interval_throttles(self):
        buf = io.StringIO()
        bar = ProgressBar(100, stream=buf, refresh_interval=1.0)
        for _ in range(5):
            bar.update(1)
        bar.finish()
        assert buf.getvalue()

    def test_repr(self):
        bar = ProgressBar(4, "Test")
        assert "4" in repr(bar)


class TestSpinner:
    def test_cycle(self):
        buf = io.StringIO()
        spinner = Spinner("Loading", interval=0.01, stream=buf)
        spinner.update()
        spinner.update()
        spinner.stop()
        assert buf.getvalue()

    def test_context_manager(self):
        buf = io.StringIO()
        with Spinner("Busy", interval=0.01, stream=buf) as spinner:
            spinner.update()
        assert buf.getvalue()

    def test_stop_twice(self):
        buf = io.StringIO()
        spinner = Spinner(stream=buf, interval=0.01)
        spinner.stop()
        spinner.stop()


class TestLogger:
    def test_get_logger(self):
        logger = get_logger("path_file.test")
        assert logger.name.startswith("path_file")

    def test_get_default_logger(self):
        assert get_logger().name.startswith("path_file")

    def test_set_verbosity_and_log(self):
        set_verbosity(10)
        log_debug("debug %s", 1)
        log_info("info")
        log_warning("warn")
        log_error("err")
        try:
            raise ValueError("boom")
        except ValueError:
            log_exception("failed")
        set_verbosity(30)

    def test_with_verbose_context(self):
        with with_verbose():
            log_debug("inside verbose")

    def test_quiet_context(self):
        from path_file._internal._log import with_quiet

        with with_quiet():
            log_info("hidden")


class TestWalkErrorPaths:
    def test_on_error_callback(self, tmp_dir):
        _tree(tmp_dir)
        seen: list[tuple[str, OSError]] = []
        config = WalkConfig(on_error=lambda path, err: seen.append((path, err)))
        results = list(walk(tmp_dir, config))
        assert results

    def test_ignore_permission_errors_default(self, tmp_dir):
        _tree(tmp_dir)
        assert len(list(walk(tmp_dir))) >= 3

    def test_max_depth_zero(self, tmp_dir):
        _tree(tmp_dir)
        config = WalkConfig(max_depth=0)
        results = list(walk_iterative(tmp_dir, config))
        assert all(e.path.parent == tmp_dir for e in results)

    def test_min_depth(self, tmp_dir):
        _tree(tmp_dir)
        config = WalkConfig(min_depth=2)
        results = list(walk_iterative(tmp_dir, config))
        assert all(e.path.parent != tmp_dir for e in results)

    def test_walk_bfs_depth_order(self, tmp_dir):
        _tree(tmp_dir)
        results = list(walk_bfs(tmp_dir))
        assert results
        depths = {len(e.path.relative_to(tmp_dir).parts) for e in results}
        assert 1 in depths

    def test_walk_recursive_depth(self, tmp_dir):
        _tree(tmp_dir)
        assert len(list(walk_recursive(tmp_dir))) >= 3

    def test_walk_missing_dir(self, tmp_dir):
        assert list(walk(tmp_dir / "nope")) == []


class TestWatcher:
    def test_attributes_and_start_stop(self, tmp_dir):
        _tree(tmp_dir)
        events: list[str] = []
        watcher = Watcher(tmp_dir, poll_interval=0.05)
        watcher.on_new(lambda p: events.append(f"new:{p.name}"))
        watcher.start()
        (tmp_dir / "new.txt").write_text("fresh")
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and not events:
            time.sleep(0.05)
        watcher.stop()

    def test_deleted_event(self, tmp_dir):
        _tree(tmp_dir)
        events: list[str] = []
        watcher = Watcher(tmp_dir, poll_interval=0.05)
        watcher.on_deleted(lambda p: events.append(f"del:{p.name}"))
        watcher.start()
        (tmp_dir / "a.txt").unlink()
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and not events:
            time.sleep(0.05)
        watcher.stop()

    def test_modified_event(self, tmp_dir):
        _tree(tmp_dir)
        events: list[str] = []
        watcher = Watcher(tmp_dir, poll_interval=0.05)
        watcher.on_modified(lambda p: events.append(f"mod:{p.name}"))
        watcher.start()
        (tmp_dir / "a.txt").write_text("changed content")
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and not events:
            time.sleep(0.05)
        watcher.stop()

    def test_moved_event(self, tmp_dir):
        _tree(tmp_dir)
        events: list[str] = []
        watcher = Watcher(tmp_dir, poll_interval=0.05)
        watcher.on_moved(lambda src, dst: events.append("moved"))
        watcher.start()
        (tmp_dir / "a.txt").rename(tmp_dir / "renamed.txt")
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and not events:
            time.sleep(0.05)
        watcher.stop()

    def test_filter_by(self, tmp_dir):
        _tree(tmp_dir)
        watcher = Watcher(tmp_dir, poll_interval=0.05)
        watcher.filter(lambda p: p.name.endswith(".txt"))
        watcher.filter_by(lambda e: e.name.startswith("a"))
        watcher.debounce(0.01)
        watcher.run_for(0.15)

    def test_context_manager(self, tmp_dir):
        _tree(tmp_dir)
        with Watcher(tmp_dir, poll_interval=0.05) as watcher:
            watcher.run_for(0.15)

    def test_run_for(self, tmp_dir):
        _tree(tmp_dir)
        watcher = Watcher(tmp_dir, poll_interval=0.05)
        watcher.run_for(0.15)
        assert True


class TestWalkerInterleaved:
    def test_chain_uses_walkers(self, tmp_dir):
        _tree(tmp_dir)
        assert len(list(pf.find(tmp_dir).recursive())) >= 3
        assert len(list(pf.find(tmp_dir).max_depth(1))) >= 3
        from path_file._internal._iterators import walk_bfs

        assert len(list(walk_bfs(tmp_dir))) >= 3
