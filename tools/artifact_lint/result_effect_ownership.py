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

from .core import ARTIFACTS, ROOT, SPEC_ROOT, Lint, load_json


CONTRACT_REGISTRY = ARTIFACTS / "registry" / "contract-registry.json"
_EVENT_KIND_RE = re.compile(r"\bak\.[a-z0-9_]+(?:\.[a-z0-9_]+)*\b")
_OWNERSHIP_KEYS = {
    "typed_result_writer": frozenset({"kind"}),
    "private_service_effect": frozenset({"kind", "service_contract_id"}),
    "audit_fact_no_current_projection": frozenset({"kind", "defined_in"}),
    "owned_gap": frozenset({"kind", "owner_report", "closure_condition"}),
}
_SERVICE_BRANCH_FIELDS = frozenset(
    {"branch", "durable_effect", "unique_key", "prior_state_cas", "exact_retry", "rejection"}
)
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
        if not isinstance(branch, dict) or not isinstance(branch.get("branch"), str):
            continue
        kinds.update(_EVENT_KIND_RE.findall(branch["branch"]))
    return kinds


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
                covering = [
                    branch
                    for branch in service.get("branches") or []
                    if isinstance(branch, dict)
                    and isinstance(branch.get("branch"), str)
                    and event_kind in _EVENT_KIND_RE.findall(branch["branch"])
                ]
                for branch in covering:
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
        elif classification == "audit_fact_no_current_projection":
            defined_in = ownership.get("defined_in")
            if has_writes or reducer_input is not False or not str(event_kind).startswith("ak.audit."):
                lint.fail(
                    CONTRACT_REGISTRY,
                    f"{where} says audit_fact_no_current_projection but the row is not a non-reducer ak.audit.* fact without result_writes[]",
                )
            if (
                not isinstance(defined_in, str)
                or not defined_in.startswith("zh/")
                or not (SPEC_ROOT / defined_in).is_file()
            ):
                lint.fail(CONTRACT_REGISTRY, f"{where}.defined_in must resolve to normative zh prose")
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
            if private_owners.get(event_kind) != contract_id:
                lint.fail(
                    CONTRACT_REGISTRY,
                    f"service_contracts[{contract_id!r}] branch for {event_kind} is an orphan private effect owner",
                )

    if any(
        isinstance(row, dict)
        and row.get("status") == "active"
        and row.get("wire_scope") in {"durable_event", "actor_private_event"}
        and isinstance(row.get("result_effect_ownership"), dict)
        and row["result_effect_ownership"].get("kind") == "owned_gap"
        for row in rows
    ) and not owner_reports:
        lint.fail(CONTRACT_REGISTRY, "owned_gap rows exist but no live owner_report resolved")
