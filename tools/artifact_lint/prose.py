"""Artifact lint phase 5: prose."""

from __future__ import annotations

from .core import (
    ARTIFACTS,
    Any,
    CANONICAL_LEXEME_REGISTRY_PATH,
    COMMON_OBJECT_FIELD_MATRIX_PATH,
    C_BET_04_REQUIRED_FRONTMATTER,
    ENVELOPE_SUBJECT_FORBIDDEN,
    ENVELOPE_SUBJECT_SOURCES,
    EVENT_AUTHORING_DURABLE_EFFECT_KINDS,
    EVENT_LOG_OPERATIONS_WITHOUT_A_SIGNED_REQUEST,
    EVIDENCE_MATERIAL_AUDIT_PATH,
    FORBIDDEN_NAMING_ALIAS_KEYS,
    FULL_MARKDOWN_EXAMPLE_SCHEMAS,
    HEADING_RE,
    JSON_FENCE_EXPECT_ATTR_RE,
    JSON_FENCE_FIRST_ERROR_ATTR_RE,
    JSON_FENCE_RE,
    JSON_FENCE_SCHEMA_ATTR_RE,
    LEGACY_ANNOUNCE_ID_RE,
    LEGACY_DID_METHOD_REGEX_RE,
    Lint,
    MARKDOWN_LINK_RE,
    NAMING_DEBT_PATH,
    NAMING_RULES_PATH,
    NAMING_RULE_MARKER_RE,
    NON_NORMATIVE_KEYWORD_WAIVERS,
    OPERATION_COUNT_RE,
    PROFILE_ID_TOKEN_RE,
    Path,
    ROOT,
    SCHEMA_ID_TOKEN_RE,
    SIGNED_EVENT_REQUEST_MARKERS,
    SPEC_ROOT,
    STABLE_SECTION_PLACEHOLDER_RE,
    STAGE_VALUES,
    TEXT_ARTIFACT_REF_RE,
    TRUST_DOMAIN_JSON_DID_RE,
    TYPED_ID_PREFIX_TOKEN_RE,
    TYPED_ID_TOKEN_RE,
    UNFOLDED_PASCAL_ACRONYM_RE,
    WIRE_GUARD_FILES,
    _FRONTMATTER_BLOCK_RE,
    _NORMATIVE_HEADING_RE,
    _NORMATIVE_KEYWORD_RE,
    all_json_files,
    check_event_envelope_candidates,
    check_event_ref_invariants_in_value,
    check_json_instance_against_schema,
    check_typed_id_token,
    json,
    load_json,
    load_schema_document,
    load_yaml,
    markdown_files,
    markdown_heading_slug,
    parse_json_text,
    raw_artifact_files,
    re,
    read_text,
    resolve_json_pointer,
    split_ref,
    walk_json,
    yaml,
)
from .naming import (
    DEFAULT_REJECTED_WRAPPER_WORDS,
    DEFAULT_FORBIDDEN_LEXEMES,
    FORBIDDEN_SYMBOLIC_LITERALS,
    PASCAL_CASE_RE,
    PREDICATES,
    SNAKE_CASE_RE,
    enumerate_schema_enums,
    enumerate_schema_properties,
    enumerate_schema_type_names,
    naive_property_occurrences,
    naive_property_population,
    nc_artifact_001,
    nc_bool_001,
    nc_code_001,
    nc_count_001,
    nc_evidence_001,
    nc_hash_001,
    nc_lexeme_001,
    nc_set_001,
    schema_shape_has_type,
    stacked_wrapper_words,
    unregistered_wrapper_word,
)


def is_wire_guard_file(path: Path) -> bool:
    return path.name in WIRE_GUARD_FILES



