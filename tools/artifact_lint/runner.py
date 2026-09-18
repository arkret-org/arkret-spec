"""Command-line orchestration for the artifact lint phases."""

from __future__ import annotations

from .forbidden_wire import check_forbidden_wire_contexts

from .core import (
    Any,
    Lint,
    argparse,
    load_json_schema_for_uri,
    parse_json_file,
    parse_yaml_file,
    read_text,
    schema_format_checker,
    sys,
    time,
)

from .foundation import (
    check_event_id_suite_registry,
    check_event_kind_verb_form_registration,
    check_history_response_naming,
    check_id_form_wire_schema_alignment,
    check_pcr_exposure_registry,
    check_proof_context_registry,
    check_protocol_layer_registry,
    check_registries,
    check_registry_manifest,
    check_text_files_utf8_no_nul,
    check_timestamp_profile_single_source,
    check_typed_id_carrier_sweep_closure,
    check_typed_id_fixture_value_closure,
    check_typed_id_payload_form_closure,
    check_typed_id_prefix_registry_closure,
)

from .schemas import (
    check_account_identity_carrier_closure,
    check_agent_runtime_scope_registry,
    check_canonical_wire_source_closure,
    check_circle_lifecycle_basis_vector,
    check_circle_membership_enum_single_source,
    check_classification_context_paths,
    check_blob_identifier_form_closure,
    check_closed_object_required_declared,
    check_device_reanchor_payload_receipt_binding,
    check_derived_signature_projection_closure,
    check_did_and_device_constraints,
    check_did_boundary_allowlist,
    check_did_method_adapter_evidence_kind_routing,
    check_event_reference_inventory,
    check_content_addressed_ref_mirror_removals,
    check_content_addressed_ref_sibling_digests,
    check_event_schema_coverage,
    check_fsm_state_reachability,
    check_foundational_schema_dependency_direction,
    check_keypackage_claim_unsigned_projection,
    check_operation_clause_registry,
    check_preimage_event_identity_commitments,
    check_profile_requirements,
    check_read_scope_schema_closure,
    check_reducer_payload_closure,
    check_schema_refs,
    check_security_transaction_schema_closure,
    check_sdk_conformance_contract,
    check_signed_object_closure,
    check_stable_identity_fields_use_core_id,
    check_stated_digest_suite_sources,
    check_trust_domain_constraints,
    check_vector_group_requirements,
    check_wire_schema_no_bare_scope,
)

from .bindings import (
    check_binding_completeness_index,
    check_binding_variant_non_http,
    check_capability_action_event_mapping,
    check_delegated_write_admission_envelope_lock,
    check_event_admission_coverage,
    check_openapi_auth_semantics,
    check_openapi_core_selector_constraints,
    check_openapi_dedicated_operation_schemas,
    check_openapi_error_enum_alignment,
    check_openapi_schema_component_order,
    check_operation_binding_metadata,
    check_operation_dto_closure,
    check_operation_durable_effect_contract,
    check_operation_field_table_schema_refs,
    check_operation_surfaces,
    check_request_material_supply_closure,
    check_service_describe_alignment,
)

from .fixtures import (
    check_account_data_key_registry,
    check_agent_requested_scope_commitment_digest,
    check_applet_revoke_saga_contract,
    check_canonical_digest_fixtures,
    check_content_bound_event_id_fixture,
    check_crypto_signature_fixture,
    check_cryptographic_suite_kat_bindings,
    check_declared_canonical_json_strings,
    check_declared_schema_fixture_instances,
    check_fixture_content_addressed_sibling_digests,
    check_fixture_schema_instance_bindings,
    check_direct_conversation_digest_vectors,
    check_encrypted_envelope_digest_vector,
    check_erasure_verification_contract,
    check_event_batch_receipt_normalization_vector,
    check_fixture_runner_contract,
    check_fixtures,
    check_keypackage_write_transcript_fixture,
    check_mls_creator_bootstrap_transaction,
    check_normative_clause_registry,
    check_one_of_branch_discriminability,
    check_operation_selector_fixture,
    check_producer_allocated_identity_vectors,
    check_schema_fixture_canonical_public_material,
    check_stated_preimage_matches_stated_digest,
    check_string_profile_format_vectors,
    check_view_write_contract_fixture,
    check_vector_reference_closure,
    check_vector_registry,
    check_websocket_binding_fixture,
)

