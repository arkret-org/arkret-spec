---
title: Object Model Core
---

## 1. 目标

Contrix 的核心数据模型是一张以 Space 为边界、以标准对象和开放 Morph 共同组成的可审计协作图。

核心对象：

- `space`（security / sync / auth / E2EE 边界）
- `place`（Space 内部结构容器：board / list / 其他 profile 注册的形态）
- `actor_profile`
- `flow`
- `message`
- `morph`
- `relation`
- `event`
- `view`
- `policy`
- `invite`
- `capability`
- `blob`（内容层对象，由 Blob Store 管理，不参与协作图归约）

派生对象（不是 canonical truth，由 client / SDK 从 Event 集合本地计算；schema 仅用于 wire 表示）：

- `read_marker`（actor-private 状态；详见 `discovery/read-receipts.md`）
- `notification`（inbox projection；详见 `discovery/push-notifications.md`）

辅助对象（可选加速 / 审计）：

- `event_batch_receipt`（可选 batch 签名 receipt）

对象种类由 `id` 的 typed 前缀（`cx:flow:` / `cx:space:` / ...）唯一决定，canonical object 上没有独立 `type` 字段。Schema 约束通过 `schema_refs` 字段引用和 `cx.schema.define` / `cx.schema.update` state event 管理。`policy` 既是 typed-id 前缀（`cx:policy:`）下的物化对象，也有对应 state event 形态。

字段级结构、必填性、类型和约束见 `data-structures.md`。本文保留核心模型语义和示例，具体 JSON Schema SHOULD 从 `data-structures.md` 与 `schema-registry.md` 生成。

## 2. 基本原则

### 2.1 Space 边界与 Place 容器

每个 `cx:space:` 都是 security/sync/auth/E2EE 硬边界——复制、权限、schema、policy、membership、history visibility、加密、federation policy 都以它为根。Space 没有"容器形态"分支：结构性分组（看板、列、泳道、calendar bucket 等）由独立的 **Place** 对象（`cx:place:`）承担。

`security_class=high_assurance` 是 Space 的可选标签，进一步收紧 federation policy 与默认审计/E2EE 选项。

一个 Space 可以包含多个：

- Flow
- Place（包括 board / list / 其他 profile 注册的结构容器）
- Document
- Morph

Space MAY 通过 `cx.space.child` / `cx.space.parent` 形成 **Space-Space 层级**（每个 child 仍是独立边界）。membership、capability、history visibility、schema、policy 和 encryption key 默认不从 parent 级联到 child；任何继承都必须由 child Space 显式声明。详细规则见 [`space-hierarchy.md`](./space-hierarchy.md)。

Place 层级（看板嵌套、列在板内）通过 Place 自己的 `parent_ref` + `cx.place.parent` 表达，**不**与 Space-Space 层级混用。Place 嵌套必须在同一 Space 内；跨 Space 的引用走 Relation。授权、history visibility、E2EE 和 federation 解析始终回到 Place 所属 Space，**Place 永远不形成独立边界**。

### 2.2 Flow 承载主语义

同一个协作主题由一个 Flow 表达；track primary 解析规则与 track 配置决定默认入口和能力面。

标准对象本身表达主语义：

- `flow`：统一协作主对象。它承载 `title` / `summary` / `body` 等基础字段，并通过 track primary 解析规则决定默认进入哪个 track。
- `message`：Flow `discussion` track 中的消息。
- `morph`：开放形态对象，用于业务扩展、未知类型和实验对象。
- `place`：Space 内部的结构容器（`kind=board` / `kind=list` / 其他 profile 注册的形态）。Place 通过 `cx.place.parent` 表达层级，通过 `cx.flow.move` / `cx.flow.reorder` 管理 Flow 位置；Place 自身没有 membership / E2EE / federation。

