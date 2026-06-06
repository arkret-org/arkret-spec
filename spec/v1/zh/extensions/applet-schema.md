---
title: Applet Schema and Field Reference
status: candidate
normative: true
stability: v1
updated: 2026-06-04
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
  "webhook_auth": {
    "type": "http_message_signature",
    "key_ref": "did:web:applet.example#server-key-1"
  },
  "proof": {
    "kind": "detached_jws",
    "alg": "EdDSA",
    "verification_method": "did:webvh:z2dmjQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn:acme.example#controller-key-1",
    "payload_digest": "sha256:<canonical-registration-hash>",
    "created_at": "2026-04-26T00:00:00Z",
    "jws": "<detached-jws-signature>"
  },
  "created_at": "2026-04-26T00:00:00Z"
}
```

> 示例中 `proof` 字段省略字段不是合法 v1 wire 形态：registration MUST 由 controller DID 签名，
> `proof` 必须包含 [`models/event-and-patch.md §3`](../models/event-and-patch.md) 列出的全部 required
> 字段，且 `payload_digest` 覆盖整个 canonical registration object（不含 `proof` 自身）。
> 空 `"proof": {}` 形态 MUST 被 receiver 以 `schema_violation` 拒绝。

> **`requested_scopes` 是请求声明，不是授权**：该数组只是 Applet 在 registration 时声明它"打算请求的能力范围"，用于 Realm owner / human reviewer 审批 UI 展示。registration 接受**不**等于授予；Applet 实际写入 / 读取任何对象都需要独立的 `ck.capability.grant` event 命中具体 action / resource selector / constraint。reducer **MUST NOT** 因为 `requested_scopes` 包含某 action 而隐式 allow 该 action。详见 [`extensions/applet-integration.md` §11](./applet-integration.md)（末段）与 §4.1。

> **`registration_epoch`（registration epoch hash）**：对该 registration 的 canonical security evidence（不含 `proof` 自身）取的稳定 epoch hash，唯一标识本次 registration 的安全版本。它用于 [`applet-integration.md` §11](./applet-integration.md) 的 delegated-agent grant 绑定：grant constraint MUST 绑定 `registration_epoch`。该 epoch 的 canonical 输入 MUST 包含 derived registration object、service DID Document digest/version evidence、accepted signing key set、endpoint/auth material、bot actor/base URL 等安全相关字段。grant 存储与匹配只绑定该 epoch；reducer/verifier 仍 MUST 展开 epoch evidence，重新解析或按 method-specific version evidence 读取 service DID Document，并确认当前 DID Document digest、accepted signing key set 与 epoch 捕获值一致。无版本化 `did:web` MUST re-fetch canonical document 并比对 digest。该字段 required。

`applet_registration_payload.required` 的顺序 MUST 与 schema properties 字段出现顺序一致:

```json
[
  "applet_id",
  "service_did",
  "controller_did",
  "base_url",
  "bot_actor_id",
  "protocols",
  "namespaces",
  "receive_events",
  "receive_ephemeral",
  "rate_limited",
  "requested_scopes",
  "registration_epoch",
  "webhook_auth",
  "proof",
  "created_at"
]
```

该 registration payload 的权威机读 schema 是 [`schemas/event-payload.schema.json` 的 `$defs/applet_registration_payload`](../../artifacts/schemas/event-payload.schema.json)(`applet.schema.json` 仅描述 applet object metadata snapshot,不含本 registration payload)。上述顺序 MUST 与该 `$defs/applet_registration_payload` 的 `properties` 出现顺序一致，可据此链接核验。

## 1a. Applet Package Schema

`ck.schema.applet_package.v1` 是开发者/供应商发布的可安装 package；它不进入 Realm history，不授权写入。安装时 Principal Server / authz service MUST 从 package 派生 canonical `ck.applet.registration` payload，再根据管理员批准生成 grant。

字段参考:

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `schema` | yes | 固定 `ck.schema.applet_package.v1`。 |
| `package_id` | yes | typed id 或 DID URL；仅用于 package 分发。 |
| `applet_id` | yes | DID 或 `ck:applet:<uuidv7>`。 |
| `service_did` | yes | Applet runtime DID。 |
| `controller_did` | yes | 对 package / registration 负责的 controller DID。 |
| `base_url` | yes | Applet API base URL。 |
| `bot_actor_id` | yes | 可见 bot actor DID；不得含 `#fragment`。 |
| `claimed_profiles` | yes | v1 Applet profile id 数组；MUST 至少包含 `ck.profile.applet_service.v1`。 |
| `protocols` | yes | 外部协议标识数组。 |
| `namespaces` | yes | `actors` / `realms` / `handles` 对象形态 namespace。 |
| `requested_scopes` | yes | capability action 请求列表；只用于审批 UI。 |
| `endpoint_set` | yes | 实际支持的 Applet API endpoint 与 auth requirement。 |
| `webhook_auth` | yes | HTTP message signature key ref / accepted algorithms。 |
| `receive_events` | yes | 派生 registration 的接收事件声明。 |
| `receive_ephemeral` | yes | 派生 registration 的 ephemeral 接收声明。 |
| `rate_limited` | yes | 派生 registration 的服务端限流声明。 |
| `limits` | yes | max transaction events、payload bytes、rate limit hint。 |
| `ghost_policy` | yes | Ghost Actor 支持与 accountability 模板。 |
| `delegation_policy` | yes | delegated native-user acting 请求；默认 false。 |
| `e2ee_policy` | yes | MLS join 请求；默认 false。 |
| `widget` | optional | widget origin / CSP / token scope / consent。 |
| `package_digest` | yes | canonical package hash。 |
| `registration_epoch` | yes | canonical security epoch hash。 |
| `created_at` | yes | package 创建时间。 |
| `expires_at` | optional | package 可安装截止时间。 |
| `proof` | yes | controller DID detached proof。 |

