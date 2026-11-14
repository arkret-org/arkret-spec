"""Single-kind wire rejection and type-driven operation-target naming mutations."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from tools.artifact_lint.core import Lint
from tools.artifact_lint.object_target_naming import (
    check_object_target_naming, object_target_contract_errors, object_target_name_errors,
)

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'spec/v1/artifacts'
TARGETS = (
    ('ak.strand.update', 'strand_patch_payload', 'strand_id', {'metadata.title': 'Title'}),
    ('ak.strand.tracks.update', 'strand_tracks_update_payload', 'strand_id', {'tracks.discussion.enabled': True}),
    ('ak.morph.update', 'morph_update_payload', 'morph_id', {'metadata.title': 'Title'}),
    ('ak.profile.update', 'actor_profile_update_payload', 'actor_profile_id', {'display_name': 'Name'}),
    ('ak.profile.realm_override', 'profile_realm_override_payload', 'actor_profile_id', {'display_name': 'Name'}),
)


def token(kind):
    return 'ak:' + kind + ':' + 'A' * 44


class ObjectTargetNamingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.documents = {p.name: json.loads(p.read_text(encoding='utf-8'))
                         for p in (ART / 'schemas').glob('*.schema.json')}
        cls.catalog = json.loads((ART / 'registry/contract-registry.json').read_text(encoding='utf-8'))
        cls.registry = Registry().with_resources((d['$id'], Resource.from_contents(d))
                                                 for d in cls.documents.values())

    def validator(self, definition):
        return Draft202012Validator({'$ref': 'https://arkret.org/v1/schemas/event-payload.schema.json#/$defs/' + definition},
                                    registry=self.registry)

    def payload(self, definition, name, patch):
        value = {name: token(name[:-3]), 'patch': copy.deepcopy(patch)}
        if definition == 'profile_realm_override_payload':
            value['target_realm_id'] = token('realm')
        return value

    def test_closed_payloads_accept_new_name_and_reject_old_or_both(self):
        for event, definition, name, patch in TARGETS:
            with self.subTest(event=event):
                validator = self.validator(definition)
                valid = self.payload(definition, name, patch)
                validator.validate(valid)
                old = copy.deepcopy(valid)
                old['target_ref'] = old.pop(name)
                self.assertFalse(validator.is_valid(old))
                self.assertFalse(validator.is_valid({**valid, 'target_ref': valid[name]}))
                for kind in ('realm', 'message', 'strand', 'morph', 'actor_profile'):
                    if kind != name[:-3]:
                        self.assertFalse(validator.is_valid({**valid, name: token(kind)}))
                self.assertFalse(validator.is_valid({**valid, name: None}))
                self.assertFalse(validator.is_valid({**valid, name: token('event')}))

    def test_cas_and_scope_carriers_remain_closed(self):
        for _, definition, name, patch in TARGETS:
            validator = self.validator(definition)
            valid = self.payload(definition, name, patch)
            validator.validate({**valid, 'expected_state_digest': 'sha256:' + 'a' * 64})
            self.assertFalse(validator.is_valid({**valid, 'expected_state_digest': 'not-a-digest'}))
            self.assertFalse(validator.is_valid({**valid, 'scope_circle_id': token('circle')}))
        value = self.payload('profile_realm_override_payload', 'actor_profile_id', {'display_name': 'Name'})
        self.assertFalse(self.validator('profile_realm_override_payload').is_valid({**value, 'target_realm_id': token('strand')}))
        value.pop('target_realm_id')
        self.assertFalse(self.validator('profile_realm_override_payload').is_valid(value))
        profile = self.payload('actor_profile_update_payload', 'actor_profile_id', {'display_name': 'Name'})
        commit = json.loads((ART / 'fixtures/authority-commit-fixture.json').read_text(encoding='utf-8'))[
            'independent_streams'][0]['commits'][1]
        validator = self.validator('actor_profile_update_payload')
        validator.validate({**profile, 'expected_commit_id': commit['commit_id']})
        for invalid in (
            {'commit_id': commit['commit_id'], 'stream_position': commit['stream_position']},
            {'commit_id': commit['commit_id'], 'stream_position': -1},
            {'commit_id': commit['commit_id']},
            token('event'), 'sha256:' + 'a' * 64, None, 1,
        ):
            with self.subTest(expected_commit_id=invalid):
                self.assertFalse(validator.is_valid({**profile, 'expected_commit_id': invalid}))

    def test_full_event_dispatch_uses_each_new_payload_shape(self):
        validator = Draft202012Validator({'$ref': 'https://arkret.org/v1/schemas/event-envelope.schema.json'},
                                        registry=self.registry)
        base = {'event_id': token('event'), 'realm_id': token('realm'),
                'scope_ref': {'kind': 'realm', 'realm_id': token('realm')},
                'actor_id': {'kind': 'account', 'account_id': {
                    'principal_id': 'ak:did_core:web:alice.example', 'station_id': 'ak:did_core:web:station.example'}},
                'created_at': '2026-11-11T00:00:00.000Z',
                'producer_proof': {'kind': 'detached_jws', 'verification_method': 'did:web:alice.example#key-1',
                    'event_digest': 'sha256:' + 'a' * 64, 'created_at': '2026-11-11T00:00:00.000Z',
                    'jws': 'eyJhbGciOiJFZDI1NTE5In0..' + 'A' * 86}}
        # These are schema-only values, not valid cryptographic transcripts.
        for event, definition, name, patch in TARGETS:
            with self.subTest(event=event):
                value = {**base, 'kind': event, 'payload': self.payload(definition, name, patch)}
                validator.validate(value)
                old = copy.deepcopy(value)
                old['payload']['target_ref'] = old['payload'].pop(name)
                self.assertFalse(validator.is_valid(old))
                both = copy.deepcopy(value)
                both['payload']['target_ref'] = both['payload'][name]
                self.assertFalse(validator.is_valid(both))

    def test_patch_restrictions_remain_independent_of_target_name(self):
        paths = {
            'strand_patch_payload': ['tracks', 'tracks.synthesis.enabled', 'tracks.discussion.content'],
            'strand_tracks_update_payload': ['tracks', 'tracks.synthesis.content', 'tracks.synthesis.encrypted_content'],
            'morph_update_payload': ['morph_kind', 'schema_refs', 'stage', 'stage_changed_at'],
            'actor_profile_update_payload': ['resolution', 'resolution.did', 'principal_id', 'actor_kind', 'actor_id'],
            'profile_realm_override_payload': ['resolution', 'resolution.did', 'principal_id', 'actor_kind', 'actor_id', 'encrypted_private_fields'],
        }
        for _, definition, name, _ in TARGETS:
            for path in paths[definition]:
                with self.subTest(definition=definition, path=path):
                    self.assertFalse(self.validator(definition).is_valid(self.payload(definition, name, {path: 'changed'})))
        topic = self.payload('strand_patch_payload', 'strand_id', {'topic': {'$op': 'unset'}})
        self.assertFalse(self.validator('strand_patch_payload').is_valid(topic))
        self.validator('strand_patch_payload').validate({**topic, 'expected_state_digest': 'sha256:' + 'a' * 64})

    def test_current_canonical_contract_and_registered_gate_pass(self):
        self.assertEqual(object_target_contract_errors(self.documents, self.catalog), [])
        lint = Lint()
        check_object_target_naming(lint)
        self.assertEqual(lint.errors, [])

    def test_regression_is_rejected_even_when_selectors_follow_the_rename(self):
        for event, definition, name, _ in TARGETS:
            for replacement in ('target_ref', 'target_id', 'other_id'):
                with self.subTest(event=event, name=replacement):
                    documents = copy.deepcopy(self.documents)
                    payload = documents['event-payload.schema.json']['$defs'][definition]
                    payload['properties'][replacement] = payload['properties'].pop(name)
                    payload['required'] = [replacement if x == name else x for x in payload['required']]
                    catalog = copy.deepcopy(self.catalog)
                    row = next(r for r in catalog['event_kind_registry']['event_kinds'] if r['event_kind'] == event)
                    for write in row['state_writes']:
                        selector = write.get('state_selector') or {}
                        if selector.get('field') == 'payload.' + name:
                            selector['field'] = 'payload.' + replacement
                    self.assertTrue(object_target_contract_errors(documents, catalog))

    def test_type_changes_and_missing_target_are_rejected(self):
        for mutation in ({'$ref': '#/$defs/morph_id'}, {'type': 'string'}, {'$ref': '#/$defs/does_not_exist'}):
            documents = copy.deepcopy(self.documents)
            documents['event-payload.schema.json']['$defs']['strand_patch_payload']['properties']['strand_id'] = mutation
            self.assertTrue(object_target_contract_errors(documents, self.catalog))
        catalog = copy.deepcopy(self.catalog)
        row = next(r for r in catalog['event_kind_registry']['event_kinds'] if r['event_kind'] == 'ak.strand.update')
        row['state_writes'][0]['state_selector']['field'] = 'payload.missing_id'
        self.assertTrue(object_target_contract_errors(self.documents, catalog))

    def test_future_kind_and_cross_file_aliases_use_terminal_semantics(self):
        documents = copy.deepcopy(self.documents)
        documents['alias.schema.json'] = {'$id': 'https://arkret.org/v1/schemas/alias.schema.json', '$defs': {'target': {'oneOf': [
            {'$ref': './event-payload.schema.json#/$defs/strand_id'}, {'type': 'null'}]}}}
        shape = {'allOf': [{'$ref': './alias.schema.json#/$defs/target'}]}
        for name, expected in [('strand_id', False), ('target_strand_id', False), ('target_ref', True), ('strand_ref', True), ('target_id', True)]:
            self.assertEqual(bool(object_target_name_errors(documents, 'event-payload.schema.json', name, shape, 'strand')), expected)
        shape = {'type': 'string', 'pattern': '^ak:space:[A-Za-z0-9_-]{44}$'}
        self.assertTrue(object_target_name_errors(documents, 'alias.schema.json', 'target_ref', shape, 'space'))
        self.assertEqual(object_target_name_errors(documents, 'alias.schema.json', 'target_space_id', shape, 'space'), [])

    def test_cross_file_terminal_requires_the_registered_resource_not_a_shared_basename(self):
        for reference in (
            'https://unregistered.invalid/event-payload.schema.json#/$defs/strand_id',
            '../../untrusted/event-payload.schema.json#/$defs/strand_id',
        ):
            with self.subTest(reference=reference):
                self.assertTrue(object_target_name_errors(self.documents, 'event-payload.schema.json',
                    'strand_id', {'$ref': reference}, 'strand'))

    def test_shared_polymorphism_and_event_proof_roles_are_preserved(self):
        shape = {'$ref': '#/$defs/object_ref'}
        self.assertEqual(object_target_name_errors(self.documents, 'event-payload.schema.json', 'target_ref', shape, 'strand'), [])
        self.assertTrue(object_target_name_errors(self.documents, 'event-payload.schema.json', 'strand_id', shape, 'strand'))
        proof = {'$ref': './common-ids.schema.json#/$defs/event_id'}
        self.assertEqual(object_target_name_errors(self.documents, 'event-payload.schema.json', 'target_ref', proof, 'event'), [])
        for kind in ('strand', 'morph', 'actor_profile'):
            self.validator('object_lifecycle_payload').validate({'target_ref': token(kind)})
        reaction = self.validator('reaction_payload')
        reaction.validate({'target_ref': token('message'), 'key': 'like'})
        reaction.validate({'target_ref': token('morph'), 'key': 'like'})

    def test_shared_ref_cannot_become_a_monotype_naming_exemption(self):
        documents = copy.deepcopy(self.documents)
        documents['event-payload.schema.json']['$defs']['object_ref'] = {'$ref': '#/$defs/strand_id'}
        self.assertTrue(object_target_name_errors(documents, 'event-payload.schema.json', 'target_ref', {'$ref': '#/$defs/object_ref'}, 'strand'))


if __name__ == '__main__':
    unittest.main()
