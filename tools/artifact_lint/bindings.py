"""Artifact lint phase 3: bindings."""

from __future__ import annotations

from .core import (
    ARTIFACTS,
    Any,
    EVENT_KIND_TOKEN_RE,
    GENERIC_OPERATION_REQUEST_REF,
    GENERIC_OPERATION_RESULT_REF,
    Lint,
    OPENAPI_OPERATION_ID_RE,
    Path,
    SPEC_ROOT,
    SUPPLY_EXEMPTION_REGISTRY_PATH,
    _SUPPLY_CALLER_SIGNED_SCHEMAS,
    _SUPPLY_CAS_ECHO_RE,
    _SUPPLY_CLIENT_LOCAL_RE,
    _SUPPLY_DID_LOG_DERIVED_DEFS,
    _SUPPLY_DID_LOG_DERIVED_NAMES,
    _SUPPLY_EVIDENCE_RE,
    _SUPPLY_PAYLOAD_SUPPLY_FILES,
    _SUPPLY_STRUCTURAL_SURFACES,
    _supply_load_exemptions,
    _supply_resolve_ref,
    _supply_schema_files,
    json,
    load_json,
    load_yaml,
    parse_json_file,
    re,
    resolve_json_pointer,
)



def load_artifact_schema_from_ref(lint: Lint, owner: Path, ref: str) -> Any:
    normalized = normalize_artifact_schema_ref(ref)
    if not isinstance(normalized, str) or not normalized.startswith("schemas/"):
        lint.fail(owner, f"schema ref must point to artifacts/schemas: {ref}")
        return None
    file_ref, _, fragment = normalized.partition("#")
    schema_path = ARTIFACTS / file_ref
    document = load_json(lint, schema_path)
    if document is None:
        return None
    try:
        return resolve_json_pointer(document, f"#{fragment}" if fragment else "#")
    except KeyError:
        lint.fail(owner, f"schema ref fragment not found: {ref}")
        return None



def resolve_openapi_component_schema(
    lint: Lint,
    openapi_path: Path,
    components: dict[str, Any],
    component_name: str,
) -> Any:
    schema = components.get(component_name)
    seen: set[str] = set()
    while isinstance(schema, dict):
        ref = schema.get("$ref")
        if not isinstance(ref, str):
            return schema
        if ref.startswith("#/components/schemas/"):
            next_name = ref.rsplit("/", 1)[-1]
            if next_name in seen:
                lint.fail(openapi_path, f"cyclic OpenAPI component ref: {component_name}")
                return None
            seen.add(next_name)
            schema = components.get(next_name)
            continue
        return load_artifact_schema_from_ref(lint, openapi_path, ref)
    return schema



def resolve_openapi_schema_node(
    lint: Lint,
    openapi_path: Path,
    components: dict[str, Any],
    schema: Any,
) -> Any:
    if not isinstance(schema, dict):
        return schema
    ref = schema.get("$ref")
    if not isinstance(ref, str):
        return schema
    if ref.startswith("#/components/schemas/"):
        return resolve_openapi_component_schema(lint, openapi_path, components, ref.rsplit("/", 1)[-1])
    return load_artifact_schema_from_ref(lint, openapi_path, ref)



def schema_ref_targets(ref_schema: Any, component_name: str) -> bool:
    if not isinstance(ref_schema, dict):
        return False
    ref = ref_schema.get("$ref")
    return ref in {
        f"#/components/schemas/{component_name}",
        f"#/$defs/{component_name}",
    } or (isinstance(ref, str) and ref.endswith(f"#/$defs/{component_name}"))



def check_operation_durable_effect_contract(lint: Lint) -> None:
    path = ARTIFACTS / "registry" / "contract-registry.json"
    root = load_json(lint, path) or {}
    event_registry = root.get("event_kind_registry", {})
    operation_registry = root.get("operation_registry", {})
    rows = event_registry.get("event_kinds", []) if isinstance(event_registry, dict) else []
    operations = operation_registry.get("operations", []) if isinstance(operation_registry, dict) else []
    active = {
        row.get("event_kind")
        for row in rows
        if isinstance(row, dict) and row.get("status") != "retired"
    }
    actor_private = {
        row.get("event_kind")
        for row in rows
        if isinstance(row, dict)
        and row.get("status") != "retired"
        and row.get("wire_scope") == "actor_private_event"
    }
    if not isinstance(operations, list):
        lint.fail(path, "operation_registry.operations must be an array")
        return

    def request_pointer_node(operation: dict[str, Any], pointer: Any) -> Any:
        operation_id = operation.get("operation_id", "<unknown>")
        if not isinstance(pointer, str) or not pointer.startswith("/"):
            lint.fail(path, f"{operation_id} durable-effect request path must be an RFC 6901 pointer")
            return None
        request_ref = operation.get("request_schema_ref")
        if not isinstance(request_ref, str):
            lint.fail(path, f"{operation_id} branched durable effect requires request_schema_ref")
            return None
        node = load_artifact_schema_from_ref(lint, path, request_ref)
        for raw_token in pointer[1:].split("/"):
            token = raw_token.replace("~1", "/").replace("~0", "~")
            if not isinstance(node, dict):
                node = None
                break
            properties = node.get("properties")
            node = properties.get(token) if isinstance(properties, dict) else None
        if node is None:
            lint.fail(path, f"{operation_id} durable-effect request path does not resolve: {pointer}")
        return node

    # api-conventions.md 2.4.1: each leaf kind has a literally closed member set,
    # plus one pair that is orthogonal to kind and must co-occur.
    cross_service_pair = ("cross_service_effects", "irreversibility_note")
    leaf_members = {
        "event_log": {
            "kind",
            "event_kinds",
            "event_kind_source",
            "event_kind_sources",
            "event_submission_path",
            "rationale",
            *cross_service_pair,
        },
        "actor_private_event": {"kind", "event_kind", "rationale", *cross_service_pair},
        "none": {"kind", "rationale", *cross_service_pair},
    }
    branched_members = {"kind", "discriminator", "effect_branches"}

    def check_cross_service_pair(operation_id: str, effect: dict[str, Any], label: str) -> None:
        effects = effect.get("cross_service_effects")
        note = effect.get("irreversibility_note")
        present = [name for name in cross_service_pair if name in effect]
        if len(present) == 1:
            lint.fail(
                path,
                f"{operation_id} {label} declares {present[0]} alone; "
                "cross_service_effects and irreversibility_note MUST co-occur",
            )
            return
        if not present:
            return
        if (
            not isinstance(effects, list)
            or not effects
            or any(not isinstance(item, str) or not item for item in effects)
            or len(effects) != len(set(effects))
        ):
            lint.fail(
                path,
                f"{operation_id} {label}.cross_service_effects must be a non-empty, "
                "duplicate-free array of non-empty operation-local slugs",
            )
        if not isinstance(note, str) or not note.strip():
            lint.fail(
                path,
                f"{operation_id} {label}.irreversibility_note must be a non-empty string",
            )

    def check_leaf_effect(operation: dict[str, Any], effect: Any, label: str) -> None:
        operation_id = operation.get("operation_id", "<unknown>")
        if not isinstance(effect, dict):
            lint.fail(path, f"{operation_id} {label} must be an object")
            return
        kind = effect.get("kind")
        allowed = leaf_members.get(kind) if isinstance(kind, str) else None
        if allowed is not None:
            unknown = sorted(set(effect) - allowed)
            if unknown:
                lint.fail(
                    path,
                    f"{operation_id} {label} declares unregistered durable_effect member(s) "
                    f"{unknown} on kind={kind!r}; the leaf member set is closed",
                )
        if kind == "branched":
            lint.fail(
                path,
                f"{operation_id} {label} is a leaf position, but branched is a composition "
                "node and MUST NOT nest",
            )
            return
        check_cross_service_pair(operation_id, effect, label)
        if kind == "event_log":
            event_kinds = effect.get("event_kinds")
            source = effect.get("event_kind_source")
            sources = effect.get("event_kind_sources")
            mapping_forms = sum(value is not None for value in (event_kinds, source, sources))
            if mapping_forms != 1:
                lint.fail(path, f"{operation_id} {label} event_log effect must declare exactly one mapping form")
            if event_kinds is not None:
                if not isinstance(event_kinds, list) or not event_kinds:
                    lint.fail(path, f"{operation_id} {label}.event_kinds must be non-empty")
                else:
                    for event_kind in event_kinds:
                        if event_kind not in active or event_kind in actor_private:
                            lint.fail(path, f"{operation_id} {label} maps to invalid shared Event {event_kind!r}")
            if source is not None and (
                not isinstance(source, str) or not source.startswith("$request.")
            ):
                lint.fail(path, f"{operation_id} {label}.event_kind_source must be a $request JSON path")
            if sources is not None and (
                not isinstance(sources, list)
                or not sources
                or any(not isinstance(item, str) or not item.startswith("$request.") for item in sources)
                or len(sources) != len(set(sources))
            ):
                lint.fail(path, f"{operation_id} {label}.event_kind_sources must be a non-empty unique array of $request JSON paths")
            submission_path = effect.get("event_submission_path")
            if submission_path is not None:
                submission = request_pointer_node(operation, submission_path)
                ref = submission.get("$ref") if isinstance(submission, dict) else None
                if not isinstance(ref, str) or "EventInitialSubmission" not in ref:
                    lint.fail(path, f"{operation_id} {label}.event_submission_path must target EventInitialSubmission")
        elif kind == "actor_private_event":
            if effect.get("event_kind") not in actor_private:
                lint.fail(path, f"{operation_id} {label} must map actor_private_event to an active private kind")
        elif kind == "none":
            rationale = effect.get("rationale")
            if not isinstance(rationale, str) or not rationale:
                lint.fail(path, f"{operation_id} {label} none effect must state a rationale")
        else:
            lint.fail(path, f"{operation_id} {label} has unknown durable_effect kind {kind!r}")

    for operation in operations:
        if not isinstance(operation, dict) or "idempotency_mechanism" not in operation:
            continue
        operation_id = operation.get("operation_id", "<unknown>")
        effect = operation.get("durable_effect")
        if not isinstance(effect, dict):
            lint.fail(path, f"{operation_id} is a write operation without durable_effect")
            continue
        kind = effect.get("kind")
        if kind == "branched":
            unknown = sorted(set(effect) - branched_members)
            if unknown:
                lint.fail(
                    path,
                    f"{operation_id} branched durable_effect declares unregistered member(s) "
                    f"{unknown}; the composition node carries only "
                    f"{sorted(branched_members)}. cross_service_effects / "
                    "irreversibility_note belong on the branch effect that actually has the "
                    "side effect, so one branch's irreversibility is not generalized to every "
                    "request",
                )
            discriminator = effect.get("discriminator")
            branches = effect.get("effect_branches")
            discriminator_path = discriminator.get("request_path") if isinstance(discriminator, dict) else None
            request_pointer_node(operation, discriminator_path)
            if not isinstance(branches, list) or len(branches) < 2:
                lint.fail(path, f"{operation_id} branched durable effect requires at least two effect_branches")
                continue
            equals_values: list[str] = []
            otherwise_count = 0
            for index, branch in enumerate(branches):
                if not isinstance(branch, dict):
                    lint.fail(path, f"{operation_id} effect_branches[{index}] must be an object")
                    continue
                has_equals = isinstance(branch.get("equals"), str) and bool(branch.get("equals"))
                is_otherwise = branch.get("otherwise") is True
                if has_equals == is_otherwise:
                    lint.fail(path, f"{operation_id} effect_branches[{index}] must declare exactly one of equals or otherwise=true")
                if has_equals:
                    equals_values.append(branch["equals"])
                if is_otherwise:
                    otherwise_count += 1
                check_leaf_effect(operation, branch.get("effect"), f"effect_branches[{index}].effect")
            if len(equals_values) != len(set(equals_values)):
                lint.fail(path, f"{operation_id} branched durable effect has duplicate equals values")
            if otherwise_count != 1 or branches[-1].get("otherwise") is not True:
                lint.fail(path, f"{operation_id} branched durable effect requires exactly one final otherwise branch")
        else:
            check_leaf_effect(operation, effect, "durable_effect")



