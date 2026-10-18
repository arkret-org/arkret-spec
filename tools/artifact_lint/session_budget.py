"""Execute abstract session-budget conformance cases, not production authority proofs."""

from __future__ import annotations

import calendar
import copy
import re
from datetime import datetime, timedelta

from .core import ARTIFACTS, SPEC_ROOT, Lint, load_json, read_text, schema_validator

FIXTURE = ARTIFACTS / 'fixtures/temporal-session-budget-fixture.json'
CATALOG = ARTIFACTS / 'registry/contract-registry.json'
SCHEMA = ARTIFACTS / 'schemas/grant-constraint.schema.json'
FIELDS = ('max_duration', 'max_session_duration', 'inactivity_timeout')
ACTIVITY_ACTIONS = [
    'ak.message.create', 'ak.message.revise', 'ak.message.revise.own',
    'ak.message.redact', 'ak.message.redact.own', 'ak.reaction.add',
    'ak.reaction.remove', 'ak.morph.create', 'ak.morph.update',
    'ak.morph.stage.set', 'ak.relation.create', 'ak.relation.update',
    'ak.relation.tombstone', 'ak.rsvp.set', 'ak.object.read_content',
    'ak.self.blob.resource.get.v1',
]
PREDICATE_CASES = {
    'grant_valid', 'grant_boundary', 'grant_after_boundary', 'grant_original_not_event_time',
    'grant_not_first_use', 'grant_not_before_does_not_reset', 'session_valid', 'session_boundary', 'refresh_keeps_start',
    'reconnect_keeps_start', 'restart_keeps_start', 'new_authenticated_session',
    'idle_initial_start', 'idle_valid', 'idle_boundary', 'idle_after_boundary',
    'all_budgets_valid', 'earliest_grant_deadline', 'earliest_session_deadline',
    'earliest_idle_deadline', 'missing_grant_facts', 'wrong_grant_source',
    'missing_session_facts', 'missing_activity_facts', 'wrong_evaluation_class', 'unverified_session_facts', 'wrong_account',
    'wrong_station', 'wrong_device', 'wrong_generation', 'wrong_audience',
    'wrong_issuer', 'wrong_lineage', 'agent_valid', 'wrong_agent_key',
    'agent_owner_idle_irrelevant', 'sessionless_session_neutral',
    'sessionless_idle_neutral', 'sessionless_grant_still_valid',
    'sessionless_grant_expired', 'missing_branch_not_sessionless',
    'unknown_branch_not_sessionless', 'clock_untrusted', 'clock_overlap',
    'clock_range_inside', 'clock_range_after', 'future_session_start',
    'future_activity', 'activity_before_start', 'calendar_month_clamp',
    'calendar_leap_year', 'calendar_components_order', 'elapsed_across_dst',
    'zero_budget', 'duration_overflow', 'known_expired_and_missing_session',
    'session_revoked', 'session_terminal', 'grant_revoked', 'action_mismatch',
}
LIFECYCLE_CASES = {
    'accepted_write', 'delivered_content', 'failed_write', 'failed_read',
    'unverified_outcome', 'heartbeat', 'refresh', 'background_scan',
    'background_subscribe', 'presence', 'read_receipt', 'notification_ack',
    'client_activity_claim', 'exact_replay', 'concurrent_monotonic',
    'late_activity', 'late_claimed_time', 'cross_account_activity',
    'cross_device_activity', 'cross_lineage_activity', 'restart_preserves',
    'restart_missing_state', 'revoke_then_activity', 'terminal_then_refresh',
    'new_session_after_auth', 'new_session_after_expiry', 'new_session_without_auth', 'same_lineage_reissue',
    'local_grant_failure_not_logout', 'absolute_expiry_before_update',
    'clock_rollback', 'untrusted_clock', 'agent_business_activity',
}
SCHEMA_CASES = {
    'duration_seconds', 'duration_calendar', 'duration_zero', 'duration_weeks',
    'duration_empty', 'duration_empty_time', 'duration_trailing_time',
    'duration_negative', 'duration_fraction', 'duration_compact',
}
EFFECTS = {'allow': None, 'deny': 'Denied', 'quarantine': 'Quarantined', 'require_review': 'RequiresReview'}
DURATION = re.compile(
    r'^P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)W)?(?:(\d+)D)?'
    r'(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$'
)


