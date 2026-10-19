"""Validate Realm actor creation ownership and execute its replacement contract suite."""
from __future__ import annotations
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'spec/v1/artifacts/fixtures/applet-managed-actor-fixture.json'
CONTRACT = ROOT / 'spec/v1/artifacts/registry/contract-registry.json'
ENTRYPOINT = 'ak.suite.applet.managed_actor_authority.v1'
GROUPS = ['RA-ID','RA-STREAM','RA-CREATE','RA-CONTROL','RA-DEVICE','RA-CURRENT','RA-GATE','RA-MANAGER','RA-HANDOFF','RA-PRIVACY']

def run_named_suite(fixture, catalog=None):
    errors=[]
    if catalog is None: catalog=json.loads(CONTRACT.read_text(encoding='utf-8'))
    if fixture.get('runner') != {'kind':'named_suite','entrypoint':ENTRYPOINT}: errors.append('wrong runner')
    if fixture.get('creation_event_kinds') != ['ak.realm.actor.create']: errors.append('creation must be one Event')
    if fixture.get('acceptance_groups') != GROUPS: errors.append('incomplete acceptance groups')
    events={x['event_kind']:x for x in catalog['event_kind_registry']['event_kinds']}
    writes=events['ak.realm.actor.create']['result_writes']
    families=[x['result_family'] for x in writes]
    if families != ['realm_actor_identity','realm_actor_control','realm_actor_manager','realm_actor_device_generation','realm_actor_status','realm_actor_status','realm_actor_recovery']: errors.append('incorrect create effects')
    generation=next((x for x in writes if x['result_family']=='realm_actor_device_generation'),None)
    if not generation or generation['result_projection'] != {'kind':'set','value_projection':{'kind':'object','members':[{'name':'current_device_generation_ref','literal':1}]}}: errors.append('generation must initialize to one')
    recovery=next((x for x in writes if x['result_family']=='realm_actor_recovery'),None)
    if not recovery or recovery['result_projection'] != {'kind':'set','value_projection':{'kind':'object','members':[{'name':'kind','literal':'manager_native'},{'name':'enabled','literal':True},{'name':'pending','literal':None}]}}: errors.append('recovery must initialize enabled with no pending intent')
    for kind in ['ak.device.authorize','ak.realm.actor.control.update','ak.realm.create']:
        if any(x['result_family']=='realm_actor_device_generation' for x in events[kind].get('result_writes',[])): errors.append(kind+' cannot reset Realm actor generation')
    return errors

if __name__=='__main__':
    errors=run_named_suite(json.loads(FIXTURE.read_text(encoding='utf-8')))
    if errors: raise SystemExit('\n'.join(errors))
    import unittest
    from tools.test_realm_actor_contract import RealmActorContractTests
    result=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(RealmActorContractTests))
    raise SystemExit(not result.wasSuccessful())
