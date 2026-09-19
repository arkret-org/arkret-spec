"""Close the canonical key-backup active-series source-anchor wire shape."""

from __future__ import annotations

from typing import Any

from .core import ARTIFACTS, SPEC_ROOT, Lint, load_json


ACTIVE_SERIES_SCHEMA = ARTIFACTS / "schemas" / "key-backup-active-series.schema.json"
KEYS_OPERATIONS_SCHEMA = ARTIFACTS / "schemas" / "keys-operations.schema.json"
EVENT_PAYLOAD_SCHEMA = ARTIFACTS / "schemas" / "event-payload.schema.json"
CONTRACT_REGISTRY = ARTIFACTS / "registry" / "contract-registry.json"
FIXTURE = ARTIFACTS / "fixtures" / "key-backup-fixture.json"
KEY_MANAGEMENT_PROSE = SPEC_ROOT / "zh" / "identity" / "key-management.md"
DEVICE_LIFECYCLE_PROSE = SPEC_ROOT / "zh" / "crypto-media" / "device-lifecycle.md"
EVENT_KIND = "ak.key_backup.active_series"
SCHEMA_ID = "ak.schema.key_backup_active_series.v1"


def _fail(lint: Lint, path: Any, message: str) -> None:
    lint.fail(path, f"key-backup active-series source anchor: {message}")


def _find(rows: Any, key: str, value: str) -> dict[str, Any] | None:
    if not isinstance(rows, list):
        return None
    return next((row for row in rows if isinstance(row, dict) and row.get(key) == value), None)


