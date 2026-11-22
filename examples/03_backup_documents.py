#!/usr/bin/env python3
"""
Example 3: Backup Documents with Hash Verification

Sync Documents folder to backup drive with hash verification.
"""

import path_file as pf

SOURCE = pf.expand("~/Documents")
BACKUP = "/mnt/backup/Documents"  # Change to your backup drive


def main():
    print("💾 Backing up Documents...")

    # Create syncer
    syncer = pf.sync(SOURCE, BACKUP)
    syncer.direction("source_to_dest").ignore(
        ["*.tmp", "~$*", ".DS_Store", "Thumbs.db"]
    ).delete_extras(False).parallel(4).progress(True)

    # Compare first
    print("🔍 Comparing...")
    diff = syncer.compare()
    print(diff.summary())

    if not diff.has_changes():
        print("✅ Already in sync")
        return

    # Dry run
    print("\n🔄 Dry run:")
    syncer.dry_run(True).execute()

    # Confirm
    confirm = input("\n⚠️  Proceed with backup? Type 'yes': ").strip().lower()
    if confirm != "yes":
        print("❌ Cancelled")
        return

    # Execute
    print("\n📦 Backing up...")
    syncer.dry_run(False).execute()

    # Verify with hashes
    print("\n🔐 Verifying hashes...")
    source_chain = pf.find(SOURCE).files()
    backup_chain = pf.find(BACKUP).files()

    source_hashes = {e.path.relative_to(SOURCE): e.hash_sha256 for e in source_chain}
    backup_hashes = {e.path.relative_to(BACKUP): e.hash_sha256 for e in backup_chain}

    mismatches = []
    for rel_path, src_hash in source_hashes.items():
        if rel_path in backup_hashes:
            if src_hash != backup_hashes[rel_path]:
                mismatches.append(rel_path)

    if mismatches:
        print(f"❌ {len(mismatches)} files have hash mismatches!")
        for m in mismatches:
            print(f"  {m}")
    else:
        print("✅ All files verified successfully")


if __name__ == "__main__":
    main()
