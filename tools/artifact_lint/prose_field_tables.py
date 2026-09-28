"""Normative prose field tables must name exactly what the schema object declares.

A normative field table in `spec/v1/zh` and the schema object it documents are
two spellings of one contract, and nothing compared them. The failure mode is
not hypothetical: `member_roster_entry` was renamed in
`account-subscribe-frame.schema.json` while `sync/client-sync.md` kept the old
row, so one implementation read the prose name and one read the schema name and
both passed their own tests. The schema descriptions of the same object kept the
old name too, which is why the drift stayed invisible for a month.

This gate closes both halves for every registered binding:

* the table rows and the schema properties MUST carry the same names in the same
  order, so a rename, an addition or a removal on either side is a lint error;
* every field name mentioned inside that object's own descriptions MUST either be
  declared by the object or be listed in `external_field_mentions`, and an
  allowlist entry nothing mentions fails too, because a stale allowlist is how a
  whitelist stops describing what it guards.

Field order follows the schema: `check_field_order` already gates the schema side
against `models/common-fields.md` §3, so the schema object is the ordered form
the prose table has to mirror.
"""

from __future__ import annotations

from .core import ARTIFACTS, Any, Lint, Path, SPEC_ROOT, TOOLS_ROOT, load_json, re
from .schema_members import explicit_properties, locate

REGISTRY_PATH = TOOLS_ROOT / "prose-field-table-registry.json"
OPERATION_NOTE_EXEMPTIONS_PATH = TOOLS_ROOT / "operation-note-field-exemptions.json"
OPERATION_REGISTRY_PATH = ARTIFACTS / "registry" / "operation-registry.json"

SCHEMAS = ARTIFACTS / "schemas"

TABLE_ROW = re.compile(r"^\|(?P<body>.+)\|\s*$")

TABLE_DIVIDER = re.compile(r"^\|[\s:|-]+\|\s*$")

FIELD_CELL = re.compile(r"^`(?P<name>[a-z][a-z0-9_]*)(?:\[\])?`$")

FIELD_TOKEN = re.compile(
    r"(?<![A-Za-z0-9_.])([a-z][a-z0-9]*(?:_[a-z0-9]+)+)(?![A-Za-z0-9_]|\.[a-z])"
)

MIN_TABLE_ROWS = 3


def _resolve_pointer(document: Any, fragment: str) -> Any:
    node = document
    for raw in fragment.lstrip("#").split("/"):
        if not raw:
            continue
        segment = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict) and segment in node:
            node = node[segment]
        elif isinstance(node, list) and segment.isdigit() and int(segment) < len(node):
            node = node[int(segment)]
        else:
            return None
    return node


def field_tables(text: str) -> list[tuple[int, list[str]]]:
    """Every markdown table whose first column is only backticked field names."""
    tables: list[tuple[int, list[str]]] = []
    lines = text.split("\n")
    index = 0
    while index < len(lines):
        header = TABLE_ROW.match(lines[index])
        if header and index + 1 < len(lines) and TABLE_DIVIDER.match(lines[index + 1]):
            cursor = index + 2
            names: list[str] = []
            complete = True
            while cursor < len(lines) and TABLE_ROW.match(lines[cursor]):
                cell = lines[cursor].split("|")[1].strip()
                match = FIELD_CELL.match(cell)
                if match is None:
                    complete = False
                names.append(match.group("name") if match else "")
                cursor += 1
            if complete and len(names) >= MIN_TABLE_ROWS:
                tables.append((index + 1, names))
            index = cursor
        else:
            index += 1
    return tables


def locate_tables(
    text: str, wanted: list[list[str]]
) -> list[tuple[int, list[str]] | None]:
    """Assign one table per requested property list, exact matches first.

    A document often carries several field tables whose property sets nest
    (request body, outcome, unregister body). Overlap alone then hands two
    bindings the same table, so the exact sets are claimed first and only the
    drifted binding falls back to best overlap among what is left.
    """
    tables = field_tables(text)
    claimed: set[int] = set()
    located: list[tuple[int, list[str]] | None] = [None] * len(wanted)
    for position, declared in enumerate(wanted):
        for index, (line_no, names) in enumerate(tables):
            if index not in claimed and names == declared:
                located[position] = (line_no, names)
                claimed.add(index)
                break
    for position, declared in enumerate(wanted):
        if located[position] is not None:
            continue
        target = set(declared)
        best_index = None
        best_score = 0
        for index, (_line_no, names) in enumerate(tables):
            if index in claimed:
                continue
            score = len(target & set(names))
            if score > best_score:
                best_index, best_score = index, score
        if best_index is None or best_score * 2 < len(target):
            continue
        claimed.add(best_index)
        located[position] = tables[best_index]
    return located


