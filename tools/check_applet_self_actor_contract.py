#!/usr/bin/env python3
"""Executable contract models and transcript KATs, not a live Station certification."""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import sys
from pathlib import Path
import unittest

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from tools.check_applet_delivery_authentication_kat import jcs_text

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'spec/v1/artifacts'
FIXTURE = ART / 'fixtures/applet-self-actor-fixture.json'


def verify_projection(case, host=None, context=None):
    """Check the registered detached signature algorithm, without resolving authority."""
    host = copy.deepcopy(case['host_object'] if host is None else host)
    signature = host.pop('signature')
    expected = case['context'] if context is None else context
    digest = 'sha256:' + hashlib.sha256(jcs_text(host).encode()).hexdigest()
    if signature['context'] != expected or signature['signed_digest'] != digest:
        return False
    envelope = {key: value for key, value in signature.items() if key != 'sig'}
    preimage = (expected + '\n' + jcs_text(envelope)).encode()
    try:
        key = Ed25519PublicKey.from_public_bytes(base64.urlsafe_b64decode(case['public_key_b64u'] + '='))
        key.verify(base64.urlsafe_b64decode(signature['sig'] + '=='), preimage)
    except (ValueError, InvalidSignature):
        return False
    return True


def live_aligned(state):
    """Observable R1 rule; each input is already verified role-specific material."""
    return (
        state['method'] == 'did:webvh'
        and state['service'] == state['account_principal']
        and state['controller'] != state['service']
        and state['epoch_version'] == state['pcr_version']
        and state['epoch_document'] == state['pcr_document']
        and state['epoch_key'] == state['pcr_key']
        and state['grant_epoch'] == state['epoch']
        and state['active'] and not state['revoked']
    )


class BootstrapLedger:
    """Reference state machine: no cryptographic authentication or SUT storage claims."""
    def __init__(self, selector):
        self.selector = selector
        self.state = 'pending'
        self.bundle = None
        self.effects = 0

    def claim(self, selector, business=False):
        if selector != self.selector or business:
            return 'permission_denied'
        return self.state

    def submit(self, bundle):
        if self.state not in ('pending', 'authored'):
            return 'closed'
        if self.bundle is not None and self.bundle != bundle:
            return 'duplicate_conflict'
        self.bundle = copy.deepcopy(bundle)
        self.state = 'authored'
        return 'authored'

    def commit(self, administrator):
        if not administrator:
            return 'permission_denied'
        if self.state == 'committed':
            return 'committed'
        if self.state != 'authored':
            return 'closed'
        self.state = 'committed'
        self.effects += 1
        return 'committed'

    def close(self, state):
        if self.state == 'committed':
            return 'closed'
        if self.state in ('expired', 'cancelled', 'superseded'):
            return self.state
        self.state = state
        return self.state


class AppletSelfActorContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURE.read_text(encoding='utf8'))
        cls.documents = {p.name: json.loads(p.read_text(encoding='utf8')) for p in (ART/'schemas').glob('*.json')}
        cls.registry = Registry().with_resources((doc['$id'], Resource.from_contents(doc)) for doc in cls.documents.values())

    def validator(self, file, definition=None):
        ref = 'https://arkret.org/v1/schemas/' + file
        if definition: ref += '#/$defs/' + definition
        return Draft202012Validator({'$ref': ref}, registry=self.registry)

    def test_bootstrap_schema_cannot_carry_business_selector_or_bearer(self):
        value = self.fixture['bootstrap_claim']
        validator = self.validator('applet-client-operations.schema.json')
        validator.validate(value)
        for field in ('registration_epoch', 'authoring_request_digest', 'applet_id'):
            altered = copy.deepcopy(value); altered.pop(field)
            self.assertFalse(validator.is_valid(altered))
        for field in ('session_grant', 'bearer', 'realm_id', 'task', 'grant_refs'):
            self.assertFalse(validator.is_valid({**value, field: 'unapproved'}))

    def test_transport_choices_are_mutually_exclusive(self):
        transcript = json.loads((ART/'fixtures/applet-registration-epoch-fixture.json').read_text(encoding='utf8'))['positive']['transcript']
        validator = self.validator('applet-registration-epoch-transcript.schema.json')
        validator.validate(transcript)
        pull = copy.deepcopy(transcript)
        pull['derived_registration']['transport'] = {'kind':'client_pull'}
        pull['derived_registration'].pop('base_url')
        pull['endpoint_policy']['endpoints'] = []
        validator.validate(pull)
        altered = copy.deepcopy(pull); altered['derived_registration']['base_url'] = 'https://unused.example'
        self.assertFalse(validator.is_valid(altered))
        altered = copy.deepcopy(pull); altered['derived_registration']['receive_signals'] = True
        self.assertFalse(validator.is_valid(altered))
        altered = copy.deepcopy(transcript); altered['endpoint_policy']['endpoints'] = []
        self.assertFalse(validator.is_valid(altered))
        altered = copy.deepcopy(pull); altered['derived_registration']['transport']['kind'] = 'agent_session'
        self.assertFalse(validator.is_valid(altered))

    def test_r1_service_first_pcr_first_and_key_document_mismatch(self):
        state = self.fixture['aligned_state']
        self.assertTrue(live_aligned(state))
        for key in ('method','account_principal','epoch_version','pcr_version','pcr_document','pcr_key','grant_epoch'):
            altered = copy.deepcopy(state); altered[key] = 'wrong'
            self.assertFalse(live_aligned(altered), key)
        self.assertFalse(live_aligned({**state,'controller':state['service']}))
        self.assertFalse(live_aligned({**state,'revoked':True}))

    def test_r1_exact_station_updates_do_not_update_another_account(self):
        first = copy.deepcopy(self.fixture['aligned_state'])
        second = copy.deepcopy(first)
        first.update(epoch='new',grant_epoch='new',epoch_version='v2',pcr_version='v2')
        self.assertTrue(live_aligned(first))
        self.assertEqual(second['pcr_version'],'v1')
        second['epoch_version'] = 'v2'
        self.assertFalse(live_aligned(second))

    def test_r2_no_active_install_bootstrap_then_explicit_commit_exact_retry(self):
        selector = ('service','station','epoch','digest')
        ledger = BootstrapLedger(selector)
        self.assertEqual(ledger.claim(selector),'pending')
        self.assertEqual(ledger.claim(selector,business=True),'permission_denied')
        for index in range(4):
            wrong = list(selector); wrong[index] = 'wrong'
            self.assertEqual(ledger.claim(tuple(wrong)),'permission_denied')
        self.assertEqual(ledger.submit({'events':[1,2,3,4]}),'authored')
        self.assertEqual(ledger.effects,0)
        self.assertEqual(ledger.commit(False),'permission_denied')
        restarted = copy.deepcopy(ledger)
        self.assertEqual(restarted.submit({'events':[1,2,3,4]}),'authored')
        self.assertEqual(restarted.submit({'events':[4,3,2,1]}),'duplicate_conflict')
        self.assertEqual(restarted.commit(True),'committed')
        self.assertEqual(restarted.commit(True),'committed')
        self.assertEqual(restarted.effects,1)
        self.assertEqual(restarted.close('cancelled'),'closed')

    def test_r2_cancel_expiry_supersede_are_terminal_zero_effects(self):
        for state in ('cancelled','expired','superseded'):
            ledger = BootstrapLedger(('own',))
            self.assertEqual(ledger.close(state),state)
            self.assertEqual(ledger.submit({'events':[]}),'closed')
            self.assertEqual(ledger.commit(True),'closed')
            self.assertEqual(ledger.effects,0)

    def test_plaintext_transcripts_detect_body_target_install_epoch_replay(self):
        for name, case in self.fixture['signature_kats'].items():
            self.assertTrue(verify_projection(case), name)
            envelope = {key:value for key,value in case['host_object']['signature'].items() if key != 'sig'}
            self.assertEqual((case['context'] + '\n' + jcs_text(envelope)).encode().hex(), case['signing_bytes_hex'])
            for key in ('body','registration_epoch','registration_ref','applet_actor_id'):
                altered = copy.deepcopy(case['host_object']); altered[key] = 'tampered'
                self.assertFalse(verify_projection(case, altered), key)
            self.assertFalse(verify_projection(case, context='ak.realm_commit_signature.v1'))
            altered = copy.deepcopy(case['host_object']); altered['signature']['sig'] = 'A'*86
            self.assertFalse(verify_projection(case, altered))

    def test_content_schema_requires_distinct_device_and_principal_evidence(self):
        definitions = self.documents['content-block-applet.schema.json']['$defs']
        invocation = definitions['invocation']; result = definitions['execution_outcome']
        self.assertIn('signer_evidence', invocation['required'])
        self.assertIn('signature', invocation['required'])
        self.assertIn('managed_actor_principal_signer_evidence', result['properties']['signer_evidence']['$ref'])
        self.assertEqual(invocation['properties']['signer_evidence']['$ref'],'./account-device-signer-evidence.schema.json')
        principal = self.documents['applet-edge-operations.schema.json']['$defs']['managed_actor_principal_signer_evidence']
        self.assertEqual(set(principal['required']), {'signer_resolution_evidence_ref','authenticated_signer_evidence','attester_signer_evidence'})
        self.assertFalse(principal['additionalProperties'])

    def test_attachment_reuses_registered_aead_and_never_exports_group_state(self):
        attachment = self.documents['content-block-applet.schema.json']['$defs']['disclosed_attachment']
        self.assertEqual(attachment['properties']['attachment']['$ref'],'./blob.schema.json#/$defs/encrypted_attachment')
        self.assertEqual(set(attachment['properties']),{'source_blob_ref','attachment'})
        self.assertFalse(attachment['additionalProperties'])

    def test_relay_does_not_claim_ciphertext_plaintext_equivalence(self):
        relay = self.documents['content-block-applet.schema.json']['$defs']['relay']
        self.assertEqual(relay['properties']['verification_scope']['const'],'relay_disclosure')
        for field in ('invocation_content','result_content','invocation_event','result_event','invocation_commit','result_commit'):
            self.assertIn(field,relay['required'])
        self.assertNotIn('executed_by',relay['properties'])

    def test_profile_branch_operations_are_closed_and_directions_match_transport(self):
        profile = json.loads((ART/'profiles/conformance-profiles.json').read_text(encoding='utf8'))['profile_requirements']['ak.profile.applet_service.v1']
        branches = profile['additional_requirements']['operation_requirements_by_transport']
        self.assertEqual(set(branches),{'selector','https_push','client_pull'})
        self.assertEqual(branches['selector'],'/transport/kind')
        operations = json.loads((ART/'registry/contract-registry.json').read_text(encoding='utf8'))['operation_registry']['operations']
        known = {row['operation_id'] for row in operations}
        for kind in ('https_push','client_pull'):
            self.assertTrue(branches[kind])
            for row in branches[kind]:
                self.assertEqual(set(row),{'direction','operation_id','binding_kind'})
                self.assertIn(row['operation_id'],known)
                self.assertEqual(row['binding_kind'],'http_json')
                self.assertEqual(row['direction'],'provide' if kind=='https_push' else 'consume')


if __name__ == '__main__':
    if '--report-json' in sys.argv:
        class RecordedResult(unittest.TextTestResult):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.passed = []

            def addSuccess(self, test):
                self.passed.append(test._testMethodName)
                super().addSuccess(test)

        suite = unittest.defaultTestLoader.loadTestsFromTestCase(AppletSelfActorContractTests)
        result = unittest.TextTestRunner(stream=sys.stderr, resultclass=RecordedResult).run(suite)
        print(json.dumps({'passed':result.passed,'successful':result.wasSuccessful()}))
        raise SystemExit(0 if result.wasSuccessful() else 1)
    unittest.main(verbosity=2)
