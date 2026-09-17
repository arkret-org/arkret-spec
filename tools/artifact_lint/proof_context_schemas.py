"""Proof-context object families must own a registered schema.

``proof-context-registry.json`` is the closed inventory of signing surfaces: a
``contexts[]`` row anchors a terminal use point of the shared Event detached-proof
leaf, and a ``domain_separations[]`` row with primitive ``detached_signature``
anchors a locally declared signature leaf. Either way the row names an
``object_family`` -- a real wire object that some producer signs and some
receiver verifies.

Before this gate a row could name an object family that no schema described.
``controller_account_gate_attestation`` sat in ``domain_separations[]`` with ten
``binding_fields`` and no ``schema_ref`` at all, so the registry promised a
signed object whose members, types and closure existed only in prose; a
downstream implementation had to guess them, and a ``schema`` member spelling an
unregistered ``ak.schema.*.v1`` id could not be caught anywhere. The existing
``check_proof_context_registry`` closes the shared-proof surface in both
directions but treats ``domain_separations[].schema_ref`` as optional, so this
hole was invisible to it.

The rule, per in-scope row:

* the row MUST declare ``schema_ref`` or a non-empty ``transcript_schema_refs``;
* every referenced file MUST be an ``active`` row of ``schema-registry.json``,
  so the object family is covered by a registered ``ak.schema.*.v1`` id;
* every reference MUST resolve to a real schema object inside that file.

Primitives that are transcripts or namespaces rather than standalone wire
objects (``merkle_*``, ``hpke_info``, ``replay_cache_namespace``,
``canonical_json_sha256``, ``http_message_signature``) are out of scope by
construction: they bind bytes assembled from an enclosing carrier, not an object
family of their own.

``check_result_write_contracts`` is in the same module for the same reason: a
``result_writes[]`` contract that no gate reads is the same failure mode one
level down.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .core import ARTIFACTS, Lint, load_json, resolve_json_pointer

PROOF_CONTEXT_REGISTRY = ARTIFACTS / "registry" / "proof-context-registry.json"
SCHEMA_REGISTRY = ARTIFACTS / "registry" / "schema-registry.json"
EVENT_KIND_REGISTRY = ARTIFACTS / "registry" / "event-kind-registry.json"

# Only these primitives describe a standalone signed wire object. Everything else
# in DOMAIN_SEPARATION_PRIMITIVES binds bytes gathered from an enclosing carrier.
OBJECT_BEARING_PRIMITIVES = frozenset({"detached_signature"})


def _registered_schema_files(lint: Lint) -> tuple[set[str], dict[str, str]] | None:
    registry = load_json(lint, SCHEMA_REGISTRY)
    rows = registry.get("schemas") if isinstance(registry, dict) else None
    if not isinstance(rows, list) or not rows:
        lint.fail(SCHEMA_REGISTRY, "schemas[] must be a non-empty array")
        return None
    files: set[str] = set()
    effective: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("status", "active") != "active":
            continue
        file_ref = row.get("file")
        schema_id = row.get("schema_id")
        if not isinstance(file_ref, str) or not isinstance(schema_id, str):
            continue
        files.add(file_ref)
        fragment = row.get("fragment")
        effective[file_ref + (fragment if isinstance(fragment, str) else "")] = schema_id
    return files, effective


def _covering_schema_id(effective: dict[str, str], file_ref: str, fragment: str) -> str | None:
    """The registered id whose effective reference best covers ``file_ref#fragment``."""
    best: tuple[int, str] | None = None
    for reference, schema_id in effective.items():
        ref_file, _, ref_fragment = reference.partition("#")
        if ref_file != file_ref:
            continue
        ref_pointer = f"#{ref_fragment}" if ref_fragment else ""
        if ref_pointer and not (fragment == ref_pointer or fragment.startswith(ref_pointer + "/")):
            continue
        if best is None or len(ref_pointer) > best[0]:
            best = (len(ref_pointer), schema_id)
    return None if best is None else best[1]


