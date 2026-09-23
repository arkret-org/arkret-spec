"""Artifact lint phase 6: safety."""

from __future__ import annotations

from .core import (
    ALLOWED_PROSE_ACTIONS,
    ARTIFACTS,
    Any,
    FIELD_ORDER_RULES_PATH,
    FIXTURE_REJECT_DECISION_KEYS,
    Iterable,
    Lint,
    Path,
    ROOT,
    SPEC_ROOT,
    _ACTION_TOKEN_RE,
    _PROSE_ACTION_BULLET_RE,
    _PROSE_ACTION_TARGET_RE,
    _REJECT_REASON_CODE_RE,
    base64,
    binascii,
    json,
    load_json,
    load_schema_document,
    load_yaml,
    markdown_files,
    re,
    walk_json,
)


def check_error_code_closure(lint: Lint) -> None:
    """T4-3: error code closure.

    All `error_code` / `reason_code` literals used in spec markdown MUST be
    registered in `artifacts/registry/error-code-registry.json`. Prevents
    the drift where spec text invents a reason code that no implementation
    can resolve.
    """
    registry_path = ARTIFACTS / "registry" / "error-code-registry.json"
    data = load_json(lint, registry_path)
    if not isinstance(data, dict):
        return
    known_codes: set[str] = set()
    for entry in data.get("codes", []):
        if isinstance(entry, dict) and isinstance(entry.get("code"), str):
            known_codes.add(entry["code"])
    for entry in data.get("reason_codes", []):
        if isinstance(entry, dict) and isinstance(entry.get("code"), str):
            known_codes.add(entry["code"])

    if not known_codes:
        return

    # Look for canonical normative usage forms:
    #   reason_code="..." / reason="..." / reason=`...`
    #   reason == "..."
    #   `error_code=...`
    #   return `...` / reject `...` / audit log records reason_code such as `...`
    # We still avoid scanning every freeform backtick token because prose also
    # quotes ordinary schema fields and enum values.
    #
    # Patterns covered (single + double quotes + backticks):
    patterns = [
        re.compile(r'reason_code\s*[=:]\s*["`]([a-z_][a-z0-9_]+)["`]'),
        re.compile(r'reason\s*[=:]\s*["`]([a-z_][a-z0-9_]+)["`]'),
        re.compile(r'reason\s*==\s*["`]([a-z_][a-z0-9_]+)["`]'),
        re.compile(r'error_code\s*[=:]\s*["`]([a-z_][a-z0-9_]+)["`]'),
        re.compile(r'`reason\s*=\s*["\']?([a-z_][a-z0-9_]+)["\']?`'),
        re.compile(r'reason_code[^`\n]*(?:如|such as)\s+`([a-z_][a-z0-9_]+)`', re.IGNORECASE),
    ]
    code_like_re = re.compile(
        r"(_invalid|_mismatch|_required|_forbidden|_denied|_expired|_stale|"
        r"_conflict|_unavailable|_missing|_not_allowed|_too_stale|"
        r"_rate_limited|_failed|_violation|_rejected|_redacted|"
        r"_unknown|_incomplete)$"
    )
    non_error_code_tokens = {
        "on_conflict",
        # Sync stream frame.kind tokens, not reason codes. Their endpoint-layer
        # error codes are stream_dropped / stream_resync_required (client-sync.md
        # §5, service-http-binding.md §1015); the bare frame.kind ends in
        # _required and would otherwise trip the code-shape heuristic.
        "resync_required",
        # Direct Conversation resolver outcome state, not a reason code
        # (direct-conversation-operations.schema.json#/$defs/
        # direct_conversation_resolve_outcome, contact-and-direct-conversation
        # .md §9.1). It ends in _required and appears on sentences about what
        # the resolver returns, so it would otherwise trip the heuristic.
        "creation_required",
        # Closed decision values of the device-revocation gate receipt
        # (device-revocation-state.schema.json#/$defs/
        # device_revocation_gate_decision_receipt.decision,
        # device-lifecycle.md §2.2). A validated gate request always returns a
        # typed 200 receipt carrying one of them, so they appear on sentences
        # about what the gate returns; the corresponding endpoint error codes
        # are device_revocation_pending / device_revoked on the blocked
        # business operation. Both end in _mismatch and would otherwise trip
        # the code-shape heuristic.
        "authority_mismatch",
        "generation_mismatch",
        # Closed freshness flag of the account onboarding goal
        # (account-operations.schema.json#/$defs/account_onboarding_goal,
        # account-lifecycle.md §2.1.2). It is a snapshot field, not a wire
        # reason code, but ends in _required and appears on a sentence that
        # also rejects expired/revoked handoffs, so it would otherwise trip
        # the code-shape heuristic.
        "fresh_authentication_required",
        # Source-local durable attempt status of the history-key response
        # outbox (history-visibility.md 6/6.2), never a wire reason code: it is
        # the state an attempt enters once its exact bytes are permanently
        # unacceptable, so the source stops retrying without claiming delivery.
        # It ends in _rejected and appears on sentences about rejected chunks,
        # so it would otherwise trip the code-shape heuristic.
        "permanently_rejected",
        # Closed device-revocation result status, authenticated by its deciding
        # Seal. It is not a reason_code (device-revocation-state.schema.json).
        "revocation_rejected",
    }

    for path in markdown_files():
        text = path.read_text(encoding="utf-8")
        unresolved: set[str] = set()
        for pat in patterns:
            for match in pat.finditer(text):
                code = match.group(1)
                if code in known_codes:
                    continue
                # Filter common false positives (English words used elsewhere)
                if code in {"true", "false", "null", "ok", "yes", "no", "n_a"}:
                    continue
                unresolved.add(code)
        for line in text.splitlines():
            reason_examples = re.search(r"reason_code[^`\n]*(?:如|例如|such as)(?P<tail>.*)$", line, re.IGNORECASE)
            if reason_examples:
                candidate_text = reason_examples.group("tail")
                require_code_shape = False
            elif re.search(r"(返回|return|reject|拒绝)", line, re.IGNORECASE):
                candidate_text = line
                require_code_shape = True
            else:
                continue
            for code in re.findall(r"`([a-z_][a-z0-9_]+)`", candidate_text):
                if code in non_error_code_tokens:
                    continue
                if require_code_shape and not code_like_re.search(code):
                    continue
                if code in known_codes:
                    continue
                if code in {"true", "false", "null", "ok", "yes", "no", "n_a"}:
                    continue
                unresolved.add(code)
        for code in sorted(unresolved):
            lint.fail(path, f"reason_code referenced but not in error-code-registry.json: {code!r}")

    json_reason_keys = {"reason_code", "reject_reason", "expected_audit_reason"}
    for path in [ARTIFACTS / "profiles" / "conformance-profiles.json"]:
        data = load_json(lint, path)
        if data is None:
            continue
        unresolved: set[str] = set()
        for _, value, key in walk_json(data):
            if key in json_reason_keys and isinstance(value, str):
                if value not in known_codes:
                    unresolved.add(value)
        for code in sorted(unresolved):
            lint.fail(path, f"reason_code referenced but not in error-code-registry.json: {code!r}")


