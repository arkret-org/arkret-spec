---
title: Capability Model
status: candidate
normative: true
stability: v1
updated: 2026-07-02
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Cokret 的权限模型采用 capability 思路，而不是只依赖成员关系或模糊角色。

这样做的原因是：

- `strand`、`message`、`realm`、`morph`、`view` 的动作集不同。
- Strand 的所有 track（含 `synthesis` 与 `discussion`）共享同一 effective scope（由 `Strand.scope_circle_id` 决定，`null` = Realm-default scope，否则指向同 Realm 的 [Circle](../models/circle.md)）。Strand 永远单一 scope，不存在 per-track 安全边界。
- agent 必须被精细授权。
- 授权变化必须可审计。

## 2. 基本原则

### 2.1 授权主体 SHOULD 是稳定 principal

grant 的 `issuer` 与 `subject` SHOULD 使用 DID。

Handle、邮箱、域名用户名等人类可读标识 MUST NOT 作为权限主体主键。

### 2.2 权限必须显式表达

实现 MUST NOT 依赖以下隐式假设：

- 进入 Realm 就拥有全部能力。
- 能编辑 Strand synthesis 就一定能在 discussion 里发消息，除非有效 access policy 明确继承并授予该动作。
- discussion moderator 天然拥有全量 Strand 管理权。

### 2.3 权限判定基于当时有效的 capability 集

操作是否合法 MUST 由该时点有效 grant 集决定。

### 2.4 DID 是主体，Claim 是条件

权限模型分三层：

```txt
Identity: DID
Human-readable binding: Handle
Authorization condition: Claim / Attestation
```

## 3. Grant 对象

ID 语义：

- `ck:grant:<uuid>` 是签名 Capability Grant object 的规范 ID，`ck.schema.capability.v1` 的 `id`、grant reference 和 revoke payload 均使用它。
- `ck:capability:<uuid>` 只表示抽象 capability definition 引用；MUST NOT 作为签名 grant object ID 使用。

示例：

```json schema=schemas/capability-grant.schema.json
{
  "id": "ck:grant:0196410c-0000-7000-8000-000000000000",
  "schema": "ck.schema.capability.v1",
  "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
  "issuer": "did:webvh:z6qRDFWgaBgTY3UGDLivJztno:acme.example.com",
  "subject": "did:webvh:z8NNMm8UHw7JcDSuuZd34UisF:agent.copy.example.com",
  "actions": [
    "ck.strand.read",
    "ck.strand.update",
    "ck.message.create",
    "ck.morph.read",
    "ck.morph.update"
  ],
  "resources": [
    {
      "kind": "object",
      "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
      "object_type": "strand",
      "match_scope": "realm_wide"
    },
    {
      "kind": "morph",
      "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
      "morph_type": "document",
      "match_scope": "realm_wide"
    }
  ],
  "constraints": [
    {
      "constraint_type": "temporal",
      "effect": "allow",
      "expires_at": "2026-04-30T00:00:00Z"
    },
    {
      "constraint_type": "field_access",
      "effect": "allow",
      "allowed_write_fields": ["metadata.title", "metadata.summary", "content", "metadata.fields.review_status"]
    }
  ],
  "proofs": [
    {
      "kind": "detached_jws",
      "alg": "EdDSA",
      "verification_method": "did:webvh:z6qRDFWgaBgTY3UGDLivJztno:acme.example.com#device-1",
      "payload_digest": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
      "created_at": "2026-04-26T00:00:00Z",
      "jws": "eyJhbGciOiJFZERTQSJ9..signature"
    }
  ]
}
```

### 3.1 条件化 Grant

Grant 的 `subject` 可以是具体 DID，也可以是条件选择器。

条件化 grant MUST 明确 claim issuer、claim type、有效状态和适用资源范围。节点 MUST NOT 仅凭 handle 字符串后缀、邮箱域名或显示名判断条件成立。

### 3.2 首发 grant 的 issuer 自身权限上界（normative）

委派路径（`ck.capability.delegate` 派生 grant）由 §10.1 强制 `child.actions[] ⊆ parent.actions[]`、resources 收窄等上界约束，防止再授权扩权。**链首的首发 grant（`ck.capability.grant`，无 `parent_grant_id`）受对称的 issuer 自身权限上界约束**：仅持有 `ck.capability.grant` action 本身**不足以**签发任意 grant。

签发首发（非 delegate 派生）`ck.capability.grant` 时，reducer **MUST** 校验：grant 的 `actions[]` 与 `resources[]` 所表达的能力 **MUST ⊆** issuer 在签发时点（按该 grant 的 seal basis / `auth_state_digest`）**自身有效持有**的 effective capability——即 issuer 自身经由 Realm 角色、`ck.realm.admin` / `ck.policy.manage` 等 admin capability、membership 或上游 grant，确实持有覆盖所授 `actions[]`（且 resources 不超出自身命中范围）的有效授权。issuer 不得签发授予他人超出自身持有能力的 grant。

聚合 admin action（如 `ck.realm.admin` / `ck.policy.manage`）在该上界校验中的展开 **MUST** 以 issuer grant 的签名 / registry basis 为锚：reducer 先解析 child grant 每个 `actions[]` 的 `target_event_kinds`，再在同一 registry basis 下解析 issuer 持有的聚合 action 覆盖集。issuer 字面持有 child action 时可直接满足上界；issuer 仅持有聚合 action 时，只有当该聚合 action 在该 basis 的 effective coverage set 覆盖 child action 的全部 `target_event_kinds`，且 issuer resources / constraints 覆盖 child resources / constraints 时，才视为满足上界。历史聚合 grant **MUST NOT** 自动继承后来 registry 新增的 `target_event_kinds`；新增覆盖必须按 §5.0.1 重新签发或通过显式 opt-in 绑定新的 registry digest。聚合展开 **MUST NOT** 授权 `event_mapping_kind="non_event_surface"` 的 child action；这类 action 只能由 issuer 字面持有相同 action，或由 profile 显式声明的非事件面授权规则覆盖。

- 越界（`actions[]` 含 issuer 自身不持有的 action，或 `resources[]` 超出 issuer 自身命中范围）时 reducer **MUST** fail closed：对 actions / resources 越界返回 `schema_violation`（`reason="grant_exceeds_issuer_authority"`），对授权前置不成立（issuer 在该 basis 下不持有所需上界能力）返回 `failed_precondition`（`reason="grant_exceeds_issuer_authority"`）。实现 **MUST NOT** 把"持有 `ck.capability.grant` action"误当作"可凭空铸造任意 capability"。
- 该校验在 issuer 的有效权限随撤销 / 过期收缩时同样适用：issuer 在签发 basis 下不再持有某 action，则不得据此签发包含该 action 的首发 grant。
- 此规则关闭"窄 `ck.capability.grant` 持有者凭空签出更宽 grant"的权限提升面，与 §10.1 委派收窄对称；它**不**妨碍合法的 admin 角色分配——持有 `ck.realm.admin` 等 admin capability 的 issuer 本身即持有相应 action 上界，因此可正常把这些 action 授予他人。
- v1 不定义"可凭空授予自身不持有能力"的 sovereign 豁免。若某部署确需此类豁免边界（如 founding admin bootstrap），MUST 由 Realm policy 显式声明该豁免及其权限来源，且 MUST NOT 默认开启；未显式声明时 reducer 按上述上界校验 fail closed。

**确定性 basis 与 freshness 解耦（normative）**：首发 grant 的 issuer 上界校验 MUST 有确定性求值 basis，不得退化为对 §18.2 freshness 的循环依赖（"上界够新才算够新"）。具体：

