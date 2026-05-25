---
title: Circle
---

## 1. 目标

**Circle**(`cx:circle:`)是 Realm 内的**密码学子边界**:拥有独立 MLS group、独立 key epoch、独立 history key eligibility、Realm membership 的真子集成员,但**不**持有 federation identity 或 policy server。Circle 表达"窄于 Realm 的加密可见性圈"。

Circle 解决了 Contrix v1 早期设计中的抽象漏失:把"密码学子圈"作为一等原语拆出来,使 Realm 只承担 federation/identity boundary,Circle 专门承担 cryptographic access circle。这同时使得"一对象一安全边界"成为协议级硬不变量,不再需要让一个对象跨两个 Realm 存在。

**非目标**:Circle **不是** access-filter / ACL segment 的新名字,也不是 Realm 的"默认加密圈"。若实现只需要授权窄化但不需要独立密钥材料,应使用 [`realm-and-space.md` §4](./realm-and-space.md) 的 Group / capability constraint / resource selector;不得声明 Circle。Realm 自身仍拥有 **Realm-default encryption scope**;Circle 只表示 Realm 内更窄的额外 MLS scope。

## 2. 设计原则

1. **平面化,不嵌套**:Circle 不允许 `parent_circle_ref`。需要交叉成员关系时,actor 同时属于多个 Circle 即可;不需要 hierarchy。这条沿用 [`realm-links.md` §2.1](./realm-links.md) "link graph not tree" 的教训。
2. **真子集 membership**:`Circle.members ⊆ Realm.members`,reducer 硬约束。
3. **独立 MLS,不可派生**:Circle MLS group 是独立 epoch 链,**禁止**从 Realm-default MLS group key 派生 Circle key。
4. **不放宽父 Realm policy**:Circle 的 history visibility / metadata encryption floor **只能收紧,不能放宽**父 Realm policy floor。
5. **Circle ≠ Group**:[`realm-and-space.md` §4](./realm-and-space.md) 的 **Group** 表达 principal/actor 集合(capability subject)。Circle 表达资源 scope / 密码学子圈。两个概念正交,不可混淆。

## 3. Circle 对象

Schema id: `cx.schema.circle.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:circle` | `cx:circle:<uuid>`(UUIDv7) | Circle ID。 |
| `schema` | yes | `cx.schema.circle.v1` | 固定。 | 对象 schema。 |
| `realm_id` | yes | `id:realm` | create-locked;Circle 永远属于一个 Realm,不可改绑。 | 归属 Realm(父安全/联邦边界)。 |
| `title` | yes | `string` | 1..256 chars。 | 人类可读名称。 |
| `summary` | no | `string` | ≤2048 chars。 | 简短说明(渲染在 banner / 详情)。 |
| `display` | yes | `object` | 见 §4。 | **跨客户端一致**的视觉身份字段;只对 `directory_visibility` 允许的 actor 投影。 |
| `directory_visibility` | yes | `enum(members, realm_members)` | 默认 `members`。 | Circle 元数据可发现性。`members` 时非成员不得看到 title / display / member_count;`realm_members` 仅披露目录元数据,不授予事件或历史访问。 |
| `join_rule` | yes | `enum(invite, request, open)` | 默认 `invite`。 | Circle 加入规则。`open` 仅允许父 Realm active member 自助加入;`request` 需要 profile 定义申请/批准流程;`invite` 只能由 Circle 管理员加入或邀请。 |
| `history_visibility` | yes | `enum(world_readable, shared, invited, joined, restricted)` | 默认 `invited`。语义沿用 [`../authz/event-auth-state-resolution.md` §6](../authz/event-auth-state-resolution.md)。 | Circle 自己的历史可见性,但 effective visibility **不得宽于父 Realm 当前 policy floor**。 |
| `metadata_encryption_floor` | no | `enum(body_only, minimal_encrypted, full_encrypted)` | 省略时继承父 Realm floor。 | Circle 内对象的 metadata 加密下限;只能收紧,不得放宽父 Realm floor。 |
| `encryption_profile` | yes | `const(mls_rfc9420)` | create-locked。v1 仅允许 `mls_rfc9420`;未来 MLS 版本 / PQ-MLS 必须显式扩展 schema。Circle 必须拥有独立 MLS group;不得复用 Realm-default MLS group 或从其导出密钥。 | 加密形态。 |
| `mls_group_ref` | derived | `id:mls` | 由 `cx.circle.create` reducer 派生,scope 绑定 `(realm_id, circle_id)`;actor-supplied create payload MUST NOT 携带。 | 独立 MLS group 引用。 |
| `state` | yes | `enum(active, archived, tombstoned)` | 同 [`common-fields.md` §5](./common-fields.md);tombstoned 不可逆。 | 生命周期。 |
| `state_changed_at` | conditional | `timestamp` | `state != active` 时必填。 | 最近一次 state 转换时间。 |
| `created_by` | yes | `did` | — | 创建者。 |
| `created_at` | yes | `timestamp` | — | 创建时间。 |
| `updated_by` | no | `did` | — | 最近更新者。 |
| `updated_at` | no | `timestamp` | 不早于 `created_at`。 | 最近更新时间。 |

