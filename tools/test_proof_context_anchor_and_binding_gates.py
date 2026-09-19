"""Tests for the two gates added when `ak.events.checkpoint.*` was withdrawn.

Three registered Merkle domain separations survived every existing gate for one
reason each. `check_proof_context_object_family_schemas` exempts `merkle_*` by
construction, so nothing required the families to be reachable; and the registry
lint validates `binding_fields` only as a non-empty string array, so nothing
noticed that the leaf hashed `producer_revision`, a member of the closed
forbidden set for `producer_event_envelope_root`.

These tests pin both replacements, plus the ratchet behaviour of the exemption
ledger and the fact that the runner actually calls them. The last one matters:
a gate that is imported and never called is indistinguishable from no gate.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import proof_context_schemas as gate
from tools.artifact_lint.core import Lint


def carrier_row(**overrides) -> dict:
    row = {
        "domain": "ak.probe.carrier_digest.v1",
        "object_family": "probe_carrier_digest",
        "primitive": "canonical_json_sha256",
        "binding_fields": ["realm_id"],
    }
    row.update(overrides)
    return row


class AnchorGateTest(unittest.TestCase):
    """A carrier-bound family that nothing defines is a promise nobody can keep."""

    def run_gate(
        self,
        rows: list[dict],
        *,
        prose: str | None = None,
        schema: dict | None = None,
        vectors: dict | None = None,
        exemptions: dict | None = None,
    ) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec_root = root / "spec"
            artifacts = spec_root / "artifacts"
            (spec_root / "zh" / "sync").mkdir(parents=True)
            (artifacts / "registry").mkdir(parents=True)
            (artifacts / "schemas").mkdir(parents=True)
            (artifacts / "fixtures").mkdir(parents=True)
            (spec_root / "zh" / "sync" / "probe.md").write_text(
                prose if prose is not None else "no anchor here", encoding="utf-8"
            )
            (artifacts / "schemas" / "probe.schema.json").write_text(
                json.dumps(schema if schema is not None else {"$defs": {}}), encoding="utf-8"
            )
            (artifacts / "registry" / "vector-registry.json").write_text(
                json.dumps(vectors if vectors is not None else {"vectors": []}), encoding="utf-8"
            )
            registry_path = artifacts / "registry" / "proof-context-registry.json"
            registry_path.write_text(
                json.dumps({"contexts": [], "domain_separations": rows}), encoding="utf-8"
            )
            exemption_path = root / "proof-context-anchor-exemptions.json"
            if exemptions is not None:
                exemption_path.write_text(json.dumps(exemptions), encoding="utf-8")
            lint = Lint()
            with (
                mock.patch.object(gate, "SPEC_ROOT", spec_root),
                mock.patch.object(gate, "ARTIFACTS", artifacts),
                mock.patch.object(gate, "PROOF_CONTEXT_REGISTRY", registry_path),
                mock.patch.object(gate, "ANCHOR_EXEMPTIONS", exemption_path),
            ):
                gate.check_proof_context_carrier_family_anchors(lint)
            return lint.errors

    def test_family_defined_nowhere_fails(self) -> None:
        errors = self.run_gate([carrier_row()])
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("is defined nowhere", errors[0])

    def test_merkle_family_with_no_definition_fails(self) -> None:
        """The exact shape that was withdrawn: a Merkle separator with no prose."""
        errors = self.run_gate(
            [
                carrier_row(
                    domain="ak.events.checkpoint.leaf.v1",
                    object_family="events_checkpoint_leaf",
                    primitive="merkle_leaf_sha256",
                    binding_fields=["kind", "event_id"],
                )
            ]
        )
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("events_checkpoint_leaf", errors[0])

    def test_prose_mention_anchors_the_family(self) -> None:
        self.assertEqual(self.run_gate([carrier_row()], prose="probe_carrier_digest is …"), [])

    def test_domain_literal_anchors_the_family(self) -> None:
        self.assertEqual(
            self.run_gate([carrier_row()], prose="see ak.probe.carrier_digest.v1"), []
        )

    def test_schema_mention_anchors_the_family(self) -> None:
        self.assertEqual(
            self.run_gate([carrier_row()], schema={"$defs": {"probe_carrier_digest": {}}}), []
        )

    def test_vector_registry_mention_anchors_the_family(self) -> None:
        self.assertEqual(
            self.run_gate([carrier_row()], vectors={"vectors": ["probe_carrier_digest"]}), []
        )

    def test_declared_reference_anchors_the_family(self) -> None:
        for field, value in (
            ("schema_ref", "schemas/probe.schema.json"),
            ("transcript_schema_refs", ["schemas/probe.schema.json"]),
            ("defined_in", "zh/sync/probe.md"),
        ):
            with self.subTest(field=field):
                self.assertEqual(self.run_gate([carrier_row(**{field: value})]), [])

    def test_object_bearing_primitive_is_left_to_the_schema_gate(self) -> None:
        self.assertEqual(self.run_gate([carrier_row(primitive="detached_signature")]), [])

    def test_listed_exemption_suppresses_the_failure(self) -> None:
        errors = self.run_gate(
            [carrier_row()],
            exemptions={
                "unanchored_families": [
                    {"object_family": "probe_carrier_digest", "reason": "predates the gate"}
                ]
            },
        )
        self.assertEqual(errors, [])

    def test_exemption_without_a_reason_fails(self) -> None:
        errors = self.run_gate(
            [carrier_row()],
            exemptions={"unanchored_families": [{"object_family": "probe_carrier_digest"}]},
        )
        self.assertTrue(any("must state a reason" in message for message in errors), errors)

    def test_exemption_for_an_anchored_family_fails(self) -> None:
        """The ledger is a ratchet: cover that is no longer needed must be removed."""
        errors = self.run_gate(
            [carrier_row()],
            prose="probe_carrier_digest is …",
            exemptions={
                "unanchored_families": [
                    {"object_family": "probe_carrier_digest", "reason": "predates the gate"}
                ]
            },
        )
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("now has an anchor", errors[0])

    def test_exemption_for_a_withdrawn_family_fails(self) -> None:
        errors = self.run_gate(
            [],
            exemptions={
                "unanchored_families": [{"object_family": "gone_family", "reason": "stale"}]
            },
        )
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("no longer a carrier-bound domain separation", errors[0])

    def test_shipped_registry_and_ledger_agree(self) -> None:
        lint = Lint()
        gate.check_proof_context_carrier_family_anchors(lint)
        self.assertEqual(lint.errors, [])


class ForbiddenBindingFieldGateTest(unittest.TestCase):
    """Binding a field the Event wire forbids makes the separation unimplementable."""

    FORBIDDEN = {
        "entries": [
            {
                "id": "producer_revision",
                "context": "producer_event_envelope_root",
                "match": {"kind": "field", "values": ["producer_revision"]},
            }
        ]
    }

    def run_gate(self, registry: dict, forbidden: dict | None = None) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry_path = root / "proof-context-registry.json"
            forbidden_path = root / "forbidden-wire-fields.json"
            registry_path.write_text(json.dumps(registry), encoding="utf-8")
            forbidden_path.write_text(
                json.dumps(self.FORBIDDEN if forbidden is None else forbidden), encoding="utf-8"
            )
            lint = Lint()
            with (
                mock.patch.object(gate, "PROOF_CONTEXT_REGISTRY", registry_path),
                mock.patch.object(gate, "FORBIDDEN_WIRE_FIELDS", forbidden_path),
            ):
                gate.check_domain_separation_binding_fields_are_carriable(lint)
            return lint.errors

    def test_forbidden_binding_field_fails(self) -> None:
        errors = self.run_gate(
            {
                "contexts": [],
                "domain_separations": [
                    carrier_row(binding_fields=["kind", "event_id", "producer_revision"])
                ],
            }
        )
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("producer_revision", errors[0])

    def test_optional_marker_does_not_launder_the_field(self) -> None:
        errors = self.run_gate(
            {
                "contexts": [],
                "domain_separations": [carrier_row(binding_fields=["producer_revision?"])],
            }
        )
        self.assertEqual(len(errors), 1, errors)

    def test_contexts_rows_are_checked_too(self) -> None:
        errors = self.run_gate(
            {
                "contexts": [
                    {
                        "context": "ak.probe_proof.v1",
                        "object_family": "probe",
                        "binding_fields": ["hlc"],
                    }
                ],
                "domain_separations": [],
            },
            forbidden={
                "entries": [
                    {
                        "id": "hlc",
                        "context": "producer_event_envelope_root",
                        "match": {"kind": "field", "values": ["hlc"]},
                    }
                ]
            },
        )
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("hlc", errors[0])

    def test_field_forbidden_only_in_another_context_is_allowed(self) -> None:
        errors = self.run_gate(
            {
                "contexts": [],
                "domain_separations": [carrier_row(binding_fields=["producer_revision"])],
            },
            forbidden={
                "entries": [
                    {
                        "id": "producer_revision",
                        "context": "some_other_context",
                        "match": {"kind": "field", "values": ["producer_revision"]},
                    }
                ]
            },
        )
        self.assertTrue(any("no field entries registered" in message for message in errors), errors)

    def test_clean_registry_passes(self) -> None:
        self.assertEqual(
            self.run_gate({"contexts": [], "domain_separations": [carrier_row()]}), []
        )

    def test_shipped_registry_binds_no_forbidden_field(self) -> None:
        lint = Lint()
        gate.check_domain_separation_binding_fields_are_carriable(lint)
        self.assertEqual(lint.errors, [])


class RunnerWiringTest(unittest.TestCase):
    def test_runner_calls_both_new_gates(self) -> None:
        source = (ROOT / "tools" / "artifact_lint" / "runner.py").read_text(encoding="utf-8")
        for name in (
            "check_digest_construction_registration",
            "check_proof_context_carrier_family_anchors",
            "check_domain_separation_binding_fields_are_carriable",
        ):
            self.assertIn(f"{name}(lint)", source, f"{name} is imported but never invoked")


if __name__ == "__main__":
    unittest.main()
