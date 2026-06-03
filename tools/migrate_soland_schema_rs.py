#!/usr/bin/env python3
"""Update soland/src/schema.rs to switch UUID-typed column declarations from
`Text` / `Nullable<Text>` to `Uuid` / `Nullable<Uuid>`.

Driven by the same column whitelist used in migrate_sql_text_to_uuid.py.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_RS = ROOT / "soland" / "src" / "schema.rs"

UUID_COLUMNS_COKRET = {
    "event_id", "realm_id", "space_id", "flow_id", "morph_id", "view_id",
    "relation_id", "from_entity_id", "to_entity_id",
    "message_id", "actor_profile_id",
    "receipt_id", "snapshot_id",
    "device_id", "backup_id",
    "grant_id", "capability_id", "policy_id", "decision_id",
    "invite_id", "report_id", "modq_id", "action_id",
    "request_id",
    "notification_id",
    "applet_id", "agent_session_id", "call_id",
    "frame_id", "devmsg_id",
}
UUID_COLUMNS_SOLAND_INTERNAL = {
    "entity_id", "version_id", "current_version",
    "thread_id",
    "fallback_key_id", "package_id", "portal_id", "session_id",
    "registration_id", "operation_id",
}
UUID_COLUMNS = UUID_COLUMNS_COKRET | UUID_COLUMNS_SOLAND_INTERNAL

# Column declaration in diesel table! macro:
#   "        event_id -> Text,"
#   "        head_commit -> Nullable<Text>,"
LINE_RE = re.compile(
    r"^(?P<indent>\s+)(?P<col>[a-z_][a-z0-9_]*)\s*->\s*(?P<wrap>Nullable<)?Text(?P<close>>)?,\s*$"
)


def main() -> int:
    text = SCHEMA_RS.read_text(encoding="utf-8")
    new_lines = []
    changes = 0
    for line in text.splitlines(keepends=True):
        m = LINE_RE.match(line)
        if m and m.group("col") in UUID_COLUMNS:
            wrap = m.group("wrap") or ""
            close = m.group("close") or ""
            new_line = f"{m.group('indent')}{m.group('col')} -> {wrap}Uuid{close},\n"
            new_lines.append(new_line)
            changes += 1
        else:
            new_lines.append(line)
    SCHEMA_RS.write_text("".join(new_lines), encoding="utf-8")
    print(f"updated {changes} column declarations in {SCHEMA_RS.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
