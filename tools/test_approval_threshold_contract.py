"""Reject approval policies whose vote threshold cannot be interpreted."""

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


class ApprovalThresholdContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / 'spec/v1/artifacts/schemas/grant-constraint.schema.json'
        cls.threshold = json.loads(path.read_text(encoding='utf-8'))['properties']['approval_threshold']
        cls.validator = Draft202012Validator(cls.threshold)

    def test_registered_kat_integer_quorum_is_expressible(self):
        path = Path(__file__).resolve().parents[1] / 'spec/v1/artifacts/fixtures/approval-signature-kat-fixture.json'
        fixture = json.loads(path.read_text(encoding='utf-8'))
        def visit(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key == 'approval_threshold':
                        self.assertTrue(self.validator.is_valid(child), child)
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)
        visit(fixture)

    def test_only_executable_thresholds_are_accepted(self):
        for value in ['majority', 'unanimous', 1, 2, 100]:
            with self.subTest(value=value):
                self.assertTrue(self.validator.is_valid(value))
        for value in ['quorum', 'custom', '', None, True, False, 0, -1, 1.5, {}, []]:
            with self.subTest(value=value):
                self.assertFalse(self.validator.is_valid(value))
        self.assertEqual(self.threshold['default'], 'unanimous')

    def test_timeout_has_a_fixed_positive_duration(self):
        path = Path(__file__).resolve().parents[1] / 'spec/v1/artifacts/schemas/grant-constraint.schema.json'
        properties = json.loads(path.read_text(encoding='utf-8'))['properties']
        validator = Draft202012Validator(properties['timeout'])
        for value in ['PT1S', 'PT72H', 'P1W', 'P1DT2H', 'PT1M']:
            self.assertTrue(validator.is_valid(value), value)
        for value in ['PT-1S', 'invalid', None]:
            self.assertFalse(validator.is_valid(value), value)
        self.assertEqual(properties['timeout']['pattern'], properties['inactivity_timeout']['pattern'])
        description = properties['timeout']['description']
        self.assertIn('no calendar year/month', description)
        self.assertIn('committed_at <=', description)
        self.assertIn('inclusive and with zero tolerance', description)
        self.assertNotIn('approver_ids', properties)
        self.assertNotIn('auto_reject_on_timeout', properties)

    def test_rotation_requires_a_private_pcr_anchor_and_complete_lineage(self):
        path = Path(__file__).resolve().parents[1] / 'spec/v1/artifacts/schemas/applet-edge-operations.schema.json'
        definitions = json.loads(path.read_text(encoding='utf-8'))['$defs']
        context = definitions['applet_managed_actor_authoring_context']
        self.assertIn('principal_control_commit', context['required'])
        self.assertNotIn('resolution_update', context['required'])
        rotation = definitions['managed_actor_resolution_update_evidence']
        self.assertFalse(rotation['additionalProperties'])
        self.assertEqual(set(rotation['required']), set(rotation['properties']))
        self.assertEqual(rotation['properties']['commits']['minItems'], 1)
        self.assertNotIn('public_principal_resolution', rotation['properties'])


if __name__ == '__main__':
    unittest.main()
