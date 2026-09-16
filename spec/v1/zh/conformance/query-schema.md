---
title: Query JSON Schema
status: candidate
normative: true
stability: v1
updated: 2026-07-02
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [normative-language.md](./normative-language.md) 解释；仅大写形式具规范约束力。

> **Wire schema canonical source（informative）**: query / projection 请求体（`query_request`）与 search 请求体（`search_request`）的 wire-level canonical schema 已抽出为独立 JSON Schema [`../../artifacts/schemas/query.schema.json`](../../artifacts/schemas/query.schema.json)（schema id `ak.schema.query.v1`，含 `query_filter` / `field_filter` / `boolean_filter` / `sort_spec` / `relation_query` 等可复用 `$defs`）；[`../../artifacts/openapi/arkret-service-api.openapi.yaml`](../../artifacts/openapi/arkret-service-api.openapi.yaml) 的 `QueryRequestBody` / `SearchRequestBody` / `QueryFilter` / `FieldFilter` / `BooleanFilter` / `SortSpec` / `RelationQuery` 组件均 `$ref` 该文件，故为单一真源。本文为人类可读的语义注释与字段说明，**不**作为 wire validator 的真源；字段（`realm_ids` / `projection` enum / `cursor` / `limit` / `wait_for` / `op` / `direction` 等）以 `query.schema.json` 为准。

## 1. 目标

本文定义 Arkret View projection、客户端本地搜索、inbox 和可选受托 search / projection 扩展可复用的标准查询形状。该形状不是必需的远端索引 API；实现是否提供搜索、如何维护本地索引、是否暴露网络查询接口，均由客户端或扩展 profile 决定。任何查询执行都必须可序列化、可验证、可分页，并且不能绕过 Realm policy、`allowed_tracks` action scope、E2EE 可见性与 capability。

## 2. Query 对象

```json
{
  "realm_ids": ["ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5"],
  "object_kinds": ["strand", "message", "morph"],
  "morph_kinds": ["customer_case"],
  "facets": ["assignable"],
  "context_ref": "ak:strand:ATnpmocFhz_fKex3WQSfweBfBfLKp8y4i_EfWE_daew7",
  "filters": [],
  "relation": null,
  "order_by": [],
  "projection": [],
  "cursor": null,
  "limit": 50,
  "wait_for": "ak:cursor:..."
}
```

字段：

- `realm_ids`: REQUIRED，查询范围。
- `object_kinds`: OPTIONAL，限制标准对象类型，例如 `realm`、`space`、`strand`、`message`、`morph`、`relation`、`view`。对象类型只在这里表达；不得用 `filters.field=type` 作为别名。`card` 是 View `item_render`，不是 canonical object type；Board/List 容器必须表达为 `object_kinds=["space"]` + `filters` 限制 Space `kind`。Board/List 内部 item 查询仍按被投影对象表达，例如 `object_kinds=["strand"]` 并通过 `contains` relation 约束到目标 Space。
- `morph_kinds`: OPTIONAL，当 `object_kinds` 包含 `morph` 时进一步限制开放对象类型。
- `facets`: OPTIONAL，schema-declared capability hint 过滤。Facet 不替代对象类型，也不绕过授权、schema、policy、`allowed_tracks` action scope 或 E2EE 可见性；查询命中某 facet 不表示调用方获得该 facet 暗示的写入、排序、状态转换或 renderer 能力。
- `context_ref`: OPTIONAL，`timeline` / `renderer="timeline"` 或 Strand context 的上下文对象引用；它指向业务上下文对象，不指向 RealmCommit。
- `filters`: OPTIONAL，过滤条件。
- `relation`: OPTIONAL，关系扩展条件。
- `order_by`: OPTIONAL，排序规则。
- `projection`: OPTIONAL，返回字段选择。
- `cursor`: OPTIONAL，不透明分页游标。
- `limit`: OPTIONAL，默认 50，执行方 MAY 限制最大值。
- `wait_for`: OPTIONAL，顶层 string，读己之所写等待条件(cursor)；以 `query.schema.json` 的顶层 `wait_for` 为准，不使用 `consistency` 包装对象。

## 3. Filter

```json
{
  "field": "metadata.fields.review_status",
  "op": "eq",
  "value": "in_review"
}
```

`filters[].op` 的合法取值是下方**封闭枚举**（normative）。`op` 的 canonical 真源是 `artifacts/schemas/query.schema.json`（`ak.schema.query.v1`），本表为人类可读视图；执行方 MUST 拒绝表外取值（`schema_violation` / `param_invalid`）。

