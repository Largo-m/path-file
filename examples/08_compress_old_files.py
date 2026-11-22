#!/usr/bin/env python3
"""
Example 8: Compress Old Files

Compress files older than 1 year to save space.
"""

import path_file as pf

TARGET = pf.expand("~/Documents/Archive")  # Change to your archive folder


def main():
    print("🗜️  Compressing old files...")

    # Find files older than 1 year (excluding already compressed)
    chain = (
        pf.find(TARGET)
        .files()
        .older_than("1 year")
        .without_extension(".gz")
        .without_extension(".bz2")
        .without_extension(".xz")
        .without_extension(".zip")
        .without_extension(".tar")
    )

    count = chain.count()
    if count == 0:
        print("✅ No files to compress")
        return

    total_size = sum(e.size for e in chain)
    print(f"📁 Found {count} files ({pf.hsize(total_size)})")
    print(chain.to_table())

    # Dry run
    print("\n🔄 Dry run:")
    result = chain.compress("gz", dry_run=True).execute()
    print(result.summary())

    # Confirm
    confirm = input("\n⚠️  Compress these files? Type 'yes': ").strip().lower()
    if confirm != "yes":
        print("❌ Cancelled")
        return

    # Execute
    print("\n🗜️  Compressing...")
    result = chain.compress("gz", dry_run=False).progress().execute()
    print(result.summary())

    if result.success():
        print(f"✅ Compressed {result.count} files")
    else:
        print(f"❌ Errors: {len(result.errors)}")


if __name__ == "__main__":
    main()
