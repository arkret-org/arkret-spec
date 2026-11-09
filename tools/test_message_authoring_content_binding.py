"""Current encrypted local carriers, not native actor or membership proofs."""
import copy
import hashlib
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from tools.content_history import aad, content_key, jcs, key_commitment, unb64, verify_local_message_binding

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'spec/v1/artifacts'


class MessageAuthoringContentBindingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        docs = [json.loads(p.read_text(encoding='utf-8')) for p in (ART / 'schemas').glob('*.schema.json')]
        resources = Registry().with_resources((d['$id'], Resource.from_contents(d)) for d in docs)
        cls.schema = json.loads((ART / 'schemas/message-authoring.schema.json').read_text(encoding='utf-8'))
        cls.fixture = json.loads((ART / 'fixtures/content-history-fixture.json').read_text(encoding='utf-8'))
        cls.validator = Draft202012Validator(
            {'$ref': 'https://arkret.org/v1/schemas/message-authoring.schema.json#/$defs/message_authoring_intent'},
            registry=resources,
        )

    def intent(self):
        kat = self.fixture['kat']
        producer = kat['content_context']['producer']
        return {
            'strand_id': 'ak:strand:AT3ARBdH1FM6GjXK9ulTx-YMvQOXys39dlUzZV6KyID9',
            'track_name': 'discussion',
            'content': {
                'kind': 'mls',
                'encrypted_content': copy.deepcopy(kat['envelope']),
                'encrypted_metadata': copy.deepcopy(self.fixture['metadata_kat']['envelope']),
                'encryption_context': {
                    'scheme': kat['envelope']['encryption_scheme'],
                    'effective_scope': copy.deepcopy(kat['root_context']['effective_scope']),
                    'sender_domain': jcs(producer['actor_id']).decode('utf-8'),
                    'producer': copy.deepcopy(producer),
                    'outer_event_digest': 'sha256:' + hashlib.sha256(jcs(kat['outer_event'])).hexdigest(),
                },
            },
        }

    def test_current_encrypted_intent_uses_the_formal_content_envelope(self):
        self.validator.validate(self.intent())

    def test_scheme_reuses_the_canonical_envelope_selector(self):
        self.assertEqual(
            self.schema['$defs']['message_encryption_context']['properties']['scheme'],
            {'$ref': './encrypted-envelope.schema.json#/properties/encryption_scheme'},
        )

    def test_frozen_local_carrier_matches_independent_outer_and_producer(self):
        intent = self.fixture['local_message_authoring']
        self.assertEqual(intent, self.intent())
        producer = self.fixture['kat']['content_context']['producer']
        outer = self.fixture['kat']['outer_event']
        verify_local_message_binding(intent, outer, producer)
        for mutation in ['scope', 'producer', 'sender', 'outer_digest', 'metadata_epoch',
                         'metadata_root', 'metadata_salt']:
            value = copy.deepcopy(intent)
            context = value['content']['encryption_context']
            if mutation == 'scope':
                context['effective_scope'] = {'kind': 'realm', 'realm_id': 'ak:realm:ARQRpvtCGBgQfVQzTK4_Hgbg0D0HSnc3gPCvXOQUICir'}
            elif mutation == 'producer':
                context['producer']['authorization_event_ref'] = 'ak:event:ARQRpvtCGBgQfVQzTK4_Hgbg0D0HSnc3gPCvXOQUICir'
            elif mutation == 'sender':
                context['sender_domain'] = ' ' + context['sender_domain']
            elif mutation == 'outer_digest':
                context['outer_event_digest'] = 'sha256:' + '0' * 64
            else:
                metadata = value['content']['encrypted_metadata']['encryption_context']
                field = {'metadata_epoch': 'epoch', 'metadata_root': 'root_ref',
                         'metadata_salt': 'content_key_salt'}[mutation]
                metadata[field] = {'metadata_epoch': '13', 'metadata_root': 'sha256:' + '0' * 64,
                                   'metadata_salt': value['content']['encrypted_content']['encryption_context']['content_key_salt']}[mutation]
            with self.assertRaises(ValueError, msg=mutation):
                verify_local_message_binding(value, outer, producer)
        changed_outer = copy.deepcopy(outer)
        changed_outer['created_at'] = '2026-11-08T00:00:00.001Z'
        with self.assertRaises(ValueError):
            verify_local_message_binding(intent, changed_outer, producer)

    def test_metadata_is_a_real_independently_sealed_slot(self):
        body = self.fixture['kat']
        metadata = self.fixture['metadata_kat']
        context = metadata['content_context']
        key = content_key(bytes.fromhex(body['root_hex']), context)
        self.assertEqual(key.hex(), metadata['key_hex'])
        self.assertNotEqual(key.hex(), body['key_hex'])
        envelope = metadata['envelope']
        self.assertEqual(key_commitment(key, context), envelope['encryption_context']['key_commitment'])
        associated = aad(body['outer_event'], envelope, context)
        self.assertEqual(associated.hex(), metadata['aad_hex'])
        self.assertEqual(AESGCM(key).decrypt(bytes(12), unb64(envelope['ciphertext']), associated).hex(),
                         metadata['plaintext_hex'])

    def test_old_unknown_and_null_scheme_are_not_compatibility_branches(self):
        for scheme in ['mls_rfc9420', 'ak.encryption.unknown.v1', None]:
            value = self.intent()
            value['content']['encryption_context']['scheme'] = scheme
            self.assertFalse(self.validator.is_valid(value), scheme)

    def test_endpoint_and_complete_outer_digest_are_required_and_closed(self):
        for field in ['producer', 'outer_event_digest']:
            for missing in [False, True]:
                value = self.intent()
                context = value['content']['encryption_context']
                if missing:
                    del context[field]
                else:
                    context[field] = None
                self.assertFalse(self.validator.is_valid(value), (field, missing))
        value = self.intent()
        value['content']['encryption_context']['outer_event_digest'] = 'sha512:' + 'a' * 128
        self.assertFalse(self.validator.is_valid(value))
        value = self.intent()
        value['content']['encryption_context']['native_authorized'] = True
        self.assertFalse(self.validator.is_valid(value))
