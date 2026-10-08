"""Check explicit owned-Agent authority, current ceilings and management gates."""
import json
from .core import ARTIFACTS, Lint, load_json, schema_validator

INVARIANTS = {
    'default_self_service': True, 'explicit_confirmation': True,
    'all_grant_paths_current_controller_ceiling': True, 'current_management_gate': True,
    'agent_policy_payload_exact_cas': True,
    'parent_quota_shared_atomic': True, 'full_actor_identity': True, 'terminal_source': True,
    'issuer_revoke_without_capability': True, 'ineffective_exact_revision_read': True,
    'read_delivery_material_current_gate': True, 'global_cross_grant_deny': True,
    'source_controller_is_not_agent': True,
    'regrant_to_arbitrary_subject': False, 'revoked_record_auto_restores': False,
    'join_ban_stops_existing': False, 'management_allow_grants_authority': False,
    'unknown_means_no_ban': False, 'controller_private_selection_disclosed': False,
}

OPERATIONS = ['join', 'authorize', 'execute', 'read', 'deliver', 'publish', 'serve']
SUPPORTED = ['ak.event.read', 'ak.message.create', 'ak.message.redact.own',
             'ak.message.revise.own', 'ak.object.read', 'ak.object.read_content',
             'ak.object.read_history', 'ak.object.read_metadata', 'ak.reaction.add',
             'ak.reaction.remove', 'ak.strand.read']


def management_effect(case):
    """The fixture represents already priority-resolved policy documents."""
    effects = []
    for rule in case.get('management_rules', []):
        if case['operation'] not in rule['operations']:
            continue
        target = rule['target']
        if target['kind'] == 'controller' and target['account_id'] != case['controller_account_id']:
            continue
        if target['kind'] == 'agent' and target['account_id'] != case['agent_account_id']:
            continue
        if rule.get('actions') and case['action'] not in rule['actions']:
            continue
        effects.append(rule['effect'])
    for effect in ('deny', 'quarantine', 'require_review'):
        if effect in effects:
            return effect
    return 'allow'


def decide(case, contract):
    if case.get('accepted_identity') is True:
        return 'reuse_accepted'
    if case.get('signing_eligible') is not True or case.get('exact_account_binding') is not True:
        return 'deny'
    if case['operation'] == 'revoke':
        return 'allow' if all(case.get(k) is True for k in (
            'owned_source', 'original_issuer', 'target_present', 'exact_revision',
        )) else 'deny'
    if case.get('current_evidence') is not True or case.get('management_evidence') is not True:
        return 'pending'
    if case['operation'] == 'authorize' and (
        case['action'] not in contract['supported_actions']
        or case.get('explicit_confirmation') is not True
        or case.get('terminal_source') is not True
        or case.get('controller_is_agent') is True
    ):
        return 'deny'
    effect = management_effect(case)
    if effect != 'allow':
        return effect
    if case['operation'] == 'join':
        return 'allow' if all(case.get(k) is True for k in (
            'controller_join_active', 'agent_binding_valid', 'agent_action_gates',
        )) else 'deny'
    if not all(case.get(k) is True for k in (
        'controller_join_active', 'agent_binding_valid', 'controller_permission',
        'whole_allow_path', 'identity_conditions_preserved', 'scope_within_confirmation',
        'global_key_ceiling', 'agent_action_gates', 'parent_quota_available',
    )) or case.get('matched_global_deny') is True:
        return 'deny'
    if case['operation'] != 'join' and case.get('grant_terminal') is True:
        return 'deny'
    return 'allow'


