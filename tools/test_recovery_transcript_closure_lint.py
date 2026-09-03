"""Mutation tests for recovery transcript and registered-context closure."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import recovery_transcripts
from tools.artifact_lint.core import Lint


class RecoveryTranscriptClosureLintTest(unittest.TestCase):
    def _recovery_lint(self, mutate) -> list[str]:
        original = recovery_transcripts.load_json

        def mutated_load(lint, path):
            value = original(lint, path)
            if isinstance(value, dict):
                value = copy.deepcopy(value)
                mutate(path.resolve(), value)
            return value

        recovery_transcripts.load_json = mutated_load
        try:
            lint = Lint()
            recovery_transcripts.check_recovery_transcript_closure(lint)
            return lint.errors
        finally:
            recovery_transcripts.load_json = original

    def test_current_recovery_closure_passes(self) -> None:
        self.assertEqual(self._recovery_lint(lambda _path, _value: None), [])

    def test_generic_did_root_path_fails(self) -> None:
        schema = recovery_transcripts.SCHEMA.resolve()

        def mutate(path, value):
            if path == schema:
                value["$defs"]["generic_recovery_transcript"]["properties"]["kind"]["enum"].insert(
                    0, "did_root"
                )

        errors = self._recovery_lint(mutate)
        self.assertTrue(any("generic_recovery_transcript kind enum" in error for error in errors), errors)

    def test_missing_domain_registration_fails(self) -> None:
        registry = recovery_transcripts.REGISTRY.resolve()

        def mutate(path, value):
            if path == registry:
                value["domain_separations"] = [
                    row
                    for row in value["domain_separations"]
                    if row.get("domain") != recovery_transcripts.DOMAIN
                ]

        errors = self._recovery_lint(mutate)
        self.assertTrue(any("exactly one domain_separations row" in error for error in errors), errors)

    def test_recovery_share_hardware_branch_fails(self) -> None:
        policy = recovery_transcripts.POLICY_SCHEMA.resolve()

        def mutate(path, value):
            if path == policy:
                value["$defs"]["recovery_share_holder"]["properties"]["holder_kind"]["enum"].append(
                    "hardware_module"
                )

        errors = self._recovery_lint(mutate)
        self.assertTrue(any("exact two-branch enum" in error for error in errors), errors)

    def test_recovery_share_discriminator_branch_mismatch_fails(self) -> None:
        policy = recovery_transcripts.POLICY_SCHEMA.resolve()

        def mutate(path, value):
            if path == policy:
                branch = value["$defs"]["recovery_share_holder"]["oneOf"][0]
                branch["required"] = ["holder_service_id"]

        errors = self._recovery_lint(mutate)
        self.assertTrue(any("matching branch-specific holder field" in error for error in errors), errors)

    def test_recovery_share_branch_ref_drift_fails(self) -> None:
        schema = recovery_transcripts.SCHEMA.resolve()

        def mutate(path, value):
            if path == schema:
                item = value["$defs"]["threshold_recovery_proof_body"]["properties"]["share_releases"]["items"]
                item["allOf"] = []

        errors = self._recovery_lint(mutate)
        self.assertTrue(any("must reuse recovery_share_holder exactly" in error for error in errors), errors)

    def test_registered_context_schema_copy_fails(self) -> None:
        original = recovery_transcripts.load_json
        target = recovery_transcripts.SCHEMA.resolve()
        registry = original(Lint(), recovery_transcripts.REGISTRY)
        row = registry["contexts"][0]
        fields = [field.removesuffix("?") for field in row["binding_fields"]]

        def mutated_load(lint, path):
            value = original(lint, path)
            if isinstance(value, dict):
                value = copy.deepcopy(value)
            if path.resolve() == target:
                value["$defs"]["registered_context_copy_probe"] = {
                    "type": "object",
                    "properties": {
                        "context": {"const": row["context"]},
                        **{field: {} for field in fields},
                    },
                    "additionalProperties": False,
                }
            return value

        recovery_transcripts.load_json = mutated_load
        try:
            lint = Lint()
            recovery_transcripts.check_registered_context_schema_duplicates(lint)
            errors = lint.errors
        finally:
            recovery_transcripts.load_json = original
        self.assertTrue(any("registered_context_copy_probe" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
