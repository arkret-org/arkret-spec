---
cxp: CXP-0007
title: Circle — intra-Realm cryptographic sub-boundary primitive
normative: false
stability: v1
updated: 2026-05-25
status: accepted
created: 2026-05-25
authors:
  - chris@acroidea.com
merged_into: spec/v1/zh/models/circle.md
---

> **Status: accepted, merged into v1 normative spec on 2026-05-25.**
>
> Normative entry point: [`spec/v1/zh/models/circle.md`](../zh/models/circle.md). Schema artifact: [`spec/v1/artifacts/schemas/circle.schema.json`](../artifacts/schemas/circle.schema.json). The `Flow.discussion_realm_ref` field is removed; see [`forbidden-wire-fields.json`](../artifacts/registry/forbidden-wire-fields.json) entry `discussion_realm_ref` and [`renames.json`](../artifacts/registry/renames.json) `cxp_0007_circle_introduction` migration group. CHANGELOG entry under 2026-05-25.
>
> This proposal file is retained as historical design rationale. Future updates to the Circle primitive MUST land directly on normative files, not here.

## 1. Summary

引入一等对象 **`ck:circle:`**(信任圈),作为 Realm 内的**密码学子边界**:拥有独立 MLS group、独立 key epoch、独立 history key eligibility、Realm membership 的真子集成员,但不持有 federation identity 或 policy server。对象通过 `scope_circle_id` 引用 Circle 表达"窄于 Realm 的加密可见性圈"。**一个 Flow 永远只有一个 encryption scope**,不再支持 per-track 安全边界。

同时**删除 `Flow.discussion_realm_ref`** —— Flow 不允许跨两个安全边界。需要"宽 synthesis + 窄 discussion"的场景统一用**两个 Flow + Relation 连接**的形态表达(一个 public Flow,一个 Circle-scoped Flow)。

非目标:Circle **不是** access-filter / ACL segment 的新名字,也不是 Realm 的"默认加密圈"。若实现只需要授权窄化但不需要独立密钥材料,应使用现有 Group / capability constraint / resource selector;不得声明 Circle。Realm 自身仍拥有 **Realm-default encryption scope**;Circle 只表示 Realm 内更窄的额外 MLS scope。

## 2. Motivation

### 2.1 当前 spec 的抽象漏失

当前 [`architecture.md` §2.0](../zh/overview/architecture.md) 容器选型表只有三档:Realm(全套安全边界)、Space(零边界,纯导航)、Flow(协作单元)。中间档"**Realm 内的密码学子圈**"被刻意省略,导致:

- [`flow-and-message.md` §5](../zh/models/flow-and-message.md) 为"Flow 的 discussion 需要独立访问域"专门开了 `discussion_realm_ref` 单点补丁,让一个 Flow 跨两个 Realm 存在,从而**打破了"一对象一安全边界"的清爽不变量**。spec 因此被迫发明 §5.0.1 跨 Realm lifecycle 级联表、§8.9 跨 Realm watch 重校验、改绑禁令等补丁规则。
- [`realm-and-space.md` §2.2](../zh/models/realm-and-space.md):"实现 MAY 在同一 Realm 中声明辅助 MLS group" —— 默认承认子 MLS group 是合理存在的,但没有 normativize。
- [`realm-and-space.md` §2.1](../zh/models/realm-and-space.md):"强保密差异通过切分 Realm 表达" —— 把所有"想要密码学子圈"的需求都推到"开新 Realm"路径上,带上 federation identity、policy server、capability registry 整套机器。

这等于把 Realm 原语同时承担两个本质不同的概念:**federation/identity boundary** 与 **cryptographic access circle**。本提案的核心是把后者拆出来作为独立原语,同时**彻底清掉**导致"一 Flow 跨两 Realm" 的 `discussion_realm_ref` 补丁 —— 让"一对象一安全边界" 成为协议级硬不变量。

### 2.2 同构需求被迫升级为完整 Realm

下列需求在当前 spec 下没有 Realm 之外的解,被迫每个开一个真 Realm:

- HR / 法务 / security ops 想在公司 Realm 内有独立 E2EE 圈
- 一个 Board 上的某条 List 整体只对子团队可见
- 一组相关 Flow(不只是讨论)整体限定可见成员
- 临时 incident war room
- 跨 Flow 的机密线索板(同一组人讨论 N 个 Flow)

每条需求都背 federation identity / policy / MLS lifecycle 的全套开销,但它们语义上明明是**同组织内的子单元**。

### 2.3 外部对照

- Matrix / MLS deployments: room 或 subgroup 是 encryption/access scope(类比 Circle),homeserver / deployment route 是 federation boundary(类比 Realm)。两层概念清晰分离。
- Slack: workspace ≈ Realm,private channel ≈ 产品层的 scoped audience;Circle 只采纳其中"子圈"产品语义,但在协议层要求独立 MLS 密钥边界。
- Element/MLS deployments: "subgroup" / "encryption scope" 概念已是行业共识。

Cokret v1 把两层压成一个 Realm 原语,是当前协议设计中的最大单点遗漏。

## 3. Specification

### 3.1 `ck:circle:` 对象

Schema id: `cx.schema.circle.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:circle` | `ck:circle:<uuid>`(UUIDv7) | Circle ID。 |
| `schema` | yes | `cx.schema.circle.v1` | 固定。 | 对象 schema。 |
| `realm_id` | yes | `id:realm` | create-locked;Circle 永远属于一个 Realm,不可改绑。 | 归属 Realm(父安全/联邦边界)。 |
| `title` | yes | `string` | 1..256 chars。 | 人类可读名称。 |
| `summary` | no | `string` | ≤2048 chars。 | 简短说明(渲染在 banner / 详情)。 |
| `display` | yes | `object` | 见 §3.2。 | **跨客户端一致**的视觉身份字段;只对 `directory_visibility` 允许的 actor 投影。 |
| `directory_visibility` | yes | `enum(members, realm_members)` | 默认 `members`。 | Circle 元数据可发现性。`members` 时非成员不得看到 title / display / member_count;`realm_members` 仅披露目录元数据,不授予事件或历史访问。 |
| `join_rule` | yes | `enum(invite, request, open)` | 默认 `invite`。 | Circle 加入规则。`open` 仅允许父 Realm active member 自助加入;`request` 需要 profile 定义申请/批准流程;`invite` 只能由 Circle 管理员加入或邀请。 |
| `history_visibility` | yes | `enum(world_readable, shared, invited, joined, restricted)` | 默认 `invited`。语义沿用 [`event-auth-state-resolution.md` §6](../zh/authz/event-auth-state-resolution.md)。 | Circle 自己的历史可见性,但 effective visibility **不得宽于父 Realm 当前 policy floor**。 |
| `metadata_encryption_floor` | no | `enum(content_only, minimal_encrypted, full_encrypted)` | 省略时继承父 Realm floor。 | Circle 内对象的 metadata 加密下限;只能收紧,不得放宽父 Realm floor。 |
| `encryption_profile` | yes | `enum(mls_rfc9420, ...)` | create-locked。v1 仅允许 `mls_rfc9420`;enum 形态预留未来 MLS 版本 / PQ-MLS 扩展位。Circle 必须拥有独立 MLS group;不得复用 Realm-default MLS group 或从其导出密钥。 | 加密形态。 |
| `mls_group_ref` | yes | `id:mls` | 由 `cx.circle.create` reducer 派生,scope 绑定 `(realm_id, circle_id)`。 | 独立 MLS group 引用。 |
| `parent_circle_ref` | n/a | — | **不存在**。Circle 平面化,不允许嵌套(见 §3.6)。 | — |
| `state` | yes | `enum(active, archived, tombstoned)` | 同 common-fields §5;tombstoned 不可逆。 | 生命周期。 |
| `state_changed_at` | conditional | `timestamp` | `state != active` 时必填。 | 最近一次 state 转换时间。 |
| 公共字段 | — | — | `created_by` / `created_at` / `updated_by` / `updated_at` | 同 common-fields §3。 |

