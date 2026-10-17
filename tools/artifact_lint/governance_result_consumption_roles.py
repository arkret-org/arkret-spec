"""Execute the role policy without pretending it verifies a wire artifact."""

from .core import ARTIFACTS, Lint, load_json


def snapshot_decision(case: dict) -> str:
    """Evaluate policy facts, never a signature or a wire trust boolean."""
    if case.get("role") not in {"ordinary_client", "account_station", "independent_auditor"}:
        return "reject"
    if case.get("operation") not in {"head", "by_ref"}:
        return "reject"
    if not all(case.get(key) is True for key in (
        "known_tenure", "native_governance_verified", "context_ids_cut_and_continuity_valid",
    )):
        return "reject"
    if any(case.get(key) is not False for key in (
        "ordinary_method_history_required", "replaces_newer_current",
        "substitutes_current_head", "rewrites_original",
    )):
        return "reject"
    generation = case.get("snapshot_generation")
    current = case.get("current_generation")
    if type(generation) is not int or type(current) is not int or not 0 <= generation <= current:
        return "reject"
    if case["operation"] == "head":
        if generation != current:
            return "reject"
    elif case.get("exact_ref_matches") is not True or generation != case.get("basis_generation"):
        return "reject"
    if not all(case.get(key) is True for key in (
        "original_available", "all_original_components_disclosable", "target_stream_disclosable",
    )):
        return "unavailable"
    return "accept_current" if case["operation"] == "head" else "accept_historical"


def accepts_case(rules: dict, case: dict) -> bool:
    policy = rules.get("roles", {}).get(case.get("role"))
    if policy is None:
        return False
    return (
        case.get("source") == policy.get("input")
        and case.get("method_history_verifier") is policy.get("method_history_verifier")
        and case.get("live_did_discovery") is False
        and case.get("portable") is False
        and set(case.get("checks", [])) == set(policy.get("checks", []))
    )


def check_governance_result_consumption_roles(lint: Lint) -> None:
    path = ARTIFACTS / "registry/contract-registry.json"
    contract = load_json(lint, path)
    rules = contract["did_evidence_boundary_registry"].get("governance_result_consumption_contract", {})
    roles = rules.get("roles", {})
    client = roles.get("ordinary_client", {})
    if client.get("method_history_verifier") is not False or client.get("live_did_discovery") is not False:
        lint.fail(path, "ordinary governance result consumer must not verify method history or discover retained signers")
    required = {"full_account_and_station_binding", "original_closed_shapes_and_content_ids", "exact_realm_scope_selectors_and_coordinates", "independent_stream_continuity_and_no_rollback", "exact_snapshot_floor_and_same_cut", "producer_proof_self_consistency", "independent_mls_and_attachment_authentication"}
    if set(client.get("checks", [])) != required or client.get("portable") is not False:
        lint.fail(path, "ordinary result consumption must retain closed context, cuts and independent producer/MLS checks")
    for role in ("account_station", "independent_auditor"):
        policy = roles.get(role, {})
        if policy.get("method_history_verifier") is not True or set(policy.get("checks", [])) != {"genesis_and_continuous_handoff_chain", "historical_governance_signature_and_content_id", "nonce_audience_generation_and_freshness", "independent_stream_continuity", "selector_visibility_and_original_bytes"}:
            lint.fail(path, f"{role} must retain complete native governance verification")
    for name in ("network_from_retained_commit_signer", "boolean_only_success", "new_wire_carriers", "new_operations"):
        if rules.get(name) is not False:
            lint.fail(path, f"governance consumption cannot enable {name}")
    profile_path = ARTIFACTS / "profiles/conformance-profiles.json"
    profiles = load_json(lint, profile_path)["profile_requirements"]
    vector = "ak.vector.authority_commit_projection.result_consumption_roles.v1"
    for profile, role in (("full_client", "ordinary_client"), ("e2ee_client", "ordinary_client"), ("station", "account_station"), ("core_event_store", "account_station")):
        row = profiles[f"ak.profile.{profile}.v1"]
        if row.get("governance_result_consumption") != roles.get(role) or vector not in row.get("required_vectors", []):
            lint.fail(profile_path, f"{profile} must match canonical governance consumption responsibilities")
    fixture_path = ARTIFACTS / "fixtures/governance-result-consumption-roles-fixture.json"
    cases = load_json(lint, fixture_path)["cases"]
    required_names = {"legal_cross_station_original_self_result", "wrong_station", "boolean_only", "ordinary_forced_history", "retained_signer_discovery", "self_result_portability"}
    required_names.update("missing_" + check for check in required)
    for role in ("account_station", "independent_auditor"):
        required_names.update({role + "_complete_verification", role + "_missing_native_verifier"})
        required_names.update(role + "_missing_" + check for check in roles[role]["checks"])
    names = [case["name"] for case in cases]
    if len(names) != len(set(names)) or set(names) != required_names:
        lint.fail(fixture_path, "role policy cases must cover every mandatory check and forbidden source exactly once")
    for case in cases:
        actual = "accept" if accepts_case(rules, case) else "reject"
        if actual != case["expected"]:
            lint.fail(fixture_path, f"{case['name']}: expected {case['expected']}, got {actual}")
    check_snapshot_consumption(lint, path, rules, fixture_path)


