"""Close the two-step Agent draft pending-intent and holder-CAS contract."""

from __future__ import annotations

from typing import Any

from .core import ARTIFACTS, SPEC_ROOT, Lint, load_json


CONTRACT = ARTIFACTS / "registry" / "contract-registry.json"
ACCOUNT_DATA = ARTIFACTS / "registry" / "account-data-key-registry.json"
EVENT_PAYLOAD = ARTIFACTS / "schemas" / "event-payload.schema.json"
PRIVATE_SCHEMA = ARTIFACTS / "schemas" / "agent-draft-private.schema.json"
VECTOR_REGISTRY = ARTIFACTS / "registry" / "vector-registry.json"
FIXTURE = ARTIFACTS / "fixtures" / "agent-draft-pending-intent-fixture.json"
PROSE = SPEC_ROOT / "zh" / "models" / "actor-private-effects.md"
EVENT_KIND = "ak.agent.draft.propose"
KEY_PATTERN = "ak.agent.draft.v1:<agent_id>:<draft_id>"
VECTOR_ID = "ak.vector.agent.draft_pending_intent.v1"


def _fail(lint: Lint, path: Any, message: str) -> None:
    lint.fail(path, f"agent draft pending intent: {message}")


def _find(rows: Any, key: str, value: str) -> dict[str, Any] | None:
    if not isinstance(rows, list):
        return None
    return next((row for row in rows if isinstance(row, dict) and row.get(key) == value), None)


