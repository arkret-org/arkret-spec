#!/usr/bin/env python3
"""Convert ULID-typed TEXT columns to PostgreSQL UUID across soland / starid /
coauth migrations. coauth is already UUID-native; this script only verifies it
and reports.

Backward compat is intentionally NOT preserved: the user has accepted the
spec-level switch from ULID-as-Crockford to UUIDv7-as-uuid, so storage
columns flip from `TEXT` to `UUID` directly. ALTER COLUMN with USING cast is
not emitted because the user said "不管兼容性，直接改 sql"; we just rewrite the
original CREATE TABLE statements.

Column classification rule:
  - ULID-typed Cokret wire IDs (per id-kind-registry.json) → UUID
  - Soland-internal opaque IDs that store UUID-shape values → UUID
  - DIDs, handles, hashes, JWTs, public keys, status enums, action names,
    polymorphic refs → STAY TEXT
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGETS = [
    # soland is the only Cokret wire participant. starid uses multihash scid
    # (z<base58(sha256)>) for receipt_id and is NOT migrated. coauth's
    # device_id is an opaque OAuth scope-derived client string and is also
    # NOT migrated; coauth's other tables are already UUID-native.
    ROOT / "soland" / "migrations",
]

# Columns that store Cokret typed UUIDv7 values (per id-kind-registry):
UUID_COLUMNS_COKRET = {
    # core wire IDs
    "event_id", "realm_id", "space_id", "flow_id", "morph_id", "view_id",
    "relation_id", "from_entity_id", "to_entity_id",
    "message_id", "actor_profile_id",
    # receipts / snapshots
    "receipt_id", "snapshot_id",
    # identity / device
    "device_id", "backup_id",
    # capability / authz
    "grant_id", "capability_id", "policy_id", "decision_id",
    # invite / moderation
    "invite_id", "report_id", "modq_id", "action_id",
    # transport / sync
    "request_id",
    # notification
    "notification_id",
    # extension
    "applet_id", "agent_session_id", "call_id",
    # frame / devmsg
    "frame_id", "devmsg_id",
}

# Soland-internal opaque IDs that are UUID-shape but not in the Cokret
# id-kind-registry namespace. These are server-internal but the user wants
# them stored as native UUID for the same performance reasons.
UUID_COLUMNS_SOLAND_INTERNAL = {
    # Versioned-entity model
    "entity_id", "version_id", "current_version",
    # Threading (event roots)
    "thread_id",
    # Soland-internal generators
    "fallback_key_id", "package_id", "portal_id", "session_id",
    "registration_id", "operation_id",
}

UUID_COLUMNS = UUID_COLUMNS_COKRET | UUID_COLUMNS_SOLAND_INTERNAL

# Pattern: column declaration line where TEXT appears as the type.
# Examples it must match:
#   "    event_id TEXT PRIMARY KEY,"
#   "    space_id TEXT NOT NULL,"
#   "    receipt_id TEXT NOT NULL REFERENCES identity_documents(did) ..."
#   "    device_id TEXT NOT NULL,"
COLUMN_DECL_RE = re.compile(
    r"(?P<indent>^[ \t]+)(?P<col>[a-z_][a-z0-9_]*)\s+TEXT(?P<rest>(?:\s+[A-Z][^,\n]*)?(?:,)?\s*$)",
    re.MULTILINE,
)


def rewrite_sql(text: str, path: Path) -> tuple[str, list[str]]:
    changes: list[str] = []

    def _sub(m: re.Match) -> str:
        col = m.group("col")
        if col in UUID_COLUMNS:
            changes.append(col)
            return f"{m.group('indent')}{col} UUID{m.group('rest')}"
        return m.group(0)

    new = COLUMN_DECL_RE.sub(_sub, text)
    return new, changes


def main() -> int:
    total_changes = 0
    files_touched = 0
    for base in TARGETS:
        if not base.exists():
            print(f"skip missing: {base}")
            continue
        for sql_path in sorted(base.rglob("*.sql")):
            text = sql_path.read_text(encoding="utf-8")
            new, changes = rewrite_sql(text, sql_path)
            if new != text:
                sql_path.write_text(new, encoding="utf-8")
                files_touched += 1
                total_changes += len(changes)
                rel = sql_path.relative_to(ROOT)
                print(f"  {rel}: {len(changes)} cols ({', '.join(sorted(set(changes)))})")
    print()
    print(f"done: {files_touched} files, {total_changes} column conversions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
