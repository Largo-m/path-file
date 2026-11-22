#!/usr/bin/env python3
"""
Example 2: Organize Photos by Date

Sort photos into YYYY/MM folders based on modification date.
"""

import path_file as pf

PHOTOS = pf.expand("~/Photos")
ORGANIZED = pf.expand("~/Photos/Organized")


def main():
    print("📸 Organizing photos by date...")

    # Find all image files
    chain = (
        pf.find(PHOTOS)
        .files()
        .with_extensions(".jpg", ".jpeg", ".png", ".heic", ".raw", ".cr2", ".nef")
    )

    count = chain.count()
    if count == 0:
        print("✅ No photos to organize")
        return

    print(f"📁 Found {count} photos")

    # Process each photo
    for entry in chain:
        # Get date from modification time
        date = entry.modified
        year = date.strftime("%Y")
        month = date.strftime("%m")

        # Create destination folder
        dest_dir = ORGANIZED / year / month
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Move file
        dest = dest_dir / entry.name
        if dest.exists():
            # Handle duplicates
            base = entry.stem
            ext = entry.suffix
            counter = 1
            while dest.exists():
                dest = dest_dir / f"{base}_{counter}{ext}"
                counter += 1

        print(f"  Moving {entry.name} → {year}/{month}/")
        entry.path.rename(dest)

    print(f"\n✅ Organized {count} photos into {ORGANIZED}")


if __name__ == "__main__":
    main()
