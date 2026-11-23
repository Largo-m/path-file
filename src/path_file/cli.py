"""Command-line interface for path_file using stdlib argparse."""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from path_file.watch import WatchEvent

import path_file as pf
from path_file._version import __version__
from path_file.exceptions import DryRunRequiredError, PathflowError

# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point."""
    # Avoid crashes on Windows consoles that cannot encode box-drawing /
    # non-ASCII characters; replace unencodable characters instead of raising.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            with contextlib.suppress(ValueError, OSError):
                reconfigure(errors="replace")

    parser = _create_parser()
    args = parser.parse_args(argv)

    # Set verbosity
    if args.verbose:
        pf.verbose()
    elif args.quiet:
        pf.quiet()

    try:
        # Every command handler registered via set_defaults(func=...) is
        # annotated to return ``int``.
        return cast(int, args.func(args))
    except DryRunRequiredError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 3
    except PathflowError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130
    except Exception as e:
        if args.verbose:
            import traceback

            traceback.print_exc()
        print(f"Error: {e}", file=sys.stderr)
        return 1


# ──────────────────────────────────────────────────────────────────────────────
# PARSER CREATION
# ──────────────────────────────────────────────────────────────────────────────


def _create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="path_file",
        description="The elegant file automation library for Python",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  path_file find ~/Downloads --ext .jpg --larger 2MB
  path_file report ~/Documents --by-ext
  path_file copy ~/Photos /backup/Photos --dry-run
  path_file delete ~/Downloads/*.tmp --confirm
  path_file sync ~/Documents /mnt/backup --delete-extras
  path_file watch ~/Downloads --on-new "echo New file: {}"
        """,
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("-q", "--quiet", action="store_true", help="Quiet output")
    parser.add_argument("-n", "--dry-run", action="store_true", help="Dry run (no changes)")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--version", action="version", version=f"path_file {__version__}")

    # Common flags shared by all subcommands (usable before OR after the command).
    # default=SUPPRESS so a value set by the main parser is not overwritten
    # by the subparser's default.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "-v", "--verbose", action="store_true", default=argparse.SUPPRESS, help="Verbose output"
    )
    common.add_argument(
        "-q", "--quiet", action="store_true", default=argparse.SUPPRESS, help="Quiet output"
    )
    common.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Dry run (no changes)",
    )
    common.add_argument(
        "--json", action="store_true", default=argparse.SUPPRESS, help="Output JSON"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # find
    _add_find_parser(subparsers, common)
    # report
    _add_report_parser(subparsers, common)
    # copy
    _add_copy_parser(subparsers, common)
    # move
    _add_move_parser(subparsers, common)
    # delete
    _add_delete_parser(subparsers, common)
    # hash
    _add_hash_parser(subparsers, common)
    # duplicates
    _add_duplicates_parser(subparsers, common)
    # archive
    _add_archive_parser(subparsers, common)
    # extract
    _add_extract_parser(subparsers, common)
    # watch
    _add_watch_parser(subparsers, common)
    # sync
    _add_sync_parser(subparsers, common)
    # rules
    _add_rules_parser(subparsers, common)

    return parser


# ──────────────────────────────────────────────────────────────────────────────
# COMMAND PARSERS
# ──────────────────────────────────────────────────────────────────────────────


def _add_find_parser(subparsers: Any, parents: argparse.ArgumentParser) -> None:
    p = subparsers.add_parser("find", help="Find files", parents=[parents])
    p.add_argument("path", type=Path, help="Root directory")
    p.add_argument(
        "-r", "--recursive", action="store_true", default=True, help="Recursive (default)"
    )
    p.add_argument("--no-recursive", dest="recursive", action="store_false", help="Non-recursive")
    p.add_argument(
        "--ext", "--extension", action="append", dest="extensions", help="File extension"
    )
    p.add_argument("--name", help="Name contains")
    p.add_argument("--pattern", help="Glob pattern")
    p.add_argument("--regex", help="Regex pattern")
    p.add_argument("--larger", help="Larger than size (e.g., 1MB)")
    p.add_argument("--smaller", help="Smaller than size")
    p.add_argument("--newer", help="Newer than duration (e.g., 7 days)")
    p.add_argument("--older", help="Older than duration")
    p.add_argument("--hidden", action="store_true", help="Include hidden")
    p.add_argument("--empty", action="store_true", help="Only empty")
    p.add_argument("--sort", choices=["name", "size", "date", "path"], help="Sort by")
    p.add_argument("--reverse", action="store_true", help="Reverse sort")
    p.add_argument("--limit", type=int, help="Limit results")
    p.add_argument("--files", action="store_true", help="Only files")
    p.add_argument("--dirs", action="store_true", help="Only directories")
    p.set_defaults(func=_cmd_find)


def _add_report_parser(subparsers: Any, parents: argparse.ArgumentParser) -> None:
    p = subparsers.add_parser("report", help="Generate report", parents=[parents])
    p.add_argument("path", type=Path, help="Root directory")
    p.add_argument(
        "-r", "--recursive", action="store_true", default=True, help="Recursive (default)"
    )
    p.add_argument("--no-recursive", dest="recursive", action="store_false", help="Non-recursive")
    p.add_argument("--by-ext", action="store_true", help="Show by extension")
    p.add_argument("--by-size", action="store_true", help="Show by size")
    p.add_argument("--extremes", action="store_true", help="Show largest/smallest/newest/oldest")
    p.set_defaults(func=_cmd_report)


def _add_copy_parser(subparsers: Any, parents: argparse.ArgumentParser) -> None:
    p = subparsers.add_parser("copy", help="Copy files", parents=[parents])
    p.add_argument("source", type=Path, help="Source path")
    p.add_argument("dest", type=Path, help="Destination directory")
    p.add_argument("-r", "--recursive", action="store_true", default=True)
    p.add_argument("--ext", action="append", help="Extension filter")
    p.add_argument("--overwrite", action="store_true", help="Overwrite existing")
    p.add_argument("--preserve", action="store_true", default=True, help="Preserve metadata")
    p.add_argument("-p", "--parallel", type=int, default=1, help="Parallel workers")
    p.set_defaults(func=_cmd_copy)


def _add_move_parser(subparsers: Any, parents: argparse.ArgumentParser) -> None:
    p = subparsers.add_parser("move", help="Move files", parents=[parents])
    p.add_argument("source", type=Path, help="Source path")
    p.add_argument("dest", type=Path, help="Destination directory")
    p.add_argument("-r", "--recursive", action="store_true", default=True)
    p.add_argument("--ext", action="append", help="Extension filter")
    p.add_argument("--overwrite", action="store_true", help="Overwrite existing")
    p.set_defaults(func=_cmd_move)


def _add_delete_parser(subparsers: Any, parents: argparse.ArgumentParser) -> None:
    p = subparsers.add_parser("delete", help="Delete files", parents=[parents])
    p.add_argument("path", type=Path, help="Path to delete from")
    p.add_argument("-r", "--recursive", action="store_true", default=True)
    p.add_argument("--ext", action="append", help="Extension filter")
    p.add_argument("--older", help="Older than duration")
    p.add_argument("--larger", help="Larger than size")
    p.add_argument("--pattern", help="Glob pattern")
    p.add_argument("--confirm", action="store_true", required=False, help="Confirm deletion")
    p.add_argument("--trash", action="store_true", help="Move to trash instead")
    p.set_defaults(func=_cmd_delete)


def _add_hash_parser(subparsers: Any, parents: argparse.ArgumentParser) -> None:
    p = subparsers.add_parser("hash", help="Compute file hashes", parents=[parents])
    p.add_argument("path", type=Path, help="File or directory")
    p.add_argument(
        "-a", "--algorithm", default="sha256", choices=["md5", "sha1", "sha256", "sha512"]
    )
    p.add_argument("-r", "--recursive", action="store_true", default=True)
    p.set_defaults(func=_cmd_hash)


def _add_duplicates_parser(subparsers: Any, parents: argparse.ArgumentParser) -> None:
    p = subparsers.add_parser("duplicates", help="Find duplicate files", parents=[parents])
    p.add_argument("path", type=Path, help="Directory to scan")
    p.add_argument("-a", "--algorithm", default="sha256")
    p.add_argument("-r", "--recursive", action="store_true", default=True)
    p.add_argument("--by-name", action="store_true", help="Find by name instead of content")
    p.set_defaults(func=_cmd_duplicates)


def _add_archive_parser(subparsers: Any, parents: argparse.ArgumentParser) -> None:
    p = subparsers.add_parser("archive", help="Create archive", parents=[parents])
    p.add_argument("path", type=Path, help="Directory or files to archive")
    p.add_argument("-r", "--recursive", action="store_true", default=True)
    p.add_argument("-o", "--output", type=Path, required=True, help="Output archive path")
    p.add_argument(
        "-f", "--format", default="zip", choices=["zip", "tar", "tar.gz", "tar.bz2", "tar.xz"]
    )
    p.set_defaults(func=_cmd_archive)


def _add_extract_parser(subparsers: Any, parents: argparse.ArgumentParser) -> None:
    p = subparsers.add_parser("extract", help="Extract archive", parents=[parents])
    p.add_argument("archive", type=Path, help="Archive file")
    p.add_argument("-r", "--recursive", action="store_true", default=True)
    p.add_argument("-o", "--output", type=Path, required=True, help="Output directory")
    p.set_defaults(func=_cmd_extract)


def _add_watch_parser(subparsers: Any, parents: argparse.ArgumentParser) -> None:
    p = subparsers.add_parser("watch", help="Watch directory for changes", parents=[parents])
    p.add_argument("path", type=Path, help="Directory to watch")
    p.add_argument("-i", "--interval", type=float, default=1.0, help="Poll interval")
    p.add_argument("--filter", help="Glob filter")
    p.add_argument("--debounce", type=float, default=0, help="Debounce seconds")
    p.add_argument("--on-new", help="Command for new files (use {} for path)")
    p.add_argument("--on-modified", help="Command for modified files")
    p.add_argument("--on-deleted", help="Command for deleted files")
    p.add_argument("--duration", type=float, help="Run for N seconds")
    p.set_defaults(func=_cmd_watch)


def _add_sync_parser(subparsers: Any, parents: argparse.ArgumentParser) -> None:
    p = subparsers.add_parser("sync", help="Synchronize directories", parents=[parents])
    p.add_argument("source", type=Path, help="Source directory")
    p.add_argument("dest", type=Path, help="Destination directory")
    p.add_argument("-r", "--recursive", action="store_true", default=True)
    p.add_argument(
        "--direction",
        choices=["source_to_dest", "dest_to_source", "bidirectional"],
        default="source_to_dest",
    )
    p.add_argument(
        "--delete-extras", action="store_true", help="Delete files in dest not in source"
    )
    p.add_argument("--ignore", action="append", help="Ignore pattern")
    p.add_argument("--ignore-file", type=Path, help="Ignore file (.gitignore style)")
    p.add_argument(
        "--conflict", choices=["error", "source_wins", "dest_wins", "newer_wins"], default="error"
    )
    p.add_argument("-p", "--parallel", type=int, default=4)
    p.set_defaults(func=_cmd_sync)


def _add_rules_parser(subparsers: Any, parents: argparse.ArgumentParser) -> None:
    p = subparsers.add_parser("rules", help="Apply rules from TOML file", parents=[parents])
    p.add_argument("path", type=Path, help="Directory to apply rules to")
    p.add_argument("-r", "--recursive", action="store_true", default=True)
    p.add_argument("-f", "--file", type=Path, required=True, help="Rules file")
    p.add_argument("--apply", action="store_true", help="Actually apply (not dry-run)")
    p.set_defaults(func=_cmd_rules)


# ──────────────────────────────────────────────────────────────────────────────
# COMMAND IMPLEMENTATIONS
# ──────────────────────────────────────────────────────────────────────────────


def _build_chain(args: argparse.Namespace) -> pf.FileChain:
    """Build FileChain from common find arguments.

    Tolerant of different subparsers: uses ``source``/``path`` for the root and
    ``extensions``/``ext`` for extension filters.
    """
    root = getattr(args, "path", None) or getattr(args, "source", None) or "."
    chain = pf.find(root)

    if not getattr(args, "recursive", True):
        chain = chain.recursive(False)

    if getattr(args, "files", False):
        chain = chain.files()
    if getattr(args, "dirs", False):
        chain = chain.dirs()

    extensions = getattr(args, "extensions", None) or getattr(args, "ext", None)
    if extensions:
        chain = chain.with_extensions(*extensions)

    if getattr(args, "name", None):
        chain = chain.name_contains(args.name)

    if getattr(args, "pattern", None):
        chain = chain.glob(args.pattern)

    if getattr(args, "regex", None):
        chain = chain.name_matches_regex(args.regex)

    if getattr(args, "larger", None):
        chain = chain.larger_than(args.larger)

    if getattr(args, "smaller", None):
        chain = chain.smaller_than(args.smaller)

    if getattr(args, "newer", None):
        chain = chain.newer_than(args.newer)

    if getattr(args, "older", None):
        chain = chain.older_than(args.older)

    if getattr(args, "hidden", False):
        chain = chain.hidden()

    if getattr(args, "empty", False):
        chain = chain.empty()

    if getattr(args, "sort", None):
        chain = chain.sort_by(args.sort, desc=getattr(args, "reverse", False))

    if getattr(args, "limit", None):
        chain = chain.limit(args.limit)

    if getattr(args, "dry_run", False):
        chain = chain.dry_run(True)

    if getattr(args, "parallel", 1) > 1:
        chain = chain.parallel(args.parallel)

    return chain


def _cmd_find(args: argparse.Namespace) -> int:
    chain = _build_chain(args)

    if args.json:
        print(chain.to_json())
    else:
        print(chain.to_table())

    return 0 if chain.count() > 0 else 4


def _cmd_report(args: argparse.Namespace) -> int:
    chain = pf.find(args.path)
    if not args.recursive:
        chain = chain.recursive(False)

    report = chain.report()

    if args.json:
        print(report.to_json())
    else:
        print(report.to_table())

    return 0


def _cmd_copy(args: argparse.Namespace) -> int:
    chain = _build_chain(args)
    result = chain.copy_to(
        args.dest, overwrite=args.overwrite, preserve_metadata=args.preserve
    ).execute()
    print(result.summary())
    return 0 if result.success() else 1


def _cmd_move(args: argparse.Namespace) -> int:
    chain = _build_chain(args).dry_run(args.dry_run)
    result = chain.move_to(args.dest, overwrite=args.overwrite).execute()
    print(result.summary())
    return 0 if result.success() else 1


def _cmd_delete(args: argparse.Namespace) -> int:
    chain = _build_chain(args)

    if args.trash:
        result = chain.trash(dry_run=args.dry_run, confirm=args.confirm).execute()
    else:
        result = chain.delete(dry_run=args.dry_run, confirm=args.confirm).execute()

    print(result.summary())
    return 0 if result.success() else 1


def _cmd_hash(args: argparse.Namespace) -> int:
    from path_file.utils import hash_file

    path = args.path
    if path.is_file():
        files = [path]
    else:
        chain = pf.find(path)
        if not args.recursive:
            chain = chain.recursive(False)
        files = [e.path for e in chain.files()]

    if args.json:
        data = [{"hash": hash_file(f, algorithm=args.algorithm), "path": str(f)} for f in files]
        print(json.dumps(data, indent=2))
    else:
        for f in files:
            print(f"{hash_file(f, algorithm=args.algorithm)}  {f}")

    return 0


def _cmd_duplicates(args: argparse.Namespace) -> int:
    chain = pf.find(args.path)
    if not args.recursive:
        chain = chain.recursive(False)
    chain = chain.files()

    dupes = chain.duplicates_by_name() if args.by_name else chain.duplicates_by_hash(args.algorithm)

    if args.json:
        print(json.dumps(dupes, indent=2, default=str))
    else:
        for hash_val, entries in dupes.items():
            print(f"\n{hash_val[:16]}... ({len(entries)} files):")
            for e in entries:
                print(f"  {e.path} ({e.size_human})")

    return 0


def _cmd_archive(args: argparse.Namespace) -> int:
    chain = _build_chain(args).files()

    result = chain.archive_to(args.output, format=args.format).execute()
    print(result.summary())
    return 0 if result.success() else 1


def _cmd_extract(args: argparse.Namespace) -> int:
    if not args.archive.is_file():
        raise PathflowError(f"Archive not found: {args.archive}")
    chain = pf.find(args.archive).files()
    result = chain.extract_to(args.output).execute()
    print(result.summary())
    return 0 if result.success() else 1


def _cmd_watch(args: argparse.Namespace) -> int:
    watcher = pf.watch(args.path, poll_interval=args.interval)

    if args.filter:
        watcher.filter(args.filter)

    if args.debounce:
        watcher.debounce(args.debounce)

    def make_callback(cmd_template: str) -> Callable[[WatchEvent], None]:
        def callback(event: WatchEvent) -> None:
            cmd = cmd_template.replace("{}", str(event.path))
            import subprocess

            # shell command template is the documented user-facing API
            subprocess.run(cmd, shell=True)  # noqa: S602  # user-provided shell command API

        return callback

    if args.on_new:
        watcher.on_new(make_callback(args.on_new))
    if args.on_modified:
        watcher.on_modified(make_callback(args.on_modified))
    if args.on_deleted:
        watcher.on_deleted(make_callback(args.on_deleted))

    if args.duration:
        watcher.run_for(args.duration)
    else:
        watcher.run_forever()

    return 0


def _cmd_sync(args: argparse.Namespace) -> int:
    syncer = pf.sync(args.source, args.dest)
    syncer.direction(args.direction)
    syncer.delete_extras(args.delete_extras)

    if args.ignore:
        syncer.ignore(args.ignore)
    if args.ignore_file:
        syncer.ignore_file(args.ignore_file)

    syncer.conflict_strategy(args.conflict)
    syncer.parallel(args.parallel)
    syncer.dry_run(args.dry_run)
    syncer.progress(True)

    if args.dry_run:
        diff = syncer.compare()
        print(diff.summary())
        for rel in diff.to_add:
            print(f"  + {rel}")
        for rel in diff.to_update:
            print(f"  ~ {rel}")
        for rel in diff.to_delete:
            print(f"  - {rel}")
        return 0 if diff.has_changes() else 4
    else:
        result = syncer.execute()
        if args.json:
            print(json.dumps(result.to_dict(), indent=2, default=str))
        else:
            print(result.summary())
        return 0 if result.success() else 1


def _cmd_rules(args: argparse.Namespace) -> int:
    rules = pf.Rules.from_file(args.file)
    errors = rules.validate()
    if errors:
        for e in errors:
            print(f"Error: {e}", file=sys.stderr)
        return 1

    chain = pf.find(args.path)
    chain = chain.dry_run(False) if args.apply else chain.dry_run(True)

    result_chain = rules.apply(chain)

    if args.apply:
        results = rules.run(chain, dry_run=False)
        executed = sum(1 for r in results if r.get("status") == "executed")
        rule_errors = [r for r in results if r.get("status") == "error"]
        print(f"Rules applied: {executed} file(s) affected.")
        for r in rule_errors:
            print(f"  Error on {r['entry'].name}: {r['error']}", file=sys.stderr)
        return 0 if not rule_errors else 1
    else:
        print(rules.explain())
        print(f"\nDry run: {result_chain.count()} files would be affected")
        print(result_chain.preview())

    return 0