- issuer 自身有效持有的 effective capability（上界 ancestor 能力）**MUST** 在该 `ck.capability.grant` Control Move 的 **`seal_basis` joined view**（[`event-auth-state-resolution.md` §6.3.1](./event-auth-state-resolution.md) 的 deterministic joined control view）下解析。该 joined view 是确定性的：给定 `seal_basis`，ancestor 能力的撤销 / 存活状态有唯一解，与 freshness 置信判定**正交**——basis 本身固定了"按此 view 看 ancestor 是否仍授权"，而 freshness 只回答"此 basis 是否够新以排除尚未观察到的 revoke"。
- 若 issuer 的上界 ancestor 能力在该 `seal_basis` joined view 下**被撤销 / superseded / expired / tombstoned**（即 joined view 下 ancestor 已不授权），首发 grant **MUST** `failed_precondition`（`reason="grant_exceeds_issuer_authority"`），不论 freshness 状态如何——这是 basis 内确定性结果，不是 freshness 问题。
- 若 issuer 的上界 ancestor 能力在该 joined view 下存活，但该 basis 的 **freshness 为 `unknown`**（[§18.2](#182-撤销新鲜度-revocation-freshness)）：`ck.capability.grant` 属高风险授权动作，**按 §18.2 风险表对高风险动作 `unknown` 即 fail closed** 处理，首发 grant **MUST** `failed_precondition`（`reason="grant_exceeds_issuer_authority"`，附 `freshness_state`），不得在 freshness 不可确认时仍签出依赖该 ancestor 的首发 grant。`stale` 状态按 §18.2 高风险行同样 fail closed。
- joined view 出现 `⊥`（multi-head / fork quarantine，见 [`event-auth-state-resolution.md` §6.3.1](./event-auth-state-resolution.md)）时该上界分支 MUST fail closed，MUST NOT 任取一个 head 作为上界来源。

该规则使首发 grant 的上界校验有"先按 seal_basis joined view 确定性解析 ancestor 授权，再按 §18.2 对 basis 新鲜度做高风险 fail-closed"的两步确定性算法，消除 §18.2 freshness 与上界校验之间的循环依赖。

## 4. Resource Selector

Cokret v1 支持以下 18 项 `kind`（完整 kind 集以 [`resource-selector.schema.json`](../../artifacts/schemas/resource-selector.schema.json) 与 [`policy-server.md` §7.0](./policy-server.md) 为准）：

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

动作名称与标准 event kind / operation id 的语义对齐，使用 `ck.<domain>.<action>` 点分记法。Wire 层 `actions[]` 字段 MUST 是具体动作字符串；实现 **MUST NOT 接受任何 wildcard / segment 通配**（含 `*`、`ck.<domain>.*`、`ck.<domain>.<sub>.*`）。`capability-grant.schema.json` 已用 pattern 静态拒绝 wildcard。

机器可读的 canonical 动作集（含 `risk_tier`、`required_constraints`、`required_evaluator_checks`、`target_event_kinds`、`event_mapping_kind`、`profile`）MUST 来自 [`registry/capability-action-registry.json`](../../artifacts/registry/capability-action-registry.json)；本节的散文枚举只是该 registry 的 human-readable 镜像，新增 / 修改动作 MUST 先改 `contract-catalog.json` 的 `capability_action_registry` 节并跑 `tools/artifact_pipeline.py generate`，再回流到本节。

**散文枚举 ↔ registry 一致性 gate（normative）**：本节 §5.1–§5.6 散文枚举的 action token 集合，及散文中标注的每个 action 的 `target_event_kinds` / `risk_tier` / `event_mapping_kind` / `profile`，**MUST** 与 `capability-action-registry.json` 对应字段**双向等价**——既不得有散文列出而 registry 缺失的 action（反之亦然），也不得有同一 action 在散文标注与 registry 声明之间的 `target_event_kinds` / `risk_tier` 不一致。该等价性 **MUST** 由 artifact lint gate(`tools/lint_artifacts.py` 的 registry 一致性校验，纳入 CI 强制)双向自动校验：任一方向的成员漂移或属性漂移 **MUST** 触发 conformance 失败，MUST NOT 仅靠人工 review 保证。该 gate 既覆盖 §5 整体动作集，也覆盖 §5.0 四类偏离与 §5.0.1 聚合 admin 覆盖集的 RFC 约束（散文新增 target_event_kinds 成员必须同步 registry 且经 RFC）。

裸名动作（例如 `realm.upgrade` 或 `realm.link.manage`）MUST NOT 被接受。`ck.realm.admin` 覆盖普通 Realm 管理动作，但 MUST NOT 自动覆盖 E2EE key export、legal hold bypass 或审计降级——后者 MUST 在 grant `actions[]` 中显式列出对应 high-risk 动作。

### 5.0 Action ↔ Event kind 偏离类别（normative reference）

绝大多数 action 与其 `target_event_kinds` 单一同名映射（`ck.strand.create` action ↔ `ck.strand.create` event）。当存在偏离时，授权决策、IAM 工具与 audit 解析 MUST 以 `capability-action-registry.json` 的 `target_event_kinds` 为准，而不是用 action 字符串拆解推断 event kind。**偏离限定为以下四类**，任何其它类型的偏离 **MUST NOT 被引入**：

| 类别 | 形态 | 标准示例 |
| --- | --- | --- |
| **聚合 admin 动作** | 一个 action 覆盖多条 Realm policy facet event kinds | `ck.realm.admin` → registry 中声明的 Realm policy facet events；`ck.policy.manage` → `ck.policy.*` 与 `ck.realm.policy_*` 系列 |
| **polymorphic 对象动作** | 一个 action 同时覆盖 Strand / Morph / Space 等同语义 event | `ck.object.archive` → `{ck.strand.archive, ck.morph.archive}`；`ck.object.restore` → `{ck.strand.restore, ck.morph.restore, ck.space.restore}`；`ck.object.stage.set` → `{ck.strand.stage.set, ck.morph.stage.set}` |
| **scope 后缀变体** | 同一 event，授权按 self vs others / target subset 分粒度 | `ck.message.revise.own` → `ck.message.revise`；`ck.message.redact.own` → `ck.message.redact`；`ck.strand.watch.set.others` → `ck.strand.watch.set` |
| **操作动词动作（`event_mapping_kind="operation_verb"`）** | action token 命名为操作 / 命令动词，与 target event kind 名形态不同；reducer admission 经 `target_event_kinds` 解析，逐字命中 `actions[]` 规则照常适用，且不带聚合 admin 语义 | `ck.agent.interop_session.cancel` → `{ck.agent.interop_session.status, ck.agent.interop_session.result}`（命令动词写入 lifecycle 事件）；`ck.agent.interop_session.stream_status` → `ck.agent.interop_session.status`；`ck.message.redact` → `{ck.message.redact, ck.redaction}` |

`ck.mls.commit` action → `{ck.mls.commit, ck.mls.commit_failed}`、`ck.moderation.appeal.review` → `{ck.moderation.appeal.review, ck.moderation.appeal.decision, ck.moderation.appeal.close}` 等"同一 action 同时覆盖正常 event 与诊断 / 派生 event"的情况落在**聚合 admin 动作**类别，并以 registry `target_event_kinds` 为准。

`ck.message.redact` → `{ck.message.redact, ck.redaction}` **不是聚合 admin**：registry 把它标为 `event_mapping_kind="operation_verb"`（risk_tier=medium），即上表第四类“操作动词动作”。授权决策、IAM 工具与 audit 解析 MUST 以 registry 的 `event_mapping_kind` 与 `target_event_kinds` 为准。

**聚合 admin 的覆盖语义仅作用于 event-kind 解析层，不改变授权层 `actions[]` 的逐字命中规则。** 例如 `ck.policy.manage` 在 §5.4 与具体的 `ck.policy.set` / `ck.policy.rule` / `ck.policy.action` 并列：持有 `ck.policy.manage` 的 grant 表示该 admin action 在 registry 中聚合覆盖 `ck.policy.*` 与 `ck.realm.policy_*` 系列对应的 **event kinds**（audit / reducer 据 `target_event_kinds` 解析），但它**不在授权层自动等价于持有 `ck.policy.set` / `ck.policy.rule` / `ck.policy.action` 这三个具体 action token**。授权判定仍 MUST 按 §5「`actions[]` MUST 逐字命中、MUST NOT wildcard / segment 通配」执行：要授予某具体 policy 子动作，grant 的 `actions[]` MUST 显式列出 `ck.policy.manage`（若 receiver 已声明并接受该 action 对相应 event kinds 的聚合覆盖）或对应的具体 action token，二者不可互相推断。

新增动作 MUST 默认与 event kind 同名；只有上述四类之一的明确理由可以偏离，且必须在 `contract-catalog.json` 内显式声明 `target_event_kinds` 与 `event_mapping_kind`。**新增偏离类别 MUST 在 RFC 中讨论后才能加表项；MUST NOT 通过 lint 例外或注释方式悄悄引入新桥**。

#### 5.0.1 聚合 admin 覆盖集防权限蠕变（normative）

聚合 admin 动作（`ck.realm.admin`、`ck.policy.manage` 等，见上表第一类）的 `target_event_kinds` 是一个随 registry 演进可能增长的集合。若允许它随 registry 静默膨胀，则一个早先签发、覆盖范围较窄的历史 grant 会因后续向某聚合 action 的 `target_event_kinds` 新增成员而**自动扩大**其实际授权面（权限蠕变 / authority creep）。为关闭该面，v1 固定：

- 向任一聚合 admin action 的 `target_event_kinds` **新增成员 MUST 经 RFC**（与 §5.0 末段的偏离类别变更同级流程），MUST NOT 通过 lint 例外、注释或非 RFC 的 registry 直接编辑引入。
- 既有 grant 对该新增成员的覆盖 **MUST NOT 对历史 grant 自动生效**。`target_event_kinds` 扩张后，一个在扩张前签发的 grant 持有该聚合 action 时，其对**新增** event kind 的授权 MUST 由部署**显式 opt-in**（部署 policy 声明接受该聚合 action 的新版本覆盖集）或对受影响 grant **重签**（issuer 在扩张后的 registry basis 下重新签发 grant）后才生效。
- 实现 MUST 能区分"grant 签发时点聚合 action 覆盖的 event kind 集"与"当前 registry 覆盖集"，并在历史 grant 未 opt-in / 未重签时，对**仅由扩张才纳入**的 event kind **fail closed**（按未授权处理），而不是按当前 registry 集自动放行。该 basis 与 §3.2 首发 grant issuer 上界校验、§18.1 `auth_state_digest` 绑定的 registry 版本协同：grant 的有效覆盖集锚定到其签发 basis，registry 扩张不回溯放宽历史授权。
- 收窄（从 `target_event_kinds` 移除成员）不受 opt-in 约束——移除只会收紧历史 grant 的覆盖，不构成权限放大。

### 5.1 通用动作

- `ck.realm.discover`
- `ck.realm.create`
- `ck.realm.update`
- `ck.realm.archive`
- `ck.realm.freeze`
- `ck.realm.tombstone`
- `ck.realm.destroy`
- `ck.object.read`
- `ck.object.read_metadata`
- `ck.object.read_content`
- `ck.object.read_history`
- `ck.object.archive`
- `ck.object.restore`

### 5.2 Strand 与工作流动作

- `ck.strand.create`
- `ck.strand.read`
- `ck.strand.update`
- `ck.strand.archive`
- `ck.strand.restore`
- `ck.strand.move`
- `ck.strand.reorder`
- `ck.strand.tracks.update`（Strand tracks map 写入入口：启用 / 关闭 track、切换 primary、修改 track profile，target=`ck.strand.tracks.update`，`event_mapping_kind=same_name`。这是该 action 的权威定义；§5.3 仅交叉引用）
- `ck.relation.create`
- `ck.relation.update`
- `ck.relation.tombstone`
- `ck.space.create`
- `ck.space.update`
- `ck.space.parent`
- `ck.space.archive`
- `ck.space.restore`
- `ck.space.tombstone`
- `ck.container.move_item`
- `ck.container.rebalance`
- `ck.view.create`
- `ck.view.update`
- `ck.view.reconcile`
- `ck.morph.read`
- `ck.morph.create`(默认 required constraint:`allowed_morph_types`)
- `ck.morph.update`(默认 required constraint:`allowed_write_fields`)

Strand 权限只覆盖 Strand 自身字段、track 配置和 position / relation 管理。Message 正文权限按 Strand 的 effective scope 判断：`Strand.scope_circle_id=null` 时使用 Realm-default capability；`scope_circle_id` 指向 Circle 时使用该 [Circle](../models/circle.md) scope 的 capability + Circle membership 两层 AND（详见 [`circle.md` §8](../models/circle.md)）。

若 Circle membership control cell 在当前 CBA basis 下为 `⊥`（`fsm, bottom=reject`），上述两层 AND 的 membership 分支 MUST fail closed：授权结果为 deny，后续依赖该 cell 的 DataEvent / Control Move MUST 返回 `failed_bottom`（`reason=cell_in_bottom_state`），而 `failed_precondition` 仅用于 predicate 本身不成立（cell 持有明确 value 但 predicate 求值为 false）的情形；实现 MUST NOT 把 `⊥` 当作非成员、空成员集或任一候选 membership 状态来继续授权。

Morph 权限粒度与 Strand 平行(`ck.morph.read` / `ck.morph.create` / `ck.morph.update` 对应 `ck.strand.read` / `ck.strand.create` / `ck.strand.update`),通过 `allowed_morph_types` constraint 进一步限定可创建或操作的 `morph_type`。

### 5.3 Discussion 与消息动作

- `ck.event.read`
- `ck.message.create`
- `ck.message.mention.broadcast`（high risk；允许在 `ck.message.create` / `ck.message.revise` 中新增 audience mention，例如 `@all` / `@here`。必须同时持有普通消息写入授权，且 grant MUST 携带 rate-limit quota（`max_operations` + `period`），Realm / Circle policy MUST 声明允许的 audience 与 `max_recipients`；`@here` 映射为 `audience="strand_engaged"` 且不使用 presence / online 状态；详见 [`../models/strand-and-message.md` §9.4.4](../models/strand-and-message.md)）
- `ck.message.revise`
- `ck.message.revise.own`
- `ck.message.redact`
- `ck.message.redact.own`
- `ck.reaction.add`
- `ck.reaction.remove`
- `ck.strand.tracks.update`（管理 track 启用 / primary / profile；权威定义见 §5.2，此处仅交叉引用，target=`ck.strand.tracks.update`，`event_mapping_kind=same_name`）
- `ck.strand.watch.set`（写入自己的 watch 订阅，target=`ck.strand.watch.set`；详见 [`../models/strand-and-message.md` §8](../models/strand-and-message.md)）
- `ck.strand.watch.set.others`（high risk；为他人写入 `level ∈ {mentions_only, participating, all}` 的 watch 订阅；MUST NOT 写入 `muted` 或 `level_public=true`，target=`ck.strand.watch.set`；详见 [`../models/strand-and-message.md` §8.4](../models/strand-and-message.md)）

### 5.4 管理动作

- `ck.circle.create`（创建 Circle；默认不进入普通成员 bundle；Realm 管理员交接若希望接手者能继续创建 Circle，必须显式把本 action 纳入交接 bundle 或产品管理员角色）
- `ck.circle.manage`（管理 Circle lifecycle / metadata；MUST 通过 `allowed_circle_ids` 或 `kind="circle"` selector 收窄；不得由 `ck.realm.admin`、Realm owner transfer 或无约束 Realm-wide grant 隐式推出）
- `ck.circle.member.add`（自助加入 / 接受邀请 / 自助离开，受 Circle join_rule 与父 Realm membership gate 约束）
- `ck.circle.member.manage`（邀请、移除或 ban 他人；MUST 通过 `allowed_circle_ids` 或 `kind="circle"` selector 收窄；Realm admin transfer 不自动赋予本 action，也不自动创建 Circle membership）
- `ck.circle.member.add.others`（high risk；代他人写入 Circle membership，MUST 与 `ck.audit.accessed` 配对）
- `ck.circle.audit`（high risk；审计读取 Circle 元数据 / activity rollup，MUST 与 `ck.audit.accessed` 配对）
- `ck.realm.admin`
- `ck.audit.applet_binding`（high risk；新增、暂停或撤销 Audit Applet Binding；target=`ck.audit.applet_binding`）
- `ck.audit.session.authorize`（high risk；授权某个 Audit Applet release session；Circle-scoped session 必须由覆盖该 Circle 的 grant 授权）
- `ck.realm.link`（管理 Realm 间关系图，target=`ck.realm.link`）
- `ck.realm.upgrade`
- `ck.realm.moderation_policy`（管理 Realm 审核策略，target=`ck.realm.moderation_policy`）
- `ck.realm.plaintext_visible_services`（high risk；修改 E2EE 边界外可见明文的服务声明，target=`ck.realm.plaintext_visible_services`）
- `ck.realm.preview_policy`（high risk；修改加入前 / token-scoped preview 可披露字段、历史 stub 或明文 snippet 的策略，target=`ck.realm.preview_policy`）
- `ck.strand.admin`
- `ck.realm.notification.audit`（读取完整 watch 状态含 `muted`；MUST 与 `ck.audit.accessed` 同时持有，详见 [`../models/strand-and-message.md` §8.5](../models/strand-and-message.md)）
- `ck.schema.define`
- `ck.schema.update`
- `ck.capability.grant`
- `ck.capability.delegate`
- `ck.capability.derived`（risk_tier=medium；记录从 parent grant 机械派生出的 child grant 记录，target=`ck.capability.derived`。与 `ck.capability.delegate` 的区别：`delegate` 是“主体主动再授权第三方”的授权动作，`derived` 仅承载 reducer / 工具按既有委托规则物化出的派生 grant 记录，不引入新的授权意图）
- `ck.capability.revoke`
- `ck.agent.key.authorize`（high risk；授权 agent key，target=`ck.agent.key.authorize`）
- `ck.agent.key.rotate`（high risk；轮换 agent key，target=`ck.agent.key.rotate`）
- `ck.agent.key.revoke`（high risk；撤销 agent key，target=`ck.agent.key.revoke`）
- `ck.self.agent.command.provision`(aggregate admin action,`target_event_kinds=[ck.profile.create, ck.identity.accountability_grant, ck.agent.key.authorize, ck.capability.grant]`,profile=`ck.profile.personal_agent_provisioning.v1`)
- `ck.self.agent.command.pause`(controller-only;target=`ck.self.agent.command.pause`)
- `ck.self.agent.command.resume`(controller-only;target=`ck.self.agent.command.resume`)
- `ck.self.agent.command.deactivate`(controller-only,terminal;target=`ck.self.agent.command.deactivate`,fan-out 见 [`../identity/account-lifecycle.md` §9.1](../identity/account-lifecycle.md))
- `ck.agent.draft.propose`(agent-initiated draft;target=`ck.agent.draft.propose`,wire_scope=`actor_private_event`)
- `ck.agent.action_request`(agent-initiated action request;target=`ck.agent.action_request`)
- `ck.agent.action_approve`(controller-only;target=`ck.agent.action_approve`)
- `ck.agent.action_reject`(controller-only;target=`ck.agent.action_reject`)
- `ck.self.agent.sidecar_thread.command.ensure`(aggregate admin action,`target_event_kinds=[ck.circle.create, ck.circle.member.state, ck.strand.create, ck.relation.create]`,profile=`ck.profile.agent_sidecar_thread.v1`。该 action MAY 作为 self-scoped default capability 授予 Realm active member，仅允许创建 / 复用自己的 sidecar profile constrained Circle / Strand / Relation；不授予普通 `ck.circle.create`。Controller-private projection 写入(`ck.agent.sidecar_projection.v1`)不属于此 grant 集合)
- `ck.agent.sidecar_thread.write`(profile action;`target_event_kinds=[ck.message.create]`,resource 必须限定 sidecar private Strand)
- `ck.agent.sidecar_thread.publish`(profile action;target event kinds 由最终发布目标决定，至少包括 `ck.message.create`，受 reply-as-agent / act-on-behalf attribution 规则约束)
- `ck.self.agent.participation.resource.replace`(controller-only aggregate admin;profile=`ck.profile.agent_participation_policy.v1`，`target_event_kinds=[ck.capability.grant, ck.capability.revoke]`。controller 设置某 agent 在某 scope 的参与选择 `{reply, accept_third_party_mention, act_on_behalf}`；服务端校验 `selection ⊆ effective_ceiling`（deployment ⊇ Realm ⊇ Circle ⊇ Strand 的单调收紧 fold），超出对应位返回 `failed_precondition`（`reason="agent_participation_exceeds_ceiling"`）。**fold 各层不可读时 fail-closed（normative）**：effective_ceiling 的四层 fold（deployment / Realm / Circle / Strand ceiling）中**任一层** cell 在求值 basis 下处于 `⊥`（多 head / fork quarantine）或不可解析（缺失、frontier 不可达、freshness `unknown`）时，该层 **MUST** 按**最严格**值参与 fold——即对该层取空 selection / 全 deny（该层对每个参与位贡献"不允许"），而**不得**按"该层无声明 = 不收紧"放宽到上层 ceiling。由于 fold 是单调收紧（AND 各层），任一层贡献全 deny 即令 effective_ceiling 在对应位收紧为 deny；此时若 `selection` 在该位请求允许，`ck.self.agent.participation.resource.replace` **MUST** 返回 `failed_precondition`（`reason="agent_participation_ceiling_unresolved"`），MUST NOT 物化对应 `ck.capability.grant`。这保证 fold 的单调收紧不被某层不可读静默破坏（不可读层绝不放宽下层选择）。`reply` / `act_on_behalf` effective 为真时物化为既有 `ck.capability.grant`（`ck.message.create` 等），为假时 `ck.capability.revoke`；`accept_third_party_mention` 不物化为 grant，而是 driver of [`../models/strand-and-message.md` §9.4](../models/strand-and-message.md) 的第三方 mention 投递 gate。controller-owned `ck.agent.participation.v1` account-data 写入不纳入此 grant 集合（由 controller 对自身 account-data 的固有写权批准）。Realm-level ceiling 由持有 `ck.realm.admin` 的 principal 通过 `ck.realm.policy_components` 的 `agent_participation` 组件写入；Circle / Strand ceiling 分别由 `ck.circle.manage` / `ck.strand.admin` 写入对应 object 的 `agent_participation` 字段，reducer 强制 tighten-only。Realm / Circle / Strand ceiling 分别见 [`../models/realm-and-space.md`](../models/realm-and-space.md)、[`../models/circle.md`](../models/circle.md)、[`../models/strand-and-message.md` §9.4.5](../models/strand-and-message.md))
- `ck.agent.protocol.discover`（profile=`ck.profile.agent_runtime.v1`，risk_tier=low，`non_event_surface`，无 target event：发现 agent runtime 协议端点 / capability，仅服务面发现，不写入 event）
- `ck.agent.interop_session.start`（profile=`ck.profile.agent_runtime.v1`，high risk；启动 agent interop session，`event_mapping_kind=same_name`，target=`ck.agent.interop_session.start`；required constraint `allowed_endpoints` + `allowed_data_classes`）
- `ck.agent.interop_session.cancel`（profile=`ck.profile.agent_runtime.v1`，medium；取消 / 终止 session，`event_mapping_kind=operation_verb`，target=`{ck.agent.interop_session.status, ck.agent.interop_session.result}`）
- `ck.agent.interop_session.stream_status`（profile=`ck.profile.agent_runtime.v1`，low；流式上报 session 状态，`event_mapping_kind=operation_verb`，target=`ck.agent.interop_session.status`）
- `ck.agent.interop_session.attach_artifact`（profile=`ck.profile.agent_runtime.v1`，high risk；附加 session artifact，`event_mapping_kind=operation_verb`，target=`{ck.agent.interop_session.status, ck.agent.interop_session.result}`；required constraint `allowed_data_classes` + `max_artifact_bytes`）
- `ck.agent.interop_session.read_transcript`（profile=`ck.profile.agent_runtime.v1`，high risk；读取 session transcript，`non_event_surface`，无 target event；required constraint `allowed_data_classes`）

> 以上 agent runtime / interop session 动作均 profile-gated（`ck.profile.agent_runtime.v1`），未声明该 profile 的 receiver MUST 按 registry_rules 视为 unknown 并 default 高风险 fail-closed。

- `ck.policy.manage`
- `ck.policy.set`
- `ck.policy.rule`（管理 policy 规则集合，target=`ck.policy.rule`）
- `ck.policy.action`（管理 policy 动作集合，target=`ck.policy.action`）
- `ck.invite.create`
- `ck.invite.cancel`
- `ck.invite.third_party`（签发 3PID 邀请，target=`ck.invite.third_party`）
- `ck.invite.claim`
- `ck.invite.revoke`
- `ck.realm.join.review`（候选 capability，与 candidate join-policy event 配对：审核 `member.application`、签发 `member.application.review`；详见 [`../governance/join-policy.md` §7](../governance/join-policy.md)。capability-action-registry 中 `profile = "ck.profile.candidate.join_policy.v1"`：未声明该候选 profile 的 receiver MUST 按 registry_rules 把本 action 视为 unknown，default risk_tier=high。Join-policy 正式登记前，本 capability 不属于 v1 active conformance。**Candidate / Profile-only**：`ck.realm.join.review` 不是 v1 base conformance 必需 capability；base v1 实现把 review 结果承载为 signed receipt（`review_receipt_digest`），并把 `ck.invite.create.refs[role='join_authorised_by']` 指向该 receipt digest（见 [`../governance/join-policy.md` §7.5](../governance/join-policy.md)）。只有声明 join-policy candidate profile 的部署才需要注册该 capability。）
- `ck.approval.vote`
- `ck.moderation.decision`（写入 sealed moderation state cell；详见 [`policy-server.md` §7.1](./policy-server.md)）
- `ck.moderation.decision.lift`（解除已 sealed 的 moderation 决策）
- `ck.moderation.appeal.submit`（risk_tier=low；提交对 moderation 决策的申诉，target=`ck.moderation.appeal.submit`）
- `ck.moderation.appeal.review`（risk_tier=medium；审理申诉，aggregate admin action，target=`{ck.moderation.appeal.review, ck.moderation.appeal.decision, ck.moderation.appeal.close}`）

### 5.5 服务动作

- `ck.self.events.query.scan`
- `ck.self.events.stream.subscribe`
- `ck.self.account.stream.subscribe`
- `ck.self.account.query.describe`
- `ck.self.snapshot.query.manifest_head`
- `ck.self.blob.upload.create`
- `ck.self.blob.resource.get`
- `ck.self.blob.resource.head`
- `ck.self.blob.command.presign`（签发预签名 blob URL；必需 constraint `blob_presign_scope` + `blob_presign_max_ttl_seconds`）
- `ck.realm.media_service`（target=`ck.realm.media_service`，`event_mapping_kind=same_name`）
- `ck.mls.genesis`
- `ck.mls.proposal`
- `ck.mls.commit`
- `ck.mls.welcome`
- `ck.mls.keypackage`
- `ck.audit.accessed`
- `ck.audit.session.request`
- `ck.audit.session.notice`
- `ck.audit.release`
- `ck.audit.session.close`
- `ck.audit.query`
- `ck.audit.export`
- `ck.presence.broadcast`
- `ck.typing.broadcast`
- `ck.receipt.broadcast`
- `ck.call.signal.send`
- `ck.call.join`（risk_tier=medium；加入通话，scope_suffix_variant，target=`ck.call.state`）
- `ck.call.screen_share`（risk_tier=medium；屏幕共享，scope_suffix_variant，target=`ck.call.state`）
- `ck.call.record`（**high risk**；录制通话，aggregate admin action，target=`{ck.call.recording.start, ck.call.state}`；MUST 按 high-risk 规则携带 `expires_at`、resource selector narrowing 与审计证据）
- `ck.call.transcribe`（**high risk**；转写通话，scope_suffix_variant，target=`ck.call.state`；同 high-risk 约束要求）
- `ck.call.moderate`（risk_tier=medium；通话内 moderation，scope_suffix_variant，target=`ck.call.state`）

v1 不再注册独立的 `ck.mls.epoch` event；每个 group 的当前 epoch 由 accepted `ck.mls.commit` payload 中的 `next_epoch` 和对应 `ck.component.mls_epoch.v1` cell reducer 结果直接表达，没有"推进 epoch"这个独立可授权动作。

Audit action 只授权受控审计 applet / release service 执行绑定、阶段性 session、成员通知、sealed historical release、审计视图读取或审计材料导出。审计 applet 不是 MLS group 成员，也不会因 capability 获得实时消息 fanout；E2EE 合规 release 必须走 active `ck.audit.applet_binding`、`ck.audit.session.*`、`ck.audit.release` 和 RYW receipt。普通 Realm/Circle 治理举报不使用这些 action，举报只路由给 scoped 管理员 / moderator。

### 5.6 人类界面与个人状态动作

- `ck.read_cursor.advance`（capability action; 对应 event kind 同名 `ck.read_cursor.advance`）
- `ck.notification.read`
- `ck.notification.ack`
- `ck.invite.accept`

## 6. Constraints

Cokret v1 支持以下约束字段（按 constraint family 分组，与 `grant-constraint.schema.json` 属性分组一致）。**allow 与 deny 两侧都属于 v1 受支持约束**；deny / `denied_*` / `*_deny` 字段不是扩展私货，它们与对应 allow 字段同源，命中即按 §15 “任一 deny 命中即生效”裁决：

**temporal**

- `expires_at`
- `not_before`
- `message_edit_window`
- `message_redact_window`
- `allow_redact_after_window`

**field_access**

- `allowed_write_fields`
- `denied_write_fields`
- `allowed_read_fields`
- `denied_read_fields`
- `sensitive_fields`
- `sensitive_handling`

**type_restriction**

- `allowed_object_types`
- `denied_object_types`
- `allowed_morph_types`
- `denied_morph_types`
- `allowed_space_kinds`
- `denied_space_kinds`
- `allowed_facets`
- `denied_facets`

**scope_limitation**

- `allowed_strand_ids` / `denied_strand_ids`
- `allowed_space_ids` / `denied_space_ids`
- `allowed_view_ids`
- `allowed_view_kinds` / `denied_view_kinds`
- `allowed_view_renderers` / `denied_view_renderers`
- `allowed_circle_ids`（限定 Circle-scoped capability 动作（`ck.circle.manage` / `ck.circle.member.manage` 等）到列出的 Circle id；配合 `resource-selector-grammar.md` §2.2 的 Circle selector 使用。Realm-wide 无收窄的 Circle 管理 grant 不是正常授权形态）
- `allowed_tracks` / `denied_tracks`
- `allowed_relation_kinds`（**kanban extension**，profile-gated `ck.profile.kanban_mvp.v1`；未声明该 profile 的实现 MUST fail closed，见 [`constraint-schema.md` §2.2](./constraint-schema.md)）
- `allowed_from_container_refs`（同上，kanban extension，profile-gated `ck.profile.kanban_mvp.v1`，fail closed）
- `allowed_to_container_refs`（同上，kanban extension，profile-gated `ck.profile.kanban_mvp.v1`，fail closed）
- `wip_limit_override`（同上，kanban extension）
- `blob_presign_scope`
- `allowed_data_classes`
- `allowed_endpoints`

**delegation_control**（求值规则见 [`constraint-schema.md` §7.3](./constraint-schema.md)：`prohibit_subdelegation=true` ⇒ child `max_delegation_depth` MUST=0；`allow_scope_expansion=true` 在 v1 MUST 被 reducer 拒绝（`schema_violation`，与 §10.1 收窄不变量矛盾）；`delegation_scope` 三值 `narrowing_only`/`same_scope`/`custom` 各自校验规则）

- `max_delegation_depth`
- `delegation_path`
- `prohibit_subdelegation`
- `delegation_scope`
- `allow_scope_expansion`
- `require_parent_reference`

**quota**

- `rate_limit`（`max_operations` + `period`，可选 `burst`）
- `resource_limit`（`max_resources` + `resource_type`，可选 `period`；见 [`constraint-schema.md` §8.2](./constraint-schema.md)）
- `blob_max_bytes`
- `blob_presign_max_ttl_seconds`
- `max_total_blob_bytes`
- `max_artifact_bytes`

**claim_based**

- `approval_required`
- `approval_mode`
- `approval_actor_ids`
- `approval_relation`
- `accountability_required`
- `guardian_approval_required`
- `controller_approval_required`
- `requires_claims`
- `trusted_claim_issuers`
- `claim_refresh_required`
- `claim_max_age`

**confidentiality**

- `allowed_history_visibility_values`
- `deny_redacted_history`（命中即拒绝读取已 redact 的历史，属 `confidentiality` `subtype=visibility`）
- `encryption_required`

**moderation 缓存依赖标记**

- `depends_on_moderation_state`（缓存失效 hint，默认 `false`；当 grant 的授权决策依赖 `ck.component.moderation_state.v1` cell 时 MUST 显式声明 `true`，触发条件与静态 lint 规则见 §18.1。它本身不是 allow/deny 约束，而是 fast-path cache 失效绑定，定义见 [`grant-constraint.schema.json`](../../artifacts/schemas/grant-constraint.schema.json) 与 [`constraint-schema.md` §18.1 引用](./constraint-schema.md)）

上表中的扁平名称是 `constraint-schema.md` 中 typed constraint 对象的 shorthand 别名。完整约束结构和求值规则以 `constraint-schema.md` 为准；机读权威源是 [`grant-constraint.schema.json`](../../artifacts/schemas/grant-constraint.schema.json)。

### 6.1 Effective Validity Window

Grant 的 wire schema 同时允许顶层 `not_before` / `expires_at` 和 `constraints[]` 中的 temporal `not_before` / `expires_at`。它们不是两套独立有效期；授权解析 MUST 先归一化为单一 effective window：

```text
effective_not_before = max(grant.not_before?, temporal.not_before[]?)
effective_expires_at = min(grant.expires_at?, temporal.expires_at[]?)
```

缺省的 lower bound 视为无下限；缺省的 upper bound 视为无上限，但高风险、agent、service、delegated grant 仍按本文风险规则 MUST 有有限 `effective_expires_at`。若归一化后 `effective_not_before >= effective_expires_at`，reducer MUST `failed_precondition`，`reason="grant_validity_window_empty"`。授权日志、缓存 key、delegation narrowing 和 revoke freshness 判断都 MUST 使用 effective window，MUST NOT 分别按顶层字段和 temporal constraint 做两次不一致判断。

| 扁平名称 | Typed `constraint_type` | `subtype` | 对应字段 |
|----------|------------------------|----------|----------|
| `expires_at` | `temporal` | — | `expires_at` |
| `not_before` | `temporal` | — | `not_before` |
| `allowed_write_fields` | `field_access` | — | `allowed_write_fields` |
| `denied_write_fields` | `field_access` | — | `denied_write_fields` |
| `allowed_read_fields` | `field_access` | — | `allowed_read_fields`（读取面字段允许列表，见 [`constraint-schema.md` §4.3](./constraint-schema.md)） |
| `denied_read_fields` | `field_access` | — | `denied_read_fields`（读取面字段拒绝列表，[`constraint-schema.md` §16.2](./constraint-schema.md) 算法消费） |
| `sensitive_fields` | `field_access` | — | `sensitive_fields`（读取时需特殊处理的敏感字段集） |
| `sensitive_handling` | `field_access` | — | `sensitive_handling`（敏感字段处理方式：`redact` / `hash` / `omit`） |
| `allowed_object_types` | `type_restriction` | — | `allowed_object_types` |
| `denied_object_types` | `type_restriction` | — | `denied_object_types`（命中即拒绝该对象类型） |
| `allowed_space_kinds` | `type_restriction` | — | `allowed_space_kinds`（限定 Space 的 kind，例如 board / list / swimlane）|
| `denied_space_kinds` | `type_restriction` | — | `denied_space_kinds` |
| `allowed_morph_types` | `type_restriction` | — | `allowed_morph_types` |
| `denied_morph_types` | `type_restriction` | — | `denied_morph_types` |
| `allowed_facets` | `type_restriction` | — | `allowed_facets` |
| `denied_facets` | `type_restriction` | — | `denied_facets` |
| `allowed_strand_ids` | `scope_limitation` | — | `allowed_strand_ids` |
| `denied_strand_ids` | `scope_limitation` | — | `denied_strand_ids` |
| `allowed_space_ids` | `scope_limitation` | — | `allowed_space_ids` |
| `denied_space_ids` | `scope_limitation` | — | `denied_space_ids` |
| `allowed_view_ids` | `scope_limitation` | — | `allowed_view_ids` |
| `allowed_view_kinds` | `scope_limitation` | — | `allowed_view_kinds` |
| `denied_view_kinds` | `scope_limitation` | — | `denied_view_kinds` |
| `allowed_view_renderers` | `scope_limitation` | — | `allowed_view_renderers` |
| `denied_view_renderers` | `scope_limitation` | — | `denied_view_renderers` |
| `allowed_circle_ids` | `scope_limitation` | — | `allowed_circle_ids`（限定 Circle-scoped 动作到列出的 Circle id，配合 Circle selector） |
| `allowed_tracks` | `scope_limitation` | — | `allowed_tracks` |
| `denied_tracks` | `scope_limitation` | — | `denied_tracks` |
| `allowed_relation_kinds` | `scope_limitation`（kanban extension，profile-gated `ck.profile.kanban_mvp.v1`，fail closed） | — | `allowed_relation_kinds` |
| `allowed_from_container_refs` | `scope_limitation`（kanban extension，profile-gated `ck.profile.kanban_mvp.v1`，fail closed） | — | `allowed_from_container_refs` |
| `allowed_to_container_refs` | `scope_limitation`（kanban extension，profile-gated `ck.profile.kanban_mvp.v1`，fail closed） | — | `allowed_to_container_refs` |
| `wip_limit_override` | `scope_limitation`（kanban extension，profile-gated `ck.profile.kanban_mvp.v1`） | — | `wip_limit_override`（看板容器 WIP 上限覆盖） |
| `allowed_history_visibility_values` | `confidentiality` | `visibility` | `allowed_history_visibility_values` |
| `deny_redacted_history` | `confidentiality` | `visibility` | `deny_redacted_history`（命中即拒绝读取已 redact 历史） |
| `blob_max_bytes` | `quota` | `resource` | `blob_max_bytes` |
| `blob_presign_max_ttl_seconds` | `quota` | `resource` | `blob_presign_max_ttl_seconds` |
| `max_artifact_bytes` | `quota` | `resource` | `max_artifact_bytes` |
| `blob_presign_scope` | `scope_limitation` | — | `blob_presign_scope` |
| `allowed_data_classes` | `scope_limitation` | — | `allowed_data_classes` |
| `allowed_endpoints` | `scope_limitation` | — | `allowed_endpoints` |
| `encryption_required` | `confidentiality` | `encryption` | `encryption_required` |
| `message_edit_window` | `temporal` | `edit_window` | `message_edit_window` |
| `message_redact_window` | `temporal` | `redact_window` | `message_redact_window` |
| `allow_redact_after_window` | `temporal` | `edit_window` / `redact_window` | `allow_redact_after_window`（窗口修饰符，见 [`constraint-schema.md` §14.2](./constraint-schema.md)） |
| `max_delegation_depth` | `delegation_control` | — | `max_delegation_depth` |
| `delegation_path` | `delegation_control` | — | `delegation_path`（委托链 DID 路径约束，见 [`constraint-schema.md` §7](./constraint-schema.md)） |
| `prohibit_subdelegation` | `delegation_control` | — | `prohibit_subdelegation` |
| `delegation_scope` | `delegation_control` | — | `delegation_scope`（`narrowing_only` / `same_scope` / `custom`） |
| `allow_scope_expansion` | `delegation_control` | — | `allow_scope_expansion` |
| `require_parent_reference` | `delegation_control` | — | `require_parent_reference` |
| `rate_limit` | `quota` | `rate` | `max_operations`, `period`, `burst` |
| `max_total_blob_bytes` | `quota` | `resource` | `max_total_blob_bytes`（scope 内累计字节上限） |
| `approval_required` | `claim_based` | `approval` | `approval_required` |
| `approval_mode` | `claim_based` | `approval` | `approval_mode` |
| `approval_actor_ids` | `claim_based` | `approval` | `approval_actor_ids` |
| `approval_relation` | `claim_based` | `approval` | `approval_relation` |
| `accountability_required` | `claim_based` | `accountability` | `accountability_required` |
| `guardian_approval_required` | `claim_based` | `accountability` | `guardian_approval_required` |
| `controller_approval_required` | `claim_based` | `accountability` | `controller_approval_required` |
| `requires_claims` | `claim_based` | `claim` | `requires_claims` |
| `trusted_claim_issuers` | `claim_based` | `claim` | `trusted_claim_issuers` |
| `claim_refresh_required` | `claim_based` | `claim` | `claim_refresh_required` |
| `claim_max_age` | `claim_based` | `claim` | `claim_max_age` |
| `depends_on_moderation_state` | （缓存依赖标记，非 allow/deny 约束） | — | `depends_on_moderation_state`（fast-path cache 失效 hint，默认 `false`；MUST 显式 `true` 的三类触发条件见 §18.1。它不归入 8 个 constraint family，而是 grant cache 失效绑定字段） |

### 6.2 资源类型 / facet / claim 约束求值规则

`discussion` 不是独立资源类型。需要限制 discussion track 时，使用 `allowed_object_types=["strand"]` 和 `allowed_tracks=["discussion"]`；MUST NOT 引入按 track profile 名称授权的 v1 grant 字段。`tracks.<name>.profile` 只是 Strand track 的语义/profile hint，MUST NOT 单独授予读取、发送或成员权限。

Facet 只在 grant 显式包含 `allowed_facets` / `denied_facets` 这类 typed constraint 时作为范围收窄条件参与第 7 步 constraints 判断；未声明 facet constraint 的 grant 不会因为目标对象具有 `stateful`、`assignable` 或其他 facet 而自动允许或自动拒绝。`facet=stateful` 不引入独立授权动作：修改 Morph `state` 仍 MUST 命中 `ck.morph.update` 或 profile 注册的更具体 action、目标 resource selector、`allowed_morph_types`、字段写约束、schema state transition policy 和其他有效 constraints。若 grant 允许 `ck.morph.update` 且没有字段/类型/策略拒绝，缺少 `allowed_facets=["stateful"]` 本身 MUST NOT 成为拒绝理由；若 grant 显式声明 `allowed_facets` 且目标 facets 不匹配，则 constraint 不满足。

`requires_claims[]` 中每个 claim 条目 MUST 明确绑定 `issuer` 或 `trusted_issuers[]`；`subject_matches_actor` 未出现时按 `true` 求值。实现 MUST NOT 接受只有 `claim_type` 而无发行者边界的 claim grant。

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
- Event MUST 记录 grant、delegation chain、approval 证据和执行上下文；缺失时 reducer MUST fail closed。

风险分层硬约束：

- `risk_tier=high` 的 action MUST 有 `expires_at`、resource selector narrowing、authorization evidence ref 与 audit evidence。
- 对需要更高保证的 high-risk action，profile MAY 要求显式 approval / proposal workflow、默认 `delegable=false`、更短 child grant TTL、不可扩大 scope 和 approver DID 记录；该要求 MUST NOT 通过 registry 未定义的第四级风险字符串表达。
- Agent / service principal 的 grant 无论 action 风险级别如何，默认 MUST 有最大 TTL 与 resource selector；缺失时 reducer MUST `failed_precondition`。

### 8.1 Proposal 模式

高风险操作建议使用 proposal 模式：

```txt
actor -> proposal.created
guardian/controller -> proposal.approved
system/human -> `ck.strand.update` 或 `ck.morph.update`
```

## 9. Agent 安全授权

给 agent 授权时 MUST 默认：

- 只授予明确 Realm / Strand / Message / Morph / View 范围。
- 只授予所需动作。
- 只授予有限时效。
- 只授予该 agent 任务所需的最小可写字段、可写 track 和可写 Morph 类型集合。
- 对 high action 按 action registry 与 profile 要求 controller / responsible actor approval。

高风险模式包括：

- 给 agent 长期全 Realm 管理权。
- 让 agent 直接继承 human owner 全权限。
- 不设过期时间。
- 不保留 agent 执行审计链。
- 高风险操作不需要 approval。

### 9.1 Personal-agent 授权预设展开（normative）

产品 UI / SDK MAY 暴露 personal-agent 授权预设(`read`、`draft`、`reply_as_agent`、`act_on_behalf`、`organizer`),以简化 `ck.profile.personal_agent_provisioning.v1` 下的 agent 授权输入。本节是这些预设到 canonical grant 的**权威展开定义**。

预设名的语义约束(MUST):

- **预设名不进入 canonical wire。** 预设只是 UI / SDK 便捷输入;server 接收与持久化的永远是 `ck.capability.grant` 的 `actions[]`、resource selector、registered constraints 与 effective validity window(§6.1)。任何 grant 校验、审计、delegation 收窄都基于展开后的 canonical 形态,MUST NOT 依赖预设名。
- **预设是 additive shorthand,不表达 deny / cap / only。** 同时选择多个预设时，结果是各预设 action / grant template 的**并集**;预设**不**移除、上限化或否定任何其他预设授予的权限。历史命名(如 `read_only` / `draft_only`)有 deny / cap 误导性,MUST NOT 作为 normative 预设名出现。若部署需要收窄，收窄只能通过 resource selector 与 constraint 表达，不能通过预设名。
- **实现 MUST NOT 引入未在下表登记的预设名**(例如 `write_summary` 等任意字符串)而不先在本表登记。
- **高风险预设 MUST 展开为完整 grant template**——包含 registry 要求的 required constraints 与有限 `expires_at`,而非无约束的 action union。

canonical 展开表:

| 预设 | Canonical actions | Required constraints | Resource scope | 语义 / 边界 |
| --- | --- | --- | --- | --- |
| `read` | `ck.event.read` | 显式 resource selector(MUST) | 显式 Realm / Strand / Circle scope,MUST NOT Realm-wide 无约束 | 授予**内容层**事件投影读能力。`ck.event.read` 是 `non_event_surface` 的内容读能力,**MUST NOT** 被解释为授予 events 服务面本身——agent 要真正调用 events 查询 / 订阅 endpoint,其 **session 还 MUST 携带对应服务面 scope**(`ck.self.events.query.scan` / `ck.self.events.stream.subscribe`,§5.5;见下方「服务面 scope 与内容能力分层」)。二者按 **AND** 组合:读取 surface 由服务面 scope 授权,payload 由 `ck.event.read` + membership / history visibility 授权(见 [`../models/relation.md` §4.2](../models/relation.md))。**MUST NOT** 隐含 object content/history 读取、`ck.object.read*`、`ck.strand.read`、E2EE history key 或 MLS membership。 |
| `read_content` / `read_history` | `ck.object.read_content` / `ck.object.read_history`(按需分别授予) | 显式 resource selector(MUST) | 同上 | 对象正文 / 历史读取是**独立的 additive 预设**,不折叠进 `read`。实现若需要"读事件+读正文",MUST 分别授予这些 action,而不是扩大 `read` 的展开集合。 |
| `draft` | `ck.agent.draft.propose`, `ck.agent.action_request` | `expires_at`(MUST,registry required) | controller-private control surface | 允许 agent 提出候选草稿 / 动作请求，由 Principal Server materialize controller-owned `ck.agent.draft.v1` account-data(见 [`../models/private-objects.md` §4.1](../models/private-objects.md))。两个 action 均 profile-gated 于 `ck.profile.personal_agent_provisioning.v1`。**MUST NOT** 直接发布到 shared Realm / Strand(不得展开为 `ck.message.create` / `ck.strand.create` 或任何 `wire_scope=durable_event`)。 |
| `reply_as_agent` | `ck.message.create`, `ck.reaction.add` | 显式 resource selector(MUST) | 显式 Strand / Circle scope | agent 以自身 principal identity 在授权 scope 内发消息 / 加反应。 |
| `act_on_behalf` | `ck.message.create`(及选定 workflow actions) | controller approval / accountability 证据(MUST,见 §8)+ 有限 `expires_at`(MUST)+ resource selector narrowing + audit evidence ref | 显式 scope,MUST NOT 全 Realm 无约束 | **高风险。** `actor_id` 为 controller、`executed_by` 为 agent 的 accountable-actor 授权(§8)。MUST 携带 controller approval / accountability 约束,MUST NOT 仅做 action union。 |
| `organizer` | `ck.strand.create`, `ck.strand.update`, `ck.relation.create`,受限 `ck.message.create` | `ck.strand.update` MUST 携带 `allowed_write_fields`(registry required);显式 resource selector(MUST) | 显式 Realm / Space scope | **中到高风险。** 结构化编排权限。包含 `ck.strand.update` 时 MUST 通过 `allowed_write_fields` 限定可写字段,MUST NOT 展开为无约束的 strand 全字段写。 |

**服务面 scope 与内容能力分层(normative)。** 本展开表定义的是**内容层 capability grant**(`ck.capability.grant.actions[]`)。要真正调用某服务面 endpoint,调用方 session **MUST** 另行携带对应**服务面 scope**——例如 events 面的 `ck.self.events.query.scan` / `ck.self.events.stream.subscribe`(§5.5 服务动作),由 session 签发时 provision(personal agent 见 [`../../proposals/0008-personal-agent-provisioning.md` §4.6](../../proposals/0008-personal-agent-provisioning.md))。服务面 scope 与内容能力是**正交两层，按 AND 组合**:持有 `ck.event.read` 内容能力 **MUST NOT** 被解释为授予该服务面(§5.0 `actions[]` 逐字命中、无 subsumption),持有服务面 scope 也不授予内容读；最终可见性再叠加 membership / history visibility(见 [`../models/relation.md` §4.2](../models/relation.md))。预设展开 **MUST NOT** 把服务面 scope 混入本内容能力表——服务面授权随 session 演进，与本表解耦，二者可各自独立演进。

**Membership 派生读取与受托读取(normative)。** Realm 成员的常规事件读取由 membership + history visibility + E2EE epoch policy 判定(见 [`../governance/history-visibility.md`](../governance/history-visibility.md) 与 [`../sync/service-http-binding.md`](../sync/service-http-binding.md) 中 events 读取面的授权规则),实现 **MUST NOT** 把持有显式 `ck.event.read` grant 作为成员读取的前置条件；本表 `read` 预设的 grant 形态服务于**受托主体**(personal agent 等非成员 principal)的显式窄化授权。在 E2EE Realm 中,`ck.event.read` grant 只界定读取 surface 可向该受托 session 返回的 event envelope 范围；内容可解密性由 MLS membership 决定——agent 的 E2EE access MUST 作为独立 MLS member 表达(personal agent 见 [`../../proposals/0008-personal-agent-provisioning.md` §4.6](../../proposals/0008-personal-agent-provisioning.md)),本 grant **MUST NOT** 被解释为 MLS admission 或任何 key share。低于 Realm 粒度的 resource selector 收窄由读取 surface 的投递过滤执行——实现 **MUST** 在读取 surface enforce 该过滤，且 **MUST NOT** 把该过滤宣称为密码学隔离(同 Realm 内不承诺对已入组成员的强读隔离，强读隔离必须切分 Realm,见 [`../models/realm-and-space.md` §1](../models/realm-and-space.md))。

> 上表 canonical actions 与 required constraints 以 [`../../artifacts/registry/capability-action-registry.json`](../../artifacts/registry/capability-action-registry.json) 为准。当 registry 声明某 action 的 `required_constraints` 或 `risk_tier` 变化时，本表 MUST 随之更新；二者冲突时以 registry 为权威。

## 10. Delegation

委托表示 subject 可以将其能力的一部分再授予第三方。

若 `max_delegation_depth = 0`，则 MUST NOT 继续委托。  
若大于 0，则：

- 每次再授权 MUST 递减深度。
- 再授权 MUST NOT 扩大原始资源范围和动作范围。
- 委托链 MUST 可验证。

### 10.1 时效收窄（normative）

`ck.capability.delegate` 派生 grant **MUST** 满足时间窗口收窄,reducer 校验:

| 子 grant 字段 | 与 parent grant 关系 |
| --- | --- |
| `effective_not_before` | MUST ≥ `parent.effective_not_before` |
| `effective_expires_at` | MUST 存在且 ≤ `parent.effective_expires_at`(无限期 parent 在 v1 中不允许；若 parent 未声明 finite effective upper bound,delegate 时 child MUST 自带 `expires_at` 或 temporal `expires_at`)。**注意：仅"child 自带 `expires_at` ≤ `now + max_delegation_lifetime_ms`"不足以防滚动续期；整条 child 链每一级的 `effective_expires_at` 还 MUST ≤ 不可刷新的固定 `delegation_expiry_seal`，见下方"固定 seal 防滚动续期"段。** |
| `max_delegation_depth` | MUST ≤ `parent.max_delegation_depth - 1` |
| `actions[]` | MUST ⊆ `parent.actions[]` |
| `resources[]` | MUST 是 `parent.resources[]` 的 selector-narrowing 子集(见 `resource-selector-grammar.md`) |
| `constraints[]` | MUST 至少包含 parent 的所有 deny / require / quarantine constraints; MAY 增加更严格的 allow constraints |

违反任何一项 reducer MUST 返回 `failed_precondition` reason=`delegation_expiry_widening`(对窗口),或 `schema_violation`(对 actions / resources / constraints 越界)。

**固定 seal 防滚动续期（normative）**：仅靠"child 自带 `expires_at` ≤ `now + max_delegation_lifetime_ms`"不足以约束无限期 parent——parent 可以每 `max_delegation_lifetime_ms` 自我 re-delegate 一次，每次都让 child 取得一个新的 `now + 24h`，从而把"无 finite upper bound 的 parent"漂白成事实无限期的 child 链。为关闭该面，无 finite effective upper bound 的 parent grant **MUST NOT** 直接作为 delegation source；任何从它派生的 child 链 MUST 绑定一个**固定 `delegation_expiry_seal`**，且整条链每一级的 `effective_expires_at` **MUST** ≤ `delegation_expiry_seal`，re-delegate **MUST NOT** 刷新该 seal：

- 若 parent grant 自身有 finite `effective_expires_at`，则 `delegation_expiry_seal = parent.effective_expires_at`（与表中收窄规则一致）。
- 若 parent grant 无 finite effective upper bound，则其第一次作为 delegation source 时，reducer **MUST** 冻结 `delegation_expiry_seal = first_delegation_sealed_at + max_delegation_lifetime_ms`（默认 24 小时），并把该 seal 作为不可变 child-chain 属性记录（`refs[role="delegation_expiry_seal"]` 或 profile 声明的等价字段）。
- 同一无限期 parent 的后续 re-delegate **MUST** 复用同一 `delegation_expiry_seal`，**MUST NOT** 用新的 `now` 重新计算；child 的 `effective_expires_at` 超过该 seal 时 reducer **MUST** 返回 `failed_precondition` reason=`delegation_expiry_widening`。

`max_delegation_lifetime_ms` 是 Realm authz 参数，wire 承载位置为 [`realm.schema.json`](../../artifacts/schemas/realm.schema.json) 的同名可选字段与 [`realm-and-space.md` §2.3](../models/realm-and-space.md) 字段表。缺省值为 `86400000`（24 小时）。若 grant / policy / deployment profile 声明更短窗口，effective value MUST 取所有适用窗口的最小值；child grant 或下游 profile 不得放宽父 Realm 的 effective value。实现无法读取该参数时 MUST 使用缺省值，不得把无限期 parent 视作可无限滚动续期。

本规则与 §8 "delegated grant MUST 有有限 expiry" 对齐：任何 child 链最终 expiry 都 MUST 可追溯到一个不随 re-delegate 推移的固定时点。

### 10.2 Cycle detection（normative）

`ck.capability.delegate` event 的 `refs[]` 中包含 `role="parent_grant"` 引用作为父 grant id。Reducer **MUST** 把所有已 sealed 的 delegation 关系视为有向图，节点是 `grant_id`,边是 `(parent_grant_id, child_grant_id)`,并按下列算法做 cycle detection:

Delegation Move SHOULD 同时记录签发时点的 parent `auth_state_digest` / `auth_frontier`（可放入 `refs[role="auth_frontier"]`、grant audit metadata 或 profile 声明的等价字段）。该记录不替代实时 revoke/freshness 校验，但用于审计 child grant 是基于哪个 parent policy/auth frontier 派生的；缺失时实现仍 MUST 重新按当前 frontier 验证，MUST NOT 把 child grant 当作不可追溯授权。

1. 收到新的 `ck.capability.delegate(child_grant_id, parent_grant_id)` 时,reducer 沿 parent chain 做 DFS,直到遇到无 parent 的 root grant 或深度 = `max_delegation_depth_observed`。
2. 若在 DFS 过程中发现新 `child_grant_id` 出现在已访问 ancestor 集合中(即新 grant 会 close 一条循环 path),reducer **MUST** 拒绝整条 delegation chain 上的本 Event,reason=`delegation_cycle`,MUST NOT 接受任何子 grant 即便它们单看 valid。
3. DFS 深度上限 default 4，即 [`scalability-constraints.md` §3](../conformance/scalability-constraints.md) 的 delegation chain 深度 canonical 上限(profile MAY 声明更低上限，MUST NOT 放宽)；超过深度的 chain 视作病态，reducer MUST 退化为拒绝。此外，grant 的 `max_delegation_depth` 字段本身 MUST ≤ 4:reducer 在 **accept grant 时** 即 MUST 校验该字段 ≤ DFS 深度上限，声明更大值的 grant MUST 以 `schema_violation` 拒绝(`grant-constraint.schema.json` 已用 `maximum:4` 静态强制)，而非仅在 DFS 遍历时截断——避免字段声明语义与实际兜底上限(4)不一致而误导审计 / UI。
4. 当 parent grant 已被 revoke 但 freshness 未到达时,reducer 仍 MUST 把它视为 cycle detection 的 ancestor 节点(prevent 攻击者 revoke-then-re-delegate 构造环)。
5. 同一 delegate event 携带的多 child grant(批量委托)MUST 整体 fail-or-pass;部分接受会产生不完整的图结构,reducer MUST NOT 部分接受。

实现 SHOULD 维护 in-memory delegation-graph adjacency cache,以使每次 delegate 校验为 O(depth);冷启动时从 sealed control Events 与可验证 DataEvent 授权引用重建。

### 10.3 Revoke 因果传播

`parent grant` 被 revoke 时，所有 derived child grant **MUST** 在该 revoke 的 causal 后继中失效。具体行为见 [`event-auth-state-resolution.md` §6](./event-auth-state-resolution.md) 委托链 revocation 传播规则；本节只补充: revoke 与 freshness 不一致期间(receiver 已收到 revoke 但未达到 freshness windows),derived child grant 已发起的 in-flight Events 由 reducer 按 §6 fast-path freshness 表判定(parent freshness `unknown` 时 fail closed 适用于高风险 action)。

上游 revoke 的本地可见性优先于 child grant 的 causal 视图：授权解析 `refs[role="parent_grant"]` / `parent_grant_id` 时，reducer MUST 主动查询本地已 accepted 的 grant/revoke index。若任一 ancestor parent grant 在本地已知为 revoked、superseded、expired 或 tombstoned，则 child grant 及依赖它的 Event MUST 立即 `failed_precondition`，`reason="grant_revoked_upstream"`，不得等待 child 的 `prev_refs` 或某个数据面观测 root 自然包含该 revoke。若本地无法确认 parent freshness，则按 §18.2 风险表处理：高风险与跨域 grant 相关 action MUST fail closed，低风险只可进入 pending / limited 模式。

`grant_id` 是授权图的唯一追踪键。所有 reducer-input Event 的 `refs[role="authorized_by"]` MUST 指向 `ck:grant:<uuid>` 或 profile 注册的不可变 grant record id；MUST NOT 指向一次 `ck.self.policy.query.check`（默认 path `/_cokret/self/policy/check`）decision、human role、Event id alias 或当前 membership cell。节点 MUST 为每个 accepted / pending Event 记录 `authorized_by.grant_id[]` 与 grant canonical digest，用于 revoke 后的影响面枚举。revoke 生效后：

1. 该 grant 直接授权的 pending Event MUST fail closed；
2. 该 grant 派生出的 child grant MUST 标记 `revoked_upstream`。child grant 的有效性 **MUST** 取其**所有** parent path freshness 的最严格值（min over paths）：只要有**任一**关键 ancestor 在该 child 的某条 parent path 上为 `revoked` / `superseded` / `expired` / `tombstoned` / freshness `unknown`，整个 child grant 即 **MUST** 降级 fail-closed，**MUST NOT** 因为存在另一条"仍有效的 alternate parent path"而保持有效。实现 **MUST NOT** 把 multi-path delegation 当作可漂白单条 path 撤销的冗余授权；多 path 只增加约束、不放宽约束。child grant 仅当其**每一条** parent path 上的全部关键 ancestor 都仍有效时才保持有效；
3. 依赖该 grant 的 allow cache、policy decision cache、projection shortcut 和 server-side cursor authority MUST 在同一 reducer transaction 内失效；
4. 已 accepted / sealed 的历史 Event 保留审计事实，但后续 snapshot / range completeness / export MUST NOT 再把它作为“当前仍授权”的证据。

## 11. 有效权限集合

Cokret v1 采用 allow-grant + explicit revoke 模型。

也就是说：

- 协议层没有通用 `deny` grant。
- 有效权限集合是所有当前有效 grant 的并集。
- revoke 通过显式 Event 把 grant 从有效集合移出。

## 12. Revocation

撤销必须是显式操作，而不是删除 grant 记录。

示例：

```json
{
  "kind": "ck.capability.revoke",
  "payload": {
    "grant_id": "ck:grant:0196410c-0000-7000-8000-000000000000",
    "reason": "contract ended"
  }
}
```

v1 canonical `ck.capability.revoke` payload MUST 携带顶层 `grant_id`；registry cell_subject 从 `payload.grant_id` 派生。

**撤销的控制面定位与生效切点（normative）**：`ck.capability.revoke` 是控制面 Control Move。其**授权基准**由信封 `seal_basis` 表达（撤销发起者在其控制面链上当时的 Seal basis），payload **MUST NOT** 携带任何 frontier / event-digest 数组（v1 不存在 `revocation_frontier`；与 [`event-auth-state-resolution.md` §5–§6](./event-auth-state-resolution.md) 的 Control Move 信封纪律一致）。撤销的**生效切点**是覆盖该 revoke 的 **accepted Seal**：按 [`event-auth-state-resolution.md` §6.3](./event-auth-state-resolution.md) 的 Seal 接受规则，revoke 的 effect 在其所属 Control Move 被某个 accepted Seal 的 `delta[]` 覆盖并原子应用后才生效；在该 Seal 被接受之前，revoke 不改变有效权限集合。§18.2 的 freshness 是与生效切点**正交**的窗口置信判定（回答"当前 basis 是否够新、足以排除尚未观察到的 revoke"），而非生效切点本身；freshness 为 `stale` / `unknown` 时按 §18.2 风险表 fail-closed，**MUST NOT** 把"未观察到 revoke"当作"未撤销"。该模型与 [`../identity/consent-model.md`](../identity/consent-model.md) 的 consent revoke 完全平行（consent 同为 or_set 控制 cell、revoke 在 `seal_basis` view 下解析、被 accepted Seal 覆盖后生效）。

### 12.1 Grant cell 的确定性收敛（normative）

capability 授权状态投影到 cell family `ck.component.capability.grant.v1`（见 [`registry/event-kind-registry.json`](../../artifacts/registry/event-kind-registry.json) 的 `ck.capability.grant` / `ck.capability.revoke`），`cell_subject` 从 `payload.grant_id` 派生（每个 `grant_id` 一个 cell），`lattice = or_set`；`ck.capability.delegate` 投影到 `ck.component.capability.delegate.v1`（同收敛规则，另以 `refs[role="parent_grant"]` 维护 delegation 链，见 §10）。收敛规则：

- **grant** = 对该 grant cell 的 or_set **add**：add dot = 该 `ck.capability.grant` 事件的 `ck:event:<event_id>:<effect_index>`，value = grant 的 canonical 快照。
- **revoke** = 对**同一** grant cell 的 or_set **remove**，observe 该 grant 的 add dot（与 [`../identity/consent-model.md`](../identity/consent-model.md) 的 consent revoke `observed_dots` 语义一致）。`ck.capability.revoke` 以顶层 `grant_id` 定位目标 cell；reducer **MUST** 在该 revoke Control Move 的 `seal_basis` view 下把目标 grant 的 add dot 解析为合法 add op 后再 supersede。已被 observe-remove 的 add **MUST NOT** 因同 `grant_id` 的后续 re-add / 重放而复活（remove-after-observed-add 为终态）；多 issuer 并发 revoke 同一 grant 收敛于 or_set 的去重语义。
- **有效性** = 该 grant cell or_set join 后仍存活（未被 observed-remove）的 add 所对应的 grant 快照。对 `ck.component.capability.grant.v1` 这一 grant cell 而言，`bottom` 对 or_set **inert**：or_set join 永不产生 ⊥，[`registry/event-kind-registry.json`](../../artifacts/registry/event-kind-registry.json) 中该 cell 的 `bottom = reject` 为 registry 声明的占位值，reducer **MUST NOT** 据其产生任何 reject 语义（与 [`../identity/consent-model.md`](../identity/consent-model.md) 对 consent or_set `bottom` 的 inert 处理一致）；有效权限集合始终由 or_set join 决定。该 inert 规则只适用于 capability / consent 这类普通 observed-remove 集合；`ck.component.moderation_state.v1` 的 `bottom=expose` 是显式领域冲突处理，按 [`policy-server.md` §7.2](./policy-server.md) 的 `moderation_control_split` 规则 fail closed 并暴露冲突状态。
- **GC / tombstone**：已被 sealed 的 grant / revoke 历史保留审计事实（§10.3 第 4 点）；GC 后 cell **MUST** 保留足以判定"该 `grant_id` 当前是否仍授权"的 tombstone，snapshot / range completeness / export **MUST NOT** 把已 revoke 的 grant 再计为"当前仍授权"。

conformance：[`capability-fixture.json`](../../artifacts/fixtures/capability-fixture.json) **MUST** 覆盖 (a) grant → use → revoke → deny 序列、(b) 同一 grant 重复 / 并发 revoke 的幂等去重收敛、(c) revoke 后以同 `grant_id` re-add 仍保持已撤销（终态不复活）。freshness `unknown` 下高风险 action fail-closed 由 §18.2 风险表规范并据其验证。

## 13. Invite、通知与已读状态

invite / notification / read-cursor 等用户可见操作 MUST 由对应 capability action 授权（见下列）；实现 MUST NOT 通过权限模型之外的私有通道授予这些操作。

- 创建 / 取消普通定向 invite 需要 `ck.invite.create` / `ck.invite.cancel`；第三方/token invite 撤销需要 `ck.invite.revoke`
- 接受发给自己的 invite 需要 `ck.invite.accept`
- 写入自己的 `read_cursor` 需要 `ck.read_cursor.advance`（事件 kind 同名）
- 读取 notification 需要 `ck.notification.read`
- `ck.notification.ack` 只应影响自己的派生 inbox 状态

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

- `discover` → `ck.realm.discover`（能否发现对象存在）
- `read_metadata` → `ck.object.read_metadata`（能否看到被撤回消息的元信息）
- `read_content` → `ck.object.read_content`（能否读取附件内容）
- `read_history` → `ck.object.read_history`（能否读取对象 discussion / 历史事件）

## 16. Strand / Discussion 场景下的权限建议

Cokret v1 至少区分：

- 修改 Strand synthesis。
- 开启或关闭 discussion track。
- 管理 Realm 成员（`ck.realm.admin` 管理 `ck.member.state` 写入）或 Circle 成员（`ck.circle.member.manage` / `ck.circle.member.add.others` 管理 `ck.circle.member.state` 写入，见 [`../models/circle.md`](../models/circle.md)）。
- 普通发送消息。
- 编辑自己的消息。
- 编辑任意消息。
- 撤回自己的消息。
- 撤回任意消息。
- 切换 primary track。

这能避免把"能改 Strand"和"能进入 discussion"混成一种权限——Realm-default discussion 按源 Realm capability 判断；若整个 Strand 落在 Circle，则还必须满足该 Circle 的 membership / effective scope 校验。

## 17. 决策执行位置

权限检查 MUST 至少在以下协议边界执行：

- Events API 接收写入时
- Sync Service 分发前
- 受托 search / projection 服务返回结果前
- blob store 下发内容前

声明主客户端、web 客户端或离线编辑 profile 的实现 SHOULD 在本地提交前执行同等语义的预检查，以降低失败回滚和本地 pending 噪声；该预检查是 UX / 性能优化，不能替代上述服务端或 reducer 边界的 MUST 检查，也不能作为接受、分发或下发内容的唯一依据。

## 18. 最小权限判定算法与性能优化

给定一个操作，节点理论上的判定全链路如下：

1. 解析 actor DID。
2. 验证签名链。
3. 查找当时有效 grant 集。
4. 展开 delegation，并执行 cycle detection。
5. 判断 resource selector 是否覆盖 target。
6. 判断 action 是否匹配。
7. 判断 constraints 是否满足。**当多个 grant 同时命中该 `(action, resource)` 时，constraint 求值 MUST 走 [`constraint-schema.md` §15.4](./constraint-schema.md) 的跨 grant 全局合并入口（`evaluate_constraints_across_grants`），任一命中 grant 的 deny / quarantine / require_review 全局生效，MUST NOT 逐 grant 独立求值后取"任一 ALLOWED 即放行"。**
8. 若 grant 或 constraint 要求 claim，拉取并验证 claim / attestation。
9. 判断 claim issuer 是否可信。
10. 判断 claim 是否有效、未过期、未撤销。
11. 若需要 approval，校验 responsible / guardian / controller approval 证据。
12. 应用 revoke 和 superseding 规则。

Facets 不属于独立授权输入。算法 MUST NOT 在上述步骤之外读取 Morph facets、View renderer 或 track profile 来授予、拒绝或升级权限。第 7 步若检查 Realm schema、Morph profile 或 reducer policy，只能读取其中明确声明的字段规则、状态机、RelationProfile 或 policy 条件；MUST NOT 把 facets 本身当作状态机、动作或授权规则。

### 18.1 高频交互的 O(1) 快速路径

在“discussion 消息收发”或“Strand 状态拖拽”等高频交互场景下，声称支持主客户端或 Principal Server profile 的实现 SHOULD 提供 capability 快照缓存或语义等价 fast path。

高频 fast path 典型事件：

- `ck.message.create`
- `ck.reaction.add`
- `ck.strand.update`
- `ck.strand.move`
- `ck.strand.reorder`

Fast path 只能缓存基础 capability 是否允许。Moderation / Policy Server 的 `deny`、`quarantine`、`require_review`、rate limit、legal hold 和 abuse policy 仍 MUST 在写入接收、分发和查询返回前执行。

Capability fast path cache MUST 绑定确定性授权状态，而不是只绑定 subject/action/resource 三元组。每个 cache entry 至少包含：

- `realm_id`、scope / track / object selector、subject DID、action 和 constraint profile。
- `auth_state_digest`：由当前 accepted capability grant/revoke、membership、policy、必要 claim status（包括 condition-selector grant 依赖的 `claim_status_root`）、device/session control seal 和相关 state event canonical digest 计算出的确定性 hash。
- `auth_frontier`：参与该 hash 的 state event head set 或 snapshot frontier。
- 命中的 grant event id、revoke tombstone / superseding event id（如有）、claim status evidence 和过期时间。

除非具体 deployment profile 另行声明可复算的 auth-state canonical encoding，`auth_state_digest` 在跨实现 wire 上是 issuer-local opaque commitment：它绑定 cache entry、snapshot authority binding 或审计记录与某个 `auth_frontier`，但第三方 verifier 的安全判定 MUST 来自按 `auth_frontier` 可取得的 accepted auth state 回放 / 查询结果。换言之，verifier MUST 检查 digest 与 frontier 的自洽性和新鲜度，MUST NOT 把无法逐字重算该 opaque digest 解释为授权通过。

规则：

- 任何影响该 scope 的 accepted grant、revoke、membership、policy、claim status、device/session revoke 或 Realm lifecycle 变化，MUST 立即把对应 cache entry 标记 stale。"立即"指节点接受 DataEvent 或确认控制面 Seal 并更新相关 cell 的同一事务边界内；分布式 fanout 的传播延迟由 §18.2 freshness 检查兜底，**MUST NOT** 作为延迟标记 stale 的理由。**Reducer-derived membership cascade** 也 MUST 触发 cache stale：典型场景是 Realm leave/ban 触发各 Circle membership 自动收敛（见 [`circle.md` §9.1](../models/circle.md)），以及 Circle tombstone 触发对象 scope 失效。这些 cascade 不一定发出独立 `ck.member.state` event，但产生的 cell 变化同样属于"membership 变化"，MUST 触发 cache invalidation。
- **Moderation state cell 与 cache 的关系**：sealed moderation decision（写入 `ck.component.moderation_state.v1`，见 [`policy-server.md` §7.1](./policy-server.md)）**默认不**触发 capability cache invalidation——moderation 是 deny / quarantine 后置层，不是 capability 来源。但若 grant 的 constraint 显式声明 `depends_on_moderation_state=true`（典型场景：moderator role grant 依赖被 moderation cell 标记的 actor 不在其中），则该 cell 的变化 MUST 触发对应 grant cache 失效。grant constraint 默认 `depends_on_moderation_state=false`。
  - **静态 lint 规则（MUST，reducer / schema 强制）**：为防止 silently-stale grant，grant 在写入 / accept 时若满足下列任一条件，`constraints[]` 中 **MUST 显式包含** `depends_on_moderation_state=true`，缺失即 `schema_violation`：
    1. `subject` 是 condition selector 且引用任何 moderation state 字段（例如 `not_in_moderation_set`、`moderation_role_in`、`moderation_status_*`）；
    2. `actions[]` 包含 `ck.moderation.decision` / `ck.moderation.decision.lift` / `ck.realm.moderation_policy` 中的任一项（moderator role grant 几乎总是依赖 moderation cell 决定谁是 moderator）；
    3. `constraints[]` 中存在任何 typed constraint 引用 moderation state cell、moderation queue、moderation report 或 moderation tag。
  - 该 lint 在 `capability-grant.schema.json` 与 grant accept reducer 中静态执行；实现 MUST NOT 接受"默认值省略"的兼容写法。Grant 显式声明 `depends_on_moderation_state=false` 而满足上述条件之一时同样 reject——只允许显式 `true`，从而确保意图可审计。
  - 不在上述条件内的普通 grant（典型如 `ck.strand.update`、`ck.message.create`、组织成员 grant）默认 `depends_on_moderation_state=false`，fast path 不受 moderation cell 失效抖动影响，符合本节"moderation 是后置层"的设计。
  - **条件 2 的保守取舍（normative rationale）**：条件 2 按 `actions[]` 是否含 moderation 写入动作触发，即使 subject 是固定 DID 的 admin / moderator grant（其"谁是 moderator"并不真正依赖 moderation cell）也强制 `depends_on_moderation_state=true`，因而该 grant 的 fast-path cache 会被无关 moderation cell 变化抖动失效。这是**有意的 fail-safe 设计**：lint 是 schema / reducer 层的静态规则，无法廉价区分"固定 DID admin"与"依赖 moderation state 的 condition-selector moderator"，而漏失效（已被 moderation 降权的 moderator 仍走 fast-path allow）的安全代价远高于多失效一次 cache 的性能代价。真正精确依赖 moderation state 的 grant 由条件 1、条件 3 覆盖；条件 2 是对"moderation 动作持有者"的额外保守网，**不收窄**。
- Cache entry 的 `auth_state_digest` 与当前 accepted auth state hash 不一致时，MUST 回退到完整授权判定；MUST NOT 继续用旧 grant 允许新写入。
- 对 subject 为 condition selector 或约束引用外部 claim / attestation 状态的 grant，cache key / cache value MUST 额外绑定 `claim_status_root` 与 `claim_freshness_deadline`。Issuer revoke、claim status root rotation、attestation expiry 或 freshness deadline 过期 MUST 使 cache entry stale；实现 MUST NOT 只因 grant/revoke/membership 未变化就继续使用 fast-path allow。
- 已被 GC 的 grant 仍 MUST 保留足以验证 revoke 的 tombstone、revocation index、snapshot witness 或 state root 证据。实现 MUST NOT 因为 grant payload 已压缩或归档而让旧 cache 重新生效。
- `partial_auth_state`、soft-failed auth chain 或无法确认 revoke freshness 的状态 MUST NOT 生成 allow cache；只能生成 deny / unknown / pending 诊断。
- fast path（capability 快照缓存）**MUST** 只适用于"该 grant 的全部 constraint 的 `evaluation_class` 均为 `stateless` 或 `grant_local`"的 grant；只要 grant 含任一 `external` 或 `realm_state` 类 constraint（见 [`constraint-schema.md` §2.3](./constraint-schema.md) evaluation_class 分类，典型如 `claim_based` / `quota.rate` / `confidentiality` / `field_access` 带 `condition` 等），该 grant 的判定 **MUST** 走完整授权判定，**MUST NOT** 仅凭 fast-path cache 命中放行。该绑定与 §18.1 fast-path cache 的 `auth_state_digest` 失效机制叠加生效，不互相替代。
- 多 Principal Server 部署中，cache TTL 只是额外保险，MUST NOT 替代 revoke fanout、frontier 对账和 `auth_state_digest` 失效。

### 18.2 撤销新鲜度 (Revocation Freshness)

授权判定要回答两个问题：①当前 CBA basis 下，subject 是否被 grant？②该 basis 是否足够新，以至于"还没看到的 revoke"概率足够低？open_set / threshold Notary profile 下 ②不能凭单节点状态独立断言——必须显式建模 freshness 不确定性。

**Freshness 状态分级**：节点对自己当前 frontier 的新鲜度判定 MUST 落入以下三个状态之一：

- `fresh`：节点已观察到控制面 Seal 更新时间在 `freshness_required_ms` 窗口内，或持有 ≥1 受信 notary / witness 在该窗口内签发的 frontier attestation。
- `stale`：上一次控制面 Seal 更新或受信 attestation 超出 `freshness_required_ms` 窗口，但仍小于 `freshness_hard_limit_ms`。
- `unknown`：节点处于网络分区、frontier 来源不可达、notary 长时间无新 Seal、本地时钟与受信时间源 drift 超出 `clock_skew_tolerance_ms`，或上一次控制面 Seal 更新 / 受信 attestation 的年龄 **大于等于** `freshness_hard_limit_ms`。超过 hard limit 的状态 MUST 归入 `unknown`，不得继续按 `stale` 处理。

**`freshness_unknown` ≠ allow**：当判定的状态是 `stale` 或 `unknown` 时，节点 MUST 按动作风险等级强制降级，绝不能因"找不到 revoke 证据"就默认为"未撤销"：

| 动作风险等级 | `fresh` | `stale` | `unknown` |
| --- | --- | --- | --- |
| 高风险（**[`registry/capability-action-registry.json`](../../artifacts/registry/capability-action-registry.json) 中 `risk_tier=high` 的全部已登记动作**，例如 `ck.realm.destroy`、`ck.realm.freeze`、`ck.realm.tombstone`、`ck.capability.revoke`、`ck.realm.admin`、`ck.policy.manage`、`ck.schema.define`、`ck.agent.key.authorize` / `ck.agent.key.rotate` / `ck.agent.key.revoke`、`ck.call.record`、`ck.call.transcribe`、`ck.audit.export` 等；以及按"默认 fail closed"规则被视为高风险的未登记动作） | allow | **MUST fail closed**（`revocation_freshness_unknown`） | **MUST fail closed**（`revocation_freshness_unknown`） |
| 中风险（`ck.strand.update`、`ck.circle.member.manage`、`ck.invite.create`、跨 Realm relation 创建、policy_components 修改） | allow | allow + audit log + 异步 re-check | **MUST fail closed**，可携带 `retry_after_ms` |
| 高频写入 / 本地 pending tier（按本表显式枚举：`ck.message.create`、`ck.reaction.add`、`ck.read_cursor.advance`、`ck.strand.move`、`ck.strand.reorder`） | allow | allow + 加快后台 Seal 同步 | **本地 pending（不对外生效）**：客户端 MAY 在本地 UI 中乐观显示作者自己看到的状态，但 MUST NOT 把该 Event 同步给其他成员、不得 fanout、不得 push notify，直到 freshness 恢复。basis 恢复 fresh 后再做完整 re-validate；validate 失败的本地 pending Event MUST 静默丢弃，不写入 redaction（因为它从未进入共享 accepted set）。 |

> **本表行归属（normative）**：上表三行是 **freshness 分区降级策略**，其成员按本表**显式枚举**确定，与 [`registry/capability-action-registry.json`](../../artifacts/registry/capability-action-registry.json) 的 `risk_tier` 是两个正交轴。`risk_tier` 在本节只治理两件事：(i) **未登记动作**的 freshness fail-closed 默认（registry 缺失该动作 ⇒ 视为 high ⇒ `unknown` 时 fail closed，见 registry_rules）；(ii) 禁止 grant author 通过 grant-side 标签把高风险动作降级（下方 MUST 列表）。因此 `ck.message.create` / `ck.strand.move` / `ck.strand.reorder` 虽在 registry 中为 `risk_tier=medium`，在分区 `unknown` 下仍按本行「本地 pending」处理——这是有意的离线可用性取舍，**不**构成与 `risk_tier` 的冲突；它们不会被静默放行给其他成员，因此不违反 medium 行的「不污染他人」目标。

设计取舍：低风险 `unknown` allow + 后续重放校验在分区下会让恶意 actor 故意制造分区然后高频写入；即使后续 redaction 也已经污染过其他成员的 inbox / notification / 通话邀请。**v1 采用本地 pending 模式**：分区期间作者自己看得见自己的写入（保留 UX），但分区另一侧的成员看不到任何被分区动作影响的内容，分区恢复时被 invalidate 的 Event 直接丢弃，无副作用。

实现 MUST：

- 在 `server/describe.limits` 暴露 `freshness_required_ms`、`freshness_hard_limit_ms`、`clock_skew_tolerance_ms`，让客户端协商。任何 registry 中 `risk_tier=high` 或未登记而按默认规则视为 high 的动作，其 `freshness_required_ms` MUST 严格大于 `2 * clock_skew_tolerance_ms`；否则本地时钟偏差可覆盖整个 freshness window，receiver MUST 把配置视为 `schema_violation` / deployment misconfiguration。默认值：高风险 `freshness_required_ms = 180_000`、`freshness_hard_limit_ms = 300_000`；中风险 `freshness_required_ms = 300_000`、`freshness_hard_limit_ms = 600_000`；clock_skew_tolerance_ms = 60_000。
- 在 `unknown` / `stale` 拒绝响应中返回 `freshness_state`、`last_known_frontier_age_ms`、`notary_status`、`retry_after_ms`，让客户端 UI 区分"被拒绝"和"暂时不能确认"。
- 客户端在低风险 `unknown` 模式下 MUST 在 UI 中标记本地 pending 写入为 `pending_local`（例如灰色发送中状态），并暴露"分区恢复后可能丢弃"的提示。
- MUST NOT 用 cache TTL 静默掩盖 `unknown` 状态。任何高风险动作 fast path 命中后，若 cache entry 的 `auth_state_digest` 对应的 frontier 已超出 `freshness_required_ms`，MUST 从 cache 降级回完整判定。
- MUST NOT 通过把高风险动作降级为中风险（例如把 `ck.capability.revoke` 标记为 "low_risk_followup"）来绕过本表。动作风险等级 MUST 由 [`registry/capability-action-registry.json`](../../artifacts/registry/capability-action-registry.json) 的 `risk_tier` 字段声明，MUST NOT 接受 grant-side override。
- 本地 pending 数量 MUST 按 Realm 维度限制在滚动时间窗口内（默认 ≤ 1000 / Realm / 5 minutes）；同一网络分区 episode 持续超过 5 minutes 时，quota 窗口继续滚动计算，不把整个 episode 合并为单一无限长窗口。超过限额后客户端 SHOULD 转为离线模式提示用户，避免 pending 队列爆炸。

**默认 fail closed**：当实现无法确定动作风险等级、或动作来自尚未注册的 capability action 时，freshness 判定 MUST 默认按高风险处理（`stale` / `unknown` 即拒绝），而不是按低风险放行。这条 default 是为了让任何未来引入的高风险动作在进入 capability registry 前不会被旧实现误判为低风险路径。

## 19. 设计决定

Cokret v1 固定：

- 权限采用 capability 模型。
- Strand、discussion、agent 执行都使用统一 grant 体系；Strand track 不携带独立 access，整个 Strand 通过 Realm-default scope 或 Circle scope 形成单一安全边界。
- `ck.message.revise.own` 与 `ck.message.redact` 分开。
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
- Claim / attestation envelope 使用 `../models/event-and-patch.md` §3 的 Proof、`../identity/identity-handles.md` 的 claim / VC 规则与 §16 的 presentation 规则。

## 附录 B. 与 UCAN / ZCAP 的关系与差异（informative）

> 本附录为 informative 设计背景说明，不构成 normative 约束。它解释 Cokret capability 模型为何采用 grant-as-signed-Event + lattice-revoke，而非 UCAN 风格的 JWT bearer 能力链，并不替换 §2–§12 定义的自有授权模型。

UCAN 与 ZCAP-LD 以可携带的 bearer token / 能力链表达授权：持有者出示一条由 root 经 attenuation 逐级签发的 JWT（或 LD proof）链，验证方就地校验链上签名与 caveat 即可放行，无需中心化状态。这种"无状态 bearer 链"在离线签发与去中心信任路由上很优雅。

Cokret 没有采用该路径，核心原因是 **revoke / attenuation 必须进入可重放的控制面 Seal / cell 收敛与 freshness 判定**：

- Cokret 的 grant 是一条 **signed Event**，进入 reducer 后在 registry cell 上以 lattice 收敛；revoke 同样是 Event（`ck.capability.revoke`），其效果通过 cell 收敛对所有副本可重放、可定序、可审计。授权判定因此能绑定到 DataEvent 的 `seal_ref` 或 Control Move 的 `seal_basis`，并施加 freshness 门槛（见 §18、common-fields freshness 约定）。
- bearer-token 链对**集中收敛的 revocation freshness 支持较弱**:撤销一条已签发的 UCAN/ZCAP 链通常依赖短 TTL、外部 revocation list 或带外吊销服务，验证方无法仅凭链本身判断"此刻是否仍有效",也难以纳入统一的 frontier / freshness 收敛。对一个以可重放事件流为真相源、且需要分区下 fail-closed 的系统，这一点是关键短板。

因此 Cokret 在核心层坚持 grant-as-signed-Event + lattice-revoke,使授权状态与对象状态共享同一套收敛与 freshness 语义。

未来 Cokret MAY 提供单独登记的 UCAN interop profile，把外部 UCAN 作为 claim / attestation 输入桥接进自有模型（外部 UCAN 仅作为 §7 claim/attestation 一类证据被消费，而不替代内生 grant cell）。在该 profile 进入 active conformance 前，实现 MUST NOT 依赖外部 bearer 能力链直接授权。
