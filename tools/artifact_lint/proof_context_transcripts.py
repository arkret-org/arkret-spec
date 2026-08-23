"""Every registered proof context must own a byte-level transcript vector.

``proof-context-registry.json`` decides which fields enter a detached-proof
transcript, and rule 3 of its ``registry_rules`` requires a verifier to reject a
valid signature made under another object family's context. That rule is only
decidable when both sides agree on the transcript bytes, and for a long time only
``ak.event_proof.v1`` had bytes to agree on: the other 62 rows existed as a field
array plus prose, so the unsigned projection, the ``audience`` shape and the
absent-optional encoding were each re-decided per implementation.

This gate closes that direction. Every row must be covered by exactly one
``ak.vector.proof_context.transcript.*`` vector, every vector must carry a case in
``proof-context-transcript-fixture.json``, and every case must recompute: the JCS
of the unsigned projection, its digest, the canonical binding object built from
the registered ``binding_fields`` plus the context constant, the JWS signing input
and the Ed25519 signature. Each case also carries the cross-family replay that
MUST fail, because a positive vector alone cannot prove domain separation.

Adding a context row without a vector fails here rather than silently growing the
untested surface.
"""

from __future__ import annotations

from .core import (
    ARTIFACTS,
    Any,
    Lint,
    Path,
    base64,
    binascii,
    canonical_json,
    hashlib,
    load_json,
    re,
)

try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
except ImportError:  # pragma: no cover - CI installs the dependency.
    InvalidSignature = None
    Ed25519PrivateKey = None
    Ed25519PublicKey = None
    serialization = None


REGISTRY_PATH = ARTIFACTS / "registry" / "proof-context-registry.json"

VECTOR_REGISTRY_PATH = ARTIFACTS / "registry" / "vector-registry.json"

FIXTURE_PATH = ARTIFACTS / "fixtures" / "proof-context-transcript-fixture.json"

SHARED_KEY_FIXTURE_PATH = ARTIFACTS / "fixtures" / "keypackage-write-transcript-fixture.json"

FIXTURE_NAME = FIXTURE_PATH.name

GENERATOR = "tools/regenerate_proof_context_transcript_fixture.py"

VECTOR_ID_RE = re.compile(r"^ak\.vector\.proof_context\.transcript\.([a-z0-9_]+)\.v1$")

# Binding members that carry the digest of the object the proof signs. A row that
# names one of these has an unsigned projection the fixture must pin; a row that
# names none is itself the transcript.
SELF_DIGEST_FIELDS = ("payload_digest", "receipt_digest", "event_digest", "envelope_digest")

PROTECTED_HEADER_ALLOWED_KEYS = frozenset({"alg"})

# Coverage is recorded in vector-registry.json only. A second copy inside the
# proof-context registry would drift, and the two would then disagree about which
# rows are tested.
FORBIDDEN_REGISTRY_COVERAGE_KEYS = (
    "covers_vectors",
    "conformance_vector_id",
    "conformance_vector_ids",
)


def _decode_base64url(lint: Lint, path: Path, label: str, value: Any) -> bytes | None:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        lint.fail(path, f"{label} must be an unpadded base64url string")
        return None
    try:
        decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, binascii.Error):
        lint.fail(path, f"{label} is not valid base64url")
        return None
    if base64.urlsafe_b64encode(decoded).rstrip(b"=").decode("ascii") != value:
        lint.fail(path, f"{label} is not canonical unpadded base64url")
        return None
    return decoded


