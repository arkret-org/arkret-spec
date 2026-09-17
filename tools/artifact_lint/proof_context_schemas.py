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
import posixpath
import re
from typing import Any

from .core import ARTIFACTS, Lint, TOOLS_ROOT, load_json, resolve_json_pointer

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


def _check_projection_value_source(lint: Lint, ref: str, value: Any) -> None:
    """A projection's whole-value source MUST name exactly one registered origin.

    ``result_projection.value`` had no validator at all outside the keyed-set
    branch: ``check_result_write_contracts`` checked that ``value`` or
    ``value_projection`` was present and then read neither. The grammar that did
    validate it, ``foundation.lint_effect_source``, was written for
    ``effect_projection`` and lost its only caller when the ``cell_writes[]``
    loop went dead, so 31 registered ``set`` values were passing unread.

    The closure is the one already in force for ``keyed_set_add`` in this file,
    and it is exactly what the live rows use: one member, ``field`` or
    ``envelope_field``. The retired grammar also admitted ``const``,
    ``projected_value``, ``object_without_fields`` and ``dot``; no registered row
    uses any of them for a whole value, and re-admitting a spelling nothing needs
    is how removed vocabulary comes back. A row that genuinely needs one makes
    that an explicit decision here rather than passing unnoticed.
    """
    if not isinstance(value, dict):
        lint.fail(EVENT_KIND_REGISTRY, f"{ref} must be an object")
        return
    unknown = set(value) - {"field", "envelope_field"}
    if unknown:
        lint.fail(EVENT_KIND_REGISTRY, f"{ref} has unknown member(s) {sorted(unknown)}")
    named = [member for member in ("field", "envelope_field") if member in value]
    if len(named) != 1:
        lint.fail(
            EVENT_KIND_REGISTRY,
            f"{ref} must declare exactly one of field/envelope_field",
        )
        return
    if "field" in value:
        from .foundation import lint_field_path

        lint_field_path(lint, EVENT_KIND_REGISTRY, f"{ref}.field", value["field"])
        return
    from .core import EFFECT_PROJECTION_ENVELOPE_FIELDS

    if value["envelope_field"] not in EFFECT_PROJECTION_ENVELOPE_FIELDS:
        lint.fail(
            EVENT_KIND_REGISTRY,
            f"{ref}.envelope_field must be one of "
            f"{sorted(EFFECT_PROJECTION_ENVELOPE_FIELDS)}",
        )


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
        _check_projection_value_source(
            lint, f"{where}.result_projection.value", projection.get("value")
        )
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
_COVERAGE_NOTE_RE = re.compile(
    r"(\d+) of the (\d+) reducer_input kinds declare it; the remaining (\d+)"
)
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


# `canonical_json` and `string_set_digest` describe how one component of a
# multi-component subject is reduced to bytes. Neither has a row in the closed
# embedding table, so neither has a defined wire id on its own, and neither is a
# member of CELL_SUBJECT_KINDS -- a top-level use is already rejected there, and
# is spelled as a single-component composite instead (ruling 2026-09-05-1200,
# conformance/encoding.md section 9.5.1).
_SUBJECT_COMPONENT_KINDS = frozenset({"canonical_json", "string_set_digest"})
_MULTI_COMPONENT_SUBJECT_KINDS = frozenset({"composite", "tuple"})


def _check_subject_component(
    lint: Lint, ref: str, component: Any, event_kind: Any = None
) -> None:
    """One component of a `composite` or `tuple` subject.

    A `string_set_digest` component carries a third member, `context`, and it is
    not decoration: the digest is domain-separated, so the same scope set under
    two contexts is two different keys. `zh/models/actor.md:141` fixes both sides
    of the `identity_accountability` selector as
    `string_set_digest(payload.accountability_scope, ak.accountability_scope_set.v1)`
    precisely so the general grant and the provision projection land on one
    result. The component grammar closed to `{kind, field}` when it was written
    here, which made that sentence unregisterable; `context` is validated by
    `foundation.lint_string_set_digest_component`, which the retired
    `cell_writes[]` loop was the only caller of.
    """
    from .foundation import lint_string_set_digest_component, lint_subject_field_path

    if isinstance(component, str):
        lint_subject_field_path(lint, EVENT_KIND_REGISTRY, ref, component)
        return
    if not isinstance(component, dict):
        lint.fail(
            EVENT_KIND_REGISTRY,
            f"{ref} must be an explicit field path or a {{kind, field}} descriptor",
        )
        return
    kind = component.get("kind")
    if kind == "string_set_digest":
        lint_string_set_digest_component(
            lint, EVENT_KIND_REGISTRY, ref, component, event_kind=event_kind
        )
        return
    unknown = set(component) - {"kind", "field"}
    if unknown:
        lint.fail(EVENT_KIND_REGISTRY, f"{ref} has unknown member(s) {sorted(unknown)}")
    if kind not in _SUBJECT_COMPONENT_KINDS:
        lint.fail(
            EVENT_KIND_REGISTRY,
            f"{ref}.kind must be one of {sorted(_SUBJECT_COMPONENT_KINDS)}, not {kind!r}; "
            "those are the only registered component descriptors, and a typed-ID component "
            "belongs to a typed_pair subject rather than to this one",
        )
    if "field" not in component:
        lint.fail(EVENT_KIND_REGISTRY, f"{ref}.field is required")
        return
    lint_subject_field_path(lint, EVENT_KIND_REGISTRY, f"{ref}.field", component["field"])


