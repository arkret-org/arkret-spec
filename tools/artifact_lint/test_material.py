"""Artifact lint: published test material, SDK clause evidence, claim binding.

Three checks land here because they share one failure mode: a normative
obligation whose *stated* evidence cannot be recomputed from the specification's
own artifacts, so the obligation quietly unbinds while every gate stays green.

``check_test_material_registry`` recomputes each registered fingerprint from the
fixture it points at and executes the three reserved-identifier matchers against
their own ``examples``/``non_examples``, so rotating a fixture key or loosening a
matcher turns the gate red instead of silently widening what a verifier admits.

``check_sdk_clause_vector_evidence`` resolves the SDK clause to vector mapping
that ``conformance-profiles.json#sdk_conformance_contract`` now carries. It
proves the mapping resolves; it deliberately does not read the requirement
sentences, which is why every decision point is reviewed when registered.

``check_sdk_claim_contract_binding`` recomputes ``contract_digest`` over the
contract and verifies the claim fixture's positive case signature under the
scheme its schema declares. Before this check the fixture's only ``expect_valid``
case carried bytes that did not verify, so an authenticator that honestly
verified the signature failed the case the specification calls valid.
"""

from __future__ import annotations

from .core import (
    ARTIFACTS,
    Any,
    Lint,
    Path,
    ROOT,
    base64,
    hashlib,
    json,
    load_json,
    re,
)

try:  # pragma: no cover - CI installs cryptography.
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
except ImportError:  # pragma: no cover
    InvalidSignature = None  # type: ignore[assignment]
    Ed25519PublicKey = None  # type: ignore[assignment]


def _registry_path() -> Path:
    return ARTIFACTS / "registry" / "test-material-registry.json"


def _contract_path() -> Path:
    return ARTIFACTS / "profiles" / "conformance-profiles.json"


def _vector_registry_path() -> Path:
    return ARTIFACTS / "registry" / "vector-registry.json"


def _claim_fixture_path() -> Path:
    return ARTIFACTS / "fixtures" / "sdk-conformance-claim-fixture.json"


def _fixtures_dir() -> Path:
    return ARTIFACTS / "fixtures"


CLAIM_DOMAIN = b"arkret-sdk-conformance-claim-v1\n"

VECTOR_ID_RE = re.compile(r"^ak\.vector\.[a-z0-9_]+(?:\.[a-z0-9_]+)+\.v[0-9]+$")
VECTOR_WILDCARD_RE = re.compile(r"^ak\.vector\.[a-z0-9_]+(?:\.[a-z0-9_]+)*\.\*$")
CLAUSE_ID_RE = re.compile(r"^AK-SDK-\d{3}$")
DECISION_POINT_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
MIN_REQUIREMENT_LENGTH = 16


# ----------------------------------------------------------------------
# shared helpers


def _jcs(value: Any) -> bytes:
    """RFC 8785 JCS bytes for the artifact subset used here.

    Every object the callers pass has ASCII member names and carries no
    floating-point number, so sorting by code point and emitting the compact
    separators is byte-identical to JCS.
    """
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )


def _b64u_decode(lint: Lint, path: Path, where: str, value: Any) -> bytes | None:
    if not isinstance(value, str) or not value:
        lint.fail(path, f"{where} must be a non-empty base64url string")
        return None
    padded = value + "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(padded.encode("ascii"))
    except Exception:
        lint.fail(path, f"{where} is not valid base64url")
        return None


