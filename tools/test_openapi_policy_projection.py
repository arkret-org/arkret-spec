#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import artifact_pipeline


class OpenApiPolicyProjectionTests(unittest.TestCase):
    def test_projection_replaces_stale_public_operation_list(self) -> None:
        catalog = {
            "operation_registry": {
                "high_security_session_authentication_policy": {
                    "applies_to_operation_id_prefix": "ak.self.",
                    "protected_operation_default": "rfc9421_session_public_key_required",
                    "unauthenticated_public_projection_operations": [
                        "ak.self.events.read.describe.v1",
                        "ak.self.account.read.describe.v1",
                        "ak.self.example.read.describe.v1",
                    ],
                    "new_operation_rule": "Unknown operations fail closed.",
                }
            }
        }
        stale = """openapi: 3.2.0
x-arkret-high-security-session-authentication-policy:
  appliesToOperationIdPrefix: ak.self.
  protectedOperationDefault: rfc9421_session_public_key_required
  unauthenticatedPublicProjectionOperations:
  - ak.self.events.read.describe.v1
  newOperationsFailClosed: true
info:
  title: Arkret Service API
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "openapi.yaml"
            path.write_text(stale, encoding="utf-8")
            with patch.object(artifact_pipeline, "OPENAPI_PATH", path):
                projected = artifact_pipeline.projected_openapi_text(catalog)
        self.assertIn("  - ak.self.example.read.describe.v1\n", projected)
        self.assertEqual(projected.count("x-arkret-high-security-session-authentication-policy:"), 1)
        self.assertTrue(projected.endswith("info:\n  title: Arkret Service API\n"))


if __name__ == "__main__":
    unittest.main()
