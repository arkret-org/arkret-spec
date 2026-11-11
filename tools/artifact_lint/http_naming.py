"""Close the lexical and binding namespaces of the canonical Arkret HTTP API.

Only registered Arkret operations and their OpenAPI HTTP bindings are traversed.
External URL values, raw standard documents and OpenAPI's own keyword namespace
are not Arkret route or parameter names. HTTP header names retain HTTP syntax and
case-insensitive identity instead of inheriting JSON member naming predicates.
"""

from __future__ import annotations

import re
from typing import Any

from .core import ARTIFACTS, ROOT, Lint, load_json, load_yaml


SURFACES = frozenset({"self", "gate", "root", "find", "peer", "open", "edge"})
KINDS = frozenset({"read", "stream", "resource", "command", "upload", "exchange"})
HTTP_METHODS = frozenset({"get", "head", "post", "put", "patch", "delete", "options", "trace", "query"})
SNAKE = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*\Z")
KEBAB = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z")
HEADER_TOKEN = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+\Z")
FORBIDDEN_QUERY_SET_PREFIXES = ("allow_", "deny_", "permitted_", "forbidden_", "blocked_", "banned_")
FORBIDDEN_QUERY_SET_SUFFIXES = ("_allow", "_deny", "_allowlist", "_denylist")
META_OPERATION = "ak.server.read.describe.v1"
META_PATH = "/_arkret/describe"
RULE = "NC-HTTP-001"
TRANSPORT_RULE = "NC-TRANSPORT-001"
PASCAL = re.compile(r"[A-Z][A-Za-z0-9]*\Z")
LIBP2P_PROTOCOL = re.compile(r"/arkret/[a-z][a-z0-9]*(?:-[a-z0-9]+)*/1\.0\.0\Z")


def operation_id_errors(value: Any) -> list[str]:
    """Version, kind and each symbol segment are independent lexical checks."""
    if value == META_OPERATION:
        return []
    if not isinstance(value, str):
        return ["operation_id must be a string"]
    parts = value.split(".")
    if len(parts) < 6 or parts[0] != "ak" or parts[-1] != "v1":
        return ["operation_id must be ak.<surface>.<subject...>.<kind>.<action>.v1"]
    errors = []
    if parts[1] not in SURFACES:
        errors.append("operation_id has an unregistered trust surface")
    if any(not SNAKE.fullmatch(part) for part in parts[1:]):
        errors.append("every operation_id segment must be strict snake_case")
    if parts[-3] not in KINDS:
        errors.append("operation_id has an unregistered kind")
    if parts[-2] in {"post", "put", "patch"}:
        errors.append("operation action must describe an effect, not an HTTP method")
    return errors


def path_name_errors(value: Any) -> list[str]:
    """Validate the route template, never percent-decoded parameter values."""
    if value == META_PATH:
        return []
    if not isinstance(value, str) or not value.startswith("/_arkret/"):
        return ["canonical Arkret paths must be absolute under /_arkret/"]
    parts = value[len("/_arkret/"):].split("/")
    if len(parts) < 2 or parts[0] not in SURFACES:
        return ["path must name a registered trust surface and a resource"]
    errors = []
    for index, part in enumerate(parts[1:], 1):
        if part.startswith("{") and part.endswith("}") and SNAKE.fullmatch(part[1:-1]):
            continue
        if ":" in part:
            tokens = part.split(":")
            if index == len(parts) - 1 and len(tokens) == 2 and all(KEBAB.fullmatch(token) for token in tokens):
                continue
            errors.append(f"invalid terminal resource:action segment {part!r}")
        elif not KEBAB.fullmatch(part):
            errors.append(f"literal route segment must be lowercase kebab-case: {part!r}")
        elif re.fullmatch(r"v[0-9]+", part):
            errors.append("protocol versions must not be encoded as route segments")
    return errors


