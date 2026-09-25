"""Close peer Event-submit semantic branches and their aggregate carriers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .core import ARTIFACTS, SPEC_ROOT, Lint, load_json, read_text


SCHEMA = ARTIFACTS / "schemas" / "authority-commit-operations.schema.json"
DTO_SCHEMA = ARTIFACTS / "schemas" / "service-operation-dtos.schema.json"
DIRECT_SCHEMA = ARTIFACTS / "schemas" / "direct-conversation-operations.schema.json"
CONTRACT = ARTIFACTS / "registry" / "contract-registry.json"
ERRORS = ARTIFACTS / "registry" / "error-code-registry.json"
ERROR_MAPPING = ARTIFACTS / "registry" / "operations-error-mapping.json"
PROFILES = ARTIFACTS / "profiles" / "conformance-profiles.json"
VECTORS = ARTIFACTS / "registry" / "vector-registry.json"
FIXTURE = ARTIFACTS / "fixtures" / "peer-event-submit-semantic-union-fixture.json"
OPENAPI = ARTIFACTS / "openapi" / "arkret-service-api.openapi.yaml"
RUNNER = Path(__file__).with_name("runner.py")
PRODUCER_EVIDENCE_VECTOR = "ak.vector.federation.authority_forward_producer_device_evidence.v1"
PRODUCER_DEVICE_CODES = (
    "device_unauthorized",
    "device_revoked",
    "device_revocation_pending",
    "device_generation_fenced",
)

PROSE_MARKERS = {
    SPEC_ROOT / "zh" / "sync" / "service-http-binding.md": (
        "`authority_forward`",
        "`committed_replication`",
        "`registered_atomic_unit`",
        "不得重做首次 admission",
        "`replication_outcomes[]`",
        "`producer_device_evidence`",
    ),
    SPEC_ROOT / "zh" / "sync" / "federation.md": (
        "`EventAdmissionSubmission` 与 source-signed",
        "`status=\"stored\"|\"duplicate\"`",
        "`fanout_authorization_basis`",
        "不得把 replica persistence 称为新的 accepted finality",
        "**跨站 human 设备 producer（normative）**",
        "**非治理接收方以治理签名为准（normative）**",
        "`producer_device_evidence`",
    ),
    SPEC_ROOT / "zh" / "identity" / "contact-and-direct-conversation.md": (
        "`direct_conversation_founding_unit_submission`",
        "`direct_conversation_founding_federation_submission`",
        "main_strand_id",
        "第四条",
        "不携带 `founding_authority_evidence`",
        "重签第二套 Commit",
        "第二轮 fanout",
        "不再定义第二张 acceptance receipt",
        "第四个 Commit 的 `committed_at` 是唯一 founding acceptance time",
    ),
    SPEC_ROOT / "zh" / "crypto-media" / "device-lifecycle.md": (
        "#### 8.2.2 Human 设备 producer 解析（normative）",
        "`producer_device_evidence`",
        "不按 Control／Data／actor-private 或 event kind 分流",
        "`membership_compensation_unit_submission`",
        "`membership_compensation_federation_submission`",
        "`membership_compensation_conflict` 且零写入",
    ),
}


def _fail(lint: Lint, path: Any, message: str) -> None:
    lint.fail(path, f"peer Event-submit semantic union: {message}")


def _find(rows: Any, key: str, value: str) -> dict[str, Any] | None:
    if not isinstance(rows, list):
        return None
    return next((row for row in rows if isinstance(row, dict) and row.get(key) == value), None)


def _ref_name(node: Any) -> str | None:
    if not isinstance(node, dict):
        return None
    value = node.get("$ref")
    return value if isinstance(value, str) else None


def _required(node: Any) -> set[str]:
    if not isinstance(node, dict) or not isinstance(node.get("required"), list):
        return set()
    return {item for item in node["required"] if isinstance(item, str)}


def _section(text: str, start: str, end: str) -> str:
    """Return one named prose section without inspecting adjacent receipt vocabularies."""

    start_at = text.find(start)
    if start_at < 0:
        return ""
    end_at = text.find(end, start_at + len(start))
    return text[start_at:] if end_at < 0 else text[start_at:end_at]


def _check_founding_commit_only_surface(
    lint: Lint,
    path: Path,
    label: str,
    text: str,
    required_markers: tuple[str, ...],
    forbidden_markers: tuple[str, ...],
) -> None:
    """Pin one DC-founding surface without rejecting unrelated receipt protocols."""

    for marker in required_markers:
        if marker not in text:
            _fail(lint, path, f"{label} omits commit-only marker {marker!r}")
    for marker in forbidden_markers:
        if marker in text:
            _fail(lint, path, f"{label} restores deleted founding-receipt semantic {marker!r}")


def _resolve_pointer(document: Any, fragment: str) -> Any:
    if fragment == "#":
        return document
    if not fragment.startswith("#/"):
        return None
    node = document
    for raw in fragment[2:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or token not in node:
            return None
        node = node[token]
    return node


def check_profile_wire_contract_refs(lint: Lint) -> None:
    """Resolve every profile wire_contract_refs file and JSON Pointer fragment."""

    data = load_json(lint, PROFILES)
    if not isinstance(data, dict):
        return
    profiles = data.get("profile_requirements")
    if not isinstance(profiles, dict):
        _fail(lint, PROFILES, "profile_requirements object is missing")
        return
    for profile_id, profile in profiles.items():
        if not isinstance(profile, dict):
            continue
        refs = profile.get("wire_contract_refs", [])
        if not isinstance(refs, list):
            _fail(lint, PROFILES, f"{profile_id}.wire_contract_refs must be an array")
            continue
        for index, ref in enumerate(refs):
            if not isinstance(ref, str) or "#/$defs/" not in ref:
                _fail(lint, PROFILES, f"{profile_id}.wire_contract_refs[{index}] must target one named $defs fragment")
                continue
            file_part, fragment = ref.split("#", 1)
            target = ARTIFACTS / file_part
            document = load_json(lint, target) if target.is_file() else None
            if document is None:
                _fail(lint, PROFILES, f"{profile_id}.wire_contract_refs[{index}] file does not resolve: {file_part}")
                continue
            if _resolve_pointer(document, f"#{fragment}") is None:
                _fail(lint, PROFILES, f"{profile_id}.wire_contract_refs[{index}] fragment does not resolve: {ref}")


def check_peer_event_submit_semantic_union(lint: Lint) -> None:
    schema = load_json(lint, SCHEMA)
    dto_schema = load_json(lint, DTO_SCHEMA)
    direct_schema = load_json(lint, DIRECT_SCHEMA)
    contract = load_json(lint, CONTRACT)
    errors = load_json(lint, ERRORS)
    mapping = load_json(lint, ERROR_MAPPING)
    profiles = load_json(lint, PROFILES)
    vectors = load_json(lint, VECTORS)
    fixture = load_json(lint, FIXTURE)
    if not all(isinstance(item, dict) for item in (schema, dto_schema, direct_schema, contract, errors, mapping, profiles, vectors, fixture)):
        return

    defs = schema.get("$defs", {})
    dto_defs = dto_schema.get("$defs", {})
    if "EventAdmissionSubmission" not in dto_defs or "EventCommitSubmission" in dto_defs:
        _fail(lint, DTO_SCHEMA, "EventAdmissionSubmission must be the sole admission-submission type with no old alias")
    required_defs = {
        "self_submit_request",
        "self_submit_outcome",
        "peer_submit_request",
        "peer_submit_outcome",
        "committed_event_submission",
        "peer_committed_replication_outcome_record",
        "direct_conversation_founding_unit_submission",
        "direct_conversation_founding_federation_submission",
        "direct_conversation_founding_acceptance_outcome",
        "membership_compensation_unit_submission",
        "membership_compensation_federation_submission",
        "membership_compensation_evidence",
        "direct_conversation_founding_missing_dependency_list",
    }
    missing_defs = sorted(required_defs - set(defs) if isinstance(defs, dict) else required_defs)
    if missing_defs:
        _fail(lint, SCHEMA, f"missing canonical definitions: {missing_defs}")
        return

    peer = defs["peer_submit_request"]
    branch = peer.get("properties", {}).get("branch", {}) if isinstance(peer, dict) else {}
    if branch.get("enum") != ["authority_forward", "committed_replication", "registered_atomic_unit"]:
        _fail(lint, SCHEMA, "peer_submit_request branch enum must be the exact closed three-value list")
    if peer.get("additionalProperties") is not False or _required(peer) != {"branch"}:
        _fail(lint, SCHEMA, "peer_submit_request must be closed with branch as its common required field")
    branches = peer.get("oneOf") if isinstance(peer, dict) else None
    if not isinstance(branches, list) or len(branches) != 4:
        _fail(lint, SCHEMA, "peer_submit_request must have two authority-forward alternatives plus replication and atomic-unit alternatives")
    else:
        constants = [item.get("properties", {}).get("branch", {}).get("const") for item in branches if isinstance(item, dict)]
        if constants != ["authority_forward", "authority_forward", "committed_replication", "registered_atomic_unit"]:
            _fail(lint, SCHEMA, "peer_submit_request alternatives drift from the registered branch partition")
        allowed_fields = (
            {"branch", "event_submission", "mls_genesis_material", "producer_device_evidence"},
            {"branch", "mls_submission", "producer_device_evidence"},
            {"branch", "replications"},
            {"branch", "unit"},
        )
        all_branch_fields = {"event_submission", "mls_genesis_material", "mls_submission", "producer_device_evidence", "replications", "unit"}
        for index, (item, allowed) in enumerate(zip(branches, allowed_fields, strict=True)):
            forbidden = {
                next(iter(_required(candidate)))
                for candidate in item.get("not", {}).get("anyOf", [])
                if len(_required(candidate)) == 1
            }
            if forbidden != all_branch_fields - allowed:
                _fail(lint, SCHEMA, f"peer_submit_request alternative {index} must reject every cross-branch field")

    peer_properties = peer.get("properties", {})
    if set(peer_properties) != {"branch", "event_submission", "mls_genesis_material", "mls_submission", "producer_device_evidence", "replications", "unit"}:
        _fail(lint, SCHEMA, "peer_submit_request properties must be the exact branch field set")
    if _ref_name(peer_properties.get("mls_genesis_material")) != "#/$defs/mls_genesis_material":
        _fail(lint, SCHEMA, "authority_forward mls_genesis_material must use the closed mls_genesis_material definition")
    genesis_material = defs.get("mls_genesis_material", {})
    if genesis_material.get("additionalProperties") is not False or _required(genesis_material) != {"group_info_bytes_b64", "ratchet_tree_bytes_b64"} or set(genesis_material.get("properties", {})) != {"group_info_bytes_b64", "ratchet_tree_bytes_b64"}:
        _fail(lint, SCHEMA, "mls_genesis_material must be exactly the two raw Blob byte members with no ref or digest echo")
    if isinstance(branches, list) and branches:
        genesis_rule = branches[0]
        kind_const = (
            genesis_rule.get("if", {}).get("properties", {}).get("event_submission", {}).get("properties", {})
            .get("event", {}).get("properties", {}).get("kind", {}).get("const")
        )
        if kind_const != "ak.mls.genesis" or _required(genesis_rule.get("then", {})) != {"mls_genesis_material"} or _required(genesis_rule.get("else", {}).get("not", {})) != {"mls_genesis_material"}:
            _fail(lint, SCHEMA, "the Event kind alone must decide mls_genesis_material: required for ak.mls.genesis, forbidden otherwise")
    if _ref_name(peer_properties.get("producer_device_evidence")) != "./account-device-signer-evidence.schema.json":
        _fail(lint, SCHEMA, "authority_forward producer_device_evidence must directly reuse account-device-signer-evidence")
    if isinstance(branches, list):
        for item in branches:
            if isinstance(item, dict) and "producer_device_evidence" in _required(item):
                _fail(lint, SCHEMA, "producer_device_evidence presence is decided by the Event and must not be schema-required")
    replications = peer_properties.get("replications", {})
    if replications.get("minItems") != 1 or replications.get("maxItems") != 100:
        _fail(lint, SCHEMA, "committed replication must remain bounded to 1..100 replications")
    if _ref_name(replications.get("items")) != "#/$defs/committed_event_submission":
        _fail(lint, SCHEMA, "replication items must directly use the committed Event pair")
    for deleted_field in ("processing", "submissions", "recipient_witnesses"):
        if deleted_field in peer_properties:
            _fail(lint, SCHEMA, f"deleted peer request field must not return: {deleted_field}")
    for deleted_def in ("replicated_committed_event_submission", "replication_recipient_witness"):
        if deleted_def in defs:
            _fail(lint, SCHEMA, f"deleted peer replication wrapper must not return: {deleted_def}")
    committed = defs["committed_event_submission"]
    if _required(committed) != {"event_submission", "source_commit"} or committed.get("additionalProperties") is not False:
        _fail(lint, SCHEMA, "committed_event_submission must be closed EventAdmissionSubmission + source_commit")
    if set(committed.get("properties", {})) != {"event_submission", "source_commit", "welcomes"}:
        _fail(lint, SCHEMA, "committed_event_submission properties must be the Event pair plus the MLS Commit welcomes carrier, with no echoes or hints")
    welcomes = committed.get("properties", {}).get("welcomes", {})
    if welcomes.get("minItems") != 1 or _ref_name(welcomes.get("items")) != "./mls-welcome-delivery.schema.json":
        _fail(lint, SCHEMA, "committed_event_submission.welcomes must be a non-empty array of exact MlsWelcomeDelivery objects")
    welcome_kind = next(
        (
            rule.get("then", {}).get("properties", {}).get("event_submission", {}).get("properties", {})
            .get("event", {}).get("properties", {}).get("kind", {}).get("const")
            for rule in committed.get("allOf", [])
            if isinstance(rule, dict) and _required(rule.get("if", {})) == {"welcomes"}
        ),
        None,
    )
    if welcome_kind != "ak.mls.commit":
        _fail(lint, SCHEMA, "committed_event_submission.welcomes must be allowed only for an ak.mls.commit source Event")
    if _ref_name(committed.get("properties", {}).get("event_submission")) != "./service-operation-dtos.schema.json#/$defs/EventAdmissionSubmission":
        _fail(lint, SCHEMA, "committed_event_submission.event_submission must use the canonical admission submission")

    replication_outcome = defs["peer_committed_replication_outcome"]
    outcome_properties = replication_outcome.get("properties", {})
    if set(outcome_properties) != {"branch", "replication_outcomes"}:
        _fail(lint, SCHEMA, "replication outcome properties must be exactly branch and replication_outcomes")
    outcomes = outcome_properties.get("replication_outcomes", {})
    if _required(replication_outcome) != {"branch", "replication_outcomes"}:
        _fail(lint, SCHEMA, "replication outcome must require only branch and replication_outcomes")
    if outcomes.get("minItems") != 1 or outcomes.get("maxItems") != 100 or _ref_name(outcomes.get("items")) != "#/$defs/peer_committed_replication_outcome_record":
        _fail(lint, SCHEMA, "replication outcome must return 1..100 same-order typed replication_outcomes")
    if "results" in outcome_properties or "peer_committed_replication_record" in defs:
        _fail(lint, SCHEMA, "deleted generic results/record names must not return")
    result_branches = defs.get("peer_committed_replication_outcome_record", {}).get("oneOf", [])
    statuses: list[Any] = []
    for index, item in enumerate(result_branches if isinstance(result_branches, list) else []):
        properties = item.get("properties", {}) if isinstance(item, dict) else {}
        if "index" in properties or "committed_ref" in properties:
            _fail(lint, SCHEMA, "replication result must not echo redundant index or committed_ref")
        expected_properties = {"status"} if index == 0 else {"status", "reason_code"}
        if set(properties) != expected_properties:
            _fail(lint, SCHEMA, "replication outcome record properties must be the exact minimal set")
        status = item.get("properties", {}).get("status", {}) if isinstance(item, dict) else {}
        statuses.extend(status.get("enum", []))
        if "const" in status:
            statuses.append(status["const"])
    if statuses != ["stored", "duplicate", "rejected"]:
        _fail(lint, SCHEMA, "replication result status vocabulary must be stored|duplicate|rejected")
    if len(result_branches) == 2:
        if _required(result_branches[0]) != {"status"} or _required(result_branches[1]) != {"status", "reason_code"}:
            _fail(lint, SCHEMA, "replication result rows must contain only status and rejection reason_code")

    self_founding = defs["direct_conversation_founding_unit_submission"]
    events = self_founding.get("properties", {}).get("events", {})
    expected_order = [
        "#/$defs/direct_conversation_realm_create_submission",
        "#/$defs/direct_conversation_member_join_submission",
        "#/$defs/direct_conversation_member_join_submission",
        "#/$defs/direct_conversation_strand_create_submission",
    ]
    actual_order = [_ref_name(item) for item in events.get("prefixItems", [])]
    if events.get("minItems") != 4 or events.get("maxItems") != 4 or events.get("items") is not False or actual_order != expected_order:
        _fail(lint, SCHEMA, "self founding unit must be exactly realm/create, founder/join, peer/join, strand/create")
    if "founding_authority_evidence" in self_founding.get("properties", {}):
        _fail(lint, SCHEMA, "self founding unit must reject founding_authority_evidence echo")

    peer_founding = defs["direct_conversation_founding_federation_submission"]
    if _required(peer_founding) != {"unit_kind", "committed_events", "founding_authority_evidence"} or "source_acceptance_receipt" in peer_founding.get("properties", {}):
        _fail(lint, SCHEMA, "peer founding unit must require only four source rows and authority evidence, with no receipt")
    if peer_founding.get("additionalProperties") is not False:
        _fail(lint, SCHEMA, "peer founding unit must be closed")
    founding_rows = peer_founding.get("properties", {}).get("committed_events", {})
    if founding_rows.get("minItems") != 4 or founding_rows.get("maxItems") != 4 or founding_rows.get("items") is not False:
        _fail(lint, SCHEMA, "peer founding committed row count must be exactly four")
    founding_outcome = defs.get("direct_conversation_founding_acceptance_outcome", {})
    if _required(founding_outcome) != {"unit_kind", "status", "commits"} or "receipt" in founding_outcome.get("properties", {}):
        _fail(lint, SCHEMA, "founding outcome must return only the four source commits and no receipt")
    direct_defs = direct_schema.get("$defs", {}) if isinstance(direct_schema, dict) else {}
    direct_root_refs = {_ref_name(row) for row in direct_schema.get("oneOf", []) if isinstance(row, dict)} if isinstance(direct_schema, dict) else set()
    if "direct_conversation_founding_acceptance_receipt" in direct_defs or "#/$defs/direct_conversation_founding_acceptance_receipt" in direct_root_refs:
        _fail(lint, DIRECT_SCHEMA, "deleted Direct Conversation founding receipt must not be restored")

    atomic = defs.get("peer_registered_atomic_unit", {}).get("oneOf", [])
    atomic_refs = [_ref_name(item) for item in atomic if isinstance(item, dict)]
    if atomic_refs != ["#/$defs/direct_conversation_founding_federation_submission", "#/$defs/membership_compensation_federation_submission"]:
        _fail(lint, SCHEMA, "registered atomic unit registry must contain exactly founding and compensation")

    evidence = defs["membership_compensation_evidence"]
    if _required(evidence) != {"delegation", "terminal_certificate", "single_use_binding"} or evidence.get("additionalProperties") is not False:
        _fail(lint, SCHEMA, "membership compensation evidence must be the closed three-part carrier")
    core_action = defs.get("membership_compensation_delegation_core", {}).get("properties", {}).get("action", {}).get("enum")
    if core_action != ["ak.member.compensate.leave", "ak.member.compensate.remove"]:
        _fail(lint, SCHEMA, "membership compensation action must remain the closed leave/remove XOR")

    operations = contract.get("operation_registry", {}).get("operations")
    self_row = _find(operations, "operation_id", "ak.self.events.command.submit.v1")
    peer_row = _find(operations, "operation_id", "ak.peer.events.command.submit.v1")
    if not isinstance(self_row, dict) or not isinstance(peer_row, dict):
        _fail(lint, CONTRACT, "self or peer submit operation row is missing")
    else:
        if self_row.get("request_schema_ref") != "schemas/authority-commit-operations.schema.json#/$defs/self_submit_request" or self_row.get("response_schema_ref") != "schemas/authority-commit-operations.schema.json#/$defs/self_submit_outcome":
            _fail(lint, CONTRACT, "self submit must use endpoint-specific request/outcome refs")
        if peer_row.get("request_schema_ref") != "schemas/authority-commit-operations.schema.json#/$defs/peer_submit_request" or peer_row.get("response_schema_ref") != "schemas/authority-commit-operations.schema.json#/$defs/peer_submit_outcome":
            _fail(lint, CONTRACT, "peer submit must use endpoint-specific request/outcome refs")
        effect = peer_row.get("durable_effect", {})
        effect_branches = effect.get("effect_branches", []) if isinstance(effect, dict) else []
        if effect.get("kind") != "branched" or effect.get("discriminator", {}).get("request_path") != "/branch" or len(effect_branches) != 3:
            _fail(lint, CONTRACT, "peer durable effect must branch exactly on /branch")
        else:
            if effect_branches[0].get("equals") != "authority_forward" or effect_branches[0].get("effect", {}).get("kind") != "event_log":
                _fail(lint, CONTRACT, "authority_forward must be the only event_log branch")
            if effect_branches[1].get("equals") != "committed_replication" or effect_branches[1].get("effect", {}).get("kind") != "none":
                _fail(lint, CONTRACT, "committed_replication durable effect must be none")
            if effect_branches[2].get("otherwise") is not True or effect_branches[2].get("effect", {}).get("kind") != "none":
                _fail(lint, CONTRACT, "registered_atomic_unit durable effect must be final none branch")
            for index, branch_row in enumerate(effect_branches[1:], start=1):
                rationale = str(branch_row.get("effect", {}).get("rationale", ""))
                for marker in ("without_new_event_finality", "resigning", "second_fanout"):
                    if marker not in rationale:
                        _fail(lint, CONTRACT, f"none-effect branch {index} rationale omits {marker}")

    direct_schema_row = _find(
        contract.get("schema_registry", {}).get("schemas"),
        "schema_id",
        "ak.schema.direct_conversation_operations.v1",
    )
    if not isinstance(direct_schema_row, dict):
        _fail(lint, CONTRACT, "Direct Conversation schema registry row is missing")
    else:
        _check_founding_commit_only_surface(
            lint,
            CONTRACT,
            "Direct Conversation schema description",
            str(direct_schema_row.get("description", "")),
            ("verified founding-authority evidence", "no second acceptance receipt"),
            ("source founding acceptance receipt", "accepted_contact_evidence_digest", "DirectConversationFoundingAcceptanceReceipt"),
        )
    if isinstance(self_row, dict):
        _check_founding_commit_only_surface(
            lint,
            CONTRACT,
            "self Event-submit notes",
            str(self_row.get("notes", "")),
            ("same four consecutive source RealmCommits", "fourth committed_at is the sole acceptance time", "No founding receipt exists"),
            ("source-signed receipt", "accepted_contact_evidence_digest", "DirectConversationFoundingAcceptanceReceipt"),
        )

    code_rows = [
        *errors.get("codes", []),
        *errors.get("reason_codes", []),
    ]
    required_active = {
        "membership_compensation_conflict",
        "direct_conversation_founding_unit_invalid",
    }
    for code in sorted(required_active):
        row = _find(code_rows, "code", code)
        if not isinstance(row, dict) or row.get("status") != "active" or "activation_condition" in row:
            _fail(lint, ERRORS, f"{code} must be active after its machine producer path exists")
    independently_closed_active = {
        "direct_conversation_binding_invalid",
        "direct_conversation_invite_forbidden",
        "direct_conversation_member_count_invalid",
        "direct_conversation_participant_authority_denied",
        "direct_conversation_root_mask_violation",
        "direct_conversation_terminal_forbidden",
        "direct_conversation_third_party_member_forbidden",
    }
    for code in sorted(independently_closed_active):
        row = _find(code_rows, "code", code)
        if not isinstance(row, dict) or row.get("status") != "active" or "activation_condition" in row:
            _fail(lint, ERRORS, f"{code} must be active after its independent machine producer path is registered")

    materialization_conflict = _find(code_rows, "code", "direct_conversation_pair_materialization_conflict")
    if not isinstance(materialization_conflict, dict):
        _fail(lint, ERRORS, "direct_conversation_pair_materialization_conflict is missing")
    else:
        _check_founding_commit_only_surface(
            lint,
            ERRORS,
            "Direct Conversation materialization-conflict code",
            str(materialization_conflict.get("description", "")),
            ("four exact Events", "four consecutive source RealmCommits", "founding-authority evidence"),
            ("source acceptance receipts", "accepted_contact_evidence_digest", "DirectConversationFoundingAcceptanceReceipt"),
        )
    slot_committed = _find(code_rows, "code", "direct_conversation_slot_already_committed")
    if not isinstance(slot_committed, dict):
        _fail(lint, ERRORS, "direct_conversation_slot_already_committed is missing")
    else:
        _check_founding_commit_only_surface(
            lint,
            ERRORS,
            "Direct Conversation slot-committed code",
            str(slot_committed.get("description", "")),
            ("same four byte-identical source RealmCommits", "without changing the fourth committed_at"),
            ("stored byte-identical receipt", "accepted_contact_evidence_digest", "DirectConversationFoundingAcceptanceReceipt"),
        )

    mapping_row = _find(mapping.get("operations"), "operation_id", "ak.peer.events.command.submit.v1")
    required_codes = {"dependency_missing", "source_refs_unverifiable", "history_not_visible", "membership_compensation_conflict", "direct_conversation_founding_unit_invalid", "direct_conversation_pair_materialization_conflict"}
    if not isinstance(mapping_row, dict) or not required_codes.issubset(set(mapping_row.get("operation_specific", []))):
        _fail(lint, ERROR_MAPPING, "peer submit error map omits branch-specific rejection codes")

    self_mapping_row = _find(mapping.get("operations"), "operation_id", "ak.self.events.command.submit.v1")
    if not isinstance(self_mapping_row, dict):
        _fail(lint, ERROR_MAPPING, "self submit error-map row is missing")
    else:
        _check_founding_commit_only_surface(
            lint,
            ERROR_MAPPING,
            "self Event-submit error-map description",
            str(self_mapping_row.get("description", "")),
            ("four consecutive RealmCommits", "returns no second receipt"),
            ("one receipt atomically", "accepted_contact_evidence_digest", "DirectConversationFoundingAcceptanceReceipt"),
        )

    membership_profile = profiles.get("profile_requirements", {}).get("ak.profile.membership_join_compensation.v1", {})
    expected_wire_refs = [
        "schemas/authority-commit-operations.schema.json#/$defs/membership_compensation_unit_submission",
        "schemas/authority-commit-operations.schema.json#/$defs/membership_compensation_federation_submission",
    ]
    if membership_profile.get("wire_contract_refs") != expected_wire_refs:
        _fail(lint, PROFILES, "membership compensation profile must reference both current aggregate carriers")

    direct_profile = profiles.get("profile_requirements", {}).get("ak.profile.direct_conversation_realm.v1", {})
    direct_invariants = direct_profile.get("binding_invariants", []) if isinstance(direct_profile, dict) else []
    slot_invariant = next(
        (item for item in direct_invariants if isinstance(item, str) and item.startswith("The founding slot admits")),
        "",
    )
    _check_founding_commit_only_surface(
        lint,
        PROFILES,
        "Direct Conversation founding-slot invariant",
        slot_invariant,
        ("same four byte-identical source RealmCommits", "without changing the fourth committed_at", "no founding receipt exists"),
        ("return the stored receipt", "advancing accepted_at", "accepted_contact_evidence_digest", "DirectConversationFoundingAcceptanceReceipt"),
    )

    founding_slot_description = str(
        defs["direct_conversation_founding_unit_submission"].get("properties", {}).get("idempotency_key", {}).get("description", "")
    )
    _check_founding_commit_only_surface(
        lint,
        SCHEMA,
        "authority schema founding-slot description",
        founding_slot_description,
        ("same four byte-identical source RealmCommits", "without changing the fourth committed_at"),
        ("stored receipt", "accepted_contact_evidence_digest", "DirectConversationFoundingAcceptanceReceipt"),
    )

    vector_rows = vectors.get("vectors")
    peer_vector = _find(vector_rows, "vector_id", "ak.vector.peer.event_submit.semantic_union.v1")
    if not isinstance(peer_vector, dict) or peer_vector.get("applies_to_fixtures") != [FIXTURE.name]:
        _fail(lint, VECTORS, "peer semantic-union vector must bind the executable fixture")
    forward_vector = _find(vector_rows, "vector_id", PRODUCER_EVIDENCE_VECTOR)
    if (
        not isinstance(forward_vector, dict)
        or forward_vector.get("status") != "active"
        or forward_vector.get("applies_to_fixtures") != [FIXTURE.name]
    ):
        _fail(lint, VECTORS, "authority-forward producer-evidence vector must be active and bind the executable fixture")
    forward_case = _find(fixture.get("cases"), "name", "authority_forward_producer_device_evidence")
    if not isinstance(forward_case, dict) or forward_case.get("vector_id") != PRODUCER_EVIDENCE_VECTOR:
        _fail(lint, FIXTURE, "authority-forward producer-evidence case must carry its vector_id")
    for operation_id in ("ak.peer.events.command.submit.v1", "ak.self.events.command.submit.v1"):
        row = _find(mapping.get("operations"), "operation_id", operation_id)
        codes = set(row.get("operation_specific", [])) if isinstance(row, dict) else set()
        missing_device_codes = sorted(set(PRODUCER_DEVICE_CODES) - codes)
        if missing_device_codes:
            _fail(lint, ERROR_MAPPING, f"{operation_id} error map omits human producer device codes {missing_device_codes}")
    descriptions = {row.get("vector_id"): row.get("description", "") for row in vector_rows if isinstance(row, dict)} if isinstance(vector_rows, list) else {}
    if "first and fourth Event IDs" not in descriptions.get("ak.vector.direct_conversation.founding_unit.v1", ""):
        _fail(lint, VECTORS, "founding-unit vector must derive main Strand from the fourth Event")
    authoring = descriptions.get("ak.vector.direct_conversation.founding_authoring_material.v1", "")
    if "sole member is founding_authority_evidence" not in authoring or "rejects any echo" not in authoring:
        _fail(lint, VECTORS, "authoring-material vector must pin the evidence/submission non-echo boundary")
    admission = descriptions.get("ak.vector.direct_conversation.founding_admission.v1", "")
    if "same four byte-identical source RealmCommits" not in admission or "deleted founding receipt is rejected" not in admission or "fourth committed_at" not in admission:
        _fail(lint, VECTORS, "founding-admission vector must pin commit-only finality and receipt rejection")

    required_cases = {
        "authority_forward",
        "authority_forward_producer_device_evidence",
        "committed_replication",
        "non_governance_receiver_trusts_governance_commit",
        "direct_conversation_founding",
        "founding_authoring_material_non_echo",
        "membership_compensation",
    }
    actual_cases = {row.get("name") for row in fixture.get("cases", []) if isinstance(row, dict)}
    if actual_cases != required_cases:
        _fail(lint, FIXTURE, f"fixture cases drift: expected {sorted(required_cases)}, got {sorted(actual_cases)}")
    fixture_text = read_text(FIXTURE) if FIXTURE.is_file() else ""
    for marker in (
        "missing_source_commit",
        "wrong_authenticated_destination",
        "wrong_authority_generation",
        "broken_previous_commit_chain",
        "wire_recipient_witness_rejected",
        "wire_processing_rejected",
        "no_eligible_local_member",
        "membership_history_dependency_missing",
        "duplicate_source_coordinates_in_batch",
        "same_stream_out_of_order",
        "member_exit_or_route_change_cancels_outbox",
        "response_lost_exact_full_body_replay",
        "main_strand_from_fourth_event",
        "main_strand_from_third_event",
        "self_submission_echoes_evidence",
        "peer_injects_deleted_receipt",
        "missing_terminal_certificate",
        "superseded_by_j2_or_new_join",
        "duplicate_attempts_second_fanout",
        "same_station_control_event_accepted",
        "cross_station_forward_with_fresh_evidence_accepted",
        "exact_replay_after_evidence_expiry_returns_original_outcome",
        "source_station_differs_from_attested_account_station",
        "service_history_lacks_method_at_attested_at",
        "agent_producer_carries_evidence",
        "human_producer_without_evidence",
        "foreign_human_producer_replica_stored",
        "commit_signed_by_non_current_governance_station",
        "local_account_producer_key_mismatch",
    ):
        if marker not in fixture_text:
            _fail(lint, FIXTURE, f"fixture omits mutation case {marker}")

    openapi = read_text(OPENAPI) if OPENAPI.is_file() else ""
    for marker in (
        "../schemas/authority-commit-operations.schema.json#/$defs/self_submit_request",
        "../schemas/authority-commit-operations.schema.json#/$defs/self_submit_outcome",
        "../schemas/authority-commit-operations.schema.json#/$defs/peer_submit_request",
        "../schemas/authority-commit-operations.schema.json#/$defs/peer_submit_outcome",
        "../schemas/authority-commit-operations.schema.json#/$defs/direct_conversation_founding_dependency_missing_problem",
        "application/problem+json",
    ):
        if marker not in openapi:
            _fail(lint, OPENAPI, f"OpenAPI binding omits {marker!r}")

    for path, markers in PROSE_MARKERS.items():
        prose = read_text(path) if path.is_file() else ""
        for marker in markers:
            if marker not in prose:
                _fail(lint, path, f"normative prose omits {marker!r}")

    service_surface = SPEC_ROOT / "zh" / "sync" / "service-surface.md"
    service_submit_section = _section(
        read_text(service_surface) if service_surface.is_file() else "",
        "### 4.2 提交 Event",
        "### 4.3 获取单个 Event",
    )
    _check_founding_commit_only_surface(
        lint,
        service_surface,
        "service-surface Event-submit section",
        service_submit_section,
        ("founding success 只返回四个连续 source Commit", "第四个 Commit 的 `committed_at` 是唯一接受时间", "不返回第二张 receipt"),
        ("source-signed receipt", "accepted_contact_evidence_digest", "DirectConversationFoundingAcceptanceReceipt"),
    )

    device_lifecycle = SPEC_ROOT / "zh" / "crypto-media" / "device-lifecycle.md"
    device_founding_section = _section(
        read_text(device_lifecycle) if device_lifecycle.is_file() else "",
        "#### 9.2.4 Welcome、consume 与已接受的 founding unit",
        "### 9.3 普通 MLS join admission 与补偿（normative）",
    )
    _check_founding_commit_only_surface(
        lint,
        device_lifecycle,
        "device-lifecycle accepted-founding section",
        device_founding_section,
        ("四笔连续 source `RealmCommit`", "`founding_authority_evidence` 与本地唯一 slot", "不存在 founding receipt 输入或输出"),
        ("source acceptance receipt", "accepted_contact_evidence_digest", "DirectConversationFoundingAcceptanceReceipt"),
    )

    forbidden_targets = (SCHEMA, CONTRACT, PROFILES, FIXTURE, OPENAPI) + tuple(PROSE_MARKERS)
    for path in forbidden_targets:
        text = read_text(path) if path.is_file() else ""
        if "EventFederationSubmission" in text:
            _fail(lint, path, "deleted EventFederationSubmission must not be restored on a current carrier surface")