Circle v1 不提供 `plaintext_inherit` 或 "authorization-only Circle"。这条边界是故意的:access-filter 能力已经由 Group、capability constraint 与 resource selector 覆盖;把未加密隔离的对象命名为 Circle 会让客户端与用户误以为存在密码学隔离。

### 3.2 `display` 字段(标准化视觉身份)

跨客户端一致的 UI 表达是 Circle 安全模型的必要条件(见 §6 UX 论证):

| 子字段 | 必填 | 类型 | 约束 |
| --- | --- | --- | --- |
| `short_name` | yes | `string` | `^[A-Z][A-Za-z0-9 _-]{0,23}$`;在 `(realm_id, short_name)` 上 reducer 强制唯一(case-insensitive)。 |
| `color_token` | yes | `string` | 从受控 palette 选;v1 palette: `{slate, red, orange, amber, yellow, lime, green, emerald, teal, cyan, sky, blue, indigo, violet, fuchsia, pink, gray_high_contrast}`。客户端 MUST 映射 token → 主题颜色(浅/深/高对比),**不**得自行重分配 token。 |
| `symbol` | yes | `object` | `{emoji?: string, glyph?: enum}`;`glyph` 从受控集 ~24 个 icon(lock/shield/eye/diamond/...);二选一。 |

**颜色 token 与 symbol 必须在 spec 受控集中**,目的是同一 Circle 在 Alice 与 Bob 的客户端上呈现一致视觉,否则跨设备社会工程攻击成立。

### 3.3 Event 家族

| event kind | reducer_input | payload 形态 | 说明 |
| --- | --- | --- | --- |
| `cx.circle.create` | yes | full object | 创建 Circle,同时初始化独立 MLS group 与 epoch 0 governance binding。 |
| `cx.circle.update` | yes | `cx.patch.v1`(path 不含 `realm_id` / `encryption_profile`) | 改 title / summary / display / directory_visibility / join_rule / history_visibility。 |
| `cx.circle.archive` | yes | object_lifecycle_payload | active → archived。 |
| `cx.circle.restore` | yes | object_lifecycle_payload | archived → active。 |
| `cx.circle.tombstone` | yes | object_lifecycle_payload | terminal;触发 §3.7 cascade。 |
| `cx.circle.member.state` | yes | `{circle_id, actor_id, membership: invited\|active\|left\|banned, ...}` | 平行 `cx.member.state`,但 reducer 先校验 actor 已是父 Realm `active` member。 |
| `cx.circle.anchor_commit` | reducer-derived | `{circle_id, sub_anchor_head_digest, epoch}` | Circle sub-anchor 周期性向 Realm Anchor 提交不透明 commitment(§3.9)。 |

### 3.4 对象 scope 表达

新增字段(跨多个现有对象):

```
Flow.scope_circle_id             : id:circle | null       # null = Realm-default encryption scope
Message.effective_scope    : reducer-stamped,immutable tagged scope
Event.effective_scope      : reducer-stamped,immutable tagged scope,进入 envelope/AAD/sub-anchor
Space.scope_circle_id            : id:circle | null       # Space 自身 metadata / scoped structural relation 的可见性 scope
Space.default_scope_circle_id    : id:circle | null       # 在该 Space 新建 Flow 的默认 scope(hint,非强制)
Space.child_scope_policy   : object                  # 子资源 placement/encryption floor,见 §3.4.2
Morph.scope_circle_id            : id:circle | null        # null = Realm-default encryption scope
```

**关键约束:Flow 永远只有一个 effective encryption scope**。不存在 per-track scope —— 整个 Flow(synthesis、discussion、其他 track)共享同一安全边界,要么都在 Realm-default,要么都在某个 Circle。

reducer 规则:

- `scope_circle_id` 引用的 Circle MUST `realm_id` 与对象 `realm_id` 一致;否则 `schema_violation`(`reason="circle_realm_mismatch"`)。
- `scope_circle_id` 引用的 Circle MUST `state=active`;否则 `failed_precondition`(`reason="circle_not_active"`)。
- `scope_circle_id=null` 不表示"没有 scope";它表示 Realm-default encryption scope。Reducer MUST 把它物化为 tagged `effective_scope = {kind:"realm", realm_id}`。
- `scope_circle_id=ck:circle:...` MUST 物化为 tagged `effective_scope = {kind:"circle", realm_id, circle_id}`。
- Reducer 在接受每个 event 时 MUST 固化 `effective_scope`。该值进入 Event envelope、E2EE AAD、MLS governance binding 输入、Anchor/sub-anchor leaf,后续 `scope_circle_id` 改绑不得重解释旧 event。
- Effective history visibility = 父 Realm policy floor 与 Circle `history_visibility` 的更严格者。Circle MAY 收紧父 Realm,不得放宽父 Realm 的隐私/合规下限。
- 改绑 `scope_circle_id` 默认 reducer 拒绝(`failed_precondition` `reason="scope_rebind_forbidden"`);profile MAY 允许,但 MUST audit-paired high-risk update。所有已存在 Message / 子内容保留其写入时的 `effective_scope` 与旧 scope MLS;新内容才进新 scope。客户端 MUST 把切分前后历史分段展示。
- Structural Relation / position cell 的 `effective_scope` **MUST 不宽于参与端点中最窄的 scope**(即:取参与端点 scope 集合中最严格者作为关系事实自身的 scope)。具体例:`public Board (Realm-default)` 包含 `private Flow (Circle=HR-Conf)` 时,`contains` 关系事实与其 position cell 的 `effective_scope = Circle:HR-Conf`,**不是** Realm-default;非 Circle 成员看不到该 containment 关系、看不到 private Flow 的 rank/position,也看不到 board 上"此处有隐藏项"的可枚举元数据(否则等于把 Circle 内容数量泄露给 Realm 全员)。

`effective_scope` wire shape:

```json
{ "kind": "realm", "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000" }
```

```json
{
  "kind": "circle",
  "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
  "circle_id": "ck:circle:0196419c-0000-7000-8000-000000000000"
}
```

**Space 三个 scope 相关字段语义辨析**(实现易混点):

| 字段 | 影响对象 | 强制性 | 说明 |
| --- | --- | --- | --- |
| `Space.scope_circle_id` | Space 对象自身的 metadata 与 structural relation facts | reducer-enforced | Space 自身的 title / parent / rank / contains 事实落在该 Circle scope;**不**使 Space 成为安全边界,Space 仍是 authorization-transparent 容器,只是它的 metadata 被某 Circle 加密。 |
| `Space.default_scope_circle_id` | 在该 Space 下**新建**的子 Flow / 子 Space | hint(可被显式覆盖) | 客户端默认填入该值,actor 仍可在 create payload 中显式提供另一 `scope_circle_id`。不强制。 |
| `Space.child_scope_policy` | 任何 placement / move 进入该 Space 的子对象 | reducer-enforced | `allow_any` / `require_e2ee` / `require_same_scope` / `require_scope_circle_id` 之一,见 §3.4.2。是真正的"该 Space 只接受这种 scope 的子对象"硬约束。 |

