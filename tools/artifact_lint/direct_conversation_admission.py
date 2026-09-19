"""Close every active Direct Conversation admission reason over a real producer."""

from __future__ import annotations

from typing import Any

from .core import ARTIFACTS, ROOT, SPEC_ROOT, Lint, load_json, read_text


CONTRACT = ARTIFACTS / "registry" / "contract-registry.json"
OPERATIONS = ARTIFACTS / "registry" / "operation-registry.json"
ERRORS = ARTIFACTS / "registry" / "error-code-registry.json"
EVENTS = ARTIFACTS / "registry" / "event-kind-registry.json"
AUTHORITY = ARTIFACTS / "registry" / "authority-source-registry.json"
VECTORS = ARTIFACTS / "registry" / "vector-registry.json"
SCHEMA = ARTIFACTS / "schemas" / "authority-commit-operations.schema.json"
RESOLVER_SCHEMA = ARTIFACTS / "schemas" / "direct-conversation-operations.schema.json"
FIXTURE = ARTIFACTS / "fixtures" / "direct-conversation-admission-fixture.json"
PROSE = SPEC_ROOT / "zh" / "identity" / "contact-and-direct-conversation.md"
VECTOR_PROSE = SPEC_ROOT / "zh" / "conformance" / "conformance-vectors.md"
REALM_PROSE = SPEC_ROOT / "zh" / "models" / "realm-and-space.md"
RUNNER = ROOT / "tools" / "artifact_lint" / "runner.py"

OPERATION_ID = "ak.self.events.command.submit.v1"
RESOLVE_OPERATION_ID = "ak.self.direct_conversation.read.resolve.v1"
REJECTION_SCHEMA_REF = "schemas/authority-commit-operations.schema.json#/$defs/submit_outcome"
REASONS = (
    "direct_conversation_binding_invalid",
    "direct_conversation_terminal_forbidden",
    "direct_conversation_member_count_invalid",
    "direct_conversation_third_party_member_forbidden",
    "direct_conversation_invite_forbidden",
    "direct_conversation_root_mask_violation",
    "direct_conversation_participant_authority_denied",
)
PATH_IDS = {
    "direct_conversation_binding_invalid": "ak.direct_conversation.admission.binding_integrity.v1",
    "direct_conversation_terminal_forbidden": "ak.direct_conversation.admission.terminal_guard.v1",
    "direct_conversation_member_count_invalid": "ak.direct_conversation.admission.exact_two_projection.v1",
    "direct_conversation_third_party_member_forbidden": "ak.direct_conversation.admission.third_party_member_guard.v1",
    "direct_conversation_invite_forbidden": "ak.direct_conversation.admission.invite_guard.v1",
    "direct_conversation_root_mask_violation": "ak.direct_conversation.admission.root_phase_mask.v1",
    "direct_conversation_participant_authority_denied": "ak.direct_conversation.admission.participant_authority.v1",
}
VECTOR_IDS = {
    reason: f"ak.vector.direct_conversation.admission.{reason.removeprefix('direct_conversation_')}.v1"
    for reason in REASONS
}
NEGATIVE_CASES = {
    "direct_conversation_binding_invalid": {
        "binding_wrong_pair_key_rejects",
        "binding_wrong_group_state_rejects",
    },
    "direct_conversation_terminal_forbidden": {"destroy_rejects", "tombstone_rejects"},
    "direct_conversation_member_count_invalid": {
        "zero_participants_rejects",
        "one_participant_rejects",
        "duplicate_participant_rejects",
        "three_participants_rejects",
        "binding_membership_disagreement_rejects",
    },
    "direct_conversation_third_party_member_forbidden": {
        "third_party_invite_rejects",
        "third_party_direct_join_rejects",
        "third_party_invite_dual_match_uses_third_party_reason",
    },
    "direct_conversation_invite_forbidden": {"pair_member_invite_rejects"},
    "direct_conversation_root_mask_violation": {
        "root_operational_action_rejects",
        "root_grant_action_rejects",
        "root_member_governance_action_rejects",
        "root_policy_action_rejects",
        "root_terminal_action_rejects",
    },
    "direct_conversation_participant_authority_denied": {
        "binding_input_missing_denies",
        "membership_input_missing_denies",
        "mls_cross_binding_missing_denies",
        "contact_input_missing_denies",
        "device_gate_missing_denies",
        "agent_gate_missing_denies",
        "consent_does_not_authorize",
        "owner_aggregation_does_not_authorize",
        "local_projection_does_not_authorize",
    },
}


