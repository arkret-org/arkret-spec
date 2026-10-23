"""The signed PCR resolution CAS uses the shared typed revision carrier."""
import copy
import json
import unittest
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'spec/v1/artifacts'


class PrincipalResolutionCasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        schemas = [json.loads(p.read_text(encoding='utf-8')) for p in (ART / 'schemas').glob('*.json')]
        cls.registry = Registry().with_resources((s['$id'], Resource.from_contents(s)) for s in schemas)
        cls.schema = next(s for s in schemas if s['$id'].endswith('/identity-resolution.schema.json'))

    def payload(self):
        return {
            'expected_revision': {'commit_id': 'ak:realm_commit:ARNRmzDi2r78zveOLmoHOb6AephFMwVuGE1fwXmCoeo4', 'stream_position': 3},
            'next': {'did': 'did:web:alice.example', 'method_history_head': 'sha256:' + 'a' * 64, 'version_id': 'synthetic-jcs-sha256:' + 'a' * 64},
        }

    def validator(self):
        return Draft202012Validator({'$ref': self.schema['$id'] + '#/$defs/principal_resolution_update_payload'}, registry=self.registry)

    def test_exact_shared_revision_and_next_are_required(self):
        value = self.payload()
        self.validator().validate(value)
        self.assertEqual(list(self.schema['$defs']['principal_resolution_update_payload']['properties']), ['expected_revision', 'next'])
        for key in value:
            changed = copy.deepcopy(value)
            del changed[key]
            self.assertFalse(self.validator().is_valid(changed))

    def test_revision_rejects_null_counter_and_bare_commit(self):
        for revision in [None, 3, self.payload()['expected_revision']['commit_id'], {'stream_position': 3}, {'commit_id': self.payload()['expected_revision']['commit_id']}, {'commit_id': self.payload()['expected_revision']['commit_id'], 'stream_position': -1}]:
            value = self.payload()
            value['expected_revision'] = revision
            self.assertFalse(self.validator().is_valid(value), revision)

    def test_whole_value_guard_and_predecessor_echo_are_closed(self):
        for key in ['value', 'previous', 'preconditions', 'previous_event_ref', 'method_history_head']:
            value = self.payload()
            value[key] = {}
            self.assertFalse(self.validator().is_valid(value), key)
        value = self.payload()
        value['expected_revision']['value'] = value['next']
        self.assertFalse(self.validator().is_valid(value))

    def test_envelope_guard_stays_forbidden(self):
        envelope = json.loads((ART / 'schemas/event-envelope.schema.json').read_text(encoding='utf-8'))
        self.assertFalse(envelope['additionalProperties'])
        self.assertTrue({'expected_revision', 'preconditions'}.isdisjoint(envelope['properties']))
        entries = json.loads((ART / 'registry/forbidden-wire-fields.json').read_text(encoding='utf-8'))['entries']
        forbidden = {entry['id'] for entry in entries if entry.get('context') == 'producer_event_envelope_root'}
        self.assertTrue({'expected_revision', 'preconditions'} <= forbidden)

    def test_signature_binds_both_revision_components(self):
        key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
        canonical = lambda value: json.dumps(value, sort_keys=True, separators=(',', ':')).encode()
        value = self.payload()
        signature = key.sign(canonical(value))
        key.public_key().verify(signature, canonical(value))
        for field, replacement in [('commit_id', 'ak:realm_commit:' + 'A' * 44), ('stream_position', 4)]:
            changed = copy.deepcopy(value)
            changed['expected_revision'][field] = replacement
            with self.assertRaises(InvalidSignature):
                key.public_key().verify(signature, canonical(changed))

    def test_cursor_uses_accepted_commit_and_exact_lineage(self):
        cursor = self.schema['$defs']['principal_resolution_audit_evidence']['properties']['next_audit_cursor']['description']
        for requirement in ['payload.expected_revision', 'accepted covering RealmCommit', 'Account PCR lineage', 'Commit event_ref']:
            self.assertIn(requirement, cursor)
        self.assertNotIn('value.resolution_event_ref', cursor)


if __name__ == '__main__':
    unittest.main()
