#!/usr/bin/env python3
"""One-shot migration: replace all ULID (Crockford 26-char) usage with UUIDv7
(36-char hex with dashes, version=7, variant RFC 4122) across the entire spec.

Scope:
  - JSON schemas: rewrite regex patterns `[0-9a-hjkmnp-z]{26}` → UUIDv7 pattern.
  - Fixtures: rewrite all ULID-shaped example IDs to deterministic UUIDv7.
  - Markdown / OpenAPI / bindings: rewrite ULID example IDs to UUIDv7.
  - id-kind-registry storage_rules text: drop Crockford / ULID wording.
  - lint_artifacts.py: update ULID_RE constant.

Run once with `python tools/migrations/migrate_ulid_to_uuid7.py` from repo root.
After it finishes, run `python tools/artifact_pipeline.py generate` then
`python tools/artifact_pipeline.py check` to verify.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "spec" / "v1"

# ---- patterns -----------------------------------------------------------

ULID_RAW_RE      = re.compile(r"\[0-9a-hjkmnp-z\]\{26\}")
# Typed-prefix-anchored ULID: only match 26-char Crockford strings preceded by
# a known ck:<kind>: typed prefix from id-kind-registry, so we don't touch
# unrelated 26-char alphanumerics (hashes, hex strings, etc.).
TYPED_KINDS = (
    "actor_profile|agent_session|applet|backup|batch|blob|block|call|"
    "capability|chunk|claim|device|devmsg|event|filter|flow|frame|frank|grant|"
    "invite|keyevt|message|modq|morph|notif|place|policy|presentation|receipt|"
    "relation|report|req|snapshot|space|txn|view"
)
TYPED_ULID_RE    = re.compile(
    rf"(ck:(?:{TYPED_KINDS}):)([0-9a-z]{{26}})(?![0-9a-z])"
)
# Standalone bare ULID in a quoted JSON value (string starts immediately):
QUOTED_ULID_RE   = re.compile(r'(["\'])([0-9a-z]{26})\1')
UUID7_PATTERN    = "[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"

CROCKFORD = "0123456789abcdefghjkmnpqrstvwxyz"
DECODE = {c: i for i, c in enumerate(CROCKFORD)}

# ---- helpers ------------------------------------------------------------

def deterministic_bytes(s: str) -> bytes:
    """Return 16 stable bytes for a ULID-shaped example string.

    Strict Crockford strings (no i/l/o/u) are decoded directly to preserve
    the 48-bit timestamp prefix and lexicographic order. Strings that contain
    excluded letters (i/l/o/u) — historically seen in fixtures because the
    spec regex was permissive — fall back to sha256(s)[:16] so they still get
    a stable, distinct mapping.
    """
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
    """Deterministic ULID-shape → UUIDv7. Forces version=7 in byte 6 high
    nibble and variant=10b in byte 8 high two bits."""
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


def find_all_ulids() -> dict[str, str]:
    """Walk all spec files; return {ulid_str: uuid7_str} for every unique
    ULID-shaped 26-char Crockford string that appears either after a known
    ck:<kind>: typed prefix or inside a quoted JSON string."""
    mapping: dict[str, str] = {}
    targets = []
    for ext in ("*.json", "*.md", "*.mdx", "*.yaml", "*.yml"):
        targets.extend(SPEC.rglob(ext))
    for path in targets:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for m in TYPED_ULID_RE.finditer(text):
            s = m.group(2)
            mapping.setdefault(s, ulid_to_uuid7(s))
        for m in QUOTED_ULID_RE.finditer(text):
            s = m.group(2)
            mapping.setdefault(s, ulid_to_uuid7(s))
    return mapping


# ---- transformations ----------------------------------------------------

def rewrite_text(text: str, ulid_map: dict[str, str]) -> str:
    # 1) regex pattern in schemas
    text = ULID_RAW_RE.sub(UUID7_PATTERN, text)

    # 2) typed-prefix-anchored ULID: ck:KIND:<26-char> → ck:KIND:<uuid7>
    def _typed_sub(m: re.Match) -> str:
        prefix, ulid = m.group(1), m.group(2)
        return prefix + ulid_map.get(ulid, ulid)

    text = TYPED_ULID_RE.sub(_typed_sub, text)

    # 3) bare ULID inside a quoted JSON string: "<26-char>" → "<uuid7>"
    def _quoted_sub(m: re.Match) -> str:
        q, ulid = m.group(1), m.group(2)
        return q + ulid_map.get(ulid, ulid) + q

    text = QUOTED_ULID_RE.sub(_quoted_sub, text)
    return text


def rewrite_id_kind_storage_rules(catalog_path: Path) -> None:
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    section = data.get("id_kind_registry")
    if not isinstance(section, dict):
        return
    section["uuid_pattern"] = f"^{UUID7_PATTERN}$"
    section["typed_uuid_pattern"] = f"^ck:<kind>:{UUID7_PATTERN}$"
    section.pop("ulid_pattern", None)
    section.pop("typed_ulid_pattern", None)
    new_rules = [
        "Protocol wire objects, canonical JSON, signatures, hashes, fixtures, logs, API DTOs, and cross-service references MUST use the full typed form ck:<kind>:<uuid> unless a special form below applies.",
        "Storage implementations MAY store raw 16-byte UUID values (e.g. PostgreSQL `uuid` column) without the ck:<kind>: prefix when the table, column, or explicit kind field already supplies the type context.",
        "Implementations that store raw IDs MUST restore the full typed form before computing canonical JSON, event IDs, payload hashes, detached proofs, federation payloads, sync cursors, or audit logs.",
        "The <kind> segment is part of the signed/canonical wire value. It MUST NOT be changed, inferred differently, or stripped during verification, forwarding, backfill, or replay.",
        "The UUID segment MUST be RFC 9562 UUID version 7 (48-bit Unix-millisecond timestamp + 4-bit version=7 + 12-bit rand_a + 2-bit variant=10b + 62-bit rand_b), serialized as the canonical 36-character lowercase hex form `xxxxxxxx-xxxx-7xxx-Nxxx-xxxxxxxxxxxx` where N ∈ {8,9,a,b}.",
    ]
    section["storage_rules"] = new_rules
    catalog_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def rewrite_lint(lint_path: Path) -> None:
    text = lint_path.read_text(encoding="utf-8")
    text = re.sub(
        r'ULID_RE\s*=\s*re\.compile\(r"\^\[0-9a-hjkmnp-z\]\{26\}\$"\)',
        f'UUID7_RE = re.compile(r"^{UUID7_PATTERN}$")',
        text,
    )
    text = text.replace("ULID_RE", "UUID7_RE")
    text = text.replace("typed ULID", "typed UUIDv7")
    text = text.replace("rest[:26]", "rest[:36]")
    lint_path.write_text(text, encoding="utf-8")


# ---- main ---------------------------------------------------------------

def main() -> int:
    print("Phase 1: scan for ULID-shaped example strings ...")
    ulid_map = find_all_ulids()
    print(f"  found {len(ulid_map)} unique ULID examples")

    print("Phase 2: rewrite all .json/.md/.mdx/.yaml/.yml files ...")
    targets: list[Path] = []
    for ext in ("*.json", "*.md", "*.mdx", "*.yaml", "*.yml"):
        targets.extend(SPEC.rglob(ext))
    changed = 0
    for path in sorted(set(targets)):
        try:
            old = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        new = rewrite_text(old, ulid_map)
        if new != old:
            path.write_text(new, encoding="utf-8")
            changed += 1
    print(f"  rewrote {changed} files")

    print("Phase 3: rewrite contract-catalog id_kind_registry storage_rules ...")
    rewrite_id_kind_storage_rules(SPEC / "artifacts" / "registry" / "contract-catalog.json")

    print("Phase 4: rewrite tools/lint_artifacts.py ULID_RE ...")
    rewrite_lint(ROOT / "tools" / "lint_artifacts.py")

    print("Done. Next: python tools/artifact_pipeline.py generate && check")
    return 0


if __name__ == "__main__":
    sys.exit(main())
