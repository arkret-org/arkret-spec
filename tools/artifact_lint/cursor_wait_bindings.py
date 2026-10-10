"""Validate the closed operation/binding wait carrier catalog."""

from .core import ARTIFACTS, Lint, load_json, load_yaml


def catalog_errors(registry: dict, openapi: dict) -> list[str]:
    errors = []
    operations = {row["operation_id"]: row for row in registry.get("operations", [])}
    seen = set()
    catalog = registry.get("wait_for_bindings")
    if not isinstance(catalog, list):
        return ["wait_for_bindings must be an array"]
    http_waits = set()
    for row in catalog:
        if not isinstance(row, dict) or set(row) != {"operation_id", "binding_kind", "carrier", "field"}:
            errors.append("wait carrier must use the closed four-field shape")
            continue
        if not all(isinstance(value, str) and value for value in row.values()):
            errors.append("wait carrier fields must be non-empty strings")
            continue
        identity = (row["operation_id"], row["binding_kind"])
        if identity in seen:
            errors.append(f"duplicate wait carrier: {identity}")
        seen.add(identity)
        if identity[0] not in operations:
            errors.append(f"unknown wait operation: {identity[0]}")
            continue
        expected = {"http_json": ("header", "X-Arkret-Wait-For"), "websocket": ("channel_open_parameters", "wait_for")}.get(identity[1])
        if expected != (row["carrier"], row["field"]):
            errors.append(f"unregistered wait carrier shape: {identity}")
        if identity[1] == "http_json":
            http_waits.add(identity[0])
    for path, item in openapi.get("paths", {}).items():
        for method, operation in item.items():
            if method.upper() not in {"GET", "HEAD", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"}:
                continue
            operation_id = operation.get("operationId", "")
            if not operation_id.endswith(".v1"):
                operation_id += ".v1"
            parameters = operation.get("parameters", [])
            waits = [p for p in parameters if p.get("name", "").lower() == "x-arkret-wait-for"]
            if bool(waits) != (operation_id in http_waits) or len(waits) > 1:
                errors.append(f"OpenAPI wait carrier differs from catalog: {method} {path}")
            for parameter in waits:
                if parameter.get("in") != "header" or parameter.get("schema", {}).get("pattern") != "^ak:cursor:[A-Za-z0-9_-]+$":
                    errors.append(f"wait header must carry exactly one opaque cursor: {method} {path}")
    return errors


def check_cursor_wait_bindings(lint: Lint) -> None:
    path = ARTIFACTS / "registry" / "contract-registry.json"
    registry = load_json(lint, path)
    openapi = load_yaml(lint, ARTIFACTS / "openapi" / "arkret-service-api.openapi.yaml")
    if isinstance(registry, dict) and isinstance(openapi, dict):
        for error in catalog_errors(registry.get("operation_registry", {}), openapi):
            lint.fail(path, error)
