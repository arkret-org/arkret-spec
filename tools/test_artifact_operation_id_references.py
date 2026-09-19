"""Mutation tests for the artifact operation-id reference gate.

A fixture that names an operation id is telling a conformance runner which
entry point to exercise. Report 1600 found three artifacts naming ids that
`operation-registry.json` does not list, one of them the sole surviving trace
of a wire surface deleted along with its prose. The gate that now forbids an
unresolvable reference is only worth its runtime if each rule can be made to
fail, so every rule here is exercised against a green probe tree and against a
single-mutation tree that violates exactly that rule.

The committed spec is asserted green as well, so a rule that quietly stops
matching real artifacts shows up here rather than as silent permission.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from artifact_lint import bindings as gate
from artifact_lint import core
from artifact_lint.core import Lint

REGISTRY = {
    "version": "probe",
    "operations": [
        {"operation_id": "ak.self.events.command.submit.v1"},
        {"operation_id": "ak.server.read.describe.v1"},
    ],
}

FIXTURE = {
    "suite": "probe",
    "cases": [{"operation_id": "ak.self.events.command.submit.v1"}],
}

EMPTY_LEDGER: dict = {"version": "probe", "references": []}

NEGATIVE_ROW = {
    "token": "ak.self.events.command.unregistered.v1",
    "artifact": "spec/v1/artifacts/fixtures/probe-fixture.json",
    "kind": "negative_token",
    "case": "reject_unregistered_operation_token",
    "reason": "the case asserts the refusal",
}

OWNED_ROW = {
    "token": "ak.self.events.read.delivery_status.v1",
    "artifact": "spec/v1/artifacts/fixtures/probe-fixture.json",
    "kind": "owned_gap",
    "owner_report": "arkret-work/tasks/spec-open/probe.md",
    "reason": "the read surface was deleted with its prose",
}


class ArtifactOperationIdReferenceTest(unittest.TestCase):
    """Each test mutates one thing and asserts the gate notices."""

    def run_gate(
        self,
        *,
        registry: dict | None = None,
        fixtures: dict[str, dict] | None = None,
        ledger: dict | None = None,
    ) -> list[str]:
        registry = REGISTRY if registry is None else registry
        fixtures = {"fixtures/probe-fixture.json": FIXTURE} if fixtures is None else fixtures
        ledger = EMPTY_LEDGER if ledger is None else ledger

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            artifacts_root = root / "spec" / "v1" / "artifacts"
            (artifacts_root / "registry").mkdir(parents=True)
            (artifacts_root / "registry" / "operation-registry.json").write_text(
                json.dumps(registry, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            for name, document in fixtures.items():
                path = artifacts_root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                    newline="\n",
                )
            tools = root / "tools"
            tools.mkdir()
            ledger_path = tools / "artifact-operation-id-reference-exemptions.json"
            if ledger is not False:
                ledger_path.write_text(
                    json.dumps(ledger, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                    newline="\n",
                )

            lint = Lint()
            with mock.patch.object(gate, "ARTIFACTS", artifacts_root), mock.patch.object(
                gate, "OPERATION_ID_REFERENCE_LEDGER_PATH", ledger_path
            ), mock.patch.object(core, "ROOT", root):
                gate.check_artifact_operation_id_references(lint)
            return lint.errors

    # ---- baselines -------------------------------------------------------

    def test_the_probe_tree_is_green(self) -> None:
        """Without a mutation nothing fires, so every red below is the mutation."""
        self.assertEqual([], self.run_gate())

    def test_the_committed_spec_is_green(self) -> None:
        """The real tree passes, so the rule still matches real artifacts."""
        lint = Lint()
        gate.check_artifact_operation_id_references(lint)
        self.assertEqual([], lint.errors)

    def test_the_committed_ledger_carries_only_documented_kinds(self) -> None:
        """Every real row parses, so no row is silently ignored at runtime."""
        document = json.loads(
            gate.OPERATION_ID_REFERENCE_LEDGER_PATH.read_text(encoding="utf-8")
        )
        rows = document["references"]
        self.assertTrue(rows, "an empty ledger would make the gate untested in practice")
        for row in rows:
            self.assertIn(row["kind"], {"negative_token", "owned_gap"})
            if row["kind"] == "owned_gap":
                self.assertTrue(row["owner_report"].startswith("arkret-work/tasks/"))
            else:
                self.assertNotIn("owner_report", row)

    # ---- the main rule ---------------------------------------------------

    def test_an_unregistered_reference_turns_the_gate_red(self) -> None:
        fixture = {
            "suite": "probe",
            "cases": [{"operation_id": "ak.self.events.read.delivery_status.v1"}],
        }
        errors = self.run_gate(fixtures={"fixtures/probe-fixture.json": fixture})
        self.assertEqual(1, len(errors), errors)
        self.assertIn("ak.self.events.read.delivery_status.v1", errors[0])

    def test_a_reference_inside_free_text_is_caught_too(self) -> None:
        """The dangling reference report found one inside a case's action string."""
        fixture = {
            "suite": "probe",
            "semantic_cases": [
                {"action": "QUERY ak.self.events.read.delivery_status.v1"}
            ],
        }
        errors = self.run_gate(fixtures={"fixtures/probe-fixture.json": fixture})
        self.assertEqual(1, len(errors), errors)

    def test_an_unknown_version_suffix_is_a_distinct_token(self) -> None:
        """ak.server.read.describe.v9 must not resolve through describe.v1."""
        fixture = {"suite": "probe", "cases": [{"x": "ak.server.read.describe.v9"}]}
        errors = self.run_gate(fixtures={"fixtures/probe-fixture.json": fixture})
        self.assertEqual(1, len(errors), errors)
        self.assertIn("ak.server.read.describe.v9", errors[0])

    def test_a_name_outside_the_registered_surfaces_is_not_scanned(self) -> None:
        """Other ak.* families are governed by their own naming rules."""
        fixture = {"suite": "probe", "cases": [{"x": "ak.vector.fanout.route_miss.v1"}]}
        self.assertEqual(
            [], self.run_gate(fixtures={"fixtures/probe-fixture.json": fixture})
        )

    def test_the_registry_itself_is_not_scanned_against_itself(self) -> None:
        """Otherwise every row would report its own id as unresolved prose."""
        self.assertEqual([], self.run_gate())

    # ---- the ledger ------------------------------------------------------

    def test_a_ledger_row_licenses_exactly_its_own_artifact(self) -> None:
        fixture = {
            "suite": "probe",
            "cases": [{"operation_id": "ak.self.events.read.delivery_status.v1"}],
        }
        self.assertEqual(
            [],
            self.run_gate(
                fixtures={"fixtures/probe-fixture.json": fixture},
                ledger={"version": "probe", "references": [OWNED_ROW]},
            ),
        )

    def test_the_same_token_in_another_artifact_is_still_red(self) -> None:
        """An exemption is per artifact, so it cannot shield a second reference."""
        fixture = {
            "suite": "probe",
            "cases": [{"operation_id": "ak.self.events.read.delivery_status.v1"}],
        }
        errors = self.run_gate(
            fixtures={
                "fixtures/probe-fixture.json": fixture,
                "fixtures/other-fixture.json": fixture,
            },
            ledger={"version": "probe", "references": [OWNED_ROW]},
        )
        self.assertEqual(1, len(errors), errors)
        self.assertIn("other-fixture.json", errors[0])

    def test_an_owned_gap_without_an_owner_is_rejected(self) -> None:
        row = dict(OWNED_ROW)
        row.pop("owner_report")
        fixture = {
            "suite": "probe",
            "cases": [{"operation_id": "ak.self.events.read.delivery_status.v1"}],
        }
        errors = self.run_gate(
            fixtures={"fixtures/probe-fixture.json": fixture},
            ledger={"version": "probe", "references": [row]},
        )
        self.assertEqual(2, len(errors), errors)
        self.assertIn("owner_report", errors[0])

    def test_a_negative_token_must_name_its_case(self) -> None:
        row = dict(NEGATIVE_ROW)
        row.pop("case")
        fixture = {
            "suite": "probe",
            "cases": [{"operation_id": "ak.self.events.command.unregistered.v1"}],
        }
        errors = self.run_gate(
            fixtures={"fixtures/probe-fixture.json": fixture},
            ledger={"version": "probe", "references": [row]},
        )
        self.assertEqual(2, len(errors), errors)
        self.assertIn("asserts the rejection", errors[0])

    def test_a_negative_token_may_not_claim_an_owner(self) -> None:
        """A deliberate refusal case is not a gap waiting to be closed."""
        row = dict(NEGATIVE_ROW)
        row["owner_report"] = "arkret-work/tasks/spec-open/probe.md"
        fixture = {
            "suite": "probe",
            "cases": [{"operation_id": "ak.self.events.command.unregistered.v1"}],
        }
        errors = self.run_gate(
            fixtures={"fixtures/probe-fixture.json": fixture},
            ledger={"version": "probe", "references": [row]},
        )
        self.assertEqual(2, len(errors), errors)
        self.assertIn("no owner_report", errors[0])

    def test_an_unknown_kind_is_rejected(self) -> None:
        row = dict(OWNED_ROW)
        row["kind"] = "historical"
        fixture = {
            "suite": "probe",
            "cases": [{"operation_id": "ak.self.events.read.delivery_status.v1"}],
        }
        errors = self.run_gate(
            fixtures={"fixtures/probe-fixture.json": fixture},
            ledger={"version": "probe", "references": [row]},
        )
        self.assertEqual(2, len(errors), errors)
        self.assertIn("kind must be", errors[0])

    def test_a_row_without_a_reason_is_rejected(self) -> None:
        row = dict(OWNED_ROW)
        row["reason"] = "   "
        fixture = {
            "suite": "probe",
            "cases": [{"operation_id": "ak.self.events.read.delivery_status.v1"}],
        }
        errors = self.run_gate(
            fixtures={"fixtures/probe-fixture.json": fixture},
            ledger={"version": "probe", "references": [row]},
        )
        self.assertEqual(2, len(errors), errors)
        self.assertIn("no reason", errors[0])

    # ---- the ratchet self-checks ----------------------------------------

    def test_a_row_whose_token_became_registered_turns_the_gate_red(self) -> None:
        row = dict(OWNED_ROW)
        row["token"] = "ak.self.events.command.submit.v1"
        errors = self.run_gate(ledger={"version": "probe", "references": [row]})
        self.assertEqual(1, len(errors), errors)
        self.assertIn("registered now", errors[0])

    def test_a_registered_negative_token_says_the_case_is_contradicted(self) -> None:
        row = dict(NEGATIVE_ROW)
        row["token"] = "ak.self.events.command.submit.v1"
        errors = self.run_gate(ledger={"version": "probe", "references": [row]})
        self.assertEqual(1, len(errors), errors)
        self.assertIn("contradicts", errors[0])

    def test_a_row_no_artifact_carries_any_more_turns_the_gate_red(self) -> None:
        errors = self.run_gate(ledger={"version": "probe", "references": [OWNED_ROW]})
        self.assertEqual(1, len(errors), errors)
        self.assertIn("does not name the token", errors[0])

    def test_an_unparseable_ledger_turns_the_gate_red(self) -> None:
        errors = self.run_gate(ledger=False)
        self.assertTrue(errors)
        self.assertIn("unable to parse ledger", errors[0])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
