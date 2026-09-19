"""Close Event-submit request replay identity without deciding peer DTO shape."""

from __future__ import annotations

from typing import Any

from .core import ARTIFACTS, SPEC_ROOT, Lint, load_json, read_text


CONTRACT = ARTIFACTS / "registry" / "contract-registry.json"
PROSE = SPEC_ROOT / "zh" / "sync" / "api-conventions.md"

OPERATIONS = {
    "ak.self.events.command.submit.v1",
    "ak.peer.events.command.submit.v1",
}


def _fail(lint: Lint, path: Any, message: str) -> None:
    lint.fail(path, f"event-submit idempotency: {message}")


def _find(rows: Any, key: str, value: str) -> dict[str, Any] | None:
    if not isinstance(rows, list):
        return None
    return next((row for row in rows if isinstance(row, dict) and row.get(key) == value), None)


def check_event_submit_idempotency(lint: Lint) -> None:
    contract = load_json(lint, CONTRACT)
    if not isinstance(contract, dict):
        return

    operations = contract.get("operation_registry", {}).get("operations")
    for operation_id in sorted(OPERATIONS):
        row = _find(operations, "operation_id", operation_id)
        if not isinstance(row, dict):
            _fail(lint, CONTRACT, f"{operation_id} row is missing")
            continue
        if (
            row.get("idempotency_mechanism") != "canonical_hash"
            or row.get("canonical_hash_input") != "full_body"
            or row.get("retry_safe") is not True
        ):
            _fail(lint, CONTRACT, f"{operation_id} must remain canonical_hash/full_body/retry_safe=true")
    prose = read_text(PROSE) if PROSE.is_file() else ""
    required_markers = (
        "均登记为 `canonical_hash / full_body / retry_safe=true`",
        "外层 request replay identity 是完整 `submit_request` canonical body 的 SHA-256",
        "普通 Event 分支即完整 `EventCommitSubmission`",
        "内层 `event_id` 只是不变 Event 内容身份",
        "`event_id_digest_mismatch` 且零副作用",
        "`witness_disagreement` reason",
        "至少 24 小时记录下限",
        "同 identity 异完整 body 的 `duplicate_conflict`",
        "具体 request／outcome shape 只由 operation registry 同行的 `request_schema_ref`／`response_schema_ref` 决定",
        "当前登记 schema 没有可供 `accepted[]`／`duplicate[]` 求差的逐项结果",
        "调用方不得据此构造 partial retry",
        "同一 24 小时保留窗口内",
        "不由本段幂等规则预先裁决",
    )
    for marker in required_markers:
        if marker not in prose:
            _fail(lint, PROSE, f"normative prose omits {marker!r}")
    forbidden_markers = (
        "虽登记为 `protocol_sequence`",
        "以 `event_id` 作为 request identity 的事件提交",
        "（`Idempotency-Key` / `event_id` /",
        "按 `accepted[] ∪ duplicate[]` 求差重组的 partial retry",
        "复用原 `Idempotency-Key`",
    )
    for marker in forbidden_markers:
        if marker in prose:
            _fail(lint, PROSE, f"normative prose retains obsolete claim {marker!r}")
