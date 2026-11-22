# CLI Reference

path-file provides a command-line interface for common file operations.

## Installation

```bash
pip install path-file
```

## Global Options

| Option | Description |
|--------|-------------|
| `-v, --verbose` | Verbose output |
| `-q, --quiet` | Quiet output |
| `-n, --dry-run` | Dry run (no changes) |
| `--json` | Output JSON |
| `--version` | Show version |
| `--help` | Show help |

## Commands

### `find` - Find Files

```bash
path-file find PATH [OPTIONS]
```

**Options:**
| Option | Description |
|--------|-------------|
| `-r, --recursive / --no-recursive` | Recursive search (default: true) |
| `--ext, --extension EXT` | File extension filter (repeatable) |
| `--name TEXT` | Name contains text |
| `--pattern GLOB` | Glob pattern |
| `--regex REGEX` | Regex pattern |
| `--larger SIZE` | Larger than size (e.g., 1MB) |
| `--smaller SIZE` | Smaller than size |
| `--newer DURATION` | Newer than (e.g., 7 days) |
| `--older DURATION` | Older than |
| `--hidden` | Include hidden files |
| `--empty` | Only empty files |
| `--sort KEY` | Sort by: name, size, date, path |
| `--reverse` | Reverse sort |
| `--limit N` | Limit results |
| `--files` | Only files |
| `--dirs` | Only directories |

**Examples:**
```bash
# Find all JPGs
path-file find ~/Pictures --ext .jpg

# Find large files
path-file find ~/Downloads --larger 100MB

# Find old files
path-file find ~/Temp --older "30 days" --ext .tmp

# JSON output
path-file find ~/Projects --ext .py --json
```

### `report` - Generate Report

```bash
path-file report PATH [OPTIONS]
```

**Options:**
| Option | Description |
|--------|-------------|
| `--by-ext` | Show by extension |
| `--by-size` | Show by size buckets |
| `--extremes` | Show largest/smallest/newest/oldest |

**Examples:**
```bash
path-file report ~/Documents
path-file report ~/Data --json
```

### `copy` - Copy Files

```bash
path-file copy SOURCE DEST [OPTIONS]
```

**Options:**
| Option | Description |
|--------|-------------|
| `-r, --recursive / --no-recursive` | Recursive (default: true) |
| `--ext EXT` | Extension filter |
| `--overwrite` | Overwrite existing |
| `--preserve / --no-preserve` | Preserve metadata (default: true) |
| `-p, --parallel N` | Parallel workers (default: 1) |

**Examples:**
```bash
path-file copy ~/Photos /backup/Photos --ext .jpg --overwrite
path-file copy ~/Documents /mnt/backup --parallel 4
```

### `move` - Move Files

```bash
path-file move SOURCE DEST [OPTIONS]
```

**Options:** Same as copy.

### `delete` - Delete Files

```bash
path-file delete PATH [OPTIONS]
```

**Options:**
| Option | Description |
|--------|-------------|
| `-r, --recursive / --no-recursive` | Recursive (default: true) |
| `--ext EXT` | Extension filter |
| `--older DURATION` | Older than |
| `--larger SIZE` | Larger than |
| `--pattern GLOB` | Glob pattern |
| `--confirm` | **Required** for actual deletion |
| `--trash` | Move to trash instead |

**Examples:**
```bash
# Dry run (default)
path-file delete ~/Temp --ext .tmp

# Actually delete (requires --confirm)
path-file delete ~/Temp --ext .tmp --confirm

# Move to trash
path-file delete ~/Downloads --older "7 days" --trash --confirm
```

### `hash` - Compute Hashes

```bash
path-file hash PATH [OPTIONS]
```

**Options:**
| Option | Description |
|--------|-------------|
| `-a, --algorithm ALGO` | Hash algorithm: md5, sha1, sha256, sha512 (default: sha256) |
| `-r, --recursive / --no-recursive` | Recursive (default: true) |

**Examples:**
```bash
path-file hash ~/Documents --algorithm sha256
path-file hash file.txt -a md5
```

### `duplicates` - Find Duplicates

```bash
path-file duplicates PATH [OPTIONS]
```

**Options:**
| Option | Description |
|--------|-------------|
| `-a, --algorithm ALGO` | Hash algorithm (default: sha256) |
| `-r, --recursive / --no-recursive` | Recursive (default: true) |
| `--by-name` | Find by filename instead of content |

