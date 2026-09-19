"""Keep the account-private CAS revision field canonical and unambiguous."""

from __future__ import annotations

from typing import Any

from .core import ARTIFACTS, SPEC_ROOT, Lint, load_json


EVENT_SCHEMA = ARTIFACTS / "schemas" / "event-payload.schema.json"
OPERATIONS_SCHEMA = ARTIFACTS / "schemas" / "account-data-operations.schema.json"
CONTRACT_REGISTRY = ARTIFACTS / "registry" / "contract-registry.json"
KEY_REGISTRY = ARTIFACTS / "registry" / "account-data-key-registry.json"
ERROR_MAPPING = ARTIFACTS / "registry" / "operations-error-mapping.json"
VECTOR_REGISTRY = ARTIFACTS / "registry" / "vector-registry.json"
FIXTURE = ARTIFACTS / "fixtures" / "account-data-cas-convergence-fixture.json"
ACCOUNT_DATA_PROSE = SPEC_ROOT / "zh" / "models" / "account-data.md"
RELATED_PROSE = (
    SPEC_ROOT / "zh" / "models" / "file-transfer.md",
    SPEC_ROOT / "zh" / "models" / "personal-productivity.md",
    SPEC_ROOT / "zh" / "models" / "private-objects.md",
    SPEC_ROOT / "zh" / "sync" / "invite-addressing.md",
)
EVENT_KIND = "ak.account_data.set"
OPERATIONS = {
    "ak.self.account_data.resource.delete.v1",
    "ak.self.account_data.resource.replace.v1",
}
VECTOR_ID = "ak.vector.account_data.cas_convergence.v1"


def _fail(lint: Lint, path: Any, message: str) -> None:
    lint.fail(path, f"account-data revision name: {message}")


def _find(rows: Any, key: str, value: str) -> dict[str, Any] | None:
    if not isinstance(rows, list):
        return None
    return next((row for row in rows if isinstance(row, dict) and row.get(key) == value), None)


def _all_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [text for item in value for text in _all_strings(item)]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _all_strings(item)]
    return []


