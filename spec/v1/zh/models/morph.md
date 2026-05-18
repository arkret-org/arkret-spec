---
title: Morph
---

## 1. 目标

`morph`（`cx:morph:`）是 Contrix 协作图中的**开放形态对象**，用于承载协议未固化为标准类型的协作对象。它适合：

- 插件或业务自定义对象
- 未来标准类型的实验阶段
- 外部系统镜像对象
- 低频、弱互操作的扩展数据
- 不要求强互操作的弱结构数据

Morph 是扩展缓冲层，不是标准对象的替代品。Flow、Message 和 Space workflow 的主语义已经由标准对象类型定义；实现不得为了复用字段、renderer 或插件机制而把这些对象改写为 Morph。

公共字段、lifecycle、reducer 总则见 [`common-fields.md`](./common-fields.md)。

## 2. Schema 与字段

Schema id: `cx.schema.morph.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:morph` | 以 `cx:morph:` 开头。 | Morph ID。 |
| `space_id` | yes | `id:space` |  | 所属 Space。 |
| `schema_refs` | yes | `array<string>` | 至少 1 项，唯一。 | `fields` 与 transition validation 的权威 schema 集合；`morph_type` / `facets` 不能替代。 |
| `morph_type` | yes | `string` | 标准值见业务 profile，扩展不得使用未注册 `cx.` 前缀。**create-locked**，禁止后续修改。 | 开放类型 / 业务标签。 |
| `facets` | no | `map<FacetConfig>` | 未知 facet 必须由 Space schema / Morph profile 声明。 | Morph 暴露哪些已声明能力 hint。 |
| `title` | no | `string` | SHOULD <= 512 chars。 | 标题。 |
| `summary` | no | `string` |  | 摘要。 |
| `content` | no | `object` | 富文本/blocks 见 [`content-types.md`](./content-types.md)。 | 正文内容。 |
| `encrypted_payload` | no | `EncryptedPayload` | 与 `content` 二选一；见 `encrypted-envelope.schema.json`。 | E2EE 场景下包裹 Morph 正文内容。 |
| `fields` | no | `object` | 字段 schema 由 `schema_refs` 决定。 | 自身属性。 |
| `state` | no | `enum(active, archived, redacted)` | 终态必须有事件来源。Reducer 按 [common-fields.md §5.1](./common-fields.md) 校验源状态：`cx.morph.archive` MUST 来自 `active`（否则 `morph_not_active`）；`cx.morph.restore` MUST 来自 `archived`（否则 `morph_not_archived`）；`cx.redaction` 指向 Morph 时 MUST 来自 `{active, archived}`（否则 `morph_already_terminal`）。same-state self-transition MUST fail。 | 物化状态。 |
| `state_changed_at` | conditional | `timestamp` | `state != active` 时必填。 | 最近一次 state 转换时间。 |
| `created_by` | yes | `did` |  | 创建者。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `updated_by` | no | `did` |  | 最近更新者。 |
| `updated_at` | no | `timestamp` |  | 更新时间。 |

## 3. 最小示例

```json
{
  "id": "cx:morph:0196414b-0000-7000-8000-000000000000",
  "schema": "cx.schema.morph.v1",
  "space_id": "cx:space:0196419b-0000-7000-8000-000000000000",
  "schema_refs": ["cx.schema.morph.customer_risk.v1"],
  "morph_type": "customer_risk",
  "title": "ACME procurement risk",
  "facets": {
    "stateful": {
      "state_field": "fields.status"
    },
    "renderable": {
      "renderers": ["card", "row"]
    }
  },
  "fields": {
    "status": "open",
    "severity": "high"
  },
  "created_by": "did:web:alice.example",
  "created_at": "2026-04-26T00:00:00Z"
}
```

