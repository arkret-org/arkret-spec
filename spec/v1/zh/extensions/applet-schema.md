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

单主体 identity、条件 transport、首次 bootstrap 与严格 invocation 的完整准入合同另见
[applet-client-and-invocation](./applet-client-and-invocation.md)。Applet Account 的 principal 必须
等于 service_id；Applets 仅使用 did:webvh，旧 Bot identity 与 install_bot 分支都拒绝。


```json fragment
{
  "kind": "ak.applet.registration",
  "applet_id": "ak:applet:dd552c17-0000-7000-8000-000000000000",
  "service_id": "ak:did_core:webvh:z5ApPLeTnL4rP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z",
  "controller_principal_id": "ak:did_core:webvh:z2dmjQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn",
  "transport": {"kind":"https_push"},
  "base_url": "https://applet.example/applet",
  "applet_actor_id": {"kind":"account","account_id":{"principal_id":"ak:did_core:webvh:z5ApPLeTnL4rP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z","station_id":"ak:did_core:webvh:z6MkStationScid"}},
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
> 示例中 `proof` 字段省略字段不是合法 v1 wire 形态：它必须是 accepted Applet Package
> 的 controller DID detached proof 的逐字副本，并包含 `detached_proof` schema 的全部 required
> 字段；`payload_digest` 覆盖 canonical package（不含 package `proof` 自身）。formal registration
> Event 另由安装管理员签署，且由接收 Station 加 admission proof。
> 空 `"proof": {}` 形态 MUST 被 receiver 以 `schema_violation` 拒绝。

> **`requested_scopes` 是请求声明，不是授权**：该数组只是 Applet 在 registration 时声明它"打算请求的能力范围"，用于 Realm owner / human reviewer 审批 UI 展示。registration 接受**不**等于授予；Applet 实际写入 / 读取任何对象都需要独立的 `ak.capability.grant` event 命中具体 action / resource selector / constraint。reducer **MUST NOT** 因为 `requested_scopes` 包含某 action 而隐式 allow 该 action。详见 [`extensions/applet-integration.md` §11](./applet-integration.md)（末段）与 §4.1。

> **`claimed_profiles` 是 durable profile binding**：安装方 MUST 从已验证 Applet Package
> 原样复制 canonical profile-id 集合，且至少包含 `ak.profile.applet_service.v1`。它不是
> capability；但 profile-bound grant authority rule 只能读取已 accepted registration Event
> 中的该字段，不能读取带外 package cache、preview DTO 或 registry 响应。

> **`registration_epoch`（registration epoch hash）**：对该 registration 的 canonical security transcript（不含 `proof` 与 `registration_epoch` 自身）取的稳定 epoch hash，唯一标识本次 registration 的安全版本。它用于 [`applet-integration.md` §11](./applet-integration.md) 的 delegated-agent grant 绑定：grant constraint MUST 绑定 `registration_epoch`。transcript MUST 通过 [`ak.schema.applet_registration_epoch_transcript.v1`](../../artifacts/schemas/applet-registration-epoch-transcript.schema.json) 校验，并按下方 §1.0.1 的唯一算法计算。registration 首次接受、renew / key 变更或 binding invalidation 时，verifier MUST 展开 transcript evidence，按 method-specific version evidence 读取 service DID Document，并确认 DID Document digest、accepted signing key set 与 epoch 捕获值一致。Applet service 必须能为所有 creation / Event 提供可历史复验的 `AuthenticatedSignerResolutionEvidence::Service`，因此 v1 registration epoch 只接受 `did:webvh`；无历史版本证明的 `did:web` 必须 fail closed，不能以 current snapshot、HTTP 来源签名或 registration epoch hash替代。普通 grant 存储、匹配与 reducer replay 只绑定已接受的该 epoch，不得逐次 re-fetch。该字段 required。

### 1.0.1 `registration_epoch` transcript 与计算算法（normative）

唯一 canonical transcript 是 `ak.schema.applet_registration_epoch_transcript.v1` 的 closed object，顶层字段依次为：`schema`、`derived_registration`、`service_did_document`、`accepted_signing_keys`、`endpoint_policy`、`webhook_auth`、`security_policy`。不得加入 package id、package digest、proof、registration epoch 自身或实现私有缓存字段。

- `derived_registration` MUST 固定包含 schema 所列的 registration 安全字段；`proof`、`registration_epoch` 与派生 `manifest` 不进入该对象。manifest 的安全含义必须展开到 `endpoint_policy`、`webhook_auth` 与 `security_policy`，不得通过嵌套 opaque manifest 间接参与 hash。
- `service_did_document` MUST 包含 `service_id`、canonical DID Document 的 `document_digest` 与 closed `method_version`。`method_version.method` 只允许 `did:webvh`，`unversioned_refetch` 固定为 `false`，并至少给出 `version_id` 或 `version_time`；`did:key` expansion 不能承担 Applet Account，必须拒绝。没有稳定版本证据、必须依赖 current refetch 的 method 不能形成 Applet producer 的历史 signer root，MUST fail closed。
- 以下数组是数学集合，producer MUST 先按 UTF-8 字节序升序排列并拒绝重复项：`protocols`、`requested_scopes`、`claimed_profiles`、`webhook_auth.accepted_signature_algorithms`、`accepted_signing_keys`（按 `key_ref`）、三个 namespace bucket（按 `pattern`，相同 pattern 再按 `exclusive=false` 在前）、`endpoint_policy.endpoints`（按 `method`、`path`、`auth` 的 tuple）。同一排序键重复 MUST fail closed，不能靠“保留第一项”消歧。
- 任意 optional 字段缺失时 MUST 直接省略；不得以 JSON `null` 代替。对象成员顺序最终由 JCS 处理；上述数组排序在 JCS 之前完成。
- transcript 通过 schema 与集合规范化校验后，令 `canonical_bytes = JCS(transcript)`；令域分离字节为 UTF-8 `arkret-applet-registration-epoch-v1\n`（末尾单个 LF，字节 `0a`）；最终值为 `registration_epoch = "sha256:" + lowercase_hex(SHA-256(domain_separator || canonical_bytes))`。

[`applet-registration-epoch-fixture.json`](../../artifacts/fixtures/applet-registration-epoch-fixture.json) 给出 transcript、完整 canonical bytes、expected digest 以及排序重复、null、DID version 分支和安全字段变更的负向向量。实现 MUST 执行这些向量，不得只检查 fixture 文件存在。

`applet_registration_payload.required` 条目的相对顺序 MUST 与 schema `properties` 字段出现顺序一致；
required 集合与顺序均直接从 schema 读取，本节不复述派生清单。该 registration payload 的权威机读 schema 是
[`schemas/event-payload.schema.json` 的 `$defs/applet_registration_payload`](../../artifacts/schemas/event-payload.schema.json)
（`applet.schema.json` 仅描述 applet object metadata snapshot，不含本 registration payload）。

## 1a. Applet Package Schema

`ak.schema.applet_package.v1` 是开发者/供应商发布的可安装 package；它不进入 Realm history，不授权写入。安装时 Station 的 authorization capability MUST 从 package 派生 canonical `ak.applet.registration` payload，再根据管理员批准生成 grant。

`registration_epoch_evidence` **不是 AppletPackage 字段**。它是安装时验证 DID resolution 与重算
`registration_epoch` 的 authority input，唯一 wire 载体是 §1b caller-signed
`registration_event.payload.manifest.registration_epoch_evidence`。AppletPackage 必须拒绝该未知成员；
`package_digest` 与 controller proof transcript 均不得包含 evidence。Station 与 Applet service 都从
同一个管理员签名 Event 读取并验证 evidence，accepted value 持久化后供 epoch runtime check 使用。

字段参考:

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `schema` | yes | 固定 `ak.schema.applet_package.v1`。 |
| `package_id` | yes | typed id 或 DID URL；仅用于 package 分发。 |
| `applet_id` | yes | 唯一合法形态为 `ak:applet:<uuidv7>`；其它形态均不合法。 |
| `service_id` | yes | Applet runtime 的稳定 service `did_core_id`。 |
| `controller_principal_id` | yes | 对 package 负责的 controller `did_core_id`；package proof VM 的 bare `did` 必须经 adapter 投影到该值。 |
| `transport` | yes | Closed `https_push|client_pull`；两支同样使用 service 持钥认证。 |
| `base_url` | conditional | 仅 https_push 必填；client_pull 禁止。 |
| `applet_actor_id` | yes | 完整 account ActorId；principal_id 必须等于 service_id，保留 exact Station。 |
| `claimed_profiles` | yes | v1 Applet profile id 数组；MUST 至少包含 `ak.profile.applet_service.v1`。 |
| `protocols` | yes | 外部协议标识数组。 |
| `namespaces` | yes | `actors` / `realms` / `handles` 对象形态 namespace。 |
| `requested_scopes` | yes | capability action 请求列表；只用于审批 UI。 |
| `endpoint_policy` | yes | 实际支持的 Applet API endpoint 与 auth requirement。 |
| `webhook_auth` | yes | HTTP message signature key ref / accepted algorithms；`key_ref` MUST 是某个 Applet service `did` 下的 DID URL，该 `did` 经已登记 adapter 投影后 MUST 等于 `service_id`（`did_core_id`），并作为 app/bridge→arkret inbound transaction push 的投递验签 key。 |
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
| `expires_at` | optional | package 可安装截止时间。 |
| `created_at` | yes | package 创建时间。 |
| `proof` | yes | controller DID detached proof。 |

Package -> registration 派生映射:

| `ak.applet.registration` 字段 | Package 来源 | 规则 |
| --- | --- | --- |
| `applet_id` | `applet_id` | 原样复制；只接受 `ak:applet:<uuidv7>`。 |
| `service_id` | `service_id` | 原样复制；必须可解析并绑定 Applet endpoint。 |
| `controller_principal_id` | `controller_principal_id` | 原样复制；必须验证 controller proof。 |
| `transport` | `transport` | 原样复制；进入安全 epoch transcript。 |
| `base_url` | `base_url` | https_push 原样复制并验证 DID endpoint；client_pull 两侧都禁止。 |
| `applet_actor_id` | `applet_actor_id` | 原样复制 complete Account；principal core 逐字等于 service_id。 |
| `protocols` | `protocols` | 原样复制；空数组非法。 |
| `namespaces` | `namespaces` | canonicalize 后复制；只接受对象形态。 |
| `receive_events` | `receive_events` | 原样复制；不得从 `endpoint_policy` 猜测默认值。 |
| `receive_signals` | `receive_signals` | 原样复制；不得省略。 |
| `rate_limited` | `rate_limited` | 原样复制；不得省略。 |
| `requested_scopes` | `requested_scopes` | 原样复制；仍只是请求声明。 |
| `registration_epoch` | `registration_epoch` | 由 canonical derived registration + DID/key/endpoint/auth evidence 计算。 |
| `webhook_auth` | `webhook_auth` | 原样复制；必须覆盖 transaction push signature 验证锚点。`key_ref` 的 bare controller `did` 经已登记 adapter 投影后 MUST 等于 `service_id`，并绑定当前 `registration_epoch`；key rotate 后必须通过新的 effective registration / install 生效，旧 key 不得继续放行 inbound push。 |
| `manifest` | `claimed_profiles` + `limits` + policies + optional widget declaration + install evidence | 作为 snapshot 放入 manifest，但不得替代顶层 required 字段；安装 authoring 时加入唯一 `registration_epoch_evidence`，并由管理员 Event proof 覆盖；widget snapshot MUST 保持 `ak.schema.applet_widget_declaration.v1` 的闭合形态。 |
| `proof` | `proof` | accepted package 的 controller detached proof 逐字副本；`payload_digest` 只覆盖 canonical package，formal registration Event 使用独立 `producer_proof`。 |
| `created_at` | `created_at` | 原样复制。 |

Widget declaration 的字段顺序与 schema 一致：`schema`、`widget_origin`、`csp`、`token_scope`、`consent_required`。`token_scope` 是对象而非字符串数组，至少包含 `actions[]`、`resources[]` 与 `expires_at`；host / node 签发给 widget 的短期 token MUST 是该 scope 的子集，不能回退到用户 full session 权限。

### 1a.1 Applet-managed Actor creation anchor

`ak.schema.applet_managed_actor_provision.v1` 以
[`applet-managed-actor.schema.json`](../../artifacts/schemas/applet-managed-actor.schema.json) 为唯一闭合
wire schema。payload 必须携完整 `actor_id: ActorId`；Applet managed actor 使用
`account` 分支，`principal_id` 与 `station_id` 封闭在其 `account_id` 对象内。payload 还必须携闭合
`actor_role=applet|ghost`、`initial_resolution`、v1 唯一合法的完整 WebVH
`method_history_evidence`、immutable `registration_ref` 与 `applet_authority_ref`。did:web snapshot 与
did:key expansion 不能为长期可轮换的高风险 managed authority 提供所需 history/version pinning，均非法。Ghost 还必须携
`external_ref`，Applet 自身禁止携该字段。contract registry 的 provision typed current result subject 是 pair 的复合键，不能仅按
core id 做 CAS。Package/registration/Ghost durable record 只保存 accepted provision Event 与 PCR genesis
anchor；current resolution ref 不属于这些对象。provision typed current result subject 是 `JCS(actor_id)`，不得以裸
`principal_id` 或平行 server sidecar 建立第二套 CAS 键。

## 1b. Applet Install Operation Objects

安装使用管理员、目标 Station 与 Applet service 的两步 co-sign 握手，机器契约分别是
[`applet-install-operations.schema.json`](../../artifacts/schemas/applet-install-operations.schema.json) 与
[`applet-install-authoring.schema.json`](../../artifacts/schemas/applet-install-authoring.schema.json)。

Install preview request 只含 `applet_package` 与 closed `authoring_request_basis`。install basis 固定
`purpose=install_applet`，精确绑定目标 Station、安装管理员、typed `applet_id`、Applet
`service_id`、`package_digest`、effective scope、审批/策略，并且唯一内嵌管理员签名的
`registration_event` 与 `capability_grant_events`。basis 不携请求时间。registration epoch evidence 只在
`registration_event.payload.manifest.registration_epoch_evidence` 出现；preview 顶层、basis sibling、package
及 commit 均不得镜像。

Station 重新验证 package、Event/evidence、当前策略和 namespace，生成 canonical `InstallPlan`，再返回
`{plan, authoring_request}`。Station 自行取得 `issued_at`，要求
`0 < expires_at-issued_at <= 5 minutes` 且 `proof.created_at == issued_at`。closed request 固定
`purpose=install_applet`，携 exact basis、`plan_digest`、current `governance_station_id`、时间窗与 proof。
`request_payload_digest` 是不含 proof 的 closed request 的 RFC 8785 SHA-256，逐字等于
`proof.payload_digest`；`authoring_request_digest` 是完整 signed request 的 RFC 8785 SHA-256。协议不
mint request ID。相同 subject/payload 的 preview 返回 ledger 中已保存的 exact signed bytes；异 payload 的
新 generation 在同一事务中永久 supersede 旧未提交 generation。

客户端把 exact signed request relay 到标准
`POST /_arkret/edge/applet/managed-actors/author`
（`ak.edge.applet.managed_actor.command.author.v1`）。该 operation 以
`purpose=install_applet|provision_ghost` 的 closed union 同时服务 Applet 与 Ghost；Applet service 必须用
current trusted Station service identity/key 验证 proof，并逐字校验 package/service/admin
Event/evidence/actor/plan/expiry 绑定；不得只接受自洽历史 key。Applet service 按既有 creation admission 签
`ak.applet.managed_actor.provision`、Applet PCR `ak.realm.create`、
`ak.identity.accountability_grant`、`ak.profile.create` 四个 formal Events：provision/accountability 使用 service actor，
PCR genesis/Profile 使用 service `executed_by`，不得新增预生效 Applet Account 直签特例。四个 Event 对象只在 closed
`managed_actor_bundle` 的 role-neutral 字段
`managed_actor_provision_event/pcr_genesis_event/accountability_grant_event/profile_event` 出现一次；禁止
`bot_*`、`ghost_*` alias。bundle proof 绑定完整 signed-request digest 与不含 proof 的 closed bundle。
request/bundle proof 分别使用
`ak.applet_managed_actor_authoring_request_proof.v1` 与
`ak.applet_managed_actor_bundle_proof.v1`；context 是 canonical binding object 常量，不是 wire 字段。
这两个 proof MUST 使用 `applet-install-authoring.schema.json#/$defs/managed_actor_proof` 的 closed
形态：`kind`、`verification_method`、`payload_digest`、`created_at`、`audience_id`、`jws`。
`audience_id` 是单一责任主体的 `DidCoreId`：request MUST 等于 `basis.service_id`，bundle MUST 等于
已绑定 request 的 `basis.target_station_id`；MUST NOT 使用 URL、裸 DID、数组或通用 `audience` 别名。
两者的 canonical signing binding 都依次包含 `context`、`payload_digest`、`verification_method`、
`created_at`、`audience_id`，验证时 MUST 同时检查受众与对应 branch 的身份逐字相等。
该专用身份字段遵循 `common-fields.md` §2.1 的 `_id` 规则，不继承通用 proof 的自由字符串受众形态。 专用 proof 的两个签名域登记于 `proof-context-registry.json` 的 `domain_separations[]`（`primitive=detached_signature`），schema 使用 `x-arkret-signature-domain`；它们不再属于仅服务通用 proof leaf 的 `contexts[]`，既有签名域常量和 `context` binding 字段保持不变。
Applet service 必须在响应前按 branch subject 与 request digest 原子保存 exact request/bundle、actor key
handle、method history 与 provision state。restart 后 exact replay 返回原 bytes；不得从 request 确定性派生
私钥或依赖易失内存 cache。

