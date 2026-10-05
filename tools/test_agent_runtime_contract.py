"""Mutation coverage for the closed carrier and action-time current boundary."""
import copy
import json
import unittest
from unittest.mock import patch
from .artifact_lint import agent_runtime_contract as contract


class AgentRuntimeContractTest(unittest.TestCase):
    def test_committed_contract(self):
        lint = contract.Lint()
        contract.check_agent_runtime_contract(lint)
        self.assertEqual(lint.errors, [])

    def test_missing_commit_bundle_or_dependency_is_rejected(self):
        original = contract.load_json
        for field in ('commits', 'authority_bundle', 'signer_dependencies'):
            def mutated(lint, path):
                value = copy.deepcopy(original(lint, path))
                if path.name == 'agent-authority-evidence.schema.json':
                    value['$defs']['agent_authority_state']['required'].remove(field)
                return value
            with patch.object(contract, 'load_json', mutated):
                lint = contract.Lint()
                contract.check_agent_runtime_contract(lint)
                self.assertTrue(lint.errors, field)

    def test_current_inputs_are_independent(self):
        fixture = json.loads((contract.ARTIFACTS / 'fixtures/agent-participation-fixture.json').read_text(encoding='utf-8'))
        valid = fixture['runtime_access_cases'][0]
        self.assertTrue(contract.participation_allows(valid))
        for key in ('same_station', 'current_selection', 'complete_governance_cut', 'exact_binding', 'selection_bit', 'ceiling_bit'):
            changed = dict(valid, **{key: False})
            self.assertFalse(contract.participation_allows(changed), key)
        for source in ('session_overlay', 'session_active', 'portable_authority_state'):
            self.assertFalse(contract.participation_allows(dict(valid, selection_source=source)))


if __name__ == '__main__':
    unittest.main()
