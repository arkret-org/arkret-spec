---
title: Capability Model
status: candidate
normative: true
stability: v1
updated: 2026-05-25
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Cokret 的权限模型采用 capability 思路，而不是只依赖成员关系或模糊角色。

这样做的原因是：

- `flow`、`message`、`realm`、`morph`、`view` 的动作集不同。
- Flow 的所有 track（含 `synthesis` 与 `discussion`）共享同一 effective scope（由 `Flow.scope_circle_id` 决定，`null` = Realm-default scope，否则指向同 Realm 的 [Circle](../models/circle.md)）。Flow 永远单一 scope，不存在 per-track 安全边界。
- agent 必须被精细授权。
- 授权变化必须可审计。

## 2. 基本原则

### 2.1 授权主体 SHOULD 是稳定 principal

grant 的 `issuer` 与 `subject` SHOULD 使用 DID。

Handle、邮箱、域名用户名等人类可读标识 MUST NOT 作为权限主体主键。

### 2.2 权限必须显式表达

不要依赖以下隐式假设：

- 进入 Realm 就拥有全部能力。
- 能编辑 Flow synthesis 就一定能在 discussion 里发消息，除非有效 access policy 明确继承并授予该动作。
- discussion moderator 天然拥有全量 Flow 管理权。

### 2.3 权限判定基于当时有效的 capability 集

