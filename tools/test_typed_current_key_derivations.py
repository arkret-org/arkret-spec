"""Mutation tests for decision 0079 family-specific current-row keys."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import typed_current_key_derivations as gate

REGISTRY = ROOT / "spec/v1/artifacts/registry/contract-registry.json"


def registry() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))["event_kind_registry"]


def errors_for(mutate) -> list[str]:
    document = copy.deepcopy(registry())
    mutate(document)
    lint = gate.Lint()
    gate._check_typed_current_key_derivations(lint, document)
    return lint.errors


class TypedCurrentKeyDerivationsTest(unittest.TestCase):
    def test_live_registry_is_closed_and_recomputable(self) -> None:
        lint = gate.Lint()
        gate._check_typed_current_key_derivations(lint, registry())
        self.assertEqual(lint.errors, [])

    def test_a_family_row_cannot_be_removed(self) -> None:
        reported = errors_for(
            lambda doc: doc["typed_current_key_derivations"]["families"].pop()
        )
        self.assertTrue(any("families must be exactly" in error for error in reported), reported)

    def test_a_generic_api_name_is_rejected(self) -> None:
        def mutate(doc: dict) -> None:
            doc["typed_current_key_derivations"]["families"][0]["api_name"] = (
                "composite_subject"
            )

        reported = errors_for(mutate)
        self.assertTrue(any("family-specific typed API" in error for error in reported), reported)

    def test_parameter_order_and_arity_are_closed(self) -> None:
        def mutate(doc: dict) -> None:
            row = next(
                row
                for row in doc["typed_current_key_derivations"]["families"]
                if row["result_family"] == "agent_key"
            )
            row["parameters"].reverse()

        reported = errors_for(mutate)
        self.assertTrue(any("closed typed signature" in error for error in reported), reported)

    def test_kat_output_and_domain_are_recomputed(self) -> None:
        def mutate(doc: dict) -> None:
            row = next(
                row
                for row in doc["typed_current_key_derivations"]["families"]
                if row["result_family"] == "agent_key"
            )
            row["kat"]["expected_output"] = "A" * 43

        reported = errors_for(mutate)
        self.assertTrue(any("expected_output does not recompute" in error for error in reported), reported)

    def test_reorder_negative_kat_must_diverge(self) -> None:
        def mutate(doc: dict) -> None:
            row = next(
                row
                for row in doc["typed_current_key_derivations"]["families"]
                if row["result_family"] == "key_backup_active_series"
            )
            row["kat"]["negative_cases"]["reordered_components"]["expected_output"] = (
                row["kat"]["expected_output"]
            )

        reported = errors_for(mutate)
        self.assertTrue(any("reordered-component KAT" in error for error in reported), reported)

    def test_extra_component_and_type_mismatch_must_reject_before_hash(self) -> None:
        def mutate(doc: dict) -> None:
            row = doc["typed_current_key_derivations"]["families"][0]
            row["kat"]["negative_cases"]["extra_component"] = {
                "disposition": "hash_anyway"
            }
            row["kat"]["negative_cases"]["type_mismatch"] = {
                "disposition": "coerce_to_string"
            }

        reported = errors_for(mutate)
        self.assertTrue(any("reject an extra component" in error for error in reported), reported)
        self.assertTrue(any("typed-parameter mismatch" in error for error in reported), reported)

    def test_live_selector_source_must_match_the_family_descriptor(self) -> None:
        def mutate(doc: dict) -> None:
            event = next(row for row in doc["event_kinds"] if row["event_kind"] == "ak.member.state")
            write = next(
                row for row in event["result_writes"] if row["result_family"] == "member_state"
            )
            write["result_selector"]["components"][0]["field"] = "payload.actor_id"

        reported = errors_for(mutate)
        self.assertTrue(any("component 0 is not registered" in error for error in reported), reported)

    def test_legacy_per_leg_mute_cannot_gain_a_compatibility_api(self) -> None:
        def mutate(doc: dict) -> None:
            template = copy.deepcopy(doc["typed_current_key_derivations"]["families"][2])
            template["result_family"] = "call_mute_override"
            doc["typed_current_key_derivations"]["families"].append(template)

        reported = errors_for(mutate)
        self.assertTrue(any("legacy per-leg mute caller" in error for error in reported), reported)


if __name__ == "__main__":
    unittest.main()
