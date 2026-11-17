"""Sole pure native-scope-source bytes; native DB, role and source qualification are external.

The native owner supplies complete installed rows and genuine origin/caller cut.
These functions never manufacture membership, native current, a fence or an accept.
"""
import copy
import hashlib
from datetime import datetime

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from tools.content_history import b64, jcs, unb64
from tools.recovery_scope_cleanup import request_digest

DOMAIN = b"ak.mls.native_scope_source.v1\n"
BASIS_DOMAIN = "ak.mls.native_scope_basis.v1"
PURPOSES = {"mls_admission", "sidecar_view", "group_state_material", "roster_authority", "welcome_bootstrap", "payload_delivery"}


def _ordered_unique(values):
    return [value for _, value in sorted({jcs(v): v for v in values}.items())]


def covered_authorization(endpoint):
    """Actual native predicate ignores raw MLS key; do not change its identity."""
    if set(endpoint) not in ({"actor_id", "endpoint", "authorization_event_ref"},
                             {"actor_id", "endpoint", "authorization_event_ref", "signature_key_base64url"}):
        raise ValueError("unknown/incomplete native fence identity")
    return {key: copy.deepcopy(endpoint[key]) for key in ("actor_id", "endpoint", "authorization_event_ref")}


def installed_fence_projection(first_source, complete_covered):
    """Called only for a real installed fence, never for an FP-only reservation.

    Native qualification of canonical first_source and complete coverage is not
    inferred here. Reuse the original I formula; do not invent a parallel hash.
    """
    authorization = first_source["attestation"]
    actor = authorization["replacement"]["actor_id"]
    covered = _ordered_unique([covered_authorization(e) for e in complete_covered])
    if any(e["actor_id"] != actor for e in covered):
        raise ValueError("fence coverage changed complete subject")
    return {"intent_digest": request_digest(authorization), "covered_authorizations": covered}


def _validate_sidecar_create(basis):
    event = basis["sidecar_create_event_ref"]
    if not isinstance(event, str) or not event.startswith("ak:event:") or len(event) != 53:
        raise ValueError("Sidecar Create reference is not a typed Event")
    if basis["sidecar_id"] != "ak:sidecar:" + event.removeprefix("ak:event:"):
        raise ValueError("Sidecar ID is not its immutable Create Event retype")


def canonical_basis(value):
    value = copy.deepcopy(value)
    allowed = {"domain", "realm_id", "effective_scope", "governance_authority_ref", "genesis_event_ref", "sidecar_membership_basis", "endpoint_fences"}
    if set(value) - allowed or value.get("domain") != BASIS_DOMAIN:
        raise ValueError("invalid closed native G basis")
    required = {"domain", "realm_id", "effective_scope", "governance_authority_ref", "endpoint_fences"}
    if not required <= set(value) or value["effective_scope"].get("realm_id") != value["realm_id"]:
        raise ValueError("native G basis target mismatch")
    sidecar = value["effective_scope"].get("kind") == "sidecar"
    if ("sidecar_membership_basis" in value) != sidecar:
        raise ValueError("native G basis membership scope misplaced")
    if sidecar and value["sidecar_membership_basis"]["sidecar_id"] != value["effective_scope"]["sidecar_id"]:
        raise ValueError("native G basis Sidecar mismatch")
    entries = value["endpoint_fences"]
    for entry in entries:
        if set(entry) != {"intent_digest", "covered_authorizations"}:
            raise ValueError("fence projection contains mirrors or lacks source identity")
        entry["covered_authorizations"] = _ordered_unique([covered_authorization(e) for e in entry["covered_authorizations"]])
    entries.sort(key=lambda e: e["intent_digest"].encode("utf-8"))
    if len({e["intent_digest"] for e in entries}) != len(entries):
        raise ValueError("duplicate installed native intent")
    if "sidecar_membership_basis" in value:
        basis = value["sidecar_membership_basis"]
        _validate_sidecar_create(basis)
        basis["candidate_joins"].sort(key=lambda e: jcs(e["agent_actor_id"]))
        if len({jcs(e["agent_actor_id"]) for e in basis["candidate_joins"]}) != len(basis["candidate_joins"]):
            raise ValueError("multiple current joins of one candidate")
    return value


def basis_digest(value):
    return "sha256:" + hashlib.sha256(jcs(canonical_basis(value))).hexdigest()


