# Federation Wire Protocol Draft

## 1. 目标

本文定义跨域服务间交易、跨域加入、backfill authorization 与 fork detection。

## 2. Service Authentication

每个 federation service MUST have DID。请求 MUST 使用 HTTP Message Signatures，并绑定：

- method
- target URI
- date
- content digest
- source service DID
- destination service DID

## 3. Transaction

```text
PUT /api/v1/federation/transactions/{txn_id}
```

请求字段：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `txn_id` | path | `id` | required | 幂等 transaction ID；path 值 MUST 与 body 中 `txn_id` 一致。 |
| `origin` | body | `did` | required | 来源 service DID。 |
| `destination` | body | `did` | required | 目标 service DID；MUST 与 HTTP Message Signature、目标 URL、DID service endpoint、Space policy 和 `service_binding_ref` 一致。 |
| `service_binding_ref` | body | `object` | required | 接收方服务绑定快照。 |
| `service_binding_ref.space_policy_hash` | body | `sha256:<hash>` | required | Space policy 版本或 hash。 |
| `service_binding_ref.membership_frontier` | body | `id[]` | required | membership / policy 因果前沿。 |
| `service_binding_ref.destination_service_type` | body | `string` | required | 目标服务类型，例如 `principal_server`。 |
| `events` | body | `object[]` | required | 签名 Event Envelope 数组；每项独立验签和授权。 |
| `receipts` | body | `object[]` | optional | 与本 transaction 相关的 receipt / witness 证明。 |
| `frontier` | body | `object` | optional | 发送方当前 causal frontier。 |
| `created_at` | body | `datetime` | optional | 发送方创建时间；不得作为授权依据。 |

请求示例（非完整 schema）：

```json
{
  "txn_id": "cx:txn:01JS0TX000000000000000000",
  "origin": "did:web:server.a.example",
  "destination": "did:web:server.b.example",
  "service_binding_ref": {
    "space_policy_hash": "sha256:...",
    "membership_frontier": ["cx:evt:..."],
    "destination_service_type": "principal_server"
  },
  "events": [],
  "receipts": [],
  "frontier": {},
  "created_at": "2026-04-26T00:00:00Z"
}
```

`txn_id` MUST be idempotent。

`origin` 与 `destination` MUST 是 service DID。接收方 MUST 验证 `destination` 与请求签名、目标 URL、DID service endpoint、Space policy 和 `service_binding_ref` 一致；不一致时 MUST 拒绝或进入 quarantine。

响应字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `ok` | `boolean` | required | transaction 是否被处理；为 `true` 不表示所有 event 都接受。 |
| `accepted` | `id[]` | required | 已接受 event / operation ID。 |
| `rejected` | `object[]` | required | 被拒绝项；每项 SHOULD 包含 `id`、`reason_code` 和诊断信息。 |
| `next_retry_at` | `datetime` | optional | 可重试时间；仅限限流、临时不可用或待依赖补齐场景。 |

## 4. Cross-Domain Join

Join flow:

1. remote actor requests invite or join.
2. local authz checks Space policy.
3. local service returns join authorization.
4. remote actor submits membership event.
5. federation transaction distributes membership event.
6. if encrypted, MLS Welcome / Commit follows policy.

## 5. Backfill Authorization

Backfill 请求字段：

字段定义同 `GET /api/v1/federation/pull-operations`：`space_id: id` 为 required，`from_cursor/after_cursor: cursor` 与 `limit: int` 为 optional，`requester: did` MUST 与请求签名的来源 service DID 一致。

```json
{
  "space_id": "cx:space:...",
  "from_cursor": "cx:cursor:...",
  "limit": 100,
  "requester": "did:web:server.remote.example"
}
```

Remote service MUST prove it is allowed to receive the requested history. Visibility and capability rules apply to backfill.

Backfill authorization MUST evaluate the requester service DID against the Space policy, membership frontier, service delegation and plaintext visibility rules. If the requested range contains non-E2EE private content, the requester MUST be a participant Principal Server or an explicitly listed `plaintext_visible_services` entry for that range.

## 6. Fork Detection

Services SHOULD exchange frontier:

```json
{
  "space_id": "cx:space:...",
  "heads": ["sha256:..."],
  "max_hlc": "01970e589d21-0004-a13f9c2e",
  "witness_receipts": []
}
```

If two histories contain conflicting commits with same id but different hash, service MUST quarantine and report `duplicate_conflict`。

## 7. Quarantine

Suspicious remote input MAY be stored in quarantine queue until:

- signature verified
- schema verified
- capability verified
- fork resolved
- operator policy accepts source

