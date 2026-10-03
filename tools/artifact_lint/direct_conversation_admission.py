"""Close every active Direct Conversation admission reason over a real producer."""

from __future__ import annotations

from typing import Any

from .core import ARTIFACTS, ROOT, SPEC_ROOT, Lint, load_json, read_text


CONTRACT = ARTIFACTS / "registry" / "contract-registry.json"
OPERATIONS = ARTIFACTS / "registry" / "operation-registry.json"
ERRORS = ARTIFACTS / "registry" / "error-code-registry.json"
EVENTS = ARTIFACTS / "registry" / "event-kind-registry.json"
AUTHORITY = ARTIFACTS / "registry" / "authority-source-registry.json"
ACTIONS = ARTIFACTS / "registry" / "capability-action-registry.json"
VECTORS = ARTIFACTS / "registry" / "vector-registry.json"
SCHEMA = ARTIFACTS / "schemas" / "authority-commit-operations.schema.json"
RESOLVER_SCHEMA = ARTIFACTS / "schemas" / "direct-conversation-operations.schema.json"
FIXTURE = ARTIFACTS / "fixtures" / "direct-conversation-admission-fixture.json"
RUNTIME_FIXTURE = ARTIFACTS / "fixtures" / "direct-conversation-runtime-endpoint-repair-fixture.json"
SIGNAL_FIXTURE = ARTIFACTS / "fixtures" / "direct-conversation-signal-admission-fixture.json"
SIGNAL_SCHEMA = ARTIFACTS / "schemas" / "signal-envelope.schema.json"
SIGNAL_PROSE = SPEC_ROOT / "zh" / "sync" / "signal.md"
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


def _check_owned_agent_runtime_repair(lint: Lint, fixture: dict[str, Any]) -> None:
    contract = fixture.get("owned_agent_runtime_repair", {})
    invariants = {
        "membership_event_count": 0,
        "key_access_revision_delta": 0,
        "group_id_unchanged": True,
        "lifetime_binding_unchanged": True,
        "epoch_reset_allowed": False,
        "human_devices_collapsed_by_actor": False,
    }
    if contract.get("invariants") != invariants or contract.get("classification_only") is not True:
        lint.fail(RUNTIME_FIXTURE, "runtime repair must retain the same-group invariants and classification-only boundary")
    required_cases = {
        "rotated_runtime_without_membership_change", "same_key_new_authorization",
        "current_endpoint_already_present", "previous_leaf_already_removed", "paused_agent",
        "missing_current_authorization", "missing_fresh_claim", "controller_binding_revoked",
        "membership_inactive", "scope_gate_denies", "different_actor", "all_private_state_lost",
        "second_human_device",
    }
    cases = contract.get("cases", [])
    if {case.get("case_id") for case in cases} != required_cases or len(cases) != len(required_cases):
        lint.fail(RUNTIME_FIXTURE, "runtime repair must retain every scheduling and fail-closed case")
    base = contract.get("base_input", {})
    gates = ("controller_binding_current", "agent_active", "membership_current", "scope_gate_current",
             "runtime_authorization_current", "same_complete_actor")
    for case in cases:
        inputs = {**base, **case.get("mutations", {})}
        if inputs.get("target_endpoint_kind") == "human_device":
            plan = "independent_human_endpoint"
        elif not all(inputs.get(gate) is True for gate in gates):
            plan = "blocked"
        elif not inputs.get("private_state_available"):
            plan = "private_state_unavailable"
        elif inputs.get("current_endpoint_present"):
            plan = "no_change"
        elif not inputs.get("fresh_claim_valid"):
            plan = "blocked"
        else:
            plan = "remove_add_runtime" if inputs.get("previous_runtime_present") else "add_runtime"
        if case.get("expected_plan") != plan:
            lint.fail(RUNTIME_FIXTURE, f"runtime repair {case.get('case_id')} violates current endpoint/gate classification")
    source = read_text(PROSE)
    for marker in ("自有 Agent runtime 端点收敛（normative）", "不推进 `key_access_revision`",
                   "同一 human Actor 的不同 device 是独立 leaf", "owned_agent_runtime_repair"):
        if marker not in source:
            lint.fail(PROSE, f"runtime repair prose missing {marker!r}")


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
    expected_owner = {
        "semantic_owner": "current_governance_station",
        "self_ingress_role": "authenticate_producer_and_forward_exact_bytes_without_profile_admission",
        "authority_forward_branch": "ak.peer.events.command.submit.v1#authority_forward",
        "authority_outcome_relay": "return_exact_authority_outcome_without_second_admission",
        "committed_replica_role": "verify_source_commit_and_materialize_without_profile_admission_or_resigning",
    }
    for field, expected in expected_owner.items():
        if mapping.get(field) != expected:
            lint.fail(CONTRACT, f"Direct Conversation single-authority mapping drift: {field}")
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
        if rule.get("producer_role") != "current_governance_station":
            lint.fail(CONTRACT, f"{reason} must run only at current governance Station")
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
    if participant_rule.get("action_surface") != "event_mapped_only":
        lint.fail(CONTRACT, "Event participant reason must exclude encrypted Signal product actions")

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
    _check_owned_agent_runtime_repair(lint, load_json(lint, RUNTIME_FIXTURE) or {})
    if fixture.get("precedence") != list(REASONS):
        lint.fail(FIXTURE, "fixture precedence must match the canonical mapping")

    vectors = load_json(lint, VECTORS)
    vector_rows = vectors.get("vectors", []) if isinstance(vectors, dict) else []
    for reason, vector_id in VECTOR_IDS.items():
        row = _find(vector_rows, "vector_id", vector_id)
        if not isinstance(row, dict) or row.get("status") != "active" or row.get("applies_to_fixtures") != [FIXTURE.name]:
            lint.fail(VECTORS, f"{reason} must have one active dedicated vector bound to the fixture")
    participant_vector = _find(vector_rows, "vector_id", VECTOR_IDS["direct_conversation_participant_authority_denied"])
    if not isinstance(participant_vector, dict) or "spec/v1/artifacts/fixtures/" + RUNTIME_FIXTURE.name not in participant_vector.get("source_refs", []):
        lint.fail(VECTORS, "participant authority vector must retain the runtime endpoint repair fixture")

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


