"""Mutations of the single-Event Realm actor creation effect contract."""
import copy
import json
import unittest
from tools import check_applet_managed_actor_authority_fixture as runner
class AppletManagedActorAuthorityFixtureTest(unittest.TestCase):
    def setUp(self):
        self.f=json.loads(runner.FIXTURE.read_text(encoding='utf-8'))
        self.c=json.loads(runner.CONTRACT.read_text(encoding='utf-8'))
    def create(self): return next(x for x in self.c['event_kind_registry']['event_kinds'] if x['event_kind']=='ak.realm.actor.create')
    def test_complete(self): self.assertEqual(runner.run_named_suite(self.f,self.c),[])
    def test_missing_group(self):
        self.f['acceptance_groups'].pop();self.assertTrue(runner.run_named_suite(self.f,self.c))
    def test_no_install_or_pcr_aggregate(self):
        self.f['creation_event_kinds'].append('ak.realm.create');self.assertTrue(runner.run_named_suite(self.f,self.c))
    def test_missing_initializer(self):
        self.create()['state_writes'].pop();self.assertTrue(runner.run_named_suite(self.f,self.c))
    def test_wrong_initializer(self):
        self.create()['state_writes'][3]['state_projection']['value_projection']['members'][0]['literal']=7
        self.assertTrue(runner.run_named_suite(self.f,self.c))
    def test_wrong_recovery_initializer(self):
        row=next(x for x in self.create()['state_writes'] if x['state_family']=='realm_actor_recovery')
        row['state_projection']['value_projection']['members'][1]['literal']=False
        self.assertTrue(runner.run_named_suite(self.f,self.c))
    def test_recovery_exact_initial_values_and_recipient_derivations_are_closed(self):
        baseline=copy.deepcopy(self.c)
        for failure in ['kind','enabled','pending','missing_recipient','missing_ref','wrong_recipient','wrong_ref','duplicate','extra']:
            self.c=copy.deepcopy(baseline)
            row=next(x for x in self.create()['state_writes'] if x['state_family']=='realm_actor_recovery')
            members=row['state_projection']['value_projection']['members']
            if failure=='kind':members[0]['literal']='other'
            if failure=='enabled':members[1]['literal']=False
            if failure=='pending':members[2]['literal']={}
            if failure=='missing_recipient':members.pop(3)
            if failure=='missing_ref':members.pop(4)
            if failure=='wrong_recipient':members[3]['derivation']='realm_actor_content_backup_recipient_ref'
            if failure=='wrong_ref':members[4]['derivation']='realm_actor_content_backup_recipient'
            if failure=='duplicate':members.append(copy.deepcopy(members[3]))
            if failure=='extra':members.append({'name':'unregistered','literal':True})
            with self.subTest(failure=failure):self.assertTrue(runner.run_named_suite(self.f,self.c))
    def test_authorize_cannot_reset_generation(self):
        authorize=next(x for x in self.c['event_kind_registry']['event_kinds'] if x['event_kind']=='ak.device.authorize')
        authorize['state_writes'].append(copy.deepcopy(self.create()['state_writes'][3]))
        self.assertTrue(runner.run_named_suite(self.f,self.c))
if __name__=='__main__': unittest.main()
