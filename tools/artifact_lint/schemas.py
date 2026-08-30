"""Artifact lint phase 2: schemas."""

from __future__ import annotations

import hashlib

from .core import (
    ARTIFACTS,
    Any,
    DEVICE_ID_PATTERN,
    DID_BARE_PATTERN,
    DID_LEGACY_GREEDY_PATTERN,
    DID_LEGACY_PREFIX_PATTERN,
    DID_URL_PROFILE_PATTERN,
    KIND_PAYLOAD_RENAME_EXEMPTIONS,
    LEGACY_SHARED_PAYLOAD_DISPATCH,
    Lint,
    PAYLOAD_DISPATCH_REF_RE,
    PREIMAGE_EXEMPTION_ID_RE,
    PREIMAGE_EXEMPTION_KINDS,
    PREIMAGE_EXEMPTION_REGISTRY_PATH,
    PREIMAGE_EXEMPTION_ROW_KEYS,
    PREIMAGE_EXEMPTION_SECTION_ANCHOR,
    PREIMAGE_EXEMPTION_SECTION_PATH,
    PREIMAGE_EXEMPTION_STATUS,
    PREIMAGE_FORBIDDEN_DIRECTIONS,
    PREIMAGE_FORWARD_DECLARATION_PHRASES,
    PREIMAGE_IDENTITY_DERIVATION_RE,
    PREIMAGE_IDENTITY_EXACT_NAMES,
    PREIMAGE_IDENTITY_NAME_SUFFIXES,
    PREIMAGE_SELF_REFERENCE_PHRASES,
    PROFILE_ID_RE,
    PROFILE_ID_TOKEN_RE,
    Path,
    ROOT,
    SCHEMA_ID_RE,
    SCHEMA_ID_TOKEN_RE,
    SPEC_ROOT,
    SUPPLY_EXEMPTION_REGISTRY_PATH,
    TRUST_DOMAIN_PATTERN,
    VECTOR_GROUP_ID_RE,
    YAML_REF_RE,
    _FSM_ABSENT,
    _FSM_CONTRACT_KEYS,
    _FSM_TEMPLATE_KEYS,
    _supply_load_exemptions,
    _supply_resolve_ref,
    _supply_schema_files,
    all_json_files,
    canonical_json,
    json,
    load_json,
    load_yaml,
    markdown_files,
    markdown_section_body,
    markdown_section_digest,
    re,
    read_text,
    resolve_json_pointer,
    split_ref,
    walk_json,
)


def check_trust_domain_constraints(lint: Lint) -> None:
    """Require every protocol trust-domain field to resolve to one canonical schema."""
    schema_paths = sorted((ARTIFACTS / "schemas").glob("*.schema.json"))
    schema_docs: dict[str, Any] = {}
    for path in schema_paths:
        data = load_json(lint, path)
        if isinstance(data, dict):
            schema_docs[path.name] = data
    def resolve_terminal(owner_name: str, node: Any) -> Any:
        seen: set[tuple[str, str]] = set()
        while isinstance(node, dict) and isinstance(node.get("$ref"), str):
            ref = node["$ref"]
            file_part, _, fragment = ref.partition("#")
            target_name = owner_name if file_part in ("", ".") else file_part.removeprefix("./")
            if "/" in target_name:
                return None
            key = (target_name, fragment)
            if key in seen:
                return None
            seen.add(key)
            target_doc = schema_docs.get(target_name)
            if target_doc is None:
                return None
            try:
                node = resolve_json_pointer(target_doc, f"#{fragment}" if fragment else "#")
            except KeyError:
                return None
            owner_name = target_name
        return node

    for path in schema_paths:
        data = schema_docs.get(path.name)
        if not isinstance(data, dict):
            continue
        for json_path, value, key in walk_json(data):
            if key != "properties" or not isinstance(value, dict):
                continue
            for field, field_schema in value.items():
                if not (
                    field == "trust_domain"
                    or field == "trust_domain_id"
                    or field.endswith("_trust_domain")
                ):
                    continue
                terminal = resolve_terminal(path.name, field_schema)
                if not isinstance(terminal, dict) or terminal.get("pattern") != TRUST_DOMAIN_PATTERN:
                    lint.fail(
                        path,
                        f"{json_path}.{field} must resolve to "
                        "common-ids.schema.json#/$defs/trust_domain; bare scope aliases are forbidden",
                    )


def check_foundational_schema_dependency_direction(lint: Lint) -> None:
    """Keep foundational lexical schemas below operation DTO schemas."""
    path = ARTIFACTS / "schemas" / "common-ids.schema.json"
    document = load_json(lint, path)
    if not isinstance(document, dict):
        return

    def visit(node: Any, pointer: str) -> None:
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str):
                target = ref.partition("#")[0].removeprefix("./")
                if target.endswith("-operations.schema.json"):
                    lint.fail(
                        path,
                        f"{pointer or '/'} points upward to operation schema {target}; "
                        "canonical lexical terminals belong in common-ids.schema.json",
                    )
            for key, child in node.items():
                visit(child, f"{pointer}/{key}")
        elif isinstance(node, list):
            for index, child in enumerate(node):
                visit(child, f"{pointer}/{index}")

    visit(document, "")



def ensure_relative_file(lint: Lint, owner: Path, base: Path, ref: str, label: str) -> Path | None:
    if ref.startswith("#"):
        # Local fragments are just as capable of drifting as cross-file ones.
        # Validate them against the owning JSON document instead of treating
        # the absence of a file component as success.
        ensure_cross_file_pointer(lint, owner, owner, ref, label)
        return owner
    ref_path = split_ref(ref)
    if not ref_path:
        return None
    target = (base / ref_path).resolve()
    try:
        target.relative_to(ROOT.resolve())
    except ValueError:
        lint.fail(owner, f"{label} escapes repository: {ref}")
        return None
    if not target.exists():
        lint.fail(owner, f"{label} target does not exist: {ref}")
        return target
    ensure_cross_file_pointer(lint, owner, target, ref, label)
    return target


SCHEMA_ANNOTATION_POINTER_RE = re.compile(
    r"(?P<ref>(?:(?:\.\.?/)|(?:[A-Za-z0-9_.-]+/))*"
    r"[A-Za-z0-9_.-]+\.schema\.json#/"
    r"[A-Za-z0-9_$~%./-]*[A-Za-z0-9_$~%/-])"
)


def ensure_schema_annotation_pointers(
    lint: Lint, owner: Path, annotation: str, label: str
) -> None:
    """Resolve machine-recognizable schema pointers in comments and descriptions."""
    for match in SCHEMA_ANNOTATION_POINTER_RE.finditer(annotation):
        ref = match.group("ref")
        try:
            owner.relative_to(ARTIFACTS)
        except ValueError:
            base = owner.parent
        else:
            if ref.startswith("schemas/"):
                base = ARTIFACTS
            elif "/" not in ref.split("#", 1)[0]:
                base = ARTIFACTS / "schemas"
            else:
                base = owner.parent
        ensure_relative_file(lint, owner, base, ref, f"{label} schema pointer")


_STABLE_CORE_ID_FIELDS = {
    "principal_id",
    "actor_id",
    "controller_id",
    "service_id",
    "recipient_principal_id",
    "target_principal_id",
}


_DID_REF_TARGETS = {
    "did",
    "webvh_did",
    "human_principal_did",
    "ephemeral_pairwise_principal_did",
    "did_key_did",
}

_INLINE_DID_KEY_ENCODING_POINTERS = {
    "device-pairing.schema.json#/$defs/device_pairing_target_attestation/properties/device_public_key_did/pattern",
    "keys-operations.schema.json#/$defs/did_key/pattern",
    "realm-genesis.schema.json#/$defs/founding_device_descriptor/properties/device_public_key_did/pattern",
    "event-envelope.schema.json#/$defs/principal_server_admission_proof/properties/producer_signing_key_did/pattern",
}


def check_did_boundary_allowlist(lint: Lint) -> None:
    """Keep DID use at explicit registration, resolution, or method-evidence boundaries."""

    allowlist_path = ROOT / "tools" / "did-boundary-allowlist.json"
    allowlist = load_json(lint, allowlist_path)
    if not isinstance(allowlist, dict):
        return
    categories = set(allowlist.get("categories", []))
    rows = allowlist.get("entries", [])
    if not isinstance(rows, list):
        lint.fail(allowlist_path, "entries must be an array")
        return
    allowed: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            lint.fail(allowlist_path, f"entries[{index}] must be an object")
            continue
        pointer = row.get("pointer")
        category = row.get("category")
        if not isinstance(pointer, str) or not pointer:
            lint.fail(allowlist_path, f"entries[{index}].pointer must be non-empty")
            continue
        if category not in categories:
            lint.fail(allowlist_path, f"{pointer}: unknown category {category!r}")
        if pointer in allowed:
            lint.fail(allowlist_path, f"duplicate DID pointer: {pointer}")
        allowed.add(pointer)

    observed: set[str] = set()
    inline_did_key_encodings: set[str] = set()

    def escape(token: str) -> str:
        return token.replace("~", "~0").replace("/", "~1")

    def visit(owner: Path, value: Any, pointer: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                child_pointer = f"{pointer}/{escape(key)}"
                absolute = f"{owner.name}#{child_pointer}"
                if (
                    key == "$ref"
                    and isinstance(child, str)
                    and child.rsplit("/", 1)[-1] in _DID_REF_TARGETS
                ):
                    forwarding_definition = child_pointer == "/$defs/did/$ref"
                    common_subtype_definition = (
                        owner.name == "common-ids.schema.json"
                        and child_pointer == "/$defs/human_principal_did/$ref"
                    )
                    if not forwarding_definition and not common_subtype_definition:
                        observed.add(absolute)
                if (
                    key == "pattern"
                    and isinstance(child, str)
                    and child.startswith("^did:")
                    and "#" not in child
                    and child not in {r"^did:[a-z0-9]+$", r"^did:[a-z0-9]+:$"}
                    and owner.name != "common-ids.schema.json"
                ):
                    if child.startswith("^did:key:z"):
                        inline_did_key_encodings.add(absolute)
                    else:
                        lint.fail(
                            owner,
                            f"{child_pointer}: DID pattern bypasses the shared registered type",
                        )
                visit(owner, child, child_pointer)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(owner, child, f"{pointer}/{index}")

    for path in sorted((ARTIFACTS / "schemas").glob("*.json")):
        document = load_json(lint, path)
        if isinstance(document, dict):
            visit(path, document, "")

    for pointer in sorted(observed - allowed):
        lint.fail(allowlist_path, f"unreviewed DID use: {pointer}")
    for pointer in sorted(allowed - observed):
        lint.fail(allowlist_path, f"stale DID allowlist entry: {pointer}")
    for pointer in sorted(inline_did_key_encodings - _INLINE_DID_KEY_ENCODING_POINTERS):
        lint.fail(allowlist_path, f"unreviewed inline did:key public-key encoding: {pointer}")
    for pointer in sorted(_INLINE_DID_KEY_ENCODING_POINTERS - inline_did_key_encodings):
        lint.fail(allowlist_path, f"stale inline did:key encoding entry: {pointer}")

    from tools.generate_did_representation_report import build_report

    report_path = ARTIFACTS / "reports" / "did-representation-report.json"
    actual_report = load_json(lint, report_path)
    expected_report = build_report()
    if actual_report != expected_report:
        lint.fail(
            report_path,
            "generated DID representation report is stale; run "
            "python tools/generate_did_representation_report.py",
        )
    entries = expected_report.get("entries", [])
    if isinstance(entries, list):
        name_profiles: dict[str, set[str]] = {}
        for row in entries:
            if not isinstance(row, dict):
                continue
            if row.get("representation_profile") == "ambiguous":
                lint.fail(
                    report_path,
                    f"{row.get('schema_path')}: one property admits multiple DID representations",
                )
            if row.get("semantic_category") == "external_system_identifier":
                continue
            name = row.get("property_name")
            profile = row.get("representation_profile")
            if isinstance(name, str) and isinstance(profile, str):
                name_profiles.setdefault(name, set()).add(profile)
        for name, profiles in sorted(name_profiles.items()):
            if len(profiles) > 1:
                lint.fail(
                    report_path,
                    f"Arkret-owned property {name!r} maps to multiple DID representations: "
                    f"{sorted(profiles)}",
                )

    legacy_tokens = (
        "did" + "_full_id",
        "Did" + "FullId",
        "Bare" + "Did",
        "full" + "_id",
        "full" + "-id",
        "full" + " ID",
        "full" + " DID",
        "full" + "-DID",
    )
    legacy_pattern = re.compile("(?i)(" + "|".join(re.escape(token) for token in legacy_tokens) + ")")
    for root in (SPEC_ROOT, ROOT / "tools", ROOT / "site" / "public"):
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix not in {".json", ".md", ".py", ".yaml", ".yml"}:
                continue
            if path.resolve() == Path(__file__).resolve():
                continue
            match = legacy_pattern.search(read_text(path))
            if match:
                lint.fail(path, f"legacy DID vocabulary is forbidden: {match.group(0)!r}")


def check_stable_identity_fields_use_core_id(lint: Lint) -> None:
    """Stable business identity fields must never regress to bare/DID refs."""
    schema_root = ARTIFACTS / "schemas"
    for path in sorted(schema_root.rglob("*.json")):
        document = load_json(lint, path)
        if not isinstance(document, dict):
            continue
        for json_path, value, key in walk_json(document):
            if key != "properties" or not isinstance(value, dict):
                continue
            for field in sorted(_STABLE_CORE_ID_FIELDS & value.keys()):
                schema = value[field]
                if not isinstance(schema, dict):
                    continue
                refs = [
                    nested_value
                    for _, nested_value, nested_key in walk_json(schema)
                    if nested_key == "$ref" and isinstance(nested_value, str)
                ]
                forbidden_refs = [
                    ref
                    for ref in refs
                    if ref.rsplit("/", 1)[-1] in {
                        "did",
                        "webvh_did",
                        "human_principal_did",
                        "ephemeral_pairwise_principal_did",
                        "did_key_did",
                    }
                ]
                if forbidden_refs:
                    lint.fail(
                        path,
                        f"{json_path}.{field}: stable identity field must reference did_core_id, got {forbidden_refs}",
                    )



def ensure_cross_file_pointer(
    lint: Lint, owner: Path, target: Path, ref: str, label: str
) -> None:
    """Resolve the ``#/...`` fragment of a cross-file ``$ref`` inside the target document.

    Checking only that the *file* exists lets a deleted ``$defs`` entry survive every gate and
    surface much later as a downstream schema-compile failure. Pruning a shared schema is exactly
    when that happens, so the pointer itself is verified here.
    """
    if "#" not in ref or target.suffix != ".json":
        return
    fragment = ref.split("#", 1)[1]
    if not fragment.startswith("/"):
        return
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    node: Any = document
    for raw in fragment.lstrip("/").split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict) and token in node:
            node = node[token]
            continue
        if isinstance(node, list) and token.isdigit() and int(token) < len(node):
            node = node[int(token)]
            continue
        lint.fail(
            owner,
            f"{label} points at a missing location in {target.name}: {ref}",
        )
        return



def check_event_reference_inventory(lint: Lint) -> None:
    path = ARTIFACTS / "reports" / "event-reference-field-inventory.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return
    if data.get("generated_by") != "tools/gen_event_reference_inventory.py":
        lint.fail(path, "Event reference inventory must name its generator")
    rows = data.get("fields", [])
    if not isinstance(rows, list):
        lint.fail(path, "Event reference inventory fields must be an array")
        return
    prev_refs = [
        row for row in rows
        if isinstance(row, dict)
        and row.get("schema") == "event-envelope.schema.json"
        and row.get("field") == "prev_refs"
    ]
    if len(prev_refs) != 1 or prev_refs[0].get("classification") != "complete_event_id":
        lint.fail(path, "event-envelope.prev_refs must be inventoried as complete_event_id")
    valid = {"complete_event_id", "digest_copy_or_commitment", "external_event_namespace"}
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or row.get("classification") not in valid:
            lint.fail(path, f"fields[{index}] has invalid classification")



def check_schema_refs(lint: Lint, known: dict[str, set[str]]) -> None:
    # The current-wire rejection guard intentionally names forbidden fields
    # that are absent from active registries.
    drift_tracking_files = {"forbidden-wire-fields.json"}
    for path in all_json_files():
        data = load_json(lint, path)
        if data is None:
            continue
        schema_ids: set[str] = set()
        profile_ids: set[str] = set()

        def visit(value: Any, json_path: str) -> None:
            if isinstance(value, dict):
                if path.name != "event-envelope-negative-fixture.json":
                    event_id = value.get("event_id")
                    if isinstance(event_id, str):
                        for ref_key in ("prev_refs", "auth_refs"):
                            refs = value.get(ref_key)
                            if isinstance(refs, list) and event_id in refs:
                                lint.fail(
                                    path,
                                    f"{json_path}.{ref_key} contains its own event_id {event_id}",
                                )
                for key, child in value.items():
                    child_path = f"{json_path}.{key}"
                    schema_ids.update(SCHEMA_ID_TOKEN_RE.findall(key))
                    profile_ids.update(PROFILE_ID_TOKEN_RE.findall(key))
                    if key == "$ref" and isinstance(child, str):
                        ensure_relative_file(
                            lint, path, path.parent, child, f"{child_path} $ref"
                        )
                    if key in {"$comment", "description"} and isinstance(child, str):
                        ensure_schema_annotation_pointers(lint, path, child, child_path)
                    visit(child, child_path)
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    visit(child, f"{json_path}[{index}]")
            elif isinstance(value, str):
                schema_ids.update(SCHEMA_ID_TOKEN_RE.findall(value))
                profile_ids.update(PROFILE_ID_TOKEN_RE.findall(value))

        visit(data, "$")
        if path.name in drift_tracking_files:
            continue
        # This KAT carries the input to ak.schema.define, so its schema ids are
        # definitions under test rather than references to the current registry.
        if path.name != "schema-definition-validator-kat.json":
            for schema_id in schema_ids:
                if schema_id not in known["schema_ids"]:
                    lint.fail(path, f"unknown schema id reference: {schema_id}")
        for profile_id in profile_ids:
            if profile_id not in known["profiles"]:
                lint.fail(path, f"unknown profile reference: {profile_id}")

    for yaml_path in sorted((ARTIFACTS / "openapi").glob("*.yaml")) + sorted((ARTIFACTS / "bindings").glob("*.yaml")):
        text = yaml_path.read_text(encoding="utf-8")
        for ref in YAML_REF_RE.findall(text):
            ensure_relative_file(lint, yaml_path, yaml_path.parent, ref, "$ref")
        for schema_id in SCHEMA_ID_TOKEN_RE.findall(text):
            if schema_id not in known["schema_ids"]:
                lint.fail(yaml_path, f"unknown schema id reference: {schema_id}")
        for profile_id in PROFILE_ID_TOKEN_RE.findall(text):
            if profile_id not in known["profiles"]:
                lint.fail(yaml_path, f"unknown profile reference: {profile_id}")



