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
# Files still being downloaded / written by other tools.
TEMP_SUFFIXES = {".part", ".crdownload", ".tmp", ".download"}

log = logging.getLogger("organizer")


def setup_logging(target: Path) -> None:
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    for handler in (logging.FileHandler(target / LOG_NAME, encoding="utf-8"),
                    logging.StreamHandler()):
        handler.setFormatter(fmt)
        log.addHandler(handler)


def dest_dir_name(path: Path) -> str:
    ext = path.suffix.lstrip(".").lower()
    return ext if ext else NO_EXT_DIR


def unique_path(dest: Path) -> Path:
    if not dest.exists():
        return dest
    n = 1
    while True:
        candidate = dest.with_name(f"{dest.stem} ({n}){dest.suffix}")
        if not candidate.exists():
            return candidate
        n += 1


def organize_file(path: Path, target: Path) -> bool:
    """Move one file into its extension subdirectory. Returns True if moved."""
    if path.name.startswith(".") or path.name == LOG_NAME:
        return False
    if path.suffix.lower() in TEMP_SUFFIXES:
        return False
    if not path.is_file() or path.is_symlink():
        return False
    if path.parent != target:  # already in a subdirectory
        return False
    dest_dir = target / dest_dir_name(path)
    try:
        dest_dir.mkdir(exist_ok=True)
        dest = unique_path(dest_dir / path.name)
        shutil.move(str(path), str(dest))
    except OSError as e:
        log.error("failed to move %s: %s", path.name, e)
        return False
    log.info("moved %s -> %s", path.name, dest.relative_to(target))
    return True


def organize_once(target: Path) -> int:
    moved = 0
    for entry in sorted(target.iterdir()):
        if organize_file(entry, target):
            moved += 1
    return moved


def watch(target: Path, interval: float) -> None:
    """Poll the directory; only move files whose size is stable between scans."""
    log.info("watching %s (every %ss, Ctrl+C to stop)", target, interval)
    sizes: dict[Path, int] = {}
    while True:
        current: dict[Path, int] = {}
        for entry in target.iterdir():
            try:
                if entry.is_file():
                    current[entry] = entry.stat().st_size
            except OSError:
                continue
        for entry, size in current.items():
            if sizes.get(entry) == size:
                organize_file(entry, target)
        sizes = current
        time.sleep(interval)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", default=".",
                        help="directory to organize (default: current)")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true",
                      help="organize existing files and exit")
    mode.add_argument("--watch", action="store_true",
                      help="keep running and organize new files")
    parser.add_argument("--interval", type=float, default=2.0,
                        help="poll interval in seconds for --watch (default: 2)")
    args = parser.parse_args()

    target = Path(args.directory).expanduser().resolve()
    if not target.is_dir():
        print(f"error: {target} is not a directory", file=sys.stderr)
        return 1

    setup_logging(target)
    if args.once:
        n = organize_once(target)
        log.info("done: %d file(s) moved", n)
    else:
        try:
            watch(target, args.interval)
        except KeyboardInterrupt:
            log.info("stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
