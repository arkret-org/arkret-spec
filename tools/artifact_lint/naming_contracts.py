"""Artifact lint: naming rule coverage matrix and identifier value categories.

Two contracts live here, both of which exist because "the walker reached every
property" is not the same statement as "every normative naming clause is
enforced":

1. ``check_naming_rule_coverage_matrix`` reads
   ``tools/naming-rule-coverage-matrix.json`` and proves, per rule, that the
   enforcement it claims is real: the named predicate is in the executed
   predicate table, the named functions are defined in this package, the named
   registries exist, and the function is reachable in the static call graph from
   a check that ``artifact_lint.runner.main`` actually registers. A row that
   names a function nobody calls is the exact failure mode the matrix exists to
   prevent, so reachability is computed rather than declared.
2. ``check_identifier_value_categories`` decides, from the resolved schema
   terminal constraint, which identifier value category every ``id`` / ``*_id``
   / ``*_ids`` wire property carries. Occurrences the type system decides on its
   own are never written down: duplicating an obvious ``$ref`` into a hand-kept
   table just creates a second truth that drifts. Only occurrences the type
   system cannot decide enter
   ``tools/identifier-classification-registry.json``, and that registry is
   closed in both directions against the category table in
   ``common-fields.md`` 2.1.
"""

from __future__ import annotations

import ast
import functools

from .core import (
    ARTIFACTS,
    Any,
    Lint,
    Path,
    ROOT,
    SPEC_ROOT,
    TOOLS_ROOT,
    json,
    load_json,
    re,
    read_text,
    resolve_json_pointer,
)
from .naming import (
    EXTERNAL_ANCHOR_URL_RE,
    EXTERNAL_LITERAL_OBJECT_FIELDS,
    EXTERNAL_LITERAL_OBJECT_KEYWORD,
    PREDICATES,
    TYPED_ID_NAMESPACE_PREFIX,
    enumerate_property_owners,
    enumerate_schema_properties,
    nc_fieldcase_001,
    split_name_words,
    terminal_excludes_typed_id_namespace,
)

NAMING_COVERAGE_MATRIX_PATH = TOOLS_ROOT / "naming-rule-coverage-matrix.json"
IDENTIFIER_CLASSIFICATION_PATH = TOOLS_ROOT / "identifier-classification-registry.json"
SLUG_FIELD_REGISTRY_PATH = TOOLS_ROOT / "slug-field-registry.json"
ROLE_SUFFIX_REGISTRY_PATH = TOOLS_ROOT / "identifier-role-suffix-registry.json"
COLLECTION_NAMING_REGISTRY_PATH = TOOLS_ROOT / "collection-naming-registry.json"
NAMING_RULES_FILE = TOOLS_ROOT / "naming-convention-rules.json"
ID_KIND_REGISTRY_PATH = ARTIFACTS / "registry" / "id-kind-registry.json"
COMMON_FIELDS_PATH = SPEC_ROOT / "zh" / "models" / "common-fields.md"
SCHEMA_DIR = ARTIFACTS / "schemas"
PACKAGE_DIR = Path(__file__).resolve().parent

ENFORCEMENT_KINDS = frozenset(
    {"predicate", "registry_closure", "schema_type", "prose_only", "uncovered"}
)
COVERAGE_LEVELS = frozenset({"full", "partial"})
MECHANICAL_ENFORCEMENT_KINDS = frozenset({"predicate", "registry_closure", "schema_type"})

IDENTIFIER_CATEGORY_MARKER_RE = re.compile(r"identifier_category:\s*([a-z_]+)")
SECTION_HEADING_PREFIX = "^#{1,6}[ \t]+"
SECTION_HEADING_SUFFIX = "[ \t　]"

# Identifier-bearing wire property names. `_ref` / `_refs` are a different
# contract (2.1.2) and are deliberately out of scope here.
IDENTIFIER_NAME_SUFFIXES = ("_id", "_ids")

# NC-IDROLE-001.  A role stem answers "what does this identity do?" while the
# suffix answers "what representation is on the wire?".  Entity/deployment
# classes (service, human, organization, agent) are validation facts and are
# not inserted between those two axes.  The only retained `service` stems are
# protocol roles in their own right rather than class qualifiers.
# The two value categories whose values legitimately live in the `ak:` typed-ID
# namespace. Every other category MUST stay lexically disjoint from it, which is
# the half of 2.1 the typed-ID prefix closure cannot see: that closure only asks
# whether an `ak:<kind>:` it finds is registered.
TYPED_ID_NAMESPACE_OWNER_CATEGORIES = frozenset({"typed_object_id", "responsibility_identity_material"})


# --------------------------------------------------------------------------
# Static reachability. A coverage row may not certify itself; the proof that a
# check runs has to come from the module that builds the phase lists.
# --------------------------------------------------------------------------


@functools.lru_cache(maxsize=1)
def _package_trees() -> dict[str, ast.Module]:
    trees: dict[str, ast.Module] = {}
    for path in sorted(PACKAGE_DIR.glob("*.py")):
        trees[path.name] = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return trees


@functools.lru_cache(maxsize=1)
def _definition_index() -> dict[str, set[str]]:
    """Map function name to the set of package modules that define it."""

    index: dict[str, set[str]] = {}
    for module_name, tree in _package_trees().items():
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                index.setdefault(node.name, set()).add(module_name)
    return index


def _called_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        target = child.func
        if isinstance(target, ast.Name):
            names.add(target.id)
        elif isinstance(target, ast.Attribute):
            names.add(target.attr)
    return names


@functools.lru_cache(maxsize=1)
def _call_graph() -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {}
    for tree in _package_trees().values():
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                graph.setdefault(node.name, set()).update(_called_names(node))
    return graph


@functools.lru_cache(maxsize=1)
def _runner_entry_points() -> dict[str, str]:
    """Map the runner's phase label to the check function it invokes.

    ``runner.main`` registers checks as ``("label", lambda: check_x(lint))``
    tuples, so the label-to-function mapping is recoverable statically and stays
    correct when the phase lists are reordered.
    """

    entries: dict[str, str] = {}
    tree = _package_trees().get("runner.py")
    if tree is None:
        return entries
    for node in ast.walk(tree):
        if not isinstance(node, ast.Tuple) or len(node.elts) != 2:
            continue
        label, factory = node.elts
        if not isinstance(label, ast.Constant) or not isinstance(label.value, str):
            continue
        if not isinstance(factory, ast.Lambda):
            continue
        body = factory.body
        if isinstance(body, ast.Call) and isinstance(body.func, ast.Name):
            entries[label.value] = body.func.id
    return entries


def _reachable_functions(entry_function: str) -> set[str]:
    graph = _call_graph()
    seen: set[str] = set()
    frontier = [entry_function]
    while frontier:
        current = frontier.pop()
        if current in seen:
            continue
        seen.add(current)
        frontier.extend(graph.get(current, ()))
    return seen


# --------------------------------------------------------------------------
# Coverage matrix
# --------------------------------------------------------------------------


def _heading_present(text: str, section: str) -> bool:
    pattern = SECTION_HEADING_PREFIX + re.escape(section) + SECTION_HEADING_SUFFIX
    return bool(re.search(pattern, text, re.M))


def check_naming_rule_coverage_matrix(lint: Lint) -> None:
    """Prove that every registered naming contract has the enforcement it claims."""

    data = load_json(lint, NAMING_COVERAGE_MATRIX_PATH)
    if not isinstance(data, dict):
        return
    if data.get("source_of_truth") is not False:
        lint.fail(
            NAMING_COVERAGE_MATRIX_PATH,
            "the coverage matrix is derived from prose and lint code, not a truth source",
        )
    rows = data.get("rules")
    if not isinstance(rows, list) or not rows:
        lint.fail(NAMING_COVERAGE_MATRIX_PATH, "rules must be a non-empty array")
        return

    entry_points = _runner_entry_points()
    definitions = _definition_index()
    prose_cache: dict[str, str] = {}
    seen_ids: set[str] = set()
    coverage_counts: dict[str, int] = {kind: 0 for kind in ENFORCEMENT_KINDS}
    predicate_rows: set[str] = set()

    for index, row in enumerate(rows):
        where = f"rules[{index}]"
        if not isinstance(row, dict):
            lint.fail(NAMING_COVERAGE_MATRIX_PATH, f"{where} must be an object")
            continue
        rule_id = row.get("rule_id")
        if not isinstance(rule_id, str) or not re.fullmatch(r"NC-[A-Z0-9]+-[0-9]{3}", rule_id):
            lint.fail(NAMING_COVERAGE_MATRIX_PATH, f"{where} needs a stable NC-<AXIS>-<NNN> rule_id")
            continue
        where = f"{rule_id}"
        if rule_id in seen_ids:
            lint.fail(NAMING_COVERAGE_MATRIX_PATH, f"{where} is registered twice")
            continue
        seen_ids.add(rule_id)

        if not isinstance(row.get("title"), str) or not row["title"].strip():
            lint.fail(NAMING_COVERAGE_MATRIX_PATH, f"{where} needs a title")

        anchor = row.get("normative_anchor")
        if not isinstance(anchor, dict):
            lint.fail(NAMING_COVERAGE_MATRIX_PATH, f"{where} needs a normative_anchor object")
        else:
            anchor_file = anchor.get("file")
            section = anchor.get("section")
            quote = anchor.get("quote")
            if not isinstance(anchor_file, str) or not (ROOT / anchor_file).exists():
                lint.fail(
                    NAMING_COVERAGE_MATRIX_PATH,
                    f"{where} anchors a file that does not exist: {anchor_file}",
                )
            elif not isinstance(section, str) or not isinstance(quote, str) or not quote:
                lint.fail(NAMING_COVERAGE_MATRIX_PATH, f"{where} needs anchor section and quote")
            else:
                text = prose_cache.get(anchor_file)
                if text is None:
                    text = read_text(ROOT / anchor_file)
                    prose_cache[anchor_file] = text
                if not _heading_present(text, section):
                    lint.fail(
                        NAMING_COVERAGE_MATRIX_PATH,
                        f"{where} anchors section {section}, which {anchor_file} no longer has",
                    )
                if quote not in text:
                    # The quote is the drift detector: a clause that was reworded
                    # or deleted must not keep a row claiming it is enforced.
                    lint.fail(
                        NAMING_COVERAGE_MATRIX_PATH,
                        f"{where} quotes text that is no longer in {anchor_file}: {quote!r}",
                    )

        surfaces = row.get("applies_to")
        if not isinstance(surfaces, list) or not surfaces or not all(
            isinstance(item, str) and item for item in surfaces
        ):
            lint.fail(NAMING_COVERAGE_MATRIX_PATH, f"{where} needs a non-empty applies_to list")

        enforcement_kind = row.get("enforcement_kind")
        if enforcement_kind not in ENFORCEMENT_KINDS:
            lint.fail(
                NAMING_COVERAGE_MATRIX_PATH,
                f"{where} enforcement_kind must be one of {sorted(ENFORCEMENT_KINDS)}",
            )
            continue
        coverage_counts[enforcement_kind] += 1

        coverage_level = row.get("coverage_level")
        if coverage_level not in COVERAGE_LEVELS:
            lint.fail(
                NAMING_COVERAGE_MATRIX_PATH,
                f"{where} coverage_level must be one of {sorted(COVERAGE_LEVELS)}",
            )

        enforced_by = row.get("enforced_by")
        if not isinstance(enforced_by, dict):
            lint.fail(NAMING_COVERAGE_MATRIX_PATH, f"{where} needs an enforced_by object")
            continue
        predicates = enforced_by.get("predicates", [])
        functions = enforced_by.get("functions", [])
        registries = enforced_by.get("registries", [])
        if not all(isinstance(value, list) for value in (predicates, functions, registries)):
            lint.fail(NAMING_COVERAGE_MATRIX_PATH, f"{where} enforced_by members must be arrays")
            continue

        for predicate in predicates:
            if predicate not in PREDICATES:
                lint.fail(
                    NAMING_COVERAGE_MATRIX_PATH,
                    f"{where} names predicate `{predicate}`, which the executed table does not have",
                )
        predicate_rows.update(name for name in predicates if isinstance(name, str))

        for registry in registries:
            if not isinstance(registry, str) or not (ROOT / registry).exists():
                lint.fail(
                    NAMING_COVERAGE_MATRIX_PATH,
                    f"{where} names registry `{registry}`, which does not exist",
                )

        entry_names = row.get("entry_points")
        if not isinstance(entry_names, list):
            lint.fail(NAMING_COVERAGE_MATRIX_PATH, f"{where} entry_points must be an array")
            entry_names = []
        unknown_entries = [name for name in entry_names if name not in entry_points]
        if unknown_entries:
            lint.fail(
                NAMING_COVERAGE_MATRIX_PATH,
                f"{where} names entry points the artifact-lint main entry does not register: "
                f"{sorted(unknown_entries)}",
            )
        reachable: set[str] = set()
        for name in entry_names:
            target = entry_points.get(name)
            if target:
                reachable |= _reachable_functions(target)

        for function in functions:
            if not isinstance(function, str) or ":" not in function:
                lint.fail(
                    NAMING_COVERAGE_MATRIX_PATH,
                    f"{where} functions must be `module.py:function` strings",
                )
                continue
            module_name, _, function_name = function.partition(":")
            modules = definitions.get(function_name, set())
            if module_name not in modules:
                lint.fail(
                    NAMING_COVERAGE_MATRIX_PATH,
                    f"{where} names `{function}`, which is not defined there",
                )
                continue
            if function_name not in reachable:
                lint.fail(
                    NAMING_COVERAGE_MATRIX_PATH,
                    f"{where} names `{function}`, which is not reachable from its declared "
                    f"entry points {sorted(entry_names)}",
                )

        if enforcement_kind in MECHANICAL_ENFORCEMENT_KINDS:
            if not functions and not registries:
                lint.fail(
                    NAMING_COVERAGE_MATRIX_PATH,
                    f"{where} claims mechanical enforcement without naming a function or registry",
                )
            if not entry_names:
                lint.fail(
                    NAMING_COVERAGE_MATRIX_PATH,
                    f"{where} claims mechanical enforcement without an entry point",
                )
        else:
            if functions or predicates:
                lint.fail(
                    NAMING_COVERAGE_MATRIX_PATH,
                    f"{where} is filed as {enforcement_kind} but names executable enforcement",
                )
            reason = row.get("manual_review_reason")
            if not isinstance(reason, str) or len(reason.strip()) < 24:
                lint.fail(
                    NAMING_COVERAGE_MATRIX_PATH,
                    f"{where} is {enforcement_kind} and MUST state, in manual_review_reason, why "
                    f"the clause is not mechanically enforced and what accepts the residual risk",
                )
            if coverage_level == "full":
                lint.fail(
                    NAMING_COVERAGE_MATRIX_PATH,
                    f"{where} cannot claim full coverage without mechanical enforcement",
                )

        tests = row.get("tests")
        if not isinstance(tests, list):
            lint.fail(NAMING_COVERAGE_MATRIX_PATH, f"{where} tests must be an array")
        else:
            for test in tests:
                if not isinstance(test, str) or not (ROOT / test).exists():
                    lint.fail(
                        NAMING_COVERAGE_MATRIX_PATH,
                        f"{where} names test `{test}`, which does not exist",
                    )
            if enforcement_kind == "predicate" and not tests:
                lint.fail(
                    NAMING_COVERAGE_MATRIX_PATH,
                    f"{where} is predicate-enforced and MUST name the mutation test that can fail it",
                )

    # The predicate table and the matrix are the same population seen from two
    # sides; either one growing alone means a rule is enforced but unregistered,
    # or registered but not executed.
    rules_data = load_json(lint, NAMING_RULES_FILE)
    if isinstance(rules_data, dict) and isinstance(rules_data.get("rules"), list):
        registered = {
            entry.get("rule_id")
            for entry in rules_data["rules"]
            if isinstance(entry, dict) and isinstance(entry.get("rule_id"), str)
        }
        if registered != predicate_rows:
            lint.fail(
                NAMING_COVERAGE_MATRIX_PATH,
                "predicate rows disagree with naming-convention-rules.json: "
                f"matrix-only={sorted(predicate_rows - registered)}, "
                f"rules-only={sorted(registered - predicate_rows)}",
            )

    summary = data.get("coverage_summary")
    if not isinstance(summary, dict) or summary != coverage_counts:
        lint.fail(
            NAMING_COVERAGE_MATRIX_PATH,
            f"coverage_summary is stale; recompute it as {coverage_counts}",
        )


