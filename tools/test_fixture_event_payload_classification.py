"""A declared object schema ID does not erase its canonical Event/create role."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.artifact_lint import fixtures
from tools.artifact_lint.core import ARTIFACTS, Lint
from tools.generate_call_current_fixture import build_fixture


class FixtureEventPayloadClassification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads((ARTIFACTS / 'registry/schema-registry.json').read_text(encoding='utf-8'))
        cls.contract = json.loads((ARTIFACTS / 'registry/contract-registry.json').read_text(encoding='utf-8'))
        cls.source = build_fixture()['capture_transcripts']['initiator_grant_source']

    def check(self, value):
        original_load = fixtures.load_json
        with tempfile.TemporaryDirectory() as directory:
            artifacts = Path(directory)
            (artifacts / 'fixtures').mkdir()
            (artifacts / 'fixtures/example.json').write_text(json.dumps(value), encoding='utf-8')
            def load(lint, path):
                if path.name == 'schema-registry.json': return self.registry
                if path.name == 'contract-registry.json': return self.contract
                return original_load(lint, path)
            lint = Lint()
            with patch.object(fixtures, 'ARTIFACTS', artifacts), patch.object(fixtures, 'load_json', side_effect=load):
                fixtures.check_declared_schema_fixture_instances(lint)
            return lint.errors

    def test_actual_grant_event_createbody_and_complete_current_use_distinct_contracts(self):
        self.assertEqual(self.check(self.source), [])

    def test_receiver_derived_fields_are_forbidden_in_the_real_createbody(self):
        changed = copy.deepcopy(self.source)
        for field in ('id', 'status', 'authority_depth'):
            changed['event']['payload']['grant'][field] = changed['current'][field]
        self.assertTrue(self.check(changed))

    def test_unparented_schema_objects_still_require_the_complete_object(self):
        self.assertTrue(self.check({'standalone': self.source['event']['payload']['grant']}))
        self.assertEqual(self.check({'standalone': self.source['current']}), [])

    def test_wrong_event_kind_and_schema_like_kind_cannot_hide_invalid_objects(self):
        changed = copy.deepcopy(self.source)
        changed['event']['kind'] = 'ak.call.state'
        self.assertTrue(self.check(changed))
        self.assertTrue(self.check({'kind': {}, 'object': self.source['event']['payload']['grant']}))


if __name__ == '__main__':
    unittest.main()
