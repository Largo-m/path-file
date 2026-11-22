# Rules Engine

Declarative file automation using TOML configuration files.

## Overview

The rules engine lets you define file automation rules in a TOML file, then apply them to any directory. This separates *what* to do from *how* to do it.

## Quick Start

Create `rules.toml`:

```toml
[[rule]]
match = "*.tmp"
when_older_than = "7 days"
action = "delete"

[[rule]]
match = "*.jpg"
when_larger_than = "10MB"
action = "move"
dest = "~/Pictures/Large"
```

Apply rules:

```python
import path_file as pf

rules = pf.Rules.from_file("rules.toml")
chain = pf.find("~/Downloads").files()

# Dry run (default)
result = rules.apply(chain)
print(result.preview())

# Execute
result = rules.apply(chain.dry_run(False))
```

## Rule Structure

```toml
[[rule]]
match = "*.ext"           # Glob pattern (required)
when_<condition> = "..."  # Optional conditions
action = "delete"         # Action to take
dest = "~/path"           # Destination (for move/copy/archive)
pattern = "..."           # Rename pattern (for rename action)
overwrite = false         # Overwrite existing
confirm = false           # Confirm destructive actions
dry_run = true            # Dry run by default
```

### Match Patterns

Uses glob patterns:
- `*.txt` - All .txt files
- `IMG_*.jpg` - Files starting with IMG_ and ending with .jpg
- `**/*.log` - All .log files recursively
- `temp_*` - Files starting with temp_

### Conditions

| Condition | Description |
|-----------|-------------|
| `when_larger_than` | File size greater than |
| `when_smaller_than` | File size less than |
| `when_older_than` | Modified longer ago than |
| `when_newer_than` | Modified more recently than |
| `when_size` | Size range (e.g., "1MB-10MB") |
| `when_age` | Age range (e.g., "1 day-30 days") |

All size values support: `B`, `KB`, `MB`, `GB`, `TB`
All duration values support: `s`, `m`, `h`, `d`, `w`, `month`, `year`

### Actions

| Action | Description | Required Fields |
|--------|-------------|-----------------|
| `delete` | Permanently delete | - |
| `trash` | Move to OS trash | - |
| `move` | Move to destination | `dest` |
| `copy` | Copy to destination | `dest` |
| `archive` | Add to archive | `dest` |
| `compress` | Compress file (gz/bz2/xz) | - |
| `rename` | Rename file | `pattern` |

### Rename Patterns

For `action = "rename"`, use `pattern` with placeholders:

```toml
[[rule]]
match = "*.jpg"
action = "rename"
pattern = "PHOTO_{date:%Y%m%d}_{n:04d}{ext}"
```

Placeholders:
- `{name}` - Original filename
- `{stem}` - Filename without extension
- `{ext}` - Extension (with dot)
- `{n}` - Sequential number (1, 2, 3...)
- `{n:04d}` - Zero-padded number (0001, 0002...)
- `{date}` - Current date (YYYY-MM-DD)
- `{date:%Y%m%d}` - Custom date format
- `{size}` - File size in bytes
- `{size_human}` - Human-readable size

## Complete Example

`cleanup.toml`:

```toml
# Delete temporary files older than 1 day
[[rule]]
match = "*.tmp"
when_older_than = "1 day"
action = "delete"

# Delete cache files
[[rule]]
match = "*.cache"
action = "delete"

# Move large images to separate folder
[[rule]]
match = "*.jpg"
when_larger_than = "50MB"
action = "move"
dest = "~/Pictures/Large"
overwrite = false

# Archive old logs
[[rule]]
match = "*.log"
when_older_than = "30 days"
action = "archive"
dest = "~/Archives/Logs"

# Compress old documents
[[rule]]
match = "*.pdf"
when_older_than = "1 year"
action = "compress"

# Rename screenshots
[[rule]]
match = "Screenshot*.png"
action = "rename"
pattern = "Screenshot_{date:%Y-%m-%d}_{n:03d}{ext}"
```

## Loading Rules

```python
import path_file as pf

# From file
rules = pf.Rules.from_file("rules.toml")

# From string
rules = pf.Rules.from_string(toml_content)

# From dictionary
rules = pf.Rules.from_dict({"rules": [...]})

# Validate
errors = rules.validate()
if errors:
    for err in errors:
        print(f"Error: {err}")

# Explain
print(rules.explain())

# Apply
chain = pf.find("~/Downloads").files()
result = rules.apply(chain.dry_run(False))
```

## Rule Priority

Rules are evaluated in order. The **first matching rule wins** for each file.

```toml
# This runs first - specific pattern
[[rule]]
match = "important_*.tmp"
action = "copy"
dest = "~/Important"

# This runs second - general pattern
[[rule]]
match = "*.tmp"
action = "delete"
```

## Dry Run

By default, `dry_run = true` for safety. Override per-rule or globally:

```python
# Per rule in TOML
[[rule]]
match = "*.tmp"
action = "delete"
dry_run = false  # This rule actually deletes

# Or globally
result = rules.apply(chain.dry_run(False))  # All rules execute
```

## Condition Combinations

Combine multiple conditions with multiple `when_` keys:

```toml
[[rule]]
match = "*.log"
when_older_than = "30 days"
when_larger_than = "10MB"
action = "archive"
dest = "~/Archives/Logs"
```

All conditions must be true (AND logic).

## Best Practices

1. **Always dry-run first** - Use `rules.apply(chain)` to preview
2. **Order matters** - Specific rules before general rules
3. **Test on copy** - Apply to a test directory first
4. **Use confirm** - Add `confirm = true` for destructive actions
5. **Version control** - Keep rules.toml in git

## Migration from Scripts

Convert imperative scripts to declarative rules:

```python
# Before: Imperative script
for f in Path("~/Downloads").glob("*.tmp"):
    if f.stat().st_mtime < time.time() - 86400:
        f.unlink()

# After: Declarative rule
# rules.toml:
# [[rule]]
# match = "*.tmp"
# when_older_than = "1 day"
# action = "delete"
```