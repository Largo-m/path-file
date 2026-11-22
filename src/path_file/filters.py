"""Filter functions for FileChain - each returns a callable (Entry) -> bool."""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

from path_file._internal._parsers import _compile_regex, make_glob_filter
from path_file.entries import Entry
from path_file.units import parse_duration, parse_size

# ──────────────────────────────────────────────────────────────────────────────
# TYPE ALIASES
# ──────────────────────────────────────────────────────────────────────────────

FilterFunc = Callable[[Entry], bool]


# ──────────────────────────────────────────────────────────────────────────────
# BASIC TYPE FILTERS
# ──────────────────────────────────────────────────────────────────────────────


def filter_files() -> FilterFunc:
    """Filter: only regular files."""

    def _filter(entry: Entry) -> bool:
        return entry.is_file

    return _filter


def filter_dirs() -> FilterFunc:
    """Filter: only directories."""

    def _filter(entry: Entry) -> bool:
        return entry.is_dir

    return _filter


def filter_symlinks() -> FilterFunc:
    """Filter: only symbolic links."""

    def _filter(entry: Entry) -> bool:
        return entry.is_symlink

    return _filter


def filter_all() -> FilterFunc:
    """Filter: all entries (no-op)."""

    def _filter(entry: Entry) -> bool:
        return True

    return _filter


# ──────────────────────────────────────────────────────────────────────────────
# EXTENSION FILTERS
# ──────────────────────────────────────────────────────────────────────────────


def filter_extension(ext: str) -> FilterFunc:
    """Filter: files with specific extension (e.g., '.txt' or 'txt')."""
    ext = ext.lower()
    if not ext.startswith("."):
        ext = "." + ext

    def _filter(entry: Entry) -> bool:
        return entry.suffix.lower() == ext

    return _filter


def filter_extensions(*exts: str) -> FilterFunc:
    """Filter: files with any of the given extensions."""
    ext_set = {e.lower() if e.lower().startswith(".") else "." + e.lower() for e in exts}

    def _filter(entry: Entry) -> bool:
        return entry.suffix.lower() in ext_set

    return _filter


def filter_without_extension(ext: str) -> FilterFunc:
    """Filter: files NOT having the given extension."""
    ext = ext.lower()
    if not ext.startswith("."):
        ext = "." + ext

    def _filter(entry: Entry) -> bool:
        return entry.suffix.lower() != ext

    return _filter


# ──────────────────────────────────────────────────────────────────────────────
# SIZE FILTERS
# ──────────────────────────────────────────────────────────────────────────────


def filter_larger_than(size: str | int) -> FilterFunc:
    """Filter: files larger than given size."""
    size_bytes = parse_size(size)

    def _filter(entry: Entry) -> bool:
        return entry.is_file and entry.size > size_bytes

    return _filter


def filter_smaller_than(size: str | int) -> FilterFunc:
    """Filter: files smaller than given size."""
    size_bytes = parse_size(size)

    def _filter(entry: Entry) -> bool:
        return entry.is_file and entry.size < size_bytes

    return _filter


def filter_between_sizes(min_size: str | int, max_size: str | int) -> FilterFunc:
    """Filter: files with size between min and max (inclusive)."""
    min_bytes = parse_size(min_size)
    max_bytes = parse_size(max_size)

    if min_bytes > max_bytes:
        min_bytes, max_bytes = max_bytes, min_bytes

    def _filter(entry: Entry) -> bool:
        return entry.is_file and min_bytes <= entry.size <= max_bytes

    return _filter


def filter_empty() -> FilterFunc:
    """Filter: empty files or directories."""

    def _filter(entry: Entry) -> bool:
        return entry.is_empty

    return _filter


def filter_not_empty() -> FilterFunc:
    """Filter: non-empty files or directories."""

    def _filter(entry: Entry) -> bool:
        return not entry.is_empty

    return _filter


# ──────────────────────────────────────────────────────────────────────────────
# TIME FILTERS
# ──────────────────────────────────────────────────────────────────────────────


