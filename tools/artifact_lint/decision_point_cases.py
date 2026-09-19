"""Artifact lint: SDK clause decision points must reach an executable fixture case.

``check_sdk_clause_vector_evidence`` proves the *mapping* resolves: every clause
that accepts ``vector_result`` names registered active vectors, and every vector
it names is carried by some fixture file. It stops at the file. A clause could
therefore name a vector whose carrier fixture contains no case that exercises the
obligation, and every gate stayed green -- which is the same failure shape as a
``section_digest`` that proves the hash equals the prose without proving the
prose satisfies the requirement.

``check_sdk_decision_point_cases`` closes the last two hops of
``clause -> decision point -> active vector -> carrier -> case -> runner``. A
fixture case opts in by carrying ``covers_decision_points``: a list of
``"<clause_id>/<decision_point_id>"`` strings. The check then proves, in both
directions, that

* every declared reference names a decision point that exists in the contract,
  so a renamed or deleted point turns the case red instead of orphaning it;
* the fixture that carries the case is a carrier of at least one vector the
  decision point names, so dropping the id into an unrelated fixture does not
  count;
* the case actually asserts something -- it carries a name and a non-empty
  ``expected`` -- so an empty case is not a pass;
* the carrier declares a runner, and a ``named_suite`` runner declares a
  tool-neutral ``ak.suite.*.v1`` entrypoint, so an unloadable suite is not a pass;
* every decision point in the contract is reached by at least one case, unless it
  is recorded in the shrink-only ``decision_point_case_ratchet``.

What the check deliberately does not do is read the requirement sentence or the
case body for meaning. A case whose ``expected`` asserts the wrong thing in
fluent English still passes here; that is what review at registration time is
for. The gate catches structural mismatch -- missing, misfiled, empty, unrunnable
or stale -- and nothing else, and the rule text in the contract says so.
"""

from __future__ import annotations

from .core import (
    ARTIFACTS,
    Any,
    Lint,
    Path,
    load_json,
    re,
)
from .evidence_sets import check_closed_evidence_set

CASE_REF_RE = re.compile(r"^(AK-SDK-\d{3})/([a-z0-9_]+)$")
SUITE_ENTRYPOINT_RE = re.compile(r"^ak\.suite\.[a-z0-9_.-]+\.v1$")
FIXTURE_REF_RE = re.compile(r"^fixtures/[a-z0-9][a-z0-9_.-]*\.json$")
MIN_OWNER_REPORT_LENGTH = 8


def _contract_path() -> Path:
    return ARTIFACTS / "profiles" / "conformance-profiles.json"


def _vector_registry_path() -> Path:
    return ARTIFACTS / "registry" / "vector-registry.json"


def _fixtures_dir() -> Path:
    return ARTIFACTS / "fixtures"


def _fixture_carriers(vector: dict[str, Any]) -> set[str]:
    """Fixture file names that carry ``vector``, by either indexing convention."""
    carriers = {name for name in vector.get("applies_to_fixtures", []) if isinstance(name, str)}
    for ref in vector.get("source_refs", []):
        if isinstance(ref, str) and "/artifacts/fixtures/" in ref:
            carriers.add(ref.rsplit("/", 1)[-1])
    return carriers


