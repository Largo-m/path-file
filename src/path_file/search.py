"""Content search utilities for finding text/regex in files."""

from __future__ import annotations

import mmap
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from path_file._internal._log import get_logger, log_debug
from path_file._internal._parsers import _compile_regex
from path_file.entries import Entry

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# TEXT FILE DETECTION
# ──────────────────────────────────────────────────────────────────────────────

_TEXT_EXTENSIONS = {
    # Code
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".go",
    ".rs",
    ".rb",
    ".php",
    ".swift",
    ".kt",
    ".scala",
    ".clj",
    ".sh",
    ".bash",
    ".zsh",
    ".fish",
    ".ps1",
    ".bat",
    ".cmd",
    ".html",
    ".htm",
    ".css",
    ".scss",
    ".sass",
    ".less",
    ".xml",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".config",
    ".sql",
    ".r",
    ".m",
    ".pl",
    ".lua",
    ".vim",
    ".elm",
    ".dart",
    ".ex",
    ".exs",
    # Text
    ".txt",
    ".md",
    ".rst",
    ".adoc",
    ".tex",
    ".bib",
    ".csv",
    ".tsv",
    ".log",
    ".out",
    ".err",
    ".trace",
    ".dump",
    # Config
    ".gitignore",
    ".gitattributes",
    ".dockerignore",
    ".editorconfig",
    # Docs
    ".doc",
    ".docx",
    ".odt",
    ".rtf",  # These are binary but we'll try
}

_BINARY_EXTENSIONS = {
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".bin",
    ".dat",
    ".db",
    ".sqlite",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".tiff",
    ".webp",
    ".ico",
    ".mp3",
    ".mp4",
    ".avi",
    ".mkv",
    ".mov",
    ".wav",
    ".flac",
    ".ogg",
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
    ".xz",
    ".7z",
    ".rar",
    ".jar",
    ".war",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".ttf",
    ".otf",
    ".woff",
    ".woff2",
    ".eot",
    ".class",
    ".pyc",
    ".pyo",
    ".pyd",
}

_MAX_TEXT_FILE_SIZE = 100 * 1024 * 1024  # 100 MB


def is_text_file(path: Path, check_content: bool = True) -> bool:
    """
    Determine if a file is likely a text file.

    Args:
        path: File path
        check_content: If True, check first bytes for null characters

    Returns:
        True if likely text file
    """
    # Check extension first
    suffix = path.suffix.lower()
    if suffix in _TEXT_EXTENSIONS:
        return True
    if suffix in _BINARY_EXTENSIONS:
        # For empty files, still check content - empty files are text
        try:
            if path.stat().st_size == 0:
                return True
        except (OSError, PermissionError):
            pass
        return False

    # Check filename (no extension)
    if not suffix and path.name in {
        "README",
        "LICENSE",
        "CHANGELOG",
        "CONTRIBUTING",
        "AUTHORS",
        "Makefile",
        "CMakeLists.txt",
        "Dockerfile",
        "Vagrantfile",
        ".gitignore",
        ".gitattributes",
        ".dockerignore",
    }:
        return True

    if not check_content:
        return False

    # Check content for null bytes (binary indicator)
    try:
        with path.open("rb") as f:
            chunk = f.read(8192)
            if b"\x00" in chunk:
                return False
            # Check if mostly printable ASCII/UTF-8
            text_chars = sum(1 for b in chunk if 32 <= b <= 126 or b in (9, 10, 13))
            if len(chunk) > 0 and text_chars / len(chunk) < 0.7:
                return False
    except (OSError, PermissionError):
        return False

    return True


