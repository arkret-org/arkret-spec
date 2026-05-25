#!/usr/bin/env python3
"""One-shot: insert §0 normative-language reference into normative docs.

For every spec/v1/zh/*.md file whose frontmatter has `normative: true` and
whose body does not yet mention `normative-language.md`, insert a §0
section before the first `## ` heading. The reference path is computed
relative to the file.

Idempotent.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC_ZH = ROOT / "spec" / "v1" / "zh"
TARGET = SPEC_ZH / "conformance" / "normative-language.md"

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
FIRST_H2_RE = re.compile(r"^## ", re.MULTILINE)
NORMATIVE_RE = re.compile(r"^normative:\s*true\s*$", re.MULTILINE)


def make_block(rel_path: str) -> str:
    return (
        "## 0. 规范语言\n\n"
        f"本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 "
        f"[conformance/normative-language.md]({rel_path}) 解释；"
        f"仅大写形式具规范约束力。\n\n"
    )


def patch(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    fm = FRONTMATTER_RE.match(text)
    if not fm:
        return False
    if not NORMATIVE_RE.search(fm.group(1)):
        return False
    body = text[fm.end():]
    if "normative-language.md" in body:
        return False

    h2 = FIRST_H2_RE.search(body)
    if not h2:
        return False

    depth = len(path.relative_to(SPEC_ZH).parts) - 1
    prefix = "../" * depth
    rel_path = f"{prefix}conformance/normative-language.md"

    insertion = make_block(rel_path)
    new_body = body[: h2.start()] + insertion + body[h2.start():]
    path.write_text(text[: fm.end()] + new_body, encoding="utf-8")
    return True


def main(argv: list[str]) -> int:
    changed = 0
    for path in sorted(SPEC_ZH.rglob("*.md")):
        if path == TARGET:
            continue
        if patch(path):
            changed += 1
            rel = path.resolve().relative_to(ROOT).as_posix()
            print(f"patched: {rel}")
    print(f"\nupdated {changed} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
