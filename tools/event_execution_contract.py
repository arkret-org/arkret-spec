"""Derive the closed Event kind set accepted by the producer envelope."""

from __future__ import annotations

import json


def field_guard(path: str, constraint: dict) -> dict:
    parts = path.split(".")
    if not constraint:
        constraint = {"required": [parts.pop()]}
    for part in reversed(parts):
        constraint = {"properties": {part: constraint}, "required": [part]}
    return constraint


def condition_guard(condition: dict | None) -> dict:
    if condition is None:
        return {}
    kind = condition["kind"]
    if kind == "field_present":
        return field_guard(condition["field"], {})
    if kind == "field_absent":
        return {"not": field_guard(condition["field"], {})}
    if kind == "any_field_present":
        return {"anyOf": [field_guard(field, {}) for field in condition["fields"]]}
    if kind == "critical_ref_role_exact_count":
        count = condition["count"]
        match = {"properties": {"role": {"const": condition["role"]}, "critical": {"const": True}}, "required": ["role", "critical"]}
        if count == 0:
            return {"properties": {"semantic_refs": {"not": {"contains": match}}}}
        return {"required": ["semantic_refs"], "properties": {"semantic_refs": {"contains": match, "minContains": count, "maxContains": count}}}
    if kind == "field_equals":
        return field_guard(condition["field"], {"const": condition["const"]})
    raise ValueError(f"unregistered execution condition: {condition}")


def schema_definition(registry: dict) -> dict:
    kinds = sorted(
        row["event_kind"]
        for row in registry["event_kinds"]
        if row.get("status") == "active"
    )
    return {
        "$comment": (
            "Generated from the canonical event-kind registry. Shared durable "
            "Events run typed reducers at the current governance Station before "
            "RealmCommit issuance; actor-private Events remain valid producer "
            "envelopes but are not inserted into a shared stream."
        ),
        "properties": {"kind": {"enum": kinds}},
        "required": ["kind"],
    }
