---
title: Applet Schema and Field Reference
status: candidate
normative: true
stability: v1
updated: 2026-05-25
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

> **权威 schema / OpenAPI 来源**：本文是 Applet wire 对象与 HTTP 字段的人类可读参考；它**不**是机器可校验的权威定义。Applet registration / transaction / bridge-error 的权威 JSON Schema 见 `artifacts/schemas/applet.schema.json`，HTTP operation 的权威 OpenAPI 定义见 `artifacts/openapi/cokret-service-api.openapi.yaml`（两者由 artifact pipeline 从 contract catalog 生成）。本文与上述 artifacts 冲突时，**以 artifacts 为准**。

## 1. Applet Registration Schema

```json
{
  "kind": "ck.applet.registration",
  "applet_id": "ck:applet:dd552c17-0000-7000-8000-000000000000",
  "service_did": "did:web:applet.example",
  "controller_did": "did:webvh:z2dmjQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn:acme.example",
  "base_url": "https://applet.example/applet",
  "bot_actor_id": "did:web:applet.example:bot",
  "protocols": ["slack"],
  "namespaces": {
    "actors": [],
    "realms": [],
    "handles": []
  },
  "receive_events": true,
  "receive_ephemeral": false,
  "rate_limited": true,
  "requested_scopes": [],
  "registration_epoch": "sha256:<canonical-registration-epoch-hash>",
  "proof": {
    "kind": "detached_jws",
    "alg": "EdDSA",
    "verification_method": "did:webvh:z2dmjQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn:acme.example#controller-key-1",
    "payload_digest": "sha256:<canonical-registration-hash>",
    "created_at": "2026-04-26T00:00:00Z",
    "jws": "<detached-jws-signature>"
  }
}
```

> 示例中 `proof` 字段省略字段不是合法 v1 wire 形态：registration MUST 由 controller DID 签名，
> `proof` 必须包含 [`models/event-and-patch.md §3`](../models/event-and-patch.md) 列出的全部 required
> 字段，且 `payload_digest` 覆盖整个 canonical registration object（不含 `proof` 自身）。
> 空 `"proof": {}` 形态 MUST 被 receiver 以 `schema_violation` 拒绝。

> **`requested_scopes` 是请求声明，不是授权**：该数组只是 Applet 在 registration 时声明它"打算请求的能力范围"，用于 Realm owner / human reviewer 审批 UI 展示。registration 接受**不**等于授予；Applet 实际写入 / 读取任何对象都需要独立的 `ck.capability.grant` event 命中具体 action / resource selector / constraint。reducer **MUST NOT** 因为 `requested_scopes` 包含某 action 而隐式 allow 该 action。详见 [`extensions/applet-integration.md` §5](./applet-integration.md)。

> **`registration_epoch`（registration epoch hash）**：对该 registration 的 canonical 形态（不含 `proof` 自身）取的稳定 epoch hash，唯一标识本次 registration 的版本。它用于 [`applet-integration.md` §11](./applet-integration.md) 的 delegated-agent grant 绑定：grant constraint MUST 绑定 `registration_epoch`，registration 更新（namespace / endpoint / scope 变化）后该 hash MUST 变化，使旧 grant 不再匹配新 registration epoch，除非 grant 明确声明可接受的 epoch range 并由 reducer 验证。对无版本化 DID method，`registration_epoch` 与 service DID Document 的 fetch-time digest 共同构成 grant 的 epoch 证据；reducer MUST 以二者任一不匹配作为拒绝条件。该字段 required。

## 2. Namespace Pattern

```json
{
  "exclusive": true,
  "pattern": "did:web:applet.example:ghost:*"
}
```

Pattern grammar:

- `*` matches exactly one segment，且 `*` **不跨 segment 分隔符**。
- `**` matches one or more path-like segments，且**仅对 `/` 分隔符**有 path-like 语义（即 `**` 只跨 `/`，不跨 `:`）。
- literal `*` MUST be escaped as `\\*`。

**Segment 分隔符（normative）**：segment 边界由 pattern 所属命名空间决定，匹配前 pattern 与目标字符串按相同分隔符集合切分：

- **Actor namespace（DID pattern）**：分隔符为 `:`。`*` 匹配 DID 中由 `:` 分隔的**单一** segment，MUST NOT 跨越 `:`。例如 `did:web:slack-bridge.example:ghost:*` 匹配 `did:web:slack-bridge.example:ghost:u123`，但 MUST NOT 匹配 `did:web:slack-bridge.example:ghost:team:u123`（后者跨了一个额外 `:` segment）。DID pattern 中 `**` 同样不跨 `:`——DID 没有 path-like `/` 结构，因此 DID pattern MUST NOT 依赖 `**` 的跨段语义。`#fragment` 不参与 namespace 匹配。
- **Realm / portal namespace pattern**：分隔符集合为 `:` 与 `/`。`*` 匹配由 `:` 或 `/` 分隔的单一 segment，不跨任一分隔符；`**` 只对 `/` 分隔的 path-like 尾段生效（匹配一个或多个 `/`-分隔 segment），MUST NOT 跨 `:`。例如 `slack:team:*:channel:*` 匹配 `slack:team:T123:channel:C456`；`slack.acme.example/*` 匹配单层 path，`slack.acme.example/**` 匹配多层 path。
- 任一分隔符集合下，`*` / `**` MUST NOT 匹配空 segment；exclusive namespace 的冲突判定按 [`applet-integration.md` §4.1](./applet-integration.md) 在切分后的 segment 序列上进行。

