---
title: Space Hierarchy
status: candidate
normative: true
stability: v1
updated: 2026-07-02
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Space hierarchy 是 Arkret 的产品结构层：组织、workspace、project、folder、board、list、section、calendar bucket 等都可以用 `ak:space:` 节点表达。

Space hierarchy 可以跨 Realm 导航，但不改变 Realm 边界。Realm 决定谁能接收事件、读历史、解密内容和参与 federation；Space 决定对象在产品结构中位于哪里。

## 2. 基本规则

1. Space hierarchy 使用 `ak.space.parent` 写入 `parent_space_id` cell。
2. 一个 Space MAY 有 0 或 1 个 active parent；需要多归属时使用 Relation / View，而不是多个 parent。
3. Parent Space MAY 位于不同 Realm。跨 Realm parent 只表示导航，不级联任何安全语义。
4. 遍历 Space tree 时，客户端 / 服务端 MUST 对每个 Space 的 `realm_id` 独立做授权检查。
5. `default_realm_id` 只为新建资源提供默认落点；不得被解释为读取或解密授权。

## 3. Space Parent Event

`ak.space.parent` payload：

```json
{
  "kind": "ak.space.parent",
  "payload": {
    "space_id": "ak:space:019640c0-8000-7000-8000-000000000000",
    "parent_space_id": "ak:space:019640a0-8000-7000-8000-000000000000",
    "expected_parent_space_id": null
  }
}
```

