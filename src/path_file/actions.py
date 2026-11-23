"""Action executors for FileChain operations."""

from __future__ import annotations

import hashlib
import re
import shutil
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import IO, Any

from path_file._internal._log import get_logger, log_debug, log_info
from path_file._internal._safety import (
    require_confirm_or_dry_run,
    validate_dest,
)
from path_file.archive import (
    compress_file,
    create_archive,
    extract_archive,
)
from path_file.chain import FileChain
from path_file.entries import ActionResult, Entry
from path_file.exceptions import (
    PathflowError,
)

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# MAIN EXECUTION ENTRY POINT
# ──────────────────────────────────────────────────────────────────────────────


def execute_action(chain: FileChain) -> ActionResult:
    """
    Execute the pending action on a FileChain.

    This is the main entry point called by FileChain.execute().
    """
    action_name = chain._action_name
    params = dict(chain._action_params)  # Make a copy
    pos_args = params.pop("_args", ())

    if not action_name:
        raise PathflowError("No action specified")

    # Special handling for archive_to - creates single archive from all entries
    if action_name == "archive_to":
        return _execute_archive_to(chain, params, pos_args)

    # Map action name to executor
    executors: dict[str, Callable[..., Any]] = {
        "copy_to": _action_copy,
        "move_to": _action_move,
        "delete": _action_delete,
        "trash": _action_trash,
        "rename": _action_rename,
        "rename_with": _action_rename_with,
        "compress": _action_compress,
        "extract_to": _action_extract_to,
        "chmod": _action_chmod,
        "touch": _action_touch,
        "read_text": _action_read_text,
        "read_bytes": _action_read_bytes,
        "write_text": _action_write_text,
        "write_bytes": _action_write_bytes,
        "hash": _action_hash,
        "open": _action_open,
        "create_dir": _action_create_dir,
        "symlink_to": _action_symlink_to,
    }

    executor = executors.get(action_name)
    if not executor:
        raise PathflowError(f"Unknown action: {action_name}")

    # Get entries to process
    entries = chain._materialize()
    if not entries:
        # create_dir/touch are useful on paths that do not exist yet
        if action_name in ("create_dir", "touch", "symlink_to") and not chain._dry_run:
            root = chain._source
            if isinstance(root, (str, Path)) and not Path(root).exists():
                target = Path(root)
                if action_name == "create_dir":
                    target.mkdir(parents=True, exist_ok=True)
                    return ActionResult(action=action_name, count=1)
                if action_name == "touch":
                    target.touch()
                    return ActionResult(action=action_name, count=1)
                link_target = pos_args[0] if pos_args else params.get("target")
                if link_target is not None:
                    target.symlink_to(Path(link_target))
                    return ActionResult(action=action_name, count=1)
        log_info(f"No files to {action_name}")
        return ActionResult(action=action_name, count=0, dry_run=chain._dry_run or False)

    # Determine dry_run mode
    dry_run = chain._dry_run
    if dry_run is None:
        # Default: dry_run for most destructive ops, but delete/trash require explicit confirm
        dry_run = action_name in ("move_to", "rename", "chmod", "write_text", "write_bytes")

    # Confirm destructive operations - delete/trash require explicit confirm
    if action_name in ("delete", "trash"):
        if dry_run:
            # In dry_run mode, no confirm needed
            pass
        else:
            # Not in dry_run - require confirm
            require_confirm_or_dry_run(
                action_name,
                len(entries),
                sum(e.size for e in entries),
                params.get("confirm", False),
                dry_run,
            )

    # Progress bar setup
    progress_bar = None
    if chain._progress and entries:
        from path_file.progress import ProgressBar

        progress_bar = ProgressBar(len(entries), prefix=f"{action_name}: ")
        progress_bar.__enter__()

    try:
        # Remove dry_run from params if present (passed explicitly)
        params.pop("dry_run", None)

        # Execute based on parallel setting
        if chain._parallel > 1 and action_name not in ("read_text", "read_bytes", "hash", "open"):
            result = _execute_parallel(
                executor,
                entries,
                params,
                chain._parallel,
                chain._on_error,
                dry_run,
                action_name,
                progress_bar,
                chain._verbose,
                pos_args,
            )
        else:
            result = _execute_sequential(
                executor,
                entries,
                params,
                chain._on_error,
                dry_run,
                action_name,
                progress_bar,
                chain._verbose,
                pos_args,
            )

        if progress_bar:
            progress_bar.finish()
            progress_bar.__exit__(None, None, None)

        return result

    except Exception as e:
        if progress_bar:
            progress_bar.__exit__(type(e), e, e.__traceback__)
        raise