四个 creation Event 的 actual producer 都是 Applet service：provision/accountability 的 actor 是 service，PCR
genesis/Profile 则由相同 service 作为 `executed_by`；尚未 accepted 的 Applet/Ghost 不签这四条 Event。Applet
service MUST 从 request 中唯一的 registration epoch evidence 与自己已验证的完整 method-native DID state 构建
一份 `AuthenticatedSignerResolutionEvidence::Service`，使用统一 canonical helper 重算
`signer_resolution_evidence_ref`，在返回 bundle 前原子保存 exact root；四条 Event 的唯一 producer proof 是 closed
Event proof，不携带该 ref，其 verification method 与 key MUST 逐字等于该 root 绑定的值。目标 Station 独立重建并逐字
核对 service id、method、key、registration epoch 与 ref；任一不匹配
使 closed aggregate 零写入。不得把 verification-method hash、registration epoch、HTTP message signature 或 bundle
proof digest当作 signer evidence ref。

Commit request 只有：

```json fragment
{
  "applet_package": {},
  "authoring_request": {},
  "managed_actor_bundle": {}
}
```
Station 从 authoring request 唯一提取管理员 Events/evidence/scope/policies，从 bundle 唯一提取四个
Applet Events，重新计算所有 digest、Event refs、plan 与权限，并在一个 durable transaction 内原子提交完整
formal Event 集合、Applet record、namespace/managed-authority claims 与 idempotency outcome。任何失败必须零
Event 可见；Station 不得代签、重建或逐条 fan-out。

