"""Mutations must not turn a typed receipt into a different proof contract."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import franking_transcript as gate
from tools.artifact_lint.core import Lint


class FrankingCurrentInstallationGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.current = json.loads(gate.CURRENT_SCHEMA.read_text(encoding="utf-8"))
        self.prose = gate.MODERATION_PROSE.read_text(encoding="utf-8")

    def errors_after(self, mutate=None, prose=None) -> list[str]:
        current = copy.deepcopy(self.current)
        if mutate:
            mutate(current["$defs"]["moderation_franking_proof_result"])
        lint = Lint()
        with (
            mock.patch.object(gate, "load_json", return_value=current),
            mock.patch.object(gate, "read_text", return_value=self.prose if prose is None else prose),
        ):
            gate._check_current_installation(lint)
        return lint.errors

    def test_existing_closed_contract_passes(self) -> None:
        self.assertEqual(self.errors_after(), [])

    def test_target_cannot_become_report_id(self) -> None:
        def mutate(row) -> None:
            row["properties"]["selector"]["required"] = ["kind", "report_id"]

        self.assertTrue(self.errors_after(mutate))

    def test_value_cannot_become_an_evidence_wrapper(self) -> None:
        def mutate(row) -> None:
            row["properties"]["value"]["$ref"] = "./moderation-evidence.schema.json#/$defs/evidence_package"

        self.assertTrue(self.errors_after(mutate))

    def test_value_cannot_be_opened_to_extra_members(self) -> None:
        self.assertTrue(self.errors_after(lambda row: row.update(additionalProperties=True)))

    def test_current_installation_must_not_wait_for_report(self) -> None:
        prose = self.prose.replace("普通聊天的同步与展示 MUST NOT 等待", "普通聊天可以等待")
        self.assertTrue(self.errors_after(prose=prose))


if __name__ == "__main__":
    unittest.main()