# --------------------------------------------------------------------------
# Identifier value categories
# --------------------------------------------------------------------------


def check_wire_property_name_case(lint: Lint, documents: dict[str, Any]) -> None:
    """Close NC-FIELDCASE-001: every declared property name is snake_case.

    The one admissible exemption is an object that mirrors an external
    specification verbatim, and the object declares that itself through
    ``x-arkret-external-literal-object``. Keeping the fact in the schema rather
    than in a lint-side table is what makes the exemption exact: it covers the
    properties that node declares and cannot be inherited by a `$ref`, by another
    object of the same type name, or by a same-named property elsewhere.

    The annotation also establishes exact lexical ownership for external
    identifier-role literals whose names may already be snake_case (for example
    RFC 9457 ``instance``). Therefore a fully snake_case marked object is not
    inherently stale: the marker can still be consumed by NC-IDROLE-001, while
    its required specification, anchor, and reason keep the exception auditable.
    """

    reached: set[tuple[str, str]] = set()
    for file_name, document in documents.items():
        schema_path = SCHEMA_DIR / file_name
        for owner in enumerate_property_owners(file_name, document):
            marker = owner.node.get(EXTERNAL_LITERAL_OBJECT_KEYWORD)
            violations = [name for name in owner.names if nc_fieldcase_001(name)]
            reached |= {(owner.pointer, name) for name in owner.names}
            if marker is None:
                for name in violations:
                    lint.fail(
                        schema_path,
                        f"{owner.pointer}/properties/{name} violates NC-FIELDCASE-001 "
                        f"(`{name}` is not snake_case); an object that mirrors an external "
                        f"specification verbatim MUST declare "
                        f"{EXTERNAL_LITERAL_OBJECT_KEYWORD} on that exact node",
                    )
                continue
            if not owner.names:
                lint.fail(
                    schema_path,
                    f"{owner.pointer}/{EXTERNAL_LITERAL_OBJECT_KEYWORD} is a stale annotation: "
                    "the annotated object declares no properties",
                )
            if not isinstance(marker, dict):
                lint.fail(
                    schema_path,
                    f"{owner.pointer}/{EXTERNAL_LITERAL_OBJECT_KEYWORD} must be an object "
                    f"declaring {list(EXTERNAL_LITERAL_OBJECT_FIELDS)}",
                )
                continue
            unknown = sorted(set(marker) - set(EXTERNAL_LITERAL_OBJECT_FIELDS) - {"reason"})
            if unknown:
                lint.fail(
                    schema_path,
                    f"{owner.pointer}/{EXTERNAL_LITERAL_OBJECT_KEYWORD} declares unknown "
                    f"members {unknown}",
                )
            specification = marker.get("specification")
            if not isinstance(specification, str) or not specification.strip():
                lint.fail(
                    schema_path,
                    f"{owner.pointer}/{EXTERNAL_LITERAL_OBJECT_KEYWORD} must name the external "
                    f"specification whose lexicon governs these property names",
                )
            anchor = marker.get("anchor")
            if not isinstance(anchor, str) or not EXTERNAL_ANCHOR_URL_RE.fullmatch(anchor):
                # A bare specification name cannot be checked against anything; the
                # fragment is what pins the exemption to a section rather than to a
                # whole document.
                lint.fail(
                    schema_path,
                    f"{owner.pointer}/{EXTERNAL_LITERAL_OBJECT_KEYWORD}.anchor must be an "
                    f"https:// URL carrying the section fragment that defines these names",
                )
    # Walker duality. The owner walk and the occurrence walk are two views of one
    # population, so a regression in either one shrinks the judged surface without
    # failing anything unless they are compared.
    expected = {
        (occurrence.pointer.rsplit("/properties/", 1)[0], occurrence.name)
        for file_name, document in documents.items()
        for occurrence in enumerate_schema_properties(file_name, document)
    }
    if expected != reached:
        lint.fail(
            NAMING_RULES_FILE,
            "NC-FIELDCASE-001 owner walk disagrees with the property occurrence walk: "
            f"missing={sorted(expected - reached)[:5]}, extra={sorted(reached - expected)[:5]}",
        )


def check_typed_id_namespace_disjointness(
    lint: Lint,
    file_name: str,
    pointer: str,
    name: str,
    category: str | None,
    terminals: tuple[tuple[str, str], ...],
) -> None:
    """Close the other half of 2.1: non-typed categories may not reach into ``ak:``.

    ``check_typed_id_prefix_registry_closure`` only decides whether an ``ak:<kind>:``
    that appears in a schema is registered. Nothing asked the opposite question --
    whether a field that is *not* a typed ID can accept an ``ak:`` value anyway --
    and the answer used to be yes for every carrier whose character class merely
    happened to contain ``:``. A bounded terminal that carries no lexical
    information at all (a bare ``type``) cannot be decided here; those occurrences
    are the pending-convergence rows of the classification registry. ``category``
    is ``None`` when neither the type nor the registry classifies the occurrence;
    that is judged like any other non-owning category, because an occurrence
    nobody has classified cannot be assumed to own the namespace.
    """

    if category in TYPED_ID_NAMESPACE_OWNER_CATEGORIES:
        return
    where = f"category `{category}`" if category else "unclassified"
    verdicts = [terminal_excludes_typed_id_namespace(kind, value) for kind, value in terminals]
    for (kind, value), verdict in zip(terminals, verdicts):
        if verdict is False:
            lint.fail(
                SCHEMA_DIR / file_name,
                f"{pointer} is {where} but its {kind} `{value}` admits values in the "
                f"`{TYPED_ID_NAMESPACE_PREFIX}` typed-ID namespace; the 2.1 categories are "
                f"mutually exclusive, so the terminal constraint MUST reject them",
            )
    # Fail closed on "undecided". A terminal that carries no lexical information
    # at all (a bare `type: string`) used to pass here, so an occurrence nobody
    # could judge was silently treated as judged-clean while the schema still
    # accepted `ak:<any kind>:<any payload>`. 2.1 requires every non-owning
    # category to carry a `pattern` / `const` / closed `enum` that provably
    # rejects the prefix; `maxLength` bounds the length and proves nothing about
    # the namespace. An object-typed descriptor is not an identifier terminal, so
    # it has nothing to constrain.
    if any(verdict is True for verdict in verdicts):
        return
    if any(kind == "type" and value == '"object"' for kind, value in terminals):
        return
    lint.fail(
        SCHEMA_DIR / file_name,
        f"{pointer} is {where} and no terminal constraint proves it rejects the "
        f"`{TYPED_ID_NAMESPACE_PREFIX}` typed-ID namespace; a category that does not own that "
        f"namespace MUST carry a pattern / const / closed enum floor (the shared one is "
        f"string-profiles.schema.json#/$defs/non_typed_identifier_floor). Resolved terminals: "
        f"{list(terminals)}",
    )


def _schema_documents(lint: Lint) -> dict[str, Any]:
    documents: dict[str, Any] = {}
    for path in sorted(SCHEMA_DIR.glob("*.json")):
        document = load_json(lint, path)
        if document is not None:
            documents[path.name] = document
    return documents


