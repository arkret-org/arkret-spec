"""Mutation tests for the closed `cell_subject.kind` set.

zh/conformance/encoding.md section 4.1 calls its subject-embedding table the
complete list of legal ``cell_writes[].cell_subject`` shapes and forbids two
rows applying to one field. ``canonical_json`` and ``string_set_digest`` have no
row of their own -- they are ``components[]`` descriptors -- so a structured
single-field subject MUST be spelled as a one-component composite. Nothing
mechanised that until `ak.device.reanchor` and `ak.fork.resolution` were found
carrying the top-level spelling, so this file pins the closure by mutation: the
registered contracts must be clean, and each shape outside the table must fail
closed.
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import core, foundation

CONTRACT_PATH = ROOT / "spec" / "v1" / "artifacts" / "registry" / "contract-registry.json"
SUBJECT_KIND = "ak.fork.resolution"


class CellSubjectKindClosureTest(unittest.TestCase):
    def _lint_mutated_contract(self, mutate) -> list[str]:
        root = core.parse_json_text(CONTRACT_PATH.read_text(encoding="utf-8"))
        mutated = copy.deepcopy(root)
        if mutate is not None:
            writes = mutated["event_kind_registry"]["cell_contracts"][SUBJECT_KIND]["cell_writes"]
            mutate(writes)

        original_load_json = foundation.load_json

        def load_json_with_mutation(lint, path):
            if Path(path).resolve() == CONTRACT_PATH.resolve():
                return mutated
            return original_load_json(lint, path)

        foundation.load_json = load_json_with_mutation
        try:
            lint = foundation.Lint()
            foundation.check_state_contract_closure(lint)
            return lint.errors
        finally:
            foundation.load_json = original_load_json

    def _subject_errors(self, mutate) -> list[str]:
        return [
            error for error in self._lint_mutated_contract(mutate) if "cell_subject" in error
        ]

    def test_registered_contracts_are_clean(self) -> None:
        self.assertEqual(self._subject_errors(None), [])

    def test_registered_subject_is_the_composite_spelling(self) -> None:
        root = core.parse_json_text(CONTRACT_PATH.read_text(encoding="utf-8"))
        contracts = root["event_kind_registry"]["cell_contracts"]
        top_level = [
            (kind, index)
            for kind, contract in contracts.items()
            for index, write in enumerate(contract.get("cell_writes", []))
            if isinstance(write, dict)
            and isinstance(write.get("cell_subject"), dict)
            and write["cell_subject"].get("kind") in core.CELL_SUBJECT_COMPONENT_ONLY_KINDS
        ]
        self.assertEqual(top_level, [])

    def test_top_level_canonical_json_fails_closed(self) -> None:
        def mutate(writes):
            writes[0]["cell_subject"] = {"kind": "canonical_json", "field": "payload.subject"}

        errors = self._subject_errors(mutate)
        self.assertTrue(errors, "a top-level canonical_json subject must fail closed")
        self.assertTrue(
            any("components[] descriptor" in error for error in errors),
            errors,
        )

    def test_top_level_string_set_digest_fails_closed(self) -> None:
        def mutate(writes):
            writes[0]["cell_subject"] = {
                "kind": "string_set_digest",
                "field": "payload.subject",
            }

        self.assertTrue(self._subject_errors(mutate))

    def test_unregistered_subject_kind_fails_closed(self) -> None:
        def mutate(writes):
            writes[0]["cell_subject"] = {"kind": "digest", "field": "payload.subject"}

        self.assertTrue(self._subject_errors(mutate))

    def test_typed_object_id_subject_kind_is_accepted(self) -> None:
        def mutate(writes):
            writes[0]["cell_subject"] = {"kind": "id:event", "field": "payload.subject"}

        self.assertEqual(
            [error for error in self._subject_errors(mutate) if "must be one of" in error],
            [],
        )


if __name__ == "__main__":
    unittest.main()
