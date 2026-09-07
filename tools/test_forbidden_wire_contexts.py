"""Mutation tests for the context vocabulary gate."""

import copy
import json
import unittest
from pathlib import Path

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


if __name__ == '__main__':
    unittest.main()