def check_error_code_registry_uniqueness(lint: Lint) -> None:
    """Reject duplicates and asymmetric explicit dual-registration metadata.

    Top-level ``codes`` and item-level ``reason_codes`` may intentionally reuse
    a string under the dual-registration model, but a duplicate inside the same
    section has no stable first/last-wins semantics for SDK generation or
    catalog UI. If either side explicitly labels a row dual-registered, the
    matching row and reciprocal label are required on the other side.
    """
    path = ARTIFACTS / "registry" / "error-code-registry.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return

    rows_by_section: dict[str, dict[str, dict[str, Any]]] = {}
    for section in ("codes", "reason_codes"):
        rows = data.get(section, [])
        if not isinstance(rows, list):
            lint.fail(path, f"{section} must be a list")
            continue
        seen: dict[str, int] = {}
        rows_by_section[section] = {}
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                lint.fail(path, f"{section}[{index}] must be an object")
                continue
            code = row.get("code")
            if not isinstance(code, str) or not code:
                lint.fail(path, f"{section}[{index}] missing non-empty code")
                continue
            previous = seen.get(code)
            if previous is not None:
                lint.fail(
                    path,
                    f"duplicate error code {code!r} inside {section} at rows {previous} and {index}",
                )
            seen[code] = index
            rows_by_section[section][code] = row
            # A top-level code is an HTTP-mapped protocol error; a reason code is
            # a sub-reason carried inside one. Putting a row in the wrong section
            # is invisible here but breaks every consumer that generates HTTP
            # status mappings from codes[].
            if section == "codes":
                if not isinstance(row.get("http_status"), int) or isinstance(
                    row.get("http_status"), bool
                ):
                    lint.fail(path, f"codes[{index}] {code!r} must declare an integer http_status")
                if not isinstance(row.get("scope"), str) or not row.get("scope"):
                    lint.fail(path, f"codes[{index}] {code!r} must declare a scope")
            elif "http_status" in row:
                lint.fail(
                    path,
                    f"reason_codes[{index}] {code!r} must not declare http_status; "
                    "a sub-reason inherits the status of the code it qualifies",
                )
            if not isinstance(row.get("description"), str) or not row.get("description").strip():
                lint.fail(path, f"{section}[{index}] {code!r} must carry a description")

    top_level_rows = rows_by_section.get("codes", {})
    reason_rows = rows_by_section.get("reason_codes", {})
    for code in sorted(set(top_level_rows) | set(reason_rows)):
        top_description = top_level_rows.get(code, {}).get("description", "")
        reason_description = reason_rows.get(code, {}).get("description", "")
        top_declares_dual = isinstance(top_description, str) and "dual-registered" in top_description.lower()
        reason_declares_dual = (
            isinstance(reason_description, str) and "dual-registered" in reason_description.lower()
        )
        if top_declares_dual != reason_declares_dual:
            missing_side = "reason_codes" if top_declares_dual else "codes"
            lint.fail(path, f"{code!r} dual-registration description missing reciprocal label in {missing_side}")


def check_consent_current_clean_break(lint: Lint) -> None:
    """Consent self views mirror one governance-committed current row, not OR-set dots."""
    schema_path = ARTIFACTS / "schemas" / "consent-operations.schema.json"
    schema = load_json(lint, schema_path)
    if not isinstance(schema, dict):
        return
    defs = schema.get("$defs", {})
    if defs.get("consent_state", {}).get("enum") != ["active", "revoked"]:
        lint.fail(schema_path, "consent_state must be exactly active|revoked; expiry is a read-time predicate")
    view = defs.get("consent_view", {})
    properties = view.get("properties", {})
    if not {"consent_id", "state", "revision"}.issubset(properties):
        lint.fail(schema_path, "consent_view must carry stable ID, current state and exact revision")
    for retired in ("requested_at", "active_grant_dots", "grant_dots", "revoked_dots"):
        if retired in properties:
            lint.fail(schema_path, f"consent_view must not restore retired or inferred field {retired!r}")


def check_direct_conversation_local_blocker_clean_break(lint: Lint) -> None:
    profiles_path = ARTIFACTS / "profiles" / "conformance-profiles.json"
    vectors_path = ARTIFACTS / "registry" / "vector-registry.json"
    profiles = load_json(lint, profiles_path)
    vectors = load_json(lint, vectors_path)
    if not isinstance(profiles, dict) or not isinstance(vectors, dict):
        return
    role = profiles.get("profile_requirements", {}).get("ak.profile.direct_conversation_realm.v1", {})
    values = role.get("client_local_send_blockers", {}).get("values")
    if values != ["personal_blocked"]:
        lint.fail(profiles_path, "Direct Conversation client-local blockers must be exactly personal_blocked")
    rows = [row for row in vectors.get("vectors", []) if isinstance(row, dict) and row.get("vector_id") == "ak.vector.direct_conversation.send_blocker_authority.v1"]
    if len(rows) != 1 or "history_key_unavailable" in rows[0].get("description", ""):
        lint.fail(vectors_path, "send blocker vector must not restore retired history_key_unavailable")


def check_operations_error_mapping_closure(lint: Lint) -> None:
    """Every operations-error-mapping code must be in the error registry."""
    registry_path = ARTIFACTS / "registry" / "error-code-registry.json"
    mapping_path = ARTIFACTS / "registry" / "operations-error-mapping.json"
    registry = load_json(lint, registry_path)
    mapping = load_json(lint, mapping_path)
    if not isinstance(registry, dict) or not isinstance(mapping, dict):
        return

    # Route failures happen before an operation_id exists. Keep their producer
    # path machine-readable and tied to active typed error codes and OpenAPI.
    route_rows = mapping.get("pre_dispatch_route_errors")
    expected_route_codes = {
        "unrecognized_endpoint": 404,
        "method_not_allowed": 405,
    }
    if not isinstance(route_rows, list) or len(route_rows) != 2:
        lint.fail(mapping_path, "pre_dispatch_route_errors must contain exactly the 404/405 router producers")
    else:
        actual_route_codes: dict[str, int] = {}
        for row in route_rows:
            if not isinstance(row, dict):
                lint.fail(mapping_path, "pre_dispatch_route_errors entry must be an object")
                continue
            code = row.get("code")
            if code in actual_route_codes:
                lint.fail(mapping_path, f"duplicate pre-dispatch route producer: {code!r}")
            if isinstance(code, str):
                actual_route_codes[code] = row.get("http_status")
            if row.get("producer_stage") != "router_before_operation_dispatch" or row.get("side_effects") != "none" or row.get("problem_content_type") != "application/problem+json":
                lint.fail(mapping_path, f"invalid pre-dispatch route producer contract: {code!r}")
        if actual_route_codes != expected_route_codes:
            lint.fail(mapping_path, "pre_dispatch_route_errors code/status pair must be unrecognized_endpoint/404 and method_not_allowed/405")

    active_codes = {
        row.get("code"): row.get("http_status")
        for row in registry.get("codes", [])
        if isinstance(row, dict) and row.get("status") == "active"
    }
    for code, status in expected_route_codes.items():
        if active_codes.get(code) != status:
            lint.fail(registry_path, f"route producer {code!r} requires active HTTP {status} registry code")

    openapi_path = ARTIFACTS / "openapi" / "arkret-service-api.openapi.yaml"
    openapi = load_yaml(lint, openapi_path)
    responses = (openapi or {}).get("components", {}).get("responses", {}) if isinstance(openapi, dict) else {}
    for response_name, code in (("UnrecognizedEndpoint", "unrecognized_endpoint"), ("MethodNotAllowed", "method_not_allowed")):
        response = responses.get(response_name, {})
        if response.get("x-arkret-route-error-code") != code or "application/problem+json" not in response.get("content", {}):
            lint.fail(openapi_path, f"{response_name} must expose canonical route Problem code {code!r}")

    known_codes = {
        row.get("code")
        for section in ("codes", "reason_codes")
        for row in registry.get(section, [])
        if isinstance(row, dict) and isinstance(row.get("code"), str)
    }
    unresolved: set[str] = set()

    rules = mapping.get("rules")
    if isinstance(rules, dict):
        universal = rules.get("universal_codes")
        if isinstance(universal, str):
            match = re.search(r"any of:\s*(?P<codes>.*?)(?:\.|$)", universal)
            code_text = match.group("codes") if match else universal
            for raw_code in code_text.split(","):
                code = raw_code.strip().strip(".")
                if not re.fullmatch(r"[a-z][a-z0-9_]+", code):
                    continue
                if code not in known_codes:
                    unresolved.add(code)

    operations = mapping.get("operations")
    if isinstance(operations, list):
        for index, row in enumerate(operations):
            if not isinstance(row, dict):
                lint.fail(mapping_path, f"operations[{index}] must be an object")
                continue
            for code in row.get("operation_specific", []):
                if not isinstance(code, str):
                    lint.fail(mapping_path, f"operations[{index}].operation_specific contains non-string code")
                    continue
                if code not in known_codes:
                    unresolved.add(code)

    for code in sorted(unresolved):
        lint.fail(mapping_path, f"error code referenced but not in error-code-registry.json: {code!r}")

    # Coverage invariant (rules.operation_coverage): every operation_id in
    # operation-registry.json MUST appear in operations[] exactly once, and
    # operations[] MUST NOT reference an operation_id absent from the registry.
    op_registry_path = ARTIFACTS / "registry" / "operation-registry.json"
    op_registry = load_json(lint, op_registry_path)
    if isinstance(op_registry, dict) and isinstance(operations, list):
        registry_http = {
            row["operation_id"]: row.get("http")
            for row in op_registry.get("operations", [])
            if isinstance(row, dict) and isinstance(row.get("operation_id"), str)
        }
        registry_ids = set(registry_http)
        mapping_counts: dict[str, int] = {}
        for row in operations:
            if isinstance(row, dict) and isinstance(row.get("operation_id"), str):
                op_id = row["operation_id"]
                mapping_counts[op_id] = mapping_counts.get(op_id, 0) + 1
                if op_id in registry_http and row.get("http_alias") != registry_http[op_id]:
                    lint.fail(mapping_path, f"operations[] http_alias differs from operation-registry.json for {op_id!r}")
        for op_id in sorted(registry_ids):
            count = mapping_counts.get(op_id, 0)
            if count == 0:
                lint.fail(mapping_path, f"operation_id in operation-registry.json missing from operations[]: {op_id!r}")
            elif count > 1:
                lint.fail(mapping_path, f"operation_id appears {count} times in operations[] (must be exactly once): {op_id!r}")
        for op_id in sorted(mapping_counts):
            if op_id not in registry_ids:
                lint.fail(mapping_path, f"operations[] references operation_id absent from operation-registry.json: {op_id!r}")