标准对象 MAY 暴露 schema/profile 已声明的 `facets` 来辅助展示或查询，但它的核心职责不依赖 facets 才成立。例如 `flow` 天然是共享上下文容器；启用 `synthesis` 的 Flow 可作为 Place 管理的工作对象；启用 `discussion` 的 Flow 可作为讨论入口；`message` 天然属于 Flow `discussion` track。实现不得要求标准对象先声明 facet 才能承认其主语义。

### 2.3 Morph 是开放对象

`morph` 表示协议未固化为标准类型的协作对象。它适合：

- 插件或业务自定义对象
- 未来标准类型的实验阶段
- 外部系统镜像对象
- 低频、弱互操作的扩展数据

Morph 的可见能力可以由 Space schema / Morph profile 声明，并通过 `facets` 暴露给 View、UI、本地搜索或插件。实现遇到未知标准类型 SHOULD fail closed；遇到未知 Morph facet SHOULD 保留数据，但不得让未知 facet 绕过 schema、capability、policy 或 encryption 约束。

Facet 字符串本身不是规范性 reducer 或授权来源。任何会改变写入权限、状态转换、排序、包含关系、事件有效性或跨实现 wire 行为的能力，MUST 由明确 schema/profile/event kind/capability action 定义。

### 2.4 Relation 是一等对象

跨对象语义 MUST 使用 `relation` 表达，而不是藏在对象字段里。

常见关系：

- `contains`
- `belongs_to`
- `replies_to`
- `depends_on`
- `blocks`
- `mentions`
- `assigned_to`
- `references`
- `derived_from`
- `summarized_from`
- `promoted_from_discussion`

Relation 连接的是对象引用。标准字段使用 `from_ref` / `to_ref`，其值可以指向 `flow`、`message`、`morph`、`actor`、`place` 或 `space`。

#### 2.4.1 跨 Space 引用

Relation 的 `space_id` 表示关系事实所在的源 Space；`from_ref` / `to_ref` MAY 指向其他 Space 的对象、Actor 或 Space。跨 Space 引用只发布引用事实，不复制被引用对象内容，也不授予读取、写入、管理或同步被引用 Space 历史的权限。

创建跨 Space Relation 时，actor MUST 同时满足：

- 对 Relation 所在源 Space 的写入能力。
- 对被引用目标的 discover/reference 能力，或目标 Space policy 允许的等价引用能力。

读取与同步规则：

- 引用 ID、目标类型和目标 `space_id`（若已知）可以作为源 Space 的 Relation metadata 同步。
- 被引用对象的标题、字段、消息、附件、成员、计数、preview 和历史只按目标 Space 的 policy、history visibility、E2EE epoch 与 redaction policy 展开。
- 公共 Space 引用私有 Space 对象时，默认只能展示 opaque ref 或 Lazy Link；除非目标 Space policy 明确允许 preview，不得泄露目标内容、成员、计数或存在性细节。
- Sync / projection 层不得因为源 Space 可见就自动 backfill 目标 Space；跨 Space 展开必须重新执行目标 Space 授权，并在响应 metadata 中标记 `lazy_link`、`locked`、`accessible` 或等价可见性状态。

授权拆分规则（明确两端 enforce 责任）：

