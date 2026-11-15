"""DID document deletion known answers follow the complete current preimage."""

from __future__ import annotations

import copy
import hashlib
import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tools.artifact_lint import primitive_fixtures
from tools.artifact_lint.core import Lint
from tools import regenerate_named_primitive_fixtures as generator


FIXTURE = Path(__file__).resolve().parents[1] / 'spec/v1/artifacts/fixtures/did-binding-digest-fixture.json'
PREFIXES = (
    'removing also_known_as MUST change the digest to ',
    'removing both also_known_as and metadata.primary_handle MUST change the digest to ',
)


def document_case(fixture):
    return next(case for case in fixture['cases'] if case['name'] == 'document_digest_normalized_projection')


def deletion_digests(document):
    preimage = copy.deepcopy(document)
    del preimage['also_known_as']
    result = []
    for remove_handle in (False, True):
        if remove_handle:
            del preimage['metadata']['primary_handle']
        encoded = json.dumps(preimage, ensure_ascii=False, sort_keys=True,
                             separators=(',', ':'), allow_nan=False).encode('utf-8')
        result.append('sha256:' + hashlib.sha256(encoded).hexdigest())
    return result


class DidBindingDigestFixtureTest(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(FIXTURE.read_text(encoding='utf-8'))

    def assert_deletion_answers(self, fixture):
        case = document_case(fixture)
        digests = deletion_digests(case['input']['normalized_document'])
        for prefix, digest in zip(PREFIXES, digests):
            self.assertEqual([value for value in case['assertions'] if value.startswith(prefix)],
                             [prefix + digest])
            self.assertNotEqual(digest, case['expected']['document_digest'])

    def lint_fixture(self, fixture):
        original = primitive_fixtures.load_json

        def load(lint, path):
            return fixture if path == FIXTURE else original(lint, path)

        with patch.object(primitive_fixtures, 'load_json', side_effect=load):
            lint = Lint()
            primitive_fixtures.check_named_primitive_fixtures(lint)
        return [str(error) for error in lint.errors]

    def check_fixture(self, fixture):
        with patch.object(generator, 'NAMES', [FIXTURE.name]), \
                patch.object(Path, 'read_text', return_value=json.dumps(fixture)), \
                patch('sys.argv', ['regenerate_named_primitive_fixtures.py', '--check']), \
                redirect_stdout(io.StringIO()):
            return generator.main()

    def test_shipped_deletion_answers_match_independent_preimages(self):
        self.assert_deletion_answers(self.fixture)
        self.assertEqual(self.lint_fixture(self.fixture), [])
        self.assertEqual(self.check_fixture(self.fixture), 0)

    def test_legacy_service_extension_deletion_answers_fail_gate_and_check(self):
        stale = copy.deepcopy(self.fixture)
        case = document_case(stale)
        legacy_document = copy.deepcopy(case['input']['normalized_document'])
        legacy_document['services'][0]['extensions'][0]['name'] = 'serviceKind'
        legacy_digests = deletion_digests(legacy_document)
        self.assertEqual(legacy_digests, [
            'sha256:41a9952f2759044d26d640dba9c54b4d7702de30bc4ca5621a56667495e1fb58',
            'sha256:acbe292d7600ba1e26ca284e5f408795aae4ac3dc6247e4a4e312ae6ada5b251',
        ])
        for prefix, digest in zip(PREFIXES, legacy_digests):
            index = next(index for index, value in enumerate(case['assertions']) if value.startswith(prefix))
            case['assertions'][index] = prefix + digest
        with self.assertRaises(AssertionError):
            self.assert_deletion_answers(stale)
        self.assertTrue(any(FIXTURE.name in error for error in self.lint_fixture(stale)))
        self.assertEqual(self.check_fixture(stale), 1)
        self.assertEqual(generator.build(FIXTURE.name, stale), self.fixture)

    def test_changed_document_refreshes_all_deletion_preimages(self):
        changed = copy.deepcopy(self.fixture)
        document_case(changed)['input']['normalized_document']['services'][0]['endpoint'] = 'https://other.example/'
        self.assertTrue(self.lint_fixture(changed))
        self.assertEqual(self.check_fixture(changed), 1)
        refreshed = generator.build(FIXTURE.name, changed)
        self.assert_deletion_answers(refreshed)
        self.assertEqual(document_case(refreshed)['input'], document_case(changed)['input'])
        self.assertEqual(refreshed['cases'][1:], self.fixture['cases'][1:])
        self.assertEqual(self.lint_fixture(refreshed), [])
        self.assertEqual(self.check_fixture(refreshed), 0)


if __name__ == '__main__':
    unittest.main()