def _in_scope_rows(data: dict[str, Any]) -> list[tuple[str, int, dict[str, Any]]]:
    rows: list[tuple[str, int, dict[str, Any]]] = []
    for index, row in enumerate(data.get("contexts") or []):
        if isinstance(row, dict):
            rows.append(("contexts", index, row))
    for index, row in enumerate(data.get("domain_separations") or []):
        if isinstance(row, dict) and row.get("primitive") in OBJECT_BEARING_PRIMITIVES:
            rows.append(("domain_separations", index, row))
    return rows


def check_proof_context_object_family_schemas(lint: Lint) -> None:
    """Every signing object family must resolve to a registered schema."""
    data = load_json(lint, PROOF_CONTEXT_REGISTRY)
    if not isinstance(data, dict):
        lint.fail(PROOF_CONTEXT_REGISTRY, "proof context registry must be an object")
        return
    registered = _registered_schema_files(lint)
    if registered is None:
        return
    files, effective = registered

    documents: dict[str, Any] = {}

    def document(file_ref: str) -> Any:
        if file_ref not in documents:
            path = ARTIFACTS / file_ref
            documents[file_ref] = load_json(lint, path) if path.is_file() else None
        return documents[file_ref]

    for array_name, index, row in _in_scope_rows(data):
        where = f"{array_name}[{index}]"
        family = row.get("object_family")
        label = family if isinstance(family, str) and family else where
        references: list[str] = []
        schema_ref = row.get("schema_ref")
        if isinstance(schema_ref, str) and schema_ref:
            references.append(schema_ref)
        transcript_refs = row.get("transcript_schema_refs")
        if isinstance(transcript_refs, list):
            references.extend(item for item in transcript_refs if isinstance(item, str) and item)
        if not references:
            lint.fail(
                PROOF_CONTEXT_REGISTRY,
                f"{where} object_family {label!r} signs a wire object but names no schema; "
                "declare schema_ref (or transcript_schema_refs) pointing at a schema registered "
                "in registry/schema-registry.json",
            )
            continue
        for reference in references:
            file_ref, separator, fragment_body = reference.partition("#")
            fragment = f"#{fragment_body}" if separator else ""
            if file_ref not in files:
                lint.fail(
                    PROOF_CONTEXT_REGISTRY,
                    f"{where} object_family {label!r} points at {file_ref}, which is not an "
                    "active row of registry/schema-registry.json",
                )
                continue
            node = document(file_ref)
            if node is None:
                lint.fail(
                    PROOF_CONTEXT_REGISTRY,
                    f"{where} object_family {label!r} points at {file_ref}, which does not exist",
                )
                continue
            try:
                resolved = resolve_json_pointer(node, fragment)
            except (KeyError, IndexError, ValueError):
                resolved = None
            if not isinstance(resolved, dict):
                lint.fail(
                    PROOF_CONTEXT_REGISTRY,
                    f"{where} object_family {label!r} reference {reference} does not resolve to a "
                    "schema object",
                )
                continue
            if _covering_schema_id(effective, file_ref, fragment) is None:
                lint.fail(
                    PROOF_CONTEXT_REGISTRY,
                    f"{where} object_family {label!r} reference {reference} is not covered by any "
                    "registered schema id",
                )


# `set` / `merge` / `transition` cover a register-shaped family. `agent_key` is
# not register-shaped: zh/identity/key-management.md section 3.6.1 fixes its
# registered reducer projection as a tagged set whose element tag is the
# canonical `<event_id>:<write_index>` Event dot of event-and-patch.md section
# 2.4.2, and typed-current-result.schema.json backs that with a closed
# `agent_key_authorization_entry` of exactly `{tag_id, value}`. A register kind
# cannot express it, and spelling it as `set` would silently collapse a
# tagged-set family into whole-value overwrite -- the shell this file exists to
# refuse. The three keyed-set kinds below carry over the shapes of the retired
# pre-v1 set vocabulary that still sits dormant in foundation.py, under the v1
# names that zh/models/pins.md and zh/models/strand-and-message.md already use,
# so nothing is invented here and the retired spelling is not resurrected.
_RESULT_PROJECTION_KINDS = frozenset(
    {"set", "merge", "transition", "keyed_set_add", "keyed_set_remove_observed", "keyed_set_remove_dots"}
)
_RESULT_KEYED_SET_KINDS = frozenset({"keyed_set_add", "keyed_set_remove_observed", "keyed_set_remove_dots"})

