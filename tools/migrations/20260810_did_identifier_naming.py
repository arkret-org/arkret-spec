#!/usr/bin/env python3
"""Apply decision 0021's one-shot DID identifier naming migration.

The source artifacts intentionally retain their existing ordering and layout.
Every replacement below is exact or boundary-aware, making the migration
idempotent and preventing ``did`` from matching ``did_url``/``did_core_id``.
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "spec" / "v1"
SCHEMAS = SPEC / "artifacts" / "schemas"

ROOT_BARE_DID_PROPERTY_SCHEMAS = {
    "did-webvh-witness-receipt.schema.json",
    "identity-receipt.schema.json",
}

TEXT_EXTENSIONS = {".json", ".md", ".mdx", ".yaml", ".yml"}

CORE_WIRE_RENAMES = {
    "verifier_did": "verifier_service_id",
    "operator_did": "operator_principal_id",
    "holder_did": "holder_principal_id",
    "peer_did": "peer_principal_id",
    "organization_did": "organization_principal_id",
    "expected_did": "expected_principal_id",
    "expected_agent_did": "expected_actor_id",
    "subscriber_did": "subscriber_principal_id",
    "push_gateway_did": "push_gateway_service_id",
    "requester_did": "requester_actor_id",
    "policy_server_did": "policy_server_service_id",
    "reviewer_did": "reviewer_actor_id",
    "applicant_did": "applicant_actor_id",
    "principal_server_did": "principal_server_service_id",
    "appellant_did": "appellant_actor_id",
    "allowed_principal_dids": "allowed_principal_ids",
    "denied_principal_dids": "denied_principal_ids",
}

COMMON_DID_ALIAS = '''    "did": {
      "$ref": "#/$defs/full_id",
      "description": "Compatibility schema name for the canonical FullId wire type. New normative text distinguishes full_id from core_id; this alias does not permit a core_id where a standard bare DID is required."
    },
'''


def write_if_changed(path: Path, text: str, updated: str) -> None:
    if updated != text:
        path.write_text(updated, encoding="utf-8", newline="\n")


def migrate_schema(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    updated = text

    if path.name == "common-ids.schema.json":
        updated = updated.replace(COMMON_DID_ALIAS, "")

    # Root $defs entries are indented by exactly four spaces. Wire properties
    # nested in object schemas are deeper and therefore remain untouched.
    updated = re.sub(r'(?m)^    "full_id"(?=\s*:)', '    "did_full_id"', updated)
    updated = updated.replace('#/$defs/full_id"', '#/$defs/did_full_id"')
    updated = updated.replace('/$defs/full_id"', '/$defs/did_full_id"')

    if path.name not in {"common-ids.schema.json", *ROOT_BARE_DID_PROPERTY_SCHEMAS}:
        local_did_name = (
            "did_full_id" if path.name == "did-binding-contracts.schema.json" else "did_core_id"
        )
        updated = re.sub(r'(?m)^    "did"(?=\s*:)', f'    "{local_did_name}"', updated)
        updated = updated.replace('#/$defs/did"', f'#/$defs/{local_did_name}"')

    # The only remaining cross-file use of the deleted common alias is the DID
    # log response, whose wire field remains the genuine bare-DID name ``did``.
    updated = updated.replace('/$defs/did"', '/$defs/did_full_id"')
    write_if_changed(path, text, updated)


def migrate_text_tokens() -> None:
    paths = [
        path
        for path in sorted(SPEC.rglob("*"))
        if path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS
    ]
    paths.append(ROOT / "tools" / "artifact_lint" / "schemas.py")
    for path in paths:
        text = path.read_text(encoding="utf-8")
        updated = re.sub(r"(?<!did_)\bcore_id\b", "did_core_id", text)
        updated = re.sub(r"(?<!Did)\bCoreId\b", "DidCoreId", updated)
        updated = re.sub(r"(?<!Did)\bFullId\b", "DidFullId", updated)
        for old, new in CORE_WIRE_RENAMES.items():
            updated = updated.replace(old, new)
            updated = re.sub(rf"\b{re.escape(new)}: did\b", f"{new}: did_core_id", updated)
        if path.suffix.lower() in {".md", ".mdx"}:
            updated = updated.replace("auth_context.did", "auth_context.actor_id")
            updated = updated.replace("notary.did", "notary.actor_id")
            updated = re.sub(
                r'"did": "(ak:did_core:[^"]+)"',
                r'"actor_id": "\1"',
                updated,
            )
        write_if_changed(path, text, updated)


def migrate_fixture_contexts() -> None:
    for name in (
        "cba-lattice-fixture.json",
        "crypto-signature-fixture.json",
        "encoding-fixture.json",
    ):
        path = SPEC / "artifacts" / "fixtures" / name
        text = path.read_text(encoding="utf-8")
        updated = re.sub(
            r'"did": "did:webvh:([^":]+)(?::[^"]*)?"',
            r'"actor_id": "ak:did_core:webvh:\1"',
            text,
        )
        write_if_changed(path, text, updated)

    path = SPEC / "artifacts" / "fixtures" / "schema-validation-fixture.json"
    text = path.read_text(encoding="utf-8")
    updated = re.sub(
        r'"did": "(ak:did_core:[^"]+)"',
        r'"actor_id": "\1"',
        text,
    )
    write_if_changed(path, text, updated)

    path = SPEC / "artifacts" / "fixtures" / "key-transparency-fixture.json"
    text = path.read_text(encoding="utf-8")
    updated = text.replace('"witness_did": "ak:did_core:', '"witness_service_id": "ak:did_core:')
    write_if_changed(path, text, updated)

    path = SPEC / "artifacts" / "fixtures" / "websocket-binding-fixture.json"
    text = path.read_text(encoding="utf-8")
    updated = text.replace(
        '\\"auth_context\\":{\\"did\\":\\"ak:did_core:',
        '\\"auth_context\\":{\\"actor_id\\":\\"ak:did_core:',
    )
    write_if_changed(path, text, updated)


def main() -> None:
    for path in sorted(SCHEMAS.glob("*.json")):
        migrate_schema(path)
    migrate_text_tokens()
    migrate_fixture_contexts()


if __name__ == "__main__":
    main()
