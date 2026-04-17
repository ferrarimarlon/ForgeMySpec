import os
import shutil
import time
import argparse
import logging

CATEGORIES = {
    "images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"],
    "documents": [".pdf", ".doc", ".docx", ".txt", ".md", ".csv", ".xlsx"],
    "videos": [".mp4", ".avi", ".mov", ".mkv"],
    "audio": [".mp3", ".wav", ".flac", ".aac"],
    "archives": [".zip", ".tar", ".gz", ".rar", ".7z"],
}

def get_category(filename):
    ext = os.path.splitext(filename)[1].lower()
    for cat, exts in CATEGORIES.items():
        if ext in exts:
            return cat
    return "other"

def organize(target):
    moved = 0
    for name in os.listdir(target):
        path = os.path.join(target, name)
        if os.path.isdir(path):
            continue
        if name.startswith("."):
            continue
        if name == "organizer.log":
            continue
        cat = get_category(name)
        dest_dir = os.path.join(target, cat)
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, name)
        if os.path.exists(dest):
            logging.warning("Skipped %s: exists in %s/", name, cat)
            continue
        shutil.move(path, dest_dir)
        logging.info("Moved %s → %s/", name, cat)
        moved += 1
    return moved

def main():
    p = argparse.ArgumentParser()
    p.add_argument("target")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--once", action="store_true")
    g.add_argument("--watch", action="store_true")
    args = p.parse_args()

    log_path = os.path.join(args.target, "organizer.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.FileHandler(log_path), logging.StreamHandler()]
    )

    if args.watch:
        logging.info("Watching %s ...", args.target)
        try:
            while True:
                organize(args.target)
                time.sleep(2)
        except KeyboardInterrupt:
            logging.info("Stopped.")
    else:
        n = organize(args.target)
        logging.info("Done. %d moved.", n)

if __name__ == "__main__":
    main()