# The exact Agent supersedes remove of foundation.py lines 1186-1193. `for_each`
# and `keyed_set_remove_dots` exist only for this one registered write; anything
# else would be an open-ended per-item removal loop over arbitrary families.
_AGENT_SUPERSEDES_FOR_EACH = {"field": "payload.supersedes", "max_items": 256}
_AGENT_SUPERSEDES_SELECTOR = {
    "kind": "composite",
    "components": ["payload.agent_id", "item.key_id"],
}
_AGENT_SUPERSEDES_PROJECTION = {
    "kind": "keyed_set_remove_dots",
    "dots": {"agent_authorization_dot": {"field": "item.authorized_event_ref"}},
}


def _check_result_keyed_set_projection(lint: Lint, where: str, write: dict, projection: dict) -> None:
    """Validate one keyed-set `result_projection` and its `for_each` closure.

    The add tag MUST be the write's own canonical dot. `key-management.md`
    section 3.6.1 says so in as many words ("绝不是裸 `event_id`"), and the reason
    is mechanical: one Event may carry several writes on one subject, so a bare
    `event_id` is not unique among them and two entries would collide on one tag.
    """
    kind = projection["kind"]
    if kind == "keyed_set_add":
        unknown = set(projection) - {"kind", "tag", "value"}
        if unknown:
            lint.fail(EVENT_KIND_REGISTRY, f"{where}.result_projection has unknown member(s) {sorted(unknown)}")
        if projection.get("tag") != {"dot": True}:
            lint.fail(
                EVENT_KIND_REGISTRY,
                f'{where}.result_projection.tag must be exactly {{"dot": true}}; the stable element '
                "tag is the canonical <event_id>:<write_index> dot, never a bare event_id",
            )
        value = projection.get("value")
        if not isinstance(value, dict) or len([k for k in ("field", "envelope_field") if k in value]) != 1:
            lint.fail(
                EVENT_KIND_REGISTRY,
                f"{where}.result_projection.value must declare exactly one of field/envelope_field",
            )
        elif "field" in value:
            from .foundation import lint_field_path

            lint_field_path(lint, EVENT_KIND_REGISTRY, f"{where}.result_projection.value.field", value["field"])
    elif kind == "keyed_set_remove_observed":
        unknown = set(projection) - {"kind", "match"}
        if unknown:
            lint.fail(EVENT_KIND_REGISTRY, f"{where}.result_projection has unknown member(s) {sorted(unknown)}")
        match = projection.get("match")
        if match is None:
            return
        if not isinstance(match, dict) or set(match) - {"element_field", "source"}:
            lint.fail(EVENT_KIND_REGISTRY, f"{where}.result_projection.match must be {{element_field, source}}")
            return
        from .foundation import lint_field_path

        lint_field_path(
            lint, EVENT_KIND_REGISTRY, f"{where}.result_projection.match.element_field", match.get("element_field")
        )
        if "source" not in match:
            lint.fail(EVENT_KIND_REGISTRY, f"{where}.result_projection.match.source is required")
    elif kind == "keyed_set_remove_dots":
        if "for_each" not in write:
            lint.fail(
                EVENT_KIND_REGISTRY,
                f"{where}.result_projection keyed_set_remove_dots is legal only inside the registered "
                "for_each supersedes remove; a payload-enumerated dot array with no per-item bound is "
                "an open removal loop",
            )


RESULT_FAMILY_RE = re.compile(r"^[a-z][a-z0-9_]*$")
CURRENT_RESULT_REGISTRY = ARTIFACTS / "registry" / "current-result-registry.json"


