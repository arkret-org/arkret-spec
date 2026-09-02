"""Regression lock for adjudicated derived wire field deletions.

`derived-wire-field-removal-lock.json` carries one row per exact
`(schema, path, removed)` triple that a ruling deleted because the member is a
pure function of members that stay on the wire. The gate is a lock, not a
detector: it never infers a projection from a field name. Every row must keep
pointing at a real schema object, the removed member must stay out of that
object's explicit property and required sets (including its overlays), and the
declared source member must stay declared, so the projection cannot quietly
lose the thing it is recomputed from.

Sibling digests deleted under encoding.md 4.0.1 stay locked by
`schemas.CONTENT_ADDRESSED_REF_MIRROR_REMOVALS`; a row here that repeats one of
those triples is rejected so the two locks never disagree about an owner.
"""

from __future__ import annotations

from .core import (
    ARTIFACTS,
    ROOT,
    Any,
    Lint,
    load_json,
    markdown_section_body,
    re,
    read_text,
)
from .schema_members import (
    explicit_properties,
    explicit_required,
    load_schema_documents,
    walk_pointer,
)
from .schemas import CONTENT_ADDRESSED_REF_MIRROR_REMOVALS

LOCK_PATH = ARTIFACTS / "registry" / "derived-wire-field-removal-lock.json"

LOCK_KIND = "derived_wire_field_removals"

MACHINE_GATE = "tools/artifact_lint:derived_wire_field_removals"

ROW_KEYS = ("lock_id", "ruling", "schema", "path", "removed", "source", "derivation", "spec_anchor")

SOURCE_KEYS = frozenset({"schema", "path", "field"})

LOCK_ID_RE = re.compile(r"^ak\.lock\.derived_wire_field_removal\.[a-z0-9_]+\.v1$")

VERSION_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.\d+$")


def _mirror_lock_triples() -> set[tuple[str, str, str]]:
    triples: set[tuple[str, str, str]] = set()
    for file_name, path, _id_field, digest_field in CONTENT_ADDRESSED_REF_MIRROR_REMOVALS:
        pointer = "".join(f"/{segment}" for segment in path)
        triples.add((file_name, pointer, digest_field))
    return triples


def _resolve_object(docs: dict[str, Any], schema: str, pointer: str) -> tuple[str, Any]:
    file_name = schema.removeprefix("schemas/")
    document = docs.get(file_name)
    if document is None:
        return file_name, None
    node = walk_pointer(document, pointer)
    return file_name, node if isinstance(node, dict) else None