def check_security_transaction_schema_closure(lint: Lint) -> None:
    """Require canonical transaction intent/progress and closed prepared material."""
    path = ARTIFACTS / "schemas" / "security-transaction.schema.json"
    data = load_json(lint, path)
    defs = data.get("$defs") if isinstance(data, dict) else None
    if not isinstance(defs, dict):
        lint.fail(path, "security transaction schema must define $defs")
        return

    expected_orders = {
        "pcr_policy_recovery": (
            "pcr_policy",
            ["submit_reanchor_unit", "issue_terminal_receipt"],
        ),
        "security_rotation": (
            "security_rotation",
            [
            "revoke",
            "upload_new_material",
            "switch_authoritative_pointer",
            "erase_old_material",
            "local_commit",
            ],
        ),
    }
    for prefix, (accepted_prefix, expected) in expected_orders.items():
        step_def = defs.get(f"{prefix}_step")
        actual = step_def.get("enum") if isinstance(step_def, dict) else None
        if actual != expected:
            lint.fail(path, f"$defs/{prefix}_step must declare the canonical order {expected}")
        accepted = defs.get(f"{accepted_prefix}_accepted_steps")
        if not isinstance(accepted, dict):
            lint.fail(path, f"missing $defs/{accepted_prefix}_accepted_steps")
            continue
        if accepted.get("maxItems") != len(expected):
            lint.fail(path, f"$defs/{accepted_prefix}_accepted_steps maxItems must equal step count")
        if accepted.get("items") != {"$ref": "#/$defs/accepted_step"}:
            lint.fail(path, f"$defs/{accepted_prefix}_accepted_steps must use the sole accepted_step shape")
        if "prefixItems" in accepted:
            lint.fail(path, f"$defs/{accepted_prefix}_accepted_steps must not duplicate step labels by position")

    accepted_step = defs.get("accepted_step")
    accepted_required = accepted_step.get("required") if isinstance(accepted_step, dict) else None
    accepted_properties = accepted_step.get("properties") if isinstance(accepted_step, dict) else None
    if not isinstance(accepted_required, list) or "step" in accepted_required:
        lint.fail(path, "$defs/accepted_step must not require a derived step label")
    if not isinstance(accepted_properties, dict) or "step" in accepted_properties:
        lint.fail(path, "$defs/accepted_step must not define a derived step label")
    if any(name.startswith("accepted_") and name != "accepted_step" for name in defs):
        lint.fail(path, "per-step accepted wrapper definitions are forbidden")

    resource_required = data.get("required", [])
    resource_properties = data.get("properties", {})
    if any(value == "awaiting_device_attestation" for _, value, _ in walk_json(data)):
        lint.fail(path, "transaction schema must not serialize derived device-attestation readiness")
    for derived in ("binding", "next_required_step", "state"):
        if derived in resource_required or derived in resource_properties:
            lint.fail(path, f"transaction resource must not serialize derived {derived}")

    for create_name in ("recovery_create_request", "security_rotation_create_request"):
        create = defs.get(create_name)
        required = create.get("required", []) if isinstance(create, dict) else []
        properties = create.get("properties", {}) if isinstance(create, dict) else {}
        for derived in ("binding", "prepared_plan_digest"):
            if derived in required or derived in properties:
                lint.fail(path, f"$defs/{create_name} must not accept caller-supplied {derived}")

    recovery_plan = defs.get("pcr_policy_recovery_plan")
    recovery_required = recovery_plan.get("required", []) if isinstance(recovery_plan, dict) else []
    recovery_properties = recovery_plan.get("properties", {}) if isinstance(recovery_plan, dict) else {}
    if recovery_properties.get("binding") != {"$ref": "#/$defs/pcr_policy_recovery_binding"}:
        lint.fail(path, "$defs/pcr_policy_recovery_plan must own its closed binding")
    if "binding" not in recovery_required or "identity_model" in recovery_properties:
        lint.fail(path, "PCR recovery identity_model must appear only inside prepared_plan.binding")
    if "security_rotation_binding" in defs:
        lint.fail(path, "top-level security_rotation_binding schema is a forbidden plan projection")

    prepared_unit = defs.get("prepared_event_unit")
    prepared_required = prepared_unit.get("required") if isinstance(prepared_unit, dict) else None
    prepared_properties = prepared_unit.get("properties") if isinstance(prepared_unit, dict) else None
    expected_prepared_fields = {"request", "request_digest"}
    if not isinstance(prepared_required, list) or set(prepared_required) != expected_prepared_fields:
        lint.fail(path, "$defs/prepared_event_unit must require only request and request_digest")
    if not isinstance(prepared_properties, dict) or set(prepared_properties) != expected_prepared_fields:
        lint.fail(path, "$defs/prepared_event_unit must define only request and request_digest")

    continue_request = defs.get("continue_request")
    continue_required = continue_request.get("required", []) if isinstance(continue_request, dict) else []
    continue_properties = continue_request.get("properties", {}) if isinstance(continue_request, dict) else {}
    if "expected_accepted_step_count" not in continue_required:
        lint.fail(path, "$defs/continue_request must require expected_accepted_step_count CAS")
    if "expected_next_step" in continue_required or "expected_next_step" in continue_properties:
        lint.fail(path, "$defs/continue_request must not accept a derived expected_next_step")

    plan_refs: set[str] = set()
    for def_name, definition in defs.items():
        if not def_name.endswith("_plan"):
            continue
        plan_refs.update(
            value
            for _, value, key in walk_json(definition)
            if key == "$ref" and isinstance(value, str)
        )
    for def_name in sorted(defs):
        if def_name.startswith("prepared_") and f"#/$defs/{def_name}" not in plan_refs:
            lint.fail(
                path,
                f"orphan prepared material $defs/{def_name} is not referenced by any plan",
            )


def check_canonical_wire_source_closure(lint: Lint) -> None:
    """Reject reintroduction of Event-draft and device-pairing wire mirrors."""
    schema_dir = ARTIFACTS / "schemas"
    principal_path = schema_dir / "principal-operations.schema.json"
    contact_path = schema_dir / "contact-operations.schema.json"
    agent_path = schema_dir / "agent-operations.schema.json"
    cleanup_path = schema_dir / "agent-membership-cascade.schema.json"
    account_data_path = schema_dir / "account-data-encrypted-value.schema.json"
    receipt_path = schema_dir / "event-batch-receipt.schema.json"
    key_backup_path = schema_dir / "key-backup.schema.json"
    active_series_path = schema_dir / "key-backup-active-series.schema.json"
    governance_path = schema_dir / "mls-governance-proof-bundle.schema.json"
    principal = load_json(lint, principal_path)
    contact = load_json(lint, contact_path)
    agent = load_json(lint, agent_path)
    cleanup = load_json(lint, cleanup_path)
    account_data = load_json(lint, account_data_path)
    receipt = load_json(lint, receipt_path)
    key_backup = load_json(lint, key_backup_path)
    active_series = load_json(lint, active_series_path)
    governance = load_json(lint, governance_path)
    if not all(isinstance(value, dict) for value in (
        principal,
        contact,
        agent,
        cleanup,
        account_data,
        receipt,
        key_backup,
        active_series,
        governance,
    )):
        return

    principal_defs = principal.get("$defs", {})
    draft = principal_defs.get("prepared_event_draft") if isinstance(principal_defs, dict) else None
    draft_required = draft.get("required") if isinstance(draft, dict) else None
    draft_properties = draft.get("properties") if isinstance(draft, dict) else None
    expected_draft_fields = {"unsigned_event_bytes", "event_digest"}
    if not isinstance(draft_required, list) or set(draft_required) != expected_draft_fields:
        lint.fail(principal_path, "$defs/prepared_event_draft must require only bytes and typed digest")
    if not isinstance(draft_properties, dict) or set(draft_properties) != expected_draft_fields:
        lint.fail(principal_path, "$defs/prepared_event_draft must define only bytes and typed digest")
    if isinstance(principal_defs, dict) and "sidecar_prepared_event_draft" in principal_defs:
        lint.fail(principal_path, "Sidecar must use the sole generic prepared_event_draft")

    contact_defs = contact.get("$defs", {})
    if isinstance(contact_defs, dict) and "contact_prepared_event_draft" in contact_defs:
        lint.fail(contact_path, "Contact must use the sole generic prepared_event_draft")
    contact_refs = {
        value
        for _, value, key in walk_json(contact)
        if key == "$ref" and isinstance(value, str) and "prepared_event_draft" in value
    }
    expected_ref = "./principal-operations.schema.json#/$defs/prepared_event_draft"
    if contact_refs != {expected_ref}:
        lint.fail(contact_path, "all Contact prepared drafts must reference the generic draft schema")
    contact_outcome = contact_defs.get("contact_operation_outcome") if isinstance(contact_defs, dict) else None
    contact_branches = contact_outcome.get("oneOf", []) if isinstance(contact_outcome, dict) else []
    prepared_contact_branches = [
        branch
        for branch in contact_branches
        if isinstance(branch, dict)
        and isinstance(branch.get("properties"), dict)
        and branch["properties"].get("status", {}).get("const") == "prepared"
    ]
    if len(prepared_contact_branches) != 5:
        lint.fail(contact_path, "Contact outcome must define exactly five prepared branches")
    for branch in prepared_contact_branches:
        if branch["properties"].get("event_draft") != {"$ref": expected_ref}:
            lint.fail(contact_path, "Contact prepared event_draft must be the direct generic draft reference")

    cleanup_defs = cleanup.get("$defs", {})
    cleanup_record = cleanup_defs.get("agent_cleanup_record") if isinstance(cleanup_defs, dict) else None
    cleanup_required = set(cleanup_record.get("required", [])) if isinstance(cleanup_record, dict) else set()
    cleanup_properties = set(cleanup_record.get("properties", {})) if isinstance(cleanup_record, dict) else set()
    if isinstance(cleanup_defs, dict) and "agent_cleanup_pending_record" in cleanup_defs:
        lint.fail(cleanup_path, "agent cleanup must not retain the obsolete pending-record wire name")
    if "status" in cleanup_required or "status" in cleanup_properties:
        lint.fail(cleanup_path, "agent cleanup must derive status from deadline and completion evidence")

    account_required = set(account_data.get("required", []))
    account_properties = set(account_data.get("properties", {}))
    duplicated_account_digests = sorted(
        {"aad_digest", "ciphertext_digest"} & (account_required | account_properties)
    )
    if duplicated_account_digests:
        lint.fail(account_data_path, f"account-data envelope duplicates local digests {duplicated_account_digests}")

    receipt_defs = receipt.get("$defs", {})
    receipt_item = receipt_defs.get("event_receipt_item") if isinstance(receipt_defs, dict) else None
    receipt_required = set(receipt_item.get("required", [])) if isinstance(receipt_item, dict) else set()
    receipt_properties = set(receipt_item.get("properties", {})) if isinstance(receipt_item, dict) else set()
    if "event_digest" in receipt_required or "event_digest" in receipt_properties:
        lint.fail(receipt_path, "event receipt item must derive event_digest from event_id")
    receipt_required_root = set(receipt.get("required", []))
    receipt_properties_root = set(receipt.get("properties", {}))
    if "frontier" in receipt_required_root or "frontier" in receipt_properties_root:
        lint.fail(
            receipt_path,
            "Event Batch Receipt must not claim an unscoped partial frontier; use typed frontier contracts",
        )
    for scope_name, derived_fields in (
        ("device_reanchor_scope", {"reanchor_digest", "replacement_authorize_digest"}),
        ("pcr_genesis_scope", {"create_digest", "founding_authorize_digest"}),
    ):
        scope = receipt_defs.get(scope_name) if isinstance(receipt_defs, dict) else None
        scope_required = set(scope.get("required", [])) if isinstance(scope, dict) else set()
        scope_properties = set(scope.get("properties", {})) if isinstance(scope, dict) else set()
        duplicated = sorted(derived_fields & (scope_required | scope_properties))
        if duplicated:
            lint.fail(
                receipt_path,
                f"{scope_name} must derive typed Event digests from events[].event_id, found {duplicated}",
            )

    generation_ref = "./recovery-session.schema.json#/$defs/pcr_generation_ref"
    backup_frontier = key_backup.get("properties", {}).get("frontier_ref", {})
    series_frontier = active_series.get("$defs", {}).get("frontier_ref", {})
    for path, frontier in (
        (key_backup_path, backup_frontier),
        (active_series_path, series_frontier),
    ):
        field = frontier.get("properties", {}).get("device_generation_ref", {})
        if field.get("$ref") != generation_ref:
            lint.fail(
                path,
                "frontier_ref.device_generation_ref must reuse the canonical PCR generation integer",
            )

    governance_defs = governance.get("$defs", {})
    proof_material = governance_defs.get("typed_proof_material") if isinstance(governance_defs, dict) else None
    proof_properties = proof_material.get("properties", {}) if isinstance(proof_material, dict) else {}
    descriptors = proof_properties.get("event_ids") if isinstance(proof_properties, dict) else None
    descriptor = descriptors.get("items") if isinstance(descriptors, dict) else None
    expected_event_id_ref = {"$ref": "./common-ids.schema.json#/$defs/event_id"}
    if descriptor != expected_event_id_ref:
        lint.fail(governance_path, "MLS governance event_ids must be the direct EventId set")
    if isinstance(proof_properties, dict) and "event_descriptors" in proof_properties:
        lint.fail(governance_path, "MLS governance must not retain the obsolete event_descriptors name")

    sidecar_outcome = principal_defs.get("sidecar_ensure_outcome") if isinstance(principal_defs, dict) else None
    branches = sidecar_outcome.get("oneOf", []) if isinstance(sidecar_outcome, dict) else []
    prepared_branches = [
        branch
        for branch in branches
        if isinstance(branch, dict)
        and isinstance(branch.get("properties"), dict)
        and branch["properties"].get("status", {}).get("const") == "prepared"
    ]
    for branch in prepared_branches:
        branch_name = branch["properties"].get("branch", {}).get("const")
        forbidden = {"create_event_id", "context_attach_event_id"}
        if branch_name == "new":
            forbidden.add("sidecar_id")
        required = set(branch.get("required", []))
        properties = set(branch.get("properties", {}))
        duplicated = sorted(forbidden & (required | properties))
        if duplicated:
            lint.fail(principal_path, f"Sidecar {branch_name} prepare duplicates derived fields {duplicated}")

    agent_defs = agent.get("$defs", {})
    pair = agent_defs.get("account_device_pair_request_body") if isinstance(agent_defs, dict) else None
    pair_required = set(pair.get("required", [])) if isinstance(pair, dict) else set()
    pair_properties = set(pair.get("properties", {})) if isinstance(pair, dict) else set()
    duplicated_pair_fields = sorted({"hpke_key", "device_signature"} & (pair_required | pair_properties))
    if duplicated_pair_fields:
        lint.fail(agent_path, f"device pair commit duplicates signed payload fields {duplicated_pair_fields}")
    for retained in ("new_device_pubkey", "challenge_proof", "authorize_event"):
        if retained not in pair_required or retained not in pair_properties:
            lint.fail(agent_path, f"device pair commit must retain required {retained}")


def check_agent_runtime_scope_registry(lint: Lint, known: dict[str, set[str]]) -> None:
    path = ARTIFACTS / "registry" / "agent-runtime-scope-registry.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return

    expected_layers = {
        "provision": "agent_provision_scope_migration_required",
        "key_authorization": "agent_key_scope_reauthorization_required",
        "session": "agent_session_scope_refresh_required",
    }
    layers = data.get("layers")
    observed_layers = {
        row.get("layer"): row.get("missing_reason")
        for row in layers or []
        if isinstance(row, dict)
    }
    if observed_layers != expected_layers:
        lint.fail(path, f"layers must equal the closed three-layer migration map: {expected_layers}")

    capability_sets = data.get("capability_sets") or {}
    interactive = set((capability_sets.get("interactive_chat") or {}).get("mandatory_operations") or [])
    e2ee = set((capability_sets.get("e2ee") or {}).get("mandatory_operations") or [])
    expected_interactive = {
        "ak.self.events.stream.subscribe.v1",
        "ak.self.events.read.scan.v1",
        "ak.self.events.read.frontier.v1",
        "ak.self.seals.read.frontier.v1",
        "ak.self.events.command.submit.v1",
    }
    expected_e2ee = {"ak.self.keys.keypackages.upload.create.v1"}
    if interactive != expected_interactive:
        lint.fail(path, f"interactive_chat mandatory operations drift: {sorted(interactive)}")
    if e2ee != expected_e2ee:
        lint.fail(path, f"e2ee mandatory operations drift: {sorted(e2ee)}")
    for operation_id in sorted(interactive | e2ee):
        if operation_id not in known["operation_ids"]:
            lint.fail(path, f"unknown mandatory operation: {operation_id}")

    profiles_path = ARTIFACTS / "profiles" / "conformance-profiles.json"
    profiles = load_json(lint, profiles_path) or {}
    requirements = profiles.get("profile_requirements") or {}
    core_endpoints = {
        row.get("operation_id")
        for row in (requirements.get("ak.profile.core_event_store.v1") or {}).get("operation_requirements", [])
        if isinstance(row, dict)
    }
    if "ak.self.seals.read.frontier.v1" not in core_endpoints:
        lint.fail(profiles_path, "core_event_store must require the Seal frontier operation")
    child_endpoints = (requirements.get("ak.profile.principal_server_events_api.v1") or {}).get("operation_requirements")
    if child_endpoints != []:
        lint.fail(profiles_path, "principal_server_events_api must inherit the parent endpoint set without duplicating it")
    runtime_endpoints = {
        row.get("operation_id")
        for row in (requirements.get("ak.profile.agent_runtime.v1") or {}).get("operation_requirements", [])
        if isinstance(row, dict)
    }
    required_runtime = interactive | expected_e2ee
    if not required_runtime <= runtime_endpoints:
        lint.fail(profiles_path, f"agent_runtime missing mandatory operations: {sorted(required_runtime - runtime_endpoints)}")


