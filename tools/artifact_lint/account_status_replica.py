"""Closure gate for the account-status replica classification decision table.

zh/identity/account-lifecycle.md section 3.1 previously left the comparison
baseline of the `same seq + same id is duplicate` branch unstated, so a receiver
could classify against a retained history row instead of the durable head and
return `duplicate` where another implementation returned
`failed_precondition` + `account_status_record_stale`. The decision table is now
the canonical machine projection of that classification; this module keeps it
exhaustive, keeps every branch anchored on the durable head, and keeps the typed
reason codes and outcomes inside their registered vocabularies.
"""

from __future__ import annotations

import re

from .core import (
    ARTIFACTS,
    SPEC_ROOT,
    Any,
    Lint,
    load_json,
    read_text,
)


TABLE_PATH = ARTIFACTS / "registry" / "account-status-replica-decision-table.json"

PROSE_PATH = SPEC_ROOT / "zh" / "identity" / "account-lifecycle.md"

ERROR_CODE_PATH = ARTIFACTS / "registry" / "error-code-registry.json"

OPERATIONS_SCHEMA_PATH = ARTIFACTS / "schemas" / "account-operations.schema.json"

BASELINE = "durable_replica_head"

# The submission and the durable head are the only legal operands. A condition
# that names anything else has reintroduced the second baseline this table
# exists to remove.
CONDITION_OPERAND_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)+")

ALLOWED_OPERAND_ROOTS = frozenset({"submitted", "head"})

OUTCOMES_WITHOUT_ERROR = frozenset({"accepted", "duplicate", "dependency_missing"})

REQUIRED_ROW_FIELDS = (
    "name",
    "head_state",
    "condition",
    "outcome",
    "error_code",
    "reason_code",
    "replica_writes",
    "retryable_for_exact_record",
    "description",
)

# Exhaustiveness contract: with a durable head present every sequence relation
# must be classified, and the head-absent case must classify both the genesis
# record and everything above it.
REQUIRED_HEAD_PRESENT_CONDITIONS = (
    "submitted.status_seq < head.status_seq",
    "submitted.status_seq == head.status_seq",
    "submitted.status_seq == head.status_seq + 1",
    "submitted.status_seq > head.status_seq + 1",
)

REQUIRED_HEAD_ABSENT_CONDITIONS = (
    "submitted.status_seq == 1",
    "submitted.status_seq > 1",
)


