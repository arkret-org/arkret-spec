"""Mutation tests for recovery SessionGrant authentication semantics."""

from __future__ import annotations

import copy
import inspect
import sys
import unittest
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import bindings
from tools.artifact_lint import runner

OPENAPI = ROOT / "spec" / "v1" / "artifacts" / "openapi" / "arkret-service-api.openapi.yaml"
OPERATIONS = (
    "ak.root.identity.recovery_policy.command.publish",
    "ak.root.identity.recovery_policy.resource.get",
    "ak.root.identity.recovery_session.command.create",
    "ak.root.identity.recovery_session.resource.get",
    "ak.root.identity.recovery_session.command.submit_proof",
)


class OpenApiSessionGrantAuthLintTest(unittest.TestCase):
    def setUp(self) -> None:
        self.real_load_yaml = bindings.load_yaml
        lint = bindings.Lint()
        document = self.real_load_yaml(lint, OPENAPI)
        self.assertEqual(lint.errors, [])
        self.assertIsInstance(document, dict)
        self.document = document

    def tearDown(self) -> None:
        bindings.load_yaml = self.real_load_yaml

    def _run(self, mutate: Callable[[dict], None] | None = None) -> list[str]:
        document = copy.deepcopy(self.document)
        if mutate is not None:
            mutate(document)

        def load_yaml(lint: bindings.Lint, path: Path):
            if path == OPENAPI:
                return document
            return self.real_load_yaml(lint, path)

        bindings.load_yaml = load_yaml
        lint = bindings.Lint()
        bindings.check_openapi_auth_semantics(lint)
        return list(lint.errors)

    @staticmethod
    def _operation(document: dict, operation_id: str) -> dict:
        for path_item in document["paths"].values():
            if not isinstance(path_item, dict):
                continue
            for operation in path_item.values():
                if isinstance(operation, dict) and operation.get("operationId") == operation_id:
                    return operation
        raise AssertionError(f"operation missing: {operation_id}")

    def test_committed_contract_passes(self) -> None:
        self.assertEqual(self._run(), [])

    def test_gate_runs_from_artifact_lint_entry_point(self) -> None:
        self.assertIs(runner.check_openapi_auth_semantics, bindings.check_openapi_auth_semantics)
        self.assertIn("check_openapi_auth_semantics(lint)", inspect.getsource(runner.main))

    def test_bearer_regression_is_rejected(self) -> None:
        def mutate(document: dict) -> None:
            operation = self._operation(document, OPERATIONS[2])
            operation["security"][0] = {"bearerAuth": []}

        failures = self._run(mutate)
        self.assertTrue(any("must require sessionGrantAuth" in failure for failure in failures), failures)
        self.assertTrue(any("must not use bearerAuth" in failure for failure in failures), failures)

    def test_session_grant_without_dpop_is_rejected(self) -> None:
        def mutate(document: dict) -> None:
            operation = self._operation(document, OPERATIONS[3])
            operation["security"][0] = {"sessionGrantAuth": []}

        failures = self._run(mutate)
        self.assertTrue(any("same security alternative" in failure for failure in failures), failures)

    def test_recovery_coordinator_service_alternative_is_rejected(self) -> None:
        def mutate(document: dict) -> None:
            operation = self._operation(document, OPERATIONS[4])
            operation["security"].append(
                {
                    "httpMessageSignature": [],
                    "sourceServiceId": [],
                    "destinationServiceId": [],
                }
            )

        failures = self._run(mutate)
        self.assertTrue(any("must not expose a recovery coordinator" in failure for failure in failures), failures)


if __name__ == "__main__":
    unittest.main()