| 授权检查类型 | 在哪一边 enforce | 原因 |
| --- | --- | --- |
| Relation **创建**（`cx.relation.create`、`cx.relation.update`、`cx.relation.delete`） | **源 Space**（Relation `space_id`） | Relation 是源 Space 的 reducer-input；reducer 在源 Space 验证 actor 在源 Space 的 capability 是否覆盖 `cx.relation.*`。 |
| 引用目标的 **discover / reference 能力** | **目标 Space**（`from_ref` 或 `to_ref` 指向的 Space） | 目标 Space policy 决定是否允许该 Relation 引用自身；典型 capability `cx.object.read_metadata` 或 `cx.space.discover`。源 Space reducer 在 accept Relation 前 SHOULD 验证目标 Space 的 reference 许可（通过 cached attestation / capability grant ref 等）；缺失证据时 Relation 仍可写入源 Space，但 projection 层在展开时 MUST 重新校验目标授权，校验失败的 Relation 显示为 `locked`。 |
| 目标对象**内容展开**（标题、字段、preview） | **目标 Space**（read 时） | 每次展开都用 reader 在目标 Space 的 capability 重新校验；源 Space 的可见性不传染到目标。 |
| **位置 / structural 关系**（如 `contains` 跨 Space） | **源 Space + 强制源 == 目标** | `contains` 这类强结构关系在 v1 **MUST NOT 跨 Space**——结构容器（Place）必须与所属 Flow 同 Space。跨 Space 的引用只能用 `references`、`mentions`、`derived_from`、`summarized_from` 等弱语义关系。 |

实现 MUST：

- 在源 Space 接收 Relation 时验证 `from_ref` / `to_ref` 的 typed prefix 与目标 Space 一致性（`space_id` 字段或 typed ref 解析）。
- 不得把"源 Space 写权限"误当成"目标 Space 引用权限"——两者是**两次独立 capability check**。
- 目标 Space policy 拒绝引用时（例如 `discoverability=secret` + 不在 trusted issuer 列表），源 Space 仍 MAY 接受 Relation 但**MUST**在 projection 层把它降级为 `locked`，并不得泄露目标 Space 的存在性细节。
- **存在性反枚举（normative）**：`locked` 降级状态与"目标 Space 不存在 / 未发现"对外 MUST 不可区分。projection 在两种情况下 MUST 返回**相同**的 wire 形态：相同 `status="locked"` 字段、相同 metadata 集合、相同 timing 类（差距 ≤ 50ms）、相同 error 字符串。MUST NOT 在 `locked` 响应中泄露目标 `space_id`、`title`、`member_count`、`created_at`、issuer set 或任何能被探测者用于"目标存在 vs 不存在"区分的字段；客户端 UI MAY 显示通用 "reference not accessible" 而不是显示具体目标 ID。源 Space reducer SHOULD 限制单一 actor 在固定窗口内创建跨 Space `locked` Relation 的速率（默认 ≤ 20/min），防止枚举攻击。

### 2.5 Event 是事实

所有协作变化最终都落为签名 `event`。

Event 是审计根和 reducer 输入。当前态只是 Event 集合在某个 reducer profile 下的物化结果。

### 2.6 View 是投影定义

`view` 是一等协议对象，但它拥有的是投影定义的真相，而不是被投影对象的协作事实。它定义查询、过滤、排序、分组、renderer、布局、可见字段和共享 saved view 配置。

同一组 Flow / Message / Morph / Relation 可以投影为：

- board
- list
- table
- calendar
- gantt
- chat
- thread
- forum
- graph
- flow activity
- review queue

View 不得发明对象能力，也不得持有对象状态的唯一副本；对象能力来自对象类型、schema/profile 和 capability，facets 只作为已声明能力的查询与投影 hint。Board Place 包含 List Place、List Place 包含 Flow、Flow 的字段与位置、Flow `discussion` track 的消息与成员，都必须由对应标准对象、Relation 和 Event 归约得到。

当用户通过 View 修改协作对象时，写入必须落到真实对象操作。例如 Flow 跨 List 拖拽写为 `cx.flow.move`，同 List 排序写为 `cx.flow.reorder`，修改列顺序写为 `cx.place.update`（更新 List Place 的 `rank` 字段），改变 View 的 filter / columns / layout 才写为 `cx.view.update` 或 actor-private account data。

## 3. 通用字段规则

所有 canonical object 字段 MUST 使用 snake_case。

基础字段：

