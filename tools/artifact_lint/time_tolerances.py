"""Close protocol clock-tolerance scenarios over prose, schemas and boundary KATs."""

from __future__ import annotations

from typing import Any

from .core import ARTIFACTS, SPEC_ROOT, Lint, load_json, read_text, resolve_json_pointer

CONTRACT = ARTIFACTS / "registry" / "contract-registry.json"
REGISTRY_KEY = "protocol_time_tolerance_registry"
ALLOWED_DIRECTIONS = {"future_only", "symmetric_not_before_and_expiry"}
ALLOWED_BOUNDARIES = {"future", "future_not_before", "past_expiry"}
EXPECTED_TOLERANCE_NAMES = {
    "ak.time_tolerance.hard_future_skew.v1": "hard_future_skew_ms",
    "ak.time_tolerance.expected_future_skew.v1": "expected_future_skew_ms",
}
EXPECTED_SCENARIOS = {
    "ak.time_tolerance.approval_approved_at.v1": (
        "ak.time_tolerance.hard_future_skew.v1",
        "future_only",
        {("future", 0, True), ("future", 1, False)},
    ),
    "ak.time_tolerance.temporal_constraint.v1": (
        "ak.time_tolerance.hard_future_skew.v1",
        "symmetric_not_before_and_expiry",
        {
            ("future_not_before", 0, True),
            ("future_not_before", 1, False),
            ("past_expiry", 0, True),
            ("past_expiry", 1, False),
        },
    ),
    "ak.time_tolerance.blob_presign_ttl.v1": (
        "ak.time_tolerance.expected_future_skew.v1",
        "symmetric_not_before_and_expiry",
        {
            ("future_not_before", 0, True),
            ("future_not_before", 1, False),
            ("past_expiry", 0, True),
            ("past_expiry", 1, False),
        },
    ),
}


