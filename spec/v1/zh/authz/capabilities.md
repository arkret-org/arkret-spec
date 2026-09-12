---
title: Capability Model
status: candidate
normative: true
stability: v1
updated: 2026-07-13
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Arkret 的权限模型采用 capability 思路，而不是只依赖成员关系或模糊角色。

这样做的原因是：

- `strand`、`message`、`realm`、`morph`、`view` 的动作集不同。
- Strand 的所有 track（含 `synthesis` 与 `discussion`）共享同一 effective scope（由 `Strand.scope_circle_id` 决定，`null` = Realm-default scope，否则指向同 Realm 的 [Circle](../models/circle.md)）。Strand 永远单一 scope，不存在 per-track 安全边界。
- agent 必须被精细授权。
- 授权变化必须可审计。

## 2. 基本原则

### 2.1 授权主体 MUST 使用完整 ActorId

grant 的 `issuer_id` 与具体主体分支的 `subject` MUST 使用闭合 `ActorId`。账号主体使用 `{kind:"account", account_id:{principal_id, station_id}}`；托管 principal 与 service 分别使用对应的 ActorId 分支。裸 `did_core_id` 不足以标识账号，也不得再附加平行的 `*_station_id` sidecar。

Handle、邮箱、域名用户名等人类可读标识 MUST NOT 作为权限主体主键。