def check_account_status_replica_decision_table(lint: Lint) -> None:
    data = load_json(lint, TABLE_PATH)
    if not isinstance(data, dict):
        return

    if data.get("source_of_truth") is not True:
        lint.fail(TABLE_PATH, "source_of_truth must be true")
    if not isinstance(data.get("description"), str) or not data["description"].strip():
        lint.fail(TABLE_PATH, "description must be a non-empty string")
    if data.get("comparison_baseline") != BASELINE:
        lint.fail(TABLE_PATH, f"comparison_baseline must be {BASELINE!r}")
    rules = data.get("registry_rules")
    if not isinstance(rules, list) or not rules or any(
        not isinstance(rule, str) or not rule.strip() for rule in rules
    ):
        lint.fail(TABLE_PATH, "registry_rules must be a non-empty string array")

    rows = data.get("classifications")
    if not isinstance(rows, list) or not rows:
        lint.fail(TABLE_PATH, "classifications must be a non-empty array")
        return

    known_reason_codes = _account_status_reason_codes(lint)
    known_outcomes = _publication_outcome_values(lint)

    seen_names: set[str] = set()
    conditions_by_head_state: dict[str, list[str]] = {"present": [], "absent": []}
    stale_row: dict[str, Any] | None = None
    duplicate_row: dict[str, Any] | None = None
    rollback_index: int | None = None
    first_sequence_index: int | None = None

    for index, row in enumerate(rows):
        label = f"classifications[{index}]"
        if not isinstance(row, dict):
            lint.fail(TABLE_PATH, f"{label} must be an object")
            continue

        missing = [field for field in REQUIRED_ROW_FIELDS if field not in row]
        if missing:
            lint.fail(TABLE_PATH, f"{label} missing field(s): {', '.join(missing)}")
            continue
        unknown = sorted(set(row) - set(REQUIRED_ROW_FIELDS))
        if unknown:
            lint.fail(TABLE_PATH, f"{label} declares unknown field(s): {', '.join(unknown)}")

        name = row["name"]
        if not isinstance(name, str) or not name:
            lint.fail(TABLE_PATH, f"{label}.name must be a non-empty string")
            continue
        if name in seen_names:
            lint.fail(TABLE_PATH, f"{label}.name duplicates {name!r}")
        seen_names.add(name)

        head_state = row["head_state"]
        if head_state not in {"present", "absent"}:
            lint.fail(TABLE_PATH, f"{label}.head_state must be 'present' or 'absent'")
            head_state = None

        condition = row["condition"]
        if not isinstance(condition, str) or not condition.strip():
            lint.fail(TABLE_PATH, f"{label}.condition must be a non-empty string")
        else:
            if head_state is not None:
                conditions_by_head_state[head_state].append(condition)
            for operand in CONDITION_OPERAND_RE.findall(condition):
                root = operand.split(".", 1)[0]
                if root not in ALLOWED_OPERAND_ROOTS:
                    lint.fail(
                        TABLE_PATH,
                        f"{label}.condition references {operand!r}; the submission and the durable head "
                        "are the only legal operands, a retained history row is not a baseline",
                    )
            if head_state == "absent" and "head." in condition:
                lint.fail(
                    TABLE_PATH,
                    f"{label}.condition compares against head fields while head_state is 'absent'",
                )

        outcome = row["outcome"]
        error_code = row["error_code"]
        reason_code = row["reason_code"]
        if outcome == "rejected":
            if error_code != "failed_precondition":
                lint.fail(TABLE_PATH, f"{label}.error_code must be 'failed_precondition' for a rejected row")
            if not isinstance(reason_code, str) or reason_code not in known_reason_codes:
                lint.fail(
                    TABLE_PATH,
                    f"{label}.reason_code must be an account_status error code: {reason_code!r}",
                )
        elif outcome in OUTCOMES_WITHOUT_ERROR:
            if known_outcomes and outcome not in known_outcomes:
                lint.fail(
                    TABLE_PATH,
                    f"{label}.outcome {outcome!r} is not an account_status_publication_outcome status value",
                )
            if error_code is not None or reason_code is not None:
                lint.fail(TABLE_PATH, f"{label} non-rejected row must carry null error_code and reason_code")
        else:
            lint.fail(
                TABLE_PATH,
                f"{label}.outcome must be one of accepted, duplicate, dependency_missing, rejected",
            )

        if row["replica_writes"] not in {"advance", "none"}:
            lint.fail(TABLE_PATH, f"{label}.replica_writes must be 'advance' or 'none'")
        if outcome != "accepted" and row["replica_writes"] != "none":
            lint.fail(TABLE_PATH, f"{label} must perform zero replica writes unless the outcome is accepted")

        retryable = row["retryable_for_exact_record"]
        if not isinstance(retryable, bool):
            lint.fail(TABLE_PATH, f"{label}.retryable_for_exact_record must be a boolean")
        elif retryable and outcome != "dependency_missing":
            lint.fail(
                TABLE_PATH,
                f"{label} keeps the exact record retryable; only dependency_missing may do that",
            )

        if not isinstance(row["description"], str) or not row["description"].strip():
            lint.fail(TABLE_PATH, f"{label}.description must be a non-empty string")

        if reason_code == "account_status_binding_rollback":
            rollback_index = index if rollback_index is None else rollback_index
        elif isinstance(condition, str) and "status_seq" in condition and first_sequence_index is None:
            first_sequence_index = index
        if reason_code == "account_status_record_stale":
            stale_row = row
        if outcome == "duplicate":
            duplicate_row = row

    for head_state, required in (
        ("present", REQUIRED_HEAD_PRESENT_CONDITIONS),
        ("absent", REQUIRED_HEAD_ABSENT_CONDITIONS),
    ):
        joined = " || ".join(conditions_by_head_state[head_state])
        for fragment in required:
            if fragment not in joined:
                lint.fail(
                    TABLE_PATH,
                    f"head_state={head_state} classification is not exhaustive: no row covers {fragment!r}",
                )

    if rollback_index is None:
        lint.fail(TABLE_PATH, "missing account_status_binding_rollback classification")
    elif first_sequence_index is not None and rollback_index > first_sequence_index:
        lint.fail(
            TABLE_PATH,
            "the binding_version rollback row must be evaluated before every sequence row so a "
            "rolled-back binding can never be written by the advance branch",
        )

    if stale_row is None:
        lint.fail(TABLE_PATH, "missing account_status_record_stale classification")
    elif "byte-identical" not in str(stale_row.get("description", "")):
        lint.fail(
            TABLE_PATH,
            "the stale row description must state that a byte-identical retained history row does not "
            "downgrade the outcome to duplicate",
        )

    if duplicate_row is None:
        lint.fail(TABLE_PATH, "missing duplicate classification")
    elif "head.status_seq" not in str(duplicate_row.get("condition", "")):
        lint.fail(TABLE_PATH, "the duplicate row must be conditioned on the durable head sequence")

    _check_prose_binding(lint)
    _check_stale_error_description(lint)


