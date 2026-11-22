#!/usr/bin/env python3
"""
Example 9: Batch Rename Photos

Rename photos with pattern "IMG_{date}_{n}" based on modification time.
"""

import path_file as pf

PHOTOS = pf.expand("~/Photos/Unsorted")  # Change to your photo folder


def main():
    print("📸 Batch renaming photos...")

    # Find all image files
    chain = (
        pf.find(PHOTOS)
        .files()
        .with_extensions(".jpg", ".jpeg", ".png", ".heic", ".raw")
        .sort_by("date")
    )

    count = chain.count()
    if count == 0:
        print("✅ No photos to rename")
        return

    print(f"📁 Found {count} photos")

    # Show preview with pattern
    print("\n🔄 Preview (pattern: IMG_{date:%Y%m%d}_{n:04d}{ext}):")
    for i, entry in enumerate(chain.to_list()[:10], 1):
        date = entry.modified.strftime("%Y%m%d")
        new_name = f"IMG_{date}_{i:04d}{entry.suffix}"
        print(f"  {entry.name} → {new_name}")

    if count > 10:
        print(f"  ... and {count - 10} more")

    # Confirm
    confirm = input("\n⚠️  Rename these files? Type 'yes': ").strip().lower()
    if confirm != "yes":
        print("❌ Cancelled")
        return

    # Execute rename
    print("\n✏️  Renaming...")
    result = chain.rename("IMG_{date:%Y%m%d}_{n:04d}{ext}").execute()
    print(result.summary())

    if result.success():
        print(f"✅ Renamed {result.count} files")
    else:
        print(f"❌ Errors: {len(result.errors)}")


if __name__ == "__main__":
    main()
