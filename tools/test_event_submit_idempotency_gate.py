"""Mutation tests for Event-submit full-body replay across endpoint unions."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import event_submit_idempotency as gate
from tools.artifact_lint.core import Lint


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class EventSubmitIdempotencyGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.documents = {gate.CONTRACT.resolve(): read(gate.CONTRACT)}
        self.prose = gate.PROSE.read_text(encoding="utf-8")

    def run_gate(self, mutate=None, prose_mutate=None) -> list[str]:
        documents = copy.deepcopy(self.documents)
        prose = self.prose
        if mutate is not None:
            mutate(documents)
        if prose_mutate is not None:
            prose = prose_mutate(prose)
        original_json = gate.load_json
        original_text = gate.read_text

        def load_json(lint, path):  # type: ignore[no-untyped-def]
            resolved = Path(path).resolve()
            return documents.get(resolved) if resolved in documents else original_json(lint, path)

        def read_text(path):  # type: ignore[no-untyped-def]
            return prose if Path(path).resolve() == gate.PROSE.resolve() else original_text(path)

        gate.load_json = load_json
        gate.read_text = read_text
        try:
            lint = Lint()
            gate.check_event_submit_idempotency(lint)
            return lint.errors
        finally:
            gate.load_json = original_json
            gate.read_text = original_text

    def assert_red(self, mutate=None, marker: str = "", prose_mutate=None) -> None:
        errors = self.run_gate(mutate, prose_mutate)
        self.assertTrue(any(marker in error for error in errors), errors)

    def operation(self, documents: dict, operation_id: str) -> dict:
        rows = documents[gate.CONTRACT.resolve()]["operation_registry"]["operations"]
        return gate._find(rows, "operation_id", operation_id)

    def test_complete_contract_passes(self) -> None:
        self.assertEqual(self.run_gate(), [])

    def test_self_submit_cannot_be_protocol_sequence(self) -> None:
        def mutate(documents: dict) -> None:
            self.operation(documents, "ak.self.events.command.submit.v1")["idempotency_mechanism"] = "protocol_sequence"

        self.assert_red(mutate, "canonical_hash/full_body/retry_safe=true")

    def test_peer_submit_cannot_hash_only_event_pointer(self) -> None:
        def mutate(documents: dict) -> None:
            self.operation(documents, "ak.peer.events.command.submit.v1")["canonical_hash_input"] = "/event"

        self.assert_red(mutate, "canonical_hash/full_body/retry_safe=true")

    def test_peer_submit_must_remain_retry_safe(self) -> None:
        def mutate(documents: dict) -> None:
            self.operation(documents, "ak.peer.events.command.submit.v1")["retry_safe"] = False

        self.assert_red(mutate, "canonical_hash/full_body/retry_safe=true")

    def test_prose_cannot_restore_protocol_sequence_claim(self) -> None:
        self.assert_red(
            marker="obsolete claim",
            prose_mutate=lambda prose: prose + "\n两项虽登记为 `protocol_sequence`。\n",
        )

    def test_prose_must_reject_batch_partial_retry(self) -> None:
        self.assert_red(
            marker="normative prose omits",
            prose_mutate=lambda prose: prose.replace(
                "不存在顶层 `accepted[]`／`duplicate[]`",
                "当前登记 schema 允许逐项求差",
            ),
        )

    def test_prose_cannot_turn_idempotency_rule_into_peer_shape_adjudication(self) -> None:
        self.assert_red(
            marker="normative prose omits",
            prose_mutate=lambda prose: prose.replace("返回原 branch outcome 或等价幂等结果", "允许重新求值"),
        )

    def test_runner_invokes_gate(self) -> None:
        source = (ROOT / "tools/artifact_lint/runner.py").read_text(encoding="utf-8")
        self.assertIn("check_event_submit_idempotency(lint)", source)


if __name__ == "__main__":
    unittest.main()
