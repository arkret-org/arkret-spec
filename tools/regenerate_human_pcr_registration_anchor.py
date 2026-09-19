#!/usr/bin/env python3
"""Rebuild the human PCR genesis registration evidence from real material.

1105 replaced the unsatisfiable ``did_inception`` reference with an admission
branch that resolves the create Event's signing key from the genesis unit's typed
``principal_registration_anchor``. Nothing in the repository carried such an
anchor: ``initial_resolution.method_history_head`` and ``version_id`` were
hand-written constants, the create proof named a device DID URL that the
registration exception forbids, and the identity-root control transcript still
carried three members the schema retired plus five placeholder digests. A branch
whose registration evidence cannot be constructed has not been shown to be
reachable, so this script derives the whole chain and writes it back.

Everything here is recomputed from published material. The single value that is
asserted rather than derived is the SCID segment ``z6mkfixture``, which
``registry/test-material-registry.json`` reserves precisely because every
conformance did:webvh SCID is hand-written; SCID derivation itself is exercised
by ``did-webvh-v1-fixture.json``. Every other webvh relation in the anchor -- the
entry-hash versionId, the prerotation commitment, the terminal history head, the
root controller proof -- is derived from the entry bytes this script emits.
"""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "spec/v1/artifacts"
CONTENT_BOUND = ARTIFACTS / "fixtures/content-bound-event-id-fixture.json"
PCR_GENESIS = ARTIFACTS / "fixtures/pcr-genesis-fixture.json"
TEST_MATERIAL = ARTIFACTS / "registry/test-material-registry.json"

B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

# registry/test-material-registry.json rows. Both private keys ship with the
# specification, so a signature under either proves nothing about a signer; they
# exist so a verifier can check and re-derive the conformance material.
RFC8032_TEST_1_SEED = bytes.fromhex(
    "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"
)
CONFORMANCE_ED25519_SEED = bytes(range(32))

SCID = "z6mkfixture"
DID = f"did:webvh:{SCID}:alice.example"
PRINCIPAL_ID = f"ak:did_core:webvh:{SCID}"
PUBLISHED_VM_FRAGMENT = "ed25519-2026-05-fixture"
REGISTRATION_VERSION_TIME = "2026-08-08T00:00:00Z"

CONTROL_PROOF_DOMAIN = "ak.identity_creation_control_proof.v1"
ACCOUNT_SUBJECT_DOMAIN = "ak.account-subject.v1"
ACCOUNT_AUTHORITY_ID = "ak:did_core:webvh:z6mkfixtureaccountexample"
TRUST_DOMAIN = "ak:trust_domain:fixture.example"

SELF_CASE = "principal_control_realm_id_is_event_derived_and_nonzero_nibble_rejected"
SECOND_STATION_CASE = "human_pcr_genesis_on_a_second_station_derives_a_distinct_realm_id"
DELEGATED_CASE = "organization_governed_pcr_genesis_derives_a_distinct_realm"
AUTHORIZE_CASE = "human_founding_device_authorize_binds_the_derived_realm"