def check_profile_requirements(lint: Lint, known: dict[str, set[str]]) -> None:
    path = ARTIFACTS / "profiles" / "conformance-profiles.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return

    requirements = data.get("profile_requirements")
    if not isinstance(requirements, dict):
        lint.fail(path, "missing profile_requirements matrix")
        return

    declared_profiles: set[str] = set()
    for key in (
        "implementation_profiles",
        "identity_extension_profiles",
        "deployment_profiles",
        "hardening_profiles",
    ):
        values = data.get(key, [])
        if isinstance(values, list):
            declared_profiles.update(item for item in values if isinstance(item, str) and item.startswith("ak.profile."))

    for profile_id in sorted(declared_profiles - set(requirements.keys())):
        lint.fail(path, f"profile_requirements missing declared profile: {profile_id}")

    fixture_files = {fixture.name for fixture in (ARTIFACTS / "fixtures").glob("*.json")}
    fixture_documents = {
        fixture.name: load_json(lint, fixture)
        for fixture in (ARTIFACTS / "fixtures").glob("*.json")
    }
    vector_registry = load_json(lint, ARTIFACTS / "registry" / "vector-registry.json")
    feature_registry = load_json(lint, ARTIFACTS / "registry" / "feature-registry.json")
    registered_features = {
        row.get("feature_id")
        for row in (feature_registry or {}).get("features", [])
        if isinstance(row, dict) and isinstance(row.get("feature_id"), str)
    }
    event_payload_schema_path = ARTIFACTS / "schemas" / "event-payload.schema.json"
    event_payload_schema = load_json(lint, event_payload_schema_path)
    applet_registration_payload = (
        event_payload_schema.get("$defs", {}).get("applet_registration_payload", {})
        if isinstance(event_payload_schema, dict)
        else {}
    )
    vector_ids = {
        row.get("vector_id")
        for row in (vector_registry or {}).get("vectors", [])
        if isinstance(row, dict) and isinstance(row.get("vector_id"), str)
    }
    required_keys = {
        "enforcement_phases",
        "operation_requirements",
        "required_event_kinds",
        "rejected_event_kinds",
        "required_schemas",
        "required_fixtures",
        "optional_extensions",
        "feature_discovery",
    }

    for profile_id, requirement in requirements.items():
        if profile_id not in known["profiles"]:
            lint.fail(path, f"profile_requirements key is not a declared profile id: {profile_id}")
        if not isinstance(requirement, dict):
            lint.fail(path, f"{profile_id} requirement must be an object")
            continue
        if "summary" in requirement:
            lint.fail(path, f"{profile_id} uses summary for profile metadata; use description")
        for missing_key in sorted(required_keys - set(requirement.keys())):
            lint.fail(path, f"{profile_id} missing {missing_key}")

        for inherited in requirement.get("inherits", []):
            if inherited not in known["profiles"]:
                lint.fail(path, f"{profile_id} inherits unknown profile: {inherited}")

        phases = requirement.get("enforcement_phases")
        allowed_phases = {
            "build",
            "conformance",
            "startup_claim_guard",
            "peer_eligibility",
            "runtime_negotiation",
            "runtime_admission",
        }
        if not isinstance(phases, list) or not phases or len(phases) != len(set(phases)):
            lint.fail(path, f"{profile_id} enforcement_phases must be a non-empty unique array")
            phases = []
        for phase in phases:
            if phase not in allowed_phases:
                lint.fail(path, f"{profile_id} has unknown enforcement phase: {phase!r}")
        if {"runtime_negotiation", "runtime_admission"}.intersection(phases):
            for field in ("wire_selector_refs", "normative_effect_refs"):
                refs = requirement.get(field)
                if not isinstance(refs, list) or not refs or not all(
                    isinstance(ref, str) and ref for ref in refs
                ):
                    lint.fail(path, f"{profile_id} runtime enforcement requires non-empty {field}")

        operation_requirements = requirement.get("operation_requirements")
        if not isinstance(operation_requirements, list):
            lint.fail(path, f"{profile_id} operation_requirements must be an array")
            operation_requirements = []
        seen_operation_requirements: set[tuple[str, str, str]] = set()
        for index, operation_requirement in enumerate(operation_requirements):
            label = f"{profile_id}.operation_requirements[{index}]"
            if not isinstance(operation_requirement, dict) or set(operation_requirement) != {
                "direction",
                "operation_id",
                "binding_kind",
            }:
                lint.fail(path, f"{label} must use the closed direction/operation_id/binding_kind shape")
                continue
            direction = operation_requirement.get("direction")
            operation_id = operation_requirement.get("operation_id")
            binding_kind = operation_requirement.get("binding_kind")
            if direction not in {"provide", "consume"}:
                lint.fail(path, f"{label}.direction must be provide or consume")
            if operation_id not in known["operation_ids"]:
                lint.fail(path, f"{label} requires unknown operation_id: {operation_id}")
            if binding_kind not in {"http_json", "websocket", "tus"}:
                lint.fail(path, f"{label} has unknown binding_kind: {binding_kind}")
            identity = (str(direction), str(operation_id), str(binding_kind))
            if identity in seen_operation_requirements:
                lint.fail(path, f"{label} duplicates {identity}")
            seen_operation_requirements.add(identity)

        for event_kind in requirement.get("required_event_kinds", []):
            if isinstance(event_kind, str) and event_kind.startswith("wire_scope:"):
                continue
            if event_kind not in known["event_kinds"]:
                lint.fail(path, f"{profile_id} requires unknown Event.kind: {event_kind}")

        for event_kind in requirement.get("rejected_event_kinds", []):
            if isinstance(event_kind, str) and event_kind.startswith("wire_scope:"):
                scope = event_kind.split(":", 1)[1]
                if scope not in {"durable_event", "actor_private_event"}:
                    lint.fail(path, f"{profile_id} rejects unknown wire_scope: {event_kind}")
                continue
            if event_kind not in known["event_kinds"]:
                lint.fail(path, f"{profile_id} rejects unknown Event.kind: {event_kind}")

        for schema_id in requirement.get("required_schemas", []):
            if schema_id not in known["schema_ids"]:
                lint.fail(path, f"{profile_id} requires unknown schema: {schema_id}")

        required_features = requirement.get("required_features", [])
        if (
            not isinstance(required_features, list)
            or any(not isinstance(item, str) for item in required_features)
            or len(required_features) != len(set(required_features))
        ):
            lint.fail(path, f"{profile_id} required_features must be a unique array")
        else:
            for feature_id in required_features:
                if feature_id not in registered_features:
                    lint.fail(path, f"{profile_id} requires unregistered feature: {feature_id!r}")

        for constraint_kind in requirement.get("required_constraint_kinds", []):
            if constraint_kind not in known["constraint_types"]:
                lint.fail(path, f"{profile_id} requires invalid constraint_kind: {constraint_kind}")

        if "owner_grant_authority_actions" in requirement:
            lint.fail(
                path,
                f"{profile_id}: owner_grant_authority_actions is retired; a profile action "
                "is owner-grantable only when the reducer profile's compiled "
                "ak.realm.owner grant_authority_rule includes that exact action "
                "(capabilities.md section 3.2)",
            )

        authority_rule_keys = {
            "issuer_action",
            "issuer_owner_authority_allowed",
            "grantable_action",
            "required_registration_event_kind",
            "required_claimed_profile",
            "required_constraint_kind",
            "required_constraint_subkind",
            "subject_binding",
            "scope_binding",
            "epoch_binding",
            "requested_action_binding",
        }
        for index, rule in enumerate(requirement.get("non_event_grant_authority_rules", [])):
            label = f"{profile_id}.non_event_grant_authority_rules[{index}]"
            if not isinstance(rule, dict) or set(rule.keys()) != authority_rule_keys:
                lint.fail(path, f"{label} must use the closed non-event authority rule shape")
                continue
            if rule.get("issuer_action") not in known["capability_actions"]:
                lint.fail(path, f"{label} issuer_action is not registered")
            if not isinstance(rule.get("issuer_owner_authority_allowed"), bool):
                lint.fail(path, f"{label}.issuer_owner_authority_allowed must be a boolean")
            if rule.get("grantable_action") not in known["capability_actions"]:
                lint.fail(path, f"{label} grantable_action is not registered")
            if rule.get("required_registration_event_kind") not in known["event_kinds"]:
                lint.fail(path, f"{label} required_registration_event_kind is not registered")
            if rule.get("required_claimed_profile") not in known["profiles"]:
                lint.fail(path, f"{label} required_claimed_profile is not registered")
            if rule.get("required_constraint_kind") not in known["constraint_types"]:
                lint.fail(path, f"{label} required_constraint_kind is not registered")
            if rule.get("required_constraint_subkind") != "applet_authority":
                lint.fail(path, f"{label} uses an unsupported constraint subkind")
            expected_bindings = {
                "subject_binding": "registration.service_id",
                "scope_binding": "grant.resource_exact_registration_scope",
                "epoch_binding": "constraint.registration_epoch_exact_registration",
                "requested_action_binding": "grant.action_in_registration.requested_scopes",
            }
            for field, expected in expected_bindings.items():
                if rule.get(field) != expected:
                    lint.fail(path, f"{label}.{field} must equal {expected}")
            if rule.get("required_registration_event_kind") == "ak.applet.registration":
                registration_required = applet_registration_payload.get("required", [])
                registration_properties = applet_registration_payload.get("properties", {})
                if "claimed_profiles" not in registration_required:
                    lint.fail(
                        event_payload_schema_path,
                        f"{label} requires durable claimed_profiles but applet registration does not require it",
                    )
                if "claimed_profiles" not in registration_properties:
                    lint.fail(
                        event_payload_schema_path,
                        f"{label} requires durable claimed_profiles but applet registration does not define it",
                    )

        for fixture in requirement.get("required_fixtures", []):
            if fixture not in fixture_files:
                lint.fail(path, f"{profile_id} requires missing fixture: {fixture}")

        for vector_id in requirement.get("required_vectors", []):
            if vector_id not in vector_ids:
                lint.fail(path, f"{profile_id} requires unknown vector: {vector_id}")

        for runner_suite in requirement.get("required_runner_suites", []):
            if not isinstance(runner_suite, dict):
                lint.fail(path, f"{profile_id} required_runner_suites entry must be an object")
                continue
            suite = runner_suite.get("suite")
            fixture = runner_suite.get("artifact_fixture")
            entrypoint = runner_suite.get("entrypoint")
            if not isinstance(suite, str) or not suite:
                lint.fail(path, f"{profile_id} runner suite requires non-empty suite")
                continue
            if not isinstance(fixture, str) or fixture not in fixture_documents:
                lint.fail(path, f"{profile_id} runner suite references missing fixture: {fixture!r}")
                continue
            fixture_document = fixture_documents[fixture]
            if not isinstance(fixture_document, dict) or fixture_document.get("suite") != suite:
                lint.fail(path, f"{profile_id} runner suite {suite!r} does not match {fixture}")
                continue
            fixture_runner = fixture_document.get("runner")
            if not isinstance(fixture_runner, dict):
                lint.fail(path, f"{profile_id} runner suite fixture {fixture} has no runner")
                continue
            if entrypoint is not None and fixture_runner.get("entrypoint") != entrypoint:
                lint.fail(path, f"{profile_id} runner suite entrypoint does not match {fixture}")

        feature_discovery = requirement.get("feature_discovery")
        if not isinstance(feature_discovery, dict):
            lint.fail(path, f"{profile_id} feature_discovery must be an object")
        else:
            assertions = feature_discovery.get("required")
            if not isinstance(assertions, list):
                lint.fail(path, f"{profile_id} feature_discovery.required must be a list")
            elif any(isinstance(item, str) and item.startswith("ak.feature.") for item in assertions):
                lint.fail(
                    path,
                    f"{profile_id} feature_discovery.required must contain conformance assertion names, "
                    "not feature IDs; use top-level required_features",
                )
            if not isinstance(feature_discovery.get("unsupported_optional"), str):
                lint.fail(path, f"{profile_id} feature_discovery.unsupported_optional must be a string")



def check_keypackage_claim_unsigned_projection(lint: Lint) -> None:
    schema_path = ARTIFACTS / "schemas" / "keypackage-operations.schema.json"
    data = load_json(lint, schema_path)
    defs = data.get("$defs", {}) if isinstance(data, dict) else {}
    signed = defs.get("keypackages_claim_request_body", {}) if isinstance(defs, dict) else {}
    unsigned = defs.get("peer_keypackages_claim_unsigned_request", {}) if isinstance(defs, dict) else {}
    if not isinstance(signed, dict) or not isinstance(unsigned, dict):
        lint.fail(schema_path, "KeyPackage claim signed and unsigned request definitions must exist")
        return

    transport_members = {"service_binding", "requester_authorization"}
    signed_properties = signed.get("properties", {})
    unsigned_properties = unsigned.get("properties", {})
    if not isinstance(signed_properties, dict) or not isinstance(unsigned_properties, dict):
        lint.fail(schema_path, "KeyPackage claim request properties must be objects")
        return
    projected_properties = {
        key: value for key, value in signed_properties.items() if key not in transport_members
    }
    if projected_properties != unsigned_properties:
        lint.fail(
            schema_path,
            "peer_keypackages_claim_unsigned_request properties must equal the signed claim request projection with only service_binding and requester_authorization removed",
        )
    signed_required = [
        key for key in signed.get("required", []) if key not in transport_members
    ]
    if signed_required != unsigned.get("required"):
        lint.fail(
            schema_path,
            "peer_keypackages_claim_unsigned_request required[] must preserve the signed request business-member order",
        )
    if signed.get("allOf") != unsigned.get("allOf"):
        lint.fail(schema_path, "KeyPackage claim signed and unsigned selector branches must be identical")

    fixture_path = ARTIFACTS / "fixtures" / "keypackage-lifecycle-fixture.json"
    fixture = load_json(lint, fixture_path)
    rows = fixture.get("unsigned_selector_transcripts", []) if isinstance(fixture, dict) else []
    expected_branches = {"device", "native_agent", "minimal_metadata_pairwise"}
    seen_branches: set[str] = set()
    selector_fields = {
        "target_device_ids",
        "target_agent_id",
        "target_agent_verification_method",
        "target_agent_key_authorize_event_id",
        "target_pairwise_verification_method",
    }
    for index, row in enumerate(rows if isinstance(rows, list) else []):
        if not isinstance(row, dict):
            lint.fail(fixture_path, f"unsigned_selector_transcripts[{index}] must be an object")
            continue
        branch = row.get("branch")
        unsigned_request = row.get("unsigned_request")
        if branch not in expected_branches or not isinstance(unsigned_request, dict):
            lint.fail(fixture_path, f"unsigned_selector_transcripts[{index}] has an invalid branch or request")
            continue
        seen_branches.add(branch)
        present = set(unsigned_request) & selector_fields
        required_by_branch = {
            "device": {"target_device_ids"},
            "native_agent": {
                "target_agent_id",
                "target_agent_verification_method",
                "target_agent_key_authorize_event_id",
            },
            "minimal_metadata_pairwise": {"target_pairwise_verification_method"},
        }[branch]
        if present != required_by_branch:
            lint.fail(fixture_path, f"unsigned_selector_transcripts[{index}] does not preserve its exact selector branch")
        canonical = canonical_json(unsigned_request)
        if row.get("canonical_jcs") != canonical:
            lint.fail(fixture_path, f"unsigned_selector_transcripts[{index}].canonical_jcs drifted")
        digest = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if row.get("request_digest") != digest:
            lint.fail(fixture_path, f"unsigned_selector_transcripts[{index}].request_digest drifted")
    if seen_branches != expected_branches:
        lint.fail(fixture_path, "unsigned selector transcripts must cover device, native_agent, and minimal_metadata_pairwise exactly")


def check_sdk_conformance_contract(lint: Lint) -> None:
    path = ARTIFACTS / "profiles" / "conformance-profiles.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return
    contract = data.get("sdk_conformance_contract")
    if not isinstance(contract, dict):
        lint.fail(path, "missing sdk_conformance_contract")
        return
    if contract.get("contract_version") != "1":
        lint.fail(path, "sdk_conformance_contract.contract_version must be '1'")
    evidence_kinds = contract.get("evidence_kinds")
    if not isinstance(evidence_kinds, list) or not evidence_kinds:
        lint.fail(path, "sdk_conformance_contract.evidence_kinds must be non-empty")
        evidence_kinds = []
    clauses = contract.get("clauses")
    if not isinstance(clauses, list) or not clauses:
        lint.fail(path, "sdk_conformance_contract.clauses must be non-empty")
        return
    seen: set[str] = set()
    allowed_grades = {"V", "A", "U"}
    for index, clause in enumerate(clauses):
        label = f"sdk_conformance_contract.clauses[{index}]"
        if not isinstance(clause, dict):
            lint.fail(path, f"{label} must be an object")
            continue
        clause_id = clause.get("clause_id")
        if not isinstance(clause_id, str) or not re.fullmatch(r"AK-SDK-[0-9]{3}", clause_id):
            lint.fail(path, f"{label}.clause_id must be AK-SDK-NNN")
        elif clause_id in seen:
            lint.fail(path, f"{label}.clause_id duplicates {clause_id}")
        else:
            seen.add(clause_id)
        grades = clause.get("grades")
        if not isinstance(grades, list) or not grades or any(grade not in allowed_grades for grade in grades):
            lint.fail(path, f"{label}.grades must be a non-empty subset of V/A/U")
        required_evidence = clause.get("required_evidence")
        if not isinstance(required_evidence, list) or not required_evidence:
            lint.fail(path, f"{label}.required_evidence must be non-empty")
        elif any(kind not in evidence_kinds for kind in required_evidence):
            lint.fail(path, f"{label}.required_evidence contains an unknown evidence kind")
        source_anchor = clause.get("source_anchor")
        if not isinstance(source_anchor, str) or not source_anchor.startswith("spec/v1/zh/") or "#" not in source_anchor:
            lint.fail(path, f"{label}.source_anchor must reference a stable zh/ heading")
    expected_ids = {f"AK-SDK-{index:03d}" for index in range(1, 25)}
    if seen != expected_ids:
        lint.fail(path, "sdk_conformance_contract must define exactly AK-SDK-001 through AK-SDK-024")

    schema_path = ARTIFACTS / "schemas" / "sdk-conformance-claim.schema.json"
    fixture_path = ARTIFACTS / "fixtures" / "sdk-conformance-claim-fixture.json"
    if not schema_path.is_file():
        lint.fail(path, "sdk_conformance_contract requires schemas/sdk-conformance-claim.schema.json")
    if not fixture_path.is_file():
        lint.fail(path, "sdk_conformance_contract requires fixtures/sdk-conformance-claim-fixture.json")
    schema_registry = load_json(lint, ARTIFACTS / "registry" / "schema-registry.json")
    registered_schema_ids = {
        row.get("schema_id")
        for row in schema_registry.get("schemas", [])
        if isinstance(row, dict)
    } if isinstance(schema_registry, dict) else set()
    if "ak.schema.sdk_conformance_claim.v1" not in registered_schema_ids:
        lint.fail(path, "sdk conformance claim schema is not registered")



def check_operation_clause_registry(lint: Lint) -> None:
    clause_path = ARTIFACTS / "registry" / "operation-clause-registry.json"
    operation_path = ARTIFACTS / "registry" / "operation-registry.json"
    clause_data = load_json(lint, clause_path)
    operation_data = load_json(lint, operation_path)
    if not isinstance(clause_data, dict) or not isinstance(operation_data, dict):
        return
    clauses = clause_data.get("clauses")
    operations = operation_data.get("operations")
    if not isinstance(clauses, list) or not clauses:
        lint.fail(clause_path, "operation clause registry must contain clauses")
        return
    if not isinstance(operations, list):
        return

    allowed_selectors = {
        "all_operations",
        "openapi_protected_operations",
        "write_operations",
        "http_operations",
        "stream_operations",
        "partial_outcome_operations",
        "privacy_sensitive_operations",
    }
    selectors_by_clause: dict[str, str] = {}
    seen: set[str] = set()
    for index, clause in enumerate(clauses):
        label = f"clauses[{index}]"
        if not isinstance(clause, dict):
            lint.fail(clause_path, f"{label} must be an object")
            continue
        clause_id = clause.get("clause_id")
        if not isinstance(clause_id, str) or not re.fullmatch(r"AK-OP-[0-9]{3}", clause_id):
            lint.fail(clause_path, f"{label}.clause_id must be AK-OP-NNN")
            continue
        if clause_id in seen:
            lint.fail(clause_path, f"duplicate operation clause {clause_id}")
        seen.add(clause_id)
        selector = clause.get("selector")
        selector_kind = selector.get("kind") if isinstance(selector, dict) else None
        if selector_kind not in allowed_selectors:
            lint.fail(clause_path, f"{clause_id} has unknown selector kind {selector_kind!r}")
            continue
        selectors_by_clause[clause_id] = selector_kind
        evidence = clause.get("required_evidence")
        if not isinstance(evidence, list) or not evidence or any(not isinstance(item, str) or not item for item in evidence):
            lint.fail(clause_path, f"{clause_id}.required_evidence must be a non-empty string list")
        refs = clause.get("source_refs")
        if not isinstance(refs, list) or not refs:
            lint.fail(clause_path, f"{clause_id}.source_refs must be non-empty")
        else:
            for ref in refs:
                if not isinstance(ref, str) or not ref.startswith("spec/v1/"):
                    lint.fail(clause_path, f"{clause_id} has invalid source ref {ref!r}")
                    continue
                relative = ref.split("#", 1)[0].removeprefix("spec/v1/")
                if not (SPEC_ROOT / relative).is_file():
                    lint.fail(clause_path, f"{clause_id} source ref does not exist: {ref}")

    required_clause_ids = {f"AK-OP-{index:03d}" for index in range(1, 9)}
    if seen != required_clause_ids:
        lint.fail(clause_path, "operation clause registry must define exactly AK-OP-001 through AK-OP-008")

    for row in operations:
        if not isinstance(row, dict):
            continue
        operation_id = row.get("operation_id")
        if not isinstance(operation_id, str):
            continue
        segments = operation_id.split(".")
        op_kind = segments[-3] if len(segments) >= 3 else ""
        op_action = segments[-2] if len(segments) >= 2 else ""
        is_write = op_kind in {"command", "upload", "exchange"} or (
            op_kind == "resource" and op_action in {"replace", "delete"}
        )
        required = {"AK-OP-001", "AK-OP-004", "AK-OP-005"}
        if is_write:
            required.add("AK-OP-003")
        if op_kind == "stream":
            required.add("AK-OP-006")
        missing = required - seen
        if missing:
            lint.fail(clause_path, f"{operation_id} lacks required clause coverage {sorted(missing)}")



def check_vector_group_requirements(lint: Lint, known: dict[str, set[str]]) -> None:
    # Conformance-vector groups are fixture/runner groupings, NOT ak.profile.*
    # capability-negotiation profiles. They live in their own ak.vector_group.*
    # namespace with a dedicated requirements matrix, kept out of profile_roles /
    # profile_requirements so the capability namespace stays pure.
    path = ARTIFACTS / "profiles" / "conformance-profiles.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return

    groups = data.get("vector_groups")
    requirements = data.get("vector_group_requirements")
    if not isinstance(groups, list):
        lint.fail(path, "missing vector_groups list")
        return
    if not isinstance(requirements, dict):
        lint.fail(path, "missing vector_group_requirements matrix")
        return

    group_ids: set[str] = set()
    for gid in groups:
        if not isinstance(gid, str) or not VECTOR_GROUP_ID_RE.fullmatch(gid):
            lint.fail(path, f"vector_groups entry has invalid vector-group id: {gid}")
        else:
            group_ids.add(gid)

    for gid in sorted(group_ids - set(requirements.keys())):
        lint.fail(path, f"vector_group_requirements missing declared vector group: {gid}")

    fixture_files = {fixture.name for fixture in (ARTIFACTS / "fixtures").glob("*.json")}
    required_keys = {
        "operation_requirements",
        "required_event_kinds",
        "rejected_event_kinds",
        "required_schemas",
        "required_fixtures",
        "optional_extensions",
        "feature_discovery",
    }

    for gid, requirement in requirements.items():
        if gid not in group_ids:
            lint.fail(path, f"vector_group_requirements key is not a declared vector group: {gid}")
        if not isinstance(requirement, dict):
            lint.fail(path, f"{gid} requirement must be an object")
            continue
        for missing_key in sorted(required_keys - set(requirement.keys())):
            lint.fail(path, f"{gid} missing {missing_key}")

        for index, operation_requirement in enumerate(requirement.get("operation_requirements", [])):
            label = f"{gid}.operation_requirements[{index}]"
            if not isinstance(operation_requirement, dict) or set(operation_requirement) != {
                "direction",
                "operation_id",
                "binding_kind",
            }:
                lint.fail(path, f"{label} must use the closed operation requirement shape")
                continue
            if operation_requirement.get("direction") != "consume":
                lint.fail(path, f"{label}.direction must be consume for a vector runner")
            if operation_requirement.get("operation_id") not in known["operation_ids"]:
                lint.fail(path, f"{label} requires unknown operation_id")
            if operation_requirement.get("binding_kind") != "http_json":
                lint.fail(path, f"{label}.binding_kind must be http_json")

        for event_kind in requirement.get("required_event_kinds", []):
            if isinstance(event_kind, str) and event_kind.startswith("wire_scope:"):
                continue
            if event_kind not in known["event_kinds"]:
                lint.fail(path, f"{gid} requires unknown Event.kind: {event_kind}")

        for event_kind in requirement.get("rejected_event_kinds", []):
            if isinstance(event_kind, str) and event_kind.startswith("wire_scope:"):
                continue
            if event_kind not in known["event_kinds"]:
                lint.fail(path, f"{gid} rejects unknown Event.kind: {event_kind}")

        for schema_id in requirement.get("required_schemas", []):
            if schema_id not in known["schema_ids"]:
                lint.fail(path, f"{gid} requires unknown schema: {schema_id}")

        for fixture in requirement.get("required_fixtures", []):
            if fixture not in fixture_files:
                lint.fail(path, f"{gid} requires missing fixture: {fixture}")

        feature_discovery = requirement.get("feature_discovery")
        if not isinstance(feature_discovery, dict):
            lint.fail(path, f"{gid} feature_discovery must be an object")
        else:
            if not isinstance(feature_discovery.get("required"), list):
                lint.fail(path, f"{gid} feature_discovery.required must be a list")
            if not isinstance(feature_discovery.get("unsupported_optional"), str):
                lint.fail(path, f"{gid} feature_discovery.unsupported_optional must be a string")



