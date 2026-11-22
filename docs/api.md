# API Reference

## Core Entry Points

### `pf.find(path)` / `pf.scan(path)`

Create a FileChain from a directory path.

```python
chain = pf.find("~/Documents")  # Recursive by default
chain = pf.scan("~/Documents")  # Alias
chain = pf.current()  # Current working directory
```

### `pf.watch(path)`

Create a folder watcher.

```python
watcher = pf.watch("~/Downloads", poll_interval=1.0)
watcher.filter("*.jpg").on_new(callback)
watcher.run_forever()
```

### `pf.sync(source, dest)`

Create a directory syncer.

```python
syncer = pf.sync("~/Documents", "/backup/Documents")
syncer.direction("source_to_dest").delete_extras(True)
diff = syncer.compare()
syncer.execute()
```

## FileChain Methods

### Filters

| Method | Description |
|--------|-------------|
| `.files()` | Only regular files |
| `.dirs()` | Only directories |
| `.symlinks()` | Only symbolic links |
| `.all()` | All entries |
| `.with_extension(ext)` | Files with extension |
| `.with_extensions(*exts)` | Files with any extension |
| `.without_extension(ext)` | Files without extension |
| `.larger_than(size)` | Files larger than size |
| `.smaller_than(size)` | Files smaller than size |
| `.between_sizes(min, max)` | Files in size range |
| `.newer_than(duration)` | Modified recently |
| `.older_than(duration)` | Modified long ago |
| `.modified_between(start, end)` | Modified in range |
| `.created_between(start, end)` | Created in range |
| `.modified_today()` | Modified today |
| `.modified_this_week()` | Modified this week |
| `.modified_this_month()` | Modified this month |
| `.name_matches(regex)` | Name matches regex |
| `.name_contains(text)` | Name contains text |
| `.name_starts_with(prefix)` | Name starts with |
| `.name_ends_with(suffix)` | Name ends with |
| `.path_contains(text)` | Path contains text |
| `.path_matches(regex)` | Path matches regex |
| `.in_folder(path)` | Inside folder |
| `.not_in_folder(path)` | Not inside folder |
| `.empty()` | Empty files/dirs |
| `.not_empty()` | Non-empty files/dirs |
| `.hidden()` | Hidden entries |
| `.visible()` | Visible entries |
| `.readable()` | Readable entries |
| `.writable()` | Writable entries |
| `.executable()` | Executable entries |
| `.matching_content(text)` | File contains text |
| `.matching_regex_in_content(regex)` | File matches regex |
| `.containing_line(text)` | File contains line |
| `.containing_lines(*texts)` | File contains all lines |
| `.duplicates_by_hash(algo)` | Duplicate content |
| `.unique_by_hash()` | Unique content |
| `.duplicates_by_name()` | Duplicate names |
| `.unique_by_name()` | Unique names |
| `.same_size_as(path)` | Same size as reference |
| `.same_content_as(path)` | Same content as reference |

### Sorting & Limiting

| Method | Description |
|--------|-------------|
| `.sort_by(key, desc=False)` | Sort: name, size, date, created, path, extension |
| `.reverse()` | Reverse sort order |
| `.limit(n)` | Limit to first n |
| `.skip(n)` | Skip first n |
| `.slice(start, stop)` | Slice entries |
| `.deduplicate()` | Remove duplicate paths |

### Execution Modifiers

| Method | Description |
|--------|-------------|
| `.dry_run(bool)` | Enable dry-run |
| `.parallel(workers)` | Parallel execution |
| `.progress(bool)` | Show progress bar |
| `.verbose(bool)` | Verbose output |
| `.quiet(bool)` | Suppress output |
| `.on_error(action)` | "raise", "skip", "collect" |
| `.recursive(bool)` | Recursive traversal |
| `.follow_symlinks(bool)` | Follow symlinks |
| `.max_depth(n)` | Max recursion depth |
| `.min_depth(n)` | Min depth to yield |

### Materialization

