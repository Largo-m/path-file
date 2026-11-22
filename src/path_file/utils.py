"""Public utility functions for path_file."""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import tempfile
from collections.abc import Generator
from datetime import timedelta
from pathlib import Path

from path_file._internal._safety import safe_path
from path_file.units import human_size, parse_duration, parse_size

# ──────────────────────────────────────────────────────────────────────────────
# SIZE & DURATION ALIASES
# ──────────────────────────────────────────────────────────────────────────────


def size(s: str | int | float) -> int:
    """Parse human-readable size to bytes. Alias for parse_size."""
    return parse_size(s)


def hsize(n: int, precision: int = 2) -> str:
    """Format bytes to human-readable. Alias for human_size."""
    return human_size(n, precision)


def duration(s: str | int | float) -> timedelta:
    """Parse human-readable duration to timedelta. Alias for parse_duration."""
    return parse_duration(s)


# ──────────────────────────────────────────────────────────────────────────────
# PATH UTILITIES
# ──────────────────────────────────────────────────────────────────────────────


def expand(path: str | Path) -> Path:
    """Expand ~ and environment variables in path."""
    return Path(os.path.expandvars(os.path.expanduser(str(path)))).resolve()


def safe_join(*parts: str | Path, base: Path | None = None) -> Path:
    """Safely join path parts, optionally restricting to base directory."""
    path = Path(*parts)
    if base:
        # Join relative to base
        path = base / path
        return safe_path(path, base)
    return path.resolve()


def mkdir(path: str | Path, mode: int = 0o755, parents: bool = True, exist_ok: bool = True) -> Path:
    """Create directory with parents. Returns the created path."""
    path = Path(path)
    path.mkdir(mode=mode, parents=parents, exist_ok=exist_ok)
    return path


def which(cmd: str) -> Path | None:
    """Find executable in PATH. Returns Path or None."""
    result = shutil.which(cmd)
    return Path(result) if result else None


def free_space(path: str | Path) -> int:
    """Get free disk space in bytes for the filesystem containing path."""
    path = Path(path)
    if os.name == "nt":
        import ctypes

        free_bytes = ctypes.c_ulonglong(0)
        ctypes.windll.kernel32.GetDiskFreeSpaceExW(str(path), None, None, ctypes.byref(free_bytes))
        return free_bytes.value
    else:
        # shutil.disk_usage uses os.statvfs(...).f_bavail * f_frsize on POSIX
        return shutil.disk_usage(path).free


def disk_usage(path: str | Path) -> tuple[int, int, int]:
    """Return (total, used, free) disk space in bytes."""
    total, used, free = shutil.disk_usage(path)
    return total, used, free


# ──────────────────────────────────────────────────────────────────────────────
# TEMPORARY DIRECTORY
# ──────────────────────────────────────────────────────────────────────────────


@contextlib.contextmanager
def tempdir(
    prefix: str = "path_file_",
    suffix: str = "",
    dir: str | Path | None = None,
) -> Generator[Path, None, None]:
    """
    Context manager for temporary directory.

    Example:
        with pf.tempdir() as tmp:
            # use tmp
            pass
        # tmp is automatically cleaned up
    """
    with tempfile.TemporaryDirectory(prefix=prefix, suffix=suffix, dir=dir) as tmp:
        yield Path(tmp)


# ──────────────────────────────────────────────────────────────────────────────
# FILE OPERATIONS
# ──────────────────────────────────────────────────────────────────────────────


def copy_file(
    src: str | Path,
    dest: str | Path,
    overwrite: bool = False,
    preserve_metadata: bool = True,
) -> Path:
    """Copy a single file."""
    src = Path(src)
    dest = Path(dest)

    if dest.exists() and not overwrite:
        raise FileExistsError(f"Destination exists: {dest}")

    dest.parent.mkdir(parents=True, exist_ok=True)

    if preserve_metadata:
        shutil.copy2(src, dest)
    else:
        shutil.copy(src, dest)

    return dest


def move_file(
    src: str | Path,
    dest: str | Path,
    overwrite: bool = False,
) -> Path:
    """Move a single file."""
    src = Path(src)
    dest = Path(dest)

    if dest.exists() and not overwrite:
        raise FileExistsError(f"Destination exists: {dest}")

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))

    return dest


