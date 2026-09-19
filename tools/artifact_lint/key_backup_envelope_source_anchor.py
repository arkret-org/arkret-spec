"""Close the key-backup envelope source anchor and successor authoring contract."""

from __future__ import annotations

from typing import Any

from .core import ARTIFACTS, SPEC_ROOT, Lint, load_json


ENVELOPE_SCHEMA = ARTIFACTS / "schemas" / "key-backup.schema.json"
ACTIVE_SERIES_SCHEMA = ARTIFACTS / "schemas" / "key-backup-active-series.schema.json"
CONTRACT_REGISTRY = ARTIFACTS / "registry" / "contract-registry.json"
FIXTURE = ARTIFACTS / "fixtures" / "key-backup-fixture.json"
KEY_MANAGEMENT_PROSE = SPEC_ROOT / "zh" / "identity" / "key-management.md"
DEVICE_LIFECYCLE_PROSE = SPEC_ROOT / "zh" / "crypto-media" / "device-lifecycle.md"
SCHEMA_ID = "ak.schema.key_backup.v1"


def _fail(lint: Lint, path: Any, message: str) -> None:
    lint.fail(path, f"key-backup envelope source anchor: {message}")


def _find(rows: Any, key: str, value: str) -> dict[str, Any] | None:
    if not isinstance(rows, list):
        return None
    return next((row for row in rows if isinstance(row, dict) and row.get(key) == value), None)


def _source_shape(schema: dict[str, Any], *, active_series: bool) -> dict[str, Any]:
    if active_series:
        return schema.get("$defs", {}).get("source_commit_ref", {})
    return schema.get("properties", {}).get("source_commit_ref", {})


def _predecessor_rules_closed(schema: dict[str, Any]) -> bool:
    rules = schema.get("allOf")
    if not isinstance(rules, list):
        return False
    genesis = any(
        rule.get("if", {}).get("properties", {}).get("series_seq", {}).get("const") == 0
        and {
            tuple(branch.get("not", {}).get("required", []))
            for branch in rule.get("then", {}).get("allOf", [])
            if isinstance(branch, dict)
        }
        == {("supersedes_id",), ("supersedes_digest",)}
        for rule in rules
        if isinstance(rule, dict)
    )
    successor = any(
        rule.get("if", {}).get("properties", {}).get("series_seq", {}).get("minimum") == 1
        and set(rule.get("then", {}).get("required", []))
        == {"supersedes_id", "supersedes_digest"}
        for rule in rules
        if isinstance(rule, dict)
    )
    return genesis and successor


