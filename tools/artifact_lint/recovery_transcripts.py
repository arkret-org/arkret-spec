"""Close local recovery signing transcripts and reject registered-context copies."""

from __future__ import annotations

from .core import ARTIFACTS, Any, Lint, base64, canonical_json, hashlib, load_json

try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
except ImportError:  # pragma: no cover - CI installs cryptography.
    InvalidSignature = None
    Ed25519PublicKey = None


REGISTRY = ARTIFACTS / "registry" / "proof-context-registry.json"
VECTOR_REGISTRY = ARTIFACTS / "registry" / "vector-registry.json"
SCHEMA = ARTIFACTS / "schemas" / "recovery-session.schema.json"
POLICY_SCHEMA = ARTIFACTS / "schemas" / "recovery-policy.schema.json"
FIXTURE = ARTIFACTS / "fixtures" / "recovery-transcript-fixture.json"
VECTOR_ID = "ak.vector.identity.recovery_transcript.v1"
DOMAIN = "ak.identity.recovery_proof.v1"
CONDITIONAL_RULE = (
    "kind=did_root MUST omit proof_body; kind in "
    "recovery_unlock|device_quorum|trusted_recovery_service|threshold_recovery "
    "MUST include the matching closed signature-independent proof_body projection"
)
KINDS = [
    "did_root",
    "recovery_unlock",
    "device_quorum",
    "trusted_recovery_service",
    "threshold_recovery",
]
GENERIC_KINDS = KINDS[1:]
COMMON_FIELDS = [
    "schema",
    "kind",
    "request_id",
    "session_grant_id",
    "session_grant_cnf_jkt",
    "account_id",
    "requesting_device_id",
    "trust_domain",
    "policy_id",
    "policy_version",
    "recovery_session_id",
    "identity_model",
    "model_generation_ref",
    "publication_authority_context_digest",
    "challenge",
    "expires_at",
    "created_at",
]
BODY_DEFS = {
    "recovery_unlock": "recovery_unlock_proof_body",
    "device_quorum": "device_quorum_proof_body",
    "trusted_recovery_service": "trusted_recovery_service_proof_body",
    "threshold_recovery": "threshold_recovery_proof_body",
}


def _b64u_decode(value: Any) -> bytes | None:
    if not isinstance(value, str):
        return None
    try:
        decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except Exception:
        return None
    if base64.urlsafe_b64encode(decoded).rstrip(b"=").decode("ascii") != value:
        return None
    return decoded


def _projection(kind: str, proof: Any) -> dict[str, Any] | None:
    if not isinstance(proof, dict):
        return None
    if kind == "did_root":
        return None
    body = {key: value for key, value in proof.items()}
    if kind == "recovery_unlock":
        body.pop("signature", None)
        body.pop("unlock_commitment", None)
    elif kind == "trusted_recovery_service":
        body.pop("signature", None)
    elif kind == "device_quorum":
        rows = body.get("signatures")
        if not isinstance(rows, list):
            return None
        body["signatures"] = [
            {key: value for key, value in row.items() if key != "signature"}
            for row in rows
            if isinstance(row, dict)
        ]
    elif kind == "threshold_recovery":
        rows = body.get("share_releases")
        if not isinstance(rows, list):
            return None
        body["share_releases"] = [
            {key: value for key, value in row.items() if key != "signature"}
            for row in rows
            if isinstance(row, dict)
        ]
    else:
        return None
    return body


def _verify_signature(public_key: Any, signature: Any, transcript: Any) -> bool:
    raw = _b64u_decode(signature)
    if public_key is None or raw is None:
        return False
    try:
        public_key.verify(raw, canonical_json(transcript).encode("utf-8"))
    except (InvalidSignature, ValueError, TypeError):
        return False
    return True