**跨 Station 无 principal 授权关联（normative）**：遵守 [`common-fields.md` §4.2](../models/common-fields.md#42-主体引用字段)
的账号隔离铁律。授予 `{P,S1}` 的权限对 `{P,S2}` 没有任何效力；接收方 MUST NOT 因二者 principal、
DID 控制者或签名公钥相同而匹配 grant subject、补足 issuer authority、继承 owner/admin/notary/recovery
角色，或替代已离线、注销或永久失去 Station 的账号。condition selector 的匹配同样 MUST NOT 将同
principal 的另一账号所持 membership、grant 或账号级 claim 当作当前账号的授权证据。其他账号只能
凭独立有效的授权行动，不能将身份相似性作为 delegation、Realm 接管或 Seal 恢复依据。

### 2.2 权限必须显式表达

实现 MUST NOT 依赖以下隐式假设：

- 进入 Realm 就拥有全部能力。
- 能编辑 Strand synthesis 就一定能在 discussion 里发消息，除非有效 access policy 明确继承并授予该动作。
- discussion moderator 天然拥有全量 Strand 管理权。

### 2.3 权限判定基于当时有效的 capability 集

操作是否合法 MUST 由该时点有效 grant 集决定。

### 2.4 ActorId 是业务主体，Claim 是条件

权限模型分三层：

```txt
Business identity: ActorId
Cryptographic principal: did_core_id
Human-readable binding: Handle
Authorization condition: Claim / Attestation
```

## 3. Grant 对象

ID 语义：

- `ak:grant:<44-char-event-token>` 是 durable Capability Grant fact 的规范 ID，由 `ak.capability.grant` Event ID 重类型派生。create payload 同时省略顶层 `grant_id` 和 `grant.id`；reducer 在 `ak.schema.capability.v1` 投影中插入 `id`。grant reference 和 revoke payload 使用该派生 ID；body 本身无签名，签名位于承载它的 Event envelope proof。
- `ak:capability:<uuid>` 只表示抽象 capability definition 引用；MUST NOT 作为 durable grant fact ID 使用。

下例是 reducer 物化后的完整 Grant 对象，不是 create Event payload：

```json schema=schemas/capability-grant.schema.json
{
  "id": "ak:grant:AU1_A5a8MMz_OdxEleQlWPFn-ljdJteaJv3ZZ9APkcrZ",
  "schema": "ak.schema.capability.v1",
  "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
  "issuer_id": {"kind":"account","account_id":{"principal_id":"ak:did_core:webvh:z6qRDFWgaBgTY3UGDLivJztno","station_id":"ak:did_core:webvh:z6mkfixtureissuerstation"}},
  "subject": {"kind":"account","account_id":{"principal_id":"ak:did_core:webvh:z8NNMm8UHw7JcDSuuZd34UisF","station_id":"ak:did_core:webvh:z6mkfixturestation"}},
  "issuer_authority_refs": [
    {
      "kind": "realm_root",
      "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
      "cell_ref": "ak:cell:ak.component.realm.authority_root.v1:null",
      "controller_epoch_at_issuance": 0,
      "authority_generation": 0
    }
  ],
  "actions": [
    "ak.strand.read",
    "ak.strand.update",
    "ak.message.create",
    "ak.morph.read",
    "ak.morph.update"
  ],
  "resources": [
    {
      "kind": "object",
      "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
      "object_kind": "strand",
      "match_scope": "realm_wide"
    },
    {
      "kind": "morph",
      "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
      "morph_kind": "document",
      "match_scope": "realm_wide"
    }
  ],
  "constraints": [
    {
      "constraint_kind": "temporal",
      "effect": "allow",
      "expires_at": "2026-04-30T00:00:00.000Z"
    },
    {
      "constraint_kind": "field_access",
      "effect": "allow",
      "allowed_write_fields": ["metadata.title", "metadata.summary", "content", "metadata.fields.review_status"]
    }
  ],
  "issued_at": "2026-04-26T00:00:00.000Z"
}
```

### 3.0.1 单一 durable signature（normative）

`ak.capability.grant` 的 `event.payload.grant` 是无 `id`、无 `authority_depth`、无 `authority_root_refs`、无内层 proof 的 closed authoring body；这些 reducer-derived 字段若由 producer 自填，schema MUST 拒绝。唯一 durable issuer signature 是承载该 payload 的 Event envelope proof；它同时覆盖完整 `ActorId`、scope、typed authority refs、完整 create body 与时间。Event accepted 后 reducer MUST 以 `retype(event_id,"grant")` 同时作为 cell subject 和投影 `grant.id`。该 Event 的 `actor_id` MUST 逐字段等于 `grant.issuer_id`，且本 kind MUST NOT 使用 `executed_by`。账号与托管 principal 的 server 归属已经封闭在 ActorId 内，reducer 不再复制或派生 `issuer_station_id`，也不得接受 `subject_station_id`。需要独立携带、不同 signer、quorum/threshold 或独立密码学 transcript 的证明必须使用另行注册的 typed payload，不得把通用 `proofs[]` 加回 grant body。服务端不得代签或补造 Event proof。

### 3.1 条件化 Grant

Grant 的 `subject` 可以是具体 ActorId，也可以是条件选择器。

条件化 grant MUST 明确 claim issuer、claim type、有效状态和适用资源范围。节点 MUST NOT 仅凭 handle 字符串后缀、邮箱域名或显示名判断条件成立。

### 3.2 首发 grant 的 issuer 自身权限上界（normative）

以 `kind="grant"` ref 签出的 grant 由 §10.1 强制逐 action 的 `child.actions[] ⊆ union(refs.actions)`、resources 收窄等上界约束，防止再授权扩权。**以 `kind="realm_root"` ref 签出的 grant 受对称的 issuer 自身权限上界约束**：仅持有 `ak.capability.grant` action 本身**不足以**签发任意 grant。两条路径是同一种 grant，只是 `issuer_authority_refs[]` 的 ref 类型不同。

签发以 `realm_root` ref 为根的 `ak.capability.grant` 时，reducer **MUST** 校验：grant 的 `actions[]` 与 `resources[]` 所表达的能力 **MUST ⊆** issuer 在签发时点（按该 grant 的 seal basis / `auth_state_digest`）**自身有效持有**的 effective capability。effective capability 的来源是一个**封闭列表**：active 上游 grant（含 `ak.realm.admin` / `ak.policy.manage` 等 admin capability 与 `ak.realm.owner` co-owner grant），或本节下文的 Realm authority-root cell current controller。**membership、`created_by`、Realm 角色标签与任何 `realm_state.owner` 一类投影镜像都不是授权来源**，MUST NOT 参与该判定。issuer 不得签发授予他人超出自身持有能力的 grant。

聚合 admin action（如 `ak.realm.admin` / `ak.policy.manage`）在该上界校验中的展开 **MUST** 使用 Realm 的冻结 reducer profile compiled rules：reducer 先解析 child grant 每个 `actions[]` 的 `target_event_kinds`，再从同一 profile 解释器解析 issuer 持有的聚合 action 覆盖集。issuer 字面持有 child action 时可直接满足上界；issuer 仅持有聚合 action 时，只有当该 profile 的 effective coverage set 覆盖 child action 的全部 `target_event_kinds`，且 issuer resources / constraints 覆盖 child resources / constraints 时，才视为满足上界。覆盖集为空（`target_event_kinds == []`）的 child action **MUST NOT** 由任何聚合满足——空集是任意集合的子集，若不显式拦下，每个非事件面 action 都会被每个聚合"覆盖"。同一稳定 reducer profile 的 coverage set 永久冻结；新增 durable Event/action coverage 必须进入 successor profile。聚合展开 **MUST NOT** 授权 `event_mapping_kind="non_event_surface"` 的 child action；这类 action 只有三个已注册的上界来源：issuer 字面持有相同 action、由 profile 显式声明的非事件面授权规则覆盖，或由下文 Realm owner authority 的 `grant_authority_actions` 逐字命中。

**Realm owner authority（normative）**：`ak.realm.owner` 是 Realm 内最高的显式授权聚合，有且仅有两个来源：

1. **root authority**——[`realm-and-space.md` §2.5](../models/realm-and-space.md#25-akrealmcreate-reducer-bootstrapnormative) 的 `ak.component.realm.authority_root.v1` cell 的 current controller。该分支的 operational authorization **MUST** 使用该 cell 在同一 Seal basis 下的 registered inclusion proof；**MUST NOT** 回退到 `realm_state.owner`、membership 或 `created_by`。
2. **co-owner grant**——一条 active 的普通 `ak.realm.owner` grant。它给予 owner 的 operational / grant authority，但**不**给予 root-control authority：持有人不控制 authority-root cell。

current-v1 **不定义** authority-policy override cell、role-assignment cell 或 deployment-local owner override。owner 的 direct Event coverage 与 grant issuer ceiling 分别是 reducer profile bundle 中冻结的 `ak.realm.owner.target_event_kinds` 与 `grant_authority_actions`；偏离默认只能通过本规范已经定义的显式 capability grant、revoke、constraint 与对应 policy control state 表达。实现不得从未知 cell、配置文件、`ServiceDescribe`、membership role 或 UI role 标签扩张/收窄这两个集合。这样 cell 缺席不是 fallback，而是 current-v1 的唯一协议状态。

**Authority-root successor counters（normative）**：`ak.realm.owner.transfer` 与 `ak.realm.authority.reset` 都以签名内的 `expected_state_digest` 对 authority-root cell 做 CAS，故 successor counter 没有 author 可选值。transfer 的 `payload.patch` 只允许 `controller_actor_id`；registered reducer contract 必须从该 digest 锁定的冻结前态计算 `controller_epoch = checked_add(prestate.controller_epoch, 1)`。reset 不携带 `patch`；contract 必须计算 `authority_generation = checked_add(prestate.authority_generation, 1)`。两项加法均受 [`encoding.md` §1](../conformance/encoding.md) JSON safe-integer 上限约束，溢出 MUST fail closed；不得 wrap、饱和或保留旧值。transfer 保留 authority generation，reset 保留 controller 与 controller epoch。`successor_acceptance` 覆盖完整 payload 及 `expected_state_digest`，因此也唯一绑定 computed successor epoch，无需在 wire 上复述它。并发或 stale 前态仍由同一 CAS 拒绝。

Profile 对 non-event action 的显式授权规则必须登记在
`conformance-profiles.json#/profile_requirements/<profile>/non_event_grant_authority_rules[]`；
散文声明或只把 action 列入 `required_capability_actions[]` 不构成权限来源。每条规则必须逐字
登记 `issuer_action`、`grantable_action`、`required_registration_event_kind`、
`required_claimed_profile`、`required_constraint_kind/subkind`、`subject_binding`、
`scope_binding`、`epoch_binding`、`requested_action_binding` 与
`issuer_owner_authority_allowed`。`issuer_owner_authority_allowed=true` 时 issuer 侧另接受
Realm effective owner（authority-root cell current controller 或 active co-owner grant）；
该扩展只替换 issuer 来源，profile 的 registration / constraint / evidence gate 一条不减。
Reducer 只有在同一
`seal_basis` joined view 下 issuer 的 active grant 覆盖 `issuer_action`（或按上一句取得
effective owner）和 child resource，
且被引用 registration、subject、constraint、epoch、scope、requested action 全部满足规则时，
才可把该规则视为 child action 的 issuer 上界；任一 registration 缺失、profile 未声明、
epoch/subject/scope/constraint 不一致、action 未被 registration 请求，或 rule/profile
unsupported 时都必须 `grant_exceeds_issuer_authority` fail closed。该机制不是 sovereign
豁免，不允许 owner/membership 隐式授权，也不允许 profile 声明 wildcard/prefix action。
机器正负向闭包由 `ak.vector.capability.applet_bridge_non_event_grant_authority.v1` 覆盖。

Capability grant wire body MUST NOT 携带 registry version、timestamp 或 digest。`capability-action-registry.json` 只作为 spec/codegen/conformance 输入；production reducer 根据 Realm reducer profile 的 compiled action descriptors 判定 aggregate coverage 与 grant authority。

- 越界（`actions[]` 含 issuer 自身不持有的 action，或 `resources[]` 超出 issuer 自身命中范围）时 reducer **MUST** fail closed：对 actions / resources 越界返回 `schema_violation`（`reason="grant_exceeds_issuer_authority"`），对授权前置不成立（issuer 在该 basis 下不持有所需上界能力）返回 `failed_precondition`（`reason="grant_exceeds_issuer_authority"`）。实现 **MUST NOT** 把"持有 `ak.capability.grant` action"误当作"可凭空铸造任意 capability"。
- 该校验在 issuer 的有效权限随撤销 / 过期收缩时同样适用：issuer 在签发 basis 下不再持有某 action，则不得据此签发包含该 action 的首发 grant。
- Realm `schema_refs` 中出现任何结构角色 profile 都不得扩张 owner ceiling。`ak.realm.owner.grant_authority_actions` 是 reducer profile bundle 的冻结精确清单：默认 derivation 只选择 `profile=null` action，profile action 只有在 owner 的 compiled `grant_authority_rule.include_actions[]` 中逐字列出时才可由 root/co-owner 签发；这不是 generic active-profile 机制，也不授予 owner 直接 author 该 Event。current-v1 唯一显式 application exception 是 `ak.rsvp.set`：grant 可在 Calendar Strand 创建前签发，但后续 Event 仍必须由 `Strand.schema_refs` 中的 `ak.schema.calendar_event.v1` 与 `metadata.fields.calendar` 双向 guard 激活并命中 grant resource/constraint，否则拒绝。其它带 `profile` 的 action 仍只能经本节登记的 `non_event_grant_authority_rules[]` 及其完整 registration / constraint / evidence gate，或未来 reducer profile 明确加入 exact action；receiver MUST NOT 从 Realm profile、ServiceDescribe 或对象任意 schema ref 自行推导 owner ceiling。
- 此规则关闭"窄 `ak.capability.grant` 持有者凭空签出更宽 grant"的权限提升面，与 §10.1 委派收窄对称；它**不**妨碍合法的 admin 角色分配——持有 `ak.realm.admin` 等 admin capability 的 issuer 本身即持有相应 action 上界，因此可正常把这些 action 授予他人。
- v1 授权图的唯一 genesis base case 是 [`realm-and-space.md` §2.5](../models/realm-and-space.md#25-akrealmcreate-reducer-bootstrapnormative) 的 `ak.component.realm.authority_root.v1` cell，它由 `ak.realm.create` 的注册 reducer contract 在 genesis `state_root` 内原子物化，**不是**一条 per-person grant，因此不存在"issuer 凭空给自己签发一条 grant"的路径。root controller 的上界仍完整适用本节：child action 必须逐字命中该 Realm reducer profile 中 `ak.realm.owner` 的 frozen `grant_authority_actions`。cell 缺失、controller 不匹配或 epoch/generation 不一致时 MUST fail closed（`failed_precondition`，`reason="realm_authority_root_missing"` 或 `"realm_authority_controller_mismatch"`）。
- 除该 registered authority root 外，v1 不定义“可凭空授予自身不持有能力”的 sovereign 豁免，也不承认任何形态的 creator / owner omnipotence 捷径。部署 policy 不得自行放宽本节上界；需要不同 bootstrap authority 的 extension 必须注册独立 profile、完整定义机器可验证的权限来源与收窄规则，未声明 / 不支持该 profile 时 fail closed。

**确定性 basis 与 freshness 解耦（normative）**：首发 grant 的 issuer 上界校验 MUST 有确定性求值 basis，不得退化为对 §18.2 freshness 的循环依赖（"上界够新才算够新"）。具体：

- issuer 自身有效持有的 effective capability 必须从签名 seal_basis 中各 Realm 的确认状态验证，并将可撤销的实际安全读取加入事务 revision/锁集合；执行时重新检查，不能靠 Seal 年龄推断当前资格。
- 若 issuer 的上界 ancestor 能力在该 `seal_basis` joined view 下**被撤销 / superseded / expired / tombstoned**（即 joined view 下 ancestor 已不授权），首发 grant **MUST** `failed_precondition`（`reason="grant_exceeds_issuer_authority"`），不论 freshness 状态如何——这是 basis 内确定性结果，不是 freshness 问题。
- 若 issuer 的上界 ancestor 能力在该 joined view 下存活，但该 basis 的 **freshness 为 `unknown`**（[§18.2](#182-撤销传播与当前检查)）：`ak.capability.grant` 属高风险授权动作，**按 §18.2 风险表对高风险动作 `unknown` 即 fail closed** 处理，首发 grant **MUST** `failed_precondition`（`reason="grant_exceeds_issuer_authority"`，附 `freshness_state`），不得在 freshness 不可确认时仍签出依赖该 ancestor 的首发 grant。`stale` 状态按 §18.2 高风险行同样 fail closed。
- 配置、确认前缀或确切授权依赖不能验证时 fail closed/pending；同 Realm 竞争 Seal 不产生可选权限 heads。

该规则使首发 grant 的上界校验有"先按 seal_basis joined view 确定性解析 ancestor 授权，再按 §18.2 对 basis 新鲜度做高风险 fail-closed"的两步确定性算法，消除 §18.2 freshness 与上界校验之间的循环依赖。

### 3.3 注册的非 grant authority source（normative）

v1 普通授权仍以 capability grant 为默认。唯一注册的 profile-scoped 非 grant source 是
`ak.authority.direct_conversation_participant.v1`，canonical 行见
[`authority-source-registry.json`](../../artifacts/registry/authority-source-registry.json)。语法匹配、membership、
任意 Event/cell ref 或本地 projection row 都不能创建 source。该 source：

- 只在 `ak.profile.direct_conversation_realm.v1` 内，按唯一 immutable binding 与 exact participant/member/
  Realm/Strand/MLS/lifecycle/consent/Agent gate 求值；
- action 是 registry 闭合 allowlist，不能进入 `issuer_authority_refs[]`、不能授权
  `ak.capability.grant`，也不能被 owner/admin aggregate 放宽；
- 不依赖 `authority_generation`，所以 root reset/transfer 不撤销 participant baseline；结构终态则立即失效；
- 直接 participant Event 以 exact source token + critical binding Event ref 选择 evaluator；`executed_by` 路径
  仍以普通 grant/delegation 绑定 executor，并与 participant source 做 AND；
- 任一 evidence 缺失、冲突或 freshness unknown 都 fail closed/dependency pending，不得回退。

Direct Conversation root owner 还必须与 profile phase mask 求交：founding 仅可完成逐字段绑定 draft，active
phase 只保留注册 root-control，普通 operational/grant/member/policy/terminal coverage 被拒绝。完整规则见
[`contact-and-direct-conversation.md` §7–§8](../identity/contact-and-direct-conversation.md)。
机器正负向闭包由 `ak.vector.capability.direct_conversation_participant_authority.v1` 固定。

## 4. Resource Selector

Arkret v1 支持以下 18 项 `kind`（完整 kind 集以 [`resource-selector.schema.json`](../../artifacts/schemas/resource-selector.schema.json) 为准）：

- `realm`
- `space`
- `circle`
- `strand`
- `message`
- `morph`
- `object`
- `relation`
- `view`
- `event`
- `actor`
- `schema`
- `policy`
- `invite`
- `notification`
- `read_cursor`
- `blob`
- `*`（wildcard，见 [`resource-selector-grammar.md` §3.1](./resource-selector-grammar.md)）

资源选择器应把 Space（`kind=board/list/...`）、Strand track、Morph type 和 Relation kind 表达为 canonical resource selector + typed constraint，而不是把它们当成新的 selector kind。Strand 的业务语义通过 schema/profile、`metadata.fields`、Relation、labels、Morph type 或 facet 约束表达，不放在顶层字段上。

## 5. 动作集合

动作名称与标准 event kind / operation id 的语义对齐，使用 `ak.<domain>.<action>` 点分记法。Wire 层 `actions[]` 字段 MUST 是具体动作字符串；实现 **MUST NOT 接受任何 wildcard / segment 通配**（含 `*`、`ak.<domain>.*`、`ak.<domain>.<sub>.*`）。`capability-grant.schema.json` 已用 pattern 静态拒绝 wildcard。

机器可读的 canonical 动作集（含 `risk_tier`、`required_constraints`、`required_evaluator_checks`、`target_event_kinds`、`event_mapping_kind`、`profile`）MUST 来自 [`registry/capability-action-registry.json`](../../artifacts/registry/capability-action-registry.json)；本节的散文枚举只是该 registry 的 human-readable 镜像，新增 / 修改动作 MUST 先改 `contract-registry.json` 的 `capability_action_registry` 节并跑 `tools/artifact_pipeline.py generate`，再回流到本节。

**散文枚举 ↔ registry 一致性 gate（normative）**：本节 §5.1–§5.6 散文枚举的 action token 集合，及散文中标注的每个 action 的 `target_event_kinds` / `risk_tier` / `event_mapping_kind` / `profile`，**MUST** 与 `capability-action-registry.json` 对应字段**双向等价**——既不得有散文列出而 registry 缺失的 action（反之亦然），也不得有同一 action 在散文标注与 registry 声明之间的 `target_event_kinds` / `risk_tier` 不一致。该等价性 **MUST** 由 artifact lint gate(`tools/artifact_lint` 的 registry 一致性校验，纳入 CI 强制)双向自动校验：任一方向的成员漂移或属性漂移 **MUST** 触发 conformance 失败，MUST NOT 仅靠人工 review 保证。该 gate 既覆盖 §5 整体动作集，也覆盖 §5.0 四类偏离与 §5.0.1 聚合 admin 覆盖集的 RFC 约束（散文新增 target_event_kinds 成员必须同步 registry 且经 RFC）。

裸名动作（例如 `realm.upgrade` 或 `realm.link.manage`）MUST NOT 被接受。`ak.realm.admin` 覆盖普通 Realm 管理动作，但 MUST NOT 自动覆盖 E2EE key export、legal hold bypass 或审计降级——后者 MUST 在 grant `actions[]` 中显式列出对应 high-risk 动作。

### 5.0 Action ↔ Event kind 偏离类别（normative reference）

绝大多数 action 与其 `target_event_kinds` 单一同名映射（`ak.strand.create` action ↔ `ak.strand.create` event）。当存在偏离时，授权决策、IAM 工具与 audit 解析 MUST 以 `capability-action-registry.json` 的 `target_event_kinds` 为准，而不是用 action 字符串拆解推断 event kind。**偏离限定为以下四类**，任何其它类型的偏离 **MUST NOT 被引入**：

| 类别 | 形态 | 标准示例 |
| --- | --- | --- |
| **聚合 admin 动作** | 一个 action 覆盖多条 Realm policy facet event kinds | `ak.realm.admin` → registry 中声明的 Realm policy facet events；`ak.policy.manage` → `ak.policy.*` 与 `ak.realm.policy_*` 系列 |
| **polymorphic 对象动作** | 一个 action 同时覆盖 Strand / Morph / Space 等同语义 event | `ak.object.archive` → `{ak.strand.archive, ak.morph.archive}`；`ak.object.restore` → `{ak.strand.restore, ak.morph.restore, ak.space.restore}`；`ak.object.stage.set` → `{ak.strand.stage.set, ak.morph.stage.set}` |
| **scope 后缀变体** | action 按主体、目标子集或语义相邻的 event 子集细分授权；可映射到一个异名 event，也可映射到多个紧密相关 event | `ak.message.revise.own` → `ak.message.revise`；`ak.call.join` → `{ak.call.create, ak.call.state, ak.call.summary}`；`ak.circle.member.add` → `ak.circle.member.state` |
| **操作动词动作（`event_mapping_kind="operation_verb"`）** | action token 命名为操作 / 命令动词，与 target event kind 名形态不同；reducer admission 经 `target_event_kinds` 解析，逐字命中 `actions[]` 规则照常适用，且不带聚合 admin 语义 | `ak.message.redact` → `{ak.message.redact, ak.redaction}` |

`ak.mls.commit` action → `{ak.mls.commit, ak.mls.commit_failed}` 等“同一 action 同时覆盖正常 event 与诊断 / 派生 event”的情况落在**聚合 admin 动作**类别，并以 registry `target_event_kinds` 为准。

`ak.message.redact` → `{ak.message.redact, ak.redaction}` **不是聚合 admin**：registry 把它标为 `event_mapping_kind="operation_verb"`（risk_tier=medium），即上表第四类“操作动词动作”。授权决策、IAM 工具与 audit 解析 MUST 以 registry 的 `event_mapping_kind` 与 `target_event_kinds` 为准。

**聚合 admin 的覆盖语义仅作用于 event-kind 解析层，不改变授权层 `actions[]` 的逐字命中规则。** 例如 `ak.policy.manage` 在 §5.4 与具体的 `ak.policy.set` / `ak.policy.rule` / `ak.policy.action` 并列：持有 `ak.policy.manage` 的 grant 表示该 admin action 在 registry 中聚合覆盖 `ak.policy.*` 与 `ak.realm.policy_*` 系列对应的 **event kinds**（audit / reducer 据 `target_event_kinds` 解析），但它**不在授权层自动等价于持有 `ak.policy.set` / `ak.policy.rule` / `ak.policy.action` 这三个具体 action token**。授权判定仍 MUST 按 §5「`actions[]` MUST 逐字命中、MUST NOT wildcard / segment 通配」执行：要授予某具体 policy 子动作，grant 的 `actions[]` MUST 显式列出 `ak.policy.manage`（若 receiver 已声明并接受该 action 对相应 event kinds 的聚合覆盖）或对应的具体 action token，二者不可互相推断。

新增动作 MUST 默认与 event kind 同名；只有上述四类之一的明确理由可以偏离，且必须在 `contract-registry.json` 内显式声明 `target_event_kinds` 与 `event_mapping_kind`。**新增偏离类别 MUST 在 RFC 中讨论后才能加表项；MUST NOT 通过 lint 例外或注释方式悄悄引入新桥**。

#### 5.0.2 Action token 槽位语法（normative）

偏离类别（上表）与 **action 字符串本身的槽位语法**是两套正交规则：前者管 action↔event 映射，后者管 token 怎么拼。本节定义后者。

**A. 通用形态**：`ak.<entity>[.<sub_entity>].<verb>`，末段 MUST 是动词（`create` / `archive` / `set` / `advance` …）或已登记的 facet 名词槽（见 D）。

**B. `ak.self.*` 形态**：`ak.self.<entity>[.<sub_entity>].<surface_class>.<verb>`。`<surface_class>` 是**封闭词表**，按调用面而非按领域选择：

| surface_class | 含义 | 实例 |
| --- | --- | --- |
| `command` | 改变状态的 POST | `ak.self.agent.command.pause.v1`、`ak.self.blob.command.presign.v1` |
| `resource` | 只读 GET / HEAD | `ak.self.blob.resource.get.v1`、`ak.self.blob.resource.head.v1` |
| `read` | 查询 / 扫描 | `ak.self.events.read.scan.v1`、`ak.self.account.read.describe.v1` |
| `stream` | 长连接订阅 | `ak.self.events.stream.subscribe.v1`、`ak.self.account.stream.subscribe.v1` |
| `upload` | 分片上传会话 | `ak.self.blob.upload.create.v1` |

`<sub_entity>` 只能出现在 `<entity>` 与 `<surface_class>` 之间（`ak.self.agent.participation.resource.replace.v1`），MUST NOT 占据 `<surface_class>` 槽。末段 MUST 是动词：`ak.self.realm_state_snapshot.read.manifest_head.v1` 的末段是名词，属**已登记的历史例外**，新增 action MUST NOT 沿用该形态。

**C. 限定词位置**：作用域限定词 MUST 作为**后缀**出现（`.own` / `.others`，见 §5.0 的 action 后缀约定）。`ak.member.compensate.leave` / `ak.member.compensate.remove` 把限定词放在动词之前，属**已登记的历史例外**——`compensate` 在此是补偿事务的语义前缀而非作用域限定词；新增作用域限定 MUST 用后缀形态。

**D. 动宾分隔符**：同一动作的宾语 MUST 用点分层级表达（`ak.object.stage.set`），MUST NOT 用下划线把动宾粘成一段。`ak.object.read_content` / `read_history` / `read_metadata` 是**已登记的历史例外**（三者是 read 的三个封闭投影档位，不是 `read` 动作的三个宾语）；新增 action MUST NOT 沿用下划线动宾形态。

**E. 聚合权限动词层级**：`owner` > `admin` > `manage` 是**严格层级**，不是同义词：

| 动词 | 语义 | 实例 |
| --- | --- | --- |
| `owner` | 对象最高权，含转让与销毁等 admin 不可推导的能力 | `ak.realm.owner`（112 event kinds） |
| `admin` | 治理面全权，不含所有权转移 | `ak.realm.admin`（26）、`ak.strand.admin` |
| `manage` | 单一子域的聚合管理权 | `ak.policy.manage`（16）、`ak.circle.manage`（4）、`ak.circle.member.manage` |

持有上位词 **MUST NOT** 在授权层自动等价于持有下位词（§5 的逐字命中规则照常适用）；层级只表达覆盖面的包含关系与风险排序。`ak.realm.owner` 的末段是名词而非动词，属 §5.0.2-A 的**已登记专名例外**。

**F. 实体命名空间边界（normative）**：以下相邻命名空间是**有意区分**，MUST NOT 因名字相似而合并：

| 命名空间 | 指称 | 不是 |
| --- | --- | --- |
| `ak.self.keys.*` / `ak.peer.keys.*` | HTTP 密钥材料**调用面**（镜像 `/self/keys/…`、`/peer/keys/…` 路径段，故用复数） | 不是某个对象族 |
| `ak.key_backup.*` | Key Backup **对象族**（series、active series 等） | 不是调用面 |
| `ak.sidecar.*` | Sidecar **对象自身**的生命周期（id kind 为 `sidecar`，是顶层对象） | 不是 agent 的子资源 |
| `ak.agent.sidecar.*` | agent 对其 sidecar 的**操作面**（publish / write / exchange control） | 不改变 sidecar 是顶层对象这一事实 |

`ak.realm.discover` 是 `non_event_surface` 的**目录发现调用**（动词），与 event kind `ak.realm.discovery`
（名词，写入 `ak.component.realm.discovery.v1`）不是同一事物：前者是读取面，后者是可发现性声明的状态写入。
二者同时存在是有意的，MUST NOT 互相替代。

#### 5.0.1 聚合 admin 覆盖集防权限蠕变（normative）

聚合 admin 动作（`ak.realm.admin`、`ak.policy.manage` 等，见上表第一类）的 `target_event_kinds` 是一个随 registry 演进可能增长的集合。若允许它随 registry 静默膨胀，则一个早先签发、覆盖范围较窄的历史 grant 会因后续向某聚合 action 的 `target_event_kinds` 新增成员而**自动扩大**其实际授权面（权限蠕变 / authority creep）。为关闭该面，v1 固定：

- 向任一聚合 admin action 的 `target_event_kinds` **新增成员 MUST 经 RFC**（与 §5.0 末段的偏离类别变更同级流程），MUST NOT 通过 lint 例外、注释或非 RFC 的 registry 直接编辑引入。
- 既有 grant 对该新增成员的覆盖 **MUST NOT 对历史 grant 自动生效**。`target_event_kinds` 扩张后，一个在扩张前签发的 grant 持有该聚合 action 时，其对**新增** event kind 的授权 MUST 由部署**显式 opt-in**（部署 policy 声明接受该聚合 action 的新版本覆盖集）或对受影响 grant **重签**（issuer 在扩张后的 registry basis 下重新签发 grant）后才生效。
- 实现 MUST 能区分"grant 签发时点聚合 action 覆盖的 event kind 集"与"当前 registry 覆盖集"，并在历史 grant 未 opt-in / 未重签时，对**仅由扩张才纳入**的 event kind **fail closed**（按未授权处理），而不是按当前 registry 集自动放行。该 basis 与 §3.2 首发 grant issuer 上界校验、§18.1 `auth_state_digest` 绑定的 registry 版本协同：grant 的有效覆盖集锚定到其签发 basis，registry 扩张不回溯放宽历史授权。
- 收窄（从 `target_event_kinds` 移除成员）不受 opt-in 约束——移除只会收紧历史 grant 的覆盖，不构成权限放大。

### 5.1 通用动作

- `ak.realm.discover`
- `ak.realm.create`
- `ak.realm.profile`
- `ak.realm.archive`
- `ak.realm.freeze`
- `ak.realm.tombstone`
- `ak.realm.destroy`
- `ak.object.read`
- `ak.object.read_metadata`
- `ak.object.read_content`
- `ak.object.read_history`
- `ak.object.archive`
- `ak.object.restore`

### 5.2 Strand 与工作流动作

- `ak.strand.create`
- `ak.strand.read`
- `ak.strand.update`
- `ak.strand.archive`
- `ak.strand.restore`
- `ak.strand.move`
- `ak.strand.reorder`
- `ak.strand.tracks.update`（Strand tracks map 写入入口：启用 / 关闭 track、切换 primary、修改 track profile，target=`ak.strand.tracks.update`，`event_mapping_kind=same_name`。这是该 action 的权威定义；§5.3 仅交叉引用）
- `ak.relation.create`
- `ak.relation.update`
- `ak.relation.tombstone`
- `ak.space.create`
- `ak.space.update`
- `ak.space.parent`
- `ak.space.archive`
- `ak.space.restore`
- `ak.space.tombstone`
- `ak.container.move_item`
- `ak.container.rebalance`
- `ak.view.create`
- `ak.view.update`
- `ak.view.reconcile`
- `ak.morph.read`
- `ak.morph.create`(默认 required constraint:`allowed_morph_kinds`)
- `ak.morph.update`(默认 required constraint:`allowed_write_fields`)

Strand 权限只覆盖 Strand 自身字段、track entry 和 position / relation 管理。`ak.strand.update` 的 `allowed_write_fields` MUST 把 Strand Description（`content` / `encrypted_content`）与 Synthesis track 正文（`tracks.synthesis.content` / `tracks.synthesis.encrypted_content`）当作互不蕴含的独立路径：允许写其中一组 MUST NOT 自动允许另一组。`ak.strand.tracks.update` 只管理 track 的启用、primary、profile、template 与 track-local metadata，MUST NOT 用来写 Description 或 Synthesis 正文。Message 正文权限按 Strand 的 effective scope 判断：`Strand.scope_circle_id=null` 时使用 Realm-default capability；`scope_circle_id` 指向 Circle 时使用该 [Circle](../models/circle.md) scope 的 capability + Circle membership 两层 AND（详见 [`circle.md` §8](../models/circle.md)）。

Circle membership 是 `sequenced_state`。缺少必要授权/确认依赖时 pending；已确认非成员时 deny；验证到同高度两个冲突确认时停止该安全域并保留故障证据。不得把安全故障解释成一个可 join 的成员多头状态，普通消息也不因此要求全局最新 Seal。

Morph 权限粒度与 Strand 平行(`ak.morph.read` / `ak.morph.create` / `ak.morph.update` 对应 `ak.strand.read` / `ak.strand.create` / `ak.strand.update`),通过 `allowed_morph_kinds` constraint 进一步限定可创建或操作的 `morph_kind`。

### 5.3 Discussion 与消息动作

- `ak.event.read`
- `ak.message.create`
- `ak.message.mention.broadcast`（high risk；允许在 `ak.message.create` / `ak.message.revise` 中新增 audience mention，例如 `@all` / `@here`。必须同时持有普通消息写入授权，且 grant MUST 携带 rate-limit quota（`max_operations` + `period` + `constraint_scope`），Realm / Circle policy MUST 声明允许的 audience 与 `max_recipients`；`@here` 映射为 `audience="strand_engaged"` 且不使用 presence / online 状态；详见 [`../models/strand-and-message.md` §9.4.4](../models/strand-and-message.md)）
- `ak.message.revise`
- `ak.message.revise.own`
- `ak.message.redact`
- `ak.message.redact.own`
- `ak.reaction.add`
- `ak.reaction.remove`
- `ak.strand.tracks.update`（管理 track 启用 / primary / profile；权威定义见 §5.2，此处仅交叉引用，target=`ak.strand.tracks.update`，`event_mapping_kind=same_name`）
- `ak.strand.watch.set`（写入自己的 watch 订阅，target=`ak.strand.watch.set`；详见 [`../models/strand-and-message.md` §8](../models/strand-and-message.md)）
- `ak.strand.watch.set.others`（high risk；为他人写入 `level ∈ {mentions_only, participating, all}` 的 watch 订阅；MUST NOT 写入 `muted` 或 `level_public=true`，target=`ak.strand.watch.set`；详见 [`../models/strand-and-message.md` §8.4](../models/strand-and-message.md)）

### 5.4 管理动作

- `ak.circle.create`（创建 Circle；默认不进入普通成员 bundle；Realm 管理员交接若希望接手者能继续创建 Circle，必须显式把本 action 纳入交接 bundle 或产品管理员角色）
- `ak.circle.manage`（管理 Circle lifecycle / metadata；MUST 通过 `allowed_circle_ids` 或 `kind="circle"` selector 收窄；不得由 `ak.realm.admin`、Realm owner transfer 或无约束 Realm-wide grant 隐式推出）
- `ak.circle.member.add`（自助加入 / 接受邀请 / 自助离开，受 Circle join_rule 与父 Realm membership gate 约束）
- `ak.circle.member.manage`（邀请、移除或 ban 他人；MUST 通过 `allowed_circle_ids` 或 `kind="circle"` selector 收窄；Realm admin transfer 不自动赋予本 action，也不自动创建 Circle membership）
- `ak.circle.member.add.others`（high risk；代他人写入 Circle membership，MUST 与 `ak.audit.accessed` 配对）
- `ak.circle.audit`（high risk；审计读取 Circle 元数据 / activity rollup，MUST 与 `ak.audit.accessed` 配对）
- `ak.realm.admin`
- `ak.realm.owner`（high risk；Realm 内最高显式授权聚合。两个来源见 §3.2：authority-root cell 的 current controller，或一条 active 的普通 co-owner grant。它同时携带两个由 registry 规则派生的集合——`target_event_kinds` 只用于直接 Event admission，`grant_authority_actions` 只用于 §3.2 的 issuer 上界；两者 MUST NOT 互换使用。`root_control_only` / `subject_only` / `reducer_only` 的 action 不在任一集合内，因此 owner 既不能直接 author 也不能签发它们）
- `ak.applet.ghost.provision`（high risk、profile=`ak.profile.applet_bridge.v1`、`target_event_kinds=[]`、`event_mapping_kind=non_event_surface`；授权 installed Applet service 调用闭合的 Ghost Actor provisioning aggregate；grant MUST 以 `applet_id`、`executed_by`、`registration_epoch` 约束绑定 active registration，且不得解释为对 `ak.identity.accountability_grant` 或 `ak.profile.create` 的通用授权）
- `ak.audit.applet_binding`（high risk；新增、暂停或撤销 Audit Applet Binding；target=`{ak.audit.applet_binding.create, ak.audit.applet_binding.state}`）
- `ak.audit.session.authorize`（high risk；授权某个 Audit Applet release session；Circle-scoped session 必须由覆盖该 Circle 的 grant 授权）
- `ak.realm.link`（管理 Realm 间关系图，target=`ak.realm.link`）
- `ak.realm.alias`（high risk；占用、改名或 tombstone Realm 的人类可读 alias，target=`ak.realm.alias`；alias 是用户会键入和转发的地址，夺取或改指它是钓鱼 / 冒名原语，见 [`../discovery/object-addressing.md` §3.3](../discovery/object-addressing.md)）
- `ak.realm.upgrade`
- `ak.realm.plaintext_visible_services`（high risk；修改 E2EE 边界外可见明文的服务声明，target=`ak.realm.plaintext_visible_services`）
- `ak.realm.preview_policy`（high risk；修改加入前 / token-scoped preview 可披露字段、历史 stub 或明文 snippet 的策略，target=`ak.realm.preview_policy`）
- `ak.strand.admin`
- `ak.realm.notification.audit`（读取完整 watch 状态含 `muted`；MUST 与 `ak.audit.accessed` 同时持有，详见 [`../models/strand-and-message.md` §8.5](../models/strand-and-message.md)）
- `ak.schema.define`
- `ak.capability.grant`
- `ak.capability.derived`（risk_tier=medium；记录 reducer 按 Realm link inheritance policy 机械物化出的 grant 记录，target=`ak.capability.derived`。它标记 `reducer_only`：任何 principal 都不得 author 它，因此它与 `ak.capability.grant` 的区别不是“谁再授权谁”，而是“谁写的”——`grant` 承载主体的授权意图并按 §10 的 issuer authority 规则求值，`derived` 只承载 reducer 依 [`realm-links.md` §6](../models/realm-links.md) 物化的派生记录，不引入新的授权意图）
- `ak.capability.revoke`
- `ak.agent.key.authorize`（high risk；授权 agent key，target=`ak.agent.key.authorize`。key 替换不设独立 rotate action：runtime replacement 的 controller-signed authorize Event 必须用精确 `supersedes[]` 列出全部既有 active authorization；reducer 接受该单一 Event 时原子 observe-remove，见 [`../identity/key-management.md` §3.6.1](../identity/key-management.md)）
- `ak.agent.key.revoke`（high risk；撤销 agent key，target=`ak.agent.key.revoke`）
- `ak.self.agent.command.provision.v1`(aggregate admin action,`target_event_kinds=[ak.agent.provision]`,profile=`ak.profile.agent_provisioning.v1`；controller 先生成并发布不含 PCR binding 的 Agent DID inception，服务端 prepare 只验证并返回 exact `initial_resolution`/delegation/allocation，**不**生成 Agent DID/私钥或分配 PCR id。controller 把该承诺写入本地冻结的 PCR genesis，取 `retype(event_id)` 作为 `principal_control_realm_id`，再提交唯一 closed controller-signed `ak.agent.provision` Event。Station MUST NOT 代签、重建 proof transcript、自选 realm id 或用 service/dev proof 替代。provision accepted 后为 `awaiting_pcr_genesis`；genesis accepted 后为 `awaiting_did_binding`；controller 使用 inception 预承诺 key 发布 exact PCR service update，accepted 后才 complete 并暴露 pairing/list/get。Agent Profile 与首次 `ak.agent.key.authorize` 都是后续独立提交。Provisioning MUST NOT 物化任何 `ak.capability.grant`；完整时序见 [`../identity/key-management.md` §3.6.3](../identity/key-management.md))
- `ak.self.agent.command.renew_pairing.v1`(controller-only,high risk;重开一次性 pairing handle；bootstrap 状态或已持有 active authorized key 且 lifecycle 为 `active | paused` 的 agent 均可调用，`active` 无需先 pause；怀疑旧 key 失陷时 SHOULD 先 pause；`target_event_kinds=[]`,`event_mapping_kind=non_event_surface`，不产生 durable Event，也不创建、撤销或重发 Realm grant；语义见 [`../identity/key-management.md` §3.6.1](../identity/key-management.md))
- `ak.self.agent.command.pause.v1`(controller-only;target=`ak.self.agent.pause`)
- `ak.self.agent.command.resume.v1`(controller-only;target=`ak.self.agent.resume`)
- `ak.self.agent.command.deactivate.v1`(controller-only,terminal;target=`ak.self.agent.deactivate`；请求只提交一个 lifecycle Event，accepted parent lifecycle AND gate 使全部 child authority ineffective，cleanup 非成功前置；见 [`../identity/account-lifecycle.md` §9.1](../identity/account-lifecycle.md))
- `ak.agent.draft.propose`(agent-initiated draft;target=`ak.agent.draft.propose`,wire_scope=`actor_private_event`)
- `ak.agent.action_request`(agent-initiated action request;target=`ak.agent.action_request`)
- `ak.agent.action_approve`(controller-only;target=`ak.agent.action_approve`)
- `ak.agent.action_reject`(controller-only;target=`ak.agent.action_reject`)
- `ak.self.agent.sidecar.command.ensure.v1`（aggregate admin action，`target_event_kinds=[ak.sidecar.create,ak.sidecar.context.attach]`，profile=`ak.profile.agent_sidecar.v1`）。该 action MAY 作为 self-scoped default capability 授予 Realm active member；create 建立 Event-derived Sidecar 原生 scope，attach 只登记现有 source context，不创建 Circle、membership、Strand 或 Relation。
- `ak.agent.sidecar.write`（profile action；`target_event_kinds=[ak.message.create]`，resource 必须限定 controller 自己的原生 Sidecar scope，且 actor 位于当前 Realm-scoped `effective_agent_ids`）
- `ak.agent.sidecar.exchange.control`（controller-only profile action；target 为同名 Event，resource 必须限定自己的原生 Sidecar scope；Agent capability 即使包含普通 Sidecar write 也不得 author control）
- `ak.agent.sidecar.publish`（profile action；target event kinds 由最终发布目标决定，至少包括 `ak.message.create`，受 reply-as-agent / act-on-behalf attribution 规则约束）
- `ak.self.agent.participation.resource.replace.v1`（controller-only private Account Data replace；profile=`ak.profile.agent_participation_policy.v1`）。请求为 closed `{target_scope,selection,expected_version}`，selection 是 required 五位 `{reply_message,reaction_add,reaction_remove,accept_third_party_mention,act_on_behalf}`。该操作只保存 controller 偏好并推进 CAS version，不创建或撤销 capability。实际动作把当前 selection 与 target-local deployment safety、Realm/Circle/Strand policy 逐位求交，再独立校验普通 capability、session scope、membership 与 lifecycle；任一 required 输入 unknown/stale/fork 均 fail closed（reason `agent_participation_ceiling_unresolved`：该 gate 把未决 policy 视为全 false，controller 的私有 selection 保持不变）。`reply_message`只治理`ak.message.create`；reactions 分别治理其 action；mention 只治理 fanout；act-on-behalf 必须保留 controller/Agent attribution 与 approval/accountability。
- `ak.policy.manage`
- `ak.policy.set`
- `ak.policy.rule`（管理 policy 规则集合，target=`ak.policy.rule`）
- `ak.policy.action`（管理 policy 动作集合，target=`ak.policy.action`）
- `ak.invite.create`
- `ak.invite.cancel`
- `ak.invite.third_party`（签发 3PID 邀请，target=`ak.invite.third_party`）
- `ak.invite.claim`
- `ak.invite.revoke`
- `ak.member.leave.own`（risk_tier=medium；profile=`ak.profile.direct_conversation_realm.v1`；scope_suffix_variant，target=`ak.member.state`；只允许 `actor_id == payload.member_id`（完整 ActorId）的 `join → leave`，不得 leave/ban 对方或执行 join）
- `ak.member.rejoin.own`（risk_tier=medium；profile=`ak.profile.direct_conversation_repair.v1`；scope_suffix_variant，target=`ak.member.state`；Direct Conversation exact-pair self-rejoin 专用，只允许 `actor_id == payload.member_id`（完整 ActorId）的 `leave → join`，不得承载首次 join、第三 participant 或代对方 join，也不得取得 grant/policy/admin/Strand/binding 变更权）
- `ak.approval.vote`
- `ak.moderation.decision`（写入 sealed moderation state cell；详见 [`../governance/content-moderation.md`](../governance/content-moderation.md)）
- `ak.moderation.decision.lift`（解除已 sealed 的 moderation 决策）

### 5.5 服务动作

v1 不注册独立的 `ak.mls.epoch` event；每个 group 的当前 epoch 由 accepted `ak.mls.commit` payload 中的 `next_epoch` 和对应 `ak.component.mls.epoch.v1` cell reducer 结果直接表达，没有"推进 epoch"这个独立可授权动作。

Audit action 只授权受控审计 applet / release service 执行绑定、阶段性 session、成员通知、sealed historical release、审计视图读取或审计材料导出。审计 applet 不是 MLS group 成员，也不会因 capability 获得实时消息 fanout；E2EE 合规 release 必须走 active `ak.audit.applet_binding.create/state`、`ak.audit.session.*`、`ak.audit.release` 和 RYW receipt。普通 Realm/Circle 治理举报不使用这些 action，举报只路由给 scoped 管理员 / moderator。

### 5.6 人类界面与个人状态动作

- `ak.read_cursor.advance`（capability action; 对应 event kind 同名 `ak.read_cursor.advance`）
- `ak.notification.read`
- `ak.notification.ack`
- `ak.invite.accept`

## 6. Constraints

Arkret v1 支持的完整 shorthand inventory、typed family/subkind 与承载字段统一列在本节下方的映射表中，
不再维护第二份分组清单。**allow 与 deny 两侧都属于 v1 受支持约束**；deny / `denied_*` / `*_deny`
字段不是扩展私货，它们与对应 allow 字段同源，命中即按 §15 “任一 deny 命中即生效”裁决。
完整约束结构和求值规则以 [`constraint-schema.md`](./constraint-schema.md) 为准；机读权威源是
[`grant-constraint.schema.json`](../../artifacts/schemas/grant-constraint.schema.json)。普通再授权控制的
`authority_regrant_allowed` / `max_authority_depth` / `authority_scope` 组合规则见该文 §7.4，Applet grant
绑定见 §7.3。

### 6.1 Effective Validity Window

Grant 的有效期只由 `constraints[]` 中的 temporal constraint 承载。全局有效期必须写成一条不含 `applies_to_actions` 与 `recurrence`、`effect=allow` 的独立 temporal constraint；不得把它结构合并进带局部 action 或 recurrence 语义的 constraint。授权解析 MUST 从 constraint 集合计算单一 effective window：

```text
effective_not_before = max(temporal.not_before[]?)
effective_expires_at = min(temporal.expires_at[]?)
```

缺省的 lower bound 视为无下限；缺省的 upper bound 视为无上限，但 agent / service principal 的高风险 action 与 registry `required_constraints` 明列 `expires_at` 的 action 仍按 §8 风险分层 MUST 有有限 `effective_expires_at`。若归一化后 `effective_not_before >= effective_expires_at`，reducer MUST `failed_precondition`，`reason="grant_validity_window_empty"`。授权日志、缓存 key、issuer-authority 收窄和 grant 有效期判断都 MUST 使用 effective window。

| 扁平名称 | Typed `constraint_kind` | `constraint_subkind` | 对应字段 |
|----------|------------------------|----------|----------|
| `expires_at` | `temporal` | — | `expires_at` |
| `not_before` | `temporal` | — | `not_before` |
| `allowed_write_fields` | `field_access` | — | `allowed_write_fields` |
| `denied_write_fields` | `field_access` | — | `denied_write_fields` |
| `allowed_read_fields` | `field_access` | — | `allowed_read_fields`（读取面字段允许列表，见 [`constraint-schema.md` §4.3](./constraint-schema.md)） |
| `denied_read_fields` | `field_access` | — | `denied_read_fields`（读取面字段拒绝列表，[`constraint-schema.md` §16.2](./constraint-schema.md) 算法消费） |
| `sensitive_fields` | `field_access` | — | `sensitive_fields`（读取时需特殊处理的敏感字段集） |
| `sensitive_handling` | `field_access` | — | `sensitive_handling`（敏感字段处理方式：`redact` / `hash` / `omit`） |
| `allowed_object_kinds` | `kind_restriction` | — | `allowed_object_kinds` |
| `denied_object_kinds` | `kind_restriction` | — | `denied_object_kinds`（命中即拒绝该对象类型） |
| `allowed_space_kinds` | `kind_restriction` | — | `allowed_space_kinds`（限定 Space 的 kind，例如 board / list / swimlane）|
| `denied_space_kinds` | `kind_restriction` | — | `denied_space_kinds` |
| `allowed_morph_kinds` | `kind_restriction` | — | `allowed_morph_kinds` |
| `denied_morph_kinds` | `kind_restriction` | — | `denied_morph_kinds` |
| `allowed_facets` | `kind_restriction` | — | `allowed_facets` |
| `denied_facets` | `kind_restriction` | — | `denied_facets` |
| `allowed_strand_ids` | `scope_limitation` | — | `allowed_strand_ids` |
| `denied_strand_ids` | `scope_limitation` | — | `denied_strand_ids` |
| `allowed_space_ids` | `scope_limitation` | — | `allowed_space_ids` |
| `denied_space_ids` | `scope_limitation` | — | `denied_space_ids` |
| `allowed_view_ids` | `scope_limitation` | — | `allowed_view_ids` |
| `allowed_view_kinds` | `scope_limitation` | — | `allowed_view_kinds` |
| `denied_view_kinds` | `scope_limitation` | — | `denied_view_kinds` |
| `allowed_view_renderers` | `scope_limitation` | — | `allowed_view_renderers` |
| `denied_view_renderers` | `scope_limitation` | — | `denied_view_renderers` |
| `allowed_circle_ids` | `scope_limitation` | — | `allowed_circle_ids`（限定 Circle-scoped capability 动作到列出的 Circle id，配合 `resource-selector-grammar.md` §2.2 的 Circle selector；Realm-wide 无收窄的 Circle 管理 grant 不是正常授权形态） |
| `allowed_tracks` | `scope_limitation` | — | `allowed_tracks` |
| `denied_tracks` | `scope_limitation` | — | `denied_tracks` |
| `allowed_relation_kinds` | `scope_limitation`（kanban extension，profile-gated `ak.profile.kanban_mvp.v1`，fail closed） | — | `allowed_relation_kinds` |
| `allowed_from_container_refs` | `scope_limitation`（kanban extension，profile-gated `ak.profile.kanban_mvp.v1`，fail closed） | — | `allowed_from_container_refs` |
| `allowed_to_container_refs` | `scope_limitation`（kanban extension，profile-gated `ak.profile.kanban_mvp.v1`，fail closed） | — | `allowed_to_container_refs` |
| `wip_limit_override` | `scope_limitation`（kanban extension，profile-gated `ak.profile.kanban_mvp.v1`） | — | `wip_limit_override`（看板容器 WIP 上限覆盖） |
| `allowed_history_access_values` | `confidentiality` | `visibility` | `allowed_history_access_values` |
| `redacted_history_allowed` | `confidentiality` | `visibility` | `redacted_history_allowed`（仅 `true` 允许读取 redacted stub；`false` / 缺省拒绝） |
| `blob_max_bytes` | `quota` | `resource` | `blob_max_bytes` |
| `blob_presign_max_ttl_seconds` | `quota` | `resource` | `blob_presign_max_ttl_seconds` |
| `max_artifact_bytes` | `quota` | `resource` | `max_artifact_bytes` |
| `blob_presign_scope` | `scope_limitation` | — | `blob_presign_scope` |
| `allowed_data_labels` | `scope_limitation` | — | `allowed_data_labels` |
| `allowed_endpoints` | `scope_limitation` | — | `allowed_endpoints` |
| `encryption_required` | `confidentiality` | `encryption` | `encryption_required` |
| `message_edit_window` | `temporal` | `edit_window` | `message_edit_window` |
| `message_redact_window` | `temporal` | `redact_window` | `message_redact_window` |
| `redact_after_window_allowed` | `temporal` | `edit_window` / `redact_window` | `redact_after_window_allowed`（窗口修饰符，见 [`constraint-schema.md` §14.2](./constraint-schema.md)） |
| `max_authority_depth` | `authority_control` | — | `max_authority_depth` |
| `authority_path` | `authority_control` | — | `authority_path`（授权链 DID 路径约束，见 [`constraint-schema.md` §7](./constraint-schema.md)） |
| `authority_regrant_allowed` | `authority_control` | — | `authority_regrant_allowed` |
| `authority_scope` | `authority_control` | — | `authority_scope`（`narrowing_only` / `same_scope` / `custom`） |
| `rate_limit` | `quota` | `rate` | `max_operations`, `period`, `constraint_scope`, `burst` |
| `resource_limit` | `quota` | `resource` | `max_resources`, `resource_kind`, `constraint_scope`（scope 内累计资源数量上限） |
| `max_total_blob_bytes` | `quota` | `resource` | `max_total_blob_bytes`, `constraint_scope`（scope 内累计字节上限） |
| `approval_required` | `claim_based` | `approval` | `approval_required` |
| `approval_mode` | `claim_based` | `approval` | `approval_mode` |
| `approval_actor_ids` | `claim_based` | `approval` | `approval_actor_ids` |
| `approval_relation` | `claim_based` | `approval` | `approval_relation` |
| `accountability_required` | `claim_based` | `accountability` | `accountability_required` |
| `guardian_approval_required` | `claim_based` | `accountability` | `guardian_approval_required` |
| `controller_approval_required` | `claim_based` | `accountability` | `controller_approval_required` |
| `required_claims` | `claim_based` | `claim` | `required_claims` |
| `trusted_claim_issuers` | `claim_based` | `claim` | `trusted_claim_issuers` |
| `claim_refresh_required` | `claim_based` | `claim` | `claim_refresh_required` |
| `claim_max_age` | `claim_based` | `claim` | `claim_max_age` |
| `depends_on_moderation_state` | （缓存依赖标记，非 allow/deny 约束） | — | `depends_on_moderation_state`（fast-path cache 失效 hint，默认 `false`；MUST 显式 `true` 的三类触发条件见 §18.1。它不归入 8 个 constraint family，而是 grant cache 失效绑定字段） |

### 6.2 资源类型 / facet / claim 约束求值规则

`discussion` 不是独立资源类型。需要限制 discussion track 时，使用 `allowed_object_kinds=["strand"]` 和 `allowed_tracks=["discussion"]`；MUST NOT 引入按 track profile 名称授权的 v1 grant 字段。`tracks.<name>.profile` 只是 Strand track 的语义/profile hint，MUST NOT 单独授予读取、发送或成员权限。

Facet 只在 grant 显式包含 `allowed_facets` / `denied_facets` 这类 typed constraint 时作为范围收窄条件参与第 7 步 constraints 判断；未声明 facet constraint 的 grant 不会因为目标对象具有 `stateful`、`assignable` 或其他 facet 而自动允许或自动拒绝。`facet=stateful` 不引入独立授权动作：修改 Morph `state` 仍 MUST 命中 `ak.morph.update` 或具体 reducer 注册的更具体 action、目标 resource selector、`allowed_morph_kinds`、字段写约束和其他有效 constraints。JSON Schema 不承载通用 before→after transition policy。若 grant 允许 `ak.morph.update` 且没有字段/类型/策略拒绝，缺少 `allowed_facets=["stateful"]` 本身 MUST NOT 成为拒绝理由；若 grant 显式声明 `allowed_facets` 且目标 facets 不匹配，则 constraint 不满足。

`required_claims[]` 中每个 claim 条目 MUST 明确绑定 `issuer` 或 `trusted_issuers[]`；`subject_matches_actor` 未出现时按 `true` 求值。实现 MUST NOT 接受只有 `claim_kind` 而无发行者边界的 claim grant。

## 7. Claim / Attestation

Claim / Attestation 表示某个 issuer 对某个 subject 的可验证声明。

它用于表达组织成员、组织角色、监护关系、设备可信度、年龄/保护状态、认证等级等条件。

建议最小结构保持不变，权限判断仍必须基于 DID、claim issuer、有效期、撤销状态和最小披露范围。

## 8. Accountable Actor 授权

Capability 必须支持“有直接身份但需要责任主体/监护主体/控制主体”的 Actor。

这类 Actor 包括：

- AI agent
- 服务机器人
- 自动化账号
- 未成年人账号
- 受保护主体账号
- 企业托管账号
- 第三方集成账号

核心规则：

- accountability 不等于 capability。
- owner / guardian / controller 不会自动把自己的权限传给 subject。
- subject 要执行操作，仍然必须命中显式 grant。
- 高风险动作 MUST 按 action registry 的 `risk_tier` 要求 responsible / guardian / controller approval 或等价 proposal workflow。
- Event MUST 记录 grant、issuer-authority chain、approval 证据和执行上下文；缺失时 reducer MUST fail closed。

风险分层硬约束：

- `risk_tier=high` 的 action MUST 有 `expires_at`、resource selector narrowing、authorization evidence ref 与 audit evidence。
- 对需要更高保证的 high-risk action，profile MAY 要求显式 approval / proposal workflow、默认不可转授（无 `authority_control` 约束，等价 `max_authority_depth=0`）、更短 child grant TTL、不可扩大 scope 和 approver DID 记录；该要求 MUST NOT 通过 registry 未定义的第四级风险字符串表达。
- Agent / service principal 的 grant 无论 action 风险级别如何，默认 MUST 有 resource selector；缺失时 reducer MUST `failed_precondition`。
- Agent / service principal 的 grant 的 `expires_at` 分层要求:`risk_tier=high` 的 action 按上文风险分层硬约束 MUST 有有限 `expires_at`;registry `required_constraints` 列出 `expires_at` 的 action(如 `ak.agent.sidecar.publish`)同样 MUST,缺失时 reducer MUST `failed_precondition`。**低 / 中风险** action 的 agent grant MAY 不设时间过期(longevity-safe:失效控制由撤销链、pause / deactivate kill switch 与 controller lifecycle / membership 级联承担，见 [`../identity/key-management.md` §3.6.1](../identity/key-management.md));agent 的常驻工作面(read / draft / reply_as_agent / organizer)全部落在该层，因此配对完成后的持续在线不依赖任何 grant 定时器。

### 8.1 Proposal 模式

高风险操作建议使用 proposal 模式：

```txt
actor -> proposal.created
guardian/controller -> proposal.approved
system/human -> `ak.strand.update` 或 `ak.morph.update`
```

## 9. Agent 安全授权

给 agent 授权时 MUST 默认：

- 只授予明确 Realm / Strand / Message / Morph / View 范围。
- 只授予所需动作。
- 对 registry 要求 `expires_at` 的高风险 action 授予有限时效；其余 action 以撤销链与 lifecycle 级联为失效控制（§8）。
- 只授予该 agent 任务所需的最小可写字段、可写 track 和可写 Morph 类型集合。
- 对 high action 按 action registry 与 profile 要求 controller / responsible actor approval。

高风险模式包括：

- 给 agent 长期全 Realm 管理权。
- 让 agent 直接继承 human owner 全权限。
- registry 要求有限时效的高风险 action 不设过期时间。
- 不保留 agent 执行审计链。
- 高风险操作不需要 approval。

### 9.1 Agent 授权预设展开（normative）

产品 UI / SDK MAY 暴露 agent 授权预设(`read`、`draft`、`reply_as_agent`、`act_on_behalf`、`organizer`),以简化 `ak.profile.agent_provisioning.v1` 下的 agent 授权输入。本节是这些预设到 canonical grant 的**权威展开定义**。

预设名的语义约束(MUST):

- **预设名不进入 canonical wire。** 预设只是 UI / SDK 便捷输入;server 接收与持久化的永远是 `ak.capability.grant` 的 `actions[]`、resource selector、registered constraints 与 effective validity window(§6.1)。任何 grant 校验、审计、issuer-authority 收窄都基于展开后的 canonical 形态,MUST NOT 依赖预设名。
- **预设是 additive shorthand,不表达 deny / cap / only。** 同时选择多个预设时，结果是各预设 action / grant template 的**并集**;预设**不**移除、上限化或否定任何其他预设授予的权限。历史命名(如 `read_only` / `draft_only`)有 deny / cap 误导性,MUST NOT 作为 normative 预设名出现。若部署需要收窄，收窄只能通过 resource selector 与 constraint 表达，不能通过预设名。
- **实现 MUST NOT 引入未在下表登记的预设名**(例如 `write_summary` 等任意字符串)而不先在本表登记。
- **高风险预设 MUST 展开为完整 grant template**——包含 registry 要求的 required constraints 与有限 `expires_at`,而非无约束的 action union。

canonical 展开表:

| 预设 | Canonical actions | Required constraints | Resource scope | 语义 / 边界 |
| --- | --- | --- | --- | --- |
| `read` | `ak.event.read` | 显式 resource selector(MUST) | 显式 Realm / Strand / Circle scope,MUST NOT Realm-wide 无约束 | 授予**内容层**事件投影读能力。`ak.event.read` 是 `non_event_surface` 的内容读能力,**MUST NOT** 被解释为授予 events 服务面本身——agent 要真正调用 events 查询 / 订阅 endpoint,其 **session 还 MUST 携带对应服务面 scope**(`ak.self.events.read.scan.v1` / `ak.self.events.stream.subscribe.v1`,§5.5;见下方「服务面 scope 与内容能力分层」)。二者按 **AND** 组合:读取 surface 由服务面 scope 授权,payload 由 `ak.event.read` + membership / history visibility 授权(见 [`../models/relation.md` §4.2](../models/relation.md))。**MUST NOT** 隐含 object content/history 读取、`ak.object.read*`、`ak.strand.read`、E2EE history key 或 MLS membership。 |
| `read_content` / `read_history` | `ak.object.read_content` / `ak.object.read_history`(按需分别授予) | 显式 resource selector(MUST) | 同上 | 对象正文 / 历史读取是**独立的 additive 预设**,不折叠进 `read`。实现若需要"读事件+读正文",MUST 分别授予这些 action,而不是扩大 `read` 的展开集合。 |
| `draft` | `ak.agent.draft.propose`, `ak.agent.action_request` | —(revocation-governed;`expires_at` MAY 由部署 / controller 策略添加) | controller-private control surface | 允许 agent 提出候选草稿 / 动作请求，由 Station materialize controller-owned `ak.agent.draft.v1` account-data(见 [`../models/private-objects.md` §4.1](../models/private-objects.md))。两个 action 均 profile-gated 于 `ak.profile.agent_provisioning.v1`。**MUST NOT** 直接发布到 shared Realm / Strand(不得展开为 `ak.message.create` / `ak.strand.create` 或任何 `wire_scope=durable_event`)。 |
| `reply_as_agent` | `ak.message.create`, `ak.reaction.add` | 显式 resource selector(MUST) | 显式 Strand / Circle scope | agent 以自身 principal identity 在授权 scope 内发消息 / 加反应。 |
| `act_on_behalf` | `ak.message.create`(及选定 workflow actions) | controller approval / accountability 证据(MUST,见 §8)+ 有限 `expires_at`(MUST)+ resource selector narrowing + audit evidence ref | 显式 scope,MUST NOT 全 Realm 无约束 | **高风险。** `actor_id` 为 controller、`executed_by` 为 agent 的 accountable-actor 授权(§8)。MUST 携带 controller approval / accountability 约束,MUST NOT 仅做 action union。 |
| `organizer` | `ak.strand.create`, `ak.strand.update`, `ak.relation.create`,受限 `ak.message.create` | `ak.strand.update` MUST 携带 `allowed_write_fields`(registry required);显式 resource selector(MUST) | 显式 Realm / Space scope | **中到高风险。** 结构化编排权限。包含 `ak.strand.update` 时 MUST 通过 `allowed_write_fields` 限定可写字段,MUST NOT 展开为无约束的 strand 全字段写。 |

**服务面 scope 与内容能力分层(normative)。** 本展开表定义的是**内容层 capability grant**(`ak.capability.grant.actions[]`)。要真正调用某服务面 endpoint,调用方 session **MUST** 另行携带对应**服务面 scope**——例如 events 面的 `ak.self.events.read.scan.v1` / `ak.self.events.stream.subscribe.v1`(§5.5 服务动作),由 session 签发时 provision(Agent 见 [`conformance-profiles.md` §18.1](../conformance/conformance-profiles.md))。服务面 scope 与内容能力是**正交两层，按 AND 组合**:持有 `ak.event.read` 内容能力 **MUST NOT** 被解释为授予该服务面(§5.0 `actions[]` 逐字命中、无 subsumption),持有服务面 scope 也不授予内容读；最终可见性再叠加 membership / history visibility(见 [`../models/relation.md` §4.2](../models/relation.md))。对于 Agent runtime,`agent_key_scope.actions[]` MAY 同时列出服务操作 id 与内容 action token；其中内容 action 是 Agent 的全局硬上界而不是 grant，provision / key authorize 不得因其出现而物化内容授权。后续 Realm-scoped grant必须是该 action 上界的子集。Participation selection 是独立的 controller 行为偏好，可以预先选择任意已登记 bit，但不能授予或补回 requested scope、key scope或Realm grant缺失的authority。session 签发时必须分别求交:服务面 scope = requested_scope ∩ agent_key_scope 服务上界 ∩ endpoint/resource policy;内容 payload 可见性 = agent_key_scope 内容 action 上界 ∩ 有效 Realm capability grant ∩ 服务面允许 ∩ membership/history/E2EE 允许。预设展开 **MUST NOT** 把服务面 scope 混入本内容能力表——服务面授权随 session 演进，与本表解耦，二者可各自独立演进。

**Agent 全局 ceiling 的子集判定（normative）。** `POST /_arkret/self/agents` 的 `requested_scope` 是必填且创建后 immutable；改变或扩大该值必须创建新的 Agent principal。其后接受的 `ak.agent.key.authorize.payload.agent_key_scope`、Realm-scoped grant 与 session request 都 MUST 是该 ceiling 的收窄子集，而非必须与其完全相等。Participation 不派生 grant，也不进入本子集关系；它在动作时作为额外 deny gate 独立求值。子集判定固定如下：

- `actions[]`：子项逐字包含于父 ceiling；不得依靠 action family、前缀或 subsumption 补回未列 action。
- `resources[]`：子项中的每个 selector 必须被至少一个父 selector 覆盖。`operation` / `service` 只覆盖同 kind 且对应 `operation` / `service_id` 相同或父字段省略的服务资源；这两种服务 selector 不得携带内容字段。内容 kind 固定为 `realm` / `space` / `circle` / `strand` / `message` / `morph` / `object` / `relation` / `view` / `event` / `actor` / `schema` / `policy` / `invite` / `notification` / `read_cursor` / `blob`，不得把 `operation` / `service` 或 `*` 当作内容 kind。父 `kind=realm` 覆盖匹配 Realm 内的全部上述 Realm-local content kinds；其它父 content kind 只覆盖同 kind。父省略 `realm_id` 表示跨 Realm ceiling wildcard，省略精确 ref 表示该 kind / Realm 内 wildcard；父声明的字段必须与子项逐字相同。grant 的 `space_id` / `circle_id` / `strand_id` / `message_id` / `morph_id` / `object_ref` / `relation_id` / `view_id` / `event_id` / `actor_id` / `schema_ref` / `policy_id` / `invite_id` / `blob_ref` 分别映射为 ceiling selector 的 `resource_ref`（`schema_ref` 使用同名 ceiling 字段）后再判定；`notification` / `read_cursor` 仅按 `realm_id` 收窄。没有内容 selector 时，只表示 provision ceiling 未额外限制后续 grant 的具体内容资源；它不授予内容 wildcard，实际资源仍必须来自独立 Realm grant。
- `constraints[]`：provision ceiling 中的每条 constraint 都是全局 mandatory constraint；key authorization、grant/session 的有效求值必须继续与其做 AND。任何下游 scope 不得删除或放宽这些 constraint，可以增加更严格的 constraint。若下游对象无法直接承载该 constraint，authz evaluator 仍必须从 immutable provision state 注入并强制执行；不可解析时 fail closed。

**Ceiling 权威绑定与私有披露（normative）。** Provisioning MUST 只把 `requested_scope_digest` 固定到 Agent DID accepted create-locked bootstrap history entry 1 中唯一 `ArkretPrincipalControlRealm.serviceEndpoint`；entry 0 不含 PCR binding 或该 digest。该 endpoint 的闭合四元组见 [`../identity/key-management.md` §4.1](../identity/key-management.md)，公开 DID Document 与可解析历史 MUST NOT 包含完整 `requested_scope`。digest 固定为 `sha256(canonical_json({"agent_id": <Agent DID>, "controller_principal_id": <controller principal core>, "kind": "ak.agent.requested_scope_commitment.v1", "requested_scope": <完整 AgentKeyScope>}))`。完整 scope 只通过 controller 签名的 [`agent-requested-scope-disclosure.schema.json`](../../artifacts/schemas/agent-requested-scope-disclosure.schema.json) 私有出示：disclosure MUST 绑定 verifier DID、audience、presentation request、不可预测 challenge 与不超过 300 秒的接收窗口；proof MUST 覆盖去掉 `proofs` 后的完整对象。Receiver MUST 在 authorizing Event / grant 的 accepted-at 时点解析 Agent DID history，验证 disclosure 的当前 controller proof、单次 challenge、audience/freshness，重算 digest 与公开 commitment 相等，再以披露 scope 执行本节子集判定。只读 service-local Agent record、当前时刻 DID document、调用方自报 scope 或未绑定 verifier/challenge 的缓存均不构成权威证据。首次 accepted binding 后任何 DID update 若删除或改变 `realm_id`、`controller_did`、`authorization_ref` 或 `requested_scope_digest`，该 Agent binding 对新 key/grant/session MUST fail closed；需要改变 ceiling 必须 provision 新 Agent DID。成功验证的披露 MAY 仅以加密 verifier-private evidence 缓存，并由 accepted-at digest/controller lifecycle 约束；不得把完整 scope 复制到 pairing code、通知、runtime private key、Realm plaintext、durable Event 或其它公开记录。

因此最终服务面授权为 `requested_scope ∩ agent_key_scope ∩ requested_session_scope ∩ endpoint/resource policy`；最终内容授权为 `requested_scope ∩ agent_key_scope ∩ Realm grant ∩ participation ∩ requested_session_scope ∩ membership/history/E2EE/policy`。任一层不能解析或越界都 MUST fail closed；provisioning、pairing、pairing expiry 与 renew-pairing 都不得借此创建或修改 Realm grant。

**Membership 派生读取与受托读取(normative)。** Realm 成员的常规事件读取由 membership + history visibility + E2EE epoch policy 判定(见 [`../governance/history-visibility.md`](../governance/history-visibility.md) 与 [`../sync/service-http-binding.md`](../sync/service-http-binding.md) 中 events 读取面的授权规则),实现 **MUST NOT** 把持有显式 `ak.event.read` grant 作为成员读取的前置条件；本表 `read` 预设的 grant 形态服务于**受托主体**(Agent 等非成员 principal)的显式窄化授权。在 E2EE Realm 中,`ak.event.read` grant 只界定读取 surface 可向该受托 session 返回的 event envelope 范围；内容可解密性由 MLS membership 决定——agent 的 E2EE access MUST 作为独立 MLS member 表达(Agent 见 [`conformance-profiles.md` §18.1](../conformance/conformance-profiles.md)),本 grant **MUST NOT** 被解释为 MLS admission 或任何 key share。低于 Realm 粒度的 resource selector 收窄由读取 surface 的投递过滤执行——实现 **MUST** 在读取 surface enforce 该过滤，且 **MUST NOT** 把该过滤宣称为密码学隔离(同 Realm 内不承诺对已入组成员的强读隔离，强读隔离必须切分 Realm,见 [`../models/realm-and-space.md` §1](../models/realm-and-space.md))。

> 上表 canonical actions 与 required constraints 以 [`../../artifacts/registry/capability-action-registry.json`](../../artifacts/registry/capability-action-registry.json) 为准。当 registry 声明某 action 的 `required_constraints` 或 `risk_tier` 变化时，本表 MUST 随之更新；二者冲突时以 registry 为权威。

## 10. Issuer authority

v1 只有**一种** grant 形态。每条 grant 用 `issuer_authority_refs[]` 记录它是凭什么被签出的：

| | root controller 直发 | 普通 principal 再授予 |
| --- | --- | --- |
| ref | `{kind:"realm_root", realm_id, cell_ref, controller_epoch_at_issuance, authority_generation}` | 一个或多个 `{kind:"grant", grant_id}` |
| issuer 证明 | 签发 Seal basis 下 root cell 的 `controller_actor_id == issuer_id`，且 `issuer_id == Event.actor_id` | 每条 ref 的具体 `subject == child.issuer_id`（完整 ActorId 相等） |
| 持续有效性 | root 存在、Realm 未终止且 `authority_generation` 与 ref 相同；controller transfer 不影响 | 该 ref grant 当前 active |
| 上界 | root owner ceiling ∩ Realm policy | union(ref grants) ∩ Realm policy |

wire 上不存在"这是不是一次转授"的语义位——ref 的类型就是全部差异。`realm_root` 是有根终点，`grant` 是一条边。

`issuer_authority_refs[]` MUST 非空、canonical 去重，且 reducer MUST 拒绝不贡献任何覆盖的冗余 ref。所有 ref 的能力并集 MUST 覆盖 child 的全部 (action, resource)；标记 `root_control_only` 的 action 永远不能成为 child（见 §3.2）。

没有普通 `authority_control` constraint 的 grant 不具备再授权能力，MUST NOT 被任何 child grant 引用为 ref。若某条 ref 的普通 `authority_control` constraint 声明 `authority_regrant_allowed=false`（字段缺省同样为 false），则以它为 ref 的 child grant MUST 在 wire 上显式携带普通 `authority_control` 与 `max_authority_depth=0`，且 child 的 `authority_regrant_allowed` 必须为 false（字段省略按 false 求值）；该 terminal child MUST NOT 再被任何 grant 引用为 ref。省略 carrier、声明正深度或重新开启 regrant 时 reducer MUST 以 `failed_precondition` reason=`authority_regrant_denied` 拒绝。`constraint_subkind=applet_authority` 不构成普通再授权控制。

**求值时机（normative）**：child grant 的有效性在**每次授权判定时**按当前 refs 状态重算，不做级联写。`kind="grant"` ref 必须保持 active，且其具体 `subject` 必须与 child 的 `issuer_id` 做完整 ActorId 相等比较；只比较 `signing_principal_id` 或裸 DID MUST 视为未提供 issuer authority，并以 `failed_precondition`、reason=`grant_exceeds_issuer_authority` fail closed。该比较只读取已物化 ActorId，不得按 DID 二次查询或把当前路由服务替换进身份；因此离线 replay、迁移和联邦重放不会把同一 DID 的另一 Station 实例串成授权链。`kind="grant"` ref 失活按 action 传播；`kind="realm_root"` ref 只检查 cell 存在、Realm 未终止且当前 `authority_generation` 与 ref 相同，**不比较** current controller / epoch。因此 `ak.realm.owner.transfer` 不影响任何既有 child，只有 `ak.realm.authority.reset` 才整代失效。

**接受后物化字段（normative）**：reducer MUST 物化下列两个字段；它们都不属于 producer 的 closed authoring body，因此不可由作者谎报：

- `authority_depth`：`realm_root` ref 深度为 0，grant 自身为 `max(refs.authority_depth) + 1`。root controller 直发为 1，成员再授予为 2。取签发时静态值，撤销不重算——撤销只改有效性、不改历史结构；实际链深可能小于记录值，对 `max_authority_depth` 判定是偏严方向。
- `authority_root_refs[]`：direct `realm_root` refs 并上 `union(grant_refs.authority_root_refs)`。它**不是单值**——多亲与 `ak.capability.derived` 的跨 Realm 继承都可能追溯到不同 root / generation。去重键为 `(realm_id, cell_ref, authority_generation)`，MUST 按 unsigned-byte lexicographic 排序；`controller_epoch_at_issuance` 属每条 grant 的 issuance audit，不进入 root identity 去重键。

二者 MUST 登记进 `ak.capability.grant` 的 `cell_writes[].derived_members[]`（见 [`registry/contract-registry.json`](../../artifacts/registry/contract-registry.json) 的 `cell_contracts`），派生名分别为 `capability_authority_depth` 与 `capability_authority_root_refs`；该 `derivation` 取值集合是封闭的，新增派生等同新增 normative reducer 规则。未登记的 reducer 顺带写入 MUST NOT 进入 `state_root`（[`realm-and-space.md`](../models/realm-and-space.md)）。refs 指向的 grant 尚未投影时 depth / roots 算不出，MUST 走 dependency pending 或 `temporarily_unavailable`，**MUST NOT** 猜一个深度。

审计因此退化为单字段过滤（"权限扩散了几跳、根在哪里"），不需要递归 join，也不会因为各实现自行递归重建而在联邦对端得到不一致的视图。

### 10.1 时效与约束收窄（normative）

收窄**逐 action 判定**：对 child 的每个 action，窗口与约束以**覆盖该 action 的 refs** 为准。全局取 min/max 会让只被晚窗口 ref 覆盖的 action 借到早窗口，反之亦然。

| 子 grant 字段 | 与覆盖该 action 的 refs 的关系 |
| --- | --- |
| `effective_not_before` | MUST ≥ 覆盖该 action 的 refs 中最早的 `effective_not_before` |
| `effective_expires_at` | MUST ≤ 覆盖该 action 的 refs 中最晚的 `effective_expires_at`；该 action 按 §8 分层必须有限期而所有覆盖它的 ref 都无 finite upper bound 时，见下方"固定 seal 防滚动续期" |
| `max_authority_depth` | 对已显式允许 regrant 的普通 `authority_control`，MUST ≤ `min(grant_refs.max_authority_depth) - 1`；该 constraint 内未声明 depth 视为**无限**。完全没有普通 `authority_control` 的 grant 不得作为 grant ref；`authority_regrant_allowed=false` 的 terminal-child 规则按 [`constraint-schema.md` §7.4](./constraint-schema.md) 优先。`realm_root` ref 无 grant-local depth。若需要 Realm 级默认上限，MUST 先在 [`realm.schema.json`](../../artifacts/schemas/realm.schema.json) 注册可选字段再引用，不得引用未注册的"root policy 上限"概念 |
| `actions[]` | MUST ⊆ union(refs 的 actions)（`realm_root` ref 贡献该 root 的 owner ceiling） |
| `resources[]` | MUST 是 union(refs 的 resources) 的 selector-narrowing 子集（见 [`resource-selector-grammar.md`](./resource-selector-grammar.md)） |
| `constraints[]` | MUST 至少包含覆盖该 action 的各 `grant` ref 的全部 deny / require / quarantine constraints 的并集（更严者胜）；MAY 增加更严格的 allow constraints。`realm_root` ref 没有 grant-local constraint，只提供同 generation 的 owner ceiling |

违反窗口项 reducer MUST 返回 `failed_precondition` reason=`authority_expiry_widening`；违反 actions / resources / constraints 越界返回 `schema_violation`。

签发时的这组校验是 hygiene；**实际授权以求值时的 refs 存活判定为准**（见上文"求值时机"），两者并存不矛盾。

**固定 seal 防滚动续期（normative）**：仅靠"child 自带 `expires_at` ≤ `now + max_authority_lifetime_ms`"不足以约束无限期 ref——ref 持有人可以每 `max_authority_lifetime_ms` 自我再签一次，每次让 child 取得新的 `now + 24h`，从而把无 finite upper bound 的 ref 漂白成事实无限期的链。为关闭该面，当某 action 按 §8 分层**必须有限期**、而覆盖它的 refs 均无 finite upper bound 时，该 child 链 MUST 绑定一个**固定 `authority_expiry_seal`**，整条链每一级该 action 的 `effective_expires_at` MUST ≤ 该 seal，再签 MUST NOT 刷新它：

- 覆盖该 action 的 refs 中存在 finite `effective_expires_at` 时，`authority_expiry_seal` 取其中最晚者（与表中收窄规则一致）。
- 全部无 finite upper bound 时，其第一次作为 issuer authority 使用时 reducer MUST 冻结 `authority_expiry_seal = first_sealed_at + max_authority_lifetime_ms`（默认 24 小时），并作为不可变 child-chain 属性记录（`refs[role="authority_expiry_seal"]` 或 profile 声明的等价字段）。
- 同一 ref 的后续再签 MUST 复用同一 `authority_expiry_seal`，MUST NOT 用新的 `now` 重算；child 的 `effective_expires_at` 超过该 seal 时 reducer MUST 返回 `failed_precondition` reason=`authority_expiry_widening`。

该规则**不引用 event kind**，也不引用"是否经过转手"：触发条件完全来自 §8 的分层与 refs 的窗口。

`max_authority_lifetime_ms` 是 Realm authz 参数，wire 承载位置为 [`realm.schema.json`](../../artifacts/schemas/realm.schema.json) 的同名可选字段与 [`realm-and-space.md` §2.3](../models/realm-and-space.md) 字段表。缺省值为 `86400000`（24 小时）。若 grant / policy / deployment profile 声明更短窗口，effective value MUST 取所有适用窗口的最小值；child grant 或下游 profile 不得放宽父 Realm 的 effective value。实现无法读取该参数时 MUST 使用缺省值，不得把无限期 ref 视作可无限滚动续期。

### 10.2 Cycle detection（normative）

Reducer MUST 把 `issuer_authority_refs[]` 中 `kind="grant"` 的条目视为有向图的边，节点是 `grant_id`：边为 `(ref.grant_id → child_grant_id)`。`kind="realm_root"` 是**有根终点**，不产生任何边，因此不参与环检测。一条 grant 可有多条出边，DFS 是多出度遍历。

1. 收到新的 `ak.capability.grant(child_grant_id, issuer_authority_refs)` 时，reducer 沿全部 `grant` ref 做 DFS，直到遇到只有 `realm_root` ref 的 grant（有根终点）或深度达到上限。
2. 若 DFS 过程中发现新 `child_grant_id` 出现在已访问 ancestor 集合中（即新 grant 会 close 一条循环 path），reducer MUST 拒绝本 Event，reason=`authority_cycle`，MUST NOT 接受任何子 grant 即便它们单看 valid。互相支撑的环 MUST 被拒绝，且求值 MUST NOT 递归不终止。
3. DFS 深度上限 default 4，即 [`scalability-constraints.md` §3](../conformance/scalability-constraints.md) 的 canonical 上限（profile MAY 声明更低上限，MUST NOT 放宽）；超过深度的 chain 视作病态，reducer MUST 退化为拒绝。此外 grant 的 `max_authority_depth` 字段本身 MUST ≤ 4：reducer 在 **accept grant 时** 即 MUST 校验该字段 ≤ DFS 深度上限，声明更大值的 grant MUST 以 `schema_violation` 拒绝（[`grant-constraint.schema.json`](../../artifacts/schemas/grant-constraint.schema.json) 已用 `maximum:4` 静态强制），而非仅在 DFS 遍历时截断——避免字段声明语义与实际兜底上限不一致而误导审计 / UI。
4. 当某条 ref grant 已被 revoke 但 freshness 未到达时，reducer 仍 MUST 把它视为 cycle detection 的 ancestor 节点（防止攻击者 revoke-then-re-issue 构造环）。
5. 同一 Event 携带的多 child grant（批量签发）MUST 整体 fail-or-pass；部分接受会产生不完整的图结构，reducer MUST NOT 部分接受。

grant SHOULD 同时记录签发时点的 `auth_state_digest` / `auth_frontier`（可放入 `refs[role="auth_frontier"]`、grant audit metadata 或 profile 声明的等价字段）。该记录不替代实时 revoke / freshness 校验，但用于审计 child grant 是基于哪个 policy / auth frontier 派生的；缺失时实现仍 MUST 重新按当前 frontier 验证，MUST NOT 把 child grant 当作不可追溯授权。

实现 SHOULD 维护 in-memory authority-graph adjacency cache，以使每次校验为 O(depth)；冷启动时从 sealed control Events 与可验证 DataEvent 授权引用重建。

### 10.3 Revoke 因果传播

已确认撤销对所有依赖该 grant 的委托链按 action 与 scope 传递。新 grant 和安全操作在唯一安全确认顺序处检查真实当前前态；祖先已关闭时返回 `grant_revoked_upstream`。

普通数据的 receiver 使用已验证的缓存授权，未知撤销允许传播窗口；本地已知撤销与 live admission 在同一持久事务串行化。历史 Event 由原授权实例和全部适用关闭 frontier 决定资格，接纳收据不保证永久有效。缺被引用依赖时 pending；仅因无法证明全球没有未知撤销，MUST NOT 强制原站在线或刷新 Seal。

### 10.4 Revoke 与 relinquish 的分工（normative）

撤销与主动放弃不共用一个 Event：

- `ak.capability.revoke`：actor MUST 先通过普通 action authorization，随后 target guard 只接受 `actor == target.issuer`，或 actor 是 **target grant 自身 `realm_id`** 的 current root controller。仅仅控制 `authority_root_refs[]` 中某个跨 Realm 上游 root **不**获得撤销权。后一分支保证 Realm 转让后新 root owner 能治理旧 controller 签出的 grant；普通 co-owner 与 sibling 不能借 `ak.realm.owner` 撤销上游或同级 grant。不满足时 reducer MUST 拒绝，reason=`grant_revoke_not_authorized`。
- `ak.capability.relinquish`：subject-only self-service Control Move，只接受 `actor == target.subject`。它只减少 actor 自身权限，因此 **MUST NOT** 要求 actor 另持 `ak.capability.revoke`——否则一个窄权限持有人可能无权放弃自己持有的东西。不满足时 reducer MUST 拒绝，reason=`grant_relinquish_not_subject`。被放弃 grant 的 descendants 同样按 refs 在读取时失效。
- authority-root cell **不是** grant，不能成为 revoke / relinquish 的 target；root controller 退出只能走 `ak.realm.owner.transfer`。
- target grant 尚未投影时，revoke / relinquish MUST 进入 dependency pending，**MUST NOT** 预写未经关系校验的 tombstone——target guard 需要 target 才能校验 issuer / root-controller / subject 关系。pending revoke MUST 在 target grant 投影的**同一原子投影步**内生效，不得存在"grant 先短暂可用于授权判定"的窗口；验证通过后 §12.1 的终态规则照旧（已 revoked 的 `grant_id` re-add 不复活）。

拒绝 MUST NOT 把 target 是否存在、或属于哪个 Realm，泄漏给无权 actor。

## 11. 有效权限集合

Arkret v1 采用 allow-grant + explicit revoke 模型。

也就是说：

- 协议层没有通用 `deny` grant。
- 有效权限集合是所有当前有效 grant 的并集。
- revoke 通过显式 Event 把 grant 从有效集合移出。

## 12. Revocation

撤销必须是显式操作，而不是删除 grant 记录。

示例：

```json
{
  "kind": "ak.capability.revoke",
  "payload": {
    "grant_id": "ak:grant:AU1_A5a8MMz_OdxEleQlWPFn-ljdJteaJv3ZZ9APkcrZ",
    "reason": "contract ended"
  }
}
```

v1 canonical `ak.capability.revoke` payload MUST 携带顶层 `grant_id`；registry cell_subject 从 `payload.grant_id` 派生。

**撤销的生效切点（normative）**：capability revoke 在唯一安全序列的 committed outcome 生效，并派生精确授权关闭集合。payload 不自报 frontier；Seal 依据完整命令及可获得历史生成关闭证明。普通消息允许未知撤销的传播窗口，获知后立即 gate，历史按所有适用 cut 重算；安全命令在实际执行位置检查授权和 revision。Consent 同样采用 sequenced_state，保留 observed-remove 集合值的完整 dots。

### 12.1 Grant cell 的确定性收敛（normative）

capability 授权状态投影到 cell family `ak.component.capability.grant.v1`（见 [`registry/event-kind-registry.json`](../../artifacts/registry/event-kind-registry.json) 的 `ak.capability.grant` / `ak.capability.revoke`）。grant create 的 `cell_subject` 从 `envelope.event_id` 重类型派生；revoke / relinquish 从 `payload.grant_id` 引用同一 cell（每个 `grant_id` 一个 cell），`lattice = or_set`。v1 只有这一个 capability cell family：再授予不是另一种 Event，而是同一个 `ak.capability.grant` 携带 `kind="grant"` 的 `issuer_authority_refs[]`（见 §10），因此不存在第二个被写入却无人读取的 family。收敛规则：

- **grant** = 对该 grant cell 的 or_set **add**：add dot = 该 `ak.capability.grant` 事件的 `ak:event:<event_id>:<write_index>`（dot 的规范定义见 [`../models/event-and-patch.md`](../models/event-and-patch.md) §2.4.2），value = grant 的 canonical 快照。
- **revoke** = 对**同一** grant cell 的 or_set **remove**，observe 该 grant 的 add dot（与 [`../identity/consent-model.md`](../identity/consent-model.md) 的 consent revoke `observed_dot_ids` 语义一致）。`ak.capability.revoke` 以顶层 `grant_id` 定位目标 cell；reducer **MUST** 在该 revoke Control Move 的 `seal_basis` view 下把目标 grant 的 add dot 解析为合法 add op 后再 supersede。已被 observe-remove 的 add **MUST NOT** 因同 `grant_id` 的后续 re-add / 重放而复活（remove-after-observed-add 为终态）；多 issuer 并发 revoke 同一 grant 收敛于 or_set 的去重语义。
- **有效性** = 唯一确认序列中尚未被 observed-remove 的 grant add。Cell 模型是 sequenced_state，值为完整活跃 tagged set；revoke 按确切 revision 执行移除。集合元素并存不代表安全分叉，不能通过无序权限 join 或 Bottom 替代确认。
- **GC / tombstone**：已被 sealed 的 grant / revoke 历史保留审计事实（§10.3 第 4 点）；GC 后 cell **MUST** 保留足以判定"该 `grant_id` 当前是否仍授权"的 tombstone，snapshot / export **MUST NOT** 把已 revoke 的 grant 再计为"当前仍授权"。

conformance：[`capability-fixture.json`](../../artifacts/fixtures/capability-fixture.json) **MUST** 覆盖 (a) grant → use → revoke → deny 序列、(b) 同一 grant 重复 / 并发 revoke 的幂等去重收敛、(c) revoke 后以同 `grant_id` re-add 仍保持已撤销（终态不复活）。freshness `unknown` 下高风险 action fail-closed 由 §18.2 风险表规范并据其验证。

## 13. Invite、通知与已读状态

invite / notification / read-cursor 等用户可见操作 MUST 由对应 capability action 授权（见下列）；实现 MUST NOT 通过权限模型之外的私有通道授予这些操作。

- 创建 / 取消普通定向 invite 需要 `ak.invite.create` / `ak.invite.cancel`；第三方/token invite 撤销需要 `ak.invite.revoke`
- 接受发给自己的 invite 需要 `ak.invite.accept`
- 写入自己的 `read_cursor` 需要 `ak.read_cursor.advance`（事件 kind 同名）
- 读取 notification 需要 `ak.notification.read`
- `ak.notification.ack` 只应影响自己的派生 inbox 状态

## 14. Role 只是 bundle

产品层可以提供：

- `realm_admin`
- `board_manager`
- `contributor`
- `observer`
- `discussion_moderator`
- `agent_writer`

但这些 role 在协议层只是 capability bundle，不是主语义。

## 15. 读权限与可发现性

读权限不只是“能不能 fetch 内容”，还包括：

- 能否发现对象存在。
- 能否看到 discussion 历史。
- 能否看到被撤回消息的元信息。
- 能否读取附件内容。

初版至少区分以下四类读权限，每类在 capability-action-registry 中都有对应 action：

- `discover` → `ak.realm.discover`（能否发现对象存在）
- `read_metadata` → `ak.object.read_metadata`（能否看到被撤回消息的元信息）
- `read_content` → `ak.object.read_content`（能否读取附件内容）
- `read_history` → `ak.object.read_history`（能否读取对象 discussion / 历史事件）

## 16. Strand / Discussion 场景下的权限建议

Arkret v1 至少区分：

- 修改 Strand synthesis。
- 开启或关闭 discussion track。
- 管理 Realm 成员（`ak.realm.admin` 管理 `ak.member.state` 写入）或 Circle 成员（`ak.circle.member.manage` / `ak.circle.member.add.others` 管理 `ak.circle.member.state` 写入，见 [`../models/circle.md`](../models/circle.md)）。
- 普通发送消息。
- 编辑自己的消息。
- 编辑任意消息。
- 撤回自己的消息。
- 撤回任意消息。
- 切换 primary track。

这能避免把"能改 Strand"和"能进入 discussion"混成一种权限——Realm-default discussion 按源 Realm capability 判断；若整个 Strand 落在 Circle，则还必须满足该 Circle 的 membership / effective scope 校验。

profile-gated 动作沿用同一原则：出现在 schedule、roster 或成员快照中的身份**不是**授权真源。例如 `ak.profile.calendar_event.v1` 的 `ak.rsvp.set`，其准入完全由覆盖该精确 Strand / effective scope 的 grant 决定——attendee 身份 MUST NOT 自动授予该动作，持有精确 capability 的非 attendee 也 MUST NOT 被 reducer 用隐式身份判断拒绝。产品若要求"只有 attendees 能回应"，MUST 通过 grant materialization 或 profile policy 实现。完整 admission predicate（目标 Realm / lifecycle / calendar status / basis 两级校验与反枚举要求）见 [`../models/calendar-event.md` §8.4](../models/calendar-event.md)。

## 17. 决策执行位置

权限检查 MUST 至少在以下协议边界执行：

- Events API 接收写入时
- Station sync surface 分发前
- 受托 search / projection 服务返回结果前
- blob store 下发内容前

声明主客户端、web 客户端或离线编辑 profile 的实现 SHOULD 在本地提交前执行同等语义的预检查，以降低失败回滚和本地 pending 噪声；该预检查是 UX / 性能优化，不能替代上述服务端或 reducer 边界的 MUST 检查，也不能作为接受、分发或下发内容的唯一依据。

## 18. 最小权限判定算法与性能优化

给定一个操作，节点理论上的判定全链路如下：

1. 解析 actor DID。
2. 验证签名链。
3. 查找当时有效 grant 集。
4. 展开 `issuer_authority_refs[]`，并执行 cycle detection。
5. 判断 resource selector 是否覆盖 target。
6. 判断 action 是否匹配。
7. 判断 constraints 是否满足。**当多个 grant 同时命中该 `(action, resource)` 时，constraint 求值 MUST 走 [`constraint-schema.md` §15.4](./constraint-schema.md) 的跨 grant 全局合并入口（`evaluate_constraints_across_grants`），任一命中 grant 的 deny / quarantine / require_review 全局生效，MUST NOT 逐 grant 独立求值后取"任一 ALLOWED 即放行"。**
8. 若 grant 或 constraint 要求 claim，拉取并验证 claim / attestation。
9. 判断 claim issuer 是否可信。
10. 判断 claim 是否有效、未过期、未撤销。
11. 若需要 approval，校验 responsible / guardian / controller approval 证据。
12. 应用 revoke 和 superseding 规则。

Facets 不属于独立授权输入。算法 MUST NOT 在上述步骤之外读取 Morph facets、View renderer 或 track profile 来授予、拒绝或升级权限。第 7 步若检查 Realm schema、Morph profile 或 reducer policy，只能读取其中明确声明的字段规则、状态机 或 policy 条件；MUST NOT 把 facets 本身当作状态机、动作或授权规则。

### 18.1 高频交互的 O(1) 快速路径

在“discussion 消息收发”或“Strand 状态拖拽”等高频交互场景下，声称支持主客户端或 Station profile 的实现 SHOULD 提供 capability 快照缓存或语义等价 fast path。

高频 fast path 典型事件：

- `ak.message.create`
- `ak.reaction.add`
- `ak.strand.update`
- `ak.strand.move`
- `ak.strand.reorder`

Fast path 只能缓存基础 capability 是否允许。Moderation 的 `deny`、`quarantine`、`require_review`、rate limit、legal hold 和 abuse policy 仍 MUST 在写入接收、分发和查询返回前执行。

Capability fast path cache MUST 绑定确定性授权状态，而不是只绑定 subject/action/resource 三元组。每个 cache entry 至少包含：

- `realm_id`、scope / track / object selector、subject DID、action 和 constraint profile。
- `auth_state_digest`：由当前 accepted capability grant/revoke、membership、policy、必要 claim status（包括 condition-selector grant 依赖的 `claim_status_root`）、device/session control seal 和相关 state event canonical digest 计算出的确定性 hash。
- `auth_frontier`：参与该 hash 的 state event head set 或 snapshot frontier。
- 命中的 grant event id、revoke tombstone / superseding event id（如有）、claim status evidence 和过期时间。

除非具体 deployment profile 另行声明可复算的 auth-state canonical encoding，`auth_state_digest` 在跨实现 wire 上是 issuer-local opaque commitment：它绑定 cache entry、snapshot authority binding 或审计记录与某个 `auth_frontier`，但第三方 verifier 的安全判定 MUST 来自按 `auth_frontier` 可取得的 accepted auth state 回放 / 查询结果。换言之，verifier MUST 检查 digest 与 frontier 的自洽性和新鲜度，MUST NOT 把无法逐字重算该 opaque digest 解释为授权通过。

规则：

- 任何影响该 scope 的 accepted grant、revoke、membership、policy、claim status、device/session revoke 或 Realm lifecycle 变化，MUST 立即把对应 cache entry 标记 stale。"立即"指节点接受 DataEvent 或确认控制面 Seal 并更新相关 cell 的同一事务边界内；分布式 fanout 的传播延迟由 §18.2 freshness 检查兜底，**MUST NOT** 作为延迟标记 stale 的理由。**Reducer-derived membership cascade** 也 MUST 触发 cache stale：典型场景是 Realm leave/ban 触发各 Circle membership 自动收敛（见 [`circle.md` §9.1](../models/circle.md)），以及 Circle tombstone 触发对象 scope 失效。这些 cascade 不一定发出独立 `ak.member.state` event，但产生的 cell 变化同样属于"membership 变化"，MUST 触发 cache invalidation。
- **Moderation state cell 与 cache 的关系**：sealed moderation decision（写入 `ak.component.moderation_state.v1`，见 [`../governance/content-moderation.md`](../governance/content-moderation.md)）**默认不**触发 capability cache invalidation——moderation 是 deny / quarantine 后置层，不是 capability 来源。但若 grant 的 constraint 显式声明 `depends_on_moderation_state=true`（典型场景：moderator role grant 依赖被 moderation cell 标记的 actor 不在其中），则该 cell 的变化 MUST 触发对应 grant cache 失效。grant constraint 默认 `depends_on_moderation_state=false`。
  - **静态 lint 规则（MUST，reducer / schema 强制）**：为防止 silently-stale grant，grant 在写入 / accept 时若满足下列任一条件，`constraints[]` 中 **MUST 显式包含** `depends_on_moderation_state=true`，缺失即 `schema_violation`：
    1. `subject` 是 condition selector 且引用任何 moderation state 字段（例如 `not_in_moderation_set`、`moderation_role_in`、`moderation_status_*`）；
    2. `actions[]` 包含 `ak.moderation.decision` / `ak.moderation.decision.lift` 中的任一项（moderator role grant 通常依赖 moderation cell 决定谁是 moderator）；
    3. `constraints[]` 中存在任何 typed constraint 引用 moderation state cell、moderation queue、moderation report 或 moderation tag。
  - 该 lint 在 `capability-grant.schema.json` 与 grant accept reducer 中静态执行；实现 MUST NOT 接受"默认值省略"的兼容写法。Grant 显式声明 `depends_on_moderation_state=false` 而满足上述条件之一时同样 reject——只允许显式 `true`，从而确保意图可审计。
  - 不在上述条件内的普通 grant（典型如 `ak.strand.update`、`ak.message.create`、组织成员 grant）默认 `depends_on_moderation_state=false`，fast path 不受 moderation cell 失效抖动影响，符合本节"moderation 是后置层"的设计。
  - **条件 2 的保守取舍（normative rationale）**：条件 2 按 `actions[]` 是否含 moderation 写入动作触发，即使 subject 是固定 DID 的 admin / moderator grant（其"谁是 moderator"并不真正依赖 moderation cell）也强制 `depends_on_moderation_state=true`，因而该 grant 的 fast-path cache 会被无关 moderation cell 变化抖动失效。这是**有意的 fail-safe 设计**：lint 是 schema / reducer 层的静态规则，无法廉价区分"固定 DID admin"与"依赖 moderation state 的 condition-selector moderator"，而漏失效（已被 moderation 降权的 moderator 仍走 fast-path allow）的安全代价远高于多失效一次 cache 的性能代价。真正精确依赖 moderation state 的 grant 由条件 1、条件 3 覆盖；条件 2 是对"moderation 动作持有者"的额外保守网，**不收窄**。
- Cache entry 的 `auth_state_digest` 与当前 accepted auth state hash 不一致时，MUST 回退到完整授权判定；MUST NOT 继续用旧 grant 允许新写入。
- 对 subject 为 condition selector 或约束引用外部 claim / attestation 状态的 grant，cache key / cache value MUST 额外绑定 `claim_status_root` 与 `claim_freshness_deadline`。Issuer revoke、claim status root rotation、attestation expiry 或 freshness deadline 过期 MUST 使 cache entry stale；实现 MUST NOT 只因 grant/revoke/membership 未变化就继续使用 fast-path allow。
- 已被 GC 的 grant 仍 MUST 保留足以验证 revoke 的 tombstone、revocation index、snapshot witness 或 state root 证据。实现 MUST NOT 因为 grant payload 已压缩或归档而让旧 cache 重新生效。
- `partial_auth_state`、soft-failed auth chain 或无法确认当前撤销状态的状态 MUST NOT 生成 allow cache；只能生成 deny / unknown / pending 诊断。
- fast path（capability 快照缓存）**MUST** 只适用于"该 grant 的全部 constraint 的 `evaluation_class` 均为 `stateless` 或 `grant_local`"的 grant；只要 grant 含任一 `external` 或 `realm_state` 类 constraint（见 [`constraint-schema.md` §2.3](./constraint-schema.md) evaluation_class 分类，典型如 `claim_based` / `quota.rate` / `confidentiality` / `field_access` 带 `condition` 等），该 grant 的判定 **MUST** 走完整授权判定，**MUST NOT** 仅凭 fast-path cache 命中放行。该绑定与 §18.1 fast-path cache 的 `auth_state_digest` 失效机制叠加生效，不互相替代。
- 多 Station 部署中，cache TTL 只是额外保险，MUST NOT 替代 revoke fanout、frontier 对账和 `auth_state_digest` 失效。

### 18.2 撤销传播与当前检查

普通消息、编辑和其它 `execution=data` 操作不以 Seal 年龄、签名缓存 TTL、heartbeat 或在线 revocation 查询为前置。接收站必须已完整验证 Event 引用的授权和依赖，但不要求取得全球最新状态。未知撤销的传播窗口在持续分区中没有固定上界；获知撤销立即阻止新 live 效果，历史按关闭证明重算。

`execution=security` 操作在其唯一确认顺序处重新检查真实权限和前态；quorum 不可用时 pending，不按 low/medium risk 降级为本地授权。显式有限期资格仍按 §6.1 和 [授权归约 §5](./event-auth-state-resolution.md) 验证，普通无期限聊天不因此引入定期授权续签。

风险等级只决定已登记的审批、期限与约束，不能覆盖 execution 分类或把同一数据写入在不同 Station 变成不同模型。

## 19. 设计决定

Arkret v1 固定：

- 权限采用 capability 模型。
- Strand、discussion、agent 执行都使用统一 grant 体系；Strand track 不携带独立 access，整个 Strand 通过 Realm-default scope 或 Circle scope 形成单一安全边界。
- `ak.message.revise.own` 与 `ak.message.redact` 分开。
- invite / notification / read cursor 进入统一 capability 体系。
- 协议级语义采用 allow-grant + explicit revoke。
- agent 使用窄权限、短时效、可审计授权。
- accountable Actor 是通用授权对象。
- owner / guardian / controller 不导致权限自动继承。
- grant 主体使用 DID 或 condition selector，不使用 handle 作为权限主键。

## 20. 规范性收敛

以下授权事项在 v1 中按本节和引用文档执行：

- Resource selector 语法由 `resource-selector-grammar.md` 和 `resource-selector.schema.json` 固定。
- Constraint schema 由 `constraint-schema.md` 固定。
- 多个 grant 命中时，允许动作取并集，但约束按最严格规则相交：deny / quarantine / require_review 跨**全部**命中 grant 全局生效（全局 deny 优先），任一命中 grant 的 deny 不得被另一无 deny 命中 grant 绕过；allow 仍按"每个满足的依赖 grant 内 allow 全满足"判定。确定性跨 grant 入口算法见 [`constraint-schema.md` §15.4](./constraint-schema.md)。
- Moderation policy MUST NOT 凭空授予 capability。
- Approval proof 与 proposal 状态机由本文件、`event-auth-state-resolution.md` 和 conformance vectors 固定。
- Claim / attestation envelope 使用 `../models/event-and-patch.md` §3 的 Proof、`../identity/identity-handles.md` 的 claim / VC 规则与 [`../identity/identity-handles.md` §16](../identity/identity-handles.md) 的 presentation 规则。

## 附录 B. 可携带授权与撤销（informative）

Arkret 使用已确认的 grant Event 及精确委托证据作为可携带授权。grant/revoke 的变更有唯一安全顺序，使用既有 grant 的普通数据可离线并发。传播中的撤销通过作用域、授权实例和关闭集合收敛；短 TTL 不能消除网络分区的取舍。
