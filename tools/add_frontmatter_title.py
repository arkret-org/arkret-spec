#!/usr/bin/env python3
"""Inject `title:` frontmatter into every spec/<v>/<locale>/*.md{,x}.

Starlight's content collection schema requires a frontmatter `title`. The
existing prose was authored as plain Markdown starting with a single `#`
heading. Rather than rely on a remark plugin (which runs after schema
validation), we make the title explicit in the source by lifting the first
H1/H2 into frontmatter and stripping it from the body. Idempotent — files
that already declare `title:` are skipped.

Run from repo root: `python tools/add_frontmatter_title.py`
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "spec"

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
HEADING_RE = re.compile(r"^(#{1,2})\s+(.+?)\s*$", re.MULTILINE)


def yaml_escape(value: str) -> str:
    """Quote the title only if YAML would otherwise misparse it."""
    if any(ch in value for ch in ":#&*!|>%@`") or value.strip() != value:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def update(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    fm_match = FRONTMATTER_RE.match(text)
    if fm_match and re.search(r"^title\s*:", fm_match.group(1), re.MULTILINE):
        return False  # already has title

    body = text[fm_match.end():] if fm_match else text
    existing_fm = fm_match.group(1) if fm_match else ""

    heading_match = HEADING_RE.search(body)
    if not heading_match:
        return False
    title = heading_match.group(2).strip()
    if not title:
        return False

    # remove the heading line from the body
    body_without_heading = (body[: heading_match.start()] + body[heading_match.end():]).lstrip("\n")

    new_fm_lines = []
    if existing_fm:
        new_fm_lines.append(existing_fm.rstrip())
    new_fm_lines.append(f"title: {yaml_escape(title)}")
    new_fm = "\n".join(new_fm_lines).strip() + "\n"

    new_text = f"---\n{new_fm}---\n\n{body_without_heading}"
    if new_text == text:
        return False
    path.write_text(new_text, encoding="utf-8")
    return True


def main() -> int:
    if not SPEC.is_dir():
        print(f"spec/ not found at {SPEC}", file=sys.stderr)
        return 1
    changed = 0
    for path in sorted(SPEC.rglob("*")):
        if path.is_file() and path.suffix in {".md", ".mdx"}:
            if update(path):
                changed += 1
                print(f"updated {path.relative_to(ROOT).as_posix()}")
    print(f"{changed} file(s) updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
