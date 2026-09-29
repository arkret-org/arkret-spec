---
title: Circle
status: candidate
normative: true
stability: v1
updated: 2026-07-20
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

**Circle**(`ak:circle:`)是 Realm 内被父 Realm 包裹的**子事件 / 子消息边界**:拥有独立 membership、独立 history visibility、独立投递 / 查询 / projection 裁剪规则，且 `Circle.members ⊆ Realm.members`；但**不**持有 federation identity 或 capability registry。Circle 表达"窄于 Realm 的协作圈"。

Realm 与 Circle 分工正交:Realm 承担 federation / identity boundary,Circle 承担 intra-Realm scoped event boundary。**一对象一 effective scope** 是协议级硬不变量——任何对象 MUST 只属于一个 effective scope(Realm-default 或某个 Circle)。

Circle 在自己的 `ak.mls.genesis` 被接受之前是 plaintext delivery-only scope；该 Genesis 的 accepted RealmCommit 把 Circle 不可逆激活为 MLS-backed cryptographic scope（见 §7）。未激活的 Circle 仍然必须执行 Circle membership / history / delivery 裁剪。

**非目标**:Circle **不是** principal Group 的新名字，也不是 Realm 的"默认子圈"。若实现只需要把某个 capability 授给一组 principal，而不需要独立事件历史、投递裁剪或 Strand scope，应使用 [`realm-and-space.md` §4](./realm-and-space.md) 的 Group / capability constraint / resource selector；不得声明 Circle。Realm 自身仍拥有 **Realm-default scope**；Circle 表示 Realm 内更窄的 scoped event boundary。

## 2. 设计原则

1. **平面化，不嵌套**:Circle 不允许 `parent_circle_ref`。需要交叉成员关系时，actor 同时属于多个 Circle 即可；不需要 hierarchy。这条沿用 [`realm-links.md` §2](./realm-links.md) "link graph not tree" 的教训。
2. **真子集 membership**:`Circle.members ⊆ Realm.members`,reducer 硬约束。
3. **加密激活不可逆**:Circle 的 MLS 激活由本 Circle 自己的 accepted `ak.mls.genesis` 决定，且不可撤销；协议不提供把已激活 Circle 退回明文的分支。
4. **MLS 独立，不可派生**:Circle 激活后，其 MLS group 是独立 epoch 链，**MUST NOT** 从 Realm-default MLS group key 派生 Circle key。
5. **独立历史 ratchet**:Circle 的 `history_access` 由 create 初始化，之后仅允许 `all_history_for_current_members → since_join`；不继承也不受父 Realm `history_access` cap。父 Realm 只提供 current membership intersection。
6. **Circle ≠ Group**:[`realm-and-space.md` §4](./realm-and-space.md) 的 **Group** 表达 principal/actor 集合(capability subject)。Circle 表达资源 / 事件 scope。两个概念正交，不可混淆。

## 3. Circle 对象

Circle 的 canonical schema 为 [`circle.schema.json`](../../artifacts/schemas/circle.schema.json)。与历史/加密相关的
author input 与 materialized projection 分离：

Schema id: `ak.schema.circle.v1`

| 字段 | 规则 |
| --- | --- |
| `schema` | 固定为 `ak.schema.circle.v1` |
| `realm_id` | 父 Realm 的内容寻址 ID，create 后不可变 |
| `title` | Circle 的规范标题 |
| `display` | §4 定义的规范视觉身份 |
| `directory_visibility` | Circle 目录可见性策略 |
| `join_rule` | Circle 加入规则 |
| `history_access` | Circle 自有的单向治理 ratchet；不动态继承父 Realm |
| `mls_group_id` | 仅 materialized MLS Circle；reducer 派生，create payload 禁止 |
| `id` | 仅 materialized；由 create EventId retype |
| `state` | materialized lifecycle，初始为 `active` |
| `created_by` | create Event 的 producer actor |
| `created_at` | create Event 的规范时间 |

Schema 的两个 closed branch 是：create branch 同时禁止 `id/mls_group_id`；materialized branch 要求 `id`，且 MLS
时要求 derived `mls_group_id`，其值按 [`realm-and-space.md` §2.2](./realm-and-space.md) 的唯一派生式从该 Circle 的 `circle` 分支 effective scope 算出（`realm_id` 与 `circle_id` 都进入 key bytes）。Plaintext、standard MLS、exporter MLS 的
closed union 见 [`history-visibility.md`](../governance/history-visibility.md) §2。

self-surface 的 `circle_view`（[`circle-operations.schema.json#/$defs/circle_view`](../../artifacts/schemas/circle-operations.schema.json)）
不携 `member_count`：成员数由同载体 required 的 `member_ids.length` 派生，能拿到 `circle_view` 的 caller 自行计数；
隐私阈由 `circle_view` 本身的可见性承担。`circle_preview` 不携 `member_ids`，只携本节 §9.3 定义的
`member_count_bucket`；这个 Circle bucket 与公开 Realm Directory 没有共同字段或推断关系。

## 4. `display` 字段(标准化视觉身份)

跨客户端一致的 UI 表达是 Circle 安全模型的必要条件（见 §11 UX 论证）：

| 子字段 | 必填 | 类型 | 约束 |
| --- | --- | --- | --- |
| `short_name` | yes | `string` | `^[A-Z][A-Za-z0-9 _-]{0,23}$`；在 `(realm_id, short_name)` 上 reducer 强制唯一(case-insensitive)。冲突 MUST `failed_precondition`（`reason=circle_short_name_taken`，见 [`error-code-registry.json`](../../artifacts/registry/error-code-registry.json)）。Circle 名称空间不为 Sidecar 保留前缀。 |
| `color_token` | yes | `string` | 从 `circle.schema.json#/$defs/display/properties/color_token/enum` 的受控 palette 选；该 schema enum 是 canonical 机器真源。客户端 MUST 映射 token → 主题颜色(浅/深/高对比),**不**得自行重分配 token。`gray_high_contrast` 是承载无障碍/高对比语义的特例 token，并非纯色相；客户端 MUST 把它映射为高对比中性灰主题色。 |
| `symbol` | yes | `object` | `{emoji?: string, glyph?: enum}`；二选一。`glyph` 取 `circle.schema.json#/$defs/display/properties/symbol/properties/glyph/enum` 的受控 snake_case 枚举；该 schema enum 是 canonical 机器真源。客户端 MUST 把 glyph token 映射为本地 icon,MUST NOT 自行扩展未注册 token。 |