from .naming_contracts import (
    check_collection_field_contracts,
    check_duration_field_units,
    check_identifier_role_suffix_contracts,
    check_identifier_value_categories,
    check_naming_rule_coverage_matrix,
    check_slug_field_closure,
    check_typed_current_result_naming,
)

from .prose import (
    check_account_notification_prose_schema_alignment,
    check_canonical_digest_alias,
    check_common_object_field_matrix,
    check_content_composite_uses_parts,
    check_cross_doc_anchors,
    check_cross_source_drift,
    check_directory_field_drift,
    check_envelope_subject_source_whitelist,
    check_event_log_operations_carry_a_signed_event,
    check_event_proof_digest_shape,
    check_join_policy_gate_id_uniqueness,
    check_keypackage_claim_proof_shape,
    check_legacy_announce_id_form,
    check_markdown_examples,
    check_markdown_links,
    check_naming_predicates,
    check_non_normative_frontmatter,
    check_normative_prose_role_names,
    check_station_role_clean_break,
    check_profile_dependency_graph,
    check_release_readiness_counts,
    check_text_reference_targets,
    check_typed_id_prose_consistency,
)

from .safety import (
    check_action_reference_closure,
    check_alg_registry,
    check_applet_install_epoch_evidence_carrier,
    check_device_messages_cursor_binding,
    check_error_code_closure,
    check_error_code_registry_uniqueness,
    check_exporter_label_registry,
    check_field_order,
    check_fixture_reject_reason_closure,
    check_mls_pq_suite_registration,
    check_model_required_field_table_coverage,
    check_openapi_no_floating_number,
    check_operations_error_mapping_closure,
    check_repeated_enum_drift,
    check_service_kind_registry,
)

from .redactable_fields import (
    check_redactable_field_registry,
)

from .account_status_replica import (
    check_account_status_replica_decision_table,
)

from .franking_transcript import check_franking_proof_transcript

from .recovery_transcripts import (
    check_recovery_transcript_closure,
    check_registered_context_schema_duplicates,
)

from .schema_roots import check_schema_root_reachability

from .constructability import check_schema_constructability
from .derived_wire_removals import check_derived_wire_field_removals
from .expanded_projections import check_expanded_projection_registry
from .prose_field_tables import check_prose_field_tables
from .ref_overlay_closure import check_schema_ref_overlay_closure

from .psi_class_b import check_psi_class_b_artifact_closure
from .reason_code_producers import check_reason_code_producer_paths
from .proof_context_schemas import (
    check_asserted_result_families_are_registered,
    check_author_writable_state_axis_contract,
    check_proof_context_object_family_schemas,
    check_proof_context_carrier_family_anchors,
    check_domain_separation_binding_fields_are_carriable,
    check_every_result_family_has_a_writer,
    check_partial_update_base_producers,
    check_pre_state_requirement_closure,
    check_registered_families_are_listed_in_prose,
    check_result_family_write_agreement,
    check_result_value_member_closure,
    check_result_write_contracts,
    check_result_write_target_uniqueness,
    check_result_write_coverage_note,
)



def run_lint_phase(
    index: int,
    total: int,
    label: str,
    checks: list[tuple[str, Any]],
    *,
    quiet: bool,
    timing: bool,
) -> dict[str, Any]:
    if not quiet:
        print(f"[lint {index}/{total}] {label} ...", file=sys.stderr, flush=True)
    phase_started = time.perf_counter()
    results: dict[str, Any] = {}
    for name, check in checks:
        started = time.perf_counter()
        results[name] = check()
        if timing:
            print(
                f"  {name}: {time.perf_counter() - started:.3f}s",
                file=sys.stderr,
                flush=True,
            )
    if not quiet:
        print(
            f"[lint {index}/{total}] {label} done "
            f"({time.perf_counter() - phase_started:.2f}s)",
            file=sys.stderr,
            flush=True,
        )
    return results



