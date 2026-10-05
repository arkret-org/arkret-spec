"""Mutation coverage for the closed carrier and action-time current boundary."""
import copy
import json
import unittest
from unittest.mock import patch
from .artifact_lint import agent_runtime_contract as contract


class AgentRuntimeContractTest(unittest.TestCase):
    def check_mutation(self, mutate):
        original = contract.load_json

        def mutated(lint, path):
            value = copy.deepcopy(original(lint, path))
            mutate(path.name, value)
            return value

        with patch.object(contract, 'load_json', mutated):
            lint = contract.Lint()
            contract.check_agent_runtime_contract(lint)
        self.assertTrue(lint.errors)

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

    def test_reply_contract_mutations_are_rejected(self):
        fixture = contract.load_json(contract.Lint(), contract.ARTIFACTS / 'registry/contract-registry.json')
        product = fixture['did_evidence_boundary_registry']['agent_participation_runtime_contract']['product_configuration']
        for key, value in product.items():
            with self.subTest(field=key):
                def mutate(name, document, key=key, value=value):
                    if name == 'contract-registry.json':
                        row = document['did_evidence_boundary_registry']['agent_participation_runtime_contract']['product_configuration']
                        row[key] = not value if isinstance(value, bool) else 'unsupported'
                self.check_mutation(mutate)

    def test_each_reply_decision_has_a_negative_mutation(self):
        fixture = contract.load_json(contract.Lint(), contract.ARTIFACTS / 'fixtures/agent-participation-fixture.json')
        matrix = fixture['reply_configuration_contract']
        for table in ('authorization_cases', 'setup_cases', 'readiness_cases', 'recovery_cases'):
            for index, case in enumerate(matrix[table]):
                with self.subTest(table=table, case=case['name']):
                    def mutate(name, document, table=table, index=index):
                        if name == 'agent-participation-fixture.json':
                            row = document['reply_configuration_contract'][table][index]
                            row['expected'] = not row['expected'] if isinstance(row['expected'], bool) else 'unsupported'
                    self.check_mutation(mutate)

    def test_reply_contract_flags_are_boolean(self):
        for value in (0, 1, None):
            with self.subTest(value=value):
                def mutate(name, document, value=value):
                    if name == 'contract-registry.json':
                        document['did_evidence_boundary_registry']['agent_participation_runtime_contract']['product_configuration']['reuse_active_bound_grant'] = value
                self.check_mutation(mutate)

    def test_omitted_or_duplicate_reply_boundaries_are_rejected(self):
        for table in ('authorization_cases', 'setup_cases', 'readiness_cases', 'recovery_cases'):
            for duplicate in (False, True):
                with self.subTest(table=table, duplicate=duplicate):
                    def mutate(name, document, table=table, duplicate=duplicate):
                        if name == 'agent-participation-fixture.json':
                            cases = document['reply_configuration_contract'][table]
                            if duplicate:
                                cases[-1] = copy.deepcopy(cases[0])
                            else:
                                cases.pop()
                    self.check_mutation(mutate)

    def test_reply_fixture_cannot_bind_an_unregistered_contract(self):
        def mutate(name, document):
            if name == 'agent-participation-fixture.json':
                document['reply_configuration_contract']['registry_ref'] = 'local-private-authority'
        self.check_mutation(mutate)


if __name__ == '__main__':
    unittest.main()
