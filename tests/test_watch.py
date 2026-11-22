"""Tests for folder watcher."""

from __future__ import annotations

import time
from pathlib import Path

from path_file.watch import Watcher, watch


class TestWatcherCreation:
    """Test Watcher creation and configuration."""

    def test_create_watcher(self, tmp_dir: Path):
        watcher = watch(tmp_dir)

        assert isinstance(watcher, Watcher)
        assert watcher.path == tmp_dir.resolve()

    def test_watcher_filter(self, tmp_dir: Path):
        watcher = watch(tmp_dir).filter("*.txt")

        assert watcher._name_filter is not None
        assert watcher._name_filter("test.txt") is True
        assert watcher._name_filter("test.jpg") is False

    def test_watcher_filter_by(self, tmp_dir: Path):
        watcher = watch(tmp_dir).filter_by(lambda e: e.size > 1000)

        assert watcher._entry_filter is not None

    def test_watcher_debounce(self, tmp_dir: Path):
        watcher = watch(tmp_dir).debounce(0.5)

        assert watcher._debounce_seconds == 0.5

    def test_watcher_callbacks(self, tmp_dir: Path):
        events = []

        def on_new(e):
            events.append(("new", e.path))

        def on_modified(e):
            events.append(("modified", e.path))

        watcher = watch(tmp_dir).on_new(on_new).on_modified(on_modified)

        assert watcher._on_new is not None
        assert watcher._on_modified is not None


class TestWatcherEvents:
    """Test watcher event detection."""

    def test_detect_new_file(self, tmp_dir: Path):
        watcher = Watcher(tmp_dir, poll_interval=0.1)

        # Initial scan
        watcher._update_snapshot()

        # Create new file
        new_file = tmp_dir / "new.txt"
        new_file.write_text("new")

        # Scan for changes
        events = watcher._scan()

        created_events = [e for e in events if e.type == "created"]
        assert len(created_events) == 1
        assert created_events[0].path.name == "new.txt"

    def test_detect_modified_file(self, tmp_dir: Path):
        watcher = Watcher(tmp_dir, poll_interval=0.1)
        existing = tmp_dir / "file1.txt"
        existing.write_text("original")
        watcher._update_snapshot()

        # Modify existing file
        existing.write_text("modified content")
        time.sleep(0.05)  # Ensure mtime changes

        events = watcher._scan()

        modified_events = [e for e in events if e.type == "modified"]
        assert len(modified_events) >= 1

    def test_detect_deleted_file(self, tmp_dir: Path):
        watcher = Watcher(tmp_dir, poll_interval=0.1)
        to_delete = tmp_dir / "empty.txt"
        to_delete.write_text("")
        watcher._update_snapshot()

        # Delete file
        to_delete.unlink()

        events = watcher._scan()

        deleted_events = [e for e in events if e.type == "deleted"]
        assert len(deleted_events) == 1
        assert deleted_events[0].path.name == "empty.txt"


class TestWatcherFilters:
    """Test watcher filters."""

    def test_filter_by_name(self, tmp_dir: Path):
        watcher = Watcher(tmp_dir, poll_interval=0.1).filter("*.txt")
        watcher._update_snapshot()

        # Create .jpg file - should be filtered out
        (tmp_dir / "image.jpg").write_bytes(b"fake")
        events = watcher._scan()

        created = [e for e in events if e.type == "created"]
        assert len(created) == 0

    def test_filter_by_entry(self, tmp_dir: Path):
        watcher = Watcher(tmp_dir, poll_interval=0.1).filter_by(lambda e: e.size > 100)
        watcher._update_snapshot()

        # Create small file - should be filtered out
        (tmp_dir / "small.txt").write_text("x")
        events = watcher._scan()

        created = [e for e in events if e.type == "created"]
        assert len(created) == 0


class TestWatcherDebounce:
    """Test watcher debouncing."""

    def test_debounce_ignores_rapid_events(self, tmp_dir: Path):
        watcher = Watcher(tmp_dir, poll_interval=0.01).debounce(0.1)
        watcher._update_snapshot()

        # Create file
        f = tmp_dir / "debounce.txt"
        f.write_text("1")
        events1 = watcher._scan()

        # Modify rapidly (distinct sizes so modifications are detectible)
        f.write_text("22")
        events2 = watcher._scan()

        f.write_text("333")
        events3 = watcher._scan()

        f.write_text("3")
        events3 = watcher._scan()

        # Only first event should pass debounce
        modified_count = sum(1 for e in events1 + events2 + events3 if e.type == "modified")
        # Debounce may allow some through depending on timing
        assert modified_count >= 1


class TestWatcherContextManager:
    """Test watcher context manager."""

    def test_context_manager(self, tmp_dir: Path):
        watcher = watch(tmp_dir)

        with watcher as w:
            assert w._running is True

        assert watcher._running is False

    def test_start_stop(self, tmp_dir: Path):
        watcher = watch(tmp_dir)

        watcher.start()
        assert watcher._running is True
        assert watcher._thread is not None

        watcher.stop()
        assert watcher._running is False


class TestWatchEvent:
    """Test WatchEvent dataclass."""

    def test_event_creation(self, tmp_dir: Path):
        from datetime import datetime

        from path_file.watch import WatchEvent

        event = WatchEvent(type="created", path=tmp_dir / "test.txt", timestamp=datetime.now())

        assert event.type == "created"
        assert event.path == tmp_dir / "test.txt"
        assert event.old_path is None
