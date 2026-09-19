from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from artifact_lint import proof_context_schemas as gate
from artifact_lint.core import ARTIFACTS, Lint, ROOT


class LocalSignatureBindingFieldsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.artifacts = Path(self.temporary.name) / "artifacts"
        for relative in (
            "registry/proof-context-registry.json",
            "registry/signature-alg-registry.json",
            "schemas/account-operations.schema.json",
        ):
            target = self.artifacts / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ARTIFACTS / relative, target)
        registry_path = self.artifacts / "registry/proof-context-registry.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        registry["domain_separations"] = [
            row
            for row in registry["domain_separations"]
            if row.get("domain") == "ak.identity_creation_control_proof.v1"
        ]
        registry_path.write_text(
            json.dumps(registry, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def read(self, relative: str) -> dict:
        return json.loads((self.artifacts / relative).read_text(encoding="utf-8"))

    def write(self, relative: str, value: dict) -> None:
        (self.artifacts / relative).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    def run_gate(self) -> list[str]:
        lint = Lint()
        with (
            patch.object(gate, "ARTIFACTS", self.artifacts),
            patch.object(gate, "PROOF_CONTEXT_REGISTRY", self.artifacts / "registry/proof-context-registry.json"),
        ):
            gate.check_local_signature_binding_fields_match_schema(lint)
        return lint.errors

    def mutate_identity_row(self, mutation) -> None:
        relative = "registry/proof-context-registry.json"
        data = self.read(relative)
        row = next(
            item
            for item in data["domain_separations"]
            if item.get("domain") == "ak.identity_creation_control_proof.v1"
        )
        mutation(row)
        self.write(relative, data)

    def assert_rejected(self, phrase: str) -> None:
        errors = self.run_gate()
        self.assertTrue(any(phrase in error for error in errors), "\n".join(errors))

    def test_shipped_local_signature_contract_passes(self) -> None:
        self.assertEqual(self.run_gate(), [])

    def test_missing_required_binding_field_is_rejected(self) -> None:
        self.mutate_identity_row(lambda row: row["binding_fields"].remove("account_subject"))
        self.assert_rejected("missing=['account_subject']")

    def test_unknown_binding_field_is_rejected(self) -> None:
        self.mutate_identity_row(lambda row: row["binding_fields"].append("phantom"))
        self.assert_rejected("extra=['phantom']")

    def test_schema_required_member_cannot_outpace_registry(self) -> None:
        relative = "schemas/account-operations.schema.json"
        data = self.read(relative)
        proof = data["$defs"]["identity_creation_control_proof"]
        proof["required"].append("new_signed_member")
        proof["properties"]["new_signed_member"] = {"type": "string"}
        self.write(relative, data)
        self.assert_rejected("missing=['new_signed_member']")

    def test_signature_algorithm_must_be_an_active_raw_mapping(self) -> None:
        relative = "schemas/account-operations.schema.json"
        data = self.read(relative)
        data["$defs"]["identity_creation_control_proof"]["properties"]["signature_algorithm"]["const"] = "EdDSA"
        self.write(relative, data)
        self.assert_rejected("active raw_signature_algorithm")

    def test_outer_shared_proof_carrier_is_not_subject_to_required_equality(self) -> None:
        relative = "registry/proof-context-registry.json"
        data = self.read(relative)
        data["contexts"][0]["binding_fields"] = ["proof_leaf_binding_only"]
        self.write(relative, data)
        self.assertEqual(self.run_gate(), [])

    def test_identity_domain_is_not_a_shared_proof_context(self) -> None:
        data = self.read("registry/proof-context-registry.json")
        self.assertNotIn(
            "ak.identity_creation_control_proof.v1",
            {row.get("context") for row in data["contexts"]},
        )
        self.assertIn(
            "ak.identity_creation_control_proof.v1",
            {row.get("domain") for row in data["domain_separations"]},
        )

    def test_runner_invokes_gate(self) -> None:
        source = (ROOT / "tools/artifact_lint/runner.py").read_text(encoding="utf-8")
        self.assertIn("check_local_signature_binding_fields_match_schema(lint)", source)


if __name__ == "__main__":
    unittest.main()