实现常见错误:把 `default_scope_circle_id` 当成约束,或把 `scope_circle_id` 与 `default_scope_circle_id` 混用。三者各司其职,**不可**互相替代。

### 3.4.1 Realm-default scope 与加密覆盖范围

Realm **不会**自动创建默认 Circle。Realm-default encryption scope 是 Realm 自身的 MLS / plaintext / external 加密上下文:

| `effective_scope.kind` | 由什么承载密钥 | 何时使用 |
| --- | --- | --- |
| `realm` | `Realm.encryption_profile` 指定的 Realm-default group / external provider / plaintext mode | `scope_circle_id=null` |
| `circle` | Circle 独立 MLS group | `scope_circle_id` 指向 Circle |

`Realm.encryption_profile="mls_rfc9420"` 只说明使用 MLS 作为加密机制,**不**说明哪些 Cokret 字段进入密文。加密覆盖范围由 Realm policy floor 独立声明:

| policy field | enum | 说明 |
| --- | --- | --- |
| `content_encryption_floor` | `allow_plaintext` / `e2ee_required` | `e2ee_required` 时,Flow / Message / Morph / Blob content 的 `effective_scope` MUST 是 MLS-backed:Realm-default MLS 或 Circle MLS。 |
| `metadata_encryption_profile` | `content_only` / `minimal_encrypted` / `full_encrypted` | 既有 Realm policy 字段;本提案明确其作为 Realm-wide metadata 加密下限,不得被 Circle、Space 或对象 profile 放宽。 |

`metadata_encryption_profile` 语义:

| value | 明文允许范围 | 必须加密范围 |
| --- | --- | --- |
| `content_only` | Realm / scope 路由字段、object id/kind、必要 causal refs、Flow / Message metadata、Space parent / rank 等结构 metadata | Message / Morph / Flow content、附件正文、明确标注 encrypted 的字段 |
| `minimal_encrypted` | 路由所需 `realm_id`、`effective_scope.kind`、不可逆 routing digest、policy-required subject、必要 causal refs、Flow `tracks`、`stage` / `state` | 用户可读 `metadata.title` / `metadata.summary` / `metadata.fields`、Message `metadata.fields`、mention / reply excerpt、search token、关系预览、附件文件名 |
| `full_encrypted` | 仅 envelope routing stub、opaque refs、policy/audit 必需的不可逆 commitment | 绝大多数应用 metadata、可逆索引材料、展示标签、结构标题、关系摘要 |

Effective metadata profile = max(parent Realm `metadata_encryption_profile`, Circle `metadata_encryption_floor` if present, Space `child_scope_policy.metadata_encryption_floor` if in placement context, object profile requirement)。比较顺序为 `content_only < minimal_encrypted < full_encrypted`;任何写入若低于 effective profile MUST `failed_precondition`(`reason="metadata_encryption_floor_violation"`)。

### 3.4.2 Space child scope policy

Space 不拥有 membership / policy server / MLS group;`Space.scope_circle_id` 只是让 Space 自身 metadata 与 structural relation facts 落入某个 existing encryption scope。为了表达"这个 Space 下不允许 plaintext Flow"或"这个 List 只能放 HR Circle 对象",Space MAY 声明 placement policy:

| field | enum / type | 说明 |
| --- | --- | --- |
| `child_scope_policy.kind` | `allow_any` / `require_e2ee` / `require_same_scope` / `require_scope_circle_id` | 子资源 scope 约束。 |
| `child_scope_policy.scope_circle_id` | `id:circle` | `kind=require_scope_circle_id` 时必填。 |
| `child_scope_policy.metadata_encryption_floor` | `content_only` / `minimal_encrypted` / `full_encrypted` | 可选,对该 Space 下新建 / 移入对象施加更严格 metadata floor。 |

Reducer MUST 在 `cx.flow.create`、`cx.flow.move`、`cx.space.parent`、structural `contains` projection 写入时检查 effective Space policy:

- `allow_any`:不额外限制。
- `require_e2ee`:子资源 `effective_scope` 必须 MLS-backed。
- `require_same_scope`:子资源 `effective_scope` 必须等于 Space 自身 `effective_scope`。
- `require_scope_circle_id`:子资源 `scope_circle_id` 必须等于指定 Circle。

`Space.default_scope_circle_id` 只是创建默认值,不是强制约束;强制约束必须用 `child_scope_policy` 表达。

### 3.4.3 "宽 synthesis + 窄 discussion" 场景如何表达

旧 `discussion_realm_ref` 服务的核心场景是"Flow 公开可见,但讨论只对小圈可见"。本提案下统一用 **两个 Flow + Relation** 表达,不再有 per-track 安全边界:

```
Flow F_public  (scope_circle_id = null)              ← 公开 anchor Flow,承载 metadata.title / metadata.summary / stage / metadata.fields
Flow F_private (scope_circle_id = ck:circle:HR-Conf) ← Circle 内 Flow,承载敏感讨论与决策细节
F_private --confidential_discussion_of--> F_public
```

客户端 UI MAY 把这两个 Flow 在视觉上"组合显示"(同卡片标题区 + 切换 tab),但协议层它们是**两个独立对象**,各自有独立的:
- 时间线、消息历史
- 成员、MLS group(F_public 用 Realm-default,F_private 用 Circle MLS)
- watch cell、stage、生命周期
- 投影裁剪规则(无 Circle 成员的 Realm 成员只看到 F_public,看不到 F_private 的存在或活动元数据,符合 §3.8 投递不变量)

`confidential_discussion_of` 是标准 weak-semantic Relation kind,关系事实 SHOULD 存放在 `F_private` 的 Circle scope 内。这样 private 成员能从 private Flow 回到 public anchor;非 Circle 成员不会在 public Flow 上看到"存在一个私密讨论"的可枚举边。

此模式的代价是用户需要显式创建两个 Flow,而不是一个 Flow 配置两层 scope。收益是协议层**没有任何对象跨越两个安全边界**,所有 cross-boundary 推理坍缩到"两对象 + scoped relation"的通用规则,与 [`relation.md` §4](../zh/models/relation.md) 跨 Realm relation 同构。

### 3.5 Capability 与授权评估

新增 capability actions:

| action | risk_tier | target event kinds | 说明 |
| --- | --- | --- | --- |
| `cx.circle.create` | medium | `cx.circle.create` | 创建 Circle。**默认不**在普通成员 bundle 中(防止 Circle 滥用稀释 UX)。 |
| `cx.circle.manage` | medium | `cx.circle.update`, `cx.circle.archive`, `cx.circle.restore`, `cx.circle.tombstone` | 管理已存在 Circle。 |
| `cx.circle.member.add` | low | `cx.circle.member.state`(payload.actor_id == envelope.actor_id,且 transition 合法) | 用户接受邀请、加入 `join_rule=open` 的 Circle 或自助退出;不得自助解除 ban。 |
| `cx.circle.member.manage` | medium | `cx.circle.member.state`(actor_id != envelope.actor_id) | 邀请/移除他人;Circle admin 持有。 |
| `cx.circle.member.add.others` | high | 同上 + 强制带 `cx.audit.accessed` 配对(与 `cx.flow.watch.set.others` 同模式) | 跨成员代写(罕用),审计配对。 |
| `cx.circle.audit` | high | 空(read-only),配对 `cx.audit.accessed` | 不属于 Circle 的 Realm admin 读取 Circle 元数据 / activity rollup 的审计权。 |

**授权评估两层 AND**:

```
authorized(actor, action, object) ⇔
    capability_grant(actor, action) ∧
    (scope(object) == null ∨ actor ∈ Circle(scope(object)).members[at object.causal_frontier])
```

