"""Close family-specific typed-current composite-key derivations.

Decision 0079 keeps ``result_selector.kind = composite`` as a closed, ordered
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

from .core import Lint, load_json
from .proof_context_schemas import EVENT_KIND_REGISTRY


_ALGORITHM_PROFILE = {
    "id": "ak.typed_current_key.sha256_domain_lf_jcs_array.v1",
    "preimage": "UTF8(domain) || 0x0A || RFC8785_JCS(normalized_components)",
    "output": "base64url_nopad(SHA-256(preimage))",
    "role": "opaque_current_row_locator",
    "public_generic_api": False,
    "authority_semantics": "none",
}

_FAMILIES = {
    "agent_interaction": {
        "derivation_id": "ak.current_key.agent_interaction.v1",
        "api_name": "derive_agent_interaction_current_key",
        "parameters": [("agent_account_id", "AccountId")],
        "components": [("agent_account_id", "rfc8785_jcs_value", {"payload.agent_account_id"})],
    },
    "member_state": {
        "derivation_id": "ak.current_key.member_state.v1",
        "api_name": "derive_member_state_current_key",
        "parameters": [("member_actor_id", "ActorId")],
        "components": [
            ("member_actor_id", "rfc8785_jcs_value", {"envelope.actor_id", "payload.member_id"})
        ],
    },
    "agent_status": {
        "derivation_id": "ak.current_key.agent_status.v1",
        "api_name": "derive_agent_status_current_key",
        "parameters": [("agent_actor_id", "ActorId")],
        "components": [
            ("agent_actor_id", "rfc8785_jcs_value", {"envelope.actor_id"})
        ],
    },
    "agent_key": {
        "derivation_id": "ak.current_key.agent_key.v1",
        "api_name": "derive_agent_key_current_key",
        "parameters": [("agent_id", "DidCoreId"), ("key_id", "AgentKeyId")],
        "components": [
            ("agent_id", "wire_scalar", {"payload.agent_id"}),
            ("key_id", "wire_scalar", {"item.key_id", "payload.key_id"}),
        ],
    },
    "key_backup_active_series": {
        "derivation_id": "ak.current_key.key_backup_active_series.v1",
        "api_name": "derive_key_backup_active_series_current_key",
        "parameters": [("actor_id", "ActorId"), ("backup_kind", "BackupKind")],
        "components": [
            ("actor_id", "rfc8785_jcs_value", {"payload.actor_id"}),
            ("backup_kind", "wire_scalar", {"payload.backup_kind"}),
        ],
    },
}

_ROW_KEYS = {
    "derivation_id",
    "result_family",
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


def _jcs(value: Any) -> str:
    """RFC 8785 spelling for the fixture's string/object-only value subset."""

    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


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


def _check_family_row(lint: Lint, row: Any, expected: dict[str, Any]) -> None:
    family = expected["result_family"]
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
        if parameter_type in {"ActorId", "AccountId"} and not isinstance(value, dict):
            _fail(lint, f"family {family!r} {parameter_type} KAT argument must be an object")
        elif parameter_type not in {"ActorId", "AccountId"} and not isinstance(value, str):
            _fail(lint, f"family {family!r} {parameter_type} KAT argument must be a string")
    if kat.get("normalized_components") != values:
        _fail(lint, f"family {family!r}.kat normalized components must preserve typed arguments")

    domain = row.get("domain")
    if not isinstance(domain, str):
        return
    preimage, output = _derive(domain, values)
    if kat.get("preimage_utf8") != preimage:
        _fail(lint, f"family {family!r}.kat.preimage_utf8 does not recompute")
    if kat.get("expected_output") != output:
        _fail(lint, f"family {family!r}.kat.expected_output does not recompute")

    negatives = kat.get("negative_cases")
    if not isinstance(negatives, dict) or set(negatives) != {
        "reordered_components",
        "wrong_family_domain",
        "extra_component",
        "type_mismatch",
    }:
        _fail(lint, f"family {family!r}.kat.negative_cases is not the closed mutation set")
        return
    if negatives.get("extra_component") != {"disposition": "reject_before_hash"}:
        _fail(lint, f"family {family!r} must reject an extra component before hashing")
    if negatives.get("type_mismatch") != {"disposition": "reject_before_hash"}:
        _fail(lint, f"family {family!r} must reject a typed-parameter mismatch before hashing")

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
            _, mutation_output = _derive(mutation_domain, values)
            if wrong_domain.get("expected_output") != mutation_output or mutation_output == output:
                _fail(lint, f"family {family!r} wrong-family-domain KAT does not diverge")


