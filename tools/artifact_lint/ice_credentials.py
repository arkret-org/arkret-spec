"""Executable ICE issuance KAT and closed-request lifecycle checks."""

from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import datetime, timezone

from .core import ARTIFACTS, SPEC_ROOT, Lint, canonical_json, load_json, read_text, schema_validator

FIXTURE = ARTIFACTS / "fixtures/ice-credential-lifecycle-fixture.json"
SCHEMA = ARTIFACTS / "schemas/media-operations.schema.json"
PROSE = SPEC_ROOT / "zh/crypto-media/webrtc-signaling.md"
FIELDS = {"realm_id", "call_id", "actor_id", "device_id", "mode"}
PHASES = {"first", "refresh", "parallel", "ice_restart", "cold_recovery", "expired_recovery", "new_device", "new_account", "new_station", "new_call", "new_realm", "new_issuer"}
TRANSITIONS = {
    "new_configuration": ["allocate_with_new_username", "ice_restart", "select_new_pair", "migrate_rtp", "delete_old_allocation_with_old_auth_refresh_lifetime_zero"],
    "stale_nonce": ["retry_turn_request_with_challenge_nonce"],
    "old_path_expired": ["do_not_extend_expiry", "recover_or_graceful_hangup"],
    "identity_or_membership_revoked": ["deny_configuration", "deny_media"],
    "call_participation_revoked": ["deny_media_refresh", "deny_final_media_delivery", "do_not_treat_turn_bearer_as_authority"],
    "secret_rotation": ["sign_new_with_current_secret", "verify_old_until_original_expiry", "do_not_extend_expiry"],
}


def derive(request, service_id, bucket, nonce_hex, secret_hex):
    nonce = bytes.fromhex(nonce_hex)
    if len(nonce) < 16:
        raise ValueError("issuance nonce must have at least 128 bits")
    context = {key: request[key] for key in FIELDS - {"mode"}}
    bucket_at = datetime.fromtimestamp(bucket, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    context.update(media_service_id=service_id, ice_bucket=bucket_at, nonce=nonce_hex)
    tag = hmac.new(bytes.fromhex(secret_hex), canonical_json(context).encode(), hashlib.sha256).digest()[:16]
    return "ak_pseudonym_call_" + base64.urlsafe_b64encode(tag).rstrip(b"=").decode()


def check_ice_credentials(lint: Lint) -> None:
    data = load_json(lint, FIXTURE)
    schema = load_json(lint, SCHEMA)
    if not isinstance(data, dict) or not isinstance(schema, dict):
        return
    try:
        body = schema["$defs"]["media_ice_config_request_body"]
        if set(body["properties"]) != FIELDS or set(body["required"]) != FIELDS or body["additionalProperties"] is not False:
            raise ValueError("ICE request must remain the closed five-field body")
        validator = schema_validator(SCHEMA, "#/$defs/media_ice_config_request_body")
        cases = data["issuances"]
        if {case["name"] for case in cases} != PHASES or len(cases) != len(PHASES):
            raise ValueError("issuance phases are incomplete or duplicated")
        seen_nonces, seen_tags = set(), set()
        for case in cases:
            if list(validator.iter_errors(case["request_body"])):
                raise ValueError("issuance request violates the closed schema: " + case["name"])
            nonce = case["test_nonce_hex"]
            if nonce in seen_nonces:
                raise ValueError("issuances reuse a nonce")
            seen_nonces.add(nonce)
            issued = case["issued_at_unix"]
            bucket = issued // 300 * 300
            tag = derive(case["request_body"], case["media_service_id"], bucket, nonce, data["test_pseudonym_secret_hex"])
            username = str(issued + case["ttl_seconds"]) + ":" + tag
            credential = base64.b64encode(hmac.new(bytes.fromhex(data["test_turn_secret_hex"]), username.encode(), hashlib.sha256).digest()).decode()
            if tag in seen_tags or case["expected_username"] != username or case["expected_credential"] != credential:
                raise ValueError("fresh issuance or HMAC KAT mismatch: " + case["name"])
            seen_tags.add(tag)
        probes = data["request_cases"]
        if {case["name"] for case in probes} != {"closed", "pseudonym_echo", "username_echo", "credential_echo", "participant_echo", "recovery_ticket", "bare_actor"} or len(probes) != 7:
            raise ValueError("closed request probes are incomplete or duplicated")
        for case in probes:
            valid = not list(validator.iter_errors(case["request_body"]))
            if valid != case["valid"]:
                raise ValueError("closed request probe mismatch: " + case["name"])
        transitions = {case["name"]: case["actions"] for case in data["transitions"]}
        if transitions != TRANSITIONS or len(data["transitions"]) != len(TRANSITIONS):
            raise ValueError("allocation/authorization lifecycle drift")
    except (KeyError, TypeError, ValueError) as exc:
        lint.fail(FIXTURE, str(exc))
    prose = read_text(PROSE)
    for forbidden in ("Refresh 请求 MUST 与原 ICE config 请求一致地携带", "同一 active call leg MAY 复用 pseudonym", "然后再 `CREATE-PERMISSION` 释放"):
        if forbidden in prose:
            lint.fail(PROSE, "retired pseudonym echo/reuse or allocation deletion rule")
    for required in ("每次 ICE config 签发", "至少 128 bit CSPRNG fresh nonce", "Refresh(LIFETIME=0)", "438 Stale Nonce", "不建立或恢复 accepted leg", "ice-credential-lifecycle-fixture.json"):
        if required not in prose:
            lint.fail(PROSE, "missing ICE lifecycle rule: " + required)