同一 `(applet_id,target_station_id)` 的后续 Realm/Circle install 走 closed
`reuse_existing_managed_actor` 分支，只重验首次 accepted provision/PCR/accountability/profile anchors 并提交
本次 registration/grant；不得再携新 bundle 或创建第二 Applet DID。Ghost subject 是
`(provision_ghost,applet_id,target_station_id,external_ref)`，Realm 与 package digest 均不是 identity
维度，因此同 external tuple 跨 Realm 复用、跨 target Station 独立。

首次 commit 必须在 `authoring_request.expires_at` 前到达。对于已经成功的相同
`Idempotency-Key` + exact canonical body，durable replay lookup 必须先于 expiry 检查并返回原 outcome，即使
authoring request 此时已过期；同 key 不同 body 必须 `duplicate_conflict`。Commit 响应以
`applet_install_outcome` 为权威。

## 2. Namespace Pattern

```json fragment
{
  "exclusive": true,
  "pattern": "did:webvh:*:applet.example:ghost:*"
}
```
Pattern 语法：

- `*` 匹配恰好一个 segment，且 `*` **不跨 segment 分隔符**。
- `**` 匹配一个或多个 path-like segment，且**仅对 `/` 分隔符**有 path-like 语义（即 `**` 只跨 `/`，不跨 `:`）。
- 字面量 `*` MUST 转义为 `\\*`。