def parse_openapi_operation_http_map(text: str) -> tuple[dict[str, str], list[str]]:
    mapping: dict[str, str] = {}
    errors: list[str] = []
    in_paths = False
    current_path: str | None = None
    current_method: str | None = None

    for line_no, line in enumerate(text.splitlines(), start=1):
        if not in_paths:
            if line.strip() == "paths:":
                in_paths = True
            continue
        if line and not line.startswith(" "):
            break

        path_match = re.match(r"^  (/.*):\s*$", line)
        if path_match:
            current_path = path_match.group(1)
            current_method = None
            continue

        method_match = re.match(r"^    (get|post|put|patch|delete|head|options|trace|query):\s*$", line)
        if method_match and current_path is not None:
            current_method = method_match.group(1).upper()
            continue

        operation_match = re.match(r"^      operationId:\s*([A-Za-z0-9_.-]+)\s*$", line)
        if operation_match and current_path is not None and current_method is not None:
            operation_id = operation_match.group(1)
            http_binding = f"{current_method} {current_path}"
            previous = mapping.get(operation_id)
            if previous is not None and previous != http_binding:
                errors.append(
                    f"line {line_no}: operationId {operation_id} maps to multiple HTTP bindings: "
                    f"{previous} vs {http_binding}"
                )
            mapping[operation_id] = http_binding

    return mapping, errors



def check_openapi_contract_shape(lint: Lint, path: Path, text: str) -> None:
    in_paths = False
    current_path: str | None = None
    current_method: str | None = None
    current_operation_id: str | None = None
    has_request_body = False

    def finish_operation(line_no: int) -> None:
        if current_method in {"post", "put", "patch", "query"} and not has_request_body:
            label = current_operation_id or f"{current_method.upper()} {current_path}"
            lint.fail(path, f"line {line_no}: write operation missing requestBody: {label}")

    for line_no, line in enumerate(text.splitlines(), start=1):
        if not in_paths:
            if line.strip() == "paths:":
                in_paths = True
            continue
        if line and not line.startswith(" "):
            finish_operation(line_no)
            break

        path_match = re.match(r"^  (/.*):\s*$", line)
        if path_match:
            finish_operation(line_no)
            current_path = path_match.group(1)
            current_method = None
            current_operation_id = None
            has_request_body = False
            continue

        method_match = re.match(r"^    (get|post|put|patch|delete|head|options|trace|query):\s*$", line)
        if method_match and current_path is not None:
            finish_operation(line_no)
            current_method = method_match.group(1)
            current_operation_id = None
            has_request_body = False
            continue

        if current_method is None:
            continue
        operation_match = re.match(r"^      operationId:\s*([A-Za-z0-9_.-]+)\s*$", line)
        if operation_match:
            current_operation_id = operation_match.group(1)
        if re.match(r"^      requestBody:\s*$", line):
            has_request_body = True
        if re.match(r"^      headers:\s*$", line):
            label = current_operation_id or f"{current_method.upper()} {current_path}"
            lint.fail(path, f"line {line_no}: operation-level headers are invalid OpenAPI: {label}")

    if in_paths:
        finish_operation(line_no if "line_no" in locals() else 0)



def check_openapi_schema_component_order(lint: Lint) -> None:
    openapi_path = ARTIFACTS / "openapi" / "arkret-service-api.openapi.yaml"
    openapi = load_yaml(lint, openapi_path)
    if not isinstance(openapi, dict):
        return

    schemas = openapi.get("components", {}).get("schemas", {})
    if not isinstance(schemas, dict):
        lint.fail(openapi_path, "components.schemas missing")
        return

    names = list(schemas)
    expected = sorted(names, key=str.casefold)
    if names == expected:
        return

    index, actual, wanted = next(
        (index, actual, expected[index])
        for index, actual in enumerate(names)
        if actual != expected[index]
    )
    lint.fail(
        openapi_path,
        "components.schemas must be sorted alphabetically; "
        f"position {index + 1} has {actual}, expected {wanted}",
    )



def check_operation_surfaces(lint: Lint, known: dict[str, set[str]]) -> None:
    openapi_path = ARTIFACTS / "openapi" / "arkret-service-api.openapi.yaml"
    openapi_text = openapi_path.read_text(encoding="utf-8")
    check_openapi_contract_shape(lint, openapi_path, openapi_text)
    openapi_operation_ids = OPENAPI_OPERATION_ID_RE.findall(openapi_text)
    openapi_set = set(openapi_operation_ids)
    if len(openapi_operation_ids) != len(openapi_set):
        duplicates = sorted({item for item in openapi_operation_ids if openapi_operation_ids.count(item) > 1})
        lint.fail(openapi_path, f"duplicate operationId values: {', '.join(duplicates)}")
    for operation_id in sorted(openapi_set - known["operation_ids"]):
        lint.fail(openapi_path, f"operationId not registered: {operation_id}")
    for operation_id in sorted(known["operation_ids"] - openapi_set):
        lint.fail(openapi_path, f"registered operation_id missing from OpenAPI: {operation_id}")
    openapi_http_map, openapi_parse_errors = parse_openapi_operation_http_map(openapi_text)
    for error in openapi_parse_errors:
        lint.fail(openapi_path, error)
    for operation_id in sorted(known["operation_ids"]):
        expected_http = known["operation_http_map"].get(operation_id)
        actual_http = openapi_http_map.get(operation_id)
        if expected_http is None:
            continue
        if actual_http is None:
            lint.fail(openapi_path, f"operationId missing HTTP path/method mapping: {operation_id}")
        elif actual_http != expected_http:
            lint.fail(
                openapi_path,
                f"operationId HTTP binding mismatch for {operation_id}: "
                f"registry={expected_http!r}, openapi={actual_http!r}",
            )

    openapi = load_yaml(lint, openapi_path)
    operation_registry = load_json(lint, ARTIFACTS / "registry" / "operation-registry.json")
    if isinstance(openapi, dict) and isinstance(operation_registry, dict):
        if openapi.get("openapi") != "3.2.0":
            lint.fail(openapi_path, "Arkret OpenAPI must use 3.2.0 so RFC 10008 QUERY is represented by the standard query field")
        if "x-arkret-compatibility-binding-of" in openapi_path.read_text(encoding="utf-8"):
            lint.fail(openapi_path, "removed HTTP compatibility bindings must not remain in OpenAPI")

    binding_path = ARTIFACTS / "bindings" / "non-http-bindings.yaml"
    binding = load_yaml(lint, binding_path)
    if not isinstance(binding, dict):
        return
    if binding.get("coverage") != "complete_except_http_only":
        lint.fail(binding_path, "non-HTTP binding coverage must be complete_except_http_only")
    binding_text = binding_path.read_text(encoding="utf-8")
    binding_operation_ids = set(EVENT_KIND_TOKEN_RE.findall(binding_text))
    http_only_operation_ids = known.get("http_only_operation_ids", set())
    for operation_id in sorted(binding_operation_ids - known["operation_ids"]):
        lint.fail(binding_path, f"non-HTTP binding references unregistered operation_id: {operation_id}")
    for operation_id in sorted(binding_operation_ids & http_only_operation_ids):
        lint.fail(binding_path, f"http-only operation_id must not appear in non-HTTP bindings: {operation_id}")
    for operation_id in sorted(known["operation_ids"] - binding_operation_ids - http_only_operation_ids):
        lint.fail(binding_path, f"registered operation_id missing from non-HTTP bindings: {operation_id}")