def check_naming_predicates(lint: Lint) -> None:
    """Apply naming predicates and retain exact aliases only as historical fallback.

    The drift registries and changelog intentionally mention legacy spellings;
    current schemas, fixtures, OpenAPI, and prose examples must not. This guard
    is driven by ``naming-convention-rules.json`` and enforces the mechanically
    decidable portion of common-fields.md §2.
    """

    rules_data = load_json(lint, NAMING_RULES_PATH)
    if not isinstance(rules_data, dict):
        return
    if rules_data.get("source_of_truth") is not False:
        lint.fail(NAMING_RULES_PATH, "naming rules are a derived predicate table, not a truth source")
    if rules_data.get("baseline") != []:
        lint.fail(NAMING_RULES_PATH, "naming convention baseline must be empty at closure")
    if rules_data.get("evidence_material_audit") != "tools/evidence-material-audit.json":
        lint.fail(NAMING_RULES_PATH, "NC-EVIDENCE-001 must point to the exact-path evidence audit")
    if rules_data.get("canonical_lexeme_registry") != (
        "spec/v1/artifacts/registry/canonical-lexeme-registry.json"
    ):
        lint.fail(NAMING_RULES_PATH, "NC-LEXEME-001 must point to the canonical lexeme registry")
    rules = rules_data.get("rules")
    if not isinstance(rules, list):
        lint.fail(NAMING_RULES_PATH, "rules must be an array")
        return
    rule_ids = [row.get("rule_id") for row in rules if isinstance(row, dict)]
    if len(rule_ids) != len(set(rule_ids)) or any(not isinstance(item, str) for item in rule_ids):
        lint.fail(NAMING_RULES_PATH, "rule_id values must be unique non-empty strings")
    prose_path = SPEC_ROOT / "zh" / "models" / "common-fields.md"
    prose_ids = NAMING_RULE_MARKER_RE.findall(prose_path.read_text(encoding="utf-8"))
    if len(prose_ids) != len(set(prose_ids)):
        lint.fail(prose_path, "naming rule markers must be unique")
    if set(prose_ids) != set(rule_ids):
        lint.fail(
            NAMING_RULES_PATH,
            f"narrative/predicate rule_id drift: prose-only={sorted(set(prose_ids) - set(rule_ids))}, "
            f"json-only={sorted(set(rule_ids) - set(prose_ids))}",
        )
    for row in rules:
        if not isinstance(row, dict):
            lint.fail(NAMING_RULES_PATH, "every naming rule must be an object")
            continue
        for exception in row.get("exceptions", []):
            if not isinstance(exception, dict) or not all(
                exception.get(field) for field in ("id", "basis", "reason", "anchor")
            ):
                lint.fail(NAMING_RULES_PATH, f"{row.get('rule_id')} has an incomplete exception")
                continue
            if exception.get("basis") == "external_literal" and not exception.get("external_anchor"):
                lint.fail(
                    NAMING_RULES_PATH,
                    f"{row.get('rule_id')} external_literal exception lacks external_anchor",
                )
            # An exception whose anchor no longer resolves has stopped describing
            # anything; it silently widens the rule instead of narrowing it.
            anchor = exception.get("anchor")
            if isinstance(anchor, str) and not (ROOT / anchor).exists():
                lint.fail(
                    NAMING_RULES_PATH,
                    f"{row.get('rule_id')} exception `{exception.get('id')}` anchors a path "
                    f"that no longer exists: {anchor}",
                )

    lexeme_registry = load_json(lint, CANONICAL_LEXEME_REGISTRY_PATH)
    forbidden_lexemes: set[str] = set()
    lexeme_qualified_external_forms: set[str] = set()
    lexeme_non_contract_exceptions: set[tuple[str, str, str]] = set()
    matched_lexeme_non_contract_exceptions: set[tuple[str, str, str]] = set()
    if isinstance(lexeme_registry, dict):
        if lexeme_registry.get("source_of_truth") is not True:
            lint.fail(CANONICAL_LEXEME_REGISTRY_PATH, "canonical lexeme registry must be a truth source")
        if lexeme_registry.get("kind") != "canonical_lexeme_registry":
            lint.fail(CANONICAL_LEXEME_REGISTRY_PATH, "canonical lexeme registry has the wrong kind")
        terms = lexeme_registry.get("canonical_terms")
        if not isinstance(terms, list) or not terms:
            lint.fail(CANONICAL_LEXEME_REGISTRY_PATH, "canonical_terms must be a non-empty array")
        else:
            canonical_words: set[str] = set()
            for index, term in enumerate(terms):
                where = f"canonical_terms[{index}]"
                if not isinstance(term, dict):
                    lint.fail(CANONICAL_LEXEME_REGISTRY_PATH, f"{where} must be an object")
                    continue
                canonical = term.get("canonical")
                aliases = term.get("forbidden_aliases")
                if not isinstance(canonical, str) or not SNAKE_CASE_RE.fullmatch(canonical):
                    lint.fail(CANONICAL_LEXEME_REGISTRY_PATH, f"{where}.canonical must be snake_case")
                    continue
                if canonical in canonical_words:
                    lint.fail(CANONICAL_LEXEME_REGISTRY_PATH, f"{where} duplicates `{canonical}`")
                canonical_words.add(canonical)
                if not isinstance(aliases, list) or not aliases:
                    lint.fail(CANONICAL_LEXEME_REGISTRY_PATH, f"{where}.forbidden_aliases must be non-empty")
                    continue
                for alias in aliases:
                    if not isinstance(alias, str) or not SNAKE_CASE_RE.fullmatch(alias):
                        lint.fail(CANONICAL_LEXEME_REGISTRY_PATH, f"{where} has invalid alias `{alias}`")
                        continue
                    if alias == canonical or alias in forbidden_lexemes:
                        lint.fail(CANONICAL_LEXEME_REGISTRY_PATH, f"{where} duplicates alias `{alias}`")
                    forbidden_lexemes.add(alias)
                qualified_forms = term.get("qualified_external_forms", [])
                if not isinstance(qualified_forms, list):
                    lint.fail(
                        CANONICAL_LEXEME_REGISTRY_PATH,
                        f"{where}.qualified_external_forms must be an array",
                    )
                else:
                    for form_index, form in enumerate(qualified_forms):
                        if not isinstance(form, dict) or not all(
                            isinstance(form.get(field), str) and form.get(field)
                            for field in ("name", "boundary", "reason", "external_anchor")
                        ):
                            lint.fail(
                                CANONICAL_LEXEME_REGISTRY_PATH,
                                f"{where}.qualified_external_forms[{form_index}] is incomplete",
                            )
                            continue
                        lexeme_qualified_external_forms.add(form["name"])
        exception_rows = lexeme_registry.get("exact_non_contract_exceptions")
        if not isinstance(exception_rows, list):
            lint.fail(
                CANONICAL_LEXEME_REGISTRY_PATH,
                "exact_non_contract_exceptions must be an array",
            )
        else:
            for index, exception in enumerate(exception_rows):
                where = f"exact_non_contract_exceptions[{index}]"
                if not isinstance(exception, dict) or not all(
                    isinstance(exception.get(field), str) and exception.get(field)
                    for field in ("file", "json_path", "name", "basis", "reason", "external_anchor")
                ):
                    lint.fail(CANONICAL_LEXEME_REGISTRY_PATH, f"{where} is incomplete")
                    continue
                file_name = exception["file"]
                if not (ROOT / file_name).exists():
                    lint.fail(CANONICAL_LEXEME_REGISTRY_PATH, f"{where} names a missing file")
                key = (file_name, exception["json_path"], exception["name"])
                if key in lexeme_non_contract_exceptions:
                    lint.fail(CANONICAL_LEXEME_REGISTRY_PATH, f"{where} duplicates an exception")
                lexeme_non_contract_exceptions.add(key)
    if forbidden_lexemes != set(DEFAULT_FORBIDDEN_LEXEMES):
        lint.fail(
            CANONICAL_LEXEME_REGISTRY_PATH,
            "canonical forbidden aliases disagree with the executable predicate table: "
            f"registry={sorted(forbidden_lexemes)}, predicate={sorted(DEFAULT_FORBIDDEN_LEXEMES)}",
        )

    dto_schema_path = ARTIFACTS / "schemas" / "service-operation-dtos.schema.json"
    dto_schema = load_json(lint, dto_schema_path)
    if isinstance(dto_schema, dict):
        dto_defs = dto_schema.get("$defs")
        if isinstance(dto_defs, dict):
            for type_name in dto_defs:
                if UNFOLDED_PASCAL_ACRONYM_RE.search(type_name):
                    lint.fail(
                        dto_schema_path,
                        f"NC-TYPE-001 type name must fold acronym segments as ordinary "
                        f"PascalCase words: {type_name}",
                    )

    openapi_path = ARTIFACTS / "openapi" / "arkret-service-api.openapi.yaml"
    openapi = load_yaml(lint, openapi_path)
    if isinstance(openapi, dict):
        components = openapi.get("components")
        schemas = components.get("schemas") if isinstance(components, dict) else None
        if isinstance(schemas, dict):
            for type_name in schemas:
                if UNFOLDED_PASCAL_ACRONYM_RE.search(type_name):
                    lint.fail(
                        openapi_path,
                        f"NC-TYPE-001 component name must fold acronym segments as ordinary "
                        f"PascalCase words: {type_name}",
                    )

    evidence_audit = load_json(lint, EVIDENCE_MATERIAL_AUDIT_PATH)
    if isinstance(evidence_audit, dict):
        if evidence_audit.get("source_of_truth") is not False:
            lint.fail(
                EVIDENCE_MATERIAL_AUDIT_PATH,
                "the evidence audit is derived from schemas and registries, not a truth source",
            )
        registrations = evidence_audit.get("registrations")
        expected_evidence_keys: dict[tuple[str, str], int] = {}
        if not isinstance(registrations, list):
            lint.fail(EVIDENCE_MATERIAL_AUDIT_PATH, "registrations must be an array")
            registrations = []
        allowed_dispositions = {
            "polymorphic_container",
            "derived_summary",
            "qualifier",
            "registry_contract",
        }
        material_family_names = {
            "proof",
            "attestation",
            "receipt",
            "commitment",
            "transcript",
        }
        for index, registration in enumerate(registrations):
            where = f"registrations[{index}]"
            if not isinstance(registration, dict):
                lint.fail(EVIDENCE_MATERIAL_AUDIT_PATH, f"{where} must be an object")
                continue
            file_name = registration.get("file")
            key = registration.get("key")
            occurrences = registration.get("occurrences")
            disposition = registration.get("disposition")
            reason = registration.get("reason")
            if not isinstance(file_name, str) or not isinstance(key, str) or "evidence" not in key:
                lint.fail(EVIDENCE_MATERIAL_AUDIT_PATH, f"{where} has an invalid file/key")
                continue
            pair = (file_name, key)
            if pair in expected_evidence_keys:
                lint.fail(EVIDENCE_MATERIAL_AUDIT_PATH, f"{where} duplicates {file_name}:{key}")
            if not isinstance(occurrences, int) or occurrences < 1:
                lint.fail(EVIDENCE_MATERIAL_AUDIT_PATH, f"{where}.occurrences must be positive")
                continue
            expected_evidence_keys[pair] = occurrences
            if disposition not in allowed_dispositions:
                lint.fail(EVIDENCE_MATERIAL_AUDIT_PATH, f"{where} has an unknown disposition")
            if not isinstance(reason, str) or not reason.strip():
                lint.fail(EVIDENCE_MATERIAL_AUDIT_PATH, f"{where} must explain the adjudication")
            families = registration.get("material_families", [])
            if disposition == "polymorphic_container":
                if (
                    not isinstance(families, list)
                    or len(set(families)) < 2
                    or any(family not in material_family_names for family in families)
                ):
                    lint.fail(
                        EVIDENCE_MATERIAL_AUDIT_PATH,
                        f"{where} must register at least two distinct material families",
                    )
            elif families:
                lint.fail(
                    EVIDENCE_MATERIAL_AUDIT_PATH,
                    f"{where} may declare material_families only for a polymorphic container",
                )

        actual_evidence_keys: dict[tuple[str, str], int] = {}

        def count_evidence_keys(file_name: str, node: Any) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    if "evidence" in key:
                        pair = (file_name, key)
                        actual_evidence_keys[pair] = actual_evidence_keys.get(pair, 0) + 1
                    count_evidence_keys(file_name, value)
            elif isinstance(node, list):
                for value in node:
                    count_evidence_keys(file_name, value)

        evidence_scope = [
            *(ARTIFACTS / "schemas").glob("*.json"),
            *(ARTIFACTS / "registry").glob("*.json"),
        ]
        for evidence_path in sorted(evidence_scope):
            evidence_data = load_json(lint, evidence_path)
            if evidence_data is not None:
                count_evidence_keys(evidence_path.name, evidence_data)
        if actual_evidence_keys != expected_evidence_keys:
            missing = sorted(set(actual_evidence_keys) - set(expected_evidence_keys))
            stale = sorted(set(expected_evidence_keys) - set(actual_evidence_keys))
            count_drift = sorted(
                (pair, expected_evidence_keys[pair], actual_evidence_keys[pair])
                for pair in set(expected_evidence_keys) & set(actual_evidence_keys)
                if expected_evidence_keys[pair] != actual_evidence_keys[pair]
            )
            lint.fail(
                EVIDENCE_MATERIAL_AUDIT_PATH,
                f"evidence adjudication drift: unregistered={missing}, stale={stale}, "
                f"count_drift={count_drift}",
            )
        actual_occurrence_count = sum(actual_evidence_keys.values())
        if evidence_audit.get("audited_occurrence_count") != actual_occurrence_count:
            lint.fail(
                EVIDENCE_MATERIAL_AUDIT_PATH,
                "audited_occurrence_count does not match the registered schema/registry key count",
            )

    # ------------------------------------------------------------------
    # Exact-path exception index. A naming exception is only meaningful for
    # the schema location its external anchor actually covers; a name-only
    # allowlist silently exports that grant to every other schema.
    # ------------------------------------------------------------------
    def index_exact_paths(source_path: Path, rows: Any, where: str) -> dict[tuple[str, str, str], dict]:
        index: dict[tuple[str, str, str], dict] = {}
        if not isinstance(rows, list):
            if rows is not None:
                lint.fail(source_path, f"{where} must be an array")
            return index
        for row in rows:
            if not isinstance(row, dict):
                lint.fail(source_path, f"{where} entries must be objects")
                continue
            file_name = row.get("file")
            pointer = row.get("pointer")
            name = row.get("name")
            if not isinstance(file_name, str) or not isinstance(pointer, str) or not isinstance(name, str):
                lint.fail(source_path, f"{where} entry needs string file/pointer/name")
                continue
            if not pointer.startswith("/"):
                lint.fail(source_path, f"{where} pointer `{pointer}` must be an RFC 6901 pointer")
                continue
            key = (file_name, pointer, name)
            if key in index:
                lint.fail(source_path, f"{where} duplicates {file_name}#{pointer}")
                continue
            index[key] = row
        return index

    rejected_wrapper_words = tuple(rules_data.get("rejected_wrapper_words", ()))
    if not rejected_wrapper_words:
        lint.fail(NAMING_RULES_PATH, "NC-TYPE-001 needs a registered rejected_wrapper_words list")
    elif tuple(DEFAULT_REJECTED_WRAPPER_WORDS) != rejected_wrapper_words:
        lint.fail(
            NAMING_RULES_PATH,
            "rejected_wrapper_words must match the predicate table used by the registered cases",
        )

    exact_exceptions: dict[str, dict[tuple[str, str, str], dict]] = {}
    for row in rules:
        if not isinstance(row, dict):
            continue
        rule_id = row.get("rule_id")
        if not isinstance(rule_id, str):
            continue
        exact_exceptions[rule_id] = index_exact_paths(
            NAMING_RULES_PATH, row.get("exact_path_exceptions", []), f"{rule_id}.exact_path_exceptions"
        )

    debt_data = load_json(lint, NAMING_DEBT_PATH)
    debt_index: dict[str, dict[tuple[str, str, str], dict]] = {}
    if isinstance(debt_data, dict):
        if debt_data.get("source_of_truth") is not False:
            lint.fail(NAMING_DEBT_PATH, "debt baseline is a transient ledger, not a truth source")
        entries = debt_data.get("entries")
        grouped: dict[str, list] = {}
        if isinstance(entries, list):
            for entry in entries:
                if not isinstance(entry, dict):
                    lint.fail(NAMING_DEBT_PATH, "entries must be objects")
                    continue
                rule_id = entry.get("rule_id")
                if rule_id not in PREDICATES:
                    lint.fail(NAMING_DEBT_PATH, f"unknown rule_id `{rule_id}`")
                    continue
                if entry.get("basis") == "external_literal" or entry.get("external_anchor"):
                    lint.fail(
                        NAMING_DEBT_PATH,
                        f"{rule_id} debt must not claim an external anchor; register it as a "
                        f"rule exception instead",
                    )
                if not entry.get("owner_batch") or not entry.get("reason"):
                    lint.fail(NAMING_DEBT_PATH, f"{rule_id} debt needs owner_batch and reason")
                grouped.setdefault(rule_id, []).append(entry)
        elif entries is not None:
            lint.fail(NAMING_DEBT_PATH, "entries must be an array")
        for rule_id, rows_for_rule in grouped.items():
            debt_index[rule_id] = index_exact_paths(
                NAMING_DEBT_PATH, rows_for_rule, f"{rule_id} debt"
            )

    matched_exceptions: set[tuple[str, str, str, str]] = set()
    matched_debt: set[tuple[str, str, str, str]] = set()

    def adjudicate(path: Path, rule_id: str, file_name: str, pointer: str, name: str) -> None:
        """Report a violation unless an exact-path exception or debt entry covers it."""

        key = (file_name, pointer, name)
        if key in exact_exceptions.get(rule_id, {}):
            matched_exceptions.add((rule_id, *key))
            return
        if key in debt_index.get(rule_id, {}):
            matched_debt.add((rule_id, *key))
            return
        lint.fail(path, f"{pointer} violates {rule_id} (`{name}`)")

    # ------------------------------------------------------------------
    # Schema surface. One walker feeds both the checks and the coverage proof.
    # ------------------------------------------------------------------
    schema_paths = sorted((ARTIFACTS / "schemas").glob("*.json"))
    schema_documents = {
        schema_path.name: schema_data
        for schema_path in schema_paths
        if (schema_data := load_json(lint, schema_path)) is not None
    }

    def resolve_shape_ref(current_file: str, ref: str) -> tuple[str, Any] | None:
        target, separator, fragment = ref.partition("#")
        target_file = current_file if not target else Path(target).name
        target_document = schema_documents.get(target_file)
        if target_document is None:
            return None
        pointer = f"#{fragment}" if separator else ""
        try:
            return target_file, resolve_json_pointer(target_document, pointer)
        except (KeyError, TypeError, ValueError):
            return None

    reached_names: set[str] = set()
    reached_paths: set[tuple[str, str, str]] = set()
    expected_names: set[str] = set()
    expected_paths: set[tuple[str, str, str]] = set()

    for schema_path in schema_paths:
        schema_data = schema_documents.get(schema_path.name)
        if schema_data is None:
            continue
        file_name = schema_path.name
        expected_names |= naive_property_population(schema_data)
        expected_paths |= {
            (file_name, pointer, name)
            for pointer, name in naive_property_occurrences(schema_data)
        }
        is_dto_mirror = file_name == "service-operation-dtos.schema.json"

        for occurrence in enumerate_schema_properties(file_name, schema_data):
            name = occurrence.name
            pointer = occurrence.pointer
            shape = occurrence.shape
            reached_names.add(name)
            reached_paths.add((file_name, pointer, name))

            shape_is = shape if isinstance(shape, dict) else {}
            if schema_shape_has_type(file_name, shape, "boolean", resolve_shape_ref) and nc_bool_001(
                name
            ):
                adjudicate(schema_path, "NC-BOOL-001", file_name, pointer, name)
            if nc_hash_001(name):
                adjudicate(schema_path, "NC-HASH-001", file_name, pointer, name)
            if nc_count_001(name):
                adjudicate(schema_path, "NC-COUNT-001", file_name, pointer, name)
            if nc_code_001(name):
                adjudicate(schema_path, "NC-CODE-001", file_name, pointer, name)
            if schema_shape_has_type(file_name, shape, "array", resolve_shape_ref) and nc_set_001(
                name
            ):
                adjudicate(schema_path, "NC-SET-001", file_name, pointer, name)
            if nc_evidence_001(name):
                adjudicate(schema_path, "NC-EVIDENCE-001", file_name, pointer, name)
            if nc_lexeme_001(name):
                adjudicate(schema_path, "NC-LEXEME-001", file_name, pointer, name)
            if name == "stage" and isinstance(shape_is.get("enum"), list):
                if set(shape_is["enum"]) != STAGE_VALUES:
                    lint.fail(schema_path, f"{pointer} reuses reserved stage outside the 8-value axis")

        for type_name in enumerate_schema_type_names(file_name, schema_data):
            if is_dto_mirror:
                # The DTO file mirrors OpenAPI PascalCase components. It is exempt
                # from snake_case, not from the wrapper-word and acronym rules.
                violates = (
                    not PASCAL_CASE_RE.fullmatch(type_name.name)
                    or stacked_wrapper_words(type_name.name) is not None
                    or unregistered_wrapper_word(type_name.name, rejected_wrapper_words) is not None
                )
            else:
                violates = not SNAKE_CASE_RE.fullmatch(type_name.name)
            if violates:
                adjudicate(
                    schema_path, "NC-TYPE-001", file_name, type_name.pointer, type_name.name
                )
            # NC-HASH-001 covers Arkret-owned type names as well as wire fields:
            # the type carrying a self-describing digest must not be the one place
            # the forbidden vocabulary survives.
            if nc_hash_001(type_name.name):
                adjudicate(
                    schema_path, "NC-HASH-001", file_name, type_name.pointer, type_name.name
                )
            if nc_lexeme_001(type_name.name):
                adjudicate(
                    schema_path, "NC-LEXEME-001", file_name, type_name.pointer, type_name.name
                )

        for enum_occurrence in enumerate_schema_enums(file_name, schema_data):
            for value in enum_occurrence.values:
                if isinstance(value, str) and value in FORBIDDEN_SYMBOLIC_LITERALS:
                    lint.fail(
                        schema_path,
                        f"{enum_occurrence.pointer} contains non-snake Arkret symbol `{value}`",
                    )
                if isinstance(value, str) and nc_lexeme_001(value):
                    adjudicate(
                        schema_path,
                        "NC-LEXEME-001",
                        file_name,
                        enum_occurrence.pointer,
                        value,
                    )

    # Coverage proof. Both figures must be total: a walker that stops descending
    # would otherwise shrink the enforced surface without failing anything.
    missing_names = sorted(expected_names - reached_names)
    if missing_names:
        lint.fail(
            NAMING_RULES_PATH,
            f"naming walker missed {len(missing_names)} distinct property names, e.g. "
            f"{missing_names[:5]}",
        )
    missing_paths = sorted(expected_paths - reached_paths)
    unexpected_paths = sorted(reached_paths - expected_paths)
    if missing_paths or unexpected_paths:
        lint.fail(
            NAMING_RULES_PATH,
            "naming walker occurrence paths disagree with the independent walk: "
            f"missing={missing_paths[:5]}, unexpected={unexpected_paths[:5]}",
        )

    for artifact_path in raw_artifact_files():
        if nc_artifact_001(artifact_path.name):
            lint.fail(artifact_path, "artifact filename violates NC-ARTIFACT-001 kebab-case rule")

    openapi_path = ARTIFACTS / "openapi" / "arkret-service-api.openapi.yaml"
    openapi_components = load_yaml(lint, openapi_path)
    component_schemas = {}
    if isinstance(openapi_components, dict):
        components_node = openapi_components.get("components")
        if isinstance(components_node, dict) and isinstance(components_node.get("schemas"), dict):
            component_schemas = components_node["schemas"]
    for component in component_schemas:
        if not isinstance(component, str):
            continue
        if (
            stacked_wrapper_words(component) is not None
            or unregistered_wrapper_word(component, rejected_wrapper_words) is not None
        ):
            adjudicate(
                openapi_path,
                "NC-TYPE-001",
                openapi_path.name,
                f"/components/schemas/{component}",
                component,
            )
        if nc_lexeme_001(component):
            adjudicate(
                openapi_path,
                "NC-LEXEME-001",
                openapi_path.name,
                f"/components/schemas/{component}",
                component,
            )

    # Staleness is judged only after every surface has been adjudicated, so an
    # entry is reported stale because the violation is gone, not because its
    # surface had not been visited yet.
    stale_exceptions = [
        f"{rule_id}:{key[0]}#{key[1]}"
        for rule_id, rows_for_rule in exact_exceptions.items()
        for key in rows_for_rule
        if (rule_id, *key) not in matched_exceptions
    ]
    if stale_exceptions:
        lint.fail(
            NAMING_RULES_PATH,
            f"exact-path naming exceptions no longer match a violation: {sorted(stale_exceptions)}",
        )

    stale_debt = [
        f"{rule_id}:{key[0]}#{key[1]}"
        for rule_id, rows_for_rule in debt_index.items()
        for key in rows_for_rule
        if (rule_id, *key) not in matched_debt
    ]
    if stale_debt:
        lint.fail(
            NAMING_DEBT_PATH,
            f"debt entries no longer match a violation and must be deleted: {sorted(stale_debt)}",
        )

    # Registered cases are executed, not merely counted. A rule cannot claim
    # coverage unless its predicate actually decides its own candidates.
    case_rule_ids: set[str] = set()
    for case_field, expected_reject in (("negative_cases", True), ("positive_cases", False)):
        cases = rules_data.get(case_field, [])
        if not isinstance(cases, list):
            lint.fail(NAMING_RULES_PATH, f"{case_field} must be an array")
            continue
        for case in cases:
            if not isinstance(case, dict):
                lint.fail(NAMING_RULES_PATH, f"{case_field} entries must be objects")
                continue
            rule_id = case.get("rule_id")
            candidate = case.get("candidate")
            expected = case.get("expected")
            predicate = PREDICATES.get(rule_id) if isinstance(rule_id, str) else None
            if predicate is None:
                lint.fail(NAMING_RULES_PATH, f"{case_field} references unknown rule `{rule_id}`")
                continue
            if not isinstance(candidate, str) or expected not in {"reject", "accept"}:
                lint.fail(NAMING_RULES_PATH, f"{rule_id} {case_field} entry is malformed")
                continue
            if (expected == "reject") is not expected_reject:
                lint.fail(
                    NAMING_RULES_PATH,
                    f"{rule_id} case `{candidate}` is filed under {case_field} but expects {expected}",
                )
                continue
            if predicate(candidate) is not (expected == "reject"):
                lint.fail(
                    NAMING_RULES_PATH,
                    f"{rule_id} predicate disagrees with registered case `{candidate}` "
                    f"(expected {expected})",
                )
            case_rule_ids.add(rule_id)

    required_case_ids = set(PREDICATES)
    if case_rule_ids != required_case_ids:
        lint.fail(
            NAMING_RULES_PATH,
            f"every predicate needs executed cases: missing="
            f"{sorted(required_case_ids - case_rule_ids)}, "
            f"unknown={sorted(case_rule_ids - required_case_ids)}",
        )

    for row in rules:
        if not isinstance(row, dict):
            continue
        rule_id = row.get("rule_id")
        enforcement = row.get("enforcement")
        if enforcement not in {"predicate", "registry", "predicate+registry"}:
            lint.fail(
                NAMING_RULES_PATH,
                f"{rule_id} must declare enforcement as predicate, registry or predicate+registry",
            )

    def check_key(path: Path, relative_path: str, where: str, key: str | None) -> None:
        if not key:
            return
        exception_key = (relative_path, where, key)
        if exception_key in lexeme_non_contract_exceptions:
            matched_lexeme_non_contract_exceptions.add(exception_key)
            return
        if re.fullmatch(r"(?!ak\.)[a-z0-9]+(?:\.[a-z0-9]+){2,}", key):
            # Reverse-DNS extension keys are externally owned namespaces, not
            # Arkret contract lexemes (for example org.example.work).
            return
        replacement = FORBIDDEN_NAMING_ALIAS_KEYS.get(key)
        if replacement:
            lint.fail(path, f"{where} uses forbidden legacy field `{key}`; use `{replacement}`")
            return
        if nc_lexeme_001(key):
            lint.fail(path, f"{where} violates NC-LEXEME-001 (`{key}`)")
            return
        if key != "principal_server_did" and (key == "service_did" or "_service_did" in key):
            lint.fail(
                path,
                f"{where} uses forbidden legacy service identity field `{key}`; "
                f"use `{key.replace('service_did', 'service_id')}`",
            )

    name_value_fields = {
        "actor_kind",
        "claim_kind",
        "event_kind",
        "kind",
        "operation_id",
        "profile_id",
        "schema_id",
        "type",
    }

    def check_json_value(path: Path, data: Any, where: str = "$") -> None:
        relative_path = path.resolve().relative_to(ROOT.resolve()).as_posix()
        for json_path, value, key in walk_json(data, where):
            check_key(path, relative_path, json_path, key)
            if not isinstance(value, str):
                continue
            if value in lexeme_qualified_external_forms:
                continue
            if (
                path == CANONICAL_LEXEME_REGISTRY_PATH
                and ".forbidden_aliases[" in json_path
            ):
                # This registry is the executable negative vocabulary. Its
                # rejected spellings are rule input, not live contract values.
                continue
            is_contract_name = (
                key in name_value_fields
                or value.startswith("ak.")
                or value.startswith("arkret_")
            )
            if is_contract_name and nc_lexeme_001(value):
                lint.fail(path, f"{json_path} violates NC-LEXEME-001 (`{value}`)")

    json_paths = [p for p in all_json_files() if not is_wire_guard_file(p)]
    for path in json_paths:
        data = load_json(lint, path)
        if data is not None:
            check_json_value(path, data)

    # Prose may discuss historical spellings. Only machine objects and declared
    # JSON examples are naming-contract inputs; raw-word blacklists create false
    # positives when protocol rationale names a rejected spelling.
    for path in markdown_files():
        text = read_text(path)
        for match in JSON_FENCE_RE.finditer(text):
            try:
                data = parse_json_text(match.group("body"))
            except Exception:
                continue
            line_no = text.count("\n", 0, match.start()) + 1
            check_json_value(path, data, f"json block line {line_no}")

    stale_lexeme_exceptions = sorted(
        lexeme_non_contract_exceptions - matched_lexeme_non_contract_exceptions
    )
    if stale_lexeme_exceptions:
        lint.fail(
            CANONICAL_LEXEME_REGISTRY_PATH,
            f"exact_non_contract_exceptions no longer match a violation: {stale_lexeme_exceptions}",
        )



