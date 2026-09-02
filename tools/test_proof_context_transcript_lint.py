"""Mutation tests for the per-object-family proof transcript gate.

Each case below is a way the 63 registered proof contexts could go back to having
no byte-level truth source without any other gate noticing: a context row added
with no vector, a vector quietly deprecated, two vectors claiming one context, an
absent optional binding field written as `null` instead of omitted, a single
audience wrapped in a one-element array, the context constant moved out of the
binding object and into the JWS header, a payload digest that no longer matches
its own preimage, and a cross-family negative case degraded back into a copy of
the accept case. A coverage gate that does not fail on each of these is only
paperwork, so the last test also proves artifact-lint's own entrypoint runs it.
"""

from __future__ import annotations

import copy
import inspect
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import proof_context_transcripts, runner
from tools.artifact_lint.core import Lint
from tools import regenerate_proof_context_transcript_fixture as generator

ARTIFACTS = ROOT / "spec" / "v1" / "artifacts"
REGISTRY = ARTIFACTS / "registry" / "proof-context-registry.json"
VECTOR_REGISTRY = ARTIFACTS / "registry" / "vector-registry.json"
FIXTURE = ARTIFACTS / "fixtures" / "proof-context-transcript-fixture.json"

SAMPLE_CONTEXT = "ak.accountability_grant_proof.v1"
SAMPLE_FAMILY = "accountability_grant"
SAMPLE_VECTOR = "ak.vector.proof_context.transcript.accountability_grant.v1"

# A family whose binding carries a required single-value audience.
REQUIRED_AUDIENCE_FAMILY = "directory_source_ref_access"


