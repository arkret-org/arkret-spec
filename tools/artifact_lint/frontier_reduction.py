"""Executable exchange terminal-state and Event-ID evidence vectors."""
from __future__ import annotations

import base64
import hashlib


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


def check_frontier_reduction_fixture(lint, path, data):
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
