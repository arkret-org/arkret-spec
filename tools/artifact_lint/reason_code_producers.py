"""Reason-code producer-path ratchet.

Ruling ``2026-09-04-1752`` (workflow profile stage transition): a whole
state-machine semantics had been "promised" to implementations through a single
error-code registry entry (``invalid_task_fsm_transition``) that no event kind,
reducer contract, operation mapping, schema, fixture or profile ever produced.
``fsm_contracts`` has ``check_fsm_state_reachability``; the error-code registry
had no reachability gate of its own, so prose could mint a code and the
machine contract never noticed. This check closes that hole as a ratchet:

* every ``reason_codes[].code`` in ``error-code-registry.json`` MUST be
  referenced as a bare token by at least one other machine artifact under
  ``spec/v1/artifacts`` (registry / schemas / profiles / fixtures / openapi /
  bindings -- generated ``reports/`` do not count, they are views of the
  others), OR be listed in the frozen baseline
  ``tools/reason-code-producer-baseline.json``;
* a baseline code that gains a reference MUST be removed from the baseline
  (the list only shrinks, never grows);
* a baseline code that no longer exists in the registry is stale and fails;
* a code listed under ``removed_reason_codes`` MUST NOT come back -- not in
  the registry, not in any artifact (reports included), not in prose.

"Referenced by a machine artifact" is deliberately the loosest objective
criterion: a bare-token hit anywhere in a JSON / YAML artifact, including a
reducer contract's ``payload`` prose. It is still a real binding because it
lives in a source-of-truth artifact that implementations consume; a code that
does not clear even this bar exists only in the registry that defines it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .core import ARTIFACTS, SPEC_ROOT, TOOLS_ROOT, Lint, load_json

REASON_CODE_PRODUCER_BASELINE_PATH = TOOLS_ROOT / "reason-code-producer-baseline.json"
ERROR_CODE_REGISTRY_RELATIVE = Path("registry") / "error-code-registry.json"
_ARTIFACT_SUFFIXES = {".json", ".yaml", ".yml"}
_CODE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_BASELINE_KEYS = {
    "$schema",
    "version",
    "kind",
    "source_of_truth",
    "generated_from",
    "generated_by",
    "description",
    "unreferenced_reason_codes",
    "removed_reason_codes",
}
_REMOVED_ROW_KEYS = {"code", "ruling", "registry_version", "why"}


def _bare_token_pattern(codes: list[str]) -> re.Pattern[str] | None:
    if not codes:
        return None
    alternation = "|".join(re.escape(code) for code in sorted(codes, key=len, reverse=True))
    return re.compile(rf"(?<![A-Za-z0-9_])(?:{alternation})(?![A-Za-z0-9_])")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def registry_reason_codes(lint: Lint, artifacts_root: Path) -> list[str] | None:
    """Return the ordered ``reason_codes[].code`` list, or None on a malformed registry."""
    registry_path = artifacts_root / ERROR_CODE_REGISTRY_RELATIVE
    document = load_json(lint, registry_path)
    if not isinstance(document, dict) or not isinstance(document.get("reason_codes"), list):
        lint.fail(registry_path, "reason_codes[] must be a list")
        return None
    codes: list[str] = []
    for index, row in enumerate(document["reason_codes"]):
        code = row.get("code") if isinstance(row, dict) else None
        if not isinstance(code, str) or not _CODE_RE.fullmatch(code):
            lint.fail(registry_path, f"reason_codes[{index}].code must be a snake_case string")
            continue
        codes.append(code)
    return codes


def producer_artifact_files(artifacts_root: Path) -> list[Path]:
    """Machine artifacts that may carry a producer path for a reason code."""
    registry_path = (artifacts_root / ERROR_CODE_REGISTRY_RELATIVE).resolve()
    reports_root = (artifacts_root / "reports").resolve()
    files: list[Path] = []
    for path in sorted(artifacts_root.rglob("*")):
        if not path.is_file() or path.suffix not in _ARTIFACT_SUFFIXES:
            continue
        resolved = path.resolve()
        if resolved == registry_path:
            continue
        if reports_root in resolved.parents:
            continue
        files.append(path)
    return files


def referenced_reason_codes(codes: list[str], files: list[Path]) -> set[str]:
    """Codes that appear as a bare token in at least one of ``files``."""
    pattern = _bare_token_pattern(codes)
    if pattern is None:
        return set()
    seen: set[str] = set()
    for path in files:
        for match in pattern.finditer(_read_text(path)):
            seen.add(match.group(0))
            if len(seen) == len(codes):
                return seen
    return seen


def unreferenced_reason_codes(lint: Lint, artifacts_root: Path = ARTIFACTS) -> list[str]:
    """Sorted codes with no producer reference -- the material of the baseline file."""
    codes = registry_reason_codes(lint, artifacts_root)
    if codes is None:
        return []
    referenced = referenced_reason_codes(codes, producer_artifact_files(artifacts_root))
    return sorted(code for code in codes if code not in referenced)


def load_baseline(lint: Lint, baseline_path: Path) -> dict[str, Any] | None:
    document = load_json(lint, baseline_path)
    if not isinstance(document, dict):
        lint.fail(baseline_path, "baseline must be a JSON object")
        return None
    unknown = set(document) - _BASELINE_KEYS
    missing = {"kind", "unreferenced_reason_codes", "removed_reason_codes"} - set(document)
    if unknown or missing:
        lint.fail(
            baseline_path,
            f"baseline key set is closed; unknown {sorted(unknown)}, missing {sorted(missing)}",
        )
        return None
    if document.get("kind") != "reason_code_producer_baseline":
        lint.fail(baseline_path, "kind must be reason_code_producer_baseline")
        return None
    unreferenced = document["unreferenced_reason_codes"]
    if not isinstance(unreferenced, list) or not all(
        isinstance(code, str) and _CODE_RE.fullmatch(code) for code in unreferenced
    ):
        lint.fail(baseline_path, "unreferenced_reason_codes must be a list of snake_case codes")
        return None
    if unreferenced != sorted(set(unreferenced)):
        lint.fail(
            baseline_path,
            "unreferenced_reason_codes must be sorted and unique so the ledger stays hand-auditable",
        )
        return None
    removed = document["removed_reason_codes"]
    if not isinstance(removed, list):
        lint.fail(baseline_path, "removed_reason_codes must be a list")
        return None
    seen_removed: set[str] = set()
    for index, row in enumerate(removed):
        if not isinstance(row, dict) or set(row) != _REMOVED_ROW_KEYS:
            lint.fail(
                baseline_path,
                f"removed_reason_codes[{index}] must carry exactly {sorted(_REMOVED_ROW_KEYS)}",
            )
            return None
        if not all(isinstance(row[key], str) and row[key].strip() for key in _REMOVED_ROW_KEYS):
            lint.fail(baseline_path, f"removed_reason_codes[{index}] fields must be non-empty strings")
            return None
        if not _CODE_RE.fullmatch(row["code"]):
            lint.fail(baseline_path, f"removed_reason_codes[{index}].code must be snake_case")
            return None
        if "/" in row["ruling"] or "\\" in row["ruling"]:
            lint.fail(
                baseline_path,
                f"removed_reason_codes[{index}].ruling names the ruling, never a repository path",
            )
            return None
        if row["code"] in seen_removed:
            lint.fail(baseline_path, f"removed_reason_codes[{index}].code is duplicated")
            return None
        seen_removed.add(row["code"])
    overlap = seen_removed & set(unreferenced)
    if overlap:
        lint.fail(
            baseline_path,
            f"codes cannot be both removed and baselined-unreferenced: {sorted(overlap)}",
        )
        return None
    return document


def prose_files(prose_roots: tuple[Path, ...]) -> list[Path]:
    files: list[Path] = []
    for root in prose_roots:
        if root.is_dir():
            files.extend(sorted(root.rglob("*.md")))
    return files


def check_reason_code_producer_paths(
    lint: Lint,
    *,
    artifacts_root: Path = ARTIFACTS,
    baseline_path: Path = REASON_CODE_PRODUCER_BASELINE_PATH,
    prose_roots: tuple[Path, ...] = (SPEC_ROOT / "zh", SPEC_ROOT / "en"),
) -> None:
    """Every registered reason code has a producer path or sits in the frozen baseline;
    removed codes never come back."""
    registry_path = artifacts_root / ERROR_CODE_REGISTRY_RELATIVE
    codes = registry_reason_codes(lint, artifacts_root)
    baseline = load_baseline(lint, baseline_path)
    if codes is None or baseline is None:
        return
    code_set = set(codes)
    baselined = set(baseline["unreferenced_reason_codes"])
    removed_rows = baseline["removed_reason_codes"]
    removed = [row["code"] for row in removed_rows]

    files = producer_artifact_files(artifacts_root)
    referenced = referenced_reason_codes(codes, files)

    for code in codes:
        if code in referenced or code in baselined:
            continue
        lint.fail(
            registry_path,
            f"reason code {code} has no producer path: no registry / schema / profile / "
            "fixture / openapi / binding artifact references it. Register the producer "
            "(reducer contract, operation error mapping, schema or fixture) or do not "
            "register the code; new entries in the baseline are not accepted",
        )
    for code in sorted(baselined):
        if code not in code_set:
            lint.fail(
                baseline_path,
                f"baseline lists {code} but error-code-registry.json no longer registers it; "
                "drop the stale row",
            )
        elif code in referenced:
            lint.fail(
                baseline_path,
                f"{code} now has a producer reference; remove it from unreferenced_reason_codes "
                "(the baseline only shrinks)",
            )

    if not removed:
        return
    for code in removed:
        if code in code_set:
            lint.fail(
                registry_path,
                f"reason code {code} was removed by a ruling and MUST NOT be re-registered",
            )
    pattern = _bare_token_pattern(removed)
    assert pattern is not None
    residue_files = [
        path
        for path in sorted(artifacts_root.rglob("*"))
        if path.is_file()
        and path.suffix in _ARTIFACT_SUFFIXES
        and path.resolve() != registry_path.resolve()
    ] + prose_files(prose_roots)
    for path in residue_files:
        hits = sorted({match.group(0) for match in pattern.finditer(_read_text(path))})
        for code in hits:
            lint.fail(
                path,
                f"removed reason code {code} still appears here; the ruling that removed it "
                "requires zero residue",
            )


def baseline_document(codes: list[str], removed_rows: list[dict[str, str]]) -> dict[str, Any]:
    """Shape of ``tools/reason-code-producer-baseline.json`` (used to (re)generate it)."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "version": 1,
        "kind": "reason_code_producer_baseline",
        "source_of_truth": False,
        "generated_from": [
            "spec/v1/artifacts/registry/error-code-registry.json",
            "spec/v1/artifacts",
        ],
        "generated_by": "tools/artifact_lint (check_reason_code_producer_paths)",
        "description": (
            "Frozen ledger of reason codes that error-code-registry.json registers but no "
            "other machine artifact under spec/v1/artifacts references as a bare token "
            "(generated reports excluded). Adopted by ruling 2026-09-04-1752 after "
            "invalid_task_fsm_transition was found to describe a state machine that no "
            "event kind, cell family or fsm contract could ever produce. The list is a "
            "ratchet: check_reason_code_producer_paths fails on any new unreferenced code "
            "and on any listed code that gains a reference without being dropped here. "
            "removed_reason_codes pins codes a ruling deleted so they cannot return."
        ),
        "unreferenced_reason_codes": sorted(codes),
        "removed_reason_codes": removed_rows,
    }


def dump_baseline(document: dict[str, Any]) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"