其中 `scope(object)` 对 durable Event 使用 immutable `effective_scope`,对 materialized object 使用当前 `scope_circle_id` 派生出的 tagged scope。capability 决定"能不能做",Circle membership 决定"够不够近"。任一不满足都拒绝。

Circle 管理类 grant MUST 显式约束到 `allowed_circle_refs` / `circle_id` selector,或由 Circle 自身的 admin cell 派生;不得把无约束的 Realm-wide `cx.circle.manage` 当作普通管理权限发放。Realm admin 需要读取 Circle 正文或成员细节时 MUST 走 `cx.circle.audit` + `cx.audit.accessed` 配对路径,且不能获得历史解密 key,除非被正式加入该 Circle。

### 3.6 Membership 拓扑

**硬不变量**:

1. `Circle.members ⊆ Realm.members`。reducer 在 `cx.circle.member.state -> active` 时,若 target actor 不是父 Realm `active` member,MUST `failed_precondition` `reason="circle_member_must_be_realm_member"`。
2. 父 Realm `cx.member.state -> left/banned` 触发 **reducer-derived** cascade:该 actor 在该 Realm 所有 Circle 的 membership 收敛到 `left`,并触发各 Circle 的 MLS `remove` proposal。不需要 actor 显式写。
3. **Circle 平面化,不允许嵌套**(`parent_circle_ref` 不存在)。需要交叉成员关系时,actor 同时属于多个 Circle 即可;不需要 hierarchy。本约束沿用 [`realm-links.md` §2.1](../zh/models/realm-links.md) "link graph not tree" 的教训。
4. Circle admin / moderator 不是 Realm admin 的隐式子集。需要 Circle-local 管理时,必须通过 Circle-scoped admin cell 或带 `circle_id` / `allowed_circle_refs` selector 的 capability grant 表达;v1 不注册单独的 `cx.circle.admin` action。

Membership transition table:

| from | to | writer |
| --- | --- | --- |
| none / left | invited | `cx.circle.member.manage` |
| invited | active | target actor (`cx.circle.member.add`) 或 `cx.circle.member.manage` |
| none / left | active | target actor only when `join_rule=open`; otherwise `cx.circle.member.manage` |
| active | left | target actor or `cx.circle.member.manage` |
| none / invited / active / left | banned | `cx.circle.member.manage` |
| banned | left / invited | `cx.circle.member.manage` only; self-service MUST fail closed |

### 3.7 Lifecycle cascade

因为对象只有单一 scope,lifecycle 表退化为简单形态(对比当前 [`flow-and-message.md` §5.0.1](../zh/models/flow-and-message.md) 跨 Realm 表的复杂度):

| 场景 | Realm-level / 未 scope 对象 | scope_circle_id 指向该 Circle 的对象 |
| --- | --- | --- |
| 父 Realm tombstone | 按 Realm lifecycle 停止 | Circle 全部 tombstone;对象按 Circle lifecycle 停止 |
| Circle tombstone | 不受影响 | 对象写入 MUST fail closed,projection 显示 scope unavailable;`scope_circle_id` 不会被自动 rewrite |
| 父 Realm 收紧 history visibility | 按新 visibility | Effective visibility 重新计算为更严格值;Circle 不得保持比父 Realm 更宽的历史披露 |
| Circle history visibility 收紧 | 不受影响 | 投影、watch、message read/write 按新状态重新裁剪 |
| `scope_circle_id` 改绑 | — | 默认拒;profile 允许时 audit-paired,新旧历史分段展示(见 §3.4) |

注意:本表**没有**"对象跨两个 scope"的格子需要处理 —— 这正是删除 `discussion_realm_ref` 换来的复杂度坍缩。每个对象有唯一 scope,lifecycle 只需在该 scope 与父 Realm 两层间做判定,不需要 §5.0.1 那种四象限组合表。

### 3.8 Sync / 投递不变量

正式化为通用规则(取代当前 [`flow-and-message.md` §8.9](../zh/models/flow-and-message.md) 跨 Realm 派发的特化形态):

> **Scope 投递不变量**:对任意事件 `E` 满足 `E.effective_scope.kind="circle"` 且 `E.effective_scope.circle_id=C`,Sync Service MUST NOT 向不属于 `C.members(at causal frontier of E)` 的 actor 投递 `E` 的 envelope 或 payload。订阅 Realm R 等价于订阅 (R 的 Realm-level events) ∪ (∀C ∈ R.circles, 若 actor ∈ C.members 则 C 的 scoped events,否则 ∅)。

特例:
- `cx.circle.create` 的 authorization shell 是 Realm-level event,但 projection MUST 按 `directory_visibility` 裁剪。`directory_visibility=members` 时,非成员不得看到 Circle title、display、member_count、created_by 或可区分存在性的错误;最多只能看到不可枚举的 opaque commitment。
- `cx.circle.member.state` 仅投递给该 Circle 的成员 + 完成 `cx.circle.audit` / `cx.audit.accessed` 配对的 audit reader。
- `cx.circle.anchor_commit` 是 Realm-level event,但只携带 opaque digest(见 §3.9),且触发节奏不得泄露 Circle 活动频率。

### 3.9 MLS / Anchor 集成

**MLS**:

- Circle 拥有独立 MLS group,独立 epoch,独立 key tree。**禁止**从 Realm-default MLS group key 派生 Circle key(否则全 Realm 都能解密)。
- Realm 移除某 actor MUST 触发该 actor 所在所有 Circle 的 MLS `remove` proposal,**并**触发 Realm-default MLS rotate。这是必要的密码学卫生,reducer-enforced。
- Circle MLS handshake (commit/welcome/proposal) 投递严格限于 Circle 成员,不进入 Realm-default sync 流。
- MLS governance binding 的 scope 从单 `realm_id` 扩展为 `(realm_id, circle_id?)`。Circle commit / welcome / genesis MUST 绑定 `circle_id`、Circle membership frontier、Circle policy root 与父 Realm policy floor frontier;接收端验证时任一不匹配 MUST fail closed。

**Anchor stream**:

- Circle 内事件维护 Circle sub-anchor(只对 Circle 成员可读,记录完整 envelope + payload digest)。
- Circle 按 profile 固定节拍触发 `cx.circle.anchor_commit`,向 Realm Anchor stream 提交 `sub_anchor_head_digest`(不透明 SHA-256)。默认命名 profile 为 `cx.profile.circle_anchor_cadence.fixed_5m.v1`：`period_ms=300000`、`max_jitter_ms=30000`、必须提交空批次 commitment、不得因为没有真实事件而跳过 public anchor tick。低隐私部署若声明 event-count profile,必须显式标为不满足 confidential Circle profile。
- 验证链:Circle member 验证时 `Circle sub-anchor head ↔ Realm anchor commitment ↔ Realm anchor head`,三段闭合。非 Circle 成员只能验证 Realm anchor 完整性。

### 3.10 删除 `Flow.discussion_realm_ref`

本提案 **彻底删除** `Flow.discussion_realm_ref` 字段及其相关补丁规则:

- 字段从 [`flow.schema.json`](../artifacts/schemas/flow.schema.json) 与 [`event-payload.schema.json`](../artifacts/schemas/event-payload.schema.json) 中移除。
- 加入 [`forbidden-wire-fields.json`](../artifacts/registry/forbidden-wire-fields.json) reserved-name guard:`flow.discussion_realm_ref` 出现在 wire 上 MUST `schema_violation`(`reason="discussion_realm_ref_removed"`)。
- [`flow-and-message.md` §5 / §5.0.1 / §8.9](../zh/models/flow-and-message.md) 全部删除或重写为本提案 §3.4.3 / §3.7 / §3.8 的形态。
- Glossary 中 `Linked Discussion Realm` 条目移除;`Realm` / `Circle` 区分由 [`zh/overview/glossary.md`](../zh/overview/glossary.md) 新条目承担。

