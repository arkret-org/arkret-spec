"""Focused tests for lint runtime classification and response-shape inference."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
MODULE_SPEC = importlib.util.spec_from_file_location(
    "lint_artifacts_runtime", ROOT / "tools" / "lint_artifacts.py"
)
assert MODULE_SPEC is not None and MODULE_SPEC.loader is not None
lint_artifacts = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(lint_artifacts)


class LintArtifactsRuntimeTest(unittest.TestCase):
    def test_success_shape_uses_response_media_type(self) -> None:
        self.assertEqual(
            lint_artifacts.infer_openapi_success_shape(
                "get",
                {
                    "application/x-ndjson": {
                        "schema": {"$ref": "../schemas/realtime-envelope.schema.json"}
                    }
                },
            ),
            "event_stream",
        )
        self.assertEqual(
            lint_artifacts.infer_openapi_success_shape(
                "get",
                {"application/octet-stream": {"schema": {"type": "string"}}},
            ),
            "binary_stream",
        )
        self.assertEqual(
            lint_artifacts.infer_openapi_success_shape("head", {}),
            "metadata_headers",
        )

    def test_unrelated_kind_is_not_classified_as_event(self) -> None:
        lint = lint_artifacts.Lint()
        lint_artifacts.check_event_envelope_candidates(
            lint,
            ROOT / "synthetic.json",
            {"kind": "ak.typing", "ciphertext": "opaque"},
            {"ak.message.create"},
        )
        self.assertEqual(lint.errors, [])

    def test_event_identity_fields_enable_event_kind_validation(self) -> None:
        lint = lint_artifacts.Lint()
        lint_artifacts.check_event_envelope_candidates(
            lint,
            ROOT / "synthetic.json",
            {
                "event_id": "ak:event:00000000-0000-7000-8000-000000000000",
                "realm_id": "ak:realm:00000000-0000-7000-8000-000000000000",
                "kind": "ak.unknown",
                "payload": {},
            },
            {"ak.message.create"},
        )
        self.assertTrue(
            any("unregistered Event.kind: ak.unknown" in error for error in lint.errors),
            lint.errors,
        )

    def test_rejected_case_may_contain_intentionally_invalid_event(self) -> None:
        lint = lint_artifacts.Lint()
        lint_artifacts.check_event_envelope_candidates(
            lint,
            ROOT / "synthetic.json",
            {
                "input": {
                    "event": {
                        "event_id": "ak:event:00000000-0000-7000-8000-000000000000",
                        "realm_id": "ak:realm:00000000-0000-7000-8000-000000000000",
                        "kind": "ak.typing",
                        "payload": {},
                    }
                },
                "expected": {"decision": "reject"},
            },
            {"ak.message.create"},
        )
        self.assertEqual(lint.errors, [])


if __name__ == "__main__":
    unittest.main()
