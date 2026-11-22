#!/usr/bin/env python3
"""
Example 5: Watch and Auto-Sort Downloads

Watch Downloads folder and automatically sort new files by extension.
"""

import shutil

import path_file as pf

DOWNLOADS = pf.expand("~/Downloads")
SORTED = pf.expand("~/Downloads/Sorted")

# Extension to folder mapping
CATEGORIES = {
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".heic"],
    "Documents": [".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".md"],
    "Spreadsheets": [".xls", ".xlsx", ".csv", ".ods"],
    "Presentations": [".ppt", ".pptx", ".odp"],
    "Archives": [".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar"],
    "Audio": [".mp3", ".wav", ".flac", ".ogg", ".m4a"],
    "Video": [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv"],
    "Code": [".py", ".js", ".ts", ".html", ".css", ".json", ".xml", ".yaml", ".yml", ".sh", ".sql"],
    "Executables": [".exe", ".msi", ".dmg", ".app", ".deb", ".rpm"],
    "Other": [],
}


def get_category(ext: str) -> str:
    """Get category for extension."""
    ext = ext.lower()
    for category, extensions in CATEGORIES.items():
        if ext in extensions:
            return category
    return "Other"


def main():
    print("👀 Starting Downloads watcher...")
    print(f"   Source: {DOWNLOADS}")
    print(f"   Destination: {SORTED}")
    print("   Press Ctrl+C to stop\n")

    # Create watcher
    watcher = pf.watch(DOWNLOADS, poll_interval=2.0)

    # Filter for files only (skip directories)
    watcher.filter_by(lambda e: e.is_file)

    # Debounce to avoid duplicate events
    watcher.debounce(1.0)

    def on_new(event):
        """Handle new file."""
        path = event.path
        ext = path.suffix.lower()
        category = get_category(ext)

        dest_dir = SORTED / category
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest = dest_dir / path.name
        if dest.exists():
            # Handle duplicates
            base = path.stem
            counter = 1
            while dest.exists():
                dest = dest_dir / f"{base}_{counter}{ext}"
                counter += 1

        try:
            shutil.move(str(path), str(dest))
            print(f"📦 {path.name} → {category}/")
        except Exception as e:
            print(f"❌ Failed to move {path.name}: {e}")

    watcher.on_new(on_new)

    try:
        watcher.run_forever()
    except KeyboardInterrupt:
        print("\n👋 Stopping watcher...")


if __name__ == "__main__":
    main()
