"""Close the two-step Agent draft pending-intent and holder-CAS contract."""

from __future__ import annotations

import base64
import hashlib
from typing import Any

from .core import ARTIFACTS, SPEC_ROOT, Lint, load_json


CONTRACT = ARTIFACTS / "registry" / "contract-registry.json"
ACCOUNT_DATA = ARTIFACTS / "registry" / "account-data-key-registry.json"
EVENT_PAYLOAD = ARTIFACTS / "schemas" / "event-payload.schema.json"
PRIVATE_SCHEMA = ARTIFACTS / "schemas" / "agent-draft-private.schema.json"
ACCOUNT_SUBSCRIBE = ARTIFACTS / "schemas" / "account-subscribe-frame.schema.json"
VECTOR_REGISTRY = ARTIFACTS / "registry" / "vector-registry.json"
PROOF_CONTEXT = ARTIFACTS / "registry" / "proof-context-registry.json"
FIXTURE = ARTIFACTS / "fixtures" / "agent-draft-pending-intent-fixture.json"
PROSE = SPEC_ROOT / "zh" / "models" / "actor-private-effects.md"
CLIENT_SYNC_PROSE = SPEC_ROOT / "zh" / "sync" / "client-sync.md"
EVENT_KIND = "ak.agent.draft.propose"
KEY_PATTERN = "ak.agent.draft.v1:<agent_id_sha256_b64u43>:<draft_id_sha256_b64u43>"
KEY_SCHEMA_REF = "schemas/agent-draft-private.schema.json#/$defs/agent_draft_account_data_key"
KEY_REGEX = r"^ak\.agent\.draft\.v1:[A-Za-z0-9_-]{42}[AEIMQUYcgkosw048]:[A-Za-z0-9_-]{42}[AEIMQUYcgkosw048]$"
CONSTRUCTION = "domain_prefixed_utf8_literal_sha256"
AGENT_DOMAIN = "ak.agent-draft.account-data-key.agent-id.v1"
DRAFT_DOMAIN = "ak.agent-draft.account-data-key.draft-id.v1"
VECTOR_ID = "ak.vector.agent.draft_pending_intent.v1"


def _fail(lint: Lint, path: Any, message: str) -> None:
    lint.fail(path, f"agent draft pending intent: {message}")


def _find(rows: Any, key: str, value: str) -> dict[str, Any] | None:
    if not isinstance(rows, list):
        return None
    return next((row for row in rows if isinstance(row, dict) and row.get(key) == value), None)


def _component(domain: str, literal: str) -> tuple[str, str, str, str]:
    prefix = (domain + "\n").encode("utf-8")
    literal_bytes = literal.encode("utf-8")
    digest = hashlib.sha256(prefix + literal_bytes).digest()
    encoded = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return prefix.hex(), literal_bytes.hex(), digest.hex(), encoded


