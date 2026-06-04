---
ckp: CKP-0012
title: Account Self-Service Operations — close the protocol gaps behind soland's /self/account/*
normative: false
stability: v1
updated: 2026-06-04
status: draft
created: 2026-06-04
authors:
  - chris@acroidea.com
depends_on: []
merged_into: null
---

> **Status: draft.** 本提案尚未合入 normative spec。合入前 operation 注册以 `contract-catalog.json#operation_registry` 为准;本文件只描述设计意图与待决问题。
>
> **范围拆分(2026-06-04):** 本提案原含联系人关系(`ck.contact.*`)。审议发现"联系人 + 找他聊天"横跨 consent / discovery / realm / flow 多个 normative spec,是一份端到端编排提案,已分拆为 **[CKP-0013 Contact & Direct Conversation Lifecycle](./0013-contact-and-direct-conversation-lifecycle.md)**。本提案现只覆盖 **account self-service 四项**,可独立速通,不被联系人设计阻塞。

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
ck.account.describe        ck.account.subscribe       ck.account.cursor_revoke
ck.account.device_pair     ck.account.issue_session_grant
ck.account.oidc_callback   ck.account.agent_key_pair
```

`ck.account.{describe,subscribe}` 是**聚合元数据 / 流式订阅**,不提供:

- "我是谁"的一次性自读(DID / handle / 设备列表 / 账户状态);
- 账户注册、profile 更新;
- 自助 session 注销(logout)。

(联系人关系的建立 / 应答 / 列举同样缺失,但因横跨多个 spec,单列 CKP-0013 处理。)

### 2.2 下游已在用未注册的 `ck.account.*` id

证据表明 soland 实现层早已使用一批未进 catalog 的 operation id:

- yougen [`api/account.rs`](../../../../yougen/src/api/account.rs) 注释:profile 更新 "Mirrors soland's `ck.account.update_profile` wire shape";硬编码 `_soland/self/account/{register,me,profile}`、`_soland/gate/auth/logout`。
- yougen [`api/keys.rs`](../../../../yougen/src/api/keys.rs) 注释:设备吊销 "NOT spec's `ck.admin.revoke_device`"。

即协议与实现已出现**事实漂移**:实现自定义 operation 名,但协议 catalog 不承认。本提案把其中应属协议层的部分正式化,把应属产品层的部分明确划走。

### 2.3 "位置千差万别"问题

非协议 operation 没有 spec 钉死的路径,不同实现可任意放置;通用客户端只能硬编码或逐实现适配。提升为协议 operation 后,`ck.account.viewer` 在任何合规服务器都必定位于 `/_cokret/self/account/viewer`,客户端通过 `/_cokret/describe.supported_operations` 仅需发现"是否支持",无需发现"在哪"。

## 3. Specification(proposed operations)

> **信任段总则**:除 §3.2 `register`、§3.4 `session_revoke` 外,本节 operation 要求 `user_session`(holder-bound)、落 `/_cokret/self/...`、不含版本段。`register` / `session_revoke` 属认证生命周期(账户创建 / 会话撤销),落 `gate` 段并与既有 `session-grants` 共面共 proof 词汇,避免双入口。

### 3.1 `ck.account.viewer` — 自账户一次性读

| 项 | 值 |
| --- | --- |
| HTTP | `GET /_cokret/self/account/viewer` |
| Auth | `user_session` |
| Response | `{ did, handle, state, devices[], profile? }` |

`state` MUST 取 [`account-lifecycle.md`](../zh/identity/account-lifecycle.md) §3 定义的**闭合枚举**(`active` / `locked` / `soft_logged_out` / `suspended` / `deactivated` / `erasure_pending`),不得返回手写子集——viewer 是主体身份的权威自读,枚举漂移会让客户端对账户状态判断与状态机不一致。

替代 soland `/_soland/self/account/me`。命名用 `viewer` 与既有 `describe`(服务能力)区分:`viewer` 返回**主体身份**(holder-bound),`describe` 返回**服务元数据**(可 pre-auth 限流);二者鉴权与缓存语义不同,故独立 operation(见 §6 Q1,已收敛)。

### 3.2 `ck.account.register` — 账户记录创建

| 项 | 值 |
| --- | --- |
| HTTP | `POST /_cokret/gate/account/register` |
| Auth | bootstrap proof:DID-bound signature / paired device proof / 已签发 session grant proof,与 `/_cokret/gate/account/session-grants`(`ck.account.issue_session_grant`)**同一认证面、同一 proof 词汇** |
| Body | `{ did, handle, display_name?, device_id? }` |
| Response | `AccountResponse`(did / handle / state / devices) |

落 `gate` 而非 `self`:register 时账户/会话尚不存在,不满足 `self` 段"本人已认证会话"前提;它与 `session-grants`、`device-pair`、`oidc/callback` 同属认证生命周期入口,应共段、共享 proof 校验路径(收敛自 §6 旧 Q4)。

### 3.3 `ck.account.update_profile` — profile 更新

| 项 | 值 |
| --- | --- |
| HTTP | `POST /_cokret/self/account/profile` |
| Auth | `user_session` |
| Body | `{ display_name?, bio?, avatar_url? }`;`Some("")` 显式清空,`None` 保持不变;`avatar_url` MUST 为 `http(s)://` 或空 |
| Response | `UpdateProfileResponse` |

