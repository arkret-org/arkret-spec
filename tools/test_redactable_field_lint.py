"""Mutation tests for the redactable content-carrier slot gate.

Before the registry existed, the protected path set lived only in
zh/models/event-and-patch.md section 4.2.4, and the Strand row silently omitted
the plaintext `content` slot for months. Each case below reproduces the shape a
regression would actually take -- a dropped row, a one-sided pair, a metadata
path smuggled into the ban, a row with no non-terminal clear path -- and asserts
the gate rejects it.
"""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import redactable_fields as lint_module

REGISTRY = lint_module.REGISTRY_PATH


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


class RedactableFieldLintTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = _load(REGISTRY)
        self.real_load_json = lint_module.load_json

    def tearDown(self) -> None:
        lint_module.load_json = self.real_load_json

    def _run(self, registry: object) -> list[str]:
        def fake_load_json(lint: object, path: Path) -> object:
            if path == REGISTRY:
                return registry
            return self.real_load_json(lint, path)

        lint_module.load_json = fake_load_json
        lint = lint_module.Lint()
        lint_module.check_redactable_field_registry(lint)
        return list(lint.errors)

    def _mutate(self) -> dict:
        return copy.deepcopy(self.registry)

    def _row(self, registry: dict, object_kind: str, path: str) -> dict:
        for row in registry["redactable_fields"]:
            if row["object_kind"] == object_kind and row["path"] == path:
                return row
        raise AssertionError(f"missing row ({object_kind}, {path})")

    def test_committed_registry_passes(self) -> None:
        self.assertEqual(self._run(self.registry), [])

    def test_strand_plaintext_slot_is_registered(self) -> None:
        # The exact 2248 regression: Strand listed only encrypted_content.
        self.assertIsNotNone(self._row(self.registry, "strand", "content"))

    def test_dropping_a_prose_listed_slot_is_rejected(self) -> None:
        registry = self._mutate()
        registry["redactable_fields"] = [
            row
            for row in registry["redactable_fields"]
            if not (row["object_kind"] == "strand" and row["path"] == "content")
        ]
        errors = self._run(registry)
        self.assertTrue(any("section 4.2.4 lists strand.content" in error for error in errors), errors)

    def test_registering_a_slot_absent_from_prose_is_rejected(self) -> None:
        registry = self._mutate()
        extra = copy.deepcopy(self._row(registry, "strand", "content"))
        extra["path"] = "tracks"
        extra["paired_path"] = "tracks"
        registry["redactable_fields"].append(extra)
        errors = self._run(registry)
        self.assertTrue(any("section 4.2.4 does not list it" in error for error in errors), errors)

    def test_unpaired_slot_is_rejected(self) -> None:
        registry = self._mutate()
        self._row(registry, "strand", "content")["paired_path"] = "encrypted_metadata"
        errors = self._run(registry)
        self.assertTrue(any("is not registered for the same object kind" in error for error in errors), errors)

    def test_asymmetric_pairing_is_rejected(self) -> None:
        registry = self._mutate()
        self._row(registry, "strand", "encrypted_content")["paired_path"] = "content"
        self._row(registry, "strand", "content")["paired_path"] = "encrypted_content"
        registry["redactable_fields"].append(
            {
                "object_kind": "morph",
                "schema_ref": "schemas/morph.schema.json",
                "path": "metadata",
                "paired_path": "encrypted_metadata",
                "non_terminal_clear_op": "set",
                "non_terminal_clear_contract": "irrelevant",
                "terminal_clear_event_kinds": ["ak.redaction"],
                "description": "irrelevant",
            }
        )
        errors = self._run(registry)
        self.assertTrue(any("not a content-carrier slot" in error for error in errors), errors)

    def test_metadata_path_cannot_be_registered(self) -> None:
        registry = self._mutate()
        self._row(registry, "strand", "content")["path"] = "metadata.summary"
        errors = self._run(registry)
        self.assertTrue(any("write-once" in error for error in errors), errors)

    def test_unset_as_clear_path_is_rejected(self) -> None:
        registry = self._mutate()
        self._row(registry, "morph", "content")["non_terminal_clear_op"] = "unset"
        errors = self._run(registry)
        self.assertTrue(
            any("MUST keep a non-terminal clear path" in error for error in errors), errors
        )

    def test_unknown_terminal_clear_event_kind_is_rejected(self) -> None:
        registry = self._mutate()
        self._row(registry, "strand", "content")["terminal_clear_event_kinds"] = ["ak.strand.redact"]
        errors = self._run(registry)
        self.assertTrue(
            any("unknown or inactive event kind" in error for error in errors), errors
        )

    def test_path_absent_from_the_declared_schema_is_rejected(self) -> None:
        registry = self._mutate()
        self._row(registry, "message", "content")["schema_ref"] = "schemas/strand.schema.json"
        self._row(registry, "message", "content")["path"] = "strand_id"
        errors = self._run(registry)
        self.assertTrue(any("is not a declared property" in error for error in errors), errors)

    def test_duplicate_row_is_rejected(self) -> None:
        registry = self._mutate()
        registry["redactable_fields"].append(copy.deepcopy(self._row(registry, "morph", "content")))
        errors = self._run(registry)
        self.assertTrue(any("duplicates (morph, content)" in error for error in errors), errors)


class RedactableFieldErrorCodeBindingTest(unittest.TestCase):
    """The reason code description must delegate to the registry, not restate it."""

    def setUp(self) -> None:
        self.real_load_json = lint_module.load_json
        self.error_codes = _load(lint_module.ERROR_CODE_PATH)

    def tearDown(self) -> None:
        lint_module.load_json = self.real_load_json

    def _run(self, error_codes: object) -> list[str]:
        def fake_load_json(lint: object, path: Path) -> object:
            if path == lint_module.ERROR_CODE_PATH:
                return error_codes
            return self.real_load_json(lint, path)

        lint_module.load_json = fake_load_json
        lint = lint_module.Lint()
        lint_module.check_redactable_field_registry(lint)
        return list(lint.errors)

    def test_description_without_registry_pointer_is_rejected(self) -> None:
        codes = copy.deepcopy(self.error_codes)
        for row in codes["reason_codes"]:
            if row.get("code") == lint_module.REASON_CODE:
                row["description"] = "An unset was used on a redactable content field."
        errors = self._run(codes)
        self.assertTrue(
            any("redactable-field-registry.json" in error for error in errors), errors
        )

    def test_description_naming_a_metadata_path_is_rejected(self) -> None:
        codes = copy.deepcopy(self.error_codes)
        for row in codes["reason_codes"]:
            if row.get("code") == lint_module.REASON_CODE:
                row["description"] = (
                    "See registry/redactable-field-registry.json; e.g. strand.metadata.summary."
                )
        errors = self._run(codes)
        self.assertTrue(
            any("still names metadata.summary" in error for error in errors), errors
        )


if __name__ == "__main__":
    unittest.main()
