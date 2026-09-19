"""Single-point mutations for the seven Direct Conversation reason producers."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import direct_conversation_admission as gate
from tools.artifact_lint.core import Lint


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class DirectConversationAdmissionGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.documents = {
            path.resolve(): read(path)
            for path in (
                gate.CONTRACT,
                gate.OPERATIONS,
                gate.ERRORS,
                gate.EVENTS,
                gate.AUTHORITY,
                gate.VECTORS,
                gate.SCHEMA,
                gate.RESOLVER_SCHEMA,
                gate.FIXTURE,
            )
        }
        self.texts = {
            path.resolve(): path.read_text(encoding="utf-8")
            for path in (gate.PROSE, gate.VECTOR_PROSE, gate.REALM_PROSE, gate.RUNNER)
        }

    def run_gate(self, mutate=None, text_mutate=None) -> list[str]:
        documents = copy.deepcopy(self.documents)
        texts = copy.deepcopy(self.texts)
        if mutate is not None:
            mutate(documents)
        if text_mutate is not None:
            text_mutate(texts)
        original_json = gate.load_json
        original_text = gate.read_text

        def load_json(lint, path):  # type: ignore[no-untyped-def]
            resolved = Path(path).resolve()
            return documents.get(resolved) if resolved in documents else original_json(lint, path)

        def read_text(path):  # type: ignore[no-untyped-def]
            resolved = Path(path).resolve()
            return texts.get(resolved) if resolved in texts else original_text(path)

        gate.load_json = load_json
        gate.read_text = read_text
        try:
            lint = Lint()
            gate.check_direct_conversation_admission_producers(lint)
            return lint.errors
        finally:
            gate.load_json = original_json
            gate.read_text = original_text

    def assert_red(self, mutate=None, marker="", text_mutate=None) -> None:
        errors = self.run_gate(mutate, text_mutate)
        self.assertTrue(any(marker in error for error in errors), errors)

    @staticmethod
    def mapping(documents: dict) -> dict:
        return documents[gate.CONTRACT.resolve()]["operation_registry"]["direct_conversation_admission_mappings"]

    def remove_rule(self, reason: str):
        def mutate(documents: dict) -> None:
            mapping = self.mapping(documents)
            mapping["rules"] = [row for row in mapping["rules"] if row["reason_code"] != reason]
            documents[gate.OPERATIONS.resolve()]["direct_conversation_admission_mappings"] = copy.deepcopy(mapping)

        return mutate

    def test_complete_contract_passes(self) -> None:
        self.assertEqual(self.run_gate(), [])

    def test_binding_producer_removal_fails(self) -> None:
        self.assert_red(self.remove_rule("direct_conversation_binding_invalid"), "exactly seven rules")

    def test_terminal_producer_removal_fails(self) -> None:
        self.assert_red(self.remove_rule("direct_conversation_terminal_forbidden"), "exactly seven rules")

    def test_member_count_producer_removal_fails(self) -> None:
        self.assert_red(self.remove_rule("direct_conversation_member_count_invalid"), "exactly seven rules")

    def test_third_party_producer_removal_fails(self) -> None:
        self.assert_red(self.remove_rule("direct_conversation_third_party_member_forbidden"), "exactly seven rules")

    def test_invite_producer_removal_fails(self) -> None:
        self.assert_red(self.remove_rule("direct_conversation_invite_forbidden"), "exactly seven rules")

    def test_root_mask_producer_removal_fails(self) -> None:
        self.assert_red(self.remove_rule("direct_conversation_root_mask_violation"), "exactly seven rules")

    def test_participant_evaluator_producer_removal_fails(self) -> None:
        self.assert_red(self.remove_rule("direct_conversation_participant_authority_denied"), "exactly seven rules")

    def test_precedence_flip_fails(self) -> None:
        def mutate(documents: dict) -> None:
            mapping = self.mapping(documents)
            mapping["precedence"][3], mapping["precedence"][4] = mapping["precedence"][4], mapping["precedence"][3]
            documents[gate.OPERATIONS.resolve()]["direct_conversation_admission_mappings"] = copy.deepcopy(mapping)

        self.assert_red(mutate, "precedence must be complete")

    def test_zero_write_mutation_fails(self) -> None:
        def mutate(documents: dict) -> None:
            documents[gate.FIXTURE.resolve()]["all_rejections"]["outbox_write_count"] = 1

        self.assert_red(mutate, "outbox_write_count=0")

    def test_member_count_read_downgrade_fails(self) -> None:
        def mutate(documents: dict) -> None:
            mapping = self.mapping(documents)
            row = next(row for row in mapping["rules"] if row["reason_code"] == "direct_conversation_member_count_invalid")
            row["read_projection"]["state"] = "rejected"
            documents[gate.OPERATIONS.resolve()]["direct_conversation_admission_mappings"] = copy.deepcopy(mapping)

        self.assert_red(mutate, "separate read-only suspended")

    def test_participant_detail_leak_fails(self) -> None:
        def mutate(documents: dict) -> None:
            mapping = self.mapping(documents)
            row = next(row for row in mapping["rules"] if row["reason_code"] == "direct_conversation_participant_authority_denied")
            row["privacy_rule"] = "return failed input name"
            documents[gate.OPERATIONS.resolve()]["direct_conversation_admission_mappings"] = copy.deepcopy(mapping)

        self.assert_red(mutate, "remain non-enumerating")

    def test_runner_wiring_removal_fails(self) -> None:
        def mutate(texts: dict) -> None:
            path = gate.RUNNER.resolve()
            texts[path] = texts[path].replace("check_direct_conversation_admission_producers(lint)", "pass")

        self.assert_red(text_mutate=mutate, marker="runner must invoke")

    def test_realm_precedence_prose_regression_fails(self) -> None:
        def mutate(texts: dict) -> None:
            path = gate.REALM_PROSE.resolve()
            texts[path] = texts[path].replace("这里必须区分三件事", "这里必须区分两件事")

        self.assert_red(text_mutate=mutate, marker="这里必须区分三件事")


if __name__ == "__main__":
    unittest.main()
