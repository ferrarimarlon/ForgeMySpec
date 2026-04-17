import argparse
import logging
import shutil
import time
from pathlib import Path

EXTENSION_MAP = {
    "images":    {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"},
    "documents": {".pdf", ".doc", ".docx", ".txt", ".md", ".csv", ".xlsx"},
    "videos":    {".mp4", ".avi", ".mov", ".mkv"},
    "audio":     {".mp3", ".wav", ".flac", ".aac"},
    "archives":  {".zip", ".tar", ".gz", ".rar", ".7z"},
}

SKIP_NAMES = {"organizer.log"}


def setup_logging(target: Path) -> None:
    log_path = target / "organizer.log"
    fmt = "%(asctime)s - %(levelname)s - %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        datefmt=datefmt,
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def get_subdir(suffix: str) -> str:
    s = suffix.lower()
    for subdir, extensions in EXTENSION_MAP.items():
        if s in extensions:
            return subdir
    return "other"


def organize_once(target: Path) -> int:
    moved = 0
    for item in list(target.iterdir()):
        # skip subdirectories themselves
        if item.is_dir():
            continue
        # skip files not at root level (already organised — extra guard)
        if item.parent != target:
            continue
        # skip hidden files
        if item.name.startswith("."):
            continue
        # skip reserved names
        if item.name in SKIP_NAMES:
            continue

        subdir_name = get_subdir(item.suffix)
        dest_dir = target / subdir_name
        dest_dir.mkdir(exist_ok=True)
        dest_file = dest_dir / item.name

        if dest_file.exists():
            logging.warning("Skipped %s: already exists in %s/", item.name, subdir_name)
            continue

        shutil.move(str(item), str(dest_dir))
        logging.info("Moved %s → %s/", item.name, subdir_name)
        moved += 1

    return moved


def watch_mode(target: Path, interval: int = 2) -> None:
    logging.info("Watch mode started (interval=%ds). Press Ctrl-C to stop.", interval)
    try:
        while True:
            organize_once(target)
            time.sleep(interval)
    except KeyboardInterrupt:
        logging.info("Watch mode stopped.")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="organizer",
        description="Organize files in a directory into typed subdirectories.",
    )
    p.add_argument("target", type=Path, help="Directory to organize")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="Single pass then exit (default)")
    mode.add_argument("--watch", action="store_true", help="Continuous polling every 2 s")
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    target = args.target.resolve()
    if not target.is_dir():
        parser.error(f"Target is not a directory: {target}")

    setup_logging(target)

    if args.watch:
        watch_mode(target)
    else:
        n = organize_once(target)
        logging.info("Done. %d file(s) moved.", n)


if __name__ == "__main__":
    main()
