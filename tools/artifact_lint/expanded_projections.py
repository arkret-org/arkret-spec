"""Every proof binding field is either on the wire or explicitly injected.

A proof-context row (or an `x-arkret-signature-transcript` annotation) names the
members its transcript covers. When a member is not a property of the wire leaf
the row anchors on, the verifier has to obtain it from somewhere else: an outer
carrier, a constant of the domain, or a pure function of wire members. That
somewhere else must be written down, otherwise the fixture generator invents a
value and every implementation invents its own. This gate computes the exact
difference between the binding set and the explicit wire property set and
demands that the owning row or annotation declare precisely that difference in
`injected_fields` / `x-arkret-injected-fields` as `{field, source}` entries.
A declaration for a member that is on the wire is stale and fails too.
"""

from __future__ import annotations

from .core import ARTIFACTS, Any, Lint, load_json, walk_json
from .schema_members import (
    explicit_properties,
    load_schema_documents,
    locate,
    resolve_ref,
    walk_pointer,
)

REGISTRY_PATH = ARTIFACTS / "registry" / "proof-context-registry.json"

INJECTED_FIELDS_KEY = "injected_fields"

SCHEMA_INJECTED_FIELDS_KEY = "x-arkret-injected-fields"

SIGNATURE_TRANSCRIPT_KEY = "x-arkret-signature-transcript"

# Property names under which a carrier holds its detached proof or signature leaf.
PROOF_CARRIER_NAMES = ("proof", "proofs", "status_proof", "signature", "signatures", "governance_proof")

PROOF_CARRIER_SUFFIXES = ("_proof", "_proofs", "_signature", "_signatures")

REGISTRY_RULE_MARKER = "injected_fields"


def _leaf_properties(docs: dict[str, Any], file_name: str, subschema: Any, depth: int = 0) -> set[str]:
    """Explicit properties of a proof leaf, unwrapping arrays and tuple items."""
    if depth > 8:
        return set()
    leaf_file, _, leaf = resolve_ref(docs, file_name, subschema)
    if not isinstance(leaf, dict):
        return set()
    names: set[str] = set()
    items = leaf.get("items")
    prefix_items = leaf.get("prefixItems")
    if isinstance(items, dict) or isinstance(prefix_items, list):
        if isinstance(items, dict):
            names |= _leaf_properties(docs, leaf_file, items, depth + 1)
        for item in prefix_items or []:
            names |= _leaf_properties(docs, leaf_file, item, depth + 1)
        return names
    properties = explicit_properties(docs, leaf_file, leaf)
    names |= set(properties)
    for name, (property_file, property_schema) in properties.items():
        if (
            name in PROOF_CARRIER_NAMES
            or name.endswith(PROOF_CARRIER_SUFFIXES)
        ):
            names |= _leaf_properties(docs, property_file, property_schema, depth + 1)
    return names


def wire_property_set(docs: dict[str, Any], file_name: str, pointer: str, node: Any) -> set[str]:
    """Names a verifier can read off the anchored wire object without any injection.

    The set is the anchored object's explicit properties, the properties of the
    core member when the object is a `{core, carrier}` wrapper, the properties of
    every proof carrier leaf it holds, and, when the anchor is itself a property
    (`.../properties/<name>`), the properties of the object that carries it.
    """
    names: set[str] = set()
    properties = explicit_properties(docs, file_name, node)
    names |= set(properties)
    carriers = [
        name
        for name in properties
        if name in PROOF_CARRIER_NAMES
        or name.endswith(PROOF_CARRIER_SUFFIXES)
    ]
    if len(properties) == 2 and len(carriers) == 1:
        core = next(name for name in properties if name != carriers[0])
        core_file, core_schema = properties[core]
        names |= set(explicit_properties(docs, core_file, core_schema))
    for property_name, (property_file, property_schema) in properties.items():
        leaf_names = _leaf_properties(docs, property_file, property_schema)
        is_named_carrier = property_name in carriers
        is_structural_carrier = bool(
            {"jws", "signature"} & leaf_names
            and {"verification_method", "payload_digest", "created_at"} & leaf_names
        )
        if is_named_carrier or is_structural_carrier:
            names |= leaf_names
    segments = [segment for segment in pointer.split("/") if segment]
    if len(segments) >= 2 and segments[-2] == "properties":
        parent_pointer = "/" + "/".join(segments[:-2]) if len(segments) > 2 else ""
        parent = walk_pointer(docs.get(file_name), parent_pointer)
        if isinstance(parent, dict):
            names |= set(explicit_properties(docs, file_name, parent))
    return names


