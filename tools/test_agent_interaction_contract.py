"""Mutation probes for the published Agent interaction contract."""

import copy
import unittest
from unittest.mock import patch

from tools.artifact_lint import fixtures as gate


class AgentInteractionContractTest(unittest.TestCase):
    def run_gate(self, mutate=None):
        path = gate.ARTIFACTS / 'fixtures/agent-participation-fixture.json'
        document = copy.deepcopy(gate.load_json(gate.Lint(), path))
        if mutate:
            mutate(document)
        lint = gate.Lint()
        with patch.object(gate, 'load_json', return_value=document):
            gate.check_agent_interaction_contract(lint)
        return lint.errors

    def test_published_matrix(self):
        self.assertEqual(self.run_gate(), [])

    def test_unknown_cannot_become_private(self):
        self.assertTrue(self.run_gate(lambda d: d['interaction_contract']['mode_cases'][3].update(expected='private')))

    def test_delegated_controller_write_rejected(self):
        self.assertTrue(self.run_gate(lambda d: d['interaction_contract']['admission_cases'][-2].update(expected=True)))

    def test_private_shared_executor_rejected(self):
        self.assertTrue(self.run_gate(lambda d: d['interaction_contract']['shared_action_cases'][0].update(expected=True)))

    def test_public_owner_does_not_route_private(self):
        self.assertTrue(self.run_gate(lambda d: next(row for row in d['cases'][0]['composer_contract']['routing_cases'] if row['name'] == 'current_public_owned_mention_routes_original_strand').update(expected='sidecar')))

    def test_circle_cannot_route_private_to_realm(self):
        self.assertTrue(self.run_gate(lambda d: next(row for row in d['cases'][0]['composer_contract']['routing_cases'] if row['name'] == 'circle_private_mention_never_routes_realm_sidecar').update(expected='sidecar')))

    def test_prior_private_history_does_not_supply_a_current_target(self):
        for name in ['no_agent_after_private_session', 'no_agent_after_restored_private_history', 'deleted_private_token_does_not_reuse_last_request', 'public_mention_after_private_history']:
            with self.subTest(name=name):
                self.assertTrue(self.run_gate(lambda d: next(row for row in d['cases'][0]['composer_contract']['routing_cases'] if row['name'] == name).update(expected='sidecar')))

    def test_mode_cannot_rewrite_roster(self):
        self.assertTrue(self.run_gate(lambda d: d['interaction_contract']['invariants'].update(mode_changes_sidecar_roster=True)))

    def test_empty_cases_cannot_claim_coverage(self):
        self.assertTrue(self.run_gate(lambda d: d['interaction_contract'].update(admission_cases=[])))

    def test_external_private_request_cannot_trigger(self):
        self.assertTrue(self.run_gate(lambda d: d['interaction_contract']['request_cases'][0].update(expected=True)))

    def test_guessed_target_cannot_create_stub(self):
        self.assertTrue(self.run_gate(lambda d: d['interaction_contract']['observation_cases'][0].update(expected_stub=True)))


if __name__ == '__main__':
    unittest.main()
