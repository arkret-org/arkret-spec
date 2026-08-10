"""Artifact lint phase 4: fixtures."""

from __future__ import annotations

from .core import (
    ARTIFACTS,
    Any,
    Iterable,
    Lint,
    NEGATIVE_TOKEN_PATH_SEGMENTS,
    ONE_OF_REFERENCE_RE,
    PLACEHOLDER_DIGEST_FIXTURES,
    PROFILE_ID_TOKEN_RE,
    Path,
    ROOT,
    SCHEMA_ID_TOKEN_RE,
    SECURITY_CLOSURE_VECTOR_IDS,
    SHA256_RE,
    SPEC_ROOT,
    STATED_PREIMAGE_DIGEST_PAIRS,
    STATED_PREIMAGE_KEY_RE,
    TYPED_ID_TOKEN_RE,
    UNPAIRED_STATED_PREIMAGE_KEYS,
    VECTOR_ID_TOKEN_RE,
    Draft202012Validator,
    base64,
    binascii,
    canonical_json,
    check_event_envelope_candidates,
    check_json_instance_against_schema,
    check_typed_id_token,
    copy,
    datetime,
    hashlib,
    json,
    load_json,
    markdown_files,
    markdown_section_digest,
    raw_artifact_files,
    re,
    read_text,
    unicodedata,
    urllib,
    walk_json,
)



def sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()



def base64url_text(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).rstrip(b"=").decode("ascii")