def _registered_result_families(lint: Lint) -> set[str] | None:
    """The closed typed current result families, with each row's schema resolved."""
    data = load_json(lint, CURRENT_RESULT_REGISTRY)
    kinds = data.get("result_kinds") if isinstance(data, dict) else None
    if not isinstance(kinds, list) or not kinds:
        lint.fail(CURRENT_RESULT_REGISTRY, "result_kinds[] must be a non-empty array")
        return None
    families: set[str] = set()
    documents: dict[str, Any] = {}
    for index, row in enumerate(kinds):
        where = f"result_kinds[{index}]"
        if not isinstance(row, dict):
            lint.fail(CURRENT_RESULT_REGISTRY, f"{where} must be an object")
            continue
        kind = row.get("result_kind")
        if not isinstance(kind, str) or not RESULT_FAMILY_RE.fullmatch(kind):
            lint.fail(
                CURRENT_RESULT_REGISTRY,
                f"{where}.result_kind must be a snake_case typed current result family name",
            )
        elif kind in families:
            lint.fail(CURRENT_RESULT_REGISTRY, f"{where}.result_kind duplicates {kind!r}")
        else:
            families.add(kind)
        schema_ref = row.get("schema_ref")
        if not isinstance(schema_ref, str) or not schema_ref.startswith("schemas/"):
            lint.fail(
                CURRENT_RESULT_REGISTRY,
                f"{where}.schema_ref must point into artifacts/schemas",
            )
            continue
        file_ref, separator, fragment_body = schema_ref.partition("#")
        if file_ref not in documents:
            path = ARTIFACTS / file_ref
            documents[file_ref] = load_json(lint, path) if path.is_file() else None
        document = documents[file_ref]
        if document is None:
            lint.fail(
                CURRENT_RESULT_REGISTRY,
                f"{where}.schema_ref does not resolve: {schema_ref}",
            )
            continue
        try:
            node = resolve_json_pointer(document, f"#{fragment_body}" if separator else "")
        except (KeyError, IndexError, ValueError):
            node = None
        if not isinstance(node, dict):
            lint.fail(
                CURRENT_RESULT_REGISTRY,
                f"{where}.schema_ref does not resolve to a schema object: {schema_ref}",
            )
    return families


def _check_result_selector(lint: Lint, ref: str, selector: Any) -> None:
    """A singleton is JSON null; anything else is a closed subject descriptor."""
    from .foundation import is_registered_cell_subject_kind

    if selector is None:
        return
    if not isinstance(selector, dict):
        lint.fail(EVENT_KIND_REGISTRY, f"{ref} must be JSON null or an object")
        return
    kind = selector.get("kind")
    if not isinstance(kind, str) or not is_registered_cell_subject_kind(kind):
        lint.fail(
            EVENT_KIND_REGISTRY,
            f"{ref}.kind is not in the encoding.md section 4.1 closed subject table: {kind!r}",
        )
        return
    if kind == "composite":
        components = selector.get("components")
        if not isinstance(components, list) or not components:
            lint.fail(EVENT_KIND_REGISTRY, f"{ref}.components must be a non-empty array")
        elif len(components) != len({json.dumps(part, sort_keys=True) for part in components}):
            lint.fail(EVENT_KIND_REGISTRY, f"{ref}.components must not repeat a component")


