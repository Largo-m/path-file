"""Internal parsing utilities with caching."""

from __future__ import annotations

import functools
import re
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from re import Pattern

from path_file.exceptions import InvalidDurationError, InvalidPatternError, InvalidSizeError
from path_file.units import parse_datetime, parse_duration, parse_size

# ──────────────────────────────────────────────────────────────────────────────
# REGEX CACHE
# ──────────────────────────────────────────────────────────────────────────────


@functools.lru_cache(maxsize=256)
def _compile_regex(pattern: str, flags: int = 0) -> Pattern[str]:
    """Compile and cache regex pattern."""
    try:
        return re.compile(pattern, flags)
    except re.error as e:
        raise InvalidPatternError(pattern, f"Invalid regex: {e}") from e


# ──────────────────────────────────────────────────────────────────────────────
# PATTERN MATCHER
# ──────────────────────────────────────────────────────────────────────────────


class PatternMatcher:
    """
    Unified pattern matching for glob and regex patterns.

    Supports:
    - Glob patterns: *.txt, **/*.py, folder/*
    - Regex patterns: wrapped in /.../ or prefixed with 're:'
    - Plain strings: exact match
    """

    def __init__(self, pattern: str, case_sensitive: bool = False) -> None:
        self.pattern = pattern
        self.case_sensitive = case_sensitive
        self._compiled: Pattern[str] | None = None
        self._is_regex = False
        self._parse_pattern()

    def _parse_pattern(self) -> None:
        """Parse pattern and determine type."""
        # Regex: /pattern/flags or re:pattern
        if self.pattern.startswith("/") and self.pattern.count("/") >= 2:
            # /pattern/flags
            parts = self.pattern.split("/")
            if len(parts) >= 3:
                pattern = "/".join(parts[1:-1])
                flags_str = parts[-1]
                flags = 0
                if "i" in flags_str:
                    flags |= re.IGNORECASE
                if "m" in flags_str:
                    flags |= re.MULTILINE
                if "s" in flags_str:
                    flags |= re.DOTALL
                self._compiled = _compile_regex(pattern, flags)
                self._is_regex = True
                return
        elif self.pattern.startswith("re:"):
            self._compiled = _compile_regex(
                self.pattern[3:], 0 if self.case_sensitive else re.IGNORECASE
            )
            self._is_regex = True
            return

        # Glob pattern - convert to regex
        self._is_regex = False

    def match(self, text: str) -> bool:
        """Match text against pattern."""
        if self._is_regex and self._compiled:
            return bool(self._compiled.search(text))

        # Glob matching
        return self._glob_match(text)

    def _glob_match(self, text: str) -> bool:
        """Match using glob-style pattern."""
        import fnmatch

        if self.case_sensitive:
            return fnmatch.fnmatchcase(text, self.pattern) or fnmatch.fnmatchcase(
                Path(text).name, self.pattern
            )
        else:
            # Case-insensitive matching - use lower() on both sides
            text_lower = text.lower()
            pattern_lower = self.pattern.lower()
            name_lower = Path(text).name.lower()
            return fnmatch.fnmatch(text_lower, pattern_lower) or fnmatch.fnmatch(
                name_lower, pattern_lower
            )

    def match_path(self, path: Path) -> bool:
        """Match against path (both full path and name)."""
        return self.match(str(path)) or self.match(path.name)


# ──────────────────────────────────────────────────────────────────────────────
# SIZE PARSER
# ──────────────────────────────────────────────────────────────────────────────


class SizeParser:
    """Parse and validate size specifications."""

    @staticmethod
    def parse(size: str | int | float) -> int:
        """Parse size to bytes."""
        return parse_size(size)

    @staticmethod
    def parse_range(size_spec: str) -> tuple[int, int]:
        """
        Parse size range like '1MB-10MB' or '1MB..10MB'.
        Returns (min_bytes, max_bytes).
        """
        for sep in ["..", "-", " to ", " TO "]:
            if sep in size_spec:
                parts = size_spec.split(sep)
                if len(parts) == 2:
                    return (parse_size(parts[0].strip()), parse_size(parts[1].strip()))
        raise InvalidSizeError(size_spec, "Use format like '1MB-10MB' or '1MB..10MB'")


# ──────────────────────────────────────────────────────────────────────────────
# DURATION PARSER
# ──────────────────────────────────────────────────────────────────────────────


class DurationParser:
    """Parse and validate duration specifications."""

    @staticmethod
    def parse(duration: str | int | float | timedelta) -> timedelta:
        """Parse duration to timedelta."""
        return parse_duration(duration)

    @staticmethod
    def parse_range(duration_spec: str) -> tuple[timedelta, timedelta]:
        """
        Parse duration range like '1d-7d' or '1 hour..2 hours'.
        Returns (min_timedelta, max_timedelta).
        """
        for sep in ["..", "-", " to ", " TO "]:
            if sep in duration_spec:
                parts = duration_spec.split(sep)
                if len(parts) == 2:
                    return (
                        parse_duration(parts[0].strip()),
                        parse_duration(parts[1].strip()),
                    )
        raise InvalidDurationError(duration_spec, "Use format like '1d-7d' or '1 hour..2 hours'")


# ──────────────────────────────────────────────────────────────────────────────
# DATETIME PARSER
# ──────────────────────────────────────────────────────────────────────────────


class DateTimeParser:
    """Parse datetime specifications."""

    @staticmethod
    def parse(dt: str | datetime) -> datetime:
        """Parse datetime string."""
        return parse_datetime(dt)

    @staticmethod
    def parse_range(dt_spec: str) -> tuple[datetime, datetime]:
        """Parse datetime range."""
        for sep in ["..", "-", " to ", " TO "]:
            if sep in dt_spec:
                parts = dt_spec.split(sep)
                if len(parts) == 2:
                    return (
                        parse_datetime(parts[0].strip()),
                        parse_datetime(parts[1].strip()),
                    )
        raise ValueError(f"Invalid datetime range: {dt_spec}")


# ──────────────────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ──────────────────────────────────────────────────────────────────────────────


def make_glob_filter(pattern: str, case_sensitive: bool = False) -> Callable[[str], bool]:
    """Create a filter function for glob pattern."""
    matcher = PatternMatcher(pattern, case_sensitive)
    return matcher.match


def make_regex_filter(pattern: str, flags: int = 0) -> Callable[[str], bool]:
    """Create a filter function for regex pattern."""
    compiled = _compile_regex(pattern, flags)
    return lambda text: bool(compiled.search(text))


def make_size_filter(
    min_size: int | None = None, max_size: int | None = None
) -> Callable[[int], bool]:
    """Create a filter function for size range."""

    def _filter(size: int) -> bool:
        if min_size is not None and size < min_size:
            return False
        return not (max_size is not None and size > max_size)

    return _filter


def make_time_filter(
    min_time: datetime | None = None, max_time: datetime | None = None
) -> Callable[[datetime], bool]:
    """Create a filter function for time range."""

    def _filter(dt: datetime) -> bool:
        if min_time is not None and dt < min_time:
            return False
        return not (max_time is not None and dt > max_time)

    return _filter
