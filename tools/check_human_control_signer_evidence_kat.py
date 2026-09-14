#!/usr/bin/env python3
"""Execute the account_device_control portable signer-evidence closure KAT."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = (
    ROOT
    / "spec"
    / "v1"
    / "artifacts"
    / "fixtures"
    / "human-control-signer-evidence-kat.json"
)
SCHEMAS = ROOT / "spec" / "v1" / "artifacts" / "schemas"
ADAPTER_REGISTRY = (
    ROOT / "spec" / "v1" / "artifacts" / "registry" / "did-method-adapter-registry.json"
)
SCHEMA_ID = "https://arkret.org/v1/schemas/authenticated-signer-resolution-evidence.schema.json"
VECTOR_ID = "ak.vector.identity.human_control_signer_evidence.v1"
ENTRYPOINT = "ak.suite.identity.human_control_signer_evidence.v1"


def canonical(value: object) -> str:
    # This fixture contains no floating-point values; sorted compact JSON is its
    # RFC 8785 representation and keeps the known content address reviewable.
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def evidence_ref(root: object) -> str:
    return f"ak:signer_evidence:sha256:{sha256_hex(canonical(root))}"


def registered_anchor_kinds() -> dict[str, str]:
    """Map registration_anchor_kind to its method, from the adapter registry alone."""
    registry = json.loads(ADAPTER_REGISTRY.read_text(encoding="utf-8"))
    kinds: dict[str, str] = {}
    for adapter in registry["adapters"]:
        if adapter.get("status") != "active" or not adapter.get("human_principal_anchor"):
            continue
        kind = adapter.get("registration_anchor_kind")
        if not isinstance(kind, str) or not kind:
            raise SystemExit(
                f"{adapter.get('method')}: an active human principal anchor must declare registration_anchor_kind"
            )
        if kind in kinds:
            raise SystemExit(f"registration_anchor_kind {kind} is declared by more than one adapter")
        kinds[kind] = adapter["method"]
    return kinds


def evidence_validator() -> Draft202012Validator:
    resources = []
    for path in SCHEMAS.glob("*.json"):
        document = json.loads(path.read_text(encoding="utf-8"))
        resources.append((document["$id"], Resource.from_contents(document)))
    registry = Registry().with_resources(resources)
    return Draft202012Validator(
        {"$ref": f"{SCHEMA_ID}#/$defs/account_device_control_signer_evidence"},
        registry=registry,
    )


def anchor_union_matches_registry(kinds: dict[str, str]) -> None:
    document = json.loads(
        (SCHEMAS / "principal-registration-anchor.schema.json").read_text(encoding="utf-8")
    )
    declared = set()
    for branch in document["oneOf"]:
        pointer = branch["$ref"].removeprefix("#/$defs/")
        const = document["$defs"][pointer]["properties"]["anchor_kind"]["const"]
        declared.add(const)
    if declared != set(kinds):
        raise SystemExit(
            "principal-registration-anchor branches "
            f"{sorted(declared)} drifted from the registry-derived anchor kinds {sorted(kinds)}"
        )


def pointer_parent(document: Any, pointer: str) -> tuple[Any, str]:
    if not pointer.startswith("/"):
        raise ValueError(f"mutation path is not a JSON Pointer: {pointer}")
    parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer[1:].split("/")]
    parent = document
    for part in parts[:-1]:
        parent = parent[int(part)] if isinstance(parent, list) else parent[part]
    return parent, parts[-1]


def apply_mutations(base: dict[str, Any], mutations: list[dict[str, Any]]) -> dict[str, Any]:
    value = copy.deepcopy(base)
    for mutation in mutations:
        if set(mutation) - {"op", "path", "value"}:
            raise ValueError(f"mutation has unknown members: {mutation}")
        parent, final = pointer_parent(value, mutation["path"])
        operation = mutation["op"]
        if operation == "delete":
            if "value" in mutation:
                raise ValueError("delete mutation cannot carry value")
            if isinstance(parent, list):
                del parent[int(final)]
            else:
                del parent[final]
        elif operation == "replace":
            if "value" not in mutation:
                raise ValueError("replace mutation requires value")
            if isinstance(parent, list):
                parent[int(final)] = mutation["value"]
            else:
                parent[final] = mutation["value"]
        elif operation == "append":
            if "value" not in mutation:
                raise ValueError("append mutation requires value")
            target = parent[int(final)] if isinstance(parent, list) else parent[final]
            if not isinstance(target, list):
                raise ValueError("append mutation target is not an array")
            target.append(mutation["value"])
        else:
            raise ValueError(f"unsupported mutation operation: {operation}")
    return value


def utf8_sorted_unique(values: list[str]) -> bool:
    return values == sorted(values, key=lambda value: value.encode("utf-8")) and len(values) == len(set(values))


def project(did: str) -> str | None:
    parts = did.split(":")
    if len(parts) < 3 or parts[0] != "did":
        return None
    return f"ak:did_core:{parts[1]}:{parts[2]}"


def version_number(version_id: object) -> int | None:
    """did:webvh versionId is <version number>-<entryHash>."""
    if not isinstance(version_id, str):
        return None
    head, separator, _ = version_id.partition("-")
    if not separator or not head.isdigit():
        return None
    return int(head)


def derive_webvh_anchor(anchor: dict[str, Any]) -> dict[str, str] | None:
    operation = anchor["registration_did_operation"]
    did = operation.get("did")
    if operation.get("did_method") != "webvh" or not isinstance(did, str):
        return None
    if not did.startswith("did:webvh:"):
        return None
    entries = anchor["log_entries"]
    if not entries:
        return None
    for index, entry in enumerate(entries):
        if version_number(entry.get("versionId")) != index + 1:
            return None
    terminal = entries[-1]
    if canonical(operation.get("operation")) != canonical(terminal):
        return None
    terminal_version = version_number(terminal["versionId"])
    if "seq" in operation and operation["seq"] != terminal_version:
        return None

    known_versions = {entry["versionId"] for entry in entries}
    records: dict[str, Any] = {}
    for record in anchor["witness_records"]:
        version_id = record.get("versionId")
        if version_id not in known_versions or set(record) != {"versionId", "proof"}:
            return None
        if version_id in records:
            return None
        records[version_id] = record
    # did:webvh witness policy is inherited: once an entry declares one it stays
    # active for every later entry until a successor replaces it.
    active_policy: dict[str, Any] | None = None
    for entry in entries:
        declared = entry.get("parameters", {}).get("witness")
        if declared is not None:
            active_policy = declared
        if active_policy is None:
            continue
        proofs = records.get(entry["versionId"], {}).get("proof", [])
        witnesses = {witness["id"] for witness in active_policy["witnesses"]}
        signers = {
            proof.get("verificationMethod", "").split("#", 1)[0]
            for proof in proofs
        }
        if len(signers & witnesses) < active_policy["threshold"]:
            return None

    if anchor["normalized_did_document"].get("did") != did:
        return None
    update_keys = terminal.get("parameters", {}).get("updateKeys")
    if not isinstance(update_keys, list) or len(update_keys) != 1:
        return None
    root_key = update_keys[0]
    if not isinstance(root_key, str):
        return None
    proofs = terminal.get("proof")
    if not isinstance(proofs, list) or not proofs:
        return None
    root_method = proofs[0].get("verificationMethod")
    if root_method != f"did:key:{root_key}#{root_key}":
        return None
    return {
        "did": did,
        "method_history_head": "sha256:" + sha256_hex(canonical(terminal)),
        "version_id": terminal["versionId"],
        "root_verification_method": root_method,
        "root_public_key_multibase": root_key,
    }


def derive_anchor(anchor: dict[str, Any]) -> dict[str, str] | None:
    if anchor["anchor_kind"] == "webvh_registration":
        return derive_webvh_anchor(anchor)
    return None


def reject(reason: str) -> dict[str, str]:
    return {"decision": "reject", "failure_class": reason}


def evaluate(
    case: dict[str, Any], validator: Draft202012Validator, anchor_kinds: dict[str, str]
) -> dict[str, str]:
    root = case["evidence_root"]
    candidate = case["candidate_event"]
    if candidate.get("lane") != "generic_control":
        return reject("wrong_lane")
    if not candidate.get("proof_uses_evidence_root_content_address"):
        return reject("evidence_reference_mismatch")

    anchor = root.get("principal_registration_anchor")
    if not isinstance(anchor, dict) or anchor.get("anchor_kind") not in anchor_kinds:
        return reject("unsupported_did_method")
    if not validator.is_valid(root):
        return reject("evidence_schema_invalid")
    derived = derive_anchor(anchor)
    if derived is None:
        return reject("registration_anchor_invalid")

    dependencies = case["resolved_dependencies"]
    events = {event["event_ref"]: event for event in dependencies["events"]}
    seals = {seal["seal_ref"]: seal for seal in dependencies["seals"]}
    if any(reference not in events for reference in root["history_event_refs"]):
        return reject("dependency_missing")
    if any(reference not in seals for reference in root["history_seal_refs"]):
        return reject("dependency_missing")

    authorization_ref = root["authorization_event_ref"]
    successful = sorted(
        (
            seal
            for seal in case["authority_history"]["seals"]
            if seal["confirms_authorization_ref"] == authorization_ref
            and seal["command_result"] == "committed"
        ),
        key=lambda seal: seal["sequence"],
    )
    if not successful or root["confirmation_seal_ref"] != successful[0]["seal_ref"]:
        return reject("confirmation_not_first_successful")

    event_refs = root["history_event_refs"]
    seal_refs = root["history_seal_refs"]
    if not utf8_sorted_unique(event_refs) or not utf8_sorted_unique(seal_refs):
        return reject("prefix_not_canonical")
    exact_event_prefix = {root["pcr_genesis_event_ref"], root["generation_event_ref"], authorization_ref}
    exact_seal_prefix = {root["confirmation_seal_ref"]}
    if set(event_refs) != exact_event_prefix or set(seal_refs) != exact_seal_prefix:
        return reject("prefix_not_minimal")

    genesis = events[root["pcr_genesis_event_ref"]]
    authorization = events[authorization_ref]
    generation = events[root["generation_event_ref"]]
    confirmation = seals[root["confirmation_seal_ref"]]
    if (
        genesis.get("pcr_genesis") is not True
        or genesis.get("root_producer_proof_valid") is not True
        or genesis.get("producer_proof_valid") is not True
        or authorization.get("producer_proof_valid") is not True
        or authorization.get("possession_proof_valid") is not True
        or confirmation.get("historical_notary_configuration_valid") is not True
        or confirmation.get("state_transition_valid") is not True
        or confirmation.get("command_result") != "committed"
    ):
        return reject("history_verification_failed")

    initial_resolution = genesis.get("initial_resolution", {})
    if any(
        initial_resolution.get(field) != derived[field]
        for field in ("did", "method_history_head", "version_id")
    ):
        return reject("registration_anchor_coordinates_mismatch")
    if (
        genesis.get("root_verification_method") != derived["root_verification_method"]
        or genesis.get("root_public_key_multibase") != derived["root_public_key_multibase"]
    ):
        return reject("registration_anchor_root_key_mismatch")

    account = root["account_id"]
    if project(derived["did"]) != account["principal_id"]:
        return reject("principal_projection_mismatch")
    if root["signer_id"] != account["principal_id"]:
        return reject("account_mismatch")
    if candidate["producer_account_id"] != account or authorization["account_id"] != account:
        return reject("account_mismatch")
    if candidate["producer_device_id"] != root["device_id"] or authorization["device_id"] != root["device_id"]:
        return reject("device_mismatch")
    if (
        candidate["verification_method"] != root["verification_method"]
        or authorization["verification_method"] != root["verification_method"]
        or root["verification_method"].split("#", 1)[0] != derived["did"]
    ):
        return reject("verification_method_mismatch")
    if candidate["public_key_multibase"] != authorization["public_key_multibase"]:
        return reject("public_key_mismatch")
    if (
        authorization["authorized_generation_ref"] != root["authorized_generation_ref"]
        or generation["authorized_generation_ref"] != root["authorized_generation_ref"]
        or authorization["generation_event_ref"] != root["generation_event_ref"]
    ):
        return reject("generation_mismatch")
    if not authorization["not_before"] <= candidate["created_at"] < authorization["expires_at"]:
        return reject("authorization_window_mismatch")
    return {
        "decision": "accept",
        "evidence_root_jcs": canonical(root),
        "evidence_root_ref": evidence_ref(root),
    }


EXPECTED_WEBVH_NEGATIVES = {
    "missing_authorization_event_dependency",
    "missing_confirmation_seal_dependency",
    "invalid_registration_root_producer_proof",
    "invalid_pcr_genesis_producer_proof",
    "invalid_authorize_producer_proof",
    "invalid_device_possession_proof",
    "invalid_historical_notary_configuration",
    "invalid_confirming_state_transition",
    "confirmation_is_not_first_successful_seal",
    "history_event_prefix_is_not_utf8_sorted",
    "history_prefix_contains_unrelated_successor",
    "did_web_human_anchor_is_not_a_registered_branch",
    "unknown_anchor_discriminator",
    "did_key_human_anchor_is_not_a_registered_branch",
    "anchor_operation_method_disagrees_with_did",
    "anchor_log_does_not_start_at_inception",
    "anchor_log_skips_a_predecessor_version",
    "anchor_operation_is_not_the_terminal_log_entry",
    "anchor_operation_seq_disagrees_with_the_terminal_version",
    "anchor_witness_record_set_is_incomplete",
    "anchor_witness_record_is_surplus",
    "anchor_root_verification_method_is_not_the_update_key",
    "anchor_normalized_document_did_is_substituted",
    "derived_method_history_head_mismatches_genesis",
    "derived_version_id_mismatches_genesis",
    "derived_root_verification_method_mismatches_genesis",
    "derived_root_key_mismatches_genesis",
    "anchor_principal_projection_mismatches_account",
    "wrong_account_binding",
    "wrong_device_binding",
    "wrong_verification_method_binding",
    "wrong_public_key_binding",
    "wrong_generation_binding",
    "signature_before_authorization_window",
    "signature_at_authorization_expiry",
    "account_device_control_rejected_for_data_lane",
    "account_device_control_rejected_for_native_unit_lane",
}

EXPECTED_DID_KEY_REJECTIONS = {
    "did_key_anchor_carries_a_selectable_document_mirror",
    "did_key_anchor_carries_a_synthesized_operation",
    "did_key_derived_synthetic_version_mismatches_genesis",
    "did_key_derived_root_key_mismatches_genesis",
}


def run_group(
    base: dict[str, Any],
    cases: list[dict[str, Any]],
    validator: Draft202012Validator,
    anchor_kinds: dict[str, str],
    label: str,
) -> None:
    validator.validate(base["evidence_root"])
    expected = {
        "decision": "accept",
        "evidence_root_jcs": canonical(base["evidence_root"]),
        "evidence_root_ref": evidence_ref(base["evidence_root"]),
    }
    if base["expected"] != expected:
        raise SystemExit(f"{label}: content-address known answer drifted")
    if evaluate(base, validator, anchor_kinds) != base["expected"]:
        raise SystemExit(f"{label}: canonical prefix was not accepted")
    for case in cases:
        mutated = apply_mutations(base, case["mutations"])
        mutated.pop("expected", None)
        actual = evaluate(mutated, validator, anchor_kinds)
        if actual != case["expected"]:
            raise SystemExit(f"{label}/{case['name']}: expected {case['expected']!r}, got {actual!r}")


def run_rejected_group(
    base: dict[str, Any],
    cases: list[dict[str, Any]],
    validator: Draft202012Validator,
    anchor_kinds: dict[str, str],
    label: str,
) -> None:
    if evaluate(base, validator, anchor_kinds) != base["expected"]:
        raise SystemExit(f"{label}: unsupported base input was not rejected")
    for case in cases:
        mutated = apply_mutations(base, case["mutations"])
        mutated.pop("expected", None)
        actual = evaluate(mutated, validator, anchor_kinds)
        if actual != case["expected"]:
            raise SystemExit(f"{label}/{case['name']}: expected {case['expected']!r}, got {actual!r}")


def main() -> int:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if set(fixture) != {
        "suite",
        "runner",
        "covers_vectors",
        "schema_ref",
        "registration_anchor_rules",
        "canonical_case",
        "unsupported_did_key_case",
        "negative_cases",
        "did_key_rejection_cases",
    }:
        raise SystemExit("human Control signer-evidence KAT top-level shape drifted")
    if fixture["runner"] != {"kind": "known_answer_tests", "entrypoint": ENTRYPOINT}:
        raise SystemExit("human Control signer-evidence KAT runner drifted")
    if fixture["covers_vectors"] != [VECTOR_ID]:
        raise SystemExit("human Control signer-evidence KAT vector binding drifted")
    if fixture["schema_ref"] != (
        "schemas/authenticated-signer-resolution-evidence.schema.json"
        "#/$defs/account_device_control_signer_evidence"
    ):
        raise SystemExit("human Control signer-evidence KAT schema_ref drifted")

    for group, expected_names in (
        ("negative_cases", EXPECTED_WEBVH_NEGATIVES),
        ("did_key_rejection_cases", EXPECTED_DID_KEY_REJECTIONS),
    ):
        names = [case.get("name") for case in fixture[group]]
        if len(names) != len(set(names)) or set(names) != expected_names:
            raise SystemExit(f"human Control signer-evidence {group} coverage drifted")

    anchor_kinds = registered_anchor_kinds()
    anchor_union_matches_registry(anchor_kinds)
    validator = evidence_validator()
    run_group(
        fixture["canonical_case"], fixture["negative_cases"], validator, anchor_kinds, "did:webvh anchor"
    )
    run_rejected_group(
        fixture["unsupported_did_key_case"],
        fixture["did_key_rejection_cases"],
        validator,
        anchor_kinds,
        "did:key human registration",
    )

    print(
        "human Control signer-evidence KAT: WebVH-only registration anchor, did:key rejection, canonical "
        "content addresses, complete first-confirmation prefix and "
        f"{len(fixture['negative_cases']) + len(fixture['did_key_rejection_cases'])} negative cases OK"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