> **示例规则**：顶层 `schema` 必须是容器 self-schema `cx.schema.morph.v1`，它仅定义 Morph 容器形态；`schema_refs[]` 是 §4 顺序 1 的"结构 / 验证真源"，必须列出**业务字段** schema id——上例使用配套的参考业务 schema [`cx.schema.morph.customer_risk.v1`](../../artifacts/schemas/morph-customer-risk.schema.json)，它声明 `fields.status` / `fields.severity` 两个业务字段的允许取值集合（structural validation 部分）。本参考 schema 不附带 transition 规则；真实部署若需要 transition validation，SHOULD 在 Space schema 的 `morph_type_profiles[<morph_type>].transition_rules` 中声明（顺序 2 收紧来源），或注册一个独立 `cx.profile.morph.<type>.v1` profile 承载 state-machine 表，并由 reducer 按 §4.0 第 5 行"状态机 transition 合法性"读取。同名容器 schema `cx.schema.morph.v1` MUST NOT 被列入 `schema_refs[]` 当作业务 schema：容器 schema 不验证 `fields.*` 业务字段，二者职责不可混用。

Morph 字段用于对象自身属性。跨对象语义 SHOULD 使用 Relation。Morph 可以通过 schema/profile 声明的 facets 参与 Board、Timeline、Graph、Flow track projection 或 Document View，但这些 facets 只作为查询、投影和降级展示提示；标准对象的主语义必须保留在对应标准类型上。

## 4. Morph 类型系统合并优先级

> Machine-readable canonical: [`artifacts/registry/morph-type-decision-table.json`](../../artifacts/registry/morph-type-decision-table.json) 。下表与该 artifact 双向同步;有歧义时以 artifact 为准,本表为人类可读视图。

### 4.0 决策矩阵 (Normative summary)

在进入 4 源合并表之前，先列出 Morph 上每类决策问题应当从**唯一来源**读取——所有 reducer / projection / authz / UI 实现 MUST 按下表选源，**禁止跨源混合或回退**。不在表内的决策问题 SHOULD 抑制（不读 morph_type / facets 当作业务行为依据）。

| 决策问题 | 唯一来源 | 不得读取 |
| --- | --- | --- |
| 字段是否合法 / 是否必填 / 类型正确 | §4 顺序 1 (`schema_refs[]`) ∩ 顺序 2 (`morph_type_profiles`) | morph_type, facets |
| capability `morph_type_allow` / resource selector 匹配 | §4 顺序 3 (`morph_type` 字符串) | schema_refs, facets |
| 默认 renderer / `query.item_facets` / `graph.node_facets` 过滤 / UI 降级 hint | §4 顺序 4 (`facets`) | schema_refs, morph_type |
| 是否可调用某 capability action | capability grant + Space policy（reducer-input event 自身的 capability 校验） | morph_type, facets, schema_refs |
| 状态机 transition 合法性 | §4 顺序 1 + 顺序 2 声明的 transition rules | morph_type, facets |
| Schema 演进（schema_refs[] 变更） | §4.1 S2 / S3（schema-evolution policy + `cx.morph.schema_migrate.v1`） | 任何 facet / morph_type 推断 |

任何实现违反本表（典型错误：UI 按 `facets.assignable` 显示 assign 按钮**且**绕过 capability 检查，或 reducer 按 `morph_type` 决定字段验证集合）即为实现 bug，conformance 套件 MUST 覆盖反例。

同一 Morph 对象的"类型"信息可能来自四个声明源；任意 reducer / projection / capability 路径在求"该 Morph 是什么 / 允许什么"时必须按下表合并，不得自行选边。优先级数字越低越优先，冲突时高优先级值整体替换低优先级值（不部分混合）：

| 顺序 | 来源 | 作用 | 谁可写 |
| --- | --- | --- | --- |
| 1 | Morph object 的 `schema_refs[]` | **结构 / 验证真源**：决定 `fields` 的 schema、必填性、类型与 transition 规则。 | Morph create / `cx.morph.update` |
| 2 | Space schema `morph_type_profiles[<morph_type>]` | **Space-scoped 收紧**：声明该 `morph_type` 在本 Space 中可暴露的 facets、可写字段子集、必需 schema_refs、必需 capability action。本层 **只能收紧** §1 声明的范围，不得放宽。 | Space schema / Space profile |
| 3 | Morph object 的 `morph_type` (string) | **业务标签 / discoverability key**：用于 query / view / capability `morph_type_allow` 匹配；不引入 reducer 行为。 | Morph create（**create-locked**，禁止后续修改） |
| 4 | Morph object 的 `facets` (map) | **UI / projection hint**：选择默认 renderer、查询过滤、降级展示；MUST NOT 影响授权、状态机、reducer、wire 互操作。 | Morph create / `cx.morph.update` |

