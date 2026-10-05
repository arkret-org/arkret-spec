"""Close historical signer queries over exact authority-commit coordinates."""

from __future__ import annotations

from typing import Any

from .core import ARTIFACTS, ROOT, SPEC_ROOT, Lint, load_json, read_text


SCHEMA = ARTIFACTS / "schemas" / "signer-key-operations.schema.json"
AUTHORITY_SCHEMA = ARTIFACTS / "schemas" / "authority-commit-operations.schema.json"
ACCOUNT_SYNC_SCHEMA = ARTIFACTS / "schemas" / "account-subscribe-frame.schema.json"
INVITE_SCHEMA = ARTIFACTS / "schemas" / "invite-delivery-request.schema.json"
CONTRACT = ARTIFACTS / "registry" / "contract-registry.json"
ERROR_MAPPING = ARTIFACTS / "registry" / "operations-error-mapping.json"
VECTORS = ARTIFACTS / "registry" / "vector-registry.json"
FIXTURE = ARTIFACTS / "fixtures" / "signer-key-historical-coordinate-fixture.json"
SERVER_PROSE = SPEC_ROOT / "zh" / "sync" / "server-trusted-results.md"
SYNC_PROSE = SPEC_ROOT / "zh" / "sync" / "client-sync.md"
VECTOR_PROSE = SPEC_ROOT / "zh" / "conformance" / "conformance-vectors.md"
RUNNER = ROOT / "tools" / "artifact_lint" / "runner.py"

OPERATION_ID = "ak.self.signer_keys.read.resolve.v1"
VECTOR_ID = "ak.vector.signer_key.historical_commit_coordinate.v1"
COMMITTED_REF = "./authority-commit-operations.schema.json#/$defs/committed_event_ref"
HISTORICAL_DEFS = ("historical_account_device_selector", "historical_agent_selector")
CURRENT_DEFS = ("current_account_device_selector", "current_agent_selector")
SELF_SUBMISSION_RULE = {'coordinate_source': 'frozen_complete_signed_request_event_and_bound_accepted_outcome_original_commit',
 'binding': 'same_accepted_station_authenticated_full_account_and_local_session_epoch',
 'correlation': 'validated_request_outcome_branch_and_each_aggregate_slot',
 'checks': ['event_and_commit_content_ids', 'event_ref_realm_scope_stream_position'],
 'advances_stream_head_or_floor': False,
 'requires_pcr_history_scan': False,
 'historical_key_authorization': 'independent_complete_original_authorization_coordinates_and_proof',
 'pcr_human_query': {'recipient': 'authenticated_full_account_equals_actual_human_producer_full_account',
                     'provenance': 'original_same_station_self_admission_transaction_and_exact_target',
                     'human_binding': 'original_accepted_full_account_binding',
                     'agent_genesis_binding': 'original_accepted_provision_complete_controller_account_and_original_delegation_same_transaction',
                     'fact': 'complete_immutable_original_historical_authorization_and_proof',
                     'current_authentication_required': True,
                     'foreign_or_sibling_admission_allowed': False,
                     'current_row_fact_backfill_allowed': False,
                     'grants_pcr_history_or_membership': False,
                     'changes_ordinary_received_floor': False,
                     'missing_or_conflicting_fact': 'existing_unavailable_without_current_query_fallback'}}
SELF_SUBMISSION_FLOWS = {'controller_human_agent_pcr_genesis_resolves_from_original_provision_delegation_transaction', 'human_pcr_self_submission_resolves_from_original_self_admission_without_scan', 'self_submission_checks_each_aggregate_slot_without_advancing_head_or_floor', 'historical_authorization_revoked_later_keeps_original_fact_without_current_authority'}