| Method | Returns |
|--------|---------|
| `.count()` | int |
| `.first()` | Entry \| None |
| `.last()` | Entry \| None |
| `.to_list()` | List[Entry] |
| `.to_paths()` | List[Path] |
| `.to_dict()` | List[dict] |
| `.to_json(path?)` | str |
| `.to_csv(path?)` | str |
| `.to_table()` | str |
| `.report()` | Report |
| `.preview()` | str |
| `.for_each(callback)` | FileChain |
| `.map(callback)` | List |
| `.reduce(func, initial)` | Any |
| `.execute()` | ActionResult |

### Actions

| Method | Description |
|--------|-------------|
| `.copy_to(dest, **opts)` | Copy files |
| `.move_to(dest, **opts)` | Move files |
| `.delete(**opts)` | Delete files |
| `.trash(**opts)` | Move to trash |
| `.rename(pattern)` | Rename with pattern |
| `.rename_with(func)` | Rename with function |
| `.archive_to(path, format)` | Create archive |
| `.compress(format)` | Compress each file |
| `.extract_to(dest)` | Extract archives |
| `.chmod(mode)` | Change permissions |
| `.touch()` | Update mtime |
| `.read_text(encoding)` | Read as text |
| `.read_bytes()` | Read as bytes |
| `.write_text(data)` | Write text |
| `.write_bytes(data)` | Write bytes |
| `.hash(algorithm)` | Compute hash |
| `.open(mode)` | Open files |
| `.create_dir(mode)` | Create directories |
| `.symlink_to(target)` | Create symlinks |

## Entry Class

```python
entry.path  # Path (resolved)
entry.name  # str
entry.stem  # str
entry.suffix  # str
entry.extensions  # List[str]
entry.size  # int
entry.size_human  # str
entry.created  # datetime
entry.modified  # datetime
entry.accessed  # datetime
entry.modified_ago  # str
entry.is_file  # bool
entry.is_dir  # bool
entry.is_symlink  # bool
entry.is_hidden  # bool
entry.is_empty  # bool
entry.hash_sha256  # str (lazy)
entry.read_text()  # str
entry.read_bytes()  # bytes
entry.open(mode)  # file handle
entry.relative_to(base)  # Path
entry.as_dict()  # dict
```

## Report Class

```python
report.chain_size  # int
report.total_size  # int
report.by_extension  # Dict[str, int]
report.by_size_bucket  # Dict[str, int]
report.largest  # Entry
report.smallest  # Entry
report.oldest  # Entry
report.newest  # Entry
report.file_count  # int
report.dir_count  # int
report.symlink_count  # int
report.hidden_count  # int
report.empty_count  # int

report.to_dict()  # dict
report.to_json()  # str
report.to_csv()  # str
report.to_table()  # str
```

## ActionResult Class

```python
result.action  # str
result.count  # int
result.total_size  # int
result.duration  # float
result.errors  # List[Tuple[Path, Exception]]
result.skipped  # int
result.dry_run  # bool

result.success()  # bool
result.summary()  # str
result.to_dict()  # dict
```

## Units

```python
pf.parse_size("2.5 MB")  # int (bytes)
pf.human_size(2621440)  # "2.50 MiB"
pf.parse_duration("7 days")  # timedelta
pf.human_ago(datetime)  # "3 days ago"
pf.parse_datetime("today")  # datetime
pf.human_duration(td)  # "3d 4h"
```

## Utilities