def check_profile_dependency_graph(lint: Lint) -> None:
    """Keep the generated profile graph aligned with its canonical requirements."""

    profiles_path = ARTIFACTS / "profiles" / "conformance-profiles.json"
    graph_path = ARTIFACTS / "registry" / "profiles-dependency-graph.json"
    profiles = load_json(lint, profiles_path)
    graph = load_json(lint, graph_path)
    if not isinstance(profiles, dict) or not isinstance(graph, dict):
        return
    requirements = profiles.get("profile_requirements")
    if not isinstance(requirements, dict):
        lint.fail(profiles_path, "profile_requirements must be an object")
        return
    expected_nodes = set(requirements)
    expected_edges: set[tuple[str, str, str]] = set()
    for profile_id, requirement in requirements.items():
        if not isinstance(requirement, dict):
            continue
        for field, kind in (
            ("inherits", "inherits"),
            ("depends_on", "depends_on"),
            ("mutually_exclusive_with", "mutually_exclusive_with"),
        ):
            for target in requirement.get(field, []):
                if isinstance(target, str):
                    expected_edges.add((profile_id, target, kind))
    actual_nodes = set(graph.get("nodes", []))
    actual_edges = {
        (row.get("from"), row.get("to"), row.get("kind"))
        for row in graph.get("edges", [])
        if isinstance(row, dict)
    }
    if actual_nodes != expected_nodes:
        lint.fail(graph_path, "generated profile graph nodes drift from profile_requirements")
    if actual_edges != expected_edges:
        lint.fail(graph_path, "generated profile graph edges drift from profile_requirements")
    if graph.get("source_of_truth") is not False:
        lint.fail(graph_path, "generated profile graph must not claim source_of_truth")



