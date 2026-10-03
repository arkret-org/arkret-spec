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
                gate.ACTIONS,
                gate.VECTORS,
                gate.SCHEMA,
                gate.RESOLVER_SCHEMA,
                gate.FIXTURE,
                gate.RUNTIME_FIXTURE,
                gate.SIGNAL_SCHEMA,
                gate.SIGNAL_FIXTURE,
            )
        }
        self.texts = {
            path.resolve(): path.read_text(encoding="utf-8")
            for path in (gate.PROSE, gate.VECTOR_PROSE, gate.REALM_PROSE, gate.SIGNAL_PROSE, gate.RUNNER)
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

    def test_runtime_rotation_cannot_be_skipped_for_unchanged_membership(self) -> None:
        def mutate(documents):
            documents[gate.RUNTIME_FIXTURE.resolve()]["owned_agent_runtime_repair"]["cases"][0]["expected_plan"] = "no_change"

        self.assert_red(mutate, "current endpoint/gate classification")

    def test_same_key_reauthorization_still_changes_the_complete_endpoint(self) -> None:
        def mutate(documents):
            documents[gate.RUNTIME_FIXTURE.resolve()]["owned_agent_runtime_repair"]["cases"][1]["expected_plan"] = "no_change"

        self.assert_red(mutate, "current endpoint/gate classification")

    def test_paused_runtime_cannot_be_added(self) -> None:
        def mutate(documents):
            documents[gate.RUNTIME_FIXTURE.resolve()]["owned_agent_runtime_repair"]["cases"][4]["expected_plan"] = "remove_add_runtime"

        self.assert_red(mutate, "current endpoint/gate classification")

    def test_runtime_repair_cannot_advance_membership_revision(self) -> None:
        def mutate(documents):
            documents[gate.RUNTIME_FIXTURE.resolve()]["owned_agent_runtime_repair"]["invariants"]["key_access_revision_delta"] = 1

        self.assert_red(mutate, "same-group invariants")

    def test_human_second_device_cannot_replace_the_first_leaf(self) -> None:
        def mutate(documents):
            documents[gate.RUNTIME_FIXTURE.resolve()]["owned_agent_runtime_repair"]["cases"][-1]["expected_plan"] = "remove_add_runtime"

        self.assert_red(mutate, "current endpoint/gate classification")

    def test_runtime_repair_negative_case_cannot_disappear(self) -> None:
        def mutate(documents):
            documents[gate.RUNTIME_FIXTURE.resolve()]["owned_agent_runtime_repair"]["cases"].pop()

        self.assert_red(mutate, "every scheduling and fail-closed case")

    def test_runtime_fixture_cannot_be_unlinked_from_the_active_vector(self) -> None:
        def mutate(documents):
            row = next(row for row in documents[gate.VECTORS.resolve()]["vectors"]
                       if row["vector_id"] == gate.VECTOR_IDS["direct_conversation_participant_authority_denied"])
            row["source_refs"].pop()

        self.assert_red(mutate, "retain the runtime endpoint repair fixture")

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

    def run_signal_gate(self, mutate=None) -> list[str]:
        documents = copy.deepcopy(self.documents)
        if mutate is not None:
            mutate(documents)
        original_json = gate.load_json

        def load_json(lint, path):  # type: ignore[no-untyped-def]
            return documents.get(Path(path).resolve(), original_json(lint, path))

        gate.load_json = load_json
        try:
            lint = Lint()
            gate.check_direct_conversation_signal_admission(lint)
            return lint.errors
        finally:
            gate.load_json = original_json

    def test_signal_contract_passes(self) -> None:
        self.assertEqual(self.run_signal_gate(), [])

    def test_edge_second_admission_fails(self) -> None:
        def mutate(documents: dict) -> None:
            documents[gate.SIGNAL_FIXTURE.resolve()]["event_authority_role_cases"][0]["profile_admission_count"] = 1

        self.assertTrue(any("must not repeat current-governance admission" in e for e in self.run_signal_gate(mutate)))

    def test_signal_product_kind_leak_fails(self) -> None:
        def mutate(documents: dict) -> None:
            documents[gate.SIGNAL_SCHEMA.resolve()]["properties"]["signal_kind"] = {"type": "string"}

        self.assertTrue(any("must remain encrypted" in e for e in self.run_signal_gate(mutate)))

    def test_signal_second_governance_writer_fails(self) -> None:
        def mutate(documents: dict) -> None:
            documents[gate.CONTRACT.resolve()]["operation_registry"]["direct_conversation_signal_admission_mappings"]["governance_writer"] = "recipient_account_station"

        self.assertTrue(any("governance_writer" in e for e in self.run_signal_gate(mutate)))

    def test_signal_event_surface_mixing_fails(self) -> None:
        def mutate(documents: dict) -> None:
            row = next(r for r in documents[gate.AUTHORITY.resolve()]["sources"] if r["authority_source_id"] == "ak.authority.direct_conversation_participant.v1")
            row["event_action_allowlist"].append("ak.typing.broadcast")

        self.assertTrue(any("partitions" in e for e in self.run_signal_gate(mutate)))

    def test_signal_stale_peer_gate_removal_fails(self) -> None:
        def mutate(documents: dict) -> None:
            documents[gate.CONTRACT.resolve()]["operation_registry"]["direct_conversation_signal_admission_mappings"]["freshness_stages"].pop(2)

        self.assertTrue(any("four read-only freshness" in e for e in self.run_signal_gate(mutate)))


if __name__ == "__main__":
    unittest.main()
