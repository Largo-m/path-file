# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-11-22

### Added
- Initial release of path_file
- **FileChain**: Immutable, lazy, chainable file collection
- **40+ Filters**: files, dirs, extensions, size, time, name, path, visibility, permissions, content, duplicates
- **20+ Actions**: copy, move, delete, trash, rename, archive, compress, extract, chmod, touch, read/write, hash
- **Execution Modifiers**: dry-run, parallel, progress, verbose, error handling
- **Materialization**: count, first, last, to_list, to_paths, to_dict, to_json, to_csv, to_table, report, preview
- **Entry Class**: Rich metadata with lazy properties (size, dates, hash, content)
- **Report Class**: Aggregate statistics with table, JSON, CSV output
- **Units**: parse_size, human_size, parse_duration, human_ago, parse_datetime, human_duration
- **Rules Engine**: Declarative TOML-based automation rules
- **Watcher**: Polling-based folder monitoring with callbacks
- **Syncer**: Hash-based directory synchronization with conflict resolution
- **Hash Utilities**: SHA-256, MD5, duplicate detection, verification
- **Archive Utilities**: ZIP, TAR, TAR.GZ, TAR.BZ2, TAR.XZ, GZ, BZ2, XZ
- **Search**: Content search with text and regex
- **CLI**: Full command-line interface with 12 commands
- **Utilities**: 30+ helper functions for common file operations
- **Zero Dependencies**: Only Python standard library
- **Full Type Hints**: Strict mypy compliance
- **Comprehensive Tests**: 26 test files, 875 tests, 85% line coverage
- **Release-Gated Quality**: ruff check + ruff format --check + mypy strict + pytest --cov-fail-under=85 + twine check, all passing
- **Documentation**: API reference, quickstart, recipes, rules, CLI guide

### Security
- Path traversal protection in archive extraction
- Dry-run by default for destructive operations
- Explicit confirmation required for delete/trash
- Safe path validation utilities

### Performance
- os.scandir-based iteration (not os.walk)
- Parallel execution with ThreadPoolExecutor
- Streaming hash computation for large files
- Cached regex compilation
- Efficient size/time filtering (cutoff computed once)

## [Unreleased]

### Planned for v0.2.0
- Async/await support
- More archive formats (RAR, 7Z)
- EXIF/metadata support for photos
- Faster duplicate detection (xxhash)
- Configuration file (path_file.toml)
- Plugin system
- Web UI for rules management