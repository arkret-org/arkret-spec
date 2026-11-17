"""Generate pure signature/projection KATs, not native DB/current/role evidence."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from tools.content_history import b64, jcs
from tools.mls_native_scope_source import BASIS_DOMAIN, basis_digest, signing_bytes, installed_fence_projection
from tools.recovery_scope_cleanup import sign as sign_cleanup_authorization
from tools.regenerate_mls_governance_binding_fixture import REALM_ID, SIDECAR_ID, BASE_REF, _fixture_event_ref

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "spec/v1/artifacts/fixtures/mls-native-scope-source-fixture.json"
VECTOR = "ak.vector.mls.native_scope_source.v1"


def actor(name):
    return {"kind": "account", "account_id": {"principal_id": "ak:did_core:web:" + name + ".example", "station_id": "ak:did_core:web:holder.example"}}


def build_fixture():
    method = "did:web:holder.example#native-source"
    key = Ed25519PrivateKey.from_private_bytes(bytes([213]) * 32)
    mls = Ed25519PrivateKey.from_private_bytes(bytes([214]) * 32)
    controller = actor("controller")
    agents = [actor("agent-a"), actor("agent-b")]
    endpoint = {"actor_id": controller, "endpoint": {"kind": "device", "device_id": "ak:device:019a0000-0000-7000-8000-000000000001"}, "authorization_event_ref": _fixture_event_ref("native-source/auth0"), "signature_key_base64url": b64(mls.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))}
    scope = {"kind": "sidecar", "realm_id": REALM_ID, "sidecar_id": SIDECAR_ID}
    member = {"sidecar_id": SIDECAR_ID, "controller_account_id": controller["account_id"], "sidecar_create_event_ref": SIDECAR_ID.replace("ak:sidecar:", "ak:event:", 1), "controller_join_event_ref": _fixture_event_ref("native-source/controller-join"), "candidate_joins": [{"agent_actor_id": a, "join_event_ref": _fixture_event_ref("native-source/join-" + str(i))} for i, a in enumerate(agents)]}
    gbasis = {"domain": BASIS_DOMAIN, "realm_id": REALM_ID, "effective_scope": scope, "governance_authority_ref": BASE_REF, "genesis_event_ref": BASE_REF, "sidecar_membership_basis": member, "endpoint_fences": []}
    source = {"authorization_event_ref": endpoint["authorization_event_ref"]}
    query = {"source_id": "ak:did_core:web:governor.example", "destination_id": "ak:did_core:web:holder.example", "query_nonce_base64url": b64(bytes([215]) * 32), "realm_id": REALM_ID, "effective_scope": scope, "governance_authority_ref": BASE_REF, "genesis_event_ref": BASE_REF, "purpose": "sidecar_view", "original_request_digest": "sha256:" + hashlib.sha256(b"existing-complete-native-binding-fixture-only").hexdigest(), "g_basis_digest": basis_digest(gbasis), "sidecar_membership_basis": member, "endpoint_sources": [source]}
    qualification = {"desired_qualifications": [True, False], "endpoint_qualifications": [{"state": "qualified"}], "issued_at": "2026-11-17T00:00:00.000Z", "expires_at": "2026-11-17T00:00:20.000Z"}
    transcript = signing_bytes(query, qualification)
    response = {"qualification": qualification, "signature": {"kid": method, "signature_algorithm": "Ed25519", "signature": b64(key.sign(transcript))}}
    original_authorization = {"replacement": endpoint, "inventory_digest": "sha256:" + "12" * 32, "inventory_entry": {"effective_scope": scope, "genesis_event_ref": BASE_REF, "base_group_state_ref": BASE_REF, "epoch": "0", "old_leaves": []}, "nonce_base64url": b64(bytes([216]) * 32)}
    original_authorization.update(destination_service_id=query["source_id"], predecessor_authorization_event_refs=[], delivery_challenge_base64url=b64(bytes([217]) * 32), verification_method=method, attested_at=qualification["issued_at"], expires_at=qualification["expires_at"])
    original_authorization = sign_cleanup_authorization(original_authorization, key, source=True)
    first_source = {"attestation": original_authorization}
    installed = installed_fence_projection(first_source, [])
    born = copy.deepcopy(gbasis); born["endpoint_fences"] = [installed]
    rejoin = copy.deepcopy(gbasis); rejoin["sidecar_membership_basis"]["controller_join_event_ref"] = _fixture_event_ref("native-source/controller-rejoin")
    negatives = [
        "changed_nonce", "changed_original_request_digest", "changed_authority_ref", "wrong_owning_service_key", "response_common_field_mirror", "response_wrong_order_or_length", "same_key_different_authorization", "raw_negative_candidate_omitted", "new_installed_empty_fence", "wrong_scope", "current_source_expired", "source_past_original_peer_deadline", "noncanonical_challenge", "non_sidecar_desired_projection", "extra_unrequested_endpoint", "qualified_claim_without_keypackage_ref", "reused_old_source_for_new_batch", "numeric_0_or_1_not_boolean", "desired_qualification_length", "desired_qualification_order_signature_binding", "sidecar_create_event_retype_mismatch_even_resigned"]
    semantic = [
        {"name": "first_creator_has_no_claim_or_retained_tree", "requirement": "Use original genuine producer/native source and exact signed creator binding; native key may differ from MLS key.", "evidence_level": "native_implementation_required"},
        {"name": "H_pause_after_exact_inflight_source", "requirement": "Bounded exact in-flight semantics only; every new original/query/batch takes fresh H evaluation.", "evidence_level": "native_implementation_required"},
        {"name": "G_local_durable_denial_dominates_source", "requirement": "AccountStatus, current membership/tenure and permanent fence are checked at the final original cut.", "evidence_level": "native_implementation_required"},
        {"name": "late_attestation_not_a_current_fence", "requirement": "Keep real post-winning-Commit/Welcome/durable historical source and never infer readiness from prequalification.", "evidence_level": "native_implementation_required"}]
    zero = copy.deepcopy(response); zero["qualification"]["desired_qualifications"] = [True, 0]
    one = copy.deepcopy(response); one["qualification"]["desired_qualifications"] = [True, 1]
    return {"runner": {"kind": "named_suite", "entrypoint": "ak.suite.mls.native_scope_source.v1"}, "generated_by": "python -m tools.regenerate_mls_native_scope_source_fixture", "covers_vectors": [VECTOR], "machine_contracts": ["schemas/mls-native-scope-source.schema.json", "registry/contract-registry.json"], "description": "Real Ed25519 over exact finite request/qualification plus canonical membership/fence projection primitives. Fixture coordinates and qualified-key input are not native role, accepted Event/PCR, current H truth, complete G database or actual RFC proof. Separate native implementation obligations remain explicit.", "qualification": {"evidence": "primitive_bytes_only", "native_current_role_or_database_acceptance": "not_claimed"}, "case": {"qualified_endpoint_context_not_H_leaf_attestation": endpoint, "request": query, "response": response, "signing_bytes_hex": transcript.hex(), "owning_method": {"station_id": query["destination_id"], "verification_method": method, "public_key_base64url": b64(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))}, "wrong_method_public_key_base64url": b64(mls.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)), "evaluated_at": "2026-11-17T00:00:01.000Z", "peer_deadline": "2026-11-17T00:00:30.000Z"}, "basis_cases": {"before": gbasis, "before_digest": basis_digest(gbasis), "installed_first_source_I_projection": installed, "first_source_intent_only_not_native_proof": first_source, "installed_empty_fence": born, "installed_empty_fence_digest": basis_digest(born), "controller_rejoin": rejoin, "controller_rejoin_digest": basis_digest(rejoin), "fp_reservation_not_a_fence_digest": basis_digest(gbasis)}, "required_rejections": negatives, "native_obligations": semantic, "security_evidence": [{"clause_id": "AK-NC-133", "vector_id": VECTOR, "decision_points": [{"id": "exact_query_and_qualification_signature", "requirement": "Real H Ed25519 binds the single exact typed query plus qualification, original native business digest, scope, challenge, authority tenure, endpoint instance, paired results and bounded peer/source window. Complete native roles, keeper state and RFC remain external.", "evidence": ["/case", "/basis_cases", "/required_rejections"]}]}], "schema_validation_cases": [{"name": "finite_sidecar_source_query", "schema_ref": "schemas/mls-native-scope-source.schema.json#/$defs/native_scope_source_request_body", "expect_valid": True, "instance": query}, {"name": "no_response_echoes", "schema_ref": "schemas/mls-native-scope-source.schema.json#/$defs/native_scope_source_response_body", "expect_valid": True, "instance": response}, {"name": "numeric_zero_is_not_boolean_qualification", "schema_ref": "schemas/mls-native-scope-source.schema.json#/$defs/native_scope_source_response_body", "expect_valid": False, "first_expected_error": "contains:not of type 'boolean'", "instance": zero}, {"name": "numeric_one_is_not_boolean_qualification", "schema_ref": "schemas/mls-native-scope-source.schema.json#/$defs/native_scope_source_response_body", "expect_valid": False, "first_expected_error": "contains:not of type 'boolean'", "instance": one}]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = json.dumps(build_fixture(), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if OUTPUT.read_text(encoding="utf-8") != expected: raise SystemExit("native scope source fixture drift")
    else:
        OUTPUT.write_text(expected, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