# ──────────────────────────────────────────────────────────────────────────────
# EXECUTION HELPERS
# ──────────────────────────────────────────────────────────────────────────────


def _execute_sequential(
    executor: Callable[..., Any],
    entries: list[Entry],
    params: dict[str, Any],
    on_error: str,
    dry_run: bool,
    action_name: str,
    progress_bar: Any,
    verbose: bool,
    pos_args: tuple[Any, ...] = (),
) -> ActionResult:
    """Execute action sequentially."""
    errors: list[tuple[Path, Exception]] = []
    count = 0
    total_size = 0
    skipped = 0

    for entry in entries:
        try:
            if verbose:
                log_info(f"{action_name}: {entry.path}")

            executor(entry, *pos_args, dry_run=dry_run, **params)
            count += 1
            if hasattr(entry, "size"):
                total_size += entry.size

            if progress_bar:
                progress_bar.update(1)

        except Exception as e:
            if on_error == "raise":
                raise
            elif on_error == "collect":
                errors.append((entry.path, e))
                skipped += 1
            else:  # skip
                skipped += 1
                log_debug(f"Skipped {entry.path}: {e}")

            if progress_bar:
                progress_bar.update(1)

    return ActionResult(
        action=action_name,
        count=count,
        total_size=total_size,
        duration=0.0,  # Will be set by caller
        errors=errors,
        skipped=skipped,
        dry_run=dry_run,
    )


def _execute_parallel(
    executor: Callable[..., Any],
    entries: list[Entry],
    params: dict[str, Any],
    workers: int,
    on_error: str,
    dry_run: bool,
    action_name: str,
    progress_bar: Any,
    verbose: bool,
    pos_args: tuple[Any, ...] = (),
) -> ActionResult:
    """Execute action in parallel using thread pool."""
    errors: list[tuple[Path, Exception]] = []
    count = 0
    total_size = 0
    skipped = 0
    lock = threading.Lock()

    def process_entry(entry: Entry) -> tuple[bool, int, Exception | None]:
        """Process single entry, return (success, size, error)."""
        try:
            if verbose:
                log_info(f"{action_name}: {entry.path}")
            executor(entry, *pos_args, dry_run=dry_run, **params)
            return True, entry.size if entry.is_file else 0, None
        except Exception as e:
            return False, 0, e

    with ThreadPoolExecutor(max_workers=workers) as executor_pool:
        futures = {executor_pool.submit(process_entry, entry): entry for entry in entries}

        for future in as_completed(futures):
            entry = futures[future]
            try:
                success, size, error = future.result()
                if success:
                    with lock:
                        count += 1
                        total_size += size
                else:
                    with lock:
                        if error is not None:
                            if on_error == "collect":
                                errors.append((entry.path, error))
                            skipped += 1
                            if on_error == "raise":
                                raise error
            except Exception as e:
                if on_error == "raise":
                    raise
                with lock:
                    if on_error == "collect":
                        errors.append((entry.path, e))
                    skipped += 1

            if progress_bar:
                progress_bar.update(1)

    return ActionResult(
        action=action_name,
        count=count,
        total_size=total_size,
        duration=0.0,
        errors=errors,
        skipped=skipped,
        dry_run=dry_run,
    )


