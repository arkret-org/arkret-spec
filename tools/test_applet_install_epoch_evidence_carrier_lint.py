"""Mutation tests for the Applet install epoch-evidence carrier boundary."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import safety

ARTIFACTS = ROOT / "spec" / "v1" / "artifacts"
PACKAGE_PATH = (ARTIFACTS / "schemas" / "applet-package.schema.json").resolve()
INSTALL_PATH = (
    ARTIFACTS / "schemas" / "applet-install-operations.schema.json"
).resolve()
AUTHORING_PATH = (
    ARTIFACTS / "schemas" / "applet-install-authoring.schema.json"
).resolve()


class AppletInstallEpochEvidenceCarrierLintTest(unittest.TestCase):
    def _run(self, mutations=None) -> list[str]:
        mutations = mutations or {}
        original_load_json = safety.load_json
        documents = {}
        for path, mutate in mutations.items():
            document = copy.deepcopy(original_load_json(safety.Lint(), path))
            mutate(document)
            documents[path.resolve()] = document

        def load_json_with_mutation(lint, path):
            return documents.get(path.resolve(), original_load_json(lint, path))

        safety.load_json = load_json_with_mutation
        try:
            lint = safety.Lint()
            safety.check_applet_install_epoch_evidence_carrier(lint)
            return lint.errors
        finally:
            safety.load_json = original_load_json

    def test_committed_carrier_boundary_passes(self) -> None:
        self.assertEqual(self._run(), [])

    def test_package_evidence_member_fails(self) -> None:
        def mutate(schema):
            schema["properties"]["registration_epoch_evidence"] = {"type": "object"}

        errors = self._run({PACKAGE_PATH: mutate})
        self.assertTrue(any("must not enter" in error for error in errors), errors)

    def test_preview_evidence_mirror_fails(self) -> None:
        def mutate(schema):
            schema["$defs"]["applet_install_preview_request_body"]["properties"][
                "registration_epoch_evidence"
            ] = {"type": "object"}

        errors = self._run({INSTALL_PATH: mutate})
        self.assertTrue(any("must not mirror" in error for error in errors), errors)

    def test_basis_evidence_mirror_fails(self) -> None:
        def mutate(schema):
            schema["$defs"]["install_authoring_request_basis"]["properties"][
                "registration_epoch_evidence"
            ] = {"type": "object"}

        errors = self._run({AUTHORING_PATH: mutate})
        self.assertTrue(any("must not mirror" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