```json
{
  "id": "cx:flow:01964137-0000-7000-8000-000000000000",
  "space_id": "cx:space:0196419b-0000-7000-8000-000000000000",
  "created_by": "did:webvh:QmZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example",
  "created_at": "2026-04-26T00:00:00Z",
  "updated_by": "did:webvh:QmZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example",
  "updated_at": "2026-04-26T00:00:00Z",
  "schema": "cx.schema.flow.v1"
}
```

对象 ID SHOULD 使用带类型前缀的稳定字符串：

- `cx:space:<uuid>`
- `cx:place:<uuid>`
- `cx:flow:<uuid>`
- `cx:message:<uuid>`
- `cx:morph:<uuid>`
- `cx:relation:<uuid>`
- `cx:event:<uuid>`
- `cx:view:<uuid>`
- `cx:grant:<uuid>`

## 4. Space

最小结构：

```json
{
  "id": "cx:space:0196419b-0000-7000-8000-000000000000",
  "schema": "cx.schema.space.v1",
  "title": "Launch Plan",
  "created_by_principal": "did:web:acme.example",
  "schema_refs": [
    "cx.schema.space.v1"
  ],
  "policy_ref": "cx:policy:01964160-8000-7000-8000-000000000000",
  "default_discoverability": "invite_only",
  "default_join_rule": "invite",
  "history_visibility": "joined",
  "encryption_profile": "mls_rfc9420",
  "created_at": "2026-04-26T00:00:00Z"
}
```

Space policy 决定：

- 谁能加入 Space
- 哪些 Flow / Morph 类型与 track profile 可用
- 哪些服务可同步、索引或看见明文
- 是否加密
- 是否允许外部联邦
- 数据保留与 blob 配额

Space 层级关系不改变上述边界。Parent Space 可以帮助发现和组织 child Space，但不能单方面授予 child Space 的读取、写入、审核或解密能力。

## 5. Actor

Actor 是能执行动作的主体。协议中的 actor identity 根由 DID 定义。

Actor 类型：

- `user`
- `org`
- `team`
- `agent`
- `service`
- `device`
- `integration`

Actor MAY 有对应的 `actor_profile` 对象，便于在协作图中被 mention、assign 或展示。

Accountable actor MUST 记录责任关系，但 accountability 不等于 capability。

## 6. Flow

Flow 是 Space 内统一的协作主对象，直接承载“这件事本身”、一组参与者和围绕它的上下文信息。

Flow 通过 `tracks` 数组表达能力轨道：每个 track 至少声明 `name`；`is_primary=true` 可显式标识默认入口，未显式标记时按确定性规则派生。`synthesis` track 承载整理后的正式表达、结构化字段和推进信息；`discussion` track 承载聊天和讨论 timeline。

**Track 是纯展示 / 时间线分段标识，不携带独立的 membership / 权限 / history visibility / E2EE**。Track access 完全等于所属 Space 的 access。需要让 discussion 拥有独立 membership、history visibility 或 MLS group 时，必须创建一个 child Space 并通过 `discussion_space_ref` 引用（详见 [`data-structures.md`](./data-structures.md) §6.1.1）；不存在 track-internal "track_scoped" 模式。

业务语义分类不属于 Flow 顶层字段。实现 SHOULD 通过 Space schema/profile、`fields`、Relation、labels 或 Morph profile 表达业务类型，并通过 View 定义选择 renderer。切换默认 track 使用 `cx.flow.track.set_primary`（必要时配合 `cx.flow.track.enable`）；切换不会改变 Flow identity，也不要求复制或迁移消息历史。

最小结构：

```json
{
  "id": "cx:flow:019640f9-8000-7000-8000-000000000000",
  "schema": "cx.schema.flow.v1",
  "space_id": "cx:space:0196419b-0000-7000-8000-000000000000",
  "title": "支付重构",
  "summary": "统一支付链路、风控回调和退款状态机；同步 owner、决策与 blocker。",
  "body": {
    "kind": "cx.content.text",
    "body": "Please finish the final review.",
    "format": "markdown",
    "formatted_body": "Please finish the final review."
  },
  "fields": {
    "status": "review",
    "priority": "high",
    "due_at": "2026-05-01T00:00:00Z"
  },
  "tracks": [
    { "name": "synthesis", "is_primary": true },
    { "name": "discussion", "profile": "review" }
  ],
  "discussion_space_ref": "cx:space:019640dc-8000-7000-8000-000000000000",
  "state": "active",
  "created_by": "did:web:alice.example",
  "created_at": "2026-04-26T00:00:00Z"
}
```

