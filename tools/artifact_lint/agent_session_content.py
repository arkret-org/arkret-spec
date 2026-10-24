"""Validate resource-bound Agent session authority and phased MLS bootstrap."""
from .core import ARTIFACTS, Lint, load_json

VECTOR = 'ak.vector.agent.session_content_authority.v1'
READ_ACTIONS = [
    'ak.event.read', 'ak.object.read', 'ak.object.read_content',
    'ak.object.read_history', 'ak.object.read_metadata', 'ak.strand.read',
]
INVARIANTS = {
    'literal_read_grant_required': False,
    'provision_or_participation_grants_content': False,
    'source_read_grants_write': False,
    'new_issue_requires_predecessor_content': False,
    'fresh_issue_supersedes_old_chain': False,
    'refresh_expands_ceiling': False,
    'empty_content_selector_is_unbounded': False,
    'absent_policy_requires_synthetic_ref': False,
    'unknown_policy_means_absent': False,
    'bootstrap_requires_effective': False,
    'desired_grants_payload': False,
    'old_overlay_is_current_authority': False,
    'unrelated_realm_limits_independent_direct': False,
    'future_material_rechecks_current': True,
    'all_content_paths_obey_provision_key_session': True,
    'same_resource_complete_allow_path': True,
    'all_matching_denies_apply': True,
    'current_gate_each_delivery': True,
    'retained_conditions_checked_at_use': True,
    'exact_replay_keeps_original_credential': True,
}
REQUIRED_CASES = set('''
membership_read_without_literal_grant membership_does_not_grant_write literal_write_grant
direct_read_without_realm_grant direct_registered_write_authority direct_wrong_participant_binding
sidecar_read_without_literal_grant sidecar_read_does_not_grant_write provision_only_is_not_authority
participation_only_is_not_authority accountability_only_is_not_authority service_only_session
fresh_issue_after_service_session issue_pending_mls_is_only_ceiling refresh_preserves_existing_ceiling
refresh_rejects_scope_expansion refresh_rejects_scope_request_field refresh_current_authority_lost
exact_issue_replay_unchanged terminal_issue_replay conflicting_issue_replay
bootstrap_desired_not_yet_effective bootstrap_wrong_endpoint bootstrap_missing_add_welcome_claim_lineage
desired_cannot_read_payload effective_sidecar_payload wrong_sidecar_binding
queued_welcome_after_desired_revoke future_epoch_material_after_desired_revoke valid_future_epoch_material
cross_authority_source_unregistered no_policy_with_complete_current_evidence policy_unknown_is_not_absent
explicit_policy_allow policy_deny action_resource_cannot_be_spliced unsafe_flat_cross_product
one_complete_path_among_alternatives revoked_grant_path_cannot_restore revoked_literal_read_does_not_erase_membership
provision_omits_content key_omits_content request_omits_content content_selector_missing
runtime_mandatory_floor_missing issuer_proof_invalid holder_authorization_replaced source_stale_or_unknown
ordinary_controller_read_revoked management_read_denied global_deny_overrides_complete_allow
session_service_only_cannot_read history_not_visible participation_current_denied condition_not_satisfied
quota_exhausted approval_missing mls_not_ready_for_payload
direct_authority_cannot_read_ordinary_realm realm_grant_cannot_replace_sidecar_authority
realm_membership_cannot_replace_direct_participant
direct_verified_interval_without_origin_poll
sidecar_explicit_write_grant sidecar_write_grant_without_effective
sidecar_write_grant_after_desired_loss sidecar_material_not_a_write_grant_operation
'''.split())


def path_allows(path, case):
    if not all(path.get(key) is True for key in ('complete', 'active')):
        return False
    if case['action'] not in path.get('actions', []) or case['resource'] not in path.get('resources', []):
        return False
    kind = path.get('kind')
    profile = case.get('resource_profile')
    if profile == 'direct':
        return kind == 'direct_participant'
    if profile == 'sidecar':
        if case.get('desired') is not True:
            return False
        if case['action'] in READ_ACTIONS:
            return kind == 'sidecar_read'
        return kind == 'capability_grant'
    if profile not in ('realm', 'circle'):
        return False
    return kind == 'capability_grant' or (kind == 'membership_read' and case['action'] in READ_ACTIONS)


