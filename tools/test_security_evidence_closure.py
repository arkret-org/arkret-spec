"""Tests for the executable security evidence closure gate.

Report 0310 found `check_security_closure_fixture` still defined in
`fixtures.py` while `runner.py` no longer scheduled it, guarding a fixture that
had been deleted 6308 lines earlier in the same commit. Its obligation set was a
hardcoded Python `set` that had drifted to 15 vectors of which 5 no longer
existed anywhere. The successor keeps the obligations and moves the set into
`normative-clause-registry.json`, so adding a gated clause without evidence — or
deleting the evidence — is what turns the gate red.

Each test removes exactly one guarantee and asserts the gate fails, because a
gate nobody can make fail is indistinguishable from no gate.
"""

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

from tools.artifact_lint import security_evidence as gate
from tools.artifact_lint.core import Lint

VECTOR = "ak.vector.probe.obligation.v1"
CLAUSE = "AK-NC-999"
FIXTURE = "probe-fixture.json"


def clause_registry() -> dict:
    return {
        "version": "probe",
        "coverage_scope": {
            "included_categories": ["security", "privacy"],
            "executable_fixture_categories": ["security"],
            "executable_fixture_rule": "gated clauses need executable evidence",
            "executable_evidence_exemption_rule": "the exemption ledger only shrinks",
            "executable_evidence_exemptions": [],
        },
        "registry_rules": [],
        "clauses": [
            {
                "clause_id": CLAUSE,
                "status": "active",
                "category": "security",
                "source_anchor": "spec/v1/zh/probe.md#1-probe",
                "section_digest": "sha256:0",
                "requirement": "The probe refuses an unauthorized write.",
                "testability_grade": "vector",
                "evidence_refs": [VECTOR],
            }
        ],
    }


def vector_registry() -> dict:
    return {
        "version": "probe",
        "source_of_truth": True,
        "vectors": [
            {
                "vector_id": VECTOR,
                "status": "active",
                "source_refs": [f"spec/v1/artifacts/fixtures/{FIXTURE}"],
            }
        ],
    }


def fixture() -> dict:
    return {
        "suite": "probe",
        "fixture_kind": "semantic",
        "runner": {"kind": "named_suite", "entrypoint": "ak.suite.probe.v1"},
        "version": "probe",
        "covers_vectors": [VECTOR],
        "security_evidence": [
            {
                "vector_id": VECTOR,
                "clause_id": CLAUSE,
                "decision_points": [
                    {
                        "id": "unauthorized_write_refused",
                        "requirement": "An unauthorized write is refused before it reaches state.",
                        "evidence": ["/cases/0"],
                    }
                ],
            }
        ],
        "cases": [
            {
                "name": "unauthorized_write_refused",
                "given": "the writer holds no capability",
                "action": "submit the write",
                "decision": "reject",
                "reason": "unauthorized",
                "observed": "the submission outcome",
                "assertions": ["the write MUST NOT reach state"],
            }
        ],
    }


