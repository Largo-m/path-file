"""High-performance filesystem iterators using os.scandir."""

from __future__ import annotations

import contextlib
import os
import threading
from collections.abc import Callable, Iterator
from pathlib import Path

from path_file.entries import Entry

# ──────────────────────────────────────────────────────────────────────────────
# WALK CONFIGURATION
# ──────────────────────────────────────────────────────────────────────────────


class WalkConfig:
    """Configuration for directory walking."""

    def __init__(
        self,
        follow_symlinks: bool = False,
        max_depth: int | None = None,
        min_depth: int = 0,
        ignore_permission_errors: bool = True,
        on_error: Callable[[str, OSError], None] | None = None,
    ) -> None:
        self.follow_symlinks = follow_symlinks
        self.max_depth = max_depth
        self.min_depth = min_depth
        self.ignore_permission_errors = ignore_permission_errors
        self.on_error = on_error


# ──────────────────────────────────────────────────────────────────────────────
# SYMLINK CYCLE DETECTION
# ──────────────────────────────────────────────────────────────────────────────


class SymlinkTracker:
    """Track visited symlinks to detect cycles."""

    def __init__(self) -> None:
        self._visited: set[tuple[int, int]] = set()  # (st_dev, st_ino)
        self._lock = threading.Lock()

    def visit(self, path: Path) -> bool:
        """
        Mark path as visited.
        Returns True if this is a new visit, False if cycle detected.
        """
        try:
            st = path.stat()
            key = (st.st_dev, st.st_ino)
            with self._lock:
                if key in self._visited:
                    return False
                self._visited.add(key)
            return True
        except (OSError, PermissionError):
            return True  # Can't stat, assume safe

    def clear(self) -> None:
        """Clear visited set."""
        with self._lock:
            self._visited.clear()


# ──────────────────────────────────────────────────────────────────────────────
# RECURSIVE WALK (DFS) - MAIN IMPLEMENTATION
# ──────────────────────────────────────────────────────────────────────────────


def walk_recursive(
    root: Path,
    config: WalkConfig | None = None,
    _depth: int = 0,
    _tracker: SymlinkTracker | None = None,
) -> Iterator[Entry]:
    """
    Depth-first recursive walk using os.scandir for performance.

    Yields Entry objects for each filesystem entry.
    """
    config = config or WalkConfig()
    root = Path(root).resolve()

    # Single file as root: yield it directly
    if root.is_file():
        if _depth >= config.min_depth:
            with contextlib.suppress(OSError, PermissionError):
                yield Entry.from_path(root)
        return

    if config.max_depth is not None and _depth > config.max_depth:
        return

    if _tracker is None and config.follow_symlinks:
        _tracker = SymlinkTracker()

    try:
        with os.scandir(root) as it:
            for entry in it:
                try:
                    yield from _process_entry(entry, _depth, config, _tracker)
                except (PermissionError, OSError) as e:
                    if not config.ignore_permission_errors:
                        raise
                    if config.on_error:
                        config.on_error(entry.path, e)
    except (PermissionError, OSError) as e:
        if not config.ignore_permission_errors:
            raise
        if config.on_error:
            config.on_error(str(root), e)


def _process_entry(
    entry: os.DirEntry[str],
    depth: int,
    config: WalkConfig,
    tracker: SymlinkTracker | None,
) -> Iterator[Entry]:
    """Process a single directory entry."""
    path = Path(entry.path)

    # Check if we should follow symlinks
    is_symlink = entry.is_symlink()

    if is_symlink and config.follow_symlinks:
        if tracker and not tracker.visit(path):
            # Cycle detected
            return
        # Yield the symlink entry itself before following it
        if depth >= config.min_depth:
            try:
                yield Entry.from_stat(path, entry.stat(follow_symlinks=False))
            except (OSError, PermissionError):
                with contextlib.suppress(OSError, PermissionError):
                    yield Entry.from_path(path)
        # Follow the symlink - recurse if it's a directory
        if entry.is_dir(follow_symlinks=True):
            yield from walk_recursive(path, config, depth + 1, tracker)
            return

    # Yield current entry if at minimum depth
    if depth >= config.min_depth:
        try:
            yield Entry.from_stat(path, entry.stat(follow_symlinks=False))
        except (OSError, PermissionError):
            # Fallback to basic Entry
            with contextlib.suppress(OSError, PermissionError):
                yield Entry.from_path(path)

    # Recurse into subdirectories
    if entry.is_dir(follow_symlinks=False):
        if is_symlink and not config.follow_symlinks:
            return  # Don't follow symlinks to directories unless configured
        yield from walk_recursive(path, config, depth + 1, tracker)


# ──────────────────────────────────────────────────────────────────────────────
# ITERATIVE WALK (NON-RECURSIVE) - FOR VERY DEEP TREES
# ──────────────────────────────────────────────────────────────────────────────


