"""Occurrence, schema-position and ownership-boundary tests for the inventory."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.naming_surface_inventory import Inventory, build_inventory, json_document


class NamingSurfaceInventoryTests(unittest.TestCase):
    def test_duplicate_json_members_cannot_silently_hide_a_declaration(self):
        with self.assertRaisesRegex(ValueError, 'duplicate JSON member'):
            json_document('{"properties":{"name":{},"name":{"const":"hidden"}}}')

    def test_invalid_token_values_are_retained_for_review(self):
        inventory = Inventory()
        inventory.data({"operation_id": "Bad Symbol With Spaces"}, "registry.json", "", "registry_metadata", "canonical")
        self.assertTrue(any(row["name"] == "Bad Symbol With Spaces"
                            and row["pointer"] == "/operation_id"
                            and row["category"] == "data.string_value_candidate"
                            for row in inventory.report()["occurrences"]))

    def rows(self, schema):
        inventory = Inventory()
        inventory.schema(schema, "one.schema.json", "", "json_schema", "schema_contract")
        return inventory.report()["occurrences"]

    def test_all_schema_positions_are_reached_once(self):
        declaration = {"type": "object", "properties": {"name": {"const": "named"}}}
        schema = {"$defs": {"inner": declaration}, "definitions": {"legacy": declaration},
                  "properties": {"nested": declaration}, "patternProperties": {"^x/": declaration},
                  "dependentSchemas": {"trigger": declaration}, "dependencies": {"legacy": declaration},
                  "items": declaration}
        for key in ("allOf", "anyOf", "oneOf", "prefixItems"):
            schema[key] = [declaration]
        for key in ("additionalProperties", "unevaluatedProperties", "propertyNames", "contains",
                    "not", "if", "then", "else", "additionalItems", "unevaluatedItems", "contentSchema"):
            schema[key] = declaration
        rows = self.rows(schema)
        names = [row for row in rows if row["category"] == "schema.property_name" and row["name"] == "name"]
        self.assertEqual(len(names), 22)
        self.assertEqual(len({row["pointer"] for row in names}), 22)
        self.assertIn("/patternProperties/^x~1/properties/name", {row["pointer"] for row in names})

    def test_examples_and_annotation_data_never_become_wire_properties(self):
        schema = {"properties": {"real": {"type": "string"}},
                  "examples": [{"properties": {"invented": {"enum": ["fake"]}}}],
                  "x-owner": {"properties": {"also_fake": {"const": "fake"}}}}
        rows = self.rows(schema)
        self.assertEqual([row["name"] for row in rows if row["category"] == "schema.property_name"], ["real"])
        self.assertEqual([row for row in rows if row["category"] == "schema.enum_or_const"], [])
        self.assertTrue(any(row["name"] == "invented" and row["category"] == "data.member" for row in rows))

    def test_external_property_owner_does_not_propagate_to_nested_schema(self):
        schema = {"x-arkret-external-literal-object": {"specification": "Example", "anchor": "https://example.org/spec#object"},
                  "properties": {"camelCase": {"properties": {"inner_name": {"type": "string"}}}}}
        rows = {row["name"]: row for row in self.rows(schema) if row["category"] == "schema.property_name"}
        self.assertEqual(rows["camelCase"]["ownership"], "external_literal_object")
        self.assertEqual(rows["inner_name"]["ownership"], "arkret_or_undeclared")

    def test_enum_and_const_keep_exact_owner_and_scalar_type(self):
        schema = {"$defs": {"values": {"enum": ["accepted", 1, None],
                  "x-arkret-value-ownership": {"class": "owned_symbol", "owner": "one#/$defs/values", "authority": "source"}},
                  "single": {"const": False}}}
        rows = [row for row in self.rows(schema) if row["category"] == "schema.enum_or_const"]
        self.assertEqual(len(rows), 4)
        self.assertEqual([row["literal"] for row in rows], [False, "accepted", 1, None])
        self.assertEqual(rows[0]["ownership"], "undeclared")
        self.assertEqual(rows[1]["declared_owner"], "one#/$defs/values")

    def test_openapi_schema_parameters_headers_operations_and_examples_are_separate(self):
        document = {"openapi": "3.1.0", "components": {"schemas": {"Thing": {"properties": {"wire": {"enum": ["yes"]}}}},
                    "headers": {"TraceHeader": {"schema": {"type": "string"}}}},
                    "paths": {"/things/{id}": {"get": {"operationId": "getThing", "parameters": [
                    {"in": place, "name": place + "_name", "schema": {"type": "string"}} for place in ("path", "query", "header", "cookie")],
                    "security": [{"DeviceProof": ["read"]}],
                    "responses": {"200": {"headers": {"ETag": {"schema": {"type": "string"}}},
                    "content": {"application/json": {"schema": {"properties": {"actual": {"const": True}}},
                    "example": {"schema": {"properties": {"fake": {}}}}}}}}}}}}
        inventory = Inventory()
        inventory.openapi(document, "api.yaml", "", "generated")
        rows = inventory.report()["occurrences"]
        self.assertEqual({r["name"] for r in rows if r["category"] == "schema.property_name"}, {"wire", "actual"})
        self.assertEqual(len([r for r in rows if r["category"] == "openapi.parameter_name"]), 4)
        self.assertEqual({r["name"] for r in rows if r["category"] == "openapi.header_name"}, {"ETag"})
        self.assertEqual({r["name"] for r in rows if r["category"] == "openapi.operation_id"}, {"getThing"})
        self.assertEqual({r["name"] for r in rows if r["category"] == "openapi.security_requirement"}, {"DeviceProof"})
        self.assertTrue(any(r["pointer"] == "/paths/~1things~1{id}" for r in rows))

    def test_dynamic_map_patterns_are_not_fixed_wire_fields(self):
        rows = self.rows({"patternProperties": {"^[a-z]+$": {"type": "string"}}, "additionalProperties": True})
        self.assertEqual(len([r for r in rows if r["category"] == "schema.dynamic_key_pattern"]), 1)
        self.assertEqual(len([r for r in rows if r["category"] == "schema.dynamic_key_slot"]), 1)
        self.assertFalse(any(r["category"] == "schema.property_name" for r in rows))

    def test_markdown_candidates_do_not_claim_canonical_or_wire_ownership(self):
        inventory = Inventory()
        inventory.markdown("`ThingView` and `did:web:external` with BareView\n```rust\nstruct LocalRow {}\nlet value: OtherType;\n```\n```json\n{\"camelCase\": 1}\n```\n", "doc.md")
        rows = inventory.report()["occurrences"]
        self.assertEqual(len([r for r in rows if r["category"] == "prose.identifier_candidate"]), 2)
        self.assertTrue(any(r["name"] == "LocalRow" and r["category"] == "prose.type_declaration_candidate" for r in rows))
        self.assertTrue(any(r["name"] == "BareView" and r["context"] == "prose_text" for r in rows))
        self.assertTrue(any(r["name"] == "OtherType" and r["category"] == "prose.pascal_candidate" for r in rows))
        self.assertEqual(sum(r['name'] == 'ThingView' for r in rows), 1)
        self.assertTrue(any(r["name"] == "camelCase" and r["context"] == "prose_json_instance_candidate" for r in rows))
        self.assertFalse(any(r["category"] == "schema.property_name" for r in rows))

    def test_markdown_inner_fences_and_info_strings_do_not_close_an_outer_block(self):
        inventory = Inventory()
        inventory.markdown('````text\n```json\n{"TypeName": 1}\n```\nTailType\n````\nAfterType\n', 'doc.md')
        rows = inventory.report()['occurrences']
        self.assertTrue(any(row['name'] == 'TailType' and row['context'] == 'code_fence_text' for row in rows))
        self.assertTrue(any(row['name'] == 'AfterType' and row['context'] == 'prose_text' for row in rows))
        self.assertFalse(any(row['context'] == 'prose_json_instance_candidate' for row in rows))

    def test_inventory_covers_canonical_derived_and_data_without_inventing_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = root / "spec/v1/artifacts"
            for folder in ("registry", "schemas", "fixtures", "openapi"):
                (artifacts / folder).mkdir(parents=True)
            (artifacts / "registry/registry-manifest.json").write_text(json.dumps({"registries": [
                {"file": "registry/one.json", "source_role": "canonical"},
                {"file": "registry/two.json", "source_role": "generated"}]}), encoding="utf-8")
            for name in ("one", "two"):
                (artifacts / f"registry/{name}.json").write_text('{"properties":{"not_wire":1}}', encoding="utf-8")
            (artifacts / 'opaque.bin').write_bytes(b'\x00\xff')
            (artifacts / "fixtures/example.json").write_text('{"enum":["fixture_only"]}', encoding="utf-8")
            (artifacts / "schemas/value.schema.json").write_text('{"properties":{"wire":{}}}', encoding="utf-8")
            first = build_inventory(root)
            self.assertEqual(first, build_inventory(root))
            self.assertEqual(first["statistics"]["file_count"], 6)
            self.assertTrue(any(row['name'] == 'opaque.bin' and row['category'] == 'artifact.filename'
                                for row in first['occurrences']))
            rows = first["occurrences"]
            self.assertEqual([r["name"] for r in rows if r["category"] == "schema.property_name"], ["wire"])
            for name, role in (("one", "canonical"), ("two", "generated")):
                self.assertTrue(any(r["file"].endswith(name + ".json") and r["source_role"] == role for r in rows))
            self.assertEqual(rows, sorted(rows, key=lambda r: (r["file"], r["pointer"], r["category"], r["name"], r["context"])))

    def test_mdx_contract_prose_is_included(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prose = root / "spec/v1/zh/sync"
            prose.mkdir(parents=True)
            (prose / "api.mdx").write_text("`CanonicalView`", encoding="utf-8")
            inventory = build_inventory(root)
            self.assertEqual(inventory["statistics"]["file_count"], 1)
            self.assertTrue(any(row["name"] == "CanonicalView" for row in inventory["occurrences"]))


if __name__ == "__main__":
    unittest.main()
