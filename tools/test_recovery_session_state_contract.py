import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "spec/v1/artifacts/schemas/recovery-session.schema.json"


class RecoverySessionStateContractTest(unittest.TestCase):
    def test_authoritative_pcr_snapshot_fields_are_required_and_non_nullable(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        state = schema["$defs"]["recovery_session_state"]
        required = set(state["required"])
        snapshot_fields = {
            "current_device_generation_ref",
            "device_generation_status",
            "registry_head",
            "accepted_seal_frontier",
        }
        self.assertLessEqual(snapshot_fields, required)

        registry_head = state["properties"]["registry_head"]
        self.assertEqual(registry_head, {
            "$ref": "#/$defs/digest",
            "description": "Digest of the accepted identity-registry head snapshot.",
        })


if __name__ == "__main__":
    unittest.main()
