"""Close historical signer queries over exact authority-commit coordinates."""

from __future__ import annotations

from typing import Any

from .core import ARTIFACTS, ROOT, SPEC_ROOT, Lint, load_json, read_text


SCHEMA = ARTIFACTS / "schemas" / "signer-key-operations.schema.json"
AUTHORITY_SCHEMA = ARTIFACTS / "schemas" / "authority-commit-operations.schema.json"
ACCOUNT_SYNC_SCHEMA = ARTIFACTS / "schemas" / "account-subscribe-frame.schema.json"
CONTRACT = ARTIFACTS / "registry" / "contract-registry.json"
ERROR_MAPPING = ARTIFACTS / "registry" / "operations-error-mapping.json"
VECTORS = ARTIFACTS / "registry" / "vector-registry.json"
FIXTURE = ARTIFACTS / "fixtures" / "signer-key-historical-coordinate-fixture.json"
SERVER_PROSE = SPEC_ROOT / "zh" / "sync" / "server-trusted-results.md"
SYNC_PROSE = SPEC_ROOT / "zh" / "sync" / "client-sync.md"
VECTOR_PROSE = SPEC_ROOT / "zh" / "conformance" / "conformance-vectors.md"
RUNNER = ROOT / "tools" / "artifact_lint" / "runner.py"

OPERATION_ID = "ak.self.signer_keys.read.resolve.v1"
VECTOR_ID = "ak.vector.signer_key.historical_commit_coordinate.v1"
COMMITTED_REF = "./authority-commit-operations.schema.json#/$defs/committed_event_ref"
HISTORICAL_DEFS = ("historical_account_device_selector", "historical_agent_selector")
CURRENT_DEFS = ("current_account_device_selector", "current_agent_selector")
NEGATIVE_CASES = {
    "historical_selector_uses_bare_event_id",
    "request_realm_differs_from_selector_stream_realm",
    "row_event_id_differs_from_commit_event_ref",
    "selector_commit_id_differs_from_verified_row",
    "selector_stream_ref_differs_from_verified_row",
    "selector_stream_position_differs_from_verified_row",
    "target_and_authorization_ref_forced_equal",
    "current_projection_nested_event_used_as_coordinate",
    "array_index_used_for_result_correlation",
    "redacted_row_used_for_producer_signature_verification",
    "late_response_for_another_recipient_account",
    "bare_event_id_downgraded_to_current_query",
}


def _find(rows: Any, field: str, value: str) -> dict[str, Any] | None:
    if not isinstance(rows, list):
        return None
    matches = [row for row in rows if isinstance(row, dict) and row.get(field) == value]
    return matches[0] if len(matches) == 1 else None


def _defs(document: Any) -> dict[str, Any]:
    return document.get("$defs", {}) if isinstance(document, dict) else {}


