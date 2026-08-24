---
title: Applet Integration
status: candidate
normative: true
stability: v1
updated: 2026-07-13
---

> **状态：extension profile（非 v1 core 互操作必需）**。Applet registry、审核 SLA 与 capability
> 注入流程仍在演进。Arkret v1 core 互操作 **不要求** 实现本 profile；声称 v1 core 的
> 实现可以完全不接 Applet，仅通过 capability + actor 模型表达 bot / bridge / agent。
> `ak.profile.applet_service.v1` 视为可选 extension（见 `artifacts/profiles/conformance-profiles.json`
> 的 `profile_sets.extension_profile_implementation`）。Applet v1 家族用继承关系分层:
> base bot-only 使用 `ak.profile.applet_service.v1`，bridge / delegated / E2EE join / widget
> 分别通过 `ak.profile.applet_bridge.v1`、`ak.profile.applet_delegated.v1`、
> `ak.profile.applet_e2ee_join.v1`、`ak.profile.applet_widget.v1` 叠加。

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Matrix 有 Application Service / Appservice，用于桥接 IRC、Slack、Discord 等外部网络，也用于 bot 和自动化集成。Arkret 需要类似能力，但不能继承 homeserver 中心化和 user_id namespace 的假设。

Arkret 将该能力定义为 **Applet**。

Applet 是一个受注册、受授权、可审计的集成服务。它可以：

- 作为 bot 参与 Realm
- 桥接外部网络
- 创建和管理 Ghost Actor
- 管理 portal realm
- 接收 Arkret 事件交易
- 把外部事件转换为 Arkret event
- 在获得明确授权时以受托 agent / device 方式执行操作

Applet / Agent / Morph / Ghost Actor 的选择边界如下，实现 MUST 按最窄概念建模：

| 场景 | 首选模型 | 不应使用 |
| --- | --- | --- |
| 高频外部事件桥接、多用户镜像、需要 namespace / capability 撤销 / portal Realm | Applet + Ghost Actor | Morph 直接表示外部用户；Agent session 长期常驻 |
| 单次或低频外部对象导入、内容不可信、只需保留原文与映射证据 | Morph / Relation | Ghost Actor 写入协作历史 |
| AI / 自动化长任务、需要状态回流、产物归档、可取消会话 | Agent protocol session | Applet masquerading 成人类 actor |
| 外部人类用户在 Arkret 内可被 mention / 授权 / 审计 | Ghost Actor（标记 managed_by_applet） | 伪装为 native principal DID |

同一外部实体可以在不同上下文下产生 Morph 记录和 Ghost Actor，但二者 MUST 通过显式 Relation / provenance 字段连接，不能让 projection 自由猜测它们是同一主体。

## 2. 与 Matrix Appservice 的对应关系

| Matrix Appservice | Arkret Applet |
| --- | --- |
| homeserver 本地注册文件 | signed `applet_registration` |
| sender localpart | applet controller DID / bot DID |
| user namespace regex | actor namespace claim / DID namespace |
| room namespace regex | Realm / portal namespace |
| alias namespace regex | handle / portal alias namespace |
| `/transactions/{txn_id}` | `POST /_arkret/edge/applet/transactions` + `Idempotency-Key` header |
| `/users/{user_id}` | `/_arkret/edge/applet/actors/{actor_id}` |
| `/rooms/{room_alias}` | `/_arkret/edge/applet/realms/{realm_id_or_alias}` |
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

Bot 是独立长期 principal，不复用 Applet service/controller identity。安装原子单元必须接受
`ak.applet.managed_actor.provision` 与 purpose=`applet_managed_control` 的 PCR genesis：前者冻结完整
`PrincipalAuthorityKey=(bot_actor_id, actor_principal_server_id)`、method-native initial-resolution evidence、
registration/grant 与 Applet provenance，后者以 critical ref 唯一引用该 provision Event 并逐字交叉绑定
`initial_resolution`。Package / durable registration 只保存不可变的 provision/genesis anchor，不保存
current resolution source ref；运行时 current resolution 只由该 authority pair 的 PCR resolution cell 重放。

### 3.4 Ghost Actor

外部网络用户在 Arkret 中的镜像 Actor。例如 Slack 用户 `U123` 映射为一个独立 Actor DID：

```text
did:webvh:z6MkGhostU123:slack-bridge.example
```

`#fragment` 只用于 DID URL 形式的 verification method（例如 `did:webvh:z6MkGhostU123:slack-bridge.example#key-1`），不得作为 `actor_id` / `bot_actor_id` 的一部分。稳定 `actor_id` 使用其 adapter projection `ak:did_core:webvh:z6MkGhostU123`；每个 Ghost 必须有自己的 validated SCID，不能复用 Applet service SCID 后仅靠 host/path 区分。

Ghost 使用与 Bot 相同的 managed-actor provision + PCR genesis authority 模型，但 role 固定为 `ghost`，
provision 还必须逐字绑定 external tuple。namespace 对经 method evidence 验证的 `initial_resolution.full_id`
匹配，不能对 `did_core_id` 匹配完整 DID pattern。Profile/accountability Event 不能替代 identity binding，
服务端也不得从 external tuple、namespace 或 Applet service DID 生成 Ghost DID。

Ghost Actor MUST 带有 `accountable_principal_ids`，且本节 provisioning aggregate 创建的初始 Profile MUST 只包含提交并签署同请求 `accountability_grant_event` 的外部 service DID。Applet controller 与 Ghost 的生命周期关系由 active Applet registration / install 记录表达，不得在缺少 controller 自己签发的 active `ak.identity.accountability_grant` 时把 controller DID 复制进该数组；后续若要增加 controller，必须先独立提交该 controller 的 grant，再按普通 Profile update 规则更新。外部网络来源（protocol / network id / user id）记录在 `profile_fields.external_ref`。问责字段以 actor-profile schema 的 `accountable_principal_ids` 为唯一权威形态（见 [`applet-schema.md`](./applet-schema.md) 与 §9）；`accountability` 嵌套对象不是合法 wire 形态。

#### 3.4.1 Ghost Actor vs Native Personal Agent 边界

`actor_kind` 不定义 `agent_native`、`agent_ghost` 或 `ghost` wire enum。Native personal AI agent 使用 `actor_kind="agent"`；Applet-managed Ghost Actor 使用现有 enum 中最贴合其主体类型的值：外部人类/账号镜像 SHOULD 使用 `actor_kind="integration"`，Applet 托管的 AI/automation ghost MAY 使用 `actor_kind="agent"`。二者必须通过 Applet provenance、`accountable_principal_ids` 和 profile/capability 约束与 native personal agent 区分，不能依赖新增 `actor_kind` 值区分。

Native personal AI agent(由 controller 通过 `ak.self.agent.command.provision` 创建，见 [`../identity/key-management.md` §3.6.1](../identity/key-management.md))与 Applet-managed Ghost Actor(本节)是两类不同 actor，生命周期与治理路径完全分离:

| 维度 | Native personal agent | Applet-managed Ghost Actor |
| --- | --- | --- |
| 创建路径 | controller 先生成、签署并发布不含 PCR binding 的 Agent DID entry 0；`ak.self.agent.command.provision` prepare 只验证其 accepted `initial_resolution` 与 delegation，不生成 DID/私钥或分配 PCR id。controller 把该承诺写入本地冻结的 Agent PCR genesis并取 `retype(event_id)`，再提交唯一 controller-signed `ak.agent.provision` Event，在一个 reducer transaction 原子派生 provision/accountability/selector/realm-id-claim projection；必填 `requested_scope` 只建立 immutable 全局 ceiling，不生成 `ak.capability.grant`。PCR genesis 在另一次提交 accepted 后 outcome 为 `awaiting_did_binding`；controller 以预承诺 key 发布 create-locked entry 1，accepted 后才 `complete` 并暴露 pairing/list/get。Profile、恢复备份与首次 `ak.agent.key.authorize` 继续独立提交 | `ak.applet.registration` + Applet bot/Ghost Actor 注册 |
| `accountable_principal_ids` | 指向 controller principal，显式 `ak.identity.accountability_grant` | 初始 Profile 指向签署同一 aggregate accountability grant 的外部 service DID；Applet controller 关系由 registration / install 表达 |
| Runtime credential | 通过 `POST /_arkret/gate/account/agent-key-pair` pairing 得到 `ak.agent.key.authorize` 绑定的 key | Applet 管辖，通常是 Applet service DID + HTTP signature |
| Session 路径 | `POST /_arkret/gate/account/session-grants` + `proof.proof_kind="agent_key_proof"` | Applet `ak.edge.applet.command.transaction` 与 Applet 的 delegated session |
| 撤销 | `ak.self.agent.command.pause` / 单一 `ak.self.agent.command.deactivate` lifecycle Event；terminal parent gate 使 child authority ineffective，cleanup 非前置 | Applet registration 撤销；Ghost Actor 跟随 Applet 生命周期(经 §4b Revoke,`remove_ghost_membership` 需 active ghost projection 完整否则 MUST fail closed) |
| Realm policy | Realm policy MUST 单独允许 native personal agent(`ak.profile.personal_agent_provisioning.v1`) | Realm policy MUST 单独允许 Applet base bot-only(`ak.profile.applet_service.v1`)；Ghost Actor / portal bridge 需额外声明 `ak.profile.applet_bridge.v1` |

**Realm policy MUST 至少能分别控制 native personal agent 与 Applet / Ghost Actor**:部署可以禁止普通用户创建或使用 personal agents 同时允许管理员安装的 Applet + Ghost Actor，也可以反向配置；**二者不得被合并为一个不可区分的 "automation allowed" 开关**。

`ak.profile.personal_agent_provisioning.v1` / `ak.profile.agent_sidecar.v1` 只覆盖 Native Personal Agent 路径；Ghost Actor / Applet Bot Actor 不走 personal Agent provisioning，也不得进入独立 Sidecar 对象的 desired/effective access。

