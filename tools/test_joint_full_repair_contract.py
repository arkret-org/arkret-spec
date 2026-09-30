"""Executable boundary checks for the joint-full repair adjudication."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / 'spec/v1/artifacts'


def load(relative: str) -> dict:
    return json.loads((ARTIFACTS / relative).read_text(encoding='utf-8'))


class JointFullRepairContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        resources = []
        for path in (ARTIFACTS / 'schemas').glob('*.schema.json'):
            value = json.loads(path.read_text(encoding='utf-8'))
            resources.append((value['$id'], Resource.from_contents(value)))
        cls.registry = Registry().with_resources(resources)

    def validator(self, schema: str, definition: str) -> Draft202012Validator:
        return Draft202012Validator(
            {'$ref': f'https://arkret.org/v1/schemas/{schema}#/$defs/{definition}'},
            registry=self.registry,
        )

    def test_synthesis_content_paths_do_not_open_track_configuration(self) -> None:
        validator = self.validator('event-payload.schema.json', 'strand_patch_payload')
        target = 'ak:strand:' + 'A' * 44
        for path in ('tracks.synthesis.content', 'tracks.synthesis.encrypted_content', 'metadata.title'):
            with self.subTest(path=path):
                self.assertTrue(validator.is_valid({'target_ref': target, 'patch': {path: 'value'}}))
        for path in ('tracks', 'tracks.synthesis', 'tracks.synthesis.enabled',
                     'tracks.discussion.content', 'tracks.synthesis.content.text'):
            with self.subTest(path=path):
                self.assertFalse(validator.is_valid({'target_ref': target, 'patch': {path: 'value'}}))

    def test_track_configuration_cannot_replace_or_delete_content(self) -> None:
        validator = self.validator('event-payload.schema.json', 'strand_tracks_update_payload')
        target = 'ak:strand:' + 'A' * 44
        valid = {'target_ref': target, 'patch': {'tracks.discussion.enabled': True,
                                              'tracks.synthesis.is_primary': False}}
        self.assertTrue(validator.is_valid(valid))
        for path in ('tracks', 'tracks.synthesis', 'tracks.synthesis.content',
                     'tracks.synthesis.encrypted_content', 'tracks.unknown.enabled'):
            invalid = copy.deepcopy(valid)
            invalid['patch'] = {path: {'$op': 'unset'}}
            with self.subTest(path=path):
                self.assertFalse(validator.is_valid(invalid))

    def test_blob_upload_requires_private_safe_classification(self) -> None:
        validator = self.validator('blob-operations.schema.json', 'blob_upload_request_body')
        request = {'content': 'bytes', 'size_bytes': 5, 'encryption': None}
        self.assertTrue(validator.is_valid(request))
        request['encryption'] = {'scheme': 'ak.blob.whole_file_aead.v1'}
        self.assertTrue(validator.is_valid(request))
        invalid = copy.deepcopy(request)
        invalid['media_type'] = 'text/plain'
        self.assertFalse(validator.is_valid(invalid))
        invalid['media_type'] = 'application/octet-stream'
        self.assertTrue(validator.is_valid(invalid))
        for extra in ('media_type', 'size_bytes', 'key_ref', 'nonce'):
            invalid = copy.deepcopy(request)
            invalid['encryption'][extra] = 'private'
            with self.subTest(extra=extra):
                self.assertFalse(validator.is_valid(invalid))
        invalid = copy.deepcopy(request)
        invalid.pop('encryption')
        self.assertFalse(validator.is_valid(invalid))
        request['purpose'] = 'privilege'
        self.assertFalse(validator.is_valid(request))

    def test_membership_reason_is_active_and_has_real_ingress_producers(self) -> None:
        errors = load('registry/error-code-registry.json')
        row = next(row for row in errors['reason_codes'] if row['code'] == 'invalid_membership_transition')
        self.assertEqual(row['status'], 'active')
        self.assertNotIn('activation_condition', row)
        catalog = load('registry/contract-registry.json')
        kinds = {row['event_kind']: row for row in catalog['event_kind_registry']['event_kinds']}
        for kind in ('ak.member.state', 'ak.circle.member.state'):
            self.assertIn('invalid_membership_transition', kinds[kind]['payload'])
        mapping = load('registry/operations-error-mapping.json')
        operations = {row['operation_id']: row for row in mapping['operations']}
        for operation in ('ak.self.events.command.submit.v1', 'ak.peer.events.command.submit.v1',
                          'ak.edge.applet.command.transaction.v1'):
            self.assertIn('invalid_membership_transition', operations[operation]['operation_specific'])

    def test_revoke_membership_intent_has_no_nonexistent_remove_state(self) -> None:
        schema = load('schemas/applet-install-operations.schema.json')
        membership = schema['$defs']['applet_membership_remove_intent']['properties']['membership']
        self.assertTrue(Draft202012Validator(membership).is_valid('leave'))
        self.assertFalse(Draft202012Validator(membership).is_valid('remove'))

    def test_only_the_founding_genesis_can_carry_genesis_semantic_roles(self) -> None:
        schema = load('schemas/authority-commit-operations.schema.json')
        for definition in ('direct_conversation_member_join_submission',
                           'direct_conversation_strand_create_submission'):
            event = schema['$defs'][definition]['allOf'][1]['properties']['event']
            validator = Draft202012Validator(event['properties']['semantic_refs'])
            for role in ('direct_conversation_contact_round', 'direct_conversation_agent_provision'):
                with self.subTest(definition=definition, role=role):
                    self.assertFalse(validator.is_valid([{'role': role}]))
            self.assertTrue(validator.is_valid([{'role': 'references'}]))

    def test_argon2_kdf_null_cannot_enter_the_signed_envelope(self) -> None:
        schema = load('schemas/key-backup.schema.json')
        validator = Draft202012Validator(schema['properties']['encryption']['properties']['kdf'])
        kdf = {'name': 'argon2id', 'salt': 'A' * 22,
               'params': {'memory_kib': 65536, 'iterations': 3, 'parallelism': 1}}
        self.assertTrue(validator.is_valid(kdf))
        kdf['params']['digest_algorithm'] = None
        self.assertFalse(validator.is_valid(kdf))
        kdf = {'name': 'pbkdf2', 'salt': 'A' * 22, 'degraded_profile_reason': 'restricted runtime',
               'params': {'iterations': 600000, 'digest_algorithm': 'sha256'}}
        self.assertTrue(validator.is_valid(kdf))
        kdf['params']['digest_algorithm'] = None
        self.assertFalse(validator.is_valid(kdf))
        kdf['params'].pop('digest_algorithm')
        self.assertFalse(validator.is_valid(kdf))


if __name__ == '__main__':
    unittest.main()
