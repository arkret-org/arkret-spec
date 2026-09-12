"""Project canonical admission selectors into Event syntax and history guards.

These guards prove branch selection and field presence only. Native authority,
signatures and accepted-Seal closure remain the named semantic verifiers' work.
"""

from __future__ import annotations

import json
from pathlib import Path

try:
    from .event_execution_contract import schema_definition as execution_schema
except ImportError:
    from event_execution_contract import schema_definition as execution_schema


def nested(path: str, value: dict) -> dict:
    for part in reversed(path.split(".")):
        value = {"properties": {part: value}, "required": [part]}
    return value


def predicate_schema(when: dict) -> dict:
    supported = {"payload_path", "const", "not_const", "ref_role", "ref_critical", "ref_exact_count", "top_level_fields_present"}
    if not when or set(when) - supported:
        raise ValueError(f"unknown admission selector: {when}")
    clauses = []
    if "payload_path" in when:
        if ("const" in when) == ("not_const" in when):
            raise ValueError("payload selector requires exactly one comparator")
        key = "const" if "const" in when else "not_const"
        value = nested("payload." + when["payload_path"], {"const": when[key]})
        clauses.append(value if key == "const" else {"not": value})
    elif "const" in when or "not_const" in when:
        raise ValueError("comparison without payload_path")
    if "ref_role" in when:
        properties = {"role": {"const": when["ref_role"]}}
        if "ref_critical" in when:
            properties["critical"] = {"const": when["ref_critical"]}
        match = {"properties": properties, "required": list(properties)}
        count = when.get("ref_exact_count", 1)
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ValueError("invalid reference count")
        if count == 0:
            clauses.append({"properties": {"refs": {"not": {"contains": match}}}})
        else:
            constraint = {"contains": match, "minContains": count}
            if "ref_exact_count" in when:
                constraint["maxContains"] = count
            clauses.append({"properties": {"refs": constraint}, "required": ["refs"]})
    elif "ref_critical" in when or "ref_exact_count" in when:
        raise ValueError("reference selector without role")
    if "top_level_fields_present" in when:
        fields = when["top_level_fields_present"]
        if not fields or not isinstance(fields, list):
            raise ValueError("empty top-level field selector")
        clauses.append({"required": fields})
    return {"allOf": clauses}


def selected_branches(row: dict) -> list[tuple[str, dict]]:
    if row.get("admission") != "conditional":
        return [(row.get("admission", "capability_gated"), {})]
    variants = row["admission_variants"]
    if variants[-1]["when"] != {"otherwise": True}:
        raise ValueError("conditional admission requires a final otherwise")
    predicates = [predicate_schema(v["when"]) for v in variants[:-1]]
    result = []
    for index, variant in enumerate(variants[:-1]):
        others = predicates[:index] + predicates[index + 1:]
        guard = {"allOf": [predicates[index], {"not": {"anyOf": others}}]} if others else predicates[index]
        result.append((variant["admission"], guard))
    result.append((variants[-1]["admission"], {"not": {"anyOf": predicates}}))
    return result


def schema_definitions(registry: dict) -> dict:
    guards, durable = [], []
    contract = registry["history_admission_contract"]
    native_classes = set(contract["native_admission_classes"])
    known_classes = set(registry["admission_class_definitions"])
    if not native_classes <= known_classes or native_classes & {"capability_gated", "conditional", "deny"}:
        raise ValueError("history native exceptions must name explicit non-capability admission classes")
    for row in registry["event_kinds"]:
        if row.get("status") != "active" or row.get("wire_scope") != "durable_event":
            continue
        kind = row["event_kind"]
        durable.append(kind)
        kind_guard = {"properties": {"kind": {"const": kind}}, "required": ["kind"]}
        branches = selected_branches(row)
        if kind not in registry["cell_contracts"]:
            guards.append({"if": kind_guard, "then": {"not": {"anyOf": [
                {"required": [field]} for field in ("auth_context", "seal_basis", "preconditions")
            ]}}})
        if row.get("admission") == "conditional":
            guards.append({"if": kind_guard, "then": {"anyOf": [g for a, g in branches if a != "deny"]}})
    return {
        "ordinary_publication_event": {
            "$comment": "Body-proof publication is limited to complete ordinary shared Events; it grants no account session or private account access.",
            "allOf": [
                {"$ref": "#/$defs/shared_history_event"},
                {"required": ["auth_context"], "not": {"required": ["seal_basis"]}},
                {"properties": {"kind": {"enum": sorted(registry["cell_contracts"])}}},
                {"properties": {"refs": {"not": {"contains": {"required": ["role"], "properties": {"role": {"const": "bootstrap_genesis"}}}}}}},
            ],
        },
        "registered_execution_shape": execution_schema(registry),
        "registered_admission_shape": {
            "$comment": "Generated from canonical event_kind_registry.admission_variants; do not hand-edit. Semantic authority verification is additional.",
            "allOf": guards,
        },
        "shared_history_event": {
            "$comment": "Generated from canonical history_admission_contract. Every receiving Station verifies the portable producer, authority and causal evidence. Security commands require their scoped final decision; ordinary history uses deterministic eligibility. Syntax alone never grants authority.",
            "allOf": [
                {"$ref": "#"},
                {"properties": {"kind": {"enum": sorted(durable)}}, "required": ["kind"]},
                {"properties": {"proofs": {"items": {"required": ["signer_resolution_evidence_ref"]}}}},
            ],
        },
    }


def synchronize(root: Path, *, check: bool) -> None:
    artifacts = root / "spec/v1/artifacts"
    registry = json.loads((artifacts / "registry/contract-registry.json").read_text(encoding="utf-8"))["event_kind_registry"]
    path = artifacts / "schemas/event-envelope.schema.json"
    schema = json.loads(path.read_text(encoding="utf-8"))
    definitions = schema_definitions(registry)
    references = [{"$ref": "#/$defs/registered_admission_shape"},
                  {"$ref": "#/$defs/registered_execution_shape"}]
    if check:
        if any(schema["allOf"].count(ref) != 1 for ref in references) or any(schema["$defs"].get(k) != v for k, v in definitions.items()):
            raise ValueError("Event admission schema projection drift; run artifact_pipeline.py generate")
    else:
        schema["$defs"].update(definitions)
        for reference in references:
            if reference not in schema["allOf"]:
                schema["allOf"].append(reference)
        path.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    for binding in registry["history_admission_contract"]["consumer_schema_bindings"]:
        target_path = artifacts / binding["schema"]
        document = json.loads(target_path.read_text(encoding="utf-8"))
        tokens = [token.replace("~1", "/").replace("~0", "~") for token in binding["pointer"].strip("/").split("/")]
        target = document
        for token in tokens[:-1]:
            target = target[int(token)] if isinstance(target, list) else target[token]
        shared_ref = "./event-envelope.schema.json#/$defs/shared_history_event"
        if check:
            if target[tokens[-1]] != shared_ref:
                raise ValueError(f"shared-history consumer drift: {binding}")
        elif target[tokens[-1]] != shared_ref:
            target[tokens[-1]] = shared_ref
            target_path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
