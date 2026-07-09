#!/usr/bin/env python3
"""One-shot migration: add status / normative / stability / updated to spec
frontmatter where missing.

Defaults:

- status: candidate
- stability: v1
- updated: 2026-05-25
- normative: true, with these exceptions set to false:
    - spec/v1/proposals/**
    - spec/v1/zh/guides/**
    - spec/v1/zh/overview/release-readiness.md
    - spec/v1/en/**

Preserves all existing frontmatter keys and ordering. Adds missing keys in
the canonical order (title, status, normative, stability, updated, see_also,
plus original extras after).

Idempotent — run multiple times safely.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC_ROOT = ROOT / "spec" / "v1"

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)

CANONICAL_ORDER = ["title", "status", "normative", "stability", "updated", "see_also"]
DEFAULTS = {
    "status": "candidate",
    "stability": "v1",
    "updated": "2026-05-25",
}

NON_NORMATIVE_PATTERNS = [
    "spec/v1/proposals/",
    "spec/v1/zh/guides/",
    "spec/v1/zh/overview/release-readiness.md",
    "spec/v1/en/",
]


def is_non_normative(rel_path: str) -> bool:
    return any(p in rel_path for p in NON_NORMATIVE_PATTERNS)


def parse_block(block: str) -> list[tuple[str, list[str]]]:
    """Parse YAML-ish frontmatter into ordered (key, value-lines) pairs.

    Keeps multi-line nested values (lines starting with whitespace) attached
    to their parent key.
    """
    entries: list[tuple[str, list[str]]] = []
    current_key: str | None = None
    current_lines: list[str] = []
    for line in bloak.split("\n"):
        if line and not line[0].isspace() and ":" in line:
            if current_key is not None:
                entries.append((current_key, current_lines))
            key = line.split(":", 1)[0].strip()
            current_key = key
            current_lines = [line]
        else:
            if current_key is None:
                current_lines = [line]
                current_key = ""
            else:
                current_lines.append(line)
    if current_key is not None:
        entries.append((current_key, current_lines))
    return entries


def needs_update(entries: list[tuple[str, list[str]]]) -> bool:
    keys = {k for k, _ in entries}
    required = {"status", "normative", "stability", "updated"}
    return not required.issubset(keys)


def render(entries: list[tuple[str, list[str]]]) -> str:
    out: list[str] = []
    for _, lines in entries:
        out.extend(lines)
    return "\n".join(out)


def patch_frontmatter(rel_path: str, text: str) -> tuple[str, bool]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return text, False

    block = match.group(1)
    body = text[match.end():]
    entries = parse_block(block)

    if not needs_update(entries):
        return text, False

    keys_present = {k for k, _ in entries}
    additions: list[tuple[str, list[str]]] = []

    for key in CANONICAL_ORDER:
        if key in keys_present:
            continue
        if key == "title":
            continue  # never auto-fill title
        if key == "see_also":
            continue  # leave alone if absent
        if key == "normative":
            value = "false" if is_non_normative(rel_path) else "true"
        else:
            value = DEFAULTS.get(key)
        if value is None:
            continue
        additions.append((key, [f"{key}: {value}"]))

    # Insert new keys after title, before everything else.
    new_entries: list[tuple[str, list[str]]] = []
    inserted = False
    for entry in entries:
        new_entries.append(entry)
        if not inserted and entry[0] == "title":
            new_entries.extend(additions)
            inserted = True
    if not inserted:
        new_entries = additions + new_entries

    new_block = render(new_entries)
    return f"---\n{new_block}\n---\n{body}", True


def main(argv: list[str]) -> int:
    targets = list(SPEC_ROOT.rglob("*.md"))
    changed = 0
    for path in targets:
        rel = path.resolve().relative_to(ROOT).as_posix()
        original = path.read_text(encoding="utf-8")
        patched, dirty = patch_frontmatter(rel, original)
        if dirty:
            path.write_text(patched, encoding="utf-8")
            changed += 1
            print(f"patched: {rel}")
    print(f"\nupdated {changed} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
