"""Validate canonical write guards and single-source artifact/challenge shapes."""

import base64
import copy
import json
from pathlib import Path
import unittest

from tools.artifact_lint.core import schema_validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "spec/v1/artifacts/schemas"
TOKEN = base64.urlsafe_b64encode(b"\x01" + b"\x00" * 32).decode()
COMMIT = "ak:realm_commit:" + TOKEN
ACCOUNT = {"principal_id": "ak:did_core:web:alice.example", "station_id": "ak:did_core:web:station.example"}


class CommitArtifactChallengeContract(unittest.TestCase):
    def test_cas_is_single_identity_and_read_revision_keeps_position(self):
        write = schema_validator(SCHEMAS / "event-payload.schema.json", "#/$defs/capability_revoke_payload/properties/expected_commit_id")
        self.assertTrue(write.is_valid(COMMIT))
        self.assertFalse(write.is_valid({"commit_id": COMMIT, "stream_position": 1}))
        self.assertFalse(write.is_valid("ak:event:" + TOKEN))
        self.assertFalse(write.is_valid(None))
        read = schema_validator(SCHEMAS / "current-state.schema.json", "#/$defs/revision")
        self.assertTrue(read.is_valid({"commit_id": COMMIT, "stream_position": 1}))
        self.assertFalse(read.is_valid(COMMIT))

    def test_nullable_first_write_does_not_become_optional(self):
        schema = json.loads((SCHEMAS / "event-payload.schema.json").read_text(encoding="utf-8"))
        payload = schema["$defs"]["applet_registration_payload"]
        self.assertIn("expected_commit_id", payload["required"])
        self.assertNotIn("expected_revision", payload["properties"])
        guard = schema_validator(SCHEMAS / "event-payload.schema.json", "#/$defs/applet_registration_payload/properties/expected_commit_id")
        self.assertTrue(guard.is_valid(None))
        self.assertTrue(guard.is_valid(COMMIT))
        self.assertFalse(guard.is_valid({"commit_id": COMMIT, "stream_position": 0}))

    def test_consent_present_guard_has_one_identity(self):
        guard = schema_validator(SCHEMAS / "event-payload.schema.json", "#/$defs/consent_expected_current")
        self.assertTrue(guard.is_valid({"state": "present", "commit_id": COMMIT}))
        self.assertTrue(guard.is_valid({"state": "never_written"}))
        self.assertFalse(guard.is_valid({"state": "present", "revision": {"commit_id": COMMIT, "stream_position": 1}}))
        self.assertFalse(guard.is_valid({"state": "present"}))

    def test_single_challenge_canonical_bytes_and_old_nonce_rejected(self):
        schema = schema_validator(SCHEMAS / "keys-operations.schema.json", "#/$defs/keys_backups_delete_challenge")
        challenge = {
            "challenge_id": "A" * 22, "challenge": base64.urlsafe_b64encode(bytes(range(32))).decode().rstrip("="),
            "operation": "ak.self.keys.backups.resource.delete.v1", "account_id": ACCOUNT,
            "backup_id": "ak:backup:01964137-0000-7000-8000-000000000001",
            "audience": "https://station.example", "service_id": ACCOUNT["station_id"],
            "request_id": "01964137-0000-7000-8000-000000000002",
            "issued_at": "2026-11-14T00:00:00.000Z", "expires_at": "2026-11-14T00:05:00.000Z",
        }
        self.assertTrue(schema.is_valid(challenge), list(schema.iter_errors(challenge)))
        extra = dict(challenge, nonce="A" * 43)
        self.assertFalse(schema.is_valid(extra))
        for invalid in (challenge["challenge"] + "=", "A" * 42 + "B", "A" * 42):
            changed = dict(challenge, challenge=invalid)
            self.assertFalse(schema.is_valid(changed))

    def test_ready_has_one_complete_artifact(self):
        artifact = {
            "schema": "ak.schema.call_recording_artifact.v1", "realm_id": "ak:realm:" + TOKEN,
            "call_id": "ak:call:" + TOKEN, "recording_id": "recording-1",
            "recording_start_event_id": "ak:event:" + TOKEN, "blob_ref": "ak:blob:sha256:" + "0" * 64,
            "size_bytes": 1, "duration_ms": 1, "media_type": "audio/ogg",
            "encryption": {"encryption_algorithm": "mls_exporter_aead_xchacha20poly1305", "exporter_label": "ak.rtc-recording-key/v1",
                "context": {"realm_id": "ak:realm:" + TOKEN, "call_id": "ak:call:" + TOKEN, "focus_id": "focus-1", "recording_id": "recording-1", "media_service_id": ACCOUNT["station_id"], "recording_start_event_id": "ak:event:" + TOKEN}},
            "retention": {"retention_expires_at": "2026-12-14T00:00:00.000Z", "consent_confirmed": True},
            "produced_by": ACCOUNT["station_id"], "recording_initiator_capability_ref": "ak:grant:" + TOKEN,
            "created_at": "2026-11-14T00:00:00.000Z",
        }
        schema = schema_validator(SCHEMAS / "event-payload.schema.json", "#/$defs/call_state_payload/properties/recording_transition")
        ready = {"recording_id": "recording-1", "from": "stopped", "to": "ready", "capture_metadata": {"artifact": artifact}}
        self.assertTrue(schema.is_valid(ready), list(schema.iter_errors(ready)))
        for name, value in (("duration_ms", 1), ("retention", artifact["retention"]), ("recording_start_event_id", artifact["recording_start_event_id"])):
            bad = copy.deepcopy(ready)
            bad["capture_metadata"][name] = value
            self.assertFalse(schema.is_valid(bad))
        bad = copy.deepcopy(ready)
        bad["capture_metadata"]["artifact"]["content_digest"] = "sha256:" + "0" * 64
        self.assertFalse(schema.is_valid(bad))
        bad = copy.deepcopy(ready)
        bad["to"] = "failed"
        self.assertFalse(schema.is_valid(bad))


if __name__ == "__main__":
    unittest.main()