class ProofContextTranscriptLintTest(unittest.TestCase):
    def test_actor_reference_keeps_the_complete_identity(self) -> None:
        value = generator.body_value(
            "actor_id",
            {"$ref": "./common-ids.schema.json#/$defs/actor_id"},
            generator.SchemaIndex(),
            "signal-envelope.schema.json",
        )
        self.assertEqual(value["kind"], "account")
        self.assertEqual(value["account_id"], generator.VALUE_TABLE["account_id"])

    def test_signal_transcript_binds_the_complete_actor(self) -> None:
        document = generator.build_document()
        case = self._case(document, "signal_envelope")
        self.assertEqual(case["unsigned_object"]["sender_actor_id"]["kind"], "account")
        self.assertEqual(
            case["binding_object"]["sender_actor_id"],
            case["unsigned_object"]["sender_actor_id"],
        )

    def _run_with_mutations(self, mutations: dict[Path, object]) -> list[str]:
        original_load_json = proof_context_transcripts.load_json
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

        proof_context_transcripts.load_json = load_json_with_mutation
        try:
            lint = Lint()
            proof_context_transcripts.check_proof_context_transcript_vectors(lint)
            return lint.errors
        finally:
            proof_context_transcripts.load_json = original_load_json

    @staticmethod
    def _vector_row(document, vector_id: str) -> dict:
        for row in document["vectors"]:
            if row.get("vector_id") == vector_id:
                return row
        raise AssertionError(f"missing vector row {vector_id}")

    @staticmethod
    def _case(document, family: str) -> dict:
        for case in document["cases"]:
            if case.get("object_family") == family:
                return case
        raise AssertionError(f"missing transcript case {family}")

    @staticmethod
    def _case_index(document, family: str) -> int:
        for index, case in enumerate(document["cases"]):
            if case.get("object_family") == family:
                return index
        raise AssertionError(f"missing transcript case {family}")

    def assertAnyContains(self, errors: list[str], needle: str) -> None:
        self.assertTrue(
            any(needle in error for error in errors),
            f"no error contained {needle!r}; got {errors}",
        )

    def test_baseline_is_clean(self) -> None:
        lint = Lint()
        proof_context_transcripts.check_proof_context_transcript_vectors(lint)
        self.assertEqual(lint.errors, [])

    def test_new_context_without_a_vector_fails(self) -> None:
        """The state the report describes: contexts grow, vectors do not."""

        def add_row(document) -> None:
            row = copy.deepcopy(document["contexts"][0])
            row["context"] = "ak.new_object_family_proof.v1"
            row["object_family"] = "new_object_family"
            document["contexts"].append(row)

        errors = self._run_with_mutations({REGISTRY: add_row})
        self.assertAnyContains(errors, "ak.new_object_family_proof.v1 has no transcript vector")
        self.assertAnyContains(
            errors, "ak.vector.proof_context.transcript.new_object_family.v1"
        )

    def test_removed_vector_row_fails(self) -> None:
        def drop(document) -> None:
            document["vectors"] = [
                row for row in document["vectors"] if row.get("vector_id") != SAMPLE_VECTOR
            ]

        errors = self._run_with_mutations({VECTOR_REGISTRY: drop})
        self.assertAnyContains(errors, f"proof context {SAMPLE_CONTEXT} has no transcript vector")

    def test_deprecated_vector_row_fails(self) -> None:
        def deprecate(document) -> None:
            self._vector_row(document, SAMPLE_VECTOR)["status"] = "deprecated"

        errors = self._run_with_mutations({VECTOR_REGISTRY: deprecate})
        self.assertAnyContains(errors, "must stay active while its context is registered")

    def test_duplicate_coverage_fails(self) -> None:
        def duplicate(document) -> None:
            row = copy.deepcopy(self._vector_row(document, SAMPLE_VECTOR))
            row["vector_id"] = "ak.vector.proof_context.transcript.accountability_grant_copy.v1"
            document["vectors"].append(row)

        errors = self._run_with_mutations({VECTOR_REGISTRY: duplicate})
        self.assertAnyContains(errors, "duplicates transcript coverage of")

    def test_vector_named_after_the_wrong_family_fails(self) -> None:
        def rename(document) -> None:
            row = self._vector_row(document, SAMPLE_VECTOR)
            row["vector_id"] = "ak.vector.proof_context.transcript.some_other_family.v1"

        errors = self._run_with_mutations({VECTOR_REGISTRY: rename})
        self.assertAnyContains(errors, "must be named after the object family it covers")

    def test_second_coverage_bookkeeping_in_the_registry_fails(self) -> None:
        """Coverage lives in one place; a second copy is a future disagreement."""

        def duplicate_bookkeeping(document) -> None:
            document["contexts"][0]["conformance_vector_ids"] = [SAMPLE_VECTOR]

        errors = self._run_with_mutations({REGISTRY: duplicate_bookkeeping})
        self.assertAnyContains(errors, "transcript vector coverage is recorded once")

    def test_absent_optional_written_as_null_fails(self) -> None:
        def nullify(document) -> None:
            self._case(document, SAMPLE_FAMILY)["binding_object"]["audience"] = None

        errors = self._run_with_mutations({FIXTURE: nullify})
        self.assertAnyContains(
            errors, "an absent optional binding field is omitted, never written as null"
        )

    def test_single_audience_wrapped_in_an_array_fails(self) -> None:
        def wrap(document) -> None:
            binding = self._case(document, REQUIRED_AUDIENCE_FAMILY)["binding_object"]
            binding["audience"] = [binding["audience"]]

        errors = self._run_with_mutations({FIXTURE: wrap})
        self.assertAnyContains(errors, "wraps one value in an array")

    def test_context_moved_into_the_jws_header_fails(self) -> None:
        def move(document) -> None:
            case = self._case(document, SAMPLE_FAMILY)
            case["protected_header"]["context"] = case["binding_object"].pop("context")

        errors = self._run_with_mutations({FIXTURE: move})
        self.assertAnyContains(
            errors, "the context constant is a binding object member, never a JWS header parameter"
        )

    def test_binding_object_dropping_the_context_fails(self) -> None:
        def drop(document) -> None:
            self._case(document, SAMPLE_FAMILY)["binding_object"].pop("context")

        errors = self._run_with_mutations({FIXTURE: drop})
        self.assertAnyContains(errors, "are not the registered binding closure")

    def test_carrier_nulled_instead_of_deleted_fails(self) -> None:
        def nullify(document) -> None:
            projection = self._case(document, SAMPLE_FAMILY)["unsigned_projection"]
            for member in projection["removed_member_values"]:
                projection["removed_member_values"][member] = None

        errors = self._run_with_mutations({FIXTURE: nullify})
        self.assertAnyContains(errors, "removes a member by writing null")

    def test_payload_digest_drifting_from_its_preimage_fails(self) -> None:
        def drift(document) -> None:
            case = self._case(document, SAMPLE_FAMILY)
            case["binding_object"]["payload_digest"] = "sha256:" + "0" * 64

        errors = self._run_with_mutations({FIXTURE: drift})
        self.assertAnyContains(
            errors, "does not equal the recomputed digest of the unsigned projection"
        )

    def test_unsigned_body_drifting_from_its_canonical_bytes_fails(self) -> None:
        def drift(document) -> None:
            self._case(document, SAMPLE_FAMILY)["unsigned_object"]["issuer"] = "ak:did_core:webvh:z6mkother"

        errors = self._run_with_mutations({FIXTURE: drift})
        self.assertAnyContains(errors, "unsigned_jcs is not JCS(unsigned_object)")

    def test_negative_case_degraded_into_the_accept_case_fails(self) -> None:
        """Without a real cross-family replay the vector proves no separation."""

        def degrade(document) -> None:
            index = self._case_index(document, SAMPLE_FAMILY)
            case = document["cases"][index]
            negative = document["negative_cases"][index]
            negative["signed_binding_jcs"] = case["binding_jcs"]
            negative["signature"] = case["signature"]
            negative["detached_jws"] = case["detached_jws"]

        errors = self._run_with_mutations({FIXTURE: degrade})
        self.assertAnyContains(errors, "anything else stops testing domain separation")

    def test_negative_case_reusing_its_own_context_fails(self) -> None:
        def reuse(document) -> None:
            index = self._case_index(document, SAMPLE_FAMILY)
            negative = document["negative_cases"][index]
            negative["substituted_context"] = negative["registered_context"]

        errors = self._run_with_mutations({FIXTURE: reuse})
        self.assertAnyContains(errors, "must replay under the adjacent registry row")

    def test_missing_negative_cases_fail(self) -> None:
        def drop(document) -> None:
            document["negative_cases"] = document["negative_cases"][:-1]

        errors = self._run_with_mutations({FIXTURE: drop})
        self.assertAnyContains(
            errors, "a positive-only vector cannot prove domain separation"
        )

    def test_second_test_key_fails(self) -> None:
        def swap(document) -> None:
            document["test_key"]["private_key_seed"] = "AQIDBAUGBwgJCgsMDQ4PEBESExQVFhcYGRobHB0eHyA"

        errors = self._run_with_mutations({FIXTURE: swap})
        self.assertAnyContains(errors, "must be the shared conformance seed")

    def test_main_entrypoint_runs_the_gate_and_fails(self) -> None:
        """The gate is worthless unless artifact-lint's own entrypoint calls it."""
        self.assertIn(
            "check_proof_context_transcript_vectors(lint)",
            inspect.getsource(runner.main),
        )


if __name__ == "__main__":
    unittest.main()
