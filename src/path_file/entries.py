"""Core data classes for path_file: Entry, ActionResult, Report, SyncDiff, SyncResult."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import (
    IO,
    Any,
)

from path_file.units import human_ago, human_size

# ──────────────────────────────────────────────────────────────────────────────
# ENTRY
# ──────────────────────────────────────────────────────────────────────────────


class Entry:
    """
    Represents a filesystem entry with rich metadata.

    This is the core data object used throughout path_file. It wraps a path
    and its os.stat_result, providing lazy-loaded properties and helper methods.
    """

    __slots__ = (
        "_content_bytes",
        "_content_text",
        "_hash_sha256",
        "_path",
        "_rule_action",
        "_rule_dest",
        "_rule_params",
        "_stat",
    )

    def __init__(self, path: str | Path, stat_result: os.stat_result | None = None) -> None:
        _p = Path(path)
        # Resolve for a canonical absolute path, but keep symlink identity
        # (resolve() would replace a symlink with its target).
        try:
            self._path = Path(os.path.abspath(_p)) if _p.is_symlink() else _p.resolve()
        except (OSError, ValueError):
            self._path = _p
        self._stat = stat_result or self._path.stat()
        self._hash_sha256: str | None = None
        self._content_text: str | None = None
        self._content_bytes: bytes | None = None
        self._rule_action: str | None = None
        self._rule_dest: str | None = None
        self._rule_params: dict[str, Any] | None = None

    @classmethod
    def from_path(cls, path: str | Path) -> Entry:
        """Create Entry from path, resolving and getting stat."""
        p = Path(os.path.abspath(path)) if Path(path).is_symlink() else Path(path).resolve()
        return cls(p, p.stat())

    @classmethod
    def from_stat(cls, path: Path, stat: os.stat_result) -> Entry:
        """Create Entry from pre-resolved path and stat result (faster)."""
        return cls(path, stat)

    # ─── Properties ───────────────────────────────────────────────────────────

    @property
    def path(self) -> Path:
        """Resolved absolute path."""
        return self._path

    @property
    def name(self) -> str:
        """File/directory name."""
        return self._path.name

    @property
    def stem(self) -> str:
        """File name without last suffix."""
        return self._path.stem

    @property
    def suffix(self) -> str:
        """Last file suffix (e.g., '.txt')."""
        return self._path.suffix

    @property
    def extensions(self) -> list[str]:
        """All suffixes (e.g., ['.tar', '.gz'] for 'file.tar.gz')."""
        return self._path.suffixes

    @property
    def size(self) -> int:
        """File size in bytes."""
        return self._stat.st_size

    @property
    def size_human(self) -> str:
        """Human-readable file size."""
        return human_size(self.size)

    @property
    def created(self) -> datetime:
        """Creation time (platform-dependent)."""
        return datetime.fromtimestamp(self._stat.st_ctime)

    @property
    def modified(self) -> datetime:
        """Last modification time."""
        return datetime.fromtimestamp(self._stat.st_mtime)

    @property
    def accessed(self) -> datetime:
        """Last access time."""
        return datetime.fromtimestamp(self._stat.st_atime)

    @property
    def modified_ago(self) -> str:
        """Human-readable time since modification."""
        return human_ago(self.modified)

    @property
    def created_ago(self) -> str:
        """Human-readable time since creation."""
        return human_ago(self.created)

    @property
    def is_file(self) -> bool:
        """True if regular file (or a symlink pointing to a regular file)."""
        fmt = self._stat.st_mode & 0o170000
        if fmt == 0o100000:
            return True
        if fmt == 0o120000:
            # Symlink: consider it a file when its target is a regular file
            try:
                target_mode = self._path.stat().st_mode & 0o170000
            except (OSError, ValueError):
                return False
            return target_mode == 0o100000
        return False

    @property
    def is_dir(self) -> bool:
        """True if directory."""
        return self._stat.st_mode & 0o170000 == 0o040000

    @property
    def is_symlink(self) -> bool:
        """True if symbolic link."""
        return self._stat.st_mode & 0o170000 == 0o120000

    @property
    def is_hidden(self) -> bool:
        """True if hidden (starts with dot or has hidden attribute on Windows)."""
        if self.name.startswith("."):
            return True
        try:
            return bool(self._stat.st_file_attributes & 0x2)  # Windows FILE_ATTRIBUTE_HIDDEN
        except AttributeError:
            return False

    @property
    def is_empty(self) -> bool:
        """True if file is empty (size 0) or directory has no entries."""
        if self.is_file:
            return self.size == 0
        if self.is_dir:
            try:
                return not any(self._path.iterdir())
            except (PermissionError, OSError):
                return False
        return True

    @property
    def hash_sha256(self) -> str:
        """SHA-256 hash of file content (lazy, cached)."""
        if self._hash_sha256 is None:
            if not self.is_file:
                self._hash_sha256 = ""
            else:
                h = hashlib.sha256()
                with self._path.open("rb") as f:
                    for chunk in iter(lambda: f.read(65536), b""):
                        h.update(chunk)
                self._hash_sha256 = h.hexdigest()
        return self._hash_sha256

    # ─── Content Reading ──────────────────────────────────────────────────────

    def read_text(self, encoding: str = "utf-8") -> str:
        """Read file as text (lazy, cached)."""
        if self._content_text is None:
            if not self.is_file:
                self._content_text = ""
            else:
                try:
                    self._content_text = self._path.read_text(encoding=encoding)
                except UnicodeDecodeError:
                    # Fallback to latin-1 which never fails
                    self._content_text = self._path.read_text(encoding="latin-1")
        return self._content_text

    def read_bytes(self) -> bytes:
        """Read file as bytes (lazy, cached)."""
        if self._content_bytes is None:
            if not self.is_file:
                self._content_bytes = b""
            else:
                self._content_bytes = self._path.read_bytes()
        return self._content_bytes

    def open(self, mode: str = "r", **kwargs: Any) -> IO[Any]:
        """Open file with given mode."""
        return self._path.open(mode, **kwargs)

    # ─── Path Operations ──────────────────────────────────────────────────────

    def relative_to(self, base: str | Path) -> Path:
        """Return path relative to base."""
        return self._path.relative_to(Path(base).resolve())

    def as_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "path": str(self._path),
            "name": self.name,
            "stem": self.stem,
            "suffix": self.suffix,
            "extensions": self.extensions,
            "size": self.size,
            "size_human": self.size_human,
            "created": self.created.isoformat(),
            "modified": self.modified.isoformat(),
            "accessed": self.accessed.isoformat(),
            "is_file": self.is_file,
            "is_dir": self.is_dir,
            "is_symlink": self.is_symlink,
            "is_hidden": self.is_hidden,
            "is_empty": self.is_empty,
            "hash_sha256": self.hash_sha256 if self.is_file else None,
        }

    # ─── Dunder Methods ───────────────────────────────────────────────────────

    def __str__(self) -> str:
        return str(self._path)

    def __repr__(self) -> str:
        type_char = "f" if self.is_file else "d" if self.is_dir else "l"
        return f"<Entry {type_char} {self._path} ({self.size_human})>"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entry):
            return NotImplemented
        return self._path == other._path

    def __hash__(self) -> int:
        return hash(self._path)

    def __lt__(self, other: Entry) -> bool:
        if not isinstance(other, Entry):
            return NotImplemented
        return str(self._path) < str(other._path)

    def __fspath__(self) -> str:
        return str(self._path)


# ──────────────────────────────────────────────────────────────────────────────
# ACTION RESULT
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class ActionResult:
    """Result of an action execution (copy, move, delete, etc.)."""

    action: str
    count: int = 0
    total_size: int = 0
    duration: float = 0.0
    errors: list[tuple[Path, Exception]] = field(default_factory=list)
    skipped: int = 0
    dry_run: bool = False

    def success(self) -> bool:
        """True if no errors occurred."""
        return len(self.errors) == 0

    def summary(self) -> str:
        """Human-readable summary."""
        status = "DRY RUN" if self.dry_run else "COMPLETED"
        error_info = f", {len(self.errors)} errors" if self.errors else ""
        skip_info = f", {self.skipped} skipped" if self.skipped else ""
        return (
            f"{self.action.upper()} {status}: {self.count} file(s), "
            f"{human_size(self.total_size)} in {self.duration:.2f}s"
            f"{error_info}{skip_info}"
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "action": self.action,
            "count": self.count,
            "total_size": self.total_size,
            "total_size_human": human_size(self.total_size),
            "duration": self.duration,
            "errors": [{"path": str(p), "error": str(e)} for p, e in self.errors],
            "skipped": self.skipped,
            "dry_run": self.dry_run,
            "success": self.success(),
        }


# ──────────────────────────────────────────────────────────────────────────────
# REPORT
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class Report:
    """Aggregated report of a file collection."""

    chain_size: int = 0
    total_size: int = 0
    by_extension: dict[str, int] = field(default_factory=dict)
    by_size_bucket: dict[str, int] = field(default_factory=dict)
    largest: Entry | None = None
    smallest: Entry | None = None
    oldest: Entry | None = None
    newest: Entry | None = None
    file_count: int = 0
    dir_count: int = 0
    symlink_count: int = 0
    hidden_count: int = 0
    empty_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "chain_size": self.chain_size,
            "total_size": self.total_size,
            "total_size_human": human_size(self.total_size),
            "by_extension": self.by_extension,
            "by_size_bucket": self.by_size_bucket,
            "largest": self.largest.as_dict() if self.largest else None,
            "smallest": self.smallest.as_dict() if self.smallest else None,
            "oldest": self.oldest.as_dict() if self.oldest else None,
            "newest": self.newest.as_dict() if self.newest else None,
            "file_count": self.file_count,
            "dir_count": self.dir_count,
            "symlink_count": self.symlink_count,
            "hidden_count": self.hidden_count,
            "empty_count": self.empty_count,
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def to_csv(self) -> str:
        """Convert to CSV string (extension breakdown)."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Extension", "Count", "Size", "Size Human"])
        for ext, count in sorted(self.by_extension.items(), key=lambda x: -x[1]):
            writer.writerow([ext, count, "", human_size(count)])  # size per ext not tracked
        return output.getvalue()

    def to_table(self) -> str:
        """Pretty ASCII table."""
        lines = []
        lines.append("┌────────────────────────────────────────────────────────────┐")
        lines.append("│                      PATHFLOW REPORT                       │")
        lines.append("├────────────────────────────────────────────────────────────┤")
        lines.append(
            f"│ Files: {self.file_count:<5}  Dirs: {self.dir_count:<5}  "
            f"Symlinks: {self.symlink_count:<5}  Hidden: {self.hidden_count:<5}  "
            f"Empty: {self.empty_count:<5} │"
        )
        lines.append(
            f"│ Total Entries: {self.chain_size:<5}  Total Size: "
            f"{human_size(self.total_size):>10}                │"
        )
        lines.append("├──────────────────┬──────────┬──────────────────────────────┤")
        lines.append("│ Extension        │ Count    │ Size                         │")
        lines.append("├──────────────────┼──────────┼──────────────────────────────┤")

        for ext, count in sorted(self.by_extension.items(), key=lambda x: -x[1]):
            ext_display = ext if ext else "(no extension)"
            lines.append(f"│ {ext_display:<16} │ {count:>8} │ {human_size(count):>28} │")

        lines.append("└──────────────────┴──────────┴──────────────────────────────┘")

        if self.largest:
            lines.append(f"\nLargest: {self.largest} ({self.largest.size_human})")
        if self.smallest and self.smallest.size > 0:
            lines.append(f"Smallest: {self.smallest} ({self.smallest.size_human})")
        if self.newest:
            lines.append(f"Newest: {self.newest} (modified {self.newest.modified_ago})")
        if self.oldest:
            lines.append(f"Oldest: {self.oldest} (modified {self.oldest.modified_ago})")

        return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# SYNC DIFF & RESULT
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class SyncDiff:
    """Difference between source and destination for sync operations."""

    to_add: list[Path] = field(default_factory=list)
    to_update: list[Path] = field(default_factory=list)
    to_delete: list[Path] = field(default_factory=list)
    conflicts: list[tuple[Path, Path]] = field(default_factory=list)
    unchanged: list[Path] = field(default_factory=list)

    def summary(self) -> str:
        """Human-readable summary."""
        parts = []
        if self.to_add:
            parts.append(f"+{len(self.to_add)} new")
        if self.to_update:
            parts.append(f"~{len(self.to_update)} modified")
        if self.to_delete:
            parts.append(f"-{len(self.to_delete)} to delete")
        if self.conflicts:
            parts.append(f"!{len(self.conflicts)} conflicts")
        if not parts:
            return "Already in sync"
        return ", ".join(parts)

    def has_changes(self) -> bool:
        """True if any changes needed."""
        return bool(self.to_add or self.to_update or self.to_delete or self.conflicts)


@dataclass
class SyncResult(ActionResult):
    """Result of a sync operation."""

    diff: SyncDiff | None = None

    def summary(self) -> str:
        base = super().summary()
        if self.diff:
            return f"{base} | {self.diff.summary()}"
        return base
