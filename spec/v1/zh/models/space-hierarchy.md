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

Space hierarchy MUST 完整位于同一个 Realm 内。Realm 决定谁能接收事件、读历史、解密内容和参与 federation；Space 决定对象在产品结构中位于哪里。

**权限不随层级继承（normative）**：Space 的当前父子关系与创建时归属均不授予或撤销权限。移动 Space / Strand 只改变导航或 placement；对象原有 Realm、Circle 和显式 capability 仍分别验证。操作 Space 本身需要对应授权；目标容器的 `child_scope_policy` 可以拒绝移动，但 MUST NOT 自动改变被移动对象的 scope 或密钥访问资格。授权选择器不支持子树继承，见 [resource-selector-grammar.md §6](../authz/resource-selector-grammar.md#6-匹配算法)。

## 2. 基本规则

1. Space hierarchy 使用 `ak.space.parent` 写入 `parent_space_id` cell。
2. 一个 Space MAY 有 0 或 1 个 active parent；需要多归属时使用 Relation / View，而不是多个 parent。
3. Parent Space MUST 与子 Space 具有相同的实际 `realm_id`；初始 parent 与后续改挂遵守同一规则。
4. 遍历 Space tree 时，客户端 / 服务端 MUST 对每个 Space 的 `realm_id` 独立做授权检查。
5. 新资源 MUST 显式填写当前 Space 的 `realm_id`，并独立通过授权验证。

## 3. Space Parent Event

`ak.space.parent` payload：

```json
{
  "kind": "ak.space.parent",
  "payload": {
    "space_id": "ak:space:AScD0xd0vWSGWhC2n9BZHco7N_jYnNgmEIifpAo_uxUJ",
    "parent_space_id": "ak:space:AUwbeCUMZI_GuEADljowhvFwzl6wIkaSiCDhu2oaOqTg",
    "expected_parent_space_id": null
  }
}
```

`ak.component.space.parent.v1` 的 cell identity、control-plane CBS、CAS basis、acyclic 检测、不可读 ancestor 的 fail-closed 错误与 root/hidden-parent 规则，其唯一 normative 真源是 [`realm-and-space.md` §3.5](./realm-and-space.md)。本文件只定义产品导航与查询语义；实现 MUST NOT 从本节另行派生一套 reducer。

## 4. 新资源的 Realm

Space 的 `realm_id` 是其 metadata 和结构子资源所属的唯一 Realm。客户端从 Space 创建资源时 MUST 显式使用该值并独立验证 scope 与创建 capability；服务端 MUST NOT 在签名后改写 Realm。Realm 不可用或无创建授权时写入 MUST fail closed；不得通过 ancestor 或 Realm link fallback。

## 5. 跨 Realm 展示

跨 Realm 内容 MUST 使用已定义的 View 聚合或普通 Relation / 链接，逐目标授权并标明所属 Realm；不得伪装成 canonical parent 或 contains placement。此类引用不进入 Space 的删除依赖集合。普通 reparent / move MUST NOT 修改对象的 Realm；本规范不定义跨 Realm 迁移入口。

同 Realm 不自动授予 Circle 或对象读取权限。archive / restore 不级联；tombstone 的完整依赖保护见 `realm-and-space.md` §3.4。

## 6. Workflow Containers

`kind=board` / `kind=list` 也是 Space。Strand 位置仍由 `ak.strand.move` / `ak.strand.reorder` 的 causal_register cell 维护；position cell 的 `cell_id` / value shape（`{ list_space_id, rank } | null`）与去重 / 唯一性规则的单一真源是 [`realm-and-space.md` §3.6](./realm-and-space.md#36-strand-位置)，本节不重复定义，只补充跨 Realm placement 约束。

`Space(kind=list).fields` 可承载下列写入 policy；它们是 List 容器状态的一部分，由 `ak.space.create` / `ak.space.update` 的控制面 basis 版本化，不属于 View：

| 字段 | 必填 | 类型 | 语义 |
| --- | --- | --- | --- |
| `wip_limit` | no | `integer`，1..100000 | 目标 List 允许的 active Strand 数上限；省略表示不设置协议级 WIP 上限。 |
| `wip_limit_enforcement` | conditional | `enum(warn, reject, require_review)` | `wip_limit` 存在时必填。`warn` 允许写入但产生稳定诊断；`reject` 以 `failed_precondition` 拒绝；`require_review` 要求写入引用 accepted review / approval proof。 |

`ak.strand.move` / `ak.strand.reorder` 必须在其 `seal_basis` 对应的目标 List state 上计算 effective WIP，计数只包含同一 Board 下 position cell 当前指向该 List 且 Strand 非终态的 distinct Strand。比较谓词固定为后像：`ak.strand.move` 先把本次移动应用到集合，再仅当 `count_after > wip_limit` 时触发 enforcement；目标 List 已包含该 Strand 时不得重复计数。`ak.strand.reorder` 不改变成员集合，因此不执行 WIP 拒绝（即使 List 当前恰好等于或因既有状态已经超过上限），只校验 rank / position 的其它规则。写入授权缓存键 MUST 至少包含 [`../authz/constraint-schema.md` §2.3](../authz/constraint-schema.md) 为 `scope_limitation`（`wip_limit_override` 分支）登记的 `(realm_id, frontier_digest, target_container_id)`，其中 `target_container_id` 在本场景即目标 List Space id；不得包含 View id，也不得读取 `View.grouping.wip_limit_enforcement`。`wip_limit_override=true` 只允许持有相应 override capability 的 actor 绕过目标 List policy；缺少 override 时按上述 enforcement 收口。

workflow placement MUST 属于同一个实际 Realm：

- Strand `realm_id = R`
- Board Space `realm_id` MUST be `R`
- List Space `realm_id` MUST be `R`

需要跨 Realm 展示时，使用 View / Relation 聚合，不要把 Strand placement cell 写到另一个 Realm 的 Space 中；任何 profile 都不得豁免同 Realm 约束。

## 7. Query

Space hierarchy 查询返回产品结构，不返回 Realm link graph。

请求字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `root_space_id` | `id:space` | 起点 Space。 |
| `depth` | `integer` | 查询深度；服务端 MUST enforce 最大值。 |
| `include_hidden_parent` | `boolean` | 是否返回不可读 parent 的占位。 |
| `include_realm_summary` | `boolean` | 是否返回每个 Space 的 Realm 摘要。 |

响应项：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `space_id` | `id:space` | Space ID。 |
| `realm_id` | `id:realm` | Space metadata home Realm。 |
| `parent_space_id` | `id:space` | 可选 parent。 |
| `accessible` | `boolean` | 调用方是否可读取该 Space metadata。 |
| `children` | `object[]` | 子 Space 摘要。 |

## 8. 与 Realm Link 的关系

Space hierarchy 是用户结构；Realm link 是安全边界之间的治理 / 发现 / 来源关系。二者不得混用。

例如，机密 Realm 的 `Pricing Strategy` Space 可以通过 View 展示在组织入口，但不能挂到另一个 Realm 的 `/Acme/Projects` Space 下。`R_pricing_confidential` 是否 `governed_by R_acme_org` 是 Realm link 问题，不是 Space parent 问题。
