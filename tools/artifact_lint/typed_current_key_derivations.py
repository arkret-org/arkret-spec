"""Close family-specific typed-current composite-key derivations.

Decision 0079 keeps ``state_selector.kind = composite`` as a closed, ordered
family descriptor while forbidding the old generic ``composite_subject`` API.
This gate pins the registered active families, their generated API metadata,
their selector sources and their domain-separated KATs.  The digest is only a
row locator; it has no authority semantics.
"""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from tools.reference_json import jcs_text as _jcs

from .core import ARTIFACTS, Lint, load_json
from .proof_context_schemas import EVENT_KIND_REGISTRY


_ALGORITHM_PROFILE = {
    "id": "ak.typed_current_key.sha256_domain_lf_jcs_array.v1",
    "preimage": "UTF8(domain) || 0x0A || RFC8785_JCS(normalized_components)",
    "output": "base64url_nopad(SHA-256(preimage))",
    "role": "opaque_current_row_locator",
    "public_generic_api": False,
    "authority_semantics": "none",
}

_ROW_KEYS = {
    "derivation_id",
    "state_family",
    "api_name",
    "parameters",
    "domain",
    "components",
    "kat",
}
_KAT_KEYS = {
    "arguments",
    "normalized_components",
    "preimage_utf8",
    "expected_output",
    "negative_cases",
}


def _derive(domain: str, components: list[Any]) -> tuple[str, str]:
    preimage = f"{domain}\n{_jcs(components)}"
    digest = hashlib.sha256(preimage.encode("utf-8")).digest()
    return preimage, base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _selector_component(component: Any) -> tuple[str | None, str | None]:
    if isinstance(component, str):
        return "wire_scalar", component
    if isinstance(component, dict) and component.get("kind") == "canonical_json":
        field = component.get("field")
        return "rfc8785_jcs_value", field if isinstance(field, str) else None
    return None, None


def _fail(lint: Lint, message: str) -> None:
    lint.fail(EVENT_KIND_REGISTRY, f"typed_current_key_derivations {message}")


def _registered_families(lint: Lint) -> tuple[dict[str, Any], Any]:
    """Read API metadata from its canonical contract, independently of codegen."""
    document = load_json(lint, ARTIFACTS / "registry/contract-registry.json")
    try:
        contract = document["event_kind_registry"]["typed_current_key_derivations"]
        families = {}
        for row in contract["families"]:
            family = row["state_family"]
            if family in families:
                raise ValueError("duplicate family")
            families[family] = {
                "state_family": family,
                "derivation_id": row["derivation_id"],
                "api_name": row["api_name"],
                "parameters": [(p["name"], p["value_shape"]) for p in row["parameters"]],
                "components": [
                    (c["parameter"], c["normalization"], set(c["registry_sources"]))
                    for c in row["components"]
                ],
            }
        return families, contract["coverage_audit"]
    except (KeyError, TypeError, ValueError):
        _fail(lint, "canonical family metadata is malformed")
        return {}, None


