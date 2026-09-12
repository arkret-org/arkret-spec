#!/usr/bin/env python3
"""Generate the near-current unique-head MLS governance-frontier fixture."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "spec/v1/artifacts/schemas"
OUTPUT = ROOT / "spec/v1/artifacts/fixtures/mls-governance-proof-fixture.json"
DOMAIN = b"ak.mls-governance-proof-page-v1"
ZERO = b"\x00"

EMPTY_ROOT = "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def jcs(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def sha(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def query_digest(value: dict[str, Any]) -> str:
    return sha(b"ak.mls-governance-proof-query-v1" + ZERO + jcs(value))


def seal(byte: int) -> str:
    return "ak:seal:sha256:" + f"{byte:02x}" * 32


def basis(*refs: str) -> dict[str, Any]:
    return {"leaves": sorted(refs)}


def query(base: dict[str, Any], target: dict[str, Any], *, genesis: bool) -> dict[str, Any]:
    value = {
        "profile": "group_security_frontier",
        "effective_scope": {"kind": "realm", "realm_id": REALM},
        "mls_group_id": GROUP,
        "local_mls_leaves": [
            {
                "leaf_index": 0,
                "actor_id": {
                    "kind": "account",
                    "account_id": {
                        "principal_id": "ak:did_core:webvh:z6mkfixturealice:alice.example",
                        "station_id": "ak:did_core:web:station.example",
                    },
                },
                "credential_ref": "did:webvh:z6mkfixturealice:alice.example#device-1",
            }
        ],
        "proof_base_basis": base,
        "proof_target_basis": target,
        "byte_limit": 1048576,
        "frontier_purpose": "group_binding",
        "previous_epoch": 0,
        "next_epoch": 0 if genesis else 1,
        "binding_profile": "ak.security_frontier.v1",
    }
    if not genesis:
        value["base_group_state_ref"] = BASE_GROUP_STATE
    return value


def b64u(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def content_id(kind: str, label: str) -> str:
    body = b"\x01" + hashlib.sha256(label.encode("utf-8")).digest()
    return f"ak:{kind}:" + b64u(body)


REALM = content_id("realm", "mls-governance-fixture-realm-create")
GROUP = b64u(REALM.encode("utf-8"))
BASE_GROUP_STATE = content_id("event", "mls-governance-fixture-base-group-state")


def frontier_entry(target_ref: str, index: int) -> tuple[dict[str, Any], str, str]:
    cell = f"ak:cell:ak.component.member.state.v1:did.web.member-{index}.example"
    value = {"head": "join", "target_seal_ref": target_ref}
    event_id = content_id("event", f"mls-governance-frontier-provenance-{index}")
    preimage = jcs({"cell": cell, "state": {"revision_event_id": event_id, "value": value}})
    leaf_digest = sha(ZERO + preimage)
    entry = {
        "cell_id": cell,
        "value_digest": sha(jcs(value)),
        "provenance_event_refs": [event_id],
        "inclusion_witness": {
            "proof_kind": "state_membership",
            "root_seal_ref": target_ref,
            "root_field": "state_root",
            "root_digest": leaf_digest,
            "leaf_canonical_preimage_b64u": b64u(preimage),
            "leaf_digest": leaf_digest,
            "leaf_index": 0,
            "leaf_count": 1,
            "siblings": [],
        },
    }
    return entry, event_id, leaf_digest


def empty_range() -> dict[str, Any]:
    return {
        "cell_family": "ak.component.mls.epoch.v1",
        "subject_prefix": "",
        "leaf_count": 0,
        "start_index": 0,
        "end_index_exclusive": 0,
        "included_entry_indices": [],
        "left_boundary": {"side": "left", "state_edge": True},
        "right_boundary": {"side": "right", "state_edge": True},
    }


def body(refs: list[str], target_refs: list[str], edges: list[tuple[str, str]]) -> dict[str, Any]:
    registry = json.loads(
        (ROOT / "spec/v1/artifacts/registry/mls-security-frontier-registry.json").read_text(
            encoding="utf-8"
        )
    )
    descriptors = [{"seal_ref": ref} for ref in sorted(refs)]
    predecessor_edges = [
        {"seal_ref": child, "predecessor_seal_ref": parent}
        for child, parent in sorted(edges)
    ]
    branches = []
    event_ids = []
    for index, target_ref in enumerate(sorted(target_refs)):
        if edges:
            entry, event_id, state_root = frontier_entry(target_ref, index)
            event_ids.append(event_id)
            ranges = [
                {
                    "cell_family": "ak.component.member.state.v1",
                    "subject_prefix": f"did.web.member-{index}.example",
                    "leaf_count": 1,
                    "start_index": 0,
                    "end_index_exclusive": 1,
                    "included_entry_indices": [0],
                    "left_boundary": {"side": "left", "state_edge": True},
                    "right_boundary": {"side": "right", "state_edge": True},
                }
            ]
            entries = [entry]
        else:
            state_root = EMPTY_ROOT
            entries = []
            ranges = [empty_range()]
        branches.append(
            {
                "target_seal_ref": target_ref,
                "state_root": state_root,
                "cells": entries,
                "range_witnesses": ranges,
            }
        )
    return {
        "frontier_projection": {
            "frontier_registry_digest": sha(jcs(registry)),
            "branches": branches,
        },
        "proof_material": {
            "seal_descriptors": descriptors,
            "seal_predecessor_edges": predecessor_edges,
            "event_ids": sorted(event_ids),
        },
    }


def make_case(
    name: str,
    base_refs: list[str],
    target_refs: list[str],
    edges: list[tuple[str, str]],
    *,
    genesis: bool = False,
) -> dict[str, Any]:
    q = query(basis(*base_refs), basis(*target_refs), genesis=genesis)
    page_body = body(sorted(set(base_refs + target_refs + [r for edge in edges for r in edge])), target_refs, edges)
    q_digest = query_digest(q)
    page_digest = sha(DOMAIN + ZERO + q_digest.encode("utf-8") + ZERO + jcs(page_body))
    outcome = {"query_digest": q_digest, **page_body, "page_digest": page_digest}
    return {
        "name": name,
        "query": q,
        "query_digest": q_digest,
        "page_body_without_query_digest_and_page_digest": page_body,
        "outcome": outcome,
        "expected_page_digest": page_digest,
        "expected_relation": (
            "equal_basis" if base_refs == target_refs else
            "strict_descendant_basis"
        ),
    }


def validator() -> Draft202012Validator:
    schemas: dict[str, Any] = {}
    for path in SCHEMA_DIR.glob("*.json"):
        value = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(value, dict) and isinstance(value.get("$id"), str):
            schemas[value["$id"]] = value
    schema = json.loads((SCHEMA_DIR / "mls-governance-proof-bundle.schema.json").read_text(encoding="utf-8"))
    resolver = RefResolver(base_uri=schema["$id"], referrer=schema, store=schemas)
    return Draft202012Validator(schema, resolver=resolver)


def build() -> dict[str, Any]:
    s1, s2, s3, s4 = seal(1), seal(2), seal(3), seal(4)
    cases = [
        make_case("genesis_base_equals_target", [s1], [s1], [], genesis=True),
        make_case("successor_base_equals_target", [s1], [s1], []),
        make_case("strict_descendant", [s1], [s2], [(s2, s1)]),
        make_case("confirmed_prefix_two_steps", [s1], [s3], [(s3, s2), (s2, s1)]),
    ]
    schema_validator = validator()
    for case in cases:
        schema_validator.validate(case["query"])
        schema_validator.validate(case["outcome"])
    return {
        "profile": "ak.profile.mls_governance_binding.full.v1",
        "version": "2026-08-21",
        "suite": "mls_governance_frontier_basis",
        "generated_by": "tools/generate_mls_governance_proof_fixture.py",
        "runner": {"kind": "named_suite", "entrypoint": "ak.suite.mls.governance_proof_bundle.v1"},
        "covers_vectors": [
            "ak.vector.mls.governance_proof.verifier.v1",
            "ak.vector.mls.governance_proof.materializer.v1",
        ],
        "schema_ref": "../schemas/mls-governance-proof-bundle.schema.json#/$defs/read_outcome",
        "page_digest_formula": {
            "domain": DOMAIN.decode("ascii"),
            "formula": "SHA-256(UTF8(domain) || 0x00 || UTF8(query_digest) || 0x00 || JCS(page_body))",
        },
        "cases": cases,
        "negative_cases": [
            {
                "name": "genesis_with_base_group_state_ref",
                "mutation": "add base_group_state_ref to a genesis 0 -> 0 query",
                "expected": "schema_violation",
                "response_count": 0,
            },
            {
                "name": "successor_without_base_group_state_ref",
                "mutation": "remove base_group_state_ref from a successor query",
                "expected": "schema_violation",
                "response_count": 0,
            },
            {
                "name": "concurrent_unreachable_basis",
                "mutation": "replace proof_target_basis with a head that has no base ancestor",
                "expected": "mls_governance_anchor_unreachable",
                "response_count": 0,
            },
            {
                "name": "response_exceeds_byte_limit",
                "mutation": "set byte_limit below the exact complete response bytes",
                "expected": "mls_governance_proof_bounds_exceeded",
                "response_count": 0,
            },
            {
                "name": "multiple_same_realm_heads",
                "mutation": "supply two incomparable heads for the same group Realm",
                "expected": "reject_incomplete_target_basis",
                "response_count": 0,
            },
            {
                "name": "multi_leaf_missing_branch",
                "mutation": "remove one frontier branch required by proof_target_basis",
                "expected": "reject_incomplete_target_branch_set",
                "response_count": 0,
            },
            {
                "name": "multi_leaf_duplicate_branch",
                "mutation": "duplicate one target_seal_ref branch",
                "expected": "reject_duplicate_target_branch",
                "response_count": 0,
            },
            {
                "name": "multi_leaf_cross_root_witness",
                "mutation": "move one branch entry under another target Seal root",
                "expected": "reject_cross_branch_root",
                "response_count": 0,
            },
            {
                "name": "base_leaf_not_consumed",
                "mutation": "remove the only target descendant of one base leaf",
                "expected": "reject_basis_dominance",
                "response_count": 0,
            },
            {
                "name": "page_digest_mismatch",
                "mutation": "change one target leaf after page digest calculation",
                "expected": "reject_page_digest",
                "response_count": 0,
            },
            {
                "name": "stateful_bulk_profile",
                "mutation": "add an epoch range, cursor, continuation or result-set selector",
                "expected": "schema_violation",
                "response_count": 0,
            },
        ],
        "runner_rules": [
            "Validate every positive query and outcome against the read_request/read_outcome schema.",
            "Treat proof_base_basis and proof_target_basis as canonical complete Seal bases with exactly one confirmed head per represented Realm.",
            "base==target is valid; a strict descendant is valid only with the complete unique predecessor chain.",
            "The stateless operation never transports bulk epoch activation evidence.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = json.dumps(build(), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != rendered:
            print(f"stale generated fixture: {OUTPUT.relative_to(ROOT)}")
            return 1
        print(f"generated fixture is current: {OUTPUT.relative_to(ROOT)}")
        return 0
    OUTPUT.write_text(rendered, encoding="utf-8", newline="\n")
    print(f"updated {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