Flow 规则：

- Flow identity 只保存一份，resolved primary track 只决定默认视角，不创建新的对象副本。
- 同一 Flow 的 `tracks[].name` MUST 唯一，且至多一个 active track MAY 设置 `is_primary=true`。
- 若没有显式 `is_primary=true`，Reducer MUST 派生 primary：`synthesis` 存在时优先选择 `synthesis`；否则单 track Flow 选择唯一 track；否则按 profile 默认 track 选择；仍无法唯一确定时 fail closed。
- `synthesis` track 与 `discussion` track 共享同一标题和基础字段；track 不存在独立 access 域。
- 未设置 `discussion_space_ref` 时，discussion 时间线、成员、history visibility、E2EE 完全继承父 Space。
- 设置 `discussion_space_ref` 时，所有 `cx.message.*` / `cx.reaction.*` / 成员管理写入 MUST 使用该 child Space 的 `space_id`；child Space 是独立的安全边界，按其自身 policy 收敛。
- `is_primary` 只是默认入口标记，不授予读取、写入或管理权限。
- `cx.flow.track.set_primary` / `cx.flow.track.enable` 只改变默认入口或 track 启用状态，不得隐式创建或迁移 child Space；child Space 的生命周期由独立 `cx.space.*` event 管理。

## 7. Flow Discussion Track

Flow 的 `discussion` track 是会话能力，而不是独立对象。它承载消息时间线和通知 profile；access 完全继承父 Space，或通过 `Flow.discussion_space_ref` 升级到独立 child Space 承载。

若 `discussion` track 设置 `is_primary=true`，该 track MUST 存在于 active `tracks` 数组中。Flow MAY 初始只带 `synthesis` track；需要讨论时再启用 `discussion` track。

Discussion track 规则：

- 未设置 `discussion_space_ref` 时，能看父 Space 的 actor 即可看 discussion 时间线（按父 Space history visibility）。
- 设置 `discussion_space_ref` 时，能否看 discussion 由 child Space 自身 access policy 决定，与父 Space 的 Flow synthesis 可见性无关。
- 能看 `discussion` 不表示能改 Flow 的字段、状态或 Board 位置（这些仍按父 Space capability 判断）。
- 切换 primary track 不会自动删除已有讨论历史。
- `discussion_space_ref` 启用 MLS 时，对应 MLS group 绑定该 child Space；E2EE 边界、membership frontier、`covered_frontier_cell` 都按 child Space 自身收敛。

## 8. Place（看板 / 列 / 泳道 / …）与 Flow 位置

Place 是 Space 内部的结构容器对象，ID 形如 `cx:place:`。看板（`kind=board`）、列（`kind=list`）、泳道、calendar bucket、page group 等都是 Place。Place 永远不形成独立 membership / policy / E2EE / federation 边界——授权、E2EE group 解析始终回到所属 Space。完整字段定义见 [`data-structures.md`](./data-structures.md) §4a；schema 见 [`place.schema.json`](../../artifacts/schemas/place.schema.json)。

Place 层级表达：Place 之间的父子关系通过 Place 对象的 `parent_ref` 字段 + `cx.place.parent` reducer-input event 表达（cas-register, bottom=reject）。Place 嵌套不得跨 Space：`parent_ref` 引用的对象 MUST 与该 Place 的 `space_id` 相同。

Board Place canonical 对象示例：

