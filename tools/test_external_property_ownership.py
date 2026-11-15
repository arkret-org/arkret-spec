"""External fields receive exact ownership; newly added members remain local."""
import json
import unittest
from unittest.mock import patch

from tools.artifact_lint import naming_contracts
from tools.artifact_lint.core import Lint
from tools.artifact_lint.naming import external_literal_property_names


class ExternalPropertyOwnershipTest(unittest.TestCase):
    def owner(self):
        return {"type": "object", "properties": {
            "externalName": {"type": "string"}, "local_name": {"type": "string"}},
            "x-arkret-external-literal-object": {
                "specification": "External Example", "anchor": "https://example.org/spec#object",
                "external_properties": ["externalName"]}}

    def errors(self, owner):
        return naming_contracts._wire_property_owner_case_errors("/owner", owner)

    def test_exact_external_field_and_ordinary_local_field_coexist(self):
        owner = self.owner()
        self.assertEqual(self.errors(owner), [])
        self.assertEqual(external_literal_property_names(owner), {"externalName"})

    def test_new_unlisted_camel_case_member_gets_no_exemption(self):
        owner = self.owner()
        owner["properties"]["newLocalName"] = {"type": "string"}
        self.assertTrue(any("newLocalName" in error and "Arkret-owned" in error for error in self.errors(owner)))

    def test_missing_empty_duplicate_unknown_and_malformed_lists_fail_closed(self):
        for names in (None, [], ["externalName", "externalName"], ["absent"], [42], "externalName"):
            owner = self.owner()
            if names is None:
                del owner["x-arkret-external-literal-object"]["external_properties"]
            else:
                owner["x-arkret-external-literal-object"]["external_properties"] = names
            with self.subTest(names=names):
                self.assertTrue(self.errors(owner))
                self.assertEqual(external_literal_property_names(owner), set())

    def test_renaming_a_declared_external_field_makes_the_old_list_stale(self):
        owner = self.owner()
        owner["properties"]["renamed_external"] = owner["properties"].pop("externalName")
        self.assertTrue(any("stale" in error for error in self.errors(owner)))

    def test_ownership_does_not_follow_a_nested_object_or_reference(self):
        owner = self.owner()
        owner["properties"]["nested"] = {"properties": {"externalName": {}}}
        owner["properties"]["alias"] = {"$ref": "#/$defs/other"}
        owner["$defs"] = {"other": {"properties": {"externalName": {}}}}
        lint = Lint()
        naming_contracts.check_wire_property_name_case(lint, {"example.schema.json": owner})
        errors = [error for error in lint.errors if "externalName" in error]
        self.assertEqual(len(errors), 2, errors)

    def test_identifier_role_of_a_new_owned_field_is_not_exempt(self):
        owner = self.owner()
        owner["properties"]["signer"] = {"$ref": "./common-ids.schema.json#/$defs/did_core_id"}
        documents = {"example.schema.json": owner, "common-ids.schema.json": json.loads(
            (naming_contracts.SCHEMA_DIR / "common-ids.schema.json").read_text(encoding="utf-8"))}
        lint = Lint()
        with patch.object(naming_contracts, "_schema_documents", return_value=documents):
            naming_contracts.check_identifier_role_suffix_contracts(lint)
        self.assertTrue(any("role_stem=signer" in error and "lexical_owner=arkret_owned" in error
                            for error in lint.errors), lint.errors)

    def test_new_owned_object_collection_is_not_exempt(self):
        owner = self.owner()
        owner["properties"]["entry"] = {"type": "array", "items": {"type": "object"}}
        lint = Lint()
        with patch.object(naming_contracts, "_schema_documents", return_value={"example.schema.json": owner}):
            naming_contracts.check_collection_field_contracts(lint)
        self.assertTrue(any("/properties/entry" in error and "NC-COLLECTION-001" in error for error in lint.errors), lint.errors)

    def test_pure_external_owners_keep_their_exact_member_names(self):
        owner = self.owner()
        owner["properties"] = {"@context": {}, "verificationMethod": {}}
        owner["x-arkret-external-literal-object"]["external_properties"] = list(owner["properties"])
        self.assertEqual(self.errors(owner), [])

    def test_a_marker_without_direct_properties_is_stale_even_on_an_alias(self):
        owner = self.owner()
        owner["$defs"] = {"target": {"type": "string"}}
        owner["$ref"] = "#/$defs/target"
        del owner["properties"]
        lint = Lint()
        naming_contracts.check_wire_property_name_case(lint, {"example.schema.json": owner})
        self.assertTrue(any("stale annotation" in error for error in lint.errors), lint.errors)


if __name__ == "__main__":
    unittest.main()
