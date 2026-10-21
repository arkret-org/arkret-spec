"""Execute registered-unit and audited Watch read protocol contracts."""
from __future__ import annotations

import copy
import json

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from .core import ARTIFACTS, Lint, load_json, schema_format_checker

CONTRACT = ARTIFACTS / 'registry/contract-registry.json'
SCHEMA = ARTIFACTS / 'schemas/authority-commit-operations.schema.json'
AUDIT_SCHEMA = ARTIFACTS / 'schemas/watch-audit-operations.schema.json'
FIXTURE = ARTIFACTS / 'fixtures/registered-atomic-unit-and-watch-audit-fixture.json'
SELF = 'ak.self.strand.watch.command.audit_read.v1'
PEER = 'ak.peer.strand.watch.command.audit_read.v1'
UNIT_KINDS = {'ordinary_realm_bootstrap', 'direct_conversation_founding', 'membership_compensation', 'audit_paired_event'}
UNIT_REQUIRED = {'watch_pair_accepted', 'circle_manage_pair_accepted', 'circle_others_pair_accepted', 'missing_audit', 'duplicate_audit', 'reverse_order', 'wrong_writer', 'wrong_target', 'wrong_pair_ref', 'wrong_scope', 'wrong_producer', 'missing_audit_capability', 'cas_conflict', 'muted_by_other', 'public_by_other', 'clear_by_other', 'unregistered_kind', 'raw_atomic_batch', 'exact_unit_replay', 'changed_unit_replay', 'ordinary_replication_pair_fragment', 'committed_pair_replication', 'replica_missing_source_slot', 'cross_stream_unit', 'device_proof_missing', 'agent_controller_revoked'}
READ_REQUIRED = {'audited_never_written', 'audited_written_null', 'audit_capability_missing', 'read_capability_missing', 'others_is_not_read', 'nonmember_without_circle_audit', 'scoped_circle_auditor', 'wrong_scope_read', 'wrong_auditor_station', 'governor_unverified', 'namespace_incomplete', 'audit_admission_failure', 'replay_returns_frozen_value', 'old_audit_cannot_query_new_value', 'changed_audit_request', 'preaccepted_ticket_rejected', 'replay_material_missing', 'delivery_revoked', 'agent_content_ceiling_denied', 'handoff_requires_new_audit', 'network_loss_keeps_authorized_audit'}


def producer(event: dict) -> dict:
    return event.get('executed_by', event['actor_id'])


def evaluate_unit(value: dict) -> str:
    """Abstract authenticated-state oracle, not a PG or signature implementation."""
    if value.get('unit_kind') != 'audit_paired_event' or value.get('raw_atomic'):
        return 'schema_violation'
    events = value['events']
    if len(events) != 2:
        return 'failed_precondition'
    business, audit = events
    pairs = {'ak.strand.watch.set': ('watch_set_others', 'watcher_actor_id', 'strand_id'), 'ak.circle.member.state': ('circle_member_set_others', 'member_id', 'circle_id')}
    if business['kind'] not in pairs or audit['kind'] != 'ak.audit.accessed':
        return 'failed_precondition'
    access, actor_key, target_key = pairs[business['kind']]
    bp, ap = business['payload'], audit['payload']
    refs = [ref for ref in audit.get('semantic_refs', []) if ref.get('role') == 'audit_pair']
    if (
        business['actor_id'] == bp[actor_key]
        or business['actor_id'] != audit['actor_id']
        or producer(business) != producer(audit)
        or business['producer_proof']['verification_method'] != audit['producer_proof']['verification_method']
        or business['realm_id'] != audit['realm_id']
        or business['scope_ref'] != audit['scope_ref']
        or ap['access_kind'] != access
        or ap['writer_actor_id'] != business['actor_id']
        or ap['target_actor_id'] != bp[actor_key]
        or ap['target_ref'] != bp[target_key]
        or ap['paired_event_id'] != business['event_id']
        or refs != [{'id': business['event_id'], 'role': 'audit_pair', 'critical': True}]
        or any(ref.get('id') == audit['event_id'] for ref in business.get('semantic_refs', []))
        or value.get('cross_stream')
    ):
        return 'failed_precondition'
    if business['kind'] == 'ak.strand.watch.set' and (bp['level'] not in {'mentions_only', 'participating', 'all'} or bp.get('level_public') is True):
        return 'failed_precondition'
    if not value['business_authorized'] or not value['audit_authorized'] or not value['cas_matches'] or not value['controller_current']:
        return 'failed_precondition'
    if value['transport'] == 'authority_forward' and (not value['fresh_producer_evidence'] or not value.get('both_slot_authorizations_match', True)):
        return 'authentication_rejected'
    if value['transport'] == 'committed_replication':
        return 'failed_precondition'
    if value['transport'] == 'registered_atomic_unit':
        return 'stored' if value['source_slots_complete'] and value['source_commits_consecutive'] and value['both_slots_disclosable'] else 'revision_unavailable'
    if value.get('event_fence_conflict'):
        return 'duplicate_conflict'
    if value['replay'] == 'changed':
        return 'duplicate_conflict'
    if value['replay'] == 'exact':
        return 'original_outcome_no_new_effect'
    if value.get('fault_at'):
        return 'rollback_zero_writes'
    return 'accepted_two_commits'


