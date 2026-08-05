---
title: Applet Schema and Field Reference
status: candidate
normative: true
stability: v1
updated: 2026-07-02
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

> **权威 schema / OpenAPI 来源**：本文是 Applet wire 对象与 HTTP 字段的人类可读参考；它**不**是机器可校验的权威定义。Applet registration / transaction / bridge-error 的权威 JSON Schema 见 `artifacts/schemas/applet.schema.json`，HTTP operation 的权威 OpenAPI 定义见 `artifacts/openapi/arkret-service-api.openapi.yaml`（两者由 artifact pipeline 从 contract registry 生成）。本文与上述 artifacts 冲突时，**以 artifacts 为准**。

## 1. Applet Registration Schema

```json
{
  "kind": "ak.applet.registration",
  "applet_id": "ak:applet:dd552c17-0000-7000-8000-000000000000",
  "service_id": "did:webvh:z5ApPLeTnL4rP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z:applet.example",
  "controller_id": "did:webvh:z2dmjQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn:acme.example",
  "base_url": "https://applet.example/applet",
  "bot_actor_id": "did:webvh:z5ApPLeTnL4rP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z:applet.example:bot",
  "claimed_profiles": [
    "ak.profile.applet_service.v1",
    "ak.profile.applet_bridge.v1"
  ],
  "protocols": [
    "slack"
  ],
  "namespaces": {
    "actors": [],
    "realms": [],
    "handles": []
  },
  "receive_events": true,
  "receive_signals": false,
  "rate_limited": true,
  "requested_scopes": [],
  "registration_epoch": "sha256:<canonical-registration-epoch-hash>",
  "webhook_auth": {
    "kind": "http_message_signature",
    "key_ref": "did:webvh:z5ApPLeTnL4rP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z:applet.example#server-key-1",
    "accepted_signature_algorithms": [
      "ed25519"
    ]
  },
  "proof": {
    "kind": "detached_jws",
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

> **`requested_scopes` 是请求声明，不是授权**：该数组只是 Applet 在 registration 时声明它"打算请求的能力范围"，用于 Realm owner / human reviewer 审批 UI 展示。registration 接受**不**等于授予；Applet 实际写入 / 读取任何对象都需要独立的 `ak.capability.grant` event 命中具体 action / resource selector / constraint。reducer **MUST NOT** 因为 `requested_scopes` 包含某 action 而隐式 allow 该 action。详见 [`extensions/applet-integration.md` §11](./applet-integration.md)（末段）与 §4.1。

> **`claimed_profiles` 是 durable profile binding**：安装方 MUST 从已验证 Applet Package
> 原样复制 canonical profile-id 集合，且至少包含 `ak.profile.applet_service.v1`。它不是
> capability；但 profile-bound grant authority rule 只能读取已 accepted registration Event
> 中的该字段，不能读取带外 package cache、preview DTO 或 registry 响应。

> **`registration_epoch`（registration epoch hash）**：对该 registration 的 canonical security transcript（不含 `proof` 与 `registration_epoch` 自身）取的稳定 epoch hash，唯一标识本次 registration 的安全版本。它用于 [`applet-integration.md` §11](./applet-integration.md) 的 delegated-agent grant 绑定：grant constraint MUST 绑定 `registration_epoch`。transcript MUST 通过 [`ak.schema.applet_registration_epoch_transcript.v1`](../../artifacts/schemas/applet-registration-epoch-transcript.schema.json) 校验，并按下方 §1.0.1 的唯一算法计算。registration 首次接受、renew / key 变更、binding invalidation 或 authority freshness 到期时，verifier MUST 展开 transcript evidence，解析或按 method-specific version evidence 读取 service DID Document，并确认 DID Document digest、accepted signing key set 与 epoch 捕获值一致；无版本化 `did:web` 在这些触发点 MUST re-fetch canonical document 并比对 digest。普通 grant 存储、匹配与 reducer replay 只绑定已接受的该 epoch，不得逐次 re-fetch。该字段 required。

### 1.0.1 `registration_epoch` transcript 与计算算法（normative）

唯一 canonical transcript 是 `ak.schema.applet_registration_epoch_transcript.v1` 的 closed object，顶层字段依次为：`schema`、`derived_registration`、`service_did_document`、`accepted_signing_keys`、`endpoint_policy`、`webhook_auth`、`security_policy`。不得加入 package id、package digest、proof、registration epoch 自身或实现私有缓存字段。

- `derived_registration` MUST 固定包含 schema 所列的 registration 安全字段；`proof`、`registration_epoch` 与派生 `manifest` 不进入该对象。manifest 的安全含义必须展开到 `endpoint_policy`、`webhook_auth` 与 `security_policy`，不得通过嵌套 opaque manifest 间接参与 hash。
- `service_did_document` MUST 包含 `service_id`、canonical DID Document 的 `document_digest` 与 closed `method_version`。有稳定版本证据的 DID method MUST 令 `unversioned_refetch=false`，并至少给出 `version_id` 或 `version_time`；没有稳定版本证据的 method MUST 令 `unversioned_refetch=true`，且 MUST 省略 `version_id` / `version_time`。后者只在 registration epoch 首次接受 / 续期、binding invalidation 或该授权面的显式 authority freshness 到期时重新解析 canonical document并比对 `document_digest`；同一 accepted epoch 下的普通授权匹配复用其固定 document digest 与 key binding。
- 以下数组是数学集合，producer MUST 先按 UTF-8 字节序升序排列并拒绝重复项：`protocols`、`requested_scopes`、`claimed_profiles`、`webhook_auth.accepted_signature_algorithms`、`accepted_signing_keys`（按 `key_ref`）、三个 namespace bucket（按 `pattern`，相同 pattern 再按 `exclusive=false` 在前）、`endpoint_policy.endpoints`（按 `method`、`path`、`auth` 的 tuple）。同一排序键重复 MUST fail closed，不能靠“保留第一项”消歧。
- 任意 optional 字段缺失时 MUST 直接省略；不得以 JSON `null` 代替。对象成员顺序最终由 JCS 处理；上述数组排序在 JCS 之前完成。
- transcript 通过 schema 与集合规范化校验后，令 `canonical_bytes = JCS(transcript)`；令域分离字节为 UTF-8 `arkret-applet-registration-epoch-v1\n`（末尾单个 LF，字节 `0a`）；最终值为 `registration_epoch = "sha256:" + lowercase_hex(SHA-256(domain_separator || canonical_bytes))`。

[`applet-registration-epoch-fixture.json`](../../artifacts/fixtures/applet-registration-epoch-fixture.json) 给出 transcript、完整 canonical bytes、expected digest 以及排序重复、null、DID version 分支和安全字段变更的负向向量。实现 MUST 执行这些向量，不得只检查 fixture 文件存在。

`applet_registration_payload.required` 的顺序 MUST 与 schema properties 字段出现顺序一致:

```json
[
  "applet_id",
  "service_id",
  "controller_id",
  "base_url",
  "bot_actor_id",
  "claimed_profiles",
  "protocols",
  "namespaces",
  "receive_events",
  "receive_signals",
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

`ak.schema.applet_package.v1` 是开发者/供应商发布的可安装 package；它不进入 Realm history，不授权写入。安装时 Principal Server / authz service MUST 从 package 派生 canonical `ak.applet.registration` payload，再根据管理员批准生成 grant。

字段参考:

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `schema` | yes | 固定 `ak.schema.applet_package.v1`。 |
| `package_id` | yes | typed id 或 DID URL；仅用于 package 分发。 |
| `applet_id` | yes | DID 或 `ak:applet:<uuidv7>`。 |
| `service_id` | yes | Applet runtime DID。 |
| `controller_id` | yes | 对 package / registration 负责的 controller DID。 |
| `base_url` | yes | Applet API base URL。 |
| `bot_actor_id` | yes | 可见 bot actor DID；不得含 `#fragment`。 |
| `claimed_profiles` | yes | v1 Applet profile id 数组；MUST 至少包含 `ak.profile.applet_service.v1`。 |
| `protocols` | yes | 外部协议标识数组。 |
| `namespaces` | yes | `actors` / `realms` / `handles` 对象形态 namespace。 |
| `requested_scopes` | yes | capability action 请求列表；只用于审批 UI。 |
| `endpoint_policy` | yes | 实际支持的 Applet API endpoint 与 auth requirement。 |
| `webhook_auth` | yes | HTTP message signature key ref / accepted algorithms；`key_ref` MUST 是 Applet `service_id` 下的 DID URL，并作为 app/bridge→arkret inbound transaction push 的来源签名锚点。 |
| `receive_events` | yes | 派生 registration 的接收事件声明。 |
| `receive_signals` | yes | 派生 registration 的 encrypted Signal Extension 接收声明。 |
| `rate_limited` | yes | 派生 registration 的服务端限流声明。 |
| `limits` | yes | max transaction events、payload bytes、rate limit hint。 |
| `ghost_policy` | yes | Ghost Actor 支持与 accountability 模板。 |
| `delegation_policy` | yes | delegated native-user acting 请求；默认 false。 |
| `e2ee_policy` | yes | MLS join 请求；默认 false。 |
| `widget` | optional | Applet UI widget declaration；若存在，MUST 通过 `ak.schema.applet_widget_declaration.v1`（[`applet-widget-declaration.schema.json`](../../artifacts/schemas/applet-widget-declaration.schema.json)）校验。 |
| `package_digest` | yes | canonical package hash。 |
| `registration_epoch` | yes | canonical security epoch hash。 |
| `created_at` | yes | package 创建时间。 |
| `expires_at` | optional | package 可安装截止时间。 |
| `proof` | yes | controller DID detached proof。 |

Package -> registration 派生映射:

| `ak.applet.registration` 字段 | Package 来源 | 规则 |
| --- | --- | --- |
| `applet_id` | `applet_id` | 原样复制；只接受 DID 或 `ak:applet:<uuidv7>`。 |
| `service_id` | `service_id` | 原样复制；必须可解析并绑定 Applet endpoint。 |
| `controller_id` | `controller_id` | 原样复制；必须验证 controller proof。 |
| `base_url` | `base_url` | 原样复制；必须与 service DID Document binding 一致。 |
| `bot_actor_id` | `bot_actor_id` | 原样复制；不得含 `#fragment`。 |
| `protocols` | `protocols` | 原样复制；空数组非法。 |
| `namespaces` | `namespaces` | canonicalize 后复制；只接受对象形态。 |
| `receive_events` | `receive_events` | 原样复制；不得从 `endpoint_policy` 猜测默认值。 |
| `receive_signals` | `receive_signals` | 原样复制；不得省略。 |
| `rate_limited` | `rate_limited` | 原样复制；不得省略。 |
| `requested_scopes` | `requested_scopes` | 原样复制；仍只是请求声明。 |
| `registration_epoch` | `registration_epoch` | 由 canonical derived registration + DID/key/endpoint/auth evidence 计算。 |
| `webhook_auth` | `webhook_auth` | 原样复制；必须覆盖 transaction push signature 验证锚点。`key_ref` MUST 归属于 `service_id`，绑定当前 `registration_epoch`；key rotate 后必须通过新的 effective registration / install 生效，旧 key 不得继续放行 inbound push。 |
| `manifest` | `claimed_profiles` + `limits` + policies + optional widget declaration | 作为 snapshot 放入 manifest，但不得替代顶层 required 字段；widget snapshot MUST 保持 `ak.schema.applet_widget_declaration.v1` 的闭合形态。 |
| `proof` | `proof` | detached proof 覆盖 canonical package 或 derived registration object。 |
| `created_at` | `created_at` | 原样复制。 |

Widget declaration 的字段顺序与 schema 一致：`schema`、`widget_origin`、`csp`、`token_scope`、`consent_required`。`token_scope` 是对象而非字符串数组，至少包含 `actions[]`、`resources[]` 与 `expires_at`；host / node 签发给 widget 的短期 token MUST 是该 scope 的子集，不能回退到用户 full session 权限。

## 1b. Applet Install Operation Objects

Install preview request:

```json
{
  "applet_package": {},
  "effective_scope": {
    "kind": "realm",
    "realm_id": "ak:realm:0196419b-0000-8000-8000-000000000000"
  },
  "approval_request": {
    "approve_actions": ["ak.message.create"],
    "ghost_actors_allowed": false,
    "delegated_native_actors_allowed": false,
    "e2ee_join_allowed": false,
    "widget_allowed": false
  }
}
```

`InstallPlan` 的机器契约是 [`schemas/applet-install-plan.schema.json`](../../artifacts/schemas/applet-install-plan.schema.json)。它 MUST 包含 `schema="ak.schema.applet_install_plan.v1"`、`plan_id`、`applet_id`、`package_digest`、`registration_epoch`、`effective_scope`、`requested_scopes`、`approved_scopes`、`denied_scopes`、`events_to_submit`、`capability_constraints`、`namespace_conflicts`、`e2ee_effect`、`widget_effect`、`warnings`、`plan_digest`。`plan_digest` 的 canonical input 是按 [`encoding.md`](../conformance/encoding.md) canonical JSON 编码的 InstallPlan object，且在计算输入中省略 `plan_digest` 字段本身。

Install commit request:

```json
{
  "plan_digest": "sha256:<install-plan-hash>",
  "applet_package": {},
  "effective_scope": {
    "kind": "realm",
    "realm_id": "ak:realm:0196419b-0000-8000-8000-000000000000"
  },
  "registration_event": {
    "kind": "ak.applet.registration",
    "actor_id": "did:webvh:z6MkAdmin:acme.example",
    "payload": {},
    "proofs": []
  },
  "capability_grant_events": [
    {
      "kind": "ak.capability.grant",
      "actor_id": "did:webvh:z6MkAdmin:acme.example",
      "payload": {
        "grant_id": "ak:grant:0196419b-0000-7000-8000-000000000001",
        "grant": {}
      },
      "proofs": []
    }
  ],
  "actor_policy": {
    "bot_membership": "invite",
    "ghost_actor_mode": "disallowed"
  },
  "e2ee_policy": {
    "mls_join_allowed": false
  },
  "widget_policy": {
    "widget_allowed": false
  }
}
```

上例只展示字段归属；`registration_event` 与 `capability_grant_events[]` 的省略字段和空
`proofs`/`grant` 在真实请求中不合法。真实值 MUST 是通过 Event、payload 与 capability
schema 的完整 admin-caller-signed formal Event，服务端不得代签或重建。

Commit 响应 MUST 通过 [`schemas/applet-install-operations.schema.json#/$defs/applet_install_outcome`](../../artifacts/schemas/applet-install-operations.schema.json) 校验，并包含 `ok`、`install_id`、`applet_id`、`registration_event_ref`、`registration_epoch`、`bot_actor_id`、`capability_grant_refs`、`membership_event_refs`、`e2ee_authorization_refs`、`widget_policy_ref`、`effective_status`、`rejected`。

`effective_scope.kind="realm"` MUST 只包含 `kind` 与 `realm_id`。`effective_scope.kind="circle"` MUST 包含 `kind`、`realm_id` 与 `circle_id`。单次 install operation MUST 只作用于一个 effective_scope。recomputed plan `plan_digest` 不等于提交的 `plan_digest` 时 MUST fail closed，reason=`applet_install_plan_mismatch`。

**preview `ghost_actors_allowed` 与 commit `actor_policy.ghost_actor_mode` 一致性(normative)**:preview 的 `approval_request.ghost_actors_allowed`(布尔)与 commit `actor_policy.ghost_actor_mode`(三值 `disallowed` / `controller_approved` / `policy_declared`)表达同一 ghost actor 准入意图,commit 时二者 MUST 语义一致，不一致 MUST fail closed:

- `ghost_actors_allowed=false` ↔ `ghost_actor_mode="disallowed"`;
- `ghost_actors_allowed=true` ↔ `ghost_actor_mode ∈ {controller_approved, policy_declared}`。

即 `ghost_actors_allowed=false` 与 `ghost_actor_mode ∈ {controller_approved, policy_declared}` 冲突,`ghost_actors_allowed=true` 与 `ghost_actor_mode="disallowed"` 冲突；任一冲突组合 MUST 被 commit 拒绝(fail closed,reason=`applet_install_plan_mismatch` 或更细 ghost-policy reason),不得静默取其一。

## 2. Namespace Pattern

```json
{
  "exclusive": true,
  "pattern": "did:webvh:z5ApPLeTnL4rP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z:applet.example:ghost:*"
}
```

Pattern 语法：

- `*` 匹配恰好一个 segment，且 `*` **不跨 segment 分隔符**。
- `**` 匹配一个或多个 path-like segment，且**仅对 `/` 分隔符**有 path-like 语义（即 `**` 只跨 `/`，不跨 `:`）。
- 字面量 `*` MUST 转义为 `\\*`。

**Segment 分隔符（normative）**：segment 边界由 pattern 所属命名空间决定，匹配前 pattern 与目标字符串按相同分隔符集合切分：

- **Actor namespace（DID pattern）**：分隔符为 `:`。`*` 匹配 DID 中由 `:` 分隔的**单一** segment，MUST NOT 跨越 `:`。例如 `did:webvh:z6Mkw8qTnL4rP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z:slack-bridge.example:ghost:*` 匹配 `did:webvh:z6Mkw8qTnL4rP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z:slack-bridge.example:ghost:u123`，但 MUST NOT 匹配 `did:webvh:z6Mkw8qTnL4rP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z:slack-bridge.example:ghost:team:u123`（后者跨了一个额外 `:` segment）。DID pattern 中 `**` 同样不跨 `:`——DID 没有 path-like `/` 结构，因此 DID pattern MUST NOT 依赖 `**` 的跨段语义。`#fragment` 不参与 namespace 匹配。
- **Realm / portal namespace pattern**：分隔符集合为 `:` 与 `/`。`*` 匹配由 `:` 或 `/` 分隔的单一 segment，不跨任一分隔符；`**` 只对 `/` 分隔的 path-like 尾段生效（匹配一个或多个 `/`-分隔 segment），MUST NOT 跨 `:`。例如 `slack:team:*:channel:*` 匹配 `slack:team:T123:channel:C456`；`slack.acme.example/*` 匹配单层 path，`slack.acme.example/**` 匹配多层 path。
- 任一分隔符集合下，`*` / `**` MUST NOT 匹配空 segment；exclusive namespace 的冲突判定按 [`applet-integration.md` §4.1](./applet-integration.md) 在切分后的 segment 序列上进行。

## 3. Transaction Endpoint

```text
POST /_arkret/edge/applet/transactions
Idempotency-Key: <opaque-string>
```

请求字段：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `Idempotency-Key` | header | `string` | required | 发送方生成的幂等 / nonce 键，长度 1..128；接收方 MUST 以 `(operation_id, direction, Source-Service-ID, Destination-Service-ID, Idempotency-Key)` 定位幂等记录，并绑定 canonical body digest 与 `source_signature_anchor`；重复键但 body digest 或签名锚点不同 MUST fail closed。 |
| `Source-Service-ID` | header | `did` | required | 推送来源 service DID；MUST 等于 body `source_service_id`，并进入 HTTP Message Signature transcript。 |
| `Destination-Service-ID` | header | `did` | required | 接收方 service DID；MUST 等于实际接收服务 identity，并进入 HTTP Message Signature transcript。 |
| `Content-Digest` | header | `sha-256=:...:` | required | 按 [`../sync/service-http-binding.md` §2.5.1](../sync/service-http-binding.md) 覆盖 exact canonical HTTP content bytes；接收方 MUST 在 JSON 业务解析与验签前对 exact bytes 重算，拒绝 `sha256=:` alias、非 canonical JSON wire 与 parse-then-canonicalize verification。 |
| `Signature-Input` | header | `string` | required | RFC 9421 covered components MUST 至少包含 `@method`、`@target-uri`、`@authority`、`content-digest`、`source-service-id`、`destination-service-id`、`idempotency-key`，并带 `created` / `expires`。 |
| `Signature` | header | `string` | required | 来源 service DID 的逐次 HTTP Message Signature；纯 bearer 不满足 transaction push 认证。 |
| `source_service_id` | body | `did` | required | 推送来源 service DID。 |
| `events` | body | `EventEnvelope[]` | conditional | 推送给 Applet 的非空 signed Event 数组；每项必须满足 `event-envelope.schema.json`。与 `signals[]` 至少出现一个。 |
| `signals` | body | `SignalEnvelope[]` | conditional | 非持久、encrypted-only 的非空 Signal Extension envelope 数组；与 `events[]` 至少出现一个。 |

> **HTTP signature、source signature anchor 与 `received_at`(normative)**:[`applet-integration.md` §7.3.1](./applet-integration.md) / §16 把逐次 RFC 9421 HTTP message signature、`source_signature_anchor` audit value 与 `received_at` audit metadata 列为 transaction push 的 MUST。它们由 transport / audit 层承载（HTTP `Signature` / `Signature-Input` header 与 receiving service 记录的 audit metadata），**不进入** transaction body；receiver MUST 校验 HTTP message signature，形成并持久化 `source_signature_anchor`，记录 `received_at`，缺失任一者 MUST 拒绝。

请求示例（非完整 schema）：

```json
{
  "source_service_id": "did:webvh:z7SrvceTnL4rP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z:server.example",
  "events": [],
  "signals": []
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
GET /_arkret/edge/applet/actors/{actor_id}
```

响应字段：`exists: boolean` required；`actor_id: did` optional；`display_name: string` optional；`external_ref: object` optional。

响应示例（非完整 schema）：

```json
{
  "exists": true,
  "actor_id": "did:webvh:z5ApPLeTnL4rP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z:applet.example:ghost:u123",
  "display_name": "Alice",
  "external_ref": {}
}
```

## 5. Query Realm

```text
GET /_arkret/edge/applet/realms/{realm_id_or_alias}
```

响应字段：`exists: boolean` required；`realm_id: id` optional；`title: string` optional；`external_ref: object` optional。

响应示例（非完整 schema）：

```json
{
  "exists": true,
  "realm_id": "ak:realm:c0c69410-0000-8000-8000-000000000000",
  "title": "#general",
  "external_ref": {}
}
```

## 6. Protocol Metadata

```text
GET /_arkret/edge/applet/protocols/{protocol}
```

响应字段：`protocol: string` required；`display_name: string` required；`icon_blob_ref: string` optional；`field_definitions: object` required；`instances: object[]` optional。

响应示例（非完整 schema）：

```json
{
  "protocol": "slack",
  "display_name": "Slack",
  "field_definitions": {},
  "instances": []
}
```

## 7. Bridge Error Event

```json
{
  "kind": "ak.applet.bridge_error",
  "applet_id": "ak:applet:dd552c17-0000-7000-8000-000000000000",
  "realm_id": "ak:realm:c0c69410-0000-8000-8000-000000000000",
  "failed_transaction_ref": "ak:event:019640ed-8000-8000-8000-000000000000",
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
| `kind` | `string` | required | 固定为 `ak.applet.bridge_error`（wire Event kind，进 Realm history）。 |
| `applet_id` | `id` | required | 产生该错误的 Applet id。 |
| `realm_id` | `id` | required | 该 bridge error 所属 Realm；reducer / 客户端据此做可见范围与授权判定。 |
| `failed_transaction_ref` | `ref` | required | 指向失败的 transaction / 源 Event（如 push 中的 `event_id` 或 transaction idempotency 记录），用于审计回溯。MUST NOT 内联未授权外部正文。 |
| `error_class` | `string`（封闭枚举） | required | 错误类别封闭枚举，取值 **MUST** 属于 `external_network` / `auth` / `schema` / `rate_limit` / `policy`(供聚合与告警)。`error_class` 是粗粒度类别，具体错误码由 `error_code` 承载(例如 `error_class="rate_limit"` 配 `error_code="external_rate_limited"`);二者不得混用。`rate_limit` 是该枚举的 canonical 类别名,[`applet-integration.md` §14](./applet-integration.md) 的重试语境用 `rate_limited` 指同一类错误状态。该枚举的机读 enum 权威源为 [`schemas/event-payload.schema.json`](../../artifacts/schemas/event-payload.schema.json) 的 `ak.applet.bridge_error` payload。 |
| `error_code` | `string` | required | 具体错误码（如 `external_rate_limited`）。 |
| `retriable` | `boolean` | required | 该错误是否可重试；发送方据此决定是否以相同 `Idempotency-Key` 重试（与 [`applet-integration.md` §14](./applet-integration.md) 重试规则一致）。 |
| `visibility_scope` | `string`（封闭枚举） | required | 该 error event 的可见范围枚举，取值 MUST 属于 `realm_admins` / `applet_controller` / `realm_members`；客户端 MUST 按此限制展示，MUST NOT 把 bridge 内部错误细节暴露给无关成员。 |
| `external_ref` | `object` | optional | 外部网络引用（protocol / network id 等）；MUST NOT 包含未授权外部正文明文。 |
| `message` | `string` | optional | 人类可读摘要；MUST NOT 泄露未授权外部正文。 |
| `retry_after_ms` | `int` | optional | 建议重试延迟，仅当 `retriable=true` 时有意义。 |

`ak.applet.bridge_error` MUST 绑定 `realm_id`、`failed_transaction_ref`、`retriable` 和 `visibility_scope`；缺少任一 required 字段的 bridge error event MUST 被以 `schema_violation` 拒绝。该 event MUST NOT 泄露未授权外部正文（与 [`applet-integration.md` §16](./applet-integration.md) 一致）。
