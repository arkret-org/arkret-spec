"""Lock the original device evidence closure on accepted Applet delivery."""

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / 'spec/v1/artifacts/schemas'


class AppletDeviceDeliveryContractTest(unittest.TestCase):
    def test_delivery_uses_the_existing_closed_device_root(self):
        schema = json.loads((SCHEMAS / 'applet-edge-operations.schema.json').read_text(encoding='utf-8'))
        pair = schema['$defs']['applet_committed_event']
        self.assertFalse(pair['additionalProperties'])
        self.assertEqual(pair['required'], ['commit', 'event'])
        self.assertEqual(set(pair['properties']), {'commit', 'event', 'producer_device_evidence', 'producer_signer_fact'})
        evidence = pair['properties']['producer_device_evidence']
        self.assertEqual(evidence['$ref'], './account-device-signer-evidence.schema.json')
        root = json.loads((SCHEMAS / 'account-device-signer-evidence.schema.json').read_text(encoding='utf-8'))
        self.assertFalse(root['additionalProperties'])
        self.assertEqual(set(root['required']), {'device_projection_attestation', 'service_resolution'})
        self.assertEqual(set(root['properties']), set(root['required']))

    def test_historical_cut_and_device_determined_presence_are_explicit(self):
        schema = json.loads((SCHEMAS / 'applet-edge-operations.schema.json').read_text(encoding='utf-8'))
        description = schema['$defs']['applet_committed_event']['properties']['producer_device_evidence']['description']
        for requirement in ['Required exactly', 'ak:device:', 'forbidden otherwise', 'original admission', 'committed_at', 'never receiver current time']:
            self.assertIn(requirement, description)

    def test_realm_delivery_and_control_have_distinct_authority(self):
        schema = json.loads((SCHEMAS / 'applet-edge-operations.schema.json').read_text(encoding='utf-8'))
        fact = schema['$defs']['applet_committed_event']['properties']['producer_signer_fact']
        self.assertEqual(fact['$ref'], './authority-commit-operations.schema.json#/$defs/realm_device_historical_signer_fact')
        context = schema['$defs']['applet_managed_actor_authoring_context']
        self.assertEqual(context['required'], ['material'])
        self.assertEqual(context['properties']['material']['$ref'], './realm-actor-material.schema.json#/$defs/realm_actor_material_response_body')
        self.assertNotIn('managed_actor_resolution_update_evidence', schema['$defs'])


if __name__ == '__main__':
    unittest.main()
