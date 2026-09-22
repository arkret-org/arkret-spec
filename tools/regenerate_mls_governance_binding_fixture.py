#!/usr/bin/env python3
"""Regenerate the MLS governance-binding byte and admission closure fixture."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "spec/v1/artifacts/fixtures"
OUTPUT = FIXTURES / "mls-governance-binding-closure-fixture.json"
FINAL_CLOSURE = FIXTURES / "final-conformance-closure-fixture.json"
VECTOR_ID = "ak.vector.mls.governance_binding_closure.v1"
EPOCH_VECTOR_ID = "ak.vector.mls.governance_epoch_binding.v1"
UINT64_MAX = (1 << 64) - 1

REALM_ID = "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5"
OTHER_REALM_ID = "ak:realm:ATh7OWLLpUdTVYsKdp6rkClScUpjYJlF1Y3byjeyHS8J"
CIRCLE_ID = "ak:circle:AcQajqaKFvyDoMpqpSlBvMh0d4gheZsVPhbHaTlqXtkV"
SIDECAR_ID = "ak:sidecar:AZUfzdx1qBOtCsg2CGmS3QLP7vlDe_kxRx0pxdxefWTa"
BASE_REF = "ak:event:AZk4PXzJ6MpkxXnYTUmgXzeIYNd0Wfnz3N0hwLHNV6Xq"
OTHER_BASE_REF = "ak:event:AbhX3-n_FG8scl_4zkFai8VRhqvIwjOeWHvA8D3mQ9V7"


def _head(major: int, value: int) -> bytes:
    if value < 24:
        return bytes([(major << 5) | value])
    if value <= 0xFF:
        return bytes([(major << 5) | 24, value])
    if value <= 0xFFFF:
        return bytes([(major << 5) | 25]) + value.to_bytes(2, "big")
    if value <= 0xFFFFFFFF:
        return bytes([(major << 5) | 26]) + value.to_bytes(4, "big")
    if value <= UINT64_MAX:
        return bytes([(major << 5) | 27]) + value.to_bytes(8, "big")
    raise ValueError("deterministic CBOR v1 admits only unsigned 64-bit integers")


def encode(value: Any) -> bytes:
    if value is None:
        return b"\xf6"
    if isinstance(value, bool):
        raise TypeError("booleans are outside MlsGroupBinding")
    if isinstance(value, int):
        if value < 0:
            raise ValueError("MlsGroupBinding integers are unsigned")
        return _head(0, value)
    if isinstance(value, str):
        raw = value.encode("utf-8")
        return _head(3, len(raw)) + raw
    if isinstance(value, dict):
        pairs = sorted((encode(key), encode(item)) for key, item in value.items())
        return _head(5, len(pairs)) + b"".join(key + item for key, item in pairs)
    raise TypeError(f"unsupported MlsGroupBinding value: {type(value).__name__}")


def realm_scope() -> dict[str, str]:
    return {"kind": "realm", "realm_id": REALM_ID}


def circle_scope() -> dict[str, str]:
    return {"kind": "circle", "realm_id": REALM_ID, "circle_id": CIRCLE_ID}


def sidecar_scope() -> dict[str, str]:
    return {"kind": "sidecar", "realm_id": REALM_ID, "sidecar_id": SIDECAR_ID}


def binding(scope: dict[str, str], *, base: str | None = BASE_REF,
            previous: int = 41, next_: int = 42, revision: int = 17) -> dict[str, Any]:
    return {
        "effective_scope": scope,
        "base_group_state_ref": base,
        "previous_epoch": previous,
        "next_epoch": next_,
        "key_access_revision": revision,
    }


def accepted(name: str, value: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "binding": value,
        "encoded_map_hex": encode(value).hex(),
        "expected": {"decision": "accept"},
    }


def rejected(name: str, violation: str, raw: bytes) -> dict[str, Any]:
    return {
        "name": name,
        "violation": violation,
        "encoded_map_hex": raw.hex(),
        "expected": {"decision": "reject", "reason": "schema_violation"},
    }


def map_with_raw_value(value: dict[str, Any], member: str, raw_value: bytes) -> bytes:
    pairs = []
    for key, item in value.items():
        encoded_key = encode(key)
        encoded_value = raw_value if key == member else encode(item)
        pairs.append((encoded_key, encoded_value))
    pairs.sort(key=lambda pair: pair[0])
    return _head(5, len(pairs)) + b"".join(key + item for key, item in pairs)


def build_fixture() -> dict[str, Any]:
    realm = binding(realm_scope())
    circle = binding(circle_scope())
    sidecar = binding(sidecar_scope())
    genesis = binding(realm_scope(), base=None, previous=0, next_=0, revision=0)

    unknown = dict(realm)
    unknown["sender_index"] = 3
    missing = dict(realm)
    del missing["key_access_revision"]
    keys = sorted((encode(key), key) for key in realm)
    canonical_pairs = [(raw_key, encode(realm[key])) for raw_key, key in keys]
    duplicate = _head(5, 6) + canonical_pairs[0][0] + canonical_pairs[0][1] + b"".join(
        key + item for key, item in canonical_pairs
    )
    out_of_order = _head(5, 5) + b"".join(
        encode(key) + encode(value) for key, value in realm.items()
    )
    indefinite = b"\xbf" + b"".join(key + item for key, item in canonical_pairs) + b"\xff"
    non_minimal = map_with_raw_value(realm, "previous_epoch", b"\x19\x00\x29")
    overflow = map_with_raw_value(
        realm,
        "key_access_revision",
        b"\xc2\x49\x01\x00\x00\x00\x00\x00\x00\x00\x00",
    )

    carrier = {
        "event_kind": "ak.mls.genesis",
        "proposal_kind": "group_genesis_binding",
        "sender_actor_id": {
            "kind": "service",
            "service_id": "ak:did_core:web:creator.example",
        },
        "target_scope": realm_scope(),
        "proposed_group_genesis_binding": genesis,
    }

    cases = [
        {
            "name": "governance_binding_wire_encoding_is_closed",
            "assertions": [
                "binding_is_exactly_the_five_registered_members",
                "map_keys_follow_rfc8949_bytewise_deterministic_order",
                "key_access_revision_is_an_unsigned_64_bit_monotonic_integer",
                "non_deterministic_or_out_of_bounds_input_is_rejected_without_normalisation",
            ],
            "canonical_member_order": [key for _, key in keys],
            "member_order_rule": "RFC 8949 section 4.2.1 bytewise lexicographic order of deterministic key encodings.",
            "resource_limits": {
                "maximum_input_bytes": 16384,
                "maximum_nesting_depth": 8,
                "maximum_collection_items": 64,
            },
            "accepted": [
                accepted("realm_scope_commit", realm),
                accepted("circle_scope_commit", circle),
                accepted("sidecar_scope_commit", sidecar),
                accepted("realm_scope_genesis", genesis),
            ],
            "rejection_samples": [
                rejected("unknown_member", "sixth member outside the closed five", encode(unknown)),
                rejected("missing_member", "key_access_revision absent", encode(missing)),
                rejected("indefinite_length_map", "indefinite-length map", indefinite),
                rejected("non_minimal_integer", "previous_epoch uses a wider-than-minimal head", non_minimal),
                rejected("duplicate_map_key", "next_epoch appears twice", duplicate),
                rejected("out_of_order_map_key", "schema declaration order is not CBOR deterministic order", out_of_order),
                rejected("trailing_bytes", "one complete map is followed by an extra item", encode(realm) + b"\x00"),
                rejected("unsupported_major_type", "top-level array is not the binding map", b"\x80"),
                rejected("non_text_map_key", "map key is an unsigned integer", b"\xa1\x00\x00"),
                rejected("unsigned_integer_overflow", "2^64 is encoded as a bignum tag outside the uint64 contract", overflow),
                rejected("truncated", "declared text length exceeds the remaining input", b"\xa1\x78\x18"),
                rejected("resource_limit_exceeded", "declared map count exceeds the decoder collection limit", b"\xb8\x41"),
            ],
        },
        {
            "name": "governance_binding_epoch_transition_is_fixed",
            "assertions": [
                "genesis_transition_is_exactly_zero_to_zero",
                "commit_transition_is_previous_epoch_plus_one",
                "key_access_revision_is_monotonic_and_never_a_digest",
            ],
            "samples": [
                accepted("genesis_zero_to_zero_accept", genesis),
                accepted("commit_increments_by_one_accept", realm),
                {
                    "name": "commit_skips_an_epoch_reject",
                    "covers_decision_points": ["AK-SDK-009/governance_binding_mismatch_stops_the_commit"],
                    "binding": binding(realm_scope(), next_=43),
                    "expected": {"decision": "reject", "reason": "governance_binding_mismatch"},
                },
                {
                    "name": "genesis_with_a_nonzero_transition_reject",
                    "covers_decision_points": ["AK-SDK-009/governance_binding_mismatch_stops_the_commit"],
                    "binding": binding(realm_scope(), base=None, previous=0, next_=1, revision=0),
                    "expected": {"decision": "reject", "reason": "governance_binding_mismatch"},
                },
                {
                    "name": "commit_repeats_the_previous_epoch_reject",
                    "covers_decision_points": ["AK-SDK-009/governance_binding_mismatch_stops_the_commit"],
                    "binding": binding(realm_scope(), next_=41),
                    "expected": {"decision": "reject", "reason": "governance_binding_mismatch"},
                },
                {
                    "name": "revision_rollback_reject",
                    "station_public_state": {"current_key_access_revision": 18},
                    "binding": binding(realm_scope(), revision=17),
                    "expected": {"decision": "reject", "reason": "governance_binding_mismatch"},
                },
            ],
        },
        {
            "name": "binding_matches_public_state_and_payload",
            "assertions": [
                "rfc9420_public_validation_does_not_replace_governance_binding_equality",
                "base_revision_and_payload_extension_equality_are_checked_separately",
            ],
            "rfc9420_public_material": {
                "group_info_signature_valid": True,
                "ratchet_tree_consistent": True,
                "group_id_matches": True,
                "epoch_matches": True,
            },
            "station_public_state": {
                "effective_scope": realm_scope(),
                "base_group_state_ref": BASE_REF,
                "current_key_access_revision": 17,
            },
            "event_payload_binding": realm,
            "samples": [
                {"name": "all_fields_equal_accept", "binding": realm, "expected": {"decision": "accept"}},
                {"name": "base_differs_reject", "binding": binding(realm_scope(), base=OTHER_BASE_REF), "expected": {"decision": "reject", "reason": "governance_binding_mismatch"}},
                {"name": "revision_differs_reject", "binding": binding(realm_scope(), revision=18), "expected": {"decision": "reject", "reason": "governance_binding_mismatch"}},
                {"name": "payload_extension_differs_reject", "binding": binding(realm_scope(), revision=16), "expected": {"decision": "reject", "reason": "governance_binding_mismatch"}},
            ],
        },
        {
            "name": "historical_replay_does_not_grant_current_send_authority",
            "assertions": [
                "historical_material_is_compared_with_its_historical_binding",
                "historical_acceptance_does_not_grant_current_send_authority",
            ],
            "historical_accepted_binding": binding(realm_scope(), revision=17),
            "current_public_state": {"current_key_access_revision": 18},
            "expected": {
                "historical_replay_decision": "accept",
                "current_send_decision": "reject",
                "current_send_reason": "epoch_update_required",
            },
        },
        {
            "name": "pre_genesis_proposal_uses_the_same_binding_schema",
            "assertions": [
                "proposal_carrier_structurally_binds_event_kind_kind_sender_and_target_scope",
                "proposal_carrier_reuses_the_one_mls_governance_binding_schema",
                "missing_required_carrier_member_is_a_schema_violation",
                "mismatched_complete_proposal_leaves_no_proof_or_cache_entry",
            ],
            "carrier_schema_ref": "schemas/event-payload.schema.json#/$defs/mls_genesis_binding_proposal_carrier",
            "binding_schema_ref": "schemas/event-payload.schema.json#/$defs/mls_governance_binding",
            "accepted_carrier": carrier,
            "rejection_samples": [
                {"name": "proposal_binding_member_missing", "carrier": {key: value for key, value in carrier.items() if key != "proposed_group_genesis_binding"}, "expected": {"decision": "reject", "reason": "schema_violation", "proof_emitted": False, "cache_entry_written": False}},
                {"name": "proposal_target_scope_differs", "carrier": {**carrier, "target_scope": {"kind": "realm", "realm_id": OTHER_REALM_ID}}, "expected": {"decision": "reject", "reason": "mls_genesis_binding_proposal_mismatch", "proof_emitted": False, "cache_entry_written": False}},
                {"name": "proposal_event_kind_differs", "carrier": {**carrier, "event_kind": "ak.mls.commit"}, "expected": {"decision": "reject", "reason": "mls_genesis_binding_proposal_mismatch", "proof_emitted": False, "cache_entry_written": False}},
                {"name": "proposal_sender_missing", "carrier": {key: value for key, value in carrier.items() if key != "sender_actor_id"}, "expected": {"decision": "reject", "reason": "schema_violation", "proof_emitted": False, "cache_entry_written": False}},
            ],
        },
    ]

    return {
        "profile": "ak.vector_group.privacy_security.v1",
        "version": "2026-09-22.1",
        "suite": "mls_governance_binding_closure",
        "runner": {"kind": "named_suite", "entrypoint": "ak.suite.mls.governance_binding_closure.v1"},
        "covers_vectors": [VECTOR_ID, EPOCH_VECTOR_ID],
        "security_evidence": [{
            "vector_id": VECTOR_ID,
            "clause_id": "AK-NC-061",
            "decision_points": [
                {"id": "closed_deterministic_cbor_and_bounds", "requirement": "Every received binding is the exact closed deterministic-CBOR map and fails before allocation when a syntax, range or decoder bound is violated.", "evidence": ["/cases/0"]},
                {"id": "all_scope_branches_have_fixed_acceptance_bytes", "requirement": "Realm, Circle, Sidecar and Genesis/null branches each have a positive fixed-byte acceptance KAT.", "evidence": ["/cases/0/accepted/0", "/cases/0/accepted/1", "/cases/0/accepted/2", "/cases/0/accepted/3"]},
                {"id": "epoch_and_revision_are_unsigned_monotonic_counters", "requirement": "Genesis is 0 to 0, Commit increments epoch by one, and key_access_revision is a monotonic unsigned 64-bit counter rather than a digest.", "evidence": ["/cases/1"]},
                {"id": "valid_public_material_still_requires_exact_binding_equality", "requirement": "RFC 9420-valid public material is rejected when its internal binding differs from Station state or the Event payload.", "evidence": ["/cases/2"]},
                {"id": "historical_replay_is_not_current_send_authority", "requirement": "Historical material is verified against its accepted historical binding and never grants current send authority.", "evidence": ["/cases/3"]},
                {"id": "proposal_carrier_reuses_the_one_binding_schema", "requirement": "The closed pre-Genesis carrier fixes Event route, proposal kind, complete sender and target scope while directly reusing the one binding schema; a missing required member fails schema validation before semantic evaluation.", "evidence": ["/cases/4"]},
            ],
        }],
        "cases": cases,
    }


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def clean_final_closure() -> None:
    data = json.loads(FINAL_CLOSURE.read_text(encoding="utf-8"))
    data["version"] = "2026-09-19.2"
    data["covers_vectors"] = [
        item for item in data["covers_vectors"] if item not in {VECTOR_ID, EPOCH_VECTOR_ID}
    ]
    data["security_evidence"] = [
        item for item in data["security_evidence"] if item.get("vector_id") != VECTOR_ID
    ]
    for evidence in data["security_evidence"]:
        for point in evidence.get("decision_points", []):
            point["evidence"] = [
                ref.replace("/cases/15", "/cases/9") for ref in point.get("evidence", [])
            ]
    cleaned_cases = []
    for case in data["cases"]:
        if case.get("vector_id") in {VECTOR_ID, EPOCH_VECTOR_ID}:
            continue
        cleaned_cases.append(case)
    data["cases"] = cleaned_cases
    write_json(FINAL_CLOSURE, data)


def main() -> None:
    write_json(OUTPUT, build_fixture())
    clean_final_closure()


if __name__ == "__main__":
    main()