## 3. Transaction Endpoint

```text
POST /_cokret/edge/applet/transactions
Idempotency-Key: <opaque-string>
```

请求字段：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `Idempotency-Key` | header | `string` | required | 发送方生成的幂等键，长度 1..128；Applet MUST 以 `(source_service_did, Idempotency-Key)` 去重，重复键但 body canonical hash 不同 MUST 返回 `duplicate_conflict`。 |
| `source_service_did` | body | `did` | required | 推送来源 service DID。 |
| `events` | body | `EventEnvelope[]` | required | 推送给 Applet 的 signed Event 数组；每项必须满足 `event-envelope.schema.json`。 |
| `ephemeral` | body | `object[]` | optional | 非持久临时事件数组。 |

请求示例（非完整 schema）：

```json
{
  "source_service_did": "did:web:server.example",
  "events": [],
  "ephemeral": []
}
```

响应字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `ok` | `boolean` | required | transaction 是否被处理。 |
| `rejected` | `object[]` | optional | 被拒绝事件摘要。 |
| `retry_after_ms` | `int` | optional | 建议重试延迟。 |

响应示例：

```json
{ "ok": true }
```

## 4. Query Actor

```text
GET /_cokret/edge/applet/actors/{actor_id}
```

响应字段：`exists: boolean` required；`actor_id: did` optional；`display_name: string` optional；`external_ref: object` optional。

响应示例（非完整 schema）：

```json
{
  "exists": true,
  "actor_id": "did:web:applet.example:ghost:u123",
  "display_name": "Alice",
  "external_ref": {}
}
```

## 5. Query Realm

```text
GET /_cokret/edge/applet/realms/{realm_id_or_alias}
```

响应字段：`exists: boolean` required；`realm_id: id` optional；`title: string` optional；`external_ref: object` optional。

响应示例（非完整 schema）：

```json
{
  "exists": true,
  "realm_id": "ck:realm:c0c69410-0000-7000-8000-000000000000",
  "title": "#general",
  "external_ref": {}
}
```

## 6. Protocol Metadata

```text
GET /_cokret/edge/applet/protocols/{protocol}
```

响应字段：`protocol: string` required；`display_name: string` required；`icon_blob_ref: string` optional；`field_types: object` required；`instances: object[]` optional。

响应示例（非完整 schema）：

```json
{
  "protocol": "slack",
  "display_name": "Slack",
  "field_types": {},
  "instances": []
}
```

## 7. Bridge Error Event

```json
{
  "kind": "ck.applet.bridge_error",
  "applet_id": "ck:applet:dd552c17-0000-7000-8000-000000000000",
  "realm_id": "ck:realm:c0c69410-0000-7000-8000-000000000000",
  "failed_transaction_ref": "ck:event:019640ed-8000-7000-8000-000000000000",
  "external_ref": {},
  "error_code": "external_rate_limited",
  "error_class": "external_network",
  "retriable": true,
  "visibility_scope": "realm_admins",
  "message": "external network rejected the message",
  "retry_after_ms": 1000
}
```

字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `kind` | `string` | required | 固定为 `ck.applet.bridge_error`（wire Event kind，进 Realm history）。 |
| `applet_id` | `id` | required | 产生该错误的 Applet id。 |
| `realm_id` | `id` | required | 该 bridge error 所属 Realm；reducer / 客户端据此做可见范围与授权判定。 |
| `failed_transaction_ref` | `ref` | required | 指向失败的 transaction / 源 Event（如 push 中的 `event_id` 或 transaction idempotency 记录），用于审计回溯。MUST NOT 内联未授权外部正文。 |
| `error_class` | `string` | required | 错误类别枚举（如 `external_network` / `auth` / `schema` / `rate_limit` / `policy`），供聚合与告警。 |
| `error_code` | `string` | required | 具体错误码（如 `external_rate_limited`）。 |
| `retriable` | `boolean` | required | 该错误是否可重试；发送方据此决定是否以相同 `Idempotency-Key` 重试（与 [`applet-integration.md` §14](./applet-integration.md) 重试规则一致）。 |
| `visibility_scope` | `string` | required | 该 error event 的可见范围枚举（如 `realm_admins` / `applet_controller` / `realm_members`）；客户端 MUST 按此限制展示，MUST NOT 把 bridge 内部错误细节暴露给无关成员。 |
| `external_ref` | `object` | optional | 外部网络引用（protocol / network id 等）；MUST NOT 包含未授权外部正文明文。 |
| `message` | `string` | optional | 人类可读摘要；MUST NOT 泄露未授权外部正文。 |
| `retry_after_ms` | `int` | optional | 建议重试延迟，仅当 `retriable=true` 时有意义。 |

`ck.applet.bridge_error` MUST 绑定 `realm_id`、`failed_transaction_ref`、`retriable` 和 `visibility_scope`；缺少任一 required 字段的 bridge error event MUST 被以 `schema_violation` 拒绝。该 event MUST NOT 泄露未授权外部正文（与 [`applet-integration.md` §16](./applet-integration.md) 一致）。
