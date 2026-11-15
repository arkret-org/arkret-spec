"""Owner-transfer byte/reference gates, separate from native source admission."""
import copy
import hashlib
import json
from pathlib import Path
import unittest

from cryptography.exceptions import InvalidSignature
from tools.artifact_lint.call_current import verify_producer, schema_validator
from tools.artifact_lint.proof_context_schemas import (
    validate_owner_transfer_reference, run_owner_transfer_case, validate_owner_transfer_transport_reference,
    check_detached_object_signature_registration,
)
from tools.artifact_lint.core import Lint
from tools.regenerate_detached_object_signature_kat import (
    owner_transfer_fixture, owner_transfer_intent, sign_owner_transfer_event,
    OWNER_TRANSFER_CASES, jcs,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / 'spec/v1/artifacts/schemas'


class OwnerTransferAcceptance(unittest.TestCase):
    def setUp(self):
        self.sample = owner_transfer_fixture()

    def test_real_independent_signatures_and_registered_contract(self):
        lint = Lint()
        check_detached_object_signature_registration(lint)
        self.assertEqual(lint.errors, [])
        intent = validate_owner_transfer_reference(self.sample)
        self.assertEqual(intent, self.sample['unsigned_projection'])
        self.assertNotEqual(self.sample['public_key_base64url'], self.sample['outer_signer_basis']['public_key_base64url'])

    def test_finite_intent_has_no_signature_or_event_id_cycle(self):
        intent = owner_transfer_intent(self.sample['event'])
        self.assertEqual(set(intent), {'scope_ref', 'actor_id', 'payload_without_successor_acceptance'})
        self.assertEqual(set(intent['payload_without_successor_acceptance']), {'realm_id', 'expected_state_digest', 'patch'})
        self.assertEqual(self.sample['acceptance']['signed_digest'], 'sha256:' + hashlib.sha256(jcs(intent)).hexdigest())
        validator = schema_validator(SCHEMAS/'event-payload.schema.json', '#/$defs/realm_owner_transfer_acceptance_transcript')
        for key in ('event_id', 'producer_proof', 'successor_acceptance', 'controller_epoch', 'nonce'):
            changed = copy.deepcopy(intent)
            changed[key] = 'not an intent member'
            self.assertFalse(validator.is_valid(changed))

    def test_signed_current_controller_cannot_change_successor_intent(self):
        sample = copy.deepcopy(self.sample)
        sample['prestate_root']['controller_epoch'] += 1
        sample['event']['payload']['expected_state_digest'] = 'sha256:' + hashlib.sha256(jcs(sample['prestate_root'])).hexdigest()
        sample['event'] = sign_owner_transfer_event(sample['event'])
        verify_producer(sample['event'], sample['outer_signer_basis']['public_key_base64url'])
        with self.assertRaisesRegex(ValueError, 'independent intent commitment'):
            validate_owner_transfer_reference(sample)

    def test_wrong_successor_key_is_a_real_ed25519_rejection(self):
        sample = copy.deepcopy(self.sample)
        sample['successor_source']['public_key_base64url'] = sample['outer_signer_basis']['public_key_base64url']
        with self.assertRaises(InvalidSignature):
            validate_owner_transfer_reference(sample)

    def test_scope_omission_and_finite_explicit_purpose_are_distinct(self):
        self.assertEqual(run_owner_transfer_case(self.sample, 'scope_omitted'), 'accept')
        for name in ('scope_empty', 'scope_unknown', 'scope_wildcard', 'scope_null'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'key purpose ceiling'):
                run_owner_transfer_case(self.sample, name)

    def test_raw_payload_null_and_legacy_open_signatures_are_rejected(self):
        validator = schema_validator(SCHEMAS/'event-payload.schema.json', '#/$defs/realm_owner_transfer_payload')
        for value in (None, 'yes', {'signature': 'anything'}, {}):
            payload = copy.deepcopy(self.sample['event']['payload'])
            payload['successor_acceptance'] = value
            self.assertFalse(validator.is_valid(payload))
        device = json.loads((SCHEMAS/'event-payload.schema.json').read_text(encoding='utf-8'))['$defs']['device_authorize_payload']['properties']['scopes']
        self.assertNotIn('null', device.get('type', []))
        self.assertFalse(schema_validator(SCHEMAS/'event-payload.schema.json', '#/$defs/device_authorize_payload/properties/scopes').is_valid(None))

    def test_new_root_targets_must_have_an_operable_native_source(self):
        for name in ('owned_agent_root', 'service_root', 'realm_actor_root'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'unsupported or mismatched'):
                run_owner_transfer_case(self.sample, name)

    def test_current_source_and_cas_mutation_matrix_is_closed(self):
        for name, expected in OWNER_TRANSFER_CASES:
            with self.subTest(name=name):
                try: actual = run_owner_transfer_case(self.sample, name)
                except (ValueError, KeyError, TypeError, InvalidSignature): actual = 'reject'
                self.assertEqual(actual, expected)
        self.assertEqual(len(OWNER_TRANSFER_CASES), 33)

    def test_current_key_does_not_authorize_a_signature_before_its_original_window(self):
        with self.assertRaisesRegex(ValueError, 'signature outside original Device window'):
            run_owner_transfer_case(self.sample, 'acceptance_before_device_window')


    def test_fresh_source_changes_http_bytes_but_never_the_signed_intent(self):
        transport=self.sample['transport']
        stable=lambda body:{k:v for k,v in body.items() if k not in ('producer_device_evidence','successor_device_evidence')}
        self.assertEqual(stable(transport['forward_body']),stable(transport['fresh_forward_body']))
        self.assertEqual(transport['stable_business_digest'],'sha256:'+hashlib.sha256(jcs(stable(transport['forward_body']))).hexdigest())
        self.assertNotEqual(transport['full_http_body_digest'],transport['fresh_full_http_body_digest'])
        for body in (transport['forward_body'],transport['fresh_forward_body']):
            self.assertEqual(body['event_submission']['event'],self.sample['event'])
            self.assertEqual(body['event_submission']['event']['payload']['successor_acceptance'],self.sample['acceptance'])
        validate_owner_transfer_transport_reference(self.sample)
        self.assertNotIn('scopes',transport['evidence']['device_projection_attestation']['attestation'])

    def test_final_deadline_rejects_old_source_and_accepts_refetched_original_intent(self):
        transport=self.sample['transport']
        with self.assertRaisesRegex(ValueError,'final current observation deadline'):
            validate_owner_transfer_transport_reference(self.sample,at='2026-09-20T00:00:30.000Z')
        validate_owner_transfer_transport_reference(self.sample,transport['fresh_evidence'],transport['fresh_evidence_ref'],'2026-09-20T00:00:30.000Z')
        with self.assertRaisesRegex(ValueError,'final current observation deadline'):
            validate_owner_transfer_transport_reference(self.sample,transport['fresh_evidence'],transport['fresh_evidence_ref'],'2026-09-20T00:00:31.000Z')

    def test_real_fresh_c_signature_cannot_be_used_before_its_observation(self):
        transport=self.sample['transport']
        with self.assertRaisesRegex(ValueError,'final current observation deadline'):
            validate_owner_transfer_transport_reference(self.sample,transport['fresh_evidence'],transport['fresh_evidence_ref'],'2026-09-20T00:00:00.000Z')

    def test_original_candidate_and_final_admission_time_must_both_fit_the_same_witness(self):
        transport=self.sample['transport']
        for committed in ('2026-09-20T00:00:00.000Z','2026-09-20T00:00:31.000Z'):
            with self.subTest(committed=committed), self.assertRaisesRegex(ValueError,'final current observation deadline'):
                validate_owner_transfer_transport_reference(self.sample,transport['fresh_evidence'],transport['fresh_evidence_ref'],'2026-09-20T00:00:30.000Z',committed)

    def test_unchanged_c_signature_does_not_make_different_resolution_wrappers_same_ref(self):
        transport=self.sample['transport']
        self.assertEqual(transport['origin_wrapper']['device_projection_attestation'],transport['evidence']['device_projection_attestation'])
        self.assertNotEqual(transport['origin_wrapper']['service_resolution'],transport['evidence']['service_resolution'])
        self.assertNotEqual(transport['peer_row_signer_evidence_ref'],transport['evidence_ref'])
        with self.assertRaisesRegex(ValueError,'full wrapper reference'):
            validate_owner_transfer_transport_reference(self.sample,evidence_ref=transport['peer_row_signer_evidence_ref'])
        archive=transport['archive_input_coordinates']
        self.assertEqual(archive['successor_evidence_ref'],transport['evidence_ref'])
        self.assertNotEqual(archive['successor_evidence_ref'],transport['fresh_evidence_ref'])

    def test_actual_origin_signature_is_verified_and_intent_digest_is_not_a_bool(self):
        sample=copy.deepcopy(self.sample)
        evidence=sample['transport']['evidence']
        proof=evidence['device_projection_attestation']['proof']
        text=proof['jws']
        proof['jws']=text[:-4]+('A' if text[-4]!='A' else 'B')+text[-3:]
        ref='ak:signer_evidence:sha256:'+hashlib.sha256(jcs(evidence)).hexdigest()
        with self.assertRaises(InvalidSignature):
            validate_owner_transfer_transport_reference(sample,evidence,ref)
        sample=copy.deepcopy(self.sample)
        evidence=sample['transport']['evidence']
        evidence['device_projection_attestation']['attestation']['owner_transfer_acceptance_intent_digest']='sha256:'+'0'*64
        ref='ak:signer_evidence:sha256:'+hashlib.sha256(jcs(evidence)).hexdigest()
        with self.assertRaisesRegex(ValueError,'C exact source/intent binding'):
            validate_owner_transfer_transport_reference(sample,evidence,ref)

    def test_query_purpose_is_finite_and_never_a_contact_or_realm_requester(self):
        validator=schema_validator(SCHEMAS/'keys-operations.schema.json','#/$defs/peer_keys_query_request_body')
        query=self.sample['transport']['query']
        self.assertTrue(validator.is_valid(query),list(validator.iter_errors(query)))
        mutations=[]
        changed=copy.deepcopy(query);changed.pop('owner_transfer_acceptance');mutations.append(changed)
        changed=copy.deepcopy(query);changed['purpose']='call_media';mutations.append(changed)
        changed=copy.deepcopy(query);changed['relationship_basis']={'kind':'contact'};mutations.append(changed)
        changed=copy.deepcopy(query);changed['device_keys'][0]['device_ids'].append('ak:device:0199bbbb-bbbb-7bbb-8bbb-bbbbbbbbbbbc');mutations.append(changed)
        changed=copy.deepcopy(query);changed['device_keys'].append(copy.deepcopy(changed['device_keys'][0]));mutations.append(changed)
        for changed in mutations:self.assertFalse(validator.is_valid(changed))

    def test_only_owner_transfer_single_forward_can_carry_successor_evidence(self):
        raw=json.loads((SCHEMAS/'authority-commit-operations.schema.json').read_text(encoding='utf-8'))
        index=len(raw['$defs']['peer_submit_request_body']['allOf'])-1
        guard=schema_validator(SCHEMAS/'authority-commit-operations.schema.json','#/$defs/peer_submit_request_body/allOf/'+str(index))
        ordinary={'branch':'authority_forward','event_submission':{'event':{'kind':'ak.call.state'}}}
        self.assertTrue(guard.is_valid(ordinary))
        ordinary['successor_device_evidence']={}
        self.assertFalse(guard.is_valid(ordinary))
        transfer={'branch':'authority_forward','event_submission':{'event':{'kind':'ak.realm.owner.transfer'}}}
        self.assertFalse(guard.is_valid(transfer))
        transfer['successor_device_evidence']={}
        self.assertTrue(guard.is_valid(transfer))
        for branch in ('registered_atomic_unit','committed_replication'):
            self.assertFalse(guard.is_valid({'branch':branch,'successor_device_evidence':{}}))


if __name__ == '__main__':
    unittest.main()
