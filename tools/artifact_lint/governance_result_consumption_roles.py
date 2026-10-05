"""Execute the role policy without pretending it verifies a wire artifact."""

from .core import ARTIFACTS, Lint, load_json


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