def _check_result_selector(
    lint: Lint, ref: str, selector: Any, id_source: Any = None, event_kind: Any = None
) -> None:
    """A singleton is JSON null; anything else is a closed subject descriptor.

    conformance/encoding.md section 9.5.1 is the whole rule: "subject 的 registry
    字段来源必须显式命名", and a bare field name or a payload-then-envelope
    fallback is undefined and MUST be rejected. Before this closure only the
    `kind` itself was checked against the closed table, plus a shallow
    non-empty/no-duplicate pass over `composite.components` -- so a subject could
    name no source at all, name one through an unregistered envelope field, or
    carry members nobody reads, and the registry would still pass.

    That was not hypothetical: `authz/capabilities.md` says the revoke selector
    derives from `payload.grant_id` and `extensions/mimi-interop.md` says the
    room-binding subject is `payload.mimi_room_uri` under a `uri` kind, and
    neither sentence could be spelled in the grammar, because a non-composite
    subject had nowhere to name its field.

    A fieldless `id:<object kind>` subject stays legal only where it already
    means something: an `id_source: "event_derived"` Event kind, where the
    object's id is this Event's own id retyped. `ak.capability.grant` and
    `ak.strand.create` are the two live uses and both say so in their notes. On
    any other row a missing `field` is exactly the undefined bare source that
    section 9.5.1 rejects.
    """
    from .foundation import is_registered_cell_subject_kind, lint_subject_field_path

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
    if kind in _MULTI_COMPONENT_SUBJECT_KINDS:
        unknown = set(selector) - {"kind", "components"}
        if unknown:
            lint.fail(EVENT_KIND_REGISTRY, f"{ref} has unknown member(s) {sorted(unknown)}")
        components = selector.get("components")
        if not isinstance(components, list) or not components:
            lint.fail(EVENT_KIND_REGISTRY, f"{ref}.components must be a non-empty array")
            return
        if len(components) != len({json.dumps(part, sort_keys=True) for part in components}):
            lint.fail(EVENT_KIND_REGISTRY, f"{ref}.components must not repeat a component")
        for index, component in enumerate(components):
            _check_subject_component(
                lint, f"{ref}.components[{index}]", component, event_kind
            )
        return
    if kind == "typed_pair":
        _check_typed_pair_components(lint, ref, selector)
        return
    if kind == "coalesce":
        unknown = set(selector) - {"kind", "fields"}
        if unknown:
            lint.fail(EVENT_KIND_REGISTRY, f"{ref} has unknown member(s) {sorted(unknown)}")
        fields = selector.get("fields")
        if not isinstance(fields, list) or not fields:
            lint.fail(EVENT_KIND_REGISTRY, f"{ref}.fields must be a non-empty array")
            return
        if len(fields) != len({json.dumps(part, sort_keys=True) for part in fields}):
            lint.fail(EVENT_KIND_REGISTRY, f"{ref}.fields must not repeat a field")
        for index, field in enumerate(fields):
            lint_subject_field_path(lint, EVENT_KIND_REGISTRY, f"{ref}.fields[{index}]", field)
        return
    unknown = set(selector) - {"kind", "field"}
    if unknown:
        lint.fail(EVENT_KIND_REGISTRY, f"{ref} has unknown member(s) {sorted(unknown)}")
    if "field" in selector:
        lint_subject_field_path(lint, EVENT_KIND_REGISTRY, f"{ref}.field", selector["field"])
        if id_source == "event_derived" and kind.startswith("id:"):
            lint.fail(
                EVENT_KIND_REGISTRY,
                f"{ref} names a source field on an id_source=event_derived Event kind; the "
                "fieldless form already means this Event's own id retyped, so naming a field "
                "here says the object id comes from the payload and contradicts the row",
            )
    elif id_source == "event_derived" and kind.startswith("id:"):
        return
    else:
        lint.fail(
            EVENT_KIND_REGISTRY,
            f"{ref}.field is required for a {kind!r} subject; encoding.md section 9.5.1 says a "
            "subject's registry field source MUST be named explicitly, and only an "
            "id_source=event_derived id:<object kind> subject may omit it (it is then this "
            "Event's own id retyped)",
        )


