"""Progress reporting: progress bar and spinner (stdlib only)."""

from __future__ import annotations

import contextlib
import shutil
import sys
import time
from typing import IO, ClassVar

# ──────────────────────────────────────────────────────────────────────────────
# TERMINAL HELPERS
# ──────────────────────────────────────────────────────────────────────────────


def terminal_width(default: int = 80) -> int:
    """Return the current terminal width (falling back to ``default``)."""
    try:
        size = shutil.get_terminal_size(fallback=(default, 24))
    except (ValueError, OSError):
        return default
    return max(20, int(size.columns))


def _can_encode(stream: IO[str], text: str) -> bool:
    """Check whether a stream can encode text without loss."""
    try:
        encoding = getattr(stream, "encoding", None) or "ascii"
        text.encode(encoding, errors="strict")
        return True
    except (UnicodeError, LookupError, AttributeError):
        return False


def _safe_write(stream: IO[str], text: str) -> None:
    """Write to a stream, falling back to a replacement-safe encode."""
    try:
        stream.write(text)
    except UnicodeEncodeError:
        encoding = getattr(stream, "encoding", None) or "ascii"
        stream.write(text.encode(encoding, errors="replace").decode(encoding, errors="replace"))
    except (ValueError, OSError):
        pass


# ──────────────────────────────────────────────────────────────────────────────
# PROGRESS BAR
# ──────────────────────────────────────────────────────────────────────────────


class ProgressBar:
    """
    Simple determinate progress bar.

    Example:
        >>> with ProgressBar(100, prefix="copy: ") as bar:   # doctest: +SKIP
        ...     for _ in range(100):
        ...         bar.update(1)
    """

    # Unicode glyphs (used when the stream can encode them)
    FILLED = "\u2588"
    EMPTY = "\u2591"
    ARROW = "\u25b6"

    # ASCII fallbacks
    FILLED_ASCII = "#"
    EMPTY_ASCII = "-"
    ARROW_ASCII = ">"

    def __init__(
        self,
        total: int,
        prefix: str = "",
        width: int | None = None,
        stream: IO[str] | None = None,
        show_percent: bool = True,
        show_count: bool = True,
        refresh_interval: float = 0.05,
    ) -> None:
        self.total = max(0, int(total))
        self.prefix = prefix
        self.width = width if width is not None else 40
        self.stream = stream if stream is not None else sys.stderr
        self.show_percent = show_percent
        self.show_count = show_count
        self.refresh_interval = refresh_interval

        self.count = 0
        self.started_at = time.monotonic()
        self._last_render = 0.0
        self._closed = False
        self._entered = False

        # Choose glyphs based on what the stream can encode
        if _can_encode(self.stream, self.FILLED + self.EMPTY + self.ARROW):
            self._filled, self._empty, self._arrow = self.FILLED, self.EMPTY, self.ARROW
        else:
            self._filled, self._empty, self._arrow = (
                self.FILLED_ASCII,
                self.EMPTY_ASCII,
                self.ARROW_ASCII,
            )

    # ─── Properties ───────────────────────────────────────────────────────────

    @property
    def fraction(self) -> float:
        """Completion fraction between 0 and 1."""
        if self.total == 0:
            return 1.0
        return min(1.0, self.count / self.total)

    @property
    def percent(self) -> float:
        """Completion percentage between 0 and 100."""
        return self.fraction * 100

    @property
    def elapsed(self) -> float:
        """Seconds since the bar was created."""
        return time.monotonic() - self.started_at

    @property
    def rate(self) -> float:
        """Items per second (0 when unknown)."""
        if self.elapsed <= 0 or self.count == 0:
            return 0.0
        return self.count / self.elapsed

    @property
    def eta(self) -> float | None:
        """Estimated remaining seconds, or None when unknown."""
        if self.total <= self.count or self.rate <= 0:
            return None
        return (self.total - self.count) / self.rate

    # ─── Rendering ────────────────────────────────────────────────────────────

    def _render(self, force: bool = False) -> str:
        """Build the bar string."""
        now = time.monotonic()
        if not force and (now - self._last_render) < self.refresh_interval:
            return ""
        self._last_render = now

        filled = round(self.width * self.fraction) if self.total > 0 else self.width
        bar = self._filled * filled + self._empty * max(0, self.width - filled)

        parts = [self.prefix, bar]
        if self.show_percent:
            parts.append(f" {self.percent:5.1f}%")
        if self.show_count:
            if self.total:
                parts.append(f" ({self.count}/{self.total})")
            else:
                parts.append(f" ({self.count})")
        return "".join(parts)

    def update(self, n: int = 1) -> None:
        """Advance the bar by ``n`` items and redraw."""
        if self._closed:
            return
        self.count = min(self.count + max(0, int(n)), self.total) if self.total else self.count + n
        line = self._render()
        if line:
            _safe_write(self.stream, "\r" + line.ljust(terminal_width() - 1))

    def set(self, value: int) -> None:
        """Set the bar to an absolute item count."""
        if self._closed:
            return
        self.count = min(max(0, int(value)), self.total) if self.total else int(value)
        line = self._render(force=True)
        if line:
            _safe_write(self.stream, "\r" + line.ljust(terminal_width() - 1))

    def finish(self) -> None:
        """Complete the bar and move to the next line."""
        if self._closed:
            return
        self.count = self.total
        line = self._render(force=True)
        if line:
            _safe_write(self.stream, "\r" + line.ljust(terminal_width() - 1) + "\n")
            flush = getattr(self.stream, "flush", None)
            if flush is not None:
                with contextlib.suppress(ValueError, OSError):
                    flush()
        self._closed = True

    # ─── Context Manager ──────────────────────────────────────────────────────

    def __enter__(self) -> ProgressBar:
        self._entered = True
        if self.total:
            line = self._render(force=True)
            if line:
                _safe_write(self.stream, "\r" + line.ljust(terminal_width() - 1))
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.finish()
        self._entered = False

    def __repr__(self) -> str:
        return f"ProgressBar(count={self.count}, total={self.total}, percent={self.percent:.1f})"