def check_common_object_field_matrix(lint: Lint) -> None:
    """Check the derived §3.1 matrix and its conditional View lifecycle cells."""

    matrix = load_json(lint, COMMON_OBJECT_FIELD_MATRIX_PATH)
    prose_path = SPEC_ROOT / "zh" / "models" / "common-fields.md"
    if not isinstance(matrix, dict):
        return
    lines = prose_path.read_text(encoding="utf-8").splitlines()
    try:
        start = next(
            index
            for index, line in enumerate(lines)
            if line.startswith("| 字段 | 组 | Realm | Circle |")
        )
    except StopIteration:
        lint.fail(prose_path, "§3.1 matrix header is missing")
        return
    headers = [cell.strip() for cell in lines[start].strip("|").split("|")]
    prose_rows: list[dict[str, str]] = []
    for line in lines[start + 2 :]:
        if not line.startswith("|"):
            break
        values = [cell.strip() for cell in line.strip("|").split("|")]
        if len(values) != len(headers):
            lint.fail(prose_path, f"§3.1 matrix row has {len(values)} cells, expected {len(headers)}")
            continue
        prose_rows.append(dict(zip(headers, values)))
    if matrix.get("headers") != headers or matrix.get("rows") != prose_rows:
        lint.fail(COMMON_OBJECT_FIELD_MATRIX_PATH, "derived matrix drifts from common-fields.md §3.1")

    by_field = {row.get("字段"): row for row in prose_rows}
    view_schema_path = ARTIFACTS / "schemas" / "view.schema.json"
    view_schema = load_json(lint, view_schema_path)
    if not isinstance(view_schema, dict):
        return
    view_properties = view_schema.get("properties", {})
    view_required = view_schema.get("required", [])
    if "state" not in view_required:
        lint.fail(view_schema_path, "View.state must be explicitly required; missing state is not a valid wire shape")
    state_property = view_properties.get("state", {}) if isinstance(view_properties, dict) else {}
    if isinstance(state_property, dict) and "default" in state_property:
        lint.fail(view_schema_path, "View.state must not declare a default")
    for raw_field, row in by_field.items():
        if not isinstance(raw_field, str) or not isinstance(row, dict):
            continue
        field = raw_field.strip("`")
        cell = row.get("View", "")
        present = field in view_properties
        if cell.startswith("—") and present:
            lint.fail(view_schema_path, f"§3.1 View.{field} is not applicable but schema declares it")
        if not cell.startswith("—") and not present and "/" not in field:
            lint.fail(view_schema_path, f"§3.1 View.{field} is applicable but schema omits it")
    state_rule = next(
        (
            rule
            for rule in view_schema.get("allOf", [])
            if isinstance(rule, dict)
            and ((rule.get("if") or {}).get("properties") or {}).get("state")
            == {"const": "tombstoned"}
        ),
        None,
    )
    if not isinstance(state_rule, dict) or "state_changed_at" not in (
        (state_rule.get("then") or {}).get("required") or []
    ):
        lint.fail(view_schema_path, "View.state_changed_at must be conditionally required for tombstoned")



def check_keypackage_claim_proof_shape(lint: Lint) -> None:
    """Self/peer claim share one closed requester authorization and service binding."""

    path = ARTIFACTS / "schemas" / "keypackage-operations.schema.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return
    claim = ((data.get("$defs") or {}).get("keypackages_claim_request_body") or {})
    if not isinstance(claim, dict):
        lint.fail(path, "$defs.keypackages_claim_request_body must exist")
        return
    required = claim.get("required") or []
    properties = claim.get("properties") or {}
    for field, ref in (
        ("requester_authorization", "#/$defs/requester_authorization"),
        ("service_binding", "#/$defs/keypackages_claim_service_binding"),
    ):
        if field not in required:
            lint.fail(path, f"unified KeyPackage claim must require {field}")
        definition = properties.get(field) if isinstance(properties, dict) else None
        if not isinstance(definition, dict) or definition.get("$ref") != ref:
            lint.fail(path, f"unified KeyPackage claim {field} must directly reference {ref}")
    if isinstance(properties, dict):
        for legacy in ("holder_acceptance_proof", "proofs", "transport_binding"):
            if legacy in properties:
                lint.fail(path, f"unified KeyPackage claim must not retain legacy {legacy}")



def check_event_proof_digest_shape(lint: Lint) -> None:
    """Event proofs must use event_digest, not generic payload_hash."""

    path = ARTIFACTS / "schemas" / "event-envelope.schema.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return

    proofs = (((data.get("properties") or {}).get("proofs") or {}).get("items") or {})
    if proofs.get("$ref") != "#/$defs/event_proof":
        lint.fail(path, "Event.properties.proofs.items must reference $defs/event_proof")

    event_proof = ((data.get("$defs") or {}).get("event_proof") or {})
    if not isinstance(event_proof, dict):
        lint.fail(path, "$defs.event_proof must exist")
        return

    required = event_proof.get("required") or []
    properties = event_proof.get("properties") or {}
    if "event_digest" not in required or "event_digest" not in properties:
        lint.fail(path, "$defs.event_proof must require event_digest")
    if "payload_hash" in required or "payload_hash" in properties:
        lint.fail(path, "$defs.event_proof must not expose payload_hash; use event_digest")