**Segment 分隔符（normative）**：segment 边界由 pattern 所属命名空间决定，匹配前 pattern 与目标字符串按相同分隔符集合切分：

- **Actor namespace（DID pattern）**：分隔符为 `:`。`*` 匹配 DID 中由 `:` 分隔的**单一** segment，MUST NOT 跨越 `:`。例如 `did:webvh:*:slack-bridge.example:ghost:*` 匹配 `did:webvh:z6MkGhostU123:slack-bridge.example:ghost:u123`，但 MUST NOT 匹配 `did:webvh:z6MkGhostU123:slack-bridge.example:ghost:team:u123`（后者跨了一个额外 `:` segment）。DID pattern 中 `**` 同样不跨 `:`——DID 没有 path-like `/` 结构，因此 DID pattern MUST NOT 依赖 `**` 的跨段语义。`#fragment` 不参与 namespace 匹配。
- **Actor namespace pattern 的形状约束（normative）**：`did:webvh` 的 SCID 在第三个 segment，而每个 Ghost MUST 有自己独立的 validated SCID（[`applet-integration.md` §3.4](./applet-integration.md)），因此覆盖 Ghost 的 pattern 的 SCID 段只能是 `*`。`namespaces.actors[]` 的每条 `pattern` MUST 满足：(a) 以 `did:webvh:` 开头；(b) 第三个 segment 是 `*` 或一个非空的具体 SCID；(c) 紧随其后的 host segment 是**字面量**（MUST NOT 是 `*` 或 `**`）且逐字等于 registration `service_id` 当前已验证解析出的那个 bare `did` 的 host segment；(d) host 之后 MUST 至少还有一个 segment。任一条不成立 MUST 在 install preview 与 commit 上 fail closed，code=`applet_namespace_pattern_invalid`。此外，把 registration 自己 `service_id` 的 SCID 写死在第三段的 pattern **永不命中任何合规 Ghost**（合规 Ghost 的 SCID 必然不等于 service SCID），MUST 以同一 code 拒绝；写死**其它**具体 SCID 的 pattern 合法，它表示一个只覆盖该单一 actor 的 namespace。
- **Realm / portal namespace pattern**：分隔符集合为 `:` 与 `/`。`*` 匹配由 `:` 或 `/` 分隔的单一 segment，不跨任一分隔符；`**` 只对 `/` 分隔的 path-like 尾段生效（匹配一个或多个 `/`-分隔 segment），MUST NOT 跨 `:`。例如 `slack:team:*:channel:*` 匹配 `slack:team:T123:channel:C456`；`slack.acme.example/*` 匹配单层 path，`slack.acme.example/**` 匹配多层 path。
- 任一分隔符集合下，`*` / `**` MUST NOT 匹配空 segment；exclusive namespace 的冲突判定按下方 §2.1 在切分后的 segment 序列上进行，其拒绝后注册者的义务见 [`applet-integration.md` §4.1](./applet-integration.md)。

