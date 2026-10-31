#!/usr/bin/env python3
"""Directory Organizer: move top-level files into subdirectories named by extension."""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

NO_EXTENSION = "no_extension"
LOGGER = logging.getLogger("organizer")


def destination_dir_name(filename):
    """Lowercased last suffix without the dot, or no_extension."""
    suffix = Path(filename).suffix
    if len(suffix) > 1:
        return suffix[1:].lower()
    return NO_EXTENSION


def unique_path(dest):
    """Return dest, or dest with _1, _2... before the suffix if it exists."""
    if not os.path.lexists(dest):
        return dest
    n = 1
    while True:
        candidate = dest.with_name(f"{dest.stem}_{n}{dest.suffix}")
        if not os.path.lexists(candidate):
            return candidate
        n += 1


def organize_once(target, log_path=None):
    """One pass over the top level of target. Returns list of (src, dst) moves."""
    target = Path(target)
    log_abs = Path(log_path).resolve() if log_path else None
    moves = []
    for entry in sorted(target.iterdir()):
        if entry.name.startswith("."):
            continue
        if entry.is_symlink() or not entry.is_file():
            continue
        if log_abs is not None and entry.resolve() == log_abs:
            continue
        dest_dir = target / destination_dir_name(entry.name)
        dest_dir.mkdir(exist_ok=True)
        dest = unique_path(dest_dir / entry.name)
        try:
            os.rename(entry, dest)
        except OSError as exc:
            LOGGER.error("failed to move %s: %s", entry, exc)
            continue
        LOGGER.info("moved %s -> %s", entry, dest)
        moves.append((entry, dest))
    return moves


def watch(target, log_path=None, interval=2.0, stop=None):
    """Poll target until stop() returns True (or forever)."""
    while not (stop and stop()):
        organize_once(target, log_path)
        time.sleep(interval)


def setup_logging(log_path):
    LOGGER.setLevel(logging.INFO)
    LOGGER.handlers.clear()
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    LOGGER.addHandler(handler)
    return handler


def build_parser():
    p = argparse.ArgumentParser(description="Organize files in a directory by extension.")
    p.add_argument("target", help="directory to organize")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="organize once and exit")
    mode.add_argument("--watch", action="store_true", help="keep organizing until interrupted")
    p.add_argument("--interval", type=float, default=2.0, help="watch poll seconds (default 2)")
    p.add_argument("--log", default="organizer.log", help="log file (default organizer.log)")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    if not os.path.isdir(args.target):
        print(f"error: not a directory: {args.target}", file=sys.stderr)
        return 2
    handler = setup_logging(args.log)
    try:
        if args.once:
            organize_once(args.target, args.log)
        else:
            try:
                watch(args.target, args.log, args.interval)
            except KeyboardInterrupt:
                pass
    finally:
        handler.close()
        LOGGER.removeHandler(handler)
    return 0


if __name__ == "__main__":
    sys.exit(main())
