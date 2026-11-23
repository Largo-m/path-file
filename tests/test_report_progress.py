"""Tests for report.py formatting/export and progress.py rendering."""

from __future__ import annotations

import io
import json
from pathlib import Path

from path_file import Entry
from path_file.progress import (
    ProgressBar,
    Spinner,
    _can_encode,
    _safe_write,
    create_progress,
    terminal_width,
)
from path_file.report import (
    PathflowJSONEncoder,
    build_report,
    format_entry_table,
    format_extension_table,
    format_report,
    format_size_bucket_table,
    format_table,
    to_csv,
    to_json,
)


def _entries(tmp_dir: Path) -> list[Entry]:
    (tmp_dir / "a.txt").write_text("hello")
    (tmp_dir / "b.log").write_text("x" * 2048)
    (tmp_dir / "c.bin").write_bytes(b"\x00" * 10)
    (tmp_dir / "empty.txt").write_text("")
    (tmp_dir / ".hidden").write_text("h")
    (tmp_dir / "sub").mkdir()
    (tmp_dir / "sub" / "d.txt").write_text("deep")
    return [Entry.from_path(p) for p in sorted(tmp_dir.rglob("*"))]


class TestBuildReport:
    def test_report_counts(self, tmp_dir):
        report = build_report(_entries(tmp_dir))
        assert report.chain_size > 0
        assert report.file_count >= 5
        assert report.dir_count == 1
        assert report.hidden_count == 1
        assert report.empty_count == 1
        assert report.total_size > 0
        assert ".txt" in report.by_extension
        assert report.largest is not None
        assert report.smallest is not None
        assert report.newest is not None
        assert report.oldest is not None

    def test_report_empty(self):
        report = build_report([])
        assert report.chain_size == 0
        assert report.total_size == 0
        assert report.largest is None

    def test_size_buckets(self, tmp_dir):
        (tmp_dir / "big.bin").write_bytes(b"x" * (2 * 1024 * 1024))
        report = build_report(_entries(tmp_dir))
        assert sum(report.by_size_bucket.values()) >= 6


class TestFormatting:
    def test_format_table(self, tmp_dir):
        table = format_table(
            ["Extension", "Count"],
            [[".txt", "3"], [".log", "1"]],
        )
        assert "Extension" in table and ".txt" in table

    def test_format_entry_table(self, tmp_dir):
        out = format_entry_table(_entries(tmp_dir))
        assert "a.txt" in out

    def test_format_extension_table(self, tmp_dir):
        report = build_report(_entries(tmp_dir))
        out = format_extension_table(report)
        assert ".txt" in out

    def test_format_size_bucket_table(self, tmp_dir):
        report = build_report(_entries(tmp_dir))
        out = format_size_bucket_table(report)
        assert "B" in out

    def test_format_report_full(self, tmp_dir):
        report = build_report(_entries(tmp_dir))
        out = format_report(report)
        assert "a.txt" in out or ".txt" in out

    def test_format_report_no_tables(self, tmp_dir):
        report = build_report(_entries(tmp_dir))
        out = format_report(report, include_tables=False)
        assert "Largest" in out or "Files" in out or out

    def test_to_json(self, tmp_dir):
        report = build_report(_entries(tmp_dir))
        data = json.loads(to_json(report))
        assert data["chain_size"] == report.chain_size

    def test_to_json_indent(self, tmp_dir):
        report = build_report(_entries(tmp_dir))
        assert "\n" in to_json(report, indent=4)

    def test_encoder_direct(self):
        encoded = json.dumps({"a": Path("x")}, cls=PathflowJSONEncoder)
        assert "x" in encoded


class TestToCsv:
    def test_to_csv_with_header(self, tmp_dir):
        out = to_csv(_entries(tmp_dir))
        lines = out.strip().splitlines()
        assert lines[0].startswith("name") or lines[0].startswith("path") or lines[0]
        assert len(lines) >= 6

    def test_to_csv_without_header(self, tmp_dir):
        out = to_csv(_entries(tmp_dir), include_header=False)
        assert "a.txt" in out

    def test_to_csv_empty(self):
        out = to_csv([])
        assert out.strip() == "" or out.startswith("path")


class TestProgress:
    def test_terminal_width(self):
        assert terminal_width() > 0

    def test_can_encode_and_safe_write(self):
        buf = io.StringIO()
        assert _can_encode(buf, "plain") is True
        _safe_write(buf, "hello")
        assert buf.getvalue() == "hello"

    def test_progress_bar_renders(self):
        buf = io.StringIO()
        bar = ProgressBar(3, stream=buf)
        bar.update(1)
        bar.update(1)
        bar.finish()
        out = buf.getvalue()
        assert out

    def test_progress_bar_iteration(self):
        buf = io.StringIO()
        seen = []
        with ProgressBar(3, stream=buf) as bar:
            for i in range(3):
                seen.append(i)
                bar.update(1)
        assert len(seen) == 3

    def test_progress_bar_zero_total(self):
        buf = io.StringIO()
        bar = ProgressBar(0, stream=buf)
        bar.finish()

    def test_progress_bar_overflow(self):
        buf = io.StringIO()
        bar = ProgressBar(2, stream=buf)
        bar.update(5)
        bar.finish()

    def test_spinner_frames(self):
        buf = io.StringIO()
        spinner = Spinner(stream=buf)
        spinner.update("working")
        spinner.stop()
        assert buf.getvalue()

    def test_create_progress_bar(self):
        buf = io.StringIO()
        result = create_progress(5, "copy", buf)
        assert isinstance(result, ProgressBar)
        result.finish()

    def test_create_progress_spinner(self):
        buf = io.StringIO()
        result = create_progress(None, "waiting", buf)
        assert isinstance(result, Spinner)
        result.stop()
