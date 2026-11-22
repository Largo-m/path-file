"""
path_file - The elegant file automation library for Python.

A zero-dependency, chainable API for file operations with dry-run safety,
progress reporting, and declarative rules.
"""

from __future__ import annotations

from pathlib import Path

from path_file._internal._log import debug as debug
from path_file._internal._log import get_logger as get_logger
from path_file._internal._log import quiet as quiet
from path_file._internal._log import set_verbosity as set_verbosity
from path_file._internal._log import verbose as verbose
from path_file._version import __version__
from path_file.archive import create_archive as create_archive
from path_file.archive import detect_archive_type as detect_archive_type
from path_file.archive import list_archive as list_archive
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
from path_file.hash import find_duplicates as find_duplicates
from path_file.hash import hash_files as hash_files
from path_file.hash import verify_hashes as verify_hashes
from path_file.progress import ProgressBar as ProgressBar
from path_file.progress import Spinner as Spinner
from path_file.progress import create_progress as create_progress
from path_file.progress import terminal_width as terminal_width
from path_file.report import PathflowJSONEncoder as PathflowJSONEncoder
from path_file.report import build_report as build_report
from path_file.report import format_entry_table as format_entry_table
from path_file.report import format_extension_table as format_extension_table
from path_file.report import format_report as format_report
from path_file.report import format_size_bucket_table as format_size_bucket_table
from path_file.report import format_table as format_table
from path_file.report import to_csv as to_csv
from path_file.report import to_json as to_json
from path_file.rules import Rule, Rules
from path_file.search import is_text_file as is_text_file
from path_file.search import search_content as search_content
from path_file.search import search_regex as search_regex
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
    "ActionResult",
    "ArchiveError",
    "DestExistsError",
    "DryRunRequiredError",
    "Entry",
    "FileChain",
    "FileNotFoundError",
    "HashError",
    "InvalidDurationError",
    "InvalidPatternError",
    "InvalidSizeError",
    "PathflowError",
    "PermissionError",
    "Report",
    "Rule",
    "Rules",
    "RulesParseError",
    "SyncConflictError",
    "SyncDiff",
    "SyncResult",
    "Syncer",
    "WatchError",
    "WatchEvent",
    "Watcher",
    "__version__",
    "change_extension",
    "copy_file",
    "count_files",
    "current",
    "delete_dir",
    "delete_file",
    "disk_usage",
    "duration",
    "expand",
    "extract_archive",
    "find",
    "find_largest",
    "find_newest",
    "find_oldest",
    "free_space",
    "get_extension",
    "get_mime_type",
    "get_size",
    "get_size_human",
    "hash_file",
    "hsize",
    "human_ago",
    "human_duration",
    "human_size",
    "is_binary",
    "is_symlink",
    "make_archive",
    "mkdir",
    "move_file",
    "parse_datetime",
    "parse_duration",
    "parse_size",
    "read_bytes",
    "read_text",
    "readlink",
    "resolve_link",
    "run_command",
    "run_shell",
    "safe_join",
    "scan",
    "size",
    "strip_extension",
    "symlink",
    "sync",
    "tempdir",
    "touch",
    "verify_hash",
    "watch",
    "which",
    "write_bytes",
    "write_text",
]