def decide(case):
    """Inputs are verified predicates; this is not a runtime proof validator."""
    phase = case.get('phase')
    if phase not in ('issue', 'refresh', 'bootstrap', 'payload', 'future_material'):
        return 'deny'
    if not all(case.get(key) is True for key in ('proof_valid', 'holder_current', 'same_account_scope')):
        return 'deny'
    replay = case.get('replay_state')
    if phase in ('issue', 'refresh') and replay != 'none':
        return 'reuse_original' if replay == 'active_exact' else 'deny'
    if not all(case.get(key) is True for key in (
        'provision_allows', 'key_allows', 'request_allows', 'runtime_floor_complete',
    )):
        return 'deny'
    if phase != 'issue' and case.get('session_allows') is not True:
        return 'deny'
    if phase == 'refresh' and (
        case.get('refresh_ceiling_unchanged') is not True
        or case.get('scope_request_field_present') is not False
    ):
        return 'deny'
    if case.get('action') == 'service_operation':
        return 'allow' if phase in ('issue', 'refresh') else 'deny'
    if not all(case.get(key) is True for key in (
        'content_selector_present', 'source_current', 'source_supply_verified',
        'management_allows', 'flat_encoding_safe',
    )) or case.get('global_deny') is not False:
        return 'deny'
    if case.get('policy_state') not in ('absent_proven', 'allow'):
        return 'deny'
    if case.get('resource_profile') != 'direct' and case.get('controller_allows') is not True:
        return 'deny'
    if not any(path_allows(path, case) for path in case.get('paths', [])):
        return 'deny'
    if case.get('resource_profile') == 'sidecar' and case.get('exact_endpoint') is not True:
        return 'deny'
    if phase in ('bootstrap', 'future_material'):
        if case.get('resource_profile') != 'sidecar' or case.get('accepted_lineage') is not True or case.get('action') != 'ak.event.read':
            return 'deny'
    if phase not in ('issue', 'refresh'):
        if not all(case.get(key) is True for key in (
            'history_visible', 'participation_allows', 'conditions_allow',
            'quota_available', 'approval_allows',
        )):
            return 'deny'
    if phase == 'payload':
        if case.get('mls_ready') is not True:
            return 'deny'
        if case.get('resource_profile') == 'sidecar' and case.get('effective') is not True:
            return 'deny'
    return 'allow'


