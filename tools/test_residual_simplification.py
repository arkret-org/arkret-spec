"""Residual simplification: complete schemas and bounded semantic/crypto checks.

The HPKE counterexample exercises the Welcome GroupSecrets encryption layer,
not a complete MLS group or a live Station. Product runners cover those layers.
"""
import copy
import hashlib
import hmac
import json
import unittest
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import test_self_signer_result_schema as signer_tests


def hkdf_extract(salt: bytes, ikm: bytes) -> bytes:
    return hmac.new(salt or b"\x00" * 32, ikm, hashlib.sha256).digest()


def hkdf_expand(prk: bytes, info: bytes, length: int) -> bytes:
    output = b""
    block = b""
    counter = 1
    while len(output) < length:
        block = hmac.new(prk, block + info + bytes([counter]), hashlib.sha256).digest()
        output += block
        counter += 1
    return output[:length]


def hpke_labeled_extract(suite_id: bytes, salt: bytes, label: bytes, ikm: bytes) -> bytes:
    return hkdf_extract(salt, b"HPKE-v1" + suite_id + label + ikm)


def hpke_labeled_expand(suite_id: bytes, prk: bytes, label: bytes, info: bytes, length: int) -> bytes:
    labeled_info = length.to_bytes(2, "big") + b"HPKE-v1" + suite_id + label + info
    return hkdf_expand(prk, labeled_info, length)


ROOT = Path(__file__).resolve().parents[1]
A = ROOT / 'spec/v1/artifacts'

def load(name):
    return json.loads((A/name).read_text(encoding='utf-8'))

def validate_advertisement(value):
    supported = set(value['supported_profiles'])
    verified = [x['profile_id'] for x in value['verified_profiles']]
    if len(set(verified)) != len(verified) or not set(verified) <= supported:
        raise ValueError('verified profile relationship')
    registered = {x['tzdb_version'] for x in load('registry/calendar-timezone-registry.json')['releases']}
    if not set(value.get('calendar_tzdb_versions', [])) <= registered:
        raise ValueError('unregistered TZDB release')

def associate(request, outcome):
    for field in ['request_id', 'realm_id', 'recipient_account_id']:
        if request[field] != outcome[field]:
            raise ValueError('invocation mismatch')
    canonical = lambda x: json.dumps(x, sort_keys=True, separators=(',', ':'))
    queries = [canonical(x) for x in request['queries']]
    results = [canonical(x['selector']) for x in outcome['results']]
    if len(set(results)) != len(results) or set(queries) != set(results):
        raise ValueError('selector conservation')
    return dict(zip(results, outcome['results']))

def hpke_key_nonce(private, peer_public, enc, recipient_public, info):
    kem = b'KEM\x00\x20'
    suite = b'HPKE\x00\x20\x00\x01\x00\x01'
    dh = private.exchange(X25519PublicKey.from_public_bytes(peer_public))
    eae = hpke_labeled_extract(kem, b'', b'eae_prk', dh)
    shared = hpke_labeled_expand(kem, eae, b'shared_secret', enc+recipient_public, 32)
    context = b'\x00'+hpke_labeled_extract(suite, b'', b'psk_id_hash', b'')+hpke_labeled_extract(suite, b'', b'info_hash', info)
    secret = hpke_labeled_extract(suite, shared, b'secret', b'')
    return (hpke_labeled_expand(suite, secret, b'key', context, 16),
            hpke_labeled_expand(suite, secret, b'base_nonce', context, 12))

class ResidualSimplificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        docs = [json.loads(p.read_text(encoding='utf-8')) for p in (A/'schemas').glob('*.json')]
        cls.registry = Registry().with_resources((d['$id'], Resource.from_contents(d)) for d in docs)
        cls.describe = Draft202012Validator({'$ref': 'https://arkret.org/v1/schemas/service-describe.schema.json'}, registry=cls.registry)
        cases=load('fixtures/schema-validation-fixture.json')['schema_validation_cases']
        cls.prototype=next(x['instance'] for x in cases if x['name']=='service_describe_valid')

    def test_both_calendar_profiles_all_advertisement_paths(self):
        for profile in ['ak.profile.calendar_event.v1', 'ak.profile.calendar_notification_dispatch.v1']:
            for verified in [False, True]:
                value=copy.deepcopy(self.prototype)
                value['supported_profiles']=[profile]
                value['verified_profiles']=[]
                if verified:
                    value['verified_profiles']=[{'profile_id':profile,'claim_kind':'conformance_verified','verification_run_id':'test-run','artifact_digest':'sha256:'+'a'*64,'artifact_ref':'https://verifier.example/run','verifier_id':'ak:did_core:web:verifier.example','signature':'AA','timestamp':'2026-09-12T00:00:00.000Z'}]
                value['calendar_tzdb_versions']=['2025a']
                self.describe.validate(value)
                validate_advertisement(value)
                for versions in [None, []]:
                    changed=copy.deepcopy(value)
                    if versions is None:del changed['calendar_tzdb_versions']
                    else:changed['calendar_tzdb_versions']=versions
                    self.assertFalse(self.describe.is_valid(changed))
                changed=copy.deepcopy(value);changed['calendar_tzdb_versions']=['9999z']
                with self.assertRaises(ValueError):validate_advertisement(changed)
                changed=copy.deepcopy(value);changed['claimed_profiles']=[]
                self.assertFalse(self.describe.is_valid(changed))
                if verified:
                    changed=copy.deepcopy(value);changed['supported_profiles']=[]
                    with self.assertRaises(ValueError):validate_advertisement(changed)
                    del changed['calendar_tzdb_versions']
                    self.assertFalse(self.describe.is_valid(changed))

    def test_exact_selector_association_is_order_independent(self):
        helper=signer_tests.SelfSignerResultTests()
        request=helper.request('historical_event')
        a=request['queries'][0]
        b=copy.deepcopy(a);b['verification_method']+='.other'
        c=copy.deepcopy(a);c['event_id']='ak:event:Ae6YFfDokA1FLUx_l-MhAbSvTvoys2ZpRPmqFwrWjd9g'
        request['queries']=[a,b,c]
        outcome={k:v for k,v in request.items() if k!='queries'}
        outcome['results']=[{'selector':x,'status':'unavailable'} for x in [c,a,b]]
        self.assertEqual(len(associate(request,outcome)),3)
        for results in [outcome['results'][:2],outcome['results']+[outcome['results'][0]]]:
            with self.assertRaises(ValueError):associate(request,{**outcome,'results':results})
        for field in ['request_id','realm_id','recipient_account_id']:
            with self.assertRaises(ValueError):associate(request,{**outcome,field:'other'})

    def test_query_keys_reject_mirrors_and_signal_retains_identity(self):
        s=load('schemas/signer-key-operations.schema.json')
        key={'public_key_b64u':'A'*43,'authorization_ref':'ak:event:Ae6YFfDokA1FLUx_l-MhAbSvTvoys2ZpRPmqFwrWjd9g'}
        validator=Draft202012Validator({'$ref':s['$id']+'#/$defs/query_signing_key'},registry=self.registry)
        validator.validate(key)
        for field,value in [('actor',signer_tests.SelfSignerResultTests().request()['queries'][0]['actor']),('verification_method','did:web:alice.example#key')]:
            self.assertFalse(validator.is_valid({**key,field:value}))
        self.assertFalse(validator.is_valid({'public_key_b64u':'A'*43}))
        self.assertEqual(set(s['$defs']['station_signing_key']['required']),{'actor','verification_method','public_key_b64u','authorization_ref'})
        signal=load('schemas/signal-stream-frame.schema.json')
        self.assertIn('signer-key-operations.schema.json#/$defs/station_signing_key',json.dumps(signal))

    def test_expiry_does_not_revoke_captured_welcome_key_material(self):
        fixture=load('fixtures/keypackage-lifecycle-fixture.json')['expiry_security_case']
        recipient=X25519PrivateKey.from_private_bytes(bytes.fromhex(fixture['recipient_private_key_hex']))
        ephemeral=X25519PrivateKey.from_private_bytes(bytes.fromhex(fixture['ephemeral_private_key_hex']))
        pk=recipient.public_key().public_bytes_raw();enc=ephemeral.public_key().public_bytes_raw()
        info=bytes.fromhex(fixture['encrypt_context_hex'])
        secret=bytes.fromhex(fixture['group_secrets_hex'])
        key,nonce=hpke_key_nonce(ephemeral,pk,enc,pk,info)
        ciphertext=AESGCM(key).encrypt(nonce,secret,b'')
        self.assertEqual(ciphertext.hex(),fixture['captured_ciphertext_hex'])
        self.assertLess(fixture['welcome_day'],fixture['expires_day'])
        self.assertGreater(fixture['compromise_day'],fixture['expires_day'])
        for day in [fixture['expires_day'],fixture['compromise_day']]:
            self.assertFalse(day < fixture['expires_day'])
            recovered_key,recovered_nonce=hpke_key_nonce(recipient,enc,enc,pk,info)
            self.assertEqual(AESGCM(recovered_key).decrypt(recovered_nonce,ciphertext,b''),secret)
        fresh=X25519PrivateKey.from_private_bytes(bytes.fromhex('44'*32))
        fresh_pk=fresh.public_key().public_bytes_raw()
        new_key,new_nonce=hpke_key_nonce(ephemeral,fresh_pk,enc,fresh_pk,info)
        future_ciphertext=AESGCM(new_key).encrypt(new_nonce,secret,b'')
        with self.assertRaises(InvalidTag):AESGCM(key).decrypt(new_nonce,future_ciphertext,b'')
        # The future-secret check is conditional; it is not an MLS update simulation.
        self.assertEqual(AESGCM(key).decrypt(nonce,ciphertext,b''),secret)

if __name__=='__main__':
    unittest.main()
