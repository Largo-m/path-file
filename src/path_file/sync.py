"""Directory synchronization utilities."""

from __future__ import annotations

import fnmatch
import os
import shutil
from pathlib import Path

from path_file._internal._iterators import WalkConfig, walk
from path_file._internal._log import get_logger
from path_file.entries import SyncDiff, SyncResult
from path_file.exceptions import SyncConflictError
from path_file.hash import hash_file

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# GITIGNORE-STYLE PATTERN MATCHER
# ──────────────────────────────────────────────────────────────────────────────


class IgnoreMatcher:
    """Gitignore-style pattern matcher."""

    def __init__(self, patterns: list[str] = None) -> None:
        self.patterns: list[tuple[bool, str]] = []  # (negate, pattern)
        if patterns:
            for p in patterns:
                self.add_pattern(p)

    def add_pattern(self, pattern: str) -> None:
        """Add a pattern."""
        pattern = pattern.strip()
        if not pattern or pattern.startswith("#"):
            return

        negate = pattern.startswith("!")
        if negate:
            pattern = pattern[1:]

        self.patterns.append((negate, pattern))

    def load_file(self, path: Path) -> None:
        """Load patterns from .gitignore-style file."""
        try:
            content = path.read_text(encoding="utf-8")
            for line in content.splitlines():
                self.add_pattern(line)
        except (OSError, PermissionError):
            pass

    def match(self, path: Path, is_dir: bool = False) -> bool:
        """
        Check if path matches any pattern.
        Returns True if should be ignored.
        """
        # Get relative path for matching
        path_str = str(path)

        result = False
        for negate, pattern in self.patterns:
            if self._match_pattern(path_str, pattern, is_dir):
                result = not negate

        return result

    def _match_pattern(self, path: str, pattern: str, is_dir: bool) -> bool:
        """Match a single pattern."""
        # Normalize path separators
        path = path.replace("/", os.sep).replace("\\", os.sep)

        # Normalize pattern
        orig_pattern = pattern
        pattern = pattern.rstrip("/")

        # Check if this is a directory pattern (ends with /)
        is_dir_pattern = orig_pattern.endswith("/")

        # If it's a directory pattern but we're matching a file, check if file is inside that dir
        if is_dir_pattern:
            # Pattern like "build" should match "build/" (dir) and "build/file.txt" (file in dir)
            # But NOT "src/build" or "src/build/file.txt"
            if is_dir:
                # Matching a directory - exact match on basename or full path
                return fnmatch.fnmatch(os.path.basename(path), pattern) or fnmatch.fnmatch(
                    path, pattern
                )
            else:
                # Matching a file - check if file is directly inside the directory (not nested)
                # path = "build/file.txt", pattern = "build"
                # Should match: path starts with pattern + sep AND pattern is the first component
                return path == pattern or (path.startswith(pattern + os.sep))

        # Handle **/
        if pattern.startswith("**/"):
            # Match anywhere in path
            rest = pattern[3:]
            return fnmatch.fnmatch(os.path.basename(path), rest) or any(
                fnmatch.fnmatch(part, rest) for part in path.split(os.sep)
            )

        # Handle /*/ (any directory)
        if "/*/" in pattern:
            # Convert to regex-like
            pass

        # Simple fnmatch - match against full path or basename
        return fnmatch.fnmatch(os.path.basename(path), pattern) or fnmatch.fnmatch(path, pattern)


# ──────────────────────────────────────────────────────────────────────────────
# SYNCER
# ──────────────────────────────────────────────────────────────────────────────


