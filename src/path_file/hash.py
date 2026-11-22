"""Hash computation and duplicate detection utilities."""

from __future__ import annotations

import hashlib
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from path_file._internal._log import get_logger, log_debug
from path_file.entries import Entry

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# SINGLE FILE HASHING
# ──────────────────────────────────────────────────────────────────────────────

DEFAULT_CHUNK_SIZE = 65536  # 64 KB


def hash_file(
    path: Path,
    algorithm: str = "sha256",
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> str:
    """
    Compute hash of a file.

    Args:
        path: File path
        algorithm: Hash algorithm (md5, sha1, sha256, sha512, blake2b, blake2s)
        chunk_size: Read chunk size in bytes

    Returns:
        Hex digest string

    Raises:
        HashError: If file cannot be read
    """
    try:
        h = hashlib.new(algorithm)
    except ValueError as e:
        from path_file.exceptions import HashError

        raise HashError(str(path), f"Unknown algorithm: {algorithm}") from e

    try:
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                h.update(chunk)
    except (OSError, PermissionError) as e:
        from path_file.exceptions import HashError

        raise HashError(str(path), f"Cannot read file: {e}") from e

    return h.hexdigest()


def hash_file_fast(
    path: Path,
    algorithm: str = "sha256",
    sample_size: int = 4096,
) -> str:
    """
    Fast hash using only first N bytes (for quick duplicate detection).

    Not cryptographically secure - use for preliminary filtering only.
    """
    try:
        h = hashlib.new(algorithm)
        with path.open("rb") as f:
            h.update(f.read(sample_size))
        return h.hexdigest()
    except (OSError, PermissionError, ValueError) as e:
        from path_file.exceptions import HashError

        raise HashError(str(path), f"Fast hash failed: {e}") from e


# ──────────────────────────────────────────────────────────────────────────────
# BATCH HASHING
# ──────────────────────────────────────────────────────────────────────────────


def hash_files(
    entries: list[Entry],
    algorithm: str = "sha256",
    parallel: bool = True,
    workers: int = 8,
    progress: Callable[[int, int], None] | None = None,
) -> dict[Path, str]:
    """
    Compute hashes for multiple files.

    Args:
        entries: List of Entry objects (only files are hashed)
        algorithm: Hash algorithm
        parallel: Use thread pool
        workers: Number of worker threads
        progress: Optional callback(current, total)

    Returns:
        Dict mapping Path -> hash string
    """
    files = [e for e in entries if e.is_file]
    results: dict[Path, str] = {}
    lock = threading.Lock()
    completed = 0

    def hash_one(entry: Entry) -> tuple[Path, str]:
        return entry.path, hash_file(entry.path, algorithm)

    if parallel and len(files) > 1:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(hash_one, e): e for e in files}
            for future in as_completed(futures):
                try:
                    path, hash_val = future.result()
                    with lock:
                        results[path] = hash_val
                        completed += 1
                        if progress:
                            progress(completed, len(files))
                except Exception as e:
                    entry = futures[future]
                    log_debug(f"Hash failed for {entry.path}: {e}")
    else:
        for entry in files:
            try:
                results[entry.path] = hash_file(entry.path, algorithm)
                completed += 1
                if progress:
                    progress(completed, len(files))
            except Exception as e:
                log_debug(f"Hash failed for {entry.path}: {e}")

    return results


# ──────────────────────────────────────────────────────────────────────────────
# DUPLICATE DETECTION
# ──────────────────────────────────────────────────────────────────────────────


def find_duplicates(
    entries: list[Entry],
    algorithm: str = "sha256",
    parallel: bool = True,
    workers: int = 8,
    min_size: int = 1,
) -> dict[str, list[Entry]]:
    """
    Find duplicate files by content hash.

    Args:
        entries: List of Entry objects
        algorithm: Hash algorithm
        parallel: Use parallel hashing
        workers: Worker threads
        min_size: Minimum file size to consider (bytes)

    Returns:
        Dict mapping hash -> list of duplicate Entries (only groups with 2+ files)
    """
    # Filter files by minimum size
    files = [e for e in entries if e.is_file and e.size >= min_size]

    if len(files) < 2:
        return {}

    # Quick pass: group by size first
    by_size: dict[int, list[Entry]] = {}
    for f in files:
        by_size.setdefault(f.size, []).append(f)

    # Only hash groups with same size
    candidates = []
    for size, group in by_size.items():
        if len(group) > 1:
            candidates.extend(group)

    if not candidates:
        return {}

    # Hash candidates
    hashes = hash_files(candidates, algorithm, parallel, workers)

    # Group by hash
    by_hash: dict[str, list[Entry]] = {}
    for entry in candidates:
        h = hashes.get(entry.path)
        if h:
            by_hash.setdefault(h, []).append(entry)

    # Return only duplicates (2+ files with same hash)
    return {h: group for h, group in by_hash.items() if len(group) > 1}


