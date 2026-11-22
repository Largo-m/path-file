"""Simple logging setup using stdlib logging."""

from __future__ import annotations

import logging
import sys

# ──────────────────────────────────────────────────────────────────────────────
# LOGGER SETUP
# ──────────────────────────────────────────────────────────────────────────────

_DEFAULT_LEVEL = logging.WARNING
_LOGGER_NAME = "path_file"
_LOGGER: logging.Logger | None = None


def get_logger(name: str = _LOGGER_NAME) -> logging.Logger:
    """
    Get or create the path_file logger.

    Args:
        name: Logger name (default: 'path_file')

    Returns:
        Configured logger instance
    """
    global _LOGGER
    if _LOGGER is None:
        _LOGGER = _create_logger(name)
    return _LOGGER


def _create_logger(name: str) -> logging.Logger:
    """Create and configure logger."""
    logger = logging.getLogger(name)
    logger.setLevel(_DEFAULT_LEVEL)

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # Console handler with simple format
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(_DEFAULT_LEVEL)

    formatter = logging.Formatter("%(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


def set_verbosity(level: int) -> None:
    """
    Set logging verbosity level.

    Args:
        level: Logging level (logging.DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    logger = get_logger()
    logger.setLevel(level)
    for handler in logger.handlers:
        handler.setLevel(level)


def verbose() -> None:
    """Enable verbose (INFO) logging."""
    set_verbosity(logging.INFO)


def quiet() -> None:
    """Enable quiet (CRITICAL only) logging."""
    set_verbosity(logging.CRITICAL)


def debug() -> None:
    """Enable debug logging."""
    set_verbosity(logging.DEBUG)


# ──────────────────────────────────────────────────────────────────────────────
# CONTEXT MANAGERS
# ──────────────────────────────────────────────────────────────────────────────


class LogContext:
    """Context manager for temporary log level changes."""

    def __init__(self, level: int) -> None:
        self.level = level
        self.previous_level = _DEFAULT_LEVEL

    def __enter__(self) -> None:
        global _DEFAULT_LEVEL
        self.previous_level = get_logger().level
        set_verbosity(self.level)

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        set_verbosity(self.previous_level)


def with_verbose() -> LogContext:
    """Context manager for verbose logging."""
    return LogContext(logging.INFO)


def with_quiet() -> LogContext:
    """Context manager for quiet logging."""
    return LogContext(logging.CRITICAL)


def with_debug() -> LogContext:
    """Context manager for debug logging."""
    return LogContext(logging.DEBUG)


# ──────────────────────────────────────────────────────────────────────────────
# CONVENIENCE FUNCTIONS
# ──────────────────────────────────────────────────────────────────────────────


def log_debug(msg: str, *args: object) -> None:
    """Log debug message."""
    get_logger().debug(msg, *args)


def log_info(msg: str, *args: object) -> None:
    """Log info message."""
    get_logger().info(msg, *args)


def log_warning(msg: str, *args: object) -> None:
    """Log warning message."""
    get_logger().warning(msg, *args)


def log_error(msg: str, *args: object) -> None:
    """Log error message."""
    get_logger().error(msg, *args)


def log_exception(msg: str, *args: object) -> None:
    """Log exception with traceback."""
    get_logger().exception(msg, *args)
