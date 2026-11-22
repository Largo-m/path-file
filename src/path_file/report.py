"""Report building and formatting utilities."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from path_file.entries import Entry, Report
from path_file.units import human_size

# ──────────────────────────────────────────────────────────────────────────────
# REPORT BUILDER
# ──────────────────────────────────────────────────────────────────────────────


def build_report(entries: list[Entry]) -> Report:
    """
    Build aggregate report from list of entries.

    Args:
        entries: List of Entry objects

    Returns:
        Report object with aggregated statistics
    """
    report = Report()
    report.chain_size = len(entries)

    if not entries:
        return report

    report.total_size = sum(e.size for e in entries)
    report.file_count = sum(1 for e in entries if e.is_file)
    report.dir_count = sum(1 for e in entries if e.is_dir)
    report.symlink_count = sum(1 for e in entries if e.is_symlink)
    report.hidden_count = sum(1 for e in entries if e.is_hidden)
    report.empty_count = sum(1 for e in entries if e.is_empty)

    # By extension
    for e in entries:
        ext = e.suffix or "(none)"
        report.by_extension[ext] = report.by_extension.get(ext, 0) + 1

    # Size buckets
    buckets = {
        "0 B": (0, 0),
        "1-10 KB": (1, 10 * 1024),
        "10-100 KB": (10 * 1024, 100 * 1024),
        "100 KB - 1 MB": (100 * 1024, 1024 * 1024),
        "1-10 MB": (1024 * 1024, 10 * 1024 * 1024),
        "10-100 MB": (10 * 1024 * 1024, 100 * 1024 * 1024),
        "100 MB - 1 GB": (100 * 1024 * 1024, 1024 * 1024 * 1024),
        "1-10 GB": (1024 * 1024 * 1024, 10 * 1024 * 1024 * 1024),
        "10 GB+": (10 * 1024 * 1024 * 1024, float("inf")),
    }
    for e in entries:
        for bucket, (min_s, max_s) in buckets.items():
            if min_s <= e.size <= max_s:
                report.by_size_bucket[bucket] = report.by_size_bucket.get(bucket, 0) + 1
                break

    # Extremes
    file_entries = [e for e in entries if e.is_file]
    if file_entries:
        report.largest = max(file_entries, key=lambda e: e.size)
        report.smallest = min(file_entries, key=lambda e: e.size)

    report.newest = max(entries, key=lambda e: e.modified)
    report.oldest = min(entries, key=lambda e: e.modified)

    return report


# ──────────────────────────────────────────────────────────────────────────────
# TABLE FORMATTER
# ──────────────────────────────────────────────────────────────────────────────


def format_table(
    headers: list[str],
    rows: list[list[str]],
    alignments: list[str] | None = None,
) -> str:
    """
    Format data as pretty ASCII table.

    Args:
        headers: Column headers
        rows: Data rows (list of lists of strings)
        alignments: List of 'left', 'right', 'center' for each column

    Returns:
        Formatted table string
    """
    if not rows:
        return "No data."

    # Calculate column widths
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(str(cell)))

    # Default alignments
    if alignments is None:
        alignments = ["left"] * len(headers)

    # Build format strings
    def align_cell(cell: str, width: int, align: str) -> str:
        cell = str(cell)
        if align == "right":
            return cell.rjust(width)
        elif align == "center":
            return cell.center(width)
        else:
            return cell.ljust(width)

    lines = []
    # Top border
    top_parts = ["┌" + "─" * (w + 2) + "┐" for w in col_widths]
    lines.append("".join(top_parts[0].replace("┌", "┌").replace("┐", "┬")[:-1] + "┐"))

    # Headers
    header_cells = [
        f" {align_cell(h, col_widths[i], alignments[i])} " for i, h in enumerate(headers)
    ]
    lines.append("│" + "│".join(header_cells) + "│")

    # Header separator
    sep_cells = ["─" * (col_widths[i] + 2) for i in range(len(headers))]
    lines.append("├" + "┼".join(sep_cells) + "┤")

    # Data rows
    for row in rows:
        row_cells = [
            f" {align_cell(row[i] if i < len(row) else '', col_widths[i], alignments[i])} "
            for i in range(len(headers))
        ]
        lines.append("│" + "│".join(row_cells) + "│")

    # Bottom border
    bot_parts = ["└" + "─" * (w + 2) + "┘" for w in col_widths]
    lines.append("".join(bot_parts[0].replace("└", "└").replace("┘", "┴")[:-1] + "┘"))

    return "\n".join(lines)


def format_entry_table(entries: list[Entry]) -> str:
    """Format entries as a table."""
    if not entries:
        return "No entries found."

    headers = ["Name", "Size", "Type", "Modified"]
    alignments = ["left", "right", "left", "left"]
    rows = []

    for e in entries:
        name = e.name[:40] + ".." if len(e.name) > 42 else e.name
        size = e.size_human if e.is_file else "-"
        typ = "FILE" if e.is_file else "DIR" if e.is_dir else "LINK"
        mod = e.modified.strftime("%Y-%m-%d %H:%M")
        rows.append([name, size, typ, mod])

    return format_table(headers, rows, alignments)


def format_extension_table(report: Report) -> str:
    """Format extension breakdown as table."""
    if not report.by_extension:
        return "No files."

    headers = ["Extension", "Count", "Percentage"]
    alignments = ["left", "right", "right"]
    rows = []

    total = report.chain_size
    for ext, count in sorted(report.by_extension.items(), key=lambda x: -x[1]):
        ext_display = ext if ext else "(none)"
        pct = f"{count / total * 100:.1f}%"
        rows.append([ext_display, str(count), pct])

    return format_table(headers, rows, alignments)


def format_size_bucket_table(report: Report) -> str:
    """Format size bucket breakdown as table."""
    if not report.by_size_bucket:
        return "No files."

    headers = ["Size Range", "Count", "Percentage"]
    alignments = ["left", "right", "right"]
    rows = []

    total = report.chain_size
    for bucket, count in sorted(report.by_size_bucket.items(), key=lambda x: x[0]):
        pct = f"{count / total * 100:.1f}%"
        rows.append([bucket, str(count), pct])

    return format_table(headers, rows, alignments)


# ──────────────────────────────────────────────────────────────────────────────
# JSON ENCODER
# ──────────────────────────────────────────────────────────────────────────────


class PathflowJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for path_file types."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, Path):
            return str(obj)
        if isinstance(obj, Entry):
            return obj.as_dict()
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return super().default(obj)


def to_json(data: Any, indent: int = 2) -> str:
    """Convert to JSON string with custom encoder."""
    return json.dumps(data, indent=indent, ensure_ascii=False, cls=PathflowJSONEncoder)


# ──────────────────────────────────────────────────────────────────────────────
# CSV FORMATTER
# ──────────────────────────────────────────────────────────────────────────────


def to_csv(entries: list[Entry], include_header: bool = True) -> str:
    """Convert entries to CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)

    if include_header:
        writer.writerow(
            [
                "path",
                "name",
                "stem",
                "suffix",
                "extensions",
                "size",
                "size_human",
                "created",
                "modified",
                "accessed",
                "is_file",
                "is_dir",
                "is_symlink",
                "is_hidden",
                "is_empty",
                "hash_sha256",
            ]
        )

    for e in entries:
        writer.writerow(
            [
                str(e.path),
                e.name,
                e.stem,
                e.suffix,
                ";".join(e.extensions),
                e.size,
                e.size_human,
                e.created.isoformat(),
                e.modified.isoformat(),
                e.accessed.isoformat(),
                e.is_file,
                e.is_dir,
                e.is_symlink,
                e.is_hidden,
                e.is_empty,
                e.hash_sha256 if e.is_file else "",
            ]
        )

    return output.getvalue()


