#!/usr/bin/env python3
"""
Example 10: Generate Audit Report

Generate a comprehensive audit report of a directory tree.
"""

import path_file as pf

TARGET = pf.expand("~/Projects")  # Change to your target directory
OUTPUT_DIR = pf.expand("~/AuditReports")


def main():
    print("📊 Generating audit report...")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Generate report
    chain = pf.find(TARGET)
    report = chain.report()

    # Print summary table
    print(report.to_table())

    # Extension breakdown
    print("\n📈 By Extension:")
    print(report.to_table())  # Shows extension table

    # Size breakdown
    print("\n📦 By Size:")
    # Custom size table would go here

    # Save reports
    timestamp = pf.human_ago(pf.duration("0")).replace(" ", "_").replace(":", "-")
    base = OUTPUT_DIR / f"audit_{timestamp}"

    # JSON report
    json_path = base.with_suffix(".json")
    report.to_json(json_path)
    print(f"\n💾 JSON report: {json_path}")

    # CSV report
    csv_path = base.with_suffix(".csv")
    report.to_csv(csv_path)
    print(f"💾 CSV report: {csv_path}")

    # Detailed file list
    detail_path = base.with_name(base.name + "_files.csv")
    chain.files().to_csv(detail_path)
    print(f"💾 File list: {detail_path}")

    # Find largest files
    print("\n🏆 Top 10 Largest Files:")
    largest = pf.find_largest(TARGET, 10)
    for f in largest:
        entry = pf.Entry.from_path(f)
        print(f"  {entry.path.relative_to(TARGET)} - {entry.size_human}")

    # Find oldest files
    print("\n📅 Top 10 Oldest Files:")
    oldest = pf.find_oldest(TARGET, 10)
    for f in oldest:
        entry = pf.Entry.from_path(f)
        print(f"  {entry.path.relative_to(TARGET)} - {entry.modified_ago}")

    print(f"\n✅ Audit complete. Reports saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
