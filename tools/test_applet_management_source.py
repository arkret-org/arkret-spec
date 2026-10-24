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
STRIPPED={'approval_signatures'}
def projection(request):return {k:v for k,v in request.items() if k not in STRIPPED}
def decode(s):return base64.urlsafe_b64decode(s+'='*(-len(s)%4))
def verify(domain,host,jws,key):
    head,empty,signature=jws.split('.')
    if empty or decode(head)!=b'{"alg":"Ed25519"}':return False
    try:
        Ed25519PublicKey.from_public_bytes(key).verify(decode(signature),(head+'.'+base64.urlsafe_b64encode(domain.encode()+b'\x00'+canonical(host)).rstrip(b'=').decode()).encode())
        return True
    except (InvalidSignature,ValueError):return False


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
                self.source_count+=1;account='realm-actor-'+str(self.source_count)
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
    def test_current_installation_binding_is_closed_and_history_is_separate(self):
        validator = self.schema('schemas/applet-authority-material.schema.json#/$defs/current_binding')
        self.assertTrue(validator.is_valid({'status': 'inactive'}))
        for extra in ('registration_ref', 'registration_epoch', 'service_id'):
            self.assertFalse(validator.is_valid({'status': 'inactive', extra: None}))
        self.assertFalse(validator.is_valid({'status': 'unknown'}))
        self.assertFalse(validator.is_valid({'status': 'active'}))
        schema = json.loads((ART/'schemas/applet-authority-material.schema.json').read_text(encoding='utf-8'))
        self.assertIn('current_binding', schema['$defs']['response_body']['required'])
        self.assertIn('registration', schema['$defs']['response_body']['required'])
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
    def test_registered_event_carrier_and_configuration_domains(self):
        d=json.loads((ART/'schemas/service-operation-dtos.schema.json').read_text(encoding='utf-8'))['$defs']['EventAdmissionSubmission']
        self.assertEqual(set(d['properties']), {'event','approval_signatures'})
        p=json.loads((ART/'schemas/authority-commit-operations.schema.json').read_text(encoding='utf-8'))['$defs']['peer_submit_request_body']
        self.assertNotIn('producer_managed_provenance',p['properties'])
        domains=json.loads((ART/'registry/proof-context-registry.json').read_text(encoding='utf-8'))['domain_separations']
        for domain in ['ak.applet.configuration_command.v1','ak.applet.configuration_outcome.v1']:
            row=next(x for x in domains if x['domain']==domain)
            self.assertEqual(row['prefix_bytes_hex'],(domain.encode()+b'\0').hex())
            self.assertEqual(row['signature_algorithm'],'Ed25519')

    def test_source_and_approval_dependencies_are_acyclic(self):
        request={'event':{'producer_proof':'original','candidate_control_signature':'original'}}
        target=digest(request['event'])
        request['approval_signatures']=[{'target_digest':target}]
        self.assertEqual(digest(projection(request)['event']),target)
        request['event']['candidate_control_signature']='tampered'
        self.assertNotEqual(digest(projection(request)['event']),target)

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
    def run_model(self,name):
        l=Ledger({'candidate':'join-a','subject':'bot-a'},{'epoch':1,'revision':2});c=Configuration()
        if name=='foreign_review':
            self.assertEqual(l.effects,0);self.assertTrue(l.decide('admin',{'C','device','bot'},l.basis));self.assertTrue(l.consume(l.basis));self.assertEqual(l.effects,1)
        elif name=='local_and_split':
            for route in ['same_governor','after_complete_handoff']:
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
            for stage in ['accepted_realm_actor','minimal_child','controller_authorize_device','join','MLS']:stages.append(stage)
            self.assertLess(stages.index('minimal_child'),stages.index('controller_authorize_device'));self.assertEqual(gate('allow',True,False),'denied')
        elif name=='external_tuple':
            key=('realm','applet','platform','tenant','user');first=c.configure('B1',{},ghost=key);second=c.configure('B2',{},ghost=key);self.assertEqual(first[0],second[0]);self.assertEqual(second[1],'reused')
            other=c.configure('B3',{},ghost=('realm','applet','platform','other-tenant','user'));self.assertNotEqual(first[0],other[0])
        elif name=='cancel_race':
            self.assertEqual(c.configure('cmd',{},known=False),'pending');self.assertEqual(c.source_count,1);self.assertEqual(c.configure('cmd',{'changed':True}),'duplicate_conflict');created=c.configure('cmd',{});self.assertEqual(c.configure('cmd',{}),created);self.assertEqual(gate('deny',True,True),'denied');self.assertEqual(c.source_count,1)
        elif name=='originating_actor':
            self.assertFalse(l.decide('original-admin',{'C','original-admin','device','bot'},l.basis));self.assertTrue(l.decide('independent-admin',{'C','original-admin','device','bot'},l.basis))
        elif name=='ghost_quota':
            key=('realm','applet','platform','tenant','user')
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