# ──────────────────────────────────────────────────────────────────────────────
# SPINNER (indeterminate progress)
# ──────────────────────────────────────────────────────────────────────────────


class Spinner:
    """
    Indeterminate spinner for operations with unknown duration.

    Example:
        >>> with Spinner("Working"):   # doctest: +SKIP
        ...     do_something_slow()
    """

    FRAMES: ClassVar[list[str]] = [
        "\u280b",
        "\u2819",
        "\u2839",
        "\u2838",
        "\u283c",
        "\u2834",
        "\u2826",
        "\u2827",
        "\u2807",
        "\u280f",
    ]
    FRAMES_ASCII: ClassVar[list[str]] = ["|", "/", "-", "\\"]

    def __init__(
        self,
        message: str = "",
        interval: float = 0.1,
        stream: IO[str] | None = None,
    ) -> None:
        self.message = message
        self.interval = interval
        self.stream = stream if stream is not None else sys.stderr
        self.count = 0
        self._frame = 0
        self._last_render = 0.0
        self._closed = False
        self._entered = False

        if _can_encode(self.stream, "".join(self.FRAMES)):
            self._frames = self.FRAMES
        else:
            self._frames = self.FRAMES_ASCII

    def update(self, message: str | None = None) -> None:
        """Redraw the spinner (optionally with a new message)."""
        if self._closed:
            return
        if message is not None:
            self.message = message
        self.count += 1
        now = time.monotonic()
        if (now - self._last_render) < self.interval:
            return
        self._last_render = now
        frame = self._frames[self._frame % len(self._frames)]
        self._frame += 1
        text = f"\r{frame} {self.message}" if self.message else f"\r{frame}"
        _safe_write(self.stream, text.ljust(terminal_width() - 1))

    def stop(self) -> None:
        """Clear the spinner line."""
        if self._closed:
            return
        _safe_write(self.stream, "\r" + " " * (terminal_width() - 1) + "\r")
        flush = getattr(self.stream, "flush", None)
        if flush is not None:
            with contextlib.suppress(ValueError, OSError):
                flush()
        self._closed = True

    # ─── Context Manager ──────────────────────────────────────────────────────

    def __enter__(self) -> Spinner:
        self._entered = True
        self.update()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.stop()
        self._entered = False

    def __repr__(self) -> str:
        return f"Spinner(message={self.message!r}, count={self.count})"


# ──────────────────────────────────────────────────────────────────────────────
# FACTORY
# ──────────────────────────────────────────────────────────────────────────────


def create_progress(
    total: int | None,
    message: str = "",
    stream: IO[str] | None = None,
) -> ProgressBar | Spinner:
    """Create a ProgressBar when the total is known, else a Spinner."""
    if total is not None:
        return ProgressBar(total, prefix=message, stream=stream)
    return Spinner(message, stream=stream)


__all__ = [
    "ProgressBar",
    "Spinner",
    "create_progress",
    "terminal_width",
]
