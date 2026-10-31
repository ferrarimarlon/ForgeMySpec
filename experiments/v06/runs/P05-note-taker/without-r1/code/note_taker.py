#!/usr/bin/env python3
"""note_taker: a Markdown note-taking CLI.

Notes are stored as .md files with YAML frontmatter in ~/.note-taker/
(override with the NOTE_TAKER_DIR environment variable).
"""
import argparse
import datetime as dt
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path


def notes_dir():
    d = Path(os.environ.get("NOTE_TAKER_DIR") or Path.home() / ".note-taker")
    d.mkdir(parents=True, exist_ok=True)
    return d


def slugify(text):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:50].strip("-") or "note"


def now():
    return dt.datetime.now().replace(microsecond=0).isoformat()


# ---------- frontmatter ----------

def _quote(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _unquote(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] == '"':
        return re.sub(r"\\(.)", r"\1", s[1:-1])
    if len(s) >= 2 and s[0] == s[-1] == "'":
        return s[1:-1].replace("''", "'")
    return s


def _split_list(s):
    items, cur, q = [], "", None
    i = 0
    while i < len(s):
        c = s[i]
        if q:
            cur += c
            if c == "\\" and q == '"' and i + 1 < len(s):
                i += 1
                cur += s[i]
            elif c == q:
                q = None
        elif c in "\"'":
            q = c
            cur += c
        elif c == ",":
            items.append(cur)
            cur = ""
        else:
            cur += c
        i += 1
    if cur.strip():
        items.append(cur)
    return [_unquote(x) for x in items if x.strip()]


def parse(text):
    """Return (meta dict, body)."""
    meta, body = {}, text
    m = re.match(r"\A---[ \t]*\r?\n(.*?\r?\n)?---[ \t]*(?:\r?\n|\Z)", text, re.S)
    if not m:
        return meta, body
    body = text[m.end():]
    lines = (m.group(1) or "").splitlines()
    key = None
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        li = re.match(r"\s+-\s+(.*)", line)
        if li and key and isinstance(meta.get(key), list):
            meta[key].append(_unquote(li.group(1)))
            continue
        kv = re.match(r"([A-Za-z_][\w-]*)\s*:\s*(.*)", line)
        if not kv:
            continue
        key, val = kv.group(1), kv.group(2).strip()
        if val.startswith("[") and val.endswith("]"):
            meta[key] = _split_list(val[1:-1])
        elif val == "":
            meta[key] = []
        else:
            meta[key] = _unquote(val)
    return meta, body


def dump(meta, body):
    out = ["---", f"title: {_quote(meta.get('title', ''))}"]
    tags = meta.get("tags") or []
    out.append("tags: [" + ", ".join(_quote(t) for t in tags) + "]")
    out.append(f"created: {meta.get('created', now())}")
    out.append(f"updated: {meta.get('updated', now())}")
    out.append("---")
    out.append("")
    return "\n".join(out) + body.lstrip("\n")


# ---------- storage ----------

class Note:
    def __init__(self, path):
        self.path = path
        self.id = path.stem
        text = path.read_text(encoding="utf-8")
        self.meta, self.body = parse(text)
        self.title = self.meta.get("title") or self.id
        tags = self.meta.get("tags", [])
        self.tags = [tags] if isinstance(tags, str) else tags
        self.created = str(self.meta.get("created", ""))
        self.updated = str(self.meta.get("updated", ""))


def all_notes():
    notes = []
    for p in sorted(notes_dir().glob("*.md")):
        try:
            notes.append(Note(p))
        except (OSError, UnicodeDecodeError) as e:
            print(f"warning: skipping {p.name}: {e}", file=sys.stderr)
    return notes


def find(ident):
    """Resolve a note by exact id, then unique id prefix, then unique title match."""
    notes = all_notes()
    for n in notes:
        if n.id == ident:
            return n
    cands = [n for n in notes if n.id.startswith(ident)]
    if not cands:
        cands = [n for n in notes if ident.lower() in n.title.lower()]
    if len(cands) == 1:
        return cands[0]
    if not cands:
        sys.exit(f"error: no note matching '{ident}'")
    sys.exit("error: ambiguous '%s'; matches:\n%s" % (
        ident, "\n".join(f"  {n.id}  {n.title}" for n in cands)))


def unique_path(slug):
    d = notes_dir()
    p = d / f"{slug}.md"
    i = 2
    while p.exists():
        p = d / f"{slug}-{i}.md"
        i += 1
    return p


def parse_tags(values):
    tags = []
    for v in values or []:
        for t in v.split(","):
            t = t.strip().lstrip("#")
            if t and t not in tags:
                tags.append(t)
    return tags


def open_editor(path):
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vi"
    try:
        return subprocess.call(shlex.split(editor) + [str(path)])
    except FileNotFoundError:
        sys.exit(f"error: editor not found: {editor} (set $EDITOR)")


# ---------- commands ----------

def cmd_new(a):
    tags = parse_tags(a.tag)
    if a.body is not None:
        body = a.body
    elif not sys.stdin.isatty():
        body = sys.stdin.read()
    else:
        body = ""
    ts = now()
    meta = {"title": a.title, "tags": tags, "created": ts, "updated": ts}
    path = unique_path(slugify(a.title))
    path.write_text(dump(meta, body), encoding="utf-8")
    if a.body is None and sys.stdin.isatty():
        open_editor(path)
        touch_updated(path)
    print(f"created {path.stem}")


def touch_updated(path):
    meta, body = parse(path.read_text(encoding="utf-8"))
    meta["updated"] = now()
    path.write_text(dump(meta, body), encoding="utf-8")


def cmd_list(a):
    notes = all_notes()
    if a.tag:
        want = {t.lower() for t in parse_tags(a.tag)}
        notes = [n for n in notes if want <= {t.lower() for t in n.tags}]
    if a.search:
        kw = a.search.lower()
        notes = [n for n in notes
                 if kw in n.title.lower() or kw in n.body.lower()
                 or any(kw in t.lower() for t in n.tags)]
    notes.sort(key=lambda n: n.updated, reverse=True)
    if not notes:
        print("no notes found")
        return
    for n in notes:
        tags = " ".join(f"#{t}" for t in n.tags)
        print(f"{n.id:<30} {n.updated[:10]}  {n.title}  {tags}".rstrip())


def cmd_show(a):
    n = find(a.note)
    if a.raw:
        print(n.path.read_text(encoding="utf-8"), end="")
        return
    print(f"# {n.title}")
    print(f"id: {n.id}  tags: {', '.join(n.tags) or '-'}")
    print(f"created: {n.created}  updated: {n.updated}\n")
    print(n.body, end="" if n.body.endswith("\n") else "\n")


def cmd_edit(a):
    n = find(a.note)
    before = n.path.read_text(encoding="utf-8")
    if a.title or a.tag or a.body is not None:
        if a.title:
            n.meta["title"] = a.title
        if a.tag:
            n.meta["tags"] = parse_tags(a.tag)
        body = n.body if a.body is None else a.body
        n.meta["updated"] = now()
        n.path.write_text(dump(n.meta, body), encoding="utf-8")
    else:
        open_editor(n.path)
        if n.path.read_text(encoding="utf-8") != before:
            touch_updated(n.path)
    print(f"updated {n.id}")


def cmd_delete(a):
    n = find(a.note)
    if not a.yes:
        if not sys.stdin.isatty():
            sys.exit("error: refusing to delete without --yes when not interactive")
        if input(f"delete '{n.title}' ({n.id})? [y/N] ").strip().lower() not in ("y", "yes"):
            print("aborted")
            return
    n.path.unlink()
    print(f"deleted {n.id}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="note_taker", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("new", help="create a note (body from -b, stdin, or $EDITOR)")
    s.add_argument("title")
    s.add_argument("-t", "--tag", action="append", help="tag (repeat or comma-separate)")
    s.add_argument("-b", "--body", help="note body")
    s.set_defaults(fn=cmd_new)

    s = sub.add_parser("list", help="list notes, optionally filtered")
    s.add_argument("-t", "--tag", action="append", help="require tag (repeatable)")
    s.add_argument("-s", "--search", metavar="KEYWORD", help="keyword in title, body, or tags")
    s.set_defaults(fn=cmd_list)

    s = sub.add_parser("show", help="show a note")
    s.add_argument("note", help="id, id prefix, or title fragment")
    s.add_argument("--raw", action="store_true", help="print the file as stored")
    s.set_defaults(fn=cmd_show)

    s = sub.add_parser("edit", help="edit in $EDITOR, or set --title/--tag/--body")
    s.add_argument("note")
    s.add_argument("--title")
    s.add_argument("-t", "--tag", action="append", help="replace tags")
    s.add_argument("-b", "--body", help="replace body")
    s.set_defaults(fn=cmd_edit)

    s = sub.add_parser("delete", help="delete a note")
    s.add_argument("note")
    s.add_argument("-y", "--yes", action="store_true", help="skip confirmation")
    s.set_defaults(fn=cmd_delete)

    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