面向 Realm 全体成员、并由组织或 Realm 运维的知识库问答、moderation、workflow 等共享机器人，不得建模为“没有 owner 的 Native Personal Agent”。Native Personal Agent 必须有可验证的人类 / 组织 controller，且不能脱离该 controller 的 Realm membership 单独存留。此类共享机器人 SHOULD 作为管理员安装的 Applet Bot Actor 接入：Applet service / registration 是其 lifecycle 与 accountability 根；只有需要代表外部网络中多个独立主体时才进一步 provision Ghost Actors。单一共享 bot 不需要为了满足该规则虚构一个 Ghost Actor。

### 3.5 Portal Realm

外部网络 location 在 Arkret 中的镜像 Realm。例如 Slack channel、Discord guild channel、GitHub issue discussion。

## 4. Applet Registration

Applet MUST 有签名 registration。它可以由 Realm owner、组织管理员、registry 或 authz service 接受。

Applet 进入某个 Realm 的 capability MUST 由该 Realm owner、Realm admin 或 Realm policy 明确授权的 registry/authz service 签发。仅凭 Applet 自签 registration、namespace claim 或外部 registry 收录不得写入 Realm；缺少该 grant 时，任何 Applet 通过 transaction push、Event submit 或 delegated signing 引入的 Realm 写入 MUST 拒绝，reason=`applet_registration_unauthorized`。

**机读授权门(normative)**：上述"由 Realm owner/admin/authz 授权 install / grant"绑定到机读 capability gate——`ak.applet.registration` 是 `ak.realm.admin` capability action 的目标 event kind(见 [`capability-action-registry.json`](../../artifacts/registry/capability-action-registry.json) 中 `ak.realm.admin.target_event_kinds`)。提交 formal fixed set 的 admin actor MUST 持有覆盖目标 Realm 的 active `ak.realm.admin` grant(或 Realm policy 明确授权的 authz service 等价授权);reducer 校验失败时整个本地事务 MUST 拒绝，reason=`applet_registration_unauthorized`。`ak.applet.registration` 在数据面仍是 `service_attested`(注册载体真实性),`ak.realm.admin` 门控的是"谁有权安装"，二者并存:注册被服务背书不等于被授权安装。

示例：