def check_account_data_revision_name(lint: Lint) -> None:
    event_schema = load_json(lint, EVENT_SCHEMA)
    operations_schema = load_json(lint, OPERATIONS_SCHEMA)
    contract = load_json(lint, CONTRACT_REGISTRY)
    key_registry = load_json(lint, KEY_REGISTRY)
    error_mapping = load_json(lint, ERROR_MAPPING)
    vector_registry = load_json(lint, VECTOR_REGISTRY)
    fixture = load_json(lint, FIXTURE)
    if not all(
        isinstance(value, dict)
        for value in (
            event_schema,
            operations_schema,
            contract,
            key_registry,
            error_mapping,
            vector_registry,
            fixture,
        )
    ):
        return

    payload = event_schema.get("$defs", {}).get("account_data_set_payload", {})
    required = payload.get("required", [])
    properties = payload.get("properties", {})
    if required.count("expected_server_revision") != 1:
        _fail(lint, EVENT_SCHEMA, "signed payload must require expected_server_revision exactly once")
    if "expected_revision" in required or "expected_revision" in properties:
        _fail(lint, EVENT_SCHEMA, "legacy expected_revision alias is forbidden")
    if properties.get("expected_server_revision", {}).get("type") != "integer" or properties.get(
        "expected_server_revision", {}
    ).get("minimum") != 0:
        _fail(lint, EVENT_SCHEMA, "expected_server_revision must remain a non-negative integer")
    if payload.get("additionalProperties") is not False:
        _fail(lint, EVENT_SCHEMA, "signed payload must remain closed so dual fields fail before verification")
    payload_text = " ".join(_all_strings(payload))
    for marker in ("expected_server_revision", "expected_revision is not an alias", "shared face"):
        if marker not in payload_text:
            _fail(lint, EVENT_SCHEMA, f"signed payload contract does not pin {marker!r}")

    branches = payload.get("allOf", [])
    if not isinstance(branches, list) or len(branches) < 2:
        _fail(lint, EVENT_SCHEMA, "agent-draft create branches are missing")
    else:
        revision_guards = []
        for branch in branches:
            if not isinstance(branch, dict):
                continue
            for side in ("if", "then"):
                guard = branch.get(side, {}).get("properties", {}).get("expected_server_revision")
                if isinstance(guard, dict) and guard.get("const") == 0:
                    revision_guards.append(guard)
        if len(revision_guards) != 2:
            _fail(lint, EVENT_SCHEMA, "both agent-draft source branches must pin expected_server_revision=0")

    blocklist = event_schema.get("$defs", {}).get("account_blocklist_payload", {})
    if "expected_server_revision" not in " ".join(_all_strings(blocklist)):
        _fail(lint, EVENT_SCHEMA, "blocklist shared-counter cross-reference uses the wrong field name")

    operation_schema_text = " ".join(_all_strings(operations_schema))
    if "expected_server_revision" not in operation_schema_text:
        _fail(lint, OPERATIONS_SCHEMA, "operation DTO descriptions omit expected_server_revision")
    if "expected_revision" in operation_schema_text:
        _fail(lint, OPERATIONS_SCHEMA, "operation DTO descriptions retain the legacy field name")

    event_row = _find(contract.get("event_kind_registry", {}).get("event_kinds"), "event_kind", EVENT_KIND)
    if not isinstance(event_row, dict):
        _fail(lint, CONTRACT_REGISTRY, "event-kind row is missing")
    else:
        row_text = " ".join(_all_strings(event_row))
        if "expected_server_revision" not in row_text or "not an alias" not in row_text:
            _fail(lint, CONTRACT_REGISTRY, "event-kind row does not close the canonical name and alias rejection")

    private_write = (
        contract.get("event_kind_registry", {})
        .get("actor_private_contracts", {})
        .get("event_writes", {})
        .get(EVENT_KIND, {})
    )
    private_text = " ".join(_all_strings(private_write))
    for marker in (
        "payload.expected_server_revision",
        "checked_add(payload.expected_server_revision,1)",
        "server_revision_cas",
    ):
        if marker not in private_text:
            _fail(lint, CONTRACT_REGISTRY, f"private effect contract omits {marker!r}")
    if "payload.expected_revision" in private_text:
        _fail(lint, CONTRACT_REGISTRY, "private effect contract uses the shared revision field")

    operation_rows = contract.get("operation_registry", {}).get("operations")
    for operation_id in sorted(OPERATIONS):
        row = _find(operation_rows, "operation_id", operation_id)
        notes = str(row.get("notes", "")) if isinstance(row, dict) else ""
        if "expected_server_revision" not in notes or "not accepted as an alias" not in notes:
            _fail(lint, CONTRACT_REGISTRY, f"{operation_id} does not close canonical use and alias rejection")

    key_rules = " ".join(_all_strings(key_registry.get("registry_rules", [])))
    for marker in ("expected_server_revision", "shared typed expected_revision", "not an alias"):
        if marker not in key_rules:
            _fail(lint, KEY_REGISTRY, f"registry rule does not separate {marker!r}")

    error_rows = error_mapping.get("operations")
    for operation_id in sorted(OPERATIONS):
        row = _find(error_rows, "operation_id", operation_id)
        if not isinstance(row, dict) or "expected_server_revision" not in str(row.get("description", "")):
            _fail(lint, ERROR_MAPPING, f"{operation_id} error mapping uses the wrong CAS field name")

    vector = _find(vector_registry.get("vectors"), "vector_id", VECTOR_ID)
    vector_text = " ".join(_all_strings(vector or {}))
    for marker in ("expected_server_revision", "expected_revision alias", "both names"):
        if marker not in vector_text:
            _fail(lint, VECTOR_REGISTRY, f"conformance vector does not cover {marker!r}")

    cases = fixture.get("schema_validation_cases")
    required_cases = {
        "account_data_set_expected_server_revision_valid",
        "account_data_set_expected_revision_alias_rejected",
        "account_data_set_dual_revision_fields_rejected",
        "account_data_set_missing_revision_rejected",
    }
    case_names = {case.get("name") for case in cases or [] if isinstance(case, dict)}
    if case_names != required_cases:
        _fail(lint, FIXTURE, f"schema cases must be exactly {sorted(required_cases)}")
    by_name = {case.get("name"): case for case in cases or [] if isinstance(case, dict)}
    valid = by_name.get("account_data_set_expected_server_revision_valid", {}).get("instance", {})
    alias = by_name.get("account_data_set_expected_revision_alias_rejected", {}).get("instance", {})
    dual = by_name.get("account_data_set_dual_revision_fields_rejected", {}).get("instance", {})
    if "expected_server_revision" not in valid or "expected_revision" in valid:
        _fail(lint, FIXTURE, "canonical positive case does not use only expected_server_revision")
    if "expected_revision" not in alias or "expected_server_revision" in alias:
        _fail(lint, FIXTURE, "alias rejection case does not isolate expected_revision")
    if not {"expected_server_revision", "expected_revision"}.issubset(dual):
        _fail(lint, FIXTURE, "dual-field rejection case does not carry both names")

    account_text = ACCOUNT_DATA_PROSE.read_text(encoding="utf-8") if ACCOUNT_DATA_PROSE.is_file() else ""
    for marker in (
        "`expected_server_revision`",
        "shared Realm typed current result",
        "不得互换、别名、双写或在验签后改名",
    ):
        if marker not in account_text:
            _fail(lint, ACCOUNT_DATA_PROSE, f"normative prose omits {marker!r}")
    for path in RELATED_PROSE:
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        if "expected_server_revision" not in text:
            _fail(lint, path, "cross-domain account-data CAS reference uses the wrong field name")
