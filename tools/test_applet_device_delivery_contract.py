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
        self.assertEqual(set(pair['properties']), {'commit', 'event', 'producer_device_evidence'})
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

    def test_native_managed_rotation_cannot_borrow_portal_or_session_authority(self):
        schema = json.loads((SCHEMAS / 'applet-edge-operations.schema.json').read_text(encoding='utf-8'))
        description = schema['$defs']['applet_event_transaction_request_body']['properties']['events']['description']
        for requirement in ['IdentityResolutionUpdate', 'original active owning Applet', 'original installing Station', 'own derived managed PCR', 'never the native principal producer', 'no portal grant or SessionGrant']:
            self.assertIn(requirement, description)


if __name__ == '__main__':
    unittest.main()