```json
{
  "kind": "ak.applet.registration",
  "applet_id": "ak:applet:21532600-0000-7000-8000-000000000000",
  "service_id": "ak:did_core:webvh:z6Mkw8qTnL4rP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z",
  "controller_id": "ak:did_core:webvh:z2dmjQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn",
  "base_url": "https://slack-bridge.example/applet",
  "bot_actor_id": "ak:did_core:webvh:z6MkSlackBridgeBotScid",
  "claimed_profiles": [
    "ak.profile.applet_service.v1",
    "ak.profile.applet_bridge.v1"
  ],
  "protocols": [
    "slack"
  ],
  "namespaces": {
    "actors": [
      {
        "exclusive": true,
        "pattern": "did:webvh:z6Mkw8qTnL4rP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z:slack-bridge.example:ghost:*"
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
  "receive_signals": false,
  "rate_limited": true,
  "requested_scopes": [
    "ak.realm.discover",
    "ak.object.read",
    "ak.strand.create",
    "ak.morph.create",
    "ak.message.create",
    "ak.relation.create"
  ],
  "registration_epoch": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "webhook_auth": {
    "kind": "http_message_signature",
    "key_ref": "did:webvh:z6Mkw8qTnL4rP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z:slack-bridge.example#server-key-1",
    "accepted_signature_algorithms": [
      "ed25519"
    ]
  },
  "proof": {
    "kind": "detached_jws",
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
- `service_id` MUST 是稳定 service `did_core_id`；注册时提供的 `full_id` 必须经 adapter 投影到它，当前 endpoint 通过 verified ServiceResolutionRecord 取得。
- `controller_id` MUST 是 controller `did_core_id`；复制到 registration 的 package proof VM 的 bare `full_id` 必须经 adapter 投影到它并通过签名验证。
- `bot_actor_id` 是独立 Bot principal；安装单元的 managed-actor provision payload MUST 逐字等于 registration 的该字段，并携完整 authority pair、initial resolution 与 method history evidence。一个 registration 只能接受这一个 Bot authority pair，且 Bot 不得等于 service/controller/Ghost。
- `claimed_profiles` MUST 从已验证 package 原样复制到 durable registration，至少包含
  `ak.profile.applet_service.v1`；profile-bound authority 只读取 accepted Event，不得读取
  preview/package cache。
- `namespaces` MUST 明确声明，不能默认为全网。
- exclusive namespace 冲突时，registry / authz service MUST 拒绝后注册者。
- `requested_scopes` 只是请求权限，不是实际授权。
- 实际权限 MUST 通过 capability grant 授予。
- `registration_epoch` MUST 进入 payload required 字段，并严格按 [`applet-schema.md` §1.0.1](./applet-schema.md#101-registration_epoch-transcript-与计算算法normative) 的 closed transcript、集合排序、JCS、域分离与 SHA-256 步骤覆盖 canonical derived registration、service DID Document digest/version evidence、accepted signing key set、endpoint/auth material。grant 存储与匹配只绑定该 epoch；reducer/verifier 仍 MUST 展开 epoch evidence，校验当前 DID Document digest / signing key 与 epoch 捕获值一致。
- `proof` MUST 是已验证 package controller DID detached proof 的逐字副本，`payload_digest` 覆盖 canonical package（不含 package `proof` 自身）；空对象、旧 `event_digest` 或与同一安装 package 不同的 proof MUST 以 `schema_violation` / `proof_invalid` 拒绝。formal registration Event 由安装管理员自己的 Event proof 覆盖，并由接收 Principal Server 加 admission proof；不得把 package proof 当作 Event proof。

## 4a. Applet Package 与安装聚合操作

开发者发布 Applet 时 SHOULD 发布 controller-signed **Applet Package**。Package 是分发对象，不是 Realm history event；进入协议事实前 MUST 派生为 `ak.applet.registration` payload，并由 Realm owner/admin/authz service 通过安装聚合操作签发实际 grant。

Package 最小字段以 [`applet-schema.md` §1a](./applet-schema.md#1a-applet-package-schema) 的字段参考表为唯一规范源；本节不重复维护字段表。Package MUST NOT 自行授权写入 Realm。Package 接受、registry 收录、namespace claim 或 `requested_scopes[]` 出现某 action 都不得被 reducer 解释为 grant。`registration_epoch` MUST 随 claimed profiles、namespace、base URL、webhook auth、endpoint key、requested scopes、widget origin、E2EE request、receive/rate-limit 行为或 DID/key evidence 改变而改变。

Package -> registration 派生映射同样以 [`applet-schema.md` §1a](./applet-schema.md#1a-applet-package-schema) 的映射表为唯一规范源。本节只补充安装语义：派生出的 registration 成功写入仍不授权；只有随后签发的 grant 与 `(applet_id, effective_scope, registration_epoch)` 绑定并保持 active，Applet 才取得对应 scope 的 effective install。

## 4b. Install Preview / Commit / Revoke

Applet 安装使用 self/admin aggregate operation。它不创建 install 专用 durable Event；Bot 基线的固定事实集合是
`ak.applet.registration`、一个或多个 `ak.capability.grant`、恰好一个
`ak.applet.managed_actor.provision`、恰好一个 purpose=`applet_managed_control` 的 `ak.realm.create`、
`ak.identity.accountability_grant` 与 `ak.profile.create`。服务端必须先验证完整集合，再按上述顺序在同一
durable transaction 中接受 Events、projection、Applet record 与 idempotency outcome；不得暴露 staged
registration/grant，任一失败整个单元不可见。membership、E2EE 与 widget effect 仍使用各自登记的事实。

新增 operation:

| operation_id | HTTP | 语义 |
| --- | --- | --- |
| `ak.self.applet.install.command.preview` | `POST /_arkret/self/applets/install/preview` | 校验唯一内嵌的管理员 formal Events，返回 canonical `InstallPlan` 与目标 Principal Server 签名的短期 authoring request。 |
| `ak.edge.applet.install.command.author` | `POST /_arkret/edge/applet/install/author` | Applet service 校验 Principal Server authoring request，按既有 service-authored / service-executed creation admission 签四个 managed-actor Events 并返回 exact bundle；独立 Bot key 在 PCR accepted 后才用于 Bot 自签/rotation。 |
| `ak.self.applet.command.install` | `POST /_arkret/self/applets/install` | 提交安装，必须带 `Idempotency-Key`、exact signed authoring request 与 exact Applet bundle。 |
| `ak.self.applet.revoke.command.preview` | `POST /_arkret/self/applets/{applet_id}/revoke/preview` | 只读重算 active install，返回 canonical `AppletRevokePlan` 与 `revoke_plan_digest`。 |
| `ak.self.applet.command.revoke` | `POST /_arkret/self/applets/{applet_id}/revoke` | 提交 caller-signed revoke saga，必须带 `Idempotency-Key` 与 preview digest。 |

`effective_scope` 是单次 install 的唯一目标:

- `kind="realm"` MUST 只包含 `kind` 与 `realm_id`，并约束为 Realm-wide grant。
- `kind="circle"` MUST 同时包含 `kind`、`realm_id` 与 `circle_id`，并约束为该 Circle grant；不得由 Circle install 推导 Realm-wide grant。
- 单次 install operation 只处理一个 `effective_scope`。多 Realm、多 Circle 批量安装和跨 sovereign server 的 install 事务聚合不是 v1 目标。
- install preview/commit MUST 由目标 Realm 的 controlling Principal Server 或 Realm policy 明确授权的 authz service 承载；Bot authority 固定集合跨 portal lineage 与新建 PCR，只允许 `actor_principal_server_id` 指定的同一 Principal Server 在本地 closed aggregate 中接受，既不把 install operation 变成跨 server 分布式事务，也不得把固定集合拆成逐 Event peer federation。安装后的普通 Collaboration Realm Event 才按各自 federation 规则传播。
- install commit 的授权门是机读 `ak.realm.admin` capability(§4)：commit 提交的 admin actor MUST 持有覆盖目标 Realm 的 active `ak.realm.admin` grant(或 Realm policy 授权的等价 authz service)；fixed set 中的 `ak.applet.registration` 是该 capability action 的目标 event kind。reduce-time 缺少该授权时 MUST fail closed,reason=`applet_registration_unauthorized`，且整个本地事务零写。
- `authoring_request.basis.registration_event` 与同一 basis 中每条 `capability_grant_events[]` MUST 是该 admin caller
  已完成签名、可直接进入通用 Event admission 的 formal Event；服务端 MUST NOT 重建 Event、
  改写 event id/frontier/seal basis、以 service notary 代签 Event，或替 grant issuer 生成
  payload proof。`registration_event.actor_id`、每条 grant Event 的 `actor_id`、grant `issuer`
  与 authenticated install actor MUST 全部逐字相等。
- `ak.profile.applet_bridge.v1` 对 non-event action `ak.applet.ghost.provision` 的唯一首发
  authority 是其机器 artifact `non_event_grant_authority_rules[]`：issuer 必须在同一
  `seal_basis` joined view 下持有覆盖 effective scope 的 `ak.realm.admin`；registration
  必须已 accepted、`claimed_profiles[]` 包含 `ak.profile.applet_bridge.v1`、service/epoch/
  requested scopes 与 grant 的 subject、`applet_authority` constraint 及 action 逐字绑定。
  Realm owner、membership、package controller proof 或 install endpoint authentication
  均不得替代该 authority。规则只覆盖 `ak.applet.ghost.provision`，不得类推到其它
  non-event action。
  Conformance 必须执行
  `ak.vector.capability.applet_bridge_non_event_grant_authority.v1` 的 owner/profile/binding
  正负向矩阵。

当 controller proof 无效、DID Document 不可解析或 key ref 不匹配、namespace pattern 非法、exclusive namespace 与 active install 冲突、requested action 不在 capability registry、effective_scope 所属 Realm policy 禁止 Applet/Ghost Actor/widget/E2EE、或 package 已过期时，Preview MUST fail closed。

Commit MUST 执行：

- 在同一 durable transaction 中持久化完整 install execution record、formal fixed set、projection、Applet record 与幂等结果。
- 对同一 `Idempotency-Key` + 同一 body canonical hash 重试返回同一结果和同一批 accepted event refs；同一 key + 不同 body MUST 返回 `duplicate_conflict`。
- 服务端在事务开始前验证 caller 提交的每条 Event canonical bytes、event id、proof、frontier、依赖与 fixed-set 交叉绑定；事务内任一 CAS 或持久化失败必须回滚全部 Event 与 record。重试只读取同事务保存的 exact outcome，不得生成替代 id、重建 Event 或恢复逐步提交。
- 重新计算 plan；不得盲信客户端传回的 `InstallPlan`。
- 从 `authoring_request.basis.capability_grant_events[]` 提取 actions/resources，与 package requested scopes、当前 Realm/Circle policy 取交集后重建 Approved Capability Set；不得接受未请求 action、scope widening、重复 action，或缺少 `authority_control.applet_authority` 精确绑定的 grant。commit 不镜像这些 Events。
- `authoring_request.basis.registration_event.payload` MUST 与 package 派生 registration payload canonical bytes 完全相同；每条 grant 的完整 subject authority pair MUST 等于 `(package.service_id, authoring_request.basis.target_principal_server_id)`，resource MUST 等于 basis 中唯一 `effective_scope`，constraint MUST 绑定相同 `applet_id + service_id + registration_epoch`。任一不匹配 MUST 在提交首条 Event 前 fail closed。
- 当 recomputed plan canonical `plan_digest` 与 signed `authoring_request.plan_digest` 不一致时 MUST fail closed，返回 `applet_install_plan_mismatch`，并要求管理员重新 preview/approve；commit 不携第二个 plan digest。

正式安装的 registration、grant、Bot provision、PCR genesis、accountability 与 Profile 是本地单事务 fixed set；preview-time 或 reduce-time 任一步失败都 MUST 零 Event、零 projection、零 Applet record、零幂等结果。旧的逐 Event fan-out、partial accepted/rejected refs 与 orphan registration 模型删除，不提供兼容。该 fixed set MUST NOT 写 federation outbox；远端不能用 `ak.peer.events.command.submit` 单独重放其中的 `applet_managed_control` genesis。

Revoke 使用 caller-signed event-log saga。preview MUST 从 current effective install 精确枚举每个 active
grant、applet-managed bot/ghost membership、widget scoped token 与 delegated session，返回 canonical
`AppletRevokePlan` 及 `revoke_plan_digest=sha256(canonical_json(plan))`。plan 中每个 grant 对应一条
`ak.capability.revoke` intent；每个需要离开/移除的 managed member 对应一条 `ak.member.state` intent。
projection 不完整时 MUST fail closed 并要求先重建 projection，不得按 namespace pattern、旧 request 或
本地默认值猜测 grant/member/token/session。

Commit MUST 携 `revoke_plan_digest`、与每个 grant intent 一一对应的 caller-signed
`capability_revoke_events: EventInitialSubmission[]`，以及与 membership intent 一一对应的 caller-signed
`membership_state_events: EventInitialSubmission[]`。服务端必须在首个副作用前重算 plan，并逐字节验证
Event kind、scope、registration epoch、grant/member target、membership transition 与 reason；任何遗漏、
多余或不匹配均 fail closed。服务端不得代签、补写或重建 Event，也不得以本地 grant row / revoked flag
替代正式 Event admission。Event 的 canonical bytes 完成后才能派生 Event ID；不明结果与 retry 只能重放
request 中相同的 signed Event bytes。

Commit 在首个副作用前 MUST 持久化 saga ledger：绑定
`(principal_service_id, admin_actor_id, Idempotency-Key, canonical_request_digest,
revoke_plan_digest, exact_event_submissions, status, steps[])`。每个 step 的状态固定为
`pending|accepted|duplicate|rejected`，并在继续下一步前持久化。Event admission、Account Authority delegated
session revoke、widget token 作废与本地 applet fence 可以跨服务执行，不得声称分布式原子；restart MUST
从 ledger 恢复同一 submissions 与尚未完成步骤。只有全部 required replicated Events 已
accepted/duplicate、widget token 已作废、delegated-session 子操作完成且 local fence durable 后才返回
`status=complete, ok=true`。部分成功返回 `in_progress|partially_completed` 与精确 steps/rejected refs；已
accepted Event 不回滚、不重签，只继续缺失步骤。

从第一条相关 `ak.capability.revoke` 或 `ak.member.state` 被 accepted 起，未来 Applet writes MUST 立即
fail closed，reason=`applet_revoked` 或更细 reason，不能等待 saga 全部完成。涉及 delegated session
revoke 时，请求还 MUST 携 `proof: AccountLifecycleProof`；Principal Server MUST 用 active install 重建
`ak.gate.account.command.revoke_session` applet selector（`applet_id`、`effective_scope`、
`registration_epoch`、`service_id`、`capability_grant_refs`）并转发给 Account Authority。

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
  "pattern": "did:webvh:z6Mkw8qTnL4rP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z:slack-bridge.example:ghost:*"
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
  "subject": "did:webvh:z6Mkw8qTnL4rP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z:slack-bridge.example:bot",
  "claim_scope": {
    "realm_ids": [
      "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5"
    ],
    "actions": [
      "ak.strand.create",
      "ak.morph.create",
      "ak.message.create",
      "ak.relation.create"
    ]
  },
  "constraints": [
    {
      "constraint_kind": "scope_limitation",
      "effect": "allow",
      "allowed_data_labels": ["public", "internal"]
    }
  ],
  "expires_at": "2026-07-26T00:00:00Z"
}
```

scope 限制 MUST 只使用 [`authz/constraint-schema.md`](../authz/constraint-schema.md) 登记的 `scope_limitation` 字段（如 `allowed_data_labels` / `allowed_endpoints` / `allowed_*_container_refs` 等）；与具体 Applet install 的安全绑定 MUST 另外使用标准 `constraint_kind="authority_control" + constraint_subkind="applet_authority"`，并完整携带 `applet_id`、`executed_by=service_id`、`registration_epoch`。§5.1 registration namespace 与 §11 Event envelope 的 `applet_id` / `authorization_ref` 是使用时的交叉校验，不能替代 grant 自身的绑定。