**颜色 token 与 symbol 必须在 spec 受控集中**，目的是同一 Circle 在 Alice 与 Bob 的客户端上呈现一致视觉，否则跨设备社会工程攻击成立。

## 5. Event 家族

本表为说明视图；完整集合与 `wire_scope` / `reducer_input` / projection 属性以 [`event-kind-registry.json`](../../artifacts/registry/event-kind-registry.json) 为准。

| event kind | reducer_input | payload 形态 | 说明 |
| --- | --- | --- | --- |
| `ak.circle.create` | yes | full object | 创建 Circle。Circle 的 MLS group 由随后被接受的 `ak.mls.genesis` 单独建立，create 不初始化 group。 |
| `ak.circle.history_access` | yes | `{circle_id,from,to,reason?}` | 专用单向 FSM；create 后仅允许 all_history_for_current_members → since_join。 |
| `ak.circle.update` | yes | `ak.schema.patch.v1`(path 不含 `realm_id` / `profile_ref` / `history_access`) | 改 title / summary / display / directory_visibility / join_rule。 |
| `ak.circle.archive` | yes | object_lifecycle_payload | active → archived。 |
| `ak.circle.restore` | yes | object_lifecycle_payload | archived → active。 |
| `ak.circle.tombstone` | yes | object_lifecycle_payload | terminal；触发 §8 cascade。 |
| `ak.circle.member.state` | yes | `{circle_id, member_id, membership: join\|knock\|leave\|ban, ...}` | 与 `ak.member.state` 复用同一 `membership_state` 四态枚举(`join / knock / leave / ban`)，仅 scope 限定到 Circle；Invite 是独立 pending workflow，不是 membership state。reducer 先校验完整 `member_id: ActorId` 已是父 Realm `join` 成员；`knock` 仅在 `join_rule=knock` 下允许(见 §9.1)。 |

**typed current result 归属与 subject 语义（normative）**：

- `circle_create`（`append-only projection`，`result_selector=null`）是**本 Realm 的 Circle 创建日志**：一个 Realm 内每创建一个 Circle 追加一条 entry，typed current result 本身由 Event envelope 的 `realm_id` 定位。它**不是** per-Circle 的 genesis singleton，因此 MUST NOT 把 `circle_id` 编进 typed current result subject；null subject 的 canonical wire 形态见 [`../conformance/encoding.md` §4](../conformance/encoding.md)。`append-only projection` 的合并不产生冲突值，本 family 也不定义额外的领域冲突语义；Circle 身份唯一性由 `circle_id` 的 typed-id 唯一性与 §3 的 create 校验在 admission 阶段保证，不由状态模型冲突表达。
- `circle_tombstone`（`commit-ordered projection`）是 **per-Circle** 终态槽位，`result_selector={"kind":"coalesce","fields":["payload.circle_id","payload.target_ref"]}`，与 `ak.circle.archive` / `ak.circle.restore` 写入的 `circle_lifecycle` 采用同一 subject 形态。coalesce 的第二项是必需的：三个 Circle lifecycle kind 的 payload class 是 `object_lifecycle_payload`（§5 表），它以 `target_ref` 作为目标对象的**唯一来源**、不携带 `circle_id`，因此只声明 `payload.circle_id` 的 subject 在该 payload 上不可派生。本行给出的是 Circle 自己的 subject 形态，**不是**对既有登记行的引用：`ak.morph.*` / `ak.space.*` / `ak.strand.*` 的同类终态槽位至今没有 `result_writes[]`，而 `ak.relation.tombstone` 明确**不**走这个形态——[`relation.md` §2](./relation.md) 把必填 `relation_id` 定为唯一目标字段，并要求 `target_ref` 出现时返回 `schema_violation`。[`realm-and-space.md` §2.5.1](./realm-and-space.md) 禁止正文对尚未登记的 kind 引用其 `result_writes[]`。它 MUST NOT 使用 null subject——per-Realm 单例槽位只能容纳一个 Circle 的 tombstone，第二个 Circle 会错误复用第一个的安全槽位，导致错误的前置拒绝或覆盖归属。

## 6. 对象 scope 表达

引入字段(跨多个现有对象):

```
Strand.scope_circle_id          : id:circle | null   # null = Realm-default scope
Message.effective_scope       : reducer-derived read projection，必须等于创建 Event.scope_ref
Event.scope_ref               : producer-signed, immutable tagged security scope
Space.scope_circle_id         : id:circle | null   # Space 自身 metadata / scoped structural relation 的可见性 scope
Space.child_scope_policy      : object             # 子资源 placement 约束，见 §7
Morph.scope_circle_id         : id:circle | null
Relation.scope_circle_id      : id:circle | null
Relation.effective_scope      : reducer-derived read projection，必须等于创建 Event.scope_ref
```

**关键约束:Strand 永远只有一个 effective scope**。不存在 per-track scope —— 整个 Strand(synthesis、discussion、其他 track)共享同一事件 / 投递 / history 边界，要么都在 Realm-default，要么都在某个 Circle。

### 6.1 Reducer 规则

