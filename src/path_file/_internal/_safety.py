"""Safety utilities for destructive operations."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from types import TracebackType

from path_file.exceptions import DestExistsError, DryRunRequiredError, PathflowError
from path_file.units import human_size

# ──────────────────────────────────────────────────────────────────────────────
# DESTRUCTIVE OPERATION CONFIRMATION
# ──────────────────────────────────────────────────────────────────────────────


def confirm_destructive(
    action: str,
    count: int,
    total_size: int,
    force: bool = False,
    dry_run: bool | None = None,
) -> bool:
    """
    Confirm a destructive operation.

    Args:
        action: Action name (delete, move, etc.)
        count: Number of files affected
        total_size: Total size in bytes
        force: Skip confirmation (use with caution)
        dry_run: If True, operation is dry-run (no confirmation needed)

    Returns:
        True if confirmed, False otherwise

    Raises:
        DryRunRequiredError: If not confirmed and not dry-run
    """
    if dry_run:
        return True

    if force:
        return True

    if count == 0:
        return True

    # Non-interactive environment (CI, scripts) - require explicit confirm
    if not sys.stdin.isatty():
        raise DryRunRequiredError(
            action, count, "Non-interactive environment: use confirm=True or dry_run=True"
        )

    # Interactive confirmation
    size_str = human_size(total_size)
    prompt = (
        f"\n⚠️  About to {action} {count} file(s) ({size_str}).\n"
        f"    This operation cannot be undone.\n"
        f"    Type 'yes' to confirm: "
    )

    try:
        response = input(prompt).strip().lower()
        return response in ("yes", "y")
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.")
        return False


def require_confirm_or_dry_run(
    action: str,
    count: int,
    total_size: int,
    confirm: bool,
    dry_run: bool,
) -> None:
    """
    Validate that either confirm=True or dry_run=True for destructive ops.

    Raises:
        DryRunRequiredError: If neither confirm nor dry_run is True
    """
    if not confirm and not dry_run and count > 0:
        raise DryRunRequiredError(action, count)


# ──────────────────────────────────────────────────────────────────────────────
# DESTINATION VALIDATION
# ──────────────────────────────────────────────────────────────────────────────


def validate_dest(
    dest: str | Path,
    create: bool = True,
    overwrite: bool = False,
) -> Path:
    """
    Validate and prepare destination path.

    Args:
        dest: Destination path
        create: Create parent directories if they don't exist
        overwrite: Allow overwriting existing destination

    Returns:
        Resolved destination Path

    Raises:
        DestExistsError: If destination exists and overwrite=False
        PathflowError: If destination is invalid
    """
    dest = Path(dest).resolve()

    if dest.exists():
        if not overwrite:
            raise DestExistsError(str(dest), "Use overwrite=True to replace existing destination")
        # Remove existing
        if dest.is_dir():
            shutil.rmtree(dest)
        else:
            dest.unlink()

    if create:
        dest.parent.mkdir(parents=True, exist_ok=True)

    return dest


def validate_source(source: str | Path) -> Path:
    """
    Validate source path exists.

    Returns:
        Resolved source Path

    Raises:
        FileNotFoundError: If source doesn't exist
    """
    source = Path(source).resolve()
    if not source.exists():
        from path_file.exceptions import FileNotFoundError

        raise FileNotFoundError(str(source), "Check the path exists and you have read permissions")
    return source


# ──────────────────────────────────────────────────────────────────────────────
# PATH SAFETY
# ──────────────────────────────────────────────────────────────────────────────


def safe_path(path: str | Path, base: Path | None = None) -> Path:
    """
    Resolve and validate path for safety.

    Args:
        path: Path to validate
        base: Optional base directory to restrict to (sandbox mode)

    Returns:
        Resolved absolute Path

    Raises:
        PathflowError: If path tries to escape base directory
    """
    path = Path(path).resolve()

    if base is not None:
        base = Path(base).resolve()
        try:
            path.relative_to(base)
        except ValueError:
            raise PathflowError(
                f"Path {path} escapes base directory {base}",
                "Operation not allowed: path traversal detected",
            ) from None

    return path


def is_subpath(parent: Path, child: Path) -> bool:
    """Check if child is a subpath of parent."""
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def is_same_file(path1: Path, path2: Path) -> bool:
    """Check if two paths refer to the same file (handles symlinks)."""
    try:
        return path1.resolve().samefile(path2.resolve())
    except (OSError, PermissionError):
        return False


# ──────────────────────────────────────────────────────────────────────────────
# BACKUP & RESTORE
# ──────────────────────────────────────────────────────────────────────────────


class BackupManager:
    """Manage backups for safe operations."""

    def __init__(self, backup_dir: Path | None = None) -> None:
        self.backup_dir = backup_dir or Path.home() / ".path_file" / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self._backups: list[tuple[Path, Path]] = []  # (original, backup)

    def backup(self, path: Path) -> Path:
        """Create a backup of a file/directory."""
        import uuid

        backup_name = f"{path.name}.{uuid.uuid4().hex[:8]}.bak"
        backup_path = self.backup_dir / backup_name

        if path.is_dir():
            shutil.copytree(path, backup_path)
        else:
            shutil.copy2(path, backup_path)

        self._backups.append((path, backup_path))
        return backup_path

    def restore_all(self) -> None:
        """Restore all backups."""
        for original, backup in reversed(self._backups):
            if backup.exists():
                if original.exists():
                    if original.is_dir():
                        shutil.rmtree(original)
                    else:
                        original.unlink()
                if backup.is_dir():
                    shutil.copytree(backup, original)
                else:
                    shutil.copy2(backup, original)

    def clear_backups(self) -> None:
        """Remove all backup files."""
        for _, backup in self._backups:
            try:
                if backup.is_dir():
                    shutil.rmtree(backup)
                else:
                    backup.unlink()
            except (OSError, PermissionError):
                pass
        self._backups.clear()

    def __enter__(self) -> BackupManager:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            # Error occurred - restore backups
            self.restore_all()
        else:
            # Success - clean up backups
            self.clear_backups()
