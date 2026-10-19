"""Canonical paired Device scopes and complete operation mapping vectors."""
import json
import unittest
from pathlib import Path
from tools.artifact_lint import core

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'spec/v1/artifacts'


class AppletDeviceScopeContractTest(unittest.TestCase):
    def test_scope_vectors_and_registered_actions(self):
        validator = core.schema_validator(ART / 'schemas/event-payload.schema.json', '#/$defs/applet_managed_device_scopes')
        actions = {r['action'] for r in json.loads((ART / 'registry/capability-action-registry.json').read_text())['actions']}
        cases = json.loads((ART / 'fixtures/applet-device-scope-fixture.json').read_text())['cases']
        for case in cases:
            with self.subTest(case=case['name']):
                entries = case['scopes']
                valid = not list(validator.iter_errors(entries))
                if valid:
                    keys = [core.canonical_json(e['effective_scope']).encode() for e in entries]
                    valid = all(x < y for x, y in zip(keys, keys[1:])) and all(
                        all(a in actions for a in e['actions']) and
                        all(x < y for x, y in zip(e['actions'], e['actions'][1:])) for e in entries)
                self.assertEqual(valid, case['valid'])
                permits = valid and bool(case['actions']) and any(
                    e['effective_scope'] == case['scope'] and all(a in e['actions'] for a in case['actions']) for e in entries)
                self.assertEqual(permits, case['permits'])

    def test_operation_rules_are_complete_and_closed(self):
        contract = json.loads((ART / 'registry/applet-managed-authority-registry.json').read_text())['device_authentication']
        rules = contract['operation_scope_rules']
        self.assertEqual([r['operation_id'] for r in rules], contract['operations'])
        self.assertEqual(len(rules), 22)
        actions = {r['action'] for r in json.loads((ART / 'registry/capability-action-registry.json').read_text())['actions']}
        for r in rules:
            self.assertTrue(set(r['actions']) <= actions)
            self.assertIn(r['mode'], ['all_actions', 'device_control', 'submitted_business_actions'])
            self.assertEqual(bool(r['actions']), r['mode'] == 'all_actions')
            self.assertEqual('control_rule' in r, r['mode'] == 'device_control')
        material = next(r for r in rules if r['operation_id'] == 'ak.self.realm_actor.read.material.v1')
        self.assertEqual(material['control_rule'], 'own_exact_device_authorization_material_read')
        self.assertEqual(sum(r['mode'] == 'device_control' for r in rules), 5)

    def test_payload_and_possession_use_the_same_pairs(self):
        defs = json.loads((ART / 'schemas/event-payload.schema.json').read_text())['$defs']
        scopes = {'$ref': '#/$defs/applet_managed_device_scopes'}
        self.assertEqual(defs['device_authorize_payload']['allOf'][1]['then']['properties']['scopes'], scopes)
        self.assertEqual(defs['device_authorize_realm_actor_possession_transcript']['properties']['scopes'], scopes)
        self.assertNotIn('device_signature', defs['device_authorize_possession_core']['properties'])


if __name__ == '__main__':
    unittest.main()
