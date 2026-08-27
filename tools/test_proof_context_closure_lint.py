"""Mutation tests for the shared detached-proof context closure gate.

Every case below is a state the artifacts were actually in, or could reach without
any other gate noticing: a shared proof leaf spliced into a new object family with
no registered context, a registry row pointing at a whole file instead of the inner
family it claims, a schema annotation drifting away from the registry, a second
consumer quietly borrowing the first consumer's transcript context, a DTO container
packing dozens of request/outcome families behind one proof node, or a replay-cache
namespace living only in prose. The gate is worth nothing unless it fails on each of
them, and unless the artifact-lint main entrypoint actually runs it.
"""

from __future__ import annotations

import copy
import inspect
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import foundation, runner
from tools.artifact_lint.core import Lint

ARTIFACTS = ROOT / "spec" / "v1" / "artifacts"
REGISTRY = ARTIFACTS / "registry" / "proof-context-registry.json"
SCHEMAS = ARTIFACTS / "schemas"
FIXTURES = ARTIFACTS / "fixtures"
WEBSOCKET_FIXTURE = FIXTURES / "websocket-binding-fixture.json"

DIRECTORY_PROOF_FAMILIES = (
    "directory_resolve_target_request_body",
    "directory_resolve_organization_request_body",
    "directory_resolve_handle_request_body",
    "directory_resolve_agent_selector_request_body",
    "directory_list_handles_for_subject_request_body",
)


