"""Artifact lint phase 4: fixtures."""

from __future__ import annotations

import hmac
import textwrap

from .core import (
    ARTIFACTS,
    Any,
    Iterable,
    Lint,
    NEGATIVE_TOKEN_PATH_SEGMENTS,
    ONE_OF_REFERENCE_RE,
    PLACEHOLDER_DIGEST_FIXTURES,
    PROFILE_ID_TOKEN_RE,
    Path,
    ROOT,
    Registry,
    Resource,
    SCHEMA_ID_TOKEN_RE,
    SPEC_ROOT,
    STATED_PREIMAGE_DIGEST_PAIRS,
    STATED_PREIMAGE_KEY_RE,
    TYPED_ID_TOKEN_RE,
    UNPAIRED_STATED_PREIMAGE_KEYS,
    VECTOR_ID_TOKEN_RE,
    Draft202012Validator,
    base64,
    binascii,
    canonical_json,
    check_event_envelope_candidates,
    check_json_instance_against_schema,
    check_typed_id_token,
    json_path_to_pointer,
    copy,
    datetime,
    hashlib,
    json,
    load_json,
    load_json_schema_for_uri,
    load_schema_document,
    markdown_files,
    markdown_section_digest,
    raw_artifact_files,
    re,
    read_text,
    resolve_artifact_schema_ref,
    resolve_json_pointer,
    schema_format_checker,
    unicodedata,
    urllib,
    walk_json,
)

from .schemas import CONTENT_ADDRESSED_REF_MIRROR_REMOVALS

CONTENT_ADDRESSED_TYPED_REF_RE = re.compile(r"ak:[a-z_]+:(?:sha256|blake3):[0-9a-f]{64}")
NEGATIVE_BRANCH_KEY_TOKENS = ("negative", "invalid", "malformed", "rejected", "tampered")

try:
    from cryptography.exceptions import InvalidSignature, InvalidTag
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305
except ImportError:  # pragma: no cover - CI installs the dependency.
    InvalidSignature = None
    InvalidTag = None
    Ed25519PrivateKey = None
    Ed25519PublicKey = None
    X25519PrivateKey = None
    serialization = None
    AESGCM = None
    ChaCha20Poly1305 = None


def sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def base64url_text(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).rstrip(b"=").decode("ascii")


