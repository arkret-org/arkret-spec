"""Lock complete registration shapes, time roles and control-intent binding."""
import base64
from copy import deepcopy
import json
import unittest

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from tools.generate_published_did_registration_fixture import ART, OUT, DOMAIN, build, jcs, request_digest


def unb64(value):
    return base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))


class PublishedDidRegistrationContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(OUT.read_text(encoding='utf-8'))
        docs = [json.loads(p.read_text(encoding='utf-8')) for p in (ART / 'schemas').glob('*.json')]
        cls.registry = Registry().with_resources((d['$id'], Resource.from_contents(d)) for d in docs)
        cls.account = json.loads((ART / 'schemas/account-operations.schema.json').read_text(encoding='utf-8'))['$defs']

    def test_deterministic_fixture(self):
        self.assertEqual(self.fixture, build())

    def test_positive_and_negative_closed_schema_cases(self):
        for row in self.fixture['schema_validation_cases']:
            with self.subTest(row['name']):
                validator = Draft202012Validator({'$ref': 'https://arkret.org/v1/' + row['schema_ref']}, registry=self.registry)
                errors = list(validator.iter_errors(row['instance']))
                self.assertEqual(not errors, row['expect_valid'], [e.message for e in errors])

    def test_signature_covers_each_proof_member_and_domain(self):
        proof = deepcopy(self.fixture['request']['proof'])
        signature = unb64(proof.pop('signature'))
        key = Ed25519PublicKey.from_public_bytes(unb64(self.fixture['control_public_key']))
        key.verify(signature, DOMAIN + jcs(proof))
        for member in proof:
            with self.subTest(member=member):
                changed = deepcopy(proof)
                del changed[member]
                with self.assertRaises(InvalidSignature):
                    key.verify(signature, DOMAIN + jcs(changed))
        with self.assertRaises(InvalidSignature):
            key.verify(signature, b'ak.identity_creation_control_proof.v1\n' + jcs(proof))

    def test_canonical_intent_covers_every_initialization_member(self):
        request = self.fixture['request']
        self.assertEqual(request_digest(request), request['proof']['request_canonical_digest'])
        for member in request['published_identity']:
            with self.subTest(member=member):
                changed = deepcopy(request)
                del changed['published_identity'][member]
                self.assertNotEqual(request_digest(changed), request['proof']['request_canonical_digest'])
        for member in ('principal_id', 'did'):
            changed = deepcopy(request)
            changed[member] += ':other'
            self.assertNotEqual(request_digest(changed), request['proof']['request_canonical_digest'])

    def test_success_and_relay_cannot_omit_initialization(self):
        outcome = self.account['account_register_response_body']
        self.assertTrue({'pcr_genesis_commits', 'session_grant_outcome', 'binding_receipt'} <= set(outcome['required']))
        receipt = self.account['account_binding_receipt']
        self.assertTrue({'identity_creation_lease_id', 'lease_fence'} <= set(receipt['required']))
        relay = json.loads((ART / 'schemas/principal-operations.schema.json').read_text(encoding='utf-8'))['$defs']['pcr_genesis_submit_request_body']
        self.assertEqual(len(relay['oneOf']), 2)
        self.assertEqual(relay['oneOf'][0]['properties']['registration_did_evidence']['$ref'].split('/')[-1], 'registration_did_evidence')
        self.assertEqual(relay['oneOf'][1]['properties']['registration_did_evidence']['$ref'].split('/')[-1], 'published_registration_did_evidence')

    def test_reservation_preserves_branch_and_validation_phase(self):
        reserved = self.account['reserved_identity_creation']
        self.assertIn('binding_kind', reserved['required'])
        self.assertIn('did_validated', self.account['identity_creation_lease']['properties']['state']['enum'])
        self.assertIn('binding_kind', self.account['identity_abandonment_response_body']['required'])

    def test_relay_rejects_cross_branch_proof_and_time_material(self):
        request = self.fixture['request']
        published = request['published_identity']
        proof = request['proof']
        evidence = dict(published['registration_did_evidence_draft'], validated_at='2026-08-09T00:00:01.000Z')
        relay = {key: proof[key] for key in ('principal_id', 'did', 'pcr_realm_id', 'did_version_id', 'control_key_digest')}
        relay.update(account_authority_id=proof['audience_id'], idempotency_key='published-registration-0001', registration_request_digest=proof['request_canonical_digest'], principal_registration_anchor=published['principal_registration_anchor'], registration_did_evidence=evidence, account_registration_control_proof=proof, genesis_unit=published['pcr_genesis_unit'])
        validator = Draft202012Validator({'$ref': 'https://arkret.org/v1/schemas/principal-operations.schema.json#/$defs/pcr_genesis_submit_request_body'}, registry=self.registry)
        self.assertFalse(list(validator.iter_errors(relay)))
        for mutation in ('registry_time', 'both_proofs', 'no_proof'):
            changed = deepcopy(relay)
            if mutation == 'registry_time':
                changed['registration_did_evidence']['accepted_at'] = changed['registration_did_evidence'].pop('validated_at')
            elif mutation == 'both_proofs':
                changed['identity_creation_control_proof'] = self.fixture['schema_validation_cases'][1]['instance']['identity_creation']['control_proof']
            else:
                del changed['account_registration_control_proof']
            with self.subTest(mutation=mutation):
                self.assertTrue(list(validator.iter_errors(changed)))

    def test_evidence_signature_is_separate_and_digest_bound(self):
        evidence = self.fixture['request']['published_identity']['registration_did_evidence_draft']
        control = evidence['control_proof']
        from tools.generate_published_did_registration_fixture import digest
        transcript = {key: evidence[key] for key in ('principal_id', 'did', 'adapter_version', 'method_history_head', 'version_id', 'control_key_digest')}
        transcript.update(context='ak.registration_did_evidence_control_proof.v1', method_evidence_digest=digest(evidence['method_evidence']), verification_method=control['verification_method'], created_at=control['created_at'])
        header, _, signature = control['jws'].split('.')
        message = (header + '.' + base64.urlsafe_b64encode(jcs(transcript)).decode().rstrip('=')).encode()
        key = Ed25519PublicKey.from_public_bytes(unb64(self.fixture['control_public_key']))
        key.verify(unb64(signature), message)
        changed = deepcopy(transcript)
        changed['method_evidence_digest'] = 'sha256:' + '0' * 64
        bad = (header + '.' + base64.urlsafe_b64encode(jcs(changed)).decode().rstrip('=')).encode()
        with self.assertRaises(InvalidSignature):
            key.verify(unb64(signature), bad)


if __name__ == '__main__':
    unittest.main()