def check_fixture_reject_reason_closure(lint: Lint) -> None:
    """Fixture reject `reason` codes must resolve in error-code-registry.json.

    Only enumerable reason_code-style values (snake_case identifiers) sitting in
    a reject / deny decision context (or a rollback object) are gated; free-text
    `reason` prose is ignored per the models/common-fields.md reason vs
    reason_code convention.
    """
    registry_path = ARTIFACTS / "registry" / "error-code-registry.json"
    registry = load_json(lint, registry_path)
    if not isinstance(registry, dict):
        return
    known_codes = {
        row.get("code")
        for section in ("codes", "reason_codes")
        for row in registry.get(section, [])
        if isinstance(row, dict) and isinstance(row.get("code"), str)
    }

    def is_reject(value: Any) -> bool:
        return isinstance(value, str) and ("reject" in value or value == "deny")

    def walk(node: Any, parent_key: str | None, json_path: str, path: Path) -> None:
        if isinstance(node, dict):
            reason = node.get("reason")
            if isinstance(reason, str) and _REJECT_REASON_CODE_RE.fullmatch(reason):
                reject_ctx = parent_key == "rollback" or any(
                    is_reject(node.get(key)) for key in FIXTURE_REJECT_DECISION_KEYS
                )
                if reject_ctx and reason not in known_codes:
                    lint.fail(
                        path,
                        f"{json_path}.reason reject code not in error-code-registry.json: {reason!r}",
                    )
            for key, value in node.items():
                walk(value, key, f"{json_path}/{key}", path)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, parent_key, f"{json_path}[{index}]", path)

    for path in sorted((ARTIFACTS / "fixtures").glob("**/*.json")):
        data = load_json(lint, path)
        if data is not None:
            walk(data, None, "$", path)


def check_openapi_no_floating_number(lint: Lint) -> None:
    """T4-5: forbid `type: number` in OpenAPI.

    v1 wire mandates integer-only JSON numbers (see encoding.md §2). Any
    `type: number` in OpenAPI would generate float/double SDK fields and
    break canonical-bytes interop. The forbidden-fields list below carries
    explicit waivers for known non-canonical surfaces.
    """
    openapi_path = ARTIFACTS / "openapi" / "arkret-service-api.openapi.yaml"
    if not openapi_path.exists():
        return
    lines = openapi_path.read_text(encoding="utf-8").splitlines()

    # Walk line-by-line; a waiver comment makes the next few lines'
    # `type: number` legal. Window of 8 lines is generous enough for
    # any reasonable YAML block while keeping the scan O(n).
    waiver_re = re.compile(r"#\s*lint-waiver\(type:number\)\s*:")
    type_number_re = re.compile(r"^\s*-?\s*type:\s*number\s*(?:#.*)?$")

    waiver_window = 0
    for line_no, line in enumerate(lines, start=1):
        if waiver_re.search(line):
            # next ≤ 8 lines may carry the waivered `type: number`
            waiver_window = 8
            continue
        if type_number_re.match(line):
            if waiver_window > 0:
                waiver_window = 0  # consume the waiver
                continue
            lint.fail(
                openapi_path,
                f"line {line_no}: `type: number` is forbidden in v1 wire; "
                "use integer + scale, or add a `# lint-waiver(type:number): <reason>` "
                "comment within 8 lines for non-canonical surfaces",
            )
        elif waiver_window > 0:
            waiver_window -= 1


