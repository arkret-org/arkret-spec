"""Single-point mutation tests for registered atomic admission and audited reads."""
import copy
import json
import unittest
from tools.artifact_lint.core import Lint
from tools.artifact_lint.registered_atomic_units import CONTRACT, SCHEMA, AUDIT_SCHEMA, FIXTURE, SELF, PEER, check_registered_atomic_units, contract_errors

class RegisteredAtomicUnitsTest(unittest.TestCase):
    def setUp(self):
        self.catalog=json.loads(CONTRACT.read_text());self.schema=json.loads(SCHEMA.read_text());self.audit=json.loads(AUDIT_SCHEMA.read_text());self.fixture=json.loads(FIXTURE.read_text())
    def errors(self):return contract_errors(self.catalog,self.schema,self.audit,self.fixture)
    def test_canonical_contract_and_vectors(self):
        lint=Lint();check_registered_atomic_units(lint);self.assertEqual([],lint.errors)
    def test_arbitrary_registered_unit_is_rejected(self):
        self.catalog['atomic_unit_registry']['units'].append(copy.deepcopy(self.catalog['atomic_unit_registry']['units'][0]));self.assertTrue(self.errors())
    def test_cross_stream_atomic_claim_is_rejected(self):
        self.catalog['atomic_unit_registry']['units'][-1]['same_realm_stream']=False;self.assertTrue(self.errors())
    def test_extra_audit_slot_is_rejected(self):
        self.schema['$defs']['audit_paired_event_unit_submission']['properties']['events']['maxItems']=3;self.assertTrue(self.errors())
    def test_circle_manage_cannot_bypass_audit(self):
        next(x for x in self.catalog['capability_action_registry']['actions'] if x['action']=='ak.circle.member.manage')['required_evaluator_checks']=[];self.assertTrue(self.errors())
    def test_audit_read_cannot_be_declared_read_only(self):
        next(x for x in self.catalog['operation_registry']['operations'] if x['operation_id']==SELF)['durable_effect']['kind']='none';self.assertTrue(self.errors())
    def test_peer_signature_cannot_be_removed(self):
        next(x for x in self.catalog['operation_registry']['operations'] if x['operation_id']==PEER).pop('auth_requirements');self.assertTrue(self.errors())
    def test_parallel_unsigned_selector_is_rejected(self):
        self.audit['$defs']['watch_audit_read_request']['properties']['watcher_actor_id']={};self.assertTrue(self.errors())
    def test_missing_replay_or_delivery_case_is_rejected(self):
        self.fixture['read_cases']=[x for x in self.fixture['read_cases'] if x['name']!='delivery_revoked'];self.assertTrue(self.errors())
    def test_negative_cannot_be_blessed(self):
        next(x for x in self.fixture['unit_cases'] if x['name']=='cas_conflict')['expected']='accepted_two_commits';self.assertTrue(self.errors())
    def test_read_requires_actual_producer_proof(self):
        self.audit['$defs']['peer_watch_audit_read_request'].pop('oneOf');self.assertTrue(self.errors())
    def test_audit_pair_requires_per_event_fences(self):
        self.catalog['atomic_unit_registry']['units'][-1]['replay_fence']='pair_only';self.assertTrue(self.errors())
    def test_circle_audit_exception_cannot_expand(self):
        self.catalog['atomic_unit_registry']['audit_read']['circle_authorization']['no_membership_content_history_or_mls_key_grant']=False;self.assertTrue(self.errors())
    def test_response_head_mismatch_cannot_be_blessed(self):
        next(x for x in self.fixture['response_cases'] if x['name']=='wrong_head_position')['expected']='verified_original_audit_cut';self.assertTrue(self.errors())
    def test_replayed_observation_cannot_be_replaced(self):
        next(x for x in self.fixture['response_cases'] if x['name']=='replay_cannot_replace_frozen_value')['expected']='verified_original_audit_cut';self.assertTrue(self.errors())
    def test_old_audit_cannot_query_new_value(self):
        next(x for x in self.fixture['read_cases'] if x['name']=='old_audit_cannot_query_new_value')['expected']='audit_commit_and_never_written';self.assertTrue(self.errors())

if __name__=='__main__':unittest.main()
