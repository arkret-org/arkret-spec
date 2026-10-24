import copy
import unittest

from tools.public_type_duplicates import object_duplicates


class PublicTypeDuplicateTests(unittest.TestCase):
    def test_annotations_and_imported_scalars_cannot_hide_a_duplicate(self):
        documents = {
            'one.schema.json': {'$defs': {
                'id': {'type': 'string', 'minLength': 1},
                'entity_view': {'type': 'object', 'properties': {'id': {'$ref': '#/$defs/id'}},
                                'required': ['id'], 'additionalProperties': False},
            }},
            'two.schema.json': {'$defs': {
                'entity_record': {'type': 'object', 'properties': {'id': {'type': 'string', 'minLength': 1}},
                                  'required': ['id'], 'additionalProperties': False,
                                  'description': 'A different label is not a different domain identity.'},
            }},
        }
        expected = {frozenset({'one.schema.json#/$defs/entity_view',
                               'two.schema.json#/$defs/entity_record'})}
        self.assertEqual(object_duplicates(documents), expected)
        changed = copy.deepcopy(documents)
        changed['two.schema.json']['$defs']['entity_record']['required'] = []
        self.assertFalse(object_duplicates(changed))

    def test_a_third_owner_does_not_inherit_a_two_owner_purpose_review(self):
        node = {'type': 'object', 'properties': {'id': {'type': 'string'}}}
        documents = {'one.schema.json': {'$defs': {name: node for name in ('first', 'second', 'third')}}}
        group, = object_duplicates(documents)
        self.assertEqual(len(group), 3)
        self.assertNotEqual(group, frozenset({'one.schema.json#/$defs/first', 'one.schema.json#/$defs/second'}))


if __name__ == '__main__':
    unittest.main()
