"""Deterministically regenerate Applet management transcript and protocol-model vectors."""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
from pathlib import Path
import sys
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
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
    signature=Ed25519PrivateKey.from_private_bytes(SEED).sign(signing)
    return {'domain':domain,'unsigned_host':host,'canonical_hex':canonical(host).hex(),'payload_hex':payload.hex(),'jws_signing_input_hex':signing.hex(),'jws':header+'..'+b64(signature)}

def governance_delivery_kats():
    """Real Event/Commit/HTTP signatures; qualified key/source rows, not native admission."""
    import copy
    from tools.regenerate_crypto_signature_fixture import refresh_jws_input
    from tools.regenerate_detached_object_signature_kat import make_signature
    ids=json.loads((ROOT/'spec/v1/artifacts/fixtures/managed-governance-fixture.json').read_text(encoding='utf-8'))['identities']
    realm=ids['realm_id']; service=ids['service']; applet=ids['applet_id']
    scope={'kind':'realm','realm_id':realm}
    stream={'kind':'realm','realm_id':realm}; at='2026-09-20T00:00:00.000Z'
    old_seed=bytes(range(32)); new_seed=bytes(range(32,64)); authority_seed=bytes(range(64,96))
    old_vm='did:webvh:z6mkfixtureapplet:applet.example#service-old'
    new_vm='did:webvh:z6mkfixtureapplet:applet.example#service-current'
    authority_vm='did:webvh:z6mkfixturegovernor:governor.example#authority-signing-key'
    def token(kind,value):return 'ak:'+kind+':'+b64(b'\x01'+hashlib.sha256(canonical(value)).digest())
    def event(kind,payload,actor,authorization=None,signing_seed=None,signing_method=None,created_at=None):
        vm=signing_method or (old_vm if actor['kind']=='service' else 'did:webvh:z6mkfixturealice:alice.example#ak:device:01904100-0000-7000-8000-000000000012')
        signed_at=created_at or at
        body={'kind':kind,'realm_id':realm,'scope_ref':stream,'actor_id':actor,'created_at':signed_at,'payload':payload}
        if actor['kind']=='service':body['applet_id']=applet
        if authorization is not None:body['authorization_ref']=authorization
        binding={'context':'ak.event_proof.v1','event_digest':digest(body),'actor_id':actor,'verification_method':vm,'created_at':signed_at}
        signing=refresh_jws_input({'protected_header':{'alg':'Ed25519'}},canonical(binding))
        proof={'kind':'detached_jws','verification_method':vm,'event_digest':digest(body),'created_at':signed_at,'jws':signing.decode().split('.')[0]+'..'+b64(Ed25519PrivateKey.from_private_bytes(signing_seed or old_seed).sign(signing))}
        return {**body,'event_id':token('event',body),'producer_proof':proof}
    root_ref={'kind':'realm_root','realm_id':realm,'authority_event_ref':token('event',{'source':'qualified_root'}),'authority_generation':'0'}
    binding={'constraint_kind':'authority_control','constraint_subkind':'applet_authority','effect':'allow','evaluation_class':'grant_local','applet_id':applet,'executed_by':service,'registration_epoch':'sha256:'+'a'*64}
    parent={'schema':'ak.schema.capability.v1','realm_id':realm,'issuer_id':ids['alice'],'subject':service,'actions':['ak.message.create'],'resources':[scope],
            'constraints':[binding,{'constraint_kind':'authority_control','effect':'allow','authority_regrant_allowed':True,'max_authority_depth':2,'allowed_managed_actor_roles':['bot']}],
            'issuer_authority_refs':[root_ref],'issued_at':at}
    parent_event=event('ak.capability.grant',{'grant':parent},ids['alice'])
    parent_id='ak:grant:'+parent_event['event_id'].split(':')[-1]
    child=copy.deepcopy(parent);child['issuer_id']=service;child['subject']=ids['bot'];child['issuer_authority_refs']=[{'kind':'grant','grant_id':parent_id}]
    child['constraints'][0]['executed_by']=ids['bot']
    child['constraints'][1]={'constraint_kind':'authority_control','effect':'allow','authority_regrant_allowed':False,'max_authority_depth':0}
    child_event=event('ak.capability.grant',{'grant':child},service,parent_id)
    def commit(original,position,previous,fact):
        unsigned={'realm_id':realm,'stream_ref':stream,'stream_position':position,'previous_commit_ref':previous,'event_ref':original['event_id'],'governance_generation':'0','authority_ref':root_ref['authority_event_ref'],'committed_at':at}
        unsigned['producer_signer_fact_digest']=digest(fact)
        identified={**unsigned,'commit_id':token('realm_commit',unsigned)}
        signature,_=make_signature('ak.realm_commit_signature.v1',identified,authority_vm,authority_seed)
        return {**identified,'signature':signature}
    def qualified_ref(label,stream_ref):
        return {'event_id':token('event',{'qualified_source':label}),'commit_id':token('realm_commit',{'qualified_source':label}),'stream_ref':stream_ref,'stream_position':0}
    public=b64(Ed25519PrivateKey.from_private_bytes(old_seed).public_key().public_bytes(Encoding.Raw,PublicFormat.Raw))
    authorization=qualified_ref('original_Human_Device_authorization',{'kind':'realm','realm_id':token('realm',{'qualified_source':'Human_PCR'})})
    parent_fact={'event_id':parent_event['event_id'],'actor':ids['alice'],'device_id':'ak:device:01904100-0000-7000-8000-000000000012','verification_method':parent_event['producer_proof']['verification_method'],
                 'key':{'public_key_base64url':public,'authorization_ref':authorization,'revision':{'commit_id':authorization['commit_id'],'stream_position':0},'governance_generation':'0'},'accepted_at':at}
    parent_commit=commit(parent_event,1,token('realm_commit',{'source':'qualified_predecessor'}),parent_fact)
    parent_ref={'event_id':parent_event['event_id'],'commit_id':parent_commit['commit_id'],'stream_ref':stream,'stream_position':1}
    child_fact={'event_id':child_event['event_id'],'actor':service,'verification_method':old_vm,'accepted_at':at,
                'key':{'public_key_base64url':public,'applet_id':applet,'registration_epoch':binding['registration_epoch'],'registration_ref':qualified_ref('original_registration',stream),'authorization_ref':parent_ref,'effective_scope':scope}}
    child_commit=commit(child_event,2,parent_commit['commit_id'],child_fact)
    child_id='ak:grant:'+child_event['event_id'].split(':')[-1]
    revoke=event('ak.capability.revoke',{'grant_id':child_id,'expected_commit_id':child_commit['commit_id']},service,parent_id)
    body={'applet_id':applet,'source_id':service['service_id'],'events':[revoke]}
    content=canonical(body)
    covered=['@method','@target-uri','@authority','content-digest','arkret-operation','source-service-id','destination-service-id','idempotency-key']
    def delivery(name,seed,vm,epoch,created,key,body_override=None):
        exact_content=canonical(body if body_override is None else body_override)
        exact_content_digest='sha-256=:'+base64.b64encode(hashlib.sha256(exact_content).digest()).decode()+':'
        components={'@method':'POST','@target-uri':'https://governor.example/_arkret/edge/applet/transactions','@authority':'governor.example','content-digest':exact_content_digest,'arkret-operation':'ak.edge.applet.command.transaction.v1','source-service-id':service['service_id'],'destination-service-id':'ak:did_core:webvh:z6mkfixturegovernor','idempotency-key':key}
        expires=created+60
        params='('+' '.join('"'+x+'"' for x in covered)+');created='+str(created)+';expires='+str(expires)+';keyid="'+vm+'";alg="ed25519"'
        base='\n'.join('"'+k+'": '+components[k] for k in covered)+'\n"@signature-params": '+params
        public=Ed25519PrivateKey.from_private_bytes(seed).public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
        record={'operation_id':'ak.edge.applet.command.transaction.v1','direction':'applet_to_arkret_inbound','source_id':service['service_id'],'destination_id':components['destination-service-id'],'signature_label':'sig1','verification_method':vm,'verification_key_digest':'sha256:'+hashlib.sha256(public).hexdigest(),'signature_algorithm':'ed25519','registration_epoch':epoch,'idempotency_key':key,'content_digest':exact_content_digest,'covered_components':covered,'created':created,'expires':expires}
        stable={k:v for k,v in record.items() if k not in {'created','expires'}}
        return {'name':name,'components':components,'signature_params':params,'signature_base_utf8':base,'public_key_base64url':b64(public),'signature_base64url':b64(Ed25519PrivateKey.from_private_bytes(seed).sign(base.encode())),'record':record,'stable_canonical_utf8':canonical(stable).decode(),'stable_digest':'sha256:'+hashlib.sha256(b'ak.applet.delivery_authentication_record.v1\n'+canonical(stable)).hexdigest()}
    first_current_revoke=event('ak.capability.revoke',{'grant_id':child_id,'expected_commit_id':child_commit['commit_id']},service,parent_id,
                               signing_seed=new_seed,signing_method=new_vm,created_at='2026-10-19T08:02:00.000Z')
    first_current_body={**body,'events':[first_current_revoke]}
    first_current={'event':first_current_revoke,'body':first_current_body,'delivery':delivery('first_current_key_revoke',new_seed,new_vm,'sha256:'+'b'*64,1792396920,'profile-cleanup-first-current',first_current_body)}
    return {'boundary':'Cryptographic reference KAT with explicit qualified historical source/key inputs; original Device/registration refs are explicit qualified reference inputs, not proof of native DID-history, storage admission, current-key freshness, effect-once or SUT.',
            'effect_scope':scope,'source_epoch':binding['registration_epoch'],'first_current_key_revoke':first_current,'source_rows':[{'event':parent_event,'commit':parent_commit,'producer_signer_fact':parent_fact},{'event':child_event,'commit':child_commit,'producer_signer_fact':child_fact}],
            'body':body,'canonical_body_utf8':content.decode(),'authority_public_key_base64url':b64(Ed25519PrivateKey.from_private_bytes(authority_seed).public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)),
            'deliveries':[delivery('accepted',old_seed,old_vm,'sha256:'+'a'*64,1792396800,'profile-cleanup-1'),delivery('fresh_time_retry',old_seed,old_vm,'sha256:'+'a'*64,1792396860,'profile-cleanup-1'),delivery('current_key_same_identity',new_seed,new_vm,'sha256:'+'b'*64,1792396920,'profile-cleanup-1'),delivery('current_key_new_identity',new_seed,new_vm,'sha256:'+'b'*64,1792396920,'profile-cleanup-2')]}