def find_duplicates_quick(
    entries: list[Entry],
    sample_size: int = 4096,
) -> dict[tuple[int, str], list[Entry]]:
    """
    Quick duplicate detection using (size, partial_hash) as key.

    Much faster but may have false positives (same size + same prefix).
    Use find_duplicates() for confirmation.

    Returns:
        Dict mapping (size, partial_hash) -> list of Entries
    """
    files = [e for e in entries if e.is_file]
    by_key: dict[tuple[int, str], list[Entry]] = {}

    for entry in files:
        try:
            partial = hash_file_fast(entry.path, "sha256", sample_size)
            key = (entry.size, partial)
            by_key.setdefault(key, []).append(entry)
        except Exception:
            continue

    return {k: v for k, v in by_key.items() if len(v) > 1}


def find_duplicates_by_name(entries: list[Entry]) -> dict[str, list[Entry]]:
    """Find files with same name (regardless of content)."""
    by_name: dict[str, list[Entry]] = {}
    for e in entries:
        if e.is_file:
            by_name.setdefault(e.name.lower(), []).append(e)
    return {k: v for k, v in by_name.items() if len(v) > 1}


# ──────────────────────────────────────────────────────────────────────────────
# HASH VERIFICATION
# ──────────────────────────────────────────────────────────────────────────────


def verify_hash(
    path: Path,
    expected_hash: str,
    algorithm: str = "sha256",
) -> bool:
    """Verify file matches expected hash."""
    try:
        actual = hash_file(path, algorithm)
        return actual.lower() == expected_hash.lower()
    except Exception:
        return False


def verify_hashes(
    file_hashes: dict[Path, str],
    algorithm: str = "sha256",
    parallel: bool = True,
    workers: int = 8,
) -> dict[Path, bool]:
    """Verify multiple files against expected hashes."""
    results: dict[Path, bool] = {}

    def verify_one(path: Path, expected: str) -> tuple[Path, bool]:
        return path, verify_hash(path, expected, algorithm)

    if parallel and len(file_hashes) > 1:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(verify_one, p, h): p for p, h in file_hashes.items()}
            for future in as_completed(futures):
                path, ok = future.result()
                results[path] = ok
    else:
        for path, expected in file_hashes.items():
            results[path] = verify_hash(path, expected, algorithm)

    return results


# ──────────────────────────────────────────────────────────────────────────────
# CHECKSUM FILES
# ──────────────────────────────────────────────────────────────────────────────


def write_checksums(
    entries: list[Entry],
    output: Path,
    algorithm: str = "sha256",
    format: str = "md5sum",  # or "sha256sum", "b2sum"
) -> None:
    """
    Write checksums to file in standard format.

    Format: hash *path (one per line)
    """
    files = [e for e in entries if e.is_file]
    hashes = hash_files(files, algorithm)

    lines = []
    for entry in files:
        h = hashes.get(entry.path)
        if h:
            # Use relative path if possible
            try:
                rel_path = entry.path.relative_to(output.parent)
                path_str = str(rel_path)
            except ValueError:
                path_str = str(entry.path)
            lines.append(f"{h} *{path_str}")

    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_checksums(
    checksum_file: Path,
) -> dict[Path, str]:
    """
    Read checksums from file.

    Supports: md5sum, sha256sum, b2sum formats
    """
    result = {}
    content = checksum_file.read_text(encoding="utf-8")

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 2)
        if len(parts) >= 2:
            hash_val = parts[0]
            # Path may have leading * or space
            path_str = parts[1].lstrip("* ")
            result[Path(path_str)] = hash_val

    return result