def _load_field_order_rules(lint: Lint) -> dict[str, Any]:
    """Load the declarative field-ordering rule config (C-BET-03).

    Falls back to the historical hard-coded rule set if the config is missing or
    malformed, so the gate never silently stops enforcing ordering.
    """
    default = {
        "hard_precedence": [
            {"earlier": "created_by", "later": "created_at"},
            {"earlier": "created_at", "later": "updated_at"},
            {"earlier": "updated_by", "later": "updated_at"},
        ],
        "hard_immediate_follow": [
            {"anchor": "state", "marker": "state_changed_at"},
            {"anchor": "stage", "marker": "stage_changed_at"},
        ],
        "ordered_groups": {},
        "role_after_subject": {},
    }
    if not FIELD_ORDER_RULES_PATH.exists():
        return default
    try:
        data = json.loads(FIELD_ORDER_RULES_PATH.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - config corruption
        lint.fail(FIELD_ORDER_RULES_PATH, f"invalid field-order rule config: {exc}")
        return default
    if not isinstance(data, dict):
        lint.fail(FIELD_ORDER_RULES_PATH, "field-order rule config must be a JSON object")
        return default
    return {**default, **data}


def check_field_order(lint: Lint) -> None:
    """Canonical field ordering gate (models/common-fields.md §3.2; C-BET-03).

    Rules are loaded from the declarative ``tools/field-order-rules.json`` config
    and applied recursively to every object's ``properties`` in all schema files
    (and to the relative order of ``required`` entries against ``properties``).

    Two enforcement tiers:

    * Hard rules (errors) — wire-stable leading-group, precedence and
      immediate-follow rules
      that already hold across every current schema:
        - created_by MUST precede created_at; created_at MUST precede updated_at;
          updated_by MUST precede updated_at.
        - state_changed_at MUST immediately follow state; stage_changed_at MUST
          immediately follow stage.

    * Ordered-group rules (errors) — coverage for validity / issuance /
      audit-tail member fields (issued_at, not_before, effective_at,
      expires_at, revoked_*, updated_*) and ``role`` placement. These rules are
      presence-conditional and currently hold across the registered schemas, so
      drift is a lint error rather than an advisory warning.

    All checks are presence-conditional, so intended exceptions (Read Cursor has
    no created_at, Capability Grant uses issued_at) never trigger.
    """

    rules = _load_field_order_rules(lint)
    leading_group = rules.get("leading_group") or []
    hard_precedence = rules.get("hard_precedence") or []
    hard_immediate = rules.get("hard_immediate_follow") or []
    ordered_groups = rules.get("ordered_groups") or {}
    cluster_precedence = rules.get("cluster_precedence") or []
    role_rule = rules.get("role_after_subject") or {}
    subject_anchors = set(role_rule.get("subject_anchors") or [])
    role_field = role_rule.get("role_field")

    def check_order_of_keys(
        path: Path,
        json_path: str,
        keys: list[str],
        where: str,
        enforce_leading_group: bool,
    ) -> None:
        index = {key: position for position, key in enumerate(keys)}

        # Present members of the canonical identity/schema/scope leading group
        # must occupy the first slots when the object declares that convention
        # by beginning `required` with one of those members. This preserves
        # non-canonical DTO/scope shapes that merely happen to carry realm_id.
        if enforce_leading_group:
            present_leaders = [member for member in leading_group if member in index]
            if keys[:len(present_leaders)] != present_leaders:
                lint.fail(
                    path,
                    f"{json_path}.{where}: leading group {present_leaders} MUST occupy "
                    "the first declared slots in that order",
                )

        # Hard precedence (errors).
        for rule in hard_precedence:
            earlier = rule.get("earlier")
            later = rule.get("later")
            if earlier in index and later in index and index[earlier] > index[later]:
                lint.fail(
                    path,
                    f"{json_path}.{where}: field order: '{earlier}' MUST precede '{later}'",
                )

        # Hard immediate-follow (errors). Only meaningful for properties ordering.
        if where == "properties":
            for rule in hard_immediate:
                anchor = rule.get("anchor")
                marker = rule.get("marker")
                if anchor in index and marker in index and index[marker] != index[anchor] + 1:
                    lint.fail(
                        path,
                        f"{json_path}.{where}: '{marker}' MUST immediately follow '{anchor}'",
                    )

        # Ordered-group relative ordering (errors).
        for group_name, members in ordered_groups.items():
            if group_name.startswith("$") or not isinstance(members, list):
                continue
            present = [m for m in members if m in index]
            for i in range(len(present)):
                for j in range(i + 1, len(present)):
                    earlier, later = present[i], present[j]
                    if index[earlier] > index[later]:
                        lint.fail(
                            path,
                            f"{json_path}.{where}: group '{group_name}' ordering: "
                            f"'{earlier}' MUST precede '{later}'",
                        )

        # Cluster precedence (errors): every present member of the earlier
        # cluster MUST precede every present member of the later cluster.
        for rule in cluster_precedence:
            if not isinstance(rule, dict):
                continue
            earlier_present = [m for m in (rule.get("earlier") or []) if m in index]
            later_present = [m for m in (rule.get("later") or []) if m in index]
            if earlier_present and later_present:
                latest_earlier = max(index[m] for m in earlier_present)
                earliest_later = min(index[m] for m in later_present)
                if latest_earlier > earliest_later:
                    offending_earlier = max(earlier_present, key=lambda m: index[m])
                    offending_later = min(later_present, key=lambda m: index[m])
                    lint.fail(
                        path,
                        f"{json_path}.{where}: validity cluster MUST precede creation/audit cluster: "
                        f"'{offending_earlier}' MUST precede '{offending_later}'",
                    )

        # role placement relative to subject/issuer anchor (error).
        if role_field and role_field in index:
            anchors_present = [a for a in subject_anchors if a in index]
            if anchors_present:
                earliest_anchor = min(index[a] for a in anchors_present)
                if index[role_field] < earliest_anchor:
                    lint.fail(
                        path,
                        f"{json_path}.{where}: '{role_field}' MUST follow its "
                        f"subject/issuer identity field",
                    )

    def check_node(path: Path, json_path: str, node: dict) -> None:
        required = node.get("required")
        if isinstance(required, list):
            seen_required: set[str] = set()
            duplicate_required: list[str] = []
            for member in required:
                if not isinstance(member, str):
                    continue
                if member in seen_required and member not in duplicate_required:
                    duplicate_required.append(member)
                seen_required.add(member)
            if duplicate_required:
                lint.fail(
                    path,
                    f"{json_path}.required: duplicate member(s): {duplicate_required}",
                )
        props = node.get("properties")
        if isinstance(props, dict):
            present_leaders = [member for member in leading_group if member in props]
            enforce_leading_group = (
                isinstance(required, list)
                and "schema" in present_leaders
                and required[: len(present_leaders)] == present_leaders
            )
            check_order_of_keys(
                path,
                json_path,
                list(props.keys()),
                "properties",
                enforce_leading_group,
            )
            if isinstance(required, list):
                required_set = {
                    member for member in required if isinstance(member, str)
                }
                local_required = [
                    member
                    for member in required
                    if isinstance(member, str) and member in props
                ]
                expected_local_required = [
                    member for member in props if member in required_set
                ]
                if local_required != expected_local_required:
                    lint.fail(
                        path,
                        f"{json_path}.required: locally declared members MUST follow "
                        f"properties order; expected {expected_local_required}, "
                        f"got {local_required}",
                    )

                # Check required entries in the order they are declared. A field
                # listed in required but absent from properties is left to the
                # existing schema-shape checks; we only order known property keys.
                req_keys = [r for r in required if isinstance(r, str)]
                check_order_of_keys(
                    path,
                    json_path,
                    req_keys,
                    "required",
                    enforce_leading_group,
                )

    def recurse(path: Path, json_path: str, node: Any) -> None:
        if isinstance(node, dict):
            check_node(path, json_path, node)
            for key, child in node.items():
                recurse(path, f"{json_path}.{key}", child)
        elif isinstance(node, list):
            for position, child in enumerate(node):
                recurse(path, f"{json_path}[{position}]", child)

    for schema_path in sorted((ARTIFACTS / "schemas").glob("*.schema.json")):
        data = load_json(lint, schema_path)
        if data is not None:
            recurse(schema_path, "$", data)


def check_model_required_field_table_coverage(lint: Lint) -> None:
    """Ensure core model field tables list every schema-required top-level field."""

    model_tables = [
        (
            "spec/v1/zh/models/realm-and-space.md",
            "spec/v1/artifacts/schemas/realm.schema.json",
            "ak.schema.realm.v1",
        ),
        (
            "spec/v1/zh/models/realm-and-space.md",
            "spec/v1/artifacts/schemas/space.schema.json",
            "ak.schema.space.v1",
        ),
        (
            "spec/v1/zh/models/strand-and-message.md",
            "spec/v1/artifacts/schemas/strand.schema.json",
            "ak.schema.strand.v1",
        ),
        (
            "spec/v1/zh/models/strand-and-message.md",
            "spec/v1/artifacts/schemas/message.schema.json",
            "ak.schema.message.v1",
        ),
        (
            "spec/v1/zh/models/relation.md",
            "spec/v1/artifacts/schemas/relation.schema.json",
            "ak.schema.relation.v1",
        ),
        (
            "spec/v1/zh/models/circle.md",
            "spec/v1/artifacts/schemas/circle.schema.json",
            "ak.schema.circle.v1",
        ),
        (
            "spec/v1/zh/models/morph.md",
            "spec/v1/artifacts/schemas/morph.schema.json",
            "ak.schema.morph.v1",
        ),
        (
            "spec/v1/zh/models/views.md",
            "spec/v1/artifacts/schemas/view.schema.json",
            "ak.schema.view.v1",
        ),
        (
            "spec/v1/zh/models/actor.md",
            "spec/v1/artifacts/schemas/actor-profile.schema.json",
            "ak.schema.actor_profile.v1",
        ),
    ]

    row_field_re = re.compile(r"^\|\s*`([^`]+)`\s*\|", re.MULTILINE)
    next_heading_re = re.compile(r"^#{2,6}\s+", re.MULTILINE)

    for doc_rel, schema_rel, schema_id in model_tables:
        doc_path = ROOT / doc_rel
        schema_path = ROOT / schema_rel
        schema = load_json(lint, schema_path)
        if not isinstance(schema, dict):
            continue
        required = schema.get("required")
        if not isinstance(required, list):
            continue
        try:
            text = doc_path.read_text(encoding="utf-8")
        except Exception as exc:
            lint.fail(doc_path, f"cannot read model field table: {exc}")
            continue

        marker = f"Schema id: `{schema_id}`"
        marker_index = text.find(marker)
        if marker_index < 0:
            lint.fail(doc_path, f"missing model field table marker for {schema_id}")
            continue

        table_region = text[marker_index + len(marker) :]
        next_heading = next_heading_re.search(table_region)
        if next_heading:
            table_region = table_region[: next_heading.start()]
        table_fields = {match.group(1) for match in row_field_re.finditer(table_region)}
        missing = [field for field in required if isinstance(field, str) and field not in table_fields]
        if missing:
            lint.fail(
                doc_path,
                f"{schema_id} field table missing schema-required field(s): {', '.join(missing)}",
            )


def check_exporter_label_registry(lint: Lint) -> None:
    """Validate the media exporter-label registry (OPT-003 / TERM-006).

    Each label is a wire-breaking key-derivation domain separation parameter;
    the registry is the single source of truth for label string, Context field
    shape, output length, applicable profiles, and grandfathering.
    """
    path = ARTIFACTS / "registry" / "exporter-label-registry.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        lint.fail(path, "exporter-label-registry.json must be a JSON object")
        return
    labels = data.get("labels")
    if not isinstance(labels, list) or not labels:
        lint.fail(path, "exporter-label-registry.json: labels MUST be a non-empty list")
        return
    required = {"label", "context_fields", "output_bytes", "applies_to_profiles", "grandfathered"}
    seen: set[str] = set()
    for index, entry in enumerate(labels):
        if not isinstance(entry, dict):
            lint.fail(path, f"labels[{index}] must be an object")
            continue
        for missing in sorted(required - set(entry.keys())):
            lint.fail(path, f"labels[{index}] missing required key: {missing}")
        label = entry.get("label")
        if isinstance(label, str):
            if label in seen:
                lint.fail(path, f"duplicate exporter label: {label}")
            seen.add(label)
        context_fields = entry.get("context_fields")
        if not isinstance(context_fields, list):
            lint.fail(path, f"labels[{index}] context_fields MUST be a list")
        elif not context_fields:
            if entry.get("primitive") != "ExpandWithLabel" or entry.get("empty_context_forbidden") is not False:
                lint.fail(
                    path,
                    f"labels[{index}] empty context_fields is allowed only for an explicitly empty-context ExpandWithLabel entry",
                )
            if not isinstance(entry.get("context_encoding"), str) or "empty" not in entry["context_encoding"]:
                lint.fail(path, f"labels[{index}] empty-context entry must define context_encoding")


def json_pointer_get(data: Any, pointer: str) -> Any:
    current = data
    for token in pointer.removeprefix("/").split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and token in current:
            current = current[token]
            continue
        return None
    return current


def check_alg_registry(lint: Lint) -> None:
    path = ARTIFACTS / "registry" / "signature-alg-registry.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return
    algorithms = data.get("algorithms")
    if not isinstance(algorithms, list) or not algorithms:
        lint.fail(path, "algorithms must be a non-empty array")
        return

    algs_by_proof_kind: dict[str, set[str]] = {
        "detached_jws": set(),
        "raw_detached_signature": set(),
    }
    http_message_signature_algorithms: set[str] = set()
    canonical_ids: set[str] = set()
    for index, row in enumerate(algorithms):
        label = f"algorithms[{index}]"
        if not isinstance(row, dict):
            lint.fail(path, f"{label} must be an object")
            continue
        canonical_id = row.get("canonical_id")
        jose_algorithm = row.get("jose_algorithm")
        raw_signature_algorithm = row.get("raw_signature_algorithm")
        http_message_signature_algorithm = row.get("http_message_signature_algorithm")
        proof_kinds = row.get("proof_kinds")
        status = row.get("status")
        if not isinstance(canonical_id, str) or not canonical_id:
            lint.fail(path, f"{label}.canonical_id must be a non-empty string")
            continue
        if canonical_id in canonical_ids:
            lint.fail(path, f"duplicate canonical_id: {canonical_id}")
        canonical_ids.add(canonical_id)
        if status == "active":
            if not isinstance(proof_kinds, list) or not proof_kinds:
                lint.fail(path, f"{label}.proof_kinds must be a non-empty array")
                continue
            for proof_kind in proof_kinds:
                if proof_kind not in algs_by_proof_kind:
                    lint.fail(path, f"{label}.proof_kinds contains unsupported kind {proof_kind!r}")
                    continue
                algorithm = (
                    jose_algorithm
                    if proof_kind == "detached_jws"
                    else raw_signature_algorithm
                )
                if not isinstance(algorithm, str) or not algorithm:
                    lint.fail(path, f"{label} lacks an algorithm mapping for {proof_kind}")
                    continue
                algs_by_proof_kind[proof_kind].add(algorithm)
            if isinstance(http_message_signature_algorithm, str) and http_message_signature_algorithm:
                http_message_signature_algorithms.add(http_message_signature_algorithm)

    expected_jws = sorted(algs_by_proof_kind["detached_jws"])
    expected_raw = sorted(algs_by_proof_kind["raw_detached_signature"])
    detached_jws_pattern = r"^[A-Za-z0-9_-]+\.\.[A-Za-z0-9_-]+$"
    # `alg` belongs to standards-defined JOSE objects only. In v1 schemas the
    # only inline JOSE object is the WebSocket DPoP protected header; compact
    # detached JWS values elsewhere are opaque strings and MUST NOT duplicate
    # their protected algorithm in an Arkret wrapper field.
    allowed_alg_property = (
        "websocket-dpop-proof.schema.json",
        "/$defs/protected_header/properties/alg",
    )

    def algorithm_properties(value: Any, pointer: str = "") -> Iterable[tuple[str, str, Any]]:
        if isinstance(value, dict):
            properties = value.get("properties")
            if isinstance(properties, dict):
                for name, property_schema in properties.items():
                    yield name, f"{pointer}/properties/{name}", property_schema
            for key, child in value.items():
                yield from algorithm_properties(child, f"{pointer}/{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                yield from algorithm_properties(child, f"{pointer}/{index}")

    for schema_path in sorted((ARTIFACTS / "schemas").glob("*.json")):
        schema = load_json(lint, schema_path)
        if not isinstance(schema, dict):
            continue
        for name, pointer, property_schema in algorithm_properties(schema):
            if name == "alg" and (schema_path.name, pointer) != allowed_alg_property:
                lint.fail(
                    schema_path,
                    f"{pointer} uses JOSE-only shorthand alg in an Arkret-owned object",
                )
            if name == "accepted_algs" or name.endswith("_alg"):
                lint.fail(schema_path, f"{pointer} uses forbidden abbreviated algorithm field {name}")
            if name == "jws":
                if (
                    not isinstance(property_schema, dict)
                    or property_schema.get("type") != "string"
                    or property_schema.get("pattern") != detached_jws_pattern
                ):
                    lint.fail(
                        schema_path,
                        f"{pointer} must be a compact detached JWS with an empty payload segment",
                    )
            if name != "signature_algorithm" or not isinstance(property_schema, dict):
                continue
            resolved = property_schema
            ref = resolved.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/"):
                resolved = json_pointer_get(schema, ref.removeprefix("#"))
            values: list[str] = []
            if isinstance(resolved, dict) and isinstance(resolved.get("const"), str):
                values = [resolved["const"]]
            elif isinstance(resolved, dict) and isinstance(resolved.get("enum"), list):
                values = [item for item in resolved["enum"] if isinstance(item, str)]
            if not values:
                lint.fail(
                    schema_path,
                    f"{pointer} must fail closed with an explicit const/enum from raw_signature_algorithm mappings",
                )
            elif not set(values).issubset(set(expected_raw)):
                lint.fail(
                    schema_path,
                    f"{pointer} contains values outside active raw_signature_algorithm mappings: {values!r}; allowed={expected_raw!r}",
                )

    def check_fixture_algorithm_names(value: Any, fixture_path: Path, pointer: str = "") -> None:
        if isinstance(value, dict):
            for short_name in (
                name for name in value if name == "accepted_algs" or name.endswith("_alg")
            ):
                lint.fail(
                    fixture_path,
                    f"{pointer}/{short_name} uses forbidden abbreviated algorithm field {short_name}",
                )
            if "alg" in value:
                path_tokens = {token for token in pointer.split("/") if token}
                is_protected_header = bool(path_tokens & {"protected_header", "protected"})
                is_jwk = value.get("kty") in {"OKP", "EC", "RSA", "AKP"} and (
                    "crv" in value or "x" in value or "n" in value or "pub" in value
                )
                if not is_protected_header and not is_jwk:
                    lint.fail(
                        fixture_path,
                        f"{pointer}/alg uses JOSE-only shorthand outside a protected header or JWK",
                    )
            for key, child in value.items():
                if key == "jws":
                    label = f"{pointer}/jws"
                    if not isinstance(child, str) or not re.fullmatch(detached_jws_pattern, child):
                        lint.fail(fixture_path, f"{label} must be compact detached JWS")
                    else:
                        protected_text, _, signature_text = child.split(".")
                        try:
                            protected_bytes = base64.urlsafe_b64decode(
                                protected_text + "=" * (-len(protected_text) % 4)
                            )
                            signature_bytes = base64.urlsafe_b64decode(
                                signature_text + "=" * (-len(signature_text) % 4)
                            )
                            if (
                                base64.urlsafe_b64encode(protected_bytes).rstrip(b"=").decode("ascii")
                                != protected_text
                                or base64.urlsafe_b64encode(signature_bytes).rstrip(b"=").decode("ascii")
                                != signature_text
                            ):
                                raise ValueError("non-canonical base64url")
                            protected = json.loads(protected_bytes)
                        except (ValueError, UnicodeDecodeError, json.JSONDecodeError, binascii.Error) as exc:
                            lint.fail(fixture_path, f"{label} has an invalid protected header or signature: {exc}")
                        else:
                            if not isinstance(protected, dict) or protected.get("alg") not in expected_jws:
                                lint.fail(
                                    fixture_path,
                                    f"{label} protected alg is not an active detached_jws jose_algorithm; "
                                    f"allowed={expected_jws!r}",
                                )
                check_fixture_algorithm_names(child, fixture_path, f"{pointer}/{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                check_fixture_algorithm_names(child, fixture_path, f"{pointer}/{index}")

    for fixture_path in sorted((ARTIFACTS / "fixtures").glob("*.json")):
        fixture = load_json(lint, fixture_path)
        if fixture is not None:
            check_fixture_algorithm_names(fixture, fixture_path)

    dpop_alg = load_json(lint, ARTIFACTS / "schemas" / allowed_alg_property[0])
    dpop_value = json_pointer_get(dpop_alg, allowed_alg_property[1]) if isinstance(dpop_alg, dict) else None
    dpop_const = dpop_value.get("const") if isinstance(dpop_value, dict) else None
    if dpop_const not in expected_jws:
        lint.fail(
            ARTIFACTS / "schemas" / allowed_alg_property[0],
            f"{allowed_alg_property[1]} must use an active jose_algorithm; got {dpop_const!r}",
        )

    applet_path = ARTIFACTS / "schemas" / "applet-package.schema.json"
    applet_schema = load_json(lint, applet_path)
    accepted_http_algorithms = json_pointer_get(
        applet_schema,
        "/$defs/http_message_signature_algorithm/enum",
    ) if isinstance(applet_schema, dict) else None
    if set(accepted_http_algorithms or []) != http_message_signature_algorithms:
        lint.fail(
            applet_path,
            "webhook_auth.accepted_signature_algorithms must exactly match active "
            f"http_message_signature_algorithm mappings: {sorted(http_message_signature_algorithms)!r}",
        )


def check_applet_install_epoch_evidence_carrier(lint: Lint) -> None:
    package_path = ARTIFACTS / "schemas" / "applet-package.schema.json"
    install_path = ARTIFACTS / "schemas" / "applet-install-operations.schema.json"
    authoring_path = ARTIFACTS / "schemas" / "applet-install-authoring.schema.json"
    package = load_json(lint, package_path)
    install = load_json(lint, install_path)
    authoring = load_json(lint, authoring_path)
    if not isinstance(package, dict) or not isinstance(install, dict) or not isinstance(authoring, dict):
        return

    package_properties = package.get("properties")
    if not isinstance(package_properties, dict):
        lint.fail(package_path, "AppletPackage properties must be an object")
    elif "registration_epoch_evidence" in package_properties:
        lint.fail(
            package_path,
            "registration_epoch_evidence must not enter the controller-signed AppletPackage",
        )
    if package.get("additionalProperties") is not False:
        lint.fail(package_path, "AppletPackage must reject unknown evidence placement")
    if "patternProperties" in package:
        lint.fail(package_path, "AppletPackage must not retain a top-level extension escape hatch")

    definitions = install.get("$defs")
    if not isinstance(definitions, dict):
        lint.fail(install_path, "install operation $defs must be an object")
        return
    authoring_defs = authoring.get("$defs")
    if not isinstance(authoring_defs, dict):
        lint.fail(authoring_path, "install authoring $defs must be an object")
        return
    evidence = authoring_defs.get("registration_epoch_evidence")
    if evidence != {"$ref": "./applet-registration-epoch-evidence.schema.json"}:
        lint.fail(
            authoring_path,
            "registration_epoch_evidence must reference the canonical closed evidence schema",
        )

    registration_all_of = authoring_defs.get("registration_event", {}).get("allOf", [])
    registration_overlay = registration_all_of[1] if len(registration_all_of) == 2 else {}
    manifest_evidence_ref = json_pointer_get(
        registration_overlay,
        "/properties/payload/properties/manifest/properties/registration_epoch_evidence/$ref",
    )
    if manifest_evidence_ref != "#/$defs/registration_epoch_evidence":
        lint.fail(
            authoring_path,
            "caller-signed registration Event manifest must be the sole registration_epoch_evidence carrier",
        )

    for definition_name in (
        "applet_install_preview_request_body",
        "applet_install_first_request_body",
        "applet_install_reuse_request_body",
    ):
        request = definitions.get(definition_name)
        properties = request.get("properties") if isinstance(request, dict) else None
        if not isinstance(properties, dict):
            lint.fail(install_path, f"{definition_name} properties must be an object")
            continue
        forbidden = {
            "registration_epoch_evidence",
            "registration_event",
            "capability_grant_events",
            "plan_digest",
            "effective_scope",
            "bot_actor_provision_event",
            "bot_pcr_genesis_event",
            "bot_accountability_grant_event",
            "bot_profile_event",
            "ghost_actor_provision_event",
            "ghost_pcr_genesis_event",
            "ghost_accountability_grant_event",
            "ghost_profile_event",
            "authoring_request_id",
            "requested_at",
            "requested_expires_at",
        }
        mirrored = sorted(forbidden.intersection(properties))
        if mirrored:
            lint.fail(
                install_path,
                f"{definition_name} must not mirror authoring carriers: {mirrored}",
            )

    basis_properties = json_pointer_get(authoring, "/$defs/install_authoring_request_basis/properties")
    if not isinstance(basis_properties, dict):
        lint.fail(authoring_path, "install_authoring_request_basis properties must be an object")
    else:
        if "registration_epoch_evidence" in basis_properties:
            lint.fail(authoring_path, "install_authoring_request_basis must not mirror registration evidence")
        for forbidden_time in ("requested_at", "requested_expires_at"):
            if forbidden_time in basis_properties:
                lint.fail(authoring_path, f"install_authoring_request_basis retains {forbidden_time}")
        for event_field in ("registration_event", "capability_grant_events"):
            if event_field not in basis_properties:
                lint.fail(authoring_path, f"install_authoring_request_basis must uniquely carry {event_field}")

    if "authoring_request_id" in json.dumps(authoring, sort_keys=True):
        lint.fail(authoring_path, "derived authoring_request_id must not exist")

    bundle_required = json_pointer_get(authoring, "/$defs/managed_actor_bundle/required")
    expected_bundle_required = [
        "schema",
        "authoring_request_digest",
        "managed_actor_provision_event",
        "pcr_genesis_event",
        "accountability_grant_event",
        "profile_event",
        "proof",
    ]
    if bundle_required != expected_bundle_required:
        lint.fail(authoring_path, "managed_actor_bundle must use the exact role-neutral field set")


def check_service_kind_registry(lint: Lint) -> None:
    path = ARTIFACTS / "registry" / "service-kind-registry.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return
    if data.get("source_of_truth") is not True:
        lint.fail(path, "source_of_truth must be true")

    contexts = data.get("contexts")
    rows = data.get("service_kinds")
    if not isinstance(contexts, list) or not contexts:
        lint.fail(path, "contexts must be a non-empty array")
        return
    if not isinstance(rows, list) or not rows:
        lint.fail(path, "service_kinds must be a non-empty array")
        return

    historical_description_markers = (
        "before this registry",
        "was absent",
        "registered from",
        "unconstrained string",
        "inline enum",
        "prose list",
        "arkret-rust-sdk",
        "tools/artifact_lint/safety.py",
    )
    description_sources: list[tuple[Path, Any]] = [(path, data)]
    service_describe_path = ARTIFACTS / "schemas" / "service-describe.schema.json"
    service_describe = load_json(lint, service_describe_path)
    if isinstance(service_describe, dict):
        description_sources.append((service_describe_path, service_describe))
    for owner, source in description_sources:
        for json_path, value, key in walk_json(source):
            if key != "description" or not isinstance(value, str):
                continue
            lowered = value.lower()
            for marker in historical_description_markers:
                if marker in lowered:
                    lint.fail(
                        owner,
                        f"{json_path} contains implementation history marker {marker!r}",
                    )

    context_ids: set[str] = set()
    for index, context in enumerate(contexts):
        if not isinstance(context, dict):
            lint.fail(path, f"contexts[{index}] must be an object")
            continue
        context_id = context.get("id")
        if not isinstance(context_id, str) or not context_id:
            lint.fail(path, f"contexts[{index}].id must be a non-empty string")
            continue
        if context_id in context_ids:
            lint.fail(path, f"duplicate context id: {context_id}")
        context_ids.add(context_id)

    # Active canonical ids per context, derived from the rows.
    by_context: dict[str, set[str]] = {context_id: set() for context_id in context_ids}
    canonical_ids: set[str] = set()
    for index, row in enumerate(rows):
        label = f"service_kinds[{index}]"
        if not isinstance(row, dict):
            lint.fail(path, f"{label} must be an object")
            continue
        canonical_id = row.get("canonical_id")
        status = row.get("status")
        valid_in = row.get("valid_in")
        if not isinstance(canonical_id, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", canonical_id or ""):
            lint.fail(path, f"{label}.canonical_id must be lowercase snake_case matching [a-z][a-z0-9_]*")
            continue
        if canonical_id in canonical_ids:
            lint.fail(path, f"duplicate canonical_id: {canonical_id}")
        canonical_ids.add(canonical_id)
        if status not in {"active", "reserved"}:
            lint.fail(path, f"{label}.status must be active or reserved")
            continue
        if not isinstance(valid_in, list) or not valid_in:
            lint.fail(path, f"{label}.valid_in must be a non-empty array")
            continue
        for context_id in valid_in:
            if context_id not in context_ids:
                lint.fail(path, f"{label}.valid_in references unknown context {context_id!r}")
                continue
            if status == "active":
                by_context[context_id].add(context_id and canonical_id)

    # Every declared consumer pointer must match the derived value set exactly.
    for context in contexts:
        if not isinstance(context, dict):
            continue
        context_id = context.get("id")
        if context_id not in by_context:
            continue
        expected = sorted(by_context[context_id])
        if not expected:
            lint.fail(path, f"context {context_id} has no active service_kinds")
            continue
        for consumer in context.get("consumers") or []:
            if not isinstance(consumer, dict):
                lint.fail(path, f"context {context_id} consumers[] entries must be objects")
                continue
            file_ref = consumer.get("file")
            pointer = consumer.get("pointer")
            if not isinstance(file_ref, str) or not isinstance(pointer, str):
                lint.fail(path, f"context {context_id} consumer must declare file and pointer")
                continue
            schema_path = ARTIFACTS / file_ref
            schema = load_schema_document(lint, schema_path)
            actual = json_pointer_get(schema, pointer) if isinstance(schema, dict) else None
            if pointer.endswith("/const"):
                # A const pins a single-value context; it must still be a registered id.
                if len(expected) != 1:
                    lint.fail(
                        schema_path,
                        f"{pointer} is a const but context {context_id} has {len(expected)} active service_kinds",
                    )
                elif actual != expected[0]:
                    lint.fail(
                        schema_path,
                        f"{pointer} must match service-kind-registry {context_id} value {expected[0]!r}",
                    )
                continue
            if sorted(actual or []) != expected:
                lint.fail(
                    schema_path,
                    f"{pointer} must match service-kind-registry {context_id} values {expected}",
                )


def check_mls_pq_suite_registration(lint: Lint) -> None:
    """Every reserved PQ-MLS row must track the current MLS WG suite mapping.

    MLS derives keys with the two-stage Extract/Expand pair, which
    draft-ietf-hpke-pq does not define for single-stage SHAKE KDFs. The MLS WG
    therefore pins HKDF-SHA256 (0x0001) / HKDF-SHA384 (0x0002) as the MLS KDF,
    never the HPKE PQ SHAKE256 KDF 0x0011.
    """
    path = ARTIFACTS / "registry" / "mls-ciphersuite-registry.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return
    rows = data.get("ciphersuites")
    if not isinstance(rows, list):
        lint.fail(path, "ciphersuites must be an array")
        return
    mls_draft = "draft-ietf-mls-pq-ciphersuites-06"
    mls_reference_url = f"https://datatracker.ietf.org/doc/html/{mls_draft}"
    expected_rows = {
        "reserved_pqc_hybrid": {
            "canonical_id": "MLS_128_MLKEM768X25519_AES128GCM_SHA256_Ed25519",
            "rfc9420_id": None,
            "mls_draft": mls_draft,
            "mls_reference_url": mls_reference_url,
            "kem_draft": "draft-ietf-hpke-pq-05",
            "kem_hpke_id": "0x647A",
            "kem_reference_url": "https://datatracker.ietf.org/doc/html/draft-ietf-hpke-pq-05",
            "kdf_hpke_id": "0x0001",
            "aead_hpke_id": "0x0001",
            "transcript_hash": "SHA256",
            "signature_scheme": "ed25519",
            "ietf_recommended": True,
            "construction_draft": "draft-irtf-cfrg-concrete-hybrid-kems-04",
            "construction_reference_url": "https://datatracker.ietf.org/doc/html/draft-irtf-cfrg-concrete-hybrid-kems-04",
            "status": "reserved",
        },
        "reserved_pqc_hybrid_authentication": {
            "canonical_id": "MLS_128_MLKEM768X25519_CHACHA20POLY1305_SHA384_MLDSA44",
            "rfc9420_id": None,
            "mls_draft": mls_draft,
            "mls_reference_url": mls_reference_url,
            "kem_draft": "draft-ietf-hpke-pq-05",
            "kem_hpke_id": "0x647A",
            "kem_reference_url": "https://datatracker.ietf.org/doc/html/draft-ietf-hpke-pq-05",
            "kdf_hpke_id": "0x0002",
            "aead_hpke_id": "0x0003",
            "transcript_hash": "SHA384",
            "signature_scheme": "mldsa44",
            "signature_draft": "draft-ietf-tls-mldsa-05",
            "signature_reference_url": "https://datatracker.ietf.org/doc/html/draft-ietf-tls-mldsa-05",
            "ietf_recommended": True,
            "status": "reserved",
        },
    }
    for role, expected in expected_rows.items():
        matched = [item for item in rows if isinstance(item, dict) and item.get("role") == role]
        if len(matched) != 1:
            lint.fail(path, f"expected exactly one {role} row, found {len(matched)}")
            continue
        row = matched[0]
        for field, value in expected.items():
            if row.get(field) != value:
                lint.fail(path, f"{role} row {field} must be {value!r}, got {row.get(field)!r}")
        requirements = row.get("activation_requirements")
        requirements = requirements if isinstance(requirements, list) else []
        if not any(
            isinstance(entry, str)
            and mls_draft in entry
            and f"KDF {expected['kdf_hpke_id']}" in entry
            and "0x0011 MUST NOT be used as the MLS KDF" in entry
            for entry in requirements
        ):
            lint.fail(
                path,
                f"{role} activation_requirements must pin the {mls_draft} tuple and forbid the single-stage SHAKE KDF 0x0011",
            )
    if any(isinstance(item, dict) and item.get("canonical_id") == "MLS_128_XWING_AES128GCM_SHA256_Ed25519" for item in rows):
        lint.fail(path, "private MLS_128_XWING_AES128GCM_SHA256_Ed25519 alias is forbidden")


def check_action_reference_closure(lint: Lint) -> None:
    """STR-002 / OPT-005: every action declared in capabilities.md §5 (动作集合)
    bullet lists MUST resolve in capability-action-registry.json (the canonical
    action set generated from contract-registry.json). Scope is deliberately
    restricted to the §5 action-declaration bullets (`- `ak.<...>``) so that
    event kinds, grandfathered old names in the §5.0 deviation table, and prose
    `ak.*` tokens elsewhere cannot produce false positives — closing the
    hand-maintained-list drift (e.g. ak.object.read_history) at its root."""
    registry_path = ARTIFACTS / "registry" / "capability-action-registry.json"
    data = load_json(lint, registry_path)
    if not isinstance(data, dict):
        return
    known = {
        a.get("action")
        for a in data.get("actions", [])
        if isinstance(a, dict) and isinstance(a.get("action"), str)
    }
    rows_by_action = {
        a.get("action"): a
        for a in data.get("actions", [])
        if isinstance(a, dict) and isinstance(a.get("action"), str)
    }
    path = SPEC_ROOT / "zh" / "authz" / "capabilities.md"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        lint.fail(path, "capabilities.md not readable for action-reference closure")
        return
    in_section = False
    in_code = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if stripped.startswith("## "):
            # Enter the action catalogue on "## 5." and leave on the next H2.
            in_section = stripped.startswith("## 5.") or stripped.startswith("## 5 ")
            continue
        if not in_section:
            continue
        match = _PROSE_ACTION_BULLET_RE.match(line)
        if not match:
            continue
        action = match.group(1)
        if not _ACTION_TOKEN_RE.match(action):
            continue
        if action in known or action in ALLOWED_PROSE_ACTIONS:
            target_match = _PROSE_ACTION_TARGET_RE.search(line)
            if target_match and action in rows_by_action:
                raw_targets = target_match.group(1).strip().strip("{}")
                prose_targets = sorted(
                    target.strip() for target in raw_targets.split(",") if target.strip()
                )
                registry_targets = sorted(rows_by_action[action].get("target_event_kinds") or [])
                if prose_targets != registry_targets:
                    lint.fail(
                        path,
                        f"capabilities.md §5 action {action!r} declares target={prose_targets} "
                        f"but capability-action-registry.json declares {registry_targets}",
                    )
            continue
        lint.fail(
            path,
            f"capabilities.md §5 declares action {action!r} not present in "
            f"capability-action-registry.json (hand-list drift)",
        )


def check_device_messages_cursor_binding(lint: Lint) -> None:
    """Keep the to-device queue continuation parameter canonical across surfaces."""
    openapi_path = ARTIFACTS / "openapi" / "arkret-service-api.openapi.yaml"
    openapi = load_yaml(lint, openapi_path)
    operation = (
        openapi.get("paths", {}).get("/_arkret/self/device_messages", {}).get("get", {})
        if isinstance(openapi, dict)
        else {}
    )
    parameters = operation.get("parameters", []) if isinstance(operation, dict) else []
    query_names = {
        row.get("name")
        for row in parameters
        if isinstance(row, dict) and row.get("in") == "query" and isinstance(row.get("name"), str)
    }
    for required in ("after", "limit"):
        if required not in query_names:
            lint.fail(openapi_path, f"device_messages GET missing canonical query parameter {required!r}")
    for forbidden in ("from", "start_at"):
        if forbidden in query_names:
            lint.fail(openapi_path, f"device_messages GET exposes forbidden cursor alias {forbidden!r}")

    legacy_patterns = (
        re.compile(r"self/device_messages\?from="),
        re.compile(r"device_messages(?:\.query\.list)?\?from="),
        re.compile(r"query\.from"),
        re.compile(r"device_messages from="),
    )
    for root in (SPEC_ROOT / "zh", ARTIFACTS):
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {".json", ".md", ".yaml", ".yml"}:
                continue
            text = path.read_text(encoding="utf-8")
            for pattern in legacy_patterns:
                if pattern.search(text):
                    lint.fail(path, f"device_messages uses forbidden cursor alias: {pattern.pattern}")


def _registered_enum_values(node: Any) -> list[Any] | None:
    """Return the enum a registered location carries, or None.

    A nullable site spells the enum inside a ``oneOf`` whose other branch is
    ``{"type": "null"}`` (the convention the projection row DTOs already use for
    ``title`` and ``summary``). Resolving that here keeps the registry pointing
    at the property itself, so the registry stays readable and does not have to
    encode branch indices that shift when a schema is edited.
    """

    if not isinstance(node, dict):
        return None
    if isinstance(node.get("enum"), list):
        return node["enum"]
    branches = node.get("oneOf")
    if not isinstance(branches, list):
        return None
    carrying = [b for b in branches if isinstance(b, dict) and isinstance(b.get("enum"), list)]
    if len(carrying) != 1:
        return None
    return carrying[0]["enum"]


def check_repeated_enum_drift(lint: Lint) -> None:
    """Pin enums that v1 spells out at more than one schema location.

    There is no shared enum ``$def`` anywhere under ``artifacts/schemas``: every
    enum is repeated literally at each site, which is the established
    convention. The failure mode that convention has is silent divergence -- a
    value added to the object schema and forgotten in the payload schema yields
    two implementations that disagree while both still validate.

    ``registry/repeated-enum-registry.json`` names the enums that are genuinely
    one enum and every location that must spell them identically. Value set and
    order are both enforced: a reordered copy is drift too, because the registry
    is what a generator would read. A location that no longer carries an enum is
    an error rather than a silent pass, so moving or renaming a property has to
    update the registry instead of quietly dropping coverage.

    A nullable site registers the non-null branch of its ``oneOf`` rather than
    the property itself, so every registered pointer resolves to a bare value
    list. That is also what ``check_naming_conventions`` requires of ``stage``:
    a null inside the enum itself would read as a ninth value on the axis.
    """

    path = ARTIFACTS / "registry" / "repeated-enum-registry.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        lint.fail(path, "repeated-enum-registry.json must be a JSON object")
        return
    entries = data.get("enums")
    if not isinstance(entries, list) or not entries:
        lint.fail(path, "repeated-enum-registry.json: enums MUST be a non-empty list")
        return

    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            lint.fail(path, f"enums[{index}] must be an object")
            continue
        name = entry.get("name")
        values = entry.get("values")
        locations = entry.get("locations")
        if not isinstance(name, str) or not name:
            lint.fail(path, f"enums[{index}] missing name")
            continue
        if not isinstance(values, list) or not values:
            lint.fail(path, f"{name}: values MUST be a non-empty list")
            continue
        if not isinstance(locations, list) or len(locations) < 2:
            lint.fail(
                path,
                f"{name}: locations MUST list at least two sites; a single-site enum needs no registry entry",
            )
            continue
        for location in locations:
            if not isinstance(location, str) or "#" not in location:
                lint.fail(path, f"{name}: location MUST be '<artifact path>#<json pointer>': {location!r}")
                continue
            relative, _, pointer = location.partition("#")
            target = ARTIFACTS / relative
            if not target.is_file():
                lint.fail(path, f"{name}: location file does not exist: {relative}")
                continue
            document = load_json(lint, target)
            node = json_pointer_get(document, pointer)
            if node is None:
                lint.fail(target, f"{name}: registered location no longer resolves: {pointer}")
                continue
            found = _registered_enum_values(node)
            if found is None:
                lint.fail(target, f"{name}: registered location carries no enum: {pointer}")
                continue
            if found != values:
                lint.fail(
                    target,
                    f"{name}: {pointer} enum drifted from the registry; expected {values} got {found}",
                )
