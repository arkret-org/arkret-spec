"""Regression tests for active-only state and historical-input isolation."""

import copy
import itertools
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.artifact_lint import grant_reaction as gate
from tools.generate_reaction_current_fixture import ACTOR, OTHER, build_fixture, sign_snapshot


class ReactionCurrentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = build_fixture()

    def test_live_contract_and_all_cases(self):
        lint = gate.Lint()
        gate.check_grant_reaction(lint)
        self.assertEqual(lint.errors, [])
        for case in self.fixture["cases"]:
            with self.subTest(case=case["name"]):
                self.assertEqual(gate.run_reaction_case(self.fixture, case["name"]), case["expected"])

    def test_empty_row_keeps_the_real_last_remove_revision(self):
        current = self.fixture["checkpoints"][-1]["current_state_entries"][0]
        self.assertEqual(current["value"], {"entries": []})
        self.assertEqual(current["revision"]["stream_position"], 6)
        self.assertNotIn("assertions", json.dumps(current))
        self.assertNotIn("last_action", json.dumps(current))

    def test_gap_is_buffered_and_not_used_to_delete_current(self):
        model = gate.ReactionReference(self.fixture["test_keys"])
        model.install(self.fixture["checkpoints"][3])
        self.assertEqual(len(model.entries), 2)
        self.assertEqual(model.receive(self.fixture["original_rows"][5]), "buffer")
        self.assertEqual(model.checkpoint, 4)
        self.assertEqual(len(model.entries), 2)
        model.receive(self.fixture["original_rows"][4])
        self.assertEqual(model.checkpoint, 6)
        self.assertEqual(model.entries, [])

    def test_partial_prefix_cannot_remove_a_complete_set(self):
        model = gate.ReactionReference(self.fixture["test_keys"], complete=False)
        with self.assertRaisesRegex(ValueError, "partial baseline"):
            model.receive(self.fixture["original_rows"][0])
        self.assertEqual(model.checkpoint, 0)

    def test_history_reads_do_not_reactivate_and_still_enforce_floor(self):
        model = gate.ReactionReference(self.fixture["test_keys"])
        model.install(self.fixture["checkpoints"][-1])
        state = copy.deepcopy(model.__dict__)
        model.historical_read(self.fixture["original_rows"][3], 4)
        self.assertEqual(model.__dict__, state)
        with self.assertRaisesRegex(ValueError, "history floor"):
            model.historical_read(self.fixture["original_rows"][0], 4)
        self.assertEqual(model.entries, [])

    def test_old_snapshot_does_not_override_a_new_checkpoint(self):
        model = gate.ReactionReference(self.fixture["test_keys"])
        model.install(self.fixture["checkpoints"][-1])
        with self.assertRaisesRegex(ValueError, "checkpoint rollback"):
            model.install(self.fixture["checkpoints"][0])

    def test_new_head_cannot_install_an_older_current_row(self):
        model = gate.ReactionReference(self.fixture["test_keys"])
        model.install(self.fixture["checkpoints"][3])
        before = copy.deepcopy(model.__dict__)
        snapshot = copy.deepcopy(self.fixture["checkpoints"][-1])
        snapshot["current_state_entries"][0] = copy.deepcopy(
            self.fixture["checkpoints"][0]["current_state_entries"][0])
        with self.assertRaisesRegex(ValueError, "current revision rollback"):
            model.install(sign_snapshot(snapshot))
        self.assertEqual(model.__dict__, before)

    def test_new_head_cannot_change_one_component_of_a_known_row_revision(self):
        for component in ("commit_id", "stream_position"):
            with self.subTest(component=component):
                model = gate.ReactionReference(self.fixture["test_keys"])
                model.install(self.fixture["checkpoints"][3])
                before = copy.deepcopy(model.__dict__)
                snapshot = copy.deepcopy(self.fixture["checkpoints"][-1])
                current = copy.deepcopy(self.fixture["checkpoints"][3]["current_state_entries"][0])
                if component == "commit_id":
                    current["revision"][component] = self.fixture["original_rows"][4]["commit"]["commit_id"]
                else:
                    current["revision"][component] += 1
                snapshot["current_state_entries"][0] = current
                with self.assertRaisesRegex(ValueError, "current revision equivocation"):
                    model.install(sign_snapshot(snapshot))
                self.assertEqual(model.__dict__, before)

    def test_full_actor_identity_participates_in_the_key(self):
        self.assertNotEqual(ACTOR, OTHER)
        self.assertEqual(ACTOR["account_id"]["principal_id"], OTHER["account_id"]["principal_id"])
        current = self.fixture["checkpoints"][3]["current_state_entries"][0]
        self.assertEqual(len(current["value"]["entries"]), 2)

    def test_active_metadata_needs_no_historical_event_fetch(self):
        snapshot = self.fixture["checkpoints"][3]
        floor = snapshot["retention_and_history_floor"]["stream_floors"][0]["oldest_position"]
        model = gate.ReactionReference(self.fixture["test_keys"])
        with patch.object(gate, "verified_row", side_effect=AssertionError("must not fetch/replay old Event")):
            model.install(snapshot)
        self.assertTrue(any(entry["source"]["stream_position"] < floor for entry in model.entries))
        self.assertTrue(all(set(entry) == {"actor_id", "key", "source"} for entry in model.entries))

    def test_same_revision_different_value_is_not_a_later_current(self):
        model = gate.ReactionReference(self.fixture["test_keys"])
        snapshot = copy.deepcopy(self.fixture["checkpoints"][3])
        model.install(snapshot)
        snapshot["current_state_entries"][0]["value"]["entries"] = []
        with self.assertRaisesRegex(ValueError, "same revision different value"):
            model.install(sign_snapshot(snapshot))

    def test_ordered_active_map_matches_full_history_for_all_short_sequences_and_cuts(self):
        choices = tuple(itertools.product(range(3), ("add", "remove")))
        for length in range(6):
            for sequence in itertools.product(choices, repeat=length):
                last, active = {}, {}
                for position, (key, action) in enumerate(sequence):
                    last[key] = (position, action)
                    if action == "add":
                        active[key] = position
                    else:
                        active.pop(key, None)
                self.assertEqual(active, {key: pos for key, (pos, action) in last.items() if action == "add"})
                for cut in range(length + 1):
                    prefix = {}
                    for position, (key, action) in enumerate(sequence[:cut]):
                        if action == "add":
                            prefix[key] = position
                        else:
                            prefix.pop(key, None)
                    for position, (key, action) in enumerate(sequence[cut:], cut):
                        if action == "add":
                            prefix[key] = position
                        else:
                            prefix.pop(key, None)
                    self.assertEqual(prefix, active)

    def test_wire_rejects_history_tombstone_and_payload_fields(self):
        schema = gate.schema_validator(gate.ARTIFACTS / "schemas/current-state.schema.json", "#/$defs/message_reactions_value")
        self.assertTrue(schema.is_valid({"entries": []}))
        self.assertFalse(schema.is_valid({"entries": [], "assertions": []}))
        entry = copy.deepcopy(self.fixture["checkpoints"][0]["current_state_entries"][0]["value"]["entries"][0])
        self.assertTrue(schema.is_valid({"entries": [entry]}))
        for member, value in (("last_action", "remove"), ("annotation", "secret"), ("encrypted_payload", {})):
            self.assertFalse(schema.is_valid({"entries": [dict(entry, **{member: value})]}))


if __name__ == "__main__":
    unittest.main()
