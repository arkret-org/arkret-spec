#!/usr/bin/env python3
"""Recompute and cryptographically verify the approval-signature byte KAT.

This checker deliberately lives outside the general artifact lint.  The lint
recomputes canonical bytes and digests but never performs a signature
verification, and the whole point of ``ak.approval.signature.v1`` is that two
implementations reach the same signing bytes: the domain prefix, the closed
input object and the detached-JWS profile only bind anything if a real Ed25519
verification is run over them.  So every accepted vector here is verified, and
every rejected case is refuted -- a negative case whose signature happens to
verify is reported as an error, because such a case proves nothing.

The target Event is not authored here.  Its digest preimage, ``event_digest``
and derived ``event_id`` are cross-checked against the case
``strand_object_id_is_retyped_event_id`` of content-bound-event-id-fixture.json,
which is what makes the event_id-invariance claim checkable: attaching approval
signatures moves the transport Content-Digest and MUST NOT move the Event.
"""

from __future__ import annotations

import base64
import copy
import functools
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "spec" / "v1" / "artifacts"
SCHEMAS = ARTIFACTS / "schemas"
FIXTURE_PATH = ARTIFACTS / "fixtures" / "approval-signature-kat-fixture.json"
FIXTURE_REPO_PATH = FIXTURE_PATH.relative_to(ROOT).as_posix()
EVENT_ID_FIXTURE_PATH = ARTIFACTS / "fixtures" / "content-bound-event-id-fixture.json"
APPROVAL_SCHEMA_PATH = SCHEMAS / "approval-signature.schema.json"
DTO_SCHEMA_PATH = SCHEMAS / "service-operation-dtos.schema.json"
OPERATION_REGISTRY_PATH = ARTIFACTS / "registry" / "operation-registry.json"
ACTION_REGISTRY_PATH = ARTIFACTS / "registry" / "capability-action-registry.json"
VECTOR_REGISTRY_PATH = ARTIFACTS / "registry" / "vector-registry.json"
ERROR_REGISTRY_PATH = ARTIFACTS / "registry" / "error-code-registry.json"
PROOF_CONTEXT_REGISTRY_PATH = ARTIFACTS / "registry" / "proof-context-registry.json"
MATERIAL_REGISTRY_PATH = ARTIFACTS / "registry" / "test-material-registry.json"

SIGNING_DOMAIN = "ak.approval.signature.v1"
EVENT_PROOF_CONTEXT = "ak.event_proof.v1"
MATERIAL_ROW = "conformance_ed25519_fixture_key"
PUBLISHED_SEED = bytes(range(32))
SOURCE_EVENT_CASE = "strand_object_id_is_retyped_event_id"
PREIMAGE_OMITTED_MEMBERS = ("event_id", "proofs", "unsigned")

# A named case may be renamed or re-argued, but it may not quietly disappear:
# each of these is the only refutation of one distinct way to get the bytes
# wrong, and a dropped case turns this KAT back into prose.
REQUIRED_NEGATIVE_CASES = frozenset(
    {
        "reject_substituted_request_canonical_digest",
        "reject_substituted_event_id",
        "reject_substituted_realm_id",
        "reject_substituted_action",
        "reject_substituted_operation",
        "reject_substituted_initiating_actor_station",
        "reject_substituted_grant_id",
        "reject_substituted_approval_context_branch",
        "reject_substituted_nonce",
        "reject_substituted_approved_at",
        "reject_substituted_approver_did",
        "reject_operation_target_digest_substituted",
        "reject_signature_over_input_without_domain_prefix",
        "reject_signature_over_a_digest_of_the_input",
        "reject_producer_proof_jws_presented_as_approval_proof",
        "reject_flipped_signature_bit",
        "reject_non_empty_jws_payload_segment",
        "reject_substituted_verification_method",
        "reject_missing_input_member",
        "reject_null_filled_absent_member",
        "reject_extra_input_member",
        "reject_proof_inside_input",
        "reject_governance_context_carrying_grant_id",
        "reject_event_target_without_event_id",
        "reject_operation_target_carrying_event_id",
        "reject_unregistered_operation_token",
        "reject_short_nonce",
        "reject_present_and_empty_approval_signatures",
        "reject_event_id_not_equal_to_submitted_event",
        "reject_nonce_reused_on_another_target",
        "reject_approved_at_beyond_hard_future_skew",
        "reject_approved_at_before_grant_issued_at",
        "reject_repeated_approver_counted_twice",
        "reject_reused_votes_after_timeout",
        "reject_agent_confirmation_counted_as_approval",
    }
)


