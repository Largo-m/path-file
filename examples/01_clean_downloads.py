#!/usr/bin/env python3
"""
Example 1: Clean Downloads Folder

Delete files older than 30 days in Downloads folder.
Dry-run first to preview, then execute with confirmation.
"""

import path_file as pf

DOWNLOADS = pf.expand("~/Downloads")


def main():
    print("🔍 Scanning Downloads folder...")

    # Find files older than 30 days
    chain = pf.find(DOWNLOADS).files().older_than("30 days")

    count = chain.count()
    if count == 0:
        print("✅ No old files to clean")
        return

    print(f"📁 Found {count} files older than 30 days")
    print(chain.preview())

    # Dry run first
    print("\n🔄 Dry run:")
    result = chain.delete(dry_run=True).execute()
    print(result.summary())

    # Ask for confirmation
    confirm = input("\n⚠️  Delete these files? Type 'yes' to confirm: ").strip().lower()
    if confirm != "yes":
        print("❌ Cancelled")
        return

    # Execute
    print("\n🗑️  Deleting...")
    result = chain.delete(confirm=True, dry_run=False).execute()
    print(result.summary())

    if result.success():
        print(f"✅ Cleaned {result.count} files ({pf.hsize(result.total_size)})")
    else:
        print(f"❌ Errors: {len(result.errors)}")


if __name__ == "__main__":
    main()