def resolve_terminal_constraints(
    documents: dict[str, Any], file_name: str, shape: Any
) -> tuple[tuple[str, str], ...]:
    """Return the resolved terminal lexical constraints of a property shape.

    Local and cross-file ``$ref``, ``allOf`` / ``anyOf`` / ``oneOf`` and array
    ``items`` are followed so the classification sees the constraint that
    actually governs the value rather than the indirection in front of it. A
    bare ``"null"`` branch is dropped: nullability is not a value category.
    """

    seen: set[tuple[str, str]] = set()

    def visit(current_file: str, node: Any) -> set[tuple[str, str]]:
        out: set[tuple[str, str]] = set()
        if not isinstance(node, dict):
            return out
        if node.get("x-arkret-composite-identifier") is True:
            required = set(node.get("required", []))
            if {"principal_id", "station_id"} <= required:
                return {("account_id", "closed_object")}
            branches = node.get("oneOf", [])
            if any(
                isinstance(branch, dict)
                and branch.get("properties", {}).get("kind", {}).get("const")
                in {"account", "service"}
                for branch in branches
            ):
                return {("actor_id", "closed_object")}
            return {("composite_identifier", "closed_object")}
        ref = node.get("$ref")
        if isinstance(ref, str):
            target, separator, fragment = ref.partition("#")
            target_file = current_file if not target else Path(target).name
            edge = (target_file, ref)
            if edge in seen or target_file not in documents:
                return out
            seen.add(edge)
            try:
                resolved = resolve_json_pointer(
                    documents[target_file], f"#{fragment}" if separator else ""
                )
            except (KeyError, TypeError, ValueError):
                return out
            return visit(target_file, resolved)
        for keyword in ("allOf", "anyOf", "oneOf"):
            branches = node.get(keyword)
            if isinstance(branches, list):
                for branch in branches:
                    out |= visit(current_file, branch)
        if "items" in node:
            return out | visit(current_file, node["items"])
        if isinstance(node.get("pattern"), str):
            out.add(("pattern", node["pattern"]))
        elif "const" in node:
            out.add(("const", str(node["const"])))
        elif isinstance(node.get("enum"), list):
            out.add(("enum", "|".join(sorted(str(value) for value in node["enum"]))))
        if isinstance(node.get("format"), str):
            out.add(("format", node["format"]))
        elif not out and "type" in node:
            declared = node["type"]
            if declared != "null":
                out.add(("type", json.dumps(declared, sort_keys=True)))
        return out

    return tuple(sorted(visit(file_name, shape)))


def _shape_cardinalities(
    documents: dict[str, Any], file_name: str, shape: Any
) -> set[str]:
    """Resolve whether a property carries a scalar or an array value."""

    seen: set[tuple[str, str]] = set()

    def visit(current_file: str, node: Any) -> set[str]:
        if not isinstance(node, dict):
            return set()
        ref = node.get("$ref")
        if isinstance(ref, str):
            target, separator, fragment = ref.partition("#")
            target_file = current_file if not target else Path(target).name
            edge = (target_file, ref)
            if edge in seen or target_file not in documents:
                return set()
            seen.add(edge)
            try:
                resolved = resolve_json_pointer(
                    documents[target_file], f"#{fragment}" if separator else ""
                )
            except (KeyError, TypeError, ValueError):
                return set()
            return visit(target_file, resolved)
        if node.get("type") == "array" or "items" in node:
            return {"array"}
        out: set[str] = set()
        for keyword in ("allOf", "anyOf", "oneOf"):
            branches = node.get(keyword)
            if isinstance(branches, list):
                for branch in branches:
                    out |= visit(current_file, branch)
        declared = node.get("type")
        if declared is not None and declared != "null" and declared != "array":
            out.add("scalar")
        if any(key in node for key in ("pattern", "const", "enum", "format")):
            out.add("scalar")
        return out

    return visit(file_name, shape)


def _role_terminal_contract(
    terminals: tuple[tuple[str, str], ...], *, plural: bool
) -> tuple[str | None, str | None]:
    """Return a single resolved identifier category and its mandatory suffix.

    The decision is terminal-driven, not a role-name allowlist: a newly coined
    ``signer`` or ``counterparty`` must be subject to the same grammar as the
    historically familiar issuer/subject roles.
    """

    categories: set[tuple[str, str | None]] = set()
    for kind, value in terminals:
        if kind == "pattern" and value.startswith("^ak:did_core:"):
            categories.add(("did_core_id", "_ids" if plural else "_id"))
        elif kind == "pattern" and _AK_TYPED_PREFIX_RE.match(value):
            categories.add(("typed_object_id", "_ids" if plural else "_id"))
        elif kind == "pattern" and value.startswith("^did:"):
            # `did:<method>` / `did:<method>:` are method-selector tokens, not
            # DID identifiers.  They belong to the classification grammar.
            if value in {"^did:[a-z0-9]+$", "^did:[a-z0-9]+:$"}:
                continue
            if re.search(r"\][+*]\)?#|\}\+\)?#", value):
                categories.add(("did_url", "_kids" if plural else "_kid"))
            else:
                categories.add(("did", "_dids" if plural else "_did"))
        elif kind == "format" and value in {"uri", "uri-reference"}:
            # URI syntax does not decide URL-vs-URI field spelling.  Network
            # locators and generic URI identities are registered separately.
            categories.add(("uri", None))
        elif kind in {"account_id", "actor_id", "composite_identifier"} and value == "closed_object":
            categories.add((kind, "_ids" if plural else "_id"))
    # JSON Schema commonly combines a broad URI format with a narrower DID or
    # DID-URL lexical pattern. The pattern owns the representation category in
    # that case; format remains decisive only when no narrower identifier
    # terminal was resolved.
    if len(categories) > 1:
        categories = {entry for entry in categories if entry[0] != "uri"}
    if len(categories) == 1:
        return next(iter(categories))
    if len(categories) > 1:
        names = ",".join(sorted(category for category, _ in categories))
        return f"mixed[{names}]", None
    return None, None


def _role_name_matches_terminal(
    name: str, category: str, suffix: str, grammars: list[dict[str, Any]]
) -> bool:
    """Whether an Arkret-owned property spells the resolved representation."""

    for grammar in grammars:
        if category not in grammar.get("terminal_categories", []):
            continue
        if name in grammar.get("exact_names", []):
            return True
        for registered_suffix in grammar.get("suffixes", []):
            if not name.endswith(registered_suffix):
                continue
            if registered_suffix in {
                "_id", "_ids", "_did", "_dids", "_kid", "_kids", "_uri", "_uris"
            }:
                return registered_suffix == suffix
            return True
    return False


def _role_stem(name: str, category: str) -> str:
    suffixes = {
        "did_core_id": ("_ids", "_id"),
        "typed_object_id": ("_ids", "_id"),
        "did": ("_dids", "_did"),
        "did_url": ("_verification_method", "_kids", "_kid"),
        "uri": ("_urls", "_uris", "_url", "_uri"),
    }.get(category, ())
    for suffix in suffixes:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


_DUPLICATE_REPRESENTATION_SUFFIX_RE = re.compile(
    r"(?:_id_id|_ids_ids|_did_did|_uri_uri|_url_url|_kid_kid)(?![a-z0-9_])"
)
_EMBEDDED_REPRESENTATION_SUFFIX_RE = re.compile(
    r"(?:^|_)(?:id|did|uri|url|kid)ship(?:_|$)"
)

_REPRESENTATION_SUFFIX_CATEGORIES = {
    "_ids": "identifier",
    "_id": "identifier",
    "_dids": "did",
    "_did": "did",
    "_uris": "uri",
    "_uri": "uri",
    "_urls": "uri",
    "_url": "uri",
    "_kids": "did_url",
    "_kid": "did_url",
}


def _declared_representation_suffix(name: str) -> str | None:
    for suffix in sorted(_REPRESENTATION_SUFFIX_CATEGORIES, key=len, reverse=True):
        if name.endswith(suffix):
            return suffix
    return None


_URI_SCHEME_PROBES = {
    "http": "http://example.test/path/",
    "https": "https://example.test/path/",
    "ws": "ws://example.test/path/",
    "wss": "wss://example.test/path/",
    "geo": "geo:0,0",
    "mimi": "mimi://example.test/room",
    "acct": "acct:user@example.test",
    "urn": "urn:example:value",
    "oci": "oci:example/value",
    "git": "git:example/value",
}


def _terminal_uri_schemes(terminals: tuple[tuple[str, str], ...]) -> set[str]:
    """Return schemes proven by URI-shaped regex terminals.

    A broad ``format: uri`` intentionally proves no network scheme.  URL
    fields must carry a lexical HTTP(S)/WS(S) constraint; URI identity fields
    may rely on either a URI format or a non-network scheme pattern.
    """

    schemes: set[str] = set()
    for kind, value in terminals:
        if kind != "pattern":
            continue
        if "https?://" in value:
            schemes.update({"http", "https"})
        for scheme in ("http", "https", "ws", "wss"):
            if f"{scheme}://" in value:
                schemes.add(scheme)
        for scheme, probe in _URI_SCHEME_PROBES.items():
            try:
                if re.search(value, probe):
                    schemes.add(scheme)
            except re.error:
                continue
    return schemes


def _has_uri_terminal(terminals: tuple[tuple[str, str], ...]) -> bool:
    return any(
        kind == "format" and value in {"uri", "uri-reference"}
        for kind, value in terminals
    ) or bool(_terminal_uri_schemes(terminals))


def _has_closed_web_origin_terminal(terminals: tuple[tuple[str, str], ...]) -> bool:
    valid = (
        "https://example.test",
        "http://example.test:8080",
        "https://[2001:db8::1]:8443",
    )
    invalid = (
        "https://example.test/",
        "https://example.test:443",
        "http://example.test:80",
        "https://example.test:65536",
        "https://user@example.test",
        "https://example.test/path",
        "https://example.test?query=1",
        "https://example.test#fragment",
        "https://Example.test",
    )
    for kind, pattern in terminals:
        if kind != "pattern":
            continue
        try:
            if all(re.fullmatch(pattern, value) for value in valid) and not any(
                re.fullmatch(pattern, value) for value in invalid
            ):
                return True
        except re.error:
            continue
    return False


def _web_origin_schemes(terminals: tuple[tuple[str, str], ...]) -> set[str]:
    patterns = [value for kind, value in terminals if kind == "pattern"]
    if not patterns:
        return set()
    accepted: set[str] = set()
    for scheme in ("http", "https"):
        value = f"{scheme}://example.test"
        try:
            if all(re.search(pattern, value) is not None for pattern in patterns):
                accepted.add(scheme)
        except re.error:
            continue
    return accepted


def _representation_suffix_incompatibility(
    name: str,
    terminals: tuple[tuple[str, str], ...],
    cardinalities: set[str],
) -> tuple[str, str] | None:
    """Return why a representation suffix contradicts its resolved terminal.

    Opaque local identifiers are intentionally not rejected merely because their
    regex is not an ``ak:`` typed-ID pattern. The reverse gate acts only on
    mechanically established contradictions: wrong cardinality, a non-string
    object/value terminal, a DID-method selector masquerading as a DID, or a
    closed non-URI enum masquerading as URI material.
    """

    suffix = _declared_representation_suffix(name)
    if suffix is None:
        return None
    suffix_plural = suffix.endswith("s")
    if cardinalities == {"array"} and not suffix_plural:
        return suffix, "array terminal requires a plural representation suffix"
    if cardinalities == {"scalar"} and suffix_plural:
        return suffix, "scalar terminal requires a singular representation suffix"

    non_identifier_types = {
        '"object"',
        '"boolean"',
        '"integer"',
        '"number"',
    }
    if suffix in {"_id", "_ids"} and ("type", '"object"') in terminals:
        # The object-role diagnostic below gives the actionable projected name.
        return None
    if any(kind == "type" and value in non_identifier_types for kind, value in terminals):
        return suffix, "non-identifier value terminal cannot carry a representation suffix"

    terminal_category, expected_suffix = _role_terminal_contract(
        terminals, plural=cardinalities == {"array"}
    )
    if terminal_category is not None:
        if expected_suffix is not None and suffix != expected_suffix:
            return suffix, f"resolved {terminal_category} terminal requires {expected_suffix}"
        return None

    category = _REPRESENTATION_SUFFIX_CATEGORIES[suffix]
    if category == "did" and any(
        kind == "pattern" and value in {"^did:[a-z0-9]+$", "^did:[a-z0-9]+:$"}
        for kind, value in terminals
    ):
        return suffix, "DID-method selector token is not a complete DID"

    closed_values: list[str] = []
    for kind, value in terminals:
        if kind == "const":
            closed_values.append(value)
        elif kind == "enum":
            closed_values.extend(value.split("|"))
    if category == "did" and closed_values and all(
        re.fullmatch(r"did:[a-z0-9]+", value) for value in closed_values
    ):
        return suffix, "closed DID-method selector is not a complete DID"
    if category == "uri" and closed_values and any(
        not re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", value) for value in closed_values
    ):
        return suffix, "closed selector enum is not URI material"
    return None


