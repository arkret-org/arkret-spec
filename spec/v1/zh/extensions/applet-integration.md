---
title: Applet Integration
status: candidate
normative: true
stability: v1
updated: 2026-09-28
---

> **状态：extension profile（非 v1 core 互操作必需）**。Applet registry、审核 SLA 与 capability
> 注入流程仍在演进。Arkret v1 core 互操作 **不要求** 实现本 profile；声称 v1 core 的
> 实现可以完全不接 Applet，仅通过 capability + actor 模型表达 bot / bridge / agent。
> `ak.profile.applet_service.v1` 视为可选 extension（见 `artifacts/profiles/conformance-profiles.json`
> 的 `profile_sets.extension_profile_implementation`）。Applet v1 家族用继承关系分层:
> base Applet base 使用 `ak.profile.applet_service.v1`，bridge / delegated / E2EE join / widget
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

Applet 的传输/creation 用途，使用自身唯一 `did:webvh` 的 Service signer。
无入站 URL 时仍有该身份，连接方式见 [单主体与调用合同 §2](./applet-client-and-invocation.md)。

### 3.2 Applet Controller

管理 Applet 的人或组织，独立于 Applet 本身。controller 的 package 签名与 registration
证明管理责任；没有 controller 自己的 active accountability grant 时，不得把它写入 Profile
`accountable_principal_ids`。问责数组不替代管理关系或授予权限。

### 3.3 Applet Account

Applet 自身的可见、可 mention Actor 是 `applet_actor_id` 的完整 Account；其 principal core
必须逐字等于 `service_id`，Station 坐标保持独立，不再创建第二个 Bot DID。
安装的 provision + `applet_managed_control` PCR genesis + accountability + Profile 固定集合保留。
其 Service 到同 core Account 的显式自问责记录只声明 Applet 自身承担责任，不能展示为 controller
担保；Profile `actor_kind=service`。Service/Principal 的 signer purpose 和 acceptance anchors
分别验证，见 [单主体合同 §1](./applet-client-and-invocation.md)。

current resolution 仅按 `JCS(applet_actor_id)` 的 PCR typed current 重放；Package/registration
只保存不可变 creation anchors。genesis 不携 founding device，实际 E2EE endpoint 由后继普通
`ak.device.authorize` 的 `applet_managed_delegation` 分支授权，按 §12 与 device-lifecycle §15 验证。

### 3.4 Ghost Actor

外部网络用户在 Arkret 中的镜像 Actor。例如 Slack 用户 `U123` 映射为一个独立 Actor DID：

```text
did:webvh:z6MkGhostU123:slack-bridge.example:ghost:u123
```

`#fragment` 只用于 DID URL 形式的 verification method（例如 `did:webvh:z6MkGhostU123:slack-bridge.example:ghost:u123#key-1`），不得作为 `actor_id` / `applet_actor_id` 的一部分。稳定 `actor_id` 使用 `account` 分支，其中 `account_id.principal_id` 是 adapter projection `ak:did_core:webvh:z6MkGhostU123`，`account_id.station_id` 是承载它的 Station；每个 Ghost 必须有自己的 validated SCID，不能复用 Applet service SCID 后仅靠 host/path 区分。

**Ghost DID 形状约束（normative）**：Ghost 的 `did:webvh` DID MUST 同时满足下列四条；任一不成立，§9.1 的 provision MUST fail closed：