def _find(rows: Any, field: str, value: str) -> dict[str, Any] | None:
    if not isinstance(rows, list):
        return None
    matches = [row for row in rows if isinstance(row, dict) and row.get(field) == value]
    return matches[0] if len(matches) == 1 else None


def _defs(document: Any) -> dict[str, Any]:
    return document.get("$defs", {}) if isinstance(document, dict) else {}


def check_direct_conversation_admission_producers(lint: Lint) -> None:
    contract = load_json(lint, CONTRACT)
    operation_registry = contract.get("operation_registry") if isinstance(contract, dict) else None
    mapping = operation_registry.get("direct_conversation_admission_mappings") if isinstance(operation_registry, dict) else None
    if not isinstance(mapping, dict):
        lint.fail(CONTRACT, "Direct Conversation admission mappings must be structured in operation_registry")
        return

    if mapping.get("profile") != "ak.profile.direct_conversation_realm.v1":
        lint.fail(CONTRACT, "Direct Conversation admission mapping must bind the canonical profile")
    if mapping.get("write_operation_id") != OPERATION_ID or mapping.get("write_request_event_path") != "/event":
        lint.fail(CONTRACT, "Direct Conversation rejection producer must be the ordinary single-Event submit path")
    if mapping.get("write_rejection_schema_ref") != REJECTION_SCHEMA_REF:
        lint.fail(CONTRACT, "Direct Conversation rejection mapping must use the existing submit_outcome carrier")
    if mapping.get("precedence") != list(REASONS):
        lint.fail(CONTRACT, "Direct Conversation rejection precedence must be complete and deterministic")
    for marker in ("zero", "RealmCommit", "outbox", "durable"):
        if marker not in str(mapping.get("transaction_rule", "")):
            lint.fail(CONTRACT, f"Direct Conversation zero-write transaction rule is missing {marker!r}")
    for marker in ("reevaluated", "cached"):
        if marker not in str(mapping.get("retry_rule", "")):
            lint.fail(CONTRACT, f"Direct Conversation retry rule is missing {marker!r}")

    operation = _find(operation_registry.get("operations"), "operation_id", OPERATION_ID)
    if not isinstance(operation, dict) or operation.get("response_schema_ref") != "schemas/authority-commit-operations.schema.json#/$defs/self_submit_outcome":
        lint.fail(CONTRACT, "ordinary self Event submit operation must retain its canonical response carrier")
    resolve_operation = _find(operation_registry.get("operations"), "operation_id", RESOLVE_OPERATION_ID)
    if not isinstance(resolve_operation, dict) or resolve_operation.get("response_schema_ref") != "schemas/direct-conversation-operations.schema.json#/$defs/direct_conversation_resolve_outcome":
        lint.fail(CONTRACT, "member-count read-side suspension must use the existing resolver")

    rules = mapping.get("rules")
    if not isinstance(rules, list) or len(rules) != len(REASONS):
        lint.fail(CONTRACT, "Direct Conversation admission mapping must contain exactly seven rules")
        rules = []
    rule_by_reason = {row.get("reason_code"): row for row in rules if isinstance(row, dict)}
    if set(rule_by_reason) != set(REASONS):
        lint.fail(CONTRACT, "Direct Conversation admission rules must cover each activated reason exactly once")

    events = load_json(lint, EVENTS)
    event_kinds = {
        row.get("event_kind") for row in events.get("event_kinds", []) if isinstance(row, dict)
    } if isinstance(events, dict) else set()
    for reason in REASONS:
        rule = rule_by_reason.get(reason)
        if not isinstance(rule, dict):
            continue
        if rule.get("producer_path_id") != PATH_IDS[reason]:
            lint.fail(CONTRACT, f"{reason} must retain its unique producer_path_id")
        if not isinstance(rule.get("stage"), str) or not rule.get("stage"):
            lint.fail(CONTRACT, f"{reason} must name an admission/evaluator stage")
        if not isinstance(rule.get("predicate"), str) or not rule.get("predicate"):
            lint.fail(CONTRACT, f"{reason} must carry a closed producer predicate")
        if not isinstance(rule.get("positive_case"), str) or not rule.get("positive_case"):
            lint.fail(CONTRACT, f"{reason} must name its positive fixture case")
        if set(rule.get("negative_cases", [])) != NEGATIVE_CASES[reason]:
            lint.fail(CONTRACT, f"{reason} must name every dedicated negative fixture case")
        for event_kind in rule.get("event_kinds", []):
            if event_kind != "*" and event_kind not in event_kinds:
                lint.fail(CONTRACT, f"{reason} names unknown Event kind {event_kind}")

    member_rule = rule_by_reason.get("direct_conversation_member_count_invalid", {})
    read_projection = member_rule.get("read_projection") if isinstance(member_rule, dict) else None
    if not isinstance(read_projection, dict) or read_projection.get("operation_id") != RESOLVE_OPERATION_ID or read_projection.get("state") != "suspended" or read_projection.get("blocker") != "member_count_invalid" or "no durable write" not in str(read_projection.get("rule", "")):
        lint.fail(CONTRACT, "member_count_invalid must separate read-only suspended projection from write rejection")

    participant_rule = rule_by_reason.get("direct_conversation_participant_authority_denied", {})
    if participant_rule.get("authority_source_id") != "ak.authority.direct_conversation_participant.v1" or "never identifies" not in str(participant_rule.get("privacy_rule", "")):
        lint.fail(CONTRACT, "participant denial must bind the registered evaluator and remain non-enumerating")

    authority = load_json(lint, AUTHORITY)
    participant_source = _find(authority.get("sources") if isinstance(authority, dict) else None, "authority_source_id", "ak.authority.direct_conversation_participant.v1")
    if not isinstance(participant_source, dict) or participant_source.get("denial_reason_code") != "direct_conversation_participant_authority_denied" or participant_source.get("denial_privacy") != "collapse_all_failed_activation_checks_without_naming_the_failed_input":
        lint.fail(AUTHORITY, "participant authority projection must carry its closed non-enumerating denial mapping")

    errors = load_json(lint, ERRORS)
    error_rows = errors.get("reason_codes", []) if isinstance(errors, dict) else []
    for reason in REASONS:
        row = _find(error_rows, "code", reason)
        if not isinstance(row, dict) or row.get("status") != "active" or "activation_condition" in row:
            lint.fail(ERRORS, f"{reason} must be active only after its producer closure lands")

    schema = load_json(lint, SCHEMA)
    submit_outcome = _defs(schema).get("submit_outcome")
    variants = submit_outcome.get("oneOf") if isinstance(submit_outcome, dict) else None
    rejection = next((row for row in variants or [] if row.get("properties", {}).get("status", {}).get("enum") == ["rejected", "retryable_unavailable"]), None)
    if not isinstance(rejection, dict) or rejection.get("required") != ["status", "reason_code"] or rejection.get("additionalProperties") is not False:
        lint.fail(SCHEMA, "submit_outcome must retain the closed rejection carrier")
    resolver = load_json(lint, RESOLVER_SCHEMA)
    blockers = _defs(resolver).get("direct_conversation_send_blocker", {}).get("enum", [])
    if "member_count_invalid" not in blockers:
        lint.fail(RESOLVER_SCHEMA, "resolver blocker enum must carry member_count_invalid")

    fixture = load_json(lint, FIXTURE)
    if not isinstance(fixture, dict) or fixture.get("write_operation_id") != OPERATION_ID or fixture.get("write_outcome_schema_ref") != REJECTION_SCHEMA_REF:
        lint.fail(FIXTURE, "Direct Conversation fixture must bind the real write operation and carrier")
        fixture = {}
    fixture_rules = fixture.get("rules", []) if isinstance(fixture, dict) else []
    fixture_by_reason = {row.get("reason_code"): row for row in fixture_rules if isinstance(row, dict)}
    if set(fixture_by_reason) != set(REASONS):
        lint.fail(FIXTURE, "Direct Conversation fixture must contain seven independent rule groups")
    for reason in REASONS:
        row = fixture_by_reason.get(reason)
        if not isinstance(row, dict) or row.get("producer_path_id") != PATH_IDS[reason]:
            lint.fail(FIXTURE, f"{reason} fixture must bind its unique producer path")
            continue
        positive = row.get("positive")
        if not isinstance(positive, dict) or positive.get("case_id") != rule_by_reason.get(reason, {}).get("positive_case"):
            lint.fail(FIXTURE, f"{reason} fixture must retain its dedicated positive case")
        negatives = row.get("negative")
        case_ids = {case.get("case_id") for case in negatives or [] if isinstance(case, dict)}
        if case_ids != NEGATIVE_CASES[reason]:
            lint.fail(FIXTURE, f"{reason} fixture must retain every exact-reason negative case")
        for case in negatives or []:
            if not isinstance(case, dict) or case.get("expected_reason_code") != reason:
                lint.fail(FIXTURE, f"{reason} negative cases must emit the exact reason")
    zero = fixture.get("all_rejections", {}) if isinstance(fixture, dict) else {}
    for field in ("realm_commit_count", "event_write_count", "projection_write_count", "outbox_write_count", "durable_effect_count"):
        if zero.get(field) != 0:
            lint.fail(FIXTURE, f"all Direct Conversation rejections must keep {field}=0")
    if fixture.get("precedence") != list(REASONS):
        lint.fail(FIXTURE, "fixture precedence must match the canonical mapping")

    vectors = load_json(lint, VECTORS)
    vector_rows = vectors.get("vectors", []) if isinstance(vectors, dict) else []
    for reason, vector_id in VECTOR_IDS.items():
        row = _find(vector_rows, "vector_id", vector_id)
        if not isinstance(row, dict) or row.get("status") != "active" or row.get("applies_to_fixtures") != [FIXTURE.name]:
            lint.fail(VECTORS, f"{reason} must have one active dedicated vector bound to the fixture")

    for path, markers in {
        PROSE: ("8.4 admission reason producer", "direct_conversation_third_party_member_forbidden", "全部保持零写入"),
        VECTOR_PROSE: ("ak.vector.direct_conversation.admission.", "逐项执行", "双重命中"),
        REALM_PROSE: ("这里必须区分三件事", "pair 外 invite/join", "pair 内 active-DM invite", "direct_conversation_third_party_member_forbidden", "direct_conversation_invite_forbidden"),
    }.items():
        source = read_text(path)
        for marker in markers:
            if marker not in source:
                lint.fail(path, f"Direct Conversation producer prose is missing {marker!r}")

    operations = load_json(lint, OPERATIONS)
    projected = operations.get("direct_conversation_admission_mappings") if isinstance(operations, dict) else None
    if projected != mapping:
        lint.fail(OPERATIONS, "generated operation registry must project the canonical admission mappings")
    if "check_direct_conversation_admission_producers(lint)" not in read_text(RUNNER):
        lint.fail(RUNNER, "runner must invoke the Direct Conversation admission producer gate")