def _execute_archive_to(
    chain: FileChain, params: dict[str, Any], pos_args: tuple[Any, ...]
) -> ActionResult:
    """Execute archive_to action - creates single archive from all entries."""

    entries = chain._materialize()
    if not entries:
        return ActionResult(action="archive_to", count=0, dry_run=chain._dry_run or False)

    dry_run = chain._dry_run
    if dry_run is None:
        dry_run = False  # archive is not destructive

    if dry_run:
        return ActionResult(action="archive_to", count=len(entries), dry_run=True)

    archive_path = pos_args[0] if pos_args else params.get("archive_path")
    if not archive_path:
        raise PathflowError("archive_to requires destination archive path")

    format = params.get("format", "zip")
    compression = params.get("compression", "deflated")
    compression_level = params.get("compression_level", 6)

    create_archive(entries, Path(archive_path), format, compression, compression_level)

    total_size = sum(e.size for e in entries if e.is_file)
    return ActionResult(
        action="archive_to",
        count=len(entries),
        total_size=total_size,
        dry_run=False,
    )


# ──────────────────────────────────────────────────────────────────────────────
# INDIVIDUAL ACTION EXECUTORS
# ──────────────────────────────────────────────────────────────────────────────


def _action_copy(
    entry: Entry,
    dest: str | Path,
    overwrite: bool = False,
    preserve_metadata: bool = True,
    create_dest: bool = True,
    dry_run: bool = False,
    **kwargs: Any,
) -> None:
    """Copy file or directory to destination.

    If dest is an existing directory (or parent exists and dest doesn't),
    copy the file into that directory preserving the filename.
    """
    if dry_run:
        return

    dest = Path(dest)

    # If dest is an existing directory, or parent exists but dest doesn't,
    # treat dest as a directory and copy file into it
    if dest.exists() and dest.is_dir():
        target = dest / entry.path.name
    elif not dest.exists() and dest.parent.exists():
        # Dest doesn't exist but parent does - treat as directory target
        target = dest / entry.path.name
    else:
        target = dest

    validate_dest(target, create=create_dest, overwrite=overwrite)

    if entry.is_dir:
        shutil.copytree(entry.path, target, dirs_exist_ok=overwrite)
        if preserve_metadata:
            shutil.copystat(entry.path, target)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(entry.path, target) if preserve_metadata else shutil.copy(entry.path, target)


def _action_move(
    entry: Entry,
    dest: str | Path,
    overwrite: bool = False,
    create_dest: bool = True,
    dry_run: bool = False,
    **kwargs: Any,
) -> None:
    """Move file or directory to destination.

    If dest is an existing directory, move the file into that directory.
    """
    if dry_run:
        return

    dest = Path(dest)

    # If dest is an existing directory, move into it
    if (dest.exists() and dest.is_dir()) or (not dest.exists() and dest.parent.exists()):
        target = dest / entry.path.name
    else:
        target = dest

    validate_dest(target, create=create_dest, overwrite=overwrite)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(entry.path), str(target))


def _action_delete(
    entry: Entry,
    dry_run: bool = True,
    confirm: bool = False,
    **kwargs: Any,
) -> None:
    """Delete file or directory (permanent)."""
    if dry_run:
        return

    if entry.is_dir:
        shutil.rmtree(entry.path)
    else:
        entry.path.unlink()


def _action_trash(
    entry: Entry,
    dry_run: bool = True,
    confirm: bool = False,
    **kwargs: Any,
) -> None:
    """Move file or directory to OS recycle bin/trash."""
    if dry_run:
        return

    try:
        import send2trash

        send2trash.send2trash(str(entry.path))
    except ImportError:
        # Fallback: move to ~/.local/share/Trash or Windows Recycle Bin
        _move_to_trash_fallback(entry.path)


