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
# Partial-download / temp suffixes: leave alone until they're finished.
TEMP_SUFFIXES = {".part", ".crdownload", ".tmp", ".download"}

log = logging.getLogger("organizer")


def setup_logging(target: Path) -> None:
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handlers = [logging.FileHandler(target / LOG_NAME, encoding="utf-8"),
                logging.StreamHandler()]
    for h in handlers:
        h.setFormatter(fmt)
        log.addHandler(h)
    log.setLevel(logging.INFO)


def dest_dir_name(path: Path) -> str:
    ext = path.suffix.lstrip(".").lower()
    return ext if ext else NO_EXT_DIR


def unique_path(dest: Path) -> Path:
    if not dest.exists():
        return dest
    n = 1
    while True:
        candidate = dest.with_name(f"{dest.stem}_{n}{dest.suffix}")
        if not candidate.exists():
            return candidate
        n += 1


def organize_file(path: Path, target: Path) -> bool:
    """Move one top-level file. Returns True if moved."""
    if path.name.startswith(".") or path.name == LOG_NAME:
        return False
    if not path.is_file() or path.is_symlink():
        return False
    if path.suffix.lower() in TEMP_SUFFIXES:
        return False
    dest_dir = target / dest_dir_name(path)
    try:
        dest_dir.mkdir(exist_ok=True)
        dest = unique_path(dest_dir / path.name)
        shutil.move(str(path), str(dest))
    except (OSError, shutil.Error) as e:
        log.error("failed to move %s: %s", path.name, e)
        return False
    log.info("moved %s -> %s", path.name, dest.relative_to(target))
    return True


def organize_once(target: Path) -> int:
    # Only direct children: files already in subdirectories are skipped.
    count = 0
    for entry in sorted(target.iterdir()):
        if organize_file(entry, target):
            count += 1
    return count


def watch(target: Path, interval: float) -> None:
    """Poll the directory; a file is moved once its size is stable between scans."""
    log.info("watching %s every %.1fs (Ctrl+C to stop)", target, interval)
    sizes: dict[Path, int] = {}
    while True:
        current: dict[Path, int] = {}
        try:
            entries = list(target.iterdir())
        except OSError as e:
            log.error("cannot read %s: %s", target, e)
            entries = []
        for entry in entries:
            if entry.name.startswith(".") or not entry.is_file():
                continue
            try:
                size = entry.stat().st_size
            except OSError:
                continue
            if sizes.get(entry) == size:
                organize_file(entry, target)
            else:
                current[entry] = size
        sizes = current
        time.sleep(interval)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("directory", nargs="?", default=".", help="directory to organize (default: .)")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="organize once and exit")
    mode.add_argument("--watch", action="store_true", help="keep watching for new files")
    p.add_argument("--interval", type=float, default=2.0, help="watch poll seconds (default: 2)")
    args = p.parse_args()

    target = Path(args.directory).expanduser().resolve()
    if not target.is_dir():
        print(f"error: {target} is not a directory", file=sys.stderr)
        return 1

    setup_logging(target)
    if args.once:
        n = organize_once(target)
        log.info("done: %d file(s) moved", n)
        return 0
    try:
        watch(target, max(args.interval, 0.1))
    except KeyboardInterrupt:
        log.info("stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