操作是否合法，应由该时点有效 grant 集决定。

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
  "issuer": "did:web:acme.example.com",
  "subject": "did:web:agent.copy.example.com",
  "actions": [
    "ck.flow.read",
    "ck.flow.update",
    "ck.message.create",
    "ck.morph.read",
    "ck.morph.update"
  ],
  "resources": [
    {
      "kind": "object",
      "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
      "object_type": "flow",
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
      "fields_write_allow": ["metadata.title", "metadata.summary", "content", "metadata.fields.review_status"]
    }
  ],
  "proofs": [
    {
      "kind": "detached_jws",
      "alg": "EdDSA",
      "verification_method": "did:web:acme.example.com#device-1",
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

## 4. Resource Selector

Cokret v1 支持以下 `kind`：

- `realm`
- `space`
- `flow`
- `message`
- `morph`
- `object`
- `relation`
- `event`
- `actor`
- `view`
- `schema`
- `policy`
- `invite`
- `notification`
- `read_cursor`
- `blob`

资源选择器应把 Space（`kind=board/list/...`）、Flow track、Morph type 和 Relation kind 表达为 canonical resource selector + typed constraint，而不是把它们当成新的 selector kind。Flow 的业务语义通过 schema/profile、`metadata.fields`、Relation、labels、Morph type 或 facet 约束表达，不放在顶层字段上。

## 5. 动作集合

动作名称与标准 event kind / operation id 的语义对齐，使用 `ck.<domain>.<action>` 点分记法。Wire 层 `actions[]` 字段 MUST 是具体动作字符串；实现 **MUST NOT 接受任何 wildcard / segment 通配**（含 `*`、`ck.<domain>.*`、`ck.<domain>.<sub>.*`）。`capability-grant.schema.json` 已用 pattern 静态拒绝 wildcard。

机器可读的 canonical 动作集（含 `risk_tier`、`required_constraints`、`required_evaluator_checks`、`target_event_kinds`、`event_mapping_kind`、`profile`）MUST 来自 [`registry/capability-action-registry.json`](../../artifacts/registry/capability-action-registry.json)；本节的散文枚举只是该 registry 的 human-readable 镜像，新增 / 修改动作 MUST 先改 `contract-catalog.json` 的 `capability_action_registry` 节并跑 `tools/artifact_pipeline.py generate`，再回流到本节。

裸名动作（例如 `realm.upgrade` 或 `realm.link.manage`）MUST NOT 被接受。`ck.realm.admin` 覆盖普通 Realm 管理动作，但 MUST NOT 自动覆盖 E2EE key export、legal hold bypass 或审计降级——后者 MUST 在 grant `actions[]` 中显式列出对应 high-risk 动作。

### 5.0 Action ↔ Event kind 偏离类别（normative reference）

绝大多数 action 与其 `target_event_kinds` 单一同名映射（`ck.flow.create` action ↔ `ck.flow.create` event）。当存在偏离时，授权决策、IAM 工具与 audit 解析 MUST 以 `capability-action-registry.json` 的 `target_event_kinds` 为准，而不是用 action 字符串拆解推断 event kind。**偏离限定为以下四类**，任何其它类型的偏离 **MUST NOT 被引入**；先前的"verb-noun 桥"类已于 v3 收敛废除（历史别名与 verb-noun 桥废除记录见[附录 A](#附录-a-action-命名迁移历史informative)）：

| 类别 | 形态 | 标准示例 |
| --- | --- | --- |
| **聚合 admin 动作** | 一个 action 覆盖多条 Realm policy facet event kinds | `ck.realm.admin` → registry 中声明的 Realm policy facet events；`ck.policy.manage` → `ck.policy.*` 与 `ck.realm.policy_*` 系列 |
| **polymorphic 对象动作** | 一个 action 同时覆盖 Flow / Morph / Space 等同语义 event | `ck.object.archive` → `{ck.flow.archive, ck.morph.archive}`；`ck.object.restore` → `{ck.flow.restore, ck.morph.restore, ck.space.restore}`；`ck.object.stage.set` → `{ck.flow.stage.set, ck.morph.stage.set}` |
| **scope 后缀变体** | 同一 event，授权按 self vs others / target subset 分粒度 | `ck.message.revise.own` → `ck.message.revise`；`ck.message.redact.own` → `ck.message.redact`；`ck.flow.watch.set.others` → `ck.flow.watch.set` |
| **保留旧 wire 命名（`event_mapping_kind="wire_compat_grandfather"`）** | action 用收敛后命名、event kind 因已发布的 wire bytes 不可改名而保留旧前缀 / 旧 punctuation。本类**冻结**，新增条目 **MUST NOT 落入此类**：所有现存条目都 MUST 在 registry 中声明 `grandfathered_since` | `ck.agent.session.*` → `ck.agent.protocol_session.*`（namespace 折叠）；`ck.morph.schema.migrate` → `ck.morph.schema_migrate`（separator 差异）；`ck.flow.tracks.manage` → `ck.flow.tracks.update`（umbrella verb vs 具体 verb）；`ck.call.configure_media_service` → `ck.realm.media_service`（跨 namespace 语义） |

`ck.mls.commit` action → `{ck.mls.commit, ck.mls.commit_failed}`、`ck.message.redact` → `{ck.message.redact, ck.redaction}`、`ck.moderation.appeal.review` → `{ck.moderation.appeal.review, ck.moderation.appeal.decision, ck.moderation.appeal.close}` 等"同一 action 同时覆盖正常 event 与诊断 / 派生 event"的情况落在**聚合 admin 动作**类别，并以 registry `target_event_kinds` 为准。

新增动作 MUST 默认与 event kind 同名；只有上述四类之一的明确理由可以偏离，且必须在 `contract-catalog.json` 内显式声明 `target_event_kinds` 与 `event_mapping_kind`。**新增偏离类别 MUST 在 RFC 中讨论后才能加表项；MUST NOT 通过 lint 例外或注释方式悄悄引入新桥**。

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

### 5.2 Flow 与工作流动作

- `ck.flow.create`
- `ck.flow.read`
- `ck.flow.update`
- `ck.flow.archive`
- `ck.flow.restore`
- `ck.flow.move`
- `ck.flow.reorder`
- `ck.flow.tracks.manage`（Flow tracks map 写入入口：启用 / 关闭 track、切换 primary、修改 track profile，对应 event `ck.flow.tracks.update`。这是该 action 的权威定义；§5.3 仅交叉引用）
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
- `ck.morph.create`(默认 required constraint:`morph_type_allow`)
- `ck.morph.update`(默认 required constraint:`fields_write_allow`)

Flow 权限只覆盖 Flow 自身字段、track 配置和 position / relation 管理。Message 正文权限按 Flow 的 effective scope 判断：`Flow.scope_circle_id=null` 时使用 Realm-default capability；`scope_circle_id` 指向 Circle 时使用该 [Circle](../models/circle.md) scope 的 capability + Circle membership 两层 AND（详见 [`circle.md` §8](../models/circle.md)）。

若 Circle membership cell 在当前 Anchor frontier 下为 `⊥`（`fsm, bottom=reject`），上述两层 AND 的 membership 分支 MUST fail closed：授权结果为 deny，后续依赖该 cell 的 Move MUST 返回 `failed_bottom`（`reason=cell_in_bottom_state`），而 `failed_precondition` 仅用于 predicate 本身不成立（cell 持有明确 value 但 predicate 求值为 false）的情形；实现 MUST NOT 把 `⊥` 当作非成员、空成员集或任一候选 membership 状态来继续授权。

Morph 权限粒度与 Flow 平行(`ck.morph.read` / `ck.morph.create` / `ck.morph.update` 对应 `ck.flow.read` / `ck.flow.create` / `ck.flow.update`),通过 `morph_type_allow` constraint 进一步限定可创建或操作的 `morph_type`。

### 5.3 Discussion 与消息动作

- `ck.event.read`
- `ck.message.create`
- `ck.message.mention.broadcast`（high risk；允许在 `ck.message.create` / `ck.message.revise` 中新增 audience mention，例如 `@all` / `@here`。必须同时持有普通消息写入授权，且 grant MUST 携带 rate-limit quota（`max_operations` + `period`），Realm / Circle policy MUST 声明允许的 audience 与 `max_recipients`；`@here` 映射为 `audience="flow_engaged"` 且不使用 presence / online 状态；详见 [`../models/flow-and-message.md` §9.4.3](../models/flow-and-message.md)）
- `ck.message.revise`
- `ck.message.revise.own`
- `ck.message.redact`
- `ck.message.redact.own`
- `ck.reaction.add`
- `ck.reaction.remove`
- `ck.flow.tracks.manage`（管理 track 启用 / primary / profile；权威定义见 §5.2，此处仅交叉引用，target=`ck.flow.tracks.update`）
- `ck.flow.watch.set`（写入自己的 watch 订阅，target=`ck.flow.watch.set`；详见 [`../models/flow-and-message.md` §8](../models/flow-and-message.md)）
- `ck.flow.watch.set.others`（high risk；为他人写入 `level ∈ {mentions_only, participating, all}` 的 watch 订阅；MUST NOT 写入 `muted` 或 `level_public=true`，target=`ck.flow.watch.set`；详见 [`../models/flow-and-message.md` §8.4](../models/flow-and-message.md)）

### 5.4 管理动作

- `ck.circle.create`（创建 Circle；默认不进入普通成员 bundle）
- `ck.circle.manage`（管理 Circle lifecycle / metadata；MUST 通过 `allowed_circle_ids` 或 `kind="circle"` selector 收窄）
- `ck.circle.member.add`（自助加入 / 接受邀请 / 自助离开，受 Circle join_rule 与父 Realm membership gate 约束）
- `ck.circle.member.manage`（邀请、移除或 ban 他人；MUST 通过 `allowed_circle_ids` 或 `kind="circle"` selector 收窄）
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
- `ck.flow.admin`
- `ck.realm.notification.audit`（读取完整 watch 状态含 `muted`；MUST 与 `ck.audit.accessed` 同时持有，详见 [`../models/flow-and-message.md` §8.5](../models/flow-and-message.md)）
- `ck.schema.define`
- `ck.schema.update`
- `ck.capability.grant`
- `ck.capability.delegate`
- `ck.capability.revoke`
- `ck.agent.key.authorize`（high risk；授权 agent key，target=`ck.agent.key.authorize`）
- `ck.agent.key.rotate`（high risk；轮换 agent key，target=`ck.agent.key.rotate`）
- `ck.agent.key.revoke`（high risk；撤销 agent key，target=`ck.agent.key.revoke`）
- `ck.agent.provision`(CKP-0008;aggregate admin action,`target_event_kinds=[ck.profile.create, ck.identity.accountability_grant, ck.agent.key.authorize, ck.capability.grant]`,migration_group=`ckp_0008_agent_provisioning`)
- `ck.agent.pause`(controller-only;target=`ck.agent.pause`)
- `ck.agent.resume`(controller-only;target=`ck.agent.resume`)
- `ck.agent.deactivate`(controller-only,terminal;target=`ck.agent.deactivate`,fan-out 见 [`../identity/account-lifecycle.md` §9.1](../identity/account-lifecycle.md))
- `ck.agent.draft.propose`(agent-initiated draft;target=`ck.agent.draft.propose`,wire_scope=`actor_private_event`)
- `ck.agent.action_request`(agent-initiated action request;target=`ck.agent.action_request`)
- `ck.agent.action_approve`(controller-only;target=`ck.agent.action_approve`)
- `ck.agent.action_reject`(controller-only;target=`ck.agent.action_reject`)
- `ck.agent.sidecar_thread.ensure`(CKP-0009;aggregate admin action,`target_event_kinds=[ck.circle.create, ck.circle.member.state, ck.flow.create, ck.relation.create]`,migration_group=`ckp_0009_sidecar_ensure`。Controller-private projection 写入(`ck.agent.sidecar_projection.v1`)不属于此 grant 集合)
- `ck.agent.sidecar_thread.write`(profile action;`target_event_kinds=[ck.message.create]`,resource 必须限定 sidecar private Flow)
- `ck.agent.sidecar_thread.publish`(profile action;target event kinds 由最终发布目标决定，至少包括 `ck.message.create`，受 reply-as-agent / act-on-behalf attribution 规则约束)
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
- `ck.moderation.decision`（写入 anchored moderation state cell；详见 [`policy-server.md` §7.1](./policy-server.md)）
- `ck.moderation.decision.lift`（解除已 anchored 的 moderation 决策）

### 5.5 服务动作

- `ck.events.query`
- `ck.events.subscribe`
- `ck.account.subscribe`
- `ck.account.describe`
- `ck.snapshot.head`
- `ck.blob.upload`
- `ck.blob.get`
- `ck.blob.head`
- `ck.call.configure_media_service`
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

v1 不再注册独立的 `ck.mls.epoch` event；每个 group 的当前 epoch 由 accepted `ck.mls.commit` payload 中的 `next_epoch` 和对应 `ck.component.mls_epoch.v1` cell reducer 结果直接表达，没有"推进 epoch"这个独立可授权动作。

Audit action 只授权受控审计 applet / release service 执行绑定、阶段性 session、成员通知、sealed historical release、审计视图读取或审计材料导出。审计 applet 不是 MLS group 成员，也不会因 capability 获得实时消息 fanout；E2EE 合规 release 必须走 active `ck.audit.applet_binding`、`ck.audit.session.*`、`ck.audit.release` 和 RYW receipt。普通 Realm/Circle 治理举报不使用这些 action，举报只路由给 scoped 管理员 / moderator。

### 5.6 人类界面与个人状态动作

- `ck.read_cursor.advance`（capability action; 对应 event kind 同名 `ck.read_cursor.advance`）
- `ck.notification.read`
- `ck.notification.ack`
- `ck.invite.accept`

## 6. Constraints

Cokret v1 支持：

- `expires_at`
- `not_before`
- `fields_write_allow`
- `fields_write_deny`
- `realm_kind_allow`（v1 reserved / deprecated no-op：v1 中所有 Realm 同属一种安全边界，无 kind 区分,producer SHOULD NOT 发送；receiver MUST 忽略；详见 [`constraint-schema.md`](./constraint-schema.md) §5）
- `space_kind_allow`
- `morph_type_allow`
- `facet_allow`
- `allowed_flow_ids`
- `allowed_space_ids`
- `allowed_view_ids`
- `allowed_tracks`
- `relation_kind_allow`
- `allowed_from_container_refs`
- `allowed_to_container_refs`
- `visibility_allow`
- `blob_max_bytes`
- `blob_presign_max_ttl_seconds`
- `blob_presign_scope`
- `max_artifact_bytes`
- `allowed_data_classes`
- `allowed_endpoints`
- `encryption_required`
- `message_edit_window`
- `message_redact_window`
- `allow_redact_after_window`
- `max_delegation_depth`
- `rate_limit`
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

上表中的扁平名称是 `constraint-schema.md` 中 typed constraint 对象的 shorthand 别名。完整约束结构和求值规则以 `constraint-schema.md` 为准。

### 6.1 Effective Validity Window

Grant 的 wire schema 同时允许顶层 `not_before` / `expires_at` 和 `constraints[]` 中的 temporal `not_before` / `expires_at`。它们不是两套独立有效期；授权解析 MUST 先归一化为单一 effective window：

```text
effective_not_before = max(grant.not_before?, temporal.not_before[]?)
effective_expires_at = min(grant.expires_at?, temporal.expires_at[]?)
```

缺省的 lower bound 视为无下限；缺省的 upper bound 视为无上限，但高风险、agent、service、delegated grant 仍按本文风险规则 MUST 有有限 `effective_expires_at`。若归一化后 `effective_not_before >= effective_expires_at`，reducer MUST `failed_precondition`，`reason="grant_validity_window_empty"`。授权日志、缓存 key、delegation narrowing 和 revoke freshness 判断都 MUST 使用 effective window，MUST NOT 分别按顶层字段和 temporal constraint 做两次不一致判断。

`discussion` 不是独立资源类型。需要限制 discussion track 时，使用 `object_type_allow=["flow"]` 和 `allowed_tracks=["discussion"]`；MUST NOT 引入按 track profile 名称授权的 v1 grant 字段。`tracks.<name>.profile` 只是 Flow track 的语义/profile hint，MUST NOT 单独授予读取、发送或成员权限。

Facet 只在 grant 显式包含 `facet_allow` / `facet_deny` 这类 typed constraint 时作为范围收窄条件参与第 7 步 constraints 判断；未声明 facet constraint 的 grant 不会因为目标对象具有 `stateful`、`assignable` 或其他 facet 而自动允许或自动拒绝。`facet=stateful` 不引入独立授权动作：修改 Morph `state` 仍 MUST 命中 `ck.morph.update` 或 profile 注册的更具体 action、目标 resource selector、`morph_type_allow`、字段写约束、schema state transition policy 和其他有效 constraints。若 grant 允许 `ck.morph.update` 且没有字段/类型/策略拒绝，缺少 `facet_allow=["stateful"]` 本身 MUST NOT 成为拒绝理由；若 grant 显式声明 `facet_allow` 且目标 facets 不匹配，则 constraint 不满足。

`requires_claims[]` 中每个 claim 条目 MUST 明确绑定 `issuer` 或 `trusted_issuers[]`；`subject_matches_actor` 未出现时按 `true` 求值。实现 MUST NOT 接受只有 `claim_type` 而无发行者边界的 claim grant。

| 扁平名称 | Typed `constraint_type` | `subtype` | 对应字段 |
|----------|------------------------|----------|----------|
| `expires_at` | `temporal` | — | `expires_at` |
| `not_before` | `temporal` | — | `not_before` |
| `fields_write_allow` | `field_access` | — | `fields_write_allow` |
| `fields_write_deny` | `field_access` | — | `fields_write_deny` |
| `realm_kind_allow` | `type_restriction` | — | `realm_kind_allow`（v1 reserved / deprecated no-op；producer SHOULD NOT 发送） |
| `space_kind_allow` | `type_restriction` | — | `space_kind_allow`（限定 Space 的 kind，例如 board / list / swimlane）|
| `morph_type_allow` | `type_restriction` | — | `morph_type_allow` |
| `facet_allow` | `type_restriction` | — | `facet_allow` |
| `allowed_flow_ids` | `scope_limitation` | — | `allowed_flow_ids` |
| `allowed_space_ids` | `scope_limitation` | — | `allowed_space_ids` |
| `allowed_view_ids` | `scope_limitation` | — | `allowed_view_ids` |
| `allowed_tracks` | `scope_limitation` | — | `allowed_tracks` |
| `relation_kind_allow` | `scope_limitation` | — | `relation_kind_allow` |
| `allowed_from_container_refs` | `scope_limitation` | — | `allowed_from_container_refs` |
| `allowed_to_container_refs` | `scope_limitation` | — | `allowed_to_container_refs` |
| `visibility_allow` | `confidentiality` | `visibility` | `visibility_allow` |
| `blob_max_bytes` | `quota` | `resource` | `blob_max_bytes` |
| `blob_presign_max_ttl_seconds` | `quota` | `resource` | `blob_presign_max_ttl_seconds` |
| `blob_presign_scope` | `scope_limitation` | — | `blob_presign_scope` |
| `max_artifact_bytes` | `quota` | `resource` | `max_artifact_bytes` |
| `allowed_data_classes` | `scope_limitation` | — | `allowed_data_classes` |
| `allowed_endpoints` | `scope_limitation` | — | `allowed_endpoints` |
| `encryption_required` | `confidentiality` | `encryption` | `encryption_required` |
| `message_edit_window` | `temporal` | `edit_window` | `message_edit_window` |
| `message_redact_window` | `temporal` | `redact_window` | `message_redact_window` |
| `allow_redact_after_window` | `temporal` | `edit_window` / `redact_window` | `allow_redact_after_window`（窗口修饰符，见 [`constraint-schema.md` §14.2](./constraint-schema.md)） |
| `max_delegation_depth` | `delegation_control` | — | `max_delegation_depth` |
| `rate_limit` | `quota` | `rate` | `max_operations`, `period` |
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
system/human -> `ck.flow.update` 或 `ck.morph.update`
```

## 9. Agent 安全授权

给 agent 授权时 MUST 默认：

- 只授予明确 Realm / Flow / Message / Morph / View 范围。
- 只授予所需动作。
- 只授予有限时效。
- 尽量限制可写字段、可写 track 和可写 Morph 类型。
- 对 high action 按 action registry 与 profile 要求 controller / responsible actor approval。

高风险模式包括：

- 给 agent 长期全 Realm 管理权。
- 让 agent 直接继承 human owner 全权限。
- 不设过期时间。
- 不保留 agent 执行审计链。
- 高风险操作不需要 approval。

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
| `effective_expires_at` | MUST 存在且 ≤ `parent.effective_expires_at`(无限期 parent 在 v1 中不允许；若 parent 未声明 finite effective upper bound,delegate 时 child MUST 自带 `expires_at` 或 temporal `expires_at`，且 `effective_expires_at` ≤ `now + max_delegation_lifetime_ms`,默认 24 小时) |
| `max_delegation_depth` | MUST ≤ `parent.max_delegation_depth - 1` |
| `actions[]` | MUST ⊆ `parent.actions[]` |
| `resources[]` | MUST 是 `parent.resources[]` 的 selector-narrowing 子集(见 `resource-selector-grammar.md`) |
| `constraints[]` | MUST 至少包含 parent 的所有 deny / require / quarantine constraints; MAY 增加更严格的 allow constraints |

违反任何一项 reducer MUST 返回 `failed_precondition` reason=`delegation_expiry_widening`(对窗口),或 `schema_violation`(对 actions / resources / constraints 越界)。

**固定 anchor 防滚动续期（normative）**：仅靠"child 自带 `expires_at` ≤ `now + max_delegation_lifetime_ms`"不足以约束无限期 parent——parent 可以每 `max_delegation_lifetime_ms` 自我 re-delegate 一次，每次都让 child 取得一个新的 `now + 24h`，从而把"无 finite upper bound 的 parent"漂白成事实无限期的 child 链。为关闭该面，无 finite effective upper bound 的 parent grant **MUST NOT** 直接作为 delegation source；任何从它派生的 child 链 MUST 绑定一个**固定 `delegation_expiry_anchor`**，且整条链每一级的 `effective_expires_at` **MUST** ≤ `delegation_expiry_anchor`，re-delegate **MUST NOT** 刷新该 anchor：

- 若 parent grant 自身有 finite `effective_expires_at`，则 `delegation_expiry_anchor = parent.effective_expires_at`（与表中收窄规则一致）。
- 若 parent grant 无 finite effective upper bound，则其第一次作为 delegation source 时，reducer **MUST** 冻结 `delegation_expiry_anchor = first_delegation_anchored_at + max_delegation_lifetime_ms`（默认 24 小时），并把该 anchor 作为不可变 child-chain 属性记录（`refs[role="delegation_expiry_anchor"]` 或 profile 声明的等价字段）。
- 同一无限期 parent 的后续 re-delegate **MUST** 复用同一 `delegation_expiry_anchor`，**MUST NOT** 用新的 `now` 重新计算；child 的 `effective_expires_at` 超过该 anchor 时 reducer **MUST** 返回 `failed_precondition` reason=`delegation_expiry_widening`。

本规则与 §8 "delegated grant MUST 有有限 expiry" 对齐：任何 child 链最终 expiry 都 MUST 可追溯到一个不随 re-delegate 推移的固定时点。

### 10.2 Cycle detection（normative）

`ck.capability.delegate` event 的 `refs[]` 中包含 `role="parent_grant"` 引用作为父 grant id。Reducer **MUST** 把所有已 anchored 的 delegation 关系视为有向图，节点是 `grant_id`,边是 `(parent_grant_id, child_grant_id)`,并按下列算法做 cycle detection:

Delegation Move SHOULD 同时记录签发时点的 parent `auth_state_digest` / `auth_frontier`（可放入 `refs[role="auth_frontier"]`、grant audit metadata 或 profile 声明的等价字段）。该记录不替代实时 revoke/freshness 校验，但用于审计 child grant 是基于哪个 parent policy/auth frontier 派生的；缺失时实现仍 MUST 重新按当前 frontier 验证，MUST NOT 把 child grant 当作不可追溯授权。

1. 收到新的 `ck.capability.delegate(child_grant_id, parent_grant_id)` 时,reducer 沿 parent chain 做 DFS,直到遇到无 parent 的 root grant 或深度 = `max_delegation_depth_observed`。
2. 若在 DFS 过程中发现新 `child_grant_id` 出现在已访问 ancestor 集合中(即新 grant 会 close 一条循环 path),reducer **MUST** 拒绝整条 delegation chain 上的本 Event,reason=`delegation_cycle`,MUST NOT 接受任何子 grant 即便它们单看 valid。
3. DFS 深度上限 default 64,与 `actor_seq` causal chain 上限一致(`scalability-constraints.md`);超过深度的 chain 视作病态,reducer MUST 退化为拒绝。
4. 当 parent grant 已被 revoke 但 freshness 未到达时,reducer 仍 MUST 把它视为 cycle detection 的 ancestor 节点(prevent 攻击者 revoke-then-re-delegate 构造环)。
5. 同一 delegate event 携带的多 child grant(批量委托)MUST 整体 fail-or-pass;部分接受会产生不完整的图结构,reducer MUST NOT 部分接受。

实现 SHOULD 维护 in-memory delegation-graph adjacency cache,以使每次 delegate 校验为 O(depth);冷启动时从 anchored Events 重建。

### 10.3 Revoke 因果传播

`parent grant` 被 revoke 时，所有 derived child grant **MUST** 在该 revoke 的 causal 后继中失效。具体行为见 [`event-auth-state-resolution.md` §6](./event-auth-state-resolution.md) 委托链 revocation 传播规则；本节只补充: revoke 与 freshness 不一致期间(receiver 已收到 revoke 但未达到 freshness windows),derived child grant 已发起的 in-flight Events 由 reducer 按 §6 fast-path freshness 表判定(parent freshness `unknown` 时 fail closed 适用于高风险 action)。

上游 revoke 的本地可见性优先于 child grant 的 causal 视图：授权解析 `refs[role="parent_grant"]` / `parent_grant_id` 时，reducer MUST 主动查询本地已 accepted 的 grant/revoke index。若任一 ancestor parent grant 在本地已知为 revoked、superseded、expired 或 tombstoned，则 child grant 及依赖它的 Move MUST 立即 `failed_precondition`，`reason="grant_revoked_upstream"`，不得等待 child 的 `prev_refs` 或 Anchor frontier 自然包含该 revoke。若本地无法确认 parent freshness，则按 §18.2 风险表处理：高风险与跨域 grant 相关 action MUST fail closed，低风险只可进入 pending / limited 模式。

`grant_id` 是授权图的唯一追踪键。所有 reducer-input Event 的 `refs[role="authorized_by"]` MUST 指向 `ck:grant:<uuid>` 或 profile 注册的不可变 grant record id；MUST NOT 指向一次 `/_cokret/self/policy/check` decision、human role、Event id alias 或当前 membership cell。节点 MUST 为每个 accepted / pending Event 记录 `authorized_by.grant_id[]` 与 grant canonical digest，用于 revoke 后的影响面枚举。revoke 生效后：

1. 该 grant 直接授权的 pending Event MUST fail closed；
2. 该 grant 派生出的 child grant MUST 标记 `revoked_upstream`。child grant 的有效性 **MUST** 取其**所有** parent path freshness 的最严格值（min over paths）：只要有**任一**关键 ancestor 在该 child 的某条 parent path 上为 `revoked` / `superseded` / `expired` / `tombstoned` / freshness `unknown`，整个 child grant 即 **MUST** 降级 fail-closed，**MUST NOT** 因为存在另一条"仍有效的 alternate parent path"而保持有效。实现 **MUST NOT** 把 multi-path delegation 当作可漂白单条 path 撤销的冗余授权；多 path 只增加约束、不放宽约束。child grant 仅当其**每一条** parent path 上的全部关键 ancestor 都仍有效时才保持有效；
3. 依赖该 grant 的 allow cache、policy decision cache、projection shortcut 和 server-side cursor authority MUST 在同一 reducer transaction 内失效；
4. 已 anchored 的历史 Event 保留审计事实，但后续 snapshot / range completeness / export MUST NOT 再把它作为“当前仍授权”的证据。

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

`grant_ref` MAY 作为 legacy payload 的兼容别名出现，但 v1 canonical `ck.capability.revoke` payload MUST 携带顶层 `grant_id`；registry cell_subject 从 `payload.grant_id` 派生。

## 13. Invite、通知与已读状态

invite / notification / read-cursor 等用户可见操作 MUST 由对应 capability action 授权（见下列）；实现 MUST NOT 通过权限模型之外的私有通道授予这些操作。

- 创建 / 取消 invite 需要 `ck.invite.create` / `ck.invite.revoke`
- 接受发给自己的 invite 需要 `ck.invite.accept`
- 写入自己的 `read_cursor` 需要 `ck.read_cursor.advance`（事件 kind 同名）
- 读取 notification 需要 `ck.notification.read`
- `ck.notification.ack` 只应影响自己的派生 inbox 状态

## 14. Role 只是 bundle

产品层可以提供：

- `space_admin`
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

## 16. Flow / Discussion 场景下的权限建议

Cokret v1 至少区分：

- 修改 Flow synthesis。
- 开启或关闭 discussion track。
- 管理 Realm 成员（`ck.realm.admin` 管理 `ck.member.state` 写入）或 Circle 成员（`ck.circle.member.manage` / `ck.circle.member.add.others` 管理 `ck.circle.member.state` 写入，见 [`../models/circle.md`](../models/circle.md)）。
- 普通发送消息。
- 编辑自己的消息。
- 编辑任意消息。
- 撤回自己的消息。
- 撤回任意消息。
- 切换 primary track。

这能避免把"能改 Flow"和"能进入 discussion"混成一种权限——Realm-default discussion 按源 Realm capability 判断；若整个 Flow 落在 Circle，则还必须满足该 Circle 的 membership / effective scope 校验。

## 17. 决策执行位置

权限检查不应只在客户端发生。

权限检查 MUST 至少在以下位置执行：

- client 预检查
- Events API 接收写入时
- Sync Service 分发前
- 受托 search / projection 服务返回结果前
- blob store 下发内容前

## 18. 最小权限判定算法与性能优化

给定一个操作，节点理论上的判定全链路如下：

1. 解析 actor DID。
2. 验证签名链。
3. 查找当时有效 grant 集。
4. 展开 delegation，并执行 cycle detection。
5. 判断 resource selector 是否覆盖 target。
6. 判断 action 是否匹配。
7. 判断 constraints 是否满足。
8. 若 grant 或 constraint 要求 claim，拉取并验证 claim / attestation。
9. 判断 claim issuer 是否可信。
10. 判断 claim 是否有效、未过期、未撤销。
11. 若需要 approval，校验 responsible / guardian / controller approval 证据。
12. 应用 revoke 和 superseding 规则。

Facets 不属于独立授权输入。算法 MUST NOT 在上述步骤之外读取 Morph facets、View renderer 或 track profile 来授予、拒绝或升级权限。第 7 步若检查 Realm schema、Morph profile 或 reducer policy，只能读取其中明确声明的字段规则、状态机、RelationProfile 或 policy 条件；MUST NOT 把 facets 本身当作状态机、动作或授权规则。

### 18.1 高频交互的 O(1) 快速路径

在“discussion 消息收发”或“Flow 状态拖拽”等高频交互场景下，声称支持主客户端或 Principal Server profile 的实现 SHOULD 提供 capability 快照缓存或语义等价 fast path。

高频 fast path 典型事件：

- `ck.message.create`
- `ck.reaction.add`
- `ck.flow.update`
- `ck.flow.move`
- `ck.flow.reorder`

Fast path 只能缓存基础 capability 是否允许。Moderation / Policy Server 的 `deny`、`quarantine`、`require_review`、rate limit、legal hold 和 abuse policy 仍 MUST 在写入接收、分发和查询返回前执行。

Capability fast path cache MUST 绑定确定性授权状态，而不是只绑定 subject/action/resource 三元组。每个 cache entry 至少包含：

- `realm_id`、scope / track / object selector、subject DID、action 和 constraint profile。
- `auth_state_digest`：由当前 accepted capability grant/revoke、membership、policy、必要 claim status（包括 condition-selector grant 依赖的 `claim_status_root`）、device/session control checkpoint 和相关 state event canonical digest 计算出的确定性 hash。
- `auth_frontier`：参与该 hash 的 state event head set 或 snapshot frontier。
- 命中的 grant event id、revoke tombstone / superseding event id（如有）、claim status evidence 和过期时间。

规则：

- 任何影响该 scope 的 accepted grant、revoke、membership、policy、claim status、device/session revoke 或 Realm lifecycle 变化，MUST 立即把对应 cache entry 标记 stale。"立即"指节点本地 reducer 在 `apply_anchor` 完成的同一事务边界内；分布式 fanout 的传播延迟由 §18.2 freshness 检查兜底，**MUST NOT** 作为延迟标记 stale 的理由。**Reducer-derived membership cascade** 也 MUST 触发 cache stale：典型场景是 Realm leave/ban 触发各 Circle membership 自动收敛（见 [`circle.md` §9.1](../models/circle.md)），以及 Circle tombstone 触发对象 scope 失效。这些 cascade 不一定发出独立 `ck.member.state` event，但产生的 cell 变化同样属于"membership 变化"，MUST 触发 cache invalidation。
- **Moderation state cell 与 cache 的关系**：anchored moderation decision（写入 `ck.component.moderation_state.v1`，见 [`policy-server.md` §7.1](./policy-server.md)）**默认不**触发 capability cache invalidation——moderation 是 deny / quarantine 后置层，不是 capability 来源。但若 grant 的 constraint 显式声明 `depends_on_moderation_state=true`（典型场景：moderator role grant 依赖被 moderation cell 标记的 actor 不在其中），则该 cell 的变化 MUST 触发对应 grant cache 失效。grant constraint 默认 `depends_on_moderation_state=false`。
  - **静态 lint 规则（MUST，reducer / schema 强制）**：为防止 silently-stale grant，grant 在写入 / accept 时若满足下列任一条件，`constraints[]` 中 **MUST 显式包含** `depends_on_moderation_state=true`，缺失即 `schema_violation`：
    1. `subject` 是 condition selector 且引用任何 moderation state 字段（例如 `not_in_moderation_set`、`moderation_role_in`、`moderation_status_*`）；
    2. `actions[]` 包含 `ck.moderation.decision` / `ck.moderation.decision.lift` / `ck.realm.moderation_policy` 中的任一项（moderator role grant 几乎总是依赖 moderation cell 决定谁是 moderator）；
    3. `constraints[]` 中存在任何 typed constraint 引用 moderation state cell、moderation queue、moderation report 或 moderation tag。
  - 该 lint 在 `capability-grant.schema.json` 与 grant accept reducer 中静态执行；实现 MUST NOT 接受"默认值省略"的兼容写法。Grant 显式声明 `depends_on_moderation_state=false` 而满足上述条件之一时同样 reject——只允许显式 `true`，从而确保意图可审计。
  - 不在上述条件内的普通 grant（典型如 `ck.flow.update`、`ck.message.create`、组织成员 grant）默认 `depends_on_moderation_state=false`，fast path 不受 moderation cell 失效抖动影响，符合本节"moderation 是后置层"的设计。
- Cache entry 的 `auth_state_digest` 与当前 accepted auth state hash 不一致时，MUST 回退到完整授权判定；MUST NOT 继续用旧 grant 允许新写入。
- 对 subject 为 condition selector 或约束引用外部 claim / attestation 状态的 grant，cache key / cache value MUST 额外绑定 `claim_status_root` 与 `claim_freshness_deadline`。Issuer revoke、claim status root rotation、attestation expiry 或 freshness deadline 过期 MUST 使 cache entry stale；实现 MUST NOT 只因 grant/revoke/membership 未变化就继续使用 fast-path allow。
- 已被 GC 的 grant 仍 MUST 保留足以验证 revoke 的 tombstone、revocation index、snapshot witness 或 state root 证据。实现 MUST NOT 因为 grant payload 已压缩或归档而让旧 cache 重新生效。
- `partial_auth_state`、soft-failed auth chain 或无法确认 revoke freshness 的状态 MUST NOT 生成 allow cache；只能生成 deny / unknown / pending 诊断。
- fast path（capability 快照缓存）**MUST** 只适用于"该 grant 的全部 constraint 的 `evaluation_class` 均为 `stateless` 或 `grant_local`"的 grant；只要 grant 含任一 `external` 或 `realm_state` 类 constraint（见 [`constraint-schema.md` §2.3](./constraint-schema.md) evaluation_class 分类，典型如 `claim_based` / `quota.rate` / `confidentiality` / `field_access` 带 `condition` 等），该 grant 的判定 **MUST** 走完整授权判定，**MUST NOT** 仅凭 fast-path cache 命中放行。该绑定与 §18.1 fast-path cache 的 `auth_state_digest` 失效机制叠加生效，不互相替代。
- 多 Principal Server 部署中，cache TTL 只是额外保险，MUST NOT 替代 revoke fanout、frontier 对账和 `auth_state_digest` 失效。

### 18.2 撤销新鲜度 (Revocation Freshness)

授权判定要回答两个问题：①当前已同步的 frontier 下，subject 是否被 grant？②该 frontier 是否足够新，以至于"还没看到的 revoke"概率足够低？open_set / threshold anchor profile 下 ②不能凭单节点状态独立断言——必须显式建模 freshness 不确定性。

**Freshness 状态分级**：节点对自己当前 frontier 的新鲜度判定 MUST 落入以下三个状态之一：

- `fresh`：节点已观察到 anchor frontier 更新时间在 `freshness_required_ms` 窗口内，或持有 ≥1 受信 anchorer / witness 在该窗口内签发的 frontier attestation。
- `stale`：上一次 anchor frontier 更新或受信 attestation 超出 `freshness_required_ms` 窗口，但仍小于 `freshness_hard_limit_ms`。
- `unknown`：节点处于网络分区、frontier 来源不可达、anchorer 长时间无新签发，或本地时钟与受信时间源 drift 超出 `clock_skew_tolerance_ms`。

**`freshness_unknown` ≠ allow**：当判定的状态是 `stale` 或 `unknown` 时，节点 MUST 按动作风险等级强制降级，绝不能因"找不到 revoke 证据"就默认为"未撤销"：

| 动作风险等级 | `fresh` | `stale` | `unknown` |
| --- | --- | --- | --- |
| 高风险（`ck.realm.destroy`、`ck.capability.revoke`、`ck.realm.admin`、`ck.policy.manage`、E2EE key export、legal hold bypass、跨域 grant、sovereign export） | allow | **MUST fail closed**（`revocation_freshness_unknown`） | **MUST fail closed**（`revocation_freshness_unknown`） |
| 中风险（`ck.flow.update`、`ck.circle.member.manage`、`ck.invite.create`、跨 Realm relation 创建、policy_components 修改） | allow | allow + audit log + 异步 re-check | **MUST fail closed**，可携带 `retry_after_ms` |
| 高频写入 / 本地 pending tier（按本表显式枚举：`ck.message.create`、`ck.reaction.add`、`ck.read_cursor.advance`、`ck.flow.move`、`ck.flow.reorder`） | allow | allow + 加快后台 frontier 同步 | **本地 pending（不对外生效）**：客户端 MAY 在本地 UI 中乐观显示作者自己看到的状态，但 MUST NOT 把该 Move 同步给其他成员、不得 fanout、不得 push notify、不得进入 anchor pipeline 直到 freshness 恢复。frontier 恢复 fresh 后再做完整 re-validate；validate 失败的本地 pending Move MUST 静默丢弃，不写入 redaction（因为它从未 anchored）。 |

> **本表行归属（normative）**：上表三行是 **freshness 分区降级策略**，其成员按本表**显式枚举**确定，与 [`registry/capability-action-registry.json`](../../artifacts/registry/capability-action-registry.json) 的 `risk_tier` 是两个正交轴。`risk_tier` 在本节只治理两件事：(i) **未登记动作**的 freshness fail-closed 默认（registry 缺失该动作 ⇒ 视为 high ⇒ `unknown` 时 fail closed，见 registry_rules）；(ii) 禁止 grant author 通过 grant-side 标签把高风险动作降级（下方 MUST 列表）。因此 `ck.message.create` / `ck.flow.move` / `ck.flow.reorder` 虽在 registry 中为 `risk_tier=medium`，在分区 `unknown` 下仍按本行「本地 pending」处理——这是有意的离线可用性取舍，**不**构成与 `risk_tier` 的冲突；它们不会被静默放行给其他成员，因此不违反 medium 行的「不污染他人」目标。

设计取舍：低风险 `unknown` allow + 后续重放校验在分区下会让恶意 actor 故意制造分区然后高频写入；即使后续 redaction 也已经污染过其他成员的 inbox / notification / 通话邀请。**v1 采用本地 pending 模式**：分区期间作者自己看得见自己的写入（保留 UX），但分区另一侧的成员看不到任何被分区动作影响的内容，分区恢复时被 invalidate 的 Move 直接丢弃，无副作用。

实现 MUST：

- 在 `server/describe.limits` 暴露 `freshness_required_ms`、`freshness_hard_limit_ms`、`clock_skew_tolerance_ms`，让客户端协商。任何 high-risk / cross-domain / delegated grant 相关动作的 `freshness_required_ms` MUST 严格大于 `2 * clock_skew_tolerance_ms`；否则本地时钟偏差可覆盖整个 freshness window，receiver MUST 把配置视为 `schema_violation` / deployment misconfiguration。默认值：高风险 `freshness_required_ms = 180_000`、`freshness_hard_limit_ms = 300_000`；中风险 `freshness_required_ms = 300_000`；clock_skew_tolerance_ms = 60_000。
- 在 `unknown` / `stale` 拒绝响应中返回 `freshness_state`、`last_known_frontier_age_ms`、`anchorer_status`、`retry_after_ms`，让客户端 UI 区分"被拒绝"和"暂时不能确认"。
- 客户端在低风险 `unknown` 模式下 MUST 在 UI 中标记本地 pending 写入为 `pending_local`（例如灰色发送中状态），并暴露"分区恢复后可能丢弃"的提示。
- MUST NOT 用 cache TTL 静默掩盖 `unknown` 状态。任何高风险动作 fast path 命中后，若 cache entry 的 `auth_state_digest` 对应的 frontier 已超出 `freshness_required_ms`，MUST 从 cache 降级回完整判定。
- MUST NOT 通过把高风险动作降级为中风险（例如把 `ck.capability.revoke` 标记为 "low_risk_followup"）来绕过本表。动作风险等级 MUST 由 [`registry/capability-action-registry.json`](../../artifacts/registry/capability-action-registry.json) 的 `risk_tier` 字段声明，MUST NOT 接受 grant-side override。
- 单个分区窗口内允许的本地 pending 数量 MUST 限制（默认 ≤ 1000 / Realm / 5 minutes），超过后客户端 SHOULD 转为离线模式提示用户，避免 pending 队列爆炸。

**默认 fail closed**：当实现无法确定动作风险等级、或动作来自尚未注册的 capability action 时，freshness 判定 MUST 默认按高风险处理（`stale` / `unknown` 即拒绝），而不是按低风险放行。这条 default 是为了让任何未来引入的高风险动作在进入 capability registry 前不会被旧实现误判为低风险路径。

## 19. 设计决定

Cokret v1 固定：

- 权限采用 capability 模型。
- Flow、discussion、agent 执行都使用统一 grant 体系；Flow track 不携带独立 access，整个 Flow 通过 Realm-default scope 或 Circle scope 形成单一安全边界。
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
- 多个 grant 命中时，允许动作取并集，但约束按最严格规则相交。
- Moderation policy MUST NOT 凭空授予 capability。
- Approval proof 与 proposal 状态机由本文件、`event-auth-state-resolution.md` 和 conformance vectors 固定。
- Claim / attestation envelope 使用 `../models/event-and-patch.md` §3 的 Proof、`../identity/identity-handles.md` 的 claim / VC 规则与 §16 的 presentation 规则。

## 附录 A. Action 命名迁移历史（informative）

> 本附录为 informative 迁移历史记录，不构成 normative 约束。当前 normative 规则是：action↔event 以 registry `target_event_kinds` 为准（见 §5、§5.0）。

#### verb-noun 桥的废除（历史迁移记录，2026-05-24）

历史上 v1 早期为 action 名加上动词后缀（`.manage` / `.modify` / `create_` 前缀等）以保持"action 为动词"惯例，导致与 event kind 产生 6 处 verb-noun 桥；这些桥强迫每个 IAM 工具维护一张翻译表。

**当前 v1 canonical 规则：action 名 MUST 与其 target event kind 同名。** 早期草案曾存在 6 处 verb-noun 桥，已机械收敛回 event kind 形态（历史迁移见 `renames.json.migration_group: verb_noun_bridge_collapse`）：

| 旧 action（已禁止，hard_reject） | 现行 canonical action | target event kind |
| --- | --- | --- |
| ~~`ck.invite.create_third_party`~~ | `ck.invite.third_party` | `ck.invite.third_party` |
| ~~`ck.policy.rule.manage`~~ | `ck.policy.rule` | `ck.policy.rule` |
| ~~`ck.policy.action.manage`~~ | `ck.policy.action` | `ck.policy.action` |
| ~~`ck.realm.link.manage`~~ | `ck.realm.link` | `ck.realm.link` |
| ~~`ck.realm.plaintext_visible_services.modify`~~ | `ck.realm.plaintext_visible_services` | `ck.realm.plaintext_visible_services` |
| ~~`ck.realm.moderate`~~ | `ck.realm.moderation_policy` | `ck.realm.moderation_policy` |

权衡：这放弃了"action 都是动词"的惯例换取"action 与 event kind 同名"的更强不变量。IAM 直接以 event kind 字符串作为 grant `actions[]` 元素，零翻译；动词形态由 capabilities.md prose 表达（例如 prose 描述"该 capability 授权写入 ck.invite.third_party 邀请事件"）。

剩余"保留旧 wire 命名"类（agent.protocol_session / morph.schema_migrate / flow.tracks.update / realm.media_service）的 event kind 已发布且无法机械收敛，所以保留为冻结的 grandfather 桥；新条目 MUST NOT 落入此类。

## 附录 B. 与 UCAN / ZCAP 的关系与差异（informative）

> 本附录为 informative 设计背景说明，不构成 normative 约束。它解释 Cokret capability 模型为何采用 grant-as-signed-Event + lattice-revoke，而非 UCAN 风格的 JWT bearer 能力链，并不替换 §2–§12 定义的自有授权模型。

UCAN 与 ZCAP-LD 以可携带的 bearer token / 能力链表达授权：持有者出示一条由 root 经 attenuation 逐级签发的 JWT（或 LD proof）链，验证方就地校验链上签名与 caveat 即可放行，无需中心化状态。这种"无状态 bearer 链"在离线签发与去中心信任路由上很优雅。

Cokret 没有采用该路径，核心原因是 **revoke / attenuation 必须进入可重放的 Anchor / cell 收敛与 freshness 判定**：

- Cokret 的 grant 是一条 **signed Event**，进入 reducer 后在 registry cell 上以 lattice 收敛；revoke 同样是 Event（`ck.capability.revoke`），其效果通过 cell 收敛对所有副本可重放、可定序、可审计。授权判定因此能绑定到具体 Anchor frontier，并施加 freshness 门槛（见 §18、common-fields freshness 约定）。
- bearer-token 链对**集中收敛的 revocation freshness 支持较弱**:撤销一条已签发的 UCAN/ZCAP 链通常依赖短 TTL、外部 revocation list 或带外吊销服务，验证方无法仅凭链本身判断"此刻是否仍有效",也难以纳入统一的 frontier / freshness 收敛。对一个以可重放事件流为真相源、且需要分区下 fail-closed 的系统，这一点是关键短板。

因此 Cokret 在核心层坚持 grant-as-signed-Event + lattice-revoke,使授权状态与对象状态共享同一套收敛与 freshness 语义。

未来 Cokret MAY 提供 `ck.profile.ucan_interop.v1`,把外部 UCAN 作为 claim / attestation 输入桥接进自有模型（外部 UCAN 仅作为 §7 claim/attestation 一类证据被消费，而不替代内生 grant cell）。该 profile 标记为 staging extension / 未来工作，不在 v1 核心 normative 范围内；在其落地前，实现 MUST NOT 依赖外部 bearer 能力链直接授权。
