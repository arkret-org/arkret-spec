"""The executable registry-assertion table must bind to fixtures that ship.

`check_fixture_runner_contract` holds a table keyed by fixture `suite` and then
sweeps the fixture directory by file. The two are not the same thing: a table
entry naming a suite no file declares is never visited, so it neither passes nor
fails -- it is unreachable.

The gate had no tests at all. These cover the reconciliation and the per-file
binding it was already doing unverified.

Every mutation reads as a delta against the live baseline.
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import fixtures as gate

FIXTURE_ROOT = gate.ARTIFACTS / "fixtures"
PAYLOAD_COVERAGE = FIXTURE_ROOT / "event-kind-payload-coverage-fixture.json"


class FixtureRunnerSuiteContractTest(unittest.TestCase):
    def _run(self, path: Path | None = None, mutate=None) -> list[str]:
        original_load_json = gate.load_json
        documents = {}
        if mutate is not None:
            assert path is not None
            document = copy.deepcopy(original_load_json(gate.Lint(), path))
            mutate(document)
            documents[path.resolve()] = document

        def load_json_with_mutation(lint, target):
            return documents.get(target.resolve(), original_load_json(lint, target))

        gate.load_json = load_json_with_mutation
        try:
            lint = gate.Lint()
            gate.check_fixture_runner_contract(lint)
            return lint.errors
        finally:
            gate.load_json = original_load_json

    def _newly_reported(self, path: Path, mutate) -> list[str]:
        baseline = set(self._run())
        return sorted(set(self._run(path, mutate)) - baseline)

    # ---- the live baseline ----------------------------------------------

    def test_the_live_fixture_set_is_clean(self) -> None:
        self.assertEqual(self._run(), [])

    def test_every_required_suite_is_declared_by_a_file_on_disk(self) -> None:
        """The baseline above proves it through the gate. This proves it
        directly, so a future table entry cannot be excused as `the sweep did
        not reach it`."""
        declared = set()
        for path in sorted(FIXTURE_ROOT.glob("*.json")):
            document = gate.load_json(gate.Lint(), path)
            if isinstance(document, dict) and isinstance(document.get("suite"), str):
                declared.add(document["suite"])
        self.assertIn("error_code_registry_coverage_fixture", declared)
        self.assertIn("operation_registry_coverage_fixture", declared)
        self.assertIn("event_kind_payload_coverage_fixture", declared)

    # ---- the reconciliation ---------------------------------------------

    def test_a_required_suite_that_no_file_declares_is_reported(self) -> None:
        reported = self._newly_reported(
            PAYLOAD_COVERAGE, lambda document: document.__setitem__("suite", "renamed_suite")
        )
        self.assertTrue(
            any("event_kind_payload_coverage_fixture" in error for error in reported),
            reported,
        )
        self.assertTrue(
            any("no file declares" in error for error in reported),
            reported,
        )

    # ---- the per-file binding it was already doing -----------------------

    def test_dropping_a_bound_assertion_is_reported(self) -> None:
        def mutate(document: dict) -> None:
            document["assertions"] = [
                row
                for row in document["assertions"]
                if row.get("id") != "payload_schema_ref_resolves"
            ]

        reported = self._newly_reported(PAYLOAD_COVERAGE, mutate)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("not bound to the executable lint contract", reported[0])

    def test_a_registry_coverage_input_that_does_not_exist_is_reported(self) -> None:
        def mutate(document: dict) -> None:
            document["runner"]["inputs"] = ["registry/no-such-registry.json"]

        reported = self._newly_reported(PAYLOAD_COVERAGE, mutate)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("registry coverage input does not exist", reported[0])

    def test_an_unregistered_runner_kind_is_reported(self) -> None:
        def mutate(document: dict) -> None:
            document["runner"]["kind"] = "not_a_registered_runner"

        reported = self._newly_reported(PAYLOAD_COVERAGE, mutate)
        self.assertTrue(
            any("runner.kind is not registered" in error for error in reported), reported
        )


if __name__ == "__main__":
    unittest.main()
