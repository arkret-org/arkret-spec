"""Recovery session state keeps the authoritative PCR snapshot, without a DID head.

zh/crypto-media/device-lifecycle.md section 12 requires the four authoritative
snapshot fields on every persisted recovery session, and separately forbids a
basic ``pcr_policy`` recovery from demanding ``registry_head``, current DID
updateKeys, a ``did_recovery_anchor`` ref, an old ``payload.did_version_id`` or
any DID publication: the session schema carries no ``registry_head`` at all, so
an unreachable DID service cannot block policy recovery. Both halves are guarded
here so neither can regress into the other.
"""

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "spec/v1/artifacts/schemas/recovery-session.schema.json"
FORBIDDEN_DID_PUBLICATION_FIELDS = {
    "registry_head",
    "did_recovery_anchor",
    "did_version_id",
    "update_keys",
}


class RecoverySessionStateContractTest(unittest.TestCase):
    def setUp(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.state = schema["$defs"]["recovery_session_state"]

    def test_authoritative_pcr_snapshot_fields_are_required_and_non_nullable(self) -> None:
        required = set(self.state["required"])
        snapshot_fields = {
            "current_device_generation_ref",
            "device_generation_status",
            "realm_stream_head",
        }
        self.assertLessEqual(snapshot_fields, required)
        for field in sorted(snapshot_fields):
            self.assertNotIn(
                "null", json.dumps(self.state["properties"][field], ensure_ascii=False), field
            )

    def test_state_carries_no_did_publication_field(self) -> None:
        present = FORBIDDEN_DID_PUBLICATION_FIELDS & set(self.state["properties"])
        self.assertEqual(present, set())
        self.assertEqual(FORBIDDEN_DID_PUBLICATION_FIELDS & set(self.state["required"]), set())


if __name__ == "__main__":
    unittest.main()
