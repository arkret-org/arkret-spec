"""Generate real signature bytes for the active Reaction reference fixture."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.regenerate_crypto_signature_fixture import refresh_jws_input
from tools.regenerate_detached_object_signature_kat import (
    KEY_A_SEED, KEY_B_SEED, OLD_VM, b64u, jcs, make_signature, public_key,
)

DEST = ROOT / "spec/v1/artifacts/fixtures/reaction-authority-order-fixture.json"
VECTOR = "ak.vector.reaction.authority_order_current.v1"
ACTOR = {"kind": "account", "account_id": {
    "principal_id": "ak:did_core:web:alice.example", "station_id": "ak:did_core:web:station.example"}}
OTHER = copy.deepcopy(ACTOR)
OTHER["account_id"]["station_id"] = "ak:did_core:web:other-station.example"
DEVICE = "ak:device:01964137-0000-7000-8000-000000000001"
VM = "did:web:alice.example#" + DEVICE
T = "2026-11-14T00:00:00.000Z"


def typed_id(kind, value):
    return "ak:" + kind + ":" + b64u(b"\x01" + hashlib.sha256(jcs(value)).digest())


REALM = typed_id("realm", {"fixture": "reaction_current"})
TARGET = typed_id("message", {"fixture": "accepted_target"})
STREAM = {"kind": "realm", "realm_id": REALM}
ANCHOR = typed_id("realm_commit", {"fixture": "verified_prefix_0"})


def event(actor, action, position):
    created_at = (datetime.fromisoformat(T.replace("Z", "+00:00")) + timedelta(milliseconds=position)).isoformat(
        timespec="milliseconds").replace("+00:00", "Z")
    body = {"kind": "ak.reaction." + action, "realm_id": REALM, "scope_ref": STREAM,
            "actor_id": actor, "created_at": created_at, "payload": {"target_ref": TARGET, "key": "👍"}}
    digest = "sha256:" + hashlib.sha256(jcs(body)).hexdigest()
    binding = {"context": "ak.event_proof.v1", "event_digest": digest, "actor_id": actor,
               "verification_method": VM, "created_at": created_at}
    signing_input = refresh_jws_input({"protected_header": {"alg": "Ed25519"}}, jcs(binding))
    jws = signing_input.decode().split(".")[0] + ".." + b64u(
        Ed25519PrivateKey.from_private_bytes(KEY_B_SEED).sign(signing_input))
    return {"event_id": typed_id("event", body), **body, "producer_proof": {
        "kind": "detached_jws", "verification_method": VM, "event_digest": digest,
        "created_at": created_at, "jws": jws}}


def source(row):
    commit = row["commit"]
    return {"event_id": row["event"]["event_id"], "commit_id": commit["commit_id"],
            "stream_ref": copy.deepcopy(commit["stream_ref"]), "stream_position": commit["stream_position"]}


def revision(commit):
    return {"commit_id": commit["commit_id"], "stream_position": commit["stream_position"]}


def apply(entries, row):
    actor, key = row["event"]["actor_id"], row["event"]["payload"]["key"]
    result = [copy.deepcopy(entry) for entry in entries
              if (jcs(entry["actor_id"]), entry["key"]) != (jcs(actor), key)]
    if row["event"]["kind"] == "ak.reaction.add":
        result.append({"actor_id": copy.deepcopy(actor), "key": key, "source": source(row)})
    return sorted(result, key=lambda entry: (jcs(entry["actor_id"]), entry["key"].encode("utf-8")))


def sign_snapshot(value):
    unsigned = {key: item for key, item in value.items() if key not in {"snapshot_id", "signature"}}
    snapshot = {"snapshot_id": typed_id("realm_snapshot", unsigned), **unsigned}
    snapshot["signature"], _ = make_signature("ak.realm_snapshot_signature.v1", snapshot, OLD_VM, KEY_A_SEED)
    return snapshot


def build_fixture():
    rows, checkpoints, entries = [], [], []
    previous = ANCHOR
    actions = [(ACTOR, "add"), (ACTOR, "remove"), (ACTOR, "add"),
               (OTHER, "add"), (ACTOR, "remove"), (OTHER, "remove")]
    for position, (actor, action) in enumerate(actions, 1):
        ev = event(actor, action, position)
        core = {"realm_id": REALM, "stream_ref": STREAM, "stream_position": position,
                "previous_commit_ref": previous, "event_ref": ev["event_id"], "governance_generation": "0",
                "authority_ref": typed_id("event", {"fixture": "accepted_realm_genesis"}),
                "committed_at": ev["created_at"]}
        commit = {"commit_id": typed_id("realm_commit", core), **core}
        commit["signature"], _ = make_signature("ak.realm_commit_signature.v1", commit, OLD_VM, KEY_A_SEED)
        row = {"event": ev, "commit": commit}
        rows.append(row)
        entries = apply(entries, row)
        current = {"selector": {"kind": "message_reactions", "target_ref": TARGET},
                   "source_stream_ref": STREAM, "revision": revision(commit),
                   "value": {"entries": copy.deepcopy(entries)}}
        checkpoints.append(sign_snapshot({
            "realm_id": REALM, "governance_generation": "0", "purpose": "full_recovery",
            "visible_stream_heads": [{"stream_ref": STREAM, **revision(commit)}],
            "current_state_entries": [current],
            "retention_and_history_floor": {"history_access": "since_join", "stream_floors": [
                {"stream_ref": STREAM, "oldest_position": min(4, position)}]}, "created_at": ev["created_at"]}))
        previous = commit["commit_id"]
    cases = [
        ("complete_ordered_tail", "accept"), ("remove_keeps_empty_row", "accept"),
        ("snapshot_then_tail", "accept"), ("old_add_after_empty_cut", "ignore"),
        ("gap_before_remove", "buffer"), ("same_position_equivocation", "reject"),
        ("producer_signature_tampered", "reject"), ("commit_signature_tampered", "reject"),
        ("snapshot_value_tampered", "reject"), ("duplicate_actor_key", "reject"),
        ("source_from_other_stream", "reject"), ("source_after_row_revision", "reject"),
        ("partial_snapshot_not_installed", "reject"), ("history_scan_read_only", "accept"),
        ("same_principal_other_station", "accept"), ("no_tombstone_or_payload_in_current", "accept"),
        ("floor_does_not_require_old_event", "accept"), ("nested_source_is_not_read_permission", "accept"),
    ]
    return {"profile": "ak.profile.chat_mvp.v1", "runner": {"kind": "named_suite", "entrypoint": "ak.suite.reaction.authority_order.v1"},
            "covers_vectors": [VECTOR], "generated_by": "tools/generate_reaction_current_fixture.py",
            "description": "Executable active-only Reaction current with actual Ed25519 producer/Commit/Snapshot signatures. Native DID authority, target existence and business authorization are independently validated inputs, not proven by fixture keys. Historical scans are read-only and no old Event is required to consume Snapshot metadata.",
            "test_keys": {"producer_public_key_b64u": public_key(KEY_B_SEED), "governance_public_key_b64u": public_key(KEY_A_SEED)},
            "trusted_basis": {"stream_ref": STREAM, "target_ref": TARGET, "position": 0, "commit_id": ANCHOR},
            "original_rows": rows, "checkpoints": checkpoints,
            "cases": [{"name": name, "expected": expected} for name, expected in cases]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = json.dumps(build_fixture(), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if DEST.read_text(encoding="utf-8") != expected:
            raise SystemExit("Reaction fixture differs from deterministic output")
    else:
        DEST.write_text(expected, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
