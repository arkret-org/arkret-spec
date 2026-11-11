"""Mutations cover the distinct HTTP and operation naming namespaces."""

import copy
import unittest

from .artifact_lint.http_naming import http_naming_errors, operation_id_errors, path_name_errors, transport_naming_errors, http_index_errors


def specimen():
    path = "/_arkret/self/strands/{strand_id}/messages"
    endpoint = "ak.self.strand.messages.read.list"
    operation = {
        "operationId": endpoint,
        "parameters": [
            {"in": "path", "name": "strand_id", "required": True},
            {"in": "query", "name": "include_payload"},
            {"in": "header", "name": "Arkret-Operation"},
        ],
        "responses": {"200": {"headers": {"X-Arkret-Request-Id": {}}}},
    }
    return {"paths": {path: {"get": operation}}}, [{"operation_id": endpoint + ".v1", "http": "GET " + path}]


class HttpNamingTests(unittest.TestCase):
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
        document["components"] = {"securitySchemes": {"dpopProof": {"in": "header", "name": "DPoP"}}}
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
