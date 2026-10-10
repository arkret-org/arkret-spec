"""The error mapping's HTTP aliases must follow the canonical operation registry."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.artifact_lint import safety
from tools.artifact_lint.core import ARTIFACTS, Lint


class OperationErrorMappingAliasTest(unittest.TestCase):
    def run_gate(self, mutate=None) -> list[str]:
        paths = {
            (ARTIFACTS / "registry" / name).resolve(): json.loads(
                (ARTIFACTS / "registry" / name).read_text(encoding="utf-8")
            )
            for name in (
                "error-code-registry.json",
                "operations-error-mapping.json",
                "operation-registry.json",
            )
        }
        documents = copy.deepcopy(paths)
        if mutate is not None:
            mutate(documents[ARTIFACTS.joinpath("registry/operations-error-mapping.json").resolve()])
        original_load = safety.load_json

        def load_json(lint: Lint, path: Path):
            return documents.get(path.resolve()) or original_load(lint, path)

        with patch.object(safety, "load_json", side_effect=load_json):
            lint = Lint()
            safety.check_operations_error_mapping_closure(lint)
        return [str(error) for error in lint.errors]

    def test_current_aliases_match_operation_registry(self) -> None:
        self.assertEqual(self.run_gate(), [])

    def test_account_cursor_recovery_errors_cannot_be_omitted(self) -> None:
        for code in ("cursor_expired", "cursor_integrity_invalid", "cursor_revoked"):
            with self.subTest(code=code):
                def mutate(mapping: dict) -> None:
                    row = next(
                        row for row in mapping["operations"]
                        if row["operation_id"] == "ak.self.account.stream.subscribe.v1"
                    )
                    row["operation_specific"].remove(code)

                errors = self.run_gate(mutate)
                self.assertTrue(any("cursor recovery errors missing" in error for error in errors), errors)

    def test_retired_alias_is_rejected(self) -> None:
        def mutate(mapping: dict) -> None:
            row = next(
                row for row in mapping["operations"]
                if row["operation_id"] == "ak.self.committed_event.resource.get.v1"
            )
            row["http_alias"] = "GET /_arkret/self/events/{event_id}"

        errors = self.run_gate(mutate)
        self.assertTrue(any("http_alias differs" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