def _check_family_row(lint: Lint, row: Any, expected: dict[str, Any]) -> None:
    family = expected["state_family"]
    if not isinstance(row, dict):
        _fail(lint, f"family {family!r} must be an object")
        return
    if set(row) != _ROW_KEYS:
        _fail(lint, f"family {family!r} members must be exactly {sorted(_ROW_KEYS)}")

    for member in ("derivation_id", "api_name"):
        if row.get(member) != expected[member]:
            _fail(lint, f"family {family!r}.{member} must be {expected[member]!r}")
    if row.get("domain") != expected["derivation_id"]:
        _fail(lint, f"family {family!r}.domain must equal its derivation_id")
    api_name = row.get("api_name")
    if not isinstance(api_name, str) or "composite_subject" in api_name:
        _fail(lint, f"family {family!r} must expose only its family-specific typed API")

    expected_parameters = [
        {"name": name, "value_shape": parameter_type}
        for name, parameter_type in expected["parameters"]
    ]
    if row.get("parameters") != expected_parameters:
        _fail(lint, f"family {family!r}.parameters drifted from the closed typed signature")

    components = row.get("components")
    if not isinstance(components, list) or len(components) != len(expected["components"]):
        _fail(lint, f"family {family!r}.components has the wrong arity")
    else:
        for index, (component, (parameter, normalization, sources)) in enumerate(
            zip(components, expected["components"])
        ):
            wanted = {
                "parameter": parameter,
                "normalization": normalization,
                "registry_sources": sorted(sources),
            }
            if component != wanted:
                _fail(lint, f"family {family!r}.components[{index}] drifted from {wanted!r}")

    kat = row.get("kat")
    if not isinstance(kat, dict):
        _fail(lint, f"family {family!r}.kat must be an object")
        return
    if set(kat) != _KAT_KEYS:
        _fail(lint, f"family {family!r}.kat members must be exactly {sorted(_KAT_KEYS)}")
    arguments = kat.get("arguments")
    if not isinstance(arguments, dict):
        _fail(lint, f"family {family!r}.kat.arguments must be an object")
        return
    parameter_names = [name for name, _ in expected["parameters"]]
    if list(arguments) != parameter_names:
        _fail(lint, f"family {family!r}.kat.arguments must follow the typed parameter order")
        return
    values = [arguments[name] for name in parameter_names]
    for value, (_, parameter_type) in zip(values, expected["parameters"]):
        if parameter_type in {"ActorId", "AccountId", "RealmActorId", "ScopeRef"} and not isinstance(value, dict):
            _fail(lint, f"family {family!r} {parameter_type} KAT argument must be an object")
        elif parameter_type not in {"ActorId", "AccountId", "RealmActorId", "ScopeRef"} and not isinstance(value, str):
            _fail(lint, f"family {family!r} {parameter_type} KAT argument must be a string")
    if kat.get("normalized_components") != values:
        _fail(lint, f"family {family!r}.kat normalized components must preserve typed arguments")

    domain = row.get("domain")
    if not isinstance(domain, str):
        return
    try:
        preimage, output = _derive(domain, values)
    except (ValueError, TypeError) as error:
        _fail(lint, f"family {family!r}.kat input is outside the reference JSON subset: {error}")
        return
    if kat.get("preimage_utf8") != preimage:
        _fail(lint, f"family {family!r}.kat.preimage_utf8 does not recompute")
    if kat.get("expected_output") != output:
        _fail(lint, f"family {family!r}.kat.expected_output does not recompute")

    negatives = kat.get("negative_cases")
    required_negatives = {"reordered_components", "wrong_family_domain", "extra_component", "type_mismatch"}
    if family == "realm_actor_key_backup_active_series":
        required_negatives |= {"wrong_actor_kind", "cross_realm_scope", "scope_omitted", "unsupported_sidecar"}
    if not isinstance(negatives, dict) or set(negatives) != required_negatives:
        _fail(lint, f"family {family!r}.kat.negative_cases is not the closed mutation set")
        return
    if negatives.get("extra_component") != {"disposition": "reject_before_hash"}:
        _fail(lint, f"family {family!r} must reject an extra component before hashing")
    if negatives.get("type_mismatch") != {"disposition": "reject_before_hash"}:
        _fail(lint, f"family {family!r} must reject a typed-parameter mismatch before hashing")

    if family == "realm_actor_key_backup_active_series":
        from tools.realm_actor_backup_contract import derive_native_series_current_key
        try:
            _, typed_output = derive_native_series_current_key(*values)
            if typed_output != output:
                _fail(lint, "native scope current-key typed derivation disagrees with its JCS KAT")
        except (ValueError, TypeError):
            _fail(lint, "native current-key KAT does not satisfy its closed typed input")
        for name in ["wrong_actor_kind", "cross_realm_scope", "scope_omitted", "unsupported_sidecar"]:
            if negatives.get(name) != {"disposition": "reject_before_hash"}:
                _fail(lint, f"native current-key {name} must reject before hashing")
        if len(values) == 3 and isinstance(values[0], dict) and isinstance(values[1], dict):
            invalid = [
                ({"kind": "realm", "realm_actor_id": values[0]}, values[1], values[2]),
                (values[0], {**values[1], "realm_id": "ak:realm:other"}, values[2]),
                (values[0], None, values[2]),
                (values[0], {**values[1], "kind": "sidecar"}, values[2]),
            ]
            for arguments in invalid:
                try:
                    derive_native_series_current_key(*arguments)
                except (ValueError, TypeError):
                    pass
                else:
                    _fail(lint, "native current-key typed mutation unexpectedly hashes")

    reordered = negatives.get("reordered_components")
    if len(values) == 1:
        if reordered != {"disposition": "not_applicable_single_component"}:
            _fail(lint, f"family {family!r} must mark reorder inapplicable at arity one")
    else:
        _, reordered_output = _derive(domain, list(reversed(values)))
        if reordered != {"expected_output": reordered_output} or reordered_output == output:
            _fail(lint, f"family {family!r} reordered-component KAT does not diverge")

    wrong_domain = negatives.get("wrong_family_domain")
    if not isinstance(wrong_domain, dict) or set(wrong_domain) != {"domain", "expected_output"}:
        _fail(lint, f"family {family!r} wrong-family-domain KAT must be closed")
    else:
        mutation_domain = wrong_domain.get("domain")
        if not isinstance(mutation_domain, str) or mutation_domain == domain:
            _fail(lint, f"family {family!r} wrong-family-domain mutation must change domain")
        else:
            try:
                _, mutation_output = _derive(mutation_domain, values)
            except (ValueError, TypeError) as error:
                _fail(lint, f"family {family!r} wrong-family-domain input is invalid: {error}")
                return
            if wrong_domain.get("expected_output") != mutation_output or mutation_output == output:
                _fail(lint, f"family {family!r} wrong-family-domain KAT does not diverge")