def payload_schema_contains_ref(value: Any) -> bool:
    if isinstance(value, dict):
        if "$ref" in value:
            return True
        return any(payload_schema_contains_ref(child) for child in value.values())
    if isinstance(value, list):
        return any(payload_schema_contains_ref(child) for child in value)
    return False



def collect_kind_selector_tokens(value: Any) -> set[str]:
    if not isinstance(value, dict):
        return set()
    tokens: set[str] = set()
    const_value = value.get("const")
    if isinstance(const_value, str):
        tokens.add(const_value)
    enum_values = value.get("enum")
    if isinstance(enum_values, list):
        tokens.update(item for item in enum_values if isinstance(item, str))
    return tokens



def collect_payload_dispatch_kinds(value: Any) -> set[str]:
    dispatched: set[str] = set()
    if isinstance(value, dict):
        if_schema = value.get("if")
        then_schema = value.get("then")
        if isinstance(if_schema, dict) and isinstance(then_schema, dict):
            then_properties = then_schema.get("properties")
            payload_schema = (
                then_properties.get("payload")
                if isinstance(then_properties, dict)
                else None
            )
            if payload_schema_contains_ref(payload_schema):
                if_properties = if_schema.get("properties")
                kind_schema = (
                    if_properties.get("kind")
                    if isinstance(if_properties, dict)
                    else None
                )
                dispatched.update(collect_kind_selector_tokens(kind_schema))
        for child in value.values():
            dispatched.update(collect_payload_dispatch_kinds(child))
    elif isinstance(value, list):
        for child in value:
            dispatched.update(collect_payload_dispatch_kinds(child))
    return dispatched



def collect_payload_dispatch_refs(value: Any) -> list[tuple[str, str]]:
    """Return every `(Event kind, payload schema ref)` dispatch."""
    refs: list[tuple[str, str]] = []
    if isinstance(value, dict):
        if_schema = value.get("if")
        then_schema = value.get("then")
        if isinstance(if_schema, dict) and isinstance(then_schema, dict):
            then_properties = then_schema.get("properties")
            payload_schema = (
                then_properties.get("payload")
                if isinstance(then_properties, dict)
                else None
            )
            ref = payload_schema.get("$ref") if isinstance(payload_schema, dict) else None
            if isinstance(ref, str):
                if_properties = if_schema.get("properties")
                kind_schema = (
                    if_properties.get("kind")
                    if isinstance(if_properties, dict)
                    else None
                )
                for kind in collect_kind_selector_tokens(kind_schema):
                    if kind.startswith("ak."):
                        refs.append((kind, ref))
        for child in value.values():
            refs.extend(collect_payload_dispatch_refs(child))
    elif isinstance(value, list):
        for child in value:
            refs.extend(collect_payload_dispatch_refs(child))
    return refs



def collect_payload_dispatch_pairs(value: Any) -> list[tuple[str, str]]:
    """Return `(kind, payload class name)` views of the canonical dispatch scan."""
    pairs: list[tuple[str, str]] = []
    for kind, ref in collect_payload_dispatch_refs(value):
        match = PAYLOAD_DISPATCH_REF_RE.search(ref)
        if match:
            pairs.append((kind, match.group(1)))
    return pairs



def check_composite_subject_terminal_types(
    lint: Lint,
    event_schema_path: Path,
    event_schema: Any,
) -> None:
    """Reject cell-subject endpoints that are absent or not typed scalars.

    Single-field subjects and every composite/select endpoint must exist in the
    payload class selected for the Event kind. Coalesce descriptors may share
    one descriptor across payload classes, but at least one candidate must
    resolve. Every resolved ordinary endpoint must be scalar. A
    `string_set_digest` component is checked against its stricter closed
    string-or-array schema contract and is treated as a string only after
    transformation.
    """
    event_registry_path = ARTIFACTS / "registry" / "event-kind-registry.json"
    event_registry = load_json(lint, event_registry_path)
    if not isinstance(event_registry, dict):
        return

    schema_cache: dict[Path, Any] = {event_schema_path.resolve(): event_schema}

    def schema_document(path: Path) -> Any:
        resolved = path.resolve()
        if resolved not in schema_cache:
            schema_cache[resolved] = load_json(lint, resolved)
        return schema_cache[resolved]

    def dereference(
        schema_path: Path,
        document: Any,
        node: Any,
        seen: set[tuple[Path, str]] | None = None,
    ) -> tuple[Path, Any, Any]:
        seen = set() if seen is None else seen
        while isinstance(node, dict) and isinstance(node.get("$ref"), str):
            ref = node["$ref"]
            file_ref, separator, fragment = ref.partition("#")
            target_path = (
                (schema_path.parent / file_ref).resolve()
                if file_ref
                else schema_path.resolve()
            )
            key = (target_path, fragment)
            if key in seen:
                return schema_path, document, {}
            seen.add(key)
            target_document = schema_document(target_path)
            if target_document is None:
                return target_path, {}, {}
            try:
                target = resolve_json_pointer(
                    target_document,
                    f"#{fragment}" if separator else "#",
                )
            except KeyError:
                lint.fail(event_registry_path, f"cell subject schema ref not found: {ref}")
                return target_path, target_document, {}
            schema_path, document, node = target_path, target_document, target
        return schema_path, document, node

    def property_nodes(
        schema_path: Path,
        document: Any,
        node: Any,
        name: str,
        seen: set[int] | None = None,
    ) -> list[tuple[Path, Any, Any]]:
        schema_path, document, node = dereference(schema_path, document, node)
        if not isinstance(node, dict):
            return []
        seen = set() if seen is None else seen
        marker = id(node)
        if marker in seen:
            return []
        seen.add(marker)
        results: list[tuple[Path, Any, Any]] = []
        properties = node.get("properties")
        if isinstance(properties, dict) and name in properties:
            results.append((schema_path, document, properties[name]))
        for keyword in ("allOf", "oneOf", "anyOf"):
            branches = node.get(keyword)
            if isinstance(branches, list):
                for branch in branches:
                    results.extend(
                        property_nodes(schema_path, document, branch, name, seen.copy())
                    )
        return results

    def terminal_types(
        schema_path: Path,
        document: Any,
        node: Any,
        seen: set[int] | None = None,
    ) -> set[str]:
        schema_path, document, node = dereference(schema_path, document, node)
        if not isinstance(node, dict):
            return set()
        seen = set() if seen is None else seen
        marker = id(node)
        if marker in seen:
            return set()
        seen.add(marker)
        result: set[str] = set()
        declared = node.get("type")
        if isinstance(declared, str):
            result.add(declared)
        elif isinstance(declared, list):
            result.update(item for item in declared if isinstance(item, str))
        if "const" in node:
            value = node["const"]
            result.add(
                "null"
                if value is None
                else "boolean"
                if isinstance(value, bool)
                else "integer"
                if isinstance(value, int)
                else "number"
                if isinstance(value, float)
                else "string"
                if isinstance(value, str)
                else "array"
                if isinstance(value, list)
                else "object"
                if isinstance(value, dict)
                else "unknown"
            )
        enum = node.get("enum")
        if isinstance(enum, list):
            for value in enum:
                result.add(
                    "null"
                    if value is None
                    else "boolean"
                    if isinstance(value, bool)
                    else "integer"
                    if isinstance(value, int)
                    else "number"
                    if isinstance(value, float)
                    else "string"
                    if isinstance(value, str)
                    else "array"
                    if isinstance(value, list)
                    else "object"
                    if isinstance(value, dict)
                    else "unknown"
                )
        for keyword in ("allOf", "oneOf", "anyOf"):
            branches = node.get(keyword)
            if isinstance(branches, list):
                for branch in branches:
                    result.update(
                        terminal_types(schema_path, document, branch, seen.copy())
                    )
        return result

    def path_terminal_types(ref: str, payload_path: str) -> set[str] | None:
        file_ref, separator, fragment = ref.partition("#")
        schema_path = (
            (event_schema_path.parent / file_ref).resolve()
            if file_ref
            else event_schema_path.resolve()
        )
        document = schema_document(schema_path)
        if document is None:
            return None
        try:
            node = resolve_json_pointer(document, f"#{fragment}" if separator else "#")
        except KeyError:
            return None
        candidates = [(schema_path, document, node)]
        for segment in payload_path.removeprefix("payload.").split("."):
            next_candidates: list[tuple[Path, Any, Any]] = []
            for candidate_path, candidate_document, candidate in candidates:
                next_candidates.extend(
                    property_nodes(
                        candidate_path,
                        candidate_document,
                        candidate,
                        segment,
                    )
                )
            candidates = next_candidates
            if not candidates:
                return None
        result: set[str] = set()
        for candidate_path, candidate_document, candidate in candidates:
            result.update(
                terminal_types(candidate_path, candidate_document, candidate)
            )
        return result

    def path_terminal_nodes(
        ref: str, payload_path: str
    ) -> list[tuple[Path, Any, Any]] | None:
        file_ref, separator, fragment = ref.partition("#")
        schema_path = (
            (event_schema_path.parent / file_ref).resolve()
            if file_ref
            else event_schema_path.resolve()
        )
        document = schema_document(schema_path)
        if document is None:
            return None
        try:
            node = resolve_json_pointer(document, f"#{fragment}" if separator else "#")
        except KeyError:
            return None
        candidates = [(schema_path, document, node)]
        for segment in payload_path.removeprefix("payload.").split("."):
            next_candidates: list[tuple[Path, Any, Any]] = []
            for candidate_path, candidate_document, candidate in candidates:
                next_candidates.extend(
                    property_nodes(
                        candidate_path,
                        candidate_document,
                        candidate,
                        segment,
                    )
                )
            candidates = next_candidates
            if not candidates:
                return None
        return candidates

    def schema_variants(
        schema_path: Path,
        document: Any,
        node: Any,
        seen: set[int] | None = None,
    ) -> list[tuple[Path, Any, Any]]:
        schema_path, document, node = dereference(schema_path, document, node)
        if not isinstance(node, dict):
            return []
        seen = set() if seen is None else seen
        marker = id(node)
        if marker in seen:
            return []
        seen.add(marker)
        for keyword in ("oneOf", "anyOf"):
            branches = node.get(keyword)
            if isinstance(branches, list):
                result: list[tuple[Path, Any, Any]] = []
                for branch in branches:
                    result.extend(
                        schema_variants(
                            schema_path, document, branch, seen.copy()
                        )
                    )
                return result
        return [(schema_path, document, node)]

    def validate_string_set_schema(
        kind: str,
        source: str,
        component_ref: str,
    ) -> None:
        candidates: list[tuple[Path, Any, Any]] = []
        for ref in dispatch_refs.get(kind, []):
            nodes = path_terminal_nodes(ref, source)
            if nodes is not None:
                candidates.extend(nodes)
        variants: list[tuple[Path, Any, Any]] = []
        for candidate_path, candidate_document, candidate in candidates:
            variants.extend(
                schema_variants(candidate_path, candidate_document, candidate)
            )
        typed = [
            (
                terminal_types(variant_path, variant_document, variant),
                variant_path,
                variant_document,
                variant,
            )
            for variant_path, variant_document, variant in variants
        ]
        if not typed:
            lint.fail(
                event_registry_path,
                f"{component_ref} field {source!r} has no schema endpoint",
            )
            return
        if {next(iter(types)) for types, *_ in typed if len(types) == 1} != {
            "string",
            "array",
        } or any(len(types) != 1 for types, *_ in typed):
            lint.fail(
                event_registry_path,
                f"{component_ref} field {source!r} must be a closed string | array<string> union",
            )
            return
        string_shapes: list[Any] = []
        array_items: list[Any] = []
        for types, variant_path, variant_document, variant in typed:
            resolved_path, resolved_document, resolved = dereference(
                variant_path, variant_document, variant
            )
            if types == {"string"}:
                string_shapes.append(resolved)
                continue
            if not isinstance(resolved, dict):
                lint.fail(event_registry_path, f"{component_ref} array schema is malformed")
                continue
            if not isinstance(resolved.get("minItems"), int) or resolved["minItems"] < 1:
                lint.fail(
                    event_registry_path,
                    f"{component_ref} array schema must declare minItems >= 1",
                )
            if resolved.get("uniqueItems") is not True:
                lint.fail(
                    event_registry_path,
                    f"{component_ref} array schema must declare uniqueItems: true",
                )
            item = resolved.get("items")
            item_path, item_document, item = dereference(
                resolved_path, resolved_document, item
            )
            if terminal_types(item_path, item_document, item) != {"string"}:
                lint.fail(
                    event_registry_path,
                    f"{component_ref} array items must resolve only to string",
                )
            array_items.append(item)
        if len(string_shapes) != 1 or len(array_items) != 1:
            lint.fail(
                event_registry_path,
                f"{component_ref} must have exactly one string and one array variant",
            )
        elif canonical_json(string_shapes[0]) != canonical_json(array_items[0]):
            lint.fail(
                event_registry_path,
                f"{component_ref} string and array item variants must share one element schema",
            )

    dispatch_refs: dict[str, list[str]] = {}
    for kind, ref in collect_payload_dispatch_refs(event_schema):
        dispatch_refs.setdefault(kind, []).append(ref)

    def resolved_terminal_types(kind: str, source: str) -> tuple[bool, set[str]]:
        resolved_types: set[str] = set()
        resolved = False
        for ref in dispatch_refs.get(kind, []):
            types = path_terminal_types(ref, source)
            if types is not None:
                resolved = True
                resolved_types.update(types)
        return resolved, resolved_types

    def terminal_enum_values(
        schema_path: Path,
        document: Any,
        node: Any,
        seen: set[int] | None = None,
    ) -> set[Any]:
        schema_path, document, node = dereference(schema_path, document, node)
        if not isinstance(node, dict):
            return set()
        seen = set() if seen is None else seen
        marker = id(node)
        if marker in seen:
            return set()
        seen.add(marker)
        result: set[Any] = set()
        if "const" in node and isinstance(node["const"], (str, int, bool)):
            result.add(node["const"])
        enum = node.get("enum")
        if isinstance(enum, list):
            result.update(
                value for value in enum if isinstance(value, (str, int, bool))
            )
        for keyword in ("allOf", "oneOf", "anyOf"):
            branches = node.get(keyword)
            if isinstance(branches, list):
                for branch in branches:
                    result.update(
                        terminal_enum_values(
                            schema_path, document, branch, seen.copy()
                        )
                    )
        return result

    def reachable_selector_values(kind: str, selector: str) -> set[Any]:
        values: set[Any] = set()
        for ref in dispatch_refs.get(kind, []):
            nodes = path_terminal_nodes(ref, selector)
            for node_path, node_document, node in nodes or []:
                values.update(
                    terminal_enum_values(node_path, node_document, node)
                )
        return values

    def output_paths(kind: str, component: Any) -> list[str]:
        if isinstance(component, str):
            return [component]
        if not isinstance(component, dict):
            return []
        if isinstance(component.get("field"), str):
            return [component["field"]]
        branches = component.get("branches")
        if not isinstance(branches, dict):
            return []
        selector = component.get("selector")
        reachable = (
            reachable_selector_values(kind, selector)
            if isinstance(selector, str)
            else set()
        )
        return [
            branch["field"]
            for branch_name, branch in branches.items()
            if isinstance(branch, dict) and isinstance(branch.get("field"), str)
            and (not reachable or branch_name in reachable)
        ]

    allowed = {"string", "integer", "boolean", "null"}

    def validate_scalar_endpoint(
        kind: str,
        write_index: int,
        source: str,
        endpoint_ref: str,
        *,
        require_endpoint: bool = True,
    ) -> bool:
        if source == "envelope.actor_id":
            return True
        if not source.startswith("payload."):
            return False
        resolved, resolved_types = resolved_terminal_types(kind, source)
        if not resolved:
            if require_endpoint:
                lint.fail(
                    event_registry_path,
                    f"{endpoint_ref} endpoint {source!r} has no schema endpoint",
                )
            return False
        has_scalar_variant = bool(resolved_types & allowed)
        non_scalar_variants = resolved_types - allowed
        if not has_scalar_variant:
            lint.fail(
                event_registry_path,
                f"{endpoint_ref} endpoint {source!r} must be a schema-declared "
                f"JSON string/integer/boolean/null scalar, got "
                f"{sorted(resolved_types) or ['untyped']}",
            )
        elif non_scalar_variants:
            lint.fail(
                event_registry_path,
                f"{endpoint_ref} endpoint {source!r} has forbidden "
                f"non-scalar schema variants {sorted(non_scalar_variants)}",
            )
        return True

    rows = event_registry.get("event_kinds")
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict) or not isinstance(row.get("event_kind"), str):
            continue
        kind = row["event_kind"]
        writes = row.get("cell_writes")
        for write_index, write in enumerate(writes if isinstance(writes, list) else []):
            subject = write.get("cell_subject") if isinstance(write, dict) else None
            if not isinstance(subject, dict):
                continue
            subject_kind = subject.get("kind")
            subject_ref = f"{kind} cell_writes[{write_index}].cell_subject"
            if subject_kind == "coalesce":
                fields = subject.get("fields")
                resolved_any = False
                for source in fields if isinstance(fields, list) else []:
                    if isinstance(source, str):
                        resolved_any = (
                            validate_scalar_endpoint(
                                kind,
                                write_index,
                                source,
                                subject_ref,
                                require_endpoint=False,
                            )
                            or resolved_any
                        )
                if not resolved_any:
                    lint.fail(
                        event_registry_path,
                        f"{subject_ref} coalesce fields have no schema endpoint",
                    )
                continue
            if subject_kind not in {"composite", "tuple"}:
                source = subject.get("field")
                if isinstance(source, str):
                    validate_scalar_endpoint(
                        kind, write_index, source, subject_ref
                    )
                continue
            components = subject.get("components")
            for component_index, component in enumerate(
                components if isinstance(components, list) else []
            ):
                component_ref = (
                    f"{kind} cell_writes[{write_index}].cell_subject.components"
                    f"[{component_index}]"
                )
                if (
                    isinstance(component, dict)
                    and component.get("kind") == "string_set_digest"
                ):
                    source = component.get("field")
                    if isinstance(source, str) and source.startswith("payload."):
                        validate_string_set_schema(kind, source, component_ref)
                    continue
                selector = (
                    component.get("selector")
                    if isinstance(component, dict)
                    else None
                )
                if isinstance(selector, str) and selector.startswith("payload."):
                    selector_resolved, selector_types = resolved_terminal_types(
                        kind, selector
                    )
                    if not selector_resolved:
                        lint.fail(
                            event_registry_path,
                            f"{component_ref} selector {selector!r} has no schema endpoint",
                        )
                    elif selector_types != {"string"}:
                        lint.fail(
                            event_registry_path,
                            f"{kind} cell_writes[{write_index}].cell_subject.components"
                            f"[{component_index}] selector {selector!r} must be a "
                            f"schema-declared JSON string, got "
                            f"{sorted(selector_types) or ['untyped']}",
                        )
                for source in output_paths(kind, component):
                    validate_scalar_endpoint(
                        kind, write_index, source, component_ref
                    )