```python
pf.size("1MB")  # int
pf.hsize(1024)  # "1.00 KiB"
pf.duration("1 hour")  # timedelta
pf.tempdir()  # Context manager
pf.mkdir(path)  # Path
pf.which("python")  # Path | None
pf.free_space(path)  # int
pf.disk_usage(path)  # (total, used, free)
pf.expand(path)  # Path
pf.safe_join(*parts)  # Path
pf.copy_file(src, dest)  # Path
pf.move_file(src, dest)  # Path
pf.delete_file(path)  # bool
pf.delete_dir(path)  # bool
pf.touch(path)  # Path
pf.read_text(path)  # str
pf.read_bytes(path)  # bytes
pf.write_text(path, data)  # Path
pf.write_bytes(path, data)  # Path
pf.symlink(target, link)  # Path
pf.readlink(path)  # Path
pf.is_symlink(path)  # bool
pf.resolve_link(path)  # Path
pf.run_command(cmd)  # CompletedProcess
pf.run_shell(cmd)  # CompletedProcess
pf.get_size(path)  # int
pf.get_size_human(path)  # str
pf.count_files(path)  # int
pf.find_largest(path, n)  # List[Path]
pf.find_oldest(path, n)  # List[Path]
pf.find_newest(path, n)  # List[Path]
pf.make_archive(src, dest)  # Path
pf.extract_archive(arc, dest)  # Path
pf.hash_file(path)  # str
pf.verify_hash(path, hash)  # bool
pf.is_binary(path)  # bool
pf.get_mime_type(path)  # str
pf.get_extension(path)  # str
pf.strip_extension(path)  # str
pf.change_extension(path, ext)  # Path
```

## Rules Engine

```python
rules = pf.Rules.from_file("rules.toml")
rules = pf.Rules.from_string(toml_string)
rules = pf.Rules.from_dict(dict)

errors = rules.validate()  # List[str]
explanation = rules.explain()  # str

chain = pf.find(path)
result_chain = rules.apply(chain)
```

### TOML Format

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

[[rule]]
match = "*.log"
action = "archive"
dest = "~/Archives/Logs"
```

### Actions

- `delete` - Delete files
- `trash` - Move to trash
- `move` - Move files (requires `dest`)
- `copy` - Copy files (requires `dest`)
- `archive` - Archive files (requires `dest`)
- `compress` - Compress files
- `rename` - Rename (requires `pattern`)

### Conditions

- `when_larger_than = "1MB"`
- `when_smaller_than = "100KB"`
- `when_older_than = "7 days"`
- `when_newer_than = "1 hour"`
- `when_size = "1MB-10MB"`
- `when_age = "1 day-30 days"`

## Watcher

```python
watcher = pf.watch(path, poll_interval=1.0, recursive=False)

watcher.filter("*.jpg")
watcher.filter_by(lambda e: e.size > 1000000)
watcher.debounce(1.0)

watcher.on_new(callback)
watcher.on_modified(callback)
watcher.on_deleted(callback)
watcher.on_moved(callback)

watcher.start()  # Background thread
watcher.stop()
watcher.run_forever()  # Blocking
watcher.run_for(60)  # Run for N seconds

with watcher:  # Context manager
    ...
```

## Syncer

```python
syncer = pf.sync(source, dest)

syncer.direction("source_to_dest")  # or "dest_to_source", "bidirectional"
syncer.ignore(["*.tmp", "build/"])
syncer.ignore_file(".syncignore")
syncer.delete_extras(True)
syncer.dry_run(True)
syncer.parallel(4)
syncer.progress(True)
syncer.hash_algorithm("sha256")
syncer.conflict_strategy("error")  # or "source_wins", "dest_wins", "newer_wins"

diff = syncer.compare()  # SyncDiff
result = syncer.execute()  # SyncResult
```

## Exceptions

All exceptions inherit from `pf.PathflowError` and have `.message` and `.hint` attributes.

| Exception | When Raised |
|-----------|-------------|
| `FileNotFoundError` | Path doesn't exist |
| `PermissionError` | Permission denied |
| `DestExistsError` | Destination exists, overwrite=False |
| `InvalidPatternError` | Invalid glob/regex |
| `InvalidSizeError` | Invalid size format |
| `InvalidDurationError` | Invalid duration format |
| `RulesParseError` | Rules TOML parse error |
| `DryRunRequiredError` | Destructive op without confirm |
| `SyncConflictError` | Bidirectional sync conflict |
| `WatchError` | Watcher error |
| `ArchiveError` | Archive operation failed |
| `HashError` | Hash computation failed |