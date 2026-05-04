# Standard Object Types

## 1. 目标

本文定义 Contrix 的标准对象类型。标准对象是一等协议对象，拥有明确的主语义、字段约束和 reducer 行为。

核心字段类型、必填性和通用约束见 `data-structures.md`。本文定义标准对象的业务语义、推荐字段、推荐关系和推荐 facets。

原则：

- 标准类型提供主语义。
- `flow` 是统一协作主对象，承载协作议题、任务、正式表达与讨论分支。
- `morph` 提供开放扩展。
- `facets` 是由 Space schema / Morph profile 声明的能力提示和查询标签，不替代对象类型，也不单独定义授权、状态机、排序或 reducer 语义。
- View 只定义如何投影对象；它拥有自己的定义状态，但不发明对象能力，也不持有被投影对象的协作事实。

## 2. Flow

`flow` 表示 Space 内被讨论、推进、引用、审阅、执行或沉淀的统一协作对象。它既可以表现为偏内容/推进的 `kind="card"`，也可以表现为偏讨论/协作的 `kind="room"`，但 identity 始终只保留一份。

Flow 适合：

- 产品/工程 initiative
- 决策或提案
- 事故、客户 case、研究主题
- 跨多个团队的任务簇
- 需要长期沉淀的知识主题
- 外部资产或业务对象的协作锚点
- 会话主导的协作线程

推荐字段：

- `title`
- `description`
- `brief`
- `summary`
- `kind`
- `semantic_kind`
- `body`
- `fields`
- `primary_branch`
- `branches`
- `access`
- `state`

### 2.1 `kind`

`kind` 表示 Flow 的默认主视角：

- `card`
- `room`

规则：

- `kind="card"` 默认主入口 SHOULD 是 `synthesis` branch。
- `kind="room"` 默认主入口 SHOULD 是 `discussion` branch。
- `kind` 影响默认交互入口，不改变 `flow_id`，也不强制删除其他 branch。

### 2.2 `semantic_kind`

`semantic_kind` 是 Flow 的可选业务语义分类字段。它用于声明“这个 Flow 在业务上是什么”，而不是“默认以什么交互方式打开”。

初版建议枚举：

- `topic`
- `initiative`
- `decision`
- `incident`
- `customer_case`
- `proposal`
- `research`
- `task_cluster`
- `asset`
- `custom`

规则：

- `semantic_kind` 与 `kind` 正交。
- 同一个 `semantic_kind="decision"` 的 Flow 可以是 `kind="card"` 或 `kind="room"`。
- Space schema SHOULD 可以约束允许的 `semantic_kind` 集合。
- View、搜索、通知和 agent policy SHOULD 允许按 `semantic_kind` 过滤或做默认 renderer 选择。

### 2.3 `synthesis` branch

`synthesis` branch 承载 Flow 的整理后正式表达。它不是“摘要专栏”，而是 Flow 当前可被编辑、被引用、被推进的主数据面。

适合放入：

- `title`
- `description`
- `brief`
- `summary`
- `body`
- `fields`
- 状态推进字段
- 结构化业务字段

### 2.4 `discussion` branch

`discussion` branch 承载会话能力，而不是独立对象。它包含：

- Message timeline
- timeline / notification profile
- 可选的 branch-scoped access override 引用
- 讨论相关 branch-local fields

推荐字段：

- `enabled`
- `room_kind`
- `fields`

`room_kind` 初版建议支持：

- `discussion`
- `announcement`
- `support`
- `activity`
- `review`
- `external`

规则：

- `room_kind` 是 discussion branch 的语义/profile 选择器，不是自动授权后门。
- `announcement`、`review` 等 posting 约束 MUST 通过 capability / policy 表达，不得只靠 `room_kind` 字符串隐式生效。
- `activity` SHOULD 允许系统/agent 产生状态播报，但 reducer 仍按普通 Message timeline 处理。
- Flow branch 默认继承 Flow / Space 的有效 membership、permission 与 E2EE 规则；独立 discussion membership、history visibility 或 E2EE group MUST 通过 `access.branch_overrides.discussion` 或等价 policy/capability state event 显式声明。
- `discussion` branch membership 不从 `assigned_to`、`watchers` 或其他 Flow relation 隐式派生；若实现需要此类映射，必须在有效 access policy 中可审计地声明。
- `access.branch_overrides.discussion.history_visibility` 与 `encryption_profile="mls_rfc9420"` 组合时，若未显式声明 history sharing policy，默认 SHOULD 等价于 `joined`。
- 当 `discussion.enabled=false` 或 branch 不存在时，`cx.message.create`、`cx.message.revise`、`cx.message.redact` MUST 被拒绝，错误语义 SHOULD 为 `discussion_branch_disabled` 或等价 fail-closed 结果。

### 2.5 Branch Access

Flow 使用统一 access 语义表达 branch 的 membership、permission、history visibility 与 E2EE：

```json
{
  "access": {
    "defaults": {
      "membership": "inherit_flow",
      "permissions": "inherit_flow",
      "e2ee": "inherit_space"
    },
    "branch_overrides": {
      "discussion": {
        "membership": "branch_scoped",
        "permissions": "branch_scoped",
        "history_visibility": "joined",
        "e2ee": "branch_scoped",
        "encryption_profile": "mls_rfc9420",
        "membership_policy_ref": "cx:policy:01js0rp0000000000000000000"
      }
    }
  }
}
```

规则：

- `branches` 表达 branch 是否存在、默认入口和交互 profile；它不是另一套权限对象。
- 缺省情况下，`synthesis` 与 `discussion` 都继承同一个 Flow / Space 授权体系。
- 只有显式 override 的 branch 才拥有独立 membership、history visibility 或 E2EE group。
- `synthesis` branch SHOULD 使用继承访问规则；需要字段级限制时，应优先使用 capability constraints，而不是为 `synthesis` 创建另一套成员表。

