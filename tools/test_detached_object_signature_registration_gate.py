"""Single-mutation coverage for the six detached-object signature transcripts."""

from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import proof_context_schemas as gate
from tools.artifact_lint.core import Lint

ARTIFACTS = ROOT / "spec/v1/artifacts"


class DetachedObjectSignatureRegistrationGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = json.loads((ARTIFACTS / "registry/proof-context-registry.json").read_text(encoding="utf-8"))
        self.vector = json.loads((ARTIFACTS / "registry/vector-registry.json").read_text(encoding="utf-8"))
        self.signature_schema = json.loads((ARTIFACTS / "schemas/detached-object-signature.schema.json").read_text(encoding="utf-8"))
        self.fixture = json.loads((ARTIFACTS / "fixtures/detached-object-signature-kat-fixture.json").read_text(encoding="utf-8"))

    def errors_after(self, mutate) -> list[str]:
        documents = {
            "registry": copy.deepcopy(self.registry),
            "vector": copy.deepcopy(self.vector),
            "signature_schema": copy.deepcopy(self.signature_schema),
            "fixture": copy.deepcopy(self.fixture),
        }
        mutate(documents)
        with tempfile.TemporaryDirectory() as directory:
            artifacts = Path(directory) / "artifacts"
            shutil.copytree(ARTIFACTS / "schemas", artifacts / "schemas")
            (artifacts / "registry").mkdir(parents=True)
            (artifacts / "fixtures").mkdir(parents=True)
            paths = {
                "registry": artifacts / "registry/proof-context-registry.json",
                "vector": artifacts / "registry/vector-registry.json",
                "signature_schema": artifacts / "schemas/detached-object-signature.schema.json",
                "fixture": artifacts / "fixtures/detached-object-signature-kat-fixture.json",
            }
            for name, path in paths.items():
                path.write_text(json.dumps(documents[name]), encoding="utf-8", newline="\n")
            lint = Lint()
            with (
                mock.patch.object(gate, "ARTIFACTS", artifacts),
                mock.patch.object(gate, "PROOF_CONTEXT_REGISTRY", paths["registry"]),
                mock.patch.object(gate, "VECTOR_REGISTRY", paths["vector"]),
                mock.patch.object(gate, "DETACHED_OBJECT_SIGNATURE_SCHEMA", paths["signature_schema"]),
                mock.patch.object(gate, "DETACHED_OBJECT_SIGNATURE_FIXTURE", paths["fixture"]),
            ):
                gate.check_detached_object_signature_registration(lint)
            return lint.errors

    def assert_red(self, mutate, phrase: str) -> None:
        errors = self.errors_after(mutate)
        self.assertTrue(any(phrase in error for error in errors), errors)

    def row(self, document: dict, context: str) -> dict:
        return next(row for row in document["registry"]["domain_separations"] if row.get("domain") == context)

    def case(self, document: dict, context: str) -> dict:
        return next(case for case in document["fixture"]["cases"] if case.get("context") == context)

    def test_shipped_contract_passes(self) -> None:
        self.assertEqual(self.errors_after(lambda _: None), [])

    def test_p01_enum_def_host_ref_and_row_are_closed(self) -> None:
        self.assert_red(lambda d: d["signature_schema"]["properties"]["context"]["enum"].pop(), "context enum")

    def test_p02_seventh_or_wrong_primitive_is_rejected(self) -> None:
        self.assert_red(lambda d: self.row(d, "ak.realm_commit_signature.v1").__setitem__("primitive", "canonical_json_sha256"), "primitive")

    def test_p03_context_family_and_schema_cannot_be_swapped(self) -> None:
        self.assert_red(lambda d: self.row(d, "ak.realm_commit_signature.v1").__setitem__("schema_ref", "schemas/realm-state-snapshot.schema.json"), "schema_ref")

    def test_p04_handoff_must_exclude_both_signatures(self) -> None:
        self.assert_red(lambda d: self.row(d, "ak.realm_authority_handoff_old_signature.v1")["excluded_signature_members"].pop(), "excluded_signature_members")

    def test_p05_projection_is_from_complete_closed_host(self) -> None:
        self.assert_red(lambda d: self.case(d, "ak.realm_commit_signature.v1")["host_object"].__setitem__("unknown", True), "host schema validation")

    def test_p06_digest_suite_and_encoding_are_fixed(self) -> None:
        self.assert_red(lambda d: self.row(d, "ak.realm_commit_signature.v1").__setitem__("digest_suite", "BLAKE3"), "digest_suite")

    def test_p07_prefix_is_recomputed_with_one_lf(self) -> None:
        self.assert_red(lambda d: self.case(d, "ak.realm_commit_signature.v1").__setitem__("prefix_bytes_hex", "00"), "prefix_bytes_hex")

    def test_p08_all_five_envelope_members_are_signed(self) -> None:
        self.assert_red(lambda d: self.case(d, "ak.realm_commit_signature.v1")["signature_envelope_without_sig"].pop("created_at"), "envelope expected field")

    def test_p09_signature_input_cannot_be_replaced_by_a_digest(self) -> None:
        self.assert_red(lambda d: self.case(d, "ak.realm_commit_signature.v1").__setitem__("signature_input_hex", "00" * 32), "signature_input_hex")

    def test_p10_signature_encoding_is_exact_64_byte_unpadded_base64url(self) -> None:
        def mutate(d: dict) -> None:
            case = self.case(d, "ak.realm_commit_signature.v1")
            case["host_object"]["signature"]["sig"] += "="
            case["expected_sig"] += "="
        self.assert_red(mutate, "exactly 64 bytes")

    def test_p11_fake_digest_and_matching_carrier_are_recomputed_from_host(self) -> None:
        def mutate(d: dict) -> None:
            case = self.case(d, "ak.realm_commit_signature.v1")
            fake = "sha256:" + "0" * 64
            case["expected_signed_digest"] = fake
            case["host_object"]["signature"]["signed_digest"] = fake
            case["signature_envelope_without_sig"]["signed_digest"] = fake
        self.assert_red(mutate, "recomputed host digest")

    def test_p12_each_authority_family_has_its_own_wrong_key_rejection(self) -> None:
        for context in gate.DETACHED_SIGNATURE_CONTEXTS:
            with self.subTest(context=context):
                self.assert_red(lambda d, context=context: self.case(d, context)["authority_basis"].__setitem__("authorized_verification_method", "did:webvh:wrong:wrong.example#key"), "authority_basis")

    def test_p13_context_substitution_is_rejected_even_without_resigning(self) -> None:
        self.assert_red(lambda d: self.case(d, "ak.realm_commit_signature.v1")["host_object"]["signature"].__setitem__("context", "ak.realm_snapshot_signature.v1"), "carrier context")

    def test_p14_cross_family_signature_move_is_rejected(self) -> None:
        def mutate(d: dict) -> None:
            commit = self.case(d, "ak.realm_commit_signature.v1")
            snapshot = self.case(d, "ak.realm_snapshot_signature.v1")
            snapshot["host_object"]["signature"] = copy.deepcopy(commit["host_object"]["signature"])
        self.assert_red(mutate, "carrier context")

    def test_p15_handoff_old_and_new_share_one_digest_and_distinct_keys(self) -> None:
        self.assert_red(lambda d: self.case(d, "ak.realm_authority_handoff_new_acceptance_signature.v1").__setitem__("expected_signed_digest", "sha256:" + "f" * 64), "handoff old and new")

    def test_p16_every_expected_byte_field_is_recomputed(self) -> None:
        for field in ("unsigned_jcs_utf8_hex", "expected_signed_digest", "prefix_bytes_hex", "signature_input_hex", "expected_sig"):
            with self.subTest(field=field):
                self.assertTrue(self.errors_after(lambda d, field=field: self.case(d, "ak.realm_commit_signature.v1").__setitem__(field, "00")))

    def test_p17_runner_invokes_the_gate(self) -> None:
        source = (ROOT / "tools/artifact_lint/runner.py").read_text(encoding="utf-8")
        self.assertIn("check_detached_object_signature_registration(lint)", source)

    def test_p18_removed_snapshot_proof_context_cannot_return(self) -> None:
        self.assert_red(
            lambda d: d["registry"]["contexts"].append(
                {
                    "context": "ak.realm_state_snapshot_proof.v1",
                    "object_family": "realm_state_snapshot",
                    "binding_fields": ["payload_digest"],
                    "defined_in": "zh/conformance/realm-state-snapshot-schema.md",
                    "schema_ref": "schemas/realm-state-snapshot.schema.json",
                }
            ),
            "removed snapshot proof context",
        )


if __name__ == "__main__":
    unittest.main()
