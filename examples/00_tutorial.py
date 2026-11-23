"""PathFile hands-on tutorial — copy this file, run it, then tweak it.

    python -X utf8 examples/00_tutorial.py

Everything happens in a throwaway temp directory. No file of yours is touched.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import path_file as pf

root = Path(tempfile.mkdtemp(prefix="pathflow-tutorial-"))

try:
    # --- 1. build a small messy tree -----------------------------------------
    downloads = root / "Downloads"
    pictures = root / "Pictures" / "Old"
    downloads.mkdir(parents=True)
    pictures.mkdir(parents=True)
    for name, data in {
        "photo.jpg": b"x" * 3000,
        "photo (1).jpg": b"x" * 3000,  # identical copy
        "notes.txt": "meeting notes",
        "installer.exe": b"y" * 5000,
        "old.zip": b"z" * 1000,
        "empty.tmp": b"",
        "empty (1).tmp": b"",
    }.items():
        payload = data if isinstance(data, bytes) else data.encode()
        (downloads / name).write_bytes(payload)

    # --- 2. report ------------------------------------------------------------
    report = pf.find(downloads).report()
    print(report.to_table())

    # --- 3. only keep one of two identical files -----------------------------
    keep = pf.find(downloads).unique_by_hash().to_list()
    print("unique files:", [e.name for e in keep])

    # --- 4. dry-run move of large files (safe preview) ------------------------
    result = pf.find(downloads).files().larger_than("2KB").move_to(pictures).execute()
    print(result.summary())

    # --- 5. glob filter --------------------------------------------------------
    print("jpgs:", [e.name for e in pf.find(downloads).glob("*.jpg")])

    # --- 6. content search ----------------------------------------------------
    hits = pf.search_content(pf.find(downloads).to_list(), "meeting")
    for entry, lines in hits:
        print("found in", entry.name, "line", lines)

    # --- 7. archive only empty files ------------------------------------------
    archive = downloads / "empty-files.zip"
    pf.find(downloads).glob("*.tmp").archive_to(archive).execute()
    print("archive members:", [m.name for m in pf.list_archive(archive)])

    # --- 8. sync with verification --------------------------------------------
    backup = root / "Backup"
    syncer = pf.sync(downloads, backup)
    print("plan:", syncer.compare().summary())

    # --- 9. export ------------------------------------------------------------
    print("csv header:", pf.find(downloads).to_csv().splitlines()[0])
    print("json length:", len(pf.find(downloads).to_json()))

finally:
    shutil.rmtree(root)
    print("\ntutorial finished — temp tree removed")
