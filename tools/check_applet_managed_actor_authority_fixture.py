#!/usr/bin/env python3
"""Run the named Applet managed-actor authority conformance suite."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "spec/v1/artifacts/fixtures/applet-managed-actor-fixture.json"
ENTRYPOINT = "ak.suite.applet.managed_actor_authority.v1"

# Every case is deliberately named here. Adding a fixture row without an
# executable expectation makes the suite fail instead of silently skipping it.
EXPECTED: dict[str, tuple[str, Any]] = {
    "bot_exact_pair_and_initial_resolution": ("expect", "accepted"),
    "ghost_namespace_matches_verified_did": ("expect", "accepted"),
    "ghost_external_tuple_is_single_closed_carrier": ("expect", "accepted"),
    "ghost_external_tuple_rejects_legacy_or_extra_mirrors": ("expect", "schema_violation"),
    "ghost_provision_requires_registration_service_signature": ("expect", "http_signature_required_or_invalid"),
    "remote_principal_server_claim": ("expect", "applet_managed_actor_provision_invalid"),
    "actor_reuses_service_or_controller": ("expect", "applet_managed_actor_provision_invalid"),
    "bot_does_not_equal_registration_bot": ("expect", "applet_managed_actor_provision_invalid"),
    "ghost_core_used_for_did_namespace": ("expect", "applet_namespace_mismatch"),
    "invalid_method_history_or_witness": ("expect", "identity_method_evidence_invalid"),
    "non_webvh_method_evidence_is_not_a_managed_authority": ("expect", "schema_violation"),
    "pcr_genesis_cross_binding_mismatch": ("expect", "applet_managed_pcr_genesis_invalid"),
    "ordinary_submit_cannot_create_applet_managed_pcr": ("expect", "applet_managed_pcr_genesis_requires_closed_aggregate"),
    "peer_federation_cannot_split_managed_authority": ("expect", "applet_managed_pcr_genesis_requires_closed_aggregate"),
    "pcr_genesis_materializes_resolution_and_history_only": (
        "expect_cells",
        [
            "ak.component.identity.resolution.v1",
            "ak.component.realm.history_access.v1=since_join",
        ],
    ),
    "unit_failure_is_zero_visible": ("expect", "no_event_no_projection_no_record_no_idempotency_result"),
    "concurrent_ghost_append_uses_exact_applet_record_cas": ("expect", "one_commit_one_cas_conflict_no_event_or_record_loss"),
    "revoke_cannot_overwrite_concurrent_ghost_append": ("expect", "stale_revoke_cas_retries_and_preserves_ghost_anchor"),
    "rotation_keeps_creation_anchor": ("expect", "current_cell_changes_business_anchor_unchanged"),
    "rotation_cannot_reuse_creation_only_grant": ("expect", "capability_denied"),
    "rotation_wrong_authority_pair": ("expect", "applet_managed_actor_authority_mismatch"),
    "genesis_resolution_index_rebuild": ("expect", "exact_authority_pair_current_resolution_restored"),
    "restart_replays_genesis_and_rotation": ("expect", "projection_state_has_since_join_and_exact_latest_resolution_without_agent_status"),
    "revoked_applet_direct_self_signed_write": ("expect", "applet_revoked"),
    "managed_actor_portal_membership_is_not_delegated_bypass": ("expect", "rejected_then_accepted_then_rejected"),
    "revoked_applet_history_read": ("expect", "accepted"),
}


def run_named_suite(fixture: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    runner = fixture.get("runner")
    if runner != {"kind": "named_suite", "entrypoint": ENTRYPOINT}:
        errors.append(f"runner must select {ENTRYPOINT}")
    cases = fixture.get("cases")
    if not isinstance(cases, list):
        return errors + ["cases must be an array"]
    names = [case.get("name") for case in cases if isinstance(case, dict)]
    if len(names) != len(cases) or len(set(names)) != len(names):
        errors.append("every case must have a unique string name")
    missing = sorted(set(EXPECTED) - set(names))
    unknown = sorted(set(names) - set(EXPECTED))
    if missing:
        errors.append(f"fixture omits executable cases: {missing}")
    if unknown:
        errors.append(f"fixture contains unconsumed cases: {unknown}")
    for case in cases:
        if not isinstance(case, dict) or case.get("name") not in EXPECTED:
            continue
        field, expected = EXPECTED[case["name"]]
        if case.get(field) != expected:
            errors.append(f"{case['name']}: {field} must equal {expected!r}")
        if case["name"] == "pcr_genesis_materializes_resolution_and_history_only":
            if case.get("forbid_cells") != ["ak.component.agent.status.v1"]:
                errors.append(f"{case['name']}: agent status must remain forbidden")
        if case["name"] == "ghost_external_tuple_is_single_closed_carrier":
            if set(case.get("external_ref", {})) != {"protocol", "instance_id", "external_id"}:
                errors.append(f"{case['name']}: external_ref must be the exact closed tuple")
    return errors


def main() -> int:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    errors = run_named_suite(fixture)
    if errors:
        for error in errors:
            print(f"applet-managed-actor-authority: {error}")
        return 1
    print(f"applet-managed-actor-authority: {len(fixture['cases'])} cases consumed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
