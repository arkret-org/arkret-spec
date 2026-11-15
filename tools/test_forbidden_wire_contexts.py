"""Mutation tests for the context vocabulary gate."""

import copy
import json
import unittest
from pathlib import Path

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.artifact_lint.forbidden_wire import vocabulary_errors

ARTIFACTS = Path(__file__).resolve().parents[1] / 'spec/v1/artifacts'


class ForbiddenWireContextTests(unittest.TestCase):
    def setUp(self):
        self.registry = json.loads((ARTIFACTS / 'registry/forbidden-wire-fields.json').read_text(encoding='utf-8'))

    def test_current_vocabulary_resolves(self):
        self.assertEqual(vocabulary_errors(self.registry, ARTIFACTS / 'schemas'), [])

    def test_unknown_context_and_dangling_schema_fail(self):
        changed = copy.deepcopy(self.registry)
        changed['entries'][0]['context'] = 'private_unregistered_scope'
        self.assertTrue(vocabulary_errors(changed, ARTIFACTS / 'schemas'))
        changed = copy.deepcopy(self.registry)
        changed['context_definitions']['message']['selectors'][0]['schema_ref'] = 'message.schema.json#/$defs/missing'
        self.assertTrue(vocabulary_errors(changed, ARTIFACTS / 'schemas'))

    def test_missing_matcher_is_not_interpreted_from_id(self):
        del self.registry['entries'][0]['match']
        self.assertTrue(vocabulary_errors(self.registry, ARTIFACTS / 'schemas'))

    def test_nonexistent_instance_domain_fails_even_when_schema_exists(self):
        self.registry['context_definitions']['message']['selectors'][0]['instance_pointer'] = '/nonexistent/container'
        self.assertTrue(vocabulary_errors(self.registry, ARTIFACTS / 'schemas'))

    def test_consistently_renamed_noncanonical_vocabulary_is_rejected(self):
        changed = copy.deepcopy(self.registry)
        previous = 'authority_ordered_projection_kind_value'
        invalid = 'authority-ordered projection_kind_value'
        kinds = changed['context_matching']['document_kinds']
        kinds[kinds.index(previous)] = invalid
        for definition in changed['context_definitions'].values():
            for selector in definition.get('selectors', []):
                if selector['document_kind'] == previous:
                    selector['document_kind'] = invalid
        self.assertTrue(any('strict snake_case' in error for error in vocabulary_errors(changed, ARTIFACTS / 'schemas')))
        changed = copy.deepcopy(self.registry)
        previous = 'crdt_authority_ordered_projection_enum'
        invalid = 'crdt_authority-ordered projection_enum'
        changed['context_definitions'][invalid] = changed['context_definitions'].pop(previous)
        for entry in changed['entries']:
            if entry['context'] == previous:
                entry['context'] = invalid
        self.assertTrue(any('dotted snake_case' in error for error in vocabulary_errors(changed, ARTIFACTS / 'schemas')))

    def test_document_kind_namespace_is_nonempty_and_unique(self):
        for kinds in (None, [], ['wire', 'wire']):
            changed = copy.deepcopy(self.registry)
            changed['context_matching']['document_kinds'] = kinds
            self.assertTrue(vocabulary_errors(changed, ARTIFACTS / 'schemas'))


if __name__ == '__main__':
    unittest.main()
