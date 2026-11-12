"""Independent regressions for declaration, reference and example boundaries."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from tools.artifact_lint.core import Lint
from tools.artifact_lint import naming_contracts
from tools.artifact_lint.semantic_naming import enum_errors


class SchemaPositionBoundariesTests(unittest.TestCase):
    @staticmethod
    def malformed_schema():
        return {"type": "object", "properties": {"camelCase": {"type": "string"}}}

    def openapi_errors(self, document):
        lint = Lint()
        with patch.object(naming_contracts, "load_yaml", return_value=document):
            naming_contracts.check_openapi_wire_property_name_case(lint)
        return lint.errors

    def schema_errors(self, document):
        lint = Lint()
        naming_contracts.check_wire_property_name_case(lint, {"example.schema.json": document})
        return lint.errors

    def test_reusable_media_schema_is_a_real_declaration(self):
        document = {"openapi": "3.2.0", "components": {
            "mediaTypes": {"Payload": {"schema": self.malformed_schema()}}}}
        errors = self.openapi_errors(document)
        self.assertTrue(any("/components/mediaTypes/Payload/schema/properties/camelCase" in error
                            for error in errors), errors)

    def test_media_reference_siblings_are_not_inline_schemas(self):
        document = {"components": {"mediaTypes": {"Payload": {"schema": {"type": "string"}}}},
                    "paths": {"/one": {"post": {"requestBody": {"content": {
                        "application/json": {"$ref": "#/components/mediaTypes/Payload",
                                             "schema": self.malformed_schema()}}}}}}}
        self.assertEqual(self.openapi_errors(document), [])

    def test_referenced_extension_target_is_checked_at_its_actual_pointer(self):
        document = {"components": {"schemas": {"Payload": {"$ref": "#/x-schema"}}},
                    "x-schema": self.malformed_schema()}
        errors = self.openapi_errors(document)
        self.assertTrue(any("/x-schema/properties/camelCase" in error for error in errors), errors)

    def test_reference_marker_does_not_exempt_the_referenced_owner(self):
        document = {"components": {"schemas": {"Payload": {
            "$ref": "#/x-schema", "x-arkret-external-literal-object": {
                "specification": "Example", "anchor": "https://example.org/spec#object"}}}},
                    "x-schema": self.malformed_schema()}
        self.assertTrue(any("/x-schema/properties/camelCase" in error
                            for error in self.openapi_errors(document)))

    def test_json_schema_examples_and_annotations_are_not_declarations(self):
        document = {"type": "object", "properties": {"actual_name": {"type": "string"}},
                    "examples": [self.malformed_schema()], "default": self.malformed_schema(),
                    "x-diagnostic": self.malformed_schema()}
        self.assertEqual(self.schema_errors(document), [])

    def test_json_schema_dynamic_key_pattern_is_not_a_fixed_property(self):
        document = {"type": "object", "patternProperties": {
            "^[A-Z].*$": {"type": "object", "properties": {"actual_name": {"type": "string"}}}}}
        self.assertEqual(self.schema_errors(document), [])
        document["patternProperties"]["^[A-Z].*$"] = self.malformed_schema()
        self.assertTrue(self.schema_errors(document))

    def test_external_marker_requires_an_actual_https_authority(self):
        for anchor in ("https://?q#part", "https://example.org/\x00#part", "https://example.org:bad/#part"):
            document = {**self.malformed_schema(), "x-arkret-external-literal-object": {
                "specification": "Example", "anchor": anchor}}
            with self.subTest(anchor=anchor):
                self.assertTrue(self.schema_errors(document))

    def test_external_enum_authority_obeys_the_same_url_contract(self):
        for anchor in ("https://?q#part", "https://example.org/\x00#part"):
            node = {"const": "ExternalName", "x-arkret-value-ownership": {
                "class": "external_literal", "authority": anchor,
                "owner": "one.schema.json#/$defs/word", "values": ["ExternalName"]}}
            with self.subTest(anchor=anchor):
                self.assertTrue(enum_errors(node, "one.schema.json#/$defs/word"))

    def test_schema_anchor_ignores_example_anchor_lookalikes(self):
        document = {"$defs": {"Payload": {"$anchor": "payload", "type": "string"}},
                    "$ref": "#payload", "examples": [{"$anchor": "payload"}]}
        self.assertEqual(self.schema_errors(document), [])

    def test_openapi_schema_anchor_resolves_from_schema_declarations(self):
        document = {"components": {"schemas": {
            "Payload": {"$anchor": "payload", "type": "string"},
            "Alias": {"$ref": "#payload"}}}}
        self.assertEqual(self.openapi_errors(document), [])

    def test_valid_international_https_authority_is_accepted(self):
        marker = {"specification": "Example", "anchor": "https://例子.测试/spec#object"}
        self.assertEqual(self.schema_errors({**self.malformed_schema(),
                         "x-arkret-external-literal-object": marker}), [])

    def test_missing_local_reference_is_a_readable_gate_failure(self):
        errors = self.openapi_errors({"components": {"schemas": {
            "Alias": {"$ref": "#/components/schemas/Missing"}}}})
        self.assertTrue(any("does not resolve" in error for error in errors), errors)

    def test_dynamic_schema_reference_activates_its_local_target(self):
        document = {"$dynamicRef": "#/x-schema", "x-schema": self.malformed_schema()}
        self.assertTrue(any("/x-schema/properties/camelCase" in error
                            for error in self.schema_errors(document)))

    def test_nested_resource_pointer_resolves_within_its_own_resource(self):
        document = {"$id": "https://example.org/root", "$defs": {"nested": {
            "$id": "https://example.org/nested", "$defs": {"payload": {"type": "string"}},
            "$ref": "#/$defs/payload"}}}
        self.assertEqual(self.schema_errors(document), [])

    def test_schema_reference_target_cannot_be_an_arbitrary_scalar(self):
        errors = self.openapi_errors({"components": {"schemas": {
            "Alias": {"$ref": "#/x-not-schema"}}}, "x-not-schema": "text"})
        self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
