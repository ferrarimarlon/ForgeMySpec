#!/usr/bin/env python3
"""Directory Organizer: move top-level files into subdirectories named after their extension.

Usage:
    python3 organizer.py [TARGET] --once
    python3 organizer.py [TARGET] --watch [--interval SECONDS]

Hidden files and anything already inside a subdirectory are left alone.
Every move is appended to organizer.log inside the target directory.
"""
import argparse
import os
import shutil
import sys
import threading
from datetime import datetime

LOG_NAME = "organizer.log"
NO_EXTENSION_DIR = "no_extension"
SELF_NAME = os.path.basename(__file__)


def dest_dirname(filename):
    """Subdirectory name for a file: lowercase last extension without the dot."""
    ext = os.path.splitext(filename)[1].lstrip(".").lower()
    return ext or NO_EXTENSION_DIR


def should_skip(name, path):
    """True for hidden files, our own log/script, symlinks and non-regular files."""
    if name.startswith("."):
        return True
    if name in (LOG_NAME, SELF_NAME):
        return True
    if os.path.islink(path) or not os.path.isfile(path):
        return True
    return False


def unique_destination(directory, filename):
    """Return a path in directory for filename, adding _1, _2... if taken."""
    candidate = os.path.join(directory, filename)
    if not os.path.lexists(candidate):
        return candidate
    stem, ext = os.path.splitext(filename)
    n = 1
    while True:
        candidate = os.path.join(directory, "%s_%d%s" % (stem, n, ext))
        if not os.path.lexists(candidate):
            return candidate
        n += 1


def log_move(target, src, dst):
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(os.path.join(target, LOG_NAME), "a", encoding="utf-8") as fh:
        fh.write("%s MOVED %s -> %s\n" % (stamp, src, dst))


def organize_once(target):
    """Organize the top-level files of target. Returns the number of files moved."""
    moved = 0
    for name in sorted(os.listdir(target)):
        src = os.path.join(target, name)
        if should_skip(name, src):
            continue
        try:
            subdir = os.path.join(target, dest_dirname(name))
            os.makedirs(subdir, exist_ok=True)
            dst = unique_destination(subdir, name)
            shutil.move(src, dst)
        except OSError as exc:
            print("organizer: cannot move %s: %s" % (src, exc), file=sys.stderr)
            continue
        log_move(target, os.path.relpath(src, target), os.path.relpath(dst, target))
        moved += 1
    return moved


def watch(target, interval=2.0, stop_event=None):
    """Poll target every interval seconds until stop_event is set (or Ctrl-C)."""
    stop_event = stop_event or threading.Event()
    try:
        while not stop_event.is_set():
            organize_once(target)
            stop_event.wait(interval)
    except KeyboardInterrupt:
        pass


def main(argv=None):
    parser = argparse.ArgumentParser(description="Move files into subdirectories by extension.")
    parser.add_argument("target", nargs="?", default=".", help="directory to organize (default: .)")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="organize once and exit")
    mode.add_argument("--watch", action="store_true", help="keep organizing until interrupted")
    parser.add_argument("--interval", type=float, default=2.0, help="watch poll interval in seconds")
    args = parser.parse_args(argv)

    if not os.path.isdir(args.target):
        print("organizer: not a directory: %s" % args.target, file=sys.stderr)
        return 2
    if args.once:
        organize_once(args.target)
    else:
        watch(args.target, args.interval)
    return 0


if __name__ == "__main__":
    sys.exit(main())