def evaluate_read(value: dict) -> str:
    """Abstract audit/authorization/replay cut; no live read or cryptographic claim."""
    if not value['auditor_station_matches']:
        return 'not_found'
    if not value['governor_verified']:
        return 'revision_unavailable'
    if not value['read_authorized'] or not value['audit_authorized'] or not value['realm_member'] or not (value['scope_member'] or value['scoped_circle_audit']):
        return 'not_found'
    if not value['target_scope_matches']:
        return 'not_found'
    if not value['namespace_complete'] or not value['replay_material_available'] or value['higher_generation_observed']:
        return 'revision_unavailable'
    if value['changed_request'] or value['preaccepted_without_read_binding']:
        return 'duplicate_conflict'
    if not value['audit_admission_allowed']:
        return 'failed_precondition'
    if not value['delivery_current'] or not value['agent_content_allowed']:
        return 'authorized_audit_committed_result_withheld'
    if value['network_lost']:
        return 'authorized_audit_committed_response_lost'
    if value['replay']:
        return 'original_frozen_result_no_new_audit_or_query'
    return 'audit_commit_and_' + value['presence']


def evaluate_response(value: dict) -> str:
    """Bind an already verified response to its exact request and frozen audit cut."""
    event = value['request']; outcome = value['outcome']
    commit = outcome['audit_commit']; current = outcome['current']
    expected_head = {key: commit[key] for key in ['stream_ref', 'stream_position', 'commit_id']}
    expected_selector = {'kind': 'strand_watch', 'strand_id': event['payload']['target_ref'], 'watcher_actor_id': event['payload']['target_actor_id']}
    selector = current.get('selector', current.get('result', {}).get('selector'))
    if commit['event_ref'] != event['event_id'] or commit['realm_id'] != event['realm_id'] or commit['stream_ref'] != event['scope_ref'] or current['realm_id'] != commit['realm_id'] or current['governance_generation'] != commit['governance_generation'] or current['stream_head'] != expected_head or selector != expected_selector:
        return 'revision_unavailable'
    if current['status'] == 'current':
        result = current['result']
        if result['source_stream_ref'] != commit['stream_ref'] or result['revision']['stream_position'] > commit['stream_position']:
            return 'revision_unavailable'
    if value['replay'] and outcome != value['frozen_outcome']:
        return 'revision_unavailable'
    return 'verified_original_audit_cut'


def case_input(fixture: dict, case: dict, family: str) -> dict:
    value = copy.deepcopy(fixture[family + '_basis'])
    value.update(copy.deepcopy(case['input']))
    return value


