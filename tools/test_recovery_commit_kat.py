"""Adversarial cryptographic/semantic single-submit Recovery regressions."""

import copy
import unittest

from cryptography.exceptions import InvalidSignature

from tools.recovery_commit_kat import END, admit, digest, issue_completion, make_completion_request, resign_receipt, specimen


class RecoveryCommitKatTests(unittest.TestCase):
    def setUp(self):
        self.receipt, self.qualified = specimen()

    def reject(self, change_receipt=None, change_qualified=None, resign=True):
        receipt, qualified = copy.deepcopy(self.receipt), copy.deepcopy(self.qualified)
        if change_receipt:
            change_receipt(receipt)
        if change_qualified:
            change_qualified(qualified)
        if resign:
            resign_receipt(receipt)
        ledger = {}
        with self.assertRaises((ValueError, InvalidSignature, KeyError)):
            admit(receipt, qualified, ledger)
        self.assertEqual(ledger, {})

    def test_candidate_need_not_already_be_authorized(self):
        self.assertFalse(self.qualified['candidate_already_authorized'])
        result = admit(self.receipt, self.qualified, {})
        self.assertTrue(self.qualified['candidate_already_authorized'])
        refs = result['completion_attestation']
        self.assertNotEqual(refs['reanchor_event_ref']['commit_id'], refs['device_authorization_event_ref']['commit_id'])
        self.assertEqual(refs['reanchor_event_ref']['stream_position'] + 1, refs['device_authorization_event_ref']['stream_position'])

    def test_response_loss_replay_after_original_window(self):
        ledger = {}
        first = admit(self.receipt, self.qualified, ledger)
        self.qualified['now'] = END
        self.qualified['grant_active'] = False
        self.assertEqual(admit(self.receipt, self.qualified, ledger), first)
        self.assertEqual(len(ledger), 1)

    def test_same_id_changed_full_receipt_is_conflict(self):
        ledger = {}
        admit(self.receipt, self.qualified, ledger)
        changed = copy.deepcopy(self.receipt)
        changed['welcome_count'] += 1
        resign_receipt(changed)
        with self.assertRaisesRegex(ValueError, 'duplicate_conflict'):
            admit(changed, self.qualified, ledger)

    def test_known_receipt_does_not_authorize_result_read(self):
        ledger = {}
        admit(self.receipt, self.qualified, ledger)
        self.qualified['current_reader_authorized'] = False
        with self.assertRaisesRegex(ValueError, 'current_exact_result_reader'):
            admit(self.receipt, self.qualified, ledger)

    def test_wrong_candidate_signature(self):
        self.reject(lambda receipt: receipt['signature_proof'].update(signature='A' * 86), resign=False)

    def test_wrong_candidate_method(self):
        self.reject(change_qualified=lambda q: q.update(candidate_method='did:web:wrong.example#key'))

    def test_same_principal_wrong_station(self):
        self.reject(lambda r: r['account_id'].update(station_id='ak:did_core:web:other.example'))

    def test_wrong_issuer_scoped_grant_reference(self):
        self.reject(lambda r: r['session_grant_ref'].update(issuer_id='ak:did_core:web:other.example'))

    def test_wrong_jkt(self):
        self.reject(lambda r: r.update(session_grant_cnf_jkt='B' * 43))

    def test_wrong_session(self):
        self.reject(lambda r: r.update(recovery_session_id='ak:recovery_session:019ba000-0000-7000-8000-000000000099'))

    def test_wrong_policy(self):
        self.reject(lambda r: r.update(policy_version=2))

    def test_revoked_policy(self):
        self.reject(change_qualified=lambda q: q.update(policy_active=False))

    def test_unverified_session(self):
        self.reject(change_qualified=lambda q: q.update(session_verified=False))

    def test_session_already_consumed_by_other_request(self):
        self.reject(change_qualified=lambda q: q.update(session_consumed=True))

    def test_expired_before_first_acceptance(self):
        self.reject(change_qualified=lambda q: q.update(now=END))

    def test_receipt_cannot_widen_source_deadline(self):
        self.reject(lambda r: r.update(expires_at='2026-11-14T12:16:00.000Z'))

    def test_generation_advanced(self):
        self.reject(change_qualified=lambda q: q.update(current_generation=2))

    def test_non_successor_generation(self):
        self.reject(lambda r: r.update(new_model_generation_ref=3))

    def test_stale_head(self):
        self.reject(lambda r: r['recovery_unit'].update(predecessor_ref='ak:realm_commit:wrong'))

    def test_swapped_submission_slots(self):
        self.reject(lambda r: r['recovery_unit']['events'].reverse())

    def test_missing_slot(self):
        self.reject(lambda r: r['recovery_unit']['events'].pop())

    def test_changed_signed_event(self):
        self.reject(lambda r: r['recovery_unit']['events'][1]['event']['payload'].update(authorized_generation_ref=3))


