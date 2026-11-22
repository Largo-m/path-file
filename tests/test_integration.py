"""Integration tests for path_file."""

from __future__ import annotations

from pathlib import Path

import pytest

import path_file as pf


class TestRealWorldScenarios:
    """Test real-world usage scenarios."""

    def test_clean_downloads_folder(self, tmp_dir: Path):
        """Simulate cleaning a downloads folder."""
        downloads = tmp_dir / "Downloads"
        downloads.mkdir()

        # Create various files
        (downloads / "document.pdf").write_text("PDF content")
        (downloads / "image.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"x" * 1000)
        (downloads / "old.tmp").write_text("temp")
        (downloads / "installer.exe").write_bytes(b"MZ" + b"x" * 5000)
        (downloads / "notes.txt").write_text("notes")

        # Delete .tmp files older than 7 days (all are fresh, so dry-run)
        chain = pf.find(downloads).files().with_extension(".tmp").older_than("7 days")
        result = chain.delete(dry_run=True).execute()

        assert result.dry_run
        assert result.count >= 0

    def test_organize_photos_by_date(self, tmp_dir: Path):
        """Simulate organizing photos into dated folders."""
        photos = tmp_dir / "Photos"
        photos.mkdir()

        # Create photos with different dates (simulated via name)
        for i in range(5):
            (photos / f"IMG_{20240101 + i}_{i}.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"x" * 100)

        # Find all JPGs
        chain = pf.find(photos).files().with_extension(".jpg")
        entries = chain.to_list()

        assert len(entries) == 5
        for e in entries:
            assert e.suffix == ".jpg"

    def test_backup_documents_with_hash(self, tmp_dir: Path):
        """Simulate backing up documents with hash verification."""
        source = tmp_dir / "Documents"
        backup = tmp_dir / "Backup"
        source.mkdir()
        backup.mkdir()

        (source / "report.docx").write_text("Report content")
        (source / "budget.xlsx").write_text("Budget data")
        (source / "notes.txt").write_text("Notes")

        # Copy with hash verification
        chain = pf.find(source).files()
        result = chain.copy_to(backup, preserve_metadata=True).execute()

        assert result.success()
        assert result.count == 3

        # Verify hashes match
        for entry in chain:
            backup_file = backup / entry.name
            assert backup_file.exists()
            assert entry.hash_sha256 == pf.hash_file(backup_file)

    def test_find_duplicates_and_report(self, tmp_dir: Path):
        """Find duplicates and generate report."""
        data = tmp_dir / "Data"
        data.mkdir()

        # Create duplicates
        for i in range(3):
            (data / f"duplicate_{i}.txt").write_text("SAME CONTENT")
        (data / "unique.txt").write_text("UNIQUE CONTENT")

        # Find duplicates
        chain = pf.find(data).files()
        dupes = chain.duplicates_by_hash()

        assert len(dupes) == 1
        _, group = next(iter(dupes.items()))
        assert len(group) == 3

        # Generate report
        report = chain.report()
        assert report.chain_size == 4
        assert report.file_count == 4

    def test_compress_old_logs(self, tmp_dir: Path):
        """Compress log files older than 30 days."""
        logs = tmp_dir / "Logs"
        logs.mkdir()

        (logs / "app.log").write_text("Log line 1\nLog line 2")
        (logs / "error.log").write_text("Error 1\nError 2")
        (logs / "current.log").write_text("Current log")

        # Compress old logs (dry run since all are fresh)
        chain = pf.find(logs).files().with_extension(".log").older_than("30 days")
        result = chain.compress("gz", dry_run=True).execute()

        assert result.dry_run

    def test_sync_with_ignore(self, tmp_dir: Path):
        """Sync with ignore patterns."""
        src = tmp_dir / "Project"
        dest = tmp_dir / "Backup"
        src.mkdir()
        dest.mkdir()

        (src / "main.py").write_text("print('hello')")
        (src / "config.json").write_text('{"key": "value"}')
        (src / "build").mkdir()
        (src / "build" / "output.bin").write_bytes(b"binary")
        (src / ".git").mkdir()
        (src / ".git" / "config").write_text("git config")

        # Sync ignoring build and .git
        syncer = pf.sync(src, dest).direction("source_to_dest")
        syncer.ignore(["build/", ".git/", "*.pyc"])
        diff = syncer.compare()

        # Should only sync main.py and config.json
        assert len(diff.to_add) == 2
        added_names = [str(p) for p in diff.to_add]
        assert "main.py" in added_names
        assert "config.json" in added_names

    def test_rules_based_cleanup(self, tmp_dir: Path):
        """Declarative rules-based cleanup."""
        workspace = tmp_dir / "Workspace"
        workspace.mkdir()

        (workspace / "temp.tmp").write_text("temp")
        (workspace / "cache.cache").write_text("cache")
        (workspace / "important.txt").write_text("important")
        (workspace / "old.log").write_text("old log")

        rules_content = """
[[rule]]
match = "*.tmp"
action = "delete"

[[rule]]
match = "*.cache"
action = "delete"

[[rule]]
match = "*.log"
when_older_than = "7 days"
action = "delete"
"""
        rules_file = tmp_dir / "cleanup.toml"
        rules_file.write_text(rules_content.strip())

        rules = pf.Rules.from_file(rules_file)
        errors = rules.validate()
        assert len(errors) == 0

        chain = pf.find(workspace).files()
        result_chain = rules.apply(chain)

        # Should match .tmp and .cache files
        entries = result_chain.to_list()
        matched_names = [e.name for e in entries]
        assert "temp.tmp" in matched_names
        assert "cache.cache" in matched_names

    def test_watch_and_process(self, tmp_dir: Path):
        """Watch folder and process new files."""
        incoming = tmp_dir / "Incoming"
        processed = tmp_dir / "Processed"
        incoming.mkdir()
        processed.mkdir()

        watcher = pf.watch(incoming, poll_interval=0.1)
        watcher.filter("*.txt")

        events_received = []

        def on_new(event):
            events_received.append(event)
            # Move to processed
            dest = processed / event.path.name
            event.path.rename(dest)

        watcher.on_new(on_new)

        # Start watcher in background
        watcher.start()

        # Create new file
        new_file = incoming / "new.txt"
        new_file.write_text("new content")

        # Give watcher time to detect
        import time

        time.sleep(0.3)

        watcher.stop()

        assert len(events_received) == 1
        assert events_received[0].type == "created"
        assert (processed / "new.txt").exists()

    def test_large_directory_performance(self, tmp_dir: Path):
        """Test performance with many files."""
        large_dir = tmp_dir / "Large"
        large_dir.mkdir()

        # Create 100 files
        for i in range(100):
            (large_dir / f"file_{i:03d}.txt").write_text(f"Content {i}" * 10)

        # Should handle efficiently
        chain = pf.find(large_dir).files()
        count = chain.count()

        assert count == 100

        # Parallel hash
        result = chain.parallel(4).hash().execute()
        assert result.success()
        assert result.count == 100


class TestEdgeCases:
    """Test edge cases."""

    def test_empty_directory(self, tmp_dir: Path):
        empty = tmp_dir / "Empty"
        empty.mkdir()

        chain = pf.find(empty)
        assert chain.count() == 0
        assert chain.to_list() == []

    def test_single_file(self, tmp_dir: Path):
        f = tmp_dir / "single.txt"
        f.write_text("content")

        chain = pf.find(f)
        assert chain.count() == 1
        assert chain.first().path == f.resolve()

    def test_unicode_filenames(self, tmp_dir: Path):
        f = tmp_dir / "文件.txt"
        f.write_text("中文内容", encoding="utf-8")

        chain = pf.find(tmp_dir).files()
        entries = chain.to_list()

        assert len(entries) == 1
        assert entries[0].name == "文件.txt"
        assert entries[0].read_text(encoding="utf-8") == "中文内容"

    def test_deep_nesting(self, tmp_dir: Path):
        deep = tmp_dir
        for i in range(20):
            deep = deep / f"level{i}"
            deep.mkdir()
        (deep / "deep.txt").write_text("deep")

        chain = pf.find(tmp_dir).files()
        entries = chain.to_list()

        assert len(entries) == 1
        assert entries[0].name == "deep.txt"

    def test_permission_errors_handled(self, tmp_dir: Path):
        # Create a file and remove read permission (Unix only)
        f = tmp_dir / "noperm.txt"
        f.write_text("secret")

        try:
            f.chmod(0o000)
            chain = pf.find(tmp_dir).files()
            # Should not crash, may skip the file
            entries = chain.to_list()
        finally:
            f.chmod(0o644)  # Restore for cleanup

        # Should handle gracefully
        assert isinstance(entries, list)

    def test_symlink_handling(self, tmp_dir: Path):
        target = tmp_dir / "target.txt"
        target.write_text("target")
        link = tmp_dir / "link.txt"

        try:
            link.symlink_to(target)

            # Default: don't follow symlinks
            chain = pf.find(tmp_dir).files()
            entries = chain.to_list()

            # Should include symlink as a file entry
            link_entries = [e for e in entries if e.is_symlink]
            assert len(link_entries) >= 1
        except (OSError, NotImplementedError):
            pytest.skip("Symlinks not supported")


class TestChainingComplexity:
    """Test complex chaining scenarios."""

    def test_multi_filter_chain(self, tmp_dir: Path):
        for ext in [".txt", ".jpg", ".png", ".pdf"]:
            for i in range(3):
                (tmp_dir / f"file{i}{ext}").write_text(f"content {i}")

        chain = (
            pf.find(tmp_dir)
            .files()
            .with_extensions(".txt", ".pdf")
            .larger_than("10")
            .name_contains("file")
            .sort_by("name")
            .limit(3)
        )

        entries = chain.to_list()
        assert len(entries) <= 3
        for e in entries:
            assert e.suffix in (".txt", ".pdf")
            assert e.size > 10
            assert "file" in e.name

    def test_action_chain(self, tmp_dir: Path):
        src = tmp_dir / "src"
        dest = tmp_dir / "dest"
        src.mkdir()
        dest.mkdir()

        for i in range(5):
            (src / f"data{i}.txt").write_text(f"data {i}")

        # Chain: find -> filter -> copy -> report
        chain = pf.find(src).files().with_extension(".txt")
        copy_result = chain.copy_to(dest, overwrite=True).execute()
        report = chain.report()

        assert copy_result.success()
        assert copy_result.count == 5
        assert report.chain_size == 5

    def test_parallel_pipeline(self, tmp_dir: Path):
        src = tmp_dir / "parallel"
        src.mkdir()

        for i in range(20):
            (src / f"file{i}.txt").write_text(f"content {i}" * 100)

        chain = pf.find(src).files().parallel(8)

        # Multiple operations
        hash_result = chain.hash().execute()
        assert hash_result.success()

        compressed = chain.compress("gz").execute()
        assert compressed.success()