class ProofContextClosureLintTest(unittest.TestCase):
    def _run_with_mutations(self, mutations: dict[Path, object]) -> list[str]:
        """Run the gate with selected artifacts replaced by mutated copies."""
        original_load_json = foundation.load_json
        targets: dict[Path, object] = {}
        for path, mutate in mutations.items():
            document = copy.deepcopy(original_load_json(Lint(), path))
            mutate(document)
            targets[path.resolve()] = document

        def load_json_with_mutation(lint, path):
            resolved = path.resolve()
            if resolved in targets:
                return targets[resolved]
            return original_load_json(lint, path)

        foundation.load_json = load_json_with_mutation
        try:
            lint = Lint()
            foundation.check_proof_context_registry(lint)
            return lint.errors
        finally:
            foundation.load_json = original_load_json

    @staticmethod
    def _row(document, context: str) -> dict:
        for row in document["contexts"]:
            if row.get("context") == context:
                return row
        raise AssertionError(f"missing registry row {context}")

    @staticmethod
    def _drop_row(document, context: str) -> None:
        document["contexts"] = [
            row for row in document["contexts"] if row.get("context") != context
        ]

    def assertAnyContains(self, errors: list[str], needle: str) -> None:
        self.assertTrue(
            any(needle in error for error in errors),
            f"no error contained {needle!r}; got {errors}",
        )

    def test_baseline_is_clean(self) -> None:
        lint = Lint()
        foundation.check_proof_context_registry(lint)
        self.assertEqual(lint.errors, [])

    def test_unregistered_use_point_family_fails(self) -> None:
        """The MIMI provider directory state: a whole object family with no row."""
        errors = self._run_with_mutations(
            {
                REGISTRY: lambda doc: self._drop_row(doc, "ak.mimi_provider_directory_proof.v1"),
                SCHEMAS
                / "mimi-interop.schema.json": lambda doc: doc["$defs"]["provider_directory"].pop(
                    "x-arkret-proof-context"
                ),
            }
        )
        self.assertAnyContains(
            errors,
            "shared detached-proof use point has no registered context: "
            "schemas/mimi-interop.schema.json#/$defs/provider_directory/properties/proof",
        )

    def test_unregistered_shared_leaf_family_fails(self) -> None:
        """The high-risk key-backup state: three branch use points, zero rows."""
        errors = self._run_with_mutations(
            {
                REGISTRY: lambda doc: self._drop_row(doc, "ak.key_backup_delete_proof.v1"),
                SCHEMAS
                / "high-risk-authority-proof.schema.json": lambda doc: doc.pop(
                    "x-arkret-proof-contexts"
                ),
            }
        )
        for branch in (
            "principal_signing_proof",
            "device_quorum_signature",
            "trusted_recovery_service_proof",
        ):
            self.assertAnyContains(
                errors,
                "shared detached-proof use point has no registered context: "
                f"schemas/high-risk-authority-proof.schema.json#/$defs/{branch}/properties/proof",
            )

    def test_over_broad_file_level_schema_ref_fails(self) -> None:
        """A row claiming an inner family while pointing at the whole file."""

        def widen(document) -> None:
            self._row(document, "ak.account_handoff_authentication_proof.v1")[
                "schema_ref"
            ] = "schemas/account-operations.schema.json"

        errors = self._run_with_mutations({REGISTRY: widen})
        self.assertAnyContains(errors, "tighten schema_ref to the object family it describes")

    def test_unresolvable_fragment_fails(self) -> None:
        """A fragment that names no node used to pass: only the file part was checked."""

        def break_fragment(document) -> None:
            self._row(document, "ak.snapshot_witness_attestation_proof.v1")[
                "schema_ref"
            ] = "schemas/snapshot.schema.json#/$defs/no_such_family"

        errors = self._run_with_mutations({REGISTRY: break_fragment})
        self.assertAnyContains(errors, "schema_ref fragment does not resolve to a schema node")

    def test_witness_attestation_cannot_fall_back_to_manifest_context(self) -> None:
        """Deleting the witness row leaves the schema claiming an unregistered context."""
        errors = self._run_with_mutations(
            {
                REGISTRY: lambda doc: self._drop_row(
                    doc, "ak.snapshot_witness_attestation_proof.v1"
                )
            }
        )
        self.assertAnyContains(
            errors, "names an unregistered proof context: ak.snapshot_witness_attestation_proof.v1"
        )

    def test_witness_context_cannot_be_registered_as_a_second_file_level_row(self) -> None:
        """Two rows on one anchor are a multi-consumer family, not a silent alias."""

        def flatten(document) -> None:
            self._row(document, "ak.snapshot_witness_attestation_proof.v1")[
                "schema_ref"
            ] = "schemas/snapshot.schema.json"

        errors = self._run_with_mutations({REGISTRY: flatten})
        self.assertAnyContains(errors, "is claimed by 2 contexts")

    def test_annotation_must_match_the_registry_row(self) -> None:
        def drift(document) -> None:
            document["$defs"]["snapshot_witness_attestation"][
                "x-arkret-proof-context"
            ] = "ak.snapshot_proof.v1"

        errors = self._run_with_mutations({SCHEMAS / "snapshot.schema.json": drift})
        self.assertAnyContains(errors, "but the registry binds")

    def test_second_consumer_of_a_shared_leaf_needs_its_own_operation(self) -> None:
        """A second high-risk consumer may not inherit the key-backup transcript context."""

        def add_consumer(document) -> None:
            row = copy.deepcopy(self._row(document, "ak.key_backup_delete_proof.v1"))
            row["context"] = "ak.realm_history_erasure_proof.v1"
            row["object_family"] = "realm_history_erasure_authority"
            row.pop("consumer_operation")
            document["contexts"].append(row)

        errors = self._run_with_mutations(
            {
                REGISTRY: add_consumer,
                SCHEMAS
                / "high-risk-authority-proof.schema.json": lambda doc: doc[
                    "x-arkret-proof-contexts"
                ].append("ak.realm_history_erasure_proof.v1"),
            }
        )
        self.assertAnyContains(errors, "must each declare consumer_operation")

    def test_shared_leaf_annotation_must_enumerate_every_consumer_row(self) -> None:
        def add_consumer(document) -> None:
            row = copy.deepcopy(self._row(document, "ak.key_backup_delete_proof.v1"))
            row["context"] = "ak.realm_history_erasure_proof.v1"
            row["object_family"] = "realm_history_erasure_authority"
            row["consumer_operation"] = "ak.self.keys.backups.command.unlock.v1"
            document["contexts"].append(row)

        errors = self._run_with_mutations({REGISTRY: add_consumer})
        self.assertAnyContains(errors, "x-arkret-proof-contexts")

    def test_consumer_operation_must_be_registered(self) -> None:
        def bogus(document) -> None:
            self._row(document, "ak.key_backup_delete_proof.v1")[
                "consumer_operation"
            ] = "ak.self.keys.backups.command.not_an_operation.v1"

        errors = self._run_with_mutations({REGISTRY: bogus})
        self.assertAnyContains(errors, "consumer_operation is not a registered operation")

    def test_dto_container_may_not_pack_families_behind_one_proof_node(self) -> None:
        """The directory state: 5 request families, one shared proofs alias, one row."""

        def repack_registry(document) -> None:
            for context in (
                "ak.directory_resolve_target_request_proof.v1",
                "ak.directory_resolve_organization_request_proof.v1",
                "ak.directory_resolve_handle_request_proof.v1",
                "ak.directory_resolve_agent_selector_request_proof.v1",
                "ak.directory_list_handles_for_subject_request_proof.v1",
            ):
                self._drop_row(document, context)
            document["contexts"].append(
                {
                    "context": "ak.directory_operation_proof.v1",
                    "object_family": "directory_operation",
                    "binding_fields": ["payload_digest", "issuer", "operation_id"],
                    "defined_in": "zh/discovery/discovery-directory.md",
                    "schema_ref": "schemas/directory-operations.schema.json",
                }
            )

        def repack_schema(document) -> None:
            document["$defs"]["proofs"] = {
                "type": "array",
                "items": {"$ref": "#/$defs/proof"},
                "minItems": 1,
            }
            for family in DIRECTORY_PROOF_FAMILIES:
                node = document["$defs"][family]
                node.pop("x-arkret-proof-context")
                node["properties"]["proofs"] = {"$ref": "#/$defs/proofs"}

        errors = self._run_with_mutations(
            {
                REGISTRY: repack_registry,
                SCHEMAS / "directory-operations.schema.json": repack_schema,
            }
        )
        self.assertAnyContains(errors, "is a packed shared-proof leaf")
        self.assertAnyContains(errors, "5 object families")

    def test_each_dto_request_family_needs_its_own_row(self) -> None:
        """Dropping one per-family row must not fall back to a sibling family's context."""
        errors = self._run_with_mutations(
            {
                REGISTRY: lambda doc: self._drop_row(
                    doc, "ak.mimi_identifier_query_outcome_proof.v1"
                ),
                SCHEMAS
                / "mimi-operations.schema.json": lambda doc: doc["$defs"][
                    "mimi_identifier_query_outcome"
                ].pop("x-arkret-proof-context"),
            }
        )
        self.assertAnyContains(
            errors,
            "shared detached-proof use point has no registered context: "
            "schemas/mimi-operations.schema.json#/$defs/mimi_identifier_query_outcome"
            "/properties/proofs/items",
        )

    def test_replay_cache_namespace_must_be_registered(self) -> None:
        """The websocket state: a replay-ledger namespace living only in prose."""

        def drop_namespace(document) -> None:
            document["domain_separations"] = [
                row
                for row in document["domain_separations"]
                if row.get("domain") != "ak.websocket_auth.v1"
            ]

        errors = self._run_with_mutations({REGISTRY: drop_namespace})
        self.assertAnyContains(errors, "is not a registered replay-cache namespace")

    def test_replay_cache_namespace_must_appear_in_its_declared_source(self) -> None:
        def move_source(document) -> None:
            for row in document["domain_separations"]:
                if row.get("domain") == "ak.websocket_auth.v1":
                    row["defined_in"] = "zh/sync/federation.md"

        errors = self._run_with_mutations({REGISTRY: move_source})
        self.assertAnyContains(
            errors, "ak.websocket_auth.v1 is not defined in its declared source"
        )

    def test_domain_separation_may_not_reuse_a_proof_context_label(self) -> None:
        def rename(document) -> None:
            for row in document["domain_separations"]:
                if row.get("domain") == "ak.websocket_auth.v1":
                    row["domain"] = "ak.event_proof.v1"

        errors = self._run_with_mutations({REGISTRY: rename})
        self.assertAnyContains(
            errors, "registered as both context and domain separation"
        )

    def test_domain_separation_primitive_is_a_closed_set(self) -> None:
        def widen(document) -> None:
            for row in document["domain_separations"]:
                if row.get("domain") == "ak.websocket_auth.v1":
                    row["primitive"] = "replay_namespace"

        errors = self._run_with_mutations({REGISTRY: widen})
        self.assertAnyContains(errors, "is not a registered primitive")

    def test_proof_context_field_may_not_carry_a_replay_namespace(self) -> None:
        """The exact naming collision 0748 reported: a namespace in a proof_context field."""

        def collide(document) -> None:
            kat = document["dpop_kat"]
            kat["proof_context"] = kat.pop("replay_cache_namespace")

        errors = self._run_with_mutations({WEBSOCKET_FIXTURE: collide})
        self.assertAnyContains(errors, "is not a registered proof context: 'ak.websocket_auth.v1'")

    def test_domain_separation_label_must_use_dot_and_snake_case(self) -> None:
        def drift(document) -> None:
            for row in document["domain_separations"]:
                if row.get("domain") == "ak.websocket_auth.v1":
                    row["domain"] = "ak.websocket-auth.v1"

        errors = self._run_with_mutations({REGISTRY: drift})
        self.assertAnyContains(errors, "canonical dot-separated snake_case v1 label")

    def test_main_entrypoint_runs_the_gate_and_fails(self) -> None:
        """The gate is worthless unless artifact-lint's own entrypoint calls it."""
        self.assertIn(
            "check_proof_context_registry(lint)",
            inspect.getsource(runner.main),
        )


if __name__ == "__main__":
    unittest.main()
