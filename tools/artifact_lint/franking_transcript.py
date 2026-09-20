"""Close the byte-exact moderation franking-proof signature transcript."""

from __future__ import annotations

from .core import ARTIFACTS, Any, Lint, base64, canonical_json, hashlib, load_json

try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
except ImportError:  # pragma: no cover - CI installs cryptography.
    InvalidSignature = None
    Ed25519PublicKey = None


DOMAIN = "ak.franking_proof.signature.v1"
VECTOR_ID = "ak.vector.moderation.franking_proof_transcript.v1"
REGISTRY = ARTIFACTS / "registry" / "proof-context-registry.json"
VECTOR_REGISTRY = ARTIFACTS / "registry" / "vector-registry.json"
FIXTURE = ARTIFACTS / "fixtures" / "franking-proof-transcript-fixture.json"
FIELDS = [
    "domain",
    "realm_id",
    "event_id",
    "received_by",
    "verification_method",
    "received_at",
    "replay_nonce",
]


def _decode(value: Any) -> bytes | None:
    if not isinstance(value, str):
        return None
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except Exception:
        return None
    if base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii") != value:
        return None
    return raw


def _verifies(public_key: Any, signature: Any, transcript: Any) -> bool:
    raw = _decode(signature)
    if public_key is None or raw is None or not isinstance(transcript, dict):
        return False
    try:
        public_key.verify(raw, canonical_json(transcript).encode("utf-8"))
    except (InvalidSignature, TypeError, ValueError):
        return False
    return True


def _project_webvh_method_controller(verification_method: Any) -> str | None:
    """Apply the registered did:webvh -> did_core projection to one DID URL."""

    if not isinstance(verification_method, str) or "#" not in verification_method:
        return None
    controller, _fragment = verification_method.rsplit("#", 1)
    prefix = "did:webvh:"
    if not controller.startswith(prefix):
        return None
    scid = controller.removeprefix(prefix).split(":", 1)[0]
    if not scid:
        return None
    return f"ak:did_core:webvh:{scid}"


def check_franking_proof_transcript(lint: Lint) -> None:
    registry = load_json(lint, REGISTRY)
    vectors = load_json(lint, VECTOR_REGISTRY)
    fixture = load_json(lint, FIXTURE)
    if not all(isinstance(value, dict) for value in (registry, vectors, fixture)):
        return

    rows = [
        row
        for row in registry.get("domain_separations", [])
        if isinstance(row, dict) and row.get("domain") == DOMAIN
    ]
    if len(rows) != 1:
        lint.fail(REGISTRY, f"{DOMAIN} must have exactly one domain-separation row")
    else:
        row = rows[0]
        if row.get("primitive") != "detached_signature" or row.get("binding_fields") != FIELDS:
            lint.fail(REGISTRY, f"{DOMAIN} must bind the exact seven-field detached-signature transcript")
        if row.get("schema_ref") != "schemas/moderation-evidence.schema.json#/$defs/franking_proof":
            lint.fail(REGISTRY, f"{DOMAIN} schema_ref drifted from the canonical franking-proof payload")

    matching_vectors = [
        row
        for row in vectors.get("vectors", [])
        if isinstance(row, dict) and row.get("vector_id") == VECTOR_ID
    ]
    if len(matching_vectors) != 1 or matching_vectors[0].get("applies_to_fixtures") != [FIXTURE.name]:
        lint.fail(VECTOR_REGISTRY, f"{VECTOR_ID} must cover only {FIXTURE.name}")

    if fixture.get("generated_by") != "tools/regenerate_franking_proof_transcript_fixture.py":
        lint.fail(FIXTURE, "franking transcript fixture generator metadata is invalid")
    if fixture.get("domain") != DOMAIN:
        lint.fail(FIXTURE, f"fixture domain must be {DOMAIN}")
    key = fixture.get("test_key")
    public_raw = _decode(key.get("public_key")) if isinstance(key, dict) else None
    public_key = None
    if public_raw is None or len(public_raw) != 32 or Ed25519PublicKey is None:
        lint.fail(FIXTURE, "test_key.public_key must be a canonical Ed25519 public key")
    else:
        public_key = Ed25519PublicKey.from_public_bytes(public_raw)

    case = fixture.get("case")
    if not isinstance(case, dict):
        lint.fail(FIXTURE, "fixture case must be an object")
        return
    payload = case.get("source_payload")
    transcript = case.get("transcript")
    if not isinstance(payload, dict) or not isinstance(transcript, dict):
        lint.fail(FIXTURE, "source_payload and transcript must be objects")
        return
    if case.get("removed_members") != ["signature"]:
        lint.fail(FIXTURE, "the transcript projection must remove only signature")
    expected = {"domain": DOMAIN, **{field: payload.get(field) for field in FIELDS[1:]}}
    if transcript != expected or list(transcript) != FIELDS:
        lint.fail(FIXTURE, "transcript must be the exact ordered seven-field projection")
    if _project_webvh_method_controller(payload.get("verification_method")) != payload.get("received_by"):
        lint.fail(
            FIXTURE,
            "accept verification_method controller must project exactly to received_by",
        )
    transcript_jcs = canonical_json(transcript)
    transcript_digest = "sha256:" + hashlib.sha256(transcript_jcs.encode("utf-8")).hexdigest()
    if case.get("transcript_jcs") != transcript_jcs or case.get("transcript_digest") != transcript_digest:
        lint.fail(FIXTURE, "transcript JCS bytes or digest do not recompute")
    signature = case.get("signature_b64u")
    if payload.get("signature") != signature or case.get("expected_result") != "accept":
        lint.fail(FIXTURE, "source payload must carry the fixture signature and accept outcome")
    if not _verifies(public_key, signature, transcript):
        lint.fail(FIXTURE, "accept signature does not verify")

    mutations = case.get("bound_field_mutations")
    if not isinstance(mutations, list) or [row.get("field") for row in mutations if isinstance(row, dict)] != FIELDS:
        lint.fail(FIXTURE, f"bound_field_mutations must cover exactly {FIELDS}")
        return
    for index, mutation in enumerate(mutations):
        if not isinstance(mutation, dict):
            continue
        mutated = mutation.get("transcript")
        field = FIELDS[index]
        if (
            mutation.get("expected_result") != "reject_signature_invalid"
            or not isinstance(mutated, dict)
            or set(mutated) != set(FIELDS)
            or mutated.get(field) == transcript.get(field)
            or any(mutated.get(name) != transcript.get(name) for name in FIELDS if name != field)
            or _verifies(public_key, signature, mutated)
        ):
            lint.fail(FIXTURE, f"mutation of bound field {field} does not fail closed")
        if field == "verification_method" and isinstance(mutated, dict):
            if _project_webvh_method_controller(mutated.get("verification_method")) != transcript.get("received_by"):
                lint.fail(
                    FIXTURE,
                    "verification_method mutation must retain the received_by controller so rejection proves signature binding",
                )
