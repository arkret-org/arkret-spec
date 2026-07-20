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

**Circle**(`ak:circle:`)是 Realm 内被父 Realm 包裹的**子事件 / 子消息边界**:拥有独立 membership、独立 history visibility、独立投递 / 查询 / projection 裁剪规则，且 `Circle.members ⊆ Realm.members`；但**不**持有 federation identity、Policy Server 或 capability registry。Circle 表达"窄于 Realm 的协作圈"。

Realm 与 Circle 分工正交:Realm 承担 federation / identity boundary,Circle 承担 intra-Realm scoped event boundary。**一对象一 effective scope** 是协议级硬不变量——任何对象 MUST 只属于一个 effective scope(Realm-default 或某个 Circle)。

Circle 可以是 plaintext delivery-only scope，也可以是 MLS-backed cryptographic scope。是否必须启用 MLS 由父 Realm 的 `encryption_profile`、`content_encryption_floor` 与 Circle 自身 `encryption_profile` 共同决定（见 §7）。若父 Realm 或 policy 要求 E2EE，Circle MUST 使用独立 MLS group；若父 Realm 允许明文，Circle MAY 使用 `encryption_profile=none`，但它仍然必须执行 Circle membership / history / delivery 裁剪。

**非目标**:Circle **不是** principal Group 的新名字，也不是 Realm 的"默认子圈"。若实现只需要把某个 capability 授给一组 principal，而不需要独立事件历史、投递裁剪或 Strand scope，应使用 [`realm-and-space.md` §4](./realm-and-space.md) 的 Group / capability constraint / resource selector；不得声明 Circle。Realm 自身仍拥有 **Realm-default scope**；Circle 表示 Realm 内更窄的 scoped event boundary。

## 2. 设计原则

1. **平面化，不嵌套**:Circle 不允许 `parent_circle_ref`。需要交叉成员关系时，actor 同时属于多个 Circle 即可；不需要 hierarchy。这条沿用 [`realm-links.md` §2](./realm-links.md) "link graph not tree" 的教训。
2. **真子集 membership**:`Circle.members ⊆ Realm.members`,reducer 硬约束。
3. **加密不降级父 Realm floor**:Circle 的 `encryption_profile` 可为 `none` 或 `mls_rfc9420`，但不得低于父 Realm / policy 的内容加密下限；E2EE Realm 或 `content_encryption_floor=e2ee_required` 下 MUST 为 `mls_rfc9420`。
4. **MLS 独立，不可派生**:当 Circle 为 `mls_rfc9420` 时，其 MLS group 是独立 epoch 链，**MUST NOT** 从 Realm-default MLS group key 派生 Circle key。
5. **不放宽父 Realm policy**:Circle 的 history visibility / metadata encryption floor **只能收紧，不能放宽**父 Realm policy floor。
6. **Circle ≠ Group**:[`realm-and-space.md` §4](./realm-and-space.md) 的 **Group** 表达 principal/actor 集合(capability subject)。Circle 表达资源 / 事件 scope。两个概念正交，不可混淆。

## 3. Circle 对象

