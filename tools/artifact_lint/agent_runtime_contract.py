"""Guard the independent portable authority and participation contracts."""
from .core import ARTIFACTS, Lint, load_json


def participation_allows(case: dict) -> bool:
    return (
        case.get('role') == 'target'
        and case.get('selection_source') == 'authenticated_owner_current'
        and case.get('same_station') is True
        and case.get('current_selection') is True
        and case.get('complete_governance_cut') is True
        and case.get('exact_binding') is True
        and case.get('selection_bit') is True
        and case.get('ceiling_bit') is True
    )


REPLY_READINESS_GATES = (
    'actor_binding', 'public_mode', 'message_authority', 'content_service_scope',
    'membership_lifecycle', 'participation_ceiling', 'runtime_session_key', 'scope_mls',
)


def reply_configuration_decision(table: str, case: dict):
    """Evaluate local product decisions; these outputs are never wire authority."""
    if table == 'authorization_cases':
        return (
            all(case.get(key) is True for key in (
                'exact_account_scope_binding', 'joined', 'other_action_gates',
            ))
            and (case.get('actor_root_authority') is True or case.get('effective_message_grant') is True)
        )
    if table == 'setup_cases':
        if case.get('intent') in {'preference_only', 'mode_only'}:
            return 'no_grant'
        if case.get('intent') != 'shared_reply':
            return 'invalid'
        if not all(case.get(key) is True for key in ('exact_account_scope_binding', 'global_scope_allows')):
            return 'blocked'
        state = case.get('grant_state')
        if state == 'unknown':
            return 'pending'
        if state == 'accepted':
            return 'reuse_grant'
        if state == 'refused':
            return 'refused'
        if state != 'missing':
            return 'invalid'
        if case.get('confirmation_is_explicit') is not True:
            return 'needs_confirmation'
        if case.get('verified_owned_source') is True:
            return 'publish_grant' if case.get('current_controller_authority') is True and case.get('management_allows') is True else 'blocked'
        return 'publish_grant' if case.get('issuer_can_grant') is True else 'requires_issuer'
    if table == 'readiness_cases':
        configured = case.get('configuration_accepted')
        if configured is not True:
            return 'pending' if configured is None else 'not_configured'
        if any(case.get(key) is False for key in REPLY_READINESS_GATES):
            return 'blocked'
        if any(case.get(key) is not True for key in REPLY_READINESS_GATES):
            return 'pending'
        return 'ready'
    if table == 'recovery_cases':
        kind = case.get('kind')
        if kind == 'unknown_submission':
            return 'retain_exact_pending_submission'
        if kind == 'refused_submission':
            return 'new_request_after_authority_repair'
        if kind == 'reset' or not all(case.get(key) is True for key in (
            'same_account_scope_binding', 'active_message_grant',
        )):
            return 'needs_new_confirmation'
        if kind == 'restart':
            return 'reuse_grant'
        if kind == 'endpoint_replacement':
            return 'reuse_grant_restore_endpoint'
    return 'invalid'


def check_reply_configuration_contract(lint: Lint, runtime: dict, fixture: dict, path) -> None:
    product = runtime.get('product_configuration', {})
    true_fields = {
        'explicit_account_scope_action_confirmation', 'separate_authorized_grant_submission',
        'default_scope_is_narrowest_applicable', 'extra_actions_or_realm_expansion_require_confirmation',
        'reuse_active_bound_grant', 'selected_configured_and_effective_are_distinct',
        'inline_progress_and_result', 'pending_intent_blocks_duplicate_clicks',
        'unknown_submission_reuses_exact_signed_bytes', 'cold_setup_and_retained_restart_require_live_reply',
    }
    false_fields = {
        'membership_grants_message_create', 'agent_inherits_controller_authority',
        'normal_entry_requires_raw_did_or_action', 'preference_or_mode_write_materializes_grant',
        'cross_service_atomic_success', 'unknown_is_effective', 'effective_state_is_new_wire_or_authority',
        'definitive_refusal_replays_ciphertext', 'reset_or_new_binding_inherits_old_authority',
        'private_selection_disclosed_to_third_party',
    }
    expected = dict.fromkeys(true_fields, True) | dict.fromkeys(false_fields, False) | {
        'vector_id': 'ak.vector.agent.interaction_mode.v1',
        'fixture_ref': 'fixtures/agent-participation-fixture.json#/reply_configuration_contract',
        'default_message_action': 'ak.message.create',
    }
    if set(product) != set(expected) or any(
        product.get(key) is not value if isinstance(value, bool) else product.get(key) != value
        for key, value in expected.items()
    ):
        lint.fail(path, 'canonical reply configuration must retain explicit scope, separate authority and recovery boundaries')
    matrix = fixture.get('reply_configuration_contract', {})
    if matrix.get('registry_ref') != 'registry/contract-registry.json#/did_evidence_boundary_registry/agent_participation_runtime_contract/product_configuration' or matrix.get('vector_id') != expected['vector_id']:
        lint.fail(path, 'reply configuration fixture must bind its canonical contract and existing vector')
    required = {
        'authorization_cases': {
            'human_joined_without_write_authority', 'human_realm_root_controller',
            'human_with_effective_message_grant', 'agent_does_not_inherit_owner_controller',
            'agent_joined_without_write_authority', 'agent_with_effective_message_grant',
            'grant_wrong_station_or_scope', 'grant_cannot_replace_membership',
            'grant_cannot_bypass_independent_action_gates',
        },
        'setup_cases': {
            'preference_alone_never_grants', 'public_mode_alone_never_grants',
            'missing_grant_requires_scope_confirmation', 'confirmed_normal_entry_authors_separate_grant',
            'unverified_controller_without_issuer_authority', 'accepted_matching_grant_is_reused',
            'owned_controller_without_general_grant_authority', 'owned_controller_management_denied',
            'unknown_grant_is_not_absence', 'wrong_account_or_scope_confirmation',
            'realm_grant_cannot_expand_global_ceiling', 'refused_grant_is_not_configuration_success',
        },
        'readiness_cases': {
            'accepted_configuration_and_current_gates', 'selected_preference_is_not_accepted_configuration',
            'partial_or_unknown_configuration',
        } | {prefix + key for prefix in ('missing_', 'unknown_') for key in REPLY_READINESS_GATES},
        'recovery_cases': {
            'retained_restart_reuses_grant', 'same_agent_repairing_reuses_grant_but_restores_endpoint',
            'cleared_database_requires_new_confirmation', 'new_account_station_or_realm_cannot_reuse_grant',
            'expired_or_revoked_grant_requires_new_confirmation', 'response_loss_retains_exact_grant_submission',
            'definitive_message_refusal_requires_new_request',
        },
    }
    for table, names in required.items():
        cases = matrix.get(table, [])
        if not isinstance(cases, list) or len(cases) != len(names) or {case.get('name') for case in cases if isinstance(case, dict)} != names:
            lint.fail(path, f'reply configuration {table} omits or duplicates a required boundary')
            continue
        for case in cases:
            actual = reply_configuration_decision(table, case)
            if (case.get('expected') is not actual if isinstance(actual, bool) else case.get('expected') != actual):
                lint.fail(path, f"reply configuration {table}: {case['name']} expected {case.get('expected')}, got {actual}")