def check_owned_agent_authority(lint: Lint) -> None:
    path = ARTIFACTS / 'registry/owned-agent-authority-registry.json'
    contract = load_json(lint, path)
    if contract.get('invariants') != INVARIANTS or contract.get('supported_actions') != SUPPORTED:
        lint.fail(path, 'owned Agent current authority, terminal source, quota and management invariants drift')
    if contract.get('management_operations') != OPERATIONS:
        lint.fail(path, 'Agent management operations must separate join, authorize, execute, read and deliver')
    catalog = load_json(lint, ARTIFACTS / 'registry/contract-registry.json')
    rows = {r['event_kind']: r for r in catalog['event_kind_registry']['event_kinds']}
    for kind in ('ak.capability.grant', 'ak.capability.revoke'):
        if rows[kind].get('admission') != 'capability_or_owned_agent':
            lint.fail(path, f'{kind} loses the owned Agent source or issuer-only withdrawal branch')
    grant = load_json(lint, ARTIFACTS / 'schemas/capability-grant.schema.json')
    payload = load_json(lint, ARTIFACTS / 'schemas/event-payload.schema.json')['$defs']['policy_set_state_payload']
    if payload.get('then') != {'required': ['expected_revision']} or payload.get('else') != {'not': {'required': ['expected_revision']}}:
        lint.fail(path, 'Agent Policy CAS must be required in its payload and forbidden for other families')
    condition = payload.get('if', {}).get('properties', {}).get('value', {})
    if condition.get('properties') != {'schema': {'const': 'ak.schema.policy.v1'}, 'policy_kind': {'enum': ['agent', 'applet']}} or set(condition.get('required', [])) != {'schema', 'policy_kind'}:
        lint.fail(path, 'Agent Policy CAS family discriminator drift')
    if payload.get('properties', {}).get('expected_revision', {}).get('oneOf') != [{'type': 'null'}, {'$ref': './typed-current-result.schema.json#/$defs/revision'}]:
        lint.fail(path, 'Agent Policy CAS must use the nullable exact typed current revision')
    ref = grant['$defs']['owned_agent_authority_ref']
    fields = {'kind', 'realm_id', 'controller_account_id', 'controller_join_event_id', 'agent_join_event_id'}
    if set(ref.get('required', [])) != fields or set(ref['properties']) != fields or ref.get('additionalProperties') is not False:
        lint.fail(path, 'owned Agent ref must pin exact accounts and both membership generations, not a current snapshot')
    fixture_path = ARTIFACTS / 'fixtures/agent-participation-fixture.json'
    fixture = load_json(lint, fixture_path)['owned_agent_authority_contract']
    cases = fixture.get('cases', [])
    required_names = set(fixture.get('required_case_names', []))
    mandatory = {
        'ordinary_member_no_grant_action', 'original_issuer_no_revoke_action',
        'revoke_after_leave_offline', 'revoked_record_does_not_restore',
        'new_confirmation_after_revoke', 'independent_agent_grant_parent_zero',
        'controller_ban_future_agent', 'join_ban_keeps_existing',
        'read_ban_existing_subscription', 'wrong_station_controller',
        'global_deny_other_parent', 'no_cross_grant_splice', 'own_message_wrong_author',
        'accepted_retry_after_revoke', 'unaccepted_retry_after_revoke',
        'owner_transfer_parent_zero', 'unknown_remote_delivery',
    }
    names = [c.get('name') for c in cases]
    if len(names) != len(set(names)) or set(names) != required_names or not mandatory <= required_names or len(names) < 50:
        lint.fail(fixture_path, 'owned Agent authority matrix omits a required source, revocation, read or management boundary')
    for case in cases:
        if case.get('expected') != decide(case, contract):
            lint.fail(fixture_path, f"owned Agent case {case['name']} decision drift")
    cas_cases = {
        'agent_policy_first_write_null', 'agent_policy_update_exact_revision',
        'agent_policy_missing_revision', 'agent_policy_malformed_revision',
        'non_agent_policy_revision_forbidden', 'non_agent_policy_revision_omitted',
    }
    if not cas_cases <= {item['name'] for item in fixture['schema_cases']}:
        lint.fail(fixture_path, 'Agent Policy CAS schema coverage is incomplete')
    for item in fixture['schema_cases']:
        validator = schema_validator(ARTIFACTS / item['schema_file'], item['fragment'])
        valid = not list(validator.iter_errors(json.loads(item['canonical_json'])))
        if valid is not item['valid']:
            lint.fail(fixture_path, f"owned Agent schema case {item['name']} expected {item['valid']}, got {valid}")
    quota = fixture['quota_sequence']
    counts, identities, verdicts = {}, set(), []
    for request in quota['requests']:
        key = (request['parent_grant'], request['controller_account'], request['window'])
        identity = request['event_id']
        if identity in identities:
            verdicts.append('reuse_accepted')
        elif counts.get(key, 0) >= quota['limit']:
            verdicts.append('deny')
        else:
            identities.add(identity)
            counts[key] = counts.get(key, 0) + 1
            verdicts.append('allow')
    if verdicts != quota['expected'] or len(counts) != 1:
        lint.fail(fixture_path, 'parent quota must share its original counter across controller and Agents, including retries')
