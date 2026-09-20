"""Validated access to the closed executable release-tool manifest."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, TypeVar


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "tools" / "release-tool-manifest.json"
T = TypeVar("T")


def load_manifest(path: Path = MANIFEST_PATH, root: Path = ROOT) -> dict:
    body = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(body, dict) or set(body) != {
        "version",
        "source_of_truth",
        "generated_at",
        "description",
        "pipelines",
        "checks",
    }:
        raise ValueError(f"{path}: release tool manifest has an open or incomplete shape")
    if body.get("source_of_truth") is not True:
        raise ValueError(f"{path}: source_of_truth must be true")
    checks = body.get("checks")
    if not isinstance(checks, list) or not checks:
        raise ValueError(f"{path}: checks must be a non-empty array")
    ids: list[str] = []
    for index, row in enumerate(checks):
        if not isinstance(row, dict) or set(row) != {"check_id", "label", "owner_script"}:
            raise ValueError(f"{path}: checks[{index}] has an open or incomplete shape")
        if not all(isinstance(row[key], str) and row[key] for key in row):
            raise ValueError(f"{path}: checks[{index}] fields must be non-empty strings")
        ids.append(row["check_id"])
        owner = (root / row["owner_script"]).resolve()
        if not owner.is_relative_to(root.resolve()) or not owner.is_file():
            raise ValueError(f"{path}: check {row['check_id']} owner script does not exist")
    if ids != sorted(set(ids)):
        raise ValueError(f"{path}: checks must be sorted by unique check_id")
    pipelines = body.get("pipelines")
    if not isinstance(pipelines, dict) or set(pipelines) != {
        "artifact_check",
        "release_default",
        "release_strict",
    }:
        raise ValueError(f"{path}: pipelines must define the closed release pipeline set")
    known = set(ids)
    for name, values in pipelines.items():
        if not isinstance(values, list) or not values or not all(isinstance(value, str) for value in values):
            raise ValueError(f"{path}: pipeline {name} must be a non-empty string array")
        if len(values) != len(set(values)):
            raise ValueError(f"{path}: pipeline {name} repeats a check id")
        unknown = sorted(set(values) - known)
        if unknown:
            raise ValueError(f"{path}: pipeline {name} names unknown checks: {unknown}")
    if not set(pipelines["release_default"]).issubset(pipelines["release_strict"]):
        raise ValueError(f"{path}: release_strict must contain every default check")
    return body


def registered_runners(
    pipeline: str,
    runners: dict[str, Callable[[], T]],
    *,
    manifest: dict | None = None,
) -> list[tuple[str, Callable[[], T]]]:
    body = load_manifest() if manifest is None else manifest
    pipeline_ids = body["pipelines"].get(pipeline)
    if not isinstance(pipeline_ids, list):
        raise ValueError(f"unknown release tool pipeline {pipeline!r}")
    manifest_ids = {
        check_id
        for name, values in body["pipelines"].items()
        if name == pipeline or (pipeline.startswith("release_") and name.startswith("release_"))
        for check_id in values
    }
    if set(runners) != manifest_ids:
        missing = sorted(manifest_ids - set(runners))
        unregistered = sorted(set(runners) - manifest_ids)
        raise ValueError(
            f"runner inventory differs from manifest: missing={missing}, unregistered={unregistered}"
        )
    labels = {row["check_id"]: row["label"] for row in body["checks"]}
    return [(labels[check_id], runners[check_id]) for check_id in pipeline_ids]
