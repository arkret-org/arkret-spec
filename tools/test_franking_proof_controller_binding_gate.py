"""Regression tests for the franking-proof service-controller binding."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import franking_transcript as gate
from tools.artifact_lint.core import Lint

ARTIFACTS = ROOT / "spec/v1/artifacts"


class FrankingProofControllerBindingGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = json.loads(
            (ARTIFACTS / "registry/proof-context-registry.json").read_text(encoding="utf-8")
        )
        self.vectors = json.loads(
            (ARTIFACTS / "registry/vector-registry.json").read_text(encoding="utf-8")
        )
        self.fixture = json.loads(
            (ARTIFACTS / "fixtures/franking-proof-transcript-fixture.json").read_text(encoding="utf-8")
        )

    def errors_after(self, mutate) -> list[str]:
        fixture = copy.deepcopy(self.fixture)
        mutate(fixture)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = root / "proof-context-registry.json"
            vectors = root / "vector-registry.json"
            fixture_path = root / "franking-proof-transcript-fixture.json"
            registry.write_text(json.dumps(self.registry), encoding="utf-8")
            vectors.write_text(json.dumps(self.vectors), encoding="utf-8")
            fixture_path.write_text(json.dumps(fixture), encoding="utf-8")
            lint = Lint()
            with (
                mock.patch.object(gate, "REGISTRY", registry),
                mock.patch.object(gate, "VECTOR_REGISTRY", vectors),
                mock.patch.object(gate, "FIXTURE", fixture_path),
            ):
                gate.check_franking_proof_transcript(lint)
            return lint.errors

    def test_shipped_controller_projects_to_received_by(self) -> None:
        self.assertEqual(self.errors_after(lambda _: None), [])

    def test_old_mismatched_accept_controller_is_rejected(self) -> None:
        def mutate(fixture: dict) -> None:
            method = "did:webvh:z6mkfixture:principal.example#ed25519-2026-05-fixture"
            fixture["case"]["source_payload"]["verification_method"] = method
            fixture["case"]["transcript"]["verification_method"] = method

        errors = self.errors_after(mutate)
        self.assertTrue(any("project exactly to received_by" in error for error in errors), errors)

    def test_method_mutation_cannot_escape_to_another_controller(self) -> None:
        def mutate(fixture: dict) -> None:
            mutation = next(
                row
                for row in fixture["case"]["bound_field_mutations"]
                if row["field"] == "verification_method"
            )
            mutation["transcript"]["verification_method"] = "did:webvh:z6mkother:other.example#rotated-key"

        errors = self.errors_after(mutate)
        self.assertTrue(any("must retain the received_by controller" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