class Syncer:
    """
    Directory synchronization with hash-based comparison.

    Example:
        syncer = pf.sync("~/Documents", "/backup/Documents")
        syncer.direction("source_to_dest").delete_extras(True).dry_run()
        diff = syncer.compare()
        print(diff.summary())
        syncer.execute()
    """

    def __init__(
        self,
        source: str | Path,
        dest: str | Path,
    ) -> None:
        self.source = Path(source).resolve()
        self.dest = Path(dest).resolve()

        self._direction: str = "source_to_dest"  # source_to_dest, dest_to_source, bidirectional
        self._ignore_matcher = IgnoreMatcher()
        self._delete_extras = False
        self._dry_run = False
        self._parallel = 1
        self._progress = False
        self._hash_algorithm = "sha256"
        self._workers = 4

        # Conflict resolution for bidirectional
        self._conflict_strategy: str = "error"  # error, source_wins, dest_wins, newer_wins

    # ─── Configuration ──────────────────────────────────────────────────────

    def direction(self, d: str) -> Syncer:
        """Set sync direction."""
        if d not in ("source_to_dest", "dest_to_source", "bidirectional"):
            raise ValueError("Direction must be: source_to_dest, dest_to_source, or bidirectional")
        self._direction = d
        return self

    def ignore(self, patterns: list[str]) -> Syncer:
        """Add ignore patterns."""
        for p in patterns:
            self._ignore_matcher.add_pattern(p)
        return self

    def ignore_file(self, path: str | Path) -> Syncer:
        """Load ignore patterns from file."""
        self._ignore_matcher.load_file(Path(path))
        return self

    def delete_extras(self, enabled: bool = True) -> Syncer:
        """Delete files in dest not in source (for source_to_dest)."""
        self._delete_extras = enabled
        return self

    def dry_run(self, enabled: bool = True) -> Syncer:
        """Enable/disable dry-run mode."""
        self._dry_run = enabled
        return self

    def parallel(self, workers: int = 4) -> Syncer:
        """Set parallel workers."""
        self._workers = max(1, workers)
        self._parallel = self._workers
        return self

    def progress(self, enabled: bool = True) -> Syncer:
        """Show progress bar."""
        self._progress = enabled
        return self

    def hash_algorithm(self, algo: str) -> Syncer:
        """Set hash algorithm for comparison."""
        self._hash_algorithm = algo
        return self

    def conflict_strategy(self, strategy: str) -> Syncer:
        """Set conflict resolution for bidirectional sync."""
        if strategy not in ("error", "source_wins", "dest_wins", "newer_wins"):
            raise ValueError("Strategy must be: error, source_wins, dest_wins, newer_wins")
        self._conflict_strategy = strategy
        return self

    # ─── Core Operations ────────────────────────────────────────────────────

    def compare(self) -> SyncDiff:
        """Compare source and destination, return diff."""
        return self._compute_diff()

    def execute(self) -> SyncResult:
        """Execute synchronization based on last compare."""
        diff = self._compute_diff()
        return self._apply_diff(diff)

    def _compute_diff(self) -> SyncDiff:
        """Compute differences between source and dest."""
        diff = SyncDiff()

        # Walk both directories
        src_files = self._walk_files(self.source)
        dest_files = self._walk_files(self.dest)

        src_rel = {p.relative_to(self.source): p for p in src_files}
        dest_rel = {p.relative_to(self.dest): p for p in dest_files}

        all_rel = set(src_rel.keys()) | set(dest_rel.keys())

        for rel in all_rel:
            src_path = src_rel.get(rel)
            dest_path = dest_rel.get(rel)

            # Check ignore patterns
            if self._ignore_matcher.match(rel, src_path.is_dir() if src_path else False):
                continue

            if src_path and not dest_path:
                # New in source
                if self._direction in ("source_to_dest", "bidirectional"):
                    diff.to_add.append(rel)
            elif not src_path and dest_path:
                # Only in dest
                if self._direction == "dest_to_source":
                    diff.to_add.append(rel)  # Add to source
                elif self._direction == "source_to_dest" and self._delete_extras:
                    diff.to_delete.append(rel)
            elif src_path and dest_path:
                # In both - compare
                if self._files_differ(src_path, dest_path):
                    if self._direction == "bidirectional":
                        diff.conflicts.append((src_path, dest_path))
                    elif self._direction == "source_to_dest":
                        diff.to_update.append(rel)
                    elif self._direction == "dest_to_source":
                        diff.to_update.append(rel)  # Update source
                else:
                    diff.unchanged.append(rel)

        return diff

    def _files_differ(self, src: Path, dest: Path) -> bool:
        """Check if two files differ using hash."""
        if src.stat().st_size != dest.stat().st_size:
            return True

        src_hash = hash_file(src, self._hash_algorithm)
        dest_hash = hash_file(dest, self._hash_algorithm)
        return src_hash != dest_hash

    def _walk_files(self, root: Path) -> list[Path]:
        """Walk directory and return all files."""
        files = []
        config = WalkConfig(follow_symlinks=False)
        for entry in walk(root, config=config):
            if entry.is_file:
                files.append(entry.path)
        return files

    def _apply_diff(self, diff: SyncDiff) -> SyncResult:
        """Apply the computed diff."""
        errors = []
        count = 0
        total_size = 0

        if self._dry_run:
            return SyncResult(
                action="sync",
                count=len(diff.to_add) + len(diff.to_update) + len(diff.to_delete),
                total_size=0,
                dry_run=True,
                diff=diff,
            )

        # Progress bar
        progress_bar = None
        if self._progress:
            from path_file.progress import ProgressBar

            total = len(diff.to_add) + len(diff.to_update) + len(diff.to_delete)
            progress_bar = ProgressBar(total, prefix="Sync: ")
            progress_bar.__enter__()

        try:
            # Handle additions/updates
            for rel in diff.to_add + diff.to_update:
                src = self.source / rel
                dest = self.dest / rel

                try:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest)
                    count += 1
                    total_size += src.stat().st_size
                except Exception as e:
                    errors.append((rel, e))

                if progress_bar:
                    progress_bar.update(1)

            # Handle deletions
            for rel in diff.to_delete:
                dest = self.dest / rel
                try:
                    if dest.is_dir():
                        shutil.rmtree(dest)
                    else:
                        dest.unlink()
                    count += 1
                except Exception as e:
                    errors.append((rel, e))

                if progress_bar:
                    progress_bar.update(1)

            # Handle conflicts (bidirectional)
            for src, dest in diff.conflicts:
                if self._conflict_strategy == "error":
                    src_hash = hash_file(src, self._hash_algorithm)
                    dest_hash = hash_file(dest, self._hash_algorithm)
                    raise SyncConflictError(
                        str(src.relative_to(self.source)),
                        src_hash,
                        dest_hash,
                    )
                elif self._conflict_strategy == "source_wins":
                    shutil.copy2(src, dest)
                    count += 1
                    total_size += src.stat().st_size
                elif self._conflict_strategy == "dest_wins":
                    shutil.copy2(dest, src)
                    count += 1
                    total_size += dest.stat().st_size
                elif self._conflict_strategy == "newer_wins":
                    if src.stat().st_mtime > dest.stat().st_mtime:
                        shutil.copy2(src, dest)
                    else:
                        shutil.copy2(dest, src)
                    count += 1

                if progress_bar:
                    progress_bar.update(1)

        finally:
            if progress_bar:
                progress_bar.finish()
                progress_bar.__exit__(None, None, None)

        return SyncResult(
            action="sync",
            count=count,
            total_size=total_size,
            duration=0.0,
            errors=errors,
            dry_run=self._dry_run,
            diff=diff,
        )


# ──────────────────────────────────────────────────────────────────────────────
# CONVENIENCE FUNCTION
# ──────────────────────────────────────────────────────────────────────────────


def sync(source: str | Path, dest: str | Path) -> Syncer:
    """Create a new Syncer."""
    return Syncer(source, dest)