def _b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _typed_digest(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def check_proof_context_transcript_vectors(lint: Lint) -> None:
    registry = load_json(lint, REGISTRY_PATH)
    if not isinstance(registry, dict):
        return
    rows = registry.get("contexts")
    if not isinstance(rows, list) or not rows:
        return

    families: list[str] = []
    contexts: list[str] = []
    binding_fields: dict[str, list[str]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            return
        context = row.get("context")
        family = row.get("object_family")
        fields = row.get("binding_fields")
        if not isinstance(context, str) or not isinstance(family, str) or not isinstance(fields, list):
            # foundation.py already reports malformed rows; nothing to close here.
            return
        present = [key for key in FORBIDDEN_REGISTRY_COVERAGE_KEYS if key in row]
        if present:
            lint.fail(
                REGISTRY_PATH,
                f"contexts[{index}] declares {', '.join(present)}; transcript vector coverage is "
                "recorded once, in vector-registry.json covers_proof_contexts[]",
            )
        families.append(family)
        contexts.append(context)
        binding_fields[context] = [item for item in fields if isinstance(item, str)]

    covered = _check_vector_rows(lint, contexts, families)
    missing = [context for context in contexts if context not in covered]
    if missing:
        for context in missing:
            family = families[contexts.index(context)]
            lint.fail(
                VECTOR_REGISTRY_PATH,
                f"proof context {context} has no transcript vector: register "
                f"ak.vector.proof_context.transcript.{family}.v1 with "
                f"covers_proof_contexts=[{context!r}] and regenerate {FIXTURE_NAME} with "
                f"{GENERATOR}",
            )

    _check_fixture(lint, rows, contexts, families, binding_fields)


def _check_vector_rows(lint: Lint, contexts: list[str], families: list[str]) -> set[str]:
    data = load_json(lint, VECTOR_REGISTRY_PATH)
    if not isinstance(data, dict):
        return set()
    known_contexts = set(contexts)
    family_of_context = dict(zip(contexts, families))
    covered: set[str] = set()
    claimed_by: dict[str, str] = {}

    for index, row in enumerate(data.get("vectors") or []):
        if not isinstance(row, dict):
            continue
        vector_id = row.get("vector_id")
        if not isinstance(vector_id, str):
            continue
        match = VECTOR_ID_RE.fullmatch(vector_id)
        if match is None:
            continue
        label = f"vectors[{index}] {vector_id}"
        if row.get("status") != "active":
            lint.fail(VECTOR_REGISTRY_PATH, f"{label} must stay active while its context is registered")
        if row.get("applies_to_fixtures") != [FIXTURE_NAME]:
            lint.fail(
                VECTOR_REGISTRY_PATH,
                f"{label}.applies_to_fixtures must be exactly [{FIXTURE_NAME!r}]",
            )
        declared = row.get("covers_proof_contexts")
        if not isinstance(declared, list) or len(declared) != 1 or not isinstance(declared[0], str):
            lint.fail(
                VECTOR_REGISTRY_PATH,
                f"{label}.covers_proof_contexts must be a single-element array naming the one "
                "proof context this transcript vector covers",
            )
            continue
        context = declared[0]
        if context not in known_contexts:
            lint.fail(
                VECTOR_REGISTRY_PATH,
                f"{label}.covers_proof_contexts names an unregistered proof context: {context}",
            )
            continue
        if context in claimed_by:
            lint.fail(
                VECTOR_REGISTRY_PATH,
                f"{label} duplicates transcript coverage of {context}, already claimed by "
                f"{claimed_by[context]}",
            )
            continue
        claimed_by[context] = vector_id
        if match.group(1) != family_of_context[context]:
            lint.fail(
                VECTOR_REGISTRY_PATH,
                f"{label} must be named after the object family it covers: expected "
                f"ak.vector.proof_context.transcript.{family_of_context[context]}.v1",
            )
        covered.add(context)
    return covered


def _check_fixture(
    lint: Lint,
    rows: list[dict[str, Any]],
    contexts: list[str],
    families: list[str],
    binding_fields: dict[str, list[str]],
) -> None:
    data = load_json(lint, FIXTURE_PATH)
    if not isinstance(data, dict):
        return
    if data.get("generated_by") != GENERATOR:
        lint.fail(FIXTURE_PATH, f"generated_by must name {GENERATOR}")

    verifying_key = _check_test_key(lint, data.get("test_key"))

    cases = data.get("cases")
    negative_cases = data.get("negative_cases")
    if not isinstance(cases, list) or len(cases) != len(rows):
        lint.fail(
            FIXTURE_PATH,
            f"cases must carry exactly one entry per registered proof context ({len(rows)}); "
            f"regenerate with {GENERATOR}",
        )
        return
    if not isinstance(negative_cases, list) or len(negative_cases) != len(rows):
        lint.fail(
            FIXTURE_PATH,
            "negative_cases must carry one cross-family replay per registered proof context; a "
            "positive-only vector cannot prove domain separation",
        )
        return

    for index, case in enumerate(cases):
        context = contexts[index]
        family = families[index]
        if not isinstance(case, dict):
            lint.fail(FIXTURE_PATH, f"cases[{index}] must be an object")
            continue
        if case.get("context") != context or case.get("object_family") != family:
            lint.fail(
                FIXTURE_PATH,
                f"cases[{index}] must follow proof-context-registry.json row order: expected "
                f"{family}/{context}",
            )
            continue
        if case.get("vector_id") != f"ak.vector.proof_context.transcript.{family}.v1":
            lint.fail(FIXTURE_PATH, f"cases[{index}].vector_id must be derived from {family}")
        if case.get("declared_binding_fields") != binding_fields[context]:
            lint.fail(
                FIXTURE_PATH,
                f"cases[{index}].declared_binding_fields drifted from the registry row for {context}",
            )
            continue
        binding = _check_case_binding(lint, index, case, context, binding_fields[context])
        signing_input = _check_case_bytes(lint, index, case, binding, verifying_key)
        _check_negative_case(
            lint,
            index,
            case,
            negative_cases[index],
            contexts[(index + 1) % len(contexts)],
            families[(index + 1) % len(families)],
            signing_input,
            verifying_key,
        )


def _check_test_key(lint: Lint, test_key: Any) -> Any:
    if not isinstance(test_key, dict):
        lint.fail(FIXTURE_PATH, "test_key must be an object")
        return None
    shared = load_json(lint, SHARED_KEY_FIXTURE_PATH)
    shared_key = shared.get("test_key") if isinstance(shared, dict) else None
    if isinstance(shared_key, dict) and test_key.get("private_key_seed") != shared_key.get(
        "private_key_seed"
    ):
        lint.fail(
            FIXTURE_PATH,
            "test_key.private_key_seed must be the shared conformance seed already published by "
            "keypackage-write-transcript-fixture.json; a second test key lets an implementation "
            "pass by picking the wrong one",
        )
    seed = _decode_base64url(lint, FIXTURE_PATH, "test_key.private_key_seed", test_key.get("private_key_seed"))
    public = _decode_base64url(lint, FIXTURE_PATH, "test_key.public_key", test_key.get("public_key"))
    if seed is None or public is None:
        return None
    if Ed25519PrivateKey is None or Ed25519PublicKey is None or serialization is None:
        lint.fail(FIXTURE_PATH, "cryptography is required to verify proof context transcripts")
        return None
    if len(seed) != 32 or len(public) != 32:
        lint.fail(FIXTURE_PATH, "test_key Ed25519 seed and public key must each be 32 bytes")
        return None
    derived = Ed25519PrivateKey.from_private_bytes(seed).public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    if derived != public:
        lint.fail(FIXTURE_PATH, "test_key.public_key does not derive from test_key.private_key_seed")
        return None
    return Ed25519PublicKey.from_public_bytes(public)


def _check_case_binding(
    lint: Lint,
    index: int,
    case: dict[str, Any],
    context: str,
    declared: list[str],
) -> dict[str, Any] | None:
    binding = case.get("binding_object")
    if not isinstance(binding, dict):
        lint.fail(FIXTURE_PATH, f"cases[{index}].binding_object must be an object")
        return None

    required = [name for name in declared if not name.endswith("?")]
    optional = [name[:-1] for name in declared if name.endswith("?")]
    omitted = case.get("omitted_optional_binding_fields")
    if not isinstance(omitted, list) or any(name not in optional for name in omitted):
        lint.fail(
            FIXTURE_PATH,
            f"cases[{index}].omitted_optional_binding_fields must list registry optionals only",
        )
        return None
    expected_keys = {"context", *required, *(name for name in optional if name not in omitted)}

    actual_keys = set(binding)
    if actual_keys != expected_keys:
        lint.fail(
            FIXTURE_PATH,
            f"cases[{index}].binding_object keys {sorted(actual_keys)} are not the registered "
            f"binding closure {sorted(expected_keys)}: the context constant plus every required "
            "binding field plus the optionals this case keeps",
        )
        return None
    if binding.get("context") != context:
        lint.fail(FIXTURE_PATH, f"cases[{index}].binding_object.context must be {context}")
        return None
    null_members = sorted(name for name, value in binding.items() if value is None)
    if null_members:
        lint.fail(
            FIXTURE_PATH,
            f"cases[{index}].binding_object writes null for {null_members}; an absent optional "
            "binding field is omitted, never written as null",
        )
        return None

    audience = binding.get("audience")
    if audience is not None:
        if isinstance(audience, list):
            if not audience or any(not isinstance(item, str) or not item for item in audience):
                lint.fail(
                    FIXTURE_PATH,
                    f"cases[{index}].binding_object.audience array must be non-empty strings",
                )
            elif len(set(audience)) != len(audience):
                lint.fail(
                    FIXTURE_PATH,
                    f"cases[{index}].binding_object.audience array must not repeat an entry",
                )
            elif len(audience) == 1:
                lint.fail(
                    FIXTURE_PATH,
                    f"cases[{index}].binding_object.audience wraps one value in an array; a single "
                    "audience uses the single-string form",
                )
        elif not isinstance(audience, str) or not audience:
            lint.fail(
                FIXTURE_PATH,
                f"cases[{index}].binding_object.audience must be a non-empty string or an array "
                "of non-empty strings",
            )

    digest_field = case.get("digest_binding_field")
    self_digests = [name for name in required if name in SELF_DIGEST_FIELDS]
    projection = case.get("unsigned_projection")
    if projection is None:
        if self_digests:
            lint.fail(
                FIXTURE_PATH,
                f"cases[{index}] pins no unsigned projection while {context} binds "
                f"{self_digests[0]}; the digest preimage must be spelled out",
            )
        if digest_field is not None:
            lint.fail(FIXTURE_PATH, f"cases[{index}].digest_binding_field must be null")
        for key in ("unsigned_object", "unsigned_jcs", "unsigned_digest"):
            if case.get(key) is not None:
                lint.fail(FIXTURE_PATH, f"cases[{index}].{key} must be null without a projection")
        if not isinstance(case.get("unsigned_projection_absent_because"), str):
            lint.fail(
                FIXTURE_PATH,
                f"cases[{index}] must state why no unsigned projection exists",
            )
        return binding

    if not self_digests:
        lint.fail(
            FIXTURE_PATH,
            f"cases[{index}] pins an unsigned projection while {context} binds no digest of it",
        )
        return binding
    if digest_field != self_digests[0]:
        lint.fail(
            FIXTURE_PATH,
            f"cases[{index}].digest_binding_field must be {self_digests[0]}",
        )
        return binding
    if not isinstance(projection, dict) or not isinstance(projection.get("removed_members"), list):
        lint.fail(FIXTURE_PATH, f"cases[{index}].unsigned_projection must declare removed_members[]")
        return binding
    pointer = projection.get("subject_pointer")
    if not isinstance(pointer, str):
        lint.fail(FIXTURE_PATH, f"cases[{index}].unsigned_projection.subject_pointer must be a string")
        return binding
    if bool(pointer) == bool(projection["removed_members"]):
        lint.fail(
            FIXTURE_PATH,
            f"cases[{index}].unsigned_projection must either name the digested member "
            "(subject_pointer) or the removed carrier members, never both and never neither",
        )
        return binding
    removed_values = projection.get("removed_member_values")
    if not isinstance(removed_values, dict) or sorted(removed_values) != sorted(
        projection["removed_members"]
    ):
        lint.fail(
            FIXTURE_PATH,
            f"cases[{index}].unsigned_projection.removed_member_values must pin the value of every "
            "removed member, so the fixture shows a deletion rather than a null",
        )
        return binding
    if any(value is None for value in removed_values.values()):
        lint.fail(
            FIXTURE_PATH,
            f"cases[{index}].unsigned_projection removes a member by writing null; the member "
            "itself is deleted from the digest preimage",
        )
        return binding

    unsigned = case.get("unsigned_object")
    if not isinstance(unsigned, dict) or not unsigned:
        lint.fail(FIXTURE_PATH, f"cases[{index}].unsigned_object must be a non-empty object")
        return binding
    overlap = sorted(set(unsigned) & set(projection["removed_members"]))
    if overlap:
        lint.fail(
            FIXTURE_PATH,
            f"cases[{index}].unsigned_object still carries removed member(s) {overlap}",
        )
    expected_jcs = canonical_json(unsigned)
    if case.get("unsigned_jcs") != expected_jcs:
        lint.fail(FIXTURE_PATH, f"cases[{index}].unsigned_jcs is not JCS(unsigned_object)")
        return binding
    expected_digest = _typed_digest(expected_jcs)
    if case.get("unsigned_digest") != expected_digest:
        lint.fail(FIXTURE_PATH, f"cases[{index}].unsigned_digest is not sha256(unsigned_jcs)")
        return binding
    if binding.get(digest_field) != expected_digest:
        lint.fail(
            FIXTURE_PATH,
            f"cases[{index}].binding_object.{digest_field} does not equal the recomputed digest of "
            "the unsigned projection",
        )
    return binding


def _check_case_bytes(
    lint: Lint,
    index: int,
    case: dict[str, Any],
    binding: dict[str, Any] | None,
    verifying_key: Any,
) -> str | None:
    header = case.get("protected_header")
    if not isinstance(header, dict) or set(header) - PROTECTED_HEADER_ALLOWED_KEYS:
        lint.fail(
            FIXTURE_PATH,
            f"cases[{index}].protected_header must carry the protected alg only; the context "
            "constant is a binding object member, never a JWS header parameter",
        )
        return None
    header_jcs = canonical_json(header)
    if case.get("protected_header_jcs") != header_jcs:
        lint.fail(FIXTURE_PATH, f"cases[{index}].protected_header_jcs is not JCS(protected_header)")
        return None
    if binding is None:
        return None
    binding_jcs = canonical_json(binding)
    if case.get("binding_jcs") != binding_jcs:
        lint.fail(FIXTURE_PATH, f"cases[{index}].binding_jcs is not JCS(binding_object)")
        return None

    header_segment = _b64u(header_jcs.encode("utf-8"))
    signing_input = f"{header_segment}.{_b64u(binding_jcs.encode('utf-8'))}"
    if case.get("signing_input_ascii") != signing_input:
        lint.fail(
            FIXTURE_PATH,
            f"cases[{index}].signing_input_ascii is not base64url(protected_header_jcs) || '.' || "
            "base64url(binding_jcs)",
        )
        return None
    signature = case.get("signature")
    if case.get("detached_jws") != f"{header_segment}..{signature}":
        lint.fail(
            FIXTURE_PATH,
            f"cases[{index}].detached_jws must keep an empty payload segment: "
            "base64url(protected_header_jcs) || '..' || signature",
        )
    if case.get("expected_result") != "accept":
        lint.fail(FIXTURE_PATH, f"cases[{index}].expected_result must be 'accept'")
    _verify(lint, f"cases[{index}]", verifying_key, signature, signing_input, must_verify=True)
    return signing_input


def _check_negative_case(
    lint: Lint,
    index: int,
    case: dict[str, Any],
    negative: Any,
    neighbour_context: str,
    neighbour_family: str,
    signing_input: str | None,
    verifying_key: Any,
) -> None:
    label = f"negative_cases[{index}]"
    if not isinstance(negative, dict):
        lint.fail(FIXTURE_PATH, f"{label} must be an object")
        return
    if negative.get("vector_id") != case.get("vector_id"):
        lint.fail(FIXTURE_PATH, f"{label} must belong to the same vector as cases[{index}]")
        return
    if negative.get("registered_context") != case.get("context"):
        lint.fail(FIXTURE_PATH, f"{label}.registered_context must equal cases[{index}].context")
        return
    substituted = negative.get("substituted_context")
    if substituted != neighbour_context or negative.get("substituted_object_family") != neighbour_family:
        lint.fail(
            FIXTURE_PATH,
            f"{label} must replay under the adjacent registry row {neighbour_context}",
        )
        return
    if substituted == case.get("context"):
        lint.fail(FIXTURE_PATH, f"{label} substitutes the context with itself")
        return
    if negative.get("expected_result") != "reject":
        lint.fail(FIXTURE_PATH, f"{label}.expected_result must be 'reject'")
    if not isinstance(negative.get("expected_reason"), str):
        lint.fail(FIXTURE_PATH, f"{label}.expected_reason must name the rejection code")

    binding = case.get("binding_object")
    if not isinstance(binding, dict):
        return
    substituted_binding = dict(binding)
    substituted_binding["context"] = substituted
    expected_jcs = canonical_json(substituted_binding)
    if negative.get("signed_binding_jcs") != expected_jcs:
        lint.fail(
            FIXTURE_PATH,
            f"{label}.signed_binding_jcs must be cases[{index}].binding_object with only the "
            "context member replaced; anything else stops testing domain separation",
        )
        return
    if expected_jcs == case.get("binding_jcs"):
        lint.fail(FIXTURE_PATH, f"{label} produced the same transcript bytes as the accept case")
        return

    header_segment = case.get("signing_input_ascii", "").split(".", 1)[0]
    negative_input = f"{header_segment}.{_b64u(expected_jcs.encode('utf-8'))}"
    signature = negative.get("signature")
    if negative.get("detached_jws") != f"{header_segment}..{signature}":
        lint.fail(FIXTURE_PATH, f"{label}.detached_jws does not match its signature")
    # The replay is only a real negative when the signature is cryptographically
    # sound under the substituted context and still fails against the transcript
    # the receiver rebuilds.
    _verify(lint, f"{label} (under substituted context)", verifying_key, signature, negative_input, must_verify=True)
    if signing_input is not None:
        _verify(
            lint,
            f"{label} (against the registered context)",
            verifying_key,
            signature,
            signing_input,
            must_verify=False,
        )


def _verify(
    lint: Lint,
    label: str,
    verifying_key: Any,
    signature: Any,
    signing_input: str,
    *,
    must_verify: bool,
) -> None:
    if verifying_key is None or InvalidSignature is None:
        return
    raw = _decode_base64url(lint, FIXTURE_PATH, f"{label}.signature", signature)
    if raw is None:
        return
    if len(raw) != 64:
        lint.fail(FIXTURE_PATH, f"{label}.signature must encode exactly 64 Ed25519 bytes")
        return
    try:
        verifying_key.verify(raw, signing_input.encode("ascii"))
    except InvalidSignature:
        if must_verify:
            lint.fail(
                FIXTURE_PATH,
                f"{label}.signature does not verify over its stated signing input; regenerate with "
                f"{GENERATOR}",
            )
        return
    if not must_verify:
        lint.fail(
            FIXTURE_PATH,
            f"{label}.signature verifies against the registered context transcript; the "
            "cross-family replay must not be accepted",
        )
