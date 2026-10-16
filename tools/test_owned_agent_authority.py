"""Mutation coverage for controller ceilings, withdrawal and management bans."""
import copy
import json
import unittest
from unittest.mock import patch
from tools.artifact_lint import owned_agent_authority as gate
from tools.artifact_lint import agent_session_content as session_gate


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


class AgentSessionContentTest(unittest.TestCase):
    def run_gate(self, mutation=None):
        original = session_gate.load_json

        def changed(lint, path):
            value = copy.deepcopy(original(lint, path))
            if mutation:
                mutation(path.name, value)
            return value

        lint = session_gate.Lint()
        with patch.object(session_gate, 'load_json', changed):
            session_gate.check_agent_session_content(lint)
        return lint.errors

    def test_committed_source_scope_and_bootstrap_contract(self):
        self.assertEqual(self.run_gate(), [])

    def test_participation_refusal_cannot_target_read_or_membership_write(self):
        for mode in ('read', 'implicit_read', 'membership_write', 'missing_path'):
            with self.subTest(mode=mode):
                def mutate(name, doc):
                    if name == 'agent-vectors-fixture.json':
                        row = next(c for c in doc['session_content_authority_contract']['cases']
                                   if c['name'] == 'participation_current_denied')['input']
                        if mode == 'read':
                            row['action'] = 'ak.event.read'
                        elif mode == 'implicit_read':
                            row.pop('action')
                        elif mode == 'membership_write':
                            row['paths'][0]['kind'] = 'membership_read'
                        else:
                            row.pop('paths')
                self.assertTrue(self.run_gate(mutate))

    def test_payload_approval_refusal_retains_its_actual_action_and_source(self):
        for mode in ('read', 'implicit_read', 'membership_write', 'missing_path'):
            with self.subTest(mode=mode):
                def mutate(name, doc):
                    if name == 'agent-vectors-fixture.json':
                        row = next(c for c in doc['session_content_authority_contract']['cases']
                                   if c['name'] == 'approval_missing')['input']
                        if mode == 'read':
                            row['action'] = 'ak.event.read'
                        elif mode == 'implicit_read':
                            row.pop('action')
                        elif mode == 'membership_write':
                            row['paths'][0]['kind'] = 'membership_read'
                        else:
                            row.pop('paths')
                self.assertTrue(self.run_gate(mutate))

    def test_payload_limits_cannot_be_charged_to_membership_reading(self):
        for case_name in ('condition_not_satisfied', 'quota_exhausted'):
            for mode in ('read', 'implicit_read', 'membership_write', 'missing_path'):
                with self.subTest(case=case_name, mode=mode):
                    def mutate(name, doc):
                        if name == 'agent-vectors-fixture.json':
                            row = next(c for c in doc['session_content_authority_contract']['cases']
                                       if c['name'] == case_name)['input']
                            if mode == 'read':
                                row['action'] = 'ak.event.read'
                            elif mode == 'implicit_read':
                                row.pop('action')
                            elif mode == 'membership_write':
                                row['paths'][0]['kind'] = 'membership_read'
                            else:
                                row.pop('paths')
                    self.assertTrue(self.run_gate(mutate))

    def test_approval_error_binding_cannot_disappear_or_require_refresh(self):
        for mode in ('missing_issue', 'wrong_refresh', 'inactive_reason', 'wrong_parent_status'):
            with self.subTest(mode=mode):
                def mutate(name, doc):
                    if name == 'operations-error-mapping.json':
                        issue = next(row for row in doc['operations'] if row['operation_id'] == 'ak.gate.account.command.issue_session_grant.v1')
                        refresh = next(row for row in doc['operations'] if row['operation_id'] == 'ak.gate.account.command.refresh_session_grant.v1')
                        if mode == 'missing_issue':
                            issue['operation_specific'].remove('human_approval_required')
                        elif mode == 'wrong_refresh':
                            refresh['operation_specific'].append('human_approval_required')
                    if name == 'error-code-registry.json':
                        if mode == 'inactive_reason':
                            next(row for row in doc['reason_codes'] if row['code'] == 'human_approval_required')['status'] = 'reserved'
                        elif mode == 'wrong_parent_status':
                            next(row for row in doc['codes'] if row['code'] == 'claim_required')['http_status'] = 401
                self.assertTrue(self.run_gate(mutate))

    def test_every_security_boundary_has_an_independent_expected_decision(self):
        fixture = session_gate.load_json(session_gate.Lint(), session_gate.ARTIFACTS / 'fixtures/agent-vectors-fixture.json')
        for case in fixture['session_content_authority_contract']['cases']:
            with self.subTest(case=case['name']):
                def mutate(name, doc):
                    if name == 'agent-vectors-fixture.json':
                        row = next(c for c in doc['session_content_authority_contract']['cases'] if c['name'] == case['name'])
                        row['expected'] = 'deny' if row['expected'] != 'deny' else 'allow'
                self.assertTrue(self.run_gate(mutate))

    def test_each_invariant_cannot_be_reversed(self):
        for key in session_gate.INVARIANTS:
            with self.subTest(invariant=key):
                def mutate(name, doc):
                    if name == 'owned-agent-authority-registry.json':
                        value = doc['session_content_authority_contract']['invariants'][key]
                        doc['session_content_authority_contract']['invariants'][key] = not value
                self.assertTrue(self.run_gate(mutate))

    def test_source_paths_cannot_be_spliced(self):
        base = session_gate.load_json(session_gate.Lint(), session_gate.ARTIFACTS / 'fixtures/agent-vectors-fixture.json')['session_content_authority_contract']['defaults']
        for action in ('ak.event.read', 'ak.message.create'):
            for resource in ('A', 'B'):
                paths = [
                    {'kind': 'capability_grant', 'actions': ['ak.event.read'], 'resources': ['A'], 'complete': True, 'active': True},
                    {'kind': 'capability_grant', 'actions': ['ak.message.create'], 'resources': ['B'], 'complete': True, 'active': True},
                ]
                expected = 'allow' if (action, resource) in (('ak.event.read', 'A'), ('ak.message.create', 'B')) else 'deny'
                self.assertEqual(session_gate.decide(base | {'action': action, 'resource': resource, 'paths': paths}), expected)

    def test_missing_or_duplicate_cases_are_rejected(self):
        for duplicate in (False, True):
            def mutate(name, doc):
                if name == 'agent-vectors-fixture.json':
                    cases = doc['session_content_authority_contract']['cases']
                    if duplicate:
                        cases[-1] = copy.deepcopy(cases[0])
                    else:
                        cases.pop()
            self.assertTrue(self.run_gate(mutate))

    def test_refresh_cannot_gain_scope_fields_and_reads_need_no_fake_ref(self):
        def mutate(name, doc):
            if name == 'service-operation-dtos.schema.json':
                doc['$defs']['AgentSessionGrantRefreshRequest']['properties']['requested_scope'] = {'type': 'array'}
        self.assertTrue(self.run_gate(mutate))
        def mutate_refs(name, doc):
            if name == 'service-operation-dtos.schema.json':
                doc['$defs']['SessionGrantIntrospectGrant']['properties']['scope_details']['properties']['capability_grant_refs']['minItems'] = 1
        self.assertTrue(self.run_gate(mutate_refs))


if __name__ == '__main__':
    unittest.main()
