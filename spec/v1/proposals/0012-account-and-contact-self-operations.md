---
ckp: CKP-0012
title: Account Self-Service Operations — close the protocol gaps behind soland's /self/account/*
normative: false
stability: v1
updated: 2026-06-04
status: accepted
created: 2026-06-04
accepted: 2026-06-04
authors:
  - chris@acroidea.com
depends_on: []
merged_to:
  - spec/v1/artifacts/schemas/account-operations.schema.json
  - spec/v1/artifacts/registry/contract-catalog.json
  - spec/v1/artifacts/registry/operation-registry.json
  - spec/v1/artifacts/registry/schema-registry.json
  - spec/v1/artifacts/registry/error-code-registry.json
  - spec/v1/artifacts/registry/operations-error-mapping.json
  - spec/v1/artifacts/reports/operation-schema-index.json
  - spec/v1/artifacts/openapi/cokret-service-api.openapi.yaml
  - spec/v1/artifacts/bindings/non-http-bindings.yaml
  - spec/v1/zh/sync/service-http-binding.md
  - spec/v1/zh/sync/service-api-schema.mdx
  - spec/v1/zh/sync/service-surface.md
  - spec/v1/zh/sync/transport-bindings.md
---

> **Status: accepted, merged into v1 normative spec on 2026-06-04.** 本文件保留为历史设计依据；后续 wire contract 以 `contract-catalog.json#operation_registry`、OpenAPI、schema artifact 与 `zh/sync/` 正式规范为准。
>
> **范围拆分(2026-06-04):** 本提案原含联系人关系(`ck.contact.*`)。审议发现"联系人 + 找他聊天"横跨 consent / discovery / realm / strand 多个 normative spec,是一份端到端编排提案,已分拆为 **[CKP-0013 Contact & Direct Conversation Lifecycle](./0013-contact-and-direct-conversation-lifecycle.md)**。本提案现只覆盖 **account self-service 四项**,可独立速通,不被联系人设计阻塞。

## 1. Summary

把一批**通用客户端刚需、但 catalog 缺失**的 self-service 账户能力正式提升为协议 operation,路径由 spec 钉死、可经 `*.describe` 协商:

- **账户一次性自读 / profile 更新**落 `self` 段(`/_cokret/self/account/*`);
- **账户注册 / 自助 logout**落认证入口段 `gate`(`/_cokret/gate/account/*`)——账户创建与会话撤销属认证生命周期,不落 `self`。

当前 yougen 通过硬编码 soland 私有路径(`/_soland/self/account/me`、`/_soland/gate/auth/logout` 等,见 [`yougen/src/api/account.rs`](../../../../yougen/src/api/account.rs))访问这些能力,使其退化为 **soland 专用客户端**,而非通用 Cokret 客户端。本提案补齐对应协议 operation,消除该耦合。

非目标:不引入新 Realm event / reducer 行为;不动 wire 加密路径;不收编 admin 面(`/_soland/admin/*` 按 CHANGELOG 2026-06-04 仍属实现产品面);联系人关系见 CKP-0013。

## 2. Motivation

### 2.1 catalog 现状

`operation-registry.json` 中账户相关 operation 仅有:

```
ck.self.account.describe        ck.self.account.subscribe       ck.self.account.cursor_revoke
ck.gate.account.device_pair     ck.gate.account.issue_session_grant
ck.gate.account.oidc_callback   ck.gate.account.agent_key_pair
```

`ck.account.{describe,subscribe}` 是**聚合元数据 / 流式订阅**,不提供:

- "我是谁"的一次性自读(principal DID / verified handle claim evidence / 设备列表 / 账户状态);
- 账户注册、profile 更新;
- 自助 session 注销(logout)。

(联系人关系的建立 / 应答 / 列举同样缺失,但因横跨多个 spec,单列 CKP-0013 处理。)

### 2.2 下游已在用未注册的 `ck.account.*` id

证据表明 soland 实现层早已使用一批未进 catalog 的 operation id:

- yougen [`api/account.rs`](../../../../yougen/src/api/account.rs) 注释:profile 更新 "Mirrors soland's `ck.self.account.update_profile` wire shape";硬编码 `_soland/self/account/{register,me,profile}`、`_soland/gate/auth/logout`。
- yougen [`api/keys.rs`](../../../../yougen/src/api/keys.rs) 注释:设备吊销 "NOT spec's `ck.admin.revoke_device`"。

即协议与实现已出现**事实漂移**:实现自定义 operation 名,但协议 catalog 不承认。本提案把其中应属协议层的部分正式化,把应属产品层的部分明确划走。

### 2.3 "位置千差万别"问题

非协议 operation 没有 spec 钉死的路径,不同实现可任意放置;通用客户端只能硬编码或逐实现适配。提升为协议 operation 后,`ck.self.account.viewer` 在任何合规服务器都必定位于 `/_cokret/self/account/viewer`,客户端通过 `/_cokret/describe.supported_operations` 仅需发现"是否支持",无需发现"在哪"。

## 3. Specification(proposed operations)

> **信任段总则**:除 §3.2 `register`、§3.4 `session_revoke` 外,本节 operation 要求 `user_session`(holder-bound)、落 `/_cokret/self/...`、不含版本段。`gate` 段是认证生命周期面,不是单一鉴权方式:它同时承载 bootstrap proof、session-grant proof 和 holder-bound `user_session`。`register` / `session_revoke` 属认证生命周期(账户创建 / 会话撤销),落 `gate` 段并与既有 `session-grants` 共面共 proof 词汇,避免双入口。

### 3.1 `ck.self.account.viewer` — 自账户一次性读

| 项 | 值 |
| --- | --- |
| HTTP | `GET /_cokret/self/account/viewer` |
| Auth | `user_session` |
| Response | `AccountView`(`{ principal_id: did, primary_handle_claim?, primary_handle_claim_ref?, handle_claim_digests?, state, devices[], profile? }`) |

`state` MUST 取 [`account-lifecycle.md`](../zh/identity/account-lifecycle.md) §3 定义的**闭合枚举**(`active` / `locked` / `soft_logged_out` / `suspended` / `deactivated` / `erasure_pending`),不得返回手写子集——viewer 是主体身份的权威自读,枚举漂移会让客户端对账户状态判断与状态机不一致。

`primary_handle_claim` 若存在,必须是完整可验证的 `ck.schema.handle_claim.v1` claim;仅返回引用时使用 `primary_handle_claim_ref`。二者互斥。`handle_claim_digests[]` 用于让客户端刷新 / 比对本地 claim cache。viewer **MUST NOT** 把未签名裸 `handle` 字符串作为权威身份字段返回。显示 `@localpart:domain` 时,客户端仍按 [`identity-handles.md`](../zh/identity/identity-handles.md) §3.2 的 claim-led 模型验证 claim、issuer、audience、expiry 与 revocation。

替代 soland `/_soland/self/account/me`。命名用 `viewer` 与既有 `describe`(服务能力)区分:`viewer` 返回**主体身份**(holder-bound),`describe` 返回**服务元数据**(可 pre-auth 限流);二者鉴权与缓存语义不同,故独立 operation(见 §6 Q1,已收敛)。

### 3.2 `ck.gate.account.register` — 账户记录创建

| 项 | 值 |
| --- | --- |
| HTTP | `POST /_cokret/gate/account/register` |
| Auth | bootstrap proof:DID-bound signature / paired device proof / 已签发 session grant proof,与 `/_cokret/gate/account/session-grants`(`ck.gate.account.issue_session_grant`)**同一认证面、同一 proof 词汇** |
| Body | `AccountRegisterRequestBody`(`{ principal_id: did, display_name?, device_id?: id:device, proof? }`) |
| Response | `AccountRegisterOutcome`(principal_id / state / devices / primary_handle_claim? / primary_handle_claim_ref? / handle_claim_digests? / profile?) |

落 `gate` 而非 `self`:register 时账户/会话尚不存在,不满足 `self` 段"本人已认证会话"前提;它与 `session-grants`、`device-pair`、`oidc/callback` 同属认证生命周期入口,应共段、共享 proof 校验路径(收敛自 §6 旧 Q4)。

