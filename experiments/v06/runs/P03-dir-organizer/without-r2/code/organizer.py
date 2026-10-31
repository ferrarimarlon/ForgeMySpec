#!/usr/bin/env python3
"""Directory organizer: move files into subdirectories named by extension."""

import argparse
import logging
import shutil
import sys
import time
from pathlib import Path

LOG_NAME = "organizer.log"
NO_EXT_DIR = "no_extension"
# Files still being downloaded/written; leave them alone.
TEMP_SUFFIXES = {".part", ".crdownload", ".tmp", ".download"}

log = logging.getLogger("organizer")


def setup_logging(log_path: Path) -> None:
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    for handler in (logging.FileHandler(log_path, encoding="utf-8"), logging.StreamHandler()):
        handler.setFormatter(fmt)
        log.addHandler(handler)


def dest_dir_name(path: Path) -> str:
    ext = path.suffix.lstrip(".").lower()
    return ext if ext else NO_EXT_DIR


def unique_target(target: Path) -> Path:
    if not target.exists():
        return target
    n = 1
    while True:
        candidate = target.with_name(f"{target.stem} ({n}){target.suffix}")
        if not candidate.exists():
            return candidate
        n += 1


def organize_file(path: Path, root: Path) -> bool:
    """Move a single top-level file. Returns True if moved."""
    if path.name.startswith(".") or path.name == LOG_NAME:
        return False
    if path.is_symlink() or not path.is_file():
        return False
    if path.suffix.lower() in TEMP_SUFFIXES:
        return False
    if path.resolve() == Path(__file__).resolve():
        return False

    dest_dir = root / dest_dir_name(path)
    try:
        dest_dir.mkdir(exist_ok=True)
        target = unique_target(dest_dir / path.name)
        shutil.move(str(path), str(target))
    except OSError as e:
        log.error("Failed to move %s: %s", path.name, e)
        return False
    log.info("Moved %s -> %s", path.name, target.relative_to(root))
    return True


def organize_once(root: Path) -> int:
    """Organize top-level files only; files already in subdirs are skipped."""
    moved = 0
    for entry in sorted(root.iterdir()):
        if organize_file(entry, root):
            moved += 1
    return moved


def watch(root: Path, interval: float) -> None:
    log.info("Watching %s (every %.1fs). Ctrl+C to stop.", root, interval)
    # Track (size, mtime) so we only move files that have stopped changing.
    pending = {}
    while True:
        try:
            for entry in root.iterdir():
                if entry.name.startswith(".") or not entry.is_file():
                    pending.pop(entry, None)
                    continue
                try:
                    st = entry.stat()
                except OSError:
                    pending.pop(entry, None)
                    continue
                sig = (st.st_size, st.st_mtime)
                if pending.get(entry) == sig:
                    organize_file(entry, root)
                    pending.pop(entry, None)
                else:
                    pending[entry] = sig
            pending = {p: s for p, s in pending.items() if p.exists()}
        except OSError as e:
            log.error("Scan error: %s", e)
        time.sleep(interval)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", default=".", help="target directory (default: .)")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="organize once and exit")
    mode.add_argument("--watch", action="store_true", help="keep watching the directory")
    parser.add_argument("--interval", type=float, default=2.0, help="watch poll seconds (default 2)")
    args = parser.parse_args()

    root = Path(args.directory).expanduser().resolve()
    if not root.is_dir():
        print(f"Not a directory: {root}", file=sys.stderr)
        return 1

    setup_logging(root / LOG_NAME)
    try:
        if args.once:
            log.info("Organized %d file(s) in %s", organize_once(root), root)
        else:
            watch(root, max(args.interval, 0.1))
    except KeyboardInterrupt:
        log.info("Stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
