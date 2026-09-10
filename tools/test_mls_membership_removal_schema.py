"""Schema boundaries for own-Station exact MLS leaf removal results."""
import copy
import json
import unittest
from pathlib import Path
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / 'spec/v1/artifacts/schemas'
SCHEMA_ID = 'https://arkret.org/v1/schemas/mls-governance-proof-bundle.schema.json'

class MembershipRemovalSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        resources = []
        for path in SCHEMAS.glob('*.json'):
            value = json.loads(path.read_text(encoding='utf-8'))
            resources.append((value['$id'], Resource.from_contents(value)))
        registry = Registry().with_resources(resources)
        cls.request_validator = Draft202012Validator({'$ref': SCHEMA_ID + '#/$defs/membership_removal_request_body'}, registry=registry)
        cls.outcome_validator = Draft202012Validator({'$ref': SCHEMA_ID + '#/$defs/membership_removal_outcome'}, registry=registry)

    def request(self):
        return {
            'effective_scope': {'kind': 'realm', 'realm_id': 'ak:realm:AZocxLUuB-7lfxVbVJzNCcxSEn-aDa07Di6MnigFwGfd'},
            'mls_group_id': 'Z3JvdXA',
            'local_mls_leaves': [{'leaf_index': 0, 'actor_id': {'kind': 'account', 'account_id': self.account()}, 'credential_ref': 'did:web:alice.example#device'}],
            'seal_basis': {'leaves': ['ak:seal:sha256:' + '1' * 64]},
            'base_group_state_ref': 'ak:event:ARf0hBMoVkQqflOWgdkxNzM3DDLeIZcTJgfcuk16MrSh',
            'epoch': 0,
        }

    def account(self):
        return {'principal_id': 'ak:did_core:web:alice.example', 'station_id': 'ak:did_core:web:station.example'}

    def outcome(self):
        request = self.request()
        return {'account_id': self.account(), 'query_digest': 'sha256:' + '2' * 64, 'seal_basis': request['seal_basis'],
                'epoch_head': {'transition_ref': request['base_group_state_ref'], 'transition_event_digest': 'sha256:' + '3' * 64,
                               'mls_transition_digest': 'sha256:' + '4' * 64, 'effective_scope': request['effective_scope'],
                               'mls_group_id': request['mls_group_id'], 'previous_epoch': 0, 'next_epoch': 0, 'content_scheme': 'mls_rfc9420'},
                'remove_leaf_indices': []}

    def test_genesis_base_and_atomic_empty_result_are_well_formed(self):
        self.request_validator.validate(self.request())
        self.outcome_validator.validate(self.outcome())

    def test_request_rejects_missing_context_and_legacy_authority(self):
        for key in self.request():
            request = self.request()
            del request[key]
            self.assertFalse(self.request_validator.is_valid(request), key)
        for key in ('cursor', 'proof_base_basis', 'membership_frontier', 'checkpoint', 'proposed_group_genesis_binding'):
            request = self.request()
            request[key] = {}
            self.assertFalse(self.request_validator.is_valid(request), key)
        request = self.request()
        request['effective_scope']['kind'] = 'sidecar'
        self.assertFalse(self.request_validator.is_valid(request))

    def test_leaf_and_index_structural_bounds(self):
        for value in (-1, 4294967296):
            request = self.request()
            request['local_mls_leaves'][0]['leaf_index'] = value
            self.assertFalse(self.request_validator.is_valid(request))
        for leaves in ([], self.request()['local_mls_leaves'] * 2):
            request = self.request()
            request['local_mls_leaves'] = leaves
            self.assertFalse(self.request_validator.is_valid(request))
        for indices in ([0, 0], [-1], [4294967296]):
            outcome = self.outcome()
            outcome['remove_leaf_indices'] = indices
            self.assertFalse(self.outcome_validator.is_valid(outcome))

    def test_outcome_is_closed_and_requires_complete_binding(self):
        for key in self.outcome():
            outcome = self.outcome()
            del outcome[key]
            self.assertFalse(self.outcome_validator.is_valid(outcome), key)
        for key in ('next_cursor', 'actor_ids', 'proof_material', 'membership_events'):
            outcome = self.outcome()
            outcome[key] = []
            self.assertFalse(self.outcome_validator.is_valid(outcome), key)

if __name__ == '__main__':
    unittest.main()