### 2.1 Exclusive namespace 冲突判定（normative）

同一 namespace bucket 内的两条 exclusive pattern **冲突**，当且仅当存在至少一个字符串同时被两者匹配（两者匹配语言的交非空）。判定只看 pattern 形状：实现 MUST NOT 以“当前没有实际 actor / Realm / handle 同时命中”为由放行，也 MUST NOT 只在两条 pattern 逐字节相同时才判冲突。

对同一 bucket 内的两条 pattern P、Q：

1. 按该 bucket 的分隔符集合把 P 与 Q 切成 token 序列，并记录每个 token 之前的分隔符种类。`:` 与 `/` 是不同种类，MUST NOT 互相匹配。
2. 逐位比较 token：literal 与 literal MUST 逐字节相等（转义后的字面量 `*` 按 literal `*` 比较）；`*` 与任意**单个**非空 token（包括对方的 `*`）兼容。
3. 两条都不含 `**` 时：token 数量不等即判**不冲突**；数量相等且逐位全部兼容即判**冲突**。
4. 含 `**` 时（按上文只可能出现在 realm / handle bucket 的 `/`-分隔尾段）：`**` 之前的部分按第 2、3 条逐位比较；`**` 与对方剩余的 `/`-分隔尾段兼容，当且仅当对方剩余尾段至少含一个 segment（对方的 `**` 满足该条）。`**` MUST NOT 与仍由 `:` 分隔的剩余部分兼容。
5. Actor bucket 的 SCID 段按第 2 条处理：`*` 与 `*`、`*` 与任意具体 SCID 都兼容。因此 SCID 段普遍为 `*` 之后，actor namespace 的排他性**只由 host 段承载**——§2 的 host 段字面量约束是 exclusive 判定仍然可用的唯一依据；没有它，两条 `did:webvh:*:*:ghost:*` 形状的 pattern 会与全网所有 actor namespace 冲突。