def check_event_schema_coverage(lint: Lint, known: dict[str, set[str]]) -> None:
    path = ARTIFACTS / "schemas" / "event-envelope.schema.json"
    data = load_json(lint, path)
    if data is None:
        return

    def realm_create_purpose_const(branch: object) -> object:
        if not isinstance(branch, dict):
            return None
        return (
            branch.get("properties", {})
            .get("payload", {})
            .get("properties", {})
            .get("object", {})
            .get("properties", {})
            .get("purpose", {})
            .get("const")
        )

    discriminator_conditions = {
        "Any Event carrying did_inception": ("then", "principal_control"),
        "A managed_agent_control Realm create without did_inception": (
            "if",
            "managed_agent_control",
        ),
    }
    schema_nodes = [node for _json_path, node, _key in walk_json(data) if isinstance(node, dict)]

    realm_identity_comment = (
        "zh/models/realm-and-space.md section 2.5.0: ak.realm.create MUST omit "
        "realm_id and use the realm_genesis scope. Every Realm, including "
        "Collaboration, Direct Conversation, human PCR, and managed Agent PCR, derives "
        "realm_id = retype(event_id, \"realm\") from this create Event. The uniform "
        "omission leaves one receiver-derived genesis form and avoids the digest cycle. "
        "Every other kind MUST carry realm_id."
    )
    realm_identity_matches = [
        node
        for node in schema_nodes
        if isinstance(node.get("$comment"), str)
        and node["$comment"].startswith(
            "zh/models/realm-and-space.md section 2.5.0: ak.realm.create"
        )
    ]
    if len(realm_identity_matches) != 1:
        lint.fail(
            path,
            "Event envelope must contain exactly one Realm genesis identity comment",
        )
    elif realm_identity_matches[0].get("$comment") != realm_identity_comment:
        lint.fail(
            path,
            "Realm genesis identity comment must use the uniform event-derived formula "
            "for human and managed Agent PCRs",
        )

    expected_realm_genesis_description = (
        "Genesis scope for ak.realm.create only. It carries no realm_id because the "
        "receiver derives every Realm id, including Collaboration, Direct Conversation, "
        "human PCR, and managed Agent PCR, as retype(event_id, \"realm\") from this "
        "create Event (zh/models/realm-and-space.md section 2.5.0). The uniform omission "
        "also prevents the digest cycle."
    )
    scope_ref = data.get("$defs", {}).get("scope_ref", {})
    realm_genesis_branches = [
        branch
        for branch in scope_ref.get("oneOf", [])
        if isinstance(branch, dict)
        and branch.get("properties", {}).get("kind", {}).get("const")
        == "realm_genesis"
    ]
    if len(realm_genesis_branches) != 1:
        lint.fail(path, "scope_ref must contain exactly one realm_genesis branch")
    elif (
        realm_genesis_branches[0].get("description")
        != expected_realm_genesis_description
    ):
        lint.fail(
            path,
            "scope_ref.realm_genesis description must use the uniform event-derived "
            "formula for human and managed Agent PCRs",
        )

    for comment_prefix, (branch_name, expected_purpose) in discriminator_conditions.items():
        matches = [
            node
            for node in schema_nodes
            if isinstance(node.get("$comment"), str)
            and node["$comment"].startswith(comment_prefix)
        ]
        if len(matches) != 1:
            lint.fail(
                path,
                f"Event envelope must contain exactly one {comment_prefix!r} admission condition",
            )
            continue
        actual_purpose = realm_create_purpose_const(matches[0].get(branch_name))
        if actual_purpose != expected_purpose:
            lint.fail(
                path,
                f"{comment_prefix!r} must constrain purpose={expected_purpose!r}, "
                f"got {actual_purpose!r}",
            )

    realm_genesis_path = ARTIFACTS / "schemas" / "realm-genesis.schema.json"
    realm_genesis = load_json(lint, realm_genesis_path)
    purpose_values = (
        realm_genesis.get("properties", {}).get("purpose", {}).get("enum", [])
        if isinstance(realm_genesis, dict)
        else []
    )
    for purpose in ("principal_control", "managed_agent_control"):
        if purpose not in purpose_values:
            lint.fail(
                realm_genesis_path,
                f"Realm genesis purpose enum must contain {purpose!r} used by envelope admission",
            )

    event_schema_tokens: set[str] = set()

    def collect_admitted_kind_tokens(node: object) -> None:
        if isinstance(node, list):
            for item in node:
                collect_admitted_kind_tokens(item)
            return
        if not isinstance(node, dict):
            return
        properties = node.get("properties")
        if isinstance(properties, dict):
            kind_schema = properties.get("kind")
            if isinstance(kind_schema, dict):
                value = kind_schema.get("const")
                if isinstance(value, str):
                    event_schema_tokens.add(value)
                values = kind_schema.get("enum")
                if isinstance(values, list):
                    event_schema_tokens.update(
                        item for item in values if isinstance(item, str)
                    )
        for key, value in node.items():
            # A negative rejection list proves that tokens are not Event kinds; it
            # is not admission coverage and must not be compared with the registry.
            if key != "not":
                collect_admitted_kind_tokens(value)

    collect_admitted_kind_tokens(data)

    event_schema_kinds = {
        token
        for token in event_schema_tokens
        if token.startswith("ak.") and not SCHEMA_ID_RE.fullmatch(token) and not PROFILE_ID_RE.fullmatch(token)
    }
    for token in sorted(event_schema_kinds - known["event_kinds"]):
        lint.fail(path, f"event-schema enum references unregistered Event.kind: {token}")
    for token in sorted(known["active_durable_event_kinds"] - event_schema_kinds):
        lint.fail(path, f"active Event.kind missing from event-schema enum coverage: {token}")

    active_event_wire_scopes = known.get("active_event_wire_scopes", {})
    active_envelope_event_kinds = {
        kind
        for kind, wire_scope in active_event_wire_scopes.items()
        if wire_scope in {"durable_event", "actor_private_event"}
    }
    payload_dispatch_kinds = {
        token
        for token in collect_payload_dispatch_kinds(data)
        if token.startswith("ak.") and not SCHEMA_ID_RE.fullmatch(token) and not PROFILE_ID_RE.fullmatch(token)
    }
    for token in sorted(active_envelope_event_kinds - payload_dispatch_kinds):
        lint.fail(path, f"active Event.kind missing payload schema dispatch: {token}")

    # The canonical contract registry owns one explicit payload_schema_ref for
    # every active standard Event kind. The Event Envelope remains hand-written,
    # so lint proves that its dispatch is a one-to-one equivalent view.
    contract_registry_path = ARTIFACTS / "registry" / "contract-registry.json"
    contract_registry = load_json(lint, contract_registry_path)
    event_registry = (
        contract_registry.get("event_kind_registry")
        if isinstance(contract_registry, dict)
        else None
    )
    event_rows = (
        event_registry.get("event_kinds") if isinstance(event_registry, dict) else None
    )
    dispatch_refs: dict[str, list[str]] = {}
    for kind, ref in collect_payload_dispatch_refs(data):
        dispatch_refs.setdefault(kind, []).append(ref)

    def normalize_payload_ref(ref: str, base: Path) -> str | None:
        file_ref, separator, fragment = ref.partition("#")
        target = (base / file_ref).resolve()
        try:
            relative = target.relative_to(ARTIFACTS.resolve()).as_posix()
        except ValueError:
            return None
        return relative + (f"#{fragment}" if separator else "")

    schema_cache: dict[Path, object] = {}

    def payload_ref_resolves(ref: str, base: Path) -> tuple[str | None, bool]:
        normalized = normalize_payload_ref(ref, base)
        if normalized is None:
            return None, False
        file_ref, separator, fragment = ref.partition("#")
        target = (base / file_ref).resolve()
        if not target.is_file() or not target.name.endswith(".schema.json"):
            return normalized, False
        if target not in schema_cache:
            schema_cache[target] = load_json(lint, target)
        current = schema_cache[target]
        if not separator:
            return normalized, isinstance(current, (dict, list, bool))
        if not fragment.startswith("/"):
            return normalized, False
        for token in fragment[1:].split("/"):
            token = token.replace("~1", "/").replace("~0", "~")
            if isinstance(current, dict) and token in current:
                current = current[token]
            elif isinstance(current, list) and token.isdigit() and int(token) < len(current):
                current = current[int(token)]
            else:
                return normalized, False
        return normalized, True

    registered_refs: set[str] = set()
    if not isinstance(event_rows, list):
        lint.fail(
            contract_registry_path,
            "event_kind_registry.event_kinds must be an array for payload binding",
        )
    else:
        for row in event_rows:
            if not isinstance(row, dict):
                continue
            kind = row.get("event_kind")
            if "payload_schema" in row:
                lint.fail(
                    contract_registry_path,
                    f"kind {kind!r} uses removed payload_schema carrier; use payload_schema_ref",
                )
            registered_ref = row.get("payload_schema_ref")
            if not isinstance(kind, str):
                continue
            if row.get("status") != "active" or not kind.startswith("ak."):
                continue
            if not isinstance(registered_ref, str) or not registered_ref:
                lint.fail(
                    contract_registry_path,
                    f"active standard kind {kind} must declare payload_schema_ref",
                )
                continue
            normalized_registered, resolves = payload_ref_resolves(
                registered_ref, ARTIFACTS
            )
            if normalized_registered is not None:
                registered_refs.add(normalized_registered)
            if not resolves:
                lint.fail(
                    contract_registry_path,
                    f"kind {kind} payload_schema_ref {registered_ref!r} does not resolve",
                )
            normalized_dispatches = [
                normalized
                for ref in dispatch_refs.get(kind, [])
                if (normalized := normalize_payload_ref(ref, path.parent)) is not None
            ]
            if len(normalized_dispatches) != 1:
                lint.fail(
                    path,
                    f"kind {kind} must have exactly one Event Envelope payload dispatch, "
                    f"got {normalized_dispatches}",
                )
            if normalized_registered is None or normalized_dispatches != [normalized_registered]:
                lint.fail(
                    path,
                    f"kind {kind} registry payload_schema_ref {registered_ref!r} is not selected "
                    f"by the unique Event Envelope payload dispatch {normalized_dispatches}",
                )

    event_payload_path = ARTIFACTS / "schemas" / "event-payload.schema.json"
    event_payload = load_json(lint, event_payload_path)
    payload_defs = event_payload.get("$defs") if isinstance(event_payload, dict) else None
    if isinstance(payload_defs, dict):
        for def_name in sorted(payload_defs):
            if not def_name.endswith("_payload"):
                continue
            normalized = f"schemas/event-payload.schema.json#/$defs/{def_name}"
            if normalized not in registered_refs:
                lint.fail(
                    event_payload_path,
                    f"orphan Event payload definition $defs/{def_name} is not referenced "
                    "by any active standard kind",
                )

    check_composite_subject_terminal_types(lint, path, data)

    # Mis-routed dispatch detector: each (kind, payload_class) pair must either
    # appear in KIND_PAYLOAD_RENAME_EXEMPTIONS verbatim, or embed the kind's
    # last dot-segment as a case-insensitive substring of the class name.
    # Catches typo / copy-paste errors like `ak.self.agent.command.pause.v1 → agent_resume_payload`.
    seen_pairs: set[tuple[str, str]] = set()
    for kind, class_name in collect_payload_dispatch_pairs(data):
        if (kind, class_name) in seen_pairs:
            continue
        seen_pairs.add((kind, class_name))
        if SCHEMA_ID_RE.fullmatch(kind) or PROFILE_ID_RE.fullmatch(kind):
            continue
        exempt = KIND_PAYLOAD_RENAME_EXEMPTIONS.get(kind)
        if exempt is not None:
            if exempt != class_name:
                lint.fail(
                    path,
                    f"kind {kind} is exempt and MUST dispatch to {exempt!r}, "
                    f"but dispatches to {class_name!r}",
                )
            continue
        if (kind, class_name) in LEGACY_SHARED_PAYLOAD_DISPATCH:
            continue
        last_segment = kind.rsplit(".", 1)[-1].lower()
        if last_segment not in class_name.lower():
            lint.fail(
                path,
                f"kind {kind} dispatches to payload class {class_name!r} "
                f"whose name does not contain the kind's last segment "
                f"{last_segment!r}; likely a mis-routed $ref. If this rename "
                f"is intentional, add the (kind, class) pair to "
                f"LEGACY_SHARED_PAYLOAD_DISPATCH or KIND_PAYLOAD_RENAME_EXEMPTIONS "
                f"in tools/artifact_lint/schemas.py.",
            )
    for kind, class_name in sorted(LEGACY_SHARED_PAYLOAD_DISPATCH - seen_pairs):
        lint.fail(
            path,
            "stale LEGACY_SHARED_PAYLOAD_DISPATCH entry has no matching dispatch: "
            f"({kind!r}, {class_name!r})",
        )



def check_read_scope_schema_closure(lint: Lint) -> None:
    cursor_path = ARTIFACTS / "schemas" / "read-cursor.schema.json"
    receipt_path = ARTIFACTS / "schemas" / "read-receipt.schema.json"
    cursor = load_json(lint, cursor_path)
    receipt = load_json(lint, receipt_path)

    if isinstance(cursor, dict):
        if "device_id" not in set(cursor.get("required") or []):
            lint.fail(cursor_path, "read cursor required must include device_id")
        if cursor.get("additionalProperties") is not False:
            lint.fail(cursor_path, "read cursor root additionalProperties must be false")
        read_scope = (cursor.get("properties") or {}).get("read_scope")
        if not isinstance(read_scope, dict):
            lint.fail(cursor_path, "read_cursor.read_scope schema missing")
        else:
            local_ref = read_scope.get("$ref")
            if isinstance(local_ref, str) and local_ref.startswith("#/$defs/"):
                def_name = local_ref.removeprefix("#/$defs/")
                resolved = (cursor.get("$defs") or {}).get(def_name)
                if isinstance(resolved, dict):
                    read_scope = resolved
                else:
                    lint.fail(cursor_path, f"read_cursor.read_scope local $ref does not resolve: {local_ref}")
            properties = read_scope.get("properties") or {}
            if "track_name" not in properties:
                lint.fail(cursor_path, "read_cursor.read_scope must define track_name for strand-track cursors")
            if not isinstance(read_scope.get("allOf"), list) or not read_scope.get("allOf"):
                lint.fail(cursor_path, "read_cursor.read_scope must define conditional scope constraints")

    if isinstance(receipt, dict):
        if "read_scope" not in set(receipt.get("required") or []):
            lint.fail(receipt_path, "read receipt required must include read_scope")
        if receipt.get("additionalProperties") is not False:
            lint.fail(receipt_path, "read receipt root additionalProperties must be false")
        read_scope = (receipt.get("properties") or {}).get("read_scope")
        if not isinstance(read_scope, dict) or read_scope.get("type") != "object":
            lint.fail(receipt_path, "read_receipt.read_scope must be an object schema")
        properties = receipt.get("properties") or {}
        if "strand_id" in properties or "track" in properties:
            lint.fail(receipt_path, "read receipt must not reintroduce top-level strand_id/track aliases")



def check_signed_object_closure(lint: Lint) -> None:
    envelope_path = ARTIFACTS / "schemas" / "encrypted-envelope.schema.json"
    identity_path = ARTIFACTS / "schemas" / "identity-receipt.schema.json"
    batch_path = ARTIFACTS / "schemas" / "event-batch-receipt.schema.json"

    envelope = load_json(lint, envelope_path)
    if isinstance(envelope, dict):
        if envelope.get("additionalProperties") is not False:
            lint.fail(envelope_path, "encrypted envelope root additionalProperties must be false")
        definitions = envelope.get("$defs") or {}
        for name in ("routing_context", "standard_mls_encryption_context", "exporter_mls_encryption_context"):
            context = definitions.get(name)
            if not isinstance(context, dict) or context.get("additionalProperties") is not False:
                lint.fail(
                    envelope_path,
                    f"encrypted envelope {name} additionalProperties must be false",
                )

    identity = load_json(lint, identity_path)
    if isinstance(identity, dict) and identity.get("additionalProperties") is not False:
        lint.fail(identity_path, "identity receipt root additionalProperties must be false")

    batch = load_json(lint, batch_path)
    if isinstance(batch, dict):
        def is_closed_object_schema(schema: object) -> bool:
            if not isinstance(schema, dict):
                return False
            if schema.get("additionalProperties") is False:
                return True
            ref = schema.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/$defs/"):
                target: object = batch
                for token in ref[2:].split("/"):
                    if not isinstance(target, dict):
                        return False
                    target = target.get(token)
                return is_closed_object_schema(target)
            branches = schema.get("oneOf")
            return isinstance(branches, list) and bool(branches) and all(is_closed_object_schema(branch) for branch in branches)

        if batch.get("additionalProperties") is not False:
            lint.fail(batch_path, "event batch receipt root additionalProperties must be false")
        properties = batch.get("properties") or {}
        for name in ("scope",):
            schema = properties.get(name)
            if not is_closed_object_schema(schema):
                lint.fail(batch_path, f"event batch receipt {name} additionalProperties must be false")