def walk_iterative(
    root: Path,
    config: WalkConfig | None = None,
) -> Iterator[Entry]:
    """
    Non-recursive iterative walk using explicit stack.
    Better for very deep directory trees to avoid recursion limits.
    """
    config = config or WalkConfig()
    root = Path(root).resolve()

    stack = [(root, 0)]
    tracker = SymlinkTracker() if config.follow_symlinks else None

    while stack:
        current_path, depth = stack.pop()

        if config.max_depth is not None and depth > config.max_depth:
            continue

        try:
            with os.scandir(current_path) as it:
                entries = list(it)
        except (PermissionError, OSError) as e:
            if not config.ignore_permission_errors:
                raise
            if config.on_error:
                config.on_error(str(current_path), e)
            continue

        # Process in reverse for DFS-like order (stack is LIFO)
        for entry in reversed(entries):
            path = Path(entry.path)
            is_symlink = entry.is_symlink()

            if is_symlink and config.follow_symlinks:
                if tracker and not tracker.visit(path):
                    continue
                if entry.is_dir(follow_symlinks=True):
                    stack.append((path, depth + 1))
                    continue

            if depth >= config.min_depth:
                try:
                    yield Entry.from_stat(path, entry.stat(follow_symlinks=False))
                except (OSError, PermissionError):
                    with contextlib.suppress(OSError, PermissionError):
                        yield Entry.from_path(path)

            if entry.is_dir(follow_symlinks=False):
                if is_symlink and not config.follow_symlinks:
                    continue
                stack.append((path, depth + 1))


# ──────────────────────────────────────────────────────────────────────────────
# BREADTH-FIRST WALK
# ──────────────────────────────────────────────────────────────────────────────


def walk_bfs(
    root: Path,
    config: WalkConfig | None = None,
) -> Iterator[Entry]:
    """
    Breadth-first walk using queue.
    Processes directories level by level.
    """
    from collections import deque

    config = config or WalkConfig()
    root = Path(root).resolve()

    queue = deque([(root, 0)])
    tracker = SymlinkTracker() if config.follow_symlinks else None

    while queue:
        current_path, depth = queue.popleft()

        if config.max_depth is not None and depth > config.max_depth:
            continue

        try:
            with os.scandir(current_path) as it:
                entries = list(it)
        except (PermissionError, OSError) as e:
            if not config.ignore_permission_errors:
                raise
            if config.on_error:
                config.on_error(str(current_path), e)
            continue

        # First yield all entries at this level
        for entry in entries:
            path = Path(entry.path)
            is_symlink = entry.is_symlink()

            if is_symlink and config.follow_symlinks and tracker and not tracker.visit(path):
                continue

            if depth >= config.min_depth:
                try:
                    yield Entry.from_stat(path, entry.stat(follow_symlinks=False))
                except (OSError, PermissionError):
                    with contextlib.suppress(OSError, PermissionError):
                        yield Entry.from_path(path)

        # Then queue subdirectories for next level
        for entry in entries:
            if entry.is_dir(follow_symlinks=False):
                is_symlink = entry.is_symlink()
                if is_symlink and not config.follow_symlinks:
                    continue
                path = Path(entry.path)
                queue.append((path, depth + 1))


# ──────────────────────────────────────────────────────────────────────────────
# CONVENIENCE FUNCTIONS
# ──────────────────────────────────────────────────────────────────────────────


def walk(
    root: str | Path,
    follow_symlinks: bool = False,
    max_depth: int | None = None,
    min_depth: int = 0,
    breadth_first: bool = False,
    iterative: bool = False,
    config: WalkConfig | None = None,
) -> Iterator[Entry]:
    """
    Main entry point for walking a directory tree.

    Args:
        root: Root directory to walk
        follow_symlinks: Follow symbolic links to directories
        max_depth: Maximum depth to traverse (None = unlimited)
        min_depth: Minimum depth before yielding entries
        breadth_first: Use BFS instead of DFS
        iterative: Use iterative (non-recursive) implementation
        config: Optional WalkConfig object (overrides other params)

    Yields:
        Entry objects for each file/directory
    """
    if config is None:
        config = WalkConfig(
            follow_symlinks=follow_symlinks,
            max_depth=max_depth,
            min_depth=min_depth,
        )

    if breadth_first:
        return walk_bfs(Path(root), config)
    elif iterative:
        return walk_iterative(Path(root), config)
    else:
        return walk_recursive(Path(root), config)


# ──────────────────────────────────────────────────────────────────────────────
# FAST SCOPED WALK (for single directory, no recursion)
# ──────────────────────────────────────────────────────────────────────────────


def scan_dir(path: str | Path) -> Iterator[Entry]:
    """
    Fast non-recursive scan of a single directory.
    Uses os.scandir directly, no recursion.
    """
    path = Path(path).resolve()
    try:
        with os.scandir(path) as it:
            for entry in it:
                try:
                    yield Entry.from_stat(Path(entry.path), entry.stat(follow_symlinks=False))
                except (OSError, PermissionError):
                    with contextlib.suppress(OSError, PermissionError):
                        yield Entry.from_path(entry.path)
    except (PermissionError, OSError):
        return  # Silently return empty iterator