`register` 是 Auth Server 的 service operation:它验证 / 创建部署本地 `service_account -> principal_id` 绑定,并把客户端带入既有 DID / session / device 生命周期。它 **MUST NOT** 通过裸字段创建新的协议身份真相源,也 **MUST NOT** 把服务端账号记录当作 DID 控制证明、`ck.device.authorize` 或 `ck.session.grant` 的替代。若实现需要为首台设备、session grant 或 Actor Profile 产生持久状态,必须 fan-out 到既有 `ck.device.authorize`、`ck.session.grant`、`ck.profile.create` / `ck.profile.update` 等已注册 event / operation 语义。

`proof` 的承载必须在 OpenAPI schema 中闭合:实现 MAY 使用 body `proof`、holder-bound `Authorization`/DPoP header 或 HTTP Message Signature,但无论 transport 如何,签名 transcript MUST 绑定 `principal_id`、`device_id?`、`audience`、`request_canonical_digest`、`challenge`、`issued_at` 与 `expires_at`。缺少 proof 或 proof freshness 超限时返回 `did_proof_required` / `proof_invalid` 家族错误,不得 fallback 到"服务端已认识该账号"。

`display_name` 只是 bootstrap 展示字段。若持久化到 Actor Profile,必须落到 `ck.profile.create` / `ck.profile.update` 的 `display_name` 字段;不得把它扩展成 handle 或授权主体。Handle 申请、审批、预分配、重签和撤销仍属于 issuer / coauth / 部署本地治理面;本 operation 最多返回 issuer 已签发的 `primary_handle_claim` / `handle_claim_digests`,不得接受或返回未签名裸 `handle` 作为 verified identity。

### 3.3 `ck.self.account.update_profile` — profile 更新

| 项 | 值 |
| --- | --- |
| HTTP | `POST /_cokret/self/account/profile` |
| Auth | `user_session` |
| Body | `AccountUpdateProfileRequestBody`(`{ patch }`),其中 `patch` 为 `ck.patch.v1`;允许路径限于 `display_name`、`avatar_blob_ref`、`profile_fields.<key>` |
| Response | `{ profile: ActorProfile }` |

直接采纳 soland 已用的 `ck.self.account.update_profile` operation 名,但不采纳 soland 临时 DTO 作为 v1 wire。v1 wire 必须沿用 Actor Profile 的 canonical 字段名:头像引用是 `avatar_blob_ref`(`id:blob`),任意展示扩展进入 `profile_fields.<key>`;不得新增 `avatar` / `avatar_ref` / `avatar_url` 作为 canonical 字段。需要兼容 `avatar_url` 的实现 MAY 在 `_soland` 兼容层或 migration adapter 中把 URL 上传 / 解析为 Blob 后写入 `avatar_blob_ref`,但 `/_cokret/self/account/profile` 的协议请求不得接受 URL 作为头像真相源。

`patch` MUST 原子应用,并复用 [`event-and-patch.md`](../zh/models/event-and-patch.md) §4 的路径语法、`set` / `unset` / `add` / `remove` 语义与 reducer-managed 字段保护。`display_name` 写入后必须满足 [`actor-profile.schema.json`](../artifacts/schemas/actor-profile.schema.json) 的长度约束;清空可选字段使用 `$op:"unset"`。`bio` 不是 Actor Profile 顶层 canonical 字段;soland / yougen 现有 `bio` MUST 迁移为 `profile_fields.bio`。下列路径 MUST reject:`handle`、`status`、`principal_id`、`actor_kind`、`accountable_principal_ids`、任何 authorization / lifecycle / handle claim 字段。Handle 仍只来自 signed `ck.schema.handle_claim.v1`,不得通过 profile patch 设置、覆盖或撤销。

`ck.self.account.update_profile` 是 holder-bound service wrapper,不是新的 profile 真相源。服务端接受后 MUST 写入或等价产生 `ck.profile.update` / Actor Profile projection;不得只修改实现私有 account 表再把它伪装成 canonical profile。