def check_derived_signature_projection_closure(lint: Lint) -> None:
    """Keep the seven current-v1 signed object families free of wire projection lists."""

    schema_names = (
        "key-backup.schema.json",
        "key-backup-active-series.schema.json",
        "key-backup-unlock-proof.schema.json",
        "recovery-policy.schema.json",
        "recovery-receipt.schema.json",
        "recovery-authority.schema.json",
        "security-transaction.schema.json",
    )

    def reject_signed_fields(path: Path, value: Any, pointer: str = "") -> None:
        if isinstance(value, dict):
            if "signed_fields" in value:
                lint.fail(path, f"{pointer or '/'} must not reintroduce derived wire field signed_fields")
            for key, child in value.items():
                reject_signed_fields(path, child, f"{pointer}/{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                reject_signed_fields(path, child, f"{pointer}/{index}")
        elif value == "signed_fields":
            lint.fail(path, f"{pointer or '/'} must not reintroduce derived wire field signed_fields")

    documents: dict[str, Any] = {}
    for name in schema_names:
        path = ARTIFACTS / "schemas" / name
        document = load_json(lint, path)
        documents[name] = document
        reject_signed_fields(path, document)

    canonical_ref = "./recovery-session.schema.json#/$defs/pcr_generation_ref"
    generation_paths = {
        "key-backup.schema.json": ("properties", "frontier_ref", "properties", "device_generation_ref"),
        "key-backup-active-series.schema.json": (
            "$defs",
            "frontier_ref",
            "properties",
            "device_generation_ref",
        ),
    }
    for name, keys in generation_paths.items():
        node = documents.get(name)
        try:
            for key in keys:
                node = node[key]
        except (KeyError, TypeError):
            lint.fail(ARTIFACTS / "schemas" / name, "missing frontier_ref.device_generation_ref")
            continue
        if not isinstance(node, dict) or node.get("$ref") != canonical_ref:
            lint.fail(
                ARTIFACTS / "schemas" / name,
                "frontier_ref.device_generation_ref must reuse recovery-session pcr_generation_ref",
            )

    authority_path = ARTIFACTS / "schemas" / "recovery-authority.schema.json"
    try:
        completion = documents["recovery-authority.schema.json"]["$defs"][
            "recovery_completion_attestation"
        ]
        completion_properties = completion["properties"]
        signature_description = completion_properties["auth_data"]["properties"]["signature"][
            "description"
        ]
    except (KeyError, TypeError):
        completion_properties = {}
        signature_description = ""
    if "device_authorization_event_digest" in completion_properties:
        lint.fail(
            authority_path,
            "recovery completion attestation signature projection must derive the Event digest from device_authorization_event_id",
        )
    if "device_authorization_event_id" not in signature_description:
        lint.fail(
            authority_path,
            "recovery completion attestation signature projection must bind device_authorization_event_id",
        )



def preimage_identity_candidate(name: str, description: str) -> bool:
    """True when a schema property is in scope for the 6.0.1 gate."""
    if name in PREIMAGE_IDENTITY_EXACT_NAMES or name.endswith(PREIMAGE_IDENTITY_NAME_SUFFIXES):
        return True
    return bool(PREIMAGE_IDENTITY_DERIVATION_RE.search(description))



def load_preimage_identity_exemptions(lint: Lint) -> dict[tuple[str, str, str], dict[str, Any]]:
    """Validate the exemption registry and index its active forward declarations.

    Returned keys are `(schema file name, json path, field)`. Rows that fail structural
    validation are reported and dropped, so a broken registry can never widen the gate.
    """
    path = PREIMAGE_EXEMPTION_REGISTRY_PATH
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return {}
    rows = data.get("exemptions")
    if not isinstance(rows, list) or not rows:
        lint.fail(path, "exemptions must be a non-empty list")
        return {}

    section_text = markdown_section_body(read_text(PREIMAGE_EXEMPTION_SECTION_PATH), PREIMAGE_EXEMPTION_SECTION_ANCHOR)
    if section_text is None:
        lint.fail(path, f"encoding.md section {PREIMAGE_EXEMPTION_SECTION_ANCHOR} does not exist")
        section_text = ""
    prose_ids = set(PREIMAGE_EXEMPTION_ID_RE.findall(section_text))

    id_pattern = re.compile(str(((data.get("registry_rules") or {}).get("exemption_id_pattern")) or r"^$"))
    vectors = load_json(lint, ARTIFACTS / "registry" / "vector-registry.json")
    vector_rows = vectors.get("vectors", []) if isinstance(vectors, dict) else []
    vector_status = {
        row.get("vector_id"): row.get("status") for row in vector_rows if isinstance(row, dict)
    }

    indexed: dict[tuple[str, str, str], dict[str, Any]] = {}
    registered_ids: set[str] = set()
    for index, row in enumerate(rows):
        label = f"exemptions[{index}]"
        if not isinstance(row, dict):
            lint.fail(path, f"{label} must be an object")
            continue
        exemption_id = row.get("exemption_id")
        if not isinstance(exemption_id, str) or not id_pattern.fullmatch(exemption_id):
            lint.fail(path, f"{label}.exemption_id must match registry_rules.exemption_id_pattern")
            continue
        label = exemption_id
        if exemption_id in registered_ids:
            lint.fail(path, f"{label}: duplicate exemption_id")
            continue
        registered_ids.add(exemption_id)

        missing = [key for key in PREIMAGE_EXEMPTION_ROW_KEYS if key not in row]
        if missing:
            lint.fail(path, f"{label} is missing required keys {missing}")
            continue
        extra = sorted(set(row) - set(PREIMAGE_EXEMPTION_ROW_KEYS))
        if extra:
            lint.fail(path, f"{label} carries unregistered keys {extra}")

        status = row.get("status")
        if status not in PREIMAGE_EXEMPTION_STATUS:
            lint.fail(path, f"{label}.status must be one of {sorted(PREIMAGE_EXEMPTION_STATUS)}")
            continue
        kind = row.get("kind")
        if kind not in PREIMAGE_EXEMPTION_KINDS:
            lint.fail(path, f"{label}.kind must be one of {sorted(PREIMAGE_EXEMPTION_KINDS)}")
            continue

        direction = row.get("commitment_direction")
        if direction in PREIMAGE_FORBIDDEN_DIRECTIONS:
            lint.fail(
                path,
                f"{label}.commitment_direction={direction!r} is a class A/B shape. encoding.md 6.0.1 makes "
                "those unconditional: the preimage would contain a function of its own digest, so no "
                "ordering can construct the unit. This registry MUST NOT carry such a row.",
            )
            continue
        for key in ("one_way_rationale", "target_fixed_when", "absent_target_semantics", "spec_anchor"):
            if not isinstance(row.get(key), str) or not str(row[key]).strip():
                lint.fail(path, f"{label}.{key} must be a non-empty string")
        for key in ("admission_compensating_checks", "conformance_vector_ids"):
            value = row.get(key)
            if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
                lint.fail(path, f"{label}.{key} must be a non-empty list of strings")

        for vector_id in row.get("conformance_vector_ids") or []:
            if not isinstance(vector_id, str):
                continue
            if vector_status.get(vector_id) != "active":
                lint.fail(
                    path,
                    f"{label}.conformance_vector_ids references {vector_id!r}, which is not an active "
                    "row in vector-registry.json; an exemption without live evidence is not a ruling",
                )

        anchor_ref = row.get("spec_anchor")
        if isinstance(anchor_ref, str) and "#" in anchor_ref:
            rel, _, anchor = anchor_ref.partition("#")
            resolved = (ROOT / rel).resolve()
            if not resolved.is_file():
                lint.fail(path, f"{label}.spec_anchor target does not exist: {rel}")
            elif markdown_section_digest(read_text(resolved), anchor) is None:
                lint.fail(path, f"{label}.spec_anchor heading does not exist: {anchor_ref}")
        else:
            lint.fail(path, f"{label}.spec_anchor must be <repo-relative markdown path>#<heading slug>")

        if status != "active":
            continue

        if exemption_id not in prose_ids:
            lint.fail(
                path,
                f"{label} is active but does not appear in encoding.md 6.0.1's closed list table; the "
                "prose list and this registry are bound in both directions",
            )

        subject = row.get("subject")
        if not isinstance(subject, dict):
            lint.fail(path, f"{label}.subject must be an object")
            continue
        event_kind = subject.get("event_kind")
        if not isinstance(event_kind, str) or not event_kind:
            lint.fail(path, f"{label}.subject.event_kind must be a non-empty string")
        if kind != "forward_declaration":
            continue
        schema_file = subject.get("schema_file")
        json_path = subject.get("json_path")
        field = subject.get("field")
        if not all(isinstance(item, str) and item for item in (schema_file, json_path, field)):
            lint.fail(
                path,
                f"{label}.subject must carry schema_file, json_path and field for a forward_declaration",
            )
            continue
        indexed[(Path(schema_file).name, json_path, field)] = row

    for exemption_id in sorted(prose_ids - registered_ids):
        lint.fail(
            path,
            f"encoding.md 6.0.1 lists {exemption_id!r}, which has no row here; the closed list may not "
            "name an exemption this registry does not carry",
        )
    return indexed



def check_preimage_event_identity_commitments(lint: Lint) -> None:
    """No preimage field may commit to an Event identity except by named exemption.

    encoding.md 6.0.1: `event_id` is a function of `event_digest`, whose preimage holds
    `payload` and `refs`. Class A (the enclosing Event's own identity or a retype of it)
    and class B (a not-yet-formed sibling of the same atomic unit or ordered submit
    batch) have no fixed point, so they are unconstructible and are rejected here
    unconditionally. Class C — a one-way forward declaration naming a later Event from
    another submission whose bytes the author already froze — is constructible and is
    allowed only when `preimage-identity-exemption-registry.json` carries an active row
    for exactly that field.

    The gate no longer decides by reading wording: wording only selects which rule
    applies, and the answer for class C comes from the registry. It also runs the
    reverse self-checks, so a registered row cannot rot into a licence for a field that
    moved, lost its declaration, or lost its evidence.
    """
    exemptions = load_preimage_identity_exemptions(lint)
    unmatched = dict(exemptions)

    for path in sorted((ARTIFACTS / "schemas").glob("*.schema.json")):
        data = load_json(lint, path)
        if not isinstance(data, dict):
            continue
        for json_path, value, key in walk_json(data):
            if key != "properties" or not isinstance(value, dict):
                continue
            for name, field in value.items():
                if not isinstance(field, dict):
                    continue
                description = str(field.get("description", "")).lower()
                if not preimage_identity_candidate(name, description):
                    continue
                row = exemptions.get((path.name, json_path, name))

                forbidden = next(
                    (phrase for phrase in PREIMAGE_SELF_REFERENCE_PHRASES if phrase in description),
                    None,
                )
                if forbidden is not None and not (
                    "not the enclosing" in description or "outside the preimage" in description
                ):
                    lint.fail(
                        path,
                        f"{json_path}.{name} declares an Event identity of the {forbidden!r} inside the "
                        "digest preimage; encoding.md 6.0.1 class A/B forbids it unconditionally because "
                        "event_id derives from that preimage. Commit to the counterpart's payload digest, "
                        "or move the commitment into proofs/receipts. No registry row can exempt it.",
                    )
                    continue

                forward = any(phrase in description for phrase in PREIMAGE_FORWARD_DECLARATION_PHRASES)
                if row is None:
                    if forward:
                        lint.fail(
                            path,
                            f"{json_path}.{name} declares a commitment to an Event that is not submitted "
                            "yet, but carries no row in preimage-identity-exemption-registry.json. "
                            "encoding.md 6.0.1 class C requires a named exemption; an implementation "
                            "MUST NOT infer one.",
                        )
                    continue

                unmatched.pop((path.name, json_path, name), None)
                if not forward:
                    lint.fail(
                        path,
                        f"{json_path}.{name} is registered as {row['exemption_id']} but its description no "
                        "longer states that it commits to an Event from a later submission. A registered "
                        "exemption whose declaration went vague is exactly what encoding.md 6.0.1 forbids.",
                    )
                if "6.0.1" not in description:
                    lint.fail(
                        path,
                        f"{json_path}.{name} is registered as {row['exemption_id']} but its description does "
                        "not cite encoding.md 6.0.1; a reader of the schema alone would not learn that this "
                        "field is a named exemption.",
                    )

    for (schema_name, json_path, field), row in sorted(unmatched.items()):
        lint.fail(
            PREIMAGE_EXEMPTION_REGISTRY_PATH,
            f"{row['exemption_id']} exempts {schema_name} {json_path}.{field}, which does not exist. "
            "A stale exemption silently licenses whatever later takes that name.",
        )



def check_wire_schema_no_bare_scope(lint: Lint) -> None:
    """Wire schemas must use bare scope only for an object's own boundary field."""
    allowed = {
        ("erasure-receipt.schema.json", "$.properties"),
        ("erasure-receipt.schema.json", "$.$defs.verification_stub.properties"),
        ("erasure-verification-stub.schema.json", "$.properties"),
        ("event-batch-receipt.schema.json", "$.properties"),
        ("event-batch-receipt.schema.json", "$.allOf[0].if.properties"),
        ("event-batch-receipt.schema.json", "$.allOf[1].if.properties"),
    }
    for path in sorted((ARTIFACTS / "schemas").glob("*.schema.json")):
        data = load_json(lint, path)
        if not isinstance(data, dict):
            continue
        for json_path, value, key in walk_json(data):
            if key == "properties" and isinstance(value, dict) and "scope" in value:
                if (path.name, json_path) in allowed:
                    continue
                lint.fail(path, f"{json_path}.scope uses bare wire field `scope`; use a domain-prefixed name")



def check_closed_object_required_declared(lint: Lint) -> None:
    """A closed object may not require a member it does not declare.

    `additionalProperties: false` plus a `required` name absent from
    `properties` makes the node unsatisfiable: no document can carry the
    required member without being rejected as an undeclared one. This is what a
    field rename looks like when it reaches `properties` but not `required`, and
    it is invisible until a conformance run tries to build a valid instance.
    """
    for path in sorted((ARTIFACTS / "schemas").glob("*.schema.json")):
        data = load_json(lint, path)
        if not isinstance(data, dict):
            continue
        for json_path, value, _key in walk_json(data):
            if not isinstance(value, dict) or value.get("additionalProperties") is not False:
                continue
            required = value.get("required")
            properties = value.get("properties")
            if not isinstance(required, list) or not isinstance(properties, dict):
                continue
            undeclared = [name for name in required if name not in properties]
            if undeclared:
                lint.fail(
                    path,
                    f"{json_path} is unsatisfiable: required {sorted(undeclared)} "
                    "absent from properties under additionalProperties:false",
                )


def check_reducer_payload_closure(lint: Lint) -> None:
    """Standard reducer-input payloads must reject undeclared top-level fields."""
    event_envelope_path = ARTIFACTS / "schemas" / "event-envelope.schema.json"
    payload_path = ARTIFACTS / "schemas" / "event-payload.schema.json"
    event_envelope = load_json(lint, event_envelope_path)
    payload_schema = load_json(lint, payload_path)
    if not isinstance(event_envelope, dict) or not isinstance(payload_schema, dict):
        return

    referenced_defs: set[str] = set()
    for _json_path, value, key in walk_json(event_envelope):
        if key == "$ref" and isinstance(value, str) and value.startswith("./event-payload.schema.json#/$defs/"):
            referenced_defs.add(value.rsplit("/", 1)[-1])

    defs = payload_schema.get("$defs", {})
    if not isinstance(defs, dict):
        lint.fail(payload_path, "event payload schema missing $defs")
        return

    for def_name in sorted(referenced_defs):
        definition = defs.get(def_name)
        if not isinstance(definition, dict):
            lint.fail(payload_path, f"Event Envelope references missing payload $defs/{def_name}")
            continue
        if definition.get("type") == "object" and definition.get("additionalProperties") is not False:
            lint.fail(
                payload_path,
                f"$defs.{def_name} is a standard reducer-input payload and must set additionalProperties=false",
            )



EVENT_ID_DIGEST_MIRROR_REMOVALS = (
    ("agent-membership-cascade.schema.json", ("$defs", "agent_cleanup_record"), "controller_terminal_event_id", "controller_terminal_event_digest"),
    ("agent-signer-evidence-operations.schema.json", ("$defs", "historical_query_selector"), "event_id", "event_digest"),
    ("agent-signer-evidence.schema.json", ("$defs", "account_status_event_basis"), "status_event_id", "status_event_digest"),
    ("agent-signer-evidence.schema.json", ("$defs", "event_admission_receipt"), "event_id", "event_digest"),
    ("audit-ryw-receipt.schema.json", (), "audit_event_id", "audit_event_digest"),
    ("event-payload.schema.json", ("$defs", "audit_accessed_payload"), "paired_event_id", "paired_event_digest"),
    ("history-key.schema.json", ("$defs", "event_candidate_binding", "properties", "event_binding_key"), "event_id", "event_digest"),
    ("recovery-authority.schema.json", ("$defs", "recovery_completion_attestation"), "device_authorization_event_id", "device_authorization_event_digest"),
    ("relation.schema.json", ("$defs", "relation_conflict_candidate"), "event_id", "event_digest"),
    ("service-operation-dtos.schema.json", ("$defs", "RedactedEventView"), "event_id", "event_digest"),
    ("contact-operations.schema.json", ("$defs", "contact_current_proof"), "head_event_ref", "head_digest"),
    ("contact-operations.schema.json", ("$defs", "request_acceptance_receipt_core"), "request_event_ref", "request_digest"),
    ("contact-operations.schema.json", ("$defs", "normal_response_acceptance_receipt"), "response_event_ref", "response_digest"),
    ("contact-operations.schema.json", ("$defs", "reject_acceptance_receipt"), "reject_event_ref", "reject_digest"),
    ("contact-operations.schema.json", ("$defs", "peer_contact_mirror_receipt"), "signed_event_ref", "signed_event_digest"),
    ("direct-conversation-operations.schema.json", ("$defs", "direct_conversation_founding_acceptance_receipt", "properties", "authorization_core", "oneOf", 1), "agent_provision_ref", "agent_provision_digest"),
    ("service-operation-dtos.schema.json", ("$defs", "DirectConversationFoundingAuthorityEvidence", "oneOf", 1), "agent_provision_ref", "agent_provision_digest"),
)


def check_event_id_digest_mirror_removals(lint: Lint) -> None:
    """Complete Event IDs are the sole wire source for their encoded digest."""
    schema_dir = ARTIFACTS / "schemas"
    for file_name, path, id_field, digest_field in EVENT_ID_DIGEST_MIRROR_REMOVALS:
        schema_path = schema_dir / file_name
        node = load_json(lint, schema_path)
        try:
            for segment in path:
                node = node[segment]
        except (KeyError, TypeError):
            lint.fail(
                schema_path,
                f"missing registered EventId mirror-removal object {'/'.join(map(str, path))}",
            )
            continue
        properties = node.get("properties", {}) if isinstance(node, dict) else {}
        required = set(node.get("required", [])) if isinstance(node, dict) else set()
        if id_field not in properties:
            lint.fail(schema_path, f"{id_field} must remain the complete Event identity source")
        if digest_field in properties or digest_field in required:
            lint.fail(
                schema_path,
                f"{digest_field} must be derived from {id_field}, not restored as a wire mirror",
            )


REANCHOR_RETIRED_AUTHORITY_FIELDS = (
    "did_version_id",
    "did_version_number",
    "registry_head",
    "log_head_digest",
)

REANCHOR_SCOPE_LOCAL_FIELDS = (
    "kind",
    "realm_id",
)


def check_device_reanchor_payload_receipt_binding(lint: Lint) -> None:
    """The re-anchor receipt scope and its payload must select the same authority."""
    payload_path = ARTIFACTS / "schemas" / "event-payload.schema.json"
    receipt_path = ARTIFACTS / "schemas" / "event-batch-receipt.schema.json"
    payload_schema = load_json(lint, payload_path)
    receipt_schema = load_json(lint, receipt_path)
    if not isinstance(payload_schema, dict) or not isinstance(receipt_schema, dict):
        return

    payload = payload_schema.get("$defs", {}).get("device_reanchor_payload")
    scope = receipt_schema.get("$defs", {}).get("device_reanchor_scope")
    if not isinstance(payload, dict):
        lint.fail(payload_path, "$defs.device_reanchor_payload is missing")
        return
    if not isinstance(scope, dict):
        lint.fail(receipt_path, "$defs.device_reanchor_scope is missing")
        return

    payload_props = payload.get("properties", {})
    scope_props = scope.get("properties", {})
    payload_required = set(payload.get("required", []))
    scope_required = set(scope.get("required", []))

    for name in ("reanchor_digest", "replacement_authorize_digest"):
        if name in scope_props or name in scope_required:
            lint.fail(
                receipt_path,
                f"$defs.device_reanchor_scope.{name} duplicates the digest encoded by the unique typed events[] item",
            )

    pcr_scope = receipt_schema.get("$defs", {}).get("pcr_genesis_scope")
    if isinstance(pcr_scope, dict):
        pcr_props = pcr_scope.get("properties", {})
        pcr_required = set(pcr_scope.get("required", []))
        for name in ("create_digest", "founding_authorize_digest"):
            if name in pcr_props or name in pcr_required:
                lint.fail(
                    receipt_path,
                    f"$defs.pcr_genesis_scope.{name} duplicates the digest encoded by the unique typed events[] item",
                )

    for name in REANCHOR_RETIRED_AUTHORITY_FIELDS:
        if name in payload_props:
            lint.fail(
                payload_path,
                f"$defs.device_reanchor_payload.{name} restores a retired DID-version authority field; "
                "the base re-anchor branch selects authority only through principal_id plus principal_server_id and the "
                "PCR-local device generation CAS",
            )
        if name in scope_props:
            lint.fail(
                receipt_path,
                f"$defs.device_reanchor_scope.{name} restores a retired DID-version authority field; "
                "the receipt scope MUST mirror the payload authority selection",
            )

    shared = [name for name in scope_props if name not in REANCHOR_SCOPE_LOCAL_FIELDS]
    for name in sorted(shared):
        if name not in payload_props:
            lint.fail(
                receipt_path,
                f"$defs.device_reanchor_scope.{name} has no counterpart in device_reanchor_payload; "
                "a receipt MUST NOT commit an authority field the covered Event does not carry",
            )
            continue
        if name not in scope_required or name not in payload_required:
            lint.fail(
                receipt_path,
                f"$defs.device_reanchor_scope.{name} must be required on both the payload and the "
                "receipt scope so the two can only be compared exactly",
            )
        if scope_props[name].get("$ref") != payload_props[name].get("$ref"):
            lint.fail(
                receipt_path,
                f"$defs.device_reanchor_scope.{name} does not reuse the payload $ref; a second shape "
                "for the same authority field allows silent substitution",
            )

    for name in ("principal_id", "principal_server_id", "previous_device_generation", "new_device_generation"):
        if name not in scope_required:
            lint.fail(
                receipt_path,
                f"$defs.device_reanchor_scope must require {name} to bind the exact re-anchored authority",
            )



def check_circle_membership_enum_single_source(lint: Lint) -> None:
    """Circle operation DTOs must reference the canonical membership enum directly."""
    path = ARTIFACTS / "schemas" / "circle-operations.schema.json"
    schema = load_json(lint, path)
    if not isinstance(schema, dict):
        return

    defs = schema.get("$defs", {})
    if not isinstance(defs, dict):
        lint.fail(path, "circle operation schema missing $defs")
        return

    if "circle_member_state" in defs:
        lint.fail(path, "$defs.circle_member_state is a forbidden alias; reference membership_state directly")

    canonical_ref = "./event-payload.schema.json#/$defs/membership_state"
    # Only the response DTOs still name a membership value. The request body carries
    # the caller-signed `ak.circle.member.state` Event and nothing else, so the
    # membership on the write path is `circle_member_state_payload.membership`, which
    # single-sources the same enum from inside event-payload.schema.json.
    fields = (
        ("circle_view", "viewer_membership"),
        ("circle_membership_outcome", "membership"),
    )
    for def_name, field_name in fields:
        definition = defs.get(def_name, {})
        properties = definition.get("properties", {}) if isinstance(definition, dict) else {}
        field = properties.get(field_name) if isinstance(properties, dict) else None
        if not isinstance(field, dict) or field.get("$ref") != canonical_ref:
            lint.fail(
                path,
                f"$defs.{def_name}.properties.{field_name} must reference {canonical_ref}",
            )



def check_null_cell_subject_wire_form(lint: Lint) -> None:
    """Pin the wire form of every cell family declared with `cell_subject: null`.

    encoding.md section 4 fixes that subject segment to the literal ASCII string
    `null`. The segment is both the state_root leaf preimage content and the leaf
    sort key, so any other spelling (realm id, Realm role classification, empty
    segment) forks state_root across implementations.
    """
    contract_registry = load_json(
        lint, ARTIFACTS / "registry" / "contract-registry.json"
    )
    if not isinstance(contract_registry, dict):
        return
    registry = contract_registry.get("event_kind_registry")
    if not isinstance(registry, dict):
        return

    null_families: set[str] = set()
    for contract in (registry.get("cell_contracts") or {}).values():
        if not isinstance(contract, dict):
            continue
        for write in contract.get("cell_writes", []) or []:
            if not isinstance(write, dict):
                continue
            family = write.get("cell_family")
            if isinstance(family, str) and family and write.get("cell_subject") is None:
                null_families.add(family)
    if not null_families:
        return

    scan_paths = sorted((ARTIFACTS / "fixtures").rglob("*.json"))
    scan_paths.extend(markdown_files())
    for path in scan_paths:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for family in sorted(null_families):
            if family not in text:
                continue
            pattern = re.compile(
                r"ak:cell:" + re.escape(family) + r":([A-Za-z0-9._~=%-]*)"
            )
            for match in pattern.finditer(text):
                subject = match.group(1)
                if subject != "null":
                    lint.fail(
                        path,
                        f"ak:cell:{family} declares cell_subject: null; its wire subject "
                        f"segment MUST be the literal 'null', found {subject!r} "
                        "(encoding.md section 4)",
                    )



def check_classification_context_paths(lint: Lint) -> None:
    """Every closed-class context MUST resolve to a real node in a real artifact.

    A context that points at a field which does not exist silently governs nothing,
    so a registration slip reads as coverage it never had. `*` matches any element
    of a list or any value of an object.
    """
    path = ARTIFACTS / "registry" / "classification-field-registry.json"
    registry = load_json(lint, path)
    if not isinstance(registry, dict):
        return
    rows = registry.get("closed_class_fields")
    if not isinstance(rows, list):
        lint.fail(path, "closed_class_fields must be an array")
        return

    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            lint.fail(path, f"closed_class_fields[{index}] must be an object")
            continue
        context = row.get("context")
        if not isinstance(context, str) or not context:
            lint.fail(path, f"closed_class_fields[{index}].context must be a non-empty string")
            continue
        artifact_ref, _, fragment = context.partition("#")
        artifact_path = ARTIFACTS / artifact_ref
        if not artifact_path.exists():
            lint.fail(path, f"{context} references missing artifact {artifact_ref}")
            continue
        document = load_json(lint, artifact_path)
        nodes: list[Any] = [document]
        for segment in [part for part in fragment.split("/") if part]:
            segment = segment.replace("~1", "/").replace("~0", "~")
            following: list[Any] = []
            for node in nodes:
                if segment == "*":
                    if isinstance(node, list):
                        following.extend(node)
                    elif isinstance(node, dict):
                        following.extend(node.values())
                elif isinstance(node, dict) and segment in node:
                    following.append(node[segment])
            if not following:
                lint.fail(path, f"{context} does not resolve: no node at {segment!r}")
                break
            nodes = following



def check_circle_lifecycle_basis_vector(lint: Lint) -> None:
    """Pin Circle lifecycle evaluation to the Event CBA basis and freshness rules."""
    path = ARTIFACTS / "fixtures" / "circle-scope-fixture.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return

    vector_id = "ak.vector.circle.lifecycle_basis_and_archive_freshness.v1"
    covers = data.get("covers_vectors", [])
    if not isinstance(covers, list) or vector_id not in covers:
        lint.fail(path, f"covers_vectors must include {vector_id}")

    rows = data.get("lifecycle_basis_cases")
    if not isinstance(rows, list):
        lint.fail(path, "lifecycle_basis_cases must be an array")
        return
    cases = {
        row.get("name"): row
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("name"), str)
    }
    required_names = {
        "data_event_basis_already_archived",
        "linear_archive_within_freshness_window",
        "linear_archive_beyond_freshness_window",
        "open_set_concurrent_archive",
        "tombstone_is_immediate",
        "restore_does_not_rehabilitate_pre_archive_basis",
        "control_move_basis_active",
        "control_move_basis_archived",
    }
    missing = sorted(required_names - cases.keys())
    if missing:
        lint.fail(path, f"missing Circle lifecycle basis case(s): {missing}")
        return

    archived = cases["data_event_basis_already_archived"]
    if archived.get("evaluation_basis") != "seal_ref" or archived.get("circle_state_at_basis") != "archived":
        lint.fail(path, "data_event_basis_already_archived must evaluate archived state at seal_ref")
    if archived.get("expected") != {"result": "failed_precondition", "reason": "circle_not_active"}:
        lint.fail(path, "an inactive Circle in the Event basis must reject with circle_not_active")

    within = cases["linear_archive_within_freshness_window"]
    within_expected = within.get("expected", {})
    if not isinstance(within_expected, dict) or within_expected.get("result") != "accept":
        lint.fail(path, "linear archive within the freshness window must be accepted")
    within_distance = within.get("distance_ms")
    within_window = within.get("revocation_freshness_window_ms")
    if not isinstance(within_distance, int) or not isinstance(within_window, int) or within_distance > within_window:
        lint.fail(path, "within-window Circle archive case exceeds its freshness window")
    if within_expected.get("included_in_data_cell_join") is not True:
        lint.fail(path, "accepted within-window Circle archive must remain in data-cell join input")
    if within_expected.get("must_not_reason") != "circle_not_active":
        lint.fail(path, "post-basis archive must not be reclassified as basis-time circle_not_active")

    beyond = cases["linear_archive_beyond_freshness_window"]
    beyond_distance = beyond.get("distance_ms")
    beyond_window = beyond.get("revocation_freshness_window_ms")
    if not isinstance(beyond_distance, int) or not isinstance(beyond_window, int) or beyond_distance <= beyond_window:
        lint.fail(path, "beyond-window Circle archive case must exceed its freshness window")
    if beyond.get("expected") != {"result": "reject_or_hide", "reason": "seal_ref_stale"}:
        lint.fail(path, "beyond-window Circle archive must reject or hide with seal_ref_stale")

    concurrent = cases["open_set_concurrent_archive"]
    concurrent_expected = concurrent.get("expected", {})
    if concurrent.get("notary_kind") != "open_set" or concurrent.get("evaluation_basis") != "joined_control_view":
        lint.fail(path, "concurrent Circle archive must evaluate the open_set joined control view")
    if not isinstance(concurrent_expected, dict) or concurrent_expected.get("reason") != "seal_ref_stale":
        lint.fail(path, "concurrent Circle archive must fail closed with seal_ref_stale")
    if concurrent_expected.get("freshness_window_applies") is not False:
        lint.fail(path, "concurrent Circle archive must not receive a freshness window")

    tombstone = cases["tombstone_is_immediate"]
    tombstone_expected = tombstone.get("expected", {})
    if tombstone.get("observed_lifecycle_move") != "ak.circle.tombstone":
        lint.fail(path, "tombstone_is_immediate must use ak.circle.tombstone")
    if (
        not isinstance(tombstone_expected, dict)
        or tombstone_expected.get("reason") != "seal_ref_stale"
        or tombstone_expected.get("freshness_window_applies") is not False
    ):
        lint.fail(path, "Circle tombstone must fail closed without a freshness window")

    restore = cases["restore_does_not_rehabilitate_pre_archive_basis"]
    restore_expected = restore.get("expected", {})
    if restore.get("seal_ref_position") != "before_archive":
        lint.fail(path, "restore barrier case must use a pre-archive seal_ref")
    if not isinstance(restore_expected, dict) or restore_expected.get("reason") != "seal_ref_stale":
        lint.fail(path, "restore must not rehabilitate a pre-archive seal_ref")
    if restore_expected.get("requires_new_basis_containing") != "ak.circle.restore":
        lint.fail(path, "post-restore writes must require a basis containing ak.circle.restore")

    control_active = cases["control_move_basis_active"]
    control_archived = cases["control_move_basis_archived"]
    control_active_expected = control_active.get("expected", {})
    if control_active.get("evaluation_basis") != "seal_basis_joined_view":
        lint.fail(path, "active Control Move case must evaluate seal_basis joined view")
    if (
        not isinstance(control_active_expected, dict)
        or control_active_expected.get("seal_revalidation_basis")
        != "frozen_predecessor_joined_governance_state"
    ):
        lint.fail(path, "Control Move must be revalidated at the Seal frozen predecessor state")
    if control_archived.get("expected") != {"result": "failed_precondition", "reason": "circle_not_active"}:
        lint.fail(path, "archived Circle in Control Move basis must reject with circle_not_active")