Circle v1 不提供 `plaintext_inherit` 或 "authorization-only Circle"。这条边界是故意的:access-filter 能力已经由 Group、capability constraint 与 resource selector 覆盖;把未加密隔离的对象命名为 Circle 会让客户端与用户误以为存在密码学隔离。

## 4. `display` 字段(标准化视觉身份)

跨客户端一致的 UI 表达是 Circle 安全模型的必要条件(见 §10 UX 论证):

| 子字段 | 必填 | 类型 | 约束 |
| --- | --- | --- | --- |
| `short_name` | yes | `string` | `^[A-Z][A-Za-z0-9 _-]{0,23}$`;在 `(realm_id, short_name)` 上 reducer 强制唯一(case-insensitive)。 |
| `color_token` | yes | `string` | 从受控 palette 选;v1 palette: `{slate, red, orange, amber, yellow, lime, green, emerald, teal, cyan, sky, blue, indigo, violet, fuchsia, pink, gray_high_contrast}`。客户端 MUST 映射 token → 主题颜色(浅/深/高对比),**不**得自行重分配 token。 |
| `symbol` | yes | `object` | `{emoji?: string, glyph?: enum}`;`glyph` 从受控集 ~24 个 icon(lock/shield/eye/diamond/...);二选一。 |

**颜色 token 与 symbol 必须在 spec 受控集中**,目的是同一 Circle 在 Alice 与 Bob 的客户端上呈现一致视觉,否则跨设备社会工程攻击成立。

## 5. Event 家族

| event kind | reducer_input | payload 形态 | 说明 |
| --- | --- | --- | --- |
| `cx.circle.create` | yes | full object | 创建 Circle,同时初始化独立 MLS group 与 epoch 0 governance binding。 |
| `cx.circle.update` | yes | `cx.patch.v1`(path 不含 `realm_id` / `encryption_profile`) | 改 title / summary / display / directory_visibility / join_rule / history_visibility。 |
| `cx.circle.archive` | yes | object_lifecycle_payload | active → archived。 |
| `cx.circle.restore` | yes | object_lifecycle_payload | archived → active。 |
| `cx.circle.tombstone` | yes | object_lifecycle_payload | terminal;触发 §8 cascade。 |
| `cx.circle.member.state` | yes | `{circle_id, actor_id, membership: invited\|active\|left\|banned, ...}` | 平行 `cx.member.state`,但 reducer 先校验 actor 已是父 Realm `active` member。 |
| `cx.circle.anchor_commit` | reducer-derived | `{circle_id, sub_anchor_head_digest, epoch}` | Circle sub-anchor 周期性向 Realm Anchor 提交不透明 commitment(§9)。 |

## 6. 对象 scope 表达

引入字段(跨多个现有对象):

```
Flow.scope_ref          : id:circle | null       # null = Realm-default encryption scope
Message.effective_scope : reducer-stamped,immutable tagged scope
Event.effective_scope   : reducer-stamped,immutable tagged scope,进入 envelope/AAD/sub-anchor
Space.scope_ref         : id:circle | null       # Space 自身 metadata / scoped structural relation 的可见性 scope
Space.default_scope_ref : id:circle | null       # 在该 Space 新建 Flow 的默认 scope(hint,非强制)
Space.child_scope_policy: object                  # 子资源 placement/encryption floor,见 §7
Morph.scope_ref         : id:circle | null
```