def _iter_nodes(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        found.append(value)
        for child in value.values():
            found.extend(_iter_nodes(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_iter_nodes(child))
    return found


def _is_non_empty(value: Any) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, (str, list, dict, tuple, set)):
        return bool(value)
    return True


def _expand(declared: Any, vectors: dict[str, dict[str, Any]]) -> set[str]:
    """The clause's vector set, expanding a trailing ``.*`` family."""
    expanded: set[str] = set()
    if not isinstance(declared, list):
        return expanded
    for entry in declared:
        if not isinstance(entry, str):
            continue
        if entry.endswith(".*"):
            prefix = entry[:-1]
            expanded |= {name for name in vectors if name.startswith(prefix)}
            continue
        if entry in vectors:
            expanded.add(entry)
    return expanded


def check_sdk_decision_point_cases(lint: Lint) -> None:
    """Prove every SDK decision point reaches a runnable fixture case."""
    contract_document = load_json(lint, _contract_path())
    vector_document = load_json(lint, _vector_registry_path())
    if not isinstance(contract_document, dict) or not isinstance(vector_document, dict):
        return
    contract = contract_document.get("sdk_conformance_contract")
    if not isinstance(contract, dict):
        return

    rule = contract.get("decision_point_case_rule")
    if not isinstance(rule, str) or not rule.strip():
        lint.fail(
            _contract_path(),
            "sdk_conformance_contract.decision_point_case_rule must state what a fixture case has "
            "to carry for a decision point to count as reached",
        )
    ratchet_rule = contract.get("decision_point_case_ratchet_rule")
    if not isinstance(ratchet_rule, str) or not ratchet_rule.strip():
        lint.fail(
            _contract_path(),
            "sdk_conformance_contract.decision_point_case_ratchet_rule must state that the list "
            "only shrinks and what a row means",
        )
    ceiling_rule = contract.get("decision_point_case_ratchet_ceiling_rule")
    if not isinstance(ceiling_rule, str) or not ceiling_rule.strip():
        lint.fail(
            _contract_path(),
            "sdk_conformance_contract.decision_point_case_ratchet_ceiling_rule must state what "
            "the frozen baseline is and what widening it costs",
        )

    # Only active rows route a decision point to a carrier. A vector that
    # leaves the active set stops carrying anything, so a clause still leaning
    # on it goes red here instead of staying green on a row the conformance
    # suite no longer runs.
    vectors = {
        entry["vector_id"]: entry
        for entry in vector_document.get("vectors", [])
        if isinstance(entry, dict)
        and isinstance(entry.get("vector_id"), str)
        and entry.get("status") == "active"
    }

    # clause/point -> the fixture names allowed to carry a case for it.
    allowed_carriers: dict[tuple[str, str], set[str]] = {}
    declared_points: set[tuple[str, str]] = set()
    required_case_refs: dict[tuple[str, str], Any] = {}
    clauses = contract.get("clauses")
    if not isinstance(clauses, list):
        return
    for clause in clauses:
        if not isinstance(clause, dict):
            continue
        clause_id = clause.get("clause_id")
        evidence = clause.get("vector_evidence")
        if not isinstance(clause_id, str) or not isinstance(evidence, dict):
            continue
        expanded = _expand(evidence.get("vectors"), vectors)
        points = evidence.get("decision_points")
        if not isinstance(points, list):
            continue
        for point in points:
            if not isinstance(point, dict):
                continue
            point_id = point.get("id")
            if not isinstance(point_id, str):
                continue
            key = (clause_id, point_id)
            declared_points.add(key)
            if "required_case_refs" in point:
                required_case_refs[key] = point.get("required_case_refs")
            carriers: set[str] = set()
            point_vectors = point.get("vectors")
            if isinstance(point_vectors, list):
                for entry in point_vectors:
                    if isinstance(entry, str) and entry in expanded:
                        carriers |= _fixture_carriers(vectors[entry])
            allowed_carriers[key] = carriers

    # "Only shrinks" is not something prose can enforce: a list cannot tell a
    # removed row from a newly added one. The ceiling is the controlled baseline
    # that can -- the frozen set of pairs the ratchet was ever allowed to hold.
    # Widening it is possible and deliberately expensive, because the ceiling
    # lives inside sdk_conformance_contract, so editing it moves contract_digest
    # and invalidates the signed claim fixture.
    ceiling = contract.get("decision_point_case_ratchet_ceiling")
    ceiling_keys: set[tuple[str, str]] = set()
    if not isinstance(ceiling, list):
        lint.fail(
            _contract_path(),
            "decision_point_case_ratchet_ceiling must be a list, even when it is empty",
        )
    else:
        for index, entry in enumerate(ceiling):
            where = f"decision_point_case_ratchet_ceiling[{index}]"
            if not isinstance(entry, dict):
                lint.fail(_contract_path(), f"{where} must be an object")
                continue
            clause_id = entry.get("clause_id")
            point_id = entry.get("decision_point_id")
            if not isinstance(clause_id, str) or not isinstance(point_id, str):
                lint.fail(
                    _contract_path(),
                    f"{where} must name a clause_id and a decision_point_id",
                )
                continue
            if (clause_id, point_id) in ceiling_keys:
                lint.fail(_contract_path(), f"{where} duplicates {clause_id}/{point_id}")
            ceiling_keys.add((clause_id, point_id))

    ratchet = contract.get("decision_point_case_ratchet")
    if not isinstance(ratchet, list):
        lint.fail(_contract_path(), "decision_point_case_ratchet must be a list")
        ratchet = []
    ratchet_keys: set[tuple[str, str]] = set()
    for index, entry in enumerate(ratchet):
        where = f"decision_point_case_ratchet[{index}]"
        if not isinstance(entry, dict):
            lint.fail(_contract_path(), f"{where} must be an object")
            continue
        clause_id = entry.get("clause_id")
        point_id = entry.get("decision_point_id")
        if not isinstance(clause_id, str) or not isinstance(point_id, str):
            lint.fail(
                _contract_path(),
                f"{where} must name a clause_id and a decision_point_id",
            )
            continue
        key = (clause_id, point_id)
        if key in ratchet_keys:
            lint.fail(_contract_path(), f"{where} duplicates {clause_id}/{point_id}")
        ratchet_keys.add(key)
        owner = entry.get("owner_report")
        if not isinstance(owner, str) or len(owner.strip()) < MIN_OWNER_REPORT_LENGTH:
            lint.fail(
                _contract_path(),
                f"{where} must name the report that owns the gap",
            )
        if key not in declared_points:
            lint.fail(
                _contract_path(),
                f"{where} lists {clause_id}/{point_id}, which the contract no longer declares; "
                f"the ratchet only shrinks",
            )
        if isinstance(ceiling, list) and key not in ceiling_keys:
            lint.fail(
                _contract_path(),
                f"{where} adds {clause_id}/{point_id}, which the frozen "
                f"decision_point_case_ratchet_ceiling does not contain; the ratchet only shrinks, "
                f"so a new gap needs the ceiling widened and the claim re-signed, not one more row",
            )

    covered: set[tuple[str, str]] = set()
    case_index: dict[tuple[str, str], dict[str, Any]] = {}
    runner_ready: dict[str, bool] = {}
    for fixture_path in sorted(_fixtures_dir().glob("*.json")):
        fixture = load_json(lint, fixture_path)
        if not isinstance(fixture, dict):
            continue
        nodes = [node for node in _iter_nodes(fixture) if "covers_decision_points" in node]
        if not nodes:
            continue
        fixture_ref = f"fixtures/{fixture_path.name}"
        runner = fixture.get("runner")
        fixture_runner_ready = True
        if not isinstance(runner, dict):
            lint.fail(
                fixture_path,
                "carries decision point cases but declares no runner, so nothing states how the "
                "cases execute",
            )
            fixture_runner_ready = False
        elif runner.get("kind") == "named_suite":
            entrypoint = runner.get("entrypoint")
            if not isinstance(entrypoint, str) or not SUITE_ENTRYPOINT_RE.match(entrypoint):
                lint.fail(
                    fixture_path,
                    "carries decision point cases under runner.kind=named_suite but declares no "
                    "tool-neutral ak.suite.*.v1 entrypoint",
                )
                fixture_runner_ready = False
        runner_ready[fixture_ref] = fixture_runner_ready
        seen_names: set[str] = set()
        for node in nodes:
            refs = node.get("covers_decision_points")
            name = node.get("name")
            label = name if isinstance(name, str) and name else "<unnamed>"
            if not isinstance(name, str) or not name.strip():
                lint.fail(
                    fixture_path,
                    "a decision point case must carry a name so a reviewer can point at it",
                )
            elif name in seen_names:
                lint.fail(fixture_path, f"decision point case name duplicates {name}")
            else:
                seen_names.add(name)
                case_index[(fixture_ref, name)] = node
            if not _is_non_empty(node.get("expected")):
                lint.fail(
                    fixture_path,
                    f"decision point case {label} carries no non-empty expected result, so it "
                    f"asserts nothing",
                )
            if not isinstance(refs, list) or not refs:
                lint.fail(
                    fixture_path,
                    f"decision point case {label}.covers_decision_points must be a non-empty list",
                )
                continue
            for ref in refs:
                if not isinstance(ref, str) or not CASE_REF_RE.match(ref):
                    lint.fail(
                        fixture_path,
                        f"decision point case {label} holds a malformed reference: {ref!r}; the "
                        f"shape is \"<clause_id>/<decision_point_id>\"",
                    )
                    continue
                clause_id, point_id = CASE_REF_RE.match(ref).groups()  # type: ignore[union-attr]
                key = (clause_id, point_id)
                if key not in declared_points:
                    lint.fail(
                        fixture_path,
                        f"decision point case {label} names {ref}, which the SDK clause contract "
                        f"does not declare",
                    )
                    continue
                if fixture_path.name not in allowed_carriers.get(key, set()):
                    lint.fail(
                        fixture_path,
                        f"decision point case {label} names {ref}, but this fixture carries none "
                        f"of that decision point's vectors; a case only counts in a carrier of the "
                        f"vector it claims to exercise",
                    )
                    continue
                covered.add(key)

    for key, references in sorted(required_case_refs.items()):
        clause_id, point_id = key
        point_ref = f"{clause_id}/{point_id}"
        label = f"{clause_id}.{point_id}.required_case_refs"

        def parse_required_ref(reference: Any) -> tuple[tuple[str, str] | None, str | None]:
            if not isinstance(reference, dict) or set(reference) != {"fixture_ref", "case_id"}:
                return None, "must be an object with exactly fixture_ref and case_id"
            fixture_ref = reference.get("fixture_ref")
            case_id = reference.get("case_id")
            if not isinstance(fixture_ref, str) or not FIXTURE_REF_RE.fullmatch(fixture_ref):
                return None, "fixture_ref must be an artifacts-relative fixtures/*.json path"
            if not isinstance(case_id, str) or not case_id.strip():
                return None, "case_id must be a non-empty exact case name"
            return (fixture_ref, case_id), None

        def resolve_required_ref(reference: Any, parsed: object) -> str | None:
            assert isinstance(parsed, tuple) and len(parsed) == 2
            fixture_ref, case_id = parsed
            assert isinstance(fixture_ref, str) and isinstance(case_id, str)
            target = case_index.get((fixture_ref, case_id))
            if target is None:
                return f"does not resolve to a covered fixture case: {fixture_ref}#{case_id}"
            if not runner_ready.get(fixture_ref, False):
                return f"names {fixture_ref}#{case_id}, whose fixture has no valid registered runner"
            refs = target.get("covers_decision_points")
            if not isinstance(refs, list) or point_ref not in refs:
                return f"names a case that does not cover {point_ref}: {fixture_ref}#{case_id}"
            if not _is_non_empty(target.get("expected")):
                return f"names a case with no non-empty expected result: {fixture_ref}#{case_id}"
            fixture_name = fixture_ref.removeprefix("fixtures/")
            if fixture_name not in allowed_carriers.get(key, set()):
                return f"names {fixture_ref}#{case_id}, which carries none of the point's vectors"
            return None

        check_closed_evidence_set(
            lint,
            _contract_path(),
            label,
            references,
            empty_error=f"{label} must be a non-empty closed list",
            parse=parse_required_ref,
            resolve=resolve_required_ref,
        )

    for clause_id, point_id in sorted(declared_points):
        key = (clause_id, point_id)
        if key in covered:
            if key in ratchet_keys:
                lint.fail(
                    _contract_path(),
                    f"decision_point_case_ratchet still lists {clause_id}/{point_id}, which now "
                    f"has a fixture case; the ratchet only shrinks",
                )
            continue
        if key in ratchet_keys:
            continue
        lint.fail(
            _contract_path(),
            f"{clause_id}.{point_id} is reached by no fixture case and "
            f"decision_point_case_ratchet does not record it",
        )
