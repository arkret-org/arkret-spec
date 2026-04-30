# Query JSON Schema

## 1. 目标

本文定义 Contrix Index / View / Inbox 使用的标准查询语法。查询语法必须可序列化、可验证、可分页，并且不能绕过 Space policy 与 capability。

## 2. Query 对象

```json
{
  "space_ids": ["cx:space:01JS0SP000000000000000000"],
  "entity_types": ["task", "message"],
  "anchor_entity_id": "cx:entity:01JS0TASK000000000000000000",
  "filters": [],
  "relation": null,
  "context": {
    "event_kinds": ["cx.entity.update", "cx.message.create", "cx.relation.create"],
    "relation_kinds": ["contains", "assigned_to", "depends_on", "replies_to"],
    "event_tiebreak": "event_id"
  },
  "order_by": [],
  "projection": [],
  "cursor": null,
  "limit": 50,
  "consistency": {
    "wait_for": "cx:sync:...",
    "timeout_ms": 5000
  }
}
```

字段：

- `space_ids`: REQUIRED，查询范围。
- `entity_types`: OPTIONAL，限制 Entity type。
- `anchor_entity_id`: OPTIONAL，`timeline` / `renderer="timeline"` 的上下文锚点对象 ID。若设置，表示查询应围绕该对象收敛相关边界与事件。
- `filters`: OPTIONAL，过滤条件。
- `relation`: OPTIONAL，关系扩展条件。
- `context`: OPTIONAL，上下文时间线聚合参数，若存在用于 `timeline` / `renderer="timeline"` 聚合：
  - `event_kinds`: OPTIONAL，返回的事件 kind 列表。
  - `relation_kinds`: OPTIONAL，关系收敛时允许的关系类型。
  - `event_tiebreak`: OPTIONAL，事件同序比较的 tie-break 字段名，例如 `event_id`。
- `order_by`: OPTIONAL，排序规则。
- `projection`: OPTIONAL，返回字段选择。
- `cursor`: OPTIONAL，不透明分页游标。
- `limit`: OPTIONAL，默认 50，服务 MAY 限制最大值。
- `consistency`: OPTIONAL，读己之所写等待条件。

## 3. Filter

```json
{
  "field": "fields.status",
  "op": "eq",
  "value": "todo"
}
```

支持操作：

- `eq`
- `neq`
- `in`
- `not_in`
- `lt`
- `lte`
- `gt`
- `gte`
- `contains`
- `exists`
- `prefix`
- `full_text`

字段路径 MUST 使用 dot path。实现 MUST 拒绝访问未授权字段。

## 4. Boolean Filter

```json
{
  "and": [
    { "field": "entity_type", "op": "eq", "value": "task" },
    { "field": "fields.status", "op": "neq", "value": "done" }
  ]
}
```

支持：

- `and`
- `or`
- `not`

服务 MAY 限制嵌套深度，防止高成本查询。

## 5. Relation Query

```json
{
  "kind": "assigned_to",
  "direction": "out",
  "target_actor_id": "did:web:alice.example"
}
```

`direction`:

- `out`: 从当前 Entity 出发。
- `in`: 指向当前 Entity。
- `both`: 双向查询。

Relation Query 字段：

- `kind`: REQUIRED，关系类型，例如 `contains`、`belongs_to`、`assigned_to`。
- `direction`: REQUIRED，`out` / `in` / `both`。
- `source_entity_id`: OPTIONAL，限制 relation 起点 Entity。
- `source_actor_id`: OPTIONAL，限制 relation 起点 Actor。
- `source_space_id`: OPTIONAL，限制 relation 起点 Space。
- `target_entity_id`: OPTIONAL，限制 relation 终点 Entity。
- `target_actor_id`: OPTIONAL，限制 relation 终点 Actor。
- `target_space_id`: OPTIONAL，限制 relation 终点 Space。
- `depth`: OPTIONAL，关系展开深度；跨 Space 规则见 `views.md` Lazy Link。

`source_*` 与 `target_*` 每侧最多指定一个。Index MUST reject 含糊或互相矛盾的 Relation Query。

## 6. Sort

```json
{
  "field": "fields.rank",
  "direction": "asc",
  "nulls": "last"
}
```

`direction` MUST 是 `asc` 或 `desc`。  
`nulls` MAY 是 `first` 或 `last`。

## 7. Projection

```json
[
  "id",
  "entity_type",
  "title",
  "fields.status"
]
```

Projection 只减少返回字段，不提升权限。

## 8. Response

```json
{
  "items": [],
  "next_cursor": "cx:cursor:...",
  "has_more": true,
  "frontier": {
    "sync_token": "cx:sync:...",
    "max_hlc": "01JS0KE000000000000000000"
  }
}
```

## 9. 安全规则

Index MUST:

- 对 query 做 schema validation
- 对 Space 和字段做 authorization filtering
- 对高成本 full_text / relation expansion 限流
- 不泄露不可见对象是否存在
- 在 E2EE Space 中不得对密文正文做服务器全文搜索
