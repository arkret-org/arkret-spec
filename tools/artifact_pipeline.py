#!/usr/bin/env python3
"""Unified artifact maintenance pipeline for Contrix spec.

Layout (post-restructure):

  spec/v1/zh/                          normative Chinese prose
  spec/v1/en/                          normative English prose (placeholder)
  spec/v1/artifacts/registry/          canonical + generated registry views
  spec/v1/artifacts/profiles/          conformance profiles
  spec/v1/artifacts/schemas/           JSON Schemas
  spec/v1/artifacts/openapi/           OpenAPI document(s)
  spec/v1/artifacts/bindings/          non-HTTP bindings
  spec/v1/artifacts/fixtures/          conformance fixtures

This pipeline owns two responsibilities only:

  generate   regenerate derived registry views from contract-catalog.json
  check      verify no drift, then run lint_artifacts.py

The legacy "sync canonical files into zh/ mirrors" and "rewrite generated
markdown tables inside zh/sync/service-api-schema.{md,mdx}" responsibilities
are gone. The site renders machine artifacts directly via MDX components
(<EventKindTable/>, <OperationTable/>, <SchemaViewer/>, ...), so duplicating
them inside Markdown or under zh/ is no longer needed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SPEC_ROOT = ROOT / "spec" / "v1"
ARTIFACTS = SPEC_ROOT / "artifacts"
REGISTRY = ARTIFACTS / "registry"
CONTRACT_CATALOG_PATH = REGISTRY / "contract-catalog.json"
PROFILE_REGISTRY_PATH = ARTIFACTS / "profiles" / "conformance-profiles.json"
LINT_SCRIPT = Path(__file__).with_name("lint_artifacts.py")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def load_contract_catalog() -> dict[str, Any]:
    data = load_json(CONTRACT_CATALOG_PATH)
    if not isinstance(data, dict):
        raise SystemExit(f"invalid contract catalog: {CONTRACT_CATALOG_PATH}")
    return data


def generated_registry_payloads(catalog: dict[str, Any]) -> dict[Path, dict[str, Any]]:
    version = catalog.get("version")
    generated = catalog.get("generated_registries")
    if not isinstance(version, str) or not version:
        raise SystemExit("contract catalog missing version")
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
        payloads[ARTIFACTS / file_ref] = {
            "version": version,
            "source_of_truth": False,
            "generated_from": "registry/contract-catalog.json",
            "generated_by": "tools/artifact_pipeline.py",
            **section_payload,
        }
    return payloads


def profile_summary_text() -> str:
    data = load_json(PROFILE_REGISTRY_PATH)
    if not isinstance(data, dict):
        raise SystemExit("invalid conformance profile registry")
    implementation_profiles = data.get("implementation_profiles", [])
    deployment_profiles = data.get("deployment_profiles", [])
    vector_profiles = data.get("vector_profiles", [])
    hardening_profiles = data.get("hardening_profiles", [])
    profile_requirements = data.get("profile_requirements", {})
    return (
        "profile summary: "
        f"{len(implementation_profiles)} implementation, "
        f"{len(deployment_profiles)} deployment, "
        f"{len(vector_profiles)} vector, "
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
        path.write_text(dump_json(payload), encoding="utf-8")
        print(f"updated {path.relative_to(ROOT).as_posix()}")


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


def run_lint() -> int:
    result = subprocess.run([sys.executable, str(LINT_SCRIPT)], cwd=ROOT)
    return result.returncode


def cmd_generate(_: argparse.Namespace) -> int:
    write_generated_registries()
    print_contract_status()
    return 0


def cmd_check(_: argparse.Namespace) -> int:
    errors = check_generated_registries()
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        print("contract policy: active-contract checks only")
        print(profile_summary_text())
        print(f"registry diff: {len(errors)} pre-lint pipeline error(s)")
        return 1
    print_contract_status()
    return run_lint()


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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