| `op`（normative enum） | 语义 |
| --- | --- |
| `eq` | 等于 |
| `neq` | 不等于 |
| `in` | 属于给定集合 |
| `not_in` | 不属于给定集合 |
| `lt` | 小于 |
| `lte` | 小于等于 |
| `gt` | 大于 |
| `gte` | 大于等于 |
| `contains` | 包含（集合 / 子串） |
| `exists` | 字段存在 |
| `prefix` | 前缀匹配 |
| `full_text` | 全文匹配 |

字段路径 MUST 使用 dot path。实现 MUST 拒绝访问未授权字段。

## 4. Boolean Filter

```json
{
  "and": [
    { "field": "fields.workflow_type", "op": "eq", "value": "review" },
    { "field": "stage", "op": "neq", "value": "done" }
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
  "target_ref": {"kind":"account","account_id":{"principal_id":"ak:did_core:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw","station_id":"ak:did_core:web:alice-station.example"}}
}
```

`direction` 的合法取值是下方**封闭枚举**（normative）。Relation Query `direction` 的 canonical 真源是 `artifacts/schemas/query.schema.json`（`ak.schema.query.v1`），本表为人类可读视图；执行方 MUST 拒绝表外取值。

| `direction`（normative enum） | 语义 |
| --- | --- |
| `out` | 从当前对象出发 |
| `in` | 指向当前对象 |
| `both` | 双向查询 |

Relation Query 字段：

- `kind`: REQUIRED，关系类型，例如 `contains`、`belongs_to`、`assigned_to`、`promoted_from_discussion`。
- `direction`: REQUIRED，`out` / `in` / `both`。
- `source_ref`: OPTIONAL，限制 relation 起点；使用与 Relation 相同的 typed object-reference string 或完整 ActorId object。
- `target_ref`: OPTIONAL，限制 relation 终点；使用相同 `RelationEndpoint` union。Actor 匹配 MUST 包含 Station，不能只按 DID 匹配。`source_actor_id` / `source_realm_id` / `target_actor_id` / `target_realm_id` 不再是并行 wire 字段；所有端点只由 `source_ref` / `target_ref` 表达。
- `source_type`: OPTIONAL，限制起点类型，例如 `strand`、`actor`、`realm`。业务分类应通过 Realm schema/profile、`metadata.fields`、Relation、labels 或 Morph type 表达；不要把 `card` / `room` 当作 canonical source type。
- `target_type`: OPTIONAL，限制终点类型。
- `depth`: OPTIONAL，关系展开深度；跨 Realm 规则见 `views.md` Lazy Link。

Strand synthesis 与 discussion 的 relation 查询必须遵守有效 access 授权：

- `promoted_from_discussion` 可显示 synthesis 条目来自 discussion 的沉淀关系。
- Strand synthesis 可见只有在有效 access policy 继承或授予 discussion 读取时，才代表 discussion timeline 可读。
- Discussion 可读不代表 Strand synthesis 可写。

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
  "schema",
  "metadata.title",
  "stage",
  "metadata.fields.review_status"
]
```

Projection 只减少返回字段，不提升权限。

## 8. Response

[`query.schema.json`](../../artifacts/schemas/query.schema.json) 只定义可复用的 query / search **请求**形状，不定义通用响应 envelope。每个 URL endpoint 的响应必须以 operation registry 的 `response_schema_ref` 与 OpenAPI binding 为准；v1 没有要求所有查询响应携带 `basis` / `grade`，也没有登记跨 operation 通用的 `key_view_ref` 字段。

若某个 operation 需要 `checkpoint`、barrier cursor、RealmCommit basis 或可验证 proof，必须在该 operation 的 response schema 中逐字段登记。实现不得把私有响应扩展描述成 v1 core 的通用响应契约。

## 9. 安全规则

任何对外暴露可互操作 query / search / projection 语义的执行方 MUST:

- 对 query 做 schema validation。
- 对 Realm、Strand、Message、Morph、Relation、View 和字段做 authorization filtering。
- 把 `facets` 仅作为过滤条件和 projection hint；不得因 facet 字符串扩大授权、启用未声明 reducer 或绕过 Morph profile validation。
- 对 Strand 的所有 track 按 Strand 的 effective scope 做 membership / history visibility 检查：`Strand.scope_circle_id=null` 时按父 Realm 的 Realm-default scope；`scope_circle_id` 指向同 Realm 的 [Circle](../models/circle.md) 时按该 Circle 独立裁剪。Synthesis 与 discussion 同 scope，不存在 per-track 安全边界。
- 对高成本 full_text / relation expansion 限流。
- 不泄露不可见对象是否存在。
- 在 E2EE Realm 中不得对密文正文做服务器全文搜索；客户端本地搜索只能覆盖本设备已解密且当前 actor 仍有权读取的内容。