```json
{
  "id": "cx:place:019640b6-8000-7000-8000-000000000000",
  "schema": "cx.schema.place.v1",
  "space_id": "cx:space:0196419b-0000-7000-8000-000000000000",
  "kind": "board",
  "title": "Release Board",
  "fields": {
    "default_view_id": "cx:view:019641be-0000-7000-8000-000000000000"
  },
  "created_by": "did:web:alice.example",
  "created_at": "2026-04-26T00:00:00Z"
}
```

List Place canonical 对象示例（在父 Board 内的位置由 `parent_ref` + `rank` 共同决定）：

```json
{
  "id": "cx:place:0196401c-8000-7000-8000-000000000000",
  "schema": "cx.schema.place.v1",
  "space_id": "cx:space:0196419b-0000-7000-8000-000000000000",
  "parent_ref": "cx:place:019640b6-8000-7000-8000-000000000000",
  "kind": "list",
  "title": "Review",
  "rank": "mV",
  "fields": {
    "wip_limit": 5
  },
  "created_by": "did:web:alice.example",
  "created_at": "2026-04-26T00:00:00Z"
}
```

Board / List 中的 Flow 示例：

```json
{
  "id": "cx:flow:019640c6-8000-7000-8000-000000000000",
  "schema": "cx.schema.flow.v1",
  "space_id": "cx:space:0196419b-0000-7000-8000-000000000000",
  "title": "Review launch checklist",
  "body": {
    "kind": "cx.content.text",
    "body": "Please finish the final review.",
    "format": "markdown",
    "formatted_body": "Please finish the final review."
  },
  "fields": {
    "status": "review",
    "priority": "high",
    "due_at": "2026-05-01T00:00:00Z"
  },
  "tracks": [
    {
      "name": "synthesis",
      "is_primary": true
    }
  ],
  "created_by": "did:web:alice.example",
  "created_at": "2026-04-26T00:00:00Z",
  "updated_at": "2026-04-26T00:00:00Z"
}
```

Flow 在 Place 中的位置通过 active `contains` Relation / flow position event 表达，不由 track 决定，也不要求 Flow canonical object 自带 `place_id` 字段。View projection 返回的 `board_place_id` / `list_place_id` / `rank` 是投影派生字段。

**位置唯一性**：一个 Flow 在同一个 Board Place 内 MUST NOT 同时占据多个 List Place 的 active position。位置真相由 cas-register cell `cx:cell:cx.component.flow.position.v1:<board_place_id>:<flow_id>` 提供（详见 [`data-structures.md`](./data-structures.md) §4a.4）；`(board_place_id, flow_id)` 是 cell key，cell value `{ list_place_id, rank }` 决定当前 active list。派生 `contains` Relation 由 cell value 投影出来，不存在"reducer 关闭旧 position edge"的旁路：并发不同 set 直接由 cas-register 返回 `⊥`，单 active list 由 lattice 单 value 语义自动保证。

`cx.flow.move` payload 字段：

- `flow_id`：被移动的 Flow（与 `board_place_id` 共同决定 cell key）。
- `target_place_id`：目标 List Place（`cx:place: kind=list`），编入 effect `set { list_place_id }`。
- `board_place_id`：必填，cell key 的另一组成部分；早期版本曾允许省略由 reducer 推断，cas-register 模型下 MUST 显式提供。
- `rank`：移动后在目标 List 内的 rank，编入 effect `set { rank }`。
- `expected_position`：编译为 cell `head_eq`（详见 [`sync/operations-sync.md`](../sync/operations-sync.md) §9.1）。

常见关系：

- `board --contains--> list`（两端均为 Place）
- `list --contains--> flow`
- `flow --assigned_to--> actor`
- `flow --depends_on--> flow`
- `message --references--> flow`

## 9. Message

Message 是 Flow `discussion` track 时间线中的原子消息对象。