Package -> registration 派生映射:

| `ck.applet.registration` 字段 | Package 来源 | 规则 |
| --- | --- | --- |
| `applet_id` | `applet_id` | 原样复制；只接受 DID 或 `ck:applet:<uuidv7>`。 |
| `service_did` | `service_did` | 原样复制；必须可解析并绑定 Applet endpoint。 |
| `controller_did` | `controller_did` | 原样复制；必须验证 controller proof。 |
| `base_url` | `base_url` | 原样复制；必须与 service DID Document binding 一致。 |
| `bot_actor_id` | `bot_actor_id` | 原样复制；不得含 `#fragment`。 |
| `protocols` | `protocols` | 原样复制；空数组非法。 |
| `namespaces` | `namespaces` | canonicalize 后复制；只接受对象形态。 |
| `receive_events` | `receive_events` | 原样复制；不得从 `endpoint_set` 猜测默认值。 |
| `receive_ephemeral` | `receive_ephemeral` | 原样复制；不得省略。 |
| `rate_limited` | `rate_limited` | 原样复制；不得省略。 |
| `requested_scopes` | `requested_scopes` | 原样复制；仍只是请求声明。 |
| `registration_epoch` | `registration_epoch` | 由 canonical derived registration + DID/key/endpoint/auth evidence 计算。 |
| `webhook_auth` | `webhook_auth` | 原样复制；必须覆盖 transaction push signature 验证锚点。 |
| `manifest` | `claimed_profiles` + `limits` + policies + optional widget | 作为 snapshot 放入 manifest，但不得替代顶层 required 字段。 |
| `proof` | `proof` | detached proof 覆盖 canonical package 或 derived registration object。 |
| `created_at` | `created_at` | 原样复制。 |

## 1b. Applet Install Operation Objects

Install preview request:

```json
{
  "applet_package": {},
  "effective_scope": {
    "kind": "realm",
    "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000"
  },
  "approval_request": {
    "approve_actions": ["ck.message.create"],
    "allow_ghost_actors": false,
    "allow_delegated_native_actors": false,
    "allow_e2ee_join": false,
    "allow_widget": false
  }
}
```

`InstallPlan` 的机器契约是 [`schemas/applet-install-plan.schema.json`](../../artifacts/schemas/applet-install-plan.schema.json)。它 MUST include `schema="ck.schema.applet_install_plan.v1"`、`plan_id`、`applet_id`、`package_digest`、`registration_epoch`、`effective_scope`、`requested_scopes`、`approved_scopes`、`denied_scopes`、`events_to_submit`、`capability_constraints`、`namespace_conflicts`、`e2ee_effect`、`widget_effect`、`warnings`、`plan_digest`。`plan_digest` 的 canonical input 是按 [`encoding.md`](../conformance/encoding.md) canonical JSON 编码的 InstallPlan object，且在计算输入中省略 `plan_digest` 字段本身。

Install commit request:

```json
{
  "plan_digest": "sha256:<install-plan-hash>",
  "applet_package": {},
  "effective_scope": {
    "kind": "realm",
    "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000"
  },
  "approved_scopes": [
    {
      "actions": ["ck.message.create"],
      "realm_ids": ["ck:realm:0196419b-0000-7000-8000-000000000000"],
      "constraints": []
    }
  ],
  "actor_policy": {
    "bot_membership": "invite",
    "ghost_actor_mode": "disallowed"
  },
  "e2ee_policy": {
    "allow_mls_join": false
  },
  "widget_policy": {
    "allow_widget": false
  }
}
```