def check_did_and_device_constraints(lint: Lint) -> None:
    """Reject ambiguous DID/DID URL and device_id constraints in machine artifacts."""
    openapi_path = ARTIFACTS / "openapi" / "arkret-service-api.openapi.yaml"

    schema_paths = sorted((ARTIFACTS / "schemas").glob("*.schema.json"))
    schema_docs: dict[str, Any] = {}
    for path in schema_paths:
        data = load_json(lint, path)
        if isinstance(data, dict):
            schema_docs[path.name] = data

    def resolve_terminal(owner_name: str, node: Any) -> Any:
        """Follow $ref chains (local and sibling-file) to the terminal constraint node."""
        seen: set[tuple[str, str]] = set()
        while isinstance(node, dict) and isinstance(node.get("$ref"), str):
            ref = node["$ref"]
            file_part, _, fragment = ref.partition("#")
            if file_part in ("", "."):
                target_name = owner_name
            else:
                target_name = file_part.removeprefix("./")
                if "/" in target_name:
                    return None
            key = (target_name, fragment)
            if key in seen:
                return None
            seen.add(key)
            target_doc = schema_docs.get(target_name)
            if target_doc is None:
                return None
            try:
                node = resolve_json_pointer(target_doc, f"#{fragment}" if fragment else "#")
            except KeyError:
                return None
            owner_name = target_name
        return node

    for path in schema_paths:
        data = schema_docs.get(path.name)
        if not isinstance(data, dict):
            continue
        defs = data.get("$defs", {})
        if isinstance(defs, dict):
            local_did_url = defs.get("did_url")
            if (
                isinstance(local_did_url, dict)
                and "pattern" in local_did_url
                and local_did_url["pattern"] != DID_URL_PROFILE_PATTERN
            ):
                lint.fail(
                    path,
                    "$defs.did_url must equal the Arkret verification-method DID URL profile "
                    "(common-ids.schema.json#/$defs/did_url)",
                )
            local_did = defs.get("did")
            if isinstance(local_did, dict) and "pattern" in local_did and local_did["pattern"] != DID_BARE_PATTERN:
                lint.fail(
                    path,
                    "$defs.did must equal the canonical bare DID pattern "
                    "(common-ids.schema.json#/$defs/did)",
                )
        for json_path, value, key in walk_json(data):
            if key == "pattern" and value == DID_LEGACY_GREEDY_PATTERN:
                lint.fail(path, f"{json_path} uses legacy greedy DID pattern; use bare DID or DID URL pattern")
            if key == "properties" and isinstance(value, dict):
                for vm_key in ("verification_method", "verificationMethod"):
                    vm_schema = value.get(vm_key)
                    if not isinstance(vm_schema, dict):
                        continue
                    terminal = resolve_terminal(path.name, vm_schema)
                    if not isinstance(terminal, dict):
                        continue
                    if terminal.get("type") == "array":
                        # DID Document verification-method object arrays are covered by
                        # their item schemas, not by the DID URL profile.
                        continue
                    if terminal.get("pattern") != DID_URL_PROFILE_PATTERN:
                        lint.fail(
                            path,
                            f"{json_path}.{vm_key} must resolve to the Arkret verification-method DID URL "
                            "profile (common-ids.schema.json#/$defs/did_url); see "
                            "identity/did-usage-and-verification.md section 2.2.1",
                        )

    common_ids_path = ARTIFACTS / "schemas" / "common-ids.schema.json"
    common_defs = schema_docs.get("common-ids.schema.json", {}).get("$defs", {})
    human_principal = common_defs.get("human_principal_did", {})

    adapter_registry_path = ARTIFACTS / "registry" / "did-method-adapter-registry.json"
    adapter_registry = load_json(lint, adapter_registry_path)
    role_requirements = adapter_registry.get("role_requirements", {}) if isinstance(adapter_registry, dict) else {}
    adapters = adapter_registry.get("adapters", []) if isinstance(adapter_registry, dict) else []
    if not isinstance(role_requirements, dict):
        lint.fail(adapter_registry_path, "role_requirements must be an object")
        role_requirements = {}
    if not isinstance(adapters, list):
        lint.fail(adapter_registry_path, "adapters must be an array")
        adapters = []

    def methods_eligible_for(role: str) -> list[str]:
        requirement = role_requirements.get(role)
        if not isinstance(requirement, dict):
            lint.fail(adapter_registry_path, f"role_requirements.{role} must be an object")
            return []
        required = requirement.get("required_adapter_properties")
        if not isinstance(required, dict) or not required:
            lint.fail(
                adapter_registry_path,
                f"role_requirements.{role}.required_adapter_properties must be a non-empty object",
            )
            return []
        conditional = requirement.get("conditional_adapter_properties", [])
        if not isinstance(conditional, list):
            lint.fail(
                adapter_registry_path,
                f"role_requirements.{role}.conditional_adapter_properties must be an array",
            )
            return []

        eligible: list[str] = []
        for index, adapter in enumerate(adapters):
            if not isinstance(adapter, dict) or adapter.get("status") != "active":
                continue
            method = adapter.get("method")
            if not isinstance(method, str) or not method:
                lint.fail(adapter_registry_path, f"adapters[{index}].method must be a non-empty string")
                continue
            if any(field not in adapter for field in required):
                missing = sorted(field for field in required if field not in adapter)
                lint.fail(
                    adapter_registry_path,
                    f"adapters[{index}] is missing role property/properties: {', '.join(missing)}",
                )
                continue
            if any(adapter.get(field) != expected for field, expected in required.items()):
                continue
            conditional_match = True
            for condition_index, condition in enumerate(conditional):
                if not isinstance(condition, dict):
                    lint.fail(
                        adapter_registry_path,
                        f"role_requirements.{role}.conditional_adapter_properties[{condition_index}] must be an object",
                    )
                    conditional_match = False
                    continue
                when = condition.get("when")
                required_when_matched = condition.get("require")
                if not isinstance(when, dict) or not when or not isinstance(required_when_matched, dict) or not required_when_matched:
                    lint.fail(
                        adapter_registry_path,
                        f"role_requirements.{role}.conditional_adapter_properties[{condition_index}] must contain non-empty when and require objects",
                    )
                    conditional_match = False
                    continue
                if all(adapter.get(field) == expected for field, expected in when.items()) and any(
                    adapter.get(field) != expected for field, expected in required_when_matched.items()
                ):
                    conditional_match = False
            if conditional_match:
                eligible.append(method)
        return eligible

    principal_methods = methods_eligible_for("human_principal_anchor")
    service_methods = methods_eligible_for("service")
    actor_methods = methods_eligible_for("realm_local_ephemeral_actor")

    human_principal_pattern = str(human_principal.get("pattern", "")) if isinstance(human_principal, dict) else ""
    principal_schema_matches_registry = bool(principal_methods) and (
        human_principal_pattern.startswith(f"^{principal_methods[0]}:")
        if len(principal_methods) == 1
        else all(f"{method}:" in human_principal_pattern for method in principal_methods)
    )
    if not principal_schema_matches_registry:
        lint.fail(
            common_ids_path,
            "$defs.human_principal_did must admit the registry-derived human principal anchor methods "
            f"{principal_methods!r}",
        )

    account_schema_path = ARTIFACTS / "schemas" / "account-operations.schema.json"
    account_did = (
        schema_docs.get("account-operations.schema.json", {})
        .get("$defs", {})
        .get("did", {})
    )
    if account_did.get("$ref") != "./common-ids.schema.json#/$defs/human_principal_did":
        lint.fail(
            account_schema_path,
            "account registration did must use the closed registry-derived human principal schema",
        )

    principal_schema_path = ARTIFACTS / "schemas" / "principal-operations.schema.json"
    pcr_did = (
        schema_docs.get("principal-operations.schema.json", {})
        .get("$defs", {})
        .get("pcr_genesis_submit_request", {})
        .get("properties", {})
        .get("did", {})
    )
    if pcr_did.get("$ref") != "./common-ids.schema.json#/$defs/human_principal_did":
        lint.fail(
            principal_schema_path,
            "account-authority PCR genesis did must use the closed registry-derived human principal schema",
        )

    realm_genesis_path = ARTIFACTS / "schemas" / "realm-genesis.schema.json"
    realm_genesis_doc = schema_docs.get("realm-genesis.schema.json", {})
    realm_genesis_text = canonical_json(realm_genesis_doc)
    for required_token in ("#/$defs/human_principal_did",):
        if required_token not in realm_genesis_text:
            lint.fail(
                realm_genesis_path,
                f"identity-control genesis must use the closed registry-derived human principal branch: missing {required_token}",
            )
    profiles_path = ARTIFACTS / "profiles" / "conformance-profiles.json"
    profiles_doc = load_json(lint, profiles_path)
    profiles = profiles_doc.get("profile_requirements", {}) if isinstance(profiles_doc, dict) else {}
    if not isinstance(profiles, dict):
        lint.fail(profiles_path, "profiles must be an object")
        profiles = {}
    actor_profile_ids = sorted(
        profile_id
        for profile_id, profile in profiles.items()
        if isinstance(profile, dict)
        and isinstance(profile.get("identity"), dict)
        and "allowed_actor_methods" in profile["identity"]
    )
    if not actor_profile_ids:
        lint.fail(profiles_path, "at least one profile must declare allowed_actor_methods")
    realm_profile_allowlist = {
        value
        for branch in (
            schema_docs.get("realm.schema.json", {})
            .get("properties", {})
            .get("schema_refs", {})
            .get("items", {})
            .get("oneOf", [])
        )
        if isinstance(branch, dict)
        for value in branch.get("enum", [])
        if isinstance(value, str)
    }
    for actor_profile_id in actor_profile_ids:
        if actor_profile_id in realm_profile_allowlist:
            lint.fail(
                realm_genesis_path,
                f"actor-method profile {actor_profile_id} must not enter the closed Realm structural-profile allowlist",
            )
    for profile_id, profile in profiles.items():
        if not isinstance(profile, dict):
            continue
        identity = profile.get("identity")
        if not isinstance(identity, dict):
            continue
        if "allowed_principal_methods" in identity and identity.get("allowed_principal_methods") != principal_methods:
            lint.fail(
                profiles_path,
                f"{profile_id}.identity.allowed_principal_methods must equal the registry-derived human principal anchor allowlist {principal_methods!r}",
            )
        if "principal_method_default" in identity and identity.get("principal_method_default") not in principal_methods:
            lint.fail(
                profiles_path,
                f"{profile_id}.identity.principal_method_default must be in the registry-derived human principal anchor allowlist {principal_methods!r}",
            )
        if "service_method_default" in identity:
            if identity.get("allowed_service_methods") != service_methods:
                lint.fail(
                    profiles_path,
                    f"{profile_id}.identity.allowed_service_methods must equal the registry-derived service allowlist {service_methods!r}",
                )
            if identity.get("service_method_default") not in service_methods:
                lint.fail(
                    profiles_path,
                    f"{profile_id}.identity.service_method_default must be in the registry-derived service allowlist {service_methods!r}",
                )
        if "allowed_actor_methods" not in identity:
            continue
        if identity.get("allowed_actor_methods") != actor_methods:
            lint.fail(
                profiles_path,
                f"{profile_id}.identity.allowed_actor_methods must equal the registry-derived Realm-local ephemeral actor allowlist {actor_methods!r}",
            )
        if identity.get("actor_method_default") not in actor_methods:
            lint.fail(
                profiles_path,
                f"{profile_id}.identity.actor_method_default must be in the registry-derived Realm-local ephemeral actor allowlist {actor_methods!r}",
            )
        if identity.get("long_lived_principal") is not False:
            lint.fail(
                profiles_path,
                f"{profile_id}.identity.long_lived_principal must be false for an actor-method profile",
            )
        expected_closed_flags = {
            "account_registration_allowed": False,
            "principal_control_realm_allowed": False,
            "device_directory_allowed": False,
            "author_trust_anchor": "accepted_exact_epoch_mls_leafnode",
            "key_scope": "one_realm_no_reuse",
        }
        for field, expected in expected_closed_flags.items():
            if identity.get(field) != expected:
                lint.fail(
                    profiles_path,
                    f"{profile_id}.identity.{field} must equal {expected!r} for an actor-method profile",
                )
        if profile.get("required_event_kinds") != []:
            lint.fail(
                profiles_path,
                f"{profile_id} must not require PCR/device lifecycle Event kinds when it declares allowed_actor_methods",
            )

    freshness_path = ARTIFACTS / "registry" / "did-freshness-profile-registry.json"
    freshness_doc = load_json(lint, freshness_path)
    freshness_profiles = freshness_doc.get("profiles", []) if isinstance(freshness_doc, dict) else []
    call_sites = freshness_doc.get("call_sites", []) if isinstance(freshness_doc, dict) else []
    evidence_classes = freshness_doc.get("evidence_classes", []) if isinstance(freshness_doc, dict) else []
    current_evidence_classes = {
        row.get("evidence_class")
        for row in evidence_classes
        if isinstance(row, dict) and row.get("requires_current_did") is True
    }
    profile_ids = {
        row.get("freshness_profile_id")
        for row in freshness_profiles
        if isinstance(row, dict) and isinstance(row.get("freshness_profile_id"), str)
    }
    declared_sites: dict[tuple[str, str], dict[str, Any]] = {}
    for index, row in enumerate(call_sites if isinstance(call_sites, list) else []):
        if not isinstance(row, dict):
            lint.fail(freshness_path, f"call_sites[{index}] must be an object")
            continue
        key = (row.get("site_kind"), row.get("site_id"))
        if not all(isinstance(part, str) and part for part in key):
            lint.fail(freshness_path, f"call_sites[{index}] must identify site_kind and site_id")
            continue
        if key in declared_sites:
            lint.fail(freshness_path, f"duplicate DID authority call site {key!r}")
        declared_sites[key] = {name: value for name, value in row.items() if name not in {"site_kind", "site_id"}}
        freshness_profile_id = row.get("freshness_profile_id")
        if row.get("evidence_class") in current_evidence_classes:
            if freshness_profile_id not in profile_ids:
                lint.fail(freshness_path, f"{key!r} references an unknown freshness_profile_id")
        elif freshness_profile_id is not None:
            lint.fail(
                freshness_path,
                f"{key!r} is historical/non-current evidence and must use freshness_profile_id=null",
            )

    contract_path = ARTIFACTS / "registry" / "contract-registry.json"
    contract = load_json(lint, contract_path)
    actual_sites: dict[tuple[str, str], dict[str, Any]] = {}
    operations = contract.get("operation_registry", {}).get("operations", []) if isinstance(contract, dict) else []
    event_kinds = contract.get("event_kind_registry", {}).get("event_kinds", []) if isinstance(contract, dict) else []
    for kind, id_field, rows in (
        ("operation", "operation_id", operations),
        ("event_kind", "event_kind", event_kinds),
    ):
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict) or "did_authority" not in row:
                continue
            authority = row.get("did_authority")
            site_id = row.get(id_field)
            if not isinstance(authority, dict) or not isinstance(site_id, str):
                lint.fail(contract_path, f"invalid did_authority registration on {kind} {site_id!r}")
                continue
            actual_sites[(kind, site_id)] = authority
    verifier_actions = contract.get("did_authority_verifier_actions", []) if isinstance(contract, dict) else []
    for index, row in enumerate(verifier_actions if isinstance(verifier_actions, list) else []):
        if not isinstance(row, dict):
            lint.fail(contract_path, f"did_authority_verifier_actions[{index}] must be an object")
            continue
        site_id = row.get("site_id")
        if row.get("site_kind") != "verifier_action" or not isinstance(site_id, str) or not site_id:
            lint.fail(contract_path, f"invalid verifier_action registration at index {index}")
            continue
        actual_sites[("verifier_action", site_id)] = {
            name: value for name, value in row.items() if name not in {"site_kind", "site_id"}
        }
    if set(actual_sites) != set(declared_sites):
        lint.fail(
            freshness_path,
            "DID authority call-site closure mismatch: "
            f"missing_in_registry={sorted(set(actual_sites) - set(declared_sites))!r}, "
            f"stale_in_registry={sorted(set(declared_sites) - set(actual_sites))!r}",
        )
    for key in sorted(set(actual_sites) & set(declared_sites)):
        if actual_sites[key] != declared_sites[key]:
            lint.fail(freshness_path, f"{key!r} does not byte-match its operation/event did_authority object")

    evidence_boundary_path = ARTIFACTS / "registry" / "did-evidence-boundary-registry.json"
    evidence_boundary_doc = load_json(lint, evidence_boundary_path)
    boundaries = evidence_boundary_doc.get("boundaries", []) if isinstance(evidence_boundary_doc, dict) else []
    expected_boundary_ids = {
        "human_or_organization_pcr_genesis",
        "managed_agent_pcr_genesis",
        "applet_ghost_pcr_genesis",
        "principal_resolution_record",
        "service_resolution_record",
        "did_method_evidence",
        "ephemeral_pairwise_mls_credential",
        "third_party_proof",
        "ordinary_identity_reference",
    }
    boundary_ids: set[str] = set()
    for index, row in enumerate(boundaries if isinstance(boundaries, list) else []):
        if not isinstance(row, dict):
            lint.fail(evidence_boundary_path, f"boundaries[{index}] must be an object")
            continue
        boundary_id = row.get("boundary_id")
        if not isinstance(boundary_id, str) or not boundary_id:
            lint.fail(evidence_boundary_path, f"boundaries[{index}].boundary_id must be non-empty")
            continue
        if boundary_id in boundary_ids:
            lint.fail(evidence_boundary_path, f"duplicate boundary_id {boundary_id}")
        boundary_ids.add(boundary_id)
        requirement = row.get("did_requirement")
        if requirement not in {"required", "required_did_url", "forbidden"}:
            lint.fail(evidence_boundary_path, f"{boundary_id} has invalid did_requirement {requirement!r}")
        did_path = row.get("did_path")
        if requirement == "forbidden" and did_path is not None:
            lint.fail(evidence_boundary_path, f"{boundary_id} forbids did but declares did_path")
        if requirement != "forbidden" and not isinstance(did_path, str):
            lint.fail(evidence_boundary_path, f"{boundary_id} requires a non-empty did_path")
        schema_ref = row.get("schema_ref")
        if not isinstance(schema_ref, str) or not schema_ref:
            lint.fail(evidence_boundary_path, f"{boundary_id} must declare schema_ref")
        elif not (ARTIFACTS / schema_ref.partition("#")[0]).exists():
            lint.fail(evidence_boundary_path, f"{boundary_id} references missing schema {schema_ref}")
    if boundary_ids != expected_boundary_ids:
        lint.fail(
            evidence_boundary_path,
            "DID evidence-boundary closure mismatch: "
            f"missing={sorted(expected_boundary_ids - boundary_ids)!r}, "
            f"stale={sorted(boundary_ids - expected_boundary_ids)!r}",
        )
    def contains_forbidden_adapter_key(value: Any) -> bool:
        if isinstance(value, dict):
            return any(
                key in {"core_to_did", "expand"} or contains_forbidden_adapter_key(child)
                for key, child in value.items()
            )
        if isinstance(value, list):
            return any(contains_forbidden_adapter_key(child) for child in value)
        return False

    if contains_forbidden_adapter_key(adapter_registry):
        lint.fail(adapter_registry_path, "DID adapters must not expose core_to_did/expand")

    document_contract_path = ARTIFACTS / "registry" / "did-document-contract-registry.json"
    document_contract = load_json(lint, document_contract_path)
    normalized_ref = document_contract.get("normalized_document_schema_ref") if isinstance(document_contract, dict) else None
    if normalized_ref != "schemas/did-binding-contracts.schema.json#/$defs/normalized_did_document":
        lint.fail(document_contract_path, "normalized_document_schema_ref must have one canonical owner")
    digest_owner = document_contract.get("document_digest_owner") if isinstance(document_contract, dict) else None
    expected_forbidden_digest_names = {
        "did_document_digest",
        "did_document_snapshot_digest",
    }
    if not isinstance(digest_owner, dict):
        lint.fail(document_contract_path, "document_digest_owner must be an object")
    else:
        if digest_owner.get("field") != "document_digest":
            lint.fail(document_contract_path, "document_digest_owner.field must be document_digest")
        if digest_owner.get("raw_bytes_field") != "raw_document_digest":
            lint.fail(
                document_contract_path,
                "document_digest_owner.raw_bytes_field must be raw_document_digest",
            )
        forbidden_digest_names = digest_owner.get("forbidden_synonyms")
        if (
            not isinstance(forbidden_digest_names, list)
            or any(not isinstance(name, str) for name in forbidden_digest_names)
            or set(forbidden_digest_names) != expected_forbidden_digest_names
        ):
            lint.fail(
                document_contract_path,
                "document_digest_owner.forbidden_synonyms must close every retired DID-document digest field name",
            )
    registered_types = {
        row.get("type")
        for row in document_contract.get("arkret_service_types", [])
        if isinstance(row, dict)
    } if isinstance(document_contract, dict) else set()
    expected_types = {
        "ArkretService",
        "ArkretGovernanceService",
        "ArkretRealmHistoryRecoveryKey",
        "ArkretManagedPrincipalController",
        "ArkretPrincipalControlRealm",
    }
    if registered_types != expected_types:
        lint.fail(
            document_contract_path,
            f"Arkret DID service type closure mismatch: expected {sorted(expected_types)!r}, got {sorted(registered_types)!r}",
        )
    rejected_service_types = ("ArkretPrincipalServer", "ArkretDirectory")
    for forbidden_type in rejected_service_types:
        if forbidden_type in registered_types:
            lint.fail(document_contract_path, f"legacy service type {forbidden_type} must not be registered")

    # A rejected DID service type is only allowed to be *named by the rule that
    # rejects it*. Anywhere else in the artifact tree — a fixture value, an error
    # description, a schema enum — it reads as a second, dual-read spelling of
    # `ArkretService` + `serviceKind`, which is exactly what the closure forbids.
    rejection_rule_paths = {
        "contract-registry.json": "$.did_document_contract_registry.registry_rules[3]",
        "did-document-contract-registry.json": "$.registry_rules[3]",
    }
    for artifact_path in all_json_files():
        document = load_json(lint, artifact_path)
        if document is None:
            continue
        allowed_rule_prefix = rejection_rule_paths.get(artifact_path.name)
        for json_path, value, key in walk_json(document):
            candidates = []
            if isinstance(key, str):
                candidates.append((f"{json_path} (property name)", key, False))
            if isinstance(value, str):
                candidates.append((json_path, value, True))
            for candidate_path, candidate, is_value in candidates:
                hit = next(
                    (name for name in rejected_service_types if name in candidate),
                    None,
                )
                if hit is None:
                    continue
                if (
                    is_value
                    and allowed_rule_prefix is not None
                    and json_path == allowed_rule_prefix
                ):
                    continue
                lint.fail(
                    artifact_path,
                    f"{candidate_path} names rejected DID service type {hit}; use "
                    "ArkretService plus serviceKind (or the registered specialized type)",
                )

    forbidden_digest_owner_paths = {
        "contract-registry.json": "$.did_document_contract_registry.document_digest_owner.forbidden_synonyms[",
        "did-document-contract-registry.json": "$.document_digest_owner.forbidden_synonyms[",
    }
    for artifact_path in all_json_files():
        document = load_json(lint, artifact_path)
        if document is None:
            continue
        allowed_owner_prefix = forbidden_digest_owner_paths.get(artifact_path.name)
        for json_path, value, key in walk_json(document):
            candidates = []
            if isinstance(key, str):
                candidates.append((f"{json_path} (property name)", key, False))
            if isinstance(value, str):
                candidates.append((json_path, value, True))
            for candidate_path, candidate, is_value in candidates:
                hit = next(
                    (name for name in expected_forbidden_digest_names if name in candidate),
                    None,
                )
                if hit is None:
                    continue
                if (
                    is_value
                    and allowed_owner_prefix is not None
                    and json_path.startswith(allowed_owner_prefix)
                ):
                    continue
                lint.fail(
                    artifact_path,
                    f"{candidate_path} names forbidden DID-document digest field {hit}; "
                    "use document_digest or raw_document_digest according to the registered preimage",
                )

    openapi = load_yaml(lint, openapi_path)
    if not isinstance(openapi, dict):
        return

    for json_path, value, key in walk_json(openapi):
        if key == "pattern" and value in {DID_LEGACY_PREFIX_PATTERN, DID_LEGACY_GREEDY_PATTERN}:
            lint.fail(openapi_path, f"{json_path} uses legacy DID pattern {value!r}")

        if key == "properties" and isinstance(value, dict):
            device_schema = value.get("device_id")
            if isinstance(device_schema, dict) and not (
                device_schema.get("$ref") or device_schema.get("pattern") == DEVICE_ID_PATTERN
            ):
                lint.fail(openapi_path, f"{json_path}.device_id must use the canonical ak:device UUIDv7 pattern")

            vm_schema = value.get("verification_method")
            if isinstance(vm_schema, dict) and not (
                vm_schema.get("$ref") or "#" in str(vm_schema.get("pattern", ""))
            ):
                lint.fail(openapi_path, f"{json_path}.verification_method must use a DID URL pattern with a key fragment")

        if isinstance(value, dict) and value.get("name") == "device_id":
            schema = value.get("schema", {})
            if isinstance(schema, dict) and not (
                schema.get("$ref") or schema.get("pattern") == DEVICE_ID_PATTERN
            ):
                lint.fail(openapi_path, f"{json_path}.schema must use the canonical ak:device UUIDv7 pattern")



