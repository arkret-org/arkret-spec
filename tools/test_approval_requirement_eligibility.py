"""Mutation coverage for approval requirement eligibility and carrier closure."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import approval_eligibility as gate


class ApprovalRequirementEligibilityTest(unittest.TestCase):
    def _run(self, mutate=None) -> list[str]:
        original = gate.load_json
        originals = {
            gate.ACTION_REGISTRY.resolve(): copy.deepcopy(original(gate.Lint(), gate.ACTION_REGISTRY)),
            gate.OPERATION_REGISTRY.resolve(): copy.deepcopy(original(gate.Lint(), gate.OPERATION_REGISTRY)),
            gate.APPROVAL_SCHEMA.resolve(): copy.deepcopy(original(gate.Lint(), gate.APPROVAL_SCHEMA)),
        }
        if mutate is not None:
            mutate(originals)

        def load_json(lint, path):  # type: ignore[no-untyped-def]
            resolved = Path(path).resolve()
            if resolved in originals:
                return originals[resolved]
            return original(lint, path)

        gate.load_json = load_json
        try:
            lint = gate.Lint()
            gate.check_approval_requirement_eligibility(lint)
            return lint.errors
        finally:
            gate.load_json = original

    def _new_errors(self, mutate) -> list[str]:
        return sorted(set(self._run(mutate)) - set(self._run()))

    @staticmethod
    def _block(documents: dict[Path, dict]) -> dict:
        return documents[gate.ACTION_REGISTRY.resolve()]["approval_requirement_eligibility"]

    def test_live_registry_is_closed(self) -> None:
        self.assertEqual(self._run(), [])

    def test_every_action_resolves_and_non_event_requires_registered_override(self) -> None:
        registry = gate.load_json(gate.Lint(), gate.ACTION_REGISTRY)
        block = registry["approval_requirement_eligibility"]
        overrides = {row["action"] for row in block["action_overrides"]}
        non_event = [
            row for row in registry["actions"]
            if row["event_mapping_kind"] == "non_event_surface"
        ]
        self.assertGreater(len(non_event), 0)
        self.assertFalse(overrides.intersection(row["action"] for row in non_event))
        self.assertEqual(overrides, {"ak.applet.bot.provision", "ak.applet.ghost.provision"})
        carriers = {row["carrier_id"]: row for row in block["carriers"]}
        for row in block["action_overrides"]:
            self.assertEqual(carriers[row["carrier_id"]]["carrier_class"], "non_event_operation")
        self.assertEqual(
            block["event_mapping_defaults"]["non_event_surface"],
            "ineligible_no_registered_carrier",
        )

    def test_aggregate_override_requires_all_target_event_kinds(self) -> None:
        def mutate(documents: dict[Path, dict]) -> None:
            registry = documents[gate.OPERATION_REGISTRY.resolve()]
            operation = next(row for row in registry["operations"] if row["operation_id"] == "ak.self.applet.bot.command.provision.v1")
            operation["durable_effect"]["event_kinds"].remove("ak.applet.managed_actor.provision")
        errors = self._new_errors(mutate)
        self.assertTrue(any("covering every target Event kind" in error for error in errors), errors)

    def test_missing_mapping_default_breaks_full_universe_coverage(self) -> None:
        def mutate(documents: dict[Path, dict]) -> None:
            self._block(documents)["event_mapping_defaults"].pop("scope_suffix_variant")

        errors = self._new_errors(mutate)
        self.assertTrue(any("cover every event_mapping_kind exactly" in error for error in errors), errors)
        self.assertTrue(any("has no closed approval eligibility" in error for error in errors), errors)

    def test_non_event_default_cannot_be_made_event_eligible(self) -> None:
        def mutate(documents: dict[Path, dict]) -> None:
            self._block(documents)["event_mapping_defaults"]["non_event_surface"] = "event_submission_carrier"

        errors = self._new_errors(mutate)
        self.assertTrue(any("MUST default to ineligible" in error for error in errors), errors)
        self.assertTrue(any("eligible without an explicit carrier" in error for error in errors), errors)

    def test_non_event_override_cannot_borrow_event_submit_carrier(self) -> None:
        def mutate(documents: dict[Path, dict]) -> None:
            self._block(documents)["action_overrides"].append(
                {
                    "action": "ak.self.agent.command.renew_pairing.v1",
                    "eligibility_kind": "registered_operation_carrier",
                    "carrier_id": "event_admission_submission.approval_signatures",
                }
            )

        errors = self._new_errors(mutate)
        self.assertTrue(any("must name a non_event_operation carrier" in error for error in errors), errors)

    def test_carrier_must_be_reachable_from_canonical_request(self) -> None:
        def mutate(documents: dict[Path, dict]) -> None:
            self._block(documents)["carriers"][0]["carrier_schema_ref"] = (
                "schemas/unreachable-approval-carrier-probe.schema.json"
            )

        errors = self._new_errors(mutate)
        self.assertTrue(any("not reachable" in error for error in errors), errors)

    def test_operation_target_projection_cannot_admit_unregistered_carrier(self) -> None:
        def mutate(documents: dict[Path, dict]) -> None:
            schema = documents[gate.APPROVAL_SCHEMA.resolve()]
            schema["x-arkret-operation-target-carrier-operations"].append(
                "ak.self.agent.command.renew_pairing.v1"
            )

        errors = self._new_errors(mutate)
        self.assertTrue(any("projection does not equal" in error for error in errors), errors)

    def test_operation_target_schema_enum_cannot_drop_true_carrier(self) -> None:
        def mutate(documents: dict[Path, dict]) -> None:
            schema = documents[gate.APPROVAL_SCHEMA.resolve()]
            schema["$defs"]["approval_signature_input"]["allOf"][0]["then"]["properties"]["operation"]["enum"] = []

        errors = self._new_errors(mutate)
        self.assertTrue(any("must enumerate exactly" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
