"""Mutation tests for the encoding.md 6.0.1 named-exemption gate.

The gate used to decide by reading wording, so a field could slip past it by
being vague. It now decides by looking the field up in
`preimage-identity-exemption-registry.json`, which only helps if the registry
itself cannot rot: a row must keep pointing at a field that exists, the field
must keep declaring the forward commitment, class A/B shapes must stay
unexemptible, and the prose list and the registry must stay bound in both
directions. Every case below is one of those properties failing.
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import schemas as lint_artifacts

ARTIFACTS = ROOT / "spec" / "v1" / "artifacts"
REGISTRY_PATH = (ARTIFACTS / "registry" / "preimage-identity-exemption-registry.json").resolve()
PROVISION_SCHEMA_PATH = (ARTIFACTS / "schemas" / "agent-provision.schema.json").resolve()
ENCODING_PATH = (ROOT / "spec" / "v1" / "zh" / "conformance" / "encoding.md").resolve()

REGISTERED_EXEMPTION = "ak.exemption.preimage_identity.agent_provision_principal_control_realm_id.v1"


class PreimageIdentityExemptionLintTest(unittest.TestCase):
    def _run(self, *, json_mutations=None, text_mutations=None) -> list[str]:
        """Run the gate with selected files replaced by mutated copies."""
        json_mutations = json_mutations or {}
        text_mutations = text_mutations or {}
        original_load_json = lint_artifacts.load_json
        original_read_text = lint_artifacts.read_text

        mutated_json: dict[Path, object] = {}
        for path, mutate in json_mutations.items():
            document = copy.deepcopy(original_load_json(lint_artifacts.Lint(), path))
            mutate(document)
            mutated_json[path] = document

        mutated_text: dict[Path, str] = {}
        for path, mutate in text_mutations.items():
            mutated_text[path] = mutate(original_read_text(path))

        def load_json_with_mutation(lint, path):
            resolved = path.resolve()
            if resolved in mutated_json:
                return mutated_json[resolved]
            return original_load_json(lint, path)

        def read_text_with_mutation(path):
            resolved = path.resolve()
            if resolved in mutated_text:
                return mutated_text[resolved]
            return original_read_text(path)

        lint_artifacts.load_json = load_json_with_mutation
        lint_artifacts.read_text = read_text_with_mutation
        try:
            lint = lint_artifacts.Lint()
            lint_artifacts.check_preimage_event_identity_commitments(lint)
            return lint.errors
        finally:
            lint_artifacts.load_json = original_load_json
            lint_artifacts.read_text = original_read_text

    @staticmethod
    def _registered_row(registry: dict) -> dict:
        for row in registry["exemptions"]:
            if row["exemption_id"] == REGISTERED_EXEMPTION:
                return row
        raise AssertionError(f"{REGISTERED_EXEMPTION} is missing from the registry")

    @staticmethod
    def _declared_field(schema: dict) -> dict:
        return schema["properties"]["principal_control_realm_id"]

    def test_committed_tree_passes(self) -> None:
        self.assertEqual(self._run(), [])

    def test_unregistered_forward_declaration_fails(self) -> None:
        # The whole point of the registry: a new field may not simply announce
        # that it names an Event from another submission.
        def mutate(schema):
            schema["properties"]["controller_authorization_ref"]["description"] = (
                "Names the delegation Event from another submission; retype(event_id) of a "
                "genesis that is not yet submitted."
            )

        errors = self._run(json_mutations={PROVISION_SCHEMA_PATH: mutate})
        self.assertTrue(
            any("carries no row in preimage-identity-exemption-registry.json" in e for e in errors),
            errors,
        )

    def test_registered_field_cannot_declare_a_same_unit_sibling(self) -> None:
        # Class B stays unconditional even for a field that holds an exemption:
        # the registry can license a later submission, never a same-unit sibling.
        def mutate(schema):
            self._declared_field(schema)["description"] = (
                "retype(event_id) of the sibling event in the same atomic unit; see encoding.md 6.0.1."
            )

        errors = self._run(json_mutations={PROVISION_SCHEMA_PATH: mutate})
        self.assertTrue(
            any("No registry row can exempt it" in e for e in errors),
            errors,
        )

    def test_registry_rejects_a_self_identity_row(self) -> None:
        def mutate(registry):
            self._registered_row(registry)["commitment_direction"] = "self_identity"

        errors = self._run(json_mutations={REGISTRY_PATH: mutate})
        self.assertTrue(
            any("is a class A/B shape" in e for e in errors),
            errors,
        )

    def test_registry_rejects_a_same_unit_sibling_row(self) -> None:
        def mutate(registry):
            self._registered_row(registry)["commitment_direction"] = "same_unit_sibling"

        errors = self._run(json_mutations={REGISTRY_PATH: mutate})
        self.assertTrue(
            any("is a class A/B shape" in e for e in errors),
            errors,
        )

    def test_stale_subject_fails(self) -> None:
        # A row pointing at a field that no longer exists silently licenses
        # whatever later takes that name.
        def mutate(registry):
            self._registered_row(registry)["subject"]["field"] = "principal_control_realm_id_renamed"

        errors = self._run(json_mutations={REGISTRY_PATH: mutate})
        self.assertTrue(any("which does not exist" in e for e in errors), errors)

    def test_declaration_going_vague_fails(self) -> None:
        def mutate(schema):
            self._declared_field(schema)["description"] = (
                "Agent PCR realm id, retype(event_id) of the genesis create. See encoding.md 6.0.1."
            )

        errors = self._run(json_mutations={PROVISION_SCHEMA_PATH: mutate})
        self.assertTrue(
            any("no longer states that it commits to an Event from a later submission" in e for e in errors),
            errors,
        )

    def test_dropping_the_601_citation_fails(self) -> None:
        def mutate(schema):
            field = self._declared_field(schema)
            field["description"] = field["description"].replace("encoding.md 6.0.1", "the encoding rules")

        errors = self._run(json_mutations={PROVISION_SCHEMA_PATH: mutate})
        self.assertTrue(any("does not cite encoding.md 6.0.1" in e for e in errors), errors)

    def test_active_row_missing_from_the_prose_list_fails(self) -> None:
        def mutate(text):
            return text.replace(REGISTERED_EXEMPTION, "ak.exemption.preimage_identity.unlisted.v1")

        errors = self._run(text_mutations={ENCODING_PATH: mutate})
        self.assertTrue(
            any("does not appear in encoding.md 6.0.1's closed list table" in e for e in errors),
            errors,
        )

    def test_prose_list_naming_an_unregistered_exemption_fails(self) -> None:
        def mutate(text):
            return text.replace(
                "**封闭例外清单**：",
                "**封闭例外清单**：`ak.exemption.preimage_identity.invented.v1`",
            )

        errors = self._run(text_mutations={ENCODING_PATH: mutate})
        self.assertTrue(any("which has no row here" in e for e in errors), errors)

    def test_evidence_must_be_an_active_vector(self) -> None:
        def mutate(registry):
            self._registered_row(registry)["conformance_vector_ids"] = ["ak.vector.does.not.exist.v1"]

        errors = self._run(json_mutations={REGISTRY_PATH: mutate})
        self.assertTrue(
            any("is not an active " in e and "vector-registry.json" in e for e in errors),
            errors,
        )

    def test_missing_row_key_fails(self) -> None:
        def mutate(registry):
            del self._registered_row(registry)["absent_target_semantics"]

        errors = self._run(json_mutations={REGISTRY_PATH: mutate})
        self.assertTrue(any("is missing required keys" in e for e in errors), errors)

    def test_broken_spec_anchor_fails(self) -> None:
        def mutate(registry):
            row = self._registered_row(registry)
            row["spec_anchor"] = "spec/v1/zh/identity/key-management.md#no-such-heading"

        errors = self._run(json_mutations={REGISTRY_PATH: mutate})
        self.assertTrue(any("spec_anchor heading does not exist" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
