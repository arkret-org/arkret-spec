"""Verify reuse, cryptographic bindings and rejection at the MIMI claim boundary."""
from copy import deepcopy
import base64
import json
import unittest

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from tools.generate_mimi_key_material_fixture import ART, OP, OUT, OUTCOME, REQUEST, build, digest, jcs


def unb64(value):
    return base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))


def adapter_accepts(request, world):
    binding = request['service_binding']
    return (world['provider_id'] == world['source_id'] == binding['source_id']
        and world['destination_id'] == binding['destination_id']
        and world['idempotency_key'] == request['claim_request_id']
        and world['room_uri'] == world['binding_room_uri']
        and world['binding_realm_id'] == request['intended_realm_id']
        and world['binding_group_id'] == request['mls_group_id']
        and world['binding_active'] and world['native_authorized']
        and 'mimi.content.v1' in request['required_capabilities']
        and not request.get('last_resort_allowed', False))


class MimiKeyMaterialClaimContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(OUT.read_text(encoding='utf-8'))
        docs = [json.loads(p.read_text(encoding='utf-8')) for p in (ART / 'schemas').glob('*.json')]
        cls.registry = Registry().with_resources((d['$id'], Resource.from_contents(d)) for d in docs)
        cls.catalog = json.loads((ART / 'registry/contract-registry.json').read_text(encoding='utf-8'))

    def test_fixture_is_deterministic(self):
        self.assertEqual(self.fixture, build())

    def test_operation_uses_native_carriers_and_recovery(self):
        op = next(x for x in self.catalog['operation_registry']['operations'] if x['operation_id'] == OP)
        self.assertEqual(op['request_schema_ref'], REQUEST)
        self.assertEqual(op['response_schema_ref'], OUTCOME)
        self.assertEqual(op['idempotency_mechanism'], 'idempotency_key')
        self.assertTrue(op['retry_safe'])
        self.assertEqual(op['uncertain_outcome']['strategy'], 'replay_same_operation')
        self.assertEqual(op['uncertain_outcome']['operation_id'], OP)
        self.assertEqual(op['outward_disclosure_policy_id'], 'ak.outward_disclosure.target_private_claim.v1')

    def test_all_positive_and_negative_schema_cases(self):
        for row in self.fixture['schema_validation_cases']:
            with self.subTest(row['name']):
                validator = Draft202012Validator({'$ref': 'https://arkret.org/v1/' + row['schema_ref']}, registry=self.registry)
                errors = list(validator.iter_errors(row['instance']))
                self.assertEqual(not errors, row['expect_valid'], [x.message for x in errors])

    def test_provider_scope_and_authorization_boundaries(self):
        for row in self.fixture['decision_cases']:
            with self.subTest(row['name']):
                world = dict(self.fixture['world'], **row['overrides'])
                self.assertEqual(adapter_accepts(self.fixture['request'], world), row['expect_valid'])
        for field, value in [('last_resort_allowed', True), ('required_capabilities', ['ak.content.v1'])]:
            changed = dict(self.fixture['request'], **{field: value})
            self.assertFalse(adapter_accepts(changed, self.fixture['world']))

    def test_participant_signature_binds_request_and_station_pair(self):
        request = self.fixture['request']
        auth = request['requester_authorization']
        transcript = {
            'authorization': {k: v for k, v in auth.items() if k not in ('kind', 'signature')},
            'request': {k: v for k, v in request.items() if k not in ('requester_authorization', 'service_binding')},
            'service_binding': request['service_binding'],
        }
        key = Ed25519PublicKey.from_public_bytes(unb64(self.fixture['participant_public_key']))
        signature = unb64(auth['signature']['signature'])
        prefix = b'ak.peer-keypackage-claim-authorization-v1\n'
        key.verify(signature, prefix + jcs(transcript))
        for branch in transcript:
            for field in transcript[branch]:
                with self.subTest(branch=branch, field=field):
                    changed = deepcopy(transcript)
                    del changed[branch][field]
                    with self.assertRaises(InvalidSignature):
                        key.verify(signature, prefix + jcs(changed))

    def test_receipt_covers_original_claim_and_request(self):
        outcome = self.fixture['outcome']['claim_outcome']
        receipt = outcome['claim_receipt']
        self.assertEqual(receipt['request_digest'], digest(self.fixture['request']))
        self.assertEqual(receipt['claims_digest'], digest(outcome['claims']))
        self.assertEqual(outcome['claim_request_id'], receipt['claim_request_id'])
        kat = json.loads((ART / 'fixtures/mls-keypackage-endpoint-kat-fixture.json').read_text(encoding='utf-8'))['cases'][0]
        publication = json.loads(kat['upload_entry_jcs'])
        self.assertEqual(outcome['claims'][0]['capabilities'], publication['capabilities'])
        self.assertLessEqual(publication['created_at'], receipt['claimed_at'])
        self.assertLessEqual(receipt['expires_at'], publication['expires_at'])
        key = Ed25519PublicKey.from_public_bytes(unb64(self.fixture['destination_public_key']))
        body = {k: v for k, v in receipt.items() if k != 'signature'}
        signature = unb64(receipt['signature']['signature'])
        prefix = b'ak.peer-keypackage-claim-receipt-v1\n'
        key.verify(signature, prefix + jcs(body))
        for field in body:
            changed = deepcopy(body)
            del changed[field]
            with self.subTest(field=field), self.assertRaises(InvalidSignature):
                key.verify(signature, prefix + jcs(changed))
        for field in outcome['claims'][0]:
            changed = deepcopy(outcome['claims'])
            del changed[0][field]
            self.assertNotEqual(digest(changed), receipt['claims_digest'])

    def test_old_parallel_carriers_and_proof_contexts_are_removed(self):
        schema = json.loads((ART / 'schemas/mimi-operations.schema.json').read_text(encoding='utf-8'))
        for name in ('keypackage', 'group_info', 'mimi_key_material_request_body', 'mimi_key_material_outcome'):
            self.assertNotIn(name, schema['$defs'])
        registry = json.loads((ART / 'registry/proof-context-registry.json').read_text(encoding='utf-8'))
        contexts = {x['context'] for x in registry['contexts']}
        self.assertNotIn('ak.mimi_key_material_request_proof.v1', contexts)
        self.assertNotIn('ak.mimi_key_material_outcome_proof.v1', contexts)

    def test_transport_covers_idempotency_and_cross_domain_binding(self):
        scenario = next(x for x in self.catalog['http_signature_contract_registry']['scenarios'] if x['scenario_id'] == 'ak.http_signature.scenario.mimi_provider.v1')
        conditions = {x['component']: x['condition'] for x in scenario['conditional_covered_components']}
        for field in ('idempotency-key', 'source-trust-domain', 'destination-trust-domain'):
            self.assertIn(OP, conditions[field])

    def test_native_lifecycle_obligations_keep_their_original_cases(self):
        for reference in self.fixture['native_lifecycle_cases']:
            fixture = json.loads((ART / 'fixtures' / reference['fixture']).read_text(encoding='utf-8'))
            case = next(x for x in fixture['cases'] if x['name'] == reference['case'])
            self.assertTrue(case['expected'])
            self.assertTrue(case.get('negative_mutations') or case.get('negative_cases') or case.get('assertions'))


if __name__ == '__main__':
    unittest.main()
