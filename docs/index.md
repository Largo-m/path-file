# PathFile Documentation

> The elegant file automation library for Python.

## Quick Links

- [Quick Start](quickstart.md)
- [API Reference](api.md)
- [Recipes](recipes.md)
- [Rules Engine](rules.md)
- [CLI Reference](cli.md)

## Overview

path-file is a zero-dependency Python library that makes file automation simple, safe, and expressive. It bridges the gap between `pathlib` (great for single files) and `shutil` (inconsistent APIs) with a chainable, declarative API.

### Key Features

- **Chainable API**: `pf.find(path).files().with_extension(".jpg").copy_to(dest)`
- **Dry-run by default**: Destructive operations require explicit confirmation
- **Zero dependencies**: Only Python standard library
- **Type-safe**: Full type hints with IDE autocomplete
- **Progress reporting**: Beautiful ASCII progress bars
- **Parallel execution**: Multi-threaded operations
- **Declarative rules**: TOML-based automation rules
- **Folder watching**: Polling-based file monitoring
- **Directory sync**: Hash-based synchronization

## Installation

```bash
pip install path-file
```

Requires Python 3.10+

## Quick Example

```python
import path_file as pf

# Find all JPEG files larger than 2MB in Downloads
pf.find("~/Downloads").files().with_extension(".jpg").larger_than("2MB").copy_to(
    "~/Pictures/Large"
).execute()
```

## Philosophy

- **Simple in appearance, powerful in depth**
- **Progressive disclosure**: 90% of use cases = 1 line
- **Safety first**: Dry-run by default for destructive operations
- **Helpful errors**: Actionable hints with every exception
- **Beautiful output**: Progress bars, tables, reports