Schema id: `ak.schema.circle.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:circle` | `ak:circle:<uuid>`(UUIDv7) | Circle ID。 |
| `schema` | yes | `ak.schema.circle.v1` | 固定。 | 对象 schema。 |
| `realm_id` | yes | `id:realm` | create-locked;Circle 永远属于一个 Realm，不可改绑。 | 归属 Realm(父安全/联邦边界)。 |
| `profile_ref` | no | `profile id` | create-locked；必须匹配 `^ak\.profile\.[a-z0-9_.-]+\.v1$`。普通 Circle 省略；profile-specific 创建路径必须写入其规范注册的 profile id。 | Circle 的语义 profile 判别器；目录、查询与客户端用它执行 profile-specific fail-closed 过滤，不得依赖 title、short_name 或 relation 推断。Agent Sidecar 是独立对象，不使用 Circle `profile_ref` 表达。 |
| `title` | yes | `string` | 1..256 chars。 | 人类可读名称。 |
| `summary` | no | `string` | ≤2048 chars。 | 简短说明(渲染在 banner / 详情)。 |
| `display` | yes | `object` | 见 §4。 | **跨客户端一致**的视觉身份字段；只对 `directory_visibility` 允许的 actor 投影。 |
| `directory_visibility` | yes | `enum(members, realm_members)` | 必填；推荐初始值 `members`（客户端预填，非 wire 缺省）。 | Circle 元数据可发现性。`members` 时非成员不得看到 title / display / member_count;`realm_members` 仅披露目录元数据，不授予事件或历史访问。 |
| `join_rule` | yes | `enum(invite, knock, public)` | 必填；推荐初始值 `invite`（客户端预填，非 wire 缺省）。 | 与 Realm 入口模式共用词形。Circle 的 `public` 仅允许父 Realm `join` 成员自助加入(`membership=join`)，不改变全局 discoverability；`knock` 触发申请/批准流(见 §9.1 transition table)；`invite` 只能由 Circle 管理员加入或邀请。 |
| `history_visibility` | yes | `enum(world_readable, shared, invited, joined, restricted)` | 必填；推荐初始值 `invited`（客户端预填，非 wire 缺省）。语义沿用 [`../governance/history-visibility.md`](../governance/history-visibility.md)。 | Circle 自己的历史可见性，但 effective visibility **不得宽于父 Realm 当前 policy floor**。 |
| `content_encryption_floor` | no | `enum(allow_plaintext, e2ee_required)` | 省略时继承父 Realm `content_encryption_floor`。effective = max(父 Realm, Circle)；只能收紧、不得放宽父 Realm floor，且 effective floor 是单向 ratchet(见 §7)。`e2ee_required` 仅在 `encryption_profile=mls_rfc9420` 时有意义；`encryption_profile=none` 的 Circle MUST 保持 `allow_plaintext`。 | Circle 内对象的 content 加密下限。 |
| `metadata_encryption_floor` | no | `enum(allow_plaintext, e2ee_required)` | 省略时继承父 Realm `metadata_encryption_floor`。effective = max(父 Realm, Circle)；只能收紧、不得放宽父 Realm floor，且 effective floor 是单向 ratchet(见 §7)。 | Circle 内对象的 metadata 加密下限，与 `content_encryption_floor` 对称；`e2ee_required` 时用户可读 metadata 进 `encrypted_metadata`。`encryption_profile=none` 时不得声明高于实际可执行能力的 metadata 加密保证。 |
| `agent_participation` | no | `object{native_agent:{reply, accept_third_party_mention, act_on_behalf: boolean}}` | 整个 object 省略时继承父 Realm `agent_participation` ceiling。`native_agent` 存在但某些 bool 位省略时，每个省略位独立继承父 Realm 对应位；只有显式位参与 Circle 自身声明。每一位只能收紧、不得放宽父 Realm ceiling（违反返回 `failed_precondition`，`reason="agent_participation_ceiling_widen"`，见 §7），并可由内层 Strand 继续收紧。Realm、Circle、Strand 使用同一带轴 wire 形态；旧扁平三位不是 v1 wire，见 [`common-fields.md` §4.4](./common-fields.md#44-agent_participation-wire-形态normative)。详见 [`../authz/capabilities.md` §5.4](../authz/capabilities.md)。 | native personal agent 在该 Circle scope 内的参与上限。 |
| `encryption_profile` | yes | `enum(none, mls_rfc9420)` | create-locked。父 Realm `encryption_profile=mls_rfc9420` 或 effective `content_encryption_floor=e2ee_required` 时 MUST 为 `mls_rfc9420`；父 Realm 允许明文时 MAY 为 `none`。未来 MLS 版本 / PQ-MLS / external provider 必须显式扩展 schema。 | Circle 内容加密形态。 |
| `mls_group_ref` | conditional | `ref:mls` | 条件 `encryption_profile=mls_rfc9420`：满足时由 `ak.circle.create` reducer 派生、scope 绑定 `(realm_id, circle_id)`，`encryption_profile=none` 时 MUST NOT exist。**reducer 派生，actor MUST NOT 携带**（actor-supplied create payload 出现该字段 reducer MUST `schema_violation`）。字段使用 `_ref` 是因为 `ak:mls:<profile>:<profile_id>` 是 profile-scoped typed reference；MLS 标准 payload 内的原始 group id 继续命名为 `mls_group_id`。 | 独立 MLS group 引用。 |
| `state` | yes | `enum(active, archived, tombstoned)` | 同 [`common-fields.md` §5](./common-fields.md);tombstoned 不可逆。 | 生命周期。 |
| `state_changed_at` | conditional | `timestamp` | `state != active` 时必填。 | 最近一次 state 转换时间。 |
| `created_by` | yes | `did` | — | 创建者。 |
| `created_at` | yes | `timestamp` | — | 创建时间。 |
| `updated_by` | no | `did` | — | 最近更新者。 |
| `updated_at` | no | `timestamp` | 不早于 `created_at`。 | 最近更新时间。 |

`encryption_profile=none` 的 Circle 是 plaintext scoped event boundary：它承诺事件不进入 Realm-wide shared delivery / query / projection / search / notification / export surface，且非 Circle 成员不得收到 Circle-scoped envelope 或 payload；它**不**承诺服务端、中继、明文存储后端或被列入 plaintext-visible 的处理服务无法读取内容。实现和 UI MUST 把 plaintext Circle 标示为"受限投递 / 查询边界"，不得宣传为 E2EE。

## 4. `display` 字段(标准化视觉身份)

跨客户端一致的 UI 表达是 Circle 安全模型的必要条件（见 §11 UX 论证）：

| 子字段 | 必填 | 类型 | 约束 |
| --- | --- | --- | --- |
| `short_name` | yes | `string` | `^[A-Z][A-Za-z0-9 _-]{0,23}$`；在 `(realm_id, short_name)` 上 reducer 强制唯一(case-insensitive)。`SC-` 前缀由 [`sidecar.md` §5](./sidecar.md) 保留，普通 Circle create/update MUST `schema_violation`(`reason=reserved_circle_short_name`)。其它普通 Circle 冲突 MUST `failed_precondition`(`reason=circle_short_name_taken`，见 [`error-code-registry.json`](../../artifacts/registry/error-code-registry.json))。Sidecar backing Circle 的 short name 由 reducer canonical 派生，任何冲突只返回通用 `sidecar_create_denied`。 |
| `color_token` | yes | `string` | 从 `circle.schema.json#/$defs/display/properties/color_token/enum` 的受控 palette 选；该 schema enum 是 canonical 机器真源。客户端 MUST 映射 token → 主题颜色(浅/深/高对比),**不**得自行重分配 token。`gray_high_contrast` 是承载无障碍/高对比语义的特例 token，并非纯色相；客户端 MUST 把它映射为高对比中性灰主题色。 |
| `symbol` | yes | `object` | `{emoji?: string, glyph?: enum}`；二选一。`glyph` 取 `circle.schema.json#/$defs/display/properties/symbol/properties/glyph/enum` 的受控 snake_case 枚举；该 schema enum 是 canonical 机器真源。客户端 MUST 把 glyph token 映射为本地 icon,MUST NOT 自行扩展未注册 token。 |

**颜色 token 与 symbol 必须在 spec 受控集中**，目的是同一 Circle 在 Alice 与 Bob 的客户端上呈现一致视觉，否则跨设备社会工程攻击成立。

## 5. Event 家族

本表为说明视图；完整集合与 `wire_scope` / `reducer_input` / lattice 属性以 [`event-kind-registry.json`](../../artifacts/registry/event-kind-registry.json) 为准。

| event kind | reducer_input | payload 形态 | 说明 |
| --- | --- | --- | --- |
| `ak.circle.create` | yes | full object | 创建 Circle；当 `encryption_profile=mls_rfc9420` 时同时初始化独立 MLS group 与 epoch 0 governance binding。 |
| `ak.circle.update` | yes | `ak.patch.v1`(path 不含 `realm_id` / `profile_ref` / `encryption_profile`) | 改 title / summary / display / directory_visibility / join_rule / history_visibility。 |
| `ak.circle.archive` | yes | object_lifecycle_payload | active → archived。 |
| `ak.circle.restore` | yes | object_lifecycle_payload | archived → active。 |
| `ak.circle.tombstone` | yes | object_lifecycle_payload | terminal；触发 §8 cascade。 |
| `ak.circle.member.state` | yes | `{circle_id, actor_id, membership: invite\|join\|knock\|leave\|ban, ...}` | 与 `ak.member.state` 复用同一 `membership_state` 枚举(`invite / join / knock / leave / ban`)，仅 scope 限定到 Circle；二者 wire 取值完全一致，不存在独立词形。reducer 先校验 actor 已是父 Realm `join` 成员；`knock` 仅在 `join_rule=knock` 下允许(见 §9.1)。 |
| `ak.circle.seal_commit` | no | `{circle_id, sub_seal_head_digest, epoch}` | reducer-derived:Circle sub-seal 按 profile cadence 周期性向 Realm Seal 提交不透明 commitment(§9)，由服务端 / seal service 发出，actor 不直接提交。 |

## 6. 对象 scope 表达

引入字段(跨多个现有对象):

```
Strand.scope_circle_id          : id:circle | null   # null = Realm-default scope
Message.effective_scope       : reducer-stamped, immutable tagged scope
Event.effective_scope         : reducer-stamped, immutable tagged scope，进入 envelope/sub-seal；MLS-backed scope 中也进入 AAD/governance binding
Space.scope_circle_id         : id:circle | null   # Space 自身 metadata / scoped structural relation 的可见性 scope
Space.child_scope_policy      : object             # 子资源 placement 约束，见 §7
Morph.scope_circle_id         : id:circle | null
Relation.scope_circle_id      : id:circle | null
Relation.effective_scope      : reducer-stamped, immutable tagged scope
```

**关键约束:Strand 永远只有一个 effective scope**。不存在 per-track scope —— 整个 Strand(synthesis、discussion、其他 track)共享同一事件 / 投递 / history 边界，要么都在 Realm-default，要么都在某个 Circle。

### 6.1 Reducer 规则

- `scope_circle_id` 引用的 Circle MUST `realm_id` 与对象 `realm_id` 一致；否则 `schema_violation`(`reason=circle_realm_mismatch`)。
- `scope_circle_id` 引用的 Circle MUST `state=active`；否则 `failed_precondition`(`reason=circle_not_active`)。
- `scope_circle_id=null` 不表示"没有 scope"；它表示 Realm-default scope。Reducer MUST 把它物化为 tagged `effective_scope = {kind:"realm", realm_id}`。
- `scope_circle_id=ak:circle:...` MUST 物化为 tagged `effective_scope = {kind:"circle", realm_id, circle_id}`。
- Reducer 在接受每个 event 时 MUST 固化 `effective_scope`。该值进入 Event envelope 与 Seal/sub-seal leaf；在 MLS-backed scope 中还进入 E2EE AAD 与 MLS governance binding 输入。后续 `scope_circle_id` 改绑不得重解释旧 event。
- Message 与 Relation 的 canonical reducer-output 对象 MUST 物化顶层 `effective_scope`；Strand 与 Morph 的 canonical 对象只保存 actor-signed `scope_circle_id`，其 reducer 派生的 `effective_scope` MUST 写入承载变更的 Event。该差异用于避免把派生字段混入 Strand/Morph 的 actor-signed 对象前像；实现 MUST NOT 从当前 Circle 状态重算历史 Event 的 scope。
- Effective history visibility = 父 Realm policy floor 与 Circle `history_visibility` 的更严格者。Circle MAY 收紧父 Realm，不得放宽父 Realm 的隐私/合规下限。
- 改绑 `scope_circle_id` 默认 reducer 拒绝(`failed_precondition` `reason=scope_rebind_forbidden`);profile MAY 允许，但 MUST audit-paired high-risk update。所有已存在 Message / 子内容保留其写入时的 `effective_scope` 与旧 scope 的 history / key eligibility；新内容才进新 scope。客户端 MUST 把切分前后历史分段展示。
- Structural Relation / position cell 的 `effective_scope` **MUST be no broader than 参与端点中最窄的 scope**(取参与端点 scope 集合中最严格者作为关系事实自身的 scope)。具体例:`public Board (Realm-default)` 包含 `private Strand (Circle=HR-Conf)` 时，`contains` 关系事实与其 position cell 的 `effective_scope = Circle:HR-Conf`,**不是** Realm-default；非 Circle 成员看不到该 containment 关系、看不到 private Strand 的 rank/position，也看不到 board 上"此处有隐藏项"的可枚举元数据。
- 当参与端点分别落在同一 Realm 的两个不同 Circle，且没有 Realm-default 端点可作为共同公开侧时，这两个 scope 在 v1 中是**不可比较的并列 scope**。Reducer MUST NOT 选择任一 Circle 作为"更窄者"，MUST NOT 取并集，也 MUST NOT 自动把关系提升到 Realm-default。Structural Relation、position、parent、cascade 或任何会产生 target-side reverse projection 的事实 MUST `failed_precondition`(`reason=scope_incomparable`)。弱语义 reference 若 profile 显式允许，producer MUST 选择单一 source-side `scope_circle_id`，且 projection 对该 scope 外 caller 返回 `locked` / none，不得创建目标侧反向边或可枚举空洞。

**Circle lifecycle 求值基线（normative）**：上述 `state=active` 检查是 CBA 授权输入，不得读取 receiver 当前 materialized Circle projection 代替事件自己的治理基线。DataEvent MUST 在其 `seal_ref` 对应的控制面 view 中求值 Circle `realm_id` 与 lifecycle；Control Move 在 admission 时 MUST 在其 `seal_basis.leaves[]` 合成的 joined control view 中求值，并在 Seal 接受时按 [`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §6.3 step 8 对该 Seal 的冻结 predecessor joined governance state 重验。若对应基线内 Circle 已是 `archived` 或 `tombstoned`，MUST `failed_precondition`(`reason=circle_not_active`)。实现不得因本地较新的 Circle projection 不同而改变同一基线的判定。

当 DataEvent 的 `seal_ref` 基线内 Circle 仍为 `active`、但 receiver 已观察到其后的 lifecycle Seal 时，按 [`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §4.3 的撤销新鲜度框架处理：

- 若 `ak.circle.archive` 所在 Seal `S_archive` 是 `seal_ref` 的后继，`distance(seal_ref, S_archive)` MUST 使用被签名的 Seal 提交时间计算。距离不超过 `revocation_freshness_window_ms` 时，receiver MAY 暂定接受，但 query grade MUST 为 `stale`；超过窗口 MUST 拒绝或隐藏，reason=`stale_seal_ref`。不得把 receiver 当前看到的 `archived` 直接当成事件基线内的 `circle_not_active`。
- `ak.circle.tombstone` 是不可逆终止。一旦 receiver 观察到其 Seal，任何更早 `seal_ref` 的 Circle-scoped DataEvent MUST 立即拒绝或隐藏，reason=`stale_seal_ref`，不享受新鲜度窗口。
- `open_set` 下 archive / tombstone Seal 与 `seal_ref` 并发时，receiver MUST 按已验证 leaf 集的 joined control view 重判；joined lifecycle 不是 `active` 时立即 `stale_seal_ref`，不得计算 `distance` 或给予窗口。无法验证 multi-leaf joined view 的轻客户端 MUST hold pending 或 fail closed，不得 fanout。
- 后续 `ak.circle.restore` 只使**以包含 restore 的 active control view 为新基线**的写入恢复合法；它 MUST NOT 追溯恢复任何跨过 archive barrier 的旧 `seal_ref`。producer 在 restore 后继续写入 MUST 换用包含 restore 的新 Seal 基线。

这些规则只统一 lifecycle gate 的基线与 stale 处置，不改变 `effective_scope` 的 immutable 派生：一旦 DataEvent 被接受，其 stamped scope 不因 archive / restore 重写。Conformance vector `ak.vector.circle.lifecycle_basis_and_archive_freshness.v1` 固定线性 archive、并发 archive、tombstone、restore barrier 与 Control Move basis 的结果。

### 6.2 `effective_scope` wire shape — submit-payload vs canonical reducer-output

`effective_scope` 在 wire 上有**两个不同的形态**，机器契约 MUST 分别校验:

1. **Submit-payload form (actor-supplied)**:actor 在 `ak.strand.create` / `ak.morph.create` / `ak.relation.create` / `ak.space.create` 等建对象写事件的 `payload.object`(Relation 为 `payload.relation`)内联对象中 supply `scope_circle_id` 字段(可为 `null`)。**MUST NOT** 携带 `effective_scope` 顶层字段；若 supply，reducer MUST 返回 `schema_violation` (`reason=effective_scope_reducer_managed`)。`ak.message.create` 与 `ak.space.parent` **不**携带 `scope_circle_id`:Message 无独立 scope，其 `effective_scope` 由所属 Strand 的 scope 派生；`ak.space.parent` 是只设 parent 链的 cas_register Move,Space 的 `scope_circle_id` 在 `ak.space.create` 随对象写入。
2. **Canonical reducer-output form (reducer-stamped, immutable)**:reducer 在接受 event 时把 `scope_circle_id` 物化为 tagged 对象，写入 Event envelope 的 `effective_scope` 字段 + 物化对象的 `effective_scope` cell。该字段一经写入 immutable；旧 event 即使 `scope_circle_id` 后续改绑也保留写入时的值。

两个形态的 schema:

**Submit-payload (actor-side input shape)**:

```json
{
  "scope_circle_id": null
}
```

```json
{
  "scope_circle_id": "ak:circle:0196419c-0000-7000-8000-000000000000"
}
```

`scope_circle_id` 是 `id:circle | null`;`effective_scope` 字段 MUST NOT 出现。

**Canonical reducer-output (Event envelope + materialized object)**:

`effective_scope.kind = "realm"`(对应 submit-payload `scope_circle_id=null`):

```json
{ "kind": "realm", "realm_id": "ak:realm:0196419b-0000-7000-8000-000000000000" }
```

`effective_scope.kind = "circle"`(对应 submit-payload `scope_circle_id=ak:circle:...`):

```json
{
  "kind": "circle",
  "realm_id": "ak:realm:0196419b-0000-7000-8000-000000000000",
  "circle_id": "ak:circle:0196419c-0000-7000-8000-000000000000"
}
```

Reducer 校验顺序(MUST):

1. 解析 submit-payload，确认顶层无 `effective_scope`，确认 `scope_circle_id` 为合法 `id:circle | null`。
2. 若 `scope_circle_id` 非 null:在 §6.1 规定的 DataEvent `seal_ref` / Control Move `seal_basis` CBA 基线中解析对应 Circle，校验 `realm_id` 一致 + `state=active`；不得读取 receiver 当前 projection 代替事件基线。
3. 物化 tagged `effective_scope` 对象，写入 Event envelope + 物化 cell；后续 Event reader / projection / Seal verifier MUST 使用 canonical reducer-output form 进行 authorization 与 history visibility 评估。

Conformance fixture 见 `artifacts/fixtures/circle-scope-fixture.json`，覆盖 None→None / 同scope→同scope / None→Some / Some→None / Some(A)→Some(B) 五种 rebind transition 与 schema-violation negative case。

### 6.3 Space 三个 scope 相关字段语义辨析

| 字段 | 影响对象 | 强制性 | 说明 |
| --- | --- | --- | --- |
| `Space.scope_circle_id` | Space 对象自身的 metadata 与 structural relation facts | reducer-enforced | Space 自身的 title / parent / rank / contains 事实落在该 Circle scope;**不**使 Space 成为独立 Realm 边界，Space 仍是 authorization-transparent 容器，只是它的 metadata 被该 Circle 的投递 / history / encryption profile 约束。 |
| `Space.child_scope_policy` | 任何 placement / move 进入该 Space 的子对象 | reducer-enforced | `allow_any` / `require_e2ee` / `require_same_scope` / `require_scope_circle_id` 之一，见 §7。是真正的"该 Space 只接受这种 scope 的子对象"硬约束。 |

实现必须区分 `scope_circle_id`（Space 自身 metadata scope）与 `child_scope_policy`（子对象 placement 硬约束），二者不可互相替代。

## 7. Realm-default scope、Circle scope 与加密覆盖范围

Realm **不会**自动创建默认 Circle。Realm-default scope 是 Realm 自身的 membership / history / delivery / encryption 上下文:

| `effective_scope.kind` | 事件 / 投递边界 | 加密承载 | 何时使用 |
| --- | --- | --- | --- |
| `realm` | 父 Realm membership / history visibility / policy floor | `Realm.encryption_profile` 指定的 Realm-default group / external provider / plaintext mode | `scope_circle_id=null` |
| `circle` | Circle membership / history visibility / projection 裁剪，且受父 Realm policy floor 包裹 | `Circle.encryption_profile=none` 时为 plaintext delivery-only；`mls_rfc9420` 时为 Circle 独立 MLS group | `scope_circle_id` 指向 Circle |

`encryption_profile`（Realm `enum(none, mls_rfc9420, external)` / Circle `enum(none, mls_rfc9420)`）是 **create-locked 的能力轴**：它只声明该 scope 用什么加密**机制**（有没有 MLS group），**不**决定哪些 Arkret 字段进入密文，也**不是**“内容是否加密”的开关。`none` 表示该 scope 结构上不是 / 不可能是 E2EE（bridge 到无 E2EE 外部网络、大型公开广播等诚实 opt-out）；`mls_rfc9420` 表示该 scope 恒有一条 MLS group，具备随时启用 E2EE 的能力。**推荐默认**：任何将来可能加密的协作 Realm / Circle SHOULD 以 `mls_rfc9420` + `content_encryption_floor=allow_plaintext` 创建——钥匙常在手，后期把 floor 抬到 `e2ee_required` 即可原地启用加密，无需 tombstone 重建。

是否真正加密、加密覆盖哪些字段，由两根 **enforcement floor** 独立声明，二者在 Realm 与 Circle 对称、Circle 不得低于 Realm、且只能单向收紧：

| policy field | enum | 说明 |
| --- | --- | --- |
| `content_encryption_floor` | `allow_plaintext` / `e2ee_required` | 取值为 `e2ee_required` 时，Strand / Message / Morph / Blob content 的 `effective_scope` MUST 是 MLS-backed：Realm-default MLS 或 Circle MLS；这些写入不得落在 plaintext Circle。 |
| `metadata_encryption_floor` | `allow_plaintext` / `e2ee_required` | Realm-wide metadata 加密下限，与 `content_encryption_floor` 对称；不得被 Circle 或对象 profile 放宽。缺省规则：MLS 或 `content_encryption_floor=e2ee_required` Realm 为 `e2ee_required`，其他 Realm 为 `allow_plaintext`。 |

Circle encryption compatibility rules:

- 父 Realm `encryption_profile=mls_rfc9420` 时，Circle `encryption_profile` MUST 为 `mls_rfc9420`。当 effective `content_encryption_floor` 取值为 `e2ee_required` 时适用同一规则。
  不满足上述规则的 `ak.circle.create` / `ak.circle.update` MUST `failed_precondition`(`reason=circle_encryption_below_realm_floor`)。
- 父 Realm `encryption_profile=none` 且 effective `content_encryption_floor=allow_plaintext` 时，Circle `encryption_profile` MAY 为 `none` 或 `mls_rfc9420`。选择 `none` 只提供投递 / 查询 / projection 隔离；选择 `mls_rfc9420` 提供独立 cryptographic scope。
- Circle 提供独立的 `content_encryption_floor` 收紧位，与 `metadata_encryption_floor` 对称：省略时继承父 Realm `content_encryption_floor`，effective content floor = max（父 Realm `content_encryption_floor`，Circle `content_encryption_floor`）。Circle 只能在父 Realm floor 之上**收紧**，不得放宽；声明低于 effective floor 的值 MUST `failed_precondition`（`reason=circle_encryption_below_realm_floor`）。`content_encryption_floor=e2ee_required` 仅在 `encryption_profile=mls_rfc9420` 时可声明；`encryption_profile=none` 的 Circle 声明 `e2ee_required` MUST `failed_precondition`（`reason=circle_encryption_below_realm_floor`，因 none scope 无 MLS-backed effective_scope 可承载密文）。
- Circle `encryption_profile=none` 时，`mls_group_ref` MUST NOT exist，`ak.mls.genesis` / `ak.mls.commit` / MLS Welcome 不适用于该 Circle。任何声明 `metadata_encryption_floor=e2ee_required` 的 plaintext Circle MUST 同时有可执行的 profile 说明如何加密对应 metadata；否则 reducer MUST reject。
- Circle `encryption_profile=mls_rfc9420` 时，`mls_group_ref` 由 reducer 派生，Circle key MUST NOT 从 Realm-default MLS group 或其他 Circle key 派生。

`metadata_encryption_floor` 语义:

| value | 明文允许范围 | 必须加密范围 |
| --- | --- | --- |
| `allow_plaintext` | Realm / scope 路由字段、object id/kind、必要 causal refs、Strand / Message 用户可读 metadata、Space parent / rank 等结构 metadata | 无（metadata 不强制加密；content 是否加密由 `content_encryption_floor` 决定） |
| `e2ee_required` | 路由所需 `realm_id`、`effective_scope.kind`、不可逆 routing digest、policy-required subject、必要 causal refs、Strand `tracks`、`stage` / `state` | 用户可读 `metadata.title` / `metadata.summary` / `metadata.fields`、Message `metadata.fields`、mention / reply excerpt、search token、关系预览、附件文件名 |

`e2ee_required` 档下，哪些 metadata 字段为换取服务端搜索 / projection 能力而对受托服务暴露明文，由独立的 `plaintext_visible_services` 声明控制（见 [`../crypto-media/encryption-and-audit.md` §2.3.0 / §2.8](../crypto-media/encryption-and-audit.md)）。`realm_id`、kind、epoch、routing digest 等同步收敛边界字段在两档下都保持 wire 明文，不可加密。

Effective content floor = max（parent Realm `content_encryption_floor`，Circle `content_encryption_floor` if present）。比较顺序为 `allow_plaintext < e2ee_required`；`e2ee_required` 时该 scope 的 Strand / Message / Morph / Blob content `effective_scope` MUST 为 MLS-backed，plaintext content 写入 MUST `failed_precondition`（`reason=content_encryption_floor_violation`）。

Effective metadata floor = max（parent Realm `metadata_encryption_floor`，Circle `metadata_encryption_floor` if present，object profile requirement）。比较顺序为 `allow_plaintext < e2ee_required`；任何写入若低于 effective floor MUST `failed_precondition`（`reason=metadata_encryption_floor_violation`）。Space 是 authorization-transparent placement 容器，不承载第三套 floor 值。

**单向 ratchet（normative）**：任一 scope（Realm-default 或 Circle）的 effective content floor 与 effective metadata floor MUST 随时间**单调非降**。任何 `ak.realm.policy_components` / `ak.circle.update` 若使某 scope 的 effective content floor 从 `e2ee_required` 降回 `allow_plaintext`，MUST `failed_precondition`（`reason=content_encryption_floor_downgrade`）；若使 effective metadata floor 降到更低等级，MUST `failed_precondition`（`reason=metadata_encryption_floor_downgrade`）。ratchet 约束的是 effective floor：抬高父 Realm floor（收紧）永远允许，只有**降低**被拒。该规则把 “前期不加密、后期加密、不可撤销” 做成密码学 / 治理双重不可逆，并堵住静默 downgrade 攻击面。对应负向向量 `ak.vector.e2ee.content_floor_downgrade_rejected.v1`、`ak.vector.e2ee.metadata_floor_downgrade_rejected.v1`、`ak.vector.circle.content_floor_below_realm_rejected.v1`，正向向量 `ak.vector.e2ee.in_place_enable.v1`。

### 7.1 Space child scope policy

Space 不拥有 membership / Policy Server / MLS group;`Space.scope_circle_id` 只是让 Space 自身 metadata 与 structural relation facts 落入某个 existing scope。为了表达"这个 Space 下不允许 plaintext Strand"或"这个 List 只能放 HR Circle 对象",Space MAY 声明 placement policy:

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

### 7.2 "宽 synthesis + 窄 discussion" 场景如何表达

需要"公开锚 + 私密讨论"组合时，MUST 用 **两个 Strand + Relation** 表达；Strand 永远单一 scope，不存在 per-track 安全边界:

```
Strand F_public  (scope_circle_id = null)              ← 公开 seal Strand，承载 metadata.title / metadata.summary / stage / metadata.fields
Strand F_private (scope_circle_id = ak:circle:0196419c-0000-7000-8000-000000000000; short_name=HR-Conf) ← Circle 内 Strand，承载敏感讨论与决策细节
F_private --confidential_discussion_of--> F_public
```

客户端 UI MAY 把这两个 Strand 在视觉上"组合显示"(同卡片标题区 + 切换 tab)，但协议层它们是**两个独立对象**，各自有独立的:
- 时间线、消息历史
- 成员、history visibility、投递 / 查询裁剪；若对应 scope 为 MLS-backed，则各自使用对应 MLS group(F_public 用 Realm-default,F_private 用 Circle MLS)
- watch cell、stage、生命周期
- 投影裁剪规则(无 Circle 成员的 Realm 成员只看到 F_public，看不到 F_private 的存在或活动元数据，符合 §9.1 投递不变量)

`confidential_discussion_of` 是标准 weak-semantic Relation kind(详见 [`relation.md`](./relation.md))，关系事实 MUST 存放在 `F_private` 的 Circle scope 内。这样 private 成员能从 private Strand 回到 public seal；非 Circle 成员不会在 public Strand 上看到"存在一个私密讨论"的可枚举边。

## 8. Capability 与授权评估

Capability actions:

| action | risk_tier | target event kinds | 说明 |
| --- | --- | --- | --- |
| `ak.circle.create` | medium | `ak.circle.create` | 创建 Circle。**默认不**在普通成员 bundle 中(防止 Circle 滥用稀释 UX)。 |
| `ak.circle.manage` | medium | `ak.circle.update`, `ak.circle.archive`, `ak.circle.restore`, `ak.circle.tombstone` | 管理已存在 Circle。 |
| `ak.circle.member.add` | low | `ak.circle.member.state`(payload.actor_id == envelope.actor_id，且 transition 合法) | 用户接受邀请、加入 `join_rule=public` 的 Circle 或自助退出；不得自助解除 ban。 |
| `ak.circle.member.manage` | medium | `ak.circle.member.state`(actor_id != envelope.actor_id) | 邀请/移除他人；Circle admin 持有。 |
| `ak.circle.member.add.others` | high | 同上 + 强制带 `ak.audit.accessed` 配对(与 `ak.strand.watch.set.others` 同模式) | 跨成员代写(罕用)，审计配对。 |
| `ak.circle.audit` | high | 空(read-only)，配对 `ak.audit.accessed` | 不属于 Circle 的 Realm admin 读取 Circle 元数据 / activity rollup 的审计权。 |

**授权评估两层 AND**:

```
authorized(actor, action, object) ⇔
    capability_grant(actor, action) ∧
    (effective_scope(object).kind == "realm" ∨
     actor ∈ Circle(effective_scope(object).circle_id).members[at object.causal_frontier])
```

其中 `effective_scope(object)` 对 durable Event 使用 immutable `effective_scope`，对 materialized object 使用当前 `scope_circle_id` 派生出的 tagged scope。capability 决定"能不能做",Circle membership 决定"够不够近"。任一不满足都拒绝。

Circle 管理类 grant MUST 显式约束到 `allowed_circle_ids` / `circle_id` selector，或由 Circle 自身的 admin cell 派生；不得把无约束的 Realm-wide `ak.circle.manage` 当作普通管理权限发放。Realm admin 需要读取 Circle 正文或成员细节时 MUST 走 `ak.circle.audit` + `ak.audit.accessed` 配对路径；MLS-backed Circle 中还不能获得历史解密 key，除非被正式加入该 Circle。Plaintext Circle 不存在历史解密 key，但仍不得绕过 Circle membership / audit gate 直接投递或查询。

**Realm 管理权交接与 Circle 隔离（normative）**：Realm ownership / admin capability transfer 只转移 Realm 治理能力，MUST NOT 隐式创建任何 `ak.circle.member.state`、MUST NOT 把接手管理员加入既有 Circle、MUST NOT 赋予既有 Circle 的历史读取 / 解密资格，也不是交接前必须完成的前置条件。若产品希望新管理员继续创建新的 Circle，应在交接 bundle 中显式授予 `ak.circle.create`（或等价的产品管理员角色中显式包含该 action）；这不影响任何既有 Circle。若需要新管理员接管某个既有 Circle 的 lifecycle / membership 管理，必须对该 Circle 显式签发带 `allowed_circle_ids` 的 `ak.circle.manage` / `ak.circle.member.manage` grant；若需要其参与内容讨论，则必须按 §9.1 写入明确的 Circle membership transition。实现 MAY 在交接向导中提示“可选移交哪些 Circle 的管理/成员资格”，但 MUST NOT 要求“把目标管理员加入所有 Circle”作为 Realm admin transfer 的协议条件。

## 9. Membership 与 Lifecycle

### 9.1 Membership 拓扑

**硬不变量**:

1. `Circle.members ⊆ Realm.members`。reducer 在 `ak.circle.member.state -> join` 时，若 target actor 的父 Realm `ak.member.state` 不是 `join`,MUST `failed_precondition` `reason=circle_member_must_be_realm_member`。
2. 父 Realm `ak.member.state -> leave/ban` 触发 **reducer-derived** cascade:该 actor 在该 Realm 所有 Circle 的 membership 收敛到 `leave`。对 `encryption_profile=mls_rfc9420` 的 Circle，还 MUST 触发对应 MLS `remove` proposal；plaintext Circle 不产生 MLS proposal。不需要 actor 显式写。

   **Cascade seal 锚点（normative）**：该 derived cascade 没有独立显式 event，其治理锚点 MUST 取为覆盖触发 `leave/ban` 的父 Realm `ak.member.state` event 的 Seal（记为 `S_cascade`），并以该 control view 中的 event digest 作为审计证据。Circle-scoped DataEvent 的授权 MUST 在该 event 自身 `seal_ref` 所指向的 joined control view 上求值：若 `seal_ref` 已包含 `S_cascade` 或包含同一父 Realm membership 变更，则该 actor 在所有 Circle 的 effective membership 派生为 `leave`，reducer MUST 拒绝其写入（`failed_precondition`，`reason=circle_member_must_be_realm_member`）并 MUST NOT 投递；若 `seal_ref` 尚未包含该 cascade，写入只能按该 `seal_ref` 视图下的成员资格暂定接受，并受 revocation freshness / backfill 规则约束。服务端不得用 producer 提供的 `prev_refs` 因果闭包替代 `seal_ref` 治理视图；需要表达 in-flight 窗口时，MUST 用从事件 `seal_ref` 到 `S_cascade` 的 sealed-control predecessor 关系定义，而不是用 payload-level refs。
3. **Circle 平面化，不允许嵌套**。需要交叉成员关系时，actor 同时属于多个 Circle 即可。
4. Circle admin / moderator 不是 Realm admin 的隐式子集。需要 Circle-local 管理时，必须通过 Circle-scoped admin cell 或带 `circle_id` / `allowed_circle_ids` selector 的 capability grant 表达；v1 不注册单独的 `ak.circle.admin` action。Realm admin transfer 不改变本条不变量：接手者不是自动 Circle member，也不是自动 Circle-local manager。

Circle membership 使用 [`common-fields.md` §4.5](./common-fields.md#45-参数化-membership-fsmnormative) 的共享 membership FSM，实例参数为 `scope_kind=circle`、`delivery_binding_rebind=false`；writer/guard 以该表 Circle 列为准。申请正文 MUST NOT 进入 member-state Move，沿用 [`../governance/join-policy.md` §8](../governance/join-policy.md) 的加密 envelope 约定。

Circle 与 Realm 共用 `$defs/membership_state` 单一枚举真源和同一 transition graph；差异由实例参数与 guard 列表达，不再维护第二张转换表。Circle 不承载成员级 delivery binding，因此 `join -> join` 与其余 same-state transition 一样非法。membership 与物理 lifecycle state 正交，不受 [`common-fields.md` §5.1](./common-fields.md) 的 lifecycle same-state 规则覆盖。需要幂等重试的 producer MUST 基于当前 membership state 重新提交合法 transition，而非重放 same-state 写入。

### 9.2 Lifecycle cascade

Circle lifecycle 只有 `active` / `archived` / `tombstoned` 三态，对应 `ak.circle.archive` / `ak.circle.restore` / `ak.circle.tombstone`。v1 不定义 `ak.circle.freeze` 或 `ak.circle.destroy`：`archived` 是可恢复的新写入冻结；`tombstoned` 是 Circle 本身的不可逆终态；父 Realm 的 `freeze` / `destroy` 在父边界统一生效，Circle 不持有独立 federation identity 或 successor 语义。

因为对象只有单一 scope,lifecycle cascade 简单:

| 场景 | Realm-level / 未 scope 对象 | scope_circle_id 指向该 Circle 的对象 |
| --- | --- | --- |
| 父 Realm tombstone / destroy | 按 Realm lifecycle 停止 | Circle 全部 tombstone；对象按 Circle lifecycle 停止；tombstone 到 successor Realm 时不会自动把 Circle membership / MLS key / history grant 迁移到 successor |
| 父 Realm freeze | 所有非豁免新写入按 Realm §2.6.0 拒绝 `realm_frozen` | Circle-scoped 新写入同样按 `realm_frozen` 拒绝；Circle 本身不定义独立 freeze，也不得用 Circle capability 绕过父 Realm freeze |
| 父 Realm archive | 按 Realm 默认隐藏 / 只读投影，可由 Realm restore 恢复 | Circle 与其对象遵循父 Realm archive 的默认隐藏 / 只读投影；不额外 tombstone、不改 membership / MLS eligibility，Realm restore 后恢复到 Circle 自身 lifecycle 决定的状态 |
| Circle archive | 不受影响 | 事件 CBA 基线内已 archived 时，新写入 MUST fail closed(`failed_precondition`, `reason=circle_not_active`)，**含新建以该 archived Circle 为 `scope_circle_id` 的对象**；基线后才观察到 archive 时按 §6.1 的 freshness / joined-view 规则处置。既有对象保持历史可读/可审计投影，但不得继续追加 Message / Morph / structural Relation / position update，直到 `ak.circle.restore` 使 Circle 恢复 active |
| Circle tombstone | 不受影响 | 事件基线内已 tombstoned 时对象写入 MUST `circle_not_active`；基线后观察到 tombstone 时立即 `stale_seal_ref`，不享受 freshness window。projection 显示 scope unavailable；`scope_circle_id` 不会被自动 rewrite |
| 父 Realm 收紧 history visibility | 按新 visibility | Effective visibility 重新计算为更严格值；Circle 不得保持比父 Realm 更宽的历史披露 |
| Circle history visibility 收紧 | 不受影响 | 投影、watch、message read/write 按新状态重新裁剪 |
| `scope_circle_id` 改绑 | — | 默认拒；profile 允许时 audit-paired，新旧历史分段展示(见 §6.1) |

每个对象有唯一 scope,lifecycle 只需在该 scope 与父 Realm 两层间做判定，不存在跨双 scope 的组合表。

**`ak.circle.restore`（archived → active）后置条件（normative）**：archived 是可逆中间态，restore 的 membership / MLS 后置条件如下：

- **archive 期间 membership cascade 仍生效**：archived Circle **不冻结** membership。archive 期间父 Realm 发生的 `ak.member.state -> leave/ban` MUST 照常按 §9.1 硬不变量 2 cascade 到该 archived Circle（被踢成员的 Circle membership 收敛到 `leave`）；restore 后该 Circle 的 effective membership = 父 Realm 当前 membership 与 Circle 自身 membership 事件的收敛结果，不存在「archive 期间漏掉的 leave/ban 在 restore 后才补」的窗口。
- **MLS-backed Circle 的 epoch 与 rotate**：archive 期间 Circle 的 MLS group **不暂停**成员变更语义——cascade 触发的 MLS `remove` proposal MUST 照常产生（与 plaintext Circle 仅做 delivery cascade 相对）。`ak.circle.restore` 本身**不**强制引入额外 MLS rotate：若 archive 期间已按 §10.1 / §10.3 完成了被踢成员的 remove + rotate，则 restore 不重复 rotate；仅当 archive 期间有 pending 未完成的 remove proposal 时，restore 后 MUST 在恢复写入前先完成这些 remove 对应的 rotate，保证 forward secrecy / post-compromise security 不因 archive→restore 出现空洞。
- restore 不改变既有对象的 `effective_scope` 与历史 key eligibility；restore 只解除 §9.2 表「Circle archive」行的写入冻结（`circle_not_active`），使新 Message / Morph / structural Relation / position update 可继续追加。

### 9.3 Sync / 投递不变量

> **Scope 投递不变量**:对任意事件 `E` 满足 `E.effective_scope.kind="circle"` 且 `E.effective_scope.circle_id=C`,Sync Service MUST NOT 向不属于 `C.members(at causal frontier of E)` 的 actor 投递 `E` 的 envelope 或 payload。订阅 Realm R 等价于订阅 (R 的 Realm-level events) ∪ (∀C ∈ R.circles, 若 actor ∈ C.members 则 C 的 scoped events，否则 ∅)。

特例:
- `ak.circle.create` 的 authorization shell 是 Realm-level event，但 projection MUST 按 `directory_visibility` 裁剪。`directory_visibility=members` 时，非成员不得看到 Circle title、display、member_count、created_by 或可区分存在性的错误；最多只能看到不可枚举的 opaque commitment。非成员 Circle stub 的 shape MUST 固定为 `{ "visibility": "locked", "opaque_commitment": "<digest-or-fixed-placeholder>" }` 或等价字段集合；`opaque_commitment` MUST 是固定长度、不可逆、不可按 Circle title / short_name / member set 枚举的 digest，且不可见与不存在 Circle 的 list / get / search 响应 MUST 使用同一错误 envelope、同一字段集合和同一 timing bucket。普通 Circle 的该隐私要求由 `ak.vector.circle.directory_visibility_members_indistinguishable.v1` 覆盖；独立 Sidecar 及其 backing Circle 还需额外满足 `ak.vector.sidecar.existence_privacy.v1`。
- `directory_visibility=realm_members` 时，属于父 Realm 但不属于该 Circle 的 caller 只能看到固定预览白名单：`circle_id`、`realm_id`、`visibility="realm_members"`、`display.color_token`、`display.symbol`、`member_count_bucket`、`join_rule` 与 `opaque_commitment`。不得向非 Circle 成员暴露 title、summary、raw member_count、成员 DID、created_by、join history 或 Circle 私有事件引用。非 Realm 成员与未授权 caller 必须收到与 `directory_visibility=members` 相同的 locked stub / not_found envelope 和 timing bucket。该要求由 `ak.vector.circle.directory_visibility_realm_members_indistinguishable.v1` 覆盖。
- `ak.circle.member.state` 仅投递给该 Circle 的成员 + 完成 `ak.circle.audit` / `ak.audit.accessed` 配对的 audit reader。
- `ak.circle.seal_commit` 是 Realm-level event，但只携带 opaque digest(见 §10)，且触发节奏不得泄露 Circle 活动频率。

## 10. 加密 / Seal 集成

### 10.1 Circle encryption profiles

- `encryption_profile=none`:Circle 是 plaintext scoped event boundary。Sync / query / projection / notification / export MUST 按 Circle membership 裁剪；服务端或明文存储后端可能接触 plaintext，部署 MUST 在 UI / policy / service description 中披露这种保证边界。
- `encryption_profile=mls_rfc9420`:Circle 拥有独立 MLS group，独立 epoch，独立 key tree。**MUST NOT** 从 Realm-default MLS group key 派生 Circle key(否则全 Realm 都能解密)。
- Realm 移除某 actor MUST 触发该 actor 所在所有 Circle 的 membership cascade；对 MLS-backed Circle 还 MUST 触发对应 MLS `remove` proposal，并在 Realm-default 也是 MLS-backed 时触发 Realm-default rotate。这是必要的密码学卫生，reducer-enforced。已知运维代价见 §10.3。
- Circle MLS handshake (commit/welcome/proposal) 投递严格限于 Circle 成员，不进入 Realm-default sync 流。
- MLS governance binding 的 scope 使用 tagged `effective_scope`。Realm-default MLS group 使用 `{kind:"realm", realm_id}`；Circle commit / welcome / genesis MUST 使用 `{kind:"circle", realm_id, circle_id}`，并绑定 `circle_id`、Circle membership frontier、Circle policy root 与父 Realm policy floor frontier。接收端验证时，`governance_binding.realm_id` / `circle_id` 与 `effective_scope` 任一不匹配 MUST fail closed；Strand `track_name` 或 `strand_id` 不得参与 MLS key scope 判定。

### 10.2 Seal stream

- Circle 内事件维护 Circle sub-seal(只对 Circle 成员可读，记录完整 envelope + payload digest)。
- Circle 按 profile 固定节拍触发 `ak.circle.seal_commit`，向 Realm Seal stream 提交 `sub_seal_head_digest`(不透明 SHA-256)。默认命名 profile 是 `ak.profile.circle_seal_cadence.fixed_5m.v1`：`period_ms=300000`、`max_jitter_ms=30000`、MUST emit empty-batch commitment、MUST NOT skip public seal ticks when the Circle has no new private events。移动端省电只能延迟客户端上传 private sub-seal entries；服务端/seal service 仍必须按公开 cadence 补空 commitment。不得按"每 N 个真实 event"触发，否则会泄露活动频率。低隐私部署若声明 event-count profile，必须显式标为不满足 confidential Circle profile。
- 验证链:Circle member 验证时 `Circle sub-seal head ↔ Realm seal commitment ↔ Realm seal head`，三段闭合。非 Circle 成员只能验证 Realm seal 完整性。

### 10.3 Realm-member-removal MLS rotate amplification

一次离职 / 踢人因此可能放大为 **M+R 次 MLS group rotation**，其中 `M` 是该 actor 所在的 MLS-backed Circle 数，`R` 是父 Realm-default scope 是否 MLS-backed(是则 1，否则 0)。Plaintext Circle 只做 membership / delivery cascade，不产生 MLS rotate。这是密码学卫生的必要代价(forward secrecy 与 post-compromise security 要求)，不可省。

操作上的缓解策略(profile MAY 实现，**不在 protocol normative 层强制**):

- **批量 rotate**:profile MAY 把短时间窗内的多次 member removal 合并为单次 rotate proposal batch(MLS 协议本身支持 multi-proposal commit)。
- **延迟 rotate 窗口**:profile MAY 声明 rotate 必须在 actor removal 后 ≤ X 完成。X 是该 profile 的 forward secrecy 窗口承诺，MUST 显式公开，且 MUST be no longer than profile 声明的最大可容忍泄露窗口(典型 ≤ 1 小时)。
- **Circle 数量上限(normative + 运营建议)**:[`../conformance/scalability-constraints.md` §5](../conformance/scalability-constraints.md) 设两条 **normative 硬上限**封顶最坏情况:单 Realm active Circle 数 ≤ 1,000、单 actor 所属 active **MLS-backed** Circle 数 ≤ 256(后者直接封顶本节 `M+R` 放大里的 `M`，即单次 membership 变更触发的最坏 MLS rotation 次数)；超限 reducer MUST reject(`circle_count_exceeded`)。在硬上限之上，产品 SHOULD 鼓励 Circle 少而稳定(参考 §11 UX 风险),profile MAY 进一步声明更紧的软上限(例如单 Realm ≤ 64 Circle)以进一步约束 delivery fanout 与 MLS rotate amplification。

对 MLS-backed Circle，替代方案(共享 Realm-default key 派生 Circle key、或惰性 rotate 直到下一次实际通信)会破坏 Circle 的密码学隔离前提，使其退化为 plaintext delivery-only scope，声明 MLS-backed 时 **MUST NOT** 采纳。

## 11. Scope-identity UX safety invariants

Circle 引入的最大实践风险是**跨 Circle 上下文混淆**:用户在 Circle A 的 Strand 工作，被通知 ping 到 Circle B 的 Strand，回复时误以为仍在 A 圈。这是真实泄露发生的瞬间。**因为 Strand 是单 scope 的(§6)，所以"我在哪个 Circle"等价于"我在哪个 Strand"，这反而让 UX 清晰**:每个 Strand 的视觉身份就是它 scope 的视觉身份，不存在"同一 Strand 内 synthesis 一个色、discussion 另一个色"的混乱。

要让客户端能可靠区分 scope，以下信号 **MUST** 在 spec 层统一，**不**留给客户端各自发明:

- **颜色 token**:同一 Circle 在 Alice 与 Bob 的客户端上必须呈现一致颜色，否则跨设备 social engineering 攻击成立。
- **短名**:`short_name`(如 `HR-Conf`)相比裸 Circle ID（如 `ak:circle:01964...`）更易人工识别；客户端 SHOULD 显示 `short_name` 以辅助 scope 识别。
- **符号 / glyph**:无障碍 / 色盲场景的第二信号。

以下不变量只适用于**向人类用户呈现写入、回复、转发、引用、mention、邀请或导航入口的客户端 surface**。纯 headless SDK、webhook worker、自动化 agent runtime 若不向人类呈现这些入口，则本节呈现义务不适用；但它们向上层 UI 暴露 Circle 数据时 MUST 原样提供 `display` 与 effective scope，使实际呈现方能够履行本节。适用的客户端实现 MUST 满足以下可测试不变量。具体控件布局、文案与视觉形式是实现自由。

1. 在任何会导致写入、回复、转发、引用、mention 或发送通知的入口，当前 effective scope MUST 可被用户区分；Circle scope 至少呈现 `display.color_token`、`display.symbol` 与 `display.short_name` 中的两个互补信号。
2. Plaintext Circle MUST 使用不会暗示 E2EE 的 glyph、标签或披露语义；MLS-backed Circle MAY 使用 lock/shield 类语义，但不得让 plaintext scope 与 E2EE scope 看起来等价。
3. 跨 Circle 导航或同一 surface 内切换不同 scope 时，客户端 MUST 让用户感知这是跨 scope 转场；不得表现成同一 Strand 内的普通滚动或普通 tab 内容切换。
4. Mention / invite / add-recipient 等候选交互 MUST 区分 Circle member 与非 member；不得暗示非成员会收到 Circle-scoped 内容。
5. 跨 Circle 引用必须标识为“另一 Circle / 另一协作圈 / 另一作用域”或等价语义，**不得**使用“信任圈”措辞，且不得预览调用者无权访问的内容。
6. "宽 seal Strand + 窄 discussion Strand" 的组合形态(§7.2)在 UI 上 MAY 渲染为同一工作 surface,**但**两个 Strand 之间的切换 MUST 表现为跨 scope 转场，不得表现为同一 Strand 内不同视图。

### 11.1 Agent Sidecar backing Circle

Agent Sidecar 是 [`sidecar.md`](./sidecar.md) 定义的独立 `ak:sidecar:` 对象，不是 Circle profile。Sidecar reducer/service 为它派生一个系统管理的 backing Circle，以复用本文件的 scoped delivery、query/projection、sub-seal 与独立 MLS group 语义。

普通 Circle create/list/get/update/member/lifecycle API MUST 排除所有被 Sidecar `backing_circle_id` 引用的 Circle。Backing Circle 的 shape、访问 fan-out、MLS readiness、存在性隐私、private Strand projection 与 lifecycle 只服从 `sidecar.md`；caller 不得通过 `profile_ref`、title、short_name、member set 或 Relation 猜测或管理它。

## 12. 与既有概念的区分

| 概念 | 含义 | 主要承担 |
| --- | --- | --- |
| **Realm** | federation/identity boundary | membership 主源、Policy Server、capability registry、federation route、Realm-default MLS group |
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