def _non_empty_strings(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(
        isinstance(item, str) and item.strip() for item in value
    )


def check_protocol_time_tolerance_closure(lint: Lint) -> None:
    document = load_json(lint, CONTRACT)
    if not isinstance(document, dict):
        return
    registry = document.get(REGISTRY_KEY)
    if not isinstance(registry, dict):
        lint.fail(CONTRACT, f"missing {REGISTRY_KEY}")
        return
    if registry.get("source_of_truth") is not True:
        lint.fail(CONTRACT, f"{REGISTRY_KEY}.source_of_truth must be true")

    tolerance_rows = registry.get("tolerances")
    if not isinstance(tolerance_rows, list) or not tolerance_rows:
        lint.fail(CONTRACT, f"{REGISTRY_KEY}.tolerances must be a non-empty list")
        return
    tolerances: dict[str, dict[str, Any]] = {}
    names: set[str] = set()
    for index, row in enumerate(tolerance_rows):
        label = f"{REGISTRY_KEY}.tolerances[{index}]"
        if not isinstance(row, dict) or set(row) != {
            "tolerance_id", "name", "value", "unit"
        }:
            lint.fail(CONTRACT, f"{label} must have exactly tolerance_id/name/value/unit")
            continue
        tolerance_id = row.get("tolerance_id")
        name = row.get("name")
        value = row.get("value")
        if not isinstance(tolerance_id, str) or not tolerance_id.startswith("ak.time_tolerance."):
            lint.fail(CONTRACT, f"{label}.tolerance_id is invalid")
            continue
        if tolerance_id in tolerances:
            lint.fail(CONTRACT, f"duplicate tolerance_id {tolerance_id}")
        if not isinstance(name, str) or not name.endswith("_ms") or name in names:
            lint.fail(CONTRACT, f"{label}.name must be a unique *_ms name")
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            lint.fail(CONTRACT, f"{label}.value must be a positive integer")
        if row.get("unit") != "milliseconds":
            lint.fail(CONTRACT, f"{label}.unit must be milliseconds")
        tolerances[tolerance_id] = row
        if isinstance(name, str):
            names.add(name)
    if set(tolerances) != set(EXPECTED_TOLERANCE_NAMES):
        lint.fail(CONTRACT, f"{REGISTRY_KEY}.tolerances must be the closed protocol set")
    for tolerance_id, expected_name in EXPECTED_TOLERANCE_NAMES.items():
        row = tolerances.get(tolerance_id)
        if isinstance(row, dict) and row.get("name") != expected_name:
            lint.fail(CONTRACT, f"{tolerance_id}.name must be {expected_name}")

    scenario_rows = registry.get("scenarios")
    if not isinstance(scenario_rows, list) or not scenario_rows:
        lint.fail(CONTRACT, f"{REGISTRY_KEY}.scenarios must be a non-empty list")
        return
    scenarios: dict[str, dict[str, Any]] = {}
    declared_cases: dict[str, tuple[str, str, int, bool]] = {}
    for index, row in enumerate(scenario_rows):
        label = f"{REGISTRY_KEY}.scenarios[{index}]"
        if not isinstance(row, dict):
            lint.fail(CONTRACT, f"{label} must be an object")
            continue
        scenario_id = row.get("scenario_id")
        if not isinstance(scenario_id, str) or not scenario_id.startswith("ak.time_tolerance."):
            lint.fail(CONTRACT, f"{label}.scenario_id is invalid")
            continue
        if scenario_id in scenarios:
            lint.fail(CONTRACT, f"duplicate scenario_id {scenario_id}")
        scenarios[scenario_id] = row
        tolerance_id = row.get("tolerance_id")
        tolerance = tolerances.get(tolerance_id) if isinstance(tolerance_id, str) else None
        if tolerance is None:
            lint.fail(CONTRACT, f"{label}.tolerance_id does not resolve")
            continue
        direction = row.get("direction")
        if direction not in ALLOWED_DIRECTIONS:
            lint.fail(CONTRACT, f"{label}.direction is not a closed value")
        if not isinstance(row.get("comparison"), str) or not row["comparison"].strip():
            lint.fail(CONTRACT, f"{label}.comparison must be non-empty")
        prose_bindings = row.get("prose_bindings")
        if not _non_empty_strings(prose_bindings):
            lint.fail(CONTRACT, f"{label}.prose_bindings must be non-empty")
        else:
            for binding in prose_bindings:
                page = SPEC_ROOT / binding.split("#", 1)[0]
                if not page.is_file() or scenario_id not in read_text(page):
                    lint.fail(CONTRACT, f"{label} prose binding does not cite {scenario_id}: {binding}")
        machine_bindings = row.get("machine_bindings")
        if not isinstance(machine_bindings, list):
            lint.fail(CONTRACT, f"{label}.machine_bindings must be a list")
        else:
            for binding in machine_bindings:
                if not isinstance(binding, str) or "#" not in binding:
                    lint.fail(CONTRACT, f"{label}.machine_bindings contains an invalid reference")
                    continue
                relative, fragment = binding.split("#", 1)
                target_path = ARTIFACTS / relative
                target_document = load_json(lint, target_path)
                try:
                    target = (
                        resolve_json_pointer(target_document, f"#{fragment}")
                        if target_document is not None
                        else None
                    )
                except (KeyError, IndexError, TypeError, ValueError):
                    target = None
                if not isinstance(target, dict) or scenario_id not in str(target.get("description", "")):
                    lint.fail(CONTRACT, f"{label} machine binding does not cite {scenario_id}: {binding}")

        boundary_rows = row.get("boundary_cases")
        if not isinstance(boundary_rows, list) or not boundary_rows:
            lint.fail(CONTRACT, f"{label}.boundary_cases must be non-empty")
            continue
        for case_index, case in enumerate(boundary_rows):
            case_label = f"{label}.boundary_cases[{case_index}]"
            if not isinstance(case, dict) or set(case) != {
                "case_id", "boundary", "beyond_limit_ms", "accepted"
            }:
                lint.fail(CONTRACT, f"{case_label} has the wrong closed shape")
                continue
            case_id = case.get("case_id")
            boundary = case.get("boundary")
            beyond = case.get("beyond_limit_ms")
            accepted = case.get("accepted")
            if not isinstance(case_id, str) or not case_id:
                lint.fail(CONTRACT, f"{case_label}.case_id must be non-empty")
                continue
            if case_id in declared_cases:
                lint.fail(CONTRACT, f"duplicate boundary case {case_id}")
            if boundary not in ALLOWED_BOUNDARIES:
                lint.fail(CONTRACT, f"{case_label}.boundary is not closed")
            if not isinstance(beyond, int) or isinstance(beyond, bool) or beyond not in {0, 1}:
                lint.fail(CONTRACT, f"{case_label}.beyond_limit_ms must be 0 or 1")
            if not isinstance(accepted, bool) or accepted is not (beyond == 0):
                lint.fail(CONTRACT, f"{case_label}.accepted must be true at the limit and false beyond it")
            if direction == "future_only" and boundary != "future":
                lint.fail(CONTRACT, f"{case_label}: future_only admits only the future boundary")
            if direction == "symmetric_not_before_and_expiry" and boundary not in {
                "future_not_before", "past_expiry"
            }:
                lint.fail(CONTRACT, f"{case_label}: symmetric scenario has the wrong boundary")
            declared_cases[case_id] = (scenario_id, str(boundary), int(tolerance["value"]), bool(accepted))

        expected_scenario = EXPECTED_SCENARIOS.get(scenario_id)
        if expected_scenario is not None:
            expected_tolerance, expected_direction, expected_boundaries = expected_scenario
            if tolerance_id != expected_tolerance or direction != expected_direction:
                lint.fail(CONTRACT, f"{label} changes the canonical tolerance or direction")
            actual_boundaries = {
                (case.get("boundary"), case.get("beyond_limit_ms"), case.get("accepted"))
                for case in boundary_rows
                if isinstance(case, dict)
            }
            if actual_boundaries != expected_boundaries:
                lint.fail(CONTRACT, f"{label}.boundary_cases do not close the canonical edges")

    if set(scenarios) != set(EXPECTED_SCENARIOS):
        lint.fail(CONTRACT, f"{REGISTRY_KEY}.scenarios must be the closed protocol set")

    fixture_ref = registry.get("fixture")
    if not isinstance(fixture_ref, str):
        lint.fail(CONTRACT, f"{REGISTRY_KEY}.fixture must be a path")
        return
    fixture_path = ARTIFACTS / fixture_ref
    fixture = load_json(lint, fixture_path)
    if not isinstance(fixture, dict):
        return
    if fixture.get("source_registry") != f"registry/contract-registry.json#{REGISTRY_KEY}":
        lint.fail(fixture_path, "source_registry does not name the canonical time-tolerance block")
    runner = fixture.get("runner")
    if not isinstance(runner, dict) or runner.get("entrypoint") != "ak.suite.protocol.time_tolerance.v1":
        lint.fail(fixture_path, "time-tolerance boundary cases have no registered runner")
    cases = fixture.get("cases")
    if not isinstance(cases, list):
        lint.fail(fixture_path, "cases must be a list")
        return
    seen_cases: set[str] = set()
    for index, case in enumerate(cases):
        label = f"cases[{index}]"
        if not isinstance(case, dict):
            lint.fail(fixture_path, f"{label} must be an object")
            continue
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or case_id not in declared_cases:
            lint.fail(fixture_path, f"{label}.case_id is not declared by the registry")
            continue
        if case_id in seen_cases:
            lint.fail(fixture_path, f"duplicate case_id {case_id}")
        seen_cases.add(case_id)
        scenario_id, boundary, limit, accepted = declared_cases[case_id]
        expected_offset = limit if accepted else limit + 1
        if boundary == "past_expiry":
            expected_offset = -expected_offset
        if case.get("scenario_id") != scenario_id or case.get("boundary") != boundary:
            lint.fail(fixture_path, f"{label} does not project its declared scenario/boundary")
        if case.get("offset_ms") != expected_offset:
            lint.fail(fixture_path, f"{label}.offset_ms does not project the registered limit")
        expected = case.get("expected")
        if expected != {"accepted": accepted}:
            lint.fail(fixture_path, f"{label}.expected does not project the boundary verdict")
    missing = set(declared_cases) - seen_cases
    if missing:
        lint.fail(fixture_path, f"missing conjunctive boundary cases: {sorted(missing)}")


__all__ = ["check_protocol_time_tolerance_closure"]
