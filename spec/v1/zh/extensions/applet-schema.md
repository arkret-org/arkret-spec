---
title: Applet Schema and OpenAPI
---

## 1. Applet Registration Schema

```json
{
  "kind": "cx.applet.registration",
  "applet_id": "cx:applet:dd552c17-0000-7000-8000-000000000000",
  "service_did": "did:web:applet.example",
  "controller_did": "did:web:acme.example",
  "base_url": "https://applet.example/api/v1/applet",
  "bot_actor_id": "did:web:applet.example#bot",
  "protocols": ["slack"],
  "namespaces": {
    "actors": [],
    "spaces": [],
    "handles": []
  },
  "receive_events": true,
  "receive_ephemeral": false,
  "rate_limited": true,
  "requested_scopes": [],
  "proof": {
    "kind": "detached_jws",
    "alg": "EdDSA",
    "verification_method": "did:web:applet.example#controller-key-1",
    "payload_hash": "sha256:<canonical-registration-hash>",
    "created_at": "2026-04-26T00:00:00Z",
    "jws": "<detached-jws-signature>"
  }
}
```

> 示例中 `proof` 字段省略字段不是合法 v1 wire 形态：registration MUST 由 controller DID 签名，
> `proof` 必须包含 [`models/event-and-patch.md §3`](../models/event-and-patch.md) 列出的全部 required
> 字段，且 `payload_hash` 覆盖整个 canonical registration object（不含 `proof` 自身）。
> 空 `"proof": {}` 形态 MUST 被 receiver 以 `schema_violation` 拒绝。

> **`requested_scopes` 是请求声明，不是授权**：该数组只是 Applet 在 registration 时声明它"打算请求的能力范围"，用于 Space owner / human reviewer 审批 UI 展示。registration 接受**不**等于授予；Applet 实际写入 / 读取任何对象都需要独立的 `cx.capability.grant` event 命中具体 action / resource selector / constraint。reducer **MUST NOT** 因为 `requested_scopes` 包含某 action 而隐式 allow 该 action。详见 [`extensions/applet-integration.md` §5](./applet-integration.md)。

## 2. Namespace Pattern

```json
{
  "exclusive": true,
  "pattern": "did:web:applet.example#ghost-*"
}
```

Pattern grammar:

- `*` matches a single suffix segment
- `**` matches multiple path-like segments
- literal `*` MUST be escaped as `\\*`

## 3. Transaction Endpoint

```text
POST /api/v1/applet/transactions
Idempotency-Key: <opaque-string>
```

请求字段：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `Idempotency-Key` | header | `string` | required | 发送方生成的幂等键，长度 1..128；Applet MUST 以 `(source_service_did, Idempotency-Key)` 去重，重复键但 body canonical hash 不同 MUST 返回 `duplicate_conflict`。 |
| `source_service_did` | body | `did` | required | 推送来源 service DID。 |
| `events` | body | `object[]` | required | 推送给 Applet 的事件数组。 |
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
GET /api/v1/applet/actors/{actor_id}
```

响应字段：`exists: boolean` required；`actor_id: did` optional；`display_name: string` optional；`external_ref: object` optional。

响应示例（非完整 schema）：

```json
{
  "exists": true,
  "actor_id": "did:web:applet.example#ghost-u123",
  "display_name": "Alice",
  "external_ref": {}
}
```

## 5. Query Space

```text
GET /api/v1/applet/spaces/{space_id_or_alias}
```

响应字段：`exists: boolean` required；`space_id: id` optional；`title: string` optional；`external_ref: object` optional。

响应示例（非完整 schema）：

```json
{
  "exists": true,
  "space_id": "cx:space:c0c69410-0000-7000-8000-000000000000:slack:T:C",
  "title": "#general",
  "external_ref": {}
}
```

## 6. Protocol Metadata

```text
GET /api/v1/applet/protocols/{protocol}
```

响应字段：`protocol: string` required；`display_name: string` required；`icon_blob: string` optional；`field_types: object` required；`instances: object[]` optional。

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
  "kind": "cx.applet.bridge_error",
  "applet_id": "cx:applet:dd552c17-0000-7000-8000-000000000000",
  "external_ref": {},
  "error_code": "external_rate_limited",
  "message": "external network rejected the message",
  "retry_after_ms": 1000
}
```
