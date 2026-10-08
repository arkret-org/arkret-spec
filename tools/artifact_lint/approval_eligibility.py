"""Closure checks for approval-requirement eligibility and evidence carriers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .core import ARTIFACTS, Lint, load_json, resolve_json_pointer


ACTION_REGISTRY = ARTIFACTS / "registry" / "capability-action-registry.json"
OPERATION_REGISTRY = ARTIFACTS / "registry" / "operation-registry.json"
APPROVAL_SCHEMA = ARTIFACTS / "schemas" / "approval-signature.schema.json"

ELIGIBILITY_KINDS = {
    "event_submission_carrier",
    "registered_operation_carrier",
    "ineligible_no_registered_carrier",
}
TARGET_KINDS = {"event", "operation"}
CARRIER_CLASSES = {"event_submission", "non_event_operation"}


def _normalize_ref(base_file: Path, ref: str) -> tuple[Path, str]:
    path_text, separator, fragment_text = ref.partition("#")
    if path_text.startswith("schemas/"):
        path = (ARTIFACTS / path_text).resolve()
    elif path_text:
        path = (base_file.parent / path_text).resolve()
    else:
        path = base_file.resolve()
    fragment = "#" + fragment_text if separator else "#"
    return path, fragment


def _pointer_child(fragment: str, key: str) -> str:
    escaped = key.replace("~", "~0").replace("/", "~1")
    return f"#/{escaped}" if fragment == "#" else f"{fragment}/{escaped}"


def _schema_location_reachable(
    lint: Lint,
    start_ref: str,
    target_ref: str,
) -> bool:
    """Return whether a request schema can reach the exact carrier location."""

    start = _normalize_ref(ACTION_REGISTRY, start_ref)
    target = _normalize_ref(ACTION_REGISTRY, target_ref)
    queue = [start]
    visited: set[tuple[Path, str]] = set()
    documents: dict[Path, Any] = {}
    while queue:
        location = queue.pop()
        if location in visited:
            continue
        visited.add(location)
        if location == target:
            return True
        path, fragment = location
        if path not in documents:
            document = load_json(lint, path)
            if document is None:
                continue
            documents[path] = document
        try:
            node = resolve_json_pointer(documents[path], fragment)
        except (KeyError, IndexError, TypeError, ValueError):
            continue
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str):
                queue.append(_normalize_ref(path, ref))
            for key in node:
                queue.append((path, _pointer_child(fragment, key)))
        elif isinstance(node, list):
            for index in range(len(node)):
                queue.append((path, _pointer_child(fragment, str(index))))
    return False


def _resolve_schema_node(lint: Lint, ref: str) -> tuple[Path, Any] | None:
    path, fragment = _normalize_ref(ACTION_REGISTRY, ref)
    document = load_json(lint, path)
    if document is None:
        return None
    try:
        return path, resolve_json_pointer(document, fragment)
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        lint.fail(ACTION_REGISTRY, f"approval carrier schema ref cannot resolve: {ref}: {exc}")
        return None


def check_approval_requirement_eligibility(lint: Lint) -> None:
    """Close every capability action over an actual approval evidence carrier."""

    registry = load_json(lint, ACTION_REGISTRY)
    operations = load_json(lint, OPERATION_REGISTRY)
    schema = load_json(lint, APPROVAL_SCHEMA)
    if not all(isinstance(value, dict) for value in (registry, operations, schema)):
        return

    block = registry.get("approval_requirement_eligibility")
    if not isinstance(block, dict):
        lint.fail(ACTION_REGISTRY, "missing approval_requirement_eligibility registry")
        return
    expected_block_keys = {
        "eligibility_kind_definitions",
        "event_mapping_defaults",
        "carriers",
        "default_carrier_by_eligibility_kind",
        "action_overrides",
    }
    if set(block) != expected_block_keys:
        lint.fail(
            ACTION_REGISTRY,
            "approval_requirement_eligibility must be closed over "
            f"{sorted(expected_block_keys)}",
        )

    definitions = block.get("eligibility_kind_definitions")
    if not isinstance(definitions, dict) or set(definitions) != ELIGIBILITY_KINDS:
        lint.fail(
            ACTION_REGISTRY,
            f"approval eligibility kind definitions must equal {sorted(ELIGIBILITY_KINDS)}",
        )
        definitions = {}

    mapping_definitions = registry.get("event_mapping_kind_definitions")
    defaults = block.get("event_mapping_defaults")
    if not isinstance(mapping_definitions, dict) or not isinstance(defaults, dict):
        lint.fail(ACTION_REGISTRY, "approval event_mapping_defaults must be an object")
        defaults = {}
    elif set(defaults) != set(mapping_definitions):
        lint.fail(
            ACTION_REGISTRY,
            "approval event_mapping_defaults must cover every event_mapping_kind exactly",
        )
    for mapping_kind, eligibility in defaults.items():
        if eligibility not in ELIGIBILITY_KINDS:
            lint.fail(
                ACTION_REGISTRY,
                f"approval default {mapping_kind!r} has unknown eligibility {eligibility!r}",
            )
    if defaults.get("non_event_surface") != "ineligible_no_registered_carrier":
        lint.fail(
            ACTION_REGISTRY,
            "non_event_surface MUST default to ineligible_no_registered_carrier",
        )
    for mapping_kind, eligibility in defaults.items():
        if mapping_kind != "non_event_surface" and eligibility != "event_submission_carrier":
            lint.fail(
                ACTION_REGISTRY,
                f"durable mapping kind {mapping_kind!r} MUST use event_submission_carrier",
            )

    operation_rows = operations.get("operations")
    operation_by_id = {
        row.get("operation_id"): row
        for row in operation_rows if isinstance(row, dict) and isinstance(row.get("operation_id"), str)
    } if isinstance(operation_rows, list) else {}

    carriers = block.get("carriers")
    carrier_by_id: dict[str, dict[str, Any]] = {}
    operation_target_operations: set[str] = set()
    required_carrier_keys = {
        "carrier_id",
        "carrier_class",
        "operation_id",
        "request_schema_ref",
        "carrier_schema_ref",
        "carrier_field",
        "evidence_schema_ref",
        "allowed_target_kinds",
    }
    if not isinstance(carriers, list) or not carriers:
        lint.fail(ACTION_REGISTRY, "approval carriers must be a non-empty array")
        carriers = []
    for index, carrier in enumerate(carriers):
        where = f"approval carriers[{index}]"
        if not isinstance(carrier, dict) or set(carrier) != required_carrier_keys:
            lint.fail(ACTION_REGISTRY, f"{where} must be closed over {sorted(required_carrier_keys)}")
            continue
        carrier_id = carrier.get("carrier_id")
        carrier_class = carrier.get("carrier_class")
        operation_id = carrier.get("operation_id")
        request_ref = carrier.get("request_schema_ref")
        carrier_ref = carrier.get("carrier_schema_ref")
        evidence_ref = carrier.get("evidence_schema_ref")
        target_kinds = carrier.get("allowed_target_kinds")
        if not all(isinstance(value, str) and value for value in (
            carrier_id, carrier_class, operation_id, request_ref, carrier_ref, evidence_ref, carrier.get("carrier_field")
        )):
            lint.fail(ACTION_REGISTRY, f"{where} string fields must be non-empty")
            continue
        if carrier_id in carrier_by_id:
            lint.fail(ACTION_REGISTRY, f"duplicate approval carrier_id {carrier_id!r}")
        carrier_by_id[carrier_id] = carrier
        if carrier_class not in CARRIER_CLASSES:
            lint.fail(ACTION_REGISTRY, f"{where}.carrier_class must be one of {sorted(CARRIER_CLASSES)}")
        if not isinstance(target_kinds, list) or not target_kinds or set(target_kinds) - TARGET_KINDS:
            lint.fail(ACTION_REGISTRY, f"{where}.allowed_target_kinds must be a non-empty subset of {sorted(TARGET_KINDS)}")
            target_kinds = []
        if "operation" in target_kinds:
            operation_target_operations.add(operation_id)
        operation = operation_by_id.get(operation_id)
        if operation is None:
            lint.fail(ACTION_REGISTRY, f"{where} names unregistered operation {operation_id!r}")
        elif operation.get("request_schema_ref") != request_ref:
            lint.fail(
                ACTION_REGISTRY,
                f"{where}.request_schema_ref does not equal {operation_id}'s canonical request schema",
            )
        if not _schema_location_reachable(lint, request_ref, carrier_ref):
            lint.fail(
                ACTION_REGISTRY,
                f"{where} carrier_schema_ref is not reachable from the canonical request schema",
            )
        resolved = _resolve_schema_node(lint, carrier_ref)
        if resolved is not None:
            carrier_path, node = resolved
            if not isinstance(node, dict) or node.get("type") != "array" or node.get("minItems") != 1:
                lint.fail(ACTION_REGISTRY, f"{where} carrier schema must be a non-empty array")
            else:
                item_ref = (node.get("items") or {}).get("$ref") if isinstance(node.get("items"), dict) else None
                if not isinstance(item_ref, str) or _normalize_ref(carrier_path, item_ref) != _normalize_ref(ACTION_REGISTRY, evidence_ref):
                    lint.fail(ACTION_REGISTRY, f"{where} items do not reference evidence_schema_ref")

    defaults_by_eligibility = block.get("default_carrier_by_eligibility_kind")
    if not isinstance(defaults_by_eligibility, dict) or set(defaults_by_eligibility) != {"event_submission_carrier"}:
        lint.fail(
            ACTION_REGISTRY,
            "default_carrier_by_eligibility_kind must contain only event_submission_carrier",
        )
        defaults_by_eligibility = {}
    for eligibility, carrier_id in defaults_by_eligibility.items():
        if carrier_id not in carrier_by_id:
            lint.fail(ACTION_REGISTRY, f"{eligibility} names unknown default carrier {carrier_id!r}")
        elif carrier_by_id[carrier_id].get("carrier_class") != "event_submission":
            lint.fail(ACTION_REGISTRY, f"{eligibility} default carrier must have class event_submission")

    action_rows = registry.get("actions")
    action_by_id = {
        row.get("action"): row
        for row in action_rows if isinstance(row, dict) and isinstance(row.get("action"), str)
    } if isinstance(action_rows, list) else {}
    overrides = block.get("action_overrides")
    override_by_action: dict[str, dict[str, Any]] = {}
    if not isinstance(overrides, list):
        lint.fail(ACTION_REGISTRY, "approval action_overrides must be an array")
        overrides = []
    for index, override in enumerate(overrides):
        if not isinstance(override, dict) or set(override) != {"action", "eligibility_kind", "carrier_id"}:
            lint.fail(ACTION_REGISTRY, f"approval action_overrides[{index}] has an open or incomplete shape")
            continue
        action = override.get("action")
        if action in override_by_action:
            lint.fail(ACTION_REGISTRY, f"duplicate approval action override for {action!r}")
        override_by_action[action] = override
        row = action_by_id.get(action)
        if row is None:
            lint.fail(ACTION_REGISTRY, f"approval action override names unknown action {action!r}")
            continue
        if row.get("event_mapping_kind") != "non_event_surface":
            carrier = carrier_by_id.get(override.get("carrier_id"), {})
            operation = operation_by_id.get(carrier.get("operation_id"), {})
            effect = operation.get("durable_effect", {})
            targets = row.get("target_event_kinds", [])
            if effect.get("kind") != "event_log" or not targets or not set(targets).issubset(effect.get("event_kinds", [])):
                lint.fail(ACTION_REGISTRY, f"approval action override {action!r} requires a registered aggregate carrier covering every target Event kind")
        if override.get("eligibility_kind") != "registered_operation_carrier":
            lint.fail(ACTION_REGISTRY, f"approval action override {action!r} must select registered_operation_carrier")
        if override.get("carrier_id") not in carrier_by_id:
            lint.fail(ACTION_REGISTRY, f"approval action override {action!r} names unknown carrier")
        elif carrier_by_id[override["carrier_id"]].get("carrier_class") != "non_event_operation":
            lint.fail(ACTION_REGISTRY, f"approval action override {action!r} must name a non_event_operation carrier")

    for action, row in action_by_id.items():
        mapping_kind = row.get("event_mapping_kind")
        eligibility = defaults.get(mapping_kind)
        override = override_by_action.get(action)
        if override is not None:
            eligibility = override.get("eligibility_kind")
        if eligibility not in ELIGIBILITY_KINDS:
            lint.fail(ACTION_REGISTRY, f"action {action!r} has no closed approval eligibility")
        if mapping_kind == "non_event_surface" and override is None and eligibility != "ineligible_no_registered_carrier":
            lint.fail(ACTION_REGISTRY, f"non-event action {action!r} is eligible without an explicit carrier override")
        if mapping_kind == "non_event_surface" and override is not None and eligibility != "registered_operation_carrier":
            lint.fail(ACTION_REGISTRY, f"non-event action {action!r} override is not carrier-backed")

    projection = schema.get("x-arkret-operation-target-carrier-operations")
    if not isinstance(projection, list) or set(projection) != operation_target_operations:
        lint.fail(
            APPROVAL_SCHEMA,
            "operation-target carrier operation projection does not equal the reachable carrier registry",
        )
    input_schema = ((schema.get("$defs") or {}).get("approval_signature_input") or {})
    all_of = input_schema.get("allOf") if isinstance(input_schema, dict) else None
    projected_enums = []
    if isinstance(all_of, list):
        for branch in all_of:
            try:
                if branch["if"]["properties"]["approval_target"]["properties"]["target_kind"]["const"] == "operation":
                    projected_enums.append(branch["then"]["properties"]["operation"]["enum"])
            except (KeyError, TypeError):
                continue
    if len(projected_enums) != 1 or not isinstance(projected_enums[0], list) or set(projected_enums[0]) != operation_target_operations:
        lint.fail(
            APPROVAL_SCHEMA,
            "operation approval_target branch must enumerate exactly the reachable carrier operations",
        )