def check_result_write_contracts(lint: Lint) -> None:
    """Validate the registered shared-state ``result_writes[]`` of each Event kind.

    ``zh/models/realm-and-space.md`` section 2.5.1 makes ``contract-registry.json``
    the machine source for which typed current results an Event kind writes. A
    registry array nobody validates is how the previous ``cell_writes[]`` promise
    stayed a promise, so the grammar is closed here from the start.

    Every declared ``result_family`` MUST also be a registered ``result_kinds[]``
    row of ``current-result-registry.json`` whose ``schema_ref`` resolves: a write
    into an unregistered family is the same failure mode one level down -- prose
    and reducers would share a family name that no closed selector/value schema
    defines.
    """
    registered_families = _registered_result_families(lint)
    if registered_families is None:
        return
    registry = load_json(lint, EVENT_KIND_REGISTRY)
    rows = registry.get("event_kinds") if isinstance(registry, dict) else None
    if not isinstance(rows, list):
        lint.fail(EVENT_KIND_REGISTRY, "event_kinds[] must be an array")
        return
    for row in rows:
        if not isinstance(row, dict):
            continue
        writes = row.get("result_writes")
        if writes is None:
            continue
        kind = row.get("event_kind")
        if not isinstance(writes, list) or not writes:
            lint.fail(EVENT_KIND_REGISTRY, f"{kind}.result_writes must be a non-empty array")
            continue
        if row.get("reducer_input") is not True:
            lint.fail(
                EVENT_KIND_REGISTRY,
                f"{kind} declares result_writes but is not a reducer_input Event kind",
            )
        for index, write in enumerate(writes):
            where = f"{kind}.result_writes[{index}]"
            if not isinstance(write, dict):
                lint.fail(EVENT_KIND_REGISTRY, f"{where} must be an object")
                continue
            unknown = set(write) - {
                "result_family",
                "result_selector",
                "for_each",
                "condition",
                "result_projection",
                "derived_members",
                "value_schema_ref",
                "notes",
            }
            if unknown:
                lint.fail(EVENT_KIND_REGISTRY, f"{where} has unknown member(s) {sorted(unknown)}")
            if "for_each" in write:
                if (
                    kind != "ak.agent.key.authorize"
                    or index != 0
                    or write["for_each"] != _AGENT_SUPERSEDES_FOR_EACH
                    or write.get("result_selector") != _AGENT_SUPERSEDES_SELECTOR
                    or write.get("result_projection") != _AGENT_SUPERSEDES_PROJECTION
                ):
                    lint.fail(
                        EVENT_KIND_REGISTRY,
                        f"{where}.for_each is restricted to the exact Agent supersedes remove of "
                        "zh/identity/key-management.md section 3.6.1: write 0 of ak.agent.key.authorize, "
                        "removing only the observed authorization dot from its old key subject",
                    )
            elif kind == "ak.agent.key.authorize" and index == 0:
                lint.fail(
                    EVENT_KIND_REGISTRY,
                    f"{where} must enumerate the bounded exact supersedes set before the add",
                )
            family = write.get("result_family")
            if not isinstance(family, str) or not RESULT_FAMILY_RE.fullmatch(family):
                lint.fail(
                    EVENT_KIND_REGISTRY,
                    f"{where}.result_family must be a snake_case typed current result family name",
                )
            elif family not in registered_families:
                lint.fail(
                    EVENT_KIND_REGISTRY,
                    f"{where}.result_family {family!r} is not a registered result_kinds[] row of "
                    "registry/current-result-registry.json",
                )
            if "result_selector" not in write:
                lint.fail(EVENT_KIND_REGISTRY, f"{where}.result_selector is required (JSON null for a singleton)")
            else:
                _check_result_selector(lint, f"{where}.result_selector", write["result_selector"])
            derived_members = write.get("derived_members")
            if derived_members is not None:
                from .foundation import lint_derived_members

                lint_derived_members(
                    lint, EVENT_KIND_REGISTRY, f"{where}.derived_members", derived_members
                )
            projection = write.get("result_projection")
            if not isinstance(projection, dict) or projection.get("kind") not in _RESULT_PROJECTION_KINDS:
                lint.fail(
                    EVENT_KIND_REGISTRY,
                    f"{where}.result_projection.kind must be one of {sorted(_RESULT_PROJECTION_KINDS)}",
                )
                continue
            if projection["kind"] == "transition":
                for member in ("from", "to"):
                    if not isinstance(projection.get(member), dict) or "const" not in projection[member]:
                        lint.fail(
                            EVENT_KIND_REGISTRY,
                            f"{where}.result_projection.{member} must declare a const state",
                        )
            elif projection["kind"] in _RESULT_KEYED_SET_KINDS:
                _check_result_keyed_set_projection(lint, where, write, projection)
            elif "value" not in projection and "value_projection" not in projection:
                lint.fail(
                    EVENT_KIND_REGISTRY,
                    f"{where}.result_projection must declare value or value_projection",
                )
            condition = write.get("condition")
            if condition is not None:
                from .foundation import lint_cell_write_condition

                lint_cell_write_condition(lint, EVENT_KIND_REGISTRY, f"{where}.condition", condition)
            value_projection = projection.get("value_projection")
            if value_projection is not None:
                from .foundation import lint_value_projection

                lint_value_projection(
                    lint,
                    EVENT_KIND_REGISTRY,
                    f"{where}.result_projection.value_projection",
                    value_projection,
                )
            value_schema_ref = write.get("value_schema_ref")
            if value_schema_ref is not None:
                if not isinstance(value_schema_ref, str) or not value_schema_ref.startswith("schemas/"):
                    lint.fail(EVENT_KIND_REGISTRY, f"{where}.value_schema_ref must point into artifacts/schemas")
                    continue
                file_ref, separator, fragment_body = value_schema_ref.partition("#")
                path = ARTIFACTS / file_ref
                document = load_json(lint, path) if path.is_file() else None
                if document is None:
                    lint.fail(EVENT_KIND_REGISTRY, f"{where}.value_schema_ref does not resolve: {value_schema_ref}")
                    continue
                try:
                    node = resolve_json_pointer(document, f"#{fragment_body}" if separator else "")
                except (KeyError, IndexError, ValueError):
                    node = None
                if not isinstance(node, dict):
                    lint.fail(
                        EVENT_KIND_REGISTRY,
                        f"{where}.value_schema_ref does not resolve to a schema object: {value_schema_ref}",
                    )

    _check_prose_result_write_citations(lint, rows)


