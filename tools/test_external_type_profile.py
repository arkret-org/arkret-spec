"""The single DID service extension cannot exempt unrelated type fields."""
import unittest
from .artifact_pipeline import classification_discipline_errors


class ExternalTypeProfileTest(unittest.TestCase):
    def specimen(self):
        owner = "/$defs/ServiceDidEndpoint/properties/type"
        schema = {"$defs": {"ServiceDidEndpoint": {"properties": {"type": {"const": "ArkretService"}}}}}
        row = {"schema_ref": "schemas/service-operation-dtos.schema.json", "json_pointer": owner,
               "external_standard": "W3C DID Core", "external_field_path": "Service type",
               "round_trip_requirement": "Preserve the registered profile", "dispatch_authority": "external_standard",
               "arkret_extensions_allowed": True,
               "extension_authority": "registry/contract-registry.json#/did_document_contract_registry/arkret_service_types/0/type"}
        return {row['schema_ref']: schema}, {"external_type_fields": [row], "closed_class_fields": [], "ordered_tier_fields": []}

    def test_registered_owner(self):
        schemas, registry = self.specimen()
        self.assertEqual(classification_discipline_errors(schemas, {}, registry), [])

    def test_missing_schema_fails_without_exception(self):
        schemas, registry = self.specimen()
        self.assertTrue(classification_discipline_errors({}, {}, registry))

    def test_expanded_value_fails(self):
        schemas, registry = self.specimen()
        schemas["schemas/service-operation-dtos.schema.json"]["$defs"]["ServiceDidEndpoint"]["properties"]["type"]["const"] = "PrivateDispatch"
        self.assertTrue(classification_discipline_errors(schemas, {}, registry))

    def test_claiming_no_extension_cannot_hide_profile_ownership(self):
        for value in ("ArkretService", "PrivateDispatch"):
            schemas, registry = self.specimen()
            row = registry["external_type_fields"][0]
            row["arkret_extensions_allowed"] = False
            del row["extension_authority"]
            schemas["schemas/service-operation-dtos.schema.json"]["$defs"]["ServiceDidEndpoint"]["properties"]["type"]["const"] = value
            self.assertTrue(classification_discipline_errors(schemas, {}, registry))

    def test_unrelated_owner_and_unresolved_authority_fail(self):
        for key, value in [("extension_authority", "invented"), ("external_standard", "Invented")]:
            schemas, registry = self.specimen()
            registry["external_type_fields"][0][key] = value
            self.assertTrue(classification_discipline_errors(schemas, {}, registry))


if __name__ == '__main__':
    unittest.main()
