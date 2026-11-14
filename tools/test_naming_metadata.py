"""Regressions for preserving literal ownership while moving schema owners."""

import copy
import unittest

from tools.artifact_lint.semantic_naming import enum_errors
from tools.naming_metadata import owned_projection


class NamingMetadataProjectionTest(unittest.TestCase):
    def test_boolean_const_gets_scalar_ownership(self):
        node = owned_projection({'const': True}, 'new.schema.json', '/properties/active')
        self.assertEqual(node['x-arkret-value-ownership']['class'], 'numeric')
        self.assertEqual(enum_errors(node, 'new.schema.json#/properties/active'), [])

    def test_existing_literal_classes_and_registered_authorities_survive_projection(self):
        cases = (
            ('uri', 'https://www.w3.org/ns/did/v1', 'old.schema.json#/value'),
            ('uri', 'did:webvh:1.0', 'old.schema.json#/value'),
            ('registered_literal', 'ArkretService', '../registry/terms.json#/types/0/type'),
            ('external_literal', 'Ed25519', 'https://www.rfc-editor.org/rfc/rfc8032.html#section-5.1'),
            ('numeric', True, 'old.schema.json#/value'),
        )
        for kind, value, authority in cases:
            with self.subTest(kind=kind, value=value):
                original = {'const': value, 'x-arkret-value-ownership': {
                    'class': kind, 'authority': authority, 'owner': 'old.schema.json#/value',
                    'values': [value],
                }}
                before = copy.deepcopy(original)
                projected = owned_projection(original, 'new.schema.json', '/properties/value')
                owner = 'new.schema.json#/properties/value'
                metadata = projected['x-arkret-value-ownership']
                self.assertEqual(metadata['class'], kind)
                self.assertEqual(metadata['owner'], owner)
                self.assertEqual(metadata['authority'], owner if authority == 'old.schema.json#/value' else authority)
                self.assertEqual(metadata['values'], [value])
                self.assertEqual(enum_errors(projected, owner, [value] if kind == 'registered_literal' else None), [])
                self.assertEqual(original, before)

    def test_source_authority_does_not_leak_into_unclassified_sibling(self):
        source = {'type': 'object', 'properties': {
            'algorithm': {'const': 'Ed25519', 'x-arkret-value-ownership': {
                'class': 'external_literal',
                'authority': 'https://www.rfc-editor.org/rfc/rfc8032.html#section-5.1',
                'owner': 'old.schema.json#/properties/algorithm', 'values': ['Ed25519'],
            }},
            'state': {'const': 'active'},
        }}
        projected = owned_projection(source, 'new.schema.json', '')
        state = projected['properties']['state']['x-arkret-value-ownership']
        self.assertEqual(state['class'], 'owned_symbol')
        self.assertEqual(state['authority'], 'new.schema.json#/properties/state')

    def test_unclassified_external_string_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'explicit source authority'):
            owned_projection({'const': 'ArkretService'}, 'new.schema.json', '/properties/type')


if __name__ == '__main__':
    unittest.main()
