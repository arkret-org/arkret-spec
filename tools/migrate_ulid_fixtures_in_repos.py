#!/usr/bin/env python3
"""Migrate ULID-shaped test/example IDs to UUIDv7 across implementation repos
(soland, yougen, floria, chime, sodmin, cotest, cokret-rust-sdk).

Reuses the typed-prefix-anchored regex from migrate_ulid_to_uuid7.py to
restrict replacements to actual `ck:<kind>:<26-char>` references and quoted
JSON strings; never touches sha256 hex or other 26-char-looking content.

Skips:
  - target/ build artifacts
  - node_modules / .next / .yarn caches
  - .git / .claude worktrees
  - _todos.md (scratch personal todos may reference old IDs)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPOS = [
    # Only repos whose ULID examples represent Cokret wire IDs (`ck:<kind>:<id>`).
    # starid/coauth are excluded: they have their own ULID-shaped IDs (did:webvh
    # scid, internal admin tokens) that are NOT Cokret typed UUIDs and would
    # break at parse if blanket-converted.
    "soland",
    "yougen",
    "floria",
    "chime",
    "sodmin",
    "cotest",
    "cokret-rust-sdk",
]
SUFFIXES = (".rs", ".ts", ".tsx", ".js", ".jsx", ".dart", ".swift", ".kt",
            ".md", ".mdx", ".json", ".yaml", ".yml", ".toml", ".html")
SKIP_DIRS = {"target", "node_modules", ".next", ".yarn", ".git", ".claude",
             "build", "dist", "out", ".turbo"}

TYPED_KINDS = (
    "actor_profile|agent_session|applet|backup|batch|blob|block|call|"
    "capability|chunk|claim|device|devmsg|event|filter|flow|frame|frank|grant|"
    "invite|keyevt|message|modq|morph|notif|place|policy|presentation|receipt|"
    "relation|report|req|snapshot|space|txn|view|operation|commit|entity|"
    "version|cell|webrtc|fr|webhook|push|portal|session|registration|fallback"
)
TYPED_ULID_RE = re.compile(
    rf"(ck:(?:{TYPED_KINDS}):)([0-9a-z]{{26}})(?![0-9a-z])"
)
QUOTED_ULID_RE = re.compile(r'(["\'])([0-9a-z]{26})\1')

CROCKFORD = "0123456789abcdefghjkmnpqrstvwxyz"
DECODE = {c: i for i, c in enumerate(CROCKFORD)}


def deterministic_bytes(s: str) -> bytes:
    import hashlib
    s = s.lower()
    if all(c in DECODE for c in s):
        val = 0
        for c in s:
            val = (val << 5) | DECODE[c]
        val &= (1 << 128) - 1
        return val.to_bytes(16, "big")
    return hashlib.sha256(s.encode()).digest()[:16]


def ulid_to_uuid7(ulid_str: str) -> str:
    b = bytearray(deterministic_bytes(ulid_str))
    b[6] = (b[6] & 0x0F) | 0x70
    b[8] = (b[8] & 0x3F) | 0x80
    return (
        f"{b[0]:02x}{b[1]:02x}{b[2]:02x}{b[3]:02x}-"
        f"{b[4]:02x}{b[5]:02x}-"
        f"{b[6]:02x}{b[7]:02x}-"
        f"{b[8]:02x}{b[9]:02x}-"
        f"{b[10]:02x}{b[11]:02x}{b[12]:02x}{b[13]:02x}{b[14]:02x}{b[15]:02x}"
    )


def walk_files(root: Path):
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.suffix not in SUFFIXES:
            continue
        if p.name == "_todos.md":
            continue
        yield p


def collect_ulids(repos: list[Path]) -> dict[str, str]:
    """Only collect ULIDs that appear after a known ck:<kind>: typed prefix.
    Bare quoted ULIDs (e.g. inside `Ulid::from_string("...")` arguments,
    raw fixture digests, content-hash bytes) are intentionally NOT collected
    because they may be non-Cokret internal IDs that would break if
    converted to UUID format.
    """
    mapping: dict[str, str] = {}
    for repo in repos:
        if not repo.exists():
            continue
        for path in walk_files(repo):
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for m in TYPED_ULID_RE.finditer(text):
                s = m.group(2)
                mapping.setdefault(s, ulid_to_uuid7(s))
    return mapping


def rewrite_text(text: str, ulid_map: dict[str, str]) -> str:
    """Replace only typed `ck:<kind>:<ulid>` references. Bare quoted ULIDs
    are not touched."""
    def _typed_sub(m: re.Match) -> str:
        prefix, ulid = m.group(1), m.group(2)
        return prefix + ulid_map.get(ulid, ulid)
    return TYPED_ULID_RE.sub(_typed_sub, text)


def main() -> int:
    repo_paths = [ROOT / r for r in REPOS]
    print("Phase 1: collect unique ULID examples ...")
    ulid_map = collect_ulids(repo_paths)
    print(f"  found {len(ulid_map)} unique ULID examples")

    print("Phase 2: rewrite files ...")
    file_count = 0
    for repo in repo_paths:
        if not repo.exists():
            print(f"  skip missing: {repo}")
            continue
        repo_changed = 0
        for path in walk_files(repo):
            try:
                old = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            new = rewrite_text(old, ulid_map)
            if new != old:
                path.write_text(new, encoding="utf-8")
                repo_changed += 1
        if repo_changed:
            print(f"  {repo.name}: {repo_changed} files")
        file_count += repo_changed
    print()
    print(f"done: {file_count} files rewritten")
    return 0


if __name__ == "__main__":
    sys.exit(main())