def _declared_injections(lint: Lint, path, label: str, value: Any, key: str) -> dict[str, str] | None:
    if value is None:
        return {}
    if not isinstance(value, list):
        lint.fail(path, f"{label}.{key} must be an array of {{field, source}} objects")
        return None
    declared: dict[str, str] = {}
    for index, entry in enumerate(value):
        if (
            not isinstance(entry, dict)
            or set(entry) != {"field", "source"}
            or not isinstance(entry.get("field"), str)
            or not entry["field"]
            or not isinstance(entry.get("source"), str)
            or len(entry["source"].strip()) < 4
        ):
            lint.fail(
                path,
                f"{label}.{key}[{index}] must be {{field, source}} with a non-empty source path or pure-function expansion",
            )
            return None
        if entry["field"] in declared:
            lint.fail(path, f"{label}.{key} declares {entry['field']} twice")
            return None
        declared[entry["field"]] = entry["source"]
    return declared


def _compare(
    lint: Lint,
    path,
    label: str,
    key: str,
    binding: set[str],
    wire: set[str],
    declared: dict[str, str],
) -> None:
    missing = binding - wire
    undeclared = sorted(missing - set(declared))
    stale = sorted(set(declared) - missing)
    if undeclared:
        lint.fail(
            path,
            f"{label} binds {undeclared} which the anchored wire schema never declares; "
            f"declare each in {key} with its source path or pure-function expansion",
        )
    if stale:
        on_wire = [name for name in stale if name in wire]
        foreign = [name for name in stale if name not in binding]
        if on_wire:
            lint.fail(path, f"{label}.{key} declares {on_wire}, which the wire schema already carries; the entry is stale")
        if foreign:
            lint.fail(path, f"{label}.{key} declares {foreign}, which are not binding fields of this transcript")


def check_expanded_projection_registry(lint: Lint) -> None:
    docs = load_schema_documents(lint)
    registry = load_json(lint, REGISTRY_PATH)
    if not isinstance(registry, dict):
        return
    rules = registry.get("registry_rules")
    if not isinstance(rules, list) or not any(REGISTRY_RULE_MARKER in str(rule) for rule in rules):
        lint.fail(REGISTRY_PATH, f"registry_rules must state the {INJECTED_FIELDS_KEY} declaration rule")

    for array, id_key in (("contexts", "context"), ("domain_separations", "domain")):
        for index, row in enumerate(registry.get(array) or []):
            if not isinstance(row, dict):
                continue
            label = f"{array}[{index}] {row.get(id_key, '?')}"
            if array == "domain_separations" and row.get("primitive") != "detached_signature":
                if INJECTED_FIELDS_KEY in row:
                    lint.fail(REGISTRY_PATH, f"{label}.{INJECTED_FIELDS_KEY} is only meaningful for a detached_signature transcript")
                continue
            refs: list[str] = []
            if isinstance(row.get("schema_ref"), str):
                refs.append(row["schema_ref"])
            for ref in row.get("transcript_schema_refs") or []:
                if isinstance(ref, str):
                    refs.append(ref)
            if not refs:
                if INJECTED_FIELDS_KEY in row:
                    lint.fail(REGISTRY_PATH, f"{label}.{INJECTED_FIELDS_KEY} needs a schema_ref or transcript_schema_refs to compare against")
                continue
            fields = row.get("binding_fields")
            if not isinstance(fields, list) or not all(isinstance(item, str) for item in fields):
                continue
            binding = {item.rstrip("?") for item in fields}
            wire: set[str] = set()
            unresolved = False
            for ref in refs:
                file_name, pointer, node = locate(docs, ref)
                if not isinstance(node, dict):
                    unresolved = True
                    break
                wire |= wire_property_set(docs, file_name, pointer, node)
            if unresolved:
                continue
            declared = _declared_injections(lint, REGISTRY_PATH, label, row.get(INJECTED_FIELDS_KEY), INJECTED_FIELDS_KEY)
            if declared is None:
                continue
            _compare(lint, REGISTRY_PATH, label, INJECTED_FIELDS_KEY, binding, wire, declared)

    for file_name in sorted(docs):
        document = docs[file_name]
        if not isinstance(document, dict):
            continue
        path = ARTIFACTS / "schemas" / file_name
        for json_path, node, _key in walk_json(document):
            if not isinstance(node, dict) or SIGNATURE_TRANSCRIPT_KEY not in node:
                continue
            transcript = node[SIGNATURE_TRANSCRIPT_KEY]
            if not isinstance(transcript, list) or not all(isinstance(item, str) for item in transcript):
                lint.fail(path, f"{json_path}.{SIGNATURE_TRANSCRIPT_KEY} must be a string array")
                continue
            wire = set(explicit_properties(docs, file_name, node))
            for carrier in PROOF_CARRIER_NAMES:
                located = explicit_properties(docs, file_name, node).get(carrier)
                if located is not None:
                    wire |= _leaf_properties(docs, located[0], located[1])
            declared = _declared_injections(lint, path, json_path, node.get(SCHEMA_INJECTED_FIELDS_KEY), SCHEMA_INJECTED_FIELDS_KEY)
            if declared is None:
                continue
            _compare(lint, path, json_path, SCHEMA_INJECTED_FIELDS_KEY, {item.rstrip("?") for item in transcript}, wire, declared)
