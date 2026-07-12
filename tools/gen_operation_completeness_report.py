#!/usr/bin/env python3
"""Generate operation-completeness-report.json.

This report covers every operation in the canonical operation registry
(``registry/contract-catalog.json`` -> ``operation_registry``) and records, per
operation, the machine-readable schema-contract completeness state derived from
three sources of truth:

  * the operation registry (declared ``request_schema_ref`` /
    ``response_schema_ref`` and ``success_shape_kind``),
  * the OpenAPI document (``openapi/arkret-service-api.openapi.yaml``) — which
    request/response component each operation actually binds, and
  * the operation field table in ``zh/sync/service-http-binding.md`` (the prose
    constraint that any declared registry ref must be mentioned there).

The report is a derived artifact: JSON Schema files and the registry remain the
canonical source. ``tools/artifact_pipeline.py generate`` regenerates it and
``tools/artifact_pipeline.py check`` verifies drift via ``check`` mode below;
because the generator iterates every operation in the registry, the drift check
also enforces registry/report operation-set equality.

``completeness_class`` taxonomy (one value per operation, first match wins):

  typed_schema          registry declares a request and/or response artifact
                        schema ref (the typed DTO contract is machine-readable).
  generic_binding       OpenAPI binds the governed generic OperationRequest /
                        OperationResult envelope (profile-gated escape hatch).
  streaming_frame_schema  success_shape_kind is event_stream (NDJSON frame
                        stream; the frame schema lives in a dedicated frame
                        schema, not a single request/response DTO).
  binary_or_redirect    success_shape_kind is binary_stream / metadata_headers /
                        redirect (no JSON DTO body by design).
  service_describe      success_shape_kind is service_describe (response is the
                        shared ServiceDescribe contract; bound once, globally).
  no_request_body       read-only GET/HEAD with no request body whose response
                        OpenAPI component is NOT yet mirrored to an artifact
                        schema ref; the only open gap is response typing.
  schema_missing        OpenAPI declares a typed request and/or response
                        component but no artifact schema ref is wired in the
                        registry yet (the actionable backlog).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "spec" / "v1" / "artifacts"
CATALOG = ARTIFACTS / "registry" / "contract-catalog.json"
OPENAPI = ARTIFACTS / "openapi" / "arkret-service-api.openapi.yaml"
BINDING = ROOT / "spec" / "v1" / "zh" / "sync" / "service-http-binding.md"
REPORT = ARTIFACTS / "reports" / "operation-completeness-report.json"

GENERIC_REQUEST_REF = "#/components/schemas/OperationRequest"
GENERIC_RESULT_REF = "#/components/schemas/OperationResult"

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def catalog_generation_metadata(catalog: dict[str, Any]) -> tuple[str, str]:
    version = catalog.get("version")
    generated_at = catalog.get("generated_at")
    if not isinstance(version, str) or not version:
        raise SystemExit("contract catalog missing version")
    if not isinstance(generated_at, str) or not generated_at:
        raise SystemExit("contract catalog missing generated_at")
    try:
        datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SystemExit(f"contract catalog generated_at must be RFC3339: {generated_at}") from exc
    if len(version) == 10 and generated_at[:10] != version:
        raise SystemExit("contract catalog generated_at date must match version")
    return version, generated_at


def normalize_artifact_ref(ref: str | None) -> str | None:
    if not isinstance(ref, str) or not ref:
        return None
    for prefix in ("../schemas/", "./schemas/"):
        if ref.startswith(prefix):
            return "schemas/" + ref[len(prefix):]
    return ref


def openapi_artifact_ref(schema: Any, components: dict[str, Any]) -> str | None:
    """Resolve the artifact schema ref an OpenAPI schema binds, mirroring
    lint_artifacts.openapi_artifact_schema_ref. Returns a ``schemas/...`` ref
    when the bound OpenAPI component is a thin ``$ref`` wrapper to an artifact
    schema, otherwise the raw ``#/components/...`` ref (an inline component)."""
    if not isinstance(schema, dict):
        return None
    ref = schema.get("$ref")
    if not isinstance(ref, str):
        return None
    if ref.startswith("#/components/schemas/"):
        component_name = ref.rsplit("/", 1)[-1]
        component_schema = components.get(component_name)
        if isinstance(component_schema, dict):
            component_ref = component_schema.get("$ref")
            if isinstance(component_ref, str):
                return normalize_artifact_ref(component_ref)
        return ref
    return normalize_artifact_ref(ref)


def request_schema(operation: dict[str, Any]) -> Any:
    content = operation.get("requestBody", {}).get("content", {})
    if not isinstance(content, dict):
        return None
    for media_type in ("application/json", "multipart/form-data", "application/octet-stream"):
        media = content.get(media_type)
        schema = media.get("schema") if isinstance(media, dict) else None
        if isinstance(schema, dict):
            return schema
    for media in content.values():
        schema = media.get("schema") if isinstance(media, dict) else None
        if isinstance(schema, dict):
            return schema
    return None


