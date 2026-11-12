"""Mutation checks for actual OpenAPI schema positions and exact ownership."""
from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from tools.artifact_lint.core import Lint
from tools.artifact_lint import naming_contracts


class OpenApiPropertyCaseTests(unittest.TestCase):
    def errors(self, document):
        lint = Lint()
        with patch.object(naming_contracts, 'load_yaml', return_value=document):
            naming_contracts.check_openapi_wire_property_name_case(lint)
        return lint.errors

    def bad(self):
        return {'type': 'object', 'properties': {'camelCase': {'type': 'string'}}}

    def media(self):
        return {'content': {'application/json': {'schema': self.bad()}}}

    def test_real_document_passes_and_schema_positions_are_unique(self):
        lint = Lint()
        naming_contracts.check_openapi_wire_property_name_case(lint)
        self.assertEqual(lint.errors, [])
        document = naming_contracts.load_yaml(lint, naming_contracts.ARTIFACTS / 'openapi/arkret-service-api.openapi.yaml')
        positions = [pointer for pointer, _ in naming_contracts.openapi_schema_positions(document)]
        self.assertTrue(positions)
        self.assertEqual(len(positions), len(set(positions)))

    def test_component_and_inline_binding_slots_are_reached(self):
        cases = [
            {'components': {'schemas': {'Payload': self.bad()}}},
            {'components': {'parameters': {'Input': {'name': 'q', 'in': 'query', 'schema': self.bad()}}}},
            {'components': {'headers': {'x-custom-header': {'schema': self.bad()}}}},
            {'components': {'requestBodies': {'Input': self.media()}}},
            {'components': {'responses': {'Output': self.media()}}},
            {'components': {'pathItems': {'StoredPath': {'post': {'requestBody': self.media()}}}}},
            {'paths': {'/one': {'parameters': [{'in': 'query', 'name': 'q', 'schema': self.bad()}]}}},
            {'paths': {'/one': {'post': {'parameters': [{'name': 'q', 'in': 'query', **self.media()}]}}}},
            {'paths': {'/one': {'post': {'requestBody': self.media()}}}},
            {'paths': {'/one': {'post': {'responses': {'200': self.media()}}}}},
            {'paths': {'/one': {'get': {'responses': {'200': {'headers': {'x-custom-header': {'schema': self.bad()}}}}}}}},
            {'webhooks': {'x-custom-hook': {'post': {'requestBody': self.media()}}}},
            {'paths': {'/one': {'additionalOperations': {'CUSTOM': {'requestBody': self.media()}}}}},
            {'components': {'callbacks': {'Callback': {'{$request.body#/url}': {'post': {'requestBody': self.media()}}}}}},
            {'paths': {'/one': {'post': {'callbacks': {'Callback': {'{$request.body#/url}': {'post': {'requestBody': self.media()}}}}}}}},
            {'components': {'requestBodies': {'Input': {'content': {'application/json': {'encoding': {'field': {'headers': {'X-Header': {'schema': self.bad()}}}}}}}}}},
            {'components': {'requestBodies': {'Input': {'content': {'application/json-seq': {'itemSchema': self.bad()}}}}}},
        ]
        for index, document in enumerate(cases):
            with self.subTest(index=index):
                errors = self.errors(document)
                self.assertEqual(len(errors), 1, errors)
                self.assertIn('camelCase', errors[0])

    def test_every_schema_combinator_and_definition_position_is_reached(self):
        containers = [{key: [self.bad()]} for key in ('allOf', 'anyOf', 'oneOf', 'prefixItems')]
        containers += [{key: self.bad()} for key in ('not', 'if', 'then', 'else', 'contains', 'items',
                       'additionalProperties', 'unevaluatedProperties', 'additionalItems', 'unevaluatedItems',
                       'propertyNames', 'contentSchema')]
        containers += [{key: {'nested': self.bad()}} for key in ('$defs', 'definitions', 'properties',
                       'dependentSchemas', 'dependencies', 'patternProperties')]
        for index, schema in enumerate(containers):
            with self.subTest(index=index):
                errors = self.errors({'components': {'schemas': {'Payload': schema}}})
                self.assertEqual(len(errors), 1, errors)

    def test_examples_vendor_extensions_and_dynamic_instance_keys_are_not_schemas(self):
        fake = {'properties': {'camelCase': {}}, '$defs': {'Fake': self.bad()}, 'schema': self.bad()}
        document = {'x-root': fake, 'components': {'examples': {'Payload': {'value': fake}},
                    'schemas': {'Actual': {'type': 'object', 'properties': {'valid_name': {}},
                    'example': fake, 'examples': [fake], 'default': fake, 'x-extension': fake}}},
                    'paths': {'x-path-extension': fake, '/one': {'get': {'x-operation-extension': fake,
                    'requestBody': {'content': {'application/json': {'schema': {'type': 'string'},
                    'example': fake, 'examples': {'sample': {'value': fake}}}}}}}}}
        self.assertEqual(self.errors(document), [])

    def test_precise_external_marker_does_not_propagate_to_nested_or_reference_nodes(self):
        marker = {'specification': 'External Example', 'anchor': 'https://example.org/spec#object'}
        external = self.bad()
        external['x-arkret-external-literal-object'] = marker
        self.assertEqual(self.errors({'components': {'schemas': {'External': external}}}), [])
        for changed_marker in ({'specification': 'External Example'}, {**marker, 'extra': True}, None):
            changed = {**external, 'x-arkret-external-literal-object': changed_marker}
            self.assertTrue(self.errors({'components': {'schemas': {'External': changed}}}))
        nested = copy.deepcopy(external)
        nested['properties']['nested'] = self.bad()
        self.assertEqual(len(self.errors({'components': {'schemas': {'External': nested}}})), 1)
        referenced = {'components': {'schemas': {'Source': external, 'Other': self.bad(),
                      'Alias': {'$ref': '#/components/schemas/Other', 'x-arkret-external-literal-object': marker}}}}
        errors = self.errors(referenced)
        self.assertTrue(any('/Other/' in error and 'camelCase' in error for error in errors), errors)
        self.assertTrue(any('/Alias/' in error and 'stale annotation' in error for error in errors), errors)

    def test_dynamic_map_key_is_not_a_property_but_its_value_schema_is(self):
        valid = {'type': 'object', 'patternProperties': {'Camel.*': {'type': 'string'}}, 'additionalProperties': True}
        self.assertEqual(self.errors({'components': {'schemas': {'Map': valid}}}), [])
        invalid = {'type': 'object', 'patternProperties': {'Camel.*': self.bad()}}
        errors = self.errors({'components': {'schemas': {'Map': invalid}}})
        self.assertEqual(len(errors), 1, errors)

    def test_reference_object_ignored_siblings_are_not_new_schema_declarations(self):
        document = {'components': {
            'parameters': {'Good': {'name': 'q', 'in': 'query', 'schema': {'type': 'string'}},
                           'Ref': {'$ref': '#/components/parameters/Good', 'schema': self.bad()}},
            'headers': {'Good': {'schema': {'type': 'string'}},
                        'Ref': {'$ref': '#/components/headers/Good', 'schema': self.bad()}},
            'requestBodies': {'Good': {'content': {}},
                             'Ref': {'$ref': '#/components/requestBodies/Good', **self.media()}},
            'responses': {'Good': {'description': 'fine'},
                          'Ref': {'$ref': '#/components/responses/Good', **self.media()}},
            'callbacks': {'Good': {}, 'Ref': {'$ref': '#/components/callbacks/Good',
                          '{$request.body#/url}': {'post': {'requestBody': self.media()}}}},
        }}
        self.assertEqual(self.errors(document), [])
        document['components']['schemas'] = {'Good': {'type': 'object'},
            'Sibling': {'$ref': '#/components/schemas/Good', **self.bad()}}
        document['components']['pathItems'] = {'Good': {},
            'Sibling': {'$ref': '#/components/pathItems/Good', 'post': {'requestBody': self.media()}}}
        self.assertEqual(len(self.errors(document)), 2)

    def test_yaml_non_string_property_keys_are_diagnostics_not_tracebacks(self):
        schema = {'properties': {42: {'type': 'string'}}}
        errors = self.errors({'components': {'schemas': {'Payload': schema}}})
        self.assertEqual(len(errors), 1)
        self.assertIn('property names must be strings', errors[0])
        schema['x-arkret-external-literal-object'] = {
            'specification': 'External Example', 'anchor': 'https://example.org/spec#object'}
        self.assertTrue(self.errors({'components': {'schemas': {'Payload': schema}}}))

    def test_recursive_local_references_activate_only_their_actual_targets(self):
        document = {'components': {'schemas': {'Root': {'$ref': '#/x-schema'}}},
                    'x-schema': {'properties': {'camelCase': {}, 'next_value': {'$ref': '#/x-schema'}}},
                    'x-unused': self.bad()}
        errors = self.errors(document)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn('/x-schema/properties/camelCase', errors[0])
        positions = [path for path, _ in naming_contracts.openapi_schema_positions(document)]
        self.assertEqual(len(positions), len(set(positions)))

    def test_missing_local_reference_is_a_diagnostic(self):
        errors = self.errors({'components': {'schemas': {'Root': {'$ref': '#/missing'}}}})
        self.assertTrue(any('does not resolve' in error for error in errors), errors)

    def test_external_anchor_urls_keep_legal_iri_and_ipv6_authorities(self):
        from tools.artifact_lint.naming import external_anchor_is_valid
        for anchor in ('https://example.org/spec#section', 'https://例子.测试/spec#部分',
                       'https://[2001:db8::1]:443/spec#section'):
            self.assertTrue(external_anchor_is_valid(anchor), anchor)
        for anchor in ('https://?q#part', 'https://example.org:/#part',
                       'https://example.org:65536/#part', 'https://example.org:bad/#part',
                       'https://example.org/\x00#part', 'https://example.org/#',
                       'https://example.org/ bad#part'):
            self.assertFalse(external_anchor_is_valid(anchor), anchor)

    def test_json_anchor_index_ignores_instance_anchors_and_nested_resources(self):
        from tools.artifact_lint.naming import enumerate_schema_properties
        document = {'$id': 'https://example.org/root', '$defs': {
            'Real': {'$anchor': 'real', 'properties': {'actual_name': {}}},
            'Other': {'$id': 'other', '$anchor': 'real', 'properties': {'other_name': {}}}},
            'allOf': [{'$ref': '#real'}],
            'examples': [{'$anchor': 'real', 'properties': {'camelCase': {}}}]}
        paths = [occurrence.pointer for occurrence in enumerate_schema_properties('one', document)]
        self.assertEqual(len(paths), 2)
        self.assertFalse(any('examples' in path for path in paths))

    def test_referenced_media_schema_registers_its_own_resource(self):
        document = {'components': {'mediaTypes': {'Payload': {'$ref': '#/x-media'}}},
            'x-media': {'schema': {'$id': 'https://example.org/payload',
                '$defs': {'Value': self.bad()}, '$ref': '#/$defs/Value'}}}
        errors = self.errors(document)
        self.assertTrue(any('/x-media/schema/$defs/Value/properties/camelCase' in error for error in errors), errors)

    def test_dynamic_reference_and_nested_resource_follow_real_targets(self):
        from tools.artifact_lint.naming import enumerate_schema_properties, naive_property_occurrences
        document = {'$id': 'https://example.org/root', '$defs': {'Nested': {
            '$id': 'nested', '$defs': {'Value': self.bad()}, '$ref': '#/$defs/Value'}},
            '$dynamicRef': '#/x-schema', 'x-schema': self.bad()}
        occurrences = list(enumerate_schema_properties('one', document))
        self.assertEqual(len(occurrences), 2)
        self.assertEqual({(value.pointer, value.name) for value in occurrences}, naive_property_occurrences(document))

    def test_malformed_pointer_and_scalar_targets_fail_closed(self):
        for document in ({'$ref': '#/x~2schema', 'x~2schema': {}}, {'$ref': '#/x-schema', 'x-schema': 'data'}):
            with self.subTest(document=document):
                errors = self.errors({'components': {'schemas': {'Root': document}}})
                self.assertTrue(errors)

    def test_json_owner_coverage_keeps_file_identity(self):
        original = naming_contracts.enumerate_property_owners
        def incomplete(file_name, document):
            return original(file_name, document) if file_name == 'one.schema.json' else iter(())
        documents = {name: {'properties': {'valid_name': {}}}
                     for name in ('one.schema.json', 'two.schema.json')}
        lint = Lint()
        with patch.object(naming_contracts, 'enumerate_property_owners', side_effect=incomplete):
            naming_contracts.check_wire_property_name_case(lint, documents)
        self.assertTrue(any('disagrees' in error and 'two.schema.json' in error for error in lint.errors), lint.errors)


if __name__ == '__main__':
    unittest.main()
