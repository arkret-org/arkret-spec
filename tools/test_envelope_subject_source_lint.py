"""Mutation tests for the §9.5.1 envelope-subject-source reconciliation.

The state this gate exists to make unreachable really happened: `encoding.md`
§9.5.1 forbade `envelope.event_id` as a cell subject while six registered create
kinds were already reading it, and the release gate was green on both sides. The
per-occurrence lint could not catch it, because it checked each registry row
against its own copy of the list rather than against the prose.
"""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
MODULE_SPEC = importlib.util.spec_from_file_location(
    "lint_artifacts", ROOT / "tools" / "lint_artifacts.py"
)
assert MODULE_SPEC is not None and MODULE_SPEC.loader is not None
lint_artifacts = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(lint_artifacts)

REGISTRY = ROOT / "spec" / "v1" / "artifacts" / "registry"


class EnvelopeSubjectSourceLintTest(unittest.TestCase):
    def _lint(self, *, prose=None, registry_mutation=None) -> list[str]:
        """Run the reconciliation with the prose and/or a registry replaced."""
        original_read_text = lint_artifacts.read_text
        original_load_json = lint_artifacts.load_json
        target = (REGISTRY / "contract-registry.json").resolve()
        mutated = None
        if registry_mutation is not None:
            mutated = copy.deepcopy(original_load_json(lint_artifacts.Lint(), target))
            registry_mutation(mutated)

        def read_text_with_mutation(path):
            text = original_read_text(path)
            return prose(text) if prose is not None and path.name == "encoding.md" else text

        def load_json_with_mutation(lint, path):
            if mutated is not None and path.resolve() == target:
                return mutated
            return original_load_json(lint, path)

        lint_artifacts.read_text = read_text_with_mutation
        lint_artifacts.load_json = load_json_with_mutation
        try:
            lint = lint_artifacts.Lint()
            lint_artifacts.check_envelope_subject_source_whitelist(lint)
            return lint.errors
        finally:
            lint_artifacts.read_text = original_read_text
            lint_artifacts.load_json = original_load_json

    def test_current_spec_and_registry_agree(self) -> None:
        self.assertEqual(self._lint(), [])

    def test_prose_dropping_a_whitelisted_source_fails(self) -> None:
        # The original divergence: prose says event_id is not a legal source,
        # registry reads it anyway.
        def prose(text: str) -> str:
            return text.replace(
                "只包含 `envelope.actor_id` 与 `envelope.event_id` 两项",
                "只包含 `envelope.actor_id` 一项",
            )

        errors = self._lint(prose=prose)
        self.assertTrue(
            any("whitelist sentence names" in error for error in errors),
            errors,
        )

    def test_deleting_the_whitelist_sentence_fails(self) -> None:
        def prose(text: str) -> str:
            return "\n".join(
                line for line in text.splitlines() if "envelope 来源白名单" not in line
            )

        errors = self._lint(prose=prose)
        self.assertTrue(
            any("must keep a sentence naming the closed" in error for error in errors),
            errors,
        )

    def test_registry_reading_a_forbidden_envelope_field_fails(self) -> None:
        def mutate(registry) -> None:
            contracts = registry["event_kind_registry"]["cell_contracts"]
            write = contracts["ak.profile.create"]["cell_writes"][0]
            write["cell_subject"]["field"] = "envelope.realm_id"

        errors = self._lint(registry_mutation=mutate)
        self.assertTrue(
            any("forbids envelope.realm_id" in error for error in errors),
            errors,
        )

    def test_a_whitelisted_source_nothing_reads_fails(self) -> None:
        original = lint_artifacts.ENVELOPE_SUBJECT_SOURCES
        lint_artifacts.ENVELOPE_SUBJECT_SOURCES = original + ("envelope.applet_id",)
        try:
            errors = self._lint()
        finally:
            lint_artifacts.ENVELOPE_SUBJECT_SOURCES = original
        self.assertTrue(
            any("no registered cell subject reads it" in error for error in errors),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