def _described_names(node: dict[str, Any]) -> set[str]:
    texts: list[str] = []
    if isinstance(node.get("description"), str):
        texts.append(node["description"])
    for subschema in (node.get("properties") or {}).values():
        if isinstance(subschema, dict) and isinstance(subschema.get("description"), str):
            texts.append(subschema["description"])
    found: set[str] = set()
    for text in texts:
        found.update(FIELD_TOKEN.findall(text))
    return found


def _property_vocabulary(documents: dict[str, Any]) -> set[str]:
    vocabulary: set[str] = set()

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            properties = node.get("properties")
            if isinstance(properties, dict):
                vocabulary.update(name for name in properties if isinstance(name, str))
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    for document in documents.values():
        visit(document)
    return vocabulary


def operation_note_field_drift(
    operations: list[Any],
    documents: dict[str, Any],
    exemptions: dict[str, Any],
) -> list[str]:
    """Return closed-schema drift found in operation ``notes``.

    A field token that exists somewhere in the schema vocabulary must either
    belong to this operation's request/response schema closure or be declared
    as an intentional cross-object mention. Requiring the exemption inventory
    to match exactly makes stale exemptions fail as well.
    """
    vocabulary = _property_vocabulary(documents)
    operation_exemptions = exemptions.get("operations")
    if not isinstance(operation_exemptions, dict):
        return ["operation note field exemptions must declare an operations object"]

    errors: list[str] = []
    seen: set[str] = set()
    for operation in operations:
        if not isinstance(operation, dict) or not isinstance(operation.get("operation_id"), str):
            continue
        operation_id = operation["operation_id"]
        seen.add(operation_id)
        notes = operation.get("notes")
        if not isinstance(notes, str):
            notes = ""
        mentioned = set(FIELD_TOKEN.findall(notes)) & vocabulary
        declared: set[str] = set()
        for key in ("request_schema_ref", "response_schema_ref"):
            schema_ref = operation.get(key)
            if not isinstance(schema_ref, str):
                continue
            file_name, _fragment, node = locate(documents, schema_ref)
            pending = [(file_name, node)]
            visited: set[tuple[str, int]] = set()
            while pending:
                owner_file, current = pending.pop()
                marker = (owner_file, id(current))
                if marker in visited or not isinstance(current, dict):
                    continue
                visited.add(marker)
                properties = explicit_properties(documents, owner_file, current)
                declared.update(properties)
                pending.extend(properties.values())
                items = current.get("items")
                if isinstance(items, dict):
                    pending.append((owner_file, items))
        external = mentioned - declared
        allowed = operation_exemptions.get(operation_id, [])
        if not isinstance(allowed, list) or any(not isinstance(name, str) for name in allowed):
            errors.append(f"{operation_id} exemptions must be a string array")
            continue
        if allowed != sorted(set(allowed)):
            errors.append(f"{operation_id} exemptions must be sorted and unique")
            continue
        for name in sorted(external - set(allowed)):
            errors.append(
                f"{operation_id} notes name `{name}`, which its request/response schemas do not declare"
            )
        for name in sorted(set(allowed) - external):
            errors.append(
                f"{operation_id} exempts `{name}`, but the notes make no such cross-object mention"
            )
    for operation_id in sorted(set(operation_exemptions) - seen):
        errors.append(f"operation note exemptions name unknown operation {operation_id}")
    return errors


