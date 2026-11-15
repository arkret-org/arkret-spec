"""Mutations cover the distinct HTTP and operation naming namespaces."""

import copy
import json
import unittest
from urllib.parse import quote, unquote

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from .artifact_lint.http_naming import http_naming_errors, operation_id_errors, path_name_errors, transport_naming_errors, http_index_errors, SCALAR_PARAMETER_REFS
from .artifact_lint.core import ARTIFACTS, Lint, load_json, load_yaml


def specimen():
    path = "/_arkret/self/strands/{strand_id}/messages"
    endpoint = "ak.self.strand.messages.read.list"
    operation = {
        "operationId": endpoint,
        "parameters": [
            {"in": "path", "name": "strand_id", "required": True,
             "schema": {"$ref": "../schemas/strand.schema.json#/properties/id"}},
            {"in": "query", "name": "include_payload"},
            {"in": "header", "name": "Arkret-Operation"},
        ],
        "responses": {"200": {"headers": {"X-Arkret-Request-Id": {}}}},
    }
    return {"paths": {path: {"get": operation}}}, [{"operation_id": endpoint + ".v1", "http": "GET " + path}]


class HttpNamingTests(unittest.TestCase):
    def test_registered_scalar_carrier_targets_resolve_to_real_schemas(self):
        for name, reference in SCALAR_PARAMETER_REFS.items():
            with self.subTest(name=name, reference=reference):
                filename, pointer = reference.split("#", 1)
                node = json.loads((ARTIFACTS / "schemas" / filename).read_text(encoding="utf-8"))
                for token in pointer.split("/")[1:]:
                    token = token.replace("~1", "/").replace("~0", "~")
                    node = node[int(token)] if isinstance(node, list) else node[token]
                self.assertIsInstance(node, (dict, bool))

    def test_every_component_reference_namespace_uses_canonical_pascal_case(self):
        for group in ("schemas", "requestBodies", "parameters", "responses", "headers", "examples",
                      "securitySchemes", "links", "callbacks", "pathItems", "mediaTypes"):
            document, rows = specimen()
            document["components"] = {group: {"ValidName": {}}}
            self.assertEqual(http_naming_errors(document, rows), [], group)
            for name in ("lowerCamel", "snake_case", "HTTPProof", "Bad_Name"):
                document["components"] = {group: {name: {}}}
                self.assertTrue(http_naming_errors(document, rows), (group, name))

    def test_metadata_keys_are_checked_at_oas_objects_without_scanning_instances(self):
        document, rows = specimen()
        document["x-arkret-policy"] = {"valid_name": True}
        document["components"] = {"examples": {"Sample": {"value": {
            "x-arkret-policy": {"lowerCamel": True}}}}}
        document["components"]["schemas"] = {"SampleValue": {"type": "object", "default": {
            "x-arkret-policy": {"lowerCamel": True}}}}
        operation = next(iter(document["paths"].values()))["get"]
        operation["x-arkret-auth"] = {"holder_proof": True}
        self.assertEqual(http_naming_errors(document, rows), [])
        operation["x-arkret-auth"]["service_signature"] = {"delivery_authentication_record": {"requestBodyField": False}}
        self.assertTrue(any("requestBodyField" in error for error in http_naming_errors(document, rows)))
        operation["x-arkret-auth"]["service_signature"] = [{"requestBodyField": False}]
        self.assertTrue(http_naming_errors(document, rows))
        del operation["x-arkret-auth"]["service_signature"]
        operation["x-arkret-value-ownership"] = {"class": "external_literal", "values": [{"externalCamel": True}]}
        self.assertEqual(http_naming_errors(document, rows), [])
        document["x-arkret-policy"]["lowerCamel"] = True
        self.assertTrue(any("fixed extension metadata keys" in error for error in http_naming_errors(document, rows)))
        del document["x-arkret-policy"]["lowerCamel"]
        operation["x-arkret-auth"]["holderProof"] = True
        self.assertTrue(http_naming_errors(document, rows))
        del operation["x-arkret-auth"]["holderProof"]
        operation["callbacks"] = {"Callback": {"{$request.body#/url}": {"post": {
            "x-arkret-auth": {"holderProof": True}}}}}
        self.assertTrue(http_naming_errors(document, rows))

    def test_scalar_identifier_names_cannot_use_a_bare_or_wrong_terminal(self):
        for schema in ({"type": "string"}, {"type": "string", "pattern": "^.*$"},
                       {"$ref": "../schemas/common-ids.schema.json#/$defs/realm_id"}):
            document, rows = specimen()
            next(iter(document["paths"].values()))["get"]["parameters"][0]["schema"] = schema
            self.assertTrue(http_naming_errors(document, rows), schema)

    def test_real_http_binding_names_and_identity_carriers_are_closed(self):
        lint = Lint()
        document = load_yaml(lint, ARTIFACTS / "openapi/arkret-service-api.openapi.yaml")
        registry = load_json(lint, ARTIFACTS / "registry/operation-registry.json")
        self.assertEqual(lint.errors, [])
        self.assertEqual(http_naming_errors(document, registry["operations"]), [])
        for path, name, carrier in (
            ("/_arkret/self/authz/invites", "subject_account_id", "account_id"),
            ("/_arkret/self/authz/effective-grants", "subject_actor_id", "actor_id"),
        ):
            parameters = document["paths"][path]["get"]["parameters"]
            selected = [value for value in parameters if value.get("in") == "query" and value.get("name") == name]
            self.assertEqual(len(selected), 1)
            self.assertFalse(selected[0]["required"])
            self.assertEqual(selected[0]["content"]["application/json"]["schema"],
                             {"$ref": "../schemas/common-ids.schema.json#/$defs/" + carrier})
            self.assertFalse({"subject", "subject_station_id"} & {value.get("name") for value in parameters})

    def test_compound_query_identity_name_cannot_hide_a_bare_or_different_carrier(self):
        for name, carrier in (("subject_account_id", "account_id"), ("subject_actor_id", "actor_id"),
                              ("source_realm_actor_id", "realm_actor_id")):
            document, rows = specimen()
            parameter = {"in": "query", "name": name, "content": {"application/json": {
                "schema": {"$ref": "../schemas/common-ids.schema.json#/$defs/" + carrier}}}}
            next(iter(document["paths"].values()))["get"]["parameters"][1] = parameter
            self.assertEqual(http_naming_errors(document, rows), [])
            for changed in (
                {"in": "query", "name": name, "schema": {"type": "string"}},
                {**parameter, "schema": {"type": "string"}},
                {"in": "query", "name": name, "content": {"application/json": {"schema": {"type": "object"}}}},
                {"in": "query", "name": name, "content": {"application/json": {"schema": {
                    "$ref": "../schemas/common-ids.schema.json#/$defs/did_core_id"}}}},
            ):
                invalid = copy.deepcopy(document)
                next(iter(invalid["paths"].values()))["get"]["parameters"][1] = changed
                self.assertTrue(http_naming_errors(invalid, rows), (name, changed))

    def test_compound_query_schema_local_references_and_flat_deep_object(self):
        document, rows = specimen()
        parameter = {"in": "query", "name": "realm_actor_id", "style": "deepObject", "explode": True,
                     "schema": {"$ref": "#/components/schemas/RealmActorId"}}
        document["components"] = {"schemas": {"RealmActorId": {
            "$ref": "../schemas/common-ids.schema.json#/$defs/realm_actor_id"}}}
        next(iter(document["paths"].values()))["get"]["parameters"][1] = parameter
        self.assertEqual(http_naming_errors(document, rows), [])
        for changed in ({**parameter, "explode": False}, {**parameter, "name": "actor_id"},
                        {**parameter, "schema": {"$ref": "#/components/schemas/Missing"}}):
            invalid = copy.deepcopy(document)
            next(iter(invalid["paths"].values()))["get"]["parameters"][1] = changed
            self.assertTrue(http_naming_errors(invalid, rows), changed)
        document["components"]["schemas"]["RealmActorId"] = {"$ref": "#/components/schemas/RealmActorId"}
        self.assertTrue(http_naming_errors(document, rows))

    def test_repeated_compound_identity_values_require_decoded_content_schemas(self):
        for name, carrier in (("account_ids", "account_id"), ("source_actor_ids", "actor_id"),
                              ("target_realm_actor_ids", "realm_actor_id")):
            document, rows = specimen()
            item = {"type": "string", "contentMediaType": "application/json", "contentSchema": {
                "$ref": "../schemas/common-ids.schema.json#/$defs/" + carrier}}
            parameter = {"in": "query", "name": name, "style": "form", "explode": True,
                         "schema": {"type": "array", "items": item}}
            next(iter(document["paths"].values()))["get"]["parameters"][1] = parameter
            self.assertEqual(http_naming_errors(document, rows), [])
            invalid_items = [
                {"type": "string"},
                {"type": "string", "contentMediaType": "application/json"},
                {key: value for key, value in item.items() if key != "contentMediaType"},
                {**item, "contentMediaType": "text/plain"},
                {**item, "contentEncoding": "base64"},
                {**item, "type": "object"},
                {**item, "contentSchema": {"type": "object"}},
                {**item, "contentSchema": {"$ref": "../schemas/common-ids.schema.json#/$defs/did_core_id"}},
                {**item, "contentSchema": {"$ref": "../schemas/common-ids.schema.json#/$defs/" + (
                    "account_id" if carrier != "account_id" else "actor_id")}},
            ]
            for changed_item in invalid_items:
                invalid = copy.deepcopy(document)
                selected = next(iter(invalid["paths"].values()))["get"]["parameters"][1]
                selected["schema"]["items"] = changed_item
                with self.subTest(name=name, item=changed_item):
                    self.assertTrue(http_naming_errors(invalid, rows))
            for changed in (
                {**parameter, "style": "deepObject"}, {**parameter, "style": "simple"},
                {**parameter, "explode": False}, {**parameter, "in": "path"},
                {**parameter, "content": {"application/json": {"schema": parameter["schema"]}}},
                {**parameter, "schema": {"type": "string"}},
            ):
                invalid = copy.deepcopy(document)
                next(iter(invalid["paths"].values()))["get"]["parameters"][1] = changed
                errors = http_naming_errors(invalid, rows)
                with self.subTest(name=name, parameter=changed):
                    self.assertTrue(any("compound identity collection" in error for error in errors), errors)

    def test_repeated_identity_content_schema_follows_local_aliases(self):
        document, rows = specimen()
        document["components"] = {"schemas": {
            "ActorId": {"$ref": "../schemas/common-ids.schema.json#/$defs/actor_id"},
            "EncodedActor": {"type": "string", "contentMediaType": "application/json",
                             "contentSchema": {"$ref": "#/components/schemas/ActorId"}},
            "EncodedActors": {"type": "array", "items": {"$ref": "#/components/schemas/EncodedActor"}},
        }}
        parameter = {"in": "query", "name": "actor_ids", "style": "form", "explode": True,
                     "schema": {"$ref": "#/components/schemas/EncodedActors"}}
        next(iter(document["paths"].values()))["get"]["parameters"][1] = parameter
        self.assertEqual(http_naming_errors(document, rows), [])
        for reference in ("#/components/schemas/Missing", "#/components/schemas/ActorId"):
            invalid = copy.deepcopy(document)
            invalid["components"]["schemas"]["ActorId"] = {"$ref": reference}
            self.assertTrue(http_naming_errors(invalid, rows), reference)

    def test_repeated_identity_aliases_reject_shape_and_content_siblings_at_every_layer(self):
        document, rows = specimen()
        annotation = {"description": "The same complete decoded identity.", "title": "Identity alias"}
        document["components"] = {"schemas": {
            "ActorId": {"$ref": "../schemas/common-ids.schema.json#/$defs/actor_id", **annotation},
            "ActorIdAlias": {"$ref": "#/components/schemas/ActorId", **annotation},
            "EncodedActor": {"type": "string", "contentMediaType": "application/json",
                             "contentSchema": {"$ref": "#/components/schemas/ActorIdAlias", **annotation}},
            "EncodedActorAlias": {"$ref": "#/components/schemas/EncodedActor", **annotation},
            "EncodedActors": {"type": "array", "items": {
                "$ref": "#/components/schemas/EncodedActorAlias", **annotation}},
            "EncodedActorsAlias": {"$ref": "#/components/schemas/EncodedActors", **annotation},
        }}
        parameter = {"in": "query", "name": "actor_ids", "style": "form", "explode": True,
                     "schema": {"$ref": "#/components/schemas/EncodedActorsAlias", **annotation}}
        operation = next(iter(document["paths"].values()))["get"]
        operation["parameters"][1] = parameter
        self.assertEqual(http_naming_errors(document, rows), [])
        path = next(iter(document["paths"]))
        cases = (
            (("paths", path, "get", "parameters", 1, "schema"), {"type": "string"}),
            (("components", "schemas", "EncodedActorsAlias"), {"minItems": 1}),
            (("components", "schemas", "EncodedActors", "items"), {"contentEncoding": "base64"}),
            (("components", "schemas", "EncodedActorAlias"), {"contentMediaType": "text/plain"}),
            (("components", "schemas", "EncodedActor", "contentSchema"), {"type": "string"}),
            (("components", "schemas", "ActorIdAlias"), {"allOf": [{"type": "string"}]}),
            (("components", "schemas", "ActorId"), {"type": "string"}),
        )
        for parts, sibling in cases:
            invalid = copy.deepcopy(document)
            target = invalid
            for part in parts:
                target = target[part]
            target.update(sibling)
            errors = http_naming_errors(invalid, rows)
            with self.subTest(path=parts, sibling=sibling):
                self.assertTrue(any("transparent aliases" in error for error in errors), errors)

    def test_single_compound_identity_canonical_references_allow_only_annotations(self):
        annotations = {"title": "Identity alias", "description": "One complete identity.", "$comment": "Alias.",
                       "examples": [], "default": {}, "deprecated": False, "readOnly": True, "writeOnly": False}
        for carrier in ("actor_id", "account_id", "realm_actor_id"):
            for local in (False, True):
                document, rows = specimen()
                reference = {"$ref": "../schemas/common-ids.schema.json#/$defs/" + carrier, **annotations}
                if local:
                    document["components"] = {"schemas": {"Identity": reference}}
                    schema = {"$ref": "#/components/schemas/Identity", **annotations}
                else:
                    schema = reference
                parameter = {"in": "query", "name": carrier, "content": {"application/json": {"schema": schema}}}
                next(iter(document["paths"].values()))["get"]["parameters"][1] = parameter
                self.assertEqual(http_naming_errors(document, rows), [])
                for sibling in ({"type": "string"}, {"properties": {"unknown_member": {}}},
                                {"contentEncoding": "base64"}, {"contentSchema": {"type": "string"}}):
                    invalid = copy.deepcopy(document)
                    target = (invalid["components"]["schemas"]["Identity"] if local else
                              next(iter(invalid["paths"].values()))["get"]["parameters"][1]["content"]["application/json"]["schema"])
                    target.update(sibling)
                    errors = http_naming_errors(invalid, rows)
                    with self.subTest(carrier=carrier, local=local, sibling=sibling):
                        self.assertTrue(any("transparent aliases" in error for error in errors), errors)

    def test_real_repeated_actor_ids_decode_before_canonical_identity_validation(self):
        """Content annotations identify the decoded schema; receivers perform validation."""
        lint = Lint()
        document = load_yaml(lint, ARTIFACTS / "openapi/arkret-service-api.openapi.yaml")
        parameters = document["paths"]["/_arkret/self/committed-events/subscribe"]["get"]["parameters"]
        parameter = next(value for value in parameters if value.get("name") == "actor_ids")
        items = parameter["schema"]["items"]
        filename, pointer = items["contentSchema"]["$ref"].split("#", 1)
        canonical = json.loads((ARTIFACTS / "openapi" / filename).read_text(encoding="utf-8"))
        registry = Registry().with_resource(canonical["$id"], Resource.from_contents(canonical))
        validator = Draft202012Validator({"$ref": canonical["$id"] + "#" + pointer}, registry=registry)
        account = {"kind": "account", "account_id": {
            "principal_id": "ak:did_core:web:alice.example", "station_id": "ak:did_core:web:station.example"}}
        missing_station = {"kind": "account", "account_id": {"principal_id": "ak:did_core:web:alice.example"}}
        for value, valid in (
            (account, True), ({"kind": "service", "service_id": "ak:did_core:web:service.example"}, True),
            (missing_station, False), ({}, False), ("did:web:alice.example", False),
            ({**account, "unknown_member": True}, False),
        ):
            jcs = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            encoded = quote(jcs, safe="")
            decoded = json.loads(unquote(encoded, encoding="utf-8", errors="strict"))
            with self.subTest(value=value):
                self.assertEqual(validator.is_valid(decoded), valid)
        with self.assertRaises(json.JSONDecodeError):
            json.loads(unquote(quote("did:web:alice.example", safe="")))
        self.assertTrue(Draft202012Validator(items).is_valid(json.dumps(missing_station)))

    def test_canonical_public_dto_mirrors_cannot_create_type_name_aliases(self):
        document, rows = specimen()
        reference = {"$ref": "../schemas/service-operation-dtos.schema.json#/$defs/CommittedEventView"}
        document["components"] = {"schemas": {"CommittedEventView": reference}}
        self.assertEqual(http_naming_errors(document, rows), [])
        document["components"]["schemas"] = {"EventView": reference}
        errors = http_naming_errors(document, rows)
        self.assertTrue(any("canonical public DTO mirror" in error for error in errors), errors)

    def test_prose_http_index_rejects_stale_missing_extra_and_duplicate_rows(self):
        row = {"operation_id": "ak.self.account_data.read.list.v1", "http": "GET /_arkret/self/account-data"}
        row_text = "| `ak.self.account_data.read.list.v1` | `GET /_arkret/self/account-data` | - | - | refs |"
        def table(rows):
            return "<!-- BEGIN GENERATED OPERATION FIELD TABLE -->\n" + rows + "\n<!-- END GENERATED OPERATION FIELD TABLE -->"
        text = table(row_text)
        self.assertEqual(http_index_errors(text, [row]), [])
        for invalid in ("", table(""), text.replace("/account-data", "/account_data"), table(row_text + "\n" + row_text)):
            self.assertTrue(http_index_errors(invalid, [row]))
        self.assertTrue(http_index_errors(text, []))
        self.assertEqual(http_index_errors(row_text + "\n" + text, [row]), [])
        for extra in ("  " + row_text, row_text.replace("ak.self.account_data.read.list.v1", "not_registered"),
                      row_text.replace("`GET /_arkret/self/account-data`", "GET /_arkret/self/account-data"),
                      "|" + row_text + "|", "invalid row"):
            self.assertTrue(http_index_errors(table(row_text + "\n" + extra), [row]))

    def test_distinct_namespaces_and_exact_http_binding(self):
        document, rows = specimen()
        self.assertEqual(http_naming_errors(document, rows), [])
        document["external_examples"] = {"url": "https://identity.example/.well-known/openid-configuration", "verificationMethod": "external"}
        document["components"] = {"securitySchemes": {"DpopProof": {"in": "header", "name": "DPoP"}}}
        self.assertEqual(http_naming_errors(document, rows), [])
        rows[0]["http"] = "POST /_arkret/self/strands/{strand_id}/messages"
        self.assertTrue(http_naming_errors(document, rows))

    def test_operation_segment_mutations_cannot_hide_after_prefix(self):
        for value in (
            "ak.self._strands.read.list.v1", "ak.self.123.read.list.v1",
            "ak.self.strands_.read.list.v1", "ak.self.strands..read.list.v1",
            "ak.self.strands.read..v1", "ak.self.strands.read.list.v2",
            "ak.self.strands.compute.list.v1", "ak.self.strands.command.post.v1",
        ):
            self.assertTrue(operation_id_errors(value), value)
        for value in ("ak.server.read.describe.v1", "ak.self.strand.messages.read.list.v1", "ak.self.strand.resource.get.v1"):
            self.assertEqual(operation_id_errors(value), [], value)

    def test_paths_do_not_inherit_symbol_separators_or_external_url_syntax(self):
        for value in (
            "/_arkret/self/account_data", "/_arkret/self/v1/strands", "/_arkret/self/Strands",
            "/_arkret/self/strands/", "/_arkret/self//strands", "/_arkret/self/strands?limit=1",
            "/_arkret/self/strands#fragment", "/_arkret/self/%73trands", "/_arkret/self/{strandId}",
            "/_arkret/self/resources:ensure/next", "/_matrix/client/v3/account_data",
        ):
            self.assertTrue(path_name_errors(value), value)
        for value in ("/_arkret/describe", "/_arkret/self/account-data/{account_data_key}", "/_arkret/root/identity/service-registrations:ensure"):
            self.assertEqual(path_name_errors(value), [], value)

    def test_root_metadata_is_an_exact_exception(self):
        document = {"paths": {"/_arkret/describe": {"get": {"operationId": "ak.server.read.describe"}}}}
        rows = [{"operation_id": "ak.server.read.describe.v1", "http": "GET /_arkret/describe"}]
        self.assertEqual(http_naming_errors(document, rows), [])
        rows[0]["http"] = "GET /_arkret/self/describe"
        self.assertTrue(http_naming_errors(document, rows))

    def test_terminal_action_is_not_an_operation_string_derivation(self):
        path = "/_arkret/edge/push/registrations:apply"
        endpoint = "ak.edge.push.command.apply_registration"
        document = {"paths": {path: {"post": {"operationId": endpoint}}}}
        rows = [{"operation_id": endpoint + ".v1", "http": "POST " + path}]
        self.assertEqual(http_naming_errors(document, rows), [])
        document["paths"][path]["get"] = document["paths"][path].pop("post")
        rows[0]["http"] = "GET " + path
        self.assertTrue(http_naming_errors(document, rows))

    def test_path_parameters_are_required_and_match_the_template(self):
        for field, value in (("name", "strandId"), ("name", "event_id"), ("required", False)):
            document, rows = specimen()
            operation = next(iter(document["paths"].values()))["get"]
            operation["parameters"][0][field] = value
            self.assertTrue(http_naming_errors(document, rows), (field, value))

    def test_query_names_and_endpoint_versions_are_not_implicit_aliases(self):
        for mutate in ("query", "version", "missing", "duplicate"):
            document, rows = specimen()
            operation = next(iter(document["paths"].values()))["get"]
            if mutate == "query":
                operation["parameters"][1]["name"] = "includePayload"
            elif mutate == "version":
                operation["operationId"] += ".v1"
            elif mutate == "missing":
                rows = []
            else:
                rows += copy.deepcopy(rows)
            self.assertTrue(http_naming_errors(document, rows), mutate)

    def test_query_collection_names_do_not_depend_on_comma_or_array_encoding(self):
        for name in ("link_kind_allow", "link_kind_deny", "link_kind_allowlist", "allow_link_kinds", "permitted_link_kinds"):
            for schema in ({"type": "string"}, {"type": "array", "items": {"type": "string"}}):
                document, rows = specimen()
                operation = next(iter(document["paths"].values()))["get"]
                operation["parameters"][1] = {"in": "query", "name": name, "schema": schema}
                self.assertTrue(http_naming_errors(document, rows), (name, schema))
        for name in ("allowed_link_kinds", "denied_link_kinds"):
            document, rows = specimen()
            next(iter(document["paths"].values()))["get"]["parameters"][1]["name"] = name
            self.assertEqual(http_naming_errors(document, rows), [])

    def test_header_identity_is_case_insensitive_but_not_json_snake_case(self):
        document, rows = specimen()
        operation = next(iter(document["paths"].values()))["get"]
        for name in ("DPoP", "MIMI-Room-URI", "Source-Service-ID"):
            operation["parameters"].append({"in": "header", "name": name})
        self.assertEqual(http_naming_errors(document, rows), [])
        operation["parameters"].append({"in": "header", "name": "arkret-operation"})
        self.assertTrue(http_naming_errors(document, rows))

    def test_response_and_security_scheme_headers_are_included(self):
        document, rows = specimen()
        operation = next(iter(document["paths"].values()))["get"]
        operation["responses"]["200"]["headers"]["x-arkret-request-id"] = {}
        self.assertTrue(http_naming_errors(document, rows))
        document, rows = specimen()
        document["components"] = {"securitySchemes": {"proof": {"in": "header", "name": "Bad Header"}}}
        self.assertTrue(http_naming_errors(document, rows))

    def test_references_cannot_hide_unchecked_parameter_names(self):
        document, rows = specimen()
        operation = next(iter(document["paths"].values()))["get"]
        document["components"] = {"parameters": {"Selector": operation["parameters"][1]}}
        operation["parameters"][1] = {"$ref": "#/components/parameters/Selector"}
        self.assertEqual(http_naming_errors(document, rows), [])
        document["components"]["parameters"]["Selector"]["name"] = "includePayload"
        self.assertTrue(http_naming_errors(document, rows))
        document["components"]["parameters"]["Selector"] = {"$ref": "#/components/parameters/Selector"}
        self.assertTrue(http_naming_errors(document, rows))

    def test_unknown_method_objects_cannot_bypass_the_complete_walker(self):
        for field in ("GET", "fetch", "additionalOperations"):
            document, rows = specimen()
            item = next(iter(document["paths"].values()))
            item[field] = {"CUSTOM": copy.deepcopy(item["get"])} if field == "additionalOperations" else copy.deepcopy(item["get"])
            self.assertTrue(http_naming_errors(document, rows), field)

    def test_path_item_reference_siblings_are_real_operations(self):
        document, rows = specimen()
        path = next(iter(document["paths"]))
        original = document["paths"][path]
        document["components"] = {"pathItems": {"Base": copy.deepcopy(original)}}
        added = copy.deepcopy(original["get"])
        added["operationId"] = "ak.self.strand.messages.command.submit"
        document["paths"][path] = {"$ref": "#/components/pathItems/Base", "post": added}
        self.assertTrue(http_naming_errors(document, rows))
        rows.append({"operation_id": added["operationId"] + ".v1", "http": "POST " + path})
        self.assertEqual(http_naming_errors(document, rows), [])
        added["parameters"][1]["name"] = "includePayload"
        self.assertTrue(http_naming_errors(document, rows))

    def test_path_item_reference_overlaps_are_undefined_and_rejected(self):
        document, rows = specimen()
        path = next(iter(document["paths"]))
        original = copy.deepcopy(document["paths"][path])
        document["components"] = {"pathItems": {"Base": original}}
        document["paths"][path] = {"$ref": "#/components/pathItems/Base", **copy.deepcopy(original)}
        errors = http_naming_errors(document, rows)
        self.assertTrue(any("undefined duplicate sibling" in error for error in errors))

    def test_reference_object_siblings_do_not_override_the_referenced_parameter(self):
        document, rows = specimen()
        operation = next(iter(document["paths"].values()))["get"]
        document["components"] = {"parameters": {"Selector": copy.deepcopy(operation["parameters"][1])}}
        operation["parameters"][1] = {
            "$ref": "#/components/parameters/Selector", "summary": "External Reference Object",
            "description": "Descriptions can annotate the reference", "name": "badName",
        }
        self.assertEqual(http_naming_errors(document, rows), [])

    def test_malformed_short_endpoint_on_action_path_returns_diagnostics(self):
        path = "/_arkret/self/resources:send"
        document = {"paths": {path: {"post": {"operationId": "x"}}}}
        self.assertTrue(http_naming_errors(document, [{"operation_id": "x.v1", "http": "POST " + path}]))


