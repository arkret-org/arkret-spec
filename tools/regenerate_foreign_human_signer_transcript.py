"""Conformance bytes only: published fixture keys, no admission outcome."""
import argparse,copy,hashlib,json
from pathlib import Path
from tools.generate_content_bound_event_id_fixture import derive
from tools.regenerate_crypto_signature_fixture import b64u,unb64u,sign_ed25519,refresh_jws_input
from tools.regenerate_detached_object_signature_kat import jcs,make_signature,public_key,KEY_A_SEED,KEY_B_SEED,NEW_VM
from tools.artifact_lint.fixtures import base58btc_encode
ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'spec/v1/artifacts/fixtures/signer-key-historical-coordinate-fixture.json'
T='2026-09-20T00:00:00.000Z'; AT='2026-09-20T00:00:00.000Z'
DEVICE='ak:device:019a0000-0000-7000-8000-00000000000b'
HUMAN_VM='did:webvh:z6mkfixture:human.example#'+DEVICE
ORIGIN_VM='did:webvh:z6mkfixturestationexample:origin.example#assertion-fixture'
GOV_VM='did:webvh:z6mkfixturegovernor:governor.example#assertion-fixture'
DEST='ak:did_core:webvh:z6mkfixturegovernor'
def sha(v):return 'sha256:'+hashlib.sha256(jcs(v)).hexdigest()
def typed_id(kind,v):return 'ak:'+kind+':'+b64u(b'\x01'+hashlib.sha256(jcs(v)).digest())
def jws(binding,seed):
 v={'protected_header':{'alg':'Ed25519'}};msg=refresh_jws_input(v,jcs(binding))
 return msg.decode().split('.')[0]+'..'+b64u(sign_ed25519(b64u(seed),msg))
def origin_signed(core):
 b={'context':'ak.device_projection_attestation_proof.v1','payload_digest':sha({'attestation':core})}
 for k in ['account_id','device_id','device_signing_key_did','hpke_key','device_authorize_event_id','authorized_generation_ref','device_status','attested_at','expires_at']:b[k]=core[k]
 b.update(verification_method=ORIGIN_VM,created_at=core['attested_at'])
 return {'attestation':copy.deepcopy(core),'proof':{'verification_method':ORIGIN_VM,'created_at':core['attested_at'],'jws':jws(b,KEY_A_SEED)}},b