# ──────────────────────────────────────────────────────────────────────────────
# REPORT FORMATTING
# ──────────────────────────────────────────────────────────────────────────────


def format_report(report: Report, include_tables: bool = True) -> str:
    """Format full report as human-readable string."""
    lines = []

    lines.append("╔════════════════════════════════════════════════════════════════╗")
    lines.append("║                        PATHFLOW REPORT                        ║")
    lines.append("╠════════════════════════════════════════════════════════════════╣")

    lines.append(
        f"║  Total Entries: {report.chain_size:<6}  Total Size: "
        f"{human_size(report.total_size):>12}              ║"
    )
    lines.append(
        f"║  Files: {report.file_count:<6}  Dirs: {report.dir_count:<6}  "
        f"Symlinks: {report.symlink_count:<6}  Hidden: {report.hidden_count:<6}  "
        f"Empty: {report.empty_count:<6}  ║"
    )

    if include_tables and report.by_extension:
        lines.append("╠════════════════════════════════════════════════════════════════╣")
        lines.append("║  BY EXTENSION                                                 ║")
        lines.append("╠════════════════════════════════════════════════════════════════╣")
        ext_table = format_extension_table(report)
        for line in ext_table.split("\n"):
            lines.append(f"║  {line:<58} ║")

    if include_tables and report.by_size_bucket:
        lines.append("╠════════════════════════════════════════════════════════════════╣")
        lines.append("║  BY SIZE                                                      ║")
        lines.append("╠════════════════════════════════════════════════════════════════╣")
        size_table = format_size_bucket_table(report)
        for line in size_table.split("\n"):
            lines.append(f"║  {line:<58} ║")

    if report.largest or report.newest:
        lines.append("╠════════════════════════════════════════════════════════════════╣")
        lines.append("║  EXTREMES                                                     ║")
        lines.append("╠════════════════════════════════════════════════════════════════╣")
        if report.largest:
            lines.append(
                f"║  Largest:  {report.largest.path!s:<50} ({report.largest.size_human}) ║"
            )
        if report.smallest and report.smallest.size > 0:
            lines.append(
                f"║  Smallest: {report.smallest.path!s:<50} ({report.smallest.size_human}) ║"
            )
        if report.newest:
            lines.append(
                f"║  Newest:   {report.newest.path!s:<50} ({report.newest.modified_ago}) ║"
            )
        if report.oldest:
            lines.append(
                f"║  Oldest:   {report.oldest.path!s:<50} ({report.oldest.modified_ago}) ║"
            )

    lines.append("╚════════════════════════════════════════════════════════════════╝")

    return "\n".join(lines)