**与既有投影面的协同(已收敛)**:yougen 现实现把 profile 更新**同时**镜像到 (a) directory 的可发现 profile、(b) 跨设备 account-data(`client.ui.avatar_blob_ref`)。v1 已将该副作用边界收敛为: `ck.self.account.update_profile` 只承诺更新 server 侧 canonical profile,不隐式触发 `ck.find.directory.announce` 或 `ck.account_data.set`。需要可发现 profile 或跨设备 UI/avatar 状态同步的客户端 / 服务,必须继续显式走对应 Directory / Account Data 路径,直到后续 profile 另行声明更强 fan-out 契约。

### 3.4 `ck.gate.account.session_revoke` — 自助 logout

| 项 | 值 |
| --- | --- |
| HTTP | `POST /_cokret/gate/account/session-grants/revoke` |
| Auth | `user_session`(撤销当前会话);跨 grant / 跨 device / 全量撤销需要 fresh DID/device proof 或显式 capability |
| Body | `SessionRevokeRequestBody`(`{ target_grant_id?: id:grant, target_device_id?: id:device, all_sessions?: boolean, proof? }`) |
| Response | `{ revoked_count: int, revoked_grant_ids?: id:grant[] }` |

替代 soland `/_soland/gate/auth/logout`。**落 `gate` 与 `session-grants` 签发端对称**——撤销与签发是同一 session-grant 资源生命周期的两端,放同段同资源前缀,避免把 logout 拆到 `self` 段而割裂认证生命周期。

空 body 表示撤销当前 request 绑定的 session grant / access token。`target_grant_id` 撤指定 session grant;`target_device_id` 撤销绑定到该 device 的 session grants,但不改变 device authorization;`all_sessions=true` 撤销当前 principal 的所有 active session grants。`target_grant_id`、`target_device_id` 与 `all_sessions` 的组合规则必须在 schema 中闭合:实现 MUST reject 多个互斥 selector 同时出现,也 MUST reject target 不属于当前 principal 的请求。

跨 grant / 跨 device / `all_sessions=true` 请求的 `proof` 与 §3.2 register 使用同一 proof 词汇,并 MUST 绑定 selector、`principal_id`、`request_canonical_digest`、`challenge`、`issued_at` 与 `expires_at`。仅有 bearer access token 不足以撤销其它 device / 全部 session。

> **语义边界**:session_revoke 撤的是 **session grant / access token**,不是设备授权吊销,也不自动发布 durable `ck.account.status`。撤销后的旧 token MAY 在资源请求中表现为 `401 soft_logged_out` / inactive token,但是否发布 `ck.account.status{status="soft_logged_out"}` 属 account lifecycle policy,不得由本 endpoint 隐式伪造。设备吊销是 `ck.device.revoke`(event-kind-registry,正式 event)或 admin 面 `ck.admin.revoke_device`;cursor 撤销是已注册的 `ck.self.account.cursor_revoke`(`/_cokret/self/account/cursor/revoke`)。三者互不复用(收敛自 §6 旧 Q2)。

## 4. Non-goals / 仅迁移、不新增 operation

下列 yougen 现有 `_soland/` 调用**已有协议等价 operation**,只需迁移调用、无需新增:

| 现状(soland 私有) | 应改用(已存在) |
| --- | --- |
| `POST /_soland/self/index/search` | `ck.directory.search_*`(`/_cokret/find/directory/*`) |
| `GET /_soland/self/account/{id}/principal-realm` | `ck.find.directory.resolve_realm` / `resolve_*` |
| `GET /_soland/self/notifications` + `mark-all-read` | `ck.self.account.subscribe`(流式投递)+ `ck.read_cursor.advance`(已读位) |

下列保持**产品私有**,不进本提案(改走 describe 文档发现,不硬编码):

- `consent/cells`(list / grant / revoke)— 产品 consent 模型(注意:consent 的**协议**面是既有 `consent-model.md`,CKP-0013 会处理它与联系人的关系);
- `audit/user-action` — 客户端审计上报;
- `gate/auth/dev-login`、`gate/auth/bridge/describe` — auth bridge,经 describe 引导(`_soland/gate/auth/*` 与本提案 `/_cokret/gate/account/*` 不同子面)。