def sha256_base64url_text(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def mls_varint(value: int) -> bytes:
    if value < 0:
        raise ValueError("MLS variable-length integers cannot be negative")
    if value < 64:
        return bytes((value,))
    if value < 16_384:
        return (value | 0x4000).to_bytes(2, "big")
    if value < 1_073_741_824:
        return (value | 0x80000000).to_bytes(4, "big")
    if value < 4_611_686_018_427_387_904:
        return (value | 0xC000000000000000).to_bytes(8, "big")
    raise ValueError("MLS variable-length integer exceeds the RFC 9420 range")


def hkdf_expand_sha256(secret: bytes, info: bytes, length: int) -> bytes:
    hash_length = hashlib.sha256().digest_size
    if length < 0 or length > 255 * hash_length:
        raise ValueError("HKDF-SHA256 output length is out of range")
    output = bytearray()
    previous = b""
    for counter in range(1, (length + hash_length - 1) // hash_length + 1):
        previous = hmac.new(
            secret, previous + info + bytes((counter,)), hashlib.sha256
        ).digest()
        output.extend(previous)
    return bytes(output[:length])


def mls_expand_with_label_sha256(
    secret: bytes, label: str, context: bytes, length: int
) -> bytes:
    full_label = ("MLS 1.0 " + label).encode("utf-8")
    info = (
        length.to_bytes(2, "big")
        + mls_varint(len(full_label))
        + full_label
        + mls_varint(len(context))
        + context
    )
    return hkdf_expand_sha256(secret, info, length)


def check_content_bound_event_id_fixture(lint: Lint) -> None:
    path = ARTIFACTS / "fixtures" / "content-bound-event-id-fixture.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return
    if data.get("generated_by") != "tools/generate_content_bound_event_id_fixture.py":
        lint.fail(path, "suite-tagged Event-ID fixture must name its deterministic generator")
    required = {
        "full_digest_single_bit_difference_changes_event_id",
        "suite_code_mismatch_rejected",
        "invalid_zero_suite_code_rejected",
        "nonzero_event_reserved_nibble_rejected",
        "reserved_suite_code_rejected",
        "unknown_suite_code_rejected",
        "padding_rejected",
        "wrong_decoded_length_rejected",
        "same_event_id_different_canonical_bytes_is_hash_collision",
        "principal_control_realm_id_is_event_derived_and_nonzero_nibble_rejected",
        "human_pcr_genesis_on_a_second_station_derives_a_distinct_realm_id",
        "human_founding_device_authorize_binds_the_derived_realm",
        "same_account_second_genesis_rejected_by_station_account_uniqueness",
    }
    names: set[str] = set()
    for case in data.get("cases", []):
        if not isinstance(case, dict):
            continue
        name = case.get("name")
        if isinstance(name, str):
            names.add(name)
        digest_wire = case.get("event_digest")
        suite_code = case.get("suite_wire_code")
        expected_id = case.get("derived_event_id")
        if not (isinstance(digest_wire, str) and isinstance(suite_code, int) and isinstance(expected_id, str)):
            continue
        try:
            digest = bytes.fromhex(digest_wire.split(":", 1)[1])
        except (IndexError, ValueError):
            lint.fail(path, f"{name}: invalid event_digest")
            continue
        body = bytes((suite_code,)) + digest
        token = base64.urlsafe_b64encode(body).rstrip(b"=").decode("ascii")
        if len(digest) != 32 or len(body) != 33 or len(token) != 44:
            lint.fail(path, f"{name}: Event-ID byte/encoding length mismatch")
            continue
        if case.get("event_id_bytes_hex") != body.hex() or expected_id != "ak:event:" + token:
            lint.fail(path, f"{name}: suite-tagged Event-ID KAT mismatch")
        preimage = case.get("digest_preimage_canonical_bytes_utf8")
        if isinstance(preimage, str) and digest_wire.startswith("sha256:"):
            if hashlib.sha256(preimage.encode("utf-8")).digest() != digest:
                lint.fail(path, f"{name}: stated SHA-256 digest preimage mismatch")
    for name in sorted(required - names):
        lint.fail(path, f"missing required Event-ID case {name}")

    cases_by_name = {
        case.get("name"): case
        for case in data.get("cases", [])
        if isinstance(case, dict) and isinstance(case.get("name"), str)
    }
    human_pcr = cases_by_name.get(
        "principal_control_realm_id_is_event_derived_and_nonzero_nibble_rejected"
    )
    if not isinstance(human_pcr, dict) or (
        human_pcr.get("principal_kind"),
        human_pcr.get("realm_purpose"),
        human_pcr.get("accepted_form", {}).get("realm_id_source"),
        human_pcr.get("accepted_form", {}).get("retype_is_byte_identical"),
    ) != (
        "human",
        "principal_control",
        "retype_of_genesis_ak_realm_create_event_token",
        True,
    ):
        lint.fail(
            path,
            "human PCR vector must assert byte-identical realm_id retyping from its "
            "ak.realm.create event_id",
        )
    _check_human_pcr_genesis_chain(lint, path, cases_by_name)

    agent_pcr = cases_by_name.get(
        "agent_provision_forward_declaration_is_constructible"
    )
    if not isinstance(agent_pcr, dict) or (
        agent_pcr.get("principal_kind"),
        agent_pcr.get("realm_purpose"),
        agent_pcr.get("expected", {}).get("realm_id_source"),
    ) != (
        "agent",
        "agent_control",
        "derived_from_event_id",
    ):
        lint.fail(
            path,
            "Agent PCR vector must assert realm_id derivation from its "
            "ak.realm.create event_id",
        )
    elif agent_pcr.get("derived_realm_id", "").removeprefix(
        "ak:realm:"
    ) != agent_pcr.get("derived_event_id", "").removeprefix("ak:event:"):
        lint.fail(
            path,
            "Agent PCR vector realm_id and event_id tokens must be byte-identical",
        )

    # The class C exemption is a two-step constructibility proof, and the two
    # steps live in separate cases. 914279c0 recomputed step 1 and left step 2
    # declaring the previous realm id, so the pair claimed
    # declaration_equals_step_1_derived_realm_id while naming two different
    # Realms. Each half stayed internally consistent, which is why every digest
    # check passed; only the cross-case comparison can see it.
    declaration = cases_by_name.get("agent_provision_declares_the_frozen_genesis_realm_id")
    if isinstance(declaration, dict) and isinstance(agent_pcr, dict):
        expected_realm_id = agent_pcr.get("derived_realm_id")
        if declaration.get("expected", {}).get(
            "declaration_equals_step_1_derived_realm_id"
        ) is not True:
            lint.fail(
                path,
                "the provision declaration case must assert that it equals the step 1 "
                "derived realm id; without that assertion the exemption has no vector",
            )
        declared = declaration.get("declared_principal_control_realm_id")
        if declared != expected_realm_id:
            lint.fail(
                path,
                f"provision declares principal_control_realm_id={declared} but step 1 "
                f"derives {expected_realm_id}",
            )
        preimage = declaration.get("digest_preimage_canonical_bytes_utf8")
        if isinstance(preimage, str):
            try:
                envelope = json.loads(preimage)
            except json.JSONDecodeError:
                envelope = None
            carried = (
                envelope.get("payload", {}).get("principal_control_realm_id")
                if isinstance(envelope, dict)
                else None
            )
            if carried != expected_realm_id:
                lint.fail(
                    path,
                    f"the provision preimage carries principal_control_realm_id="
                    f"{carried} but step 1 derives {expected_realm_id}; the declared "
                    "value and the hashed value must be one value",
                )

    single_bit_case = next(
        (
            case
            for case in data.get("cases", [])
            if isinstance(case, dict)
            and case.get("name") == "full_digest_single_bit_difference_changes_event_id"
        ),
        None,
    )
    if isinstance(single_bit_case, dict):
        try:
            first = base64.urlsafe_b64decode(single_bit_case["first_event_id"].split(":", 2)[2] + "==")
            second = base64.urlsafe_b64decode(single_bit_case["second_event_id"].split(":", 2)[2] + "==")
        except (KeyError, ValueError):
            lint.fail(path, "single-bit Event-ID case contains an invalid typed ID")
        else:
            differing_bits = sum((left ^ right).bit_count() for left, right in zip(first, second, strict=True))
            if len(first) != 33 or len(second) != 33 or first[0] != second[0] or differing_bits != 1:
                lint.fail(path, "single-bit Event-ID case must differ by exactly one digest bit")



# --- general derived-relation evidence gate (0520) --------------------------
# A fixture may assert that one value is derived from another: an Event id from
# its canonical preimage, a Realm id from that Event token, a digest from a
# canonical object. Those assertions used to be prose members next to the
# values, so a case could claim "retype_is_byte_identical" while carrying no
# bytes at all, and nothing failed. A relation row instead names the rule, the
# exact input locations and the exact output location, and this gate recomputes
# it. Declaring the relation is therefore the only way to pass, and deleting the
# declaration is a failure rather than a silently lost obligation.

BASE58BTC_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def base58btc_decode(text: str) -> bytes:
    value = 0
    for character in text:
        position = BASE58BTC_ALPHABET.find(character)
        if position < 0:
            raise ValueError(f"{character!r} is not a base58btc character")
        value = value * 58 + position
    body = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return bytes(len(text) - len(text.lstrip("1"))) + body


DERIVED_RELATION_INPUTS: dict[str, dict[str, str]] = {
    "event_id_from_canonical_preimage": {
        "canonical_preimage_utf8": "ref",
        "suite_wire_code": "ref",
    },
    "retype_typed_id": {"source_typed_id": "ref"},
    "reserved_nibble_only_mutation": {"accepted_typed_id": "ref"},
    "event_preimage_member": {
        "canonical_preimage_utf8": "ref",
        "member_pointer": "literal",
    },
    "did_core_projection": {"did": "ref", "did_method": "ref"},
    "sha256_of_canonical_json": {"object": "ref"},
    "equal_json_value": {"left": "ref"},
    "ed25519_signature_over_prefixed_canonical_json": {
        "domain": "ref",
        "canonical_json": "ref",
        "public_key_did": "ref",
    },
}

# Relations whose output is by construction a rejected value, so the usual
# "accepted evidence only" rule does not apply to that one endpoint.
NEGATIVE_OUTPUT_RELATIONS = frozenset({"reserved_nibble_only_mutation"})

# (fixture, relation, canonical output reference) triples that MUST stay
# declared. Without this table a mutation could delete the declaration and the
# gate would report a clean fixture with nothing left to recompute.
REQUIRED_DERIVED_RELATIONS: tuple[tuple[str, str, str], ...] = (
    (
        "content-bound-event-id-fixture.json",
        "event_id_from_canonical_preimage",
        "case:principal_control_realm_id_is_event_derived_and_nonzero_nibble_rejected#/derived_event_id",
    ),
    (
        "content-bound-event-id-fixture.json",
        "retype_typed_id",
        "case:principal_control_realm_id_is_event_derived_and_nonzero_nibble_rejected#/derived_realm_id",
    ),
    (
        "content-bound-event-id-fixture.json",
        "reserved_nibble_only_mutation",
        "case:principal_control_realm_id_is_event_derived_and_nonzero_nibble_rejected#/rejected_form/realm_id",
    ),
    (
        "content-bound-event-id-fixture.json",
        "did_core_projection",
        "case:principal_control_realm_id_is_event_derived_and_nonzero_nibble_rejected#/identity_bindings/projected_principal_id",
    ),
    (
        "content-bound-event-id-fixture.json",
        "equal_json_value",
        "case:principal_control_realm_id_is_event_derived_and_nonzero_nibble_rejected#/identity_bindings/actor_principal_id",
    ),
    (
        "content-bound-event-id-fixture.json",
        "sha256_of_canonical_json",
        "fixture:pcr-genesis-fixture.json#/founding_device_descriptor/founding_authorize_payload_digest",
    ),
    (
        "content-bound-event-id-fixture.json",
        "ed25519_signature_over_prefixed_canonical_json",
        "fixture:pcr-genesis-fixture.json#/device_possession/device_signature",
    ),
    (
        "content-bound-event-id-fixture.json",
        "event_id_from_canonical_preimage",
        "case:human_pcr_genesis_on_a_second_station_derives_a_distinct_realm_id#/derived_event_id",
    ),
    (
        "content-bound-event-id-fixture.json",
        "event_id_from_canonical_preimage",
        "case:human_founding_device_authorize_binds_the_derived_realm#/derived_event_id",
    ),
    (
        "content-bound-event-id-fixture.json",
        "event_preimage_member",
        "case:principal_control_realm_id_is_event_derived_and_nonzero_nibble_rejected#/derived_realm_id",
    ),
    (
        "content-bound-event-id-fixture.json",
        "retype_typed_id",
        "case:strand_object_id_is_retyped_event_id#/derived_object_id",
    ),
    (
        "content-bound-event-id-fixture.json",
        "retype_typed_id",
        "case:agent_provision_forward_declaration_is_constructible#/derived_realm_id",
    ),
    (
        "content-bound-event-id-fixture.json",
        "equal_json_value",
        "case:agent_provision_forward_declaration_is_constructible#/derived_realm_id",
    ),
)

_RELATION_MISSING = object()


def _relation_ref_key(reference: Any) -> str | None:
    if not isinstance(reference, dict) or not isinstance(reference.get("pointer"), str):
        return None
    case = reference.get("case")
    fixture = reference.get("fixture")
    if isinstance(case, str) and fixture is None:
        return f"case:{case}#{reference['pointer']}"
    if isinstance(fixture, str) and case is None:
        return f"fixture:{fixture}#{reference['pointer']}"
    return None


def _resolve_relation_ref(
    lint: Lint, path: Path, cases: dict[str, Any], reference: Any
) -> tuple[Any, str | None]:
    """Resolve one relation endpoint. A stale reference is a failure, not a skip."""
    key = _relation_ref_key(reference)
    if key is None:
        lint.fail(
            path,
            "derived relation endpoint MUST be {case|fixture, pointer} with exactly one "
            f"of case/fixture: {reference!r}",
        )
        return _RELATION_MISSING, None
    pointer = reference["pointer"]
    if "case" in reference:
        document = cases.get(reference["case"], _RELATION_MISSING)
        if document is _RELATION_MISSING:
            lint.fail(path, f"derived relation names no such case: {reference['case']}")
            return _RELATION_MISSING, key
    else:
        target = ARTIFACTS / "fixtures" / reference["fixture"]
        if not target.is_file():
            lint.fail(path, f"derived relation names no such fixture: {reference['fixture']}")
            return _RELATION_MISSING, key
        document = load_json(lint, target)
    try:
        value = resolve_json_pointer(document, "#" + pointer)
    except (KeyError, IndexError, TypeError, ValueError):
        lint.fail(path, f"derived relation pointer does not resolve: {key}")
        return _RELATION_MISSING, key
    if value is None:
        lint.fail(path, f"derived relation pointer resolves to null: {key}")
        return _RELATION_MISSING, key
    return value, key


def _relation_case_outcome(cases: dict[str, Any], reference: Any) -> str | None:
    if not isinstance(reference, dict) or not isinstance(reference.get("case"), str):
        return None
    case = cases.get(reference["case"])
    if not isinstance(case, dict):
        return None
    expected = case.get("expected")
    if isinstance(expected, dict) and isinstance(expected.get("outcome"), str):
        return expected["outcome"]
    return None


def _typed_id_parts(value: Any) -> tuple[str, bytes] | None:
    if not isinstance(value, str) or value.count(":") != 2:
        return None
    namespace, kind, token = value.split(":")
    if namespace != "ak" or len(token) != 44:
        return None
    try:
        body = base64.urlsafe_b64decode(token + "==")
    except (binascii.Error, ValueError):
        return None
    if len(body) != 33 or base64.urlsafe_b64encode(body).rstrip(b"=").decode("ascii") != token:
        return None
    return kind, body


def _did_core_projection_prefix(lint: Lint, path: Path, method: Any) -> str | None:
    """Projection is method-defined, so the gate reads the adapter, never a guess."""
    registry = load_json(lint, ARTIFACTS / "registry" / "did-method-adapter-registry.json")
    if not isinstance(registry, dict):
        return None
    for adapter in registry.get("adapters", []):
        if not isinstance(adapter, dict) or adapter.get("method") != method:
            continue
        if adapter.get("status") != "active":
            lint.fail(path, f"did_core_projection names an inactive adapter: {method}")
            return None
        template = adapter.get("core_projection")
        if template != "ak:did_core:webvh:<validated-scid>":
            lint.fail(
                path,
                f"did_core_projection cannot recompute {method}: this gate only implements the "
                f"validated-SCID projection, and the adapter declares {template!r}",
            )
            return None
        return "ak:did_core:webvh:"
    lint.fail(path, f"did_core_projection names no registered adapter: {method!r}")
    return None


def _check_one_derived_relation(
    lint: Lint, path: Path, cases: dict[str, Any], row: Any
) -> tuple[str, str] | None:
    if not isinstance(row, dict):
        lint.fail(path, "derived_relations entries MUST be objects")
        return None
    relation = row.get("relation")
    specification = DERIVED_RELATION_INPUTS.get(relation) if isinstance(relation, str) else None
    if specification is None:
        lint.fail(path, f"unknown derived relation {relation!r}")
        return None
    inputs = row.get("inputs")
    if not isinstance(inputs, dict) or set(inputs) != set(specification):
        lint.fail(
            path,
            f"{relation} inputs MUST be exactly {sorted(specification)}, got "
            f"{sorted(inputs) if isinstance(inputs, dict) else inputs!r}",
        )
        return None
    output_value, output_key = _resolve_relation_ref(lint, path, cases, row.get("output"))
    if output_key is None:
        return None
    if _relation_case_outcome(cases, row.get("output")) not in (None, "accepted") and (
        relation not in NEGATIVE_OUTPUT_RELATIONS
    ):
        lint.fail(
            path,
            f"{relation} output {output_key} belongs to a rejected case, so recomputing it "
            "proves nothing about accepted material",
        )
    resolved: dict[str, Any] = {}
    for member, form in specification.items():
        if form == "literal":
            resolved[member] = inputs[member]
            continue
        value, key = _resolve_relation_ref(lint, path, cases, inputs[member])
        if key == output_key:
            lint.fail(path, f"{relation} input {member} is its own output: {key}")
        if _relation_case_outcome(cases, inputs[member]) not in (None, "accepted"):
            lint.fail(
                path,
                f"{relation} input {member} reads rejected case material at {key}; a negative "
                "case cannot serve as accepted evidence",
            )
        resolved[member] = value
    if output_value is _RELATION_MISSING or any(
        value is _RELATION_MISSING for value in resolved.values()
    ):
        return None
    _recompute_derived_relation(lint, path, relation, resolved, output_value, output_key)
    return relation, output_key


def _recompute_derived_relation(
    lint: Lint,
    path: Path,
    relation: str,
    inputs: dict[str, Any],
    output: Any,
    output_key: str,
) -> None:
    def wrong(detail: str) -> None:
        lint.fail(path, f"{relation} does not hold for {output_key}: {detail}")

    if relation == "event_id_from_canonical_preimage":
        preimage, suite = inputs["canonical_preimage_utf8"], inputs["suite_wire_code"]
        if not isinstance(preimage, str) or not isinstance(suite, int) or isinstance(suite, bool):
            wrong("inputs are not canonical UTF-8 bytes plus an integer suite wire code")
            return
        if not 0 < suite <= 0x0F:
            wrong(f"suite wire code {suite} is outside the uint4 range")
            return
        body = bytes((suite,)) + hashlib.sha256(preimage.encode("utf-8")).digest()
        expected = "ak:event:" + base64.urlsafe_b64encode(body).rstrip(b"=").decode("ascii")
        if output != expected:
            wrong(f"recomputed {expected}")
        return

    if relation == "retype_typed_id":
        source = _typed_id_parts(inputs["source_typed_id"])
        target = _typed_id_parts(output)
        if source is None or target is None:
            wrong("both endpoints MUST be 33-octet typed ID tokens")
            return
        if source[1] != target[1]:
            wrong("retyping MUST keep all 33 octets and change only the typed prefix")
        elif source[0] == target[0]:
            wrong("a retype MUST change the typed kind; the two endpoints name one kind")
        return

    if relation == "reserved_nibble_only_mutation":
        accepted = _typed_id_parts(inputs["accepted_typed_id"])
        mutated = _typed_id_parts(output)
        if accepted is None or mutated is None:
            wrong("both endpoints MUST be 33-octet typed ID tokens")
            return
        if accepted[0] != mutated[0]:
            wrong("the mutation MUST keep the typed kind")
        if accepted[1][1:] != mutated[1][1:]:
            wrong("the mutation MUST change only the header octet")
        if accepted[1][0] >> 4 != 0:
            wrong("the accepted token MUST carry a zero reserved high nibble")
        if mutated[1][0] >> 4 == 0:
            wrong("the rejected token MUST carry a non-zero reserved high nibble")
        if accepted[1][0] & 0x0F != mutated[1][0] & 0x0F:
            wrong("the mutation MUST NOT also change the digest suite nibble")
        return

    if relation == "event_preimage_member":
        preimage, pointer = inputs["canonical_preimage_utf8"], inputs["member_pointer"]
        if not isinstance(preimage, str) or not isinstance(pointer, str):
            wrong("inputs are not canonical UTF-8 bytes plus a JSON Pointer")
            return
        try:
            document = json.loads(preimage)
        except json.JSONDecodeError:
            wrong("the stated preimage is not valid JSON")
            return
        if canonical_json(document) != preimage:
            wrong("the stated preimage bytes are not canonical JSON")
            return
        try:
            carried = resolve_json_pointer(document, "#" + pointer)
        except (KeyError, IndexError, TypeError, ValueError):
            wrong(f"the preimage has no member at {pointer}")
            return
        if carried != output:
            wrong(f"the hashed bytes carry {carried!r} at {pointer}")
        return

    if relation == "did_core_projection":
        prefix = _did_core_projection_prefix(lint, path, inputs["did_method"])
        if prefix is None:
            return
        did = inputs["did"]
        if not isinstance(did, str) or not did.startswith(inputs["did_method"] + ":"):
            wrong(f"{did!r} is not a bare {inputs['did_method']} DID")
            return
        segments = did.split(":")
        if len(segments) < 3 or not segments[2]:
            wrong("the DID carries no method-specific SCID segment")
            return
        expected = prefix + segments[2]
        if output != expected:
            wrong(f"project({did}) is {expected}")
        return

    if relation == "sha256_of_canonical_json":
        expected = "sha256:" + hashlib.sha256(
            canonical_json(inputs["object"]).encode("utf-8")
        ).hexdigest()
        if output != expected:
            wrong(f"recomputed {expected}")
        return

    if relation == "equal_json_value":
        if inputs["left"] != output:
            wrong(f"{inputs['left']!r} != {output!r}")
        return

    if relation == "ed25519_signature_over_prefixed_canonical_json":
        if Ed25519PublicKey is None:  # pragma: no cover - CI installs cryptography.
            return
        domain, body, key_did = inputs["domain"], inputs["canonical_json"], inputs["public_key_did"]
        if not all(isinstance(value, str) for value in (domain, body, key_did, output)):
            wrong("every endpoint of a signature relation MUST be a string")
            return
        if not key_did.startswith("did:key:z"):
            wrong(f"{key_did!r} is not a did:key multibase value")
            return
        try:
            multikey = base58btc_decode(key_did.removeprefix("did:key:z"))
        except ValueError as error:
            wrong(f"the did:key value does not decode: {error}")
            return
        if multikey[:2] != b"\xed\x01" or len(multikey) != 34:
            wrong(
                "the did:key value is not an Ed25519 multikey (0xed01 plus 32 octets); it decodes "
                f"to prefix {multikey[:2].hex()} and {len(multikey) - 2} key octets"
            )
            return
        try:
            signature = base64.urlsafe_b64decode(output + "=" * (-len(output) % 4))
        except (binascii.Error, ValueError):
            wrong("the signature is not unpadded base64url")
            return
        try:
            Ed25519PublicKey.from_public_bytes(multikey[2:]).verify(
                signature, (domain + "\n" + body).encode("utf-8")
            )
        except Exception:  # noqa: BLE001 - InvalidSignature plus malformed input
            wrong("the signature does not verify over UTF8(domain) || 0x0A || canonical bytes")
        return

    lint.fail(path, f"derived relation {relation} has no recomputation")  # pragma: no cover


def _json_leaf_paths(value: object, prefix: str = "") -> dict[str, object]:
    """Flatten a JSON value into dotted leaf paths, so two preimages can be
    diffed by path instead of by eyeball. Arrays index by position because a
    reordered array is a different canonical object."""
    if isinstance(value, dict):
        leaves: dict[str, object] = {}
        for key, member in value.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            leaves.update(_json_leaf_paths(member, child))
        return leaves
    if isinstance(value, list):
        leaves = {}
        for index, member in enumerate(value):
            leaves.update(_json_leaf_paths(member, f"{prefix}[{index}]"))
        return leaves
    return {prefix: value}


def _human_chain_preimage(
    lint: Lint, path: Path, case: dict, name: str
) -> dict | None:
    raw = case.get("digest_preimage_canonical_bytes_utf8")
    if not isinstance(raw, str):
        lint.fail(path, f"{name}: the human genesis chain requires canonical preimage bytes")
        return None
    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError:
        lint.fail(path, f"{name}: canonical preimage bytes are not JSON")
        return None
    if not isinstance(envelope, dict):
        lint.fail(path, f"{name}: canonical preimage must decode to an Event envelope")
        return None
    return envelope


def _check_human_pcr_genesis_chain(
    lint: Lint, path: Path, cases_by_name: dict
) -> None:
    """The human Principal Control Realm chain must be constructive.

    Before 0520 this case carried four label members -- principal_kind,
    realm_purpose, realm_id_source and retype_is_byte_identical -- and no bytes
    at all, so the gate above was checking what the case claimed rather than
    whether the claim holds. The relation gate recomputes every declared
    derivation; this function holds the case shape, so the bytes cannot be
    deleted while the labels survive.
    """
    step1_name = "principal_control_realm_id_is_event_derived_and_nonzero_nibble_rejected"
    step1 = cases_by_name.get(step1_name)
    if not isinstance(step1, dict):
        return

    # 1. Step 1 must be constructive, and its Realm token must be the Event
    #    token retyped. The generic KAT loop above recomputes the digest and the
    #    33-octet token; what it cannot see is a case that keeps the retype
    #    label while dropping the Realm token.
    for member in (
        "digest_preimage_canonical_bytes_utf8",
        "event_digest",
        "suite_wire_code",
        "event_id_bytes_hex",
        "derived_event_id",
        "derived_realm_id",
    ):
        if member not in step1:
            lint.fail(
                path,
                f"{step1_name}: the human PCR case asserts a byte-identical retype, "
                f"so it MUST carry {member}",
            )
    accepted_event = str(step1.get("derived_event_id", "")).removeprefix("ak:event:")
    accepted_realm = str(step1.get("derived_realm_id", "")).removeprefix("ak:realm:")
    if not accepted_event or accepted_event != accepted_realm:
        lint.fail(
            path,
            f"{step1_name}: derived_realm_id must be the derived_event_id token "
            "byte for byte",
        )

    step1_envelope = _human_chain_preimage(lint, path, step1, step1_name)

    # 2. The rejected token is a mutation of the accepted one, not an unrelated
    #    constant. Only the reserved high nibble may move.
    rejected = step1.get("rejected_form", {})
    rejected_realm = str(rejected.get("realm_id", "")).removeprefix("ak:realm:")
    if accepted_realm and rejected_realm:
        try:
            accepted_bytes = base64.urlsafe_b64decode(accepted_realm + "==")
            rejected_bytes = base64.urlsafe_b64decode(rejected_realm + "==")
        except ValueError:
            lint.fail(path, f"{step1_name}: rejected_form.realm_id is not a typed token")
        else:
            if (
                len(rejected_bytes) != 33
                or rejected_bytes[1:] != accepted_bytes[1:]
                or rejected_bytes[0] & 0x0F != accepted_bytes[0] & 0x0F
                or rejected_bytes[0] >> 4 == 0
            ):
                lint.fail(
                    path,
                    f"{step1_name}: the rejected Realm token must be the accepted token "
                    "with only the reserved high nibble changed to a non-zero value",
                )
            if rejected.get("expected_error") != "realm_id_not_event_derived":
                lint.fail(
                    path,
                    f"{step1_name}: a non-zero reserved nibble MUST be rejected as "
                    "realm_id_not_event_derived",
                )

    # 3. One DID on two Stations is two Realms. The claim is only worth
    #    anything if the second preimage really differs from the first in
    #    exactly the paths it names.
    second_name = "human_pcr_genesis_on_a_second_station_derives_a_distinct_realm_id"
    second = cases_by_name.get(second_name)
    if isinstance(second, dict):
        differs = second.get("differs_from", {})
        if differs.get("case") != step1_name:
            lint.fail(
                path,
                f"{second_name}: the distinct-Realm claim must name the step 1 case it "
                "differs from",
            )
        declared = differs.get("only_in")
        second_envelope = _human_chain_preimage(lint, path, second, second_name)
        if (
            isinstance(step1_envelope, dict)
            and isinstance(second_envelope, dict)
            and isinstance(declared, list)
        ):
            left = _json_leaf_paths(step1_envelope)
            right = _json_leaf_paths(second_envelope)
            actual = {
                key
                for key in set(left) | set(right)
                if left.get(key, _RELATION_MISSING) != right.get(key, _RELATION_MISSING)
            }
            if actual != set(declared):
                lint.fail(
                    path,
                    f"{second_name}: the two genesis preimages differ in "
                    f"{sorted(actual)} but the case declares {sorted(declared)}",
                )
        if second.get("derived_realm_id") == step1.get("derived_realm_id"):
            lint.fail(
                path,
                f"{second_name}: a second Station MUST derive a different realm_id",
            )
        if second.get("expected", {}).get("realm_id_equals_step_1") is not False:
            lint.fail(
                path,
                f"{second_name}: the case must state that the derived Realm is not "
                "step 1's Realm",
            )

    # 4. Step 2 binds to the Realm step 1 derived, and the dependency runs one
    #    way: the create preimage MUST NOT name the authorize Event.
    authorize_name = "human_founding_device_authorize_binds_the_derived_realm"
    authorize = cases_by_name.get(authorize_name)
    if isinstance(authorize, dict):
        expected_realm = step1.get("derived_realm_id")
        if authorize.get("realm_id") != expected_realm or authorize.get(
            "scope_ref", {}
        ).get("realm_id") != expected_realm:
            lint.fail(
                path,
                f"{authorize_name}: the founding authorize Event must carry the Realm "
                "derived in step 1 in both its envelope and its scope_ref",
            )
        authorize_envelope = _human_chain_preimage(lint, path, authorize, authorize_name)
        if isinstance(authorize_envelope, dict) and isinstance(step1_envelope, dict):
            if authorize_envelope.get("actor_id") != step1_envelope.get("actor_id"):
                lint.fail(
                    path,
                    f"{authorize_name}: both Events of one genesis unit must carry the "
                    "same account ActorId",
                )
            authorize_id = authorize.get("derived_event_id")
            if isinstance(authorize_id, str) and authorize_id in json.dumps(
                step1_envelope, ensure_ascii=False
            ):
                lint.fail(
                    path,
                    f"{step1_name}: the create preimage commits to the sibling "
                    "authorize event_id, which has no fixed point",
                )
        if authorize.get("expected", {}).get("declares_any_sibling_event_id") is not False:
            lint.fail(
                path,
                f"{authorize_name}: the unit contract must state that neither Event "
                "declares a sibling event_id",
            )

    # 5. Account-dimension uniqueness is a state judgement. Giving this case
    #    bytes would invite the reading that the rejection follows from the
    #    digests, which under event-derived ids it never can.
    state_name = "same_account_second_genesis_rejected_by_station_account_uniqueness"
    state = cases_by_name.get(state_name)
    if isinstance(state, dict):
        for member in ("digest_preimage_canonical_bytes_utf8", "event_digest", "derived_event_id"):
            if member in state:
                lint.fail(
                    path,
                    f"{state_name}: account uniqueness is decided from Station state, "
                    f"so this case MUST NOT carry {member}",
                )
        if not isinstance(state.get("state_input"), dict):
            lint.fail(path, f"{state_name}: a state judgement requires an explicit state_input")
        if not isinstance(state.get("decided_by"), str):
            lint.fail(path, f"{state_name}: the case must name the rule that decides it")
        expected = state.get("expected", {})
        if (
            expected.get("outcome") != "rejected"
            or expected.get("writes") != 0
            or expected.get("decided_by_id_collision") is not False
        ):
            lint.fail(
                path,
                f"{state_name}: the expected outcome must be a zero-write rejection that "
                "is not decided by id collision",
            )
    if isinstance(step1, dict) and step1.get("expected", {}).get(
        "same_account_second_genesis"
    ) is not None:
        lint.fail(
            path,
            f"{step1_name}: the account-uniqueness judgement belongs to "
            f"{state_name}; it MUST NOT be inferred from this case's digests",
        )


def check_derived_relation_evidence(lint: Lint) -> None:
    """Every declared derivation is recomputed, and the required ones stay declared."""
    declared: set[tuple[str, str, str]] = set()
    for path in sorted((ARTIFACTS / "fixtures").glob("*.json")):
        data = load_json(lint, path)
        if not isinstance(data, dict) or "derived_relations" not in data:
            continue
        rows = data["derived_relations"]
        if not isinstance(rows, list) or not rows:
            lint.fail(path, "derived_relations MUST be a non-empty array when present")
            continue
        cases = {
            case["name"]: case
            for case in data.get("cases", [])
            if isinstance(case, dict) and isinstance(case.get("name"), str)
        }
        for row in rows:
            result = _check_one_derived_relation(lint, path, cases, row)
            if result is not None:
                declared.add((path.name, result[0], result[1]))
    for fixture, relation, output_key in REQUIRED_DERIVED_RELATIONS:
        if (fixture, relation, output_key) not in declared:
            lint.fail(
                ARTIFACTS / "fixtures" / fixture,
                f"required derived relation is not declared: {relation} -> {output_key}. "
                "Deleting a derivation declaration removes the only check that the asserted "
                "relation actually holds, so the declaration is mandatory.",
            )

def check_operation_selector_fixture(lint: Lint) -> None:
    """Single-candidate HTTP selectors are required and signature-covered."""
    bootstrap_path = (
        ARTIFACTS / "fixtures" / "service-protocol-version-bootstrap-fixture.json"
    )
    bootstrap = load_json(lint, bootstrap_path)
    if not isinstance(bootstrap, dict):
        return
    bootstrap_cases = {
        case.get("name"): case
        for case in bootstrap.get("cases", [])
        if isinstance(case, dict) and isinstance(case.get("name"), str)
    }
    supported = bootstrap_cases.get("describe_supported")
    if not isinstance(supported, dict) or (
        supported.get("carrier"),
        supported.get("arkret_operation"),
        supported.get("expected", {}).get("outcome"),
    ) != (
        "service_describe",
        "ak.server.read.describe.v1",
        "continue_typed_validation",
    ):
        lint.fail(
            bootstrap_path,
            "single-candidate service_describe success must carry its exact selector",
        )
    missing = bootstrap_cases.get("describe_operation_selector_missing")
    if not isinstance(missing, dict) or (
        "arkret_operation" in missing
        or missing.get("carrier") != "service_describe"
        or missing.get("expected", {}).get("outcome")
        != "operation_selector_required"
        or missing.get("expected", {}).get("body_parse_attempts") != 0
    ):
        lint.fail(
            bootstrap_path,
            "single-candidate service_describe without a selector must fail before body parsing",
        )

    signature_path = ARTIFACTS / "fixtures" / "final-conformance-closure-fixture.json"
    signature = load_json(lint, signature_path)
    if not isinstance(signature, dict):
        return
    applet_case = next(
        (
            case
            for case in signature.get("cases", [])
            if isinstance(case, dict)
            and case.get("vector_id")
            == "ak.vector.applet.transaction_delivery_authentication_record_digest.v1"
        ),
        None,
    )
    if not isinstance(applet_case, dict) or "arkret-operation" not in applet_case.get(
        "required_components", []
    ):
        lint.fail(
            signature_path,
            "signed applet transaction vector must require arkret-operation coverage",
        )
        return
    transactions = {
        transaction.get("name"): transaction
        for transaction in applet_case.get("transactions", [])
        if isinstance(transaction, dict)
        and isinstance(transaction.get("name"), str)
    }
    valid = transactions.get("valid_inbound")
    if not isinstance(valid, dict) or (
        valid.get("arkret_operation")
        != "ak.edge.applet.command.transaction.v1"
        or "arkret-operation" not in valid.get("covered_components", [])
        or valid.get("expected", {}).get("decision") != "accept"
    ):
        lint.fail(
            signature_path,
            "valid signed request must carry and cover the exact Arkret-Operation selector",
        )
    uncovered = transactions.get("operation_selector_not_covered")
    if not isinstance(uncovered, dict) or (
        uncovered.get("arkret_operation")
        != "ak.edge.applet.command.transaction.v1"
        or "arkret-operation" in uncovered.get("covered_components", [])
        or uncovered.get("expected", {}).get("reason") != "http_signature_invalid"
    ):
        lint.fail(
            signature_path,
            "signed request with an uncovered Arkret-Operation selector must fail closed",
        )


def check_fixture_runner_contract(lint: Lint) -> None:
    fixture_root = ARTIFACTS / "fixtures"
    runner_registry_path = ARTIFACTS / "registry" / "runner-kind-registry.json"
    runner_registry = load_json(lint, runner_registry_path)
    rows = runner_registry.get("runner_kinds", []) if isinstance(runner_registry, dict) else []
    allowed_kinds = {
        row.get("kind")
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("kind"), str)
    }
    if not allowed_kinds:
        lint.fail(runner_registry_path, "runner kind registry must declare a non-empty closed vocabulary")
        return
    if len(allowed_kinds) != len(rows):
        lint.fail(runner_registry_path, "runner kind registry contains duplicate or malformed kind entries")
    for row in rows:
        if not isinstance(row, dict):
            continue
        if not isinstance(row.get("execution_contract"), str) or not row["execution_contract"].strip():
            lint.fail(runner_registry_path, f"runner kind {row.get('kind')!r} lacks execution_contract")
        if row.get("owner") not in {"protocol", "in_tree_lint", "cotest", "in_tree_lint_and_cotest"}:
            lint.fail(runner_registry_path, f"runner kind {row.get('kind')!r} has invalid owner")
        if row.get("execution_status") != "contract_published":
            lint.fail(runner_registry_path, f"runner kind {row.get('kind')!r} must publish its execution contract")
    executable_registry_assertions = {
        "error_code_registry_coverage_fixture": {
            "unique_top_level_codes",
            "unique_reason_codes",
            "operation_errors_registered",
            "reason_references_registered",
            "layering_is_explicit",
        },
        "operation_registry_coverage_fixture": {
            "catalog_registry_bijection",
            "registry_openapi_endpoint_projection",
            "registry_binding_coverage",
            "schema_refs_resolve",
            "write_retry_contract",
            "read_retry_contract",
            "write_durable_effect_contract",
        },
        "event_kind_payload_coverage_fixture": {
            "catalog_registry_bijection",
            "payload_schema_ref_resolves",
            "wire_scope_matches_envelope",
            "unknown_durable_kind_fails_closed",
        },
    }
    # The table above is keyed by suite and the sweep below is keyed by file, so
    # an entry naming a suite nobody ships is unreachable rather than wrong:
    # c473e3c4 deleted event-kind-lattice-dispatch-fixture.json with the rest of
    # the pre-clean-break lattice and left its row here, asserting against a file
    # that had stopped existing. The row is gone and the two are reconciled after
    # the sweep so the next deletion is an error instead of a silent hole.
    declared_suites: set[str] = set()
    for path in sorted(fixture_root.glob("*.json")):
        data = load_json(lint, path)
        if not isinstance(data, dict):
            continue
        suite_name = data.get("suite")
        if isinstance(suite_name, str):
            declared_suites.add(suite_name)
        runner = data.get("runner")
        if not isinstance(runner, dict):
            lint.fail(path, "top-level runner must be an object with runner.kind")
            continue
        kind = runner.get("kind")
        if not isinstance(kind, str) or not kind:
            lint.fail(path, "top-level runner.kind must be a non-empty string")
            continue
        if kind not in allowed_kinds:
            lint.fail(path, f"runner.kind is not registered: {kind!r}")
            continue
        if kind == "named_suite":
            entrypoint = runner.get("entrypoint")
            if not isinstance(entrypoint, str) or not re.fullmatch(r"ak\.suite\.[a-z0-9_.-]+\.v1", entrypoint):
                lint.fail(path, "runner.kind=named_suite requires a tool-neutral ak.suite.*.v1 entrypoint")
        if kind == "registry_coverage":
            inputs = runner.get("inputs")
            if not isinstance(inputs, list) or not inputs:
                lint.fail(path, "runner.kind=registry_coverage requires non-empty inputs")
            else:
                for relative in inputs:
                    if not isinstance(relative, str) or not (ARTIFACTS / relative).is_file():
                        lint.fail(path, f"registry coverage input does not exist: {relative!r}")
            suite = data.get("suite")
            expected = executable_registry_assertions.get(suite)
            assertions = data.get("assertions")
            actual = {
                row.get("id") for row in assertions if isinstance(row, dict) and isinstance(row.get("id"), str)
            } if isinstance(assertions, list) else set()
            if expected is None or actual != expected:
                lint.fail(path, f"registry coverage assertions are not bound to the executable lint contract: {sorted(actual)}")
    unshipped = sorted(set(executable_registry_assertions) - declared_suites)
    if unshipped:
        lint.fail(
            fixture_root,
            "executable registry assertion contract names fixture suite(s) no file declares: "
            f"{unshipped}",
        )


def check_erasure_verification_contract(lint: Lint) -> None:
    """Verify hard-erasure structure, digest consistency, and proof boundary vectors."""
    fixture_path = ARTIFACTS / "fixtures" / "redaction-fixture.json"
    fixture = load_json(lint, fixture_path)
    if not isinstance(fixture, dict):
        return
    cases = fixture.get("cases")
    case_rows = cases if isinstance(cases, list) else []
    hard_erasure = next(
        (
            case
            for case in case_rows if isinstance(case, dict)
            if case.get("name") == "hard_erasure_receipt"
        ),
        None,
    )
    if not isinstance(hard_erasure, dict):
        lint.fail(fixture_path, "missing hard_erasure_receipt case")
        return

    receipt = hard_erasure.get("redaction_receipt")
    expected_projection = hard_erasure.get("expected_projection")
    if not isinstance(receipt, dict) or not isinstance(expected_projection, dict):
        lint.fail(fixture_path, "hard_erasure_receipt must contain receipt and expected_projection")
        return
    stub = receipt.get("retained_stub")
    stated_stub_digest = receipt.get("retained_stub_digest")
    if not isinstance(stub, dict) or not isinstance(stated_stub_digest, str):
        lint.fail(fixture_path, "hard-erasure receipt must contain retained_stub and its digest")
        return
    recomputed_stub_digest = "sha256:" + hashlib.sha256(
        canonical_json(stub).encode("utf-8")
    ).hexdigest()
    if stated_stub_digest != recomputed_stub_digest:
        lint.fail(
            fixture_path,
            "hard-erasure retained_stub_digest does not equal sha256(canonical_json(retained_stub))",
        )
    if expected_projection.get("retained_stub_digest") != stated_stub_digest:
        lint.fail(fixture_path, "hard-erasure projection must expose the bound retained_stub_digest")
    if expected_projection.get("original_preimage_verified") is not False:
        lint.fail(fixture_path, "hard-erasure positive vector must state original_preimage_verified=false")

    suite_registry_path = ARTIFACTS / "registry" / "digest-suite-registry.json"
    suite_registry = load_json(lint, suite_registry_path)
    active_suites = {
        row.get("wire_code"): row.get("canonical_id")
        for row in (suite_registry.get("suites", []) if isinstance(suite_registry, dict) else [])
        if isinstance(row, dict) and row.get("status") == "active"
    }
    kind_prefixes = {
        "principal": "did:",
        "realm": "ak:realm:",
        "event": "ak:event:",
        "blob": "ak:blob:",
        "device": "ak:device:",
        "account_private_state": "sha256:",
    }

    def verdict(vector: dict[str, Any]) -> str:
        subject = vector.get("subject")
        if not isinstance(subject, dict):
            return "schema_violation"
        kind = subject.get("kind")
        subject_ref = subject.get("subject_ref")
        expected_prefix = kind_prefixes.get(kind)
        if not isinstance(subject_ref, str) or expected_prefix is None or not subject_ref.startswith(expected_prefix):
            return "schema_violation"
        if kind != "event":
            return "accepted"
        suffix = subject_ref.removeprefix("ak:event:")
        if not re.fullmatch(r"[A-Za-z0-9_-]{44}", suffix):
            return "schema_violation"
        try:
            decoded = base64.urlsafe_b64decode(suffix + "==")
        except (ValueError, binascii.Error):
            return "schema_violation"
        if len(decoded) != 33 or base64.urlsafe_b64encode(decoded).decode("ascii").rstrip("=") != suffix:
            return "schema_violation"
        if decoded[0] >> 4 != 0:
            return "schema_violation"
        suite_id = active_suites.get(decoded[0] & 0x0F)
        if not isinstance(suite_id, str):
            return "unsupported_digest_algorithm"
        event_digest = vector.get("event_digest")
        if event_digest is not None and event_digest != f"{suite_id}:{decoded[1:].hex()}":
            return "event_id_digest_mismatch"
        if vector.get("retained_stub_digest") != recomputed_stub_digest:
            return "erasure_receipt_stub_digest_mismatch"
        return "accepted"

    vectors = hard_erasure.get("verification_cases")
    if not isinstance(vectors, list) or len(vectors) < 5:
        lint.fail(fixture_path, "hard-erasure verification_cases must cover at least five cases")
        return
    required = {
        "structure_digest_and_stub_binding_valid",
        "wrong_kind_ref_namespace_rejected",
        "invalid_event_id_suite_rejected",
        "event_id_digest_mismatch_rejected",
        "stub_digest_mismatch_rejected",
    }
    names = {vector.get("name") for vector in vectors if isinstance(vector, dict)}
    if names != required:
        lint.fail(fixture_path, f"hard-erasure verification case names drifted: {sorted(names)}")
    for vector in vectors:
        if not isinstance(vector, dict):
            lint.fail(fixture_path, "hard-erasure verification case must be an object")
            continue
        if verdict(vector) != vector.get("expected"):
            lint.fail(
                fixture_path,
                f"hard-erasure case {vector.get('name')!r} expected {vector.get('expected')!r} "
                f"but evaluates to {verdict(vector)!r}",
            )
        if vector.get("expected") == "accepted" and vector.get("original_preimage_verified") is not False:
            lint.fail(fixture_path, "accepted hard-erasure vector must deny original preimage verification")

    receipt_schema_path = ARTIFACTS / "schemas" / "erasure-receipt.schema.json"
    receipt_schema = load_json(lint, receipt_schema_path)
    if isinstance(receipt_schema, dict):
        defs = receipt_schema.get("$defs", {})
        retained_stub = receipt_schema.get("properties", {}).get("retained_stub", {})
        if isinstance(defs, dict) and "verification_stub" in defs:
            lint.fail(receipt_schema_path, "receipt schema must not copy the verification stub definition")
        if not isinstance(retained_stub, dict) or retained_stub.get("$ref") != "./erasure-verification-stub.schema.json":
            lint.fail(receipt_schema_path, "retained_stub must reference the standalone schema truth source")


def check_producer_allocated_identity_vectors(lint: Lint) -> None:
    """Require the registry-driven five-case collision suite for every producer ID kind."""
    registry_path = ARTIFACTS / "registry" / "id-kind-registry.json"
    fixture_path = ARTIFACTS / "fixtures" / "producer-allocated-identity-fixture.json"
    registry = load_json(lint, registry_path)
    fixture = load_json(lint, fixture_path)
    if not isinstance(registry, dict) or not isinstance(fixture, dict):
        return
    expected_kinds = sorted(
        row["kind"]
        for row in registry.get("id_kinds", [])
        if isinstance(row, dict)
        and row.get("id_form") == "producer_allocated"
        and row.get("identity_authority") == "producer_signature"
        and isinstance(row.get("kind"), str)
    )
    driver = fixture.get("driver")
    if not isinstance(driver, dict):
        lint.fail(fixture_path, "producer identity fixture missing registry driver")
        return
    if driver.get("selected_id_kinds") != expected_kinds:
        lint.fail(fixture_path, "producer identity fixture selected_id_kinds drifted from registry")
    if driver.get("registry_ref") != "registry/id-kind-registry.json#/id_kinds":
        lint.fail(fixture_path, "producer identity fixture must consume the generated ID registry")
    expected_cases = {
        "authorized_first_reservation_accepted": "accepted",
        "same_authority_exact_replay_idempotent": "idempotent",
        "same_authority_conflicting_binding_quarantined": "reject_and_quarantine",
        "cross_authority_same_uuid_distinct": "distinct_identity",
        "bare_lookup_or_unauthorized_allocator_rejected": "rejected",
    }
    cases = fixture.get("cases")
    case_rows = cases if isinstance(cases, list) else []
    actual_cases = {
        case.get("name"): case.get("expected")
        for case in case_rows if isinstance(case, dict)
    }
    if actual_cases != expected_cases:
        lint.fail(fixture_path, "producer identity fixture must contain the closed five-case matrix")


def check_applet_revoke_saga_contract(lint: Lint) -> None:
    """Pin the executable revoke saga matrix to its schema and operation contract."""
    fixture_path = ARTIFACTS / "fixtures" / "applet-revoke-saga-fixture.json"
    operation_path = ARTIFACTS / "registry" / "operation-registry.json"
    schema_path = ARTIFACTS / "schemas" / "applet-install-operations.schema.json"
    fixture = load_json(lint, fixture_path)
    operations = load_json(lint, operation_path)
    schema = load_json(lint, schema_path)
    if not all(isinstance(value, dict) for value in (fixture, operations, schema)):
        return

    runner = fixture.get("runner", {})
    if runner != {
        "kind": "named_suite",
        "entrypoint": "ak.suite.applet.revoke_saga.v1",
    }:
        lint.fail(fixture_path, "revoke saga fixture must expose the canonical named suite")
    if fixture.get("covers_vectors") != ["ak.vector.applet.revoke_saga.v1"]:
        lint.fail(fixture_path, "revoke saga fixture must cover exactly its registered vector")

    required_invariants = {
        "persist_ledger_before_first_effect",
        "ledger_binds_principal_service_and_admin_actor",
        "exact_replay_resumes_same_ledger",
        "conflicting_replay_has_no_effect",
        "accepted_or_duplicate_steps_are_never_reexecuted",
        "rejected_step_cannot_be_skipped",
        "first_accepted_revoke_event_fences_future_applet_writes",
        "complete_requires_every_planned_step_terminal_success",
    }
    if set(fixture.get("invariants", [])) != required_invariants:
        lint.fail(fixture_path, "revoke saga fixture invariants are incomplete or drifted")

    plan = fixture.get("plan", {})
    steps = plan.get("steps", []) if isinstance(plan, dict) else []
    step_ids = {
        step.get("step_id")
        for step in steps
        if isinstance(step, dict) and isinstance(step.get("step_id"), str)
    }
    if len(step_ids) != len(steps) or not {
        "capability:0",
        "membership:0",
        "delegated_session:0",
        "widget_token:0",
    }.issubset(step_ids):
        lint.fail(fixture_path, "revoke saga plan must contain unique Event, external, and local steps")

    cases = fixture.get("cases", [])
    case_by_name = {
        case.get("name"): case
        for case in cases
        if isinstance(case, dict) and isinstance(case.get("name"), str)
    }
    required_cases = {
        "complete_exact_plan",
        "event_rejected_without_skip",
        "crash_after_first_acceptance_then_exact_restart",
        "same_key_different_body_conflicts",
        "same_key_different_actor_or_service_conflicts",
        "external_effect_partial_then_restart",
        "plan_or_submission_mismatch_is_pre_effect",
    }
    if set(case_by_name) != required_cases:
        lint.fail(fixture_path, "revoke saga fixture must contain the closed seven-case matrix")
        return

    effect_prefixes = ("accepted:", "duplicate:", "rejected:")
    for name, case in case_by_name.items():
        for field in ("timeline", "first_attempt", "restart_timeline"):
            timeline = case.get(field)
            if not isinstance(timeline, list):
                continue
            effect_indexes = [
                index
                for index, action in enumerate(timeline)
                if isinstance(action, str) and action.startswith(effect_prefixes)
            ]
            if field != "restart_timeline" and effect_indexes:
                persist_index = timeline.index("persist_ledger") if "persist_ledger" in timeline else -1
                if persist_index < 0 or persist_index > effect_indexes[0]:
                    lint.fail(fixture_path, f"{name}.{field} performs an effect before ledger persistence")
            for action in timeline:
                if not isinstance(action, str) or not action.startswith(effect_prefixes):
                    continue
                step_id = action.split(":", 1)[1]
                if step_id not in step_ids:
                    lint.fail(fixture_path, f"{name}.{field} references unknown saga step {step_id!r}")

    complete = case_by_name["complete_exact_plan"]["timeline"]
    first_event = complete.index("accepted:capability:0")
    if complete[first_event + 1] != "fence_applet_writes":
        lint.fail(fixture_path, "first accepted revoke Event must immediately fence Applet writes")
    rejected = case_by_name["event_rejected_without_skip"]
    if rejected.get("expected_pending_steps") != [
        "membership:0",
        "delegated_session:0",
        "widget_token:0",
    ]:
        lint.fail(fixture_path, "a rejected Event must preserve every later step as pending")
    restart = case_by_name["crash_after_first_acceptance_then_exact_restart"]
    if restart.get("request_binding") != restart.get("restart_request_binding"):
        lint.fail(fixture_path, "restart case must replay the exact request binding")
    if "accepted:capability:0" in restart.get("restart_timeline", []):
        lint.fail(fixture_path, "restart must not re-execute an already accepted Event")
    conflict = case_by_name["same_key_different_body_conflicts"]
    if (
        conflict.get("request_binding") == conflict.get("replay_request_binding")
        or conflict.get("expected_new_effect_count") != 0
    ):
        lint.fail(fixture_path, "conflicting idempotency replay must have zero new effects")
    principal_conflict = case_by_name["same_key_different_actor_or_service_conflicts"]
    if (
        len(principal_conflict.get("replay_request_bindings", [])) != 2
        or principal_conflict.get("expected_new_effect_count") != 0
    ):
        lint.fail(fixture_path, "revoke ledger must bind both principal service and admin actor")
    mismatch = case_by_name["plan_or_submission_mismatch_is_pre_effect"]
    if mismatch.get("timeline") != ["reject_plan_or_submission_mismatch"]:
        lint.fail(fixture_path, "plan/submission mismatch must fail before ledger or effects")

    rows = operations.get("operations", [])
    revoke = next(
        (
            row
            for row in rows
            if isinstance(row, dict)
            and row.get("operation_id") == "ak.self.applet.command.revoke.v1"
        ),
        {},
    )
    saga = revoke.get("saga_contract", {}) if isinstance(revoke, dict) else {}
    if (
        saga.get("ledger") != "durable_before_first_effect"
        or saga.get("restart_recovery")
        != "resume_exact_persisted_submissions_and_pending_steps"
        or saga.get("first_revoke_acceptance_fences_future_writes") is not True
    ):
        lint.fail(operation_path, "Applet revoke operation saga contract drifted from its vector")

    defs = schema.get("$defs", {})
    request = defs.get("applet_revoke_request_body", {}) if isinstance(defs, dict) else {}
    required = set(request.get("required", [])) if isinstance(request, dict) else set()
    carrier_fields = {
        "effective_scope",
        "reason_code",
        "revoke_mode",
        "revoke_plan_digest",
        "capability_revoke_events",
        "membership_state_events",
    }
    if not carrier_fields.issubset(required):
        lint.fail(schema_path, "Applet revoke commit schema is missing its exact signed carrier")

    preview = defs.get("applet_revoke_preview_outcome", {}) if isinstance(defs, dict) else {}
    preview_properties = preview.get("properties", {}) if isinstance(preview, dict) else {}
    preview_required = preview.get("required", []) if isinstance(preview, dict) else []
    if "revoke_plan_digest" in preview_properties or "revoke_plan_digest" in preview_required:
        lint.fail(
            schema_path,
            "applet_revoke_preview_outcome.revoke_plan_digest must be derived by the caller from "
            "revoke_plan (SHA-256 over RFC 8785 JCS) and must not return to the preview wire",
        )
    if "revoke_plan" not in preview_required:
        lint.fail(schema_path, "applet_revoke_preview_outcome must require the canonical revoke_plan")

    kat = fixture.get("preview_plan_digest_kat")
    plan_ref = "schemas/applet-install-operations.schema.json#/$defs/applet_revoke_plan"
    if not isinstance(kat, dict):
        lint.fail(fixture_path, "preview_plan_digest_kat must pin the caller-side revoke_plan_digest recomputation")
    else:
        if kat.get("schema_ref") != plan_ref:
            lint.fail(fixture_path, f"preview_plan_digest_kat.schema_ref must be {plan_ref}")
        revoke_plan = kat.get("revoke_plan")
        if not isinstance(revoke_plan, dict):
            lint.fail(fixture_path, "preview_plan_digest_kat.revoke_plan must be an object")
        else:
            check_json_instance_against_schema(
                lint, fixture_path, "preview_plan_digest_kat.revoke_plan", plan_ref, revoke_plan
            )
            jcs = canonical_json(revoke_plan)
            if kat.get("revoke_plan_jcs") != jcs:
                lint.fail(fixture_path, "preview_plan_digest_kat.revoke_plan_jcs must equal RFC 8785 JCS of revoke_plan")
            expected = "sha256:" + hashlib.sha256(jcs.encode("utf-8")).hexdigest()
            if kat.get("expected_revoke_plan_digest") != expected:
                lint.fail(
                    fixture_path,
                    "preview_plan_digest_kat.expected_revoke_plan_digest must equal SHA-256 over the JCS bytes of revoke_plan",
                )


def check_normative_clause_registry(lint: Lint) -> None:
    """Reverse coverage: every registered normative clause must have live evidence.

    vector-registry.json proves each vector has a consumer. This registry proves
    the other direction for the high-risk obligation set: each registered clause
    points at an existing prose section, that section's text has not drifted
    since the clause was reviewed, and the clause names evidence that actually
    exists (an active vector, or an explicit non-vector test plan).
    """
    path = ARTIFACTS / "registry" / "normative-clause-registry.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return

    if data.get("source_of_truth") is not True:
        lint.fail(path, "source_of_truth must be true")

    coverage_scope = data.get("coverage_scope")
    if not isinstance(coverage_scope, dict):
        lint.fail(path, "coverage_scope must be an object")
        return
    categories = coverage_scope.get("included_categories")
    if not isinstance(categories, list) or not categories:
        lint.fail(path, "coverage_scope.included_categories must be a non-empty array")
        return
    included_categories = set(categories)
    for field in ("rule", "extension_rule"):
        if not isinstance(coverage_scope.get(field), str) or not coverage_scope[field].strip():
            lint.fail(path, f"coverage_scope.{field} must be a non-empty string")

    vector_data = load_json(lint, ARTIFACTS / "registry" / "vector-registry.json")
    active_vectors = {
        row.get("vector_id")
        for row in (vector_data.get("vectors", []) if isinstance(vector_data, dict) else [])
        if isinstance(row, dict) and row.get("status") == "active"
    }

    rows = data.get("clauses")
    if not isinstance(rows, list) or not rows:
        lint.fail(path, "clauses must be a non-empty list")
        return

    clause_id_re = re.compile(r"^AK-NC-\d{3}$")
    allowed_status = {"active", "deprecated"}
    allowed_grades = {"vector", "api_shape", "audit"}
    seen: set[str] = set()
    covered_categories: set[str] = set()
    for index, row in enumerate(rows):
        label = f"clauses[{index}]"
        if not isinstance(row, dict):
            lint.fail(path, f"{label} must be an object")
            continue

        clause_id = row.get("clause_id")
        if not isinstance(clause_id, str) or not clause_id_re.fullmatch(clause_id):
            lint.fail(path, f"{label}.clause_id must match AK-NC-###")
            continue
        if clause_id in seen:
            lint.fail(path, f"{label}.clause_id duplicates {clause_id}")
        seen.add(clause_id)

        status = row.get("status")
        if status not in allowed_status:
            lint.fail(path, f"{clause_id}.status must be one of {sorted(allowed_status)}")
        category = row.get("category")
        if category not in included_categories:
            lint.fail(path, f"{clause_id}.category {category!r} is outside coverage_scope.included_categories")
        elif status == "active":
            covered_categories.add(category)
        if not isinstance(row.get("requirement"), str) or not row["requirement"].strip():
            lint.fail(path, f"{clause_id}.requirement must be a non-empty string")

        source_anchor = row.get("source_anchor")
        if not isinstance(source_anchor, str) or "#" not in source_anchor:
            lint.fail(path, f"{clause_id}.source_anchor must be <repo-relative markdown path>#<heading slug>")
            continue
        rel, _, anchor = source_anchor.partition("#")
        source_path = Path(rel)
        if source_path.is_absolute() or ".." in source_path.parts:
            lint.fail(path, f"{clause_id}.source_anchor escapes repository: {source_anchor}")
            continue
        resolved = (ROOT / source_path).resolve()
        try:
            resolved.relative_to(ROOT.resolve())
        except ValueError:
            lint.fail(path, f"{clause_id}.source_anchor escapes repository: {source_anchor}")
            continue
        if not resolved.is_file():
            lint.fail(path, f"{clause_id}.source_anchor target does not exist: {rel}")
            continue
        digest = markdown_section_digest(read_text(resolved), anchor)
        if digest is None:
            lint.fail(path, f"{clause_id}.source_anchor heading does not exist: {source_anchor}")
            continue
        if row.get("section_digest") != digest:
            lint.fail(
                path,
                f"{clause_id}.section_digest is stale for {source_anchor}: the normative text changed, so the clause "
                f"and its evidence must be re-reviewed and the digest updated to {digest}",
            )

        grade = row.get("testability_grade")
        if grade not in allowed_grades:
            lint.fail(path, f"{clause_id}.testability_grade must be one of {sorted(allowed_grades)}")
            continue
        if grade == "vector":
            evidence = row.get("evidence_refs")
            if not isinstance(evidence, list) or not evidence:
                lint.fail(path, f"{clause_id}.evidence_refs must be a non-empty array for testability_grade=vector")
                continue
            if "test_plan" in row:
                lint.fail(path, f"{clause_id} must not declare both evidence_refs and test_plan")
            for vector_id in evidence:
                if vector_id not in active_vectors:
                    lint.fail(path, f"{clause_id}.evidence_refs references a non-active vector: {vector_id!r}")
        else:
            if "evidence_refs" in row:
                lint.fail(path, f"{clause_id} must declare test_plan instead of evidence_refs for grade {grade}")
            if not isinstance(row.get("test_plan"), str) or not row["test_plan"].strip():
                lint.fail(path, f"{clause_id}.test_plan must be a non-empty string for testability_grade={grade}")

    missing = included_categories - covered_categories
    if missing:
        lint.fail(path, f"coverage_scope.included_categories has no active clause: {sorted(missing)}")


def check_vector_registry(lint: Lint) -> None:
    path = ARTIFACTS / "registry" / "vector-registry.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return

    if data.get("source_of_truth") is not True:
        lint.fail(path, "source_of_truth must be true")

    profiles_path = ARTIFACTS / "profiles" / "conformance-profiles.json"
    profiles_data = load_json(lint, profiles_path)
    if not isinstance(profiles_data, dict):
        return
    known_profiles = set(PROFILE_ID_TOKEN_RE.findall(json.dumps(profiles_data, ensure_ascii=False)))
    known_vector_groups = set(profiles_data.get("vector_groups") or [])
    known_fixtures = {fixture.name for fixture in (ARTIFACTS / "fixtures").glob("*.json")}

    rows = data.get("vectors")
    if not isinstance(rows, list) or not rows:
        lint.fail(path, "vectors must be a non-empty list")
        return

    registered: dict[str, dict[str, Any]] = {}
    source_vector_ids: dict[Path, set[str]] = {}
    for index, row in enumerate(rows):
        label = f"vectors[{index}]"
        if not isinstance(row, dict):
            lint.fail(path, f"{label} must be an object")
            continue

        vector_id = row.get("vector_id")
        if not isinstance(vector_id, str) or not VECTOR_ID_TOKEN_RE.fullmatch(vector_id):
            lint.fail(path, f"{label}.vector_id must be a ak.vector.*.vN identifier")
            continue
        if vector_id in registered:
            lint.fail(path, f"{label}.vector_id duplicates {vector_id}")
        registered[vector_id] = row

        if row.get("status") not in {"active", "reserved", "deprecated"}:
            lint.fail(path, f"{label}.status must be active, reserved, or deprecated")

        expected_domain = vector_id.removeprefix("ak.vector.").rsplit(".v", 1)[0].split(".", 1)[0]
        if row.get("domain") != expected_domain:
            lint.fail(path, f"{label}.domain must match vector id domain {expected_domain!r}")

        if "profile" in row:
            lint.fail(path, f"{label}.profile is ambiguous; use one explicit applicability selector")
        selector_keys = [
            key
            for key in ("scope", "applies_to_profiles", "applies_to_vector_groups", "applies_to_fixtures")
            if key in row
        ]
        if len(selector_keys) != 1:
            lint.fail(path, f"{label} must declare exactly one applicability selector")
        elif selector_keys[0] == "scope":
            if row.get("scope") != "universal":
                lint.fail(path, f"{label}.scope must be 'universal'")
        else:
            selector = selector_keys[0]
            values = row.get(selector)
            if not isinstance(values, list) or not values or any(not isinstance(value, str) for value in values):
                lint.fail(path, f"{label}.{selector} must be a non-empty string array")
            elif len(values) != len(set(values)):
                lint.fail(path, f"{label}.{selector} must not contain duplicates")
            elif selector == "applies_to_profiles":
                for profile_id in values:
                    if profile_id not in known_profiles:
                        lint.fail(path, f"{label}.{selector} references unknown profile: {profile_id}")
            elif selector == "applies_to_vector_groups":
                for group_id in values:
                    if group_id not in known_vector_groups:
                        lint.fail(path, f"{label}.{selector} references unknown vector group: {group_id}")
            elif selector == "applies_to_fixtures":
                for fixture in values:
                    if fixture not in known_fixtures:
                        lint.fail(path, f"{label}.{selector} references missing fixture: {fixture}")

        source_refs = row.get("source_refs")
        if not isinstance(source_refs, list) or not source_refs:
            lint.fail(path, f"{label}.source_refs must be a non-empty array")
            continue
        for source_index, source_ref in enumerate(source_refs):
            source_label = f"{label}.source_refs[{source_index}]"
            if not isinstance(source_ref, str) or not source_ref:
                lint.fail(path, f"{source_label} must be a non-empty string")
                continue
            source_path = Path(source_ref)
            if source_path.is_absolute() or ".." in source_path.parts:
                lint.fail(path, f"{source_label} escapes repository: {source_ref}")
                continue
            resolved = (ROOT / source_path).resolve()
            try:
                resolved.relative_to(ROOT.resolve())
            except ValueError:
                lint.fail(path, f"{source_label} escapes repository: {source_ref}")
                continue
            if not resolved.is_file():
                lint.fail(path, f"{source_label} target does not exist: {source_ref}")
                continue
            try:
                referenced_ids = source_vector_ids.get(resolved)
                if referenced_ids is None:
                    referenced_ids = set(VECTOR_ID_TOKEN_RE.findall(read_text(resolved)))
                    source_vector_ids[resolved] = referenced_ids
            except Exception as exc:
                lint.fail(path, f"{source_label} target cannot be read: {source_ref}: {exc}")
                continue
            if vector_id not in referenced_ids:
                lint.fail(path, f"{source_label} does not contain vector_id {vector_id}")

        for fixture in row.get("applies_to_fixtures", []):
            expected_ref = f"spec/v1/artifacts/fixtures/{fixture}"
            if expected_ref not in source_refs:
                lint.fail(path, f"{label}.applies_to_fixtures entry lacks matching source_ref: {fixture}")

    for scan_path in markdown_files() + raw_artifact_files():
        try:
            text = read_text(scan_path.resolve())
        except Exception:
            continue
        for vector_id in sorted(set(VECTOR_ID_TOKEN_RE.findall(text))):
            if vector_id not in registered:
                lint.fail(scan_path, f"references unregistered conformance vector id: {vector_id}")

    indexed_fixtures: set[str] = set()
    for row in registered.values():
        if row.get("status") != "active":
            continue
        indexed_fixtures.update(
            fixture
            for fixture in row.get("applies_to_fixtures", [])
            if isinstance(fixture, str)
        )
        for source_ref in row.get("source_refs", []):
            if not isinstance(source_ref, str):
                continue
            prefix = "spec/v1/artifacts/fixtures/"
            if source_ref.startswith(prefix) and source_ref.endswith(".json"):
                indexed_fixtures.add(source_ref.removeprefix(prefix))

    for fixture_path in sorted((ARTIFACTS / "fixtures").glob("*.json")):
        fixture = load_json(lint, fixture_path)
        if not isinstance(fixture, dict):
            continue
        vectors = fixture.get("vectors")
        if isinstance(vectors, list):
            seen_fixture_vector_ids: set[str] = set()
            for index, vector in enumerate(vectors):
                if not isinstance(vector, dict):
                    continue
                vector_id = vector.get("vector_id")
                if vector_id is None:
                    continue
                if not isinstance(vector_id, str) or not VECTOR_ID_TOKEN_RE.fullmatch(vector_id):
                    lint.fail(
                        fixture_path,
                        f"vectors[{index}].vector_id must be a conformance vector id",
                    )
                    continue
                if vector_id in seen_fixture_vector_ids:
                    lint.fail(
                        fixture_path,
                        f"vectors[{index}].vector_id duplicates {vector_id} within the fixture",
                    )
                seen_fixture_vector_ids.add(vector_id)
        runner = fixture.get("runner")
        if (
            isinstance(runner, dict)
            and runner.get("kind") == "named_suite"
            and fixture_path.name not in indexed_fixtures
        ):
            lint.fail(
                fixture_path,
                "runner.kind=named_suite fixture must be indexed by an active vector through "
                "applies_to_fixtures[] or source_refs[]",
            )


def check_cryptographic_suite_kat_bindings(lint: Lint) -> None:
    vector_path = ARTIFACTS / "registry" / "vector-registry.json"
    vector_registry = load_json(lint, vector_path)
    if not isinstance(vector_registry, dict):
        return
    active_vectors = {
        row.get("vector_id")
        for row in vector_registry.get("vectors", [])
        if isinstance(row, dict)
        and row.get("status") == "active"
        and isinstance(row.get("vector_id"), str)
    }
    registries = {
        "signature-alg-registry.json": "algorithms",
        "digest-suite-registry.json": "suites",
        "hpke-suite-registry.json": "suites",
        "mls-ciphersuite-registry.json": "ciphersuites",
    }
    for filename, rows_key in registries.items():
        path = ARTIFACTS / "registry" / filename
        data = load_json(lint, path)
        if not isinstance(data, dict):
            continue
        rows = data.get(rows_key)
        if not isinstance(rows, list):
            lint.fail(path, f"{rows_key} must be an array")
            continue
        for index, row in enumerate(rows):
            label = f"{rows_key}[{index}]"
            if not isinstance(row, dict):
                lint.fail(path, f"{label} must be an object")
                continue
            status = row.get("status")
            kat_vector_id = row.get("kat_vector_id")
            absence_reason = row.get("kat_absence_reason")
            if status == "active":
                if not isinstance(kat_vector_id, str) or not kat_vector_id:
                    lint.fail(path, f"{label} status=active requires kat_vector_id")
                elif kat_vector_id not in active_vectors:
                    lint.fail(path, f"{label}.kat_vector_id is not an active vector: {kat_vector_id!r}")
                if absence_reason is not None:
                    lint.fail(path, f"{label} status=active MUST NOT declare kat_absence_reason")
            elif status == "reserved":
                if kat_vector_id is not None:
                    lint.fail(path, f"{label} status=reserved MUST NOT declare kat_vector_id")
                if not isinstance(absence_reason, str) or not absence_reason.strip():
                    lint.fail(path, f"{label} status=reserved requires kat_absence_reason")


def check_account_data_key_registry(lint: Lint, known: dict[str, set[str]]) -> None:
    path = ARTIFACTS / "registry" / "account-data-key-registry.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return

    if data.get("source_of_truth") is not True:
        lint.fail(path, "source_of_truth must be true")

    rows = data.get("account_data_key_patterns")
    if not isinstance(rows, list) or not rows:
        lint.fail(path, "account_data_key_patterns must be a non-empty list")
        return

    seen: set[str] = set()
    allowed_status = {"active", "reserved", "deprecated"}
    allowed_storage = {"encrypted_account_data", "local_only", "encrypted_account_data_or_local", "plaintext_account_data"}
    allowed_deletion_modes = {"physical_delete", "value_tombstone"}
    allowed_writer_authorities = {"holder_event", "station_cas"}
    allowed_holder_self_operations = {"put", "delete"}
    for index, row in enumerate(rows):
        label = f"account_data_key_patterns[{index}]"
        if not isinstance(row, dict):
            lint.fail(path, f"{label} must be an object")
            continue

        key_pattern = row.get("key_pattern")
        if not isinstance(key_pattern, str) or not key_pattern.startswith("ak."):
            lint.fail(path, f"{label}.key_pattern must be a ak.* key pattern")
            continue
        if key_pattern in seen:
            lint.fail(path, f"{label}.key_pattern duplicates {key_pattern}")
        seen.add(key_pattern)

        if row.get("status") not in allowed_status:
            lint.fail(path, f"{label}.status must be one of {sorted(allowed_status)}")
        if row.get("storage") not in allowed_storage:
            lint.fail(path, f"{label}.storage must be one of {sorted(allowed_storage)}")
        if row.get("deletion_mode") not in allowed_deletion_modes:
            lint.fail(path, f"{label}.deletion_mode must be one of {sorted(allowed_deletion_modes)}")
        if not isinstance(row.get("scope"), str) or not row["scope"]:
            lint.fail(path, f"{label}.scope must be a non-empty string")
        if not isinstance(row.get("description"), str) or not row["description"].strip():
            lint.fail(path, f"{label}.description must be a non-empty string")

        writer_authorities = row.get("writer_authorities")
        if (
            not isinstance(writer_authorities, list)
            or not writer_authorities
            or any(not isinstance(authority, str) for authority in writer_authorities)
            or len(writer_authorities) != len(set(writer_authorities))
            or any(authority not in allowed_writer_authorities for authority in writer_authorities)
        ):
            lint.fail(
                path,
                f"{label}.writer_authorities must be a non-empty unique array over "
                f"{sorted(allowed_writer_authorities)}",
            )
            writer_authorities = []

        holder_self_operations = row.get("holder_self_operations")
        if (
            not isinstance(holder_self_operations, list)
            or any(not isinstance(operation, str) for operation in holder_self_operations)
            or len(holder_self_operations) != len(set(holder_self_operations))
            or any(operation not in allowed_holder_self_operations for operation in holder_self_operations)
        ):
            lint.fail(
                path,
                f"{label}.holder_self_operations must be a unique array over "
                f"{sorted(allowed_holder_self_operations)}",
            )
            holder_self_operations = []

        write_event_kinds = row.get("write_event_kinds")
        if not isinstance(write_event_kinds, list):
            lint.fail(path, f"{label}.write_event_kinds must be an array")
            write_event_kinds = []
        else:
            for event_kind in write_event_kinds:
                if not isinstance(event_kind, str) or event_kind not in known["event_kinds"]:
                    lint.fail(path, f"{label}.write_event_kinds contains unknown Event.kind: {event_kind!r}")

        if "holder_event" in writer_authorities and not write_event_kinds:
            lint.fail(path, f"{label} holder_event requires non-empty write_event_kinds")
        if "holder_event" not in writer_authorities and write_event_kinds:
            lint.fail(path, f"{label} write_event_kinds requires holder_event authority")
        if holder_self_operations and "holder_event" not in writer_authorities:
            lint.fail(path, f"{label} holder self operations require holder_event authority")
        if "put" in holder_self_operations and "ak.account_data.set" not in write_event_kinds:
            lint.fail(path, f"{label} holder self put requires ak.account_data.set")
        if "delete" in holder_self_operations and row.get("deletion_mode") != "physical_delete":
            lint.fail(path, f"{label} holder self delete requires deletion_mode=physical_delete")
        if "station_cas" in writer_authorities:
            if row.get("storage") != "plaintext_account_data":
                lint.fail(path, f"{label} station_cas requires plaintext_account_data")
            if not isinstance(row.get("plaintext_schema"), str) or not row["plaintext_schema"]:
                lint.fail(path, f"{label} station_cas requires plaintext_schema")

        encrypted_value_schema = row.get("encrypted_value_schema")
        if encrypted_value_schema is not None:
            if row.get("storage") not in {"encrypted_account_data", "encrypted_account_data_or_local"}:
                lint.fail(path, f"{label}.encrypted_value_schema requires encrypted storage")
            if not isinstance(encrypted_value_schema, str) or not encrypted_value_schema.startswith("schemas/"):
                lint.fail(path, f"{label}.encrypted_value_schema must name an artifacts schemas/ file")
            elif not (ARTIFACTS / encrypted_value_schema).is_file():
                lint.fail(path, f"{label}.encrypted_value_schema does not exist: {encrypted_value_schema}")

        source_refs = row.get("source_refs")
        if not isinstance(source_refs, list) or not source_refs:
            lint.fail(path, f"{label}.source_refs must be a non-empty array")
            continue

        mentions_key = False
        for source_index, source_ref in enumerate(source_refs):
            source_label = f"{label}.source_refs[{source_index}]"
            if not isinstance(source_ref, str) or not source_ref:
                lint.fail(path, f"{source_label} must be a non-empty string")
                continue
            source_path = Path(source_ref)
            if source_path.is_absolute() or ".." in source_path.parts:
                lint.fail(path, f"{source_label} escapes repository: {source_ref}")
                continue
            resolved = (ROOT / source_path).resolve()
            try:
                resolved.relative_to(ROOT.resolve())
            except ValueError:
                lint.fail(path, f"{source_label} escapes repository: {source_ref}")
                continue
            if not resolved.is_file():
                lint.fail(path, f"{source_label} target does not exist: {source_ref}")
                continue
            try:
                source_text = resolved.read_text(encoding="utf-8")
            except Exception as exc:
                lint.fail(path, f"{source_label} target cannot be read: {source_ref}: {exc}")
                continue
            if key_pattern in source_text:
                mentions_key = True
        if not mentions_key:
            lint.fail(path, f"{label}.source_refs must include at least one source that mentions {key_pattern}")


def check_vector_reference_closure(lint: Lint) -> None:
    definition_paths = [
        SPEC_ROOT / "zh" / "conformance" / "conformance-vectors.md",
        *sorted((ARTIFACTS / "fixtures").glob("*.json")),
    ]
    known_vectors: set[str] = set()
    for path in definition_paths:
        if not path.is_file():
            continue
        try:
            known_vectors.update(VECTOR_ID_TOKEN_RE.findall(path.read_text(encoding="utf-8")))
        except Exception:
            continue
    if not known_vectors:
        lint.fail(SPEC_ROOT / "zh" / "conformance" / "conformance-vectors.md", "no conformance vector ids found")
        return

    for path in markdown_files() + raw_artifact_files():
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for vector_id in sorted(set(VECTOR_ID_TOKEN_RE.findall(text))):
            if vector_id not in known_vectors:
                lint.fail(path, f"references undefined conformance vector id: {vector_id}")


def check_private_kdf_full_width_nonce(lint: Lint, path: Path, data: dict[str, Any]) -> None:
    vector_id = "ak.vector.aead.full_width_counter_nonce.v1"
    covers = data.get("covers_vectors")
    if not isinstance(covers, list) or vector_id not in covers:
        lint.fail(path, f"covers_vectors must include {vector_id}")
    if isinstance(covers, list) and any("sender_nonce_prefix" in str(value) for value in covers):
        lint.fail(path, "covers_vectors must not retain the removed sender nonce prefix vector")

    cases = {
        case.get("name"): case
        for case in data.get("cases", [])
        if isinstance(case, dict) and isinstance(case.get("name"), str)
    }
    case = cases.get("full_width_counter_nonce_aes128gcm")
    if not isinstance(case, dict) or case.get("vector_id") != vector_id:
        lint.fail(path, "full-width counter nonce KAT is missing or references the wrong vector")
        return
    inputs = case.get("input")
    expected = case.get("expected")
    if not isinstance(inputs, dict) or not isinstance(expected, dict):
        lint.fail(path, "full-width counter nonce KAT input/expected must be objects")
        return
    counter = inputs.get("counter")
    nonce_length = inputs.get("aead_nn")
    if not isinstance(counter, int) or not isinstance(nonce_length, int):
        lint.fail(path, "full-width counter nonce KAT requires integer counter and aead_nn")
        return
    try:
        nonce = counter.to_bytes(nonce_length, "big", signed=False)
    except (OverflowError, ValueError):
        lint.fail(path, "full-width counter nonce KAT input cannot be encoded by I2OSP")
        return
    if expected.get("nonce_hex") != nonce.hex():
        lint.fail(path, "full-width counter nonce KAT nonce_hex does not equal I2OSP(counter, AEAD.Nn)")
    leading_zeroes = nonce_length - max(1, (counter.bit_length() + 7) // 8)
    if expected.get("high_order_zero_bytes") != leading_zeroes:
        lint.fail(path, "full-width counter nonce KAT high_order_zero_bytes drift")

def check_fixtures(lint: Lint, known: dict[str, set[str]]) -> None:
    fixture_dir = ARTIFACTS / "fixtures"
    registry_path = ARTIFACTS / "registry" / "contract-registry.json"
    registry = load_json(lint, registry_path)
    operation_rows = (
        registry.get("operation_registry", {}).get("operations", [])
        if isinstance(registry, dict)
        else []
    )
    operation_contracts = {
        row["operation_id"]: row
        for row in operation_rows
        if isinstance(row, dict) and isinstance(row.get("operation_id"), str)
    }
    for path in sorted(fixture_dir.glob("*.json")):
        data = load_json(lint, path)
        if data is None:
            continue
        check_fixture_operation_contracts(lint, path, data, operation_contracts)
        if path.name == "arkret-private-kdf-fixture.json" and isinstance(data, dict):
            check_private_kdf_full_width_nonce(lint, path, data)
        if path.name == "producer-allocated-identity-collision-fixture.json":
            expected_parameter_source = {
                "registry": "registry/contract-registry.json#id_kind_registry.id_kinds",
                "filter": {"id_form": "producer_allocated"},
                "identity_key": ["mint_authority", "typed_id"],
            }
            if data.get("parameter_source") != expected_parameter_source:
                lint.fail(path, "producer-ID collision fixture must select producer_allocated rows dynamically")
            required_cases = {
                "first_atomic_reservation": "accept_and_reserve_atomically",
                "same_authority_exact_replay": "idempotent_replay",
                "same_authority_conflicting_binding": "reject_and_quarantine",
                "cross_authority_same_uuid": "distinct_identity",
                "bare_typed_id_lookup": "reject",
                "unauthorized_allocator": "reject",
            }
            actual_cases = {
                case.get("name"): case.get("expected")
                for case in data.get("cases", [])
                if isinstance(case, dict)
            }
            if actual_cases != required_cases:
                lint.fail(path, "producer-ID collision fixture must contain the closed six-case contract")
            if "expanded_kinds" in data:
                lint.fail(path, "producer-ID collision fixture must not freeze a hand-maintained kind list")
        check_fixture_schema_validation_cases(lint, path, data)
        check_event_envelope_candidates(lint, path, data, known["event_kinds"])
        for json_path, value, key in walk_json(data):
            if key in {"auth_weight", "authority_class"}:
                lint.fail(path, f"{json_path} uses removed state-resolution authority field: {key}")

            if not isinstance(value, str):
                continue

            # schema-definition-validator-kat.json supplies documents to
            # ak.schema.define; their value.$id values are definitions,
            # not references that must already exist in the registry.
            if path.name != "schema-definition-validator-kat.json":
                for schema_id in SCHEMA_ID_TOKEN_RE.findall(value):
                    if schema_id not in known["schema_ids"]:
                        lint.fail(path, f"{json_path} references unknown schema id: {schema_id}")

            for profile_id in PROFILE_ID_TOKEN_RE.findall(value):
                if profile_id not in known["profiles"]:
                    lint.fail(path, f"{json_path} references unknown profile: {profile_id}")

            if key == "event_kind" and value.startswith("ak.") and value not in known["event_kinds"]:
                lint.fail(path, f"{json_path} references unregistered Event.kind: {value}")
            if key in {"operation_id", "mapped_operation_id"} and value.startswith("ak."):
                if value not in known["operation_ids"]:
                    lint.fail(path, f"{json_path} references unregistered operation_id: {value}")
            if key == "call" and ".recovery.call" in json_path and value.startswith("ak."):
                if value not in known["operation_ids"]:
                    lint.fail(path, f"{json_path} references unregistered recovery operation_id: {value}")
            if key == "constraint_kind" and value not in known["constraint_types"]:
                lint.fail(path, f"{json_path} uses invalid constraint_kind: {value}")

            negative_token_branch = any(
                segment in f"{json_path}." for segment in NEGATIVE_TOKEN_PATH_SEGMENTS
            )
            for match in TYPED_ID_TOKEN_RE.finditer(value):
                kind = match.group(1)
                if negative_token_branch:
                    if kind not in known["id_kinds"] and kind not in known["special_id_kinds"]:
                        lint.fail(path, f"{json_path} references unregistered typed ID kind: ak:{kind}:")
                    continue
                exemption_key = (
                    f"{path.name}#{json_path_to_pointer(json_path)}|{value}"
                )
                if exemption_key in known.get("fixture_typed_id_exemption_keys", set()):
                    continue
                check_typed_id_token(lint, path, json_path, kind, match.group(2), known)


def check_fixture_operation_contracts(
    lint: Lint,
    path: Path,
    data: Any,
    operation_contracts: dict[str, dict[str, Any]],
) -> None:
    """Bind positive fixture request/response claims to registered schemas.

    A case opts in by carrying an ``operation_id`` together with either a
    concrete ``request`` or ``expected_required_fields``. The operation
    registry selects the owning request/response schema, so a fixture cannot
    silently pin a stale parallel contract.
    """

    if not isinstance(data, dict):
        return
    machine_contracts = data.get("machine_contracts")
    declared_contracts = (
        set(machine_contracts)
        if isinstance(machine_contracts, list)
        and all(isinstance(value, str) for value in machine_contracts)
        else set()
    )
    cases = data.get("cases")
    if not isinstance(cases, list):
        return

    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            continue
        operation_id = case.get("operation_id")
        has_request = "request" in case
        has_required_fields = "expected_required_fields" in case
        if not has_request and not has_required_fields:
            continue
        label = f"cases[{index}]"
        if not isinstance(operation_id, str):
            continue
        operation = operation_contracts.get(operation_id)
        if operation is None:
            lint.fail(path, f"{label} references unregistered operation_id {operation_id}")
            continue

        if has_request:
            request_schema_ref = operation.get("request_schema_ref")
            if not isinstance(request_schema_ref, str):
                lint.fail(path, f"{label} operation has no request_schema_ref: {operation_id}")
            else:
                check_json_instance_against_schema(
                    lint,
                    path,
                    f"{label}.request",
                    request_schema_ref,
                    case.get("request"),
                )
            bindings = case.get("request_digest_bindings", [])
            if not isinstance(bindings, list):
                lint.fail(path, f"{label}.request_digest_bindings must be an array")
            else:
                for binding_index, binding in enumerate(bindings):
                    binding_label = f"{label}.request_digest_bindings[{binding_index}]"
                    if not isinstance(binding, dict):
                        lint.fail(path, f"{binding_label} must be an object")
                        continue
                    target_pointer = binding.get("target_pointer")
                    expected_digest = binding.get("expected_digest")
                    input_value = binding.get("input")
                    if (
                        not isinstance(target_pointer, str)
                        or not target_pointer.startswith("/")
                        or not isinstance(expected_digest, str)
                        or input_value is None
                    ):
                        lint.fail(
                            path,
                            f"{binding_label} requires target_pointer, input and expected_digest",
                        )
                        continue
                    recomputed_digest = sha256_text(canonical_json(input_value))
                    if expected_digest != recomputed_digest:
                        lint.fail(
                            path,
                            f"{binding_label}.expected_digest does not hash its canonical input",
                        )
                    try:
                        target_digest = resolve_json_pointer(
                            case.get("request"),
                            "#" + target_pointer,
                        )
                    except (KeyError, TypeError, ValueError) as exc:
                        lint.fail(path, f"{binding_label}.target_pointer cannot be resolved: {exc}")
                        continue
                    if target_digest != expected_digest:
                        lint.fail(
                            path,
                            f"{binding_label} target digest does not equal expected_digest",
                        )

        if not has_required_fields:
            continue
        response_schema_ref = operation.get("response_schema_ref")
        if not isinstance(response_schema_ref, str):
            lint.fail(path, f"{label} operation has no response_schema_ref: {operation_id}")
            continue
        if declared_contracts and response_schema_ref not in declared_contracts:
            lint.fail(
                path,
                f"{label} response schema {response_schema_ref} is absent from machine_contracts",
            )
        schema_path = resolve_artifact_schema_ref(lint, path, response_schema_ref)
        if schema_path is None:
            continue
        fragment = "#" + response_schema_ref.split("#", 1)[1] if "#" in response_schema_ref else "#"
        try:
            schema = resolve_json_pointer(load_schema_document(lint, schema_path), fragment)
        except (KeyError, TypeError, ValueError) as exc:
            lint.fail(path, f"{label} response schema cannot be resolved: {exc}")
            continue
        if not isinstance(schema, dict) or schema.get("type") != "object":
            lint.fail(path, f"{label} response schema is not an object")
            continue
        if schema.get("additionalProperties") is not False:
            lint.fail(path, f"{label} response schema is not closed")
        expected = case.get("expected_required_fields")
        required = schema.get("required")
        if not isinstance(expected, list) or not all(isinstance(field, str) for field in expected):
            lint.fail(path, f"{label}.expected_required_fields must be a string array")
        elif expected != required:
            lint.fail(
                path,
                f"{label}.expected_required_fields must exactly equal {response_schema_ref} required: "
                f"expected {required!r}, got {expected!r}",
            )


def check_declared_schema_fixture_instances(lint: Lint) -> None:
    """Validate every positive fixture object that declares a registered schema ID.

    Fixture suites contain metadata, traces and intentionally invalid branches, so a
    whole fixture file is not itself a wire instance.  The normative boundary is each
    nested object carrying a ``schema`` discriminator.  This check discovers those
    objects across every fixture, resolves the discriminator through the generated
    schema registry (including its fragment), and validates the complete object.
    Negative branches remain owned by explicit ``schema_validation_cases`` so their
    expected failure and first error stay testable.
    """

    registry_path = ARTIFACTS / "registry" / "schema-registry.json"
    registry = load_json(lint, registry_path)
    rows = registry.get("schemas", []) if isinstance(registry, dict) else []
    schema_refs = {
        row["schema_id"]: row["file"] + row.get("fragment", "")
        for row in rows
        if isinstance(row, dict)
        and isinstance(row.get("schema_id"), str)
        and isinstance(row.get("file"), str)
    }

    negative_key_tokens = ("negative", "invalid", "malformed", "rejected", "tampered")

    def visit(owner: Path, value: Any, pointer: str, negative: bool = False) -> None:
        if isinstance(value, dict):
            local_negative = negative or value.get("expect_valid") is False
            schema_id = value.get("schema")
            schema_ref = schema_refs.get(schema_id) if isinstance(schema_id, str) else None
            is_case_overlay = "accepted" in value and "name" in value
            if schema_ref is not None and not local_negative and not is_case_overlay:
                check_json_instance_against_schema(
                    lint,
                    owner,
                    pointer or "/",
                    schema_ref,
                    value,
                )
            for key, child in value.items():
                key_negative = local_negative or any(token in key.lower() for token in negative_key_tokens)
                if key == "input" and value.get("kind") == "canonical_json_digest":
                    key_negative = True
                if (
                    owner.name == "read-cursor-multi-device-merge-fixture.json"
                    and key == "shared"
                ):
                    key_negative = True
                visit(owner, child, f"{pointer}/{key}", key_negative)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(owner, child, f"{pointer}/{index}", negative)

    for path in sorted((ARTIFACTS / "fixtures").glob("*.json")):
        data = load_json(lint, path)
        if data is not None:
            visit(path, data, "")


def content_addressed_sibling_digest_violations(
    data: Any,
    removals: Iterable[tuple[str, tuple[Any, ...], str, str]] = CONTENT_ADDRESSED_REF_MIRROR_REMOVALS,
) -> list[tuple[str, str, str]]:
    """Every `(pointer, ref_field, sibling_digest_field)` this instance violates.

    Split out from the lint entry point so the decision is testable on its own:
    the walk has to reason about JSON-string-embedded records and about negative
    branches, and neither is verifiable through a check that only reads the real
    artifact tree.
    """

    pairs: dict[str, set[str]] = {}
    for _file_name, _path, id_field, digest_field in removals:
        pairs.setdefault(id_field, set()).add(digest_field)

    violations: list[tuple[str, str, str]] = []

    def visit(value: Any, pointer: str, negative: bool) -> None:
        if isinstance(value, dict):
            local_negative = negative or value.get("expect_valid") is False
            if not local_negative:
                for id_field, digest_fields in pairs.items():
                    ref = value.get(id_field)
                    if not isinstance(ref, str) or not CONTENT_ADDRESSED_TYPED_REF_RE.fullmatch(ref):
                        continue
                    for digest_field in sorted(digest_fields):
                        if digest_field in value:
                            violations.append((pointer, id_field, digest_field))
            for key, child in value.items():
                key_negative = local_negative or any(
                    token in key.lower() for token in NEGATIVE_BRANCH_KEY_TOKENS
                )
                visit(child, f"{pointer}/{key}", key_negative)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{pointer}/{index}", negative)
        elif isinstance(value, str) and pointer.rsplit("/", 1)[-1].endswith("_json"):
            try:
                decoded = json.loads(value)
            except ValueError:
                return
            visit(decoded, f"{pointer}(decoded)", negative)

    visit(data, "", False)
    return violations


def check_fixture_content_addressed_sibling_digests(lint: Lint) -> None:
    """`encoding.md` 4.0.1 on fixture instances, not just on schemas.

    ``check_content_addressed_ref_mirror_removals`` proves each registered sibling
    digest is gone from its schema.  That leaves fixtures unguarded wherever a
    record is not schema-validated in place -- a record carried as an embedded
    JSON *string* is opaque to both the schema walk and ``additionalProperties``,
    so it can keep shipping a sibling the schema deleted.

    A violation is claimed only when the ref field actually holds a complete
    content-addressed typed ref.  A union-shaped ref holding a UUID branch carries
    no digest, so its neighbour is not a mirror and is not judged here.
    """

    for path in sorted((ARTIFACTS / "fixtures").glob("*.json")):
        data = load_json(lint, path)
        if data is None:
            continue
        for pointer, id_field, digest_field in content_addressed_sibling_digest_violations(data):
            lint.fail(
                path,
                f"{pointer or '/'}: {digest_field} mirrors the complete "
                f"content-addressed {id_field}; 4.0.1 leaves the ref as the "
                "sole digest source",
            )


FIXTURE_SCHEMA_INSTANCE_BINDING_PATH = (
    ROOT / "tools" / "fixture-schema-instance-binding-registry.json"
)


def check_fixture_schema_instance_bindings(lint: Lint) -> None:
    """Validate fixture instances that carry no `schema` discriminator.

    ``check_declared_schema_fixture_instances`` only claims objects that name
    their own schema. An instance without that member has no schema landing
    point at all: it survives every field deletion its schema makes, and the
    drift surfaces only when some downstream `deny_unknown_fields` type finally
    parses it. Two such objects reached that state within one commit of the
    deletion that should have cascaded to them, so each is bound here by exact
    JSON Pointer and validated in the pipeline instead.
    """

    registry = load_json(lint, FIXTURE_SCHEMA_INSTANCE_BINDING_PATH)
    if not isinstance(registry, dict):
        return
    rows = registry.get("bindings")
    if not isinstance(rows, list) or not rows:
        lint.fail(FIXTURE_SCHEMA_INSTANCE_BINDING_PATH, "bindings must be a non-empty list")
        return

    seen: set[tuple[str, str]] = set()
    for index, row in enumerate(rows):
        label = f"bindings[{index}]"
        if not isinstance(row, dict) or not isinstance(row.get("fixture"), str):
            lint.fail(FIXTURE_SCHEMA_INSTANCE_BINDING_PATH, f"{label} must name a fixture")
            continue
        fixture, pointer = row["fixture"], row.get("pointer")
        schema_ref, why = row.get("schema_ref"), row.get("why")
        label = f"{fixture}#{pointer}"
        if not isinstance(pointer, str) or not pointer.startswith("/"):
            lint.fail(FIXTURE_SCHEMA_INSTANCE_BINDING_PATH, f"{label}: pointer must start with /")
            continue
        if not isinstance(schema_ref, str) or "schemas/" not in schema_ref:
            lint.fail(FIXTURE_SCHEMA_INSTANCE_BINDING_PATH, f"{label}: schema_ref must name a schema")
            continue
        if not isinstance(why, str) or len(why.strip()) < 20:
            lint.fail(
                FIXTURE_SCHEMA_INSTANCE_BINDING_PATH,
                f"{label}: why must say what makes this object schema-less",
            )
            continue
        key = (fixture, pointer)
        if key in seen:
            lint.fail(FIXTURE_SCHEMA_INSTANCE_BINDING_PATH, f"{label}: duplicate binding")
            continue
        seen.add(key)

        path = ARTIFACTS / "fixtures" / fixture
        if not path.is_file():
            lint.fail(FIXTURE_SCHEMA_INSTANCE_BINDING_PATH, f"{label}: fixture does not exist")
            continue
        data = load_json(lint, path)
        if data is None:
            continue
        try:
            instance = resolve_json_pointer(data, f"#{pointer}")
        except (KeyError, IndexError, ValueError):
            lint.fail(path, f"{pointer}: bound instance no longer resolves; retarget or retire the row")
            continue
        if row.get("decode") == "json_string":
            if not isinstance(instance, str):
                lint.fail(path, f"{pointer}: declared json_string but the value is not a string")
                continue
            try:
                instance = json.loads(instance)
            except ValueError as error:
                lint.fail(path, f"{pointer}: embedded JSON string does not parse: {error}")
                continue
        elif "decode" in row:
            lint.fail(FIXTURE_SCHEMA_INSTANCE_BINDING_PATH, f"{label}: unknown decode mode")
            continue
        if isinstance(instance, dict) and isinstance(instance.get("schema"), str):
            lint.fail(
                FIXTURE_SCHEMA_INSTANCE_BINDING_PATH,
                f"{label}: the instance names its own schema, so it is already owned by "
                "check_declared_schema_fixture_instances; two owners can disagree",
            )
            continue
        check_json_instance_against_schema(lint, path, pointer, schema_ref, instance)


def _event_id_validation_error(value: Any, active_suite_codes: set[int]) -> str | None:
    """Return the semantic v1 Event-ID validation error, if any."""

    if not isinstance(value, str) or not value.startswith("ak:event:"):
        return "must be an ak:event: identifier"
    token = value.removeprefix("ak:event:")
    if not re.fullmatch(r"[A-Za-z0-9_-]{44}", token):
        return "must carry a canonical 44-character base64url token"
    try:
        body = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    except (ValueError, binascii.Error):
        return "must carry decodable base64url"
    if base64.urlsafe_b64encode(body).rstrip(b"=").decode("ascii") != token:
        return "must use canonical unpadded base64url"
    if len(body) != 33:
        return "must decode to the 33-byte v1 Event-ID body"
    header = body[0]
    if header >> 4:
        return f"uses non-zero reserved header nibble 0x{header:02x}"
    suite_code = header & 0x0F
    if suite_code == 0:
        return "uses permanently invalid digest-suite code 0x0"
    if suite_code not in active_suite_codes:
        return f"uses inactive or unassigned digest-suite code 0x{suite_code:x}"
    return None


def check_keypackage_write_transcript_fixture(lint: Lint) -> None:
    """Bind every KeyPackage write transcript to its wire schema and bytes.

    The fixture stores the request before its top-level signature is attached,
    so the generic declared-schema walker cannot validate these cases.  Rebuild
    the signed wire object here, resolve its schema through the operation
    registry, then verify the canonical transcript and Ed25519 signature.
    """

    fixture_path = ARTIFACTS / "fixtures" / "keypackage-write-transcript-fixture.json"
    fixture = load_json(lint, fixture_path)
    registry_path = ARTIFACTS / "registry" / "operation-registry.json"
    registry = load_json(lint, registry_path)
    if not isinstance(fixture, dict) or not isinstance(registry, dict):
        return

    test_key = fixture.get("test_key")
    cases = fixture.get("cases")
    if not isinstance(test_key, dict) or not isinstance(cases, list):
        lint.fail(fixture_path, "KeyPackage write transcript fixture needs test_key and cases[]")
        return
    kid = test_key.get("kid")
    public_key_text = test_key.get("public_key")
    private_key_seed_text = test_key.get("private_key_seed")
    if (
        test_key.get("algorithm") != "Ed25519"
        or not isinstance(kid, str)
        or not isinstance(public_key_text, str)
        or not isinstance(private_key_seed_text, str)
    ):
        lint.fail(fixture_path, "test_key must declare an Ed25519 kid, private_key_seed and public_key")
        return

    def decode_base64url(label: str, value: Any) -> bytes | None:
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
            lint.fail(fixture_path, f"{label} must be an unpadded base64url string")
            return None
        try:
            decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        except (ValueError, binascii.Error):
            lint.fail(fixture_path, f"{label} is not valid base64url")
            return None
        if base64.urlsafe_b64encode(decoded).rstrip(b"=").decode("ascii") != value:
            lint.fail(fixture_path, f"{label} is not canonical unpadded base64url")
            return None
        return decoded

    public_key_bytes = decode_base64url("test_key.public_key", public_key_text)
    private_key_seed = decode_base64url("test_key.private_key_seed", private_key_seed_text)
    if public_key_bytes is None or private_key_seed is None:
        return
    if len(public_key_bytes) != 32 or len(private_key_seed) != 32:
        lint.fail(fixture_path, "test_key Ed25519 public key and private seed must each be 32 bytes")
        return
    if (
        Ed25519PrivateKey is None
        or Ed25519PublicKey is None
        or InvalidSignature is None
        or serialization is None
    ):
        lint.fail(fixture_path, "cryptography is required to verify KeyPackage transcript signatures")
        return
    try:
        verifying_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
        derived_public_key = Ed25519PrivateKey.from_private_bytes(private_key_seed).public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    except ValueError as exc:
        lint.fail(fixture_path, f"test_key does not contain valid Ed25519 key material: {exc}")
        return
    if derived_public_key != public_key_bytes:
        lint.fail(fixture_path, "test_key.public_key does not derive from test_key.private_key_seed")

    operation_schema_refs = {
        row.get("operation_id"): row.get("request_schema_ref")
        for row in registry.get("operations", [])
        if isinstance(row, dict)
        and isinstance(row.get("operation_id"), str)
        and isinstance(row.get("request_schema_ref"), str)
    }
    expected_operations = {
        "upload_batch_required_fields": "ak.self.keys.keypackages.upload.create.v1",
        "consume_single_claim": "ak.self.keys.keypackages.command.consume.v1",
        "consume_receipt_single_source_coordinates": None,
        "revoke_with_reason": "ak.self.keys.keypackages.command.revoke.v1",
    }
    actual_names = {
        case.get("name") for case in cases if isinstance(case, dict) and isinstance(case.get("name"), str)
    }
    if len(cases) != len(expected_operations) or actual_names != set(expected_operations):
        lint.fail(fixture_path, f"KeyPackage write transcript cases drifted: {sorted(actual_names)}")

    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            lint.fail(fixture_path, f"cases[{index}] must be an object")
            continue
        name = case.get("name")
        if name == "consume_receipt_single_source_coordinates":
            signed_receipt = case.get("signed_receipt")
            domain = case.get("domain")
            if not isinstance(signed_receipt, dict) or domain != "ak.keypackage.consume_receipt.v1\n":
                lint.fail(
                    fixture_path,
                    "consume receipt transcript needs signed_receipt and the canonical receipt domain",
                )
                continue
            unsigned_receipt = dict(signed_receipt)
            signature_object = unsigned_receipt.pop("signature", None)
            canonical = canonical_json(unsigned_receipt)
            if case.get("canonical_jcs") != canonical:
                lint.fail(
                    fixture_path,
                    "consume receipt canonical_jcs does not equal JCS(receipt without signature)",
                )
            expected_signing_input = domain.encode("utf-8") + canonical.encode("utf-8")
            stated_signing_input = decode_base64url(
                "consume receipt signing_input_base64url",
                case.get("signing_input_base64url"),
            )
            if stated_signing_input is not None and stated_signing_input != expected_signing_input:
                lint.fail(
                    fixture_path,
                    "consume receipt signing_input_base64url does not encode domain || JCS(unsigned receipt)",
                )
            signature_text = case.get("signature")
            if not isinstance(signature_object, dict) or signature_object.get("sig") != signature_text:
                lint.fail(fixture_path, "consume receipt inner and fixture signatures must match")
                continue
            signature_bytes = decode_base64url("consume receipt signature", signature_text)
            if signature_bytes is not None:
                try:
                    verifying_key.verify(signature_bytes, expected_signing_input)
                except InvalidSignature:
                    lint.fail(
                        fixture_path,
                        "consume receipt signature does not verify over domain || JCS(unsigned receipt)",
                    )
            continue
        operation_id = case.get("operation_id")
        unsigned = case.get("unsigned_request")
        domain = case.get("domain")
        stated_canonical = case.get("canonical_jcs")
        if not isinstance(name, str) or not isinstance(operation_id, str) or not isinstance(unsigned, dict):
            lint.fail(fixture_path, f"cases[{index}] needs name, operation_id and unsigned_request")
            continue
        if operation_id != expected_operations.get(name):
            lint.fail(fixture_path, f"{name}.operation_id is not the registered transcript operation")
            continue
        if domain != operation_id + "\n":
            lint.fail(fixture_path, f"{name}.domain must equal operation_id plus newline")
            continue

        canonical = canonical_json(unsigned)
        if stated_canonical != canonical:
            lint.fail(fixture_path, f"{name}.canonical_jcs does not equal JCS(unsigned_request)")
        expected_signing_input = domain.encode("utf-8") + canonical.encode("utf-8")
        stated_signing_input = decode_base64url(
            f"{name}.signing_input_base64url", case.get("signing_input_base64url")
        )
        if stated_signing_input is not None and stated_signing_input != expected_signing_input:
            lint.fail(fixture_path, f"{name}.signing_input_base64url does not encode domain || JCS(unsigned_request)")

        signature_bytes = decode_base64url(f"{name}.signature", case.get("signature"))
        if signature_bytes is not None:
            if len(signature_bytes) != 64:
                lint.fail(fixture_path, f"{name}.signature must encode exactly 64 Ed25519 bytes")
                continue
            try:
                verifying_key.verify(signature_bytes, expected_signing_input)
            except InvalidSignature:
                lint.fail(fixture_path, f"{name}.signature does not verify over domain || JCS(unsigned_request)")

        signature_object = {
            "kid": kid,
            "signature_algorithm": "Ed25519",
            "sig": case.get("signature"),
        }
        schema_ref = operation_schema_refs.get(operation_id)
        if not isinstance(schema_ref, str):
            lint.fail(fixture_path, f"{name} operation has no request_schema_ref: {operation_id}")
            continue
        instance = copy.deepcopy(unsigned)
        signature_field = "endpoint_signature" if name == "upload_batch_required_fields" else "signature"
        instance[signature_field] = signature_object
        check_json_instance_against_schema(lint, fixture_path, name, schema_ref, instance)


def check_fixture_schema_validation_cases(lint: Lint, path: Path, data: Any) -> None:
    if not isinstance(data, dict):
        return
    cases = data.get("schema_validation_cases")
    if cases is None:
        return
    if not isinstance(cases, list) or not cases:
        lint.fail(path, "schema_validation_cases must be a non-empty array when present")
        return
    named_instances: dict[str, Any] = {}
    for index, case in enumerate(cases):
        label = f"schema_validation_cases[{index}]"
        if not isinstance(case, dict):
            lint.fail(path, f"{label} must be an object")
            continue
        schema_ref = case.get("schema_ref")
        instance = case.get("instance")
        instance_from = case.get("instance_from")
        if "instance" not in case and isinstance(instance_from, str):
            base_instance = named_instances.get(instance_from)
            mutations = case.get("mutations")
            if base_instance is None or not isinstance(mutations, list):
                lint.fail(
                    path,
                    f"{label}.instance_from must name an earlier case and mutations must be an array",
                )
                continue
            instance = copy.deepcopy(base_instance)
            for mutation in mutations:
                if (
                    not isinstance(mutation, dict)
                    or mutation.get("op") not in {"add", "replace", "remove"}
                    or not isinstance(mutation.get("path"), str)
                ):
                    lint.fail(path, f"{label}.mutations supports explicit add/replace/remove operations")
                    instance = None
                    break
                tokens = [
                    token.replace("~1", "/").replace("~0", "~")
                    for token in mutation["path"].lstrip("/").split("/")
                    if token
                ]
                target = instance
                for token in tokens[:-1]:
                    if not isinstance(target, dict) or token not in target:
                        target = None
                        break
                    target = target[token]
                if not isinstance(target, dict) or not tokens:
                    lint.fail(path, f"{label}.mutation path does not resolve")
                    instance = None
                    break
                leaf = tokens[-1]
                operation = mutation["op"]
                if operation in {"replace", "remove"} and leaf not in target:
                    lint.fail(path, f"{label}.mutation target does not exist")
                    instance = None
                    break
                if operation == "remove":
                    del target[leaf]
                else:
                    target[leaf] = mutation.get("value")
        expect_valid = case.get("expect_valid", True)
        if not isinstance(schema_ref, str) or not schema_ref:
            lint.fail(path, f"{label}.schema_ref must be a non-empty string")
            continue
        if instance is None:
            lint.fail(path, f"{label}.instance is required")
            continue
        if not isinstance(expect_valid, bool):
            lint.fail(path, f"{label}.expect_valid must be boolean when present")
            continue
        first_expected_error = case.get("first_expected_error")
        if expect_valid:
            if first_expected_error is not None:
                lint.fail(path, f"{label}.first_expected_error is only valid when expect_valid=false")
                continue
        elif not isinstance(first_expected_error, str) or not first_expected_error:
            lint.fail(path, f"{label}.first_expected_error must be a non-empty string when expect_valid=false")
            continue
        case_name = case.get("name")
        if not isinstance(case_name, str) or not case_name:
            case_name = label
        named_instances[case_name] = copy.deepcopy(instance)
        check_json_instance_against_schema(
            lint,
            path,
            case_name,
            schema_ref,
            instance,
            expect_valid,
            first_expected_error,
        )

    if path.name == "schema-validation-fixture.json":
        base = named_instances.get("service_describe_valid")
        extended = named_instances.get("service_describe_x_metadata_ignored_valid")
        if not isinstance(base, dict) or not isinstance(extended, dict):
            lint.fail(path, "ServiceDescribe x_* metamorphic fixture pair is missing")
        else:
            stripped = {
                key: value
                for key, value in extended.items()
                if not key.startswith("x_")
            }
            if stripped != base:
                lint.fail(
                    path,
                    "removing every top-level x_* field must reproduce the same valid ServiceDescribe",
                )


def check_crypto_signature_fixture(lint: Lint) -> None:
    path = ARTIFACTS / "fixtures" / "crypto-signature-fixture.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return

    vectors = data.get("vectors", [])
    if not isinstance(vectors, list):
        lint.fail(path, "vectors must be a list")
        return

    for index, vector in enumerate(vectors):
        if not isinstance(vector, dict):
            lint.fail(path, f"vectors[{index}] must be an object")
            continue

        event = vector.get("event_without_proofs")
        if isinstance(event, dict):
            signed_event = dict(event)
            # zh/conformance/encoding.md section 6: the digest preimage removes
            # event_id, proofs and unsigned. event_id is excluded because
            # section 4.0 derives it from this very digest.
            signed_event.pop("unsigned", None)
            signed_event.pop("event_id", None)
            expected_canonical = canonical_json(signed_event)
            if vector.get("canonical_event_payload") != expected_canonical:
                lint.fail(path, f"vectors[{index}] canonical_event_payload does not match canonical JSON")
            expected_event_digest = sha256_text(expected_canonical)
            if vector.get("event_digest") != expected_event_digest:
                lint.fail(path, f"vectors[{index}] event_digest does not match canonical_event_payload")

            event_with_proof = vector.get("event_with_proof")
            if isinstance(event_with_proof, dict):
                unsigned = dict(event_with_proof)
                unsigned.pop("proofs", None)
                unsigned.pop("unsigned", None)
                unsigned.pop("event_id", None)
                if unsigned != signed_event:
                    lint.fail(path, f"vectors[{index}] event_with_proof without proofs differs from event_without_proofs")

        binding = vector.get("binding_object")
        if isinstance(binding, dict):
            expected_binding = canonical_json(binding)
            if vector.get("canonical_binding_payload") != expected_binding:
                lint.fail(path, f"vectors[{index}] canonical_binding_payload does not match canonical JSON")
            expected_binding_digest = sha256_text(expected_binding)
            if vector.get("binding_digest") != expected_binding_digest:
                lint.fail(path, f"vectors[{index}] binding_digest does not match canonical_binding_payload")
            if vector.get("detached_payload_b64u") != base64url_text(expected_binding):
                lint.fail(path, f"vectors[{index}] detached_payload_b64u does not match canonical_binding_payload")

        protected_header = vector.get("protected_header")
        if isinstance(protected_header, dict):
            expected_header = canonical_json(protected_header)
            if vector.get("protected_header_canonical") != expected_header:
                lint.fail(path, f"vectors[{index}] protected_header_canonical does not match canonical JSON")

        proof = vector.get("proof")
        if isinstance(proof, dict) and isinstance(vector.get("event_digest"), str):
            if proof.get("event_digest") != vector["event_digest"]:
                lint.fail(path, f"vectors[{index}] proof event_digest differs from vector event_digest")

    negative_cases = data.get("negative_cases")
    if not isinstance(negative_cases, list) or not negative_cases:
        lint.fail(path, "negative_cases must be a non-empty list")
        return
    positive_names = {vector.get("name") for vector in vectors if isinstance(vector, dict)}
    negative_bases = {
        case.get("base_vector")
        for case in negative_cases
        if isinstance(case, dict) and isinstance(case.get("base_vector"), str)
    }
    missing_algorithm_negatives = positive_names - negative_bases
    if missing_algorithm_negatives:
        lint.fail(path, f"each active signature vector needs an algorithm-specific negative case: {sorted(missing_algorithm_negatives)}")


def check_canonical_digest_fixtures(lint: Lint) -> None:
    """T4-1: canonical-JSON recompute guard.

    Walk every fixture JSON and, when it contains both a canonical-input
    object and an expected digest field, recompute the digest from the
    input's canonical bytes and require an exact match.

    Recognized fixture shapes:
      { "input": <obj>, "expected_digest": "sha256:..." }
      { "input": <obj>, "digest": "sha256:..." }
      { "envelope": <obj>, "event_digest": "sha256:..." }
      { "envelope": <obj>, "payload_hash": "sha256:..." }
      { "canonical_bytes": "<hex>", "digest": "sha256:..." }
      { "root_basis": <obj>, "expected_root_basis_digest": "sha256:..." }

    This is intentionally narrow: it does not try to canonicalize whole
    repositories of arbitrary fixtures. New fixtures opt in by naming
    their input + digest fields using one of the shapes above.
    """
    fixtures_dir = ARTIFACTS / "fixtures"
    if not fixtures_dir.exists():
        return

    shapes: list[tuple[str, str]] = [
        ("input", "expected_digest"),
        ("input", "digest"),
        ("envelope", "event_digest"),
        ("envelope", "payload_hash"),
        ("canonical_input", "expected_digest"),
        ("root_basis", "expected_root_basis_digest"),
    ]

    def iter_dict_nodes(value: Any) -> Iterable[dict[str, Any]]:
        if isinstance(value, dict):
            yield value
            for child in value.values():
                yield from iter_dict_nodes(child)
        elif isinstance(value, list):
            for child in value:
                yield from iter_dict_nodes(child)

    for fixture_path in fixtures_dir.rglob("*.json"):
        data = load_json(lint, fixture_path)
        if data is None:
            continue

        for case in iter_dict_nodes(data):
            for input_key, digest_key in shapes:
                if input_key not in case or digest_key not in case:
                    continue
                expected = case.get(digest_key)
                if not isinstance(expected, str):
                    continue
                if not expected.startswith("sha256:"):
                    # Non-sha256 algorithms are out of scope for this guard.
                    continue
                canonical_input = case[input_key]
                if (
                    case.get("vector_id") == "ak.vector.encoding.event_digest.v1"
                    and input_key == "input"
                    and isinstance(canonical_input, dict)
                ):
                    canonical_input = {
                        key: value
                        for key, value in canonical_input.items()
                        if key not in {"proofs", "unsigned", "event_id"}
                    }
                try:
                    canonical = canonical_json(canonical_input)
                except (TypeError, ValueError) as exc:
                    lint.fail(
                        fixture_path,
                        f"could not canonicalize {input_key!r} for digest check: {exc}",
                    )
                    continue
                expected_canonical = case.get("expected_canonical_bytes_utf8")
                if isinstance(expected_canonical, str) and expected_canonical != canonical:
                    lint.fail(
                        fixture_path,
                        f"canonical bytes mismatch: {input_key!r} produces {canonical!r} "
                        f"but expected_canonical_bytes_utf8={expected_canonical!r}",
                    )
                domain_separator = case.get("domain_separator_utf8", "")
                if not isinstance(domain_separator, str):
                    lint.fail(
                        fixture_path,
                        "domain_separator_utf8 must be a string when present",
                    )
                    continue
                digest_input = domain_separator + canonical
                digest_input_hex = case.get("digest_input_hex")
                if isinstance(digest_input_hex, str) and digest_input_hex != digest_input.encode("utf-8").hex():
                    lint.fail(
                        fixture_path,
                        f"digest_input_hex does not match domain_separator_utf8 || {input_key!r} canonical bytes",
                    )
                recomputed = sha256_text(digest_input)
                if recomputed != expected:
                    lint.fail(
                        fixture_path,
                        f"digest mismatch: domain separator plus {input_key!r} canonical bytes produce "
                        f"{recomputed} but {digest_key!r}={expected}",
                    )


def check_direct_conversation_digest_vectors(lint: Lint) -> None:
    """Pin the two domain-separated Direct Conversation identity digests."""

    fixture_path = ARTIFACTS / "fixtures" / "encoding-fixture.json"
    fixture = load_json(lint, fixture_path)
    if not isinstance(fixture, dict) or not isinstance(fixture.get("vectors"), list):
        return

    vectors = {
        vector.get("vector_id"): vector
        for vector in fixture["vectors"]
        if isinstance(vector, dict) and isinstance(vector.get("vector_id"), str)
    }
    pair = vectors.get("ak.vector.direct_conversation.pair_key.v1")
    binding = vectors.get("ak.vector.direct_conversation.binding_digest.v1")
    if not isinstance(pair, dict):
        lint.fail(fixture_path, "missing direct-conversation pair_key KAT")
        return
    if not isinstance(binding, dict):
        lint.fail(fixture_path, "missing direct-conversation binding_digest KAT")
        return

    expected_pair_domain = "ak.direct-conversation.pair-key.v1\n"
    if pair.get("domain_separator_utf8") != expected_pair_domain:
        lint.fail(fixture_path, "direct-conversation pair_key KAT has the wrong domain separator")
    pair_input = pair.get("input")
    if not isinstance(pair_input, dict) or set(pair_input) != {"participants", "trust_domain_id"}:
        lint.fail(
            fixture_path,
            "direct-conversation pair_key input must be exactly {participants, trust_domain_id}",
        )
    elif (
        not isinstance(pair_input.get("participants"), list)
        or len(pair_input["participants"]) != 2
        or not all(isinstance(value, dict) for value in pair_input["participants"])
        or len({canonical_json(value) for value in pair_input["participants"]}) != 2
        or pair_input["participants"] != sorted(
            pair_input["participants"], key=lambda value: canonical_json(value).encode("utf-8")
        )
    ):
        lint.fail(fixture_path, "direct-conversation pair_key participants must be two distinct ActorIds sorted by JCS bytes")

    expected_binding_domain = "ak.direct-conversation.binding-digest.v1\n"
    if binding.get("domain_separator_utf8") != expected_binding_domain:
        lint.fail(fixture_path, "direct-conversation binding_digest KAT has the wrong domain separator")
    canonical_binding = binding.get("input")
    valid_digest = binding.get("expected_digest")
    if not isinstance(canonical_binding, dict) or not isinstance(valid_digest, str):
        lint.fail(fixture_path, "direct-conversation binding_digest KAT lacks input or digest")
        return

    expected_binding_fields = {
        "pair_key",
        "unordered_participant_ids",
        "realm_id",
        "main_strand_id",
        "founding_unit_digest",
        "authorization_basis",
        "initial_exact_pair_group_state_ref",
    }
    if set(canonical_binding) != expected_binding_fields:
        lint.fail(fixture_path, "binding_digest canonical object has the wrong closed field set")

    def normalize_payload(payload: Any, label: str) -> dict[str, Any] | None:
        if not isinstance(payload, dict):
            lint.fail(fixture_path, f"{label}.payload must be an object")
            return None
        if "binding_digest" in payload:
            lint.fail(fixture_path, f"{label}.payload must not carry binding_digest")
        basis = payload.get("authorization_basis")
        participants = payload.get("unordered_participant_ids")
        refs = basis.get("event_refs") if isinstance(basis, dict) else None
        if (
            not isinstance(participants, list)
            or len(participants) != 2
            or not all(isinstance(value, dict) for value in participants)
            or len({canonical_json(value) for value in participants}) != 2
            or not isinstance(basis, dict)
            or set(basis) != {"kind", "event_refs"}
            or not isinstance(basis.get("kind"), str)
            or not isinstance(refs, list)
            or len(refs) != 2
            or not all(isinstance(value, str) for value in refs)
            or len(set(refs)) != 2
        ):
            lint.fail(fixture_path, f"{label}.payload has invalid unordered binding inputs")
            return None
        missing = expected_binding_fields - set(payload)
        if missing:
            lint.fail(fixture_path, f"{label}.payload misses binding fields: {sorted(missing)}")
            return None
        return {
            "pair_key": payload["pair_key"],
            "unordered_participant_ids": sorted(
                participants, key=lambda value: canonical_json(value).encode("utf-8")
            ),
            "realm_id": payload["realm_id"],
            "main_strand_id": payload["main_strand_id"],
            "founding_unit_digest": payload["founding_unit_digest"],
            "authorization_basis": {
                "kind": basis["kind"],
                "event_refs": sorted(refs, key=lambda value: value.encode("utf-8")),
            },
            "initial_exact_pair_group_state_ref": payload[
                "initial_exact_pair_group_state_ref"
            ],
        }

    normalization_cases = binding.get("normalization_cases")
    if not isinstance(normalization_cases, list) or not normalization_cases:
        lint.fail(fixture_path, "binding_digest KAT must include normalization cases")
    else:
        for index, case in enumerate(normalization_cases):
            label = f"binding normalization_cases[{index}]"
            if not isinstance(case, dict):
                lint.fail(fixture_path, f"{label} must be an object")
                continue
            normalized = normalize_payload(case.get("payload"), label)
            if normalized is None:
                continue
            if normalized != canonical_binding:
                lint.fail(fixture_path, f"{label} does not normalize to the canonical binding object")
            recomputed = sha256_text(expected_binding_domain + canonical_json(normalized))
            if case.get("expected_digest") != recomputed or recomputed != valid_digest:
                lint.fail(fixture_path, f"{label} does not preserve the binding digest")
            event_context = case.get("event_context")
            if not isinstance(event_context, dict) or not {"actor_id", "proof"} <= set(event_context):
                lint.fail(fixture_path, f"{label} must cover excluded Event actor/proof context")

    mutations = binding.get("mutation_cases")
    if not isinstance(mutations, list):
        lint.fail(fixture_path, "binding_digest KAT must include mutation_cases")
    else:
        mutation_by_name = {
            case.get("name"): case for case in mutations if isinstance(case, dict)
        }
        omitted = mutation_by_name.get("omit_domain_separator")
        if not isinstance(omitted, dict):
            lint.fail(fixture_path, "binding_digest KAT misses omit_domain_separator")
        else:
            canonical_bytes = canonical_json(canonical_binding).encode("utf-8")
            if omitted.get("digest_input_hex") != canonical_bytes.hex():
                lint.fail(fixture_path, "omit_domain_separator does not hash bare canonical bytes")
            omitted_digest = "sha256:" + hashlib.sha256(canonical_bytes).hexdigest()
            if (
                omitted.get("expected_digest") != omitted_digest
                or omitted.get("must_not_equal_valid") is not True
                or omitted_digest == valid_digest
            ):
                lint.fail(fixture_path, "omit_domain_separator is not a strict negative")
        changed = mutation_by_name.get("semantic_main_strand_change")
        if (
            not isinstance(changed, dict)
            or changed.get("must_not_equal_valid") is not True
            or changed.get("expected_digest") == valid_digest
        ):
            lint.fail(fixture_path, "semantic binding mutation is not a strict negative")

    schema_path = ARTIFACTS / "schemas" / "event-payload.schema.json"
    schema = load_json(lint, schema_path)
    bound_payload = (
        schema.get("$defs", {}).get("direct_conversation_bound_payload", {})
        if isinstance(schema, dict)
        else {}
    )
    properties = bound_payload.get("properties", {}) if isinstance(bound_payload, dict) else {}
    if "binding_digest" in properties or bound_payload.get("additionalProperties") is not False:
        lint.fail(schema_path, "binding_digest must remain derived and off-wire in the closed payload")



def _stated_preimage_bytes(source: str, decoding: str) -> bytes | None:
    if decoding == "utf8":
        return source.encode("utf-8")
    if decoding == "base64url":
        try:
            return base64.urlsafe_b64decode(source + "=" * (-len(source) % 4))
        except (ValueError, binascii.Error):
            return None
    if decoding == "hex":
        try:
            return bytes.fromhex(source)
        except ValueError:
            return None
    raise AssertionError(f"unknown stated-preimage decoding: {decoding}")


def _stated_digest(data: bytes, encoding: str) -> str:
    digest = hashlib.sha256(data).digest()
    if encoding == "sha256_hex":
        return "sha256:" + digest.hex()
    if encoding == "raw_hex":
        return digest.hex()
    if encoding == "base64url":
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    raise AssertionError(f"unknown stated-digest encoding: {encoding}")


def check_schema_fixture_canonical_public_material(lint: Lint) -> None:
    """Keep CanonicalPublicMaterial fixtures internally reproducible."""
    fixture_path = ARTIFACTS / "fixtures" / "schema-validation-fixture.json"
    fixture = load_json(lint, fixture_path)
    if fixture is None:
        return

    found = 0
    required = {"canonical_encoding", "value", "canonical_bytes_base64url", "digest"}
    for json_path, node, _ in walk_json(fixture):
        if not isinstance(node, dict) or not required.issubset(node):
            continue
        found += 1
        if node["canonical_encoding"] != "canonical_json":
            continue
        canonical_bytes = canonical_json(node["value"]).encode("utf-8")
        encoded = base64.urlsafe_b64encode(canonical_bytes).rstrip(b"=").decode("ascii")
        digest = "sha256:" + hashlib.sha256(canonical_bytes).hexdigest()
        if node["canonical_bytes_base64url"] != encoded:
            lint.fail(
                fixture_path,
                f"{json_path}.canonical_bytes_base64url does not encode canonical JSON of value",
            )
        if node["digest"] != digest:
            lint.fail(
                fixture_path,
                f"{json_path}.digest={node['digest']} but canonical JSON of value hashes to {digest}",
            )
    if found == 0:
        lint.fail(
            fixture_path,
            "schema fixture must retain a CanonicalPublicMaterial structural case",
        )


def check_stated_preimage_matches_stated_digest(lint: Lint) -> None:
    """Every fixture that spells out a preimage MUST hash to the digest beside it.

    These pairs are the whole point of a KAT: an implementor reads the preimage,
    hashes it and compares. When an id inside the preimage changes and the digest
    beside it does not, the vector still *looks* authoritative while pinning a
    value nothing can produce — which is exactly how the v1 id-form change left
    stale `expected_subject` / `batch_tag` values behind.

    Checking the two pairs that were caught by hand only made *those two* pairs
    unreachable. The recurring failure is a fixture family nobody thought to add,
    so this check has two halves:

    * every registered `(preimage, digest)` pair must agree wherever both keys
      sit in one node — the same rule extended from 2 to 8 families, including
      the two Event-digest families (`canonical_event_payload`,
      `digest_preimage_canonical_bytes_utf8`) where a vector once hashed the
      envelope instead of the preimage; and
    * every key that *states* canonical preimage bytes must be registered,
      either as a pair source or as a documented unpaired key. A new fixture
      family cannot arrive with an unchecked preimage.
    """

    def walk(node: Any, fixture_path: Path, placeholder_digests: bool) -> None:
        if isinstance(node, dict):
            components = node.get("components_array")
            if isinstance(components, list) and isinstance(node.get("expected_subject"), str):
                recomputed = sha256_base64url_text(canonical_json(components))
                if recomputed != node["expected_subject"]:
                    lint.fail(
                        fixture_path,
                        f"'expected_subject'={node['expected_subject']} but "
                        f"'components_array' hashes to {recomputed}",
                    )
            for key, value in node.items():
                if not isinstance(value, str) or not STATED_PREIMAGE_KEY_RE.search(key):
                    continue
                registered = key in UNPAIRED_STATED_PREIMAGE_KEYS or any(
                    key == source for source, *_ in STATED_PREIMAGE_DIGEST_PAIRS
                )
                if not registered:
                    lint.fail(
                        fixture_path,
                        f"{key!r} states canonical preimage bytes but is not registered: add it to "
                        "STATED_PREIMAGE_DIGEST_PAIRS with the digest it must hash to, or to "
                        "UNPAIRED_STATED_PREIMAGE_KEYS with the reason no digest can check it",
                    )
            if not placeholder_digests:
                for source_key, digest_key, decoding, encoding, prefix in (
                    STATED_PREIMAGE_DIGEST_PAIRS
                ):
                    source = node.get(source_key)
                    digest = node.get(digest_key)
                    if not isinstance(source, str) or not isinstance(digest, str):
                        continue
                    data = _stated_preimage_bytes(source, decoding)
                    if data is None:
                        lint.fail(
                            fixture_path,
                            f"{source_key!r} is not decodable as {decoding}",
                        )
                        continue
                    declared_prefix = node.get("domain_separator_utf8")
                    effective_prefix = (
                        declared_prefix
                        if not prefix and isinstance(declared_prefix, str)
                        else prefix
                    )
                    recomputed = _stated_digest(effective_prefix.encode("utf-8") + data, encoding)
                    if recomputed != digest:
                        domain = f" under {effective_prefix!r}" if effective_prefix else ""
                        lint.fail(
                            fixture_path,
                            f"{digest_key!r}={digest} but {source_key!r} hashes{domain} to "
                            f"{recomputed}: the stated preimage and the stated digest disagree",
                        )
            for value in node.values():
                walk(value, fixture_path, placeholder_digests)
        elif isinstance(node, list):
            for value in node:
                walk(value, fixture_path, placeholder_digests)

    for fixture_path in sorted((ARTIFACTS / "fixtures").glob("*.json")):
        fixture = load_json(lint, fixture_path)
        if fixture is not None:
            walk(fixture, fixture_path, fixture_path.name in PLACEHOLDER_DIGEST_FIXTURES)


EVENT_PREIMAGE_RELAXED_ENVELOPE_MEMBERS = ("event_id", "proofs", "unsigned")

EVENT_PREIMAGE_ENVELOPE_SCHEMA_ID = (
    "https://arkret.org/v1/schemas/event-envelope-preimage.internal.json"
)


def _event_preimage_envelope_validator(lint: Lint) -> Any:
    """event-envelope.schema.json with exactly the §5 preimage omissions relaxed.

    zh/conformance/encoding.md §5 and §6.0.2(a) define the Event digest preimage
    as the signed Event body: the envelope with `event_id`, `proofs` and
    `unsigned` deleted. Nothing else about the envelope is relaxed, so a stated
    preimage stays subject to every closed-schema rule the wire Event obeys.
    """
    if Draft202012Validator is None or Registry is None or Resource is None:
        return None
    schema_path = ARTIFACTS / "schemas" / "event-envelope.schema.json"
    document = load_json(lint, schema_path)
    if not isinstance(document, dict):
        return None
    required = document.get("required")
    if not isinstance(required, list) or not {"event_id", "proofs"} <= set(required):
        lint.fail(
            schema_path,
            "the Event envelope must still require event_id and proofs; the preimage "
            "gate relaxes exactly those members and would otherwise relax nothing",
        )
        return None
    relaxed = copy.deepcopy(document)
    relaxed["required"] = [
        member
        for member in required
        if member not in EVENT_PREIMAGE_RELAXED_ENVELOPE_MEMBERS
    ]
    relaxed["$id"] = EVENT_PREIMAGE_ENVELOPE_SCHEMA_ID

    def retrieve(uri: str) -> Any:
        return Resource.from_contents(load_json_schema_for_uri(uri))

    registry = Registry(retrieve=retrieve).with_resource(
        EVENT_PREIMAGE_ENVELOPE_SCHEMA_ID,
        Resource.from_contents(relaxed),
    )
    return Draft202012Validator(
        relaxed,
        registry=registry,
        format_checker=schema_format_checker(),
    )


def check_stated_event_preimage_is_a_valid_event(lint: Lint) -> None:
    """A stated Event preimage MUST be an Event the closed schemas accept.

    `check_stated_preimage_matches_stated_digest` proves the bytes hash to the
    digest beside them. That is only half a known-answer vector: it says nothing
    about whether the bytes are an Event anyone could ever submit. The other
    half went unchecked, and every preimage in the content-bound Event-ID family
    drifted through the hole at once — a bare `ak:did_core:` string where the
    envelope requires the composite `actor_id`, an empty `refs` array the
    envelope forbids, a materialized `ak.schema.realm.v1` object standing in for
    a realm genesis, `schema_refs` on a closed genesis schema that has no such
    member, and an `agent_id` in DID form where the payload requires a
    `did_core_id`. Each digest agreed with its preimage throughout, so the whole
    family read as green while pinning Events that are unconstructible.

    Both halves run here: the envelope under the §5 preimage relaxation, and the
    payload under the `payload_schema_ref` the contract registry binds to that
    kind. Negative material lives under the registered `rejected_form` path
    segments and is skipped, because those preimages are meant to be invalid.
    """
    validator = _event_preimage_envelope_validator(lint)
    if validator is None:
        return
    registry_path = ARTIFACTS / "registry" / "contract-registry.json"
    contract = load_json(lint, registry_path)
    payload_refs: dict[str, str] = {}
    rows = (
        contract.get("event_kind_registry", {}).get("event_kinds")
        if isinstance(contract, dict)
        else None
    )
    for row in rows if isinstance(rows, list) else ():
        if not isinstance(row, dict):
            continue
        kind = row.get("event_kind")
        ref = row.get("payload_schema_ref")
        if isinstance(kind, str) and isinstance(ref, str) and ref:
            payload_refs[kind] = ref

    checked = 0
    for fixture_path in sorted((ARTIFACTS / "fixtures").glob("*.json")):
        fixture = load_json(lint, fixture_path)
        if fixture is None:
            continue
        for json_path, node, key in walk_json(fixture):
            if not isinstance(node, str) or not isinstance(key, str):
                continue
            if not STATED_PREIMAGE_KEY_RE.search(key):
                continue
            if any(
                segment in json_path for segment in NEGATIVE_TOKEN_PATH_SEGMENTS
            ):
                continue
            try:
                envelope = json.loads(node)
            except json.JSONDecodeError:
                continue
            if not isinstance(envelope, dict):
                continue
            kind = envelope.get("kind")
            if not isinstance(kind, str) or not kind.startswith("ak."):
                continue
            if not isinstance(envelope.get("payload"), dict):
                continue
            checked += 1
            errors = sorted(
                validator.iter_errors(envelope), key=lambda error: list(error.path)
            )
            if errors:
                detail = "; ".join(
                    ".".join(["$", *(str(bit) for bit in error.path)])
                    + ": "
                    + textwrap.shorten(error.message, width=200, placeholder=" ...")
                    for error in errors[:3]
                )
                lint.fail(
                    fixture_path,
                    f"{json_path} states an Event preimage that the Event envelope "
                    f"rejects: {detail}",
                )
            payload_ref = payload_refs.get(kind)
            if payload_ref is None:
                lint.fail(
                    fixture_path,
                    f"{json_path} states a preimage for {kind}, which the contract "
                    "registry binds to no payload_schema_ref",
                )
                continue
            check_json_instance_against_schema(
                lint,
                fixture_path,
                f"{json_path}.payload",
                payload_ref,
                envelope["payload"],
            )
    if checked == 0:
        lint.fail(
            registry_path,
            "no fixture states an Event digest preimage any more; the content-bound "
            "Event-ID family must keep its constructibility vectors",
        )


def check_event_batch_receipt_normalization_vector(lint: Lint) -> None:
    fixture_path = ARTIFACTS / "fixtures" / "encoding-fixture.json"
    fixture = load_json(lint, fixture_path)
    if not isinstance(fixture, dict):
        return
    vector = next(
        (
            item
            for item in fixture.get("vectors", [])
            if isinstance(item, dict)
            and item.get("vector_id") == "ak.vector.encoding.event_batch_receipt_digest.v1"
        ),
        None,
    )
    if not isinstance(vector, dict):
        lint.fail(fixture_path, "missing Event Batch Receipt digest vector")
        return
    receipt = vector.get("input")
    expected_digest = vector.get("expected_digest")
    if not isinstance(receipt, dict) or not isinstance(expected_digest, str):
        lint.fail(fixture_path, "Event Batch Receipt vector must declare input and expected_digest")
        return

    def normalize_events(events: Any) -> list[Any] | None:
        if not isinstance(events, list) or not events:
            return None
        by_key: dict[bytes, Any] = {}
        for event in events:
            key = canonical_json(event).encode("utf-8")
            by_key[key] = event
        return [by_key[key] for key in sorted(by_key)]

    baseline_events = receipt.get("events")
    normalized_baseline = normalize_events(baseline_events)
    if normalized_baseline is None or baseline_events != normalized_baseline:
        lint.fail(fixture_path, "Event Batch Receipt vector events must already be canonical and unique")

    cases = vector.get("normalization_cases")
    if not isinstance(cases, list) or len(cases) < 3:
        lint.fail(fixture_path, "Event Batch Receipt vector must cover normalize, unsorted, and duplicate cases")
        return
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            lint.fail(fixture_path, f"normalization_cases[{index}] must be an object")
            continue
        if "input_events" in case:
            normalized = normalize_events(case.get("input_events"))
            if normalized != case.get("expected_events"):
                lint.fail(fixture_path, f"normalization_cases[{index}] expected_events mismatch")
                continue
            normalized_receipt = copy.deepcopy(receipt)
            normalized_receipt["events"] = normalized
            normalized_digest = sha256_text(canonical_json(normalized_receipt))
            if normalized_digest != case.get("expected_digest") or normalized_digest != expected_digest:
                lint.fail(fixture_path, f"normalization_cases[{index}] digest mismatch")
        if "wire_events" in case:
            wire_events = case.get("wire_events")
            if normalize_events(wire_events) == wire_events:
                lint.fail(fixture_path, f"normalization_cases[{index}] negative wire is canonical")
            if case.get("expected") != "schema_violation_before_digest_verification":
                lint.fail(fixture_path, f"normalization_cases[{index}] must reject before digest verification")

    schema_path = ARTIFACTS / "schemas" / "event-batch-receipt.schema.json"
    schema = load_json(lint, schema_path)
    events_schema = schema.get("properties", {}).get("events", {}) if isinstance(schema, dict) else {}
    if events_schema.get("uniqueItems") is not True:
        lint.fail(schema_path, "Event Batch Receipt events must set uniqueItems=true")


def check_encrypted_envelope_digest_vector(lint: Lint) -> None:
    fixture_path = ARTIFACTS / "fixtures" / "encoding-fixture.json"
    fixture = load_json(lint, fixture_path)
    if not isinstance(fixture, dict):
        return
    vector = next(
        (
            item
            for item in fixture.get("vectors", [])
            if isinstance(item, dict)
            and item.get("vector_id") == "ak.vector.encoding.encrypted_envelope_digest.v1"
        ),
        None,
    )
    if not isinstance(vector, dict):
        lint.fail(fixture_path, "missing Encrypted Envelope digest vector")
        return

    metadata = vector.get("payload_metadata")
    if not isinstance(metadata, dict):
        lint.fail(fixture_path, "Encrypted Envelope vector must declare payload_metadata")
        return
    if set(metadata) != {"version", "content_type", "encryption_context"}:
        lint.fail(fixture_path, "Encrypted Envelope payload_metadata must be the minimal wire projection")
    context = metadata.get("encryption_context")
    if not isinstance(context, dict) or set(context) != {"epoch", "group_state_ref"}:
        lint.fail(fixture_path, "Encrypted Envelope standard MLS context must omit duplicated AAD inputs and counter")
    canonical_metadata = canonical_json(metadata)
    if vector.get("expected_metadata_canonical_bytes_utf8") != canonical_metadata:
        lint.fail(fixture_path, "Encrypted Envelope canonical payload_metadata bytes mismatch")
    ciphertext_base64url = vector.get("ciphertext_base64url")
    if not isinstance(ciphertext_base64url, str):
        lint.fail(fixture_path, "Encrypted Envelope ciphertext_base64url must be a string")
        return
    try:
        padded = ciphertext_base64url + "=" * (-len(ciphertext_base64url) % 4)
        ciphertext = base64.urlsafe_b64decode(padded)
    except (ValueError, base64.binascii.Error):
        lint.fail(fixture_path, "Encrypted Envelope ciphertext_base64url is invalid")
        return
    expected_digest = "sha256:" + hashlib.sha256(canonical_metadata.encode("utf-8") + ciphertext).hexdigest()
    if vector.get("expected_digest") != expected_digest:
        lint.fail(fixture_path, "Encrypted Envelope expected_digest mismatch")


def check_one_of_branch_discriminability(lint: Lint) -> None:
    """Every object-union `oneOf` must have a decidable branch.

    ``oneOf`` means "exactly one branch matches". When the branches are objects
    that overlap, a single instance can satisfy two of them and the whole union
    fails, and a statically typed decoder has no principled way to choose. A
    union is decidable when one of these holds:

      * a discriminator: one required property carries a distinct single value
        (``const`` or a one-entry ``enum``) in every branch;
      * structural exclusivity: for every pair of branches, one side is closed
        and the other requires a property that side does not declare, the two
        pin a shared required property to different constants, or one side
        explicitly refuses a property the other requires.

    Two shapes are deliberately out of scope. A document-level ``oneOf`` is a
    catalog of DTOs whose consumers bind a fragment, not a runtime union. A
    constraint-style ``oneOf`` whose branches declare no ``required`` and no
    ``$ref`` expresses legal field combinations of one object, and its
    discriminator lives on the enclosing schema.
    """

    documents = {
        path.name: load_json(lint, path)
        for path in sorted((ARTIFACTS / "schemas").glob("*.json"))
    }

    def resolve_pointer(document: Any, pointer: str) -> Any:
        node = document
        for part in pointer.lstrip("#/").split("/"):
            if not part:
                continue
            part = part.replace("~1", "/").replace("~0", "~")
            if isinstance(node, dict) and part in node:
                node = node[part]
            elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
                node = node[int(part)]
            else:
                return None
        return node

    def deref(node: Any, current: str, depth: int = 0) -> Any:
        if depth > 8 or not isinstance(node, dict) or "$ref" not in node:
            return node
        reference = node["$ref"]
        if reference.startswith("#"):
            return deref(resolve_pointer(documents[current], reference), current, depth + 1)
        match = ONE_OF_REFERENCE_RE.match(reference)
        if not match or match.group(1) not in documents:
            return None
        target = documents[match.group(1)]
        return deref(resolve_pointer(target, match.group(2) or "#"), match.group(1), depth + 1)

    def single_valued(node: Any) -> str | None:
        if not isinstance(node, dict):
            return None
        if "const" in node:
            return json.dumps(node["const"], sort_keys=True)
        enum = node.get("enum")
        if isinstance(enum, list) and len(enum) == 1:
            return json.dumps(enum[0], sort_keys=True)
        return None

    def discriminator(branches: list[dict[str, Any]], outer_required: set[str]) -> str | None:
        candidates: set[str] | None = None
        for branch in branches:
            required = set(branch.get("required", [])) | outer_required
            properties = branch.get("properties") or {}
            names = {name for name in required if single_valued(properties.get(name))}
            candidates = names if candidates is None else candidates & names
        for name in sorted(candidates or ()):
            values = [single_valued((branch.get("properties") or {})[name]) for branch in branches]
            if len(set(values)) == len(values):
                return name
        return None

    def closed(node: dict[str, Any]) -> bool:
        return node.get("additionalProperties") is False or node.get("unevaluatedProperties") is False

    def forbidden(node: dict[str, Any]) -> set[str]:
        names: set[str] = set()
        negated = node.get("not")
        if isinstance(negated, dict):
            names.update(name for name in negated.get("required", []) if isinstance(name, str))
            for branch in negated.get("anyOf", []) or []:
                if isinstance(branch, dict):
                    names.update(n for n in branch.get("required", []) if isinstance(n, str))
        return names

    def exclusive(left: dict[str, Any], right: dict[str, Any]) -> bool:
        left_required = set(left.get("required", []))
        right_required = set(right.get("required", []))
        if forbidden(left) & right_required or forbidden(right) & left_required:
            return True
        if closed(right) and left_required - set((right.get("properties") or {}).keys()):
            return True
        if closed(left) and right_required - set((left.get("properties") or {}).keys()):
            return True
        for name in left_required & right_required:
            left_value = single_valued((left.get("properties") or {}).get(name))
            right_value = single_valued((right.get("properties") or {}).get(name))
            if left_value and right_value and left_value != right_value:
                return True
        return False

    def required_nested_separation(left: Any, right: Any, left_doc: str, right_doc: str, depth: int = 0) -> bool:
        """Prove disjointness through required object properties; never guess on optional paths."""
        if depth > 12:
            return False
        def resolve_with_document(node: Any, document_name: str) -> tuple[Any, str]:
            for _ in range(9):
                if not isinstance(node, dict) or "$ref" not in node:
                    return node, document_name
                ref = node["$ref"]
                if ref.startswith("#"):
                    node = resolve_pointer(documents[document_name], ref)
                else:
                    match = ONE_OF_REFERENCE_RE.match(ref)
                    if not match or match.group(1) not in documents:
                        return None, document_name
                    document_name = match.group(1)
                    node = resolve_pointer(documents[document_name], match.group(2) or "#")
            return None, document_name
        left, left_doc = resolve_with_document(left, left_doc)
        right, right_doc = resolve_with_document(right, right_doc)
        if not isinstance(left, dict) or not isinstance(right, dict):
            return False
        left_value, right_value = single_valued(left), single_valued(right)
        if left_value is not None and right_value is not None:
            return left_value != right_value
        if left.get("type") != "object" or right.get("type") != "object":
            return False
        return any(
            required_nested_separation(
                left.get("properties", {}).get(name), right.get("properties", {}).get(name),
                left_doc, right_doc, depth + 1,
            )
            for name in set(left.get("required", [])) & set(right.get("required", []))
        )

    def sites(name: str, node: Any, pointer: str, out: list[tuple[str, list[Any], set[str]]]) -> None:
        if isinstance(node, dict):
            branches = node.get("oneOf")
            if isinstance(branches, list) and len(branches) > 1:
                out.append((pointer, branches, set(node.get("required", []))))
            for key, value in node.items():
                sites(name, value, f"{pointer}/{key}", out)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                sites(name, value, f"{pointer}/{index}", out)

    for document_name, document in documents.items():
        if not isinstance(document, dict):
            continue
        path = ARTIFACTS / "schemas" / document_name
        found: list[tuple[str, list[Any], set[str]]] = []
        sites(document_name, document, "", found)
        for pointer, branches, outer_required in found:
            if pointer == "":
                continue
            if all(
                isinstance(branch, dict) and not branch.get("required") and "$ref" not in branch
                for branch in branches
            ):
                continue
            resolved = [deref(branch, document_name) for branch in branches]
            if not all(isinstance(node, dict) for node in resolved):
                continue
            if not all(
                node.get("type") == "object" or "properties" in node for node in resolved
            ):
                continue
            if discriminator(resolved, outer_required):
                continue
            if all(
                exclusive(left, right) or required_nested_separation(
                    branches[index], branches[other_index], document_name, document_name
                )
                for index, left in enumerate(resolved)
                for other_index, right in enumerate(resolved[index + 1 :], index + 1)
            ):
                continue
            lint.fail(
                path,
                f"{pointer or '/'} oneOf object branches are not decidable: add a required "
                "single-valued discriminator, close a branch, or make the required sets exclusive",
            )


def check_view_write_contract_fixture(lint: Lint) -> None:
    """Run ak.vector.view.terminal_state_patch.v1 instead of describing it.

    The vector said two things: the terminal `state=tombstoned` patch MUST be
    accepted, and an actor-supplied `state_changed_at` MUST be rejected. Both
    were prose in a registry row with no fixture behind them, and the acceptance
    half was the load-bearing one -- `models/views.md` section 3.1 has no
    tombstone Event kind for a shared View, so that patch IS the removal path.
    Nothing ran, so nothing noticed that the patch could not even be registered:
    the registry consumer flattened every object's reducer-managed paths into
    one set, and `state` -- carved out for this exact write by the one
    `universal_exemptions` row in the file -- came back as a prohibition.

    Every case here is validated against the live schema, and the author-writable
    partition is recomputed from the live registry rather than compared to a
    copy, so the fixture cannot drift into being a second source of truth.
    """

    fixture_path = ARTIFACTS / "fixtures" / "view-write-contract-fixture.json"
    fixture = load_json(lint, fixture_path)
    if not isinstance(fixture, dict):
        return

    if fixture.get("covers_vectors") != ["ak.vector.view.terminal_state_patch.v1"]:
        lint.fail(
            fixture_path,
            "covers_vectors must be exactly ['ak.vector.view.terminal_state_patch.v1']",
        )

    partition = fixture.get("author_writable_partition")
    if not isinstance(partition, dict):
        lint.fail(fixture_path, "author_writable_partition must be an object")
        return

    author_writable = partition.get("author_writable")
    reducer_managed = partition.get("reducer_managed")
    if not isinstance(author_writable, list) or not isinstance(reducer_managed, list):
        lint.fail(fixture_path, "author_writable and reducer_managed must both be arrays")
        return
    author_set = set(author_writable)
    managed_set = set(reducer_managed)

    view_schema = load_json(lint, ARTIFACTS / "schemas" / "view.schema.json")
    declared = set(view_schema.get("properties") or {}) if isinstance(view_schema, dict) else set()
    if not declared:
        lint.fail(fixture_path, "view.schema.json declares no properties to partition")
        return
    if author_set | managed_set != declared:
        lint.fail(
            fixture_path,
            "author_writable + reducer_managed must partition every member view.schema.json declares; "
            f"unclassified {sorted(declared - author_set - managed_set)}, "
            f"undeclared {sorted((author_set | managed_set) - declared)}",
        )
    overlap = sorted(author_set & managed_set)
    if overlap:
        lint.fail(fixture_path, f"{overlap} are listed as both author-writable and reducer-managed")

    registry = load_json(lint, ARTIFACTS / "registry" / "event-kind-registry.json")
    rows = registry.get("event_kinds") if isinstance(registry, dict) else None
    registered_paths: set[str] | None = None
    for row in rows or []:
        if not isinstance(row, dict) or row.get("event_kind") != partition.get("event_kind"):
            continue
        for write in row.get("result_writes") or []:
            projection = write.get("result_projection") if isinstance(write, dict) else None
            if isinstance(projection, dict) and projection.get("kind") == "apply_patch":
                registered_paths = {
                    item for item in projection.get("allowed_paths") or [] if isinstance(item, str)
                }
    if registered_paths is None:
        lint.fail(
            fixture_path,
            f"{partition.get('event_kind')!r} registers no apply_patch write, so the author-writable "
            "partition has nothing to be the complement of",
        )
    elif registered_paths != author_set:
        lint.fail(
            fixture_path,
            f"author_writable disagrees with the registered allowed_paths of "
            f"{partition.get('event_kind')!r}: only in fixture {sorted(author_set - registered_paths)}, "
            f"only in registry {sorted(registered_paths - author_set)}",
        )

    cases = fixture.get("cases")
    if not isinstance(cases, list) or not cases:
        lint.fail(fixture_path, "cases must be a non-empty array")
        return
    seen: set[str] = set()
    accepted_terminal = False
    for index, case in enumerate(cases):
        label = f"cases[{index}]"
        if not isinstance(case, dict):
            lint.fail(fixture_path, f"{label} must be an object")
            continue
        name = case.get("name")
        if not isinstance(name, str) or not name:
            lint.fail(fixture_path, f"{label}.name must be a non-empty string")
            continue
        if name in seen:
            lint.fail(fixture_path, f"{label}.name duplicates {name}")
        seen.add(name)
        schema_ref = case.get("schema_ref")
        if not isinstance(schema_ref, str) or not schema_ref:
            lint.fail(fixture_path, f"{label}.schema_ref must name the schema this case is run against")
            continue
        if not isinstance(case.get("valid"), bool):
            lint.fail(fixture_path, f"{label}.valid must be a boolean")
            continue
        if not isinstance(case.get("why"), str) or not case["why"].strip():
            # A negative case whose reason is not written down decays into a
            # shape nobody can re-derive when the schema changes under it.
            lint.fail(fixture_path, f"{label}.why must say what the case proves")
        check_json_instance_against_schema(
            lint,
            fixture_path,
            f"{label} ({name})",
            schema_ref,
            case.get("instance"),
            expect_valid=case["valid"],
        )
        if name == "terminal_state_patch_is_accepted" and case["valid"]:
            accepted_terminal = True
        if case["valid"] and schema_ref.endswith("view_value"):
            # common-fields.md section 3 pins created_at <= state_changed_at
            # <= updated_at, and JSON Schema has no keyword that can express an
            # ordering between two members. One accepted Event produces both
            # the transition time and the update time, so a materialized value
            # whose state_changed_at runs ahead of its updated_at describes a
            # write no reducer performed -- and every schema-shaped gate in the
            # pipeline calls it valid.
            _check_view_value_timestamps(lint, fixture_path, f"{label} ({name})", case.get("instance"))
        if case["valid"] and schema_ref.endswith("view_update_payload"):
            # A patch map's KEYS are its paths (patch.schema.json, and
            # event-and-patch.md section 4.2.1). Nothing in that grammar
            # distinguishes a member name from any other legal identifier, so
            # the shape `{"set": {"state": "tombstoned"}}` validates -- as a
            # patch that sets a member literally named `set`. It is neither a
            # member view.schema.json declares nor one of the registered
            # allowed_paths, so a fixture written that way would assert
            # "the removal patch is accepted" while carrying a patch that the
            # reducer must refuse.
            for path in (case.get("instance") or {}).get("patch") or {}:
                if not isinstance(path, str):
                    continue
                head = path.split(".", 1)[0]
                if head not in author_set:
                    lint.fail(
                        fixture_path,
                        f"{label} ({name}) is an accepted case whose patch addresses {path!r}, which is "
                        f"not author-writable on this object; a patch map's keys ARE its paths",
                    )
    if not accepted_terminal:
        lint.fail(
            fixture_path,
            "the fixture must keep an accepted terminal-state patch case: that acceptance IS the shared "
            "View removal path, and it is the half a rejection-only fixture would silently drop",
        )

    _check_view_admission_cases(lint, fixture_path, fixture, author_set)


def _check_view_value_timestamps(lint: Lint, fixture_path: Path, label: str, value: object) -> None:
    """created_at <= state_changed_at <= updated_at, on a materialized View."""

    if not isinstance(value, dict):
        return
    created_at = value.get("created_at")
    updated_at = value.get("updated_at")
    state_changed_at = value.get("state_changed_at")
    if isinstance(created_at, str) and isinstance(updated_at, str) and updated_at < created_at:
        lint.fail(fixture_path, f"{label} has updated_at earlier than created_at")
    if not isinstance(state_changed_at, str):
        return
    if isinstance(created_at, str) and state_changed_at < created_at:
        lint.fail(fixture_path, f"{label} has state_changed_at earlier than created_at")
    if isinstance(updated_at, str) and state_changed_at > updated_at:
        lint.fail(
            fixture_path,
            f"{label} has state_changed_at later than updated_at: the same accepted Event produces "
            "both, so the transition cannot postdate the write that carried it",
        )


def _check_view_admission_cases(
    lint: Lint, fixture_path: Path, fixture: dict, author_set: set[str]
) -> None:
    """The behavioral face: outcomes schema validation cannot express.

    ``cases[]`` can prove that the terminal patch has a legal shape. It cannot
    prove that the transition is admitted, that a later edit of a tombstoned
    View is refused, that a stale pre-state guard does not quietly resolve
    against an older matching value, or that a refusal leaves nothing behind.
    Those are the acceptance items of the vector, and each one names the
    registered error and reason code it MUST fail with, so a refusal cannot
    drift into a different, vaguer code without this gate noticing.
    """

    admission_cases = fixture.get("admission_cases")
    if not isinstance(admission_cases, list) or not admission_cases:
        lint.fail(fixture_path, "admission_cases must be a non-empty array")
        return

    errors = load_json(lint, ARTIFACTS / "registry" / "error-code-registry.json")
    registered_codes = {
        row.get("code")
        for row in (errors.get("codes") or [])
        if isinstance(row, dict)
    }
    registered_reasons = {
        row.get("code")
        for row in (errors.get("reason_codes") or [])
        if isinstance(row, dict)
    }
    kinds = load_json(lint, ARTIFACTS / "registry" / "event-kind-registry.json")
    registered_kinds = {
        row.get("event_kind")
        for row in (kinds.get("event_kinds") or [])
        if isinstance(row, dict)
    }

    seen: set[str] = set()
    required = {
        "legal_active_to_tombstoned_is_admitted",
        "author_supplied_state_changed_at_is_refused",
        "an_update_after_the_terminal_transition_is_refused",
        "a_stale_prestate_guard_fails_without_selecting_a_historical_candidate",
        "an_exact_retry_of_an_accepted_update_produces_no_second_effect",
    }
    for index, case in enumerate(admission_cases):
        label = f"admission_cases[{index}]"
        if not isinstance(case, dict):
            lint.fail(fixture_path, f"{label} must be an object")
            continue
        name = case.get("name")
        if not isinstance(name, str) or not name:
            lint.fail(fixture_path, f"{label}.name must be a non-empty string")
            continue
        if name in seen:
            lint.fail(fixture_path, f"{label}.name duplicates {name}")
        seen.add(name)
        if not isinstance(case.get("why"), str) or not case["why"].strip():
            lint.fail(fixture_path, f"{label} ({name}).why must say what the case proves")
        event_kind = case.get("event_kind")
        if event_kind not in registered_kinds:
            lint.fail(
                fixture_path,
                f"{label} ({name}).event_kind {event_kind!r} is not a registered Event kind",
            )
        if not isinstance(case.get("given"), dict):
            lint.fail(fixture_path, f"{label} ({name}).given must state the pre-state it runs against")
        payload = case.get("payload")
        if not isinstance(payload, dict):
            lint.fail(fixture_path, f"{label} ({name}).payload must be an object")
            payload = {}
        expected = case.get("expected")
        if not isinstance(expected, dict):
            lint.fail(fixture_path, f"{label} ({name}).expected must be an object")
            continue
        result = expected.get("outcome")
        if result not in ("admitted", "refused"):
            lint.fail(
                fixture_path,
                f"{label} ({name}).expected.outcome must be 'admitted' or 'refused'",
            )
            continue

        error = expected.get("error")
        reason_code = expected.get("reason_code")
        if result == "refused":
            if error not in registered_codes:
                lint.fail(
                    fixture_path,
                    f"{label} ({name}) is a refusal, so expected.error must be a registered error code; "
                    f"got {error!r}",
                )
            if reason_code is not None and reason_code not in registered_reasons:
                # A reason code is optional -- some refusals are fully described
                # by the generic code -- but an unregistered spelling is a
                # second vocabulary, which is the thing the registry exists to
                # prevent.
                lint.fail(
                    fixture_path,
                    f"{label} ({name}).expected.reason_code {reason_code!r} is not registered in "
                    "error-code-registry.json",
                )
            if expected.get("stored_effect") not in (None, "none"):
                lint.fail(
                    fixture_path,
                    f"{label} ({name}) is a refusal, so it MUST NOT declare a stored effect",
                )
        else:
            if error is not None or reason_code is not None:
                lint.fail(
                    fixture_path,
                    f"{label} ({name}) is admitted, so it MUST NOT carry an error or reason code",
                )

        patch = payload.get("patch")
        if isinstance(patch, dict) and result == "admitted":
            for path in patch:
                if isinstance(path, str) and path.split(".", 1)[0] not in author_set:
                    lint.fail(
                        fixture_path,
                        f"{label} ({name}) is admitted but patches {path!r}, which is not author-writable",
                    )

    missing = sorted(required - seen)
    if missing:
        lint.fail(
            fixture_path,
            "admission_cases must keep the acceptance items of "
            f"ak.vector.view.terminal_state_patch.v1; missing {missing}",
        )


def check_string_profile_format_vectors(lint: Lint) -> None:
    """The custom string formats must keep one executable vector set.

    ``string-profiles.schema.json`` declares eight ``arkret-*`` formats whose
    normative semantics (PRECIS, UTS #46, NFC) cannot be expressed by the
    coarse JSON Schema pattern and length keywords. This check binds the
    fixture to the schema so every format keeps positive and negative vectors,
    and it proves the declared rejection layer of each negative value: a
    ``schema_pattern`` value must already fail the coarse shape, while a
    ``profile_validator`` value must pass it, which is exactly why a runtime
    that only validates JSON Schema is insufficient.
    """

    schema_path = ARTIFACTS / "schemas" / "string-profiles.schema.json"
    fixture_path = ARTIFACTS / "fixtures" / "string-profile-fixture.json"
    schema = load_json(lint, schema_path)
    fixture = load_json(lint, fixture_path)
    if not isinstance(schema, dict) or not isinstance(fixture, dict):
        return
    if Draft202012Validator is None:
        return

    defs = schema.get("$defs")
    if not isinstance(defs, dict):
        lint.fail(schema_path, "string profiles schema must declare $defs")
        return
    declared_formats = {
        node["format"]: f"schemas/string-profiles.schema.json#/$defs/{name}"
        for name, node in defs.items()
        if isinstance(node, dict) and isinstance(node.get("format"), str)
    }

    vectors = fixture.get("vectors")
    if not isinstance(vectors, list) or not vectors:
        lint.fail(fixture_path, "string profile fixture must declare a non-empty vectors list")
        return

    covered: dict[str, str] = {}
    for index, vector in enumerate(vectors):
        label = f"vectors[{index}]"
        if not isinstance(vector, dict):
            lint.fail(fixture_path, f"{label} must be an object")
            continue
        format_name = vector.get("format")
        schema_ref = vector.get("schema_ref")
        if not isinstance(format_name, str) or format_name not in declared_formats:
            lint.fail(fixture_path, f"{label}.format is not declared by string-profiles.schema.json")
            continue
        if format_name in covered:
            lint.fail(fixture_path, f"{label}.format duplicates {format_name}")
            continue
        covered[format_name] = schema_ref if isinstance(schema_ref, str) else ""
        if schema_ref != declared_formats[format_name]:
            lint.fail(
                fixture_path,
                f"{label}.schema_ref must be {declared_formats[format_name]} for {format_name}",
            )
            continue

        definition = dict(defs[schema_ref.rsplit("/", 1)[-1]])
        definition.pop("format", None)
        definition["$defs"] = defs
        validator = Draft202012Validator(definition)

        accepted = vector.get("accepted")
        if not isinstance(accepted, list) or not accepted:
            lint.fail(fixture_path, f"{label}.accepted must be a non-empty list")
        else:
            for value in accepted:
                if not isinstance(value, str):
                    lint.fail(fixture_path, f"{label}.accepted values must be strings")
                elif not validator.is_valid(value):
                    lint.fail(
                        fixture_path,
                        f"{label}.accepted value fails the coarse {format_name} shape: {value!r}",
                    )
                elif unicodedata.normalize("NFC", value) != value:
                    lint.fail(
                        fixture_path,
                        f"{label}.accepted value is not NFC: {value!r}",
                    )

        rejected = vector.get("rejected")
        if not isinstance(rejected, list) or not rejected:
            lint.fail(fixture_path, f"{label}.rejected must be a non-empty list")
            continue
        profile_only = 0
        for position, case in enumerate(rejected):
            case_label = f"{label}.rejected[{position}]"
            if not isinstance(case, dict):
                lint.fail(fixture_path, f"{case_label} must be an object")
                continue
            value = case.get("value")
            layer = case.get("rejected_by")
            if not isinstance(value, str):
                lint.fail(fixture_path, f"{case_label}.value must be a string")
                continue
            if not isinstance(case.get("reason"), str) or not case.get("reason"):
                lint.fail(fixture_path, f"{case_label}.reason must be a non-empty string")
            if layer not in {"schema_pattern", "profile_validator"}:
                lint.fail(fixture_path, f"{case_label}.rejected_by must be schema_pattern or profile_validator")
                continue
            accepted_by_shape = validator.is_valid(value)
            if layer == "schema_pattern" and accepted_by_shape:
                lint.fail(
                    fixture_path,
                    f"{case_label} claims schema_pattern but the coarse shape accepts it: {value!r}",
                )
            if layer == "profile_validator":
                profile_only += 1
                if not accepted_by_shape:
                    lint.fail(
                        fixture_path,
                        f"{case_label} claims profile_validator but the coarse shape already rejects it: {value!r}",
                    )
        if profile_only == 0:
            lint.fail(
                fixture_path,
                f"{label} must carry at least one profile_validator-only negative for {format_name}",
            )

    for format_name in sorted(set(declared_formats) - set(covered)):
        lint.fail(fixture_path, f"custom format has no vector: {format_name}")


def check_declared_canonical_json_strings(lint: Lint) -> None:
    """A fixture field named `*_canonical_json` MUST actually be canonical.

    RFC 8785 canonical JSON sorts object keys. A fixture that stores an
    unsorted string under a `_canonical_json` name is self-contradictory: the
    vector stays internally consistent while disagreeing with every conforming
    implementation, and the mismatch only surfaces downstream. The
    `passphrase_kdf_kat` nonce transcript failed exactly this way, and every
    value derived from it had to be regenerated.
    """
    fixture_root = ARTIFACTS / "fixtures"
    for path in sorted(fixture_root.glob("*.json")):
        data = load_json(lint, path)
        if data is None:
            continue

        def walk(node: Any, pointer: str) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    child = f"{pointer}/{key}"
                    if key.endswith("_canonical_json") and isinstance(value, str):
                        try:
                            parsed = json.loads(value)
                        except json.JSONDecodeError:
                            lint.fail(path, f"{child} is not parseable JSON")
                            continue
                        if canonical_json(parsed) != value:
                            lint.fail(
                                path,
                                f"{child} is named canonical but is not RFC 8785 canonical "
                                "(object keys must be sorted, no insignificant whitespace)",
                            )
                    walk(value, child)
            elif isinstance(node, list):
                for index, value in enumerate(node):
                    walk(value, f"{pointer}/{index}")

        walk(data, "")


def websocket_canonical_wss_errors(value: object) -> list[str]:
    """Return profile-level canonicalization errors for a WebSocket base URL."""
    if not isinstance(value, str):
        return ["value is not a string"]
    errors: list[str] = []
    if len(value.encode("utf-8")) > 2048:
        errors.append("UTF-8 form exceeds 2048 bytes")
    if not value.isascii():
        errors.append("URI must use an ASCII DNS A-label host")
    try:
        parsed = urllib.parse.urlsplit(value)
    except ValueError as exc:
        return [f"URI cannot be parsed: {exc}"]
    if parsed.scheme != "wss" or not value.startswith("wss://"):
        errors.append("scheme must be lowercase wss")
    if parsed.query or parsed.fragment:
        errors.append("query and fragment are forbidden")
    if parsed.username is not None or parsed.password is not None or "@" in parsed.netloc:
        errors.append("userinfo is forbidden")
    authority = parsed.netloc.rsplit("@", 1)[-1]
    raw_host = authority.rsplit(":", 1)[0] if ":" in authority and not authority.startswith("[") else authority
    host = parsed.hostname
    if not host:
        errors.append("DNS host is required")
    else:
        if raw_host != raw_host.lower():
            errors.append("DNS host must be lowercase")
        if host.endswith("."):
            errors.append("DNS host trailing dot is forbidden")
        if ":" in host:
            errors.append("IP literals are not DNS A-label hosts")
        labels = host.split(".")
        if (
            any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels)
            or len(host) > 253
        ):
            errors.append("host is not a valid lowercase DNS A-label name")
    try:
        port = parsed.port
    except ValueError as exc:
        errors.append(f"port is invalid: {exc}")
        port = None
    if ":" in authority and not authority.startswith("["):
        port_text = authority.rsplit(":", 1)[1]
        if not re.fullmatch(r"[1-9][0-9]{0,4}", port_text):
            errors.append("explicit port must be non-zero decimal without leading zeros")
        if port == 443:
            errors.append("default port 443 must be omitted")
    if port is not None and not 1 <= port <= 65535:
        errors.append("port is outside 1..65535")
    path_value = parsed.path
    if not path_value or not path_value.startswith("/"):
        errors.append("non-empty absolute path is required")
    if any(segment in {".", ".."} for segment in path_value.split("/")):
        errors.append("dot segments are forbidden")
    unreserved = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")
    index = 0
    while index < len(path_value):
        if path_value[index] != "%":
            index += 1
            continue
        escape = path_value[index : index + 3]
        if not re.fullmatch(r"%[0-9A-F]{2}", escape):
            errors.append("percent escapes must be complete and use uppercase hexadecimal")
            index += 1
            continue
        if chr(int(escape[1:], 16)) in unreserved:
            errors.append("unreserved path characters must not be percent-encoded")
        index += 3
    return errors


def check_agent_requested_scope_commitment_digest(lint: Lint) -> None:
    """Recompute the Agent requested-scope commitment digest from its preimage.

    The digest is a create-locked commitment in public Agent DID history, so a
    frozen fixture value that drifts from the normative preimage would let a
    conforming controller and a fixture verifier derive different identities.
    Every occurrence in the fixture is recomputed here rather than trusted.
    """
    path = ARTIFACTS / "fixtures" / "agent-vectors-fixture.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return

    def commitment_digest(agent_id: str, controller_principal_id: str, requested_scope: Any) -> str:
        preimage = {
            "agent_id": agent_id,
            "controller_principal_id": controller_principal_id,
            "kind": "ak.agent.requested_scope_commitment.v1",
            "requested_scope": requested_scope,
        }
        return "sha256:" + hashlib.sha256(canonical_json(preimage).encode("utf-8")).hexdigest()

    cases = data.get("cases")
    if not isinstance(cases, list):
        lint.fail(path, "agent fixture must expose cases[]")
        return
    provision = next(
        (case for case in cases if isinstance(case, dict) and case.get("name") == "agent_provision"),
        None,
    )
    if not isinstance(provision, dict):
        lint.fail(path, "agent fixture omits the agent_provision case")
        return
    commitment = provision.get("requested_scope_commitment")
    if not isinstance(commitment, dict):
        lint.fail(path, "agent_provision omits requested_scope_commitment")
        return
    agent_id = commitment.get("agent_id")
    controller_principal_id = commitment.get("controller_principal_id")
    requested_scope = commitment.get("requested_scope")
    if not isinstance(agent_id, str) or not isinstance(controller_principal_id, str) or requested_scope is None:
        lint.fail(path, "requested_scope_commitment preimage is incomplete")
        return
    expected = commitment_digest(agent_id, controller_principal_id, requested_scope)
    if commitment.get("expected_digest") != expected:
        lint.fail(
            path,
            "requested_scope_commitment.expected_digest drifted from its preimage: "
            f"{commitment.get('expected_digest')!r} != {expected!r}",
        )
    endpoint = provision.get("public_did_service_endpoint")
    if isinstance(endpoint, dict) and endpoint.get("requested_scope_digest") != expected:
        lint.fail(
            path,
            "public_did_service_endpoint.requested_scope_digest must equal the recomputed commitment",
        )

    for case in data.get("schema_validation_cases", []):
        if not isinstance(case, dict):
            continue
        instance = case.get("instance")
        if not isinstance(instance, dict):
            continue
        stated = instance.get("requested_scope_digest")
        if not isinstance(stated, str):
            continue
        scope = instance.get("requested_scope")
        case_agent = instance.get("agent_id")
        case_controller = instance.get("controller_principal_id")
        if scope is None:
            # The instance carries only the commitment; it must reuse the case digest.
            if stated != expected:
                lint.fail(
                    path,
                    f"schema case {case.get('name')!r} pins a requested_scope_digest that no "
                    "preimage in this fixture produces",
                )
            continue
        if not isinstance(case_agent, str) or not isinstance(case_controller, str):
            lint.fail(
                path,
                f"schema case {case.get('name')!r} carries requested_scope without its commitment subjects",
            )
            continue
        case_expected = commitment_digest(case_agent, case_controller, scope)
        if stated != case_expected:
            lint.fail(
                path,
                f"schema case {case.get('name')!r} requested_scope_digest drifted from its own "
                f"requested_scope: {stated!r} != {case_expected!r}",
            )

    runtime_pairing = next(
        (
            case
            for case in cases
            if isinstance(case, dict) and case.get("name") == "agent_runtime_key_binding"
        ),
        None,
    )
    if not isinstance(runtime_pairing, dict):
        lint.fail(path, "agent fixture omits the agent_runtime_key_binding case")
        return
    possession = runtime_pairing.get("proof_of_possession")
    if not isinstance(possession, dict):
        lint.fail(path, "agent_runtime_key_binding omits proof_of_possession")
        return
    binding_json = runtime_pairing.get("canonical_pairing_request_binding_json")
    if not isinstance(binding_json, str):
        lint.fail(path, "agent_runtime_key_binding omits canonical_pairing_request_binding_json")
        return
    try:
        binding = json.loads(binding_json)
    except json.JSONDecodeError as exc:
        lint.fail(path, f"canonical_pairing_request_binding_json is invalid JSON: {exc}")
        return
    if canonical_json(binding) != binding_json:
        lint.fail(path, "canonical_pairing_request_binding_json is not RFC 8785 JCS")
    if binding.get("runtime_key_binding_digest") != possession.get("runtime_key_binding_digest"):
        lint.fail(path, "canonical approval must bind the frozen candidate digest")
    if "proof_of_possession_digest" in binding or "pairing_code" in binding:
        lint.fail(path, "canonical approval must exclude replaceable PoP and private secret")
    binding_digest = sha256_text(binding_json)
    if runtime_pairing.get("expected_pairing_request_binding_digest") != binding_digest:
        lint.fail(
            path,
            "agent_runtime_key_binding.expected_pairing_request_binding_digest drifted "
            "from its canonical binding bytes",
        )


def check_websocket_bundle_closure_cases(lint: Lint, path: Path, data: dict[str, Any]) -> None:
    """Execute the ServiceDescribe-level operation reachability cases.

    Operation reachability is owned by `supported_operation_bundles`, not by the
    transport descriptor, so these cases mutate a full ServiceDescribe instead of
    the closed websocket binding object. Every declared mutation must name a
    carrier that actually exists in the base instance; a mutation that cannot be
    materialised is a fixture failure, never a silently skipped case.
    """
    cases = data.get("bundle_closure_cases")
    if not isinstance(cases, list) or not cases:
        lint.fail(path, "bundle_closure_cases must be a non-empty array")
        return
    by_name = {
        case.get("name"): case
        for case in cases
        if isinstance(case, dict) and isinstance(case.get("name"), str)
    }
    required = {
        "advertised_bundle_closure_selects_websocket",
        "missing_websocket_bundle_falls_back",
        "bundle_without_websocket_transport_falls_back",
    }
    if set(by_name) != required:
        lint.fail(path, f"bundle_closure_cases names drift: {sorted(set(by_name))}")
        return

    base_case = by_name["advertised_bundle_closure_selects_websocket"]
    base = base_case.get("instance")
    schema_ref = base_case.get("schema_ref")
    if not isinstance(base, dict) or not isinstance(schema_ref, str):
        lint.fail(path, "bundle closure base case requires instance and schema_ref")
        return
    check_json_instance_against_schema(lint, path, "bundle closure base", schema_ref, base)

    required_bundle = base_case.get("required_bundle")
    required_operations = base_case.get("required_operations")
    if not isinstance(required_bundle, str) or not isinstance(required_operations, list):
        lint.fail(path, "bundle closure base case requires required_bundle and required_operations")
        return
    if required_bundle not in base.get("supported_operation_bundles", []):
        lint.fail(path, "bundle closure base case does not advertise its own required_bundle")
    if not any(
        isinstance(binding, dict) and binding.get("kind") == "websocket"
        for binding in base.get("transport_bindings", [])
    ):
        lint.fail(path, "bundle closure base case does not advertise a websocket transport binding")

    registry = load_json(lint, ARTIFACTS / "registry" / "operation-registry.json")
    if not isinstance(registry, dict):
        return
    bundles = {
        row.get("operation_bundle_id"): row
        for row in registry.get("operation_bundles", [])
        if isinstance(row, dict)
    }
    bundle = bundles.get(required_bundle)
    if not isinstance(bundle, dict):
        lint.fail(path, f"bundle closure references unregistered bundle: {required_bundle!r}")
        return
    websocket_members = sorted(
        member.get("operation_id")
        for member in bundle.get("members", [])
        if isinstance(member, dict) and member.get("binding_kind") == "websocket"
    )
    if websocket_members != sorted(required_operations):
        lint.fail(
            path,
            "bundle closure required_operations drift from the registered bundle: "
            f"{websocket_members} != {sorted(required_operations)}",
        )

    removed_bundle = by_name["missing_websocket_bundle_falls_back"].get("remove_bundle")
    if removed_bundle not in base.get("supported_operation_bundles", []):
        lint.fail(path, f"remove_bundle names a carrier the base does not advertise: {removed_bundle!r}")
    else:
        mutation = copy.deepcopy(base)
        mutation["supported_operation_bundles"] = [
            value for value in mutation["supported_operation_bundles"] if value != removed_bundle
        ]
        check_json_instance_against_schema(
            lint, path, "missing_websocket_bundle_falls_back", schema_ref, mutation
        )

    removed_kind = by_name["bundle_without_websocket_transport_falls_back"].get("remove_transport_kind")
    bindings = base.get("transport_bindings", [])
    if not any(isinstance(row, dict) and row.get("kind") == removed_kind for row in bindings):
        lint.fail(
            path,
            f"remove_transport_kind names a carrier the base does not advertise: {removed_kind!r}",
        )
    else:
        mutation = copy.deepcopy(base)
        mutation["transport_bindings"] = [
            row for row in bindings if not (isinstance(row, dict) and row.get("kind") == removed_kind)
        ]
        if not mutation["transport_bindings"]:
            lint.fail(path, "bundle closure fallback case removed the mandatory HTTP binding")
        check_json_instance_against_schema(
            lint, path, "bundle_without_websocket_transport_falls_back", schema_ref, mutation
        )


def check_websocket_binding_fixture(lint: Lint) -> None:
    """Execute the in-tree, tool-neutral portion of the WebSocket binding suite."""
    path = ARTIFACTS / "fixtures" / "websocket-binding-fixture.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return

    discovery_cases = data.get("discovery_cases")
    if not isinstance(discovery_cases, list):
        lint.fail(path, "discovery_cases must be an array")
        return
    discovery_by_name = {
        case.get("name"): case
        for case in discovery_cases
        if isinstance(case, dict) and isinstance(case.get("name"), str)
    }
    required_discovery_names = {
        "closed_descriptor",
        "noncanonical_or_credentialed_url_rejected",
        "missing_limit_rejected",
    }
    if set(discovery_by_name) != required_discovery_names:
        lint.fail(path, f"discovery_cases names drift: {sorted(set(discovery_by_name))}")
    descriptor_case = discovery_by_name.get("closed_descriptor") or {}
    descriptor = descriptor_case.get("instance")
    descriptor_schema_ref = descriptor_case.get("schema_ref")
    if not isinstance(descriptor, dict) or not isinstance(descriptor_schema_ref, str):
        lint.fail(path, "closed_descriptor requires instance and schema_ref")
    else:
        check_json_instance_against_schema(
            lint,
            path,
            "closed_descriptor",
            descriptor_schema_ref,
            descriptor,
        )
        canonical_errors = websocket_canonical_wss_errors(descriptor.get("base_url"))
        if canonical_errors:
            lint.fail(path, "closed_descriptor base_url is not canonical: " + "; ".join(canonical_errors))

        if "operations" in descriptor:
            lint.fail(
                path,
                "websocket transport descriptor must not carry its own operations[]; "
                "operation reachability lives in ServiceDescribe.supported_operation_bundles",
            )

        missing_case = discovery_by_name.get("missing_limit_rejected") or {}
        remove_each = missing_case.get("remove_each")
        if not isinstance(remove_each, list) or set(remove_each) != {
            "max_frame_bytes",
            "max_channels",
        }:
            lint.fail(path, "missing_limit_rejected remove_each drift")
        else:
            for field in remove_each:
                mutation = copy.deepcopy(descriptor)
                mutation.pop(field, None)
                check_json_instance_against_schema(
                    lint,
                    path,
                    f"missing descriptor field {field}",
                    descriptor_schema_ref,
                    mutation,
                    expect_valid=False,
                )

    url_case = discovery_by_name.get("noncanonical_or_credentialed_url_rejected") or {}
    rejected_urls = url_case.get("base_urls")
    if not isinstance(rejected_urls, list) or not rejected_urls:
        lint.fail(path, "noncanonical URL case requires base_urls")
    else:
        for value in rejected_urls:
            if not websocket_canonical_wss_errors(value):
                lint.fail(path, f"noncanonical base_url vector is canonical: {value!r}")
            if isinstance(descriptor, dict) and isinstance(descriptor_schema_ref, str):
                mutation = copy.deepcopy(descriptor)
                mutation["base_url"] = value
                check_json_instance_against_schema(
                    lint,
                    path,
                    f"noncanonical base_url {value!r}",
                    descriptor_schema_ref,
                    mutation,
                    expect_valid=False,
                )

    check_websocket_bundle_closure_cases(lint, path, data)

    kat = data.get("dpop_kat")
    if not isinstance(kat, dict):
        lint.fail(path, "dpop_kat must be an object")
        return
    decoded = kat.get("decoded")
    check_json_instance_against_schema(
        lint,
        path,
        "dpop_kat.decoded",
        "schemas/websocket-dpop-proof.schema.json",
        decoded,
    )
    if not isinstance(decoded, dict):
        return
    protected = decoded.get("protected")
    claims = decoded.get("claims")
    if not isinstance(protected, dict) or not isinstance(claims, dict):
        lint.fail(path, "dpop_kat.decoded must contain protected and claims objects")
        return
    if protected.get("jwk") != kat.get("public_jwk"):
        lint.fail(path, "dpop_kat protected jwk must equal public_jwk")
    if claims.get("htu") != kat.get("base_url"):
        lint.fail(path, "dpop_kat htu must equal the advertised base_url verbatim")
    canonical_htu_errors = websocket_canonical_wss_errors(claims.get("htu"))
    if canonical_htu_errors:
        lint.fail(path, "dpop_kat htu is not canonical: " + "; ".join(canonical_htu_errors))
    if claims.get("nonce") != kat.get("nonce"):
        lint.fail(path, "dpop_kat nonce must equal the challenge nonce")

    def fixture_timestamp(value: object, label: str) -> datetime | None:
        if not isinstance(value, str):
            lint.fail(path, f"{label} must be an RFC 3339 timestamp")
            return None
        try:
            return datetime.fromisoformat(value.removesuffix("Z") + ("+00:00" if value.endswith("Z") else ""))
        except ValueError:
            lint.fail(path, f"{label} is not an RFC 3339 timestamp")
            return None

    issued_at = fixture_timestamp(kat.get("issued_at"), "dpop_kat.issued_at")
    expires_at = fixture_timestamp(kat.get("expires_at"), "dpop_kat.expires_at")
    if issued_at is not None and expires_at is not None:
        if not 0 < (expires_at - issued_at).total_seconds() <= 5:
            lint.fail(path, "dpop_kat challenge window must be greater than zero and at most 5 seconds")
        if claims.get("iat") != int(issued_at.timestamp()):
            lint.fail(path, "dpop_kat iat must equal issued_at NumericDate")

    challenge_state = kat.get("challenge_state")
    if not isinstance(challenge_state, dict):
        lint.fail(path, "dpop_kat challenge_state must be an object")
    else:
        expected_challenge_key = [kat.get("connection_id"), kat.get("nonce")]
        if challenge_state.get("key") != expected_challenge_key:
            lint.fail(path, "dpop_kat challenge_state key must be [connection_id, nonce]")
        for field in ("canonical_origin", "canonical_base_url", "issued_at", "expires_at"):
            expected_field = {
                "canonical_origin": kat.get("origin"),
                "canonical_base_url": kat.get("base_url"),
                "issued_at": kat.get("issued_at"),
                "expires_at": kat.get("expires_at"),
            }[field]
            if challenge_state.get(field) != expected_field:
                lint.fail(path, f"dpop_kat challenge_state {field} drift")
        if challenge_state.get("consumed") is not False:
            lint.fail(path, "dpop_kat initial challenge_state must be unconsumed")

    canonical_protected = json.dumps(
        protected,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    canonical_claims = json.dumps(
        claims,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    if kat.get("protected_json_utf8") != canonical_protected:
        lint.fail(path, "dpop_kat protected_json_utf8 is not canonical JSON")
    if kat.get("claims_json_utf8") != canonical_claims:
        lint.fail(path, "dpop_kat claims_json_utf8 is not canonical JSON")

    def b64url(data_bytes: bytes) -> str:
        return base64.urlsafe_b64encode(data_bytes).rstrip(b"=").decode("ascii")

    protected_segment = b64url(canonical_protected.encode("utf-8"))
    claims_segment = b64url(canonical_claims.encode("utf-8"))
    signing_input = protected_segment + "." + claims_segment
    if kat.get("protected_base64url") != protected_segment:
        lint.fail(path, "dpop_kat protected_base64url drift")
    if kat.get("claims_base64url") != claims_segment:
        lint.fail(path, "dpop_kat claims_base64url drift")
    if kat.get("signing_input_ascii") != signing_input:
        lint.fail(path, "dpop_kat signing_input_ascii drift")
    signature = kat.get("signature_base64url")
    if not isinstance(signature, str) or len(signature) != 86:
        lint.fail(path, "dpop_kat signature must encode one 64-byte Ed25519 signature")
    elif kat.get("compact_jws") != signing_input + "." + signature:
        lint.fail(path, "dpop_kat compact_jws does not match its declared segments")
    else:
        try:
            signature_bytes = base64.urlsafe_b64decode(signature + "==")
        except (ValueError, TypeError):
            signature_bytes = b""
        if len(signature_bytes) != 64:
            lint.fail(path, "dpop_kat signature_base64url does not decode to 64 bytes")
    private_seed_hex = kat.get("private_seed_hex")
    if not isinstance(private_seed_hex, str) or not re.fullmatch(r"[0-9a-f]{64}", private_seed_hex):
        lint.fail(path, "dpop_kat private_seed_hex must encode one 32-byte public test seed")

    grant = kat.get("session_grant")
    if not isinstance(grant, str):
        lint.fail(path, "dpop_kat session_grant must be a string")
    else:
        expected_ath = b64url(hashlib.sha256(grant.encode("ascii")).digest())
        if claims.get("ath") != expected_ath:
            lint.fail(path, "dpop_kat ath does not bind the ASCII session grant")

    public_jwk = kat.get("public_jwk")
    if isinstance(public_jwk, dict):
        canonical_jwk = json.dumps(
            public_jwk,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        expected_jkt = b64url(hashlib.sha256(canonical_jwk.encode("utf-8")).digest())
        if kat.get("cnf_jkt") != expected_jkt:
            lint.fail(path, "dpop_kat cnf_jkt is not the RFC 7638 JWK thumbprint")
        namespace = kat.get("replay_cache_namespace")
        if not isinstance(namespace, str) or not namespace:
            lint.fail(path, "dpop_kat replay_cache_namespace must be a non-empty string")
            namespace = None
        expected_replay_key = [expected_jkt, claims.get("jti"), namespace]
        if kat.get("expected_replay_ledger_key") != expected_replay_key:
            lint.fail(path, "dpop_kat replay ledger key drift")
    else:
        lint.fail(path, "dpop_kat public_jwk must be an object")

    dpop_negative_cases = data.get("dpop_negative_cases")
    if not isinstance(dpop_negative_cases, list):
        lint.fail(path, "dpop_negative_cases must be an array")
        dpop_negative_cases = []
    dpop_by_name = {
        case.get("name"): case
        for case in dpop_negative_cases
        if isinstance(case, dict) and isinstance(case.get("name"), str)
    }
    required_dpop_negative = {
        "http_validator_must_not_accept_application_context",
        "wrong_htu_scheme",
        "wrong_method_token",
        "wrong_ath",
        "wrong_nonce",
        "connection_id_mismatch",
        "origin_mismatch",
        "expired_challenge",
        "replayed_nonce_and_jti",
        "unknown_claim",
        "holder_thumbprint_mismatch",
    }
    if set(dpop_by_name) != required_dpop_negative:
        lint.fail(path, f"dpop_negative_cases names drift: {sorted(set(dpop_by_name))}")
    for name, case in dpop_by_name.items():
        if case.get("expected") != "rejected":
            lint.fail(path, f"dpop negative {name} must expect rejected")

    proof_schema_ref = kat.get("proof_schema_ref")
    if not isinstance(proof_schema_ref, str):
        lint.fail(path, "dpop_kat proof_schema_ref must be a string")
    else:
        if proof_schema_ref != "schemas/websocket-dpop-proof.schema.json":
            lint.fail(path, "dpop_kat proof_schema_ref drift")
        for value in (rejected_urls if isinstance(rejected_urls, list) else []):
            mutation = copy.deepcopy(decoded)
            mutation["claims"]["htu"] = value
            check_json_instance_against_schema(
                lint,
                path,
                f"dpop noncanonical htu {value!r}",
                proof_schema_ref,
                mutation,
                expect_valid=False,
            )
        for name in ("wrong_htu_scheme", "wrong_method_token", "unknown_claim"):
            case = dpop_by_name.get(name) or {}
            mutation = copy.deepcopy(decoded)
            if isinstance(case.get("replace_claim"), dict):
                mutation["claims"].update(case["replace_claim"])
            if isinstance(case.get("add_claim"), dict):
                mutation["claims"].update(case["add_claim"])
            check_json_instance_against_schema(
                lint,
                path,
                f"dpop negative {name}",
                proof_schema_ref,
                mutation,
                expect_valid=False,
            )

    if (dpop_by_name.get("http_validator_must_not_accept_application_context") or {}).get(
        "validator_context"
    ) != "http_request_dpop":
        lint.fail(path, "HTTP DPoP isolation negative must select http_request_dpop")
    wrong_ath = ((dpop_by_name.get("wrong_ath") or {}).get("replace_claim") or {}).get("ath")
    if not isinstance(wrong_ath, str) or wrong_ath == claims.get("ath"):
        lint.fail(path, "wrong_ath negative must replace ath with a distinct value")
    wrong_nonce = ((dpop_by_name.get("wrong_nonce") or {}).get("replace_claim") or {}).get("nonce")
    if not isinstance(wrong_nonce, str) or wrong_nonce == kat.get("nonce"):
        lint.fail(path, "wrong_nonce negative must replace nonce with a distinct value")
    if (dpop_by_name.get("connection_id_mismatch") or {}).get(
        "authenticate_connection_id"
    ) == kat.get("connection_id"):
        lint.fail(path, "connection_id_mismatch negative does not mismatch")
    if (dpop_by_name.get("origin_mismatch") or {}).get("socket_origin") == kat.get("origin"):
        lint.fail(path, "origin_mismatch negative does not mismatch")
    expired_verification = fixture_timestamp(
        (dpop_by_name.get("expired_challenge") or {}).get("verification_time"),
        "expired_challenge.verification_time",
    )
    if expires_at is not None and (
        expired_verification is None or expired_verification <= expires_at
    ):
        lint.fail(path, "expired_challenge verification_time must be after expires_at")
    replay_case = dpop_by_name.get("replayed_nonce_and_jti") or {}
    if replay_case.get("challenge_consumed") is not True or replay_case.get(
        "replay_ledger_key_present"
    ) is not True:
        lint.fail(path, "replay negative must exercise consumed challenge and present ledger key")
    if (dpop_by_name.get("holder_thumbprint_mismatch") or {}).get(
        "grant_cnf_jkt"
    ) == kat.get("cnf_jkt"):
        lint.fail(path, "holder_thumbprint_mismatch negative does not mismatch")

    parsed_frame_cases: dict[str, dict[str, Any]] = {}
    frame_cases = data.get("frame_schema_cases")
    if not isinstance(frame_cases, list) or not frame_cases:
        lint.fail(path, "frame_schema_cases must be a non-empty array")
    else:
        advertised_limit = ((data.get("limits") or {}).get("fixture_advertised_max_frame_bytes"))
        for index, case in enumerate(frame_cases):
            if not isinstance(case, dict):
                lint.fail(path, f"frame_schema_cases[{index}] must be an object")
                continue
            name = case.get("name")
            if not isinstance(name, str) or not name:
                lint.fail(path, f"frame_schema_cases[{index}] requires a name")
            elif name in parsed_frame_cases:
                lint.fail(path, f"duplicate frame_schema_cases name: {name}")
            else:
                parsed_frame_cases[name] = case
            wire = case.get("wire_utf8")
            schema_ref = case.get("direction_schema_ref")
            if not isinstance(wire, str) or not isinstance(schema_ref, str):
                lint.fail(path, f"frame_schema_cases[{index}] requires wire_utf8 and direction_schema_ref")
                continue
            if case.get("expect_valid") is not True:
                lint.fail(path, f"frame_schema_cases[{index}] must explicitly expect valid")
            if isinstance(advertised_limit, int) and len(wire.encode("utf-8")) > advertised_limit:
                lint.fail(path, f"frame_schema_cases[{index}] exceeds the advertised byte limit")
            try:
                duplicate_members: list[str] = []

                def collect_duplicate_members(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
                    result: dict[str, Any] = {}
                    for key, value in pairs:
                        if key in result:
                            duplicate_members.append(key)
                        result[key] = value
                    return result

                instance = json.loads(wire, object_pairs_hook=collect_duplicate_members)
            except json.JSONDecodeError as exc:
                lint.fail(path, f"frame_schema_cases[{index}] wire_utf8 is invalid JSON: {exc}")
                continue
            if duplicate_members:
                lint.fail(path, f"frame_schema_cases[{index}] contains duplicate members")
            check_json_instance_against_schema(
                lint,
                path,
                f"frame_schema_cases[{index}]",
                schema_ref,
                instance,
                expect_valid=case.get("expect_valid") is True,
            )
            check_json_instance_against_schema(
                lint,
                path,
                f"frame_schema_cases[{index}] top-level union",
                "schemas/websocket-frame.schema.json",
                instance,
            )
            opposite_schema_ref = (
                "schemas/websocket-frame.schema.json#/$defs/client_frame"
                if schema_ref.endswith("/server_frame")
                else "schemas/websocket-frame.schema.json#/$defs/server_frame"
            )
            check_json_instance_against_schema(
                lint,
                path,
                f"frame_schema_cases[{index}] opposite direction",
                opposite_schema_ref,
                instance,
                expect_valid=False,
            )

        required_frame_cases = {
            "challenge",
            "authenticate",
            "welcome",
            "open_account",
            "open_events",
            "open_signal",
            "opened",
            "opened_events",
            "opened_signal",
            "account_data",
            "events_data",
            "signal_data",
            "channel_control",
            "signal_control",
            "channel_error",
            "connection_error",
            "client_close",
            "server_closed",
            "ping",
            "pong",
            "reauth_required",
            "connection_drain",
        }
        if set(parsed_frame_cases) != required_frame_cases:
            lint.fail(path, f"frame_schema_cases names drift: {sorted(set(parsed_frame_cases))}")
        authenticate_case = parsed_frame_cases.get("authenticate") or {}
        try:
            authenticate_instance = json.loads(authenticate_case.get("wire_utf8", "null"))
        except json.JSONDecodeError:
            authenticate_instance = None
        if not isinstance(authenticate_instance, dict) or authenticate_instance.get(
            "dpop_proof"
        ) != kat.get("compact_jws"):
            lint.fail(path, "authenticate frame must carry the exact DPoP KAT compact_jws")
        welcome_case = parsed_frame_cases.get("welcome") or {}
        try:
            welcome_instance = json.loads(welcome_case.get("wire_utf8", "null"))
        except json.JSONDecodeError:
            welcome_instance = None
        if not isinstance(welcome_instance, dict) or welcome_instance.get(
            "max_frame_bytes"
        ) != advertised_limit:
            lint.fail(path, "welcome max_frame_bytes must equal the fixture advertised limit")
        error_registry = load_json(lint, ARTIFACTS / "registry" / "error-code-registry.json")
        registered_error_codes = {
            row.get("code")
            for row in (error_registry or {}).get("codes", [])
            if isinstance(row, dict) and isinstance(row.get("code"), str)
        }
        for error_case_name in ("channel_error", "connection_error"):
            try:
                error_instance = json.loads(
                    (parsed_frame_cases.get(error_case_name) or {}).get("wire_utf8", "null")
                )
            except json.JSONDecodeError:
                error_instance = None
            error_code = (
                ((error_instance or {}).get("error") or {}).get("code")
                if isinstance(error_instance, dict)
                else None
            )
            if error_code not in registered_error_codes:
                lint.fail(path, f"{error_case_name} uses an unregistered error code: {error_code!r}")

    negative_cases = data.get("wire_negative_cases")
    if not isinstance(negative_cases, list) or not negative_cases:
        lint.fail(path, "wire_negative_cases must be a non-empty array")
        return
    by_name = {
        case.get("name"): case
        for case in negative_cases
        if isinstance(case, dict) and isinstance(case.get("name"), str)
    }
    required_negative = {
        "duplicate_member",
        "unknown_field",
        "non_ascii_session_grant",
        "wrong_direction",
        "binary_message",
        "oversize_before_json_parse",
        "data_on_unopened_channel",
        "payload_does_not_match_channel_operation",
    }
    if set(by_name) != required_negative:
        lint.fail(path, f"wire_negative_cases names drift: {sorted(set(by_name))}")

    duplicate_wire = (by_name.get("duplicate_member") or {}).get("wire_utf8")
    duplicate_seen = False
    if isinstance(duplicate_wire, str):
        def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            nonlocal duplicate_seen
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    duplicate_seen = True
                result[key] = value
            return result
        json.loads(duplicate_wire, object_pairs_hook=reject_duplicates)
    if not duplicate_seen:
        lint.fail(path, "duplicate_member vector does not contain a duplicate JSON member")

    for name in ("unknown_field", "non_ascii_session_grant", "wrong_direction"):
        case = by_name.get(name) or {}
        wire = case.get("wire_utf8")
        schema_ref = case.get("direction_schema_ref") or "schemas/websocket-frame.schema.json#/$defs/client_frame"
        if isinstance(wire, str):
            check_json_instance_against_schema(
                lint,
                path,
                name,
                schema_ref,
                json.loads(wire),
                expect_valid=False,
            )

    oversize = by_name.get("oversize_before_json_parse") or {}
    generator = oversize.get("generator")
    limit = oversize.get("advertised_max_frame_bytes")
    if not isinstance(generator, dict) or not isinstance(limit, int):
        lint.fail(path, "oversize vector requires generator and advertised_max_frame_bytes")
    else:
        total = generator.get("total_message_bytes")
        prefix = generator.get("prefix_utf8")
        repeated = generator.get("repeat_utf8")
        suffix = generator.get("suffix_utf8")
        if (
            not isinstance(total, int)
            or not isinstance(prefix, str)
            or not isinstance(repeated, str)
            or len(repeated.encode("utf-8")) != 1
            or not isinstance(suffix, str)
            or total != limit + 1
            or len(prefix.encode("utf-8")) + len(suffix.encode("utf-8")) >= total
        ):
            lint.fail(path, "oversize generator must materialize exactly limit + 1 UTF-8 bytes")

    expected_wire_close_codes = {
        "duplicate_member": 1002,
        "unknown_field": 1002,
        "non_ascii_session_grant": 1002,
        "wrong_direction": 1002,
        "binary_message": 1002,
        "oversize_before_json_parse": 1009,
        "data_on_unopened_channel": 1002,
    }
    for name, expected_close_code in expected_wire_close_codes.items():
        if (by_name.get(name) or {}).get("expected_close_code") != expected_close_code:
            lint.fail(path, f"{name} close code must be {expected_close_code}")
    binary_case = by_name.get("binary_message") or {}
    if binary_case.get("opcode") != "binary" or not re.fullmatch(
        r"(?:[0-9a-f]{2})+",
        binary_case.get("wire_hex", ""),
    ):
        lint.fail(path, "binary_message must contain lowercase even-length wire_hex and binary opcode")
    state_case = by_name.get("data_on_unopened_channel") or {}
    if state_case.get("rejection_stage") != "connection_state":
        lint.fail(path, "data_on_unopened_channel must fail at connection_state")
    operation_case = by_name.get("payload_does_not_match_channel_operation") or {}
    if (
        operation_case.get("channel_operation") != "ak.self.signal.stream.subscribe.v1"
        or operation_case.get("rejection_stage") != "channel_operation_schema"
        or operation_case.get("connection_remains_open") is not True
    ):
        lint.fail(path, "payload mismatch negative must isolate the Signal channel")

    multiplex_trace = data.get("multiplex_trace")
    if not isinstance(multiplex_trace, dict):
        lint.fail(path, "multiplex_trace must be an object")
    else:
        sequence = multiplex_trace.get("frame_case_sequence")
        required_sequence = [
            "challenge",
            "authenticate",
            "welcome",
            "open_account",
            "opened",
            "open_events",
            "opened_events",
            "open_signal",
            "opened_signal",
            "account_data",
            "events_data",
            "channel_control",
            "signal_control",
            "channel_error",
            "server_closed",
        ]
        if sequence != required_sequence:
            lint.fail(path, "multiplex_trace frame_case_sequence drift")
        elif any(name not in parsed_frame_cases for name in sequence):
            lint.fail(path, "multiplex_trace references an unknown exact frame case")
        expected_state = multiplex_trace.get("expected")
        if not isinstance(expected_state, dict):
            lint.fail(path, "multiplex_trace expected state must be an object")
        else:
            try:
                account_data = json.loads(parsed_frame_cases["account_data"]["wire_utf8"])
                events_data = json.loads(parsed_frame_cases["events_data"]["wire_utf8"])
            except (KeyError, json.JSONDecodeError):
                account_data = {}
                events_data = {}
            if expected_state.get("account_cursor") != (
                (account_data.get("payload") or {}).get("cursor")
            ):
                lint.fail(path, "multiplex_trace account cursor does not come from account_data")
            if expected_state.get("events_cursor") != (
                (events_data.get("payload") or {}).get("cursor")
            ):
                lint.fail(path, "multiplex_trace events cursor does not come from events_data")
            if (
                expected_state.get("signal_cursor") is not None
                or expected_state.get("signal_catchup") is not False
                or expected_state.get("open_channels_after_events_close")
                != ["account-1", "signal-1"]
                or expected_state.get("channel_id_reuse") != "conflict"
                or expected_state.get("physical_connection_open") is not True
            ):
                lint.fail(path, "multiplex_trace isolation state drift")

    reauth_trace = data.get("reauth_trace")
    reauth_by_name = {
        case.get("name"): case
        for case in reauth_trace or []
        if isinstance(case, dict) and isinstance(case.get("name"), str)
    }
    if set(reauth_by_name) != {"fresh_reauth_succeeds", "old_proof_reuse_fails"}:
        lint.fail(path, f"reauth_trace names drift: {sorted(set(reauth_by_name))}")
    fresh_reauth = reauth_by_name.get("fresh_reauth_succeeds") or {}
    if (
        any(fresh_reauth.get(field) is not True for field in (
            "new_nonce",
            "new_jti",
            "new_session_grant",
            "new_ath",
        ))
        or not isinstance(fresh_reauth.get("authenticate_within_ms"), int)
        or fresh_reauth.get("authenticate_within_ms", 5001) > 5000
        or fresh_reauth.get("expected") != "channels_continue"
    ):
        lint.fail(path, "fresh_reauth_succeeds must refresh every proof input within 5 seconds")
    stale_reauth = reauth_by_name.get("old_proof_reuse_fails") or {}
    if (
        stale_reauth.get("reuse_old_nonce") is not True
        or stale_reauth.get("reuse_old_jti") is not True
        or stale_reauth.get("expected_close_code") != 1008
        or stale_reauth.get("old_authorization_continues") is not False
    ):
        lint.fail(path, "old_proof_reuse_fails semantics drift")

    close_traces = data.get("drain_and_close_traces")
    close_by_name = {
        case.get("name"): case
        for case in close_traces or []
        if isinstance(case, dict) and isinstance(case.get("name"), str)
    }
    expected_close_names = {
        "channel_error_isolated",
        "graceful_service_drain",
        "protocol_error",
        "policy_error_retry_once",
        "message_too_big",
        "restart_retry_budget",
    }
    if set(close_by_name) != expected_close_names:
        lint.fail(path, f"drain_and_close_traces names drift: {sorted(set(close_by_name))}")
    required_trace_codes = {
        "graceful_service_drain": 1001,
        "protocol_error": 1002,
        "message_too_big": 1009,
    }
    for name, code in required_trace_codes.items():
        if (close_by_name.get(name) or {}).get("expected_close_code") != code:
            lint.fail(path, f"{name} close code must be {code}")
    if (close_by_name.get("restart_retry_budget") or {}).get("attempts") != 3:
        lint.fail(path, "restart_retry_budget must fall back after three pre-welcome failures")

    fallback_cases = data.get("fallback_cases")
    fallback_by_name = {
        case.get("name"): case
        for case in fallback_cases or []
        if isinstance(case, dict) and isinstance(case.get("name"), str)
    }
    if set(fallback_by_name) != {"upgrade_or_proxy_failure", "single_owner_transport_switch"}:
        lint.fail(path, f"fallback_cases names drift: {sorted(set(fallback_by_name))}")
    for name, case in fallback_by_name.items():
        if case.get("expected_transport") != "http_json":
            lint.fail(path, f"fallback case {name} must end on http_json")
    owner_switch = fallback_by_name.get("single_owner_transport_switch") or {}
    if (
        owner_switch.get("old_websocket_owner_closed") is not True
        or owner_switch.get("http_owner_started_after_old_owner_stopped") is not True
        or owner_switch.get("duplicate_consumers") is not False
        or owner_switch.get("signal_catchup_attempted") is not False
    ):
        lint.fail(path, "single_owner_transport_switch ordering drift")

    frame_schema = load_json(lint, ARTIFACTS / "schemas" / "websocket-frame.schema.json")
    definitions = set(((frame_schema or {}).get("$defs") or {}).keys())
    required_frame_definitions = {
        "challenge",
        "authenticate",
        "welcome",
        "open",
        "opened",
        "data",
        "control",
        "error",
        "close",
        "closed",
        "ping",
        "pong",
        "reauth_required",
        "server_frame",
        "client_frame",
    }
    missing = sorted(required_frame_definitions - definitions)
    if missing:
        lint.fail(path, f"websocket frame schema misses required definitions: {missing}")
MLS_CREATOR_BOOTSTRAP_REGISTRY_PATH = (
    ARTIFACTS / "registry" / "mls-creator-bootstrap-transaction-registry.json"
)

MLS_CREATOR_BOOTSTRAP_FIXTURE_PATH = (
    ARTIFACTS / "fixtures" / "mls-creator-bootstrap-recovery-fixture.json"
)

MLS_CREATOR_BOOTSTRAP_VECTOR_ID = "ak.vector.mls.creator_bootstrap_recovery.v1"

MLS_CREATOR_BOOTSTRAP_STATE_KEYS = (
    "state_id",
    "ordinal",
    "kind",
    "authority_source",
    "entry_predicate",
    "required_durable_fields",
    "amendment_rule",
    "allowed_exits",
    "retry_rule",
    "gc_rule",
    "failure_disposition",
)

MLS_CREATOR_BOOTSTRAP_AMENDMENT_RULES = frozenset(
    {"closed_intent_atomic_replacement", "forbidden"}
)

MLS_CREATOR_BOOTSTRAP_AMENDMENT_KEYS = (
    "amendable_state",
    "forbidden_from_state",
    "transition_id",
    "granularity",
    "amendable_fields",
    "immutable_fields",
    "rationale",
    "exit_rule",
)

MLS_CREATOR_BOOTSTRAP_SCOPE_KIND_KEYS = (
    "applicable_scope_kinds",
    "excluded_scope_kinds",
    "rule",
)

MLS_CREATOR_BOOTSTRAP_SCOPE_KINDS = ("realm", "circle", "sidecar")

MLS_CREATOR_BOOTSTRAP_TRANSITION_KEYS = (
    "transition_id",
    "from_state",
    "to_state",
    "commit_boundary",
    "crash_before_commit",
    "crash_after_commit",
)

MLS_CREATOR_BOOTSTRAP_STATE_KINDS = frozenset(
    {"progress", "terminal_success", "terminal_attempt", "terminal_failure"}
)

MLS_CREATOR_BOOTSTRAP_PROGRESS_ORDER = (
    "genesis_intent_persisted",
    "realm_accepted",
    "governance_result_pinned",
    "epoch0_state_persisted",
    "genesis_queued",
    "genesis_accepted",
    "artifacts_converged",
    "ready",
)

MLS_CREATOR_BOOTSTRAP_SCENARIOS = (
    "selector_amendment_at_genesis_intent_persisted",
    "selector_amendment_after_realm_accepted",
    "realm_create_response_loss",
    "governance_query_response_loss",
    "public_blob_partial_upload",
    "sign_before_enqueue",
    "enqueue_commit_then_response_loss",
    "accepted_then_local_confirmation_loss",
    "artifact_partial_persistence",
    "another_genesis_wins",
    "terminal_reject",
    "local_corruption",
)


def check_mls_creator_bootstrap_scope_kinds(
    lint: Lint, registry_path: Path, registry: dict[str, Any]
) -> None:
    """Refuse a creator bootstrap registry that stays silent about Sidecar scopes.

    encryption-and-audit.md section 2.5.1 gives effective_scope.kind="sidecar" its
    own handshake profile. A registry that only says "effective scope" invites an
    implementation to drive a Sidecar through this FSM, so the applicable kinds are
    stated positively and the excluded kind is named.
    """

    block = registry.get("scope_kind_applicability")
    if not isinstance(block, dict):
        lint.fail(registry_path, "scope_kind_applicability must be an object")
        return
    if tuple(block.keys()) != MLS_CREATOR_BOOTSTRAP_SCOPE_KIND_KEYS:
        lint.fail(
            registry_path,
            "scope_kind_applicability must declare exactly "
            f"{list(MLS_CREATOR_BOOTSTRAP_SCOPE_KIND_KEYS)} in that order",
        )
        return
    applicable = block["applicable_scope_kinds"]
    excluded = block["excluded_scope_kinds"]
    for key, value in (("applicable_scope_kinds", applicable), ("excluded_scope_kinds", excluded)):
        if not isinstance(value, list) or len(set(value)) != len(value):
            lint.fail(
                registry_path,
                f"scope_kind_applicability.{key} must be a duplicate-free array",
            )
            return
    if not applicable:
        lint.fail(registry_path, "scope_kind_applicability.applicable_scope_kinds must be non-empty")
        return
    unknown = sorted((set(applicable) | set(excluded)) - set(MLS_CREATOR_BOOTSTRAP_SCOPE_KINDS))
    if unknown:
        lint.fail(registry_path, f"scope_kind_applicability names unregistered scope kinds: {unknown}")
    if set(applicable) & set(excluded):
        lint.fail(registry_path, "a scope kind cannot be both applicable and excluded")
    if set(applicable) | set(excluded) != set(MLS_CREATOR_BOOTSTRAP_SCOPE_KINDS):
        lint.fail(
            registry_path,
            "scope_kind_applicability must take a position on every registered effective_scope kind "
            f"{list(MLS_CREATOR_BOOTSTRAP_SCOPE_KINDS)}",
        )
    if "sidecar" not in excluded:
        lint.fail(
            registry_path,
            "sidecar MUST be excluded: encryption-and-audit.md section 2.5.1 keeps its independent "
            "handshake profile and this transaction does not change the Sidecar contract",
        )
    rule = block["rule"]
    if not isinstance(rule, str) or "sidecar" not in rule:
        lint.fail(registry_path, "scope_kind_applicability.rule must state the Sidecar exclusion")


def check_mls_creator_bootstrap_amendment(
    lint: Lint,
    registry_path: Path,
    registry: dict[str, Any],
    state_rows: dict[str, dict[str, Any]],
) -> str | None:
    """Keep in-place selector amendment confined to genesis_intent_persisted.

    The ruling allows a creator to replace the whole closed creation intent while
    nothing outside the device can have observed it, and forbids it from
    realm_accepted on, where the pinned governance outcome and the
    selector-dependent random material already exist. The decay this refuses is a
    registry that keeps the prose but quietly lets a later state stay amendable.
    """

    block = registry.get("selector_amendment")
    if not isinstance(block, dict):
        lint.fail(registry_path, "selector_amendment must be an object")
        return None
    if tuple(block.keys()) != MLS_CREATOR_BOOTSTRAP_AMENDMENT_KEYS:
        lint.fail(
            registry_path,
            f"selector_amendment must declare exactly {list(MLS_CREATOR_BOOTSTRAP_AMENDMENT_KEYS)} in that order",
        )
        return None
    for key in ("amendable_state", "forbidden_from_state", "transition_id", "granularity", "rationale", "exit_rule"):
        if not isinstance(block[key], str) or not block[key].strip():
            lint.fail(registry_path, f"selector_amendment.{key} must be a non-empty string")
            return None
    amendable_state = block["amendable_state"]
    forbidden_from_state = block["forbidden_from_state"]
    for key, value in (("amendable_state", amendable_state), ("forbidden_from_state", forbidden_from_state)):
        if value not in state_rows:
            lint.fail(registry_path, f"selector_amendment.{key} is not a registered state: {value!r}")
            return None
    if block["transition_id"] != f"{amendable_state}_to_{amendable_state}":
        lint.fail(
            registry_path,
            f"selector_amendment.transition_id must be {amendable_state}_to_{amendable_state}",
        )
    for key in ("amendable_fields", "immutable_fields"):
        value = block[key]
        if not isinstance(value, list) or not value or len(set(value)) != len(value) or not all(
            isinstance(item, str) and item.strip() for item in value
        ):
            lint.fail(
                registry_path,
                f"selector_amendment.{key} must be a non-empty duplicate-free array of non-empty strings",
            )
            return None
    overlap = sorted(set(block["amendable_fields"]) & set(block["immutable_fields"]))
    if overlap:
        lint.fail(registry_path, f"selector_amendment lists the same field as amendable and immutable: {overlap}")
    identity = registry.get("record_identity")
    if isinstance(identity, dict):
        locked = set(identity.get("logical_key_fields") or []) | set(
            identity.get("immutable_non_key_fields") or []
        )
        leaked = sorted(locked & set(block["amendable_fields"]))
        if leaked:
            lint.fail(
                registry_path,
                f"selector_amendment.amendable_fields may not include a record identity field: {leaked}",
            )

    amendable_rows = sorted(
        state_id
        for state_id, row in state_rows.items()
        if row.get("amendment_rule") == "closed_intent_atomic_replacement"
    )
    if amendable_rows != [amendable_state]:
        lint.fail(
            registry_path,
            "exactly one state may carry amendment_rule=closed_intent_atomic_replacement and it MUST be "
            f"selector_amendment.amendable_state {amendable_state!r}; found {amendable_rows}",
        )
    if state_rows[amendable_state]["ordinal"] != 1:
        lint.fail(registry_path, f"{amendable_state} may only be amendable as the first state of the chain")
    if state_rows[forbidden_from_state]["ordinal"] != state_rows[amendable_state]["ordinal"] + 1:
        lint.fail(
            registry_path,
            f"selector_amendment.forbidden_from_state must be the state immediately after {amendable_state}",
        )
    still_amendable = sorted(
        state_id
        for state_id, row in state_rows.items()
        if row.get("amendment_rule") != "forbidden"
        and row["ordinal"] >= state_rows[forbidden_from_state]["ordinal"]
    )
    if still_amendable:
        lint.fail(
            registry_path,
            f"the closed creation intent is immutable from {forbidden_from_state} on, but these states "
            f"still allow amendment: {still_amendable}",
        )
    if amendable_state not in state_rows[amendable_state]["allowed_exits"]:
        lint.fail(
            registry_path,
            f"{amendable_state} is amendable but does not list itself in allowed_exits",
        )
    for state_id, row in state_rows.items():
        if state_id != amendable_state and state_id in (row.get("allowed_exits") or []):
            lint.fail(
                registry_path,
                f"{state_id} forbids amendment but declares an in-place exit to itself",
            )
    return amendable_state


def check_mls_creator_bootstrap_transaction(lint: Lint) -> None:
    """Bind the creator bootstrap FSM to a crash vector on both sides of every arrow.

    encryption-and-audit.md section 5.1.2 registers one client-local durable
    transaction. The gap the ruling closed was that two conforming clients could
    each pick a different cut point, so the machine contract only helps if every
    registered arrow is proven crash-recoverable from both sides. This walks the
    registry and refuses an arrow, a state or a required durable field that no
    fixture case exercises.
    """

    registry_path = MLS_CREATOR_BOOTSTRAP_REGISTRY_PATH
    registry = load_json(lint, registry_path)
    if not isinstance(registry, dict):
        return
    if registry.get("source_of_truth") is not True:
        lint.fail(registry_path, "source_of_truth must be true")

    states = registry.get("states")
    if not isinstance(states, list) or not states:
        lint.fail(registry_path, "states must be a non-empty list")
        return

    state_rows: dict[str, dict[str, Any]] = {}
    ordinals: list[int] = []
    for index, row in enumerate(states):
        label = f"states[{index}]"
        if not isinstance(row, dict):
            lint.fail(registry_path, f"{label} must be an object")
            continue
        if tuple(row.keys()) != MLS_CREATOR_BOOTSTRAP_STATE_KEYS:
            lint.fail(
                registry_path,
                f"{label} must declare exactly {list(MLS_CREATOR_BOOTSTRAP_STATE_KEYS)} in that order",
            )
            continue
        state_id = row["state_id"]
        if not isinstance(state_id, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", state_id):
            lint.fail(registry_path, f"{label}.state_id must be a snake_case token")
            continue
        if state_id in state_rows:
            lint.fail(registry_path, f"{label}.state_id duplicates {state_id}")
        state_rows[state_id] = row
        if not isinstance(row["ordinal"], int) or isinstance(row["ordinal"], bool):
            lint.fail(registry_path, f"{state_id}.ordinal must be an integer")
        else:
            ordinals.append(row["ordinal"])
        if row["kind"] not in MLS_CREATOR_BOOTSTRAP_STATE_KINDS:
            lint.fail(
                registry_path,
                f"{state_id}.kind must be one of {sorted(MLS_CREATOR_BOOTSTRAP_STATE_KINDS)}",
            )
        for key in ("authority_source", "entry_predicate", "retry_rule", "gc_rule", "failure_disposition"):
            if not isinstance(row[key], str) or not row[key].strip():
                lint.fail(registry_path, f"{state_id}.{key} must be a non-empty string")
        fields = row["required_durable_fields"]
        if not isinstance(fields, list) or not fields or not all(
            isinstance(item, str) and item.strip() for item in fields
        ):
            lint.fail(
                registry_path,
                f"{state_id}.required_durable_fields must be a non-empty array of non-empty strings",
            )
        if row["amendment_rule"] not in MLS_CREATOR_BOOTSTRAP_AMENDMENT_RULES:
            lint.fail(
                registry_path,
                f"{state_id}.amendment_rule must be one of {sorted(MLS_CREATOR_BOOTSTRAP_AMENDMENT_RULES)}",
            )
        exits = row["allowed_exits"]
        if not isinstance(exits, list) or len(exits) != len(set(exits)):
            lint.fail(registry_path, f"{state_id}.allowed_exits must be a duplicate-free array")

    if ordinals != sorted(ordinals) or len(set(ordinals)) != len(ordinals):
        lint.fail(registry_path, "states[].ordinal must be unique and strictly increasing in file order")

    for state_id, row in state_rows.items():
        for target in row["allowed_exits"]:
            if target not in state_rows:
                lint.fail(registry_path, f"{state_id}.allowed_exits references unknown state: {target!r}")
        if row["kind"] in {"terminal_success", "terminal_failure"} and row["allowed_exits"]:
            if row["kind"] == "terminal_failure":
                lint.fail(registry_path, f"{state_id} is terminal_failure but declares an exit")
        if row["kind"] == "progress" and not row["allowed_exits"]:
            lint.fail(registry_path, f"{state_id} is a progress state with no exit")

    for state_id in MLS_CREATOR_BOOTSTRAP_PROGRESS_ORDER:
        if state_id not in state_rows:
            lint.fail(registry_path, f"the ruled progress chain requires state {state_id!r}")

    check_mls_creator_bootstrap_scope_kinds(lint, registry_path, registry)
    amendable_state = check_mls_creator_bootstrap_amendment(
        lint, registry_path, registry, state_rows
    )

    transitions = registry.get("transitions")
    if not isinstance(transitions, list) or not transitions:
        lint.fail(registry_path, "transitions must be a non-empty list")
        return

    transition_ids: list[str] = []
    for index, row in enumerate(transitions):
        label = f"transitions[{index}]"
        if not isinstance(row, dict):
            lint.fail(registry_path, f"{label} must be an object")
            continue
        if tuple(row.keys()) != MLS_CREATOR_BOOTSTRAP_TRANSITION_KEYS:
            lint.fail(
                registry_path,
                f"{label} must declare exactly {list(MLS_CREATOR_BOOTSTRAP_TRANSITION_KEYS)} in that order",
            )
            continue
        transition_id = row["transition_id"]
        if not isinstance(transition_id, str) or not transition_id:
            lint.fail(registry_path, f"{label}.transition_id must be a non-empty string")
            continue
        if transition_id in transition_ids:
            lint.fail(registry_path, f"{label}.transition_id duplicates {transition_id}")
        transition_ids.append(transition_id)
        from_state = row["from_state"]
        to_state = row["to_state"]
        if from_state is not None and from_state not in state_rows:
            lint.fail(registry_path, f"{transition_id}.from_state is not a registered state: {from_state!r}")
        if to_state not in state_rows:
            lint.fail(registry_path, f"{transition_id}.to_state is not a registered state: {to_state!r}")
        elif from_state is None:
            if state_rows[to_state]["ordinal"] != 1:
                lint.fail(registry_path, f"{transition_id} may only enter the first state")
        elif to_state not in state_rows[from_state]["allowed_exits"]:
            lint.fail(
                registry_path,
                f"{transition_id} is not listed in {from_state}.allowed_exits",
            )
        if from_state is not None and from_state == to_state and from_state != amendable_state:
            lint.fail(
                registry_path,
                f"{transition_id} is a self transition on {from_state}, but only the amendable state "
                "may re-enter itself; a state that forbids amendment MUST NOT carry an in-place arrow",
            )
        expected_id = f"{from_state or 'absent'}_to_{to_state}"
        if transition_id != expected_id:
            lint.fail(registry_path, f"{transition_id} must be named {expected_id}")
        for key in ("commit_boundary", "crash_before_commit", "crash_after_commit"):
            if not isinstance(row[key], str) or not row[key].strip():
                lint.fail(registry_path, f"{transition_id}.{key} must be a non-empty string")

    if amendable_state is not None:
        amendment_arrow = f"{amendable_state}_to_{amendable_state}"
        if amendment_arrow not in transition_ids:
            lint.fail(
                registry_path,
                f"selector_amendment names {amendable_state} amendable but {amendment_arrow} is not "
                "registered; an in-place amendment needs its own arrow so the crash vector covers it",
            )

    chain = ["absent_to_" + MLS_CREATOR_BOOTSTRAP_PROGRESS_ORDER[0]] + [
        f"{a}_to_{b}"
        for a, b in zip(
            MLS_CREATOR_BOOTSTRAP_PROGRESS_ORDER, MLS_CREATOR_BOOTSTRAP_PROGRESS_ORDER[1:]
        )
    ]
    missing_chain = [item for item in chain if item not in transition_ids]
    if missing_chain:
        lint.fail(registry_path, f"the ruled progress chain has unregistered arrows: {missing_chain}")

    fixture_path = MLS_CREATOR_BOOTSTRAP_FIXTURE_PATH
    fixture = load_json(lint, fixture_path)
    if not isinstance(fixture, dict):
        return
    if fixture.get("covers_vectors") != [MLS_CREATOR_BOOTSTRAP_VECTOR_ID]:
        lint.fail(fixture_path, f"covers_vectors must be exactly [{MLS_CREATOR_BOOTSTRAP_VECTOR_ID!r}]")
    if fixture.get("registry_under_test") != "spec/v1/artifacts/registry/mls-creator-bootstrap-transaction-registry.json":
        lint.fail(fixture_path, "registry_under_test must name the creator bootstrap transaction registry")
    assertions = fixture.get("global_assertions")
    if not isinstance(assertions, list) or len(assertions) < 3:
        lint.fail(fixture_path, "global_assertions must state the single-accepted-Genesis closure")

    crash_cases = fixture.get("crash_cases")
    if not isinstance(crash_cases, list) or not crash_cases:
        lint.fail(fixture_path, "crash_cases must be a non-empty list")
        return

    observed: set[tuple[str, str]] = set()
    for index, case in enumerate(crash_cases):
        label = f"crash_cases[{index}]"
        if not isinstance(case, dict):
            lint.fail(fixture_path, f"{label} must be an object")
            continue
        transition_id = case.get("transition")
        injection = case.get("injection")
        if transition_id not in transition_ids:
            lint.fail(fixture_path, f"{label}.transition is not a registered arrow: {transition_id!r}")
            continue
        if injection not in {"pre_commit", "post_commit"}:
            lint.fail(fixture_path, f"{label}.injection must be pre_commit or post_commit")
            continue
        suffix = "crash_before_commit" if injection == "pre_commit" else "crash_after_commit"
        if case.get("name") != f"{transition_id}__{suffix}":
            lint.fail(fixture_path, f"{label}.name must be {transition_id}__{suffix}")
        if (transition_id, injection) in observed:
            lint.fail(fixture_path, f"{label} duplicates {transition_id} {injection}")
        observed.add((transition_id, injection))
        if not isinstance(case.get("expected_state"), str) or not case["expected_state"].strip():
            lint.fail(fixture_path, f"{label}.expected_state must be a non-empty string")
        elif case["expected_state"] not in state_rows and case["expected_state"] != "absent":
            lint.fail(fixture_path, f"{label}.expected_state is not a registered state")
        if not isinstance(case.get("expected"), str) or not case["expected"].strip():
            lint.fail(fixture_path, f"{label}.expected must be a non-empty string")
        invariants = case.get("invariants")
        if not isinstance(invariants, list) or not invariants:
            lint.fail(fixture_path, f"{label}.invariants must be a non-empty array")

    for transition_id in transition_ids:
        for injection in ("pre_commit", "post_commit"):
            if (transition_id, injection) not in observed:
                lint.fail(
                    fixture_path,
                    f"arrow {transition_id} has no {injection} crash case; "
                    "every registered arrow needs a crash and reload on both sides",
                )

    scenario_cases = fixture.get("scenario_cases")
    if not isinstance(scenario_cases, list):
        lint.fail(fixture_path, "scenario_cases must be a list")
        return
    scenario_names = [
        case.get("name") for case in scenario_cases if isinstance(case, dict)
    ]
    missing_scenarios = [name for name in MLS_CREATOR_BOOTSTRAP_SCENARIOS if name not in scenario_names]
    if missing_scenarios:
        lint.fail(fixture_path, f"scenario_cases misses ruled failure coverage: {missing_scenarios}")
    for index, case in enumerate(scenario_cases):
        label = f"scenario_cases[{index}]"
        if not isinstance(case, dict):
            lint.fail(fixture_path, f"{label} must be an object")
            continue
        for key in ("name", "given", "action", "expected"):
            if not isinstance(case.get(key), str) or not case[key].strip():
                lint.fail(fixture_path, f"{label}.{key} must be a non-empty string")
        invariants = case.get("invariants")
        if not isinstance(invariants, list) or not invariants:
            lint.fail(fixture_path, f"{label}.invariants must be a non-empty array")
