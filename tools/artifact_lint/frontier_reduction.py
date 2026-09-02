"""Executable exchange terminal-state and Event-ID evidence vectors."""
from __future__ import annotations

import base64
import hashlib


DELIVERY_EVENT_ID = "ak:event:AY4rjZ5eX4tirzUMKIQZ0K26SIcvduWsg-p90KQ2PMVZ"


def event_evidence(preimages, carried_ids, *, injected_digest=None, prerequisites=True):
    """Injection tests collision handling; it makes no real SHA-256 collision claim."""
    verified = {}
    for preimage, carried in zip(preimages, carried_ids, strict=True):
        digest = injected_digest if injected_digest is not None else hashlib.sha256(preimage.encode()).digest()
        actual = "ak:event:" + base64.urlsafe_b64encode(b"\x01" + digest).decode().rstrip("=")
        if actual != carried:
            return "event_id_digest_mismatch", False
        if not prerequisites:
            return "invalid_proof", False
        if actual in verified and verified[actual] != preimage:
            return "witness_disagreement", True
        verified[actual] = preimage
    return "accepted", False


def terminal(case):
    if case.get("confirmed_evidence"):
        return {"status": "peer_stale", "failures": 0, "quarantine": True, "complete": False}
    if case.get("failure"):
        failures = case.get("previous_failures", 0) + 1
        return {"status": "peer_stale" if failures >= 3 else "healthy", "failures": failures, "quarantine": False, "complete": False}
    return {"status": "healthy", "failures": 0, "quarantine": False, "complete": False}


def delivery_terminal(case):
    current = set(case.get("top_level_accepted", [])) | set(case.get("top_level_duplicate", []))
    retry_current = set(case.get("retry_top_level_duplicate", []))
    delivered = DELIVERY_EVENT_ID in current or DELIVERY_EVENT_ID in retry_current
    return {"delivered": delivered, "retry": not delivered}


def frontier_diagnostic(case):
    if case.get("root_equal"):
        return "observation_unchanged_without_set_equality_or_completeness"
    if case.get("known_dependency_gap"):
        return "resolve_then_submit_or_outbox"
    if case.get("operator_fallback") and case.get("local_budget_exhausted"):
        return "stop_with_local_diagnostic_without_peer_failure"
    if case.get("operator_fallback") and case.get("cursor_expired"):
        return "restart_or_stop_without_peer_failure"
    return "reconciliation_incomplete_without_routine_scan_or_peer_failure"


def check_frontier_reduction_fixture(lint, path, data):
    delivery_cases = data.get("delivery_outcome_cases", [])
    required_delivery = {
        "http_2xx_without_item_outcome",
        "destination_commit_before_response_crash_then_retry",
        "source_crash_before_delivered_persist_then_retry",
        "historical_only_original_outcome_does_not_complete_intent",
        "destination_old_backup_allows_authorized_backfill",
    }
    if {case.get("name") for case in delivery_cases} != required_delivery:
        lint.fail(path, "delivery outcome case inventory is incomplete")
    for case in delivery_cases:
        if delivery_terminal(case) != case.get("expected"):
            lint.fail(path, f"delivery outcome KAT mismatch: {case.get('name')}")

    diagnostic_cases = data.get("frontier_diagnostic_cases", [])
    required_diagnostics = {
        "aggregate_root_equal_same_direction",
        "aggregate_root_mismatch_unknown_scope",
        "known_dependency_gap",
        "operator_fallback_budget_exhausted",
        "operator_fallback_cursor_expired",
    }
    if {case.get("name") for case in diagnostic_cases} != required_diagnostics:
        lint.fail(path, "frontier diagnostic case inventory is incomplete")
    for case in diagnostic_cases:
        if frontier_diagnostic(case) != case.get("expected"):
            lint.fail(path, f"frontier diagnostic KAT mismatch: {case.get('name')}")

    cases = data.get("frontier_reduction_cases", [])
    required = {"equal_root", "no_common_obligation", "required_actor_omitted", "permanent_scope_difference", "legal_sibling_union", "local_outbox_ahead", "remote_backfill_ahead", "network_failure", "first_over_fork", "first_non_joinable", "first_full_hash_collision"}
    if {case.get("name") for case in cases} != required:
        lint.fail(path, "frontier reduction case inventory is incomplete")
    for case in cases:
        if terminal(case) != case.get("expected"):
            lint.fail(path, f"frontier terminal KAT mismatch: {case.get('name')}")
    vectors = data.get("frontier_event_evidence", {})
    for name, vector in vectors.items():
        injected = bytes.fromhex(vector["injected_digest_hex"]) if "injected_digest_hex" in vector else None
        if injected is not None and vector.get("real_hash_collision_claimed") is not False:
            lint.fail(path, f"{name}: collision injection must not claim a real hash collision")
        reason, quarantine = event_evidence(vector["preimages"], vector["carried_ids"], injected_digest=injected, prerequisites=vector.get("prerequisites", True))
        if {"reason": reason, "quarantine": quarantine} != vector.get("expected"):
            lint.fail(path, f"frontier Event-ID evidence KAT mismatch: {name}")
    if set(vectors) != {"forged_carried_id", "injected_full_hash_collision", "invalid_collision_proof"}:
        lint.fail(path, "frontier Event-ID evidence case inventory is incomplete")
