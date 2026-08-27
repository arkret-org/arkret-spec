"""Read and validate the canonical v1 publication metadata."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RELEASE_METADATA_PATH = ROOT / "spec/v1/release-metadata.json"
RELEASE_TAG_RE = re.compile(
    r"^v(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
    r"(?P<candidate>-candidate(?:\.[0-9A-Za-z-]+)*)?$"
)


def load_release_metadata(path: Path = RELEASE_METADATA_PATH) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: release metadata must be a JSON object")
    if data.get("format_version") != 1:
        raise ValueError(f"{path}: unsupported release metadata format_version")
    tag = data.get("release_tag")
    if not isinstance(tag, str) or not RELEASE_TAG_RE.fullmatch(tag):
        raise ValueError(
            f"{path}: release_tag must be a stable or candidate semantic release tag"
        )
    return data


def current_release_tag() -> str:
    return load_release_metadata()["release_tag"]


def is_candidate_release_tag(tag: str) -> bool:
    match = RELEASE_TAG_RE.fullmatch(tag)
    return match is not None and match.group("candidate") is not None