def _fsm_field_states(
    schema_files: dict[str, Any],
    payload_schema_ref: str | None,
    field_path: str,
    states: list[str],
) -> list[str]:
    """Resolve a field-sourced transition endpoint to its payload const/enum.

    Falling back to the full state list keeps the gate permissive when the
    field cannot be resolved, but a resolvable const/enum narrows the edge so
    that field-sourced writes cannot fabricate reachability (the exact hole
    OPEN-FLOW-PROTO-013 hid in)."""
    if not payload_schema_ref or not field_path.startswith("payload."):
        return list(states)
    resolved = _supply_resolve_ref(schema_files, "", payload_schema_ref)
    if resolved is None:
        return list(states)
    file, _def_name, _identity, node = resolved

    def deref(current_file: str, current: Any) -> tuple[str, Any]:
        for _ in range(6):
            if isinstance(current, dict) and "$ref" in current:
                r = _supply_resolve_ref(schema_files, current_file, current["$ref"])
                if r is None:
                    return current_file, None
                current_file, _d, _identity, current = r
            else:
                break
        return current_file, current

    for part in field_path.split(".")[1:]:
        file, node = deref(file, node)
        if not isinstance(node, dict):
            return list(states)
        props = node.get("properties")
        if not isinstance(props, dict) or part not in props:
            return list(states)
        node = props[part]
    file, node = deref(file, node)
    if isinstance(node, dict):
        if "const" in node:
            return [_FSM_ABSENT if node["const"] is None else node["const"]]
        enum_values = node.get("enum")
        if isinstance(enum_values, list) and enum_values:
            return [_FSM_ABSENT if value is None else value for value in enum_values]
        alternatives = node.get("oneOf") or node.get("anyOf")
        if isinstance(alternatives, list):
            projected: list[str] = []
            for alternative in alternatives:
                _alternative_file, alternative = deref(file, alternative)
                if not isinstance(alternative, dict):
                    continue
                if alternative.get("type") == "null":
                    projected.append(_FSM_ABSENT)
                elif "const" in alternative:
                    projected.append(
                        _FSM_ABSENT
                        if alternative["const"] is None
                        else alternative["const"]
                    )
                elif isinstance(alternative.get("enum"), list):
                    projected.extend(
                        _FSM_ABSENT if value is None else value
                        for value in alternative["enum"]
                    )
            if projected:
                return list(dict.fromkeys(projected))
    return list(states)



def check_fsm_state_reachability(lint: Lint) -> None:
    """Every fsm cell family must declare exactly one entry idiom
    (initial_state | initial_states | template) and every declared state must
    be reachable from the entry set through registered cell writes; every
    allowed transition must have a write that can perform it and no write may
    leave the allowed transition table. This is the gate OPEN-FLOW-PROTO-013
    was missing."""
    registry_path = ARTIFACTS / "registry" / "contract-registry.json"
    contract = load_json(lint, registry_path)
    if not isinstance(contract, dict):
        return
    event_kind_registry = contract.get("event_kind_registry") or {}
    fsm_contracts = event_kind_registry.get("fsm_contracts") or {}
    fsm_templates = event_kind_registry.get("fsm_templates") or {}
    cell_contracts = event_kind_registry.get("cell_contracts") or {}
    schema_files = _supply_schema_files(lint)
    payload_refs: dict[str, str] = {}
    for row in event_kind_registry.get("event_kinds") or []:
        kind = row.get("event_kind")
        ref = row.get("payload_schema_ref")
        if isinstance(kind, str) and isinstance(ref, str):
            payload_refs[kind] = ref

    writes_by_family: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for event_kind, cell_contract in cell_contracts.items():
        for write in cell_contract.get("cell_writes") or []:
            if write.get("lattice") != "fsm":
                continue
            family = write.get("cell_family")
            projection = write.get("effect_projection") or {}
            if family and projection.get("kind") in ("transition", "transition_to"):
                writes_by_family.setdefault(family, []).append((event_kind, projection))

    fsm_exemption_rows = [
        row
        for row in _supply_load_exemptions(lint)
        if row["kind"] == "fsm_transition"
    ]
    waived_states: dict[str, set[str]] = {}
    waived_transitions: dict[str, set[tuple[str, str]]] = {}
    for row in fsm_exemption_rows:
        waived_states.setdefault(row["fsm_family"], set()).update(row["states"])
        waived_transitions.setdefault(row["fsm_family"], set()).update(
            tuple(pair) for pair in row["transitions"]
        )
    fsm_used_rows: set[str] = set()

    for template_name, template in fsm_templates.items():
        unknown = set(template.keys()) - _FSM_TEMPLATE_KEYS
        if unknown:
            lint.fail(
                registry_path,
                f"fsm_templates.{template_name}: unknown keys {sorted(unknown)}",
            )

    for family, declared in fsm_contracts.items():
        unknown = set(declared.keys()) - _FSM_CONTRACT_KEYS
        if unknown:
            lint.fail(
                registry_path,
                f"fsm_contracts.{family}: unknown keys {sorted(unknown)}; the "
                "entry idiom key set is closed",
            )
            continue
        entry_keys = [
            key
            for key in ("initial_state", "initial_states", "template")
            if key in declared
        ]
        if len(entry_keys) != 1:
            lint.fail(
                registry_path,
                f"fsm_contracts.{family}: exactly one of initial_state / "
                f"initial_states / template must be declared, found {entry_keys}",
            )
            continue
        contract_view = declared
        if "template" in declared:
            template = fsm_templates.get(declared["template"])
            if not isinstance(template, dict):
                lint.fail(
                    registry_path,
                    f"fsm_contracts.{family}: unknown template {declared['template']}",
                )
                continue
            contract_view = dict(template)
            contract_view.update(
                {key: value for key, value in declared.items() if key != "template"}
            )
        states = list(contract_view.get("states") or [])
        if not states:
            lint.fail(registry_path, f"fsm_contracts.{family}: states must be non-empty")
            continue
        entry_states = []
        if contract_view.get("initial_state") in states:
            entry_states.append(contract_view["initial_state"])
        for state in contract_view.get("initial_states") or []:
            if state in states:
                entry_states.append(state)
            else:
                lint.fail(
                    registry_path,
                    f"fsm_contracts.{family}: initial state {state} not in states",
                )
        allowed = {
            tuple(_FSM_ABSENT if value is None else value for value in pair)
            for pair in contract_view.get("allowed_transitions") or []
        }
        instance_parameters = declared.get("instance_parameters") or {}
        for conditional in contract_view.get("conditional_transitions") or []:
            condition = conditional.get("when") or {}
            parameter = condition.get("parameter")
            if instance_parameters.get(parameter) == condition.get("const"):
                allowed.add(tuple(conditional.get("transition") or ()))

        edges: list[tuple[str, str, str]] = []
        for event_kind, projection in writes_by_family.get(family, []):
            payload_ref = payload_refs.get(event_kind)
            to_source = projection.get("to") or {}
            if "const" in to_source:
                to_states = [to_source["const"]]
            elif isinstance(to_source.get("field"), str):
                to_states = _fsm_field_states(
                    schema_files, payload_ref, to_source["field"], states
                )
            else:
                to_states = list(states)
            if projection.get("kind") == "transition":
                from_source = projection.get("from") or {}
                if "const" in from_source:
                    from_states = (
                        [_FSM_ABSENT]
                        if from_source["const"] is None
                        else [from_source["const"]]
                    )
                elif isinstance(from_source.get("field"), str):
                    from_states = _fsm_field_states(
                        schema_files, payload_ref, from_source["field"], states
                    )
                else:
                    from_states = list(states)
            else:
                from_states = list(states)
            for from_state in from_states:
                for to_state in to_states:
                    if to_state not in states:
                        lint.fail(
                            registry_path,
                            f"fsm_contracts.{family}: {event_kind} writes to "
                            f"undeclared state {to_state}",
                        )
                        continue
                    edges.append((from_state, to_state, event_kind))
            # Only const->const writes are checked against the transition
            # table here: field-sourced from/to values are constrained by the
            # reducer against the frozen prestate at admission
            # (event-and-patch.md transition_to semantics), so the synthetic
            # expansion above must not be treated as a declared write pair.
            if projection.get("kind") == "transition":
                from_source = projection.get("from") or {}
                to_source = projection.get("to") or {}
                if (
                    "const" in from_source
                    and from_source["const"] is not None
                    and "const" in to_source
                    and (from_source["const"], to_source["const"]) not in allowed
                ):
                    lint.fail(
                        registry_path,
                        f"fsm_contracts.{family}: {event_kind} writes "
                        f"{from_source['const']} -> {to_source['const']} "
                        "outside allowed_transitions",
                    )

        if not entry_states and not any(edge[0] == _FSM_ABSENT for edge in edges):
            lint.fail(
                registry_path,
                f"fsm_contracts.{family}: no entry — neither an initial state "
                "nor an absent-state creation write exists",
            )
            continue
        reachable = set(entry_states)
        changed = True
        while changed:
            changed = False
            for from_state, to_state, _event_kind in edges:
                if to_state in reachable:
                    continue
                if from_state == _FSM_ABSENT or from_state in reachable:
                    reachable.add(to_state)
                    changed = True
        family_waived_states = waived_states.get(family, set())
        family_waived_transitions = waived_transitions.get(family, set())
        unreachable = [state for state in states if state not in reachable]
        waived_unreachable = [s for s in unreachable if s in family_waived_states]
        unreachable = [s for s in unreachable if s not in family_waived_states]
        if unreachable:
            lint.fail(
                registry_path,
                f"fsm_contracts.{family}: states unreachable from the entry set "
                f"through registered writes: {unreachable}",
            )
        covered_pairs = set()
        for from_state, to_state, _event_kind in edges:
            covered_pairs.add((from_state, to_state))
        dead_allowed = sorted(pair for pair in allowed if pair not in covered_pairs)
        waived_dead = [p for p in dead_allowed if p in family_waived_transitions]
        dead_allowed = [p for p in dead_allowed if p not in family_waived_transitions]
        if dead_allowed:
            lint.fail(
                registry_path,
                f"fsm_contracts.{family}: allowed transitions with no registered "
                f"write: {dead_allowed}",
            )
        if waived_unreachable or waived_dead:
            for row in fsm_exemption_rows:
                if row["fsm_family"] != family:
                    continue
                if any(s in row["states"] for s in waived_unreachable) or any(
                    list(p) in row["transitions"] for p in waived_dead
                ):
                    fsm_used_rows.add(row["exemption_id"])

    for row in fsm_exemption_rows:
        if row["exemption_id"] not in fsm_used_rows:
            lint.fail(
                SUPPLY_EXEMPTION_REGISTRY_PATH,
                f"{row['exemption_id']}: stale fsm exemption row waives no "
                "failing state or transition; delete the row now that the "
                "machine contract carries the write",
            )
