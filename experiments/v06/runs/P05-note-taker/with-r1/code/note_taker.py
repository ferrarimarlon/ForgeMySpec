#!/usr/bin/env python3
"""note-taker: a Markdown note CLI. Notes are .md files with YAML frontmatter
stored in ~/.note-taker/ (override with NOTE_TAKER_DIR). Standard library only."""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shlex
import subprocess
import sys

ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class NoteError(Exception):
    pass


def notes_dir():
    return os.environ.get("NOTE_TAKER_DIR") or os.path.join(os.path.expanduser("~"), ".note-taker")


def now():
    return datetime.datetime.now().replace(microsecond=0).isoformat()


def slugify(title):
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "note"


def note_path(note_id):
    if note_id.endswith(".md"):
        note_id = note_id[:-3]
    if not ID_RE.match(note_id) or ".." in note_id:
        raise NoteError("invalid note id: %r" % note_id)
    return os.path.join(notes_dir(), note_id + ".md")


def dump(meta, body):
    head = [
        "---",
        "title: " + json.dumps(meta["title"], ensure_ascii=False),
        "tags: " + json.dumps(meta["tags"], ensure_ascii=False),
        "created: " + meta["created"],
        "updated: " + meta["updated"],
        "---",
    ]
    return "\n".join(head) + "\n" + body.rstrip("\n") + "\n"


def parse(text):
    """Return (meta, body). Tolerates missing or hand-edited frontmatter."""
    meta = {"title": "", "tags": [], "created": "", "updated": ""}
    lines = text.split("\n")
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                for ln in lines[1:i]:
                    key, sep, val = ln.partition(":")
                    key, val = key.strip(), val.strip()
                    if not sep or key not in meta:
                        continue
                    if key == "tags":
                        meta[key] = _parse_tags(val)
                    elif key == "title":
                        meta[key] = _unquote(val)
                    else:
                        meta[key] = val
                return meta, "\n".join(lines[i + 1:])
    return meta, text


def _unquote(val):
    if val[:1] in ('"', "'"):
        try:
            return json.loads(val) if val[0] == '"' else val.strip("'")
        except ValueError:
            return val.strip("\"'")
    return val


def _parse_tags(val):
    try:
        data = json.loads(val)
        if isinstance(data, list):
            return [str(t) for t in data]
    except ValueError:
        pass
    inner = val.strip()[1:-1] if val.strip().startswith("[") else val
    return [t.strip().strip("\"'") for t in inner.split(",") if t.strip()]


def load(note_id):
    path = note_path(note_id)
    if not os.path.isfile(path):
        raise NoteError("no such note: %s" % note_id)
    with open(path, encoding="utf-8") as f:
        meta, body = parse(f.read())
    return path, meta, body


def run_editor(path):
    cmd = shlex.split(os.environ.get("EDITOR") or os.environ.get("VISUAL") or "vi")
    try:
        rc = subprocess.call(cmd + [path])
    except OSError as e:
        raise NoteError("cannot run editor %r: %s" % (cmd[0], e))
    if rc != 0:
        raise NoteError("editor exited with status %d" % rc)


def cmd_new(args):
    d = notes_dir()
    os.makedirs(d, exist_ok=True)
    base = slugify(args.title)
    note_id, n = base, 1
    while os.path.exists(os.path.join(d, note_id + ".md")):
        n += 1
        note_id = "%s-%d" % (base, n)
    tags = []
    for t in args.tag or []:
        tags.extend(x.strip() for x in t.split(",") if x.strip())
    ts = now()
    meta = {"title": args.title, "tags": tags, "created": ts, "updated": ts}
    body = args.body
    if body is None and not sys.stdin.isatty():
        body = sys.stdin.read()
    path = os.path.join(d, note_id + ".md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(dump(meta, body or ""))
    if body is None:
        run_editor(path)
    print(note_id)


def cmd_list(args):
    d = notes_dir()
    rows = []
    if os.path.isdir(d):
        for name in os.listdir(d):
            if not name.endswith(".md"):
                continue
            with open(os.path.join(d, name), encoding="utf-8") as f:
                meta, body = parse(f.read())
            if args.tag and args.tag.lower() not in [t.lower() for t in meta["tags"]]:
                continue
            if args.search:
                kw = args.search.lower()
                if kw not in meta["title"].lower() and kw not in body.lower():
                    continue
            rows.append((meta["updated"], name[:-3], meta))
    rows.sort(key=lambda r: (r[0], r[1]), reverse=True)
    for _, note_id, meta in rows:
        tags = " ".join("#" + t for t in meta["tags"])
        print("%s\t%s\t%s" % (note_id, meta["title"], tags))


def cmd_show(args):
    _, meta, body = load(args.id)
    print("# " + meta["title"])
    if meta["tags"]:
        print("tags: " + ", ".join(meta["tags"]))
    print("created: %s  updated: %s\n" % (meta["created"], meta["updated"]))
    print(body.strip("\n"))


def cmd_edit(args):
    path, _, _ = load(args.id)
    run_editor(path)
    with open(path, encoding="utf-8") as f:
        meta, body = parse(f.read())
    meta["updated"] = now()
    if not meta["title"]:
        meta["title"] = args.id
    if not meta["created"]:
        meta["created"] = meta["updated"]
    with open(path, "w", encoding="utf-8") as f:
        f.write(dump(meta, body))


def cmd_delete(args):
    path, _, _ = load(args.id)
    os.remove(path)
    print("deleted " + args.id)


def build_parser():
    p = argparse.ArgumentParser(prog="note_taker", description="Markdown note-taking CLI")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("new", help="create a note")
    s.add_argument("title")
    s.add_argument("-t", "--tag", action="append", help="tag (repeatable or comma-separated)")
    s.add_argument("-b", "--body", help="note body (else stdin, else $EDITOR)")
    s.set_defaults(func=cmd_new)
    s = sub.add_parser("list", help="list notes, optionally filtered")
    s.add_argument("--tag", help="only notes with this tag")
    s.add_argument("-s", "--search", help="only notes whose title or body contains this keyword")
    s.set_defaults(func=cmd_list)
    for name, fn, h in (("show", cmd_show, "print a note"), ("edit", cmd_edit, "edit a note in $EDITOR"),
                        ("delete", cmd_delete, "delete a note")):
        s = sub.add_parser(name, help=h)
        s.add_argument("id")
        s.set_defaults(func=fn)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except NoteError as e:
        print("error: %s" % e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
