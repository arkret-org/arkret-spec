"""Closure between the canonical HTTP Message Signature contract and its projections.

``contract-registry.json`` carries ``http_signature_contract_registry``: the single
owner of every RFC 9421 covered set, trigger condition and freshness numeral in the
spec.  Before report 0110 those facts lived in eight hand-kept prose enumerations, two
conformance-profile sentences and one fixture, and nothing compared them; editing one
copy turned no test red.

This module makes each copy a checked projection:

* a prose page states a covered set only inside an explicitly delimited block that
  names the scenario it projects, and the tokens inside that block must be exactly the
  scenario's applicable components -- no regex is asked to guess which words in a
  sentence were meant as components;
* a page that is not a declared binding may not enumerate a covered set at all;
* the window numerals appear in one block on one page, and the phrase that defines the
  window may not appear anywhere else;
* an operation binds a scenario by id and may not restate the array or the numbers.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .core import ARTIFACTS, SPEC_ROOT, Lint, load_json, read_text

REGISTRY_KEY = "http_signature_contract_registry"
CONTRACT_REGISTRY = ARTIFACTS / "registry" / "contract-registry.json"

COVERED_SET_BEGIN_RE = re.compile(
    r"<!--\s*BEGIN ak-http-signature-covered-set\s+(?P<scenario>\S+)\s*-->"
)
COVERED_SET_END = "<!-- END ak-http-signature-covered-set -->"
FRESHNESS_BEGIN_RE = re.compile(
    r"<!--\s*BEGIN ak-http-signature-freshness\s+(?P<profile>\S+)\s*-->"
)
FRESHNESS_END = "<!-- END ak-http-signature-freshness -->"

BACKTICKED_RE = re.compile(r"`([^`]+)`")
INTEGER_RE = re.compile(r"(?<![\w.])(\d+)(?![\w.])")

# A page that enumerates a covered set outside a declared block is the failure mode
# this gate exists for, so the detector is deliberately blunt: the two derived
# components that every scenario shares.
ENUMERATION_MARKERS = ("@target-uri", "@authority")

# The one phrase that states the window. Only the canonical block may carry it.
WINDOW_PHRASE_RE = re.compile(r"expires\s*-\s*created|expires-created")


def _blocks(text: str, begin_re: re.Pattern[str], end: str) -> list[tuple[str, str, int]]:
    """Return (name, body, line) for each delimited block, in document order."""
    found: list[tuple[str, str, int]] = []
    for match in begin_re.finditer(text):
        stop = text.find(end, match.end())
        if stop == -1:
            continue
        found.append(
            (
                match.group(1),
                text[match.end():stop],
                text[: match.start()].count("\n") + 1,
            )
        )
    return found


def _unterminated(text: str, begin_re: re.Pattern[str], end: str) -> list[str]:
    names = []
    for match in begin_re.finditer(text):
        if text.find(end, match.end()) == -1:
            names.append(match.group(1))
    return names


def _prose_pages() -> list[Path]:
    return sorted((SPEC_ROOT / "zh").rglob("*.md"))


def _rel(path: Path) -> str:
    return f"zh/{path.relative_to(SPEC_ROOT / 'zh').as_posix()}"


def _resolve_pointer(data: Any, pointer: str) -> Any:
    current = data
    for raw in pointer.split("/"):
        if raw == "":
            continue
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            if not token.isdigit() or int(token) >= len(current):
                return None
            current = current[int(token)]
        elif isinstance(current, dict):
            if token not in current:
                return None
            current = current[token]
        else:
            return None
    return current


_SCENARIO_KEYS = frozenset(
    {
        "scenario_id",
        "label",
        "applies_to",
        "extends",
        "additional_covered_components",
        "conditional_covered_components",
        "required_headers",
        "freshness_profile_id",
        "prose_bindings",
        "machine_projections",
        "freshness_projections",
        "operations",
        "vectors",
        "error_codes",
    }
)

# A profile that no scenario resolves, and that is deliberately so: DPoP is a separate
# standard with its own carrier, not an RFC 9421 signing scenario.
_STANDALONE_PROFILES = frozenset({"ak.dpop.freshness.v1"})


def check_http_signature_contract_closure(lint: Lint) -> None:
    catalog = load_json(lint, CONTRACT_REGISTRY)
    if not isinstance(catalog, dict):
        return
    registry = catalog.get(REGISTRY_KEY)
    if not isinstance(registry, dict):
        lint.fail(CONTRACT_REGISTRY, f"{REGISTRY_KEY} is missing")
        return

    vocabulary = {
        row.get("component")
        for row in registry.get("component_vocabulary", [])
        if isinstance(row, dict)
    }
    common = registry.get("common_contract", {})
    common_components = list(common.get("covered_components", []))
    for component in common_components:
        if component not in vocabulary:
            lint.fail(CONTRACT_REGISTRY, f"common_contract covers unregistered component {component}")

    profiles = {
        row.get("freshness_profile_id"): row
        for row in registry.get("freshness_profiles", [])
        if isinstance(row, dict)
    }
    if None in profiles:
        lint.fail(CONTRACT_REGISTRY, "every freshness profile needs a freshness_profile_id")
        del profiles[None]

    scenarios: dict[str, dict[str, Any]] = {}
    applicable: dict[str, set[str]] = {}
    for scenario in registry.get("scenarios", []):
        if not isinstance(scenario, dict):
            lint.fail(CONTRACT_REGISTRY, "every scenario must be an object")
            continue
        scenario_id = scenario.get("scenario_id")
        if not isinstance(scenario_id, str):
            lint.fail(CONTRACT_REGISTRY, "every scenario needs a scenario_id")
            continue
        if scenario_id in scenarios:
            lint.fail(CONTRACT_REGISTRY, f"duplicate scenario_id {scenario_id}")
        scenarios[scenario_id] = scenario

        components = set(common_components)
        for component in scenario.get("additional_covered_components", []):
            if component not in vocabulary:
                lint.fail(CONTRACT_REGISTRY, f"{scenario_id} covers unregistered component {component}")
            components.add(component)
        for row in scenario.get("conditional_covered_components", []):
            if not isinstance(row, dict) or not row.get("condition"):
                lint.fail(
                    CONTRACT_REGISTRY,
                    f"{scenario_id}: a conditional component must state the condition that makes it required",
                )
                continue
            component = row.get("component")
            if component not in vocabulary:
                lint.fail(CONTRACT_REGISTRY, f"{scenario_id} covers unregistered component {component}")
            components.add(component)
        applicable[scenario_id] = components

        profile_id = scenario.get("freshness_profile_id")
        if profile_id not in profiles:
            lint.fail(CONTRACT_REGISTRY, f"{scenario_id} names unregistered freshness profile {profile_id}")

        for key in scenario:
            if key not in _SCENARIO_KEYS:
                lint.fail(
                    CONTRACT_REGISTRY,
                    f"{scenario_id} declares unregistered key {key!r}; a new deviation mechanism "
                    "is a protocol change, not a key nobody reads",
                )

        bindings = scenario.get("prose_bindings")
        if not isinstance(bindings, list) or not bindings:
            lint.fail(CONTRACT_REGISTRY, f"{scenario_id} must declare at least one prose binding")
            continue
        for binding in bindings:
            if not isinstance(binding, str) or not binding.startswith("zh/"):
                lint.fail(CONTRACT_REGISTRY, f"{scenario_id} prose binding must be a zh/ path: {binding!r}")
            elif not (SPEC_ROOT / binding).is_file():
                lint.fail(CONTRACT_REGISTRY, f"{scenario_id} prose binding does not exist: {binding}")

    if not scenarios:
        lint.fail(CONTRACT_REGISTRY, "the registry declares no signing scenario")
        return

    named_profiles = {scenario.get("freshness_profile_id") for scenario in scenarios.values()}
    for profile_id in profiles:
        if profile_id in named_profiles or profile_id in _STANDALONE_PROFILES:
            continue
        lint.fail(
            CONTRACT_REGISTRY,
            f"freshness profile {profile_id} is named by no scenario. Report 1240 retired the two "
            "lifetime tightenings this guard replaces: a window nobody resolves is a numeral "
            "waiting to be cited from prose.",
        )

    _check_prose(lint, scenarios, applicable, profiles, registry)
    _check_machine_projections(lint, scenarios, applicable, profiles)
    _check_operations(lint, catalog, scenarios)
    _check_boundary_vectors(lint, catalog, scenarios, profiles)


def _check_prose(
    lint: Lint,
    scenarios: dict[str, dict[str, Any]],
    applicable: dict[str, set[str]],
    profiles: dict[str, dict[str, Any]],
    registry: dict[str, Any],
) -> None:
    normative_page = SPEC_ROOT / "zh" / "sync" / "service-http-binding.md"
    seen: dict[str, set[str]] = {scenario_id: set() for scenario_id in scenarios}
    freshness_seen: set[str] = set()
    vocabulary = _all_components(registry)

    for path in _prose_pages():
        text = read_text(path)
        rel = _rel(path)

        for name in _unterminated(text, COVERED_SET_BEGIN_RE, COVERED_SET_END):
            lint.fail(path, f"covered-set block for {name} is never closed")
        for name in _unterminated(text, FRESHNESS_BEGIN_RE, FRESHNESS_END):
            lint.fail(path, f"freshness block for {name} is never closed")

        covered_blocks = _blocks(text, COVERED_SET_BEGIN_RE, COVERED_SET_END)
        for scenario_id, body, line in covered_blocks:
            if scenario_id not in scenarios:
                lint.fail(path, f"line {line}: covered-set block names unregistered scenario {scenario_id}")
                continue
            seen[scenario_id].add(rel)
            declared = {
                token
                for run in BACKTICKED_RE.findall(body)
                for token in re.split(r"[、,，/]\s*", run)
                if token in vocabulary
            }
            expected = applicable[scenario_id]
            missing = sorted(expected - declared)
            extra = sorted(declared - expected)
            if missing:
                lint.fail(
                    path,
                    f"line {line}: {scenario_id} block omits {', '.join(missing)}; "
                    "the canonical contract requires it",
                )
            if extra:
                lint.fail(
                    path,
                    f"line {line}: {scenario_id} block adds {', '.join(extra)}, which the canonical "
                    "contract does not require; register it there first",
                )
            if rel not in scenarios[scenario_id].get("prose_bindings", []):
                lint.fail(
                    path,
                    f"line {line}: carries a {scenario_id} block but is not a declared prose binding",
                )

        # An enumeration outside a block is the regression this gate exists for.
        stripped = text
        for match in reversed(list(COVERED_SET_BEGIN_RE.finditer(text))):
            stop = text.find(COVERED_SET_END, match.end())
            if stop != -1:
                stripped = stripped[: match.start()] + stripped[stop + len(COVERED_SET_END):]
        for number, raw in enumerate(stripped.splitlines(), 1):
            if all(marker in raw for marker in ENUMERATION_MARKERS):
                lint.fail(
                    path,
                    "enumerates an RFC 9421 covered set outside a declared covered-set block; "
                    "cite the scenario instead of restating the list",
                )
                break

        freshness_blocks = _blocks(text, FRESHNESS_BEGIN_RE, FRESHNESS_END)
        for profile_id, body, line in freshness_blocks:
            if path != normative_page:
                lint.fail(
                    path,
                    f"line {line}: the freshness window is stated only in "
                    "zh/sync/service-http-binding.md",
                )
                continue
            profile = profiles.get(profile_id)
            if profile is None:
                lint.fail(path, f"line {line}: unregistered freshness profile {profile_id}")
                continue
            freshness_seen.add(profile_id)
            numerals = {int(value) for value in INTEGER_RE.findall(body)}
            for key, value in profile.items():
                if key.endswith("_seconds") and isinstance(value, int) and value not in numerals:
                    lint.fail(
                        path,
                        f"line {line}: {profile_id} block does not state {key}={value}",
                    )

        # Only the canonical block may define the window.
        window_body = "".join(body for _, body, _ in freshness_blocks)
        if len(WINDOW_PHRASE_RE.findall(text)) != len(WINDOW_PHRASE_RE.findall(window_body)):
            lint.fail(
                path,
                "states the signature window outside the canonical freshness block; "
                "cite zh/sync/service-http-binding.md section 8.3 instead",
            )

    for scenario_id, pages in seen.items():
        declared = set(scenarios[scenario_id].get("prose_bindings", []))
        for missing in sorted(declared - pages):
            lint.fail(
                SPEC_ROOT / missing,
                f"declared as a prose binding for {scenario_id} but carries no covered-set block",
            )

    for profile_id in sorted(set(profiles) - freshness_seen):
        lint.fail(
            SPEC_ROOT / "zh" / "sync" / "service-http-binding.md",
            f"freshness profile {profile_id} has no block in the prose",
        )


def _all_components(registry: dict[str, Any]) -> set[str]:
    return {
        row.get("component")
        for row in registry.get("component_vocabulary", [])
        if isinstance(row, dict)
    }


def _check_machine_projections(
    lint: Lint,
    scenarios: dict[str, dict[str, Any]],
    applicable: dict[str, set[str]],
    profiles: dict[str, dict[str, Any]] | None = None,
) -> None:
    cache: dict[Path, Any] = {}
    for scenario_id, scenario in scenarios.items():
        for pointer in scenario.get("machine_projections", []):
            if not isinstance(pointer, str) or "#" not in pointer:
                lint.fail(CONTRACT_REGISTRY, f"{scenario_id}: bad projection pointer {pointer!r}")
                continue
            rel, fragment = pointer.split("#", 1)
            target = ARTIFACTS / rel
            if not target.is_file():
                lint.fail(CONTRACT_REGISTRY, f"{scenario_id}: projection target missing: {rel}")
                continue
            if target not in cache:
                cache[target] = load_json(lint, target)
            value = _resolve_pointer(cache[target], fragment)
            if value is None:
                lint.fail(target, f"{scenario_id}: projection pointer does not resolve: {fragment}")
                continue
            if not isinstance(value, list):
                lint.fail(target, f"{scenario_id}: projection {fragment} must be an array")
                continue
            declared = set(value)
            expected = applicable[scenario_id]
            if declared != expected:
                missing = sorted(expected - declared)
                extra = sorted(declared - expected)
                lint.fail(
                    target,
                    f"{scenario_id}: projection {fragment} drifted from the canonical contract"
                    + (f"; missing {', '.join(missing)}" if missing else "")
                    + (f"; unexpected {', '.join(extra)}" if extra else ""),
                )

    _check_freshness_projections(lint, scenarios, profiles or {}, cache)


def _check_freshness_projections(
    lint: Lint,
    scenarios: dict[str, dict[str, Any]],
    profiles: dict[str, dict[str, Any]],
    cache: dict[Path, Any],
) -> None:
    """A machine copy of a window numeral is checked against the profile that owns it."""
    for scenario_id, scenario in scenarios.items():
        for row in scenario.get("freshness_projections", []):
            if not isinstance(row, dict) or "#" not in str(row.get("pointer", "")):
                lint.fail(CONTRACT_REGISTRY, f"{scenario_id}: bad freshness projection {row!r}")
                continue
            # A projection may name another registered profile: one fixture case
            # states both the RFC 9421 window and the separate DPoP one.
            profile_id = row.get("profile_id") or scenario.get("freshness_profile_id")
            if profile_id not in profiles:
                lint.fail(
                    CONTRACT_REGISTRY,
                    f"{scenario_id}: freshness projection names unregistered profile {profile_id}",
                )
                continue
            profile = profiles[profile_id]
            key = row.get("profile_key")
            if key not in profile:
                lint.fail(
                    CONTRACT_REGISTRY,
                    f"{scenario_id}: freshness projection names unknown profile key {key!r}",
                )
                continue
            rel, fragment = str(row["pointer"]).split("#", 1)
            target = ARTIFACTS / rel
            if not target.is_file():
                lint.fail(CONTRACT_REGISTRY, f"{scenario_id}: projection target missing: {rel}")
                continue
            if target not in cache:
                cache[target] = load_json(lint, target)
            value = _resolve_pointer(cache[target], fragment)
            if value != profile[key]:
                lint.fail(
                    target,
                    f"{scenario_id}: {fragment} is {value!r}, but {key} of "
                    f"{profile_id} is {profile[key]!r}",
                )


def _check_boundary_vectors(
    lint: Lint,
    catalog: dict[str, Any],
    scenarios: dict[str, dict[str, Any]],
    profiles: dict[str, dict[str, Any]],
) -> None:
    """Boundary evidence is bound to the operations that really resolve the profile.

    Report 1240 retired two per-operation lifetime tightenings. Testing a profile
    nobody calls would not have caught either of them, so a profile that declares a
    boundary vector also names the operations whose requests it decides, and this
    gate resolves operation -> scenario -> profile to check the claim.
    """
    resolved: dict[str, str] = {}
    for operation in catalog.get("operation_registry", {}).get("operations", []):
        if not isinstance(operation, dict):
            continue
        signature = operation.get("auth_requirements", {}).get("service_signature")
        if not isinstance(signature, dict):
            continue
        scenario = scenarios.get(signature.get("signature_scenario_id"))
        if isinstance(scenario, dict):
            resolved[operation.get("operation_id")] = scenario.get("freshness_profile_id")

    for profile_id, profile in profiles.items():
        binding = profile.get("boundary_vector")
        if binding is None:
            continue
        if not isinstance(binding, dict):
            lint.fail(CONTRACT_REGISTRY, f"{profile_id}: boundary_vector must be an object")
            continue
        pointer = str(binding.get("fixture_pointer", ""))
        if "#" not in pointer:
            lint.fail(CONTRACT_REGISTRY, f"{profile_id}: boundary_vector needs a fixture pointer")
        else:
            rel, fragment = pointer.split("#", 1)
            target = ARTIFACTS / rel
            case = _resolve_pointer(load_json(lint, target), fragment) if target.is_file() else None
            if not isinstance(case, dict):
                lint.fail(
                    CONTRACT_REGISTRY,
                    f"{profile_id}: boundary_vector pointer does not resolve: {pointer}",
                )
            else:
                if case.get("vector_id") != binding.get("vector_id"):
                    lint.fail(
                        target,
                        f"{profile_id}: {fragment} carries vector {case.get('vector_id')!r}, "
                        f"but the profile claims {binding.get('vector_id')!r}",
                    )
                if case.get("freshness_profile_id") != profile_id:
                    lint.fail(
                        target,
                        f"{profile_id}: {fragment} states profile "
                        f"{case.get('freshness_profile_id')!r}",
                    )

        operations = binding.get("resolved_by_operations")
        if not isinstance(operations, list) or not operations:
            lint.fail(
                CONTRACT_REGISTRY,
                f"{profile_id}: boundary_vector must name the operations it decides",
            )
            continue
        for operation_id in operations:
            if operation_id not in resolved:
                lint.fail(
                    CONTRACT_REGISTRY,
                    f"{profile_id}: boundary_vector names {operation_id}, which binds no "
                    "signature scenario, so it resolves no window at all",
                )
            elif resolved[operation_id] != profile_id:
                lint.fail(
                    CONTRACT_REGISTRY,
                    f"{profile_id}: boundary_vector claims {operation_id}, but that operation "
                    f"resolves {resolved[operation_id]}",
                )


def _check_operations(
    lint: Lint,
    catalog: dict[str, Any],
    scenarios: dict[str, dict[str, Any]],
) -> None:
    operations = catalog.get("operation_registry", {}).get("operations", [])
    known = {
        operation.get("operation_id")
        for operation in operations
        if isinstance(operation, dict)
    }
    bound: set[str] = set()
    for operation in operations:
        if not isinstance(operation, dict):
            continue
        signature = operation.get("auth_requirements", {}).get("service_signature")
        if not isinstance(signature, dict):
            continue
        operation_id = operation.get("operation_id")
        scenario_id = signature.get("signature_scenario_id")
        if scenario_id not in scenarios:
            lint.fail(
                CONTRACT_REGISTRY,
                f"{operation_id}: service_signature names unregistered scenario {scenario_id!r}",
            )
            continue
        bound.add(operation_id)
        for forbidden in ("covered_components", "freshness"):
            if forbidden in signature:
                lint.fail(
                    CONTRACT_REGISTRY,
                    f"{operation_id}: service_signature restates {forbidden}; the scenario owns it",
                )
        if operation_id not in scenarios[scenario_id].get("operations", []):
            lint.fail(
                CONTRACT_REGISTRY,
                f"{scenario_id} does not list {operation_id}, but that operation binds it",
            )

    for scenario_id, scenario in scenarios.items():
        for operation_id in scenario.get("operations", []):
            if operation_id not in known:
                lint.fail(CONTRACT_REGISTRY, f"{scenario_id} names unknown operation {operation_id}")
            elif operation_id not in bound:
                lint.fail(
                    CONTRACT_REGISTRY,
                    f"{scenario_id} names {operation_id}, but that operation does not bind the scenario",
                )