def _check_typed_pair_components(lint: Lint, ref: str, selector: Any) -> None:
    """A `typed_pair` subject is a reversible two-component typed-ID encoding.

    `zh/models/realm-and-space.md` section 3.6 is the only paragraph that pins a
    family to this kind, and it pins the reason too: the wire form
    `strand_position:<board_space_id>:<strand_id>` MUST stay invertible, so the
    SHA-256 subject of `tuple`/`composite` is explicitly not applicable and a
    reader MUST validate BOTH typed-ID components rather than slicing the tail.
    Neither property survives a free-form component list: two components in a
    fixed order, each naming its own registered id kind, is what makes the
    encoding reversible and the pair-wise validation possible.

    So the shape is closed here rather than left to `composite`'s weaker "any
    non-repeating list" rule. Without this branch `typed_pair` would sit in the
    closed subject table with no grammar behind it -- a subject kind spelled in
    prose and in the registry that nothing agrees on, which is the same shell
    one level down from the family shells the writer gate refuses.
    """
    from .foundation import CELL_SUBJECT_ID_KIND_RE, lint_field_path
    from .naming_contracts import ID_KIND_REGISTRY_PATH, registered_id_kinds

    unknown = set(selector) - {"kind", "components"}
    if unknown:
        lint.fail(EVENT_KIND_REGISTRY, f"{ref} has unknown member(s) {sorted(unknown)}")
    components = selector.get("components")
    if not isinstance(components, list) or len(components) != 2:
        lint.fail(
            EVENT_KIND_REGISTRY,
            f"{ref}.components must be exactly two ordered components; the reversible "
            "typed_pair encoding of zh/models/realm-and-space.md section 3.6 has no other arity",
        )
        return
    id_kinds = registered_id_kinds(load_json(lint, ID_KIND_REGISTRY_PATH))
    fields: list[str] = []
    for index, part in enumerate(components):
        where = f"{ref}.components[{index}]"
        if not isinstance(part, dict) or set(part) != {"kind", "field"}:
            lint.fail(EVENT_KIND_REGISTRY, f"{where} must be exactly {{kind, field}}")
            continue
        part_kind = part["kind"]
        if not isinstance(part_kind, str) or CELL_SUBJECT_ID_KIND_RE.fullmatch(part_kind) is None:
            lint.fail(
                EVENT_KIND_REGISTRY,
                f"{where}.kind must be an `id:<object kind>` typed-ID kind, not {part_kind!r}; "
                "a typed_pair component that is not typed cannot be validated on parse",
            )
        elif id_kinds and part_kind[len("id:") :] not in id_kinds:
            lint.fail(
                EVENT_KIND_REGISTRY,
                f"{where}.kind {part_kind!r} is not a registered id_kinds[] row of "
                "registry/id-kind-registry.json",
            )
        lint_field_path(lint, EVENT_KIND_REGISTRY, f"{where}.field", part["field"])
        if isinstance(part["field"], str):
            fields.append(part["field"])
    if len(fields) == 2 and fields[0] == fields[1]:
        lint.fail(
            EVENT_KIND_REGISTRY,
            f"{ref}.components must not read the same field twice; the two ordered components "
            "are what make the subject invertible",
        )


_VALUE_SCHEMA_REF_DEPTH = 6