1. **SCID 段独立**：第三个 `:` segment（SCID）MUST 是该 Ghost 自己的 validated SCID，MUST NOT 等于 Applet service DID 或 controller DID 的 SCID。违反本条 reason code 为 `applet_managed_actor_provision_invalid`。
2. **host 段逐字绑定**：紧随 SCID 的 host segment MUST 逐字等于 registration `service_id` 当前已验证解析出的那个 bare `did` 的 host segment。多租户 bridge 不得把不同租户的 Ghost 放到另一个域名下；若将来确需多租户，MUST 由 registration 显式声明的 host 列表放开，MUST NOT 削弱本条。违反本条 reason code 为 `applet_managed_actor_provision_invalid`。
3. **MUST 带 path 段**：host 之后 MUST 至少还有一个非空 segment（例如 `:ghost:u123`）。没有 path 段的 Ghost DID 与「Applet service DID 本身」只差一个 SCID 段，而 SCID 段在 actor namespace pattern 中是通配位，Applet service 会因此命中自己的 Ghost namespace。违反本条 reason code 为 `applet_managed_actor_provision_invalid`。
4. **落在 namespace 覆盖内**：完整 DID（不是 `did_core_id`）MUST 命中该 registration `namespaces.actors` 的某条 pattern（[`applet-schema.md` §2](./applet-schema.md#2-namespace-pattern)）。不命中时 reason code 为 `applet_namespace_mismatch`。

这四条合起来只证明「该 DID 的 webvh log 托管在 Applet 自己的 host 与 path 之下」，即 **web origin 控制权**；它们**不证明** provision 事实，因此 MUST NOT 被当作归属或授权（见 §5）。归属只由已接受的 `ak.applet.managed_actor.provision` 证据建立（见 §9.1）。

Ghost 使用与 Applet 相同的 managed-actor provision + PCR genesis authority 模型，但 role 固定为 `ghost`，
provision 还必须逐字绑定 external tuple。namespace 对经 method evidence 验证的 `initial_resolution.did`
匹配，不能对 `did_core_id` 匹配DID pattern。Profile/accountability Event 不能替代 identity binding，
服务端也不得从 external tuple、namespace 或 Applet service DID 生成 Ghost DID。

Ghost Actor MUST 带有 `accountable_principal_ids`，且本节 provisioning aggregate 创建的初始 Profile MUST 只包含提交并签署同请求 `accountability_grant_event` 的外部 service DID。Applet controller 与 Ghost 的生命周期关系由 active Applet registration / install 记录表达，不得在缺少 controller 自己签发的 active `ak.identity.accountability_grant` 时把 controller DID 复制进该数组；后续若要增加 controller，必须先独立提交该 controller 的 grant，再按普通 Profile update 规则更新。外部网络来源（protocol / network id / user id）记录在 `profile_fields.external_ref`。问责字段以 actor-profile schema 的 `accountable_principal_ids` 为唯一权威形态（见 [`applet-schema.md`](./applet-schema.md) 与 §9）；`accountability` 嵌套对象不是合法 wire 形态。

#### 3.4.1 Agent、Applet 与 Ghost 边界

个人 Agent 仍仅指 controller 经 `ak.self.agent.command.provision.v1` 创建的 `actor_kind=agent`
主体，使用个人 provisioning/runtime key/session/lifecycle。Applet 使用自身 Service/Account，
初始 Profile 为 `service`，不走 Agent pairing、agent_key_proof 或 SessionGrant。
Ghost 表示外部人类/账号的独立 provenance，外部账户为 `integration`，外部 Bot 镜像可为 `bot`；
分类字面值不授予 authority。Realm policy MUST 分别控制个人 Agent、Applet 和 Ghost provenance。
shared automation 作为 Applet 自身安装，不虚构没有 owner 的个人 Agent 或另一 Bot DID。
成员、Profile、grant、delegated device、MLS 和 revoke 验证职责都保留，见
[单主体合同 §1](./applet-client-and-invocation.md)。

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
  "controller_principal_id": "ak:did_core:webvh:z2dmjQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn",
  "transport": {"kind":"https_push"},
  "base_url": "https://slack-bridge.example/applet",
  "applet_actor_id": {
    "kind": "account",
    "account_id": {
      "principal_id": "ak:did_core:webvh:z6Mkw8qTnL4rP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z",
      "station_id": "ak:did_core:webvh:z6MkStationScid"
    }
  },
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
        "pattern": "did:webvh:*:slack-bridge.example:ghost:*"
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
    "ak.applet.bridge_error",
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
- `service_id` MUST 是稳定 service `did_core_id`；注册时提供的 `did` 必须经 adapter 投影到它，只接受 did:webvh；https_push 的 endpoint 经 method 验证，client_pull 禁止入站 URL。
- `controller_principal_id` MUST 是 controller `did_core_id`；复制到 registration 的 package proof VM 的 bare `did` 必须经 adapter 投影到它并通过签名验证。
- `applet_actor_id` 是同 Applet subject 的完整 Account `ActorId`；安装单元的 managed-actor provision payload MUST 逐字等于 registration 的该字段，并携 initial resolution 与 method history evidence。一个 registration 只能接受这一个 Applet AccountId，其 principal 必须等于 service_id，且不等于 controller 或任一 Ghost principal。
- `claimed_profiles` MUST 从已验证 package 原样复制到 durable registration，至少包含
  `ak.profile.applet_service.v1`；profile-bound authority 只读取 accepted Event，不得读取
  preview/package cache。
- `namespaces` MUST 明确声明，不能默认为全网。
- exclusive namespace 冲突时，registry 与执行安装准入的 Station MUST 拒绝后注册者，code=`applet_namespace_conflict`；冲突判定算法（含通配符对通配符）以 [`applet-schema.md` §2.1](./applet-schema.md#21-exclusive-namespace-冲突判定normative) 为唯一规范源。`namespaces.actors[]` 的每条 pattern MUST 满足 [`applet-schema.md` §2](./applet-schema.md#2-namespace-pattern) 的形状约束，否则 code=`applet_namespace_pattern_invalid`。
- `requested_scopes` 只是请求权限，不是实际授权。
- 实际权限 MUST 通过 capability grant 授予。
- `registration_epoch` MUST 进入 payload required 字段，并严格按 [`applet-schema.md` §1.0.1](./applet-schema.md#101-registration_epoch-transcript-与计算算法normative) 的 closed transcript、集合排序、JCS、域分离与 SHA-256 步骤覆盖 canonical derived registration、service DID Document digest/version evidence、accepted signing key set、endpoint/auth material。grant 存储与匹配只绑定该 epoch；reducer/verifier 仍 MUST 展开已接纳的 epoch evidence，校验其 DID Document digest / signing key 与 epoch 捕获值一致。初次接纳、续订、已知失效与明确 current 操作按 applet-schema 的刷新规则验证；同 accepted epoch 的普通发送不要求重新在线解析 DID。
- `proof` MUST 是已验证 package controller DID detached proof 的逐字副本，`payload_digest` 覆盖 canonical package（不含 package `proof` 自身）；空对象、旧 `event_digest` 或与同一安装 package 不同的 proof MUST 以 `schema_violation` / `proof_invalid` 拒绝。formal registration Event 由安装管理员自己的 Event proof 覆盖，并由接收 Station 加 admission proof；不得把 package proof 当作 Event proof。

## 4a. Applet Package 与安装聚合操作

开发者发布 Applet 时 SHOULD 发布 controller-signed **Applet Package**。Package 是分发对象，不是 Realm history event；进入协议事实前 MUST 派生为 `ak.applet.registration` payload，并由获授权的 Realm administrator actor 通过 Station 的安装聚合操作签发实际 grant。

Package 最小字段以 [`applet-schema.md` §1a](./applet-schema.md#1a-applet-package-schema) 的字段参考表为唯一规范源；本节不重复维护字段表。Package MUST NOT 自行授权写入 Realm。Package 接受、registry 收录、namespace claim 或 `requested_scopes[]` 出现某 action 都不得被 reducer 解释为 grant。`registration_epoch` MUST 随 claimed profiles、namespace、base URL、webhook auth、endpoint key、requested scopes、widget origin、E2EE request、receive/rate-limit 行为或 DID/key evidence 改变而改变。

Package -> registration 派生映射同样以 [`applet-schema.md` §1a](./applet-schema.md#1a-applet-package-schema) 的映射表为唯一规范源。本节只补充安装语义：派生出的 registration 成功写入仍不授权；只有随后签发的 grant 与 `(applet_id, effective_scope, registration_epoch)` 绑定并保持 active，Applet 才取得对应 scope 的 effective install。

registration 的历史资格使用 [current-results §2](../sync/current-results.md#2-领域-selector-与-revision) 的 `applet_registration` 实例。连续重申同一 registration_epoch 及全部 security bindings 不产生新实例；真正替换时关闭旧实例，改回相同业务值仍是新的 Event 实例。旧实例被关闭排除的 Event 不因同 epoch 再出现而复活。effective install 另展开实际 grant、scope、membership 与 controller 等依赖，不能合成 install generation 或以 service-local fence 冒充已确认 revoke。

## 4b. Install Preview / Commit / Revoke

Applet 安装使用 self/admin aggregate operation。它不创建 install 专用 durable Event；Applet 基线的固定事实集合是
`ak.applet.registration`、一个或多个 `ak.capability.grant`、恰好一个
`ak.applet.managed_actor.provision`、恰好一个 purpose=`applet_managed_control` 的 `ak.realm.create`、
`ak.identity.accountability_grant` 与 `ak.profile.create`。服务端必须先验证完整集合，再按上述顺序在同一
durable transaction 中接受 Events、projection、Applet record 与 idempotency outcome；不得暴露 staged
registration/grant，任一失败整个单元不可见。membership、E2EE 与 widget effect 仍使用各自登记的事实。

新增 operation:

| operation_id | HTTP | 语义 |
| --- | --- | --- |
| `ak.self.applet.install.command.preview.v1` | `POST /_arkret/self/applets/install/preview` | 校验唯一内嵌的管理员 formal Events，返回 canonical `InstallPlan` 与目标 Station 签名的短期 authoring request。 |
| `ak.edge.applet.managed_actor.command.author.v1` | `POST /_arkret/edge/applet/managed-actors/author` | Applet service 消费 `install_applet|provision_ghost` 的统一 signed request，签 role-neutral 四 Event bundle，并按 branch subject + full request digest durable exact replay；不 mint request ID。 |
| `ak.self.applet.command.install.v1` | `POST /_arkret/self/applets/install` | 提交安装，必须带 `Idempotency-Key`、exact signed authoring request 与 exact Applet bundle。 |
| `ak.self.applet.revoke.command.preview.v1` | `POST /_arkret/self/applets/{applet_id}/revoke/preview` | 只读重算 active install，返回 canonical `AppletRevokePlan`；`revoke_plan_digest` 由 caller 自算。 |
| `ak.self.applet.command.revoke.v1` | `POST /_arkret/self/applets/{applet_id}/revoke` | 提交 caller-signed revoke saga，必须带 `Idempotency-Key` 与 preview digest。 |

`effective_scope` 是单次 install 的唯一目标:

- `kind="realm"` MUST 只包含 `kind` 与 `realm_id`，并只给出 Realm resource ceiling，实际 grant MAY 用 exact 子资源缩小范围。
- `kind="circle"` MUST 同时包含 `kind`、`realm_id` 与 `circle_id`，并约束为该 Circle grant；不得由 Circle install 推导 Realm-wide grant。
- 单次 install operation 只处理一个 `effective_scope`。多 Realm、多 Circle 批量安装和跨 sovereign server 的 install 事务聚合不是 v1 目标。
- durable effective install 的唯一键是 `(applet_id,effective_scope)`。同一键不得同时存在两个 active install；
  同一 `applet_id` 的不同 scope install 必须复用首次 accepted managed-Applet anchors，但各自保存 registration、grant、
  install outcome、幂等与 revoke saga 状态。实现不得以单独 `applet_id` 作为安装唯一键，也不得把首个 scope 的
  registration/grant 镜像成后续 scope 的 authority。
- install preview/commit MUST 由目标 Realm 的 controlling Station 承载；内部 authorization worker 不产生独立 discovery target。Applet authority 固定集合跨 portal lineage 与新建 PCR，只允许 `actor_id.account_id.station_id` 导出的同一 Station 在本地 closed aggregate 中接受，既不把 install operation 变成跨 server 分布式事务，也不得把固定集合拆成逐 Event peer federation。安装后的普通 Collaboration Realm Event 才按各自 federation 规则传播。
- install commit 的授权门是机读 `ak.realm.admin` capability(§4)：commit 提交的 admin actor MUST 持有覆盖目标 Realm 的 active `ak.realm.admin` grant；fixed set 中的 `ak.applet.registration` 是该 capability action 的目标 event kind。Station authorization capability 的 reduce-time 校验缺少该授权时 MUST fail closed,code=`applet_registration_unauthorized`，且整个本地事务零写。
- `authoring_request.basis.registration_event` 与同一 basis 中每条 `capability_grant_events[]` MUST 是该 admin caller
  已完成签名、可直接进入通用 Event admission 的 formal Event；服务端 MUST NOT 重建 Event、
  改写 event id/checkpoint/authority commit basis、以 Station service key 代签 producer Event，或替 grant issuer 生成
  payload proof。`registration_event.actor_id`、每条 grant Event 的 `actor_id`、grant `issuer`
  与 authenticated install actor MUST 全部逐字相等。
- `ak.profile.applet_bridge.v1` 对 non-event action `ak.applet.ghost.provision` 的唯一首发
  authority 是其机器 artifact `non_event_grant_authority_rules[]`：issuer 必须在同一
  `expected_revision` 对应的已确认状态下持有覆盖 effective scope 的 `ak.realm.admin`；registration
  必须已 accepted、`claimed_profiles[]` 包含 `ak.profile.applet_bridge.v1`、service/epoch/
  requested scopes 与 grant 的 subject、`applet_authority` constraint 及 action 逐字绑定。
  Realm owner、membership、package controller proof 或 install endpoint authentication
  均不得替代该 authority。规则只覆盖 `ak.applet.ghost.provision`，不得类推到其它
  non-event action。
  owner/profile/binding 正负向矩阵由
  `ak.vector.capability.applet_bridge_non_event_grant_authority.v1` 定义；该向量当前为 `reserved`，
  补齐 fixture 并回到 `active` 后 conformance 必须执行。

当 controller proof 无效、DID Document 不可解析或 key ref 不匹配、namespace pattern 非法（`applet_namespace_pattern_invalid`）、exclusive namespace 与 active install 冲突（`applet_namespace_conflict`）、requested action 不在 capability registry、effective_scope 所属 Realm policy 禁止 Applet/Ghost Actor/widget/E2EE、或 package 已过期时，Preview MUST fail closed。Commit 重算 plan 时 MUST 复验这两项并返回同一 code。

Commit MUST 执行：

- 在同一 durable transaction 中持久化完整 install execution record、formal fixed set、projection、Applet record 与幂等结果。
- 从四条 creation Event 的 producer proof 与 registration epoch material 独立解析并验证同一 exact Applet
  `Service` verification method、public key 与 service binding。closed producer proof 不携带 signer evidence
  或尚未产生的 RealmCommit 引用。全部事实接受后，Station MUST 在同一事务中以目标 Collaboration Realm
  的实际 accepted Realm stream head 及本次 accepted 时间物化完整 `Service` signer evidence root，
  同时耐久保存该 root；不能接受 verification-method hash、裸 key digest 或 caller 自报 verified 代替。
- 对同一 `Idempotency-Key` + 同一 body canonical hash 重试返回同一结果和同一批 accepted event refs；同一 key + 不同 body MUST 返回 `duplicate_conflict`。
- 服务端在事务开始前验证 caller 提交的每条 Event canonical bytes、event id、proof、checkpoint、依赖与 fixed-set 交叉绑定；事务内任一 CAS 或持久化失败必须回滚全部 Event 与 record。重试只读取同事务保存的 exact outcome，不得生成替代 id、重建 Event 或恢复逐步提交。
- 重新计算 plan；不得盲信客户端传回的 `InstallPlan`。
- 从 `authoring_request.basis.capability_grant_events[]` 提取 actions/resources，与 package requested scopes、当前 Realm/Circle policy 取交集后重建 Approved Capability Set；不得接受未请求 action、scope widening、重复 action，或缺少 `authority_control.applet_authority` 精确绑定的 grant。commit 不镜像这些 Events。
- `authoring_request.basis.registration_event.payload` MUST 与 package 派生 registration payload canonical bytes 完全相同；每条 grant 的完整 subject authority pair MUST 等于 `(package.service_id, authoring_request.basis.target_station_id)`，resource MUST 等于 basis 中唯一 `effective_scope`，constraint MUST 绑定相同 `applet_id + service_id + registration_epoch`。任一不匹配 MUST 在提交首条 Event 前 fail closed。
- preview 对 registration epoch evidence 解析出的 exact DID method version MUST 要求状态为 current/active；可解析但已 deactivated 的 service DID 必须以 `applet_registration_epoch_evidence_deactivated` 独立 fail closed，不得误报 document-unresolvable，也不得回退到未版本化 current DID、package sibling 或 service-local key。
- 当 recomputed plan canonical `plan_digest` 与 signed `authoring_request.plan_digest` 不一致时 MUST fail closed，返回 `applet_install_plan_mismatch`，并要求管理员重新 preview/approve；commit 不携第二个 plan digest。

正式安装的 registration、grant、Applet provision、PCR genesis、accountability 与 Profile 是本地单事务 fixed set；preview-time 或 reduce-time 任一步失败都 MUST 零 Event、零 projection、零 Applet record、零幂等结果。该 fixed set MUST NOT 写 federation outbox；远端不能用 `ak.peer.events.command.submit.v1` 单独重放其中的 `applet_managed_control` genesis。

Revoke 使用 caller-signed event-log saga。请求中的 `effective_scope` 与 path `applet_id` 共同选择唯一 current
effective install；该操作只撤销这个 exact install，不得隐式撤销同一 Applet 在其它 scope 的 active install。
preview MUST 从该 current effective install 精确枚举每个 active
grant、applet-managed bot/ghost membership 与 widget scoped token，返回 canonical
`AppletRevokePlan`；preview outcome 不携 `revoke_plan_digest`，caller 自算
`revoke_plan_digest = SHA-256(RFC 8785 JCS(revoke_plan))` 并填入 commit request。plan 中每个 grant 对应一条
`ak.capability.revoke` intent。每条 intent MUST 必填 `expected_revision`，并且 Station MUST 从同一个 durable
`capability_grant` current-result snapshot 原子取得 active Grant value 与该 revision；不得把 authorization 内存索引、
另一次 current read、GrantId、create EventId、Realm stream head 或列表 digest 拼成 authoring basis。该 revision 是 canonical
plan 的成员，因此进入 JCS bytes 与 `revoke_plan_digest`；caller MUST 原样复制到对应 caller-signed
`CapabilityRevokePayload.expected_revision`。每个需要离开/移除的 managed member 对应一条 `ak.member.state` intent。
projection 不完整时 MUST fail closed 并要求先重建 projection，不得按 namespace pattern、旧 request 或
本地默认值猜测 grant/member/token。

Commit MUST 携 `revoke_plan_digest`、与每个 grant intent 一一对应的 caller-signed
`capability_revoke_events: EventAdmissionSubmission[]`，以及与 membership intent 一一对应的 caller-signed
`membership_state_events: EventAdmissionSubmission[]`。服务端必须在首个副作用前重算 plan，并逐字节验证
Event kind、scope、registration epoch、grant/member target、capability `expected_revision`、membership transition 与 reason；任何遗漏、
多余或不匹配均 fail closed。服务端不得代签、补写或重建 Event，也不得以本地 grant row / revoked flag
替代正式 Event admission。Event 的 canonical bytes 完成后才能派生 Event ID；不明结果与 retry 只能重放
request 中相同的 signed Event bytes。

preview 之后若任一 Grant revision 已变化，commit 重算的 plan/digest mismatch 或 Event admission 的 `cas_conflict`
MUST 零新增领域副作用；caller MUST 重新 preview、重新取得用户确认并重签整组受影响 Event。服务端与客户端均不得把
旧 signed Event 在线改写为新 revision。response-loss retry 只能重放原 exact request bytes；它可以返回原幂等结果，
不能借 retry 放宽 current CAS。

Commit 在首个副作用前 MUST 持久化 saga ledger：绑定
`(principal_service_id, admin_actor_id, Idempotency-Key, canonical_request_digest,
revoke_plan_digest, exact_event_submissions, status, steps[])`。每个 step 的状态固定为
`pending|accepted|duplicate|rejected`，并在继续下一步前持久化。Event admission、widget token 作废与本地
applet fence 可以跨服务执行，不得声称分布式原子；restart MUST
从 ledger 恢复同一 submissions 与尚未完成步骤。只有全部 required replicated Events 已
accepted/duplicate、widget token 已作废且 local fence durable 后才返回
`status=complete, ok=true`。Event-backed step 是按状态封闭的 union：`pending`／`rejected` MUST 携原 caller-signed
bytes 唯一派生的 immutable `submitted_event_id`，且 MUST NOT 携 `CommittedEventRef`；只有
`accepted`／`duplicate` MUST 携 admission 返回的完整 `committed_event_ref`，且不得退化为裸 EventId。
widget token 与 local fence 等本地 step 始终携非 Event typed resource `effect_ref`；该分支
不得承载 EventId／RealmCommitId。`revoked_refs[]` 只列实际完成的 effect，使用 `CommittedEventRef` 或本地 typed
resource 的闭合 union，submitted/rejected identity 不得进入。部分成功返回 `in_progress|partially_completed` 与精确 steps/rejected refs；已
accepted Event 不回滚、不重签，只继续缺失步骤。

从第一条相关 `ak.capability.revoke` 或 `ak.member.state` 被 accepted 起，目标 `effective_scope` 内未来 Applet
writes MUST 立即 fail closed，code=`applet_revoked` 或更细 reason，不能等待 saga 全部完成；其它 scope 只有在
其自身 effective install 仍 active 时才继续授权。最后一个 active effective install 被 fence 后，Applet service、
Applet 与全部 Ghost 才形成全局 `applet_revoked` fence。

**撤销模式（normative）**：`revoke_all` 枚举并撤销 exact install 的全部 capability grants、移除该 scope 内的 managed membership、作废 widget tokens 并建立 runtime fence；`revoke_runtime_only` 执行同样的 capability / membership / runtime fence 步骤，但不作废 widget tokens；`revoke_widget_only` 只作废该 scope 的 widget tokens，不改变 grants、membership 或 runtime fence。widget 后续调用仍独立受 current capability / install 状态约束，保留 token 不绕过 runtime fence。前两种模式的 `membership_removals[]` 只枚举当前 `join` / `knock` 的 managed members，目标值固定为 `membership="leave"`，由 caller 按管理员移除权限签署；已 `leave` / `ban` 的成员不产生 same-state intent，禁止把 `remove` 作为 membership wire 状态。Circle scope 只移除对应 Circle membership，不移除 Realm membership。

## 5. Namespace

Namespace 用于决定：

- 哪些未知 actor 可以向 Applet 查询
- 哪些 Realm / portal alias 属于 Applet
- 哪些事件应推送给 Applet
- Applet 可以为哪些 Ghost Actor 申请或声明身份

Namespace 不等于 capability。  
Namespace 命中只表示“这个 Applet 是该名称空间的处理方”。

**Namespace 命中不是归属证明（normative）**：namespace 命中只是**路由与排他判据**，**MUST NOT** 被解释为归属证明或授权。managed actor（Applet / Ghost）的归属由已接受的 `ak.applet.managed_actor.provision` 证据建立（§9.1）；凡该证据可达的判定点，实现 MUST 展开并校验该证据，MUST NOT 以 pattern 命中替代。

namespace 在 provision 证据结构上不可达的判定点仍然是判据——§7.3.1 的逐次投递来源独立验证、§7.4 的未知 actor 发现与推送路由、以及 §4b 中发生在任何 Ghost 存在**之前**的 exclusive 冲突门（provision 的四条创建事实按 §9.1 只由接收 Station 保存并重放，不做 peer Event fan-out，因此这些站点拿不到 provision 证据）。但在这些判定点上，namespace 只回答“谁来处理 / 谁排他占用这个名称空间”，同样不产生任何授权。

该总则与 [`../authz/constraint-schema.md` §7.3](../authz/constraint-schema.md#73-applet-授权绑定constraint_subkindapplet_authority)（grant 的 `executed_by` 不得仅凭 namespace wildcard 签发）以及 §11 规则 4（delegated 代表真人时不得仅凭 wildcard 命中通过）的既有收紧一致；那两条是本总则在具体路径上的实例，不是例外。

### 5.1 Actor Namespace

Actor namespace 适用于 Ghost Actor 和 Applet Account。

```json fragment
{
  "exclusive": true,
  "pattern": "did:webvh:*:slack-bridge.example:ghost:*"
}
```
SCID 位是 `*`：`did:webvh` 的 SCID 在第三个 segment，而每个 Ghost 按 §3.4 MUST 有自己独立的 validated SCID，因此把 Applet service 自己的 SCID 钉在该位置的 pattern 永不命中任何合规 Ghost。pattern 的 host 段 MUST 是字面量且等于 registration service host，path 段 MUST 存在——形状约束与 exclusive 冲突判定见 [`applet-schema.md` §2 / §2.1](./applet-schema.md#2-namespace-pattern)。通配到 SCID 位后，pattern 只证明该 DID 的 webvh log 托管在本 Applet 的 host 与 path 之下，**不证明归属**（见 §5 总则）。

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
      "allowed_data_labels": ["public", "internal"]
    }
  ],
  "expires_at": "2026-07-26T00:00:00Z"
}
```
scope 限制 MUST 只使用 [`authz/constraint-schema.md`](../authz/constraint-schema.md) 登记的 `scope_limitation` 字段（如 `allowed_data_labels` / `allowed_endpoints` / `allowed_*_container_refs` 等）；与具体 Applet install 的安全绑定 MUST 另外使用标准 `constraint_kind="authority_control" + constraint_subkind="applet_authority"`，并完整携带 `applet_id`、`executed_by=service_id`、`registration_epoch`。§5.1 registration namespace 与 §11 Event envelope 的 `applet_id` / `authorization_ref` 是使用时的交叉校验，不能替代 grant 自身的绑定。

除非 Applet 拥有 effective grant，或以委托授权身份显式代表已授权 actor 行事（此时 MUST 满足 [§11](#11-masquerading-与-delegated-agent) delegated agent 的全部字段 `executed_by` / `authorization_ref` / `applet_id` 与对应 reducer 校验），否则 Applet MUST NOT 向 Realm 写入。

## 7. Applet API

本节 Station→Applet HTTP endpoint 适用于 `transport.kind=https_push`。
`client_pull` 把相同已登记操作的 closed task/body/result 经目标 Station 的客户端 exchange
交付，不要求以下入站 URL；首装 bootstrap 与 installed 阶段的认证/队列/取消另见
[主动领取合同 §2](./applet-client-and-invocation.md)。不能把既有 active-install gate 用于初次领取。


Applet API 是 Arkret 节点调用 Applet 的接口。  
Applet 调用 Arkret 节点时使用常规 Events API / Station sync surface / authz API。

Base URL 来自 registration 的 `base_url`。

**出站网络目标策略（normative，SSRF 防护）**：node 在向 Applet registration `base_url` 主动出站（transaction push、ping、describe、resolve 等任意 server-side fetch，含 redirect / Alt-Svc 后实际目标）之前，MUST 执行 [`../sync/api-conventions.md` §11.2](../sync/api-conventions.md) 出站网络目标策略；命中云 metadata / 内网 / 回环等禁止地址类别时 MUST 拒绝出站，`base_url` / webhook endpoint 的 scheme MUST 限 `https`。§4b registration preview / commit 时 MUST 对 `base_url` / webhook endpoint 预检该策略。§7.3.1 的逐次来源签名只证明"是这个 Applet"，不证明"目标 IP 合法"，二者 MUST 同时满足。

**`ak.applet.*` 标识符的两类用途（normative 区分）**：`ak.applet.*` 前缀的标识符根据上下文分属两个互不混淆的命名空间，实现不得把二者当作同一对象：

- **Event kind（进 Realm history）**：`ak.applet.registration` 与 `ak.applet.bridge_error`。这些是 durable Arkret Event，进入 Realm history，由 reducer 按 schema 校验；`ak.applet.bridge_error` payload 以 `artifacts/schemas/event-payload.schema.json` 与 `applet-schema.md` §7 为权威。Applet runtime 的调用进度、私有 session id、opaque params/detail 与实现状态只属于 operation response/stream 或部署本地状态，MUST NOT 写入共享 Realm history；跨实现有意义的业务结果必须落为既有 Event、Strand、Message、Morph、Relation 或封闭的 result artifact。
- **operation_id（HTTP，不进 history）**：本节表中的 edge operations、§4b 的 install/revoke operations，以及 §9.1 的 `ak.self.applet.ghost.command.preview.v1` / `ak.self.applet.ghost.command.provision.v1` 是 HTTP API operation 标识符，只描述 Arkret 节点 ↔ Applet 或 self/admin aggregate operation 的请求/响应绑定，本身不是 wire Event，不进入 Realm history。

`ak.edge.applet.command.transaction.v1` 在 v1 artifacts 中只作为 operation_id 存在，指 §7.3 的 transaction push HTTP 调用；它 MUST NOT 作为 durable Event kind 或 transaction-origin Event 写入 Realm history。transaction push 的幂等记录属于 Applet service / transport audit log；Applet 写入 Arkret 的事实由具体 Event Envelope 的 signed `applet_id`、`external_ref`、`authorization_ref`、event signature 与 capability grant 表达。

字段级接口索引：

本表 **surface / 调用方向** 列区分两类 operation:`edge`（节点 → Applet，鉴权主体为 Arkret 节点，路径 `/_arkret/edge/applet/...`）与 `self`（管理员 → 自有 Station aggregate，鉴权主体为管理员 actor，路径 `/_arkret/self/applets/...`）。二者调用方向相反、鉴权主体不同，实现不得套用同一鉴权模型。

| operation_id | surface / 调用方向 | 必填字段 | 可选字段 | 响应字段 | 约束 |
| --- | --- | --- | --- | --- | --- |
| `ak.edge.applet.read.ping.v1` | edge（节点→Applet） | 无 | 无 | `applet_id: id`; `service_id: did_core_id`; `protocol_version: string` | 可公开，但不得泄露 private namespace。 |
| `ak.edge.applet.read.describe.v1` | edge（节点→Applet） | 无 | 无 | SDK `ServiceDescribe` | public mode 只返回 canonical discovery capabilities；不得私定义 Applet describe DTO。 |
| `ak.edge.applet.command.transaction.v1` | edge（双向） | `header.Idempotency-Key: string`; `applet_id: applet_id`; `source_id: did_core_id` | Applet→Station 为 `events: EventEnvelope[]`；Station→Applet 为 `committed_events: {commit, event, producer_device_evidence?}[]`；两者互斥，均可与 `signals: SignalEnvelope[]` 同时出现，至少一组非空。另有互斥的 `authoring_context`（仅 Station→Applet，见 §7.3.2） | `status: enum(accepted,partial,rejected)`; `committed_event_refs: CommittedEventRef[]`（accepted/partial 必填，可为空）; `rejected: object[]?`; `retry_after_ms: int?` | 成功不能只返回 status；每个 durable accepted Event 都必须以 Event/Commit/stream/position 四元组定位。signals-only 成功返回空 refs。rejected 分支不得携 `committed_event_refs`。字段集权威来源是 [`applet-edge-operations.schema.json`](../../artifacts/schemas/applet-edge-operations.schema.json) 与 [`applet-schema.md` §7](./applet-schema.md)。接收方 MUST 以 exact `applet_id + source_id` 选择唯一 active registration/current epoch，再验证 full/VM 投影、HTTP signature、Event 与 Commit 签名和绑定、namespace 和 capability；不得按 service id 任取首条 Applet。replay key 是 `(applet_id, source_id, Idempotency-Key)`。 |
| `ak.edge.applet.actor.read.resolve.v1` | edge（节点→Applet） | `path.actor_id: percent-encoded RFC 8785 JCS(ActorId)` | 无 | `exists: boolean`; `actor_id: ActorId?`; `display_name: string?`; `external_ref: object?` | path 解码后必须是 closed ActorId，按完整 Actor 命中 Applet actor namespace；不得只比较 principal。 |
| `ak.edge.applet.realm.read.resolve.v1` | edge（节点→Applet） | `path.realm_id_or_alias: string` | 无 | `exists: boolean`; `realm_id: id?`; `title: string?`; `external_ref: object?` | 必须命中 portal namespace 或授权查询。 |
| `ak.edge.applet.read.protocol_metadata.v1` | edge（节点→Applet） | `path.protocol: string` | 无 | `protocol: string`; `display_name: string`; `icon_blob_ref: string?`; `field_definitions: object`; `instances: object[]?`（entry: `instance_id`, `display_name`） | instance list 可要求授权。 |
| `ak.edge.applet.third_party_users.read.list.v1` | edge（节点→Applet） | `query.protocol: string`; `query.instance_id: string`; `query.external_id: string` | 无 | `actor_id: did_core_id?`; `exists: boolean`; `external_ref: object?` | 查询必须逐字匹配 Ghost immutable external tuple。 |
| `ak.edge.applet.third_party_locations.read.list.v1` | edge（节点→Applet） | `query.protocol: string`; 外部 ID query 字段 | 无 | `realm_id: id?`; `exists: boolean`; `external_ref: object?` | 查询字段必须在 portal namespace 内。 |
| `ak.self.applet.install.command.preview.v1` | self（管理员→Station） | `applet_package`; `authoring_request_basis`（唯一内嵌 caller-signed registration/grant Events） | 无 | `{plan, authoring_request}`（契约 `applet-install-authoring.schema.json`） | Station 重算 plan、限制短期 expiry 并签名；registration epoch evidence 只在 registration Event manifest，不属于 package digest / proof。 |
| `ak.edge.applet.managed_actor.command.author.v1` | edge（客户端→Applet service） | `authoring_request` | 无 | `managed_actor_bundle` | 统一消费 `purpose=install_applet|provision_ghost`；四个 role-neutral Event 仅在 bundle 出现一次。 |
| `ak.self.applet.command.install.v1` | self（管理员→Station） | `Idempotency-Key`; `applet_package`; `authoring_request`; 首次分支 `managed_actor_bundle` 或后续分支 `reuse_existing_managed_actor` | 无 | install / commit response 的完整 required 字段集合以 [`applet-schema.md` §1b](./applet-schema.md) 与契约 `applet-install-operations.schema.json` 为权威源 | 两分支 closed XOR；同一 applet/target PS 后续 scope install 必须复用首次 anchors。 |
| `ak.self.applet.revoke.command.preview.v1` | self（管理员→Station） | `path.applet_id`; `effective_scope`; `reason_code`; `revoke_mode` | 无 | `revoke_plan` | 从同一 durable current snapshot 枚举 exact revoke intents；每个 capability intent 必填同一 Grant 的 `expected_revision`，并进入 caller 自算的 `revoke_plan_digest`；见 §4b。 |
| `ak.self.applet.command.revoke.v1` | self（管理员→Station） | `header.Idempotency-Key`; `path.applet_id`; `revoke_plan_digest`; `effective_scope`; `reason_code`; `revoke_mode`; `capability_revoke_events[]`; `membership_state_events[]` | `proof?: AccountLifecycleProof` | `operation_id`; `revoke_plan_digest`; `status`; `steps[]`; `revoked_refs: AppletRevokeEffectRef[]?`; `rejected[]?` | 重算 plan 并逐项校验 signed revoke 的 exact revision；stale 必须重新 preview／确认／重签。Event effect 使用 `CommittedEventRef`；服务本地 effect 使用非 Event typed resource string；见 §4b。 |
| `ak.self.applet.ghost.command.preview.v1` | self（已安装 Applet service→Station） | `path.applet_id`; `realm_id`; `external_ref` | `display_name` | `authoring_request` | PS 从 active install 派生全部 current 坐标并签发唯一 current generation；preview 有 durable winner/supersede ledger。 |
| `ak.self.applet.ghost.command.provision.v1` | self（已安装 Applet service→Station） | `header.Idempotency-Key`; `path.applet_id`; `authoring_request`; `managed_actor_bundle` | 无 | Ghost provision outcome | commit 重验 PS proof、Applet bundle proof、`governance_station_id`、external tuple 与 active install；不接受裸四 Event body。 |

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

Arkret Station 向 Applet 推送 Event/Signal 批次，或按 §7.3.2 交付已确认 managed Actor 的 authoring 初始化结果。

请求示例（非完整 schema）：

```json fragment
{
  "applet_id": "ak:applet:01904100-0000-7000-8000-aaaaaaaaaaaa",
  "source_id": "ak:did_core:webvh:z7SrvceTnL4rP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z",
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

- **node → Applet**（§7.3 上文，Arkret 节点向 Applet 推送）：Applet 端 MUST 按 `Source-Service-ID` 的 accepted service key binding 取得当前有效 verification method，并逐次验证 HTTP Message Signature；逐次验签不等于逐次在线解析 DID。新 service / key、binding invalidation 或显式 freshness 失效时才进入 DID authority resolution。`Destination-Service-ID` MUST 等于接收 Applet registration 的 `service_id`。Applet registration 的 `webhook_auth` 在该方向声明 transaction endpoint 要求 `http_message_signature` 与可接受算法；`webhook_auth.key_ref` MUST NOT 被解释成任意 Arkret 节点的来源 key。
- **app/bridge → arkret edge inbound**（`POST /_arkret/edge/applet/transactions` 的入站方向，已安装 Applet service / bridge 向 arkret edge 推送外部网络 transaction）：arkret edge 接收方 MUST 先用 signed `applet_id` 与 exact Event `scope_ref` 唯一选择 §4b 接受的 active install，并用 `Source-Service-ID`（service `did_core_id`）验证其来源与当前 effective Applet registration，再要求签名 `keyid` / verification method 等于该 registration 的 `webhook_auth.key_ref`；接收方从该 DID URL 取得 bare controller `did`，用已登记 adapter 验证并要求 `project(did) == registration.service_id == Source-Service-ID`，不得把 DID 与 core header 直接比较，并逐次验签。缺签名、签名无效、投影不一致、`webhook_auth.key_ref` 未被该 Applet service 当前状态授权或无 active install 时 MUST fail closed。

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
- `registration_epoch` 是本次方向所使用的 effective Applet registration epoch；它必须同时承诺该方向适用的 `webhook_auth.key_ref` / algorithm policy。registration 不适用、已撤销或无法得到唯一 effective epoch 时不得形成记录。
- `idempotency_key` 是 header `Idempotency-Key` 的 exact value；`content_digest` 是通过 §2.5.1 profile 校验后的 canonical `Content-Digest` structured-field value，绑定 exact canonical body bytes。
- `covered_components` 按 receiver 实际验证的 `Signature-Input` 顺序保存 canonical lowercase component identifier，必须包含本节 required set；`created` / `expires` 是同一 signature parameters 中的整数 UNIX seconds。

记录使用 RFC 8785/JCS；不得增加 implementation-private 成员参与协议比较。每次投递 MUST 先独立验证完整 RFC 9421 transcript、当前 key / registration / active install 与时效窗口。`created` / `expires` 保存在本次认证记录中供 freshness 验证与 audit，**仅这两个成员**不参与稳定幂等绑定；发送方以新的有效签名时间重试同一 body，不得因此成为另一项外部副作用。其 digest 固定为：

```text
stable_delivery_authentication_binding =
  delivery_authentication_record with only created and expires removed

delivery_authentication_record_digest =
  "sha256:" + lowerhex(SHA256(
    UTF8("ak.applet.delivery_authentication_record.v1\n") ||
    RFC8785_JCS(stable_delivery_authentication_binding)))
```

receiver MUST 从本地派生记录重算 digest，不得信任 caller 或 cache 输入的预算值。domain label 不是 `delivery_authentication_record` 的成员，实现 **MUST NOT** 把它以 `domain`、`profile` 或任何其他键插入记录后改算 `SHA256(JCS(record))`；该标签只以上式的 UTF-8 前缀形态参与摘要。记录的字段集封闭为本节列出的成员，**MUST NOT** 追加 `Signature` bytes、原始 `Signature-Input` 字符串、webhook 认证配置或请求摘要等本节未列出的成员。幂等 / replay equality 是上述稳定投影重算后的 digest 相等，MUST NOT 再比较完整记录中的 `created` / `expires`。完整记录与两个时间成员仍必须保存；接收方可以另存逐次 audit，但不得刷新原 outcome、重做副作用或用旧窗口代替本次 freshness 验证；实现私有 audit metadata 可以与记录并列保存，但不得改变该 equality。实现不得只用裸 `Idempotency-Key` 或 body 内 `source_id` 决定重复投递，也不得在 service DID key rotate、registration epoch 改变或 active install 撤销后把旧记录当成新授权。

`source_id` 只认证来源服务，不认证每条 durable Event 的业务 actor。arkret edge 把 Applet transaction 落为 Arkret Event 时，仍 MUST 对每条 Event 独立验证 `actor_id`、`applet_id`、`authorization_ref`、`external_ref` / provenance、`producer_proof` 与 registration `namespaces.actors` / capability grant；Ghost、Applet Account 或 delegated native actor 与 source service 不一致时 MUST fail closed（`applet_namespace_mismatch` / `capability_denied` / `applet_registration_unauthorized`，按失败层级选择）。

**失败码（normative）**：

按 [`../sync/api-conventions.md` §5](../sync/api-conventions.md)，唯一机器判别字段是 RFC 9457
Problem 的 `type`（`https://arkret.org/problems/{code}`）。下列三种签名失败各有自己已登记的
code 与 `type` URI，接收方 MUST 直接返回该 code，MUST NOT 返回通用 code 再用 `reason` /
`reason_code` 做第二次分派；consumer 也 MUST NOT 从扩展成员反推签名失败类别。

- 缺 `Signature` / 纯 bearer：`http_signature_required`（401，`type=https://arkret.org/problems/http_signature_required`）。
- 签名验证失败、`Content-Digest` header profile 不符合 [`../sync/service-http-binding.md` §8.2](../sync/service-http-binding.md)、digest 不覆盖 exact HTTP content bytes、wire 本身不是 canonical JSON，或 `source_id` 与 header / transcript 不一致：`http_signature_invalid`（401，`type=https://arkret.org/problems/http_signature_invalid`）。
- `created` / `expires` 超出时效窗口（含 replay cache evict 后的窗口外重放）：`signature_window_invalid`（401，`type=https://arkret.org/problems/signature_window_invalid`）。
- inbound 方向 exact `(applet_id,scope_ref)` 从未存在可验证 accepted install，或 `Source-Service-ID` 与该 install registration service 不一致：`applet_registration_unauthorized`（403）。已验证 exact install 因 revoke fence / capability revoke 失效时返回 `applet_revoked`；不得搜索其它 scope 的 install 来替代，也不得把 revoked install 误报为从未授权。认证失败仍优先返回对应签名失败 code，不泄露安装状态。
- 幂等 identity 已存在但 canonical body digest 或稳定 `delivery_authentication_record_digest` 不一致：认证成功后 MUST 返回 `duplicate_conflict`；认证未通过时 MUST 优先返回上述对应的认证失败 code，避免泄露历史 transaction 状态。

transaction push 的逐次签名是传输层来源认证，**不替代** §8 每条 Applet-originated 写入 Event 的 envelope event signature（`producer_proof`）与 capability grant 校验：arkret 把外部 transaction 落为 durable Arkret Event 时，仍 MUST 按 §8 / §11 校验每条 Event 的 `actor_id` / `applet_id` / `authorization_ref` / `producer_proof`。

#### 7.3.2 已确认 managed Actor 的 authoring 初始化

普通发送的 Applet producer MAY 消费其安装所绑定 Station 的已确认结果。该角色服从 own-Station result 的信任边界：结果提供构造普通 Event 所需的已确认配置和引用，MUST NOT 作为接收 Station 的准入证明。接收 Station 仍独立验证原 producer、安装、grant、membership 与适用关闭依赖；本节不授予 Applet 读取整个 Realm/PCR 的权限。另承担治理消费者角色的 Applet 仍 MUST 从独立可信起点验证 authority-commit 证明，不能从此结果创建 governance-Station trust。

`ak.edge.applet.command.transaction.v1` 的请求具有两个互斥的封闭分支：既有 Event/Signal 批次，或 `authoring_context`。后者只允许 Station→Applet；Applet→Arkret 入站出现该分支 MUST 返回 `schema_violation`。该分支不得同时包含 `events` 或 `signals`，完整 canonical body 上限为 16 MiB。结果结构由 `applet-edge-operations.schema.json#/$defs/applet_managed_actor_authoring_context` 定义，字段顺序为：

| 字段 | 精确含义 |
| --- | --- |
| `committed_request` | 本次实际提交并确认的原请求。复用既有 install 首次/复用请求或 Ghost provision 请求的封闭类型，不创建第二个 request ID、digest 或 actor anchor 副本。 |
| `realm_stream_head` | 目标 Collaboration Realm 的 commit stream 在该确认时刻的 head，形态是 [`realm-commit.schema.json#/$defs/stream_head`](../../artifacts/schemas/realm-commit.schema.json)（`{stream_ref, stream_position, commit_id}`）。它是安装/portal Collaboration Realm 的唯一 head 声明，与下述 PCR Commit 独立；MUST NOT 从另一流 position 或 Commit 引用推断。本上下文不再单独声明 digest suite 或 actor checkpoint：suite 由该 stream 所属 Realm 对象承载（见 [`realm.schema.json`](../../artifacts/schemas/realm.schema.json)），managed Actor 的既有位置由 `committed_request` 的不可变 anchors 唯一确定，接纳方的授权判定记录留在 Station 本地、不是可交付字段。 |
| `principal_control_commit` | 接受本 managed Principal resolution 的实际 PCR Commit，与 portal head 独立；首次必须覆盖原 Bundle PCR genesis，rotation 必须等于 lineage 最后 Commit。 |
| `applet_service_signer_evidence` | 安装所接受 Applet service producer 的 exact `Service` root，含 `signer_resolution_evidence_ref` 与完整 leaf；ref 必须从 leaf 重算。 |
| `managed_actor_signer_evidence` | 新 Applet/Ghost current method 的 exact `Principal` root 及其唯一 Station `Service` attester leaf。`signer_resolution_evidence_ref` 必须从完整 canonical `authenticated_signer_evidence` 重算；attester leaf **没有自己的 ref**——signer-resolution evidence 是紧凑六成员对象，不带 attester ref，该 leaf 的绑定由本对象内的位置、与 `authenticated_signer_evidence.authority_commit_id` 相等，以及其 subject 必须是签署该 accepted resolution 的 Station `Service` 三者共同承载（见 [`../identity/key-management.md` §「可复用当前授权」](../identity/key-management.md)）。 |

上述五个基础字段全部必需；后续轮换另外携带 optional `resolution_update`（四个 closed 成员见下文），首次与 reuse 不携带该成员：本节下文把「产生 accepted authoring result」本身条件化在两份 signer evidence 已被验证并与结果、原请求、outbox 意图同事务冻结之上，因此缺任一份的上下文根本不可能被接纳。

安装 Station MUST 在原 install/Ghost closed unit 实际 committed 且全部效果完成安装后，从同一 accepted
resolution projection 物化 managed Actor `Principal` root，并冻结签署该实际 PCR RealmCommit 的 Station
`Service` leaf。三个 leaf 的 `authority_commit_id` MUST 逐字等于本上下文 `realm_stream_head.commit_id`，
`resolved_at` MUST 为该完成提交实际冻结的 accepted 时间，不得由 author 阶段猜测未来 Commit。
同一完成提交物化的 Applet `Service` root、Principal root、attester leaf、完整结果、原请求及 Applet
交付 outbox 意图 MUST 属于同一可恢复的原子提交。任一 root/ref/closure 冲突使该完成提交整体回滚且不产生
accepted authoring result。若协议实现将 RealmCommit 确认和派生效果安装分阶段，完成阶段也 MUST 先核确切已确认原
unit，再原子保存效果、evidence、结果与 outbox，不能以已有一条 timeline row 认定整个单元完成。
pending/rejected 不产生结果。该 outbox 是本地 Station→Applet 完成交付，MUST NOT 把私有 fixed set 拆为
Realm Event federation。管理员在安装返回后离线不影响重试交付。

接收 Applet MUST 先执行 §7.3.1 的逐次 RFC 9421 来源认证，且 body/header/source proof 的来源 MUST 等于 `committed_request.authoring_request.basis.target_station_id`，目标 MUST 等于同一 basis 的 `service_id`，外层 `applet_id` MUST 等于 basis 的 `applet_id`。已知其他 Station 的有效签名不能覆盖本安装来源。原 authoring request/bundle 的结构、内容 digest、audience 与全部交叉绑定 MUST 成立；收到 own-Station 结果不构成对外可转交的管理员或治理证明。

首次 install 或 Ghost provision 的原四 Event Bundle MUST 与 runtime 在 author 阶段已经耐久保存的 exact request/bundle 相等，并使用当时保存的身份密钥。后续 scope 的 install reuse 分支 MAY 首次向 runtime 交付该 scope 的新 request；runtime MUST 将其 `reuse_existing_managed_actor` 全部不可变 anchors 与首次保存的 Applet 身份精确匹配，不得重新生成 Applet、PCR、Bundle 或私钥。丢失原身份材料时 MUST 保持未决并恢复原材料，不能从结果重造平行身份。

`realm_stream_head.stream_ref` 指向的 Realm MUST 等于 install effective_scope 的 Realm 或 Ghost basis 的 `realm_id`；完整 Actor MUST 等于该原 Bundle 或 reuse anchors 的 managed Actor，且其 Account Station 与安装目标相等。Circle install 保留原 Circle scope，MUST NOT 扩为整个 Realm。适用的 grant 从原 committed request 和 runtime 的原授权记录取得，缺材料保持未决；`accountability_grant` 仅表达责任，MUST NOT 当作普通发送 capability。跨授权域引用可以各自使用其 Realm 对象登记的 digest suite。

`principal_control_commit` 是独立 required 的完整 accepted RealmCommit，接受 managed Actor 当前
resolution 的实际 PCR Event；首次创建时必须覆盖原 Bundle 的 managed PCR genesis，并与其
realm_id / Event digest / governance Station 精确绑定。managed Principal root 及唯一 Station Service
attester 的 `authority_commit_id` / `resolved_at` 必须等于该 Commit 的 id / `committed_at`。
它不是安装/portal Realm 的 `realm_stream_head`，不得比较两流 position 或把 portal Commit 冒充
PCR authority。install reuse 保留 runtime 已验证的 current PCR closure；若缺轮换前驱材料，先按
下述 completion 有序恢复，不能仅凭新 scope 的 install 重造 root。

runtime MUST 验证两个完整 evidence object，重算 Applet `Service` root、Station attester `Service` root 与
managed Actor `Principal` root，逐字核对 actor、service、verification method、实际本地 public key、原
registration/install/provision anchors 与 effective install fence；随后把确切来源记录、原 committed
request、对应原身份/授权材料、两个 producer roots、attester closure、`realm_stream_head` 与 authoring 上下文
原子保存，才返回 `status="accepted"`。该分支没有 partial 安装。完全相同的重投只确认原持久结果，不重置
Actor checkpoint，不重新签发或替换 evidence，不覆盖已经冻结的待发送 Event，也不刷新首次观察时间。不同原文
或绑定不得复用同一幂等身份。迟到结果不得使 checkpoint 倒退、清除已知关闭或重新打开旧授权实例；接收方可以
确认已保存的旧结果而不恢复其 live 资格。

完成交付后的普通聊天不要求逐消息查询原 Station或续订 RealmCommit 年龄租约；producer 也不需为无关 stream 前进重新 author。每条新聊天 Event 仍须由目标 stream 的 current governance Station 接纳并签发 RealmCommit。原授权的真实有限期与已 committed 关闭约束新 live 提交；非 authority 接收方只能排队／转发。仅因 authoring preview 的有效期已过，不得否定已经 committed 的原结果或强制重新 author；未提交的新请求仍执行 preview 的原期限。重启必须恢复原件，不得用任意入站消息的授权判定、用户填写的 RealmCommit ID 或重新读取 current DID 的结果冒充本次完成材料。

managed Actor 后续通过普通 `ak.identity.resolution.update` 轮换时，旧 root 继续只验证旧 Event。
唯一交付载体仍是本节 node-to-Applet completion：`authoring_context` 的 optional
`resolution_update` 选择 closed rotation 分支（[`applet-edge-operations.schema.json#/$defs/managed_actor_resolution_update_evidence`](../../artifacts/schemas/applet-edge-operations.schema.json)），包含
exact accepted `resolution_event`、从 runtime 已持旧 Principal root Commit 之后到本 Event covering Commit
为止的连续 `commits`、该新 resolution 的完整 `method_history_evidence`，以及原 target Station 的
`attester_resolution`。仅向原 install/provision 已授权的 managed runtime 披露其自己的 PCR
材料；公开 resolution 响应不扩张，也不存在另一条 evidence endpoint 或 governance-dependency 读取面。

Station MUST 在接受 resolution 的同一耐久事务保存新 Principal root、唯一 Station Service attester
leaf、完整 closure 与 completion outbox。两 leaf 的 `authority_commit_id` / `resolved_at` 分别精确等于
lineage 最后 Commit 的 id / `committed_at`。单独 PCR rotation completion 的原 Applet Service registration root、原 `committed_request`、
原四 Event anchors 与 effective scope 保持逐字相同；delivery 幂等身份绑定这个新 resolution Event，
不同原文不得复用。lineage 每条 Commit 的 stream / predecessor / position / 签名及最后 Event digest 必须
独立验证；Station 历史 key 由完整 Service native history在各 Commit 时点选择，不能拿 current key补历史。

runtime MUST 在提交轮换前独立耐久保存新私钥及 exact method/native history 准备材料，收到投递时逐字
匹配实际本地新 public key，并独立验证 native successor、SCID/core 不变、旧 root ancestry、exact原
Station 与上述全部交叉绑定，才原子保存新 root / closure 并启用新 method。缺新私钥或旧 predecessor
closure 保持未决，通过相同 outbox 的有序重投恢复，不从响应重造私钥、旧材料或平行身份。新原件与旧
证据均保留；完全相同重试返回原结果，迟到旧结果不能覆盖更新 root、倒退 checkpoint 或恢复已关闭
install。普通 Event verifier 按 proof ref 使用已冻结的 exact signer root 与原生历史关系，不能以新
current DID head 重写旧 Event 的签名事实。轮换 completion 不授予新 grant、扩大 scope 或恢复撤销资格。同一 Applet 自身主体的 PCR-first 暂停、Service-first 零接纳以及新 epoch/grants 的 Reuse 续订，必须另按 [单主体合同 §1.2](./applet-client-and-invocation.md) 完成；未对齐时不得业务 authoring。Ghost 的独立 native rotation 不改变 Applet Service epoch。

同机 host MAY 经内部类型化存储交付相同结果，但 MUST 保持以上来源、原件、原子保存及重复处理规则，不能用一个公开 bool 或裸配置字符串替代它们。


#### 7.3.2.1 managed PCR 轮换的既有入站（normative）

managed runtime MUST 经既有 `ak.edge.applet.command.transaction.v1` Applet→Station `events[]` 发送原生
`ak.identity.resolution.update`；该请求只含一条该 Event，不混普通 Portal Event 或 Signal。原 Event 的
`actor_id` 为原安装／provision 接纳的完整 managed AccountId，scope 是其派生身份 PCR 的 Realm scope；
MUST NOT 携 `applet_id`、`executed_by` 或 Portal `authorization_ref` 来伪装成 Service 代署。RFC 9421
只认证原 Applet Service 的传输来源，不能代替 Principal 的 producer proof。

接收者仅为原 installing Station。它 MUST 在同一接受事务锁定 exact 原 install／provision、有效
registration epoch 与该 managed PCR；原 Applet、source Service、完整 managed Account、PCR derive、
原 creation anchors 任一不匹配或 runtime/install 已关闭均零写拒绝。该狭窄分支不需要也不创建
SessionGrant，不使用 Portal action/resource grant，不允许更新另一 managed Actor 或 human PCR。

producer 的标准 `did:key:<multibase>#<multibase>` method MUST 逐字属于该 managed PCR current
resolution 的独立认证 native history 中有效 old updateKeys；key DID 本身不被投影为 Account 身份。
验证者 MUST 独立核对 old native SCID/core、完整历史与 witness、原 Event JWS、标准 expected_revision
及其 whole previous resolution projection，并验证 next resolution 的完整 native successor、同 core／
原 Station 和确切新 method/public key；不能以调用方裸 key、当前网上 DID head 或 Service 签名替代。
这是 managed `identity_resolution_update` 的专用 native producer admission，不是普通 Event 验签豁免。

接纳仍沿唯一治理 Station 的一个 Event／RealmCommit UoW，原子推进 current resolution、保存新 roots／
完整闭包及原 runtime 的 completion outbox（§7.3.2）。任何失败或 CAS 冲突均不留下 Event、Commit、
current、root 或 outbox。exact replay 沿原 Event／请求幂等规则，不能接受不同原件或回退 current。

### 7.4 Query Actor

```text
GET /_arkret/edge/applet/actors/{percent_encoded_jcs_actor_id}
```

用于 Arkret 节点发现 namespace 内的未知 Ghost Actor 是否存在。

返回：

```json fragment
{
  "exists": true,
  "actor_id": {
    "kind": "account",
    "account_id": {
      "principal_id": "ak:did_core:webvh:z6MkGhostU123",
      "station_id": "ak:did_core:webvh:z6MkStation123"
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
但 Station 或 Actor kind 不同不是同一查询目标。

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

普通 Applet-originated 写入 MUST 通过 `ak.edge.applet.command.transaction.v1` 的 Applet→Station `events[]` 提交 producer-only `EventAdmissionSubmission`，见 §7.3.1 / §11.1。Applet service 不持有 SessionGrant，不得把 `/_arkret/self/events` 的 Bearer session 路径作为替代入口。§4b install、§9.1 Ghost provision 与设备授权等正式登记的 aggregate / operation 仍使用各自封闭载体。

每个 Applet-originated 写入 Event MUST 包含下列 signed Event Envelope 字段（这些字段均进入 `producer_proof.event_digest`；不得只放在 `unsigned` 中）：

- `actor_id`
- `applet_id`
- `external_ref`，若来自外部网络
- `authorization_ref`
- `producer_proof`

`authorization_ref` MUST 引用 exact install 中真实 accepted 的 active `ak.capability.grant`，并交叉验证 service authority、`applet_id`、registration epoch 与 producer-signed `scope_ref`。其用途由 event-kind registry 的 admission 合同决定：

- capability-gated Event 必须另外验证该 grant 覆盖具体 action / resource；不能以安装成功替代 action 权限。
- `subject_only` Event（如 `ak.invite.accept` 与本人 `ak.member.state` join）不把该 ref 当作 action 授权。该 ref 只绑定 exact installation；本人签名、exact invite、join rule、membership FSM、目标 Realm / Circle policy 与 E2EE admission 仍独立验证。不得为不可授权 action 签发虚构 grant，也不得要求 managed actor 持有 `ak.realm.admin` 才能本人加入。Applet / Ghost 的本人签名按其已登记 managed-principal authority 解析；service 签名不得凭 install ref 冒充任意 native actor。

按事件签署主体进一步区分：

- **Delegated-ghost / masquerading 事件**（`actor_id` 为 ghost / bot / delegated native actor）：`authorization_ref` 必须满足上述 admission 分支；capability-gated 写入须覆盖 Event action / resource（见 §9.1 与 §11）。`ak.identity.accountability_grant` 只证明责任归属，MUST NOT 被解释为 action authorization。
- **Service-actor 自署事件**（`actor_id` 为 `ActorId.service`，`service_id` 等于 registration 的 Applet service，如 portal strand 创建、`ak.applet.bridge_error` 审计等运维 / 审计事件，非委托 ghost）：此类事件不存在委托关系，`executed_by` MUST 省略，`authorization_ref` MUST 指向该 Applet 的 active capability grant，而非 registration Event 或某个 ghost 的 accountability grant。install grant 的 subject 仍是 §4b 冻结的完整 `(service_id,target_station_id)` AccountId；`applet_installation_authority` verifier 只在此 exact install 合同中核对这一 authority pair 与 service producer、目标 Station，MUST NOT 把 account / service variants 当作通用身份等价。签名只证明来源，不能替代 action / resource 授权。

§4b 的合规安装必须为该 Applet 铸造一个或多个与 `(applet_id, effective_scope, registration_epoch)` 绑定的 active grant。安装若未产生覆盖待写 action/resource 的真实 grant，就尚未形成可写入状态，Applet MUST NOT 发送携 `applet_id` 的 Event。需要创建 portal Strand 的 grant 必须覆盖 `ak.strand.create`；需要写入 bridge 审计错误的 grant 必须覆盖 `ak.applet.bridge_error`。不得使用 sentinel ref、静态占位 grant、service 签名或隐式部署特权代替。grant 被 revoke 后，新的 portal Strand 创建与新的 `ak.applet.bridge_error` 都 MUST fail closed；撤销事实由撤销动作及部署侧安全审计记录，不要求已失去授权的 Applet 再写 Realm 审计 Event。

`ak.applet.bridge_error` 是 `capabilities.md` §3.2 与 owner compiled `grant_authority_rule.include_actions[]` 登记的 exact grant issuer exception：root/co-owner 可在安装事务中为此 action 签发上述专用 grant，但这不授予 owner 直接 author 该 Event，也不扩展到其它 Applet profile action。安装及入站接纳仍 MUST 验证完整 Service Account subject、专用 native Service actor 映射、精确 installation/registration epoch/resource、producer 签名与当前 revoke fence。

示例：

```json fragment
{
  "event_id": "ak:event:AQsHmGu_9sPOyJ4aG8VlWQBp8wGGhdC-BjfAaXqrIbk-",
  "realm_id": "ak:realm:Adoyg50aOV537gzxNy87EOdUlHiIujznqwZcMLSGFmzg",
  "actor_id": {
    "kind": "account",
    "account_id": {
      "principal_id": "ak:did_core:webvh:z6MkGhostU123",
      "station_id": "ak:did_core:webvh:z7SrvceTnL4rP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z"
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

### 9.1 Ghost Actor Provisioning（`ak.self.applet.ghost.command.provision.v1`，normative）

bridge Applet 第一次遇到某个外部用户时，先以 active Applet service signature 调用

`POST /_arkret/self/applets/{applet_id}/ghosts/provision/preview`，body 只携
`{realm_id,external_ref,display_name?}`。Station 从本地 active install 派生 registration/grant、
epoch evidence、package digest、service、target PS 与 governance Station，返回 exact signed
`purpose=provision_ghost` authoring request。Applet 再把它提交到统一
`POST /_arkret/edge/applet/managed-actors/author` 取得 role-neutral bundle，最后通过

preview 的 service/app binding MUST 取自签名覆盖的 `Source-Service-ID`、路径
`{applet_id}` 与本地 active exact install；验证器 MUST NOT 要求该 preview body 携带尚未由
Station 签发的 `authoring_request` 或其中的 `basis.service_id` / `basis.applet_id`。

```text
POST /_arkret/self/applets/{applet_id}/ghosts/provision
Idempotency-Key: <opaque-string>
```

请求 Station 原子接受 exact `{authoring_request,managed_actor_bundle}`。请求/响应契约以 [`applet-ghost-operations.schema.json`](../../artifacts/schemas/applet-ghost-operations.schema.json) 为权威；旧裸四 Event 顶层 body 非法。

规则：

- 调用方 MUST 使用 active Applet registration service DID 的 RFC 9421 `service_signature`；签名逐字覆盖 method、target URI、authority、Content-Digest、Source/Destination-Service-ID 与 Idempotency-Key，并使用 registration epoch 内的 current verification method。HTTP 来源签名不替代四条 Event 各自的 proof。服务端 MUST 校验 active exact install、caller、registration、grant、Realm 与 `external_ref={protocol,instance_id,external_id}` 唯一tuple。`actor_id` MUST 为 closed `account` ActorId，且其 `account_id.station_id` MUST 逐字等于本次接收/持久化操作的 Station；v1 不支持伪装 remote hosting 的单阶段写入。违反本条 `actor_id` 绑定（remote station 声明、actor 与 service / controller principal 相撞、或 provision 的 actor 不等于 registration 声明的 `applet_actor_id`）MUST 以 reason code `applet_managed_actor_provision_invalid` 拒绝。
- provision payload role MUST 为 `ghost`，该完整 `ActorId` 尚未被使用，`initial_resolution.did` 的 adapter projection MUST 等于 `ghost_actor_id.account_id.principal_id`，且该 DID（不是 core id）MUST 满足 §3.4 的四条 Ghost DID 形状约束——独立 SCID、host 段逐字等于 registration service host、至少一个 path 段、并命中 actor namespace。namespace 命中只是路由与排他判据，本条的归属结论由本 provision 本身建立（§5）。Applet-managed principal 是长期可轮换的高风险 authority；v1 的 `method_history_evidence` MUST 为完整 `webvh_log`，服务端 MUST 独立验证 inception/current hash chain、SCID、controller proof、适用 witness threshold、freshness 与本地 trust policy。did:web snapshot 和 did:key expansion 均不得用于该字段；service attestation 不能代替 WebVH evidence。`method_history_evidence` 验证失败（chain / SCID / controller proof / witness threshold / freshness 任一项）MUST 以 reason code `identity_method_evidence_invalid` 拒绝。
- PCR genesis MUST 由 Ghost authority pair 建立 purpose=`applet_managed_control` 的新 Realm，critical ref 恰好指向同单元 provision Event，且 `initial_resolution`、Applet、grant、service 与 provision 逐字交叉绑定；任一交叉绑定不成立 MUST 以 reason code `applet_managed_pcr_genesis_invalid` 拒绝。durable Ghost record 保存 immutable provision/genesis anchors，不保存 current source ref。
- **Caller-signed proof contract（normative）**：Station MUST NOT 构造、重建或以自身 RealmCommit-signing key 代签任一 producer Event / payload proof。四条 Event 均由请求携带并按各自 authority 验证；accountability/profile 的 issuer、subject、registration-epoch key、`[service_id]`、external ref 与 critical accountability ref 约束保持不变。
- 创建单元四条 Event 的 `authorization_ref` MUST 逐字相同：provision 以它授权 `ak.applet.ghost.provision`；PCR genesis、accountability 与 Profile 只在这个 exact atomic aggregate 内以同一 ref 交叉绑定创建 authority/accountability 投影。该 ref MUST 指向 active exact install 为 `service_id` 签发、覆盖目标 Realm 的 `ak.applet.ghost.provision` grant；accountability grant 只记录责任关系，**不是**后续 Ghost Event 的授权。后续 Ghost 署名 Event 必须另按其具体 kind/resource 校验 Event 自带的 active capability grant（见 §8、§11）。
- 服务端 MUST 对四条 Event 执行 production proof、checkpoint/dependency、registration epoch、registry reducer 与 preflight 校验。仅 exact 四事件单元 MAY 在 unit-local overlay 中让后项引用前项；普通 submit 不得解析未 accepted ref。
- **失败原子性（normative）**：四条 Event、projection、Ghost record 与幂等结果 MUST 在同一 durable transaction 中提交；禁止逐条 fan-out。
- **hosting / federation（normative）**：四条创建事实只由 `actor_id.account_id.station_id` 指定的接收 Station 保存并重放，不生成 peer Event fan-out。`ak.peer.events.command.submit.v1` 即使 transport/proof 合法也不是 `AppletFormal` admission，单独或普通 Realm bootstrap batch 提交该 PCR genesis MUST 以 `applet_managed_pcr_genesis_requires_closed_aggregate` 拒绝。Ghost 后续写入 Collaboration Realm 的普通 Event 才按该 Realm 的 federation 规则传播。
- 成功时服务端返回调用方所提交的 Ghost Actor `ak.profile.create` 与 `ak.identity.accountability_grant` durable refs；响应 `authorization_ref` 回显上述 provisioning capability grant，不得回显 accountability ref 冒充授权。
- 完成提交还 MUST 按 §7.3.2 原子物化并耐久保存 Applet `Service` root、Ghost `Principal` root及其
  Station `Service` attester leaf，并经既有 `authoring_context` outbox 交付 runtime；同步 provision outcome
  不镜像这些 runtime-private authoring inputs。
- 后续 rotation 使用普通 `ak.identity.resolution.update`，其唯一 predecessor/CAS 输入是 envelope `resolution_projection` 的 `expected_revision`；payload 不镜像 previous ref。Package/Ghost record anchors 不随 rotation 改写，current 只从 `JCS(actor_id)` 的 PCR typed current result 解析。
- `applet_managed_control` PCR 与 human / Agent PCR 使用同一 create-locked Availability holder 规则：successor RealmCommit 的唯一 eligible holder必须从 predecessor closure 中唯一 accepted create 的 actual-author `ActorId` 路由得到，并完整验证其 原始 producer proof 与 historical signer evidence；不得回退到不存在的 member-state holder。
- 对任意 ingress（包括 actor 自签的普通 Event），receiver 一旦由 managed provision/PCR 识别该 authority pair，写入 admission MUST 与该 Event `scope_ref` 对应的 active exact Applet registration、install grant 与 revoke fence 做 AND。Ghost 严格跟随创建它的 exact effective install lifecycle，v1 不定义第二套 per-Ghost revoke 状态或操作；撤销一个 install 后只拒绝该 scope 的新写，最后一个 active effective install 被 fence 后 Applet 与全部 Ghost 才全局拒绝新写。历史读取与 identity-resolution audit 始终可用。
- **幂等（normative）**：同一 `(applet_id, external_ref.protocol, external_ref.instance_id, external_ref.external_id)` 与同一 `Idempotency-Key` 的 exact replay（包含四条 Event 的 canonical bytes）MUST 返回既有 refs，不得重复提交。`external_ref`是唯一tuple carrier，请求不再镜像`protocol/tenant/external_user_id`。相同 tuple 或 key 携带不同 Event bytes / event ids MUST `duplicate_conflict`；`Idempotency-Key` 的保存必须与原子提交同事务。语义与 §7.3 相同。
- provision 不隐含任何 Realm membership 或 MLS 入组：ghost 加入 portal Realm 走常规 membership 流程，加入 E2EE group 还需 §12 的独立 E2EE 加入授权。
- 四 Event 创建单元 MUST NOT 携带设备授权，Ghost PCR genesis 也不携带 founding device。Ghost 参与 E2EE 所需的**受限 delegated device** 与 Applet 完全相同：在该 Ghost 自己的 `applet_managed_control` PCR 中，以 genesis 之后一条普通后继 `ak.device.authorize`（`authorization_binding_kind="applet_managed_delegation"`，`authorized_by` 为 Ghost 自己的 `principal_id`，`applet_id` 为本次 install）授权，见 §12 与 [`../crypto-media/device-lifecycle.md` §5.2.3 / §15](../crypto-media/device-lifecycle.md)。该 authorize 走普通 Event admission，MUST NOT 以 `ak.self.applet.ghost.command.provision.v1` 的封闭 aggregate 携带；它与 Ghost 的其余写入一样跟随 exact effective install 的 revoke fence。

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
  4. `executed_by` MUST 落在 `applet_id` registration 声明的主体集合内:即等于该 registration 的 service DID / `applet_actor_id`，或匹配其 `namespaces.actors` pattern(含 ghost DID namespace)。持有针对 `actor_id` 主体的有效 grant、但 `applet_id` 指向另一无关已注册 applet(其 registration namespace 不覆盖 `executed_by`)时，reducer MUST 拒绝，reason=`applet_namespace_mismatch`。**delegated 代表真人时收紧绑定粒度（normative）**：当 `actor_id` 指向 **native principal DID**（delegated 代表真人行事，而非 ghost 自署名）时，`executed_by` MUST 等于具体的已注册 service DID / `applet_actor_id`,**或一条已 provision（存在 active `ak.profile.create` + §9.1 `accountability_grant`）的具体 ghost DID**；此路径下 reducer MUST NOT 仅凭匹配 `namespaces.actors` wildcard pattern 通过（`applet_namespace_mismatch`）。`namespaces.actors` 通配匹配只对 **ghost actor 自署名**（`actor_id` 即该 ghost）路径有效。否则 applet 可在其自有 registration 声明的 namespace 通配下，用任意未 provision 的 ghost DID 自签 key 代表真人写入，削弱 §9.1 ghost provision 的问责闭环与审计归因。
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

receiver MUST 按原 covering `commit.committed_at` 验完整 Service native history 的 exact历史
assertionMethod、origin Station 与 attestation 原签名，核对完整 AccountId／DeviceId、原授权
Event／generation、device raw signing key及 authorization_window 对 Event created_at 与 committed_at
的覆盖，再用该真实 key 验原 producer JWS与内容ID。设备 evidence 的 attested_at 必须不晚于原接受
cut，其 proof window 在该 cut 有效；不能用 receiver current clock 或后来 current Device status
改判原接受事实。原 attestation完整保存，所以后来撤销、rotation 或 cache deadline经过不使已接受
历史失效。当前 install／registration／可见权限 gate 仍独立执行；证据不授予任意 PCR 读取、SessionGrant
或新 Event 写权。HTTP／RealmCommit 签名、DID Document的普通method与裸publickey均不能代替原设备
签名证据。站点在原接受事务内或同一原子 completion UoW保存该完整root及原件，不能发送后补写。

普通 Applet Event 必须用原始 producer 签名的 `applet_id`、`authorization_ref` 与 `scope_ref` 解析标准 `applet_installation_authority` dependency，精确匹配 registration、grant、scope 和历史授权实例；registration epoch 从 referenced grant 的 `authority_control.applet_authority` constraint 读取，再核对 accepted registration epoch evidence。这里没有额外的 `authority_refs` wire 字段。任何 receiver 都独立验证；不能以某站补签代替，也不能任取同 service 的另一安装。Circle 安装不扩权至 Realm。

## 12. E2EE

Applet 参与 E2EE 时有持续群成员、外部密文转发，以及独立 invocation Circle 最小披露模式：

1. Applet 作为正式成员加入 MLS group。
2. Ghost Actor 作为正式成员加入 portal Realm 的 MLS group。
3. Applet 不解密，只转发外部密文或桥接 metadata。
4. 严格调用：不加入原群 MLS，仅在独立 private Circle 接收明确披露并返回签名结果；由原调用者持钥客户端转交，合同见 [§3](./applet-client-and-invocation.md)。

规则：

- Applet 未加入原群 MLS 时 MUST NOT 获得原群 private state；严格调用仅可经独立 invocation Circle 的 MLS 收到用户明确批准的最小披露，见 [按调用合同 §3](./applet-client-and-invocation.md)。
- Bridge 到不支持 E2EE 的外部网络时，客户端 MUST 明确提示加密边界在 bridge 处终止。
- Applet 托管 Ghost Actor MLS state 时，必须将其视为高敏感密钥材料。

**E2EE 加入授权（normative）**：Applet Account 或 Applet-managed Ghost Actor 加入 E2EE Realm 的 MLS group（上文模式 1、2）MUST 经过独立的 **E2EE 加入授权**，该授权与普通的 capability grant（如 `ak.strand.create` / `ak.message.create` 等写入权限）**分立**：持有写入 capability 不自动授予把 applet / ghost 成员加入 MLS group 的权利。

- 该 E2EE 加入授权 MUST 由 Realm owner、Realm admin 或 Realm policy 明确授权的 administrator actor 通过已 accepted 的 registration `claimed_profiles[]`（含 `ak.profile.applet_e2ee_join.v1`）、exact install grants 与当前 Realm policy 明确同意，并经 Station authorization capability 校验。该同意不允许管理员代写第三方 `leave→join`：Applet / Ghost 必须本人签署 `ak.member.state` 或接受 exact 定向邀请，按 [common-fields.md §4.5](../models/common-fields.md#45-membership-fsmnormative) 的 FSM 准入，Event 必须携 applet provenance。未登记新的 E2EE consent Event / payload 字段，不得自行添加。Welcome 不能替代 membership 或上述同意。
- 缺少该独立 E2EE 加入授权时，Arkret 客户端 MUST NOT 把 applet / ghost 成员加入 MLS group，并 MUST 以 `applet_e2ee_join_unauthorized` 拒绝该加入。
- 成员加入后，客户端在 MLS group 的成员 roster（成员列表 UI 与 audit 视图）中 MUST 显式标注该成员为 **applet-managed**（区别于 native 人类成员），不得让 applet / ghost 成员在 roster 中表现为普通 native 成员。该标注与 §9 的 Ghost Actor 协议层可区分要求一致。

**E2EE endpoint 是 delegated device，不是新分支（normative）**：模式 1、2 中实际持有 MLS leaf 的是 Applet / Ghost 的**受限 delegated device**，走 [`../crypto-media/device-lifecycle.md` §9.2.1](../crypto-media/device-lifecycle.md) 既有的**普通 device 分支**。Applet 与 Ghost MUST NOT 借用 Agent 分支（§3.4.1），v1 也 **不**为它们新增第三个 recipient endpoint 分支。

- 该 delegated device MUST 由该 principal 自己 `applet_managed_control` PCR 中一条已接受的 `authorization_binding_kind="applet_managed_delegation"` 的 `ak.device.authorize` 授权，形状、possession transcript 与签名方解析见 [`../crypto-media/device-lifecycle.md` §5.2.3 / §5.3 / §15](../crypto-media/device-lifecycle.md)。该 authorize 是 PCR genesis 之后的**普通后继 Event**，不属于 §4b 的 install fixed set，也不属于 §9.1 的四 Event Ghost aggregate；把它塞进任一封闭单元 MUST 以 `applet_managed_pcr_genesis_requires_closed_aggregate` 的对偶规则拒绝，因为那两个单元的形状是逐条固定的。
- 没有这样一条已接受的 authorize 时，客户端 MUST NOT 为该 Applet / Ghost 发布 KeyPackage、MUST NOT 把它加入 MLS group，也 MUST NOT 接受它签署的 MLS durable receipt。此处 fail closed 的是**设备**条件，与上文独立 E2EE 加入授权（`applet_e2ee_join_unauthorized`）是两道彼此独立的门，任一不成立都拒绝。
- 该 delegated device 严格跟随创建该 principal 的 exact effective install 的 revoke fence：install 被 fence 后，该设备的新 KeyPackage 发布、新 Welcome 准入与新 durable receipt MUST 以 `applet_revoked` 拒绝，不得等待另一条 `ak.device.revoke`。

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

任何“安装前策略拒绝”的测试不得让尚未 accepted 的 Applet/Ghost 直接签普通 Event，也不得要求其提前提供未来
`Principal` root。测试必须让已经存在且具有真实 `Service` evidence 的 Applet service 作为 actual producer，
或直接测试 closed install/ghost admission；安装后的 Applet/Ghost 策略负例则必须先以真实 `Principal` root通过
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

`ak.profile.applet_service.v1` 的 base Applet base 基线 MUST 测试：

- registration 签名
- namespace 匹配
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

- `applet_registration` 的字段集由 [`applet-package.schema.json`](../../artifacts/schemas/applet-package.schema.json) 与 [`event-payload.schema.json#/$defs/applet_registration_payload`](../../artifacts/schemas/event-payload.schema.json) 固定（closed，`additionalProperties:false`），至少包含 service DID、`base_url`、namespace、protocol、`requested_scopes` 与 `webhook_auth` signing policy。它**不携带** capability refs 与 expiry：实际授权由独立的 `ak.capability.grant` 承载并有自己的 `temporal` 约束，registration 的时效由 `registration_epoch` 与 controller 的 revoke 表达。
- Namespace pattern grammar（命名空间模式语法）MUST 明确 actor、realm、handle、external protocol id 的匹配边界；namespace 命中不授予写权限。
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
