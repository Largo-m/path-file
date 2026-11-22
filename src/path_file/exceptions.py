"""Custom exceptions for path_file with helpful hints."""

from __future__ import annotations


class PathflowError(Exception):
    """Base exception for all path_file errors."""

    def __init__(self, message: str, hint: str | None = None) -> None:
        self.message = message
        self.hint = hint
        super().__init__(message)

    def __str__(self) -> str:
        if self.hint:
            return f"{self.message}\nHint: {self.hint}"
        return self.message

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.message!r}, hint={self.hint!r})"


class FileNotFoundError(PathflowError):
    """Raised when a file or directory is not found."""

    def __init__(self, path: str | None = None, hint: str | None = None) -> None:
        msg = f"File not found: {path}" if path else "File not found"
        default_hint = "Check the path exists and you have read permissions" if not hint else hint
        super().__init__(msg, default_hint)
        self.path = path


class PermissionError(PathflowError):
    """Raised when permission is denied for an operation."""

    def __init__(
        self, path: str | None = None, operation: str | None = None, hint: str | None = None
    ) -> None:
        op = f" during {operation}" if operation else ""
        msg = f"Permission denied{op}: {path}" if path else f"Permission denied{op}"
        default_hint = (
            "Run with elevated privileges or check file/folder permissions" if not hint else hint
        )
        super().__init__(msg, default_hint)
        self.path = path
        self.operation = operation


class DestExistsError(PathflowError):
    """Raised when destination already exists and overwrite is False."""

    def __init__(self, dest: str | None = None, hint: str | None = None) -> None:
        msg = f"Destination already exists: {dest}" if dest else "Destination already exists"
        default_hint = (
            "Use overwrite=True or remove the existing destination first" if not hint else hint
        )
        super().__init__(msg, default_hint)
        self.dest = dest


class InvalidPatternError(PathflowError):
    """Raised when a pattern (glob/regex) is invalid."""

    def __init__(self, pattern: str | None = None, hint: str | None = None) -> None:
        msg = f"Invalid pattern: {pattern}" if pattern else "Invalid pattern"
        default_hint = (
            "Check pattern syntax: use glob patterns (*.txt) or valid regex" if not hint else hint
        )
        super().__init__(msg, default_hint)
        self.pattern = pattern


class InvalidSizeError(PathflowError):
    """Raised when a size specification is invalid."""

    def __init__(self, size_spec: str | None = None, hint: str | None = None) -> None:
        msg = f"Invalid size specification: {size_spec}" if size_spec else "Invalid size"
        default_hint = (
            "Use format like '100B', '1KB', '2.5MB', '1GB' (KB, MB, GB supported)"
            if not hint
            else hint
        )
        super().__init__(msg, default_hint)
        self.size_spec = size_spec


class InvalidDurationError(PathflowError):
    """Raised when a duration specification is invalid."""

    def __init__(self, duration_spec: str | None = None, hint: str | None = None) -> None:
        msg = f"Invalid duration: {duration_spec}" if duration_spec else "Invalid duration"
        default_hint = (
            "Use format like '7 days', '1h', '30m', '1 week', '2 months'" if not hint else hint
        )
        super().__init__(msg, default_hint)
        self.duration_spec = duration_spec


class RulesParseError(PathflowError):
    """Raised when parsing rules file fails."""

    def __init__(self, message: str, line: int | None = None, hint: str | None = None) -> None:
        line_info = f" at line {line}" if line else ""
        msg = f"Failed to parse rules{line_info}: {message}"
        default_hint = (
            "Check TOML syntax: ensure [[rule]] sections have valid keys and values"
            if not hint
            else hint
        )
        super().__init__(msg, default_hint)
        self.line = line


class DryRunRequiredError(PathflowError):
    """Raised when a destructive operation requires explicit confirmation."""

    def __init__(self, action: str, count: int, hint: str | None = None) -> None:
        msg = f"Destructive operation '{action}' would affect {count} file(s)"
        default_hint = (
            "Use confirm=True to proceed, or dry_run=True to preview" if not hint else hint
        )
        super().__init__(msg, default_hint)
        self.action = action
        self.count = count


class SyncConflictError(PathflowError):
    """Raised when sync detects a conflict."""

    def __init__(
        self,
        path: str,
        source_hash: str,
        dest_hash: str,
        hint: str | None = None,
    ) -> None:
        msg = f"Sync conflict at {path}: source and destination differ"
        default_hint = (
            "Resolve manually or use direction='source_to_dest' to force" if not hint else hint
        )
        super().__init__(msg, default_hint)
        self.path = path
        self.source_hash = source_hash
        self.dest_hash = dest_hash


class WatchError(PathflowError):
    """Raised when folder watching encounters an error."""

    def __init__(self, path: str | None = None, hint: str | None = None) -> None:
        msg = f"Watch error: {path}" if path else "Watch error"
        default_hint = (
            "Check path exists and is readable; watcher uses polling fallback" if not hint else hint
        )
        super().__init__(msg, default_hint)
        self.path = path


class ArchiveError(PathflowError):
    """Raised when archive operations fail."""

    def __init__(self, message: str, path: str | None = None, hint: str | None = None) -> None:
        msg = f"Archive error: {message}" + (f" ({path})" if path else "")
        default_hint = (
            "Check archive format is supported and file is not corrupted" if not hint else hint
        )
        super().__init__(msg, default_hint)
        self.path = path


class HashError(PathflowError):
    """Raised when hash computation fails."""

    def __init__(self, path: str | None = None, hint: str | None = None) -> None:
        msg = f"Hash computation failed: {path}" if path else "Hash computation failed"
        default_hint = (
            "Check file is readable and not locked by another process" if not hint else hint
        )
        super().__init__(msg, default_hint)
        self.path = path