冲突比较的对象是**其它** `applet_id` 当前 active 的 exclusive namespace claim。同一 `applet_id` 自身 registration 的重申、renew，或为新 `effective_scope` 复用同一 registration 的 install，MUST NOT 与自己判冲突。判定为冲突时，registry 与执行安装准入的 Station MUST 拒绝后注册者，code=`applet_namespace_conflict`。

## 3. Transaction Endpoint

```text
POST /_arkret/edge/applet/transactions
Idempotency-Key: <opaque-string>
```

请求字段：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `Idempotency-Key` | header | `string` | required | 发送方生成的幂等 / nonce 键，长度 1..128；接收方 MUST 以 `(operation_id, direction, applet_id, Source-Service-ID, Destination-Service-ID, Idempotency-Key)` 定位幂等记录，并绑定 canonical body digest 与 `delivery_authentication_record`；重复键但 body digest 或投递认证记录不同 MUST fail closed。 |
| `Source-Service-ID` | header | `did_core_id` | required | 推送来源 service `did_core_id`；MUST 等于 body `source_id`，并进入 HTTP Message Signature transcript。来源 VM 的 bare `did` 必须经 adapter 投影到该值。 |
| `Destination-Service-ID` | header | `did_core_id` | required | 接收方 service `did_core_id`；MUST 等于实际接收服务 identity，并进入 HTTP Message Signature transcript。 |
| `Content-Digest` | header | `sha-256=:...:` | required | 按 [`../sync/service-http-binding.md` §8.2](../sync/service-http-binding.md) 覆盖 exact canonical HTTP content bytes；接收方 MUST 在 JSON 业务解析与验签前对 exact bytes 重算，拒绝 `sha256=:` alias、非 canonical JSON wire 与 parse-then-canonicalize verification。 |
| `Signature-Input` | header | `string` | required | covered components 与 signature parameters 的唯一合同是 `ak.http_signature.scenario.applet_transaction.v1`，正文见 [`applet-integration.md` §7.3.1](./applet-integration.md)。本页不复制该清单。 |
| `Signature` | header | `string` | required | 来源 service 已验证 `did` / VM 的逐次 HTTP Message Signature；纯 bearer 不满足 transaction push 认证。 |
| `applet_id` | body | `applet_id` | required | 精确选择 active install；必须与来源 service、当前 registration epoch/key 唯一交叉绑定，不得按同 service 任取首条安装。 |
| `source_id` | body | `did_core_id` | required | 推送来源 service 的稳定 `did_core_id`。 |
| `events` | body | `EventEnvelope[]` | conditional | 推送给 Applet 的非空 signed Event 数组；每项必须满足 `event-envelope.schema.json`。与 `signals[]` 至少出现一个。 |
| `signals` | body | `SignalEnvelope[]` | conditional | 非持久、encrypted-only 的非空 Signal Extension envelope 数组；与 `events[]` 至少出现一个。 |