def check_legacy_announce_id_form(lint: Lint) -> None:
    """Reject the pre-registry Directory announce id spelling.

    ``ann_<hex>`` appeared in prose before Directory announce records were
    registered as typed IDs. The canonical v1 wire form is now
    ``ak:announce:<uuidv7>``; keeping this guard prevents examples or fixtures
    from reintroducing the unregistered local prefix.
    """
    scan_paths = sorted(SPEC_ROOT.rglob("*.md"))
    scan_paths.extend(raw_artifact_files())
    for path in scan_paths:
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            if LEGACY_ANNOUNCE_ID_RE.search(line):
                lint.fail(
                    path,
                    f"line {line_no}: legacy Directory announce id form `ann_*` is forbidden; "
                    "use `ak:announce:<uuidv7>`.",
                )



def check_join_policy_gate_id_uniqueness(lint: Lint) -> None:
    """Enforce property-level gate_id uniqueness within join_policy gates[].

    JSON Schema 2020-12 has no native "unique by property" keyword: ``uniqueItems``
    only catches whole-object duplicates. The wire contract for
    ``ak.realm.join_policy`` (see zh/governance/join-policy.md §3.1) requires that
    ``gate_id`` be unique across siblings in ``gates[]`` so that audit refs in
    ``ak.member.state{gate_proofs[gate_id=…]}`` remain unambiguous; the canonical
    reject reason is ``schema_violation reason_code=join_policy_duplicate_gate_id``.

    This lint walks every JSON artifact and every Markdown ``json`` example,
    finds objects that look like a join_policy value (have a ``gates`` array
    whose items have ``gate_id``), and rejects any with duplicate ``gate_id``
    across siblings. Markdown blocks demonstrating the negative case MUST be
    annotated with ``expect=invalid first_error="join_policy_duplicate_gate_id"``
    in their fence header to be exempted (matching the existing negative-case
    convention used elsewhere in this linter).
    """

    def walk(value: Any, on_object: Any) -> None:
        if isinstance(value, dict):
            on_object(value)
            for child in value.values():
                walk(child, on_object)
        elif isinstance(value, list):
            for child in value:
                walk(child, on_object)

    def check_value(path: Path, value: Any, where: str) -> None:
        def on_object(obj: dict) -> None:
            gates = obj.get("gates")
            if not isinstance(gates, list) or not gates:
                return
            # heuristic: items must look like join_policy gates (have gate_id+kind)
            looks_like_join_policy = all(
                isinstance(g, dict) and "gate_id" in g and "kind" in g
                for g in gates
            )
            if not looks_like_join_policy:
                return
            seen: set[str] = set()
            for g in gates:
                gid = g.get("gate_id")
                if not isinstance(gid, str):
                    continue
                if gid in seen:
                    lint.fail(
                        path,
                        f"{where}: join_policy gates[] contains duplicate gate_id "
                        f"'{gid}' — see error-code-registry reason "
                        f"`join_policy_duplicate_gate_id` and join-policy.md §3.1.",
                    )
                    return
                seen.add(gid)

        walk(value, on_object)

    # JSON files under artifacts/
    for path in all_json_files():
        if ARTIFACTS not in path.parents:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        check_value(path, data, "value")

    # Markdown json fences
    fence_re = re.compile(r"```json([^\n]*)\n(.*?)```", re.DOTALL)
    for path in markdown_files():
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for match in fence_re.finditer(text):
            header = match.group(1) or ""
            body = match.group(2)
            # Skip explicit negative cases tagged in the fence header
            if "join_policy_duplicate_gate_id" in header and "expect=invalid" in header:
                continue
            try:
                data = json.loads(body)
            except Exception:
                continue
            line_no = text.count("\n", 0, match.start()) + 1
            check_value(path, data, f"json block at line {line_no}")



def check_join_policy_question_budget(lint: Lint) -> None:
    """Keep the policy-wide application_form question budget satisfiable.

    A join policy may carry up to 16 gates and each ``application_form`` gate up
    to 64 ``questions[]``, while one application carries at most 64
    ``answers[]``. Without a policy-wide budget, ``combinator=all`` admits a
    policy whose ``required=true`` questions cannot all be answered by any legal
    application — the applicant only discovers it at submit time, and the
    reference key (gate_id, question_id) does not help.

    The budget is the same machine constant as the ``answers[]`` cap, so the two
    sides can never drift: the sum of ``questions[]`` over all
    ``application_form`` gates of one policy MUST NOT exceed it. JSON Schema
    2020-12 cannot express a sum across array items, so this follows the
    ``gate_id`` uniqueness precedent: schema caps each side, this lint holds
    artifacts and prose examples, and the reducer rejects on the wire with
    ``schema_violation reason_code=join_policy_question_budget_exceeded``. See
    zh/governance/join-policy.md §3.3.
    """

    answers_cap = None
    operations = load_json(lint, ARTIFACTS / "schemas" / "join-policy-operations.schema.json")
    if isinstance(operations, dict):
        answers_cap = (
            operations.get("$defs", {})
            .get("server_protected_body", {})
            .get("properties", {})
            .get("answers", {})
            .get("maxItems")
        )
    if not isinstance(answers_cap, int) or answers_cap <= 0:
        lint.fail(
            ARTIFACTS / "schemas" / "join-policy-operations.schema.json",
            "server_protected_body.answers must declare a positive maxItems to anchor the "
            "join-policy question budget",
        )
        return

    def walk(value: Any, on_object: Any) -> None:
        if isinstance(value, dict):
            on_object(value)
            for child in value.values():
                walk(child, on_object)
        elif isinstance(value, list):
            for child in value:
                walk(child, on_object)

    def check_value(path: Path, value: Any, where: str) -> None:
        def on_object(obj: dict) -> None:
            gates = obj.get("gates")
            if not isinstance(gates, list) or not gates:
                return
            if not all(
                isinstance(gate, dict) and "gate_id" in gate and "kind" in gate
                for gate in gates
            ):
                return
            total = 0
            for gate in gates:
                if gate.get("kind") != "application_form":
                    continue
                questions = gate.get("questions")
                if isinstance(questions, list):
                    total += len(questions)
            if total > answers_cap:
                lint.fail(
                    path,
                    f"{where}: join_policy declares {total} application_form questions across "
                    f"gates[], over the {answers_cap} answers[] budget — see error-code-registry "
                    "reason `join_policy_question_budget_exceeded` and join-policy.md §3.3.",
                )

        walk(value, on_object)

    for path in all_json_files():
        if ARTIFACTS not in path.parents:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        check_value(path, data, "value")

    fence_re = re.compile(r"```json([^\n]*)\n(.*?)```", re.DOTALL)
    for path in markdown_files():
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for match in fence_re.finditer(text):
            header = match.group(1) or ""
            body = match.group(2)
            if "join_policy_question_budget_exceeded" in header and "expect=invalid" in header:
                continue
            try:
                data = json.loads(body)
            except Exception:
                continue
            line_no = text.count("\n", 0, match.start()) + 1
            check_value(path, data, f"json block at line {line_no}")



def check_content_composite_uses_parts(lint: Lint) -> None:
    """Reject legacy ``blocks`` spelling on ak.content.composite examples.

    The canonical composite child field is required as ``parts``. ``blocks`` is
    too tied to document layout semantics and is now listed in
    forbidden-wire-fields.json for the content_block_composite context. JSON
    Schema rejects it on real wire payloads; this lint keeps artifacts and prose
    JSON examples aligned.
    """

    def walk(value: Any, on_object: Any) -> None:
        if isinstance(value, dict):
            on_object(value)
            for child in value.values():
                walk(child, on_object)
        elif isinstance(value, list):
            for child in value:
                walk(child, on_object)

    def check_value(path: Path, value: Any, where: str) -> None:
        def on_object(obj: dict) -> None:
            if obj.get("kind") != "ak.content.composite":
                return
            if "blocks" in obj:
                lint.fail(
                    path,
                    f"{where}: ak.content.composite uses legacy `blocks`; "
                    "canonical wire field is `parts`.",
                )
            if "parts" not in obj:
                lint.fail(
                    path,
                    f"{where}: ak.content.composite is missing required `parts`.",
                )

        walk(value, on_object)

    for path in all_json_files():
        if ARTIFACTS not in path.parents:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        check_value(path, data, "value")

    fence_re = re.compile(r"```json([^\n]*)\n(.*?)```", re.DOTALL)
    for path in markdown_files():
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for match in fence_re.finditer(text):
            header = match.group(1) or ""
            if "content_block_legacy_blocks" in header and "expect=invalid" in header:
                continue
            try:
                data = json.loads(match.group(2))
            except Exception:
                continue
            line_no = text.count("\n", 0, match.start()) + 1
            check_value(path, data, f"json block at line {line_no}")


def check_markdown_links(lint: Lint) -> None:
    for path in markdown_files():
        text = path.read_text(encoding="utf-8")
        for target in MARKDOWN_LINK_RE.findall(text):
            if not target or target.startswith("#"):
                continue
            if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                continue
            target_path = split_ref(target)
            if not target_path:
                continue
            resolved = (path.parent / target_path).resolve()
            try:
                resolved.relative_to(ROOT.resolve())
            except ValueError:
                lint.fail(path, f"markdown link escapes repository: {target}")
                continue
            if not resolved.exists():
                lint.fail(path, f"markdown link target does not exist: {target}")



