"""Reason-code producer-path ratchet.

Ruling ``2026-09-04-1752`` (workflow profile stage transition): a whole
state-machine semantics had been "promised" to implementations through a single
error-code registry entry (``invalid_task_fsm_transition``) that no event kind,
reducer contract, operation mapping, schema, fixture or profile ever produced.
``transition_contracts`` has ``check_fsm_state_reachability``; the error-code registry
had no reachability gate of its own, so prose could mint a code and the
machine contract never noticed. This check closes that hole as a ratchet:

* every public ``codes[].code`` and ``reason_codes[].code`` is explicitly
  ``active`` or ``reserved``;
* an ``active`` code MUST be referenced as a bare token by at least one other
  machine artifact under ``spec/v1/artifacts`` (generated ``reports/`` do not
  count); a ``reserved`` code MUST NOT be referenced there and carries a
  closed ``applies_to`` plus ``activation_condition`` declaration;
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
_REMOVED_ROW_REQUIRED_KEYS = {"code", "ruling", "registry_version", "why"}
_REMOVED_ROW_OPTIONAL_KEYS = {"carried_by_code"}
_STATUS_VALUES = {"active", "reserved"}


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


def registry_code_rows(
    lint: Lint, artifacts_root: Path
) -> dict[str, list[dict[str, Any]]] | None:
    """Return both public code arrays after validating their basic row identity."""
    registry_path = artifacts_root / ERROR_CODE_REGISTRY_RELATIVE
    document = load_json(lint, registry_path)
    if not isinstance(document, dict):
        return None
    result: dict[str, list[dict[str, Any]]] = {}
    seen: set[str] = set()
    for field in ("codes", "reason_codes"):
        rows = document.get(field)
        if not isinstance(rows, list):
            lint.fail(registry_path, f"{field}[] must be a list")
            return None
        accepted: list[dict[str, Any]] = []
        for index, row in enumerate(rows):
            code = row.get("code") if isinstance(row, dict) else None
            if not isinstance(code, str) or not _CODE_RE.fullmatch(code):
                lint.fail(registry_path, f"{field}[{index}].code must be a snake_case string")
                continue
            identity = f"{field}:{code}"
            if identity in seen:
                lint.fail(registry_path, f"{field}[{index}].code duplicates {code}")
                continue
            seen.add(identity)
            accepted.append(row)
        result[field] = accepted
    return result


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
        keys = set(row) if isinstance(row, dict) else set()
        if (
            not isinstance(row, dict)
            or not _REMOVED_ROW_REQUIRED_KEYS <= keys
            or keys - _REMOVED_ROW_REQUIRED_KEYS - _REMOVED_ROW_OPTIONAL_KEYS
        ):
            lint.fail(
                baseline_path,
                f"removed_reason_codes[{index}] must carry {sorted(_REMOVED_ROW_REQUIRED_KEYS)} "
                f"and only optional {sorted(_REMOVED_ROW_OPTIONAL_KEYS)}",
            )
            return None
        if not all(
            isinstance(row[key], str) and row[key].strip()
            for key in _REMOVED_ROW_REQUIRED_KEYS
        ):
            lint.fail(baseline_path, f"removed_reason_codes[{index}] fields must be non-empty strings")
            return None
        carrier = row.get("carried_by_code")
        if carrier is not None and (
            not isinstance(carrier, str) or not _CODE_RE.fullmatch(carrier)
        ):
            lint.fail(
                baseline_path,
                f"removed_reason_codes[{index}].carried_by_code must be a snake_case code",
            )
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
    """Both error-code arrays have a closed active/reserved producer contract."""
    registry_path = artifacts_root / ERROR_CODE_REGISTRY_RELATIVE
    code_rows = registry_code_rows(lint, artifacts_root)
    baseline = load_baseline(lint, baseline_path)
    if code_rows is None or baseline is None:
        return
    reason_codes = [row["code"] for row in code_rows["reason_codes"]]
    code_set = set(reason_codes)
    baselined = set(baseline["unreferenced_reason_codes"])
    removed_rows = baseline["removed_reason_codes"]
    removed = [row["code"] for row in removed_rows]

    files = producer_artifact_files(artifacts_root)
    all_codes = [row["code"] for field in ("codes", "reason_codes") for row in code_rows[field]]
    referenced = referenced_reason_codes(all_codes, files)

    if baselined:
        lint.fail(
            baseline_path,
            "unreferenced_reason_codes must be empty; reachability state now lives on every "
            "registry row as active or reserved",
        )

    for field in ("codes", "reason_codes"):
        for index, row in enumerate(code_rows[field]):
            code = row["code"]
            status = row.get("status")
            where = f"{field}[{index}] ({code})"
            if status not in _STATUS_VALUES:
                lint.fail(
                    registry_path,
                    f"{where}.status must be one of {sorted(_STATUS_VALUES)}",
                )
                continue
            has_producer = code in referenced
            if status == "active":
                if not has_producer:
                    lint.fail(
                        registry_path,
                        f"{where} is active but has no machine producer path",
                    )
                if "activation_condition" in row:
                    lint.fail(
                        registry_path,
                        f"{where} is active and MUST NOT retain activation_condition",
                    )
                continue
            applies_to = row.get("applies_to")
            if not isinstance(applies_to, list) or not applies_to or not all(
                isinstance(value, str) and value for value in applies_to
            ) or len(applies_to) != len(set(applies_to)):
                lint.fail(
                    registry_path,
                    f"{where} is reserved and requires a non-empty unique applies_to[]",
                )
            condition = row.get("activation_condition")
            if not isinstance(condition, str) or not condition.strip():
                lint.fail(
                    registry_path,
                    f"{where} is reserved and requires activation_condition",
                )
            if has_producer:
                lint.fail(
                    registry_path,
                    f"{where} is reserved but a machine artifact emits/references it; "
                    "reserved codes MUST NOT be emitted",
                )

    top_rows = {row["code"]: row for row in code_rows["codes"]}
    for index, row in enumerate(removed_rows):
        carrier = row.get("carried_by_code")
        if carrier is None:
            continue
        carrier_row = top_rows.get(carrier)
        if carrier_row is None:
            lint.fail(
                baseline_path,
                f"removed_reason_codes[{index}].carried_by_code {carrier} is not a top-level code",
            )
        elif carrier_row.get("status") != "active" or carrier not in referenced:
            lint.fail(
                baseline_path,
                f"removed_reason_codes[{index}].carried_by_code {carrier} must be active "
                "and have a machine producer path",
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
        "version": 2,
        "kind": "reason_code_producer_baseline",
        "source_of_truth": False,
        "generated_from": [
            "spec/v1/artifacts/registry/error-code-registry.json",
            "spec/v1/artifacts",
        ],
        "generated_by": "tools/artifact_lint (check_reason_code_producer_paths)",
        "description": (
            "Tombstone ledger for reason codes removed by adjudication. Live reachability "
            "is declared per row in error-code-registry.json as active or reserved; "
            "unreferenced_reason_codes is closed to empty. removed_reason_codes pins codes "
            "a ruling deleted so they cannot return and may name an active replacement "
            "through carried_by_code."
        ),
        "unreferenced_reason_codes": sorted(codes),
        "removed_reason_codes": removed_rows,
    }


def dump_baseline(document: dict[str, Any]) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"
