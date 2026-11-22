# Recipes

Common patterns and real-world examples.

## Clean Up Downloads Folder

```python
import path_file as pf

# Delete files older than 30 days
pf.find("~/Downloads").files().older_than("30 days").delete(confirm=True).execute()

# Or move to archive
pf.find("~/Downloads").files().older_than("30 days").move_to("~/Archive/Downloads").execute()
```

## Organize Photos by Date

```python
import path_file as pf
from datetime import datetime

photos = pf.find("~/Photos").files().with_extensions(".jpg", ".jpeg", ".png", ".heic")

for entry in photos:
    # Use EXIF date or file modification time
    date = entry.modified.strftime("%Y/%m")
    dest = Path(f"~/Photos/Organized/{date}")
    entry.path.rename(dest / entry.name)
```

## Backup with Verification

```python
import path_file as pf

source = "~/Documents"
backup = "/mnt/backup/Documents"

# Copy with hash verification
chain = pf.find(source).files()
result = chain.copy_to(backup, preserve_metadata=True).execute()

# Verify all files match
for entry in chain:
    backup_file = Path(backup) / entry.path.relative_to(source)
    assert entry.hash_sha256 == pf.hash_file(backup_file)
```

## Find and Remove Duplicates

```python
import path_file as pf

# Find duplicates by content
chain = pf.find("~/Documents").files()
dupes = chain.duplicates_by_hash()

for hash_val, entries in dupes.items():
    print(f"Duplicate group ({len(entries)} files):")
    for e in entries:
        print(f"  {e.path} ({e.size_human})")
    
    # Keep first, delete rest
    for e in entries[1:]:
        e.path.unlink()
```

## Compress Old Log Files

```python
import path_file as pf

pf.find("/var/log/myapp").files().with_extension(".log").older_than("7 days").compress(
    "gz"
).execute()
```

## Sync with Exclusions

```python
import path_file as pf

syncer = pf.sync("~/Projects", "/backup/Projects")
syncer.direction("source_to_dest").ignore(
    ["*.pyc", "__pycache__/", ".git/", "*.log", "build/", "dist/"]
).delete_extras(True).dry_run()

diff = syncer.compare()
print(diff.summary())

if diff.has_changes():
    syncer.dry_run(False).execute()
```

## Watch and Auto-Organize

```python
import path_file as pf
import shutil

watcher = pf.watch("~/Downloads", poll_interval=2.0)


def organize(event):
    ext = event.path.suffix.lower()
    if ext in (".jpg", ".jpeg", ".png", ".gif"):
        dest = Path("~/Pictures") / ext[1:].upper()
    elif ext in (".pdf", ".doc", ".docx"):
        dest = Path("~/Documents")
    elif ext in (".zip", ".tar", ".gz"):
        dest = Path("~/Archives")
    else:
        dest = Path("~/Downloads/Other")

    dest.mkdir(parents=True, exist_ok=True)
    shutil.move(str(event.path), str(dest / event.path.name))


watcher.filter("*.jpg", "*.png", "*.pdf", "*.zip").on_new(organize)
watcher.run_forever()
```

## Declarative Rules

Create `cleanup.toml`:

```toml
[[rule]]
match = "*.tmp"
when_older_than = "1 day"
action = "delete"

[[rule]]
match = "*.log"
when_older_than = "30 days"
action = "delete"

[[rule]]
match = "*.bak"
action = "delete"

[[rule]]
match = "*.jpg"
when_larger_than = "50MB"
action = "move"
dest = "~/Pictures/Large"
```

Apply rules:

```python
import path_file as pf

rules = pf.Rules.from_file("cleanup.toml")
chain = pf.find("~/Downloads").files()
result = rules.apply(chain)

# Dry run first
print(result.preview())

# Actually execute
result_chain = rules.apply(chain.dry_run(False))
```

## Generate Disk Usage Report

```python
import path_file as pf

report = pf.find("/data").report()
print(report.to_table())

# Save as JSON
report.to_json("/tmp/report.json")

# Save as CSV
report.to_csv("/tmp/report.csv")
```

## Rename Files in Batch

```python
import path_file as pf

# Pattern-based rename
pf.find("~/Photos").files().with_extension(".jpg").sort_by("date").rename(
    "IMG_{date:%Y%m%d}_{n:04d}{ext}"
).execute()

# Function-based rename
pf.find("~/Documents").files().with_extension(".txt").rename_with(
    lambda stem: stem.upper().replace(" ", "_")
).execute()
```

## Process Text Files

```python
import path_file as pf

# Find files containing "TODO"
chain = pf.find("~/Projects").files().with_extension(".py").matching_content("TODO")

for entry, lines in chain.grep("TODO"):
    print(f"{entry.path}:{lines}")

# Find files with specific pattern
chain = pf.find("~/Logs").files().matching_regex_in_content(r"ERROR \d{3}")

for entry, matches in chain.grep(r"ERROR \d{3}"):
    for line_num, match in matches:
        print(f"{entry.path}:{line_num}: {match}")
```

## Archive Old Projects

```python
import path_file as pf

pf.find("~/Projects").dirs().older_than("1 year").archive_to(
    "~/Archives/Projects_{date:%Y}.tar.gz", format="tar.gz"
).execute()
```

## Safe Delete with Trash

```python
import path_file as pf

# Move to trash instead of permanent delete
pf.find("~/Temp").files().older_than("7 days").trash(confirm=True).execute()
```

## Parallel Processing

```python
import path_file as pf

# Hash 10000 files in parallel
pf.find("~/LargeDataset").files().parallel(16).progress().hash().execute()
```

## Custom Filter Chain

```python
import path_file as pf

# Build complex filter
chain = (
    pf.find("~/Data")
    .files()
    .with_extensions(".csv", ".json", ".parquet")
    .between_sizes("1KB", "100MB")
    .newer_than("1 day")
    .not_in_folder("~/Data/temp")
    .sort_by("size", desc=True)
    .limit(100)
)

print(f"Found {chain.count()} files")
for entry in chain:
    print(f"{entry.path} ({entry.size_human})")
```