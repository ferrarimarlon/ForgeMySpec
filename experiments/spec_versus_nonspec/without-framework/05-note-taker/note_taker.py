import argparse
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

NOTES_DIR = Path(os.environ.get("NOTES_DIR", Path.home() / ".note-taker"))

def setup():
    NOTES_DIR.mkdir(parents=True, exist_ok=True)

def now():
    return datetime.now(timezone.utc).isoformat()

def slugify(t):
    return re.sub(r"[^a-z0-9-]+", "", t.lower().replace(" ", "-"))[:40]

def next_id():
    ids = [int(f.stem.split("-")[0]) for f in NOTES_DIR.glob("*.md") if f.stem.split("-")[0].isdigit()]
    return max(ids, default=0) + 1

def parse(path):
    txt = path.read_text()
    parts = txt.split("---\n", 2)
    if len(parts) < 3:
        return {}, txt
    meta = {}
    for line in parts[1].splitlines():
        if ": " in line:
            k, v = line.split(": ", 1)
            meta[k] = v
    return meta, parts[2]

def write(path, meta, body):
    fm = "\n".join(f"{k}: {v}" for k, v in meta.items())
    path.write_text(f"---\n{fm}\n---\n{body}")

def find(nid):
    for f in NOTES_DIR.glob(f"{nid}-*.md"):
        return f
    return None

def all_notes():
    return sorted(NOTES_DIR.glob("*.md"))

def main():
    setup()
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd")

    pn = sub.add_parser("new")
    pn.add_argument("--title", required=True)
    pn.add_argument("--tags", default="")
    pn.add_argument("--body", default="")

    pl = sub.add_parser("list")
    pl.add_argument("--tag", default=None)
    pl.add_argument("--search", default=None)

    ps = sub.add_parser("show")
    ps.add_argument("id", type=int)

    pe = sub.add_parser("edit")
    pe.add_argument("id", type=int)
    pe.add_argument("--title", default=None)
    pe.add_argument("--tags", default=None)
    pe.add_argument("--body", default=None)

    pd = sub.add_parser("delete")
    pd.add_argument("id", type=int)

    args = p.parse_args()

    if args.cmd == "new":
        nid = next_id()
        slug = slugify(args.title)
        path = NOTES_DIR / f"{nid}-{slug}.md"
        t = now()
        write(path, {"id": nid, "title": args.title, "tags": args.tags, "created_at": t, "updated_at": t}, args.body + "\n")
        print(f"Created {nid}: {args.title}")

    elif args.cmd == "list":
        rows = []
        for f in all_notes():
            meta, body = parse(f)
            if args.tag and args.tag not in [t.strip() for t in meta.get("tags", "").split(",")]:
                continue
            if args.search and args.search.lower() not in (meta.get("title", "") + body).lower():
                continue
            rows.append(meta)
        if not rows:
            print("No notes found.")
        else:
            print(f"{'ID':<4}  {'Title':<30}  {'Tags':<20}  {'Created':<20}")
            print("-" * 82)
            for m in rows:
                print(f"{str(m.get('id','')):<4}  {str(m.get('title',''))[:30]:<30}  {str(m.get('tags',''))[:20]:<20}  {str(m.get('created_at',''))[:19]:<20}")

    elif args.cmd == "show":
        f = find(args.id)
        if not f:
            print(f"Note {args.id} not found"); sys.exit(1)
        print(f.read_text())

    elif args.cmd == "edit":
        f = find(args.id)
        if not f:
            print(f"Note {args.id} not found"); sys.exit(1)
        meta, body = parse(f)
        changed = False
        if args.title:
            meta["title"] = args.title; changed = True
        if args.tags is not None:
            meta["tags"] = args.tags; changed = True
        if args.body:
            body = args.body + "\n"; changed = True
        if not changed:
            print("Nothing to update."); return
        meta["updated_at"] = now()
        new_path = NOTES_DIR / f"{meta['id']}-{slugify(meta['title'])}.md"
        write(new_path, meta, body)
        if new_path != f:
            f.unlink()
        print(f"Updated {meta['id']}: {meta['title']}")

    elif args.cmd == "delete":
        f = find(args.id)
        if not f:
            print(f"Note {args.id} not found"); sys.exit(1)
        meta, _ = parse(f)
        f.unlink()
        print(f"Deleted {args.id}: {meta.get('title','')}")

    else:
        p.print_help()

if __name__ == "__main__":
    main()
