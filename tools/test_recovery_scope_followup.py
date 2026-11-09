"""Reference/model regression only; no Native admission or physical handoff claims."""

import copy
import json
import unittest
from pathlib import Path

from tools import recovery_scope_cleanup as m
from tools import test_content_history_contract as contract_tests


class RecoveryScopeFollowupTest(unittest.TestCase):
    setUpClass = classmethod(contract_tests.ContentHistoryContractTest.setUpClass.__func__)
    validate = contract_tests.ContentHistoryContractTest.validate

    def setUp(self):
        root = Path(m.__file__).resolve().parents[1]
        self.f = json.loads((root / 'spec/v1/artifacts/fixtures/content-history-fixture.json').read_text(encoding='utf-8'))['scope_retirement']
        self.authorization = self.f['authorization']
        self.inventory = self.f['inventory']
        self.entry = self.inventory['entries'][0]
        self.reader = self.f['reader_authority']
        self.historical = self.f['historical_completion_basis']
        self.route = self.f['current_delivery']

    def fresh(self, challenge=101):
        key = m.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(self.f['origin_signing_seed_hex']))
        return m.sign({**self.authorization, 'delivery_challenge_base64url': m.b64(bytes([challenge]) * 32)}, key, source=True)

    def test_first_domain_failure_is_an_immutable_outer_and_challenge_outcome(self):
        outer, inner, observations, calls = {}, {}, {}, []

        def attempt(source, eligible):
            m.qualify_source(source, self.inventory, self.entry, self.reader, self.route, '2026-11-09T00:00:03.000Z')
            return m.transport_replay(outer, 'origin', 'peer', source, True,
                lambda: m.observe_delivery(observations, source, lambda: compute(source, eligible)))

        def compute(source, eligible):
            calls.append(eligible)
            return m.settle_intent(inner, source, eligible, self.f['results']['removed'])

        for eligible in [True, False]:
            with self.assertRaisesRegex(m.FirstFinalizationRejected, 'failed_precondition'):
                attempt(self.authorization, eligible)
        self.assertEqual(calls, [True])
        self.assertFalse(inner)
        self.assertEqual((len(outer), len(observations)), (1, 1))
        self.assertEqual(attempt(self.fresh(), False), self.f['results']['removed'])
        self.assertEqual(calls, [True, False])
        with self.assertRaises(m.FirstFinalizationRejected):
            attempt(self.authorization, False)

    def test_auth_and_expiry_precede_cached_failure_and_temporary_failure_is_retryable(self):
        outer, observations = {}, {}
        with self.assertRaises(m.FirstFinalizationRejected):
            m.transport_replay(outer, 'origin', 'peer', self.authorization, True,
                lambda: m.observe_delivery(observations, self.authorization, lambda: m.settle_intent({}, self.authorization, True, None)))
        with self.assertRaisesRegex(ValueError, 'not_found'):
            m.transport_replay(outer, 'origin', 'peer', self.authorization, False, lambda: self.fail('unauthorized compute'))
        with self.assertRaisesRegex(ValueError, 'expired'):
            m.qualify_source(self.authorization, self.inventory, self.entry, self.reader, self.route, self.authorization['expires_at'])
        temporary_outer, temporary_observations = {}, {}
        for _ in range(2):
            with self.assertRaisesRegex(ValueError, 'revision_unavailable'):
                m.transport_replay(temporary_outer, 'origin', 'peer', self.authorization, True,
                    lambda: m.observe_delivery(temporary_observations, self.authorization,
                        lambda: (_ for _ in ()).throw(ValueError('revision_unavailable'))))
        self.assertFalse(temporary_outer)
        self.assertFalse(temporary_observations)
        changed = self.fresh()
        changed['delivery_challenge_base64url'] = self.authorization['delivery_challenge_base64url']
        changed['expires_at'] = '2026-11-09T00:04:00.000Z'
        key = m.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(self.f['origin_signing_seed_hex']))
        changed = m.sign(changed, key, source=True)
        with self.assertRaisesRegex(ValueError, 'duplicate_conflict'):
            m.observe_delivery(observations, changed, lambda: self.fail('challenge rebound before effects'))

    def test_handoff_target_is_an_independent_ordinary_realm_and_pcr_is_unchanged(self):
        self.assertNotEqual(self.entry['effective_scope'], self.inventory['pcr_cut']['stream_ref'])
        self.assertEqual(self.historical['scope_cut']['stream_ref'], self.entry['effective_scope'])
        self.assertEqual(self.route['scope_authority']['kind'], 'ordinary_realm')
        after = self.f['handoff']
        m.verify_self_retirement(after['self_deliveries']['removed'], after['authorization'], self.inventory,
            self.entry, self.reader, self.historical, after['current_delivery'], '2026-11-09T00:06:02.000Z')
        self.assertEqual(after['authorization']['replacement']['actor_id'], self.inventory['actor_id'])
        self.assertNotEqual(after['current_delivery']['governance_station_id'], self.route['origin_service_id'])
        with self.assertRaisesRegex(ValueError, 'natively qualified'):
            m.qualify_source(after['authorization'], self.inventory, self.entry, self.reader,
                {**after['current_delivery'], 'handoff_native_qualified': False}, '2026-11-09T00:06:02.000Z')

    def test_signed_complete_material_cannot_unlock_fixed_or_unknown_scope_migration(self):
        for kind in ['human_pcr', 'user_managed_agent_pcr', 'direct', 'unknown']:
            with self.subTest(kind=kind):
                entry = copy.deepcopy(self.entry)
                if kind in {'human_pcr', 'user_managed_agent_pcr'}:
                    entry['effective_scope'] = self.inventory['pcr_cut']['stream_ref']
                    entry['genesis_event_ref'] = 'ak:event:' + entry['effective_scope']['realm_id'].split(':', 2)[2]
                    entry['base_group_state_ref'] = entry['genesis_event_ref']
                f = m.fixture(self.inventory['replacement'], entry, self.inventory['pcr_cut'], scope_kind=kind)
                after = f['handoff']
                self.validate('content-encryption.schema.json#/$defs/recovery_scope_cleanup_self_response_body', after['self_deliveries']['removed'])
                m.verify_signature(after['authorization'], after['current_delivery']['origin_public_key'], source=True)
                m.verify_signature(after['deliveries']['removed']['delivery_attestation'], after['current_delivery']['governor_public_key'], delivery=True)
                if kind != 'unknown':
                    m.verify_self_retirement(f['self_deliveries']['removed'], f['authorization'], f['inventory'], entry,
                        f['reader_authority'], f['historical_completion_basis'], f['current_delivery'], '2026-11-09T00:00:03.000Z')
                with self.assertRaisesRegex(ValueError, 'forbids governance migration|unknown native scope origin'):
                    m.verify_self_retirement(after['self_deliveries']['removed'], after['authorization'], f['inventory'], entry,
                        f['reader_authority'], f['historical_completion_basis'], after['current_delivery'], '2026-11-09T00:06:02.000Z')

    def test_accepted_delivery_survives_offline_restart_without_becoming_a_new_live_acceptance(self):
        ledger = {}
        identity = m.accept_self_retirement(ledger, self.f['self_deliveries']['removed'], self.authorization,
            self.inventory, self.entry, self.reader, self.historical, self.route, '2026-11-09T00:00:03.000Z')
        restarted = json.loads(json.dumps(ledger))
        self.assertEqual(m.resume_accepted_retirement(restarted, identity, self.inventory, self.entry, self.reader),
                         self.f['results']['removed']['retirement_proof'])
        late = {}
        with self.assertRaises(ValueError):
            m.accept_self_retirement(late, self.f['self_deliveries']['removed'], self.authorization,
                self.inventory, self.entry, self.reader, self.historical, self.route, '2026-11-09T00:05:01.000Z')
        self.assertFalse(late)
        for reader in [{**self.reader, 'episode_current': False},
                       {**self.reader, 'role': 'agent_custodian', 'custody_current': False}]:
            with self.subTest(reader=reader), self.assertRaises(ValueError):
                m.resume_accepted_retirement(restarted, identity, self.inventory, self.entry, reader)
        with self.assertRaises(ValueError):
            m.resume_accepted_retirement({}, identity, self.inventory, self.entry, self.reader)
        changed = copy.deepcopy(restarted)
        changed[identity]['response']['delivery']['delivery_attestation']['recipient_service_id'] = 'ak:did_core:web:other.example'
        with self.assertRaises(ValueError):
            m.resume_accepted_retirement(changed, identity, self.inventory, self.entry, self.reader)

    def test_pending_retirement_then_rejoin_converges_through_normal_rekeyed_terminal(self):
        outer, inner, observations, terminals = {}, {}, {}, {}
        pending = m.transport_replay(outer, 'origin', 'peer', self.authorization, True,
            lambda: m.observe_delivery(observations, self.authorization,
                lambda: m.settle_retirement_for_scope(terminals, inner, self.authorization, False, None)))
        self.assertEqual(pending, {'state': 'pending'})
        fresh = self.fresh()
        with self.assertRaises(m.FirstFinalizationRejected):
            m.observe_delivery(observations, fresh,
                lambda: m.settle_retirement_for_scope(terminals, inner, fresh, True, None))
        identity = m.scope_episode_identity(self.authorization)
        other_episode = ('another-subject', 'another-episode')
        blockers = {identity, other_episode}
        winning = {**self.historical['scope_cut'], 'stream_position': 18,
                   'event_id': 'ak:event:' + m.b64(b'\x01' + bytes([212]) * 32),
                   'commit_id': 'ak:realm_commit:' + m.b64(b'\x01' + bytes([213]) * 32)}
        result = {'state': 'rekeyed', 'effective_scope': self.entry['effective_scope'],
                  'genesis_event_ref': self.entry['genesis_event_ref'], 'winning_commit': winning,
                  'remaining_old_leaf_count': 0, 'root_refs': ['sha256:' + '1' * 64],
                  'backup_refs': ['ak:backup:019b0000-0000-7000-8000-000000000001']}
        self.validate('content-encryption.schema.json#/$defs/scope_cleanup', result)
        native = {'winning_commit': winning, 'current_eligible': True, 'accepted_rfc_complete': True,
                  'all_old_endpoints_removed': True, 'roots_and_backups_durable': True,
                  'replacement': self.authorization['replacement'], 'epoch': int(self.entry['epoch']) + 1}
        before = copy.deepcopy((terminals, blockers))
        with self.assertRaises(ValueError):
            m.complete_scope_rekey(terminals, blockers, self.authorization, result,
                {**native, 'roots_and_backups_durable': False})
        self.assertEqual((terminals, blockers), before)
        self.assertEqual(m.complete_scope_rekey(terminals, blockers, self.authorization, result, native), result)
        self.assertEqual(terminals[identity]['cleanup'], result)

        self.assertEqual(blockers, {other_episode})
        self.assertFalse(m.business_send_allowed(blockers, True))
        self.assertFalse(m.business_send_allowed(set(), True, terminal=True))
        self.assertEqual(m.observe_delivery(observations, self.authorization, lambda: self.fail('old observation changed')), pending)
        self.assertEqual(m.transport_replay(outer, 'origin', 'peer', self.authorization, True, lambda: self.fail('old body changed')), pending)
        for eligible in [True, False]:
            with self.assertRaises(m.FirstFinalizationRejected):
                m.settle_retirement_for_scope(terminals, inner, self.fresh(102), eligible, self.f['results']['removed'])
        self.assertEqual(terminals[identity]['cleanup'], result)

    def test_first_retired_terminal_and_its_intent_cannot_be_overwritten(self):
        terminals, ledger = {}, {}
        m.settle_retirement_for_scope(terminals, ledger, self.authorization, False, self.f['results']['removed'])
        before = copy.deepcopy((terminals, ledger))
        changed = self.fresh()
        changed['nonce_base64url'] = m.b64(bytes([103]) * 32)
        with self.assertRaisesRegex(ValueError, 'duplicate_conflict'):
            m.settle_retirement_for_scope(terminals, ledger, changed, False, self.f['results']['terminated'])
        self.assertEqual((terminals, ledger), before)
        with self.assertRaisesRegex(ValueError, 'revision_unavailable'):
            m.settle_retirement_for_scope(terminals, {}, self.authorization, True, None)
        self.assertEqual((terminals, ledger), before)

    def test_prose_and_operation_errors_preserve_pending_and_retirement_branch_gates(self):
        root = Path(m.__file__).resolve().parents[1]
        prose = (root / 'spec/v1/zh/crypto-media/content-history.md').read_text(encoding='utf-8')
        self.assertIn('pending不以全部历史已到齐为前提', prose)
        self.assertIn('removed／terminated仅核§10.1', prose)
        self.assertIn('已有rekeyed终局的episode不得再首次签发retirement', prose)
        mapping = json.loads((root / 'spec/v1/artifacts/registry/operations-error-mapping.json').read_text(encoding='utf-8'))
        selected = [row for row in mapping['operations'] if row['operation_id'] in {
            'ak.self.mls.command.reconcile_recovery_scope.v1', 'ak.peer.mls.command.reconcile_recovery_scope.v1'}]
        self.assertEqual(len(selected), 2)
        for row in selected:
            self.assertIn('first retirement without a prior terminal', row['description'])
            self.assertIn('existing removed/terminated terminal remains readable after rejoin', row['description'])
            self.assertIn('already finalized as rekeyed', row['description'])


if __name__ == '__main__':
    unittest.main()
