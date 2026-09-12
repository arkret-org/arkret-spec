"""Quorum read-conclusion schema and adversarial signature vectors.

This is a consumer reference model, not a production PBFT implementation.
It verifies attestation authority and binding; it deliberately does not replay
the state machine whose facts the configured quorum attests.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.exceptions import InvalidSignature
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from tools.artifact_lint.core import canonical_json as canonical_text

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / 'spec/v1/artifacts'
CONTEXT = 'ak.seal.conclusion.v1'
HANDOFF = 'ak.seal.configuration_handoff.v1'
REALM = 'ak:realm:' + base64.urlsafe_b64encode(b'\x01' + b'\x11' * 32).decode()
CONFIG = 'ak:event:' + base64.urlsafe_b64encode(b'\x01' + b'\x22' * 32).decode()
TARGET = 'ak:seal:sha256:' + '3' * 64
CELL = 'ak:cell:ak.component.member.state.v1:bob'


def canonical_json(value):
    return canonical_text(value).encode('utf-8')


def b64(value):
    return base64.urlsafe_b64encode(value).decode().rstrip('=')


def unb64(value):
    return base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))


def sign(statement, keys, context=CONTEXT):
    payload = canonical_json({'context': context, 'statement': statement})
    signatures = []
    for method, key in sorted(keys.items()):
        header = b64(canonical_json({'alg': 'Ed25519', 'kid': method}))
        encoded = b64(payload)
        message = (header + '.' + encoded).encode()
        signatures.append({'verification_method': method,
                           'payload_digest': 'sha256:' + hashlib.sha256(payload).hexdigest(),
                           'jws': message.decode() + '.' + b64(key.sign(message))})
    return {'statement': copy.deepcopy(statement), 'signatures': signatures}


def verify_signatures(certificate, keys, expected_config, realm, context=CONTEXT):
    statement = certificate['statement']
    if statement['realm_id'] != realm or statement['configuration_ref'] != expected_config:
        raise ValueError('authority binding')
    n = len(keys)
    if (n - 1) % 3:
        raise ValueError('configuration size')
    signatures = certificate['signatures']
    methods = [s['verification_method'] for s in signatures]
    if len(methods) != 2 * ((n - 1) // 3) + 1 or methods != sorted(set(methods)):
        raise ValueError('quorum')
    payload = canonical_json({'context': context, 'statement': statement})
    for signature in signatures:
        method = signature['verification_method']
        if method not in keys or signature['payload_digest'] != 'sha256:' + hashlib.sha256(payload).hexdigest():
            raise ValueError('signer or payload')
        protected, encoded, raw_signature = signature['jws'].split('.')
        if protected != b64(canonical_json({'alg': 'Ed25519', 'kid': method})) or encoded != b64(payload):
            raise ValueError('canonical transcript')
        keys[method].public_key().verify(unb64(raw_signature), (protected + '.' + encoded).encode())


def verify_query(certificate, query, keys, expected_config=CONFIG, realm=REALM):
    verify_signatures(certificate, keys, expected_config, realm)
    statement = certificate['statement']
    if statement['target_seal_ref'] != query['target_seal_ref']:
        raise ValueError('target')
    selectors = query['selectors']
    if [canonical_json(s) for s in selectors] != sorted(set(canonical_json(s) for s in selectors)):
        raise ValueError('selector order')
    if [r['selector'] for r in statement['results']] != selectors:
        raise ValueError('query coverage')
    for result in statement['results']:
        selector = result['selector']
        if selector['kind'] == 'cell_range':
            lower, upper = selector['lower_cell_id'], selector['upper_cell_id']
            ids = [c['cell_id'] for c in result['cells']]
            if lower >= upper or ids != sorted(set(ids)) or any(not lower <= c < upper for c in ids):
                raise ValueError('range binding')


class SealConclusionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        resources = []
        for path in (ARTIFACTS / 'schemas').glob('*.json'):
            value = json.loads(path.read_text(encoding='utf-8'))
            if '$id' in value:
                resources.append((value['$id'], Resource.from_contents(value)))
        cls.registry = Registry().with_resources(resources)

    def setUp(self):
        self.keys = {f'did:web:notary{i}.example#seal': Ed25519PrivateKey.from_private_bytes(bytes([i+1])*32)
                     for i in range(4)}
        self.voters = dict(list(self.keys.items())[:3])
        self.query = {'target_seal_ref': TARGET, 'selectors': [{'kind': 'cell', 'cell_id': CELL}]}
        self.statement = {'realm_id': REALM, 'configuration_ref': CONFIG, 'authority_seal_ref': TARGET,
                          'target_seal_ref': TARGET, 'results': [{'selector': self.query['selectors'][0], 'state': None}]}
        self.certificate = sign(self.statement, self.voters)

    def valid(self, fragment, instance, expected=True, file='seal-conclusion.schema.json'):
        validator = Draft202012Validator({'$ref': 'https://arkret.org/v1/schemas/' + file + fragment}, registry=self.registry)
        errors = list(validator.iter_errors(instance))
        self.assertEqual(not errors, expected, [e.message for e in errors][:5])

    def test_private_circle_absence_without_history_or_neighbors(self):
        private_history = [{'scope': 'private_circle', 'member': 'secret_member', 'command': 'remove'}]
        self.valid('#/$defs/certificate', self.certificate)
        verify_query(self.certificate, self.query, self.keys)
        wire = canonical_json(self.certificate)
        for value in private_history[0].values():
            self.assertNotIn(value.encode(), wire)
        self.assertNotIn(b'neighbor', wire)

    def test_written_null_is_not_absence(self):
        statement = copy.deepcopy(self.statement)
        statement['results'][0]['state'] = {'revision_event_id': CONFIG, 'value': None}
        cert = sign(statement, self.voters)
        self.valid('#/$defs/certificate', cert)
        verify_query(cert, self.query, self.keys)
        self.assertNotEqual(cert['statement']['results'][0]['state'], None)
        statement['results'][0]['state'].pop('revision_event_id')
        self.valid('#/$defs/certificate', sign(statement, self.voters), False)

    def test_unknown_fact_and_extra_state_fields_rejected(self):
        bad = copy.deepcopy(self.certificate)
        bad['statement']['results'][0]['selector']['kind'] = 'allow_everything'
        self.valid('#/$defs/certificate', bad, False)
        bad = copy.deepcopy(self.certificate)
        bad['statement']['latest'] = True
        self.valid('#/$defs/certificate', bad, False)

    def test_single_voter_does_not_replace_quorum(self):
        with self.assertRaises(ValueError):
            verify_query(sign(self.statement, dict(list(self.keys.items())[:1])), self.query, self.keys)

    def test_f_zero_uses_same_structure(self):
        one = dict(list(self.keys.items())[:1])
        verify_query(sign(self.statement, one), self.query, one)

    def test_duplicate_voter_rejected(self):
        cert = copy.deepcopy(self.certificate)
        cert['signatures'][2] = cert['signatures'][0]
        with self.assertRaises(ValueError): verify_query(cert, self.query, self.keys)

    def test_foreign_configuration_cannot_self_authorize(self):
        foreign = {f'did:web:attacker{i}.example#seal': key for i, key in enumerate(self.keys.values())}
        with self.assertRaises(ValueError):
            verify_query(sign(self.statement, dict(list(foreign.items())[:3])), self.query, self.keys)

    def test_signature_and_phase_substitution_rejected(self):
        for context in ['ak.seal.commit.v1', HANDOFF]:
            with self.subTest(context=context), self.assertRaises(ValueError):
                verify_query(sign(self.statement, self.voters, context), self.query, self.keys)
        cert = copy.deepcopy(self.certificate)
        cert['statement']['results'][0]['state'] = {'revision_event_id': CONFIG, 'value': 'join'}
        with self.assertRaises((ValueError, InvalidSignature)): verify_query(cert, self.query, self.keys)

    def test_realm_configuration_and_target_substitution_rejected(self):
        for field in ['realm_id', 'configuration_ref', 'target_seal_ref']:
            body = copy.deepcopy(self.statement)
            body[field] = body[field][:-1] + ('A' if body[field][-1] != 'A' else 'B')
            with self.subTest(field=field), self.assertRaises(ValueError):
                verify_query(sign(body, self.voters), self.query, self.keys)

    def test_query_omission_or_extra_result_rejected(self):
        for results in [[], self.statement['results'] * 2]:
            body = {**self.statement, 'results': results}
            with self.assertRaises(ValueError): verify_query(sign(body, self.voters), self.query, self.keys)

    def test_account_selector_substitution_rejected(self):
        query = copy.deepcopy(self.query)
        query['selectors'][0]['cell_id'] = CELL.replace('bob', 'alice')
        with self.assertRaises(ValueError): verify_query(self.certificate, query, self.keys)

    def test_complete_empty_range_and_bounds(self):
        selector = {'kind': 'cell_range', 'lower_cell_id': CELL, 'upper_cell_id': CELL+'z'}
        query = {'target_seal_ref': TARGET, 'selectors': [selector]}
        body = {**self.statement, 'results': [{'selector': selector, 'cells': []}]}
        cert = sign(body, self.voters)
        self.valid('#/$defs/certificate', cert)
        verify_query(cert, query, self.keys)
        body['results'][0]['cells'] = [{'cell_id': CELL+'zz', 'state': {'revision_event_id': CONFIG, 'value': None}}]
        with self.assertRaises(ValueError): verify_query(sign(body, self.voters), query, self.keys)

    def test_command_effect_is_separate_from_final_cell(self):
        effect = {'selector': {'kind': 'command_effect', 'event_digest': 'sha256:'+'a'*64, 'cell_id': CELL},
                  'state': {'revision_event_id': CONFIG, 'value': None}}
        self.valid('#/$defs/result', effect)
        final = {'selector': {'kind': 'cell', 'cell_id': CELL}, 'state': {'revision_event_id': CONFIG, 'value': 'join'}}
        query = {'target_seal_ref': TARGET, 'selectors': [effect['selector']]}
        with self.assertRaises(ValueError):
            verify_query(sign({**self.statement, 'results': [final]}, self.voters), query, self.keys)

    def test_raw_resolve_and_conclusion_queries_are_exclusive(self):
        shape = {'realm_id': REALM, 'conclusion_queries': [self.query]}
        fragment = '#/$defs/PeerSealResolveRequestBody'
        self.valid(fragment, shape, file='service-operation-dtos.schema.json')
        self.valid(fragment, {**shape, 'seal_refs': [TARGET]}, False, file='service-operation-dtos.schema.json')

    def test_resolve_missing_and_success_outcomes(self):
        fragment = '#/$defs/SealResolveOutcome'
        evidence = {'configuration_handoffs': [], 'conclusions': [self.certificate]}
        self.valid(fragment, {'missing_conclusion_queries': [self.query]}, file='service-operation-dtos.schema.json')
        self.valid(fragment, {'missing_conclusion_queries': []}, False, file='service-operation-dtos.schema.json')
        self.valid(fragment, {'missing_conclusion_queries': [], 'conclusion_set': evidence}, file='service-operation-dtos.schema.json')

    def test_unsigned_bundle_cannot_be_empty_success(self):
        bundle = {'target_seal_ref': TARGET, 'seals': [], 'control_moves': [], 'inclusion_proofs': [], 'availability_proofs': []}
        self.valid('', bundle, False, file='cbs-proof-bundle.schema.json')
        bundle['conclusion_set'] = {'configuration_handoffs': [], 'conclusions': [self.certificate]}
        self.valid('', bundle, file='cbs-proof-bundle.schema.json')

    def test_bootstrap_uses_same_certificate(self):
        self.valid('#/$defs/realm_join_bootstrap_record', {'kind': 'seal_conclusion',
                   'conclusion_set': {'configuration_handoffs': [], 'conclusions': [self.certificate]}}, file='realm-join-intake.schema.json')

    def test_handoff_is_signed_by_old_configuration(self):
        new = {f'did:web:new{i}.example#seal': Ed25519PrivateKey.from_private_bytes(bytes([i+10])*32)
               for i in range(4)}
        descriptors = []
        for method, key in new.items():
            public = key.public_key().public_bytes_raw()
            descriptors.append({'actor_id': {'kind': 'service', 'service_id': 'ak:did_core:' + method[4:].split('#')[0]},
                                'verification_method': method, 'key_kind': 'ed25519_raw32', 'jose_algorithm': 'Ed25519',
                                'frozen_public_key_b64u': b64(public),
                                'frozen_public_key_digest': 'sha256:' + hashlib.sha256(public).hexdigest()})
        statement = {'realm_id': REALM, 'configuration_ref': CONFIG, 'handoff_seal_ref': TARGET,
                     'next_configuration_ref': 'ak:event:'+b64(b'\x01'+b'\x88'*32),
                     'next_configuration': {'kind': 'quorum', 'signers': descriptors, 'fault_tolerance': 1, 'max_clock_error_ms': 1000}}
        cert = sign(statement, self.voters, HANDOFF)
        self.valid('#/$defs/handoff_certificate', cert)
        verify_signatures(cert, self.keys, CONFIG, REALM, HANDOFF)
        with self.assertRaises(ValueError):
            verify_signatures(sign(statement, dict(list(new.items())[:3]), HANDOFF), self.keys, CONFIG, REALM, HANDOFF)
        after_handoff = {**self.statement, 'configuration_ref': statement['next_configuration_ref'],
                         'authority_seal_ref': 'ak:seal:sha256:'+'9'*64}
        historical = sign(after_handoff, dict(list(new.items())[:3]))
        verify_query(historical, self.query, new, statement['next_configuration_ref'])
        with self.assertRaises(ValueError):
            verify_query(historical, self.query, self.keys)

    def test_cached_statement_is_reusable_without_new_signature(self):
        cached = json.loads(json.dumps(self.certificate))
        verify_query(cached, self.query, self.keys)
        self.assertNotIn('expires_at', cached['statement'])
        self.assertNotIn('request_id', cached['statement'])

    def test_known_configuration_is_only_a_transfer_hint(self):
        query = {**self.query, 'known_configuration_ref': CONFIG}
        self.valid('#/$defs/query', query)
        verify_query(self.certificate, query, self.keys)
        query['known_configuration_ref'] = 'ak:event:'+b64(b'\x01'+b'\x99'*32)
        foreign = {**self.statement, 'configuration_ref': query['known_configuration_ref']}
        with self.assertRaises(ValueError):
            verify_query(sign(foreign, self.voters), query, self.keys)


if __name__ == '__main__':
    unittest.main()
