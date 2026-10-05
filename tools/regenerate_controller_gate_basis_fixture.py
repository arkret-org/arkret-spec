"""Public fixture keys only; no deployed AA ledger, HTTP or SDK execution proof."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from tools.regenerate_crypto_signature_fixture import b64u, unb64u, refresh_jws_input
from tools.regenerate_detached_object_signature_kat import jcs, public_key, KEY_A_SEED

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "spec/v1/artifacts/fixtures/account-status-issuer-ledger-fixture.json"
STATUSES = ("active", "soft_logged_out", "locked", "suspended", "deactivated", "erasure_pending")


def digest(value):
    return "sha256:" + hashlib.sha256(jcs(value)).hexdigest()


def jws(message):
    v = {"protected_header": {"alg": "Ed25519"}}
    signing = refresh_jws_input(v, message)
    return signing.decode().split(".")[0] + ".." + b64u(Ed25519PrivateKey.from_private_bytes(KEY_A_SEED).sign(signing))


def verify_jws(value, message):
    header, detached, signature = value.split(".")
    if detached or unb64u(header) != jcs({"alg": "Ed25519"}):
        raise ValueError("non-canonical fixture JWS header")
    Ed25519PrivateKey.from_private_bytes(KEY_A_SEED).public_key().verify(unb64u(signature), (header + "." + b64u(message)).encode())


def record(core, seq, status, previous=None):
    value = copy.deepcopy(core)
    for field in ("account_status_record_id", "proof", "reason_code", "previous_account_status_record_id"):
        value.pop(field, None)
    value.update(status_seq=seq, status=status, issued_at=f"2026-08-{seq+5:02d}T00:00:00.000Z", effective_at=f"2026-08-{seq+5:02d}T00:00:00.000Z")
    if previous:
        value["previous_account_status_record_id"] = previous["account_status_record_id"]
    rid = "ak:account_status_record:" + b64u(b"\x01" + hashlib.sha256(jcs(value)).digest())
    proof = {"kind": "detached_jws", "verification_method": "did:webvh:z6mkfixtureaccountauthority:authority.example#account-status-2026", "payload_digest": digest(value), "created_at": value["issued_at"]}
    binding = {"context": "ak.account_status_record_proof.v1", "payload_digest": proof["payload_digest"], "verification_method": proof["verification_method"], "created_at": proof["created_at"]}
    proof["jws"] = jws(jcs(binding))
    return dict(value, account_status_record_id=rid, proof=proof)


def gate_bytes(gate):
    value = copy.deepcopy(gate)
    del value["proof"]["jws"]
    return b"ak.controller_account_gate.v1\n" + jcs(value)


def basis_digest_for_gate(gate):
    # accepted_id is a derived preimage key, never an extra Gate wire member.
    return digest({"principal_id": gate["principal_id"], "accepted_id": gate["authority_id"], "status": gate["status"], "basis": gate["basis"]})


def build(data):
    core = copy.deepcopy(data["ledger"]["records"][0]["record"])
    core["account_id"]["station_id"] = core["account_authority_id"]
    initial = record(core, 1, "active")
    locked = record(initial, 2, "locked", initial)
    cases = []
    for status in ("initial",) + STATUSES:
        head = initial if status == "initial" else record(initial, 3, status, locked) if status == "active" else record(initial, 2, status, initial)
        basis = {"kind": "account_binding_default", "binding_version": head["binding_version"], "binding_receipt_digest": "sha256:" + "b" * 64} if status == "initial" else {"kind": "account_status_record", "account_status_record_id": head["account_status_record_id"], "status_record_digest": digest(head)}
        gate = {"schema": "ak.schema.controller_account_gate_attestation.v1", "principal_id": head["account_id"]["principal_id"], "eligibility": "active" if head["status"] == "active" else "inactive", "status": head["status"], "basis": basis, "basis_digest": digest(basis), "authority_id": head["account_authority_id"], "verification_method": "did:webvh:z6mkfixtureaccountauthority:authority.example#account-status-2026", "issued_at": "2026-09-20T00:00:00.000Z", "expires_at": "2026-09-20T00:05:00.000Z", "proof": {"kind": "detached_jws", "jws": ""}}
        gate["basis_digest"] = basis_digest_for_gate(gate)
        gate["proof"]["jws"] = jws(gate_bytes(gate))
        expected_binding = {k: copy.deepcopy(initial[k]) for k in ("account_id", "account_authority_id", "binding_version", "principal_control_realm_id")}
        cases.append({"expected_private_binding": expected_binding, "name": "initial_active_default" if status == "initial" else "successor_" + status, "private_current_record": head, "private_predecessor": None if status == "initial" else locked if status == "active" else initial, "gate": gate})
    decisions = [
        {"name": "stable_absence_active", "binding": expected_binding, "head": None, "user_active": True, "allowed": True},
        {"name": "stable_absence_inactive", "binding": expected_binding, "head": None, "user_active": False, "allowed": False},
        {"name": "exact_initial_active", "binding": expected_binding, "head": initial, "user_active": True, "allowed": True},
        {"name": "restored_active_is_successor", "binding": expected_binding, "head": cases[1]["private_current_record"], "user_active": True, "allowed": False},
    ]
    for field in ("account_id", "account_authority_id", "binding_version", "principal_control_realm_id"):
        wrong = copy.deepcopy(expected_binding)
        if field == "account_id": wrong[field]["station_id"] = "ak:did_core:webvh:zOtherStation"
        elif field == "binding_version": wrong[field] += 1
        else: wrong[field] = "different_private_coordinate"
        decisions.append({"name": "wrong_" + field, "binding": wrong, "head": initial, "user_active": True, "allowed": False})
    return {"source_private_seed_b64u": b64u(KEY_A_SEED), "public_key_b64u": public_key(KEY_A_SEED), "scope": "conformance bytes and issuer-source relationships only; not deployed AA ledger or transport", "cases": cases, "default_decisions": decisions}


def default_allowed(binding, head, user_active):
    if not user_active:
        return False
    if head is None:
        return True
    return head["status_seq"] == 1 and head["status"] == "active" and "previous_account_status_record_id" not in head and all(head[k] == v for k, v in binding.items())


def verify_case(case):
    head, gate = case["private_current_record"], case["gate"]
    if {k: head[k] for k in case["expected_private_binding"]} != case["expected_private_binding"]:
        raise ValueError("complete private binding mismatch")
    if head["account_id"]["station_id"] != head["account_authority_id"]:
        raise ValueError("owning Station mismatch")
    core = {k: v for k, v in head.items() if k not in ("account_status_record_id", "proof")}
    if head["account_status_record_id"] != "ak:account_status_record:" + b64u(b"\x01" + hashlib.sha256(jcs(core)).digest()):
        raise ValueError("record identity")
    proof = head["proof"]
    binding = {"context": "ak.account_status_record_proof.v1", "payload_digest": proof["payload_digest"], "verification_method": proof["verification_method"], "created_at": proof["created_at"]}
    if proof["payload_digest"] != digest(core) or proof["created_at"] != head["issued_at"]:
        raise ValueError("record proof metadata")
    verify_jws(proof["jws"], jcs(binding))
    if head["status_seq"] == 1:
        if head["status"] != "active" or "previous_account_status_record_id" in head:
            raise ValueError("invalid initial binding head")
    else:
        previous = case["private_predecessor"]
        if not previous or previous["status_seq"] + 1 != head["status_seq"] or head["previous_account_status_record_id"] != previous["account_status_record_id"]:
            raise ValueError("not the original predecessor")
    basis = gate["basis"]
    if head["status_seq"] == 1:
        if basis != {"kind": "account_binding_default", "binding_version": head["binding_version"], "binding_receipt_digest": "sha256:" + "b" * 64}:
            raise ValueError("initial binding basis")
    elif basis != {"kind": "account_status_record", "account_status_record_id": head["account_status_record_id"], "status_record_digest": digest(head)}:
        raise ValueError("original complete signed record basis")
    if gate["status"] != head["status"] or gate["eligibility"] != ("active" if head["status"] == "active" else "inactive") or gate["principal_id"] != head["account_id"]["principal_id"] or gate["authority_id"] != head["account_authority_id"]:
        raise ValueError("private current source mismatch")
    if gate["basis_digest"] != basis_digest_for_gate(gate):
        raise ValueError("basis digest")
    verify_jws(gate["proof"]["jws"], gate_bytes(gate))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = json.loads(FIXTURE.read_text())
    expected = build(data)
    for case in expected["cases"]:
        verify_case(case)
    for decision in expected["default_decisions"]:
        if default_allowed(decision["binding"], decision["head"], decision["user_active"]) != decision["allowed"]:
            raise ValueError("default source decision")
    if args.check:
        if data.get("controller_gate_basis_contract") != expected:
            raise SystemExit("controller gate basis transcript drift")
    else:
        data["controller_gate_basis_contract"] = expected
        FIXTURE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