NEGATIVE_CASES = {
    'self_submission_wrong_slot_or_foreign_commit',
    'self_submission_wrong_station_account_or_epoch',
    'self_submission_sibling_or_foreign_admission',
    'self_submission_non_human_actual_producer',
    'self_submission_registration_missing_original_authorization',
    'self_submission_agent_current_row_backfills_provision_or_delegation',
    'self_submission_missing_complete_historical_authorization',
    'self_submission_advances_head_or_floor',
    'self_submission_requires_pcr_history_scan',
    "changed_projection_short_circuits_historical_query",
    "agent_reply_waits_for_unrelated_account_frame_or_reload",
    "historical_selector_uses_bare_event_id",
    "request_realm_differs_from_selector_stream_realm",
    "row_event_id_differs_from_commit_event_ref",
    "selector_commit_id_differs_from_verified_row",
    "selector_stream_ref_differs_from_verified_row",
    "selector_stream_position_differs_from_verified_row",
    "target_and_authorization_ref_forced_equal",
    "current_projection_nested_event_used_as_coordinate",
    "array_index_used_for_result_correlation",
    "redacted_row_used_for_producer_signature_verification",
    "late_response_for_another_recipient_account",
    "bare_event_id_downgraded_to_current_query",
}


def _find(rows: Any, field: str, value: str) -> dict[str, Any] | None:
    if not isinstance(rows, list):
        return None
    matches = [row for row in rows if isinstance(row, dict) and row.get(field) == value]
    return matches[0] if len(matches) == 1 else None


def _defs(document: Any) -> dict[str, Any]:
    return document.get("$defs", {}) if isinstance(document, dict) else {}


