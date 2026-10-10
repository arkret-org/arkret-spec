from __future__ import annotations

import sys
import base64
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import fixtures
from tools.artifact_lint.core import ARTIFACTS, Lint


REQUIRED_FILES = (
    "fixtures/mls-keypackage-endpoint-kat-fixture.json",
    "fixtures/keypackage-lifecycle-fixture.json",
    "registry/mls-ciphersuite-registry.json",
    "schemas/keypackage-operations.schema.json",
)


class MlsKeypackageActorCiphersuiteClosureTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.artifacts = Path(self.temporary.name) / "artifacts"
        for relative in REQUIRED_FILES:
            source = ARTIFACTS / relative
            target = self.artifacts / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

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
        with patch.object(fixtures, "ARTIFACTS", self.artifacts):
            fixtures.check_mls_keypackage_actor_ciphersuite_closure(lint)
        return lint.errors

    def assert_rejected(self, errors: list[str], phrase: str) -> None:
        self.assertTrue(errors, "mutation unexpectedly passed")
        self.assertTrue(any(phrase in error for error in errors), "\n".join(errors))

    def test_shipped_closure_passes(self) -> None:
        self.assertEqual(self.run_gate(), [])

    def test_complete_actor_id_cannot_collapse_to_principal(self) -> None:
        relative = "fixtures/mls-keypackage-endpoint-kat-fixture.json"
        data = self.read(relative)
        data["cases"][0]["endpoint"]["actor_id"] = "ak:did_core:webvh:z6mkkatordinary"
        self.write(relative, data)
        self.assert_rejected(self.run_gate(), "complete ActorId object")

    def test_basic_credential_bytes_must_equal_actor_jcs(self) -> None:
        relative = "fixtures/mls-keypackage-endpoint-kat-fixture.json"
        data = self.read(relative)
        data["cases"][0]["leaf_credential"] = base64.urlsafe_b64encode(b"collapsed").rstrip(b"=").decode()
        self.write(relative, data)
        self.assert_rejected(self.run_gate(), "UTF8(RFC8785_JCS(complete ActorId))")

    def test_numeric_suite_must_match_active_registry_row(self) -> None:
        relative = "fixtures/mls-keypackage-endpoint-kat-fixture.json"
        data = self.read(relative)
        data["cases"][0]["cipher_suite"] = 3
        self.write(relative, data)
        self.assert_rejected(self.run_gate(), "sole active registry ciphersuite")

    def test_keypackage_signature_mutation_is_rejected(self) -> None:
        relative = "fixtures/mls-keypackage-endpoint-kat-fixture.json"
        data = self.read(relative)
        encoded = data["cases"][0]["keypackage"]
        raw = bytearray(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        raw[-1] ^= 1
        data["cases"][0]["keypackage"] = base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
        self.write(relative, data)
        self.assert_rejected(self.run_gate(), "KeyPackageTBS signature does not verify")

    def test_leaf_digest_cannot_be_stale(self) -> None:
        relative = "fixtures/mls-keypackage-endpoint-kat-fixture.json"
        data = self.read(relative)
        data["cases"][0]["leaf_node_sha256"] = "sha256:" + "0" * 64
        self.write(relative, data)
        self.assert_rejected(self.run_gate(), "leaf_node_sha256")

    def test_claim_and_upload_schemas_must_require_actor_id(self) -> None:
        relative = "schemas/keypackage-operations.schema.json"
        data = self.read(relative)
        data["$defs"]["keypackage_claim_record"]["required"].remove("actor_id")
        self.write(relative, data)
        self.assert_rejected(self.run_gate(), "must require the complete common ActorId")

    def test_publish_rejection_case_cannot_be_removed(self) -> None:
        relative = "fixtures/keypackage-lifecycle-fixture.json"
        data = self.read(relative)
        case = next(row for row in data["cases"] if row.get("name") == "mls_keypackage_actor_and_ciphersuite_closure")
        case["rejection_cases"] = [
            row for row in case["rejection_cases"] if row["name"] != "publish_rejects_unregistered_suite"
        ]
        self.write(relative, data)
        self.assert_rejected(self.run_gate(), "rejection matrix drifted")

    def test_try_many_cannot_fall_through_to_active_suite(self) -> None:
        relative = "fixtures/keypackage-lifecycle-fixture.json"
        data = self.read(relative)
        case = next(row for row in data["cases"] if row.get("name") == "mls_keypackage_actor_and_ciphersuite_closure")
        row = next(row for row in case["rejection_cases"] if row["name"] == "try_many_is_not_a_fallback")
        row["accepted_later_suite"] = True
        self.write(relative, data)
        self.assert_rejected(self.run_gate(), "must stop at the reserved selector")

    def test_foreign_suite_cannot_be_rewritten(self) -> None:
        relative = "fixtures/keypackage-lifecycle-fixture.json"
        data = self.read(relative)
        case = next(row for row in data["cases"] if row.get("name") == "mls_keypackage_actor_and_ciphersuite_closure")
        row = next(
            row for row in case["rejection_cases"] if row["name"] == "foreign_suite_identifier_is_not_rewritten"
        )
        row["rewrite_performed"] = True
        self.write(relative, data)
        self.assert_rejected(self.run_gate(), "must refuse local rewrite")

    def test_reserved_suite_must_really_be_reserved(self) -> None:
        relative = "registry/mls-ciphersuite-registry.json"
        data = self.read(relative)
        data["ciphersuites"][1]["status"] = "active"
        self.write(relative, data)
        self.assert_rejected(self.run_gate(), "exactly one active MLS ciphersuite")

    def test_runner_invokes_gate(self) -> None:
        source = (Path(__file__).resolve().parent / "artifact_lint" / "runner.py").read_text(encoding="utf-8")
        self.assertIn("check_mls_keypackage_actor_ciphersuite_closure(lint)", source)


if __name__ == "__main__":
    unittest.main()
