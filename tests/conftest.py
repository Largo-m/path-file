"""Pytest configuration and fixtures for path_file tests."""

from __future__ import annotations

import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

# ──────────────────────────────────────────────────────────────────────────────
# FIXTURES
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def tmp_tree(tmp_dir: Path) -> Generator[Path, None, None]:
    """Create a temporary directory tree with known structure."""
    # Create structure
    (tmp_dir / "docs").mkdir()
    (tmp_dir / "images").mkdir()
    (tmp_dir / "archives").mkdir()
    (tmp_dir / "empty_dir").mkdir()
    (tmp_dir / "hidden_dir").mkdir()
    (tmp_dir / "hidden_dir" / ".hidden_file").write_text("secret")

    # Create files
    (tmp_dir / "file1.txt").write_text("hello world")
    (tmp_dir / "file2.txt").write_text("another file")
    (tmp_dir / "data.csv").write_text("a,b,c\n1,2,3")
    (tmp_dir / "script.py").write_text("print('hello')")
    (tmp_dir / "image1.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"x" * 1000)
    (tmp_dir / "image2.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 2000)
    (tmp_dir / "large.bin").write_bytes(b"x" * (5 * 1024 * 1024))  # 5 MB
    (tmp_dir / "small.txt").write_text("x")
    (tmp_dir / "empty.txt").write_text("")
    (tmp_dir / ".hidden").write_text("hidden")

    # Nested files
    (tmp_dir / "docs" / "readme.md").write_text("# Readme")
    (tmp_dir / "docs" / "guide.txt").write_text("Guide content")
    (tmp_dir / "images" / "photo1.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"x" * 500)
    (tmp_dir / "images" / "photo2.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"x" * 600)
    (tmp_dir / "archives" / "backup.zip").write_bytes(b"PK" + b"x" * 100)

    # Symlink
    try:
        (tmp_dir / "link_to_file1.txt").symlink_to(tmp_dir / "file1.txt")
        (tmp_dir / "link_to_docs").symlink_to(tmp_dir / "docs", target_is_directory=True)
    except (OSError, NotImplementedError):
        pass  # Symlinks may not work on all systems

    yield tmp_dir


@pytest.fixture
def sample_files(tmp_dir: Path) -> Generator[Path, None, None]:
    """Create various file types for testing."""
    # Text files
    (tmp_dir / "utf8.txt").write_text("Hello 世界", encoding="utf-8")
    (tmp_dir / "latin1.txt").write_text("Héllo", encoding="latin-1")
    (tmp_dir / "ascii.txt").write_text("Hello")

    # Binary files
    (tmp_dir / "binary.bin").write_bytes(bytes(range(256)))
    (tmp_dir / "empty.bin").write_bytes(b"")

    # Large file
    (tmp_dir / "large.txt").write_text("x" * (10 * 1024 * 1024))  # 10 MB

    # Files with special names
    (tmp_dir / "file with spaces.txt").write_text("spaces")
    (tmp_dir / "UPPERCASE.TXT").write_text("upper")
    (tmp_dir / "multiple.dots.txt").write_text("dots")

    yield tmp_dir


@pytest.fixture
def nested_tree(tmp_dir: Path) -> Generator[Path, None, None]:
    """Create deeply nested directory structure."""
    deep = tmp_dir
    for i in range(10):
        deep = deep / f"level{i}"
        deep.mkdir()
        (deep / f"file{i}.txt").write_text(f"content {i}")

    yield tmp_dir


@pytest.fixture
def symlink_tree(tmp_dir: Path) -> Generator[Path, None, None]:
    """Create directory with symlinks (including cycles)."""
    (tmp_dir / "real_file.txt").write_text("real")
    (tmp_dir / "real_dir").mkdir()
    (tmp_dir / "real_dir" / "inside.txt").write_text("inside")

    try:
        (tmp_dir / "link_file.txt").symlink_to(tmp_dir / "real_file.txt")
        (tmp_dir / "link_dir").symlink_to(tmp_dir / "real_dir", target_is_directory=True)
        # Broken symlink
        (tmp_dir / "broken_link.txt").symlink_to(tmp_dir / "nonexistent.txt")
        # Cycle
        (tmp_dir / "cycle_a").mkdir()
        (tmp_dir / "cycle_a" / "link_to_b").symlink_to(
            tmp_dir / "cycle_b", target_is_directory=True
        )
        (tmp_dir / "cycle_b").mkdir()
        (tmp_dir / "cycle_b" / "link_to_a").symlink_to(
            tmp_dir / "cycle_a", target_is_directory=True
        )
    except (OSError, NotImplementedError):
        pass

    yield tmp_dir


@pytest.fixture
def rules_file(tmp_dir: Path) -> Generator[Path, None, None]:
    """Create a sample rules TOML file."""
    content = """
[[rule]]
match = "*.tmp"
when_older_than = "7 days"
action = "delete"

[[rule]]
match = "*.jpg"
when_larger_than = "10MB"
action = "move"
dest = "~/Pictures/Large"

[[rule]]
match = "*.log"
when_older_than = "30 days"
action = "archive"
dest = "~/Archives/Logs"
"""
    rules_path = tmp_dir / "rules.toml"
    rules_path.write_text(content.strip())
    yield rules_path


# ──────────────────────────────────────────────────────────────────────────────
# TEST HELPERS
# ──────────────────────────────────────────────────────────────────────────────


def assert_action_result(result, expected_count: int = None, success: bool = True):
    """Assert ActionResult properties."""
    if expected_count is not None:
        assert result.count == expected_count
    assert result.success() == success


def create_test_files(base: Path, count: int = 10, prefix: str = "test") -> list[Path]:
    """Create test files with sequential names."""
    paths = []
    for i in range(count):
        p = base / f"{prefix}_{i:03d}.txt"
        p.write_text(f"Content {i}")
        paths.append(p)
    return paths