def collect_openapi_facts(openapi: dict[str, Any]) -> dict[str, dict[str, Any]]:
    components = openapi.get("components", {}).get("schemas", {})
    if not isinstance(components, dict):
        components = {}
    facts: dict[str, dict[str, Any]] = {}
    for path_item in openapi.get("paths", {}).values():
        if not isinstance(path_item, dict):
            continue
        for method in ("get", "post", "put", "patch", "delete", "head"):
            operation = path_item.get(method)
            if not isinstance(operation, dict):
                continue
            operation_id = operation.get("operationId")
            if not isinstance(operation_id, str) or not operation_id:
                continue
            req_schema = request_schema(operation)
            ok_response = (
                operation.get("responses", {})
                .get("200", {})
            )
            resp_schema = (
                ok_response.get("content", {})
                .get("application/json", {})
                .get("schema")
                if isinstance(ok_response, dict)
                else None
            )
            req_raw_ref = req_schema.get("$ref") if isinstance(req_schema, dict) else None
            resp_raw_ref = resp_schema.get("$ref") if isinstance(resp_schema, dict) else None
            has_request_body = bool(operation.get("requestBody"))
            response_media = []
            ok = operation.get("responses", {}).get("200", {})
            if isinstance(ok, dict):
                response_media = sorted((ok.get("content") or {}).keys())
            facts[operation_id] = {
                "method": method,
                "request_component_ref": req_raw_ref,
                "response_component_ref": resp_raw_ref,
                "request_artifact_ref": openapi_artifact_ref(req_schema, components),
                "response_artifact_ref": openapi_artifact_ref(resp_schema, components),
                "generic_request": req_raw_ref == GENERIC_REQUEST_REF,
                "generic_response": resp_raw_ref == GENERIC_RESULT_REF,
                "has_request_body": has_request_body,
                "response_media": response_media,
            }
    return facts


def classify(
    operation_id: str,
    row: dict[str, Any],
    facts: dict[str, Any] | None,
) -> tuple[str, str]:
    """Return (completeness_class, reason)."""
    shape = row.get("success_shape_kind")
    req_ref = row.get("request_schema_ref")
    resp_ref = row.get("response_schema_ref")
    has_registry_ref = bool(req_ref) or bool(resp_ref)

    if has_registry_ref:
        sides = []
        if req_ref:
            sides.append("request")
        if resp_ref:
            sides.append("response")
        return (
            "typed_schema",
            f"registry declares artifact schema ref(s) for {', '.join(sides)}.",
        )

    if isinstance(row.get("generic_binding"), dict):
        return (
            "generic_binding",
            "OpenAPI binds the governed generic OperationRequest/OperationResult envelope.",
        )

    if shape == "event_stream":
        return (
            "streaming_frame_schema",
            "NDJSON event/account frame stream; frame contract lives in a dedicated frame schema, not a single DTO.",
        )

    if shape in ("binary_stream", "metadata_headers", "redirect"):
        return (
            "binary_or_redirect",
            f"success_shape_kind={shape!r}; no JSON DTO body by design.",
        )

    if shape == "service_describe":
        return (
            "service_describe",
            "response is the shared ServiceDescribe contract (bound globally as schemas/service-describe.schema.json).",
        )

    # From here: no registry ref, not generic, not stream/binary/describe.
    if facts is None:
        return ("schema_missing", "operation absent from OpenAPI document; no binding facts available.")

    req_component = facts.get("request_component_ref")
    resp_component = facts.get("response_component_ref")
    has_typed_request = isinstance(req_component, str)
    has_typed_response = isinstance(resp_component, str)

    if not has_typed_request and not has_typed_response:
        if not facts.get("has_request_body"):
            return (
                "no_request_body",
                "read-only operation with no request body and no typed JSON response component in OpenAPI.",
            )
        return (
            "schema_missing",
            "operation has a request body but no typed request/response component is bound in OpenAPI.",
        )

    # OpenAPI declares a typed component on at least one side, but the registry
    # has no artifact schema ref. This is the actionable mirroring backlog.
    open_sides = []
    if has_typed_request:
        open_sides.append(f"request={req_component}")
    if has_typed_response:
        open_sides.append(f"response={resp_component}")
    return (
        "schema_missing",
        "OpenAPI binds inline component(s) (" + ", ".join(open_sides) + ") "
        "not yet mirrored to a canonical artifact schema ref in the registry.",
    )