**关键约束:Flow 永远只有一个 effective encryption scope**。不存在 per-track scope —— 整个 Flow(synthesis、discussion、其他 track)共享同一安全边界,要么都在 Realm-default,要么都在某个 Circle。

### 6.1 Reducer 规则

- `scope_ref` 引用的 Circle MUST `realm_id` 与对象 `realm_id` 一致;否则 `schema_violation`(`reason=circle_realm_mismatch`)。
- `scope_ref` 引用的 Circle MUST `state=active`;否则 `failed_precondition`(`reason=circle_not_active`)。
- `scope_ref=null` 不表示"没有 scope";它表示 Realm-default encryption scope。Reducer MUST 把它物化为 tagged `effective_scope = {kind:"realm", realm_id}`。
- `scope_ref=cx:circle:...` MUST 物化为 tagged `effective_scope = {kind:"circle", realm_id, circle_id}`。
- Reducer 在接受每个 event 时 MUST 固化 `effective_scope`。该值进入 Event envelope、E2EE AAD、MLS governance binding 输入、Anchor/sub-anchor leaf,后续 `scope_ref` 改绑不得重解释旧 event。
- Effective history visibility = 父 Realm policy floor 与 Circle `history_visibility` 的更严格者。Circle MAY 收紧父 Realm,不得放宽父 Realm 的隐私/合规下限。
- 改绑 `scope_ref` 默认 reducer 拒绝(`failed_precondition` `reason=scope_rebind_forbidden`);profile MAY 允许,但 MUST audit-paired high-risk update。所有已存在 Message / 子内容保留其写入时的 `effective_scope` 与旧 scope MLS;新内容才进新 scope。客户端 MUST 把切分前后历史分段展示。
- Structural Relation / position cell 的 `effective_scope` **MUST 不宽于参与端点中最窄的 scope**(取参与端点 scope 集合中最严格者作为关系事实自身的 scope)。具体例:`public Board (Realm-default)` 包含 `private Flow (Circle=HR-Conf)` 时,`contains` 关系事实与其 position cell 的 `effective_scope = Circle:HR-Conf`,**不是** Realm-default;非 Circle 成员看不到该 containment 关系、看不到 private Flow 的 rank/position,也看不到 board 上"此处有隐藏项"的可枚举元数据。

### 6.2 `effective_scope` wire shape

```json
{ "kind": "realm", "realm_id": "cx:realm:0196419b-0000-7000-8000-000000000000" }
```

```json
{
  "kind": "circle",
  "realm_id": "cx:realm:0196419b-0000-7000-8000-000000000000",
  "circle_id": "cx:circle:0196419c-0000-7000-8000-000000000000"
}
```

### 6.3 Space 三个 scope 相关字段语义辨析

| 字段 | 影响对象 | 强制性 | 说明 |
| --- | --- | --- | --- |
| `Space.scope_ref` | Space 对象自身的 metadata 与 structural relation facts | reducer-enforced | Space 自身的 title / parent / rank / contains 事实落在该 Circle scope;**不**使 Space 成为安全边界,Space 仍是 authorization-transparent 容器,只是它的 metadata 被某 Circle 加密。 |
| `Space.default_scope_ref` | 在该 Space 下**新建**的子 Flow / 子 Space | hint(可被显式覆盖) | 客户端默认填入该值,actor 仍可在 create payload 中显式提供另一 `scope_ref`。不强制。 |
| `Space.child_scope_policy` | 任何 placement / move 进入该 Space 的子对象 | reducer-enforced | `allow_any` / `require_e2ee` / `require_same_scope` / `require_scope_ref` 之一,见 §7。是真正的"该 Space 只接受这种 scope 的子对象"硬约束。 |

实现常见错误:把 `default_scope_ref` 当成约束,或把 `scope_ref` 与 `default_scope_ref` 混用。三者各司其职,**不可**互相替代。

## 7. Realm-default scope 与加密覆盖范围

Realm **不会**自动创建默认 Circle。Realm-default encryption scope 是 Realm 自身的 MLS / plaintext / external 加密上下文:

