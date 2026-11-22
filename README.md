# PathFile

> The elegant file automation library for Python.

[![PyPI](https://img.shields.io/pypi/v/path-file)](https://pypi.org/project/path-file/)
[![Python Versions](https://img.shields.io/pypi/pyversions/path-file)](https://pypi.org/project/path-file/)
[![License](https://img.shields.io/pypi/l/path-file)](LICENSE)
[![CI](https://github.com/Largo-m/path-file/workflows/CI/badge.svg)](https://github.com/Largo-m/path-file/actions)
[![Coverage](https://codecov.io/gh/Largo-m/path_file/branch/main/graph/badge.svg)](https://codecov.io/gh/Largo-m/path_file)

---

## Why PathFile?

Python's `pathlib` is great for single-file operations but painful for bulk operations, filtering, searching, and reporting. `shutil` has inconsistent APIs. Users end up writing 50-line scripts for tasks that should be 1 line.

**PathFile bridges this gap** with a chainable, declarative, dry-run-safe API.

```python
# Before: 30 lines of pathlib + shutil + os.walk
# After: 1 line with path_file
import path_file as pf

pf.find("~/Downloads").files().with_extension(".jpg").larger_than("2MB").older_than(
    "30 days"
).move_to("~/Pictures/OldLarge").execute()
```

## Features

- 🔗 **Chainable API** - Fluent interface for complex operations
- 🛡️ **Dry-run by default** - Safety first for destructive operations
- 📦 **Zero dependencies** - Only Python standard library
- 🎯 **40+ filters** - Size, time, name, path, content, duplicates, permissions
- ⚡ **20+ actions** - Copy, move, delete, archive, compress, hash, rename, sync
- 📊 **Rich reporting** - Tables, JSON, CSV, summary statistics
- 🔄 **Parallel execution** - Multi-threaded with progress bars
- 📝 **Declarative rules** - TOML-based automation rules
- 👀 **Folder watching** - Polling-based file monitoring
- 🔁 **Directory sync** - Hash-based bidirectional synchronization
- 🖥️ **Full CLI** - 12 commands for terminal use
- 🏷️ **Full type hints** - Strict mypy compliance, IDE autocomplete

## Installation

```bash
pip install path-file
```

Requires **Python 3.10+**

## Quick Start

```python
import path_file as pf

# Find and report
report = pf.find("~/Documents").report()
print(report.to_table())

# Batch operations with safety
pf.find("~/Downloads") \
  .files() \
  .older_than("30 days") \
  .delete(dry_run=True) \  # Preview first
  .execute()

# Actually delete (requires confirmation)
pf.find("~/Downloads") \
  .files() \
  .older_than("30 days") \
  .delete(confirm=True) \
  .execute()

# Organize photos by date
pf.find("~/Photos") \
  .files() \
  .with_extensions(".jpg", ".png", ".heic") \
  .for_each(lambda e: e.path.rename(f"~/Photos/Organized/{e.modified:%Y/%m}/{e.name}"))

# Sync with verification
syncer = pf.sync("~/Documents", "/backup/Documents")
syncer.direction("source_to_dest").delete_extras(True).progress()
diff = syncer.compare()
syncer.execute()

# Declarative rules
rules = pf.Rules.from_file("cleanup.toml")
rules.apply(pf.find("~/Downloads").files())
```

## Documentation

- [Quick Start](docs/quickstart.md)
- [API Reference](docs/api.md)
- [Recipes](docs/recipes.md)
- [Rules Engine](docs/rules.md)
- [CLI Reference](docs/cli.md)

## CLI Usage

```bash
# Find files
path-file find ~/Downloads --ext .jpg --larger 2MB

# Generate report
path-file report ~/Documents --json

# Copy with progress
path-file copy ~/Photos /backup/Photos --ext .jpg --parallel 4

# Safe delete (requires --confirm)
path-file delete ~/Temp --ext .tmp --confirm

# Sync directories
path-file sync ~/Documents /backup/Documents --delete-extras --dry-run

# Find duplicates
path-file duplicates ~/Photos

# Archive
path-file archive ~/Projects -o backup.zip

# Watch folder
path-file watch ~/Downloads --filter "*.pdf" --on-new "notify.sh {}"

# Apply rules
path-file rules ~/Downloads -f cleanup.toml --apply
```

## Comparison

| Feature | pathlib | shutil | path_file |
|---------|---------|--------|----------|
| Chainable API | ❌ | ❌ | ✅ |
| Bulk filtering | Manual | Limited | ✅ 40+ filters |
| Dry-run safety | Manual | ❌ | ✅ Default |
| Progress bars | ❌ | ❌ | ✅ Built-in |
| Parallel execution | Manual | ❌ | ✅ Built-in |
| Content search | Manual | ❌ | ✅ Text & regex |
| Duplicate detection | Manual | ❌ | ✅ By hash/name |
| Declarative rules | ❌ | ❌ | ✅ TOML |
| Folder watching | ❌ | ❌ | ✅ Polling |
| Directory sync | ❌ | Manual | ✅ Hash-based |
| CLI | ❌ | ❌ | ✅ 12 commands |
| Zero dependencies | ✅ | ✅ | ✅ |
| Type hints | ✅ | Partial | ✅ Strict |

## Examples

See [examples/](examples/) for 10 real-world scripts:

1. `01_clean_downloads.py` - Clean old downloads
2. `02_organize_photos.py` - Organize photos by date
3. `03_backup_documents.py` - Backup with hash verification
4. `04_find_duplicates.py` - Find and report duplicates
5. `05_watch_and_sort.py` - Auto-sort downloads
6. `06_sync_folders.py` - Bidirectional sync
7. `07_rules_declarative.py` - Rules-based cleanup
8. `08_compress_old_files.py` - Compress old files
9. `09_rename_batch.py` - Batch rename photos
10. `10_report_audit.py` - Generate audit reports

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Security

See [SECURITY.md](SECURITY.md) for security policy and vulnerability reporting.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for release history.

---

Made with ❤️ by [Largo-m](https://github.com/Largo-m)