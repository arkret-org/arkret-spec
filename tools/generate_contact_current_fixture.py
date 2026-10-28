#!/usr/bin/env python3
"""Generate deterministic source-signed Contact-current conformance inputs."""
from __future__ import annotations
import argparse
from copy import deepcopy
import json
from pathlib import Path
try:
    from .check_contact_round_kat import signed_fact, digest, canonical_json, TEST_PUBLIC_KEY
except ImportError:
    from check_contact_round_kat import signed_fact, digest, canonical_json, TEST_PUBLIC_KEY

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'spec/v1/artifacts/fixtures/contact-current-state-fixture.json'

def build() -> dict:
    round_fixture = json.loads((OUT.parent / 'contact-round-kat.json').read_text())
    source = round_fixture['producer_signer_kat']['cases'][0]['signed_object']
    at = source['core']['accepted_at']
    holder,peer = source['core']['holder'],source['core']['peer']
    round_id=round_fixture['cases'][0]['expected_contact_round_id']
    ref = source['core']['request_event_ref']
    proof=signed_fact({'trust_domain_id':'ak:trust_domain:fixture','holder':holder,'peer':peer,
        'initial_contact_round_id':round_id,'contact_round_id':round_id,
        'issuer_id':source['core']['issuer_id'],'head_event_ref':ref,'version':12,
        'scope_instances':[{'contact_scope':'direct_message','grant_event_ref':ref}],
        'issued_at':at,'cache_expires_at':'2026-10-21T23:59:59.000Z'},source['signature']['verification_method'],at)
    request={'kind':'current_refresh','idempotency_key':'contact-current-refresh-0001','requester':peer,
        'trust_domain_id':'ak:trust_domain:fixture','known_version':0,'grant_event_refs':[],
        'contact_address':{'recipient':holder,'service_resolution':{
            'resolution_url':'https://station-a.example/.well-known/did.json',
        }}}
    cases=[{'name':'source_current_signed','schema_ref':'schemas/contact-operations.schema.json#/$defs/contact_current_proof','expect_valid':True,'instance':proof}]
    for name,field,value in [('wrong_unknown_field','verified',True),('old_shared_head_flag','terminal',True),('old_complete_through','complete_through',12),('old_prefix','accepted_commit_event_ids',[ref])]:
        x=deepcopy(proof);x[field]=value
        cases.append({'name':name,'schema_ref':cases[0]['schema_ref'],'expect_valid':False,'first_expected_error':"$: Additional properties are not allowed ('"+field+"' was unexpected)",'instance':x})
    for field in ['holder','trust_domain_id','version','scope_instances','issued_at','signature']:
        x=deepcopy(proof);del x[field]
        cases.append({'name':'missing_'+field,'schema_ref':cases[0]['schema_ref'],'expect_valid':False,'first_expected_error':'$: '+repr(field)+' is a required property','instance':x})
    cases.append({'name':'refresh_without_old_mirror_valid','schema_ref':'schemas/contact-operations.schema.json#/$defs/peer_contact_submit_request_body','expect_valid':True,'instance':request})
    rows=[]
    for n in [1,2,65,1000]:
        rows.append({'name':f'bounded_slot_after_{n}_rounds','rule':'bounded_slot','input':{'round_count':n,'current_request_refs':[ref],'operation_version':n*3},'expected':{'current_request_count':1,'history_scan_required':False}})
    for name,before,after,expected in [
        ('scope_aba_readd',{},['direct_message'],{'direct_message':'E12'}),
        ('scope_retained',{'direct_message':'E10'},['direct_message','presence'],{'direct_message':'E10','presence':'E12'}),
        ('scope_empty',{'direct_message':'E10'},[],{}),
    ]:
        rows.append({'name':name,'rule':'scope_instances','input':{'before':before,'scopes':after,'event_ref':'E12'},'expected':expected})
    for name,old,new,expected in [('refresh_same_operation','E8','E8','same_operation'),('same_version_other_operation','E8','X8','conflict')]:
        rows.append({'name':name,'rule':'same_version','input':{'old_event':old,'new_event':new,'old_version':8,'new_version':8},'expected':expected})
    for name,closed,round_,expected in [('known_close_blocks_old_accept',['R1'],'R1',False),('old_close_does_not_close_new',['R1'],'R2',True)]:
        rows.append({'name':name,'rule':'round_live','input':{'closed':closed,'round':round_},'expected':expected})
    for name,operation,remote_fresh,expected in [('revoke_offline','revoke',False,True),('narrow_offline','narrow',False,True),('request_offline','request',False,True),('founding_stale','founding',False,False),('widen_stale','widen',False,False),('widen_fresh','widen',True,True),('ordinary_send_lease_expired','ordinary_send',False,True)]:
        rows.append({'name':name,'rule':'freshness','input':{'operation':operation,'remote_fresh':remote_fresh,'verified_interval':True,'known_close':False},'expected':expected})
    for reason in ['not_found','policy_deny','quota_drop','hidden_pending']:
        rows.append({'name':'opaque_'+reason,'rule':'disclosure','input':{'reason':reason,'disclosable_fact':False},'expected':{'status':'deferred','material':None}})
    for name,choice,next_choice,expected in [('glare_to_normal','glare','normal',False),('glare_to_reject','glare','reject',False),('glare_exact_retry','glare','glare',True),('normal_to_glare','normal','glare',False)]:
        rows.append({'name':name,'rule':'consume','input':{'choice':choice,'next_choice':next_choice},'expected':expected})
    return {'generated_by':'tools/generate_contact_current_fixture.py','spec_anchor':'spec/v1/zh/identity/contact-and-direct-conversation.md',
        'covers_vectors':['ak.vector.contact.current_state.v1'],
        'source_refs':['spec/v1/artifacts/schemas/contact-operations.schema.json','spec/v1/zh/identity/contact-and-direct-conversation.md'],
        'description':'Deterministic Ed25519 source current, closed-shape negatives and executable reference transitions. Event refs and lifecycle rows are synthetic conformance inputs, not verified native identity, live HTTP/PG admission, or complete holder-Event proofs.',
        'runner':{'kind':'json_schema_and_semantic_cases','command':'python -B -m unittest tools.test_contact_current_contract'},
        'source_public_key_b64u':TEST_PUBLIC_KEY,
        'signed_current':proof,'canonical_unsigned':canonical_json({k:v for k,v in proof.items() if k!='signature'}),
        'expected_signed_digest':digest(proof),'schema_validation_cases':cases,'decision_cases':rows}

def main() -> int:
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    expected=json.dumps(build(),ensure_ascii=False,indent=2)+'\n'
    if args.check:
        if not OUT.exists() or OUT.read_text()!=expected:raise SystemExit('Contact current fixture drift; regenerate from source inputs')
    else:OUT.write_text(expected, encoding="utf-8", newline="\n")
    print('Contact current fixture deterministic inputs OK')
    return 0
if __name__=='__main__':raise SystemExit(main())
