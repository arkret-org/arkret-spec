"""Executable opaque SessionGrant reference with issuer-owned durable state.

This is a conformance model, not a production issuer or a source of authority.
Trusted current-account/endpoint decisions are explicit model inputs; DPoP
cryptography, exact credential binding and issuer transitions are executed.
"""

from __future__ import annotations

import base64
import binascii
import copy
import hashlib
import json
import re
import secrets
import threading
import uuid
from datetime import datetime
from typing import Any, Callable

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


GRANT_PREFIX = "ak:session_grant:"
ID_RE = re.compile(r"^ak:session_grant:[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
SECRET_RE = re.compile(r"^[A-Za-z0-9_-]{42}[AEIMQUYcgkosw048]$")
TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
PRIVATE_JWK_MEMBERS = {"d", "k", "p", "q", "dp", "dq", "qi", "oth"}


class GrantError(ValueError):
    """Stable conformance rejection label."""


def jcs_text(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        if abs(value) > 9_007_199_254_740_991:
            raise ValueError("JCS integer is outside the interoperable IEEE-754 range")
        return str(value)
    if isinstance(value, float):
        raise ValueError("floating-point values are not supported by this KAT checker")
    if isinstance(value, str):
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
        encoded.encode("utf-8", errors="strict")
        return encoded
    if isinstance(value, list):
        return "[" + ",".join(jcs_text(item) for item in value) + "]"
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("JCS object property names must be strings")
        return "{" + ",".join(
            jcs_text(key) + ":" + jcs_text(value[key])
            for key in sorted(value, key=lambda key: key.encode("utf-16-be", errors="strict"))
        ) + "}"
    raise ValueError(f"unsupported JCS value type: {type(value).__name__}")


def b64u(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def strict_base64url(value: object, expected_length: int) -> bytes:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise GrantError("noncanonical_base64url")
    try:
        decoded = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    except (ValueError, binascii.Error) as exc:
        raise GrantError("noncanonical_base64url") from exc
    if b64u(decoded) != value or len(decoded) != expected_length:
        raise GrantError("noncanonical_base64url")
    return decoded


def secret_from_random(random_bytes: bytes) -> str:
    if not isinstance(random_bytes, bytes) or len(random_bytes) != 32:
        raise GrantError("secret_requires_32_octets")
    return b64u(random_bytes)


def validate_secret(value: object) -> str:
    if not isinstance(value, str) or not SECRET_RE.fullmatch(value):
        raise GrantError("invalid_session_grant_secret")
    strict_base64url(value, 32)
    return value


def validate_id(value: object) -> str:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise GrantError("invalid_session_grant_id")
    parsed = uuid.UUID(value[len(GRANT_PREFIX):])
    if parsed.version != 7 or parsed.variant != uuid.RFC_4122:
        raise GrantError("invalid_session_grant_id")
    return value


def grant_ref(issuer_id: str, record_id: str) -> dict[str, str]:
    validate_id(record_id)
    if not isinstance(issuer_id, str) or not issuer_id.startswith("ak:did_core:"):
        raise GrantError("invalid_issuer")
    return {"issuer_id": issuer_id, "id": record_id}


def validate_ref(value: object) -> tuple[str, str]:
    if not isinstance(value, dict) or set(value) != {"issuer_id", "id"}:
        raise GrantError("invalid_session_grant_ref")
    valid = grant_ref(value["issuer_id"], value["id"])
    return valid["issuer_id"], valid["id"]


def credential_digest(secret: str) -> str:
    return "sha256:" + hashlib.sha256(validate_secret(secret).encode("ascii")).hexdigest()


def ath(secret: str) -> str:
    return b64u(hashlib.sha256(validate_secret(secret).encode("ascii")).digest())


def canonical_public_jwk(value: object) -> tuple[dict[str, Any], str]:
    if not isinstance(value, str):
        raise GrantError("public_jwk_must_be_jcs_string")
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise GrantError("invalid_public_jwk") from exc
    if not isinstance(parsed, dict) or PRIVATE_JWK_MEMBERS.intersection(parsed):
        raise GrantError("private_or_symmetric_jwk")
    if parsed.get("kty") != "OKP" or parsed.get("crv") != "Ed25519" or set(parsed) != {"kty", "crv", "x"}:
        raise GrantError("unsupported_public_jwk")
    strict_base64url(parsed.get("x"), 32)
    return parsed, jcs_text(parsed)


def jwk_thumbprint(value: str) -> str:
    parsed, _ = canonical_public_jwk(value)
    return b64u(hashlib.sha256(jcs_text({key: parsed[key] for key in ("crv", "kty", "x")}).encode()).digest())


def timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not TIMESTAMP_RE.fullmatch(value):
        raise GrantError("noncanonical_timestamp")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def validate_metadata(metadata: dict[str, Any]) -> None:
    validate_id(metadata.get("id"))
    grant_ref(metadata.get("issuer_id"), metadata["id"])
    account = metadata.get("account_id")
    if not isinstance(account, dict) or set(account) != {"principal_id", "station_id"}:
        raise GrantError("invalid_account_binding")
    if timestamp(metadata.get("not_before")) >= timestamp(metadata.get("expires_at")):
        raise GrantError("empty_credential_window")
    scopes = metadata.get("scopes")
    if not isinstance(scopes, list) or not scopes or any(not isinstance(scope, str) or not scope for scope in scopes):
        raise GrantError("invalid_scopes")
    if scopes != sorted(set(scopes), key=lambda scope: scope.encode("utf-8")):
        raise GrantError("noncanonical_scopes")
    _, canonical = canonical_public_jwk(metadata.get("session_public_key"))
    if canonical != metadata["session_public_key"]:
        raise GrantError("noncanonical_public_jwk")
    if metadata.get("cnf_jkt") != jwk_thumbprint(canonical):
        raise GrantError("holder_thumbprint_mismatch")
    if not isinstance(metadata.get("session_id"), str) or not metadata["session_id"] or metadata["session_id"] == metadata["id"]:
        raise GrantError("invalid_session_chain_id")
    holder = metadata.get("holder_binding")
    if not isinstance(holder, dict):
        raise GrantError("invalid_holder_binding")
    kind = holder.get("kind")
    credential_class = metadata.get("credential_class")
    if credential_class == "recovery_session":
        if kind != "recovery_candidate_device" or set(holder) != {"kind", "device_id"}:
            raise GrantError("invalid_recovery_holder")
        if "device_binding" in metadata or "scope_details" in metadata:
            raise GrantError("recovery_carries_accepted_authority")
        if "device_id" in metadata and metadata["device_id"] != holder["device_id"]:
            raise GrantError("candidate_device_mismatch")
        if (timestamp(metadata["expires_at"]) - timestamp(metadata["not_before"])).total_seconds() > 900:
            raise GrantError("recovery_window_exceeded")
    elif credential_class == "standard" and kind == "human_device":
        if set(holder) != {"kind", "device_binding"} or not isinstance(metadata.get("device_binding"), dict):
            raise GrantError("human_requires_accepted_binding")
        binding = metadata["device_binding"]
        if set(binding) != {"device_id", "authorization_event_id", "model_generation_ref"}:
            raise GrantError("invalid_accepted_binding")
        if holder["device_binding"] != binding["device_id"] or ("device_id" in metadata and metadata["device_id"] != binding["device_id"]):
            raise GrantError("human_device_mismatch")
        if "scope_details" in metadata:
            raise GrantError("human_carries_agent_scope")
    elif credential_class == "standard" and kind == "agent_runtime":
        if set(holder) != {"kind", "agent_id", "agent_key_authorization_ref", "verification_method"}:
            raise GrantError("invalid_agent_endpoint")
        if holder["agent_id"] != account["principal_id"] or "device_binding" in metadata or "device_id" in metadata:
            raise GrantError("agent_carries_synthetic_device")
        scope = metadata.get("scope_details")
        required = {"controller_principal_id", "agent_key_authorization_ref", "realm_ids", "strand_ids", "resources", "constraints", "capability_grant_refs", "policy_refs"}
        if not isinstance(scope, dict) or not required <= set(scope):
            raise GrantError("agent_scope_incomplete")
        if scope["agent_key_authorization_ref"] != holder["agent_key_authorization_ref"]:
            raise GrantError("agent_authorization_mismatch")
    else:
        raise GrantError("credential_class_holder_mismatch")


def sign_dpop(seed: bytes, secret: str, method: str, uri: str, issued: int, jti: str, nonce: str | None = None) -> str:
    key = Ed25519PrivateKey.from_private_bytes(seed)
    from cryptography.hazmat.primitives import serialization
    public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    header = {"alg": "EdDSA", "typ": "dpop+jwt", "jwk": {"crv": "Ed25519", "kty": "OKP", "x": b64u(public)}}
    claims = {"htm": method, "htu": uri, "iat": issued, "jti": jti, "ath": ath(secret)}
    if nonce is not None:
        claims["nonce"] = nonce
    signing = b64u(jcs_text(header).encode()) + "." + b64u(jcs_text(claims).encode())
    return signing + "." + b64u(key.sign(signing.encode("ascii")))


def verify_dpop(proof: str, secret: str, metadata: dict[str, Any], method: str, uri: str,
                now: int, seen: set[tuple[str, str]], nonce: str | None = None) -> None:
    try:
        parts = proof.split(".")
        if len(parts) != 3:
            raise GrantError("invalid_dpop")
        header = json.loads(base64.urlsafe_b64decode(parts[0] + "=" * (-len(parts[0]) % 4)))
        claims = json.loads(base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4)))
        if header.get("typ") != "dpop+jwt" or header.get("alg") != "EdDSA":
            raise GrantError("invalid_dpop_header")
        jwk, canonical = canonical_public_jwk(jcs_text(header.get("jwk")))
        public = Ed25519PublicKey.from_public_bytes(strict_base64url(jwk["x"], 32))
        public.verify(strict_base64url(parts[2], 64), (parts[0] + "." + parts[1]).encode("ascii"))
    except (ValueError, TypeError, KeyError, InvalidSignature, json.JSONDecodeError) as exc:
        if isinstance(exc, GrantError):
            raise
        raise GrantError("invalid_dpop_signature") from exc
    if jwk_thumbprint(canonical) != metadata["cnf_jkt"]:
        raise GrantError("holder_thumbprint_mismatch")
    if claims.get("ath") != ath(secret):
        raise GrantError("dpop_ath_mismatch")
    if claims.get("htm") != method or claims.get("htu") != uri:
        raise GrantError("dpop_target_mismatch")
    issued = claims.get("iat")
    if not isinstance(issued, int) or isinstance(issued, bool) or not -30 <= now - issued <= 30:
        raise GrantError("dpop_freshness")
    if not isinstance(claims.get("jti"), str) or not claims["jti"] or (nonce is not None and claims.get("nonce") != nonce):
        raise GrantError("dpop_nonce_or_jti")
    key = (metadata["cnf_jkt"], claims["jti"])
    if key in seen:
        raise GrantError("dpop_replay")
    seen.add(key)


class IssuerLedger:
    """A serializable single logical issuer ledger with exact operation replay."""

    def __init__(self) -> None:
        self.records: dict[tuple[str, str], dict[str, Any]] = {}
        self.operations: dict[tuple[str, str, str], dict[str, Any] | None] = {}
        self.draws = 0
        self._lock = threading.RLock()

    def export(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy({"records": list(self.records.items()), "operations": list(self.operations.items()), "draws": self.draws})

    @classmethod
    def restore(cls, state: dict[str, Any]) -> "IssuerLedger":
        ledger = cls()
        ledger.records = {tuple(key): copy.deepcopy(value) for key, value in state["records"]}
        ledger.operations = {tuple(key): copy.deepcopy(value) for key, value in state["operations"]}
        ledger.draws = state["draws"]
        return ledger

    def _record_status(self, record: dict[str, Any], now: str) -> str:
        if timestamp(now) >= timestamp(record["metadata"]["expires_at"]):
            return "expired"
        return record["state"]

    def _replay(self, key: tuple[str, str, str], intent: str, now: str) -> dict[str, Any] | None:
        if key not in self.operations:
            return None
        operation = self.operations[key]
        if operation is None:
            raise GrantError("session_grant_replay_indeterminate")
        if operation["intent"] != intent:
            raise GrantError("duplicate_conflict")
        record = self.records[tuple(operation["record_key"])]
        status = self._record_status(record, now)
        if status == "expired":
            raise GrantError("session_grant_replay_expired")
        if status != "active":
            raise GrantError("session_grant_replay_terminal")
        return copy.deepcopy(operation["outcome"])

    def _insert(self, metadata: dict[str, Any], random_source: Callable[[int], bytes]) -> dict[str, Any]:
        validate_metadata(metadata)
        key = (metadata["issuer_id"], metadata["id"])
        if key in self.records:
            raise GrantError("record_id_conflict")
        secret = secret_from_random(random_source(32))
        self.draws += 1
        if any(issuer == key[0] and secrets.compare_digest(record["secret"], secret) for (issuer, _), record in self.records.items()):
            raise GrantError("secret_collision")
        record = {"metadata": copy.deepcopy(metadata), "secret": secret, "state": "active", "successor_id": None}
        self.records[key] = record
        return {"session_grant": secret, "session_grant_ref": grant_ref(*key), "metadata": copy.deepcopy(metadata)}

    def issue(self, metadata: dict[str, Any], request_id: str, intent: dict[str, Any], now: str,
              *, holder_current: bool, random_source: Callable[[int], bytes] = secrets.token_bytes) -> dict[str, Any]:
        if not holder_current:
            raise GrantError("unauthenticated")
        with self._lock:
            key = (metadata["issuer_id"], "issue", request_id)
            canonical = jcs_text(intent)
            replay = self._replay(key, canonical, now)
            if replay is not None:
                return replay
            if not timestamp(metadata["not_before"]) <= timestamp(now) < timestamp(metadata["expires_at"]):
                raise GrantError("credential_time_invalid")
            outcome = self._insert(metadata, random_source)
            self.operations[key] = {"intent": canonical, "record_key": [metadata["issuer_id"], metadata["id"]], "outcome": copy.deepcopy(outcome)}
            return outcome

    def exact_record(self, issuer: str, secret: str) -> tuple[tuple[str, str], dict[str, Any]]:
        validate_secret(secret)
        for key, record in self.records.items():
            if key[0] == issuer and secrets.compare_digest(record["secret"], secret):
                return key, record
        raise GrantError("not_found")

    def introspect(self, issuer: str, secret: str, audience: str, now: str,
                   *, holder_current: bool = True) -> dict[str, Any]:
        with self._lock:
            _, record = self.exact_record(issuer, secret)
            if record["metadata"]["audience_id"] != audience:
                raise GrantError("audience_mismatch")
            if not holder_current:
                raise GrantError("unauthenticated")
            status = self._record_status(record, now)
            if status != "active":
                raise GrantError(status)
            if timestamp(now) < timestamp(record["metadata"]["not_before"]):
                raise GrantError("credential_time_invalid")
            return copy.deepcopy(record["metadata"])

    def management_status(self, reference: dict[str, str], now: str) -> str:
        with self._lock:
            key = validate_ref(reference)
            record = self.records.get(key)
            if record is None:
                raise GrantError("not_found")
            return self._record_status(record, now)

    def refresh(self, issuer: str, predecessor_secret: str, successor: dict[str, Any],
                intent: dict[str, Any], now: str, *, holder_current: bool,
                random_source: Callable[[int], bytes] = secrets.token_bytes) -> dict[str, Any]:
        if not holder_current:
            raise GrantError("unauthenticated")
        with self._lock:
            predecessor_key, predecessor = self.exact_record(issuer, predecessor_secret)
            if predecessor["metadata"]["credential_class"] != "standard":
                raise GrantError("recovery_refresh_forbidden")
            canonical = jcs_text(intent)
            key = (issuer, "refresh", predecessor_key[1] + ":" + hashlib.sha256(canonical.encode()).hexdigest())
            replay = self._replay(key, canonical, now)
            if replay is not None:
                return replay
            if self._record_status(predecessor, now) != "active":
                raise GrantError("predecessor_terminal")
            for field in ("issuer_id", "account_id", "audience_id", "session_id", "credential_class", "holder_binding", "device_binding", "scope_details"):
                if successor.get(field) != predecessor["metadata"].get(field):
                    raise GrantError("refresh_ceiling_changed")
            if not set(successor["scopes"]) <= set(predecessor["metadata"]["scopes"]):
                raise GrantError("refresh_ceiling_changed")
            if successor["cnf_jkt"] != predecessor["metadata"]["cnf_jkt"]:
                raise GrantError("refresh_holder_changed")
            if not timestamp(successor["not_before"]) <= timestamp(now) < timestamp(successor["expires_at"]):
                raise GrantError("credential_time_invalid")
            outcome = self._insert(successor, random_source)
            predecessor["state"] = "superseded"
            predecessor["successor_id"] = successor["id"]
            self.operations[key] = {"intent": canonical, "record_key": [issuer, successor["id"]], "outcome": copy.deepcopy(outcome)}
            return outcome

    def revoke(self, reference: dict[str, str], *, caller_current: bool) -> None:
        if not caller_current:
            raise GrantError("unauthenticated")
        with self._lock:
            key = validate_ref(reference)
            record = self.records.get(key)
            if record is None:
                raise GrantError("not_found")
            if record["state"] == "active":
                record["state"] = "revoked"