def _account_status_reason_codes(lint: Lint) -> set[str]:
    data = load_json(lint, ERROR_CODE_PATH)
    if not isinstance(data, dict):
        return set()
    codes: set[str] = set()
    for row in data.get("reason_codes", []):
        if not isinstance(row, dict):
            continue

        applies_to = row.get("applies_to")
        code = row.get("code")
        if isinstance(code, str) and isinstance(applies_to, list) and "account_status" in applies_to:
            codes.add(code)
    return codes


def _publication_outcome_values(lint: Lint) -> set[str]:
    data = load_json(lint, OPERATIONS_SCHEMA_PATH)
    if not isinstance(data, dict):
        return set()
    outcome = (data.get("$defs") or {}).get("account_status_publication_outcome")
    if not isinstance(outcome, dict):
        return set()
    status = (outcome.get("properties") or {}).get("status")
    if not isinstance(status, dict):
        return set()
    values = status.get("enum")
    return set(values) if isinstance(values, list) else set()


def _check_prose_binding(lint: Lint) -> None:
    try:
        text = read_text(PROSE_PATH)
    except Exception as exc:  # pragma: no cover - unreadable prose is a hard stop
        lint.fail(PROSE_PATH, f"could not read account lifecycle prose: {exc}")
        return
    if "account-status-replica-decision-table.json" not in text:
        lint.fail(
            PROSE_PATH,
            "section 3.1 must reference registry/account-status-replica-decision-table.json as the "
            "canonical machine projection of the receiver classification",
        )
    if "durable replica head" not in text:
        lint.fail(
            PROSE_PATH,
            "section 3.1 must name the durable replica head as the single comparison baseline",
        )


def _check_stale_error_description(lint: Lint) -> None:
    data = load_json(lint, ERROR_CODE_PATH)
    if not isinstance(data, dict):
        return
    for row in data.get("reason_codes", []):
        if not isinstance(row, dict) or row.get("code") != "account_status_record_stale":
            continue
        description = row.get("description")
        if not isinstance(description, str):
            lint.fail(ERROR_CODE_PATH, "account_status_record_stale.description must be a string")
            return
        if "byte-identical" not in description:
            lint.fail(
                ERROR_CODE_PATH,
                "account_status_record_stale.description must state that the reason applies even when "
                "the submitted record is byte-identical to a retained history row",
            )
        if "account-status-replica-decision-table.json" not in description:
            lint.fail(
                ERROR_CODE_PATH,
                "account_status_record_stale.description must point at the ordered classification table",
            )
        return
    lint.fail(ERROR_CODE_PATH, "missing error code row: account_status_record_stale")
