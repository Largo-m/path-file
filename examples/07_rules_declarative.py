#!/usr/bin/env python3
"""
Example 7: Declarative Rules-Based Cleanup

Use a TOML rules file to automate file management.
"""

import path_file as pf

TARGET = pf.expand("~/Downloads")
RULES_FILE = pf.expand("~/cleanup_rules.toml")


def create_sample_rules():
    """Create a sample rules file."""
    content = """
# Cleanup rules for Downloads folder
# Run with: python 07_rules_declarative.py --create-rules

[[rule]]
match = "*.tmp"
when_older_than = "1 day"
action = "delete"
# Clean temp files older than 1 day

[[rule]]
match = "*.crdownload"
action = "delete"
# Chrome partial downloads

[[rule]]
match = "*.part"
action = "delete"
# Firefox partial downloads

[[rule]]
match = "*.dmg"
when_older_than = "7 days"
action = "move"
dest = "~/Archives/Installers"
# Move old macOS installers

[[rule]]
match = "*.exe"
when_older_than = "30 days"
action = "move"
dest = "~/Archives/Installers"
# Move old Windows installers

[[rule]]
match = "*.zip"
when_older_than = "30 days"
action = "move"
dest = "~/Archives/Archives"
# Move old archives

[[rule]]
match = "*.jpg"
when_larger_than = "50MB"
action = "move"
dest = "~/Pictures/Large"
# Move large photos

[[rule]]
match = "*.pdf"
when_older_than = "1 year"
action = "archive"
dest = "~/Archives/OldPDFs.tar.gz"
# Archive old PDFs

[[rule]]
match = "Screenshot*.png"
action = "rename"
pattern = "Screenshot_{date:%Y-%m-%d}_{n:03d}{ext}"
# Rename screenshots with date
"""
    RULES_FILE.write_text(content.strip())
    print(f"✅ Created sample rules at {RULES_FILE}")


def main():
    import sys

    if "--create-rules" in sys.argv:
        create_sample_rules()
        return

    if not RULES_FILE.exists():
        print(f"❌ Rules file not found: {RULES_FILE}")
        print("   Run with --create-rules to create a sample")
        return

    print("📋 Loading rules...")
    rules = pf.Rules.from_file(RULES_FILE)

    # Validate
    errors = rules.validate()
    if errors:
        print("❌ Validation errors:")
        for e in errors:
            print(f"   {e}")
        return

    print(rules.explain())

    # Apply to target
    chain = pf.find(TARGET).files()
    print(f"\n🔍 Scanning {TARGET}...")
    print(f"   Found {chain.count()} files")

    # Dry run
    print("\n🔄 Dry run:")
    result = rules.apply(chain.dry_run(True))
    print(result.preview())

    # Confirm
    confirm = input("\n⚠️  Apply rules? Type 'yes': ").strip().lower()
    if confirm != "yes":
        print("❌ Cancelled")
        return

    # Execute
    print("\n⚡ Applying rules...")
    result = rules.apply(chain.dry_run(False))
    print("✅ Rules applied")


if __name__ == "__main__":
    main()
