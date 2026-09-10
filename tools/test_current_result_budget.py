"""Frozen semantic vectors for the request-independent current entry budget."""
import base64
import copy
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'spec/v1/artifacts'

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def jcs(value):
    # Vectors use integers and strings only; this is their RFC 8785 encoding.
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()

class CurrentBudget(unittest.TestCase):
    def test_fixed_budget_and_maximum_required_wrapper(self):
        registry = read(ART / 'registry/contract-registry.json')['current_result_registry']
        budget = registry['budgets']
        entry_schema = read(ART / 'schemas/account-current-result.schema.json')['$defs']['entry']
        self.assertEqual(budget['max_atomic_entry_canonical_bytes'], 7 * 1024 * 1024)
        self.assertEqual(entry_schema['x-arkret-max-canonical-bytes'], budget['max_atomic_entry_canonical_bytes'])
        ids = read(ART / 'schemas/common-ids.schema.json')['$defs']
        frames = read(ART / 'schemas/account-subscribe-frame.schema.json')['$defs']
        current = read(ART / 'schemas/account-current-result.schema.json')['$defs']
        self.assertEqual(ids['did_core_id']['maxLength'], 512)
        self.assertEqual(set(ids['account_id']['properties']), {'principal_id','station_id'})
        self.assertEqual(set(frames['realm_detail_baseline']['properties']), {'snapshot_cursor','cut_revision','coverage','complete'})
        self.assertEqual(set(current['coverage']['properties']), {'realm','strand_ids','members','event_ids'})
        self.assertEqual(frames['cursor_value']['maxLength'], 2048)
        self.assertEqual(current['coverage']['properties']['strand_ids']['maxItems'], 32)
        self.assertEqual(current['coverage']['properties']['event_ids']['maxItems'], 100)
        self.assertEqual(current['members_coverage']['oneOf'][1]['properties']['actor_ids']['maxItems'], 100)
        # A control character occupies six canonical bytes. Using it for every
        # code point overestimates even the mandatory DID prefix, so no valid
        # lexical or Unicode normalization choice can exceed this bound.
        did_bound = '\x00' * 512
        actor_bound = {'kind':'account','account_id':{'principal_id':did_bound,'station_id':did_bound}}
        coverage_bound = {'realm':True,'strand_ids':['s'*54]*32,
            'members':{'mode':'selected','actor_ids':[actor_bound]*100},'event_ids':['e'*53]*100}
        def frame(entry, coverage):
            return {'kind':'delta','cursor':'c'*2048,'realms':{'r'*53:{'current':{'entries':[entry]},
                'baseline':{'snapshot_cursor':'c'*2048,'cut_revision':9007199254740991,'coverage':coverage,'complete':False}}}}
        overhead = len(jcs(frame(None,coverage_bound))) - len(jcs(None))
        fixture = read(ROOT / 'tools/fixtures/current-result-budget.json')
        self.assertEqual(overhead, fixture['max_required_wrapper_upper_bound_bytes'])
        self.assertLessEqual(overhead,budget['max_required_single_realm_frame_overhead_bytes'])
        self.assertLessEqual(budget['max_atomic_entry_canonical_bytes']+overhead,budget['max_account_frame_canonical_bytes'])
        # Boundary mutations preserve the entire atomic unit, including heads.
        prototype = {'selector':{'scope_ref':{'kind':'realm','realm_id':'ak:realm:'+'A'*44},
            'cell_id':'ak:cell:ak.component.profile.create.v1:subject'},'target':{'kind':'realm'},'revision':7,
            'result':{'status':'heads','heads':[{'event_id':'ak:event:'+'A'*44,'value':{'padding':''}}]}}
        size = budget['max_atomic_entry_canonical_bytes']
        prototype['result']['heads'][0]['value']['padding'] = 'a' * (size-len(jcs(prototype)))
        self.assertEqual(len(jcs(prototype)),size)
        small = {'realm':True,'strand_ids':[],'members':{'mode':'selected','actor_ids':[]},'event_ids':[]}
        def token(index):
            return base64.urlsafe_b64encode(bytes([1]) + index.to_bytes(32,'big')).decode().rstrip('=')
        prefix = 'ak:did_core:web:'
        actors = [{'kind':'account','account_id':{'principal_id':prefix + str(i).zfill(512-len(prefix)),
            'station_id':prefix + 's'*(512-len(prefix))}} for i in range(100)]
        large_valid = {'realm':True,'strand_ids':['ak:strand:'+token(i) for i in range(32)],
            'members':{'mode':'selected','actor_ids':actors},'event_ids':['ak:event:'+token(i) for i in range(100)]}
        for case in fixture['cases']:
            self.assertEqual(case['expected'], 'value' if case['entry_bytes'] <= size else 'unavailable_limit_exceeded')
        for coverage in [small,large_valid,coverage_bound]:
            wrapped=frame(prototype,coverage)
            self.assertLessEqual(len(jcs(wrapped)),budget['max_account_frame_canonical_bytes'])
            self.assertEqual(jcs(wrapped['realms']['r'*53]['current']['entries'][0]),jcs(prototype))
        too_large=copy.deepcopy(prototype)
        too_large['result']['heads'][0]['value']['padding']+='a'
        self.assertGreater(len(jcs(too_large)),size)
        too_large['result']={'status':'unavailable','reason':'limit_exceeded'}
        self.assertLess(len(jcs(too_large)),size)
        # Frame occupancy must never select a different published result.
        self.assertEqual(prototype['revision'],too_large['revision'])
        self.assertNotEqual(jcs(prototype['result']),jcs(too_large['result']))

if __name__ == '__main__':
    unittest.main()