下列保持 **admin 产品面**(CHANGELOG 2026-06-04),不进协议:

- `/_soland/admin/realms/{id}/notary`、`/_soland/admin/devices/{id}/revoke`、`PATCH /_soland/self/policies/{id}`。

## 5. Migration / 影响 artifact

合入需同步:

- `artifacts/registry/contract-catalog.json` operation_registry(+ 派生 `operation-registry.json`);
- `artifacts/openapi/cokret-service-api.openapi.yaml`(新增 path + schema;`AccountView`、`AccountRegisterRequestBody`、`AccountRegisterOutcome`、`AccountUpdateProfileRequestBody`、`SessionRevokeRequestBody` / response MUST 注册为 schema,不得只留 inline DTO);
- `operations-error-mapping.json`(`invalid_avatar_blob_ref`、`unsupported_profile_patch_path`、`session_grant_not_found`、`session_revoke_selector_conflict` 等错误映射);
- `zh/sync/service-http-binding.md`:`/_cokret/self/account/*` 行扩展 `viewer`/`profile`;`/_cokret/gate/account/*` 行扩展 `register`/`session-grants/revoke`;
- `zh/sync/service-surface.md` Principal Server / Auth Server surface 列表;
- 下游 soland(把上述端点同时挂到 `/_cokret/...` 或迁移)、yougen(改调协议路径 + wire shape)、cotest(契约测试)。

下游迁移必须显式处理以下 wire break,不得只改 URL:

- register:yougen / soland 现状 `{ did, handle, display_name, device_id }` 必须迁移为 `{ principal_id, display_name?, device_id?, proof? }`;`did` → `principal_id`;裸 `handle` 删除。首次 handle 只能经 issuer / coauth 签发的 `ck.schema.handle_claim.v1` 或 claim digest/ref 返回,不得继续由 register body 设置。
- update_profile:yougen / soland 现状 `{ display_name, bio, avatar_url }` 必须迁移为 `{ patch }`;`bio` → `profile_fields.bio`;`avatar_url` 由兼容层上传 / 解析为 Blob 后写 `avatar_blob_ref`,或由客户端直接提交 `avatar_blob_ref`。
- update_profile 副作用:在 §6 Q3 合入前,客户端切到 `/_cokret/self/account/profile` 后仍 MUST 另行保留必要的 `ck.find.directory.announce` / `ck.account_data.set` 调用,以维持可发现 profile 与跨设备头像 / UI state 同步;不得因换端点而静默丢失 directory 可见性或 account-data fan-out。

本提案四项 operation 的核心边界已钉死,可独立合入,直接解 yougen 对 `_soland/self/account/*` 与 `_soland/gate/auth/logout` 的硬编码,不依赖 CKP-0013。`update_profile` 的 directory / account-data fan-out 是否纳入契约仍按 §6 Q3 作为后续增强;在纳入前,该 operation 只承诺更新 server canonical profile。

## 6. Open questions

- **~~Q1~~(已收敛)** `ck.self.account.viewer` 独立 operation,不并入 `describe`——鉴权与缓存语义不同。已写入 §3.1。
- **~~Q2~~(已收敛)** session_revoke **不复用** device revoke:logout 撤 session token,`ck.device.revoke`(正式名,非旧名 `ck.device.revoke`)撤设备授权。已写入 §3.4,落 `gate` 与签发端对称。
- **~~旧 Q4~~(已收敛)** `register` 落 `gate`、proof 与 `session-grants` 同面同词汇,消除双入口。已写入 §3.2。
- **~~Q3~~(已收敛)** `ck.self.account.update_profile` 不隐式 fan-out 到 `ck.find.directory.announce` 或 `ck.account_data.set`;该 operation 只承诺更新 server canonical profile。需要 directory / account-data 同步时,客户端或服务显式调用对应路径。已写入 §3.3 和正式 `zh/sync/service-http-binding.md`。