def _check_duplicate_representation_suffixes(
    lint: Lint, documents: dict[str, Any]
) -> None:
    """Reject duplicated suffixes and suffix fragments inserted into ordinary words."""

    def walk(path: Path, value: Any, pointer: str = "") -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                child_pointer = f"{pointer}/{key}"
                if _DUPLICATE_REPRESENTATION_SUFFIX_RE.search(key):
                    lint.fail(path, f"NC-IDROLE-001 {child_pointer}: duplicated representation suffix")
                if _EMBEDDED_REPRESENTATION_SUFFIX_RE.search(key):
                    lint.fail(path, f"NC-IDROLE-001 {child_pointer}: representation suffix corrupts an ordinary word")
                walk(path, child, child_pointer)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(path, child, f"{pointer}/{index}")
        elif isinstance(value, str) and _DUPLICATE_REPRESENTATION_SUFFIX_RE.search(value):
            lint.fail(path, f"NC-IDROLE-001 {pointer}: duplicated representation suffix in `{value}`")
        elif isinstance(value, str) and _EMBEDDED_REPRESENTATION_SUFFIX_RE.search(value):
            lint.fail(path, f"NC-IDROLE-001 {pointer}: representation suffix corrupts ordinary word in `{value}`")

    for file_name, document in documents.items():
        walk(SCHEMA_DIR / file_name, document)
    for path in sorted((ARTIFACTS / "registry").glob("*.json")):
        document = load_json(lint, path)
        if document is not None:
            walk(path, document)