def _check_selector_alignment(
    lint: Lint, registry: dict[str, Any], rows_by_family: dict[str, Any], families: dict[str, Any]
) -> None:
    seen: dict[str, list[set[str]]] = {
        family: [set() for _ in expected["components"]]
        for family, expected in families.items()
    }
    live_count = {family: 0 for family in families}
    call_mute_selectors: list[Any] = []

    for event in registry.get("event_kinds") or ():
        if not isinstance(event, dict):
            continue
        for write in event.get("state_writes") or ():
            if not isinstance(write, dict):
                continue
            family = write.get("state_family")
            selector = write.get("state_selector")
            if family == "call_mute_override":
                call_mute_selectors.append(selector)
            if family not in families:
                continue
            live_count[family] += 1
            components = selector.get("components") if isinstance(selector, dict) else None
            if not isinstance(selector, dict) or selector.get("kind") != "composite":
                _fail(lint, f"active family {family!r} must use its registered composite descriptor")
                continue
            expected_components = families[family]["components"]
            if not isinstance(components, list) or len(components) != len(expected_components):
                _fail(lint, f"active family {family!r} selector arity disagrees with its derivation")
                continue
            for index, (component, (_, normalization, allowed_sources)) in enumerate(
                zip(components, expected_components)
            ):
                actual_normalization, source = _selector_component(component)
                if actual_normalization != normalization or source not in allowed_sources:
                    _fail(
                        lint,
                        f"active family {family!r} selector component {index} is not registered",
                    )
                elif source is not None:
                    seen[family][index].add(source)

    for family, expected in families.items():
        if live_count[family] == 0:
            _fail(lint, f"registered family {family!r} has no active selector")
        for index, (_, _, sources) in enumerate(expected["components"]):
            if seen[family][index] != sources:
                _fail(lint, f"family {family!r} component {index} source coverage drifted")
        if family not in rows_by_family:
            _fail(lint, f"active family {family!r} has no typed derivation row")

    if call_mute_selectors != [{"kind": "composite", "components": ["payload.call_id"]}]:
        _fail(lint, "call_mute_override must remain the active one-component [call_id] family")


def _check_typed_current_key_derivations(lint: Lint, registry: Any) -> None:
    if not isinstance(registry, dict):
        _fail(lint, "registry must be an object")
        return
    contract = registry.get("typed_current_key_derivations")
    if not isinstance(contract, dict) or set(contract) != {
        "algorithm_profile",
        "coverage_audit",
        "families",
    }:
        _fail(lint, "must contain exactly algorithm_profile, coverage_audit, and families")
        return
    if contract.get("algorithm_profile") != _ALGORITHM_PROFILE:
        _fail(lint, "algorithm_profile drifted from the locator-only domain-separated profile")

    families, expected_audit = _registered_families(lint)
    if contract.get("coverage_audit") != expected_audit:
        _fail(lint, "coverage_audit must match the canonical contract")

    rows = contract.get("families")
    if not isinstance(rows, list):
        _fail(lint, "families must be an array")
        return
    rows_by_family: dict[str, Any] = {}
    for row in rows:
        family = row.get("state_family") if isinstance(row, dict) else None
        if not isinstance(family, str) or family not in families or family in rows_by_family:
            _fail(lint, f"families contains unknown or duplicate state_family {family!r}")
            continue
        rows_by_family[family] = row
        expected = dict(families[family])
        expected["state_family"] = family
        _check_family_row(lint, row, expected)
    if set(rows_by_family) != set(families):
        _fail(lint, f"families must be exactly {sorted(families)}")
    if "composite_subject" in json.dumps(contract, ensure_ascii=False):
        _fail(lint, "must not publish the retired generic composite_subject name")
    _check_selector_alignment(lint, registry, rows_by_family, families)


def check_typed_current_key_derivations(lint: Lint) -> None:
    """Validate generated event-kind metadata, KATs and live selector alignment."""

    _check_typed_current_key_derivations(lint, load_json(lint, EVENT_KIND_REGISTRY))