- `scope_circle_id` 引用的 Circle MUST `realm_id` 与对象 `realm_id` 一致；否则 `schema_violation`(`reason=circle_realm_mismatch`)。
- `scope_circle_id` 引用的 Circle MUST `state=active`；否则 `failed_precondition`(`reason=circle_not_active`)。
- `scope_circle_id=null` 表示 Realm-default scope，对应签名 `scope_ref={kind:"realm", realm_id}`。
- `scope_circle_id=ak:circle:...` 对应签名 `scope_ref={kind:"circle", realm_id, circle_id}`。
- Reducer 在接受每个 Event 时 MUST 从 payload 与 accepted references 派生 scope，并与 producer-signed `scope_ref` 逐字段比较。后续对象 rebind 不得重解释旧 Event。
- Message 与 Relation 的 read projection MAY 物化顶层 `effective_scope`，但它必须逐字段等于创建 Event 的 `scope_ref`。该 projection 不是可写真相源。
- Effective history access 恰等于 Circle 当前 `history_access`。父 Realm history facet 不进入该值；父 Realm 当前 membership intersection 仍独立生效。Circle 的明文/密文判定只看该 Circle scope 自己是否已有 accepted `ak.mls.genesis`，父 Realm 的激活状态不传递。
- 改绑 `scope_circle_id` 默认 reducer 拒绝(`failed_precondition` `reason=scope_rebind_forbidden`);profile MAY 允许，但 MUST audit-paired high-risk update。所有已存在 Message / 子内容保留其写入时的 `effective_scope` 与旧 scope 的 history / key eligibility；新内容才进新 scope。客户端 MUST 把切分前后历史分段展示。
- Structural Relation / position typed current result 的 `effective_scope` **MUST be no broader than 参与端点中最窄的 scope**(取参与端点 scope 集合中最严格者作为关系事实自身的 scope)。具体例:`public Board (Realm-default)` 包含 `private Strand (Circle=HR-Conf)` 时，`contains` 关系事实与其 position typed current result 的 `effective_scope = Circle:HR-Conf`,**不是** Realm-default；非 Circle 成员看不到该 containment 关系、看不到 private Strand 的 rank/position，也看不到 board 上"此处有隐藏项"的可枚举元数据。
- 当参与端点分别落在同一 Realm 的两个不同 Circle，且没有 Realm-default 端点可作为共同公开侧时，这两个 scope 在 v1 中是**不可比较的并列 scope**。Reducer MUST NOT 选择任一 Circle 作为"更窄者"，MUST NOT 取并集，也 MUST NOT 自动把关系提升到 Realm-default。Structural Relation、position、parent、cascade 或任何会产生 target-side reverse projection 的事实 MUST `failed_precondition`(`reason=scope_incomparable`)。弱语义 reference 若 profile 显式允许，producer MUST 选择单一 source-side `scope_circle_id`，且 projection 对该 scope 外 caller 返回 `locked` / none，不得创建目标侧反向边或可枚举空洞。

**Circle lifecycle 求值基线（normative）**：普通 Event 的 Circle 身份、active 授权实例与 scope 由当前治理 Station 在接纳事务内从已提交 typed state 解析，允许未知撤销的传播窗口；producer 不携带、也不得替换该授权状态。安全命令从 `expected_revision` 派生确切 revision，并在唯一确认执行位置重验所有实际读取的安全 typed current result。不得合并多个同 Realm RealmCommit 为权限 view。

每条 accepted 普通消息都由其 Circle stream 的 RealmCommit 接纳并推进一个 position。分区的非 authority Station 只能耐久排队或转发，不能按缓存暂时接纳、更新共享 projection 或向成员 fanout；current governance Station 在接纳位置按 committed archive/tombstone 与授权状态裁决。缺必要依赖时保持 queued／retryable unavailable，不以到达时间或旧收据保留永久资格。restore 产生新的授权 generation，不能复活旧 generation 中被关闭排除的 Event；作者必须绑定新授权重新签发后继。

对应 conformance vector 是 `ak.vector.circle.lifecycle_admission_barrier.v1`。

### 6.2 `scope_ref` wire shape 与对象 projection

Event wire 只有一个安全作用域字段 `scope_ref`：

1. 对带 `scope_circle_id` 的对象，producer 同时提交对象字段和由它确定的 Event `scope_ref`；
2. Message 等不带独立 `scope_circle_id` 的 payload，producer 从引用对象的已接受 projection 得到 `scope_ref`；
3. reducer 独立派生并比较；不一致返回 `scope_ref_mismatch`，不得替 sender 盖章或修正；
4. 对象 read projection 中的 `effective_scope` 只能从创建 Event `scope_ref` 物化。

Realm scope Event：

```json fragment
{
  "scope_ref": {
    "kind": "realm",
    "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5"
  }
}
```
Circle scope Event：

```json fragment
{
  "scope_ref": {
    "kind": "circle",
    "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
    "circle_id": "ak:circle:AUD2WOhX-Xh47vBHtRJPMRfXRQXGiOWQqOrJGJnE8CaI"
  }
}
```
Reducer 校验顺序(MUST):

1. schema 校验 Event 必有 `scope_ref`，且 `scope_ref.realm_id == realm_id`。
2. 若 `scope_circle_id` 非 null:在 §6.1 规定的 authority-commit 基线中解析对应 Circle——普通 Event 用治理 Station 接纳时的 current authorization，state-changing Event 用领域 payload 的 `expected_revision`——校验 `realm_id` 一致 + `state=active`；不得读取 receiver 当前 projection 代替事件基线。
3. 从 payload/accepted target projection 派生预期 scope，与签名 `scope_ref` 逐字段比较。
4. authorization、fanout、history 与 E2EE 只使用已验证的签名 `scope_ref`；对象 projection 可复制该值但不得反向覆盖 Event。

Conformance fixture 见 `artifacts/fixtures/circle-scope-fixture.json`，覆盖 None→None / 同scope→同scope / None→Some / Some→None / Some(A)→Some(B) 五种 rebind transition 与 schema-violation negative case。

### 6.3 Space 两个 scope 相关字段语义辨析

| 字段 | 影响对象 | 强制性 | 说明 |
| --- | --- | --- | --- |
| `Space.scope_circle_id` | Space 对象自身的 metadata 与 structural relation facts | reducer-enforced | Space 自身的 title / parent / rank / contains 事实落在该 Circle scope;**不**使 Space 成为独立 Realm 边界，Space 仍是 authorization-transparent 容器，只是它的 metadata 被该 Circle 的投递 / history / encryption profile 约束。 |
| `Space.child_scope_policy` | 任何 placement / move 进入该 Space 的子对象 | reducer-enforced | `allow_any` / `require_e2ee` / `require_same_scope` / `require_scope_circle_id` 之一，见 §7。是真正的"该 Space 只接受这种 scope 的子对象"硬约束。 |

实现必须区分 `scope_circle_id`（Space 自身 metadata scope）与 `child_scope_policy`（子对象 placement 硬约束），二者不可互相替代。

## 7. Realm-default scope、Circle scope 与加密覆盖范围

