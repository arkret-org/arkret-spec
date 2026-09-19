"""Close peer Event-submit semantic branches and their aggregate carriers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .core import ARTIFACTS, SPEC_ROOT, Lint, load_json, read_text


SCHEMA = ARTIFACTS / "schemas" / "authority-commit-operations.schema.json"
CONTRACT = ARTIFACTS / "registry" / "contract-registry.json"
ERRORS = ARTIFACTS / "registry" / "error-code-registry.json"
ERROR_MAPPING = ARTIFACTS / "registry" / "operations-error-mapping.json"
PROFILES = ARTIFACTS / "profiles" / "conformance-profiles.json"
VECTORS = ARTIFACTS / "registry" / "vector-registry.json"
FIXTURE = ARTIFACTS / "fixtures" / "peer-event-submit-semantic-union-fixture.json"
OPENAPI = ARTIFACTS / "openapi" / "arkret-service-api.openapi.yaml"
RUNNER = Path(__file__).with_name("runner.py")

PROSE_MARKERS = {
    SPEC_ROOT / "zh" / "sync" / "service-http-binding.md": (
        "`authority_forward`",
        "`committed_replication`",
        "`registered_atomic_unit`",
        "不得重做首次 admission、重签 Commit 或创建第二轮 fanout",
        "`stored|duplicate|rejected`",
    ),
    SPEC_ROOT / "zh" / "sync" / "federation.md": (
        "source `EventCommitSubmission`、source-signed `RealmCommit`",
        "`status=\"stored\"|\"duplicate\"`",
        "不得把 replica persistence 称为新的 accepted finality",
    ),
    SPEC_ROOT / "zh" / "identity" / "contact-and-direct-conversation.md": (
        "`direct_conversation_founding_unit_submission`",
        "`direct_conversation_founding_federation_submission`",
        "main_strand_id",
        "第四条",
        "不携带 `founding_authority_evidence`",
        "重签第二套 Commit",
        "第二轮 fanout",
    ),
    SPEC_ROOT / "zh" / "crypto-media" / "device-lifecycle.md": (
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
    contract = load_json(lint, CONTRACT)
    errors = load_json(lint, ERRORS)
    mapping = load_json(lint, ERROR_MAPPING)
    profiles = load_json(lint, PROFILES)
    vectors = load_json(lint, VECTORS)
    fixture = load_json(lint, FIXTURE)
    if not all(isinstance(item, dict) for item in (schema, contract, errors, mapping, profiles, vectors, fixture)):
        return

    defs = schema.get("$defs", {})
    required_defs = {
        "self_submit_request",
        "self_submit_outcome",
        "peer_submit_request",
        "peer_submit_outcome",
        "committed_event_submission",
        "replicated_committed_event_submission",
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

    submissions = peer.get("properties", {}).get("submissions", {})
    if submissions.get("minItems") != 1 or submissions.get("maxItems") != 100:
        _fail(lint, SCHEMA, "committed replication must remain bounded to 1..100 submissions")
    if _ref_name(submissions.get("items")) != "#/$defs/replicated_committed_event_submission":
        _fail(lint, SCHEMA, "replication items must use the witness-bearing committed row")
    committed = defs["committed_event_submission"]
    if _required(committed) != {"submission", "source_commit"} or committed.get("additionalProperties") is not False:
        _fail(lint, SCHEMA, "committed_event_submission must be closed EventCommitSubmission + source_commit")
    replicated = defs["replicated_committed_event_submission"]
    if _required(replicated) != {"committed_event", "recipient_witnesses"} or replicated.get("additionalProperties") is not False:
        _fail(lint, SCHEMA, "replicated row must require exact committed_event and recipient_witnesses")

    replication_outcome = defs["peer_committed_replication_outcome"]
    results = replication_outcome.get("properties", {}).get("results", {})
    if _ref_name(results.get("items")) != "#/$defs/peer_committed_replication_record":
        _fail(lint, SCHEMA, "replication outcome must return same-order typed results")
    result_branches = defs.get("peer_committed_replication_record", {}).get("oneOf", [])
    statuses: list[Any] = []
    for item in result_branches if isinstance(result_branches, list) else []:
        status = item.get("properties", {}).get("status", {}) if isinstance(item, dict) else {}
        statuses.extend(status.get("enum", []))
        if "const" in status:
            statuses.append(status["const"])
    if statuses != ["stored", "duplicate", "rejected"]:
        _fail(lint, SCHEMA, "replication result status vocabulary must be stored|duplicate|rejected")

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
    if _required(peer_founding) != {"unit_kind", "committed_events", "source_acceptance_receipt", "founding_authority_evidence"}:
        _fail(lint, SCHEMA, "peer founding unit must require four source rows, receipt and authority evidence")
    if peer_founding.get("additionalProperties") is not False:
        _fail(lint, SCHEMA, "peer founding unit must be closed")
    founding_rows = peer_founding.get("properties", {}).get("committed_events", {})
    if founding_rows.get("minItems") != 4 or founding_rows.get("maxItems") != 4 or founding_rows.get("items") is not False:
        _fail(lint, SCHEMA, "peer founding committed row count must be exactly four")

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
    required_reserved = {
        "direct_conversation_binding_invalid",
        "direct_conversation_invite_forbidden",
        "direct_conversation_member_count_invalid",
        "direct_conversation_participant_authority_denied",
        "direct_conversation_root_mask_violation",
        "direct_conversation_terminal_forbidden",
        "direct_conversation_third_party_member_forbidden",
    }
    for code in sorted(required_reserved):
        row = _find(code_rows, "code", code)
        if not isinstance(row, dict) or row.get("status") != "reserved" or not row.get("activation_condition"):
            _fail(lint, ERRORS, f"{code} must remain reserved until its own machine producer path is registered")

    mapping_row = _find(mapping.get("operations"), "operation_id", "ak.peer.events.command.submit.v1")
    required_codes = {"dependency_missing", "source_refs_unverifiable", "history_not_visible", "membership_compensation_conflict", "direct_conversation_founding_unit_invalid", "direct_conversation_pair_materialization_conflict"}
    if not isinstance(mapping_row, dict) or not required_codes.issubset(set(mapping_row.get("operation_specific", []))):
        _fail(lint, ERROR_MAPPING, "peer submit error map omits branch-specific rejection codes")

    membership_profile = profiles.get("profile_requirements", {}).get("ak.profile.membership_join_compensation.v1", {})
    expected_wire_refs = [
        "schemas/authority-commit-operations.schema.json#/$defs/membership_compensation_unit_submission",
        "schemas/authority-commit-operations.schema.json#/$defs/membership_compensation_federation_submission",
    ]
    if membership_profile.get("wire_contract_refs") != expected_wire_refs:
        _fail(lint, PROFILES, "membership compensation profile must reference both current aggregate carriers")

    vector_rows = vectors.get("vectors")
    peer_vector = _find(vector_rows, "vector_id", "ak.vector.peer.event_submit.semantic_union.v1")
    if not isinstance(peer_vector, dict) or peer_vector.get("applies_to_fixtures") != [FIXTURE.name]:
        _fail(lint, VECTORS, "peer semantic-union vector must bind the executable fixture")
    descriptions = {row.get("vector_id"): row.get("description", "") for row in vector_rows if isinstance(row, dict)} if isinstance(vector_rows, list) else {}
    if "first and fourth Event IDs" not in descriptions.get("ak.vector.direct_conversation.founding_unit.v1", ""):
        _fail(lint, VECTORS, "founding-unit vector must derive main Strand from the fourth Event")
    authoring = descriptions.get("ak.vector.direct_conversation.founding_authoring_material.v1", "")
    if "sole member is founding_authority_evidence" not in authoring or "rejects any echo" not in authoring:
        _fail(lint, VECTORS, "authoring-material vector must pin the evidence/submission non-echo boundary")

    required_cases = {"authority_forward", "committed_replication", "direct_conversation_founding", "founding_authoring_material_non_echo", "membership_compensation"}
    actual_cases = {row.get("name") for row in fixture.get("cases", []) if isinstance(row, dict)}
    if actual_cases != required_cases:
        _fail(lint, FIXTURE, f"fixture cases drift: expected {sorted(required_cases)}, got {sorted(actual_cases)}")
    fixture_text = read_text(FIXTURE) if FIXTURE.is_file() else ""
    for marker in (
        "missing_source_commit",
        "wrong_authority_generation",
        "broken_previous_commit_chain",
        "main_strand_from_fourth_event",
        "main_strand_from_third_event",
        "self_submission_echoes_evidence",
        "missing_terminal_certificate",
        "superseded_by_j2_or_new_join",
        "duplicate_attempts_second_fanout",
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

    forbidden_targets = (SCHEMA, CONTRACT, PROFILES, FIXTURE, OPENAPI) + tuple(PROSE_MARKERS)
    for path in forbidden_targets:
        text = read_text(path) if path.is_file() else ""
        if "EventFederationSubmission" in text:
            _fail(lint, path, "deleted EventFederationSubmission must not be restored on a current carrier surface")