def check_identifier_role_suffix_contracts(lint: Lint) -> None:
    """Enforce role + representation suffixes on Arkret-owned identifiers.

    Diagnostics deliberately expose the six review axes required by the
    naming contract.  This makes a failure actionable without asking a reviewer
    to infer lexical ownership or a service-only authorization invariant from
    the field spelling.
    """

    registry = load_json(lint, ROLE_SUFFIX_REGISTRY_PATH)
    if not isinstance(registry, dict):
        return
    grammars = registry.get("generic_grammars")
    forbidden_fields = registry.get("forbidden_arkret_owned_fields")
    responsibility_rows = registry.get("responsibility_field_contracts")
    exception_rows = registry.get("exact_exceptions")
    service_role_rows = registry.get("registered_service_role_fields")
    qualified_service_rows = registry.get("registered_service_qualified_fields")
    provenance_byline_rows = registry.get("registered_provenance_byline_fields")
    network_locator_rows = registry.get("registered_network_locator_fields")
    uri_reference_rows = registry.get("registered_uri_reference_fields")
    origin_rows = registry.get("registered_origin_fields")
    multi_representation_rows = registry.get("multi_representation_field_contracts")
    if not isinstance(forbidden_fields, list) or not all(
        isinstance(field, str) and field for field in forbidden_fields
    ):
        lint.fail(
            ROLE_SUFFIX_REGISTRY_PATH,
            "forbidden_arkret_owned_fields must be an array of field names",
        )
        forbidden_fields = []
    if not all(
        isinstance(rows, list)
        for rows in (
            grammars,
            responsibility_rows,
            exception_rows,
            service_role_rows,
            qualified_service_rows,
            provenance_byline_rows,
            network_locator_rows,
            uri_reference_rows,
            origin_rows,
            multi_representation_rows,
        )
    ):
        lint.fail(
            ROLE_SUFFIX_REGISTRY_PATH,
            "identifier role registries and exception tables must be arrays",
        )
        return
    allowed_representation_profiles = {
        "did_core_id",
        "did",
        "did_url",
        "account_id",
        "actor_id",
    }
    multi_representation_contracts: dict[str, set[str]] = {}
    for index, row in enumerate(multi_representation_rows):
        where = f"multi_representation_field_contracts[{index}]"
        if not isinstance(row, dict):
            lint.fail(ROLE_SUFFIX_REGISTRY_PATH, f"{where} must be an object")
            continue
        field = row.get("field")
        profiles = row.get("representation_profiles")
        profile_meanings = row.get("profile_meanings")
        reason = row.get("reason")
        if (
            not isinstance(field, str)
            or field in multi_representation_contracts
            or not isinstance(profiles, list)
            or len(profiles) < 2
            or not all(profile in allowed_representation_profiles for profile in profiles)
            or len(set(profiles)) != len(profiles)
            or not isinstance(profile_meanings, dict)
            or set(profile_meanings) != set(profiles)
            or not all(isinstance(value, str) and value for value in profile_meanings.values())
            or not isinstance(reason, str)
            or not reason
        ):
            lint.fail(ROLE_SUFFIX_REGISTRY_PATH, f"{where} is incomplete or duplicated")
            continue
        multi_representation_contracts[field] = set(profiles)
    responsibility_contracts: dict[str, dict[str, Any]] = {}
    allowed_responsibility_carriers = {"did_core_id", "account_id", "actor_id"}
    allowed_responsibility_subjects = {"principal", "service", "station", "hardware_module", "account", "actor"}
    for index, row in enumerate(responsibility_rows):
        where = f"responsibility_field_contracts[{index}]"
        if not isinstance(row, dict):
            lint.fail(ROLE_SUFFIX_REGISTRY_PATH, f"{where} must be an object")
            continue
        field = row.get("field")
        terminal_category = row.get("terminal_category")
        subject_class = row.get("subject_class")
        account_scoped = row.get("account_scoped")
        required_evidence = row.get("required_evidence")
        if (
            not isinstance(field, str)
            or field in responsibility_contracts
            or terminal_category not in allowed_responsibility_carriers
            or subject_class not in allowed_responsibility_subjects
            or not isinstance(account_scoped, bool)
            or not isinstance(required_evidence, list)
            or not required_evidence
            or not all(isinstance(item, str) and item for item in required_evidence)
        ):
            lint.fail(ROLE_SUFFIX_REGISTRY_PATH, f"{where} is incomplete or duplicated")
            continue
        if account_scoped and (
            terminal_category != "account_id" or not field.endswith("_account_id")
        ):
            lint.fail(
                ROLE_SUFFIX_REGISTRY_PATH,
                f"{where} declares account_scoped=true without an _account_id AccountId carrier",
            )
            continue
        responsibility_contracts[field] = row
    registered_service_roles: set[str] = set()
    for index, row in enumerate(service_role_rows):
        if not isinstance(row, dict) or not isinstance(row.get("field"), str) or not isinstance(row.get("reason"), str):
            lint.fail(ROLE_SUFFIX_REGISTRY_PATH, f"registered_service_role_fields[{index}] is incomplete")
            continue
        registered_service_roles.add(row["field"])
    registered_service_qualified: set[str] = set()
    for index, row in enumerate(qualified_service_rows):
        if not isinstance(row, dict) or not all(
            isinstance(row.get(key), str) and row[key]
            for key in ("field", "role_stem", "reason")
        ):
            lint.fail(ROLE_SUFFIX_REGISTRY_PATH, f"registered_service_qualified_fields[{index}] is incomplete")
            continue
        registered_service_qualified.add(row["field"])
    registered_provenance_bylines: dict[str, tuple[str, set[str]]] = {}
    for index, row in enumerate(provenance_byline_rows):
        where = f"registered_provenance_byline_fields[{index}]"
        if not isinstance(row, dict):
            lint.fail(ROLE_SUFFIX_REGISTRY_PATH, f"{where} must be an object")
            continue
        field = row.get("field")
        reason = row.get("reason")
        terminal_categories = row.get("terminal_categories")
        if (
            not isinstance(field, str)
            or not re.fullmatch(r"[a-z][a-z0-9_]*_by", field)
            or not isinstance(reason, str)
            or not reason
            or not isinstance(terminal_categories, list)
            or not terminal_categories
            or not all(isinstance(item, str) and item for item in terminal_categories)
        ):
            lint.fail(ROLE_SUFFIX_REGISTRY_PATH, f"{where} is incomplete")
            continue
        if field in registered_provenance_bylines:
            lint.fail(ROLE_SUFFIX_REGISTRY_PATH, f"duplicate provenance byline field `{field}`")
            continue
        registered_provenance_bylines[field] = (reason, set(terminal_categories))
    registered_network_locators: dict[str, tuple[str, set[str]]] = {}
    for index, row in enumerate(network_locator_rows):
        where = f"registered_network_locator_fields[{index}]"
        if not isinstance(row, dict):
            lint.fail(ROLE_SUFFIX_REGISTRY_PATH, f"{where} must be an object")
            continue
        field = row.get("field")
        schemes = row.get("schemes")
        reason = row.get("reason")
        if (
            not isinstance(field, str)
            or (field != "url" and not field.endswith("_url"))
            or not isinstance(schemes, list)
            or not schemes
            or not all(scheme in {"http", "https", "ws", "wss"} for scheme in schemes)
            or not isinstance(reason, str)
            or not reason
        ):
            lint.fail(ROLE_SUFFIX_REGISTRY_PATH, f"{where} is incomplete")
            continue
        if field in registered_network_locators:
            lint.fail(ROLE_SUFFIX_REGISTRY_PATH, f"duplicate network locator field `{field}`")
            continue
        registered_network_locators[field] = (reason, set(schemes))
    registered_uri_references: dict[str, str] = {}
    for index, row in enumerate(uri_reference_rows):
        where = f"registered_uri_reference_fields[{index}]"
        if not isinstance(row, dict) or not all(
            isinstance(row.get(key), str) and row[key] for key in ("field", "reason")
        ):
            lint.fail(ROLE_SUFFIX_REGISTRY_PATH, f"{where} is incomplete")
            continue
        field = row["field"]
        if field != "uri" and not field.endswith("_uri"):
            lint.fail(ROLE_SUFFIX_REGISTRY_PATH, f"{where} must name a complete URI role")
            continue
        if field in registered_uri_references:
            lint.fail(ROLE_SUFFIX_REGISTRY_PATH, f"duplicate URI reference field `{field}`")
            continue
        registered_uri_references[field] = row["reason"]
    registered_origins: dict[tuple[str, str], tuple[str, set[str]]] = {}
    for index, row in enumerate(origin_rows):
        where = f"registered_origin_fields[{index}]"
        if not isinstance(row, dict) or not all(
            isinstance(row.get(key), str) and row[key] for key in ("file", "pointer", "reason")
        ):
            lint.fail(ROLE_SUFFIX_REGISTRY_PATH, f"{where} is incomplete")
            continue
        key = (row["file"], row["pointer"])
        property_name = row["pointer"].rsplit("/properties/", 1)[-1]
        if property_name != "origin" and not property_name.endswith("_origin"):
            lint.fail(
                ROLE_SUFFIX_REGISTRY_PATH,
                f"{where} must point to a complete `origin` or `*_origin` role",
            )
            continue
        schemes = row.get("schemes", ["http", "https"])
        if (
            not isinstance(schemes, list)
            or not schemes
            or not all(scheme in {"http", "https"} for scheme in schemes)
        ):
            lint.fail(ROLE_SUFFIX_REGISTRY_PATH, f"{where}.schemes is invalid")
            continue
        if key in registered_origins:
            lint.fail(ROLE_SUFFIX_REGISTRY_PATH, f"duplicate Web Origin registration {key}")
            continue
        registered_origins[key] = (row["reason"], set(schemes))
    exceptions: dict[tuple[str, str], tuple[str, set[str]]] = {}
    for index, row in enumerate(exception_rows):
        if not isinstance(row, dict):
            lint.fail(ROLE_SUFFIX_REGISTRY_PATH, f"exact_exceptions[{index}] must be an object")
            continue
        key = (row.get("file"), row.get("pointer"))
        reason = row.get("reason")
        terminal_categories = row.get("terminal_categories")
        if (
            not all(isinstance(item, str) and item for item in (*key, reason))
            or not isinstance(terminal_categories, list)
            or not terminal_categories
            or not all(isinstance(item, str) and item for item in terminal_categories)
        ):
            lint.fail(ROLE_SUFFIX_REGISTRY_PATH, f"exact_exceptions[{index}] is incomplete")
            continue
        if key in exceptions:
            lint.fail(ROLE_SUFFIX_REGISTRY_PATH, f"duplicate exact exception {key}")
            continue
        exceptions[key] = (reason, set(terminal_categories))

    documents = _schema_documents(lint)
    _check_duplicate_representation_suffixes(lint, documents)
    observed_representation_profiles: dict[str, set[str]] = {}
    for file_name, document in documents.items():
        external_owners = {
            owner.pointer
            for owner in enumerate_property_owners(file_name, document)
            if EXTERNAL_LITERAL_OBJECT_KEYWORD in owner.node
        }
        for occurrence in enumerate_schema_properties(file_name, document):
            owner_pointer = occurrence.pointer.rsplit("/properties/", 1)[0]
            if owner_pointer in external_owners:
                continue
            terminals = resolve_terminal_constraints(documents, file_name, occurrence.shape)
            cardinalities = _shape_cardinalities(documents, file_name, occurrence.shape)
            category, _ = _role_terminal_contract(
                terminals, plural=cardinalities == {"array"}
            )
            if category in allowed_representation_profiles:
                observed_representation_profiles.setdefault(occurrence.name, set()).add(category)
    observed_multi_representation = {
        field: profiles
        for field, profiles in observed_representation_profiles.items()
        if len(profiles) > 1
    }
    for field, profiles in sorted(observed_multi_representation.items()):
        registered = multi_representation_contracts.get(field)
        if registered != profiles:
            lint.fail(
                ROLE_SUFFIX_REGISTRY_PATH,
                f"multi-representation field `{field}` resolves to {sorted(profiles)} but "
                f"registry declares {sorted(registered) if registered is not None else None}",
            )
    stale_multi_representation = sorted(
        set(multi_representation_contracts) - set(observed_multi_representation)
    )
    if stale_multi_representation:
        lint.fail(
            ROLE_SUFFIX_REGISTRY_PATH,
            "multi-representation field contracts are stale or no longer polymorphic: "
            f"{stale_multi_representation}",
        )
    reached_exceptions: set[tuple[str, str]] = set()
    reached_provenance_bylines: set[str] = set()
    reached_network_locators: set[str] = set()
    reached_uri_references: set[str] = set()
    reached_origins: set[tuple[str, str]] = set()
    reached_responsibility_contracts: set[str] = set()
    for file_name, document in documents.items():
        external_owners = {
            owner.pointer
            for owner in enumerate_property_owners(file_name, document)
            if EXTERNAL_LITERAL_OBJECT_KEYWORD in owner.node
        }
        for occurrence in enumerate_schema_properties(file_name, document):
            owner_pointer = occurrence.pointer.rsplit("/properties/", 1)[0]
            lexical_owner = (
                "external_literal" if owner_pointer in external_owners else "arkret_owned"
            )
            if lexical_owner == "external_literal":
                continue

            name = occurrence.name
            exception = exceptions.get((file_name, occurrence.pointer))
            exception_reason = exception[0] if exception else "none"

            if name in forbidden_fields:
                terminals = resolve_terminal_constraints(documents, file_name, occurrence.shape)
                terminal_category, _ = _role_terminal_contract(terminals, plural=False)
                lint.fail(
                    SCHEMA_DIR / file_name,
                    f"NC-IDROLE-001 {occurrence.pointer}: Arkret-owned responsibility field "
                    f"`{name}` is forbidden regardless of terminal_category={terminal_category}; "
                    "use a subject-class and carrier-specific field such as "
                    "holder_principal_id, holder_service_id, controller_principal_id, "
                    "controller_account_id, or controller_actor_id",
                )
                continue

            responsibility_contract = responsibility_contracts.get(name)
            if responsibility_contract is not None:
                terminals = resolve_terminal_constraints(documents, file_name, occurrence.shape)
                cardinalities = _shape_cardinalities(documents, file_name, occurrence.shape)
                terminal_category, _ = _role_terminal_contract(
                    terminals, plural=cardinalities == {"array"}
                )
                required_carrier = responsibility_contract["terminal_category"]
                if cardinalities not in ({"scalar"}, set()):
                    lint.fail(
                        SCHEMA_DIR / file_name,
                        f"NC-IDROLE-001 {occurrence.pointer}: `{name}` must be a scalar responsibility identifier",
                    )
                elif terminal_category != required_carrier:
                    lint.fail(
                        SCHEMA_DIR / file_name,
                        f"NC-IDROLE-001 {occurrence.pointer}: `{name}` resolves to "
                        f"terminal_category={terminal_category}; required carrier is "
                        f"{required_carrier} for subject_class={responsibility_contract['subject_class']}",
                    )
                if (
                    name == "controller_principal_id"
                    and (
                        file_name in {
                            "applet-package.schema.json",
                            "applet-registration-epoch-transcript.schema.json",
                        }
                        or (
                            file_name == "event-payload.schema.json"
                            and "/$defs/applet_registration_payload/" in occurrence.pointer
                        )
                    )
                    and occurrence.shape.get("x-arkret-principal-kinds")
                    != ["human", "organization"]
                ):
                    lint.fail(
                        SCHEMA_DIR / file_name,
                        f"NC-IDROLE-001 {occurrence.pointer}: Applet controller_principal_id "
                        "must declare the exact human/organization publisher-principal constraint",
                    )
                reached_responsibility_contracts.add(name)
                continue

            if re.search(r"_by_(?:id|ids|did|dids|verification_method|verification_methods)$", name):
                bare_byline = re.sub(
                    r"_(?:id|ids|did|dids|verification_method|verification_methods)$",
                    "",
                    name,
                )
                lint.fail(
                    SCHEMA_DIR / file_name,
                    f"NC-IDROLE-001 {occurrence.pointer}: provenance/byline role `{name}` "
                    f"must retain the complete bare role `{bare_byline}`; its DidCoreId, Did, "
                    "DidUrl, or closed-union terminal is enforced independently of spelling",
                )
                continue

            if (
                (name.endswith("_service_kind") or name.endswith("_service_kinds"))
                and name not in registered_service_roles
                and not name.endswith(("_service_id", "_service_ids"))
            ):
                plural = name.endswith("_service_kinds")
                role_stem = name.removesuffix("_service_kinds").removesuffix("_service_kind")
                expected = f"{role_stem}_{'kinds' if plural else 'kind'}"
                lint.fail(
                    SCHEMA_DIR / file_name,
                    f"NC-IDROLE-001 {occurrence.pointer}: lexical_owner={lexical_owner}; "
                    f"role_stem={role_stem}; terminal_category=service_kind; "
                    f"required_subject_class=service; expected_suffix=_kind; "
                    f"exception_reason={exception_reason}; service is an entity-class "
                    f"qualifier here, so rename `{name}` to `{expected}` and keep the "
                    "service-only invariant in schema/authorization validation",
                )
                continue

            if (
                ({"service", "services"} & set(name.split("_")))
                and name not in registered_service_roles
                and name not in registered_service_qualified
                and not name.endswith(("_service_id", "_service_ids"))
            ):
                lint.fail(
                    SCHEMA_DIR / file_name,
                    f"NC-IDROLE-001 {occurrence.pointer}: lexical_owner={lexical_owner}; "
                    f"role_stem={name}; terminal_category=qualified_field; "
                    "required_subject_class=service; expected_suffix=role_specific; "
                    f"exception_reason={exception_reason}; `{name}` inserts service as an "
                    "entity-class qualifier; rename it according to its resolved value "
                    "category, or register the complete service role with exact field, "
                    "role_stem, and reason",
                )
                continue

            terminals = resolve_terminal_constraints(documents, file_name, occurrence.shape)
            cardinalities = _shape_cardinalities(documents, file_name, occurrence.shape)
            if exception is not None:
                exception_category, _ = _role_terminal_contract(
                    terminals, plural=cardinalities == {"array"}
                )
                if exception_category not in exception[1]:
                    lint.fail(
                        ROLE_SUFFIX_REGISTRY_PATH,
                        f"exact exception {(file_name, occurrence.pointer)} declares "
                        f"terminal_categories={sorted(exception[1])} but resolves to "
                        f"{exception_category!r}",
                    )
                reached_exceptions.add((file_name, occurrence.pointer))
                continue
            network_locator = registered_network_locators.get(name)
            if network_locator is not None:
                observed_schemes = _terminal_uri_schemes(terminals)
                allowed_schemes = network_locator[1]
                if cardinalities not in ({"scalar"}, set()):
                    lint.fail(
                        SCHEMA_DIR / file_name,
                        f"NC-IDROLE-001 {occurrence.pointer}: registered network locator "
                        f"`{name}` must be scalar URL material",
                    )
                elif not observed_schemes:
                    lint.fail(
                        SCHEMA_DIR / file_name,
                        f"NC-IDROLE-001 {occurrence.pointer}: registered network locator "
                        f"`{name}` must constrain an HTTP(S)/WS(S) scheme; `format: uri` "
                        "alone does not establish URL semantics",
                    )
                elif not observed_schemes <= allowed_schemes:
                    lint.fail(
                        SCHEMA_DIR / file_name,
                        f"NC-IDROLE-001 {occurrence.pointer}: registered network locator "
                        f"`{name}` permits schemes={sorted(allowed_schemes)} but its terminal "
                        f"admits {sorted(observed_schemes)}",
                    )
                reached_network_locators.add(name)
                continue
            uri_reference = registered_uri_references.get(name)
            if uri_reference is not None:
                if cardinalities not in ({"scalar"}, set()):
                    lint.fail(
                        SCHEMA_DIR / file_name,
                        f"NC-IDROLE-001 {occurrence.pointer}: registered URI reference "
                        f"`{name}` must be scalar URI material",
                    )
                elif not _has_uri_terminal(terminals):
                    lint.fail(
                        SCHEMA_DIR / file_name,
                        f"NC-IDROLE-001 {occurrence.pointer}: registered URI reference "
                        f"`{name}` does not resolve to a URI terminal",
                    )
                reached_uri_references.add(name)
                continue
            origin_key = (file_name, occurrence.pointer)
            origin_role = registered_origins.get(origin_key)
            if origin_role is not None:
                if cardinalities not in ({"scalar"}, set()) or not _has_uri_terminal(terminals):
                    lint.fail(
                        SCHEMA_DIR / file_name,
                        f"NC-IDROLE-001 {occurrence.pointer}: complete Web Origin role "
                        "`origin` must resolve to a scalar URI terminal",
                    )
                elif not _has_closed_web_origin_terminal(terminals):
                    lint.fail(
                        SCHEMA_DIR / file_name,
                        f"NC-IDROLE-001 {occurrence.pointer}: complete Web Origin role "
                        "`origin` must use the canonical scheme+host+effective-port profile "
                        "and reject userinfo, path, query, fragment, trailing slash, default "
                        "ports, out-of-range ports, and non-canonical host spelling",
                    )
                elif _web_origin_schemes(terminals) != origin_role[1]:
                    lint.fail(
                        SCHEMA_DIR / file_name,
                        f"NC-IDROLE-001 {occurrence.pointer}: complete Web Origin role "
                        f"`{name}` must allow exactly the registered schemes "
                        f"{sorted(origin_role[1])}",
                    )
                reached_origins.add(origin_key)
                continue
            provenance_byline = registered_provenance_bylines.get(name)
            if provenance_byline is not None:
                terminal_category, _ = _role_terminal_contract(
                    terminals, plural=cardinalities == {"array"}
                )
                if cardinalities not in ({"scalar"}, set()):
                    lint.fail(
                        SCHEMA_DIR / file_name,
                        f"NC-IDROLE-001 {occurrence.pointer}: registered provenance/byline "
                        f"role `{name}` must be a scalar identifier",
                    )
                elif terminal_category not in provenance_byline[1]:
                    lint.fail(
                        SCHEMA_DIR / file_name,
                        f"NC-IDROLE-001 {occurrence.pointer}: registered provenance/byline "
                        f"role `{name}` permits terminal_categories="
                        f"{sorted(provenance_byline[1])} but resolves to {terminal_category!r}",
                    )
                reached_provenance_bylines.add(name)
                continue

            carrier_suffixes = {
                "_principal_id": "did_core_id",
                "_service_id": "did_core_id",
                "_station_id": "did_core_id",
                "_hardware_module_id": "did_core_id",
                "_account_id": "account_id",
                "_actor_id": "actor_id",
            }
            matched_carrier = next(
                (
                    (suffix, carrier)
                    for suffix, carrier in carrier_suffixes.items()
                    if name.endswith(suffix)
                ),
                None,
            )
            if matched_carrier is not None:
                declared_suffix, required_carrier = matched_carrier
                terminal_category, _ = _role_terminal_contract(
                    terminals, plural=False
                )
                if terminal_category != required_carrier:
                    lint.fail(
                        SCHEMA_DIR / file_name,
                        f"NC-IDROLE-001 {occurrence.pointer}: `{name}` declares "
                        f"carrier suffix {declared_suffix} but resolves to "
                        f"terminal_category={terminal_category}; required carrier is "
                        f"{required_carrier}",
                    )
                    continue
                if name.endswith("_station_id") and name.startswith(("holder_", "controller_")):
                    if occurrence.shape.get("x-arkret-service-kind") != "station":
                        lint.fail(
                            SCHEMA_DIR / file_name,
                            f"NC-IDROLE-001 {occurrence.pointer}: `{name}` requires "
                            "machine-readable x-arkret-service-kind=station metadata",
                        )
                        continue
                if name.endswith("_hardware_module_id") and name.startswith(("holder_", "controller_")):
                    if occurrence.shape.get("x-arkret-required-binding") != "hardware_backed_attestation":
                        lint.fail(
                            SCHEMA_DIR / file_name,
                            f"NC-IDROLE-001 {occurrence.pointer}: `{name}` requires "
                            "machine-readable hardware-backed attestation binding",
                        )
                        continue
            inverse_mismatch = _representation_suffix_incompatibility(
                name, terminals, cardinalities
            )
            if inverse_mismatch is not None:
                declared_suffix, mismatch_reason = inverse_mismatch
                lint.fail(
                    SCHEMA_DIR / file_name,
                    f"NC-IDROLE-001 {occurrence.pointer}: lexical_owner={lexical_owner}; "
                    f"role_stem={name.removesuffix(declared_suffix)}; "
                    "terminal_category=non_identifier_or_mismatched_representation; "
                    "required_subject_class=unspecified; "
                    f"expected_suffix=none; exception_reason={exception_reason}; "
                    f"`{name}` declares {declared_suffix} but {mismatch_reason}",
                )
                continue
            if name.endswith(("_id", "_ids")) and (
                ("type", '"object"') in terminals
                or any(
                    kind in {"account_id", "actor_id", "composite_identifier"}
                    and value == "closed_object"
                    for kind, value in terminals
                )
            ):
                terminal_category, expected_suffix = _role_terminal_contract(
                    terminals, plural=name.endswith("_ids")
                )
                if _role_name_matches_terminal(
                    name, terminal_category or "", expected_suffix or "", grammars
                ):
                    continue
                expected = (
                    name.removesuffix("_ids") + "s"
                    if name.endswith("_ids")
                    else name.removesuffix("_id")
                )
                lint.fail(
                    SCHEMA_DIR / file_name,
                    f"NC-IDROLE-001 {occurrence.pointer}: lexical_owner={lexical_owner}; "
                    f"role_stem={_role_stem(name, 'typed_object_id')}; "
                    "terminal_category=object; required_subject_class=unspecified; "
                    f"expected_suffix=object_role; exception_reason={exception_reason}; "
                    f"`{name}` claims an identifier representation but resolves to an "
                    f"object value; rename it to an object role such as `{expected}`",
                )
                continue

            if cardinalities == {"array"}:
                plural = True
            else:
                plural = False
            terminal_category, expected_suffix = _role_terminal_contract(
                terminals, plural=plural
            )
            if terminal_category is None:
                continue
            if terminal_category == "uri":
                lint.fail(
                    SCHEMA_DIR / file_name,
                    f"NC-IDROLE-001 {occurrence.pointer}: lexical_owner={lexical_owner}; "
                    f"role_stem={name}; terminal_category=uri; "
                    "required_subject_class=unspecified; expected_suffix=semantic_registration; "
                    f"exception_reason={exception_reason}; `format: uri` does not determine "
                    "whether the Arkret-owned field is a network `_url`, a generic `_uri`, "
                    "or a complete Web Origin role",
                )
                continue
            if cardinalities not in ({"array"}, {"scalar"}, set()):
                lint.fail(
                    SCHEMA_DIR / file_name,
                    f"NC-IDROLE-001 {occurrence.pointer}: lexical_owner={lexical_owner}; "
                    f"role_stem={name}; terminal_category=mixed_cardinality; "
                    "required_subject_class=unspecified; expected_suffix=none; "
                    f"exception_reason={exception_reason}; identifier scalar/array unions "
                    "require an exact closed-union exception",
                )
                continue
            if expected_suffix is None:
                lint.fail(
                    SCHEMA_DIR / file_name,
                    f"NC-IDROLE-001 {occurrence.pointer}: lexical_owner={lexical_owner}; "
                    f"role_stem={name}; terminal_category={terminal_category}; "
                    "required_subject_class=unspecified; expected_suffix=none; "
                    f"exception_reason={exception_reason}; multiple identifier terminal "
                    "categories require a closed discriminated union and exact-path exception",
                )
                continue
            if _role_name_matches_terminal(name, terminal_category, expected_suffix, grammars):
                continue
            description = occurrence.shape.get("description", "") if isinstance(occurrence.shape, dict) else ""
            required_subject_class = (
                "service" if "service" in description.lower() else "unspecified"
            )
            role_stem = _role_stem(name, terminal_category)
            lint.fail(
                SCHEMA_DIR / file_name,
                f"NC-IDROLE-001 {occurrence.pointer}: lexical_owner={lexical_owner}; "
                f"role_stem={role_stem}; terminal_category={terminal_category}; "
                f"required_subject_class={required_subject_class}; "
                f"expected_suffix={expected_suffix}; exception_reason={exception_reason}; "
                f"Arkret-owned single identifiers must use `{name}{expected_suffix}`",
            )

    stale_exceptions = sorted(set(exceptions) - reached_exceptions)
    stale_responsibility_contracts = sorted(
        set(responsibility_contracts) - reached_responsibility_contracts
    )
    if stale_responsibility_contracts:
        lint.fail(
            ROLE_SUFFIX_REGISTRY_PATH,
            "responsibility field contracts are stale or unreachable: "
            f"{stale_responsibility_contracts}",
        )
    if stale_exceptions:
        lint.fail(
            ROLE_SUFFIX_REGISTRY_PATH,
            f"exact identifier exceptions are stale or unreachable: {stale_exceptions}",
        )
    stale_provenance_bylines = sorted(
        set(registered_provenance_bylines) - reached_provenance_bylines
    )
    if stale_provenance_bylines:
        lint.fail(
            ROLE_SUFFIX_REGISTRY_PATH,
            "registered provenance/byline fields are stale or unreachable: "
            f"{stale_provenance_bylines}",
        )
    stale_network_locators = sorted(set(registered_network_locators) - reached_network_locators)
    if stale_network_locators:
        lint.fail(
            ROLE_SUFFIX_REGISTRY_PATH,
            f"registered network locator fields are stale or unreachable: {stale_network_locators}",
        )
    stale_uri_references = sorted(set(registered_uri_references) - reached_uri_references)
    if stale_uri_references:
        lint.fail(
            ROLE_SUFFIX_REGISTRY_PATH,
            f"registered URI reference fields are stale or unreachable: {stale_uri_references}",
        )
    stale_origins = sorted(set(registered_origins) - reached_origins)
    if stale_origins:
        lint.fail(
            ROLE_SUFFIX_REGISTRY_PATH,
            f"registered origin fields are stale or unreachable: {stale_origins}",
        )

