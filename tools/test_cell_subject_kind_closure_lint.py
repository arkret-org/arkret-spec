"""Mutation tests for the closed cell_subject.kind table (ruling 2026-09-05-1200).

encoding.md 4.1 is a closed dispatch table: a top-level `cell_subject.kind`
outside it has no embedding rule, so the cell wire id is undefined.
`canonical_json` in particular is only a `components[]` descriptor; two
contracts used it as a top-level kind for months because nothing pinned the
table. These tests pin both the foundation kind check and the schemas-phase
rejection of a top-level canonical_json subject.
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import core, foundation, schemas

CONTRACT_REGISTRY = ROOT / "spec" / "v1" / "artifacts" / "registry" / "contract-registry.json"
EVENT_REGISTRY = ROOT / "spec" / "v1" / "artifacts" / "registry" / "event-kind-registry.json"
EVENT_SCHEMA = ROOT / "spec" / "v1" / "artifacts" / "schemas" / "event-envelope.schema.json"


def _first_write(registry: dict, kind: str) -> dict:
    row = next(row for row in registry["event_kinds"] if row["event_kind"] == kind)
    return row["cell_writes"][0]


class CellSubjectKindTableTest(unittest.TestCase):
    def test_registered_kinds(self) -> None:
        for kind in (
            "did",
            "typed_id",
            "string",
            "uri",
            "coalesce",
            "composite",
            "tuple",
            "typed_pair",
            "id:strand",
        ):
            self.assertTrue(foundation.is_registered_cell_subject_kind(kind), kind)
        for kind in ("canonical_json", "string_set_digest", "select", "id:", "id:Strand", "object"):
            self.assertFalse(foundation.is_registered_cell_subject_kind(kind), kind)

    def test_shipped_registry_uses_only_registered_kinds(self) -> None:
        registry = core.parse_json_text(EVENT_REGISTRY.read_text(encoding="utf-8"))
        offenders = []
        for row in registry["event_kinds"]:
            for write in row.get("cell_writes") or []:
                subject = write.get("cell_subject")
                if isinstance(subject, dict) and not foundation.is_registered_cell_subject_kind(
                    subject.get("kind", "")
                ):
                    offenders.append((row["event_kind"], subject.get("kind")))
        self.assertEqual(offenders, [])

    def test_reanchor_and_fork_resolution_are_single_component_composites(self) -> None:
        registry = core.parse_json_text(EVENT_REGISTRY.read_text(encoding="utf-8"))
        for kind, field in (
            ("ak.device.reanchor", "payload.account_id"),
            ("ak.fork.resolution", "payload.subject"),
        ):
            subject = _first_write(registry, kind)["cell_subject"]
            self.assertEqual(
                subject,
                {"kind": "composite", "components": [{"kind": "canonical_json", "field": field}]},
                kind,
            )


class TopLevelCanonicalJsonSubjectLintTest(unittest.TestCase):
    def _lint_mutated_registry(self, mutate) -> list[str]:
        event_schema = core.parse_json_text(EVENT_SCHEMA.read_text(encoding="utf-8"))
        registry = core.parse_json_text(EVENT_REGISTRY.read_text(encoding="utf-8"))
        mutated = copy.deepcopy(registry)
        mutate(mutated)
        original_load_json = schemas.load_json

        def load_json_with_mutation(lint, path):
            if path.resolve() == EVENT_REGISTRY.resolve():
                return mutated
            return original_load_json(lint, path)

        schemas.load_json = load_json_with_mutation
        try:
            lint = schemas.Lint()
            schemas.check_composite_subject_terminal_types(lint, EVENT_SCHEMA, event_schema)
            return [str(error) for error in lint.errors]
        finally:
            schemas.load_json = original_load_json

    def test_shipped_registry_is_clean(self) -> None:
        self.assertEqual(self._lint_mutated_registry(lambda registry: None), [])

    def test_top_level_canonical_json_is_rejected(self) -> None:
        def mutate(registry):
            _first_write(registry, "ak.device.reanchor")["cell_subject"] = {
                "kind": "canonical_json",
                "field": "payload.account_id",
            }

        errors = self._lint_mutated_registry(mutate)
        self.assertTrue(
            any("ak.device.reanchor" in error and "top-level subject kind" in error for error in errors),
            errors,
        )

    def test_single_component_composite_still_passes(self) -> None:
        def mutate(registry):
            _first_write(registry, "ak.fork.resolution")["cell_subject"] = {
                "kind": "composite",
                "components": [{"kind": "canonical_json", "field": "payload.subject"}],
            }

        self.assertEqual(self._lint_mutated_registry(mutate), [])


if __name__ == "__main__":
    unittest.main()
