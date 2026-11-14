"""Scope-bound correlation handles retain literals and reject another namespace."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "spec/v1/artifacts/schemas"
OWNERS = [
    ('account-subscribe-frame.schema.json', '/$defs/agent_draft_pending_intent_key/properties/draft_id'),
    ('agent-draft-private.schema.json', '/$defs/agent_draft_content_handoff_plaintext/properties/draft_id'),
    ('agent-draft-private.schema.json', '/$defs/agent_draft_account_data_value/properties/draft_id'),
    ('agent-draft-private.schema.json', '/$defs/agent_draft_pending_intent_live/properties/draft_id'),
    ('agent-draft-private.schema.json', '/$defs/agent_draft_pending_intent_terminal_redacted/properties/draft_id'),
    ('applet-install-operations.schema.json', '/$defs/applet_install_response_body/properties/install_id'),
    ('authority-commit-operations.schema.json', '/$defs/membership_compensation_delegation_core/properties/admission_id'),
    ('authority-commit-operations.schema.json', '/$defs/membership_compensation_terminal_certificate/properties/admission_id'),
    ('authority-commit-operations.schema.json', '/$defs/membership_compensation_single_use_binding/properties/admission_id'),
    ('call-invitation-operations.schema.json', '/$defs/admission_request_body/properties/focus_id'),
    ('call-recording-artifact.schema.json', '/$defs/recording_encryption/properties/context/properties/focus_id'),
    ('current-state.schema.json', '/$defs/current_agent_action_approval/properties/selector/properties/approval_id'),
    ('current-state.schema.json', '/$defs/current_policy_action/properties/selector/properties/action_id'),
    ('event-payload.schema.json', '/$defs/agent_action_approve_payload/properties/approval_id'),
    ('event-payload.schema.json', '/$defs/agent_action_approve_payload/properties/draft_id'),
    ('event-payload.schema.json', '/$defs/agent_action_reject_payload/properties/rejection_id'),
    ('event-payload.schema.json', '/$defs/agent_action_request_payload/properties/draft_id'),
    ('event-payload.schema.json', '/$defs/agent_draft_propose_payload/properties/draft_id'),
    ('event-payload.schema.json', '/$defs/call_participant/properties/focus_id'),
    ('event-payload.schema.json', '/$defs/policy_action_state_payload/properties/action_id'),
    ('event-payload.schema.json', '/$defs/realm_organization_payload/properties/statement_id'),
    ('event-payload.schema.json', '/$defs/realm_organization_payload/properties/supersedes_statement_id'),
    ('event-payload.schema.json', '/$defs/realm_organization_payload/properties/revokes_statement_id'),
    ('event-payload.schema.json', '/$defs/media_service_focus/properties/focus_id'),
    ('realm-organization-operations.schema.json', '/$defs/realm_organization_relationship_view/properties/statement_id'),
    ('realm-organization-operations.schema.json', '/$defs/realm_organization_relationship_view/properties/supersedes_statement_id'),
    ('realm-organization-operations.schema.json', '/$defs/realm_organization_relationship_view/properties/revokes_statement_id'),
    ('service-operation-dtos.schema.json', '/$defs/ArkretNativeMediaBackendToken/properties/payload/properties/focus_id'),
    ('service-operation-dtos.schema.json', '/$defs/CallMediaTokenExchangeResponseBody/properties/focus_id'),
    ('service-operation-dtos.schema.json', '/$defs/CallMediaTokenExchangeRequestBody/properties/focus_id'),
]
EXISTING_FIXTURE_FIELDS = [
    ('spec/v1/artifacts/fixtures/actor-private-events-submit-fixture.json', '/schema_validation_cases/3/instance/rejection_id', 'rejection_id'),
    ('spec/v1/artifacts/fixtures/actor-private-events-submit-fixture.json', '/schema_validation_cases/6/instance/draft_id', 'draft_id'),
    ('spec/v1/artifacts/fixtures/agent-draft-pending-intent-fixture.json', '/schema_validation_cases/0/instance/draft_id', 'draft_id'),
    ('spec/v1/artifacts/fixtures/agent-draft-pending-intent-fixture.json', '/schema_validation_cases/3/instance/draft_id', 'draft_id'),
    ('spec/v1/artifacts/fixtures/agent-draft-pending-intent-fixture.json', '/schema_validation_cases/7/instance/draft_id', 'draft_id'),
    ('spec/v1/artifacts/fixtures/call-current-fixture.json', '/original_rows/2/event/payload/roster_delta/participant/focus_id', 'focus_id'),
    ('spec/v1/artifacts/fixtures/call-current-fixture.json', '/original_rows/3/event/payload/roster_delta/participant/focus_id', 'focus_id'),
    ('spec/v1/artifacts/fixtures/call-current-fixture.json', '/original_rows/7/event/payload/roster_delta/participant/focus_id', 'focus_id'),
    ('spec/v1/artifacts/fixtures/call-current-fixture.json', '/original_rows/10/event/payload/roster_delta/participant/focus_id', 'focus_id'),
    ('spec/v1/artifacts/fixtures/call-current-fixture.json', '/checkpoints/2/current_state_entries/2/value/entries/0/value/participant/focus_id', 'focus_id'),
    ('spec/v1/artifacts/fixtures/call-current-fixture.json', '/checkpoints/2/current_state_entries/2/value/last_source/value/participant/focus_id', 'focus_id'),
    ('spec/v1/artifacts/fixtures/call-current-fixture.json', '/checkpoints/3/current_state_entries/2/value/entries/0/value/participant/focus_id', 'focus_id'),
    ('spec/v1/artifacts/fixtures/call-current-fixture.json', '/checkpoints/3/current_state_entries/2/value/entries/1/value/participant/focus_id', 'focus_id'),
    ('spec/v1/artifacts/fixtures/call-current-fixture.json', '/checkpoints/3/current_state_entries/2/value/last_source/value/participant/focus_id', 'focus_id'),
    ('spec/v1/artifacts/fixtures/call-current-fixture.json', '/checkpoints/4/current_state_entries/2/value/entries/0/value/participant/focus_id', 'focus_id'),
    ('spec/v1/artifacts/fixtures/call-current-fixture.json', '/checkpoints/4/current_state_entries/2/value/entries/1/value/participant/focus_id', 'focus_id'),
    ('spec/v1/artifacts/fixtures/call-current-fixture.json', '/checkpoints/4/current_state_entries/2/value/last_source/value/participant/focus_id', 'focus_id'),
    ('spec/v1/artifacts/fixtures/call-current-fixture.json', '/checkpoints/5/current_state_entries/2/value/entries/0/value/participant/focus_id', 'focus_id'),
    ('spec/v1/artifacts/fixtures/call-current-fixture.json', '/checkpoints/5/current_state_entries/2/value/entries/1/value/participant/focus_id', 'focus_id'),
    ('spec/v1/artifacts/fixtures/call-current-fixture.json', '/checkpoints/5/current_state_entries/2/value/last_source/value/participant/focus_id', 'focus_id'),
    ('spec/v1/artifacts/fixtures/call-current-fixture.json', '/checkpoints/6/current_state_entries/2/value/entries/0/value/participant/focus_id', 'focus_id'),
    ('spec/v1/artifacts/fixtures/call-current-fixture.json', '/checkpoints/6/current_state_entries/2/value/entries/1/value/participant/focus_id', 'focus_id'),
    ('spec/v1/artifacts/fixtures/call-current-fixture.json', '/checkpoints/6/current_state_entries/2/value/last_source/value/participant/focus_id', 'focus_id'),
    ('spec/v1/artifacts/fixtures/call-current-fixture.json', '/checkpoints/7/current_state_entries/2/value/entries/0/value/participant/focus_id', 'focus_id'),
    ('spec/v1/artifacts/fixtures/call-current-fixture.json', '/checkpoints/7/current_state_entries/2/value/entries/1/value/participant/focus_id', 'focus_id'),
    ('spec/v1/artifacts/fixtures/call-current-fixture.json', '/checkpoints/7/current_state_entries/2/value/last_source/value/participant/focus_id', 'focus_id'),
    ('spec/v1/artifacts/fixtures/call-current-fixture.json', '/checkpoints/8/current_state_entries/2/value/entries/0/value/participant/focus_id', 'focus_id'),
    ('spec/v1/artifacts/fixtures/call-current-fixture.json', '/checkpoints/10/current_state_entries/2/value/entries/0/value/participant/focus_id', 'focus_id'),
    ('spec/v1/artifacts/fixtures/call-current-fixture.json', '/checkpoints/10/current_state_entries/2/value/last_source/value/participant/focus_id', 'focus_id'),
    ('spec/v1/artifacts/fixtures/event-payload-value-closure-fixture.json', '/schema_validation_cases/11/instance/action_id', 'action_id'),
    ('spec/v1/artifacts/fixtures/event-payload-value-closure-fixture.json', '/schema_validation_cases/12/instance/action_id', 'action_id'),
    ('spec/v1/artifacts/fixtures/event-payload-value-closure-fixture.json', '/schema_validation_cases/13/instance/action_id', 'action_id'),
    ('spec/v1/artifacts/fixtures/event-payload-value-closure-fixture.json', '/schema_validation_cases/14/instance/action_id', 'action_id'),
    ('spec/v1/artifacts/fixtures/event-payload-value-closure-fixture.json', '/schema_validation_cases/15/instance/action_id', 'action_id'),
    ('spec/v1/artifacts/fixtures/realm-organization-fixture.json', '/schema_validation_cases/0/instance/statement_id', 'statement_id'),
    ('spec/v1/artifacts/fixtures/realm-organization-fixture.json', '/schema_validation_cases/1/instance/statement_id', 'statement_id'),
    ('spec/v1/artifacts/fixtures/realm-organization-fixture.json', '/schema_validation_cases/2/instance/statement_id', 'statement_id'),
    ('spec/v1/artifacts/fixtures/realm-organization-fixture.json', '/schema_validation_cases/3/instance/statement_id', 'statement_id'),
    ('spec/v1/artifacts/fixtures/realm-organization-fixture.json', '/schema_validation_cases/4/instance/statement_id', 'statement_id'),
    ('spec/v1/artifacts/fixtures/realm-organization-fixture.json', '/schema_validation_cases/5/instance/statement_id', 'statement_id'),
    ('spec/v1/artifacts/fixtures/realm-organization-fixture.json', '/schema_validation_cases/6/instance/statement_id', 'statement_id'),
    ('spec/v1/artifacts/fixtures/realm-organization-fixture.json', '/schema_validation_cases/7/instance/statement_id', 'statement_id'),
    ('spec/v1/artifacts/fixtures/realm-organization-fixture.json', '/schema_validation_cases/8/instance/statement_id', 'statement_id'),
    ('spec/v1/artifacts/fixtures/realm-organization-fixture.json', '/schema_validation_cases/9/instance/statement_id', 'statement_id'),
    ('spec/v1/artifacts/fixtures/realm-organization-fixture.json', '/schema_validation_cases/10/instance/statement_id', 'statement_id'),
    ('spec/v1/artifacts/fixtures/realm-organization-fixture.json', '/schema_validation_cases/11/instance/statement_id', 'statement_id'),
    ('spec/v1/artifacts/fixtures/realm-organization-fixture.json', '/schema_validation_cases/12/instance/statement_id', 'statement_id'),
    ('spec/v1/artifacts/fixtures/realm-organization-fixture.json', '/schema_validation_cases/13/instance/statement_id', 'statement_id'),
    ('spec/v1/artifacts/fixtures/realm-organization-fixture.json', '/schema_validation_cases/6/instance/revokes_statement_id', 'revokes_statement_id'),
    ('spec/v1/artifacts/fixtures/schema-validation-fixture.json', '/schema_validation_cases/4/instance/approval_id', 'approval_id'),
]
PREEXISTING_BOUND_OWNERS = [
    ('grant-constraint.schema.json', '/properties/constraint_id'),
    ('agent-operations.schema.json', '/$defs/agent_key_authorization_state/properties/key_id'),
    ('applet-package.schema.json', '/properties/package_id'),
    ('content-encryption.schema.json', '/$defs/content_epoch_root/properties/secret_id'),
    ('event-payload.schema.json', '/$defs/agent_action_approve_payload/properties/request_id'),
    ('event-payload.schema.json', '/$defs/agent_action_reject_payload/properties/request_id'),
    ('event-payload.schema.json', '/$defs/agent_action_request_payload/properties/request_id'),
    ('grant-constraint.schema.json', '/properties/allowed_session_ids/items'),
    ('key-backup-plaintext.schema.json', '/$defs/secret_storage_item/properties/secret_id'),
    ('key-backup.schema.json', '/properties/contents/items/properties/secret_id'),
    ('keys-operations.schema.json', '/$defs/signed_prekey/properties/key_id'),
    ('service-describe.schema.json', '/properties/verified_profiles/items/properties/verification_run_id'),
    ('service-operation-dtos.schema.json', '/$defs/SessionGrantMetadata/properties/session_id'),
]

PROFILE_NAMES = {"action_id":"realm_action_name", "admission_id":"membership_admission_handle", "approval_id":"agent_confirmation_handle", "draft_id":"agent_draft_handle", "focus_id":"media_focus_handle", "install_id":"applet_install_handle", "rejection_id":"agent_rejection_handle", "statement_id":"organization_statement_handle", "revokes_statement_id":"organization_statement_handle", "supersedes_statement_id":"organization_statement_handle"}


class ScopedIdentifierHandleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.documents = {p.name:json.loads(p.read_text(encoding="utf-8")) for p in SCHEMAS.glob("*.json")}
        cls.registry = Registry().with_resources((d["$id"], Resource.from_contents(d)) for d in cls.documents.values() if "$id" in d)

    def validator(self, file_name, pointer):
        return Draft202012Validator({"$ref":self.documents[file_name]["$id"]+"#"+pointer}, registry=self.registry)

    def test_every_exact_owner_has_the_bounded_non_typed_profile(self):
        self.assertEqual(len(OWNERS), 30)
        for file_name, pointer in OWNERS:
            with self.subTest(owner=file_name+"#"+pointer):
                validator = self.validator(file_name, pointer)
                validator.validate("local:reference-1")
                shape = self.documents[file_name]
                for token in pointer.split("/")[1:]:
                    token = token.replace("~1", "/").replace("~0", "~")
                    shape = shape[int(token)] if isinstance(shape,list) else shape[token]
                maximum = min(256, shape.get("maxLength", 256))
                validator.validate("x" * maximum)
                self.assertTrue(list(validator.iter_errors("x" * (maximum + 1))))
                for invalid in ("", "ak:realm:example", "ak:unknown_kind:example", "x" * 257, 1, None):
                    self.assertTrue(list(validator.iter_errors(invalid)), invalid)

    def test_existing_fixture_handles_remain_valid_without_changing_their_bytes(self):
        for file_name, pointer, name in EXISTING_FIXTURE_FIELDS:
            value = json.loads((ROOT / file_name).read_text(encoding="utf-8"))
            for token in pointer.split("/")[1:]:
                token = token.replace("~1", "/").replace("~0", "~")
                value = value[int(token)] if isinstance(value,list) else value[token]
            with self.subTest(owner=file_name+"#"+pointer):
                self.validator("string-profiles.schema.json", "/$defs/"+PROFILE_NAMES[name]).validate(value)

    def test_rate_limit_policy_reuses_the_existing_policy_kind(self):
        validator = self.validator("service-describe.schema.json", "/properties/rate_limit_policy_id")
        validator.validate("ak:policy:01904100-0000-7000-8000-000000000001")
        for invalid in ("", "default-policy", "ak:space:01904100-0000-7000-8000-000000000001", None):
            self.assertTrue(list(validator.iter_errors(invalid)), invalid)

    def test_preexisting_opaque_and_local_roles_have_actual_upper_bounds(self):
        self.assertEqual(len(PREEXISTING_BOUND_OWNERS), 13)
        for file_name, pointer in PREEXISTING_BOUND_OWNERS:
            with self.subTest(owner=file_name+"#"+pointer):
                validator = self.validator(file_name, pointer)
                validator.validate("opaque-1")
                validator.validate("x" * 256)
                for invalid in ("", "ak:device:example", "x" * 257):
                    self.assertTrue(list(validator.iter_errors(invalid)), invalid)