def _resolve_pointer(document: Any, pointer: str) -> Any:
    if not pointer.startswith("/"):
        return None
    current = document
    for raw_token in pointer[1:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            if token not in current:
                return None
            current = current[token]
        elif isinstance(current, list):
            if not token.isdigit() or int(token) >= len(current):
                return None
            current = current[int(token)]
        else:
            return None
    return current


# ----------------------------------------------------------------------
# 1. test material registry


def _material_public_key(
    lint: Lint, registry: dict[str, Any], row: dict[str, Any], where: str
) -> bytes | None:
    """Recompute the row's public key bytes from the fixture it points at."""
    recomputation = row.get("recomputation")
    if not isinstance(recomputation, dict):
        lint.fail(_registry_path(), f"{where} must carry a recomputation block")
        return None
    fixture_ref = recomputation.get("fixture")
    scheme = recomputation.get("scheme")
    pointers = recomputation.get("pointers")
    schemes = registry.get("recomputation_schemes")
    if not isinstance(schemes, dict) or scheme not in schemes:
        lint.fail(_registry_path(), f"{where}.recomputation.scheme is not a registered scheme")
        return None
    if not isinstance(fixture_ref, str) or not isinstance(pointers, list) or not pointers:
        lint.fail(_registry_path(), f"{where}.recomputation must name a fixture and its pointers")
        return None
    fixture_path = ROOT / fixture_ref
    if not fixture_path.is_file():
        lint.fail(_registry_path(), f"{where}.recomputation.fixture does not exist: {fixture_ref}")
        return None
    if fixture_ref not in row.get("source_fixtures", []):
        lint.fail(
            _registry_path(),
            f"{where}.recomputation.fixture must also appear in source_fixtures",
        )
        return None
    document = load_json(lint, fixture_path)
    if document is None:
        return None

    values: list[bytes] = []
    for index, pointer in enumerate(pointers):
        if not isinstance(pointer, str):
            lint.fail(_registry_path(), f"{where}.recomputation.pointers[{index}] must be a string")
            return None
        target = _resolve_pointer(document, pointer)
        if target is None:
            lint.fail(
                _registry_path(),
                f"{where}.recomputation.pointers[{index}] does not resolve in {fixture_ref}: {pointer}",
            )
            return None
        decoded = _b64u_decode(
            lint, _registry_path(), f"{where}.recomputation.pointers[{index}]", target
        )
        if decoded is None:
            return None
        values.append(decoded)

    if scheme in {"jwk_okp_x_b64u", "raw_public_key_b64u"}:
        if len(values) != 1:
            lint.fail(_registry_path(), f"{where}.recomputation.{scheme} takes exactly one pointer")
            return None
        return values[0]
    if scheme == "jwk_ec_uncompressed_point_b64u":
        if len(values) != 2:
            lint.fail(
                _registry_path(),
                f"{where}.recomputation.{scheme} takes exactly two pointers, x then y",
            )
            return None
        return b"\x04" + values[0] + values[1]
    lint.fail(_registry_path(), f"{where}.recomputation.scheme is not implemented: {scheme}")
    return None


def _split_did(value: str) -> tuple[str, list[str]] | None:
    if not value.startswith("did:"):
        return None
    parts = value.split(":")
    if len(parts) < 3:
        return None
    return parts[1], parts[2:]


def _matches_did_rule(match: dict[str, Any], value: str) -> bool:
    if "#" in value or "?" in value:
        return False
    split = _split_did(value)
    if split is None:
        return False
    method, segments = split
    if method != match.get("method"):
        return False
    prefixes = match.get("scid_segment_prefixes") or []
    return any(segments[0].startswith(prefix) for prefix in prefixes)


def _matches_key_id_rule(match: dict[str, Any], value: str) -> bool:
    if "#" not in value:
        return False
    fragment = value.split("#", 1)[1]
    if not fragment:
        return False
    suffixes = match.get("fragment_suffixes") or []
    return any(fragment.endswith(suffix) for suffix in suffixes)


def _matches_trust_domain_rule(match: dict[str, Any], value: str) -> bool:
    prefix = str(match.get("typed_identifier", "")) + ":"
    if not value.startswith(prefix):
        return False
    domain = value[len(prefix) :]
    if not domain:
        return False
    if domain in (match.get("values") or []):
        return True
    reserved = match.get("reserved_top_labels") or []
    return domain.rsplit(".", 1)[-1] in reserved


_MATCHERS = {
    "did": _matches_did_rule,
    "key_id": _matches_key_id_rule,
    "trust_domain": _matches_trust_domain_rule,
}

_IDENTITY_ROLES = {"test_material", "deployment_like_example", "derived_positive"}
_WEBVH_VALUE_RE = re.compile(
    r"did:webvh:[A-Za-z0-9][A-Za-z0-9._%:-]*(?:#[A-Za-z0-9._-]+)?"
)


def _identity_example_sources() -> dict[str, list[str]]:
    """Closed corpus of concrete did:webvh examples in artifacts and normative prose."""
    found: dict[str, set[str]] = {}
    registry_path = _registry_path().resolve()
    candidates = [
        *ARTIFACTS.rglob("*.json"),
        *ARTIFACTS.rglob("*.yaml"),
        *ARTIFACTS.rglob("*.yml"),
        *(ROOT / "spec" / "v1" / "zh").rglob("*.md"),
    ]
    reports = (ARTIFACTS / "reports").resolve()
    for path in sorted(set(candidates)):
        resolved = path.resolve()
        if resolved == registry_path or reports in resolved.parents:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in _WEBVH_VALUE_RE.finditer(text):
            value = match.group(0).rstrip(".`")
            scid = value.split(":", 3)[2]
            if re.fullmatch(r"\d+\.\d+", scid) or "..." in value or value.endswith(":"):
                continue
            found.setdefault(value, set()).add(path.relative_to(ROOT).as_posix())
    return {value: sorted(sources) for value, sources in sorted(found.items())}


def _identity_is_reserved(identifier_rules: list[dict[str, Any]], value: str) -> bool:
    for row in identifier_rules:
        kind = row.get("kind")
        matcher = _MATCHERS.get(kind)
        match = row.get("match")
        if matcher is not None and isinstance(match, dict) and matcher(match, value):
            return True
    return False


def _check_identity_example_inventory(
    lint: Lint, registry: dict[str, Any], identifier_rules: list[dict[str, Any]]
) -> None:
    rows = registry.get("identity_examples")
    if not isinstance(rows, list):
        lint.fail(_registry_path(), "identity_examples must be a closed inventory array")
        return
    actual = _identity_example_sources()
    registered: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        where = f"identity_examples[{index}]"
        if not isinstance(row, dict):
            lint.fail(_registry_path(), f"{where} must be an object")
            continue
        value = row.get("value")
        role = row.get("role")
        expected_keys = {"value", "role", "sources"}
        if role == "derived_positive":
            expected_keys.add("derivation_ref")
        if set(row) != expected_keys:
            lint.fail(_registry_path(), f"{where} key set must be exactly {sorted(expected_keys)}")
            continue
        if not isinstance(value, str) or value not in actual:
            lint.fail(_registry_path(), f"{where}.value is not a concrete live did:webvh example")
            continue
        if value in registered:
            lint.fail(_registry_path(), f"{where}.value duplicates {value}")
            continue
        registered[value] = row
        if role not in _IDENTITY_ROLES:
            lint.fail(_registry_path(), f"{where}.role must be one of {sorted(_IDENTITY_ROLES)}")
            continue
        if row.get("sources") != actual[value]:
            lint.fail(_registry_path(), f"{where}.sources does not equal the live occurrence set")
        reserved = _identity_is_reserved(identifier_rules, value)
        if role == "test_material" and not reserved:
            lint.fail(_registry_path(), f"{where} is test_material but matches no reserved identifier rule")
        if role != "test_material" and reserved:
            lint.fail(_registry_path(), f"{where} role {role} MUST NOT enter the reserved namespace")
        if role == "derived_positive":
            ref = row.get("derivation_ref")
            if not isinstance(ref, str) or "#" not in ref:
                lint.fail(_registry_path(), f"{where}.derivation_ref must be a JSON Pointer reference")
                continue
            file_ref, pointer = ref.split("#", 1)
            document = load_json(lint, ROOT / file_ref)
            derived = _resolve_pointer(document, pointer)
            if derived != value:
                lint.fail(_registry_path(), f"{where}.derivation_ref does not resolve to its value")
    missing = sorted(set(actual) - set(registered))
    stale = sorted(set(registered) - set(actual))
    if missing:
        lint.fail(_registry_path(), f"identity_examples misses live values: {missing}")
    if stale:
        lint.fail(_registry_path(), f"identity_examples contains stale values: {stale}")


def check_test_material_registry(lint: Lint) -> None:
    """Prove the test-material registry is recomputable and its matchers work."""
    registry = load_json(lint, _registry_path())
    if not isinstance(registry, dict):
        lint.fail(_registry_path(), "test-material-registry.json must be a JSON object")
        return

    field_names = registry.get("published_signing_material_field_names")
    if not isinstance(field_names, list) or not field_names:
        lint.fail(_registry_path(), "published_signing_material_field_names must be a non-empty list")
        field_names = []

    encodings = registry.get("public_key_encodings")
    if not isinstance(encodings, dict) or not encodings:
        lint.fail(_registry_path(), "public_key_encodings must be a non-empty object")
        encodings = {}

    rows = registry.get("published_signing_material")
    if not isinstance(rows, list) or not rows:
        lint.fail(_registry_path(), "published_signing_material must be a non-empty list")
        rows = []

    seen_ids: set[str] = set()
    seen_fingerprints: set[str] = set()
    registered_fixtures: set[str] = set()
    for index, row in enumerate(rows):
        where = f"published_signing_material[{index}]"
        if not isinstance(row, dict):
            lint.fail(_registry_path(), f"{where} must be an object")
            continue
        row_id = row.get("id")
        if not isinstance(row_id, str) or not row_id:
            lint.fail(_registry_path(), f"{where}.id must be a non-empty string")
        elif row_id in seen_ids:
            lint.fail(_registry_path(), f"{where}.id duplicates {row_id}")
        else:
            seen_ids.add(row_id)
        where = f"published_signing_material[{row_id}]"

        for source in row.get("source_fixtures", []) or []:
            if isinstance(source, str):
                registered_fixtures.add(source)
                if not (ROOT / source).is_file():
                    lint.fail(_registry_path(), f"{where}.source_fixtures names a missing file: {source}")

        encoding_name = row.get("public_key_encoding")
        encoding = encodings.get(encoding_name) if isinstance(encoding_name, str) else None
        if not isinstance(encoding, dict):
            lint.fail(_registry_path(), f"{where}.public_key_encoding is not registered")
            continue

        public_key = _material_public_key(lint, registry, row, where)
        if public_key is None:
            continue
        expected_length = encoding.get("length_bytes")
        if isinstance(expected_length, int) and len(public_key) != expected_length:
            lint.fail(
                _registry_path(),
                f"{where} recomputed {len(public_key)} public key bytes, "
                f"but {encoding_name} is {expected_length}",
            )
            continue
        computed = "sha256:" + hashlib.sha256(public_key).hexdigest()
        if row.get("fingerprint") != computed:
            lint.fail(
                _registry_path(),
                f"{where}.fingerprint does not match the key its recomputation block points at: "
                f"registered {row.get('fingerprint')!r}, recomputed {computed!r}",
            )
        if computed in seen_fingerprints:
            lint.fail(_registry_path(), f"{where} duplicates an already registered fingerprint")
        seen_fingerprints.add(computed)

    public_rows = registry.get("public_fixture_keys")
    if public_rows is None:
        public_rows = []
    elif not isinstance(public_rows, list):
        lint.fail(_registry_path(), "public_fixture_keys must be an array when present")
        public_rows = []
    public_ids: set[str] = set()
    for index, row in enumerate(public_rows):
        where = f"public_fixture_keys[{index}]"
        if not isinstance(row, dict):
            lint.fail(_registry_path(), f"{where} must be an object")
            continue
        row_id = row.get("id")
        if not isinstance(row_id, str) or not row_id or row_id in public_ids:
            lint.fail(_registry_path(), f"{where}.id must be unique and non-empty")
            continue
        public_ids.add(row_id)
        fixture_ref = row.get("fixture")
        pointer = row.get("pointer")
        if not isinstance(fixture_ref, str) or not isinstance(pointer, str):
            lint.fail(_registry_path(), f"{where} must name fixture and pointer strings")
            continue
        fixture = load_json(lint, ROOT / fixture_ref)
        target = _resolve_pointer(fixture, pointer)
        if not isinstance(target, dict):
            lint.fail(_registry_path(), f"{where}.pointer does not resolve to a key object")
            continue
        if target.get("did") != row.get("did") or target.get("fingerprint") != row.get("fingerprint"):
            lint.fail(_registry_path(), f"{where} differs from its fixture key object")
        public_key = _public_key_from_did_key_url(row.get("did"))
        if public_key is None:
            lint.fail(_registry_path(), f"{where}.did is not a decodable Ed25519 did:key")
            continue
        computed = "sha256:" + hashlib.sha256(public_key).hexdigest()
        if row.get("fingerprint") != computed:
            lint.fail(_registry_path(), f"{where}.fingerprint recomputes to {computed}")

    identifiers = registry.get("reserved_identifiers")
    if not isinstance(identifiers, list) or not identifiers:
        lint.fail(_registry_path(), "reserved_identifiers must be a non-empty list")
        identifiers = []

    kinds_seen: set[str] = set()
    for index, row in enumerate(identifiers):
        where = f"reserved_identifiers[{index}]"
        if not isinstance(row, dict):
            lint.fail(_registry_path(), f"{where} must be an object")
            continue
        kind = row.get("kind")
        matcher = _MATCHERS.get(kind) if isinstance(kind, str) else None
        if matcher is None:
            lint.fail(_registry_path(), f"{where}.kind has no implemented matcher: {kind!r}")
            continue
        if kind in kinds_seen:
            lint.fail(_registry_path(), f"{where}.kind duplicates {kind}; the rules are independent")
        kinds_seen.add(kind)
        match = row.get("match")
        if not isinstance(match, dict):
            lint.fail(_registry_path(), f"{where}.match must be an object")
            continue
        examples = row.get("examples")
        non_examples = row.get("non_examples")
        if not isinstance(examples, list) or not examples:
            lint.fail(_registry_path(), f"{where}.examples must be a non-empty list")
            examples = []
        if not isinstance(non_examples, list) or not non_examples:
            lint.fail(_registry_path(), f"{where}.non_examples must be a non-empty list")
            non_examples = []
        for value in examples:
            if not isinstance(value, str) or not matcher(match, value):
                lint.fail(_registry_path(), f"{where}.examples entry does not match its rule: {value!r}")
        for value in non_examples:
            if not isinstance(value, str) or matcher(match, value):
                lint.fail(
                    _registry_path(), f"{where}.non_examples entry matches its rule: {value!r}"
                )

    for kind in _MATCHERS:
        if kind not in kinds_seen:
            lint.fail(_registry_path(), f"reserved_identifiers is missing the {kind} rule")

    _check_identity_example_inventory(lint, registry, identifiers)

    # Reverse scan: a fixture that publishes a private signing key MUST be registered.
    for fixture_path in sorted(_fixtures_dir().glob("*.json")):
        document = load_json(lint, fixture_path)
        if document is None:
            continue
        if not _carries_field(document, set(field_names)):
            continue
        relative = fixture_path.relative_to(ROOT).as_posix()
        if relative not in registered_fixtures:
            lint.fail(
                _registry_path(),
                f"{relative} publishes a private signing key but no published_signing_material "
                f"row lists it in source_fixtures",
            )


def _carries_field(node: Any, names: set[str]) -> bool:
    if isinstance(node, dict):
        if names & set(node):
            return True
        return any(_carries_field(value, names) for value in node.values())
    if isinstance(node, list):
        return any(_carries_field(value, names) for value in node)
    return False


_DID_KEY_IN_CANONICAL_JSON_RE = re.compile(r'"(did:key:z[^"\\]+)"')
_DID_KEY_MULTICODECS = {
    b"\xed\x01": ("Ed25519", 32),
    b"\xec\x01": ("X25519", 32),
}


def _decode_did_key(value: str) -> tuple[str | None, str | None]:
    bare = value.split("#", 1)[0]
    if not bare.startswith("did:key:z"):
        return None, "not a did:key base58btc value"
    multibase = bare.removeprefix("did:key:z")
    number = 0
    for character in multibase:
        position = _BASE58_ALPHABET.find(character)
        if position < 0:
            return None, f"{character!r} is not base58btc"
        number = number * 58 + position
    decoded = number.to_bytes((number.bit_length() + 7) // 8, "big")
    decoded = b"\x00" * (len(multibase) - len(multibase.lstrip("1"))) + decoded
    profile = next(
        ((name, length) for prefix, (name, length) in _DID_KEY_MULTICODECS.items() if decoded.startswith(prefix)),
        None,
    )
    if profile is None:
        return None, f"unregistered multicodec prefix {decoded[:2].hex()}"
    name, length = profile
    if len(decoded) != length + 2:
        return None, f"{name} carries {len(decoded) - 2} key bytes instead of {length}"
    if "#" in value and value.split("#", 1)[1] != "z" + multibase:
        return None, "did:key URL fragment does not repeat the multibase value"
    return name, None


def check_did_key_artifact_values(lint: Lint) -> None:
    """Decode every fixture did:key value; only the named malformed case may be invalid."""

    def visit(path: Path, node: Any, pointer: str, allowed_invalid_prefix: str | None) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                token = str(key).replace("~", "~0").replace("/", "~1")
                visit(path, value, f"{pointer}/{token}", allowed_invalid_prefix)
            return
        if isinstance(node, list):
            for index, value in enumerate(node):
                visit(path, value, f"{pointer}/{index}", allowed_invalid_prefix)
            return
        if not isinstance(node, str):
            return
        candidates: list[str] = []
        if node.startswith("did:key:z"):
            candidates.append(node)
        candidates.extend(match.group(1) for match in _DID_KEY_IN_CANONICAL_JSON_RE.finditer(node))
        for value in candidates:
            _, error = _decode_did_key(value)
            if error is None:
                continue
            if allowed_invalid_prefix is not None and pointer.startswith(allowed_invalid_prefix):
                continue
            lint.fail(path, f"{pointer}: {value!r} does not decode as a registered did:key: {error}")

    for path in sorted(_fixtures_dir().glob("*.json")):
        document = load_json(lint, path)
        if not isinstance(document, dict):
            continue
        invalid_prefix = None
        if path.name == "did-webvh-witness-fixture.json":
            cases = document.get("method_policy_cases")
            if isinstance(cases, list):
                matches = [
                    index
                    for index, case in enumerate(cases)
                    if isinstance(case, dict)
                    and case.get("name") == "undecodable_did_key_witness_fails_closed"
                    and case.get("semantic_outcome") == "reject"
                    and case.get("expected_reason_code") == "webvh_witness_parameter_malformed"
                ]
                if len(matches) == 1:
                    invalid_prefix = f"/method_policy_cases/{matches[0]}/parameters/"
        visit(path, document, "", invalid_prefix)


# ----------------------------------------------------------------------
# 2. SDK clause vector evidence


def _fixture_carriers(vector: dict[str, Any]) -> set[str]:
    carriers = {name for name in vector.get("applies_to_fixtures", []) if isinstance(name, str)}
    for ref in vector.get("source_refs", []):
        if isinstance(ref, str) and "/artifacts/fixtures/" in ref:
            carriers.add(ref.rsplit("/", 1)[-1])
    return carriers


def check_sdk_clause_vector_evidence(lint: Lint) -> None:
    """Prove every vector_result SDK clause maps onto resolvable vectors."""
    contract_document = load_json(lint, _contract_path())
    vector_document = load_json(lint, _vector_registry_path())
    if not isinstance(contract_document, dict) or not isinstance(vector_document, dict):
        return
    contract = contract_document.get("sdk_conformance_contract")
    if not isinstance(contract, dict):
        lint.fail(_contract_path(), "sdk_conformance_contract must be an object")
        return

    vectors = {
        entry["vector_id"]: entry
        for entry in vector_document.get("vectors", [])
        if isinstance(entry, dict) and isinstance(entry.get("vector_id"), str)
    }

    for key in (
        "vector_evidence_rule",
        "vector_evidence_carrier_ratchet_rule",
        "vector_evidence_carrier_ratchet_ceiling_rule",
    ):
        if not isinstance(contract.get(key), str) or not contract[key].strip():
            lint.fail(_contract_path(), f"sdk_conformance_contract.{key} must state the rule")

    # The ratchet prose says the list only shrinks, but prose cannot tell a
    # removed row from a newly added one. The ceiling is the controlled
    # baseline that can: it is the frozen set of pairs the ratchet was ever
    # allowed to hold, so a new gap cannot be made to disappear by writing one
    # more row with a plausible owner. Widening it is possible and deliberately
    # expensive -- the ceiling is inside sdk_conformance_contract, so editing it
    # moves contract_digest and invalidates the signed claim fixture.
    ceiling = contract.get("vector_evidence_carrier_ratchet_ceiling")
    ceiling_pairs: set[tuple[str, str]] = set()
    if not isinstance(ceiling, list):
        lint.fail(
            _contract_path(),
            "vector_evidence_carrier_ratchet_ceiling must be a list, even when it is empty",
        )
    else:
        for index, entry in enumerate(ceiling):
            where = f"vector_evidence_carrier_ratchet_ceiling[{index}]"
            if not isinstance(entry, dict):
                lint.fail(_contract_path(), f"{where} must be an object")
                continue
            pair = (entry.get("clause_id"), entry.get("vector_id"))
            if not isinstance(pair[0], str) or not isinstance(pair[1], str):
                lint.fail(_contract_path(), f"{where} must name a clause_id and a vector_id")
                continue
            if pair in ceiling_pairs:
                lint.fail(_contract_path(), f"{where} duplicates {pair[0]}/{pair[1]}")
            ceiling_pairs.add(pair)  # type: ignore[arg-type]

    ratchet = contract.get("vector_evidence_carrier_ratchet")
    if not isinstance(ratchet, list):
        lint.fail(_contract_path(), "vector_evidence_carrier_ratchet must be a list")
        ratchet = []
    ratchet_pairs: set[tuple[str, str]] = set()
    for index, entry in enumerate(ratchet):
        where = f"vector_evidence_carrier_ratchet[{index}]"
        if not isinstance(entry, dict):
            lint.fail(_contract_path(), f"{where} must be an object")
            continue
        pair = (entry.get("clause_id"), entry.get("vector_id"))
        if not isinstance(pair[0], str) or not isinstance(pair[1], str):
            lint.fail(_contract_path(), f"{where} must name a clause_id and a vector_id")
            continue
        if pair in ratchet_pairs:
            lint.fail(_contract_path(), f"{where} duplicates {pair[0]}/{pair[1]}")
        ratchet_pairs.add(pair)  # type: ignore[arg-type]
        owner = entry.get("owner_report")
        if not isinstance(owner, str) or not owner.strip():
            lint.fail(_contract_path(), f"{where} must name the report that owns the gap")
        if isinstance(ceiling, list) and pair not in ceiling_pairs:
            lint.fail(
                _contract_path(),
                f"{where} adds {pair[0]}/{pair[1]}, which the frozen "
                f"vector_evidence_carrier_ratchet_ceiling does not contain; the ratchet only "
                f"shrinks, so a new gap needs the ceiling widened and the claim re-signed, not "
                f"one more row",
            )

    used_ratchet_pairs: set[tuple[str, str]] = set()

    clauses = contract.get("clauses")
    if not isinstance(clauses, list) or not clauses:
        lint.fail(_contract_path(), "sdk_conformance_contract.clauses must be a non-empty list")
        return

    for clause in clauses:
        if not isinstance(clause, dict):
            lint.fail(_contract_path(), "every sdk_conformance_contract clause must be an object")
            continue
        clause_id = clause.get("clause_id")
        if not isinstance(clause_id, str) or not CLAUSE_ID_RE.match(clause_id):
            lint.fail(_contract_path(), f"clause_id is not an AK-SDK id: {clause_id!r}")
            continue
        required = clause.get("required_evidence")
        carries_vector_result = isinstance(required, list) and "vector_result" in required
        evidence = clause.get("vector_evidence")
        if not carries_vector_result:
            if evidence is not None:
                lint.fail(
                    _contract_path(),
                    f"{clause_id} carries vector_evidence but does not accept vector_result",
                )
            continue
        if not isinstance(evidence, dict):
            lint.fail(
                _contract_path(),
                f"{clause_id} accepts vector_result but carries no vector_evidence mapping",
            )
            continue

        declared = evidence.get("vectors")
        if not isinstance(declared, list) or not declared:
            lint.fail(_contract_path(), f"{clause_id}.vector_evidence.vectors must be non-empty")
            continue

        expanded: set[str] = set()
        malformed = False
        for entry in declared:
            if not isinstance(entry, str):
                lint.fail(_contract_path(), f"{clause_id}.vector_evidence.vectors must hold strings")
                malformed = True
                continue
            if VECTOR_WILDCARD_RE.match(entry):
                prefix = entry[:-1]
                matched = {name for name in vectors if name.startswith(prefix)}
                if not matched:
                    lint.fail(
                        _contract_path(),
                        f"{clause_id}.vector_evidence.vectors family expands to nothing: {entry}",
                    )
                    malformed = True
                    continue
                expanded |= matched
                continue
            if not VECTOR_ID_RE.match(entry):
                lint.fail(
                    _contract_path(),
                    f"{clause_id}.vector_evidence.vectors holds a malformed id: {entry!r}",
                )
                malformed = True
                continue
            if entry not in vectors:
                lint.fail(
                    _contract_path(),
                    f"{clause_id}.vector_evidence.vectors names an unregistered vector: {entry}",
                )
                malformed = True
                continue
            expanded.add(entry)
        if malformed or not expanded:
            continue

        for vector_id in sorted(expanded):
            vector = vectors[vector_id]
            if vector.get("status") != "active":
                lint.fail(
                    _contract_path(),
                    f"{clause_id} names {vector_id}, which is not active",
                )
            source_refs = vector.get("source_refs")
            if not isinstance(source_refs, list) or not source_refs:
                lint.fail(
                    _contract_path(),
                    f"{clause_id} names {vector_id}, which declares no source_refs",
                )
            carriers = _fixture_carriers(vector)
            pair = (clause_id, vector_id)
            if carriers:
                if pair in ratchet_pairs:
                    lint.fail(
                        _contract_path(),
                        f"vector_evidence_carrier_ratchet still lists {clause_id}/{vector_id}, "
                        f"which now has a fixture carrier; the ratchet only shrinks",
                    )
                for name in sorted(carriers):
                    fixture_path = _fixtures_dir() / name
                    if not fixture_path.is_file():
                        lint.fail(
                            _contract_path(),
                            f"{clause_id} names {vector_id}, whose carrier {name} does not exist",
                        )
                        continue
                    fixture = load_json(lint, fixture_path)
                    if isinstance(fixture, dict) and not isinstance(fixture.get("runner"), dict):
                        lint.fail(
                            _contract_path(),
                            f"{clause_id} names {vector_id}, whose carrier {name} declares no runner",
                        )
            elif pair in ratchet_pairs:
                used_ratchet_pairs.add(pair)
            else:
                lint.fail(
                    _contract_path(),
                    f"{clause_id} names {vector_id}, which no fixture carries and which "
                    f"vector_evidence_carrier_ratchet does not record",
                )

        points = evidence.get("decision_points")
        if not isinstance(points, list) or not points:
            lint.fail(_contract_path(), f"{clause_id}.vector_evidence.decision_points must be non-empty")
            continue
        seen_points: set[str] = set()
        for index, point in enumerate(points):
            where = f"{clause_id}.vector_evidence.decision_points[{index}]"
            if not isinstance(point, dict):
                lint.fail(_contract_path(), f"{where} must be an object")
                continue
            point_id = point.get("id")
            if not isinstance(point_id, str) or not DECISION_POINT_ID_RE.match(point_id):
                lint.fail(_contract_path(), f"{where}.id must be snake_case")
            elif point_id in seen_points:
                lint.fail(_contract_path(), f"{where}.id duplicates {point_id}")
            else:
                seen_points.add(point_id)
            requirement = point.get("requirement")
            if not isinstance(requirement, str) or len(requirement.strip()) < MIN_REQUIREMENT_LENGTH:
                lint.fail(
                    _contract_path(),
                    f"{where}.requirement must state the decision in at least "
                    f"{MIN_REQUIREMENT_LENGTH} characters",
                )
            point_vectors = point.get("vectors")
            if not isinstance(point_vectors, list) or not point_vectors:
                lint.fail(_contract_path(), f"{where}.vectors must name at least one vector")
                continue
            for entry in point_vectors:
                if not isinstance(entry, str) or not VECTOR_ID_RE.match(entry):
                    lint.fail(_contract_path(), f"{where}.vectors holds a malformed id: {entry!r}")
                    continue
                if entry not in expanded:
                    lint.fail(
                        _contract_path(),
                        f"{where}.vectors names {entry}, which is outside the clause's "
                        f"expanded vector set",
                    )

    stale = sorted(ratchet_pairs - used_ratchet_pairs)
    for clause_id, vector_id in stale:
        lint.fail(
            _contract_path(),
            f"vector_evidence_carrier_ratchet lists {clause_id}/{vector_id}, which no clause "
            f"mapping reaches; the ratchet only shrinks",
        )


# ----------------------------------------------------------------------
# 3. claim contract binding


def check_sdk_claim_contract_binding(lint: Lint) -> None:
    """Every claim case binds current contract except one explicit wrong-binding case."""
    contract_document = load_json(lint, _contract_path())
    fixture = load_json(lint, _claim_fixture_path())
    if not isinstance(contract_document, dict) or not isinstance(fixture, dict):
        return
    contract = contract_document.get("sdk_conformance_contract")
    if not isinstance(contract, dict):
        return
    if not isinstance(contract.get("contract_digest_computation"), str):
        lint.fail(
            _contract_path(),
            "sdk_conformance_contract.contract_digest_computation must state how the digest "
            "a claim binds is computed",
        )
        return
    expected_digest = "sha256:" + hashlib.sha256(_jcs(contract)).hexdigest()

    cases = fixture.get("schema_validation_cases")
    if not isinstance(cases, list) or not cases:
        lint.fail(_claim_fixture_path(), "schema_validation_cases must be a non-empty list")
        return
    positives = [case for case in cases if isinstance(case, dict) and case.get("expect_valid")]
    if not positives:
        lint.fail(
            _claim_fixture_path(),
            "the claim fixture must carry at least one expect_valid case, otherwise nothing "
            "pins the accepted shape",
        )
        return

    wrong_binding = [
        case for case in cases
        if isinstance(case, dict) and case.get("contract_binding_expect_valid") is False
    ]
    if len(wrong_binding) != 1:
        lint.fail(
            _claim_fixture_path(),
            "claim fixture must carry exactly one contract_binding_expect_valid=false case",
        )
    wrong_signature = [
        case for case in cases
        if isinstance(case, dict) and case.get("signature_expect_valid") is False
    ]
    if len(wrong_signature) != 1:
        lint.fail(
            _claim_fixture_path(),
            "claim fixture must carry exactly one signature_expect_valid=false case",
        )

    for case in cases:
        if not isinstance(case, dict):
            continue
        name = case.get("name", "<unnamed>")
        instance = case.get("instance")
        if not isinstance(instance, dict):
            lint.fail(_claim_fixture_path(), f"{name}.instance must be an object")
            continue
        binding_expected = case.get("contract_binding_expect_valid", True)
        if binding_expected not in (True, False):
            lint.fail(
                _claim_fixture_path(),
                f"{name}.contract_binding_expect_valid must be boolean when present",
            )
            continue
        signature_expected = case.get("signature_expect_valid", True)
        if signature_expected not in (True, False):
            lint.fail(
                _claim_fixture_path(),
                f"{name}.signature_expect_valid must be boolean when present",
            )
            continue
        if not signature_expected and (
            case.get("expect_valid") is not True
            or case.get("semantic_outcome") != "reject"
            or case.get("expected_reason_code") != "signature_invalid"
        ):
            lint.fail(
                _claim_fixture_path(),
                f"{name} signature-negative must be schema-valid and expect signature_invalid",
            )
        if binding_expected and instance.get("contract_digest") != expected_digest:
            lint.fail(
                _claim_fixture_path(),
                f"{name} binds a stale contract_digest: carries "
                f"{instance.get('contract_digest')!r}, contract recomputes to {expected_digest!r}",
            )
        if not binding_expected and instance.get("contract_digest") == expected_digest:
            lint.fail(
                _claim_fixture_path(),
                f"{name} is the dedicated wrong-binding case but carries the current digest",
            )
        proof = instance.get("proof")
        if not isinstance(proof, dict):
            lint.fail(_claim_fixture_path(), f"{name}.proof must be an object")
            continue
        if proof.get("signature_algorithm") != "Ed25519":
            lint.fail(_claim_fixture_path(), f"{name}.proof.signature_algorithm must be Ed25519")
            continue
        if Ed25519PublicKey is None:  # pragma: no cover - CI installs cryptography.
            lint.fail(_claim_fixture_path(), "cryptography is required to verify the claim signature")
            continue
        kid = proof.get("kid")
        public_key = _public_key_from_did_key_url(kid)
        if public_key is None:
            lint.fail(
                _claim_fixture_path(),
                f"{name}.proof.kid must be a did:key URL whose multibase value carries the "
                f"Ed25519 public key so the signature can be verified: {kid!r}",
            )
            continue
        signature = _b64u_decode(lint, _claim_fixture_path(), f"{name}.proof.signature", proof.get("signature"))
        if signature is None:
            continue
        body = {key: value for key, value in instance.items() if key != "proof"}
        try:
            Ed25519PublicKey.from_public_bytes(public_key).verify(
                signature, CLAIM_DOMAIN + _jcs(body)
            )
        except InvalidSignature:
            if signature_expected:
                lint.fail(
                    _claim_fixture_path(),
                    f"{name}: its signature does not verify under the scheme "
                    f"the schema declares (domain separator, LF, JCS of the object with proof omitted)",
                )
        except Exception as exc:  # pragma: no cover - malformed key bytes
            lint.fail(_claim_fixture_path(), f"{name} signature could not be verified: {exc}")
        else:
            if not signature_expected:
                lint.fail(
                    _claim_fixture_path(),
                    f"{name} is the dedicated wrong-signature case but its signature verifies",
                )


_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _public_key_from_did_key_url(value: Any) -> bytes | None:
    """Ed25519 public key bytes behind a ``did:key:z...`` URL, or None."""
    if not isinstance(value, str) or not value.startswith("did:key:z"):
        return None
    multibase = value.split("did:key:", 1)[1].split("#", 1)[0]
    number = 0
    for char in multibase[1:]:
        index = _BASE58_ALPHABET.find(char)
        if index < 0:
            return None
        number = number * 58 + index
    decoded = number.to_bytes((number.bit_length() + 7) // 8, "big")
    leading = len(multibase[1:]) - len(multibase[1:].lstrip("1"))
    decoded = b"\x00" * leading + decoded
    if not decoded.startswith(b"\xed\x01") or len(decoded) != 34:
        return None
    return decoded[2:]
