"""Closure gate for the Account Authority issuer-ledger genesis contract.

The executable carrier once said that genesis waits for Station checkpoint and
RealmCommit while the structured evidence and normative prose both said the
opposite.  This gate keeps the prose-bearing decision point and its structured
evidence on the same fail-closed, issuer-private no-wait contract.
"""

from __future__ import annotations

from .core import ARTIFACTS, Lint, load_json


FIXTURE_PATH = ARTIFACTS / "fixtures" / "account-status-issuer-ledger-fixture.json"
SCHEMA_PATH = ARTIFACTS / "schemas" / "account-operations.schema.json"

GENESIS_REQUIREMENT = (
    "The genesis record is created inside the binding commit transaction, carries no "
    "predecessor, and does not wait for the Station checkpoint or the RealmCommit."
)


def check_account_status_issuer_genesis(lint: Lint) -> None:
    data = load_json(lint, FIXTURE_PATH)
    if not isinstance(data, dict):
        return

    schema = load_json(lint, SCHEMA_PATH)
    record_shape = schema.get("$defs", {}).get("account_status_record", {}) if isinstance(schema, dict) else {}
    if ("effective_at" in record_shape.get("properties", {})
            or "effective_at" in record_shape.get("required", [])
            or record_shape.get("additionalProperties") is not False):
        lint.fail(SCHEMA_PATH, "account_status_record must reject retired effective_at")
    try:
        from tools.regenerate_controller_gate_basis_fixture import refresh_ledger
        if refresh_ledger(data) != data:
            lint.fail(FIXTURE_PATH, "account status ledger identity/proof/reference transcript drift")
    except Exception as error:
        lint.fail(FIXTURE_PATH, "account status ledger transcript: " + str(error))
    for group in ("records", "conflicting_records"):
        for row in data.get("ledger", {}).get(group, []):
            if "effective_at" in row.get("record", {}):
                lint.fail(FIXTURE_PATH, "account_status_record must reject retired effective_at")

    rules = data.get("genesis_rules")
    if not isinstance(rules, dict):
        lint.fail(FIXTURE_PATH, "genesis_rules must be an object")
        return

    required = {
        "created_in_the_binding_commit_transaction": True,
        "carries_previous_account_status_record_id": False,
        "waits_for_station_checkpoint": False,
        "waits_for_realm_commit": False,
    }
    for field, expected in required.items():
        if rules.get(field) is not expected:
            lint.fail(FIXTURE_PATH, f"genesis_rules.{field} must be {str(expected).lower()}")

    matching: list[dict] = []
    for evidence in data.get("security_evidence", []):
        if not isinstance(evidence, dict) or evidence.get("clause_id") != "AK-NC-081":
            continue
        for point in evidence.get("decision_points", []):
            if isinstance(point, dict) and point.get("id") == "genesis_creation":
                matching.append(point)

    if len(matching) != 1:
        lint.fail(
            FIXTURE_PATH,
            "security_evidence must contain exactly one AK-NC-081/genesis_creation decision point",
        )
        return

    point = matching[0]
    if point.get("requirement") != GENESIS_REQUIREMENT:
        lint.fail(
            FIXTURE_PATH,
            "AK-NC-081/genesis_creation requirement must state the issuer-private no-wait contract",
        )
    if point.get("evidence") != ["/genesis_rules"]:
        lint.fail(
            FIXTURE_PATH,
            "AK-NC-081/genesis_creation evidence must be exactly ['/genesis_rules']",
        )

    # The same canonical ledger vector also closes the private Gate source role.
    try:
        from tools.regenerate_controller_gate_basis_fixture import build, verify_case, default_allowed
        contract = data.get("controller_gate_basis_contract")
        if contract != build(data):
            raise ValueError("controller Gate basis transcript drift")
        for case in contract["cases"]:
            verify_case(case)
        for decision in contract["default_decisions"]:
            if default_allowed(decision["binding"], decision["head"], decision["user_active"]) != decision["allowed"]:
                raise ValueError("default source decision")
    except Exception as error:
        lint.fail(FIXTURE_PATH, "controller Gate basis contract: " + str(error))
