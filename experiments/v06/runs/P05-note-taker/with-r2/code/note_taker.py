#!/usr/bin/env python3
"""Markdown note-taking CLI. Notes are .md files with YAML frontmatter."""
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


def slugify(title):
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "note"


def _quote(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _unquote(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] == '"':
        return re.sub(r"\\(.)", r"\1", s[1:-1])
    if len(s) >= 2 and s[0] == s[-1] == "'":
        return s[1:-1]
    return s


def _split_tags(s):
    s = s.strip()
    if s.startswith("[") and s.endswith("]"):
        s = s[1:-1]
    items, cur, q = [], "", None
    i = 0
    while i < len(s):
        c = s[i]
        if q:
            if c == "\\" and q == '"' and i + 1 < len(s):
                cur += s[i:i + 2]
                i += 2
                continue
            if c == q:
                q = None
            cur += c
        elif c in "\"'":
            q = c
            cur += c
        elif c == ",":
            items.append(cur)
            cur = ""
        else:
            cur += c
        i += 1
    items.append(cur)
    return [_unquote(t) for t in items if t.strip()]


def render(title, tags, created, body):
    tag_list = ", ".join(_quote(t) for t in tags)
    return "---\ntitle: %s\ntags: [%s]\ncreated: %s\n---\n%s" % (
        _quote(title), tag_list, created, body)


def parse(text):
    """Return (meta, body). Raises ValueError on malformed frontmatter."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        raise ValueError("missing frontmatter")
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        raise ValueError("unterminated frontmatter")
    meta = {"title": "", "tags": [], "created": ""}
    for line in lines[1:end]:
        if not line.strip():
            continue
        if ":" not in line:
            raise ValueError("bad frontmatter line: %r" % line)
        key, value = line.split(":", 1)
        key = key.strip()
        if key == "tags":
            meta["tags"] = _split_tags(value)
        elif key in ("title", "created"):
            meta[key] = _unquote(value)
    if not meta["title"]:
        raise ValueError("frontmatter has no title")
    return meta, "\n".join(lines[end + 1:])


def note_path(note_id):
    if not re.fullmatch(r"[A-Za-z0-9._-]+", note_id) or note_id.startswith("."):
        return None
    return notes_dir() / (note_id + ".md")


def load(note_id):
    path = note_path(note_id)
    if path is None or not path.is_file():
        return None
    meta, body = parse(path.read_text(encoding="utf-8"))
    return path, meta, body


def all_notes():
    d = notes_dir()
    result = []
    if not d.is_dir():
        return result
    for p in sorted(d.glob("*.md")):
        try:
            meta, body = parse(p.read_text(encoding="utf-8"))
        except (ValueError, OSError, UnicodeDecodeError):
            continue
        result.append((p.stem, meta, body))
    return result


def err(msg):
    print("note-taker: " + msg, file=sys.stderr)
    return 1


def cmd_new(args):
    d = notes_dir()
    d.mkdir(parents=True, exist_ok=True)
    base = slugify(args.title)
    note_id, n = base, 2
    while (d / (note_id + ".md")).exists():
        note_id = "%s-%d" % (base, n)
        n += 1
    body = args.body
    if body is None:
        body = sys.stdin.read() if not sys.stdin.isatty() else ""
    if body and not body.endswith("\n"):
        body += "\n"
    created = datetime.datetime.now().replace(microsecond=0).isoformat()
    tags = [t.strip() for t in (args.tag or []) if t.strip()]
    (d / (note_id + ".md")).write_text(
        render(args.title, tags, created, body), encoding="utf-8")
    print(note_id)
    return 0


def cmd_list(args):
    kw = args.search.lower() if args.search else None
    for note_id, meta, body in all_notes():
        if args.tag and args.tag.lower() not in [t.lower() for t in meta["tags"]]:
            continue
        if kw and kw not in meta["title"].lower() and kw not in body.lower():
            continue
        tags = ",".join(meta["tags"])
        print("%s\t%s\t[%s]" % (note_id, meta["title"], tags))
    return 0


def cmd_show(args):
    try:
        found = load(args.id)
    except (ValueError, OSError) as e:
        return err("cannot read note %s: %s" % (args.id, e))
    if found is None:
        return err("no such note: %s" % args.id)
    path, _, _ = found
    sys.stdout.write(path.read_text(encoding="utf-8"))
    return 0


def cmd_edit(args):
    path = note_path(args.id)
    if path is None or not path.is_file():
        return err("no such note: %s" % args.id)
    editor = shlex.split(os.environ.get("EDITOR") or "vi")
    try:
        rc = subprocess.call(editor + [str(path)])
    except OSError as e:
        return err("cannot run editor: %s" % e)
    if rc != 0:
        return err("editor exited with status %d" % rc)
    try:
        parse(path.read_text(encoding="utf-8"))
    except ValueError as e:
        return err("note %s now has invalid frontmatter: %s" % (args.id, e))
    return 0


def cmd_delete(args):
    path = note_path(args.id)
    if path is None or not path.is_file():
        return err("no such note: %s" % args.id)
    path.unlink()
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="note_taker", description="Markdown note taker")
    sub = p.add_subparsers(dest="command", required=True)
    n = sub.add_parser("new", help="create a note")
    n.add_argument("title")
    n.add_argument("-t", "--tag", action="append", help="tag (repeatable)")
    n.add_argument("-b", "--body", help="note body (default: stdin)")
    n.set_defaults(func=cmd_new)
    l = sub.add_parser("list", help="list notes")
    l.add_argument("--tag", help="only notes with this tag")
    l.add_argument("--search", help="only notes whose title or body contains this")
    l.set_defaults(func=cmd_list)
    for name, fn, h in (("show", cmd_show, "print a note"),
                        ("edit", cmd_edit, "edit a note in $EDITOR"),
                        ("delete", cmd_delete, "delete a note")):
        s = sub.add_parser(name, help=h)
        s.add_argument("id")
        s.set_defaults(func=fn)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