def build_transcript():
 data=json.loads((ROOT/'spec/v1/artifacts/fixtures/content-bound-event-id-fixture.json').read_text())
 source=next(c for c in data['cases'] if c.get('name')=='strand_object_id_is_retyped_event_id')
 body=json.loads(source['digest_preimage_canonical_bytes_utf8']);body['created_at']=T;body['payload']['object']['created_at']=T;digest=sha(body);_,eid=derive(1,digest.split(':')[1])
 binding={'context':'ak.event_proof.v1','event_digest':digest,'actor_id':body['actor_id'],'verification_method':HUMAN_VM,'created_at':T}
 event=dict(body,event_id=eid,producer_proof={'kind':'detached_jws','verification_method':HUMAN_VM,'event_digest':digest,'created_at':T,'jws':jws(binding,KEY_B_SEED)})
 old=json.loads(FIXTURE.read_text())['positive_case']['resolved_key'];key=copy.deepcopy(old);key['public_key_b64u']=public_key(KEY_B_SEED)
 fact={'event_id':eid,'actor':body['actor_id'],'device_id':DEVICE,'verification_method':HUMAN_VM,'key':key,'accepted_at':'2026-08-01T00:00:00.000Z'}
 request={'branch':'authority_forward','event_submission':{'event':event}}
 auth={'event_id':eid,'verification_method':HUMAN_VM,'destination_service_id':DEST,'forward_body_digest':sha(request),'authorization_ref':key['authorization_ref'],'revision':key['revision'],'governance_generation':key['governance_generation'],'accepted_at':fact['accepted_at']}
 core={'account_id':body['actor_id']['account_id'],'device_id':DEVICE,'device_signing_key_did':'did:key:z'+base58btc_encode(b'\xed\x01'+unb64u(key['public_key_b64u'])),'hpke_key':'conformance-public-hpke-fixture','device_authorize_event_id':key['authorization_ref']['event_id'],'authorized_generation_ref':2,'device_status':'active','attested_at':AT,'expires_at':'2026-09-20T00:05:00.000Z','authorization_window':{'not_before':'2026-08-01T00:00:00.000Z','expires_at':None},'event_authorization':auth}
 origin,ob=origin_signed(core);alt=copy.deepcopy(core);alt['event_authorization']['revision']['stream_position']+=1;alternate,ab=origin_signed(alt)
 af=copy.deepcopy(fact);af['key']['revision']=copy.deepcopy(alt['event_authorization']['revision'])
 u={'realm_id':body['realm_id'],'stream_ref':body['scope_ref'],'stream_position':1,'previous_commit_ref':old['revision']['commit_id'],'event_ref':eid,'governance_generation':1,'authority_ref':old['authorization_ref']['event_id'],'committed_at':'2026-09-20T00:00:00.000Z','producer_signer_fact_digest':sha(fact)}
 cid=typed_id('realm_commit',u);u=dict(commit_id=cid,**u);sig,derived=make_signature('ak.realm_commit_signature.v1',u,GOV_VM,KEY_A_SEED);commit=dict(u,signature=sig)
 target={'event_id':eid,'commit_id':cid,'stream_ref':u['stream_ref'],'stream_position':u['stream_position']};entry={'target':target,'producer_signer_fact':fact}
 original_kat=json.loads((ROOT/'spec/v1/artifacts/fixtures/detached-object-signature-kat-fixture.json').read_text())
 hu=copy.deepcopy(next(c['host_object'] for c in original_kat['cases'] if c['case_id']=='realm_authority_handoff_old'))
 for member in ['handoff_id','old_authority_signature','new_authority_acceptance_signature']:hu.pop(member,None)
 heads=[{'stream_ref':u['stream_ref'],'stream_position':u['stream_position'],'commit_id':cid}]
 hu['realm_id']=body['realm_id'];hu['from_service_id']=DEST;hu['final_stream_heads_digest']=sha(heads);hu['historical_signer_facts_digest']=sha([entry]);hu['change_event_ref']=eid;hu['change_commit_id']=cid
 hu=dict(handoff_id=typed_id('realm_authority_handoff',hu),**hu)
 old_sig,old_derived=make_signature('ak.realm_authority_handoff_old_signature.v1',hu,GOV_VM,KEY_A_SEED)
 new_sig,new_derived=make_signature('ak.realm_authority_handoff_new_acceptance_signature.v1',hu,NEW_VM,KEY_B_SEED)
 handoff=dict(hu,old_authority_signature=old_sig,new_authority_acceptance_signature=new_sig)
 return {'kind':'conformance_cryptographic_transcript_not_admission_outcome','keys':{'human_test_key_ref':'rfc8032_test_1_ed25519_key','human_public_key_b64u':public_key(KEY_B_SEED),'origin_governor_test_key_ref':'conformance_ed25519_fixture_key','origin_governor_public_key_b64u':public_key(KEY_A_SEED)},'coverage_limit':['source coordinates are fixture inputs; no actual PCR cut or admission proof','Service/DID authority chains and SQL atomicity not proven','no real accepted outcome or current permission created'],'event':event,'event_binding':binding,'origin_attestation':origin,'origin_binding':ob,'alternate_authentic_origin_attestation':alternate,'alternate_origin_binding':ab,'alternate_fact':af,'fact':fact,'commit':commit,'commit_signature_transcript':derived,'replication':{'event_submission':{'event':event},'source_commit':commit,'producer_signer_fact':fact},'handoff':handoff,'handoff_inventory':[entry],'handoff_fenced_imported_originals':[{'commit':commit,'event':event}],'handoff_signature_transcripts':[old_derived,new_derived],'peer_scan':{'committed_events':[{'commit':commit,'event':event}],'readable_floor':{'oldest_position':1,'floor_commit_id':cid,'floor_reason':'membership_join'},'truncated':False,'producer_signer_facts':[entry]}}
def main():
 p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args();f=json.loads(FIXTURE.read_text());g=build_transcript();s=f['foreign_human_historical_signer_delivery']
 if a.check:
  if s.get('crypto_transcript')!=g:print('transcript drift');return 1
  print('transcript deterministic exact match');return 0
 s['crypto_transcript']=g;s['crypto_transcript_status']='generated_real_Ed_bytes_native_authority_and_business_pending';FIXTURE.write_text(json.dumps(f,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n');print('generated actual conformance signatures; no admission outcome');return 0
if __name__=='__main__':raise SystemExit(main())