**Examples:**
```bash
path-file duplicates ~/Photos
path-file duplicates ~/Downloads --by-name
```

### `archive` - Create Archive

```bash
path-file archive PATH -o OUTPUT [OPTIONS]
```

**Options:**
| Option | Description |
|--------|-------------|
| `-o, --output PATH` | Output archive path (required) |
| `-f, --format FORMAT` | Format: zip, tar, tar.gz, tar.bz2, tar.xz (default: zip) |

**Examples:**
```bash
path-file archive ~/Projects -o backup.zip
path-file archive ~/Data -o backup.tar.gz -f tar.gz
```

### `extract` - Extract Archive

```bash
path-file extract ARCHIVE -o OUTPUT
```

**Options:**
| Option | Description |
|--------|-------------|
| `-o, --output PATH` | Output directory (required) |

**Examples:**
```bash
path-file extract backup.zip -o ~/restored
```

### `watch` - Watch Directory

```bash
path-file watch PATH [OPTIONS]
```

**Options:**
| Option | Description |
|--------|-------------|
| `-i, --interval SECONDS` | Poll interval (default: 1.0) |
| `--filter GLOB` | Glob filter |
| `--debounce SECONDS` | Debounce time |
| `--on-new CMD` | Command for new files (use `{}` for path) |
| `--on-modified CMD` | Command for modified files |
| `--on-deleted CMD` | Command for deleted files |
| `--duration SECONDS` | Run for N seconds |

**Examples:**
```bash
# Watch and print new files
path-file watch ~/Downloads --filter "*.jpg" --on-new "echo New: {}"

# Watch for 60 seconds
path-file watch ~/Incoming --duration 60 --on-new "process.sh {}"
```

### `sync` - Synchronize Directories

```bash
path-file sync SOURCE DEST [OPTIONS]
```

**Options:**
| Option | Description |
|--------|-------------|
| `--direction DIR` | source_to_dest, dest_to_source, bidirectional (default: source_to_dest) |
| `--delete-extras` | Delete files in dest not in source |
| `--ignore PATTERN` | Ignore pattern (repeatable) |
| `--ignore-file PATH` | Ignore file (.gitignore style) |
| `--conflict STRATEGY` | error, source_wins, dest_wins, newer_wins (default: error) |
| `-p, --parallel N` | Parallel workers (default: 4) |

**Examples:**
```bash
# Dry run sync
path-file sync ~/Documents /backup/Documents --dry-run

# Sync with delete
path-file sync ~/Projects /backup/Projects --delete-extras

# Bidirectional with conflict resolution
path-file sync ~/FolderA ~/FolderB --direction bidirectional --conflict newer_wins
```

### `rules` - Apply Rules

```bash
path-file rules PATH -f RULES_FILE [OPTIONS]
```

**Options:**
| Option | Description |
|--------|-------------|
| `-f, --file PATH` | Rules TOML file (required) |
| `--apply` | Actually apply (not dry-run) |

**Examples:**
```bash
# Dry run
path-file rules ~/Downloads -f cleanup.toml

# Apply rules
path-file rules ~/Downloads -f cleanup.toml --apply
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid arguments |
| 3 | Dry-run required (confirm needed) |
| 4 | No matches found |
| 130 | Interrupted (Ctrl+C) |

## Examples

### Daily Cleanup Script

```bash
#!/bin/bash
# cleanup.sh - Daily cleanup

# Clean temp files older than 7 days
path-file delete /tmp --pattern "*.tmp" --older "7 days" --confirm

# Archive old logs
path-file archive /var/log/myapp -o /archive/logs_$(date +%Y%m%d).tar.gz -f tar.gz

# Sync documents
path-file sync ~/Documents /mnt/backup/Documents --delete-extras
```

### Find Large Files

```bash
# Find files larger than 100MB
path-file find ~ --larger 100MB --sort size --reverse --limit 20

# JSON for scripting
path-file find ~/Projects --ext .log --larger 10MB --json | jq '.[] | {path, size_human}'
```

### Batch Processing

```bash
# Hash all files in directory
path-file hash ~/Dataset --algorithm sha256 > hashes.txt

# Find duplicates
path-file duplicates ~/Photos --algorithm sha256
```