def check_key_backup_active_series_source_anchor(lint: Lint) -> None:
    active_series = load_json(lint, ACTIVE_SERIES_SCHEMA)
    keys_operations = load_json(lint, KEYS_OPERATIONS_SCHEMA)
    event_payload = load_json(lint, EVENT_PAYLOAD_SCHEMA)
    contract = load_json(lint, CONTRACT_REGISTRY)
    fixture = load_json(lint, FIXTURE)
    if not all(
        isinstance(value, dict)
        for value in (active_series, keys_operations, event_payload, contract, fixture)
    ):
        return

    required = active_series.get("required")
    properties = active_series.get("properties")
    if not isinstance(required, list) or required.count("source_commit_ref") != 1:
        _fail(lint, ACTIVE_SERIES_SCHEMA, "signed payload must require source_commit_ref exactly once")
    if not isinstance(properties, dict) or properties.get("source_commit_ref", {}).get("$ref") != "#/$defs/source_commit_ref":
        _fail(lint, ACTIVE_SERIES_SCHEMA, "signed payload must expose only the canonical source_commit_ref definition")
    if isinstance(properties, dict) and "source_ref" in properties:
        _fail(lint, ACTIVE_SERIES_SCHEMA, "legacy source_ref alias is forbidden")

    anchor = active_series.get("$defs", {}).get("source_commit_ref", {})
    expected_fields = {"realm_commit_id", "device_generation_ref"}
    if set(anchor.get("required", [])) != expected_fields:
        _fail(lint, ACTIVE_SERIES_SCHEMA, "source_commit_ref must require exactly realm_commit_id and device_generation_ref")
    if set(anchor.get("properties", {})) != expected_fields:
        _fail(lint, ACTIVE_SERIES_SCHEMA, "source_commit_ref must define exactly two members and no CommittedEventRef mirror")
    if anchor.get("additionalProperties") is not False:
        _fail(lint, ACTIVE_SERIES_SCHEMA, "source_commit_ref must remain closed")
    anchor_properties = anchor.get("properties", {})
    if anchor_properties.get("realm_commit_id") != {
        "$ref": "./common-ids.schema.json#/$defs/realm_commit_id"
    }:
        _fail(lint, ACTIVE_SERIES_SCHEMA, "realm_commit_id must directly reuse the strong RealmCommitId definition")
    generation = anchor_properties.get("device_generation_ref", {})
    if generation.get("$ref") != "./recovery-session.schema.json#/$defs/pcr_generation_ref":
        _fail(lint, ACTIVE_SERIES_SCHEMA, "device_generation_ref must reuse the positive PCR generation definition")

    payload_def = event_payload.get("$defs", {}).get("key_backup_active_series_payload", {})
    if payload_def.get("allOf") != [{"$ref": "./key-backup-active-series.schema.json"}]:
        _fail(lint, EVENT_PAYLOAD_SCHEMA, "Event payload must directly reuse the standalone closed schema")

    event_registry = contract.get("event_kind_registry", {})
    event_row = _find(event_registry.get("event_kinds"), "event_kind", EVENT_KIND)
    if not isinstance(event_row, dict):
        _fail(lint, CONTRACT_REGISTRY, "event-kind row is missing")
    else:
        if event_row.get("payload_schema_ref") != "schemas/event-payload.schema.json#/$defs/key_backup_active_series_payload":
            _fail(lint, CONTRACT_REGISTRY, "event-kind payload schema ref is missing or wrong")
        contract_text = f"{event_row.get('payload', '')} {event_row.get('result_writes', '')}"
        for marker in ("source_commit_ref", "realm_commit_id", "device_generation_ref"):
            if marker not in contract_text:
                _fail(lint, CONTRACT_REGISTRY, f"event contract does not pin {marker}")
        if "source_ref" not in contract_text or "CommittedEventRef" not in contract_text:
            _fail(lint, CONTRACT_REGISTRY, "event contract must explicitly forbid the legacy alias and full committed-event shape")

    schema_registry = contract.get("schema_registry", {})
    schema_row = _find(schema_registry.get("schemas"), "schema_id", SCHEMA_ID)
    if not isinstance(schema_row, dict) or "source_commit_ref" not in str(schema_row.get("description", "")):
        _fail(lint, CONTRACT_REGISTRY, "schema row must name the sole canonical source anchor")

    projection = keys_operations.get("$defs", {}).get("backup_active_series_state", {})
    projection_required = set(projection.get("required", []))
    projection_properties = projection.get("properties", {})
    if "authority_commit_id" not in projection_required or "source_commit_ref" in projection_required:
        _fail(lint, KEYS_OPERATIONS_SCHEMA, "Station projection provenance must remain authority_commit_id")
    if set(projection_properties) & {"source_commit_ref", "source_ref"}:
        _fail(lint, KEYS_OPERATIONS_SCHEMA, "Station projection must not alias the signed payload source anchor")
    if projection_properties.get("authority_commit_id") != {
        "$ref": "./common-ids.schema.json#/$defs/realm_commit_id"
    }:
        _fail(lint, KEYS_OPERATIONS_SCHEMA, "projection authority_commit_id must remain a strong RealmCommitId")

    required_cases = {
        "key_backup_active_series_canonical_source_commit_ref_valid",
        "key_backup_active_series_source_ref_alias_rejected",
        "key_backup_active_series_full_committed_event_ref_rejected",
        "key_backup_active_series_missing_realm_commit_id_rejected",
        "key_backup_active_series_missing_device_generation_ref_rejected",
    }
    cases = fixture.get("schema_validation_cases")
    case_names = {case.get("name") for case in cases or [] if isinstance(case, dict)}
    missing_cases = sorted(required_cases - case_names)
    if missing_cases:
        _fail(lint, FIXTURE, f"schema fixture omits canonical/negative cases {missing_cases}")

    prose_markers = {
        KEY_MANAGEMENT_PROSE: (
            "来源锚只有一个 canonical wire 形状",
            "payload 不携 `source_ref`",
            "response DTO 的 `authority_commit_id`",
        ),
        DEVICE_LIFECYCLE_PROSE: (
            "唯一顶层名是 `source_commit_ref`",
            "完整 `CommittedEventRef` 都不是 v1 wire",
        ),
    }
    for path, markers in prose_markers.items():
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        for marker in markers:
            if marker not in text:
                _fail(lint, path, f"normative prose is missing {marker!r}")