def check_snapshot_consumption(lint: Lint, path, rules: dict, fixture_path) -> None:
    expected = {
        "current_head_generation": "fresh_current_authority_generation",
        "historical_by_ref_generation": "exact_basis_generation_in_fresh_current_chain",
        "native_governance_verification_roles": ["account_station", "independent_auditor"],
        "ordinary_client_contract": "authenticated_bound_own_station_original_with_exact_context_and_independent_producer_mls_checks",
        "historical_basis_carrier": "complete_original_signed_snapshot",
        "current_disclosure_recheck": "every_original_row_head_and_floor",
        "unrelated_scope_revocation": "whole_exact_original_unavailable",
        "missing_basis_at_issuance": "per_stream_preview_only",
        "missing_basis_at_consumption": "reject_account_frame_without_cursor_advance",
        "historical_may_replace_newer_current": False,
        "current_head_may_replace_exact_basis": False,
        "partial_snapshot_rewrite": False,
        "capacity_contract": "scalability_constraints_section_4_1_complete_inline_maximal_disclosure_admission_budget",
    }
    if rules.get("snapshot_consumption") != expected:
        lint.fail(path, "Snapshot role, tenure, exact-original, disclosure and capacity policy drift")
    cases = load_json(lint, fixture_path).get("snapshot_cases", [])
    required_names = {
        "historical_after_handoff", "current_head", "old_tenure_as_head", "future_tenure",
        "unknown_historical_tenure", "wrong_signer_or_signing_time_key",
        "auditor_historical_after_handoff", "auditor_missing_native_verification",
        "ordinary_client_forced_method_history", "exact_ref_mismatch", "basis_generation_mismatch",
        "wrong_account_session_or_mixed_cut", "unrelated_scope_revoked_target_still_readable",
        "target_scope_revoked", "original_missing_or_expired", "head_substituted_for_exact_basis",
        "unauthorized_components_trimmed", "historical_replaces_newer_current",
        "current_rows_advanced_original_still_disclosable", "new_visible_stream_does_not_change_exact_original",
    }
    names = [case.get("name") for case in cases]
    if len(names) != len(set(names)) or set(names) != required_names:
        lint.fail(fixture_path, "Snapshot policy cases must cover all role, tenure and whole-original boundaries")
    for case in cases:
        actual = snapshot_decision(case.get("input", {}))
        if actual != case.get("expected"):
            lint.fail(fixture_path, f"{case.get('name')}: expected {case.get('expected')}, got {actual}")
    schema_path = ARTIFACTS / "schemas/realm-state-snapshot.schema.json"
    description = load_json(lint, schema_path)["properties"]["governance_generation"]["description"]
    for phrase in ("Current /head", "Exact historical by-ref", "ordinary clients"):
        if phrase.lower() not in description.lower():
            lint.fail(schema_path, f"Snapshot generation description must distinguish {phrase}")