def _make_time_filter(
    get_time: Callable[[Entry], datetime],
    duration: str | timedelta,
    newer: bool = True,
) -> FilterFunc:
    """Create a time-based filter."""
    delta = parse_duration(duration)
    cutoff = datetime.now() - delta

    if newer:

        def _filter(entry: Entry) -> bool:
            return get_time(entry) > cutoff
    else:

        def _filter(entry: Entry) -> bool:
            return get_time(entry) < cutoff

    return _filter


def filter_newer_than(duration: str | timedelta) -> FilterFunc:
    """Filter: modified more recently than duration ago."""
    return _make_time_filter(lambda e: e.modified, duration, newer=True)


def filter_older_than(duration: str | timedelta) -> FilterFunc:
    """Filter: modified longer ago than duration."""
    return _make_time_filter(lambda e: e.modified, duration, newer=False)


def filter_created_newer_than(duration: str | timedelta) -> FilterFunc:
    """Filter: created more recently than duration ago."""
    return _make_time_filter(lambda e: e.created, duration, newer=True)


def filter_created_older_than(duration: str | timedelta) -> FilterFunc:
    """Filter: created longer ago than duration."""
    return _make_time_filter(lambda e: e.created, duration, newer=False)


def filter_modified_between(
    start: str | datetime,
    end: str | datetime,
) -> FilterFunc:
    """Filter: modified between start and end (inclusive)."""
    from path_file.units import parse_datetime

    start_dt = parse_datetime(start)
    end_dt = parse_datetime(end)

    if start_dt > end_dt:
        start_dt, end_dt = end_dt, start_dt

    def _filter(entry: Entry) -> bool:
        return start_dt <= entry.modified <= end_dt

    return _filter


def filter_created_between(
    start: str | datetime,
    end: str | datetime,
) -> FilterFunc:
    """Filter: created between start and end (inclusive)."""
    from path_file.units import parse_datetime

    start_dt = parse_datetime(start)
    end_dt = parse_datetime(end)

    if start_dt > end_dt:
        start_dt, end_dt = end_dt, start_dt

    def _filter(entry: Entry) -> bool:
        return start_dt <= entry.created <= end_dt

    return _filter


# Convenience time filters
def filter_modified_today() -> FilterFunc:
    """Filter: modified today."""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)

    def _filter(entry: Entry) -> bool:
        return today <= entry.modified < tomorrow

    return _filter


def filter_modified_this_week() -> FilterFunc:
    """Filter: modified this week (Monday-Sunday)."""
    now = datetime.now()
    week_start = now - timedelta(days=now.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = week_start + timedelta(days=7)

    def _filter(entry: Entry) -> bool:
        return week_start <= entry.modified < week_end

    return _filter


def filter_modified_this_month() -> FilterFunc:
    """Filter: modified this month."""
    now = datetime.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if month_start.month == 12:
        month_end = month_start.replace(year=month_start.year + 1, month=1)
    else:
        month_end = month_start.replace(month=month_start.month + 1)

    def _filter(entry: Entry) -> bool:
        return month_start <= entry.modified < month_end

    return _filter


def filter_created_today() -> FilterFunc:
    """Filter: created today."""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)

    def _filter(entry: Entry) -> bool:
        return today <= entry.created < tomorrow

    return _filter


