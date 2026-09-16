"""Device key rows keep the retained signer-evidence coordinate and no digest mirror."""

import json
import unittest
from pathlib import Path


SCHEMAS = Path(__file__).resolve().parents[1] / "spec/v1/artifacts/schemas"
DEVICE_RECORDS = ("query_device_record", "peer_query_device_record")


class DeviceHistoryEvidenceSchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.keys = json.loads(
            (SCHEMAS / "keys-operations.schema.json").read_text(encoding="utf-8")
        )

    def test_device_rows_require_the_retained_signer_evidence_ref(self):
        for name in DEVICE_RECORDS:
            record = self.keys["$defs"][name]
            self.assertIn("signer_evidence_ref", record["required"], name)
            self.assertEqual(
                record["properties"]["signer_evidence_ref"]["$ref"],
                "./authenticated-signer-resolution-evidence.schema.json#/$defs/signer_evidence_ref",
                name,
            )

    def test_device_rows_are_closed_against_a_sibling_digest_mirror(self):
        for name in DEVICE_RECORDS:
            record = self.keys["$defs"][name]
            self.assertIs(record["additionalProperties"], False, name)
            self.assertNotIn("signer_evidence_digest", record["properties"], name)

    def test_client_and_station_rows_stay_distinct_carriers(self):
        client = self.keys["$defs"]["query_device_record"]
        station = self.keys["$defs"]["peer_query_device_record"]
        self.assertIn("device_projection", client["required"])
        self.assertNotIn("device_projection_attestation", client["properties"])
        self.assertIn("device_projection_attestation", station["required"])
        self.assertNotIn("device_projection", station["properties"])


if __name__ == "__main__":
    unittest.main()
