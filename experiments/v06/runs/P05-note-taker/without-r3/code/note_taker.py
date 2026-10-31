#!/usr/bin/env python3
"""Markdown note-taking CLI. Notes are .md files with YAML frontmatter in ~/.note-taker/."""

import argparse
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path


def notes_dir():
    d = Path(os.environ.get("NOTE_TAKER_DIR", Path.home() / ".note-taker"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def slugify(title):
    s = re.sub(r"[^\w\s-]", "", title.lower()).strip()
    s = re.sub(r"[\s_-]+", "-", s)
    return s or "untitled"


def quote(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def unquote(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] == '"':
        return s[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    if len(s) >= 2 and s[0] == s[-1] == "'":
        return s[1:-1]
    return s


def split_list(s):
    return [unquote(x) for x in s.split(",") if x.strip()]


def parse(text):
    """Return (meta, body). Handles a simple YAML subset: scalars and tag lists."""
    meta = {"title": "", "tags": [], "created": "", "updated": ""}
    m = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n?(.*)\Z", text, re.S)
    if not m:
        return meta, text
    front, body = m.groups()
    body = re.sub(r"\A\r?\n", "", body, count=1)  # blank separator written by render()
    key = None
    for line in front.splitlines():
        item = re.match(r"\s+-\s+(.*)", line)
        if item and key == "tags":
            meta["tags"].append(unquote(item.group(1)))
            continue
        kv = re.match(r"([\w-]+):\s*(.*)", line)
        if not kv:
            continue
        key, val = kv.group(1), kv.group(2).strip()
        if key == "tags":
            if val.startswith("[") and val.endswith("]"):
                meta["tags"] = split_list(val[1:-1])
            elif val:
                meta["tags"] = split_list(val)
            else:
                meta["tags"] = []
        else:
            meta[key] = unquote(val)
    return meta, body


def render(meta, body):
    tags = ", ".join(quote(t) for t in meta["tags"])
    extra = [k for k in meta if k not in ("title", "tags", "created", "updated")]
    lines = [
        "---",
        f"title: {quote(meta['title'])}",
        f"tags: [{tags}]",
        f"created: {meta['created']}",
        f"updated: {meta['updated']}",
        *[f"{k}: {quote(str(meta[k]))}" for k in extra],
        "---",
        "",
        body.lstrip("\n"),
    ]
    out = "\n".join(lines)
    return out if out.endswith("\n") else out + "\n"


def now():
    return datetime.now().replace(microsecond=0).isoformat()


def parse_tags(s):
    return [t.strip() for t in (s or "").split(",") if t.strip()]


def all_notes():
    notes = []
    for p in sorted(notes_dir().glob("*.md")):
        meta, body = parse(p.read_text(encoding="utf-8"))
        meta["title"] = meta["title"] or p.stem
        notes.append((p, meta, body))
    return notes


def find(ident):
    """Resolve a note by exact id (filename stem), unique id prefix, or exact title."""
    notes = all_notes()
    exact = [n for n in notes if n[0].stem == ident]
    if not exact:
        exact = [n for n in notes if n[1]["title"].lower() == ident.lower()]
    if not exact:
        exact = [n for n in notes if n[0].stem.startswith(ident)]
    if not exact:
        sys.exit(f"error: no note matching '{ident}'")
    if len(exact) > 1:
        names = ", ".join(n[0].stem for n in exact)
        sys.exit(f"error: '{ident}' is ambiguous: {names}")
    return exact[0]


def edit_in_editor(path):
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vi"
    import shlex
    return subprocess.call(shlex.split(editor) + [str(path)])


def cmd_new(args):
    d = notes_dir()
    base = slugify(args.title)
    path = d / f"{base}.md"
    n = 2
    while path.exists():
        path = d / f"{base}-{n}.md"
        n += 1
    ts = now()
    meta = {"title": args.title, "tags": parse_tags(args.tags), "created": ts, "updated": ts}
    body = args.body
    if body is None and not sys.stdin.isatty():
        body = sys.stdin.read()
    path.write_text(render(meta, body or ""), encoding="utf-8")
    if body is None and not args.no_edit:
        edit_in_editor(path)
    print(f"created {path.stem}")


def cmd_list(args):
    tags = {t.lower() for t in parse_tags(args.tag)}
    kw = (args.search or "").lower()
    rows = []
    for p, meta, body in all_notes():
        have = {t.lower() for t in meta["tags"]}
        if tags and not tags <= have:
            continue
        if kw and kw not in (meta["title"] + "\n" + body + "\n" + " ".join(meta["tags"])).lower():
            continue
        rows.append((p, meta))
    rows.sort(key=lambda r: r[1]["updated"], reverse=True)
    if not rows:
        print("no notes found")
        return
    w = max(len(r[0].stem) for r in rows)
    for p, meta in rows:
        tg = " ".join(f"#{t}" for t in meta["tags"])
        print(f"{p.stem:<{w}}  {meta['updated'][:10]}  {meta['title']}  {tg}".rstrip())


def cmd_show(args):
    p, meta, body = find(args.note)
    if args.raw:
        sys.stdout.write(p.read_text(encoding="utf-8"))
        return
    print(f"# {meta['title']}")
    if meta["tags"]:
        print("tags: " + ", ".join(meta["tags"]))
    print(f"created: {meta['created']}  updated: {meta['updated']}\n")
    sys.stdout.write(body if body.endswith("\n") else body + "\n")


def cmd_edit(args):
    p, meta, body = find(args.note)
    changed = args.title or args.tags is not None or args.append is not None
    if args.title:
        meta["title"] = args.title
    if args.tags is not None:
        meta["tags"] = parse_tags(args.tags)
    if args.append is not None:
        body = body.rstrip("\n") + "\n\n" + args.append + "\n"
    if changed:
        meta["updated"] = now()
        p.write_text(render(meta, body), encoding="utf-8")
    else:
        before = p.stat().st_mtime_ns
        if edit_in_editor(p) != 0:
            sys.exit("error: editor exited with an error")
        if p.stat().st_mtime_ns != before:
            meta2, body2 = parse(p.read_text(encoding="utf-8"))
            meta2["title"] = meta2["title"] or p.stem
            meta2["updated"] = now()
            p.write_text(render(meta2, body2), encoding="utf-8")
    print(f"updated {p.stem}")


def cmd_delete(args):
    p, meta, _ = find(args.note)
    if not args.yes:
        if input(f"delete '{meta['title']}' ({p.stem})? [y/N] ").strip().lower() != "y":
            print("cancelled")
            return
    p.unlink()
    print(f"deleted {p.stem}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="note_taker", description="Markdown note-taking CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("new", help="create a note")
    s.add_argument("title")
    s.add_argument("-t", "--tags", help="comma-separated tags")
    s.add_argument("-b", "--body", help="note body (otherwise stdin or $EDITOR)")
    s.add_argument("--no-edit", action="store_true", help="don't open the editor")
    s.set_defaults(fn=cmd_new)

    s = sub.add_parser("list", help="list/search notes")
    s.add_argument("-t", "--tag", help="comma-separated tags (all must match)")
    s.add_argument("-s", "--search", help="keyword in title, tags or body")
    s.set_defaults(fn=cmd_list)

    s = sub.add_parser("show", help="display a note")
    s.add_argument("note", help="id, id prefix, or title")
    s.add_argument("--raw", action="store_true", help="print the file as stored")
    s.set_defaults(fn=cmd_show)

    s = sub.add_parser("edit", help="edit a note (opens $EDITOR unless flags given)")
    s.add_argument("note")
    s.add_argument("--title", help="set new title")
    s.add_argument("-t", "--tags", help="replace tags (comma-separated)")
    s.add_argument("-a", "--append", help="append text to the body")
    s.set_defaults(fn=cmd_edit)

    s = sub.add_parser("delete", help="delete a note")
    s.add_argument("note")
    s.add_argument("-y", "--yes", action="store_true", help="skip confirmation")
    s.set_defaults(fn=cmd_delete)

    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