def build():
    ids=json.loads((ROOT/'spec/v1/artifacts/fixtures/managed-governance-fixture.json').read_text(encoding='utf-8'))['identities']
    scope={'kind':'realm','realm_id':ids['realm_id']}; station='ak:did_core:webvh:z6mkfixturegovernor'
    event='ak:event:AQJmSg1s9QyzppFeJL40dN92YVHZeLdBBt3UWHa9XNOD'
    commit={'event_id':event,'commit_id':'ak:realm_commit:ARNRmzDi2r78zveOLmoHOb6AephFMwVuGE1fwXmCoeo4','stream_ref':scope,'stream_position':4}
    intent={'request_id':'ak:request:019640ed-8000-7000-8000-000000000001','applet_id':ids['applet_id'],'service_id':ids['service']['service_id'],'governance_station_id':station,'governance_generation':"2",'effective_scope':scope,'registration_ref':commit,'registration_epoch':'sha256:'+'a'*64,'originating_actor_id':ids['alice'],'selection':{'kind':'new_bot','display_name':'Bridge helper'}}
    command={'command':'configure','intent':intent,'governance_station_id':station,'governance_generation':"2",'issued_at':'2026-10-19T08:00:00.000Z','expires_at':'2026-10-19T08:05:00.000Z'}
    outcome={'request_id':'ak:request:019640ed-8000-7000-8000-000000000001','intent_digest':digest(intent),'service_id':ids['service']['service_id'],'status':'created','actor_id':ids['bot'],'creation_refs':[dict(commit,stream_ref={'kind':'realm_control','realm_id':ids['realm_id']})],'evaluated_at':'2026-10-19T08:00:00.000Z'}
    kats=[sign('ak.applet.configuration_command.v1',command),sign('ak.applet.configuration_outcome.v1',outcome)]
    for k,schema in zip(kats,['applet-configuration-operations.schema.json#/$defs/applet_configuration_execution_request_body','applet-configuration-operations.schema.json#/$defs/execution_response_body']):k['schema_ref']='schemas/'+schema
    for k in kats:
        k['verification_method']='did:webvh:z6mkfixtureapplet:applet.example#fixture' if k['domain']=='ak.applet.configuration_outcome.v1' else 'did:webvh:z6mkfixturegovernor:governor.example#fixture'
    cases=[('MR-1','foreign_review'),('MR-2','local_and_split'),('MR-3','wrong_binding'),('MR-4','refresh_same_intent'),('MR-5','binding_change'),('MR-6','visibility_and_self_review'),('MR-7','atomic_recovery'),('MR-8','handoff'),('MR-9','private_audit'),('CR-1','automatic_ghost'),('CR-2','admin_configuration'),('CR-3','source_permission'),('CR-4','configuration_retry'),('CR-5','created_not_admitted'),('CR-6','actual_candidate'),('CR-7','bootstrap'),('CR-8','external_tuple'),('CR-9','cancel_race'),('CR-10','originating_actor'),('CR-11','ghost_quota'),('CR-12','readiness')]
    return {'runner':{'kind':'named_suite','entrypoint':'ak.suite.applet.management_source.v1','in_tree_checker':'tools/test_applet_management_source.py'},'covers_vectors':['ak.vector.applet.management_source.v1'],'generated_by':'tools/regenerate_applet_management_source_fixture.py','description':'Executable reference models plus real deterministic Ed25519 outer transcript KATs. Referenced IDs and creation refs are shape material, not proof of accepted native Events. Native Realm actor create/Commit/current verification and all production MR/CR live runs remain required; no SUT or complete native signature-chain claim. Source binding tests are separate from whole-source cryptographic/native acceptance.','governance_delivery_kats':governance_delivery_kats(),'test_key':{'seed_hex':SEED.hex(),'public_key_hex':Ed25519PrivateKey.from_private_bytes(SEED).public_key().public_bytes(Encoding.Raw,PublicFormat.Raw).hex(),'verification_method':'did:webvh:z6mkfixturegovernor:governor.example#fixture'},'signature_kats':kats,'cases':[{'name':label+'_'+name,'acceptance_id':label,'model_case':name} for label,name in cases]}
def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args();text=json.dumps(build(),ensure_ascii=False,indent=2)+'\n'
    if a.check:
        if not OUT.exists() or OUT.read_text(encoding='utf-8')!=text:raise SystemExit('Applet management source fixture drift')
        print('Applet management source fixture deterministic: ok')
    else:OUT.write_text(text,encoding='utf-8',newline='\n')
if __name__=='__main__':main()
