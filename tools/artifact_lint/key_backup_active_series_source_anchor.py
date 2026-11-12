"""Close the canonical key-backup active-series source-anchor wire shape."""

from __future__ import annotations

from typing import Any

from .core import ARTIFACTS, SPEC_ROOT, Lint, load_json


KEY_BACKUP_SCHEMA = ARTIFACTS / "schemas" / "key-backup.schema.json"
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


def _shape(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _shape(child) for key, child in value.items()
                if key != "description" and not key.startswith("x-")}
    if isinstance(value, list):
        return [_shape(child) for child in value]
    return value


def _scope_shape() -> dict[str, Any]:
    return {"oneOf": [
        {"type": "object", "required": ["kind", "realm_id"],
         "properties": {"kind": {"const": "realm"}, "realm_id": {"$ref": "./common-ids.schema.json#/$defs/realm_id"}},
         "additionalProperties": False},
        {"type": "object", "required": ["kind", "realm_id", "circle_id"],
         "properties": {"kind": {"const": "circle"}, "realm_id": {"$ref": "./common-ids.schema.json#/$defs/realm_id"},
                        "circle_id": {"$ref": "./common-ids.schema.json#/$defs/circle_id"}},
         "additionalProperties": False},
    ]}


def check_key_backup_active_series_source_anchor(lint: Lint) -> None:
    key_backup = load_json(lint, KEY_BACKUP_SCHEMA)
    active_series = load_json(lint, ACTIVE_SERIES_SCHEMA)
    keys_operations = load_json(lint, KEYS_OPERATIONS_SCHEMA)
    event_payload = load_json(lint, EVENT_PAYLOAD_SCHEMA)
    contract = load_json(lint, CONTRACT_REGISTRY)
    fixture = load_json(lint, FIXTURE)
    if not all(
        isinstance(value, dict)
        for value in (key_backup, active_series, keys_operations, event_payload, contract, fixture)
    ):
        return

    required = active_series.get("required")
    properties = active_series.get("properties")
    branches = active_series.get("allOf", [])
    branch = branches[0] if isinstance(branches, list) and len(branches) == 1 and isinstance(branches[0], dict) else {}
    native_fields = ["effective_scope", "manager_ref", "recovery_ref", "recipient_ref"]
    discriminator = {"properties": {"actor_id": {"properties": {"kind": {"const": "realm"}}, "required": ["kind"],
        "$ref": "./common-ids.schema.json#/$defs/actor_id"}}, "required": ["actor_id"]}
    if _shape(branch.get("if")) != discriminator:
        _fail(lint, ACTIVE_SERIES_SCHEMA, "native/PCR branch discriminator must be exactly the Realm actor kind")
    legacy = branch.get("else", {})
    if (not isinstance(required, list) or "source_commit_ref" in required
            or legacy.get("required") != ["source_commit_ref"]):
        _fail(lint, ACTIVE_SERIES_SCHEMA, "PCR signed payload must require source_commit_ref exactly once")
    legacy_shape = {"required": ["source_commit_ref"], "properties": {"signature_proof": {"required": ["device_authorize_event_id"]}},
                    "not": {"anyOf": [{"required": [name]} for name in native_fields]}}
    if _shape(legacy) != legacy_shape:
        _fail(lint, ACTIVE_SERIES_SCHEMA, "PCR branch must retain its Device author and exclude native scope/source fields")
    native_shape = {"required": native_fields, "properties": {"actor_id": {"$ref": "./common-ids.schema.json#/$defs/realm_actor"},
                    "signature_proof": {"not": {"anyOf": [{"required": ["device_authorize_event_id"]}]}}},
                    "not": {"anyOf": [{"required": [name]} for name in ["source_commit_ref", "custodian_actor_id", "custody_authorization_ref"]]}}
    if _shape(branch.get("then")) != native_shape or active_series.get("additionalProperties") is not False:
        _fail(lint, ACTIVE_SERIES_SCHEMA, "native branch must require exact scoped source refs and forbid PCR/custody/Device author")
    if isinstance(properties, dict):
        if _shape(properties.get("effective_scope")) != _scope_shape():
            _fail(lint, ACTIVE_SERIES_SCHEMA, "native scope must remain a closed Realm/Circle union")
        for name in native_fields[1:]:
            if _shape(properties.get(name)) != {"$ref": "./authority-commit-operations.schema.json#/$defs/committed_event_ref"}:
                _fail(lint, ACTIVE_SERIES_SCHEMA, "native source refs must reuse full committed originals")
    if not isinstance(properties, dict) or properties.get("source_commit_ref", {}).get("$ref") != "./key-backup.schema.json#/properties/source_commit_ref":
        _fail(lint, ACTIVE_SERIES_SCHEMA, "signed payload must expose only the canonical source_commit_ref definition")
    if isinstance(properties, dict) and "source_ref" in properties:
        _fail(lint, ACTIVE_SERIES_SCHEMA, "legacy source_ref alias is forbidden")

    if 'source_commit_ref' in active_series.get('$defs', {}):
        _fail(lint, ACTIVE_SERIES_SCHEMA, 'duplicate source checkpoint definition is forbidden')
    anchor = key_backup.get('properties', {}).get('source_commit_ref', {})
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
        contract_text = f"{event_row.get('payload', '')} {event_row.get('state_writes', '')}"
        for marker in ("source_commit_ref", "realm_commit_id", "device_generation_ref"):
            if marker not in contract_text:
                _fail(lint, CONTRACT_REGISTRY, f"event contract does not pin {marker}")
        if "source_ref" not in contract_text or "CommittedEventRef" not in contract_text:
            _fail(lint, CONTRACT_REGISTRY, "event contract must explicitly forbid the legacy alias and full committed-event shape")

    schema_registry = contract.get("schema_registry", {})
    schema_row = _find(schema_registry.get("schemas"), "schema_id", SCHEMA_ID)
    if not isinstance(schema_row, dict) or "source_commit_ref" not in str(schema_row.get("description", "")):
        _fail(lint, CONTRACT_REGISTRY, "schema row must name the sole canonical source anchor")

    definitions = keys_operations.get("$defs", {})
    union = definitions.get("keys_backups_list_response_body", {}).get("oneOf", [])
    expected_refs = {"#/$defs/keys_backups_page", "#/$defs/realm_actor_archive_inventory_page", "#/$defs/realm_actor_backup_series_head_response_body"}
    if (not isinstance(union, list) or len(union) != 3
            or any(not isinstance(item, dict) or set(item) != {"$ref"} for item in union)
            or {item.get("$ref") for item in union if isinstance(item, dict)} != expected_refs):
        _fail(lint, KEYS_OPERATIONS_SCHEMA, "Station list response projection must be the closed three-role union")
    projection = definitions.get("backup_active_series_state", {})
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
    if (projection_required != {"account_id", "control_realm_id", "authority_commit_id", "secret_storage"}
            or set(projection_properties) != projection_required or projection.get("additionalProperties") is not False):
        _fail(lint, KEYS_OPERATIONS_SCHEMA, "PCR Station projection must retain its exact closed fields")

    # This is the existing list-head state, not the Device's five-field public current value.
    head = definitions.get("realm_actor_backup_series_head_response_body", {})
    if head.get("properties", {}).get("active_series") != {"$ref": "#/$defs/realm_actor_backup_active_series_state"}:
        _fail(lint, KEYS_OPERATIONS_SCHEMA, "native head response projection must reach its distinct native active-series state")
    native = definitions.get("realm_actor_backup_active_series_state", {})
    fields = {"realm_actor_id", "effective_scope", "manager_ref", "recovery_ref", "recipient_ref", "authority_commit_id", "secret_storage"}
    native_properties = native.get("properties", {})
    if (set(native.get("required", [])) != fields or set(native_properties) != fields
            or native.get("additionalProperties") is not False
            or native_properties.get("realm_actor_id") != {"$ref": "./common-ids.schema.json#/$defs/realm_actor_id"}
            or _shape(native_properties.get("effective_scope")) != _scope_shape()
            or native_properties.get("authority_commit_id") != {"$ref": "./common-ids.schema.json#/$defs/realm_commit_id"}
            or native_properties.get("secret_storage") != {"$ref": "#/$defs/backup_active_series_pointer"}
            or any(native_properties.get(name) != {"$ref": "./authority-commit-operations.schema.json#/$defs/committed_event_ref"} for name in native_fields[1:])):
        _fail(lint, KEYS_OPERATIONS_SCHEMA, "native list-head projection must retain exact actor/scope/original refs and provenance")

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