def check_service_describe_alignment(lint: Lint) -> None:
    openapi_path = ARTIFACTS / "openapi" / "arkret-service-api.openapi.yaml"
    schema_path = ARTIFACTS / "schemas" / "service-describe.schema.json"
    openapi = load_yaml(lint, openapi_path)
    service_schema = load_json(lint, schema_path)
    if not isinstance(openapi, dict) or not isinstance(service_schema, dict):
        return

    component = (
        openapi.get("components", {})
        .get("schemas", {})
        .get("ServiceDescribe")
    )
    if not isinstance(component, dict):
        lint.fail(openapi_path, "components.schemas.ServiceDescribe missing")
        return

    openapi_required = set(component.get("required") or [])
    schema_required = set(service_schema.get("required") or [])
    for required_field in ("service_id", "trust_domain"):
        if required_field not in schema_required:
            lint.fail(schema_path, f"ServiceDescribe.required must include {required_field}")
        if required_field not in openapi_required:
            lint.fail(openapi_path, f"components.schemas.ServiceDescribe.required must include {required_field}")
    if "trust_domain" not in (service_schema.get("properties") or {}):
        lint.fail(schema_path, "ServiceDescribe.properties.trust_domain missing")
    if "trust_domain" not in (component.get("properties") or {}):
        lint.fail(openapi_path, "components.schemas.ServiceDescribe.properties.trust_domain missing")
    directory_fields = {
        "resource_kinds",
        "discovery_profiles",
        "restricted_query_proof",
        "ingest_modes",
        "accept_policy_kind",
        "accept_policy_ref",
        "default_ttl_seconds",
        "max_ttl_seconds",
        "revalidation_grace_seconds",
        "accepted_resource_kinds",
        "accepted_did_methods",
        "takedown_contact",
        "rate_limits",
    }
    schema_properties = service_schema.get("properties") or {}
    openapi_properties = component.get("properties") or {}
    for field in sorted(directory_fields):
        if field not in schema_properties:
            lint.fail(schema_path, f"ServiceDescribe.properties.{field} missing")
        if field not in openapi_properties:
            lint.fail(openapi_path, f"components.schemas.ServiceDescribe.properties.{field} missing")
    if openapi_required != schema_required:
        lint.fail(
            openapi_path,
            "ServiceDescribe.required differs from service-describe.schema.json: "
            f"openapi-only={sorted(openapi_required - schema_required)}, "
            f"schema-only={sorted(schema_required - openapi_required)}",
        )

    paths = openapi.get("paths")
    if not isinstance(paths, dict):
        return
    describe_bindings = [
        ("/_arkret/describe", "get"),
        ("/_arkret/self/events/describe", "query"),
        ("/_arkret/root/identity/describe", "get"),
        ("/_arkret/self/account/describe", "get"),
        ("/_arkret/find/directory/describe", "get"),
        ("/_arkret/edge/applet/describe", "get"),
    ]
    for describe_path, describe_method in describe_bindings:
        response_schema = (
            paths.get(describe_path, {})
            .get(describe_method, {})
            .get("responses", {})
            .get("200", {})
            .get("content", {})
            .get("application/json", {})
            .get("schema")
        )
        if response_schema != {"$ref": "#/components/schemas/ServiceDescribe"}:
            lint.fail(openapi_path, f"{describe_path} 200 response must reference ServiceDescribe")



