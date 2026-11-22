"""Archive operations: create, extract, list, compress, decompress."""

from __future__ import annotations

import bz2
import gzip
import lzma
import shutil
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from path_file._internal._log import get_logger
from path_file._internal._safety import is_subpath
from path_file.entries import Entry
from path_file.exceptions import ArchiveError

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# ARCHIVE ENTRY
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class ArchiveEntry:
    """Represents an entry in an archive."""

    name: str
    size: int
    is_dir: bool
    modified: float | None = None  # Unix timestamp
    mode: int | None = None


# ──────────────────────────────────────────────────────────────────────────────
# ARCHIVE TYPE DETECTION
# ──────────────────────────────────────────────────────────────────────────────


def detect_archive_type(path: Path) -> str:
    """
    Detect archive type from file extension and magic bytes.

    Returns:
        One of: 'zip', 'tar', 'tar.gz', 'tar.bz2', 'tar.xz', 'gz', 'bz2', 'xz', 'unknown'
    """
    suffixes = [s.lower() for s in path.suffixes]
    name = "".join(suffixes)

    # Check by extension first
    if name.endswith(".tar.gz") or name.endswith(".tgz"):
        return "tar.gz"
    if name.endswith(".tar.bz2") or name.endswith(".tbz2"):
        return "tar.bz2"
    if name.endswith(".tar.xz") or name.endswith(".txz"):
        return "tar.xz"
    if name.endswith(".tar"):
        return "tar"
    if name.endswith(".zip"):
        return "zip"
    if name.endswith(".gz"):
        return "gz"
    if name.endswith(".bz2"):
        return "bz2"
    if name.endswith(".xz"):
        return "xz"

    # Check magic bytes
    try:
        with path.open("rb") as f:
            magic = f.read(8)
    except (OSError, PermissionError):
        return "unknown"

    if (
        magic.startswith(b"PK\x03\x04")
        or magic.startswith(b"PK\x05\x06")
        or magic.startswith(b"PK\x07\x08")
    ):
        return "zip"
    if magic.startswith(b"\x1f\x8b"):
        return "gz"
    if magic.startswith(b"BZh"):
        return "bz2"
    if magic.startswith(b"\xfd7zXZ\x00"):
        return "xz"
    # tar has no magic, but we can check for ustar indicator
    if len(magic) >= 512 and magic[257:262] == b"ustar":
        return "tar"

    return "unknown"


# ──────────────────────────────────────────────────────────────────────────────
# CREATE ARCHIVE
# ──────────────────────────────────────────────────────────────────────────────