def contract_errors(catalog: dict, schema: dict, audit_schema: dict, fixture: dict) -> list[str]:
    errors = []
    registry = catalog.get('atomic_unit_registry', {})
    rows = registry.get('units', [])
    if len(rows) != 4 or {r.get('unit_kind') for r in rows} != UNIT_KINDS:
        errors.append('Closed registered-unit allowlist is incomplete or contains an arbitrary unit')
    for row in rows:
        if not all(row.get(k) is True for k in ['same_governor', 'same_realm_stream', 'all_or_nothing', 'one_commit_per_event', 'consecutive_commits']):
            errors.append('Atomic scope/finality invariant removed: ' + str(row.get('unit_kind')))
        if not row.get('request_schema_ref') or not row.get('replay_fence'):
            errors.append('Typed request/replay binding missing')
    defs = schema['$defs']
    unit = defs.get('audit_paired_event_unit_submission', {})
    slots = unit.get('properties', {}).get('events', {})
    if unit.get('additionalProperties') is not False or unit.get('required') != ['unit_kind', 'events'] or slots.get('minItems') != 2 or slots.get('maxItems') != 2 or slots.get('items') is not False or slots.get('prefixItems') != [{'$ref':'#/$defs/audit_paired_business_submission'}, {'$ref':'#/$defs/audit_paired_access_submission'}]:
        errors.append('Audit pair must be exactly two closed typed ordered slots')
    operations = {r['operation_id']:r for r in catalog['operation_registry']['operations']}
    for op_id,request in [(SELF,'watch_audit_read_request'),(PEER,'peer_watch_audit_read_request')]:
        op = operations.get(op_id, {})
        if op.get('request_schema_ref') != 'schemas/watch-audit-operations.schema.json#/$defs/' + request or op.get('response_schema_ref') != 'schemas/watch-audit-operations.schema.json#/$defs/watch_audit_read_outcome' or op.get('durable_effect',{}).get('kind') != 'event_log' or op.get('canonical_hash_input') != 'full_body' or op.get('max_canonical_body_bytes') != 1048576:
            errors.append('Side-effecting audited read operation/schema/replay/budget contract drift: ' + op_id)
    if operations.get(PEER,{}).get('auth_requirements',{}).get('service_signature',{}).get('bearer_only_allowed') is not False:
        errors.append('Peer audited read must require S2S signature')
    req = audit_schema['$defs']['watch_audit_read_request']
    if req.get('required') != ['audit_submission'] or set(req.get('properties',{})) != {'audit_submission'} or req.get('additionalProperties') is not False:
        errors.append('Audited read selector must derive only from the signed audit Event')
    manageable = next(r for r in catalog['capability_action_registry']['actions'] if r['action']=='ak.circle.member.manage')
    if 'audit_pair_required' not in manageable.get('required_evaluator_checks',[]):
        errors.append('Circle member.manage must not bypass audit pairing')
    peer = defs['peer_submit_request']
    branches = peer.get('oneOf', [])
    forwarding = [b for b in branches if b.get('properties', {}).get('branch', {}).get('const') == 'authority_forward']
    if len(branches) != 5 or len(forwarding) != 3 or not any(b.get('required') == ['branch', 'atomic_submission', 'atomic_producer_evidence'] for b in forwarding):
        errors.append('Closed typed first-admission peer branches drift')
    slot_proofs = defs.get('audit_pair_producer_evidence', {})
    if slot_proofs.get('minItems') != 2 or slot_proofs.get('maxItems') != 2 or slot_proofs.get('items') is not False:
        errors.append('Atomic first admission must retain exactly two slot-bound producer closures')
    peer_read = audit_schema['$defs']['peer_watch_audit_read_request']
    if peer_read.get('oneOf') != [{'required':['producer_device_evidence']},{'required':['producer_agent_evidence']}]:
        errors.append('Peer audited read must carry exactly one actual producer proof')
    audit_contract = registry.get('audit_read', {})
    circle = audit_contract.get('circle_authorization', {})
    if audit_contract.get('producer_classes') != ['account_device','agent_runtime'] or circle != {'current_parent_realm_membership':True,'effective_circle_member_or_scoped_circle_audit':True,'nonmember_exception':'watch_audit_read_command_audit_event_only','no_membership_content_history_or_mls_key_grant':True}:
        errors.append('Audited-read producer/Circle exception boundary drift')
    if rows[-1].get('replay_fence') != 'full_canonical_unit_and_single_use_business_event_id_and_audit_event_id':
        errors.append('Audit pair must fence each Event ID against changed pairing')
    response_cases = fixture.get('response_cases', [])
    if len(response_cases) < 11:
        errors.append('Missing exact response and frozen replay binding vectors')
    for case in response_cases:
        if evaluate_response(case['input']) != case['expected']:
            errors.append('Response binding verdict drift: ' + case['name'])
    for family,required,oracle in [('unit',UNIT_REQUIRED,evaluate_unit),('read',READ_REQUIRED,evaluate_read)]:
        cases = fixture.get(family + '_cases', [])
        names = [c['name'] for c in cases]
        if len(names) != len(set(names)) or not required.issubset(names):
            errors.append('Required ' + family + ' coverage is missing or duplicated')
        for case in cases:
            if oracle(case_input(fixture,case,family)) != case['expected']:
                errors.append('Verdict drift: ' + case['name'])
    return errors


def check_registered_atomic_units(lint: Lint) -> None:
    catalog = load_json(lint,CONTRACT);schema = load_json(lint,SCHEMA);audit_schema = load_json(lint,AUDIT_SCHEMA);fixture = load_json(lint,FIXTURE)
    for error in contract_errors(catalog,schema,audit_schema,fixture):lint.fail(FIXTURE,error)
    resources=[]
    for path in (ARTIFACTS/'schemas').glob('*.json'):
        doc=json.loads(path.read_text(encoding='utf-8'));resource=Resource.from_contents(doc,default_specification=DRAFT202012);resources.extend([(path.as_uri(),resource),(doc.get('$id',path.as_uri()),resource)])
    registry=Registry().with_resources(resources)
    cases=fixture.get('schema_validation_cases',[])
    if len(cases)<12:lint.fail(FIXTURE,'Missing closed carrier schema vectors')
    for case in cases:
        file,fragment=case['schema_ref'].split('#');doc=json.loads((ARTIFACTS/file).read_text(encoding='utf-8'))
        validator=Draft202012Validator({'$ref':doc['$id']+'#'+fragment},registry=registry,format_checker=schema_format_checker())
        errors=list(validator.iter_errors(case['instance']))
        if (not errors)!=case['expect_valid']:lint.fail(FIXTURE,'Wire schema verdict drift: '+case['name']+ ('; '+errors[0].message[:140] if errors else ''))