def filter_created_this_week() -> FilterFunc:
    """Filter: created this week."""
    now = datetime.now()
    week_start = now - timedelta(days=now.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = week_start + timedelta(days=7)

    def _filter(entry: Entry) -> bool:
        return week_start <= entry.created < week_end

    return _filter


# ──────────────────────────────────────────────────────────────────────────────
# NAME & PATH FILTERS
# ──────────────────────────────────────────────────────────────────────────────


def filter_name_matches(pattern: str) -> FilterFunc:
    """Filter: name matches regex pattern (full name match)."""
    compiled = _compile_regex(pattern)

    def _filter(entry: Entry) -> bool:
        return bool(compiled.fullmatch(entry.name))

    return _filter


def filter_name_contains(text: str, case_sensitive: bool = False) -> FilterFunc:
    """Filter: name contains text."""
    if case_sensitive:

        def _filter(entry: Entry) -> bool:
            return text in entry.name
    else:
        text_lower = text.lower()

        def _filter(entry: Entry) -> bool:
            return text_lower in entry.name.lower()

    return _filter


def filter_name_starts_with(prefix: str, case_sensitive: bool = False) -> FilterFunc:
    """Filter: name starts with prefix."""
    if case_sensitive:

        def _filter(entry: Entry) -> bool:
            return entry.name.startswith(prefix)
    else:
        prefix_lower = prefix.lower()

        def _filter(entry: Entry) -> bool:
            return entry.name.lower().startswith(prefix_lower)

    return _filter


def filter_name_ends_with(suffix: str, case_sensitive: bool = False) -> FilterFunc:
    """Filter: name ends with suffix."""
    if case_sensitive:

        def _filter(entry: Entry) -> bool:
            return entry.name.endswith(suffix)
    else:
        suffix_lower = suffix.lower()

        def _filter(entry: Entry) -> bool:
            return entry.name.lower().endswith(suffix_lower)

    return _filter


def filter_path_contains(text: str, case_sensitive: bool = False) -> FilterFunc:
    """Filter: full path contains text."""
    if case_sensitive:

        def _filter(entry: Entry) -> bool:
            return text in str(entry.path)
    else:
        text_lower = text.lower()

        def _filter(entry: Entry) -> bool:
            return text_lower in str(entry.path).lower()

    return _filter


def filter_path_matches(pattern: str) -> FilterFunc:
    """Filter: full path matches regex pattern."""
    compiled = _compile_regex(pattern)

    def _filter(entry: Entry) -> bool:
        return bool(compiled.search(str(entry.path)))

    return _filter


def filter_in_folder(folder: str | Path) -> FilterFunc:
    """Filter: entry is inside given folder (or subfolder)."""
    folder_path = Path(folder).resolve()

    def _filter(entry: Entry) -> bool:
        try:
            entry.path.relative_to(folder_path)
            return True
        except ValueError:
            return False

    return _filter


def filter_not_in_folder(folder: str | Path) -> FilterFunc:
    """Filter: entry is NOT inside given folder."""
    folder_path = Path(folder).resolve()

    def _filter(entry: Entry) -> bool:
        try:
            entry.path.relative_to(folder_path)
            return False
        except ValueError:
            return True

    return _filter


# ──────────────────────────────────────────────────────────────────────────────
# VISIBILITY & PERMISSION FILTERS
# ──────────────────────────────────────────────────────────────────────────────


def filter_hidden() -> FilterFunc:
    """Filter: hidden files/directories."""

    def _filter(entry: Entry) -> bool:
        return entry.is_hidden

    return _filter


def filter_visible() -> FilterFunc:
    """Filter: non-hidden files/directories."""

    def _filter(entry: Entry) -> bool:
        return not entry.is_hidden

    return _filter


def filter_readable() -> FilterFunc:
    """Filter: readable entries."""

    def _filter(entry: Entry) -> bool:
        return os.access(entry.path, os.R_OK)

    return _filter


def filter_writable() -> FilterFunc:
    """Filter: writable entries."""

    def _filter(entry: Entry) -> bool:
        return os.access(entry.path, os.W_OK)

    return _filter


def filter_executable() -> FilterFunc:
    """Filter: executable entries."""

    def _filter(entry: Entry) -> bool:
        return os.access(entry.path, os.X_OK)

    return _filter


# ──────────────────────────────────────────────────────────────────────────────
# CONTENT FILTERS
# ──────────────────────────────────────────────────────────────────────────────


def filter_matching_content(text: str, encoding: str = "utf-8") -> FilterFunc:
    """Filter: text file contains given text."""

    def _filter(entry: Entry) -> bool:
        if not entry.is_file:
            return False
        try:
            content = entry.read_text(encoding)
            return text in content
        except (UnicodeDecodeError, OSError):
            return False

    return _filter


def filter_matching_regex_in_content(pattern: str, encoding: str = "utf-8") -> FilterFunc:
    """Filter: text file content matches regex pattern."""
    compiled = _compile_regex(pattern)

    def _filter(entry: Entry) -> bool:
        if not entry.is_file:
            return False
        try:
            content = entry.read_text(encoding)
            return bool(compiled.search(content))
        except (UnicodeDecodeError, OSError):
            return False

    return _filter


def filter_containing_line(text: str, encoding: str = "utf-8") -> FilterFunc:
    """Filter: text file contains a line with given text."""

    def _filter(entry: Entry) -> bool:
        if not entry.is_file:
            return False
        try:
            content = entry.read_text(encoding)
            return any(text in line for line in content.splitlines())
        except (UnicodeDecodeError, OSError):
            return False

    return _filter


def filter_containing_lines(*texts: str, encoding: str = "utf-8") -> FilterFunc:
    """Filter: text file contains ALL of the given lines."""

    def _filter(entry: Entry) -> bool:
        if not entry.is_file:
            return False
        try:
            content = entry.read_text(encoding)
            lines = content.splitlines()
            return all(any(t in line for line in lines) for t in texts)
        except (UnicodeDecodeError, OSError):
            return False

    return _filter


# ──────────────────────────────────────────────────────────────────────────────
# DUPLICATE FILTERS
# ──────────────────────────────────────────────────────────────────────────────


class _ContextFilter:
    """
    Callable marker for context-aware (duplicate/unique) filters.

    These filters need the full entry list to work, so per-entry calls always
    pass through (return True) and the real decision is made by the chain in
    ``FileChain._materialize()`` based on ``mode``.
    """

    _needs_context: bool = True

    def __init__(self, mode: str, algorithm: str | None = None) -> None:
        self.mode = mode
        self._algorithm = algorithm

    def __call__(self, entry: Entry) -> bool:
        return True  # marker only; the chain applies the real decision


def filter_duplicates_by_hash(algorithm: str = "sha256") -> FilterFunc:
    """Filter: entries that have duplicate content (by hash)."""
    # Context-aware filter; the chain applies it against all entries.
    return _ContextFilter("duplicates_by_hash", algorithm)


def filter_unique_by_hash() -> FilterFunc:
    """Filter: entries with unique content (no duplicates)."""
    # Context-aware filter; the chain applies it against all entries.
    return _ContextFilter("unique_by_hash")


def filter_duplicates_by_name() -> FilterFunc:
    """Filter: entries with duplicate names."""
    # Context-aware filter; the chain applies it against all entries.
    return _ContextFilter("duplicates_by_name")


def filter_unique_by_name() -> FilterFunc:
    """Filter: entries with unique names."""
    # Context-aware filter; the chain applies it against all entries.
    return _ContextFilter("unique_by_name")


def filter_same_size_as(path: str | Path) -> FilterFunc:
    """Filter: entries with same size as reference file."""
    ref_path = Path(path).resolve()
    ref_size = ref_path.stat().st_size if ref_path.exists() else -1

    def _filter(entry: Entry) -> bool:
        return entry.is_file and entry.size == ref_size

    return _filter


def filter_same_content_as(path: str | Path) -> FilterFunc:
    """Filter: entries with same content as reference file."""
    ref_path = Path(path).resolve()
    ref_hash = ""
    if ref_path.exists() and ref_path.is_file():
        import hashlib

        h = hashlib.sha256()
        with ref_path.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        ref_hash = h.hexdigest()

    def _filter(entry: Entry) -> bool:
        return entry.is_file and entry.hash_sha256 == ref_hash

    return _filter


# ──────────────────────────────────────────────────────────────────────────────
# GLOB FILTER (convenience)
# ──────────────────────────────────────────────────────────────────────────────


def filter_glob(pattern: str, case_sensitive: bool = False) -> FilterFunc:
    """Filter: name matches glob pattern."""
    matcher = make_glob_filter(pattern, case_sensitive)

    def _filter(entry: Entry) -> bool:
        return matcher(entry.name) or matcher(str(entry.path))

    return _filter


# ──────────────────────────────────────────────────────────────────────────────
# COMBINATION HELPERS
# ──────────────────────────────────────────────────────────────────────────────


def combine_filters(*filters: FilterFunc, operator: str = "and") -> FilterFunc:
    """Combine multiple filters with AND or OR logic."""
    if operator.lower() == "or":

        def _filter(entry: Entry) -> bool:
            return any(f(entry) for f in filters)
    else:  # "and"

        def _filter(entry: Entry) -> bool:
            return all(f(entry) for f in filters)

    return _filter


def negate_filter(filter_func: FilterFunc) -> FilterFunc:
    """Negate a filter."""

    def _filter(entry: Entry) -> bool:
        return not filter_func(entry)

    return _filter
