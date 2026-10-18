"""Mutation tests for the retired discovery boundary and public metadata closure."""

from __future__ import annotations

import copy
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.artifact_lint import prose
from tools.artifact_lint.core import Lint


class DirectoryRetirementLintTest(unittest.TestCase):
    def check_mutation(self, filename=None, mutate=None, threat_suffix=""):
        original_load = prose.load_json
        original_read = Path.read_text

        def load(lint, path):
            value = copy.deepcopy(original_load(lint, path))
            if filename and path.name == filename:
                mutate(value)
            return value

        def read(path, *args, **kwargs):
            value = original_read(path, *args, **kwargs)
            if path.name == "server-threat-model.md":
                value += threat_suffix
            return value

        lint = Lint()
        with patch.object(prose, "load_json", load), patch.object(Path, "read_text", read):
            prose.check_directory_field_drift(lint)
        return lint.errors

    def test_current_contract_passes(self):
        self.assertEqual(self.check_mutation(), [])

    def test_retired_threat_obligations_fail(self):
        for token in ("Consent / PSI oracle", "announce replay", "policy_revision rollback",
                      "Directory Ingest Abuse", "discovery-directory §8.10 / §11"):
            with self.subTest(token=token):
                self.assertTrue(any("retired discovery" in e for e in self.check_mutation(threat_suffix=token)))

    def test_source_refs_cannot_expand_directory_entry(self):
        def mutate(data):
            data["$defs"]["public_realm_directory_entry"]["properties"]["source_refs"] = {}
        self.assertTrue(self.check_mutation("directory-operations.schema.json", mutate))

    def test_public_metadata_cannot_gain_membership(self):
        def mutate(data):
            data["$defs"]["PublicRealmMetadata"]["properties"]["members"] = {}
        self.assertTrue(self.check_mutation("service-operation-dtos.schema.json", mutate))

    def test_public_metadata_cannot_become_open(self):
        def mutate(data):
            data["$defs"]["PublicRealmMetadata"]["additionalProperties"] = True
        self.assertTrue(self.check_mutation("service-operation-dtos.schema.json", mutate))

    def test_negative_directory_obligations_cannot_be_removed(self):
        for key in ("unregistered_write_attempts_change_no_index",
                    "listed_restricted_and_unconfirmed_realms_are_hidden",
                    "expired_entries_never_answer_or_auto_renew",
                    "public_metadata_never_contains_source_or_authority_evidence"):
            with self.subTest(key=key):
                def mutate(data):
                    data["cases"][0]["expected"].pop(key)
                self.assertTrue(any(key in e for e in self.check_mutation("privacy-security-fixture.json", mutate)))


if __name__ == "__main__":
    unittest.main()
