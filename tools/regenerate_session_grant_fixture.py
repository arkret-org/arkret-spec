#!/usr/bin/env python3
"""Regenerate opaque SessionGrant KATs using public deterministic test seeds."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from session_grant_reference import ath, b64u, credential_digest, grant_ref, jcs_text, jwk_thumbprint, secret_from_random, sign_dpop


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "spec/v1/artifacts/fixtures/session-grant-issuance-fixture.json"
ISSUER_A = "ak:did_core:webvh:z6mkfixtureauthaexample"
ISSUER_B = "ak:did_core:webvh:z6mkfixtureauthbexample"
AUDIENCE = "ak:did_core:webvh:z6mkfixtureserviceexample"
PRINCIPAL = "ak:did_core:webvh:z6mkfixture"
DEVICE = "ak:device:019a0000-0000-7000-8000-000000000001"
EVENT = "ak:event:Ae6YFfDokA1FLUx_l-MhAbSvTvoys2ZpRPmqFwrWjd9g"
RECORD = "ak:session_grant:019a0000-0000-7000-8000-000000000011"
SEED = bytes(range(32, 64))
DEVICE_SEED = bytes(range(64, 96))
NOW = "2026-08-08T12:00:00.000Z"


def build_fixture(previous: dict) -> dict:
    public = Ed25519PrivateKey.from_private_bytes(SEED).public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    jwk = {"crv": "Ed25519", "kty": "OKP", "x": b64u(public)}
    canonical = jcs_text(jwk)
    base = {
        "id": RECORD, "issuer_id": ISSUER_A, "device_id": DEVICE,
        "account_id": {"principal_id": PRINCIPAL, "station_id": AUDIENCE},
        "audience_id": AUDIENCE,
        "scopes": ["ak.self.account.read.describe.v1", "ak.self.committed_event.read.scan.v1"],
        "not_before": NOW, "expires_at": "2026-08-08T13:00:00.000Z",
        "session_id": "session-chain-fixture-001", "session_public_key": canonical,
        "cnf_jkt": jwk_thumbprint(canonical), "credential_class": "standard",
        "holder_binding": {"kind": "human_device", "device_binding": DEVICE},
        "device_binding": {"device_id": DEVICE, "authorization_event_id": EVENT, "model_generation_ref": 1},
        "proof_kind": "account_handoff",
    }
    issuer_b = copy.deepcopy(base)
    issuer_b["issuer_id"] = ISSUER_B
    recovery = copy.deepcopy(base)
    recovery["id"] = RECORD[:-2] + "12"
    recovery["credential_class"] = "recovery_session"
    recovery["holder_binding"] = {"kind": "recovery_candidate_device", "device_id": DEVICE}
    recovery["device_id"] = DEVICE
    recovery.pop("device_binding")
    recovery["scopes"] = ["ak.root.identity.recovery_session.command.create.v1"]
    recovery["expires_at"] = "2026-08-08T12:15:00.000Z"
    agent = copy.deepcopy(base)
    agent["id"] = RECORD[:-2] + "13"
    agent["account_id"]["principal_id"] = "ak:did_core:webvh:z6mkagent"
    agent.pop("device_binding")
    agent.pop("device_id")
    agent["holder_binding"] = {"kind": "agent_runtime", "agent_id": agent["account_id"]["principal_id"], "agent_key_authorization_ref": EVENT, "verification_method": "did:webvh:z6mkagent:agent.example#runtime-1"}
    agent["proof_kind"] = "agent_key_proof"
    agent["scope_details"] = {
        "controller_principal_id": PRINCIPAL, "agent_key_authorization_ref": EVENT,
        "realm_ids": [], "strand_ids": [], "resources": {"realm_ids": [], "strand_ids": []},
        "constraints": {"allowed_tracks": ["discussion"], "allowed_data_labels": [], "allowed_endpoints": []},
        "capability_grant_refs": [], "policy_refs": [],
    }
    successor = copy.deepcopy(base)
    successor["id"] = RECORD[:-2] + "14"
    successor["expires_at"] = "2026-08-08T14:00:00.000Z"
    optional_absent = copy.deepcopy(base)
    optional_absent["id"] = RECORD[:-2] + "15"
    optional_absent.pop("proof_kind")
    vectors = []
    for index, (name, metadata) in enumerate([
        ("issuer_a_standard", base), ("issuer_b_same_record_id", issuer_b),
        ("recovery_candidate", recovery), ("agent_runtime", agent),
        ("refresh_successor", successor), ("absent_optional_is_omitted", optional_absent),
    ]):
        random_bytes = bytes((value + index * 17) % 256 for value in range(32))
        secret = secret_from_random(random_bytes)
        vectors.append({"name": name, "random_bytes_hex": random_bytes.hex(), "metadata": metadata,
                        "canonical_metadata_utf8": jcs_text(metadata), "session_grant": secret,
                        "session_grant_ref": grant_ref(metadata["issuer_id"], metadata["id"]),
                        "credential_digest": credential_digest(secret), "dpop_ath": ath(secret)})
    secret = vectors[0]["session_grant"]
    dpop = sign_dpop(SEED, secret, "GET", "https://station.example/_arkret/self/account", 1786190400, "opaque-kat-dpop-1", "server-dpop-nonce")
    device_key = Ed25519PrivateKey.from_private_bytes(DEVICE_SEED)
    device_public = b64u(device_key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))
    possession_intent = {
        "operation": "issue_session_grant",
        "request_id": "ak:request:019a0000-0000-7000-8000-000000000021",
        "principal_id": PRINCIPAL, "device_id": DEVICE, "audience_id": AUDIENCE,
        "holder_jkt": base["cnf_jkt"],
    }
    proof = {
        "context": "ak.session_grant_accepted_device_possession_proof.v1", "purpose": "session_grant_issue",
        "request_id": "ak:request:019a0000-0000-7000-8000-000000000021",
        "account_subject": "sha256:" + hashlib.sha256(b"public-account-subject-kat").hexdigest(),
        "account_handoff_grant_digest": "sha256:" + hashlib.sha256(b"public-test-handoff").hexdigest(),
        "account_id": copy.deepcopy(base["account_id"]), "device_id": DEVICE, "audience_id": AUDIENCE,
        "holder_jkt": base["cnf_jkt"], "session_intent_digest": "sha256:" + hashlib.sha256(jcs_text(possession_intent).encode()).hexdigest(),
        "issued_at": NOW, "expires_at": "2026-08-08T12:05:00.000Z",
        "verification_method": "did:webvh:z6mkfixture:fixture.example#" + DEVICE,
    }
    proof_input = (proof["context"] + "\n" + jcs_text(proof)).encode()
    proof["signature"] = b64u(device_key.sign(proof_input))

    def issue_step(vector="issuer_a_standard", request="request-1", **extra):
        return {"op": "issue", "vector": vector, "request_id": request, "intent": {"request_id": request, "audience_id": AUDIENCE}, "now": NOW, "holder_current": True, **extra}

    def refresh_step(**extra):
        return {"op": "refresh", "vector": "refresh_successor", "predecessor": "issuer_a_standard", "intent": {"predecessor_session_grant_ref": grant_ref(ISSUER_A, RECORD), "purpose": "refresh"}, "now": NOW, "holder_current": True, **extra}

    cases = [
        {"name": "issue_response_loss_restart_exact_replay", "steps": [issue_step(expect="success", expect_records=1, expect_draws=1), {"op": "restart"}, issue_step(expect="success", same_outcome_as=0, expect_records=1, expect_draws=1)]},
        {"name": "same_identity_different_intent", "steps": [issue_step(expect="success"), issue_step(intent={"request_id": "request-1", "audience_id": "ak:did_core:webvh:z6mkother"}, expect="duplicate_conflict", expect_records=1)]},
        {"name": "replay_revalidates_current_holder", "steps": [issue_step(expect="success"), issue_step(holder_current=False, expect="unauthenticated", expect_records=1)]},
        {"name": "replay_after_expiry", "steps": [issue_step(expect="success"), issue_step(now="2026-08-08T13:00:00.000Z", expect="session_grant_replay_expired", expect_draws=1)]},
        {"name": "replay_after_revoke", "steps": [issue_step(expect="success"), {"op": "revoke", "vector": "issuer_a_standard", "expect": "success"}, issue_step(expect="session_grant_replay_terminal", expect_draws=1)]},
        {"name": "refresh_response_loss_restart_exact_replay", "steps": [issue_step(expect="success"), refresh_step(expect="success", expect_records=2, expect_draws=2), {"op": "restart"}, refresh_step(expect="success", same_outcome_as=1, expect_records=2, expect_draws=2)]},
        {"name": "refresh_changed_intent_cannot_fork", "steps": [issue_step(expect="success"), refresh_step(expect="success"), refresh_step(intent={"purpose": "changed-refresh"}, expect="predecessor_terminal", expect_records=2)]},
        {"name": "recovery_cannot_refresh", "steps": [issue_step("recovery_candidate", expect="success"), refresh_step(predecessor="recovery_candidate", expect="recovery_refresh_forbidden", expect_records=1)]},
        {"name": "cross_issuer_same_id_isolated", "steps": [issue_step(expect="success"), issue_step("issuer_b_same_record_id", expect="success", expect_records=2), {"op": "introspect", "vector": "issuer_a_standard", "issuer_id": ISSUER_B, "expect": "not_found"}]},
        {"name": "cross_audience_rejected", "steps": [issue_step(expect="success"), {"op": "introspect", "vector": "issuer_a_standard", "audience_id": "ak:did_core:webvh:z6mkother", "expect": "audience_mismatch"}]},
        {"name": "known_request_result_gc_fails_closed", "steps": [issue_step(expect="success"), {"op": "forget_outcome", "issuer_id": ISSUER_A, "request_id": "request-1"}, issue_step(expect="session_grant_replay_indeterminate", expect_draws=1)]},
        {"name": "superseded_credential_not_normal_authority", "steps": [issue_step(expect="success"), refresh_step(expect="success"), {"op": "introspect", "vector": "issuer_a_standard", "expect": "superseded"}]},
    ]
    return {
        "runner": {"kind": "named_suite", "entrypoint": "ak.suite.auth.session_grant_issuer_record.v1"},
        "covers_vectors": ["ak.vector.auth.session_grant_issuer_record.v1", "ak.vector.session_grant.accepted_device_possession.v1"],
        "generated_by": "tools/regenerate_session_grant_fixture.py",
        "identity_contract_ref": "registry/id-kind-registry.json#/issuer_record_identity_contract",
        "model_scope": "Executable conformance reference; fixed public test entropy is never production randomness or native PCR authority.",
        "canonical_public_jwk": canonical,
        "equivalent_non_canonical_jwk_inputs": [json.dumps(jwk, indent=2), json.dumps({"x": jwk["x"], "kty": "OKP", "crv": "Ed25519"})],
        "accepted_vectors": vectors,
        "credential_binding_negative_cases": [
            {"name": "standard_missing_holder", "base_vector": "issuer_a_standard", "omit": ["holder_binding"]},
            {"name": "human_missing_accepted_binding", "base_vector": "issuer_a_standard", "omit": ["device_binding"]},
            {"name": "recovery_with_accepted_binding", "base_vector": "recovery_candidate", "set": {"device_binding": base["device_binding"]}},
            {"name": "standard_with_candidate_holder", "base_vector": "recovery_candidate", "set": {"credential_class": "standard"}},
            {"name": "agent_with_synthetic_device", "base_vector": "agent_runtime", "set": {"device_id": DEVICE}},
            {"name": "agent_missing_resource_ceiling", "base_vector": "agent_runtime", "omit": ["scope_details"]},
            {"name": "unknown_credential_class", "base_vector": "issuer_a_standard", "set": {"credential_class": "unknown"}},
            {"name": "optional_null_forbidden", "base_vector": "issuer_a_standard", "set": {"proof_kind": None}},
        ],
        "ledger_cases": cases,
        "dpop_kat": {"public_test_seed_hex": SEED.hex(), "session_grant": secret, "method": "GET", "uri": "https://station.example/_arkret/self/account", "iat": 1786190400, "jti": "opaque-kat-dpop-1", "nonce": "server-dpop-nonce", "proof_jwt": dpop, "expected_ath": ath(secret)},
        "accepted_device_possession": {"public_test_seed_hex": DEVICE_SEED.hex(), "public_key_b64u": device_public, "intent": possession_intent, "proof": proof, "signing_input_utf8": proof_input.decode()},
        "agent_initial_proof": copy.deepcopy(previous["agent_initial_proof"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    previous = json.loads(FIXTURE.read_text(encoding="utf-8"))
    expected = json.dumps(build_fixture(previous), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if FIXTURE.read_text(encoding="utf-8") != expected:
            raise SystemExit("opaque SessionGrant fixture drift")
        print("opaque SessionGrant fixture: deterministic regeneration verified")
    else:
        FIXTURE.write_text(expected, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