def _check_selector_alignment(lint: Lint, registry: dict[str, Any], rows_by_family: dict[str, Any]) -> None:
    seen: dict[str, list[set[str]]] = {
        family: [set() for _ in expected["components"]]
        for family, expected in _FAMILIES.items()
    }
    live_count = {family: 0 for family in _FAMILIES}
    call_mute_selectors: list[Any] = []

    for event in registry.get("event_kinds") or ():
        if not isinstance(event, dict):
            continue
        for write in event.get("result_writes") or ():
            if not isinstance(write, dict):
                continue
            family = write.get("result_family")
            selector = write.get("result_selector")
            if family == "call_mute_override":
                call_mute_selectors.append(selector)
            if family not in _FAMILIES:
                continue
            live_count[family] += 1
            components = selector.get("components") if isinstance(selector, dict) else None
            if not isinstance(selector, dict) or selector.get("kind") != "composite":
                _fail(lint, f"active family {family!r} must use its registered composite descriptor")
                continue
            expected_components = _FAMILIES[family]["components"]
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

    for family, expected in _FAMILIES.items():
        if live_count[family] == 0:
            _fail(lint, f"registered family {family!r} has no active selector")
        for index, (_, _, sources) in enumerate(expected["components"]):
            if seen[family][index] != sources:
                _fail(lint, f"family {family!r} component {index} source coverage drifted")
        if family not in rows_by_family:
            _fail(lint, f"active family {family!r} has no typed derivation row")

    if call_mute_selectors != [{"kind": "composite", "components": ["payload.call_id"]}]:
        _fail(lint, "call_mute_override must remain the active one-component [call_id] family")
    if "call_mute_override" in rows_by_family:
        _fail(lint, "the legacy per-leg mute caller must not gain a compatibility derivation")


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

    expected_audit = {
        "soland_missing_helper_callers": 10,
        "active_family_callers": 9,
        "registered_active_families": len(_FAMILIES),
        "excluded_per_leg_mute": {
            "observed_component_order": ["call_id", "actor_id", "device_id"],
            "active_result_family": "call_mute_override",
            "active_component_order": ["payload.call_id"],
            "disposition": "no_compatibility_api_fail_closed",
        },
    }
    if contract.get("coverage_audit") != expected_audit:
        _fail(lint, "coverage_audit must preserve the 9 active callers plus 1 rejected legacy caller")

    rows = contract.get("families")
    if not isinstance(rows, list):
        _fail(lint, "families must be an array")
        return
    rows_by_family: dict[str, Any] = {}
    for row in rows:
        family = row.get("result_family") if isinstance(row, dict) else None
        if family == "call_mute_override":
            _fail(lint, "the legacy per-leg mute caller must not gain a compatibility derivation")
        if not isinstance(family, str) or family not in _FAMILIES or family in rows_by_family:
            _fail(lint, f"families contains unknown or duplicate result_family {family!r}")
            continue
        rows_by_family[family] = row
        expected = dict(_FAMILIES[family])
        expected["result_family"] = family
        _check_family_row(lint, row, expected)
    if set(rows_by_family) != set(_FAMILIES):
        _fail(lint, f"families must be exactly {sorted(_FAMILIES)}")
    if "composite_subject" in json.dumps(contract, ensure_ascii=False):
        _fail(lint, "must not publish the retired generic composite_subject name")
    _check_selector_alignment(lint, registry, rows_by_family)


def check_typed_current_key_derivations(lint: Lint) -> None:
    """Validate generated event-kind metadata, KATs and live selector alignment."""

    _check_typed_current_key_derivations(lint, load_json(lint, EVENT_KIND_REGISTRY))
