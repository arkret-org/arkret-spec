"""Mutation tests for the Account Authority issuer-ledger genesis contract."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import account_status_issuer as gate


def _fixture() -> dict:
    return json.loads(gate.FIXTURE_PATH.read_text(encoding="utf-8"))


class AccountStatusIssuerGenesisLintTest(unittest.TestCase):
    def setUp(self) -> None:
        self.body = _fixture()
        self.real_load_json = gate.load_json

    def tearDown(self) -> None:
        gate.load_json = self.real_load_json

    def run_gate(self, body: dict) -> list[str]:
        gate.load_json = (
            lambda lint, path: body
            if path == gate.FIXTURE_PATH
            else self.real_load_json(lint, path)
        )
        lint = gate.Lint()
        gate.check_account_status_issuer_genesis(lint)
        return list(lint.errors)

    def point(self, body: dict) -> dict:
        return body["security_evidence"][0]["decision_points"][0]

    def test_committed_fixture_passes(self) -> None:
        self.assertEqual(self.run_gate(self.body), [])

    def test_station_checkpoint_wait_turns_the_gate_red(self) -> None:
        body = copy.deepcopy(self.body)
        body["genesis_rules"]["waits_for_station_checkpoint"] = True
        self.assertTrue(
            any("waits_for_station_checkpoint" in error for error in self.run_gate(body))
        )

    def test_realm_commit_wait_turns_the_gate_red(self) -> None:
        body = copy.deepcopy(self.body)
        body["genesis_rules"]["waits_for_realm_commit"] = True
        self.assertTrue(any("waits_for_realm_commit" in error for error in self.run_gate(body)))

    def test_reversed_requirement_turns_the_gate_red(self) -> None:
        body = copy.deepcopy(self.body)
        self.point(body)["requirement"] = (
            "The genesis record waits for the Station checkpoint and the RealmCommit."
        )
        self.assertTrue(any("no-wait contract" in error for error in self.run_gate(body)))

    def test_wrong_evidence_pointer_turns_the_gate_red(self) -> None:
        body = copy.deepcopy(self.body)
        self.point(body)["evidence"] = ["/ledger"]
        self.assertTrue(any("evidence must be exactly" in error for error in self.run_gate(body)))

    def test_runner_wires_the_gate(self) -> None:
        source = (ROOT / "tools" / "artifact_lint" / "runner.py").read_text(encoding="utf-8")
        self.assertIn("check_account_status_issuer_genesis(lint)", source)


if __name__ == "__main__":
    unittest.main()
