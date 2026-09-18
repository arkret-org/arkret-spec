"""Artifact lint phase 4: executable security evidence closure.

Successor to the aggregate ``security-closure-fixture.json`` check that
``c473e3c4`` unwired without replacement. The obligation set is no longer a
hardcoded Python allowlist: it is whatever ``normative-clause-registry.json``
registers under ``coverage_scope.executable_fixture_categories``. Every such
clause MUST name active vectors, every named vector MUST be carried by a
fixture that declares a ``security_evidence`` entry for it, and that entry MUST
map each decision point of the obligation onto evidence that actually resolves
inside the fixture.
"""

from __future__ import annotations

from .core import (
    ARTIFACTS,
    Any,
    Lint,
    Path,
    ROOT,
    VECTOR_ID_TOKEN_RE,
    load_json,
    re,
)

CLAUSE_ID_RE = re.compile(r"^AK-NC-\d{3}$")
DECISION_POINT_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def _resolve_pointer(document: Any, pointer: str) -> Any:
    """Resolve an RFC 6901 JSON Pointer, returning ``None`` when it misses."""
    if pointer == "":
        return document
    if not pointer.startswith("/"):
        return None
    current = document
    for raw_token in pointer[1:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            if token not in current:
                return None
            current = current[token]
        elif isinstance(current, list):
            if not token.isdigit():
                return None
            index = int(token)
            if index >= len(current):
                return None
            current = current[index]
        else:
            return None
    return current


def _collect_security_evidence(
    lint: Lint,
) -> tuple[dict[str, tuple[Path, dict[str, Any], dict[str, Any]]], bool]:
    """Index every declared ``security_evidence`` entry by vector id."""
    carriers: dict[str, tuple[Path, dict[str, Any], dict[str, Any]]] = {}
    ok = True
    for path in sorted((ARTIFACTS / "fixtures").glob("*.json")):
        data = load_json(lint, path)
        if not isinstance(data, dict):
            continue
        entries = data.get("security_evidence")
        if entries is None:
            continue
        if not isinstance(entries, list) or not entries:
            lint.fail(path, "security_evidence must be a non-empty array when present")
            ok = False
            continue

        runner = data.get("runner")
        if not isinstance(runner, dict) or runner.get("kind") != "named_suite":
            lint.fail(
                path,
                "a fixture declaring security_evidence must be a runner.kind=named_suite "
                "fixture so the certifier can map the suite to an executed entrypoint",
            )
            ok = False
        covers = data.get("covers_vectors")
        if not isinstance(covers, list):
            covers = []

        for index, entry in enumerate(entries):
            label = f"security_evidence[{index}]"
            if not isinstance(entry, dict):
                lint.fail(path, f"{label} must be an object")
                ok = False
                continue
            vector_id = entry.get("vector_id")
            if not isinstance(vector_id, str) or not VECTOR_ID_TOKEN_RE.fullmatch(vector_id):
                lint.fail(path, f"{label}.vector_id must be a conformance vector id")
                ok = False
                continue
            if vector_id in carriers:
                other = carriers[vector_id][0]
                lint.fail(
                    path,
                    f"{label}.vector_id {vector_id} already carries security evidence in "
                    f"{other.name}; one vector has exactly one evidence carrier",
                )
                ok = False
                continue
            carriers[vector_id] = (path, data, entry)

            if vector_id not in covers:
                lint.fail(path, f"{label}.vector_id {vector_id} must also appear in covers_vectors")
                ok = False
            clause_id = entry.get("clause_id")
            if not isinstance(clause_id, str) or not CLAUSE_ID_RE.fullmatch(clause_id):
                lint.fail(path, f"{label}.clause_id must match AK-NC-NNN")
                ok = False
            if not _check_decision_points(lint, path, data, label, entry):
                ok = False
    return carriers, ok


def _check_decision_points(
    lint: Lint,
    path: Path,
    document: dict[str, Any],
    label: str,
    entry: dict[str, Any],
) -> bool:
    points = entry.get("decision_points")
    if not isinstance(points, list) or not points:
        lint.fail(path, f"{label}.decision_points must be a non-empty array")
        return False

    ok = True
    seen: set[str] = set()
    for index, point in enumerate(points):
        point_label = f"{label}.decision_points[{index}]"
        if not isinstance(point, dict):
            lint.fail(path, f"{point_label} must be an object")
            ok = False
            continue
        point_id = point.get("id")
        if not isinstance(point_id, str) or not DECISION_POINT_ID_RE.fullmatch(point_id):
            lint.fail(path, f"{point_label}.id must be a snake_case identifier")
            ok = False
        elif point_id in seen:
            lint.fail(path, f"{point_label}.id duplicates {point_id}")
            ok = False
        else:
            seen.add(point_id)
        requirement = point.get("requirement")
        if not isinstance(requirement, str) or len(requirement.strip()) < 16:
            lint.fail(
                path,
                f"{point_label}.requirement must state the obligation this evidence discharges",
            )
            ok = False

        evidence = point.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            lint.fail(path, f"{point_label}.evidence must be a non-empty array of JSON Pointers")
            ok = False
            continue
        for pointer_index, pointer in enumerate(evidence):
            pointer_label = f"{point_label}.evidence[{pointer_index}]"
            if not isinstance(pointer, str) or not pointer.startswith("/"):
                lint.fail(path, f"{pointer_label} must be a JSON Pointer into this fixture")
                ok = False
                continue
            target = _resolve_pointer(document, pointer)
            if target is None or (isinstance(target, (dict, list, str)) and not target):
                lint.fail(path, f"{pointer_label} does not resolve to fixture content: {pointer}")
                ok = False
                continue
            if pointer.startswith("/cases/") and isinstance(target, dict):
                assertions = target.get("assertions")
                if (
                    not isinstance(assertions, list)
                    or not assertions
                    or not all(isinstance(item, str) and item.strip() for item in assertions)
                ):
                    lint.fail(
                        path,
                        f"{pointer_label} names a case without per-case assertions: {pointer}. "
                        "A case that states no expected observation proves nothing.",
                    )
                    ok = False
    return ok


def check_security_evidence_closure(lint: Lint) -> None:
    clause_path = ARTIFACTS / "registry" / "normative-clause-registry.json"
    clause_data = load_json(lint, clause_path)
    if not isinstance(clause_data, dict):
        return

    coverage_scope = clause_data.get("coverage_scope")
    if not isinstance(coverage_scope, dict):
        lint.fail(clause_path, "coverage_scope must be an object")
        return
    gated = coverage_scope.get("executable_fixture_categories")
    if not isinstance(gated, list) or not gated or not all(isinstance(item, str) and item for item in gated):
        lint.fail(
            clause_path,
            "coverage_scope.executable_fixture_categories must be a non-empty string array "
            "naming the clause categories whose evidence MUST be executable",
        )
        return
    included = coverage_scope.get("included_categories")
    if isinstance(included, list):
        for category in gated:
            if category not in included:
                lint.fail(
                    clause_path,
                    f"coverage_scope.executable_fixture_categories names {category}, "
                    "which is not in included_categories",
                )
    if not isinstance(coverage_scope.get("executable_fixture_rule"), str):
        lint.fail(
            clause_path,
            "coverage_scope.executable_fixture_rule must state, in the registry itself, what "
            "the executable evidence obligation is",
        )
    if not isinstance(coverage_scope.get("executable_evidence_exemption_rule"), str):
        lint.fail(
            clause_path,
            "coverage_scope.executable_evidence_exemption_rule must state, in the registry itself, "
            "that the exemption list only shrinks",
        )

    vector_path = ARTIFACTS / "registry" / "vector-registry.json"
    vector_data = load_json(lint, vector_path)
    active_vectors: dict[str, dict[str, Any]] = {}
    if isinstance(vector_data, dict) and isinstance(vector_data.get("vectors"), list):
        for row in vector_data["vectors"]:
            if isinstance(row, dict) and isinstance(row.get("vector_id"), str):
                if row.get("status", "active") == "active":
                    active_vectors[row["vector_id"]] = row

    carriers, _ = _collect_security_evidence(lint)

    gated_categories = set(gated)
    clauses = clause_data.get("clauses")
    if not isinstance(clauses, list):
        return

    clause_by_id: dict[str, dict[str, Any]] = {}
    required_vectors: dict[str, str] = {}
    for clause in clauses:
        if not isinstance(clause, dict):
            continue
        clause_id = clause.get("clause_id")
        if isinstance(clause_id, str):
            clause_by_id[clause_id] = clause
        if clause.get("status") != "active":
            continue
        if clause.get("category") not in gated_categories:
            continue
        if clause.get("testability_grade") != "vector":
            continue
        evidence_refs = clause.get("evidence_refs")
        if not isinstance(evidence_refs, list):
            continue
        for vector_id in evidence_refs:
            if isinstance(vector_id, str):
                required_vectors.setdefault(vector_id, clause_id if isinstance(clause_id, str) else "")

    exemptions = coverage_scope.get("executable_evidence_exemptions")
    if not isinstance(exemptions, list):
        lint.fail(
            clause_path,
            "coverage_scope.executable_evidence_exemptions must be an array; use [] when the gap is closed",
        )
        exemptions = []
    exempt_pairs: set[tuple[str, str]] = set()
    for index, row in enumerate(exemptions):
        label = f"coverage_scope.executable_evidence_exemptions[{index}]"
        if not isinstance(row, dict):
            lint.fail(clause_path, f"{label} must be an object")
            continue
        clause_id = row.get("clause_id")
        vector_id = row.get("vector_id")
        if not isinstance(clause_id, str) or not CLAUSE_ID_RE.fullmatch(clause_id):
            lint.fail(clause_path, f"{label}.clause_id must match AK-NC-NNN")
            continue
        if not isinstance(vector_id, str) or not VECTOR_ID_TOKEN_RE.fullmatch(vector_id):
            lint.fail(clause_path, f"{label}.vector_id must be a conformance vector id")
            continue
        if not isinstance(row.get("reason"), str) or not row["reason"].strip():
            lint.fail(clause_path, f"{label}.reason must say why the obligation has no executable evidence")
        if (clause_id, vector_id) in exempt_pairs:
            lint.fail(clause_path, f"{label} duplicates {clause_id}/{vector_id}")
            continue
        exempt_pairs.add((clause_id, vector_id))
        if required_vectors.get(vector_id) != clause_id:
            lint.fail(
                clause_path,
                f"{label} names {clause_id}/{vector_id}, which is not an active gated clause obligation; "
                "an exemption may only name a pair the gate would otherwise require",
            )
            continue
        if vector_id in carriers:
            lint.fail(
                clause_path,
                f"{label} exempts {vector_id}, but it now has a security_evidence carrier in "
                f"{carriers[vector_id][0].name}; the exemption list only shrinks, so remove this row",
            )

    for vector_id, clause_id in sorted(required_vectors.items()):
        if (clause_id, vector_id) in exempt_pairs:
            continue
        if vector_id not in active_vectors:
            lint.fail(
                clause_path,
                f"{clause_id} names {vector_id}, which is not an active vector in vector-registry.json",
            )
            continue
        carrier = carriers.get(vector_id)
        if carrier is None:
            lint.fail(
                clause_path,
                f"{clause_id} is in an executable-evidence category but {vector_id} has no fixture "
                "declaring a security_evidence entry for it",
            )
            continue
        fixture_path, _, entry = carrier
        if entry.get("clause_id") != clause_id:
            lint.fail(
                fixture_path,
                f"security_evidence for {vector_id} names clause {entry.get('clause_id')!r} "
                f"but the registry binds it to {clause_id}",
            )
        refs = active_vectors[vector_id].get("source_refs")
        rel = fixture_path.relative_to(ROOT).as_posix()
        if isinstance(refs, list) and rel not in refs:
            lint.fail(
                vector_path,
                f"{vector_id} carries security evidence in {fixture_path.name}; source_refs must index it",
            )

    for vector_id, (fixture_path, _, entry) in sorted(carriers.items()):
        clause_id = entry.get("clause_id")
        if not isinstance(clause_id, str) or not CLAUSE_ID_RE.fullmatch(clause_id):
            continue
        clause = clause_by_id.get(clause_id)
        if clause is None:
            lint.fail(fixture_path, f"security_evidence names unknown clause {clause_id}")
            continue
        if clause.get("status") != "active":
            lint.fail(fixture_path, f"security_evidence names clause {clause_id}, which is not active")
        evidence_refs = clause.get("evidence_refs")
        if not isinstance(evidence_refs, list) or vector_id not in evidence_refs:
            lint.fail(
                fixture_path,
                f"security_evidence claims {vector_id} discharges {clause_id}, but that clause "
                "does not list the vector in evidence_refs",
            )


__all__ = ["check_security_evidence_closure"]
