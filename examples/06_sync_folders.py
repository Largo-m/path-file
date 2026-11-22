#!/usr/bin/env python3
"""
Example 6: Bidirectional Folder Sync

Sync two folders bidirectionally with conflict detection.
"""

from pathlib import Path

import path_file as pf

FOLDER_A = pf.expand("~/FolderA")
FOLDER_B = pf.expand("~/FolderB")


def main():
    print("🔄 Bidirectional sync")
    print(f"   A: {FOLDER_A}")
    print(f"   B: {FOLDER_B}\n")

    # Create folders if they don't exist
    Path(FOLDER_A).mkdir(parents=True, exist_ok=True)
    Path(FOLDER_B).mkdir(parents=True, exist_ok=True)

    # Create syncer
    syncer = pf.sync(FOLDER_A, FOLDER_B)
    syncer.direction("bidirectional").conflict_strategy("newer_wins").ignore(
        ["*.tmp", "~$*", ".DS_Store"]
    ).parallel(4).progress(True)

    # Compare
    print("🔍 Comparing...")
    diff = syncer.compare()
    print(diff.summary())

    if diff.conflicts:
        print(f"\n⚠️  {len(diff.conflicts)} conflicts detected (newer wins):")
        for src, _dest in diff.conflicts:
            src_rel = src.relative_to(FOLDER_A)
            print(f"   {src_rel}")

    if not diff.has_changes():
        print("\n✅ Already in sync")
        return

    # Dry run
    print("\n🔄 Dry run:")
    syncer.dry_run(True).execute()

    # Confirm
    confirm = input("\n⚠️  Proceed with sync? Type 'yes': ").strip().lower()
    if confirm != "yes":
        print("❌ Cancelled")
        return

    # Execute
    print("\n🔄 Syncing...")
    syncer.dry_run(False).execute()
    print("✅ Sync complete")


if __name__ == "__main__":
    main()
