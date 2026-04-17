# CLAUDE.md — Directory Organizer

## Role
Implement organizer.py strictly from spec.yaml.

## Non-Negotiable Guardrails
- Single file: organizer.py only.
- stdlib only.
- Skip rules: hidden files, files in subdirs, organizer.log itself.
- Extension matching: case-insensitive.
- --once exits; --watch loops until Ctrl-C.
- organizer.log inside target dir (not cwd).

## Extension Map
```
images:    .jpg .jpeg .png .gif .bmp .webp
documents: .pdf .doc .docx .txt .md .csv .xlsx
videos:    .mp4 .avi .mov .mkv
audio:     .mp3 .wav .flac .aac
archives:  .zip .tar .gz .rar .7z
other:     (everything else)
```

## Decision Rules
- Default mode if no flag: --once.
- dest exists → log WARNING, skip (no overwrite).
- Case-insensitive suffix: use path.suffix.lower().
- path.parent != target → skip (already in subdir).

## Known Pitfalls
- pathlib.Path.iterdir() is not recursive — use it directly (don't use rglob).
- logging FileHandler must point to target/organizer.log, not './organizer.log'.
- shutil.move destination must be a directory path (not a file path) to preserve filename.
- On macOS, pathlib may return the log file itself in iterdir(); guard with name check.
- Setup logging AFTER argparse so target dir is known.
