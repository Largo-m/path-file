# PathFlow

### Elegant, chainable file automation for Python.

**Find, filter, organize, synchronize, and manage files with a clean Python API and a powerful command-line interface.**

[![PyPI Version](https://img.shields.io/pypi/v/pathflow-toolkit?style=for-the-badge&color=7c3aed)](https://pypi.org/project/pathflow-toolkit/)
[![Python Versions](https://img.shields.io/pypi/pyversions/pathflow-toolkit?style=for-the-badge)](https://pypi.org/project/pathflow-toolkit/)
[![License](https://img.shields.io/github/license/Largo-m/path-file?style=for-the-badge)](LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/Largo-m/path-file/ci.yml?branch=main&style=for-the-badge&label=CI)](https://github.com/Largo-m/path-file/actions)
[![GitHub Stars](https://img.shields.io/github/stars/Largo-m/path-file?style=for-the-badge)](https://github.com/Largo-m/path-file/stargazers)

---

## Overview

Python's built-in `pathlib` and `shutil` are excellent tools, but handling complex file operations often requires repetitive code, nested loops, and custom filtering logic.

**PathFlow makes file automation simple.**

It provides a fluent, chainable API that lets you describe what you want to do instead of manually implementing every step.

```python
import path_file as pf

pf.find("~/Downloads") \
    .files() \
    .with_extension(".jpg") \
    .larger_than("2MB") \
    .older_than("30 days") \
    .move_to("~/Pictures/OldLarge") \
    .execute()
```

One readable pipeline. Multiple file operations. No unnecessary boilerplate.

## Features

| Feature | Description |
|---|---|
| Chainable API | Build readable file-processing pipelines |
| 40+ Filters | Filter by name, extension, size, date, content, permissions, and more |
| Safe Operations | Preview destructive operations with dry-run support |
| Parallel Execution | Run supported operations using multiple workers |
| Duplicate Detection | Identify duplicate files using hashes and names |
| Rich Reporting | Generate readable tables and structured reports |
| Directory Sync | Synchronize directories with hash-based verification |
| Folder Watching | Monitor directories for filesystem changes |
| Rules Engine | Define reusable automation rules using TOML |
| Archive Management | Create and extract archives |
| Full CLI | Use PathFlow directly from your terminal |
| Type Hints | Better IDE support and static type checking |

### Designed for practical automation

- **Readable:** Express complex operations through simple method chains.
- **Predictable:** Preview operations before making destructive changes.
- **Lightweight:** Core functionality uses the Python standard library.
- **Extensible:** Optional integrations are available when needed.
- **Developer-friendly:** Type hints, structured output, and a dedicated CLI.

---

## Installation

Requires **Python 3.10 or newer**.

Install the latest published version:

```bash
pip install pathflow-toolkit
```

Or install a specific version:

```bash
pip install pathflow-toolkit==0.1.2
```

Optional trash support:

```bash
pip install "pathflow-toolkit[trash]"
```

## Quick Start

### 1. Find files

```python
import path_file as pf

results = pf.find("~/Documents").files()

print("Found files:", results.count())
```

### 2. Filter files

```python
results = (
    pf.find("~/Downloads")
    .files()
    .with_extension(".pdf")
    .larger_than("1MB")
    .older_than("30 days")
)

print(results.to_table())
```

### 3. Generate a report

```python
report = pf.find("~/Documents").report()

print(report.to_table())
```

### 4. Preview file operations

PathFlow supports dry-run workflows so you can inspect an operation before applying it.

```python
result = (
    pf.find("~/Downloads")
    .files()
    .older_than("30 days")
    .delete(dry_run=True)
    .execute()
)

print(result.summary())
```

### 5. Execute an operation

After reviewing the preview, execute the operation with the required confirmation:

```python
pf.find("~/Downloads") \
    .files() \
    .older_than("30 days") \
    .delete(confirm=True) \
    .execute()
```

### 6. Synchronize directories

```python
syncer = pf.sync("~/Documents", "/backup/Documents")

syncer.direction("source_to_dest")
syncer.delete_extras(True)
syncer.progress()

diff = syncer.compare()
print(diff)

syncer.execute()
```

### 7. Use declarative rules

```python
rules = pf.Rules.from_file("cleanup.toml")

rules.apply(
    pf.find("~/Downloads").files()
)
```

---

## Command Line Interface

PathFlow includes a CLI for common file automation tasks.

### Find files

```bash
pathflow find ~/Downloads --ext .jpg --larger 2MB
```

### Generate reports

```bash
pathflow report ~/Documents --json
```

### Copy files

```bash
pathflow copy ~/Photos /backup/Photos --ext .jpg --parallel 4
```

### Delete files safely

```bash
pathflow delete ~/Temp --ext .tmp --confirm
```

### Synchronize directories

```bash
pathflow sync ~/Documents /backup/Documents --delete-extras --dry-run
```

### Find duplicates

```bash
pathflow duplicates ~/Photos
```

### Create archives

```bash
pathflow archive ~/Projects -o backup.zip
```

### Watch directories

```bash
pathflow watch ~/Downloads --filter "*.pdf" --on-new "notify.sh {}"
```

### Apply automation rules

```bash
pathflow rules ~/Downloads -f cleanup.toml --apply
```

For all available commands and options:

```bash
pathflow --help
```

---

## PathFlow vs. Standard Library

| Capability | pathlib | shutil | PathFlow |
|---|:---:|:---:|:---:|
| Chainable operations | — | — | Yes |
| Bulk file filtering | Manual | Limited | Yes |
| Dry-run workflows | Manual | — | Yes |
| Duplicate detection | Manual | — | Yes |
| Progress reporting | Manual | — | Yes |
| Parallel execution | Manual | — | Yes |
| Content search | Manual | — | Yes |
| Declarative rules | — | — | Yes |
| Directory synchronization | — | Limited | Yes |
| Command-line interface | — | — | Yes |
| Type hints | Yes | Partial | Yes |

---

## Documentation

Explore the project documentation:

| Resource | Description |
|---|---|
| [Quick Start](docs/quickstart.md) | Get started with PathFlow |
| [API Reference](docs/api.md) | Explore the Python API |
| [CLI Reference](docs/cli.md) | Learn all CLI commands |
| [Recipes](docs/recipes.md) | Practical automation examples |
| [Rules Engine](docs/rules.md) | Build TOML-based workflows |
| [Publishing Guide](PUBLISHING.md) | Package and release instructions |
| [Changelog](CHANGELOG.md) | Version history |

## Examples

The [`examples/`](examples/) directory contains practical scripts covering:

1. Cleaning old downloads
2. Organizing photos
3. Backing up documents
4. Finding duplicate files
5. Watching and sorting directories
6. Synchronizing folders
7. Declarative cleanup rules
8. Compressing old files
9. Batch renaming
10. Generating audit reports

---

## Development

Clone the repository:

```bash
git clone https://github.com/Largo-m/path-file.git
cd path-file
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows:

```powershell
.venv\Scripts\Activate.ps1
```

Activate it on Linux or macOS:

```bash
source .venv/bin/activate
```

Install development dependencies:

```bash
pip install -e ".[dev]"
```

Run tests:

```bash
pytest
```

Run tests with coverage:

```bash
pytest --cov=path_file --cov-report=term-missing
```

Run linting:

```bash
ruff check .
```

Run type checking:

```bash
mypy src/path_file
```

## Contributing

Contributions, bug reports, feature suggestions, and improvements are welcome.

Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting a pull request.

## Security

If you discover a security vulnerability, please follow the instructions in [SECURITY.md](SECURITY.md).

## License

PathFlow is released under the **MIT License**. See [LICENSE](LICENSE) for details.

---

<div align="center">

**PathFlow**

*Less boilerplate. More automation.*

Created and maintained by [Largo-m](https://github.com/Largo-m).

[GitHub Repository](https://github.com/Largo-m/path-file) · [PyPI Package](https://pypi.org/project/pathflow-toolkit/)

</div>