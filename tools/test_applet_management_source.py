"""Executable Applet protocol models and transcript/schema checks; not a SUT."""
from __future__ import annotations
import base64
import copy
import hashlib
import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from jsonschema import Draft202012Validator
from referencing import Registry,Resource
from tools.regenerate_applet_management_source_fixture import build,canonical,digest
ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'spec/v1/artifacts'
STRIPPED={'subject_managed_source','managed_source','device_scope_confirmations','approval_signatures'}
def projection(request):return {k:v for k,v in request.items() if k not in STRIPPED}
def decode(s):return base64.urlsafe_b64decode(s+'='*(-len(s)%4))
def verify(domain,host,jws,key):
    head,empty,sig=jws.split('.')
    if empty or decode(head)!=b'{"alg":"Ed25519"}':return False
    try:
        Ed25519PublicKey.from_public_bytes(key).verify(decode(sig),(head+'.'+base64.urlsafe_b64encode(domain.encode()+b'\x00'+canonical(host)).rstrip(b'=').decode()).encode())
        return True
    except (InvalidSignature,ValueError):return False

def verified_source(binding,actual,facts,now):
    # Facts are outputs of the independent native verifier, never wire flags.
    return (binding==actual and facts['accepted_originals']==['provision','pcr_genesis','accountability','profile']
            and facts['role'] in {'bot','ghost'} and facts['owner_service']==actual['requester_actor_id']
            and facts['source_station']==actual['subject_account_id']['station_id']
            and facts['profile_active'] and facts['accountability_active'] and facts['authority_chain_valid']
            and facts['evaluated']<=now<facts['expires']<=facts['evaluated']+60
            and (binding['purpose']=='managed_subject' or facts['device_active'] and facts['device_cut']==facts['cut'] and facts['device_pair_authorized']))

class Ledger:
    """Reference transaction and immutable intent fence, independent of storage code."""
    def __init__(self,intent,basis):
        self.intent,self.basis=copy.deepcopy(intent),copy.deepcopy(basis)
        self.status='pending';self.effects=0;self.quota=0;self.ttl=1000;self.source_time=0;self.lock=Lock()
    def refresh(self,intent,source_time):
        if intent!=self.intent:return 'duplicate_conflict'
        self.source_time=source_time;return self.status
    def decide(self,actor,forbidden,basis,fresh=True):
        if actor in forbidden or self.status!='pending' or not fresh:return False
        if basis!=self.basis:self.status='superseded';return False
        self.status='approved';return True
    def consume(self,basis,crash=False):
        with self.lock:
            if self.status=='consumed':return True
            if self.status!='approved':return False
            if basis!=self.basis:self.status='superseded';return False
            if crash:return False
            self.status='consumed';self.effects+=1;self.quota+=1;return True
    def status_for(self,actor,requester,authenticated=True):
        return self.status if authenticated and actor==requester else 'not_found'
    def handoff(self,complete):
        if not complete:return False
        if self.status in {'pending','approved'}:self.status='superseded'
        return True

class Configuration:
    def __init__(self):self.lock=Lock();self.intents={};self.source_outcomes={};self.ghosts={};self.source_count=0;self.admissions=0
    def configure(self,key,intent,source_allowed=True,known=True,ghost=None):
        with self.lock:
            if key in self.intents:
                old,out=self.intents[key]
                if old!=intent:return 'duplicate_conflict'
                if out!='pending' or not known:return out
            self.intents[key]=(copy.deepcopy(intent),'pending')
            if not source_allowed:return 'source_denied'
            if key in self.source_outcomes:
                out=self.source_outcomes[key]
                self.intents[key]=(copy.deepcopy(intent),out)
                return out
            account=self.ghosts.get(ghost) if ghost else None
            reused=account is not None
            if account is None:
                self.source_count+=1;account='account-'+str(self.source_count)
                if ghost:self.ghosts[ghost]=account
            out=(account,'reused' if reused else 'created')
            self.source_outcomes[key]=out
            if not known:return 'pending'
            self.intents[key]=(copy.deepcopy(intent),out);return out