| `effective_scope.kind` | 由什么承载密钥 | 何时使用 |
| --- | --- | --- |
| `realm` | `Realm.encryption_profile` 指定的 Realm-default group / external provider / plaintext mode | `scope_ref=null` |
| `circle` | Circle 独立 MLS group | `scope_ref` 指向 Circle |

`Realm.encryption_profile="mls_rfc9420"` 只说明使用 MLS 作为加密机制,**不**说明哪些 Contrix 字段进入密文。加密覆盖范围由 Realm policy floor 独立声明:

| policy field | enum | 说明 |
| --- | --- | --- |
| `content_encryption_floor` | `allow_plaintext` / `e2ee_required` | `e2ee_required` 时,Flow / Message / Morph / Blob content 的 `effective_scope` MUST 是 MLS-backed:Realm-default MLS 或 Circle MLS。 |
| `metadata_encryption_profile` | `body_only` / `minimal_encrypted` / `full_encrypted` | Realm-wide metadata 加密下限;不得被 Circle、Space 或对象 profile 放宽。 |

`metadata_encryption_profile` 语义:

| value | 明文允许范围 | 必须加密范围 |
| --- | --- | --- |
| `body_only` | Realm / scope 路由字段、object id/kind、必要 causal refs、Flow title / summary / fields、Space parent / rank 等结构 metadata | Message / Morph body、附件正文、明确标注 encrypted 的字段 |
| `minimal_encrypted` | 路由所需 `realm_id`、`effective_scope.kind`、不可逆 routing digest、policy-required subject、必要 causal refs | 用户可读 title / summary / fields、mention / reply excerpt、search token、关系预览、附件文件名 |
| `full_encrypted` | 仅 envelope routing stub、opaque refs、policy/audit 必需的不可逆 commitment | 绝大多数应用 metadata、可逆索引材料、展示标签、结构标题、关系摘要 |

Effective metadata profile = max(parent Realm `metadata_encryption_profile`, Circle `metadata_encryption_floor` if present, Space `child_scope_policy.metadata_encryption_floor` if in placement context, object profile requirement)。比较顺序为 `body_only < minimal_encrypted < full_encrypted`;任何写入若低于 effective profile MUST `failed_precondition`(`reason=metadata_encryption_floor_violation`)。

### 7.1 Space child scope policy

Space 不拥有 membership / policy server / MLS group;`Space.scope_ref` 只是让 Space 自身 metadata 与 structural relation facts 落入某个 existing encryption scope。为了表达"这个 Space 下不允许 plaintext Flow"或"这个 List 只能放 HR Circle 对象",Space MAY 声明 placement policy:

| field | enum / type | 说明 |
| --- | --- | --- |
| `child_scope_policy.kind` | `allow_any` / `require_e2ee` / `require_same_scope` / `require_scope_ref` | 子资源 scope 约束。 |
| `child_scope_policy.scope_ref` | `id:circle` | `kind=require_scope_ref` 时必填。 |
| `child_scope_policy.metadata_encryption_floor` | `body_only` / `minimal_encrypted` / `full_encrypted` | 可选,对该 Space 下新建 / 移入对象施加更严格 metadata floor。 |

Reducer MUST 在 `cx.flow.create`、`cx.flow.move`、`cx.space.parent`、structural `contains` projection 写入时检查 effective Space policy:

- `allow_any`:不额外限制。
- `require_e2ee`:子资源 `effective_scope` 必须 MLS-backed。
- `require_same_scope`:子资源 `effective_scope` 必须等于 Space 自身 `effective_scope`。
- `require_scope_ref`:子资源 `scope_ref` 必须等于指定 Circle。

`Space.default_scope_ref` 只是创建默认值,不是强制约束;强制约束必须用 `child_scope_policy` 表达。

### 7.2 "宽 synthesis + 窄 discussion" 场景如何表达

历史 spec 曾用 `Flow.discussion_realm_ref` 让 Flow 跨两个 Realm 存在(已删除,详见 §11 与本文件序言)。本协议下统一用 **两个 Flow + Relation** 表达,不再有 per-track 安全边界:

```
Flow F_public  (scope_ref = null)              ← 公开 anchor Flow,承载 title/summary/stage/fields
Flow F_private (scope_ref = cx:circle:0196419c-0000-7000-8000-000000000000; short_name=HR-Conf) ← Circle 内 Flow,承载敏感讨论与决策细节
F_private --confidential_discussion_of--> F_public
```