def check_agent_session_content(lint: Lint) -> None:
    registry_path = ARTIFACTS / 'registry/owned-agent-authority-registry.json'
    authority = load_json(lint, registry_path)
    registry = authority.get('session_content_authority_contract', {})
    exact_fields = {
        'vector_id': VECTOR,
        'fixture_ref': 'fixtures/agent-vectors-fixture.json#/session_content_authority_contract',
        'authority_paths': ['capability_grant', 'membership_read', 'direct_participant', 'sidecar_read'],
        'read_actions': READ_ACTIONS,
        'issuance_operation': 'ak.gate.account.command.issue_session_grant.v1',
        'refresh_operation': 'ak.gate.account.command.refresh_session_grant.v1',
        'scope_addition': 'fresh_issue_new_signed_intent',
        'refresh_ceiling': 'preserve_predecessor_no_expansion',
        'source_supply': 'owning_station_authenticated_current_with_exact_binding',
        'cross_authority_unregistered_source': 'fail_closed',
        'flat_encoding': 'conservative_common_coverage_or_separate_resource_request',
        'sidecar_bootstrap': 'desired_exact_endpoint_accepted_lineage_not_effective',
        'sidecar_payload': 'effective_exact_endpoint',
        'material_read_action': 'ak.event.read',
        'keypackage_ledger_gate': 'service_exact_endpoint_and_profile_not_content_write',
        'invariants': INVARIANTS,
    }
    if registry != exact_fields:
        lint.fail(registry_path, 'Agent session content authority, current supply or rotation contract drift')
    approval_error = authority.get('session_human_approval_contract', {}).get('error')
    if approval_error != {'status': 403, 'code': 'claim_required',
                          'reason_code': 'human_approval_required',
                          'correlation_member': 'approval_request_id'}:
        lint.fail(registry_path, 'Agent approval must retain its closed RFC9457 error contract')
    mapping_path = ARTIFACTS / 'registry/operations-error-mapping.json'
    operations = {row.get('operation_id'): row for row in load_json(lint, mapping_path).get('operations', [])}
    issue_codes = operations.get(exact_fields['issuance_operation'], {}).get('operation_specific', [])
    refresh_codes = operations.get(exact_fields['refresh_operation'], {}).get('operation_specific', [])
    if 'human_approval_required' not in issue_codes or 'human_approval_required' in refresh_codes:
        lint.fail(mapping_path, 'Agent approval reason must bind issue, never ordinary refresh')
    errors_path = ARTIFACTS / 'registry/error-code-registry.json'
    errors = load_json(lint, errors_path)
    parent = next((row for row in errors.get('codes', []) if row.get('code') == 'claim_required'), {})
    reason = next((row for row in errors.get('reason_codes', []) if row.get('code') == 'human_approval_required'), {})
    if parent.get('http_status') != 403 or parent.get('status') != 'active' or reason.get('status') != 'active':
        lint.fail(errors_path, 'Agent approval requires active claim_required403 and its registered reason')
    fixture_path = ARTIFACTS / 'fixtures/agent-vectors-fixture.json'
    fixture = load_json(lint, fixture_path).get('session_content_authority_contract', {})
    if fixture.get('vector_id') != VECTOR or fixture.get('registry_ref') != 'registry/owned-agent-authority-registry.json#/session_content_authority_contract':
        lint.fail(fixture_path, 'Agent session fixture must bind the canonical authority contract and vector')
    cases = fixture.get('cases', [])
    names = [case.get('name') for case in cases]
    if len(names) != len(set(names)) or set(names) != REQUIRED_CASES or set(fixture.get('required_case_names', [])) != REQUIRED_CASES:
        lint.fail(fixture_path, 'Agent session fixture must retain every distinct source, scope, replay and bootstrap boundary')
    defaults = fixture.get('defaults', {})
    for case in cases:
        if case.get('name') == 'participation_current_denied':
            expected = {
                'phase': 'payload', 'action': 'ak.message.create',
                'participation_allows': False,
                'paths': [{'kind': 'capability_grant', 'actions': ['ak.message.create'],
                           'resources': ['A'], 'complete': True, 'active': True}],
            }
            if case.get('input') != expected:
                lint.fail(fixture_path, 'Participation refusal must bind a granted reply action, not membership reading')
        if case.get('name') == 'approval_missing':
            expected = {
                'phase': 'payload', 'action': 'ak.message.create',
                'approval_allows': False,
                'paths': [{'kind': 'capability_grant', 'actions': ['ak.message.create'],
                           'resources': ['A'], 'complete': True, 'active': True}],
            }
            if case.get('input') != expected:
                lint.fail(fixture_path, 'Payload approval refusal must bind a granted action with a registered confirmation carrier')
        if case.get('name') in ('condition_not_satisfied', 'quota_exhausted'):
            gate = 'conditions_allow' if case['name'] == 'condition_not_satisfied' else 'quota_available'
            expected = {
                'phase': 'payload', 'action': 'ak.message.create', gate: False,
                'paths': [{'kind': 'capability_grant', 'actions': ['ak.message.create'],
                           'resources': ['A'], 'complete': True, 'active': True}],
            }
            if case.get('input') != expected:
                lint.fail(fixture_path, 'Payload limit refusal must bind the actual constrained grant path')
        try:
            actual = decide(defaults | case['input'])
        except (KeyError, TypeError):
            actual = 'invalid_case'
        if case.get('expected') != actual:
            lint.fail(fixture_path, f"Agent session content decision drift: {case.get('name')}: {actual}")
    schemas = load_json(lint, ARTIFACTS / 'schemas/service-operation-dtos.schema.json')['$defs']
    refresh = schemas['AgentSessionGrantRefreshRequestBody']
    if refresh.get('additionalProperties') is not False or {'requested_scope', 'agent_scope_request'} & set(refresh.get('properties', {})):
        lint.fail(registry_path, 'Agent refresh must remain a closed non-expanding rotation request')
    refs = schemas['SessionGrantIntrospectGrant']['properties']['scope_details']['properties']['capability_grant_refs']
    if refs.get('minItems', 0) != 0:
        lint.fail(registry_path, 'Legitimate profile reading must not require a literal grant reference')
    profiles = load_json(lint, ARTIFACTS / 'profiles/conformance-profiles.json')
    requirements = next((value['ak.profile.agent_auth.v1'] for value in profiles.values()
                         if isinstance(value, dict) and isinstance(value.get('ak.profile.agent_auth.v1'), dict)), {})
    if requirements.get('rules', {}).get('session_content_authority_contract_ref') != 'registry/owned-agent-authority-registry.json#/session_content_authority_contract':
        lint.fail(registry_path, 'Agent Auth profile must consume the canonical content authority contract')
