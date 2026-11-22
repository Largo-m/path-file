#!/usr/bin/env python3
"""
Example 4: Find and Report Duplicate Files

Find duplicate files by content hash and generate a report.
"""

import json

import path_file as pf

TARGET = pf.expand("~/Documents")  # Change to your target directory


def main():
    print("🔍 Scanning for duplicates...")

    # Find all files
    chain = pf.find(TARGET).files()
    total = chain.count()
    print(f"📁 Scanning {total} files...")

    # Find duplicates by hash
    dupes = chain.duplicates_by_hash("sha256")

    if not dupes:
        print("✅ No duplicates found")
        return

    print(f"\n📊 Found {len(dupes)} duplicate groups:")

    total_wasted = 0
    for i, (hash_val, entries) in enumerate(dupes.items(), 1):
        size = entries[0].size
        wasted = size * (len(entries) - 1)
        total_wasted += wasted

        print(
            f"\n  Group {i} ({len(entries)} files, {pf.hsize(size)} each, {pf.hsize(wasted)} wasted):"
        )
        for e in entries:
            print(f"    {e.path}")

    print(f"\n💾 Total wasted space: {pf.hsize(total_wasted)}")

    # Save report
    report = {
        "total_files_scanned": total,
        "duplicate_groups": len(dupes),
        "total_wasted_bytes": total_wasted,
        "groups": [
            {
                "hash": h,
                "count": len(group),
                "size": group[0].size,
                "wasted": group[0].size * (len(group) - 1),
                "files": [str(e.path) for e in group],
            }
            for h, group in dupes.items()
        ],
    }

    report_path = pf.expand("~/duplicates_report.json")
    report_path.write_text(json.dumps(report, indent=2))
    print(f"\n📄 Report saved to {report_path}")


if __name__ == "__main__":
    main()
