#!/usr/bin/env python3
"""note_taker: a Markdown note-taking CLI. Notes are .md files with YAML
frontmatter stored in ~/.note-taker/ (override with NOTE_TAKER_DIR)."""
import argparse
import datetime
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path


def notes_dir():
    env = os.environ.get("NOTE_TAKER_DIR")
    return Path(env) if env else Path.home() / ".note-taker"


class NoteError(Exception):
    pass


def slugify(title):
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return s or "note"


def split_tags(raw):
    seen = []
    for t in (raw or "").split(","):
        t = t.strip().lower()
        if t and t not in seen:
            seen.append(t)
    return seen


def quote(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def unquote(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] == '"':
        return re.sub(r"\\(.)", r"\1", s[1:-1])
    return s


def render_note(nid, title, tags, created, body):
    head = [
        "---",
        f"id: {nid}",
        f"title: {title}" if _plain(title) else f"title: {quote(title)}",
        "tags: [" + ", ".join(tags) + "]",
        f"created: {created}",
        "---",
        "",
    ]
    return "\n".join(head) + body.rstrip("\n") + "\n"


def _plain(s):
    return bool(s) and s == s.strip() and not s.startswith(('"', "'", "[")) and "\n" not in s \
        and "\\" not in s and not re.search(r"\s#", s)


def parse_note(text):
    """Return (meta, body). Raises NoteError on bad frontmatter."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        raise NoteError("missing frontmatter")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise NoteError("unterminated frontmatter")
    meta = {}
    for ln in lines[1:end]:
        if not ln.strip():
            continue
        m = re.match(r"^([a-z_]+):\s*(.*)$", ln)
        if not m:
            raise NoteError(f"bad frontmatter line: {ln!r}")
        meta[m.group(1)] = m.group(2)
    for k in ("id", "title", "tags", "created"):
        if k not in meta:
            raise NoteError(f"frontmatter missing {k}")
    tags = meta["tags"].strip()
    if not (tags.startswith("[") and tags.endswith("]")):
        raise NoteError("tags must be a [list]")
    meta["tags"] = split_tags(tags[1:-1])
    meta["title"] = unquote(meta["title"])
    meta["id"] = meta["id"].strip()
    return meta, "\n".join(lines[end + 1:]).lstrip("\n")


def note_path(nid):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", nid):
        raise NoteError(f"note not found: {nid}")
    p = notes_dir() / f"{nid}.md"
    if not p.is_file():
        raise NoteError(f"note not found: {nid}")
    return p


def load_all():
    d = notes_dir()
    out = []
    if d.is_dir():
        for p in sorted(d.glob("*.md")):
            try:
                meta, body = parse_note(p.read_text(encoding="utf-8"))
            except (NoteError, OSError, UnicodeDecodeError):
                continue
            out.append((p.stem, meta, body))
    return out


def cmd_new(a):
    d = notes_dir()
    d.mkdir(parents=True, exist_ok=True)
    body = a.body if a.body is not None else (sys.stdin.read() if not sys.stdin.isatty() else "")
    base = slugify(a.title)
    nid, n = base, 1
    while True:
        try:
            with open(d / f"{nid}.md", "x", encoding="utf-8") as f:
                created = datetime.datetime.now().replace(microsecond=0).isoformat()
                f.write(render_note(nid, a.title, split_tags(a.tags), created, body))
            break
        except FileExistsError:
            n += 1
            nid = f"{base}-{n}"
    print(nid)


def cmd_list(a):
    tag = a.tag.strip().lower() if a.tag else None
    kw = a.search.lower() if a.search else None
    for nid, meta, body in load_all():
        if tag and tag not in meta["tags"]:
            continue
        if kw and kw not in meta["title"].lower() and kw not in body.lower():
            continue
        tags = ",".join(meta["tags"])
        print(f"{nid}\t{meta['title']}\t{tags}")


def cmd_show(a):
    meta, body = parse_note(note_path(a.id).read_text(encoding="utf-8"))
    print(f"# {meta['title']}")
    print(f"tags: {', '.join(meta['tags'])}")
    print(f"created: {meta['created']}")
    print()
    print(body.rstrip("\n"))


def cmd_edit(a):
    p = note_path(a.id)
    original = p.read_text(encoding="utf-8")
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "vi"
    rc = subprocess.call(shlex.split(editor) + [str(p)])
    if rc != 0:
        p.write_text(original, encoding="utf-8")
        raise NoteError(f"editor exited with status {rc}")
    try:
        meta, _ = parse_note(p.read_text(encoding="utf-8"))
        if meta["id"] != a.id:
            raise NoteError("id in frontmatter must not change")
    except (NoteError, UnicodeDecodeError) as e:
        p.write_text(original, encoding="utf-8")
        raise NoteError(f"invalid note after edit, changes reverted: {e}")


def cmd_delete(a):
    note_path(a.id).unlink()


def build_parser():
    ap = argparse.ArgumentParser(prog="note_taker", description="Markdown note-taking CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("new", help="create a note")
    p.add_argument("title")
    p.add_argument("--tags", default="", help="comma-separated tags")
    p.add_argument("--body", default=None, help="note body (default: read stdin)")
    p.set_defaults(fn=cmd_new)
    p = sub.add_parser("list", help="list notes")
    p.add_argument("--tag")
    p.add_argument("--search", help="keyword in title or body")
    p.set_defaults(fn=cmd_list)
    for name, fn, h in (("show", cmd_show, "print a note"), ("edit", cmd_edit, "edit in $EDITOR"),
                        ("delete", cmd_delete, "delete a note")):
        p = sub.add_parser(name, help=h)
        p.add_argument("id")
        p.set_defaults(fn=fn)
    return ap


def main(argv=None):
    a = build_parser().parse_args(argv)
    try:
        a.fn(a)
    except (NoteError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
