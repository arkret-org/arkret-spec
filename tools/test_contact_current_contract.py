"""Closed Contact current contracts, source signatures and lifecycle counterexamples."""
from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path
import unittest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from tools.check_contact_round_kat import unb64u, verify_detached_jws, canonical_json
from tools.generate_contact_current_fixture import build, OUT

ROOT=Path(__file__).resolve().parents[1]
ARTIFACTS=ROOT/'spec/v1/artifacts'

def evaluate(row):
    x=row['input'];rule=row['rule']
    if rule=='bounded_slot':return {'current_request_count':len(x['current_request_refs']),'history_scan_required':False}
    if rule=='scope_instances':return {scope:x['before'].get(scope,x['event_ref']) for scope in x['scopes']}
    if rule=='same_version':return 'conflict' if x['old_version']==x['new_version'] and x['old_event']!=x['new_event'] else 'same_operation'
    if rule=='round_live':return x['round'] not in x['closed']
    if rule=='freshness':
        if x['operation'] in ['request','revoke','narrow','reject']:return True
        if x['operation']=='ordinary_send':return x['verified_interval'] and not x['known_close']
        return x['remote_fresh'] and not x['known_close']
    if rule=='disclosure':return {'status':'deferred','material':None} if not x['disclosable_fact'] else {'status':'accepted'}
    if rule=='consume':return x['choice']==x['next_choice']
    raise ValueError(rule)

class ContactCurrentContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=json.loads(OUT.read_text(encoding='utf-8'))
        docs=[json.loads(p.read_text(encoding='utf-8')) for p in (ARTIFACTS/'schemas').glob('*.json')]
        cls.registry=Registry().with_resources((d['$id'],Resource.from_contents(d)) for d in docs)
        cls.schema=json.loads((ARTIFACTS/'schemas/contact-operations.schema.json').read_text(encoding='utf-8'))
        cls.catalog=json.loads((ARTIFACTS/'registry/contract-registry.json').read_text(encoding='utf-8'))
    def test_deterministic_source_inputs(self):self.assertEqual(self.fixture,build())
    def test_all_closed_schema_cases(self):
        for row in self.fixture['schema_validation_cases']:
            with self.subTest(row['name']):
                v=Draft202012Validator({'$ref':'https://arkret.org/v1/'+row['schema_ref']},registry=self.registry)
                self.assertEqual(v.is_valid(row['instance']),row['expect_valid'],[e.message for e in v.iter_errors(row['instance'])])
    def test_source_signature_and_every_signed_member_mutation(self):
        proof=self.fixture['signed_current'];key=Ed25519PublicKey.from_public_bytes(unb64u(self.fixture['source_public_key_b64u']))
        body={k:v for k,v in proof.items() if k!='signature'}
        verify_detached_jws(key,proof['signature']['jws'],canonical_json(body).encode())
        for member in body:
            with self.subTest(member):
                changed=deepcopy(body);del changed[member]
                with self.assertRaises(InvalidSignature):verify_detached_jws(key,proof['signature']['jws'],canonical_json(changed).encode())
    def test_lifecycle_counterexamples(self):
        for row in self.fixture['decision_cases']:
            with self.subTest(row['name']):self.assertEqual(evaluate(row),row['expected'])
    def test_retired_members_and_operations_are_absent(self):
        defs=self.schema['$defs']
        self.assertFalse(any(k.startswith(('contact_continuity','bilateral_continuity')) for k in defs))
        kinds=[x.get('properties',{}).get('kind',{}).get('const') for x in defs['peer_contact_submit_request']['oneOf']]
        self.assertIn('current_refresh',kinds)
        self.assertNotIn('proof_refresh',kinds);self.assertNotIn('continuity_checkpoint',kinds)
        ops=[x['operation_id'] for x in self.catalog['operation_registry']['operations']]
        self.assertNotIn('ak.self.contact.command.checkpoint.v1',ops)
    def test_direction_revision_and_scope_contract_is_canonical(self):
        c=self.catalog['contact_current_contract']
        self.assertEqual(c['direction_key'],['trust_domain_id','complete_holder_actor_id','complete_peer_actor_id'])
        self.assertFalse(c['cumulative_contact_history_required'])
        self.assertFalse(c['known_closure_overwrites_own_head'])
        self.assertTrue(c['glare_choice_durable_at_attestation'])
        self.assertEqual(c['same_version_conflict_comparison'],'immutable_operation_bytes')
    def test_current_refresh_has_no_prior_mirror_dependency(self):
        branch=next(x for x in self.schema['$defs']['peer_contact_submit_request']['oneOf'] if x.get('properties',{}).get('kind',{}).get('const')=='current_refresh')
        self.assertNotIn('prior_mirror_receipt',branch['properties'])
        for field in ['requester','trust_domain_id','known_version','grant_event_refs']:self.assertIn(field,branch['required'])
    def test_five_holder_payloads_carry_lifetime_version_and_domain(self):
        payloads=json.loads((ARTIFACTS/'schemas/event-payload.schema.json').read_text(encoding='utf-8'))['$defs']
        for name in ['contact_requested_payload','contact_accepted_payload','contact_rejected_payload','contact_tombstoned_payload']:
            with self.subTest(name):
                self.assertIn('version',payloads[name]['required']);self.assertIn('trust_domain_id',payloads[name]['required'])
        for name in ['contact_requested_payload','contact_rejected_payload']:
            self.assertNotIn('contact_round_id',payloads[name]['properties'])
    def test_recovery_and_intervals_preserve_all_round_originals(self):
        defs=self.schema['$defs']
        self.assertIn('round_events',defs['contact_scope_interval']['required'])
        material=defs['contact_current_material']
        self.assertEqual(material['allOf'][0]['then']['required'],['round_events'])
        self.assertEqual(material['properties']['round_events']['maxItems'],3)
    def test_reference_results_are_not_unconditional_success(self):
        original={'rule':'consume','input':{'choice':'glare','next_choice':'normal'}}
        self.assertFalse(evaluate(original))
        original['input']['next_choice']='glare';self.assertTrue(evaluate(original))
        for fresh in [False,True]:
            self.assertEqual(evaluate({'rule':'freshness','input':{'operation':'founding','remote_fresh':fresh,'known_close':False}}),fresh)

if __name__=='__main__':unittest.main()