def check_collection_field_contracts(lint: Lint) -> None:
    """Enforce NC-COLLECTION-001 independently of identifier representation.

    A referenced item type does not dictate the property spelling. Object
    collections use the shortest unambiguous plural role in their lexical
    context; collective nouns and grammar operators are admitted only at exact
    registered paths. Pagination objects are likewise pinned independently of
    identifier suffixes.
    """

    registry = load_json(lint, COLLECTION_NAMING_REGISTRY_PATH)
    if not isinstance(registry, dict):
        return
    if registry.get("source_of_truth") is not False:
        lint.fail(
            COLLECTION_NAMING_REGISTRY_PATH,
            "the collection naming registry records reviewed exceptions; schemas and prose remain normative",
        )
    exception_rows = registry.get("exact_exceptions")
    pagination_rows = registry.get("pagination_objects")
    singular_s_tokens = registry.get("singular_s_tokens")
    if (
        not isinstance(exception_rows, list)
        or not isinstance(pagination_rows, list)
        or not isinstance(singular_s_tokens, list)
        or not all(isinstance(item, str) and item for item in singular_s_tokens)
    ):
        lint.fail(
            COLLECTION_NAMING_REGISTRY_PATH,
            "exact_exceptions, pagination_objects and singular_s_tokens must be arrays",
        )
        return
    singular_s_token_set = set(singular_s_tokens)

    exceptions: dict[tuple[str, str], str] = {}
    for index, row in enumerate(exception_rows):
        where = f"exact_exceptions[{index}]"
        if not isinstance(row, dict) or not all(
            isinstance(row.get(key), str) and row[key]
            for key in ("file", "pointer", "reason")
        ):
            lint.fail(COLLECTION_NAMING_REGISTRY_PATH, f"{where} is incomplete")
            continue
        key = (row["file"], row["pointer"])
        if key in exceptions:
            lint.fail(COLLECTION_NAMING_REGISTRY_PATH, f"{where} duplicates {key}")
            continue
        exceptions[key] = row["reason"]

    documents = _schema_documents(lint)
    reached: set[tuple[str, str]] = set()
    for file_name, document in documents.items():
        external_owners = {
            owner.pointer
            for owner in enumerate_property_owners(file_name, document)
            if EXTERNAL_LITERAL_OBJECT_KEYWORD in owner.node
        }
        for occurrence in enumerate_schema_properties(file_name, document):
            owner_pointer = occurrence.pointer.rsplit("/properties/", 1)[0]
            if owner_pointer in external_owners:
                continue
            terminals = resolve_terminal_constraints(documents, file_name, occurrence.shape)
            cardinalities = _shape_cardinalities(documents, file_name, occurrence.shape)
            if cardinalities != {"array"} or ("type", '"object"') not in terminals:
                continue
            key = (file_name, occurrence.pointer)
            if key in exceptions:
                reached.add(key)
                continue
            final_token = occurrence.name.rsplit("_", 1)[-1]
            if final_token.endswith("s") and final_token not in singular_s_token_set:
                continue
            lint.fail(
                SCHEMA_DIR / file_name,
                f"NC-COLLECTION-001 {occurrence.pointer}: lexical_owner=arkret_owned; "
                f"role_stem={occurrence.name}; terminal_category=object_array; "
                f"expected_suffix=<plural>; exception_reason=none; object collections "
                "must use the shortest unambiguous plural role, or an exact registered "
                "collective/mass-noun exception",
            )

    stale = sorted(set(exceptions) - reached)
    if stale:
        lint.fail(
            COLLECTION_NAMING_REGISTRY_PATH,
            f"exact collection exceptions are stale or unreachable: {stale}",
        )

    observed_pages: dict[tuple[str, str], tuple[list[str], list[str]]] = {}
    for file_name, document in documents.items():
        for owner in enumerate_property_owners(file_name, document):
            if EXTERNAL_LITERAL_OBJECT_KEYWORD in owner.node:
                continue
            properties = owner.node.get("properties", {})
            companions = sorted(
                name
                for name in owner.names
                if name != "rate_limited"
                and (
                    name in {"limited", "next_cursor", "has_more"}
                    or name.endswith(("_limited", "_next_cursor", "_has_more"))
                )
            )
            collections = sorted(
                name
                for name in owner.names
                if isinstance(properties.get(name), dict)
                and _shape_cardinalities(documents, file_name, properties[name]) == {"array"}
            )
            if companions and collections:
                observed_pages[(file_name, owner.pointer)] = (collections, companions)

    seen_pages: set[tuple[str, str]] = set()
    for index, row in enumerate(pagination_rows):
        where = f"pagination_objects[{index}]"
        if not isinstance(row, dict) or not all(
            isinstance(row.get(key), str) and row[key]
            for key in ("file", "collection_field", "reason")
        ) or not isinstance(row.get("pointer"), str) or not isinstance(row.get("companion_fields"), list) or not all(
            isinstance(item, str) and item for item in row.get("companion_fields", [])
        ):
            lint.fail(COLLECTION_NAMING_REGISTRY_PATH, f"{where} is incomplete")
            continue
        key = (row["file"], row["pointer"])
        if key in seen_pages:
            lint.fail(COLLECTION_NAMING_REGISTRY_PATH, f"{where} duplicates {key}")
            continue
        seen_pages.add(key)
        observed = observed_pages.get(key)
        if observed is None:
            lint.fail(
                COLLECTION_NAMING_REGISTRY_PATH,
                f"{where} is stale: the owner no longer has both a collection and pagination companions",
            )
        document = documents.get(row["file"])
        if document is None:
            lint.fail(COLLECTION_NAMING_REGISTRY_PATH, f"{where} names an unknown schema")
            continue
        try:
            page = resolve_json_pointer(document, f"#{row['pointer']}")
        except (KeyError, TypeError, ValueError):
            lint.fail(COLLECTION_NAMING_REGISTRY_PATH, f"{where} pointer no longer resolves")
            continue
        if not isinstance(page, dict) or page.get("type") != "object":
            lint.fail(COLLECTION_NAMING_REGISTRY_PATH, f"{where} must resolve to an object")
            continue
        properties = page.get("properties")
        collection_field = row["collection_field"]
        companions = row["companion_fields"]
        if not isinstance(properties, dict) or not isinstance(properties.get(collection_field), dict):
            lint.fail(
                SCHEMA_DIR / row["file"],
                f"NC-COLLECTION-001 {row['pointer']}: pagination object is missing collection field `{collection_field}`",
            )
            continue
        cardinalities = _shape_cardinalities(
            documents, row["file"], properties[collection_field]
        )
        missing = [name for name in companions if name not in properties]
        unexpected_companions = (
            sorted(set(observed[1]) - set(companions)) if observed is not None else []
        )
        if cardinalities != {"array"} or missing or unexpected_companions:
            lint.fail(
                SCHEMA_DIR / row["file"],
                f"NC-COLLECTION-001 {row['pointer']}: pagination object requires array "
                f"`{collection_field}` and companion fields {companions}; missing={missing}; "
                f"unregistered_companions={unexpected_companions}",
            )

    unregistered_pages = sorted(set(observed_pages) - seen_pages)
    if unregistered_pages:
        lint.fail(
            COLLECTION_NAMING_REGISTRY_PATH,
            "pagination owner closure drift: unregistered="
            f"{[(file_name, pointer, observed_pages[(file_name, pointer)]) for file_name, pointer in unregistered_pages]}",
        )


