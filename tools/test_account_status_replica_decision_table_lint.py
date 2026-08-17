"""Mutation tests for the account-status replica classification decision table.

The gap this table closes is a silent one: section 3.1 named the durable head as
the baseline for every branch except `same seq + same id`, so an implementation
could classify a resubmitted lower-sequence record against a retained history
row and answer `duplicate` where the rest of the ecosystem answers
`failed_precondition` + `account_status_record_stale`. Each case below
reintroduces that ambiguity in the shape it would actually take and asserts the
gate rejects it.
"""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import account_status_replica as lint_module

TABLE = lint_module.TABLE_PATH


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


class AccountStatusReplicaDecisionTableTest(unittest.TestCase):
    def setUp(self) -> None:
        self.table = _load(TABLE)
        self.real_load_json = lint_module.load_json

    def tearDown(self) -> None:
        lint_module.load_json = self.real_load_json

    def _run(self, table: object) -> list[str]:
        def fake_load_json(lint: object, path: Path) -> object:
            if path == TABLE:
                return table
            return self.real_load_json(lint, path)

        lint_module.load_json = fake_load_json
        lint = lint_module.Lint()
        lint_module.check_account_status_replica_decision_table(lint)
        return list(lint.errors)

    def _mutate(self) -> dict:
        return copy.deepcopy(self.table)

    def _row(self, table: dict, name: str) -> dict:
        for row in table["classifications"]:
            if row["name"] == name:
                return row
        raise AssertionError(f"missing classification {name!r}")

    def test_committed_table_passes(self) -> None:
        self.assertEqual(self._run(self.table), [])

    def test_baseline_is_the_durable_head(self) -> None:
        self.assertEqual(self.table["comparison_baseline"], "durable_replica_head")

    def test_history_row_baseline_is_rejected(self) -> None:
        table = self._mutate()
        self._row(table, "stale")["condition"] = (
            "submitted.status_seq < head.status_seq && "
            "submitted.account_status_record_id != history_row.account_status_record_id"
        )
        errors = self._run(table)
        self.assertTrue(any("only legal operands" in error for error in errors), errors)

    def test_duplicate_not_conditioned_on_head_is_rejected(self) -> None:
        table = self._mutate()
        self._row(table, "duplicate")["condition"] = (
            "submitted.status_seq == submitted.status_seq"
        )
        errors = self._run(table)
        self.assertTrue(
            any("duplicate row must be conditioned on the durable head" in error for error in errors),
            errors,
        )

    def test_stale_row_without_the_byte_identical_rule_is_rejected(self) -> None:
        table = self._mutate()
        self._row(table, "stale")["description"] = "The submission is below the durable head."
        errors = self._run(table)
        self.assertTrue(any("byte-identical" in error for error in errors), errors)

    def test_dropping_the_stale_branch_is_rejected(self) -> None:
        table = self._mutate()
        table["classifications"] = [
            row for row in table["classifications"] if row["name"] != "stale"
        ]
        errors = self._run(table)
        self.assertTrue(any("not exhaustive" in error for error in errors), errors)
        self.assertTrue(
            any("missing account_status_record_stale classification" in error for error in errors),
            errors,
        )

    def test_binding_rollback_after_a_sequence_row_is_rejected(self) -> None:
        table = self._mutate()
        rows = table["classifications"]
        rollback = rows.pop(0)
        rows.append(rollback)
        errors = self._run(table)
        self.assertTrue(
            any("must be evaluated before every sequence row" in error for error in errors), errors
        )

    def test_stale_marked_retryable_is_rejected(self) -> None:
        table = self._mutate()
        self._row(table, "stale")["retryable_for_exact_record"] = True
        errors = self._run(table)
        self.assertTrue(
            any("only dependency_missing may do that" in error for error in errors), errors
        )

    def test_rejected_row_with_a_replica_write_is_rejected(self) -> None:
        table = self._mutate()
        self._row(table, "fork_same_sequence")["replica_writes"] = "advance"
        errors = self._run(table)
        self.assertTrue(
            any("zero replica writes unless the outcome is accepted" in error for error in errors),
            errors,
        )

    def test_unregistered_reason_code_is_rejected(self) -> None:
        table = self._mutate()
        self._row(table, "stale")["reason_code"] = "account_status_record_outdated"
        errors = self._run(table)
        self.assertTrue(
            any("must be an account_status error code" in error for error in errors), errors
        )

    def test_head_absent_row_comparing_against_head_is_rejected(self) -> None:
        table = self._mutate()
        self._row(table, "genesis_admission")["condition"] = "submitted.status_seq == head.status_seq"
        errors = self._run(table)
        self.assertTrue(
            any("compares against head fields while head_state is 'absent'" in error for error in errors),
            errors,
        )

    def test_non_rejected_row_carrying_a_reason_code_is_rejected(self) -> None:
        table = self._mutate()
        self._row(table, "duplicate")["reason_code"] = "account_status_record_stale"
        errors = self._run(table)
        self.assertTrue(
            any("must carry null error_code and reason_code" in error for error in errors), errors
        )


class AccountStatusStaleErrorDescriptionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.real_load_json = lint_module.load_json
        self.error_codes = _load(lint_module.ERROR_CODE_PATH)

    def tearDown(self) -> None:
        lint_module.load_json = self.real_load_json

    def _run(self, error_codes: object) -> list[str]:
        def fake_load_json(lint: object, path: Path) -> object:
            if path == lint_module.ERROR_CODE_PATH:
                return error_codes
            return self.real_load_json(lint, path)

        lint_module.load_json = fake_load_json
        lint = lint_module.Lint()
        lint_module.check_account_status_replica_decision_table(lint)
        return list(lint.errors)

    def test_description_without_the_byte_identical_rule_is_rejected(self) -> None:
        codes = copy.deepcopy(self.error_codes)
        for row in codes["reason_codes"]:
            if row.get("code") == "account_status_record_stale":
                row["description"] = (
                    "A lower status_seq than the durable replica head. "
                    "See registry/account-status-replica-decision-table.json."
                )
        errors = self._run(codes)
        self.assertTrue(any("byte-identical" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