# --------------------------------------------------------------------------
# canonical JSON
# --------------------------------------------------------------------------
def jcs_text(value: Any) -> str:
    """Encode the value shapes this KAT uses under the JCS narrowed profile.

    RFC 8785 sorts property names as UTF-16 code units, not as code points, so
    the sort key is the UTF-16-BE encoding.  Floats are rejected rather than
    rendered with Python's non-ECMAScript number formatting.
    """

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
        return json.dumps(value, ensure_ascii=False, allow_nan=False)
    if isinstance(value, list):
        return "[" + ",".join(jcs_text(item) for item in value) + "]"
    if isinstance(value, dict):
        members = sorted(value.items(), key=lambda kv: kv[0].encode("utf-16-be"))
        return "{" + ",".join(f"{jcs_text(k)}:{jcs_text(v)}" for k, v in members) + "}"
    raise ValueError(f"unsupported JSON type in KAT: {type(value).__name__}")


def b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def b64u_decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def sha256_digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def signing_bytes(approval_input: Any) -> bytes:
    return SIGNING_DOMAIN.encode("utf-8") + b"\x0a" + jcs_text(approval_input).encode("utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# schema validators
# --------------------------------------------------------------------------
@functools.cache
def schema_registry() -> Registry:
    resources = []
    for path in sorted(SCHEMAS.glob("*.schema.json")):
        document = load_json(path)
        schema_id = document.get("$id")
        if isinstance(schema_id, str):
            resources.append((schema_id, Resource.from_contents(document)))
    return Registry().with_resources(resources)


@functools.cache
def approval_validator() -> Draft202012Validator:
    return Draft202012Validator(load_json(APPROVAL_SCHEMA_PATH), registry=schema_registry())


@functools.cache
def input_validator() -> Draft202012Validator:
    document = load_json(APPROVAL_SCHEMA_PATH)
    schema = copy.deepcopy(document["$defs"]["approval_signature_input"])
    schema["$id"] = "https://arkret.org/v1/schemas/approval-signature-input.internal.json"
    schema["$defs"] = copy.deepcopy(document["$defs"])
    return Draft202012Validator(schema, registry=schema_registry())


@functools.cache
def submission_validator() -> Draft202012Validator:
    document = load_json(DTO_SCHEMA_PATH)
    schema = copy.deepcopy(document["$defs"]["EventCommitSubmission"])
    schema["$id"] = "https://arkret.org/v1/schemas/event-commit-submission.internal.json"
    schema["$defs"] = copy.deepcopy(document["$defs"])
    return Draft202012Validator(schema, registry=schema_registry())


def verify(public_key: Ed25519PublicKey, signature: bytes, message: bytes) -> bool:
    try:
        public_key.verify(signature, message)
    except InvalidSignature:
        return False
    return True


def split_jws(jws: str) -> tuple[str, str, str]:
    parts = jws.split(".")
    if len(parts) != 3:
        raise ValueError(f"compact JWS must have three segments: {jws[:32]}...")
    return parts[0], parts[1], parts[2]


# --------------------------------------------------------------------------
# accepted vectors
# --------------------------------------------------------------------------
def check_vector(vector: dict[str, Any], expected_public: bytes) -> list[str]:
    name = vector.get("name", "<unnamed>")
    errors: list[str] = []

    def fail(message: str) -> None:
        errors.append(f"{name}: {message}")

    jwk = vector["did_document_fragment"]["publicKeyJwk"]
    public_raw = b64u_decode(jwk["x"])
    if public_raw != expected_public:
        fail("publicKeyJwk.x is not the registered conformance key")
        return errors
    private_jwk = vector["test_private_key_jwk"]
    seed = b64u_decode(private_jwk["d"])
    if seed != PUBLISHED_SEED:
        fail("test_private_key_jwk.d is not the published conformance seed")
    derived = Ed25519PrivateKey.from_private_bytes(seed).public_key().public_bytes_raw()
    if derived != public_raw:
        fail("test_private_key_jwk does not derive the published public key")
    if private_jwk.get("x") != jwk["x"]:
        fail("test_private_key_jwk.x disagrees with the DID document fragment")

    fragment = vector["did_document_fragment"]
    if not fragment["id"].startswith(fragment["controller"] + "#"):
        fail("verification method id is not a fragment of its controller DID")

    approval = vector["approval_signature"]
    errors.extend(
        f"{name}: approval_signature {error.json_path}: {error.message}"
        for error in approval_validator().iter_errors(approval)
    )

    approval_input = approval["input"]
    canonical = jcs_text(approval_input)
    if canonical != vector["canonical_input_utf8"]:
        fail("canonical_input_utf8 does not match recomputed JCS(input)")
    if vector["signing_domain"] != SIGNING_DOMAIN:
        fail(f"signing_domain must be {SIGNING_DOMAIN}")
    payload = signing_bytes(approval_input)
    if payload.hex() != vector["signing_bytes_hex"]:
        fail("signing_bytes_hex does not match UTF8(domain) || 0x0A || JCS(input)")
    if sha256_digest(payload) != vector["signing_bytes_sha256"]:
        fail("signing_bytes_sha256 mismatch")
    if b64u(payload) != vector["detached_payload_b64u"]:
        fail("detached_payload_b64u is not the base64url of signing_bytes")

    protected_canonical = jcs_text(vector["protected_header"])
    if protected_canonical != vector["protected_header_canonical"]:
        fail("protected_header_canonical mismatch")
    if vector["protected_header"].get("alg") != vector["jose_algorithm"]:
        fail("protected header alg disagrees with jose_algorithm")

    protected_b64u, payload_segment, signature_segment = split_jws(approval["proof"]["jws"])
    if protected_b64u != b64u(protected_canonical.encode("utf-8")):
        fail("JWS protected segment is not the canonical protected header")
    if payload_segment != "":
        fail("detached_jws compact serialization MUST carry an empty payload segment")
    expected_signing_input = f"{protected_b64u}.{b64u(payload)}"
    if vector["jws_signing_input"] != expected_signing_input:
        fail("jws_signing_input is not b64u(protected) || '.' || b64u(signing_bytes)")

    public_key = Ed25519PublicKey.from_public_bytes(public_raw)
    signature = b64u_decode(signature_segment)
    if not verify(public_key, signature, expected_signing_input.encode("ascii")):
        fail("the Ed25519 signature does not verify over the recomputed signing input")

    # The digest-then-sign shape section 9.2.1 forbids must not also verify:
    # if it did, the two constructions would be interchangeable in practice.
    if verify(public_key, signature, hashlib.sha256(payload).digest()):
        fail("signature also verifies over a digest of signing_bytes")
    if verify(public_key, signature, canonical.encode("utf-8")):
        fail("signature also verifies over JCS(input) without the domain prefix")

    if approval["proof"]["verification_method"] != fragment["id"]:
        fail("proof.verification_method does not name the fragment carried by the vector")
    if not approval["proof"]["verification_method"].startswith(approval_input["approver_did"] + "#"):
        fail("proof.verification_method does not resolve through approver_did")

    context_kind = approval_input["approval_context"]["context_kind"]
    target_kind = approval_input["approval_target"]["target_kind"]
    expected = vector["expected"]
    if expected.get("approval_context_branch") != context_kind:
        fail("expected.approval_context_branch disagrees with the signed input")
    if expected.get("approval_target_branch") != target_kind:
        fail("expected.approval_target_branch disagrees with the signed input")
    if expected.get("verification_result") != "valid":
        fail("an accepted vector must declare verification_result valid")

    return errors


# --------------------------------------------------------------------------
# event_id invariance
# --------------------------------------------------------------------------
def check_event_id_invariance(fixture: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    block = fixture["event_id_invariance"]

    source = load_json(EVENT_ID_FIXTURE_PATH)
    case = next(
        (row for row in source["cases"] if row.get("name") == SOURCE_EVENT_CASE),
        None,
    )
    if case is None:
        return [
            "event_id_invariance: content-bound-event-id-fixture.json no longer carries "
            f"the case {SOURCE_EVENT_CASE}; this KAT's target Event has no source of truth"
        ]
    for member in ("digest_preimage_canonical_bytes_utf8", "event_digest"):
        if block[member] != case[member]:
            errors.append(f"event_id_invariance: {member} diverges from the Event-ID fixture")
    if block["event_id_before_attaching"] != case["derived_event_id"]:
        errors.append("event_id_invariance: target event_id diverges from the Event-ID fixture")

    preimage_text = block["digest_preimage_canonical_bytes_utf8"]
    preimage = json.loads(preimage_text)
    if jcs_text(preimage) != preimage_text:
        errors.append("event_id_invariance: preimage bytes are not canonical JCS")
    for member in PREIMAGE_OMITTED_MEMBERS:
        if member in preimage:
            errors.append(f"event_id_invariance: preimage must omit {member}")
    digest = sha256_digest(preimage_text.encode("utf-8"))
    if digest != block["event_digest"]:
        errors.append("event_id_invariance: event_digest is not SHA-256 over the preimage bytes")
    token = b64u(bytes([case["suite_wire_code"]]) + bytes.fromhex(digest.split(":", 1)[1]))
    derived_id = "ak:event:" + token
    if derived_id != block["event_id_before_attaching"]:
        errors.append("event_id_invariance: event_id is not the retyped 33-octet token")
    if block["event_id_after_attaching"] != block["event_id_before_attaching"]:
        errors.append("event_id_invariance: attaching evidence changed event_id")

    submission = block["submission_with_evidence"]
    event = submission["event"]
    if event.get("event_id") != derived_id:
        errors.append("event_id_invariance: the submitted Event does not carry the derived id")
    stripped = {k: v for k, v in event.items() if k not in PREIMAGE_OMITTED_MEMBERS}
    if jcs_text(stripped) != preimage_text:
        errors.append(
            "event_id_invariance: stripping event_id, proofs and unsigned from the submitted "
            "Event does not reproduce the preimage bytes"
        )
    if jcs_text(event) != block["complete_event_canonical_utf8"]:
        errors.append("event_id_invariance: complete_event_canonical_utf8 mismatch")
    request_digest = sha256_digest(block["complete_event_canonical_utf8"].encode("utf-8"))
    if request_digest != block["request_canonical_digest"]:
        errors.append("event_id_invariance: request_canonical_digest is not over the complete Event")

    without = {"event": copy.deepcopy(event)}
    if jcs_text(without) != block["submission_without_evidence_canonical_utf8"]:
        errors.append("event_id_invariance: submission_without_evidence canonical bytes mismatch")
    digest_without = sha256_digest(jcs_text(without).encode("utf-8"))
    digest_with = sha256_digest(jcs_text(submission).encode("utf-8"))
    if digest_without != block["submission_without_evidence_content_digest"]:
        errors.append("event_id_invariance: submission_without_evidence_content_digest mismatch")
    if digest_with != block["submission_with_evidence_content_digest"]:
        errors.append("event_id_invariance: submission_with_evidence_content_digest mismatch")
    if digest_with == digest_without:
        errors.append(
            "event_id_invariance: the transport Content-Digest must change when evidence is "
            "attached, otherwise the two checks are not independent"
        )

    errors.extend(
        f"event_id_invariance: submission {error.json_path}: {error.message}"
        for error in submission_validator().iter_errors(submission)
    )
    signatures = submission.get("approval_signatures")
    if not isinstance(signatures, list) or len(signatures) < 2:
        errors.append("event_id_invariance: the attached submission must carry at least two votes")
    else:
        vectors = {jcs_text(row["approval_signature"]): row["name"] for row in fixture["vectors"]}
        for entry in signatures:
            if jcs_text(entry) not in vectors:
                errors.append(
                    "event_id_invariance: an attached approval_signatures entry is not one of the "
                    "verified vectors"
                )
    return errors


# --------------------------------------------------------------------------
# negative cases
# --------------------------------------------------------------------------
def check_negative(
    case: dict[str, Any],
    fixture: dict[str, Any],
    public_key: Ed25519PublicKey,
    registered_operations: set[str],
) -> list[str]:
    name = case.get("name", "<unnamed>")
    errors: list[str] = []

    def fail(message: str) -> None:
        errors.append(f"{name}: {message}")

    expected = case["expected"]
    if expected.get("decision") != "reject":
        fail("a negative case must declare decision reject")
    code = expected.get("error_code")

    vectors = {row["name"]: row for row in fixture["vectors"]}
    base = vectors.get(case.get("base_vector"))
    if base is None:
        fail("base_vector does not name a vector of this fixture")
        return errors
    base_signature = b64u_decode(split_jws(base["approval_signature"]["proof"]["jws"])[2])
    base_input_signing = base["jws_signing_input"].encode("ascii")

    if code == "signature_invalid":
        if "mutated_input" in case:
            mutated = case["mutated_input"]
            # A substitution case is only about bytes, so the mutated object
            # must still satisfy the schema: otherwise it would be refuted for
            # its shape and would never reach signature verification.
            schema_errors = list(input_validator().iter_errors(mutated))
            if schema_errors:
                fail(
                    "a signature-substitution case must remain schema-valid, but the mutated "
                    f"input violates the schema: {schema_errors[0].message}"
                )
            if jcs_text(mutated) != case["mutated_canonical_input_utf8"]:
                fail("mutated_canonical_input_utf8 does not match recomputed JCS")
            payload = signing_bytes(mutated)
            protected_b64u = split_jws(base["approval_signature"]["proof"]["jws"])[0]
            expected_input = f"{protected_b64u}.{b64u(payload)}"
            if case["mutated_jws_signing_input"] != expected_input:
                fail("mutated_jws_signing_input mismatch")
            if case["proof_jws"] != base["approval_signature"]["proof"]["jws"]:
                fail("a substitution case must retain the base vector's signature verbatim")
            if verify(public_key, base_signature, expected_input.encode("ascii")):
                fail("the retained signature verifies over the mutated input; nothing is refuted")
            if mutated == base["approval_signature"]["input"]:
                fail("the mutated input is identical to the base input")
        elif name == "reject_substituted_verification_method":
            substituted = case["substituted_verification_method"]
            if substituted == base["did_document_fragment"]["id"]:
                fail("the substituted verification method is the original one")
            if not substituted.startswith(base["approval_signature"]["input"]["approver_did"] + "#"):
                fail("the substituted verification method must still be a key of the approver DID")
            if not verify(public_key, base_signature, base_input_signing):
                fail("the retained signature must still verify under the correct key")
        elif name == "reject_flipped_signature_bit":
            signature = b64u_decode(split_jws(case["proof_jws"])[2])
            if len(signature) != len(base_signature):
                fail("the flipped signature changed length")
            differing = sum(
                bin(left ^ right).count("1") for left, right in zip(signature, base_signature)
            )
            if differing != 1:
                fail(f"expected exactly one flipped bit, found {differing}")
            if verify(public_key, signature, case["jws_signing_input"].encode("ascii")):
                fail("the flipped signature still verifies")
        elif name == "reject_non_empty_jws_payload_segment":
            protected_b64u, payload_segment, signature_segment = split_jws(case["proof_jws"])
            if payload_segment == "":
                fail("this case must carry a non-empty payload segment")
            if b64u_decode(payload_segment) != signing_bytes(base["approval_signature"]["input"]):
                fail("the payload segment must carry the correct signing bytes")
            if b64u_decode(signature_segment) != base_signature:
                fail("this case must retain the base signature; only the serialization differs")
            # The attached form does verify over its own signing input: the
            # refutation is the profile, not the arithmetic, and saying so is
            # the point of the case.
            if not verify(
                public_key,
                base_signature,
                f"{protected_b64u}.{payload_segment}".encode("ascii"),
            ):
                fail("the attached serialization does not even verify over its own input")
        else:
            signature = b64u_decode(split_jws(case["proof_jws"])[2])
            own_input = case["jws_signing_input"].encode("ascii")
            if not verify(public_key, signature, own_input):
                fail(
                    "this case must carry a genuine signature over the wrong bytes; it does not "
                    "verify over its own signing input either, so it refutes nothing"
                )
            correct = case.get("expected_signing_input")
            if correct is None:
                fail("a wrong-bytes case must record the correct expected_signing_input")
            else:
                if correct != base["jws_signing_input"]:
                    fail("expected_signing_input is not the base vector's signing input")
                if verify(public_key, signature, correct.encode("ascii")):
                    fail("the signature also verifies over the correct signing input")
            if name == "reject_signature_over_input_without_domain_prefix":
                payload = b64u_decode(case["signed_payload_b64u"])
                if payload != jcs_text(base["approval_signature"]["input"]).encode("utf-8"):
                    fail("the signed payload is not JCS(input) with the domain prefix dropped")
            if name == "reject_signature_over_a_digest_of_the_input":
                payload = b64u_decode(case["signed_payload_b64u"])
                if payload != hashlib.sha256(
                    jcs_text(base["approval_signature"]["input"]).encode("utf-8")
                ).digest():
                    fail("the signed payload is not SHA-256 over JCS(input)")
            if name == "reject_producer_proof_jws_presented_as_approval_proof":
                event = fixture["event_id_invariance"]["submission_with_evidence"]["event"]
                proof = event["proofs"][0]
                if case["proof_jws"] != proof["jws"]:
                    fail("this case must present the target Event's own producer proof verbatim")
                binding = {
                    "context": EVENT_PROOF_CONTEXT,
                    "event_digest": proof["event_digest"],
                    "actor_id": event["actor_id"],
                    "verification_method": proof["verification_method"],
                    "created_at": proof["created_at"],
                    "domain": proof["domain"],
                }
                protected_b64u = split_jws(proof["jws"])[0]
                rebuilt = f"{protected_b64u}.{b64u(jcs_text(binding).encode('utf-8'))}"
                if rebuilt != case["jws_signing_input"]:
                    fail("the producer proof's signing input is not the registered event-proof binding")
    elif code == "schema_violation":
        detected_by = expected.get("detected_by")
        if "mutated_submission" in case:
            if not list(submission_validator().iter_errors(case["mutated_submission"])):
                fail("EventCommitSubmission accepts the mutated submission")
        elif detected_by == "schema":
            if not list(input_validator().iter_errors(case["mutated_input"])):
                fail("the closed input schema accepts this shape")
        elif detected_by == "operation_registry":
            mutated = case["mutated_input"]
            if list(input_validator().iter_errors(mutated)):
                fail(
                    "this case claims the registry is what refutes it, but the schema already "
                    "does; record detected_by schema instead"
                )
            if mutated["operation"] in registered_operations:
                fail("the operation token this case calls unregistered is registered")
        else:
            fail(f"unknown detected_by {detected_by!r} on a schema_violation case")
        if not expected.get("reject_if_reported_as_signature_invalid"):
            fail("a shape error must forbid being reported as signature_invalid")
    elif code in {"claim_required", "failed_precondition"}:
        if "reason_code" not in expected:
            fail(f"{code} requires a reason_code")
        if "mutated_input" in case or "proof_jws" in case:
            fail("an admission case must not carry mutated bytes: the signature itself is valid")
    else:
        fail(f"unexpected error_code {code!r}")
    return errors


# --------------------------------------------------------------------------
# registry closure
# --------------------------------------------------------------------------
def check_registrations(fixture: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    vector_rows = {row["vector_id"]: row for row in load_json(VECTOR_REGISTRY_PATH)["vectors"]}
    covered = fixture["covers_vectors"]
    declared = {row["name"] for row in fixture["vectors"]}
    declared.add(fixture["negative_cases_vector_id"])
    if set(covered) != declared:
        errors.append("covers_vectors does not equal the set of vector ids this fixture exercises")
    for vector_id in covered:
        row = vector_rows.get(vector_id)
        if row is None:
            errors.append(f"vector {vector_id} is not registered in vector-registry.json")
            continue
        if row.get("status") != "active":
            errors.append(f"vector {vector_id} is registered but not active")
        if FIXTURE_PATH.name not in row.get("applies_to_fixtures", []):
            errors.append(
                f"vector {vector_id} does not list {FIXTURE_PATH.name} in applies_to_fixtures"
            )

    material = load_json(MATERIAL_REGISTRY_PATH)
    row = next(
        (r for r in material["published_signing_material"] if r.get("id") == MATERIAL_ROW),
        None,
    )
    if row is None:
        errors.append(f"test-material-registry.json has no row named {MATERIAL_ROW}")
    elif FIXTURE_REPO_PATH not in row.get("source_fixtures", []):
        errors.append(
            f"{FIXTURE_REPO_PATH} publishes signing material but is not listed in "
            f"{MATERIAL_ROW}.source_fixtures"
        )

    domains = load_json(PROOF_CONTEXT_REGISTRY_PATH).get("domain_separations", [])
    domain_row = next((r for r in domains if r.get("domain") == SIGNING_DOMAIN), None)
    if domain_row is None:
        errors.append(f"{SIGNING_DOMAIN} is not registered in proof-context-registry.json")
    elif domain_row.get("primitive") != "detached_signature":
        errors.append(f"{SIGNING_DOMAIN} is not registered as a detached_signature primitive")

    errors_registry = load_json(ERROR_REGISTRY_PATH)
    codes = {row["code"] for row in errors_registry["codes"]}
    reasons = {row["code"] for row in errors_registry["reason_codes"]}
    for case in fixture["negative_cases"]:
        expected = case["expected"]
        if expected.get("error_code") not in codes:
            errors.append(f"{case['name']}: error_code is not registered")
        reason = expected.get("reason_code")
        if reason is not None and reason not in reasons:
            errors.append(f"{case['name']}: reason_code {reason} is not registered")

    names = {case["name"] for case in fixture["negative_cases"]}
    for missing in sorted(REQUIRED_NEGATIVE_CASES - names):
        errors.append(f"required negative case {missing} is absent")
    if len(names) != len(fixture["negative_cases"]):
        errors.append("negative case names are not unique")

    actions = load_json(ACTION_REGISTRY_PATH)
    action_rows = actions.get("actions", actions if isinstance(actions, list) else [])
    action_by_id = {
        row.get("action_id") or row.get("action"): row
        for row in action_rows
        if isinstance(row, dict)
    }
    registered_actions = {
        row.get("action_id") or row.get("action") for row in action_rows if isinstance(row, dict)
    }
    operations = load_json(OPERATION_REGISTRY_PATH)
    operation_rows = operations.get("operations", operations if isinstance(operations, list) else [])
    registered_operations = {
        row.get("operation_id") or row.get("operation")
        for row in operation_rows
        if isinstance(row, dict)
    }
    eligibility = actions.get("approval_requirement_eligibility", {})
    defaults = eligibility.get("event_mapping_defaults", {})
    carriers = {
        row.get("carrier_id"): row
        for row in eligibility.get("carriers", [])
        if isinstance(row, dict)
    }
    default_carriers = eligibility.get("default_carrier_by_eligibility_kind", {})
    overrides = {
        row.get("action"): row
        for row in eligibility.get("action_overrides", [])
        if isinstance(row, dict)
    }
    for vector in fixture["vectors"]:
        approval_input = vector["approval_signature"]["input"]
        if approval_input["operation"] not in registered_operations:
            errors.append(f"{vector['name']}: operation is not registered")
        if approval_input["action"] not in registered_actions:
            errors.append(f"{vector['name']}: action is not registered")
            continue
        action_row = action_by_id[approval_input["action"]]
        override = overrides.get(approval_input["action"])
        eligibility_kind = (
            override.get("eligibility_kind")
            if isinstance(override, dict)
            else defaults.get(action_row.get("event_mapping_kind"))
        )
        if eligibility_kind == "ineligible_no_registered_carrier":
            errors.append(f"{vector['name']}: action has no registered approval carrier")
            continue
        carrier_id = (
            override.get("carrier_id")
            if isinstance(override, dict)
            else default_carriers.get(eligibility_kind)
        )
        carrier = carriers.get(carrier_id)
        if carrier is None:
            errors.append(f"{vector['name']}: action eligibility does not resolve to a carrier")
            continue
        target_kind = approval_input["approval_target"]["target_kind"]
        if target_kind not in carrier.get("allowed_target_kinds", []):
            errors.append(f"{vector['name']}: carrier does not allow target kind {target_kind}")
        if approval_input["operation"] != carrier.get("operation_id"):
            errors.append(f"{vector['name']}: operation does not equal the action's registered carrier")
    return errors


def check_repository() -> list[str]:
    fixture = load_json(FIXTURE_PATH)
    errors: list[str] = []

    domain = fixture["signing_domain"]
    if domain.get("domain") != SIGNING_DOMAIN:
        errors.append(f"fixture signing_domain.domain must be {SIGNING_DOMAIN}")
    prefix = SIGNING_DOMAIN.encode("utf-8").hex() + "0a"
    if domain.get("domain_prefix_hex") != prefix:
        errors.append("signing_domain.domain_prefix_hex is not UTF8(domain) || 0x0A")

    expected_public = (
        Ed25519PrivateKey.from_private_bytes(PUBLISHED_SEED).public_key().public_bytes_raw()
    )
    public_key = Ed25519PublicKey.from_public_bytes(expected_public)

    branches = set()
    for vector in fixture["vectors"]:
        errors.extend(check_vector(vector, expected_public))
        approval_input = vector["approval_signature"]["input"]
        branches.add(
            (
                approval_input["approval_context"]["context_kind"],
                approval_input["approval_target"]["target_kind"],
            )
        )
    for required in (("grant", "event"), ("realm_governance", "event"), ("grant", "operation")):
        if required not in branches:
            errors.append(f"no accepted vector covers the branch pair {required}")

    nonces = [v["approval_signature"]["input"]["nonce"] for v in fixture["vectors"]]
    if len(set(nonces)) != len(nonces):
        errors.append("accepted vectors reuse a nonce within one (approval_context, approver) pair")

    errors.extend(check_event_id_invariance(fixture))

    operations = load_json(OPERATION_REGISTRY_PATH)
    operation_rows = operations.get("operations", operations if isinstance(operations, list) else [])
    registered_operations = {
        row.get("operation_id") or row.get("operation")
        for row in operation_rows
        if isinstance(row, dict)
    }
    for case in fixture["negative_cases"]:
        errors.extend(check_negative(case, fixture, public_key, registered_operations))

    errors.extend(check_registrations(fixture))
    return errors


def main() -> int:
    try:
        errors = check_repository()
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"approval-signature KAT checker failed to load inputs: {exc}", file=sys.stderr)
        return 1
    for error in errors:
        print(f"approval-signature KAT: {error}", file=sys.stderr)
    if errors:
        print(f"approval-signature KAT: {len(errors)} error(s)", file=sys.stderr)
        return 1
    print(
        "approval-signature KAT: signing bytes, Ed25519 signatures, event_id invariance and "
        "registry closure verified"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
