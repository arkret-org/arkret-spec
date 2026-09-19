"""Close device-pairing code claim over the origin current-device gate."""

from __future__ import annotations

from typing import Any

from .core import ARTIFACTS, SPEC_ROOT, Lint, load_json, read_text


SCHEMA = ARTIFACTS / "schemas" / "device-revocation-state.schema.json"
CONTRACT = ARTIFACTS / "registry" / "contract-registry.json"
VECTOR_REGISTRY = ARTIFACTS / "registry" / "vector-registry.json"
FIXTURE = ARTIFACTS / "fixtures" / "protocol-edge-cases-fixture.json"
DEVICE_PROSE = SPEC_ROOT / "zh" / "crypto-media" / "device-lifecycle.md"
BINDING_PROSE = SPEC_ROOT / "zh" / "sync" / "service-http-binding.md"

CLAIM_OPERATION = "ak.gate.account.read.claim_device_pairing_code.v1"
GATE_OPERATION = "ak.peer.device_revocations.command.check.v1"
ACTION_CLASS = "device_pairing_code_claim"
VECTOR_ID = "ak.vector.device_pairing.code_claim.v1"

EXPECTED_DENIED_ACTIONS = [
    "session_grant_issue_or_refresh",
    ACTION_CLASS,
    "keypackage_claim",
    "to_device_write",
    "event_write",
]

EXPECTED_GATE_ACTIONS = [
    "session_grant_issue",
    "returning_session_grant_issue",
    "session_grant_refresh",
    ACTION_CLASS,
    "keypackage_claim",
    "to_device_write",
    "event_write",
]

EXPECTED_ORDER = [
    "authenticate_standard_session_grant_and_exact_http_dpop_jti",
    "apply_caller_device_account_and_service_transport_buckets",
    "obtain_origin_station_current_device_decision",
    "locate_exact_pending_record_by_code",
    "validate_pending_and_count_only_located_failures",
]

REQUIRED_VARIANTS = {
    "claim_current_device_gate_allow",
    "claim_current_device_gate_revocation_pending",
    "claim_current_device_gate_revoked",
    "claim_current_device_gate_generation_mismatch",
    "claim_current_device_gate_receipt_mismatch_or_expired",
    "claim_current_device_gate_unavailable",
    "claim_event_write_action_class_substitution",
    "claim_session_grant_snapshot_only",
}


def _operation(document: dict[str, Any], operation_id: str) -> dict[str, Any] | None:
    registry = document.get("operation_registry")
    rows = registry.get("operations") if isinstance(registry, dict) else None
    if not isinstance(rows, list):
        return None
    matches = [
        row
        for row in rows
        if isinstance(row, dict) and row.get("operation_id") == operation_id
    ]
    return matches[0] if len(matches) == 1 else None


def _vector_case(document: dict[str, Any]) -> dict[str, Any] | None:
    cases = document.get("cases")
    if not isinstance(cases, list):
        return None
    matches = [
        row
        for row in cases
        if isinstance(row, dict) and row.get("vector_id") == VECTOR_ID
    ]
    return matches[0] if len(matches) == 1 else None


def _const_prefix_items(value: Any) -> list[Any] | None:
    if not isinstance(value, list):
        return None
    result: list[Any] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {"const"}:
            return None
        result.append(item["const"])
    return result