def check_policy_check_alignment(lint: Lint) -> None:
    openapi_path = ARTIFACTS / "openapi" / "arkret-service-api.openapi.yaml"
    openapi = load_yaml(lint, openapi_path)
    if not isinstance(openapi, dict):
        return
    paths = openapi.get("paths")
    components = openapi.get("components", {}).get("schemas", {})
    if not isinstance(paths, dict) or not isinstance(components, dict):
        return
    if "/arkret/v1/check" in paths:
        lint.fail(openapi_path, "legacy /arkret/v1/check policy path must not be present; use /_arkret/self/policy/check")

    policy_path = paths.get("/_arkret/self/policy/check", {}).get("post", {})
    request_schema = (
        policy_path.get("requestBody", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema")
    )
    response_schema = (
        policy_path.get("responses", {})
        .get("200", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema")
    )
    if request_schema != {"$ref": "#/components/schemas/PolicyCheckRequestBody"}:
        lint.fail(openapi_path, "/_arkret/self/policy/check requestBody must reference PolicyCheckRequestBody")
    if response_schema != {"$ref": "#/components/schemas/PolicyCheckOutcome"}:
        lint.fail(openapi_path, "/_arkret/self/policy/check 200 response must reference PolicyCheckOutcome")

    request_component = resolve_openapi_component_schema(lint, openapi_path, components, "PolicyCheckRequestBody")
    response_component = resolve_openapi_component_schema(lint, openapi_path, components, "PolicyCheckOutcome")
    if not isinstance(request_component, dict):
        lint.fail(openapi_path, "components.schemas.PolicyCheckRequestBody missing")
    elif "realm_id" not in set(request_component.get("required") or []):
        lint.fail(openapi_path, "PolicyCheckRequestBody.required must include realm_id")
    if not isinstance(response_component, dict):
        lint.fail(openapi_path, "components.schemas.PolicyCheckOutcome missing")
    elif "bound_to" not in set(response_component.get("required") or []):
        lint.fail(openapi_path, "PolicyCheckOutcome.required must include bound_to")



def openapi_operations_by_id(openapi: dict[str, Any]) -> dict[str, dict[str, Any]]:
    paths = openapi.get("paths")
    if not isinstance(paths, dict):
        return {}
    operations: dict[str, dict[str, Any]] = {}
    for path_item in paths.values():
        if not isinstance(path_item, dict):
            continue
        for method in ("get", "post", "put", "patch", "delete", "head", "query"):
            operation = path_item.get(method)
            if not isinstance(operation, dict):
                continue
            operation_id = operation.get("operationId")
            if isinstance(operation_id, str) and operation_id:
                operations[operation_id] = operation
    return operations



def openapi_parameter_schema(operation: dict[str, Any], name: str) -> Any:
    for parameter in operation.get("parameters", []) or []:
        if isinstance(parameter, dict) and parameter.get("name") == name:
            return parameter.get("schema")
    return None



def check_openapi_dedicated_operation_schemas(lint: Lint) -> None:
    """Prevent security-sensitive operations from drifting back to generic schemas."""
    openapi_path = ARTIFACTS / "openapi" / "arkret-service-api.openapi.yaml"
    openapi = load_yaml(lint, openapi_path)
    if not isinstance(openapi, dict):
        return

    paths = openapi.get("paths")
    components = openapi.get("components", {}).get("schemas", {})
    if not isinstance(paths, dict) or not isinstance(components, dict):
        return

    def find_operation(operation_id: str) -> dict[str, Any] | None:
        for path_item in paths.values():
            if not isinstance(path_item, dict):
                continue
            for method in ("get", "post", "put", "patch", "delete", "head", "query"):
                operation = path_item.get(method)
                if isinstance(operation, dict) and operation.get("operationId") == operation_id:
                    return operation
        return None

    def request_schema(operation: dict[str, Any]) -> Any:
        return (
            operation.get("requestBody", {})
            .get("content", {})
            .get("application/json", {})
            .get("schema")
        )

    def response_schema(operation: dict[str, Any]) -> Any:
        return (
            operation.get("responses", {})
            .get("200", {})
            .get("content", {})
            .get("application/json", {})
            .get("schema")
        )

    expected = {
        "ak.root.identity.command.submit_did_operation": ("DidOperationSubmitRequestBody", "DidOperationSubmitOutcome"),
        "ak.gate.account.command.issue_session_grant": ("SessionGrantRequestBody", "SessionGrantOutcome"),
        "ak.find.directory.command.announce": ("DirectoryAnnounceRequestBody", "DirectoryAnnounceOutcome"),
        "ak.find.directory.command.withdraw": ("DirectoryWithdrawRequestBody", "DirectoryWithdrawOutcome"),
    }
    expected_response_only = {}
    dedicated_schema_refs = {
        f"#/components/schemas/{name}"
        for pair in expected.values()
        for name in pair
    } | {f"#/components/schemas/{name}" for name in expected_response_only.values()}
    for operation_id, (request_name, response_name) in expected.items():
        operation = find_operation(operation_id)
        if operation is None:
            lint.fail(openapi_path, f"{operation_id} operation missing")
            continue
        if request_schema(operation) != {"$ref": f"#/components/schemas/{request_name}"}:
            lint.fail(openapi_path, f"{operation_id} requestBody must reference {request_name}")
        if response_schema(operation) != {"$ref": f"#/components/schemas/{response_name}"}:
            lint.fail(openapi_path, f"{operation_id} 200 response must reference {response_name}")

    for operation_id, response_name in expected_response_only.items():
        operation = find_operation(operation_id)
        if operation is None:
            lint.fail(openapi_path, f"{operation_id} operation missing")
            continue
        if request_schema(operation) is not None:
            lint.fail(openapi_path, f"{operation_id} must not define a JSON requestBody")
        if response_schema(operation) != {"$ref": f"#/components/schemas/{response_name}"}:
            lint.fail(openapi_path, f"{operation_id} 200 response must reference {response_name}")

    for path_item in paths.values():
        if not isinstance(path_item, dict):
            continue
        for method in ("get", "post", "put", "patch", "delete", "head", "query"):
            operation = path_item.get(method)
            if not isinstance(operation, dict):
                continue
            operation_id = operation.get("operationId")
            if operation_id in expected or operation_id in expected_response_only:
                continue
            for label, schema in (("requestBody", request_schema(operation)), ("200 response", response_schema(operation))):
                if isinstance(schema, dict) and schema.get("$ref") in dedicated_schema_refs:
                    lint.fail(
                        openapi_path,
                        f"{operation_id} {label} must not reference account/DID dedicated schema {schema.get('$ref')}",
                    )

    human_session_grant_required = set(
        (resolve_openapi_component_schema(lint, openapi_path, components, "HumanSessionGrantRequest") or {})
        .get("required", [])
    )
    if not {"audience", "accepted_device_possession_proof"}.issubset(human_session_grant_required):
        lint.fail(
            openapi_path,
            "HumanSessionGrantRequest.required must include audience and accepted_device_possession_proof",
        )
    agent_session_grant_proof_required = set(
        (resolve_openapi_component_schema(lint, openapi_path, components, "AgentSessionGrantRequest") or {})
        .get("properties", {})
        .get("proof", {})
        .get("required", [])
    )
    if "audience" not in agent_session_grant_proof_required:
        lint.fail(openapi_path, "AgentSessionGrantRequest.proof.required must include audience")

    projection_components = {
        "ak.self.space.read.list": "ProjectionSpaceList",
        "ak.self.strand.read.list": "ProjectionStrandList",
        "ak.self.morph.read.list": "ProjectionMorphList",
    }
    for operation_id, component_name in projection_components.items():
        operation = find_operation(operation_id)
        if operation is None:
            lint.fail(openapi_path, f"{operation_id} operation missing")
            continue
        parameter_names = {
            parameter.get("name")
            for parameter in operation.get("parameters", [])
            if isinstance(parameter, dict)
        }
        for required_parameter in ("cursor", "limit"):
            if required_parameter not in parameter_names:
                lint.fail(openapi_path, f"{operation_id} parameters must include {required_parameter}")
        component = resolve_openapi_component_schema(lint, openapi_path, components, component_name) or {}
        required = set(component.get("required") or [])
        properties = component.get("properties") or {}
        if "has_more" not in required:
            lint.fail(openapi_path, f"{component_name}.required must include has_more")
        if "next_cursor" not in properties:
            lint.fail(openapi_path, f"{component_name}.properties must include next_cursor")



def check_openapi_core_selector_constraints(lint: Lint) -> None:
    """Core event read operations must machine-declare selector and typed-id rules."""
    openapi_path = ARTIFACTS / "openapi" / "arkret-service-api.openapi.yaml"
    openapi = load_yaml(lint, openapi_path)
    if not isinstance(openapi, dict):
        return
    operations = openapi_operations_by_id(openapi)

    def op(operation_id: str) -> dict[str, Any] | None:
        operation = operations.get(operation_id)
        if not isinstance(operation, dict):
            lint.fail(openapi_path, f"{operation_id} operation missing")
            return None
        return operation

    def expect_any_of(operation_id: str, expected: list[list[str]]) -> None:
        operation = op(operation_id)
        if operation is None:
            return
        actual = operation.get("x-arkret-required-any-of")
        if actual != expected:
            lint.fail(openapi_path, f"{operation_id} x-arkret-required-any-of must be {expected!r}")

    def expect_array_param(operation_id: str, name: str, ref: str) -> None:
        operation = op(operation_id)
        if operation is None:
            return
        schema = openapi_parameter_schema(operation, name)
        if not isinstance(schema, dict):
            lint.fail(openapi_path, f"{operation_id}.{name} parameter schema missing")
            return
        if schema.get("type") != "array":
            lint.fail(openapi_path, f"{operation_id}.{name} must be an array parameter")
        if schema.get("minItems") != 1:
            lint.fail(openapi_path, f"{operation_id}.{name} must require minItems=1")
        items = schema.get("items")
        if not isinstance(items, dict) or items.get("$ref") != ref:
            lint.fail(openapi_path, f"{operation_id}.{name}.items must reference {ref}")

    def expect_param_ref(operation_id: str, name: str, ref: str) -> None:
        operation = op(operation_id)
        if operation is None:
            return
        schema = openapi_parameter_schema(operation, name)
        if not isinstance(schema, dict) or schema.get("$ref") != ref:
            lint.fail(openapi_path, f"{operation_id}.{name} parameter must reference {ref}")

    expect_any_of("ak.self.events.stream.subscribe", [["realms"], ["actors"]])
    expect_array_param("ak.self.events.stream.subscribe", "realms", "#/components/schemas/RealmId")
    expect_array_param(
        "ak.self.events.stream.subscribe",
        "actors",
        "../schemas/common-ids.schema.json#/$defs/did_core_id",
    )
    expect_param_ref("ak.self.events.stream.subscribe", "after", "#/components/schemas/Cursor")
    expect_param_ref("ak.self.events.resource.get", "event_id", "#/components/schemas/EventId")
    expect_param_ref("ak.self.snapshot.read.manifest_head", "realm_id", "#/components/schemas/RealmId")

    query_body = op("ak.self.events.read.scan")
    if query_body is not None:
        schema = resolve_openapi_schema_node(lint, openapi_path, openapi.get("components", {}).get("schemas", {}), openapi_request_schema(query_body))
        if not isinstance(schema, dict):
            lint.fail(openapi_path, "ak.self.events.read.scan requestBody schema missing")
        else:
            expected_any_of = [{"required": ["realms"]}, {"required": ["actors"]}]
            if schema.get("anyOf") != expected_any_of:
                lint.fail(openapi_path, "ak.self.events.read.scan requestBody must require realms or actors")
            properties = schema.get("properties")
            if not isinstance(properties, dict):
                lint.fail(openapi_path, "ak.self.events.read.scan requestBody properties missing")
            else:
                for name, ref in (
                    ("realms", "#/components/schemas/RealmId"),
                    ("actors", "../schemas/common-ids.schema.json#/$defs/did_core_id"),
                ):
                    property_schema = properties.get(name)
                    if not isinstance(property_schema, dict):
                        lint.fail(openapi_path, f"ak.self.events.read.scan.{name} property missing")
                        continue
                    if property_schema.get("type") != "array" or property_schema.get("minItems") != 1:
                        lint.fail(openapi_path, f"ak.self.events.read.scan.{name} must be a non-empty array")
                    items = property_schema.get("items")
                    if not isinstance(items, dict) or not (
                        items.get("$ref") == ref or schema_ref_targets(items, ref.rsplit("/", 1)[-1])
                    ):
                        lint.fail(openapi_path, f"ak.self.events.read.scan.{name}.items must reference {ref}")
                for name in ("before", "after"):
                    property_schema = properties.get(name)
                    if not schema_ref_targets(property_schema, "Cursor"):
                        lint.fail(openapi_path, f"ak.self.events.read.scan.{name} must reference Cursor")



def check_openapi_auth_semantics(lint: Lint) -> None:
    """Distinguish public metadata, proof-in-body auth, user tokens, and admin tokens."""
    openapi_path = ARTIFACTS / "openapi" / "arkret-service-api.openapi.yaml"
    openapi = load_yaml(lint, openapi_path)
    if not isinstance(openapi, dict):
        return
    operations = openapi_operations_by_id(openapi)
    public_metadata_operations = {
        "ak.server.read.describe",
        "ak.self.events.read.describe",
        "ak.peer.events.read.describe",
        "ak.open.mimi.read.provider_directory",
        "ak.root.identity.registry.read.describe",
        "ak.self.account.read.describe",
        "ak.open.identity.read.resolution",
        "ak.open.service.read.resolution",
        "ak.find.directory.read.describe",
        "ak.edge.applet.read.describe",
        "ak.edge.applet.read.protocol_metadata",
    }
    proof_in_body_operations = {
        "ak.gate.account.command.register",
        "ak.gate.account.command.issue_session_grant",
        "ak.open.invite_locator.read.resolve",
        "ak.open.agent_pairing.read.resolve",
        "ak.open.agent_pairing.command.submit_runtime_key_request",
        "ak.open.agent_pairing.read.runtime_key_request_status",
        "ak.open.device_pairing.command.stage",
        "ak.open.device_pairing.read.resolve",
        "ak.open.device_pairing.read.status",
    }

    for operation_id, operation in operations.items():
        security = operation.get("security")
        if security == []:
            auth = operation.get("x-arkret-auth")
            proof_in_body = (
                operation_id in proof_in_body_operations
                and isinstance(auth, dict)
                and auth.get("public_metadata") is False
                and auth.get("proof_in_body") is True
            )
            if operation_id not in public_metadata_operations and not proof_in_body:
                lint.fail(
                    openapi_path,
                    f"{operation_id} has security: [] but is neither public metadata nor proof-in-body auth",
                )

    for operation_id in proof_in_body_operations:
        operation = operations.get(operation_id)
        if not isinstance(operation, dict):
            lint.fail(openapi_path, f"{operation_id} operation missing")
            continue
        auth = operation.get("x-arkret-auth")
        if not isinstance(auth, dict) or auth.get("public_metadata") is not False or auth.get("proof_in_body") is not True:
            lint.fail(openapi_path, f"{operation_id} must declare x-arkret-auth proof_in_body/public_metadata=false")

    def security_groups(operation: dict[str, Any]) -> list[dict[str, Any]]:
        groups = operation.get("security")
        return [group for group in groups if isinstance(group, dict)] if isinstance(groups, list) else []

    for operation_id, operation in operations.items():
        if not operation_id.startswith("ak.admin."):
            continue
        lint.fail(openapi_path, f"{operation_id} is product-local and must not be registered in Arkret OpenAPI")



def check_binding_variant_non_http(lint: Lint) -> None:
    operation_path = ARTIFACTS / "registry" / "operation-registry.json"
    binding_path = ARTIFACTS / "bindings" / "non-http-bindings.yaml"
    registry = load_json(lint, operation_path)
    if not isinstance(registry, dict):
        return
    binding_text = binding_path.read_text(encoding="utf-8")
    binding_operation_ids = set(EVENT_KIND_TOKEN_RE.findall(binding_text))

    for row in registry.get("operations", []) if isinstance(registry.get("operations"), list) else []:
        if not isinstance(row, dict):
            continue
        operation_id = row.get("operation_id")
        if not isinstance(operation_id, str):
            continue
        if not row.get("binding_variant_of"):
            continue
        if row.get("shares_non_http_binding") is True:
            if not isinstance(row.get("notes"), str) or "non-HTTP" not in row.get("notes", ""):
                lint.fail(operation_path, f"{operation_id} shares_non_http_binding must explain non-HTTP exposure in notes")
            continue
        if row.get("http_only_variant") is not True:
            lint.fail(operation_path, f"{operation_id} binding_variant_of must declare http_only_variant=true")
        if row.get("grpc") is not None or row.get("mq") is not None:
            lint.fail(operation_path, f"{operation_id} http-only binding variant must not declare grpc/mq")
        if operation_id in binding_operation_ids:
            lint.fail(binding_path, f"{operation_id} http-only binding variant must not appear in non-HTTP bindings")



def check_openapi_error_enum_alignment(lint: Lint) -> None:
    """ErrorEnvelope.error.code must be generated from the canonical error registry."""
    registry_path = ARTIFACTS / "registry" / "error-code-registry.json"
    openapi_path = ARTIFACTS / "openapi" / "arkret-service-api.openapi.yaml"
    registry = load_json(lint, registry_path)
    openapi = load_yaml(lint, openapi_path)
    if not isinstance(registry, dict) or not isinstance(openapi, dict):
        return

    expected = [
        row.get("code")
        for row in registry.get("codes", [])
        if isinstance(row, dict) and row.get("scope") in {"both", "endpoint"}
    ]
    enum = (
        openapi.get("components", {})
        .get("schemas", {})
        .get("ErrorEnvelope", {})
        .get("properties", {})
        .get("error", {})
        .get("properties", {})
        .get("code", {})
        .get("enum")
    )
    if not isinstance(enum, list):
        lint.fail(openapi_path, "ErrorEnvelope.error.code.enum missing")
        return

    if enum != expected:
        missing = sorted(set(expected) - set(enum))
        extra = sorted(set(enum) - set(expected))
        order_note = "" if missing or extra else "; same values but registry order differs"
        lint.fail(
            openapi_path,
            "ErrorEnvelope.error.code.enum must match error-code-registry codes with "
            f"scope endpoint/both: missing={missing}, extra={extra}{order_note}",
        )



def infer_openapi_success_shape(method: str, content: Any) -> str:
    """Infer response shape from HTTP semantics instead of operation-name allowlists."""
    if method == "head":
        return "metadata_headers"
    if not isinstance(content, dict) or not content:
        return "empty_response"
    if "application/x-ndjson" in content:
        return "event_stream"
    if "application/octet-stream" in content:
        return "binary_stream"
    json_media = content.get("application/json")
    schema = json_media.get("schema") if isinstance(json_media, dict) else None
    if schema is None:
        return "empty_response"
    if isinstance(schema, dict):
        ref = schema.get("$ref")
        if ref == GENERIC_OPERATION_RESULT_REF:
            return "operation_result"
        if ref == "#/components/schemas/ServiceDescribe":
            return "service_describe"
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            return "typed_response"
        if isinstance(ref, str) and ref.startswith("../schemas/"):
            return "schema_resource"
        return "inline_response"
    return "empty_response"



def normalize_artifact_schema_ref(ref: str | None) -> str | None:
    if not isinstance(ref, str) or not ref:
        return None
    if ref.startswith("../schemas/"):
        return "schemas/" + ref.removeprefix("../schemas/")
    if ref.startswith("./schemas/"):
        return "schemas/" + ref.removeprefix("./schemas/")
    if ref.startswith("schemas/"):
        return ref
    return ref



def openapi_artifact_schema_ref(schema: Any, components: dict[str, Any]) -> str | None:
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
                return normalize_artifact_schema_ref(component_ref)
        return ref
    return normalize_artifact_schema_ref(ref)



def openapi_request_schema(operation: dict[str, Any]) -> Any:
    content = (
        operation.get("requestBody", {})
        .get("content", {})
    )
    if not isinstance(content, dict):
        return None
    for media_type in ("application/json", "multipart/form-data", "application/octet-stream"):
        schema = content.get(media_type, {}).get("schema") if isinstance(content.get(media_type), dict) else None
        if isinstance(schema, dict):
            return schema
    for media in content.values():
        schema = media.get("schema") if isinstance(media, dict) else None
        if isinstance(schema, dict):
            return schema
    return None



def check_artifact_schema_ref(lint: Lint, owner: Path, label: str, ref: Any) -> None:
    if not isinstance(ref, str) or not ref:
        lint.fail(owner, f"{label} must be a non-empty artifact schema ref")
        return
    file_ref, _, fragment = ref.partition("#")
    if not file_ref.startswith("schemas/"):
        lint.fail(owner, f"{label} must reference artifacts/schemas: {ref}")
        return
    target = ARTIFACTS / file_ref
    data = load_json(lint, target)
    if not isinstance(data, dict):
        return
    if fragment:
        current: Any = data
        for token in fragment.removeprefix("/").split("/"):
            token = token.replace("~1", "/").replace("~0", "~")
            if isinstance(current, dict) and token in current:
                current = current[token]
            else:
                lint.fail(owner, f"{label} fragment does not exist: {ref}")
                return



def collect_openapi_operation_facts(lint: Lint, openapi_path: Path) -> dict[str, dict[str, Any]]:
    openapi = load_yaml(lint, openapi_path)
    if not isinstance(openapi, dict):
        return {}
    paths = openapi.get("paths")
    if not isinstance(paths, dict):
        lint.fail(openapi_path, "OpenAPI paths missing")
        return {}
    components = openapi.get("components", {}).get("schemas", {})
    if not isinstance(components, dict):
        components = {}

    facts: dict[str, dict[str, Any]] = {}
    for path_item in paths.values():
        if not isinstance(path_item, dict):
            continue
        for method in ("get", "post", "put", "patch", "delete", "head", "query"):
            operation = path_item.get(method)
            if not isinstance(operation, dict):
                continue
            operation_id = operation.get("operationId")
            if not isinstance(operation_id, str) or not operation_id:
                continue
            request_schema = openapi_request_schema(operation)
            response_content = (
                operation.get("responses", {})
                .get("200", {})
                .get("content", {})
            )
            response_schema = (
                response_content.get("application/json", {}).get("schema")
                if isinstance(response_content, dict)
                and isinstance(response_content.get("application/json"), dict)
                else None
            )
            facts[operation_id] = {
                "generic_request": isinstance(request_schema, dict)
                and request_schema.get("$ref") == GENERIC_OPERATION_REQUEST_REF,
                "generic_response": isinstance(response_schema, dict)
                and response_schema.get("$ref") == GENERIC_OPERATION_RESULT_REF,
                "request_schema_ref": openapi_artifact_schema_ref(request_schema, components),
                "response_schema_ref": openapi_artifact_schema_ref(response_schema, components),
                "success_shape_kind": infer_openapi_success_shape(method, response_content),
            }
    return facts



def check_operation_binding_metadata(lint: Lint) -> None:
    """Operation registry must machine-declare success shape and governed generic bindings."""
    operation_path = ARTIFACTS / "registry" / "operation-registry.json"
    openapi_path = ARTIFACTS / "openapi" / "arkret-service-api.openapi.yaml"
    operation_registry = load_json(lint, operation_path)
    if not isinstance(operation_registry, dict):
        return

    allowed_success_shapes = set((operation_registry.get("success_shape_kind_definitions") or {}).keys())
    if not allowed_success_shapes:
        lint.fail(operation_path, "operation registry missing success_shape_kind_definitions")

    surface_class_by_operation: dict[str, str] = {}
    for group in operation_registry.get("surface_groups", []) if isinstance(operation_registry.get("surface_groups"), list) else []:
        if not isinstance(group, dict):
            continue
        surface_class = group.get("surface_class")
        for operation_id in group.get("operations", []) or []:
            if isinstance(operation_id, str) and isinstance(surface_class, str):
                surface_class_by_operation[operation_id] = surface_class

    openapi_facts = collect_openapi_operation_facts(lint, openapi_path)
    for row in operation_registry.get("operations", []) if isinstance(operation_registry.get("operations"), list) else []:
        if not isinstance(row, dict):
            continue
        operation_id = row.get("operation_id")
        if not isinstance(operation_id, str):
            continue
        facts = openapi_facts.get(operation_id)
        if facts is None:
            lint.fail(operation_path, f"{operation_id} missing from OpenAPI facts")
            continue

        success_shape_kind = row.get("success_shape_kind")
        if success_shape_kind not in allowed_success_shapes:
            lint.fail(operation_path, f"{operation_id} has invalid success_shape_kind {success_shape_kind!r}")
        elif success_shape_kind != facts["success_shape_kind"]:
            lint.fail(
                operation_path,
                f"{operation_id} success_shape_kind={success_shape_kind!r} "
                f"but OpenAPI implies {facts['success_shape_kind']!r}",
            )

        uses_generic = facts["generic_request"] or facts["generic_response"]
        generic_binding = row.get("generic_binding")
        for schema_field, fact_field in (
            ("request_schema_ref", "request_schema_ref"),
            ("response_schema_ref", "response_schema_ref"),
        ):
            if schema_field in row:
                expected_ref = row.get(schema_field)
                check_artifact_schema_ref(lint, operation_path, f"{operation_id}.{schema_field}", expected_ref)
                if facts.get(fact_field) != expected_ref:
                    lint.fail(
                        operation_path,
                        f"{operation_id} {schema_field}={expected_ref!r} "
                        f"but OpenAPI references {facts.get(fact_field)!r}",
                    )
        if uses_generic:
            if surface_class_by_operation.get(operation_id) == "core":
                lint.fail(
                    operation_path,
                    f"{operation_id} has surface_class=core and must not use generic OpenAPI bindings",
                )
            if not isinstance(generic_binding, dict):
                lint.fail(operation_path, f"{operation_id} uses OperationRequest/OperationResult and must declare generic_binding")
                continue
            if generic_binding.get("request") is not facts["generic_request"]:
                lint.fail(operation_path, f"{operation_id} generic_binding.request does not match OpenAPI")
            if generic_binding.get("response") is not facts["generic_response"]:
                lint.fail(operation_path, f"{operation_id} generic_binding.response does not match OpenAPI")
            if generic_binding.get("profile_gate") is not True:
                lint.fail(operation_path, f"{operation_id} generic_binding.profile_gate must be true")
            for field in ("reason", "migration_plan", "surface"):
                if not isinstance(generic_binding.get(field), str) or not generic_binding.get(field):
                    lint.fail(operation_path, f"{operation_id} generic_binding.{field} must be a non-empty string")
        elif generic_binding is not None:
            lint.fail(operation_path, f"{operation_id} declares generic_binding but OpenAPI uses dedicated schemas")



def check_binding_completeness_index(lint: Lint) -> None:
    catalog_path = ARTIFACTS / "registry" / "contract-registry.json"
    binding_path = SPEC_ROOT / "zh" / "sync" / "service-http-binding.md"
    catalog = load_json(lint, catalog_path)
    if not isinstance(catalog, dict):
        return
    operation_registry = catalog.get("operation_registry")
    if not isinstance(operation_registry, dict):
        lint.fail(catalog_path, "operation_registry missing")
        return
    try:
        text = binding_path.read_text(encoding="utf-8")
    except Exception as exc:
        lint.fail(binding_path, f"unable to read binding completeness index: {exc}")
        return
    if "#### 2.4.1 Binding completeness index" not in text:
        lint.fail(binding_path, "missing §2.4.1 Binding completeness index")
        return
    section = text.split("#### 2.4.1 Binding completeness index", 1)[1].split("\n#### ", 1)[0]
    listed = {
        match.group(1)
        for match in re.finditer(r"^\|\s*`([^`]+)`\s*\|\s*`migration_required`\s*\|", section, re.MULTILINE)
    }
    expected_migration: set[str] = set()
    for row in operation_registry.get("operations", []) if isinstance(operation_registry.get("operations"), list) else []:
        if not isinstance(row, dict):
            continue
        generic_binding = row.get("generic_binding")
        if not isinstance(generic_binding, dict) or not generic_binding.get("migration_plan"):
            continue
        operation_id = row.get("operation_id")
        if not isinstance(operation_id, str):
            continue
        expected_migration.add(operation_id)
        expected = f"| `{operation_id}` | `migration_required` |"
        if expected not in text:
            lint.fail(
                binding_path,
                f"generic operation {operation_id} with migration_plan must be listed "
                "in Binding completeness index as migration_required",
            )
    stale = sorted(listed - expected_migration)
    if stale:
        lint.fail(
            binding_path,
            "Binding completeness index lists non-generic operation(s) as migration_required: "
            + ", ".join(stale),
        )



def schema_ref_mentioned_in_field_constraints(constraints: str, schema_ref: str) -> bool:
    if schema_ref in constraints:
        return True
    file_ref, _, fragment = schema_ref.partition("#")
    return bool(fragment and file_ref in constraints and f"#{fragment}" in constraints)



def collect_operation_field_table_constraints(text: str) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in text.splitlines():
        if not line.startswith("| `ak."):
            continue
        cells = [cell.strip() for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        if len(cells) != 5:
            continue
        operation_id = cells[0].strip("`")
        if operation_id.startswith("ak."):
            rows[operation_id] = cells[4]
    return rows



def check_operation_field_table_schema_refs(lint: Lint) -> None:
    """Operation field table rows must mention registry-declared schema refs."""
    catalog_path = ARTIFACTS / "registry" / "contract-registry.json"
    binding_path = SPEC_ROOT / "zh" / "sync" / "service-http-binding.md"
    catalog = load_json(lint, catalog_path)
    if not isinstance(catalog, dict):
        return
    operation_registry = catalog.get("operation_registry")
    if not isinstance(operation_registry, dict):
        lint.fail(catalog_path, "operation_registry missing")
        return
    try:
        text = binding_path.read_text(encoding="utf-8")
    except Exception as exc:
        lint.fail(binding_path, f"unable to read operation field table: {exc}")
        return
    field_rows = collect_operation_field_table_constraints(text)
    for row in operation_registry.get("operations", []) if isinstance(operation_registry.get("operations"), list) else []:
        if not isinstance(row, dict):
            continue
        operation_id = row.get("operation_id")
        if not isinstance(operation_id, str):
            continue
        refs = [
            ref
            for ref in (row.get("request_schema_ref"), row.get("response_schema_ref"))
            if isinstance(ref, str) and ref
        ]
        if not refs:
            continue
        constraints = field_rows.get(operation_id)
        if constraints is None:
            lint.fail(binding_path, f"{operation_id} declares schema refs but is missing from the operation field table")
            continue
        for schema_ref in refs:
            if not schema_ref_mentioned_in_field_constraints(constraints, schema_ref):
                lint.fail(
                    binding_path,
                    f"{operation_id} field table constraints must mention schema_ref {schema_ref}",
                )



def check_capability_action_event_mapping(lint: Lint) -> None:
    """Machine-check allowed action ↔ event-kind mapping deviations."""
    action_path = ARTIFACTS / "registry" / "capability-action-registry.json"
    action_registry = load_json(lint, action_path)
    if not isinstance(action_registry, dict):
        return

    allowed = set((action_registry.get("event_mapping_kind_definitions") or {}).keys())
    if not allowed:
        lint.fail(action_path, "capability action registry missing event_mapping_kind_definitions")
    for row in action_registry.get("actions", []) if isinstance(action_registry.get("actions"), list) else []:
        if not isinstance(row, dict):
            continue
        action = row.get("action")
        targets = row.get("target_event_kinds") or []
        mapping_kind = row.get("event_mapping_kind")
        if not isinstance(action, str):
            continue
        if mapping_kind not in allowed:
            lint.fail(action_path, f"{action} has invalid event_mapping_kind {mapping_kind!r}")
            continue
        if not targets and mapping_kind != "non_event_surface":
            lint.fail(action_path, f"{action} has no target_event_kinds and must use event_mapping_kind=non_event_surface")
        elif targets == [action] and mapping_kind != "same_name":
            lint.fail(action_path, f"{action} maps to the same event kind and must use event_mapping_kind=same_name")
        elif targets and targets != [action] and mapping_kind in {"same_name", "non_event_surface"}:
            lint.fail(action_path, f"{action} deviates from target_event_kinds and must declare an explicit deviation kind")



def check_event_admission_coverage(lint: Lint) -> None:
    """Every active durable reducer-input event MUST have a machine-readable admission source."""
    event_path = ARTIFACTS / "registry" / "event-kind-registry.json"
    action_path = ARTIFACTS / "registry" / "capability-action-registry.json"
    event_registry = load_json(lint, event_path)
    action_registry = load_json(lint, action_path)
    if not isinstance(event_registry, dict) or not isinstance(action_registry, dict):
        return
    allowed_classes = set((event_registry.get("admission_class_definitions") or {}).keys())
    if not allowed_classes:
        lint.fail(event_path, "event registry missing admission_class_definitions")
    predicate_contract = event_registry.get("admission_predicate_contract")
    if not isinstance(predicate_contract, dict) or predicate_contract.get("closed_world") is not True:
        lint.fail(event_path, "event registry missing closed-world admission_predicate_contract")
    actions = action_registry.get("actions", [])
    action_names = {a.get("action") for a in actions if isinstance(a, dict)}
    covered: set[str] = set()
    for a in actions:
        if isinstance(a, dict):
            for target in (a.get("target_event_kinds") or []):
                covered.add(target)
    for event in event_registry.get("event_kinds", []):
        if not isinstance(event, dict):
            continue
        if event.get("status") != "active" or event.get("wire_scope") != "durable_event" or not event.get("reducer_input"):
            continue
        kind = event.get("event_kind")
        admission = event.get("admission")
        if kind not in covered and not admission:
            lint.fail(event_path, f"{kind}: active durable reducer-input event has no admission source (no capability action coverage and no admission class)")
            continue
        if admission is not None:
            if admission not in allowed_classes:
                lint.fail(event_path, f"{kind}: invalid admission class {admission!r}")
            if admission == "conditional":
                variants = event.get("admission_variants")
                if not isinstance(variants, list) or len(variants) < 2:
                    lint.fail(event_path, f"{kind}: admission=conditional MUST list at least two admission_variants")
                else:
                    otherwise_count = 0
                    seen_predicates: set[str] = set()
                    for index, variant in enumerate(variants):
                        if not isinstance(variant, dict):
                            lint.fail(event_path, f"{kind}: admission_variants[{index}] MUST be an object")
                            continue
                        unknown_variant_keys = set(variant) - {"when", "admission"}
                        if unknown_variant_keys:
                            lint.fail(event_path, f"{kind}: admission_variants[{index}] has unknown keys {sorted(unknown_variant_keys)!r}")
                        when = variant.get("when")
                        variant_admission = variant.get("admission")
                        if not isinstance(when, dict):
                            lint.fail(event_path, f"{kind}: admission_variants[{index}].when MUST be an object")
                        elif when.get("otherwise") is True:
                            otherwise_count += 1
                            if index != len(variants) - 1 or len(when) != 1:
                                lint.fail(event_path, f"{kind}: conditional otherwise MUST be the final predicate and contain no other selectors")
                        else:
                            allowed_selectors = {"payload_path", "const", "not_const", "ref_role", "ref_critical", "ref_exact_count", "top_level_fields_present"}
                            unknown_selectors = set(when) - allowed_selectors
                            if unknown_selectors:
                                lint.fail(event_path, f"{kind}: admission_variants[{index}].when has unknown selectors {sorted(unknown_selectors)!r}")
                            if not when:
                                lint.fail(event_path, f"{kind}: admission_variants[{index}].when MUST contain a selector")
                            payload_path = when.get("payload_path")
                            if "payload_path" in when:
                                if not isinstance(payload_path, str) or re.fullmatch(r"[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*", payload_path) is None:
                                    lint.fail(event_path, f"{kind}: admission_variants[{index}].when.payload_path is invalid")
                                comparison_selectors = {selector for selector in ("const", "not_const") if selector in when}
                                if len(comparison_selectors) != 1:
                                    lint.fail(event_path, f"{kind}: admission_variants[{index}].when.payload_path requires exactly one of const/not_const")
                            elif "const" in when or "not_const" in when:
                                lint.fail(event_path, f"{kind}: admission_variants[{index}] const/not_const requires payload_path")
                            for selector in ("const", "not_const"):
                                if selector in when and not (when[selector] is None or isinstance(when[selector], (str, int, bool))):
                                    lint.fail(event_path, f"{kind}: admission_variants[{index}].when.{selector} MUST be a JSON scalar")
                            ref_role = when.get("ref_role")
                            if "ref_role" in when and (not isinstance(ref_role, str) or re.fullmatch(r"[a-z][a-z0-9_]*", ref_role) is None):
                                lint.fail(event_path, f"{kind}: admission_variants[{index}].when.ref_role is invalid")
                            for selector in ("ref_critical", "ref_exact_count"):
                                if selector in when and "ref_role" not in when:
                                    lint.fail(event_path, f"{kind}: admission_variants[{index}].when.{selector} requires ref_role")
                            if "ref_critical" in when and not isinstance(when["ref_critical"], bool):
                                lint.fail(event_path, f"{kind}: admission_variants[{index}].when.ref_critical MUST be boolean")
                            if "ref_exact_count" in when and (not isinstance(when["ref_exact_count"], int) or isinstance(when["ref_exact_count"], bool) or when["ref_exact_count"] < 0):
                                lint.fail(event_path, f"{kind}: admission_variants[{index}].when.ref_exact_count MUST be a non-negative integer")
                            if "top_level_fields_present" in when:
                                fields = when["top_level_fields_present"]
                                allowed_fields = {"executed_by", "authorization_ref"}
                                if not isinstance(fields, list) or not fields or len(fields) != len(set(fields)) or any(field not in allowed_fields for field in fields):
                                    lint.fail(event_path, f"{kind}: admission_variants[{index}].when.top_level_fields_present MUST be a non-empty unique subset of {sorted(allowed_fields)!r}")
                            predicate_key = json.dumps(when, sort_keys=True, separators=(",", ":"))
                            if predicate_key in seen_predicates:
                                lint.fail(event_path, f"{kind}: admission_variants[{index}].when duplicates an earlier predicate")
                            seen_predicates.add(predicate_key)
                        if variant_admission not in allowed_classes - {"conditional"}:
                            lint.fail(event_path, f"{kind}: admission_variants[{index}] has invalid admission {variant_admission!r}")
                        if variant_admission == "capability_gated" and kind not in covered:
                            lint.fail(
                                event_path,
                                f"{kind}: capability_gated admission variant but no action's "
                                "target_event_kinds lists this kind - admission has a single "
                                "direction of truth",
                            )
                    if otherwise_count != 1:
                        lint.fail(event_path, f"{kind}: admission=conditional MUST contain exactly one final otherwise variant")
            elif admission == "capability_gated":
                if kind not in covered:
                    lint.fail(
                        event_path,
                        f"{kind}: admission=capability_gated but no action's target_event_kinds "
                        "lists this kind - admission has a single direction of truth",
                    )
            if "admission_capabilities" in event or (
                isinstance(event.get("admission_variants"), list)
                and any(
                    isinstance(variant, dict) and "admission_capabilities" in variant
                    for variant in event["admission_variants"]
                )
            ):
                lint.fail(
                    event_path,
                    f"{kind}: admission_capabilities is retired; the authorizing actions are "
                    "exactly the ones whose target_event_kinds list the kind",
                )



def _resolve_dto_object(schema_ref: str) -> dict | None:
    """Resolve a 'schemas/X.schema.json#/$defs/Y' ref to its object, following pure $ref aliases."""
    file_ref, _, fragment = (schema_ref or "").partition("#")
    if not file_ref:
        return None
    path = ARTIFACTS / file_ref

    def load(p: Path):
        try:
            return parse_json_file(p.resolve())
        except Exception:
            return None

    def navigate(doc, frag):
        node = doc
        for token in [t for t in frag.split("/") if t]:
            token = token.replace("~1", "/").replace("~0", "~")
            if isinstance(node, dict) and token in node:
                node = node[token]
            else:
                return None
        return node

    document = load(path)
    if document is None:
        return None
    node = navigate(document, fragment.lstrip("#")) if fragment else document
    seen: set[str] = set()
    while isinstance(node, dict) and set(node.keys()) == {"$ref"}:
        ref = node["$ref"]
        if ref in seen:
            break
        seen.add(ref)
        ref_file, _, ref_fragment = ref.partition("#")
        if ref_file:
            path = (path.parent / ref_file).resolve()
            document = load(path)
            if document is None:
                return None
        node = navigate(document, ref_fragment.lstrip("#")) if ref_fragment else document
    return node if isinstance(node, dict) else None



def check_operation_dto_closure(lint: Lint) -> None:
    """Core operation DTOs (request/response object schemas) MUST be closed.

    Every operation request/response schema that resolves to a ``type: object``
    MUST declare ``additionalProperties: false`` unless the object is explicitly
    marked as an intentional extension surface via ``x_extension_surface: true``
    or a non-empty ``$comment`` (models/common-fields.md DTO-closure policy).
    Reads the generated operation-schema-index (already verified current).
    """
    index_path = ARTIFACTS / "reports" / "operation-schema-index.json"
    index = load_json(lint, index_path)
    if not isinstance(index, dict):
        return
    def summaries(dto: dict[str, Any]):
        yield dto
        for variant in dto.get("variants", []):
            if isinstance(variant, dict):
                yield from summaries(variant)

    for operation in index.get("operations", []):
        if not isinstance(operation, dict):
            continue
        operation_id = operation.get("operation_id")
        for role in ("request", "response"):
            dto = operation.get(role)
            if not isinstance(dto, dict):
                continue
            for summary in summaries(dto):
                if summary.get("schema_kind") != "object" or summary.get("closed") is True:
                    continue
                schema_ref = summary.get("schema_ref") or ""
                source = _resolve_dto_object(schema_ref)
                marked = isinstance(source, dict) and (
                    source.get("x_extension_surface") is True or bool(source.get("$comment"))
                )
                if not marked:
                    lint.fail(
                        index_path,
                        f"{operation_id} {role} DTO is not closed: {schema_ref} "
                        "MUST close every object/oneOf variant or be marked open (x_extension_surface / $comment)",
                    )



def _supply_collect_supply(
    schema_files: dict[str, Any],
    file: str,
    node: Any,
    visiting: frozenset,
    defs_out: set,
    names_out: set,
) -> None:
    if not isinstance(node, dict):
        return
    if "$ref" in node:
        resolved = _supply_resolve_ref(schema_files, file, node["$ref"])
        if resolved is None:
            return
        rfile, rdef, rnode = resolved
        key = (rfile, rdef)
        if key in visiting:
            return
        defs_out.add(key)
        _supply_collect_supply(
            schema_files, rfile, rnode, visiting | {key}, defs_out, names_out
        )
        return
    for comb in ("oneOf", "anyOf", "allOf"):
        for branch in node.get(comb) or []:
            _supply_collect_supply(
                schema_files, file, branch, visiting, defs_out, names_out
            )
    items = node.get("items")
    if isinstance(items, dict):
        _supply_collect_supply(schema_files, file, items, visiting, defs_out, names_out)
    props = node.get("properties")
    if isinstance(props, dict):
        for prop_name, sub in props.items():
            names_out.add(prop_name)
            _supply_collect_supply(schema_files, file, sub, visiting, defs_out, names_out)



def _supply_is_untyped_object(node: Any) -> bool:
    if not isinstance(node, dict):
        return False
    if node.get("additionalProperties") is not True:
        return False
    for shaping in ("properties", "patternProperties", "oneOf", "anyOf", "allOf", "$ref"):
        if shaping in node:
            return False
    return node.get("type") in (None, "object")



def _supply_walk_demand(
    schema_files: dict[str, Any],
    file: str,
    node: Any,
    path: str,
    visiting: frozenset,
    out: list,
    chain_required: bool,
    supplied_defs: set,
    covered: bool,
    caller_signed: bool = False,
) -> None:
    if not isinstance(node, dict):
        return
    if "$ref" in node:
        resolved = _supply_resolve_ref(schema_files, file, node["$ref"])
        if resolved is None:
            return
        rfile, rdef, rnode = resolved
        key = (rfile, rdef)
        if key in visiting:
            return
        _supply_walk_demand(
            schema_files,
            rfile,
            rnode,
            path,
            visiting | {key},
            out,
            chain_required,
            supplied_defs,
            covered or key in supplied_defs,
            caller_signed
            or rdef in _SUPPLY_CALLER_SIGNED_SCHEMAS
            or rfile in _SUPPLY_CALLER_SIGNED_SCHEMAS,
        )
        return
    for comb in ("oneOf", "anyOf", "allOf"):
        for branch in node.get(comb) or []:
            _supply_walk_demand(
                schema_files,
                file,
                branch,
                path,
                visiting,
                out,
                chain_required,
                supplied_defs,
                covered,
                caller_signed,
            )
    items = node.get("items")
    if isinstance(items, dict):
        _supply_walk_demand(
            schema_files,
            file,
            items,
            path + "[]",
            visiting,
            out,
            chain_required,
            supplied_defs,
            covered,
            caller_signed,
        )
    props = node.get("properties")
    if not isinstance(props, dict):
        return
    required = set(node.get("required") or [])
    sibling_names = set(props.keys())
    has_schema_identity_sibling = any(
        isinstance(sub, dict)
        and isinstance(sub.get("const"), str)
        and ".schema.json#/" in sub["const"]
        for sub in props.values()
    )
    has_canonical_bytes_sibling = "canonical_bytes_base64url" in sibling_names
    for prop_name, sub in props.items():
        is_required = prop_name in required
        field_path = f"{path}.{prop_name}" if path else prop_name
        ref_def = ""
        ref_file = ""
        ref_supplied = False
        resolved_sub = sub
        resolved_file = file
        if isinstance(sub, dict) and "$ref" in sub:
            resolved = _supply_resolve_ref(schema_files, file, sub["$ref"])
            if resolved is not None:
                ref_def = resolved[1]
                ref_file = resolved[0]
                ref_supplied = (resolved[0], resolved[1]) in supplied_defs
                resolved_file = resolved[0]
                resolved_sub = resolved[2]
        field_caller_signed = (
            caller_signed
            or ref_def in _SUPPLY_CALLER_SIGNED_SCHEMAS
            or ref_file in _SUPPLY_CALLER_SIGNED_SCHEMAS
        )
        resolved_union_branches: list[tuple[str, dict[str, Any], frozenset]] = []
        if isinstance(resolved_sub, dict):
            for branch in resolved_sub.get("oneOf") or []:
                branch_file = resolved_file
                branch_node = branch
                branch_visiting = visiting
                if isinstance(branch_node, dict) and "$ref" in branch_node:
                    resolved_branch = _supply_resolve_ref(
                        schema_files, branch_file, branch_node["$ref"]
                    )
                    if resolved_branch is None:
                        resolved_union_branches = []
                        break
                    branch_file, branch_def, branch_node = resolved_branch
                    branch_key = (branch_file, branch_def)
                    if branch_key in branch_visiting:
                        resolved_union_branches = []
                        break
                    branch_visiting = branch_visiting | {branch_key}
                if not (
                    isinstance(branch_node, dict)
                    and isinstance(branch_node.get("properties"), dict)
                ):
                    resolved_union_branches = []
                    break
                resolved_union_branches.append(
                    (branch_file, branch_node, branch_visiting)
                )
        is_union = bool(resolved_union_branches) and len(resolved_union_branches) == len(
            resolved_sub.get("oneOf") or []
        )
        if is_required and chain_required and is_union and not (covered or ref_supplied):
            # A required union is constructible when at least one branch is
            # fully constructible; evaluate branches independently and let the
            # container carry the demand if every branch fails.
            branches: list[list[dict[str, Any]]] = []
            for branch_file, branch_node, branch_visiting in resolved_union_branches:
                branch_out: list[dict[str, Any]] = []
                _supply_walk_demand(
                    schema_files,
                    branch_file,
                    branch_node,
                    field_path,
                    branch_visiting,
                    branch_out,
                    True,
                    supplied_defs,
                    covered or ref_supplied,
                    field_caller_signed,
                )
                branches.append(branch_out)
            out.append(
                {
                    "union": True,
                    "path": field_path,
                    "name": prop_name,
                    "ref_def": ref_def,
                    "ref_file": ref_file,
                    "caller_signed": field_caller_signed,
                    "chain_required": chain_required,
                    "covered": covered or ref_supplied,
                    "untyped": False,
                    "schema_identity_sibling": has_schema_identity_sibling,
                    "canonical_bytes_sibling": has_canonical_bytes_sibling,
                    "branches": branches,
                }
            )
            continue
        if is_required:
            out.append(
                {
                    "union": False,
                    "path": field_path,
                    "name": prop_name,
                    "ref_def": ref_def,
                    "ref_file": ref_file,
                    "caller_signed": field_caller_signed,
                    "chain_required": chain_required,
                    "covered": covered or ref_supplied,
                    "untyped": _supply_is_untyped_object(sub),
                    "schema_identity_sibling": has_schema_identity_sibling,
                    "canonical_bytes_sibling": has_canonical_bytes_sibling,
                    "branches": [],
                }
            )
        _supply_walk_demand(
            schema_files,
            file,
            sub,
            field_path,
            visiting,
            out,
            chain_required and is_required,
            supplied_defs,
            covered or ref_supplied,
            field_caller_signed,
        )



def check_request_material_supply_closure(lint: Lint) -> None:
    """service-http-binding.md 2.2.2: every gate-scoped required request input
    (evidence-shaped or CAS/echo-shaped leaf, or untyped required object) must
    have a registered supply source; anything else needs a named exemption row.
    """
    schema_files = _supply_schema_files(lint)
    operation_registry = load_json(
        lint, ARTIFACTS / "registry" / "operation-registry.json"
    )
    if not isinstance(operation_registry, dict):
        return
    operations = operation_registry.get("operations") or []

    supplied_defs: set = set()
    supplied_names: set = set()
    for op in operations:
        response_ref = op.get("response_schema_ref")
        if not response_ref:
            continue
        resolved = _supply_resolve_ref(schema_files, "", response_ref)
        if resolved is None:
            lint.fail(
                ARTIFACTS / "registry" / "operation-registry.json",
                f"{op.get('operation_id')}: response_schema_ref does not resolve",
            )
            continue
        rfile, rdef, rnode = resolved
        supplied_defs.add((rfile, rdef))
        _supply_collect_supply(
            schema_files,
            rfile,
            rnode,
            frozenset({(rfile, rdef)}),
            supplied_defs,
            supplied_names,
        )
    for file, node in schema_files.items():
        base = file.rsplit("/", 1)[-1]
        if not any(marker in base for marker in _SUPPLY_PAYLOAD_SUPPLY_FILES):
            continue
        _supply_collect_supply(schema_files, file, node, frozenset(), supplied_defs, supplied_names)
        for def_name, def_node in (node.get("$defs") or {}).items():
            key = (file, def_name)
            supplied_defs.add(key)
            _supply_collect_supply(
                schema_files,
                file,
                def_node,
                frozenset({key}),
                supplied_defs,
                supplied_names,
            )

    exemption_rows = [
        row
        for row in _supply_load_exemptions(lint)
        if row["kind"] == "request_input"
    ]
    used_rows: set[str] = set()

    def exempted(operation_id: str, field_path: str) -> bool:
        for row in exemption_rows:
            if row["operation_id"] != operation_id:
                continue
            prefix = row["json_path_prefix"]
            if field_path == prefix or field_path.startswith(prefix + ".") or field_path.startswith(prefix + "["):
                used_rows.add(row["exemption_id"])
                return True
        return False

    registry_path = ARTIFACTS / "registry" / "operation-registry.json"
    for op in operations:
        operation_id = op.get("operation_id") or ""
        request_ref = op.get("request_schema_ref")
        if not request_ref:
            continue
        surface = operation_id.split(".")[1] if operation_id.count(".") else ""
        resolved = _supply_resolve_ref(schema_files, "", request_ref)
        if resolved is None:
            lint.fail(
                registry_path,
                f"{operation_id}: request_schema_ref does not resolve",
            )
            continue
        qfile, qdef, qnode = resolved
        demands: list[dict[str, Any]] = []
        _supply_walk_demand(
            schema_files,
            qfile,
            qnode,
            "",
            frozenset({(qfile, qdef)}),
            demands,
            True,
            supplied_defs,
            (qfile, qdef) in supplied_defs,
        )
        supplied_def_names = {def_name for (_file, def_name) in supplied_defs}

        def leaf_fails(demand: dict[str, Any]) -> bool:
            name = demand["name"]
            ref_def = demand["ref_def"]
            untyped = demand["untyped"]
            if not untyped and not demand["chain_required"]:
                return False
            evidence_shaped = bool(
                _SUPPLY_EVIDENCE_RE.search(name)
                or (ref_def and _SUPPLY_EVIDENCE_RE.search(ref_def))
            )
            cas_shaped = bool(_SUPPLY_CAS_ECHO_RE.search(name))
            if not untyped and not evidence_shaped and not cas_shaped:
                return False
            if untyped and (
                demand["schema_identity_sibling"] or demand["canonical_bytes_sibling"]
            ):
                return False
            if _SUPPLY_CLIENT_LOCAL_RE.search(name):
                return False
            if (
                name in _SUPPLY_DID_LOG_DERIVED_NAMES
                or ref_def in _SUPPLY_DID_LOG_DERIVED_DEFS
            ):
                return False
            if demand["caller_signed"]:
                return False
            if not untyped:
                if demand["covered"]:
                    return False
                if surface in _SUPPLY_STRUCTURAL_SURFACES:
                    return False
                if ref_def and ref_def in supplied_def_names:
                    return False
                # Name-level supply is the verbatim-echo discipline for inline
                # scalars; a $ref'd object must match at def level so that a
                # same-named field from an unrelated domain cannot pass it.
                if not ref_def and name in supplied_names:
                    return False
            return True

        def row_fails(row: dict[str, Any]) -> bool:
            if row["union"]:
                # Branches are not necessarily caller-choosable (admission
                # context can dictate one), so every branch must be
                # constructible; a union with any unconstructible branch is
                # surfaced instead of silently passing on the easiest branch.
                return any(
                    any(row_fails(branch_row) for branch_row in branch)
                    for branch in row["branches"]
                )
            return leaf_fails(row)

        for demand in demands:
            if not row_fails(demand):
                continue
            if exempted(operation_id, demand["path"]):
                continue
            if demand["union"]:
                kind = "required union with no constructible branch"
            elif demand["untyped"]:
                kind = "untyped required object"
            else:
                kind = "required input with no registered supply source"
            lint.fail(
                registry_path,
                f"{operation_id}: {demand['path']}: {kind}; register a supply "
                "surface or a named exemption row "
                "(service-http-binding.md 2.2.2)",
            )
    for row in exemption_rows:
        if row["exemption_id"] not in used_rows:
            lint.fail(
                SUPPLY_EXEMPTION_REGISTRY_PATH,
                f"{row['exemption_id']}: stale exemption row matches no failing "
                "demand; delete the row now that the supply exists",
            )
