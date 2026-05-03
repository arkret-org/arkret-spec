# Subject / Room / Card 到 Flow 的迁移说明

本文定义旧 `subject` / `room` / `card` wire contract 被移除后的迁移规则。自 `2026-05-03` 起，Contrix v1 active wire contract 只保留 `flow` 作为统一协作主对象。

## 1. 结论

- `cx:subject:<ulid>`、`cx:room:<ulid>`、`cx:card:<ulid>` 不再是 active wire contract 的合法 typed ID。
- `cx.schema.subject.v1`、`cx.schema.room.v1`、`cx.schema.card.v1` 已移除，统一改为 `cx.schema.flow.v1`。
- `cx.subject.*`、`cx.room.*`、`cx.card.*` 不再是 active event contract；直接等价的 lifecycle / patch / position 行为必须改写到 `cx.flow.*`。
- 没有直接一对一别名的旧 link-surface / link-room 语义，必须迁移到 Flow discussion branch 和 projection 语义。

## 1.1 Phase 模型

为后续处理其他 legacy contract，迁移策略采用统一 phase 结构：

- `active`：仍属于 active wire contract，可直接 emit / accept。
- `import_only`：不属于 active wire contract，但受控迁移导入器可接受，并且必须先重写再进入 active validation / replay。
- `historical_only`：只允许存在于封存历史、审计快照或离线档案，不接受新的迁移输入。
- `removed`：完全移出 active wire contract；实现只可离线读取并一次性重写到新 contract。

当前 `subject / room / card -> flow` contract family 的 `current_phase` 为 `removed`。规范性 machine-readable 定义见 `artifacts/registry/legacy-compatibility-policy.json` 中对应的 `contract_families[]` 条目。

## 2. ID 与 schema 迁移

| 旧 wire 形式 | 新 wire 形式 | 说明 |
| --- | --- | --- |
| `cx:subject:<ulid>` | `cx:flow:<ulid>` | Subject 语义并入统一 Flow identity。 |
| `cx:room:<ulid>` | `cx:flow:<ulid>` + `kind="room"` | Room 变为 discussion-capable Flow。 |
| `cx:card:<ulid>` | `cx:flow:<ulid>` + `kind="card"` | Card 变为 board/list-oriented Flow。 |
| `cx.schema.subject.v1` | `cx.schema.flow.v1` | 不再保留 schema alias。 |
| `cx.schema.room.v1` | `cx.schema.flow.v1` | 不再保留 schema alias。 |
| `cx.schema.card.v1` | `cx.schema.flow.v1` | 不再保留 schema alias。 |

迁移要求：

- 存储层若仍保留历史 raw ID，导出、回放、签名、hash、snapshot、federation、sync DTO 时 MUST 重新编码为 `cx:flow:<ulid>`。
- 客户端、服务端和 conformance fixture MUST 不再输出旧 typed ID 前缀。

## 3. 事件迁移

### 3.1 直接一对一映射

| 旧 event kind | 新 event kind |
| --- | --- |
| `cx.subject.create` | `cx.flow.create` |
| `cx.subject.update` | `cx.flow.update` |
| `cx.subject.archive` | `cx.flow.archive` |
| `cx.subject.restore` | `cx.flow.restore` |
| `cx.room.create` | `cx.flow.create` |
| `cx.room.update` | `cx.flow.update` |
| `cx.room.archive` | `cx.flow.archive` |
| `cx.room.restore` | `cx.flow.restore` |
| `cx.card.create` | `cx.flow.create` |
| `cx.card.update` | `cx.flow.update` |
| `cx.card.archive` | `cx.flow.archive` |
| `cx.card.restore` | `cx.flow.restore` |
| `cx.card.move` | `cx.flow.move` |
| `cx.card.reorder` | `cx.flow.reorder` |
| `cx.room.member` | `cx.flow.branch.member` |
| `cx.room.history_visibility` | `cx.flow.branch.history_visibility` |
| `cx.room.policy_components` | `cx.flow.branch.policy_components` |

### 3.2 不再保留 direct alias 的旧语义

以下 legacy event 不再保留 wire-level alias：

- `cx.subject.link_surface`
- `cx.subject.unlink_surface`
- `cx.subject.set_primary_surface`
- `cx.card.link_room`
- `cx.card.unlink_room`
- `cx.card.set_primary_room`

这些语义的迁移规则如下：

- “把一个 Card 关联到一个 Room” 改为 “为该 Flow 启用 discussion branch，并通过 projection 暴露其讨论入口”。
- “切换 primary room / primary surface” 改为 “切换 Flow branch 的 primary state”。
- “解除 room / surface link” 改为 “禁用对应 discussion branch，或停止在 projection 中暴露该入口”。

### 3.3 无 direct alias 旧语义的精确替代边界