def b58encode(payload: bytes) -> str:
    number = int.from_bytes(payload, "big")
    out = ""
    while number:
        number, remainder = divmod(number, 58)
        out = B58_ALPHABET[remainder] + out
    for octet in payload:
        if octet:
            break
        out = "1" + out
    return out


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_token(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def multihash_sha256_b58(data: bytes) -> str:
    return b58encode(b"\x12\x20" + hashlib.sha256(data).digest())


def ed25519_multikey(public_key: bytes) -> str:
    return "z" + b58encode(b"\xed\x01" + public_key)


def public_bytes(seed: bytes) -> bytes:
    return (
        Ed25519PrivateKey.from_private_bytes(seed)
        .public_key()
        .public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    )


def sign_raw(seed: bytes, message: bytes) -> bytes:
    return Ed25519PrivateKey.from_private_bytes(seed).sign(message)


def detached_jws(seed: bytes, binding: dict[str, Any]) -> dict[str, str]:
    """Produce the Event detached JWS exactly as crypto-signature-fixture pins it."""
    header = b64u(canonical({"alg": "Ed25519"}).encode("utf-8"))
    body = canonical(binding)
    signing_input = f"{header}.{b64u(body.encode('utf-8'))}"
    signature = b64u(sign_raw(seed, signing_input.encode("utf-8")))
    return {
        "canonical_binding_payload": body,
        "jws_signing_input": signing_input,
        "jws": f"{header}..{signature}",
    }


def event_identity(preimage: str, suite: int) -> tuple[str, str, str]:
    digest = hashlib.sha256(preimage.encode("utf-8")).digest()
    body = bytes((suite,)) + digest
    return "ak:event:" + b64u(body), "sha256:" + digest.hex(), body.hex()


def retype(typed_id: str, kind: str) -> str:
    return f"ak:{kind}:" + typed_id.split(":", 2)[2]


# --------------------------------------------------------------------------
# the registration anchor
# --------------------------------------------------------------------------


def build_anchor() -> dict[str, Any]:
    root_multikey = ed25519_multikey(public_bytes(RFC8032_TEST_1_SEED))
    root_controller_did = f"did:key:{root_multikey}"
    root_verification_method = f"{root_controller_did}#{root_multikey}"

    # The prerotation commitment names the next update key. This log never
    # publishes a second entry, so it commits to the same published root key:
    # committing to an unpublished key would make the commitment unrecomputable,
    # and committing to the founding device key would imply a device key may
    # become a method update key.
    next_key_hash = multihash_sha256_b58(root_multikey.encode("utf-8"))

    published_jwk = {
        "crv": "Ed25519",
        "kty": "OKP",
        "x": b64u(public_bytes(CONFORMANCE_ED25519_SEED)),
    }
    published_vm_id = f"{DID}#{PUBLISHED_VM_FRAGMENT}"
    contexts = [
        "https://www.w3.org/ns/did/v1",
        "https://w3id.org/security/suites/jws-2020/v1",
    ]
    state = {
        "@context": contexts,
        "id": DID,
        "verificationMethod": [
            {
                "id": published_vm_id,
                "type": "JsonWebKey2020",
                "controller": DID,
                "publicKeyJwk": published_jwk,
            }
        ],
        "authentication": [published_vm_id],
        "assertionMethod": [published_vm_id],
    }
    parameters = {
        "method": "did:webvh:1.0",
        "scid": SCID,
        "updateKeys": [root_multikey],
        "nextKeyHashes": [next_key_hash],
    }
    # did:webvh entry hash: the entry with versionId replaced by its predecessor
    # -- the SCID for the inception entry -- hashed without the proof array.
    entry_hash_input = {
        "versionId": SCID,
        "versionTime": REGISTRATION_VERSION_TIME,
        "parameters": parameters,
        "state": state,
    }
    entry_hash_canonical = canonical(entry_hash_input)
    version_id = "1-" + multihash_sha256_b58(entry_hash_canonical.encode("utf-8"))

    proof_value = "z" + b58encode(
        sign_raw(RFC8032_TEST_1_SEED, entry_hash_canonical.encode("utf-8"))
    )
    published_entry = {
        "versionId": version_id,
        "versionTime": REGISTRATION_VERSION_TIME,
        "parameters": parameters,
        "state": state,
        "proof": [
            {
                "type": "DataIntegrityProof",
                "cryptosuite": "eddsa-jcs-2022",
                "verificationMethod": root_verification_method,
                "proofPurpose": "assertionMethod",
                "proofValue": proof_value,
            }
        ],
    }
    method_history_head = sha256_token(canonical(published_entry).encode("utf-8"))

    normalized_did_document = {
        "did": DID,
        "contexts": contexts,
        "controller_dids": [DID],
        "also_known_as": [],
        "verification_methods": [
            {
                "verification_method": published_vm_id,
                "controller_did": DID,
                "verification_method_suite": "JsonWebKey2020",
                "public_key_material": published_jwk,
                "extensions": [],
            }
        ],
        "authentication": [{"verification_method": published_vm_id}],
        "assertion_methods": [{"verification_method": published_vm_id}],
        "key_agreements": [],
        "capability_invocations": [],
        "capability_delegations": [],
        "services": [],
        "metadata": {},
        "extensions": [],
    }
    anchor = {
        "anchor_kind": "webvh_registration",
        "registration_did_operation": {
            "did": DID,
            "did_method": "webvh",
            "seq": 1,
            "operation": published_entry,
        },
        "log_entries": [published_entry],
        "witness_records": [],
        "normalized_did_document": normalized_did_document,
    }
    return {
        "anchor": anchor,
        "anchor_digest": sha256_token(canonical(anchor).encode("utf-8")),
        "entry_hash_input_canonical_json": entry_hash_canonical,
        "published_entry_canonical_json": canonical(published_entry),
        "version_id": version_id,
        "method_history_head": method_history_head,
        "root_control_key_multibase": root_multikey,
        "root_controller_did": root_controller_did,
        "root_verification_method": root_verification_method,
        "control_key_digest": sha256_token(root_multikey.encode("utf-8")),
        "next_key_hash": next_key_hash,
        "published_verification_method": published_vm_id,
    }


# --------------------------------------------------------------------------
# rewriting the fixtures
# --------------------------------------------------------------------------


def case(fixture: dict[str, Any], name: str) -> dict[str, Any]:
    for entry in fixture["cases"]:
        if entry.get("name") == name:
            return entry
    raise KeyError(name)


def recompute_case(entry: dict[str, Any]) -> None:
    """Re-derive every declared value from the case's own hashed bytes.

    A case carries either a complete wire Event, in which case the preimage is
    that Event minus the members the preimage omits, or the preimage bytes alone.
    Both are recomputed here so a preimage-only case cannot drift.
    """
    wire = entry.get("complete_wire_event")
    if isinstance(wire, dict):
        preimage = canonical(
            {
                key: value
                for key, value in wire.items()
                if key not in ("event_id", "proofs", "unsigned")
            }
        )
    else:
        preimage = canonical(json.loads(entry["digest_preimage_canonical_bytes_utf8"]))
    token, digest, digest_bytes = event_identity(preimage, entry["suite_wire_code"])
    entry["digest_preimage_canonical_bytes_utf8"] = preimage
    entry["event_digest"] = digest
    entry["event_id_bytes_hex"] = digest_bytes
    entry["derived_event_id"] = token
    if isinstance(wire, dict):
        wire["event_id"] = token
    if "derived_realm_id" in entry:
        entry["derived_realm_id"] = retype(token, "realm")
    if "rejected_form" in entry:
        body = base64.urlsafe_b64decode(
            entry["derived_realm_id"].split(":", 2)[2] + "="
        )
        entry["rejected_form"]["realm_id"] = "ak:realm:" + b64u(
            bytes((body[0] | 0x10,)) + body[1:]
        )


def resign(entry: dict[str, Any], seed: bytes, verification_method: str) -> dict[str, Any]:
    """Replace the case's single producer proof with a reproducible detached JWS."""
    wire = entry["complete_wire_event"]
    proof = wire["proofs"][0]
    proof["verification_method"] = verification_method
    proof["event_digest"] = entry["event_digest"]
    binding = {
        "context": "ak.event_proof.v1",
        "actor_id": wire["actor_id"],
        "created_at": proof["created_at"],
        "event_digest": entry["event_digest"],
        "verification_method": verification_method,
    }
    produced = detached_jws(seed, binding)
    proof["jws"] = produced["jws"]
    return {
        "context": "ak.event_proof.v1",
        "binding_object": binding,
        "canonical_binding_payload": produced["canonical_binding_payload"],
        "protected_header_canonical": '{"alg":"Ed25519"}',
        "jws_signing_input": produced["jws_signing_input"],
        "omitted_optional_members": [
            "audience",
            "domain",
            "signer_resolution_evidence_ref",
        ],
    }


def main() -> int:
    derived = build_anchor()
    content = json.loads(CONTENT_BOUND.read_text(encoding="utf-8"))
    genesis = json.loads(PCR_GENESIS.read_text(encoding="utf-8"))
    material = json.loads(TEST_MATERIAL.read_text(encoding="utf-8"))

    initial_resolution = {
        "did": DID,
        "method_history_head": derived["method_history_head"],
        "version_id": derived["version_id"],
    }
    for name in (SELF_CASE, SECOND_STATION_CASE, DELEGATED_CASE):
        entry = case(content, name)
        wire = entry.get("complete_wire_event")
        if isinstance(wire, dict):
            wire["payload"]["object"]["initial_resolution"] = dict(initial_resolution)
        else:
            preimage = json.loads(entry["digest_preimage_canonical_bytes_utf8"])
            preimage["payload"]["object"]["initial_resolution"] = dict(initial_resolution)
            entry["digest_preimage_canonical_bytes_utf8"] = canonical(preimage)
        recompute_case(entry)

    self_case = case(content, SELF_CASE)
    realm_id = self_case["derived_realm_id"]
    evidence = self_case["admission_evidence"]
    evidence["verification_method_source"] = (
        "the registration-time active update key of this unit's typed "
        "principal_registration_anchor, projected as its did:key controller proof method"
    )
    evidence["proof_binding"] = resign(
        self_case, RFC8032_TEST_1_SEED, derived["root_verification_method"]
    )
    evidence["registration_anchor"] = {
        "fixture": "pcr-genesis-fixture.json",
        "pointer": "/principal_registration_anchor_evidence/anchor",
        "anchor_canonical_json_sha256": derived["anchor_digest"],
        "resolved_verification_method": derived["root_verification_method"],
        "note": (
            "initial_resolution.did, version_id and method_history_head are the values that "
            "anchor's own terminal entry derives, and the producer proof is made by that "
            "entry's parameters.updateKeys[0]. A create Event keeping a device DID URL here "
            "cannot be the registration_anchor branch, because the branch's verifier reads "
            "the method from the anchor and requires equality."
        ),
    }

    delegated = case(content, DELEGATED_CASE)
    delegated_evidence = delegated["admission_evidence"]
    delegated_evidence["proof_binding"] = resign(
        delegated,
        CONFORMANCE_ED25519_SEED,
        delegated["complete_wire_event"]["proofs"][0]["verification_method"],
    )
    delegated_evidence["executor_signing_material"] = {
        "test_material_registry_row": "conformance_ed25519_fixture_key",
        "public_key_multibase": ed25519_multikey(public_bytes(CONFORMANCE_ED25519_SEED)),
        "note": (
            "Two Ed25519 keys are published conformance material, so the organization "
            "executor device key is the same published key as the founding device key. The "
            "reuse is a property of published test material and carries no protocol claim: "
            "the two signers are separated by verification_method, which resolves under the "
            "executor's own DID and not under the registration anchor."
        ),
    }

    authorize = case(content, AUTHORIZE_CASE)
    authorize["realm_id"] = realm_id
    authorize["scope_ref"] = {"kind": "realm", "realm_id": realm_id}
    preimage_object = json.loads(authorize["digest_preimage_canonical_bytes_utf8"])
    preimage_object["realm_id"] = realm_id
    preimage_object["scope_ref"] = {"kind": "realm", "realm_id": realm_id}
    authorize["digest_preimage_canonical_bytes_utf8"] = canonical(preimage_object)
    recompute_case(authorize)

    # ---- pcr-genesis-fixture -------------------------------------------------
    genesis["principal_registration_anchor_evidence"] = {
        "vector_id": "ak.vector.identity.pcr_genesis.v1",
        "schema_ref": "schemas/principal-registration-anchor.schema.json",
        "anchor": derived["anchor"],
        "anchor_canonical_json_sha256": derived["anchor_digest"],
        "derivations": {
            "did": DID,
            "version_id": derived["version_id"],
            "method_history_head": derived["method_history_head"],
            "entry_hash_input_canonical_json": derived["entry_hash_input_canonical_json"],
            "published_entry_canonical_json": derived["published_entry_canonical_json"],
            "root_control_key_multibase": derived["root_control_key_multibase"],
            "root_verification_method": derived["root_verification_method"],
            "control_key_digest": derived["control_key_digest"],
            "next_key_hash": derived["next_key_hash"],
            "rules": {
                "anchor_canonical_json_sha256": "sha256(JCS(complete anchor))",
                "control_key_digest": "sha256(UTF-8(parameters.updateKeys[0]))",
                "method_history_head": "sha256(JCS(published terminal entry))",
                "next_key_hash": (
                    "base58btc(0x12 0x20 || sha256(UTF-8(next update multikey)))"
                ),
                "root_verification_method": (
                    "did:key:<updateKeys[0]> || '#' || <updateKeys[0]>, the controller proof "
                    "method of the terminal entry"
                ),
                "version_id": (
                    "'1-' || base58btc(0x12 0x20 || sha256(JCS(terminal entry with versionId "
                    "replaced by its predecessor and proof omitted)))"
                ),
            },
        },
        "signing_material": {
            "root_update_key_registry_row": "rfc8032_test_1_ed25519_key",
            "next_update_key_registry_row": "rfc8032_test_1_ed25519_key",
            "published_document_key_registry_row": "conformance_ed25519_fixture_key",
            "note": (
                "The identity root is the method-native update key and is deliberately not "
                "the DID document's published assertion key, which stays the Ed25519 "
                "conformance key that crypto-signature-fixture.json resolves under this same "
                "DID. This log never publishes a second entry, so nextKeyHashes commits to "
                "the same published root key rather than to an unpublished one."
            ),
        },
        "scid_derivation": {
            "asserted_segment": SCID,
            "reserved_by": (
                "registry/test-material-registry.json#/reserved_identifiers/"
                "<webvh_conformance_scid>"
            ),
            "derivation_vector": (
                "fixtures/did-webvh-v1-fixture.json#/cases/"
                "<accept_scid_substituted_over_the_whole_entry>"
            ),
            "note": (
                "This is the one webvh relation the anchor asserts instead of deriving: every "
                "conformance did:webvh SCID is hand-written so it cannot collide with material "
                "a deployment produced, and SCID derivation is exercised by the method fixture "
                "named above. Everything downstream of the SCID in this anchor is derived."
            ),
        },
        "binds": {
            "fixture": "content-bound-event-id-fixture.json",
            "create_case": SELF_CASE,
            "initial_resolution_pointer": (
                "/cases/<"
                + SELF_CASE
                + ">/complete_wire_event/payload/object/initial_resolution"
            ),
            "producer_proof_pointer": (
                "/cases/<" + SELF_CASE + ">/complete_wire_event/proofs/0"
            ),
            "pcr_realm_id": realm_id,
            "note": (
                "The create Event's initial_resolution carries exactly the did, version_id and "
                "method_history_head derived here, and its producer proof verification method "
                "is root_verification_method. Replacing the anchor changes "
                "anchor_canonical_json_sha256 and therefore invalidates the identity-root "
                "control proof that commits to it."
            ),
        },
        "forbidden_substitutions": [
            "a resolver summary, a current DID document or a partial log range in place of log_entries",
            "the versionId entry hash in place of the complete anchor digest",
            "a normalized_did_document verification method in place of parameters.updateKeys[0]",
            "the founding device DID URL as the create Event's verification method",
            "a caller-asserted method_history_head that the terminal entry does not hash to",
        ],
    }

    session_request = genesis["initial_session_request"]
    session_request["canonical_json"] = canonical(session_request["value"])
    session_request["digest"] = sha256_token(
        session_request["canonical_json"].encode("utf-8")
    )

    account_subject_preimage = {
        "authentication_row_key": "01J9A0000000000000000ALICE",
        "issuer_id": ACCOUNT_AUTHORITY_ID,
    }
    account_subject = sha256_token(
        (ACCOUNT_SUBJECT_DOMAIN + "\n").encode("utf-8")
        + canonical(account_subject_preimage).encode("utf-8")
    )

    create_payload = self_case["complete_wire_event"]["payload"]
    signed = {
        "proof_kind": "did_webvh_inception_update_key",
        "challenge_id": "genesis-challenge-000001",
        "challenge": "AAAAAAAAAAAAAAAAAAAAAA",
        "purpose": "account_binding_and_pcr_genesis",
        "account_subject": account_subject,
        "principal_id": PRINCIPAL_ID,
        "did": DID,
        "registration_anchor_digest": derived["anchor_digest"],
        "did_version_id": derived["version_id"],
        "control_key_digest": derived["control_key_digest"],
        "pcr_realm_id": realm_id,
        "realm_create_payload_digest": sha256_token(
            canonical(create_payload).encode("utf-8")
        ),
        "founding_authorize_payload_digest": genesis["founding_authorize"][
            "payload_digest"
        ],
        "initial_session_request_digest": session_request["digest"],
        "genesis_unit_kinds": ["ak.realm.create", "ak.device.authorize"],
        "identity_creation_lease_id": "genesis-lease-fence-0001",
        "lease_fence": 1,
        "dpop_jkt": session_request["rfc7638_jkt"],
        "audience_id": ACCOUNT_AUTHORITY_ID,
        "origin": "https://account.example",
        "trust_domain": TRUST_DOMAIN,
        "issued_at": "2026-08-09T00:00:00.000Z",
        "expires_at": "2026-08-09T00:05:00.000Z",
        "verification_key_multibase": derived["root_control_key_multibase"],
        "signature_algorithm": "Ed25519",
    }
    signed_canonical = canonical(signed)
    signature = b64u(
        sign_raw(
            RFC8032_TEST_1_SEED,
            (CONTROL_PROOF_DOMAIN + "\n").encode("utf-8")
            + signed_canonical.encode("utf-8"),
        )
    )
    transcript = genesis["identity_creation_control_transcript"]
    transcript["context"] = CONTROL_PROOF_DOMAIN
    transcript["schema_ref"] = (
        "schemas/account-operations.schema.json#/$defs/identity_creation_control_proof"
    )
    transcript["signing_input"] = (
        'UTF-8("ak.identity_creation_control_proof.v1" || 0x0A) || '
        "JCS(signature_omitted_object)"
    )
    transcript["signature_omitted_object"] = signed
    transcript["canonical_json"] = signed_canonical
    transcript["canonical_json_sha256"] = sha256_token(signed_canonical.encode("utf-8"))
    transcript["signature"] = signature
    transcript["signed_object"] = dict(signed, signature=signature)
    transcript["account_subject_preimage"] = {
        "domain": ACCOUNT_SUBJECT_DOMAIN,
        "canonical_json": canonical(account_subject_preimage),
        "value": account_subject_preimage,
        "note": (
            "SHA-256 over UTF-8(domain || 0x0A) followed by JCS of the issuer identity and the "
            "issuer-local authentication row key. The member names are deployment-local by "
            "construction: the subject never leaves the Account Authority boundary, so the "
            "specification fixes the domain and the digest but not the row key spelling."
        ),
    }
    transcript["signing_material"] = {
        "test_material_registry_row": "rfc8032_test_1_ed25519_key",
        "public_key_multibase": derived["root_control_key_multibase"],
        "public_key_did": derived["root_controller_did"],
        "note": (
            "The identity root is the registration anchor's parameters.updateKeys[0], never a "
            "normalized DID document verification method and never the founding device key. "
            "The private key is published, so this signature is reproducible and proves no "
            "authority."
        ),
    }
    transcript["forbidden_fields"] = [
        "audience",
        "founding_authorize_envelope_digest",
        "founding_authorize_event_id",
        "log_head_digest",
        "operation_digest",
        "realm_create_envelope_digest",
        "realm_create_event_id",
    ]

    device_method = f"{DID}#ak:device:019a0000-0000-7000-8000-000000000001"
    genesis["founding_event_proof_binding"] = {
        "note": (
            "The two Events of one genesis unit resolve their signing keys from different "
            "material: the create Event from the frozen registration anchor, the authorize "
            "Event from the root-signed descriptor and the unit-local candidate overlay. "
            "Collapsing both onto one device verification method is what left the "
            "registration_anchor admission branch with no constructible instance."
        ),
        "create_event": {
            "admission": "registration_anchor",
            "verification_method": derived["root_verification_method"],
            "public_key_source": (
                "/principal_registration_anchor_evidence/anchor/log_entries/-1/parameters/"
                "updateKeys/0"
            ),
            "forbidden_verification_method_forms": [
                "the founding device DID URL",
                "any fragment resolved through the device directory",
                "a normalized DID document verification method of the principal",
                "the principal actor_id rewritten into a DID URL",
            ],
        },
        "authorize_event": {
            "verification_method": device_method,
            "candidate_overlay_lookup": {
                "method": device_method,
                "public_key_source": "founding_authorize.payload.device_public_key_did",
            },
            "forbidden_verification_method_forms": [
                "did:key candidate",
                "pre-existing accepted-device directory entry",
                "any fragment other than the complete device_id",
                "the registration anchor root controller method",
            ],
        },
    }

    # ---- test material registry ---------------------------------------------
    now_signs = {
        "rfc8032_test_1_ed25519_key": [
            "spec/v1/artifacts/fixtures/content-bound-event-id-fixture.json",
            "spec/v1/artifacts/fixtures/pcr-genesis-fixture.json",
        ],
        "conformance_ed25519_fixture_key": [
            "spec/v1/artifacts/fixtures/content-bound-event-id-fixture.json",
        ],
    }
    for row in material["published_signing_material"]:
        added = now_signs.get(row["id"])
        if added:
            row["source_fixtures"] = sorted(set(row["source_fixtures"]) | set(added))
        if row["id"] == "rfc8032_test_1_ed25519_key":
            row["why"] = (
                "The RFC 8032 section 7.1 TEST 1 Ed25519 key. It is the proof-of-possession "
                "key of the WebSocket DPoP known-answer test, and it is the human PCR "
                "registration anchor's method-native update key, so it also signs that "
                "anchor's controller proof, the genesis create Event and the identity-root "
                "control transcript. Its private key has been published in an IETF document "
                "since 2017; a holder of this key can mint a syntactically perfect DPoP proof."
            )

    for path, document in (
        (CONTENT_BOUND, content),
        (PCR_GENESIS, genesis),
        (TEST_MATERIAL, material),
    ):
        path.write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    print(f"anchor digest        {derived['anchor_digest']}")
    print(f"version_id           {derived['version_id']}")
    print(f"method_history_head  {derived['method_history_head']}")
    print(f"root method          {derived['root_verification_method']}")
    print(f"pcr realm            {realm_id}")
    print(f"account_subject      {account_subject}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
