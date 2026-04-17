import argparse
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Storage ───────────────────────────────────────────────────────────────────

def get_notes_dir() -> Path:
    override = os.environ.get("NOTES_DIR")
    d = Path(override) if override else Path.home() / ".note-taker"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── Slug & id ─────────────────────────────────────────────────────────────────

def slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "", title.lower().replace(" ", "-"))[:40].strip("-")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def next_id(notes_dir: Path) -> int:
    ids = []
    for f in notes_dir.glob("*.md"):
        meta, _ = parse_note(f)
        try:
            ids.append(int(meta.get("id", 0)))
        except ValueError:
            pass
    return max(ids, default=0) + 1


# ── Frontmatter I/O ───────────────────────────────────────────────────────────

def parse_note(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        return {}, text
    fm_block = parts[1]
    body = parts[2]
    meta: dict = {}
    for line in fm_block.splitlines():
        if ": " in line:
            key, val = line.split(": ", 1)
            meta[key.strip()] = val.strip()
        elif line.strip() and ":" in line:
            key, val = line.split(":", 1)
            meta[key.strip()] = val.strip()
    return meta, body


def write_note(meta: dict, body: str, path: Path) -> None:
    fm_lines = [f"{k}: {v}" for k, v in meta.items()]
    content = "---\n" + "\n".join(fm_lines) + "\n---\n" + body
    path.write_text(content, encoding="utf-8")


def find_note_path(notes_dir: Path, note_id: int) -> Optional[Path]:
    prefix = f"{note_id}-"
    for f in notes_dir.glob("*.md"):
        if f.name.startswith(prefix):
            return f
    return None


# ── List helpers ──────────────────────────────────────────────────────────────

def load_all(notes_dir: Path) -> list[tuple[dict, str, Path]]:
    notes = []
    for f in sorted(notes_dir.glob("*.md"), key=lambda x: x.name):
        meta, body = parse_note(f)
        notes.append((meta, body, f))
    return notes


def _cell(v, w: int) -> str:
    s = str(v) if v is not None else ""
    return s[:w].ljust(w)


def print_list(notes: list[tuple[dict, str, Path]]) -> None:
    if not notes:
        print("No notes found.")
        return
    header = _cell("ID", 4) + "  " + _cell("Title", 30) + "  " + _cell("Tags", 20) + "  " + _cell("Created", 20)
    print("-" * len(header))
    print(header)
    print("-" * len(header))
    for meta, _, _ in notes:
        created = meta.get("created_at", "")[:19].replace("T", " ")
        print(
            _cell(meta.get("id", ""), 4) + "  " +
            _cell(meta.get("title", ""), 30) + "  " +
            _cell(meta.get("tags", ""), 20) + "  " +
            _cell(created, 20)
        )
    print("-" * len(header))


# ── Subcommand handlers ───────────────────────────────────────────────────────

def cmd_new(args, notes_dir: Path) -> None:
    nid = next_id(notes_dir)
    slug = slugify(args.title)
    filename = f"{nid}-{slug}.md"
    path = notes_dir / filename
    now = now_iso()
    meta = {
        "id": str(nid),
        "title": args.title,
        "tags": args.tags or "",
        "created_at": now,
        "updated_at": now,
    }
    body = (args.body or "") + "\n"
    write_note(meta, body, path)
    print(f"Created note {nid}: '{args.title}' → {filename}")


def cmd_list(args, notes_dir: Path) -> None:
    all_notes = load_all(notes_dir)
    filtered = []
    for meta, body, path in all_notes:
        if args.tag:
            tags = [t.strip() for t in meta.get("tags", "").split(",") if t.strip()]
            if args.tag not in tags:
                continue
        if args.search:
            haystack = (meta.get("title", "") + " " + body).lower()
            if args.search.lower() not in haystack:
                continue
        filtered.append((meta, body, path))
    print_list(filtered)


def cmd_show(args, notes_dir: Path) -> None:
    path = find_note_path(notes_dir, args.id)
    if path is None:
        print(f"Note {args.id} not found", file=sys.stderr)
        sys.exit(1)
    print(path.read_text(encoding="utf-8"))


def cmd_edit(args, notes_dir: Path) -> None:
    path = find_note_path(notes_dir, args.id)
    if path is None:
        print(f"Note {args.id} not found", file=sys.stderr)
        sys.exit(1)
    meta, body = parse_note(path)
    changed = False
    if args.title is not None:
        meta["title"] = args.title
        changed = True
    if args.tags is not None:
        meta["tags"] = args.tags
        changed = True
    if args.body is not None:
        body = args.body + "\n"
        changed = True
    if not changed:
        print("Nothing to update.")
        return
    meta["updated_at"] = now_iso()
    new_slug = slugify(meta["title"])
    new_filename = f"{meta['id']}-{new_slug}.md"
    new_path = notes_dir / new_filename
    write_note(meta, body, new_path)
    if new_path != path:
        path.unlink()
    print(f"Updated note {meta['id']}: '{meta['title']}'")


def cmd_delete(args, notes_dir: Path) -> None:
    path = find_note_path(notes_dir, args.id)
    if path is None:
        print(f"Note {args.id} not found", file=sys.stderr)
        sys.exit(1)
    meta, _ = parse_note(path)
    title = meta.get("title", "")
    path.unlink()
    print(f"Deleted note {args.id}: '{title}'")


# ── Argparse ──────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="note_taker", description="Markdown note-taking CLI")
    sub = p.add_subparsers(dest="command", required=True)

    pn = sub.add_parser("new", help="Create a new note")
    pn.add_argument("--title", required=True)
    pn.add_argument("--tags", default="", help="Comma-separated tags")
    pn.add_argument("--body", default="", help="Note body text")

    pl = sub.add_parser("list", help="List notes")
    pl.add_argument("--tag", default=None)
    pl.add_argument("--search", default=None)

    ps = sub.add_parser("show", help="Show a note")
    ps.add_argument("id", type=int)

    pe = sub.add_parser("edit", help="Edit a note")
    pe.add_argument("id", type=int)
    pe.add_argument("--title", default=None)
    pe.add_argument("--tags", default=None)
    pe.add_argument("--body", default=None)

    pd = sub.add_parser("delete", help="Delete a note")
    pd.add_argument("id", type=int)

    return p


def main() -> None:
    notes_dir = get_notes_dir()
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "new": cmd_new,
        "list": cmd_list,
        "show": cmd_show,
        "edit": cmd_edit,
        "delete": cmd_delete,
    }
    dispatch[args.command](args, notes_dir)


if __name__ == "__main__":
    main()