> **HTTP signature、delivery authentication record 与 `received_at`(normative)**:[`applet-integration.md` §7.3.1](./applet-integration.md) / §16 把逐次 RFC 9421 HTTP message signature、closed `delivery_authentication_record`、其 domain-separated digest 与 `received_at` audit metadata 列为 transaction push 的 MUST。它们由 transport / audit 层承载（HTTP `Signature` / `Signature-Input` header 与 receiving service 记录的 audit metadata），**不进入** transaction body；receiver MUST 校验 HTTP message signature，从已验证输入派生并持久化记录及 digest，记录 `received_at`，缺失任一者 MUST 拒绝。

请求示例（非完整 schema）：

```json fragment
{
  "applet_id": "ak:applet:01904100-0000-7000-8000-aaaaaaaaaaaa",
  "source_id": "ak:did_core:webvh:z7SrvceTnL4rP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z",
  "events": [
    {
      "event_id": "ak:event:AQsHmGu_9sPOyJ4aG8VlWQBp8wGGhdC-BjfAaXqrIbk-",
      "kind": "ak.message.create"
    }
  ]
}
```
上例只展示 transaction carrier；`events[0]` 的其余 required EventEnvelope 字段必须按
`event-envelope.schema.json` 补齐，不能把该缩略对象直接发送。

