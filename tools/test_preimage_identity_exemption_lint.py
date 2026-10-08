"""Mutation tests for the structural encoding.md §3.1 preimage gate."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import schemas as lint_artifacts
from tools.artifact_lint.core import (
    Lint,
    PREIMAGE_COMMITMENT_KEYWORD,
    PREIMAGE_EXEMPTION_SECTION_CITATION,
    PREIMAGE_EXEMPTION_SECTION_NUMBER,
)

ARTIFACTS = ROOT / "spec" / "v1" / "artifacts"
REGISTRY_PATH = (ARTIFACTS / "registry" / "preimage-identity-exemption-registry.json").resolve()
PROVISION_SCHEMA_PATH = (ARTIFACTS / "schemas" / "agent-provision.schema.json").resolve()
APPROVAL_SCHEMA_PATH = (ARTIFACTS / "schemas" / "approval-signature.schema.json").resolve()
ENVELOPE_SCHEMA_PATH = (ARTIFACTS / "schemas" / "event-envelope.schema.json").resolve()
EVENT_PAYLOAD_PATH = (ARTIFACTS / "schemas" / "event-payload.schema.json").resolve()
RECOVERY_POLICY_PATH = (ARTIFACTS / "schemas" / "recovery-policy.schema.json").resolve()
SERVICE_DTO_PATH = (ARTIFACTS / "schemas" / "service-operation-dtos.schema.json").resolve()
ENCODING_PATH = (ROOT / "spec" / "v1" / "zh" / "conformance" / "encoding.md").resolve()

REGISTERED_EXEMPTION = "ak.exemption.preimage_identity.agent_provision_principal_control_realm_id.v1"


class PreimageIdentityExemptionLintTest(unittest.TestCase):
    def _run(self, *, json_mutations=None, text_mutations=None) -> list[str]:
        json_mutations = json_mutations or {}
        text_mutations = text_mutations or {}
        original_load_json = lint_artifacts.load_json
        original_read_text = lint_artifacts.read_text

        mutated_json: dict[Path, object] = {}
        for path, mutate in json_mutations.items():
            document = copy.deepcopy(original_load_json(Lint(), path))
            mutate(document)
            mutated_json[path] = document
        mutated_text = {
            path: mutate(original_read_text(path)) for path, mutate in text_mutations.items()
        }

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
            lint = Lint()
            lint_artifacts.check_preimage_event_identity_commitments(lint)
            return lint.errors
        finally:
            lint_artifacts.load_json = original_load_json
            lint_artifacts.read_text = original_read_text

    @staticmethod
    def _registered_row(registry: dict) -> dict:
        return next(
            row for row in registry["exemptions"] if row["exemption_id"] == REGISTERED_EXEMPTION
        )

    @staticmethod
    def _declared_field(schema: dict) -> dict:
        return schema["properties"]["principal_control_realm_id"]

    def test_a_committed_tree_passes(self) -> None:
        self.assertEqual(self._run(), [])

    def test_b_non_event_honest_wording_is_outside_scope(self) -> None:
        def mutate(schema):
            field = schema["$defs"]["approval_target"]["oneOf"][0]["properties"]["event_id"]
            field["description"] = (
                "The target Event is already frozen but not yet submitted when this approval is signed."
            )

        self.assertEqual(self._run(json_mutations={APPROVAL_SCHEMA_PATH: mutate}), [])

    def test_c_unregistered_later_submission_is_red(self) -> None:
        def mutate(schema):
            schema["properties"]["companion_event_id"] = {
                "type": "string",
                PREIMAGE_COMMITMENT_KEYWORD: "later_submission",
                "description": "Event from another submission.",
            }

        errors = self._run(json_mutations={ENVELOPE_SCHEMA_PATH: mutate})
        self.assertTrue(any("carries no row" in error for error in errors), errors)

    def test_d_rewording_cannot_hide_later_submission(self) -> None:
        def mutate(schema):
            schema["properties"]["companion_event_id"] = {
                "type": "string",
                PREIMAGE_COMMITMENT_KEYWORD: "later_submission",
                "description": "The author froze the other bytes first and will hand them in afterwards.",
            }

        errors = self._run(json_mutations={ENVELOPE_SCHEMA_PATH: mutate})
        self.assertTrue(any("carries no row" in error for error in errors), errors)

    def test_candidate_requires_structured_declaration(self) -> None:
        def mutate(schema):
            del schema["properties"]["event_id"][PREIMAGE_COMMITMENT_KEYWORD]

        errors = self._run(json_mutations={ENVELOPE_SCHEMA_PATH: mutate})
        self.assertTrue(any("must declare x-arkret-preimage-commitment" in error for error in errors), errors)

    def test_unknown_declaration_is_red(self) -> None:
        def mutate(schema):
            schema["properties"]["event_id"][PREIMAGE_COMMITMENT_KEYWORD] = "wording_decides"

        errors = self._run(json_mutations={ENVELOPE_SCHEMA_PATH: mutate})
        self.assertTrue(any("must declare x-arkret-preimage-commitment" in error for error in errors), errors)

    def test_self_and_same_unit_are_unconditionally_red(self) -> None:
        for declaration in ("self_identity", "same_unit_sibling"):
            with self.subTest(declaration=declaration):
                def mutate(schema, value=declaration):
                    schema["properties"]["event_id"][PREIMAGE_COMMITMENT_KEYWORD] = value

                errors = self._run(json_mutations={ENVELOPE_SCHEMA_PATH: mutate})
                self.assertTrue(any("No registry row can exempt it" in error for error in errors), errors)

    def test_no_event_identity_cannot_mask_a_named_event_field(self) -> None:
        def mutate(schema):
            schema["properties"]["event_id"][PREIMAGE_COMMITMENT_KEYWORD] = "no_event_identity"

        errors = self._run(json_mutations={ENVELOPE_SCHEMA_PATH: mutate})
        self.assertTrue(any("cannot declare no_event_identity" in error for error in errors), errors)

    def test_pointer_closure_is_39_candidates_in_13_files(self) -> None:
        lint = Lint()
        candidates = lint_artifacts.preimage_reachable_properties(lint)
        self.assertEqual(lint.errors, [])
        # Owned authority, controller membership and other accepted payload
        # references remain in the closure. Withdrawn invocation references are absent;
        # Policy CAS and the private review request add no producer Event ID.
        self.assertEqual(len(candidates), 39)
        self.assertEqual(len({key[0] for key in candidates}), 13)
        self.assertFalse(any(key[0] == "approval-signature.schema.json" for key in candidates))

    def test_unreferenced_defs_sibling_is_not_walked(self) -> None:
        def mutate(schema):
            schema["$defs"]["unused_probe"] = {
                "type": "object",
                "properties": {"unregistered_event_id": {"type": "string"}},
            }

        self.assertEqual(self._run(json_mutations={ENVELOPE_SCHEMA_PATH: mutate}), [])

    def test_known_four_hop_defs_leak_path_stays_outside_scope(self) -> None:
        event_payload = lint_artifacts.load_json(Lint(), EVENT_PAYLOAD_PATH)
        recovery = lint_artifacts.load_json(Lint(), RECOVERY_POLICY_PATH)
        service = lint_artifacts.load_json(Lint(), SERVICE_DTO_PATH)
        refs = event_payload["$defs"]["policy_set_state_payload"]["properties"]["value"]["oneOf"]
        self.assertIn({"$ref": "./recovery-policy.schema.json"}, refs)
        self.assertEqual(
            recovery["$defs"]["recovery_policy_publish_request"]["allOf"][0]["$ref"],
            "./service-operation-dtos.schema.json#/$defs/EventAdmissionSubmission",
        )
        self.assertEqual(
            service["$defs"]["EventAdmissionSubmission"]["properties"]["approval_signatures"]["items"]["$ref"],
            "./approval-signature.schema.json",
        )
        candidates = lint_artifacts.preimage_reachable_properties(Lint())
        self.assertFalse(any(key[0] == "approval-signature.schema.json" for key in candidates))

    def test_registered_field_must_keep_later_submission_declaration(self) -> None:
        def mutate(schema):
            self._declared_field(schema)[PREIMAGE_COMMITMENT_KEYWORD] = "fixed_event"

        errors = self._run(json_mutations={PROVISION_SCHEMA_PATH: mutate})
        self.assertTrue(any("instead of later_submission" in error for error in errors), errors)

    def test_registered_field_must_cite_canonical_section(self) -> None:
        def mutate(schema):
            field = self._declared_field(schema)
            field["description"] = field["description"].replace(
                PREIMAGE_EXEMPTION_SECTION_CITATION, "the encoding rules"
            )

        errors = self._run(json_mutations={PROVISION_SCHEMA_PATH: mutate})
        self.assertTrue(any("does not cite encoding.md §3.1" in error for error in errors), errors)

    def test_gate_derives_the_real_section_number_from_core(self) -> None:
        self.assertEqual(PREIMAGE_EXEMPTION_SECTION_NUMBER, "3.1")
        source = (ROOT / "tools" / "artifact_lint" / "schemas.py").read_text(encoding="utf-8")
        self.assertNotIn('"6.0.1"', source)
        self.assertNotIn('"3.1"', source)

    def test_registry_rejects_forbidden_direction(self) -> None:
        for direction in ("self_identity", "same_unit_sibling"):
            with self.subTest(direction=direction):
                def mutate(registry, value=direction):
                    self._registered_row(registry)["commitment_direction"] = value

                errors = self._run(json_mutations={REGISTRY_PATH: mutate})
                self.assertTrue(any("is a class A/B shape" in error for error in errors), errors)

    def test_stale_subject_fails(self) -> None:
        def mutate(registry):
            self._registered_row(registry)["subject"]["field"] = "principal_control_realm_id_renamed"

        errors = self._run(json_mutations={REGISTRY_PATH: mutate})
        self.assertTrue(any("which does not exist" in error for error in errors), errors)

    def test_prose_and_registry_are_bound_both_ways(self) -> None:
        def remove(text):
            return text.replace(REGISTERED_EXEMPTION, "ak.exemption.preimage_identity.unlisted.v1")

        errors = self._run(text_mutations={ENCODING_PATH: remove})
        self.assertTrue(any("does not appear in encoding.md §3.1" in error for error in errors), errors)

        def invent(text):
            return text.replace(
                "**封闭例外清单**：",
                "**封闭例外清单**：`ak.exemption.preimage_identity.invented.v1`",
            )

        errors = self._run(text_mutations={ENCODING_PATH: invent})
        self.assertTrue(any("which has no row here" in error for error in errors), errors)

    def test_evidence_must_be_an_active_vector(self) -> None:
        def mutate(registry):
            self._registered_row(registry)["conformance_vector_ids"] = ["ak.vector.does.not.exist.v1"]

        errors = self._run(json_mutations={REGISTRY_PATH: mutate})
        self.assertTrue(any("is not an active" in error for error in errors), errors)

    def test_registry_keyword_vocabulary_is_closed(self) -> None:
        def mutate(registry):
            registry["registry_rules"]["allowed_commitment_declarations"].append("free_text")

        errors = self._run(json_mutations={REGISTRY_PATH: mutate})
        self.assertTrue(any("must equal the closed gate vocabulary" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