Circle 是独立 effective scope。父 Realm 只提供创建/管理授权与 current
membership intersection；不得提供 history_access、MLS group、epoch、secret、snapshot 或 counter fallback。
Circle 的加密激活点是本 Circle 自己的 accepted `ak.mls.genesis`，与 Realm-default scope 的激活互相独立且均不可逆。
已激活 Circle 的 current tree 仍含按 §9.1 已 effective-invalid 的成员 leaf 时（父 Realm 资格失效），按
[`../crypto-media/encryption-and-audit.md` §2.4.1](../crypto-media/encryption-and-audit.md) 处于 `epoch_update_required`，
停止新的 application send 与 Add，直到移除这些 leaf 的本 Circle winning Commit 生效；父 Realm Event 不推进本 Circle 的
`key_access_revision`。未激活 Circle 立即按 §9.1 effective Circle membership 拒绝 read/write，不生成 MLS transition。

### 7.1 Space child scope policy

Space 不拥有 membership / MLS group;`Space.scope_circle_id` 只是让 Space 自身 metadata 与 structural relation facts 落入某个 existing scope。为了表达"这个 Space 下不允许 plaintext Strand"或"这个 List 只能放 HR Circle 对象",Space MAY 声明 placement policy:

| field | enum / type | 说明 |
| --- | --- | --- |
| `child_scope_policy.kind` | `allow_any` / `require_e2ee` / `require_same_scope` / `require_scope_circle_id` | 子资源 scope 约束。 |
| `child_scope_policy.scope_circle_id` | `id:circle` | `kind=require_scope_circle_id` 时必填。 |

Reducer MUST 在 `ak.strand.create`、`ak.strand.move`、`ak.space.parent`、structural `contains` projection 写入时检查 effective child scope policy:

- `allow_any`:不额外限制。
- `require_e2ee`:子资源 `effective_scope` 必须 MLS-backed。
- `require_same_scope`:子资源 `effective_scope` 必须等于 Space 自身 `effective_scope`。
- `require_scope_circle_id`:子资源 `scope_circle_id` 必须等于指定 Circle。

客户端创建子资源时必须显式选择 `scope_circle_id`；需要强制约束时使用 `child_scope_policy` 表达，不存在 reducer 无法验证的 Space 级默认 hint。

**该 policy 是一个已登记的 typed current result family，不是 create-locked 的对象成员**：family 名为 `space_child_scope_policy`，以 SpaceId 为 subject（special form `space_child_scope_policy:<space_id>`），result schema 见 [`typed-current-result.schema.json#/$defs/space_child_scope_policy_result`](../../artifacts/schemas/typed-current-result.schema.json)。值是本节那个封闭 policy 对象**或 `null`**；`null` 是「未声明」状态，与 `allow_any` 同样「不额外限制」，但 reducer **MUST NOT** 把缺席的成员合成成 `{"kind": "allow_any"}` 对象——投影只能写签名 Event 或 envelope 提供的值，`null` 是缺席状态的唯一登记写法。

写入方恰好两处：

- `ak.space.create.result_writes[]`：签名 `object.child_scope_policy` 存在时写该对象，缺席时写 `null`。
- `ak.space.update.result_writes[]`：**专用的非 patch 写**，条件化在 `space_patch_payload` 顶层的 `child_scope_policy` 成员上。该 payload 用 `propertyNames.not` 禁止通用 `patch` 触及这条路径（含带点路径），并用 `anyOf: [{required: ["patch"]}, {required: ["child_scope_policy"]}]` 把二者分成**两条不同的准入路径**而不是同一件事的两种写法：policy 成员选择 security execution，合并事件是原子的且要求 security finality。成员缺席表示这条 Event 走 metadata patch 分支、在本 family 上零写入，**不**表示 `allow_any`。

[`reducer-managed-path-registry.json`](../../artifacts/registry/reducer-managed-path-registry.json) 里 `child_scope_policy` 一行的 `owner_kind: result_family` / `owner: space_child_scope_policy` 指向的就是上面这两条写。

### 7.2 "宽 synthesis + 窄 discussion" 场景如何表达

需要"公开锚 + 私密讨论"组合时，MUST 用 **两个 Strand + Relation** 表达；Strand 永远单一 scope，不存在 per-track 安全边界:

```
Strand F_public  (scope_circle_id = null)              ← 公开 authority commit Strand，承载 metadata.title / metadata.summary / stage / metadata.fields
Strand F_private (scope_circle_id = ak:circle:AUD2WOhX-Xh47vBHtRJPMRfXRQXGiOWQqOrJGJnE8CaI; short_name=HR-Conf) ← Circle 内 Strand，承载敏感讨论与决策细节
F_private --confidential_discussion_of--> F_public
```

客户端 UI MAY 把这两个 Strand 在视觉上"组合显示"(同卡片标题区 + 切换 tab)，但协议层它们是**两个独立对象**，各自有独立的:
- 时间线、消息历史
- 成员、history visibility、投递 / 查询裁剪；若对应 scope 为 MLS-backed，则各自使用对应 MLS group(F_public 用 Realm-default,F_private 用 Circle MLS)
- watch typed current result、stage、生命周期
- 投影裁剪规则(无 Circle 成员的 Realm 成员只看到 F_public，看不到 F_private 的存在或活动元数据，符合 §9.1 投递不变量)

`confidential_discussion_of` 是标准 weak-semantic Relation kind(详见 [`relation.md`](./relation.md))，关系事实 MUST 存放在 `F_private` 的 Circle scope 内。这样 private 成员能从 private Strand 回到 public authority commit；非 Circle 成员不会在 public Strand 上看到"存在一个私密讨论"的可枚举边。

## 8. Capability 与授权评估

Capability actions:

| action | risk_tier | target event kinds | 说明 |
| --- | --- | --- | --- |
| `ak.circle.create` | medium | `ak.circle.create` | 创建 Circle。**默认不**在普通成员 bundle 中(防止 Circle 滥用稀释 UX)。 |
| `ak.circle.manage` | medium | `ak.circle.update`, `ak.circle.archive`, `ak.circle.restore`, `ak.circle.tombstone` | 管理已存在 Circle。 |
| `ak.circle.member.add` | low | `ak.circle.member.state`(`payload.member_id == envelope.actor_id`，且 transition 合法) | 用户接受邀请、加入 `join_rule=public` 的 Circle 或自助退出；不得自助解除 ban。 |
| `ak.circle.member.manage` | medium | `ak.circle.member.state`(`payload.member_id != envelope.actor_id`) | 邀请/移除他人；Circle admin 持有。 |
| `ak.circle.member.add.others` | high | 同上 + 强制带 `ak.audit.accessed` 配对(与 `ak.strand.watch.set.others` 同模式) | 跨成员代写(罕用)，审计配对。 |
| `ak.circle.audit` | high | 空(read-only)，配对 `ak.audit.accessed` | 不属于 Circle 的 Realm admin 读取 Circle 元数据 / activity rollup 的审计权。 |

