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
from .naming import PREDICATES, enumerate_schema_properties

NAMING_COVERAGE_MATRIX_PATH = TOOLS_ROOT / "naming-rule-coverage-matrix.json"
IDENTIFIER_CLASSIFICATION_PATH = TOOLS_ROOT / "identifier-classification-registry.json"
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
        elif isinstance(node.get("format"), str):
            out.add(("format", node["format"]))
        elif "type" in node:
            declared = node["type"]
            if declared != "null":
                out.add(("type", json.dumps(declared, sort_keys=True)))
        return out

    return tuple(sorted(visit(file_name, shape)))


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
                    categories.add("responsibility_did")
                    continue
                if slug in id_kinds:
                    categories.add("typed_object_id")
                    continue
                return None
            if _DID_PREFIX_RE.match(value):
                categories.add("responsibility_did")
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
    """Close the 2.1 identifier value-category contract against schema types."""

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

    documents = _schema_documents(lint)
    observed: dict[tuple[str, str], int] = {}
    decided: dict[str, int] = {}
    for file_name, document in documents.items():
        for occurrence in enumerate_schema_properties(file_name, document):
            name = occurrence.name
            if name != "id" and not name.endswith(IDENTIFIER_NAME_SUFFIXES):
                continue
            terminals = resolve_terminal_constraints(documents, file_name, occurrence.shape)
            category = derive_category(terminals, id_kinds)
            if category is not None:
                decided[category] = decided.get(category, 0) + 1
                continue
            signature = json.dumps(terminals, ensure_ascii=False, sort_keys=True)
            key = (name, signature)
            observed[key] = observed.get(key, 0) + 1

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