### 2.6 转换

`cx.flow.convert` 在 `kind="card"` 和 `kind="room"` 之间切换同一个 Flow 的主视角。

规则：

- 转换不改变 `flow_id`。
- 转换不复制或迁移消息历史。
- 从 `card -> room` 时，若 `discussion` branch 尚未启用，Reducer MUST 自动启用它，或在 policy 禁止时 fail closed。
- 从 `room -> card` 时，不得自动删除 `discussion` branch 或既有消息；若需要关闭讨论，必须显式使用 `cx.flow.branch.disable` 或 profile 声明的 archive 语义。
- 转换不自动移除 Space (kind=board)/Space (kind=list) 中的 `contains` Relation；是否保留位置由独立的 workflow policy 或后续 `cx.flow.move` 决定。

### 2.7 常见关系

- `Space (kind=list) --contains--> flow`
- `flow --assigned_to--> actor`
- `flow --depends_on--> flow`
- `flow --blocks--> flow`
- `flow --references--> flow / morph / message / blob`
- `flow --derived_from--> flow / morph`
- `flow --summarized_from--> message`
- `flow --promoted_from_discussion--> message`

## 3. Space (kind=board)

Space (kind=board) 是 `Space` 的工作流容器形态，ID 使用 `cx:space:` 格式。看板类型、泳道策略、WIP 规则和自定义 workflow profile SHOULD 进入 `fields` 或 Space schema。

推荐字段：

- `title`
- `summary`
- `rank`
- `fields`
- `default_view_id`
- `state`

常见关系：

- `Space (kind=board) --contains--> Space (kind=list)`
- `Space (kind=board) --has_default_view--> view`

## 4. Space (kind=list)

Space (kind=list) 是 `Space` 的列/泳道形态，ID 使用 `cx:space:` 格式。Space (kind=list) 通过 `contains` relation 挂载到 Space (kind=board) 下。

推荐字段：

- `title`
- `summary`
- `rank`
- `wip_limit`
- `fields`
- `state`

常见关系：

- `Space (kind=board) --contains--> Space (kind=list)`
- `Space (kind=list) --contains--> flow`

## 5. Message

`message` 表示 Flow `discussion` branch 时间线中的原子消息。

推荐字段：

- `flow_id`
- `branch`
- `content`
- `attachments`
- `revision_root`
- `edited_at`
- `visible_state`
- `redaction_ref`

常见关系：

- `flow(discussion) --contains--> message`
- `message --replies_to--> message`
- `message --mentions--> actor / flow / morph`
- `message --references--> flow / morph / blob`

Message 创建是 append-only。编辑通过 revision chain；撤回通过 redaction/tombstone。

## 6. Morph

`morph` 是开放形态对象，用于承载 schema / profile 声明的扩展业务类型。

Morph 适合：

- 自定义业务对象
- 插件对象
- 外部系统镜像对象
- 未来标准类型的试验对象
- 不要求强互操作的弱结构数据

Morph 是扩展缓冲层，不是标准对象的替代品。Flow、Message 和 Space workflow 的主语义已经由标准对象类型定义；实现不得为了复用字段、renderer 或插件机制而把这些对象改写为 Morph。

推荐字段：

- `morph_type`
- `title`
- `summary`
- `content`
- `fields`
- `facets`

## 7. Document and File

`document` 与 `file` 在 v1 Core 中仍是 Morph profile，不是独立标准对象。后续版本若提升为标准对象，必须通过新的 schema/profile 版本声明迁移规则。

## 8. Actor Profile

`actor_profile` 是 Actor 在协作图中的展示镜像。

它用于：

- mention
- assignment
- display
- team membership view

Actor Profile 不替代 DID，也不成为权限主键。

## 9. 标准 Facets

Facets 是 schema-declared capability hints，不是对象身份。标准对象 MAY 暴露 schema/profile 已声明的 facets 来辅助展示或查询，但标准对象的核心语义不依赖 facets 才成立；Morph MAY 使用 facets 帮助 View、本地搜索、UI 和插件做过滤、降级展示和默认 renderer 选择。

Facets MUST NOT 成为授权、状态机、排序语义、reducer 行为、event kind 接受规则或 wire 互操作的唯一规范来源。这些语义必须由 Space schema / Morph profile / event registry / capability action 明确定义。Facet 配置可以引用这些 profile 或暴露 UI hints，但不能替代它们。

| Facet | 说明 |
| --- | --- |
| `container` | 可包含、排序或移动其他对象。 |
| `replyable` | 可被回复，形成 thread / discussion。 |
| `schedulable` | 有时间窗口，可进入 calendar / gantt。 |
| `assignable` | 可分配给 actor / team / agent。 |
| `stateful` | 有受控状态机。 |
| `rankable` | 有稳定手动排序 rank。 |
| `reviewable` | 可进入审核/审阅队列。 |
| `notifiable` | 可派生 notification / inbox / read state。 |
| `documentable` | 可作为文档或 section root。 |
| `renderable` | 声明允许的默认展示面。 |

## 10. Schema Evolution

标准类型演进 MUST 遵守：

- 新字段优先 optional。
- 既有字段不得静默改变语义。
- reducer 和客户端 MUST 保留未知字段。
- UI 遇到未知 Morph type SHOULD 降级为 generic Morph card。
- 标准对象不得阻止 Space 定义自定义 Morph type。

## 11. 规范性引用

- Flow / Message / branch 规则见 `conversation-model.md`。
- Flow / Space / Message 的核心字段见 `data-structures.md`。
- View 投影规则见 `views.md`。
- 授权规则见 `../authz/capabilities.md` 与 `../authz/event-auth-state-resolution.md`。
