#!/usr/bin/env python3
"""One-shot fix: replace half-width ',' / ';' with full-width '，' / '；'
when both neighbors are CJK characters.

Skips:
- frontmatter block
- fenced code blocks (``` ... ```)
- inline code spans (`...`)
- URL-bearing lines (heuristic: lines containing http:// or https://)

Idempotent.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC_ROOT = ROOT / "spec" / "v1" / "zh"

CJK = r"[一-鿿]"
PATTERN = re.compile(rf"({CJK})([,;])({CJK})")
INLINE_CODE = re.compile(r"`[^`\n]*`")
URL_RE = re.compile(r"https?://\S+")
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)

MAP = {",": "，", ";": "；"}


def fix_segment(text: str) -> str:
    placeholders: list[str] = []

    def stash(match: re.Match[str]) -> str:
        placeholders.append(match.group(0))
        return f"\x00CODE{len(placeholders) - 1}\x00"

    # Mask URLs first (they may contain inline_code-like sequences but
    # are not real code spans).
    stashed = URL_RE.sub(stash, text)
    stashed = INLINE_CODE.sub(stash, stashed)
    fixed = PATTERN.sub(lambda m: m.group(1) + MAP[m.group(2)] + m.group(3), stashed)
    while True:
        prev = fixed
        fixed = PATTERN.sub(lambda m: m.group(1) + MAP[m.group(2)] + m.group(3), fixed)
        if fixed == prev:
            break

    def restore(match: re.Match[str]) -> str:
        return placeholders[int(match.group(1))]

    return re.sub(r"\x00CODE(\d+)\x00", restore, fixed)


def fix_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    fm_match = FRONTMATTER_RE.match(text)
    if fm_match:
        head = text[: fm_match.end()]
        body = text[fm_match.end():]
    else:
        head, body = "", text

    in_code = False
    out_lines: list[str] = []
    changed = False
    for line in body.split("\n"):
        if line.lstrip().startswith("```"):
            in_code = not in_code
            out_lines.append(line)
            continue
        if in_code:
            out_lines.append(line)
            continue
        fixed = fix_segment(line)
        if fixed != line:
            changed = True
        out_lines.append(fixed)

    if not changed:
        return False
    path.write_text(head + "\n".join(out_lines), encoding="utf-8")
    return True


def main(argv: list[str]) -> int:
    targets = list(SPEC_ROOT.rglob("*.md"))
    changed = 0
    for path in targets:
        if fix_file(path):
            changed += 1
            rel = path.resolve().relative_to(ROOT).as_posix()
            print(f"fixed: {rel}")
    print(f"\nupdated {changed} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