def _pointer(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _resolve(document: dict[str, Any], value: Any, where: str, errors: list[str], *, path_item: bool = False) -> Any:
    # OAS 3.2 sections 4.9/4.23 differ: Path Item $ref has real siblings;
    # Reference Object siblings cannot replace the referenced object's fields.
    seen = set()
    siblings = {}
    while isinstance(value, dict) and "$ref" in value:
        reference = value["$ref"]
        if not isinstance(reference, str) or not reference.startswith("#/") or reference in seen:
            errors.append(f"{where}: name-bearing OpenAPI object must resolve to a local, acyclic reference")
            return None
        seen.add(reference)
        if path_item:
            local = {key: child for key, child in value.items() if key != "$ref"}
            overlap = siblings.keys() & local.keys()
            if overlap:
                errors.append(f"{where}: Path Item $ref has undefined duplicate sibling fields: {sorted(overlap)}")
            siblings.update(local)
        target: Any = document
        try:
            for part in reference[2:].split("/"):
                target = target[part.replace("~1", "/").replace("~0", "~")]
        except (KeyError, TypeError, IndexError):
            errors.append(f"{where}: unresolved reference {reference!r}")
            return None
        value = target
    if path_item and isinstance(value, dict):
        overlap = siblings.keys() & value.keys()
        if overlap:
            errors.append(f"{where}: Path Item $ref has undefined duplicate sibling fields: {sorted(overlap)}")
        return {**value, **siblings}
    return value


def _header_errors(name: Any, where: str, errors: list[str]) -> None:
    if not isinstance(name, str) or not HEADER_TOKEN.fullmatch(name):
        errors.append(f"{where}: HTTP header name must use the ASCII HTTP token grammar")


def http_naming_errors(document: Any, operation_rows: Any) -> list[str]:
    """Check every registry operation and all name-bearing HTTP binding objects."""
    if not isinstance(document, dict) or not isinstance(document.get("paths"), dict):
        return [f"{RULE}: OpenAPI paths must be an object"]
    if not isinstance(operation_rows, list):
        return [f"{RULE}: operation registry operations must be an array"]
    errors: list[str] = []
    registered: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(operation_rows):
        where = f"operation_registry/operations/{index}"
        if not isinstance(row, dict):
            errors.append(f"{where}: operation row must be an object")
            continue
        value = row.get("operation_id")
        errors.extend(f"{where}: {error}" for error in operation_id_errors(value))
        if not isinstance(value, str):
            continue
        if value in registered:
            errors.append(f"{where}: duplicate operation_id {value!r}")
        registered[value] = row
        http = row.get("http")
        if not isinstance(http, str) or " " not in http:
            errors.append(f"{where}: operation must declare one METHOD /absolute-path binding")
            continue
        method, path = http.split(" ", 1)
        if method.lower() not in HTTP_METHODS or method != method.upper():
            errors.append(f"{where}: HTTP method must use its canonical uppercase token")
        errors.extend(f"{where}: {error}" for error in path_name_errors(path))
        if value == META_OPERATION and http != "GET " + META_PATH:
            errors.append(f"{where}: root metadata operation must bind exactly to GET {META_PATH}")
        elif path == META_PATH and value != META_OPERATION:
            errors.append(f"{where}: root metadata path is reserved for {META_OPERATION}")

    covered = set()
    endpoint_ids = set()
    route_shapes: dict[tuple[str, str], str] = {}
    for path, raw_item in document["paths"].items():
        if not isinstance(path, str):
            errors.append("#/paths: route template keys must be strings")
            continue
        where = "#/paths/" + _pointer(path)
        errors.extend(f"{where}: {error}" for error in path_name_errors(path))
        item = _resolve(document, raw_item, where, errors, path_item=True)
        if not isinstance(item, dict):
            errors.append(f"{where}: path item must be an object")
            continue
        placeholders = re.findall(r"\{([^{}]+)\}", path)
        if len(placeholders) != len(set(placeholders)):
            errors.append(f"{where}: each path parameter must occur once in a route template")
        for method, operation in item.items():
            if method not in HTTP_METHODS:
                if method == "additionalOperations" and operation:
                    errors.append(f"{where}: current-v1 bindings must use the registered HTTP method set, not additionalOperations")
                elif isinstance(operation, dict) and "operationId" in operation:
                    errors.append(f"{where}/{method}: unregistered or incorrectly cased HTTP method cannot hide an operation")
                continue
            if not isinstance(operation, dict):
                errors.append(f"{where}/{method}: operation must be an object")
                continue
            operation_where = where + "/" + method
            endpoint = operation.get("operationId")
            exact = endpoint + ".v1" if isinstance(endpoint, str) else None
            if not isinstance(endpoint, str) or operation_id_errors(exact):
                errors.append(f"{operation_where}: operationId must be the strict unversioned endpoint identity")
            if isinstance(endpoint, str):
                if endpoint in endpoint_ids:
                    errors.append(f"{operation_where}: duplicate operationId {endpoint!r}")
                endpoint_ids.add(endpoint)
            row = registered.get(exact)
            if row is None:
                errors.append(f"{operation_where}: operationId does not name a registered exact v1 operation")
            elif row.get("http") != method.upper() + " " + path:
                errors.append(f"{operation_where}: operationId method/path differs from its registered operation")
            else:
                covered.add(exact)
            operation_parts = exact.split(".") if exact else []
            operation_kind = operation_parts[-3] if len(operation_parts) >= 3 else None
            if ":" in path.rsplit("/", 1)[-1] and (method != "post" or operation_kind not in {"command", "exchange", "upload"}):
                errors.append(f"{operation_where}: terminal :action denotes an explicitly registered POST command, upload or exchange")
            shape = (method, re.sub(r"\{[^{}]+\}", "{}", path))
            previous = route_shapes.setdefault(shape, path)
            if previous != path:
                errors.append(f"{operation_where}: path parameter spelling aliases the route {previous!r}")
            parameter_names: dict[tuple[str, str], str] = {}
            for source, parameter_list in ((where, item.get("parameters", [])), (operation_where, operation.get("parameters", []))):
                if not isinstance(parameter_list, list):
                    errors.append(f"{source}/parameters: parameters must be an array")
                    continue
                local_names = set()
                for index, raw_parameter in enumerate(parameter_list):
                    parameter_where = f"{source}/parameters/{index}"
                    parameter = _resolve(document, raw_parameter, parameter_where, errors)
                    if not isinstance(parameter, dict):
                        errors.append(f"{parameter_where}: parameter must be an object")
                        continue
                    location, name = parameter.get("in"), parameter.get("name")
                    if location in {"path", "query"} and (not isinstance(name, str) or not SNAKE.fullmatch(name)):
                        errors.append(f"{parameter_where}: path/query names must be strict snake_case")
                    if location == "query" and isinstance(name, str) and (
                        name.startswith(FORBIDDEN_QUERY_SET_PREFIXES)
                        or name.endswith(FORBIDDEN_QUERY_SET_SUFFIXES)
                    ):
                        errors.append(f"{parameter_where}: query allow/deny collections must use allowed_/denied_ prefixes, including comma-separated wire collections")
                    if location == "header":
                        _header_errors(name, parameter_where, errors)
                    key = (str(location), str(name).lower() if location == "header" else str(name))
                    if key in local_names:
                        errors.append(f"{parameter_where}: duplicate parameter identity {key!r}")
                    local_names.add(key)
                    if key in parameter_names and location == "header" and parameter_names[key] != name:
                        errors.append(f"{parameter_where}: header override must retain its declared canonical spelling")
                    parameter_names[key] = name
                    if location == "path" and parameter.get("required") is not True:
                        errors.append(f"{parameter_where}: path parameters must be required")
            declared_paths = {name for (location, name) in parameter_names if location == "path"}
            if declared_paths != set(placeholders):
                errors.append(f"{operation_where}: path parameter declarations must exactly match route placeholders")
            responses = operation.get("responses", {})
            if not isinstance(responses, dict):
                errors.append(f"{operation_where}: responses must be an object")
                continue
            for status, raw_response in responses.items():
                response_where = f"{operation_where}/responses/{status}"
                response = _resolve(document, raw_response, response_where, errors)
                if not isinstance(response, dict):
                    continue
                headers = response.get("headers", {})
                if not isinstance(headers, dict):
                    errors.append(f"{response_where}: response headers must be an object")
                    continue
                normalized = set()
                for name in headers:
                    _header_errors(name, response_where, errors)
                    if not isinstance(name, str):
                        continue
                    if name.lower() in normalized:
                        errors.append(f"{response_where}: duplicate case-insensitive response header {name!r}")
                    normalized.add(name.lower())
    for operation_id in sorted(set(registered) - covered):
        errors.append(f"operation_registry: registered operation lacks its exact OpenAPI binding: {operation_id}")
    for key, raw_scheme in document.get("components", {}).get("securitySchemes", {}).items():
        where = "#/components/securitySchemes/" + _pointer(key)
        scheme = _resolve(document, raw_scheme, where, errors)
        if isinstance(scheme, dict) and scheme.get("in") == "header":
            _header_errors(scheme.get("name"), where, errors)
    return [f"{RULE} {error}" for error in errors]


def http_index_errors(text: str, operation_rows: list) -> list[str]:
    """The searchable prose index must preserve each canonical HTTP binding."""
    begin = "<!-- BEGIN GENERATED OPERATION FIELD TABLE -->"
    end = "<!-- END GENERATED OPERATION FIELD TABLE -->"
    if text.count(begin) != 1 or text.count(end) != 1 or text.index(begin) >= text.index(end):
        return [f"{RULE}: prose HTTP index must have one ordered generated-table boundary pair"]
    text = text.split(begin, 1)[1].split(end, 1)[0]
    observed = {}
    errors = []
    for number, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        cells = [cell.strip() for cell in re.split(r"(?<!\\)\|", line[1:-1])]
        if cells == ["Operation", "HTTP", "Required", "Optional", "Constraints"]:
            continue
        if len(cells) == 5 and all(re.fullmatch(r":?-+:?", cell) for cell in cells):
            continue
        if not line.startswith("|") or not line.endswith("|") or len(cells) != 5:
            errors.append(f"index line {number}: malformed operation table row")
            continue
        first = re.fullmatch(r"`([^`]+)`", cells[0])
        second = re.fullmatch(r"`([^`]+)`", cells[1])
        if not first or not second:
            errors.append(f"index line {number}: operation and binding must be exact code-span cells")
            continue
        operation_id, binding = first[1], second[1]
        if operation_id in observed:
            errors.append(f"{operation_id}: duplicate operation index row")
        observed[operation_id] = binding
    expected = {row["operation_id"]: row["http"] for row in operation_rows
                if isinstance(row, dict) and isinstance(row.get("operation_id"), str)
                and isinstance(row.get("http"), str)}
    for operation_id in sorted(expected.keys() | observed.keys()):
        if expected.get(operation_id) != observed.get(operation_id):
            errors.append(f"{operation_id}: prose HTTP index differs from its canonical binding")
    return [f"{RULE} {error}" for error in errors]


def check_http_naming(lint: Lint) -> None:
    api_path = ARTIFACTS / "openapi" / "arkret-service-api.openapi.yaml"
    registry_path = ARTIFACTS / "registry" / "operation-registry.json"
    api = load_yaml(lint, api_path)
    registry = load_json(lint, registry_path)
    if not isinstance(registry, dict):
        return
    for error in http_naming_errors(api, registry.get("operations")):
        lint.fail(api_path, error)
    index_path = ROOT / "spec/v1/zh/sync/service-http-binding.md"
    if isinstance(registry.get("operations"), list):
        try:
            index = index_path.read_text(encoding="utf-8")
        except OSError as exc:
            lint.fail(index_path, f"{RULE}: cannot read canonical binding index: {exc}")
        else:
            for error in http_index_errors(index, registry["operations"]):
                lint.fail(index_path, error)


def _pascal_name(value: Any) -> bool:
    return isinstance(value, str) and bool(PASCAL.fullmatch(value)) and not re.search(r"[A-Z]{2,}", value)


def _topic_name(value: Any) -> bool:
    return isinstance(value, str) and all(SNAKE.fullmatch(part) for part in value.split("."))


def transport_naming_errors(document: Any, operation_rows: Any) -> list[str]:
    """Validate every named alternative binding without enabling that binding."""
    if not isinstance(document, dict) or not isinstance(operation_rows, list):
        return [f"{TRANSPORT_RULE}: non-HTTP binding catalog and operation rows must be structured objects"]
    errors = []
    registered = {row.get("operation_id"): row for row in operation_rows if isinstance(row, dict) and isinstance(row.get("operation_id"), str)}
    expected_grpc: dict[str, str] = {}
    expected_mq: dict[str, str] = {}
    for operation_id, row in registered.items():
        if "grpc" in row:
            binding = row["grpc"]
            if not isinstance(binding, str) or len(binding.split("/")) != 2 or not all(_pascal_name(part) for part in binding.split("/")):
                errors.append(f"{operation_id}: gRPC binding must be Service/Method with folded-acronym PascalCase names")
            else:
                previous = expected_grpc.setdefault(binding, operation_id)
                if previous != operation_id:
                    errors.append(f"{operation_id}: duplicate gRPC binding {binding!r}")
        if "mq" in row:
            binding = row["mq"]
            if not _topic_name(binding):
                errors.append(f"{operation_id}: MQ topics must use dot-separated strict snake_case segments")
            else:
                previous = expected_mq.setdefault(binding, operation_id)
                if previous != operation_id:
                    errors.append(f"{operation_id}: duplicate MQ topic {binding!r}")
    actual_grpc: dict[str, str] = {}
    actual_mq: dict[str, str] = {}
    grpc = document.get("grpc", {})
    services = grpc.get("services", {}) if isinstance(grpc, dict) else None
    if not isinstance(services, dict):
        errors.append("grpc/services must be an object")
        services = {}
    for service, methods in services.items():
        if not _pascal_name(service):
            errors.append(f"grpc/services/{service}: service must use PascalCase with folded acronyms")
        if not isinstance(methods, dict) or not methods:
            errors.append(f"grpc/services/{service}: service must declare a nonempty method map")
            continue
        for method, operation_id in methods.items():
            binding = f"{service}/{method}"
            if not _pascal_name(method):
                errors.append(f"grpc/{binding}: method must use PascalCase with folded acronyms")
            if operation_id_errors(operation_id) or operation_id not in registered:
                errors.append(f"grpc/{binding}: method must name an exact registered operation_id")
            elif registered[operation_id].get("grpc") != binding:
                errors.append(f"grpc/{binding}: method differs from the canonical operation binding")
            actual_grpc[binding] = operation_id
    mq = document.get("mq", {})
    topics = mq.get("topics", {}) if isinstance(mq, dict) else None
    if not isinstance(topics, dict):
        errors.append("mq/topics must be an object")
        topics = {}
    for topic, operation_id in topics.items():
        if not _topic_name(topic):
            errors.append(f"mq/topics/{topic}: topic must use dot-separated strict snake_case segments")
        if operation_id_errors(operation_id) or operation_id not in registered:
            errors.append(f"mq/topics/{topic}: topic must name an exact registered operation_id")
        elif registered[operation_id].get("mq") != topic:
            errors.append(f"mq/topics/{topic}: topic differs from the canonical operation binding")
        actual_mq[topic] = operation_id
    for binding, operation_id in expected_grpc.items():
        if actual_grpc.get(binding) != operation_id:
            errors.append(f"{operation_id}: canonical gRPC binding is absent from non-HTTP bindings")
    for topic, operation_id in expected_mq.items():
        if actual_mq.get(topic) != operation_id:
            errors.append(f"{operation_id}: canonical MQ binding is absent from non-HTTP bindings")
    frames = document.get("frame_schemas", {})
    sse = frames.get("sse", {}) if isinstance(frames, dict) else None
    events = sse.get("event_types", []) if isinstance(sse, dict) else None
    if not isinstance(events, list):
        errors.append("frame_schemas/sse/event_types must be an array")
    else:
        seen_events = set()
        for index, event in enumerate(events):
            if not _topic_name(event):
                errors.append(f"frame_schemas/sse/event_types/{index}: event type must use dot-separated strict snake_case segments")
            elif event in seen_events:
                errors.append(f"frame_schemas/sse/event_types/{index}: duplicate event type {event!r}")
            if isinstance(event, str):
                seen_events.add(event)
    libp2p = document.get("libp2p", {})
    protocols = libp2p.get("suggested_protocols", []) if isinstance(libp2p, dict) else None
    if not isinstance(protocols, list):
        errors.append("libp2p/suggested_protocols must be an array")
    else:
        seen_protocols = set()
        for index, protocol in enumerate(protocols):
            if not isinstance(protocol, str) or not LIBP2P_PROTOCOL.fullmatch(protocol):
                errors.append(f"libp2p/suggested_protocols/{index}: current protocol identifier must be /arkret/<kebab-name>/1.0.0, not an HTTP route")
            elif protocol in seen_protocols:
                errors.append(f"libp2p/suggested_protocols/{index}: duplicate protocol identifier")
            if isinstance(protocol, str):
                seen_protocols.add(protocol)
    return [f"{TRANSPORT_RULE} {error}" for error in errors]


def check_transport_naming(lint: Lint) -> None:
    binding_path = ARTIFACTS / "bindings" / "non-http-bindings.yaml"
    registry_path = ARTIFACTS / "registry" / "operation-registry.json"
    binding = load_yaml(lint, binding_path)
    registry = load_json(lint, registry_path)
    if not isinstance(registry, dict):
        return
    for error in transport_naming_errors(binding, registry.get("operations")):
        lint.fail(binding_path, error)
