"""Close the persistent Event effect-owner classification.

``result_writes[]`` proves a typed-result writer only after the row exists.  It
cannot distinguish a deliberate private service effect, a durable audit fact
with no current projection, and a specification gap.  Every active durable
Event (shared durable or actor-private) therefore carries one closed
``result_effect_ownership`` object in the
canonical contract registry; this gate checks the classification against the
writer rows, service contracts and live gap owner it cites.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .core import (
    ARTIFACTS,
    ROOT,
    SPEC_ROOT,
    Lint,
    load_json,
    resolve_artifact_schema_ref,
    resolve_json_pointer,
)


CONTRACT_REGISTRY = ARTIFACTS / "registry" / "contract-registry.json"
_EVENT_KIND_RE = re.compile(r"\bak\.[a-z0-9_]+(?:\.[a-z0-9_]+)*\b")
_OWNERSHIP_KEYS = {
    "typed_result_writer": frozenset({"kind"}),
    "private_service_effect": frozenset({"kind", "service_contract_id"}),
    "durable_fact_no_current_projection": frozenset({"kind", "defined_in"}),
    "authority_commit_effect": frozenset({"kind", "service_contract_id"}),
    "owned_gap": frozenset({"kind", "owner_report", "closure_condition"}),
}
_SERVICE_BRANCH_FIELDS = frozenset(
    {"branch", "durable_effect", "unique_key", "prior_state_cas", "exact_retry", "rejection"}
)
_ACTOR_PRIVATE_EFFECT_KEYS = frozenset(
    {
        "result_family",
        "durable_effect",
        "storage_owner",
        "unique_key",
        "value_projection",
        "field_maintenance",
        "concurrency",
        "exact_retry",
        "rejection",
        "shared_realm_effect",
    }
)
_AGENT_DRAFT_PENDING_EFFECT_KEYS = _ACTOR_PRIVATE_EFFECT_KEYS | {"pending_intent_lifecycle"}
_ACTOR_PRIVATE_OWNER_SOURCES = {
    "ak.account_data.set": "envelope.actor_id",
    "ak.agent.action_reject": "envelope.actor_id",
    "ak.agent.action_request": "payload.controller_account_id",
    "ak.agent.draft.propose": "payload.controller_account_id",
    "ak.device.push_route": "payload.account_id",
    "ak.read_cursor.advance": "payload.actor_id.account_id",
}
_SHARED_GAP_CLOSURE_TERMS = (
    "result_writes[]",
    "family",
    "selector",
    "projection",
    "value schema",
    "guard",
    "field source",
)
_PRIVATE_GAP_CLOSURE_TERMS = (
    "storage owner",
    "unique key",
    "CAS",
    "retry",
    "zero-side-effect rejection",
    "maintenance sources",
    "private_service_effect",
)


def _service_branch_event_kinds(service: dict[str, Any]) -> set[str]:
    kinds: set[str] = set()
    for branch in service.get("branches") or []:
        if not isinstance(branch, dict):
            continue
        event_kind = branch.get("event_kind")
        if isinstance(event_kind, str):
            kinds.add(event_kind)
        elif isinstance(branch.get("branch"), str):
            kinds.update(_EVENT_KIND_RE.findall(branch["branch"]))
    return kinds


def _covering_service_branches(service: dict[str, Any], event_kind: str) -> list[dict[str, Any]]:
    return [
        branch
        for branch in service.get("branches") or []
        if isinstance(branch, dict)
        and (
            branch.get("event_kind") == event_kind
            or (
                isinstance(branch.get("branch"), str)
                and event_kind in _EVENT_KIND_RE.findall(branch["branch"])
            )
        )
    ]


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _validate_actor_private_effect(
    lint: Lint,
    document: dict[str, Any],
    service: dict[str, Any],
    event_kind: str,
    branch: dict[str, Any],
) -> None:
    where = f"actor_private_contracts.event_writes[{event_kind!r}]"
    if service.get("wire_scope") != "actor_private_event":
        lint.fail(CONTRACT_REGISTRY, f"{service.get('contract_id')} must be scoped to actor_private_event")
    if set(branch) != {"event_kind", "effect_contract_ref"}:
        lint.fail(
            CONTRACT_REGISTRY,
            f"{service.get('contract_id')} structured branch for {event_kind} must have exactly event_kind and effect_contract_ref",
        )
    expected_ref = f"#/event_kind_registry/actor_private_contracts/event_writes/{event_kind}"
    if branch.get("effect_contract_ref") != expected_ref:
        lint.fail(CONTRACT_REGISTRY, f"{event_kind} effect_contract_ref must be {expected_ref!r}")

    event_registry = document.get("event_kind_registry")
    registry = event_registry.get("actor_private_contracts") if isinstance(event_registry, dict) else None
    writes = registry.get("event_writes") if isinstance(registry, dict) else None
    families = registry.get("result_families") if isinstance(registry, dict) else None
    merges = registry.get("merge_definitions") if isinstance(registry, dict) else None
    if not isinstance(writes, dict) or not isinstance(families, dict) or not isinstance(merges, dict):
        lint.fail(CONTRACT_REGISTRY, "actor_private_contracts must declare event_writes, result_families and merge_definitions objects")
        return
    effect = writes.get(event_kind)
    if not isinstance(effect, dict):
        lint.fail(CONTRACT_REGISTRY, f"{where} does not resolve to a structured effect contract")
        return
    expected_effect_keys = (
        _AGENT_DRAFT_PENDING_EFFECT_KEYS
        if event_kind == "ak.agent.draft.propose"
        else _ACTOR_PRIVATE_EFFECT_KEYS
    )
    if set(effect) != expected_effect_keys:
        lint.fail(CONTRACT_REGISTRY, f"{where} must have exactly {sorted(expected_effect_keys)}")

    family_id = effect.get("result_family")
    family = families.get(family_id) if isinstance(family_id, str) else None
    if not isinstance(family, dict):
        lint.fail(CONTRACT_REGISTRY, f"{where}.result_family is not registered: {family_id!r}")

    owner = effect.get("storage_owner")
    if not isinstance(owner, dict) or set(owner) != {"kind", "account_id_source", "station_id_source"}:
        lint.fail(CONTRACT_REGISTRY, f"{where}.storage_owner must be a closed owner object")
    else:
        expected_source = _ACTOR_PRIVATE_OWNER_SOURCES.get(event_kind)
        if (
            owner.get("kind") != "account_station_private_store"
            or owner.get("account_id_source") != expected_source
            or owner.get("station_id_source") != "selected_account_id.station_id"
        ):
            lint.fail(CONTRACT_REGISTRY, f"{where}.storage_owner names the wrong private account owner")

    unique_key = effect.get("unique_key")
    components = unique_key.get("components") if isinstance(unique_key, dict) else None
    if (
        not isinstance(unique_key, dict)
        or set(unique_key) != {"components"}
        or not isinstance(components, list)
        or not components
        or not all(_nonempty_string(component) for component in components)
    ):
        lint.fail(CONTRACT_REGISTRY, f"{where}.unique_key must be a closed non-empty components[] object")

    projection = effect.get("value_projection")
    members = projection.get("members") if isinstance(projection, dict) else None
    if (
        not isinstance(projection, dict)
        or set(projection) != {"kind", "schema_ref", "members"}
        or not _nonempty_string(projection.get("kind"))
        or not _nonempty_string(projection.get("schema_ref"))
        or not isinstance(members, list)
        or not members
    ):
        lint.fail(CONTRACT_REGISTRY, f"{where}.value_projection must close kind, schema_ref and members[]")
    else:
        for index, member in enumerate(members):
            if (
                not isinstance(member, dict)
                or set(member) != {"target", "source"}
                or not _nonempty_string(member.get("target"))
                or not _nonempty_string(member.get("source"))
            ):
                lint.fail(CONTRACT_REGISTRY, f"{where}.value_projection.members[{index}] must close target and source")
        schema_ref = projection["schema_ref"]
        schema_path = resolve_artifact_schema_ref(lint, CONTRACT_REGISTRY, schema_ref)
        if schema_path is not None:
            fragment = "#" + schema_ref.split("#", 1)[1] if "#" in schema_ref else "#"
            try:
                resolved = resolve_json_pointer(load_json(lint, schema_path), fragment)
                if not isinstance(resolved, dict):
                    raise TypeError("target is not an object schema")
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                lint.fail(CONTRACT_REGISTRY, f"{where}.value_projection.schema_ref does not resolve: {exc}")

    maintenance = effect.get("field_maintenance")
    if not isinstance(maintenance, list) or not maintenance:
        lint.fail(CONTRACT_REGISTRY, f"{where}.field_maintenance must be a non-empty array")
    else:
        for index, rule in enumerate(maintenance):
            if (
                not isinstance(rule, dict)
                or set(rule) != {"target", "source", "rule"}
                or not all(_nonempty_string(rule.get(member)) for member in ("target", "source", "rule"))
            ):
                lint.fail(CONTRACT_REGISTRY, f"{where}.field_maintenance[{index}] must close target, source and rule")

    concurrency = effect.get("concurrency")
    if (
        not isinstance(concurrency, dict)
        or set(concurrency) != {"kind", "precondition", "accepted_write", "conflict"}
        or not all(_nonempty_string(concurrency.get(member)) for member in concurrency)
    ):
        lint.fail(CONTRACT_REGISTRY, f"{where}.concurrency must close kind, precondition, accepted_write and conflict")
    else:
        merge_kind = concurrency["kind"]
        if merge_kind not in merges:
            lint.fail(CONTRACT_REGISTRY, f"{where}.concurrency.kind is unknown: {merge_kind!r}")
        if isinstance(family, dict) and family.get("merge") != merge_kind:
            lint.fail(CONTRACT_REGISTRY, f"{where}.concurrency.kind disagrees with its result family merge")

    retry = effect.get("exact_retry")
    if (
        not isinstance(retry, dict)
        or set(retry) != {"identity", "same_bytes", "different_bytes"}
        or not all(_nonempty_string(retry.get(member)) for member in retry)
    ):
        lint.fail(CONTRACT_REGISTRY, f"{where}.exact_retry must close identity, same_bytes and different_bytes")

    rejection = effect.get("rejection")
    conditions = rejection.get("conditions") if isinstance(rejection, dict) else None
    if (
        not isinstance(rejection, dict)
        or set(rejection) != {"conditions", "side_effects"}
        or not isinstance(conditions, list)
        or not conditions
        or not all(_nonempty_string(condition) for condition in conditions)
        or rejection.get("side_effects") != "zero"
    ):
        lint.fail(CONTRACT_REGISTRY, f"{where}.rejection must close non-empty conditions[] and side_effects=zero")
    if not _nonempty_string(effect.get("durable_effect")):
        lint.fail(CONTRACT_REGISTRY, f"{where}.durable_effect must be non-empty")
    if effect.get("shared_realm_effect") != "none":
        lint.fail(CONTRACT_REGISTRY, f"{where}.shared_realm_effect must be none")


def _owner_report_exists(owner: str) -> bool:
    """Resolve a coordination owner when the sibling work repository is present."""

    workspace = ROOT.parent
    work = workspace / "arkret-work"
    if not work.is_dir():
        # Standalone arkret-spec checkouts cannot validate a sibling repository,
        # but the closed path shape remains mandatory below.
        return True
    prefix = "arkret-work/"
    return owner.startswith(prefix) and (work / owner[len(prefix) :]).is_file()


def check_result_effect_ownership(lint: Lint) -> None:
    """Every active persistent Event has one non-contradictory effect owner."""

    document = load_json(lint, CONTRACT_REGISTRY)
    if not isinstance(document, dict):
        return
    event_registry = document.get("event_kind_registry")
    rows = event_registry.get("event_kinds") if isinstance(event_registry, dict) else None
    if not isinstance(rows, list):
        lint.fail(CONTRACT_REGISTRY, "event_kind_registry.event_kinds[] must be an array")
        return

    services = {
        row.get("contract_id"): row
        for row in document.get("service_contracts") or []
        if isinstance(row, dict) and isinstance(row.get("contract_id"), str)
    }
    service_events = {
        contract_id: _service_branch_event_kinds(service)
        for contract_id, service in services.items()
    }
    private_owners: dict[str, str] = {}
    owner_reports: set[str] = set()
    active_persistent = 0

    for row in rows:
        if not isinstance(row, dict):
            continue
        event_kind = row.get("event_kind")
        ownership = row.get("result_effect_ownership")
        in_scope = row.get("status") == "active" and row.get("wire_scope") in {
            "durable_event",
            "actor_private_event",
        }
        if not in_scope:
            if ownership is not None:
                lint.fail(
                    CONTRACT_REGISTRY,
                    f"{event_kind}.result_effect_ownership is orphaned: only active persistent Event rows carry it",
                )
            continue
        active_persistent += 1
        where = f"{event_kind}.result_effect_ownership"
        if not isinstance(ownership, dict):
            lint.fail(CONTRACT_REGISTRY, f"{where} must be a closed object")
            continue
        classification = ownership.get("kind")
        expected_keys = _OWNERSHIP_KEYS.get(classification)
        if expected_keys is None:
            lint.fail(
                CONTRACT_REGISTRY,
                f"{where}.kind must be one of {sorted(_OWNERSHIP_KEYS)}, not {classification!r}",
            )
            continue
        if set(ownership) != expected_keys:
            lint.fail(
                CONTRACT_REGISTRY,
                f"{where} for {classification} must have exactly {sorted(expected_keys)}",
            )

        writes = row.get("result_writes")
        has_writes = isinstance(writes, list) and bool(writes)
        reducer_input = row.get("reducer_input")
        if classification == "typed_result_writer":
            if row.get("wire_scope") != "durable_event" or not has_writes or reducer_input is not True:
                lint.fail(
                    CONTRACT_REGISTRY,
                    f"{where} says typed_result_writer but the row does not have non-empty result_writes[] with reducer_input=true",
                )
        elif classification == "private_service_effect":
            contract_id = ownership.get("service_contract_id")
            service = services.get(contract_id)
            if has_writes or reducer_input is not False:
                lint.fail(
                    CONTRACT_REGISTRY,
                    f"{where} says private_service_effect but the row writes Realm typed results or has reducer_input!=false",
                )
            if not isinstance(service, dict) or service.get("status") != "active":
                lint.fail(CONTRACT_REGISTRY, f"{where}.service_contract_id is not an active service contract: {contract_id!r}")
            elif event_kind not in service_events.get(contract_id, set()):
                lint.fail(
                    CONTRACT_REGISTRY,
                    f"{where} cites {contract_id!r}, but no branch of that service contract covers {event_kind}",
                )
            else:
                covering = _covering_service_branches(service, event_kind)
                if len(covering) != 1:
                    lint.fail(CONTRACT_REGISTRY, f"{where} must have exactly one covering branch in {contract_id!r}")
                for branch in covering:
                    if service.get("contract_kind") == "actor_private_effect_owner":
                        if row.get("wire_scope") != "actor_private_event":
                            lint.fail(
                                CONTRACT_REGISTRY,
                                f"{where} mixes a shared durable Event with an actor-private effect contract",
                            )
                        _validate_actor_private_effect(lint, document, service, event_kind, branch)
                    else:
                        missing = [
                            member
                            for member in sorted(_SERVICE_BRANCH_FIELDS)
                            if not isinstance(branch.get(member), str) or not branch[member].strip()
                        ]
                        if missing:
                            lint.fail(
                                CONTRACT_REGISTRY,
                                f"{where} is covered by an incomplete {contract_id!r} branch; missing {missing}",
                            )
            if isinstance(event_kind, str) and isinstance(contract_id, str):
                private_owners[event_kind] = contract_id
        elif classification == "durable_fact_no_current_projection":
            defined_in = ownership.get("defined_in")
            if has_writes:
                lint.fail(
                    CONTRACT_REGISTRY,
                    f"{where} says durable_fact_no_current_projection but the row declares result_writes[]",
                )
            if (
                not isinstance(defined_in, str)
                or not defined_in.startswith("zh/")
                or not (SPEC_ROOT / defined_in).is_file()
            ):
                lint.fail(CONTRACT_REGISTRY, f"{where}.defined_in must resolve to normative zh prose")
        elif classification == "authority_commit_effect":
            contract_id = ownership.get("service_contract_id")
            service = services.get(contract_id)
            if has_writes or reducer_input is not True or row.get("wire_scope") != "durable_event":
                lint.fail(CONTRACT_REGISTRY, f"{where} must be a durable reducer input with no Realm result_writes[]")
            if not isinstance(service, dict) or service.get("contract_kind") != "authority_commit_effect_owner":
                lint.fail(CONTRACT_REGISTRY, f"{where}.service_contract_id is not an authority-commit effect owner")
            else:
                covering = _covering_service_branches(service, event_kind)
                if len(covering) != 1:
                    lint.fail(CONTRACT_REGISTRY, f"{where} must have exactly one authority-commit branch")
                for branch in covering:
                    required = {
                        "event_kind", "storage_owner", "unique_key", "precondition",
                        "accepted_effect", "exact_retry", "rejection", "counter_owner",
                        "typed_current_result_effect",
                    }
                    if set(branch) != required or not all(
                        _nonempty_string(branch.get(member)) for member in required
                    ):
                        lint.fail(CONTRACT_REGISTRY, f"{where} authority-commit branch is not structurally closed")
                    if branch.get("counter_owner") != "RealmCommit.governance_generation":
                        lint.fail(CONTRACT_REGISTRY, f"{where} names the wrong governance counter owner")
                    if branch.get("typed_current_result_effect") != "none":
                        lint.fail(CONTRACT_REGISTRY, f"{where} duplicates governance_generation into a Realm typed result")
            if isinstance(event_kind, str) and isinstance(contract_id, str):
                private_owners[event_kind] = contract_id
        else:
            owner = ownership.get("owner_report")
            closure = ownership.get("closure_condition")
            if has_writes:
                lint.fail(
                    CONTRACT_REGISTRY,
                    f"{where} says owned_gap but the row already writes typed results",
                )
            if (
                not isinstance(owner, str)
                or not owner.startswith("arkret-work/tasks/spec-open/")
                or not owner.endswith(".md")
                or not _owner_report_exists(owner)
            ):
                lint.fail(CONTRACT_REGISTRY, f"{where}.owner_report is missing, malformed or orphaned: {owner!r}")
            else:
                owner_reports.add(owner)
            required_terms = (
                _PRIVATE_GAP_CLOSURE_TERMS
                if row.get("wire_scope") == "actor_private_event"
                else _SHARED_GAP_CLOSURE_TERMS
            )
            missing_terms = (
                list(required_terms)
                if not isinstance(closure, str)
                else [term for term in required_terms if term not in closure]
            )
            if (
                not isinstance(closure, str)
                or len(closure.strip()) < 80
                or str(event_kind) not in closure
                or missing_terms
            ):
                lint.fail(
                    CONTRACT_REGISTRY,
                    f"{where}.closure_condition must name {event_kind} and the complete closure; missing terms {missing_terms}",
                )

    if active_persistent == 0:
        lint.fail(CONTRACT_REGISTRY, "result effect ownership inspected no active persistent Event row")

    # A service contract branch that names a concrete Event effect must be
    # selected by that Event row; otherwise the service-side owner is orphaned.
    for contract_id, event_kinds in service_events.items():
        for event_kind in sorted(event_kinds):
            event_row = next(
                (
                    row
                    for row in rows
                    if isinstance(row, dict)
                    and row.get("event_kind") == event_kind
                    and row.get("status") == "active"
                ),
                None,
            )
            service = services[contract_id]
            if event_row is None:
                lint.fail(
                    CONTRACT_REGISTRY,
                    f"service_contracts[{contract_id!r}] branch names an unknown or inactive Event kind {event_kind}",
                )
            elif (
                service.get("contract_kind") == "actor_private_effect_owner"
                and event_row.get("wire_scope") != "actor_private_event"
            ):
                lint.fail(
                    CONTRACT_REGISTRY,
                    f"service_contracts[{contract_id!r}] branch for {event_kind} mixes shared and actor-private scope",
                )
            if private_owners.get(event_kind) != contract_id:
                lint.fail(
                    CONTRACT_REGISTRY,
                    f"service_contracts[{contract_id!r}] branch for {event_kind} is an orphan private effect owner",
                )

    private_registry = event_registry.get("actor_private_contracts") if isinstance(event_registry, dict) else None
    private_writes = private_registry.get("event_writes") if isinstance(private_registry, dict) else None
    actor_services = [
        service
        for service in services.values()
        if service.get("contract_kind") == "actor_private_effect_owner"
    ]
    if actor_services:
        referenced = set().union(*(_service_branch_event_kinds(service) for service in actor_services))
        if not isinstance(private_writes, dict):
            lint.fail(CONTRACT_REGISTRY, "actor-private effect owner exists without actor_private_contracts.event_writes")
        else:
            for event_kind in sorted(set(private_writes) - referenced):
                lint.fail(CONTRACT_REGISTRY, f"actor_private_contracts.event_writes[{event_kind!r}] is an orphan branch")
            for event_kind in sorted(referenced - set(private_writes)):
                lint.fail(CONTRACT_REGISTRY, f"actor-private service branch {event_kind} has no structured event_writes contract")

    if any(
        isinstance(row, dict)
        and row.get("status") == "active"
        and row.get("wire_scope") in {"durable_event", "actor_private_event"}
        and isinstance(row.get("result_effect_ownership"), dict)
        and row["result_effect_ownership"].get("kind") == "owned_gap"
        for row in rows
    ) and not owner_reports:
        lint.fail(CONTRACT_REGISTRY, "owned_gap rows exist but no live owner_report resolved")
