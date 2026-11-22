"""Tests for exceptions."""

from __future__ import annotations

import path_file as pf
from path_file.exceptions import *


class TestPathflowError:
    """Test base PathflowError."""

    def test_basic_error(self):
        err = PathflowError("Something went wrong")
        assert str(err) == "Something went wrong"
        assert err.message == "Something went wrong"
        assert err.hint is None

    def test_error_with_hint(self):
        err = PathflowError("Failed", "Try again")
        assert str(err) == "Failed\nHint: Try again"
        assert err.hint == "Try again"

    def test_repr(self):
        err = PathflowError("msg", "hint")
        repr_str = repr(err)
        assert "PathflowError" in repr_str
        assert "msg" in repr_str
        assert "hint" in repr_str


class TestFileNotFoundError:
    """Test FileNotFoundError."""

    def test_with_path(self):
        err = pf.FileNotFoundError("/path/to/file")
        assert "File not found: /path/to/file" in str(err)
        assert err.path == "/path/to/file"

    def test_with_hint(self):
        err = pf.FileNotFoundError("/path", "Check permissions")
        assert "Check permissions" in str(err)


class TestPermissionError:
    """Test PermissionError."""

    def test_basic(self):
        err = pf.PermissionError("/path", "read")
        assert "Permission denied during read: /path" in str(err)
        assert err.path == "/path"
        assert err.operation == "read"

    def test_with_hint(self):
        err = pf.PermissionError("/path", "write", "Run as admin")
        assert "Run as admin" in str(err)


class TestDestExistsError:
    """Test DestExistsError."""

    def test_basic(self):
        err = pf.DestExistsError("/dest/path")
        assert "Destination already exists: /dest/path" in str(err)
        assert "overwrite=True" in str(err)

    def test_custom_hint(self):
        err = pf.DestExistsError("/dest", "Custom hint")
        assert "Custom hint" in str(err)


class TestInvalidPatternError:
    """Test InvalidPatternError."""

    def test_basic(self):
        err = pf.InvalidPatternError("[invalid")
        assert "Invalid pattern" in str(err)
        assert "glob patterns" in str(err)

    def test_custom_hint(self):
        err = pf.InvalidPatternError("bad", "Use valid regex")
        assert "Use valid regex" in str(err)


class TestInvalidSizeError:
    """Test InvalidSizeError."""

    def test_basic(self):
        err = pf.InvalidSizeError("10XB")
        assert "Invalid size" in str(err)
        assert "KB, MB, GB" in str(err)

    def test_negative_size(self):
        err = pf.InvalidSizeError("-1MB")
        # Negative sizes are rejected at regex level
        assert "invalid size" in str(err).lower()


class TestInvalidDurationError:
    """Test InvalidDurationError."""

    def test_basic(self):
        err = pf.InvalidDurationError("10 fortnights")
        assert "Invalid duration" in str(err)
        assert "days" in str(err) or "hours" in str(err)


class TestRulesParseError:
    """Test RulesParseError."""

    def test_with_line(self):
        err = pf.RulesParseError("Invalid key", line=5)
        assert "line 5" in str(err)

    def test_without_line(self):
        err = pf.RulesParseError("Invalid key")
        assert "line" not in str(err).lower()


class TestDryRunRequiredError:
    """Test DryRunRequiredError."""

    def test_basic(self):
        err = pf.DryRunRequiredError("delete", 5)
        assert "delete" in str(err)
        assert "5" in str(err)
        assert "confirm=True" in str(err)

    def test_custom_hint(self):
        err = pf.DryRunRequiredError("move", 3, "Custom hint")
        assert "Custom hint" in str(err)


class TestSyncConflictError:
    """Test SyncConflictError."""

    def test_basic(self):
        err = pf.SyncConflictError("/path/file.txt", "hash1", "hash2")
        assert "Sync conflict" in str(err)
        assert "/path/file.txt" in str(err)
        assert err.source_hash == "hash1"
        assert err.dest_hash == "hash2"


class TestWatchError:
    """Test WatchError."""

    def test_basic(self):
        err = pf.WatchError("/watched/path")
        assert "Watch error" in str(err)


class TestArchiveError:
    """Test ArchiveError."""

    def test_basic(self):
        err = pf.ArchiveError("Corrupt archive", "/path/archive.zip")
        assert "Archive error" in str(err)
        assert "archive.zip" in str(err)


class TestHashError:
    """Test HashError."""

    def test_basic(self):
        err = pf.HashError("/path/file.txt")
        assert "Hash computation failed" in str(err)


class TestExceptionHierarchy:
    """Test exception inheritance."""

    def test_all_inherit_from_path_fileerror(self):
        errors = [
            pf.FileNotFoundError(""),
            pf.PermissionError(""),
            pf.DestExistsError(""),
            pf.InvalidPatternError(""),
            pf.InvalidSizeError(""),
            pf.InvalidDurationError(""),
            pf.RulesParseError(""),
            pf.DryRunRequiredError("", 0),
            pf.SyncConflictError("", "", ""),
            pf.WatchError(""),
            pf.ArchiveError(""),
            pf.HashError(""),
        ]

        for err in errors:
            assert isinstance(err, pf.PathflowError)
            assert isinstance(err, Exception)