def create_archive(
    entries: list[Entry],
    dest: Path,
    format: str = "zip",
    compression: str = "deflated",
    compression_level: int = 6,
) -> None:
    """
    Create archive from entries.

    Args:
        entries: List of Entry objects to archive
        dest: Destination archive path
        format: 'zip', 'tar', 'tar.gz', 'tar.bz2', 'tar.xz'
        compression: For zip: 'stored' or 'deflated'
        compression_level: 0-9 for gzip/bz2/xz
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    format = format.lower()

    if format == "zip":
        _create_zip(entries, dest, compression, compression_level)
    elif format in ("tar", "tar.gz", "tar.bz2", "tar.xz"):
        _create_tar(entries, dest, format, compression_level)
    else:
        raise ArchiveError(f"Unsupported archive format: {format}", str(dest))


def _create_zip(
    entries: list[Entry],
    dest: Path,
    compression: str,
    level: int,
) -> None:
    """Create ZIP archive."""
    comp = zipfile.ZIP_DEFLATED if compression == "deflated" else zipfile.ZIP_STORED

    with zipfile.ZipFile(dest, "w", compression=comp, compresslevel=level) as zf:
        for entry in entries:
            if entry.is_dir:
                # Add directory entry
                arcname = str(entry.path.relative_to(entry.path.parent)) + "/"
                zf.writestr(zipfile.ZipInfo(arcname), b"")
            else:
                arcname = str(entry.path.relative_to(entry.path.parent))
                zf.write(entry.path, arcname)


def _tar_add(tf: tarfile.TarFile, entries: list[Entry]) -> None:
    """Add entries to an open tar file (arcname = entry basename)."""
    for entry in entries:
        arcname = str(entry.path.relative_to(entry.path.parent))
        tf.add(entry.path, arcname=arcname)


def _create_tar(
    entries: list[Entry],
    dest: Path,
    format: str,
    level: int,
) -> None:
    """Create TAR archive (optionally compressed)."""
    if format == "tar.gz":
        with tarfile.open(dest, "w:gz", compresslevel=level) as tf:
            _tar_add(tf, entries)
    elif format == "tar.bz2":
        with tarfile.open(dest, "w:bz2", compresslevel=level) as tf:
            _tar_add(tf, entries)
    elif format == "tar.xz":
        # lzma doesn't accept compresslevel in tarfile
        with tarfile.open(dest, "w:xz") as tf:
            _tar_add(tf, entries)
    elif format == "tar":
        with tarfile.open(dest, "w") as tf:
            _tar_add(tf, entries)
    else:
        raise ArchiveError(f"Unknown tar format: {format}", str(dest))


# ──────────────────────────────────────────────────────────────────────────────
# EXTRACT ARCHIVE
# ──────────────────────────────────────────────────────────────────────────────


def extract_archive(
    archive: Path,
    dest: Path,
    overwrite: bool = False,
    members: list[str] | None = None,
) -> list[Path]:
    """
    Extract archive to destination.

    Args:
        archive: Archive path
        dest: Destination directory
        overwrite: Overwrite existing files
        members: Specific members to extract (None = all)

    Returns:
        List of extracted paths
    """
    archive = Path(archive)
    dest = Path(dest).resolve()
    dest.mkdir(parents=True, exist_ok=True)

    archive_type = detect_archive_type(archive)
    extracted = []

    if archive_type == "zip":
        extracted = _extract_zip(archive, dest, overwrite, members)
    elif archive_type in ("tar", "tar.gz", "tar.bz2", "tar.xz"):
        extracted = _extract_tar(archive, dest, overwrite, members)
    elif archive_type in ("gz", "bz2", "xz"):
        extracted = _extract_compressed(archive, dest, overwrite)
    else:
        raise ArchiveError(f"Cannot extract unknown format: {archive_type}", str(archive))

    return extracted


def _extract_zip(
    archive: Path,
    dest: Path,
    overwrite: bool,
    members: list[str] | None,
) -> list[Path]:
    """Extract ZIP archive with path traversal protection."""
    extracted = []

    with zipfile.ZipFile(archive, "r") as zf:
        for member in zf.namelist():
            if members and member not in members:
                continue

            # Path traversal protection
            member_path = (dest / member).resolve()
            if not is_subpath(dest, member_path):
                logger.warning(f"Skipping potentially dangerous path: {member}")
                continue

            if member_path.exists() and not overwrite:
                continue

            if member.endswith("/"):
                member_path.mkdir(parents=True, exist_ok=True)
            else:
                member_path.parent.mkdir(parents=True, exist_ok=True)
                zf.extract(member, dest)

            extracted.append(member_path)

    return extracted


def _extract_tar(
    archive: Path,
    dest: Path,
    overwrite: bool,
    members: list[str] | None,
) -> list[Path]:
    """Extract TAR archive with path traversal protection."""
    extracted = []

    with tarfile.open(archive, "r:*") as tf:
        for member in tf.getmembers():
            if members and member.name not in members:
                continue

            # Path traversal protection
            member_path = (dest / member.name).resolve()
            if not is_subpath(dest, member_path):
                logger.warning(f"Skipping potentially dangerous path: {member.name}")
                continue

            if member_path.exists() and not overwrite:
                continue

            tf.extract(member, dest)
            extracted.append(member_path)

    return extracted


def _extract_compressed(
    archive: Path,
    dest: Path,
    overwrite: bool,
) -> list[Path]:
    """Extract single-file compressed archive (gz, bz2, xz)."""
    archive_type = detect_archive_type(archive)
    output_name = archive.stem  # Remove .gz, .bz2, .xz
    output_path = dest / output_name

    if output_path.exists() and not overwrite:
        return []

    if archive_type == "gz":
        with gzip.open(archive, "rb") as f_in, output_path.open("wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    elif archive_type == "bz2":
        with bz2.open(archive, "rb") as f_in, output_path.open("wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    elif archive_type == "xz":
        with lzma.open(archive, "rb") as f_in, output_path.open("wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    else:
        raise ArchiveError(f"Unknown compressed format: {archive_type}", str(archive))

    return [output_path]


# ──────────────────────────────────────────────────────────────────────────────
# LIST ARCHIVE CONTENTS
# ──────────────────────────────────────────────────────────────────────────────


def list_archive(archive: Path) -> list[ArchiveEntry]:
    """List contents of archive without extracting."""
    archive_type = detect_archive_type(archive)
    entries = []

    if archive_type == "zip":
        with zipfile.ZipFile(archive, "r") as zf:
            for info in zf.infolist():
                entries.append(
                    ArchiveEntry(
                        name=info.filename,
                        size=info.file_size,
                        is_dir=info.is_dir(),
                        modified=info.date_time and info.date_time[0] > 1980,
                    )
                )
    elif archive_type in ("tar", "tar.gz", "tar.bz2", "tar.xz"):
        with tarfile.open(archive, "r:*") as tf:
            for member in tf.getmembers():
                entries.append(
                    ArchiveEntry(
                        name=member.name,
                        size=member.size,
                        is_dir=member.isdir(),
                        modified=member.mtime,
                        mode=member.mode,
                    )
                )
    else:
        raise ArchiveError(f"Cannot list unknown format: {archive_type}", str(archive))

    return entries


# ──────────────────────────────────────────────────────────────────────────────
# COMPRESS / DECOMPRESS SINGLE FILE
# ──────────────────────────────────────────────────────────────────────────────


def compress_file(
    path: Path,
    format: str = "gz",
    level: int = 6,
    keep_original: bool = True,
) -> Path:
    """
    Compress a single file.

    Args:
        path: File to compress
        format: 'gz', 'bz2', 'xz'
        level: Compression level (0-9)
        keep_original: Don't delete original

    Returns:
        Path to compressed file
    """
    path = Path(path)
    if not path.is_file():
        raise ArchiveError("Not a file", str(path))

    format = format.lower()
    if format == "gz":
        out_path = path.with_suffix(path.suffix + ".gz")
        with path.open("rb") as f_in, gzip.open(out_path, "wb", compresslevel=level) as f_out:
            shutil.copyfileobj(f_in, f_out)
    elif format == "bz2":
        out_path = path.with_suffix(path.suffix + ".bz2")
        with path.open("rb") as f_in, bz2.open(out_path, "wb", compresslevel=level) as f_out:
            shutil.copyfileobj(f_in, f_out)
    elif format == "xz":
        out_path = path.with_suffix(path.suffix + ".xz")
        with path.open("rb") as f_in, lzma.open(out_path, "wb", preset=level) as f_out:
            shutil.copyfileobj(f_in, f_out)
    else:
        raise ArchiveError(f"Unsupported compression format: {format}", str(path))

    if not keep_original:
        path.unlink()

    return out_path


def decompress_file(
    path: Path,
    keep_original: bool = False,
) -> Path:
    """
    Decompress a single file.

    Args:
        path: Compressed file
        keep_original: Don't delete compressed file

    Returns:
        Path to decompressed file
    """
    path = Path(path)
    if not path.is_file():
        raise ArchiveError("Not a file", str(path))

    archive_type = detect_archive_type(path)
    out_path = path.with_suffix("")  # Remove compression suffix

    if out_path.exists():
        # Find unique name
        i = 1
        while out_path.exists():
            out_path = path.with_stem(f"{path.stem}_{i}")
            i += 1

    if archive_type == "gz":
        with gzip.open(path, "rb") as f_in, out_path.open("wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    elif archive_type == "bz2":
        with bz2.open(path, "rb") as f_in, out_path.open("wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    elif archive_type == "xz":
        with lzma.open(path, "rb") as f_in, out_path.open("wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    else:
        raise ArchiveError(f"Cannot decompress: {archive_type}", str(path))

    if not keep_original:
        path.unlink()

    return out_path