def check_envelope_subject_source_whitelist(lint: Lint) -> None:
    """Reconcile the §9.5.1 prose whitelist with what the registry actually uses.

    Three statements of the same closed set have to agree: the sentence in
    `encoding.md` §9.5.1, [`ENVELOPE_SUBJECT_SOURCES`], and the envelope sources
    the registry really reads. Nothing compared them before, and they diverged:
    §9.5.1 forbade `envelope.event_id` as a cell subject in prose while six
    registered create kinds were already using it, and the release gate was green
    on both sides — the per-occurrence lint only ever checked each registry row
    against its own hard-coded copy of the list.

    An unused whitelist entry fails too. A permission the registry does not
    exercise is exactly the state that lets the prose and the registry drift
    apart unnoticed.
    """
    prose_path = SPEC_ROOT / "zh" / "conformance" / "encoding.md"
    if not prose_path.exists():
        lint.fail(prose_path, "encoding.md is missing")
        return
    text = read_text(prose_path)

    # The sentence that states the whitelist. Anchored on the phrase rather than a
    # section digest so rewording the surrounding paragraph stays free, while
    # deleting or renaming the whitelist sentence fails loudly.
    sentence = next(
        (line for line in text.splitlines() if "envelope 来源白名单" in line),
        None,
    )
    if sentence is None:
        lint.fail(
            prose_path,
            "§9.5.1 must keep a sentence naming the closed `envelope 来源白名单`; "
            "the machine check reads its members from there",
        )
        return
    prose_sources = set(re.findall(r"`(envelope\.[A-Za-z0-9_.]+)`", sentence))
    declared = set(ENVELOPE_SUBJECT_SOURCES)
    forbidden = set(ENVELOPE_SUBJECT_FORBIDDEN)
    if prose_sources != declared | forbidden:
        lint.fail(
            prose_path,
            "§9.5.1 whitelist sentence names "
            f"{sorted(prose_sources)} but the lint declares whitelist="
            f"{sorted(declared)} forbidden={sorted(forbidden)}",
        )

    # What the registry actually reads. Only `registry/`: a fixture negative case
    # legitimately names a forbidden source in order to assert its rejection.
    used: dict[str, list[str]] = {}

    def collect(node: Any, owner: Path, json_path: str) -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                collect(child, owner, f"{json_path}.{key}")
        elif isinstance(node, list):
            for index, child in enumerate(node):
                collect(child, owner, f"{json_path}[{index}]")
        elif isinstance(node, str) and node.startswith("envelope."):
            used.setdefault(node, []).append(f"{owner.name}{json_path}")

    for registry_path in sorted((ARTIFACTS / "registry").glob("*.json")):
        registry = load_json(lint, registry_path)
        if registry is not None:
            collect(registry, registry_path, "$")

    for source, where in sorted(used.items()):
        if source in forbidden:
            lint.fail(
                ARTIFACTS / "registry",
                f"§9.5.1 forbids {source} as a subject source but the registry reads it at "
                f"{where[0]}",
            )
        elif source not in declared:
            lint.fail(
                ARTIFACTS / "registry",
                f"registry reads unregistered envelope source {source} at {where[0]}",
            )
    for source in sorted(declared - set(used)):
        lint.fail(
            prose_path,
            f"§9.5.1 whitelists {source} but no registered cell subject reads it; "
            "a permission nothing exercises is how the prose and the registry drifted apart",
        )



def _request_schema_reaches_signed_event(
    lint: Lint, ref: str, depth: int = 0, seen: set[str] | None = None
) -> bool:
    """Does a request schema reference reach a caller-signed Event?"""
    seen = set() if seen is None else seen
    if depth > 6 or not ref or ref in seen:
        return False
    seen.add(ref)
    file_part, _, fragment = ref.partition("#")
    relative = file_part.lstrip("./")
    if relative and not relative.startswith("schemas/"):
        relative = f"schemas/{relative}"
    if not relative:
        return False
    path = ARTIFACTS / relative
    if not path.is_file():
        return False
    document = load_json(lint, path)
    if document is None:
        return False
    node: Any = document
    if fragment:
        try:
            # `resolve_json_pointer` wants the `#/` form; `partition` dropped the `#`.
            node = resolve_json_pointer(document, f"#{fragment}")
        except (KeyError, IndexError, TypeError, ValueError):
            return False

    def walk(value: Any) -> bool:
        if isinstance(value, dict):
            nested = value.get("$ref")
            if isinstance(nested, str):
                if any(marker in nested for marker in SIGNED_EVENT_REQUEST_MARKERS):
                    return True
                next_ref = nested if ".schema.json" in nested else f"{relative}{nested}"
                if _request_schema_reaches_signed_event(lint, next_ref, depth + 1, seen):
                    return True
            return any(walk(child) for child in value.values())
        if isinstance(value, list):
            return any(walk(child) for child in value)
        return False

    return walk(node)



def check_event_log_operations_carry_a_signed_event(lint: Lint) -> None:
    """An operation that writes an Event MUST take that Event from its caller."""
    path = ARTIFACTS / "registry" / "operation-registry.json"
    registry = load_json(lint, path)
    if not isinstance(registry, dict):
        return
    operations = registry.get("operations")
    if not isinstance(operations, list):
        return

    def authors_event(effect: Any) -> bool:
        if not isinstance(effect, dict):
            return False
        if effect.get("kind") in EVENT_AUTHORING_DURABLE_EFFECT_KINDS:
            return True
        if effect.get("kind") == "branched":
            return any(
                authors_event(branch.get("effect"))
                for branch in effect.get("effect_branches", [])
                if isinstance(branch, dict)
            )
        return False

    unsigned: set[str] = set()
    for operation in operations:
        if not isinstance(operation, dict):
            continue
        effect = operation.get("durable_effect")
        if not authors_event(effect):
            continue
        operation_id = operation.get("operation_id")
        if not isinstance(operation_id, str):
            continue
        request_ref = operation.get("request_schema_ref")
        if isinstance(request_ref, str) and _request_schema_reaches_signed_event(lint, request_ref):
            continue
        unsigned.add(operation_id)
        if operation_id not in EVENT_LOG_OPERATIONS_WITHOUT_A_SIGNED_REQUEST:
            lint.fail(
                path,
                f"{operation_id} declares a durable event_log effect but its request carries no "
                "caller-signed Event, and a service MUST NOT sign one on the caller's behalf "
                "(capabilities.md sections 118/361, key-management.md section 411). Reference "
                "service-operation-dtos.schema.json#/$defs/EventInitialSubmission (or the Event "
                "envelope) from the request body, as the agent lifecycle operations and "
                "applet.command.install already do.",
            )
    for stale in sorted(set(EVENT_LOG_OPERATIONS_WITHOUT_A_SIGNED_REQUEST) - unsigned):
        lint.fail(
            path,
            f"{stale} now carries a caller-signed Event; drop it from "
            "EVENT_LOG_OPERATIONS_WITHOUT_A_SIGNED_REQUEST",
        )



def check_directory_field_drift(lint: Lint) -> None:
    """Directory announce/withdraw prose must not regress to old field names."""
    banned = ("announcement_id", "withdraw_id")
    for path in markdown_files():
        if SPEC_ROOT / "zh" not in path.parents:
            continue
        text = path.read_text(encoding="utf-8")
        for token in banned:
            if token in text:
                lint.fail(path, f"legacy Directory field name present: {token}")



def check_typed_id_prose_consistency(lint: Lint) -> None:
    common_fields = SPEC_ROOT / "zh" / "models" / "common-fields.md"
    encoding = SPEC_ROOT / "zh" / "conformance" / "encoding.md"
    id_registry = ARTIFACTS / "registry" / "id-kind-registry.json"

    common_text = common_fields.read_text(encoding="utf-8")
    if "wire value SHOULD 使用" in common_text:
        lint.fail(common_fields, "typed identifier wire value must be MUST, not SHOULD")
    if "UUID 部分 SHOULD" in common_text:
        lint.fail(common_fields, "typed identifier UUIDv7 rule must be MUST, not SHOULD")
    if "UUID 部分 MUST 使用 UUIDv7（time-ordered）" in common_text:
        lint.fail(common_fields, "typed identifier prose must not require UUIDv7 for event-derived kinds")
    for required_rule in (
        "`producer_allocated` 使用 UUIDv7",
        "`event_derived` 使用",
        "33-octet suite-tagged 完整 digest token",
        "调用点 MUST NOT 自行选择",
    ):
        if required_rule not in common_text:
            lint.fail(common_fields, f"typed identifier dual-form rule missing: {required_rule}")

    for path in [*markdown_files(), *all_json_files()]:
        text = path.read_text(encoding="utf-8")
        for reason in event_derived_uuid_wording_errors(text):
            lint.fail(path, reason)

    encoding_text = encoding.read_text(encoding="utf-8")
    if "`txn`" in encoding_text:
        lint.fail(encoding, "typed ID kind prose must use `transaction`, not `txn`")
    if "principal_id`、`device_id` MUST 是完整 typed ID 或完整 DID URI" in encoding_text:
        lint.fail(encoding, "principal_id/device_id subject rule must distinguish DID from device typed ID")

    registry_text = id_registry.read_text(encoding="utf-8")
    if "any 16-byte token" in registry_text:
        lint.fail(id_registry, "rtc_participant must not permit non-UUIDv7 16-byte tokens")

    allowed_legacy_paths = {(ARTIFACTS / "registry" / "forbidden-wire-fields.json").resolve()}
    for path in [*markdown_files(), *all_json_files()]:
        if path.resolve() in allowed_legacy_paths:
            continue
        if "ak:txn:" in path.read_text(encoding="utf-8"):
            lint.fail(path, "legacy ak:txn: prefix present outside migration/forbidden registries")


_EVENT_DERIVED_UUID_WORDING = re.compile(
    r"(?:\bevent[_ -]?id\s+UUID(?:v7)?\b|\bEvent\s+UUID(?:v7)?\b|"
    r"\bUUID(?:v7)?\b[^。\n]{0,80}\bEvent(?:\.|_)?event_id\b)",
    flags=re.IGNORECASE,
)
_EVENT_DERIVED_UUID_PLACEHOLDER = re.compile(
    r"ak:(?:actor_profile|appeal|audit_binding|audit_session|audit_release|call|circle|event|grant|invite|message|moderation_queue_item|morph|realm|relation|report|session_grant|sidecar|space|strand|view):<uuid(?:v7)?>",
    flags=re.IGNORECASE,
)
_EVENT_DERIVED_SCOPE_UUID_NAME = re.compile(
    r"\b(?:realm|circle|strand)_uuid\b",
    flags=re.IGNORECASE,
)


def event_derived_uuid_wording_errors(text: str) -> list[str]:
    """Return stale UUID descriptions for Event-derived protocol identities."""
    errors = []
    if _EVENT_DERIVED_UUID_WORDING.search(text):
        errors.append(
            "Event ID prose must use the suite-tagged full-digest token, not UUID wording"
        )
    if _EVENT_DERIVED_UUID_PLACEHOLDER.search(text):
        errors.append(
            "event-derived object ID prose must use a complete Event token placeholder, not UUID"
        )
    if _EVENT_DERIVED_SCOPE_UUID_NAME.search(text):
        errors.append(
            "Agent participation scope keys must name complete typed tokens, not *_uuid placeholders"
        )
    return errors



def check_text_reference_targets(lint: Lint) -> None:
    for path in raw_artifact_files():
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for match in TEXT_ARTIFACT_REF_RE.finditer(text):
            ref = match.group(1)
            if ref.startswith("zh/"):
                target = SPEC_ROOT / ref
            elif ref.startswith("schemas/"):
                target = ARTIFACTS / ref
            elif ref.startswith("artifacts/"):
                target = SPEC_ROOT / ref
            else:
                continue
            if not target.exists():
                lint.fail(path, f"text reference target does not exist: {ref}")



