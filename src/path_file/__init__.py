"""
path_file - The elegant file automation library for Python.

A zero-dependency, chainable API for file operations with dry-run safety,
progress reporting, and declarative rules.
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

from path_file._internal._log import debug, get_logger, quiet, set_verbosity, verbose
from path_file._version import __version__
from path_file.archive import create_archive, detect_archive_type, extract_archive, list_archive
from path_file.chain import FileChain
from path_file.entries import ActionResult, Entry, Report, SyncDiff, SyncResult
from path_file.exceptions import (
    ArchiveError,
    DestExistsError,
    DryRunRequiredError,
    FileNotFoundError,
    HashError,
    InvalidDurationError,
    InvalidPatternError,
    InvalidSizeError,
    PathflowError,
    PermissionError,
    RulesParseError,
    SyncConflictError,
    WatchError,
)
from path_file.hash import (
    find_duplicates,
    hash_file,
    hash_files,
    verify_hash,
    verify_hashes,
)
from path_file.progress import ProgressBar, Spinner, create_progress, terminal_width
from path_file.report import (
    PathflowJSONEncoder,
    build_report,
    format_entry_table,
    format_extension_table,
    format_report,
    format_size_bucket_table,
    format_table,
    to_csv,
    to_json,
)
from path_file.rules import Rule, Rules
from path_file.search import is_text_file, search_content, search_regex
from path_file.sync import Syncer, sync
from path_file.units import (
    human_ago,
    human_duration,
    human_size,
    parse_datetime,
    parse_duration,
    parse_size,
)
from path_file.utils import (
    change_extension,
    copy_file,
    count_files,
    delete_dir,
    delete_file,
    disk_usage,
    duration,
    expand,
    extract_archive,
    find_largest,
    find_newest,
    find_oldest,
    free_space,
    get_extension,
    get_mime_type,
    get_size,
    get_size_human,
    hash_file,
    hsize,
    is_binary,
    is_symlink,
    make_archive,
    mkdir,
    move_file,
    read_bytes,
    read_text,
    readlink,
    resolve_link,
    run_command,
    run_shell,
    safe_join,
    size,
    strip_extension,
    symlink,
    tempdir,
    touch,
    verify_hash,
    which,
    write_bytes,
    write_text,
)
from path_file.watch import Watcher, WatchEvent, watch

# ──────────────────────────────────────────────────────────────────────────────
# ENTRY POINTS
# ──────────────────────────────────────────────────────────────────────────────


def find(path: str | Path) -> FileChain:
    """
    Create a FileChain from a directory path.

    Args:
        path: Directory to search (recursive by default)

    Returns:
        FileChain for chaining filters and actions

    Example:
        pf.find("~/Downloads").files().with_extension(".jpg").copy_to("~/Pictures")
    """
    return FileChain(path)


def scan(path: str | Path) -> FileChain:
    """Alias for find()."""
    return find(path)


def current() -> FileChain:
    """Create a FileChain from the current working directory."""
    return FileChain(Path.cwd())


# ──────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ──────────────────────────────────────────────────────────────────────────────

__all__ = [
    # Version
    "__version__",
    # Core classes
    "FileChain",
    "Entry",
    "ActionResult",
    "Report",
    "SyncDiff",
    "SyncResult",
    # Exceptions
    "PathflowError",
    "FileNotFoundError",
    "PermissionError",
    "DestExistsError",
    "InvalidPatternError",
    "InvalidSizeError",
    "InvalidDurationError",
    "RulesParseError",
    "DryRunRequiredError",
    "SyncConflictError",
    "WatchError",
    "ArchiveError",
    "HashError",
    # Units
    "parse_size",
    "human_size",
    "parse_duration",
    "human_ago",
    "parse_datetime",
    "human_duration",
    # Rules
    "Rules",
    "Rule",
    # Watch
    "Watcher",
    "WatchEvent",
    "watch",
    # Sync
    "Syncer",
    "sync",
    # Utils
    "size",
    "hsize",
    "duration",
    "tempdir",
    "mkdir",
    "which",
    "free_space",
    "disk_usage",
    "expand",
    "safe_join",
    "copy_file",
    "move_file",
    "delete_file",
    "delete_dir",
    "touch",
    "read_text",
    "read_bytes",
    "write_text",
    "write_bytes",
    "symlink",
    "readlink",
    "is_symlink",
    "resolve_link",
    "run_command",
    "run_shell",
    "get_size",
    "get_size_human",
    "count_files",
    "find_largest",
    "find_oldest",
    "find_newest",
    "make_archive",
    "extract_archive",
    "hash_file",
    "verify_hash",
    "is_binary",
    "get_mime_type",
    "get_extension",
    "strip_extension",
    "change_extension",
    # Entry points
    "find",
    "scan",
    "current",
]