**授权评估两层 AND**:

```
authorized(actor, action, object) ⇔
    capability_grant(actor, action) ∧
    (effective_scope(object).kind == "realm" ∨
     actor ∈ Circle(effective_scope(object).circle_id).members[at object.causal_checkpoint])
```

其中 `effective_scope(object)` 对 durable Event 使用 immutable signed `scope_ref`，对 materialized object 使用创建 Event scope 或当前 `scope_circle_id` 的规范派生。capability 决定能否执行，Circle membership 决定作用域资格；任一不满足都拒绝。

Circle 管理类 grant MUST 显式约束到 `allowed_circle_ids` / `circle_id` selector，或由 Circle 自身的 admin typed current result 派生；不得把无约束的 Realm-wide `ak.circle.manage` 当作普通管理权限发放。Realm admin 需要读取 Circle 正文或成员细节时 MUST 走 `ak.circle.audit` + `ak.audit.accessed` 配对路径；MLS-backed Circle 中还不能获得历史解密 key，除非被正式加入该 Circle。Plaintext Circle 不存在历史解密 key，但仍不得绕过 Circle membership / audit gate 直接投递或查询。

**Realm 管理权交接与 Circle 隔离（normative）**：Realm ownership / admin capability transfer 只转移 Realm 治理能力，MUST NOT 隐式创建任何 `ak.circle.member.state`、MUST NOT 把接手管理员加入既有 Circle、MUST NOT 赋予既有 Circle 的历史读取 / 解密资格，也不是交接前必须完成的前置条件。若产品希望新管理员继续创建新的 Circle，应在交接 bundle 中显式授予 `ak.circle.create`（或等价的产品管理员角色中显式包含该 action）；这不影响任何既有 Circle。若需要新管理员接管某个既有 Circle 的 lifecycle / membership 管理，必须对该 Circle 显式签发带 `allowed_circle_ids` 的 `ak.circle.manage` / `ak.circle.member.manage` grant；若需要其参与内容讨论，则必须按 §9.1 写入明确的 Circle membership transition。实现 MAY 在交接向导中提示“可选移交哪些 Circle 的管理/成员资格”，但 MUST NOT 要求“把目标管理员加入所有 Circle”作为 Realm admin transfer 的协议条件。

## 9. Membership 与 Lifecycle

### 9.1 Membership 拓扑

**硬不变量**:

1. `Circle.members ⊆ Realm.members`，且每个 Circle `join` 绑定一个确切的父 Realm join 实例。`ak.circle.member.state` 的 `membership="join"` payload MUST 携带 producer 签名的 `parent_membership_revision`：同一完整 `member_id` 在父 Realm `member_state` typed current result 的 exact `revision`（`{commit_id, stream_position}`），即接纳建立该 member 当前父 Realm `join` 的 Event（`ak.member.state{join}` 或 `ak.invite.accept`）的那条 Realm stream RealmCommit。其它 transition MUST NOT 携带该字段；缺失或多带均为 `schema_violation`。治理 Station 在接纳事务内于同一 cut 读取父 Realm 该 member 的 current `member_state`：值不是 `join`，或其 `revision` 与 payload 的 `parent_membership_revision` 不逐字段相等时，MUST `failed_precondition` `reason=circle_member_must_be_realm_member` 并零写入。该字段是 producer 签名输入，不是 reducer 派生成员：replica 与 snapshot 消费方无法重算跨 stream 的接纳基线，只能读取签名值。它取自任何父 Realm 成员可读的 typed current，producer 无须读取可能位于自身 readable floor 之下的父 join Event 原文。
2. **Effective Circle membership（normative）**：actor 在 Circle C 为 effective member，当且仅当在同一 durable cut 上同时满足：(a) C 的 canonical `circle_member_state` current 为 `join`；(b) 父 Realm 该 member 的 current `member_state` 为 `join`，其 `source_stream_ref` 是父 Realm stream，且 `revision` 逐字段等于 (a) 值中的 `parent_membership_revision`；(c) 父 Realm effective membership 的其余条件（例如 Agent 的 controller binding、lifecycle 与 provision/accountability 绑定）成立。所有 Circle 授权、投递、history、MLS material 与 send gate 中的「Circle member」均指此判定。

   父 Realm `leave`／`ban` 一经接纳，父 current 的 revision 即改变，该 actor 在该 Realm 全部 Circle 的旧 `join` 从同一 Realm Commit 起同时 effective-invalid；该门不等待任何清理 Event，也不依赖缓存。父 Realm 之后的 rejoin 产生新的 RealmCommit 与新 revision，旧 Circle `join` 永远不因此复活。只有显式写入携带新 `parent_membership_revision` 的新 Circle `join` 才恢复资格；canonical Circle 值仍为旧 `join` 时，因 `join -> join` 非法，恢复先由本人或 Circle 管理者写显式 `leave`，再写新的 `join`。reducer、Station 与数据库 trigger MUST NOT 合成 Circle `leave`，MUST NOT 改写 canonical Circle 行或其 revision；Circle Event 只在 Circle stream 提交，父 Realm Commit 的 position 不得冒充 Circle stream position。已激活 MLS 的 Circle 如何移除失效 leaf 见 §7 与 [`../crypto-media/encryption-and-audit.md` §2.4.1](../crypto-media/encryption-and-audit.md)；未激活 Circle 无 MLS transition。

   **接纳与复制边界（normative）**：current governance Station 在每个 Circle stream 接纳事务中以已 committed 的父 Realm current 求值上式，并立即阻止 effective-invalid actor 的新 live 投递、读取与写入；分区的非 authority Station 只能排队／转发，不能按缓存临时接纳。判定比较的是 Commit 身份：`commit_id` 是完整 RealmCommit body 的内容寻址摘要，已承诺 Event、stream 与 position，它与父 Realm stream 上的 position 一起逐字段比较；Realm stream 与 Circle stream 各自从 0 编号，数值相同的 position 互不相关，MUST NOT 互认，也不得用跨 stream 的 position 大小、墙钟或到达顺序推断父资格。本地 Realm 副本是否已覆盖 `parent_membership_revision` 可以按同一 Realm stream 的 position 判断，这是同流比较。

   **Snapshot、committed replication 与冷启动（normative）**：该判定只依赖同一 durable cut 的两条已有 typed current——父 Realm `member_state` 与含 `parent_membership_revision` 的 `circle_member_state`；不存在也不需要另一份持久派生关闭事实。签名 Snapshot 的 `current_state_entries` 取自同一 cut，消费方直接比较；committed replication 与冷启动 hydrate 装入同一组 typed current 后按同一式子比较，不需要读取父 join Event 原文。replica 的 Realm 副本尚未覆盖该 revision（Circle 先到、Realm 滞后），或本地父 current 已是另一 revision 时，该 actor 判定为 effective-invalid 并失败关闭：本地不据此授权 Circle 读取、投递、MLS material 或写入，直到 Realm 副本推进后重新求值；已 accepted 的 Circle Event 与 canonical 行照常保存，不改写、不丢弃。成员站以 Circle join 开流的 bootstrap 规则见 [`../sync/federation.md` §4.1.1](../sync/federation.md)。历史 cut 的成员连续性见 [`../governance/history-visibility.md` §3.1](../governance/history-visibility.md)。

   对应 conformance vector 是 `ak.vector.circle.parent_membership_revision.v1`。