class TransportNamingTests(unittest.TestCase):
    def specimen(self):
        operation = "ak.self.management_review.command.request.v1"
        document = {
            "grpc": {"services": {"SelfManagement": {"ManagementReviewCommandRequest": operation}}},
            "mq": {"topics": {"self.management_review.command.request": operation}},
            "frame_schemas": {"sse": {"event_types": ["sync.event", "sync.realm_state_snapshot"]}},
            "libp2p": {"suggested_protocols": ["/arkret/sync/1.0.0", "/arkret/blob/1.0.0"]},
        }
        rows = [{"operation_id": operation, "grpc": "SelfManagement/ManagementReviewCommandRequest", "mq": "self.management_review.command.request"}]
        return document, rows

    def test_each_binding_keeps_its_own_registered_namespace(self):
        document, rows = self.specimen()
        self.assertEqual(transport_naming_errors(document, rows), [])

    def test_grpc_names_reject_underscores_and_unfolded_acronyms(self):
        for field, name in (("service", "SelfMLS"), ("service", "Self_Management"), ("method", "Management_ReviewCommandRequest"), ("method", "GetDID")):
            document, rows = self.specimen()
            if field == "service":
                document["grpc"]["services"][name] = document["grpc"]["services"].pop("SelfManagement")
                rows[0]["grpc"] = name + "/ManagementReviewCommandRequest"
            else:
                methods = document["grpc"]["services"]["SelfManagement"]
                methods[name] = methods.pop("ManagementReviewCommandRequest")
                rows[0]["grpc"] = "SelfManagement/" + name
            self.assertTrue(transport_naming_errors(document, rows), (field, name))

    def test_mq_and_sse_segments_are_all_checked(self):
        for value in ("self._private", "self.123", "self.management-review", "self.review_", "self..review"):
            document, rows = self.specimen()
            operation = rows[0]["operation_id"]
            rows[0]["mq"] = value
            document["mq"]["topics"] = {value: operation}
            self.assertTrue(transport_naming_errors(document, rows), value)
            document, rows = self.specimen()
            document["frame_schemas"]["sse"]["event_types"] = [value]
            self.assertTrue(transport_naming_errors(document, rows), value)

    def test_libp2p_versioned_protocol_is_not_an_http_route(self):
        document, rows = self.specimen()
        self.assertEqual(transport_naming_errors(document, rows), [])
        for value in ("/_arkret/self/sync", "/arkret/sync", "/arkret/Sync/1.0.0", "/arkret/sync/01.0.0"):
            document["libp2p"]["suggested_protocols"] = [value]
            self.assertTrue(transport_naming_errors(document, rows), value)

    def test_missing_duplicate_or_reassigned_bindings_fail_closed(self):
        for mutation in ("missing", "mismatch", "unknown", "duplicate_event", "duplicate_protocol"):
            document, rows = self.specimen()
            if mutation == "missing":
                document["grpc"]["services"] = {}
            elif mutation == "mismatch":
                rows[0]["mq"] = "self.management_review.command.decide"
            elif mutation == "unknown":
                document["grpc"]["services"]["SelfManagement"]["ManagementReviewCommandRequest"] = "ak.self.unknown.read.get.v1"
            elif mutation == "duplicate_event":
                document["frame_schemas"]["sse"]["event_types"] = ["sync.event", "sync.event"]
            else:
                document["libp2p"]["suggested_protocols"] = ["/arkret/sync/1.0.0", "/arkret/sync/1.0.0"]
            self.assertTrue(transport_naming_errors(document, rows), mutation)


if __name__ == "__main__":
    unittest.main()
