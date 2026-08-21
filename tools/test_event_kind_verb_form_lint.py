"""Mutation tests for the event-kind terminal-segment (verb_form) registration.

The prose claimed a machine-readable registration that did not exist, and the
readable exception table itself had drifted. Classification is mandatory for
every active kind precisely so that lint can tell a lawful omission from a new
past participle nobody registered; an English suffix scan cannot, because
``bound`` and ``withheld`` are irregular.
"""

from __future__ import annotations

import copy
import inspect
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import foundation as lint_artifacts
from tools.artifact_lint import runner

ARTIFACTS = ROOT / "spec" / "v1" / "artifacts"
CONTRACT_REGISTRY = ARTIFACTS / "registry" / "contract-registry.json"
EVENT_KIND_REGISTRY = ARTIFACTS / "registry" / "event-kind-registry.json"
COMMON_FIELDS = ROOT / "spec" / "v1" / "zh" / "models" / "common-fields.md"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class EventKindVerbFormLintTest(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _load(CONTRACT_REGISTRY)
        self.generated = _load(EVENT_KIND_REGISTRY)
        self.real_load_json = lint_artifacts.load_json

    def tearDown(self) -> None:
        lint_artifacts.load_json = self.real_load_json

    def _run(self, contract: dict, generated: dict) -> list[str]:
        def fake_load_json(lint: object, path: Path) -> object:
            if path == CONTRACT_REGISTRY:
                return contract
            if path == EVENT_KIND_REGISTRY:
                return generated
            return self.real_load_json(lint, path)

        lint_artifacts.load_json = fake_load_json
        lint = lint_artifacts.Lint()
        lint_artifacts.check_event_kind_verb_form_registration(lint)
        return list(lint.errors)

    def _rows(self, contract: dict) -> list[dict]:
        return contract["event_kind_registry"]["event_kinds"]

    def _row(self, contract: dict, event_kind: str) -> dict:
        for row in self._rows(contract):
            if row["event_kind"] == event_kind:
                return row
        raise AssertionError(event_kind)

    # --- committed tree -------------------------------------------------

    def test_committed_registration_passes(self) -> None:
        self.assertEqual(self._run(self.contract, self.generated), [])

    def test_gate_runs_from_the_artifact_lint_entry_point(self) -> None:
        self.assertIs(
            runner.check_event_kind_verb_form_registration,
            lint_artifacts.check_event_kind_verb_form_registration,
        )
        self.assertIn(
            "check_event_kind_verb_form_registration(lint)",
            inspect.getsource(runner.main),
        )

    def test_every_active_kind_carries_a_classification(self) -> None:
        rows = self._rows(self.contract)
        self.assertTrue(rows)
        for row in rows:
            self.assertIn(row.get("verb_form"), lint_artifacts.EVENT_KIND_VERB_FORMS, row)

    # --- truth-source mutations -----------------------------------------

    def test_missing_verb_form_is_rejected(self) -> None:
        contract = copy.deepcopy(self.contract)
        self._row(contract, "ak.message.create").pop("verb_form")
        failures = self._run(contract, self.generated)
        self.assertTrue(
            any("ak.message.create must declare verb_form" in failure for failure in failures),
            failures,
        )

    def test_illegal_verb_form_value_is_rejected(self) -> None:
        contract = copy.deepcopy(self.contract)
        self._row(contract, "ak.message.create")["verb_form"] = "imperative"
        failures = self._run(contract, self.generated)
        self.assertTrue(
            any("found 'imperative'" in failure for failure in failures), failures
        )

    def test_past_participle_without_rationale_is_rejected(self) -> None:
        contract = copy.deepcopy(self.contract)
        self._row(contract, "ak.audit.accessed").pop("verb_form_rationale")
        failures = self._run(contract, self.generated)
        self.assertTrue(
            any(
                "ak.audit.accessed declares verb_form=past_participle without" in failure
                for failure in failures
            ),
            failures,
        )

    def test_blank_rationale_is_rejected(self) -> None:
        contract = copy.deepcopy(self.contract)
        self._row(contract, "ak.audit.accessed")["verb_form_rationale"] = "   "
        failures = self._run(contract, self.generated)
        self.assertTrue(
            any("without a non-empty verb_form_rationale" in failure for failure in failures),
            failures,
        )

    def test_fabricated_rationale_on_a_base_verb_is_rejected(self) -> None:
        contract = copy.deepcopy(self.contract)
        self._row(contract, "ak.message.create")["verb_form_rationale"] = "reads like a notice"
        failures = self._run(contract, self.generated)
        self.assertTrue(
            any("MUST NOT carry a verb_form_rationale" in failure for failure in failures),
            failures,
        )

    # --- generated projection -------------------------------------------

    def test_generated_projection_drift_is_rejected(self) -> None:
        generated = copy.deepcopy(self.generated)
        for row in generated["event_kinds"]:
            if row["event_kind"] == "ak.contact.accepted":
                row["verb_form"] = "base"
        failures = self._run(self.contract, generated)
        self.assertTrue(
            any(
                "generated verb_form registration for 'ak.contact.accepted' drifted" in failure
                for failure in failures
            ),
            failures,
        )

    def test_generated_projection_dropping_the_field_is_rejected(self) -> None:
        generated = copy.deepcopy(self.generated)
        for row in generated["event_kinds"]:
            row.pop("verb_form", None)
            row.pop("verb_form_rationale", None)
        failures = self._run(self.contract, generated)
        self.assertTrue(any("drifted from" in failure for failure in failures), failures)

    # --- readable table --------------------------------------------------

    def test_prose_table_closes_over_exactly_the_registered_set(self) -> None:
        kinds, errors = lint_artifacts.prose_past_participle_event_kinds(
            COMMON_FIELDS.read_text(encoding="utf-8")
        )
        self.assertEqual(errors, [])
        registered = {
            row["event_kind"]
            for row in self._rows(self.contract)
            if row.get("verb_form") == "past_participle"
        }
        self.assertEqual(kinds, registered)
        self.assertEqual(len(kinds), 8)

    def test_merged_prose_row_is_rejected(self) -> None:
        text = COMMON_FIELDS.read_text(encoding="utf-8").replace(
            "| `ak.contact.requested` |",
            "| `ak.contact.requested` / `.accepted` |",
            1,
        )
        _, errors = lint_artifacts.prose_past_participle_event_kinds(text)
        self.assertTrue(
            any("merges several kinds" in error for error in errors), errors
        )

    def test_prose_row_dropped_from_the_table_is_rejected(self) -> None:
        text = COMMON_FIELDS.read_text(encoding="utf-8")
        kinds, _ = lint_artifacts.prose_past_participle_event_kinds(text)
        self.assertIn("ak.mls.commit_failed", kinds)
        stripped = "\n".join(
            line for line in text.splitlines() if "`ak.mls.commit_failed`" not in line
        )
        reduced, errors = lint_artifacts.prose_past_participle_event_kinds(stripped)
        self.assertEqual(errors, [])
        self.assertNotIn("ak.mls.commit_failed", reduced)


if __name__ == "__main__":
    unittest.main()