def signing_bytes(request, qualification):
    return DOMAIN + jcs({"request": request, "qualification": qualification})


def _moment(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _is_claim(source):
    if not isinstance(source, dict):
        raise ValueError("native source is not its closed typed projection")
    if set(source) == {"authorization_event_ref"}:
        event = source["authorization_event_ref"]
        if not isinstance(event, str) or not event.startswith("ak:event:") or len(event) != 53:
            raise ValueError("native source must name an original typed authorization Event")
        return False
    if set(source) != {"claim_id"}:
        raise ValueError("claim selector has unknown/copied native fields")
    return True


def verify_source_bytes(request, response, owning_method, now, expected_query, peer_deadline):
    """Byte-only verifier after independent native/source/Service qualification.

    expected_query is rebuilt by the real G owner at its final cut, not caller
    input or a verified bool. owning_method is independently qualified native H
    history. Schema and complete original RFC/caller/DB checks remain separate.
    """
    if request != expected_query:
        raise ValueError("native G basis/original/query changed at final cut")
    nonce = request["query_nonce_base64url"]
    if len(unb64(nonce)) != 32 or b64(unb64(nonce)) != nonce:
        raise ValueError("noncanonical source challenge")
    if request["purpose"] not in PURPOSES:
        raise ValueError("unregistered native source use")
    if set(response) != {"qualification", "signature"}:
        raise ValueError("source response echoes request or has unknown members")
    signature = response["signature"]
    if (owning_method["station_id"] != request["destination_id"]
            or signature["kid"] != owning_method["verification_method"]
            or signature.get("signature_algorithm", "Ed25519") != "Ed25519"):
        raise ValueError("native source is not its actual owning H method")
    qualification = response["qualification"]
    if set(qualification) - {"desired_qualifications", "endpoint_qualifications", "issued_at", "expires_at"}:
        raise ValueError("qualification echoes request or has unknown fields")
    Ed25519PublicKey.from_public_bytes(unb64(owning_method["public_key_base64url"])).verify(
        unb64(signature["signature"]), signing_bytes(request, qualification))
    start, end, at, deadline = map(_moment, [qualification["issued_at"], qualification["expires_at"], now, peer_deadline])
    if not start <= at < end <= deadline:
        raise ValueError("source/peer window closed")
    sources, results = request["endpoint_sources"], qualification["endpoint_qualifications"]
    if len(sources) != len(results):
        raise ValueError("native source result length changed")
    for source, result in zip(sources, results):
        _is_claim(source)
        if result["state"] == "ineligible":
            if set(result) != {"state"}: raise ValueError("negative result invents endpoint data")
            continue
        if result["state"] != "qualified": raise ValueError("unknown endpoint result")
        claim = _is_claim(source)
        if claim:
            if set(result) != {"state", "endpoint", "keypackage_ref"}:
                raise ValueError("selected package/endpoint binding missing or mirrored")
            endpoint = result["endpoint"]
        else:
            if set(result) != {"state"}:
                raise ValueError("native endpoint context must not be echoed")
            continue
        actor = endpoint["actor_id"]
        if actor.get("kind") != "account" or actor["account_id"]["station_id"] != request["destination_id"]:
            raise ValueError("endpoint is not a complete own-H Account/Agent")
    sidecar = request["effective_scope"]["kind"] == "sidecar"
    if ("desired_qualifications" in qualification) != sidecar:
        raise ValueError("Sidecar qualification projection missing or scope misplaced")
    if sidecar:
        basis = request["sidecar_membership_basis"]
        _validate_sidecar_create(basis)
        candidates = basis["candidate_joins"]
        if candidates != sorted(candidates, key=lambda e: jcs(e["agent_actor_id"])) or len({jcs(e["agent_actor_id"]) for e in candidates}) != len(candidates):
            raise ValueError("noncanonical/incomplete candidate identity set")
        if basis["controller_account_id"]["station_id"] != request["destination_id"]:
            raise ValueError("Sidecar controller is not fixed owning H")
        if any(e["agent_actor_id"]["kind"] != "account" or e["agent_actor_id"]["account_id"]["station_id"] != request["destination_id"] for e in candidates):
            raise ValueError("Sidecar candidates changed fixed owning H")
        desired = qualification["desired_qualifications"]
        if len(desired) != len(candidates) or any(type(value) is not bool for value in desired):
            raise ValueError("desired qualifications must cover each exact candidate once")
    return qualification
