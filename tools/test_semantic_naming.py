"""Mutations exercise semantic names and the complete release contract."""
import copy
import unittest
import json
import subprocess
import tempfile
from pathlib import Path
from jsonschema import Draft202012Validator

from .artifact_lint.semantic_naming import openapi_component_alias_errors,canonical_body_alias_errors,capture_member_reference_errors,enum_errors,member_role_errors,type_role_errors,retired_contract_reference_errors
from .protocol_member_contract import REFERENCE, check, compare, contract_shape, derive, registry_contract_shape


class SemanticNamingTests(unittest.TestCase):
    def test_openapi_aliases_cannot_duplicate_a_shared_canonical_type(self):
        reference = {'$ref': '../schemas/example.schema.json#/$defs/shared'}
        self.assertEqual(openapi_component_alias_errors({'Shared': reference}), [])
        for alias in (reference, {**reference, 'description': 'another use'},
                      {'allOf': [reference]}, {'oneOf': [reference]}):
            self.assertTrue(openapi_component_alias_errors({'Shared': reference, 'OperationBody': alias}))
        self.assertEqual(openapi_component_alias_errors({
            'Shared': reference, 'Restricted': {**reference, 'required': ['purpose']}}), [])

    def test_account_revocation_names_match_their_exact_subject_scope(self):
        from referencing import Registry, Resource
        from .realm_actor_contract import actor, token
        schemas = Path(__file__).resolve().parents[1] / 'spec/v1/artifacts/schemas'
        documents = [json.loads(path.read_text(encoding='utf-8')) for path in schemas.glob('*.json')]
        registry = Registry().with_resources((doc['$id'], Resource.from_contents(doc)) for doc in documents)

        def validator(name):
            return Draft202012Validator({'$ref': 'https://arkret.org/v1/schemas/device-revocation-state.schema.json#/$defs/' + name}, registry=registry)

        common = {'schema': 'ak.schema.device_revocation_state.v1',
                  'account_id': {'principal_id': 'ak:did_core:web:alice.example', 'station_id': 'ak:did_core:web:station.example'},
                  'device_id': 'ak:device:01964137-0000-7000-8000-000000000001',
                  'target_device_authorize_event_id': token('event'), 'target_device_generation_ref': 1,
                  'proposal_event_id': token('event', 2), 'accepted_at': '2026-10-24T00:00:00.000Z', 'acceptance_sequence': 1}
        for name, status, extras in [
            ('device_revocation_pending_state', 'revocation_pending', {'denied_actions': ['session_grant_issue_or_refresh', 'device_pairing_code_claim', 'keypackage_claim', 'to_device_write', 'event_write']}),
            ('device_revocation_rejected_state', 'revocation_rejected', {}),
            ('device_revoked_state', 'revoked', {'committed_at': '2026-10-24T00:00:01.000Z'}),
        ]:
            account = {**common, 'status': status, **extras}
            realm = {**account, 'actor_id': actor()}
            del realm['account_id']
            for candidate in (account, realm):
                validator(name).validate(candidate)
                validator('device_revocation_record').validate(candidate)
            validator('account_' + name).validate(account)
            validator('account_device_revocation_record').validate(account)
            self.assertFalse(validator('account_' + name).is_valid(realm))
            self.assertFalse(validator('account_device_revocation_record').is_valid(realm))
            if status != 'revocation_rejected':
                validator('account_device_revocation_gate_record').validate(account)
                self.assertFalse(validator('account_device_revocation_gate_record').is_valid(realm))
            else:
                self.assertFalse(validator('account_device_revocation_gate_record').is_valid(account))

    def test_snapshot_cannot_be_an_unbounded_summary_or_pin_optional_fields(self):
        snapshot = {'type': 'object', 'required': ['version', 'members'],
                    'properties': {'version': {'type': 'integer'}, 'members': {'type': 'array'}},
                    'x-arkret-snapshot-boundary': {'cut_fields': ['version'], 'coverage_fields': ['members']}}
        self.assertEqual(type_role_errors('membership_snapshot', snapshot), [])
        for mutation in ('missing_boundary', 'unknown_cut', 'optional_coverage'):
            changed = copy.deepcopy(snapshot)
            if mutation == 'missing_boundary':
                del changed['x-arkret-snapshot-boundary']
            elif mutation == 'unknown_cut':
                changed['x-arkret-snapshot-boundary']['cut_fields'] = ['read_at']
            else:
                changed['required'].remove('members')
            self.assertTrue(type_role_errors('membership_snapshot', changed), mutation)

    def test_singular_row_and_nested_result_names_are_not_field_role_exceptions(self):
        for name in ('row', 'current_row', 'result', 'policy_results', 'session_grant_result'):
            self.assertTrue(member_role_errors(name, {'type': 'object'}), name)
        for name in ('current_state', 'policy_evaluations', 'issued_session'):
            self.assertEqual(member_role_errors(name, {'type': 'object'}), [])

    def test_outcome_members_need_a_settled_scope_even_without_a_named_enum(self):
        scope = {'x-arkret-outcome-scope': 'holder_admission_attempt'}
        self.assertTrue(member_role_errors('outcome', {'enum': ['accepted']}))
        self.assertEqual(member_role_errors('outcome', {**scope, 'enum': ['accepted', 'deferred']}), [])
        self.assertTrue(member_role_errors('outcome', {**scope, 'enum': ['pending']}))

    def test_public_rows_and_role_metadata_are_rejected(self):
        for name, node in [('RealmRow', {}), ('realm_row', {}), ('Row', {}),
                           ('realm_view', {'x-arkret-name-role': 'row'}),
                           ('stream_row', {'$ref': '#/$defs/CommittedEventView'})]:
            with self.subTest(name=name):
                self.assertTrue(type_role_errors(name, node))
        for name in ('RealmView', 'account_data_entry', 'CurrentMimiRoomBinding'):
            self.assertEqual(type_role_errors(name, {}), [])
        self.assertTrue(retired_contract_reference_errors('ContactListRow stream_row'))


    def test_error_and_reason_code_authority_is_in_the_release_freeze(self):
        root = Path(__file__).resolve().parents[1]
        registry = json.loads((root / 'spec/v1/artifacts/registry/error-code-registry.json').read_text(encoding='utf-8'))
        self.assertIs(registry.get('source_of_truth'), True)
        baseline = derive(root)
        row = next(row for row in baseline['canonical_registries'] if row['file'] == 'error-code-registry.json')
        changed = copy.deepcopy(baseline)
        next(row for row in changed['canonical_registries'] if row['file'] == 'error-code-registry.json')['digest'] = 'changed-error-vocabulary'
        self.assertTrue(row['digest'].startswith('sha256:'))
        self.assertTrue(compare(baseline, changed))

    def test_retired_pascal_terms_cannot_survive_in_normative_notes(self):
        self.assertTrue(retired_contract_reference_errors('MlsGroupCurrent.effective_scope'))
        self.assertTrue(retired_contract_reference_errors('TypedCurrentRow and AccountCurrentView'))
        self.assertEqual(retired_contract_reference_errors('MlsGroupValue CurrentState AccountStateView'), [])

    def test_normative_ci_fetches_release_tags_and_full_history(self):
        root = Path(__file__).resolve().parents[1]
        for name in ('artifact-lint.yml', 'release-gate.yml'):
            workflow = (root / '.github/workflows' / name).read_text(encoding='utf-8')
            self.assertIn('uses: actions/checkout@v4\n        with:\n          fetch-depth: 0', workflow)

    def test_canonical_body_alias_cannot_reintroduce_an_equivalent_second_name(self):
        alias = {'$ref': './canonical.schema.json#/$defs/receipt', 'x-arkret-name-role': 'response_body'}
        self.assertTrue(canonical_body_alias_errors('issue_response_body', alias))
        self.assertEqual(canonical_body_alias_errors('issue_response_body', {**alias, 'required': ['nonce']}), [])
        for operator in ('allOf', 'anyOf', 'oneOf'):
            wrapped = {operator: [{'allOf': [alias]}]}
            self.assertTrue(canonical_body_alias_errors('issue_response_body', wrapped))
            self.assertEqual(canonical_body_alias_errors('issue_response_body', {**wrapped, 'required': ['nonce']}), [])

    def test_capture_prose_references_follow_the_schema_member(self):
        self.assertEqual(capture_member_reference_errors('recording_transition.capture_metadata.retention'), [])
        self.assertTrue(capture_member_reference_errors('recording_transition.result.retention'))
        self.assertTrue(capture_member_reference_errors('outcome="blocked_by_legal_hold"'))

    def test_decimal_integer_schema_rejects_numeric_and_noncanonical_values(self):
        schema = json.loads((Path(__file__).resolve().parents[1] / 'spec/v1/artifacts/schemas/decimal-integers.schema.json').read_text(encoding='utf-8'))
        for name, maximum in [('uint64_decimal', 2**64 - 1), ('nonnegative_int64_decimal', 2**63 - 1)]:
            validator = Draft202012Validator(schema['$defs'][name])
            for number in (0, 1, 2**53 + 1, maximum - 1, maximum):
                with self.subTest(name=name, valid=number):
                    self.assertTrue(validator.is_valid(str(number)))
                    self.assertFalse(validator.is_valid(number))
            for invalid in ('', '00', '01', '+1', '-1', '1.0', '1e3', ' 1', '1 ', str(maximum + 1), None):
                with self.subTest(name=name, invalid=invalid):
                    self.assertFalse(validator.is_valid(invalid))

    def test_published_v1_tag_blocks_replacing_the_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = root / 'spec/v1/artifacts'
            for folder in ('schemas', 'registry', 'openapi'):
                (artifacts / folder).mkdir(parents=True)
            encoding = root / 'spec/v1/zh/conformance/encoding.md'
            encoding.parent.mkdir(parents=True)
            encoding.write_text('Canonical encoding', encoding='utf-8')
            (artifacts / 'openapi/arkret-service-api.openapi.yaml').write_text('openapi: 3.1.0\n', encoding='utf-8')
            schema = artifacts / 'schemas/value.schema.json'
            schema.write_text(json.dumps({'type': 'object', 'properties': {'value': {'type': 'string'}}}), encoding='utf-8')
            reference = root / REFERENCE
            reference.parent.mkdir(parents=True)
            reference.write_text(json.dumps(derive(root)), encoding='utf-8')
            commands = [
                ['init', '-q'], ['config', 'user.name', 'Contract Test'],
                ['config', 'user.email', 'contract@example.invalid'],
                ['add', '.'], ['commit', '-qm', 'Freeze initial contract'], ['tag', 'v1.2.3'],
            ]
            for command in commands:
                subprocess.run(['git', *command], cwd=root, check=True, capture_output=True)
            self.assertEqual(check(root), [])
            shallow = root / 'shallow'
            subprocess.run(['git', 'clone', '--depth', '1', root.as_uri(), str(shallow)],
                           check=True, capture_output=True)
            self.assertTrue(any('full Git history and tags' in error for error in check(shallow)))
            schema.write_text(json.dumps({'type': 'object', 'properties': {'renamed': {'type': 'string'}}}), encoding='utf-8')
            reference.write_text(json.dumps(derive(root)), encoding='utf-8')
            self.assertTrue(any('v1.2.3 is immutable' in error for error in check(root)))

    def test_maintenance_metadata_does_not_erase_wire_version(self):
        document = {'source_of_truth': True, 'version': '2026-10-24.1',
                    'properties': {'version': {'const': 'v1'}}}
        changed = copy.deepcopy(document)
        changed['version'] = '2026-10-24.2'
        self.assertEqual(registry_contract_shape(document), registry_contract_shape(changed))
        changed['properties']['version']['const'] = 'v2'
        self.assertNotEqual(contract_shape(document), contract_shape(changed))

    def test_body_and_terminal_roles_are_distinct(self):
        self.assertEqual(type_role_errors('IssueResponseBody',{'x-arkret-name-role':'response_body'}),[])
        self.assertTrue(type_role_errors('IssueOutcome',{'x-arkret-name-role':'response_body'}))
        settled={'x-arkret-name-role':'terminal_outcome','x-arkret-outcome-scope':'attempt','enum':['accepted','rejected']}
        self.assertEqual(type_role_errors('AttemptOutcome',settled),[])
        self.assertTrue(type_role_errors('AttemptOutcome',{**settled,'enum':['accepted','pending']}))

    def test_positive_member_grammar(self):
        self.assertEqual(member_role_errors('max_channel_count',{'x-arkret-member-role':'count','type':'integer'}),[])
        self.assertTrue(member_role_errors('max_channels',{'x-arkret-member-role':'count','type':'integer'}))
        self.assertTrue(member_role_errors('export',{'x-arkret-member-role':'permission','type':'boolean'}))
        self.assertTrue(member_role_errors('expires_after',{'x-arkret-member-role':'instant'}))

    def test_current_list_page_and_set_have_roles(self):
        self.assertTrue(type_role_errors('AgentResult',{}))
        self.assertTrue(type_role_errors('AgentState',{'x-arkret-name-role':'current_state'}))
        self.assertTrue(type_role_errors('UserList',{'properties':{'next_cursor':{}}}))
        self.assertTrue(type_role_errors('UserPage',{'properties':{'exists':{}}}))
        self.assertTrue(type_role_errors('AlgorithmSet',{'type':'array','uniqueItems':True}))

    def test_enum_authority_cannot_expand_or_propagate(self):
        node={'enum':['valid'],'x-arkret-value-ownership':{'class':'owned_symbol','authority':'owner','owner':'schema#/field','values':['valid']}}
        self.assertEqual(enum_errors(node,'schema#/field'),[])
        self.assertTrue(enum_errors({**node,'enum':['New-Wrong-Value']},'schema#/field'))
        self.assertTrue(enum_errors(node,'schema#/another_field'))
        self.assertTrue(enum_errors({'enum':['Bad-Value']}))
        external={'const':'Ed25519','x-arkret-value-ownership':{'class':'external_literal','authority':'https://www.rfc-editor.org/rfc/rfc8032.html#section-5.1','owner':'schema#/algorithm','values':['Ed25519']}}
        self.assertEqual(enum_errors(external,'schema#/algorithm'),[])
        self.assertTrue(enum_errors(external,'schema#/unrelated'))

    def test_every_public_contract_axis_is_frozen(self):
        base={'schemas':[{'file':'one.schema.json','contract':{'type':'object','required':['value'],'properties':{'value':{'type':'string','enum':['a'],'x-arkret-member-role':'domain_value'}},'additionalProperties':False}}],'canonical_registries':[],'openapi':{}}
        for change in ('name','type','required','nullable','enum','encoding','unit','signature','open_slot'):
            with self.subTest(change=change):
                actual=copy.deepcopy(base);shape=actual['schemas'][0]['contract'];member=shape['properties']['value']
                if change=='name':shape['properties']['other']=shape['properties'].pop('value')
                elif change=='required':shape['required']=[]
                elif change=='type':member['type']='integer'
                elif change=='nullable':member['type']=['string','null']
                elif change=='enum':member['enum'].append('b')
                elif change=='open_slot':shape['additionalProperties']=True
                else:member['x-arkret-'+change]='changed'
                self.assertTrue(compare(base,actual))


if __name__=='__main__':unittest.main()
