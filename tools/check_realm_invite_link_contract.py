"""Verify link proof KATs, closed secret boundaries and complete IVS withdrawal."""
from __future__ import annotations

import base64
import copy
import hashlib
import json
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'spec/v1/artifacts'
PREFIX='ak.realm_invite_link.'

def read(path):return json.loads(path.read_text(encoding='utf-8'))
def jcs(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def b64(value):return base64.urlsafe_b64encode(value).decode().rstrip('=')
def decode(value):
    raw=base64.urlsafe_b64decode(value+'='*((-len(value))%4))
    assert b64(raw)==value,'noncanonical base64url'
    return raw

def main():
    fixture=read(ART/'fixtures/realm-invite-link-proof-kat-fixture.json')
    schemas={p.name:read(p) for p in (ART/'schemas').glob('*.json')}
    resources=Registry().with_resources((v['$id'],Resource.from_contents(v)) for v in schemas.values() if '$id' in v)
    proof_schema={'$ref':'https://arkret.org/v1/schemas/realm-invite-link.schema.json#/$defs/proof'}
    proof_validator=Draft202012Validator(proof_schema,registry=resources)
    token_validator=Draft202012Validator(schemas['realm-invite-link-token.schema.json'],registry=resources)
    key=Ed25519PrivateKey.from_private_bytes(decode(fixture['private_key_seed']))
    public=Ed25519PublicKey.from_public_bytes(decode(fixture['public_key']))
    assert b64(key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw))==fixture['public_key']
    bindings=[]
    for case in fixture['accepted_proof_cases']:
        body=case['binding'];proof=case['proof'];bindings.append(body)
        data=case['context'].encode()+b'\n'+jcs(body)
        assert data.decode()==case['signing_bytes_utf8']
        assert proof['transcript_digest']=='sha256:'+hashlib.sha256(data).hexdigest()
        assert b64(key.sign(data))==proof['signature']
        proof_validator.validate(proof);public.verify(decode(proof['signature']),data)
        for path in ['realm_id','realm_invite_link_id','request_id','audience','principal_id','station_id']:
            changed=copy.deepcopy(body)
            target=changed['subject_account_id'] if path in {'principal_id','station_id'} else changed
            target[path]+='x'
            try:public.verify(decode(proof['signature']),case['context'].encode()+b'\n'+jcs(changed))
            except InvalidSignature:pass
            else:raise AssertionError('proof accepted changed '+path)
        changed=copy.deepcopy(proof);changed['unexpected']=True
        assert list(proof_validator.iter_errors(changed)),'proof admits unknown fields'
        changed=copy.deepcopy(proof);changed['signature']+='='
        assert list(proof_validator.iter_errors(changed)),'proof admits padded encoding'
    assert bindings[0]['audience']!=bindings[1]['audience']
    accept,preview=fixture['accepted_proof_cases']
    try:public.verify(decode(accept['proof']['signature']),preview['signing_bytes_utf8'].encode())
    except InvalidSignature:pass
    else:raise AssertionError('accept proof became preview proof')
    token=fixture['token'];token_validator.validate(token)
    changed=copy.deepcopy(token);changed['unexpected']=True
    assert list(token_validator.iter_errors(changed)),'token admits unknown fields'
    changed=copy.deepcopy(token);changed['secret_seed']+='='
    assert list(token_validator.iter_errors(changed)),'token admits padded seed'
    # This declared client fragment must have no network, Event or current consumer.
    needle='realm-invite-link-token.schema.json'
    for name,document in schemas.items():
        if name!=needle:assert needle not in json.dumps(document),f'private credential referenced by {name}'
    openapi=(ART/'openapi/arkret-service-api.openapi.yaml').read_text(encoding='utf-8')
    assert needle not in openapi,'private credential exposed by OpenAPI'
    contract=read(ART/'registry/contract-registry.json')
    events={r['event_kind']:r for r in contract['event_kind_registry']['event_kinds']}
    operations=contract['operation_registry']['operations']
    assert not any('third_party_invite' in row['operation_id'] for row in operations)
    assert 'ak.invite.claim' not in events and 'ak.invite.third_party' not in events
    for suffix in ['create','revoke','accept']:
        row=events[PREFIX+suffix]
        assert row['effect_ownership']=={'kind':'typed_state_writer'}
        assert 'realm-invite-link.schema.json' in row['payload_schema_ref']
    assert {w['state_family'] for w in events[PREFIX+'accept']['state_writes']}=={'realm_invite_link_use','member_state'}
    assert contract['event_kind_registry']['transition_contracts']['invite_lifecycle']['states']==['pending','accepted','rejected','revoked','expired']
    for family in ['definition','lifecycle','use']:
        assert 'current_realm_invite_link_'+family in schemas['current-state.schema.json']['$defs']
    assert not (ROOT/'spec/v1/zh/sync/third-party-invites.md').exists()
    print('Realm invite link contract: two purpose KATs, exact account binding, closed private fragment and retired IVS surface verified; native admission is a separate gate')
    return 0

if __name__=='__main__':raise SystemExit(main())