_AK_TYPED_PREFIX_RE = re.compile(r"^\^\(?(?:\?:)?ak:([a-z0-9_]+):")
_DID_PREFIX_RE = re.compile(r"^\^\(?(?:\?:)?did:")
_AK_SYMBOL_PREFIX_RE = re.compile(r"^\^\(?(?:\?:)?ak\\\.")


def derive_category(
    terminals: tuple[tuple[str, str], ...], id_kinds: frozenset[str]
) -> str | None:
    """Return the category the schema type decides, or ``None`` when it cannot.

    Only anchored, unambiguous lexical evidence counts. A union of several
    decided categories is still decided; a union that contains one branch the
    table cannot read is not, and goes to the classification registry so a human
    records what that branch is.
    """

    if not terminals:
        return None
    categories: set[str] = set()
    for kind, value in terminals:
        if kind == "pattern":
            typed = _AK_TYPED_PREFIX_RE.match(value)
            if typed:
                slug = typed.group(1)
                if slug == "did_core":
                    categories.add("responsibility_identity_material")
                    continue
                if slug in id_kinds:
                    categories.add("typed_object_id")
                    continue
                return None
            if _DID_PREFIX_RE.match(value):
                categories.add("responsibility_identity_material")
                continue
            if _AK_SYMBOL_PREFIX_RE.match(value):
                categories.add("registry_catalog_symbol")
                continue
            return None
        if kind in {"const", "enum"}:
            values = value.split("|")
            if values and all(item.startswith("ak.") for item in values):
                categories.add("registry_catalog_symbol")
                continue
            return None
        if kind in {"account_id", "actor_id", "composite_identifier"} and value == "closed_object":
            categories.add("responsibility_identity_material")
            continue
        return None
    if len(categories) == 1:
        return next(iter(categories))
    return None


def registered_id_kinds(id_kind_registry: Any) -> frozenset[str]:
    """Return every kind slug the ID registry recognises, special forms included.

    ``ak:seal:`` and ``ak:blob:`` are registered special forms rather than
    ``id_kinds`` rows; reading only ``id_kinds`` would make their occurrences
    look undecidable and push them into a hand-kept table for no reason.
    """

    if not isinstance(id_kind_registry, dict):
        return frozenset()
    slugs: set[str] = set()
    for section in ("id_kinds", "special_forms"):
        rows = id_kind_registry.get(section)
        if isinstance(rows, list):
            slugs |= {
                row["kind"]
                for row in rows
                if isinstance(row, dict) and isinstance(row.get("kind"), str)
            }
    return frozenset(slugs)


def _prose_categories(lint: Lint) -> set[str]:
    text = read_text(COMMON_FIELDS_PATH)
    markers = IDENTIFIER_CATEGORY_MARKER_RE.findall(text)
    if len(markers) != len(set(markers)):
        lint.fail(COMMON_FIELDS_PATH, "identifier_category markers must be unique")
    if not markers:
        lint.fail(
            COMMON_FIELDS_PATH,
            "2.1 must declare the identifier value-category table with identifier_category markers",
        )
    return set(markers)


def check_identifier_value_categories(lint: Lint) -> None:
    """Close the 2 field-name lexicon and the 2.1 identifier value-category contract.

    Both contracts read the same schema population, so they share one walk and one
    entry point. NC-FIELDCASE-001 runs first and unconditionally: it is a property
    *name* judgement that must not be skipped by any of the early returns the
    classification registry can trigger.
    """

    documents = _schema_documents(lint)
    check_wire_property_name_case(lint, documents)

    prose_categories = _prose_categories(lint)
    registry = load_json(lint, IDENTIFIER_CLASSIFICATION_PATH)
    if not isinstance(registry, dict):
        return
    if registry.get("source_of_truth") is not False:
        lint.fail(
            IDENTIFIER_CLASSIFICATION_PATH,
            "the classification registry is derived from prose and schema types, not a truth source",
        )
    declared_categories = registry.get("categories")
    if not isinstance(declared_categories, list) or set(declared_categories) != prose_categories:
        lint.fail(
            IDENTIFIER_CLASSIFICATION_PATH,
            "categories must equal the identifier_category markers of common-fields.md 2.1: "
            f"prose={sorted(prose_categories)}",
        )
        return
    pending_only = registry.get("pending_convergence_categories")
    if not isinstance(pending_only, list) or not set(pending_only) <= prose_categories:
        lint.fail(
            IDENTIFIER_CLASSIFICATION_PATH,
            "pending_convergence_categories must be a subset of the declared categories",
        )
        pending_only = []

    id_kind_registry = load_json(lint, ID_KIND_REGISTRY_PATH)
    id_kinds = registered_id_kinds(id_kind_registry)
    if not id_kinds:
        lint.fail(ID_KIND_REGISTRY_PATH, "id_kinds must be a non-empty array of kind rows")
        return

    rows = registry.get("classifications")
    if not isinstance(rows, list):
        lint.fail(IDENTIFIER_CLASSIFICATION_PATH, "classifications must be an array")
        return

    index: dict[tuple[str, str], dict] = {}
    for position, row in enumerate(rows):
        where = f"classifications[{position}]"
        if not isinstance(row, dict):
            lint.fail(IDENTIFIER_CLASSIFICATION_PATH, f"{where} must be an object")
            continue
        name = row.get("name")
        signature = row.get("terminal_signature")
        category = row.get("category")
        if not isinstance(name, str) or not isinstance(signature, str):
            lint.fail(IDENTIFIER_CLASSIFICATION_PATH, f"{where} needs string name/terminal_signature")
            continue
        key = (name, signature)
        if key in index:
            lint.fail(IDENTIFIER_CLASSIFICATION_PATH, f"{where} duplicates {name} {signature}")
            continue
        index[key] = row
        if category not in prose_categories:
            lint.fail(
                IDENTIFIER_CLASSIFICATION_PATH,
                f"{where} uses category `{category}`, which 2.1 does not declare",
            )
        if not isinstance(row.get("reason"), str) or not row["reason"].strip():
            lint.fail(IDENTIFIER_CLASSIFICATION_PATH, f"{where} must justify its category")
        pending = row.get("pending_convergence", False)
        if not isinstance(pending, bool):
            lint.fail(IDENTIFIER_CLASSIFICATION_PATH, f"{where} pending_convergence must be boolean")
        elif category in pending_only and not pending:
            lint.fail(
                IDENTIFIER_CLASSIFICATION_PATH,
                f"{where} uses category `{category}`, which is only valid as pending convergence",
            )
        if not isinstance(row.get("occurrences"), int) or row["occurrences"] < 1:
            lint.fail(IDENTIFIER_CLASSIFICATION_PATH, f"{where}.occurrences must be positive")

    observed: dict[tuple[str, str], int] = {}
    decided: dict[str, int] = {}
    for file_name, document in documents.items():
        for occurrence in enumerate_schema_properties(file_name, document):
            name = occurrence.name
            if name != "id" and not name.endswith(IDENTIFIER_NAME_SUFFIXES):
                continue
            terminals = resolve_terminal_constraints(documents, file_name, occurrence.shape)
            category = derive_category(terminals, id_kinds)
            if category is None:
                signature = json.dumps(terminals, ensure_ascii=False, sort_keys=True)
                key = (name, signature)
                observed[key] = observed.get(key, 0) + 1
                registered = index.get(key)
                category = registered.get("category") if isinstance(registered, dict) else None
            else:
                decided[category] = decided.get(category, 0) + 1
            # An occurrence the type system cannot decide and the registry does
            # not classify is judged as if it owned nothing, so a newly widened
            # or newly minted terminal fails closed instead of slipping through
            # on the way to being registered.
            check_typed_id_namespace_disjointness(
                lint, file_name, occurrence.pointer, name, category, terminals
            )

    registered_counts = {key: row.get("occurrences") for key, row in index.items()}
    if registered_counts != observed:
        unregistered = sorted(set(observed) - set(index))
        stale = sorted(set(index) - set(observed))
        drift = sorted(
            (key[0], registered_counts[key], observed[key])
            for key in set(index) & set(observed)
            if registered_counts[key] != observed[key]
        )
        lint.fail(
            IDENTIFIER_CLASSIFICATION_PATH,
            "identifier classification drift: unregistered="
            f"{[f'{name} {signature}' for name, signature in unregistered[:5]]}, "
            f"stale={[f'{name} {signature}' for name, signature in stale[:5]]}, "
            f"count_drift={drift[:5]}",
        )

    summary = registry.get("type_derived_summary")
    if not isinstance(summary, dict) or summary != decided:
        lint.fail(
            IDENTIFIER_CLASSIFICATION_PATH,
            f"type_derived_summary is stale; recompute it as {decided}",
        )

    _check_pending_renames(lint, registry, documents)


def _check_pending_renames(lint: Lint, registry: dict, documents: dict[str, Any]) -> None:
    """Keep the queued identifier renames pinned to paths that still exist.

    These are field names whose value category is already decided and correct but
    whose spelling collides with another kind. The rename itself has to land in
    one batch across the schemas, the SDK and the implementation repositories, so
    the row exists to stop the collision from being forgotten -- and to fall over
    the moment the path it names stops matching, which is what happens once the
    rename lands and the row must be deleted.
    """

    rows = registry.get("pending_rename_convergence")
    if not isinstance(rows, list):
        lint.fail(IDENTIFIER_CLASSIFICATION_PATH, "pending_rename_convergence must be an array")
        return
    seen: set[tuple[str, str]] = set()
    for position, row in enumerate(rows):
        where = f"pending_rename_convergence[{position}]"
        if not isinstance(row, dict):
            lint.fail(IDENTIFIER_CLASSIFICATION_PATH, f"{where} must be an object")
            continue
        file_name = row.get("file")
        pointer = row.get("pointer")
        name = row.get("name")
        suggested = row.get("suggested_name")
        if not all(isinstance(value, str) and value for value in (file_name, pointer, name, suggested)):
            lint.fail(
                IDENTIFIER_CLASSIFICATION_PATH,
                f"{where} needs string file/pointer/name/suggested_name",
            )
            continue
        if not row.get("owner_batch") or not row.get("reason"):
            lint.fail(IDENTIFIER_CLASSIFICATION_PATH, f"{where} needs owner_batch and reason")
        if (file_name, pointer) in seen:
            lint.fail(IDENTIFIER_CLASSIFICATION_PATH, f"{where} duplicates {file_name}#{pointer}")
            continue
        seen.add((file_name, pointer))
        if suggested == name or not re.fullmatch(r"[a-z][a-z0-9_]*", suggested):
            lint.fail(
                IDENTIFIER_CLASSIFICATION_PATH,
                f"{where} suggested_name must be a different snake_case field name",
            )
        document = documents.get(file_name)
        if document is None:
            lint.fail(IDENTIFIER_CLASSIFICATION_PATH, f"{where} names an unknown schema {file_name}")
            continue
        if not pointer.endswith(f"/properties/{name}"):
            lint.fail(IDENTIFIER_CLASSIFICATION_PATH, f"{where} pointer must address `{name}`")
            continue
        try:
            resolve_json_pointer(document, f"#{pointer}")
        except (KeyError, TypeError, ValueError):
            lint.fail(
                IDENTIFIER_CLASSIFICATION_PATH,
                f"{where} no longer resolves; delete the row once the rename has landed",
            )


