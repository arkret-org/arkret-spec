#!/usr/bin/env python3
"""Bulk-rename ULID terminology to UUIDv7 in all prose / schema text.

Replacements:
  - `<ulid>`   → `<uuid>`        (placeholder in ak:<kind>:<ulid> templates)
  - `typed ULID` / `typed-ULID` / `typed-ULID pattern` → `typed UUIDv7` / `typed-UUIDv7`
  - 全角 ULID variants → UUIDv7
  - "26 字符" / "26 char" / "26-character" → "36 字符" / "36 char" / "36-character"
  - "Crockford" mentions stripped where they refer to the ULID alphabet
  - `[0-9a-hjkmnp-z]` (Crockford char class) → drop / replace with hex

This is a best-effort sed pass; the encoding.md §4 paragraph and other
substantive prose blocks were rewritten by hand earlier.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "spec" / "v1"

REPLACEMENTS = [
    # placeholder in templates
    (re.compile(r"<ulid>"), "<uuid>"),
    # typed-ULID compounds
    (re.compile(r"typed[- ]ULID(?: pattern)?"), "typed-UUIDv7"),
    (re.compile(r"typed ULID"), "typed UUIDv7"),
    # standalone "ULID" → "UUIDv7" (only as protocol token, not when it refers to
    # the historical ULID spec / archived doc)
    (re.compile(r"\bULID\b"), "UUIDv7"),
    (re.compile(r"\bulid\b"), "uuid"),
    # Crockford alphabet references
    (re.compile(r"小写 Crockford Base32 字符集 `\[0-9a-hjkmnp-z\]`"), "小写 hex 字符集 `[0-9a-f]`"),
    (re.compile(r"Crockford Base32"), "lowercase hex"),
    (re.compile(r"Crockford"), "hex"),
    # length references where the context is wire ID
    (re.compile(r"26 个字符"), "36 个字符"),
    (re.compile(r"26 字符"), "36 字符"),
    (re.compile(r"26-character"), "36-character"),
    (re.compile(r"26 char\b"), "36 char"),
]


def main() -> int:
    changed = 0
    targets: list[Path] = []
    for ext in ("*.md", "*.mdx", "*.json", "*.yaml", "*.yml"):
        targets.extend(SPEC.rglob(ext))
    for path in sorted(set(targets)):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        new = text
        for pat, rep in REPLACEMENTS:
            new = pat.sub(rep, new)
        if new != text:
            path.write_text(new, encoding="utf-8")
            changed += 1
    print(f"updated {changed} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