def sha256_base64url_text(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")



def check_content_bound_event_id_fixture(lint: Lint) -> None:
    path = ARTIFACTS / "fixtures" / "content-bound-event-id-fixture.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return
    if data.get("generated_by") != "tools/generate_content_bound_event_id_fixture.py":
        lint.fail(path, "suite-tagged Event-ID fixture must name its deterministic generator")
    required = {
        "full_digest_single_bit_difference_changes_event_id",
        "suite_code_mismatch_rejected",
        "invalid_zero_suite_code_rejected",
        "nonzero_event_reserved_nibble_rejected",
        "reserved_suite_code_rejected",
        "unknown_suite_code_rejected",
        "padding_rejected",
        "wrong_decoded_length_rejected",
        "same_event_id_different_canonical_bytes_is_hash_collision",
    }
    names: set[str] = set()
    for case in data.get("cases", []):
        if not isinstance(case, dict):
            continue
        name = case.get("name")
        if isinstance(name, str):
            names.add(name)
        digest_wire = case.get("event_digest")
        suite_code = case.get("suite_wire_code")
        expected_id = case.get("derived_event_id")
        if not (isinstance(digest_wire, str) and isinstance(suite_code, int) and isinstance(expected_id, str)):
            continue
        try:
            digest = bytes.fromhex(digest_wire.split(":", 1)[1])
        except (IndexError, ValueError):
            lint.fail(path, f"{name}: invalid event_digest")
            continue
        body = bytes((suite_code,)) + digest
        token = base64.urlsafe_b64encode(body).rstrip(b"=").decode("ascii")
        if len(digest) != 32 or len(body) != 33 or len(token) != 44:
            lint.fail(path, f"{name}: Event-ID byte/encoding length mismatch")
            continue
        if case.get("event_id_bytes_hex") != body.hex() or expected_id != "ak:event:" + token:
            lint.fail(path, f"{name}: suite-tagged Event-ID KAT mismatch")
        preimage = case.get("digest_preimage_canonical_bytes_utf8")
        if isinstance(preimage, str) and digest_wire.startswith("sha256:"):
            if hashlib.sha256(preimage.encode("utf-8")).digest() != digest:
                lint.fail(path, f"{name}: stated SHA-256 digest preimage mismatch")
    for name in sorted(required - names):
        lint.fail(path, f"missing required Event-ID case {name}")
    single_bit_case = next(
        (
            case
            for case in data.get("cases", [])
            if isinstance(case, dict)
            and case.get("name") == "full_digest_single_bit_difference_changes_event_id"
        ),
        None,
    )
    if isinstance(single_bit_case, dict):
        try:
            first = base64.urlsafe_b64decode(single_bit_case["first_event_id"].split(":", 2)[2] + "==")
            second = base64.urlsafe_b64decode(single_bit_case["second_event_id"].split(":", 2)[2] + "==")
        except (KeyError, ValueError):
            lint.fail(path, "single-bit Event-ID case contains an invalid typed ID")
        else:
            differing_bits = sum((left ^ right).bit_count() for left, right in zip(first, second, strict=True))
            if len(first) != 33 or len(second) != 33 or first[0] != second[0] or differing_bits != 1:
                lint.fail(path, "single-bit Event-ID case must differ by exactly one digest bit")



def check_fixture_runner_contract(lint: Lint) -> None:
    fixture_root = ARTIFACTS / "fixtures"
    runner_registry_path = ARTIFACTS / "registry" / "runner-kind-registry.json"
    runner_registry = load_json(lint, runner_registry_path)
    rows = runner_registry.get("runner_kinds", []) if isinstance(runner_registry, dict) else []
    allowed_kinds = {
        row.get("kind")
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("kind"), str)
    }
    if not allowed_kinds:
        lint.fail(runner_registry_path, "runner kind registry must declare a non-empty closed vocabulary")
        return
    if len(allowed_kinds) != len(rows):
        lint.fail(runner_registry_path, "runner kind registry contains duplicate or malformed kind entries")
    for row in rows:
        if not isinstance(row, dict):
            continue
        if not isinstance(row.get("execution_contract"), str) or not row["execution_contract"].strip():
            lint.fail(runner_registry_path, f"runner kind {row.get('kind')!r} lacks execution_contract")
        if row.get("owner") not in {"protocol", "in_tree_lint", "cotest", "in_tree_lint_and_cotest"}:
            lint.fail(runner_registry_path, f"runner kind {row.get('kind')!r} has invalid owner")
        if row.get("execution_status") != "contract_published":
            lint.fail(runner_registry_path, f"runner kind {row.get('kind')!r} must publish its execution contract")
    executable_registry_assertions = {
        "error_code_registry_coverage_fixture": {
            "unique_top_level_codes",
            "unique_reason_codes",
            "operation_errors_registered",
            "reason_references_registered",
            "layering_is_explicit",
        },
        "operation_registry_coverage_fixture": {
            "catalog_registry_bijection",
            "registry_openapi_bijection",
            "registry_binding_coverage",
            "schema_refs_resolve",
            "write_retry_contract",
            "read_retry_contract",
            "write_durable_effect_contract",
        },
        "event_kind_lattice_dispatch_fixture": {
            "registered_dispatch_target",
            "or_set_bottom_never_rejects",
            "family_semantics_present",
            "unknown_dispatch_fails_closed",
            "fsm_family_contract_closure",
            "actor_private_contract_closure",
            "lifecycle_modality_scope",
        },
        "event_kind_payload_coverage_fixture": {
            "catalog_registry_bijection",
            "payload_schema_ref_resolves",
            "wire_scope_matches_envelope",
            "unknown_durable_kind_fails_closed",
        },
    }
    for path in sorted(fixture_root.glob("*.json")):
        data = load_json(lint, path)
        if not isinstance(data, dict):
            continue
        runner = data.get("runner")
        if not isinstance(runner, dict):
            lint.fail(path, "top-level runner must be an object with runner.kind")
            continue
        kind = runner.get("kind")
        if not isinstance(kind, str) or not kind:
            lint.fail(path, "top-level runner.kind must be a non-empty string")
            continue
        if kind not in allowed_kinds:
            lint.fail(path, f"runner.kind is not registered: {kind!r}")
            continue
        if kind == "named_suite":
            entrypoint = runner.get("entrypoint")
            if not isinstance(entrypoint, str) or not re.fullmatch(r"ak\.suite\.[a-z0-9_.-]+\.v1", entrypoint):
                lint.fail(path, "runner.kind=named_suite requires a tool-neutral ak.suite.*.v1 entrypoint")
        if kind == "registry_coverage":
            inputs = runner.get("inputs")
            if not isinstance(inputs, list) or not inputs:
                lint.fail(path, "runner.kind=registry_coverage requires non-empty inputs")
            else:
                for relative in inputs:
                    if not isinstance(relative, str) or not (ARTIFACTS / relative).is_file():
                        lint.fail(path, f"registry coverage input does not exist: {relative!r}")
            suite = data.get("suite")
            expected = executable_registry_assertions.get(suite)
            assertions = data.get("assertions")
            actual = {
                row.get("id") for row in assertions if isinstance(row, dict) and isinstance(row.get("id"), str)
            } if isinstance(assertions, list) else set()
            if expected is None or actual != expected:
                lint.fail(path, f"registry coverage assertions are not bound to the executable lint contract: {sorted(actual)}")

        if path.name == "morph-schema-migration-fixture.json":
            vectors = data.get("vectors")
            if not isinstance(vectors, list) or not vectors:
                lint.fail(path, "morph migration runner requires vectors")
                continue
            observed_rules: set[str] = set()
            for vector in vectors:
                if not isinstance(vector, dict):
                    lint.fail(path, "morph migration vector must be an object")
                    continue
                fields = dict(((vector.get("input") or {}).get("fields") or {}))
                rules = (((vector.get("input") or {}).get("payload") or {}).get("transformation_rules") or [])
                for rule in rules:
                    rule_id = rule.get("rule") if isinstance(rule, dict) else None
                    observed_rules.add(rule_id)
                    if rule_id == "ak.transform.identity.v1":
                        continue
                    if rule_id == "ak.transform.rename.v1":
                        source, target = rule.get("from"), rule.get("to")
                        if source not in fields or target in fields:
                            lint.fail(path, f"{vector.get('vector_id')} rename precondition failed")
                            continue
                        fields[target] = fields.pop(source)
                    elif rule_id == "ak.transform.type_widen.v1":
                        if (rule.get("from_kind"), rule.get("to_kind")) != ("integer", "number") or not isinstance(fields.get(rule.get("field")), int):
                            lint.fail(path, f"{vector.get('vector_id')} type widening precondition failed")
                    elif rule_id == "ak.transform.default_backfill.v1":
                        fields.setdefault(rule.get("to"), rule.get("value"))
                    else:
                        lint.fail(path, f"{vector.get('vector_id')} uses unknown transformation rule {rule_id!r}")
                if fields != vector.get("expected_output"):
                    lint.fail(path, f"{vector.get('vector_id')} executable transformation output mismatch")
                canonical = json.dumps(fields, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
                digest = "sha256:" + hashlib.sha256(canonical).hexdigest()
                if digest != vector.get("expected_output_digest"):
                    lint.fail(path, f"{vector.get('vector_id')} expected_output_digest mismatch")
            required_rules = {
                "ak.transform.identity.v1",
                "ak.transform.rename.v1",
                "ak.transform.type_widen.v1",
                "ak.transform.default_backfill.v1",
            }
            if observed_rules != required_rules:
                lint.fail(path, f"morph runner rule coverage mismatch: {sorted(observed_rules)}")



def check_erasure_verification_contract(lint: Lint) -> None:
    """Verify hard-erasure structure, digest consistency, and proof boundary vectors."""
    fixture_path = ARTIFACTS / "fixtures" / "redaction-fixture.json"
    fixture = load_json(lint, fixture_path)
    if not isinstance(fixture, dict):
        return
    cases = fixture.get("cases")
    case_rows = cases if isinstance(cases, list) else []
    hard_erasure = next(
        (
            case
            for case in case_rows if isinstance(case, dict)
            if case.get("name") == "hard_erasure_receipt"
        ),
        None,
    )
    if not isinstance(hard_erasure, dict):
        lint.fail(fixture_path, "missing hard_erasure_receipt case")
        return

    receipt = hard_erasure.get("redaction_receipt")
    expected_projection = hard_erasure.get("expected_projection")
    if not isinstance(receipt, dict) or not isinstance(expected_projection, dict):
        lint.fail(fixture_path, "hard_erasure_receipt must contain receipt and expected_projection")
        return
    stub = receipt.get("retained_stub")
    stated_stub_digest = receipt.get("retained_stub_digest")
    if not isinstance(stub, dict) or not isinstance(stated_stub_digest, str):
        lint.fail(fixture_path, "hard-erasure receipt must contain retained_stub and its digest")
        return
    recomputed_stub_digest = "sha256:" + hashlib.sha256(
        canonical_json(stub).encode("utf-8")
    ).hexdigest()
    if stated_stub_digest != recomputed_stub_digest:
        lint.fail(
            fixture_path,
            "hard-erasure retained_stub_digest does not equal sha256(canonical_json(retained_stub))",
        )
    if expected_projection.get("retained_stub_digest") != stated_stub_digest:
        lint.fail(fixture_path, "hard-erasure projection must expose the bound retained_stub_digest")
    if expected_projection.get("original_preimage_verified") is not False:
        lint.fail(fixture_path, "hard-erasure positive vector must state original_preimage_verified=false")

    suite_registry_path = ARTIFACTS / "registry" / "digest-suite-registry.json"
    suite_registry = load_json(lint, suite_registry_path)
    active_suites = {
        row.get("wire_code"): row.get("canonical_id")
        for row in (suite_registry.get("suites", []) if isinstance(suite_registry, dict) else [])
        if isinstance(row, dict) and row.get("status") == "active"
    }
    kind_prefixes = {
        "principal": "did:",
        "realm": "ak:realm:",
        "event": "ak:event:",
        "blob": "ak:blob:",
        "device": "ak:device:",
        "account_private_state": "sha256:",
    }

    def verdict(vector: dict[str, Any]) -> str:
        subject = vector.get("subject")
        if not isinstance(subject, dict):
            return "schema_violation"
        kind = subject.get("kind")
        subject_ref = subject.get("subject_ref")
        expected_prefix = kind_prefixes.get(kind)
        if not isinstance(subject_ref, str) or expected_prefix is None or not subject_ref.startswith(expected_prefix):
            return "schema_violation"
        if kind != "event":
            return "accepted"
        suffix = subject_ref.removeprefix("ak:event:")
        if not re.fullmatch(r"[A-Za-z0-9_-]{44}", suffix):
            return "schema_violation"
        try:
            decoded = base64.urlsafe_b64decode(suffix + "==")
        except (ValueError, binascii.Error):
            return "schema_violation"
        if len(decoded) != 33 or base64.urlsafe_b64encode(decoded).decode("ascii").rstrip("=") != suffix:
            return "schema_violation"
        if decoded[0] >> 4 != 0:
            return "schema_violation"
        suite_id = active_suites.get(decoded[0] & 0x0F)
        if not isinstance(suite_id, str):
            return "unsupported_digest_algorithm"
        event_digest = vector.get("event_digest")
        if event_digest is not None and event_digest != f"{suite_id}:{decoded[1:].hex()}":
            return "event_id_digest_mismatch"
        if vector.get("retained_stub_digest") != recomputed_stub_digest:
            return "erasure_receipt_stub_digest_mismatch"
        return "accepted"

    vectors = hard_erasure.get("verification_cases")
    if not isinstance(vectors, list) or len(vectors) < 5:
        lint.fail(fixture_path, "hard-erasure verification_cases must cover at least five cases")
        return
    required = {
        "structure_digest_and_stub_binding_valid",
        "wrong_kind_ref_namespace_rejected",
        "invalid_event_id_suite_rejected",
        "event_id_digest_mismatch_rejected",
        "stub_digest_mismatch_rejected",
    }
    names = {vector.get("name") for vector in vectors if isinstance(vector, dict)}
    if names != required:
        lint.fail(fixture_path, f"hard-erasure verification case names drifted: {sorted(names)}")
    for vector in vectors:
        if not isinstance(vector, dict):
            lint.fail(fixture_path, "hard-erasure verification case must be an object")
            continue
        if verdict(vector) != vector.get("expected"):
            lint.fail(
                fixture_path,
                f"hard-erasure case {vector.get('name')!r} expected {vector.get('expected')!r} "
                f"but evaluates to {verdict(vector)!r}",
            )
        if vector.get("expected") == "accepted" and vector.get("original_preimage_verified") is not False:
            lint.fail(fixture_path, "accepted hard-erasure vector must deny original preimage verification")

    receipt_schema_path = ARTIFACTS / "schemas" / "erasure-receipt.schema.json"
    receipt_schema = load_json(lint, receipt_schema_path)
    if isinstance(receipt_schema, dict):
        defs = receipt_schema.get("$defs", {})
        retained_stub = receipt_schema.get("properties", {}).get("retained_stub", {})
        if isinstance(defs, dict) and "verification_stub" in defs:
            lint.fail(receipt_schema_path, "receipt schema must not copy the verification stub definition")
        if not isinstance(retained_stub, dict) or retained_stub.get("$ref") != "./erasure-verification-stub.schema.json":
            lint.fail(receipt_schema_path, "retained_stub must reference the standalone schema truth source")



def check_producer_allocated_identity_vectors(lint: Lint) -> None:
    """Require the registry-driven five-case collision suite for every producer ID kind."""
    registry_path = ARTIFACTS / "registry" / "id-kind-registry.json"
    fixture_path = ARTIFACTS / "fixtures" / "producer-allocated-identity-fixture.json"
    registry = load_json(lint, registry_path)
    fixture = load_json(lint, fixture_path)
    if not isinstance(registry, dict) or not isinstance(fixture, dict):
        return
    expected_kinds = sorted(
        row["kind"]
        for row in registry.get("id_kinds", [])
        if isinstance(row, dict)
        and row.get("id_form") == "producer_allocated"
        and row.get("identity_authority") == "producer_signature"
        and isinstance(row.get("kind"), str)
    )
    driver = fixture.get("driver")
    if not isinstance(driver, dict):
        lint.fail(fixture_path, "producer identity fixture missing registry driver")
        return
    if driver.get("selected_id_kinds") != expected_kinds:
        lint.fail(fixture_path, "producer identity fixture selected_id_kinds drifted from registry")
    if driver.get("registry_ref") != "registry/id-kind-registry.json#/id_kinds":
        lint.fail(fixture_path, "producer identity fixture must consume the generated ID registry")
    expected_cases = {
        "authorized_first_reservation_accepted": "accepted",
        "same_authority_exact_replay_idempotent": "idempotent",
        "same_authority_conflicting_binding_quarantined": "reject_and_quarantine",
        "cross_authority_same_uuid_distinct": "distinct_identity",
        "bare_lookup_or_unauthorized_allocator_rejected": "rejected",
    }
    cases = fixture.get("cases")
    case_rows = cases if isinstance(cases, list) else []
    actual_cases = {
        case.get("name"): case.get("expected")
        for case in case_rows if isinstance(case, dict)
    }
    if actual_cases != expected_cases:
        lint.fail(fixture_path, "producer identity fixture must contain the closed five-case matrix")



def check_applet_revoke_saga_contract(lint: Lint) -> None:
    """Pin the executable revoke saga matrix to its schema and operation contract."""
    fixture_path = ARTIFACTS / "fixtures" / "applet-revoke-saga-fixture.json"
    operation_path = ARTIFACTS / "registry" / "operation-registry.json"
    schema_path = ARTIFACTS / "schemas" / "applet-install-operations.schema.json"
    fixture = load_json(lint, fixture_path)
    operations = load_json(lint, operation_path)
    schema = load_json(lint, schema_path)
    if not all(isinstance(value, dict) for value in (fixture, operations, schema)):
        return

    runner = fixture.get("runner", {})
    if runner != {
        "kind": "named_suite",
        "entrypoint": "ak.suite.applet.revoke_saga.v1",
    }:
        lint.fail(fixture_path, "revoke saga fixture must expose the canonical named suite")
    if fixture.get("covers_vectors") != ["ak.vector.applet.revoke_saga.v1"]:
        lint.fail(fixture_path, "revoke saga fixture must cover exactly its registered vector")

    required_invariants = {
        "persist_ledger_before_first_effect",
        "ledger_binds_principal_service_and_admin_actor",
        "exact_replay_resumes_same_ledger",
        "conflicting_replay_has_no_effect",
        "accepted_or_duplicate_steps_are_never_reexecuted",
        "rejected_step_cannot_be_skipped",
        "first_accepted_revoke_event_fences_future_applet_writes",
        "complete_requires_every_planned_step_terminal_success",
    }
    if set(fixture.get("invariants", [])) != required_invariants:
        lint.fail(fixture_path, "revoke saga fixture invariants are incomplete or drifted")

    plan = fixture.get("plan", {})
    steps = plan.get("steps", []) if isinstance(plan, dict) else []
    step_ids = {
        step.get("step_id")
        for step in steps
        if isinstance(step, dict) and isinstance(step.get("step_id"), str)
    }
    if len(step_ids) != len(steps) or not {
        "capability:0",
        "membership:0",
        "delegated_session:0",
        "widget_token:0",
    }.issubset(step_ids):
        lint.fail(fixture_path, "revoke saga plan must contain unique Event, external, and local steps")

    cases = fixture.get("cases", [])
    case_by_name = {
        case.get("name"): case
        for case in cases
        if isinstance(case, dict) and isinstance(case.get("name"), str)
    }
    required_cases = {
        "complete_exact_plan",
        "event_rejected_without_skip",
        "crash_after_first_acceptance_then_exact_restart",
        "same_key_different_body_conflicts",
        "same_key_different_actor_or_service_conflicts",
        "external_effect_partial_then_restart",
        "plan_or_submission_mismatch_is_pre_effect",
    }
    if set(case_by_name) != required_cases:
        lint.fail(fixture_path, "revoke saga fixture must contain the closed seven-case matrix")
        return

    effect_prefixes = ("accepted:", "duplicate:", "rejected:")
    for name, case in case_by_name.items():
        for field in ("timeline", "first_attempt", "restart_timeline"):
            timeline = case.get(field)
            if not isinstance(timeline, list):
                continue
            effect_indexes = [
                index
                for index, action in enumerate(timeline)
                if isinstance(action, str) and action.startswith(effect_prefixes)
            ]
            if field != "restart_timeline" and effect_indexes:
                persist_index = timeline.index("persist_ledger") if "persist_ledger" in timeline else -1
                if persist_index < 0 or persist_index > effect_indexes[0]:
                    lint.fail(fixture_path, f"{name}.{field} performs an effect before ledger persistence")
            for action in timeline:
                if not isinstance(action, str) or not action.startswith(effect_prefixes):
                    continue
                step_id = action.split(":", 1)[1]
                if step_id not in step_ids:
                    lint.fail(fixture_path, f"{name}.{field} references unknown saga step {step_id!r}")

    complete = case_by_name["complete_exact_plan"]["timeline"]
    first_event = complete.index("accepted:capability:0")
    if complete[first_event + 1] != "fence_applet_writes":
        lint.fail(fixture_path, "first accepted revoke Event must immediately fence Applet writes")
    rejected = case_by_name["event_rejected_without_skip"]
    if rejected.get("expected_pending_steps") != [
        "membership:0",
        "delegated_session:0",
        "widget_token:0",
    ]:
        lint.fail(fixture_path, "a rejected Event must preserve every later step as pending")
    restart = case_by_name["crash_after_first_acceptance_then_exact_restart"]
    if restart.get("request_binding") != restart.get("restart_request_binding"):
        lint.fail(fixture_path, "restart case must replay the exact request binding")
    if "accepted:capability:0" in restart.get("restart_timeline", []):
        lint.fail(fixture_path, "restart must not re-execute an already accepted Event")
    conflict = case_by_name["same_key_different_body_conflicts"]
    if (
        conflict.get("request_binding") == conflict.get("replay_request_binding")
        or conflict.get("expected_new_effect_count") != 0
    ):
        lint.fail(fixture_path, "conflicting idempotency replay must have zero new effects")
    principal_conflict = case_by_name["same_key_different_actor_or_service_conflicts"]
    if (
        len(principal_conflict.get("replay_request_bindings", [])) != 2
        or principal_conflict.get("expected_new_effect_count") != 0
    ):
        lint.fail(fixture_path, "revoke ledger must bind both principal service and admin actor")
    mismatch = case_by_name["plan_or_submission_mismatch_is_pre_effect"]
    if mismatch.get("timeline") != ["reject_plan_or_submission_mismatch"]:
        lint.fail(fixture_path, "plan/submission mismatch must fail before ledger or effects")

    rows = operations.get("operations", [])
    revoke = next(
        (
            row
            for row in rows
            if isinstance(row, dict)
            and row.get("operation_id") == "ak.self.applet.command.revoke"
        ),
        {},
    )
    saga = revoke.get("saga_contract", {}) if isinstance(revoke, dict) else {}
    if (
        saga.get("ledger") != "durable_before_first_effect"
        or saga.get("restart_recovery")
        != "resume_exact_persisted_submissions_and_pending_steps"
        or saga.get("first_revoke_acceptance_fences_future_writes") is not True
    ):
        lint.fail(operation_path, "Applet revoke operation saga contract drifted from its vector")

    defs = schema.get("$defs", {})
    request = defs.get("applet_revoke_request_body", {}) if isinstance(defs, dict) else {}
    required = set(request.get("required", [])) if isinstance(request, dict) else set()
    carrier_fields = {
        "effective_scope",
        "reason_code",
        "revoke_mode",
        "revoke_plan_digest",
        "capability_revoke_events",
        "membership_state_events",
    }
    if not carrier_fields.issubset(required):
        lint.fail(schema_path, "Applet revoke commit schema is missing its exact signed carrier")



def check_normative_clause_registry(lint: Lint) -> None:
    """Reverse coverage: every registered normative clause must have live evidence.

    vector-registry.json proves each vector has a consumer. This registry proves
    the other direction for the high-risk obligation set: each registered clause
    points at an existing prose section, that section's text has not drifted
    since the clause was reviewed, and the clause names evidence that actually
    exists (an active vector, or an explicit non-vector test plan).
    """
    path = ARTIFACTS / "registry" / "normative-clause-registry.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return

    if data.get("source_of_truth") is not True:
        lint.fail(path, "source_of_truth must be true")

    coverage_scope = data.get("coverage_scope")
    if not isinstance(coverage_scope, dict):
        lint.fail(path, "coverage_scope must be an object")
        return
    categories = coverage_scope.get("included_categories")
    if not isinstance(categories, list) or not categories:
        lint.fail(path, "coverage_scope.included_categories must be a non-empty array")
        return
    included_categories = set(categories)
    for field in ("rule", "extension_rule"):
        if not isinstance(coverage_scope.get(field), str) or not coverage_scope[field].strip():
            lint.fail(path, f"coverage_scope.{field} must be a non-empty string")

    vector_data = load_json(lint, ARTIFACTS / "registry" / "vector-registry.json")
    active_vectors = {
        row.get("vector_id")
        for row in (vector_data.get("vectors", []) if isinstance(vector_data, dict) else [])
        if isinstance(row, dict) and row.get("status") == "active"
    }

    rows = data.get("clauses")
    if not isinstance(rows, list) or not rows:
        lint.fail(path, "clauses must be a non-empty list")
        return

    clause_id_re = re.compile(r"^AK-NC-\d{3}$")
    allowed_status = {"active", "deprecated"}
    allowed_grades = {"vector", "api_shape", "audit"}
    seen: set[str] = set()
    covered_categories: set[str] = set()
    for index, row in enumerate(rows):
        label = f"clauses[{index}]"
        if not isinstance(row, dict):
            lint.fail(path, f"{label} must be an object")
            continue

        clause_id = row.get("clause_id")
        if not isinstance(clause_id, str) or not clause_id_re.fullmatch(clause_id):
            lint.fail(path, f"{label}.clause_id must match AK-NC-###")
            continue
        if clause_id in seen:
            lint.fail(path, f"{label}.clause_id duplicates {clause_id}")
        seen.add(clause_id)

        status = row.get("status")
        if status not in allowed_status:
            lint.fail(path, f"{clause_id}.status must be one of {sorted(allowed_status)}")
        category = row.get("category")
        if category not in included_categories:
            lint.fail(path, f"{clause_id}.category {category!r} is outside coverage_scope.included_categories")
        elif status == "active":
            covered_categories.add(category)
        if not isinstance(row.get("requirement"), str) or not row["requirement"].strip():
            lint.fail(path, f"{clause_id}.requirement must be a non-empty string")

        source_anchor = row.get("source_anchor")
        if not isinstance(source_anchor, str) or "#" not in source_anchor:
            lint.fail(path, f"{clause_id}.source_anchor must be <repo-relative markdown path>#<heading slug>")
            continue
        rel, _, anchor = source_anchor.partition("#")
        source_path = Path(rel)
        if source_path.is_absolute() or ".." in source_path.parts:
            lint.fail(path, f"{clause_id}.source_anchor escapes repository: {source_anchor}")
            continue
        resolved = (ROOT / source_path).resolve()
        try:
            resolved.relative_to(ROOT.resolve())
        except ValueError:
            lint.fail(path, f"{clause_id}.source_anchor escapes repository: {source_anchor}")
            continue
        if not resolved.is_file():
            lint.fail(path, f"{clause_id}.source_anchor target does not exist: {rel}")
            continue
        digest = markdown_section_digest(read_text(resolved), anchor)
        if digest is None:
            lint.fail(path, f"{clause_id}.source_anchor heading does not exist: {source_anchor}")
            continue
        if row.get("section_digest") != digest:
            lint.fail(
                path,
                f"{clause_id}.section_digest is stale for {source_anchor}: the normative text changed, so the clause "
                f"and its evidence must be re-reviewed and the digest updated to {digest}",
            )

        grade = row.get("testability_grade")
        if grade not in allowed_grades:
            lint.fail(path, f"{clause_id}.testability_grade must be one of {sorted(allowed_grades)}")
            continue
        if grade == "vector":
            evidence = row.get("evidence_refs")
            if not isinstance(evidence, list) or not evidence:
                lint.fail(path, f"{clause_id}.evidence_refs must be a non-empty array for testability_grade=vector")
                continue
            if "test_plan" in row:
                lint.fail(path, f"{clause_id} must not declare both evidence_refs and test_plan")
            for vector_id in evidence:
                if vector_id not in active_vectors:
                    lint.fail(path, f"{clause_id}.evidence_refs references a non-active vector: {vector_id!r}")
        else:
            if "evidence_refs" in row:
                lint.fail(path, f"{clause_id} must declare test_plan instead of evidence_refs for grade {grade}")
            if not isinstance(row.get("test_plan"), str) or not row["test_plan"].strip():
                lint.fail(path, f"{clause_id}.test_plan must be a non-empty string for testability_grade={grade}")

    missing = included_categories - covered_categories
    if missing:
        lint.fail(path, f"coverage_scope.included_categories has no active clause: {sorted(missing)}")



def check_vector_registry(lint: Lint) -> None:
    path = ARTIFACTS / "registry" / "vector-registry.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return

    if data.get("source_of_truth") is not True:
        lint.fail(path, "source_of_truth must be true")

    profiles_path = ARTIFACTS / "profiles" / "conformance-profiles.json"
    profiles_data = load_json(lint, profiles_path)
    if not isinstance(profiles_data, dict):
        return
    known_profiles = set(PROFILE_ID_TOKEN_RE.findall(json.dumps(profiles_data, ensure_ascii=False)))
    known_vector_groups = set(profiles_data.get("vector_groups") or [])
    known_fixtures = {fixture.name for fixture in (ARTIFACTS / "fixtures").glob("*.json")}

    rows = data.get("vectors")
    if not isinstance(rows, list) or not rows:
        lint.fail(path, "vectors must be a non-empty list")
        return

    registered: dict[str, dict[str, Any]] = {}
    source_vector_ids: dict[Path, set[str]] = {}
    for index, row in enumerate(rows):
        label = f"vectors[{index}]"
        if not isinstance(row, dict):
            lint.fail(path, f"{label} must be an object")
            continue

        vector_id = row.get("vector_id")
        if not isinstance(vector_id, str) or not VECTOR_ID_TOKEN_RE.fullmatch(vector_id):
            lint.fail(path, f"{label}.vector_id must be a ak.vector.*.vN identifier")
            continue
        if vector_id in registered:
            lint.fail(path, f"{label}.vector_id duplicates {vector_id}")
        registered[vector_id] = row

        if row.get("status") not in {"active", "reserved", "deprecated"}:
            lint.fail(path, f"{label}.status must be active, reserved, or deprecated")

        expected_domain = vector_id.removeprefix("ak.vector.").rsplit(".v", 1)[0].split(".", 1)[0]
        if row.get("domain") != expected_domain:
            lint.fail(path, f"{label}.domain must match vector id domain {expected_domain!r}")

        if "profile" in row:
            lint.fail(path, f"{label}.profile is ambiguous; use one explicit applicability selector")
        selector_keys = [
            key
            for key in ("scope", "applies_to_profiles", "applies_to_vector_groups", "applies_to_fixtures")
            if key in row
        ]
        if len(selector_keys) != 1:
            lint.fail(path, f"{label} must declare exactly one applicability selector")
        elif selector_keys[0] == "scope":
            if row.get("scope") != "universal":
                lint.fail(path, f"{label}.scope must be 'universal'")
        else:
            selector = selector_keys[0]
            values = row.get(selector)
            if not isinstance(values, list) or not values or any(not isinstance(value, str) for value in values):
                lint.fail(path, f"{label}.{selector} must be a non-empty string array")
            elif len(values) != len(set(values)):
                lint.fail(path, f"{label}.{selector} must not contain duplicates")
            elif selector == "applies_to_profiles":
                for profile_id in values:
                    if profile_id not in known_profiles:
                        lint.fail(path, f"{label}.{selector} references unknown profile: {profile_id}")
            elif selector == "applies_to_vector_groups":
                for group_id in values:
                    if group_id not in known_vector_groups:
                        lint.fail(path, f"{label}.{selector} references unknown vector group: {group_id}")
            elif selector == "applies_to_fixtures":
                for fixture in values:
                    if fixture not in known_fixtures:
                        lint.fail(path, f"{label}.{selector} references missing fixture: {fixture}")

        source_refs = row.get("source_refs")
        if not isinstance(source_refs, list) or not source_refs:
            lint.fail(path, f"{label}.source_refs must be a non-empty array")
            continue
        for source_index, source_ref in enumerate(source_refs):
            source_label = f"{label}.source_refs[{source_index}]"
            if not isinstance(source_ref, str) or not source_ref:
                lint.fail(path, f"{source_label} must be a non-empty string")
                continue
            source_path = Path(source_ref)
            if source_path.is_absolute() or ".." in source_path.parts:
                lint.fail(path, f"{source_label} escapes repository: {source_ref}")
                continue
            resolved = (ROOT / source_path).resolve()
            try:
                resolved.relative_to(ROOT.resolve())
            except ValueError:
                lint.fail(path, f"{source_label} escapes repository: {source_ref}")
                continue
            if not resolved.is_file():
                lint.fail(path, f"{source_label} target does not exist: {source_ref}")
                continue
            try:
                referenced_ids = source_vector_ids.get(resolved)
                if referenced_ids is None:
                    referenced_ids = set(VECTOR_ID_TOKEN_RE.findall(read_text(resolved)))
                    source_vector_ids[resolved] = referenced_ids
            except Exception as exc:
                lint.fail(path, f"{source_label} target cannot be read: {source_ref}: {exc}")
                continue
            if vector_id not in referenced_ids:
                lint.fail(path, f"{source_label} does not contain vector_id {vector_id}")

        for fixture in row.get("applies_to_fixtures", []):
            expected_ref = f"spec/v1/artifacts/fixtures/{fixture}"
            if expected_ref not in source_refs:
                lint.fail(path, f"{label}.applies_to_fixtures entry lacks matching source_ref: {fixture}")

    for scan_path in markdown_files() + raw_artifact_files():
        try:
            text = read_text(scan_path.resolve())
        except Exception:
            continue
        for vector_id in sorted(set(VECTOR_ID_TOKEN_RE.findall(text))):
            if vector_id not in registered:
                lint.fail(scan_path, f"references unregistered conformance vector id: {vector_id}")

    indexed_fixtures: set[str] = set()
    for row in registered.values():
        if row.get("status") != "active":
            continue
        indexed_fixtures.update(
            fixture
            for fixture in row.get("applies_to_fixtures", [])
            if isinstance(fixture, str)
        )
        for source_ref in row.get("source_refs", []):
            if not isinstance(source_ref, str):
                continue
            prefix = "spec/v1/artifacts/fixtures/"
            if source_ref.startswith(prefix) and source_ref.endswith(".json"):
                indexed_fixtures.add(source_ref.removeprefix(prefix))

    for fixture_path in sorted((ARTIFACTS / "fixtures").glob("*.json")):
        fixture = load_json(lint, fixture_path)
        if not isinstance(fixture, dict):
            continue
        runner = fixture.get("runner")
        if (
            isinstance(runner, dict)
            and runner.get("kind") == "named_suite"
            and fixture_path.name not in indexed_fixtures
        ):
            lint.fail(
                fixture_path,
                "runner.kind=named_suite fixture must be indexed by an active vector through "
                "applies_to_fixtures[] or source_refs[]",
            )



def check_cryptographic_suite_kat_bindings(lint: Lint) -> None:
    vector_path = ARTIFACTS / "registry" / "vector-registry.json"
    vector_registry = load_json(lint, vector_path)
    if not isinstance(vector_registry, dict):
        return
    active_vectors = {
        row.get("vector_id")
        for row in vector_registry.get("vectors", [])
        if isinstance(row, dict)
        and row.get("status") == "active"
        and isinstance(row.get("vector_id"), str)
    }
    registries = {
        "signature-alg-registry.json": "algorithms",
        "digest-suite-registry.json": "suites",
        "hpke-suite-registry.json": "suites",
        "mls-ciphersuite-registry.json": "ciphersuites",
    }
    for filename, rows_key in registries.items():
        path = ARTIFACTS / "registry" / filename
        data = load_json(lint, path)
        if not isinstance(data, dict):
            continue
        rows = data.get(rows_key)
        if not isinstance(rows, list):
            lint.fail(path, f"{rows_key} must be an array")
            continue
        for index, row in enumerate(rows):
            label = f"{rows_key}[{index}]"
            if not isinstance(row, dict):
                lint.fail(path, f"{label} must be an object")
                continue
            status = row.get("status")
            kat_vector_id = row.get("kat_vector_id")
            absence_reason = row.get("kat_absence_reason")
            if status == "active":
                if not isinstance(kat_vector_id, str) or not kat_vector_id:
                    lint.fail(path, f"{label} status=active requires kat_vector_id")
                elif kat_vector_id not in active_vectors:
                    lint.fail(path, f"{label}.kat_vector_id is not an active vector: {kat_vector_id!r}")
                if absence_reason is not None:
                    lint.fail(path, f"{label} status=active MUST NOT declare kat_absence_reason")
            elif status == "reserved":
                if kat_vector_id is not None:
                    lint.fail(path, f"{label} status=reserved MUST NOT declare kat_vector_id")
                if not isinstance(absence_reason, str) or not absence_reason.strip():
                    lint.fail(path, f"{label} status=reserved requires kat_absence_reason")



def check_account_data_key_registry(lint: Lint, known: dict[str, set[str]]) -> None:
    path = ARTIFACTS / "registry" / "account-data-key-registry.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return

    if data.get("source_of_truth") is not True:
        lint.fail(path, "source_of_truth must be true")

    rows = data.get("account_data_key_patterns")
    if not isinstance(rows, list) or not rows:
        lint.fail(path, "account_data_key_patterns must be a non-empty list")
        return

    seen: set[str] = set()
    allowed_status = {"active", "reserved", "deprecated"}
    allowed_storage = {"encrypted_account_data", "local_only", "encrypted_account_data_or_local"}
    # zh/models/account-data.md §5: the convergence primitive is declared per row,
    # never defaulted, so an implementation can never guess "CAS/LWW".
    allowed_merge_strategies = {"cas_register"}
    allowed_deletion_modes = {"physical_delete", "value_tombstone"}
    for index, row in enumerate(rows):
        label = f"account_data_key_patterns[{index}]"
        if not isinstance(row, dict):
            lint.fail(path, f"{label} must be an object")
            continue

        key_pattern = row.get("key_pattern")
        if not isinstance(key_pattern, str) or not key_pattern.startswith("ak."):
            lint.fail(path, f"{label}.key_pattern must be a ak.* key pattern")
            continue
        if key_pattern in seen:
            lint.fail(path, f"{label}.key_pattern duplicates {key_pattern}")
        seen.add(key_pattern)

        if row.get("status") not in allowed_status:
            lint.fail(path, f"{label}.status must be one of {sorted(allowed_status)}")
        if row.get("storage") not in allowed_storage:
            lint.fail(path, f"{label}.storage must be one of {sorted(allowed_storage)}")
        if row.get("merge_strategy") not in allowed_merge_strategies:
            lint.fail(path, f"{label}.merge_strategy must be one of {sorted(allowed_merge_strategies)}")
        if row.get("deletion_mode") not in allowed_deletion_modes:
            lint.fail(path, f"{label}.deletion_mode must be one of {sorted(allowed_deletion_modes)}")
        if not isinstance(row.get("scope"), str) or not row["scope"]:
            lint.fail(path, f"{label}.scope must be a non-empty string")
        if not isinstance(row.get("description"), str) or not row["description"].strip():
            lint.fail(path, f"{label}.description must be a non-empty string")

        write_event_kinds = row.get("write_event_kinds")
        if not isinstance(write_event_kinds, list) or not write_event_kinds:
            lint.fail(path, f"{label}.write_event_kinds must be a non-empty array")
        else:
            for event_kind in write_event_kinds:
                if not isinstance(event_kind, str) or event_kind not in known["event_kinds"]:
                    lint.fail(path, f"{label}.write_event_kinds contains unknown Event.kind: {event_kind!r}")

        source_refs = row.get("source_refs")
        if not isinstance(source_refs, list) or not source_refs:
            lint.fail(path, f"{label}.source_refs must be a non-empty array")
            continue

        mentions_key = False
        for source_index, source_ref in enumerate(source_refs):
            source_label = f"{label}.source_refs[{source_index}]"
            if not isinstance(source_ref, str) or not source_ref:
                lint.fail(path, f"{source_label} must be a non-empty string")
                continue
            source_path = Path(source_ref)
            if source_path.is_absolute() or ".." in source_path.parts:
                lint.fail(path, f"{source_label} escapes repository: {source_ref}")
                continue
            resolved = (ROOT / source_path).resolve()
            try:
                resolved.relative_to(ROOT.resolve())
            except ValueError:
                lint.fail(path, f"{source_label} escapes repository: {source_ref}")
                continue
            if not resolved.is_file():
                lint.fail(path, f"{source_label} target does not exist: {source_ref}")
                continue
            try:
                source_text = resolved.read_text(encoding="utf-8")
            except Exception as exc:
                lint.fail(path, f"{source_label} target cannot be read: {source_ref}: {exc}")
                continue
            if key_pattern in source_text:
                mentions_key = True
        if not mentions_key:
            lint.fail(path, f"{label}.source_refs must include at least one source that mentions {key_pattern}")



def check_vector_reference_closure(lint: Lint) -> None:
    definition_paths = [
        SPEC_ROOT / "zh" / "conformance" / "conformance-vectors.md",
        *sorted((ARTIFACTS / "fixtures").glob("*.json")),
    ]
    known_vectors: set[str] = set()
    for path in definition_paths:
        if not path.is_file():
            continue
        try:
            known_vectors.update(VECTOR_ID_TOKEN_RE.findall(path.read_text(encoding="utf-8")))
        except Exception:
            continue
    if not known_vectors:
        lint.fail(SPEC_ROOT / "zh" / "conformance" / "conformance-vectors.md", "no conformance vector ids found")
        return

    for path in markdown_files() + raw_artifact_files():
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for vector_id in sorted(set(VECTOR_ID_TOKEN_RE.findall(text))):
            if vector_id not in known_vectors:
                lint.fail(path, f"references undefined conformance vector id: {vector_id}")



def check_security_closure_fixture(lint: Lint) -> None:
    path = ARTIFACTS / "fixtures" / "security-closure-fixture.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return

    vectors = data.get("security_closure_fixture")
    if not isinstance(vectors, list) or not vectors:
        lint.fail(path, "security_closure_fixture must be a non-empty array")
        return

    conformance_path = SPEC_ROOT / "zh" / "conformance" / "conformance-vectors.md"
    try:
        defined_vectors = set(VECTOR_ID_TOKEN_RE.findall(conformance_path.read_text(encoding="utf-8")))
    except Exception as exc:
        lint.fail(conformance_path, f"could not read conformance vector definitions: {exc}")
        defined_vectors = set()

    seen: set[str] = set()
    for index, vector in enumerate(vectors):
        label = f"security_closure_fixture[{index}]"
        if not isinstance(vector, dict):
            lint.fail(path, f"{label} must be an object")
            continue

        vector_id = vector.get("vector_id")
        if not isinstance(vector_id, str) or not VECTOR_ID_TOKEN_RE.fullmatch(vector_id):
            lint.fail(path, f"{label}.vector_id must be a conformance vector id")
            continue
        if vector_id in seen:
            lint.fail(path, f"{label}.vector_id duplicates {vector_id}")
        seen.add(vector_id)
        if vector_id not in defined_vectors:
            lint.fail(path, f"{label}.vector_id is not defined in conformance-vectors.md: {vector_id}")
        if vector_id not in SECURITY_CLOSURE_VECTOR_IDS:
            lint.fail(path, f"{label}.vector_id is not part of the required security closure set: {vector_id}")

        steps = vector.get("steps")
        if not isinstance(steps, list) or not steps:
            lint.fail(path, f"{label}.steps must be a non-empty array")
            continue
        for step_index, step in enumerate(steps):
            step_label = f"{label}.steps[{step_index}]"
            if not isinstance(step, dict):
                lint.fail(path, f"{step_label} must be an object")
                continue
            if not isinstance(step.get("name"), str) or not step["name"]:
                lint.fail(path, f"{step_label}.name must be a non-empty string")
            if not isinstance(step.get("input"), dict):
                lint.fail(path, f"{step_label}.input must be an object")
            expected = step.get("expected")
            if not isinstance(expected, dict):
                lint.fail(path, f"{step_label}.expected must be an object")
                continue
            if not isinstance(expected.get("outcome"), str) or not expected["outcome"]:
                lint.fail(path, f"{step_label}.expected.outcome must be a non-empty string")
            if not any(key in expected for key in ("reason_code", "invariants", "response")):
                lint.fail(path, f"{step_label}.expected must include reason_code, invariants, or response")
            invariants = expected.get("invariants")
            if "invariants" in expected and (
                not isinstance(invariants, list)
                or not invariants
                or not all(isinstance(item, str) and item for item in invariants)
            ):
                lint.fail(path, f"{step_label}.expected.invariants must be a non-empty string array")
            runner = step.get("runner")
            if not isinstance(runner, dict):
                lint.fail(path, f"{step_label}.runner must be an object")
                continue
            required_runner_fields = {
                "given_state",
                "operation",
                "transcript",
                "expected_state_transition",
                "expected_external_response",
                "expected_audit_reason",
            }
            missing_runner_fields = sorted(required_runner_fields - set(runner))
            if missing_runner_fields:
                lint.fail(path, f"{step_label}.runner missing field(s): {', '.join(missing_runner_fields)}")
                continue
            for object_field in (
                "given_state",
                "transcript",
                "expected_state_transition",
                "expected_external_response",
            ):
                if not isinstance(runner.get(object_field), dict):
                    lint.fail(path, f"{step_label}.runner.{object_field} must be an object")
            for string_field in ("operation", "expected_audit_reason"):
                if not isinstance(runner.get(string_field), str) or not runner[string_field]:
                    lint.fail(path, f"{step_label}.runner.{string_field} must be a non-empty string")
            state_transition = runner.get("expected_state_transition")
            if isinstance(state_transition, dict) and state_transition.get("outcome") != expected.get("outcome"):
                lint.fail(
                    path,
                    f"{step_label}.runner.expected_state_transition.outcome must match expected.outcome",
                )
            external_response = runner.get("expected_external_response")
            reason_code = expected.get("reason_code")
            if isinstance(reason_code, str) and reason_code:
                external_reason = external_response.get("reason_code") if isinstance(external_response, dict) else None
                if external_reason != reason_code and runner.get("expected_audit_reason") != reason_code:
                    lint.fail(
                        path,
                        f"{step_label}.runner must carry expected.reason_code in external response or audit reason",
                    )

    missing = SECURITY_CLOSURE_VECTOR_IDS - seen
    for vector_id in sorted(missing):
        lint.fail(path, f"missing required security closure vector fixture: {vector_id}")



def check_fixtures(lint: Lint, known: dict[str, set[str]]) -> None:
    fixture_dir = ARTIFACTS / "fixtures"
    for path in sorted(fixture_dir.glob("*.json")):
        data = load_json(lint, path)
        if data is None:
            continue
        if path.name == "producer-allocated-identity-collision-fixture.json":
            expected_parameter_source = {
                "registry": "registry/contract-registry.json#id_kind_registry.id_kinds",
                "filter": {"id_form": "producer_allocated"},
                "identity_key": ["mint_authority", "typed_id"],
            }
            if data.get("parameter_source") != expected_parameter_source:
                lint.fail(path, "producer-ID collision fixture must select producer_allocated rows dynamically")
            required_cases = {
                "first_atomic_reservation": "accept_and_reserve_atomically",
                "same_authority_exact_replay": "idempotent_replay",
                "same_authority_conflicting_binding": "reject_and_quarantine",
                "cross_authority_same_uuid": "distinct_identity",
                "bare_typed_id_lookup": "reject",
                "unauthorized_allocator": "reject",
            }
            actual_cases = {
                case.get("name"): case.get("expected")
                for case in data.get("cases", [])
                if isinstance(case, dict)
            }
            if actual_cases != required_cases:
                lint.fail(path, "producer-ID collision fixture must contain the closed six-case contract")
            if "expanded_kinds" in data:
                lint.fail(path, "producer-ID collision fixture must not freeze a hand-maintained kind list")
        check_fixture_schema_validation_cases(lint, path, data)
        check_event_envelope_candidates(lint, path, data, known["event_kinds"])
        for json_path, value, key in walk_json(data):
            if key in {"auth_weight", "authority_class"}:
                lint.fail(path, f"{json_path} uses removed state-resolution authority field: {key}")

            if not isinstance(value, str):
                continue

            for schema_id in SCHEMA_ID_TOKEN_RE.findall(value):
                if schema_id not in known["schema_ids"]:
                    lint.fail(path, f"{json_path} references unknown schema id: {schema_id}")

            for profile_id in PROFILE_ID_TOKEN_RE.findall(value):
                if profile_id not in known["profiles"]:
                    lint.fail(path, f"{json_path} references unknown profile: {profile_id}")

            if key == "event_kind" and value.startswith("ak.") and value not in known["event_kinds"]:
                lint.fail(path, f"{json_path} references unregistered Event.kind: {value}")
            if key in {"operation_id", "mapped_operation_id"} and value.startswith("ak."):
                if value not in known["operation_ids"]:
                    lint.fail(path, f"{json_path} references unregistered operation_id: {value}")
            if key == "call" and ".recovery.call" in json_path and value.startswith("ak."):
                if value not in known["operation_ids"]:
                    lint.fail(path, f"{json_path} references unregistered recovery operation_id: {value}")
            if key == "constraint_kind" and value not in known["constraint_types"]:
                lint.fail(path, f"{json_path} uses invalid constraint_kind: {value}")

            negative_token_branch = any(
                segment in f"{json_path}." for segment in NEGATIVE_TOKEN_PATH_SEGMENTS
            )
            for match in TYPED_ID_TOKEN_RE.finditer(value):
                kind = match.group(1)
                if negative_token_branch:
                    if kind not in known["id_kinds"] and kind not in known["special_id_kinds"]:
                        lint.fail(path, f"{json_path} references unregistered typed ID kind: ak:{kind}:")
                    continue
                check_typed_id_token(lint, path, json_path, kind, match.group(2), known)



def check_snapshot_merkle_fixture(lint: Lint) -> None:
    """Execute the snapshot RFC 6962 root KAT, including actor subranges."""

    path = ARTIFACTS / "fixtures" / "sync-fixture.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return
    challenge = data.get("snapshot_inclusion_challenge")
    if not isinstance(challenge, dict):
        lint.fail(path, "snapshot_inclusion_challenge must be an object")
        return
    entries = challenge.get("event_set_entries")
    manifest = challenge.get("manifest")
    response = challenge.get("base_response")
    if not isinstance(entries, list) or not isinstance(manifest, dict) or not isinstance(response, dict):
        lint.fail(path, "snapshot Merkle KAT is missing entries, manifest, or response")
        return

    def leaf_data(entry: Any) -> bytes:
        return hashlib.sha256(canonical_json(entry).encode("utf-8")).digest()

    def merkle_root(raw_leaf_data: list[bytes]) -> str:
        if not raw_leaf_data:
            root = hashlib.sha256(b"").digest()
        else:
            level = [hashlib.sha256(b"\x00" + value).digest() for value in raw_leaf_data]
            while len(level) > 1:
                next_level: list[bytes] = []
                for offset in range(0, len(level), 2):
                    if offset + 1 == len(level):
                        next_level.append(level[offset])
                    else:
                        next_level.append(
                            hashlib.sha256(b"\x01" + level[offset] + level[offset + 1]).digest()
                        )
                level = next_level
            root = level[0]
        return "sha256:" + root.hex()

    try:
        ordered = sorted(
            entries,
            key=lambda row: (
                row["actor_id"].encode("utf-8"),
                row["actor_seq"],
                row["event_id"].encode("utf-8"),
            ),
        )
        computed = merkle_root([leaf_data(row) for row in ordered])
        commitment = manifest["event_set_commitment"]
        declared = commitment["root"]
    except (KeyError, TypeError) as exc:
        lint.fail(path, f"snapshot Merkle KAT has malformed input: {exc}")
        return

    if declared != computed:
        lint.fail(path, f"snapshot manifest RFC 6962 root {declared} != computed {computed}")
    if response.get("commitment_root") != computed:
        lint.fail(path, "snapshot inclusion response root does not match computed manifest root")

    ranges = commitment.get("actor_seq_ranges")
    if not isinstance(ranges, list):
        lint.fail(path, "snapshot Merkle KAT actor_seq_ranges must be an array")
        return
    for row in ranges:
        if not isinstance(row, dict):
            lint.fail(path, "snapshot Merkle actor_seq_range must be an object")
            continue
        try:
            selected = [
                entry
                for entry in ordered
                if entry["actor_id"] == row["actor_id"]
                and row["from_seq"] <= entry["actor_seq"] <= row["to_seq"]
            ]
            range_root = merkle_root([leaf_data(entry) for entry in selected])
        except (KeyError, TypeError) as exc:
            lint.fail(path, f"snapshot Merkle actor_seq_range is malformed: {exc}")
            continue
        if row.get("root") != range_root:
            lint.fail(
                path,
                f"snapshot actor range {row.get('actor_id')} root {row.get('root')} "
                f"!= computed {range_root}",
            )

    legacy_case = next(
        (
            row
            for row in challenge.get("cases", [])
            if isinstance(row, dict) and row.get("name") == "legacy_unprefixed_commitment_root"
        ),
        None,
    )
    if (
        not isinstance(legacy_case, dict)
        or legacy_case.get("replacement_root") == computed
        or legacy_case.get("expected", {}).get("decision") != "reject"
    ):
        lint.fail(path, "snapshot Merkle KAT must reject a distinct legacy unprefixed root")



def check_fixture_schema_validation_cases(lint: Lint, path: Path, data: Any) -> None:
    if not isinstance(data, dict):
        return
    cases = data.get("schema_validation_cases")
    if cases is None:
        return
    if not isinstance(cases, list) or not cases:
        lint.fail(path, "schema_validation_cases must be a non-empty array when present")
        return
    for index, case in enumerate(cases):
        label = f"schema_validation_cases[{index}]"
        if not isinstance(case, dict):
            lint.fail(path, f"{label} must be an object")
            continue
        schema_ref = case.get("schema_ref")
        instance = case.get("instance")
        expect_valid = case.get("expect_valid", True)
        if not isinstance(schema_ref, str) or not schema_ref:
            lint.fail(path, f"{label}.schema_ref must be a non-empty string")
            continue
        if "instance" not in case:
            lint.fail(path, f"{label}.instance is required")
            continue
        if not isinstance(expect_valid, bool):
            lint.fail(path, f"{label}.expect_valid must be boolean when present")
            continue
        first_expected_error = case.get("first_expected_error")
        if expect_valid:
            if first_expected_error is not None:
                lint.fail(path, f"{label}.first_expected_error is only valid when expect_valid=false")
                continue
        elif not isinstance(first_expected_error, str) or not first_expected_error:
            lint.fail(path, f"{label}.first_expected_error must be a non-empty string when expect_valid=false")
            continue
        case_name = case.get("name")
        if not isinstance(case_name, str) or not case_name:
            case_name = label
        check_json_instance_against_schema(
            lint,
            path,
            case_name,
            schema_ref,
            instance,
            expect_valid,
            first_expected_error,
        )



def check_crypto_signature_fixture(lint: Lint) -> None:
    path = ARTIFACTS / "fixtures" / "crypto-signature-fixture.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return

    vectors = data.get("vectors", [])
    if not isinstance(vectors, list):
        lint.fail(path, "vectors must be a list")
        return

    for index, vector in enumerate(vectors):
        if not isinstance(vector, dict):
            lint.fail(path, f"vectors[{index}] must be an object")
            continue

        event = vector.get("event_without_proofs")
        if isinstance(event, dict):
            signed_event = dict(event)
            # zh/conformance/encoding.md section 6: the digest preimage removes
            # proofs, unsigned, actor_kind and event_id. event_id is excluded
            # because section 4.0 derives it from this very digest.
            signed_event.pop("unsigned", None)
            signed_event.pop("actor_kind", None)
            signed_event.pop("event_id", None)
            expected_canonical = canonical_json(signed_event)
            if vector.get("canonical_event_payload") != expected_canonical:
                lint.fail(path, f"vectors[{index}] canonical_event_payload does not match canonical JSON")
            expected_event_digest = sha256_text(expected_canonical)
            if vector.get("event_digest") != expected_event_digest:
                lint.fail(path, f"vectors[{index}] event_digest does not match canonical_event_payload")

            event_with_proof = vector.get("event_with_proof")
            if isinstance(event_with_proof, dict):
                unsigned = dict(event_with_proof)
                unsigned.pop("proofs", None)
                unsigned.pop("unsigned", None)
                unsigned.pop("actor_kind", None)
                unsigned.pop("event_id", None)
                if unsigned != signed_event:
                    lint.fail(path, f"vectors[{index}] event_with_proof without proofs differs from event_without_proofs")

        binding = vector.get("binding_object")
        if isinstance(binding, dict):
            expected_binding = canonical_json(binding)
            if vector.get("canonical_binding_payload") != expected_binding:
                lint.fail(path, f"vectors[{index}] canonical_binding_payload does not match canonical JSON")
            expected_binding_digest = sha256_text(expected_binding)
            if vector.get("binding_digest") != expected_binding_digest:
                lint.fail(path, f"vectors[{index}] binding_digest does not match canonical_binding_payload")
            if vector.get("detached_payload_b64u") != base64url_text(expected_binding):
                lint.fail(path, f"vectors[{index}] detached_payload_b64u does not match canonical_binding_payload")

        protected_header = vector.get("protected_header")
        if isinstance(protected_header, dict):
            expected_header = canonical_json(protected_header)
            if vector.get("protected_header_canonical") != expected_header:
                lint.fail(path, f"vectors[{index}] protected_header_canonical does not match canonical JSON")

        proof = vector.get("proof")
        if isinstance(proof, dict) and isinstance(vector.get("event_digest"), str):
            if proof.get("event_digest") != vector["event_digest"]:
                lint.fail(path, f"vectors[{index}] proof event_digest differs from vector event_digest")

    negative_cases = data.get("negative_cases")
    if not isinstance(negative_cases, list) or not negative_cases:
        lint.fail(path, "negative_cases must be a non-empty list")
        return
    positive_names = {vector.get("name") for vector in vectors if isinstance(vector, dict)}
    negative_bases = {
        case.get("base_vector")
        for case in negative_cases
        if isinstance(case, dict) and isinstance(case.get("base_vector"), str)
    }
    missing_algorithm_negatives = positive_names - negative_bases
    if missing_algorithm_negatives:
        lint.fail(path, f"each active signature vector needs an algorithm-specific negative case: {sorted(missing_algorithm_negatives)}")



def check_canonical_digest_fixtures(lint: Lint) -> None:
    """T4-1: canonical-JSON recompute guard.

    Walk every fixture JSON and, when it contains both a canonical-input
    object and an expected digest field, recompute the digest from the
    input's canonical bytes and require an exact match.

    Recognized fixture shapes:
      { "input": <obj>, "expected_digest": "sha256:..." }
      { "input": <obj>, "digest": "sha256:..." }
      { "envelope": <obj>, "event_digest": "sha256:..." }
      { "envelope": <obj>, "payload_hash": "sha256:..." }
      { "canonical_bytes": "<hex>", "digest": "sha256:..." }

    This is intentionally narrow: it does not try to canonicalize whole
    repositories of arbitrary fixtures. New fixtures opt in by naming
    their input + digest fields using one of the shapes above.
    """
    fixtures_dir = ARTIFACTS / "fixtures"
    if not fixtures_dir.exists():
        return

    shapes: list[tuple[str, str]] = [
        ("input", "expected_digest"),
        ("input", "digest"),
        ("envelope", "event_digest"),
        ("envelope", "payload_hash"),
        ("canonical_input", "expected_digest"),
    ]

    def iter_dict_nodes(value: Any) -> Iterable[dict[str, Any]]:
        if isinstance(value, dict):
            yield value
            for child in value.values():
                yield from iter_dict_nodes(child)
        elif isinstance(value, list):
            for child in value:
                yield from iter_dict_nodes(child)

    for fixture_path in fixtures_dir.rglob("*.json"):
        data = load_json(lint, fixture_path)
        if data is None:
            continue

        for case in iter_dict_nodes(data):
            for input_key, digest_key in shapes:
                if input_key not in case or digest_key not in case:
                    continue
                expected = case.get(digest_key)
                if not isinstance(expected, str):
                    continue
                if not expected.startswith("sha256:"):
                    # Non-sha256 algorithms are out of scope for this guard.
                    continue
                try:
                    canonical = canonical_json(case[input_key])
                except (TypeError, ValueError) as exc:
                    lint.fail(
                        fixture_path,
                        f"could not canonicalize {input_key!r} for digest check: {exc}",
                    )
                    continue
                expected_canonical = case.get("expected_canonical_bytes_utf8")
                if isinstance(expected_canonical, str) and expected_canonical != canonical:
                    lint.fail(
                        fixture_path,
                        f"canonical bytes mismatch: {input_key!r} produces {canonical!r} "
                        f"but expected_canonical_bytes_utf8={expected_canonical!r}",
                    )
                domain_separator = case.get("domain_separator_utf8", "")
                if not isinstance(domain_separator, str):
                    lint.fail(
                        fixture_path,
                        "domain_separator_utf8 must be a string when present",
                    )
                    continue
                digest_input = domain_separator + canonical
                digest_input_hex = case.get("digest_input_hex")
                if isinstance(digest_input_hex, str) and digest_input_hex != digest_input.encode("utf-8").hex():
                    lint.fail(
                        fixture_path,
                        f"digest_input_hex does not match domain_separator_utf8 || {input_key!r} canonical bytes",
                    )
                recomputed = sha256_text(digest_input)
                if recomputed != expected:
                    lint.fail(
                        fixture_path,
                        f"digest mismatch: domain separator plus {input_key!r} canonical bytes produce "
                        f"{recomputed} but {digest_key!r}={expected}",
                    )



def check_direct_conversation_digest_vectors(lint: Lint) -> None:
    """Pin the two domain-separated Direct Conversation identity digests."""

    fixture_path = ARTIFACTS / "fixtures" / "encoding-fixture.json"
    fixture = load_json(lint, fixture_path)
    if not isinstance(fixture, dict) or not isinstance(fixture.get("vectors"), list):
        return

    vectors = {
        vector.get("vector_id"): vector
        for vector in fixture["vectors"]
        if isinstance(vector, dict) and isinstance(vector.get("vector_id"), str)
    }
    pair = vectors.get("ak.vector.direct_conversation.pair_key.v1")
    binding = vectors.get("ak.vector.direct_conversation.binding_digest.v1")
    if not isinstance(pair, dict):
        lint.fail(fixture_path, "missing direct-conversation pair_key KAT")
        return
    if not isinstance(binding, dict):
        lint.fail(fixture_path, "missing direct-conversation binding_digest KAT")
        return

    expected_pair_domain = "ak.direct-conversation.pair-key.v1\n"
    if pair.get("domain_separator_utf8") != expected_pair_domain:
        lint.fail(fixture_path, "direct-conversation pair_key KAT has the wrong domain separator")
    pair_input = pair.get("input")
    if not isinstance(pair_input, dict) or set(pair_input) != {"participants", "trust_domain_id"}:
        lint.fail(
            fixture_path,
            "direct-conversation pair_key input must be exactly {participants, trust_domain_id}",
        )

    expected_binding_domain = "ak.direct-conversation.binding-digest.v1\n"
    if binding.get("domain_separator_utf8") != expected_binding_domain:
        lint.fail(fixture_path, "direct-conversation binding_digest KAT has the wrong domain separator")
    canonical_binding = binding.get("input")
    valid_digest = binding.get("expected_digest")
    if not isinstance(canonical_binding, dict) or not isinstance(valid_digest, str):
        lint.fail(fixture_path, "direct-conversation binding_digest KAT lacks input or digest")
        return

    expected_binding_fields = {
        "pair_key",
        "participants_unordered",
        "realm_id",
        "main_strand_id",
        "founding_unit_digest",
        "authorization_basis",
        "initial_exact_pair_generation_ref",
    }
    if set(canonical_binding) != expected_binding_fields:
        lint.fail(fixture_path, "binding_digest canonical object has the wrong closed field set")

    def normalize_payload(payload: Any, label: str) -> dict[str, Any] | None:
        if not isinstance(payload, dict):
            lint.fail(fixture_path, f"{label}.payload must be an object")
            return None
        if "binding_digest" in payload:
            lint.fail(fixture_path, f"{label}.payload must not carry binding_digest")
        basis = payload.get("authorization_basis")
        participants = payload.get("participants_unordered")
        refs = basis.get("event_refs") if isinstance(basis, dict) else None
        if (
            not isinstance(participants, list)
            or len(participants) != 2
            or not all(isinstance(value, str) for value in participants)
            or len(set(participants)) != 2
            or not isinstance(basis, dict)
            or set(basis) != {"kind", "event_refs"}
            or not isinstance(basis.get("kind"), str)
            or not isinstance(refs, list)
            or len(refs) != 2
            or not all(isinstance(value, str) for value in refs)
            or len(set(refs)) != 2
        ):
            lint.fail(fixture_path, f"{label}.payload has invalid unordered binding inputs")
            return None
        missing = expected_binding_fields - set(payload)
        if missing:
            lint.fail(fixture_path, f"{label}.payload misses binding fields: {sorted(missing)}")
            return None
        return {
            "pair_key": payload["pair_key"],
            "participants_unordered": sorted(participants, key=lambda value: value.encode("utf-8")),
            "realm_id": payload["realm_id"],
            "main_strand_id": payload["main_strand_id"],
            "founding_unit_digest": payload["founding_unit_digest"],
            "authorization_basis": {
                "kind": basis["kind"],
                "event_refs": sorted(refs, key=lambda value: value.encode("utf-8")),
            },
            "initial_exact_pair_generation_ref": payload[
                "initial_exact_pair_generation_ref"
            ],
        }

    normalization_cases = binding.get("normalization_cases")
    if not isinstance(normalization_cases, list) or not normalization_cases:
        lint.fail(fixture_path, "binding_digest KAT must include normalization cases")
    else:
        for index, case in enumerate(normalization_cases):
            label = f"binding normalization_cases[{index}]"
            if not isinstance(case, dict):
                lint.fail(fixture_path, f"{label} must be an object")
                continue
            normalized = normalize_payload(case.get("payload"), label)
            if normalized is None:
                continue
            if normalized != canonical_binding:
                lint.fail(fixture_path, f"{label} does not normalize to the canonical binding object")
            recomputed = sha256_text(expected_binding_domain + canonical_json(normalized))
            if case.get("expected_digest") != recomputed or recomputed != valid_digest:
                lint.fail(fixture_path, f"{label} does not preserve the binding digest")
            event_context = case.get("event_context")
            if not isinstance(event_context, dict) or not {"actor_id", "proof"} <= set(event_context):
                lint.fail(fixture_path, f"{label} must cover excluded Event actor/proof context")

    mutations = binding.get("mutation_cases")
    if not isinstance(mutations, list):
        lint.fail(fixture_path, "binding_digest KAT must include mutation_cases")
    else:
        mutation_by_name = {
            case.get("name"): case for case in mutations if isinstance(case, dict)
        }
        omitted = mutation_by_name.get("omit_domain_separator")
        if not isinstance(omitted, dict):
            lint.fail(fixture_path, "binding_digest KAT misses omit_domain_separator")
        else:
            canonical_bytes = canonical_json(canonical_binding).encode("utf-8")
            if omitted.get("digest_input_hex") != canonical_bytes.hex():
                lint.fail(fixture_path, "omit_domain_separator does not hash bare canonical bytes")
            omitted_digest = "sha256:" + hashlib.sha256(canonical_bytes).hexdigest()
            if (
                omitted.get("expected_digest") != omitted_digest
                or omitted.get("must_not_equal_valid") is not True
                or omitted_digest == valid_digest
            ):
                lint.fail(fixture_path, "omit_domain_separator is not a strict negative")
        changed = mutation_by_name.get("semantic_main_strand_change")
        if (
            not isinstance(changed, dict)
            or changed.get("must_not_equal_valid") is not True
            or changed.get("expected_digest") == valid_digest
        ):
            lint.fail(fixture_path, "semantic binding mutation is not a strict negative")

    schema_path = ARTIFACTS / "schemas" / "event-payload.schema.json"
    schema = load_json(lint, schema_path)
    bound_payload = (
        schema.get("$defs", {}).get("direct_conversation_bound_payload", {})
        if isinstance(schema, dict)
        else {}
    )
    properties = bound_payload.get("properties", {}) if isinstance(bound_payload, dict) else {}
    if "binding_digest" in properties or bound_payload.get("additionalProperties") is not False:
        lint.fail(schema_path, "binding_digest must remain derived and off-wire in the closed payload")

    registry_path = ARTIFACTS / "registry" / "contract-registry.json"
    registry = load_json(lint, registry_path)
    try:
        projection = registry["event_kind_registry"]["cell_contracts"][
            "ak.direct_conversation.bound"
        ]["cell_writes"][0]["effect_projection"]
    except (KeyError, IndexError, TypeError):
        projection = None
    expected_projection = {
        "kind": "or_set_add",
        "tag": {"dot": True},
        "value": {"field": "payload"},
    }
    if projection != expected_projection:
        lint.fail(
            registry_path,
            "direct-conversation binding core OR-Set projection must remain dot + full payload",
        )



def _stated_preimage_bytes(source: str, decoding: str) -> bytes | None:
    if decoding == "utf8":
        return source.encode("utf-8")
    if decoding == "base64url":
        try:
            return base64.urlsafe_b64decode(source + "=" * (-len(source) % 4))
        except (ValueError, binascii.Error):
            return None
    raise AssertionError(f"unknown stated-preimage decoding: {decoding}")



def _stated_digest(data: bytes, encoding: str) -> str:
    digest = hashlib.sha256(data).digest()
    if encoding == "sha256_hex":
        return "sha256:" + digest.hex()
    if encoding == "raw_hex":
        return digest.hex()
    if encoding == "base64url":
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    raise AssertionError(f"unknown stated-digest encoding: {encoding}")



def check_schema_fixture_canonical_public_material(lint: Lint) -> None:
    """Keep CanonicalPublicMaterial fixtures internally reproducible."""
    fixture_path = ARTIFACTS / "fixtures" / "schema-validation-fixture.json"
    fixture = load_json(lint, fixture_path)
    if fixture is None:
        return

    found = 0
    required = {"canonical_encoding", "value", "canonical_bytes_base64url", "digest"}
    for json_path, node, _ in walk_json(fixture):
        if not isinstance(node, dict) or not required.issubset(node):
            continue
        found += 1
        if node["canonical_encoding"] != "canonical_json":
            continue
        canonical_bytes = canonical_json(node["value"]).encode("utf-8")
        encoded = base64.urlsafe_b64encode(canonical_bytes).rstrip(b"=").decode("ascii")
        digest = "sha256:" + hashlib.sha256(canonical_bytes).hexdigest()
        if node["canonical_bytes_base64url"] != encoded:
            lint.fail(
                fixture_path,
                f"{json_path}.canonical_bytes_base64url does not encode canonical JSON of value",
            )
        if node["digest"] != digest:
            lint.fail(
                fixture_path,
                f"{json_path}.digest={node['digest']} but canonical JSON of value hashes to {digest}",
            )
    if found == 0:
        lint.fail(
            fixture_path,
            "schema fixture must retain a CanonicalPublicMaterial structural case",
        )



def check_stated_preimage_matches_stated_digest(lint: Lint) -> None:
    """Every fixture that spells out a preimage MUST hash to the digest beside it.

    These pairs are the whole point of a KAT: an implementor reads the preimage,
    hashes it and compares. When an id inside the preimage changes and the digest
    beside it does not, the vector still *looks* authoritative while pinning a
    value nothing can produce — which is exactly how the v1 id-form change left
    stale `expected_subject` / `batch_tag` values behind.

    Checking the two pairs that were caught by hand only made *those two* pairs
    unreachable. The recurring failure is a fixture family nobody thought to add,
    so this check has two halves:

    * every registered `(preimage, digest)` pair must agree wherever both keys
      sit in one node — the same rule extended from 2 to 8 families, including
      the two Event-digest families (`canonical_event_payload`,
      `digest_preimage_canonical_bytes_utf8`) where a vector once hashed the
      envelope instead of the preimage; and
    * every key that *states* canonical preimage bytes must be registered,
      either as a pair source or as a documented unpaired key. A new fixture
      family cannot arrive with an unchecked preimage.
    """

    def walk(node: Any, fixture_path: Path, placeholder_digests: bool) -> None:
        if isinstance(node, dict):
            components = node.get("components_array")
            if isinstance(components, list) and isinstance(node.get("expected_subject"), str):
                recomputed = sha256_base64url_text(canonical_json(components))
                if recomputed != node["expected_subject"]:
                    lint.fail(
                        fixture_path,
                        f"'expected_subject'={node['expected_subject']} but "
                        f"'components_array' hashes to {recomputed}",
                    )
            for key, value in node.items():
                if not isinstance(value, str) or not STATED_PREIMAGE_KEY_RE.search(key):
                    continue
                registered = key in UNPAIRED_STATED_PREIMAGE_KEYS or any(
                    key == source for source, *_ in STATED_PREIMAGE_DIGEST_PAIRS
                )
                if not registered:
                    lint.fail(
                        fixture_path,
                        f"{key!r} states canonical preimage bytes but is not registered: add it to "
                        "STATED_PREIMAGE_DIGEST_PAIRS with the digest it must hash to, or to "
                        "UNPAIRED_STATED_PREIMAGE_KEYS with the reason no digest can check it",
                    )
            if not placeholder_digests:
                for source_key, digest_key, decoding, encoding, prefix in (
                    STATED_PREIMAGE_DIGEST_PAIRS
                ):
                    source = node.get(source_key)
                    digest = node.get(digest_key)
                    if not isinstance(source, str) or not isinstance(digest, str):
                        continue
                    data = _stated_preimage_bytes(source, decoding)
                    if data is None:
                        lint.fail(
                            fixture_path,
                            f"{source_key!r} is not decodable as {decoding}",
                        )
                        continue
                    declared_prefix = node.get("domain_separator_utf8")
                    effective_prefix = (
                        declared_prefix
                        if not prefix and isinstance(declared_prefix, str)
                        else prefix
                    )
                    recomputed = _stated_digest(effective_prefix.encode("utf-8") + data, encoding)
                    if recomputed != digest:
                        domain = f" under {effective_prefix!r}" if effective_prefix else ""
                        lint.fail(
                            fixture_path,
                            f"{digest_key!r}={digest} but {source_key!r} hashes{domain} to "
                            f"{recomputed}: the stated preimage and the stated digest disagree",
                        )
            for value in node.values():
                walk(value, fixture_path, placeholder_digests)
        elif isinstance(node, list):
            for value in node:
                walk(value, fixture_path, placeholder_digests)

    for fixture_path in sorted((ARTIFACTS / "fixtures").glob("*.json")):
        fixture = load_json(lint, fixture_path)
        if fixture is not None:
            walk(fixture, fixture_path, fixture_path.name in PLACEHOLDER_DIGEST_FIXTURES)



def check_event_batch_receipt_normalization_vector(lint: Lint) -> None:
    fixture_path = ARTIFACTS / "fixtures" / "encoding-fixture.json"
    fixture = load_json(lint, fixture_path)
    if not isinstance(fixture, dict):
        return
    vector = next(
        (
            item
            for item in fixture.get("vectors", [])
            if isinstance(item, dict)
            and item.get("vector_id") == "ak.vector.encoding.event_batch_receipt_digest.v1"
        ),
        None,
    )
    if not isinstance(vector, dict):
        lint.fail(fixture_path, "missing Event Batch Receipt digest vector")
        return
    receipt = vector.get("input")
    expected_digest = vector.get("expected_digest")
    if not isinstance(receipt, dict) or not isinstance(expected_digest, str):
        lint.fail(fixture_path, "Event Batch Receipt vector must declare input and expected_digest")
        return

    def normalize_events(events: Any) -> list[Any] | None:
        if not isinstance(events, list) or not events:
            return None
        by_key: dict[bytes, Any] = {}
        for event in events:
            key = canonical_json(event).encode("utf-8")
            by_key[key] = event
        return [by_key[key] for key in sorted(by_key)]

    baseline_events = receipt.get("events")
    normalized_baseline = normalize_events(baseline_events)
    if normalized_baseline is None or baseline_events != normalized_baseline:
        lint.fail(fixture_path, "Event Batch Receipt vector events must already be canonical and unique")

    cases = vector.get("normalization_cases")
    if not isinstance(cases, list) or len(cases) < 3:
        lint.fail(fixture_path, "Event Batch Receipt vector must cover normalize, unsorted, and duplicate cases")
        return
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            lint.fail(fixture_path, f"normalization_cases[{index}] must be an object")
            continue
        if "input_events" in case:
            normalized = normalize_events(case.get("input_events"))
            if normalized != case.get("expected_events"):
                lint.fail(fixture_path, f"normalization_cases[{index}] expected_events mismatch")
                continue
            normalized_receipt = copy.deepcopy(receipt)
            normalized_receipt["events"] = normalized
            normalized_digest = sha256_text(canonical_json(normalized_receipt))
            if normalized_digest != case.get("expected_digest") or normalized_digest != expected_digest:
                lint.fail(fixture_path, f"normalization_cases[{index}] digest mismatch")
        if "wire_events" in case:
            wire_events = case.get("wire_events")
            if normalize_events(wire_events) == wire_events:
                lint.fail(fixture_path, f"normalization_cases[{index}] negative wire is canonical")
            if case.get("expected") != "schema_violation_before_digest_verification":
                lint.fail(fixture_path, f"normalization_cases[{index}] must reject before digest verification")

    schema_path = ARTIFACTS / "schemas" / "event-batch-receipt.schema.json"
    schema = load_json(lint, schema_path)
    events_schema = schema.get("properties", {}).get("events", {}) if isinstance(schema, dict) else {}
    if events_schema.get("uniqueItems") is not True:
        lint.fail(schema_path, "Event Batch Receipt events must set uniqueItems=true")



def check_encrypted_envelope_digest_vector(lint: Lint) -> None:
    fixture_path = ARTIFACTS / "fixtures" / "encoding-fixture.json"
    fixture = load_json(lint, fixture_path)
    if not isinstance(fixture, dict):
        return
    vector = next(
        (
            item
            for item in fixture.get("vectors", [])
            if isinstance(item, dict)
            and item.get("vector_id") == "ak.vector.encoding.encrypted_envelope_digest.v1"
        ),
        None,
    )
    if not isinstance(vector, dict):
        lint.fail(fixture_path, "missing Encrypted Envelope digest vector")
        return

    kat = vector.get("event_ref_digest_kat")
    metadata = vector.get("payload_metadata")
    if not isinstance(kat, dict) or not isinstance(metadata, dict):
        lint.fail(fixture_path, "Encrypted Envelope vector must declare payload_metadata and event_ref_digest_kat")
        return
    domain = kat.get("domain_separator_utf8")
    event_id = kat.get("event_id")
    realm_id = kat.get("realm_id")
    if not all(isinstance(value, str) for value in (domain, event_id, realm_id)):
        lint.fail(fixture_path, "event_ref_digest_kat inputs must be strings")
        return
    digest_input = domain.encode("utf-8") + b"\x00" + event_id.encode("utf-8") + b"\x00" + realm_id.encode("utf-8")
    expected_ref_digest = "sha256:" + hashlib.sha256(digest_input).hexdigest()
    if kat.get("digest_input_hex") != digest_input.hex():
        lint.fail(fixture_path, "event_ref_digest_kat digest_input_hex does not match canonical input")
    if kat.get("expected_digest") != expected_ref_digest:
        lint.fail(fixture_path, "event_ref_digest_kat expected_digest does not match canonical input")
    aad = metadata.get("aad")
    if not isinstance(aad, dict) or aad.get("realm_id") != realm_id or aad.get("event_ref_digest") != expected_ref_digest:
        lint.fail(fixture_path, "payload_metadata.aad is not bound to event_ref_digest_kat")

    mutations = kat.get("mutation_cases")
    expected_mutations = {
        "omit_nul_separators": domain.encode("utf-8") + event_id.encode("utf-8") + realm_id.encode("utf-8"),
        "swap_event_id_and_realm_id": (
            domain.encode("utf-8") + b"\x00" + realm_id.encode("utf-8") + b"\x00" + event_id.encode("utf-8")
        ),
        "append_trailing_nul": digest_input + b"\x00",
    }
    if not isinstance(mutations, list) or len(mutations) != len(expected_mutations):
        lint.fail(fixture_path, "event_ref_digest_kat must cover separator, field-order, and trailing-byte mutations")
    else:
        seen_mutation_names: set[str] = set()
        for index, mutation in enumerate(mutations):
            if not isinstance(mutation, dict):
                lint.fail(fixture_path, f"event_ref_digest_kat mutation_cases[{index}] must be an object")
                continue
            mutation_name = mutation.get("name")
            if (
                not isinstance(mutation_name, str)
                or mutation_name not in expected_mutations
                or mutation_name in seen_mutation_names
            ):
                lint.fail(fixture_path, f"event_ref_digest_kat mutation_cases[{index}] has unknown or duplicate name")
                continue
            seen_mutation_names.add(mutation_name)
            try:
                mutated_input = bytes.fromhex(mutation.get("digest_input_hex", ""))
            except (TypeError, ValueError):
                lint.fail(fixture_path, f"event_ref_digest_kat mutation_cases[{index}] has invalid hex")
                continue
            if mutated_input != expected_mutations[mutation_name]:
                lint.fail(fixture_path, f"event_ref_digest_kat mutation_cases[{index}] input does not match its name")
            mutated_digest = "sha256:" + hashlib.sha256(mutated_input).hexdigest()
            if mutation.get("expected_digest") != mutated_digest:
                lint.fail(fixture_path, f"event_ref_digest_kat mutation_cases[{index}] digest mismatch")
            if mutation.get("must_not_equal_valid") is not True or mutated_digest == expected_ref_digest:
                lint.fail(fixture_path, f"event_ref_digest_kat mutation_cases[{index}] is not a strict negative")

    canonical_metadata = canonical_json(metadata)
    if vector.get("expected_metadata_canonical_bytes_utf8") != canonical_metadata:
        lint.fail(fixture_path, "Encrypted Envelope canonical payload_metadata bytes mismatch")
    if isinstance(aad, dict) and vector.get("aad_digest") != sha256_text(canonical_json(aad)):
        lint.fail(fixture_path, "Encrypted Envelope aad_digest mismatch")
    ciphertext_base64url = vector.get("ciphertext_base64url")
    if not isinstance(ciphertext_base64url, str):
        lint.fail(fixture_path, "Encrypted Envelope ciphertext_base64url must be a string")
        return
    try:
        padded = ciphertext_base64url + "=" * (-len(ciphertext_base64url) % 4)
        ciphertext = base64.urlsafe_b64decode(padded)
    except (ValueError, base64.binascii.Error):
        lint.fail(fixture_path, "Encrypted Envelope ciphertext_base64url is invalid")
        return
    expected_digest = "sha256:" + hashlib.sha256(canonical_metadata.encode("utf-8") + ciphertext).hexdigest()
    if vector.get("expected_digest") != expected_digest:
        lint.fail(fixture_path, "Encrypted Envelope expected_digest mismatch")



def check_one_of_branch_discriminability(lint: Lint) -> None:
    """Every object-union `oneOf` must have a decidable branch.

    ``oneOf`` means "exactly one branch matches". When the branches are objects
    that overlap, a single instance can satisfy two of them and the whole union
    fails, and a statically typed decoder has no principled way to choose. A
    union is decidable when one of these holds:

      * a discriminator: one required property carries a distinct single value
        (``const`` or a one-entry ``enum``) in every branch;
      * structural exclusivity: for every pair of branches, one side is closed
        and the other requires a property that side does not declare, the two
        pin a shared required property to different constants, or one side
        explicitly refuses a property the other requires.

    Two shapes are deliberately out of scope. A document-level ``oneOf`` is a
    catalog of DTOs whose consumers bind a fragment, not a runtime union. A
    constraint-style ``oneOf`` whose branches declare no ``required`` and no
    ``$ref`` expresses legal field combinations of one object, and its
    discriminator lives on the enclosing schema.
    """

    documents = {
        path.name: load_json(lint, path)
        for path in sorted((ARTIFACTS / "schemas").glob("*.json"))
    }

    def resolve_pointer(document: Any, pointer: str) -> Any:
        node = document
        for part in pointer.lstrip("#/").split("/"):
            if not part:
                continue
            part = part.replace("~1", "/").replace("~0", "~")
            if isinstance(node, dict) and part in node:
                node = node[part]
            elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
                node = node[int(part)]
            else:
                return None
        return node

    def deref(node: Any, current: str, depth: int = 0) -> Any:
        if depth > 8 or not isinstance(node, dict) or "$ref" not in node:
            return node
        reference = node["$ref"]
        if reference.startswith("#"):
            return deref(resolve_pointer(documents[current], reference), current, depth + 1)
        match = ONE_OF_REFERENCE_RE.match(reference)
        if not match or match.group(1) not in documents:
            return None
        target = documents[match.group(1)]
        return deref(resolve_pointer(target, match.group(2) or "#"), match.group(1), depth + 1)

    def single_valued(node: Any) -> str | None:
        if not isinstance(node, dict):
            return None
        if "const" in node:
            return json.dumps(node["const"], sort_keys=True)
        enum = node.get("enum")
        if isinstance(enum, list) and len(enum) == 1:
            return json.dumps(enum[0], sort_keys=True)
        return None

    def discriminator(branches: list[dict[str, Any]], outer_required: set[str]) -> str | None:
        candidates: set[str] | None = None
        for branch in branches:
            required = set(branch.get("required", [])) | outer_required
            properties = branch.get("properties") or {}
            names = {name for name in required if single_valued(properties.get(name))}
            candidates = names if candidates is None else candidates & names
        for name in sorted(candidates or ()):
            values = [single_valued((branch.get("properties") or {})[name]) for branch in branches]
            if len(set(values)) == len(values):
                return name
        return None

    def closed(node: dict[str, Any]) -> bool:
        return node.get("additionalProperties") is False or node.get("unevaluatedProperties") is False

    def forbidden(node: dict[str, Any]) -> set[str]:
        names: set[str] = set()
        negated = node.get("not")
        if isinstance(negated, dict):
            names.update(name for name in negated.get("required", []) if isinstance(name, str))
            for branch in negated.get("anyOf", []) or []:
                if isinstance(branch, dict):
                    names.update(n for n in branch.get("required", []) if isinstance(n, str))
        return names

    def exclusive(left: dict[str, Any], right: dict[str, Any]) -> bool:
        left_required = set(left.get("required", []))
        right_required = set(right.get("required", []))
        if forbidden(left) & right_required or forbidden(right) & left_required:
            return True
        if closed(right) and left_required - set((right.get("properties") or {}).keys()):
            return True
        if closed(left) and right_required - set((left.get("properties") or {}).keys()):
            return True
        for name in left_required & right_required:
            left_value = single_valued((left.get("properties") or {}).get(name))
            right_value = single_valued((right.get("properties") or {}).get(name))
            if left_value and right_value and left_value != right_value:
                return True
        return False

    def sites(name: str, node: Any, pointer: str, out: list[tuple[str, list[Any], set[str]]]) -> None:
        if isinstance(node, dict):
            branches = node.get("oneOf")
            if isinstance(branches, list) and len(branches) > 1:
                out.append((pointer, branches, set(node.get("required", []))))
            for key, value in node.items():
                sites(name, value, f"{pointer}/{key}", out)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                sites(name, value, f"{pointer}/{index}", out)

    for document_name, document in documents.items():
        if not isinstance(document, dict):
            continue
        path = ARTIFACTS / "schemas" / document_name
        found: list[tuple[str, list[Any], set[str]]] = []
        sites(document_name, document, "", found)
        for pointer, branches, outer_required in found:
            if pointer == "":
                continue
            if all(
                isinstance(branch, dict) and not branch.get("required") and "$ref" not in branch
                for branch in branches
            ):
                continue
            resolved = [deref(branch, document_name) for branch in branches]
            if not all(isinstance(node, dict) for node in resolved):
                continue
            if not all(
                node.get("type") == "object" or "properties" in node for node in resolved
            ):
                continue
            if discriminator(resolved, outer_required):
                continue
            if all(
                exclusive(left, right)
                for index, left in enumerate(resolved)
                for right in resolved[index + 1 :]
            ):
                continue
            lint.fail(
                path,
                f"{pointer or '/'} oneOf object branches are not decidable: add a required "
                "single-valued discriminator, close a branch, or make the required sets exclusive",
            )



def check_string_profile_format_vectors(lint: Lint) -> None:
    """The custom string formats must keep one executable vector set.

    ``string-profiles.schema.json`` declares eight ``arkret-*`` formats whose
    normative semantics (PRECIS, UTS #46, NFC) cannot be expressed by the
    coarse JSON Schema pattern and length keywords. This check binds the
    fixture to the schema so every format keeps positive and negative vectors,
    and it proves the declared rejection layer of each negative value: a
    ``schema_pattern`` value must already fail the coarse shape, while a
    ``profile_validator`` value must pass it, which is exactly why a runtime
    that only validates JSON Schema is insufficient.
    """

    schema_path = ARTIFACTS / "schemas" / "string-profiles.schema.json"
    fixture_path = ARTIFACTS / "fixtures" / "string-profile-fixture.json"
    schema = load_json(lint, schema_path)
    fixture = load_json(lint, fixture_path)
    if not isinstance(schema, dict) or not isinstance(fixture, dict):
        return
    if Draft202012Validator is None:
        return

    defs = schema.get("$defs")
    if not isinstance(defs, dict):
        lint.fail(schema_path, "string profiles schema must declare $defs")
        return
    declared_formats = {
        node["format"]: f"schemas/string-profiles.schema.json#/$defs/{name}"
        for name, node in defs.items()
        if isinstance(node, dict) and isinstance(node.get("format"), str)
    }

    vectors = fixture.get("vectors")
    if not isinstance(vectors, list) or not vectors:
        lint.fail(fixture_path, "string profile fixture must declare a non-empty vectors list")
        return

    covered: dict[str, str] = {}
    for index, vector in enumerate(vectors):
        label = f"vectors[{index}]"
        if not isinstance(vector, dict):
            lint.fail(fixture_path, f"{label} must be an object")
            continue
        format_name = vector.get("format")
        schema_ref = vector.get("schema_ref")
        if not isinstance(format_name, str) or format_name not in declared_formats:
            lint.fail(fixture_path, f"{label}.format is not declared by string-profiles.schema.json")
            continue
        if format_name in covered:
            lint.fail(fixture_path, f"{label}.format duplicates {format_name}")
            continue
        covered[format_name] = schema_ref if isinstance(schema_ref, str) else ""
        if schema_ref != declared_formats[format_name]:
            lint.fail(
                fixture_path,
                f"{label}.schema_ref must be {declared_formats[format_name]} for {format_name}",
            )
            continue

        definition = dict(defs[schema_ref.rsplit("/", 1)[-1]])
        definition.pop("format", None)
        definition["$defs"] = defs
        validator = Draft202012Validator(definition)

        accepted = vector.get("accepted")
        if not isinstance(accepted, list) or not accepted:
            lint.fail(fixture_path, f"{label}.accepted must be a non-empty list")
        else:
            for value in accepted:
                if not isinstance(value, str):
                    lint.fail(fixture_path, f"{label}.accepted values must be strings")
                elif not validator.is_valid(value):
                    lint.fail(
                        fixture_path,
                        f"{label}.accepted value fails the coarse {format_name} shape: {value!r}",
                    )
                elif unicodedata.normalize("NFC", value) != value:
                    lint.fail(
                        fixture_path,
                        f"{label}.accepted value is not NFC: {value!r}",
                    )

        rejected = vector.get("rejected")
        if not isinstance(rejected, list) or not rejected:
            lint.fail(fixture_path, f"{label}.rejected must be a non-empty list")
            continue
        profile_only = 0
        for position, case in enumerate(rejected):
            case_label = f"{label}.rejected[{position}]"
            if not isinstance(case, dict):
                lint.fail(fixture_path, f"{case_label} must be an object")
                continue
            value = case.get("value")
            layer = case.get("rejected_by")
            if not isinstance(value, str):
                lint.fail(fixture_path, f"{case_label}.value must be a string")
                continue
            if not isinstance(case.get("reason"), str) or not case.get("reason"):
                lint.fail(fixture_path, f"{case_label}.reason must be a non-empty string")
            if layer not in {"schema_pattern", "profile_validator"}:
                lint.fail(fixture_path, f"{case_label}.rejected_by must be schema_pattern or profile_validator")
                continue
            accepted_by_shape = validator.is_valid(value)
            if layer == "schema_pattern" and accepted_by_shape:
                lint.fail(
                    fixture_path,
                    f"{case_label} claims schema_pattern but the coarse shape accepts it: {value!r}",
                )
            if layer == "profile_validator":
                profile_only += 1
                if not accepted_by_shape:
                    lint.fail(
                        fixture_path,
                        f"{case_label} claims profile_validator but the coarse shape already rejects it: {value!r}",
                    )
        if profile_only == 0:
            lint.fail(
                fixture_path,
                f"{label} must carry at least one profile_validator-only negative for {format_name}",
            )

    for format_name in sorted(set(declared_formats) - set(covered)):
        lint.fail(fixture_path, f"custom format has no vector: {format_name}")



def check_declared_canonical_json_strings(lint: Lint) -> None:
    """A fixture field named `*_canonical_json` MUST actually be canonical.

    RFC 8785 canonical JSON sorts object keys. A fixture that stores an
    unsorted string under a `_canonical_json` name is self-contradictory: the
    vector stays internally consistent while disagreeing with every conforming
    implementation, and the mismatch only surfaces downstream. The
    `passphrase_kdf_kat` nonce transcript failed exactly this way, and every
    value derived from it had to be regenerated.
    """
    fixture_root = ARTIFACTS / "fixtures"
    for path in sorted(fixture_root.glob("*.json")):
        data = load_json(lint, path)
        if data is None:
            continue

        def walk(node: Any, pointer: str) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    child = f"{pointer}/{key}"
                    if key.endswith("_canonical_json") and isinstance(value, str):
                        try:
                            parsed = json.loads(value)
                        except json.JSONDecodeError:
                            lint.fail(path, f"{child} is not parseable JSON")
                            continue
                        if canonical_json(parsed) != value:
                            lint.fail(
                                path,
                                f"{child} is named canonical but is not RFC 8785 canonical "
                                "(object keys must be sorted, no insignificant whitespace)",
                            )
                    walk(value, child)
            elif isinstance(node, list):
                for index, value in enumerate(node):
                    walk(value, f"{pointer}/{index}")

        walk(data, "")



def check_reducer_profile_registry(lint: Lint) -> None:
    registry_path = ARTIFACTS / "registry" / "reducer-profile-registry.json"
    registry = load_json(lint, registry_path)
    if not isinstance(registry, dict):
        return
    rows = registry.get("profiles")
    if not isinstance(rows, list) or not rows:
        lint.fail(registry_path, "profiles must be a non-empty array")
        return

    profile_pattern = re.compile(r"^ak\.reducer(?:\.[a-z0-9][a-z0-9_.-]*)?\.v[0-9]+$")
    ids: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            lint.fail(registry_path, f"profiles[{index}] must be an object")
            continue
        profile_id = row.get("profile_id")
        if not isinstance(profile_id, str) or not profile_pattern.fullmatch(profile_id):
            lint.fail(registry_path, f"profiles[{index}].profile_id must use ak.reducer.*.vN")
            continue
        if profile_id in ids:
            lint.fail(registry_path, f"duplicate reducer profile id: {profile_id}")
        ids.add(profile_id)
        if row.get("status") != "active":
            lint.fail(registry_path, f"{profile_id} status must be active")
        if not isinstance(row.get("governs"), list) or not row["governs"]:
            lint.fail(registry_path, f"{profile_id} must declare governs[]")
        if not isinstance(row.get("supported_lattices"), list) or not row["supported_lattices"]:
            lint.fail(registry_path, f"{profile_id} must declare supported_lattices[]")
        edges = row.get("upgrade_edges")
        if not isinstance(edges, list):
            lint.fail(registry_path, f"{profile_id}.upgrade_edges must be an array")

    for row in rows:
        if not isinstance(row, dict):
            continue
        for edge_index, edge in enumerate(row.get("upgrade_edges", [])):
            if not isinstance(edge, dict):
                lint.fail(registry_path, f"{row.get('profile_id')}.upgrade_edges[{edge_index}] must be an object")
                continue
            target = edge.get("target_profile")
            transition = edge.get("state_transition")
            if target not in ids:
                lint.fail(registry_path, f"upgrade edge target is not registered: {target}")
            if transition != "identity" and not isinstance(transition, dict):
                lint.fail(registry_path, "upgrade edge state_transition must be identity or a deterministic transition object")

    event_schema_path = ARTIFACTS / "schemas" / "event-envelope.schema.json"
    event_schema = load_json(lint, event_schema_path)
    requirement_properties = (
        event_schema.get("properties", {}).get("requirements", {}).get("properties", {})
        if isinstance(event_schema, dict)
        else {}
    )
    if "reducer" in requirement_properties:
        lint.fail(event_schema_path, "Event requirements must not declare reducer selection")

    realm_schema_path = ARTIFACTS / "schemas" / "realm.schema.json"
    realm_schema = load_json(lint, realm_schema_path)
    if isinstance(realm_schema, dict):
        if "reducer_profile" not in realm_schema.get("required", []):
            lint.fail(realm_schema_path, "Realm.reducer_profile must be required")
        reducer_property = realm_schema.get("properties", {}).get("reducer_profile")
        if not isinstance(reducer_property, dict) or reducer_property.get("pattern") != profile_pattern.pattern:
            lint.fail(realm_schema_path, "Realm.reducer_profile must use the canonical reducer profile pattern")

    event_registry_path = ARTIFACTS / "registry" / "event-kind-registry.json"
    event_registry = load_json(lint, event_registry_path)
    event_rows = event_registry.get("event_kinds", []) if isinstance(event_registry, dict) else []
    by_kind = {
        row.get("event_kind"): row
        for row in event_rows
        if isinstance(row, dict) and isinstance(row.get("event_kind"), str)
    }
    expected_family = "ak.component.realm.reducer_profile.v1"
    create_writes = by_kind.get("ak.realm.create", {}).get("cell_writes", [])
    upgrade_writes = by_kind.get("ak.realm.upgrade", {}).get("cell_writes", [])
    create_profile_writes = [write for write in create_writes if write.get("cell_family") == expected_family]
    upgrade_profile_writes = [write for write in upgrade_writes if write.get("cell_family") == expected_family]
    if len(create_profile_writes) != 1 or create_profile_writes[0].get("cell_subject") is not None:
        lint.fail(event_registry_path, "ak.realm.create must initialize exactly one reducer-profile singleton cell")
    if len(upgrade_profile_writes) != 1 or upgrade_profile_writes[0].get("cell_subject") is not None:
        lint.fail(event_registry_path, "ak.realm.upgrade must write exactly one reducer-profile singleton cell")

    dto_path = ARTIFACTS / "schemas" / "service-operation-dtos.schema.json"
    dto_schema = load_json(lint, dto_path)
    binding = dto_schema.get("$defs", {}).get("FederationServiceBindingRef", {}) if isinstance(dto_schema, dict) else {}
    binding_properties = binding.get("properties", {}) if isinstance(binding, dict) else {}
    if any(name in binding_properties for name in ("reducer_profile", "reducer_profile_digest")):
        lint.fail(dto_path, "FederationServiceBindingRef must not carry reducer identity")

    describe_path = ARTIFACTS / "schemas" / "service-describe.schema.json"
    describe = load_json(lint, describe_path)
    supported = describe.get("properties", {}).get("supported_reducer_profiles") if isinstance(describe, dict) else None
    if not isinstance(supported, dict):
        lint.fail(describe_path, "ServiceDescribe must declare supported_reducer_profiles")



def check_mls_governance_proof_fixture(lint: Lint) -> None:
    path = ARTIFACTS / "fixtures" / "mls-governance-proof-fixture.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return

    verifier_vector = "ak.vector.mls.governance_proof.verifier.v1"
    materializer_vector = "ak.vector.mls.governance_proof.materializer.v1"
    bounds_vector = "ak.vector.scalability.mls_governance_proof_bounds.v1"
    profile_id = "ak.profile.mls_governance_binding.full.v1"
    expected_vectors = {verifier_vector, materializer_vector}

    if data.get("generated_by") != "tools/generate_mls_governance_proof_fixture.py":
        lint.fail(path, "MLS governance proof fixture must name its deterministic generator")
    if set(data.get("covers_vectors", [])) != expected_vectors:
        lint.fail(path, "MLS governance proof fixture must cover the verifier and materializer vectors exactly")
    if data.get("required_companion_vectors") != [bounds_vector]:
        lint.fail(path, "MLS governance proof fixture must require the bounds companion vector")

    expected_consumers = {
        "sdk_proof_verifier": "ak.suite.mls.governance_proof_bundle.verify.v1",
        "server_materializer": "ak.suite.mls.governance_proof_bundle.materialize.v1",
    }
    consumers = data.get("consumer_contracts")
    actual_consumers = {
        row.get("role"): row.get("entrypoint")
        for row in consumers
        if isinstance(row, dict)
    } if isinstance(consumers, list) else {}
    if actual_consumers != expected_consumers:
        lint.fail(path, f"MLS governance proof consumer ownership mismatch: {actual_consumers}")
    for row in consumers if isinstance(consumers, list) else []:
        outputs = set(row.get("required_output_fields", [])) if isinstance(row, dict) else set()
        if row.get("role") == "sdk_proof_verifier":
            required_outputs = {
                "case_name", "schema_result", "decision", "failure_stage", "reason_code",
                "verified_bundle_digest", "epoch_advanced",
            }
        else:
            required_outputs = {
                "case_name", "decision", "error_code", "response_count", "bundle_digest",
                "chunk_digests", "peak_buffer_bytes", "partial_manifest_emitted",
            }
        if outputs != required_outputs:
            lint.fail(path, f"{row.get('role')} required output contract drifted: {sorted(outputs)}")

    profile_path = ARTIFACTS / "profiles" / "conformance-profiles.json"
    profiles = load_json(lint, profile_path)
    requirement = (
        profiles.get("profile_requirements", {}).get(profile_id, {})
        if isinstance(profiles, dict)
        else {}
    )
    required_profile_refs = {
        "required_endpoints": "ak.self.events.read.mls_governance_proof",
        "required_schemas": "ak.schema.mls_governance_proof_bundle.v1",
        "required_fixtures": path.name,
    }
    for field, value in required_profile_refs.items():
        if value not in requirement.get(field, []):
            lint.fail(profile_path, f"{profile_id}.{field} must include {value}")

    vector_path = ARTIFACTS / "registry" / "vector-registry.json"
    vector_data = load_json(lint, vector_path)
    rows = {
        row.get("vector_id"): row
        for row in vector_data.get("vectors", [])
        if isinstance(row, dict)
    } if isinstance(vector_data, dict) else {}
    for vector_id in expected_vectors:
        row = rows.get(vector_id, {})
        if row.get("status") != "active" or row.get("applies_to_fixtures") != [path.name]:
            lint.fail(vector_path, f"{vector_id} must be active and owned by {path.name}")
    bounds_row = rows.get(bounds_vector, {})
    if bounds_row.get("status") != "active" or bounds_row.get("applies_to_profiles") != [profile_id]:
        lint.fail(vector_path, f"{bounds_vector} must apply directly to {profile_id}")

    def raw_sha256(value: bytes) -> bytes:
        return hashlib.sha256(value).digest()

    def wire_sha256(value: bytes) -> str:
        return "sha256:" + raw_sha256(value).hex()

    def raw_digest(value: Any, label: str) -> bytes:
        if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
            lint.fail(path, f"{label} must be a sha256 wire digest")
            return b""
        return bytes.fromhex(value.split(":", 1)[1])

    def merkle_root(leaf_data: list[bytes]) -> str:
        if not leaf_data:
            return "sha256:" + raw_sha256(b"").hex()
        level = [raw_sha256(b"\x00" + item) for item in leaf_data]
        while len(level) > 1:
            next_level: list[bytes] = []
            for index in range(0, len(level), 2):
                if index + 1 == len(level):
                    next_level.append(level[index])
                else:
                    next_level.append(raw_sha256(b"\x01" + level[index] + level[index + 1]))
            level = next_level
        return "sha256:" + level[0].hex()

    source = data.get("source_state", {})
    events = source.get("covered_events", []) if isinstance(source, dict) else []
    state = source.get("joined_control_state", []) if isinstance(source, dict) else []
    seals = source.get("accepted_seals", []) if isinstance(source, dict) else []
    known = data.get("known_answer", {})
    if len(events) != 2 or len(state) != 2 or len(seals) != 1:
        lint.fail(path, "base KAT must contain two Events, two state leaves and one Seal")
        return
    event_kats = known.get("event_steps", []) if isinstance(known, dict) else []
    event_digests: list[str] = []
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            lint.fail(path, f"covered_events[{index}] must be an object")
            continue
        producer = {
            key: value
            for key, value in event.items()
            if key not in {"proofs", "unsigned", "effective_scope", "actor_kind", "event_id"}
        }
        # event_id is excluded because zh/conformance/encoding.md section 4.0
        # derives it from this digest; see section 6 for the two-class rationale.
        producer_bytes = canonical_json(producer).encode("utf-8")
        event_digest = wire_sha256(producer_bytes)
        event_digests.append(event_digest)
        proofs = event.get("proofs", [])
        proof = proofs[0] if isinstance(proofs, list) and len(proofs) == 1 and isinstance(proofs[0], dict) else {}
        if proof.get("event_digest") != event_digest:
            lint.fail(path, f"covered_events[{index}] proof.event_digest does not match producer bytes")
        binding = {
            "context": "ak.event-proof-v1",
            "event_digest": event_digest,
            "actor_id": event.get("actor_id"),
            "verification_method": proof.get("verification_method"),
            "created_at": proof.get("created_at"),
        }
        kat = event_kats[index] if index < len(event_kats) and isinstance(event_kats[index], dict) else {}
        expected_event_values = {
            "event_id": event.get("event_id"),
            "producer_event_canonical_bytes": len(producer_bytes),
            "producer_event_digest": event_digest,
            "proof_binding_canonical_bytes": len(canonical_json(binding).encode("utf-8")),
            "proof_binding_sha256": wire_sha256(canonical_json(binding).encode("utf-8")),
        }
        if kat != expected_event_values:
            lint.fail(path, f"covered_events[{index}] known-answer metadata drifted")

    sorted_digests = sorted(event_digests)
    if event_digests[0] == event_digests[1] or len(set(event_digests)) != 2:
        lint.fail(path, "base KAT Event digests must be distinct")
    control_root = merkle_root([raw_digest(value, "Event digest") for value in sorted_digests])
    if known.get("control_event_set_root") != control_root:
        lint.fail(path, "known_answer.control_event_set_root mismatch")
    cells = [row.get("cell") for row in state if isinstance(row, dict)]
    if cells != sorted(cells) or len(set(cells)) != len(cells):
        lint.fail(path, "base KAT control_state must be canonical sorted and duplicate-free")
    state_bytes = [canonical_json(row).encode("utf-8") for row in state]
    state_root = merkle_root(state_bytes)
    if known.get("state_root") != state_root:
        lint.fail(path, "known_answer.state_root mismatch")
    if known.get("state_leaf_canonical_bytes") != [len(value) for value in state_bytes]:
        lint.fail(path, "known_answer.state_leaf_canonical_bytes mismatch")

    completeness_leaf = {
        "actor_id": events[0].get("actor_id"),
        "from_seq": 0,
        "to_seq": 1,
        "event_digests": event_digests,
    }
    completeness_bytes = canonical_json(completeness_leaf).encode("utf-8")
    completeness_root = merkle_root([completeness_bytes])
    if known.get("completeness_root") != completeness_root or known.get("completeness_leaf_canonical_bytes") != len(completeness_bytes):
        lint.fail(path, "known-answer completeness commitment mismatch")

    seal = seals[0]
    seal_body = {key: value for key, value in seal.items() if key not in {"id", "notary_signature"}}
    seal_bytes = canonical_json(seal_body).encode("utf-8")
    seal_digest = wire_sha256(seal_bytes)
    signature = seal.get("notary_signature", {}) if isinstance(seal, dict) else {}
    if seal.get("id") != "ak:seal:" + seal_digest or signature.get("payload_digest") != seal_digest:
        lint.fail(path, "Seal id/signature payload digest does not match canonical Seal body")
    if seal.get("delta") != sorted_digests:
        lint.fail(path, "Seal delta must equal the canonical covered Event digest set")
    expected_seal_fields = {
        "control_event_set_root": control_root,
        "state_root": state_root,
        "completeness_root": completeness_root,
    }
    for field, expected in expected_seal_fields.items():
        if seal.get(field) != expected:
            lint.fail(path, f"Seal {field} mismatch")
    if known.get("seal_digest") != seal_digest or known.get("seal_canonical_bytes") != len(seal_bytes):
        lint.fail(path, "known-answer Seal commitment mismatch")

    commit_context = data.get("commit_context", {})
    leaf_entries = (
        commit_context.get("current_or_pending_mls_leaf_entries", [])
        if isinstance(commit_context, dict)
        else []
    )
    if not isinstance(leaf_entries, list) or leaf_entries != sorted(
        leaf_entries, key=lambda row: canonical_json(row).encode("utf-8")
    ):
        lint.fail(path, "commit_context MLS leaf entries must be canonical sorted")
        leaf_entries = []
    mls_leaf_set_digest = wire_sha256(canonical_json(leaf_entries).encode("utf-8"))
    if (
        not isinstance(commit_context, dict)
        or commit_context.get("mls_leaf_set_digest") != mls_leaf_set_digest
        or known.get("mls_leaf_set_digest") != mls_leaf_set_digest
    ):
        lint.fail(path, "MLS leaf-set digest commitment mismatch")

    cell_entries = known.get("security_frontier_cell_entries", [])
    if not isinstance(cell_entries, list):
        lint.fail(path, "known_answer.security_frontier_cell_entries must be an array")
        cell_entries = []
    expected_cell_entries = []
    for event in events:
        payload = event.get("payload", {}) if isinstance(event, dict) else {}
        if not isinstance(payload, dict):
            continue
        expected_cell_entries.append(
            {
                "cell_family": "ak.component.member.state.v1",
                "cell_subject": payload.get("actor_id"),
                "projected_value_digest": wire_sha256(
                    canonical_json(payload.get("membership")).encode("utf-8")
                ),
            }
        )
    expected_cell_entries.sort(
        key=lambda row: (
            row["cell_family"].encode("utf-8"),
            canonical_json(row["cell_subject"]).encode("utf-8"),
            row["projected_value_digest"],
        )
    )
    if cell_entries != expected_cell_entries:
        lint.fail(path, "known-answer security frontier cell projection mismatch")
    security_frontier_input = {
        "profile_id": "ak.security_frontier.v1",
        "effective_scope": data.get("commit_context", {}).get("expected_effective_scope"),
        "cell_entries": cell_entries,
        "mls_leaf_set_digest": mls_leaf_set_digest,
    }
    security_frontier_bytes = canonical_json(security_frontier_input).encode("utf-8")
    security_frontier_digest = wire_sha256(security_frontier_bytes)
    if known.get("security_frontier_digest") != security_frontier_digest or known.get("security_frontier_input_canonical_bytes") != len(security_frontier_bytes):
        lint.fail(path, "known-answer security frontier commitment mismatch")
    binding = commit_context.get("transcript_authenticated_governance_binding", {}) if isinstance(commit_context, dict) else {}
    if not isinstance(binding, dict) or binding.get("security_frontier_digest") != security_frontier_digest:
        lint.fail(path, "governance binding must contain the rederived security_frontier_digest")

    proof_identity = source.get("proof_identity", {})
    identity_bytes = canonical_json(proof_identity).encode("utf-8")
    request_digest = wire_sha256(b"arkret-mls-governance-proof-request-v1\n" + identity_bytes)
    if known.get("proof_request_digest") != request_digest or known.get("proof_identity_canonical_bytes") != len(identity_bytes):
        lint.fail(path, "known-answer proof request commitment mismatch")

    acquisition = data.get("expected_acquisition", {})
    responses = acquisition.get("responses", []) if isinstance(acquisition, dict) else []
    requests = data.get("requests", [])
    if len(responses) != 4 or len(requests) != 4:
        lint.fail(path, "base acquisition must contain exactly four requests and responses")
        return
    chunks = [row.get("chunk") for row in responses if isinstance(row, dict)]
    expected_collections = ["seal_path", "covered_event_digests", "control_state", "frontier_events"]
    if [chunk.get("collection") for chunk in chunks if isinstance(chunk, dict)] != expected_collections:
        lint.fail(path, "base chunks must use the canonical four-collection order")
    chunk_digests: list[str] = []
    chunk_bytes_lengths: list[int] = []
    for index, chunk in enumerate(chunks):
        if not isinstance(chunk, dict):
            continue
        digest_input = {
            "chunk_index": chunk.get("chunk_index"),
            "collection": chunk.get("collection"),
            "start_index": chunk.get("start_index"),
            "items": chunk.get("items"),
        }
        digest_bytes = canonical_json(digest_input).encode("utf-8")
        chunk_digest = wire_sha256(b"arkret-mls-governance-proof-chunk-v1\n" + digest_bytes)
        chunk_digests.append(chunk_digest)
        chunk_bytes_lengths.append(len(digest_bytes))
        if chunk.get("chunk_index") != index or chunk.get("start_index") != 0 or chunk.get("chunk_digest") != chunk_digest:
            lint.fail(path, f"chunk {index} index/start/digest commitment mismatch")
        response = responses[index]
        request = requests[index] if isinstance(requests[index], dict) else {}
        if response.get("proof_request_digest") != request_digest or request.get("chunk_index") != index:
            lint.fail(path, f"request/response {index} acquisition identity mismatch")
        if index == 0 and "expected_bundle_digest" in request:
            lint.fail(path, "chunk 0 request must not carry expected_bundle_digest")

    chunks_root = merkle_root([raw_digest(value, "chunk digest") for value in chunk_digests])
    manifests = [row.get("chunk_manifest") for row in responses if isinstance(row, dict)]
    if any(manifest != manifests[0] for manifest in manifests[1:]):
        lint.fail(path, "every response must repeat the same chunk_manifest")
    manifest = manifests[0] if manifests and isinstance(manifests[0], dict) else {}
    total_item_bytes = sum(
        len(canonical_json(item).encode("utf-8"))
        for chunk in chunks if isinstance(chunk, dict)
        for item in chunk.get("items", [])
    )
    totals = {
        chunk["collection"]: len(chunk.get("items", []))
        for chunk in chunks if isinstance(chunk, dict)
    }
    if manifest.get("chunks_root") != chunks_root or manifest.get("total_item_bytes") != total_item_bytes or manifest.get("collection_totals") != totals:
        lint.fail(path, "manifest root/item-byte/collection totals mismatch")
    if known.get("chunk_digests") != chunk_digests or known.get("chunk_canonical_bytes") != chunk_bytes_lengths:
        lint.fail(path, "known-answer chunk commitments mismatch")
    if known.get("chunks_root") != chunks_root or known.get("total_item_bytes") != total_item_bytes:
        lint.fail(path, "known-answer manifest commitment mismatch")

    base_header = {key: value for key, value in responses[0].items() if key not in {"bundle_digest", "chunk"}}
    header_bytes = canonical_json(base_header).encode("utf-8")
    bundle_digest = wire_sha256(b"arkret-mls-governance-proof-bundle-v1\n" + header_bytes)
    for index, response in enumerate(responses):
        response_header = {key: value for key, value in response.items() if key not in {"bundle_digest", "chunk"}}
        if response_header != base_header or response.get("bundle_digest") != bundle_digest:
            lint.fail(path, f"response {index} Bundle header/digest mismatch")
        request = requests[index]
        if index and request.get("expected_bundle_digest") != bundle_digest:
            lint.fail(path, f"request {index} must pin the base bundle_digest")
    if known.get("bundle_digest") != bundle_digest or known.get("bundle_header_canonical_bytes") != len(header_bytes):
        lint.fail(path, "known-answer Bundle commitment mismatch")

    expected_verifier_cases = {
        "valid_complete_bundle", "self_reported_anchor_is_not_trust", "broken_seal_path",
        "forked_seal_path", "wrong_notary_authority", "missing_covered_digest",
        "extra_covered_digest", "duplicate_covered_digest", "covered_digest_order",
        "missing_state_leaf", "extra_state_leaf", "duplicate_state_leaf", "state_leaf_order",
        "missing_frontier_event", "extra_frontier_event", "duplicate_frontier_event",
        "frontier_event_order", "frontier_cross_realm_scope", "frontier_event_proof_invalid",
        "chunks_root_mismatch", "missing_chunk", "duplicate_chunk", "chunk_order",
        "binding_realm_mismatch", "binding_group_mismatch", "binding_previous_epoch_mismatch",
        "binding_next_epoch_mismatch", "binding_profile_mismatch", "binding_reducer_mismatch",
        "security_frontier_digest_mismatch", "unrelated_capability_does_not_change_frontier",
        "active_leaf_revoke_missing_from_frontier",
    }
    verifier_cases = data.get("verifier_cases", [])
    actual_verifier_cases = {
        row.get("name") for row in verifier_cases if isinstance(row, dict)
    } if isinstance(verifier_cases, list) else set()
    if actual_verifier_cases != expected_verifier_cases:
        lint.fail(path, f"verifier mutation matrix drifted: {sorted(actual_verifier_cases)}")
    for row in verifier_cases if isinstance(verifier_cases, list) else []:
        expected = row.get("expected", {}) if isinstance(row, dict) else {}
        if row.get("name") != "valid_complete_bundle" and (
            expected.get("verified_bundle_persisted") is not False
            or expected.get("epoch_advanced") is not False
            or not expected.get("failure_stage")
            or not expected.get("reason_code")
        ):
            lint.fail(path, f"reject verifier case lacks fail-closed output: {row.get('name')}")

    expected_materializer_cases = {
        "valid_materialization", "unknown_anchor", "unreachable_anchor", "missing_seal_material",
        "forked_seal_source", "unauthorized_notary_source", "missing_covered_event_source",
        "bottom_control_cell_source", "scope_visibility_denied", "logical_bundle_over_bound",
    }
    materializer_cases = data.get("materializer_cases", [])
    actual_materializer_cases = {
        row.get("name") for row in materializer_cases if isinstance(row, dict)
    } if isinstance(materializer_cases, list) else set()
    if actual_materializer_cases != expected_materializer_cases:
        lint.fail(path, f"materializer mutation matrix drifted: {sorted(actual_materializer_cases)}")
    for row in materializer_cases if isinstance(materializer_cases, list) else []:
        expected = row.get("expected", {}) if isinstance(row, dict) else {}
        if row.get("name") != "valid_materialization" and (
            expected.get("response_count") != 0
            or expected.get("partial_manifest_emitted") is not False
            or not expected.get("error_code")
        ):
            lint.fail(path, f"reject materializer case may emit partial output: {row.get('name')}")



def websocket_canonical_wss_errors(value: object) -> list[str]:
    """Return profile-level canonicalization errors for a WebSocket base URL."""
    if not isinstance(value, str):
        return ["value is not a string"]
    errors: list[str] = []
    if len(value.encode("utf-8")) > 2048:
        errors.append("UTF-8 form exceeds 2048 bytes")
    if not value.isascii():
        errors.append("URI must use an ASCII DNS A-label host")
    try:
        parsed = urllib.parse.urlsplit(value)
    except ValueError as exc:
        return [f"URI cannot be parsed: {exc}"]
    if parsed.scheme != "wss" or not value.startswith("wss://"):
        errors.append("scheme must be lowercase wss")
    if parsed.query or parsed.fragment:
        errors.append("query and fragment are forbidden")
    if parsed.username is not None or parsed.password is not None or "@" in parsed.netloc:
        errors.append("userinfo is forbidden")
    authority = parsed.netloc.rsplit("@", 1)[-1]
    raw_host = authority.rsplit(":", 1)[0] if ":" in authority and not authority.startswith("[") else authority
    host = parsed.hostname
    if not host:
        errors.append("DNS host is required")
    else:
        if raw_host != raw_host.lower():
            errors.append("DNS host must be lowercase")
        if host.endswith("."):
            errors.append("DNS host trailing dot is forbidden")
        if ":" in host:
            errors.append("IP literals are not DNS A-label hosts")
        labels = host.split(".")
        if (
            any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels)
            or len(host) > 253
        ):
            errors.append("host is not a valid lowercase DNS A-label name")
    try:
        port = parsed.port
    except ValueError as exc:
        errors.append(f"port is invalid: {exc}")
        port = None
    if ":" in authority and not authority.startswith("["):
        port_text = authority.rsplit(":", 1)[1]
        if not re.fullmatch(r"[1-9][0-9]{0,4}", port_text):
            errors.append("explicit port must be non-zero decimal without leading zeros")
        if port == 443:
            errors.append("default port 443 must be omitted")
    if port is not None and not 1 <= port <= 65535:
        errors.append("port is outside 1..65535")
    path_value = parsed.path
    if not path_value or not path_value.startswith("/"):
        errors.append("non-empty absolute path is required")
    if any(segment in {".", ".."} for segment in path_value.split("/")):
        errors.append("dot segments are forbidden")
    unreserved = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")
    index = 0
    while index < len(path_value):
        if path_value[index] != "%":
            index += 1
            continue
        escape = path_value[index : index + 3]
        if not re.fullmatch(r"%[0-9A-F]{2}", escape):
            errors.append("percent escapes must be complete and use uppercase hexadecimal")
            index += 1
            continue
        if chr(int(escape[1:], 16)) in unreserved:
            errors.append("unreserved path characters must not be percent-encoded")
        index += 3
    return errors



