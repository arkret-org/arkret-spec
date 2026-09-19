"""Closure gate for the Account Authority issuer-ledger genesis contract.

The executable carrier once said that genesis waits for Station checkpoint and
RealmCommit while the structured evidence and normative prose both said the
opposite.  This gate keeps the prose-bearing decision point and its structured
evidence on the same fail-closed, issuer-private no-wait contract.
"""

from __future__ import annotations

from .core import ARTIFACTS, Lint, load_json


FIXTURE_PATH = ARTIFACTS / "fixtures" / "account-status-issuer-ledger-fixture.json"

GENESIS_REQUIREMENT = (
    "The genesis record is created inside the binding commit transaction, carries no "
    "predecessor, and does not wait for the Station checkpoint or the RealmCommit."
)


def check_account_status_issuer_genesis(lint: Lint) -> None:
    data = load_json(lint, FIXTURE_PATH)
    if not isinstance(data, dict):
        return

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