def check_recovery_transcript_closure(lint: Lint) -> None:
    schema = load_json(lint, SCHEMA)
    policy_schema = load_json(lint, POLICY_SCHEMA)
    registry = load_json(lint, REGISTRY)
    fixture = load_json(lint, FIXTURE)
    vectors = load_json(lint, VECTOR_REGISTRY)
    if not all(isinstance(value, dict) for value in (schema, policy_schema, registry, fixture, vectors)):
        return
    defs = schema.get("$defs")
    if not isinstance(defs, dict):
        return

    policy_defs = policy_schema.get("$defs")
    holder = policy_defs.get("recovery_share_holder") if isinstance(policy_defs, dict) else None
    expected_holder_branches = [
        {
            "properties": {"holder_kind": {"const": "personal_principal"}},
            "required": ["holder_principal_id"],
            "not": {"required": ["holder_service_id"]},
        },
        {
            "properties": {"holder_kind": {"const": "custodial_service"}},
            "required": ["holder_service_id"],
            "not": {"required": ["holder_principal_id"]},
        },
    ]
    if not isinstance(holder, dict):
        lint.fail(POLICY_SCHEMA, "$defs.recovery_share_holder is required")
    else:
        holder_properties = holder.get("properties", {})
        if set(holder_properties) != {
            "holder_kind",
            "holder_principal_id",
            "holder_service_id",
        }:
            lint.fail(
                POLICY_SCHEMA,
                "recovery_share_holder must expose only holder_kind plus the personal-principal and custodial-service branch fields",
            )
        if holder_properties.get("holder_kind", {}).get("enum") != [
            "personal_principal",
            "custodial_service",
        ]:
            lint.fail(POLICY_SCHEMA, "recovery_share_holder holder_kind must be the exact two-branch enum")
        if holder.get("oneOf") != expected_holder_branches:
            lint.fail(
                POLICY_SCHEMA,
                "recovery_share_holder branches must require exactly one matching branch-specific holder field",
            )

    expected_holder_ref = {
        "$ref": "./recovery-policy.schema.json#/$defs/recovery_share_holder"
    }
    for definition in ("threshold_recovery_proof", "threshold_recovery_proof_body"):
        try:
            release_item = defs[definition]["properties"]["share_releases"]["items"]
        except (KeyError, TypeError):
            release_item = None
        if not isinstance(release_item, dict) or release_item.get("allOf") != [expected_holder_ref]:
            lint.fail(
                SCHEMA,
                f"$defs.{definition} share releases must reuse recovery_share_holder exactly",
            )

    proof_kind = defs.get("proof_kind")
    proof_enum = proof_kind.get("enum") if isinstance(proof_kind, dict) else None
    if proof_enum != KINDS:
        lint.fail(SCHEMA, f"$defs.proof_kind.enum must be exactly {KINDS}")

    submit = defs.get("recovery_session_proof_submit_request_body")
    try:
        submit_refs = [row["$ref"].removeprefix("#/$defs/") for row in submit["properties"]["proof"]["oneOf"]]
    except (KeyError, TypeError):
        submit_refs = []
    expected_submit = [f"{kind}_proof" for kind in KINDS]
    if submit_refs != expected_submit:
        lint.fail(SCHEMA, f"proof submit oneOf must be exactly {expected_submit}")

    did_root = defs.get("did_root_transcript")
    generic = defs.get("generic_recovery_transcript")
    try:
        if did_root["properties"]["kind"].get("const") != "did_root":
            raise KeyError
        if "proof_body" in did_root.get("properties", {}) or "proof_body" in did_root.get("required", []):
            lint.fail(SCHEMA, "did_root_transcript must not admit proof_body")
    except (KeyError, TypeError):
        lint.fail(SCHEMA, "did_root_transcript must fix kind=did_root")
    try:
        generic_enum = generic["properties"]["kind"]["enum"]
    except (KeyError, TypeError):
        generic_enum = None
    if generic_enum != GENERIC_KINDS:
        lint.fail(SCHEMA, f"generic_recovery_transcript kind enum must be exactly {GENERIC_KINDS}")
    for kind, def_name in BODY_DEFS.items():
        body = defs.get(def_name)
        const = body.get("properties", {}).get("kind", {}).get("const") if isinstance(body, dict) else None
        if const != kind or body.get("additionalProperties") is not False:
            lint.fail(SCHEMA, f"$defs.{def_name} must be a closed projection for {kind}")

    rows = [row for row in registry.get("domain_separations", []) if isinstance(row, dict) and row.get("domain") == DOMAIN]
    if len(rows) != 1:
        lint.fail(REGISTRY, f"{DOMAIN} must have exactly one domain_separations row")
    else:
        row = rows[0]
        if row.get("object_family") != "recovery_session_factor_transcript" or row.get("primitive") != "detached_signature":
            lint.fail(REGISTRY, f"{DOMAIN} must register the recovery transcript detached-signature family")
        if row.get("binding_fields") != [*COMMON_FIELDS, "proof_body?"]:
            lint.fail(REGISTRY, f"{DOMAIN} binding_fields drifted from the closed transcript tuple")
        if row.get("conditional_binding_rule") != CONDITIONAL_RULE:
            lint.fail(REGISTRY, f"{DOMAIN} conditional factor/body partition drifted")
        if row.get("transcript_schema_refs") != [
            "schemas/recovery-session.schema.json#/$defs/did_root_transcript",
            "schemas/recovery-session.schema.json#/$defs/generic_recovery_transcript",
        ]:
            lint.fail(REGISTRY, f"{DOMAIN} must point to both recovery transcript schemas")

    matching_vectors = [
        row for row in vectors.get("vectors", [])
        if isinstance(row, dict) and row.get("vector_id") == VECTOR_ID
    ]
    if len(matching_vectors) != 1 or matching_vectors[0].get("applies_to_fixtures") != [FIXTURE.name]:
        lint.fail(VECTOR_REGISTRY, f"{VECTOR_ID} must cover only {FIXTURE.name}")

    if fixture.get("generated_by") != "tools/regenerate_recovery_transcript_fixture.py" or fixture.get("domain") != DOMAIN:
        lint.fail(FIXTURE, "recovery transcript fixture generator/domain metadata is invalid")
    key = fixture.get("test_key")
    public_raw = _b64u_decode(key.get("public_key")) if isinstance(key, dict) else None
    public_key = None
    if public_raw is None or len(public_raw) != 32 or Ed25519PublicKey is None:
        lint.fail(FIXTURE, "test_key.public_key must be a canonical Ed25519 public key")
    else:
        public_key = Ed25519PublicKey.from_public_bytes(public_raw)

    cases = fixture.get("cases")
    if not isinstance(cases, list) or [case.get("kind") for case in cases if isinstance(case, dict)] != KINDS:
        lint.fail(FIXTURE, f"cases must cover the five recovery factors in order: {KINDS}")
        return
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            continue
        kind = KINDS[index]
        transcript = case.get("transcript")
        proof = case.get("source_proof")
        if not isinstance(transcript, dict) or transcript.get("kind") != kind:
            lint.fail(FIXTURE, f"cases[{index}].transcript has the wrong kind")
            continue
        expected_keys = set(COMMON_FIELDS) | ({"proof_body"} if kind != "did_root" else set())
        if set(transcript) != expected_keys:
            lint.fail(FIXTURE, f"cases[{index}].transcript does not bind the exact factor field closure")
        projected = _projection(kind, proof)
        if kind == "did_root":
            if "proof_body" in transcript:
                lint.fail(FIXTURE, "did_root fixture transcript must omit proof_body")
        elif transcript.get("proof_body") != projected:
            lint.fail(FIXTURE, f"cases[{index}].proof_body is not the closed projection of source_proof")
        jcs = canonical_json(transcript)
        digest = "sha256:" + hashlib.sha256(jcs.encode("utf-8")).hexdigest()
        if case.get("transcript_jcs") != jcs or case.get("transcript_digest") != digest:
            lint.fail(FIXTURE, f"cases[{index}] transcript bytes/digest mismatch")
        signature = case.get("signature_b64u")
        if case.get("expected_result") != "accept" or not _verify_signature(public_key, signature, transcript):
            lint.fail(FIXTURE, f"cases[{index}] accept signature does not verify")
        replay = case.get("cross_factor_replay")
        replay_transcript = replay.get("transcript") if isinstance(replay, dict) else None
        if not isinstance(replay_transcript, dict) or replay.get("expected_result") != "reject_signature_invalid" or _verify_signature(public_key, signature, replay_transcript):
            lint.fail(FIXTURE, f"cases[{index}] cross-factor replay does not fail closed")
        for field in expected_keys:
            mutated = dict(transcript)
            mutated[field] = None if transcript.get(field) is not None else "mutated"
            if _verify_signature(public_key, signature, mutated):
                lint.fail(FIXTURE, f"cases[{index}] mutation of bound field {field} still verifies")


