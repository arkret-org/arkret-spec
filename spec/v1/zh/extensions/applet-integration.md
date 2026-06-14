---
title: Applet Integration
status: candidate
normative: true
stability: v1
updated: 2026-06-10
---

> **状态：extension profile（非 v1 core 互操作必需）**。Applet registry、审核 SLA 与 capability
> 注入流程仍在演进。Cokret v1 core 互操作 **不要求** 实现本 profile；声称 v1 core 的
> 实现可以完全不接 Applet，仅通过 capability + actor 模型表达 bot / bridge / agent。
> `ck.profile.applet_service.v1` 视为可选 extension（见 `artifacts/profiles/conformance-profiles.json`
> 的 `profile_tiers.extension_profile_implementation`）。Applet v1 家族用 `inherits` 分层:
> base bot-only 使用 `ck.profile.applet_service.v1`，bridge / delegated / E2EE join / widget
> 分别通过 `ck.profile.applet_bridge.v1`、`ck.profile.applet_delegated.v1`、
> `ck.profile.applet_e2ee_join.v1`、`ck.profile.applet_widget.v1` 叠加。

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Matrix 有 Application Service / Appservice，用于桥接 IRC、Slack、Discord 等外部网络，也用于 bot 和自动化集成。Cokret 需要类似能力，但不能继承 homeserver 中心化和 user_id namespace 的假设。

Cokret 将该能力定义为 **Applet**。

Applet 是一个受注册、受授权、可审计的集成服务。它可以：

- 作为 bot 参与 Realm
- 桥接外部网络
- 创建和管理 Ghost Actor
- 管理 portal realm
- 接收 Cokret 事件交易
- 把外部事件转换为 Cokret event
- 在获得明确授权时以受托 agent / device 方式执行操作

Applet / Agent / Morph / Ghost Actor 的选择边界如下，实现 MUST 按最窄概念建模：

| 场景 | 首选模型 | 不应使用 |
| --- | --- | --- |
| 高频外部事件桥接、多用户镜像、需要 namespace / capability 撤销 / portal Realm | Applet + Ghost Actor | Morph 直接表示外部用户；Agent session 长期常驻 |
| 单次或低频外部对象导入、内容不可信、只需保留原文与映射证据 | Morph / Relation | Ghost Actor 写入协作历史 |
| AI / 自动化长任务、需要状态回流、产物归档、可取消会话 | Agent protocol session | Applet masquerading 成人类 actor |
| 外部人类用户在 Cokret 内可被 mention / 授权 / 审计 | Ghost Actor（标记 managed_by_applet） | 伪装为 native principal DID |

同一外部实体可以在不同上下文下产生 Morph 记录和 Ghost Actor，但二者 MUST 通过显式 Relation / provenance 字段连接，不能让 projection 自由猜测它们是同一主体。

## 2. 与 Matrix Appservice 的对应关系

| Matrix Appservice | Cokret Applet |
| --- | --- |
| homeserver 本地注册文件 | signed `applet_registration` |
| sender localpart | applet controller DID / bot DID |
| user namespace regex | actor namespace claim / DID namespace |
| room namespace regex | Realm / portal namespace |
| alias namespace regex | handle / portal alias namespace |
| `/transactions/{txn_id}` | `POST /_cokret/edge/applet/transactions` + `Idempotency-Key` header |
| `/users/{user_id}` | `/_cokret/edge/applet/actors/{actor_id}` |
| `/rooms/{room_alias}` | `/_cokret/edge/applet/realms/{realm_id_or_alias}` |
| third-party protocols | external protocol metadata |
| appservice masquerading | delegated agent / Ghost Actor capability |

关键差异：

- Applet 不自动拥有全网权限。
- Applet 的每个写入仍需签名和 capability。
- Applet namespace 只表示“该 Applet 可声明或接收这些对象”，不等于权限通过。
- Ghost Actor 必须是可审计 Actor，MUST NOT 伪装成人类 DID。

## 3. 角色

### 3.1 Applet Service

运行集成逻辑的服务端进程。它有自己的 service DID。

### 3.2 Applet Controller

管理该 Applet 的主体，通常是组织、开发者或企业管理员。

### 3.3 Bot Actor

Applet 的主要可见 Actor。Bot Actor 可以加入 Realm、被 mention、发送消息或执行自动化。

### 3.4 Ghost Actor

外部网络用户在 Cokret 中的镜像 Actor。例如 Slack 用户 `U123` 映射为一个独立 Actor DID：

```text
did:web:slack-bridge.example:ghost:u123
```

`#fragment` 只用于 DID URL 形式的 verification method（例如 `did:web:slack-bridge.example:ghost:u123#key-1`），不得作为 `actor_id` / `bot_actor_id` 的一部分。

Ghost Actor MUST 带有 `accountable_principal_ids`（指向 Applet controller 与外部 service DID），外部网络来源（protocol / network id / user id）记录在 `profile_fields.external_ref`。问责字段以 actor-profile schema 的 `accountable_principal_ids` 为唯一权威形态（见 [`applet-schema.md`](./applet-schema.md) 与 §9）；旧的 `accountability` 嵌套对象不是合法 wire 形态。

#### 3.4.1 Ghost Actor vs Native Personal Agent 边界

`actor_kind` 不定义 `agent_native`、`agent_ghost` 或 `ghost` wire enum。Native personal AI agent 使用 `actor_kind="agent"`；Applet-managed Ghost Actor 使用现有 enum 中最贴合其主体类型的值：外部人类/账号镜像 SHOULD 使用 `actor_kind="integration"`，Applet 托管的 AI/automation ghost MAY 使用 `actor_kind="agent"`。二者必须通过 Applet provenance、`accountable_principal_ids` 和 profile/capability 约束与 native personal agent 区分，不能依赖新增 `actor_kind` 值区分。

Native personal AI agent(由 controller 通过 `ck.self.agent.command.provision` 创建，见 [`../identity/key-management.md` §3.6.1](../identity/key-management.md))与 Applet-managed Ghost Actor(本节)是两类不同 actor,生命周期与治理路径完全分离:

| 维度 | Native personal agent | Applet-managed Ghost Actor |
| --- | --- | --- |
| 创建路径 | `ck.self.agent.command.provision` operation,fan-out `ck.profile.create` / `ck.identity.accountability_grant` / `ck.agent.key.authorize` / `ck.capability.grant` | `ck.applet.registration` + Applet bot/Ghost Actor 注册 |
| `accountable_principal_ids` | 指向 controller principal,显式 `ck.identity.accountability_grant` | 指向 Applet controller / 外部系统 |
| Runtime credential | 通过 `POST /_cokret/gate/account/agent-key-pair` pairing 得到 `ck.agent.key.authorize` 绑定的 key | Applet 管辖，通常是 Applet service DID + HTTP signature |
| Session 路径 | `POST /_cokret/gate/account/session-grants` + `proof.proof_kind="agent_key_proof"` | Applet `ck.edge.applet.command.transaction` 与 Applet 的 delegated session |
| 撤销 | `ck.self.agent.command.pause` / `ck.self.agent.command.deactivate` + fan-out key/grant revoke | Applet registration 撤销;Ghost Actor 跟随 Applet 生命周期(经 §4b Revoke,`remove_ghost_membership` 需 active ghost projection 完整否则 MUST fail closed) |
| Realm policy | Realm policy MUST 单独允许 native personal agent(`ck.profile.personal_agent_provisioning.v1`) | Realm policy MUST 单独允许 Applet base bot-only(`ck.profile.applet_service.v1`)；Ghost Actor / portal bridge 需额外声明 `ck.profile.applet_bridge.v1` |

**Realm policy MUST 至少能分别控制 native personal agent 与 Applet / Ghost Actor**:部署可以禁止普通用户创建或使用 personal agents 同时允许管理员安装的 Applet + Ghost Actor,也可以反向配置;**二者不得被合并为一个不可区分的 "automation allowed" 开关**。

`ck.profile.personal_agent_provisioning.v1` / `ck.profile.agent_sidecar_thread.v1` 只覆盖 native personal agent 路径;Ghost Actor / Applet Bot Actor 不走 personal agent provisioning 或 sidecar thread profile。

### 3.5 Portal Realm

外部网络 location 在 Cokret 中的镜像 Realm。例如 Slack channel、Discord guild channel、GitHub issue discussion。

## 4. Applet Registration

Applet MUST 有签名 registration。它可以由 Realm owner、组织管理员、registry 或 authz service 接受。

Applet 进入某个 Realm 的 capability MUST 由该 Realm owner、Realm admin 或 Realm policy 明确授权的 registry/authz service 签发。仅凭 Applet 自签 registration、namespace claim 或外部 registry 收录不得写入 Realm；缺少该 grant 时，任何 Applet 通过 transaction push、Event submit 或 delegated signing 引入的 Realm 写入 MUST 拒绝，reason=`applet_registration_unauthorized`。

**机读授权门(normative)**：上述"由 Realm owner/admin/authz 授权 install / grant"绑定到机读 capability gate——`ck.applet.registration` 是 `ck.realm.admin` capability action 的目标 event kind(见 [`capability-action-registry.json`](../../artifacts/registry/capability-action-registry.json) 中 `ck.realm.admin.target_event_kinds`)。提交 `ck.applet.registration`(及随附 grant fan-out)的 actor MUST 持有覆盖目标 Realm 的 active `ck.realm.admin` grant(或 Realm policy 明确授权的 authz service 等价授权);reducer 校验失败时 MUST 拒绝,reason=`applet_registration_unauthorized`。`ck.applet.registration` 在数据面仍是 `service_attested`(注册载体真实性),`ck.realm.admin` 门控的是"谁有权安装",二者并存:注册被服务背书不等于被授权安装。

示例：

```json
{
  "kind": "ck.applet.registration",
  "applet_id": "ck:applet:21532600-0000-7000-8000-000000000000",
  "service_did": "did:web:slack-bridge.example",
  "controller_did": "did:webvh:z2dmjQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn:acme.example",
  "base_url": "https://slack-bridge.example/applet",
  "bot_actor_id": "did:web:slack-bridge.example:bot",
  "protocols": [
    "slack"
  ],
  "namespaces": {
    "actors": [
      {
        "exclusive": true,
        "pattern": "did:web:slack-bridge.example:ghost:*"
      }
    ],
    "realms": [
      {
        "exclusive": true,
        "pattern": "slack:team:*:channel:*"
      }
    ],
    "handles": [
      {
        "exclusive": true,
        "pattern": "slack.acme.example/*"
      }
    ]
  },
  "receive_events": true,
  "receive_ephemeral": false,
  "rate_limited": true,
  "requested_scopes": [
    "ck.realm.discover",
    "ck.object.read",
    "ck.strand.create",
    "ck.morph.create",
    "ck.message.create",
    "ck.relation.create"
  ],
  "registration_epoch": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "webhook_auth": {
    "type": "http_message_signature",
    "key_ref": "did:web:slack-bridge.example#server-key-1"
  },
  "proof": {
    "kind": "detached_jws",
    "alg": "EdDSA",
    "verification_method": "did:webvh:z2dmjQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn:acme.example#admin-key-1",
    "payload_digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "created_at": "2026-04-26T00:00:00Z",
    "jws": "..."
  },
  "created_at": "2026-04-26T00:00:00Z"
}
```

### 4.1 Registration 规则

- `applet_id` MUST 稳定。
- `service_did` MUST 可解析，并声明 Applet endpoint。
- `controller_did` MUST 对 registration 签名。
- `namespaces` MUST 明确声明，不能默认为全网。
- exclusive namespace 冲突时，registry / authz service MUST 拒绝后注册者。
- `requested_scopes` 只是请求权限，不是实际授权。
- 实际权限 MUST 通过 capability grant 授予。
- `registration_epoch` MUST 进入 payload required 字段，并覆盖 canonical derived registration、service DID Document digest/version evidence、accepted signing key set、endpoint/auth material。grant 存储与匹配只绑定该 epoch；reducer/verifier 仍 MUST 展开 epoch evidence，校验当前 DID Document digest / signing key 与 epoch 捕获值一致。
- `proof` MUST 是 controller DID detached proof，覆盖 canonical registration object（不含 `proof` 自身）；空对象 MUST 以 `schema_violation` 拒绝。

## 4a. Applet Package 与安装聚合操作

开发者发布 Applet 时 SHOULD 发布 controller-signed **Applet Package**。Package 是分发对象，不是 Realm history event；进入协议事实前 MUST 派生为 `ck.applet.registration` payload，并由 Realm owner/admin/authz service 通过安装聚合操作签发实际 grant。