def _value_schema_alternatives(
    lint: Lint, file_ref: str, node: Any, depth: int = 0
) -> list[tuple[set[str], set[str]]]:
    """Resolve one registered value schema to its alternative member shapes.

    A `value_projection` builds the stored value out of members named one at a
    time, so the question a reader has -- is this member part of the value this
    family stores, and does a whole-value `set` write all of it? -- is answered
    by the write's own `value_schema_ref`. Nothing read it, so a member name
    could be anything: `ak.member.state` pointed its ref at the enclosing
    `member_state_result` envelope, whose own members are selector/revision/value,
    and wrote `membership` into it.

    Each entry is one alternative the value may take, as (declared, required).
    Resolution follows the three shapes the registered value schemas use: a
    direct `properties` map, a `$ref` (local `#/$defs/...` or a sibling artifact
    file), and `oneOf`/`anyOf` branches, which are alternatives rather than a
    union because `required` only binds inside the branch that matched. An
    `allOf` member is a conjunction and folds into the enclosing alternative. A
    `{"type": "null"}` branch is dropped rather than reported: it is a real
    registered state -- `strand_position_value` spells pre-placement that way --
    but an object projection can never produce it, so it constrains nothing.
    """
    if depth > _VALUE_SCHEMA_REF_DEPTH or not isinstance(node, dict):
        return []
    ref = node.get("$ref")
    if isinstance(ref, str):
        target_file, separator, fragment = ref.partition("#")
        if target_file in ("", "."):
            target_ref = file_ref
        else:
            target_ref = posixpath.normpath(
                posixpath.join(posixpath.dirname(file_ref), target_file)
            )
        path = ARTIFACTS / target_ref
        document = load_json(lint, path) if path.is_file() else None
        if not isinstance(document, dict):
            return []
        try:
            target = resolve_json_pointer(document, f"#{fragment}") if separator else document
        except (KeyError, IndexError, ValueError):
            return []
        return _value_schema_alternatives(lint, target_ref, target, depth + 1)
    branches = node.get("oneOf") or node.get("anyOf")
    if isinstance(branches, list) and branches:
        alternatives: list[tuple[set[str], set[str]]] = []
        for branch in branches:
            if isinstance(branch, dict) and branch.get("type") == "null":
                continue
            alternatives.extend(_value_schema_alternatives(lint, file_ref, branch, depth + 1))
        return alternatives
    declared = set(node["properties"]) if isinstance(node.get("properties"), dict) else set()
    required = set(node["required"]) if isinstance(node.get("required"), list) else set()
    for member in node.get("allOf") or ():
        for member_declared, member_required in _value_schema_alternatives(
            lint, file_ref, member, depth + 1
        ):
            declared |= member_declared
            required |= member_required
    if not declared:
        return []
    return [(declared, required)]


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
                _check_result_selector(
                    lint,
                    f"{where}.result_selector",
                    write["result_selector"],
                    row.get("id_source"),
                    kind,
                )
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
                unknown = set(projection) - {"kind", "from", "to"}
                if unknown:
                    lint.fail(
                        EVENT_KIND_REGISTRY,
                        f"{where}.result_projection has unknown member(s) {sorted(unknown)}",
                    )
                # A const endpoint is the sharper declaration and stays the norm.
                # A field endpoint exists because one row can carry several edges
                # whose prestate only the payload knows: agent_deactivate_payload
                # closes previous_status to [active, paused], and
                # history_access_payload closes from to null plus both states. In
                # those two shapes a const would have to pick one edge and drop
                # the rest, or restate a closed set the payload schema already
                # holds. check_fsm_state_reachability resolves a field endpoint
                # against that schema, so the edge stays as narrow as the schema
                # is -- an unresolvable field widens to the whole state list
                # rather than inventing reachability.
                for member in ("from", "to"):
                    source = projection.get(member)
                    if not isinstance(source, dict) or len(
                        [key for key in ("const", "field") if key in source]
                    ) != 1:
                        lint.fail(
                            EVENT_KIND_REGISTRY,
                            f"{where}.result_projection.{member} must declare exactly one of "
                            "const/field",
                        )
                    elif "field" in source:
                        from .foundation import lint_field_path

                        lint_field_path(
                            lint,
                            EVENT_KIND_REGISTRY,
                            f"{where}.result_projection.{member}.field",
                            source["field"],
                        )
            elif projection["kind"] in _RESULT_KEYED_SET_KINDS:
                _check_result_keyed_set_projection(lint, where, write, projection)
            elif "value" not in projection and "value_projection" not in projection:
                lint.fail(
                    EVENT_KIND_REGISTRY,
                    f"{where}.result_projection must declare value or value_projection",
                )
            elif "value" in projection:
                _check_projection_value_source(
                    lint, f"{where}.result_projection.value", projection["value"]
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
            projected_members = (
                value_projection.get("members")
                if isinstance(value_projection, dict)
                else None
            )
            if projected_members and value_schema_ref is None:
                lint.fail(
                    EVENT_KIND_REGISTRY,
                    f"{where} names value_projection members but declares no value_schema_ref, "
                    "so nothing says which object those members belong to",
                )
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
                elif projected_members:
                    _check_projected_members(
                        lint, where, write, projection, value_schema_ref, file_ref, node
                    )

    _check_prose_result_write_citations(lint, rows)


def _check_projected_members(
    lint: Lint,
    where: str,
    write: dict,
    projection: dict,
    value_schema_ref: str,
    file_ref: str,
    node: Any,
) -> None:
    """Hold a value_projection to the value schema the same write names."""
    alternatives = _value_schema_alternatives(lint, file_ref, node)
    if not alternatives:
        lint.fail(
            EVENT_KIND_REGISTRY,
            f"{where}.value_schema_ref declares no members, so its value_projection cannot be "
            f"checked against it: {value_schema_ref}",
        )
        return
    declared: set[str] = set()
    for alternative_declared, _ in alternatives:
        declared |= alternative_declared
    projected: set[str] = set()
    for member in projection["value_projection"]["members"]:
        if not isinstance(member, dict):
            continue
        name = member.get("name")
        if not isinstance(name, str):
            continue
        projected.add(name)
        if name not in declared:
            lint.fail(
                EVENT_KIND_REGISTRY,
                f"{where}.result_projection.value_projection member {name!r} is not declared by "
                f"value_schema_ref {value_schema_ref}",
            )
    if projection["kind"] != "set" or write.get("derived_members"):
        # `merge` writes only the members it names, so an unnamed required member
        # is the already-projected value's, not this write's. A write that also
        # materialises derived members is undecidable here for a different
        # reason: `derived_members[].name` is the registered reducer derivation,
        # and which value member that derivation lands in is fixed by the
        # normative rule rather than by this row.
        return
    # A `set` replaces the whole value, so anything a matching alternative
    # requires and this projection does not write produces a value that violates
    # its own registered schema on the first replay.
    floor: set[str] | None = None
    for _, alternative_required in alternatives:
        floor = alternative_required if floor is None else floor & alternative_required
    for name in sorted((floor or set()) - projected):
        lint.fail(
            EVENT_KIND_REGISTRY,
            f"{where}.result_projection is a whole-value set but does not write {name!r}, which "
            f"value_schema_ref {value_schema_ref} requires",
        )


def check_result_write_coverage_note(lint: Lint) -> None:
    """The coverage note MUST count the rows that are actually there.

    ``registry_rules`` calls partial ``result_writes[]`` coverage a known gap and
    tells the next editor to shrink the note as coverage grows. Nothing read it,
    so it stayed at the numbers it was written with while four commits raised
    coverage -- a source-of-truth registry describing itself wrongly, which is
    the same defect class as a stale generated mirror except that no digest
    catches it. The note carried an enumeration of the declaring kinds too;
    ``event_kinds[]`` already is that list, so the copy is gone and only the two
    counts remain, recomputed here from the rows.
    """
    block = load_json(lint, EVENT_KIND_REGISTRY)
    rows = block.get("event_kinds") if isinstance(block, dict) else None
    if not isinstance(rows, list):
        lint.fail(
            EVENT_KIND_REGISTRY,
            "event_kinds[] is missing, so result_writes[] coverage cannot be counted",
        )
        return
    reducer_inputs = [row for row in rows if isinstance(row, dict) and row.get("reducer_input")]
    covered = [row for row in reducer_inputs if row.get("result_writes")]
    notes = [
        rule
        for rule in (block.get("registry_rules") or ())
        if isinstance(rule, str) and "COVERAGE IS PARTIAL" in rule
    ]
    if len(notes) != 1:
        lint.fail(
            EVENT_KIND_REGISTRY,
            "event_kind_registry.registry_rules must carry exactly one result_writes[] coverage "
            f"note, found {len(notes)}",
        )
        return
    match = _COVERAGE_NOTE_RE.search(notes[0])
    if match is None:
        lint.fail(
            EVENT_KIND_REGISTRY,
            "the result_writes[] coverage note must state coverage as "
            "'<n> of the <total> reducer_input kinds declare it; the remaining <rest>'",
        )
        return
    declared, total, remaining = (int(group) for group in match.groups())
    if (declared, total, remaining) != (
        len(covered),
        len(reducer_inputs),
        len(reducer_inputs) - len(covered),
    ):
        lint.fail(
            EVENT_KIND_REGISTRY,
            "the result_writes[] coverage note says "
            f"{declared} of {total} with {remaining} remaining, but event_kinds[] has "
            f"{len(covered)} of {len(reducer_inputs)} with "
            f"{len(reducer_inputs) - len(covered)} remaining",
        )
    if "ak." in notes[0]:
        lint.fail(
            EVENT_KIND_REGISTRY,
            "the result_writes[] coverage note must not enumerate the declaring kinds: "
            "event_kinds[] is that list and the copy went stale",
        )


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



CURRENT_RESULTS_PROSE = ARTIFACTS.parent / "zh" / "sync" / "current-results.md"
CURRENT_RESULTS_PROSE_HEADING = "## 2. 领域 selector 与 revision"
_PROSE_FAMILY_TOKEN_RE = re.compile(r"`([a-z][a-z0-9_]*)`")


def check_registered_families_are_listed_in_prose(lint: Lint) -> None:
    """Every registered family MUST appear in the normative selector list.

    ``sync/current-results.md`` section 2 opens with "v1 登记的 selector kind 为"
    and then enumerates the families. That sentence is a closure claim: it tells
    an implementer that an unlisted selector is one it MUST reject. The registry
    is what reducers and schemas are generated from, so when a batch adds
    families and leaves the list alone, the prose starts telling implementers to
    reject state the registry requires them to carry -- and nothing said a word,
    because no gate connected the two. That is what happened when fifteen Realm
    facet families landed against a list still naming twenty-three.

    Only this direction is mechanized. The reverse -- a listed name that is not
    registered -- cannot be read off the section reliably, because the same
    backtick spelling carries payload fields, subject kinds and Event kinds; a
    matcher loose enough to catch it would mostly catch those. The reverse
    direction is also the less dangerous one: an unregistered family name in
    prose has no schema and no writer, so ``check_typed_current_result_naming``
    and ``check_every_result_family_has_a_writer`` both bite the moment anyone
    tries to make it real.
    """
    registered = _registered_result_families(lint)
    if registered is None:
        return
    if not CURRENT_RESULTS_PROSE.is_file():
        lint.fail(CURRENT_RESULTS_PROSE, "normative selector list is missing")
        return
    text = CURRENT_RESULTS_PROSE.read_text(encoding="utf-8")
    parts = text.split(CURRENT_RESULTS_PROSE_HEADING)
    if len(parts) != 2:
        # Renaming the heading would silently disable this gate, so the anchor is
        # itself part of the contract.
        lint.fail(
            CURRENT_RESULTS_PROSE,
            f"expected exactly one {CURRENT_RESULTS_PROSE_HEADING!r} heading to anchor the "
            "registered selector list",
        )
        return
    section = parts[1].split("\n## ")[0]
    listed = set(_PROSE_FAMILY_TOKEN_RE.findall(section))
    missing = sorted(registered - listed)
    if missing:
        lint.fail(
            CURRENT_RESULTS_PROSE,
            f"section 2 enumerates the registered selector kinds but omits {missing}; "
            "the section tells implementers to reject an unlisted selector, so an omitted "
            "family is prose instructing them to reject state the registry requires",
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


# A whole prior value has to exist before anything can update part of it.
# `set` writes one outright; a `transition` out of the absent state creates the
# object the same way. Everything else builds on what a previous write left.
_PARTIAL_UPDATE_PROJECTIONS = frozenset({"merge", "apply_patch"})
PATCH_BASE_PRODUCER_BASELINE = TOOLS_ROOT / "patch-base-producer-baseline.json"


def _is_base_producer(projection: Any) -> bool:
    if not isinstance(projection, dict):
        return False
    kind = projection.get("kind")
    if kind == "set":
        return True
    if kind != "transition":
        return False
    source = projection.get("from")
    # `from: {"const": null}` is the genesis edge out of the absent state; a
    # transition between two real states changes one axis of a value someone
    # else created.
    return isinstance(source, dict) and "const" in source and source["const"] is None


def _selector_shape(write: dict) -> str:
    selector = write.get("result_selector")
    if selector is None:
        return "null"
    if isinstance(selector, dict):
        return str(selector.get("kind"))
    return str(selector)


def check_partial_update_base_producers(lint: Lint) -> None:
    """A partial update needs a base value, and only a registered write supplies it.

    `zh/models/views.md` section 3.2 argues it in full and the argument is not
    about views: an update that lands on a typed current result nobody has
    written has no pre-state, the current-value contract forbids closing the gap
    with a registered `initial_value`, and `null` or an empty object MUST NOT be
    treated as implicit initialization. So the base has to come from a
    registered create or genesis write, and the first partial update MUST NOT
    become the object's definition by default.

    The gate was written for `apply_patch` and has been dead since the
    authority-commit clean break renamed `cell_writes[].cell_family` /
    `effect_projection` to `result_writes[].result_family` /
    `result_projection`. `apply_patch` is not in the v1 `result_projection`
    closed set at all -- views.md section 3.2 still requires it and the three
    patch kinds are still uncovered, which is its own open question -- but
    `merge` is the live partial update and the same sentence covers it verbatim.
    Both are checked here so the rule binds today and keeps binding if the patch
    vocabulary comes back.

    Keyed-set projections are deliberately not partial updates: a keyed set
    begins empty, `keyed_set_add` is its genesis, and a remove over the observed
    set (`zh/models/pins.md` section 3) needs no whole prior value. Requiring a
    `set` producer for `agent_key` would be demanding a base its own contract
    says it does not have.
    """
    registry = load_json(lint, EVENT_KIND_REGISTRY)
    rows = registry.get("event_kinds") if isinstance(registry, dict) else None
    if not isinstance(rows, list):
        lint.fail(EVENT_KIND_REGISTRY, "event_kinds[] must be an array")
        return

    producers: dict[str, set[str]] = {}
    producer_shapes: dict[str, set[str]] = {}
    other_writers: dict[str, set[str]] = {}
    updaters: dict[str, set[str]] = {}
    updater_shapes: dict[str, set[str]] = {}
    writes_seen = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        kind = row.get("event_kind")
        for write in row.get("result_writes") or []:
            if not isinstance(write, dict):
                continue
            writes_seen += 1
            family = write.get("result_family")
            if not isinstance(family, str):
                continue
            projection = write.get("result_projection")
            projection_kind = (
                projection.get("kind") if isinstance(projection, dict) else None
            )
            if projection_kind in _PARTIAL_UPDATE_PROJECTIONS:
                updaters.setdefault(family, set()).add(kind)
                updater_shapes.setdefault(family, set()).add(_selector_shape(write))
            elif _is_base_producer(projection):
                producers.setdefault(family, set()).add(kind)
                producer_shapes.setdefault(family, set()).add(_selector_shape(write))
            else:
                other_writers.setdefault(family, set()).add(kind)

    if not writes_seen:
        lint.fail(
            EVENT_KIND_REGISTRY,
            "check_partial_update_base_producers inspected no result_writes[] entry at all; "
            "the registry either lost its writes or spells the array under another key, and "
            "either way this gate's silence means nothing",
        )
        return

    unproduced = {family for family in updaters if not producers.get(family)}

    # decisions/0029 section 3.2: a producer has to be usable as this update's
    # base, not merely present. A producer that addresses a different selector
    # shape names a different object, so it supplies no base for this one.
    for family in sorted(set(updaters) - unproduced):
        if not updater_shapes[family] <= producer_shapes[family]:
            lint.fail(
                EVENT_KIND_REGISTRY,
                f"{family} is partially updated on selector shape(s) "
                f"{sorted(updater_shapes[family])} but its base-value producer(s) address "
                f"{sorted(producer_shapes[family])}; a base value has to be written to the same "
                "object the update addresses",
            )
    for family in sorted(unproduced & set(other_writers)):
        lint.fail(
            EVENT_KIND_REGISTRY,
            f"{family} has only writer(s) {sorted(other_writers[family])} beside its partial "
            "update(s); none of them writes a whole value, so none can be the base the update "
            "resolves against",
        )

    baseline = load_json(lint, PATCH_BASE_PRODUCER_BASELINE) or {}
    known = {
        entry.get("result_family")
        for entry in baseline.get("families_without_base_producer") or []
        if isinstance(entry, dict)
    }
    for family in sorted(unproduced - known):
        lint.fail(
            EVENT_KIND_REGISTRY,
            f"{family} is the target of partial update write(s) {sorted(updaters[family])} but no "
            "registered write produces a base value for it; an update has no pre-state and the "
            "current-value contract forbids closing the gap with a registered initial_value",
        )
    for family in sorted(known - unproduced):
        detail = (
            "now has a registered base-value producer"
            if family in updaters
            else "is no longer the target of any partial update write"
        )
        lint.fail(
            PATCH_BASE_PRODUCER_BASELINE,
            f"{family} {detail}; remove it from families_without_base_producer "
            "(the baseline only shrinks)",
        )


def check_result_family_write_agreement(lint: Lint) -> None:
    """All writers of one family must agree on the value schema they write.

    This is what survives of `check_concurrency_class_closure`, which required
    every writer of a family to share one `execution` / `state_model` /
    `value_shape` contract. The clean break removed all three members, so that
    gate compared three absent values on an absent array and said nothing; its
    only live rule was the retired-`concurrency_class` row guard, which now sits
    with the other removed-field guards in `check_registries`.

    The proposition still holds, and in v1 it has one spelling: a family has one
    value, so two rows that both name a `value_schema_ref` for it MUST name the
    same one. A row may still omit it -- a `transition` writes no projection
    members and has nothing to declare -- so this checks agreement among the
    rows that declare one, not presence.
    """
    registry = load_json(lint, EVENT_KIND_REGISTRY)
    rows = registry.get("event_kinds") if isinstance(registry, dict) else None
    if not isinstance(rows, list):
        lint.fail(EVENT_KIND_REGISTRY, "event_kinds[] must be an array")
        return
    declared: dict[str, dict[str, set[str]]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        kind = row.get("event_kind")
        for write in row.get("result_writes") or []:
            if not isinstance(write, dict):
                continue
            family = write.get("result_family")
            ref = write.get("value_schema_ref")
            if isinstance(family, str) and isinstance(ref, str):
                declared.setdefault(family, {}).setdefault(ref, set()).add(kind)
    for family, refs in sorted(declared.items()):
        if len(refs) > 1:
            detail = "; ".join(
                f"{ref} ({', '.join(sorted(str(kind) for kind in kinds))})"
                for ref, kinds in sorted(refs.items())
            )
            lint.fail(
                EVENT_KIND_REGISTRY,
                f"{family} is written under {len(refs)} different value_schema_ref values, so its "
                f"writers do not agree on what the family's value is: {detail}",
            )


# zh/models/pins.md section 3: a keyed set's add and its remove are the two
# halves of one atomic re-key, so they are the one pair that may legally share a
# target inside a single Event.
_RESULT_SET_ADD_PROJECTIONS = frozenset({"keyed_set_add"})
_RESULT_SET_REMOVE_PROJECTIONS = frozenset(
    {"keyed_set_remove_observed", "keyed_set_remove_dots"}
)


def _result_target_key(write: dict) -> str:
    return json.dumps(
        [write.get("result_family"), write.get("result_selector")],
        sort_keys=True,
        ensure_ascii=False,
    )


def check_result_write_target_uniqueness(lint: Lint) -> None:
    """Two writes of one Event MUST NOT address the same typed current result.

    ``zh/models/event-and-patch.md`` section 2.4.2 lets one Event carry several
    ops of the same family only where the kind's closed contract registers them
    explicitly. Anything else is a duplicate target: two ops on one result are
    indistinguishable to a receiver, which is the same ambiguity the registry
    exists to remove.

    Two repeats are legal and both are provable from the row itself:

    * a keyed set's atomic remove-then-add. ``zh/identity/key-management.md``
      section 3.6.1 requires exactly that shape for Agent key re-authorization,
      and ``ak.agent.key.authorize`` is the live use;
    * a provably disjoint condition pair -- complementary presence tests, or
      unequal exact constants on one field. Anything weaker would be a guess,
      and a wrong guess means two writes racing on one result.

    The rule and its two exceptions were written for ``cell_writes[]`` and went
    down with it in the clean break; ``check_result_write_contracts`` closed the
    per-write grammar but says nothing about two rows agreeing on a target. The
    same-row coalesce agreement below has the same history.
    """
    registry = load_json(lint, EVENT_KIND_REGISTRY)
    rows = registry.get("event_kinds") if isinstance(registry, dict) else None
    if not isinstance(rows, list):
        lint.fail(EVENT_KIND_REGISTRY, "event_kinds[] must be an array")
        return

    from .foundation import complementary_conditions

    writes_seen = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        kind = row.get("event_kind")
        seen: dict[str, tuple[Any, Any]] = {}
        for index, write in enumerate(row.get("result_writes") or []):
            if not isinstance(write, dict):
                continue
            writes_seen += 1
            where = f"{kind}.result_writes[{index}]"
            projection = write.get("result_projection")
            projection_kind = (
                projection.get("kind") if isinstance(projection, dict) else None
            )
            condition = write.get("condition")

            # event-and-patch.md 2.4.2: when an `any_field_present` condition
            # selects the same alternative paths a `coalesce` selector derives
            # from, the two lists MUST agree item-for-item and in order. A
            # mismatch means the result can be required on a payload shape whose
            # key cannot be derived, or keyed on a shape where it must not be
            # written. The other legitimate use of `any_field_present` -- one
            # result carrying several distinct fields, addressed by an
            # unconditional selector -- is not constrained here.
            selector = write.get("result_selector")
            if (
                isinstance(condition, dict)
                and condition.get("kind") == "any_field_present"
                and isinstance(condition.get("fields"), list)
                and isinstance(selector, dict)
                and selector.get("kind") == "coalesce"
                and selector.get("fields") != condition["fields"]
            ):
                lint.fail(
                    EVENT_KIND_REGISTRY,
                    f"{where}.condition.fields must equal the result_selector coalesce fields "
                    "item-for-item and in order, or the result can be required on a payload "
                    "shape whose key cannot be derived",
                )

            key = _result_target_key(write)
            previous = seen.get(key)
            if previous is not None:
                previous_kind, previous_condition = previous
                pair = {previous_kind, projection_kind}
                paired = bool(pair & _RESULT_SET_ADD_PROJECTIONS) and bool(
                    pair & _RESULT_SET_REMOVE_PROJECTIONS
                )
                if not paired and not complementary_conditions(
                    previous_condition, condition
                ):
                    lint.fail(
                        EVENT_KIND_REGISTRY,
                        f"{where} addresses the same (result_family, result_selector) as an "
                        "earlier write of this Event without being a keyed-set "
                        "remove-then-add pair or carrying a provably disjoint condition; two "
                        "ops on one result are indistinguishable to a receiver",
                    )
            seen[key] = (projection_kind, condition)

    if not writes_seen:
        lint.fail(
            EVENT_KIND_REGISTRY,
            "check_result_write_target_uniqueness inspected no result_writes[] entry at all; "
            "the registry either lost its writes or spells the array under another key, and "
            "either way this gate's silence means nothing",
        )