# --------------------------------------------------------------------------
# Duration field units (common-fields.md 3.0.2)
# --------------------------------------------------------------------------

# The closed noun table of 3.0.2, plus the generic `duration` noun itself. A
# field whose final word is one of these names a duration, so 3.0.2 decides its
# wire shape; a qualifier after the noun (`window_start`, `cooldown_after_reject`)
# names something about a duration rather than the duration itself, which is why
# only the final word is judged.
DURATION_NOUNS = frozenset(
    {"ttl", "timeout", "window", "period", "cooldown", "age", "staleness", "duration"}
)

# The one ISO 8601 duration pattern 3.0.2 admits on the wire. A duration string
# carrying any other pattern is either a homegrown compact mini-DSL or an
# unreviewed refinement; the clause bans the first and this check cannot prove
# the second is a refinement, so both fail unless excepted below.
ISO_8601_DURATION_PATTERN = (
    "^P(?:[0-9]+Y)?(?:[0-9]+M)?(?:[0-9]+W)?(?:[0-9]+D)?"
    "(?:T(?:[0-9]+H)?(?:[0-9]+M)?(?:[0-9]+S)?)?$"
)

# Exact-path exceptions, keyed by (schema file, RFC 6901 pointer, name) like
# every other naming exception surface. Each row is a noun-final field the
# closed table would reject even though 3.0.2 does not govern it; the check
# fails closed the moment a row stops matching a real violation, so an
# exception cannot outlive the field shape it was granted for.
DURATION_FIELD_EXCEPTIONS = (
    {
        "file": "calendar-event.schema.json",
        "pointer": "/$defs/n_day/properties/nth_of_period",
        "name": "nth_of_period",
        "reason": "An ordinal inside a recurrence period, not a duration; the "
        "integer counts position within the period, so no unit suffix applies.",
    },
    {
        "file": "grant-constraint.schema.json",
        "pointer": "/allOf/8/then/properties/period",
        "name": "period",
        "reason": "A reviewed refinement of the canonical ISO 8601 pattern that "
        "narrows quota recurrence periods to nonzero day/week granularity; it "
        "admits only values the canonical pattern already admits.",
    },
    {
        "file": "service-describe.schema.json",
        "pointer": "/properties/private_contact_discovery/properties/max_psi_queries_per_window",
        "name": "max_psi_queries_per_window",
        "reason": "A rate count per window, not the window's length; the integer "
        "counts queries, so no unit suffix applies.",
    },
    {
        "file": "invite-receive-policy.schema.json",
        "pointer": "/properties/new_source_quota/properties/new_sources_per_window",
        "name": "new_sources_per_window",
        "reason": "A new-source admission count per window, not the window's "
        "length; the integer counts sources, so no unit suffix applies.",
    },
    {
        "file": "invite-receive-policy.schema.json",
        "pointer": "/$defs/receive_policy_constraints/properties/new_source_quota/properties/default_new_sources_per_window",
        "name": "default_new_sources_per_window",
        "reason": "A default new-source admission count per window, not the "
        "window's length; the integer counts sources, so no unit suffix applies.",
    },
    {
        "file": "invite-receive-policy.schema.json",
        "pointer": "/$defs/receive_policy_constraints/properties/new_source_quota/properties/max_new_sources_per_window",
        "name": "max_new_sources_per_window",
        "reason": "A maximum new-source admission count per window, not the "
        "window's length; the integer counts sources, so no unit suffix applies.",
    },
)


def check_duration_field_units(lint: Lint) -> None:
    """Close NC-DURATION-001: duration fields carry their unit or the ISO pattern.

    3.0.2 fixes a closed noun table and a closed two-row scale table, so the
    clause is decidable on the resolved terminal: an integer duration must end
    in ``_ms`` / ``_seconds`` (which places the unit word after the noun, so a
    noun-final integer name is exactly the unitless shape), a string duration
    must carry the single ISO 8601 pattern, and a bare duration string is
    banned outright. An enum/const terminal is a closed label set such as
    ``on_timeout``, not a duration value, and is not judged.
    """

    documents = _schema_documents(lint)
    exceptions = {
        (row["file"], row["pointer"], row["name"]): row for row in DURATION_FIELD_EXCEPTIONS
    }
    used: set[tuple[str, str, str]] = set()
    for file_name, document in documents.items():
        for occurrence in enumerate_schema_properties(file_name, document):
            words = split_name_words(occurrence.name)
            if not words or words[-1] not in DURATION_NOUNS:
                continue
            terminals = resolve_terminal_constraints(documents, file_name, occurrence.shape)
            patterns = [value for kind, value in terminals if kind == "pattern"]
            is_integer = any(
                kind == "type" and '"integer"' in value for kind, value in terminals
            )
            is_string = any(
                kind == "type" and '"string"' in value for kind, value in terminals
            )
            has_label_set = any(kind in {"enum", "const"} for kind, _value in terminals)
            violation: str | None = None
            if is_integer:
                violation = (
                    f"`{occurrence.name}` is an integer duration field whose name carries "
                    f"no unit suffix; 3.0.2 admits `_ms` or `_seconds` chosen by the "
                    f"closed scale table"
                )
            elif patterns:
                off_pattern = [p for p in patterns if p != ISO_8601_DURATION_PATTERN]
                if off_pattern:
                    violation = (
                        f"`{occurrence.name}` is a duration string whose pattern is not the "
                        f"single ISO 8601 duration pattern of 3.0.2: {off_pattern}"
                    )
            elif is_string and not has_label_set:
                violation = (
                    f"`{occurrence.name}` is a bare duration string with no pattern; 3.0.2 "
                    f"requires the ISO 8601 duration pattern on every wire duration string"
                )
            if violation is None:
                continue
            key = (file_name, occurrence.pointer, occurrence.name)
            if key in exceptions:
                used.add(key)
                continue
            lint.fail(
                SCHEMA_DIR / file_name,
                f"{occurrence.pointer} violates NC-DURATION-001: {violation}",
            )
    for key in sorted(set(exceptions) - used):
        lint.fail(
            SCHEMA_DIR / key[0],
            f"NC-DURATION-001 exception {key[1]} no longer matches a violating occurrence; "
            f"delete the stale row",
        )


# --------------------------------------------------------------------------
# Slug field closure (common-fields.md 3.0.3)
# --------------------------------------------------------------------------

# Reference form: `<entity>_slug`, optionally carrying a role / time qualifier
# (`agent_slug_at_time`). The entity prefix must be an entity whose owning
# context is registered, which is what stops a reference to a slug-bearing
# object from being coined before the object itself exists on the wire.
SLUG_REFERENCE_RE = re.compile(r"\A([a-z][a-z0-9]*)_slug(?:_.+)?\Z")


def check_slug_field_closure(lint: Lint) -> None:
    """Close NC-SLUG-001: bare `slug` only where the registry names the owning object.

    3.0.3 splits slug fields into the owning object's bare ``slug`` (shared by
    the DTOs that create, update or project that one object) and every other
    context's ``<entity>_slug``. The split is decidable once each schema
    declares which side it is on; ``tools/slug-field-registry.json`` is that
    declaration, and this check closes the wire surface against it in both
    directions so the registry cannot drift from the schemas in either
    direction.
    """

    registry = load_json(lint, SLUG_FIELD_REGISTRY_PATH)
    if not isinstance(registry, dict):
        return
    if registry.get("source_of_truth") is not False:
        lint.fail(
            SLUG_FIELD_REGISTRY_PATH,
            "the slug field registry is derived from prose and schemas, not a truth source",
        )
    entities = registry.get("entities")
    if not isinstance(entities, list) or not entities:
        lint.fail(SLUG_FIELD_REGISTRY_PATH, "entities must be a non-empty array")
        return

    documents = _schema_documents(lint)
    registered_contexts: dict[tuple[str, str], dict] = {}
    entity_names: set[str] = set()
    for position, entity in enumerate(entities):
        where = f"entities[{position}]"
        if not isinstance(entity, dict):
            lint.fail(SLUG_FIELD_REGISTRY_PATH, f"{where} must be an object")
            continue
        name = entity.get("entity")
        if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9]*", name):
            lint.fail(SLUG_FIELD_REGISTRY_PATH, f"{where} needs a snake_case entity word")
            continue
        if name in entity_names:
            lint.fail(SLUG_FIELD_REGISTRY_PATH, f"{where} duplicates entity `{name}`")
        entity_names.add(name)
        contexts = entity.get("owning_contexts")
        if not isinstance(contexts, list) or not contexts:
            lint.fail(
                SLUG_FIELD_REGISTRY_PATH,
                f"{where} needs a non-empty owning_contexts list; an entity without an "
                f"owning object may not be referenced",
            )
            continue
        for index, context in enumerate(contexts):
            cwhere = f"{where}.owning_contexts[{index}]"
            if not isinstance(context, dict):
                lint.fail(SLUG_FIELD_REGISTRY_PATH, f"{cwhere} must be an object")
                continue
            file_name = context.get("file")
            pointer = context.get("pointer")
            if (
                not isinstance(file_name, str)
                or not isinstance(pointer, str)
                or not pointer.endswith("/properties/slug")
            ):
                lint.fail(
                    SLUG_FIELD_REGISTRY_PATH,
                    f"{cwhere} needs a schema file and a pointer addressing a bare `slug` property",
                )
                continue
            if not isinstance(context.get("reason"), str) or not context["reason"].strip():
                lint.fail(
                    SLUG_FIELD_REGISTRY_PATH,
                    f"{cwhere} must state why this context is the owning object",
                )
            key = (file_name, pointer)
            if key in registered_contexts:
                lint.fail(SLUG_FIELD_REGISTRY_PATH, f"{cwhere} duplicates {file_name}#{pointer}")
                continue
            registered_contexts[key] = context
            document = documents.get(file_name)
            if document is None:
                lint.fail(SLUG_FIELD_REGISTRY_PATH, f"{cwhere} names an unknown schema {file_name}")
                continue
            try:
                resolve_json_pointer(document, f"#{pointer}")
            except (KeyError, TypeError, ValueError):
                lint.fail(
                    SLUG_FIELD_REGISTRY_PATH,
                    f"{cwhere} no longer resolves; the bare `slug` it pinned is gone",
                )

    observed_bare: set[tuple[str, str]] = set()
    for file_name, document in documents.items():
        for occurrence in enumerate_schema_properties(file_name, document):
            if "slug" not in split_name_words(occurrence.name):
                continue
            if occurrence.name == "slug":
                key = (file_name, occurrence.pointer)
                observed_bare.add(key)
                if key not in registered_contexts:
                    lint.fail(
                        SCHEMA_DIR / file_name,
                        f"{occurrence.pointer} violates NC-SLUG-001: bare `slug` is reserved "
                        f"for the owning object's canonical slug field (3.0.3); register the "
                        f"owning context in {SLUG_FIELD_REGISTRY_PATH.name} or rename the "
                        f"reference to `<entity>_slug`",
                    )
                continue
            reference = SLUG_REFERENCE_RE.fullmatch(occurrence.name)
            if reference is None:
                lint.fail(
                    SCHEMA_DIR / file_name,
                    f"{occurrence.pointer} violates NC-SLUG-001: a slug reference MUST be "
                    f"named `<entity>_slug` with an optional role/time qualifier, got "
                    f"`{occurrence.name}`",
                )
                continue
            if reference.group(1) not in entity_names:
                lint.fail(
                    SCHEMA_DIR / file_name,
                    f"{occurrence.pointer} violates NC-SLUG-001: `{occurrence.name}` references "
                    f"entity `{reference.group(1)}`, which has no registered slug-owning "
                    f"context; register the owning object first",
                )

    if observed_bare != set(registered_contexts):
        lint.fail(
            SLUG_FIELD_REGISTRY_PATH,
            "slug owning-context drift: unregistered="
            f"{sorted(observed_bare - set(registered_contexts))}, "
            f"stale={sorted(set(registered_contexts) - observed_bare)}",
        )