合并规则：

- **结构验证**只读取顺序 1 + 2：reducer / schema 校验 `fields` 时合并 §1 声明的字段集合与 §2 在该 Space 中收紧后的子集；§3 / §4 不参与字段验证。
- **类型匹配（capability 的 `morph_type_allow`、resource selector）**只读取顺序 3：`morph_type` 是 wire-stable 字符串 key。它 create-locked 是为了避免授权错位（一旦改 `morph_type`，旧 grant 的 selector 立即失效，是常见漏洞源）。
- **Facets**只在以下三处生效：默认 renderer / view 选择、查询 `item_facets` / `node_facets` 过滤、降级 UI 提示。任何 reducer 行为、状态机、授权判定 MUST NOT 读取 §4。
- **冲突处理**：
  - §1 与 §2 字段集冲突 → §2 胜（Space-scoped 收紧）；§2 试图放宽 §1 → `schema_violation`，Space schema accept 时静态拒绝。
  - `facets` 声明的 hint 字段在 §1/§2 中不存在 → 该 facet 在该 Morph 上 inactive，但 Morph 本身仍合法（facet 是 hint，不是 contract）。
  - `morph_type` 在 Space schema `morph_type_profiles` 中未声明 → §2 取空收紧（即纯 §1）；不得自动放宽到 "all fields allowed"。
  - 同一信息（例如 "可被分配"）同时由 §1 schema field、§2 必需 capability、§4 `assignable` facet 表达 → §1+§2 是真相，§4 仅作为查询提示；UI MUST NOT 仅凭 §4 决定能否调用 assign 操作。

声明者须在四层之间保持一致；只有顺序 1 与 2 是规范来源，§3/§4 的存在不构成"已声明能力"。Reducer / capability / wire 验证路径如违反本表（例如读取 §4 facet 决定授权），即为实现 bug，conformance 套件 MUST 覆盖。

### 4.1 `schema_refs[]` Evolution Policy (Normative)

`morph_type` create-locked（见 §4 顺序 3）防止授权错位，但 `schema_refs[]` 不能 freeze——Morph 的本质就是 evolvable schema。然而 `schema_refs[]` 也不能裸 update：它决定字段验证、transition 规则与历史事件解释，静默替换会导致旧事件按错误 schema 重放、reducer 行为漂移、capability 范围隐性扩张。本节定义 schema 演进的三条 normative 规则：S1 per-event schema 版本绑定；S2 `cx.morph.update` 中 schema_refs[] 变更的 capability gate；S3 完整 schema migration（含 additive / breaking / transformation 兼容声明）由一等 event `cx.morph.schema_migrate.v1` 承担。

**S1. Schema 版本绑定（per-event）**：每个针对该 Morph 的 reducer-input event（`cx.morph.create` / `cx.morph.update` / `cx.morph.transition` / 自定义 Morph kind）**MUST** 在 `requirements.schema[]` 中列出该事件写入时实际遵循的 Morph `schema_refs[]` 全集（即 Morph object 在该 event 生效后 §4 顺序 1 的真源）。`requirements.schema[]` 已进入 canonical bytes 与 event digest（见 [`event-and-patch.md` §2.7](./event-and-patch.md)），任何篡改会破坏签名。

Reader 决策规则：
- 重放历史事件时，reader **MUST** 用该事件 `requirements.schema[]` 中绑定的 schema 版本进行 payload / patch / transition 验证，**不得**使用 Morph 当前的 `schema_refs[]`；
- partial replication 下 reader 即使不持有 Morph 完整 schema_history 也能本地验证（schema 引用是自描述 profile id）；
- 若 reader 无法解析某个 schema_ref（未知 profile id），按 `requirements` 通用 fail-closed 规则处理（unknown critical → quarantine / soft_fail）。

