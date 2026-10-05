"""Mutation coverage for controller ceilings, withdrawal and management bans."""
import copy
import json
import unittest
from unittest.mock import patch
from tools.artifact_lint import owned_agent_authority as gate


class OwnedAgentAuthorityTest(unittest.TestCase):
    def run_gate(self, mutation=None):
        original = gate.load_json

        def changed(lint, path):
            value = copy.deepcopy(original(lint, path))
            if mutation:
                mutation(path.name, value)
            return value

        lint = gate.Lint()
        with patch.object(gate, 'load_json', changed):
            gate.check_owned_agent_authority(lint)
        return lint.errors

    def test_published_contract_and_schema_negatives(self):
        self.assertEqual(self.run_gate(), [])

    def test_current_ceiling_and_management_cannot_be_removed(self):
        for key in ('all_grant_paths_current_controller_ceiling', 'current_management_gate',
                    'parent_quota_shared_atomic', 'read_delivery_material_current_gate',
                    'issuer_revoke_without_capability', 'terminal_source',
                    'agent_policy_payload_exact_cas'):
            with self.subTest(key=key):
                def mutate(name, doc):
                    if name == 'owned-agent-authority-registry.json':
                        doc['invariants'][key] = False
                self.assertTrue(self.run_gate(mutate))

    def test_agent_policy_cas_is_required_nullable_and_family_specific(self):
        fixture = gate.load_json(gate.Lint(), gate.ARTIFACTS / 'fixtures/agent-participation-fixture.json')
        source = json.loads(fixture['owned_agent_authority_contract']['schema_cases'][0]['canonical_json'])['grant']
        body = {'policy_id': 'ak:policy:0198ff00-0000-7000-8000-000000000001',
                'expected_revision': None,
                'value': {'schema': 'ak.schema.policy.v1',
                          'id': 'ak:policy:0198ff00-0000-7000-8000-000000000001',
                          'realm_id': source['realm_id'], 'policy_kind': 'agent',
                          'rules': [{'rule_id': 'ban', 'kind': 'agent', 'effect': 'deny',
                                     'agent_target': {'kind': 'all'}, 'agent_operations': ['join']}],
                          'default_effect': 'allow', 'created_by': source['issuer_id'],
                          'created_at': source['issued_at']}}
        validator = gate.schema_validator(gate.ARTIFACTS / 'schemas/event-payload.schema.json',
                                          '#/$defs/policy_set_state_payload')
        self.assertEqual(list(validator.iter_errors(body)), [])
        body['expected_revision'] = {'commit_id': 'ak:realm_commit:ARNRmzDi2r78zveOLmoHOb6AephFMwVuGE1fwXmCoeo4', 'stream_position': 7}
        self.assertEqual(list(validator.iter_errors(body)), [])
        body['expected_revision'] = 7
        self.assertTrue(list(validator.iter_errors(body)))
        del body['expected_revision']
        self.assertTrue(list(validator.iter_errors(body)))
        body['value']['policy_kind'] = 'access'
        body['value']['rules'] = [{'rule_id': 'allow', 'kind': 'action', 'effect': 'allow', 'actions': ['ak.message.create']}]
        self.assertEqual(list(validator.iter_errors(body)), [])
        body['expected_revision'] = None
        self.assertTrue(list(validator.iter_errors(body)))

    def test_agent_policy_cas_mutations_fail(self):
        for field in ('then', 'else', 'if'):
            with self.subTest(field=field):
                def mutate(name, doc):
                    if name == 'event-payload.schema.json':
                        doc['$defs']['policy_set_state_payload'].pop(field)
                self.assertTrue(self.run_gate(mutate))

    def test_agent_policy_cas_fixture_cannot_be_removed(self):
        def mutate(name, doc):
            if name == 'agent-participation-fixture.json':
                cases = doc['owned_agent_authority_contract']['schema_cases']
                cases[:] = [c for c in cases if c['name'] != 'agent_policy_first_write_null']
        self.assertTrue(self.run_gate(mutate))

    def test_bypass_verdicts_fail(self):
        names = ('independent_agent_grant_parent_zero', 'controller_ban_future_agent',
                 'read_ban_existing_subscription', 'blob_parent_read_zero',
                 'revoked_record_does_not_restore', 'wrong_station_controller',
                 'global_deny_other_parent', 'no_cross_grant_splice',
                 'new_runtime_cannot_override_ban', 'unaccepted_retry_after_revoke')
        for case_name in names:
            with self.subTest(case=case_name):
                def mutate(name, doc):
                    if name == 'agent-participation-fixture.json':
                        case = next(c for c in doc['owned_agent_authority_contract']['cases'] if c['name'] == case_name)
                        case['expected'] = 'allow'
                self.assertTrue(self.run_gate(mutate))

    def test_nonterminal_and_mixed_refs_fail(self):
        def mutate(name, doc):
            if name == 'agent-participation-fixture.json':
                cases = doc['owned_agent_authority_contract']['schema_cases']
                for case in cases:
                    if case['name'] in ('nonterminal_owned_authoring', 'owned_ref_mixed_lineage'):
                        case['valid'] = True
        self.assertTrue(self.run_gate(mutate))

    def test_quota_cannot_split_per_agent(self):
        def mutate(name, doc):
            if name == 'agent-participation-fixture.json':
                requests = doc['owned_agent_authority_contract']['quota_sequence']['requests']
                requests[-1]['controller_account'] = 'new_agent_counter'
        self.assertTrue(self.run_gate(mutate))

    def test_native_grant_or_revoke_cannot_revert_to_generic_gate(self):
        for kind in ('ak.capability.grant', 'ak.capability.revoke'):
            with self.subTest(kind=kind):
                def mutate(name, doc):
                    if name == 'contract-registry.json':
                        row = next(r for r in doc['event_kind_registry']['event_kinds'] if r['event_kind'] == kind)
                        row['admission'] = 'capability_gated'
                self.assertTrue(self.run_gate(mutate))

    def test_missing_boundary_is_detected(self):
        def mutate(name, doc):
            if name == 'agent-participation-fixture.json':
                doc['owned_agent_authority_contract']['cases'].pop()
        self.assertTrue(self.run_gate(mutate))


if __name__ == '__main__':
    unittest.main()
