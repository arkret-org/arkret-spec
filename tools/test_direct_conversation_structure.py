"""Mutation tests for the active Direct Conversation structure gate."""

import sys
import copy
import unittest
from unittest.mock import patch

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint.core import Lint, load_json
from tools.artifact_lint import direct_conversation_structure as gate


class DirectConversationStructureTests(unittest.TestCase):
    def test_current_contract_and_all_wire_vectors(self):
        lint = Lint()
        gate.check_direct_conversation_structure(lint)
        self.assertEqual(lint.errors, [])

    def test_every_field_boundary_is_enforced(self):
        baseline = load_json(Lint(), gate.CONTRACT)
        source = next(row for row in baseline["authority_source_registry"]["sources"]
                      if row["authority_source_id"] == "ak.authority.direct_conversation_participant.v1")
        for key in ("scope", "main_archive", "bootstrap", "revocation", "topic", "chat_update_paths", "space_kinds"):
            with self.subTest(key=key):
                value = copy.deepcopy(baseline)
                row = next(row for row in value["authority_source_registry"]["sources"]
                           if row["authority_source_id"] == source["authority_source_id"])
                row["structural_contract"][key] = "allow_all"
                def read(lint, path):
                    return value if path == gate.CONTRACT else load_json(lint, path)
                lint = Lint()
                with patch.object(gate, "load_json", read):
                    gate.check_direct_conversation_structure(lint)
                self.assertTrue(lint.errors)

    def test_wire_expectation_flip_is_detected(self):
        value = load_json(Lint(), gate.FIXTURE)
        for index in range(len(value["cases"])):
            with self.subTest(index=index):
                changed = copy.deepcopy(value)
                changed["cases"][index]["expect_valid"] = not changed["cases"][index]["expect_valid"]
                def read(lint, path):
                    return changed if path == gate.FIXTURE else load_json(lint, path)
                lint = Lint()
                with patch.object(gate, "load_json", read):
                    gate.check_direct_conversation_structure(lint)
                self.assertTrue(lint.errors)

    def test_list_and_board_cannot_replace_the_topic_subtype(self):
        baseline = load_json(Lint(), gate.CONTRACT)
        for kind in ("list", "board"):
            with self.subTest(kind=kind):
                changed = copy.deepcopy(baseline)
                source = next(row for row in changed["authority_source_registry"]["sources"]
                              if row["authority_source_id"] == "ak.authority.direct_conversation_participant.v1")
                source["structural_contract"]["space_kinds"] = [kind]
                def read(lint, path):
                    return changed if path == gate.CONTRACT else load_json(lint, path)
                lint = Lint()
                with patch.object(gate, "load_json", read):
                    gate.check_direct_conversation_structure(lint)
                self.assertTrue(lint.errors)

    def test_personal_watch_cannot_be_removed_or_widened(self):
        baseline = load_json(Lint(), gate.CONTRACT)
        for mutation in range(4):
            with self.subTest(mutation=mutation):
                changed = copy.deepcopy(baseline)
                source = next(row for row in changed["authority_source_registry"]["sources"]
                              if row["authority_source_id"] == "ak.authority.direct_conversation_participant.v1")
                if mutation == 0:
                    source["event_action_allowlist"].remove("ak.strand.watch.set")
                elif mutation == 1:
                    source["action_allowlist"].append("ak.strand.watch.set.others")
                elif mutation == 2:
                    source["personal_watch_contract"]["watcher"] = "either_participant"
                else:
                    bootstrap = next(row for row in changed["authority_source_registry"]["sources"]
                                     if row["authority_source_id"] == "ak.authority.direct_conversation_bootstrap_participant.v1")
                    bootstrap["action_allowlist"].append("ak.strand.watch.set")
                def read(lint, path):
                    return changed if path == gate.CONTRACT else load_json(lint, path)
                lint = Lint()
                with patch.object(gate, "load_json", read):
                    gate.check_direct_conversation_structure(lint)
                self.assertTrue(lint.errors)


if __name__ == "__main__":
    unittest.main()
