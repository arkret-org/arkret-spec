"""Guard the compact Call contract and its explicit verification limits."""

import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.exceptions import InvalidSignature

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.artifact_lint import call_current as gate
from tools.generate_call_current_fixture import ACTOR, OTHER, build_fixture, jcs, project, revision


class CallCurrentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = build_fixture()

    def test_live_contract_and_every_registered_case(self):
        lint = gate.Lint()
        gate.check_call_current(lint)
        self.assertEqual(lint.errors, [])
        for case in self.fixture['cases']:
            with self.subTest(case=case['name']):
                try:
                    actual = gate.run_case(self.fixture, case['name'])
                except Exception:
                    actual = 'reject'
                self.assertEqual(actual, case['expected'])

    def test_explicit_effective_cardinality_and_last_revision(self):
        roster_counts = [0, 0, 1, 2, 2, 2, 2, 2, 1, 0, 1]
        moderation_counts = [0, 0, 0, 0, 1, 0, 1, 1, 1, 1, 2]
        last_positions = {'roster': 0, 'moderation': 0}
        for index, snapshot in enumerate(self.fixture['checkpoints']):
            original = self.fixture['original_rows'][index]
            for axis, counts in [('roster', roster_counts), ('moderation', moderation_counts)]:
                if axis + '_delta' in original['event']['payload']:
                    last_positions[axis] = index + 1
                if not last_positions[axis]:
                    self.assertFalse(any(r['selector']['kind'] == 'call_' + axis for r in snapshot['current_state_entries']))
                    continue
                row = gate.axis_row(snapshot, axis)
                self.assertEqual(len(row['value']['entries']), counts[index])
                self.assertEqual(row['revision']['stream_position'], last_positions[axis])
        current = gate.axis_row(self.fixture['checkpoints'][7], 'roster')['value']['entries']
        alice = next(e for e in current if e['value']['participant']['actor_id'] == ACTOR)
        self.assertTrue(alice['value']['participant']['participant_id'].endswith('000000000003'))

    def test_same_principal_on_different_stations_never_aliases(self):
        snapshot = self.fixture['checkpoints'][8]
        entries = gate.axis_row(snapshot, 'roster')['value']['entries']
        self.assertEqual([e['value']['participant']['actor_id'] for e in entries], [ACTOR])
        self.assertNotEqual(jcs(ACTOR), jcs(OTHER))

    def test_restore_and_repeated_ban_keep_original_kick(self):
        current = gate.axis_row(self.fixture['checkpoints'][-1], 'moderation')['value']
        kick = next(e for e in current['entries'] if e['value']['removal']['action'] == 'kick')
        row = copy.deepcopy(self.fixture['original_rows'][5])
        row['event']['payload']['moderation_delta']['expected_revision'] = revision(current['last_source']['source_commit'])
        restored = project(current, row, 'moderation', 6, self.fixture['test_keys']['issuer_public_key_b64u'])
        self.assertEqual(restored['entries'], [kick])
        removed = project(current, self.fixture['original_rows'][10], 'moderation', 6, self.fixture['test_keys']['issuer_public_key_b64u'])
        self.assertEqual(len(removed['entries']), 2)
        self.assertIn(kick, removed['entries'])

    def test_binding_changes_fail_the_actual_ed25519_verifier(self):
        entry = copy.deepcopy(gate.axis_row(self.fixture['checkpoints'][-1], 'roster')['value']['entries'][0])
        gate.verify_binding(entry, self.fixture['request_context']['realm_id'], self.fixture['request_context']['call_id'])
        entry['value']['participant']['actor_id'] = OTHER
        with self.assertRaises(InvalidSignature):
            gate.verify_binding(entry, self.fixture['request_context']['realm_id'], self.fixture['request_context']['call_id'])

    def test_no_independent_omission_claim(self):
        self.assertEqual(gate.run_case(self.fixture, 'omission_resigned_ordinary_trust_boundary'), 'accept')
        with self.assertRaisesRegex(ValueError, 'complete replica/materializer mismatch'):
            gate.run_case(self.fixture, 'omission_resigned_complete_replica')

    def test_ordinary_omission_retains_the_observable_last_join(self):
        for name in ('omission_unsigned', 'omission_resigned_ordinary_trust_boundary', 'omission_resigned_complete_replica'):
            case = next(case for case in self.fixture['cases'] if case['name'] == name)
            self.assertEqual(case['checkpoint'], 7)
            value = gate.axis_row(self.fixture['checkpoints'][case['checkpoint']], 'roster')['value']
            self.assertEqual(len(value['entries']), 2)
            self.assertEqual(sum(entry['tag_id'] == value['last_source']['tag_id'] for entry in value['entries']), 1)

    def test_below_floor_current_is_valid_without_granting_historical_event_read(self):
        self.assertEqual(gate.run_case(self.fixture, 'below_floor_current_binding_key'), 'accept')
        self.assertEqual(gate.run_case(self.fixture, 'exact_history_below_floor'), 'unavailable')
        with self.assertRaises(NotImplementedError):
            gate.run_case(self.fixture, 'undefined_rejection_case')

    def test_policy_cannot_enable_history_bypass_or_private_receipts(self):
        original = gate.load_json
        for key in ('partial_allowed', 'history_floor_bypass', 'private_receipt', 'kick_expiry'):
            def mutated(lint, path):
                value = copy.deepcopy(original(lint, path))
                if path.name == 'contract-registry.json':
                    value['current_result_registry']['call_current_contract'][key] = True
                return value
            with self.subTest(key=key), patch.object(gate, 'load_json', mutated):
                lint = gate.Lint()
                gate.check_call_current(lint)
                self.assertTrue(lint.errors)


if __name__ == '__main__':
    unittest.main()