def check_every_result_family_has_a_writer(lint: Lint) -> None:
    """Every registered typed current result family MUST have at least one writer.

    ``check_result_write_contracts`` closes the write -> family direction: a
    ``result_writes[]`` row may only name a registered family. This closes the
    other direction, which is where the ``cell_writes[]`` promise actually
    decayed. A family can sit in ``current-result-registry.json`` with a closed
    selector/value schema and a resolvable ``$defs`` entry and still have no
    Event kind that produces it. Prose then reads as if that state exists,
    reducers have nothing to replay, and no gate says a word -- a registered
    shell.

    Partial ``result_writes[]`` coverage is a known and recorded gap (see the
    ``event_kind_registry`` rule), so this check deliberately does NOT require
    every ``reducer_input`` kind to declare a contract. It requires only the one
    invariant that holds regardless of how far coverage has been extended: a
    family nobody writes MUST NOT stay registered. Either register its writer or
    withdraw the family.
    """
    registered = _registered_result_families(lint)
    if registered is None:
        return
    registry = load_json(lint, EVENT_KIND_REGISTRY)
    rows = registry.get("event_kinds") if isinstance(registry, dict) else None
    if not isinstance(rows, list):
        # check_result_write_contracts reports the shape failure; one is enough.
        return
    written: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        writes = row.get("result_writes")
        if not isinstance(writes, list):
            continue
        for write in writes:
            if isinstance(write, dict) and isinstance(write.get("result_family"), str):
                written.add(write["result_family"])
    for family in sorted(registered - written):
        lint.fail(
            CURRENT_RESULT_REGISTRY,
            f"result family {family!r} is registered but no Event kind declares a "
            "result_writes[] row that produces it; register its writer or withdraw "
            "the family",
        )


_PROSE_RESULT_WRITE_CITATION_RE = re.compile(r"(ak\.[a-z0-9_]+(?:\.[a-z0-9_]+)*)\.result_writes")


def _check_prose_result_write_citations(lint: Lint, rows: list[Any]) -> None:
    """Normative prose may cite `<kind>.result_writes[]` only for a kind that declares it.

    Coverage is partial on purpose (see the event_kind_registry rule), so the
    dangerous direction is prose promising a machine contract that the registry
    does not carry. That is exactly how `ak.realm.create.result_writes[]` and
    `ak.capability.grant.result_writes[].derived_members[]` sat dangling.
    """
    declared = {
        row.get("event_kind")
        for row in rows
        if isinstance(row, dict) and "result_writes" in row
    }
    prose_root = ARTIFACTS.parent / "zh"
    if not prose_root.is_dir():
        return
    for path in sorted(prose_root.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        for match in _PROSE_RESULT_WRITE_CITATION_RE.finditer(text):
            kind = match.group(1)
            if kind not in declared:
                lint.fail(
                    path,
                    f"cites {kind}.result_writes[] but that Event kind declares no result_writes "
                    "in contract-registry.json; register the contract or stop citing it",
                )
