from __future__ import annotations

import sys
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import safety
from tools.artifact_lint.core import ARTIFACTS, Lint


class DetachedJwsAlgorithmGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.artifacts = Path(self.temporary.name) / "artifacts"
        for relative in (
            "registry/signature-alg-registry.json",
            "schemas/applet-package.schema.json",
            "schemas/event-envelope.schema.json",
            "schemas/websocket-dpop-proof.schema.json",
        ):
            target = self.artifacts / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ARTIFACTS / relative, target)
        fixture_path = self.artifacts / "fixtures/example.json"
        fixture_path.parent.mkdir(parents=True, exist_ok=True)
        fixture_path.write_text(
            json.dumps({"proof": {"jws": "eyJhbGciOiJFZDI1NTE5In0.." + "A" * 86}}, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_gate(self) -> list[str]:
        lint = Lint()
        with patch.object(safety, "ARTIFACTS", self.artifacts):
            safety.check_alg_registry(lint)
        return lint.errors

    def mutate_fixture_jws(self, value: str) -> None:
        path = self.artifacts / "fixtures/example.json"
        path.write_text(
            json.dumps({"proof": {"jws": value}}, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    def test_active_detached_jws_passes(self) -> None:
        self.assertEqual(self.run_gate(), [])

    def test_polymorphic_eddsa_alias_is_rejected(self) -> None:
        self.mutate_fixture_jws("eyJhbGciOiJFZERTQSJ9.." + "A" * 86)
        errors = self.run_gate()
        self.assertTrue(any("protected alg is not an active" in error for error in errors), "\n".join(errors))

    def test_raw_signature_in_jws_member_is_rejected(self) -> None:
        self.mutate_fixture_jws("A" * 86)
        errors = self.run_gate()
        self.assertTrue(any("must be compact detached JWS" in error for error in errors), "\n".join(errors))

    def test_attached_payload_schema_pattern_is_rejected(self) -> None:
        path = self.artifacts / "schemas/event-envelope.schema.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["$defs"]["proof"]["properties"]["jws"]["pattern"] = (
            "^[A-Za-z0-9_-]+\\.(?:[A-Za-z0-9_-]+)?\\.[A-Za-z0-9_-]+$"
        )
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        errors = self.run_gate()
        self.assertTrue(any("empty payload segment" in error for error in errors), "\n".join(errors))


if __name__ == "__main__":
    unittest.main()