def load_derived_wire_field_removals(lint: Lint) -> list[dict[str, Any]]:
    """Validate the lock file's shape and return its structurally sound rows."""
    data = load_json(lint, LOCK_PATH)
    if not isinstance(data, dict):
        return []
    if data.get("source_of_truth") is not True:
        lint.fail(LOCK_PATH, "source_of_truth must be true; the lock is hand-adjudicated, not generated")
    if not isinstance(data.get("version"), str) or not VERSION_RE.match(data["version"]):
        lint.fail(LOCK_PATH, "version must look like YYYY-MM-DD.N")
    if data.get("lock_kind") != LOCK_KIND:
        lint.fail(LOCK_PATH, f"lock_kind must be {LOCK_KIND}")
    rules = data.get("registry_rules")
    if not isinstance(rules, dict):
        lint.fail(LOCK_PATH, "registry_rules must be an object")
        rules = {}
    if rules.get("machine_gate") != MACHINE_GATE:
        lint.fail(LOCK_PATH, f"registry_rules.machine_gate must be {MACHINE_GATE}")
    if list(rules.get("row_keys") or []) != list(ROW_KEYS):
        lint.fail(LOCK_PATH, f"registry_rules.row_keys must be exactly {list(ROW_KEYS)}")
    if "CONTENT_ADDRESSED_REF_MIRROR_REMOVALS" not in str(rules.get("division_of_labor", "")):
        lint.fail(LOCK_PATH, "registry_rules.division_of_labor must name CONTENT_ADDRESSED_REF_MIRROR_REMOVALS as the 4.0.1 owner")
    rows = data.get("removals")
    if not isinstance(rows, list) or not rows:
        lint.fail(LOCK_PATH, "removals must be a non-empty list")
        return []

    sound: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_triples: set[tuple[str, str, str]] = set()
    mirror_triples = _mirror_lock_triples()
    for index, row in enumerate(rows):
        label = f"removals[{index}]"
        if not isinstance(row, dict):
            lint.fail(LOCK_PATH, f"{label} must be an object")
            continue
        lock_id = row.get("lock_id")
        if not isinstance(lock_id, str) or not LOCK_ID_RE.match(lock_id):
            lint.fail(LOCK_PATH, f"{label}.lock_id must match registry_rules.lock_id_pattern")
            continue
        label = lock_id
        if lock_id in seen_ids:
            lint.fail(LOCK_PATH, f"{label}: duplicate lock_id")
            continue
        seen_ids.add(lock_id)
        if tuple(row.keys()) != ROW_KEYS:
            lint.fail(LOCK_PATH, f"{label}: keys must be exactly {list(ROW_KEYS)} in that order")
            continue
        ruling = row["ruling"]
        if not isinstance(ruling, str) or not ruling.strip() or "/" in ruling or "\\" in ruling:
            lint.fail(LOCK_PATH, f"{label}.ruling must be a short adjudication label, never a repository path")
            continue
        schema = row["schema"]
        if not isinstance(schema, str) or not schema.startswith("schemas/") or not (ARTIFACTS / schema).is_file():
            lint.fail(LOCK_PATH, f"{label}.schema must name an existing artifacts/schemas file")
            continue
        path = row["path"]
        if not isinstance(path, str) or (path != "" and not path.startswith("/")):
            lint.fail(LOCK_PATH, f"{label}.path must be '' or a JSON Pointer starting with /")
            continue
        removed = row["removed"]
        if not isinstance(removed, str) or not removed:
            lint.fail(LOCK_PATH, f"{label}.removed must be a non-empty member name")
            continue
        source = row["source"]
        if (
            not isinstance(source, dict)
            or not set(source) <= SOURCE_KEYS
            or not isinstance(source.get("field"), str)
            or not source["field"]
            or any(not isinstance(source[key], str) for key in ("schema", "path") if key in source)
        ):
            lint.fail(LOCK_PATH, f"{label}.source must be an object with field and optional schema/path strings")
            continue
        if (
            source["field"] == removed
            and source.get("schema", schema) == schema
            and source.get("path", path) == path
        ):
            lint.fail(LOCK_PATH, f"{label}: source must not be the removed member itself")
            continue
        derivation = row["derivation"]
        if not isinstance(derivation, str) or len(derivation.strip()) < 10:
            lint.fail(LOCK_PATH, f"{label}.derivation must state the recomputation in the words of the ruling")
            continue
        anchor = row["spec_anchor"]
        if not isinstance(anchor, str) or not anchor:
            lint.fail(LOCK_PATH, f"{label}.spec_anchor must be a non-empty string")
            continue
        file_part, _, heading = anchor.partition("#")
        if not file_part.startswith("spec/v1/zh/") or not (ROOT / file_part).is_file():
            lint.fail(LOCK_PATH, f"{label}.spec_anchor must point at an existing spec/v1/zh prose file")
            continue
        if heading and markdown_section_body(read_text(ROOT / file_part), heading) is None:
            lint.fail(LOCK_PATH, f"{label}.spec_anchor heading #{heading} does not exist in {file_part}")
            continue
        triple = (schema.removeprefix("schemas/"), path, removed)
        if triple in seen_triples:
            lint.fail(LOCK_PATH, f"{label}: duplicate (schema, path, removed) {triple}")
            continue
        seen_triples.add(triple)
        if triple in mirror_triples:
            lint.fail(
                LOCK_PATH,
                f"{label}: {triple} is a 4.0.1 sibling digest owned by CONTENT_ADDRESSED_REF_MIRROR_REMOVALS; "
                "one deletion has one lock",
            )
            continue
        sound.append(row)
    return sound


def check_derived_wire_field_removals(lint: Lint) -> None:
    """Every locked deletion stays deleted and keeps the member it is recomputed from."""
    rows = load_derived_wire_field_removals(lint)
    if not rows:
        return
    docs = load_schema_documents(lint)
    for row in rows:
        label = row["lock_id"]
        schema, path, removed = row["schema"], row["path"], row["removed"]
        file_name, node = _resolve_object(docs, schema, path)
        schema_path = ARTIFACTS / "schemas" / file_name
        if node is None:
            lint.fail(
                schema_path,
                f"{label}: locked object {path or '/'} no longer resolves to a schema object; "
                "retarget the row to where the carrier moved or retire it with the ruling",
            )
            continue
        properties = explicit_properties(docs, file_name, node)
        required = explicit_required(docs, file_name, node)
        if removed in properties or removed in required:
            lint.fail(
                schema_path,
                f"{label}: {path or '/'} carries {removed} again; the {row['ruling']} ruling deleted it "
                f"({row['derivation']})",
            )
        source = row["source"]
        source_schema = source.get("schema", schema)
        source_path = source.get("path", path)
        source_file, source_node = _resolve_object(docs, source_schema, source_path)
        source_schema_path = ARTIFACTS / "schemas" / source_file
        if source_node is None:
            lint.fail(
                source_schema_path,
                f"{label}: source object {source_path or '/'} no longer resolves to a schema object",
            )
            continue
        if source["field"] not in explicit_properties(docs, source_file, source_node):
            lint.fail(
                source_schema_path,
                f"{label}: {source_path or '/'} must keep declaring {source['field']}; "
                f"{removed} is recomputed from it ({row['derivation']})",
            )
