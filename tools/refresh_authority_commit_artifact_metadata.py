#!/usr/bin/env python3
"""Advance metadata for artifacts changed by the authority-commit migration."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from check_artifact_versions import semantic_content_digest, transition_errors


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "spec/v1/artifacts"
CONTRACT = ARTIFACTS / "registry/contract-registry.json"
REFERENCE = ARTIFACTS / "reports/artifact-version-digests.json"
VERSION = "2026-09-16.9"
GENERATED_AT = "2026-09-16T19:00:00+08:00"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def current_row(path: Path, value: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "version": value.get("version"),
        "generated_at": value.get("generated_at"),
        "content_digest": semantic_content_digest(value),
    }


def main() -> int:
    reference = load(REFERENCE)
    previous = {
        row["path"]: row
        for row in reference.get("artifacts", [])
        if isinstance(row, dict) and isinstance(row.get("path"), str)
    }
    contract = load(CONTRACT)
    generated_paths: set[str] = set()

    for view in contract.get("derived_registry_views", []):
        if not isinstance(view, dict):
            continue
        relative = view.get("file")
        section_name = view.get("section")
        if not isinstance(relative, str) or not isinstance(section_name, str):
            continue
        artifact_path = ARTIFACTS / relative
        if not artifact_path.exists():
            continue
        repository_relative = artifact_path.relative_to(ROOT).as_posix()
        generated_paths.add(repository_relative)
        old = previous.get(repository_relative)
        artifact = load(artifact_path)
        if old is None or old.get("content_digest") == semantic_content_digest(artifact):
            continue
        section = contract.get(section_name)
        if not isinstance(section, dict):
            raise SystemExit(f"missing generated section {section_name}")
        section["version"] = VERSION
        if "generated_at" in section:
            section["generated_at"] = GENERATED_AT

    save(CONTRACT, contract)
    subprocess.run(
        [sys.executable, "tools/artifact_pipeline.py", "generate"],
        cwd=ROOT,
        check=True,
    )

    changed = 0
    for directory in (ARTIFACTS / "registry", ARTIFACTS / "profiles"):
        for path in sorted(directory.glob("*.json")):
            value = load(path)
            if not isinstance(value, dict) or "version" not in value:
                continue
            row = current_row(path, value)
            old = previous.get(row["path"])
            if old is None or not transition_errors(old, row):
                continue
            if row["path"] in generated_paths:
                raise SystemExit(f"generated artifact metadata did not advance: {row['path']}")
            old_version = old.get("version")
            value["version"] = old_version + 1 if isinstance(old_version, int) else VERSION
            if value.get("generated_at") is not None:
                value["generated_at"] = GENERATED_AT
            save(path, value)
            changed += 1

    print(f"advanced authority-commit artifact metadata for {changed} canonical artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