def check_cross_source_drift(lint: Lint, known: dict[str, set[str]]) -> None:
    scan_paths = markdown_files() + raw_artifact_files()
    active_event_kinds = sorted(known["active_event_kinds"], key=len, reverse=True)
    allowed_room_scoped = {
        (SPEC_ROOT / "zh" / "extensions" / "mimi-interop.md").resolve(),
    }
    operation_count = len(known["operation_ids"])
    versioned_event_kind_re = re.compile(
        r"(?<![A-Za-z0-9_.-])("
        + "|".join(re.escape(kind) for kind in active_event_kinds)
        + r")\.v[0-9]+\b"
    )

    for path in scan_paths:
        try:
            text = read_text(path.resolve())
        except Exception:
            continue
        resolved = path.resolve()
        for line_no, line in enumerate(text.splitlines(), start=1):
            if (
                re.search(r"\broom[- ]scoped\b", line, re.IGNORECASE)
                and resolved not in allowed_room_scoped
            ):
                lint.fail(path, f"line {line_no}: core docs/artifacts must not use room-scoped; use Realm-scoped")

            if STABLE_SECTION_PLACEHOLDER_RE.search(line):
                lint.fail(path, f"line {line_no}: placeholder section reference must be replaced with a stable heading or real section number")

            if "/arkret/v1/check" in line:
                lint.fail(path, f"line {line_no}: legacy policy path /arkret/v1/check must be replaced with /_arkret/self/policy/check")

            if TRUST_DOMAIN_JSON_DID_RE.search(line):
                lint.fail(path, f"line {line_no}: trust_domain must use ak:trust_domain:<scope>, not a raw DID")

            if LEGACY_DID_METHOD_REGEX_RE.search(line):
                lint.fail(path, f"line {line_no}: DID regex must not allow ':'/'.'/'_' inside the method segment")

            for match in OPERATION_COUNT_RE.finditer(line):
                count = int(match.group(1))
                if count != operation_count:
                    lint.fail(path, f"line {line_no}: hard-coded operation count {count} differs from registry count {operation_count}")

            for match in versioned_event_kind_re.finditer(line):
                lint.fail(
                    path,
                    f"line {line_no}: active Event.kind {match.group(1)} "
                    "must not be written with a .vN suffix",
                )



def check_canonical_digest_alias(lint: Lint) -> None:
    """Keep one exact name for the Event digest preimage across prose and artifacts."""

    forbidden = "envelope_without_proofs_unsigned_reducer_stamps"
    for path in sorted({*markdown_files(), *raw_artifact_files()}):
        if forbidden in read_text(path):
            lint.fail(
                path,
                f"forbidden Event digest preimage alias `{forbidden}`; "
                "use `envelope_without_proofs_unsigned_actor_kind`",
            )



def is_placeholder_typed_id(rest: str) -> bool:
    return (
        "..." in rest
        or rest in {"id", "uuid", "example", "A", "B"}
        or rest.startswith("<")
        or rest.endswith(">")
    )



def check_markdown_json_value(lint: Lint, path: Path, json_path: str, value: Any, key: str | None, known: dict[str, set[str]]) -> None:
    if key in {"auth_weight", "authority_class"}:
        lint.fail(path, f"{json_path} markdown JSON uses removed state-resolution authority field: {key}")

    if isinstance(value, str):
        for schema_id in SCHEMA_ID_TOKEN_RE.findall(value):
            if schema_id not in known["schema_ids"]:
                lint.fail(path, f"{json_path} markdown JSON references unknown schema id: {schema_id}")
        for profile_id in PROFILE_ID_TOKEN_RE.findall(value):
            if profile_id not in known["profiles"]:
                lint.fail(path, f"{json_path} markdown JSON references unknown profile: {profile_id}")

        if key == "event_kind" and value.startswith("ak.") and value not in known["event_kinds"]:
            lint.fail(path, f"{json_path} markdown JSON references unregistered Event.kind: {value}")

        if key in {"operation_id", "mapped_operation_id", "operationId"} and value.startswith("ak."):
            if value not in known["operation_ids"]:
                lint.fail(path, f"{json_path} markdown JSON references unregistered operation_id: {value}")

        if key == "constraint_kind" and value not in known["constraint_types"]:
            lint.fail(path, f"{json_path} markdown JSON uses invalid constraint_kind: {value}")

        for match in TYPED_ID_TOKEN_RE.finditer(value):
            kind, rest = match.group(1), match.group(2)
            if is_placeholder_typed_id(rest):
                if kind not in known["id_kinds"] and kind not in known["special_id_kinds"]:
                    lint.fail(path, f"{json_path} markdown JSON references unregistered typed ID kind: ak:{kind}:")
                continue
            check_typed_id_token(lint, path, json_path, kind, rest, known)



def required_fields_from_schema(lint: Lint, schema_ref: str) -> list[str]:
    schema_path = ARTIFACTS / schema_ref
    schema = load_schema_document(lint, schema_path)
    if not isinstance(schema, dict):
        return []
    required = schema.get("required", [])
    if not isinstance(required, list):
        lint.fail(schema_path, "schema required must be an array")
        return []
    return [field for field in required if isinstance(field, str)]



def schema_ref_from_fence_meta(meta: str) -> str | None:
    match = JSON_FENCE_SCHEMA_ATTR_RE.search(meta)
    if not match:
        return None
    return next(group for group in match.groups() if group)



def expect_valid_from_fence_meta(meta: str) -> bool:
    match = JSON_FENCE_EXPECT_ATTR_RE.search(meta)
    return False if match and match.group(1) == "invalid" else True



def first_expected_error_from_fence_meta(meta: str) -> str | None:
    match = JSON_FENCE_FIRST_ERROR_ATTR_RE.search(meta)
    if not match:
        return None
    return next(group for group in match.groups() if group)



def check_markdown_full_object_example(lint: Lint, path: Path, block_index: int, data: Any) -> None:
    if not isinstance(data, dict):
        return

    schema_ref = FULL_MARKDOWN_EXAMPLE_SCHEMAS.get(lint.rel(path), {}).get(block_index)
    if not schema_ref:
        return

    missing = [field for field in required_fields_from_schema(lint, schema_ref) if field not in data]
    if missing:
        lint.fail(
            path,
            f"json_block[{block_index}] full object example for {schema_ref} missing required field(s): "
            + ", ".join(missing),
        )

    if schema_ref != "schemas/event-envelope.schema.json":
        return

    proofs = data.get("proofs")
    if not isinstance(proofs, list) or not proofs:
        lint.fail(path, f"json_block[{block_index}] proof-bearing object must include non-empty proofs[]")
        return

    proof_required: list[str] = []
    event_schema = load_json(lint, ARTIFACTS / "schemas/event-envelope.schema.json")
    if isinstance(event_schema, dict):
        proof_def_name = "event_proof" if schema_ref == "schemas/event-envelope.schema.json" else "proof"
        proof_schema = event_schema.get("$defs", {}).get(proof_def_name, {})
        required = proof_schema.get("required", []) if isinstance(proof_schema, dict) else []
        proof_required = [field for field in required if isinstance(field, str)]

    for proof_index, proof in enumerate(proofs):
        if not isinstance(proof, dict):
            lint.fail(path, f"json_block[{block_index}].proofs[{proof_index}] must be an object")
            continue
        missing_proof = [field for field in proof_required if field not in proof]
        if missing_proof:
            lint.fail(
                path,
                f"json_block[{block_index}].proofs[{proof_index}] missing required field(s): "
                + ", ".join(missing_proof),
            )



def check_markdown_examples(lint: Lint, known: dict[str, set[str]]) -> None:
    for path in markdown_files():
        text = path.read_text(encoding="utf-8")

        if "ak.moderation.policy_action" in text:
            lint.fail(path, "markdown references removed Event.kind ak.moderation.policy_action; use ak.policy.action")

        for schema_id in SCHEMA_ID_TOKEN_RE.findall(text):
            if schema_id not in known["schema_ids"]:
                lint.fail(path, f"markdown references unknown schema id: {schema_id}")
        for profile_id in PROFILE_ID_TOKEN_RE.findall(text):
            if profile_id not in known["profiles"]:
                lint.fail(path, f"markdown references unknown profile: {profile_id}")

        for prefix_match in TYPED_ID_PREFIX_TOKEN_RE.finditer(text):
            kind = prefix_match.group(1)
            if kind not in known["id_kinds"] and kind not in known["special_id_kinds"]:
                lint.fail(path, f"markdown references unregistered typed ID kind: ak:{kind}:")

        for match in TYPED_ID_TOKEN_RE.finditer(text):
            kind, rest = match.group(1), match.group(2)
            if is_placeholder_typed_id(rest):
                continue
            check_typed_id_token(lint, path, "markdown", kind, rest, known)

        for block_index, match in enumerate(JSON_FENCE_RE.finditer(text), start=1):
            block = match.group("body")
            meta = match.group("meta")
            schema_ref = schema_ref_from_fence_meta(meta)
            try:
                data = parse_json_text(block)
            except Exception as exc:
                lint.fail(path, f"json_block[{block_index}] invalid canonical JSON: {exc}")
                continue
            example_negative = False
            if schema_ref:
                expect_valid = expect_valid_from_fence_meta(meta)
                example_negative = not expect_valid
                first_expected_error = first_expected_error_from_fence_meta(meta)
                if expect_valid and first_expected_error is not None:
                    lint.fail(path, f"json_block[{block_index}] first_error is only valid with expect=invalid")
                if not expect_valid and not first_expected_error:
                    lint.fail(path, f"json_block[{block_index}] expect=invalid requires first_error metadata")
                check_json_instance_against_schema(
                    lint,
                    path,
                    f"json_block[{block_index}] declared schema example",
                    schema_ref,
                    data,
                    expect_valid,
                    first_expected_error,
                )
            check_markdown_full_object_example(lint, path, block_index, data)
            check_event_ref_invariants_in_value(lint, path, f"json_block[{block_index}]", data)
            check_event_envelope_candidates(
                lint,
                path,
                data,
                known["event_kinds"],
                label=f"json_block[{block_index}]",
                negative_context=example_negative,
            )
            for json_path, value, key in walk_json(data):
                check_markdown_json_value(lint, path, f"json_block[{block_index}]{json_path[1:]}", value, key, known)


