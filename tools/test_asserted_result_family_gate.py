"""Mutation tests for the asserted-family / registry gate.

`artifacts/**` descriptions are a normative surface: they carry the closed field
sets, subjects and write contracts that `zh` prose defers to. So a payload
description saying "rule_id is the stable policy_rule typed current result
subject" is a registration claim, and nothing checked it -- both existing family
gates start from the registry, so neither can see a family that was only ever
asserted.

Each test states one proposition about the connection the gate adds.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_REGISTRY = ROOT / "spec/v1/artifacts/registry/contract-registry.json"
ERROR_CODE_REGISTRY = ROOT / "spec/v1/artifacts/registry/error-code-registry.json"
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import proof_context_schemas as gate
from tools.artifact_lint.core import parse_json_file, read_text as cached_read_text


def errors_for(
    payload_schema: str | None = None,
    families: list[str] | None = None,
    ledger: str | None = None,
    artifact_overrides: dict[Path, str] | None = None,
) -> list[str]:
    """Run the gate against substituted sources."""
    lint = gate.Lint()
    original_read = Path.read_text
    original_is_file = Path.is_file
    original_families = gate._registered_result_families
    original_sources = gate._asserted_result_family_sources
    overrides = dict(artifact_overrides or {})
    if payload_schema is not None:
        overrides[gate.EVENT_PAYLOAD_SCHEMA] = payload_schema
        overrides[CONTRACT_REGISTRY] = "{}"

    def read_text(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        if self in overrides:
            return overrides[self]
        if ledger is not None and self == gate.ASSERTED_FAMILY_EXEMPTIONS:
            return ledger
        return original_read(self, *args, **kwargs)

    def is_file(self):  # type: ignore[no-untyped-def]
        if ledger is not None and self == gate.ASSERTED_FAMILY_EXEMPTIONS:
            return True
        return original_is_file(self)

    # load_json memoises per path, so a substituted document would otherwise
    # outlive its own test and be read back as if it were the live tree.
    parse_json_file.cache_clear()
    cached_read_text.cache_clear()
    Path.read_text = read_text  # type: ignore[method-assign]
    Path.is_file = is_file  # type: ignore[method-assign]
    if overrides:
        gate._asserted_result_family_sources = lambda: sorted(overrides)  # type: ignore[assignment]
    if families is not None:
        gate._registered_result_families = lambda _lint: set(families)  # type: ignore[assignment]
    try:
        gate.check_asserted_result_families_are_registered(lint)
    finally:
        Path.read_text = original_read  # type: ignore[method-assign]
        Path.is_file = original_is_file  # type: ignore[method-assign]
        gate._registered_result_families = original_families  # type: ignore[assignment]
        gate._asserted_result_family_sources = original_sources  # type: ignore[assignment]
        parse_json_file.cache_clear()
        cached_read_text.cache_clear()
    return lint.errors


class AssertedResultFamilyGateTest(unittest.TestCase):
    def test_the_live_tree_passes(self) -> None:
        self.assertEqual(errors_for(), [])

    def test_an_asserted_unregistered_family_is_reported(self) -> None:
        """The exact regression the gate exists for: a description claims a
        family the registry never carried."""
        reported = errors_for(
            payload_schema='{"d": "x_id is the never_registered typed current result subject."}',
            families=["realm_profile"],
            ledger='{"unregistered_families": []}',
        )
        self.assertTrue(
            any("never_registered" in error for error in reported), reported
        )

    def test_a_registered_family_is_accepted(self) -> None:
        reported = errors_for(
            payload_schema='{"d": "Writes the realm_profile typed current result."}',
            families=["realm_profile"],
            ledger='{"unregistered_families": []}',
        )
        self.assertEqual(reported, [])

    def test_a_ledgered_family_is_accepted(self) -> None:
        reported = errors_for(
            payload_schema='{"d": "Writes the deferred_family typed current result."}',
            families=["realm_profile"],
            ledger=json.dumps(
                {
                    "unregistered_families": [
                        {"result_family": "deferred_family", "reason": "why"}
                    ]
                }
            ),
        )
        self.assertEqual(reported, [])

    def test_the_ledger_is_a_ratchet_when_the_family_becomes_registered(self) -> None:
        """A listed family that acquires a registration is itself an error, so
        the ledger cannot quietly outlive the gap it recorded."""
        reported = errors_for(
            payload_schema='{"d": "Writes the deferred_family typed current result."}',
            families=["deferred_family"],
            ledger=json.dumps(
                {
                    "unregistered_families": [
                        {"result_family": "deferred_family", "reason": "why"}
                    ]
                }
            ),
        )
        self.assertTrue(any("remove the exemption" in e for e in reported), reported)

    def test_the_ledger_is_a_ratchet_when_the_assertion_disappears(self) -> None:
        reported = errors_for(
            payload_schema='{"d": "no claim here"}',
            families=["realm_profile"],
            ledger=json.dumps(
                {
                    "unregistered_families": [
                        {"result_family": "deferred_family", "reason": "why"}
                    ]
                }
            ),
        )
        self.assertTrue(any("no description asserts it" in e for e in reported), reported)

    def test_a_ledger_entry_without_a_reason_is_reported(self) -> None:
        """An exemption with no stated reason is how a ratchet turns into a
        dumping ground."""
        reported = errors_for(
            payload_schema='{"d": "Writes the deferred_family typed current result."}',
            families=["realm_profile"],
            ledger=json.dumps(
                {"unregistered_families": [{"result_family": "deferred_family"}]}
            ),
        )
        self.assertTrue(any("must state a reason" in e for e in reported), reported)

    def test_single_word_assignment_claims_are_reported(self) -> None:
        """A role noun plus ``stable`` is an assignment, not ordinary prose."""
        reported = errors_for(
            payload_schema='{"d": "policy_id is the stable policy typed current result subject."}',
            families=["realm_profile"],
            ledger='{"unregistered_families": []}',
        )
        self.assertTrue(any("'policy'" in error for error in reported), reported)

    def test_a_single_word_claim_in_another_artifact_file_is_reported(self) -> None:
        reported = errors_for(
            artifact_overrides={
                ERROR_CODE_REGISTRY: '{"d": "The stable phantom typed current result family."}'
            },
            families=["realm_profile"],
            ledger='{"unregistered_families": []}',
        )
        self.assertTrue(any("'phantom'" in error for error in reported), reported)

    def test_a_negated_family_sentence_is_not_an_assignment(self) -> None:
        reported = errors_for(
            payload_schema=(
                '{"d": "A refusal does not produce never_registered typed current result state."}'
            ),
            families=["realm_profile"],
            ledger='{"unregistered_families": []}',
        )
        self.assertEqual(reported, [])

    def test_a_generated_only_assertion_cannot_hide_from_the_source_scan(self) -> None:
        """Generated prose is not proof, but it remains a normative read surface."""
        generated = ROOT / "spec/v1/artifacts/registry/event-kind-registry.json"
        reported = errors_for(
            artifact_overrides={
                CONTRACT_REGISTRY: "{}",
                generated: '{"d": "Writes generated_split typed current result state."}',
            },
            families=["realm_profile"],
            ledger='{"unregistered_families": []}',
        )
        self.assertTrue(any("generated_split" in error for error in reported), reported)

    def test_the_live_ledger_entries_each_state_a_reason(self) -> None:
        document = json.loads(
            gate.ASSERTED_FAMILY_EXEMPTIONS.read_text(encoding="utf-8")
        )
        for entry in document["unregistered_families"]:
            self.assertTrue(entry.get("result_family"), entry)
            self.assertGreater(len(entry.get("reason", "")), 80, entry)


if __name__ == "__main__":
    unittest.main()
