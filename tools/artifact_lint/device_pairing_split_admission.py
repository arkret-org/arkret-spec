"""Close the split Station/Account-Authority device-pairing saga."""

from __future__ import annotations

from typing import Any

from .core import ARTIFACTS, ROOT, SPEC_ROOT, Lint, load_json, read_text


CONTRACT = ARTIFACTS / "registry" / "contract-registry.json"
ERROR_MAPPING = ARTIFACTS / "registry" / "operations-error-mapping.json"
VECTORS = ARTIFACTS / "registry" / "vector-registry.json"
FIXTURE = ARTIFACTS / "fixtures" / "device-pairing-split-admission-saga-fixture.json"
OPENAPI = ARTIFACTS / "openapi" / "arkret-service-api.openapi.yaml"
DEVICE_PROSE = SPEC_ROOT / "zh" / "crypto-media" / "device-lifecycle.md"
BINDING_PROSE = SPEC_ROOT / "zh" / "sync" / "service-http-binding.md"
SURFACE_PROSE = SPEC_ROOT / "zh" / "sync" / "service-surface.md"
VECTOR_PROSE = SPEC_ROOT / "zh" / "conformance" / "conformance-vectors.md"
RUNNER = ROOT / "tools" / "artifact_lint" / "runner.py"

COORDINATION_ID = "ak.coordination.device_pairing.split_admission_saga.v1"
VECTOR_ID = "ak.vector.device_pairing.split_admission_saga.v1"
PAIR = "ak.gate.account.command.pair_device.v1"
PEER_SUBMIT = "ak.peer.events.command.submit.v1"
SERVICE_SIGNATURE = "ak.http_signature.scenario.service_to_service.v1"

PROXIES = (
    (
        "ak.open.device_pairing.command.stage.v1",
        "ak.gate.account.command.stage_device_pairing.v1",
        "schemas/device-pairing.schema.json#/$defs/device_pairing_stage_request_body",
        "schemas/device-pairing.schema.json#/$defs/device_pairing_stage_outcome",
    ),
    (
        "ak.open.device_pairing.read.resolve.v1",
        "ak.gate.account.read.resolve_device_pairing.v1",
        "schemas/device-pairing.schema.json#/$defs/device_pairing_resolve_request_body",
        "schemas/device-pairing.schema.json#/$defs/device_pairing_bootstrap",
    ),
    (
        "ak.open.device_pairing.read.status.v1",
        "ak.gate.account.read.device_pairing_status.v1",
        "schemas/device-pairing.schema.json#/$defs/device_pairing_status_request_body",
        "schemas/device-pairing.schema.json#/$defs/device_pairing_status_outcome",
    ),
)

CRASH_CUTS = [
    "before_prepared_commit",
    "after_prepared_before_station_call",
    "after_station_commit_before_receipt_persist",
    "after_station_accepted_before_local_completion",
    "after_completed_before_client_response",
]

PROTECTIONS = [
    "ttl_cleanup_forbidden",
    "failure_budget_increment_forbidden",
    "finalize_supersession_forbidden",
    "different_request_finalize_must_not_create_second_ready_for_claim",
    "resolve_status_and_code_claim_fail_closed_without_budget_write",
]


def _find(rows: Any, field: str, value: str) -> dict[str, Any] | None:
    if not isinstance(rows, list):
        return None
    matches = [row for row in rows if isinstance(row, dict) and row.get(field) == value]
    return matches[0] if len(matches) == 1 else None


def _operation(document: dict[str, Any], operation_id: str) -> dict[str, Any] | None:
    registry = document.get("operation_registry")
    return _find(registry.get("operations") if isinstance(registry, dict) else None, "operation_id", operation_id)


def _bundle(document: dict[str, Any], bundle_id: str) -> dict[str, Any] | None:
    registry = document.get("operation_registry")
    return _find(registry.get("operation_bundles") if isinstance(registry, dict) else None, "operation_bundle_id", bundle_id)


