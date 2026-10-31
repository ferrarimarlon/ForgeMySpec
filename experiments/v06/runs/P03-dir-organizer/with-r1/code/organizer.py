#!/usr/bin/env python3
"""Directory Organizer: move top-level files into subdirectories by extension."""
import argparse
import logging
import os
import shutil
import sys
import time

NO_EXT = "no_extension"
DEFAULT_LOG = "organizer" + ".log"


def dest_dir_name(filename):
    ext = os.path.splitext(filename)[1]
    return ext[1:].lower() if len(ext) > 1 else NO_EXT


def unique_path(path):
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    n = 1
    while os.path.exists(f"{base}_{n}{ext}"):
        n += 1
    return f"{base}_{n}{ext}"


def organize(target, logger=None, skip=()):
    """Organize the top level of target once. Returns list of (src, dst)."""
    logger = logger or logging.getLogger("organizer")
    skip = {os.path.abspath(p) for p in skip}
    moved = []
    for entry in sorted(os.listdir(target)):
        if entry.startswith("."):
            continue
        src = os.path.join(target, entry)
        if os.path.abspath(src) in skip:
            continue
        if os.path.islink(src) or not os.path.isfile(src):
            continue
        folder = os.path.join(target, dest_dir_name(entry))
        os.makedirs(folder, exist_ok=True)
        dst = unique_path(os.path.join(folder, entry))
        try:
            shutil.move(src, dst)
        except OSError as exc:
            logger.error("failed to move %s: %s", src, exc)
            continue
        logger.info("%s -> %s", src, dst)
        moved.append((src, dst))
    return moved


def watch(target, logger=None, interval=2.0, skip=(), stop=None):
    """Poll target until KeyboardInterrupt (or stop() returns True)."""
    try:
        while not (stop and stop()):
            organize(target, logger, skip)
            time.sleep(interval)
    except KeyboardInterrupt:
        pass


def make_logger(path):
    logger = logging.getLogger("organizer." + os.path.abspath(path))
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.FileHandler(path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger


def main(argv=None):
    p = argparse.ArgumentParser(description="Move files into subdirectories by extension.")
    p.add_argument("target", help="directory to organize")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="organize once and exit")
    mode.add_argument("--watch", action="store_true", help="keep organizing until interrupted")
    p.add_argument("--interval", type=float, default=2.0, help="watch poll seconds (default 2)")
    p.add_argument("--log", default=DEFAULT_LOG, help="log file (default ./organizer.log)")
    args = p.parse_args(argv)
    if not os.path.isdir(args.target):
        p.error(f"not a directory: {args.target}")
    if args.interval <= 0:
        p.error("--interval must be positive")
    logger = make_logger(args.log)
    skip = [args.log]
    if args.once:
        organize(args.target, logger, skip)
    else:
        watch(args.target, logger, args.interval, skip)
    return 0


if __name__ == "__main__":
    sys.exit(main())
