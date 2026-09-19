"""Seven one-point mutations for the F2 machine-artifact prose boundary.

The prose scanner is only the discovery edge.  Writer existence, selector
agreement, value members and maintenance ownership remain structural checks;
these mutations pin the hand-off between those layers without pretending that
a regular expression proves arbitrary English.
"""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import proof_context_schemas as gate
from tools.artifact_lint.core import parse_json_file, read_text as cached_read_text


def row_of(document: dict, kind: str) -> dict:
    return next(row for row in document["event_kinds"] if row["event_kind"] == kind)


class AssertedResultFamilySurfaceMutationTest(unittest.TestCase):
    def _assertion_errors(self, documents: dict[Path, str], families=()) -> list[str]:
        original_read = Path.read_text
        original_sources = gate._asserted_result_family_sources
        original_families = gate._registered_result_families
        original_is_file = Path.is_file
        ledger = json.dumps({"unregistered_families": []})

        def read_text(path, *args, **kwargs):  # type: ignore[no-untyped-def]
            if path in documents:
                return documents[path]
            if path == gate.ASSERTED_FAMILY_EXEMPTIONS:
                return ledger
            return original_read(path, *args, **kwargs)

        def is_file(path):  # type: ignore[no-untyped-def]
            if path in documents or path == gate.ASSERTED_FAMILY_EXEMPTIONS:
                return True
            return original_is_file(path)

        parse_json_file.cache_clear()
        cached_read_text.cache_clear()
        Path.read_text = read_text  # type: ignore[method-assign]
        Path.is_file = is_file  # type: ignore[method-assign]
        gate._asserted_result_family_sources = lambda: sorted(documents)  # type: ignore[assignment]
        gate._registered_result_families = lambda _lint: set(families)  # type: ignore[assignment]
        try:
            lint = gate.Lint()
            gate.check_asserted_result_families_are_registered(lint)
            return lint.errors
        finally:
            Path.read_text = original_read  # type: ignore[method-assign]
            Path.is_file = original_is_file  # type: ignore[method-assign]
            gate._asserted_result_family_sources = original_sources  # type: ignore[assignment]
            gate._registered_result_families = original_families  # type: ignore[assignment]
            parse_json_file.cache_clear()
            cached_read_text.cache_clear()

    def _structural_errors(self, check, mutate_path: Path, mutate) -> list[str]:
        original = gate.load_json
        document = copy.deepcopy(original(gate.Lint(), mutate_path))
        mutate(document)

        def load_json(lint, path):  # type: ignore[no-untyped-def]
            if Path(path).resolve() == mutate_path.resolve():
                return document
            return original(lint, path)

        gate.load_json = load_json
        try:
            lint = gate.Lint()
            check(lint)
            return lint.errors
        finally:
            gate.load_json = original

    def test_other_artifact_single_word_family_is_reported(self) -> None:
        path = gate.ARTIFACTS / "registry" / "error-code-registry.json"
        errors = self._assertion_errors(
            {path: '{"description":"The stable phantom typed current result family."}'}
        )
        self.assertTrue(any("'phantom'" in error for error in errors), errors)

    def test_wrong_coalesce_subject_is_reported(self) -> None:
        def mutate(document: dict) -> None:
            write = row_of(document, "ak.capability.revoke")["result_writes"][0]
            write["result_selector"] = {
                "kind": "coalesce",
                "fields": ["payload.a", "payload.b"],
            }
            write["condition"] = {
                "kind": "any_field_present",
                "fields": ["payload.b", "payload.a"],
            }

        errors = self._structural_errors(
            gate.check_result_write_target_uniqueness, gate.EVENT_KIND_REGISTRY, mutate
        )
        self.assertTrue(any("item-for-item and in order" in error for error in errors), errors)

    def test_nonexistent_writer_citation_is_reported(self) -> None:
        path = gate.ARTIFACTS / "registry" / "error-code-registry.json"
        original_read = Path.read_text
        original_sources = gate._asserted_result_family_sources

        def read_text(target, *args, **kwargs):  # type: ignore[no-untyped-def]
            if target == path:
                return '{"description":"See ak.no_such_kind.result_writes[]."}'
            return original_read(target, *args, **kwargs)

        Path.read_text = read_text  # type: ignore[method-assign]
        gate._asserted_result_family_sources = lambda: [path]  # type: ignore[assignment]
        try:
            lint = gate.Lint()
            registry = gate.load_json(lint, gate.EVENT_KIND_REGISTRY)
            gate._check_prose_result_write_citations(lint, registry["event_kinds"])
            errors = lint.errors
        finally:
            Path.read_text = original_read  # type: ignore[method-assign]
            gate._asserted_result_family_sources = original_sources  # type: ignore[assignment]
        self.assertTrue(any("ak.no_such_kind.result_writes[]" in error for error in errors), errors)

    def test_wrong_projected_member_is_reported(self) -> None:
        def mutate(document: dict) -> None:
            write = row_of(document, "ak.capability.revoke")["result_writes"][0]
            write["result_projection"]["value_projection"]["members"][0]["name"] = (
                "member_not_in_value_schema"
            )

        errors = self._structural_errors(
            gate.check_result_write_contracts, gate.EVENT_KIND_REGISTRY, mutate
        )
        self.assertTrue(
            any("member_not_in_value_schema" in error and "not declared" in error for error in errors),
            errors,
        )

    def test_negated_family_sentence_is_not_an_assignment(self) -> None:
        path = gate.ARTIFACTS / "schemas" / "event-payload.schema.json"
        errors = self._assertion_errors(
            {
                path: (
                    '{"description":"A rejected Event does not produce phantom_family '
                    'typed current result state."}'
                )
            }
        )
        self.assertEqual(errors, [])

    def test_generated_source_split_is_still_scanned(self) -> None:
        source = gate.ARTIFACTS / "registry" / "contract-registry.json"
        generated = gate.EVENT_KIND_REGISTRY
        errors = self._assertion_errors(
            {
                source: "{}",
                generated: (
                    '{"description":"Writes generated_only typed current result state."}'
                ),
            }
        )
        self.assertTrue(any("generated_only" in error for error in errors), errors)

    def test_missing_maintenance_owner_is_reported(self) -> None:
        def mutate(document: dict) -> None:
            rows = [*(document.get("objects") or []), *(document.get("non_object_results") or [])]
            row = next(
                item
                for item in rows
                if isinstance(item.get("value_member_maintenance"), dict)
            )
            row["value_member_maintenance"].pop("owner")

        errors = self._structural_errors(
            gate.check_result_value_member_closure,
            gate.REDUCER_MANAGED_PATH_REGISTRY,
            mutate,
        )
        self.assertTrue(any("MUST name the normative owner" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