def check_websocket_binding_fixture(lint: Lint) -> None:
    """Execute the in-tree, tool-neutral portion of the WebSocket binding suite."""
    path = ARTIFACTS / "fixtures" / "websocket-binding-fixture.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return

    discovery_cases = data.get("discovery_cases")
    if not isinstance(discovery_cases, list):
        lint.fail(path, "discovery_cases must be an array")
        return
    discovery_by_name = {
        case.get("name"): case
        for case in discovery_cases
        if isinstance(case, dict) and isinstance(case.get("name"), str)
    }
    required_discovery_names = {
        "closed_descriptor",
        "partial_operations_rejected",
        "noncanonical_or_credentialed_url_rejected",
        "missing_subprotocol_or_limit_rejected",
    }
    if set(discovery_by_name) != required_discovery_names:
        lint.fail(path, f"discovery_cases names drift: {sorted(set(discovery_by_name))}")
    descriptor_case = discovery_by_name.get("closed_descriptor") or {}
    descriptor = descriptor_case.get("instance")
    descriptor_schema_ref = descriptor_case.get("schema_ref")
    if not isinstance(descriptor, dict) or not isinstance(descriptor_schema_ref, str):
        lint.fail(path, "closed_descriptor requires instance and schema_ref")
    else:
        check_json_instance_against_schema(
            lint,
            path,
            "closed_descriptor",
            descriptor_schema_ref,
            descriptor,
        )
        canonical_errors = websocket_canonical_wss_errors(descriptor.get("base_url"))
        if canonical_errors:
            lint.fail(path, "closed_descriptor base_url is not canonical: " + "; ".join(canonical_errors))

        partial = copy.deepcopy(descriptor)
        partial["operations"] = [
            operation
            for operation in partial.get("operations", [])
            if operation != "ak.self.signal.stream.subscribe"
        ]
        check_json_instance_against_schema(
            lint,
            path,
            "partial_operations_rejected",
            descriptor_schema_ref,
            partial,
            expect_valid=False,
        )

        missing_case = discovery_by_name.get("missing_subprotocol_or_limit_rejected") or {}
        remove_each = missing_case.get("remove_each")
        if not isinstance(remove_each, list) or set(remove_each) != {
            "subprotocol",
            "authentication",
            "max_frame_bytes",
            "max_channels",
        }:
            lint.fail(path, "missing_subprotocol_or_limit_rejected remove_each drift")
        else:
            for field in remove_each:
                mutation = copy.deepcopy(descriptor)
                mutation.pop(field, None)
                check_json_instance_against_schema(
                    lint,
                    path,
                    f"missing descriptor field {field}",
                    descriptor_schema_ref,
                    mutation,
                    expect_valid=False,
                )

    url_case = discovery_by_name.get("noncanonical_or_credentialed_url_rejected") or {}
    rejected_urls = url_case.get("base_urls")
    if not isinstance(rejected_urls, list) or not rejected_urls:
        lint.fail(path, "noncanonical URL case requires base_urls")
    else:
        for value in rejected_urls:
            if not websocket_canonical_wss_errors(value):
                lint.fail(path, f"noncanonical base_url vector is canonical: {value!r}")
            if isinstance(descriptor, dict) and isinstance(descriptor_schema_ref, str):
                mutation = copy.deepcopy(descriptor)
                mutation["base_url"] = value
                check_json_instance_against_schema(
                    lint,
                    path,
                    f"noncanonical base_url {value!r}",
                    descriptor_schema_ref,
                    mutation,
                    expect_valid=False,
                )

    kat = data.get("dpop_kat")
    if not isinstance(kat, dict):
        lint.fail(path, "dpop_kat must be an object")
        return
    decoded = kat.get("decoded")
    check_json_instance_against_schema(
        lint,
        path,
        "dpop_kat.decoded",
        "schemas/websocket-dpop-proof.schema.json",
        decoded,
    )
    if not isinstance(decoded, dict):
        return
    protected = decoded.get("protected")
    claims = decoded.get("claims")
    if not isinstance(protected, dict) or not isinstance(claims, dict):
        lint.fail(path, "dpop_kat.decoded must contain protected and claims objects")
        return
    if protected.get("jwk") != kat.get("public_jwk"):
        lint.fail(path, "dpop_kat protected jwk must equal public_jwk")
    if claims.get("htu") != kat.get("base_url"):
        lint.fail(path, "dpop_kat htu must equal the advertised base_url verbatim")
    canonical_htu_errors = websocket_canonical_wss_errors(claims.get("htu"))
    if canonical_htu_errors:
        lint.fail(path, "dpop_kat htu is not canonical: " + "; ".join(canonical_htu_errors))
    if claims.get("nonce") != kat.get("nonce"):
        lint.fail(path, "dpop_kat nonce must equal the challenge nonce")

    def fixture_timestamp(value: object, label: str) -> datetime | None:
        if not isinstance(value, str):
            lint.fail(path, f"{label} must be an RFC 3339 timestamp")
            return None
        try:
            return datetime.fromisoformat(value.removesuffix("Z") + ("+00:00" if value.endswith("Z") else ""))
        except ValueError:
            lint.fail(path, f"{label} is not an RFC 3339 timestamp")
            return None

    issued_at = fixture_timestamp(kat.get("issued_at"), "dpop_kat.issued_at")
    expires_at = fixture_timestamp(kat.get("expires_at"), "dpop_kat.expires_at")
    if issued_at is not None and expires_at is not None:
        if not 0 < (expires_at - issued_at).total_seconds() <= 5:
            lint.fail(path, "dpop_kat challenge window must be greater than zero and at most 5 seconds")
        if claims.get("iat") != int(issued_at.timestamp()):
            lint.fail(path, "dpop_kat iat must equal issued_at NumericDate")

    challenge_state = kat.get("challenge_state")
    if not isinstance(challenge_state, dict):
        lint.fail(path, "dpop_kat challenge_state must be an object")
    else:
        expected_challenge_key = [kat.get("connection_id"), kat.get("nonce")]
        if challenge_state.get("key") != expected_challenge_key:
            lint.fail(path, "dpop_kat challenge_state key must be [connection_id, nonce]")
        for field in ("canonical_origin", "canonical_base_url", "issued_at", "expires_at"):
            expected_field = {
                "canonical_origin": kat.get("origin"),
                "canonical_base_url": kat.get("base_url"),
                "issued_at": kat.get("issued_at"),
                "expires_at": kat.get("expires_at"),
            }[field]
            if challenge_state.get(field) != expected_field:
                lint.fail(path, f"dpop_kat challenge_state {field} drift")
        if challenge_state.get("consumed") is not False:
            lint.fail(path, "dpop_kat initial challenge_state must be unconsumed")

    canonical_protected = json.dumps(
        protected,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    canonical_claims = json.dumps(
        claims,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    if kat.get("protected_json_utf8") != canonical_protected:
        lint.fail(path, "dpop_kat protected_json_utf8 is not canonical JSON")
    if kat.get("claims_json_utf8") != canonical_claims:
        lint.fail(path, "dpop_kat claims_json_utf8 is not canonical JSON")

    def b64url(data_bytes: bytes) -> str:
        return base64.urlsafe_b64encode(data_bytes).rstrip(b"=").decode("ascii")

    protected_segment = b64url(canonical_protected.encode("utf-8"))
    claims_segment = b64url(canonical_claims.encode("utf-8"))
    signing_input = protected_segment + "." + claims_segment
    if kat.get("protected_base64url") != protected_segment:
        lint.fail(path, "dpop_kat protected_base64url drift")
    if kat.get("claims_base64url") != claims_segment:
        lint.fail(path, "dpop_kat claims_base64url drift")
    if kat.get("signing_input_ascii") != signing_input:
        lint.fail(path, "dpop_kat signing_input_ascii drift")
    signature = kat.get("signature_base64url")
    if not isinstance(signature, str) or len(signature) != 86:
        lint.fail(path, "dpop_kat signature must encode one 64-byte Ed25519 signature")
    elif kat.get("compact_jws") != signing_input + "." + signature:
        lint.fail(path, "dpop_kat compact_jws does not match its declared segments")
    else:
        try:
            signature_bytes = base64.urlsafe_b64decode(signature + "==")
        except (ValueError, TypeError):
            signature_bytes = b""
        if len(signature_bytes) != 64:
            lint.fail(path, "dpop_kat signature_base64url does not decode to 64 bytes")
    private_seed_hex = kat.get("private_seed_hex")
    if not isinstance(private_seed_hex, str) or not re.fullmatch(r"[0-9a-f]{64}", private_seed_hex):
        lint.fail(path, "dpop_kat private_seed_hex must encode one 32-byte public test seed")

    grant = kat.get("session_grant")
    if not isinstance(grant, str):
        lint.fail(path, "dpop_kat session_grant must be a string")
    else:
        expected_ath = b64url(hashlib.sha256(grant.encode("ascii")).digest())
        if claims.get("ath") != expected_ath:
            lint.fail(path, "dpop_kat ath does not bind the ASCII session grant")

    public_jwk = kat.get("public_jwk")
    if isinstance(public_jwk, dict):
        canonical_jwk = json.dumps(
            public_jwk,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        expected_jkt = b64url(hashlib.sha256(canonical_jwk.encode("utf-8")).digest())
        if kat.get("cnf_jkt") != expected_jkt:
            lint.fail(path, "dpop_kat cnf_jkt is not the RFC 7638 JWK thumbprint")
        expected_replay_key = [expected_jkt, claims.get("jti"), "ak.websocket-auth.v1"]
        if kat.get("expected_replay_ledger_key") != expected_replay_key:
            lint.fail(path, "dpop_kat replay ledger key drift")
    else:
        lint.fail(path, "dpop_kat public_jwk must be an object")

    dpop_negative_cases = data.get("dpop_negative_cases")
    if not isinstance(dpop_negative_cases, list):
        lint.fail(path, "dpop_negative_cases must be an array")
        dpop_negative_cases = []
    dpop_by_name = {
        case.get("name"): case
        for case in dpop_negative_cases
        if isinstance(case, dict) and isinstance(case.get("name"), str)
    }
    required_dpop_negative = {
        "http_validator_must_not_accept_application_context",
        "wrong_htu_scheme",
        "wrong_method_token",
        "wrong_ath",
        "wrong_nonce",
        "connection_id_mismatch",
        "origin_mismatch",
        "expired_challenge",
        "replayed_nonce_and_jti",
        "unknown_claim",
        "holder_thumbprint_mismatch",
    }
    if set(dpop_by_name) != required_dpop_negative:
        lint.fail(path, f"dpop_negative_cases names drift: {sorted(set(dpop_by_name))}")
    for name, case in dpop_by_name.items():
        if case.get("expected") != "rejected":
            lint.fail(path, f"dpop negative {name} must expect rejected")

    proof_schema_ref = kat.get("proof_schema_ref")
    if not isinstance(proof_schema_ref, str):
        lint.fail(path, "dpop_kat proof_schema_ref must be a string")
    else:
        if proof_schema_ref != "schemas/websocket-dpop-proof.schema.json":
            lint.fail(path, "dpop_kat proof_schema_ref drift")
        for value in (rejected_urls if isinstance(rejected_urls, list) else []):
            mutation = copy.deepcopy(decoded)
            mutation["claims"]["htu"] = value
            check_json_instance_against_schema(
                lint,
                path,
                f"dpop noncanonical htu {value!r}",
                proof_schema_ref,
                mutation,
                expect_valid=False,
            )
        for name in ("wrong_htu_scheme", "wrong_method_token", "unknown_claim"):
            case = dpop_by_name.get(name) or {}
            mutation = copy.deepcopy(decoded)
            if isinstance(case.get("replace_claim"), dict):
                mutation["claims"].update(case["replace_claim"])
            if isinstance(case.get("add_claim"), dict):
                mutation["claims"].update(case["add_claim"])
            check_json_instance_against_schema(
                lint,
                path,
                f"dpop negative {name}",
                proof_schema_ref,
                mutation,
                expect_valid=False,
            )

    if (dpop_by_name.get("http_validator_must_not_accept_application_context") or {}).get(
        "validator_context"
    ) != "http_request_dpop":
        lint.fail(path, "HTTP DPoP isolation negative must select http_request_dpop")
    wrong_ath = ((dpop_by_name.get("wrong_ath") or {}).get("replace_claim") or {}).get("ath")
    if not isinstance(wrong_ath, str) or wrong_ath == claims.get("ath"):
        lint.fail(path, "wrong_ath negative must replace ath with a distinct value")
    wrong_nonce = ((dpop_by_name.get("wrong_nonce") or {}).get("replace_claim") or {}).get("nonce")
    if not isinstance(wrong_nonce, str) or wrong_nonce == kat.get("nonce"):
        lint.fail(path, "wrong_nonce negative must replace nonce with a distinct value")
    if (dpop_by_name.get("connection_id_mismatch") or {}).get(
        "authenticate_connection_id"
    ) == kat.get("connection_id"):
        lint.fail(path, "connection_id_mismatch negative does not mismatch")
    if (dpop_by_name.get("origin_mismatch") or {}).get("socket_origin") == kat.get("origin"):
        lint.fail(path, "origin_mismatch negative does not mismatch")
    expired_verification = fixture_timestamp(
        (dpop_by_name.get("expired_challenge") or {}).get("verification_time"),
        "expired_challenge.verification_time",
    )
    if expires_at is not None and (
        expired_verification is None or expired_verification <= expires_at
    ):
        lint.fail(path, "expired_challenge verification_time must be after expires_at")
    replay_case = dpop_by_name.get("replayed_nonce_and_jti") or {}
    if replay_case.get("challenge_consumed") is not True or replay_case.get(
        "replay_ledger_key_present"
    ) is not True:
        lint.fail(path, "replay negative must exercise consumed challenge and present ledger key")
    if (dpop_by_name.get("holder_thumbprint_mismatch") or {}).get(
        "grant_cnf_jkt"
    ) == kat.get("cnf_jkt"):
        lint.fail(path, "holder_thumbprint_mismatch negative does not mismatch")

    parsed_frame_cases: dict[str, dict[str, Any]] = {}
    frame_cases = data.get("frame_schema_cases")
    if not isinstance(frame_cases, list) or not frame_cases:
        lint.fail(path, "frame_schema_cases must be a non-empty array")
    else:
        advertised_limit = ((data.get("limits") or {}).get("fixture_advertised_max_frame_bytes"))
        for index, case in enumerate(frame_cases):
            if not isinstance(case, dict):
                lint.fail(path, f"frame_schema_cases[{index}] must be an object")
                continue
            name = case.get("name")
            if not isinstance(name, str) or not name:
                lint.fail(path, f"frame_schema_cases[{index}] requires a name")
            elif name in parsed_frame_cases:
                lint.fail(path, f"duplicate frame_schema_cases name: {name}")
            else:
                parsed_frame_cases[name] = case
            wire = case.get("wire_utf8")
            schema_ref = case.get("direction_schema_ref")
            if not isinstance(wire, str) or not isinstance(schema_ref, str):
                lint.fail(path, f"frame_schema_cases[{index}] requires wire_utf8 and direction_schema_ref")
                continue
            if case.get("expect_valid") is not True:
                lint.fail(path, f"frame_schema_cases[{index}] must explicitly expect valid")
            if isinstance(advertised_limit, int) and len(wire.encode("utf-8")) > advertised_limit:
                lint.fail(path, f"frame_schema_cases[{index}] exceeds the advertised byte limit")
            try:
                duplicate_members: list[str] = []

                def collect_duplicate_members(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
                    result: dict[str, Any] = {}
                    for key, value in pairs:
                        if key in result:
                            duplicate_members.append(key)
                        result[key] = value
                    return result

                instance = json.loads(wire, object_pairs_hook=collect_duplicate_members)
            except json.JSONDecodeError as exc:
                lint.fail(path, f"frame_schema_cases[{index}] wire_utf8 is invalid JSON: {exc}")
                continue
            if duplicate_members:
                lint.fail(path, f"frame_schema_cases[{index}] contains duplicate members")
            check_json_instance_against_schema(
                lint,
                path,
                f"frame_schema_cases[{index}]",
                schema_ref,
                instance,
                expect_valid=case.get("expect_valid") is True,
            )
            check_json_instance_against_schema(
                lint,
                path,
                f"frame_schema_cases[{index}] top-level union",
                "schemas/websocket-frame.schema.json",
                instance,
            )
            opposite_schema_ref = (
                "schemas/websocket-frame.schema.json#/$defs/client_frame"
                if schema_ref.endswith("/server_frame")
                else "schemas/websocket-frame.schema.json#/$defs/server_frame"
            )
            check_json_instance_against_schema(
                lint,
                path,
                f"frame_schema_cases[{index}] opposite direction",
                opposite_schema_ref,
                instance,
                expect_valid=False,
            )

        required_frame_cases = {
            "challenge",
            "authenticate",
            "welcome",
            "open_account",
            "open_events",
            "open_signal",
            "opened",
            "opened_events",
            "opened_signal",
            "account_data",
            "events_data",
            "signal_data",
            "channel_control",
            "signal_control",
            "channel_error",
            "connection_error",
            "client_close",
            "server_closed",
            "ping",
            "pong",
            "reauth_required",
            "connection_drain",
        }
        if set(parsed_frame_cases) != required_frame_cases:
            lint.fail(path, f"frame_schema_cases names drift: {sorted(set(parsed_frame_cases))}")
        authenticate_case = parsed_frame_cases.get("authenticate") or {}
        try:
            authenticate_instance = json.loads(authenticate_case.get("wire_utf8", "null"))
        except json.JSONDecodeError:
            authenticate_instance = None
        if not isinstance(authenticate_instance, dict) or authenticate_instance.get(
            "dpop_proof"
        ) != kat.get("compact_jws"):
            lint.fail(path, "authenticate frame must carry the exact DPoP KAT compact_jws")
        welcome_case = parsed_frame_cases.get("welcome") or {}
        try:
            welcome_instance = json.loads(welcome_case.get("wire_utf8", "null"))
        except json.JSONDecodeError:
            welcome_instance = None
        if not isinstance(welcome_instance, dict) or welcome_instance.get(
            "max_frame_bytes"
        ) != advertised_limit:
            lint.fail(path, "welcome max_frame_bytes must equal the fixture advertised limit")
        error_registry = load_json(lint, ARTIFACTS / "registry" / "error-code-registry.json")
        registered_error_codes = {
            row.get("code")
            for row in (error_registry or {}).get("codes", [])
            if isinstance(row, dict) and isinstance(row.get("code"), str)
        }
        for error_case_name in ("channel_error", "connection_error"):
            try:
                error_instance = json.loads(
                    (parsed_frame_cases.get(error_case_name) or {}).get("wire_utf8", "null")
                )
            except json.JSONDecodeError:
                error_instance = None
            error_code = (
                ((error_instance or {}).get("error") or {}).get("code")
                if isinstance(error_instance, dict)
                else None
            )
            if error_code not in registered_error_codes:
                lint.fail(path, f"{error_case_name} uses an unregistered error code: {error_code!r}")

    negative_cases = data.get("wire_negative_cases")
    if not isinstance(negative_cases, list) or not negative_cases:
        lint.fail(path, "wire_negative_cases must be a non-empty array")
        return
    by_name = {
        case.get("name"): case
        for case in negative_cases
        if isinstance(case, dict) and isinstance(case.get("name"), str)
    }
    required_negative = {
        "duplicate_member",
        "unknown_field",
        "non_ascii_session_grant",
        "wrong_direction",
        "binary_message",
        "oversize_before_json_parse",
        "data_on_unopened_channel",
        "payload_does_not_match_channel_operation",
    }
    if set(by_name) != required_negative:
        lint.fail(path, f"wire_negative_cases names drift: {sorted(set(by_name))}")

    duplicate_wire = (by_name.get("duplicate_member") or {}).get("wire_utf8")
    duplicate_seen = False
    if isinstance(duplicate_wire, str):
        def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            nonlocal duplicate_seen
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    duplicate_seen = True
                result[key] = value
            return result
        json.loads(duplicate_wire, object_pairs_hook=reject_duplicates)
    if not duplicate_seen:
        lint.fail(path, "duplicate_member vector does not contain a duplicate JSON member")

    for name in ("unknown_field", "non_ascii_session_grant", "wrong_direction"):
        case = by_name.get(name) or {}
        wire = case.get("wire_utf8")
        schema_ref = case.get("direction_schema_ref") or "schemas/websocket-frame.schema.json#/$defs/client_frame"
        if isinstance(wire, str):
            check_json_instance_against_schema(
                lint,
                path,
                name,
                schema_ref,
                json.loads(wire),
                expect_valid=False,
            )

    oversize = by_name.get("oversize_before_json_parse") or {}
    generator = oversize.get("generator")
    limit = oversize.get("advertised_max_frame_bytes")
    if not isinstance(generator, dict) or not isinstance(limit, int):
        lint.fail(path, "oversize vector requires generator and advertised_max_frame_bytes")
    else:
        total = generator.get("total_message_bytes")
        prefix = generator.get("prefix_utf8")
        repeated = generator.get("repeat_utf8")
        suffix = generator.get("suffix_utf8")
        if (
            not isinstance(total, int)
            or not isinstance(prefix, str)
            or not isinstance(repeated, str)
            or len(repeated.encode("utf-8")) != 1
            or not isinstance(suffix, str)
            or total != limit + 1
            or len(prefix.encode("utf-8")) + len(suffix.encode("utf-8")) >= total
        ):
            lint.fail(path, "oversize generator must materialize exactly limit + 1 UTF-8 bytes")

    expected_wire_close_codes = {
        "duplicate_member": 1002,
        "unknown_field": 1002,
        "non_ascii_session_grant": 1002,
        "wrong_direction": 1002,
        "binary_message": 1002,
        "oversize_before_json_parse": 1009,
        "data_on_unopened_channel": 1002,
    }
    for name, expected_close_code in expected_wire_close_codes.items():
        if (by_name.get(name) or {}).get("expected_close_code") != expected_close_code:
            lint.fail(path, f"{name} close code must be {expected_close_code}")
    binary_case = by_name.get("binary_message") or {}
    if binary_case.get("opcode") != "binary" or not re.fullmatch(
        r"(?:[0-9a-f]{2})+",
        binary_case.get("wire_hex", ""),
    ):
        lint.fail(path, "binary_message must contain lowercase even-length wire_hex and binary opcode")
    state_case = by_name.get("data_on_unopened_channel") or {}
    if state_case.get("rejection_stage") != "connection_state":
        lint.fail(path, "data_on_unopened_channel must fail at connection_state")
    operation_case = by_name.get("payload_does_not_match_channel_operation") or {}
    if (
        operation_case.get("channel_operation") != "ak.self.signal.stream.subscribe"
        or operation_case.get("rejection_stage") != "channel_operation_schema"
        or operation_case.get("connection_remains_open") is not True
    ):
        lint.fail(path, "payload mismatch negative must isolate the Signal channel")

    multiplex_trace = data.get("multiplex_trace")
    if not isinstance(multiplex_trace, dict):
        lint.fail(path, "multiplex_trace must be an object")
    else:
        sequence = multiplex_trace.get("frame_case_sequence")
        required_sequence = [
            "challenge",
            "authenticate",
            "welcome",
            "open_account",
            "opened",
            "open_events",
            "opened_events",
            "open_signal",
            "opened_signal",
            "account_data",
            "events_data",
            "channel_control",
            "signal_control",
            "channel_error",
            "server_closed",
        ]
        if sequence != required_sequence:
            lint.fail(path, "multiplex_trace frame_case_sequence drift")
        elif any(name not in parsed_frame_cases for name in sequence):
            lint.fail(path, "multiplex_trace references an unknown exact frame case")
        expected_state = multiplex_trace.get("expected")
        if not isinstance(expected_state, dict):
            lint.fail(path, "multiplex_trace expected state must be an object")
        else:
            try:
                account_data = json.loads(parsed_frame_cases["account_data"]["wire_utf8"])
                events_data = json.loads(parsed_frame_cases["events_data"]["wire_utf8"])
            except (KeyError, json.JSONDecodeError):
                account_data = {}
                events_data = {}
            if expected_state.get("account_cursor") != (
                (account_data.get("payload") or {}).get("cursor")
            ):
                lint.fail(path, "multiplex_trace account cursor does not come from account_data")
            if expected_state.get("events_cursor") != (
                (events_data.get("payload") or {}).get("cursor")
            ):
                lint.fail(path, "multiplex_trace events cursor does not come from events_data")
            if (
                expected_state.get("signal_cursor") is not None
                or expected_state.get("signal_catchup") is not False
                or expected_state.get("open_channels_after_events_close")
                != ["account-1", "signal-1"]
                or expected_state.get("channel_id_reuse") != "conflict"
                or expected_state.get("physical_connection_open") is not True
            ):
                lint.fail(path, "multiplex_trace isolation state drift")

    reauth_trace = data.get("reauth_trace")
    reauth_by_name = {
        case.get("name"): case
        for case in reauth_trace or []
        if isinstance(case, dict) and isinstance(case.get("name"), str)
    }
    if set(reauth_by_name) != {"fresh_reauth_succeeds", "old_proof_reuse_fails"}:
        lint.fail(path, f"reauth_trace names drift: {sorted(set(reauth_by_name))}")
    fresh_reauth = reauth_by_name.get("fresh_reauth_succeeds") or {}
    if (
        any(fresh_reauth.get(field) is not True for field in (
            "new_nonce",
            "new_jti",
            "new_session_grant",
            "new_ath",
        ))
        or not isinstance(fresh_reauth.get("authenticate_within_ms"), int)
        or fresh_reauth.get("authenticate_within_ms", 5001) > 5000
        or fresh_reauth.get("expected") != "channels_continue"
    ):
        lint.fail(path, "fresh_reauth_succeeds must refresh every proof input within 5 seconds")
    stale_reauth = reauth_by_name.get("old_proof_reuse_fails") or {}
    if (
        stale_reauth.get("reuse_old_nonce") is not True
        or stale_reauth.get("reuse_old_jti") is not True
        or stale_reauth.get("expected_close_code") != 1008
        or stale_reauth.get("old_authorization_continues") is not False
    ):
        lint.fail(path, "old_proof_reuse_fails semantics drift")

    close_traces = data.get("drain_and_close_traces")
    close_by_name = {
        case.get("name"): case
        for case in close_traces or []
        if isinstance(case, dict) and isinstance(case.get("name"), str)
    }
    expected_close_names = {
        "channel_error_isolated",
        "graceful_service_drain",
        "protocol_error",
        "policy_error_retry_once",
        "message_too_big",
        "restart_retry_budget",
    }
    if set(close_by_name) != expected_close_names:
        lint.fail(path, f"drain_and_close_traces names drift: {sorted(set(close_by_name))}")
    required_trace_codes = {
        "graceful_service_drain": 1001,
        "protocol_error": 1002,
        "message_too_big": 1009,
    }
    for name, code in required_trace_codes.items():
        if (close_by_name.get(name) or {}).get("expected_close_code") != code:
            lint.fail(path, f"{name} close code must be {code}")
    if (close_by_name.get("restart_retry_budget") or {}).get("attempts") != 3:
        lint.fail(path, "restart_retry_budget must fall back after three pre-welcome failures")

    fallback_cases = data.get("fallback_cases")
    fallback_by_name = {
        case.get("name"): case
        for case in fallback_cases or []
        if isinstance(case, dict) and isinstance(case.get("name"), str)
    }
    if set(fallback_by_name) != {"upgrade_or_proxy_failure", "single_owner_transport_switch"}:
        lint.fail(path, f"fallback_cases names drift: {sorted(set(fallback_by_name))}")
    for name, case in fallback_by_name.items():
        if case.get("expected_transport") != "http_json":
            lint.fail(path, f"fallback case {name} must end on http_json")
    owner_switch = fallback_by_name.get("single_owner_transport_switch") or {}
    if (
        owner_switch.get("old_websocket_owner_closed") is not True
        or owner_switch.get("http_owner_started_after_old_owner_stopped") is not True
        or owner_switch.get("duplicate_consumers") is not False
        or owner_switch.get("signal_catchup_attempted") is not False
    ):
        lint.fail(path, "single_owner_transport_switch ordering drift")

    frame_schema = load_json(lint, ARTIFACTS / "schemas" / "websocket-frame.schema.json")
    definitions = set(((frame_schema or {}).get("$defs") or {}).keys())
    required_frame_definitions = {
        "challenge",
        "authenticate",
        "welcome",
        "open",
        "opened",
        "data",
        "control",
        "error",
        "close",
        "closed",
        "ping",
        "pong",
        "reauth_required",
        "server_frame",
        "client_frame",
    }
    missing = sorted(required_frame_definitions - definitions)
    if missing:
        lint.fail(path, f"websocket frame schema misses required definitions: {missing}")