def check_key_backup_envelope_source_anchor(lint: Lint) -> None:
    envelope = load_json(lint, ENVELOPE_SCHEMA)
    active_series = load_json(lint, ACTIVE_SERIES_SCHEMA)
    contract = load_json(lint, CONTRACT_REGISTRY)
    fixture = load_json(lint, FIXTURE)
    if not all(isinstance(value, dict) for value in (envelope, active_series, contract, fixture)):
        return

    properties = envelope.get("properties")
    required = envelope.get("required")
    if not isinstance(properties, dict) or "source_commit_ref" not in properties:
        _fail(lint, ENVELOPE_SCHEMA, "source_commit_ref property is missing")
        return
    if "source_ref" in properties:
        _fail(lint, ENVELOPE_SCHEMA, "legacy source_ref alias is forbidden")
    if isinstance(required, list) and "source_commit_ref" in required:
        _fail(lint, ENVELOPE_SCHEMA, "source_commit_ref must remain optional")
    if envelope.get("additionalProperties") is not False:
        _fail(lint, ENVELOPE_SCHEMA, "envelope must reject unregistered top-level aliases")

    expected_fields = {"realm_commit_id", "device_generation_ref"}
    anchor = _source_shape(envelope, active_series=False)
    if set(anchor.get("required", [])) != expected_fields:
        _fail(lint, ENVELOPE_SCHEMA, "source_commit_ref must require exactly two canonical members")
    if set(anchor.get("properties", {})) != expected_fields:
        _fail(lint, ENVELOPE_SCHEMA, "source_commit_ref must define exactly two members and no CommittedEventRef mirror")
    if anchor.get("additionalProperties") is not False:
        _fail(lint, ENVELOPE_SCHEMA, "source_commit_ref must remain closed")
    anchor_properties = anchor.get("properties", {})
    if anchor_properties.get("realm_commit_id") != {
        "$ref": "./common-ids.schema.json#/$defs/realm_commit_id"
    }:
        _fail(lint, ENVELOPE_SCHEMA, "realm_commit_id must directly reuse the strong RealmCommitId definition")
    generation = anchor_properties.get("device_generation_ref", {})
    if generation.get("$ref") != "./recovery-session.schema.json#/$defs/pcr_generation_ref":
        _fail(lint, ENVELOPE_SCHEMA, "device_generation_ref must reuse the positive integer PCR generation definition")

    active_anchor = _source_shape(active_series, active_series=True)
    if {
        "required": active_anchor.get("required"),
        "properties": active_anchor.get("properties"),
        "additionalProperties": active_anchor.get("additionalProperties"),
    } != {
        "required": anchor.get("required"),
        "properties": anchor.get("properties"),
        "additionalProperties": anchor.get("additionalProperties"),
    }:
        _fail(lint, ACTIVE_SERIES_SCHEMA, "active-series and envelope source anchors must have the same closed typed shape")

    if not _predecessor_rules_closed(envelope):
        _fail(lint, ENVELOPE_SCHEMA, "genesis/successor predecessor rules must remain independent and structurally closed")

    schema_row = _find(
        contract.get("schema_registry", {}).get("schemas"),
        "schema_id",
        SCHEMA_ID,
    )
    if not isinstance(schema_row, dict):
        _fail(lint, CONTRACT_REGISTRY, "canonical schema row is missing")
    else:
        authoring = schema_row.get("authoring_contract")
        if not isinstance(authoring, dict):
            _fail(lint, CONTRACT_REGISTRY, "structured authoring_contract is missing")
        else:
            if authoring.get("canonical_source_field") != "source_commit_ref" or authoring.get("presence") != "optional":
                _fail(lint, CONTRACT_REGISTRY, "authoring contract must select optional source_commit_ref")
            builder = authoring.get("successor_builder_input", {})
            if builder.get("kind") != "typed_value" or builder.get("type_name") != "KeyBackupSourceCommitRef":
                _fail(lint, CONTRACT_REGISTRY, "successor builder must accept the canonical typed value")
            if set(builder.get("required_members", [])) != expected_fields:
                _fail(lint, CONTRACT_REGISTRY, "successor builder typed value must require both canonical members")
            if builder.get("member_types") != {
                "realm_commit_id": "RealmCommitId",
                "device_generation_ref": "u64_positive_integer",
            }:
                _fail(lint, CONTRACT_REGISTRY, "successor builder member types must remain strong and exact")
            forbidden = set(builder.get("forbidden_inputs", []))
            expected_forbidden = {
                "source_ref",
                "CommittedEventRef",
                "string_device_generation_ref",
                "seal",
                "frontier_surrogate",
            }
            if forbidden != expected_forbidden:
                _fail(lint, CONTRACT_REGISTRY, "successor builder forbidden-input set is incomplete")
            signing = authoring.get("signature_transcription", {})
            if signing.get("projection") != "envelope_without_auth_data.signature" or signing.get("present_source_commit_ref_is_authenticated") is not True:
                _fail(lint, CONTRACT_REGISTRY, "signature transcription must authenticate the present canonical source field")
            if signing.get("post_signature_alias_rewrite") != "forbidden":
                _fail(lint, CONTRACT_REGISTRY, "post-signature alias rewriting must be forbidden")
            predecessor = authoring.get("predecessor_chain", {})
            if predecessor.get("independent_from_source_commit_ref") is not True:
                _fail(lint, CONTRACT_REGISTRY, "predecessor chain must remain independent of the source checkpoint")

    required_cases = {
        "key_backup_envelope_canonical_source_commit_ref_successor_valid",
        "key_backup_envelope_source_commit_ref_omitted_valid",
        "key_backup_envelope_source_ref_alias_rejected",
        "key_backup_envelope_full_committed_event_ref_rejected",
        "key_backup_envelope_string_generation_rejected",
        "key_backup_envelope_missing_realm_commit_id_rejected",
        "key_backup_envelope_missing_device_generation_ref_rejected",
        "key_backup_envelope_source_anchor_cannot_replace_predecessor_rejected",
    }
    cases = fixture.get("schema_validation_cases")
    case_names = {case.get("name") for case in cases or [] if isinstance(case, dict)}
    missing_cases = sorted(required_cases - case_names)
    if missing_cases:
        _fail(lint, FIXTURE, f"schema fixture omits envelope canonical/negative cases {missing_cases}")

    prose_markers = {
        KEY_MANAGEMENT_PROSE: (
            "KeyBackupSourceCommitRef{realm_commit_id: RealmCommitId, device_generation_ref: u64}",
            "验签后改名、兼容别名或双读均被禁止",
            "来源锚不能替代、推导或合并这组 predecessor/CAS 字段",
        ),
        DEVICE_LIFECYCLE_PROSE: (
            "envelope builder 只接受等价于 `KeyBackupSourceCommitRef",
            "它与 `series_seq + supersedes_id + supersedes_digest` predecessor/CAS 链彼此独立",
        ),
    }
    for path, markers in prose_markers.items():
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        for marker in markers:
            if marker not in text:
                _fail(lint, path, f"normative prose is missing {marker!r}")
