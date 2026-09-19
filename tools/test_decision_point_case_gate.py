"""Tests for the SDK decision-point-to-fixture-case reachability gate.

Report 1955 found five conformance vectors that existed only in the prose and the
registry: clauses named them as evidence, and no fixture under
``artifacts/fixtures/`` carried a single byte of them. Closing that produced a
carrier for each vector, but a carrier is a file, and a file proves nothing about
whether the obligation is observed inside it. ``check_sdk_decision_point_cases``
is the gate for the last two hops, so every test here removes exactly one link in
``clause -> decision point -> active vector -> carrier -> case -> runner`` and
asserts the gate turns red. A gate nobody can make fail is indistinguishable from
no gate.

The probe tree is deliberately tiny: one clause, two decision points, one vector,
one carrier. That keeps each mutation about one link rather than about the shape
of the committed spec, which the baseline test covers separately.
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

from tools.artifact_lint import decision_point_cases as gate
from tools.artifact_lint.core import Lint

CLAUSE = "AK-SDK-777"
VECTOR = "ak.vector.probe.admission_fails_closed.v1"
CARRIER = "probe-carrier-fixture.json"
OTHER = "probe-unrelated-fixture.json"
FIRST = "the_request_is_refused_before_any_write"
SECOND = "the_refusal_leaves_no_partial_state"
OWNER = "arkret-work/tasks/spec-open/probe-report.md"

RULE = "a case names the decision point it observes and carries a non-empty expected result"
RATCHET_RULE = "the list only shrinks; a row names a pair no case reaches yet"
CEILING_RULE = "the frozen set of pairs the ratchet was ever allowed to hold"


def vector_registry() -> dict:
    return {
        "version": "probe",
        "vectors": [
            {
                "vector_id": VECTOR,
                "status": "active",
                "domain": "probe",
                "applies_to_fixtures": [CARRIER],
                "description": "probe",
                "source_refs": [f"spec/v1/artifacts/fixtures/{CARRIER}"],
            }
        ],
    }


def contract() -> dict:
    return {
        "version": "probe",
        "sdk_conformance_contract": {
            "contract_version": "1",
            "decision_point_case_rule": RULE,
            "decision_point_case_ratchet_rule": RATCHET_RULE,
            "decision_point_case_ratchet": [],
            "decision_point_case_ratchet_ceiling_rule": CEILING_RULE,
            # Wide enough that the ratchet tests below exercise the rule each is
            # named for; the ceiling itself gets its own tests.
            "decision_point_case_ratchet_ceiling": [
                {"clause_id": CLAUSE, "decision_point_id": FIRST},
                {"clause_id": CLAUSE, "decision_point_id": SECOND},
                {"clause_id": CLAUSE, "decision_point_id": "a_point_that_was_renamed_away"},
            ],
            "clauses": [
                {
                    "clause_id": CLAUSE,
                    "required_evidence": ["vector_result"],
                    "vector_evidence": {
                        "vectors": [VECTOR],
                        "decision_points": [
                            {
                                "id": FIRST,
                                "requirement": "the request is refused before any write",
                                "vectors": [VECTOR],
                            },
                            {
                                "id": SECOND,
                                "requirement": "the refusal leaves no partial state",
                                "vectors": [VECTOR],
                            },
                        ],
                    },
                }
            ],
        },
    }


def carrier() -> dict:
    return {
        "suite": "probe",
        "runner": {"kind": "named_suite", "entrypoint": "ak.suite.probe.admission.v1"},
        "covers_vectors": [VECTOR],
        "cases": [
            {
                "name": "a_refused_request_never_reaches_the_writer",
                "covers_decision_points": [f"{CLAUSE}/{FIRST}"],
                "expected": {"outcome": "rejected", "writes": 0},
            },
            {
                "name": "a_refusal_leaves_the_prior_state_untouched",
                "covers_decision_points": [f"{CLAUSE}/{SECOND}"],
                "expected": {"state_after": "unchanged"},
            },
        ],
    }


def unrelated() -> dict:
    return {
        "suite": "probe_unrelated",
        "runner": {"kind": "inline_cases"},
        "cases": [{"name": "something_else", "expected": {"ok": True}}],
    }


def ratchet_row(point: str = FIRST) -> dict:
    return {"clause_id": CLAUSE, "decision_point_id": point, "owner_report": OWNER}


def contract_with_required_cases() -> dict:
    document = contract()
    point = document["sdk_conformance_contract"]["clauses"][0]["vector_evidence"][
        "decision_points"
    ][0]
    point["required_case_refs"] = [
        {"fixture_ref": f"fixtures/{CARRIER}", "case_id": "a_refused_request_never_reaches_the_writer"},
        {"fixture_ref": f"fixtures/{CARRIER}", "case_id": "the_same_refusal_is_visible_to_the_cache"},
    ]
    return document


def carrier_with_required_cases() -> dict:
    document = carrier()
    document["cases"].append(
        {
            "name": "the_same_refusal_is_visible_to_the_cache",
            "covers_decision_points": [f"{CLAUSE}/{FIRST}"],
            "expected": {"cache_writes": 0},
        }
    )
    return document


class DecisionPointCaseGateTest(unittest.TestCase):
    def run_gate(
        self,
        *,
        contract_document: dict | None = None,
        vectors: dict | None = None,
        fixtures: dict[str, dict] | None = None,
    ) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = root / "spec" / "v1" / "artifacts"
            for name in ("registry", "fixtures", "profiles"):
                (artifacts / name).mkdir(parents=True)

            def dump(path: Path, body: dict) -> None:
                path.write_text(
                    json.dumps(body, ensure_ascii=False), encoding="utf-8", newline="\n"
                )

            dump(
                artifacts / "profiles" / "conformance-profiles.json",
                contract() if contract_document is None else contract_document,
            )
            dump(
                artifacts / "registry" / "vector-registry.json",
                vector_registry() if vectors is None else vectors,
            )
            supplied = {CARRIER: carrier()} if fixtures is None else fixtures
            for name, body in supplied.items():
                dump(artifacts / "fixtures" / name, body)

            lint = Lint()
            with mock.patch.object(gate, "ARTIFACTS", artifacts):
                gate.check_sdk_decision_point_cases(lint)
            return lint.errors

    def assertRedWith(self, errors: list[str], needle: str) -> None:
        self.assertTrue(any(needle in error for error in errors), errors)

    # ---------------------------------------------------------------- baseline

    def test_the_probe_tree_passes(self) -> None:
        self.assertEqual(self.run_gate(), [])

    def test_the_committed_spec_passes(self) -> None:
        lint = Lint()
        gate.check_sdk_decision_point_cases(lint)
        self.assertEqual(lint.errors, [])

    # ------------------------------------------------------------- a case is missing

    def test_a_deleted_case_turns_the_gate_red(self) -> None:
        body = carrier()
        body["cases"] = [body["cases"][0]]
        errors = self.run_gate(fixtures={CARRIER: body})
        self.assertRedWith(errors, f"{CLAUSE}.{SECOND} is reached by no fixture case")

    def test_a_carrier_with_no_cases_at_all_turns_the_gate_red(self) -> None:
        body = carrier()
        body["cases"] = []
        errors = self.run_gate(fixtures={CARRIER: body})
        self.assertRedWith(errors, f"{CLAUSE}.{FIRST} is reached by no fixture case")
        self.assertRedWith(errors, f"{CLAUSE}.{SECOND} is reached by no fixture case")

    def test_a_clause_declaring_a_new_point_without_a_case_turns_the_gate_red(self) -> None:
        document = contract()
        points = document["sdk_conformance_contract"]["clauses"][0]["vector_evidence"][
            "decision_points"
        ]
        points.append(
            {"id": "a_third_thing", "requirement": "a third thing", "vectors": [VECTOR]}
        )
        errors = self.run_gate(contract_document=document)
        self.assertRedWith(errors, f"{CLAUSE}.a_third_thing is reached by no fixture case")

    # --------------------------------------------------------- the case is misfiled

    def test_a_case_in_a_fixture_that_carries_no_such_vector_turns_the_gate_red(self) -> None:
        stripped = carrier()
        moved = stripped["cases"].pop()
        other = unrelated()
        other["cases"].append(moved)
        errors = self.run_gate(fixtures={CARRIER: stripped, OTHER: other})
        self.assertRedWith(errors, "carries none")
        self.assertRedWith(errors, f"{CLAUSE}.{SECOND} is reached by no fixture case")

    def test_a_case_naming_an_undeclared_decision_point_turns_the_gate_red(self) -> None:
        body = carrier()
        body["cases"][1]["covers_decision_points"] = [f"{CLAUSE}/a_point_nobody_declares"]
        errors = self.run_gate(fixtures={CARRIER: body})
        self.assertRedWith(errors, "does not declare")

    def test_a_case_naming_an_unknown_clause_turns_the_gate_red(self) -> None:
        body = carrier()
        body["cases"][1]["covers_decision_points"] = [f"AK-SDK-999/{SECOND}"]
        errors = self.run_gate(fixtures={CARRIER: body})
        self.assertRedWith(errors, "does not declare")

    def test_a_malformed_reference_turns_the_gate_red(self) -> None:
        body = carrier()
        body["cases"][1]["covers_decision_points"] = [SECOND]
        errors = self.run_gate(fixtures={CARRIER: body})
        self.assertRedWith(errors, "malformed reference")

    def test_a_decision_point_whose_vector_is_inactive_turns_the_gate_red(self) -> None:
        registry = vector_registry()
        registry["vectors"][0]["status"] = "deprecated"
        errors = self.run_gate(vectors=registry)
        self.assertRedWith(errors, "carries none")

    # ----------------------------------------------------------- the case is empty

    def test_a_case_with_an_empty_expected_block_turns_the_gate_red(self) -> None:
        body = carrier()
        body["cases"][1]["expected"] = {}
        errors = self.run_gate(fixtures={CARRIER: body})
        self.assertRedWith(errors, "asserts nothing")

    def test_a_case_with_no_expected_block_turns_the_gate_red(self) -> None:
        body = carrier()
        del body["cases"][1]["expected"]
        errors = self.run_gate(fixtures={CARRIER: body})
        self.assertRedWith(errors, "asserts nothing")

    def test_an_unnamed_case_turns_the_gate_red(self) -> None:
        body = carrier()
        del body["cases"][1]["name"]
        errors = self.run_gate(fixtures={CARRIER: body})
        self.assertRedWith(errors, "must carry a name")

    def test_a_duplicate_case_name_turns_the_gate_red(self) -> None:
        body = carrier()
        body["cases"][1]["name"] = body["cases"][0]["name"]
        errors = self.run_gate(fixtures={CARRIER: body})
        self.assertRedWith(errors, "duplicates")

    def test_an_empty_covers_decision_points_list_turns_the_gate_red(self) -> None:
        body = carrier()
        body["cases"][1]["covers_decision_points"] = []
        errors = self.run_gate(fixtures={CARRIER: body})
        self.assertRedWith(errors, "must be a non-empty list")

    # ------------------------------------------------------- the suite is unrunnable

    def test_a_carrier_without_a_runner_turns_the_gate_red(self) -> None:
        body = carrier()
        del body["runner"]
        errors = self.run_gate(fixtures={CARRIER: body})
        self.assertRedWith(errors, "declares no runner")

    def test_a_named_suite_without_an_entrypoint_turns_the_gate_red(self) -> None:
        body = carrier()
        del body["runner"]["entrypoint"]
        errors = self.run_gate(fixtures={CARRIER: body})
        self.assertRedWith(errors, "ak.suite.*.v1 entrypoint")

    def test_a_named_suite_with_a_tool_specific_entrypoint_turns_the_gate_red(self) -> None:
        body = carrier()
        body["runner"]["entrypoint"] = "pytest::tests/test_admission.py::test_fails_closed"
        errors = self.run_gate(fixtures={CARRIER: body})
        self.assertRedWith(errors, "ak.suite.*.v1 entrypoint")

    # -------------------------------------------------------------- the ratchet

    def test_an_unreached_point_outside_the_ratchet_turns_the_gate_red(self) -> None:
        body = carrier()
        body["cases"] = [body["cases"][0]]
        errors = self.run_gate(fixtures={CARRIER: body})
        self.assertRedWith(errors, "decision_point_case_ratchet does not record it")

    def test_an_unreached_point_inside_the_ratchet_passes(self) -> None:
        body = carrier()
        body["cases"] = [body["cases"][0]]
        document = contract()
        document["sdk_conformance_contract"]["decision_point_case_ratchet"] = [
            ratchet_row(SECOND)
        ]
        self.assertEqual(
            self.run_gate(contract_document=document, fixtures={CARRIER: body}), []
        )

    def test_a_ratchet_row_for_a_point_that_now_has_a_case_turns_the_gate_red(self) -> None:
        document = contract()
        document["sdk_conformance_contract"]["decision_point_case_ratchet"] = [
            ratchet_row(SECOND)
        ]
        errors = self.run_gate(contract_document=document)
        self.assertRedWith(errors, "which now has a fixture case")

    def test_a_ratchet_row_the_contract_no_longer_declares_turns_the_gate_red(self) -> None:
        document = contract()
        document["sdk_conformance_contract"]["decision_point_case_ratchet"] = [
            ratchet_row("a_point_that_was_renamed_away")
        ]
        errors = self.run_gate(contract_document=document)
        self.assertRedWith(errors, "no longer declares")

    def test_a_ratchet_row_without_an_owner_report_turns_the_gate_red(self) -> None:
        body = carrier()
        body["cases"] = [body["cases"][0]]
        document = contract()
        row = ratchet_row(SECOND)
        del row["owner_report"]
        document["sdk_conformance_contract"]["decision_point_case_ratchet"] = [row]
        errors = self.run_gate(contract_document=document, fixtures={CARRIER: body})
        self.assertRedWith(errors, "must name the report that owns the gap")

    def test_a_duplicate_ratchet_row_turns_the_gate_red(self) -> None:
        body = carrier()
        body["cases"] = [body["cases"][0]]
        document = contract()
        document["sdk_conformance_contract"]["decision_point_case_ratchet"] = [
            ratchet_row(SECOND),
            ratchet_row(SECOND),
        ]
        errors = self.run_gate(contract_document=document, fixtures={CARRIER: body})
        self.assertRedWith(errors, "duplicates")

    # ------------------------------------------------------- the frozen ceiling

    def test_a_ratchet_row_outside_the_frozen_ceiling_turns_the_gate_red(self) -> None:
        # The prose says the list only shrinks; this is what makes that a check
        # rather than a promise. A decision point that newly loses its case
        # cannot be silenced by writing one more row, because the row is not in
        # the baseline.
        body = carrier()
        body["cases"] = [body["cases"][0]]
        document = contract()
        document["sdk_conformance_contract"]["decision_point_case_ratchet_ceiling"] = []
        document["sdk_conformance_contract"]["decision_point_case_ratchet"] = [
            ratchet_row(SECOND)
        ]
        errors = self.run_gate(contract_document=document, fixtures={CARRIER: body})
        self.assertRedWith(errors, "the frozen decision_point_case_ratchet_ceiling does not contain")

    def test_emptying_the_ratchet_below_the_ceiling_passes(self) -> None:
        # Shrinking is the whole point: a ceiling entry with no ratchet row is
        # a closed gap, not a violation.
        self.assertEqual(self.run_gate(), [])

    def test_dropping_the_ceiling_turns_the_gate_red(self) -> None:
        document = contract()
        del document["sdk_conformance_contract"]["decision_point_case_ratchet_ceiling"]
        errors = self.run_gate(contract_document=document)
        self.assertRedWith(errors, "decision_point_case_ratchet_ceiling must be a list")

    def test_dropping_the_ceiling_rule_turns_the_gate_red(self) -> None:
        document = contract()
        del document["sdk_conformance_contract"]["decision_point_case_ratchet_ceiling_rule"]
        errors = self.run_gate(contract_document=document)
        self.assertRedWith(errors, "decision_point_case_ratchet_ceiling_rule must state")

    def test_a_duplicate_ceiling_row_turns_the_gate_red(self) -> None:
        document = contract()
        ceiling = document["sdk_conformance_contract"]["decision_point_case_ratchet_ceiling"]
        ceiling.append(dict(ceiling[0]))
        errors = self.run_gate(contract_document=document)
        self.assertRedWith(errors, "duplicates")

    # ------------------------------------------------------------- the rule text

    def test_dropping_the_case_rule_turns_the_gate_red(self) -> None:
        document = contract()
        del document["sdk_conformance_contract"]["decision_point_case_rule"]
        errors = self.run_gate(contract_document=document)
        self.assertRedWith(errors, "decision_point_case_rule must state")

    def test_dropping_the_ratchet_rule_turns_the_gate_red(self) -> None:
        document = contract()
        del document["sdk_conformance_contract"]["decision_point_case_ratchet_rule"]
        errors = self.run_gate(contract_document=document)
        self.assertRedWith(errors, "decision_point_case_ratchet_rule must state")

    # ------------------------------------------ conjunctive required case refs

    def test_a_complete_required_case_set_passes(self) -> None:
        self.assertEqual(
            self.run_gate(
                contract_document=contract_with_required_cases(),
                fixtures={CARRIER: carrier_with_required_cases()},
            ),
            [],
        )

    def test_deleting_one_required_case_turns_the_gate_red(self) -> None:
        required_names = [
            ref["case_id"]
            for ref in contract_with_required_cases()["sdk_conformance_contract"]["clauses"][0][
                "vector_evidence"
            ]["decision_points"][0]["required_case_refs"]
        ]
        for deleted_name in required_names:
            with self.subTest(deleted_name=deleted_name):
                body = carrier_with_required_cases()
                body["cases"] = [case for case in body["cases"] if case["name"] != deleted_name]
                errors = self.run_gate(
                    contract_document=contract_with_required_cases(), fixtures={CARRIER: body}
                )
                self.assertRedWith(errors, "does not resolve to a covered fixture case")

    def test_removing_a_required_case_cover_label_turns_the_gate_red(self) -> None:
        required_names = [
            ref["case_id"]
            for ref in contract_with_required_cases()["sdk_conformance_contract"]["clauses"][0][
                "vector_evidence"
            ]["decision_points"][0]["required_case_refs"]
        ]
        for mutated_name in required_names:
            with self.subTest(mutated_name=mutated_name):
                body = carrier_with_required_cases()
                target = next(case for case in body["cases"] if case["name"] == mutated_name)
                del target["covers_decision_points"]
                errors = self.run_gate(
                    contract_document=contract_with_required_cases(), fixtures={CARRIER: body}
                )
                self.assertRedWith(errors, "does not resolve to a covered fixture case")

    def test_a_required_case_fixture_without_a_runner_turns_the_gate_red(self) -> None:
        body = carrier_with_required_cases()
        del body["runner"]
        errors = self.run_gate(
            contract_document=contract_with_required_cases(), fixtures={CARRIER: body}
        )
        self.assertRedWith(errors, "has no valid registered runner")

    def test_a_required_ref_with_an_extra_member_turns_the_gate_red(self) -> None:
        document = contract_with_required_cases()
        refs = document["sdk_conformance_contract"]["clauses"][0]["vector_evidence"][
            "decision_points"
        ][0]["required_case_refs"]
        refs[0]["note"] = "not part of the closed shape"
        errors = self.run_gate(
            contract_document=document, fixtures={CARRIER: carrier_with_required_cases()}
        )
        self.assertRedWith(errors, "exactly fixture_ref and case_id")

    def test_a_duplicate_required_ref_turns_the_gate_red(self) -> None:
        document = contract_with_required_cases()
        refs = document["sdk_conformance_contract"]["clauses"][0]["vector_evidence"][
            "decision_points"
        ][0]["required_case_refs"]
        refs.append(copy.deepcopy(refs[0]))
        errors = self.run_gate(
            contract_document=document, fixtures={CARRIER: carrier_with_required_cases()}
        )
        self.assertRedWith(errors, "duplicates an earlier required reference")

    def test_an_empty_required_case_set_turns_the_gate_red(self) -> None:
        document = contract_with_required_cases()
        document["sdk_conformance_contract"]["clauses"][0]["vector_evidence"][
            "decision_points"
        ][0]["required_case_refs"] = []
        errors = self.run_gate(
            contract_document=document, fixtures={CARRIER: carrier_with_required_cases()}
        )
        self.assertRedWith(errors, "must be a non-empty closed list")

    # ------------------------------------------------ the gate stays honest about itself

    def test_a_case_asserting_the_wrong_thing_still_passes(self) -> None:
        # Documented non-goal, not an oversight: the gate proves reachability,
        # never that the expected result matches the requirement sentence. If
        # this test ever starts failing, the contract rule text has to change
        # with it, because it currently tells readers exactly this.
        body = carrier()
        body["cases"][1]["expected"] = {"outcome": "accepted", "state_after": "rewritten"}
        self.assertEqual(self.run_gate(fixtures={CARRIER: body}), [])

    def test_one_case_may_cover_several_points(self) -> None:
        body = carrier()
        body["cases"] = [
            {
                "name": "a_single_transcript_observing_both",
                "covers_decision_points": [f"{CLAUSE}/{FIRST}", f"{CLAUSE}/{SECOND}"],
                "expected": {"outcome": "rejected", "state_after": "unchanged"},
            }
        ]
        self.assertEqual(self.run_gate(fixtures={CARRIER: body}), [])

    def test_a_source_ref_carrier_counts_like_applies_to_fixtures(self) -> None:
        registry = vector_registry()
        del registry["vectors"][0]["applies_to_fixtures"]
        registry["vectors"][0]["scope"] = "universal"
        self.assertEqual(self.run_gate(vectors=registry), [])

    def test_a_wildcard_family_expands_to_its_members(self) -> None:
        document = contract()
        document["sdk_conformance_contract"]["clauses"][0]["vector_evidence"]["vectors"] = [
            "ak.vector.probe.*"
        ]
        self.assertEqual(self.run_gate(contract_document=document), [])

    def test_the_probe_tree_is_not_accidentally_immune(self) -> None:
        # Guards the harness itself: if run_gate stopped reading the fixtures it
        # is handed, every red-path test above would pass for the wrong reason.
        self.assertNotEqual(self.run_gate(fixtures={}), [])


if __name__ == "__main__":
    unittest.main()