def check_signer_key_historical_coordinate(lint: Lint) -> None:
    schema = load_json(lint, SCHEMA)
    definitions = _defs(schema)
    if not definitions:
        return

    for name in HISTORICAL_DEFS:
        selector = definitions.get(name)
        required = selector.get("required") if isinstance(selector, dict) else None
        properties = selector.get("properties") if isinstance(selector, dict) else None
        if not isinstance(required, list) or "committed_event_ref" not in required or "event_id" in required:
            lint.fail(SCHEMA, f"{name} must require committed_event_ref and reject bare event_id")
        committed = properties.get("committed_event_ref") if isinstance(properties, dict) else None
        if not isinstance(committed, dict) or committed.get("$ref") != COMMITTED_REF or "event_id" in properties:
            lint.fail(SCHEMA, f"{name} must use the canonical committed_event_ref only")

    for name in CURRENT_DEFS:
        selector = definitions.get(name)
        properties = selector.get("properties") if isinstance(selector, dict) else None
        if not isinstance(properties, dict) or "committed_event_ref" in properties or "event_id" in properties:
            lint.fail(SCHEMA, f"{name} must not accept any historical coordinate")

    key = definitions.get("query_signing_key")
    required = key.get("required") if isinstance(key, dict) else None
    properties = key.get("properties") if isinstance(key, dict) else None
    if required != ["public_key_b64u", "authorization_ref", "revision", "governance_generation"]:
        lint.fail(SCHEMA, "query_signing_key must require key bytes, independent authorization ref, revision and generation")
    if not isinstance(properties, dict) or properties.get("authorization_ref", {}).get("$ref") != COMMITTED_REF:
        lint.fail(SCHEMA, "query_signing_key authorization_ref must be a committed_event_ref")
    revision = properties.get("revision") if isinstance(properties, dict) else None
    if not isinstance(revision, dict) or revision.get("required") != ["commit_id", "stream_position"] or revision.get("additionalProperties") is not False:
        lint.fail(SCHEMA, "query_signing_key revision must be the closed current commit coordinate")
    if not isinstance(properties, dict) or properties.get("governance_generation", {}).get("minimum") != 0:
        lint.fail(SCHEMA, "query_signing_key must bind a non-negative governance_generation")

    for name in ("historical_account_device_outcome", "historical_agent_outcome"):
        outcome = definitions.get(name)
        ref = outcome.get("properties", {}).get("key", {}).get("$ref") if isinstance(outcome, dict) else None
        if ref != "#/$defs/query_signing_key":
            lint.fail(SCHEMA, f"{name} must carry the complete query_signing_key")
    if "historical_device_signing_key" in definitions:
        lint.fail(SCHEMA, "historical device results must not retain a key-only partial-success shape")

    authority = load_json(lint, AUTHORITY_SCHEMA)
    authority_defs = _defs(authority)
    committed = authority_defs.get("committed_event_ref")
    if not isinstance(committed, dict) or committed.get("required") != ["event_id", "commit_id", "stream_ref", "stream_position"]:
        lint.fail(AUTHORITY_SCHEMA, "committed_event_ref must remain the closed four-coordinate reference")
    scan = authority_defs.get("stream_scan_outcome")
    scan_items = scan.get("properties", {}).get("committed_events", {}).get("items", {}).get("$ref") if isinstance(scan, dict) else None
    if scan_items != "#/$defs/stream_row":
        lint.fail(AUTHORITY_SCHEMA, "per-stream scan must continue to carry canonical stream_row values")
    account_sync = load_json(lint, ACCOUNT_SYNC_SCHEMA)
    realm_sync = _defs(account_sync).get("realm_sync_entry")
    account_items = realm_sync.get("properties", {}).get("committed_events", {}).get("items", {}).get("$ref") if isinstance(realm_sync, dict) else None
    if account_items != "./authority-commit-operations.schema.json#/$defs/stream_row":
        lint.fail(ACCOUNT_SYNC_SCHEMA, "account subscribe must continue to carry the same canonical stream_row")

    contract = load_json(lint, CONTRACT)
    registry = contract.get("operation_registry") if isinstance(contract, dict) else None
    operation = _find(registry.get("operations") if isinstance(registry, dict) else None, "operation_id", OPERATION_ID)
    notes = operation.get("notes") if isinstance(operation, dict) else None
    for marker in ("committed_event_ref", "stream_row", "may differ", "without current-query fallback"):
        if not isinstance(notes, str) or marker not in notes:
            lint.fail(CONTRACT, f"signer-key operation notes are missing {marker!r}")

    mappings = load_json(lint, ERROR_MAPPING)
    error_row = _find(mappings.get("operations") if isinstance(mappings, dict) else None, "operation_id", OPERATION_ID)
    error_description = error_row.get("description") if isinstance(error_row, dict) else None
    for marker in ("committed_event_ref", "authorization coordinates", "current query"):
        if not isinstance(error_description, str) or marker not in error_description:
            lint.fail(ERROR_MAPPING, f"signer-key error mapping is missing {marker!r}")

    vectors = load_json(lint, VECTORS)
    vector = _find(vectors.get("vectors") if isinstance(vectors, dict) else None, "vector_id", VECTOR_ID)
    if not isinstance(vector, dict) or vector.get("applies_to_fixtures") != [FIXTURE.name]:
        lint.fail(VECTORS, "historical signer vector must point to its dedicated fixture")
    fixture = load_json(lint, FIXTURE)
    if not isinstance(fixture, dict) or fixture.get("vector_id") != VECTOR_ID:
        lint.fail(FIXTURE, "historical signer fixture must bind the registered vector")
    else:
        if fixture.get("carrier_sources") != [
            "account_subscribe.realm_sync_entry.commits",
            "ak.self.committed_event.read.scan.v1.stream_scan_outcome.commits",
        ]:
            lint.fail(FIXTURE, "fixture must retain exactly the two existing stream_row carrier sources")
        positive = fixture.get("positive_case")
        selector_ref = positive.get("selector", {}).get("committed_event_ref") if isinstance(positive, dict) else None
        authorization_ref = positive.get("resolved_key", {}).get("authorization_ref") if isinstance(positive, dict) else None
        if not isinstance(selector_ref, dict) or not isinstance(authorization_ref, dict) or selector_ref == authorization_ref:
            lint.fail(FIXTURE, "fixture must prove independent unequal target and authorization refs are valid")
        negatives = set(fixture.get("negative_cases", []))
        if not NEGATIVE_CASES.issubset(negatives):
            lint.fail(FIXTURE, "fixture is missing historical coordinate negative cases")

    prose = {
        SERVER_PROSE: ("历史坐标来源与双引用分离", "MAY 相同", "不得降级成 `current_admission`"),
        SYNC_PROSE: ("realm_sync_entry.commits[]", "stream_scan_outcome.commits[]", "不得新增"),
        VECTOR_PROSE: (VECTOR_ID, "authorization_ref", "current-query 降级"),
    }
    for path, markers in prose.items():
        source = read_text(path)
        for marker in markers:
            if marker not in source:
                lint.fail(path, f"historical signer normative prose is missing {marker!r}")

    if "check_signer_key_historical_coordinate(lint)" not in read_text(RUNNER):
        lint.fail(RUNNER, "phase-2 runner must invoke the historical signer coordinate gate")