def check_agent_draft_pending_intent(lint: Lint) -> None:
    contract = load_json(lint, CONTRACT)
    account_data = load_json(lint, ACCOUNT_DATA)
    payload = load_json(lint, EVENT_PAYLOAD)
    private_schema = load_json(lint, PRIVATE_SCHEMA)
    account_subscribe = load_json(lint, ACCOUNT_SUBSCRIBE)
    vectors = load_json(lint, VECTOR_REGISTRY)
    proof_context = load_json(lint, PROOF_CONTEXT)
    fixture = load_json(lint, FIXTURE)
    if not all(isinstance(value, dict) for value in (contract, account_data, payload, private_schema, account_subscribe, vectors, proof_context, fixture)):
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
        if set(consumption) != {"trigger_event_kind", "source_field", "account_data_key", "preconditions", "atomic_effect"} or consumption.get("trigger_event_kind") != "ak.account_data.set" or consumption.get("source_field") != "payload.source_pending_event_id" or consumption.get("account_data_key") != KEY_PATTERN or "no second counter" not in str(consumption.get("atomic_effect")):
            _fail(lint, CONTRACT, "holder CAS consumption must be uniquely bound and atomic")
        preconditions = str(consumption.get("preconditions", ""))
        for marker in ("recomputes", "SHA-256", "source row's exact agent_id and draft_id", "no reverse decoding", "caller-supplied selector"):
            if marker not in preconditions:
                _fail(lint, CONTRACT, f"holder CAS source binding omits {marker!r}")
        if set(recovery) != {"before_commit", "uncertain_outcome", "conflicting_retry"} or "rolls back" not in str(recovery.get("before_commit")):
            _fail(lint, CONTRACT, "failure recovery and exact retry are not closed")
    if effect.get("shared_realm_effect") != "none":
        _fail(lint, CONTRACT, "pending intent must not enter the shared reducer")
    frame_contract_row = _find(
        contract.get("schema_registry", {}).get("schemas", []),
        "schema_id",
        "ak.schema.account_subscribe_frame.v1",
    )
    subscribe_projection = frame_contract_row.get("channel_contract") if isinstance(frame_contract_row, dict) else None
    expected_projection_keys = {
        "top_level_field", "baseline_channel", "container_schema_ref", "item_schema_ref",
        "stable_key", "authorization", "paging", "limits", "state_projection", "forbidden_carriers",
    }
    if not isinstance(subscribe_projection, dict) or set(subscribe_projection) != expected_projection_keys:
        _fail(lint, CONTRACT, "dedicated account-subscribe projection contract must be structurally closed")
    else:
        if subscribe_projection.get("top_level_field") != "agent_draft_pending_intents" or subscribe_projection.get("baseline_channel") != "agent_draft_pending_intents":
            _fail(lint, CONTRACT, "pending intent must use its dedicated top-level field and baseline channel")
        if subscribe_projection.get("container_schema_ref") != "schemas/account-subscribe-frame.schema.json#/$defs/agent_draft_pending_intent_container" or subscribe_projection.get("item_schema_ref") != "schemas/account-subscribe-frame.schema.json#/$defs/agent_draft_pending_intent_change":
            _fail(lint, CONTRACT, "pending-intent container and ordered change item refs must be exact")
        if subscribe_projection.get("stable_key") != ["controller_account_id", "agent_id", "draft_id"]:
            _fail(lint, CONTRACT, "pending-intent projection stable key must be exact and ordered")
        authorization = subscribe_projection.get("authorization", {})
        if authorization.get("allow") != "authenticated active device of exact controller_account_id" or set(authorization.get("deny", [])) != {"agent_session", "foreign_account", "target_realm_member", "federation_peer"} or "every baseline page and delta" not in str(authorization.get("recheck", "")):
            _fail(lint, CONTRACT, "controller active-device allow and forbidden audiences are not closed")
        paging = subscribe_projection.get("paging", {})
        if set(paging) != {"snapshot_cut", "page_offset", "completion", "delta_position", "resync"} or "next_page_offset=null" not in str(paging.get("completion", "")) or "never clear" not in str(paging.get("resync", "")):
            _fail(lint, CONTRACT, "baseline cut, offset, completion, delta position and resync are not closed")
        if subscribe_projection.get("limits") != {
            "max_items_per_frame": 100,
            "max_canonical_item_bytes": 1048576,
            "max_canonical_frame_bytes": 8388608,
            "max_round_bytes": 16777216,
        }:
            _fail(lint, CONTRACT, "pending-intent item/frame/round budgets are not exact")
        state_projection = subscribe_projection.get("state_projection", {})
        if set(state_projection) != {"live_schema_ref", "terminal_redacted_schema_ref", "removal_schema_ref", "no_resurrection"} or "prevent" not in str(state_projection.get("no_resurrection", "")):
            _fail(lint, CONTRACT, "live/terminal/removal projection and no-resurrection rule are not closed")
        if set(subscribe_projection.get("forbidden_carriers", [])) != {"account_data.events", "account_data.station_cas", "notifications", "to_device"}:
            _fail(lint, CONTRACT, "pending intent must not reuse an existing account channel")

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
        encoding = key_row.get("key_encoding")
        expected_encoding_keys = {
            "kind", "schema_ref", "literal_prefix", "separator", "total_length",
            "component_order", "components", "builder", "parser", "source_binding",
        }
        if not isinstance(encoding, dict) or set(encoding) != expected_encoding_keys:
            _fail(lint, ACCOUNT_DATA, "key encoding contract must be structurally closed")
        else:
            if encoding.get("kind") != "two_domain_separated_sha256_components" or encoding.get("schema_ref") != KEY_SCHEMA_REF or encoding.get("literal_prefix") != "ak.agent.draft.v1:" or encoding.get("separator") != ":" or encoding.get("total_length") != 105 or encoding.get("component_order") != ["agent_id", "draft_id"]:
                _fail(lint, ACCOUNT_DATA, "key encoding prefix, order, schema and fixed length are not canonical")
            components = encoding.get("components", {})
            component_contracts = {
                "agent_id": ("pending_intent.agent_id", "schemas/common-ids.schema.json#/$defs/did_core_id", AGENT_DOMAIN, "canonical agent_id"),
                "draft_id": ("pending_intent.draft_id", "schemas/event-payload.schema.json#/$defs/agent_draft_propose_payload/properties/draft_id", DRAFT_DOMAIN, "draft_id"),
            }
            if not isinstance(components, dict) or set(components) != set(component_contracts):
                _fail(lint, ACCOUNT_DATA, "key encoding must define exactly agent_id and draft_id components")
            else:
                for name, (source_name, schema_ref, domain, literal) in component_contracts.items():
                    component = components.get(name, {})
                    if set(component) != {"source", "source_schema_ref", "digest_construction", "domain", "transcript", "output"} or component.get("source") != source_name or component.get("source_schema_ref") != schema_ref or component.get("digest_construction") != CONSTRUCTION or component.get("domain") != domain or f"UTF8({literal})" not in str(component.get("transcript")) or "exactly 43" not in str(component.get("output")):
                        _fail(lint, ACCOUNT_DATA, f"{name} digest component is not canonical and domain-separated")
            encoding_text = " ".join(str(encoding.get(name, "")) for name in ("builder", "parser", "source_binding"))
            for marker in ("without padding", "decode/re-encode equality", "source_pending_event_id", "never accept a caller-supplied"):
                if marker not in encoding_text:
                    _fail(lint, ACCOUNT_DATA, f"builder/parser/source binding omits {marker!r}")

    defs = payload.get("$defs", {})
    propose = defs.get("agent_draft_propose_payload", {})
    account_set = defs.get("account_data_set_payload", {})
    if "content_handoff" not in propose.get("required", []) or "account_data_key" in propose.get("properties", {}):
        _fail(lint, EVENT_PAYLOAD, "propose must require content_handoff and must not choose an account-data key")
    if "source_pending_event_id" not in account_set.get("properties", {}) or not isinstance(account_set.get("allOf"), list):
        _fail(lint, EVENT_PAYLOAD, "account-data set must carry the conditional source pending Event id")
    source_branches = account_set.get("allOf") or []
    source_key_ref = None
    for branch in source_branches:
        then = branch.get("then", {}) if isinstance(branch, dict) else {}
        if "source_pending_event_id" in (branch.get("if", {}).get("required", []) if isinstance(branch, dict) else []):
            source_key_ref = then.get("properties", {}).get("key", {}).get("$ref")
    if source_key_ref != "./agent-draft-private.schema.json#/$defs/agent_draft_account_data_key":
        _fail(lint, EVENT_PAYLOAD, "source-pending branch must reuse the canonical digest-key schema")

    private_defs = private_schema.get("$defs", {})
    pending = private_defs.get("agent_draft_pending_intent", {})
    pending_live = private_defs.get("agent_draft_pending_intent_live", {})
    pending_terminal = private_defs.get("agent_draft_pending_intent_terminal_redacted", {})
    value = private_defs.get("agent_draft_account_data_value", {})
    handoff_plaintext = private_defs.get("agent_draft_content_handoff_plaintext", {})
    key_schema = private_defs.get("agent_draft_account_data_key", {})
    if pending.get("oneOf") != [
        {"$ref": "#/$defs/agent_draft_pending_intent_live"},
        {"$ref": "#/$defs/agent_draft_pending_intent_terminal_redacted"},
    ]:
        _fail(lint, PRIVATE_SCHEMA, "pending intent must be the exact closed live | terminal-redacted union")
    common_required = {
        "schema", "controller_account_id", "agent_id", "draft_id", "proposed_action", "target",
        "content_digest", "canonical_event_digest", "accepted_event_id", "expires_at", "created_at", "state",
    }
    if set(pending_live.get("required", [])) != common_required | {"content_handoff"} or pending_live.get("properties", {}).get("state") != {"const": "available"} or pending_live.get("additionalProperties") is not False:
        _fail(lint, PRIVATE_SCHEMA, "live pending intent must be closed, available and require content_handoff")
    terminal_properties = pending_terminal.get("properties", {})
    if set(pending_terminal.get("required", [])) != common_required or "content_handoff" in terminal_properties or pending_terminal.get("additionalProperties") is not False:
        _fail(lint, PRIVATE_SCHEMA, "terminal-redacted intent must preserve identity/source/digests/expiry and forbid ciphertext")
    if terminal_properties.get("state", {}).get("enum") != ["consumed", "expired"] or set(terminal_properties) != common_required | {"consumption", "expired_at"}:
        _fail(lint, PRIVATE_SCHEMA, "terminal-redacted state and terminal metadata fields must be exact")
    terminal_branches = pending_terminal.get("oneOf")
    if not isinstance(terminal_branches, list) or len(terminal_branches) != 2 or {branch.get("properties", {}).get("state", {}).get("const") for branch in terminal_branches if isinstance(branch, dict)} != {"consumed", "expired"}:
        _fail(lint, PRIVATE_SCHEMA, "terminal-redacted union must require exact consumed or expired metadata")
    if "source_pending_event_id" not in value.get("required", []) or value.get("properties", {}).get("schema", {}).get("const") != "ak.schema.agent_draft.v1":
        _fail(lint, PRIVATE_SCHEMA, "holder-created decrypted value must bind its source intent")
    if handoff_plaintext.get("properties", {}).get("schema", {}).get("const") != "ak.schema.agent_draft_content_handoff_plaintext.v1" or "content_digest" not in handoff_plaintext.get("required", []):
        _fail(lint, PRIVATE_SCHEMA, "HPKE handoff plaintext must be closed and digest-bound")
    if key_schema.get("minLength") != 105 or key_schema.get("maxLength") != 105 or key_schema.get("pattern") != KEY_REGEX:
        _fail(lint, PRIVATE_SCHEMA, "draft account-data key must be a fixed 105-character canonical digest key")
    consumption_key = private_defs.get("pending_intent_consumption", {}).get("properties", {}).get("account_data_key", {})
    if consumption_key != {"$ref": "#/$defs/agent_draft_account_data_key"}:
        _fail(lint, PRIVATE_SCHEMA, "pending consumption must directly reuse the canonical digest-key schema")

    subscribe_properties = account_subscribe.get("properties", {})
    if subscribe_properties.get("agent_draft_pending_intents", {}).get("$ref") != "#/$defs/agent_draft_pending_intent_container":
        _fail(lint, ACCOUNT_SUBSCRIBE, "dedicated pending-intent top-level container is missing")
    subscribe_defs = account_subscribe.get("$defs", {})
    container = subscribe_defs.get("agent_draft_pending_intent_container", {})
    if container.get("oneOf") != [
        {"$ref": "#/$defs/agent_draft_pending_intent_delta_container"},
        {"$ref": "#/$defs/agent_draft_pending_intent_baseline_container"},
    ]:
        _fail(lint, ACCOUNT_SUBSCRIBE, "pending-intent container must be a closed baseline | delta union")
    for name in ("agent_draft_pending_intent_delta_container", "agent_draft_pending_intent_baseline_container"):
        branch = subscribe_defs.get(name, {})
        if branch.get("additionalProperties") is not False:
            _fail(lint, ACCOUNT_SUBSCRIBE, f"{name} must remain closed")
        items = branch.get("properties", {}).get("items", {})
        if items.get("maxItems") != 100 or items.get("items", {}).get("$ref") != "#/$defs/agent_draft_pending_intent_change":
            _fail(lint, ACCOUNT_SUBSCRIBE, f"{name}.items must retain one combined 100-change bound")
        if "items" not in branch.get("required", []) or {"upserts", "removals"} & set(branch.get("properties", {})):
            _fail(lint, ACCOUNT_SUBSCRIBE, f"{name} must use only the combined items change array")
    change = subscribe_defs.get("agent_draft_pending_intent_change", {})
    if change.get("oneOf") != [
        {"$ref": "#/$defs/agent_draft_pending_intent_upsert"},
        {"$ref": "#/$defs/agent_draft_pending_intent_remove"},
    ]:
        _fail(lint, ACCOUNT_SUBSCRIBE, "pending-intent changes must be the exact upsert | remove union")
    expected_change_shapes = {
        "agent_draft_pending_intent_upsert": (
            "upsert",
            "./agent-draft-private.schema.json#/$defs/agent_draft_pending_intent",
        ),
        "agent_draft_pending_intent_remove": (
            "remove",
            "#/$defs/agent_draft_pending_intent_removal",
        ),
    }
    for name, (action, value_ref) in expected_change_shapes.items():
        branch = subscribe_defs.get(name, {})
        if (
            branch.get("additionalProperties") is not False
            or set(branch.get("required", [])) != {"action", "value"}
            or set(branch.get("properties", {})) != {"action", "value"}
            or branch.get("properties", {}).get("action") != {"const": action}
            or branch.get("properties", {}).get("value") != {"$ref": value_ref}
        ):
            _fail(lint, ACCOUNT_SUBSCRIBE, f"{name} must remain a closed action/value branch")
    baseline_container = subscribe_defs.get("agent_draft_pending_intent_baseline_container", {})
    if not {"snapshot_cut_position", "page_offset", "next_page_offset"}.issubset(set(baseline_container.get("required", []))):
        _fail(lint, ACCOUNT_SUBSCRIBE, "pending baseline must require frozen cut and page offsets")
    delta_container = subscribe_defs.get("agent_draft_pending_intent_delta_container", {})
    if "projection_position" not in delta_container.get("required", []):
        _fail(lint, ACCOUNT_SUBSCRIBE, "pending delta must require its independent projection position")
    baseline = subscribe_defs.get("account_baseline_segment", {})
    for field in ("channels", "completed_channels"):
        definition = baseline.get("properties", {}).get(field, {})
        enum = definition.get("items", {}).get("enum", [])
        if definition.get("maxItems") != 5 or set(enum) != {"account_data_events", "station_cas", "device_lists", "notifications", "agent_draft_pending_intents"}:
            _fail(lint, ACCOUNT_SUBSCRIBE, f"{field} must expose exactly five global channels")
    if "channel_offsets" in baseline.get("properties", {}) or "channel_offsets" in baseline.get("required", []):
        _fail(lint, ACCOUNT_SUBSCRIBE, "pending-intent paging must not impose a second universal baseline offset map")

    schema_rows = contract.get("schema_registry", {}).get("schemas", [])
    frame_row = _find(schema_rows, "schema_id", "ak.schema.account_subscribe_frame.v1")
    sdk = frame_row.get("sdk_projection") if isinstance(frame_row, dict) else None
    if not isinstance(sdk, dict) or sdk.get("frame_type") != "AccountSubscribeFrame" or sdk.get("baseline_channel_enum_type") != "AccountBaselineChannel" or sdk.get("baseline_channel_variant") != "AgentDraftPendingIntents" or sdk.get("pending_intent_variants") != ["Live", "TerminalRedacted"] or sdk.get("change_type") != "AgentDraftPendingIntentChange" or sdk.get("change_variants") != ["Upsert", "Remove"]:
        _fail(lint, CONTRACT, "SDK frame/container/channel/pending-intent projection is not closed")

    construction = _find(proof_context.get("digest_constructions"), "construction_id", CONSTRUCTION)
    if not isinstance(construction, dict):
        _fail(lint, PROOF_CONTEXT, "registered UTF-8 literal digest construction is missing")
    else:
        expected = {
            "canonicalization": "schema-validated canonical literal encoded directly as UTF-8; no JCS, normalization, truncation or decoding fallback",
            "digest_suite": "SHA-256",
            "prefix_form": "UTF8(domain + LF)",
            "digest_input": "UTF8(domain + LF) || UTF8(canonical_literal)",
            "digest_encoding": "base64url_no_pad of the complete 32-byte digest, exactly 43 ASCII characters",
        }
        if construction.get("applies_to_primitives") != ["utf8_literal_sha256"] or any(construction.get(key) != value for key, value in expected.items()):
            _fail(lint, PROOF_CONTEXT, "registered UTF-8 literal digest construction drifted")

    vector = _find(vectors.get("vectors"), "vector_id", VECTOR_ID)
    if not isinstance(vector, dict) or vector.get("applies_to_fixtures") != ["agent-draft-pending-intent-fixture.json"]:
        _fail(lint, VECTOR_REGISTRY, "active vector row is missing")
    elif "agent_draft_pending_intents" not in str(vector.get("description", "")) or "spec/v1/zh/sync/client-sync.md" not in set(vector.get("source_refs", [])):
        _fail(lint, VECTOR_REGISTRY, "active vector must cover the dedicated sync channel")
    expected_cases = {
        "pending_intent_create_replay_conflict",
        "controller_read_and_content_handoff",
        "holder_cas_consumption_and_recovery",
        "expiry_and_retention",
        "account_subscribe_projection",
    }
    cases = fixture.get("cases")
    case_names = {case.get("name") for case in cases or [] if isinstance(case, dict)}
    if fixture.get("covers_vectors") != [VECTOR_ID] or case_names != expected_cases:
        _fail(lint, FIXTURE, "fixture must cover all five closed lifecycle and sync faces")
    consume_case = _find(cases, "name", "holder_cas_consumption_and_recovery")
    required_negative = {
        "account_data_cas_conflict",
        "failure_between_account_data_and_intent_transition",
        "proposal_used_as_account_data_writer",
        "pending_value_returned_as_account_data_current_value",
        "pending_intent_sent_to_shared_reducer",
    }
    required_key_variants = {
        "initial_create_canonical_digest_key",
        "padded_key_component",
        "wrong_key_component_length",
        "noncanonical_key_component_trailing_bits",
        "wrong_key_prefix_or_extra_separator",
        "old_literal_agent_draft_key",
        "wrong_digest_domain",
        "caller_supplied_decoded_selector",
    }
    if not isinstance(consume_case, dict) or not (required_negative | required_key_variants).issubset(set(consume_case.get("variants") or [])):
        _fail(lint, FIXTURE, "fixture omits rollback, boundary or shared-reducer mutations")
    projection_case = _find(cases, "name", "account_subscribe_projection")
    required_projection_variants = {
        "initial_baseline_first_page_available", "initial_baseline_terminal_page_completed",
        "cursor_delta_available_upsert", "cursor_delta_consumed_redacted_upsert",
        "cursor_delta_expired_redacted_upsert", "terminal_metadata_retention_removal",
        "stale_available_after_terminal", "resync_rebuilds_only_pending_intent_channel",
        "active_controller_device_allowed", "agent_session_denied", "foreign_account_denied",
        "target_realm_member_denied", "federation_peer_denied", "account_data_events_carrier_rejected",
        "station_cas_carrier_rejected", "notification_carrier_rejected", "to_device_carrier_rejected",
    }
    if not isinstance(projection_case, dict) or set(projection_case.get("variants") or []) != required_projection_variants:
        _fail(lint, FIXTURE, "fixture must close baseline/delta/redaction/authz/forbidden-carrier variants")
    required_schema_cases = {
        "agent_draft_pending_intent_live_available_valid",
        "agent_draft_pending_intent_live_missing_handoff_rejected",
        "agent_draft_pending_intent_available_redacted_branch_rejected",
        "agent_draft_pending_intent_consumed_redacted_valid",
        "agent_draft_pending_intent_terminal_ciphertext_rejected",
        "agent_draft_pending_intent_terminal_missing_source_rejected",
        "agent_draft_pending_intent_consumed_missing_metadata_rejected",
        "agent_draft_pending_intent_expired_redacted_valid",
        "agent_draft_pending_intent_expired_missing_metadata_rejected",
        "agent_draft_pending_intent_baseline_segment_valid",
        "agent_draft_pending_intent_baseline_missing_page_offset_rejected",
        "agent_draft_pending_intent_delta_container_valid",
        "agent_draft_pending_intent_baseline_container_valid",
    }
    schema_case_names = {row.get("name") for row in fixture.get("schema_validation_cases", []) if isinstance(row, dict)}
    if not required_schema_cases.issubset(schema_case_names):
        _fail(lint, FIXTURE, "fixture omits live/terminal/baseline/delta schema validation cases")
    required_key_negative = {
        "padded_component", "wrong_component_length", "noncanonical_trailing_bits",
        "wrong_literal_prefix", "extra_separator", "old_literal_agent_id",
        "agent_domain_reused_for_draft", "draft_domain_reused_for_agent",
        "wrong_source_agent_id", "wrong_source_draft_id", "caller_supplied_decoded_selector",
    }
    kat = fixture.get("key_derivation_kat")
    if not isinstance(kat, dict) or set(kat) != {"digest_construction", "algorithm", "encoding", "agent_component", "draft_component", "account_data_key", "account_data_key_ascii_length", "negative_cases"}:
        _fail(lint, FIXTURE, "key derivation KAT must be structurally closed")
    else:
        if kat.get("digest_construction") != CONSTRUCTION or kat.get("algorithm") != "SHA-256" or kat.get("encoding") != "base64url_no_pad" or kat.get("account_data_key_ascii_length") != 105 or set(kat.get("negative_cases") or []) != required_key_negative:
            _fail(lint, FIXTURE, "key derivation KAT metadata or negative closure drifted")
        component_results: list[str] = []
        for name, domain in (("agent_component", AGENT_DOMAIN), ("draft_component", DRAFT_DOMAIN)):
            row = kat.get(name, {})
            literal = row.get("canonical_literal") if isinstance(row, dict) else None
            if not isinstance(literal, str):
                _fail(lint, FIXTURE, f"{name} KAT literal is missing")
                continue
            prefix_hex, literal_hex, digest_hex, encoded = _component(domain, literal)
            expected_row = {
                "domain": domain,
                "domain_utf8_lf_hex": prefix_hex,
                "canonical_literal": literal,
                "literal_utf8_hex": literal_hex,
                "digest_hex": digest_hex,
                "component": encoded,
            }
            if row != expected_row:
                _fail(lint, FIXTURE, f"{name} KAT does not recompute byte-exactly")
            component_results.append(encoded)
        expected_key = "ak.agent.draft.v1:" + ":".join(component_results)
        if kat.get("account_data_key") != expected_key or len(expected_key.encode("ascii")) != 105:
            _fail(lint, FIXTURE, "final signed account-data key does not match the two KAT components")

    prose = PROSE.read_text(encoding="utf-8") if PROSE.is_file() else ""
    for marker in (KEY_PATTERN, AGENT_DOMAIN, DRAFT_DOMAIN, 'UTF8(domain + "\\n") || UTF8(canonical_literal)', "source_pending_event_id", "调用方另传的 decoded selector", "取得 holder account secret", "agent_draft_pending_intents", "live | terminal-redacted"):
        if marker not in prose:
            _fail(lint, PROSE, f"normative prose is missing {marker!r}")
    client_sync = CLIENT_SYNC_PROSE.read_text(encoding="utf-8") if CLIENT_SYNC_PROSE.is_file() else ""
    for marker in ("AccountSubscribeFrame.agent_draft_pending_intents", "AccountBaselineChannel", "AgentDraftPendingIntents", "completed_channels", "Agent session、其它 AccountId", "不得进入 `account_data.events`", "`items[]` 合计至多 100 项", "action=upsert|remove"):
        if marker not in client_sync:
            _fail(lint, CLIENT_SYNC_PROSE, f"normative sync prose is missing {marker!r}")
