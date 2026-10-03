"""Single-point mutation tests for the MLS governance-binding closure gate."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import fixtures as gate


FIXTURE = (gate.ARTIFACTS / "fixtures/mls-governance-binding-closure-fixture.json").resolve()
FINAL = (gate.ARTIFACTS / "fixtures/final-conformance-closure-fixture.json").resolve()
SCHEMA = (gate.ARTIFACTS / "schemas/event-payload.schema.json").resolve()
EXTENSIONS = (gate.ARTIFACTS / "registry/mls-extension-registry.json").resolve()
BOOTSTRAP = (gate.ARTIFACTS / "registry/mls-creator-bootstrap-transaction-registry.json").resolve()


class MlsGovernanceBindingClosureTest(unittest.TestCase):
    def _run(self, path: Path | None = None, mutate=None) -> list[str]:
        original = gate.load_json
        overrides: dict[Path, object] = {}
        if path is not None and mutate is not None:
            value = copy.deepcopy(original(gate.Lint(), path))
            mutate(value)
            overrides[path] = value

        def load_json_with_override(lint, candidate):
            return overrides.get(candidate.resolve(), original(lint, candidate))

        gate.load_json = load_json_with_override
        try:
            lint = gate.Lint()
            gate.check_mls_governance_binding_closure_vector(lint)
            return lint.errors
        finally:
            gate.load_json = original

    def test_committed_closure_passes(self) -> None:
        self.assertEqual(self._run(), [])

    def test_sidecar_private_handshake_is_not_a_station_verifiable_transition(self) -> None:
        def mutate(value):
            value["x-arkret-sidecar-handshake-contract"]["commit_wire_format"] = "mls_private_message"

        self.assertTrue(any("Sidecar handshake" in error for error in self._run(SCHEMA, mutate)))

    def test_sidecar_handshake_cannot_disclose_to_realm_members_or_give_station_mac_secrets(self) -> None:
        for field, replacement in (
            ("handshake_disclosure", "realm_members"),
            ("secret_mac_verification_role", "station"),
            ("participant_authority_binding", "desired_roster_only"),
        ):
            with self.subTest(field=field):
                def mutate(value, field=field, replacement=replacement):
                    value["x-arkret-sidecar-handshake-contract"][field] = replacement

                self.assertTrue(any("Sidecar handshake" in error for error in self._run(SCHEMA, mutate)))

    def test_sidecar_handshake_cannot_default_to_the_realm_circle_contract(self) -> None:
        def mutate(value):
            value["x-arkret-public-handshake-contract"]["effective_scope_kinds"].append("sidecar")

        self.assertTrue(any("remain separate" in error for error in self._run(SCHEMA, mutate)))

    def test_circle_acceptance_kat_is_required(self) -> None:
        def mutate(value):
            value["cases"][0]["accepted"] = [
                sample for sample in value["cases"][0]["accepted"]
                if sample["name"] != "circle_scope_commit"
            ]

        self.assertTrue(any("circle_scope_commit" in error for error in self._run(FIXTURE, mutate)))

    def test_accepted_bytes_are_actually_decoded(self) -> None:
        def mutate(value):
            value["cases"][0]["accepted"][0]["encoded_map_hex"] += "00"

        self.assertTrue(any("trailing_bytes" in error for error in self._run(FIXTURE, mutate)))

    def test_each_boundary_rejection_class_is_required(self) -> None:
        def mutate(value):
            value["cases"][0]["rejection_samples"] = [
                sample for sample in value["cases"][0]["rejection_samples"]
                if sample["name"] != "resource_limit_exceeded"
            ]

        self.assertTrue(any("resource_limit_exceeded" in error for error in self._run(FIXTURE, mutate)))

    def test_sidecar_acceptance_kat_must_carry_both_sidecar_members(self) -> None:
        def mutate(value):
            sample = next(
                item for item in value["cases"][0]["accepted"]
                if item["name"] == "sidecar_scope_commit"
            )
            del sample["binding"]["authority_stream_head"]

        self.assertTrue(any("sidecar_member_missing" in error for error in self._run(FIXTURE, mutate)))

    def test_each_scope_member_rejection_class_is_required(self) -> None:
        for name in (
            "sidecar_member_missing",
            "non_sidecar_carries_sidecar_member",
            "authority_stream_head_unsorted",
            "authority_stream_head_duplicate",
        ):
            with self.subTest(name=name):
                def mutate(value, name=name):
                    value["cases"][0]["rejection_samples"] = [
                        sample for sample in value["cases"][0]["rejection_samples"]
                        if sample["name"] != name
                    ]

                self.assertTrue(any(name in error for error in self._run(FIXTURE, mutate)))

    def test_scope_member_rejection_bytes_must_break_the_named_rule(self) -> None:
        def mutate(value):
            samples = value["cases"][0]["rejection_samples"]
            accepted = next(
                item for item in value["cases"][0]["accepted"]
                if item["name"] == "sidecar_scope_commit"
            )
            unsorted = next(item for item in samples if item["name"] == "authority_stream_head_unsorted")
            unsorted["encoded_map_hex"] = accepted["encoded_map_hex"]

        self.assertTrue(any("authority_stream_head_unsorted" in error for error in self._run(FIXTURE, mutate)))

    def test_schema_must_bound_authority_stream_head(self) -> None:
        def mutate(value):
            del value["$defs"]["mls_governance_binding"]["properties"]["authority_stream_head"]["maxItems"]

        self.assertTrue(any("maxItems" in error for error in self._run(SCHEMA, mutate)))

    def test_schema_must_forbid_sidecar_members_outside_sidecar(self) -> None:
        def mutate(value):
            del value["$defs"]["mls_governance_binding"]["allOf"][0]["else"]

        self.assertTrue(any("forbid them" in error for error in self._run(SCHEMA, mutate)))

    def test_decoder_limits_must_match_the_gate(self) -> None:
        def mutate(value):
            value["cases"][0]["resource_limits"]["maximum_collection_items"] = 65

        self.assertTrue(any("resource_limits" in error for error in self._run(FIXTURE, mutate)))

    def test_revision_must_be_an_unsigned_integer(self) -> None:
        def mutate(value):
            value["cases"][0]["accepted"][0]["binding"]["key_access_revision"] = (
                "sha256:" + "dd" * 32
            )

        self.assertTrue(any("key_access_revision" in error for error in self._run(FIXTURE, mutate)))

    def test_schema_must_publish_uint64_maximum(self) -> None:
        def mutate(value):
            del value["$defs"]["mls_governance_binding"]["properties"]["key_access_revision"]["maximum"]

        self.assertTrue(any("key_access_revision must be uint64" in error for error in self._run(SCHEMA, mutate)))

    def test_proposal_carrier_must_reuse_the_binding_ref(self) -> None:
        def mutate(value):
            prop = value["$defs"]["mls_genesis_binding_proposal_carrier"]["properties"]
            prop["proposed_group_genesis_binding"] = copy.deepcopy(value["$defs"]["mls_governance_binding"])

        self.assertTrue(any("direct $ref" in error for error in self._run(SCHEMA, mutate)))

    def test_proposal_carrier_route_kind_is_structural(self) -> None:
        def mutate(value):
            value["$defs"]["mls_genesis_binding_proposal_carrier"]["properties"]["event_kind"]["const"] = "ak.mls.commit"

        self.assertTrue(any("ak.mls.genesis" in error for error in self._run(SCHEMA, mutate)))

    def test_proposal_target_scope_must_equal_the_binding_scope(self) -> None:
        def mutate(value):
            value["cases"][4]["accepted_carrier"]["target_scope"]["realm_id"] = (
                "ak:realm:ATh7OWLLpUdTVYsKdp6rkClScUpjYJlF1Y3byjeyHS8J"
            )

        self.assertTrue(any("target_scope" in error for error in self._run(FIXTURE, mutate)))

    def test_missing_proposal_member_fails_at_closed_schema(self) -> None:
        def mutate(value):
            sample = next(
                item for item in value["cases"][4]["rejection_samples"]
                if item["name"] == "proposal_binding_member_missing"
            )
            sample["expected"]["reason"] = "mls_genesis_binding_proposal_required"

        self.assertTrue(any("schema_violation" in error for error in self._run(FIXTURE, mutate)))

    def test_missing_proposal_sender_fails_at_closed_schema(self) -> None:
        def mutate(value):
            sample = next(
                item for item in value["cases"][4]["rejection_samples"]
                if item["name"] == "proposal_sender_missing"
            )
            sample["expected"]["reason"] = "mls_genesis_binding_proposal_mismatch"

        self.assertTrue(any("schema_violation" in error for error in self._run(FIXTURE, mutate)))

    def test_extension_registry_must_point_at_the_carrier(self) -> None:
        def mutate(value):
            value["extensions"][1]["proposal_carrier_schema_ref"] = (
                "schemas/event-payload.schema.json#/$defs/mls_governance_binding"
            )

        self.assertTrue(any("formal proposal carrier" in error for error in self._run(EXTENSIONS, mutate)))

    def test_creator_bootstrap_registry_must_bind_the_formal_carrier(self) -> None:
        def mutate(value):
            value["proposal_carrier_contract"]["wire_exposure"] = "http"

        self.assertTrue(any("wire endpoint" in error for error in self._run(BOOTSTRAP, mutate)))

    def test_digest_shaped_revision_cannot_return_to_final_fixture(self) -> None:
        def mutate(value):
            value["cases"].append({
                "vector_id": "ak.vector.mls.governance_epoch_binding.v1",
                "commit": {"governance_binding": {"key_access_revision": "sha256:" + "dd" * 32}},
                "expected": {"reason": "governance_binding_mismatch"},
            })

        self.assertTrue(any("digest-shaped" in error for error in self._run(FINAL, mutate)))

    def test_epoch_payload_mismatch_uses_governance_binding_mismatch(self) -> None:
        def mutate(value):
            sample = next(
                item for item in value["cases"][1]["samples"]
                if item.get("name") == "commit_skips_an_epoch_reject"
            )
            sample["expected"]["reason"] = "epoch_update_required"

        self.assertTrue(any("governance_binding_mismatch" in error for error in self._run(FIXTURE, mutate)))

    def test_standalone_vector_must_not_be_duplicated_in_final_fixture(self) -> None:
        def mutate(value):
            value["covers_vectors"].append("ak.vector.mls.governance_binding_closure.v1")

        self.assertTrue(any("standalone" in error for error in self._run(FINAL, mutate)))


if __name__ == "__main__":
    unittest.main()