**业务诉求迁移**:
- "宽 synthesis + 窄 discussion" → 见 §3.4.3,改用两个 Flow + Relation。
- "discussion 落在跨组织联邦 Realm" → 在该联邦 Realm 内独立 `cx.flow.create`,父侧通过 `cx.realm.link{link_kind=confidential_extension_of}` 或 Relation 引用;不是 Flow 字段。

**这是 v1 freeze 前的破坏性变更**。一旦 freeze 后才发现需要,只能 v2 处理。本提案的判断:在 freeze 窗口内一次性切干净,远好于 v1 ship 后用 deprecation 窗口慢慢拆 —— `discussion_realm_ref` 的存在污染了 §5.0.1 / §8.9 等多处 normative,deprecation 路径会让这些章节长期保持"双语义"状态,迁移成本反而更高。

## 4. Interactions with normative spec

### 4.1 新增文件

- `spec/v1/zh/models/circle.md` — Circle normative 完整描述。
- `spec/v1/artifacts/schemas/circle.schema.json` — Circle 对象 schema。

### 4.2 修改文件

- [`zh/overview/architecture.md` §2.0](../zh/overview/architecture.md):容器选型表:
  - 追加 Circle 行:`| 在已有 Realm 内做"密码学子圈"(独立 MLS group / 独立成员 / 独立 history),但共享 federation/policy/capability registry | **Circle**(`ck:circle:`),对象 `scope_circle_id` 引用 | Circle 是 Realm 内的密码学子边界;父 Realm 仍承担 federation identity / policy / capability registry。 |`
  - **删除** `Flow + discussion_realm_ref` 行;改写"宽 synthesis + 窄 discussion"指引到"两 Flow + Relation"形态(见 §3.4.3)。
  - 修订 §2.0 末尾"不得自行造第四类"为"第四类(Circle)由 CXP-0007 引入;新增容器型概念仍 MUST 先验证是否可分解为 Realm / Space / Flow / Circle"。

