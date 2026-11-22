# Quick Start

## Installation

```bash
pip install path-file
```

## Basic Usage

```python
import path_file as pf

# Find files
files = pf.find("~/Documents").files().to_list()

# Filter and act
pf.find("~/Downloads").files().with_extension(".pdf").older_than("30 days").move_to(
    "~/Archive/OldPDFs"
).execute()
```

## Common Patterns

### Find and Report

```python
# Generate a report of a directory
report = pf.find("~/Projects").report()
print(report.to_table())
```

### Batch Operations

```python
# Rename files with pattern
pf.find("~/Photos").files().with_extension(".jpg").rename(
    "IMG_{date:%Y%m%d}_{n:04d}{ext}"
).execute()
```

### Dry Run First

```python
# Preview what would happen
chain = pf.find("~/Temp").files().older_than("7 days")
print(chain.preview())  # Dry-run preview

# Actually delete (requires confirm=True)
chain.delete(confirm=True).execute()
```

## Next Steps

- [API Reference](api.md) - Complete API documentation
- [Recipes](recipes.md) - Real-world examples
- [Rules Engine](rules.md) - Declarative automation
- [CLI Reference](cli.md) - Command-line usage