def delete_file(
    path: str | Path,
    missing_ok: bool = True,
) -> bool:
    """Delete a file. Returns True if deleted, False if didn't exist."""
    path = Path(path)
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        if not missing_ok:
            raise
        return False


def delete_dir(
    path: str | Path,
    missing_ok: bool = True,
) -> bool:
    """Delete a directory and all contents. Returns True if deleted."""
    path = Path(path)
    try:
        shutil.rmtree(path)
        return True
    except FileNotFoundError:
        if not missing_ok:
            raise
        return False


def touch(path: str | Path, mode: int = 0o644, exist_ok: bool = True) -> Path:
    """Create file or update modification time."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(mode=mode, exist_ok=exist_ok)
    return path


def read_text(path: str | Path, encoding: str = "utf-8") -> str:
    """Read file as text with encoding detection fallback."""
    path = Path(path)
    try:
        return path.read_text(encoding=encoding)
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def read_bytes(path: str | Path) -> bytes:
    """Read file as bytes."""
    return Path(path).read_bytes()


def write_text(
    path: str | Path,
    data: str,
    encoding: str = "utf-8",
    atomic: bool = True,
) -> Path:
    """Write text to file (atomically by default)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if atomic:
        import tempfile

        with tempfile.NamedTemporaryFile(
            mode="w", encoding=encoding, delete=False, dir=path.parent
        ) as f:
            f.write(data)
            temp_path = Path(f.name)
        temp_path.replace(path)
    else:
        path.write_text(data, encoding=encoding)

    return path


def write_bytes(
    path: str | Path,
    data: bytes,
    atomic: bool = True,
) -> Path:
    """Write bytes to file (atomically by default)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if atomic:
        import tempfile

        with tempfile.NamedTemporaryFile(mode="wb", delete=False, dir=path.parent) as f:
            f.write(data)
            temp_path = Path(f.name)
        temp_path.replace(path)
    else:
        path.write_bytes(data)

    return path


# ──────────────────────────────────────────────────────────────────────────────
# SYMLINKS
# ──────────────────────────────────────────────────────────────────────────────


def symlink(
    target: str | Path,
    link_path: str | Path,
    target_is_directory: bool = False,
) -> Path:
    """Create symbolic link."""
    target = Path(target)
    link_path = Path(link_path)
    link_path.parent.mkdir(parents=True, exist_ok=True)
    link_path.symlink_to(target, target_is_directory=target_is_directory)
    return link_path


def readlink(path: str | Path) -> Path:
    """Read symbolic link target."""
    return Path(os.readlink(path))


def is_symlink(path: str | Path) -> bool:
    """Check if path is a symbolic link."""
    return Path(path).is_symlink()


def resolve_link(path: str | Path) -> Path:
    """Resolve all symlinks in path."""
    return Path(path).resolve()


# ──────────────────────────────────────────────────────────────────────────────
# PROCESS EXECUTION
# ──────────────────────────────────────────────────────────────────────────────


def run_command(
    cmd: list[str],
    cwd: str | Path | None = None,
    capture: bool = True,
    check: bool = True,
    env: dict[str, str] | None = None,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run command with sensible defaults."""
    # arg-list subprocess execution is the intended public API
    return subprocess.run(  # noqa: S603  # arg-list subprocess is the intended API
        cmd,
        cwd=cwd,
        capture_output=capture,
        text=True,
        check=check,
        env={**os.environ, **(env or {})},
        timeout=timeout,
    )


