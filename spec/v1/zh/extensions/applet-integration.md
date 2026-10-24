---
title: Applet Integration
status: candidate
normative: true
stability: v1
updated: 2026-10-17
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
| user namespace regex | 外部 Realm／handle 路由与 accepted actor 管理关系 |
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

Applet 创建的 Bot 是 [Realm 受管主体](./realm-actors.md)，持有独立 DID 和自己的 Device，
完整身份为 ActorId.realm。它属于固定 Realm，由该 Realm 当前治理 Station 接纳授权与控制事实。
Applet 保管控制／Device 私钥，无须提供 Station 账号服务；没有 Bot Account 或独立 PCR。
安装不自动创建 Bot。管理员主动创建、自动 Ghost 许可与逐候选 review 按 Realm actors §3 执行。

### 3.4 Ghost Actor

外部网络用户在 Arkret 中的镜像 Actor。例如 Slack 用户 `U123` 映射为一个独立 Actor DID：

```text
did:webvh:z6MkGhostU123:slack-bridge.example:ghost:u123
```

`#fragment` 只用于 DID URL 形式的 verification method（例如 `did:webvh:z6MkGhostU123:slack-bridge.example:ghost:u123#key-1`），不得作为 `actor_id` / `bot_actor_id` 的一部分。稳定 `actor_id` 使用 `realm` 分支，完整 `realm_actor_id` 同时包含不可变的所属 `realm_id` 与独立 DID 的 adapter projection `principal_id`（例如 `ak:did_core:webvh:z6MkGhostU123`）；当前治理 Station 不进入该身份，治理交接不改变它；每个 Ghost 必须有自己的 validated SCID，不能复用 Applet service SCID 后仅靠 host/path 区分。

**Ghost DID 与托管边界（normative）**：每个 Ghost 的 validated SCID 必须独立于 Service/controller。Bot 与 Ghost 均依 [Realm actors §1／§7](./realm-actors.md) 验原生 inception、portable、日志连续性和持钥授权。DID 托管可与 Applet Service 异域，不要求额外路径或 actors namespace；共享托管域名不产生受管主体的排他占用。归属仅由 accepted create 与唯一 current manager 建立，不能靠地址相同认领。

Ghost 使用与 Bot 相同的 realm_control 创建合同，role 固定为 ghost，必须逐字绑定 external tuple。
namespace 对原生方法证据验证的 initial_resolution.did 匹配，不对 core 匹配；不得从 tuple 或 Service DID 生成主体 DID。
创建不产生 Profile 或 accountability grant。外部 tuple 由不可变创建身份记录承载；Profile 不承担身份或管理来源证明。

#### 3.4.1 Agent、Bot 与 Ghost Actor 边界

`Agent` 恰好指 controller 通过 `ak.self.agent.command.provision.v1` 创建的一等个人 Agent，其 Actor Profile
使用 `actor_kind="agent"`。Applet 创建或托管的 AI/automation 是 `Bot`，其 Profile MUST 使用
`actor_kind="bot"`，不得借用 Agent 分类。Ghost Actor 只表示外部主体镜像 provenance，不是
`actor_kind`：外部账号/集成镜像的 Profile 使用 `actor_kind="integration"`，外部 Bot 镜像 Profile 使用
`actor_kind="bot"`，不得使用 `agent`。Applet service 自身直接行动时由 `ActorId.service` 与 registration
证明，Profile 可使用 `actor_kind="service"`。这些 Profile 值都不授予 authority；四者的 principal、
lifecycle、provisioning / registration 与治理路径不得合并。

Agent（见 [`../identity/key-management.md` §3.6.1](../identity/key-management.md)）与 Applet-managed Bot/Ghost
Actor 是不同 actor，生命周期与治理路径完全分离：

| 维度 | Agent | Applet-managed Bot / Ghost Actor |
| --- | --- | --- |
| 创建路径 | controller 先生成、签署并发布不含 PCR binding 的 Agent DID entry 0；`ak.self.agent.command.provision.v1` prepare 只验证其 accepted `initial_resolution` 与 delegation，不生成 DID/私钥或分配 PCR id。controller 把该承诺写入本地冻结的 Agent PCR genesis并取 `retype(event_id)`，再提交唯一 controller-signed `ak.agent.provision` Event，在一个 reducer transaction 原子派生 provision/accountability/selector/realm-id-claim projection；必填 `requested_scope` 只建立 immutable 全局 ceiling，不生成 `ak.capability.grant`。PCR genesis 在另一次提交 accepted 后 outcome 为 `awaiting_did_binding`；controller 以预承诺 key 发布 create-locked entry 1，accepted 后才 `complete` 并暴露 pairing/list/get。Profile、恢复备份与首次 `ak.agent.key.authorize` 继续独立提交 | 先安装独立 Service；再由 Service 原签 `ak.realm.actor.create`，候选主体以独立控制方法证明持钥，治理站原子接纳到所属 Realm 的 `realm_control`；没有 Account／PCR 聚合，Profile、Device、成员和业务 child 均独立建立 |
| Actor Profile `actor_kind` | `agent` | Bot 为 `bot`；外部账号/集成 Ghost 为 `integration`；外部 Bot Ghost 为 `bot`；不得为 `agent`；仅作分类，安全 provenance 仍由对应 provisioning / registration 证明 |
| `accountable_principal_ids` | 指向 controller principal，显式 `ak.identity.accountability_grant` | Realm Profile 不得携此字段；不可变创建来源由 `realm.actor.create` 证明，当前管理关系由 `realm_actor_manager` 证明，不使用账号 accountability grant |
| Runtime credential | 通过 `POST /_arkret/gate/account/agent-key-pair` pairing 得到 `ak.agent.key.authorize` 绑定的 key | Service 管理调用使用自己的 RFC 9421 签名；主体控制操作使用当前 accepted control 方法；业务与 E2EE 使用主体独立 Device 和 §16 的 Realm 身份 HTTP 分支；widget 另用 §17 的 scoped token |
| Session 路径 | `POST /_arkret/gate/account/session-grants` + `proof.proof_kind="agent_key_proof"` | Realm Bot／Ghost 无 SessionGrant，不借普通 Account 或个人 Agent 登录；Service、control 与 Device 凭据互斥，各按实际操作验独立权限，业务仍核当前安装、grant、双 gate 与 Device generation |
| 撤销 | `ak.self.agent.command.pause.v1` / 单一 `ak.self.agent.command.deactivate.v1` lifecycle Event；terminal parent gate 使 child authority ineffective，cleanup 非前置 | 安装／业务 grant 撤销阻断对应 scope 的新业务；owner／governance gate、Device 撤销、代次重置与独立恢复许可分别执行；不因卸载抹掉身份或历史，也不隐式恢复业务 |
| Realm policy | Realm policy MUST 单独允许 Agent（`ak.profile.agent_provisioning.v1`） | Realm policy MUST 单独允许 Applet base Bot-only（`ak.profile.applet_service.v1`）；Ghost Actor / portal bridge 需额外声明 `ak.profile.applet_bridge.v1` |

**Realm policy MUST 至少能分别控制 Agent、Bot 与 Applet/Ghost provenance**：部署可以禁止用户创建或使用 Agent，同时允许管理员安装 Applet Bot/Ghost Actor，也可以反向配置；这些类别不得被合并为一个不可区分的 "automation allowed" 开关。

`ak.profile.agent_provisioning.v1` / `ak.profile.agent_sidecar.v1` 只覆盖 Agent 路径；Ghost Actor / Bot 不走 Agent provisioning，也不得进入独立 Sidecar 对象的 desired/effective access。

面向 Realm 全体成员、并由组织或 Realm 运维的知识库问答、moderation、workflow 等共享机器人，不得建模为“没有 owner 的 Agent”。Agent 必须有可验证的人类 / 组织 controller，且不能脱离该 controller 的 Realm membership 单独存留。此类共享机器人 MUST 作为管理员安装的 Bot 接入：Applet service / registration 是其 lifecycle 与 accountability 根；只有需要代表外部网络中多个独立主体时才进一步 provision Ghost Actors。单一共享 Bot 不需要为了满足该规则虚构一个 Ghost Actor。

### 3.5 Portal Realm

外部网络 location 在 Arkret 中的镜像 Realm。例如 Slack channel、Discord guild channel、GitHub issue discussion。

## 4. Applet Registration

Applet MUST 有签名 registration。注册材料 MAY 由 Realm owner、组织管理员或 registry 验证；formal Realm Event 的准入与 capability 判定由 controlling Station 负责。

Applet 进入某个 Realm 的 capability MUST 由该 Realm owner、Realm admin 或 Realm policy 明确授权的 administrator actor 签发，并由 controlling Station 的 authorization capability 校验。仅凭 Applet 自签 registration、namespace claim 或外部 registry 收录不得写入 Realm；缺少该 grant 时，任何 Applet 通过 transaction push、Event submit 或 delegated signing 引入的 Realm 写入 MUST 拒绝，code=`applet_registration_unauthorized`。

**机读授权门(normative)**：上述"由 Realm owner/admin 授权 install / grant"绑定到机读 capability gate——`ak.applet.registration` 是 `ak.realm.admin` capability action 的目标 event kind(见 [`capability-action-registry.json`](../../artifacts/registry/capability-action-registry.json) 中 `ak.realm.admin.target_event_kinds`)。提交 formal fixed set 的 admin actor MUST 持有覆盖目标 Realm 的 active `ak.realm.admin` grant；Station 的 authorization capability 负责校验该授权，内部 worker 不产生独立 wire role 或替代授权门。reducer 校验失败时整个本地事务 MUST 拒绝，code=`applet_registration_unauthorized`。`ak.applet.registration` 在数据面仍是 `service_attested`(注册载体真实性),`ak.realm.admin` 门控的是"谁有权安装"，二者并存:注册被服务背书不等于被授权安装。

示例：