def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quiet", action="store_true", help="suppress phase progress")
    parser.add_argument(
        "--timing",
        action="store_true",
        help="print individual check timings in addition to phase progress",
    )
    args = parser.parse_args(argv)
    lint = Lint()
    started = time.perf_counter()

    for cached in (
        read_text,
        parse_json_file,
        parse_yaml_file,
        load_json_schema_for_uri,
        schema_format_checker,
    ):
        cached.cache_clear()

    phase_count = 6
    foundation = run_lint_phase(
        1,
        phase_count,
        "基础文件与规范注册表",
        [
            ("text_encoding", lambda: check_text_files_utf8_no_nul(lint)),
            ("history_response_naming", lambda: check_history_response_naming(lint)),
            ("registry_manifest", lambda: check_registry_manifest(lint)),
            ("timestamp_profile", lambda: check_timestamp_profile_single_source(lint)),
            ("proof_contexts", lambda: check_proof_context_registry(lint)),
            (
                "proof_context_object_family_schemas",
                lambda: check_proof_context_object_family_schemas(lint),
            ),
            (
                "proof_context_carrier_family_anchors",
                lambda: check_proof_context_carrier_family_anchors(lint),
            ),
            (
                "domain_separation_binding_fields_are_carriable",
                lambda: check_domain_separation_binding_fields_are_carriable(lint),
            ),
            ("result_write_contracts", lambda: check_result_write_contracts(lint)),
            ("result_value_member_closure", lambda: check_result_value_member_closure(lint)),
            (
                "author_writable_state_axis_contract",
                lambda: check_author_writable_state_axis_contract(lint),
            ),
            (
                "result_write_target_uniqueness",
                lambda: check_result_write_target_uniqueness(lint),
            ),
            (
                "result_write_coverage_note",
                lambda: check_result_write_coverage_note(lint),
            ),
            (
                "every_result_family_has_a_writer",
                lambda: check_every_result_family_has_a_writer(lint),
            ),
            (
                "result_family_write_agreement",
                lambda: check_result_family_write_agreement(lint),
            ),
            (
                "partial_update_base_producers",
                lambda: check_partial_update_base_producers(lint),
            ),
            (
                "pre_state_requirement_closure",
                lambda: check_pre_state_requirement_closure(lint),
            ),
            (
                "registered_families_are_listed_in_prose",
                lambda: check_registered_families_are_listed_in_prose(lint),
            ),
            (
                "asserted_result_families_are_registered",
                lambda: check_asserted_result_families_are_registered(lint),
            ),
            ("forbidden_wire_contexts", lambda: check_forbidden_wire_contexts(lint)),
            ("pcr_exposures", lambda: check_pcr_exposure_registry(lint)),
            ("event_id_suite_registry", lambda: check_event_id_suite_registry(lint)),
            ("registries", lambda: check_registries(lint)),
            ("id_form_wire_schema", lambda: check_id_form_wire_schema_alignment(lint)),
            (
                "typed_id_prefix_closure",
                lambda: check_typed_id_prefix_registry_closure(lint),
            ),
            (
                "typed_id_payload_form_closure",
                lambda: check_typed_id_payload_form_closure(lint),
            ),
            (
                "typed_id_carrier_sweep",
                lambda: check_typed_id_carrier_sweep_closure(lint),
            ),
            (
                "typed_id_fixture_value_closure",
                lambda: check_typed_id_fixture_value_closure(lint),
            ),
            (
                "event_kind_verb_form",
                lambda: check_event_kind_verb_form_registration(lint),
            ),
            ("protocol_layers", lambda: check_protocol_layer_registry(lint)),
        ],
        quiet=args.quiet,
        timing=args.timing,
    )
    known = foundation["registries"]

    run_lint_phase(
        2,
        phase_count,
        "Schema、profile 与授权闭包",
        [
            ("schema_refs", lambda: check_schema_refs(lint, known)),
            ("schema_root_reachability", lambda: check_schema_root_reachability(lint)),
            (
                "canonical_wire_source_closure",
                lambda: check_canonical_wire_source_closure(lint),
            ),
            (
                "preimage_event_identity_commitments",
                lambda: check_preimage_event_identity_commitments(lint),
            ),
            (
                "content_addressed_ref_mirror_removals",
                lambda: check_content_addressed_ref_mirror_removals(lint),
            ),
            (
                "content_addressed_ref_sibling_digests",
                lambda: check_content_addressed_ref_sibling_digests(lint),
            ),
            (
                "circle_lifecycle_basis_vector",
                lambda: check_circle_lifecycle_basis_vector(lint),
            ),
            (
                "vector_group_requirements",
                lambda: check_vector_group_requirements(lint, known),
            ),
            (
                "foundational_schema_dependencies",
                lambda: check_foundational_schema_dependency_direction(lint),
            ),
            ("schema_constructability", lambda: check_schema_constructability(lint)),
            ("schema_ref_overlay_closure", lambda: check_schema_ref_overlay_closure(lint)),
            ("expanded_projection_registry", lambda: check_expanded_projection_registry(lint)),
            ("derived_wire_field_removals", lambda: check_derived_wire_field_removals(lint)),
            (
                "registered_context_schema_duplicates",
                lambda: check_registered_context_schema_duplicates(lint),
            ),
            (
                "security_transaction_schema_closure",
                lambda: check_security_transaction_schema_closure(lint),
            ),
            (
                "stated_digest_suite_sources",
                lambda: check_stated_digest_suite_sources(lint),
            ),
            ("profile_requirements", lambda: check_profile_requirements(lint, known)),
            ("agent_runtime_scope_registry", lambda: check_agent_runtime_scope_registry(lint, known)),
            ("sdk_conformance", lambda: check_sdk_conformance_contract(lint)),
            ("operation_clauses", lambda: check_operation_clause_registry(lint)),
            ("event_schema_coverage", lambda: check_event_schema_coverage(lint, known)),
            ("event_reference_inventory", lambda: check_event_reference_inventory(lint)),
            (
                "keypackage_claim_unsigned_projection",
                lambda: check_keypackage_claim_unsigned_projection(lint),
            ),
            ("blob_identifier_form_closure", lambda: check_blob_identifier_form_closure(lint)),
            ("wire_scope", lambda: check_wire_schema_no_bare_scope(lint)),
            ("closed_object_required", lambda: check_closed_object_required_declared(lint)),
            ("fsm_reachability", lambda: check_fsm_state_reachability(lint)),
            ("read_scope", lambda: check_read_scope_schema_closure(lint)),
            ("signed_objects", lambda: check_signed_object_closure(lint)),
            (
                "derived_signature_projections",
                lambda: check_derived_signature_projection_closure(lint),
            ),
            ("reducer_payloads", lambda: check_reducer_payload_closure(lint)),
            ("account_identity_carriers", lambda: check_account_identity_carrier_closure(lint)),
            (
                "device_reanchor_binding",
                lambda: check_device_reanchor_payload_receipt_binding(lint),
            ),
            ("circle_membership", lambda: check_circle_membership_enum_single_source(lint)),
            (
                "classification_contexts",
                lambda: check_classification_context_paths(lint),
            ),
            ("did_device", lambda: check_did_and_device_constraints(lint)),
            ("trust_domain_constraints", lambda: check_trust_domain_constraints(lint)),
            ("did_boundary_allowlist", lambda: check_did_boundary_allowlist(lint)),
            (
                "did_method_adapter_evidence_kind_routing",
                lambda: check_did_method_adapter_evidence_kind_routing(lint),
            ),
            (
                "stable_identity_ids",
                lambda: check_stable_identity_fields_use_core_id(lint),
            ),
        ],
        quiet=args.quiet,
        timing=args.timing,
    )

    run_lint_phase(
        3,
        phase_count,
        "OpenAPI 与 operation 绑定",
        [
            ("openapi_component_order", lambda: check_openapi_schema_component_order(lint)),
            ("operation_surfaces", lambda: check_operation_surfaces(lint, known)),
            (
                "operation_durable_effect",
                lambda: check_operation_durable_effect_contract(lint),
            ),
            ("service_describe", lambda: check_service_describe_alignment(lint)),
            ("dedicated_schemas", lambda: check_openapi_dedicated_operation_schemas(lint)),
            ("openapi_auth", lambda: check_openapi_auth_semantics(lint)),
            (
                "openapi_core_selector_constraints",
                lambda: check_openapi_core_selector_constraints(lint),
            ),
            (
                "delegated_write_admission_envelope_lock",
                lambda: check_delegated_write_admission_envelope_lock(lint),
            ),
            ("openapi_errors", lambda: check_openapi_error_enum_alignment(lint)),
            ("binding_metadata", lambda: check_operation_binding_metadata(lint)),
            ("binding_index", lambda: check_binding_completeness_index(lint)),
            ("field_table_refs", lambda: check_operation_field_table_schema_refs(lint)),
            ("non_http_variants", lambda: check_binding_variant_non_http(lint)),
            ("capability_mapping", lambda: check_capability_action_event_mapping(lint)),
            ("event_admission", lambda: check_event_admission_coverage(lint)),
            ("dto_closure", lambda: check_operation_dto_closure(lint)),
            (
                "request_material_supply",
                lambda: check_request_material_supply_closure(lint),
            ),
        ],
        quiet=args.quiet,
        timing=args.timing,
    )

    run_lint_phase(
        4,
        phase_count,
        "Fixtures、样例与向量",
        [
            ("account_data_keys", lambda: check_account_data_key_registry(lint, known)),
            ("crypto_suite_kats", lambda: check_cryptographic_suite_kat_bindings(lint)),
            ("fixtures", lambda: check_fixtures(lint, known)),
            ("vector_registry", lambda: check_vector_registry(lint)),
            (
                "vector_reference_closure",
                lambda: check_vector_reference_closure(lint),
            ),
            (
                "normative_clause_registry",
                lambda: check_normative_clause_registry(lint),
            ),
            (
                "canonical_digest_fixtures",
                lambda: check_canonical_digest_fixtures(lint),
            ),
            (
                "content_bound_event_id_fixture",
                lambda: check_content_bound_event_id_fixture(lint),
            ),
            ("crypto_signature_fixture", lambda: check_crypto_signature_fixture(lint)),
            (
                "declared_canonical_json_strings",
                lambda: check_declared_canonical_json_strings(lint),
            ),
            (
                "direct_conversation_digest_vectors",
                lambda: check_direct_conversation_digest_vectors(lint),
            ),
            (
                "event_batch_receipt_normalization_vector",
                lambda: check_event_batch_receipt_normalization_vector(lint),
            ),
            (
                "mls_creator_bootstrap_transaction",
                lambda: check_mls_creator_bootstrap_transaction(lint),
            ),
            (
                "stated_preimage_matches_stated_digest",
                lambda: check_stated_preimage_matches_stated_digest(lint),
            ),
            (
                "string_profile_format_vectors",
                lambda: check_string_profile_format_vectors(lint),
            ),
            (
                "view_write_contract_fixture",
                lambda: check_view_write_contract_fixture(lint),
            ),
            ("websocket_binding_fixture", lambda: check_websocket_binding_fixture(lint)),
            (
                "recovery_transcript_closure",
                lambda: check_recovery_transcript_closure(lint),
            ),
            (
                "keypackage_write_transcripts",
                lambda: check_keypackage_write_transcript_fixture(lint),
            ),
            (
                "franking_proof_transcript",
                lambda: check_franking_proof_transcript(lint),
            ),
            (
                "declared_schema_fixture_instances",
                lambda: check_declared_schema_fixture_instances(lint),
            ),
            (
                "fixture_content_addressed_sibling_digests",
                lambda: check_fixture_content_addressed_sibling_digests(lint),
            ),
            (
                "fixture_schema_instance_bindings",
                lambda: check_fixture_schema_instance_bindings(lint),
            ),
            (
                "operation_selector_fixture",
                lambda: check_operation_selector_fixture(lint),
            ),
            ("erasure_verification", lambda: check_erasure_verification_contract(lint)),
            ("producer_id_vectors", lambda: check_producer_allocated_identity_vectors(lint)),
            ("applet_revoke_saga", lambda: check_applet_revoke_saga_contract(lint)),
            (
                "agent_requested_scope_commitment",
                lambda: check_agent_requested_scope_commitment_digest(lint),
            ),
            ("fixture_runner", lambda: check_fixture_runner_contract(lint)),
            (
                "canonical_public_material",
                lambda: check_schema_fixture_canonical_public_material(lint),
            ),
            ("encrypted_digest", lambda: check_encrypted_envelope_digest_vector(lint)),
            ("one_of_branches", lambda: check_one_of_branch_discriminability(lint)),
        ],
        quiet=args.quiet,
        timing=args.timing,
    )

    run_lint_phase(
        5,
        phase_count,
        "正文引用与结构化命名",
        [
            ("text_targets", lambda: check_text_reference_targets(lint)),
            ("cross_source", lambda: check_cross_source_drift(lint, known)),
            ("markdown_links", lambda: check_markdown_links(lint)),
            ("markdown_examples", lambda: check_markdown_examples(lint, known)),
            ("naming_predicates", lambda: check_naming_predicates(lint)),
            ("naming_rule_coverage", lambda: check_naming_rule_coverage_matrix(lint)),
            ("identifier_categories", lambda: check_identifier_value_categories(lint)),
            ("identifier_role_suffixes", lambda: check_identifier_role_suffix_contracts(lint)),
            ("collection_field_contracts", lambda: check_collection_field_contracts(lint)),
            ("duration_field_units", lambda: check_duration_field_units(lint)),
            ("slug_field_closure", lambda: check_slug_field_closure(lint)),
            ("typed_current_result_naming", lambda: check_typed_current_result_naming(lint)),
            ("profile_graph", lambda: check_profile_dependency_graph(lint)),
            ("field_matrix", lambda: check_common_object_field_matrix(lint)),
            ("prose_field_tables", lambda: check_prose_field_tables(lint)),
            ("keypackage_claim_proof_shape", lambda: check_keypackage_claim_proof_shape(lint)),
            ("event_proof_digest", lambda: check_event_proof_digest_shape(lint)),
            ("digest_alias", lambda: check_canonical_digest_alias(lint)),
            ("announce_ids", lambda: check_legacy_announce_id_form(lint)),
            ("directory_fields", lambda: check_directory_field_drift(lint)),
            (
                "envelope_subject_source_whitelist",
                lambda: check_envelope_subject_source_whitelist(lint),
            ),
            ("typed_id_prose", lambda: check_typed_id_prose_consistency(lint)),
            (
                "event_log_signed_request",
                lambda: check_event_log_operations_carry_a_signed_event(lint),
            ),
            ("join_policy_ids", lambda: check_join_policy_gate_id_uniqueness(lint)),
            ("composite_parts", lambda: check_content_composite_uses_parts(lint)),
            ("release_counts", lambda: check_release_readiness_counts(lint, known)),
            ("cross_doc_anchors", lambda: check_cross_doc_anchors(lint)),
            ("non_normative_frontmatter", lambda: check_non_normative_frontmatter(lint)),
            ("normative_roles", lambda: check_normative_prose_role_names(lint)),
            ("station_role_clean_break", lambda: check_station_role_clean_break(lint)),
            ("account_notification", lambda: check_account_notification_prose_schema_alignment(lint)),
        ],
        quiet=args.quiet,
        timing=args.timing,
    )

    run_lint_phase(
        6,
        phase_count,
        "错误、字段顺序与安全边界",
        [
            ("error_uniqueness", lambda: check_error_code_registry_uniqueness(lint)),
            ("error_mapping", lambda: check_operations_error_mapping_closure(lint)),
            ("psi_class_b", lambda: check_psi_class_b_artifact_closure(lint)),
            ("fixture_reasons", lambda: check_fixture_reject_reason_closure(lint)),
            ("error_closure", lambda: check_error_code_closure(lint)),
            (
                "reason_code_producer_paths",
                lambda: check_reason_code_producer_paths(lint),
            ),
            ("redactable_fields", lambda: check_redactable_field_registry(lint)),
            (
                "account_status_replica_decisions",
                lambda: check_account_status_replica_decision_table(lint),
            ),
            ("openapi_numbers", lambda: check_openapi_no_floating_number(lint)),
            ("field_order", lambda: check_field_order(lint)),
            ("required_field_tables", lambda: check_model_required_field_table_coverage(lint)),
            ("exporter_labels", lambda: check_exporter_label_registry(lint)),
            ("repeated_enums", lambda: check_repeated_enum_drift(lint)),
            ("algs", lambda: check_alg_registry(lint)),
            (
                "applet_install_epoch_evidence",
                lambda: check_applet_install_epoch_evidence_carrier(lint),
            ),
            ("mls_pq", lambda: check_mls_pq_suite_registration(lint)),
            ("service_kinds", lambda: check_service_kind_registry(lint)),
            ("action_refs", lambda: check_action_reference_closure(lint)),
            ("device_cursor", lambda: check_device_messages_cursor_binding(lint)),
        ],
        quiet=args.quiet,
        timing=args.timing,
    )

    if lint.errors:
        print("Artifact registry lint failed:", file=sys.stderr)
        for error in lint.errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        "Artifact registry lint passed "
        f"({len(known['event_kinds'])} event kinds, "
        f"{len(known['schema_ids'])} schemas, "
        f"{len(known['id_kinds'])} typed ID kinds, "
        f"{len(known['operation_ids'])} operations, "
        f"{len(known['claimable_profiles'])} claimable profiles, "
        f"{len(known['profiles'])} profile id references, "
        f"{time.perf_counter() - started:.2f}s)."
    )
    return 0
