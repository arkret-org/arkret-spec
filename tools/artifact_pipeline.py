#!/usr/bin/env python3
"""Unified artifact maintenance pipeline for Arkret spec.

Layout (post-restructure):

  spec/v1/zh/                          normative Chinese prose
  spec/v1/en/                          English placeholder (non-normative until published)
  spec/v1/artifacts/registry/          canonical + generated registry views
  spec/v1/artifacts/profiles/          conformance profiles
  spec/v1/artifacts/schemas/           JSON Schemas
  spec/v1/artifacts/openapi/           OpenAPI document(s)
  spec/v1/artifacts/bindings/          non-HTTP bindings
  spec/v1/artifacts/fixtures/          conformance fixtures

This pipeline owns two responsibilities only:

  generate   regenerate derived registry views from contract-catalog.json
  check      verify no drift, fixture digests, then run lint_artifacts.py

The legacy "sync canonical files into zh/ mirrors" and "rewrite generated
markdown tables inside zh/sync/service-api-schema.{md,mdx}" responsibilities
are gone. The site renders machine artifacts directly via MDX components
(<EventKindTable/>, <OperationTable/>, <SchemaViewer/>, ...), so duplicating
them inside Markdown or under zh/ is no longer needed.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SPEC_ROOT = ROOT / "spec" / "v1"
ARTIFACTS = SPEC_ROOT / "artifacts"
REGISTRY = ARTIFACTS / "registry"
CONTRACT_CATALOG_PATH = REGISTRY / "contract-catalog.json"
PROFILE_REGISTRY_PATH = ARTIFACTS / "profiles" / "conformance-profiles.json"
LINT_SCRIPT = Path(__file__).with_name("lint_artifacts.py")
PROSE_LINT_SCRIPT = Path(__file__).with_name("lint_spec.py")
FIXTURE_DIGEST_SCRIPT = Path(__file__).with_name("check_fixture_digests.py")
COMPLETENESS_REPORT_SCRIPT = Path(__file__).with_name("gen_operation_completeness_report.py")
SITE_META_PATH = ROOT / "site" / "src" / "lib" / "site-meta.ts"
PUBLIC_V1 = ROOT / "site" / "public" / "v1"
OPERATION_SCHEMA_INDEX_PATH = ARTIFACTS / "reports" / "operation-schema-index.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def load_contract_catalog() -> dict[str, Any]:
    data = load_json(CONTRACT_CATALOG_PATH)
    if not isinstance(data, dict):
        raise SystemExit(f"invalid contract catalog: {CONTRACT_CATALOG_PATH}")
    return data


def catalog_generation_metadata(catalog: dict[str, Any]) -> tuple[str, str]:
    version = catalog.get("version")
    generated_at = catalog.get("generated_at")
    if not isinstance(version, str) or not version:
        raise SystemExit("contract catalog missing version")
    if not isinstance(generated_at, str) or not generated_at:
        raise SystemExit("contract catalog missing generated_at")
    try:
        datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SystemExit(f"contract catalog generated_at must be RFC3339: {generated_at}") from exc
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", version) and not generated_at.startswith(version):
        raise SystemExit("contract catalog generated_at date must match version")
    return version, generated_at


def current_release_tag() -> str:
    if not SITE_META_PATH.exists():
        raise SystemExit(f"missing site release metadata: {SITE_META_PATH.relative_to(ROOT).as_posix()}")
    text = SITE_META_PATH.read_text(encoding="utf-8")
    match = re.search(r'export const specReleaseTag\s*=\s*"([^"]+)";', text)
    if not match:
        raise SystemExit("site-meta.ts missing specReleaseTag")
    tag = match.group(1)
    if not tag.startswith("v"):
        raise SystemExit(f"specReleaseTag must start with 'v': {tag}")
    return tag


def current_public_catalog_path() -> Path:
    version = current_release_tag()[1:]
    return PUBLIC_V1 / f"contract-catalog-{version}.json"


def public_catalog_paths() -> list[Path]:
    return [current_public_catalog_path()]


def generated_registry_payloads(catalog: dict[str, Any]) -> dict[Path, dict[str, Any]]:
    version, generated_at = catalog_generation_metadata(catalog)
    generated = catalog.get("generated_registries")
    if not isinstance(generated, list) or not generated:
        raise SystemExit("contract catalog missing generated_registries")

    payloads: dict[Path, dict[str, Any]] = {}
    for row in generated:
        if not isinstance(row, dict):
            raise SystemExit("generated_registries rows must be objects")
        file_ref = row.get("file")
        section = row.get("section")
        if not isinstance(file_ref, str) or not file_ref:
            raise SystemExit("generated registry missing file")
        if not isinstance(section, str) or not section:
            raise SystemExit(f"generated registry {file_ref} missing section")
        section_payload = catalog.get(section)
        if not isinstance(section_payload, dict):
            raise SystemExit(f"contract catalog missing section {section}")
        section_payload = copy.deepcopy(section_payload)
        if section == "event_kind_registry":
            cell_contracts = section_payload.pop("cell_contracts", None)
            if not isinstance(cell_contracts, dict):
                raise SystemExit("event_kind_registry missing cell_contracts object")
            event_rows = section_payload.get("event_kinds")
            if not isinstance(event_rows, list):
                raise SystemExit("event_kind_registry.event_kinds must be an array")
            known_kinds = {
                event_row.get("event_kind")
                for event_row in event_rows
                if isinstance(event_row, dict)
            }
            unknown_contracts = sorted(set(cell_contracts) - known_kinds)
            if unknown_contracts:
                raise SystemExit(
                    "cell_contracts references unknown event kinds: "
                    + ", ".join(unknown_contracts)
                )
            for event_row in event_rows:
                if not isinstance(event_row, dict):
                    continue
                event_kind = event_row.get("event_kind")
                contract = cell_contracts.get(event_kind)
                if contract is None:
                    continue
                if not isinstance(contract, dict):
                    raise SystemExit(f"cell contract for {event_kind} must be an object")
                overlapping = sorted(set(event_row) & set(contract))
                if overlapping:
                    raise SystemExit(
                        f"cell contract for {event_kind} overlaps inline fields: "
                        + ", ".join(overlapping)
                    )
                event_row.update(copy.deepcopy(contract))
                writes = contract.get("cell_writes")
                if isinstance(writes, list) and len(writes) == 1 and isinstance(writes[0], dict):
                    # Preserve the v1 single-target shorthand for existing consumers while
                    # making cell_writes[] the general machine authority.
                    for field in ("cell_family", "cell_subject", "lattice", "bottom", "initial_value"):
                        if field in writes[0]:
                            event_row[field] = copy.deepcopy(writes[0][field])
        payloads[ARTIFACTS / file_ref] = {
            "version": version,
            "source_of_truth": False,
            "generated_at": generated_at,
            "generated_from": "registry/contract-catalog.json",
            "generated_by": "tools/artifact_pipeline.py",
            **section_payload,
        }
    return payloads


def resolve_schema_pointer(document: Any, fragment: str) -> Any:
    if not fragment or fragment == "#":
        return document
    if not fragment.startswith("#/"):
        raise KeyError(fragment)
    current = document
    for token in fragment[2:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and token in current:
            current = current[token]
        else:
            raise KeyError(fragment)
    return current


def schema_summary(schema_ref: str) -> dict[str, Any]:
    file_ref, _, fragment = schema_ref.partition("#")
    schema_path = ARTIFACTS / file_ref
    document = load_json(schema_path)
    schema = resolve_schema_pointer(document, f"#{fragment}" if fragment else "#")
    seen: set[tuple[str, str]] = set()
    while (
        isinstance(schema, dict)
        and isinstance(schema.get("$ref"), str)
        and set(schema.keys()) == {"$ref"}
    ):
        ref = schema["$ref"]
        key = (schema_path.as_posix(), ref)
        if key in seen:
            break
        seen.add(key)
        ref_file, _, ref_fragment = ref.partition("#")
        if ref_file:
            schema_path = (schema_path.parent / ref_file).resolve()
            document = load_json(schema_path)
        schema = resolve_schema_pointer(document, f"#{ref_fragment}" if ref_fragment else "#")
    if not isinstance(schema, dict):
        schema = {}
    properties = schema.get("properties")
    required = schema.get("required")
    additional_properties = schema.get("additionalProperties")
    return {
        "schema_ref": schema_ref,
        "schema_kind": schema.get("type") if isinstance(schema.get("type"), str) else None,
        "required": [field for field in required if isinstance(field, str)] if isinstance(required, list) else [],
        "properties": list(properties.keys()) if isinstance(properties, dict) else [],
        "closed": additional_properties is False,
    }


def operation_schema_index_payload(catalog: dict[str, Any]) -> dict[str, Any]:
    version, generated_at = catalog_generation_metadata(catalog)
    operation_registry = catalog.get("operation_registry")
    if not isinstance(operation_registry, dict):
        raise SystemExit("contract catalog missing operation_registry")

    operations: list[dict[str, Any]] = []
    for row in operation_registry.get("operations", []):
        if not isinstance(row, dict):
            continue
        operation_id = row.get("operation_id")
        if not isinstance(operation_id, str) or not operation_id:
            continue
        entry: dict[str, Any] = {
            "operation_id": operation_id,
            "success_shape_kind": row.get("success_shape_kind"),
        }
        request_schema_ref = row.get("request_schema_ref")
        if isinstance(request_schema_ref, str) and request_schema_ref:
            entry["request"] = schema_summary(request_schema_ref)
        response_schema_ref = row.get("response_schema_ref")
        if isinstance(response_schema_ref, str) and response_schema_ref:
            entry["response"] = schema_summary(response_schema_ref)
        if "request" in entry or "response" in entry:
            operations.append(entry)

    return {
        "version": version,
        "source_of_truth": False,
        "generated_at": generated_at,
        "generated_from": [
            "registry/contract-catalog.json",
            "schemas/*.schema.json"
        ],
        "generated_by": "tools/artifact_pipeline.py",
        "description": "Generated DTO index for registered operations with request_schema_ref/response_schema_ref. JSON Schema files remain the canonical source; this report is a machine-readable summary for SDK/conformance tooling and prose drift review.",
        "operations": operations,
    }


def profile_summary_text() -> str:
    data = load_json(PROFILE_REGISTRY_PATH)
    if not isinstance(data, dict):
        raise SystemExit("invalid conformance profile registry")
    implementation_profiles = data.get("implementation_profiles", [])
    deployment_profiles = data.get("deployment_profiles", [])
    vector_groups = data.get("vector_groups", [])
    hardening_profiles = data.get("hardening_profiles", [])
    profile_requirements = data.get("profile_requirements", {})
    return (
        "profile summary: "
        f"{len(implementation_profiles)} implementation, "
        f"{len(deployment_profiles)} deployment, "
        f"{len(vector_groups)} vector-group, "
        f"{len(hardening_profiles)} hardening, "
        f"{len(profile_requirements)} requirement blocks"
    )


def registry_diff_summary_text() -> str:
    drifts = check_generated_registries()
    if not drifts:
        return "registry diff: clean"
    return f"registry diff: {len(drifts)} generated artifact drift(s)"


def print_contract_status() -> None:
    print("contract policy: active-contract checks only")
    print(profile_summary_text())
    print(registry_diff_summary_text())


def write_generated_registries() -> None:
    for path, payload in generated_registry_payloads(load_contract_catalog()).items():
        path.write_text(dump_json(payload), encoding="utf-8", newline="\n")
        print(f"updated {path.relative_to(ROOT).as_posix()}")


def write_operation_schema_index() -> None:
    OPERATION_SCHEMA_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    OPERATION_SCHEMA_INDEX_PATH.write_text(
        dump_json(operation_schema_index_payload(load_contract_catalog())),
        encoding="utf-8",
        newline="\n",
    )
    print(f"updated {OPERATION_SCHEMA_INDEX_PATH.relative_to(ROOT).as_posix()}")


def write_public_catalog_snapshot() -> None:
    canonical_bytes = CONTRACT_CATALOG_PATH.read_bytes()
    PUBLIC_V1.mkdir(parents=True, exist_ok=True)
    for target in public_catalog_paths():
        target.write_bytes(canonical_bytes)
        print(f"updated {target.relative_to(ROOT).as_posix()}")


def check_generated_registries() -> list[str]:
    errors: list[str] = []
    for path, payload in generated_registry_payloads(load_contract_catalog()).items():
        expected = dump_json(payload)
        if not path.exists():
            errors.append(f"missing generated registry {path.relative_to(ROOT).as_posix()}")
            continue
        actual = path.read_text(encoding="utf-8")
        if actual != expected:
            errors.append(
                f"generated registry drift: {path.relative_to(ROOT).as_posix()} (run python tools/artifact_pipeline.py generate)"
            )
    return errors


def check_operation_schema_index() -> list[str]:
    errors: list[str] = []
    expected = dump_json(operation_schema_index_payload(load_contract_catalog()))
    if not OPERATION_SCHEMA_INDEX_PATH.exists():
        errors.append(
            f"missing operation schema index {OPERATION_SCHEMA_INDEX_PATH.relative_to(ROOT).as_posix()} "
            "(run python tools/artifact_pipeline.py generate)"
        )
        return errors
    actual = OPERATION_SCHEMA_INDEX_PATH.read_text(encoding="utf-8")
    if actual != expected:
        errors.append(
            f"operation schema index drift: {OPERATION_SCHEMA_INDEX_PATH.relative_to(ROOT).as_posix()} "
            "(run python tools/artifact_pipeline.py generate)"
        )
    return errors


def run_lint() -> int:
    result = subprocess.run([sys.executable, str(LINT_SCRIPT)], cwd=ROOT)
    return result.returncode


def run_prose_lint() -> int:
    result = subprocess.run([sys.executable, str(PROSE_LINT_SCRIPT)], cwd=ROOT)
    return result.returncode


def run_fixture_digest_check() -> int:
    result = subprocess.run([sys.executable, str(FIXTURE_DIGEST_SCRIPT)], cwd=ROOT)
    return result.returncode


def run_operation_completeness_report(mode: str) -> int:
    result = subprocess.run(
        [sys.executable, str(COMPLETENESS_REPORT_SCRIPT), mode], cwd=ROOT
    )
    return result.returncode


def cmd_generate(_: argparse.Namespace) -> int:
    write_generated_registries()
    write_operation_schema_index()
    completeness_status = run_operation_completeness_report("generate")
    print_contract_status()
    return completeness_status


def cmd_check(_: argparse.Namespace) -> int:
    errors = check_generated_registries()
    errors.extend(check_operation_schema_index())
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        print("contract policy: active-contract checks only")
        print(profile_summary_text())
        print(f"registry diff: {len(errors)} pre-lint pipeline error(s)")
        return 1
    print_contract_status()
    completeness_status = run_operation_completeness_report("check")
    fixture_status = run_fixture_digest_check()
    lint_status = run_lint()
    prose_lint_status = run_prose_lint()
    return completeness_status or fixture_status or lint_status or prose_lint_status


def cmd_snapshot(_: argparse.Namespace) -> int:
    write_public_catalog_snapshot()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser(
        "generate",
        help="regenerate derived registry views from contract-catalog.json",
    )
    generate_parser.set_defaults(func=cmd_generate)

    check_parser = subparsers.add_parser(
        "check",
        help="check generated registries and run artifact lint",
    )
    check_parser.set_defaults(func=cmd_check)

    snapshot_parser = subparsers.add_parser(
        "snapshot",
        help="write the version-pinned public catalog snapshot under site/public/v1 (build/deploy step; not committed)",
    )
    snapshot_parser.set_defaults(func=cmd_snapshot)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
