"""Deterministically regenerate Applet management transcript and protocol-model vectors."""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'spec/v1/artifacts/fixtures/applet-management-source-fixture.json'
SEED=bytes(range(32))
def canonical(v):
    # This corpus uses integers and BMP strings only; this is the RFC8785 subset.
    return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')
def b64(v):return base64.urlsafe_b64encode(v).rstrip(b'=').decode('ascii')
def digest(v):return 'sha256:'+hashlib.sha256(canonical(v)).hexdigest()
def sign(domain,host):
    header=b64(b'{"alg":"Ed25519"}')
    payload=domain.encode()+b'\x00'+canonical(host)
    signing=(header+'.'+b64(payload)).encode()
    sig=Ed25519PrivateKey.from_private_bytes(SEED).sign(signing)
    return {'domain':domain,'unsigned_host':host,'canonical_hex':canonical(host).hex(),'payload_hex':payload.hex(),'jws_signing_input_hex':signing.hex(),'jws':header+'..'+b64(sig)}
def build():
    ids=json.loads((ROOT/'spec/v1/artifacts/fixtures/managed-governance-fixture.json').read_text(encoding='utf-8'))['identities']
    scope={'kind':'realm','realm_id':ids['realm_id']}; station='ak:did_core:webvh:z6mkfixturegovernor'
    event='ak:event:AQJmSg1s9QyzppFeJL40dN92YVHZeLdBBt3UWHa9XNOD'
    commit={'event_id':event,'commit_id':'ak:realm_commit:ARNRmzDi2r78zveOLmoHOb6AephFMwVuGE1fwXmCoeo4','stream_ref':scope,'stream_position':4}
    intent={'request_id':'ak:request:019640ed-8000-7000-8000-000000000001','applet_id':ids['applet_id'],'service_id':ids['service']['service_id'],'governance_station_id':station,'governance_generation':2,'effective_scope':scope,'registration_ref':commit,'registration_epoch':'sha256:'+'a'*64,'originating_actor_id':ids['alice'],'selection':{'kind':'new_bot','display_name':'Bridge helper'}}
    binding={'purpose':'managed_subject','operation_id':'ak.self.events.command.submit.v1','request_digest':'sha256:'+'b'*64,'requester_actor_id':ids['service'],'governance_station_id':station,'governance_generation':2,'effective_scope':scope,'subject_account_id':ids['bot']['account_id'],'nonce':'AAECAwQFBgcICQoLDA0ODw'}
    confirmation={'applet_id':ids['applet_id'],'service_id':ids['service']['service_id'],'source_station_id':ids['bot']['account_id']['station_id'],'subject_account_id':ids['bot']['account_id'],'device_id':'ak:device:019640ed-8000-7000-8000-000000000001','governance_station_id':station,'governance_generation':2,'effective_scope':scope,'registration_ref':commit,'registration_epoch':'sha256:'+'a'*64,'grant_ids':['ak:grant:'+b64(b'\x01'+hashlib.sha256(b'applet-management-parent').digest())],'request_digest':'sha256:'+'c'*64,'nonce':binding['nonce'],'evaluated_at':'2026-10-19T08:00:00.000Z','expires_at':'2026-10-19T08:01:00.000Z'}
    command={'command':'configure','intent':intent,'governance_station_id':station,'governance_generation':2,'issued_at':'2026-10-19T08:00:00.000Z','expires_at':'2026-10-19T08:05:00.000Z'}
    outcome={'request_id':'ak:request:019640ed-8000-7000-8000-000000000001','intent_digest':digest(intent),'service_id':ids['service']['service_id'],'status':'created','subject_account_id':ids['bot']['account_id'],'creation_refs':[dict(commit,stream_position=i) for i in range(4)],'evaluated_at':'2026-10-19T08:00:00.000Z'}
    kats=[sign('ak.applet.configuration_command.v1',command),sign('ak.applet.configuration_outcome.v1',outcome),sign('ak.applet.device_scope_confirmation.v1',confirmation)]
    for k,schema in zip(kats,['applet-configuration-operations.schema.json#/$defs/execution_request','applet-configuration-operations.schema.json#/$defs/execution_outcome','applet-management-source.schema.json#/$defs/scope_confirmation']):k['schema_ref']='schemas/'+schema
    for k in kats:
        k['verification_method']='did:webvh:z6mkfixtureapplet:applet.example#fixture' if k['domain']=='ak.applet.configuration_outcome.v1' else 'did:webvh:z6mkfixturegovernor:governor.example#fixture'
    cases=[('MR-1','foreign_review'),('MR-2','local_and_split'),('MR-3','wrong_binding'),('MR-4','refresh_same_intent'),('MR-5','binding_change'),('MR-6','visibility_and_self_review'),('MR-7','atomic_recovery'),('MR-8','handoff'),('MR-9','private_audit'),('CR-1','automatic_ghost'),('CR-2','admin_configuration'),('CR-3','source_permission'),('CR-4','configuration_retry'),('CR-5','created_not_admitted'),('CR-6','actual_candidate'),('CR-7','bootstrap'),('CR-8','external_tuple'),('CR-9','cancel_race'),('CR-10','originating_actor'),('CR-11','ghost_quota'),('CR-12','readiness')]
    return {'version':'2026-10-19.2','suite':'applet_management_source','fixture_kind':'semantic','runner':{'kind':'named_suite','entrypoint':'ak.suite.applet.management_source.v1','in_tree_checker':'tools/test_applet_management_source.py'},'covers_vectors':['ak.vector.applet.management_source.v1'],'generated_by':'tools/regenerate_applet_management_source_fixture.py','description':'Executable reference models plus real deterministic Ed25519 outer transcript KATs. Referenced IDs and creation refs are shape material, not proof of accepted native Events. Native four-Event/Commit/current verification and all production MR/CR live runs remain required; no SUT or complete native signature-chain claim. Source binding tests are separate from whole-source cryptographic/native acceptance.','test_key':{'seed_hex':SEED.hex(),'public_key_hex':Ed25519PrivateKey.from_private_bytes(SEED).public_key().public_bytes(Encoding.Raw,PublicFormat.Raw).hex(),'verification_method':'did:webvh:z6mkfixturegovernor:governor.example#fixture'},'operation_binding':binding,'signature_kats':kats,'cases':[{'name':label+'_'+name,'acceptance_id':label,'model_case':name} for label,name in cases]}
def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args();text=json.dumps(build(),ensure_ascii=False,indent=2)+'\n'
    if a.check:
        if not OUT.exists() or OUT.read_text(encoding='utf-8')!=text:raise SystemExit('Applet management source fixture drift')
        print('Applet management source fixture deterministic: ok')
    else:OUT.write_text(text,encoding='utf-8',newline='\n')
if __name__=='__main__':main()