Circle membership 使用 [`common-fields.md` §4.5](./common-fields.md#45-membership-fsmnormative) 的共享 materialized membership FSM，完整 `member_id: ActorId` 是 typed current result key。申请正文 MUST NOT 进入 member-state Event；部署若需附加私密材料，必须通过独立的加密扩展通道传输。

Circle 与 Realm 共用 `$defs/membership_state` 单一枚举真源和同一 transition graph；差异只由 scope guard 表达，不再维护第二张转换表。`join -> join` 与其余 same-state transition 一样非法。membership 与物理 lifecycle state 正交，不受 [`common-fields.md` §5.1](./common-fields.md) 的 lifecycle same-state 规则覆盖。需要幂等重试的 producer MUST 基于当前 membership state 重新提交合法 transition，而非重放 same-state 写入。

**`expected_membership` 的三态语义（normative）**：`ak.circle.member.state` 的可选
`expected_membership` 是并发写入下的乐观保护，与 transition guard 正交，且三种 wire 形态互不等价：

- **省略**：不施加 CAS。合法性完全由本节 FSM transition guard 判定。这与
  [`strand-and-message.md` §2](./strand-and-message.md) 的 `expected_default_strand_id` 不同——
  那里的 typed current result 是无 FSM guard 的 `current-value projection`，省略必须归一为 `expected_revision null`；这里的非法转移
  已由 guard 拒绝，因此省略不会导致无条件覆盖。
- **显式 `null`**：断言该 actor 当前在本 Circle **没有任何 membership 记录**，即这是首次写入。
  已存在任意 membership 时 reducer MUST `failed_precondition`。
- **具体枚举值**：断言当前 membership 逐字等于该值，不等时 MUST `failed_precondition`。

因此实现 MUST NOT 把"省略"与"显式 `null`"折叠为同一状态：前者放弃 CAS，后者是一个会失败的断言。
producer 类型系统 MUST 保留 Missing / Null / Value 三态，普通二态 optional 会丢失该区分。

### 9.2 Lifecycle cascade

Circle lifecycle 的转换与 reason_code 见本文件 Circle lifecycle 合同入口。
Circle 不定义 `ak.circle.freeze` 或 `ak.circle.destroy`；父 Realm 的 `freeze` / `destroy` 在父边界统一生效，Circle 不持有独立 federation identity 或 successor 语义。

因为对象只有单一 scope,lifecycle cascade 简单:

| 场景 | Realm-level / 未 scope 对象 | scope_circle_id 指向该 Circle 的对象 |
| --- | --- | --- |
| 父 Realm tombstone | 按 Realm lifecycle 停止 | Circle 的 canonical lifecycle typed current result 保持原值，但 effective lifecycle 由父 Realm terminal Event 派生为 `realm_terminal`；不得合成 `ak.circle.tombstone` 或未登记的 Circle typed current result write。Circle 与其对象停止，后续写入统一拒绝 active `failed_precondition`；tombstone 到 successor Realm 时不会自动迁移 Circle membership / MLS key / history grant |
| 父 Realm freeze | 所有非豁免新写入按 Realm §2.6.0 拒绝 `realm_frozen` | Circle-scoped 新写入同样按 `realm_frozen` 拒绝；Circle 本身不定义独立 freeze，也不得用 Circle capability 绕过父 Realm freeze |
| 父 Realm archive | 按 Realm 默认隐藏 / 只读投影，可由 Realm restore 恢复 | Circle 与其对象遵循父 Realm archive 的默认隐藏 / 只读投影；不额外 tombstone、不改 membership / MLS eligibility，Realm restore 后恢复到 Circle 自身 lifecycle 决定的状态 |
| Circle archive | 不受影响 | receiver 获知 archive 关闭后，新写入 MUST fail closed（`failed_precondition`, `reason=circle_not_active`），**含新建以该 archived Circle 为 `scope_circle_id` 的对象**；此前暂时接纳的 Event 按关闭集合重算历史资格。既有对象保持历史可读/可审计投影，但不得继续追加 Message / Morph / structural Relation / position update，直到 `ak.circle.restore` 使 Circle 恢复 active |
| Circle tombstone | 不受影响 | receiver 获知 tombstone 关闭后，新对象写入 MUST `circle_not_active`；此前接纳的历史按关闭集合重算。projection 显示 scope unavailable；`scope_circle_id` 不会被自动 rewrite |
| 父 Realm 修改 history access | 不改 Circle history access | Circle 保持自身当前 facet；仅父 Realm current membership intersection 继续生效，Circle 的 MLS 激活状态独立 |
| Circle history visibility 收紧 | 不受影响 | 投影、watch、message read/write 按新状态重新裁剪 |
| `scope_circle_id` 改绑 | — | 默认拒；profile 允许时 audit-paired，新旧历史分段展示(见 §6.1) |

每个对象有唯一 scope,lifecycle 只需在该 scope 与父 Realm 两层间做判定，不存在跨双 scope 的组合表。

父 Realm terminal gate 的判定优先于 Circle 自身 lifecycle gate。因此父 Realm已
tombstone 时，即使 Circle canonical state 仍为 `active`，receiver 也 MUST 返回
`failed_precondition`，不得输出 reserved `realm_terminal_state` reason 或 `circle_not_active`；该优先级保证所有
实现对同一父 Realm terminal basis 产生相同错误形态。

**`ak.circle.restore`（archived → active）后置条件（normative）**：archived 是可逆中间态，restore 的 membership / MLS 后置条件如下：

- **archive 期间父资格失效仍生效**：archived Circle **不冻结** membership。archive 期间父 Realm 被接纳的 `ak.member.state -> leave/ban` MUST 照常按 §9.1 硬不变量 2 使该 actor 在该 archived Circle 的旧 `join` 立即 effective-invalid（canonical 行不被改写）；restore 后该 Circle 的 effective membership 仍按 §9.1 判定式求值，不存在「archive 期间漏掉的 leave/ban 在 restore 后才补」的窗口。
- **MLS-backed Circle 的 epoch 与 rotate**：archive 期间 Circle 的 MLS group **不暂停**成员变更语义——失效 leaf 使 send gate 按 [`../crypto-media/encryption-and-audit.md` §2.4.1](../crypto-media/encryption-and-audit.md) 进入 `epoch_update_required`，移除它们的 repair Commit 照常可提交（与 plaintext Circle 只做 delivery 裁剪相对）。`ak.circle.restore` 本身**不**强制引入额外 MLS rotate：若 archive 期间已有 winning Commit 移除全部失效 leaf，则 restore 不重复 rotate；否则 restore 后 send gate 仍保持 `epoch_update_required`，恢复加密写入前 MUST 先由该 repair Commit 移除这些 leaf，保证 forward secrecy / post-compromise security 不因 archive→restore 出现空洞。
- restore 不改变既有对象的 `effective_scope` 与历史 key eligibility；restore 只解除 §9.2 表「Circle archive」行的写入冻结（`circle_not_active`），使新 Message / Morph / structural Relation / position update 可继续追加。

### 9.3 Sync / 投递不变量

> **Scope 投递不变量**:对任意事件 `E` 满足 `E.effective_scope.kind="circle"` 且 `E.effective_scope.circle_id=C`,Station sync surface MUST NOT 向在 `E` 的 committed Circle-stream position 处不属于 `C.members`（按 §9.1 effective Circle membership 求值）的 actor 投递 `E` 的 envelope 或 payload。订阅 Realm R 等价于订阅 (R 的 Realm-level events) ∪ (∀C ∈ R.circles, 若 actor ∈ C.members 则 C 的 scoped events，否则 ∅)。

特例:
- `ak.circle.create` 的 authorization shell 是 Realm-level event，但 projection MUST 按 `directory_visibility` 裁剪。`GET /_arkret/self/circles/{circle_id}` 的成功载体是闭合 `circle_read_view=oneOf(circle_view,circle_preview)`；list 的唯一数组键是 `circles`，元素使用同一 union。只有同一 accepted cut 下同时属于父 Realm 与 Circle 的 caller 才得到完整 `circle_view`。`directory_visibility=members` 时，其他 caller 的 GET 与不存在 Circle 一律返回现有 `not_found` 错误 envelope，list 不列该项；不发可枚举的成功 locked stub。原生 Sidecar 的独立存在性隐私仍由 `ak.vector.sidecar.existence_privacy.v1` 覆盖。
- `directory_visibility=realm_members` 且 Circle `state=active` 时，属于父 Realm 但不属于该 Circle 的 caller 只得到闭合 `circle_preview`：`circle_id`、`realm_id`、`visibility="realm_members"`、`display={color_token,symbol}`、`member_count_bucket`、`join_rule`、`opaque_commitment`，不得携带 title、summary、short_name、`member_ids`、成员 DID、created_by、join history 或私有 Event 引用。非父 Realm 成员、未授权 caller、不可见/不存在对象的 GET 同一 `not_found` 错误代码和字段集合；list 均省略。`archived`/`tombstoned` 的非成员预览也省略。当前 v1 未登记 Circle search operation。
- `member_count_bucket` 按同一读事务中 §9.1 **effective Circle membership** 成立的人数计算（只计 `effective_at <=` 本次读 cut 的有效成员），固定区间为 `0`、`1`、`2-3`、`4-7`、`8-15`、`16-31`、`32-63`、`64-127`、`128+`；不输出原始人数。`opaque_commitment` 是 64 位小写十六进制 SHA-256，输入字节精确为 UTF-8 `ak.circle.preview.v1`、单字节 `0x00`、wire `realm_id` UTF-8、单字节 `0x00`、wire `circle_id` UTF-8。它只承诺预览中已公开且不可由标题、短名或成员枚举的高熵 ID，跨 caller/读次稳定；不得用它证明私有 Circle Event 内容。
- 不可见与不存在的 GET 必须使用同一代码、字段集合与 `circle_locked_v1` 处理类别；实现不得依据存在性设置不同延时、重试或缓存响应类别。此处理类别不是固定毫秒值或密码学恒时承诺；验收比对完整错误 envelope 与路径处理类别，并对显著可区分的延时分支作负向检查。list 对这两者均省略且不得输出计数或占位。普通 Circle 的这两项要求分别由 `ak.vector.circle.directory_visibility_members_indistinguishable.v1` 和 `ak.vector.circle.directory_visibility_realm_members_indistinguishable.v1` 覆盖。
- `ak.circle.member.state` 仅投递给该 Circle 的成员 + 完成 `ak.circle.audit` / `ak.audit.accessed` 配对的 audit reader。

## 10. 加密 / RealmCommit 集成

每个 Circle 都有独立的 authority commit stream，Circle Event 只由该 stream 的 RealmCommit 排序与确认；父 Realm stream 与 Circle stream 之间不存在 predecessor 关系。未激活 Circle 不存在 MLS group。已激活 Circle 拥有自己的 canonical group、Genesis/Commit、Welcome delivery、leaf 与 snapshot；key-access revision 固定在自己的 Genesis。`history_access` 只可由专用
`ak.circle.history_access` Event 从 `all_history_for_current_members` 单向收紧到 `since_join`，立即作用于历史交付，
且不进入 MLS key-access revision；不存在 epoch ceiling 或 activation-time policy snapshot。
MLS secret 只保留在成员设备本地，不提供 backup、network delivery 或恢复密钥。

## 11. Scope-identity UX safety invariants

Circle 引入的最大实践风险是**跨 Circle 上下文混淆**:用户在 Circle A 的 Strand 工作，被通知 ping 到 Circle B 的 Strand，回复时误以为仍在 A 圈。这是真实泄露发生的瞬间。**因为 Strand 是单 scope 的(§6)，所以"我在哪个 Circle"等价于"我在哪个 Strand"，这反而让 UX 清晰**:每个 Strand 的视觉身份就是它 scope 的视觉身份，不存在"同一 Strand 内 synthesis 一个色、discussion 另一个色"的混乱。

要让客户端能可靠区分 scope，以下信号 **MUST** 在 spec 层统一，**不**留给客户端各自发明:

- **颜色 token**:同一 Circle 在 Alice 与 Bob 的客户端上必须呈现一致颜色，否则跨设备 social engineering 攻击成立。
- **短名**:`short_name`(如 `HR-Conf`)相比裸 Circle ID（如 `ak:circle:01964...`）更易人工识别；客户端 SHOULD 显示 `short_name` 以辅助 scope 识别。
- **符号 / glyph**:无障碍 / 色盲场景的第二信号。

本节是 **client-presentation safety conformance**，不是 Circle wire shape 或 headless reducer contract。以下不变量只适用于**向人类用户呈现写入、回复、转发、引用、mention、邀请或导航入口的客户端 surface**。纯 headless SDK、webhook worker、自动化 agent runtime 若不向人类呈现这些入口，则本节呈现义务不适用；但它们向上层 UI 暴露 Circle 数据时 MUST 原样提供 `display` 与 effective scope，使实际呈现方能够履行本节。适用的客户端实现 MUST 满足以下可测试不变量。具体控件布局、文案与视觉形式是实现自由。

1. 在任何会导致写入、回复、转发、引用、mention 或发送通知的入口，当前 effective scope MUST 可被用户区分；Circle scope 至少呈现 `display.color_token`、`display.symbol` 与 `display.short_name` 中的两个互补信号。
2. Plaintext Circle MUST 使用不会暗示 E2EE 的 glyph、标签或披露语义；MLS-backed Circle MAY 使用 lock/shield 类语义，但不得让 plaintext scope 与 E2EE scope 看起来等价。
3. 跨 Circle 导航或同一 surface 内切换不同 scope 时，客户端 MUST 让用户感知这是跨 scope 转场；不得表现成同一 Strand 内的普通滚动或普通 tab 内容切换。
4. Mention / invite / add-recipient 等候选交互 MUST 区分 Circle member 与非 member；不得暗示非成员会收到 Circle-scoped 内容。
5. 跨 Circle 引用必须标识为“另一 Circle / 另一协作圈 / 另一作用域”或等价语义，**不得**使用“信任圈”措辞，且不得预览调用者无权访问的内容。
6. "宽 authority commit Strand + 窄 discussion Strand" 的组合形态(§7.2)在 UI 上 MAY 渲染为同一工作 surface,**但**两个 Strand 之间的切换 MUST 表现为跨 scope 转场，不得表现为同一 Strand 内不同视图。

### 11.1 Agent Sidecar 与 Circle 的强制分离

Agent Sidecar 使用 [`sidecar.md`](./sidecar.md) 定义的原生 `scope_ref.kind="sidecar"`。Circle reducer、
membership、MLS group、目录与 lifecycle 均不得为 Sidecar 创建隐藏或系统管理对象。Sidecar 的 private-view
映射与显式发布规则也不得用于 Circle 内容；Circle scope 的信息只能按本文件定义的 membership/history/
delivery 边界流动。

## 12. 与既有概念的区分

| 概念 | 含义 | 主要承担 |
| --- | --- | --- |
| **Realm** | federation/identity boundary | membership 主源、capability registry、federation route、Realm-default MLS group |
| **Circle** | intra-Realm 子事件 / 子消息边界 | 子集 membership、独立 history visibility、scope 投递 / 查询 / projection 裁剪；可选独立 MLS group |
| **Group** | principal 集合(capability subject，见 [`realm-and-space.md` §4](./realm-and-space.md)) | 在 capability grant / policy 中作为主体集合；**不**持有密钥 |
| **Space** | navigation 容器 | 导航/分组/Board/List;authorization-transparent；不持有 membership 或 key |

**关键不混淆点**:
- Group 是 **principal 集合**(谁能做事);Circle 是 **资源 / 事件 scope**(哪些事件进入哪个成员圈，必要时由哪组密钥保护)。两者正交。
- Space 是导航，即使 `Space.scope_circle_id` 指向 Circle 也只表示"Space metadata 落在该 Circle scope",Space 自身不是边界。

## 13. 规范性引用

- 父 Realm 与 capability 主源:[`realm-and-space.md`](./realm-and-space.md)。
- Strand scope 字段定义:[`strand-and-message.md` §3 / §5](./strand-and-message.md)。
- 跨 scope Relation 规则:[`relation.md` §4](./relation.md)。
- 历史可见性枚举与 canonical 语义：[`../governance/history-visibility.md`](../governance/history-visibility.md)。
- MLS 加密 / governance binding:[`../crypto-media/encryption-and-audit.md`](../crypto-media/encryption-and-audit.md)。
- Circle schema artifact:`spec/v1/artifacts/schemas/circle.schema.json`。


### Circle lifecycle 合同入口

`circle` 的 lifecycle 以 contract registry 中对应 typed current result family 的 `transition_contracts` 与 Event `result_projection` 为转换真源；本节只定义对象组合规则，不复制转换表。archive 只从 active、restore 只从 archived 发起；非法源分别返回 `circle_not_active` / `circle_not_archived`；终态操作对已终态对象返回 `circle_already_terminal`。新的 same-state 写入不当作幂等成功，已接受 Event 的 exact replay 仍沿通用幂等合同处理。普通 update 只允许 active，不能隐式恢复对象。对象 redaction/terminal 优先于可逆 archive，restore 不能恢复已清除内容。缺对象或依赖时按 common-fields §5.1 保留 pending/replay。
