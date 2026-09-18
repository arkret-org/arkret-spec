#!/usr/bin/env python3
"""Recompute the Applet delivery-authentication record KAT.

`applet-integration.md` §7.3.1 fixes a closed 14-member record that the receiver
derives from the verified HTTP message, and pins its digest to

    "sha256:" + lowerhex(SHA256(UTF8(domain + LF) || RFC8785_JCS(record)))

The conformance vector asserted `delivery_authentication_record_digest_is_domain_separated`
while carrying only a digest string: no record, no preimage, and nothing that
recomputes either.  A digest nobody can derive proves domain separation the way
a comment proves a lock.  This checker derives the record from the fixture's own
verified-request fields, rebuilds the preimage bytes, and requires the pinned
digest to be the one that falls out.

It lives outside the artifact lint for the same reason the SessionGrant KAT does:
it owns byte-level cryptographic construction, not registry shape.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "spec" / "v1"
ARTIFACTS = SPEC / "artifacts"
CONTRACT_PATH = ARTIFACTS / "registry" / "contract-registry.json"
GENERATED_OPERATION_PATH = ARTIFACTS / "registry" / "operation-registry.json"
SIGNATURE_ALG_PATH = ARTIFACTS / "registry" / "signature-alg-registry.json"
FIXTURE_PATH = ARTIFACTS / "fixtures" / "final-conformance-closure-fixture.json"
PROSE_PATH = SPEC / "zh" / "extensions" / "applet-integration.md"

OPERATION_ID = "ak.edge.applet.command.transaction.v1"
VECTOR_ID = "ak.vector.applet.transaction_delivery_authentication_record_digest.v1"
DIRECTIONS = {"node_to_applet", "applet_to_arkret_inbound"}

# §7.3.1: "MUST NOT 追加 Signature bytes、原始 Signature-Input 字符串、webhook
# 认证配置或请求摘要等本节未列出的成员".  The closed member set already excludes
# them; naming them makes the failure say which prohibition was broken.
FORBIDDEN_MEMBERS = {
    "signature",
    "signature_bytes",
    "signature_input",
    "webhook_auth",
    "request_digest",
    "domain",
    "profile",
}

RECORD_KEY = "delivery_authentication_record"
PREIMAGE_KEY = "delivery_authentication_record_canonical_bytes_utf8"
DIGEST_KEY = "delivery_authentication_record_digest"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _jcs_sort_key(name: str) -> bytes:
    """RFC 8785 orders property names by UTF-16 code unit."""
    return name.encode("utf-16-be")


def jcs_text(value: Any) -> str:
    if isinstance(value, dict):
        members = sorted(value.items(), key=lambda item: _jcs_sort_key(item[0]))
        body = ",".join(
            f"{json.dumps(key, ensure_ascii=False)}:{jcs_text(item)}"
            for key, item in members
        )
        return "{" + body + "}"
    if isinstance(value, list):
        return "[" + ",".join(jcs_text(item) for item in value) + "]"
    if isinstance(value, bool) or value is None:
        return json.dumps(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    raise TypeError(f"JCS: unsupported value {value!r}")


def record_digest(domain: str, record: dict[str, Any]) -> tuple[str, str]:
    """Return (canonical record bytes, "sha256:" digest) for one record.

    The returned text is JCS(record) alone. The domain is a prefix of the hash
    input, never a member of the record, so the fixture states the two halves
    separately and the artifact lint's stated-preimage pair re-checks the
    separator independently of this KAT.
    """
    canonical = jcs_text(record)
    digest = hashlib.sha256((domain + "\n" + canonical).encode("utf-8")).hexdigest()
    return canonical, f"sha256:{digest}"


def _service_signature(contract: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    operations = contract.get("operation_registry", {}).get("operations", [])
    matches = [
        operation
        for operation in operations
        if isinstance(operation, dict) and operation.get("operation_id") == OPERATION_ID
    ]
    if len(matches) != 1:
        errors.append(
            f"contract-registry.json must declare exactly one {OPERATION_ID}, found {len(matches)}"
        )
        return {}, errors
    signature = matches[0].get("auth_requirements", {}).get("service_signature")
    if not isinstance(signature, dict):
        errors.append(f"{OPERATION_ID} declares no service_signature contract")
        return {}, errors
    return signature, errors


def _record_contract(contract: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    signature, errors = _service_signature(contract)
    if not signature:
        return {}, errors
    record = signature.get(RECORD_KEY)
    if not isinstance(record, dict):
        errors.append(f"{OPERATION_ID} declares no {RECORD_KEY} contract")
        return {}, errors
    return record, errors


def check_projection(contract: dict[str, Any], generated: dict[str, Any]) -> list[str]:
    """The generated operation registry is a projection, not a second source."""
    errors: list[str] = []
    source, source_errors = _record_contract(contract)
    errors.extend(source_errors)
    if not source:
        return errors
    matches = [
        operation
        for operation in generated.get("operations", [])
        if isinstance(operation, dict) and operation.get("operation_id") == OPERATION_ID
    ]
    if len(matches) != 1:
        errors.append(
            f"operation-registry.json must project exactly one {OPERATION_ID}, found {len(matches)}"
        )
        return errors
    projected = (
        matches[0]
        .get("auth_requirements", {})
        .get("service_signature", {})
        .get(RECORD_KEY)
    )
    if projected != source:
        errors.append(
            f"operation-registry.json {RECORD_KEY} projection differs from contract-registry.json"
        )
    return errors


def check_prose(contract: dict[str, Any], prose: str) -> list[str]:
    """The prose owns the obligation; the contract must quote, not paraphrase."""
    errors: list[str] = []
    source, source_errors = _record_contract(contract)
    errors.extend(source_errors)
    if not source:
        return errors
    domain = source.get("digest_domain")
    if not isinstance(domain, str) or domain not in prose:
        errors.append(f"applet-integration.md does not carry digest domain {domain!r}")
    for field in source.get("closed_fields", []):
        if field not in prose:
            errors.append(f"applet-integration.md never names closed field {field!r}")
    # The domain separates only as a UTF-8 prefix: §7.3.1 forbids inserting it
    # into the record as a `domain` / `profile` member and hashing JCS(record).
    if f'UTF8("{domain}' not in prose:
        errors.append(
            "applet-integration.md does not state the UTF8(domain || LF) prefix construction"
        )
    return errors


def _derived_expectations(transaction: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    """The record members the fixture's verified request already determines.

    Only members whose value the request itself fixes are returned; the fixture
    is the authority for the rest (key digest, epoch, label).
    """
    install = case.get("active_install", {})
    expected = {
        "operation_id": transaction.get("arkret_operation"),
        "source_id": transaction.get("source_id_header"),
        "destination_id": transaction.get("destination_id_header"),
        "verification_method": transaction.get("keyid"),
        "idempotency_key": transaction.get("idempotency_key"),
        "content_digest": transaction.get("content_digest"),
        "covered_components": transaction.get("covered_components"),
        "created": transaction.get("created"),
        "expires": transaction.get("expires"),
        "registration_epoch": transaction.get("registration_epoch")
        or install.get("registration_epoch"),
    }
    return {key: value for key, value in expected.items() if value is not None}


def check_record(
    name: str,
    record: Any,
    declared_digest: Any,
    declared_preimage: Any,
    contract: dict[str, Any],
    required_components: list[str],
    transaction: dict[str, Any],
    case: dict[str, Any],
    algorithms: set[str],
) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return [f"{name}: {RECORD_KEY} must be an object"]

    closed = contract.get("closed_fields", [])
    present = set(record)
    missing = [field for field in closed if field not in present]
    extra = sorted(present - set(closed))
    if missing:
        errors.append(f"{name}: record omits closed member(s) {missing}")
    if extra:
        errors.append(f"{name}: record carries member(s) outside the closed set: {extra}")
    for member in sorted(present & FORBIDDEN_MEMBERS):
        errors.append(f"{name}: record carries forbidden member {member!r}")

    if record.get("direction") not in DIRECTIONS:
        errors.append(f"{name}: direction {record.get('direction')!r} is not one of {sorted(DIRECTIONS)}")
    if record.get("signature_algorithm") not in algorithms:
        errors.append(
            f"{name}: signature_algorithm {record.get('signature_algorithm')!r} "
            "is not an active http_message_signature_algorithm"
        )

    for key, value in _derived_expectations(transaction, case).items():
        if key in record and record[key] != value:
            errors.append(
                f"{name}: record {key}={record[key]!r} does not match the verified request {value!r}"
            )

    # The required set lives on the service_signature contract, one level above
    # the record: the record states what the receiver actually verified, and the
    # contract states the floor it may not fall below.
    required = required_components
    covered = record.get("covered_components")
    if isinstance(covered, list):
        absent = [component for component in required if component not in covered]
        if absent:
            errors.append(f"{name}: covered_components omits required component(s) {absent}")
    elif "covered_components" in closed:
        errors.append(f"{name}: covered_components must be an ordered list")

    domain = contract.get("digest_domain")
    if not isinstance(domain, str):
        return errors + [f"{name}: contract declares no digest_domain"]
    preimage, digest = record_digest(domain, record)
    if declared_digest != digest:
        errors.append(
            f"{name}: pinned digest {declared_digest!r} is not the recomputed {digest!r}"
        )
    if declared_preimage is not None and declared_preimage != preimage:
        errors.append(f"{name}: pinned canonical bytes do not match the recomputed JCS bytes")
    return errors


def _scenario_components(
    contract_registry: dict[str, Any],
    signature: dict[str, Any],
) -> tuple[list[str], list[str]]:
    """Resolve the required covered set through the canonical signature contract.

    Report 0110 moved the array off the operation: the operation names a scenario
    and the scenario owns the components, so this checker resolves the same way a
    receiver does instead of reading a copy that no longer exists.
    """
    scenario_id = signature.get("signature_scenario_id")
    if not isinstance(scenario_id, str):
        return [], [f"{OPERATION_ID} service_signature names no signature_scenario_id"]
    registry = contract_registry.get("http_signature_contract_registry")
    if not isinstance(registry, dict):
        return [], ["contract-registry.json carries no http_signature_contract_registry"]
    scenario = next(
        (
            row
            for row in registry.get("scenarios", [])
            if isinstance(row, dict) and row.get("scenario_id") == scenario_id
        ),
        None,
    )
    if scenario is None:
        return [], [f"{OPERATION_ID} names unregistered signature scenario {scenario_id}"]
    components = set(registry.get("common_contract", {}).get("covered_components", []))
    components.update(scenario.get("additional_covered_components", []))
    components.update(
        row.get("component")
        for row in scenario.get("conditional_covered_components", [])
        if isinstance(row, dict)
    )
    components.discard(None)
    if not components:
        return [], [f"{scenario_id} resolves to an empty covered set"]
    return sorted(components), []


def check_fixture(
    contract: dict[str, Any],
    fixture: dict[str, Any],
    signature_algorithms: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    signature, signature_errors = _service_signature(contract)
    errors.extend(signature_errors)
    source = signature.get(RECORD_KEY) if signature else None
    if not isinstance(source, dict):
        if signature:
            errors.append(f"{OPERATION_ID} declares no {RECORD_KEY} contract")
        return errors
    required_components, resolve_errors = _scenario_components(contract, signature)
    errors.extend(resolve_errors)

    algorithms = {
        row.get("http_message_signature_algorithm")
        for row in signature_algorithms.get("algorithms", [])
        if isinstance(row, dict) and row.get("status") == "active"
    }
    algorithms.discard(None)

    cases = [
        case
        for case in fixture.get("cases", [])
        if isinstance(case, dict) and case.get("vector_id") == VECTOR_ID
    ]
    if len(cases) != 1:
        return errors + [f"{FIXTURE_PATH.name} must carry exactly one {VECTOR_ID} case"]
    case = cases[0]
    transactions = {
        transaction.get("name"): transaction
        for transaction in case.get("transactions", [])
        if isinstance(transaction, dict)
    }

    digests: dict[str, Any] = {}
    carriers = 0
    for name, transaction in transactions.items():
        for holder in (transaction.get("expected", {}), transaction):
            if not isinstance(holder, dict) or RECORD_KEY not in holder:
                continue
            carriers += 1
            digests[name] = holder.get(DIGEST_KEY)
            errors.extend(
                check_record(
                    name,
                    holder.get(RECORD_KEY),
                    holder.get(DIGEST_KEY),
                    holder.get(PREIMAGE_KEY),
                    source,
                    required_components,
                    transaction,
                    case,
                    algorithms,
                )
            )
            break
    if carriers == 0:
        errors.append(
            f"{FIXTURE_PATH.name}: the vector asserts a domain-separated digest but "
            f"carries no {RECORD_KEY} to recompute it from"
        )

    # Replay equality is digest equality (§7.3.1): the cached delivery and the
    # byte-identical replay must agree, and the body-drift delivery must not.
    accepted = digests.get("valid_inbound")
    replay = transactions.get("exact_replay", {}).get(DIGEST_KEY)
    if accepted is not None and replay is not None and replay != accepted:
        errors.append("exact_replay: cached digest differs from the accepted delivery")
    drift = digests.get("idempotency_body_drift")
    if accepted is not None and drift is not None and drift == accepted:
        errors.append(
            "idempotency_body_drift: recomputed digest equals the cached one, so "
            "duplicate_conflict could not be detected"
        )
    return errors


def check_documents(
    contract: dict[str, Any],
    generated: dict[str, Any],
    prose: str,
    fixture: dict[str, Any],
    signature_algorithms: dict[str, Any],
) -> list[str]:
    return (
        check_projection(contract, generated)
        + check_prose(contract, prose)
        + check_fixture(contract, fixture, signature_algorithms)
    )


def main() -> int:
    errors = check_documents(
        load_json(CONTRACT_PATH),
        load_json(GENERATED_OPERATION_PATH),
        PROSE_PATH.read_text(encoding="utf-8"),
        load_json(FIXTURE_PATH),
        load_json(SIGNATURE_ALG_PATH),
    )
    for error in errors:
        print(f"applet-delivery-authentication-kat: {error}")
    if errors:
        return 1
    print(
        "applet-delivery-authentication-kat: record closed, projection consistent, "
        "digests recomputed from the pinned preimage"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
