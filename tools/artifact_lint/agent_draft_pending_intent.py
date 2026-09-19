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
VECTOR_REGISTRY = ARTIFACTS / "registry" / "vector-registry.json"
PROOF_CONTEXT = ARTIFACTS / "registry" / "proof-context-registry.json"
FIXTURE = ARTIFACTS / "fixtures" / "agent-draft-pending-intent-fixture.json"
PROSE = SPEC_ROOT / "zh" / "models" / "actor-private-effects.md"
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
    vectors = load_json(lint, VECTOR_REGISTRY)
    proof_context = load_json(lint, PROOF_CONTEXT)
    fixture = load_json(lint, FIXTURE)
    if not all(isinstance(value, dict) for value in (contract, account_data, payload, private_schema, vectors, proof_context, fixture)):
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
    value = private_defs.get("agent_draft_account_data_value", {})
    handoff_plaintext = private_defs.get("agent_draft_content_handoff_plaintext", {})
    key_schema = private_defs.get("agent_draft_account_data_key", {})
    if pending.get("properties", {}).get("state", {}).get("enum") != ["available", "consumed", "expired"]:
        _fail(lint, PRIVATE_SCHEMA, "pending state machine must be closed")
    if "source_pending_event_id" not in value.get("required", []) or value.get("properties", {}).get("schema", {}).get("const") != "ak.schema.agent_draft.v1":
        _fail(lint, PRIVATE_SCHEMA, "holder-created decrypted value must bind its source intent")
    if handoff_plaintext.get("properties", {}).get("schema", {}).get("const") != "ak.schema.agent_draft_content_handoff_plaintext.v1" or "content_digest" not in handoff_plaintext.get("required", []):
        _fail(lint, PRIVATE_SCHEMA, "HPKE handoff plaintext must be closed and digest-bound")
    if key_schema.get("minLength") != 105 or key_schema.get("maxLength") != 105 or key_schema.get("pattern") != KEY_REGEX:
        _fail(lint, PRIVATE_SCHEMA, "draft account-data key must be a fixed 105-character canonical digest key")
    consumption_key = private_defs.get("pending_intent_consumption", {}).get("properties", {}).get("account_data_key", {})
    if consumption_key != {"$ref": "#/$defs/agent_draft_account_data_key"}:
        _fail(lint, PRIVATE_SCHEMA, "pending consumption must directly reuse the canonical digest-key schema")

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
    for marker in (KEY_PATTERN, AGENT_DOMAIN, DRAFT_DOMAIN, 'UTF8(domain + "\\n") || UTF8(canonical_literal)', "source_pending_event_id", "调用方另传的 decoded selector", "取得 holder account secret", "account subscribe"):
        if marker not in prose:
            _fail(lint, PROSE, f"normative prose is missing {marker!r}")
