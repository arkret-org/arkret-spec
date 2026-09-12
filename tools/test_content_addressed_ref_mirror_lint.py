"""encoding.md 4.0.1 gates: the mirror-removal lock and the pattern-driven sibling digest check.

The lock pins that a deleted sibling digest never returns under its old name. The
sibling digest check is what actually finds new ones: it pairs any content-addressed
ref pattern with any bare `<suite>:<hex>` pattern in the same closed object, whatever
the two fields are called, and only the closed exemption registry can let one stand.
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import core, schemas


SCHEMA_DIR = ROOT / "spec" / "v1" / "artifacts" / "schemas"
REGISTRY_DIR = ROOT / "spec" / "v1" / "artifacts" / "registry"
EXEMPTION_REGISTRY = "content-addressed-ref-digest-exemption-registry.json"
SCHEMA_NAMES = (
    "contact-operations.schema.json",
    "event-payload.schema.json",
    "direct-conversation-operations.schema.json",
    "mls-governance-proof-bundle.schema.json",
    "service-operation-dtos.schema.json",
    "seal.schema.json",
    "availability-receipt.schema.json",
    "event-envelope.schema.json",
)
DIGEST = {"type": "string", "pattern": "^(sha256|blake3):[0-9a-f]{64}$"}
BLOB_REF = {"type": "string", "pattern": "^ak:blob:(?:sha256|blake3):[0-9a-f]{64}$"}


class _MutatingLint(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.documents = {
            name: core.parse_json_text((SCHEMA_DIR / name).read_text(encoding="utf-8"))
            for name in SCHEMA_NAMES
        }
        cls.registry = core.parse_json_text((REGISTRY_DIR / EXEMPTION_REGISTRY).read_text(encoding="utf-8"))

    def _run(self, check, name: str | None = None, mutation=None, registry_mutation=None) -> list[str]:
        documents = copy.deepcopy(self.documents)
        registry = copy.deepcopy(self.registry)
        if name is not None and mutation is not None:
            mutation(documents[name])
        if registry_mutation is not None:
            registry_mutation(registry)
        original_load_json = schemas.load_json

        def load_json_with_mutation(lint, path):
            if path.parent.resolve() == SCHEMA_DIR.resolve() and path.name in documents:
                return documents[path.name]
            if path.resolve() == (REGISTRY_DIR / EXEMPTION_REGISTRY).resolve():
                return registry
            return original_load_json(lint, path)

        schemas.load_json = load_json_with_mutation
        try:
            lint = schemas.Lint()
            check(lint)
            return lint.errors
        finally:
            schemas.load_json = original_load_json

    def _lock(self, name=None, mutation=None) -> list[str]:
        return self._run(schemas.check_content_addressed_ref_mirror_removals, name, mutation)

    def _sibling(self, name=None, mutation=None, registry_mutation=None) -> list[str]:
        return self._run(schemas.check_content_addressed_ref_sibling_digests, name, mutation, registry_mutation)


class MirrorRemovalLockTest(_MutatingLint):
    def test_current_contract_is_closed(self) -> None:
        self.assertEqual(self._lock(), [])

    def test_request_digest_mirror_reintroduction_fails(self) -> None:
        def mutate(schema) -> None:
            core_def = schema["$defs"]["request_acceptance_receipt_core"]
            core_def["properties"]["request_digest"] = {
                "$ref": "./principal-operations.schema.json#/$defs/digest"
            }

        errors = self._lock("contact-operations.schema.json", mutate)
        self.assertTrue(any("request_digest must be derived" in error for error in errors), errors)

    def test_seal_digest_mirror_reintroduction_fails(self) -> None:
        def mutate(schema) -> None:
            item = schema["$defs"]["typed_proof_material"]["properties"]["seal_descriptors"]["items"]
            item["properties"]["seal_digest"] = {"$ref": "#/$defs/digest"}

        errors = self._lock("mls-governance-proof-bundle.schema.json", mutate)
        self.assertTrue(any("seal_digest must be derived" in error for error in errors), errors)

    def test_group_info_digest_reintroduction_fails(self) -> None:
        def mutate(schema) -> None:
            schema["$defs"]["mls_genesis_payload"]["properties"]["group_info_digest"] = dict(DIGEST)

        errors = self._lock("event-payload.schema.json", mutate)
        self.assertTrue(any("group_info_digest must be derived from group_info_ref" in error for error in errors), errors)

    def test_signer_evidence_digest_required_reintroduction_fails(self) -> None:
        def mutate(schema) -> None:
            schema["$defs"]["producer_event_proof"]["required"].append("signer_resolution_evidence_digest")

        errors = self._lock("event-envelope.schema.json", mutate)
        self.assertTrue(any("signer_resolution_evidence_digest must be derived" in error for error in errors), errors)

    def test_delegation_digest_reintroduction_fails(self) -> None:
        def mutate(schema) -> None:
            schema["$defs"]["MembershipCompensationCasToken"]["properties"]["delegation_digest"] = dict(DIGEST)

        errors = self._lock("service-operation-dtos.schema.json", mutate)
        self.assertTrue(any("delegation_digest must be derived from delegation_id" in error for error in errors), errors)

    def test_holder_evidence_digest_reintroduction_fails(self) -> None:
        def mutate(schema) -> None:
            schema["properties"]["holder_signer_evidence_digest"] = dict(DIGEST)

        errors = self._lock("availability-receipt.schema.json", mutate)
        self.assertTrue(any("holder_signer_evidence_digest must be derived" in error for error in errors), errors)


class SiblingDigestPatternGateTest(_MutatingLint):
    def test_current_schemas_and_registry_are_closed(self) -> None:
        self.assertEqual(self._sibling(), [])

    def test_arbitrary_names_are_still_caught(self) -> None:
        """The gate pairs patterns, not name stems: bar_ref + baz_digest is a hit."""

        def mutate(schema) -> None:
            schema["$defs"]["arbitrary_material_carrier"] = {
                "type": "object",
                "properties": {"bar_ref": dict(BLOB_REF), "baz_digest": dict(DIGEST)},
                "additionalProperties": False,
            }

        errors = self._sibling("service-operation-dtos.schema.json", mutate)
        self.assertTrue(
            any("$.$defs.arbitrary_material_carrier.properties.baz_digest is a bare digest next to content-addressed ref(s) bar_ref" in error for error in errors),
            errors,
        )

    def test_reintroduced_genesis_digest_is_caught_without_a_lock_row(self) -> None:
        def mutate(schema) -> None:
            schema["$defs"]["mls_genesis_payload"]["properties"]["group_info_digest"] = dict(DIGEST)

        errors = self._sibling("event-payload.schema.json", mutate)
        self.assertTrue(
            any("mls_genesis_payload.properties.group_info_digest is a bare digest" in error for error in errors),
            errors,
        )

    def test_digest_reached_through_ref_chain_is_caught(self) -> None:
        def mutate(schema) -> None:
            schema["$defs"]["MlsGroupStateMaterialOutcome"]["properties"]["material_digest"] = {
                "$ref": "./principal-operations.schema.json#/$defs/digest"
            }

        errors = self._sibling("service-operation-dtos.schema.json", mutate)
        self.assertTrue(any("MlsGroupStateMaterialOutcome.properties.material_digest is a bare digest" in error for error in errors), errors)

    def test_digest_without_any_content_addressed_sibling_is_not_a_candidate(self) -> None:
        def mutate(schema) -> None:
            schema["$defs"]["plain_digest_carrier"] = {
                "type": "object",
                "properties": {"note": {"type": "string"}, "payload_digest": dict(DIGEST)},
                "additionalProperties": False,
            }

        self.assertEqual(self._sibling("service-operation-dtos.schema.json", mutate), [])

    def test_stale_exemption_row_fails(self) -> None:
        def mutate(schema) -> None:
            del schema["properties"]["state_root"]

        errors = self._sibling("seal.schema.json", mutate)
        self.assertTrue(
            any("exempts seal.schema.json $.properties.state_root, which no longer exists" in error for error in errors),
            errors,
        )

    def test_changed_ref_set_needs_a_fresh_ruling(self) -> None:
        def mutate(schema) -> None:
            schema["properties"]["successor_seal_ref"] = {"$ref": "./event-envelope.schema.json#/$defs/seal_ref"}

        errors = self._sibling("seal.schema.json", mutate)
        self.assertTrue(any("state_root is exempted as" in error and "fresh ruling" in error for error in errors), errors)

    def test_union_ref_pattern_is_outside_the_gate(self) -> None:
        """A ref that may also hold a UUID, Event or DID form is not judged from the schema."""

        def mutate(schema) -> None:
            schema["$defs"]["dual_form_carrier"] = {
                "type": "object",
                "properties": {
                    "blob_ref": {
                        "type": "string",
                        "pattern": "^ak:blob:(?:[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}|(?:sha256|blake3):[0-9a-f]{64})$",
                    },
                    "content_digest": dict(DIGEST),
                },
                "additionalProperties": False,
            }

        self.assertEqual(self._sibling("service-operation-dtos.schema.json", mutate), [])

    def test_open_question_is_not_a_registrable_kind(self) -> None:
        def mutate_registry(registry) -> None:
            row = next(r for r in registry["exemptions"] if r["kind"] == "distinct_preimage")
            row["kind"] = "open_finding"
            row["spec_anchor"] = "arkret-work/review/spec-open/2026-09-02-2033-blob-ref-dual-form-and-content-digest-sibling.md"

        errors = self._sibling(registry_mutation=mutate_registry)
        self.assertTrue(any("kind must be distinct_preimage; an open question is not a ruling" in error for error in errors), errors)

    def test_distinct_preimage_anchor_must_exist(self) -> None:
        def mutate_registry(registry) -> None:
            row = next(r for r in registry["exemptions"] if r["kind"] == "distinct_preimage")
            row["spec_anchor"] = "spec/v1/zh/conformance/encoding.md#no-such-heading"

        errors = self._sibling(registry_mutation=mutate_registry)
        self.assertTrue(any("heading #no-such-heading does not exist" in error for error in errors), errors)

    def test_unknown_kind_row_is_dropped_and_its_field_is_then_caught(self) -> None:
        def mutate_registry(registry) -> None:
            row = next(r for r in registry["exemptions"] if r["subject"]["digest_field"] == "state_root" and r["subject"]["schema_file"] == "schemas/seal.schema.json")
            row["kind"] = "just_trust_me"

        errors = self._sibling(registry_mutation=mutate_registry)
        self.assertTrue(any("kind must be distinct_preimage; an open question is not a ruling" in error for error in errors), errors)
        self.assertTrue(any("seal.schema.json" in error and "$.properties.state_root is a bare digest" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
