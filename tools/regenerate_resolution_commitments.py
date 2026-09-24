#!/usr/bin/env python3
"""Regenerate adapter-derived fixture resolution commitments and their evidence."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "spec/v1/artifacts"
FIXTURES = ARTIFACTS / "fixtures"
REGISTRY = ROOT / "tools/resolution-commitment-pointer-registry.json"
OUTPUT = FIXTURES / "resolution-commitment-fixture.json"
PCR = FIXTURES / "pcr-genesis-fixture.json"
ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
SEED = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def b58(payload: bytes) -> str:
    number = int.from_bytes(payload, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = ALPHABET[remainder] + encoded
    return "1" * (len(payload) - len(payload.lstrip(b"\x00"))) + encoded


def multihash(payload: bytes) -> str:
    return b58(b"\x12\x20" + hashlib.sha256(payload).digest())


def replace(value: Any, old: str, new: str) -> Any:
    if isinstance(value, str):
        return value.replace(old, new)
    if isinstance(value, list):
        return [replace(item, old, new) for item in value]
    if isinstance(value, dict):
        return {key: replace(item, old, new) for key, item in value.items()}
    return value


def substitute_scid(value: Any, scid: str) -> Any:
    return replace(value, "{SCID}", scid)


def build_vector(evidence_id: str, host: str, version_time: str) -> dict[str, Any]:
    key = Ed25519PrivateKey.from_private_bytes(SEED)
    public = key.public_key().public_bytes_raw()
    multikey = "z" + b58(b"\xed\x01" + public)
    preliminary = {
        "versionId": "{SCID}",
        "versionTime": version_time,
        "parameters": {
            "method": "did:webvh:1.0",
            "scid": "{SCID}",
            "updateKeys": [multikey],
            "nextKeyHashes": [multihash(multikey.encode("utf-8"))],
        },
        "state": {
            "id": f"did:webvh:{{SCID}}:{host}",
            "verificationMethod": [
                {
                    "id": f"did:webvh:{{SCID}}:{host}#update-key-1",
                    "controller": f"did:webvh:{{SCID}}:{host}",
                    "type": "Multikey",
                    "publicKeyMultibase": multikey,
                }
            ],
        },
    }
    scid = multihash(canonical(preliminary).encode("utf-8"))
    entry = substitute_scid(preliminary, scid)
    entry_hash_input = dict(entry)
    entry_hash_input["versionId"] = scid
    version_id = "1-" + multihash(canonical(entry_hash_input).encode("utf-8"))
    entry["versionId"] = version_id
    entry["proof"] = [
        {
            "type": "DataIntegrityProof",
            "cryptosuite": "eddsa-jcs-2022",
            "verificationMethod": f"did:key:{multikey}#{multikey}",
            "proofPurpose": "authentication",
            "proofValue": "z" + b58(key.sign(canonical(entry_hash_input).encode("utf-8"))),
        }
    ]
    did = entry["state"]["id"]
    return {
        "evidence_id": evidence_id,
        "adapter_version": "did:webvh:1.0",
        "preliminary_entry": preliminary,
        "verified_entry": entry,
        "commitment": {
            "did": did,
            "method_history_head": "sha256:" + hashlib.sha256(canonical(entry).encode("utf-8")).hexdigest(),
            "version_id": version_id,
        },
        "projected_core_id": "ak:did_core:webvh:" + scid,
    }


def human_vector() -> dict[str, Any]:
    pcr = json.loads(PCR.read_text(encoding="utf-8"))
    evidence = pcr["principal_registration_anchor_evidence"]
    entry = evidence["anchor"]["log_entries"][-1]
    did = entry["state"]["id"]
    commitment = {
        "did": did,
        "method_history_head": "sha256:" + hashlib.sha256(canonical(entry).encode("utf-8")).hexdigest(),
        "version_id": entry["versionId"],
    }
    return {
        "evidence_id": "human_pcr",
        "adapter_version": "did:webvh:1.0",
        "verified_entry": entry,
        "commitment": commitment,
        "projected_core_id": "ak:did_core:webvh:" + did.split(":", 3)[2],
        "external_scid_derivation_ref": "pcr-genesis-fixture.json#/principal_registration_anchor_evidence/scid_derivation",
    }


def resolve(document: Any, pointer: str) -> Any:
    node = document
    for raw in pointer.strip("/").split("/") if pointer else []:
        token = raw.replace("~1", "/").replace("~0", "~")
        node = node[int(token)] if isinstance(node, list) else node[token]
    return node


def assign(document: Any, pointer: str, value: Any) -> None:
    parts = pointer.strip("/").split("/")
    parent = resolve(document, "/".join(parts[:-1]))
    token = parts[-1].replace("~1", "/").replace("~0", "~")
    if isinstance(parent, list):
        parent[int(token)] = value
    else:
        parent[token] = value


def apply_pointer(document: Any, pointer: str, value: Any) -> None:
    if "::" not in pointer:
        assign(document, pointer, value)
        return
    outer, inner = pointer.split("::", 1)
    embedded = json.loads(resolve(document, outer))
    assign(embedded, inner, value)
    assign(document, outer, canonical(embedded))


def recalc_event_case(case: dict[str, Any]) -> None:
    preimage = case["digest_preimage_canonical_bytes_utf8"]
    digest = hashlib.sha256(preimage.encode("utf-8")).hexdigest()
    case["event_digest"] = "sha256:" + digest
    body = bytes((case["suite_wire_code"],)) + bytes.fromhex(digest)
    token = base64.urlsafe_b64encode(body).rstrip(b"=").decode("ascii")
    case["event_id_bytes_hex"] = body.hex()
    case["derived_event_id"] = "ak:event:" + token
    if "derived_realm_id" in case:
        case["derived_realm_id"] = "ak:realm:" + token


def main() -> None:
    rows = json.loads(REGISTRY.read_text(encoding="utf-8"))["pointers"]
    vectors = {
        row["evidence_id"]: row
        for row in [
            human_vector(),
            build_vector("agent_inception", "agent.example", "2026-09-19T10:10:00Z"),
            build_vector("calendar_service", "server-alpha.example", "2026-09-19T10:20:00Z"),
            build_vector("schema_service", "alice.example.net", "2026-09-19T10:30:00Z"),
            build_vector("websocket_service", "server.example", "2026-09-19T10:40:00Z"),
        ]
    }
    documents = {
        name: json.loads((FIXTURES / name).read_text(encoding="utf-8"))
        for name in sorted({row["fixture"] for row in rows})
    }
    for row in rows:
        apply_pointer(documents[row["fixture"]], row["pointer"], vectors[row["evidence_id"]]["commitment"])

    agent = documents["agent-vectors-fixture.json"]
    old_agent_did = "did:webvh:z6mkagent:agent.example"
    old_agent_core = "ak:did_core:webvh:z6mkagent"
    agent = replace(agent, old_agent_did, vectors["agent_inception"]["commitment"]["did"])
    agent = replace(agent, old_agent_core, vectors["agent_inception"]["projected_core_id"])
    provision = next(case for case in agent["cases"] if case.get("name") == "agent_provision")
    requested = provision["requested_scope_commitment"]
    requested_preimage = {
        "agent_id": requested["agent_id"],
        "controller_principal_id": requested["controller_principal_id"],
        "kind": "ak.agent.requested_scope_commitment.v1",
        "requested_scope": requested["requested_scope"],
    }
    old_requested_digest = requested["expected_digest"]
    new_requested_digest = "sha256:" + hashlib.sha256(canonical(requested_preimage).encode("utf-8")).hexdigest()
    agent = replace(agent, old_requested_digest, new_requested_digest)
    runtime = next(case for case in agent["cases"] if case.get("name") == "agent_runtime_key_binding")
    old_binding_digest = runtime["expected_binding_digest"]
    new_binding_digest = "sha256:" + hashlib.sha256(runtime["canonical_binding_json"].encode("utf-8")).hexdigest()
    agent = replace(agent, old_binding_digest, new_binding_digest)
    runtime = next(case for case in agent["cases"] if case.get("name") == "agent_runtime_key_binding")
    old_transcript_digest = runtime["expected_possession_transcript_digest"]
    new_transcript_digest = "sha256:" + hashlib.sha256(
        runtime["canonical_possession_transcript_json"].encode("utf-8")
    ).hexdigest()
    agent = replace(agent, old_transcript_digest, new_transcript_digest)
    runtime = next(case for case in agent["cases"] if case.get("name") == "agent_runtime_key_binding")
    runtime["expected_pairing_request_binding_digest"] = "sha256:" + hashlib.sha256(
        runtime["canonical_pairing_request_binding_json"].encode("utf-8")
    ).hexdigest()
    agent["version"] = "2026-09-19.1"
    documents["agent-vectors-fixture.json"] = agent

    content = documents["content-bound-event-id-fixture.json"]
    by_name = {case.get("name"): case for case in content["cases"] if isinstance(case, dict)}
    first = by_name["agent_provision_forward_declaration_is_constructible"]
    first["digest_preimage_canonical_bytes_utf8"] = first["digest_preimage_canonical_bytes_utf8"].replace(
        old_agent_did, vectors["agent_inception"]["commitment"]["did"]
    ).replace(old_agent_core, vectors["agent_inception"]["projected_core_id"])
    recalc_event_case(first)
    second = by_name["agent_provision_declares_the_frozen_genesis_realm_id"]
    second["digest_preimage_canonical_bytes_utf8"] = second["digest_preimage_canonical_bytes_utf8"].replace(
        old_agent_did, vectors["agent_inception"]["commitment"]["did"]
    ).replace(old_agent_core, vectors["agent_inception"]["projected_core_id"])
    old_declared = second["declared_principal_control_realm_id"]
    second["digest_preimage_canonical_bytes_utf8"] = second["digest_preimage_canonical_bytes_utf8"].replace(
        old_declared, first["derived_realm_id"]
    )
    second["declared_principal_control_realm_id"] = first["derived_realm_id"]
    recalc_event_case(second)
    content["version"] = "2026-09-19.1"

    for filename, vector_id, container in (
        ("calendar-notification-fixture.json", "calendar_service", documents["calendar-notification-fixture.json"]["schema_validation_cases"][0]["instance"]),
        ("schema-validation-fixture.json", "schema_service", documents["schema-validation-fixture.json"]["schema_validation_cases"][0]["instance"]),
        ("websocket-binding-fixture.json", "websocket_service", documents["websocket-binding-fixture.json"]["bundle_closure_cases"][0]["instance"]),
    ):
        container["service_id"] = vectors[vector_id]["projected_core_id"]
        documents[filename]["version"] = "2026-09-19.1"

    for name, document in documents.items():
        (FIXTURES / name).write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    output = {
        "version": "2026-09-19.1",
        "generated_by": "tools/regenerate_resolution_commitments.py",
        "description": "Adapter evidence for every fixture resolution commitment covered by tools/resolution-commitment-pointer-registry.json.",
        "runner": {"kind": "known_answer_tests", "entrypoint": "ak.suite.identity.resolution_commitment.v1"},
        "vectors": list(vectors.values()),
    }
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