- [`zh/models/realm-and-space.md` §2.1](../zh/models/realm-and-space.md):删除"强保密差异**必须**切分 Realm"的硬约束,改为"强保密差异 MAY 通过 Circle 表达;跨 federation/policy 边界的差异 MUST 切 Realm"。
- [`zh/models/realm-and-space.md` §2.2](../zh/models/realm-and-space.md):正式化"辅助 MLS group" 为 Circle;`cx.circle.*` 是其唯一 wire 入口;新增 Realm-default encryption scope 说明,明确 Realm 不自动创建默认 Circle。
- [`zh/models/realm-and-space.md` §2.x`](../zh/models/realm-and-space.md):新增 Realm `content_encryption_floor`;把既有 `metadata_encryption_profile` 明确为 Realm-wide floor;新增 Space `child_scope_policy` 写入检查规则。
- [`zh/models/realm-and-space.md` §4](../zh/models/realm-and-space.md):在 "Group 与 Capability 的位置" 一节顶部加 disambiguation note,明确 **Group**(principal 集合,capability subject) 与 **Circle**(资源 scope,密码学子圈) 是两个正交概念,不可混淆。
- [`zh/crypto-media/encryption-and-audit.md`](../zh/crypto-media/encryption-and-audit.md):重写 MLS scope / governance binding / KeyPackage claim / identity-link cache invalidation 规则,把 scope 从 `realm_id` 扩展为 tagged `effective_scope`;明确 `mls_rfc9420` 是机制,`metadata_encryption_profile` 是加密覆盖范围,并删除 `discussion_realm_ref` 相关 special case。
- [`zh/models/relation.md`](../zh/models/relation.md):新增跨 scope Relation 规则,复用跨 Realm 的 two-sided authorization / locked projection / anti-enumeration 模型;新增标准 weak-semantic `confidential_discussion_of`。
- [`zh/models/flow-and-message.md`](../zh/models/flow-and-message.md):**重写性变更**。
  - §3 schema 表中 `discussion_realm_ref` 行删除;追加 `scope_circle_id` 行。
  - §5 整节(Discussion 独立 Realm)删除;替换为新 §5 "Flow scope" —— 描述 `scope_circle_id` 表达 Flow 整体落在某 Circle 的形态。
  - §5.0.1 lifecycle 级联表删除;新 lifecycle 规则在 [`circle.md`](../zh/models/circle.md) 内描述(§3.7)。
  - §5.1 Mermaid 关系图删除;若需要新图,描述"Flow ∈ Realm-default 或 Flow ∈ Circle" 的二选一形态。
  - §8.9 "discussion_realm_ref 场景" 删除;新 §8.9 描述 "scope_circle_id 场景" 的通用 watch 投影规则。
- [`zh/overview/current-model.md` §6-§7](../zh/overview/current-model.md):删除 `discussion_realm_ref` 提及;MLS 边界描述改为 "Realm-default group 与各 Circle 独立 group"。
- [`zh/overview/glossary.md`](../zh/overview/glossary.md):
  - **删除** `Linked Discussion Realm` 条目。
  - 修订 `discussion track` 条目,移除"通过 `Flow.discussion_realm_ref` 升级"措辞。
  - 新增 `Circle` 条目;新增 `Circle scope` / `scope_circle_id` 短条目;明确 `Circle` vs `Group` disambiguation。
- 全 spec 当前出现 `discussion_realm_ref` 的所有文件(spec 内 grep 显示 ~28 处,跨 `zh/models/*`、`zh/authz/*`、`zh/sync/*`、`zh/discovery/*`、`zh/conformance/*`、`zh/extensions/mimi-interop.md`、`zh/overview/*` 与 `artifacts/`)挨个清理或重写引用段落。Migration PR 应附完整清单与逐文件 diff,不在本提案中展开。

### 4.3 修改 artifact

- `id-kind-registry.json`:新增 `circle` → `ck:circle:<uuid>`。
- `event-kind-registry.json`:
  - 新增 7 条 `cx.circle.*` event kinds。
  - **删除** `flow_create_payload` / `flow_update_payload` 中的 `discussion_realm_ref` 字段引用。
- `capability-action-registry.json`:新增 6 条 capability actions。
- `schema-registry.json`:新增 `cx.schema.circle.v1`。
- `flow.schema.json`:
  - **删除** `discussion_realm_ref` 字段。
  - 追加 `scope_circle_id` 可选字段。
- `realm.schema.json` / policy component schemas:
  - **`metadata_encryption_profile` 是既有字段**(已在当前 realm policy schema 中存在),本提案将其语义明确为 Realm-wide floor 并固化 `content_only` / `minimal_encrypted` / `full_encrypted` 三档 enum + conformance(若当前 schema 形态与此不符,迁移 PR 负责对齐)。
  - **`content_encryption_floor` 是新增字段**(`allow_plaintext` / `e2ee_required`),挂在 Realm policy component schema 上。
  - **`Realm.encryption_profile` 是新增字段**(受控 enum,v1 仅 `mls_rfc9420`),表达 Realm-default encryption scope 的密钥承载机制;与 Circle `encryption_profile` 同 enum 集合,不同 scope 各自独立声明。
- `message.schema.json`:追加 reducer-stamped immutable tagged `effective_scope`。
- `morph.schema.json`、`space.schema.json`:追加 `scope_circle_id` / `default_scope_circle_id` / `child_scope_policy` 可选字段;明确 `Space.scope_circle_id` 只引用 Circle,不让 Space 自身成为边界;`default_scope_circle_id` 只是新建对象默认值(三字段语义见 §3.4 末尾表)。
- Event envelope / AAD schema:追加 immutable tagged `effective_scope`,并纳入 signing / E2EE AAD / Anchor leaf canonical bytes。
- `event-payload.schema.json`:`flow_create_payload` / `flow_update_payload` 字段集同步删除 `discussion_realm_ref`。
- `forbidden-wire-fields.json`:**新增** `flow.discussion_realm_ref` 进入 reserved-name guard,出现即 `schema_violation`。
- `removed-event-kinds.json`:不适用(没有 event kind 被移除;仅字段被移除)。
- `renames.json`:追加 `discussion_realm_ref` 的 migration 提示("无直接对应字段;按 §3.4.3 改用两 Flow + Relation 形态")。
- `contract-catalog.json`:登记 Circle contract 版本;`Flow` contract 升 minor 版,标注 `discussion_realm_ref` removed。
- `error-code-registry.json`:**新增**以下 reason codes:
  - `circle_realm_mismatch`(§3.4)
  - `circle_not_active`(§3.4)
  - `circle_member_must_be_realm_member`(§3.6)
  - `scope_rebind_forbidden`(§3.4)
  - `metadata_encryption_floor_violation`(§3.4.1)
  - `discussion_realm_ref_removed`(§3.10)
- `vector-registry.json`:**新增** Circle conformance vector cluster:
  - Circle create + member.state lifecycle 正确性
  - `effective_scope` immutable stamping 验证(envelope / AAD / sub-anchor leaf 三处一致性)
  - Scope-aware reducer 两层 AND 评估
  - Cross-scope Relation 投影裁剪
  - Sub-anchor commitment ↔ Realm Anchor 验证链
  - Metadata encryption floor 三档强制(`content_only` / `minimal_encrypted` / `full_encrypted`)
- MLS / governance binding artifacts:新增 `circle_id` optional binding field、Circle scoped covered-frontier cell key、KeyPackage claim intended scope 扩展。

### 4.4 不冲突 / 已对齐

- 现有 "Group"(principal 集合,capability subject)语义**保留不变**;Circle 是新增正交概念,不重命名也不取代 Group。
- `cx.realm.link` graph 不变;Circle 不参与 Realm link graph(Circle 是 intra-Realm 概念)。`link_kind=confidential_extension_of` 仍可用于"跨 federation Realm 的机密延伸"语义。

## 5. Rationale & alternatives

### 5.1 为什么不复用 Space 作为密码学边界

候选 A:给 Space 加 `is_security_circle: true` 字段,部分 Space 承载 MLS / membership。

否决理由:
- Space 当前是 "authorization-transparent" 容器,跨 Realm hierarchy 能力是其核心特性([`realm-links.md` §8](../zh/models/realm-links.md))。让部分 Space 成为 MLS 边界后,必须禁掉跨 Realm 用法或定义巨型 carveout。
- 一个原语同时承担"导航"+"密码学边界"两个本质不同概念,正是当前 Realm 双重身份(federation + crypto)问题的复刻 —— 不该再犯一次。
- `cx.space.*` event 会按 `is_security_circle` 分裂行为,违反 spec "event kind 单义" 风格。
- Space 嵌套(Space hierarchy)与"crypto 边界平面化"诉求直接冲突;前者天然嵌套,后者必须平面。

### 5.2 为什么不直接为每个子圈开新 Realm

当前 spec 的实际默认答案。否决理由(见 §2):每个子圈背 federation identity / policy server / capability registry / federation route 的全套开销;`cx.realm.link` graph 不断膨胀来缝合"这些其实是同组织内的事"。已经付出"一对象跨两 Realm" 的复杂度(§5.0.1 / §8.9 cascade 规则),但只覆盖了一种业务面(Flow.discussion)。

### 5.3 为什么不是 access-filter boundary

候选 B:Circle 只做授权窄化,复用 Realm-default MLS / 明文策略。

否决理由:
- 这与现有 Group、capability constraint、resource selector 重叠,没有足够理由引入一等 primitive。
- "Circle" 名称会让用户和客户端误以为存在独立密钥边界;实际只是服务端不投递,一旦服务端、镜像或日志路径出错就泄露正文。
- Cokret 已经有明确的 E2EE / MLS governance binding 语义。新增边界若不能进入该体系,反而会制造比 `discussion_realm_ref` 更隐蔽的安全错觉。

### 5.4 为什么不嵌套 Circle

候选 C:Circle 允许 `parent_circle_ref`,形成 Circle hierarchy。

否决理由:
- `realm-links.md` §2.1 已学到"Realm hierarchy 不要"的教训,Circle 不重蹈。
- 嵌套 MLS group 的 key 派生 / forward secrecy 跨层交互是已知地雷区,行业 MLS 部署普遍避免。
- 交叉成员需求通过"actor 同属多 Circle"表达即可,语义清晰。

### 5.5 为什么用新原语而不是扩展 `discussion_realm_ref`

候选 D:`discussion_realm_ref` 升级为可指向"轻量 Realm"(即不参与 federation 的 Realm 子类型)。

否决理由:这是把 Realm 原语从"双重身份"升级为"三重身份"(federation full Realm / sub-Realm / linked Realm),进一步复杂化已经过载的 Realm 概念。新原语干净分离,反而是简化。

### 5.6 为什么彻底删除 `discussion_realm_ref` 而不是 deprecation

候选 E:保留 `discussion_realm_ref` 作 v1 legacy,标记 deprecated,v2 再删。

否决理由:
- `discussion_realm_ref` 不只是一个字段,它带着 §5.0.1 lifecycle 级联表、§8.9 watch 跨 Realm 投影、改绑禁令等一整套补丁规则。保留字段就保留全部补丁,normative 文档长期带双语义,迁移成本递增。
- 它打破"一对象一安全边界"硬不变量。**删掉这个字段**是把这个不变量重新立起来的唯一方式;deprecation 期间不变量仍然破。
- v1 还在 freeze 窗口内,这是唯一可以无痛切的机会。一旦 ship,删字段就是 breaking change,所有已存在的 Flow 数据要 migrate。
- 业务场景没有真正丢失:§3.4.3 的"两 Flow + Relation" 形态覆盖了所有 `discussion_realm_ref` 服务的用例,且语义更清晰、客户端组合显示也能做到。

### 5.7 为什么 Flow 不允许 per-track 安全边界

候选 F:保留 `Flow.discussion_scope_circle_id` 让 discussion track 独立 scope(synthesis 与 discussion 拆 Circle)。

否决理由:这是 `discussion_realm_ref` 的"轻量版翻版" —— 仍然让一个对象跨两个安全边界,只是把跨界的"另一侧"从 Realm 换成 Circle。所有 §5.0.1 / §8.9 类型的复杂度会以另一种形式回来。**对象单一 scope 这条不变量,要么坚持,要么不坚持;没有"只对 track 网开一面"的中间态**。需要拆分时,拆成两个 Flow 是干净的做法。

### 5.8 命名:为什么是 "Circle" 不是 "Group"

[`realm-and-space.md` §4](../zh/models/realm-and-space.md) 已使用 **Group** 表达 principal/actor 集合(capability subject,~LDAP/AD group)。直接复用 "Group" 会造成两个不同概念同名,wire field、capability action、Glossary 全部歧义。"Circle"(信任圈)与"Group"(成员集合)在中英文都自然区分,且符合行业"trust circle"用法。

### 5.9 已知代价:Realm-member-removal 的 MLS rotate amplification

§3.9 规定 Realm 移除某 actor MUST 触发:
- 该 actor 所在**所有** Circle 的 MLS `remove` proposal
- Realm-default MLS rotate

一次离职 / 踢人因此可能放大为 **N+1 次 MLS group rotation**(N = 该 actor 所在 Circle 数)。这是密码学卫生的必要代价(forward secrecy 与 post-compromise security 要求),不可省。

操作上的缓解策略(profile MAY 实现,**不在 protocol normative 层强制**):

- **批量 rotate**:profile MAY 把短时间窗内的多次 member removal 合并为单次 rotate proposal batch(MLS 协议本身支持 multi-proposal commit)。
- **延迟 rotate 窗口**:profile MAY 声明 rotate 必须在 actor removal 后 ≤ X 完成。X 是该 profile 的 forward secrecy 窗口承诺,MUST 显式公开,且 MUST 不长于 profile 声明的最大可容忍泄露窗口(典型 ≤ 1 小时)。
- **Circle 数量上限的运营建议**:产品上鼓励 Circle 少而稳定(参考 §6 UX 风险);profile MAY 软上限(例如单 Realm ≤ 64 Circle)以约束 rotate amplification 的最坏情况。

设计选择 rationale:此代价**已知且可接受**。替代方案(共享 Realm-default key 派生 Circle key、或惰性 rotate 直到下一次实际通信)会破坏 Circle 的密码学隔离前提,使 Circle 退化为 access-filter,这是 §1 非目标 / §5.3 已否决的路径。

## 6. UX 论证(为什么 `display` 字段必须 normativize)

Circle 引入的最大实践风险是**跨 Circle 上下文混淆**:用户在 Circle A 的 Flow 工作,被通知 ping 到 Circle B 的 Flow,回复时误以为仍在 A 圈。这是真实泄露发生的瞬间。**因为 Flow 是单 scope 的(本提案 §3.4),所以"我在哪个 Circle"等价于"我在哪个 Flow",这反而让 UX 清晰**:每个 Flow 的视觉身份就是它 scope 的视觉身份,不存在"同一 Flow 内 synthesis 一个色、discussion 另一个色"的混乱。

要让 UI 能可靠区分,以下信号 MUST 在 spec 层统一,**不**留给客户端各自发明:

- **颜色 token**:同一 Circle 在 Alice 与 Bob 的客户端上必须呈现一致颜色,否则跨设备 social engineering 攻击成立。
- **短名**:`HR-Conf` 比 `ck:circle:01964...` 可读性高几个量级,且能进入 compose bar 实时显示。
- **符号 / glyph**:无障碍 / 色盲场景的第二信号。

客户端实现 SHOULD 至少做到:

1. Flow 列表行左侧色条 + 行尾徽章 `🔒 <short_name> · <member_count>`(整 Flow 一个 scope,色条不会"半色")。
2. Flow 打开页顶部 banner 用 Circle 颜色;标题旁显示 `<short_name> · <member_count>`。
3. compose 输入框上方常驻 scope 指示 `→ Sending to: [color bar] <short_name> · <member_count>`;切换 Flow 后首次输入时短暂高亮该行。
4. 跨 Circle 导航有可感知转场(banner 颜色变化、breadcrumb 更新);避免"同一空间内滚动"错觉。
5. mention 候选列表中非 Circle 成员置灰并提示"不在此 Circle"。
6. 跨 Circle 引用以虚线框 + "另一信任圈"标识展示,**不**预览内容。
7. "宽 anchor Flow + 窄 discussion Flow" 的组合形态(§3.4.3)在 UI 上 MAY 渲染为单卡片 + tab 切换,**但** tab 之间切换 MUST 表现为跨 scope 转场(banner 颜色变化 + compose scope 指示更新),不是同 Flow 内不同视图。

详细 UX rationale 见 design discussion(2026-05-25 conversation log)。

## 7. Open questions

- [ ] **Circle 创建权限默认**:`cx.circle.create` 是否默认包含在普通成员 bundle?倾向 **否**(Circle 应当少而稳定;参考 §6 UX 风险面)。但创业团队可能希望低门槛 —— 是否做成 profile-level 决定?
- [ ] **Display palette 大小**:v1 草案给 17 色,是否够?Linear 8 色 / Tailwind 22 色对比下,17 是个折中。固定 token 集是否锁在 schema 还是 profile?
- [x] **`Space.default_scope_circle_id` 强制性**:`default_scope_circle_id` 保持 hint;强制约束用 `child_scope_policy` 表达,避免"Space 隐式成为安全边界"的语义滑坡。
- [x] **跨 Circle Relation**:统一为"跨 scope Relation",直接复用 [`relation.md` §4](../zh/models/relation.md) 跨 Realm ref 的 two-sided authorization / locked projection / anti-enumeration 模型。§4.2 已列出 `relation.md` 修改项,§8.1 第 10 步落地。无遗留决策点。
- [x] **新 relation_kind `confidential_discussion_of`**:§3.4.3 "两 Flow + Relation" 模式需要协议级 relation_kind 来标识"这个 Circle Flow 是那个 anchor Flow 的机密讨论延伸"。关系事实 SHOULD 存在 private Flow 的 Circle scope 内,避免 public anchor 反向泄露私密讨论存在性。
- [ ] **Circle merge / split**:运维场景"两个 Circle 合并"或"Circle 拆分"是否需要协议级 event(如 `cx.circle.merge`),还是纯客户端流程?MLS 层 merge 不平凡,倾向 v1 不做,留 v1.1。
- [x] **`cx.circle.anchor_commit` 固定节拍参数**:§3.9 固定默认命名 profile `cx.profile.circle_anchor_cadence.fixed_5m.v1`，周期 5 分钟、最大抖动 30 秒；移动端省电不得改变公开 Realm anchor cadence，只能影响客户端上传私有 sub-anchor entries 的批处理。
- [ ] **Watch cell 的 Circle 归属**:scope_circle_id 指向 Circle 的 Flow,其 watch cell 应落在父 Realm namespace 还是 Circle namespace?倾向 **Circle namespace**(单源,且 watch 见解直接受 Circle membership 约束,不需要单独投影裁剪规则)。这与原 §8.3 watch cell 在 source Realm 的设计相反,需要在 [`flow-and-message.md` §8](../zh/models/flow-and-message.md) 重写。
- [ ] **历史成员 / "前成员能否看历史消息"**:与 MLS welcome 包是否携带历史 key 的 profile 选项有关,是否在 Circle 创建时就锁定?
- [x] **`encryption_profile=plaintext_inherit` 是否保留**:不保留。Circle v1 只表示独立 MLS 密码学边界;授权窄化继续使用 Group / capability constraint / selector。
- [ ] **`discussion_realm_ref` 历史数据 migration**:如果有已部署的 pre-CXP-0007 数据已经使用 `discussion_realm_ref`,如何迁移?方案:迁移工具把"Flow F 带 discussion_realm_ref=R'"拆为"Flow F 与 Flow F' (在 R')"+ Relation。需要工具支持还是 hand-migration?**前提**是 v1 freeze 前接受本提案;若 freeze 后,问题质性升级。
- [ ] **MLS rotate amplification profile 参数**(配合 §5.9):default profile 的 forward secrecy 窗口具体值、批量 rotate window 大小、单 Realm Circle 数量软上限是否需要写进 protocol-level conformance,还是完全留给 profile 自行声明?倾向**留给 profile 但要求 floor profile 必须显式公开窗口承诺**,避免不透明 SLA。

### 7.1 Post-acceptance status（accepted 后状态归档）

本提案已 `accepted` 并合并入 normative docs。上面 §7 的 open questions 是**历史讨论记录**;其在 v1 的最终归宿如下,读者应以 normative docs 为准,不要把已归档问题误读为 release blocker:

| Open question | 状态 | normative 归宿 / 决定 |
| --- | --- | --- |
| Circle 创建权限默认 | **resolved** | `cx.circle.create` 默认**不**在普通成员 bundle 中（[`circle.md`](../zh/models/circle.md) §8）。是否放宽是 deployment profile 决定。 |
| Display palette 大小 | **deferred-to-profile** | 固定 token 集由 display profile 锁定（[`circle.md`](../zh/models/circle.md) §11),不进 core wire schema。 |
| `Space.default_scope_circle_id` 强制性 | **resolved** | hint;强制约束用 `child_scope_policy`（[`circle.md`](../zh/models/circle.md) §6.3/§7.1）。 |
| 跨 Circle Relation | **resolved** | 复用跨 scope Relation 模型（[`relation.md`](../zh/models/relation.md) §4）。 |
| `confidential_discussion_of` | **resolved** | 已注册为标准 weak-semantic relation kind（[`relation.md`](../zh/models/relation.md) §3.1/§3.2）。 |
| Circle merge / split | **deferred-to-v1.1** | v1 不引入 `cx.circle.merge` 等 event;MLS 层 merge 非平凡。 |
| `cx.circle.anchor_commit` 固定节拍参数 | **resolved → named cadence profile** | `cx.profile.circle_anchor_cadence.fixed_5m.v1` 固定 `period_ms=300000`、`max_jitter_ms=30000`、空批次 commitment 与移动端省电边界（[`circle.md`](../zh/models/circle.md) §10.2）。confidential Circle profile MUST NOT 使用会泄露活动频率的 event-count cadence。 |
| Watch cell 的 Circle 归属 | **resolved** | scope 指向 Circle 的 Flow,其 watch cell 落在 Circle namespace（[`flow-and-message.md`](../zh/models/flow-and-message.md) §8）。 |
| 历史成员能否看历史消息 | **deferred-to-profile** | 由 MLS welcome 是否携带历史 key 的 profile 选项决定;Circle 创建时锁定。 |
| `encryption_profile=plaintext_inherit` 保留 | **resolved** | 不保留。 |
| `discussion_realm_ref` migration | **resolved (pre-freeze)** | §8.1 已删除该字段;迁移工具把带 `discussion_realm_ref` 的 Flow 拆为两 Flow + Relation。 |
| MLS rotate amplification 参数 | **deferred-to-profile (release-gate)** | 留给 profile,但 floor profile MUST 显式公开 forward secrecy 窗口承诺。 |

## 8. Migration plan

> accepted 后填,以下为切片次序参考。本提案**必须在 v1 freeze 前完成 §8.1 + §8.4**,否则 `discussion_realm_ref` 删除变为 v2 breaking change。

### 8.1 Pre-freeze 强制项(必须在 v1 ship 前完成)

1. **删除 `Flow.discussion_realm_ref`**:更新 `flow.schema.json` / `event-payload.schema.json` / `forbidden-wire-fields.json`;改写 [`flow-and-message.md`](../zh/models/flow-and-message.md) §3 / §5 / §5.0.1 / §5.1 / §8.9 等所有引用段;更新 [`overview/glossary.md`](../zh/overview/glossary.md) / [`overview/current-model.md`](../zh/overview/current-model.md) / [`overview/architecture.md`](../zh/overview/architecture.md) §2.0。
2. **引入 `ck:circle:` 对象 schema 与基础 event**(`cx.circle.create` / `cx.circle.member.state` / `cx.circle.tombstone`);更新 `id-kind-registry.json` / `event-kind-registry.json` / `schema-registry.json`。
3. **独立 MLS group 必须同步落地**:Circle create 必须创建 `(realm_id, circle_id)` scope 的 MLS group、epoch 0 governance binding、Circle scoped covered-frontier cell;不得以 Realm-default MLS + 应用层过滤替代。
4. **声明加密覆盖 policy**:新增 Realm `content_encryption_floor`;把既有 `metadata_encryption_profile` 固化为 Realm-wide floor,并支持 `content_only` / `minimal_encrypted` / `full_encrypted` 三档 conformance。
5. **引入 `scope_circle_id` / tagged `effective_scope` 字段** 到 `flow.schema.json` / `message.schema.json` / `morph.schema.json` / `space.schema.json`(`default_scope_circle_id` / `child_scope_policy`)以及 Event envelope / E2EE AAD / Anchor leaf canonical bytes。
6. **重写 MLS governance binding**:把 scope 从单 `realm_id` 扩展为 tagged `effective_scope`;KeyPackage claim、Welcome、identity-link cache、policy tightening invalidation 同步支持 Circle。
7. **引入 Circle sub-anchor + fixed-cadence `cx.circle.anchor_commit`**:默认 profile 必须避免通过 public commitment 节奏泄露活动频率。
8. **reducer 两层 AND 评估**(§3.5):capability_grant ∧ Circle membership(若 scope 非 null),并 enforce 父 Realm visibility floor / encryption floor。
9. **Sync 投递不变量**(§3.8)实现:服务端按 Circle membership 过滤,并按 `directory_visibility` 裁剪 Circle 元数据。
10. **跨 scope Relation**:新增 `confidential_discussion_of` 与跨 scope projection / anti-enumeration 规则。

完成本阶段后 v1 可以 ship 一个**结构上干净**的 spec:所有对象单 scope,所有补丁规则收敛到统一形态。

### 8.2 Post-freeze 增量项(v1.x minor release)

11. **Circle merge / split**:MLS 层 merge 不平凡,留 v1.1+。
12. **Anchor cadence tuning**:根据实现经验调整默认周期、移动端省电 profile 与高隐私 cover-traffic profile。

### 8.3 UI 标准化(可与 §8.1 并行)

13. 客户端实现 §6 视觉规范;颜色 token / glyph 集纳入 conformance vector。

### 8.4 历史数据迁移(若适用)

14. 若存在 pre-CXP-0007 部署使用 `discussion_realm_ref`,提供一次性迁移工具:把 "Flow F 带 discussion_realm_ref=R'" 拆为 "Flow F + Flow F' (在 R') + Relation(F → F')"。这条只在已经有 pre-spec 部署数据时需要;新部署不涉及。

## 9. References

- **本提案要删除的机制**:[`flow-and-message.md` §5](../zh/models/flow-and-message.md) `discussion_realm_ref`、§5.0.1 lifecycle 级联、§8.9 watch 跨 Realm 投影。
- 当前 spec 的容器分层:[`architecture.md` §2.0](../zh/overview/architecture.md)(需追加 Circle 行,删除 `discussion_realm_ref` 行)。
- Realm 与 MLS 关系:[`realm-and-space.md` §2.2](../zh/models/realm-and-space.md)。
- 现有 "Group" 概念(避免命名冲突):[`realm-and-space.md` §4](../zh/models/realm-and-space.md)。
- Realm link graph(Circle 不参与):[`realm-links.md`](../zh/models/realm-links.md)。
- 历史可见性枚举:[`event-auth-state-resolution.md` §6](../zh/authz/event-auth-state-resolution.md)。
- 设计 thread:2026-05-25 conversation log(本提案的 UX/MLS/Sync 推演与 `discussion_realm_ref` 完全删除决定的来源)。
- 外部对照:Matrix room/server 分层、Slack workspace/channel 分层。
