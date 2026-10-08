---
title: Space Hierarchy
status: candidate
normative: true
stability: v1
updated: 2026-10-09
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Space hierarchy 是 Arkret 的产品结构层：组织、workspace、project、folder、board、list、section、calendar bucket 等都可以用 `ak:space:` 节点表达。

Space hierarchy MUST 完整位于同一个 Realm 内。Realm 决定谁能接收事件、读历史、解密内容和参与 federation；Space 决定对象在产品结构中位于哪里。

**权限不随层级继承（normative）**：Space 的当前父子关系与创建时归属均不授予或撤销权限。移动 Space / Strand 只改变导航或 placement；对象原有 Realm、Circle 和显式 capability 仍分别验证。操作 Space 本身需要对应授权；目标容器的 `child_scope_policy` 可以拒绝移动，但 MUST NOT 自动改变被移动对象的 scope 或密钥访问资格。授权选择器不支持子树继承，见 [resource-selector-grammar.md §6](../authz/resource-selector-grammar.md#6-匹配算法)。

## 2. 基本规则

1. Space hierarchy 使用 `ak.space.parent` 写入 `parent_space_id` typed current result。
2. 一个 Space MAY 有 0 或 1 个 active parent；需要多归属时使用 Relation / View，而不是多个 parent。
3. Parent Space MUST 与子 Space 具有相同的实际 `realm_id`；初始 parent 与后续改挂遵守同一规则。
4. 遍历 Space tree 时，客户端 / 服务端 MUST 对每个 Space 的 `realm_id` 独立做授权检查。
5. 新资源 MUST 显式填写当前 Space 的 `realm_id`，并独立通过授权验证。

## 3. Space Parent Event

`ak.space.parent` payload：

```json fragment
{
  "kind": "ak.space.parent",
  "payload": {
    "space_id": "ak:space:AScD0xd0vWSGWhC2n9BZHco7N_jYnNgmEIifpAo_uxUJ",
    "parent_space_id": "ak:space:AUwbeCUMZI_GuEADljowhvFwzl6wIkaSiCDhu2oaOqTg",
    "expected_parent_space_id": null
  }
}
```
`space_parent` 的 typed current result identity、CAS basis、acyclic 检测、不可读 parent 的 fail-closed 错误与 root/不可用结构引用规则，其唯一 normative 真源是 [`realm-and-space.md` §3.5](./realm-and-space.md#35-akspaceparent-因果父边)。本文件只定义产品导航；实现 MUST NOT 从本节另行派生一套 reducer。

## 4. 新资源的 Realm

Space 的 `realm_id` 是其 metadata 和结构子资源所属的唯一 Realm。客户端从 Space 创建资源时 MUST 显式使用该值并独立验证 scope 与创建 capability；服务端 MUST NOT 在签名后改写 Realm。Realm 不可用或无创建授权时写入 MUST fail closed；不得通过 ancestor 或 Realm link fallback。

## 5. 跨 Realm 展示

跨 Realm 内容 MUST 使用已定义的 View 聚合或普通 Relation / 链接，逐目标授权并标明所属 Realm；不得伪装成 canonical parent 或 contains placement。此类引用不进入 Space 的删除依赖集合。普通 reparent / move MUST NOT 修改对象的 Realm；本规范不定义跨 Realm 迁移入口。

同 Realm 不自动授予 Circle 或对象读取权限。archive / restore 不级联；tombstone 的完整依赖保护见 `realm-and-space.md` §3.4。

## 6. Workflow Containers

`kind=board` / `kind=list` 也是 Space。Strand 位置仍由 `ak.strand.move` / `ak.strand.reorder` 的 current-value projection typed current result 维护；position typed current result 的 `result_id` / value shape（`{ list_space_id, rank } | null`）与去重 / 唯一性规则的单一真源是 [`realm-and-space.md` §3.6](./realm-and-space.md#36-strand-位置)，本节不重复定义，只补充跨 Realm placement 约束。

`Space(kind=list).fields` 可承载下列写入 policy；它们是 List 容器状态的一部分，由 `ak.space.create` / `ak.space.update` 的控制面 basis 版本化，不属于 View：

| 字段 | 必填 | 类型 | 语义 |
| --- | --- | --- | --- |
| `wip_limit` | no | `integer`，1..100000 | 目标 List 允许的 active Strand 数上限；省略表示不设置协议级 WIP 上限。 |
| `wip_limit_enforcement` | conditional | `enum(warn, reject, require_review)` | `wip_limit` 存在时必填。`warn` 允许写入并产生下述服务端诊断；`reject` 以 `failed_precondition` 拒绝；`require_review` 要求下述 List WIP approval signature。 |

`ak.strand.move` / `ak.strand.reorder` 必须在接纳它的同一权威 cut 中读取目标 List current state 并计算 effective WIP；已登记并发前像仅为可选的完整 `expected_position`，不新增目标 List `expected_revision`。计数只包含同一 Board 下 position typed current result 当前指向该 List 且 Strand 非终态的 distinct Strand。比较谓词固定为后像：`ak.strand.move` 先把本次移动应用到集合，再仅当 `count_after > wip_limit` 时触发 enforcement；目标 List 已包含该 Strand 时不得重复计数。`ak.strand.reorder` 不改变成员集合，因此不执行 WIP 拒绝（即使 List 当前恰好等于或因既有状态已经超过上限），只校验 rank / position 的其它规则。写入授权缓存键 MUST 至少包含 [`../authz/constraint-schema.md` §2.3](../authz/constraint-schema.md) 为 `scope_limitation`（`wip_limit_override` 分支）登记的 `(realm_id, source_commit_ref, target_container_id)`，其中 `target_container_id` 在本场景即目标 List Space id；不得包含 View id，也不得读取 `View.grouping.wip_limit_enforcement`。`wip_limit_override=true` 只允许持有相应 override capability 的 actor 绕过目标 List policy；缺少 override 时按上述 enforcement 收口。

`warn` 的稳定诊断是治理 Station 的**服务端结构化操作日志**，不是 Event、typed current result 或成功 outcome 字段。超限决策时 MUST 使用固定键 `list_wip_limit_exceeded`，并记录完整 `realm_id`、`event_id`、`board_space_id`、`list_space_id`、`strand_id`、`wip_limit`、`count_after` 与 List metadata current 的完整 `{commit_id,stream_position}` revision；实现 MAY 增加本地 trace 字段。该日志不向提交者或 peer 承诺交付，不能作为同步、授权或审计真相源；`committed`／`duplicate` 的 closed outcome 保持原样。exact retry 仍返回原 outcome，不重新求值 WIP，也不要求重发一条日志；如果执行器重发，键及绑定的 `event_id` 不变。日志可在事务完成前写出，因此失败的后续步骤也可能留下同键记录；只有已接受 Event／Commit 才证明写入成功。

`require_review` 在超限且无有效 override 时，MUST 由提交容器 `EventAdmissionSubmission.approval_signatures[]` 中一份合格的 detached approval signature 满足，使用 [`../authz/constraint-schema.md` §9.2.2](../authz/constraint-schema.md#922-approval_context该审批要求来自哪一层normative) 的 `list_wip` context。签名绑定完整预写 `ak.strand.move` Event、精确目标 List 及其**同一权威 cut** 的 metadata current revision；所需不同 approver 数量固定为一。approver MUST 非本次发起者，且在该 cut 对目标 List 持有有效 `ak.space.update` capability；approval 不能授予移动者 `ak.strand.move` 权限，也不能替代独立命中的 grant／Realm governance 审批层。其签名、时间、nonce、accepted-at 审计与 exact retry 均沿用 §9.2，不另造 review Event、队列或 payload 引用。目标 List revision 改变、资格不足或证据无效时，返回既有 `claim_required` + `approval_required`，零写入；无法验证证据的实现 MUST fail closed。`reject` 不接受 approval 来豁免；有效 `wip_limit_override=true` 仍先于 enforcement 生效，且不消费不需要的 List WIP approval。

workflow placement MUST 属于同一个实际 Realm：

- Strand `realm_id = R`
- Board Space `realm_id` MUST be `R`
- List Space `realm_id` MUST be `R`

需要跨 Realm 展示时，使用 View / Relation 聚合，不要把 Strand placement typed current result 写到另一个 Realm 的 Space 中；任何 profile 都不得豁免同 Realm 约束。

## 7. Query

本节定义**客户端导航算法**，不定义独立 wire read surface。v1 的 Space 集合读取使用已登记的 `ak.self.space.read.list.v1`（HTTP `GET /_arkret/self/realms/{realm_id}/spaces`；gRPC `SelfSpace/List`；MQ `self.space.query.list`），返回 [`ProjectionSpaceList` / `ProjectionSpaceRow`](../../artifacts/schemas/service-operation-dtos.schema.json)。它是调用方可见的派生读模型，不是 canonical truth source；当前父边的权威语义仍由 §3 引用的 `space_parent` family 决定。

HTTP 的查询参数只有现有 binding 定义的 `include_terminal`、`cursor`、`limit`，分页结果携带 `total`、`has_more` 和可选 `next_cursor`。具体 shape 与参数上限见 [HTTP binding](../../artifacts/openapi/arkret-service-api.openapi.yaml)。本节不增加树查询的请求字段、响应 schema、operation、binding 或 bundle。

客户端 MAY 从已获授权的 list 行及已验证的 current 材料构造局部导航视图，边界如下：

1. 以 `space_id` 索引已加载行，按已知 `parent_space_id` 组织同 Realm 父子关系；起点、显示深度和本地 `children` 数组只是 UI 选择，不发送为额外 wire 查询字段。遍历 MUST 有界并检测重复节点；环与不可用结构引用遵守 [`realm-and-space.md` §3.4–§3.5](./realm-and-space.md#35-akspaceparent-因果父边)，不得重选 current parent 或将无效边投影成有效 contains。
2. `parent_space_id` 在 list 行中可缺席或为 null。成员缺席 MUST NOT 被当作已确认 root；显式 null 或已验证 `space_parent` current 的 null 成员才表达已知无父。若非空 parent 未在已加载材料中，客户端 MUST 保留该引用的不完整状态，不能将 child 改挂到 canonical root。父节点缺席可能来自分页、授权过滤或状态变化；即使 `has_more=false`，也不能证明缺席 parent 不存在、不可读或已终态，跨页结果也不承诺同一权威 cut。
3. list 不提供隐藏祖先链或 `accessible=false` 节点。客户端 MAY 为已经披露的 parent 引用显示本地“不可用／未加载”提示，但 MUST NOT 推断该 parent 的 metadata、Realm 摘要、上级、可读性或存在性，也不得为补齐导航扩大读取授权。没有已披露 parent 引用时不得合成具名占位节点。该提示不是服务端返回的隐藏 parent。
4. Realm 摘要只能来自调用方独立获授权的既有 Realm 材料；`ProjectionSpaceRow.realm_id` 仅标明归属，不携带摘要或授予额外读取权。Space 行的 `title` / `encrypted_metadata` 仍遵守其 schema 与既有解密授权；树形展示不增加可见字段。

本裁决撤销原散文中的 `root_space_id` / `depth` / `include_hidden_parent` / `include_realm_summary` 请求合同及 `accessible` / nested `children` 响应承诺；局部导航不被声称为原树查询的无损替换。未来若需要服务端树查询，MUST 先登记精确 operation、schema、binding、bundle、分页／深度／不可读 parent／防枚举规则与 conformance 向量，不得以本节作为未登记接口的依据。

## 8. 与 Realm Link 的关系

Space hierarchy 是用户结构；Realm link 是安全边界之间的治理 / 发现 / 来源关系。二者不得混用。

例如，机密 Realm 的 `Pricing Strategy` Space 可以通过 View 展示在组织入口，但不能挂到另一个 Realm 的 `/Acme/Projects` Space 下。`R_pricing_confidential` 是否 `governed_by R_acme_org` 是 Realm link 问题，不是 Space parent 问题。
