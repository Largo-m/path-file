"""Folder monitoring with polling-based watcher."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from path_file._internal._iterators import scan_dir
from path_file._internal._log import get_logger, log_debug
from path_file.entries import Entry

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# WATCH EVENT
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class WatchEvent:
    """File system event."""

    type: str  # "created", "modified", "deleted", "moved"
    path: Path
    old_path: Path | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    entry: Entry | None = None


# ──────────────────────────────────────────────────────────────────────────────
# WATCHER
# ──────────────────────────────────────────────────────────────────────────────


class Watcher:
    """
    Polling-based directory watcher.

    Uses os.scandir to detect changes. No external dependencies.

    Example:
        watcher = pf.watch("~/Downloads")
        watcher.filter("*.jpg").on_new(lambda e: print(f"New: {e}"))
        watcher.run_forever()
    """

    def __init__(
        self,
        path: str | Path,
        poll_interval: float = 1.0,
        recursive: bool = False,
    ) -> None:
        self.path = Path(path).resolve()
        self.poll_interval = poll_interval
        self.recursive = recursive

        # Callbacks
        self._on_new: Callable[[WatchEvent], None] | None = None
        self._on_modified: Callable[[WatchEvent], None] | None = None
        self._on_deleted: Callable[[WatchEvent], None] | None = None
        self._on_moved: Callable[[WatchEvent], None] | None = None

        # Filters
        self._name_filter: Callable[[str], bool] | None = None
        self._entry_filter: Callable[[Entry], bool] | None = None

        # Debounce
        self._debounce_seconds: float = 0
        self._last_event: dict[Path, float] = {}

        # State
        self._snapshot: dict[Path, tuple] = {}  # path -> (size, mtime)
        self._running = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # Initialize snapshot
        self._update_snapshot()

    def _update_snapshot(self) -> None:
        """Update internal snapshot of directory state."""
        self._snapshot = {}
        try:
            for entry in scan_dir(self.path):
                self._snapshot[entry.path] = (entry.size, entry.modified.timestamp())
        except (OSError, PermissionError):
            pass

    # ─── Filter Methods ──────────────────────────────────────────────────────

    def filter(self, pattern: str) -> Watcher:
        """Filter events by glob pattern on name."""
        import fnmatch

        self._name_filter = lambda name: fnmatch.fnmatch(name, pattern)
        return self

    def filter_by(self, predicate: Callable[[Entry], bool]) -> Watcher:
        """Filter events by custom predicate on Entry."""
        self._entry_filter = predicate
        return self

    def debounce(self, seconds: float) -> Watcher:
        """Debounce events - ignore rapid successive events for same path."""
        self._debounce_seconds = seconds
        return self

    # ─── Callback Methods ────────────────────────────────────────────────────

    def on_new(self, callback: Callable[[WatchEvent], None]) -> Watcher:
        """Callback for new files."""
        self._on_new = callback
        return self

    def on_modified(self, callback: Callable[[WatchEvent], None]) -> Watcher:
        """Callback for modified files."""
        self._on_modified = callback
        return self

    def on_deleted(self, callback: Callable[[WatchEvent], None]) -> Watcher:
        """Callback for deleted files."""
        self._on_deleted = callback
        return self

    def on_moved(self, callback: Callable[[WatchEvent], None]) -> Watcher:
        """Callback for moved/renamed files."""
        self._on_moved = callback
        return self

    # ─── Event Processing ────────────────────────────────────────────────────

    def _scan(self) -> list[WatchEvent]:
        """Scan for changes and return list of events."""
        events = []
        current: dict[Path, tuple] = {}

        try:
            for entry in scan_dir(self.path):
                current[entry.path] = (entry.size, entry.modified.timestamp())
        except (OSError, PermissionError):
            pass

        # Detect changes
        all_paths = set(self._snapshot.keys()) | set(current.keys())

        for path in all_paths:
            old = self._snapshot.get(path)
            new = current.get(path)

            if old is None and new is not None:
                # Created
                events.append(WatchEvent("created", path, entry=Entry.from_path(path)))
            elif old is not None and new is None:
                # Deleted
                events.append(WatchEvent("deleted", path))
            elif old is not None and new is not None:
                # Check for modification
                if old[0] != new[0] or old[1] != new[1]:
                    events.append(WatchEvent("modified", path, entry=Entry.from_path(path)))

        # Apply filters (name glob / entry predicate)
        events = [e for e in events if self._filter_event(e)]

        # Detect moves (heuristic: similar size, one deleted, one created)
        # This is a simplified detection
        created = [e for e in events if e.type == "created"]
        deleted = [e for e in events if e.type == "deleted"]

        for c in created:
            for d in deleted:
                if c.entry and abs(c.entry.size - self._snapshot.get(d.path, (0,))[0]) < 1024:
                    # Likely a move
                    events.remove(c)
                    events.remove(d)
                    events.append(WatchEvent("moved", c.path, d.path, entry=c.entry))
                    break

        # Update snapshot so the next scan compares against current state
        self._snapshot = current

        return events

    def _filter_event(self, event: WatchEvent) -> bool:
        """Apply filters to event."""
        if self._name_filter and not self._name_filter(event.path.name):
            return False
        if self._entry_filter and event.entry and not self._entry_filter(event.entry):
            return False
        return True

    def _debounce_event(self, event: WatchEvent) -> bool:
        """Check if event should be debounced."""
        if self._debounce_seconds <= 0:
            return False

        now = time.time()
        key = event.path

        if key in self._last_event:
            if now - self._last_event[key] < self._debounce_seconds:
                return True

        self._last_event[key] = now
        return False

    def _dispatch(self, event: WatchEvent) -> None:
        """Dispatch event to appropriate callback."""
        if self._debounce_event(event):
            return

        try:
            if event.type == "created" and self._on_new:
                self._on_new(event)
            elif event.type == "modified" and self._on_modified:
                self._on_modified(event)
            elif event.type == "deleted" and self._on_deleted:
                self._on_deleted(event)
            elif event.type == "moved" and self._on_moved:
                self._on_moved(event)
        except Exception as e:
            log_debug(f"Watcher callback error: {e}")

    # ─── Control Methods ────────────────────────────────────────────────────

    def _run_loop(self) -> None:
        """Main polling loop."""
        while not self._stop_event.is_set():
            try:
                events = self._scan()
                for event in events:
                    if self._filter_event(event):
                        self._dispatch(event)

                # Update snapshot
                self._snapshot = {}
                try:
                    for entry in scan_dir(self.path):
                        self._snapshot[entry.path] = (entry.size, entry.modified.timestamp())
                except (OSError, PermissionError):
                    pass

            except Exception as e:
                log_debug(f"Watcher scan error: {e}")

            # Wait for next poll or stop
            self._stop_event.wait(self.poll_interval)

    def start(self) -> Watcher:
        """Start watching in background thread."""
        if self._running:
            return self

        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        """Stop watching."""
        self._running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    def run_forever(self) -> None:
        """Run watcher in current thread (blocking)."""
        self._running = True
        self._stop_event.clear()
        try:
            self._run_loop()
        except KeyboardInterrupt:
            pass
        finally:
            self._running = False

    def run_for(self, duration: float) -> None:
        """Run watcher for specified seconds."""
        self.start()
        time.sleep(duration)
        self.stop()

    def __enter__(self) -> Watcher:
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()


# ──────────────────────────────────────────────────────────────────────────────
# CONVENIENCE FUNCTION
# ──────────────────────────────────────────────────────────────────────────────


def watch(
    path: str | Path,
    poll_interval: float = 1.0,
    recursive: bool = False,
) -> Watcher:
    """Create a new Watcher."""
    return Watcher(path, poll_interval, recursive)


from dataclasses import field
