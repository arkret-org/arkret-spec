"""Mutation tests for the PCD Class B RFC 9457 machine-artifact closure."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import psi_class_b as lint_module


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


class PsiClassBArtifactClosureLintTest(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = _load(lint_module.SCHEMA_PATH)
        self.fixture = _load(lint_module.FIXTURE_PATH)
        self.schema_validation_fixture = _load(lint_module.SCHEMA_VALIDATION_FIXTURE_PATH)
        self.mapping = _load(lint_module.MAPPING_PATH)
        self.registry = _load(lint_module.ERROR_REGISTRY_PATH)
        self.real_load_json = lint_module.load_json

    def tearDown(self) -> None:
        lint_module.load_json = self.real_load_json

    def _run(
        self,
        *,
        schema: object | None = None,
        fixture: object | None = None,
        schema_validation_fixture: object | None = None,
        mapping: object | None = None,
        registry: object | None = None,
    ) -> list[str]:
        values = {
            lint_module.SCHEMA_PATH: self.schema if schema is None else schema,
            lint_module.FIXTURE_PATH: self.fixture if fixture is None else fixture,
            lint_module.SCHEMA_VALIDATION_FIXTURE_PATH: (
                self.schema_validation_fixture
                if schema_validation_fixture is None
                else schema_validation_fixture
            ),
            lint_module.MAPPING_PATH: self.mapping if mapping is None else mapping,
            lint_module.ERROR_REGISTRY_PATH: self.registry if registry is None else registry,
        }

        def fake_load_json(lint: object, path: Path) -> object:
            if path in values:
                return values[path]
            return self.real_load_json(lint, path)

        lint_module.load_json = fake_load_json
        lint = lint_module.Lint()
        lint_module.check_psi_class_b_artifact_closure(lint)
        return list(lint.errors)

    @staticmethod
    def _operation(mapping: dict) -> dict:
        return next(
            row
            for row in mapping["operations"]
            if row["operation_id"] == lint_module.OPERATION_ID
        )

    @staticmethod
    def _expected(fixture: dict) -> dict:
        vector = next(
            row
            for row in fixture["cases"]
            if row.get("vector_id") == "ak.vector.psi.quota_blinded_denial.v1"
        )
        return vector["expected"]

    def test_committed_artifacts_pass(self) -> None:
        self.assertEqual(self._run(), [])

    def test_mapping_cannot_drop_match_batch_unavailable(self) -> None:
        mapping = copy.deepcopy(self.mapping)
        self._operation(mapping)["class_b_problem_projections"].pop()
        errors = self._run(mapping=mapping)
        self.assertTrue(any("projection set or order" in error for error in errors), errors)

    def test_fixture_cannot_move_quota_denial_to_match(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        self._expected(fixture)["class_b_problem_projections"][0]["phase"] = "match"
        errors = self._run(fixture=fixture)
        self.assertTrue(any("projection set or order" in error for error in errors), errors)

    def test_schema_cannot_reopen_extension_members(self) -> None:
        schema = copy.deepcopy(self.schema)
        schema["$defs"]["psi_padded_problem"]["additionalProperties"] = True
        errors = self._run(schema=schema)
        self.assertTrue(any("must remain closed" in error for error in errors), errors)
        self.assertTrue(any("additional_extension" in error for error in errors), errors)

    def test_schema_cannot_weaken_type_status_pairing(self) -> None:
        schema = copy.deepcopy(self.schema)
        variants = schema["$defs"]["psi_padded_problem"]["oneOf"]
        variants[0]["properties"]["status"]["const"] = 403
        errors = self._run(schema=schema)
        self.assertTrue(any("schema-invalid" in error for error in errors), errors)

    def test_fixture_cannot_claim_a_larger_nonminimal_bucket(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        self._expected(fixture)["class_b_problem_projections"][0][
            "minimal_bucket_bytes"
        ] = 16384
        errors = self._run(fixture=fixture)
        self.assertTrue(any("minimal bucket drifted" in error for error in errors), errors)

    def test_registry_title_is_machine_bound(self) -> None:
        registry = copy.deepcopy(self.registry)
        row = next(row for row in registry["codes"] if row["code"] == "policy_denied")
        row["title"] = "Denied"
        errors = self._run(registry=registry)
        self.assertTrue(any("canonical PSI problem triple" in error for error in errors), errors)

    def test_common_schema_fixture_cannot_drop_old_envelope_negative(self) -> None:
        fixture = copy.deepcopy(self.schema_validation_fixture)
        fixture["schema_validation_cases"] = [
            row
            for row in fixture["schema_validation_cases"]
            if row.get("name") != "psi_padded_problem_old_envelope_rejected"
        ]
        errors = self._run(schema_validation_fixture=fixture)
        self.assertTrue(any("missing canonical PSI case" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