def check_direct_conversation_signal_admission(lint: Lint) -> None:
    contract = load_json(lint, CONTRACT)
    operation_registry = contract.get("operation_registry", {}) if isinstance(contract, dict) else {}
    mapping = operation_registry.get("direct_conversation_signal_admission_mappings", {})
    expected_actions = {"ak.call.signal.send", "ak.receipt.broadcast", "ak.typing.broadcast"}
    expected_stages = [
        ("source_local_ingress", "sender_account_station", "read_only_verified_governance_projection_plus_current_sender_device", "self_problem_or_eligible_enqueue"),
        ("source_outbound_recheck", "sender_account_station", "read_only_refreshed_governance_projection_plus_current_sender_device", "send_or_drop"),
        ("destination_peer_ingress", "recipient_account_station", "read_only_verified_governance_projection", "opaque_per_item_relay_or_drop"),
        ("recipient_delivery", "recipient_account_station", "read_only_refreshed_governance_projection_plus_current_recipient_and_sender_gate", "authenticated_frame_or_no_frame"),
    ]
    if mapping.get("profile") != "ak.profile.direct_conversation_realm.v1" or mapping.get("operation_id") != "ak.self.signal.command.send.v1":
        lint.fail(CONTRACT, "Signal admission must bind the Direct Conversation profile and self Signal operation")
    for field, expected in {
        "governance_writer": "current_governance_station_only",
        "governance_input": "verified_current_governance_station_committed_projection",
        "product_policy_owner": "recipient_after_decryption",
        "self_denial_carrier": "problem_details#signal_class_denied",
        "peer_denial_carrier": "opaque_per_item_drop",
        "delivery_denial_carrier": "no_authenticated_data_frame",
        "unknown_or_stale_rule": "fail_closed_bounded_pending_within_signal_ttl_then_drop_without_governance_write",
    }.items():
        if mapping.get(field) != expected:
            lint.fail(CONTRACT, f"Signal admission boundary drift: {field}")
    if set(mapping.get("encrypted_product_actions", [])) != expected_actions:
        lint.fail(CONTRACT, "Signal encrypted product action set must be complete")
    stages = mapping.get("freshness_stages", [])
    if [(x.get("stage"), x.get("owner"), x.get("state"), x.get("result")) for x in stages if isinstance(x, dict)] != expected_stages:
        lint.fail(CONTRACT, "Signal four read-only freshness stages must be exact")

    authority = load_json(lint, AUTHORITY)
    source = _find(authority.get("sources") if isinstance(authority, dict) else None, "authority_source_id", "ak.authority.direct_conversation_participant.v1") or {}
    actions_doc = load_json(lint, ACTIONS)
    action_rows = actions_doc.get("actions", []) if isinstance(actions_doc, dict) else []
    action_map = {row.get("action"): row.get("event_mapping_kind") for row in action_rows if isinstance(row, dict)}
    event_actions = set(source.get("event_action_allowlist", []))
    encrypted_actions = set(source.get("encrypted_signal_product_actions", []))
    if encrypted_actions != expected_actions or event_actions | encrypted_actions != set(source.get("action_allowlist", [])) or event_actions & encrypted_actions:
        lint.fail(AUTHORITY, "participant Event and encrypted Signal action partitions must cover the allowlist exactly")
    if any(action_map.get(action) == "non_event_surface" for action in event_actions) or any(action_map.get(action) != "non_event_surface" for action in encrypted_actions):
        lint.fail(ACTIONS, "participant action partitions must match capability action mapping kinds")
    if source.get("event_denial_operation_id") != OPERATION_ID or source.get("signal_product_evaluator") != "recipient_after_decryption_only":
        lint.fail(AUTHORITY, "participant denial and encrypted product owner must be separate")

    schema = load_json(lint, SIGNAL_SCHEMA)
    outer = set(schema.get("properties", {})) if isinstance(schema, dict) else set()
    if not set(mapping.get("outer_selectors", [])) or any(selector.split(".")[0] not in outer for selector in mapping.get("outer_selectors", [])):
        lint.fail(SIGNAL_SCHEMA, "Signal selectors must exist in outer envelope")
    if {"kind", "signal_kind", "target", "product_action"} & outer or schema.get("additionalProperties") is not False:
        lint.fail(SIGNAL_SCHEMA, "Signal exact product kind/target must remain encrypted and outer schema closed")
    errors = load_json(lint, ERRORS)
    code = _find(errors.get("codes") if isinstance(errors, dict) else None, "code", "signal_class_denied") or {}
    description = str(code.get("description", ""))
    if code.get("http_status") != 403 or "non-enumerating" not in description or "cannot inspect encrypted product kind" not in description:
        lint.fail(ERRORS, "signal_class_denied must describe only outer-visible non-enumerating failure")

    fixture = load_json(lint, SIGNAL_FIXTURE)
    cases = {row.get("case_id"): row for row in fixture.get("cases", []) if isinstance(row, dict)} if isinstance(fixture, dict) else {}
    authority_cases = {row.get("case_id"): row for row in fixture.get("event_authority_role_cases", []) if isinstance(row, dict)}
    if fixture.get("event_semantic_owner") != "current_governance_station" or authority_cases.get("edge_forwards_without_profile_admission", {}).get("profile_admission_count") != 0 or authority_cases.get("authority_evaluates_once", {}).get("profile_admission_count") != 1 or authority_cases.get("replica_materializes_without_readmission", {}).get("profile_admission_count") != 0 or authority_cases.get("replica_materializes_without_readmission", {}).get("realm_commit_sign_count") != 0:
        lint.fail(SIGNAL_FIXTURE, "self edge and replica must not repeat current-governance admission")
    if fixture.get("operation_id") != mapping.get("operation_id") or set(fixture.get("encrypted_product_actions", [])) != expected_actions:
        lint.fail(SIGNAL_FIXTURE, "Signal fixture must bind the operation and all encrypted product actions")
    for product, prefix in (("ak.typing.broadcast", "typing"), ("ak.receipt.broadcast", "receipt"), ("ak.call.signal.send", "call")):
        positive = cases.get(f"{prefix}_outer_valid", {})
        negative = cases.get(f"{prefix}_participant_revoked", {})
        if positive.get("product_action") != product or positive.get("expected") != "eligible_for_recipient_decryption" or negative.get("product_action") != product or negative.get("expected_self_problem") != "signal_class_denied" or negative.get("expected_peer") != "opaque_per_item_drop" or negative.get("expected_delivery") != "no_authenticated_data_frame":
            lint.fail(SIGNAL_FIXTURE, f"{product} requires positive and outer participant-failure cases")
    if cases.get("ciphertext_kind_invisible", {}).get("station_may_infer_product_action") is not False:
        lint.fail(SIGNAL_FIXTURE, "encrypted product kind must be invisible to Station")
    for case_id in ("queued_sender_revoked", "peer_projection_stale", "sender_revoked_before_delivery", "no_second_governance_ledger"):
        if case_id not in cases:
            lint.fail(SIGNAL_FIXTURE, f"Signal freshness case missing: {case_id}")
    vectors = load_json(lint, VECTORS)
    vector = _find(vectors.get("vectors") if isinstance(vectors, dict) else None, "vector_id", "ak.vector.direct_conversation.signal_admission.v1") or {}
    if vector.get("status") != "active" or vector.get("applies_to_fixtures") != [SIGNAL_FIXTURE.name]:
        lint.fail(VECTORS, "Signal admission vector must bind its fixture")
    if "四个 Station 时间边界" not in read_text(SIGNAL_PROSE) or "recipient_after_decryption" not in str(mapping):
        lint.fail(SIGNAL_PROSE, "Signal freshness and product-policy prose must be present")
    projected = load_json(lint, OPERATIONS)
    if projected.get("direct_conversation_signal_admission_mappings") != mapping:
        lint.fail(OPERATIONS, "generated operation registry must project Signal admission mappings")
    if "check_direct_conversation_signal_admission(lint)" not in read_text(RUNNER):
        lint.fail(RUNNER, "runner must invoke Direct Conversation Signal admission gate")