def check_registered_context_schema_duplicates(lint: Lint) -> None:
    registry = load_json(lint, REGISTRY)
    if not isinstance(registry, dict):
        return
    contexts = {
        row.get("context"): row.get("binding_fields")
        for row in registry.get("contexts", [])
        if isinstance(row, dict) and isinstance(row.get("context"), str)
    }
    for path in sorted((ARTIFACTS / "schemas").glob("*.json")):
        document = load_json(lint, path)
        if not isinstance(document, dict):
            continue
        stack: list[tuple[str, Any]] = [("", document)]
        while stack:
            pointer, node = stack.pop()
            if isinstance(node, dict):
                properties = node.get("properties")
                context = properties.get("context", {}).get("const") if isinstance(properties, dict) else None
                if context in contexts and node.get("additionalProperties") is False:
                    declared = contexts[context]
                    required = {field for field in declared if isinstance(field, str) and not field.endswith("?")}
                    optional = {field[:-1] for field in declared if isinstance(field, str) and field.endswith("?")}
                    keys = set(properties)
                    if keys == {"context", *required, *optional}:
                        lint.fail(path, f"{pointer or '/'} re-enumerates registered proof context {context}; registry + byte-exact vector are the sole transcript closure")
                for key, value in node.items():
                    stack.append((f"{pointer}/{key}", value))
            elif isinstance(node, list):
                for index, value in enumerate(node):
                    stack.append((f"{pointer}/{index}", value))