def check_agent_draft_pending_intent(lint: Lint) -> None:
    contract = load_json(lint, CONTRACT)
    account_data = load_json(lint, ACCOUNT_DATA)
    payload = load_json(lint, EVENT_PAYLOAD)
    private_schema = load_json(lint, PRIVATE_SCHEMA)
    vectors = load_json(lint, VECTOR_REGISTRY)
    fixture = load_json(lint, FIXTURE)
    if not all(isinstance(value, dict) for value in (contract, account_data, payload, private_schema, vectors, fixture)):
        return

    event_registry = contract.get("event_kind_registry", {})
    event_row = _find(event_registry.get("event_kinds"), "event_kind", EVENT_KIND)
    effect = event_registry.get("actor_private_contracts", {}).get("event_writes", {}).get(EVENT_KIND)
    if not isinstance(event_row, dict) or event_row.get("wire_scope") != "actor_private_event" or event_row.get("reducer_input") is not False:
        _fail(lint, CONTRACT, "propose must remain actor_private_event with reducer_input=false")
    if not isinstance(effect, dict):
        _fail(lint, CONTRACT, "structured propose effect is missing")
        return
    if effect.get("result_family") != "ak.private.agent.draft_pending_intent.v1":
        _fail(lint, CONTRACT, "propose must own the pending-intent family, not the account-data value")
    owner = effect.get("storage_owner")
    if not isinstance(owner, dict) or owner.get("account_id_source") != "payload.controller_account_id" or owner.get("station_id_source") != "selected_account_id.station_id":
        _fail(lint, CONTRACT, "owner must be the exact controller Account Station")
    projection = effect.get("value_projection", {})
    if projection.get("kind") != "structured_pending_intent":
        _fail(lint, CONTRACT, "value projection must be structured_pending_intent")
    if projection.get("schema_ref") != "schemas/agent-draft-private.schema.json#/$defs/agent_draft_pending_intent":
        _fail(lint, CONTRACT, "pending value schema ref is missing or wrong")
    expected_targets = {
        "schema", "controller_account_id", "agent_id", "draft_id", "proposed_action",
        "target", "content_digest", "content_handoff", "expires_at", "created_at",
        "state", "accepted_event_id", "canonical_event_digest",
    }
    members = projection.get("members")
    targets = {
        member.get("target")
        for member in members or []
        if isinstance(member, dict)
    }
    if targets != expected_targets or len(members or []) != len(expected_targets):
        _fail(lint, CONTRACT, "pending value projection must map every closed schema member exactly once")
    lifecycle = effect.get("pending_intent_lifecycle")
    expected_lifecycle = {"reading", "content_handoff", "expiry", "consumption", "failure_recovery"}
    if not isinstance(lifecycle, dict) or set(lifecycle) != expected_lifecycle:
        _fail(lint, CONTRACT, "lifecycle must close reading, handoff, expiry, consumption and failure recovery")
    else:
        reading = lifecycle.get("reading", {})
        handoff = lifecycle.get("content_handoff", {})
        expiry = lifecycle.get("expiry", {})
        consumption = lifecycle.get("consumption", {})
        recovery = lifecycle.get("failure_recovery", {})
        if set(reading) != {"audience", "delivery_surface", "visible_value"} or "account subscribe" not in str(reading.get("delivery_surface")):
            _fail(lint, CONTRACT, "controller-only account-subscribe reading is not closed")
        if set(handoff) != {"producer", "recipient_key_source", "schema_ref", "plaintext_schema", "info_and_aad", "station_plaintext_access"} or handoff.get("station_plaintext_access") != "forbidden":
            _fail(lint, CONTRACT, "HPKE handoff and Station plaintext prohibition are not closed")
        if handoff.get("plaintext_schema") != "schemas/agent-draft-private.schema.json#/$defs/agent_draft_content_handoff_plaintext":
            _fail(lint, CONTRACT, "HPKE handoff plaintext schema ref is missing or wrong")
        if set(expiry) != {"comparison", "transition", "retention"} or "available -> expired" not in str(expiry.get("transition")):
            _fail(lint, CONTRACT, "expiry transition and retained occupied digest are not closed")
        if set(consumption) != {"trigger_event_kind", "source_field", "account_data_key", "preconditions", "atomic_effect"} or consumption.get("trigger_event_kind") != "ak.account_data.set" or consumption.get("source_field") != "payload.source_pending_event_id" or "no second counter" not in str(consumption.get("atomic_effect")):
            _fail(lint, CONTRACT, "holder CAS consumption must be uniquely bound and atomic")
        if set(recovery) != {"before_commit", "uncertain_outcome", "conflicting_retry"} or "rolls back" not in str(recovery.get("before_commit")):
            _fail(lint, CONTRACT, "failure recovery and exact retry are not closed")
    if effect.get("shared_realm_effect") != "none":
        _fail(lint, CONTRACT, "pending intent must not enter the shared reducer")

    key_row = _find(account_data.get("account_data_key_patterns"), "key_pattern", KEY_PATTERN)
    if not isinstance(key_row, dict):
        _fail(lint, ACCOUNT_DATA, "agent draft account-data row is missing")
    else:
        writers = key_row.get("write_event_kinds")
        if writers != ["ak.agent.action_approve", "ak.account_data.set"] or EVENT_KIND in (writers or []):
            _fail(lint, ACCOUNT_DATA, "writer allowlist must exclude propose and retain holder writers")
        if key_row.get("encrypted_value_schema") != "schemas/agent-draft-private.schema.json":
            _fail(lint, ACCOUNT_DATA, "encrypted plaintext schema is not registered")
        source = key_row.get("source_intent")
        if not isinstance(source, dict) or set(source) != {"event_kind", "contract_ref", "source_field", "required_for", "consume", "failure"} or source.get("event_kind") != EVENT_KIND or source.get("source_field") != "payload.source_pending_event_id" or source.get("consume") != "same_transaction_as_account_data_revision_1":
            _fail(lint, ACCOUNT_DATA, "source-intent gate is not structurally closed")

    defs = payload.get("$defs", {})
    propose = defs.get("agent_draft_propose_payload", {})
    account_set = defs.get("account_data_set_payload", {})
    if "content_handoff" not in propose.get("required", []) or "account_data_key" in propose.get("properties", {}):
        _fail(lint, EVENT_PAYLOAD, "propose must require content_handoff and must not choose an account-data key")
    if "source_pending_event_id" not in account_set.get("properties", {}) or not isinstance(account_set.get("allOf"), list):
        _fail(lint, EVENT_PAYLOAD, "account-data set must carry the conditional source pending Event id")

    private_defs = private_schema.get("$defs", {})
    pending = private_defs.get("agent_draft_pending_intent", {})
    value = private_defs.get("agent_draft_account_data_value", {})
    handoff_plaintext = private_defs.get("agent_draft_content_handoff_plaintext", {})
    if pending.get("properties", {}).get("state", {}).get("enum") != ["available", "consumed", "expired"]:
        _fail(lint, PRIVATE_SCHEMA, "pending state machine must be closed")
    if "source_pending_event_id" not in value.get("required", []) or value.get("properties", {}).get("schema", {}).get("const") != "ak.schema.agent_draft.v1":
        _fail(lint, PRIVATE_SCHEMA, "holder-created decrypted value must bind its source intent")
    if handoff_plaintext.get("properties", {}).get("schema", {}).get("const") != "ak.schema.agent_draft_content_handoff_plaintext.v1" or "content_digest" not in handoff_plaintext.get("required", []):
        _fail(lint, PRIVATE_SCHEMA, "HPKE handoff plaintext must be closed and digest-bound")

    vector = _find(vectors.get("vectors"), "vector_id", VECTOR_ID)
    if not isinstance(vector, dict) or vector.get("applies_to_fixtures") != ["agent-draft-pending-intent-fixture.json"]:
        _fail(lint, VECTOR_REGISTRY, "active vector row is missing")
    expected_cases = {
        "pending_intent_create_replay_conflict",
        "controller_read_and_content_handoff",
        "holder_cas_consumption_and_recovery",
        "expiry_and_retention",
    }
    cases = fixture.get("cases")
    case_names = {case.get("name") for case in cases or [] if isinstance(case, dict)}
    if fixture.get("covers_vectors") != [VECTOR_ID] or case_names != expected_cases:
        _fail(lint, FIXTURE, "fixture must cover all four closed lifecycle faces")
    consume_case = _find(cases, "name", "holder_cas_consumption_and_recovery")
    required_negative = {
        "account_data_cas_conflict",
        "failure_between_account_data_and_intent_transition",
        "proposal_used_as_account_data_writer",
        "pending_value_returned_as_account_data_current_value",
        "pending_intent_sent_to_shared_reducer",
    }
    if not isinstance(consume_case, dict) or not required_negative.issubset(set(consume_case.get("variants") or [])):
        _fail(lint, FIXTURE, "fixture omits rollback, boundary or shared-reducer mutations")

    prose = PROSE.read_text(encoding="utf-8") if PROSE.is_file() else ""
    for marker in (KEY_PATTERN, "source_pending_event_id", "取得 holder account secret", "account subscribe"):
        if marker not in prose:
            _fail(lint, PROSE, f"normative prose is missing {marker!r}")
