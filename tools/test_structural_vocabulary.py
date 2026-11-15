"""Check that compact grammar tokens cannot outlive their exact authority."""
import copy
import json
import unittest
from unittest.mock import patch

from tools.artifact_lint.core import CANONICAL_LEXEME_REGISTRY_PATH, Lint, schema_validator
from tools.artifact_lint.naming import nc_lexeme_001, registry_metadata_key_errors
from tools.artifact_lint import prose


class StructuralVocabularyTest(unittest.TestCase):
    def registry(self):
        return json.loads(CANONICAL_LEXEME_REGISTRY_PATH.read_text(encoding="utf-8"))

    def errors(self, registry):
        original = prose.load_json

        def load(lint, path):
            return copy.deepcopy(registry) if path == CANONICAL_LEXEME_REGISTRY_PATH else original(lint, path)

        lint = Lint()
        with patch.object(prose, "load_json", side_effect=load):
            prose.check_naming_predicates(lint)
        return [error for error in lint.errors if "registered_structural_vocabulary" in error]

    def test_current_exact_authorities_resolve(self):
        self.assertEqual(self.errors(self.registry()), [])

    def test_operator_literal_cannot_point_to_another_operator(self):
        registry = self.registry()
        row = next(row for row in registry["registered_structural_vocabulary"] if row["token"] == "eq")
        row["anchor"] = row["anchor"].rsplit("/", 1)[0] + "/1"
        self.assertTrue(any("mismatched authority" in error for error in self.errors(registry)))

    def test_patch_directive_cannot_borrow_a_sibling_property(self):
        registry = self.registry()
        row = next(row for row in registry["registered_structural_vocabulary"] if row["token"] == "$op")
        row["anchor"] = row["anchor"].rsplit("/", 1)[0] + "/value"
        self.assertTrue(any("mismatched authority" in error for error in self.errors(registry)))

    def test_unknown_role_and_unscoped_authority_are_rejected(self):
        for field, value in (("grammar_role", "any_ordinary_word"), ("anchor", "spec/v1/zh/models/common-fields.md")):
            registry = self.registry()
            registry["registered_structural_vocabulary"][0][field] = value
            with self.subTest(field=field):
                self.assertTrue(self.errors(registry))

    def test_query_operator_is_explicit_and_legacy_field_is_rejected(self):
        validator = schema_validator(prose.ARTIFACTS / "schemas/query.schema.json", "#/$defs/field_filter")
        validator.validate({"field": "stage", "operator": "eq", "value": "done"})
        self.assertTrue(list(validator.iter_errors({"field": "stage", "op": "eq", "value": "done"})))

    def test_authorization_stem_is_unambiguous_in_fields_and_types(self):
        for name in ("auth_binding", "realm_actor_backup_auth_binding", "RealmActorBackupAuthBinding"):
            self.assertTrue(nc_lexeme_001(name), name)
        self.assertFalse(nc_lexeme_001("authorization_binding"))


class FixedRegistryMetadataTest(unittest.TestCase):
    def contract(self):
        return {
            "realm_actor_contract": {"content_backup_contract": {"source_disclosure": {"device": []}}},
            "content_encryption_contract": {"realm_actor_native_custody": {}},
            "operation_registry": {"operations": []},
        }

    def test_current_registered_metadata_is_snake_case(self):
        for name in ("contract-registry.json", "content-encryption-registry.json", "morph-kind-decision-table.json"):
            document = json.loads((prose.ARTIFACTS / "registry" / name).read_text(encoding="utf-8"))
            self.assertEqual(registry_metadata_key_errors(name, document), [], name)

    def test_nested_subject_metadata_and_auth_requirements_are_checked(self):
        for owner in ("subject", "operation"):
            document = self.contract()
            if owner == "subject":
                document["realm_actor_contract"]["content_backup_contract"]["source_disclosure"]["Device"] = []
            else:
                document["operation_registry"]["operations"].append({"auth_requirements": {"Device_PUT_allowed": False}})
            with self.subTest(owner=owner):
                self.assertTrue(registry_metadata_key_errors("contract-registry.json", document))

    def test_removed_owner_does_not_silently_shrink_the_gate(self):
        document = self.contract()
        del document["realm_actor_contract"]["content_backup_contract"]
        self.assertTrue(registry_metadata_key_errors("contract-registry.json", document))

    def test_external_keywords_and_symbol_maps_outside_owned_roots_are_preserved(self):
        document = self.contract()
        document["event_kind_registry"] = {"schema": {"minItems": 1}, "ak.external.Symbol": {}}
        document["realm_actor_contract"]["content_backup_contract"]["rule"] = "Device MUST NOT acquire a new public API"
        self.assertEqual(registry_metadata_key_errors("contract-registry.json", document), [])

    def test_normative_keyword_as_metadata_key_is_not_prose(self):
        self.assertTrue(registry_metadata_key_errors("morph-kind-decision-table.json", {"conflict": [{"MUST_NOT": "widen"}]}))
        self.assertEqual(registry_metadata_key_errors("morph-kind-decision-table.json", {"conflict": [{"must_not": "widen"}]}), [])


if __name__ == "__main__":
    unittest.main()
