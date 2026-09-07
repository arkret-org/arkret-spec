"""Closure tests for the compact MIMI abuse-report request."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "spec" / "v1" / "artifacts"


class MimiReportAbuseRequestSchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(
            (ARTIFACTS / "schemas" / "mimi-operations.schema.json").read_text(
                encoding="utf-8"
            )
        )
        cls.registry = json.loads(
            (ARTIFACTS / "registry" / "proof-context-registry.json").read_text(
                encoding="utf-8"
            )
        )

    def test_request_is_the_closed_compact_shape(self) -> None:
        request = self.schema["$defs"]["mimi_report_abuse_request_body"]
        self.assertFalse(request["additionalProperties"])
        self.assertEqual(set(request["required"]), {"reporter_authority", "report_event"})
        self.assertEqual(
            set(request["properties"]),
            {"reporter_authority", "report_event", "cbs_proof_bundles"},
        )

    def test_signed_event_and_transport_id_have_no_outer_mirrors(self) -> None:
        request = self.schema["$defs"]["mimi_report_abuse_request_body"]
        retired = {
            "realm_id",
            "strand_id",
            "target_ref",
            "abuse_reason_code",
            "evidence_package",
            "franking_proof",
            "description",
            "reporter_id",
            "source_provider_id",
            "mimi_room_uri",
        }
        self.assertTrue(retired.isdisjoint(request["properties"]))

    def test_reporter_authority_is_a_local_signature_domain(self) -> None:
        domain = "ak.mimi_reporter_authority_proof.v1"
        authority = self.schema["$defs"]["mimi_reporter_authority"]
        self.assertEqual(authority["x-arkret-signature-domain"], domain)
        self.assertFalse(
            any(row.get("context") == domain for row in self.registry["contexts"])
        )
        row = next(
            row for row in self.registry["domain_separations"] if row.get("domain") == domain
        )
        self.assertEqual(row["primitive"], "detached_signature")
        self.assertEqual(
            row["binding_fields"],
            [
                "payload_digest",
                "issuer",
                "operation_id",
                "report_event",
                "cbs_proof_bundles?",
                "membership_event_id",
                "room_binding_event_id",
                "expires_at",
                "verification_method",
                "created_at",
                "domain",
                "audience",
            ],
        )


if __name__ == "__main__":
    unittest.main()