```json
{
  "id": "cx:message:0196414c-8000-7000-8000-000000000000",
  "schema": "cx.schema.message.v1",
  "space_id": "cx:space:0196419b-0000-7000-8000-000000000000",
  "flow_id": "cx:flow:019640f9-8000-7000-8000-000000000000",
  "track": "discussion",
  "created_by": "did:web:alice.example",
  "content": {
    "kind": "cx.content.text",
    "body": "@bob 请确认这个 item 的 legal 风险。",
    "format": "markdown",
    "formatted_body": "<mention did=\"did:web:bob.example\">@bob</mention> 请确认这个 item 的 legal 风险。"
  },
  "state": "active",
  "revision_root": "cx:message:0196414c-8000-7000-8000-000000000000",
  "created_at": "2026-04-26T00:00:00Z"
}
```

Message MAY reply to another Message, mention Actor or object, reference Flow / Morph / Space, or be redacted. 编辑通过 revision chain 表达；撤回通过 redaction/tombstone 表达。

## 10. Morph

Morph 是开放对象。

```json
{
  "id": "cx:morph:0196414b-0000-7000-8000-000000000000",
  "schema": "cx.schema.morph.v1",
  "space_id": "cx:space:0196419b-0000-7000-8000-000000000000",
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

Morph 字段用于对象自身属性。跨对象语义 SHOULD 使用 Relation。Morph 可以通过 schema/profile 声明的 facets 参与 Board、Timeline、Graph、Flow track projection 或 Document View，但这些 facets 只作为查询、投影和降级展示提示；标准对象的主语义必须保留在对应标准类型上。

## 11. Relation

最小结构：

```json
{
  "id": "cx:relation:01964180-0000-7000-8000-000000000000",
  "schema": "cx.schema.relation.v1",
  "space_id": "cx:space:0196419b-0000-7000-8000-000000000000",
  "relation_kind": "contains",
  "from_ref": "cx:place:019640b6-8000-7000-8000-000000000000",
  "to_ref": "cx:flow:019640c6-8000-7000-8000-000000000000",
  "rank": "mV",
  "created_by": "did:web:bob.example",
  "created_at": "2026-04-26T00:00:00Z"
}
```

Canonical 方向由 `from_ref -> to_ref` 定义。反向语义 SHOULD 由查询层或 schema 派生。

标准 `relation_kind` 的默认基数、Board/List `contains` 互斥规则、`assigned_to` 是否允许多 assignee，以及 Space schema/profile 如何声明更严格 RelationProfile，均以 `data-structures.md` 的 Relation 基数表为准。

## 12. Event

Event 是 reducer 输入和审计事实。Reducer-input event 在顶层带 `preconditions[]` / `effects[]` / `anchor_ref`；非 reducer event 不带这三个字段。

最小 reducer-input event：

```json
{
  "event_id": "cx:event:019640ed-8000-7000-8000-000000000000",
  "space_id": "cx:space:0196419b-0000-7000-8000-000000000000",
  "actor_id": "did:web:alice.example",
  "actor_seq": 4,
  "kind": "cx.flow.update",
  "created_at": "2026-04-26T00:00:00Z",
  "hlc": "01970e589d21-0004-a13f9c2e",
  "prev_refs": [
    "cx:event:019640ed-0000-7000-8000-000000000000"
  ],
  "refs": [
    { "id": "cx:grant:0196410c-0000-7000-8000-000000000000", "role": "authorized_by", "critical": true }
  ],
  "preconditions": [
    {
      "cell": "cx:cell:cx.component.flow.fields.v1:cx:flow:019640c6-8000-7000-8000-000000000000",
      "predicate": { "op": "head_eq", "value": { "fields.status": "in_progress" } }
    }
  ],
  "effects": [
    {
      "cell": "cx:cell:cx.component.flow.fields.v1:cx:flow:019640c6-8000-7000-8000-000000000000",
      "op": { "kind": "set", "value": { "fields.status": "done" } }
    }
  ],
  "anchor_ref": "cx:anchor:sha256:0000000000000000000000000000000000000000000000000000000000000000",
  "payload": {
    "flow_id": "cx:flow:019640c6-8000-7000-8000-000000000000",
    "patch": {
      "fields.status": "done"
    }
  },
  "proofs": [
    {
      "kind": "detached_jws",
      "alg": "EdDSA",
      "verification_method": "did:web:alice.example#device-1",
      "payload_hash": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
      "created_at": "2026-04-26T00:00:00Z",
      "jws": "..."
    }
  ]
}
```

Event MUST 被签名。Reducer MUST 拒绝任何 signature、schema、capability 或 causal 校验失败的事件。

## 13. View

View 示例：

```json
{
  "id": "cx:view:019641be-0000-7000-8000-000000000000",
  "space_id": "cx:space:0196419b-0000-7000-8000-000000000000",
  "schema": "cx.schema.view.v1",
  "kind": "collection",
  "renderer": "board",
  "query": {
    "object_types": ["flow"],
    "filters": [
      { "field": "fields.archived", "op": "neq", "value": true }
    ],
    "relation": {
      "kind": "contains",
      "source_ref": "cx:space:019640b6-8000-7000-8000-000000000000",
      "depth": 2
    }
  },
  "collection": {
    "item_object_types": ["flow"],
    "item_render": "card",
    "item_order_by": [
      { "field": "position.rank", "direction": "asc" }
    ],
    "grouping": {
      "mode": "relation_container",
      "board_place_id": "cx:place:019640b6-8000-7000-8000-000000000000",
      "container_relation_kind": "contains",
      "item_relation_kind": "contains"
    }
  },
  "visible_fields": [
    "title",
    "fields.priority",
    "fields.due_at"
  ],
  "created_by": "did:web:alice.example",
  "created_at": "2026-04-26T00:00:00Z"
}
```

## 14. Schema

Schema 约束：

- 标准对象类型
- Morph type 和 facets
- fields
- relation type
- allowed actions
- default views
- validation rules

Schema evolution MUST be additive by default。新版本 SHOULD 保留未知字段，避免不支持新字段的客户端破坏数据。

## 15. Policy

Policy 约束：

- capability requirement
- object type / facet requirement
- encryption profile
- retention
- visibility
- federation
- moderation
- quota

Policy 是 reducer 和服务节点判断请求是否可接受的输入。

## 16. Invite

Invite 是加入引导对象，不等于 capability grant。

接受 invite 后，相关 capability grant 才进入有效集合。

Invite MUST 携带 `expires_at`。默认有效期 SHOULD 不超过 7 天，高安全 Space SHOULD 不超过 24 小时；过期 invite 不得被 claim、accept 或用于派生新的 capability。

## 17. Read Marker

`read_marker` 是 actor-private 状态。它 SHOULD 存在于私有 account data 或 ephemeral sync channel 中，而不是作为公共 durable Event 高频写入。

## 18. Notification

`notification` SHOULD 是从 Event / Flow / Message / Relation 派生的 inbox projection，不是 canonical truth。

## 19. Reducer 规则

Reducer MUST：

- 验证签名
- 验证 schema
- 验证 capability
- 按 causal order 处理
- 对相同 Operation 保持幂等
- 保留未知字段
- 输出可声明的 reducer profile

## 20. 规范性引用

- 标准 event type 注册表见 `../conformance/schema-registry.md`。
- Reducer conformance vector 见 `../conformance/conformance-vectors.md`。
- Relation cardinality 规则由 `data-structures.md`、`object-model-standard.md` 和各业务 profile 共同定义；未声明可多重的关系 MUST 按 `(space_id, relation_kind, from_ref, to_ref)` 去重。
- Schema evolution 测试见 `../conformance/conformance-profiles.md`。未知字段必须保留，但不得绕过 schema、capability、policy 或 encryption 约束。