| 旧语义 | 必须替代到的新语义 | 不得再做的事 |
| --- | --- | --- |
| `cx.subject.link_surface` | 若目标是讨论入口，则写 `cx.flow.branch.enable`；若只是暴露入口，则只改 projection / renderer，不新增独立 link object。 | 不得继续维持一个可签名的 `subject-surface` wire object。 |
| `cx.subject.unlink_surface` | 若讨论能力需要真正关闭，则写 `cx.flow.branch.disable`；若只是不再展示，则只移除 projection 暴露。 | 不得把“取消展示”误写成对象删除或 Flow identity 变化。 |
| `cx.subject.set_primary_surface` | 写 `cx.flow.branch.set_primary`。 | 不得把 primary surface 单独建成另一套 state key。 |
| `cx.card.link_room` | 对同一 `flow_id` 开启 `discussion` branch，并在 projection 中声明讨论入口。 | 不得再把 card 和 room 视为两个可独立签名、需跨对象跳转的 identity。 |
| `cx.card.unlink_room` | 若讨论能力要停用，则写 `cx.flow.branch.disable`；否则只去掉 projection 暴露。 | 不得隐式删消息历史。 |
| `cx.card.set_primary_room` | 写 `cx.flow.branch.set_primary`，必要时先保证对应 branch 已启用。 | 不得重建 `room_id` alias。 |

判定规则：

- branch state 是 canonical state；projection 只是展示面。
- “关闭讨论能力” 和 “不再在 UI 上突出展示讨论入口” 是两件不同的事，迁移时不得混写。
- 若旧数据无法判断它表达的是 branch lifecycle 还是单纯 projection，导入器 MUST 保守地迁移到 projection 语义，而不是擅自删除 branch 或消息历史。

## 4. 实现策略

服务端迁移建议顺序：

1. 先把 validator、schema registry、OpenAPI、fixture 改为只接受 `flow`。
2. 再把存储导出层和 federation DTO 全部改为 `cx:flow:`。
3. 最后删除旧 schema 文件、旧 event builder、旧 compatibility alias。

客户端迁移建议顺序：

1. UI 保留 `card` / `room` 视图概念，但底层 object identity 统一改成 `flow_id`。
2. 权限检查改用 `cx.flow.*` 与 `cx.flow.branch.*`。
3. timeline / discussion 入口不要再依赖 `room_id` typed ID。

### 4.1 一次性历史导入规则

历史导入器必须按以下顺序执行：

1. typed ID rewrite  
   把 `cx:subject:*` / `cx:room:*` / `cx:card:*` 全部重写为 `cx:flow:*`，并按旧语义补出 `kind="room"` 或 `kind="card"`。
2. schema rewrite  
   把 `cx.schema.subject.v1` / `cx.schema.room.v1` / `cx.schema.card.v1` 全部重写为 `cx.schema.flow.v1`。
3. event kind rewrite  
   对有 direct alias 的旧 event kind，按本文件第 3.1 节重写为 `cx.flow.*` 或 `cx.flow.branch.*`。
4. branch / projection 语义替换  
   对无 direct alias 的 `link_surface` / `link_room` 类语义，必须先判断它表达的是 branch lifecycle 还是 projection 暴露，再迁移到 branch state 或 projection state。
5. active validation  
   只有在上述 rewrite 完成后，事件才能进入 active schema validation、hash、signature、snapshot、sync、federation 或 reducer replay。

导入器不得：

- 在 active validator 前接受未重写的 legacy typed ID、schema ID 或 event kind。
- 通过保留 hidden alias 的方式“兼容” legacy contract。
- 因为旧 `link_room` 数据缺少完整上下文，就擅自删除 discussion history。

### 4.2 下游仓库最小迁移清单

`contrix-rust-sdk`

- 删除 `subject` / `room` / `card` typed ID builder 与 schema enum。
- builder、validator、parser 统一到 `flow` / `flow.branch.*`。
- 把 `legacy-contract-negative-fixture.json` 纳入最小拒绝回归。

`soland`

- 存储导出层、sync DTO、federation DTO 不再输出 legacy typed ID / schema ID / event kind。
- `supported_operations`、OpenAPI 和 service binding 全部以 registry / catalog 为准。
- 历史导入器与 active validator 分层，不能共用一条“软兼容”写入路径。

`yougen`

- 代码生成模板停止手写旧 operation / DTO alias。
- OpenAPI、service-api inventory、operation registry 只能从 canonical catalog / generated registry 读取。
- 生成物若仍保留 `room` / `card` 命名，只能作为 UI label，不得回流为 wire token。

`cotest`

- 把 `legacy-contract-negative-fixture.json` 作为黑盒 mutation set。
- 对 removed contract 的期望结果必须是 reject，而不是 optional backward compatibility。
- 允许的错误码集合以 fixture 的 `allowed_errors` 为准。

## 5. 兼容性边界

- active v1 wire contract 不要求接受旧 `subject` / `room` / `card` event。
- 若实现需要导入历史离线数据，转换必须在进入 active validation / replay 之前完成。
- 对重新出现的旧 event kind，推荐返回 `unsupported_event_kind` 或等价 schema validation error。

## 5.1 `cotest` 黑盒拒绝基线

用于黑盒回归的规范性拒绝集合见：

- `artifacts/fixtures/legacy-contract-negative-fixture.json`

该 fixture 的用途不是证明“旧 contract 还能被兼容读取”，而是证明 active wire 实现会稳定拒绝它们。

## 6. 机器可读策略文件

规范性迁移映射与禁用模式见：

- `artifacts/registry/legacy-compatibility-policy.json`
- `artifacts/fixtures/legacy-contract-negative-fixture.json`
- `implementation-compatibility-matrix.md`
