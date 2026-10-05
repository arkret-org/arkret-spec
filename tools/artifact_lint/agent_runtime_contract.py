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


def check_agent_runtime_contract(lint: Lint) -> None:
    path = ARTIFACTS / 'schemas/agent-authority-evidence.schema.json'
    schema = load_json(lint, path)
    defs = schema['$defs']
    state = defs['agent_authority_state']
    required = {'authority_id', 'agent_id', 'source_commit_id', 'pcr_genesis_event',
                'key_authorization_event', 'authorization', 'key_state_witness',
                'agent_lifecycle_witness', 'commit_lineages', 'commits',
                'authority_bundle', 'signer_dependencies'}
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
    cases = load_json(lint, fixture_path)['runtime_access_cases']
    for case in cases:
        actual = 'allow' if participation_allows(case) else 'deny'
        if case['expected'] != actual:
            lint.fail(fixture_path, f"{case['name']}: expected {case['expected']}, got {actual}")