def check_device_pairing_split_admission_saga(lint: Lint) -> None:
    contract = load_json(lint, CONTRACT)
    if not isinstance(contract, dict):
        return

    for index, (public_id, internal_id, request_ref, response_ref) in enumerate(PROXIES):
        public = _operation(contract, public_id)
        internal = _operation(contract, internal_id)
        if public is None or internal is None:
            lint.fail(CONTRACT, f"missing unique public/internal proxy pair {public_id} -> {internal_id}")
            continue
        if (internal.get("request_schema_ref"), internal.get("response_schema_ref")) != (request_ref, response_ref):
            lint.fail(CONTRACT, f"{internal_id} must reuse the exact public DTO pair")
        auth = internal.get("auth_requirements")
        signature = auth.get("service_signature") if isinstance(auth, dict) else None
        if not isinstance(signature, dict) or signature.get("signature_scenario_id") != SERVICE_SIGNATURE:
            lint.fail(CONTRACT, f"{internal_id} must require the canonical service signature scenario")
        if not internal.get("http_only_variant"):
            lint.fail(CONTRACT, f"{internal_id} must remain an internal HTTP-only operation")
        if index == 0:
            if public.get("retry_safe") is not False or public.get("idempotency_mechanism") != "none":
                lint.fail(CONTRACT, "public stage must remain non-retry-safe with no idempotency key")
            if internal.get("retry_safe") is not True or internal.get("idempotency_mechanism") != "idempotency_key":
                lint.fail(CONTRACT, "internal stage must durably deduplicate the Station key")
        elif any(key in internal for key in ("retry_safe", "idempotency_mechanism", "durable_effect")):
            lint.fail(CONTRACT, f"{internal_id} must remain a read-only proxy without mutation metadata")

    public_bundle = _bundle(contract, "ak.operation_bundle.station.device_pairing_handoff.v1")
    expected_public = [row[0] for row in PROXIES]
    public_members = public_bundle.get("members") if isinstance(public_bundle, dict) else None
    public_ids = [row.get("operation_id") for row in public_members if isinstance(row, dict)] if isinstance(public_members, list) else None
    if public_ids != expected_public:
        lint.fail(CONTRACT, "device_pairing_handoff must remain the exact three-public-operation bundle")
    core_bundle = _bundle(contract, "ak.operation_bundle.station.http_core.v1")
    core_members = core_bundle.get("members") if isinstance(core_bundle, dict) else None
    core_ids = [row.get("operation_id") for row in core_members if isinstance(row, dict)] if isinstance(core_members, list) else None
    if not isinstance(core_ids, list) or not set(row[1] for row in PROXIES).issubset(core_ids):
        lint.fail(CONTRACT, "station.http_core must include all three internal proxy operations")

    pair = _operation(contract, PAIR)
    effect = pair.get("durable_effect") if isinstance(pair, dict) else None
    expected_cross = [
        "account_authority_pairing_admission_fence_committed",
        "owning_station_authority_forward_realm_commit_verified",
        "account_authority_pending_consumed_and_terminal_outcome_committed",
    ]
    if not isinstance(effect, dict) or effect.get("event_submission_path") != "/authorize_event":
        lint.fail(CONTRACT, "pair_device must register /authorize_event as its Event submission path")
    elif effect.get("cross_service_effects") != expected_cross or not effect.get("irreversibility_note"):
        lint.fail(CONTRACT, "pair_device must register the complete split cross-service effect and irreversibility boundary")

    registry = contract.get("operation_registry")
    relations = registry.get("coordination_relations") if isinstance(registry, dict) else None
    relation = _find(relations, "coordination_id", COORDINATION_ID)
    if relation is None:
        lint.fail(CONTRACT, f"missing unique machine coordination relation {COORDINATION_ID}")
        return
    if (relation.get("entry_operation_id"), relation.get("ledger_owner"), relation.get("recovery_owner"), relation.get("station_pairing_business_state")) != (PAIR, "account_authority", "account_authority", "forbidden"):
        lint.fail(CONTRACT, "coordination ownership must keep the sole pairing ledger and recovery at Account Authority")
    mappings = relation.get("public_proxy_mappings")
    if not isinstance(mappings, list) or [row.get("internal_operation_id") for row in mappings if isinstance(row, dict)] != [row[1] for row in PROXIES]:
        lint.fail(CONTRACT, "coordination relation must cover the exact three public-to-internal mappings")
    elif any(row.get("request_mapping") != "byte_identical_body" or row.get("response_mapping") != "byte_identical_body" for row in mappings):
        lint.fail(CONTRACT, "all proxy mappings must preserve byte-identical public DTO bodies")

    admission = relation.get("event_admission")
    if not isinstance(admission, dict) or any(
        admission.get(key) != value
        for key, value in {
            "operation_id": PEER_SUBMIT,
            "branch": "authority_forward",
            "entry_request_event_submission_path": "/authorize_event",
            "downstream_request_event_submission_path": "/event_submission",
            "receipt_commit_path": "/outcome/commit",
            "forbid_second_event_operation": True,
        }.items()
    ):
        lint.fail(CONTRACT, "event admission must freeze one authority_forward request and verify its RealmCommit receipt")
    elif admission.get("accepted_statuses") != ["committed", "duplicate"] or "frozen_event_bytes_unchanged" not in admission.get("receipt_verification", []):
        lint.fail(CONTRACT, "event admission must accept only verified committed/duplicate exact replay")

    fence = relation.get("fence")
    if not isinstance(fence, dict):
        lint.fail(CONTRACT, "coordination relation is missing the Authority fence")
    else:
        if fence.get("storage_owner") != "account_authority_pairing_ledger" or fence.get("key_fields") != ["device_pairing_request_id", "approving_account_id", "approving_device_id"]:
            lint.fail(CONTRACT, "Authority fence owner/key must be closed")
        if fence.get("states") != ["prepared", "station_accepted", "completed"]:
            lint.fail(CONTRACT, "Authority fence states must be prepared -> station_accepted -> completed")
        transitions = fence.get("transitions")
        edges = [(row.get("from"), row.get("to")) for row in transitions if isinstance(row, dict)] if isinstance(transitions, list) else []
        if edges != [("absent", "prepared"), ("prepared", "station_accepted"), ("station_accepted", "completed"), ("prepared", "absent")]:
            lint.fail(CONTRACT, "Authority fence transition graph or terminal-rejection abort is incomplete")
        if fence.get("nonterminal_protections") != PROTECTIONS:
            lint.fail(CONTRACT, "nonterminal fence must be immune to TTL, budget and finalize supersession")
        if fence.get("public_status_projection") != "no_in_progress_state":
            lint.fail(CONTRACT, "private fence must not introduce a public in_progress state")

    recovery = relation.get("crash_recovery")
    if not isinstance(recovery, list) or [row.get("cut") for row in recovery if isinstance(row, dict)] != CRASH_CUTS:
        lint.fail(CONTRACT, "coordination relation must close all five crash cuts")
    translations = relation.get("downstream_error_translation")
    sources = [row.get("source") for row in translations if isinstance(row, dict)] if isinstance(translations, list) else []
    if sources != [
        "peer_rejected_with_any_schema_valid_reason",
        "peer_retryable_unavailable_or_network_failure",
        "missing_or_mismatched_realm_commit_receipt",
        "same_fence_key_different_digest_or_holder",
        "internal_proxy_unavailable",
        "proxy_read_unknown_mismatch_or_state",
    ]:
        lint.fail(CONTRACT, "coordination relation must register the closed downstream error translation")

    errors = load_json(lint, ERROR_MAPPING)
    error_rows = errors.get("operations") if isinstance(errors, dict) else None
    pair_errors = _find(error_rows, "operation_id", PAIR)
    if not isinstance(pair_errors, dict) or pair_errors.get("operation_specific") != ["failed_precondition", "proof_invalid"]:
        lint.fail(ERROR_MAPPING, "pair_device error map must include the unified terminal rejection")
    for _, internal_id, _, _ in PROXIES:
        if _find(error_rows, "operation_id", internal_id) is None:
            lint.fail(ERROR_MAPPING, f"missing error-map row for {internal_id}")

    vectors = load_json(lint, VECTORS)
    vector = _find(vectors.get("vectors") if isinstance(vectors, dict) else None, "vector_id", VECTOR_ID)
    if not isinstance(vector, dict) or vector.get("applies_to_fixtures") != [FIXTURE.name]:
        lint.fail(VECTORS, "split-admission vector must point to its dedicated fixture")
    fixture = load_json(lint, FIXTURE)
    if not isinstance(fixture, dict) or fixture.get("coordination_id") != COORDINATION_ID:
        lint.fail(FIXTURE, "split-admission fixture must bind the registered coordination relation")
    else:
        if [row.get("cut") for row in fixture.get("crash_cases", []) if isinstance(row, dict)] != CRASH_CUTS:
            lint.fail(FIXTURE, "fixture must exercise all five crash cuts")
        negative_ids = {row.get("case_id") for row in fixture.get("negative_cases", []) if isinstance(row, dict)}
        for case_id in ("peer_receipt_event_ref_mismatch", "peer_terminal_rejected_zero_write", "new_finalize_targets_fenced_account"):
            if case_id not in negative_ids:
                lint.fail(FIXTURE, f"fixture is missing negative case {case_id}")

    openapi = read_text(OPENAPI)
    for marker in (
        "/_arkret/gate/account/device-pairing/stages:",
        "/_arkret/gate/account/device-pairing/resolutions:",
        "/_arkret/gate/account/device-pairing/status-queries:",
        "operationId: ak.gate.account.command.stage_device_pairing",
        "Idempotency-Key",
        "httpMessageSignature",
    ):
        if marker not in openapi:
            lint.fail(OPENAPI, f"OpenAPI split-admission surface is missing {marker!r}")

    prose_markers = {
        DEVICE_PROSE: ("prepared -> station_accepted -> completed", "authority_forward", "`prepared` 前失败"),
        BINDING_PROSE: ("stage_device_pairing", "byte-identical", "temporarily_unavailable"),
        SURFACE_PROSE: ("coordination_relations", "Account Authority", "Station"),
        VECTOR_PROSE: (VECTOR_ID, "五个 crash cut", "authority_forward"),
    }
    for path, markers in prose_markers.items():
        source = read_text(path)
        for marker in markers:
            if marker not in source:
                lint.fail(path, f"split-admission normative prose is missing {marker!r}")

    runner = read_text(RUNNER)
    if "check_device_pairing_split_admission_saga(lint)" not in runner:
        lint.fail(RUNNER, "phase-1 runner must invoke the split-admission saga gate")