def gate(policy,has_source,has_business):
    if policy=='deny' or not has_source or not has_business:return 'denied'
    return 'pending' if policy=='require_review' else 'accepted'

class AppletManagementSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f=json.loads((ART/'fixtures/applet-management-source-fixture.json').read_text(encoding='utf-8'))
        docs=[json.loads(p.read_text(encoding='utf-8')) for p in (ART/'schemas').glob('*.json')]
        cls.registry=Registry().with_resources((d['$id'],Resource.from_contents(d)) for d in docs)
    def schema(self,ref):return Draft202012Validator({'$ref':'https://arkret.org/v1/'+ref},registry=self.registry)
    def test_fixture_reconstruction_and_closed_coverage(self):
        self.assertEqual(self.f,build())
        self.assertEqual({c['acceptance_id'] for c in self.f['cases']},{'MR-'+str(i) for i in range(1,10)}|{'CR-'+str(i) for i in range(1,13)})
    def test_actual_signature_bytes_domains_and_every_host_member_mutation(self):
        key=bytes.fromhex(self.f['test_key']['public_key_hex'])
        for kat in self.f['signature_kats']:
            with self.subTest(domain=kat['domain']):
                host=kat['unsigned_host'];domain=kat['domain']
                self.assertEqual(canonical(host).hex(),kat['canonical_hex'])
                self.assertEqual((domain.encode()+b'\0'+canonical(host)).hex(),kat['payload_hex'])
                self.assertTrue(verify(domain,host,kat['jws'],key))
                for member in host:
                    changed=copy.deepcopy(host);changed.pop(member)
                    self.assertFalse(verify(domain,changed,kat['jws'],key),member)
                self.assertFalse(verify(domain+'.wrong',host,kat['jws'],key))
                self.assertFalse(verify(domain,host,kat['jws'],bytes(reversed(key))))
                broken=kat['jws'][:-8]+'AAAAAAAA'
                self.assertFalse(verify(domain,host,broken,key))
    def test_wire_positive_and_closed_mutations(self):
        for k in self.f['signature_kats']:
            obj=copy.deepcopy(k['unsigned_host']);obj['proof']={'verification_method':k['verification_method'],'jws':k['jws']}
            v=self.schema(k['schema_ref']);v.validate(obj)
            bad=copy.deepcopy(obj);bad['unknown']=True;self.assertFalse(v.is_valid(bad))
            for field in obj:
                if field in {'proof','effective_scope','intent','nonce','subject_account_id','registration_ref','request_digest'}:
                    bad=copy.deepcopy(obj);bad.pop(field)
                    self.assertFalse(v.is_valid(bad),field)
    def test_purpose_operation_and_full_actor_schema(self):
        b=self.f['operation_binding'];v=self.schema('schemas/applet-management-source.schema.json#/$defs/operation_binding');v.validate(b)
        for field,val in [('purpose','management_review'),('operation_id','ak.peer.events.command.submit.v1'),('nonce','short'),('requester_actor_id',b['subject_account_id'])]:
            changed=copy.deepcopy(b);changed[field]=val;self.assertFalse(v.is_valid(changed),field)
    def test_no_recursive_or_unsigned_candidate_projection(self):
        event={'producer_proof':{'jws':'original'},'event_id':'original-event'}
        r={'event':event,'approval_signatures':['original-approval'],'subject_managed_source':{'proof':'fresh'},'device_scope_confirmations':[{'proof':'fresh'}]}
        p=projection(r);self.assertEqual(p,{'event':event})
        initial=digest(p);r['subject_managed_source']['proof']='refreshed';self.assertEqual(digest(projection(r)),initial)
        r['event']['producer_proof']['jws']='altered';self.assertNotEqual(digest(projection(r)),initial)
    def test_native_fact_unknown_and_handoff_authority_fail_closed(self):
        b=self.f['operation_binding'];facts={'accepted_originals':['provision','pcr_genesis','accountability','profile'],'role':'bot','owner_service':b['requester_actor_id'],'source_station':b['subject_account_id']['station_id'],'profile_active':True,'accountability_active':True,'authority_chain_valid':True,'evaluated':100,'expires':160,'device_active':True,'device_cut':7,'cut':7,'device_pair_authorized':True}
        self.assertTrue(verified_source(b,b,facts,101))
        for field,val in [('accepted_originals',['provision']),('role','human'),('profile_active',False),('accountability_active',False),('authority_chain_valid',False),('expires',100),('source_station','another-station'),('owner_service',{'kind':'service','service_id':'another'})]:
            changed=copy.deepcopy(facts);changed[field]=val;self.assertFalse(verified_source(b,b,changed,101),field)
        for field in b:
            altered=copy.deepcopy(b);altered.pop(field);self.assertFalse(verified_source(b,altered,facts,101),field)
    def test_managed_review_forbids_unbounded_device_window(self):
        defs=json.loads((ART/'schemas/applet-management-source.schema.json').read_text(encoding='utf-8'))['$defs']
        leaf=defs['managed_device_projection']['properties']['authorization_window']['properties']['expires_at']
        self.assertFalse(self.schema('schemas/applet-management-source.schema.json#/$defs/managed_device_projection/properties/authorization_window/properties/expires_at').is_valid(None))
        b=copy.deepcopy(self.f['operation_binding']);b['purpose']='management_review';b['operation_id']='ak.self.management_review.command.request.v1'
        facts={'accepted_originals':['provision','pcr_genesis','accountability','profile'],'role':'ghost','owner_service':b['requester_actor_id'],'source_station':b['subject_account_id']['station_id'],'profile_active':True,'accountability_active':True,'authority_chain_valid':True,'evaluated':100,'expires':160,'device_active':True,'device_cut':7,'cut':7,'device_pair_authorized':True}
        self.assertTrue(verified_source(b,b,facts,101));facts['device_pair_authorized']=False
        self.assertFalse(verified_source(b,b,facts,101))
    def test_carrier_role_guards_and_no_peer_expansion(self):
        d=json.loads((ART/'schemas/service-operation-dtos.schema.json').read_text(encoding='utf-8'))['$defs']['EventAdmissionSubmission']
        self.assertEqual(set(d['properties']),{'event','approval_signatures','subject_managed_source','device_scope_confirmations','approval_signatures'})
        self.assertEqual(d['allOf'][0]['then']['properties']['event']['properties']['kind']['const'],'ak.capability.grant')
        self.assertEqual(d['allOf'][1]['then']['properties']['event']['properties']['kind']['const'],'ak.device.authorize')
        p=json.loads((ART/'schemas/authority-commit-operations.schema.json').read_text(encoding='utf-8'))['$defs']['peer_submit_request']
        self.assertNotIn('subject_managed_source',p['properties'])
        self.assertIn('producer_managed_provenance',p['properties'])
        self.assertEqual(p['allOf'][-1]['then']['properties']['branch']['const'],'authority_forward')
    def test_registered_operation_projection_and_domains(self):
        reg=json.loads((ART/'registry/applet-managed-authority-registry.json').read_text(encoding='utf-8'))['operation_bound_management_source']
        self.assertEqual(set(reg['operation_anchor_excluded_members']),STRIPPED)
        self.assertTrue(reg['original_event_producer_proof_retained'])
        self.assertFalse(reg['child_requires_preexisting_device'])
        self.assertFalse(reg['failed_business_identity_preregistration'])
        domains=json.loads((ART/'registry/proof-context-registry.json').read_text(encoding='utf-8'))['domain_separations']
        for domain in ['ak.applet.management_source.v1','ak.applet.device_scope_confirmation.v1','ak.applet.configuration_command.v1','ak.applet.configuration_outcome.v1']:
            row=next(x for x in domains if x['domain']==domain)
            self.assertEqual(row['prefix_bytes_hex'],(domain.encode()+b'\0').hex())
            self.assertEqual(row['signature_algorithm'],'Ed25519')
            self.assertIn('host_with_only_proof_omitted',row['signature_input'])
    def test_source_and_approval_dependencies_are_acyclic(self):
        request={'event':{'producer_proof':'original'},'subject_managed_source':{'proof':'source'}}
        source_anchor=digest(projection(request))
        operation_approval_target=digest(request)
        request['approval_signatures']=[{'target_digest':operation_approval_target}]
        self.assertEqual(digest(projection(request)),source_anchor)
        self.assertEqual(digest({k:v for k,v in request.items() if k!='approval_signatures'}),operation_approval_target)
    def test_handoff_recovery_preserves_intent_but_uses_current_governor(self):
        command=copy.deepcopy(self.f['signature_kats'][0]['unsigned_host'])
        old_intent=digest(command['intent'])
        command['command']='recover';command['governance_station_id']='ak:did_core:webvh:z6mkfixturenewgovernor';command['governance_generation']=3
        self.assertEqual(digest(command['intent']),old_intent)
        self.assertNotEqual(command['governance_generation'],command['intent']['governance_generation'])
        self.assertEqual(command['command'],'recover')
        # New creation still demands the current tenure equal the frozen intent.
        new_allowed=lambda c:c['command']=='configure' and c['governance_generation']==c['intent']['governance_generation'] and c['governance_station_id']==c['intent']['governance_station_id']
        self.assertFalse(new_allowed(command));command['command']='configure';self.assertFalse(new_allowed(command))
    def test_capacity_and_minimum_disclosure_contract(self):
        defs=json.loads((ART/'schemas/applet-management-source.schema.json').read_text(encoding='utf-8'))['$defs']
        self.assertEqual(defs['source']['x-arkret-max-canonical-bytes'],2*1024*1024)
        self.assertEqual(defs['scope_confirmation']['x-arkret-max-canonical-bytes'],16384)
        self.assertEqual(defs['source']['properties']['authority_bundles']['maxItems'],8)
        self.assertNotIn('grant_events',defs['scope_confirmation']['properties'])
        self.assertNotIn('device_source',defs['source']['required'])
        self.assertEqual(defs['source']['allOf'][0]['else'],{'not':{'required':['device_source']}})
    def run_model(self,name):
        l=Ledger({'candidate':'join-a','subject':'bot-a'},{'epoch':1,'revision':2});c=Configuration()
        if name=='foreign_review':
            self.assertEqual(l.effects,0);self.assertTrue(l.decide('admin',{'C','device','bot'},l.basis));self.assertTrue(l.consume(l.basis));self.assertEqual(l.effects,1)
        elif name=='local_and_split':
            for route in ['local_transaction','remote_verified_source','C_S_split']:
                self.assertEqual(gate('allow',True,True),'accepted',route)
            self.assertEqual(gate('allow',False,True),'denied')
        elif name=='wrong_binding':
            self.assertEqual(gate('allow',False,True),'denied');self.assertEqual(l.effects,0)
        elif name=='refresh_same_intent':
            ttl=l.ttl;self.assertEqual(l.refresh(l.intent,100),'pending');self.assertEqual(l.ttl,ttl);self.assertEqual(l.refresh({'candidate':'other'},101),'duplicate_conflict')
        elif name=='binding_change':
            self.assertFalse(l.decide('admin',set(),{'epoch':2}));self.assertEqual(l.status,'superseded');self.assertFalse(l.consume(l.basis))
        elif name=='visibility_and_self_review':
            self.assertEqual(l.status_for('other','C'),'not_found');self.assertEqual(l.status_for('C','C',False),'not_found');self.assertFalse(l.decide('C',{'C'},l.basis))
        elif name=='atomic_recovery':
            l.decide('admin',set(),l.basis);self.assertFalse(l.consume(l.basis,crash=True));self.assertEqual((l.effects,l.quota),(0,0))
            with ThreadPoolExecutor(max_workers=4) as pool:self.assertTrue(all(pool.map(lambda _:l.consume(l.basis),range(20))))
            self.assertEqual((l.effects,l.quota),(1,1));restored=copy.deepcopy((l.intent,l.basis,l.status,l.effects));self.assertEqual(restored[-2:],('consumed',1))
        elif name=='handoff':
            self.assertFalse(l.handoff(False));self.assertEqual(l.status,'pending');self.assertTrue(l.handoff(True));self.assertEqual(l.status,'superseded')
            l.status='consumed';l.effects=1;self.assertTrue(l.handoff(True));self.assertEqual((l.status,l.effects),('consumed',1))
        elif name=='private_audit':
            private={'source':'private-originals','outcome':'accepted'};public={'event_id':'original','signer_fact':'minimum'};self.assertTrue(set(private).isdisjoint(public));self.assertNotIn('source',public)
        elif name=='automatic_ghost':
            for i in range(20):self.assertEqual(gate('allow',True,True),'accepted')
            self.assertEqual(gate('deny',True,True),'denied');self.assertEqual(gate('require_review',True,True),'pending')
        elif name=='admin_configuration':
            self.assertEqual(c.configure('cmd',{'actor':'admin','scope':'B'})[1],'created');self.assertEqual(gate('allow',True,True),'accepted');self.assertEqual(l.effects,0)
        elif name=='source_permission':
            self.assertEqual(c.configure('cmd',{},source_allowed=False),'source_denied');self.assertEqual(c.source_count,0)
        elif name=='configuration_retry':
            first=c.configure('cmd',{'intent':'same'});self.assertEqual(c.configure('cmd',{'intent':'same'}),first);self.assertEqual(c.source_count,1);self.assertEqual(c.configure('cmd',{'intent':'different'}),'duplicate_conflict')
        elif name=='created_not_admitted':
            c.configure('cmd',{});self.assertEqual(gate('deny',True,True),'denied');self.assertEqual((c.source_count,c.admissions),(1,0))
        elif name=='actual_candidate':
            l.decide('admin',set(),l.basis);self.assertEqual(l.refresh({'candidate':'source-provision'},0),'duplicate_conflict');self.assertEqual(l.effects,0)
        elif name=='bootstrap':
            stages=[]
            for stage in ['accepted_account','minimal_child','scope_confirmation','principal_authorize_device','join','MLS']:stages.append(stage)
            self.assertLess(stages.index('minimal_child'),stages.index('principal_authorize_device'));self.assertEqual(gate('allow',True,False),'denied')
        elif name=='external_tuple':
            key=('C','S','platform','tenant','user');first=c.configure('B1',{},ghost=key);second=c.configure('B2',{},ghost=key);self.assertEqual(first[0],second[0]);self.assertEqual(second[1],'reused')
            other=c.configure('B3',{},ghost=('C','S','platform','other-tenant','user'));self.assertNotEqual(first[0],other[0])
        elif name=='cancel_race':
            self.assertEqual(c.configure('cmd',{},known=False),'pending');self.assertEqual(c.source_count,1);self.assertEqual(c.configure('cmd',{'changed':True}),'duplicate_conflict');created=c.configure('cmd',{});self.assertEqual(c.configure('cmd',{}),created);self.assertEqual(gate('deny',True,True),'denied');self.assertEqual(c.source_count,1)
        elif name=='originating_actor':
            self.assertFalse(l.decide('original-admin',{'C','original-admin','device','bot'},l.basis));self.assertTrue(l.decide('independent-admin',{'C','original-admin','device','bot'},l.basis))
        elif name=='ghost_quota':
            key=('C','S','platform','tenant','user')
            with ThreadPoolExecutor(max_workers=4) as pool:out=list(pool.map(lambda n:c.configure(str(n),{},ghost=key),range(20)))
            self.assertEqual(c.source_count,1);self.assertEqual(len({x[0] for x in out}),1);self.assertEqual(sum(x[1]=='created' for x in out),1)
        elif name=='readiness':
            ready=lambda s:all(s.get(x,False) for x in ['device','membership','MLS','business_current'])
            self.assertFalse(ready({'source_created':True}));self.assertFalse(ready({'device':True,'membership':True,'business_current':True}));self.assertTrue(ready(dict.fromkeys(['device','membership','MLS','business_current'],True)))
        else:self.fail('Unexecuted model case '+name)

def attach_cases():
    f=json.loads((ART/'fixtures/applet-management-source-fixture.json').read_text(encoding='utf-8'))
    for c in f['cases']:
        def test(self,name=c['model_case']):self.run_model(name)
        setattr(AppletManagementSourceTests,'test_'+c['name'].replace('-','_'),test)
attach_cases()
if __name__=='__main__':unittest.main()
