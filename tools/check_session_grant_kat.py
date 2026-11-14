#!/usr/bin/env python3
"""Recompute opaque SessionGrant KATs and retained independent holder proofs."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.check_opaque_session_grant import (
    ARTIFACTS, CLAIMS_SCHEMA_PATH, COMMON_IDS_PATH, CONTRACT_PATH, FIXTURE_PATH,
    check_documents, load_json, run_ledger_cases,
)
from tools.session_grant_reference import jcs_text, strict_base64url as _strict_base64url


def check_repository() -> list[str]:
    errors = check_documents(
        load_json(FIXTURE_PATH), load_json(CONTRACT_PATH),
        load_json(CLAIMS_SCHEMA_PATH), load_json(COMMON_IDS_PATH),
    )
    errors.extend(check_agent_initial_proof())
    return errors


def check_agent_initial_proof() -> list[str]:
    from datetime import datetime, timedelta
    import jsonschema
    from referencing import Registry, Resource
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.exceptions import InvalidSignature

    row = load_json(FIXTURE_PATH)["agent_initial_proof"]
    request = copy.deepcopy(row["request"])
    schemas = CLAIMS_SCHEMA_PATH.parent
    registry = Registry().with_resources(
        (path.as_uri(), Resource.from_contents(load_json(path)))
        for path in schemas.glob("*.json")
    )
    validator = jsonschema.Draft202012Validator(
        {"$ref": CLAIMS_SCHEMA_PATH.as_uri() + "#/$defs/AgentSessionGrantRequestBody"},
        registry=registry,
    )
    errors = [f"agent request schema: {e.message}" for e in validator.iter_errors(request)]
    forbidden_device_request = copy.deepcopy(request)
    forbidden_device_request["device_id"] = "ak:device:0196419b-0000-7000-8000-000000000001"
    if validator.is_valid(forbidden_device_request):
        errors.append("agent request accepts forbidden synthetic device_id")
    holder_validator = jsonschema.Draft202012Validator(
        {"$ref": (schemas / "principal-operations.schema.json").as_uri() + "#/$defs/session_grant_holder_binding"},
        registry=registry,
    )
    agent_holder = {
        "kind": "agent_runtime",
        "agent_id": request["principal_id"],
        "agent_key_authorization_ref": request["agent_key_authorization_ref"],
        "verification_method": request["proof"]["verification_method"],
    }
    if not holder_validator.is_valid(agent_holder):
        errors.append("agent holder binding rejects the canonical three-field endpoint")
    if holder_validator.is_valid(dict(agent_holder, device_id=forbidden_device_request["device_id"])):
        errors.append("agent holder binding accepts forbidden synthetic device_id")
    proof = request["proof"]
    signature = _strict_base64url(proof.pop("signature"), 64)
    proof_bytes = jcs_text(proof).encode()
    if proof_bytes.decode() != row["proof_canonical_bytes_utf8"]:
        errors.append("agent proof canonical bytes mismatch")
    public = Ed25519PublicKey.from_public_bytes(_strict_base64url(row["runtime_public_key_b64u"], 32))
    try:
        public.verify(signature, proof_bytes)
    except InvalidSignature:
        errors.append("agent proof signature invalid")
    changed = dict(proof, issued_at="2026-09-09T00:00:00.001Z")
    try:
        public.verify(signature, jcs_text(changed).encode())
        errors.append("agent proof accepted a changed signed time")
    except InvalidSignature:
        pass
    digest = proof.pop("request_canonical_digest")
    canonical_request = jcs_text(request)
    if canonical_request != row["request_canonical_bytes_utf8"]:
        errors.append("agent request canonical bytes mismatch")
    if digest != row["request_digest"] or digest != "sha256:" + hashlib.sha256(canonical_request.encode()).hexdigest():
        errors.append("agent request digest mismatch")
    for field in ("issued_at", "expires_at"):
        invalid = copy.deepcopy(row["request"])
        del invalid["proof"][field]
        if validator.is_valid(invalid):
            errors.append(f"agent schema accepts missing {field}")
    invalid = copy.deepcopy(row["request"])
    invalid["proof"]["nonce"] = "forbidden"
    if validator.is_valid(invalid):
        errors.append("agent schema accepts extra nonce")
    for case in row["time_cases"]:
        issued = datetime.fromisoformat(case.get("issued_at", proof["issued_at"]))
        expires = datetime.fromisoformat(case.get("expires_at", proof["expires_at"]))
        now = datetime.fromisoformat(case["now"])
        accepted = timedelta(0) < expires-issued <= timedelta(seconds=300) and issued <= now+timedelta(seconds=30) and now < expires
        if accepted != case["accepted"]:
            errors.append(f"agent time case {case['name']} mismatch")
    return errors


def main() -> int:
    try:
        errors = check_repository()
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"session-grant KAT checker failed to load inputs: {exc}", file=sys.stderr)
        return 1
    for error in errors:
        print(f"session-grant KAT: {error}", file=sys.stderr)
    if errors:
        print(f"session-grant KAT: {len(errors)} error(s)", file=sys.stderr)
        return 1
    print("session-grant KAT: opaque bytes, issuer ledger transitions, schemas and holder proofs verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