`ak.component.space.parent.v1` 的 cell identity、control-plane CBA、CAS basis、acyclic 检测、不可读 ancestor 的 fail-closed 错误与 root/hidden-parent 规则，其唯一 normative 真源是 [`realm-and-space.md` §3.5](./realm-and-space.md#35-akspaceparent-cas_register-basis)。本文件只定义产品导航与查询语义；实现 MUST NOT 从本节另行派生一套 reducer。

## 4. Effective Realm

Space 的 `realm_id` 与 `default_realm_id` 分工如下：

- `realm_id`：Space metadata 自身所在的 home Realm。
- `default_realm_id`：该 Space 下新建资源默认使用的 Realm。

Effective default Realm 解析：

```text
effective_default_realm(space):
  if space already appears in current resolution stack:
    fail closed (space_parent_cycle)
  if space.default_realm_id exists:
    return space.default_realm_id
  if space.parent_space_id exists and parent is readable:
    return effective_default_realm(parent)
  if space.parent_space_id exists and parent is not readable:
    fail closed (space_parent_unreadable)
  return space.realm_id
```

客户端从某个 Space 创建 Strand / Morph / View 时，MUST 把解析结果显式写入新资源的 `realm_id`。服务端 / reducer 不得在签名后根据当前 tree 状态隐式改写资源 Realm。

Effective default Realm 解析 MUST NOT 跨 `ak.realm.link` 跳转。`default_realm_id` 指到哪个 Realm，新资源就只能默认落到该 Realm；即使该 Realm 与其它 Realm 存在 `governed_by`、`discoverable_from`、`confidential_extension_of` 或 migration link（`split_from` / `replaces`），也不得自动 fallback 到 link 邻居。若解析得到的 Realm 已 tombstoned、destroyed、不可达或当前 actor 对其没有创建目标对象的 capability，新写入 MUST `failed_precondition`，`reason_code=realm_unavailable` 或更具体的 terminal / capability reason；客户端只能要求用户显式选择新的 Realm 或执行被授权的 migration/reparent 流程。

## 5. Cross-Realm Navigation

跨 Realm parent 合法，但必须保持以下约束：

- 父 Space 所在 Realm 的成员不会自动成为子 Space home Realm 的成员。
- 子 Space home Realm 的成员不会自动读取父 Space。
- Parent Space archive / tombstone 不自动改变 child Space lifecycle。
- Parent Space 的 `default_realm_id` 只作为 child 省略 `default_realm_id` 时的默认解析输入；它不授予访问目标 Realm 的能力。

如果跨 Realm parent 暴露过多 metadata，实现 SHOULD 使用 minimal metadata profile 或把敏感 child Space 放到不可枚举 parent 下，仅通过授权后的 Relation / View 显示。

## 6. Workflow Containers

`kind=board` / `kind=list` 也是 Space。Strand 位置仍由 `ak.strand.move` / `ak.strand.reorder` 的 cas_register cell 维护；position cell 的 `cell_id` / value shape（`{ list_space_id, rank } | null`）与去重 / 唯一性规则的单一真源是 [`realm-and-space.md` §3.6](./realm-and-space.md#36-strand-位置)，本节不重复定义，只补充跨 Realm placement 约束。

`Space(kind=list).fields` 可承载下列写入 policy；它们是 List 容器状态的一部分，由 `ak.space.create` / `ak.space.update` 的控制面 basis 版本化，不属于 View：

| 字段 | 必填 | 类型 | 语义 |
| --- | --- | --- | --- |
| `wip_limit` | no | `integer`，1..100000 | 目标 List 允许的 active Strand 数上限；省略表示不设置协议级 WIP 上限。 |
| `wip_limit_enforcement` | conditional | `enum(warn, reject, require_review)` | `wip_limit` 存在时必填。`warn` 允许写入但产生稳定诊断；`reject` 以 `failed_precondition` 拒绝；`require_review` 要求写入引用 accepted review / approval proof。 |

`ak.strand.move` / `ak.strand.reorder` 必须在其 `seal_basis` 对应的目标 List state 上计算 effective WIP，计数只包含同一 Board 下 position cell 当前指向该 List 且 Strand 非终态的 distinct Strand。写入授权缓存键 MUST 至少包含 `(realm_id, frontier_digest, target_list_space_id)`；不得包含 View id，也不得读取 `View.grouping.wip_limit_enforcement`。`wip_limit_override=true` 只允许持有相应 override capability 的 actor 绕过目标 List policy；缺少 override 时按上述 enforcement 收口。

默认情况下，workflow placement MUST resolve to the same effective Realm as the Strand：

- Strand `realm_id = R`
- Board Space effective default Realm MUST be `R`
- List Space effective default Realm MUST be `R`

需要跨 Realm 展示时，使用 View / Relation 聚合，不要把 Strand placement cell 写到另一个 Realm 的 Space 中，除非 profile 显式定义 cross-Realm placement 语义和授权规则。

## 7. Query

Space hierarchy 查询返回产品结构，不返回 Realm link graph。

请求字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `root_space_id` | `id:space` | 起点 Space。 |
| `depth` | `integer` | 查询深度；服务端 MUST enforce 最大值。 |
| `include_hidden_parent` | `boolean` | 是否返回不可读 parent 的占位。 |
| `include_realm_summary` | `boolean` | 是否返回每个 Space 的 home/default Realm 摘要。 |

响应项：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `space_id` | `id:space` | Space ID。 |
| `realm_id` | `id:realm` | Space metadata home Realm。 |
| `default_realm_id` | `id:realm` | 可选默认资源 Realm。 |
| `effective_default_realm` | `id:realm` | 解析后的默认资源 Realm。 |
| `parent_space_id` | `id:space` | 可选 parent。 |
| `accessible` | `boolean` | 调用方是否可读取该 Space metadata。 |
| `children` | `object[]` | 子 Space 摘要。 |

## 8. 与 Realm Link 的关系

Space hierarchy 是用户结构；Realm link 是安全边界之间的治理 / 发现 / 来源关系。二者不得混用。

例如，`Pricing Strategy` Space 可以挂在 `/Acme/Projects` 下，同时默认资源 Realm 是 `R_pricing_confidential`。`R_pricing_confidential` 是否 `governed_by R_acme_org` 是 Realm link 问题，不是 Space parent 问题。