除非 Applet 拥有 effective grant，或以委托授权身份显式代表已授权 actor 行事（此时 MUST 满足 [§11](#11-masquerading-与-delegated-agent) delegated agent 的全部字段 `executed_by` / `authorization_ref` / `applet_id` 与对应 reducer 校验），否则 Applet MUST NOT 向 Realm 写入。

## 7. Applet API

Applet API 是 Arkret 节点调用 Applet 的接口。  
Applet 调用 Arkret 节点时使用常规 Events API / Principal Server sync surface / authz API。

Base URL 来自 registration 的 `base_url`。

**出站网络目标策略（normative，SSRF 防护）**：node 在向 Applet registration `base_url` 主动出站（transaction push、ping、describe、resolve 等任意 server-side fetch，含 redirect / Alt-Svc 后实际目标）之前，MUST 执行 [`../sync/api-conventions.md` §11.2](../sync/api-conventions.md) 出站网络目标策略；命中云 metadata / 内网 / 回环等禁止地址类别时 MUST 拒绝出站，`base_url` / webhook endpoint 的 scheme MUST 限 `https`。§4b registration preview / commit 时 MUST 对 `base_url` / webhook endpoint 预检该策略。§7.3.1 的逐次来源签名只证明"是这个 Applet"，不证明"目标 IP 合法"，二者 MUST 同时满足。

**`ak.applet.*` 标识符的两类用途（normative 区分）**：`ak.applet.*` 前缀的标识符根据上下文分属两个互不混淆的命名空间，实现不得把二者当作同一对象：

- **Event kind（进 Realm history）**：`ak.applet.registration` 与 `ak.applet.bridge_error`。这些是 durable Arkret Event，进入 Realm history，由 reducer 按 schema 校验；`ak.applet.bridge_error` payload 以 `artifacts/schemas/event-payload.schema.json` 与 `applet-schema.md` §7 为权威。Applet runtime 的调用进度、私有 session id、opaque params/detail 与实现状态只属于 operation response/stream 或部署本地状态，MUST NOT 写入共享 Realm history；跨实现有意义的业务结果必须落为既有 Event、Strand、Message、Morph、Relation 或封闭的 result artifact。
- **operation_id（HTTP，不进 history）**：本节表中的 `ak.edge.applet.read.ping`、`ak.edge.applet.read.describe`、`ak.edge.applet.command.transaction`、`ak.edge.applet.actor.read.resolve`、`ak.edge.applet.realm.read.resolve`、`ak.edge.applet.read.protocol_metadata`、`ak.edge.applet.third_party_users.read.list`、`ak.edge.applet.third_party_locations.read.list`、§4b 的 `ak.self.applet.install.command.preview` / `ak.self.applet.command.install` / `ak.self.applet.revoke.command.preview` / `ak.self.applet.command.revoke` 以及 §9.1 的 `ak.self.applet.ghost.command.provision` 是 HTTP API operation 标识符，只描述 Arkret 节点 ↔ Applet 或 self/admin aggregate operation 的请求/响应绑定，本身不是 wire Event，不进入 Realm history。

`ak.edge.applet.command.transaction` 在 v1 artifacts 中只作为 operation_id 存在，指 §7.3 的 transaction push HTTP 调用；它 MUST NOT 作为 durable Event kind 或 transaction-origin Event 写入 Realm history。transaction push 的幂等记录属于 Applet service / transport audit log；Applet 写入 Arkret 的事实由具体 Event Envelope 的 signed `applet_id`、`external_ref`、`authorization_ref`、event signature 与 capability grant 表达。

字段级接口索引：

本表 **surface / 调用方向** 列区分两类 operation:`edge`（节点 → Applet，鉴权主体为 Arkret 节点，路径 `/_arkret/edge/applet/...`）与 `self`（管理员 → 自有 Principal Server aggregate，鉴权主体为管理员 actor，路径 `/_arkret/self/applets/...`）。二者调用方向相反、鉴权主体不同，实现不得套用同一鉴权模型。

| operation_id | surface / 调用方向 | 必填字段 | 可选字段 | 响应字段 | 约束 |
| --- | --- | --- | --- | --- | --- |
| `ak.edge.applet.read.ping` | edge（节点→Applet） | 无 | 无 | `ok: boolean`; `applet_id: id`; `service_id: did_core_id`; `protocol_version: string` | 可公开，但不得泄露 private namespace。 |
| `ak.edge.applet.read.describe` | edge（节点→Applet） | 无 | 无 | SDK `ServiceDescribe` | public mode 只返回 canonical discovery capabilities；不得私定义 Applet describe DTO。 |
| `ak.edge.applet.command.transaction` | edge（节点→Applet） | `header.Idempotency-Key: string`; `applet_id: applet_id`; `source_service_id: did_core_id` | `events: EventEnvelope[]`; `signals: SignalEnvelope[]`（两者**至少出现一个**） | `ok: boolean`; `rejected: object[]?`; `retry_after_ms: int?` | 字段集权威来源是 [`applet-edge-operations.schema.json`](../../artifacts/schemas/applet-edge-operations.schema.json) 与 [`applet-schema.md` §7](./applet-schema.md)。接收方 MUST 以 exact `applet_id + source_service_id` 选择唯一 active registration/current epoch，再验证 full/VM 投影、HTTP signature、event signature、namespace 和 capability；不得按 service id 任取首条 Applet。replay key 是 `(applet_id, source_service_id, Idempotency-Key)`。 |
| `ak.edge.applet.actor.read.resolve` | edge（节点→Applet） | `path.actor_id: did_core_id` | 无 | `exists: boolean`; `actor_id: did_core_id?`; `display_name: string?`; `external_ref: object?` | actor_id 必须命中 Applet actor namespace。 |
| `ak.edge.applet.realm.read.resolve` | edge（节点→Applet） | `path.realm_id_or_alias: string` | 无 | `exists: boolean`; `realm_id: id?`; `title: string?`; `external_ref: object?` | 必须命中 portal namespace 或授权查询。 |
| `ak.edge.applet.read.protocol_metadata` | edge（节点→Applet） | `path.protocol: string` | 无 | `protocol: string`; `display_name: string`; `icon_blob_ref: string?`; `field_definitions: object`; `instances: object[]?`（entry: `instance_id`, `display_name`） | instance list 可要求授权。 |
| `ak.edge.applet.third_party_users.read.list` | edge（节点→Applet） | `query.protocol: string`; `query.instance_id: string`; `query.external_id: string` | 无 | `actor_id: did_core_id?`; `exists: boolean`; `external_ref: object?` | 查询必须逐字匹配 Ghost immutable external tuple。 |
| `ak.edge.applet.third_party_locations.read.list` | edge（节点→Applet） | `query.protocol: string`; 外部 ID query 字段 | 无 | `realm_id: id?`; `exists: boolean`; `external_ref: object?` | 查询字段必须在 portal namespace 内。 |
| `ak.self.applet.install.command.preview` | self（管理员→Principal Server） | `applet_package`; `authoring_request_basis`（唯一内嵌 caller-signed registration/grant Events） | 无 | `{plan, authoring_request}`（契约 `applet-install-authoring.schema.json`） | Principal Server 重算 plan、限制短期 expiry 并签名；registration epoch evidence 只在 registration Event manifest，不属于 package digest / proof。 |
| `ak.edge.applet.install.command.author` | edge（客户端→Applet service） | `authoring_request` | 无 | `managed_actor_bundle` | Applet 验证 current Principal Server 信任与 exact bindings；四个 Applet/Bot Event 仅在 bundle 出现一次。 |
| `ak.self.applet.command.install` | self（管理员→Principal Server） | `Idempotency-Key`; `applet_package`; `authoring_request`; `managed_actor_bundle` | 无 | install / commit response 的完整 required 字段集合以 [`applet-schema.md` §1b](./applet-schema.md) 与契约 `applet-install-operations.schema.json` 为权威源 | 首次提交要求 authoring request 未过期；成功 exact replay 在过期后仍返回原 outcome；同 key 异 body 冲突。 |
| `ak.self.applet.revoke.command.preview` | self（管理员→Principal Server） | `path.applet_id`; `effective_scope`; `reason_code`; `revoke_mode` | 无 | `revoke_plan_digest`; `revoke_plan` | 只读枚举 exact revoke intents；见 §4b。 |
| `ak.self.applet.command.revoke` | self（管理员→Principal Server） | `header.Idempotency-Key`; `path.applet_id`; `revoke_plan_digest`; `effective_scope`; `reason_code`; `revoke_mode`; `capability_revoke_events[]`; `membership_state_events[]` | `proof?: AccountLifecycleProof` | `ok`; `operation_id`; `revoke_plan_digest`; `status`; `steps[]`; `revoked_refs[]?`; `rejected[]?` | caller-signed event-log saga；见 §4b。 |
| `ak.self.applet.ghost.command.provision` | self（已安装 Applet service→Principal Server） | `header.Idempotency-Key`; `path.applet_id`; `schema`; `applet_id`; `service_id`; `ghost_actor_id`; `actor_principal_server_id`; `realm_id`; `external_ref: {protocol,instance_id,external_id}`; `managed_actor_provision_event: Event`; `pcr_genesis_event: Event`; `accountability_grant_event: Event`; `profile_event: Event` | `display_name` | `ghost_actor_id: did_core_id`; `actor_principal_server_id: did_core_id`; `managed_actor_provision_ref: event_id`; `principal_control_realm_id: realm_id`; `profile_event_ref: event_id`; `accountability_grant_ref: event_id`; `authorization_ref: grant_id`; `display_name: string?` | active Applet registration service 以 RFC 9421 `service_signature` 提交闭合的 caller-signed 四 Event authority 单元并原子 provision Ghost Actor；`external_ref` 是 immutable tuple 唯一 carrier，字段、proof 与幂等规则见 §9.1。 |

### 7.1 Ping

```text
GET /_arkret/edge/applet/ping
```

返回：

```json
{
  "ok": true,
  "applet_id": "ak:applet:21532600-0000-7000-8000-000000000000",
  "service_id": "ak:did_core:webvh:z6Mkw8qTnL4rP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z",
  "protocol_version": "1.0"
}
```

### 7.2 Describe

```text
GET /_arkret/edge/applet/describe
```

返回 Applet 支持的协议、profile、namespace、最大交易大小和认证方式。

### 7.3 Transaction Push

```text
POST /_arkret/edge/applet/transactions
Idempotency-Key: <opaque-string>
```

Arkret Principal Server sync surface / Events API 向 Applet 推送事件批次。

请求示例（非完整 schema）：

```json
{
  "applet_id": "ak:applet:01904100-0000-7000-8000-aaaaaaaaaaaa",
  "source_service_id": "ak:did_core:webvh:z7SrvceTnL4rP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z",
  "events": [
    {
      "event_id": "ak:event:AQsHmGu_9sPOyJ4aG8VlWQBp8wGGhdC-BjfAaXqrIbk-",
      "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
      "kind": "ak.message.create",
      "actor_id": "ak:did_core:webvh:z2dmjZ8r7L4nP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z",
      "payload": {}
    }
  ],
  "signals": [
    {
      "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
      "scope_ref": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
      "sender_actor_id": "ak:did_core:webvh:z2dmjZ8r7L4nP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z",
      "sender_device_id": "ak:device:019640ed-8000-7000-8000-000000000001",
      "seal_ref": "ak:seal:sha256:2222222222222222222222222222222222222222222222222222222222222222",
      "signal_class": "session",
      "sent_at": "2026-07-30T12:00:00Z",
      "expires_at": "2026-07-30T12:00:30Z",
      "encrypted_payload": {
        "scheme": "ak.signal_exporter_aead.v1",
        "key_ref": {
          "algorithm": "MLS-EXPORTER-AEAD",
          "group_state_ref": "ak:event:AWn8zXw0Iuqoi0snySz3P5bT_ssUZS1nwhpXchPIvk48"
        },
        "purpose": "ak.signal.v1",
        "aead_profile": "MLS_128_DHKEMX25519_AES128GCM_SHA256_Ed25519",
        "epoch": 7,
        "nonce": "AAECAwQFBgcICQoL",
        "ciphertext": "AQIDBAUGBwgJCgsMDQ4PEA",
        "aad_digest": "sha256:3333333333333333333333333333333333333333333333333333333333333333"
      },
      "proof": {
        "kind": "detached_jws",
        "verification_method": "did:webvh:z2dmjZ8r7L4nP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z:alice.example#device-1",
        "envelope_digest": "sha256:4444444444444444444444444444444444444444444444444444444444444444",
        "created_at": "2026-07-30T12:00:00Z",
        "jws": "eyJhbGciOiJFZDI1NTE5In0..c2lnbmF0dXJl"
      }
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

- `Idempotency-Key` MUST 作为逐次 transaction push 的 nonce / idempotency key 使用，并进入 HTTP Message Signature transcript（见 §7.3.1）。
- 幂等 identity MUST 至少绑定 `(operation_id, direction, Source-Service-ID, Destination-Service-ID, Idempotency-Key)`；接收方的幂等记录 MUST 同时保存 canonical body digest / `Content-Digest` 与本次验签得到的 `delivery_authentication_record`。
- 相同幂等 identity、相同 canonical body digest 且相同 `delivery_authentication_record` 的重复投递 MUST 返回原 outcome 或等价成功，不得再次执行外部副作用。
- 相同幂等 identity 但 canonical body digest、source / destination service DID 或 `delivery_authentication_record` 任一不一致时 MUST fail closed；若认证先通过则返回 `duplicate_conflict`，若签名 / source 绑定先失败则返回 §7.3.1 的认证失败 reason。
- 单事件级别仍以 `event_id` 去重；重复 `event_id` 且内容一致 MUST `accepted`，内容不一致 MUST 拒绝。
- 幂等记录的保留窗口遵循 [`api-conventions.md` §6.1](../sync/api-conventions.md)：自记录创建起至少 24 小时，且不短于 §7.3.1 签名时效窗口加最大允许时钟偏移；本节不定义更短窗口。
- Applet SHOULD 先持久化幂等记录，再执行外部副作用。
- Applet MUST 验证 source service DID 和 HTTP message signature。
- Applet MUST 独立验证 event signature，不得只信任推送方。

#### 7.3.1 逐次投递来源签名（双向对称，normative）

transaction push 是 service↔service 调用，**两个方向**都 MUST 携带**逐次投递**的 RFC 9421 HTTP Message Signature（per-delivery source signature），接收方 MUST 在处理任何 event / 副作用前先验签；纯 `Authorization: Bearer`（无 `Signature`）的 transaction push MUST 被拒绝。两方向不可只靠 bearer，也不可只在首次握手时验签一次：

- **node → Applet**（§7.3 上文，Arkret 节点向 Applet 推送）：Applet 端 MUST 按 `Source-Service-ID` 的 accepted service key binding 取得当前有效 verification method，并逐次验证 HTTP Message Signature；逐次验签不等于逐次在线解析 DID。新 service / key、binding invalidation 或显式 freshness 失效时才进入 DID authority resolution。`Destination-Service-ID` MUST 等于接收 Applet registration 的 `service_id`。Applet registration 的 `webhook_auth` 在该方向声明 transaction endpoint 要求 `http_message_signature` 与可接受算法；`webhook_auth.key_ref` MUST NOT 被解释成任意 Arkret 节点的来源 key。
- **app/bridge → arkret edge inbound**（`POST /_arkret/edge/applet/transactions` 的入站方向，已安装 Applet service / bridge 向 arkret edge 推送外部网络 transaction）：arkret edge 接收方 MUST 先用 `Source-Service-ID`（service `did_core_id`）找到 §4b 接受的 active install 与当前 effective Applet registration，再要求签名 `keyid` / verification method 等于该 registration 的 `webhook_auth.key_ref`；接收方从该 DID URL 取得 bare controller `full_id`，用已登记 adapter 验证并要求 `project(full_id) == registration.service_id == Source-Service-ID`，不得把 full DID 与 core header 直接比较，并逐次验签。缺签名、签名无效、投影不一致、`webhook_auth.key_ref` 未被该 Applet service 当前状态授权或无 active install 时 MUST fail closed。

**覆盖 header 集（MUST，与 [`../sync/federation.md` §3.2](../sync/federation.md) service-to-service 签名对称）**：签名 transcript MUST 覆盖以下 RFC 9421 derived components 与 header：

- `@method`、`@target-uri`、`@authority`
- `content-digest`（按 [`../sync/service-http-binding.md` §2.5.1](../sync/service-http-binding.md) 覆盖 exact canonical HTTP content bytes；transaction push 总是带 body，故 MUST 携带唯一 `sha-256` member 的 `Content-Digest`）
- `source-service-id`（header `Source-Service-ID`，等于 body `source_service_id`）
- `destination-service-id`（header `Destination-Service-ID`，等于接收方 service `did_core_id`）
- `idempotency-key`（header `Idempotency-Key`；参与幂等 / replay key，MUST 进入 transcript）
- 签名 parameters MUST 含 `created` 与 `expires`；时效窗口判据沿用 [`../sync/federation.md` §3.2](../sync/federation.md)（`expires - created` ≤ 300s、`created` ±30s skew、`expires` 未过期），落在窗口外的逐字节重放即便 replay cache 已 evict 也 MUST 因 `created` / `expires` 校验失败而拒绝。

接收方 MUST 在 JSON 业务解析与验签前按 [`../sync/service-http-binding.md` §2.5.1](../sync/service-http-binding.md) 对 exact HTTP content bytes 重算并校验 `Content-Digest`，再严格解析并确认收到的 wire 本身就是 canonical JSON，最后验证签名 transcript；MUST NOT parse arbitrary JSON 后仅对 canonicalized value 求 digest。body 内 `source_service_id` MUST 与 header `Source-Service-ID` 及签名 transcript 一致。

**投递认证记录（normative）**：接收方在验签通过后 MUST 从已验证的 HTTP message、effective Applet registration 与实际 verification key 派生 closed `delivery_authentication_record`，并把该记录及其 digest 写入 transaction 幂等 / replay 记录；caller 不得提供或覆盖该值，它也不是 request body 字段。字段固定为：

```text
{
  operation_id, direction,
  source_service_id, destination_service_id,
  signature_label, verification_method, verification_key_digest, signature_algorithm,
  registration_epoch,
  idempotency_key, content_digest,
  covered_components, created, expires
}
```

- `operation_id` 固定为 `ak.edge.applet.command.transaction`；`direction` 只允许 `node_to_applet` 或 `applet_to_arkret_inbound`。
- `source_service_id` / `destination_service_id` 是已与 header、实际连接目标及 registration 交叉验证的 `did_core_id`。
- `signature_label` 是 receiver 选中并成功验证的 RFC 9421 signature label；`verification_method` 是 canonical DID URL；`verification_key_digest` 是 registered DID-method adapter 对实际 verification public key 的 canonical key bytes 所计算的 `sha256:` digest；`signature_algorithm` 是已登记的 canonical algorithm name。记录不复制随机或可变长的 `Signature` bytes。
- `registration_epoch` 是本次方向所使用的 effective Applet registration epoch；它必须同时承诺该方向适用的 `webhook_auth.key_ref` / algorithm policy。registration 不适用、已撤销或无法得到唯一 effective epoch 时不得形成记录。
- `idempotency_key` 是 header `Idempotency-Key` 的 exact value；`content_digest` 是通过 §2.5.1 profile 校验后的 canonical `Content-Digest` structured-field value，绑定 exact canonical body bytes。
- `covered_components` 按 receiver 实际验证的 `Signature-Input` 顺序保存 canonical lowercase component identifier，必须包含本节 required set；`created` / `expires` 是同一 signature parameters 中的整数 UNIX seconds。

记录使用 RFC 8785/JCS；不得增加 implementation-private 成员参与协议比较。其 digest 固定为：

```text
delivery_authentication_record_digest =
  "sha256:" + lowerhex(SHA256(
    UTF8("ak.applet.delivery-authentication-record.v1\n") ||
    RFC8785_JCS(delivery_authentication_record)))
```

receiver MUST 从本地派生记录重算 digest，不得信任 caller 或 cache 输入的预算值。幂等 / replay equality 是重算后的 digest 相等；实现私有 audit metadata 可以与记录并列保存，但不得改变该 equality。实现不得只用裸 `Idempotency-Key` 或 body 内 `source_service_id` 决定重复投递，也不得在 service DID key rotate、registration epoch 改变或 active install 撤销后把旧记录当成新授权。

`source_service_id` 只认证来源服务，不认证每条 durable Event 的业务 actor。arkret edge 把 Applet transaction 落为 Arkret Event 时，仍 MUST 对每条 Event 独立验证 `actor_id`、`applet_id`、`authorization_ref`、`external_ref` / provenance、`proofs[]` 与 registration `namespaces.actors` / capability grant；ghost actor、bot actor 或 delegated native actor 与 source service 不一致时 MUST fail closed（`applet_namespace_mismatch` / `capability_denied` / `applet_registration_unauthorized`，按失败层级选择）。

**失败码（normative）**：

- 缺 `Signature` / 纯 bearer：`unauthorized`（401，reason=`http_signature_required`）。
- 签名验证失败、`Content-Digest` header profile 不符合 [`../sync/service-http-binding.md` §2.5.1](../sync/service-http-binding.md)、digest 不覆盖 exact HTTP content bytes、wire 本身不是 canonical JSON，或 `source_service_id` 与 header / transcript 不一致：`unauthorized`（401，reason=`http_signature_invalid`）。
- `created` / `expires` 超出时效窗口（含 replay cache evict 后的窗口外重放）：`unauthorized`（401，reason=`signature_window_invalid`）。
- inbound 方向 `Source-Service-ID` 无 active effective install 或与 registration service DID 不一致：fail closed，reason=`applet_registration_unauthorized`（与 §4 / §4b 同门槛）。
- 幂等 identity 已存在但 canonical body digest 或 `delivery_authentication_record` 不一致：认证成功后 MUST 返回 `duplicate_conflict`；认证未通过时 MUST 优先返回对应认证失败 reason，避免泄露历史 transaction 状态。

transaction push 的逐次签名是传输层来源认证，**不替代** §8 每条 Applet-originated 写入 Event 的 envelope event signature（`proofs[]`）与 capability grant 校验：arkret 把外部 transaction 落为 durable Arkret Event 时，仍 MUST 按 §8 / §11 校验每条 Event 的 `actor_id` / `applet_id` / `authorization_ref` / `proofs[]`。

### 7.4 Query Actor

```text
GET /_arkret/edge/applet/actors/{actor_id}
```

用于 Arkret 节点发现 namespace 内的未知 Ghost Actor 是否存在。

返回：

```json
{
  "exists": true,
  "actor_id": "ak:did_core:webvh:z6MkGhostU123",
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
GET /_arkret/edge/applet/realms/{realm_id_or_alias}
```

用于查询 portal Realm 是否存在或可创建。

返回：

```json
{
  "exists": true,
  "realm_id": "ak:realm:Adoyg50aOV537gzxNy87EOdUlHiIujznqwZcMLSGFmzg",
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
GET /_arkret/edge/applet/protocols/{protocol}
```

返回：

```json
{
  "protocol": "slack",
  "display_name": "Slack",
  "icon_blob_ref": "ak:blob:sha256:...",
  "field_definitions": {
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
GET /_arkret/edge/applet/third_party/users?protocol=slack&team=T123&user=U123
```

```text
GET /_arkret/edge/applet/third_party/locations?protocol=slack&team=T123&channel=C456
```

用于把外部用户或 location 映射到 Arkret actor / portal Realm。

## 8. Applet 写入 Arkret

Applet 写入 Arkret MUST 使用常规 `/_arkret/self/events` submit 接口。

每个 Applet-originated 写入 Event MUST 包含下列 signed Event Envelope 字段（这些字段均进入 `proof.event_digest`；不得只放在 `unsigned` 中）：

- `actor_id`
- `applet_id`
- `external_ref`，若来自外部网络
- `authorization_ref`，但仅 §8 下述 service-actor 自署且部署未铸造 registration grant ref
  的例外 MAY 省略
- `proofs[]`

`authorization_ref` 的取值按事件签署主体区分：

- **Delegated-ghost / masquerading 事件**（`actor_id` 为 ghost / bot / delegated native actor，即 Applet 代表已授权 actor 署名的常见情形）：`authorization_ref` MUST 指向覆盖该 Event action / resource 的 active `ak.capability.grant`（见 [§9.1](#91-ghost-actor-provisioningakselfappletghostcommandprovisionnormative) 与 [§11](#11-masquerading-与-delegated-agent)）；`ak.identity.accountability_grant` 只证明责任归属，MUST NOT 被解释为 action authorization。
- **Service-actor 自署事件**（`actor_id` 为 Applet 自身的 service DID，如 portal strand 创建、`ak.applet.bridge_error` 审计等运维 / 审计事件，非委托 ghost）：此类事件不存在委托关系，`authorization_ref` MUST 指向该 Applet 的 registration grant（[§4](#4-applet-registration) Applet Registration 安装授权）而非某个 ghost 的 accountability_grant；若部署未为 Applet registration 铸造独立的 grant ref，service-actor 自署事件 MAY 省略 `authorization_ref`（签名的 `applet_id` 与 service-ID `actor_id` 已承载 provenance）。两类事件的 `applet_id` 均 MUST 携带。

示例：

```json
{
  "event_id": "ak:event:AQsHmGu_9sPOyJ4aG8VlWQBp8wGGhdC-BjfAaXqrIbk-",
  "realm_id": "ak:realm:Adoyg50aOV537gzxNy87EOdUlHiIujznqwZcMLSGFmzg",
  "actor_id": "ak:did_core:webvh:z6MkGhostU123",
  "actor_seq": 17,
  "kind": "ak.message.create",
  "applet_id": "ak:applet:21532600-0000-7000-8000-000000000000",
  "authorization_ref": "ak:grant:AU1_A5a8MMz_OdxEleQlWPFn-ljdJteaJv3ZZ9APkcrZ",
  "external_ref": {
    "protocol": "slack",
    "network_id": "T123",
    "event_id": "1714040000.000100"
  },
  "created_at": "2026-04-26T00:00:01Z",
  "prev_refs": [],
  "refs": [],
  "payload": {
    "strand_id": "ak:strand:AUPkhcWNNoG21KvR89voO-SRUnh1ZFG80N_5xygyYq0O",
    "track_name": "discussion",
    "content": {
      "kind": "ak.content.text",
      "body": "hello from Slack"
    }
  },
  "proofs": [
    {
      "kind": "detached_jws",
      "verification_method": "did:webvh:z6MkGhostU123:slack-bridge.example#key-1",
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
  "id": "ak:actor_profile:ARqc1CPEkB79f9R5Lv-dwsj7VZbUKXbAYPl3sEhUufeZ",
  "schema": "ak.schema.actor_profile.v1",
  "principal_id": "ak:did_core:webvh:z6MkGhostU123",
  "actor_kind": "integration",
  "display_name": "Alice on Slack",
  "accountable_principal_ids": [
    "ak:did_core:webvh:z6Mkw8qTnL4rP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z"
  ],
  "profile_fields": {
    "managed_by_applet": "ak:applet:21532600-0000-7000-8000-000000000000",
    "external_ref": {
      "protocol": "slack",
      "network_id": "T123",
      "user_id": "U123"
    }
  },
  "created_at": "2026-04-30T00:00:00Z"
}
```

`actor-profile.schema.json` 是 `additionalProperties:false` 的封闭 schema:`id`、`schema`、`principal_id`、`actor_kind`、`display_name`、`created_at` 为 required；问责只能通过 `accountable_principal_ids` 表达。本节初始 Profile 只列同一请求中 service-signed grant 已背书的外部 service DID；不得用 Applet registration 替代 controller 自己的 accountability grant 后把 controller DID 填入数组。Applet 托管标记 `managed_by_applet` 与外部网络来源 `external_ref` MUST 放入开放容器 `profile_fields`，不得作为顶层字段(否则被 schema `schema_violation` 拒绝)。与 §3.4 / §3.4.1 一致，不存在 `accountability` 嵌套对象 wire 形态。

Ghost Actor MUST NOT 被静默合并到 native DID，除非 native holder 显式声明并完成绑定。

### 9.1 Ghost Actor Provisioning（`ak.self.applet.ghost.command.provision`，normative）

bridge Applet 第一次遇到某个外部用户（典型触发：该用户在外部网络发出第一条需要桥接的消息）时，通过

```text
POST /_arkret/self/applets/{applet_id}/ghosts/provision
Idempotency-Key: <opaque-string>
```

请求 Principal Server 为该外部用户接受一个闭合的 Ghost Actor provisioning 单元。请求/响应契约以 [`applet-ghost-operations.schema.json`](../../artifacts/schemas/applet-ghost-operations.schema.json) 为权威（封闭 schema）；请求 `schema` 固定为 `ak.applet.ghost_actor.provision_request.v1`，必填 `actor_principal_server_id`，并携完整 caller-signed `managed_actor_provision_event`、`pcr_genesis_event`、`accountability_grant_event` 与 `profile_event`。

规则：

- 调用方 MUST 使用 active Applet registration service DID 的 RFC 9421 `service_signature`；签名逐字覆盖 method、target URI、authority、Content-Digest、Source/Destination-Service-ID 与 Idempotency-Key，并使用 registration epoch 内的 current verification method。HTTP 来源签名不替代四条 Event 各自的 proof。服务端 MUST 校验 active exact install、caller、registration、grant、Realm 与 `external_ref={protocol,instance_id,external_id}` 唯一tuple。`actor_principal_server_id` MUST 逐字等于本次接收/持久化操作的 Principal Server；v1 不支持伪装 remote hosting 的单阶段写入。
- provision payload role MUST 为 `ghost`，authority pair 未被使用，`initial_resolution.full_id` 的 adapter projection MUST 等于 `ghost_actor_id`，且该 full id（不是 core id）命中 actor namespace。Applet-managed principal 是长期可轮换的高风险 authority；v1 的 `method_history_evidence` MUST 为完整 `webvh_log`，服务端 MUST 独立验证 inception/current hash chain、SCID、controller proof、适用 witness threshold、freshness 与本地 trust policy。did:web snapshot 和 did:key expansion 均不得用于该字段；service attestation 不能代替 WebVH evidence。
- PCR genesis MUST 由 Ghost authority pair 建立 purpose=`applet_managed_control` 的新 Realm，critical ref 恰好指向同单元 provision Event，且 `initial_resolution`、Applet、grant、service 与 provision 逐字交叉绑定。durable Ghost record 保存 immutable provision/genesis anchors，不保存 current source ref。
- **Caller-signed proof contract（normative）**：Principal Server MUST NOT 构造、重建或以自身 notary key 代签任一 Event / payload proof。四条 Event 均由请求携带并按各自 authority 验证；accountability/profile 的 issuer、subject、registration-epoch key、`[service_id]`、external ref 与 critical accountability ref 约束保持不变。
- 创建单元四条 Event 的 `authorization_ref` MUST 逐字相同：provision 以它授权 `ak.applet.ghost.provision`；PCR genesis、accountability 与 Profile 只在这个 exact atomic aggregate 内以同一 ref 交叉绑定创建 authority/accountability 投影。该 ref MUST 指向 active exact install 为 `service_id` 签发、覆盖目标 Realm 的 `ak.applet.ghost.provision` grant；accountability grant 只记录责任关系，**不是**后续 Ghost Event 的授权。后续 Ghost 署名 Event 必须另按其具体 kind/resource 校验 Event 自带的 active capability grant（见 §8、§11）。
- 服务端 MUST 对四条 Event 执行 production proof、frontier/dependency、registration epoch、registry reducer 与 preflight 校验。仅 exact 四事件单元 MAY 在 unit-local overlay 中让后项引用前项；普通 submit 不得解析未 accepted ref。
- **失败原子性（normative）**：四条 Event、projection、Ghost record 与幂等结果 MUST 在同一 durable transaction 中提交；禁止逐条 fan-out。
- **hosting / federation（normative）**：四条创建事实只由 `actor_principal_server_id` 指定的接收 Principal Server 保存并重放，不生成 peer Event fan-out。`ak.peer.events.command.submit` 即使 transport/proof 合法也不是 `AppletFormal` admission，单独或普通 Realm bootstrap batch 提交该 PCR genesis MUST 以 `applet_managed_pcr_genesis_requires_closed_aggregate` 拒绝。Ghost 后续写入 Collaboration Realm 的普通 Event 才按该 Realm 的 federation 规则传播。
- 成功时服务端返回调用方所提交的 Ghost Actor `ak.profile.create` 与 `ak.identity.accountability_grant` durable refs；响应 `authorization_ref` 回显上述 provisioning capability grant，不得回显 accountability ref 冒充授权。
- 后续 rotation 使用普通 `ak.identity.resolution.update`，其唯一 predecessor/CAS 输入是 envelope `resolution_projection` 的 `head_eq`；payload 不镜像 previous ref。Package/Ghost record anchors 不随 rotation 改写，current 只从 `(actor_id, actor_principal_server_id)` 的 PCR cell 解析。
- 对任意 ingress（包括 actor 自签的普通 Event），receiver 一旦由 managed provision/PCR 识别该 authority pair，写入 admission MUST 与 active exact Applet registration、install grant 与 revoke fence 做 AND。Ghost 严格跟随所属 Applet lifecycle，v1 不定义第二套 per-Ghost revoke 状态或操作；Applet revoke 后 Bot 与全部 Ghost 立即拒绝新写，历史读取与 identity-resolution audit 仍可用。
- **幂等（normative）**：同一 `(applet_id, external_ref.protocol, external_ref.instance_id, external_ref.external_id)` 与同一 `Idempotency-Key` 的 exact replay（包含四条 Event 的 canonical bytes）MUST 返回既有 refs，不得重复提交。`external_ref`是唯一tuple carrier，请求不再镜像`protocol/tenant/external_user_id`。相同 tuple 或 key 携带不同 Event bytes / event ids MUST `duplicate_conflict`；`Idempotency-Key` 的保存必须与原子提交同事务。语义与 §7.3 相同。
- provision 不隐含任何 Realm membership 或 MLS 入组：ghost 加入 portal Realm 走常规 membership 流程，加入 E2EE group 还需 §12 的独立 E2EE 加入授权。

## 10. Portal Realm

Portal Realm 把外部 location 映射到 Arkret。

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

`ak.message.create` 的 payload 是封闭 schema，required `strand_id` + `track_name`（[`event-payload.schema.json`](../../artifacts/schemas/event-payload.schema.json) `message_create_payload`）。因此 bridge 把外部消息写入 portal Realm 前，MUST 先解析出一个**目标 strand**——外部 location 的映射单位是 `(realm_id, strand_id)`，不是裸 `realm_id`。

- 每个 portal Realm MUST 至少有一个用于消息桥接的 **portal strand**；线性聊天型外部 location（IM channel / group chat）默认一个 location 对应一个 portal strand。
- **获取/创建路径**：bridge 首次为某外部 location 建立映射时，MUST 按以下顺序确定 portal strand：
  1. 查自身持久化的 location ↔ `(realm_id, strand_id)` 映射；
  2. 映射缺失时，在该 portal Realm 内通过常规 projection / view 读取查找既有 portal strand（以 `external_ref` 中的 protocol / network_id / location_id 匹配）；
  3. 仍不存在时，由 bridge 以自身可署名身份提交 `ak.strand.create`（Event Envelope 顶层携带 signed `external_ref` 记录外部 location 出处），并把结果 strand_id 写入映射。
- **创建幂等**：并发或重试导致同一外部 location 产生多个 `ak.strand.create` 时，bridge MUST 以 effective 顺序最早的 strand 为 portal strand，多余 strand SHOULD archive；判定依据是 signed `external_ref` 的 location 等值，不得靠标题字符串猜测。
- **track**：桥接消息默认写入 `track_name="discussion"`；profile / Realm schema 声明其它 track 布局时按声明走。
- ghost 署名的桥接 `ak.message.create` MUST 把正文放进 payload `content`（或 E2EE 下 `encrypted_content`）的 `content_block` 形态，媒体引用走 `blob_refs[]`；不得把 content 级字段（`mimetype` / `filename` / `blob` 等）直接平铺为 payload 顶层字段——按 schema 强校验的节点会以 `schema_violation` 拒绝。

## 11. Masquerading 与 Delegated Agent

只有当用户或组织显式授予委托权限时，Applet MAY 代表 native 用户行事。

由此产生的 Event MUST 同时呈现：

- accountable actor：native actor
- executing applet / 委托密钥

示例 UI 语义：

```text
Alice via Calendar Applet
```

协议字段 **MUST** 包含：

```json
{
  "actor_id": "ak:did_core:webvh:z2dmjZ8r7L4nP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z",
  "executed_by": "ak:did_core:webvh:z9CalAppTnL4rP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z",
  "authorization_ref": "ak:grant:AU1_A5a8MMz_OdxEleQlWPFn-ljdJteaJv3ZZ9APkcrZ",
  "applet_id": "ak:applet:8a0baad5-6000-7000-8000-000000000000"
}
```

这些字段位于 Event Envelope 顶层并进入 canonical event bytes；实现 MUST NOT 把 `applet_id` 或 `authorization_ref` 降级为 `payload` 内业务字段或 `unsigned` hint。

**Reducer normative**:

- 当 Event 的 envelope signature 由 applet / delegated agent key 签发但 `actor_id` 指向 native principal DID 时（即 actor_id ≠ signing key 所属 DID），reducer MUST 校验：
  1. `executed_by` 必填，指向实际签发该 Event 的 applet / agent DID;`executed_by` 与 envelope signing key 的 DID 一致；
  2. `authorization_ref` 必填，指向已 accepted 的 `ak.capability.grant`(或等价 delegation event), 该 grant 把 actor_id 主体的某个 action 委托给 executed_by;
  3. `applet_id` 必填(在 Applet 模式下), 指向已注册的 applet;
  4. `executed_by` MUST 落在 `applet_id` registration 声明的主体集合内:即等于该 registration 的 service DID / `bot_actor_id`，或匹配其 `namespaces.actors` pattern(含 ghost DID namespace)。持有针对 `actor_id` 主体的有效 grant、但 `applet_id` 指向另一无关已注册 applet(其 registration namespace 不覆盖 `executed_by`)时，reducer MUST 拒绝，reason=`applet_namespace_mismatch`。**delegated 代表真人时收紧绑定粒度（normative）**：当 `actor_id` 指向 **native principal DID**（delegated 代表真人行事，而非 ghost 自署名）时，`executed_by` MUST 等于具体的已注册 service DID / `bot_actor_id`,**或一条已 provision（存在 active `ak.profile.create` + §9.1 `accountability_grant`）的具体 ghost DID**；此路径下 reducer MUST NOT 仅凭匹配 `namespaces.actors` wildcard pattern 通过（`applet_namespace_mismatch`）。`namespaces.actors` 通配匹配只对 **ghost actor 自署名**（`actor_id` 即该 ghost）路径有效。否则 applet 可在其自有 registration 声明的 namespace 通配下，用任意未 provision 的 ghost DID 自签 key 代表真人写入，削弱 §9.1 ghost provision 的问责闭环与审计归因。
  5. grant MUST 通过 [`constraint-schema.md` §7.3](../authz/constraint-schema.md) 的 `authority_control` + `constraint_subkind=applet_authority` 规范形绑定 `applet_id`、`executed_by` 与 `registration_epoch`，并由 grant `resources[]` 精确覆盖 producer-signed `scope_ref` 所指的 `effective_scope`。`registration_epoch` 是唯一安全 epoch 绑定键；reducer/verifier 必须展开 referenced registration 的 epoch evidence 并确认 DID Document digest、accepted signing key set 与捕获值一致。Applet key rotate、endpoint 变化或 registration 更新后，旧 grant 不得授权新 key。实现 MUST NOT 发明 `constraint_kind=applet_delegation_binding`、live-only authorization shadow 或其他 schema 外别名替代 durable grant。
- 缺少 `executed_by`、`authorization_ref` 或 `applet_id` 中任一字段时，reducer MUST `schema_violation` 拒绝。该规则适用于所有 `ak.profile.applet_*` profile，客户端 / SDK 不得退回到 SHOULD 形态。

Applet MUST NOT use masquerading to hide automation. 客户端 MUST 明确展示 `via applet`：UI 在渲染 mention、notification、audit log、moderation queue 等任何"who did this"上下文时，MUST 同时显示 native actor 与 `executed_by` 双重署名，不得仅显示 native actor 而隐藏 applet 身份。

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

**E2EE 加入授权（normative）**：Bot Actor 或 Applet-managed Ghost Actor 加入 E2EE Realm 的 MLS group（上文模式 1、2）MUST 经过独立的 **E2EE 加入授权**，该授权与普通的 capability grant（如 `ak.strand.create` / `ak.message.create` 等写入权限）**分立**：持有写入 capability 不自动授予把 applet / ghost 成员加入 MLS group 的权利。

- 该 E2EE 加入授权 MUST 由 Realm owner、Realm admin 或 Realm policy 明确授权的 authz service 签发（参照 §4 的 `applet_registration_unauthorized` 门槛），并落为携带 applet provenance 的可审计 Arkret Event（例如 `ak.member.state`，其 membership write 由 registry 派生），不得仅凭 Applet 自身 Welcome 入组。
- 缺少该独立 E2EE 加入授权时，Arkret 客户端 MUST NOT 把 applet / ghost 成员加入 MLS group，并 MUST 以 `applet_e2ee_join_unauthorized` 拒绝该加入。
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

`ak.profile.applet_service.v1` 的 base bot-only 基线 MUST 测试：

- registration 签名
- namespace 匹配
- transaction 幂等性
- transaction push 的逐次 `delivery_authentication_record`（§7.3.1）
- `Source-Service-ID`、`Destination-Service-ID`、`Idempotency-Key`、body digest 与 `delivery_authentication_record` 之间的幂等 / replay 绑定
- capability enforcement
- bot actor attribution
- 当实现暴露 self/admin Applet install 时，install preview / commit / revoke aggregate operation 的幂等性
- `ak.edge.applet.command.transaction` 只能作为 operation_id，绝不能作为 durable Event kind

`ak.profile.applet_bridge.v1` 继承 `ak.profile.applet_service.v1`，并且 MUST 额外测试：

- actor 解析
- Realm 解析
- protocol metadata
- Ghost Actor accountability
- portal Realm metadata
- duplicate external event 处理
- bridge error event 可见性

`ak.profile.applet_delegated.v1` 继承 `ak.profile.applet_service.v1`，并且 MUST 额外测试 delegated grant binding、`executed_by` / `authorization_ref` / `applet_id`、双签名 UI 归因以及 `registration_epoch` evidence 校验。

`ak.profile.applet_e2ee_join.v1` 继承 `ak.profile.applet_service.v1`，并且 MUST 额外测试独立 E2EE join authorization、MLS roster applet-managed 标记以及 `applet_e2ee_join_unauthorized`。

`ak.profile.applet_widget.v1` 继承 `ak.profile.applet_service.v1`，并且 MUST 额外测试 widget origin isolation、CSP、scoped token、consent 以及 host session / device-key 不披露。

## 16. v1 互操作要求

- `applet_registration` 的字段集由 [`applet-package.schema.json`](../../artifacts/schemas/applet-package.schema.json) 与 [`event-payload.schema.json#/$defs/applet_registration_payload`](../../artifacts/schemas/event-payload.schema.json) 固定（closed，`additionalProperties:false`），至少包含 service DID、`base_url`、namespace、protocol、`requested_scopes` 与 `webhook_auth` signing policy。它**不携带** capability refs 与 expiry：实际授权由独立的 `ak.capability.grant` 承载并有自己的 `temporal` 约束，registration 的时效由 `registration_epoch` 与 controller 的 revoke 表达。
- Namespace pattern grammar（命名空间模式语法）MUST 明确 actor、realm、handle、external protocol id 的匹配边界；namespace 命中不授予写权限。
- Transaction push 操作 MUST 包含 exact `applet_id`、`source_service_id`、`events[]`、`Idempotency-Key`、HTTP message signature 与 received_at audit metadata；**两个投递方向（node→Applet 与 app/bridge→arkret edge inbound）都 MUST 携带逐次投递 RFC 9421 来源签名并由接收方逐次验签，覆盖 header 集、失败码与认证记录见 §7.3.1**；纯 bearer 的 transaction push MUST 被拒绝。外部 source network、external event id、mapped actor、target Realm / Circle 与 operation refs 必须落在具体 Arkret Event 的 `external_ref` / provenance / capability refs 中，不得通过 transaction 专用 durable Event 表达。
- Protocol metadata schema（协议元数据 schema）MUST 声明外部系统、identity mapping、permission mapping、E2EE boundary、rate limit 和 supported media types。
- Bridge error event 使用 `ak.applet.bridge_error`，必须绑定 failed transaction、外部错误类别、是否可重试和可见范围；不得泄露未授权外部正文。
- External event deduplication key（外部事件去重 key）MUST 至少包含 protocol、tenant/workspace、external channel/location、external event id 和 normalized sender；不得只依赖时间戳或正文 hash。
- Applet UI widget sandbox MUST 与 Realm capability、origin isolation、CSP、token scoping 和 user consent 绑定；widget 不得直接获得 Arkret session token 或未授权 Event history access。该 sandbox 的字段与约束在 [§17 Applet UI Widget](#17-applet-ui-widget) 定义。

## 17. Applet UI Widget

部分 Applet 在 Arkret 客户端内嵌入 UI widget（如 Slack-style 交互卡片、配置面板）。Widget 在 host 客户端的信任边界内渲染，因此 MUST 被沙箱隔离。本节定义 §16 引用的 widget sandbox 的最小 normative 形态。

是否提供 widget 由 Applet 决定（可选）；但**若 Applet 提供 widget，则其 widget 声明（registration、package manifest 或 describe 响应内）MUST 通过 `ak.schema.applet_widget_declaration.v1` 校验**（[`applet-widget-declaration.schema.json`](../../artifacts/schemas/applet-widget-declaration.schema.json)）并包含下列全部 required 字段。顶层的可选性仅限"是否提供 widget"这一选择，不得用于省略已提供 widget 声明中的任一 required 字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `widget_origin` | `string`（origin） | required | Widget 内容来源 origin（scheme + host + port）。host 客户端 MUST 在隔离 origin（iframe sandbox 或等价机制）内加载 widget，MUST NOT 在 host 客户端自身 origin 下执行 widget 代码。**出站目标校验（normative）**：`widget_origin` 的 scheme MUST 为 `https`（本地开发例外须 deployment policy 显式声明），且 host 客户端在加载前 MUST 对其 host 执行 [`../sync/api-conventions.md` §11.2](../sync/api-conventions.md) 的出站网络目标策略——命中 loopback / private / link-local / cloud-metadata（如 `169.254.169.254`）等禁止地址类别时 MUST NOT 加载该 widget。否则恶意 applet 可把 `widget_origin` 指向内网 / metadata 端点，借用户浏览器发起 client-side SSRF（内网存活探测、计时侧信道）。 |
| `csp` | `string` | required | 适用于 widget 文档的 Content-Security-Policy。host 客户端 MUST 强制该 CSP，并 MUST NOT 放宽到允许 widget 访问 host 客户端的 DOM、storage 或 session。 |
| `token_scope` | `object` | required | Widget 可用 token 的 capability scope（action / resource selector / realm_ids / expiry）。该 token MUST 是为 widget 单独签发的 scoped token，scope MUST NOT 超出本字段声明的范围。 |
| `consent_required` | `boolean` | required | 是否需要在加载前向用户展示 consent / capability 摘要。 |

约束（normative）：

- **Origin 隔离**：widget MUST 在与 host 客户端隔离的 origin 中运行；host 客户端 MUST NOT 把自身 origin 的 cookie、localStorage、IndexedDB 或 in-memory session 暴露给 widget。
- **Token scoping**：host 客户端 MUST NOT 把 Arkret 用户的 session token 或 device key 传给 widget；widget 只能拿到为其单独签发、scope 收敛到 `token_scope` 的短期 capability token，且该 token MUST NOT 超出 widget 声明的 scope。
- **History 读取不可越权**：widget MUST NOT 通过任何接口读取超出其 capability scope 的 Event history；host 客户端 MUST 以 widget 的 scoped capability 为准做 history 访问授权，未授权范围 MUST 拒绝。
- **写入同样不可越权（防 confused-deputy）**：所有经 widget scoped token 发起的调用——无论 read 还是 write——node / host MUST 以该 scoped capability 授权，MUST NOT 回退到 host 用户的 full session 权限。任何经 widget scoped token 的 Event submit / 副作用写入，其授权范围 MUST 受 `token_scope` 约束并 MUST NOT 超出；若写入路径回退到 host 用户 full session，widget 即可借宿主越权写入，构成 confused-deputy，MUST 拒绝。
- **Consent**：`consent_required=true` 时，host 客户端 MUST 在加载 widget 前向用户展示其 origin 与请求 scope，未获 consent MUST NOT 加载。