def _move_to_trash_fallback(path: Path) -> None:
    """Fallback trash implementation without send2trash."""
    import platform

    system = platform.system()

    if system == "Windows":
        # Use Windows Shell API via ctypes
        try:
            import ctypes
            from ctypes import wintypes

            # Win32 SHFileOperation flag values (kept uppercase-free per PEP 8)
            fo_delete = 3
            fof_allowundo = 0x40
            fof_noconfirmation = 0x10
            fof_silent = 0x4
            fof_noerrorui = 0x400

            class SHFILEOPSTRUCT(ctypes.Structure):
                _fields_ = [
                    ("hwnd", wintypes.HWND),
                    ("wFunc", wintypes.UINT),
                    ("pFrom", wintypes.LPCWSTR),
                    ("pTo", wintypes.LPCWSTR),
                    ("fFlags", wintypes.USHORT),
                    ("fAnyOperationsAborted", wintypes.BOOL),
                    ("hNameMappings", wintypes.LPVOID),
                    ("lpszProgressTitle", wintypes.LPCWSTR),
                ]

            sh_file_operation = ctypes.windll.shell32.SHFileOperationW
            sh_file_operation.argtypes = [ctypes.POINTER(SHFILEOPSTRUCT)]
            sh_file_operation.restype = wintypes.INT

            op = SHFILEOPSTRUCT()
            op.wFunc = fo_delete
            op.pFrom = str(path.resolve()) + "\0\0"
            op.fFlags = fof_allowundo | fof_noconfirmation | fof_silent | fof_noerrorui
            result = sh_file_operation(ctypes.byref(op))
            if result != 0:
                raise OSError(f"SHFileOperation failed with code {result}")
            return
        except Exception as exc:
            logger.debug("Recycle bin via SHFileOperation unavailable: %s", exc)

    # Linux/macOS fallback: ~/.local/share/Trash
    trash_dir = Path.home() / ".local" / "share" / "Trash" / "files"
    trash_dir.mkdir(parents=True, exist_ok=True)
    dest = trash_dir / path.name
    counter = 1
    while dest.exists():
        stem = path.stem
        suffix = path.suffix
        dest = trash_dir / f"{stem} ({counter}){suffix}"
        counter += 1
    shutil.move(str(path), str(dest))


def _action_rename(
    entry: Entry,
    pattern: str,
    dry_run: bool = False,
    **kwargs: Any,
) -> None:
    """
    Rename file using pattern.
    Pattern supports: {name}, {stem}, {suffix}, {n}, {n:04d}, {date}, {date:%Y-%m-%d}
    """
    if dry_run:
        return

    # Simple pattern substitution
    # For more complex patterns, use rename_with
    new_name = pattern
    new_name = new_name.replace("{name}", entry.name)
    new_name = new_name.replace("{stem}", entry.stem)
    new_name = new_name.replace("{suffix}", entry.suffix)
    new_name = new_name.replace("{date}", datetime.now().strftime("%Y-%m-%d"))

    # Handle {n:04d} style
    def repl(match: re.Match[str]) -> str:
        # This is a simple implementation - in real use, you'd track counter
        return "0001"  # Placeholder

    new_name = re.sub(r"\{n(?::([^}]+))?\}", repl, new_name)

    new_path = entry.path.parent / new_name
    validate_dest(new_path, overwrite=False)
    entry.path.rename(new_path)


def _action_rename_with(
    entry: Entry,
    func: Callable[[str], str],
    dry_run: bool = False,
    **kwargs: Any,
) -> None:
    """Rename using a function: func(stem) -> new_stem."""
    if dry_run:
        return

    new_stem = func(entry.stem)
    new_name = new_stem + entry.suffix
    new_path = entry.path.parent / new_name
    validate_dest(new_path, overwrite=False)
    entry.path.rename(new_path)


def _action_archive_to(
    entry: Entry,
    archive_path: str | Path,
    format: str = "zip",
    compression: str = "deflated",
    dry_run: bool = False,
    **kwargs: Any,
) -> None:
    """Add entry to archive."""
    if dry_run:
        return

    # This is handled by the archive module at chain level
    # Single entry archive not typical - use chain.archive_to()
    raise PathflowError("Use chain.archive_to() for archiving multiple files")