客户端 UI MAY 把这两个 Flow 在视觉上"组合显示"(同卡片标题区 + 切换 tab),但协议层它们是**两个独立对象**,各自有独立的:
- 时间线、消息历史
- 成员、MLS group(F_public 用 Realm-default,F_private 用 Circle MLS)
- watch cell、stage、生命周期
- 投影裁剪规则(无 Circle 成员的 Realm 成员只看到 F_public,看不到 F_private 的存在或活动元数据,符合 §9.1 投递不变量)

`confidential_discussion_of` 是标准 weak-semantic Relation kind(详见 [`relation.md`](./relation.md)),关系事实 SHOULD 存放在 `F_private` 的 Circle scope 内。这样 private 成员能从 private Flow 回到 public anchor;非 Circle 成员不会在 public Flow 上看到"存在一个私密讨论"的可枚举边。

## 8. Capability 与授权评估

Capability actions:

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
    (effective_scope(object).kind == "realm" ∨
     actor ∈ Circle(effective_scope(object).circle_id).members[at object.causal_frontier])
```

其中 `effective_scope(object)` 对 durable Event 使用 immutable `effective_scope`,对 materialized object 使用当前 `scope_ref` 派生出的 tagged scope。capability 决定"能不能做",Circle membership 决定"够不够近"。任一不满足都拒绝。

Circle 管理类 grant MUST 显式约束到 `allowed_circle_refs` / `circle_id` selector,或由 Circle 自身的 admin cell 派生;不得把无约束的 Realm-wide `cx.circle.manage` 当作普通管理权限发放。Realm admin 需要读取 Circle 正文或成员细节时 MUST 走 `cx.circle.audit` + `cx.audit.accessed` 配对路径,且不能获得历史解密 key,除非被正式加入该 Circle。

## 9. Membership 与 Lifecycle

### 9.1 Membership 拓扑

**硬不变量**:

1. `Circle.members ⊆ Realm.members`。reducer 在 `cx.circle.member.state -> active` 时,若 target actor 不是父 Realm `active` member,MUST `failed_precondition` `reason=circle_member_must_be_realm_member`。
2. 父 Realm `cx.member.state -> left/banned` 触发 **reducer-derived** cascade:该 actor 在该 Realm 所有 Circle 的 membership 收敛到 `left`,并触发各 Circle 的 MLS `remove` proposal。不需要 actor 显式写。
3. **Circle 平面化,不允许嵌套**。需要交叉成员关系时,actor 同时属于多个 Circle 即可。
4. Circle admin / moderator 不是 Realm admin 的隐式子集。需要 Circle-local 管理时,必须通过 `cx.circle.admin` 等 Circle-scoped cell 或带 `circle_id` selector 的 capability grant 表达。

Membership transition table:

| from | to | writer |
| --- | --- | --- |
| none / left | invited | `cx.circle.member.manage` |
| invited | active | target actor (`cx.circle.member.add`) 或 `cx.circle.member.manage` |
| none / left | active | target actor only when `join_rule=open`; otherwise `cx.circle.member.manage` |
| active | left | target actor or `cx.circle.member.manage` |
| none / invited / active / left | banned | `cx.circle.member.manage` |
| banned | left / invited | `cx.circle.member.manage` only; self-service MUST fail closed |

### 9.2 Lifecycle cascade

因为对象只有单一 scope,lifecycle cascade 简单:

| 场景 | Realm-level / 未 scope 对象 | scope_ref 指向该 Circle 的对象 |
| --- | --- | --- |
| 父 Realm tombstone | 按 Realm lifecycle 停止 | Circle 全部 tombstone;对象按 Circle lifecycle 停止 |
| Circle tombstone | 不受影响 | 对象写入 MUST fail closed,projection 显示 scope unavailable;`scope_ref` 不会被自动 rewrite |
| 父 Realm 收紧 history visibility | 按新 visibility | Effective visibility 重新计算为更严格值;Circle 不得保持比父 Realm 更宽的历史披露 |
| Circle history visibility 收紧 | 不受影响 | 投影、watch、message read/write 按新状态重新裁剪 |
| `scope_ref` 改绑 | — | 默认拒;profile 允许时 audit-paired,新旧历史分段展示(见 §6.1) |

每个对象有唯一 scope,lifecycle 只需在该 scope 与父 Realm 两层间做判定,不需要历史 spec `discussion_realm_ref` 时代的四象限组合表。

### 9.3 Sync / 投递不变量

> **Scope 投递不变量**:对任意事件 `E` 满足 `E.effective_scope.kind="circle"` 且 `E.effective_scope.circle_id=C`,Sync Service MUST NOT 向不属于 `C.members(at causal frontier of E)` 的 actor 投递 `E` 的 envelope 或 payload。订阅 Realm R 等价于订阅 (R 的 Realm-level events) ∪ (∀C ∈ R.circles, 若 actor ∈ C.members 则 C 的 scoped events,否则 ∅)。

特例:
- `cx.circle.create` 的 authorization shell 是 Realm-level event,但 projection MUST 按 `directory_visibility` 裁剪。`directory_visibility=members` 时,非成员不得看到 Circle title、display、member_count、created_by 或可区分存在性的错误;最多只能看到不可枚举的 opaque commitment。
- `cx.circle.member.state` 仅投递给该 Circle 的成员 + 完成 `cx.circle.audit` / `cx.audit.accessed` 配对的 audit reader。
- `cx.circle.anchor_commit` 是 Realm-level event,但只携带 opaque digest(见 §10),且触发节奏不得泄露 Circle 活动频率。

## 10. MLS / Anchor 集成

### 10.1 MLS

- Circle 拥有独立 MLS group,独立 epoch,独立 key tree。**禁止**从 Realm-default MLS group key 派生 Circle key(否则全 Realm 都能解密)。
- Realm 移除某 actor MUST 触发该 actor 所在所有 Circle 的 MLS `remove` proposal,**并**触发 Realm-default MLS rotate。这是必要的密码学卫生,reducer-enforced。已知运维代价见 §10.3。
- Circle MLS handshake (commit/welcome/proposal) 投递严格限于 Circle 成员,不进入 Realm-default sync 流。
- MLS governance binding 的 scope 从单 `realm_id` 扩展为 `(realm_id, circle_id?)`。Circle commit / welcome / genesis MUST 绑定 `circle_id`、Circle membership frontier、Circle policy root 与父 Realm policy floor frontier;接收端验证时任一不匹配 MUST fail closed。

### 10.2 Anchor stream

- Circle 内事件维护 Circle sub-anchor(只对 Circle 成员可读,记录完整 envelope + payload digest)。
- Circle 按 profile 固定节拍触发 `cx.circle.anchor_commit`,向 Realm Anchor stream 提交 `sub_anchor_head_digest`(不透明 SHA-256)。默认 profile MUST 使用时间节拍 + 空批次 commitment,不得按"每 N 个真实 event"触发,否则会泄露活动频率。低隐私部署若声明 event-count profile,必须显式标为不满足 confidential Circle profile。
- 验证链:Circle member 验证时 `Circle sub-anchor head ↔ Realm anchor commitment ↔ Realm anchor head`,三段闭合。非 Circle 成员只能验证 Realm anchor 完整性。

### 10.3 Realm-member-removal MLS rotate amplification

一次离职 / 踢人因此可能放大为 **N+1 次 MLS group rotation**(N = 该 actor 所在 Circle 数)。这是密码学卫生的必要代价(forward secrecy 与 post-compromise security 要求),不可省。

操作上的缓解策略(profile MAY 实现,**不在 protocol normative 层强制**):

- **批量 rotate**:profile MAY 把短时间窗内的多次 member removal 合并为单次 rotate proposal batch(MLS 协议本身支持 multi-proposal commit)。
- **延迟 rotate 窗口**:profile MAY 声明 rotate 必须在 actor removal 后 ≤ X 完成。X 是该 profile 的 forward secrecy 窗口承诺,MUST 显式公开,且 MUST 不长于 profile 声明的最大可容忍泄露窗口(典型 ≤ 1 小时)。
- **Circle 数量上限的运营建议**:产品上鼓励 Circle 少而稳定(参考 §11 UX 风险);profile MAY 软上限(例如单 Realm ≤ 64 Circle)以约束 rotate amplification 的最坏情况。

替代方案(共享 Realm-default key 派生 Circle key、或惰性 rotate 直到下一次实际通信)会破坏 Circle 的密码学隔离前提,使 Circle 退化为 access-filter,**禁止**采纳。

## 11. UX(为什么 `display` 字段必须 normativize)

Circle 引入的最大实践风险是**跨 Circle 上下文混淆**:用户在 Circle A 的 Flow 工作,被通知 ping 到 Circle B 的 Flow,回复时误以为仍在 A 圈。这是真实泄露发生的瞬间。**因为 Flow 是单 scope 的(§6),所以"我在哪个 Circle"等价于"我在哪个 Flow",这反而让 UX 清晰**:每个 Flow 的视觉身份就是它 scope 的视觉身份,不存在"同一 Flow 内 synthesis 一个色、discussion 另一个色"的混乱。

要让 UI 能可靠区分,以下信号 **MUST** 在 spec 层统一,**不**留给客户端各自发明:

- **颜色 token**:同一 Circle 在 Alice 与 Bob 的客户端上必须呈现一致颜色,否则跨设备 social engineering 攻击成立。
- **短名**:`HR-Conf` 比 `cx:circle:01964...` 可读性高几个量级,且能进入 compose bar 实时显示。
- **符号 / glyph**:无障碍 / 色盲场景的第二信号。

客户端实现 SHOULD 至少做到:

1. Flow 列表行左侧色条 + 行尾徽章 `🔒 <short_name> · <member_count>`(整 Flow 一个 scope,色条不会"半色")。
2. Flow 打开页顶部 banner 用 Circle 颜色;标题旁显示 `<short_name> · <member_count>`。
3. compose 输入框上方常驻 scope 指示 `→ Sending to: [color bar] <short_name> · <member_count>`;切换 Flow 后首次输入时短暂高亮该行。
4. 跨 Circle 导航有可感知转场(banner 颜色变化、breadcrumb 更新);避免"同一空间内滚动"错觉。
5. mention 候选列表中非 Circle 成员置灰并提示"不在此 Circle"。
6. 跨 Circle 引用以虚线框 + "另一信任圈"标识展示,**不**预览内容。
7. "宽 anchor Flow + 窄 discussion Flow" 的组合形态(§7.2)在 UI 上 MAY 渲染为单卡片 + tab 切换,**但** tab 之间切换 MUST 表现为跨 scope 转场(banner 颜色变化 + compose scope 指示更新),不是同 Flow 内不同视图。

## 12. 与既有概念的区分

| 概念 | 含义 | 主要承担 |
| --- | --- | --- |
| **Realm** | federation/identity boundary | membership 主源、policy server、capability registry、federation route、Realm-default MLS group |
| **Circle** | intra-Realm 密码学子边界 | 子集 membership、独立 MLS group、独立 history visibility、scope 投递裁剪 |
| **Group** | principal 集合(capability subject,见 [`realm-and-space.md` §4](./realm-and-space.md)) | 在 capability grant / policy 中作为主体集合;**不**持有密钥 |
| **Space** | navigation 容器 | 导航/分组/Board/List;authorization-transparent;不持有 membership 或 key |

**关键不混淆点**:
- Group 是 **principal 集合**(谁能做事);Circle 是 **资源 scope**(资源在谁的密钥圈下)。两者正交。
- Space 是导航,即使 `Space.scope_ref` 指向 Circle 也只表示"Space metadata 落在该 Circle scope",Space 自身不是边界。

## 13. 规范性引用

- 父 Realm 与 capability 主源:[`realm-and-space.md`](./realm-and-space.md)。
- Flow scope 字段定义:[`flow-and-message.md` §3 / §5](./flow-and-message.md)。
- 跨 scope Relation 规则:[`relation.md` §4](./relation.md)。
- 历史可见性枚举:[`../authz/event-auth-state-resolution.md` §6](../authz/event-auth-state-resolution.md)。
- MLS 加密 / governance binding:[`../crypto-media/encryption-and-audit.md`](../crypto-media/encryption-and-audit.md)。
- Circle schema artifact:`spec/v1/artifacts/schemas/circle.schema.json`。
- 删除的历史字段(协议演化背景):本文件序言;CXP-0007 提案;CHANGELOG。
