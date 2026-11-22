"""Unit parsing and formatting utilities for path_file."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from path_file.exceptions import InvalidDurationError, InvalidSizeError

# ──────────────────────────────────────────────────────────────────────────────
# SIZE PARSING & FORMATTING
# ──────────────────────────────────────────────────────────────────────────────

_SIZE_PATTERN = re.compile(
    r"""^\s*
        (?P<value>[\d.]+)
        \s*
        (?P<unit>[KMGT]?i?B?)?
        \s*$""",
    re.IGNORECASE | re.VERBOSE,
)

_SIZE_MULTIPLIERS: dict[str, int] = {
    "b": 1,
    "kb": 1024,
    "kib": 1024,
    "mb": 1024**2,
    "mib": 1024**2,
    "gb": 1024**3,
    "gib": 1024**3,
    "tb": 1024**4,
    "tib": 1024**4,
    "pb": 1024**5,
    "pib": 1024**5,
}


def parse_size(size: str | int | float) -> int:
    """
    Parse a human-readable size string into bytes.

    Args:
        size: Size specification (e.g., "100", "1KB", "2.5MB", "1GB", 1024)

    Returns:
        Size in bytes as integer

    Raises:
        InvalidSizeError: If the size specification is invalid

    Examples:
        >>> parse_size("100")
        100
        >>> parse_size("1KB")
        1024
        >>> parse_size("2.5 MB")
        2621440
        >>> parse_size("1GB")
        1073741824
        >>> parse_size(512)
        512
    """
    if isinstance(size, (int, float)):
        if size < 0:
            raise InvalidSizeError(str(size), "Size cannot be negative")
        return int(size)

    if not isinstance(size, str):
        raise InvalidSizeError(str(size), "Size must be string or number")

    size = size.strip()
    if not size:
        raise InvalidSizeError("", "Empty size specification")

    match = _SIZE_PATTERN.match(size)
    if not match:
        raise InvalidSizeError(size, "Use format like '100B', '1KB', '2.5MB', '1GB'")

    value_str = match.group("value")
    unit = (match.group("unit") or "B").lower()

    try:
        value = float(value_str)
    except ValueError:
        raise InvalidSizeError(size, f"Invalid number: {value_str}")

    if value < 0:
        raise InvalidSizeError(size, "Size cannot be negative")

    multiplier = _SIZE_MULTIPLIERS.get(unit)
    if multiplier is None:
        raise InvalidSizeError(
            size, f"Unknown unit: {unit}. Use B, KB, MB, GB, TB (or KiB, MiB, etc.)"
        )

    return int(value * multiplier)


def human_size(size: int, precision: int = 2, binary: bool = True) -> str:
    """
    Format bytes into human-readable string.

    Args:
        size: Size in bytes
        precision: Decimal places for formatted output
        binary: Use binary units (KiB, MiB) if True, decimal (KB, MB) if False

    Returns:
        Human-readable size string

    Examples:
        >>> human_size(1024)
        '1.00 KiB'
        >>> human_size(1536)
        '1.50 KiB'
        >>> human_size(1024**2)
        '1.00 MiB'
        >>> human_size(1024**3 * 2.5)
        '2.50 GiB'
    """
    if size < 0:
        return f"-{human_size(-size, precision, binary)}"

    if size == 0:
        return "0 B"

    units = (
        ["B", "KiB", "MiB", "GiB", "TiB", "PiB"] if binary else ["B", "KB", "MB", "GB", "TB", "PB"]
    )
    base = 1024 if binary else 1000

    import math

    exponent = min(int(math.log(size, base)), len(units) - 1)
    value = size / (base**exponent)

    if exponent == 0:
        return f"{int(value)} {units[0]}"

    return f"{value:.{precision}f} {units[exponent]}"


# ──────────────────────────────────────────────────────────────────────────────
# DURATION PARSING & FORMATTING
# ──────────────────────────────────────────────────────────────────────────────

_DURATION_PATTERN = re.compile(
    r"""^\s*
        (?P<value>[\d.]+)
        \s*
        (?P<unit>
            (?:milli)?seconds?|secs?|s
            |minutes?|mins?|m
            |hours?|hrs?|h
            |days?|d
            |weeks?|wks?|w
            |months?|mos?|mon
            |years?|yrs?|y
        )?
        \s*$""",
    re.IGNORECASE | re.VERBOSE,
)

_DURATION_UNITS: dict[str, float] = {
    "s": 1,
    "sec": 1,
    "second": 1,
    "seconds": 1,
    "m": 60,
    "min": 60,
    "minute": 60,
    "minutes": 60,
    "h": 3600,
    "hr": 3600,
    "hour": 3600,
    "hours": 3600,
    "d": 86400,
    "day": 86400,
    "days": 86400,
    "w": 604800,
    "wk": 604800,
    "week": 604800,
    "weeks": 604800,
    "mon": 2592000,
    "month": 2592000,
    "months": 2592000,
    "y": 31536000,
    "yr": 31536000,
    "year": 31536000,
    "years": 31536000,
}


def parse_duration(duration: str | int | float | timedelta) -> timedelta:
    """
    Parse a human-readable duration string into timedelta.

    Args:
        duration: Duration specification (e.g., "7 days", "1h", "30m", 3600)

    Returns:
        timedelta object

    Raises:
        InvalidDurationError: If the duration specification is invalid

    Examples:
        >>> parse_duration("7 days")
        datetime.timedelta(days=7)
        >>> parse_duration("1h")
        datetime.timedelta(seconds=3600)
        >>> parse_duration("30m")
        datetime.timedelta(seconds=1800)
        >>> parse_duration("1 week")
        datetime.timedelta(days=7)
        >>> parse_duration(3600)
        datetime.timedelta(seconds=3600)
    """
    if isinstance(duration, timedelta):
        return duration

    if isinstance(duration, (int, float)):
        if duration < 0:
            raise InvalidDurationError(str(duration), "Duration cannot be negative")
        return timedelta(seconds=duration)

    if not isinstance(duration, str):
        raise InvalidDurationError(str(duration), "Duration must be string or number")

    duration = duration.strip()
    if not duration:
        raise InvalidDurationError("", "Empty duration specification")

    match = _DURATION_PATTERN.match(duration)
    if not match:
        raise InvalidDurationError(duration, "Use format like '7 days', '1h', '30m', '1 week'")

    value_str = match.group("value")
    unit = (match.group("unit") or "s").lower()

    try:
        value = float(value_str)
    except ValueError:
        raise InvalidDurationError(duration, f"Invalid number: {value_str}")

    if value < 0:
        raise InvalidDurationError(duration, "Duration cannot be negative")

    multiplier = _DURATION_UNITS.get(unit)
    if multiplier is None:
        raise InvalidDurationError(
            duration,
            f"Unknown unit: {unit}. Use s, m, h, d, w, month, year",
        )

    return timedelta(seconds=value * multiplier)


def human_duration(td: timedelta, short: bool = False) -> str:
    """
    Format timedelta into human-readable string.

    Args:
        td: timedelta object
        short: Use short format (e.g., "3d 4h" instead of "3 days 4 hours")

    Returns:
        Human-readable duration string

    Examples:
        >>> human_duration(timedelta(days=3, hours=4))
        '3 days 4 hours'
        >>> human_duration(timedelta(hours=25), short=True)
        '1d 1h'
    """
    total_seconds = int(td.total_seconds())
    if total_seconds < 0:
        return f"-{human_duration(timedelta(seconds=-total_seconds), short)}"

    if total_seconds == 0:
        return "0s" if short else "0 seconds"

    parts = []
    units = (
        [
            ("y", 31536000),
            ("d", 86400),
            ("h", 3600),
            ("m", 60),
            ("s", 1),
        ]
        if short
        else [
            ("year", 31536000),
            ("day", 86400),
            ("hour", 3600),
            ("minute", 60),
            ("second", 1),
        ]
    )

    for unit_name, unit_seconds in units:
        if total_seconds >= unit_seconds:
            count = total_seconds // unit_seconds
            total_seconds %= unit_seconds
            if short:
                parts.append(f"{count}{unit_name}")
            else:
                suffix = "s" if count != 1 else ""
                parts.append(f"{count} {unit_name}{suffix}")

    return " ".join(parts) if not short else "".join(parts)


# ──────────────────────────────────────────────────────────────────────────────
# DATETIME PARSING & FORMATTING
# ──────────────────────────────────────────────────────────────────────────────

_RELATIVE_DATE_PATTERN = re.compile(
    r"""^\s*(?P<keyword>today|yesterday|tomorrow|now)\s*$""", re.IGNORECASE
)


def parse_datetime(dt: str | datetime) -> datetime:
    """
    Parse a datetime string into datetime object.

    Args:
        dt: Datetime string (ISO format, "today", "yesterday", etc.)

    Returns:
        datetime object (naive, local time)

    Examples:
        >>> parse_datetime("2024-01-15")
        datetime.datetime(2024, 1, 15, 0, 0)
        >>> parse_datetime("2024-01-15 10:30")
        datetime.datetime(2024, 1, 15, 10, 30)
        >>> parse_datetime("today")
        datetime.datetime(2024, ..., 0, 0)  # today at midnight
    """
    if isinstance(dt, datetime):
        return dt

    if not isinstance(dt, str):
        raise ValueError(f"Expected string or datetime, got {type(dt).__name__}")

    dt = dt.strip()
    if not dt:
        raise ValueError("Empty datetime string")

    # Relative keywords
    match = _RELATIVE_DATE_PATTERN.match(dt)
    if match:
        keyword = match.group("keyword").lower()
        now = datetime.now()
        if keyword == "today":
            return datetime(now.year, now.month, now.day)
        elif keyword == "yesterday":
            return datetime(now.year, now.month, now.day) - timedelta(days=1)
        elif keyword == "tomorrow":
            return datetime(now.year, now.month, now.day) + timedelta(days=1)
        elif keyword == "now":
            return now

    # Try ISO formats
    formats = [
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y/%m/%d",
        "%d.%m.%Y %H:%M:%S",
        "%d.%m.%Y %H:%M",
        "%d.%m.%Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(dt, fmt)
        except ValueError:
            continue

    raise ValueError(
        f"Unable to parse datetime: {dt}. "
        "Use ISO format (YYYY-MM-DD HH:MM:SS) or 'today', 'yesterday', etc."
    )


def human_ago(dt: datetime) -> str:
    """
    Format datetime as relative time from now.

    Args:
        dt: datetime object (naive, assumed local time)

    Returns:
        Human-readable relative time string

    Examples:
        >>> human_ago(datetime.now() - timedelta(days=3))
        '3 days ago'
        >>> human_ago(datetime.now() + timedelta(hours=2))
        'in 2 hours'
        >>> human_ago(datetime.now() - timedelta(seconds=30))
        'just now'
    """
    now = datetime.now()
    diff = dt - now
    total_seconds = int(diff.total_seconds())

    if abs(total_seconds) < 60:
        return "just now"

    if total_seconds < 0:
        return f"{human_duration(timedelta(seconds=-total_seconds))} ago"
    else:
        return f"in {human_duration(timedelta(seconds=total_seconds))}"