def check_device_pairing_current_device_gate(lint: Lint) -> None:
    schema = load_json(lint, SCHEMA)
    if not isinstance(schema, dict):
        return
    definitions = schema.get("$defs")
    if not isinstance(definitions, dict):
        lint.fail(SCHEMA, "$defs must be an object")
        return

    denied = definitions.get("denied_actions")
    if not isinstance(denied, dict):
        lint.fail(SCHEMA, "missing denied_actions")
    else:
        values = _const_prefix_items(denied.get("prefixItems"))
        if values != EXPECTED_DENIED_ACTIONS:
            lint.fail(
                SCHEMA,
                "denied_actions must be the closed ordered set including device_pairing_code_claim",
            )
        if denied.get("minItems") != len(EXPECTED_DENIED_ACTIONS) or denied.get(
            "maxItems"
        ) != len(EXPECTED_DENIED_ACTIONS):
            lint.fail(SCHEMA, "denied_actions cardinality must equal its closed action set")

    action = definitions.get("gate_action_class")
    if not isinstance(action, dict) or action.get("enum") != EXPECTED_GATE_ACTIONS:
        lint.fail(
            SCHEMA,
            "gate_action_class must be the closed ordered set with a dedicated device_pairing_code_claim",
        )

    request = definitions.get("device_revocation_gate_check_request_body")
    if not isinstance(request, dict):
        lint.fail(SCHEMA, "missing device_revocation_gate_check_request_body")
    else:
        rules = request.get("allOf")
        if not isinstance(rules, list) or len(rules) < 2:
            lint.fail(SCHEMA, "current-device gate request must carry selector and proof conditionals")
        else:
            selector_omissions = (
                rules[0]
                .get("if", {})
                .get("properties", {})
                .get("action_class", {})
                .get("enum")
                if isinstance(rules[0], dict)
                else None
            )
            if selector_omissions != [
                "session_grant_issue",
                "returning_session_grant_issue",
            ]:
                lint.fail(
                    SCHEMA,
                    "only the two issue action classes may omit expected device selectors",
                )
            selector_required = (
                rules[0].get("else", {}).get("required")
                if isinstance(rules[0], dict)
                else None
            )
            if selector_required != [
                "expected_device_authorize_event_id",
                "expected_device_generation_ref",
            ]:
                lint.fail(
                    SCHEMA,
                    "device_pairing_code_claim must require both expected device selectors",
                )

            proof_classes = (
                rules[1]
                .get("if", {})
                .get("properties", {})
                .get("action_class", {})
                .get("enum")
                if isinstance(rules[1], dict)
                else None
            )
            if proof_classes != [
                "returning_session_grant_issue",
                "session_grant_refresh",
            ]:
                lint.fail(
                    SCHEMA,
                    "device_pairing_code_claim must not require AcceptedDevicePossessionProof",
                )
        description = request.get("description")
        if not isinstance(description, str) or not all(
            marker in description
            for marker in (ACTION_CLASS, "Standard SessionGrant", "DPoP", "event_write")
        ):
            lint.fail(
                SCHEMA,
                "current-device gate request description must close code-claim auth and class separation",
            )
        intent = request.get("properties", {}).get("intent_digest", {})
        intent_description = intent.get("description") if isinstance(intent, dict) else None
        if not isinstance(intent_description, str) or not all(
            marker in intent_description
            for marker in (ACTION_CLASS, "operation id", "AccountId", "plaintext pairing code")
        ):
            lint.fail(
                SCHEMA,
                "intent_digest must bind the canonical code-claim intent without disclosing plaintext code",
            )

    contract = load_json(lint, CONTRACT)
    if isinstance(contract, dict):
        for operation_id in (CLAIM_OPERATION, GATE_OPERATION):
            operation = _operation(contract, operation_id)
            if operation is None:
                lint.fail(CONTRACT, f"missing unique operation {operation_id}")
                continue
            notes = operation.get("notes")
            required = (
                ACTION_CLASS,
                GATE_OPERATION if operation_id == CLAIM_OPERATION else "event_write",
                "SessionGrant",
                "before",
            )
            if not isinstance(notes, str) or not all(marker in notes for marker in required):
                lint.fail(
                    CONTRACT,
                    f"{operation_id} notes do not close current-device gate ordering and class separation",
                )
            if operation_id == CLAIM_OPERATION and "single gate-side pending ledger" not in notes:
                lint.fail(CONTRACT, f"{operation_id} must keep one Account Authority pairing ledger")

    for path in (DEVICE_PROSE, BINDING_PROSE):
        source = read_text(path)
        for marker in (ACTION_CLASS, GATE_OPERATION, "event_write", "SessionGrant"):
            if marker not in source:
                lint.fail(path, f"code-claim current-device prose is missing {marker!r}")

    fixture = load_json(lint, FIXTURE)
    case = _vector_case(fixture) if isinstance(fixture, dict) else None
    if case is None:
        lint.fail(FIXTURE, f"missing unique fixture case {VECTOR_ID}")
    else:
        variants = case.get("variants")
        if not isinstance(variants, list) or not REQUIRED_VARIANTS.issubset(set(variants)):
            lint.fail(FIXTURE, "code-claim fixture is missing current-device gate negative variants")
        expected = case.get("expected")
        if not isinstance(expected, dict):
            lint.fail(FIXTURE, "code-claim fixture expected must be an object")
        else:
            if expected.get("current_device_gate_operation") != GATE_OPERATION:
                lint.fail(FIXTURE, "fixture current_device_gate_operation is not canonical")
            if expected.get("current_device_gate_action_class") != ACTION_CLASS:
                lint.fail(FIXTURE, "fixture current_device_gate_action_class is not dedicated")
            if expected.get("current_device_gate_order") != EXPECTED_ORDER:
                lint.fail(FIXTURE, "fixture current_device_gate_order is not the closed safe order")
            if expected.get("current_device_gate_failure") != (
                "fail_closed_before_pending_lookup_without_failure_budget_charge"
            ):
                lint.fail(FIXTURE, "fixture gate failure must precede lookup and budget charge")
        assertions = case.get("assertions")
        assertion_text = " ".join(assertions) if isinstance(assertions, list) else ""
        for marker in (ACTION_CLASS, GATE_OPERATION, "event_write", "single gate-side pending"):
            if marker not in assertion_text:
                lint.fail(FIXTURE, f"code-claim fixture assertions are missing {marker!r}")

    vectors = load_json(lint, VECTOR_REGISTRY)
    rows = vectors.get("vectors") if isinstance(vectors, dict) else None
    vector = next(
        (
            row
            for row in rows
            if isinstance(row, dict) and row.get("vector_id") == VECTOR_ID
        ),
        None,
    ) if isinstance(rows, list) else None
    description = vector.get("description") if isinstance(vector, dict) else None
    if not isinstance(description, str) or not all(
        marker in description
        for marker in (ACTION_CLASS, GATE_OPERATION, "event_write", "SessionGrant")
    ):
        lint.fail(VECTOR_REGISTRY, "code-claim vector does not state the current-device gate closure")