```json fragment
{
  "kind": "ak.applet.registration",
  "applet_id": "ak:applet:21532600-0000-7000-8000-000000000000",
  "service_id": "ak:did_core:webvh:z6Mkw8qTnL4rP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z",
  "expected_revision": null,
  "controller_principal_id": "ak:did_core:webvh:z2dmjQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn",
  "base_url": "https://slack-bridge.example/applet",
  "claimed_profiles": [
    "ak.profile.applet_service.v1",
    "ak.profile.applet_bridge.v1"
  ],
  "protocols": [
    "slack"
  ],
  "namespaces": {
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
    "ak.applet.bridge_error",
    "ak.morph.create",
    "ak.message.create",
    "ak.relation.create"
  ],
  "registration_epoch": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "webhook_signature_policy": {
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
- `service_id` MUST 是稳定 service `did_core_id`；注册时提供的 `did` 必须经 adapter 投影到它，当前endpoint通过method验证的DID服务入口取得并绑定package的HTTPS base_url。
- `controller_principal_id` MUST 是 controller `did_core_id`；复制到 registration 的 package proof VM 的 bare `did` 必须经 adapter 投影到它并通过签名验证。
- Realm 主体归属只从 accepted realm.actor.create 和 current manager 验证；registration不钉住默认Bot，Service不能成为同主体Bot。
- `claimed_profiles` MUST 从已验证 package 原样复制到 durable registration，至少包含
  `ak.profile.applet_service.v1`；profile-bound authority 只读取 accepted Event，不得读取
  preview/package cache。
- `namespaces` MUST 明确声明，不能默认为全网。
- exclusive namespace 冲突时，registry 与执行安装准入的 Station MUST 拒绝后注册者，code=`applet_namespace_conflict`；冲突判定算法（含通配符对通配符）以 [`applet-schema.md` §2.1](./applet-schema.md#21-exclusive-namespace-冲突判定normative) 为唯一规范源。剩余 Realm／handle namespace 的每条 pattern MUST 满足 [`applet-schema.md` §2](./applet-schema.md#2-namespace-pattern) 的形状约束，否则 code=`applet_namespace_pattern_invalid`。
- `requested_scopes` 只是请求权限，不是实际授权。
- 实际权限 MUST 通过 capability grant 授予。
- `registration_epoch` MUST 进入 payload required 字段，并严格按 [`applet-schema.md` §1.0.1](./applet-schema.md#101-registration_epoch-transcript-与计算算法normative) 的 closed transcript、集合排序、JCS、域分离与 SHA-256 步骤覆盖 canonical derived registration、service DID Document digest/version evidence、accepted signing key set、endpoint/auth material。grant 存储与匹配只绑定该 epoch；reducer/verifier 仍 MUST 展开已接纳的 epoch evidence，校验其 DID Document digest / signing key 与 epoch 捕获值一致。初次接纳、续订、已知失效与明确 current 操作按 applet-schema 的刷新规则验证；同 accepted epoch 的普通发送不要求重新在线解析 DID。
- `proof` MUST 是已验证 package controller DID detached proof 的逐字副本，`payload_digest` 覆盖 canonical package（不含 package `proof` 自身）；空对象、旧 `event_digest` 或与同一安装 package 不同的 proof MUST 以 `schema_violation` / `proof_invalid` 拒绝。formal registration Event 由安装管理员自己的 Event proof 覆盖，并由接收 Station 加 admission proof；不得把 package proof 当作 Event proof。

## 4a. Applet Package 与安装聚合操作

开发者发布 Applet 时 SHOULD 发布 controller-signed **Applet Package**。Package 是分发对象，不是 Realm history event；进入协议事实前 MUST 派生为 `ak.applet.registration` payload，并由获授权的 Realm administrator actor 通过 Station 的安装聚合操作签发实际 grant。

Package 最小字段以 [`applet-schema.md` §1a](./applet-schema.md#1a-applet-package-schema) 的字段参考表为唯一规范源；本节不重复维护字段表。Package MUST NOT 自行授权写入 Realm。Package 接受、registry 收录、namespace claim 或 `requested_scopes[]` 出现某 action 都不得被 reducer 解释为 grant。`registration_epoch` MUST 随 claimed profiles、namespace、base URL、webhook auth、endpoint key、requested scopes、widget origin、E2EE request、receive/rate-limit 行为或 DID/key evidence 改变而改变。

Package -> registration 派生映射同样以 [`applet-schema.md` §1a](./applet-schema.md#1a-applet-package-schema) 的映射表为唯一规范源。本节只补充安装语义：派生出的 registration 成功写入仍不授权；只有随后签发的 grant 与 `(applet_id, service_id, effective_scope, registration_epoch)` 绑定并保持 active，Applet 才取得对应 scope 的 effective install。

registration 的历史资格使用 [current-state §2](../sync/current-state.md#2-领域-selector-与-revision) 的 `applet_registration` 实例。连续重申同一 registration_epoch 及全部 security bindings 不产生新实例；真正替换时关闭旧实例，改回相同业务值仍是新的 Event 实例。旧实例被关闭排除的 Event 不因同 epoch 再出现而复活。effective install 另展开实际 grant、scope、membership 与 controller 等依赖，不能合成 install generation 或以 service-local fence 冒充已确认 revoke。

## 4b. Install Preview / Commit / Revoke

Service安装与managed主体创建 **MUST** 分离。安装只在一项exact effective_scope接纳管理员原签的
`ak.applet.registration`与实际`ak.capability.grant`；它不创建Bot/PCR/Profile、不要求默认Bot、不直接改写其它scope的grant。同 Service 登记替换对其它scope的epoch依赖失效，必须按下文预览并分别重新授权。
registration不携bot_actor_id或applet_actor_id。一个Applet可管理0..N独立Bot及Ghost，inventory从accepted provision派生；
新增主体不改变Service registration epoch。

preview使用`ak.self.applet.install.command.preview.v1`，输入package与closed管理员install basis，返回canonical InstallPlan。
InstallPlan 的 `approved_scopes[].constraints` 是对应 scope 的 canonical `GrantConstraint[]`；预览、摘要和提交 MUST 保留每项原始约束，不得提升为未限定 scope 的根字段或跨 scope 合并。`planned_events[]` 仅携带已登记 durable `event_kind` 与其对应 payload 的闭合联合，不是已签名的 `event_submission`，不得带 envelope、proof 或 HTTP 元数据。
commit使用`ak.self.applet.command.install.v1`，携同一输入、plan_digest及Idempotency-Key；
Station重算plan、package/controller proof、epoch/DID endpoint、安全网络目标、namespace、当前治理与管理员ak.realm.admin。
basis.registration_event、capability_grant_events的Event bytes、issuer和actor **MUST** 是同一真实管理员原签，
Station不得代签或重写。各grant的concrete subject **MUST** 是本Service ActorId.service，范围不超过审批与exact install。
失败零写；registration/grants、projection、幂等accepted outcome同一耐久事务可见；相同canonical请求恢复原结果，异内容duplicate_conflict。
安装不需要先调用managed author接口，也不生成一个不存在的Bot signer context。

有效安装键是`(applet_id,service_id,effective_scope)`。realm scope只含kind/realm_id；circle还含circle_id；
不同scope拥有独立grant、current资格和撤销，不复用另一个scope的authority。安装主体必须是scope当前governance Station；
跨Station安装不是一个分布式原子事务。重申同一registration epoch仍按registration实例/current规则，替换关闭旧实例；
旧失效Event不得因业务值相同而复活。

Bot/Ghost创建分别使用已登记的bot／ghost preview与provision operation（见§9.1）；创建许可为
ak.applet.bot.provision／ak.applet.ghost.provision，由实际scope当前合法Realm issuer授予Service。
Realm admin可通过profile明确登记的创建action初始签发规则批准这两项；只拥有creation grant不能下放业务权限。
每项创建grant和业务parent均带applet_authority，exact applet/service/epoch，遵循[精细治理](../authz/managed-governance.md)。

revoke preview／commit沿既有AppletRevokePlan、caller原签revoke Events、exact grant revision、membership FSM及幂等saga。
preview **MUST** 枚举本Service与scope所有实际parent/child/member/widget效果，不能只列一个默认Bot。成员移除另核其当前管理关系和真实准入来源；已转交到另一 Service 的主体不得仅因旧创建／旧 parent 历史而被原 Service 的卸载移出。旧 parent 撤销仍只消除依赖它的业务资格。
撤销该scope的parent/install即时fence该scope未来业务及群材料，不等待每个child或设备分别revoke；
保留其它scope独立合法路径。密码学移除另经MLS，不抹除历史Account或已交付内容。

registration current 在 Realm 内按 `(applet_id, service_id)` 独立定位。registration Event 的 scope_ref 与 current source_stream_ref **MUST** 为所属 Realm stream；Circle 安装也只在该 Realm stream 写登记，grants 的 resources 和实际 effect 仍严格受该 Circle effective_scope 限制。一个治理事务接纳登记与 scope grants，不从不同 Circle stream 的位置推导全局登记次序。管理员签名的 registration payload **MUST** 带 `expected_revision`：null 仅表示该 Service 从未登记，否则须等于该对的 current revision；它不进入 publisher package 或 registration_epoch。管理员通过原 exact current read 按该 selector 取前态，仍核目标 Realm 的 ak.realm.admin；缺项只能在完整历史证明下返回 never_written。首次并发登记或旧前态提交只有一个可接受，失败零写；exact 已接受请求重试恢复原结果。连续同 epoch 且全部安全绑定相同的重申保留原授权实例的起点，其它更新只关闭本 Service 的旧实例。实例连续性不等于 current revision 不变：每个新接受的登记 Event 都按 set 投影更新 current snapshot／source／revision；只有原 Event／原请求的 exact 重试复用原结果。

同 Applet 新 Service **MUST** 验 package proof 的 controller_principal_id 与原已验证 Applet 发布者相同及其当前合法签名权；仅相同 AppletId、名称或取得数据库副本不能通过。新增 Service 不修改旧登记／epoch，也不继承旧安装或 grants。同 Service 更新若使其它 scope 的旧 epoch 业务失效，preview warnings **MUST** 明示该 Service 实际受影响的 scope；scope 独立重新授权，不得影响另一 Service。

InstallPlan、revoke 请求／计划、Bot preview 和配置 intent **MUST** 明确 service_id，且与 basis、package、原签 Event、plan digest、原意图及目标 endpoint 一致。Ghost preview、authority material 与入站 transaction 的 Service 唯一取自已认证 HTTP 来源；material outcome 回显该 Service，current_binding 只判断它自己的 scope。配置已有主体另核其 accepted manager；new_bot 的选择由 intent.service_id 固定，执行／重试不得改投“最新”Service。portal、widget 与非主体 transaction 亦按实际安装与来源选择，不向多个 Service 广播私有内容。配置意图的 Service 一旦固定，不能通过重试改写。非主体 alias／namespace 命中多个 Service 时，调用者必须先选定已有的精确 Service 安装；未能消歧则拒绝，不取首条、不以最新登记裁决归属。目标 Service 仍由实际 endpoint 和已签 Destination-Service-ID 绑定。

精确 installation Policy target **MUST** 包含 Service；明确的全 Applet／Realm Policy 和聚合 quota 继续覆盖所有 Service，不因多登记重置额度或规避 deny。省略 Service 的精确撤销请求不合法，不解释为撤销全部。Ghost tuple 唯一键继续为 Realm＋Applet＋protocol／instance／external_id，Bot 创建幂等继续为 Realm＋Applet＋request_id，不增加 Service 维度；并发只能创建一个身份。其它 Service 查询同 tuple 不取得私有原件或管理资格，只有当前 caller／原意图有权的结果可交付，不能借 duplicate 恢复泄漏另一 Service 的结果。

## 5. Namespace

Namespace 用于决定：

- 哪些 Realm / portal alias 属于 Applet
- 哪些外部主体与位置可由 Applet 映射；namespace 不授权把群内容投递到 base_url

Namespace 不等于 capability。  
Namespace 命中只表示“这个 Applet 是该名称空间的处理方”。

**Namespace 命中不是归属证明（normative）**：namespace 命中只是**路由与排他判据**，**MUST NOT** 被解释为归属证明或授权。managed actor（Bot / Ghost）的归属由已接受的 `ak.realm.actor.create` 证据建立（§9.1）；凡该证据可达的判定点，实现 MUST 展开并校验该证据，MUST NOT 以 pattern 命中替代。

namespace 仅用于路由候选和 exclusive 冲突检测，不证明主体已创建或已获授权。治理方从自己的私有控制流核验完整 RealmActorId 与当前 manager；获准业务接收方只取得必要历史 signer fact，不以 namespace 替代原件与当前授权。

该总则与 [`../authz/constraint-schema.md` §7.3](../authz/constraint-schema.md#73-applet-授权绑定constraint_subkindapplet_authority)（grant 的 `executed_by` 不得仅凭 namespace wildcard 签发）以及 §11 规则 4（delegated 代表真人时不得仅凭 wildcard 命中通过）的既有收紧一致；那两条是本总则在具体路径上的实例，不是例外。

### 5.1 Actor Namespace

Actor DID namespace 不属于 v1 Applet package／registration；`namespaces` 只含 realms 与 handles，携 actors（包括空数组）是未知字段并 MUST 拒绝。Realm Bot／Ghost 依 accepted create 与 current manager 判归属，不以 DID 地址匹配、排他占用或接管名单判定。普通账号委托继续核完整 Account、实际 executor、本人 grant 与全部授权上界，不新增账号域名限制，也不允许 Applet 查询或接管普通账号目录。

### 5.2 Realm Namespace

Realm namespace 适用于 portal Realm。

```json fragment
{
  "exclusive": true,
  "pattern": "slack:team:*:channel:*"
}
```
### 5.3 Handle Namespace

Handle namespace 适用于外部用户或 location 的人类入口。

```json fragment
{
  "exclusive": false,
  "pattern": "slack.acme.example/*"
}
```
## 6. Applet Capability

注册 Applet 后，Realm owner 或组织管理员 MUST 显式授予 capability。

示例：

```json fragment
{
  "issuer": "did:webvh:z2dmjQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn:acme.example",
  "subject": "did:webvh:z6Mkw8qTnL4rP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z:slack-bridge.example:bot",
  "claim_scope": {
    "realm_ids": [
      "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5"
    ],
    "actions": [
      "ak.strand.create",
      "ak.applet.bridge_error",
      "ak.morph.create",
      "ak.message.create",
      "ak.relation.create"
    ]
  },
  "constraints": [
    {
      "constraint_kind": "scope_limitation",
      "effect": "allow",
      "allowed_data_labels": [
        "public",
        "internal"
      ]
    }
  ],
  "expires_at": "2026-07-26T00:00:00Z"
}
```
scope 限制 MUST 只使用 [`authz/constraint-schema.md`](../authz/constraint-schema.md) 登记的 `scope_limitation` 字段（如 `allowed_data_labels` / `allowed_endpoints` / `allowed_*_container_refs` 等）；与具体 Applet install 的安全绑定 MUST 另外使用标准 `constraint_kind="authority_control" + constraint_subkind="applet_authority"`，完整携带 `applet_id`、`executed_by`、`registration_epoch`。创建 grant／Service 业务 parent 的 executor 为 accepted Service ActorId；受管 terminal child 的 executor 为其具体 Bot／Ghost Realm actor subject，唯一受限重绑定与普通收窄按 [managed-governance §4](../authz/managed-governance.md) 校验。§5.1 accepted 主体／受管 current manager 与 §11 Event envelope 的 `applet_id` / `authorization_ref` 是使用时的交叉校验，不能替代 grant 自身的绑定。

除非 Applet 拥有 effective grant，或以委托授权身份显式代表已授权 actor 行事（此时 MUST 满足 [§11](#11-masquerading-与-delegated-agent) delegated agent 的全部字段 `executed_by` / `authorization_ref` / `applet_id` 与对应 reducer 校验），否则 Applet MUST NOT 向 Realm 写入。

## 7. Applet API

Applet API 是 Arkret 节点调用 Applet 的接口。  
Applet 调用 Arkret 节点时使用常规 Events API / Station sync surface / authz API。

Base URL 来自 registration 的 `base_url`。

**出站网络目标策略（normative，SSRF 防护）**：node 在向 Applet registration `base_url` 主动出站（transaction push、ping、describe、resolve 等任意 server-side fetch，含 redirect / Alt-Svc 后实际目标）之前，MUST 执行 [`../sync/api-conventions.md` §11.2](../sync/api-conventions.md) 出站网络目标策略；命中云 metadata / 内网 / 回环等禁止地址类别时 MUST 拒绝出站，`base_url` / webhook endpoint 的 scheme MUST 限 `https`。§4b registration preview / commit 时 MUST 对 `base_url` / webhook endpoint 预检该策略。§7.3.1 的逐次来源签名只证明"是这个 Applet"，不证明"目标 IP 合法"，二者 MUST 同时满足。

**`ak.applet.*` 标识符的两类用途（normative 区分）**：`ak.applet.*` 前缀的标识符根据上下文分属两个互不混淆的命名空间，实现不得把二者当作同一对象：

- **Event kind（进 Realm history）**：`ak.applet.registration` 与 `ak.applet.bridge_error`。这些是 durable Arkret Event，进入 Realm history，由 reducer 按 schema 校验；`ak.applet.bridge_error` payload 以 `artifacts/schemas/event-payload.schema.json` 与 `applet-schema.md` §7 为权威。Applet runtime 的调用进度、私有 session id、opaque params/detail 与实现状态只属于 operation response/stream 或部署本地状态，MUST NOT 写入共享 Realm history；跨实现有意义的业务结果必须落为既有 Event、Strand、Message、Morph、Relation 或封闭的 result artifact。
- **operation_id（HTTP，不进 history）**：本节表中的 edge operations、§4b 的 install/revoke operations，以及 §9.1 的 `ak.self.applet.ghost.command.preview.v1` / `ak.self.applet.ghost.command.provision.v1` 是 HTTP API operation 标识符，只描述 Arkret 节点 ↔ Applet 或 self/admin aggregate operation 的请求/响应绑定，本身不是 wire Event，不进入 Realm history。

`ak.edge.applet.command.transaction.v1` 在 v1 artifacts 中只作为 operation_id 存在，指 §7.3 的 transaction push HTTP 调用；它 MUST NOT 作为 durable Event kind 或 transaction-origin Event 写入 Realm history。transaction push 的幂等记录属于 Applet service / transport audit log；Applet 写入 Arkret 的事实由具体 Event Envelope 的 signed `applet_id`、`external_ref`、`authorization_ref`、event signature 与 capability grant 表达。

字段级接口索引：

本表 **surface / 调用方向** 列区分 Applet `edge` 管理端点与 Station `self` aggregate。安装／撤销由管理员原签发起；Bot／Ghost preview 与 provision 由已安装 Applet Service 原签 RFC 9421 发起，不能用管理员 session 代替。transaction 的 Applet→Station 与 Station→Applet 方向也必须分别核验来源。各 operation 的认证合同以 operation registry 为准，实现不得套用同一鉴权模型。

| operation_id | surface / 调用方向 | 必填字段 | 可选字段 | 响应字段 | 约束 |
| --- | --- | --- | --- | --- | --- |
| `ak.edge.applet.read.ping.v1` | edge（节点→Applet） | 无 | 无 | `applet_id: id`; `service_id: did_core_id`; `protocol_version: string` | 可公开，但不得泄露 private namespace。 |
| `ak.edge.applet.read.describe.v1` | edge（节点→Applet） | 无 | 无 | SDK `ServiceDescribe` | public mode 只返回 canonical discovery capabilities；不得私定义 Applet describe DTO。 |
| `ak.edge.applet.command.transaction.v1` | edge（双向） | `header.Idempotency-Key: string`; `applet_id: applet_id`; `source_id: did_core_id` | Applet→Station 为 `events: EventEnvelope[]`；Station→Applet 为 `committed_events: {commit, event, producer_device_evidence?, producer_signer_fact?}[]`；两者互斥，均可与 `signals: SignalEnvelope[]` 同时出现，至少一组非空。另有互斥的 `authoring_context`（仅 Station→Applet，见 §7.3.2） | `status: enum(accepted,partial,rejected)`; `committed_event_refs: CommittedEventRef[]`（accepted/partial 必填，可为空）; `rejected: object[]?`; `retry_after_ms: int?` | 成功不能只返回 status；每个 durable accepted Event 都必须以 Event/Commit/stream/position 四元组定位。signals-only 成功返回空 refs。rejected 分支不得携 `committed_event_refs`。字段集权威来源是 [`applet-edge-operations.schema.json`](../../artifacts/schemas/applet-edge-operations.schema.json) 与 [`applet-schema.md` §7](./applet-schema.md)。除 §7.3.2 的历史创建结果确认外，接收方 MUST 以 exact `applet_id + source_id` 选择唯一 active registration/current epoch，再验证 full/VM 投影、HTTP signature、Event 与 Commit 签名和绑定、current manager／普通账号的真实委托和 capability；不得按 service id 任取首条 Applet。replay key 是 `(applet_id, source_id, Idempotency-Key)`。 |
| `ak.edge.applet.actor.read.resolve.v1` | edge（节点→Applet） | `path.actor_id: percent-encoded RFC 8785 JCS(ActorId)` | 无 | `exists: boolean`; `actor_id: ActorId?`; `display_name: string?`; `external_ref: object?` | path 解码后必须是 closed ActorId，受管分支按 accepted creation／current manager 路由，仅其当前治理 Station 可查；普通账号不使用此受管查询，不得只比较 principal。 |
| `ak.edge.applet.realm.read.resolve.v1` | edge（节点→Applet） | `path.realm_id_or_alias: string` | 无 | `exists: boolean`; `realm_id: id?`; `title: string?`; `external_ref: object?` | 必须命中 portal namespace 或授权查询。 |
| `ak.edge.applet.read.protocol_metadata.v1` | edge（节点→Applet） | `path.protocol: string` | 无 | `protocol: string`; `display_name: string`; `icon_blob_ref: string?`; `field_definitions: object`; `instances: object[]?`（entry: `instance_id`, `display_name`） | instance list 可要求授权。 |
| `ak.edge.applet.third_party_users.read.list.v1` | edge（节点→Applet） | `query.applet_id: applet_id`; `query.realm_id: realm_id`; `query.protocol: string`; `query.instance_id: string`; `query.external_id: string`（全部必填） | 无 | `exists: boolean`; `actor_id: ActorId.realm`／`external_ref`（exists=true 必填，false 禁带） | 查询仅限当前治理方获准读取的 exact Realm／Applet／tuple；返回值必须匹配所属 Realm 与已接受映射，不能凭 Applet 返回值创建／重绑身份，不提供枚举。 |
| `ak.edge.applet.third_party_locations.read.list.v1` | edge（节点→Applet） | `query.protocol: string`; 外部 ID query 字段 | 无 | `realm_id: id?`; `exists: boolean`; `external_ref: object?` | 查询字段必须在 portal namespace 内。 |
| `ak.self.applet.install.command.preview.v1` | self（管理员→Station） | `applet_package`; `authoring_request_basis`（唯一内嵌 caller-signed registration/grant Events） | 无 | `{plan}`（契约 `applet-install-authoring.schema.json`） | Station 重算 plan，不产生 managed authoring request；registration epoch evidence 只在 registration Event manifest，不属于 package digest / proof。 |
| `ak.edge.applet.managed_actor.command.author.v1` | edge（客户端→Applet service） | `authoring_request` | 无 | `create_event` | 统一消费 `purpose=provision_bot\|provision_ghost`；返回一个 Service 原签创建 Event。 |
| `ak.self.applet.command.install.v1` | self（管理员→Station） | `Idempotency-Key`; `applet_package`; `authoring_request_basis`; `plan_digest` | 无 | install / commit response 的完整 required 字段集合以 [`applet-schema.md` §1b](./applet-schema.md) 与契约 `applet-install-operations.schema.json` 为权威源 | 只接纳 Service registration 与管理员原签 grants，不创建或复用 managed Actor。 |
| `ak.self.applet.revoke.command.preview.v1` | self（管理员→Station） | `path.applet_id`; `effective_scope`; `service_id`; `reason_code`; `revoke_mode` | 无 | `revoke_plan` | 从同一 durable current snapshot 枚举 exact revoke intents；每个 capability intent 必填同一 Grant 的 `expected_revision`，并进入 caller 自算的 `revoke_plan_digest`；见 §4b。 |
| `ak.self.applet.command.revoke.v1` | self（管理员→Station） | `header.Idempotency-Key`; `path.applet_id`; `revoke_plan_digest`; `effective_scope`; `service_id`; `reason_code`; `revoke_mode`; `capability_revoke_events[]`; `membership_state_events[]` | `proof?: AccountLifecycleProof` | `operation_id`; `revoke_plan_digest`; `status`; `steps[]`; `revoked_refs: AppletRevokeEffectRef[]?`; `rejected[]?` | 重算 plan 并逐项校验 signed revoke 的 exact revision；stale 必须重新 preview／确认／重签。Event effect 使用 `CommittedEventRef`；服务本地 effect 使用非 Event typed resource string；见 §4b。 |
| `ak.self.applet.bot.command.preview.v1` | self（已安装 Applet Service→Station） | `path.applet_id`; `effective_scope`; `service_id`; `request_id` | `display_name` | `authoring_request` | 从 exact active install 派生 Service 创建授权，签发独立 Bot candidate；不消费安装隐含 Bot，契约见 `applet-bot-operations.schema.json`。 |
| `ak.self.applet.ghost.command.preview.v1` | self（已安装 Applet service→Station） | `path.applet_id`; `effective_scope`; `external_ref` | `display_name` | `authoring_request` | PS 从 active install 派生全部 current 坐标并签发唯一 current generation；preview 有 durable winner/supersede ledger。 |

### 7.1 Ping

```text
GET /_arkret/edge/applet/ping
```

返回：

```json fragment
{
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

Arkret Station 向 Applet 的 base_url 仅交付管理材料，包括按 §7.3.2 交付已确认 managed Actor 的 authoring 初始化结果；群组 Event／Signal 内容必须通过实际 Bot／Ghost Device 的原生接口接收，不得发送到 base_url。反向 Applet Service → Station 的 Event／Signal 批次沿既有独立 producer proof、authorization 与 scope 准入。

以下为反向 Applet → Station 入站 Event／Signal 批次示例（非完整 schema），不是 Station → Applet 的群内容投递。管理 authoring_context 的封闭形态见 §7.3.2。

```json fragment
{
  "applet_id": "ak:applet:01904100-0000-7000-8000-aaaaaaaaaaaa",
  "source_id": "ak:did_core:webvh:z6Mkw8qTnL4rP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z",
  "events": [
    {
      "event_id": "ak:event:AQsHmGu_9sPOyJ4aG8VlWQBp8wGGhdC-BjfAaXqrIbk-",
      "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
      "kind": "ak.message.create",
      "actor_id": {
        "kind": "account",
        "account_id": {
          "principal_id": "ak:did_core:webvh:z2dmjZ8r7L4nP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z",
          "station_id": "ak:did_core:webvh:z7SrvceTnL4rP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z"
        }
      },
      "payload": {}
    }
  ],
  "signals": [
    {
      "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
      "scope_ref": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
      "sender_actor_id": "ak:did_core:webvh:z2dmjZ8r7L4nP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z",
      "sender_device_id": "ak:device:019640ed-8000-7000-8000-000000000001",
      "commit_ref": "ak:realm_commit:sha256:2222222222222222222222222222222222222222222222222222222222222222",
      "signal_class": "session",
      "sent_at": "2026-07-30T12:00:00Z",
      "expires_at": "2026-07-30T12:00:30Z",
      "encrypted_payload": {
        "scheme": "ak.signal_exporter_aead.v1",
        "key_ref": {
          "group_state_ref": "ak:event:AWn8zXw0Iuqoi0snySz3P5bT_ssUZS1nwhpXchPIvk48"
        },
        "purpose": "ak.signal.v1",
        "aead_profile": "MLS_128_DHKEMX25519_AES128GCM_SHA256_Ed25519",
        "epoch": 7,
        "nonce": "AAECAwQFBgcICQoL",
        "ciphertext": "AQIDBAUGBwgJCgsMDQ4PEA"
      },
      "proof": {
        "kind": "detached_jws",
        "verification_method": "did:webvh:z2dmjZ8r7L4nP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z:alice.example#device-1",
        "envelope_digest": "sha256:4444444444444444444444444444444444444444444444444444444444444444",
        "jws": "eyJhbGciOiJFZDI1NTE5In0..c2lnbmF0dXJl"
      }
    }
  ]
}
```
响应示例（非完整 schema）：

```json fragment
{
  "status": "accepted"
}
```
规则：

- `Idempotency-Key` MUST 作为逐次 transaction push 的 nonce / idempotency key 使用，并进入 HTTP Message Signature transcript（见 §7.3.1）。
- 幂等 identity MUST 至少绑定 `(operation_id, direction, Source-Service-ID, Destination-Service-ID, Idempotency-Key)`；接收方的幂等记录 MUST 同时保存 canonical body digest / `Content-Digest` 与本次验签得到的 `delivery_authentication_record`。
- 相同幂等 identity、相同 canonical body digest 且相同 `delivery_authentication_record_digest` 的重复投递 MUST 返回原 outcome 或等价成功，不得再次执行外部副作用。
- 相同幂等 identity 但 canonical body digest、source / destination service DID 或 `delivery_authentication_record_digest` 任一不一致时 MUST fail closed；若认证先通过则返回 `duplicate_conflict`，若签名 / source 绑定先失败则返回 §7.3.1 的认证失败 reason。
- 单事件级别仍以 `event_id` 去重；重复 `event_id` 且内容一致 MUST `accepted`，内容不一致 MUST 拒绝。
- 接收方入站处理队列饱和（backpressure）时，transaction 响应 MUST 对无法入列的 event 逐条返回 `rejected[].reason_code="queue_full"` 并携带 `retry_after_ms`；该拒绝不消费幂等 identity，推送方 MAY 在 `retry_after_ms` 之后以同一幂等 identity 重投被拒 event，接收方 MUST 按普通幂等规则重新受理。
- 幂等记录的保留窗口遵循 [`api-conventions.md` §6.1](../sync/api-conventions.md)：自记录创建起至少 24 小时，且不短于 [`../sync/service-http-binding.md` §8.3](../sync/service-http-binding.md) 共享窗口的签名寿命上限加最大允许时钟偏移；本节不定义更短窗口。
- Applet SHOULD 先持久化幂等记录，再执行外部副作用。
- Applet MUST 验证 source service DID 和 HTTP message signature。
- Applet MUST 独立验证 event signature，不得只信任推送方。

#### 7.3.1 逐次投递来源签名（双向对称，normative）

transaction push 是 service↔service 调用，**两个方向**都 MUST 携带**逐次投递**的 RFC 9421 HTTP Message Signature（per-delivery source signature），接收方 MUST 在处理任何 event / 副作用前先验签；纯 `Authorization: Bearer`（无 `Signature`）的 transaction push MUST 被拒绝。两方向不可只靠 bearer，也不可只在首次握手时验签一次：

- **node → Applet**（§7.3 上文，Arkret 节点向 Applet 推送）：Applet 端 MUST 按 `Source-Service-ID` 的 accepted service key binding 取得当前有效 verification method，并逐次验证 HTTP Message Signature；逐次验签不等于逐次在线解析 DID。新 service / key、binding invalidation 或显式 freshness 失效时才进入 DID authority resolution。`Destination-Service-ID` MUST 等于接收 Applet registration 的 `service_id`。Applet registration 的 `webhook_signature_policy` 在该方向声明 transaction endpoint 要求 `http_message_signature` 与可接受算法；`webhook_signature_policy.key_ref` MUST NOT 被解释成任意 Arkret 节点的来源 key。
- **app/bridge → arkret edge inbound**（`POST /_arkret/edge/applet/transactions` 的入站方向，已安装 Applet service / bridge 向 arkret edge 推送外部网络 transaction）：arkret edge 接收方 MUST 先用 signed `applet_id`、`Source-Service-ID` 与 exact Event `scope_ref` 唯一选择 §4b 接受的 active install，并用 `Source-Service-ID`（service `did_core_id`）验证其来源与当前 effective Applet registration，再要求签名 `keyid` / verification method 等于该 registration 的 `webhook_signature_policy.key_ref`；接收方从该 DID URL 取得 bare controller `did`，用已登记 adapter 验证并要求 `project(did) == registration.service_id == Source-Service-ID`，不得把 DID 与 core header 直接比较，并逐次验签。缺签名、签名无效、投影不一致、`webhook_signature_policy.key_ref` 未被该 Applet service 当前状态授权或无 active install 时 MUST fail closed。

**覆盖 header 集（MUST）**：本场景是 [`../sync/service-http-binding.md` §8](../sync/service-http-binding.md)
的 `ak.http_signature.scenario.applet_transaction.v1`；签名 transcript MUST 覆盖以下
RFC 9421 derived components 与 header：

<!-- BEGIN ak-http-signature-covered-set ak.http_signature.scenario.applet_transaction.v1 -->
- `@method`、`@target-uri`、`@authority`
- `content-digest`（按 [`../sync/service-http-binding.md` §8.2](../sync/service-http-binding.md) 覆盖 exact canonical HTTP content bytes；transaction push 总是带 body，故 MUST 携带唯一 `sha-256` member 的 `Content-Digest`）
- `arkret-operation`（header `Arkret-Operation`，值为 exact versioned `ak.edge.applet.command.transaction.v1`；按 [`../sync/api-conventions.md` §2.4.1](../sync/api-conventions.md)，凡要求 RFC 9421 签名的 canonical 请求，签名基串 MUST 覆盖该 operation selector，未覆盖 selector 的签名 MUST 按 `http_signature_invalid` 拒绝）
- `source-service-id`（header `Source-Service-ID`，等于 body `source_id`）
- `destination-service-id`（header `Destination-Service-ID`，等于接收方 service `did_core_id`）
- `idempotency-key`（header `Idempotency-Key`；参与幂等 / replay key，MUST 进入 transcript）
<!-- END ak-http-signature-covered-set -->
签名 parameters MUST 含 `created` 与 `expires`；时效窗口判据是
[`../sync/service-http-binding.md` §8.3](../sync/service-http-binding.md) 的共享窗口，
本节不复制其数值。落在窗口外的逐字节重放即便 replay cache 已 evict，也 MUST 因
`created` / `expires` 校验失败而拒绝。

接收方 MUST 在 JSON 业务解析与验签前按 [`../sync/service-http-binding.md` §8.2](../sync/service-http-binding.md) 对 exact HTTP content bytes 重算并校验 `Content-Digest`，再严格解析并确认收到的 wire 本身就是 canonical JSON，最后验证签名 transcript；MUST NOT parse arbitrary JSON 后仅对 canonicalized value 求 digest。body 内 `source_id` MUST 与 header `Source-Service-ID` 及签名 transcript 一致。

**投递认证记录（normative）**：接收方在验签通过后 MUST 从已验证的 HTTP message、effective Applet registration 与实际 verification key 派生 closed `delivery_authentication_record`，并把该记录及其 digest 写入 transaction 幂等 / replay 记录；caller 不得提供或覆盖该值，它也不是 request body 字段。字段固定为：

```text
{
  operation_id, direction,
  source_id, destination_id,
  signature_label, verification_method, verification_key_digest, signature_algorithm,
  registration_epoch,
  idempotency_key, content_digest,
  covered_components, created, expires
}
```

- `operation_id` 固定为 `ak.edge.applet.command.transaction.v1`；`direction` 只允许 `node_to_applet` 或 `applet_to_arkret_inbound`。
- `source_id` / `destination_id` 是已与 header、实际连接目标及 registration 交叉验证的 `did_core_id`。
- `signature_label` 是 receiver 选中并成功验证的 RFC 9421 signature label；`verification_method` 是 canonical DID URL；`verification_key_digest` 是 registered DID-method adapter 对实际 verification public key 的 canonical key bytes 所计算的 `sha256:` digest；`signature_algorithm` 是已登记的 canonical algorithm name。记录不复制随机或可变长的 `Signature` bytes。
- `registration_epoch` 对业务投递是本次方向所使用的 effective Applet registration epoch；它必须承诺该方向适用的 `webhook_signature_policy.key_ref` / algorithm policy。业务 registration 不适用、已撤销或无法得到唯一 effective epoch 时不得形成记录。仅 §7.3.2 的历史创建结果确认使用原 accepted creation signer fact 所绑定的原 registration epoch；该历史绑定不授予当前业务权，当前 HTTP 来源 key、治理路由及接收资格仍逐次验证。
- `idempotency_key` 是 header `Idempotency-Key` 的 exact value；`content_digest` 是通过 §2.5.1 profile 校验后的 canonical `Content-Digest` structured-field value，绑定 exact canonical body bytes。
- `covered_components` 按 receiver 实际验证的 `Signature-Input` 顺序保存 canonical lowercase component identifier，必须包含本节 required set；`created` / `expires` 是同一 signature parameters 中的整数 UNIX seconds。

记录使用 RFC 8785/JCS；不得增加 implementation-private 成员参与协议比较。每次投递 MUST 先独立验证完整 RFC 9421 transcript、当前来源 key 与时效窗口。业务投递另验证当前 registration / active install；§7.3.2 的纯历史创建结果确认按该节验证原 registration 绑定与当前私有接收资格，不要求当前安装有效。`created` / `expires` 保存在本次认证记录中供 freshness 验证与 audit，**仅这两个成员**不参与稳定幂等绑定；发送方以新的有效签名时间重试同一 body，不得因此成为另一项外部副作用。其 digest 固定为：

```text
stable_delivery_authentication_binding =
  delivery_authentication_record with only created and expires removed

delivery_authentication_record_digest =
  "sha256:" + lowerhex(SHA256(
    UTF8("ak.applet.delivery_authentication_record.v1\n") ||
    RFC8785_JCS(stable_delivery_authentication_binding)))
```

receiver MUST 从本地派生记录重算 digest，不得信任 caller 或 cache 输入的预算值。domain label 不是 `delivery_authentication_record` 的成员，实现 **MUST NOT** 把它以 `domain`、`profile` 或任何其他键插入记录后改算 `SHA256(JCS(record))`；该标签只以上式的 UTF-8 前缀形态参与摘要。记录的字段集封闭为本节列出的成员，**MUST NOT** 追加 `Signature` bytes、原始 `Signature-Input` 字符串、webhook 认证配置或请求摘要等本节未列出的成员。幂等 / replay equality 是上述稳定投影重算后的 digest 相等，MUST NOT 再比较完整记录中的 `created` / `expires`。完整记录与两个时间成员仍必须保存；接收方可以另存逐次 audit，但不得刷新原 outcome、重做副作用或用旧窗口代替本次 freshness 验证；实现私有 audit metadata 可以与记录并列保存，但不得改变该 equality。实现不得只用裸 `Idempotency-Key` 或 body 内 `source_id` 决定重复投递，也不得在 service DID key rotate、registration epoch 改变或 active install 撤销后把旧记录当成新授权。

`source_id` 只认证来源服务，不认证每条 durable Event 的业务 actor。arkret edge 把 Applet transaction 落为 Arkret Event 时，仍 MUST 对每条 Event 独立验证 `actor_id`、`applet_id`、`authorization_ref`、`external_ref` / provenance、`producer_proof`、accepted manager / capability grant（普通 Account 另核其真实委托）；ghost actor、bot actor 或 delegated native actor 与 source service 不一致时 MUST fail closed（`capability_denied` / `applet_registration_unauthorized`，按失败层级选择）。

**失败码（normative）**：

按 [`../sync/api-conventions.md` §5](../sync/api-conventions.md)，唯一机器判别字段是 RFC 9457
Problem 的 `type`（`https://arkret.org/problems/{code}`）。下列三种签名失败各有自己已登记的
code 与 `type` URI，接收方 MUST 直接返回该 code，MUST NOT 返回通用 code 再用 `reason` /
`reason_code` 做第二次分派；consumer 也 MUST NOT 从扩展成员反推签名失败类别。

- 缺 `Signature` / 纯 bearer：`http_signature_required`（401，`type=https://arkret.org/problems/http_signature_required`）。
- 签名验证失败、`Content-Digest` header profile 不符合 [`../sync/service-http-binding.md` §8.2](../sync/service-http-binding.md)、digest 不覆盖 exact HTTP content bytes、wire 本身不是 canonical JSON，或 `source_id` 与 header / transcript 不一致：`http_signature_invalid`（401，`type=https://arkret.org/problems/http_signature_invalid`）。
- `created` / `expires` 超出时效窗口（含 replay cache evict 后的窗口外重放）：`signature_window_invalid`（401，`type=https://arkret.org/problems/signature_window_invalid`）。
- inbound 方向 exact `(applet_id,Source-Service-ID,scope_ref)` 从未存在可验证 accepted install，或 `Source-Service-ID` 与该 install registration service 不一致：`applet_registration_unauthorized`（403）。已验证 exact install 因 revoke fence / capability revoke 失效时返回 `applet_revoked`；不得搜索其它 scope 的 install 来替代，也不得把 revoked install 误报为从未授权。认证失败仍优先返回对应签名失败 code，不泄露安装状态。
- 幂等 identity 已存在但 canonical body digest 或稳定 `delivery_authentication_record_digest` 不一致：认证成功后 MUST 返回 `duplicate_conflict`；认证未通过时 MUST 优先返回上述对应的认证失败 code，避免泄露历史 transaction 状态。

transaction push 的逐次签名是传输层来源认证，**不替代** §8 每条 Applet-originated 写入 Event 的 envelope event signature（`producer_proof`）与 capability grant 校验：arkret 把外部 transaction 落为 durable Arkret Event 时，仍 MUST 按 §8 / §11 校验每条 Event 的 `actor_id` / `applet_id` / `authorization_ref` / `producer_proof`。

#### 7.3.2 已确认 managed Actor 的 authoring 初始化

runtime 通过 [Realm actor exact 材料](./realm-actors.md#8-exact-控制材料与历史验签)核实原创建或控制更新。
authoring_context 只携当前治理方签名的 material；逐项验证完整 actor、原 Event／Commit、
request digest、audience、nonce、当前治理链和所持 key。不得把 Service 收到 HTTP 成功当作 Device 已授权。
**历史创建结果确认边界（normative）**：仅当 authoring_context 的 material 是原 Bot／Ghost 创建 Event 的精确结果时，接收、验证、耐久保存与重试确认 MUST NOT 要求当前业务安装或原业务 grant 仍有效。该分支不得混入 Event／Signal 业务批次，也不得自动创建 Device 授权、membership、child grant，取得 Welcome／KeyPackage／群内容或启动业务。仍须验证当前治理链及本次 HTTP 签名、material 的 audience／nonce／freshness、原 Event／Commit／私有 signer fact、Applet／Service／完整 Actor 与本地原候选及所持 key 的一致性，并遵守 Realm actors §8 的当前私有材料读取资格。卸载不抹掉原创建事实；管理关系转交不因这条例外被撤销，也不向无读取资格的旧管理者或同名新 Service 披露材料。

本分支认证记录的 registration_epoch 绑定原 accepted creation signer fact，不以 current_binding 替换历史来源。纯 HTTP 签名时间刷新仍使用原稳定幂等绑定；material 刷新或治理换任改变 source／body 时使用新投递幂等键，并按原创建 Event／Commit 精确去重，不重复生成身份、密钥或副作用。原接受事务 MUST 原子保存可恢复 completion；治理交接保留该待办与原结果。新治理方刷新自己签发的短期材料，不改签原 Event／Commit／fact。

后续任何业务动作 MUST 在其实际 scope 检查当前安装、权限、主体／Device 状态和原有成员／MLS 条件；`current_binding=active` 本身不是 action grant。停用／卸载后仍有的独立恢复权按原恢复合同执行，不附加业务安装条件。
控制更新、卸载后的维护、原结果恢复及 manager 转交分别按 Realm actors §5–8 执行。
治理换任沿原 RealmId 取得当前治理方，不再查询另一个 Bot／Ghost Account Station 或 PCR。

Realm／portal alias 解析、外部协议元数据、外部用户映射和外部 location 查询同样只属于 Applet Service 操作包，不属于 Station 操作包或 Coland Station 部署原型。治理 Station MUST 按已选定的精确 Applet／Service 安装调用该 Applet；MUST NOT 扫描全部安装、广播查询或取首条匹配。Applet 继续按本节已有来源签名、目标 Service、安装／namespace 和当前治理边界回答；外部用户映射还须核对完整 tuple 与 accepted current manager。未声明的可选适配能力按 §15 返回 `unsupported_feature`，不得伪造映射。

### 7.4 Query Actor

该操作只属于 `ak.operation_bundle.applet_service.applet.v1`，不属于 `ak.operation_bundle.station.applet.v1` 或 Coland Station 部署原型。治理 Station 是调用方，不能把所有已安装 Applet 的主体汇总为本站 Applet 目录提供此操作；响应由已接受的当前 manager Applet Service 提供。

```text
GET /_arkret/edge/applet/actors/{percent_encoded_jcs_actor_id}
```

受管分支仅供该 Realm 当前治理 Station 向已接受的 manager Service 核对已知完整主体；不从 DID namespace 猜测 Service 或发现未知 Bot／Ghost。接收 Applet MUST 验 HTTP 来源签名、当前 Realm 治理链与自己的 accepted manager 绑定；不向无权 Station、旧 manager 或任意请求人公开主体目录／external tuple。普通 Account 继续使用原账号目录与委托合同，不进入本受管查询。缺失或不可见目标均返回相同 not_found。

返回：

```json fragment
{
  "exists": true,
  "actor_id": {
    "kind": "realm",
    "realm_actor_id": {
      "realm_id": "ak:realm:Adoyg50aOV537gzxNy87EOdUlHiIujznqwZcMLSGFmzg",
      "principal_id": "ak:did_core:webvh:z6MkGhostU123"
    }
  },
  "display_name": "Alice on Slack",
  "external_ref": {
    "protocol": "slack",
    "network_id": "T123",
    "user_id": "U123"
  }
}
```
path 参数使用 percent-encoded RFC 8785 JCS(`ActorId`)；解码、closed-schema 校验或 canonical
重编码不一致时返回 `param_invalid`。若完整 ActorId 不存在，返回 `404 not_found`。同 principal
但 Realm 或 Actor kind 不同不是同一 Ghost 查询目标；不构造独立 Account／PCR。

### 7.5 Query Realm

```text
GET /_arkret/edge/applet/realms/{realm_id_or_alias}
```

用于查询 portal Realm 是否存在或可创建。

返回：

```json fragment
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

```json fragment
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

Service原签Applet写入 MUST 通过 `ak.edge.applet.command.transaction.v1` 的 Applet→Station `events[]` 提交 producer-only `EventAdmissionSubmission`，见 §7.3.1 / §11.1。Applet service 不持有 SessionGrant，不得把 `/_arkret/self/events` 的 Bearer session 路径作为替代入口。§4b service install、§9.1 Bot/Ghost provision 与设备授权等正式登记的 aggregate / operation 仍使用各自封闭载体。

每个 Applet-originated 写入 Event MUST 包含下列 signed Event Envelope 字段（这些字段均进入 `producer_proof.event_digest`；不得只放在 `unsigned` 中）：

- `actor_id`
- `applet_id`
- `external_ref`，若来自外部网络
- `authorization_ref`
- `producer_proof`

`authorization_ref` MUST 引用本次 admission 合同规定的真实 accepted active `ak.capability.grant`，并与 exact installation、service authority、`applet_id`、registration epoch 和 producer-signed `scope_ref` 交叉验证。其用途由 event-kind registry 的 admission 合同及实际 producer 决定：

- capability-gated Event 必须验证该 grant 覆盖具体 action / resource；不能以安装成功替代 action 权限。实际 Bot／Ghost Realm Device 本人签署时，该 ref MUST 是 Service 签发给该完整 realm ActorId 的 terminal child，按 [managed-governance §4](../authz/managed-governance.md) 追溯真实 Service parent／所有贡献祖先，并在本次接纳 cut 重验 exact installation 和各自原约束／原持有人 quota。它不是第二个 installation ref，也不授权 Service 借 child 代签 Realm 主体 Event。
- 本人 `ak.circle.member.state{join}` 属于上述 capability-gated 分支：使用实际 Circle 的 `ak.circle.member.add` child，同时额外满足 `ak.applet.join` 的管理／治理审批，保持 Circle join rule／FSM、原签父 membership revision 与独立 E2EE 同意。Realm subject-only join 的安装引用规则不得套用于 Circle；Realm 安装／pair 不覆盖 Circle。
- `subject_only` Event（如 `ak.invite.accept` 与本人 `ak.member.state` join）不把该 ref 当作 action 授权。该 ref 只绑定 exact installation；本人签名、exact invite、join rule、membership FSM、目标 Realm / Circle policy 与 E2EE admission 仍独立验证。不得为不可授权 action 签发虚构 grant，也不得要求 managed actor 持有 `ak.realm.admin` 才能本人加入。Bot / Ghost 的本人签名按其已登记 managed-principal authority 解析；service 签名不得凭 install ref 冒充任意 native actor。

按事件签署主体进一步区分：

- **Delegated-ghost / masquerading 事件**（`actor_id` 为 ghost / bot / delegated native actor）：`authorization_ref` 必须满足上述 admission 分支；capability-gated 写入须覆盖 Event action / resource（见 §9.1 与 §11）。`ak.identity.accountability_grant` 只证明责任归属，MUST NOT 被解释为 action authorization。
- **Service-actor 自署事件**（`actor_id` 为 `ActorId.service`，`service_id` 等于 registration 的 Applet service，如 portal strand 创建、`ak.applet.bridge_error` 审计等运维 / 审计事件，非委托 ghost）：此类事件不存在委托关系，`executed_by` MUST 省略，`authorization_ref` MUST 指向该 Applet 的 active capability grant，而非 registration Event 或某个 ghost 的 accountability grant。install grant subject是与producer逐字段相同的ActorId.service；verifier另验exact installation/scope/hosting Station，不构造Service Accountpair或把account/service类型等价。签名只证明来源，不能替代 action / resource 授权。

§4b 的合规安装必须为该 Applet 铸造一个或多个与 `(applet_id, service_id, effective_scope, registration_epoch)` 绑定的 active grant。安装若未产生覆盖待写 action/resource 的真实 grant，就尚未形成可写入状态，Applet MUST NOT 发送携 `applet_id` 的 Event。需要创建 portal Strand 的 grant 必须覆盖 `ak.strand.create`；需要写入 bridge 审计错误的 grant 必须覆盖 `ak.applet.bridge_error`。不得使用 sentinel ref、静态占位 grant、service 签名或隐式部署特权代替。grant 被 revoke 后，新的 portal Strand 创建与新的 `ak.applet.bridge_error` 都 MUST fail closed；撤销事实由撤销动作及部署侧安全审计记录，不要求已失去授权的 Applet 再写 Realm 审计 Event。

`ak.applet.bridge_error` 是 `capabilities.md` §3.2 与 owner compiled `grant_authority_rule.include_actions[]` 登记的 exact grant issuer exception：root/co-owner 可在安装事务中为此 action 签发上述专用 grant，但这不授予 owner 直接 author 该 Event，也不扩展到其它 Applet profile action。安装及入站接纳仍 MUST 验证完整Service ActorId subject与producer逐字段相等、精确 installation/registration epoch/resource、producer 签名与当前 revoke fence。

以下片段展示所属 Realm 的 Ghost 标识与 signed provenance 字段，不是可提交的完整 Event；
实际 Device、授权与 producer proof 仍按现行合同独立验证：

```json fragment
{
  "event_id": "ak:event:AQsHmGu_9sPOyJ4aG8VlWQBp8wGGhdC-BjfAaXqrIbk-",
  "realm_id": "ak:realm:Adoyg50aOV537gzxNy87EOdUlHiIujznqwZcMLSGFmzg",
  "actor_id": {
    "kind": "realm",
    "realm_actor_id": {
      "realm_id": "ak:realm:Adoyg50aOV537gzxNy87EOdUlHiIujznqwZcMLSGFmzg",
      "principal_id": "ak:did_core:webvh:z6MkGhostU123"
    }
  },
  "kind": "ak.message.create",
  "applet_id": "ak:applet:21532600-0000-7000-8000-000000000000",
  "authorization_ref": "ak:grant:AU1_A5a8MMz_OdxEleQlWPFn-ljdJteaJv3ZZ9APkcrZ",
  "external_ref": {
    "protocol": "slack",
    "network_id": "T123",
    "event_id": "1714040000.000100"
  },
  "created_at": "2026-04-26T00:00:01Z",
  "payload": {
    "strand_id": "ak:strand:AUPkhcWNNoG21KvR89voO-SRUnh1ZFG80N_5xygyYq0O",
    "track_name": "discussion",
    "content": {
      "kind": "ak.content.text",
      "body": "hello from Slack"
    }
  },
  "producer_proof": {
    "kind": "detached_jws",
    "verification_method": "did:webvh:z6MkGhostU123:slack-bridge.example:ghost:u123#key-1",
    "event_digest": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "created_at": "2026-04-26T00:00:01Z",
    "jws": "a..b"
  }
}
```
`external_ref` 是 bridge / 外部网络 provenance 与幂等审计材料。若用于回环防护、外部消息去重、moderation audit 或用户可见出处，Producer MUST 使用 Event Envelope 顶层 signed `external_ref`；`unsigned.external_ref` 只能承载可丢弃的本地 hint，MUST NOT 作为安全决策输入。

## 9. Ghost Actor

Ghost Actor MUST 与原生人类 Actor 在协议层可区分。

Ghost Actor profile SHOULD 包含（以下为 schema 合法形态；字段与约束**以 artifacts 的 [`actor-profile.schema.json`](../../artifacts/schemas/actor-profile.schema.json) 为准**）：

```json fragment
{
  "id": "ak:actor_profile:ARqc1CPEkB79f9R5Lv-dwsj7VZbUKXbAYPl3sEhUufeZ",
  "schema": "ak.schema.actor_profile.v1",
  "actor_id": {
    "kind": "realm",
    "realm_actor_id": {
      "realm_id": "ak:realm:Adl4wx7u7qRtt-nOIWpCQylq6hgCVDdC0fiPNOKCLOvv",
      "principal_id": "ak:did_core:webvh:z6MkGhostU123"
    }
  },
  "actor_kind": "integration",
  "display_name": "Alice on Slack",
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
`actor-profile.schema.json` 是 `additionalProperties:false` 的封闭 schema。此 Realm 分支要求完整 `actor_id`，不得携 `principal_id`、`handle`、`agent_slug` 或 `accountable_principal_ids`；普通账号的 `principal_id` 分支保持原规则。Profile 必须由主体当前控制方法在 `realm_control` 单独创建或按 revision 更新，创建主体不自动建立 Profile。Applet 托管标记 `managed_by_applet` 与外部网络展示来源可放入开放容器 `profile_fields`，但不能替代不可变创建记录、真实 external tuple、当前管理关系或业务授权。初始 Profile 不公开；公开使用另核实际 scope 的 publish／review。

Ghost Actor MUST NOT 被静默合并到 native DID，除非 native holder 显式声明并完成绑定。

### 9.1 Ghost Actor Provisioning（normative）

Bot／Ghost 统一使用 [Realm actor 创建候选](./realm-actors.md#6-创建与控制更新签名)。
preview 固定创建意图；Applet author 操作只生成独立控制方法签名的 candidate 和 Service 原签
`ak.realm.actor.create`，治理方通过 `ak.self.events.command.submit.v1` 接纳这一 Event。
创建只初始化身份／控制／manager／双 status／generation，不再提交四 Event 账号聚合。
Profile、Device、child、成员与 MLS 都在各自真实权限与 producer 下另行建立。

持续 Ghost 许可允许在明确 external protocol／instance、scope、quota 与当前 Service 安装上界下自动创建，
只有 Policy 要求逐候选 review 才再次请求管理员。外部 tuple 按固定 Realm／Applet 唯一锁定；
同 Realm 其它 Circle 的复用另核授权，跨 Realm 不复用完整主体身份。unknown 恢复原请求，不重新扣配额。

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

```json fragment
{
  "actor_id": {
    "kind": "account",
    "account_id": {
      "principal_id": "ak:did_core:webvh:z2dmjZ8r7L4nP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z",
      "station_id": "ak:did_core:webvh:z7SrvceTnL4rP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z"
    }
  },
  "executed_by": {
    "kind": "service",
    "service_id": "ak:did_core:webvh:z9CalAppTnL4rP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z"
  },
  "authorization_ref": "ak:grant:AU1_A5a8MMz_OdxEleQlWPFn-ljdJteaJv3ZZ9APkcrZ",
  "applet_id": "ak:applet:8a0baad5-6000-7000-8000-000000000000"
}
```
这些字段位于 Event Envelope 顶层并进入 canonical event bytes；实现 MUST NOT 把 `applet_id` 或 `authorization_ref` 降级为 `payload` 内业务字段或 `unsigned` hint。

**Reducer normative**:

- 当 Event 的 envelope signature 由 applet / delegated agent key 签发但 `actor_id` 指向 native principal DID 时（即 actor_id ≠ signing key 所属 DID），reducer MUST 校验：
  1. `executed_by` 必填，指向实际签发该 Event 的 applet / agent DID;`executed_by` 与 envelope signing key 的 DID 一致；
  2. `authorization_ref` 必填，指向已 accepted 的 `ak.capability.grant`，该 grant 把 actor_id 主体的某个 action 委托给 executed_by;
  3. `applet_id` 必填(在 Applet 模式下), 指向已注册的 applet;
  4. `executed_by` MUST 是该 Applet 当前 registration 的真实 Service ActorId，或其已接受且当前 manager 绑定成立的完整 realm ActorId。代表普通 Account 行动时，grant 必须同时精确绑定被代表 Account、实际 executor、action、scope 和 Applet；Realm Device 还要核本人授权与全部持续门。namespace、Profile、显示角色或 accountability 不证明管理归属，未知／未创建主体不得代表任何账号。
  5. grant MUST 通过 [`constraint-schema.md` §7.3](../authz/constraint-schema.md) 的 `authority_control` + `constraint_subkind=applet_authority` 规范形绑定 `applet_id`、`executed_by` 与 `registration_epoch`，并由 grant `resources[]` 精确覆盖 producer-signed `scope_ref` 所指的 `effective_scope`。`registration_epoch` 是唯一安全 epoch 绑定键；reducer/verifier 必须展开 referenced registration 的 epoch evidence 并确认 DID Document digest、accepted signing key set 与捕获值一致。Applet key rotate、endpoint 变化或 registration 更新后，旧 grant 不得授权新 key。实现 MUST NOT 发明 `constraint_kind=applet_delegation_binding`、live-only authorization shadow 或其他 schema 外别名替代 durable grant。
- 对上述 delegated write，缺少 `executed_by`、`authorization_ref` 或 `applet_id` 中任一字段时，reducer MUST `schema_violation` 拒绝。该 delegated 规则适用于所有 `ak.profile.applet_*` profile；service 自署 Event 按 §8 省略 `executed_by`，不得因没有委托而拒绝。客户端 / SDK 不得退回到 SHOULD 形态。

Applet MUST NOT use masquerading to hide automation. 客户端 MUST 明确展示 `via applet`：UI 在渲染 mention、notification、audit log、moderation queue 等任何"who did this"上下文时，MUST 同时显示 native actor 与 `executed_by` 双重署名，不得仅显示 native actor 而隐藏 applet 身份。

`requested_scopes` 只服务 consent / audit UI：registration 接受时，reviewer 可据此决定是否签发 capability grant；一旦 grant 写入，后续 reducer 只看 grant `actions[]` / selector / constraint，不再从 `requested_scopes` 推断权限。实现 MUST 在 audit log 中把最终 grant 与 registration `requested_scopes` 的差异显示给 reviewer，避免 Applet 请求 A、实际被授予 B 时无人可见。

### 11.1 普通 inbound Event 的首次准入与历史安装证据

管理员授权 exact install，Applet 构造、签署并可靠重试普通 Event，任意合资格接收站独立验证安装授权、Applet producer 与 scope 并保存原始 Event；安装绑定不产生普通 Event 的排他准入站。

`ak.edge.applet.command.transaction.v1` 按方向验证：Applet→Station 的 `events[]` MUST 是 producer-only caller submissions，由接收 Station 接纳后产生真实 Commit；Station→Applet 的 `committed_events[]` MUST 是完整 accepted `{commit,event}` 对，接收方验证 Event 与 Commit 签名、Event 在 Commit 中的 exact 绑定及可见权限，随后仅从已验收的配对派生 `committed_event_refs[]`。无 Commit 的裸 Event 不得在 Station→Applet 方向得到成功回执或伪造坐标。只有 Signal 被接纳时成功回执的 `committed_event_refs` 是空数组；`partial` 时数组恰好包含已接纳的 durable Event，不能包含被拒项目。HTTP RFC 9421 来源验签逐次执行，不能替代每条 Event 的 producer、grant、epoch 或安装检查。Signal 保留独立规则。

Station→Applet 的每个 `committed_events[]` 项还执行**由原 Event 决定的设备证据 presence**：实际
producer（有 `executed_by` 时取它，否则取 `actor_id`）为 Account 且原 proof method fragment 是
`ak:device:` 时，MUST 携 `producer_device_evidence`；其它 producer MUST NOT 携。它直接复用
[`account-device-signer-evidence.schema.json`](../../artifacts/schemas/account-device-signer-evidence.schema.json)
的 closed 两成员 sibling：原 origin Station 在原 Event 接纳前冻结并耐久保存的
`device_projection_attestation` 与完整 `service_resolution`，不携原生 PCR log 或私有解密材料。
缺失、多余、裁剪或错绑定均 `schema_violation`，原 Event／Commit bytes 与 ID 不改。

receiver MUST 以原 covering `commit.committed_at` 作为接受 cut；完整 Service native history 的
exact历史 assertionMethod、origin Station 与 attestation 原签名 MUST 按原源签名
`attested_at` 验证，遵循 [`device-lifecycle.md` §8.2](../crypto-media/device-lifecycle.md)，
不得把接受 cut 或 receiver 当前时钟替换为源签名时刻。随后核对完整 AccountId／DeviceId、原授权
Event／generation、device raw signing key及 authorization_window 对 Event created_at 与 committed_at
的覆盖，再用该真实 key 验原 producer JWS与内容ID。设备 evidence 的 attested_at 必须不晚于原接受
cut，其 proof window 在该 cut 有效；不能用 receiver current clock 或后来 current Device status
改判原接受事实。原 attestation完整保存，所以后来撤销、rotation 或 cache deadline经过不使已接受
历史失效。当前 install／registration／可见权限 gate 仍独立执行；证据不授予任意 PCR 读取、SessionGrant
或新 Event 写权。HTTP／RealmCommit 签名、DID Document的普通method与裸publickey均不能代替原设备
签名证据。站点在原接受事务内或同一原子 completion UoW保存该完整root及原件，不能发送后补写。

普通 Applet Event 必须用原始 producer 签名的 `applet_id`、`authorization_ref` 与 `scope_ref` 解析标准 `applet_installation_authority` dependency，精确匹配 registration、grant、scope 和历史授权实例；registration epoch 从 referenced grant 的 `authority_control.applet_authority` constraint 读取，再核对 accepted registration epoch evidence。这里没有额外的 `authority_refs` wire 字段。任何 receiver 都独立验证；不能以某站补签代替，也不能任取同 service 的另一安装。Circle 安装不扩权至 Realm。

## 12. E2EE

Applet 参与 E2EE Realm 时有三种模式：

1. Bot 作为正式成员加入 MLS group。
2. Ghost Actor 作为正式成员加入 portal Realm 的 MLS group。
3. Applet 不解密，只转发外部密文或桥接 metadata。

规则：

- Applet 没有加入 MLS group 时 MUST NOT 获得明文。
- Bridge 到不支持 E2EE 的外部网络时，客户端 MUST 明确提示加密边界在 bridge 处终止。
- Applet 托管 Ghost Actor MLS state 时，必须将其视为高敏感密钥材料。

**E2EE 加入授权（normative）**：Bot Actor 或 Applet-managed Ghost Actor 加入 E2EE Realm 或 Circle 的 MLS group（上文模式 1、2）MUST 经过独立的 **E2EE 加入授权**，该授权与普通的 capability grant（如 `ak.strand.create` / `ak.message.create` 等写入权限）**分立**：持有写入 capability 不自动授予把 applet / ghost 成员加入 MLS group 的权利。

- 该 E2EE 加入授权 MUST 由 Realm owner、Realm admin 或 Realm policy 明确授权的 administrator actor 通过已 accepted 的 registration `claimed_profiles[]`（含 `ak.profile.applet_e2ee_join.v1`）、exact install grants 与当前 Realm policy 明确同意，并经 Station authorization capability 校验。该同意不允许管理员代写第三方 `leave→join`：Bot / Ghost 必须本人签署 Realm 的 `ak.member.state`、Circle 的 `ak.circle.member.state`，或在已有正式入口接受 exact 定向邀请，按 [common-fields.md §4.5](../models/common-fields.md#45-membership-fsmnormative) 的 FSM 准入，Event 必须携 applet provenance。未登记新的 E2EE consent Event / payload 字段，不得自行添加。Welcome 不能替代 membership 或上述同意。Circle MLS 须在 exact Circle 逐项重验这些来源及 Circle／父 Realm Policy，Realm 同意不覆盖 Circle；不借本节新增 Circle invite workflow 或放宽 Circle 自助加入门。
- 缺少该独立 E2EE 加入授权时，Arkret 客户端 MUST NOT 把 applet / ghost 成员加入 MLS group，并 MUST 以 `applet_e2ee_join_unauthorized` 拒绝该加入。
- 成员加入后，客户端在 MLS group 的成员 roster（成员列表 UI 与 audit 视图）中 MUST 显式标注该成员为 **applet-managed**（区别于 native 人类成员），不得让 applet / ghost 成员在 roster 中表现为普通 native 成员。该标注与 §9 的 Ghost Actor 协议层可区分要求一致。

**E2EE endpoint 是 delegated device，不是新分支（normative）**：模式 1、2 中实际持有 MLS leaf 的是 Bot / Ghost 的**受限 delegated device**，走 [`../crypto-media/device-lifecycle.md` §9.2.1](../crypto-media/device-lifecycle.md) 既有的**普通 device 分支**。Bot 与 Ghost MUST NOT 借用 Agent 分支（§3.4.1），v1 也 **不**为它们新增第三个 recipient endpoint 分支。

- 该 Device 必须由独立主体当前控制方法在所属 Realm 的 realm_control 中以 realm_managed_delegation 授权；这是创建后的独立后继 Event，不属于 install 原子集合。有限 scope/action、PoP、CAS 与 generation 见 [Realm 主体 §5](./realm-actors.md#5-devicehttp-与业务身份)。
- 没有这样一条已接受的 authorize 时，客户端 MUST NOT 为该 Bot / Ghost 发布 KeyPackage、MUST NOT 把它加入 MLS group，也 MUST NOT 接受它签署的 MLS durable receipt。此处 fail closed 的是**设备**条件，与上文独立 E2EE 加入授权（`applet_e2ee_join_unauthorized`）是两道彼此独立的门，任一不成立都拒绝。
- 该 delegated device 在每项实际业务 scope 跟随该 scope 当前安装与 parent 的 revoke fence：scope A 被 fence 后，A 的新 KeyPackage／Welcome／durable receipt MUST 以 `applet_revoked` 拒绝，不影响 scope B 已独立合法授权的请求，不得等待另一条 `ak.device.revoke`。

## 13. 安全要求

Applet 实现 MUST：

- 验证所有入站 HTTP message signature
- 验证所有 Event signature
- 持久化 transaction id，保证幂等
- 对外部事件做去重
- 限制 Realm／handle namespace 路由范围
- 遵守 capability grant
- 记录可审计 bridge mapping
- 对 secret / token 使用安全存储
- 支持管理员 revoke

任何“安装前策略拒绝”的测试不得让尚未 accepted 的 Bot/Ghost 直接签普通 Event，也不得要求其提前提供未来
`Principal` root。测试必须让已经存在且具有真实 `Service` evidence 的 Applet service 作为 actual producer，
或直接测试 closed install/ghost admission；安装后的 Bot/Ghost 策略负例则必须先以真实 `Principal` root通过
producer authentication，再只破坏目标 policy 条件。每个 Event始终只有一份 actual producer proof；Station
admission 与 RFC 9421 transport signature 都不能作为第二份 Event proof。

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
- Realm／handle namespace 匹配及受管 actor 的 accepted create／current manager 验证
- transaction 幂等性
- transaction push 的逐次 `delivery_authentication_record`（§7.3.1）
- `Source-Service-ID`、`Destination-Service-ID`、`Idempotency-Key`、body digest 与 `delivery_authentication_record` 之间的幂等 / replay 绑定
- capability enforcement
- bot actor attribution
- 当实现暴露 self/admin Applet install 时，install preview / commit / revoke aggregate operation 的幂等性
- `ak.edge.applet.command.transaction.v1` 只能作为 operation_id，绝不能作为 durable Event kind

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

- `applet_registration` 的字段集由 [`applet-package.schema.json`](../../artifacts/schemas/applet-package.schema.json) 与 [`event-payload.schema.json#/$defs/applet_registration_payload`](../../artifacts/schemas/event-payload.schema.json) 固定（closed，`additionalProperties:false`），至少包含 service DID、`base_url`、namespace、protocol、`requested_scopes` 与 `webhook_signature_policy` signing policy。它**不携带** capability refs 与 expiry：实际授权由独立的 `ak.capability.grant` 承载并有自己的 `temporal` 约束，registration 的时效由 `registration_epoch` 与 controller 的 revoke 表达。
- Namespace pattern grammar（命名空间模式语法）MUST 明确 Realm／portal、handle 与外部 protocol id 的路由匹配边界；不包含 Actor DID namespace；namespace 命中不授予写权限。
- Transaction push 操作 MUST 包含 exact `applet_id`、`source_id`、其封闭分支的非空 Event/Signal 批次或 `authoring_context`、`Idempotency-Key`、HTTP message signature 与 received_at audit metadata；**两个投递方向（node→Applet 与 app/bridge→arkret edge inbound）都 MUST 携带逐次投递 RFC 9421 来源签名并由接收方逐次验签，覆盖 header 集、失败码与认证记录见 §7.3.1**；纯 bearer 的 transaction push MUST 被拒绝。外部 source network、external event id、mapped actor、target Realm / Circle 与 operation refs 必须落在具体 Arkret Event 的 `external_ref` / provenance / capability refs 中，不得通过 transaction 专用 durable Event 表达。
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

普通成员对已获准读取的 Applet 代发 Event，MUST 使用原 RealmCommit 绑定的最小 Service 历史验签投影，合同见 sync/authority-commit-log.md。该只读投影只服务 exact Event 验签，不授予 runtime completion、私有创建／问责记录或整段历史读取权；current 安装状态变化不替代原 accepted fact。


## 18. 受限 Device 认证、业务授权与内容供给

完整合同见 [Realm actors §5](./realm-actors.md#5-devicehttp-与业务身份)。
Device HTTP 使用 Arkret-Managed-Device 的完整 realm actor 元数据，直达所属 Realm 当前治理方；
无 SessionGrant。控制方法的 HTTP 采用独立 closed allowlist，不能代替业务 Device。
每个实际 scope／action 逐项同时满足原 Device 授权、current manager、安装、terminal child、
membership、Policy 与审批。允许 Circle-only 的父成员依赖不自动授父内容读取。
Blob、MLS material、历史验签与 to-device 队列采用同一完整身份和 current 门；scope 不能互相拼接。
Device 的具体 operation/action 配对以 applet-managed-authority-registry.json 为准。

## 19. 管理配置与治理接纳

管理员在 Realm 的治理 Station 发起明确配置意图；治理方验证其权限，调用 Applet runtime 准备候选。
runtime 保管私钥，只返回签名 candidate／Event；治理方核候选、当前许可及适用审批后通过标准 Event submit 接受。
配置请求的 originating_actor 是操作者身份，不是主体所属 Station。新主体属于该 Realm。
accepted 配置结果必须带真实创建 Commit；candidate、pending、unknown 不能宣称创建成功。
详细职责、幂等和精确结果恢复见 [管理配置](./applet-management-source.md)。


<!-- BEGIN ak-http-signature-covered-set ak.http_signature.scenario.applet_managed_device.v1 -->
- `@method`、`@target-uri`、`@authority`、`arkret-operation`
- `arkret-managed-device`、`destination-service-id`
- `content-digest`（有 body 时）、`idempotency-key`（操作使用时）
<!-- END ak-http-signature-covered-set -->

`ak.vector.capability.applet_bridge_non_event_grant_authority.v1` 约束 Service 业务 parent 和 Realm 主体 terminal child 的真实能力链，不以安装或创建许可替代业务能力。

Applet 受管 Bot／Ghost 的持续同身份恢复由当前管理 Service、accepted recovery policy 与 DID 原生后继共同授权，见 [Realm 主体§10](../extensions/realm-actors.md)。普通创建许可不授予任意映射接管；恢复不重复申请创建，不产生新身份，恢复 current／pending／终态和安全收尾随原 Realm 交接。