def get_encoding(path: Path) -> str:
    """
    Detect file encoding.

    Tries: utf-8, utf-16, latin-1
    """
    # Try UTF-8 first
    try:
        path.read_text(encoding="utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass

    # Try UTF-16
    try:
        path.read_text(encoding="utf-16")
        return "utf-16"
    except UnicodeDecodeError:
        pass

    # Fallback to latin-1 (never fails)
    return "latin-1"


# ──────────────────────────────────────────────────────────────────────────────
# CONTENT SEARCH
# ──────────────────────────────────────────────────────────────────────────────


def search_content(
    entries: list[Entry],
    text: str,
    encoding: str = "utf-8",
    case_sensitive: bool = False,
    max_file_size: int = _MAX_TEXT_FILE_SIZE,
) -> list[tuple[Entry, list[int]]]:
    """
    Search for text in files.

    Args:
        entries: List of entries to search
        text: Text to search for
        encoding: File encoding
        case_sensitive: Case sensitive search
        max_file_size: Skip files larger than this

    Returns:
        List of (Entry, [line_numbers]) tuples
    """
    results = []
    search_text = text if case_sensitive else text.lower()

    for entry in entries:
        if not entry.is_file:
            continue
        if entry.size > max_file_size:
            log_debug(f"Skipping large file: {entry.path} ({entry.size_human})")
            continue
        if not is_text_file(entry.path):
            continue

        try:
            content = entry.read_text(encoding)
            search_content = content if case_sensitive else content.lower()

            line_numbers = []
            for i, line in enumerate(search_content.splitlines(), 1):
                if search_text in line:
                    line_numbers.append(i)

            if line_numbers:
                results.append((entry, line_numbers))

        except (UnicodeDecodeError, OSError, PermissionError) as e:
            log_debug(f"Error reading {entry.path}: {e}")
            continue

    return results


def search_regex(
    entries: list[Entry],
    pattern: str,
    encoding: str = "utf-8",
    flags: int = 0,
    max_file_size: int = _MAX_TEXT_FILE_SIZE,
) -> list[tuple[Entry, list[tuple[int, str | tuple[str, ...]]]]]:
    """
    Search for regex pattern in files.

    Args:
        entries: List of entries to search
        pattern: Regex pattern
        encoding: File encoding
        flags: Regex flags (re.IGNORECASE, etc.)
        max_file_size: Skip files larger than this

    Returns:
        List of (Entry, [(line_num, matched_text)]) tuples
    """
    compiled = _compile_regex(pattern, flags)
    results = []

    for entry in entries:
        if not entry.is_file:
            continue
        if entry.size > max_file_size:
            continue
        if not is_text_file(entry.path):
            continue

        try:
            content = entry.read_text(encoding)
            matches: list[tuple[int, str | tuple[str, ...]]] = []
            for i, line in enumerate(content.splitlines(), 1):
                for match in compiled.finditer(line):
                    # Return captured groups if any, otherwise full match
                    if match.groups():
                        matches.append((i, match.groups()))
                    else:
                        matches.append((i, match.group()))
            if matches:
                results.append((entry, matches))
        except (UnicodeDecodeError, OSError, PermissionError) as e:
            log_debug(f"Error reading {entry.path}: {e}")
            continue

    return results


def search_bytes(
    entries: list[Entry],
    pattern: bytes,
    max_file_size: int = _MAX_TEXT_FILE_SIZE,
) -> list[tuple[Entry, list[int]]]:
    """
    Search for byte pattern in files (works on binary files too).

    Args:
        entries: List of entries to search
        pattern: Byte pattern to search for
        max_file_size: Skip files larger than this

    Returns:
        List of (Entry, [byte_offsets]) tuples
    """
    results = []

    for entry in entries:
        if not entry.is_file:
            continue
        if entry.size > max_file_size:
            continue

        try:
            # Use mmap for efficient searching
            with (
                entry.path.open("rb") as f,
                mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm,
            ):
                offsets = []
                start = 0
                while True:
                    pos = mm.find(pattern, start)
                    if pos == -1:
                        break
                    offsets.append(pos)
                    start = pos + 1
                if offsets:
                    results.append((entry, offsets))
        except (OSError, PermissionError, ValueError) as e:
            log_debug(f"Error searching {entry.path}: {e}")
            continue

    return results


# ──────────────────────────────────────────────────────────────────────────────
# STREAMING SEARCH (for very large files)
# ──────────────────────────────────────────────────────────────────────────────


def search_streaming(
    entries: list[Entry],
    text: str,
    encoding: str = "utf-8",
    chunk_size: int = 65536,
) -> Iterator[tuple[Entry, int, str]]:
    """
    Stream search through large files without loading entirely into memory.

    Yields:
        (Entry, line_number, matching_line)
    """
    search_bytes = text.encode(encoding)

    for entry in entries:
        if not entry.is_file:
            continue
        if not is_text_file(entry.path, check_content=False):
            continue

        try:
            with entry.path.open("rb") as f:
                line_num = 0
                buffer = b""
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        # Process remaining buffer
                        if buffer:
                            line_num += 1
                            try:
                                line = buffer.decode(encoding, errors="replace")
                                if search_bytes in buffer:
                                    yield entry, line_num, line
                            except UnicodeDecodeError:
                                pass
                        break

                    buffer += chunk
                    lines = buffer.split(b"\n")
                    buffer = lines[-1]  # Keep incomplete line

                    for line_bytes in lines[:-1]:
                        line_num += 1
                        if search_bytes in line_bytes:
                            try:
                                line = line_bytes.decode(encoding, errors="replace")
                                yield entry, line_num, line
                            except UnicodeDecodeError:
                                pass
        except (OSError, PermissionError) as e:
            log_debug(f"Error streaming {entry.path}: {e}")
            continue


# ──────────────────────────────────────────────────────────────────────────────
# CONVENIENCE FUNCTIONS
# ──────────────────────────────────────────────────────────────────────────────


def grep(
    entries: list[Entry],
    pattern: str,
    **kwargs: Any,
) -> list[tuple[Entry, list[tuple[int, str | tuple[str, ...]]]]]:
    """Alias for search_regex (grep-like)."""
    return search_regex(entries, pattern, **kwargs)


def grep_text(
    entries: list[Entry],
    text: str,
    **kwargs: Any,
) -> list[tuple[Entry, list[int]]]:
    """Alias for search_content."""
    return search_content(entries, text, **kwargs)
