"""Mutation tests for the protocol-level clock-tolerance closure."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import time_tolerances as gate
from tools.artifact_lint.core import Lint

SCENARIO = "ak.time_tolerance.probe.v1"
TOLERANCE = "ak.time_tolerance.probe_limit.v1"


def catalog() -> dict:
    return {
        "protocol_time_tolerance_registry": {
            "source_of_truth": True,
            "tolerances": [
                {
                    "tolerance_id": TOLERANCE,
                    "name": "probe_limit_ms",
                    "value": 30,
                    "unit": "milliseconds",
                }
            ],
            "scenarios": [
                {
                    "scenario_id": SCENARIO,
                    "tolerance_id": TOLERANCE,
                    "direction": "future_only",
                    "comparison": "probe <= now + tolerance, inclusive",
                    "prose_bindings": ["zh/probe.md#probe"],
                    "machine_bindings": ["schemas/probe.schema.json#/properties/instant"],
                    "boundary_cases": [
                        {
                            "case_id": "at_limit",
                            "boundary": "future",
                            "beyond_limit_ms": 0,
                            "accepted": True,
                        },
                        {
                            "case_id": "beyond_limit",
                            "boundary": "future",
                            "beyond_limit_ms": 1,
                            "accepted": False,
                        },
                    ],
                }
            ],
            "fixture": "fixtures/probe.json",
        }
    }


def fixture() -> dict:
    return {
        "source_registry": "registry/contract-registry.json#protocol_time_tolerance_registry",
        "runner": {"kind": "named_suite", "entrypoint": "ak.suite.protocol.time_tolerance.v1"},
        "cases": [
            {
                "case_id": "at_limit",
                "scenario_id": SCENARIO,
                "boundary": "future",
                "offset_ms": 30,
                "expected": {"accepted": True},
            },
            {
                "case_id": "beyond_limit",
                "scenario_id": SCENARIO,
                "boundary": "future",
                "offset_ms": 31,
                "expected": {"accepted": False},
            },
        ],
    }


class ProtocolTimeToleranceClosureTest(unittest.TestCase):
    def run_gate(self, data: dict | None = None, kat: dict | None = None, prose: str | None = None) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = root / "artifacts"
            (artifacts / "registry").mkdir(parents=True)
            (artifacts / "fixtures").mkdir()
            (artifacts / "schemas").mkdir()
            (root / "zh").mkdir()
            (artifacts / "registry" / "contract-registry.json").write_text(
                json.dumps(data or catalog()), encoding="utf-8", newline="\n"
            )
            (artifacts / "fixtures" / "probe.json").write_text(
                json.dumps(kat or fixture()), encoding="utf-8", newline="\n"
            )
            (artifacts / "schemas" / "probe.schema.json").write_text(
                json.dumps({"properties": {"instant": {"description": SCENARIO}}}),
                encoding="utf-8",
                newline="\n",
            )
            (root / "zh" / "probe.md").write_text(prose or f"# probe\n\n`{SCENARIO}`\n", encoding="utf-8", newline="\n")
            lint = Lint()
            with (
                mock.patch.object(gate, "ARTIFACTS", artifacts),
                mock.patch.object(gate, "SPEC_ROOT", root),
                mock.patch.object(gate, "CONTRACT", artifacts / "registry" / "contract-registry.json"),
                mock.patch.object(gate, "EXPECTED_TOLERANCE_NAMES", {TOLERANCE: "probe_limit_ms"}),
                mock.patch.object(
                    gate,
                    "EXPECTED_SCENARIOS",
                    {SCENARIO: (TOLERANCE, "future_only", {("future", 0, True), ("future", 1, False)})},
                ),
            ):
                gate.check_protocol_time_tolerance_closure(lint)
            return lint.errors

    def assertRed(self, errors: list[str], text: str) -> None:
        self.assertTrue(any(text in error for error in errors), errors)

    def test_complete_projection_passes(self) -> None:
        self.assertEqual(self.run_gate(), [])

    def test_changed_canonical_limit_turns_fixture_red(self) -> None:
        data = catalog()
        data["protocol_time_tolerance_registry"]["tolerances"][0]["value"] = 31
        self.assertRed(self.run_gate(data=data), "offset_ms does not project")

    def test_boundary_equality_must_be_accepted(self) -> None:
        data = catalog()
        data["protocol_time_tolerance_registry"]["scenarios"][0]["boundary_cases"][0]["accepted"] = False
        self.assertRed(self.run_gate(data=data), "true at the limit")

    def test_one_millisecond_beyond_must_be_rejected(self) -> None:
        kat = fixture()
        kat["cases"][1]["expected"]["accepted"] = True
        self.assertRed(self.run_gate(kat=kat), "boundary verdict")

    def test_missing_conjunctive_boundary_case_is_red(self) -> None:
        kat = fixture()
        kat["cases"].pop()
        self.assertRed(self.run_gate(kat=kat), "missing conjunctive boundary cases")

    def test_wrong_direction_is_red(self) -> None:
        data = catalog()
        data["protocol_time_tolerance_registry"]["scenarios"][0]["direction"] = (
            "symmetric_not_before_and_expiry"
        )
        self.assertRed(self.run_gate(data=data), "changes the canonical tolerance or direction")

    def test_scenario_set_is_closed(self) -> None:
        data = catalog()
        data["protocol_time_tolerance_registry"]["scenarios"][0]["scenario_id"] = (
            "ak.time_tolerance.renamed.v1"
        )
        self.assertRed(self.run_gate(data=data), "scenarios must be the closed protocol set")

    def test_prose_must_cite_scenario(self) -> None:
        self.assertRed(self.run_gate(prose="# probe\n"), "prose binding does not cite")

    def test_machine_binding_must_cite_scenario(self) -> None:
        data = catalog()
        data["protocol_time_tolerance_registry"]["scenarios"][0]["machine_bindings"] = [
            "schemas/probe.schema.json#/properties/missing"
        ]
        self.assertRed(self.run_gate(data=data), "machine binding does not cite")

    def test_runner_is_required(self) -> None:
        kat = fixture()
        del kat["runner"]
        self.assertRed(self.run_gate(kat=kat), "no registered runner")

    def test_artifact_runner_invokes_the_gate(self) -> None:
        source = (ROOT / "tools" / "artifact_lint" / "runner.py").read_text(encoding="utf-8")
        self.assertIn("check_protocol_time_tolerance_closure(lint)", source)


if __name__ == "__main__":
    unittest.main()