def build_report() -> dict[str, Any]:
    catalog = load_json(CATALOG)
    version, generated_at = catalog_generation_metadata(catalog)
    operation_registry = catalog.get("operation_registry") or {}
    operations = operation_registry.get("operations") or []

    tier_by_op: dict[str, str] = {}
    for group in operation_registry.get("surface_groups", []) or []:
        if not isinstance(group, dict):
            continue
        tier = group.get("tier")
        for op_id in group.get("operations", []) or []:
            if isinstance(op_id, str) and isinstance(tier, str):
                tier_by_op[op_id] = tier

    if yaml is None:
        raise SystemExit("PyYAML is required to read the OpenAPI document")
    openapi = yaml.safe_load(OPENAPI.read_text(encoding="utf-8"))
    facts = collect_openapi_facts(openapi if isinstance(openapi, dict) else {})

    rows: list[dict[str, Any]] = []
    for op in operations:
        if not isinstance(op, dict):
            continue
        operation_id = op.get("operation_id")
        if not isinstance(operation_id, str) or not operation_id:
            continue
        op_facts = facts.get(operation_id)
        completeness_class, reason = classify(operation_id, op, op_facts)

        openapi_component_refs: dict[str, str] = {}
        if op_facts:
            if isinstance(op_facts.get("request_component_ref"), str):
                openapi_component_refs["request"] = op_facts["request_component_ref"]
            if isinstance(op_facts.get("response_component_ref"), str):
                openapi_component_refs["response"] = op_facts["response_component_ref"]

        rows.append(
            {
                "operation_id": operation_id,
                "tier": tier_by_op.get(operation_id),
                "http": op.get("http"),
                "success_shape_kind": op.get("success_shape_kind"),
                "request_schema_ref": op.get("request_schema_ref"),
                "response_schema_ref": op.get("response_schema_ref"),
                "openapi_component_refs": openapi_component_refs,
                "completeness_class": completeness_class,
                "reason": reason,
            }
        )

    rows.sort(key=lambda r: r["operation_id"])

    class_counts: dict[str, int] = {}
    tier_class_counts: dict[str, dict[str, int]] = {}
    for r in rows:
        cc = r["completeness_class"]
        class_counts[cc] = class_counts.get(cc, 0) + 1
        tier = r["tier"] or "unknown"
        tier_class_counts.setdefault(tier, {})
        tier_class_counts[tier][cc] = tier_class_counts[tier].get(cc, 0) + 1

    return {
        "version": version,
        "source_of_truth": False,
        "generated_at": generated_at,
        "generated_from": [
            "registry/contract-catalog.json",
            "openapi/arkret-service-api.openapi.yaml",
        ],
        "generated_by": "tools/gen_operation_completeness_report.py",
        "description": (
            "Per-operation machine-readable schema-contract completeness report "
            "covering every operation in the operation registry. JSON Schema "
            "files and the registry remain canonical; this report is a derived "
            "summary for SDK / conformance tooling and schema-coverage review."
        ),
        "completeness_class_definitions": {
            "typed_schema": "registry declares a request and/or response artifact schema ref.",
            "generic_binding": "OpenAPI binds the governed generic OperationRequest/OperationResult envelope.",
            "streaming_frame_schema": "success_shape_kind=event_stream; frame contract in a dedicated frame schema.",
            "binary_or_redirect": "success_shape_kind=binary_stream/metadata_headers/redirect; no JSON DTO body by design.",
            "service_describe": "response is the shared ServiceDescribe contract.",
            "no_request_body": "read-only GET/HEAD with no request body and no typed JSON response component.",
            "schema_missing": "OpenAPI declares a typed request/response component not yet mirrored to an artifact schema ref.",
        },
        "summary": {
            "total_operations": len(rows),
            "by_completeness_class": dict(sorted(class_counts.items())),
            "by_tier_and_class": {
                tier: dict(sorted(counts.items()))
                for tier, counts in sorted(tier_class_counts.items())
            },
        },
        "operations": rows,
    }


def write_report() -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(dump_json(build_report()), encoding="utf-8")
    print(f"updated {REPORT.relative_to(ROOT).as_posix()}")


def check_report() -> int:
    expected = dump_json(build_report())
    if not REPORT.exists():
        print(f"missing {REPORT.relative_to(ROOT).as_posix()} (run python tools/gen_operation_completeness_report.py)", file=sys.stderr)
        return 1
    actual = REPORT.read_text(encoding="utf-8")
    if actual != expected:
        print(
            f"operation completeness report drift: {REPORT.relative_to(ROOT).as_posix()} "
            "(run python tools/gen_operation_completeness_report.py)",
            file=sys.stderr,
        )
        return 1
    print("operation completeness report: clean")
    return 0


def main(argv: list[str]) -> int:
    mode = argv[1] if len(argv) > 1 else "generate"
    if mode == "check":
        return check_report()
    write_report()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
