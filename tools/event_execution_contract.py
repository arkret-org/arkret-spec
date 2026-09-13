"""Derive Event execution requirements from registered effective cell writes."""

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
            return {"properties": {"refs": {"not": {"contains": match}}}}
        return {"required": ["refs"], "properties": {"refs": {"contains": match, "minContains": count, "maxContains": count}}}
    if kind == "field_equals":
        return field_guard(condition["field"], {"const": condition["const"]})
    raise ValueError(f"unregistered execution condition: {condition}")


def schema_definition(registry: dict) -> dict:
    clauses = []
    contracts = registry["cell_contracts"]
    bootstrap_ref = {
        "required": ["refs"],
        "properties": {"refs": {"contains": {
            "required": ["role", "critical"],
            "properties": {"role": {"const": "bootstrap_genesis"},
                           "critical": {"const": True}},
        }, "minContains": 1, "maxContains": 1}},
    }
    grouped = {}
    for row in registry["event_kinds"]:
        if row.get("status") != "active":
            continue
        kind = row["event_kind"]
        contract = contracts.get(kind)
        if not contract:
            continue
        kind_guard = field_guard("kind", {"const": kind})
        writes = contract.get("cell_writes", [])
        security = [condition_guard(w.get("condition")) for w in writes
                    if w.get("execution") == "security"]
        effective = [condition_guard(w.get("condition")) for w in writes]
        if {} not in effective:
            clauses.append({"if": kind_guard, "then": {"anyOf": effective}})
        data_requirements = {"not": {"required": ["seal_basis"]}}
        if kind in registry["bootstrap_event_kinds"]:
            data_requirements["anyOf"] = [
                {"required": ["auth_context", "data_basis"]},
                bootstrap_ref,
            ]
        else:
            data_requirements["required"] = ["auth_context", "data_basis"]
        data_requirements["allOf"] = [{"if": field_guard("payload.patch", {}), "then": {"required": ["causal_refs"]}}]
        security_requirements = {
            "allOf": [
                {"not": {"required": ["auth_context"]}},
                {"not": {"required": ["data_basis"]}},
            ]
        }
        if kind != "ak.realm.create":
            if kind in registry["bootstrap_event_kinds"]:
                security_requirements["anyOf"] = [{"required": ["seal_basis"]}, bootstrap_ref]
            else:
                security_requirements["required"] = ["seal_basis"]
        if {} in security:
            rule = security_requirements
        elif security:
            clauses.append({"if": kind_guard, "then": {"if": {"anyOf": security},
                            "then": security_requirements, "else": data_requirements}})
            continue
        else:
            rule = data_requirements
        key = json.dumps(rule, sort_keys=True)
        grouped.setdefault(key, {"rule": rule, "kinds": []})["kinds"].append(kind)
    for group in grouped.values():
        clauses.append({"if": field_guard("kind", {"enum": sorted(group["kinds"])}), "then": group["rule"]})
    return {
        "$comment": "Generated from effective cell write execution. The bootstrap reference requires the registered atomic-genesis verifier; presence alone never bypasses security finality.",
        "allOf": clauses,
    }