class SecurityEvidenceClosureTest(unittest.TestCase):
    def run_gate(
        self,
        *,
        clauses: dict | None = None,
        vectors: dict | None = None,
        fixtures: dict[str, dict] | None = None,
    ) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = root / "spec" / "v1" / "artifacts"
            (artifacts / "registry").mkdir(parents=True)
            (artifacts / "fixtures").mkdir(parents=True)

            def dump(path: Path, body: dict) -> None:
                path.write_text(
                    json.dumps(body, ensure_ascii=False), encoding="utf-8", newline="\n"
                )

            dump(
                artifacts / "registry" / "normative-clause-registry.json",
                clause_registry() if clauses is None else clauses,
            )
            dump(
                artifacts / "registry" / "vector-registry.json",
                vector_registry() if vectors is None else vectors,
            )
            for name, body in ({FIXTURE: fixture()} if fixtures is None else fixtures).items():
                dump(artifacts / "fixtures" / name, body)

            lint = Lint()
            with (
                mock.patch.object(gate, "ARTIFACTS", artifacts),
                mock.patch.object(gate, "ROOT", root),
            ):
                gate.check_security_evidence_closure(lint)
            return lint.errors

    def assertRedWith(self, errors: list[str], needle: str) -> None:
        self.assertTrue(any(needle in error for error in errors), errors)

    # ---------------------------------------------------------------- baseline

    def test_a_mapped_obligation_passes(self) -> None:
        self.assertEqual(self.run_gate(), [])

    def test_the_committed_spec_passes(self) -> None:
        lint = Lint()
        gate.check_security_evidence_closure(lint)
        self.assertEqual(lint.errors, [])

    # ------------------------------------------------- the obligation set is data

    def test_a_gated_clause_without_any_carrier_turns_the_gate_red(self) -> None:
        errors = self.run_gate(fixtures={})
        self.assertRedWith(errors, "has no fixture declaring a security_evidence entry")

    def test_deleting_the_evidence_entry_turns_the_gate_red(self) -> None:
        body = fixture()
        del body["security_evidence"]
        self.assertRedWith(
            self.run_gate(fixtures={FIXTURE: body}),
            "has no fixture declaring a security_evidence entry",
        )

    def test_adding_a_gated_clause_without_evidence_turns_the_gate_red(self) -> None:
        registry = clause_registry()
        added = copy.deepcopy(registry["clauses"][0])
        added["clause_id"] = "AK-NC-998"
        added["evidence_refs"] = ["ak.vector.probe.new_obligation.v1"]
        registry["clauses"].append(added)
        self.assertRedWith(self.run_gate(clauses=registry), "AK-NC-998")

    def test_an_empty_category_list_turns_the_gate_red(self) -> None:
        registry = clause_registry()
        registry["coverage_scope"]["executable_fixture_categories"] = []
        self.assertRedWith(
            self.run_gate(clauses=registry), "must be a non-empty string array"
        )

    def test_a_gated_category_outside_included_categories_turns_the_gate_red(self) -> None:
        registry = clause_registry()
        registry["coverage_scope"]["executable_fixture_categories"] = ["invented"]
        self.assertRedWith(self.run_gate(clauses=registry), "not in included_categories")

    def test_a_vector_that_is_no_longer_active_turns_the_gate_red(self) -> None:
        registry = vector_registry()
        registry["vectors"][0]["status"] = "withdrawn"
        self.assertRedWith(self.run_gate(vectors=registry), "not an active vector")

    def test_a_vector_missing_from_the_registry_turns_the_gate_red(self) -> None:
        registry = vector_registry()
        registry["vectors"] = []
        self.assertRedWith(self.run_gate(vectors=registry), "not an active vector")

    def test_source_refs_must_index_the_evidence_carrier(self) -> None:
        registry = vector_registry()
        registry["vectors"][0]["source_refs"] = ["spec/v1/zh/probe.md"]
        self.assertRedWith(self.run_gate(vectors=registry), "source_refs must index it")

    # ------------------------------------------------------ the mapping must hold

    def test_a_decision_point_pointing_at_nothing_turns_the_gate_red(self) -> None:
        body = fixture()
        body["security_evidence"][0]["decision_points"][0]["evidence"] = ["/cases/7"]
        self.assertRedWith(
            self.run_gate(fixtures={FIXTURE: body}), "does not resolve to fixture content"
        )

    def test_a_case_without_assertions_turns_the_gate_red(self) -> None:
        body = fixture()
        body["cases"][0]["assertions"] = []
        self.assertRedWith(
            self.run_gate(fixtures={FIXTURE: body}), "without per-case assertions"
        )

    def test_an_empty_decision_point_list_turns_the_gate_red(self) -> None:
        body = fixture()
        body["security_evidence"][0]["decision_points"] = []
        self.assertRedWith(
            self.run_gate(fixtures={FIXTURE: body}), "decision_points must be a non-empty array"
        )

    def test_a_decision_point_without_a_requirement_turns_the_gate_red(self) -> None:
        body = fixture()
        body["security_evidence"][0]["decision_points"][0]["requirement"] = "too short"
        self.assertRedWith(self.run_gate(fixtures={FIXTURE: body}), "must state the obligation")

    def test_duplicate_decision_point_ids_turn_the_gate_red(self) -> None:
        body = fixture()
        points = body["security_evidence"][0]["decision_points"]
        points.append(copy.deepcopy(points[0]))
        self.assertRedWith(self.run_gate(fixtures={FIXTURE: body}), "duplicates")

    def test_a_non_named_suite_carrier_turns_the_gate_red(self) -> None:
        body = fixture()
        body["runner"] = {"kind": "known_answer_tests"}
        self.assertRedWith(self.run_gate(fixtures={FIXTURE: body}), "runner.kind=named_suite")

    def test_evidence_outside_covers_vectors_turns_the_gate_red(self) -> None:
        body = fixture()
        body["covers_vectors"] = []
        self.assertRedWith(self.run_gate(fixtures={FIXTURE: body}), "must also appear in covers_vectors")

    def test_two_carriers_for_one_vector_turn_the_gate_red(self) -> None:
        other = fixture()
        self.assertRedWith(
            self.run_gate(fixtures={FIXTURE: fixture(), "zz-probe-fixture.json": other}),
            "already carries security evidence",
        )

    def test_a_clause_id_the_registry_does_not_know_turns_the_gate_red(self) -> None:
        body = fixture()
        body["security_evidence"][0]["clause_id"] = "AK-NC-997"
        self.assertRedWith(self.run_gate(fixtures={FIXTURE: body}), "unknown clause AK-NC-997")

    def test_a_clause_that_does_not_list_the_vector_turns_the_gate_red(self) -> None:
        registry = clause_registry()
        registry["clauses"][0]["evidence_refs"] = ["ak.vector.probe.other.v1"]
        errors = self.run_gate(clauses=registry)
        self.assertRedWith(errors, "does not list the vector in evidence_refs")

    # ----------------------------------------------------- the exemption ratchet

    def test_an_exemption_lets_a_known_gap_stay_enumerated(self) -> None:
        registry = clause_registry()
        registry["coverage_scope"]["executable_evidence_exemptions"] = [
            {"clause_id": CLAUSE, "vector_id": VECTOR, "reason": "no_fixture_carrier"}
        ]
        self.assertEqual(self.run_gate(clauses=registry, fixtures={}), [])

    def test_a_stale_exemption_turns_the_gate_red(self) -> None:
        registry = clause_registry()
        registry["coverage_scope"]["executable_evidence_exemptions"] = [
            {"clause_id": CLAUSE, "vector_id": VECTOR, "reason": "no_fixture_carrier"}
        ]
        self.assertRedWith(self.run_gate(clauses=registry), "the exemption list only shrinks")

    def test_an_exemption_without_a_reason_turns_the_gate_red(self) -> None:
        registry = clause_registry()
        registry["coverage_scope"]["executable_evidence_exemptions"] = [
            {"clause_id": CLAUSE, "vector_id": VECTOR}
        ]
        self.assertRedWith(self.run_gate(clauses=registry, fixtures={}), "reason must say why")

    def test_an_exemption_for_an_ungated_pair_turns_the_gate_red(self) -> None:
        registry = clause_registry()
        registry["coverage_scope"]["executable_evidence_exemptions"] = [
            {"clause_id": CLAUSE, "vector_id": "ak.vector.probe.unrelated.v1", "reason": "x"}
        ]
        self.assertRedWith(
            self.run_gate(clauses=registry), "not an active gated clause obligation"
        )

    def test_a_missing_exemption_list_turns_the_gate_red(self) -> None:
        registry = clause_registry()
        del registry["coverage_scope"]["executable_evidence_exemptions"]
        self.assertRedWith(
            self.run_gate(clauses=registry), "executable_evidence_exemptions must be an array"
        )

    def test_a_missing_exemption_rule_turns_the_gate_red(self) -> None:
        registry = clause_registry()
        del registry["coverage_scope"]["executable_evidence_exemption_rule"]
        self.assertRedWith(self.run_gate(clauses=registry), "only shrinks")


if __name__ == "__main__":
    unittest.main()