直接采纳 soland 已用的 `ck.account.update_profile` 名,把事实标准固化。

**与既有投影面的协同(规范前必须钉死,见 §6 Q3)**:yougen 现实现把 profile 更新**同时**镜像到 (a) directory 的可发现 profile、(b) 跨设备 account-data(`client.ui.avatar_blob_ref`)。提案 MUST 明确 update_profile 的副作用边界——它是否触发 `ck.directory.announce`、是否写 `ck.account_data.set`、还是仅更新 server 侧 profile 由客户端各自镜像。在钉死前,本 operation 仅承诺"更新 server 侧 canonical profile",副作用不进契约。

### 3.4 `ck.account.session_revoke` — 自助 logout

| 项 | 值 |
| --- | --- |
| HTTP | `POST /_cokret/gate/account/session-grants/revoke` |
| Auth | `user_session`(撤销当前会话)或带 `target_device_id`(撤销指定设备会话,受 capability 约束) |
| Body | `{ target_device_id?: did, all_devices?: boolean }` |
| Response | `{ revoked: int }` |

替代 soland `/_soland/gate/auth/logout`。**落 `gate` 与 `session-grants` 签发端对称**——撤销与签发是同一 session-grant 资源生命周期的两端,放同段同资源前缀,避免把 logout 拆到 `self` 段而割裂认证生命周期。

> **语义边界**:session_revoke 撤的是 **session token**(对齐 `account-lifecycle.md` 的 `soft_logged_out`),**不是设备授权吊销**。设备吊销是 `ck.device.revoke`(event-kind-registry,正式 event)或 admin 面 `ck.admin.revoke_device`;cursor 撤销是已注册的 `ck.account.cursor_revoke`(`/_cokret/self/account/cursor/revoke`)。三者互不复用(收敛自 §6 旧 Q2)。

## 4. Non-goals / 仅迁移、不新增 operation

下列 yougen 现有 `_soland/` 调用**已有协议等价 operation**,只需迁移调用、无需新增:

| 现状(soland 私有) | 应改用(已存在) |
| --- | --- |
| `POST /_soland/self/index/search` | `ck.directory.search_*`(`/_cokret/find/directory/*`) |
| `GET /_soland/self/account/{id}/principal-space` | `ck.directory.resolve_realm` / `resolve_*` |
| `GET /_soland/self/notifications` + `mark-all-read` | `ck.account.subscribe`(流式投递)+ `ck.read_cursor.advance`(已读位) |

下列保持**产品私有**,不进本提案(改走 describe 文档发现,不硬编码):

- `consent/cells`(list / grant / revoke)— 产品 consent 模型(注意:consent 的**协议**面是既有 `consent-model.md`,CKP-0013 会处理它与联系人的关系);
- `audit/user-action` — 客户端审计上报;
- `gate/auth/dev-login`、`gate/auth/bridge/describe` — auth bridge,经 describe 引导(`_soland/gate/auth/*` 与本提案 `/_cokret/gate/account/*` 不同子面)。

下列保持 **admin 产品面**(CHANGELOG 2026-06-04),不进协议:

- `/_soland/admin/spaces/{id}/anchorer`、`/_soland/admin/devices/{id}/revoke`、`PATCH /_soland/self/policies/{id}`。

## 5. Migration / 影响 artifact

合入需同步:

- `artifacts/registry/contract-catalog.json` operation_registry(+ 派生 `operation-registry.json`);
- `artifacts/openapi/cokret-service-api.openapi.yaml`(新增 path + schema);
- `operations-error-mapping.json`(`invalid_avatar_url` 等错误映射);
- `zh/sync/service-http-binding.md`:`/_cokret/self/account/*` 行扩展 `viewer`/`profile`;`/_cokret/gate/account/*` 行扩展 `register`/`session-grants/revoke`;
- `zh/sync/service-surface.md` Principal Server / Auth Server surface 列表;
- 下游 soland(把上述端点同时挂到 `/_cokret/...` 或迁移)、yougen(改调协议路径)、cotest(契约测试)。

本提案四项语义边界已钉死,可独立合入,直接解 yougen 对 `_soland/self/account/*` 与 `_soland/gate/auth/logout` 的硬编码,不依赖 CKP-0013。

## 6. Open questions

- **~~Q1~~(已收敛)** `ck.account.viewer` 独立 operation,不并入 `describe`——鉴权与缓存语义不同。已写入 §3.1。
- **~~Q2~~(已收敛)** session_revoke **不复用** device revoke:logout 撤 session token,`ck.device.revoke`(正式名,非旧名 `cx.device.revoke`)撤设备授权。已写入 §3.4,落 `gate` 与签发端对称。
- **~~旧 Q4~~(已收敛)** `register` 落 `gate`、proof 与 `session-grants` 同面同词汇,消除双入口。已写入 §3.2。
- **Q3(open)** `ck.account.update_profile` 的副作用是否进契约:是否规范化它对 `ck.directory.announce` 与 `ck.account_data.set` 的触发(§3.3)?在钉死前 update_profile 只承诺更新 server canonical profile。