Commit response MUST validate [`schemas/applet-install-operations.schema.json#/$defs/applet_install_outcome`](../../artifacts/schemas/applet-install-operations.schema.json) and include `ok`、`install_id`、`applet_id`、`registration_event_ref`、`registration_epoch`、`bot_actor_id`、`capability_grant_refs`、`membership_event_refs`、`e2ee_authorization_refs`、`widget_policy_ref`、`effective_status`、`rejected`。

`effective_scope.kind="realm"` MUST only contain `kind` and `realm_id`。`effective_scope.kind="circle"` MUST contain `kind`、`realm_id` and `circle_id`。单次 install operation MUST only target one effective_scope。recomputed plan `plan_digest` 不等于提交的 `plan_digest` 时 MUST fail closed，reason=`applet_install_plan_mismatch`。

**preview `allow_ghost_actors` 与 commit `actor_policy.ghost_actor_mode` 一致性(normative)**:preview 的 `approval_request.allow_ghost_actors`(布尔)与 commit `actor_policy.ghost_actor_mode`(三值 `disallowed` / `controller_approved` / `policy_declared`)表达同一 ghost actor 准入意图,commit 时二者 MUST 语义一致，不一致 MUST fail closed:

- `allow_ghost_actors=false` ↔ `ghost_actor_mode="disallowed"`;
- `allow_ghost_actors=true` ↔ `ghost_actor_mode ∈ {controller_approved, policy_declared}`。

即 `allow_ghost_actors=false` 与 `ghost_actor_mode ∈ {controller_approved, policy_declared}` 冲突,`allow_ghost_actors=true` 与 `ghost_actor_mode="disallowed"` 冲突；任一冲突组合 MUST 被 commit 拒绝(fail closed,reason=`applet_install_plan_mismatch` 或更细 ghost-policy reason),不得静默取其一。

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

> **HTTP signature 与 `received_at`(normative)**:[`applet-integration.md` §16](./applet-integration.md) 把 HTTP message signature 与 `received_at` audit metadata 列为 transaction push 的 MUST。它们由 transport 层承载(HTTP `Signature` / `Signature-Input` header 与 receiving service 记录的 audit metadata),**不进入** 上表的 transaction body,因此不列为 body 字段;receiver MUST 校验 HTTP message signature 并记录 `received_at`,缺失任一者 MUST 拒绝。

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
  "error_class": "external_network",
  "error_code": "external_rate_limited",
  "retriable": true,
  "visibility_scope": "realm_admins",
  "external_ref": {},
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
| `error_class` | `string`（封闭枚举） | required | 错误类别封闭枚举，取值 **MUST** 属于 `external_network` / `auth` / `schema` / `rate_limit` / `policy`(供聚合与告警)。`error_class` 是粗粒度类别，具体错误码由 `error_code` 承载(例如 `error_class="rate_limit"` 配 `error_code="external_rate_limited"`);二者不得混用。`rate_limit` 是该枚举的 canonical 类别名,[`applet-integration.md` §14](./applet-integration.md) 的重试语境用 `rate_limited` 指同一类错误状态。该枚举的机读 enum 权威源为 [`schemas/event-payload.schema.json`](../../artifacts/schemas/event-payload.schema.json) 的 `ck.applet.bridge_error` payload。 |
| `error_code` | `string` | required | 具体错误码（如 `external_rate_limited`）。 |
| `retriable` | `boolean` | required | 该错误是否可重试；发送方据此决定是否以相同 `Idempotency-Key` 重试（与 [`applet-integration.md` §14](./applet-integration.md) 重试规则一致）。 |
| `visibility_scope` | `string` | required | 该 error event 的可见范围枚举（如 `realm_admins` / `applet_controller` / `realm_members`）；客户端 MUST 按此限制展示，MUST NOT 把 bridge 内部错误细节暴露给无关成员。 |
| `external_ref` | `object` | optional | 外部网络引用（protocol / network id 等）；MUST NOT 包含未授权外部正文明文。 |
| `message` | `string` | optional | 人类可读摘要；MUST NOT 泄露未授权外部正文。 |
| `retry_after_ms` | `int` | optional | 建议重试延迟，仅当 `retriable=true` 时有意义。 |

`ck.applet.bridge_error` MUST 绑定 `realm_id`、`failed_transaction_ref`、`retriable` 和 `visibility_scope`；缺少任一 required 字段的 bridge error event MUST 被以 `schema_violation` 拒绝。该 event MUST NOT 泄露未授权外部正文（与 [`applet-integration.md` §16](./applet-integration.md) 一致）。