def check_agent_runtime_contract(lint: Lint) -> None:
    path = ARTIFACTS / 'schemas/agent-authority-evidence.schema.json'
    schema = load_json(lint, path)
    defs = schema['$defs']
    state = defs['agent_authority_state']
    required = {'authority_id', 'agent_id', 'source_commit_id', 'pcr_genesis_event',
                'key_authorization_event', 'authorization', 'key_state_witness',
                'agent_lifecycle_witness', 'commit_lineages', 'commits',
                'authority_bundle', 'signer_dependencies', 'producer_bindings'}
    if set(state.get('required', [])) != required or set(state['properties']) != required:
        lint.fail(path, 'Agent state must carry the exact complete authority closure')
    if state.get('additionalProperties') is not False:
        lint.fail(path, 'Agent authority state must remain closed')
    if defs['agent_authority_state_evidence'].get('x-arkret-max-canonical-bytes') != 262144 or 'x-arkret-max-canonical-bytes' in state:
        lint.fail(path, 'complete evidence must have one 262144-byte canonical limit')
    bundle = defs['agent_accepted_authority_bundle']
    if set(bundle['required']) != {'realm_id', 'genesis_event', 'genesis_commit', 'authority_transitions', 'signer_histories'}:
        lint.fail(path, 'accepted authority bundle must not require an online assertion')
    if defs['agent_signer_dependency'].get('oneOf') is None or len(defs['agent_signer_dependency']['oneOf']) != 3:
        lint.fail(path, 'signer dependencies must retain the three closed sibling branches')
    carrier = defs['agent_producer_evidence']
    if set(carrier['required']) != {'authenticated_signer_evidence', 'agent_authority_state_evidence', 'controller_account_gate_attestation', 'authority_resolution'}:
        lint.fail(path, 'producer carrier must preserve ASRE/state/gate/history siblings')
    peer_path = ARTIFACTS / 'schemas/authority-commit-operations.schema.json'
    peer = load_json(lint, peer_path)['$defs']['peer_submit_request']
    if peer['properties'].get('producer_agent_evidence', {}).get('$ref') != './agent-authority-evidence.schema.json#/$defs/agent_producer_evidence':
        lint.fail(peer_path, 'formal peer ingress must reference Agent carrier')
    for branch in peer['oneOf'][2:]:
        if {'required': ['producer_agent_evidence']} not in branch['not']['anyOf']:
            lint.fail(peer_path, 'non-forwarding peer branches must forbid Agent evidence')
    asre_path = ARTIFACTS / 'schemas/authenticated-signer-resolution-evidence.schema.json'
    asre = load_json(lint, asre_path)['$defs']['base']
    if len(asre['properties']) != 6 or asre['additionalProperties'] is not False:
        lint.fail(asre_path, 'ASRE must remain six-member and closed')
    rules_path = ARTIFACTS / 'registry/contract-registry.json'
    rules = load_json(lint, rules_path)['did_evidence_boundary_registry']
    authority = rules['agent_authority_evidence_contract']
    if authority['state_fields'] != list(state['properties']) or authority['participation_in_state'] is not False:
        lint.fail(rules_path, 'Agent authority registry must match exact state order and exclude selection')
    runtime = rules['agent_participation_runtime_contract']
    if runtime['get_replace_role'] != 'controller' or runtime['runtime_selection_source'] != 'authenticated_session_overlay' or runtime['missing_current_selection'] != 'deny':
        lint.fail(rules_path, 'runtime selection role and current failure must remain explicit')
    for key in ('overlay_is_action_time_current', 'internal_channel_crosses_station_boundary', 'remote_selection_carrier', 'authority_evidence_grants_participation'):
        if runtime[key] is not False:
            lint.fail(rules_path, f'participation must not enable {key}')
    fixture_path = ARTIFACTS / 'fixtures/agent-participation-fixture.json'
    fixture = load_json(lint, fixture_path)
    cases = fixture['runtime_access_cases']
    for case in cases:
        actual = 'allow' if participation_allows(case) else 'deny'
        if case['expected'] != actual:
            lint.fail(fixture_path, f"{case['name']}: expected {case['expected']}, got {actual}")
    check_reply_configuration_contract(lint, runtime, fixture, fixture_path)
