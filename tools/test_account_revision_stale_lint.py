"""Mutation checks for the independently required stale-prefix recovery."""

import copy
import json
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint.account_revision_stale import CASE, FIXTURE, MAPPING, SCHEMA, check_account_revision_stale, contract_errors
from tools.artifact_lint.core import Lint


class AccountRevisionStaleTests(unittest.TestCase):
    def setUp(self):
        self.schema, self.mapping, self.fixture = [json.loads(path.read_text(encoding="utf-8")) for path in (SCHEMA, MAPPING, FIXTURE)]

    def test_current_contract(self):
        lint = Lint()
        check_account_revision_stale(lint)
        self.assertEqual(lint.errors, [])

    def test_case_mutations_fail(self):
        for field, value in [
            ("baseline_redone", True),
            ("discard_old_cursor", True),
            ("checkpoint_advanced_on_error", True),
            ("delivery_acks_invalidated", True),
            ("mls_private_state_deleted", True),
            ("fresh_process_readback", False),
            ("expected_client_action", "wait_without_backfill"),
        ]:
            with self.subTest(field=field):
                fixture = copy.deepcopy(self.fixture)
                case = next(row for row in fixture["reconnect"] if row["name"] == CASE)
                case[field] = value
                self.assertTrue(contract_errors(self.schema, self.mapping, fixture))

    def test_replaced_continuation_fails(self):
        case = next(row for row in self.fixture["reconnect"] if row["name"] == CASE)
        case["response_problem"]["continuation_cursor"] = "ak:cursor:replaced"
        self.assertTrue(contract_errors(self.schema, self.mapping, self.fixture))

    def test_missing_case_or_required_carrier_fails(self):
        self.fixture["reconnect"] = [row for row in self.fixture["reconnect"] if row["name"] != CASE]
        self.assertTrue(contract_errors(self.schema, self.mapping, self.fixture))
        self.schema["$defs"]["account_revision_stale_problem"]["allOf"][1]["required"] = []
        self.assertIn("carrier must require continuation_cursor", contract_errors(self.schema, self.mapping, self.fixture))


if __name__ == "__main__":
    unittest.main()
