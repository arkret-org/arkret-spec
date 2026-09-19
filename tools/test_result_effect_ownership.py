"""Mutation coverage for the closed persistent Event effect-owner classification."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import result_effect_ownership as gate


def event_row(document: dict, kind: str) -> dict:
    return next(
        row
        for row in document["event_kind_registry"]["event_kinds"]
        if row["event_kind"] == kind
    )


class ResultEffectOwnershipTest(unittest.TestCase):
    def _run(self, mutate=None) -> list[str]:
        original = gate.load_json
        document = copy.deepcopy(original(gate.Lint(), gate.CONTRACT_REGISTRY))
        if mutate is not None:
            mutate(document)

        def load_json(lint, path):  # type: ignore[no-untyped-def]
            if Path(path).resolve() == gate.CONTRACT_REGISTRY.resolve():
                return document
            return original(lint, path)

        gate.load_json = load_json
        try:
            lint = gate.Lint()
            gate.check_result_effect_ownership(lint)
            return lint.errors
        finally:
            gate.load_json = original

    def _new_errors(self, mutate) -> list[str]:
        return sorted(set(self._run(mutate)) - set(self._run()))

    def test_live_contract_is_closed(self) -> None:
        self.assertEqual(self._run(), [])

    def test_active_durable_kind_cannot_omit_ownership(self) -> None:
        errors = self._new_errors(
            lambda d: event_row(d, "ak.message.create").pop("result_effect_ownership")
        )
        self.assertTrue(any("must be a closed object" in error for error in errors), errors)

    def test_unknown_classification_is_reported(self) -> None:
        def mutate(document: dict) -> None:
            event_row(document, "ak.message.create")["result_effect_ownership"]["kind"] = "mystery"

        errors = self._new_errors(mutate)
        self.assertTrue(any("must be one of" in error for error in errors), errors)

    def test_typed_writer_cannot_name_a_second_owner(self) -> None:
        def mutate(document: dict) -> None:
            event_row(document, "ak.reaction.add")["result_effect_ownership"][
                "owner_report"
            ] = "arkret-work/tasks/spec-open/probe.md"

        errors = self._new_errors(mutate)
        self.assertTrue(any("must have exactly" in error for error in errors), errors)

    def test_typed_writer_requires_nonempty_result_writes(self) -> None:
        def mutate(document: dict) -> None:
            event_row(document, "ak.reaction.add").pop("result_writes")

        errors = self._new_errors(mutate)
        self.assertTrue(any("non-empty result_writes" in error for error in errors), errors)

    def test_private_effect_must_resolve_to_a_covering_service_branch(self) -> None:
        def mutate(document: dict) -> None:
            event_row(document, "ak.contact.accepted")["result_effect_ownership"][
                "service_contract_id"
            ] = "ak.push.bridge.v1"

        errors = self._new_errors(mutate)
        self.assertTrue(any("no branch" in error for error in errors), errors)

    def test_private_effect_branch_must_close_maintenance_and_rejection(self) -> None:
        def mutate(document: dict) -> None:
            service = next(
                row
                for row in document["service_contracts"]
                if row["contract_id"] == "ak.contact.admission.v1"
            )
            branch = next(row for row in service["branches"] if row["branch"] == "ak.contact.accepted")
            branch.pop("prior_state_cas")

        errors = self._new_errors(mutate)
        self.assertTrue(any("incomplete" in error and "prior_state_cas" in error for error in errors), errors)

    def test_service_branch_cannot_be_left_with_an_orphan_owner(self) -> None:
        def mutate(document: dict) -> None:
            event_row(document, "ak.contact.accepted")["result_effect_ownership"] = {
                "kind": "owned_gap",
                "owner_report": "arkret-work/tasks/spec-open/2026-09-19-0650-reducer-input-true-without-a-registered-result-family.md",
                "closure_condition": (
                    "Register the complete result_writes[] contract for ak.contact.accepted, including every written family, exact selector, projection, value schema, guard and field source."
                ),
            }

        errors = self._new_errors(mutate)
        self.assertTrue(any("orphan private effect owner" in error for error in errors), errors)

    def test_audit_fact_must_resolve_its_normative_definition(self) -> None:
        def mutate(document: dict) -> None:
            event_row(document, "ak.audit.erasure_receipt")["result_effect_ownership"][
                "defined_in"
            ] = "zh/identity/missing.md"

        errors = self._new_errors(mutate)
        self.assertTrue(any("defined_in" in error for error in errors), errors)

    def test_owned_gap_requires_a_live_owner_report(self) -> None:
        def mutate(document: dict) -> None:
            event_row(document, "ak.schema.define")["result_effect_ownership"][
                "owner_report"
            ] = "arkret-work/tasks/spec-open/no-such-report.md"

        errors = self._new_errors(mutate)
        self.assertTrue(any("orphaned" in error for error in errors), errors)

    def test_owned_gap_requires_a_precise_closure_condition(self) -> None:
        def mutate(document: dict) -> None:
            event_row(document, "ak.schema.define")["result_effect_ownership"][
                "closure_condition"
            ] = "later"

        errors = self._new_errors(mutate)
        self.assertTrue(any("closure_condition" in error for error in errors), errors)

    def test_owned_gap_cannot_hide_a_registered_writer(self) -> None:
        def mutate(document: dict) -> None:
            row = event_row(document, "ak.schema.define")
            row["result_writes"] = copy.deepcopy(
                event_row(document, "ak.reaction.add")["result_writes"]
            )

        errors = self._new_errors(mutate)
        self.assertTrue(any("already writes typed results" in error for error in errors), errors)

    def test_actor_private_kind_cannot_omit_ownership(self) -> None:
        def mutate(document: dict) -> None:
            event_row(document, "ak.account.blocklist").pop("result_effect_ownership")

        errors = self._new_errors(mutate)
        self.assertTrue(any("must be a closed object" in error for error in errors), errors)

    def test_actor_private_gap_requires_its_live_owner(self) -> None:
        def mutate(document: dict) -> None:
            event_row(document, "ak.account.blocklist")["result_effect_ownership"][
                "owner_report"
            ] = "arkret-work/tasks/spec-open/no-actor-private-owner.md"

        errors = self._new_errors(mutate)
        self.assertTrue(any("orphaned" in error for error in errors), errors)

    def test_actor_private_gap_cannot_drop_maintenance_sources_from_closure(self) -> None:
        def mutate(document: dict) -> None:
            ownership = event_row(document, "ak.account.blocklist")["result_effect_ownership"]
            ownership["closure_condition"] = ownership["closure_condition"].replace(
                "maintenance sources", "remaining details"
            )

        errors = self._new_errors(mutate)
        self.assertTrue(any("maintenance sources" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