def check_prose_field_tables(lint: Lint) -> None:
    registry = load_json(lint, REGISTRY_PATH)
    if not isinstance(registry, dict):
        return
    bindings = registry.get("bindings")
    if not isinstance(bindings, list):
        lint.fail(REGISTRY_PATH, "prose field table registry must declare a bindings array")
        return

    documents = {
        path.name: load_json(lint, path) for path in sorted(SCHEMAS.glob("*.schema.json"))
    }
    vocabulary = _property_vocabulary(documents)

    operation_registry = load_json(lint, OPERATION_REGISTRY_PATH)
    exemptions = load_json(lint, OPERATION_NOTE_EXEMPTIONS_PATH)
    operations = operation_registry.get("operations") if isinstance(operation_registry, dict) else None
    if not isinstance(operations, list):
        lint.fail(OPERATION_REGISTRY_PATH, "operation registry must declare an operations array")
    elif isinstance(exemptions, dict):
        if set(exemptions) != {
            "version",
            "source_of_truth",
            "generated_at",
            "description",
            "operations",
        }:
            lint.fail(
                OPERATION_NOTE_EXEMPTIONS_PATH,
                "operation note field exemptions have an open or incomplete shape",
            )
        if (
            not isinstance(exemptions.get("version"), int)
            or isinstance(exemptions.get("version"), bool)
            or exemptions["version"] < 1
            or exemptions.get("source_of_truth") is not False
        ):
            lint.fail(
                OPERATION_NOTE_EXEMPTIONS_PATH,
                "operation note field exemptions must have a positive integer version and be a non-authoritative lint inventory",
            )
        for error in operation_note_field_drift(operations, documents, exemptions):
            lint.fail(OPERATION_NOTE_EXEMPTIONS_PATH, error)

    seen: set[tuple[str, str]] = set()
    resolved: list[tuple[dict[str, Any], str, str, list[str]]] = []
    for binding in bindings:
        if not isinstance(binding, dict):
            lint.fail(REGISTRY_PATH, "each prose field table binding must be an object")
            continue
        document_name = binding.get("document")
        schema_ref = binding.get("schema_ref")
        if not isinstance(document_name, str) or not isinstance(schema_ref, str):
            lint.fail(REGISTRY_PATH, "each binding must declare document and schema_ref strings")
            continue
        key = (document_name, schema_ref)
        if key in seen:
            lint.fail(REGISTRY_PATH, f"duplicate prose field table binding {schema_ref}")
            continue
        seen.add(key)

        file_name, _, fragment = schema_ref.partition("#")
        schema_document = documents.get(file_name)
        if schema_document is None:
            lint.fail(REGISTRY_PATH, f"binding names unknown schema document {file_name}")
            continue
        node = _resolve_pointer(schema_document, fragment)
        if not isinstance(node, dict) or not isinstance(node.get("properties"), dict):
            lint.fail(REGISTRY_PATH, f"binding {schema_ref} does not resolve to a schema object")
            continue
        declared = [name for name in node["properties"] if isinstance(name, str)]
        resolved.append((binding, document_name, schema_ref, declared))

        allowed = binding.get("external_field_mentions") or []
        if not isinstance(allowed, list):
            lint.fail(REGISTRY_PATH, f"{schema_ref} external_field_mentions must be an array")
            continue
        mentioned = _described_names(node)
        external = {name for name in mentioned if name in vocabulary and name not in declared}
        schema_path = SCHEMAS / file_name
        for name in sorted(external - set(allowed)):
            lint.fail(
                schema_path,
                f"{schema_ref} descriptions name `{name}`, which the object does not declare; "
                "register it as a cross-object mention or fix the stale field name",
            )
        for name in sorted(set(allowed) - external):
            lint.fail(
                REGISTRY_PATH,
                f"{schema_ref} allows external mention `{name}` that no description makes; "
                "an allowlist entry nothing exercises stops describing what it guards",
            )

    by_document: dict[str, list[tuple[str, list[str]]]] = {}
    for _binding, document_name, schema_ref, declared in resolved:
        by_document.setdefault(document_name, []).append((schema_ref, declared))

    for document_name, entries in sorted(by_document.items()):
        markdown_path = SPEC_ROOT.parent.parent / document_name
        if not markdown_path.is_file():
            markdown_path = Path(document_name)
        if not markdown_path.is_file():
            lint.fail(REGISTRY_PATH, f"binding names missing document {document_name}")
            continue
        text = markdown_path.read_text(encoding="utf-8")
        located = locate_tables(text, [declared for _ref, declared in entries])
        for (schema_ref, declared), table in zip(entries, located):
            if table is None:
                lint.fail(
                    markdown_path,
                    f"no field table here documents {schema_ref}; the binding is registered but "
                    "the table was renamed, split or removed",
                )
                continue
            line_no, names = table
            if names == declared:
                continue
            for name in sorted(set(names) - set(declared)):
                lint.fail(
                    markdown_path,
                    f"line {line_no}: field table row `{name}` is not a property of {schema_ref}",
                )
            for name in sorted(set(declared) - set(names)):
                lint.fail(
                    markdown_path,
                    f"line {line_no}: {schema_ref} declares `{name}` but the field table omits it",
                )
            if set(names) == set(declared):
                lint.fail(
                    markdown_path,
                    f"line {line_no}: field table order {names} does not match the "
                    f"{schema_ref} property order {declared}",
                )
