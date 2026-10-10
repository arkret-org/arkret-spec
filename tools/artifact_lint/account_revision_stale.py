"""Keep the Account stale-prefix recovery carrier and its fixture aligned."""

from __future__ import annotations

from .core import ARTIFACTS, Lint, jsonschema_errors, load_json

SCHEMA = ARTIFACTS / "schemas" / "account-subscribe-frame.schema.json"
MAPPING = ARTIFACTS / "registry" / "operations-error-mapping.json"
FIXTURE = ARTIFACTS / "fixtures" / "client-sync-fixture.json"
SCHEMA_REF = "schemas/account-subscribe-frame.schema.json#/$defs/account_revision_stale_problem"
OPERATION = "ak.self.account.stream.subscribe.v1"
CASE = "revision_stale_keeps_the_cursor_and_continues_backfill"


def contract_errors(schema: dict, mapping: dict, fixture: dict) -> list[str]:
    errors = []
    carrier = schema.get("$defs", {}).get("account_revision_stale_problem", {})
    branches = carrier.get("allOf", [])
    typed = next((row for row in branches if "properties" in row), {})
    properties = typed.get("properties", {})
    if "continuation_cursor" not in typed.get("required", []):
        errors.append("carrier must require continuation_cursor")
    if properties.get("type") != {"const": "https://arkret.org/problems/revision_stale"}:
        errors.append("carrier must pin the registered Problem type")
    if properties.get("status") != {"const": 409}:
        errors.append("carrier must pin status 409")
    if properties.get("continuation_cursor") != {"$ref": "#/$defs/cursor_value"}:
        errors.append("continuation must use the canonical stream cursor shape")
    operation = next((row for row in mapping.get("operations", []) if row.get("operation_id") == OPERATION), {})
    if "revision_stale" not in operation.get("operation_specific", []):
        errors.append("Account operation must register revision_stale")
    cases = [row for row in fixture.get("reconnect", []) if row.get("name") == CASE]
    if len(cases) != 1:
        errors.append("independent revision_stale recovery case must occur exactly once")
        return errors
    case = cases[0]
    if case.get("response_problem", {}).get("continuation_cursor") != case.get("stored_cursor"):
        errors.append("fixture continuation must equal the preserved cursor")
    for name, expected in {
        "server_outcome": "revision_stale",
        "expected": "resume",
        "baseline_redone": False,
        "discard_old_cursor": False,
        "checkpoint_advanced_on_error": False,
        "delivery_acks_invalidated": False,
        "mls_private_state_deleted": False,
        "fresh_process_readback": True,
        "expected_client_action": "follow_the_response_continuation_cursor",
    }.items():
        if case.get(name) != expected:
            errors.append(f"fixture must preserve {name}={expected!r}")
    return errors


def check_account_revision_stale(lint: Lint) -> None:
    schema, mapping, fixture = [load_json(lint, path) for path in (SCHEMA, MAPPING, FIXTURE)]
    if not all(isinstance(value, dict) for value in (schema, mapping, fixture)):
        return
    for error in contract_errors(schema, mapping, fixture):
        lint.fail(FIXTURE, f"Account revision_stale: {error}")
    for case in fixture.get("reconnect", []):
        if case.get("name") == CASE:
            for error in jsonschema_errors(lint, FIXTURE, SCHEMA_REF, case.get("response_problem")):
                lint.fail(FIXTURE, f"Account revision_stale Problem: {error}")