class RecoveryCompletionIssuerTests(unittest.TestCase):
    def setUp(self):
        self.receipt, candidate = specimen()
        self.completion = admit(self.receipt, candidate, {})['completion_attestation']
        self.request, self.fresh = make_completion_request(self.receipt)

    def reject(self, request_change=None, input_change=None, completion_change=None):
        request, fresh, completion = copy.deepcopy(self.request), copy.deepcopy(self.fresh), copy.deepcopy(self.completion)
        if request_change:
            request_change(request)
            request['canonical_request_digest'] = digest({name: item for name, item in request.items() if name != 'canonical_request_digest'})
        if input_change:
            input_change(fresh)
        if completion_change:
            completion_change(completion)
        ledger = {}
        with self.assertRaises((ValueError, InvalidSignature, KeyError)):
            issue_completion(request, completion, fresh, ledger)
        self.assertEqual(ledger, {})
        self.assertEqual(fresh['account_state'], 'deactivated')

    def test_deactivated_after_lost_pcr_response_and_recovery_grant_expiry(self):
        request, fresh = make_completion_request(self.receipt, now='2026-11-14T12:16:00.000Z')
        self.assertLess(self.receipt['expires_at'], fresh['now'])
        self.assertNotEqual(self.receipt['session_grant_cnf_jkt'], fresh['holder_jkt'])
        outcome = issue_completion(request, self.completion, fresh, {})
        self.assertEqual(fresh['account_state'], 'active')
        self.assertEqual(outcome['transaction_id'], self.receipt['transaction_id'])

    def test_replay_keeps_original_outcome_after_body_proof_window(self):
        ledger = {}
        first = issue_completion(self.request, self.completion, self.fresh, ledger)
        self.fresh.update(now='2026-11-14T12:06:00.000Z', handoff_digest='sha256:' + '44' * 32)
        self.assertEqual(issue_completion(self.request, None, self.fresh, ledger), first)
        self.assertEqual(len(ledger), 1)

    def test_only_old_receipt_without_fresh_device_proof_is_insufficient(self):
        self.reject(lambda request: request['accepted_device_possession_proof'].update(signature='A' * 86))

    def test_new_holder_not_authorized_by_device(self):
        self.reject(input_change=lambda fresh: fresh.update(holder_jkt='A' * 43))

    def test_changed_completion_intent_invalidates_original_device_proof(self):
        self.reject(lambda request: request['initial_session'].update(audience_id='ak:did_core:web:other.example'))

    def test_wrong_handoff_cannot_use_current_proof(self):
        self.reject(input_change=lambda fresh: fresh.update(handoff_digest='sha256:' + '55' * 32))

    def test_unaccepted_pcr_result_does_not_issue(self):
        with self.assertRaisesRegex(ValueError, 'native_completion_unavailable'):
            issue_completion(self.request, None, self.fresh, {})
        self.assertEqual(self.fresh['account_state'], 'deactivated')

    def test_wrong_native_signature(self):
        self.reject(completion_change=lambda c: c['signature_proof'].update(signature='A' * 86))

    def test_replaced_generation_does_not_restore_current_rights(self):
        self.reject(input_change=lambda fresh: fresh.update(current_generation=3))

    def test_current_device_revocation_blocks_completion(self):
        self.reject(input_change=lambda fresh: fresh.update(current_device_active=False))

    def test_same_transaction_changed_request_id_cannot_issue_twice(self):
        ledger = {}
        issue_completion(self.request, self.completion, self.fresh, ledger)
        changed = copy.deepcopy(self.request)
        changed['accepted_device_possession_proof']['request_id'] = 'ak:request:019ba000-0000-7000-8000-000000000099'
        changed['canonical_request_digest'] = digest({name: item for name, item in changed.items() if name != 'canonical_request_digest'})
        with self.assertRaisesRegex(ValueError, 'duplicate_conflict'):
            issue_completion(changed, self.completion, self.fresh, ledger)
        self.assertEqual(len(ledger), 1)

    def test_terminal_issuer_successor_is_not_reissued(self):
        ledger = {}
        issue_completion(self.request, self.completion, self.fresh, ledger)
        next(iter(ledger.values()))['state'] = 'superseded'
        with self.assertRaisesRegex(ValueError, 'session_grant_replay_terminal'):
            issue_completion(self.request, None, self.fresh, ledger)

    def test_expired_issuer_successor_is_not_reissued(self):
        ledger = {}
        issue_completion(self.request, self.completion, self.fresh, ledger)
        self.fresh['now'] = '2026-11-14T13:00:00.000Z'
        with self.assertRaisesRegex(ValueError, 'session_grant_replay_expired'):
            issue_completion(self.request, None, self.fresh, ledger)


if __name__ == '__main__':
    unittest.main()
