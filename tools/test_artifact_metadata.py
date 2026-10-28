"""Static metadata must not alter protocol identity or evidence validation."""

import unittest

from tools.check_artifact_metadata import metadata_errors


class ArtifactMetadataTests(unittest.TestCase):
    def test_metadata_free_fixture_retains_actual_contract(self):
        document = {
            "runner": {"kind": "named_suite", "entrypoint": "ak.suite.example.v1"},
            "cases": [{"instance": {"version": 8, "created_at": "2026-10-28T00:00:00.000Z"}}],
            "schema_ref": "schemas/example.schema.json",
        }
        self.assertEqual(metadata_errors(document, fixture=True), [])

    def test_root_revisions_and_duplicate_identity_are_rejected(self):
        for key in ("version", "revision", "generated_at", "source_of_truth", "format_version", "suite", "fixture_id", "fixture_kind", "schema", "lock_kind", "generated_views"):
            with self.subTest(key=key):
                self.assertTrue(metadata_errors({key: "unused"}, fixture=True))

    def test_catalog_section_cannot_restore_revision_defaults(self):
        self.assertTrue(metadata_errors({"operation_registry": {"version": 3}}, catalog=True))
        self.assertTrue(metadata_errors({"did_method_adapter_registry": {
            "principal_resolution_contract": {"version": "2026-08-30.1"},
        }}, catalog=True))

    def test_json_schema_and_real_evidence_are_untouched(self):
        self.assertEqual(metadata_errors({
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://arkret.org/v1/example.schema.json",
            "properties": {"version": {"type": "integer"}},
            "sha256": "actual bytes digest", "accepted_at": "actual execution time",
        }), [])

    def test_custom_format_labels_are_distinct_from_real_wire_schema_ids(self):
        self.assertTrue(metadata_errors({"schema": "cotest.custom-format.v1"}))
        self.assertEqual(metadata_errors({"schema": "ak.schema.realm_profile.v1"}), [])


if __name__ == "__main__":
    unittest.main()
