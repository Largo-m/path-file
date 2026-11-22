"""FileChain - immutable, lazy, chainable file collection."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Callable, Iterator, Sequence
from datetime import datetime
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
)

from path_file._internal._iterators import WalkConfig, walk
from path_file._internal._log import get_logger, log_debug
from path_file.entries import ActionResult, Entry, Report
from path_file.exceptions import PathflowError
from path_file.filters import FilterFunc

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


def _dedupe_entries(entries: list[Entry]) -> list[Entry]:
    """Keep the first occurrence of each resolved path (stateless, repeatable)."""
    seen: set[str] = set()
    unique: list[Entry] = []
    for entry in entries:
        try:
            key = str(entry.path.resolve())
        except OSError:
            key = str(entry.path)
        if key not in seen:
            seen.add(key)
            unique.append(entry)
    return unique


# ──────────────────────────────────────────────────────────────────────────────
# FILE CHAIN
# ──────────────────────────────────────────────────────────────────────────────


class FileChain:
    """
    Immutable, lazy, chainable file collection.

    All filter methods return NEW FileChain instances.
    All action methods trigger materialization + execution.

    Example:
        pf.find("~/Downloads")
            .files()
            .with_extension(".jpg")
            .larger_than("2MB")
            .copy_to("~/Pictures/Large")
    """

    __slots__ = (
        "_action_name",
        "_action_params",
        "_dry_run",
        "_filters",
        "_follow_symlinks",
        "_limit",
        "_max_depth",
        "_min_depth",
        "_on_error",
        "_parallel",
        "_progress",
        "_recursive",
        "_skip",
        "_sort_desc",
        "_sort_key",
        "_source",
        "_verbose",
    )

    if TYPE_CHECKING:
        # Signatures of the action methods attached dynamically by
        # ``_add_action_methods()`` (declared here for type checkers).
        def copy_to(self, *args: Any, **kwargs: Any) -> FileChain: ...
        def move_to(self, *args: Any, **kwargs: Any) -> FileChain: ...
        def delete(self, *args: Any, **kwargs: Any) -> FileChain: ...
        def trash(self, *args: Any, **kwargs: Any) -> FileChain: ...
        def rename(self, *args: Any, **kwargs: Any) -> FileChain: ...
        def rename_with(self, *args: Any, **kwargs: Any) -> FileChain: ...
        def archive_to(self, *args: Any, **kwargs: Any) -> FileChain: ...
        def compress(self, *args: Any, **kwargs: Any) -> FileChain: ...
        def extract_to(self, *args: Any, **kwargs: Any) -> FileChain: ...
        def chmod(self, *args: Any, **kwargs: Any) -> FileChain: ...
        def touch(self, *args: Any, **kwargs: Any) -> FileChain: ...
        def read_text(self, *args: Any, **kwargs: Any) -> FileChain: ...
        def read_bytes(self, *args: Any, **kwargs: Any) -> FileChain: ...
        def write_text(self, *args: Any, **kwargs: Any) -> FileChain: ...
        def write_bytes(self, *args: Any, **kwargs: Any) -> FileChain: ...
        def hash(self, *args: Any, **kwargs: Any) -> FileChain: ...
        def open(self, *args: Any, **kwargs: Any) -> FileChain: ...
        def create_dir(self, *args: Any, **kwargs: Any) -> FileChain: ...
        def symlink_to(self, *args: Any, **kwargs: Any) -> FileChain: ...

    def __init__(
        self,
        source: str | Path | Sequence[str | Path] | Iterator[Entry],
        filters: list[FilterFunc] | None = None,
        sort_key: str | None = None,
        sort_desc: bool = False,
        limit: int | None = None,
        skip: int = 0,
        parallel: int = 1,
        progress: bool = False,
        dry_run: bool | None = None,
        on_error: str = "raise",
        verbose: bool = False,
        recursive: bool = True,
        follow_symlinks: bool = False,
        max_depth: int | None = None,
        min_depth: int = 0,
        action_name: str | None = None,
        action_params: dict | None = None,
    ) -> None:
        self._source = source
        self._filters = filters or []
        self._sort_key = sort_key
        self._sort_desc = sort_desc
        self._limit = limit
        self._skip = skip
        self._parallel = max(1, parallel)
        self._progress = progress
        self._dry_run = dry_run
        self._on_error = on_error  # "raise", "skip", "collect"
        self._verbose = verbose
        self._recursive = recursive
        self._follow_symlinks = follow_symlinks
        self._max_depth = max_depth
        self._min_depth = min_depth
        self._action_name = action_name
        self._action_params = action_params or {}

    # ─── Factory Methods ──────────────────────────────────────────────────────

    @classmethod
    def from_paths(cls, paths: Sequence[str | Path]) -> FileChain:
        """Create chain from explicit list of paths."""
        entries = [Entry.from_path(p) for p in paths]
        return cls(entries, filters=[])

    @classmethod
    def from_entries(cls, entries: Sequence[Entry]) -> FileChain:
        """Create chain from Entry objects."""
        return cls(list(entries), filters=[])

    # ─── Internal Helpers ─────────────────────────────────────────────────────

    def _with_filter(self, filter_func: FilterFunc) -> FileChain:
        """Return new chain with additional filter."""
        return FileChain(
            self._source,
            filters=self._filters + [filter_func],
            sort_key=self._sort_key,
            sort_desc=self._sort_desc,
            limit=self._limit,
            skip=self._skip,
            parallel=self._parallel,
            progress=self._progress,
            dry_run=self._dry_run,
            on_error=self._on_error,
            verbose=self._verbose,
            recursive=self._recursive,
            follow_symlinks=self._follow_symlinks,
            max_depth=self._max_depth,
            min_depth=self._min_depth,
            action_name=self._action_name,
            action_params=self._action_params,
        )

    def _with_config(self, **kwargs: Any) -> FileChain:
        """Return new chain with modified configuration."""
        return FileChain(
            self._source,
            filters=self._filters,
            sort_key=kwargs.get("sort_key", self._sort_key),
            sort_desc=kwargs.get("sort_desc", self._sort_desc),
            limit=kwargs.get("limit", self._limit),
            skip=kwargs.get("skip", self._skip),
            parallel=kwargs.get("parallel", self._parallel),
            progress=kwargs.get("progress", self._progress),
            dry_run=self._dry_run if kwargs.get("dry_run") is None else kwargs.get("dry_run"),
            on_error=kwargs.get("on_error", self._on_error),
            verbose=kwargs.get("verbose", self._verbose),
            recursive=kwargs.get("recursive", self._recursive),
            follow_symlinks=kwargs.get("follow_symlinks", self._follow_symlinks),
            max_depth=kwargs.get("max_depth", self._max_depth),
            min_depth=kwargs.get("min_depth", self._min_depth),
            action_name=kwargs.get("action_name", self._action_name),
            action_params=kwargs.get("action_params", self._action_params),
        )

    def _iter(self) -> Iterator[Entry]:
        """Internal: yields filtered entries (lazy)."""
        for entry in self._materialize_iter():
            yield entry

    def _materialize_iter(self) -> Iterator[Entry]:
        """Internal: iterate over filtered entries without collecting all."""
        # Get raw entries
        if isinstance(self._source, (str, Path)):
            # Walk directory
            config = WalkConfig(
                follow_symlinks=self._follow_symlinks,
                max_depth=self._max_depth,
                min_depth=self._min_depth,
            )
            raw_entries = walk(self._source, config=config)
        elif isinstance(self._source, Iterator):
            raw_entries = self._source
        else:
            # Assume sequence of paths or entries
            raw_entries = []
            for item in self._source:
                if isinstance(item, Entry):
                    raw_entries.append(item)
                else:
                    raw_entries.append(Entry.from_path(item))

        # Apply filters
        for entry in raw_entries:
            try:
                if all(f(entry) for f in self._filters):
                    yield entry
            except Exception as e:
                if self._on_error == "raise":
                    raise
                elif self._on_error == "collect":
                    log_debug(f"Filter error on {entry}: {e}")
                    continue
                else:  # skip
                    continue

    def _materialize(self) -> list[Entry]:
        """Internal: builds full list with sort/limit applied."""
        entries = list(self._materialize_iter())

        # Drop same-path duplicates when .deduplicate() was requested
        if any(getattr(f, "_needs_dedup", False) for f in self._filters):
            entries = _dedupe_entries(entries)

        # Sort
        if self._sort_key:
            entries = self._sort_entries(entries)

        # Skip and limit
        if self._skip:
            entries = entries[self._skip :]
        if self._limit is not None:
            entries = entries[: self._limit]

        return entries

    def _sort_entries(self, entries: list[Entry]) -> list[Entry]:
        """Sort entries by key."""
        key_func = self._get_sort_key_func()
        reverse = self._sort_desc
        return sorted(entries, key=key_func, reverse=reverse)

    def _get_sort_key_func(self) -> Callable[[Entry], Any]:
        """Get sort key function."""
        key = self._sort_key
        if key == "name":
            return lambda e: e.name.lower()
        elif key == "size":
            return lambda e: e.size
        elif key == "date" or key == "modified":
            return lambda e: e.modified
        elif key == "created":
            return lambda e: e.created
        elif key == "path":
            return lambda e: str(e.path).lower()
        elif key == "extension":
            return lambda e: e.suffix.lower()
        else:
            return lambda e: str(e.path).lower()

    # ─── Filter Methods (MODULE 1) ────────────────────────────────────────────

    def files(self) -> FileChain:
        """Only regular files."""
        from path_file.filters import filter_files

        return self._with_filter(filter_files())

    def dirs(self) -> FileChain:
        """Only directories."""
        from path_file.filters import filter_dirs

        return self._with_filter(filter_dirs())

    def symlinks(self) -> FileChain:
        """Only symbolic links."""
        from path_file.filters import filter_symlinks

        return self._with_filter(filter_symlinks())

    def all(self) -> FileChain:
        """All entries (reset type filter)."""
        from path_file.filters import filter_all

        return self._with_filter(filter_all())

    def with_extension(self, ext: str) -> FileChain:
        """Files with specific extension."""
        from path_file.filters import filter_extension

        return self._with_filter(filter_extension(ext))

    def with_extensions(self, *exts: str) -> FileChain:
        """Files with any of the given extensions."""
        from path_file.filters import filter_extensions

        return self._with_filter(filter_extensions(*exts))

    def without_extension(self, ext: str) -> FileChain:
        """Files NOT having the given extension."""
        from path_file.filters import filter_without_extension

        return self._with_filter(filter_without_extension(ext))

    def larger_than(self, size: str | int) -> FileChain:
        """Files larger than given size."""
        from path_file.filters import filter_larger_than

        return self._with_filter(filter_larger_than(size))

    def smaller_than(self, size: str | int) -> FileChain:
        """Files smaller than given size."""
        from path_file.filters import filter_smaller_than

        return self._with_filter(filter_smaller_than(size))

    def between_sizes(self, min_size: str | int, max_size: str | int) -> FileChain:
        """Files with size between min and max."""
        from path_file.filters import filter_between_sizes

        return self._with_filter(filter_between_sizes(min_size, max_size))

    def newer_than(self, duration: str | int) -> FileChain:
        """Modified more recently than duration ago."""
        from path_file.filters import filter_newer_than

        return self._with_filter(filter_newer_than(duration))

    def older_than(self, duration: str | int) -> FileChain:
        """Modified longer ago than duration."""
        from path_file.filters import filter_older_than

        return self._with_filter(filter_older_than(duration))

    def created_newer_than(self, duration: str | int) -> FileChain:
        """Created more recently than duration ago."""
        from path_file.filters import filter_created_newer_than

        return self._with_filter(filter_created_newer_than(duration))

    def created_older_than(self, duration: str | int) -> FileChain:
        """Created longer ago than duration."""
        from path_file.filters import filter_created_older_than

        return self._with_filter(filter_created_older_than(duration))

    def modified_between(self, start: str | datetime, end: str | datetime) -> FileChain:
        """Modified between start and end."""
        from path_file.filters import filter_modified_between

        return self._with_filter(filter_modified_between(start, end))

    def created_between(self, start: str | datetime, end: str | datetime) -> FileChain:
        """Created between start and end."""
        from path_file.filters import filter_created_between

        return self._with_filter(filter_created_between(start, end))

    def modified_today(self) -> FileChain:
        """Modified today."""
        from path_file.filters import filter_modified_today

        return self._with_filter(filter_modified_today())

    def modified_this_week(self) -> FileChain:
        """Modified this week."""
        from path_file.filters import filter_modified_this_week

        return self._with_filter(filter_modified_this_week())

    def modified_this_month(self) -> FileChain:
        """Modified this month."""
        from path_file.filters import filter_modified_this_month

        return self._with_filter(filter_modified_this_month())

    def created_today(self) -> FileChain:
        """Created today."""
        from path_file.filters import filter_created_today

        return self._with_filter(filter_created_today())

    def created_this_week(self) -> FileChain:
        """Created this week."""
        from path_file.filters import filter_created_this_week

        return self._with_filter(filter_created_this_week())

    def name_matches(self, pattern: str) -> FileChain:
        """Name matches regex pattern."""
        from path_file.filters import filter_name_matches

        return self._with_filter(filter_name_matches(pattern))

    def name_contains(self, text: str, case_sensitive: bool = False) -> FileChain:
        """Name contains text."""
        from path_file.filters import filter_name_contains

        return self._with_filter(filter_name_contains(text, case_sensitive))

    def name_starts_with(self, prefix: str, case_sensitive: bool = False) -> FileChain:
        """Name starts with prefix."""
        from path_file.filters import filter_name_starts_with

        return self._with_filter(filter_name_starts_with(prefix, case_sensitive))

    def name_ends_with(self, suffix: str, case_sensitive: bool = False) -> FileChain:
        """Name ends with suffix."""
        from path_file.filters import filter_name_ends_with

        return self._with_filter(filter_name_ends_with(suffix, case_sensitive))

    def path_contains(self, text: str, case_sensitive: bool = False) -> FileChain:
        """Full path contains text."""
        from path_file.filters import filter_path_contains

        return self._with_filter(filter_path_contains(text, case_sensitive))

    def path_matches(self, pattern: str) -> FileChain:
        """Full path matches regex pattern."""
        from path_file.filters import filter_path_matches

        return self._with_filter(filter_path_matches(pattern))

    def in_folder(self, folder: str | Path) -> FileChain:
        """Entry is inside given folder."""
        from path_file.filters import filter_in_folder

        return self._with_filter(filter_in_folder(folder))

    def not_in_folder(self, folder: str | Path) -> FileChain:
        """Entry is NOT inside given folder."""
        from path_file.filters import filter_not_in_folder

        return self._with_filter(filter_not_in_folder(folder))

    def empty(self) -> FileChain:
        """Empty files or directories."""
        from path_file.filters import filter_empty

        return self._with_filter(filter_empty())

    def not_empty(self) -> FileChain:
        """Non-empty files or directories."""
        from path_file.filters import filter_not_empty

        return self._with_filter(filter_not_empty())

    def hidden(self) -> FileChain:
        """Hidden entries."""
        from path_file.filters import filter_hidden

        return self._with_filter(filter_hidden())

    def visible(self) -> FileChain:
        """Visible (non-hidden) entries."""
        from path_file.filters import filter_visible

        return self._with_filter(filter_visible())

    def readable(self) -> FileChain:
        """Readable entries."""
        from path_file.filters import filter_readable

        return self._with_filter(filter_readable())

    def writable(self) -> FileChain:
        """Writable entries."""
        from path_file.filters import filter_writable

        return self._with_filter(filter_writable())

    def executable(self) -> FileChain:
        """Executable entries."""
        from path_file.filters import filter_executable

        return self._with_filter(filter_executable())

    def matching_content(self, text: str, encoding: str = "utf-8") -> FileChain:
        """Text file contains given text."""
        from path_file.filters import filter_matching_content

        return self._with_filter(filter_matching_content(text, encoding))

    def matching_regex_in_content(self, pattern: str, encoding: str = "utf-8") -> FileChain:
        """Text file content matches regex."""
        from path_file.filters import filter_matching_regex_in_content

        return self._with_filter(filter_matching_regex_in_content(pattern, encoding))

    def containing_line(self, text: str, encoding: str = "utf-8") -> FileChain:
        """Text file contains a line with given text."""
        from path_file.filters import filter_containing_line

        return self._with_filter(filter_containing_line(text, encoding))

    def containing_lines(self, *texts: str, encoding: str = "utf-8") -> FileChain:
        """Text file contains ALL of the given lines."""
        from path_file.filters import filter_containing_lines

        return self._with_filter(filter_containing_lines(*texts, encoding=encoding))

    def duplicates_by_hash(self, algorithm: str = "sha256") -> Dict[str, list[Entry]]:
        """
        Find groups of duplicate entries by content hash.

        Returns:
            Dict mapping hash -> list of Entries (only groups with 2+ files)
        """
        from path_file.hash import find_duplicates

        return find_duplicates(self.to_list(), algorithm)

    def unique_by_hash(self) -> FileChain:
        """Entries with unique content (no duplicates)."""
        from path_file.filters import filter_unique_by_hash

        return self._with_filter(filter_unique_by_hash())

    def duplicates_by_name(self) -> Dict[str, list[Entry]]:
        """
        Find groups of duplicate entries by file name.

        Returns:
            Dict mapping name -> list of Entries (only groups with 2+ files)
        """
        from path_file.hash import find_duplicates_by_name

        return find_duplicates_by_name(self.to_list())

    def unique_by_name(self) -> FileChain:
        """Entries with unique names."""
        from path_file.filters import filter_unique_by_name

        return self._with_filter(filter_unique_by_name())

    def same_size_as(self, path: str | Path) -> FileChain:
        """Entries with same size as reference file."""
        from path_file.filters import filter_same_size_as

        return self._with_filter(filter_same_size_as(path))

    def same_content_as(self, path: str | Path) -> FileChain:
        """Entries with same content as reference file."""
        from path_file.filters import filter_same_content_as

        return self._with_filter(filter_same_content_as(path))

    def sort_by(self, key: str, desc: bool = False) -> FileChain:
        """Sort by key: name, size, date, created, path, extension."""
        valid_keys = {"name", "size", "date", "modified", "created", "path", "extension"}
        if key not in valid_keys:
            raise ValueError(f"Invalid sort key: {key}. Valid: {valid_keys}")
        return self._with_config(sort_key=key, sort_desc=desc)

    def reverse(self) -> FileChain:
        """Reverse current sort order."""
        return self._with_config(sort_desc=not self._sort_desc)

    def limit(self, n: int) -> FileChain:
        """Limit to first n entries."""
        return self._with_config(limit=n)

    def skip(self, n: int) -> FileChain:
        """Skip first n entries."""
        return self._with_config(skip=n)

    def slice(self, start: int, stop: int | None = None) -> FileChain:
        """Slice entries (like list slicing)."""
        return self._with_config(skip=start, limit=stop - start if stop else None)

    def deduplicate(self) -> FileChain:
        """Remove duplicate entries by resolved path (keeps first occurrence)."""

        def _dedup_filter(entry: Entry) -> bool:
            return True  # marker only; real dedup happens in _materialize()

        _dedup_filter._needs_dedup = True
        return self._with_filter(_dedup_filter)

    # ─── Execution Modifiers (MODULE 3) ───────────────────────────────────────

    def dry_run(self, enabled: bool = True) -> FileChain:
        """Mark chain as dry-run (no actual changes)."""
        return self._with_config(dry_run=enabled)

    def parallel(self, workers: int = 8) -> FileChain:
        """Enable parallel execution with given worker count."""
        return self._with_config(parallel=max(1, workers))

    def progress(self, enabled: bool = True) -> FileChain:
        """Show progress bar during execution."""
        return self._with_config(progress=enabled)

    def verbose(self, enabled: bool = True) -> FileChain:
        """Enable verbose output."""
        return self._with_config(verbose=enabled)

    def quiet(self, enabled: bool = True) -> FileChain:
        """Suppress output."""
        return self._with_config(verbose=not enabled)

    def on_error(self, action: str) -> FileChain:
        """Set error handling: 'raise', 'skip', or 'collect'."""
        if action not in ("raise", "skip", "collect"):
            raise ValueError("on_error must be 'raise', 'skip', or 'collect'")
        return self._with_config(on_error=action)

    def recursive(self, enabled: bool = True) -> FileChain:
        """Enable/disable recursive directory traversal."""
        return self._with_config(recursive=enabled)

    def follow_symlinks(self, enabled: bool = True) -> FileChain:
        """Follow symbolic links to directories."""
        return self._with_config(follow_symlinks=enabled)

    def max_depth(self, depth: int) -> FileChain:
        """Maximum recursion depth."""
        return self._with_config(max_depth=depth)

    def min_depth(self, depth: int) -> FileChain:
        """Minimum depth before yielding entries."""
        return self._with_config(min_depth=depth)

    # ─── Materialization Methods (MODULE 3) ───────────────────────────────────

    def count(self) -> int:
        """Count matching entries."""
        return len(self._materialize())

    def first(self) -> Entry | None:
        """Get first matching entry."""
        entries = self._materialize()
        return entries[0] if entries else None

    def last(self) -> Entry | None:
        """Get last matching entry."""
        entries = self._materialize()
        return entries[-1] if entries else None

    def to_list(self) -> list[Entry]:
        """Get all matching entries as list."""
        return self._materialize()

    def to_paths(self) -> list[Path]:
        """Get all matching paths."""
        return [e.path for e in self._materialize()]

    def to_dict(self) -> list[dict]:
        """Get all entries as list of dicts."""
        return [e.as_dict() for e in self._materialize()]

    def to_json(self, path: str | Path | None = None, indent: int = 2) -> str:
        """Serialize to JSON string (optionally write to file)."""
        data = self.to_dict()
        json_str = json.dumps(data, indent=indent, ensure_ascii=False, default=str)
        if path:
            Path(path).write_text(json_str, encoding="utf-8")
        return json_str

    def to_csv(self, path: str | Path | None = None) -> str:
        """Serialize to CSV string (optionally write to file)."""
        entries = self._materialize()
        if not entries:
            csv_str = "path,name,size,modified\n"
        else:
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(
                [
                    "path",
                    "name",
                    "stem",
                    "suffix",
                    "size",
                    "size_human",
                    "modified",
                    "created",
                    "is_file",
                    "is_dir",
                ]
            )
            for e in entries:
                writer.writerow(
                    [
                        str(e.path),
                        e.name,
                        e.stem,
                        e.suffix,
                        e.size,
                        e.size_human,
                        e.modified.isoformat(),
                        e.created.isoformat(),
                        e.is_file,
                        e.is_dir,
                    ]
                )
            csv_str = output.getvalue()
        if path:
            Path(path).write_text(csv_str, encoding="utf-8")
        return csv_str

    def to_table(self) -> str:
        """Pretty ASCII table of entries."""
        entries = self._materialize()
        if not entries:
            return "No entries found."

        lines = []
        lines.append("┌──────────────────────────────┬──────────┬──────────┬────────────────────┐")
        lines.append("│ Name                         │ Size     │ Type     │ Modified           │")
        lines.append("├──────────────────────────────┼──────────┼──────────┼────────────────────┤")

        for e in entries:
            name = e.name[:28] + ".." if len(e.name) > 30 else e.name
            size = e.size_human if e.is_file else "-"
            typ = "FILE" if e.is_file else "DIR" if e.is_dir else "LINK"
            mod = e.modified.strftime("%Y-%m-%d %H:%M")
            lines.append(f"│ {name:<30} │ {size:>8} │ {typ:<8} │ {mod} │")

        lines.append("└──────────────────────────────┴──────────┴──────────┴────────────────────┘")
        lines.append(f"Total: {len(entries)} entries")
        return "\n".join(lines)

    def report(self) -> Report:
        """Generate aggregate report."""
        entries = self._materialize()
        return self._build_report(entries)

    def preview(self) -> str:
        """Dry-run preview of pending action."""
        if not self._action_name:
            return "No action pending. Use copy_to(), move_to(), delete(), etc."
        entries = self._materialize()
        if not entries:
            return f"No files to {self._action_name}."

        lines = [f"DRY RUN: {self._action_name.upper()} {len(entries)} file(s)"]
        for e in entries[:20]:
            lines.append(f"  {e.path} ({e.size_human})")
        if len(entries) > 20:
            lines.append(f"  ... and {len(entries) - 20} more")
        return "\n".join(lines)

    def for_each(self, callback: Callable[[Entry], Any]) -> FileChain:
        """Call callback for each entry (side effects)."""
        for entry in self._materialize():
            try:
                callback(entry)
            except Exception as e:
                if self._on_error == "raise":
                    raise
                log_debug(f"Callback error on {entry}: {e}")
        return self

    def map(self, callback: Callable[[Entry], Any]) -> list[Any]:
        """Transform each entry."""
        return [callback(e) for e in self._materialize()]

    def reduce(self, func: Callable[[Any, Entry], Any], initial: Any) -> Any:
        """Fold entries with function."""
        result = initial
        for entry in self._materialize():
            result = func(result, entry)
        return result

    def execute(self) -> ActionResult:
        """Execute pending action."""
        if not self._action_name:
            raise PathflowError("No action to execute. Use copy_to(), move_to(), etc.")
        from path_file.actions import execute_action

        return execute_action(self)

    # ─── Iterator Protocol ────────────────────────────────────────────────────

    def __iter__(self) -> Iterator[Entry]:
        return self._iter()

    def __len__(self) -> int:
        return self.count()

    def __repr__(self) -> str:
        n = self.count()
        return f"<FileChain n={n}>"

    # ─── Internal Report Building ─────────────────────────────────────────────

    def _build_report(self, entries: list[Entry]) -> Report:
        """Build aggregate report from entries."""
        report = Report()
        report.chain_size = len(entries)

        if not entries:
            return report

        report.total_size = sum(e.size for e in entries)
        report.file_count = sum(1 for e in entries if e.is_file)
        report.dir_count = sum(1 for e in entries if e.is_dir)
        report.symlink_count = sum(1 for e in entries if e.is_symlink)
        report.hidden_count = sum(1 for e in entries if e.is_hidden)
        report.empty_count = sum(1 for e in entries if e.is_empty)

        # By extension
        for e in entries:
            ext = e.suffix or "(none)"
            report.by_extension[ext] = report.by_extension.get(ext, 0) + 1

        # Size buckets
        buckets = {
            "0 B": (0, 0),
            "1-10 KB": (1, 10 * 1024),
            "10-100 KB": (10 * 1024, 100 * 1024),
            "100 KB - 1 MB": (100 * 1024, 1024 * 1024),
            "1-10 MB": (1024 * 1024, 10 * 1024 * 1024),
            "10-100 MB": (10 * 1024 * 1024, 100 * 1024 * 1024),
            "100 MB - 1 GB": (100 * 1024 * 1024, 1024 * 1024 * 1024),
            "1-10 GB": (1024 * 1024 * 1024, 10 * 1024 * 1024 * 1024),
            "10 GB+": (10 * 1024 * 1024 * 1024, float("inf")),
        }
        for e in entries:
            for bucket, (min_s, max_s) in buckets.items():
                if min_s <= e.size <= max_s:
                    report.by_size_bucket[bucket] = report.by_size_bucket.get(bucket, 0) + 1
                    break

        # Extremes
        file_entries = [e for e in entries if e.is_file]
        if file_entries:
            report.largest = max(file_entries, key=lambda e: e.size)
            report.smallest = min(file_entries, key=lambda e: e.size)

        report.newest = max(entries, key=lambda e: e.modified)
        report.oldest = min(entries, key=lambda e: e.modified)

        return report


# ──────────────────────────────────────────────────────────────────────────────
# ACTION METHODS - These set up the action for later execution
# ──────────────────────────────────────────────────────────────────────────────


def _action_method(name: str):
    """Decorator to create action methods."""

    def decorator(func):
        def wrapper(self, *args, **kwargs):
            # Set action and params, return self for chaining
            chain = self._with_config(action_name=name, action_params=dict(kwargs))
            # Store args in action_params
            if args:
                chain._action_params["_args"] = args
            return chain

        wrapper.__name__ = name
        wrapper.__doc__ = func.__doc__
        return wrapper

    return decorator


# We'll add action methods to FileChain dynamically
# This avoids circular import with actions.py
def _add_action_methods():
    """Add action methods to FileChain class."""
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

    actions = {
        "copy_to": action_copy,
        "move_to": action_move,
        "delete": action_delete,
        "trash": action_trash,
        "rename": action_rename,
        "rename_with": action_rename_with,
        "archive_to": action_archive_to,
        "compress": action_compress,
        "extract_to": action_extract_to,
        "chmod": action_chmod,
        "touch": action_touch,
        "read_text": action_read_text,
        "read_bytes": action_read_bytes,
        "write_text": action_write_text,
        "write_bytes": action_write_bytes,
        "hash": action_hash,
        "open": action_open,
        "create_dir": action_create_dir,
        "symlink_to": action_symlink_to,
    }

    for name, func in actions.items():

        def make_method(action_name, action_func):
            def method(self, *args, **kwargs):
                # Extract dry_run from kwargs to pass to _with_config
                dry_run = kwargs.pop("dry_run", None)
                chain = self._with_config(
                    action_name=action_name,
                    action_params=kwargs,
                    dry_run=dry_run,
                )
                if args:
                    chain._action_params["_args"] = args
                return chain

            method.__name__ = action_name
            method.__doc__ = action_func.__doc__
            return method

        setattr(FileChain, name, make_method(name, func))


_add_action_methods()