Package 最小字段以 [`applet-schema.md` §1a](./applet-schema.md#1a-applet-package-schema) 的字段参考表为唯一规范源；本节不重复维护字段表。Package MUST NOT 自行授权写入 Realm。Package 接受、registry 收录、namespace claim 或 `requested_scopes[]` 出现某 action 都不得被 reducer 解释为 grant。`registration_epoch` MUST 随 claimed profiles、namespace、base URL、webhook auth、endpoint key、requested scopes、widget origin、E2EE request、receive/rate-limit 行为或 DID/key evidence 改变而改变。

Package -> registration 派生映射同样以 [`applet-schema.md` §1a](./applet-schema.md#1a-applet-package-schema) 的映射表为唯一规范源。本节只补充安装语义：派生出的 registration 成功写入仍不授权；只有随后签发的 grant 与 `(applet_id, effective_scope, registration_epoch)` 绑定并保持 active，Applet 才取得对应 scope 的 effective install。

## 4b. Install Preview / Commit / Revoke

Applet 安装使用 self/admin aggregate operation。它不创建 install 专用 durable Event；它 fan-out 的协议事实仍是 `ck.applet.registration`、`ck.capability.grant`、`ck.profile.create`、`ck.member.state`、E2EE join authorization / MLS commit requirement、widget scoped token policy 等既有对象。

新增 operation:

| operation_id | HTTP | 语义 |
| --- | --- | --- |
| `ck.self.applet.install.command.preview` | `POST /_cokret/self/applets/install/preview` | 只读预览，返回 canonical `InstallPlan` 与 `plan_digest`。 |
| `ck.self.applet.command.install` | `POST /_cokret/self/applets/install` | 提交安装，必须带 `Idempotency-Key` 与 preview 得到的 `plan_digest`。 |
| `ck.self.applet.command.revoke` | `POST /_cokret/self/applets/{applet_id}/revoke` | 撤销 effective install。 |

`effective_scope` 是单次 install 的唯一目标:

- `kind="realm"` MUST 只包含 `kind` 与 `realm_id`，并约束为 Realm-wide grant。
- `kind="circle"` MUST 同时包含 `kind`、`realm_id` 与 `circle_id`，并约束为该 Circle grant；不得由 Circle install 推导 Realm-wide grant。
- 单次 install operation 只处理一个 `effective_scope`。多 Realm、多 Circle 批量安装和跨 sovereign server 的 install 事务聚合不是 v1 目标。
- install preview/commit MUST 由目标 Realm 的 controlling Principal Server 或 Realm policy 明确授权的 authz service 承载；联邦投递只传播 fan-out 后的正式 events，不把 install operation 本身变成跨 server 分布式事务。
- install commit 的授权门是机读 `ck.realm.admin` capability(§4)：commit 提交的 admin actor MUST 持有覆盖目标 Realm 的 active `ck.realm.admin` grant(或 Realm policy 授权的等价 authz service);fan-out 出的 `ck.applet.registration` 是该 capability action 的目标 event kind。reduce-time 缺少该授权时 MUST fail closed,reason=`applet_registration_unauthorized`,且整个 install 标记 rejected(无 effective install)。

Preview MUST fail closed when controller proof 无效、DID Document 不可解析或 key ref 不匹配、namespace pattern 非法、exclusive namespace 与 active install 冲突、requested action 不在 capability registry、effective_scope 所属 Realm policy 禁止 Applet/Ghost Actor/widget/E2EE、或 package 已过期。

Commit MUST:

- 在 fan-out 前持久化 install execution record:`(principal_service_id, admin_actor_id, Idempotency-Key, body_hash, submitted_plan_digest, status, produced_event_refs[])`。
- 对同一 `Idempotency-Key` + 同一 body canonical hash 重试返回同一结果和同一批 accepted event refs；同一 key + 不同 body MUST 返回 `duplicate_conflict`。
- 每个 fan-out step 提交前先记录 `step_index`、canonical event body hash、目标 event kind 与 `pending` 状态；accepted 后先把 event ref 写回 record，再继续后续 fan-out 或响应客户端。若进程在 submit accepted 与 ref 写回之间崩溃，重试 MUST 先按 deterministic event id 或 canonical body hash 查询是否已有 accepted event，补写 ref 后继续，不得直接重提。
- 重新计算 plan；不得盲信客户端传回的 `InstallPlan`。
- 将 package requested scopes、commit `approved_scopes`、当前 Realm/Circle policy 取交集后生成候选 Approved Capability Set。`approved_scopes` 是管理员意图，不是 grant truth。
- 当 recomputed plan canonical `plan_digest` 与提交的 `plan_digest` 不一致时 MUST fail closed，返回 `applet_install_plan_mismatch`，并要求管理员重新 preview/approve。

多事件 fan-out 不是分布式原子事务；安全性依赖 registration 无 grant 即无授权。preview-time reject MUST NOT 提交任何 durable event。reduce-time reject MUST 把 accepted refs 与 rejected refs 写入 install execution record 和 audit/projection。registration 成功但所有 grant 失败时 MUST 返回 rejected，标记 registration 无 effective install，并在 local projection / audit 显式显示 orphan registration。

Revoke MUST revoke all active grants bound to applet + effective_scope + registration_epoch, revoke widget scoped token, revoke delegated session/device（若有），并在需要时触发 bot/ghost membership leave/remove 与 MLS epoch rotation requirement。`remove_ghost_membership` 依赖 active ghost projection 能枚举该 effective_scope 下仍 active 的 applet-managed ghost member；若 projection 不完整，MUST fail closed 并要求先重建 projection，不得按 namespace pattern 猜测成员。revoked effective install 继续尝试未来写入或调用 MUST fail closed，reason=`applet_revoked` 或更细 reason。

### 4b.1 术语:Effective Install 与 Orphan Registration

- **effective install**(有效安装):一个 `ck.applet.registration` 在某 `effective_scope`(Realm 或 Circle)上，至少绑定一个 active `ck.capability.grant` 到同一 `(applet_id, effective_scope, registration_epoch)`。只有进入 effective install,Applet 才在该 scope 取得任何写入 / 调用授权;registration 自身不授权(见 §11 与 [`applet-schema.md`](./applet-schema.md) `requested_scopes` 说明)。
- **orphan registration**(孤儿注册):registration 已成功写入，但同一 `(applet_id, effective_scope, registration_epoch)` 下没有任何 active grant(commit 时全部 grant 失败，或 grant 事后被全部 revoke)。orphan registration MUST 被标记为无 effective install,并在 local projection / audit 显式显示；它不授予任何能力。
- 这与 install commit 响应的 `effective_status` 三值对应:`installed`(registration + 完整 grant 集合)、`partially_installed`(registration + 部分 grant,其余 rejected)、`rejected`(registration 成功但无任何 active grant ⇒ orphan registration)。

## 5. Namespace

Namespace 用于决定：

- 哪些未知 actor 可以向 Applet 查询
- 哪些 Realm / portal alias 属于 Applet
- 哪些事件应推送给 Applet
- Applet 可以为哪些 Ghost Actor 申请或声明身份

Namespace 不等于 capability。  
Namespace 命中只表示“这个 Applet 是该名称空间的处理方”。

### 5.1 Actor Namespace

Actor namespace 适用于 Ghost Actor 和 Bot Actor。

```json
{
  "exclusive": true,
  "pattern": "did:web:slack-bridge.example:ghost:*"
}
```

### 5.2 Realm Namespace

Realm namespace 适用于 portal Realm。

```json
{
  "exclusive": true,
  "pattern": "slack:team:*:channel:*"
}
```

### 5.3 Handle Namespace

Handle namespace 适用于外部用户或 location 的人类入口。

```json
{
  "exclusive": false,
  "pattern": "slack.acme.example/*"
}
```

## 6. Applet Capability

注册 Applet 后，Realm owner 或组织管理员 MUST 显式授予 capability。

示例：

```json
{
  "issuer": "did:webvh:z2dmjQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn:acme.example",
  "subject": "did:web:slack-bridge.example:bot",
  "claim_scope": {
    "realm_ids": [
      "ck:realm:0196419b-0000-7000-8000-000000000000"
    ],
    "actions": [
      "ck.strand.create",
      "ck.morph.create",
      "ck.message.create",
      "ck.relation.create"
    ]
  },
  "constraints": [
    {
      "constraint_type": "scope_limitation",
      "effect": "allow",
      "allowed_data_classes": ["public", "internal"]
    }
  ],
  "expires_at": "2026-07-26T00:00:00Z"
}
```

constraint 内 MUST 只使用 [`authz/constraint-schema.md`](../authz/constraint-schema.md) 登记的 `scope_limitation` 字段（如 `allowed_data_classes` / `allowed_endpoints` / `allowed_*_container_refs` 等）。该 capability 与具体 applet 的绑定不写在 constraint 里，而是由 §5.1 registration 的 `namespaces.actors[].pattern`（声明可代理的 ghost actor 命名空间）与 §11 delegated agent 的 `applet_id` / `authorization_ref` 在 Event 层校验。

除非 Applet 拥有 effective grant，或以委托授权身份显式代表已授权 actor 行事（此时 MUST 满足 [§11](#11-masquerading-与-delegated-agent) delegated agent 的全部字段 `executed_by` / `authorization_ref` / `applet_id` 与对应 reducer 校验），否则 Applet MUST NOT 向 Realm 写入。

## 7. Applet API

Applet API 是 Cokret 节点调用 Applet 的接口。  
Applet 调用 Cokret 节点时使用常规 Events API / Sync Service / authz API。

Base URL 来自 registration 的 `base_url`。

**`ck.applet.*` 标识符的两类用途（normative 区分）**：`ck.applet.*` 前缀的标识符根据上下文分属两个互不混淆的命名空间，实现不得把二者当作同一对象：

- **Event kind（进 Realm history）**：`ck.applet.registration`、`ck.applet.interop_session.start`、`ck.applet.interop_session.status`、`ck.applet.bridge_error`。这些是 durable Cokret Event，进入 Realm history，由 reducer 按 schema 校验；payload 字段以 `artifacts/schemas/event-payload.schema.json`（`applet_interop_session_start_payload` / `applet_interop_session_status_payload`，`ck.applet.bridge_error` 见 `applet-schema.md` §7）为权威。
- **operation_id（HTTP，不进 history）**：本节表中的 `ck.edge.applet.query.ping`、`ck.edge.applet.query.describe`、`ck.edge.applet.command.transaction`、`ck.edge.applet.actor.query.resolve`、`ck.edge.applet.realm.query.resolve`、`ck.edge.applet.query.protocol_metadata`、`ck.edge.applet.third_party_users.query.list`、`ck.edge.applet.third_party_locations.query.list`、§4b 的 `ck.self.applet.install.command.preview` / `ck.self.applet.command.install` / `ck.self.applet.command.revoke` 以及 §9.1 的 `ck.self.applet.ghost.command.provision` 是 HTTP API operation 标识符，只描述 Cokret 节点 ↔ Applet 或 self/admin aggregate operation 的请求/响应绑定，本身不是 wire Event，不进入 Realm history。

`ck.edge.applet.command.transaction` 在 v1 artifacts 中只作为 operation_id 存在，指 §7.3 的 transaction push HTTP 调用；它 MUST NOT 作为 durable Event kind 或 transaction-origin Event 写入 Realm history。transaction push 的幂等记录属于 Applet service / transport audit log；Applet 写入 Cokret 的事实由具体 Event Envelope 的 signed `applet_id`、`external_ref`、`authorization_ref`、event signature 与 capability grant 表达。

字段级接口索引：

本表 **surface / 调用方向** 列区分两类 operation:`edge`（节点 → Applet，鉴权主体为 Cokret 节点，路径 `/_cokret/edge/applet/...`）与 `self`（管理员 → 自有 Principal Server aggregate，鉴权主体为管理员 actor，路径 `/_cokret/self/applets/...`）。二者调用方向相反、鉴权主体不同，实现不得套用同一鉴权模型。

| operation_id | surface / 调用方向 | 必填字段 | 可选字段 | 响应字段 | 约束 |
| --- | --- | --- | --- | --- | --- |
| `ck.edge.applet.query.ping` | edge（节点→Applet） | 无 | 无 | `ok: boolean`; `applet_id: id`; `service_did: did`; `protocol_version: string` | 可公开，但不得泄露 private namespace。 |
| `ck.edge.applet.query.describe` | edge（节点→Applet） | 无 | 无 | `applet_id: id`; `service_did: did`; `protocols: string[]`; `namespaces: object`; `limits: object`; `auth: object` | public mode 只返回公开 capabilities。 |
| `ck.edge.applet.command.transaction` | edge（节点→Applet） | `header.Idempotency-Key: string`; `source_service_did: did`; `events: EventEnvelope[]` | `ephemeral: object[]` | `ok: boolean`; `rejected: object[]?`; `retry_after_ms: int?` | Applet MUST 验证来源 service DID、HTTP signature、event signature、namespace 和 capability。 |
| `ck.edge.applet.actor.query.resolve` | edge（节点→Applet） | `path.actor_id: did` | 无 | `exists: boolean`; `actor_id: did?`; `display_name: string?`; `external_ref: object?` | actor_id 必须命中 Applet actor namespace。 |
| `ck.edge.applet.realm.query.resolve` | edge（节点→Applet） | `path.realm_id_or_alias: string` | 无 | `exists: boolean`; `realm_id: id?`; `title: string?`; `external_ref: object?` | 必须命中 portal namespace 或授权查询。 |
| `ck.edge.applet.query.protocol_metadata` | edge（节点→Applet） | `path.protocol: string` | 无 | `protocol: string`; `display_name: string`; `icon_blob_ref: string?`; `field_types: object`; `instances: object[]?`（entry: `instance_id`, `display_name`） | instance list 可要求授权。 |
| `ck.edge.applet.third_party_users.query.list` | edge（节点→Applet） | `query.protocol: string`; 外部 ID query 字段 | 无 | `actor_id: did?`; `exists: boolean`; `external_ref: object?` | 查询字段必须在 registration namespace 内。 |
| `ck.edge.applet.third_party_locations.query.list` | edge（节点→Applet） | `query.protocol: string`; 外部 ID query 字段 | 无 | `realm_id: id?`; `exists: boolean`; `external_ref: object?` | 查询字段必须在 portal namespace 内。 |
| `ck.self.applet.install.command.preview` | self（管理员→Principal Server） | `applet_package`; `effective_scope`; `approval_request`（字段见 [`applet-schema.md` §1b](./applet-schema.md)） | 无 | `InstallPlan` + `plan_digest`（契约 `applet-install-plan.schema.json`） | 只读预览；字段定义见 §4b 与 `applet-schema.md` §1b。 |
| `ck.self.applet.command.install` | self（管理员→Principal Server） | `Idempotency-Key`; `plan_digest`; `applet_package`; `effective_scope`; `approval_request`（见 [`applet-schema.md` §1b](./applet-schema.md)） | 无 | install / commit response 的完整 required 字段集合以 [`applet-schema.md` §1b](./applet-schema.md) 与契约 `applet-install-operations.schema.json` 为权威源（本表不再部分罗列） | 提交安装；字段定义见 §4b 与 `applet-schema.md` §1b。 |
| `ck.self.applet.command.revoke` | self（管理员→Principal Server） | `path.applet_id`; `effective_scope` | 无 | revoke 结果（撤销的 grant / membership / token refs） | 撤销 effective install;见 §4b。 |
| `ck.self.applet.ghost.command.provision` | self（已安装 Applet service→Principal Server） | `header.Idempotency-Key`; `path.applet_id`; `schema`; `applet_id`; `service_did`; `ghost_actor_id`; `protocol`; `tenant`; `external_user_id`; `realm_id`; `external_ref` | `display_name` | `ghost_actor_id: did`; `profile_event_ref: ref`; `accountability_grant_ref: ref`; `authorization_ref: ref`; `display_name: string?` | bridge Applet 为单个外部用户 provision Ghost Actor;字段与幂等规则见 §9.1,契约 `applet-ghost-operations.schema.json`。 |

### 7.1 Ping

```text
GET /_cokret/edge/applet/ping
```

返回：

```json
{
  "ok": true,
  "applet_id": "ck:applet:21532600-0000-7000-8000-000000000000",
  "service_did": "did:web:slack-bridge.example",
  "protocol_version": "1.0"
}
```

### 7.2 Describe

```text
GET /_cokret/edge/applet/describe
```

返回 Applet 支持的协议、profile、namespace、最大交易大小和认证方式。

### 7.3 Transaction Push

```text
POST /_cokret/edge/applet/transactions
Idempotency-Key: <opaque-string>
```

Cokret Sync Service / Events API 向 Applet 推送事件批次。

请求示例（非完整 schema）：

```json
{
  "source_service_did": "did:web:server.example",
  "events": [
    {
      "event_id": "ck:event:019640ed-8000-7000-8000-000000000000",
      "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
      "kind": "ck.message.create",
      "actor_id": "did:web:alice.example",
      "payload": {}
    }
  ],
  "ephemeral": [
    {
      "type": "typing",
      "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
      "actor_id": "did:web:alice.example"
    }
  ]
}
```

响应示例（非完整 schema）：

```json
{
  "ok": true
}
```

规则：

- `Idempotency-Key` MUST 幂等。
- 相同 `(source_service_did, Idempotency-Key)` 和相同 body canonical hash 重复投递 MUST 成功。
- 相同 `(source_service_did, Idempotency-Key)` 但 body 不同 MUST 返回 `duplicate_conflict`。
- 单事件级别仍以 `event_id` 去重；重复 `event_id` 且内容一致 MUST `accepted`，内容不一致 MUST 拒绝。
- Applet SHOULD 先持久化幂等记录，再执行外部副作用。
- Applet MUST 验证 source service DID 和 HTTP message signature。
- Applet MUST 独立验证 event signature，不得只信任推送方。

### 7.4 Query Actor

```text
GET /_cokret/edge/applet/actors/{actor_id}
```

用于 Cokret 节点发现 namespace 内的未知 Ghost Actor 是否存在。

返回：

```json
{
  "exists": true,
  "actor_id": "did:web:slack-bridge.example:ghost:u123",
  "display_name": "Alice on Slack",
  "external_ref": {
    "protocol": "slack",
    "network_id": "T123",
    "user_id": "U123"
  }
}
```

若不存在，返回 `404 not_found`。

### 7.5 Query Realm

```text
GET /_cokret/edge/applet/realms/{realm_id_or_alias}
```

用于查询 portal Realm 是否存在或可创建。

返回：

```json
{
  "exists": true,
  "realm_id": "ck:realm:c0c69410-0000-7000-8000-000000000000",
  "title": "#release on Slack",
  "external_ref": {
    "protocol": "slack",
    "network_id": "T123",
    "location_id": "C456"
  }
}
```

### 7.6 Protocol Metadata

```text
GET /_cokret/edge/applet/protocols/{protocol}
```

返回：

```json
{
  "protocol": "slack",
  "display_name": "Slack",
  "icon_blob_ref": "ck:blob:sha256:...",
  "field_types": {
    "team": {
      "label": "Workspace",
      "type": "string"
    },
    "channel": {
      "label": "Channel",
      "type": "string"
    }
  },
  "instances": [
    {
      "instance_id": "T123",
      "display_name": "Acme Slack"
    }
  ]
}
```

### 7.7 Third-Party Lookup

```text
GET /_cokret/edge/applet/third_party/users?protocol=slack&team=T123&user=U123
```

```text
GET /_cokret/edge/applet/third_party/locations?protocol=slack&team=T123&channel=C456
```

用于把外部用户或 location 映射到 Cokret actor / portal Realm。

## 8. Applet 写入 Cokret

Applet 写入 Cokret MUST 使用常规 `/_cokret/self/events` submit 接口。

每个 Applet-originated 写入 Event MUST 包含下列 signed Event Envelope 字段（这些字段均进入 `proof.event_digest`；不得只放在 `unsigned` 中）：

- `actor_id`
- `applet_id`
- `external_ref`，若来自外部网络
- `authorization_ref`
- `proofs[]`

示例：

```json
{
  "event_id": "ck:event:019640ed-8000-7000-8000-000000000000",
  "realm_id": "ck:realm:c0c69410-0000-7000-8000-000000000000",
  "actor_id": "did:web:slack-bridge.example:ghost:u123",
  "actor_seq": 17,
  "kind": "ck.message.create",
  "applet_id": "ck:applet:21532600-0000-7000-8000-000000000000",
  "authorization_ref": "ck:grant:0196410c-0000-7000-8000-000000000000",
  "external_ref": {
    "protocol": "slack",
    "network_id": "T123",
    "event_id": "1714040000.000100"
  },
  "created_at": "2026-04-26T00:00:01Z",
  "prev_refs": [],
  "refs": [],
  "payload": {
    "strand_id": "ck:strand:c0c69410-0000-7000-8000-000000000001",
    "track_name": "discussion",
    "content": {
      "kind": "ck.content.text",
      "body": "hello from Slack"
    }
  },
  "proofs": [
    {
      "kind": "detached_jws",
      "alg": "EdDSA",
      "verification_method": "did:web:slack-bridge.example:ghost:u123#key-1",
      "event_digest": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "created_at": "2026-04-26T00:00:01Z",
      "jws": "a..b"
    }
  ]
}
```

`external_ref` 是 bridge / 外部网络 provenance 与幂等审计材料。若用于回环防护、外部消息去重、moderation audit 或用户可见出处，Producer MUST 使用 Event Envelope 顶层 signed `external_ref`；`unsigned.external_ref` 只能承载可丢弃的本地 hint，MUST NOT 作为安全决策输入。

## 9. Ghost Actor

Ghost Actor MUST 与原生人类 Actor 在协议层可区分。

Ghost Actor profile SHOULD 包含（以下为 schema 合法形态；字段与约束**以 artifacts 的 [`actor-profile.schema.json`](../../artifacts/schemas/actor-profile.schema.json) 为准**）：

```json
{
  "id": "ck:actor_profile:21532600-0000-7000-8000-000000000000",
  "schema": "ck.schema.actor_profile.v1",
  "principal_id": "did:web:slack-bridge.example:ghost:u123",
  "actor_kind": "integration",
  "display_name": "Alice on Slack",
  "accountable_principal_ids": [
    "did:webvh:z2dmjQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn:acme.example",
    "did:web:slack-bridge.example"
  ],
  "profile_fields": {
    "managed_by_applet": "ck:applet:21532600-0000-7000-8000-000000000000",
    "external_ref": {
      "protocol": "slack",
      "network_id": "T123",
      "user_id": "U123"
    }
  },
  "created_at": "2026-04-30T00:00:00Z"
}
```

`actor-profile.schema.json` 是 `additionalProperties:false` 的封闭 schema:`id`、`schema`、`principal_id`、`actor_kind`、`display_name`、`created_at` 为 required;问责只能通过 `accountable_principal_ids`(controller principal + 外部 service DID)表达;Applet 托管标记 `managed_by_applet` 与外部网络来源 `external_ref` MUST 放入开放容器 `profile_fields`,不得作为顶层字段(否则被 schema `schema_violation` 拒绝)。与 §3.4 / §3.4.1 一致，不存在 `accountability` 嵌套对象 wire 形态。

Ghost Actor MUST NOT 被静默合并到 native DID，除非 native holder 显式声明并完成绑定。

### 9.1 Ghost Actor Provisioning（`ck.self.applet.ghost.command.provision`，normative）

bridge Applet 第一次遇到某个外部用户（典型触发：该用户在外部网络发出第一条需要桥接的消息）时，通过

```text
POST /_cokret/self/applets/{applet_id}/ghosts/provision
Idempotency-Key: <opaque-string>
```

请求 Principal Server 为该外部用户铸造 Ghost Actor。请求/响应契约以 [`applet-ghost-operations.schema.json`](../../artifacts/schemas/applet-ghost-operations.schema.json) 为权威（封闭 schema）；请求 `schema` 固定为 `ck.applet.ghost_actor.provision_request.v1`。

规则：

- 调用方 MUST 以 applet registration 的 service DID 认证；服务端 MUST 校验 `applet_id` 存在 active install、caller service DID 与 registration 一致、`ghost_actor_id` 命中 registration 的 actor namespace、`realm_id` 在 effective scope 内。任一不满足 MUST fail closed（`applet_namespace_mismatch` / `applet_registration_unauthorized`）。
- 成功时服务端铸造并返回 durable refs：Ghost Actor 的 `ck.profile.create`（按 §9 的 actor-profile 封闭形态，`accountable_principal_ids` 指向 Applet controller 与外部 service DID）与 `ck.identity.accountability_grant`；`authorization_ref` 是后续该 ghost 署名 Event Envelope 顶层 MUST 携带的授权引用（见 §8、§11）。
- **幂等（normative）**：同一 `(applet_id, protocol, tenant, external_user_id)` 的重复 provision MUST 返回既有 refs，不得重复铸造 profile / grant；`Idempotency-Key` 语义与 §7.3 相同。
- provision 不隐含任何 Realm membership 或 MLS 入组：ghost 加入 portal Realm 走常规 membership 流程，加入 E2EE group 还需 §12 的独立 E2EE 加入授权。

## 10. Portal Realm

Portal Realm 把外部 location 映射到 Cokret。

Portal Realm SHOULD 记录：

- 外部协议
- 外部网络 id
- 外部 location id
- bridge Applet id
- 创建者 / 控制者
- 可见性
- 成员映射策略
- portal strand id（§10.1）

Portal Realm MUST 仍然执行常规的 Realm policy 与 capability 规则。

### 10.1 Portal Strand（normative）

`ck.message.create` 的 payload 是封闭 schema，required `strand_id` + `track_name`（[`event-payload.schema.json`](../../artifacts/schemas/event-payload.schema.json) `message_create_payload`）。因此 bridge 把外部消息写入 portal Realm 前，MUST 先解析出一个**目标 strand**——外部 location 的映射单位是 `(realm_id, strand_id)`，不是裸 `realm_id`。

- 每个 portal Realm MUST 至少有一个用于消息桥接的 **portal strand**；线性聊天型外部 location（IM channel / group chat）默认一个 location 对应一个 portal strand。
- **获取/创建路径**：bridge 首次为某外部 location 建立映射时，MUST 按以下顺序确定 portal strand：
  1. 查自身持久化的 location ↔ `(realm_id, strand_id)` 映射；
  2. 映射缺失时，在该 portal Realm 内通过常规 projection / view 读取查找既有 portal strand（以 `external_ref` 中的 protocol / network_id / location_id 匹配）；
  3. 仍不存在时，由 bridge 以自身可署名身份提交 `ck.strand.create`（Event Envelope 顶层携带 signed `external_ref` 记录外部 location 出处），并把结果 strand_id 写入映射。
- **创建幂等**：并发或重试导致同一外部 location 产生多个 `ck.strand.create` 时，bridge MUST 以 effective 顺序最早的 strand 为 portal strand，多余 strand SHOULD archive；判定依据是 signed `external_ref` 的 location 等值，不得靠标题字符串猜测。
- **track**：桥接消息默认写入 `track_name="discussion"`；profile / Realm schema 声明其它 track 布局时按声明走。
- ghost 署名的桥接 `ck.message.create` MUST 把正文放进 payload `content`（或 E2EE 下 `encrypted_content`）的 `content_block` 形态，媒体引用走 `blob_refs[]`；不得把 content 级字段（`mimetype` / `filename` / `blob` 等）直接平铺为 payload 顶层字段——按 schema 强校验的节点会以 `schema_violation` 拒绝。

## 11. Masquerading 与 Delegated Agent

只有当用户或组织显式授予委托权限时，Applet MAY 代表 native 用户行事。

由此产生的 Event MUST 同时呈现：

- accountable actor：native actor
- executing applet / 委托密钥

示例 UI 语义：

```text
Alice via Calendar Applet
```

协议字段 **MUST** include:

```json
{
  "actor_id": "did:web:alice.example",
  "executed_by": "did:web:calendar-applet.example#agent",
  "authorization_ref": "ck:grant:0196410c-0000-7000-8000-000000000000",
  "applet_id": "ck:applet:8a0baad5-6000-7000-8000-000000000000"
}
```

这些字段位于 Event Envelope 顶层并进入 canonical event bytes；实现 MUST NOT 把 `applet_id` 或 `authorization_ref` 降级为 `payload` 内业务字段或 `unsigned` hint。

**Reducer normative**:

- 当 Event 的 envelope signature 由 applet / delegated agent key 签发但 `actor_id` 指向 native principal DID 时（即 actor_id ≠ signing key 所属 DID），reducer MUST 校验：
  1. `executed_by` 必填，指向实际签发该 Event 的 applet / agent DID;`executed_by` 与 envelope signing key 的 DID 一致;
  2. `authorization_ref` 必填，指向已 accepted 的 `ck.capability.grant`(或等价 delegation event), 该 grant 把 actor_id 主体的某个 action 委托给 executed_by;
  3. `applet_id` 必填(在 Applet 模式下), 指向已注册的 applet;
  4. `executed_by` MUST 落在 `applet_id` registration 声明的主体集合内:即等于该 registration 的 service DID / `bot_actor_id`,或匹配其 `namespaces.actors` pattern(含 ghost DID namespace)。持有针对 `actor_id` 主体的有效 grant、但 `applet_id` 指向另一无关已注册 applet(其 registration namespace 不覆盖 `executed_by`)时,reducer MUST 拒绝,reason=`applet_namespace_mismatch`。
  5. grant constraint MUST 绑定 `applet_id`、`executed_by` 与 `registration_epoch`。`registration_epoch` 是 grant 的唯一安全 epoch 绑定键；service DID Document digest/version evidence、accepted signing key set、endpoint/auth material、bot actor / base URL 等安全相关字段都必须进入该 epoch 的 canonical evidence。reducer/verifier 不能只做字符串等值比较后放行：它 MUST 展开 referenced registration 的 epoch evidence，重新解析或按 method-specific version evidence 读取 service DID Document，并确认当前 DID Document digest、accepted signing key set 与 epoch 捕获值一致。无版本化 `did:web` MUST re-fetch canonical document 并比对 digest；不一致时旧 grant fail closed。Applet key rotate、DID Document endpoint 变化或 registration 更新后，旧 grant 不得继续授权新 key。
- 缺少 `executed_by`、`authorization_ref` 或 `applet_id` 中任一字段时,reducer MUST `schema_violation` 拒绝。该规则适用于所有 `ck.profile.applet_*` profile,客户端 / SDK 不得退回到 SHOULD 形态。

Applet MUST NOT use masquerading to hide automation. 客户端 MUST 明确展示 `via applet`：UI 在渲染 mention、notification、audit log、moderation queue 等任何"who did this"上下文时,MUST 同时显示 native actor 与 `executed_by` 双重署名，不得仅显示 native actor 而隐藏 applet 身份。

`requested_scopes` 只服务 consent / audit UI：registration 接受时，reviewer 可据此决定是否签发 capability grant；一旦 grant 写入，后续 reducer 只看 grant `actions[]` / selector / constraint，不再从 `requested_scopes` 推断权限。实现 MUST 在 audit log 中把最终 grant 与 registration `requested_scopes` 的差异显示给 reviewer，避免 Applet 请求 A、实际被授予 B 时无人可见。

## 12. E2EE

Applet 参与 E2EE Realm 时有三种模式：

1. Bot 作为正式成员加入 MLS group。
2. Ghost Actor 作为正式成员加入 portal Realm 的 MLS group。
3. Applet 不解密，只转发外部密文或桥接 metadata。

规则：

- Applet 没有加入 MLS group 时 MUST NOT 获得明文。
- Bridge 到不支持 E2EE 的外部网络时，客户端 MUST 明确提示加密边界在 bridge 处终止。
- Applet 托管 Ghost Actor MLS state 时，必须将其视为高敏感密钥材料。

**E2EE 加入授权（normative）**：Bot Actor 或 Applet-managed Ghost Actor 加入 E2EE Realm 的 MLS group（上文模式 1、2）MUST 经过独立的 **E2EE 加入授权**，该授权与普通的 capability grant（如 `ck.strand.create` / `ck.message.create` 等写入权限）**分立**：持有写入 capability 不自动授予把 applet / ghost 成员加入 MLS group 的权利。

- 该 E2EE 加入授权 MUST 由 Realm owner、Realm admin 或 Realm policy 明确授权的 authz service 签发（参照 §4 的 `applet_registration_unauthorized` 门槛），并落为可审计的 Cokret Event（如 `ck.member.state` 加入 effect 携带 applet provenance），不得仅凭 Applet 自身 Welcome 入组。
- 缺少该独立 E2EE 加入授权时，Cokret 客户端 MUST NOT 把 applet / ghost 成员加入 MLS group，并 MUST 以 `applet_e2ee_join_unauthorized` 拒绝该加入。
- 成员加入后，客户端在 MLS group 的成员 roster（成员列表 UI 与 audit 视图）中 MUST 显式标注该成员为 **applet-managed**（区别于 native 人类成员），不得让 applet / ghost 成员在 roster 中表现为普通 native 成员。该标注与 §9 的 Ghost Actor 协议层可区分要求一致。

## 13. 安全要求

Applet 实现 MUST：

- 验证所有入站 HTTP message signature
- 验证所有 Event signature
- 持久化 transaction id，保证幂等
- 对外部事件做去重
- 限制 namespace 范围
- 遵守 capability grant
- 记录可审计 bridge mapping
- 对 secret / token 使用安全存储
- 支持管理员 revoke

Applet 实现 MUST NOT：

- 接收全网 sync stream，除非明确授权
- 把 namespace 当作写权限
- 静默 impersonate native user
- 绕过 Realm encryption policy
- 泄露未授权 Realm 内容到外部网络

## 14. 失败与重试

Transaction push 失败时：

- 5xx / timeout：发送方 SHOULD 重试相同 `Idempotency-Key`
- 4xx：发送方 SHOULD 停止重试，除非错误是 `rate_limited`
- `rate_limited`：发送方 MUST 优先遵守 `Retry-After`，非 HTTP binding 或无 header 时再使用 `retry_after_ms`
- `duplicate_conflict`：发送方 MUST 停止并告警

Applet 处理外部网络写入失败时 SHOULD 生成 bridge error event，而不是静默丢弃。

## 15. Conformance

Applet v1 conformance 按 profile 继承拆分。实现声明某 profile 时 MUST 测试该 profile 的 required endpoints / event kinds；未声明的 profile/add-on surface MUST 返回 `unsupported_feature` 或 policy-denied，不得静默放行。

`ck.profile.applet_service.v1` base bot-only MUST 测试：

- registration signature
- namespace matching
- transaction idempotency
- capability enforcement
- bot actor attribution
- install preview / commit / revoke aggregate operation idempotency, when the implementation exposes self/admin Applet install
- `ck.edge.applet.command.transaction` only as operation_id, never as durable Event kind

`ck.profile.applet_bridge.v1` inherits `ck.profile.applet_service.v1` and MUST additionally test:

- resolve actor
- resolve realm
- protocol metadata
- Ghost Actor accountability
- portal Realm metadata
- duplicate external event handling
- bridge error event visibility

`ck.profile.applet_delegated.v1` inherits `ck.profile.applet_service.v1` and MUST additionally test delegated grant binding, `executed_by` / `authorization_ref` / `applet_id`, dual-signature UI attribution, and `registration_epoch` evidence verification.

`ck.profile.applet_e2ee_join.v1` inherits `ck.profile.applet_service.v1` and MUST additionally test independent E2EE join authorization, MLS roster applet-managed marking, and `applet_e2ee_join_unauthorized`.

`ck.profile.applet_widget.v1` inherits `ck.profile.applet_service.v1` and MUST additionally test widget origin isolation, CSP, scoped token, consent, and host session/device-key non-disclosure.

## 16. v1 互操作要求

- `applet_registration` JSON Schema 由 `applet-schema.md` 和 `schema-registry.md` 固定，必须包含 service DID、endpoint、namespace、protocol、capability refs、signing method 和 expiry。
- Namespace pattern grammar MUST 明确 actor、realm、handle、external protocol id 的匹配边界；namespace 命中不授予写权限。
- Transaction push operation MUST 包含 `source_service_did`、`events[]`、`Idempotency-Key`、HTTP message signature 与 received_at audit metadata；外部 source network、external event id、mapped actor、target Realm / Circle 与 operation refs 必须落在具体 Cokret Event 的 `external_ref` / provenance / capability refs 中，不得通过 transaction 专用 durable Event 表达。
- Protocol metadata schema MUST 声明外部系统、identity mapping、permission mapping、E2EE boundary、rate limit 和 supported media types。
- Bridge error event 使用 `ck.applet.bridge_error`，必须绑定 failed transaction、外部错误类别、是否可重试和可见范围；不得泄露未授权外部正文。
- External event deduplication key MUST 至少包含 protocol、tenant/workspace、external channel/location、external event id 和 normalized sender；不得只依赖时间戳或正文 hash。
- Applet UI widget sandbox MUST 与 Realm capability、origin isolation、CSP、token scoping 和 user consent 绑定；widget 不得直接获得 Cokret session token 或未授权 Event history access。该 sandbox 的字段与约束在 [§17 Applet UI Widget](#17-applet-ui-widget) 定义。

## 17. Applet UI Widget

部分 Applet 在 Cokret 客户端内嵌入 UI widget（如 Slack-style 交互卡片、配置面板）。Widget 在 host 客户端的信任边界内渲染，因此 MUST 被沙箱隔离。本节定义 §16 引用的 widget sandbox 的最小 normative 形态。

是否提供 widget 由 Applet 决定（可选）；但**若 Applet 提供 widget，则其 widget 声明（registration 或 describe 响应内）MUST 包含下列全部 required 字段**。顶层的可选性仅限"是否提供 widget"这一选择，不得用于省略已提供 widget 声明中的任一 required 字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `widget_origin` | `string`（origin） | required | Widget 内容来源 origin（scheme + host + port）。host 客户端 MUST 在隔离 origin（iframe sandbox 或等价机制）内加载 widget，MUST NOT 在 host 客户端自身 origin 下执行 widget 代码。 |
| `csp` | `string` | required | 适用于 widget 文档的 Content-Security-Policy。host 客户端 MUST 强制该 CSP，并 MUST NOT 放宽到允许 widget 访问 host 客户端的 DOM、storage 或 session。 |
| `token_scope` | `object` | required | Widget 可用 token 的 capability scope（action / resource selector / realm_ids / expiry）。该 token MUST 是为 widget 单独签发的 scoped token，scope MUST NOT 超出本字段声明的范围。 |
| `requires_consent` | `boolean` | required | 是否需要在加载前向用户展示 consent / capability 摘要。 |

约束（normative）：

- **Origin 隔离**：widget MUST 在与 host 客户端隔离的 origin 中运行；host 客户端 MUST NOT 把自身 origin 的 cookie、localStorage、IndexedDB 或 in-memory session 暴露给 widget。
- **Token scoping**：host 客户端 MUST NOT 把 Cokret 用户的 session token 或 device key 传给 widget；widget 只能拿到为其单独签发、scope 收敛到 `token_scope` 的短期 capability token，且该 token MUST NOT 超出 widget 声明的 scope。
- **History 读取不可越权**：widget MUST NOT 通过任何接口读取超出其 capability scope 的 Event history；host 客户端 MUST 以 widget 的 scoped capability 为准做 history 访问授权，未授权范围 MUST 拒绝。
- **Consent**：`requires_consent=true` 时，host 客户端 MUST 在加载 widget 前向用户展示其 origin 与请求 scope，未获 consent MUST NOT 加载。