def check_signer_key_historical_coordinate(lint: Lint) -> None:
    _check_foreign_human_delivery_shape(lint)
    _check_foreign_human_crypto_transcript(lint)
    schema = load_json(lint, SCHEMA)
    definitions = _defs(schema)
    if not definitions:
        return

    for name in HISTORICAL_DEFS:
        selector = definitions.get(name)
        required = selector.get("required") if isinstance(selector, dict) else None
        properties = selector.get("properties") if isinstance(selector, dict) else None
        if not isinstance(required, list) or "committed_event_ref" not in required or "event_id" in required:
            lint.fail(SCHEMA, f"{name} must require committed_event_ref and reject bare event_id")
        committed = properties.get("committed_event_ref") if isinstance(properties, dict) else None
        if not isinstance(committed, dict) or committed.get("$ref") != COMMITTED_REF or "event_id" in properties:
            lint.fail(SCHEMA, f"{name} must use the canonical committed_event_ref only")

    for name in CURRENT_DEFS:
        selector = definitions.get(name)
        properties = selector.get("properties") if isinstance(selector, dict) else None
        if not isinstance(properties, dict) or "committed_event_ref" in properties or "event_id" in properties:
            lint.fail(SCHEMA, f"{name} must not accept any historical coordinate")

    key = definitions.get("query_signing_key")
    required = key.get("required") if isinstance(key, dict) else None
    properties = key.get("properties") if isinstance(key, dict) else None
    if required != ["public_key_b64u", "authorization_ref", "revision", "governance_generation"]:
        lint.fail(SCHEMA, "query_signing_key must require key bytes, independent authorization ref, revision and generation")
    if not isinstance(properties, dict) or properties.get("authorization_ref", {}).get("$ref") != COMMITTED_REF:
        lint.fail(SCHEMA, "query_signing_key authorization_ref must be a committed_event_ref")
    revision = properties.get("revision") if isinstance(properties, dict) else None
    if not isinstance(revision, dict) or revision.get("required") != ["commit_id", "stream_position"] or revision.get("additionalProperties") is not False:
        lint.fail(SCHEMA, "query_signing_key revision must be the closed current commit coordinate")
    if not isinstance(properties, dict) or properties.get("governance_generation", {}).get("minimum") != 0:
        lint.fail(SCHEMA, "query_signing_key must bind a non-negative governance_generation")

    for name in ("historical_account_device_outcome", "historical_agent_outcome"):
        outcome = definitions.get(name)
        ref = outcome.get("properties", {}).get("key", {}).get("$ref") if isinstance(outcome, dict) else None
        if ref != "#/$defs/query_signing_key":
            lint.fail(SCHEMA, f"{name} must carry the complete query_signing_key")
    if "historical_device_signing_key" in definitions:
        lint.fail(SCHEMA, "historical device results must not retain a key-only partial-success shape")

    authority = load_json(lint, AUTHORITY_SCHEMA)
    authority_defs = _defs(authority)
    committed = authority_defs.get("committed_event_ref")
    if not isinstance(committed, dict) or committed.get("required") != ["event_id", "commit_id", "stream_ref", "stream_position"]:
        lint.fail(AUTHORITY_SCHEMA, "committed_event_ref must remain the closed four-coordinate reference")
    scan = authority_defs.get("stream_scan_outcome")
    scan_items = scan.get("properties", {}).get("committed_events", {}).get("items", {}).get("$ref") if isinstance(scan, dict) else None
    if scan_items != "#/$defs/stream_row":
        lint.fail(AUTHORITY_SCHEMA, "per-stream scan must continue to carry canonical stream_row values")
    account_sync = load_json(lint, ACCOUNT_SYNC_SCHEMA)
    realm_sync = _defs(account_sync).get("realm_sync_entry")
    account_items = realm_sync.get("properties", {}).get("committed_events", {}).get("items", {}).get("$ref") if isinstance(realm_sync, dict) else None
    if account_items != "./authority-commit-operations.schema.json#/$defs/stream_row":
        lint.fail(ACCOUNT_SYNC_SCHEMA, "account subscribe must continue to carry the same canonical stream_row")

    contract = load_json(lint, CONTRACT)
    registry = contract.get("operation_registry") if isinstance(contract, dict) else None
    operation = _find(registry.get("operations") if isinstance(registry, dict) else None, "operation_id", OPERATION_ID)
    notes = operation.get("notes") if isinstance(operation, dict) else None
    for marker in ("committed_event_ref", "stream_row", "may differ", "without current-query fallback"):
        if not isinstance(notes, str) or marker not in notes:
            lint.fail(CONTRACT, f"signer-key operation notes are missing {marker!r}")

    consumption = contract.get("did_evidence_boundary_registry", {}).get("governance_result_consumption_contract", {})
    if consumption.get("historical_producer_coordinates") != "original_authorized_self_stream_row_or_bound_self_submission_exact_committed_event_ref":
        lint.fail(CONTRACT, "historical source contract must retain stream rows and bound self submissions")
    if consumption.get("self_submission_historical_source") != SELF_SUBMISSION_RULE:
        lint.fail(CONTRACT, "self submission source must preserve exact binding, immutable authorization and restricted PCR rules")

    mappings = load_json(lint, ERROR_MAPPING)
    error_row = _find(mappings.get("operations") if isinstance(mappings, dict) else None, "operation_id", OPERATION_ID)
    error_description = error_row.get("description") if isinstance(error_row, dict) else None
    for marker in ("committed_event_ref", "authorization coordinates", "current query"):
        if not isinstance(error_description, str) or marker not in error_description:
            lint.fail(ERROR_MAPPING, f"signer-key error mapping is missing {marker!r}")

    vectors = load_json(lint, VECTORS)
    vector = _find(vectors.get("vectors") if isinstance(vectors, dict) else None, "vector_id", VECTOR_ID)
    if not isinstance(vector, dict) or vector.get("applies_to_fixtures") != [FIXTURE.name]:
        lint.fail(VECTORS, "historical signer vector must point to its dedicated fixture")
    fixture = load_json(lint, FIXTURE)
    if not isinstance(fixture, dict) or fixture.get("vector_id") != VECTOR_ID:
        lint.fail(FIXTURE, "historical signer fixture must bind the registered vector")
    else:
        if fixture.get("carrier_sources") != [
            "account_subscribe.realm_sync_entry.committed_events",
            "ak.self.committed_event.read.scan.v1.stream_scan_outcome.committed_events",
        ]:
            lint.fail(FIXTURE, "fixture must retain exactly the two existing stream_row carrier sources")
        if fixture.get("construction_sources") != fixture.get("carrier_sources", []) + ["self_submit.frozen_signed_request_and_bound_accepted_outcome"]:
            lint.fail(FIXTURE, "fixture must close coordinate construction over existing rows and bound self submissions")
        if fixture.get("self_submission_rule") != SELF_SUBMISSION_RULE:
            lint.fail(FIXTURE, "self submission fixture must preserve exact binding, immutable authorization and restricted PCR rules")
        if not SELF_SUBMISSION_FLOWS.issubset(set(fixture.get("positive_flows", []))):
            lint.fail(FIXTURE, "fixture is missing self submission authorization and no-scan flows")
        positive = fixture.get("positive_case")
        selector_ref = positive.get("selector", {}).get("committed_event_ref") if isinstance(positive, dict) else None
        authorization_ref = positive.get("resolved_key", {}).get("authorization_ref") if isinstance(positive, dict) else None
        if not isinstance(selector_ref, dict) or not isinstance(authorization_ref, dict) or selector_ref == authorization_ref:
            lint.fail(FIXTURE, "fixture must prove independent unequal target and authorization refs are valid")
        negatives = set(fixture.get("negative_cases", []))
        if not NEGATIVE_CASES.issubset(negatives):
            lint.fail(FIXTURE, "fixture is missing historical coordinate negative cases")
        positive_flows = set(fixture.get("positive_flows", []))
        if not {
            "single_agent_reply_resolves_without_later_account_frame",
            "changed_product_projection_still_resolves_historical_signer",
            "verified_key_revalidates_pending_reply_without_reload",
        }.issubset(positive_flows):
            lint.fail(FIXTURE, "fixture is missing historical signer resolution liveness flows")

    prose = {
        SERVER_PROSE: ("历史坐标来源与双引用分离", "MAY 相同", "不得降级成 `current_admission`", "历史签名证据解析的活性", "本次 self 提交原件", "self 提交的 Human PCR 历史公钥", "同事务事实", "MUST NOT 推进"),
        SYNC_PROSE: ("realm_sync_entry.committed_events[]", "stream_scan_outcome.committed_events[]", "不得新增"),
        VECTOR_PROSE: (VECTOR_ID, "authorization_ref", "current-query 降级"),
    }
    for path, markers in prose.items():
        source = read_text(path)
        for marker in markers:
            if marker not in source:
                lint.fail(path, f"historical signer normative prose is missing {marker!r}")

    if "check_signer_key_historical_coordinate(lint)" not in read_text(RUNNER):
        lint.fail(RUNNER, "phase-2 runner must invoke the historical signer coordinate gate")