def check_release_readiness_counts(lint: Lint, known: dict[str, set[str]]) -> None:
    """T4-2: schema↔doc count guard.

    Re-parses release-readiness.md's count table and verifies each number
    matches the canonical registry. Prevents the release baseline table from
    disagreeing with the machine-readable contract.
    """
    path = SPEC_ROOT / "zh" / "overview" / "release-readiness.md"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")

    profile_data = load_json(lint, ARTIFACTS / "profiles" / "conformance-profiles.json") or {}
    profile_requirements_count = len(profile_data.get("profile_requirements", []))
    profile_sets = profile_data.get("profile_sets", {})
    profile_tiers_count = (
        sum(1 for value in profile_sets.values() if isinstance(value, list))
        if isinstance(profile_sets, dict)
        else 0
    )

    expected: dict[str, int] = {
        "Event kind（active）": len(known["active_event_kinds"]),
        "Schema": len(known["schema_ids"]),
        "Typed ID kind": len(known["id_kinds"]),
        "Service operation": len(known["operation_ids"]),
        "Claimable conformance profile": len(known["claimable_profiles"]),
        "Profile id references": len(known["profiles"]),
        "profile_requirements": profile_requirements_count,
        "profile_sets": profile_tiers_count,
    }

    # Match table rows like "| Event kind（active） | 152 | `...` |"
    table_re = re.compile(r"^\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|", re.MULTILINE)
    found: dict[str, int] = {}
    for match in table_re.finditer(text):
        label = match.group(1).strip()
        if label in expected:
            found[label] = int(match.group(2))

    for label, want in expected.items():
        if label in {"profile_requirements", "profile_sets"}:
            inline_patterns = [
                rf"(\d+)\s*(?:个|组|block|blocks)?\s*`{label}`",
                rf"`{label}`\s*(?:block|blocks|分组)?\s*[（(](\d+)[）)]",
            ]
            inline_counts: list[int] = []
            for pattern in inline_patterns:
                inline_counts.extend(int(match.group(1)) for match in re.finditer(pattern, text))
            if not inline_counts:
                lint.fail(path, f"missing prose count for `{label}`")
            for have in inline_counts:
                if have != want:
                    lint.fail(
                        path,
                        f"prose mentions {have} `{label}` but registry has {want}",
                    )
            continue
        have = found.get(label)
        if have is None:
            lint.fail(path, f"missing count row for {label!r}")
        elif have != want:
            lint.fail(
                path,
                f"count drift for {label!r}: doc says {have}, registry has {want}",
            )



def check_cross_doc_anchors(lint: Lint) -> None:
    """T4-4: cross-doc anchor check.

    Every markdown link `(./foo.md#anchor)` must resolve to a real header in
    foo.md, slugified the same way GitHub-flavored renderers do. Prevents
    silent rot when sections are renamed.
    """
    # Build slug index for every markdown file.
    slug_re = HEADING_RE
    slugify = markdown_heading_slug

    file_slugs: dict[Path, set[str]] = {}
    for path in markdown_files():
        text = path.read_text(encoding="utf-8")
        slugs: set[str] = set()
        for match in slug_re.finditer(text):
            slugs.add(slugify(match.group(2)))
        file_slugs[path.resolve()] = slugs

    link_re = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)\)")
    for path in markdown_files():
        text = path.read_text(encoding="utf-8")
        for match in link_re.finditer(text):
            href = match.group(1)
            if href.startswith(("http://", "https://", "mailto:")):
                continue
            if "#" not in href:
                continue
            target_path, _, anchor = href.partition("#")
            if not anchor:
                continue
            if target_path == "":
                # Same-file anchor; check this file's own slugs.
                target_resolved = path.resolve()
            else:
                target_resolved = (path.parent / target_path).resolve()
            slugs = file_slugs.get(target_resolved)
            if slugs is None:
                # Target file not in spec tree (e.g. external schema JSON);
                # leave for check_markdown_links to validate file existence.
                continue
            if anchor not in slugs:
                # Try also without leading section number (e.g. "3.4-target"
                # vs "target"). Skip noisy false positives by only failing
                # when no slug fuzzy-matches.
                normalized = anchor.lower()
                if any(normalized in s or s in normalized for s in slugs):
                    continue
                lint.fail(path, f"broken anchor in cross-doc link: {href!r}")



def _parse_frontmatter_block(text: str) -> tuple[dict[str, Any] | None, str]:
    """Return (frontmatter dict or None, body-after-frontmatter)."""
    match = _FRONTMATTER_BLOCK_RE.match(text)
    if not match:
        return None, text
    body = text[match.end():]
    if yaml is None:
        return {}, body
    try:
        data = yaml.safe_load(match.group(1)) or {}
    except Exception:
        return {}, body
    return (data if isinstance(data, dict) else {}), body



def _strip_code_for_keyword_scan(body: str) -> tuple[str, list[str]]:
    """Drop fenced code blocks and inline code; keep heading lines separately."""
    kept: list[str] = []
    heading_lines: list[str] = []
    in_code = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if _NORMATIVE_HEADING_RE.match(line):
            heading_lines.append(line.strip())
        kept.append(re.sub(r"`[^`]*`", "", line))
    return "\n".join(kept), heading_lines



def check_non_normative_frontmatter(lint: Lint) -> None:
    """C-BET-04: guard `normative: false` prose against undeclared requirements.

    Scans every ``spec/v1/zh/**/*.md`` and ``*.mdx`` file's frontmatter. A file
    that declares ``normative: false`` but contains RFC 2119 keywords
    (MUST / MUST NOT / SHOULD / SHOULD NOT, outside code spans) or a heading that
    declares a ``normative`` subsection MUST appear on the waiver list
    (``NON_NORMATIVE_KEYWORD_WAIVERS``) or it is an error. Files missing the
    required spec frontmatter metadata are also errors.

    The waiver mechanism keeps this gate green on the current tree (the known
    C-CON-01 finding on spec-map.md plus the informative guides and the OpenAPI
    view) while still catching *new* non-normative files that drift into carrying
    unscoped normative language.
    """
    zh_root = SPEC_ROOT / "zh"
    if not zh_root.exists():
        return
    files = sorted(set(zh_root.rglob("*.md")) | set(zh_root.rglob("*.mdx")))
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        rel = lint.rel(path)
        fm, body = _parse_frontmatter_block(text)

        if fm is None:
            lint.fail(path, "C-BET-04: missing frontmatter (spec metadata required)")
            continue

        missing = C_BET_04_REQUIRED_FRONTMATTER - set(fm.keys())
        for key in sorted(missing):
            lint.fail(path, f"C-BET-04: frontmatter missing required field '{key}'")

        # `normative` must be present and boolean-typed.
        normative_value = fm.get("normative")
        if "normative" in fm and not isinstance(normative_value, bool):
            lint.fail(
                path,
                f"C-BET-04: frontmatter 'normative' must be a boolean, got {normative_value!r}",
            )

        if normative_value is not False:
            continue

        scrubbed, heading_lines = _strip_code_for_keyword_scan(body)
        keywords = sorted(set(_NORMATIVE_KEYWORD_RE.findall(scrubbed)))
        if not keywords and not heading_lines:
            continue

        if rel in NON_NORMATIVE_KEYWORD_WAIVERS:
            continue

        detail_parts: list[str] = []
        if keywords:
            detail_parts.append(f"RFC 2119 keyword(s) {keywords}")
        if heading_lines:
            detail_parts.append(f"normative section heading(s) {heading_lines}")
        lint.fail(
            path,
            "C-BET-04: normative:false document contains "
            + " and ".join(detail_parts)
            + " -- scope the requirement to a normative doc or add an explicit "
            "waiver in NON_NORMATIVE_KEYWORD_WAIVERS.",
        )



def check_normative_prose_role_names(lint: Lint) -> None:
    """Keep normative prose bound to protocol roles rather than implementations."""
    zh_root = SPEC_ROOT / "zh"
    if not zh_root.exists():
        return
    forbidden = {
        "cotest::": "private runner module path",
        "cotest scanner": "implementation-specific scanner role",
        "teabay Directory": "implementation-specific Directory Service role",
    }
    files = sorted(set(zh_root.rglob("*.md")) | set(zh_root.rglob("*.mdx")))
    for path in files:
        text = path.read_text(encoding="utf-8")
        frontmatter, body = _parse_frontmatter_block(text)
        if not isinstance(frontmatter, dict) or frontmatter.get("normative") is not True:
            continue
        for token, label in forbidden.items():
            if token in body:
                lint.fail(path, f"normative prose contains {label}: {token!r}")



def check_account_notification_prose_schema_alignment(lint: Lint) -> None:
    prose_path = SPEC_ROOT / "zh" / "sync" / "client-sync.md"
    schema_path = ARTIFACTS / "schemas" / "account-subscribe-frame.schema.json"
    prose = prose_path.read_text(encoding="utf-8")
    schema = load_json(lint, schema_path)
    if not isinstance(schema, dict):
        return
    notification_delta = schema.get("$defs", {}).get("notification_delta", {})
    required = notification_delta.get("required", [])
    properties = notification_delta.get("properties", {})
    if not {"id", "action"}.issubset(required):
        lint.fail(schema_path, "notification_delta must require id and action")
    retired_fields = {"notification_kind", "type"}
    if retired_fields.intersection(required) or retired_fields.intersection(properties):
        lint.fail(
            schema_path,
            "notification_delta must not retain a redundant notification discriminator",
        )
    for definition_name in (
        "agent_runtime_approval_notification_data",
        "agent_runtime_approval_notification_removal_data",
    ):
        definition = schema.get("$defs", {}).get(definition_name, {})
        if "kind" in definition.get("required", []) or "kind" in definition.get(
            "properties", {}
        ):
            lint.fail(
                schema_path,
                f"{definition_name} must not retain a redundant kind discriminator",
            )
    canonical_shape = "{id, action, data?}"
    if canonical_shape not in prose:
        lint.fail(
            prose_path,
            "account notification normative prose must match the discriminator-free notification_delta",
        )
    if (
        "{id, notification_kind, action, data?}" in prose
        or '`notification_kind="agent"`' in prose
        or '`data.kind="agent_runtime_approval"`' in prose
        or "{id, type, action, data?}" in prose
        or '`type="agent"`' in prose
    ):
        lint.fail(
            prose_path,
            "NotificationDelta discriminators are forbidden on the single-family v1 wire shape",
        )