**S2. `schema_refs[]` Update 受控**：`cx.morph.update` event 修改 `schema_refs[]` 字段时 **MUST**：
- 走 *schema-evolution policy* gate：实现 SHOULD 通过 Space schema / Morph profile 声明的高 tier capability action（如 `cx.morph.schema.migrate`）授权；未声明该 policy 或未携带对应 `authorization_ref` 的更新 reducer **MUST** 拒绝并返回 `failed_precondition` reason=`morph_schema_refs_evolution_unauthorized`；
- 该 event 自身的 `requirements.schema[]` **MUST** 同时包含旧版本与新版本（重叠期声明），便于 reader 判定 "本 event 之后 Morph 进入新 schema 集合"；
- audit log **MUST** 记录该 schema 变更，包括 issuer、`schema_refs` 旧值/新值、authorization_ref。

Reducer-input event 若未在 `requirements.schema[]` 中绑定生效 schema 版本，reducer **MUST** 返回 `schema_violation` reason=`morph_schema_version_binding_missing`。

**S3. Schema Migration 一等 event**：`cx.morph.schema_migrate.v1` 是 schema_refs[] 演进的一等事件，payload 形态由 `cx.schema.event_payload.v1#/$defs/morph_schema_migrate_payload` 定义。该 event 显式声明 `from_schema_refs[]` / `to_schema_refs[]` / `compatibility_class` ∈ {`additive`, `breaking`, `transformation`}，并通过高 tier capability action `cx.morph.schema.migrate` 鉴权（capability 缺失 reducer MUST `capability_denied`）。规则：

- `additive`：to_schema_refs[] 仅添加 optional 字段或向后兼容 profile；任何历史 reducer-input event 无需重新解释。Core reducer MUST 接受。
- `breaking`：to_schema_refs[] 删除字段、收紧约束或更改字段语义；历史 event 仍按写入时 schema 验证（per S1），新 event 按 to_schema_refs[] 验证。Core reducer **MUST NOT** 接受，除非 Space 显式声明 `cx.profile.morph.schema_migration_transformations.v1` opt-in profile；未声明则 reducer MUST `failed_precondition` reason=`morph_schema_refs_transformation_unsupported`。
- `transformation`：需要 per-event 数据 transform 把旧 payload shape 映射到新；payload `transformation_rules[]` 必填且 SHOULD 遵守 deterministic / replay-safe 约束。同样需 `cx.profile.morph.schema_migration_transformations.v1` profile 启用，否则 reducer MUST `failed_precondition` reason=`morph_schema_refs_transformation_unsupported`。

`cx.morph.update` event 修改 `schema_refs[]` 字段（即仍走原有路径）被收窄为 **additive-only** 的 fast path：

- reducer MUST 在 `cx.morph.update` 检测到 `schema_refs[]` 实际变化时校验该变化是 additive；非 additive MUST reject 并返回 `morph_schema_refs_transformation_unsupported`，并提示客户端改走 `cx.morph.schema_migrate`。
- breaking / transformation 路径**只能**通过 `cx.morph.schema_migrate` 表达。

reducer 在两种 path 下都 MUST 校验 `from_schema_refs[]`（或 `cx.morph.update` 写入前 Morph 的当前 `schema_refs[]`）与实际状态 set-equal；不一致 `failed_precondition`。

> Rationale：static `schema_refs[]` freeze 会扼杀 Morph 的 evolvability；裸 update 会让 capability `morph_type_allow` 通过 schema 漂移获得隐性扩张。v1 用 per-event `requirements.schema[]` 绑定 + `cx.morph.schema_migrate` 一等 event + schema-evolution capability gate 在两端之间取中：写入时绑定证据，验证时按写入版本解释；变更走显式 audit / capability，breaking / transformation 走 opt-in `cx.profile.morph.schema_migration_transformations.v1` profile。

## 5. 标准 Facets

Facets 是 schema-declared **UI / projection hints**，不是对象身份，也不是任何 normative 行为的依据。标准对象 MAY 暴露 schema/profile 已声明的 facets 来辅助展示或查询；Morph MAY 使用 facets 帮助 View、本地搜索、UI 和插件做过滤、降级展示和默认 renderer 选择。