def _check_foreign_human_delivery_shape(lint: Lint) -> None:
    """Schema/registry closure only; this is not a signature/runtime proof."""
    authority = load_json(lint, AUTHORITY_SCHEMA)
    defs = _defs(authority)
    expected = ["event_id", "actor", "device_id", "verification_method", "key", "accepted_at"]
    fact = defs.get("human_historical_signer_fact", {})
    if fact.get("required") != expected or list(fact.get("properties", {})) != expected or fact.get("additionalProperties") is not False:
        lint.fail(AUTHORITY_SCHEMA, "Human fact must remain minimal, required and closed in exact field order")
    if fact.get("properties", {}).get("key", {}).get("$ref") != "./signer-key-operations.schema.json#/$defs/query_signing_key":
        lint.fail(AUTHORITY_SCHEMA, "Human fact must reuse complete original query_signing_key")
    peer = defs.get("peer_stream_scan_outcome", {})
    if list(peer.get("properties", {})) != ["committed_events", "readable_floor", "truncated", "producer_signer_facts"] or "producer_signer_facts" not in peer.get("required", []) or peer.get("additionalProperties") is not False:
        lint.fail(AUTHORITY_SCHEMA, "peer scan must carry required closed original fact entries")
    if "producer_signer_facts" in defs.get("stream_scan_outcome", {}).get("properties", {}):
        lint.fail(AUTHORITY_SCHEMA, "self scan must not acquire peer fact metadata")
    commit = load_json(lint, ARTIFACTS / "schemas" / "realm-commit.schema.json")
    fields = list(commit.get("properties", {}))
    if fields[-3:] != ["committed_at", "producer_signer_fact_digest", "signature"]:
        lint.fail(AUTHORITY_SCHEMA, "original Commit must commit Human fact digest before signature")
    contract = load_json(lint, CONTRACT)
    rule = contract.get("did_evidence_boundary_registry", {}).get("governance_result_consumption_contract", {}).get("foreign_human_historical_signer_delivery", {})
    if rule.get("target_commit_identity_in_fact") is not False or rule.get("source_accepted_time") != "original_authorization_commit.committed_at" or rule.get("covers_local_governor_human_for_foreign_member") is not True:
        lint.fail(CONTRACT, "Human source must bind original authorization time, avoid target-ID cycle and cover local governor")
    op = _find(contract.get("operation_registry", {}).get("operations"), "operation_id", "ak.peer.committed_event.read.scan.v1")
    if not isinstance(op, dict) or op.get("response_schema_ref") != "schemas/authority-commit-operations.schema.json#/$defs/peer_stream_scan_outcome":
        lint.fail(CONTRACT, "peer operation must select its fact-bearing scan response")
    fixture = load_json(lint, FIXTURE).get("foreign_human_historical_signer_delivery", {})
    if fixture.get("contract") != rule or fixture.get("source_times", {}).get("accepted_at") != "original_authorization_commit.committed_at":
        lint.fail(FIXTURE, "Human source fixture plan must match source-time/no-cycle carrier contract")

    invite = load_json(lint, INVITE_SCHEMA)
    properties = list(invite.get("properties", {}))
    if properties[:4] != ["schema", "invite_event", "invite_commit", "producer_signer_fact"] or invite.get("properties", {}).get("producer_signer_fact", {}).get("$ref") != "./authority-commit-operations.schema.json#/$defs/human_historical_signer_fact" or invite.get("additionalProperties") is not False:
        lint.fail(INVITE_SCHEMA, "Invite notification must carry closed original fact after its original Commit")
    condition = {"if": {"properties": {"invite_commit": {"required": ["producer_signer_fact_digest"]}}, "required": ["invite_commit"]}, "then": {"required": ["producer_signer_fact"]}, "else": {"not": {"required": ["producer_signer_fact"]}}}
    if condition not in invite.get("allOf", []):
        lint.fail(INVITE_SCHEMA, "Invite fact must appear exactly when original Commit carries its digest")
    if "producer_signer_fact" in invite.get("$defs", {}).get("self_invite_dispatch_request_body", {}).get("properties", {}):
        lint.fail(INVITE_SCHEMA, "Self dispatch cannot echo or reconstruct an original signer fact")
    delivery_rule = rule.get("invite_delivery", {})
    if "invite_delivery_request.producer_signer_fact" not in rule.get("carry", []) or delivery_rule.get("recipient") != "existing_exact_invitee_account_station_only" or delivery_rule.get("membership_or_pcr_read_granted") is not False or delivery_rule.get("holder_delivery_value_extended") is not False or delivery_rule.get("missing_source") != "existing_unavailable_zero_holder_writes":
        lint.fail(CONTRACT, "Invite fact disclosure must remain exact-recipient-only without membership, PCR or holder carrier expansion")

    keys_path = ARTIFACTS / "schemas" / "keys-operations.schema.json"
    keys = _defs(load_json(lint, keys_path))
    directory = keys.get("device_projection_attestation_core", {})
    forward = keys.get("forward_device_projection_attestation_core", {})
    if "event_authorization" in directory.get("properties", {}) or directory.get("additionalProperties") is not False:
        lint.fail(keys_path, "directory must remain closed without PCR source metadata")
    if "event_authorization" not in forward.get("required", []) or forward.get("additionalProperties") is not False:
        lint.fail(keys_path, "forward must require closed Event-bound original source")
    expected_source = ["event_id", "verification_method", "destination_service_id", "forward_body_digest", "authorization_ref", "revision", "governance_generation", "accepted_at"]
    source = keys.get("human_event_authorization", {})
    fixed_ref = "./account-operations.schema.json#/$defs/sha256_digest"
    if source.get("properties", {}).get("forward_body_digest", {}).get("$ref") != fixed_ref:
        lint.fail(keys_path, "forward body digest must be fixed SHA256")
    if commit.get("properties", {}).get("producer_signer_fact_digest", {}).get("$ref") != fixed_ref:
        lint.fail(AUTHORITY_SCHEMA, "original Human fact digest must be fixed SHA256")
    handoff = load_json(lint, ARTIFACTS / "schemas" / "realm-authority-handoff.schema.json")
    if handoff.get("properties", {}).get("historical_signer_facts_digest", {}).get("$ref") != fixed_ref:
        lint.fail(AUTHORITY_SCHEMA, "historical handoff inventory digest must be fixed SHA256")
    if source.get("required") != expected_source or list(source.get("properties", {})) != expected_source or source.get("additionalProperties") is not False:
        lint.fail(keys_path, "origin source must be complete, closed and contain no fabricated target Commit")

