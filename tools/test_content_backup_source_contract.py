"""Byte and shape checks; no native storage or method-history qualification claim."""
import copy
import hashlib
import json
from pathlib import Path
import unittest

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from tools.content_history import aad, b64, content_key, jcs, key_commitment, unb64
from tools.content_backup_source import protections_digest, signing_bytes, verify_backup_source_bytes

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'spec/v1/artifacts'


def signed_original_and_attestation():
    """Real producer/service Ed25519 primitives; never an accepted native fact."""
    fixture = json.loads((ART / 'fixtures/content-history-fixture.json').read_text(encoding='utf-8'))
    event = copy.deepcopy(fixture['kat']['outer_event'])
    producer = copy.deepcopy(fixture['kat']['content_context']['producer'])
    event['actor_id'] = producer['actor_id']
    intent = fixture['local_message_authoring']
    event['payload'] = {key: intent[key] for key in ['strand_id', 'track_name']}
    for index, (field, kat) in enumerate([('encrypted_content', fixture['kat']), ('encrypted_metadata', fixture['metadata_kat'])]):
        envelope = copy.deepcopy(kat['envelope'])
        context = copy.deepcopy(kat['content_context'])
        context['producer'] = producer
        context['content_key_salt'] = b64(bytes([242 + index]) * 32)
        key = content_key(bytes.fromhex(fixture['kat']['root_hex']), context)
        if index == 0:
            envelope['content_type'] = 'application/vnd.arkret.message+json'
        envelope['encryption_context'].update({'content_key_salt': context['content_key_salt'],
                                                'key_commitment': key_commitment(key, context)})
        plaintext = ({'kind': 'ak.content.text', 'body': 'original recoverable content', 'format': 'plain'}
                     if index == 0 else {'fields': {'title': 'original metadata'}})
        envelope['ciphertext'] = b64(AESGCM(key).encrypt(bytes(12), jcs(plaintext), aad(event, envelope, context)))
        event['payload'][field] = envelope
    digest = hashlib.sha256(jcs(event)).digest()
    event['event_id'] = 'ak:event:' + b64(b'\x01' + digest)
    method = 'did:webvh:z6mkfixture:alice.example#ak:device:019a0000-0000-7000-8000-000000000001'
    binding = {'context': 'ak.event_proof.v1', 'event_digest': 'sha256:' + digest.hex(),
               'actor_id': event['actor_id'], 'verification_method': method, 'created_at': event['created_at']}
    signer = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(fixture['kat']['signing_seed_hex']))
    signature = signer.sign(jcs(binding))
    event['producer_proof'] = {key: binding[key] for key in ['event_digest', 'verification_method', 'created_at']}
    event['producer_proof'].update({'kind': 'detached_jws', 'jws': b64(b'{"alg":"Ed25519"}') + '..' + b64(signature)})
    slots = [{'content_path': '/payload/' + key, 'protection': event['payload'][key]['encryption_context']['protection']}
             for key in ['encrypted_content', 'encrypted_metadata']]
    origin = producer['actor_id']['account_id']['station_id']
    service_method = 'did:webvh:z6mkfixturestationexample:station.example#service-key-fixture'
    service = Ed25519PrivateKey.from_private_bytes(bytes([233]) * 32)
    attestation = {'event_ref': event['event_id'], 'event_original_digest': 'sha256:' + hashlib.sha256(jcs(event)).hexdigest(),
                   'producer': copy.deepcopy(producer), 'effective_scope': event['scope_ref'],
                   'destination_service_id': 'ak:did_core:web:governor.example',
                   'protections_digest': 'sha256:' + hashlib.sha256(jcs(slots)).hexdigest(),
                   'verification_method': service_method, 'attested_at': '2026-11-08T00:00:01.000Z',
                   'expires_at': '2026-11-08T00:05:01.000Z'}
    transcript = b'ak.content.backup_source.v1\n' + jcs(attestation)
    attestation['signature'] = {'kid': service_method, 'signature_algorithm': 'Ed25519', 'signature': b64(service.sign(transcript))}
    origin_key = {'station_id': origin, 'verification_method': service_method,
                  'public_key_base64url': b64(service.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))}
    return event, attestation, producer, origin_key, transcript, binding


class ContentBackupSourceContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        documents = [json.loads(p.read_text(encoding='utf-8')) for p in (ART / 'schemas').glob('*.schema.json')]
        resources = Registry().with_resources((d['$id'], Resource.from_contents(d)) for d in documents)
        cls.validator = Draft202012Validator({'$ref': 'https://arkret.org/v1/schemas/content-encryption.schema.json#/$defs/backup_source_attestation'}, registry=resources)
        cls.event_validator = Draft202012Validator({'$ref': 'https://arkret.org/v1/schemas/event-envelope.schema.json'}, registry=resources)
        cls.fixture = json.loads((ART / 'fixtures/content-history-fixture.json').read_text(encoding='utf-8'))
        cls.cases = {row['name']: row for row in json.loads((ART / 'fixtures/content-backup-source-fixture.json').read_text(encoding='utf-8'))['cases']}

    def test_explicit_source_has_closed_required_binding(self):
        _, attestation, _, _, _, _ = signed_original_and_attestation()
        self.validator.validate(attestation)

    def test_peer_carrier_has_explicit_source_and_replication_cannot_supply_it(self):
        schema = json.loads((ART / 'schemas/authority-commit-operations.schema.json').read_text(encoding='utf-8'))
        peer = schema['$defs']['peer_submit_request_body']
        self.assertEqual(peer['properties']['content_backup_sources']['items'],
                         {'$ref': './content-encryption.schema.json#/$defs/backup_source'})
        self.assertEqual(peer['properties']['content_backup_sources']['maxItems'], 2)
        for branch in peer['oneOf']:
            if branch['properties']['branch']['const'] != 'authority_forward':
                self.assertIn({'required': ['content_backup_sources']}, branch['not']['anyOf'])

    def slots(self, event):
        return [{'content_path': '/payload/' + field,
                 'protection': event['payload'][field]['encryption_context']['protection']}
                for field in ['encrypted_content', 'encrypted_metadata']]

    def verify(self, case, **overrides):
        arguments = dict(attestation=case['attestation'], original_event=case['event'],
                         actual_producer=case['producer'], registered_slots=self.slots(case['event']),
                         origin_key=case['origin_key'], destination='ak:did_core:web:governor.example',
                         evaluated_at='2026-11-08T00:00:02.000Z')
        arguments.update(overrides)
        verify_backup_source_bytes(**arguments)

    def resign(self, attestation, case):
        signer = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(case['service_signing_seed_hex']))
        attestation['signature']['signature'] = b64(signer.sign(signing_bytes(attestation)))

    def test_frozen_human_source_matches_independent_producer_and_service_transcripts(self):
        event, attestation, producer, origin, transcript, binding = signed_original_and_attestation()
        frozen = self.cases['human']
        for key, value in [('event', event), ('attestation', attestation), ('producer', producer), ('origin_key', origin)]:
            self.assertEqual(frozen[key], value)
        self.assertEqual(frozen['signing_hex'], transcript.hex())
        self.assertEqual(frozen['producer_binding_hex'], jcs(binding).hex())

    def test_human_and_agent_source_verify_real_original_signatures_and_decrypt(self):
        for name, case in self.cases.items():
            with self.subTest(name=name):
                self.validator.validate(case['attestation'])
                self.event_validator.validate(case['event'])
                self.verify(case)
                event = case['event']
                preimage = {k: v for k, v in event.items() if k not in ['event_id', 'producer_proof', 'unsigned']}
                digest = hashlib.sha256(jcs(preimage)).digest()
                self.assertEqual(event['event_id'], 'ak:event:' + b64(b'\x01' + digest))
                self.assertEqual(event['producer_proof']['event_digest'], 'sha256:' + digest.hex())
                producer_binding = json.loads(bytes.fromhex(case['producer_binding_hex']))
                self.assertEqual(producer_binding['actor_id'], event['actor_id'])
                self.assertEqual(producer_binding['event_digest'], event['producer_proof']['event_digest'])
                self.assertEqual(producer_binding['verification_method'], event['producer_proof']['verification_method'])
                Ed25519PublicKey.from_public_bytes(unb64(case['producer']['signature_key_base64url'])).verify(
                    unb64(event['producer_proof']['jws'].split('..')[1]), bytes.fromhex(case['producer_binding_hex']))
                for field, expected in [('encrypted_content', self.fixture['kat']), ('encrypted_metadata', self.fixture['metadata_kat'])]:
                    envelope = event['payload'][field]
                    context = copy.deepcopy(expected['content_context'])
                    context['producer'] = case['producer']
                    context['content_key_salt'] = envelope['encryption_context']['content_key_salt']
                    key = content_key(bytes.fromhex(self.fixture['kat']['root_hex']), context)
                    self.assertEqual(key_commitment(key, context), envelope['encryption_context']['key_commitment'])
                    self.assertEqual(AESGCM(key).decrypt(bytes(12), unb64(envelope['ciphertext']), aad(event, envelope, context)).hex(), case['plaintexts_hex'][field])

    def test_valid_service_signature_cannot_rebind_original_scope_producer_or_destination(self):
        case = self.cases['human']
        for field in ['event_ref', 'event_original_digest', 'producer', 'effective_scope', 'destination_service_id', 'protections_digest']:
            changed = copy.deepcopy(case['attestation'])
            if field == 'producer':
                changed[field]['authorization_event_ref'] = 'ak:event:' + b64(b'\x01' + bytes([19]) * 32)
            elif field == 'effective_scope':
                changed[field]['realm_id'] = 'ak:realm:' + b64(b'\x01' + bytes([19]) * 32)
            elif field == 'event_ref':
                changed[field] = 'ak:event:' + b64(b'\x01' + bytes([19]) * 32)
            elif field == 'destination_service_id':
                changed[field] = 'ak:did_core:web:another-governor.example'
            else:
                changed[field] = 'sha256:' + '0' * 64
            self.resign(changed, case)
            with self.assertRaises(ValueError, msg=field):
                self.verify(case, attestation=changed)

    def test_original_proof_ciphertext_or_metadata_change_breaks_original_binding(self):
        case = self.cases['human']
        for field in ['proof', 'body', 'metadata', 'unsigned']:
            event = copy.deepcopy(case['event'])
            if field == 'proof':
                event['producer_proof']['jws'] += 'A'
            elif field == 'unsigned':
                event['unsigned'] = {'extra': True}
            else:
                key = 'encrypted_content' if field == 'body' else 'encrypted_metadata'
                event['payload'][key]['ciphertext'] += 'A'
            with self.assertRaises(ValueError, msg=field):
                self.verify(case, original_event=event)
        with self.assertRaises(ValueError):
            self.verify(case, registered_slots=self.slots(case['event'])[:1])

    def test_wrong_origin_method_station_and_expired_or_unbounded_source_fail(self):
        case = self.cases['agent']
        for field in ['station_id', 'verification_method']:
            origin = copy.deepcopy(case['origin_key'])
            origin[field] += 'changed'
            with self.assertRaises(ValueError):
                self.verify(case, origin_key=origin)
        for now in ['2026-11-08T00:00:00.999Z', '2026-11-08T00:05:01.000Z']:
            with self.assertRaises(ValueError):
                self.verify(case, evaluated_at=now)
        for expires in ['2026-11-08T00:00:01.000Z', '2026-11-08T00:05:01.001Z']:
            attestation = copy.deepcopy(case['attestation'])
            attestation['expires_at'] = expires
            self.resign(attestation, case)
            with self.assertRaises(ValueError):
                self.verify(case, attestation=attestation)
        changed = copy.deepcopy(case['attestation'])
        changed['protections_digest'] = 'sha256:' + '0' * 64
        with self.assertRaises(InvalidSignature):
            self.verify(case, attestation=changed)

    def test_protection_paths_are_complete_unique_and_sorted_without_reordering_refs(self):
        case = self.cases['human']
        slots = self.slots(case['event'])
        self.assertEqual(protections_digest(list(reversed(slots))), case['attestation']['protections_digest'])
        with self.assertRaises(ValueError):
            protections_digest([])
        with self.assertRaises(ValueError):
            protections_digest(slots + slots[:1])
        changed = copy.deepcopy(slots)
        changed[0]['protection']['root_refs'] = []
        with self.assertRaises(ValueError):
            protections_digest(changed)

    def test_missing_null_and_unknown_attestation_members_are_rejected(self):
        _, attestation, _, _, _, _ = signed_original_and_attestation()
        for field in attestation:
            for missing in [True, False]:
                changed = copy.deepcopy(attestation)
                if missing:
                    del changed[field]
                else:
                    changed[field] = None
                self.assertFalse(self.validator.is_valid(changed), (field, missing))
        changed = copy.deepcopy(attestation)
        changed['durable'] = True
        self.assertFalse(self.validator.is_valid(changed))


if __name__ == '__main__':
    unittest.main()
