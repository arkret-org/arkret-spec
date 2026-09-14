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
SCHEMA_ID = "https://arkret.org/v1/schemas/authenticated-signer-resolution-evidence.schema.json"
VECTOR_ID = "ak.vector.identity.human_control_signer_evidence.v1"
ENTRYPOINT = "ak.suite.identity.human_control_signer_evidence.v1"


def canonical(value: object) -> str:
    # This fixture contains no floating-point values; sorted compact JSON is its
    # RFC 8785 representation and keeps the known content address reviewable.
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def evidence_ref(root: object) -> str:
    digest = hashlib.sha256(canonical(root).encode("utf-8")).hexdigest()
    return f"ak:signer_evidence:sha256:{digest}"


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


def reject(reason: str) -> dict[str, str]:
    return {"decision": "reject", "failure_class": reason}


def evaluate(case: dict[str, Any], validator: Draft202012Validator) -> dict[str, str]:
    root = case["evidence_root"]
    candidate = case["candidate_event"]
    if candidate.get("lane") != "generic_control":
        return reject("wrong_lane")
    if not candidate.get("proof_uses_evidence_root_content_address"):
        return reject("evidence_reference_mismatch")
    if not validator.is_valid(root):
        return reject("evidence_schema_invalid")

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
        or genesis.get("principal_inception_signature_valid") is not True
        or genesis.get("producer_proof_valid") is not True
        or authorization.get("producer_proof_valid") is not True
        or authorization.get("possession_proof_valid") is not True
        or confirmation.get("historical_notary_configuration_valid") is not True
        or confirmation.get("state_transition_valid") is not True
        or confirmation.get("command_result") != "committed"
    ):
        return reject("history_verification_failed")

    account = root["account_id"]
    if root["signer_id"] != account["principal_id"]:
        return reject("account_mismatch")
    if candidate["producer_account_id"] != account or authorization["account_id"] != account:
        return reject("account_mismatch")
    if candidate["producer_device_id"] != root["device_id"] or authorization["device_id"] != root["device_id"]:
        return reject("device_mismatch")
    if (
        candidate["verification_method"] != root["verification_method"]
        or authorization["verification_method"] != root["verification_method"]
        or root["verification_method"].split("#", 1)[0] != root["principal_inception"]["did"]
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


def main() -> int:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if set(fixture) != {
        "suite", "runner", "covers_vectors", "schema_ref", "canonical_case", "negative_cases"
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

    expected_names = {
        "missing_authorization_event_dependency",
        "missing_confirmation_seal_dependency",
        "invalid_principal_inception_signature",
        "invalid_pcr_genesis_producer_proof",
        "invalid_authorize_producer_proof",
        "invalid_device_possession_proof",
        "invalid_historical_notary_configuration",
        "invalid_confirming_state_transition",
        "confirmation_is_not_first_successful_seal",
        "history_event_prefix_is_not_utf8_sorted",
        "history_prefix_contains_unrelated_successor",
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
    cases = fixture["negative_cases"]
    names = [case.get("name") for case in cases]
    if len(names) != len(set(names)) or set(names) != expected_names:
        raise SystemExit("human Control signer-evidence negative case coverage drifted")

    validator = evidence_validator()
    canonical_case = fixture["canonical_case"]
    validator.validate(canonical_case["evidence_root"])
    expected_root_ref = evidence_ref(canonical_case["evidence_root"])
    expected_jcs = canonical(canonical_case["evidence_root"])
    if canonical_case["expected"] != {
        "decision": "accept",
        "evidence_root_jcs": expected_jcs,
        "evidence_root_ref": expected_root_ref,
    }:
        raise SystemExit("human Control signer-evidence content-address known answer drifted")
    if evaluate(canonical_case, validator) != canonical_case["expected"]:
        raise SystemExit("human Control signer-evidence canonical prefix was not accepted")

    for case in cases:
        mutated = apply_mutations(canonical_case, case["mutations"])
        mutated.pop("expected", None)
        actual = evaluate(mutated, validator)
        if actual != case["expected"]:
            raise SystemExit(
                f"{case['name']}: expected {case['expected']!r}, got {actual!r}"
            )

    print(
        "human Control signer-evidence KAT: canonical content address, complete first-confirmation "
        f"prefix and {len(cases)} negative cases OK"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