def _action_compress(
    entry: Entry,
    format: str = "gz",
    dry_run: bool = False,
    **kwargs: Any,
) -> None:
    """Compress file."""
    if dry_run:
        return

    if not entry.is_file:
        raise PathflowError(f"Cannot compress directory: {entry.path}")

    compress_file(entry.path, format)


def _action_extract_to(
    entry: Entry,
    dest: str | Path,
    dry_run: bool = False,
    **kwargs: Any,
) -> None:
    """Extract archive to destination."""
    if dry_run:
        return

    if not entry.is_file:
        raise PathflowError(f"Cannot extract directory: {entry.path}")

    extract_archive(entry.path, Path(dest))


def _action_chmod(
    entry: Entry,
    mode: int | str,
    dry_run: bool = False,
    **kwargs: Any,
) -> None:
    """Change file permissions."""
    if dry_run:
        return

    if isinstance(mode, str):
        mode = int(mode, 8)

    entry.path.chmod(mode)


def _action_touch(
    entry: Entry,
    dry_run: bool = False,
    **kwargs: Any,
) -> None:
    """Update modification time (create if not exists)."""
    if dry_run:
        return

    entry.path.touch(exist_ok=True)


def _action_read_text(
    entry: Entry,
    encoding: str = "utf-8",
    dry_run: bool = False,
    **kwargs: Any,
) -> str:
    """Read file as text."""
    return entry.read_text(encoding)


def _action_read_bytes(
    entry: Entry,
    dry_run: bool = False,
    **kwargs: Any,
) -> bytes:
    """Read file as bytes."""
    return entry.read_bytes()


def _action_write_text(
    entry: Entry,
    data: str,
    encoding: str = "utf-8",
    dry_run: bool = False,
    **kwargs: Any,
) -> None:
    """Write text to file."""
    if dry_run:
        return

    entry.path.write_text(data, encoding=encoding)


def _action_write_bytes(
    entry: Entry,
    data: bytes,
    dry_run: bool = False,
    **kwargs: Any,
) -> None:
    """Write bytes to file."""
    if dry_run:
        return

    entry.path.write_bytes(data)


def _action_hash(
    entry: Entry,
    algorithm: str = "sha256",
    dry_run: bool = False,
    **kwargs: Any,
) -> str:
    """Compute file hash."""
    if not entry.is_file:
        return ""

    if dry_run:
        return ""

    h = hashlib.new(algorithm)
    with entry.path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _action_open(
    entry: Entry,
    mode: str = "r",
    dry_run: bool = False,
    **kwargs: Any,
) -> IO[Any]:
    """Open file."""
    if dry_run:
        # Return a dummy file-like object
        import io

        return io.StringIO()

    return entry.path.open(mode)


def _action_create_dir(
    entry: Entry,
    mode: int = 0o755,
    dry_run: bool = False,
    **kwargs: Any,
) -> None:
    """Create directory (for dir entries)."""
    if dry_run:
        return

    entry.path.mkdir(mode=mode, parents=True, exist_ok=True)


def _action_symlink_to(
    entry: Entry,
    target: str | Path,
    dry_run: bool = False,
    **kwargs: Any,
) -> None:
    """Create symlink at entry pointing to target."""
    if dry_run:
        return

    target = Path(target)
    entry.path.symlink_to(target)


# ──────────────────────────────────────────────────────────────────────────────
# CHAIN-LEVEL ACTIONS (operate on all entries)
# ──────────────────────────────────────────────────────────────────────────────


def action_copy(chain: FileChain, dest: str | Path, **kwargs: Any) -> FileChain:
    """Copy all entries to destination directory."""
    return chain._with_config(action_name="copy_to", action_params={"dest": dest, **kwargs})


