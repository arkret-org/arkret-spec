"""Reference/model regression only; no Native admission or physical handoff claims."""

import copy
import json
import unittest
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from jsonschema.exceptions import ValidationError

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
        self.assertEqual(len(inner), 1)
        self.assertIsNone(next(iter(inner.values()))['cleanup'])
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
                  'current_governance_qualified': True, 'handoff_import_complete': True,
                  'terminal_at_completion_cut': False,
                  'accepted_commit_refs': [winning],
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

    def test_child_scopes_follow_their_native_parent_realm_handoff(self):
        parent = self.entry['effective_scope']['realm_id']
        for ordinal, kind in enumerate(['circle', 'sidecar'], 220):
            target = {'kind': kind, 'realm_id': parent,
                      kind + '_id': 'ak:' + kind + ':' + m.b64(b'\x01' + bytes([ordinal]) * 32)}
            entry = {**self.entry, 'effective_scope': target,
                     'genesis_event_ref': 'ak:event:' + m.b64(b'\x01' + bytes([ordinal + 2]) * 32)}
            f = m.fixture(self.inventory['replacement'], entry, self.inventory['pcr_cut'],
                          terminal_source_ref=self.historical['scope_cut'])
            after = f['handoff']
            with self.subTest(kind=kind):
                self.validate('content-encryption.schema.json#/$defs/recovery_scope_cleanup_self_response_body',
                              after['self_deliveries']['removed'])
                m.verify_self_retirement(after['self_deliveries']['removed'], after['authorization'], f['inventory'],
                    entry, f['reader_authority'], f['historical_completion_basis'], after['current_delivery'],
                    '2026-11-09T00:06:02.000Z')
                self.assertEqual(f['inventory']['pcr_cut'], self.inventory['pcr_cut'])
                wrong = copy.deepcopy(after['current_delivery'])
                wrong['scope_authority']['effective_scope']['realm_id'] = self.inventory['pcr_cut']['stream_ref']['realm_id']
                with self.assertRaisesRegex(ValueError, 'no exact accepted native origin'):
                    m.qualify_source(after['authorization'], f['inventory'], entry, f['reader_authority'], wrong,
                                     '2026-11-09T00:06:02.000Z')

    def test_upstream_terminal_sources_are_native_qualified_and_remain_private(self):
        target = {'kind': 'sidecar', 'realm_id': self.entry['effective_scope']['realm_id'],
                  'sidecar_id': 'ak:sidecar:' + m.b64(b'\x01' + bytes([224]) * 32)}
        entry = {**self.entry, 'effective_scope': target,
                 'genesis_event_ref': 'ak:event:' + m.b64(b'\x01' + bytes([225]) * 32)}
        upstream = copy.deepcopy(self.historical['scope_cut'])
        upstream['event_id'] = 'ak:event:' + m.b64(b'\x01' + bytes([226]) * 32)
        upstream['commit_id'] = 'ak:realm_commit:' + m.b64(b'\x01' + bytes([229]) * 32)
        f = m.fixture(self.inventory['replacement'], entry, self.inventory['pcr_cut'], terminal_source_ref=upstream)
        response = f['self_deliveries']['terminated']
        self.validate('content-encryption.schema.json#/$defs/recovery_scope_cleanup_self_response_body', response)
        proof = m.verify_self_retirement(response, f['authorization'], f['inventory'], entry, f['reader_authority'],
            f['historical_completion_basis'], f['current_delivery'], '2026-11-09T00:00:03.000Z')
        self.assertEqual(proof['scope_cut']['stream_ref'], target)
        self.assertNotEqual(upstream['stream_ref'], target)
        self.assertNotIn(upstream['event_id'], m.jcs(response).decode())
        self.assertNotIn(upstream['commit_id'], m.jcs(response).decode())
        for changed in [{'terminal_source_native_qualified': False},
                        {'terminal_source_ref': {**upstream, 'stream_position': upstream['stream_position'] + 1}}]:
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                m.verify_retirement(f['results']['terminated'], f['authorization'], f['inventory'], entry,
                                    {**f['historical_completion_basis'], **changed})
        # This byte primitive does not claim current API eligibility after a principal terminal.
        pcr_source = self.inventory['pcr_cut']
        self.assertNotEqual(m.terminal_source_digest(entry, pcr_source, f['authorization']['nonce_base64url']),
                            m.terminal_source_digest(entry, upstream, f['authorization']['nonce_base64url']))

    def test_human_controller_inventory_can_close_a_fixed_agent_pcr_endpoint(self):
        target = {'kind': 'realm', 'realm_id': 'ak:realm:' + m.b64(b'\x01' + bytes([227]) * 32)}
        entry = {**self.entry, 'effective_scope': target,
                 'genesis_event_ref': 'ak:event:' + m.b64(b'\x01' + bytes([228]) * 32)}
        f = m.fixture(self.inventory['replacement'], entry, self.inventory['pcr_cut'], scope_kind='user_managed_agent_pcr')
        self.assertNotEqual(target, f['inventory']['pcr_cut']['stream_ref'])
        self.assertEqual(f['inventory']['actor_id'], self.inventory['actor_id'])
        m.verify_self_retirement(f['self_deliveries']['removed'], f['authorization'], f['inventory'], entry,
            f['reader_authority'], f['historical_completion_basis'], f['current_delivery'], '2026-11-09T00:00:03.000Z')
        after = f['handoff']
        with self.assertRaisesRegex(ValueError, 'fixed native origin forbids governance migration'):
            m.verify_self_retirement(after['self_deliveries']['removed'], after['authorization'], f['inventory'], entry,
                f['reader_authority'], f['historical_completion_basis'], after['current_delivery'],
                '2026-11-09T00:06:02.000Z')

    def test_rejected_first_intent_stays_bound_across_entry_route_and_restart(self):
        f = self.f['combination_boundaries']['first_rejection']
        a, b = f['first_source'], f['other_source']
        inventory = f['inventory']
        self.validate('content-encryption.schema.json#/$defs/recovery_inventory', inventory)
        origin, governors, observations, outer = {}, {}, {}, {}
        for source, route in [(a, self.route), (b, f['other_route'])]:
            self.validate('content-encryption.schema.json#/$defs/recovery_scope_cleanup_authorization', source)
            m.qualify_source(source, inventory, source['inventory_entry'], self.reader, route,
                             '2026-11-09T00:00:03.000Z')
        def attempt(source, eligible):
            # A single origin CAS runs before signing/dispatch to any governor.
            m.reserve_intent(origin, source)
            return m.transport_replay(outer, 'current-subject', 'self', source, True,
                lambda: m.observe_delivery(observations, source,
                    lambda: m.settle_intent(governors, source, eligible, None)))
        with self.assertRaises(m.FirstFinalizationRejected):
            attempt(a, True)
        before = copy.deepcopy((origin, governors, observations, outer))
        origin = copy.deepcopy(origin)  # Protected-store restart; no outer-cache dependency.
        with self.assertRaisesRegex(ValueError, 'duplicate_conflict'):
            attempt(b, False)
        self.assertEqual((origin, governors, observations, outer), before)
        # A fresh governor's local table cannot authorize a changed I; the
        # origin authority prevents dispatch before any destination-side effect.
        b = {**b, 'destination_service_id': 'ak:did_core:web:another-governor.example'}
        with self.assertRaisesRegex(ValueError, 'duplicate_conflict'):
            m.reserve_intent(origin, b)
        self.assertIsNone(next(iter(origin.values()))['cleanup'])

    def test_rejected_intent_mutations_conflict_but_fresh_nonce_and_same_intent_continue(self):
        f = self.f['combination_boundaries']['first_rejection']
        a, b = f['first_source'], f['other_source']
        ledger = {}
        with self.assertRaises(m.FirstFinalizationRejected):
            m.settle_intent(ledger, a, True, None)
        changes = [ {'inventory_entry': b['inventory_entry']},
                    {'inventory_digest': 'sha256:' + '2' * 64},
                    {'replacement': {**a['replacement'], 'signature_key_base64url': m.b64(bytes([17]) * 32)}} ]
        for changed in changes:
            with self.subTest(changed=changed):
                before = copy.deepcopy(ledger)
                with self.assertRaisesRegex(ValueError, 'duplicate_conflict'):
                    m.settle_intent(ledger, {**a, **changed}, False, None)
                self.assertEqual(ledger, before)
        fresh = {**a, 'delivery_challenge_base64url': m.b64(bytes([105]) * 32)}
        self.assertEqual(m.settle_intent(ledger, fresh, False, None), {'state': 'pending'})
        other = {**b, 'nonce_base64url': m.b64(bytes([106]) * 32)}
        self.assertEqual(m.settle_intent(ledger, other, False, None), {'state': 'pending'})
        self.assertEqual(len(ledger), 2)

    def test_qualified_reservation_survives_temporary_failure_but_invalid_source_cannot_reserve(self):
        origin = {}
        for reader, now in [({**self.reader, 'episode_current': False}, '2026-11-09T00:00:03.000Z'),
                            (self.reader, self.authorization['expires_at'])]:
            with self.subTest(now=now), self.assertRaises(ValueError):
                m.qualify_source(self.authorization, self.inventory, self.entry, reader, self.route, now)
                m.reserve_intent(origin, self.authorization)
        self.assertFalse(origin)
        m.qualify_source(self.authorization, self.inventory, self.entry, self.reader, self.route,
                         '2026-11-09T00:00:03.000Z')
        m.reserve_intent(origin, self.authorization)
        before = copy.deepcopy(origin)
        with self.assertRaisesRegex(ValueError, 'revision_unavailable'):
            m.observe_delivery({}, self.authorization,
                lambda: (_ for _ in ()).throw(ValueError('revision_unavailable')))
        self.assertEqual(origin, before)

    def test_cross_destination_contenders_in_both_atomic_orders_keep_one_intent(self):
        f = self.f['combination_boundaries']['first_rejection']
        for first, second in [(f['first_source'], f['other_source']), (f['other_source'], f['first_source'])]:
            with self.subTest(first=first['inventory_entry']['effective_scope']):
                origin = {}
                m.reserve_intent(origin, first)
                before = copy.deepcopy(origin)
                with self.assertRaisesRegex(ValueError, 'duplicate_conflict'):
                    m.reserve_intent(origin, second)
                self.assertEqual(origin, before)
                self.assertEqual(len(origin), 1)

    def test_lawful_handoff_retains_rejected_reservation_before_fresh_observation(self):
        ledger = {}
        with self.assertRaises(m.FirstFinalizationRejected):
            m.settle_intent(ledger, self.authorization, True, None)
        imported = copy.deepcopy(ledger)
        after = self.f['handoff']
        m.qualify_source(after['authorization'], self.inventory, self.entry, self.reader, after['current_delivery'],
                         '2026-11-09T00:06:02.000Z')
        self.assertEqual(m.settle_intent(imported, after['authorization'], False, None), {'state': 'pending'})
        changed = {**after['authorization'], 'inventory_entry': {**self.entry, 'epoch': int(self.entry['epoch']) + 1}}
        before = copy.deepcopy(imported)
        with self.assertRaisesRegex(ValueError, 'duplicate_conflict'):
            m.settle_intent(imported, changed, False, None)
        self.assertEqual(imported, before)

    def successor_context(self, state='rekeyed', extra_predecessor=None):
        f = copy.deepcopy(self.f['combination_boundaries']['continuous_recovery'])
        if extra_predecessor is not None:
            refs = sorted(f['authorization']['predecessor_authorization_event_refs'] + [extra_predecessor])
            key = m.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(self.f['origin_signing_seed_hex']))
            # Reserve the two additional Human recovery-unit positions. This
            # branch has a distinct final authorization/cut from the base case.
            ref = 'ak:event:' + m.b64(b'\x01' + bytes([253]) * 32)
            f['inventory']['replacement']['authorization_event_ref'] = ref
            f['inventory']['authorization_event_ref'] = ref
            f['inventory']['pcr_cut'].update(event_id=ref,
                commit_id='ak:realm_commit:' + m.b64(b'\x01' + bytes([252]) * 32), stream_position=5)
            f['reader']['authorization_event_ref'] = ref
            from tools.content_history import inventory_digest
            f['authorization'] = m.sign({**f['authorization'], 'replacement': f['inventory']['replacement'],
                'inventory_digest': inventory_digest(f['inventory']), 'predecessor_authorization_event_refs': refs}, key, source=True)
            f['rekey_native']['replacement'] = f['inventory']['replacement']
            f['coverage']['supersedes_chain'][-1] = ref
            f['route']['predecessor_authorization_event_refs'] = refs
            f['historical']['authorization'] = f['authorization']
        source = f['authorization']
        m.qualify_source(source, f['inventory'], self.entry, f['reader'], f['route'],
                         '2026-11-09T00:10:03.000Z')
        old, new = m.scope_episode_identity(self.authorization), m.scope_episode_identity(source)
        row = copy.deepcopy(f['predecessor_obligation'])
        row['intent_bytes'] = bytes.fromhex(row.pop('intent_bytes_hex'))
        terminals, intents, obligations, satisfactions = {}, {}, {old: row}, {}
        blockers = {old, new}
        self.assertEqual(m.settle_retirement_for_scope(terminals, intents, self.authorization, False, None),
                         {'state': 'pending'})
        if state == 'rekeyed':
            m.complete_scope_rekey(terminals, blockers, source, f['rekeyed'], f['rekey_native'])
        elif state != 'pending':
            cleanup = f['retirement_results'][state]
            m.verify_retirement(cleanup, source, f['inventory'], self.entry, f['historical'])
            m.settle_retirement_for_scope(terminals, intents, source, False, cleanup)
            blockers.discard(new)  # Normal retirement's already qualified native terminal transaction.
        native = copy.deepcopy(f['coverage'])
        if state in {'removed', 'terminated'}:
            native['source_cleanup_digest'] = m.digest(f['retirement_results'][state])
            native['coverage_source_ref'] = f['retirement_results'][state]['retirement_proof']['scope_cut']
        if state == 'terminated':
            native.update(scope_terminal=True, terminal_irreversible=True, terminal_all_writes_blocked=True)
        return f, terminals, intents, obligations, satisfactions, blockers, native

    def custodies(self, records, native=None):
        """Fresh native-keeper model inputs, separate from the stored audit."""
        keeper = copy.deepcopy(native or self.f['combination_boundaries']['continuous_recovery']['coverage'])
        result = {}
        for identity, record in records.items():
            result[identity] = m.satisfaction_custody(record, keeper)
        return result

    def test_successor_rekey_satisfies_expired_predecessor_without_old_proof_or_reader_revival(self):
        f, terminals, intents, obligations, satisfactions, blockers, native = self.successor_context()
        source = f['authorization']
        old, new = m.scope_episode_identity(self.authorization), m.scope_episode_identity(source)
        unrelated = ('foreign-actor', 'unrelated-episode')
        blockers.add(unrelated)
        before = copy.deepcopy((terminals, intents, obligations))
        with self.assertRaises(ValueError):
            m.qualify_reader(self.inventory, {**self.reader, 'episode_current': False})
        with self.assertRaisesRegex(ValueError, 'expired'):
            m.qualify_source(self.authorization, self.inventory, self.entry, self.reader, self.route,
                             '2026-11-09T00:10:03.000Z')
        self.assertNotIn(new, blockers)
        self.assertIn(old, blockers)
        self.assertFalse(m.successor_completion_ready(terminals, obligations, satisfactions, source, [self.authorization]))
        record = m.satisfy_predecessor_obligation(terminals, obligations, satisfactions, blockers,
                                                 self.authorization, source, native)
        self.assertEqual((terminals, intents, obligations), before)
        self.assertNotIn(old, terminals)  # No fabricated E1 cleanup or ready result.
        self.assertEqual(blockers, {unrelated})
        self.assertTrue(m.successor_completion_ready(terminals, obligations, satisfactions, source,
                                                     [self.authorization], self.custodies(satisfactions)))
        self.assertFalse(m.business_send_allowed(blockers, True))
        self.assertTrue(m.business_send_allowed(set(), True))
        self.assertFalse(m.business_send_allowed(set(), False))
        restarted = copy.deepcopy(satisfactions)
        self.assertEqual(m.satisfy_predecessor_obligation(terminals, obligations, restarted, blockers,
            self.authorization, source, native, self.custodies(restarted)[old]), record)
        with self.assertRaises(ValueError):
            m.qualify_reader(self.inventory, {**self.reader, 'episode_current': False})

    def test_successor_retired_outcomes_satisfy_old_safety_only_and_terminal_never_reopens(self):
        for state in ['removed', 'terminated']:
            with self.subTest(state=state):
                f, terminals, _, obligations, records, blockers, native = self.successor_context(state)
                self.validate('content-encryption.schema.json#/$defs/scope_cleanup', f['retirement_results'][state])
                m.satisfy_predecessor_obligation(terminals, obligations, records, blockers,
                                                 self.authorization, f['authorization'], native)
                self.assertFalse(blockers)
                self.assertEqual(next(iter(records.values()))['source_state'], state)
                self.assertEqual(m.business_send_allowed(blockers, True, terminal=(state == 'terminated')),
                                 state != 'terminated')

    def test_predecessor_own_terminal_winning_first_needs_no_fabricated_satisfaction(self):
        f, terminals, _, obligations, records, blockers, native = self.successor_context('pending')
        # Model the serialized race in which E1 natively completed before its
        # replacement lost authority. E2's historical source remains separate.
        result = copy.deepcopy(f['rekeyed'])
        result['winning_commit']['stream_position'] = 18
        result['winning_commit']['event_id'] = 'ak:event:' + m.b64(b'\x01' + bytes([238]) * 32)
        result['winning_commit']['commit_id'] = 'ak:realm_commit:' + m.b64(b'\x01' + bytes([239]) * 32)
        result['root_refs'] = ['sha256:' + '2' * 64]
        result['backup_refs'] = ['ak:backup:019b0000-0000-7000-8000-000000000002']
        old_native = {**f['rekey_native'], 'replacement': self.authorization['replacement'],
                      'winning_commit': result['winning_commit'], 'accepted_commit_refs': [result['winning_commit']]}
        m.complete_scope_rekey(terminals, blockers, self.authorization, result, old_native)
        # E2's External and subsequent repair have distinct accepted cuts.
        later = copy.deepcopy(f['rekeyed'])
        later['winning_commit']['stream_position'] = 20
        later['winning_commit']['event_id'] = 'ak:event:' + m.b64(b'\x01' + bytes([247]) * 32)
        later['winning_commit']['commit_id'] = 'ak:realm_commit:' + m.b64(b'\x01' + bytes([246]) * 32)
        later_native = {**f['rekey_native'], 'winning_commit': later['winning_commit'],
                        'accepted_commit_refs': [result['winning_commit'], later['winning_commit']],
                        'epoch': f['rekey_native']['epoch'] + 2}
        self.assertNotEqual(result['winning_commit']['commit_id'], later['winning_commit']['commit_id'])
        m.complete_scope_rekey(terminals, blockers, f['authorization'], later, later_native)
        self.assertTrue(m.successor_completion_ready(terminals, obligations, records, f['authorization'],
                                                     [self.authorization]))
        before = copy.deepcopy((terminals, records, blockers))
        with self.assertRaises(ValueError):
            m.satisfy_predecessor_obligation(terminals, obligations, records, blockers,
                                             self.authorization, f['authorization'], native)
        self.assertEqual((terminals, records, blockers), before)
        self.assertFalse(records)

    def test_successor_cannot_supply_a_terminal_from_incomplete_normal_rekey(self):
        f = self.f['combination_boundaries']['continuous_recovery']
        for change in [{'accepted_rfc_complete': False}, {'current_eligible': False},
                       {'all_old_endpoints_removed': False}, {'roots_and_backups_durable': False},
                       {'epoch': int(self.entry['epoch'])}, {'replacement': self.authorization['replacement']}]:
            with self.subTest(change=change):
                terminals, blockers = {}, {m.scope_episode_identity(f['authorization'])}
                before = copy.deepcopy((terminals, blockers))
                with self.assertRaises(ValueError):
                    m.complete_scope_rekey(terminals, blockers, f['authorization'], f['rekeyed'],
                                            {**f['rekey_native'], **change})
                self.assertEqual((terminals, blockers), before)

    def test_continuous_rekey_transaction_checks_predecessor_coverage_before_terminal_publication(self):
        for valid in [False, True]:
            with self.subTest(valid=valid):
                f, terminals, _, obligations, records, blockers, native = self.successor_context('pending')
                before = copy.deepcopy((terminals, records, blockers))
                coverage = native if valid else {**native, 'closed_admission_ids': []}
                if valid:
                    self.assertEqual(m.finalize_successor_rekey(terminals, obligations, records, blockers,
                        f['authorization'], f['rekeyed'], f['rekey_native'], [(self.authorization, coverage)]), f['rekeyed'])
                    self.assertFalse(blockers)
                    self.assertTrue(m.successor_completion_ready(terminals, obligations, records,
                                                                 f['authorization'], [self.authorization], self.custodies(records)))
                else:
                    with self.assertRaises(ValueError):
                        m.finalize_successor_rekey(terminals, obligations, records, blockers,
                            f['authorization'], f['rekeyed'], f['rekey_native'], [(self.authorization, coverage)])
                    self.assertEqual((terminals, records, blockers), before)

    def test_successor_delivery_waits_for_predecessor_records_then_fresh_observation_completes(self):
        f, terminals, _, obligations, records, blockers, native = self.successor_context('removed')
        observations, outer = {}, {}
        origin = m.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(self.f['origin_signing_seed_hex']))
        governor = m.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(self.f['governor_signing_seed_hex']))
        def compute(source):
            if not m.successor_completion_ready(terminals, obligations, records, source,
                                                [self.authorization], self.custodies(records)):
                return {'delivery': {'state': 'pending'}}
            cleanup = f['retirement_results']['removed']
            proof = cleanup['retirement_proof']
            delivery = m.sign({'request_digest': m.request_digest(source), 'authorization_digest': m.digest(source),
                'proof_digest': m.digest(proof), 'recipient_service_id': f['route']['origin_service_id'],
                'governance_station_id': f['route']['governance_station_id'], 'governance_generation': 0,
                'nonce_base64url': source['nonce_base64url'],
                'delivery_challenge_base64url': source['delivery_challenge_base64url'],
                'attested_at': '2026-11-09T00:10:03.000Z', 'expires_at': source['expires_at'],
                'verification_method': f['route']['governor_verification_method']}, governor, delivery=True)
            return {'delivery': {'cleanup': cleanup, 'delivery_attestation': delivery},
                    'attestor_signing_key': {'proof_digest': m.digest(proof),
                        'verification_method': proof['verification_method'],
                        'public_key_base64url': f['historical']['governor_public_key']},
                    'delivery_signing_key': {'delivery_digest': m.digest(delivery),
                        'verification_method': delivery['verification_method'],
                        'public_key_base64url': f['route']['governor_public_key']}}
        def observe(source):
            m.qualify_source(source, f['inventory'], self.entry, f['reader'], f['route'],
                             '2026-11-09T00:10:04.000Z')
            return m.transport_replay(outer, 'origin', 'self', source, True,
                lambda: m.observe_delivery(observations, source, lambda: compute(source)))
        pending = observe(f['authorization'])
        self.validate('content-encryption.schema.json#/$defs/recovery_scope_cleanup_self_response_body', pending)
        m.satisfy_predecessor_obligation(terminals, obligations, records, blockers,
                                         self.authorization, f['authorization'], native)
        self.assertEqual(observe(f['authorization']), pending)
        fresh = m.sign({**f['authorization'], 'delivery_challenge_base64url': m.b64(bytes([108]) * 32)}, origin, source=True)
        response = observe(fresh)
        self.validate('content-encryption.schema.json#/$defs/recovery_scope_cleanup_self_response_body', response)
        self.assertEqual(m.verify_self_retirement(response, fresh, f['inventory'], self.entry, f['reader'],
            f['historical'], f['route'], '2026-11-09T00:10:04.000Z'), f['retirement_results']['removed']['retirement_proof'])

    def test_incomplete_predecessor_coverage_and_unqualified_sources_have_zero_release_effect(self):
        changes = [ {'source_native_qualified': False}, {'source_facts_durable': False},
                    {'supersedes_chain_qualified': False}, {'supersedes_chain': []},
                    {'covered_endpoint_ids': ['displaced-D1']}, {'closed_admission_ids': ['issued-claim']},
                    {'retained_fence_endpoint_ids': []}, {'all_admission_paths_closed': False},
                    {'all_old_endpoints_removed': False}, {'source_cleanup_digest': 'sha256:' + '0' * 64},
                    {'coverage_source_ref': {**self.historical['scope_cut'], 'stream_position': 999}},
                    {'genesis_event_ref': 'foreign-genesis'}, {'subject_actor_id': {'kind': 'foreign'}},
                    {'effective_scope': {'kind': 'foreign'}} ]
        for change in changes:
            with self.subTest(change=change):
                f, terminals, _, obligations, records, blockers, native = self.successor_context()
                before = copy.deepcopy((terminals, obligations, records, blockers))
                with self.assertRaises(ValueError):
                    m.satisfy_predecessor_obligation(terminals, obligations, records, blockers,
                        self.authorization, f['authorization'], {**native, **change})
                self.assertEqual((terminals, obligations, records, blockers), before)
        for flag in ['scope_terminal', 'terminal_irreversible', 'terminal_all_writes_blocked']:
            f, terminals, _, obligations, records, blockers, native = self.successor_context('terminated')
            before = copy.deepcopy((records, blockers))
            with self.assertRaises(ValueError):
                m.satisfy_predecessor_obligation(terminals, obligations, records, blockers,
                    self.authorization, f['authorization'], {**native, flag: False})
            self.assertEqual((records, blockers), before)

    def test_foreign_episode_identity_missing_obligation_and_pending_successor_never_release(self):
        f, terminals, _, obligations, records, blockers, native = self.successor_context('pending')
        before = copy.deepcopy((records, blockers))
        with self.assertRaises(ValueError):
            m.satisfy_predecessor_obligation(terminals, obligations, records, blockers,
                                             self.authorization, f['authorization'], native)
        self.assertEqual((records, blockers), before)
        f, terminals, _, obligations, records, blockers, native = self.successor_context()
        for old in [{**self.authorization, 'replacement': {**self.authorization['replacement'],
                         'actor_id': {'kind': 'foreign'}}},
                    {**self.authorization, 'inventory_entry': {**self.entry, 'genesis_event_ref': 'foreign'}},
                    f['authorization']]:
            with self.subTest(old=old), self.assertRaises(ValueError):
                m.satisfy_predecessor_obligation(terminals, obligations, records, blockers, old, f['authorization'], native)
        with self.assertRaises(ValueError):
            m.satisfy_predecessor_obligation(terminals, {}, records, blockers,
                                             self.authorization, f['authorization'], native)
        self.assertFalse(records)

    def test_multiple_predecessors_require_individual_causal_settlement_and_conflicts_preserve_first(self):
        middle = copy.deepcopy(self.authorization)
        middle['replacement']['authorization_event_ref'] = 'ak:event:' + m.b64(b'\x01' + bytes([237]) * 32)
        middle['replacement']['endpoint']['device_id'] = 'ak:device:019a0000-0000-7000-8000-000000000005'
        middle_key = m.Ed25519PrivateKey.from_private_bytes(bytes([239]) * 32)
        middle['replacement']['signature_key_base64url'] = m.b64(middle_key.public_key().public_bytes(m.Encoding.Raw, m.PublicFormat.Raw))
        origin = m.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(self.f['origin_signing_seed_hex']))
        middle = m.sign({**middle, 'predecessor_authorization_event_refs': [self.authorization['replacement']['authorization_event_ref']],
                         'attested_at': '2026-11-09T00:06:00.000Z',
                         'expires_at': '2026-11-09T00:11:00.000Z'}, origin, source=True)
        f, terminals, _, obligations, records, blockers, native = self.successor_context(
            extra_predecessor=middle['replacement']['authorization_event_ref'])
        mid_key = m.scope_episode_identity(middle)
        old_key = m.scope_episode_identity(self.authorization)
        obligations[mid_key] = {**copy.deepcopy(obligations[old_key]), 'request_digest': m.request_digest(middle),
                                'intent_bytes': m.jcs(m.request_intent(middle))}
        blockers.add(mid_key)
        native['supersedes_chain'].insert(1, middle['replacement']['authorization_event_ref'])
        m.satisfy_predecessor_obligation(terminals, obligations, records, blockers,
                                         self.authorization, f['authorization'], native)
        self.assertEqual(blockers, {mid_key})
        self.assertFalse(m.successor_completion_ready(terminals, obligations, records, f['authorization'],
                                                      [self.authorization, middle]))
        middle_native = {**native, 'supersedes_chain': native['supersedes_chain'][1:]}
        m.satisfy_predecessor_obligation(terminals, obligations, records, blockers,
                                         middle, f['authorization'], middle_native)
        self.assertFalse(blockers)
        before = copy.deepcopy((records, blockers))
        with self.assertRaisesRegex(ValueError, 'duplicate_conflict'):
            m.satisfy_predecessor_obligation(terminals, obligations, records, blockers,
                self.authorization, f['authorization'], {**native, 'supersedes_chain': [native['supersedes_chain'][0],
                                                                                      native['supersedes_chain'][-1]]})
        self.assertEqual((records, blockers), before)

    def test_machine_contract_separates_reservation_satisfaction_and_cleanup_wire_states(self):
        root = Path(m.__file__).resolve().parents[1]
        contract = json.loads((root / 'spec/v1/artifacts/registry/contract-registry.json').read_text(encoding='utf-8'))['content_encryption_contract']
        self.assertFalse(contract['retirement_idempotency']['reservation_is_scope_effect'])
        self.assertFalse(contract['retirement_idempotency']['fresh_challenge_may_change_intent'])
        self.assertEqual(contract['scope_cleanup_states'], ['rekeyed', 'removed', 'terminated'])
        self.assertEqual(contract['recovery_send_barrier']['key'][0], 'actor_id')
        satisfaction = contract['recovery_send_barrier']['predecessor_satisfaction']
        self.assertEqual(satisfaction['source_states'], contract['scope_cleanup_states'])
        self.assertIn('old_episode_read_denial', satisfaction['preserves'])
        self.assertEqual(satisfaction['prior_satisfaction']['completion_path'],
                         'verify_and_reuse_original_record_without_new_candidate_cas')

    def test_signed_causal_association_is_closed_canonical_and_cannot_be_rebound_after_rejection(self):
        f = self.f['combination_boundaries']['continuous_recovery']
        source = f['authorization']
        key = m.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(self.f['origin_signing_seed_hex']))
        missing = copy.deepcopy(source)
        missing.pop('predecessor_authorization_event_refs')
        with self.assertRaises(ValidationError):
            self.validate('content-encryption.schema.json#/$defs/recovery_scope_cleanup_authorization', missing)
        ledger = {}
        with self.assertRaises(m.FirstFinalizationRejected):
            m.settle_intent(ledger, source, True, None)
        for refs in [[], source['predecessor_authorization_event_refs'] * 2,
                     [source['replacement']['authorization_event_ref']]]:
            changed = m.sign({**source, 'predecessor_authorization_event_refs': refs,
                'delivery_challenge_base64url': m.b64(bytes([109]) * 32)}, key, source=True)
            before = copy.deepcopy(ledger)
            with self.subTest(refs=refs), self.assertRaises(ValueError):
                m.qualify_source(changed, f['inventory'], self.entry, f['reader'], f['route'],
                                 '2026-11-09T00:10:03.000Z')
            with self.assertRaisesRegex(ValueError, 'duplicate_conflict'):
                m.reserve_intent(ledger, changed)
            self.assertEqual(ledger, before)
        tampered = {**source, 'predecessor_authorization_event_refs': []}
        with self.assertRaises(InvalidSignature):
            m.verify_signature(tampered, f['route']['origin_public_key'], source=True)

    def test_missing_signed_predecessor_link_cannot_be_replaced_by_native_boolean(self):
        f, terminals, _, obligations, records, blockers, native = self.successor_context()
        before = copy.deepcopy((terminals, records, blockers))
        with self.assertRaises(ValueError):
            m.satisfy_predecessor_obligation(terminals, obligations, records, blockers, self.authorization,
                {**f['authorization'], 'predecessor_authorization_event_refs': []}, native)
        self.assertEqual((terminals, records, blockers), before)

        self.assertFalse(m.successor_completion_ready(terminals, obligations, records, f['authorization'], []))
        f, terminals, _, obligations, records, blockers, native = self.successor_context('pending')
        before = copy.deepcopy((terminals, records, blockers))
        with self.assertRaisesRegex(ValueError, 'incomplete signed predecessor census'):
            m.finalize_successor_rekey(terminals, obligations, records, blockers,
                f['authorization'], f['rekeyed'], f['rekey_native'], [])
        self.assertEqual((terminals, records, blockers), before)

    def reuse_context(self):
        f, terminals, intents, obligations, records, blockers, native = self.successor_context()
        third = copy.deepcopy(self.f['combination_boundaries']['satisfaction_reuse'])
        self.validate('content-encryption.schema.json#/$defs/recovery_inventory', third['inventory'])
        self.validate('content-encryption.schema.json#/$defs/recovery_scope_cleanup_authorization', third['authorization'])
        m.qualify_source(third['authorization'], third['inventory'], self.entry, third['reader'], third['route'],
                         '2026-11-09T00:20:03.000Z')
        bindings = {}
        with self.assertRaises(m.FirstFinalizationRejected):
            m.settle_intent(bindings, third['authorization'], True, None)
        self.assertEqual(blockers, {m.scope_episode_identity(self.authorization)})
        # A qualified normal External/repair path, not the rejected reservation,
        # installs E3's business blocker before its final completion.
        blockers.add(m.scope_episode_identity(third['authorization']))
        return f, third, terminals, intents, obligations, records, blockers, native

    def test_frozen_ancestor_reuse_converges_in_both_orders_without_rewriting_original_audit(self):
        for earlier in [True, False]:
            with self.subTest(earlier_audit=earlier):
                f, third, terminals, _, obligations, records, blockers, native = self.reuse_context()
                old = m.scope_episode_identity(self.authorization)
                unrelated = ('other-actor', 'another-episode')
                blockers.add(unrelated)
                if earlier:
                    m.satisfy_predecessor_obligation(terminals, obligations, records, blockers,
                        self.authorization, f['authorization'], native)
                original = m.jcs(records[old]) if earlier else None
                custody = self.custodies(records, third['coverage'])
                self.assertEqual(m.finalize_successor_rekey(terminals, obligations, records, blockers,
                    third['authorization'], third['rekeyed'], third['rekey_native'],
                    [(self.authorization, third['coverage'])], custody), third['rekeyed'])
                self.assertEqual(blockers, {unrelated})
                self.assertTrue(m.successor_completion_ready(terminals, obligations, records,
                    third['authorization'], [self.authorization], self.custodies(records, third['coverage'])))
                source = f['authorization'] if earlier else third['authorization']
                self.assertEqual(records[old]['successor_authorization_event_ref'], source['replacement']['authorization_event_ref'])
                if earlier:
                    self.assertEqual(m.jcs(records[old]), original)
                saved = copy.deepcopy((records, blockers))
                # A late worker reads the established completion. An explicit
                # competing write remains a genuine conflict, in either order.
                m.verify_satisfaction_record(terminals, obligations, records, self.authorization,
                    self.custodies(records, third['coverage'])[old])
                other, other_native = (third['authorization'], third['coverage']) if earlier else (f['authorization'], native)
                with self.assertRaisesRegex(ValueError, 'duplicate_conflict'):
                    m.satisfy_predecessor_obligation(terminals, obligations, records, blockers,
                        self.authorization, other, other_native)
                self.assertEqual((records, blockers), saved)
                with self.assertRaises(ValueError):
                    m.qualify_reader(f['inventory'], {**f['reader'], 'episode_current': False})

    def test_reuse_rejects_incomplete_current_custody_and_preserves_transaction(self):
        f, third, terminals, _, obligations, records, blockers, native = self.reuse_context()
        old = m.scope_episode_identity(self.authorization)
        m.satisfy_predecessor_obligation(terminals, obligations, records, blockers,
                                        self.authorization, f['authorization'], native)
        custody = self.custodies(records, third['coverage'])
        changes = [{'current_governance_qualified': False}, {'source_retention_complete': False},
                   {'handoff_import_complete': False}, {'retained_fence_endpoint_ids': []},
                   {'closed_admission_ids': []}, {'record_digest': 'sha256:' + '0' * 64},
                   {'actor_id': {'kind': 'foreign'}}, {'effective_scope': {'kind': 'foreign'}},
                   {'genesis_event_ref': 'foreign'}]
        for change in changes + [None]:
            with self.subTest(change=change):
                current = {} if change is None else {old: {**custody[old], **change}}
                before = copy.deepcopy((terminals, obligations, records, blockers))
                with self.assertRaises(ValueError):
                    m.finalize_successor_rekey(terminals, obligations, records, blockers,
                        third['authorization'], third['rekeyed'], third['rekey_native'],
                        [(self.authorization, third['coverage'])], current)
                self.assertEqual((terminals, obligations, records, blockers), before)

    def test_ready_uses_the_same_verified_reuse_gate_instead_of_record_presence(self):
        f, third, terminals, _, obligations, records, blockers, native = self.reuse_context()
        m.satisfy_predecessor_obligation(terminals, obligations, records, blockers,
                                        self.authorization, f['authorization'], native)
        m.complete_scope_rekey(terminals, blockers, third['authorization'], third['rekeyed'], third['rekey_native'])
        custody = self.custodies(records, third['coverage'])
        self.assertFalse(m.successor_completion_ready(terminals, obligations, records,
            third['authorization'], [self.authorization]))
        self.assertTrue(m.successor_completion_ready(terminals, obligations, records,
            third['authorization'], [self.authorization], custody))
        wrong = {**self.authorization, 'nonce_base64url': m.b64(bytes([117]) * 32)}
        self.assertFalse(m.successor_completion_ready(terminals, obligations, records,
            third['authorization'], [wrong], custody))

    def test_mixed_previously_fulfilled_and_pending_ancestors_complete_atomically(self):
        second = copy.deepcopy(self.f['combination_boundaries']['continuous_recovery'])
        third = copy.deepcopy(self.f['combination_boundaries']['satisfaction_reuse'])
        a1, a2 = self.authorization, second['authorization']
        refs = sorted([a1['replacement']['authorization_event_ref'], a2['replacement']['authorization_event_ref']])
        origin = m.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(self.f['origin_signing_seed_hex']))
        # This scenario freezes both pending ancestors before E3 is registered.
        third['authorization'] = m.sign({**third['authorization'], 'predecessor_authorization_event_refs': refs}, origin, source=True)
        third['route']['predecessor_authorization_event_refs'] = refs
        fourth = m.satisfaction_reuse_fixture(self.f, third, third['authorization'], third['rekeyed'],
            third['rekey_native'], third['coverage'], seed=248, ordinal=4, minute=30, predecessor_refs=refs)
        for step, now in [(third, '2026-11-09T00:20:03.000Z'), (fourth, '2026-11-09T00:30:03.000Z')]:
            self.validate('content-encryption.schema.json#/$defs/recovery_inventory', step['inventory'])
            self.validate('content-encryption.schema.json#/$defs/scope_cleanup', step['rekeyed'])
            m.qualify_source(step['authorization'], step['inventory'], self.entry, step['reader'], step['route'], now)
        k1, k2 = m.scope_episode_identity(a1), m.scope_episode_identity(a2)
        row = copy.deepcopy(second['predecessor_obligation'])
        row['intent_bytes'] = bytes.fromhex(row.pop('intent_bytes_hex'))
        obligations = {k1: row, k2: {'request_digest': m.request_digest(a2), 'intent_bytes': m.jcs(m.request_intent(a2)),
                       'endpoint_ids': ['displaced-D1'], 'admission_ids': ['inflight-outgoing']}}
        terminals, records = {}, {}
        blockers = {k1, k2, m.scope_episode_identity(third['authorization']), m.scope_episode_identity(fourth['authorization'])}
        # E2 has an accepted normal-path safety obligation but no completed
        # terminal. E3's safe cut covers both; only E1's audit is settled first.
        m.complete_scope_rekey(terminals, blockers, third['authorization'], third['rekeyed'], third['rekey_native'])
        m.satisfy_predecessor_obligation(terminals, obligations, records, blockers,
                                        a1, third['authorization'], third['coverage'])
        original = m.jcs(records[k1])
        native2 = {**fourth['coverage'], 'supersedes_chain': fourth['coverage']['supersedes_chain'][1:]}
        before = copy.deepcopy((terminals, records, blockers))
        with self.assertRaises(ValueError):
            m.finalize_successor_rekey(terminals, obligations, records, blockers,
                fourth['authorization'], fourth['rekeyed'], fourth['rekey_native'],
                [(a1, fourth['coverage']), (a2, {**native2, 'closed_admission_ids': []})],
                self.custodies(records, fourth['coverage']))
        self.assertEqual((terminals, records, blockers), before)
        m.finalize_successor_rekey(terminals, obligations, records, blockers,
            fourth['authorization'], fourth['rekeyed'], fourth['rekey_native'],
            [(a1, fourth['coverage']), (a2, native2)], self.custodies(records, fourth['coverage']))
        self.assertFalse(blockers)
        self.assertEqual(m.jcs(records[k1]), original)
        self.assertEqual(records[k2]['successor_authorization_event_ref'], fourth['authorization']['replacement']['authorization_event_ref'])
        self.assertTrue(m.successor_completion_ready(terminals, obligations, records, fourth['authorization'],
            [a1, a2], self.custodies(records, fourth['coverage'])))

    def test_reuse_reverifies_original_evidence_even_when_the_record_digest_matches(self):
        f, third, terminals, _, obligations, records, blockers, native = self.reuse_context()
        old = m.scope_episode_identity(self.authorization)
        m.satisfy_predecessor_obligation(terminals, obligations, records, blockers,
                                        self.authorization, f['authorization'], native)
        def mutate(record, kind):
            if kind == 'intent': record['predecessor_request_digest'] = 'sha256:' + '0' * 64
            if kind == 'signature': record['source_authorization']['signature']['signature'] = m.b64(bytes(64))
            if kind == 'role': record['source_native_basis']['origin_native_qualified'] = False
            if kind == 'method': record['source_native_basis']['origin_verification_method'] = 'did:web:wrong.example#key'
            if kind == 'window': record['source_native_basis']['causal_source_accepted_at'] = '2026-11-09T01:00:00.000Z'
            if kind == 'index': record['source_native_basis']['accepted_commit_refs'] = []
            if kind == 'cut': record['source_scope_cut']['stream_position'] += 1
            if kind == 'coverage': record['source_native_basis']['covered_endpoint_ids'] = []
            if kind == 'missing': record.pop('source_native_basis')
        for kind in ['intent', 'signature', 'role', 'method', 'window', 'index', 'cut', 'coverage', 'missing']:
            with self.subTest(kind=kind):
                changed = copy.deepcopy(records)
                mutate(changed[old], kind)
                # Even a matching digest cannot make false native evidence valid.
                custody = self.custodies(changed, third['coverage'])
                before = copy.deepcopy((terminals, changed, blockers))
                with self.assertRaises(ValueError):
                    m.finalize_successor_rekey(terminals, obligations, changed, blockers,
                        third['authorization'], third['rekeyed'], third['rekey_native'],
                        [(self.authorization, third['coverage'])], custody)
                self.assertEqual((terminals, changed, blockers), before)
        missing_terminal = copy.deepcopy(terminals)
        missing_terminal.pop(m.scope_episode_identity(f['authorization']))
        with self.assertRaises(ValueError):
            m.verify_satisfaction_record(missing_terminal, obligations, records, self.authorization,
                                         self.custodies(records, third['coverage'])[old])

    def test_restart_and_lawful_handoff_reuse_original_source_without_renewing_old_reader(self):
        f, third, terminals, _, obligations, records, blockers, native = self.reuse_context()
        old = m.scope_episode_identity(self.authorization)
        m.satisfy_predecessor_obligation(terminals, obligations, records, blockers,
                                        self.authorization, f['authorization'], native)
        # JSON reload models protected private rows; native identity tuple keys
        # are kept as the store index instead of exposed portable JSON keys.
        restarted = {key: json.loads(json.dumps(row)) for key, row in records.items()}
        original = m.jcs(restarted[old])
        current = self.custodies(restarted, third['coverage'])
        m.verify_satisfaction_record(terminals, obligations, restarted, self.authorization, current[old])
        after = self.f['handoff']['current_delivery']
        m.qualify_scope_governance(third['inventory'], self.entry, after)
        with self.assertRaises(ValueError):
            m.verify_satisfaction_record(terminals, obligations, restarted, self.authorization,
                {**current[old], 'handoff_import_complete': False})
        m.verify_satisfaction_record(terminals, obligations, restarted, self.authorization, current[old])
        self.assertEqual(m.jcs(restarted[old]), original)
        self.assertEqual(m.finalize_successor_rekey(terminals, obligations, restarted, blockers,
            third['authorization'], third['rekeyed'], third['rekey_native'],
            [(self.authorization, third['coverage'])], current), third['rekeyed'])
        self.assertEqual(m.jcs(restarted[old]), original)
        with self.assertRaises(ValueError):
            m.qualify_source(f['authorization'], f['inventory'], self.entry, {**f['reader'], 'episode_current': False},
                f['route'], '2026-11-09T00:20:03.000Z')

    def test_original_retirement_audits_reverify_and_terminal_lifecycle_never_reopens(self):
        for state in ['removed', 'terminated']:
            with self.subTest(state=state):
                f, terminals, _, obligations, records, blockers, native = self.successor_context(state)
                old = m.scope_episode_identity(self.authorization)
                m.satisfy_predecessor_obligation(terminals, obligations, records, blockers,
                    self.authorization, f['authorization'], native)
                custody = self.custodies(records, native)
                m.verify_satisfaction_record(terminals, obligations, records, self.authorization, custody[old])
                third = self.f['combination_boundaries']['satisfaction_reuse']
                blockers.add(m.scope_episode_identity(third['authorization']))
                before = copy.deepcopy((terminals, records, blockers))
                if state == 'terminated':
                    with self.assertRaises(ValueError):
                        m.finalize_successor_rekey(terminals, obligations, records, blockers,
                            third['authorization'], third['rekeyed'], third['rekey_native'],
                            [(self.authorization, third['coverage'])], custody)
                    self.assertEqual((terminals, records, blockers), before)
                    self.assertFalse(m.business_send_allowed(set(), True, terminal=True))
                else:
                    # Rejoin authority is an independent native premise, never
                    # derived from the old removed result or its audit.
                    m.finalize_successor_rekey(terminals, obligations, records, blockers,
                        third['authorization'], third['rekeyed'], third['rekey_native'],
                        [(self.authorization, third['coverage'])], custody)

    def test_exact_commit_ref_index_rejects_aliases_and_candidate_native_mirror_tampering(self):
        f = self.f['combination_boundaries']['continuous_recovery']
        result, native = f['rekeyed'], f['rekey_native']
        for field, value in [('event_id', self.authorization['replacement']['authorization_event_ref']),
                             ('commit_id', 'ak:realm_commit:' + m.b64(b'\x01' + bytes([255]) * 32)),
                             ('stream_position', 999), ('stream_ref', self.inventory['pcr_cut']['stream_ref'])]:
            with self.subTest(field=field):
                changed = copy.deepcopy(result)
                changed['winning_commit'][field] = value
                false_native = {**native, 'winning_commit': changed['winning_commit']}
                terminals, blockers = {}, {m.scope_episode_identity(f['authorization'])}
                before = copy.deepcopy((terminals, blockers))
                with self.assertRaises(ValueError):
                    m.complete_scope_rekey(terminals, blockers, f['authorization'], changed, false_native)
                self.assertEqual((terminals, blockers), before)
                with self.assertRaisesRegex(ValueError, 'inconsistent immutable'):
                    m.verify_exact_committed_ref(result['winning_commit'],
                        [result['winning_commit'], changed['winning_commit']])
        m.verify_exact_committed_ref(result['winning_commit'],
            [result['winning_commit'], copy.deepcopy(result['winning_commit'])])

    def test_terminal_boundary_does_not_revoke_safe_earlier_or_equal_target_cut_history(self):
        f = self.f['combination_boundaries']['continuous_recovery']
        result = f['rekeyed']
        cut = result['winning_commit']
        # Equal is possible for a derived terminal with no child tombstone;
        # the actual irreversible source is in its registered upstream stream.
        self.assertFalse(m.terminal_blocks_rekey(cut, result))
        later = {**cut, 'event_id': 'ak:event:' + m.b64(b'\x01' + bytes([248]) * 32),
                 'commit_id': 'ak:realm_commit:' + m.b64(b'\x01' + bytes([249]) * 32),
                 'stream_position': cut['stream_position'] + 1}
        self.assertFalse(m.terminal_blocks_rekey(later, result))
        self.assertTrue(m.terminal_blocks_rekey(cut, {**result, 'winning_commit': later}))
        self.assertFalse(m.business_send_allowed(set(), True, terminal=True))


if __name__ == '__main__':
    unittest.main()