def instant(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z', value):
        raise ValueError('noncanonical verification timestamp')
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def add_duration(anchor, duration):
    match = DURATION.fullmatch(duration)
    if match is None or not any(value is not None for value in match.groups()) or duration.endswith('T'):
        raise ValueError('invalid budget duration')
    years, months, weeks, days, hours, minutes, seconds = (int(value or 0) for value in match.groups())
    absolute_month = anchor.year * 12 + anchor.month - 1 + years * 12 + months
    year, month_zero = divmod(absolute_month, 12)
    month = month_zero + 1
    anchor = anchor.replace(year=year, month=month, day=min(anchor.day, calendar.monthrange(year, month)[1]))
    return anchor + timedelta(weeks=weeks, days=days, hours=hours, minutes=minutes, seconds=seconds)


def and3(values):
    return 'no_match' if 'no_match' in values else 'unknown' if 'unknown' in values else 'match'


def interval(anchor, duration, clock):
    try:
        if clock.get('trusted') is not True:
            return 'unknown'
        start, low, high = instant(anchor), instant(clock['earliest']), instant(clock['latest'])
        deadline = add_duration(start, duration)
        if low > high or low < start:
            return 'unknown'
        return 'match' if high < deadline else 'no_match' if low >= deadline else 'unknown'
    except (KeyError, TypeError, ValueError, OverflowError):
        return 'unknown'


def predicate(case):
    constraint, context, facts = case['constraint'], case['context'], case['facts']
    if constraint.get('applies_to_actions') and context['action'] not in constraint['applies_to_actions']:
        return 'not_applicable'
    declared_class = constraint.get('evaluation_class')
    if declared_class and any(key in constraint for key in FIELDS[1:]) and declared_class != 'external':
        return 'unknown'
    if declared_class and 'max_duration' in constraint and declared_class not in ('realm_state', 'external'):
        return 'unknown'
    results = []
    if 'max_duration' in constraint:
        grant = facts.get('grant', {})
        if grant.get('verified') is True and grant.get('id') == context['grant_id']:
            results.append(interval(grant.get('accepted_at'), constraint['max_duration'], case['clock']))
        else:
            results.append('unknown')
    if any(key in constraint for key in FIELDS[1:]):
        branch = context.get('auth_branch') if context.get('auth_branch_verified') is True else None
        if branch == 'registered_sessionless':
            return and3(results) if results else 'not_applicable'
        session = facts.get('session', {})
        if branch != 'session_bound' or session.get('verified') is not True or session.get('binding') != context.get('binding'):
            results.append('unknown')
        else:
            try:
                start = instant(session['started_at'])
                activity = instant(session.get('last_activity_at') or session['started_at'])
                invalid = activity < start or instant(case['clock']['earliest']) < activity
            except (KeyError, TypeError, ValueError):
                invalid = True
            if invalid:
                results.append('unknown')
            else:
                if 'max_session_duration' in constraint:
                    results.append(interval(session['started_at'], constraint['max_session_duration'], case['clock']))
                if 'inactivity_timeout' in constraint:
                    results.append('unknown' if 'last_activity_at' not in session else interval(session['last_activity_at'] or session['started_at'], constraint['inactivity_timeout'], case['clock']))
    return and3(results)


def verdict(result, effect, context, unrestricted=False):
    if context.get('authentication_active') is not True:
        return 'Denied'
    if context.get('authorization_source_active') is not True:
        return 'Allowed' if unrestricted else 'Unsatisfied'
    if effect != 'allow' and result in ('match', 'unknown'):
        return EFFECTS[effect]
    if effect == 'allow' and result not in ('match', 'not_applicable') and not unrestricted:
        return 'Unsatisfied'
    return 'Allowed'


def lifecycle(initial, steps):
    state = copy.deepcopy(initial)
    outcomes = []
    for step in steps:
        updated = False
        now = instant(step['owner_time'])
        previous = instant(state.get('last_activity_at') or state['started_at'])
        trusted = step.get('clock_trusted') is True and now >= previous and state.get('verified') is True
        if trusted and state['active']:
            policy = state.get('policy', {})
            for field, anchor in [('max_session_duration', state['started_at']), ('inactivity_timeout', state.get('last_activity_at') or state['started_at'])]:
                if field in policy and now >= add_duration(instant(anchor), policy[field]):
                    state['active'] = False
        transition = step['transition']
        if transition == 'revoke':
            state['active'] = False
        elif transition == 'restart' and step.get('restored_verified') is not True:
            state['verified'] = False
        elif transition == 'issue' and step.get('verified_issue') is True and trusted and step['new_binding']['session_lineage'] != state['binding']['session_lineage']:
            state.update(binding=copy.deepcopy(step['new_binding']), started_at=step['owner_time'], last_activity_at=None, active=True, seen_operations=[])
        elif transition == 'activity' and trusted and state['active'] and step.get('verified_success') is True and step.get('binding') == state['binding'] and step.get('action') in ACTIVITY_ACTIONS and step['operation_identity'] not in state['seen_operations']:
            state['last_activity_at'] = step['owner_time']
            state['seen_operations'].append(step['operation_identity'])
            updated = True
        outcomes.append({'activity_updated': updated, 'lineage_usable': trusted and state['active'] and state['verified']})
    return state, outcomes


def check_session_budget(lint: Lint) -> None:
    data = load_json(lint, FIXTURE)
    catalog = load_json(lint, CATALOG)
    try:
        contract = catalog['capability_action_registry']['constraint_evaluation_contract']['session_budget_contract']
        expected = {
            'anchors': dict(zip(FIELDS, ['original_authorization_acceptance', 'issuer_session_start', 'issuer_last_qualifying_activity_or_session_start'])),
            'session_owner': 'account_authority_issuer_ledger',
            'binding': ['issuer', 'account_with_station', 'audience', 'holder_with_generation', 'session_lineage'],
            'refresh_reconnect_restart': 'preserve_anchors',
            'sessionless': 'verified_operation_auth_branch_only_session_predicates_neutral',
            'duration_arithmetic': 'utc_calendar_months_clamp_then_elapsed_components',
            'valid_interval': 'anchor_inclusive_deadline_exclusive',
            'clock_uncertainty': 'unknown_on_boundary_overlap_no_skew_grace',
            'evaluation_class': {'max_duration': 'realm_state_or_external_by_authorization_owner', 'session_or_idle': 'external'},
            'activity_actions': ACTIVITY_ACTIONS,
            'activity_time': 'issuer_acceptance_after_verified_success',
            'activity_order': 'check_current_state_before_monotonic_update',
            'replay': 'first_logical_success_only',
            'local_failure': 'authorization_path_only_not_global_logout',
            'issuer_expiry': 'terminal_lineage_no_resurrection',
            'fixture_ref': 'fixtures/temporal-session-budget-fixture.json',
            'test_material_scope': 'abstract_verified_context_not_internal_receipt_or_production_consumer',
        }
        for key, value in expected.items():
            if contract.get(key) != value:
                lint.fail(CATALOG, 'session budget contract drift: ' + key)
        registered_actions = {row['action'] for row in catalog['capability_action_registry']['actions']}
        if not set(ACTIVITY_ACTIONS) <= registered_actions:
            lint.fail(CATALOG, 'activity action is not registered')
        profiles = load_json(lint, ARTIFACTS / 'profiles/conformance-profiles.json')
        if FIXTURE.name not in profiles['profile_requirements']['ak.profile.core_event_store.v1']['required_fixtures']:
            lint.fail(FIXTURE, 'core profile must require session budget fixture')
        validator = schema_validator(SCHEMA, '')
        cases = data['predicate_cases']
        if {row['name'] for row in cases} != PREDICATE_CASES or len(cases) != len(PREDICATE_CASES):
            lint.fail(FIXTURE, 'session predicate/effect matrix incomplete or duplicated')
        for case in cases:
            if list(validator.iter_errors(case['constraint'])):
                lint.fail(FIXTURE, 'invalid budget constraint: ' + case['name'])
            result = predicate(case)
            if result != case['expected_predicate'] or set(case['expected_by_effect']) != set(EFFECTS):
                lint.fail(FIXTURE, 'session predicate or effect coverage mismatch: ' + case['name'])
            for effect in EFFECTS:
                actual = [verdict(result, effect, case['context']), verdict(result, effect, case['context'], True)]
                if actual != case['expected_by_effect'].get(effect):
                    lint.fail(FIXTURE, 'session budget computation mismatch: ' + case['name'] + '/' + effect)
        transitions = data['lifecycle_cases']
        if {row['name'] for row in transitions} != LIFECYCLE_CASES or len(transitions) != len(LIFECYCLE_CASES):
            lint.fail(FIXTURE, 'session lifecycle cases incomplete or duplicated')
        for case in transitions:
            state, outcomes = lifecycle(case['initial'], case['steps'])
            if state != case['expected_state'] or outcomes != case['expected_outcomes']:
                lint.fail(FIXTURE, 'session lifecycle computation mismatch: ' + case['name'])
        schemas = data['schema_cases']
        if {row['name'] for row in schemas} != SCHEMA_CASES or len(schemas) != len(SCHEMA_CASES):
            lint.fail(FIXTURE, 'duration schema cases incomplete or duplicated')
        for case in schemas:
            for field in FIELDS:
                instance = {'constraint_kind': 'temporal', 'effect': 'allow', field: case['duration']}
                if (not list(validator.iter_errors(instance))) != case['valid']:
                    lint.fail(FIXTURE, 'budget duration schema mismatch: ' + case['name'] + '/' + field)
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        lint.fail(FIXTURE, 'malformed session budget conformance input: ' + str(exc))
    prose = read_text(SPEC_ROOT / 'zh/authz/constraint-schema.md')
    for marker in ['#### 3.2.1 ', '#### 3.2.2 ', '#### 3.2.3 ', 'predicate_verified_session_budget', 'budget_interval', FIXTURE.name]:
        if marker not in prose:
            lint.fail(FIXTURE, 'missing normative session budget rule: ' + marker)
