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

当前 `subject / room / card -> flow` contract family 的 `current_phase` 为 `removed`。规范性 machine-readable 定义见 `artifacts/registry/legacy-compatibility-policy.json`。

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

## 4. 实现策略

服务端迁移建议顺序：

1. 先把 validator、schema registry、OpenAPI、fixture 改为只接受 `flow`。
2. 再把存储导出层和 federation DTO 全部改为 `cx:flow:`。
3. 最后删除旧 schema 文件、旧 event builder、旧 compatibility alias。

客户端迁移建议顺序：

1. UI 保留 `card` / `room` 视图概念，但底层 object identity 统一改成 `flow_id`。
2. 权限检查改用 `cx.flow.*` 与 `cx.flow.branch.*`。
3. timeline / discussion 入口不要再依赖 `room_id` typed ID。

## 5. 兼容性边界

- active v1 wire contract 不要求接受旧 `subject` / `room` / `card` event。
- 若实现需要导入历史离线数据，转换必须在进入 active validation / replay 之前完成。
- 对重新出现的旧 event kind，推荐返回 `unsupported_event_kind` 或等价 schema validation error。

## 6. 机器可读策略文件

规范性迁移映射与禁用模式见：

- `artifacts/registry/legacy-compatibility-policy.json`