响应字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `status` | `enum(accepted,partial,rejected)` | required | 所有项接受、部分接受或全部拒绝。 |
| `rejected` | `object[]` | optional | 被拒绝事件摘要。 |
| `retry_after_ms` | `int` | optional | 建议重试延迟。 |

响应示例：

```json fragment
{ "status": "accepted" }
```
## 4. Query Actor

```text
GET /_arkret/edge/applet/actors/{actor_id}
```

响应字段：`exists: boolean` required；`actor_id: did` optional；`display_name: string` optional；`external_ref: object` optional。

响应示例（非完整 schema）：

```json fragment
{
  "exists": true,
  "actor_id": "ak:did_core:webvh:z5GhostU123Scid",
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

```json fragment
{
  "exists": true,
  "realm_id": "ak:realm:Adoyg50aOV537gzxNy87EOdUlHiIujznqwZcMLSGFmzg",
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

```json fragment
{
  "protocol": "slack",
  "display_name": "Slack",
  "field_definitions": {},
  "instances": []
}
```
## 7. Bridge Error Event

```json fragment
{
  "kind": "ak.applet.bridge_error",
  "applet_id": "ak:applet:dd552c17-0000-7000-8000-000000000000",
  "realm_id": "ak:realm:Adoyg50aOV537gzxNy87EOdUlHiIujznqwZcMLSGFmzg",
  "failed_transaction_ref": "ak:event:AQsHmGu_9sPOyJ4aG8VlWQBp8wGGhdC-BjfAaXqrIbk-",
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
