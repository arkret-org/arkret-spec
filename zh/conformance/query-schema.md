# Query JSON Schema

## 1. 目标

本文定义 Contrix View projection、客户端本地搜索、inbox 和可选受托 search / projection 扩展可复用的标准查询形状。该形状不是必需的远端索引 API；实现是否提供搜索、如何维护本地索引、是否暴露网络查询接口，均由客户端或扩展 profile 决定。任何查询执行都必须可序列化、可验证、可分页，并且不能绕过 Space policy、有效 branch access、E2EE 可见性与 capability。

## 2. Query 对象

```json
{
  "space_ids": ["cx:space:01js0sp0000000000000000000"],
  "object_types": ["flow", "message", "morph"],
  "morph_types": ["customer_case"],
  "facets": ["assignable"],
  "anchor_ref": "cx:flow:01js0card00000000000000000",
  "filters": [],
  "relation": null,
  "context": {
    "event_kinds": ["cx.flow.update", "cx.message.create", "cx.relation.create"],
    "relation_kinds": ["contains", "assigned_to", "depends_on", "replies_to", "promoted_from_discussion"],
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
- `object_types`: OPTIONAL，限制标准对象类型，例如 `room`、`board`、`list`、`card`、`message`、`morph`。
- `morph_types`: OPTIONAL，当 `object_types` 包含 `morph` 时进一步限制开放对象类型。
- `facets`: OPTIONAL，schema-declared capability hint 过滤。Facet 不替代对象类型，也不绕过授权、schema、policy、有效 branch access 或 E2EE 可见性；查询命中某 facet 不表示调用方获得该 facet 暗示的写入、排序、状态转换或 renderer 能力。
- `anchor_ref`: OPTIONAL，`timeline` / `renderer="timeline"` 或 Card context 的上下文锚点对象引用。
- `filters`: OPTIONAL，过滤条件。
- `relation`: OPTIONAL，关系扩展条件。
- `context`: OPTIONAL，上下文时间线聚合参数，若存在用于 `timeline` / `renderer="timeline"` 聚合：
  - `event_kinds`: OPTIONAL，返回的事件 kind 列表。
  - `relation_kinds`: OPTIONAL，关系收敛时允许的关系类型。
  - `event_tiebreak`: OPTIONAL，事件同序比较的 tie-break 字段名，例如 `event_id`。
- `order_by`: OPTIONAL，排序规则。
- `projection`: OPTIONAL，返回字段选择。
- `cursor`: OPTIONAL，不透明分页游标。
- `limit`: OPTIONAL，默认 50，执行方 MAY 限制最大值。
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
    { "field": "type", "op": "eq", "value": "card" },
    { "field": "fields.status", "op": "neq", "value": "done" }
  ]
}
```

支持：

- `and`
- `or`
- `not`

执行方 MAY 限制嵌套深度，防止高成本查询。

## 5. Relation Query

```json
{
  "kind": "assigned_to",
  "direction": "out",
  "target_ref": "did:web:alice.example"
}
```

`direction`:

- `out`: 从当前对象出发。
- `in`: 指向当前对象。
- `both`: 双向查询。

Relation Query 字段：

- `kind`: REQUIRED，关系类型，例如 `contains`、`belongs_to`、`assigned_to`、`promoted_from_discussion`。
- `direction`: REQUIRED，`out` / `in` / `both`。
- `source_ref`: OPTIONAL，限制 relation 起点对象、Actor 或 Space。
- `target_ref`: OPTIONAL，限制 relation 终点对象、Actor 或 Space。
- `source_type`: OPTIONAL，限制起点类型，例如 `card`、`room`、`actor`、`space`。
- `target_type`: OPTIONAL，限制终点类型。
- `depth`: OPTIONAL，关系展开深度；跨 Space 规则见 `views.md` Lazy Link。

Flow synthesis 与 discussion 的 relation 查询必须遵守有效 access 授权：

- `promoted_from_discussion` 可显示 synthesis 条目来自 discussion 的沉淀关系。
- Flow synthesis 可见只有在有效 access policy 继承或授予 discussion 读取时，才代表 discussion timeline 可读。
- Discussion 可读不代表 Flow synthesis 可写。

查询执行方 MUST reject 含糊或互相矛盾的 Relation Query。

## 6. Sort

```json
{
  "field": "rank",
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
  "type",
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

任何对外暴露可互操作 query / search / projection 语义的执行方 MUST:

- 对 query 做 schema validation。
- 对 Space、Subject、Room、对象和字段做 authorization filtering。
- 把 `facets` 仅作为过滤条件和 projection hint；不得因 facet 字符串扩大授权、启用未声明 reducer 或绕过 Morph profile validation。
- 对 Card-linked Room / Flow discussion 按有效 branch access 做 membership / history visibility 检查；branch-scoped override 生效时必须独立裁剪。
- 对高成本 full_text / relation expansion 限流。
- 不泄露不可见对象是否存在。
- 在 E2EE Space 中不得对密文正文做服务器全文搜索；客户端本地搜索只能覆盖本设备已解密且当前 actor 仍有权读取的内容。
