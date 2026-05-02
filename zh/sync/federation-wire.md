# Federation Wire Protocol

## 1. 目标

本文定义跨域服务间交易、跨域加入、backfill authorization 与 fork detection。

## 2. Service Authentication

每个 federation service MUST 拥有自己的 service DID。请求 MUST 使用 HTTP Message Signatures，并绑定：

- method
- target URI
- authority
- date
- content digest
- source service DID
- destination service DID
- canonical request hash

签名规则：

- `origin` 与 `destination` MUST 出现在签名 transcript 中，且 MUST 与 body 字段一致。
- `destination` MUST 是被请求服务的 service DID，不得只使用 host、SNI、IP 或 URL 作为目的地身份。
- 有 body 的请求 MUST 携带 `Content-Digest`，接收方 MUST 在验签前或验签过程中校验 digest 与 body 一致。
- 签名 SHOULD 带 `created` 与 `expires` 参数；过期、未来时间漂移过大或重复 nonce / request id MUST 拒绝或进入 quarantine。
- 联邦 endpoint MUST NOT 接受 query string 中的认证材料。
- 签名失败、目的地不匹配和请求体 hash 不一致都 MUST 使用标准 error envelope；不得返回非 JSON 框架错误。

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
| `operations` | body | `object[]` | optional | 旧字段名兼容别名；若同时存在，MUST 与 `events` canonical hash 一致，否则拒绝。 |
| `receipts` | body | `object[]` | optional | 与本 transaction 相关的 receipt / witness 证明。 |
| `frontier` | body | `object` | optional | 发送方当前 causal frontier。 |
| `created_at` | body | `datetime` | optional | 发送方创建时间；不得作为授权依据。 |
| `request_canonical_hash` | body | `sha256:<hash>` | optional | 请求 canonical body hash；存在时 MUST 与 `Content-Digest` 和签名 transcript 一致。 |

请求示例（非完整 schema）：

```json
{
  "txn_id": "cx:txn:01js0tx0000000000000000000",
  "origin": "did:web:server.a.example",
  "destination": "did:web:server.b.example",
  "service_binding_ref": {
    "space_policy_hash": "sha256:...",
    "membership_frontier": ["cx:event:..."],
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

重放与幂等规则：

- 接收方 MUST 以 `(origin, destination, txn_id)` 作为 transaction 幂等键。
- 同一幂等键 + 相同 canonical request hash MUST 返回语义等价响应。
- 同一幂等键 + 不同 canonical request hash MUST 返回 `duplicate_conflict`。
- 已过期签名、重复 nonce、高频失败或来源行为异常 MAY 进入 `quarantine`，但不得把隔离队列成功写入当作 Event 已接受。
- 单条 Event 的接受条件仍是 Actor 签名、schema、capability、Space policy、服务委托和因果依赖全部通过；transaction 签名只证明传输来源。

`events[]` MUST 按数组顺序处理。接收方在验证第 N 项时，可以把本 transaction 中前 N-1 项已经进入 `accepted[]` 的 Event 作为可解析依赖；不得把后续项、已拒绝项或 quarantine 项当作已接受事实。部分失败不回滚已接受项；依赖同批失败或缺失 Event 的后续项 MUST 进入 `rejected[]` 或 quarantine，并给出 `dependency_missing`、`causal_conflict` 或等价 `reason_code`。

响应字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `ok` | `boolean` | required | transaction 是否被处理；为 `true` 不表示所有 Event 都接受。 |
| `accepted` | `id[]` | required | 已接受 event ID。 |
| `rejected` | `object[]` | required | 被拒绝项；每项 SHOULD 包含 `id`、`reason_code` 和诊断信息。 |
| `next_retry_at` | `datetime` | optional | 可重试时间；仅限限流、临时不可用或待依赖补齐场景。 |

错误响应 MUST 使用 `api-conventions.md` 中的标准 error envelope。联邦 endpoint 不得使用数组包装响应，也不得用 HTTP `200` 包装失败业务结果。

建议的 `reason_code`：

| `reason_code` | 含义 |
| --- | --- |
| `invalid_signature` | service 或 Actor 签名无效。 |
| `destination_mismatch` | `destination` 与签名、URL、DID service endpoint 或 policy binding 不一致。 |
| `duplicate_conflict` | 相同 transaction / event id 对应不同内容。 |
| `dependency_missing` | 缺少因果依赖，可通过 backfill 或 snapshot bootstrap 恢复。 |
| `capability_denied` | Actor、service 或 Space policy 不允许。 |
| `schema_violation` | Event 或 transaction schema 不合法。 |
| `temporarily_unavailable` | 依赖、frontier 或本地队列暂不可用。 |
| `rate_limited` | 来源被限流；响应 SHOULD 携带 `Retry-After`。 |

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

字段定义同 `GET /api/v1/federation/pull-operations`：`space_id: id` 为 required，`after_cursor: cursor` 与 `limit: int` 为 optional，`requester: did` MUST 与请求签名的来源 service DID 一致。

```json
{
  "space_id": "cx:space:...",
  "after_cursor": "cx:cursor:...",
  "limit": 100,
  "requester": "did:web:server.remote.example"
}
```

远端 service MUST 证明自己有权接收请求的历史范围。Backfill 必须执行 visibility 与 capability 检查。

Backfill 授权 MUST 基于 Space policy、membership frontier、service delegation 与 plaintext visibility rules 校验 requester service DID。若请求范围包含非 E2EE 私有内容，请求方 MUST 是参与方 Principal Server，或在该范围内被显式列入 `plaintext_visible_services`。

Backfill response MUST preserve the original signed Event Envelope. 服务端不得在 backfill 中重写 Actor 签名、伪造发送者、替换时间戳或把不可见明文降级为 stripped preview，除非 Space policy 明确允许该 preview 类型。

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

If two histories contain conflicting Events with same id but different hash, service MUST quarantine and report `duplicate_conflict`。

如果冲突来自同一 Actor 的不同签名 Event frontier，接收方 SHOULD 保留最小证据集：冲突 event id、hash、签名 key id、source service DID、收到时间和相关 frontier。证据集不得包含未授权明文 payload。

## 7. Quarantine

Suspicious remote input MAY be stored in quarantine queue until:

- signature verified
- schema verified
- capability verified
- fork resolved
- operator policy accepts source