**Facets 不参与的决策**（与 §4.0 决策矩阵保持一致，本节只重申以避免实现误读）：

- 授权（capability check、capability `morph_type_allow`、resource selector）
- 状态机 transition
- 排序 / Lattice join / Move precondition
- reducer 行为（接受 / 拒绝 / soft fail）
- event kind 接受规则
- wire 互操作（canonical bytes / event digest / signature）

任何把 facet 当作上述决策唯一来源的实现属于实现 bug。Facet 配置可以引用相应 Space schema / Morph profile / event kind registry / capability action 作为权威声明，但 facet 自身不替代它们。

| Facet | 说明 | 典型字段/关系 |
| --- | --- | --- |
| `container` | 提示对象可按显式 relation/profile 作为容器投影。 | `child_object_types`, `relation_kinds`, `ordering`, `exclusive_scope`。 |
| `replyable` | 提示对象可按声明的 reply relation 被回复，形成 thread/discussion。 | `reply_object_types`, `reply_relation_kind`, `time_field`, `redaction_policy`。 |
| `schedulable` | 提示对象有声明的时间窗口，可进入 calendar/gantt 投影。 | `start_field`, `end_field`, `timezone_field`, `dependency_relation_kinds`。 |
| `assignable` | 提示对象有声明的分配字段或关系。 | `assignee_relation_kind` 或 `assignee_field`。 |
| `stateful` | 提示对象有显式 profile 定义的受控状态机。 | `state_field`, `states`, `transition_policy`。 |
| `rankable` | 提示对象有声明的稳定手动排序 rank。 | `rank_field`, `rank_profile`, `collision_policy`。 |
| `reviewable` | 提示对象有声明的审核/审阅状态。 | `review_state_field`, `reviewer_relation_kind`, `priority_field`。 |
| `notifiable` | 提示对象可按声明的 notification profile 派生 notification/inbox/read state。 | `notification_types`, `read_state_policy`。 |
| `documentable` | 提示对象可按声明的 document profile 作为文档或 section root。 | `section_relation_kind`, `section_order_field`, `body_field`。 |
| `renderable` | 提示对象声明允许的默认展示面。 | `renderers`, `title_field`, `summary_field`, `media_field`。 |

`query.facets`、`collection.item_facets` 和 `graph.node_facets` 的数组语义为 AND：候选对象 MUST 同时具备列出的全部 facet。`container.child_facets` 与 `replyable.reply_facets` 使用 `{all?, any?, none?}` 选择器。

## 6. Schema Evolution

Morph `schema_refs[]` 的 per-event 版本绑定与受控迁移规则见 [§4.1](#41-schema_refs-evolution-policy-normative)。本节列出 evolution 的其余通用约束：

- 新字段优先 optional。
- 既有字段不得静默改变语义。
- reducer 和客户端 MUST 保留未知字段。
- UI 遇到未知 Morph type SHOULD 降级为 generic Morph card。
- 标准对象不得阻止 Space 定义自定义 Morph type。
- 实现遇到未知标准类型 SHOULD fail closed；遇到未知 Morph facet SHOULD 保留数据，但不得让未知 facet 绕过 schema、capability、policy 或 encryption 约束。
- 跨 schema 版本的 Morph 历史事件 reader 解释规则见 §4.1 S1；完整 schema migration（含 `additive` / `breaking` / `transformation` 兼容声明）由一等 event `cx.morph.schema_migrate.v1` 表达，breaking / transformation 类需 Space 显式启用 `cx.profile.morph.schema_migration_transformations.v1` profile。

## 7. 规范性引用

- 公共字段：[common-fields.md](./common-fields.md)。
- Relation：[relation.md](./relation.md)。
- View facets / projection：[views.md](./views.md)。
- Morph schema：`artifacts/schemas/morph.schema.json`。
- Morph type 合并决策表（canonical）：[`artifacts/registry/morph-type-decision-table.json`](../../artifacts/registry/morph-type-decision-table.json)。
- Schema registry：[`../conformance/schema-registry.md`](../conformance/schema-registry.md)。