def _foreign_human_transcript_errors(transcript: dict) -> list[str]:
    """Published-key byte KAT only; no PCR/current/SQL admission is implied."""
    import base64
    import hashlib
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from .core import canonical_json
    from .fixtures import base58btc_decode
    errors = []
    def jcs(value):
        return canonical_json(value).encode()
    def sha(value):
        return 'sha256:' + hashlib.sha256(jcs(value)).hexdigest()
    def raw(value):
        return base64.urlsafe_b64decode(value+'='*(-len(value)%4))
    def token(kind, value):
        return 'ak:'+kind+':'+base64.urlsafe_b64encode(b'\x01'+hashlib.sha256(jcs(value)).digest()).rstrip(b'=').decode()
    def check(condition, branch):
        if not condition:
            errors.append(branch)
    def verify_jws(proof, binding, public):
        protected, payload, signature = proof['jws'].split('.')
        check(payload == '', 'detached_jws_payload')
        check(json.loads(raw(protected)) == {'alg':'Ed25519'}, 'jose_algorithm')
        Ed25519PublicKey.from_public_bytes(raw(public)).verify(raw(signature), protected.encode()+b'.'+base64.urlsafe_b64encode(jcs(binding)).rstrip(b'='))
    def verify_origin(wrapper, public):
        core=wrapper['attestation'];proof=wrapper['proof']
        binding={'context':'ak.device_projection_attestation_proof.v1','payload_digest':sha({'attestation':core})}
        for key in ['account_id','device_id','device_signing_key_did','hpke_key','device_authorize_event_id','authorized_generation_ref','device_status','attested_at','expires_at']:
            binding[key]=core[key]
        binding.update(verification_method=proof['verification_method'],created_at=proof['created_at'])
        check(proof['created_at']==core['attested_at'], 'origin_time_binding')
        verify_jws(proof,binding,public)
        return core,binding
    def verify_detached(signature, host, public, context):
        check(signature['context']==context, 'detached_context')
        check(signature['signature_algorithm']=='Ed25519', 'detached_algorithm')
        check(signature['signed_digest']==sha(host), 'complete_unsigned_digest')
        envelope={key:signature[key] for key in ['context','signature_algorithm','verification_method','signed_digest','created_at']}
        Ed25519PublicKey.from_public_bytes(raw(public)).verify(raw(signature['sig']),(context+'\n').encode()+jcs(envelope))
    import json
    try:
        kat=load_json(Lint(),ARTIFACTS/'fixtures'/'detached-object-signature-kat-fixture.json')
        keys={key['test_key_ref']:key['public_key_b64u'] for key in kat['test_keys']}
        human=keys['rfc8032_test_1_ed25519_key'];station=keys['conformance_ed25519_fixture_key']
        check(transcript['keys']['human_public_key_b64u']==human,'published_human_key')
        check(transcript['keys']['origin_governor_public_key_b64u']==station,'published_station_key')
        event=transcript['event'];proof=event['producer_proof'];body={key:value for key,value in event.items() if key not in ['event_id','producer_proof','unsigned']}
        check(event['event_id']==token('event',body),'event_content_id')
        check(proof['event_digest']==sha(body),'event_digest')
        binding={'context':'ak.event_proof.v1','event_digest':sha(body),'actor_id':event['actor_id'],'verification_method':proof['verification_method'],'created_at':proof['created_at']}
        for key in ['domain','audience']:
            if key in proof:binding[key]=proof[key]
        verify_jws(proof,binding,human)
        check(transcript['event_binding']==binding,'event_binding_record')
        core,ob=verify_origin(transcript['origin_attestation'],station)
        check(transcript['origin_binding']==ob,'origin_binding_record')
        alt,ab=verify_origin(transcript['alternate_authentic_origin_attestation'],station)
        check(transcript['alternate_origin_binding']==ab,'alternate_origin_binding_record')
        fact=transcript['fact'];auth=core['event_authorization']
        check(set(fact)=={'event_id','actor','device_id','verification_method','key','accepted_at'},'fact_closed')
        check(fact['event_id']==event['event_id'] and fact['actor']==event['actor_id'],'fact_actual_producer')
        check(fact['verification_method']==proof['verification_method'] and fact['device_id']==proof['verification_method'].split('#')[1],'fact_device_method')
        check(core['account_id']==fact['actor']['account_id'] and core['device_id']==fact['device_id'],'origin_account_device')
        check(base58btc_decode(core['device_signing_key_did'].split(':')[-1][1:])==b'\xed\x01'+raw(human),'origin_actual_key')
        check(fact['key']['public_key_b64u']==human,'fact_actual_key')
        check(auth['authorization_ref']['event_id']==core['device_authorize_event_id'],'origin_authorizer_event')
        check(auth['event_id']==event['event_id'] and auth['verification_method']==proof['verification_method'],'origin_exact_event_method')
        check(auth['forward_body_digest']==sha({'branch':'authority_forward','event_submission':{'event':event}}),'origin_exact_forward_body')
        check(auth['destination_service_id']=='ak:did_core:webvh:z6mkfixturegovernor','origin_exact_destination')
        for key in ['authorization_ref','revision','governance_generation']:
            check(auth[key]==fact['key'][key],'origin_fact_'+key)
        check(auth['accepted_at']==fact['accepted_at'],'origin_source_time')
        check(auth['revision']['stream_position']>=auth['authorization_ref']['stream_position'],'source_revision_floor')
        check(alt['event_authorization']['event_id']==auth['event_id'] and alt['device_signing_key_did']==core['device_signing_key_did'],'alternate_same_event_key')
        check(alt['event_authorization']['revision']!=auth['revision'],'alternate_distinct_source')
        check({k:v for k,v in alt.items() if k!='event_authorization'} == {k:v for k,v in core.items() if k!='event_authorization'}, 'alternate_same_original_device_projection')
        check({k:v for k,v in alt['event_authorization'].items() if k!='revision'} == {k:v for k,v in auth.items() if k!='revision'}, 'alternate_same_source_except_revision')
        alt_auth = alt['event_authorization']
        alt_key = dict(fact['key'])
        for field in ['authorization_ref', 'revision', 'governance_generation']:
            alt_key[field] = alt_auth[field]
        expected_alternate_fact = dict(fact, device_id=alt['device_id'], verification_method=alt_auth['verification_method'], key=alt_key, accepted_at=alt_auth['accepted_at'])
        check(transcript['alternate_fact'] == expected_alternate_fact, 'alternate_fact_from_authentic_origin')
        commit=transcript['commit'];unsigned={key:value for key,value in commit.items() if key!='signature'};id_body={key:value for key,value in unsigned.items() if key!='commit_id'}
        check(commit['commit_id']==token('realm_commit',id_body),'commit_content_id')
        check(commit['event_ref']==event['event_id'] and commit['realm_id']==event['realm_id'] and commit['stream_ref']==event['scope_ref'],'commit_exact_target')
        check(commit['producer_signer_fact_digest']==sha(fact),'original_governor_fact_digest')
        check(commit['producer_signer_fact_digest']!=sha(transcript['alternate_fact']),'alternate_source_cannot_replace_governor_choice')
        verify_detached(commit['signature'],unsigned,station,'ak.realm_commit_signature.v1')
        check(commit['signature']['created_at']==commit['committed_at'],'commit_signature_time')
        check(transcript['commit_signature_transcript']['unsigned_projection']==unsigned,'commit_transcript_projection')
        target={'event_id':event['event_id'],'commit_id':commit['commit_id'],'stream_ref':commit['stream_ref'],'stream_position':commit['stream_position']}
        entry={'target':target,'producer_signer_fact':fact}
        check(transcript['replication']=={'event_submission':{'event':event},'source_commit':commit,'producer_signer_fact':fact},'replication_originals')
        scan=transcript['peer_scan'];check(scan['committed_events']==[{'commit':commit,'event':event}],'scan_original_rows');check(scan['producer_signer_facts']==[entry],'scan_exact_one_fact')
        h=transcript['handoff'];hu={key:value for key,value in h.items() if key not in ['old_authority_signature','new_authority_acceptance_signature']}
        check(h['historical_signer_facts_digest']==sha(transcript['handoff_inventory']),'handoff_inventory_digest')
        inventory = transcript['handoff_inventory']
        expected_targets = []
        for original in transcript['handoff_fenced_imported_originals']:
            oc = original['commit']; oe = original['event']
            check(oc == commit and oe == event, 'handoff_exact_verified_original_bytes')
            if 'producer_signer_fact_digest' in oc:
                check(oc['event_ref'] == oe['event_id'], 'handoff_original_event_pair')
                expected_targets.append({'event_id':oe['event_id'],'commit_id':oc['commit_id'],'stream_ref':oc['stream_ref'],'stream_position':oc['stream_position']})
        def order(t):
            return (jcs(t['stream_ref']), t['stream_position'], t['event_id'].encode(), t['commit_id'].encode())
        targets = [item['target'] for item in inventory]
        check(len({jcs(t) for t in targets}) == len(targets), 'handoff_inventory_duplicate')
        check(targets == sorted(targets, key=order), 'handoff_inventory_canonical_order')
        check(sorted(targets,key=order) == sorted(expected_targets,key=order), 'handoff_inventory_exact_fenced_set')
        check(inventory==[entry],'handoff_complete_original_fact')
        check(h['handoff_id']==token('realm_authority_handoff',{key:value for key,value in hu.items() if key!='handoff_id'}),'handoff_content_id')
        verify_detached(h['old_authority_signature'],hu,station,'ak.realm_authority_handoff_old_signature.v1')
        verify_detached(h['new_authority_acceptance_signature'],hu,human,'ak.realm_authority_handoff_new_acceptance_signature.v1')
        check(h['old_authority_signature']['signed_digest']==h['new_authority_acceptance_signature']['signed_digest'],'handoff_same_projection')
    except Exception as exc:
        errors.append('cryptographic_transcript_invalid:'+type(exc).__name__)
    return errors


def _check_foreign_human_crypto_transcript(lint: Lint) -> None:
    fixture = load_json(lint, FIXTURE)
    transcript = fixture.get("foreign_human_historical_signer_delivery", {}).get("crypto_transcript")
    if not isinstance(transcript, dict):
        lint.fail(FIXTURE, "real Human/Commit cryptographic transcript is missing")
        return
    for branch in _foreign_human_transcript_errors(transcript):
        lint.fail(FIXTURE, "foreign Human cryptographic KAT: " + branch)