def run_shell(
    cmd: str,
    cwd: str | Path | None = None,
    capture: bool = True,
    check: bool = True,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run shell command."""
    # shell command strings are the intended public API
    return subprocess.run(  # noqa: S602  # shell command string is the intended API
        cmd,
        shell=True,
        cwd=cwd,
        capture_output=capture,
        text=True,
        check=check,
        timeout=timeout,
    )


# ──────────────────────────────────────────────────────────────────────────────
# PATH INFO
# ──────────────────────────────────────────────────────────────────────────────


def get_size(path: str | Path) -> int:
    """Get file or directory size in bytes."""
    path = Path(path)
    if path.is_file():
        return path.stat().st_size
    elif path.is_dir():
        total = 0
        for entry in path.rglob("*"):
            if entry.is_file():
                with contextlib.suppress(OSError, PermissionError):
                    total += entry.stat().st_size
        return total
    return 0


def get_size_human(path: str | Path) -> str:
    """Get human-readable size of file or directory."""
    return human_size(get_size(path))


def count_files(path: str | Path, pattern: str = "*") -> int:
    """Count files matching pattern in directory."""
    path = Path(path)
    if path.is_file():
        return 1 if path.match(pattern) else 0
    return len(list(path.rglob(pattern)))


def find_largest(path: str | Path, n: int = 10) -> list[Path]:
    """Find n largest files in directory."""
    path = Path(path)
    files = []
    for entry in path.rglob("*"):
        if entry.is_file():
            with contextlib.suppress(OSError, PermissionError):
                files.append((entry, entry.stat().st_size))
    files.sort(key=lambda x: -x[1])
    return [f[0] for f in files[:n]]


def find_oldest(path: str | Path, n: int = 10) -> list[Path]:
    """Find n oldest files in directory."""
    path = Path(path)
    files = []
    for entry in path.rglob("*"):
        if entry.is_file():
            with contextlib.suppress(OSError, PermissionError):
                files.append((entry, entry.stat().st_mtime))
    files.sort(key=lambda x: x[1])
    return [f[0] for f in files[:n]]


def find_newest(path: str | Path, n: int = 10) -> list[Path]:
    """Find n newest files in directory."""
    path = Path(path)
    files = []
    for entry in path.rglob("*"):
        if entry.is_file():
            with contextlib.suppress(OSError, PermissionError):
                files.append((entry, entry.stat().st_mtime))
    files.sort(key=lambda x: -x[1])
    return [f[0] for f in files[:n]]


# ──────────────────────────────────────────────────────────────────────────────
# ARCHIVE HELPERS
# ──────────────────────────────────────────────────────────────────────────────


def make_archive(
    source: str | Path,
    dest: str | Path,
    format: str = "zip",
) -> Path:
    """Create archive from directory."""
    import shutil

    source = Path(source)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    base_name = str(dest.with_suffix(""))
    shutil.make_archive(base_name, format, source)

    return dest


def extract_archive(
    archive: str | Path,
    dest: str | Path,
) -> Path:
    """Extract archive to directory."""
    import shutil

    archive = Path(archive)
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    shutil.unpack_archive(archive, dest)
    return dest


# ──────────────────────────────────────────────────────────────────────────────
# HASH HELPERS
# ──────────────────────────────────────────────────────────────────────────────


def hash_file(path: str | Path, algorithm: str = "sha256") -> str:
    """Compute file hash."""
    import hashlib

    path = Path(path)
    h = hashlib.new(algorithm)
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_hash(path: str | Path, expected: str, algorithm: str = "sha256") -> bool:
    """Verify file hash matches expected."""
    return hash_file(path, algorithm).lower() == expected.lower()


# ──────────────────────────────────────────────────────────────────────────────
# MISC
# ──────────────────────────────────────────────────────────────────────────────


def is_binary(path: str | Path) -> bool:
    """Check if file appears to be binary."""
    path = Path(path)
    try:
        with path.open("rb") as f:
            chunk = f.read(8192)
        if b"\x00" in chunk:
            return True
        text_chars = sum(1 for b in chunk if 32 <= b <= 126 or b in (9, 10, 13))
        return len(chunk) > 0 and text_chars / len(chunk) < 0.7
    except (OSError, PermissionError):
        return False


def get_mime_type(path: str | Path) -> str:
    """Get MIME type of file."""
    import mimetypes

    mimetypes.init()
    mime, _ = mimetypes.guess_type(str(path))
    return mime or "application/octet-stream"


def get_extension(path: str | Path) -> str:
    """Get file extension (lowercase)."""
    return Path(path).suffix.lower()


def strip_extension(path: str | Path) -> str:
    """Get filename without extension."""
    return Path(path).stem


def change_extension(path: str | Path, new_ext: str) -> Path:
    """Change file extension."""
    path = Path(path)
    if not new_ext.startswith("."):
        new_ext = "." + new_ext
    return path.with_suffix(new_ext)
