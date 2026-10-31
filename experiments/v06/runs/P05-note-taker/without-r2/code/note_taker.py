#!/usr/bin/env python3
"""Markdown note-taking CLI. Notes live in ~/.note-taker/ as .md files with YAML frontmatter."""

import argparse
import datetime
import os
import re
import subprocess
import shlex
import sys
from pathlib import Path


def notes_dir():
    d = Path(os.environ.get("NOTE_TAKER_DIR", Path.home() / ".note-taker"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def slugify(title):
    s = re.sub(r"[^\w]+", "-", title.lower(), flags=re.UNICODE).strip("-")
    return s or "note"


def now():
    return datetime.datetime.now().replace(microsecond=0).isoformat()


def quote(v):
    """Quote a scalar for YAML if needed."""
    if v == "" or re.search(r'[:#\[\]{},"\'\n&*!|>%@`]', v) or v != v.strip():
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
    return v


def unquote(v):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] == '"':
        return re.sub(r"\\(.)", lambda m: {"n": "\n"}.get(m.group(1), m.group(1)), v[1:-1])
    if len(v) >= 2 and v[0] == v[-1] == "'":
        return v[1:-1].replace("''", "'")
    return v


def split_list(s):
    """Split a flow-style list body on commas, respecting double quotes."""
    items, cur, inq, esc = [], "", False, False
    for ch in s:
        if esc:
            cur += ch; esc = False
        elif ch == "\\" and inq:
            cur += ch; esc = True
        elif ch == '"':
            cur += ch; inq = not inq
        elif ch == "," and not inq:
            items.append(cur); cur = ""
        else:
            cur += ch
    if cur.strip():
        items.append(cur)
    return [unquote(i) for i in items if i.strip()]


def render(meta, body):
    tags = ", ".join(quote(t) for t in meta["tags"])
    return (
        "---\n"
        f"title: {quote(meta['title'])}\n"
        f"tags: [{tags}]\n"
        f"created: {meta['created']}\n"
        f"updated: {meta['updated']}\n"
        "---\n\n"
        f"{body.strip()}\n"
    )


def parse(text):
    meta = {"title": "", "tags": [], "created": "", "updated": ""}
    body = text
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", text, re.S)
    if m:
        body = m.group(2).lstrip("\n")
        for line in m.group(1).splitlines():
            k, sep, v = line.partition(":")
            if not sep:
                continue
            k, v = k.strip(), v.strip()
            if k == "tags":
                if v.startswith("[") and v.endswith("]"):
                    meta["tags"] = split_list(v[1:-1])
                elif v:
                    meta["tags"] = split_list(v)
            elif k in meta:
                meta[k] = unquote(v)
    return meta, body


def load(path):
    meta, body = parse(path.read_text(encoding="utf-8"))
    if not meta["title"]:
        meta["title"] = path.stem
    return meta, body


def find_note(ident):
    """Resolve an id (filename stem) exactly, or by unique prefix/substring."""
    d = notes_dir()
    exact = d / f"{ident.removesuffix('.md')}.md"
    if exact.is_file():
        return exact
    files = sorted(d.glob("*.md"))
    for test in (lambda p: p.stem.startswith(ident), lambda p: ident.lower() in p.stem.lower()):
        hits = [p for p in files if test(p)]
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            sys.exit(f"Ambiguous id '{ident}': " + ", ".join(p.stem for p in hits))
    sys.exit(f"No note found matching '{ident}'")


def parse_tags(raw):
    out = []
    for t in raw or []:
        for p in t.split(","):
            p = p.strip().lstrip("#")
            if p and p not in out:
                out.append(p)
    return out


def open_editor(path):
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vi"
    try:
        subprocess.run(shlex.split(editor) + [str(path)], check=True)
    except (OSError, subprocess.CalledProcessError) as e:
        sys.exit(f"Editor failed: {e}")


def cmd_new(a):
    d = notes_dir()
    base = slugify(a.title)
    path = d / f"{base}.md"
    n = 2
    while path.exists():
        path = d / f"{base}-{n}.md"
        n += 1
    body = a.body
    if body is None and not sys.stdin.isatty():
        body = sys.stdin.read()
    ts = now()
    meta = {"title": a.title, "tags": parse_tags(a.tag), "created": ts, "updated": ts}
    path.write_text(render(meta, body or ""), encoding="utf-8")
    if body is None and not a.no_edit:
        open_editor(path)
    print(f"Created {path.stem}")


def cmd_list(a):
    tags = parse_tags(a.tag)
    kw = a.search.lower() if a.search else None
    rows = []
    for p in notes_dir().glob("*.md"):
        meta, body = load(p)
        if tags and not all(t.lower() in (x.lower() for x in meta["tags"]) for t in tags):
            continue
        if kw and kw not in (meta["title"] + "\n" + body).lower() and kw not in " ".join(meta["tags"]).lower():
            continue
        rows.append((meta["updated"] or meta["created"], p.stem, meta))
    rows.sort(key=lambda r: r[0], reverse=True)
    if not rows:
        print("No notes found.")
        return
    w = max(len(r[1]) for r in rows)
    for upd, stem, meta in rows:
        t = ",".join(meta["tags"])
        print(f"{stem:<{w}}  {upd[:16]:<16}  {meta['title']}" + (f"  [{t}]" if t else ""))


def cmd_show(a):
    p = find_note(a.id)
    if a.raw:
        print(p.read_text(encoding="utf-8"), end="")
        return
    meta, body = load(p)
    print(f"# {meta['title']}")
    if meta["tags"]:
        print("Tags: " + ", ".join(meta["tags"]))
    print(f"Created: {meta['created']}  Updated: {meta['updated']}\n")
    print(body.rstrip())


def cmd_edit(a):
    p = find_note(a.id)
    before = p.read_text(encoding="utf-8")
    open_editor(p)
    after = p.read_text(encoding="utf-8")
    if after != before:
        meta, body = parse(after)
        if not meta["title"]:
            meta["title"] = p.stem
        meta["updated"] = now()
        if not meta["created"]:
            meta["created"] = meta["updated"]
        p.write_text(render(meta, body), encoding="utf-8")
        print(f"Updated {p.stem}")
    else:
        print("No changes.")


def cmd_delete(a):
    p = find_note(a.id)
    if not a.yes:
        if input(f"Delete '{p.stem}'? [y/N] ").strip().lower() not in ("y", "yes"):
            print("Cancelled.")
            return
    p.unlink()
    print(f"Deleted {p.stem}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="note_taker", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("new", help="create a note (body from --body, stdin, or $EDITOR)")
    s.add_argument("title")
    s.add_argument("-t", "--tag", action="append", help="tag (repeatable or comma-separated)")
    s.add_argument("-b", "--body", help="note body")
    s.add_argument("--no-edit", action="store_true", help="don't open editor")
    s.set_defaults(fn=cmd_new)

    s = sub.add_parser("list", aliases=["ls"], help="list/search notes")
    s.add_argument("-t", "--tag", action="append", help="filter by tag (all must match)")
    s.add_argument("-s", "--search", help="keyword in title, body, or tags")
    s.set_defaults(fn=cmd_list)

    s = sub.add_parser("show", help="display a note")
    s.add_argument("id")
    s.add_argument("--raw", action="store_true", help="print the raw file")
    s.set_defaults(fn=cmd_show)

    s = sub.add_parser("edit", help="edit a note in $EDITOR")
    s.add_argument("id")
    s.set_defaults(fn=cmd_edit)

    s = sub.add_parser("delete", aliases=["rm"], help="delete a note")
    s.add_argument("id")
    s.add_argument("-y", "--yes", action="store_true", help="skip confirmation")
    s.set_defaults(fn=cmd_delete)

    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        sys.exit(130)