def action_move(chain: FileChain, dest: str | Path, **kwargs: Any) -> FileChain:
    """Move all entries to destination directory."""
    return chain._with_config(action_name="move_to", action_params={"dest": dest, **kwargs})


def action_delete(chain: FileChain, **kwargs: Any) -> FileChain:
    """Delete all entries."""
    return chain._with_config(action_name="delete", action_params=kwargs)


def action_trash(chain: FileChain, **kwargs: Any) -> FileChain:
    """Move all entries to trash."""
    return chain._with_config(action_name="trash", action_params=kwargs)


def action_rename(chain: FileChain, pattern: str, **kwargs: Any) -> FileChain:
    """Rename all entries using pattern."""
    return chain._with_config(action_name="rename", action_params={"pattern": pattern, **kwargs})


def action_rename_with(chain: FileChain, func: Callable[[str], str], **kwargs: Any) -> FileChain:
    """Rename all entries using function."""
    return chain._with_config(action_name="rename_with", action_params={"func": func, **kwargs})


def action_archive_to(
    chain: FileChain,
    archive_path: str | Path,
    format: str = "zip",
    compression: str = "deflated",
    **kwargs: Any,
) -> FileChain:
    """Archive all entries to a single archive."""
    return chain._with_config(
        action_name="archive_to",
        action_params={
            "archive_path": archive_path,
            "format": format,
            "compression": compression,
            **kwargs,
        },
    )


def action_compress(chain: FileChain, format: str = "gz", **kwargs: Any) -> FileChain:
    """Compress each entry individually."""
    return chain._with_config(action_name="compress", action_params={"format": format, **kwargs})


def action_extract_to(chain: FileChain, dest: str | Path, **kwargs: Any) -> FileChain:
    """Extract all archive entries to destination."""
    return chain._with_config(action_name="extract_to", action_params={"dest": dest, **kwargs})


def action_chmod(chain: FileChain, mode: int | str, **kwargs: Any) -> FileChain:
    """Change permissions of all entries."""
    return chain._with_config(action_name="chmod", action_params={"mode": mode, **kwargs})


def action_touch(chain: FileChain, **kwargs: Any) -> FileChain:
    """Touch all entries."""
    return chain._with_config(action_name="touch", action_params=kwargs)


def action_read_text(chain: FileChain, encoding: str = "utf-8", **kwargs: Any) -> FileChain:
    """Read all entries as text."""
    return chain._with_config(
        action_name="read_text", action_params={"encoding": encoding, **kwargs}
    )


def action_read_bytes(chain: FileChain, **kwargs: Any) -> FileChain:
    """Read all entries as bytes."""
    return chain._with_config(action_name="read_bytes", action_params=kwargs)


def action_write_text(chain: FileChain, data: str, **kwargs: Any) -> FileChain:
    """Write same data to all entries."""
    return chain._with_config(action_name="write_text", action_params={"data": data, **kwargs})


def action_write_bytes(chain: FileChain, data: bytes, **kwargs: Any) -> FileChain:
    """Write same bytes to all entries."""
    return chain._with_config(action_name="write_bytes", action_params={"data": data, **kwargs})


def action_hash(chain: FileChain, algorithm: str = "sha256", **kwargs: Any) -> FileChain:
    """Compute hash for all entries."""
    return chain._with_config(action_name="hash", action_params={"algorithm": algorithm, **kwargs})


def action_open(chain: FileChain, mode: str = "r", **kwargs: Any) -> FileChain:
    """Open all entries."""
    return chain._with_config(action_name="open", action_params={"mode": mode, **kwargs})


def action_create_dir(chain: FileChain, mode: int = 0o755, **kwargs: Any) -> FileChain:
    """Create directories for all entries."""
    return chain._with_config(action_name="create_dir", action_params={"mode": mode, **kwargs})


def action_symlink_to(chain: FileChain, target: str | Path, **kwargs: Any) -> FileChain:
    """Create symlinks for all entries pointing to target."""
    return chain._with_config(action_name="symlink_to", action_params={"target": target, **kwargs})
