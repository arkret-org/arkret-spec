#!/usr/bin/env python3
"""Generate schema-consumer-coverage.json.

A schema that compiles is not a schema that is used. This report answers, for
every logical schema ID in the schema registry, which consumers actually bind
it:

  inbound          an operation declares it as request_schema_ref, or it is the
                   Event envelope / payload contract a Principal Server admits.
  outbound         an operation declares it as response_schema_ref.
  startup_compile  it is a registry row, so ensure_all_schemas_compile() and
                   any equivalent startup gate compiles it.
  vectors          a conformance profile or vector group requires it, or a
                   fixture references the schema ID.
  schema_reference another schema $refs it, so it is a structural component
                   rather than a standalone wire contract.

Each consumer is recorded as ``exact`` when the reference targets the logical
schema itself and ``fragment`` when the reference targets a $defs fragment of
the same document. That distinction is deliberate: a catalog-style operations
document is legitimately consumed only through its fragments, while a schema
with no consumer at any level is a real gap and lands in ``uncovered``.

The report is derived; the registries and schema documents stay canonical.

Usage:
  python tools/gen_schema_consumer_coverage.py [generate|check]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "spec" / "v1" / "artifacts"
SCHEMA_DIR = ARTIFACTS / "schemas"
FIXTURE_DIR = ARTIFACTS / "fixtures"
SCHEMA_REGISTRY = ARTIFACTS / "registry" / "schema-registry.json"
OPERATION_REGISTRY = ARTIFACTS / "registry" / "operation-registry.json"
EVENT_KIND_REGISTRY = ARTIFACTS / "registry" / "event-kind-registry.json"
PROFILES = ARTIFACTS / "profiles" / "conformance-profiles.json"
PROSE_ROOT = ROOT / "spec" / "v1" / "zh"
REPORT = ARTIFACTS / "reports" / "schema-consumer-coverage.json"

REFERENCE_RE = re.compile(
    r"^(?:https://arkret\.org/v1/schemas/|schemas/|\./|\.\./schemas/)?"
    r"([A-Za-z0-9._-]+\.json)(#.*)?$"
)
REF_TOKEN_RE = re.compile(r'"\$ref"\s*:\s*"([^"]+)"')
DECLARED_WIRE_BINDING_KINDS = {
    "account_data_plaintext",
    "account_data_storage",
    "dynamic_schema_ref",
    "signal_plaintext_dispatch",
    "standalone_schema_alias",
}


def dump_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize(reference: str, origin: str | None = None) -> str | None:
    """Normalize any schema reference to `schemas/<file>.json[#fragment]`."""

    if reference.startswith("#"):
        return f"schemas/{origin}{reference}" if origin else None
    match = REFERENCE_RE.match(reference)
    if not match:
        return None
    return f"schemas/{match.group(1)}{match.group(2) or ''}"


def binding_kind(target: str, references: set[str]) -> str | None:
    if target in references:
        return "exact"
    if "#" in target:
        prefix = f"{target}/"
    else:
        prefix = f"{target}#"
    if any(reference.startswith(prefix) for reference in references):
        return "fragment"
    return None


def effective_schema_ref(row: dict[str, Any]) -> str:
    file_ref = row["file"]
    fragment = row.get("fragment")
    if isinstance(fragment, str):
        return f"{file_ref}{fragment}"
    return file_ref


def collect_schema_references() -> set[str]:
    references: set[str] = set()
    for path in sorted(SCHEMA_DIR.glob("*.json")):
        raw = path.read_text(encoding="utf-8")
        for match in REF_TOKEN_RE.finditer(raw):
            target = normalize(match.group(1), path.name)
            if target:
                references.add(target)
    return references


def collect_vector_mentions() -> set[str]:
    mentions: set[str] = set()
    profiles = load(PROFILES)
    for section in ("profile_requirements", "vector_group_requirements"):
        for requirement in (profiles.get(section) or {}).values():
            if isinstance(requirement, dict):
                for schema_id in requirement.get("required_schemas", []):
                    if isinstance(schema_id, str):
                        mentions.add(schema_id)
    fixture_text = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(FIXTURE_DIR.glob("*.json"))
    )
    return mentions, fixture_text


def build_report() -> dict[str, Any]:
    registry_rows = load(SCHEMA_REGISTRY)["schemas"]
    operations = load(OPERATION_REGISTRY)["operations"]
    event_kinds = load(EVENT_KIND_REGISTRY)
    payload_contract = event_kinds["payload_schema_contract"]

    request_refs = {
        normalize(operation["request_schema_ref"])
        for operation in operations
        if isinstance(operation.get("request_schema_ref"), str)
    } - {None}
    response_refs = {
        normalize(operation["response_schema_ref"])
        for operation in operations
        if isinstance(operation.get("response_schema_ref"), str)
    } - {None}
    schema_references = collect_schema_references()
    required_schema_ids, fixture_text = collect_vector_mentions()
    event_kind_text = EVENT_KIND_REGISTRY.read_text(encoding="utf-8")
    prose_text = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(PROSE_ROOT.rglob("*.md"))
    )

    admitted_event_documents = {
        payload_contract["event_envelope_schema"],
        payload_contract["payload_schema_file"],
    }

    rows: list[dict[str, Any]] = []
    for registry_row in registry_rows:
        schema_id = registry_row["schema_id"]
        file_ref = effective_schema_ref(registry_row)
        document = file_ref.split("#", 1)[0]

        consumers: dict[str, str] = {}
        inbound = binding_kind(file_ref, request_refs)
        if file_ref == document and document in admitted_event_documents:
            inbound = "exact"
        if inbound:
            consumers["inbound"] = inbound
        outbound = binding_kind(file_ref, response_refs)
        if outbound:
            consumers["outbound"] = outbound
        reference = binding_kind(file_ref, schema_references)
        if reference:
            consumers["schema_reference"] = reference
        if schema_id in event_kind_text:
            consumers["event_kind"] = "registered"
        if schema_id in required_schema_ids:
            consumers["vectors"] = "required_schema"
        elif schema_id in fixture_text:
            consumers["vectors"] = "fixture"
        if schema_id in prose_text:
            consumers["prose"] = "normative_text"

        declared_binding = registry_row.get("consumer_binding")
        if declared_binding is not None:
            if not isinstance(declared_binding, dict):
                raise SystemExit(f"{schema_id} consumer_binding must be an object")
            declared_kind = declared_binding.get("kind")
            if declared_kind == "prose_only":
                rationale = declared_binding.get("rationale")
                if not isinstance(rationale, str) or not rationale:
                    raise SystemExit(
                        f"{schema_id} prose_only consumer_binding must state a rationale"
                    )
                consumers["prose_only"] = "declared"
            elif declared_kind in DECLARED_WIRE_BINDING_KINDS:
                if not all(
                    isinstance(declared_binding.get(field), str)
                    and declared_binding[field]
                    for field in ("selector", "normative_ref")
                ):
                    raise SystemExit(
                        f"{schema_id} {declared_kind} consumer_binding must declare "
                        "selector and normative_ref"
                    )
                consumers["declared_wire"] = declared_kind
            else:
                raise SystemExit(
                    f"{schema_id} has unknown consumer_binding kind {declared_kind!r}"
                )
        consumers["startup_compile"] = "exact"

        row = {
            "schema_id": schema_id,
            "file": registry_row["file"],
            "consumers": dict(sorted(consumers.items())),
            "wire_covered": any(
                key in consumers
                for key in (
                    "inbound",
                    "outbound",
                    "schema_reference",
                    "event_kind",
                    "declared_wire",
                )
            ),
        }
        if declared_binding is not None:
            row["consumer_binding"] = declared_binding
        if isinstance(registry_row.get("fragment"), str):
            row["fragment"] = registry_row["fragment"]
        rows.append(row)

    rows.sort(key=lambda row: row["schema_id"])
    uncovered = [row["schema_id"] for row in rows if not row["wire_covered"]]
    unresolved = [
        row["schema_id"]
        for row in rows
        if not row["wire_covered"] and "prose_only" not in row["consumers"]
    ]
    prose_only = [
        row["schema_id"] for row in rows if "prose_only" in row["consumers"]
    ]
    vectorless = [row["schema_id"] for row in rows if "vectors" not in row["consumers"]]

    consumer_counts: dict[str, int] = {}
    for row in rows:
        for consumer in row["consumers"]:
            consumer_counts[consumer] = consumer_counts.get(consumer, 0) + 1

    return {
        "schema": "arkret.schema-consumer-coverage.v1",
        "source_of_truth": False,
        "generated_by": "tools/gen_schema_consumer_coverage.py",
        "generated_from": [
            "spec/v1/artifacts/registry/schema-registry.json",
            "spec/v1/artifacts/registry/operation-registry.json",
            "spec/v1/artifacts/registry/event-kind-registry.json",
            "spec/v1/artifacts/profiles/conformance-profiles.json",
            "spec/v1/artifacts/schemas/*.json",
            "spec/v1/artifacts/fixtures/*.json",
        ],
        "description": (
            "Per-logical-schema consumer coverage. A schema that only compiles has no "
            "proven wire consumer; this report separates operation request/response "
            "binding, admitted Event contracts, structural $ref use and conformance "
            "vector coverage so an unused schema cannot hide behind a startup compile."
        ),
        "consumer_definitions": {
            "inbound": "bound as an operation request body, or an admitted Event envelope/payload contract.",
            "outbound": "bound as an operation response body.",
            "schema_reference": "referenced by another schema, so it is a structural component.",
            "event_kind": "bound by the Event kind registry, so a durable Event selects it by kind.",
            "declared_wire": "explicit machine-readable runtime, dynamic, nested-value or alias binding declared by the canonical schema registry.",
            "prose_only": "explicitly declared as having no whole-object v1 wire admission surface.",
            "vectors": "required by a conformance profile or vector group, or referenced by a fixture.",
            "prose": "named by the normative text, which is where a runtime-dispatched contract is defined.",
            "startup_compile": "a schema registry row, compiled by the startup catalog gate.",
        },
        "binding_kind_definitions": {
            "exact": "the reference targets this logical schema itself.",
            "fragment": "the reference targets a $defs fragment of the same document.",
            "registered": "the schema ID appears in the Event kind registry.",
            "required_schema": "listed in a conformance profile or vector group required_schemas.",
            "fixture": "the schema ID appears in a conformance fixture.",
            "normative_text": "the schema ID appears in the normative prose.",
            "declared": "the canonical schema registry carries an explicit disposition.",
        },
        "summary": {
            "total_schemas": len(rows),
            "by_consumer": dict(sorted(consumer_counts.items())),
            "without_wire_consumer": len(uncovered),
            "explicit_prose_only": len(prose_only),
            "unresolved_consumer_coverage": len(unresolved),
            "without_vector_coverage": len(vectorless),
        },
        "without_wire_consumer": uncovered,
        "explicit_prose_only": prose_only,
        "unresolved_consumer_coverage": unresolved,
        "without_vector_coverage": vectorless,
        "schemas": rows,
    }


def write_report() -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(dump_json(build_report()), encoding="utf-8", newline="\n")
    print(f"updated {REPORT.relative_to(ROOT).as_posix()}")


def check_report() -> int:
    expected = dump_json(build_report())
    if not REPORT.exists():
        print(
            f"missing {REPORT.relative_to(ROOT).as_posix()} "
            "(run python tools/gen_schema_consumer_coverage.py)",
            file=sys.stderr,
        )
        return 1
    if REPORT.read_text(encoding="utf-8") != expected:
        print(
            f"schema consumer coverage drift: {REPORT.relative_to(ROOT).as_posix()} "
            "(run python tools/gen_schema_consumer_coverage.py)",
            file=sys.stderr,
        )
        return 1
    print("schema consumer coverage: clean")
    return 0


def main(argv: list[str]) -> int:
    mode = argv[1] if len(argv) > 1 else "generate"
    if mode == "check":
        return check_report()
    write_report()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
