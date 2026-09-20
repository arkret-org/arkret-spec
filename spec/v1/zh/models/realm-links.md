---
title: Realm Links
status: candidate
normative: true
stability: v1
updated: 2026-07-02
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Realm 是硬安全边界，不承担产品导航树职责。因此 Arkret v1 不定义通用 `Realm hierarchy`、`parent Realm` 或 `child Realm` 结构关系。Realm 内的子事件 / 子消息边界由 [Circle](./circle.md) 承担（intra-Realm，不跨 federation；可按父 Realm floor 启用独立 MLS）；若两个独立 Realm 需要治理、发现、mirror 或 confidential extension 关系，必须使用本文件定义的 `ak.realm.link` 并明确 `link_kind`。

本文定义 Realm 之间的显式 **link graph**：Realm 可以因为治理、发现、导入导出、机密扩展、mirror、迁移或审计需要互相引用，但这些 link 不表达包含关系，也不自动传播权限。

产品导航、项目树、board/list 嵌套和跨 Realm 分类统一由 [`space-hierarchy.md`](./space-hierarchy.md) 的 Space hierarchy 表达。

## 2. 设计原则

1. Realm link 是有向图，不是树。
2. Link kind 必须显式声明语义；实现不得把任意 Realm link 解释成 containment。
3. Link 不自动级联 membership、capability、history visibility、E2EE key、schema、policy、retention、notification 或 Applet permission。
4. Link graph 不承载跨 Realm 状态继承；目标 Realm 的成员、policy 与 capability 必须由目标 Realm 的本地 Event 独立表达。
5. 遍历 link graph 时，节点 MUST 对每个 Realm 独立做授权和历史可见性检查。
6. Link graph MAY 含环；遍历器 MUST 以 visited-set 截断重复节点，不得把一般有向图误判为树。`target_realm_id` 等于事件所属 Realm 的 self-link 没有跨边界语义，reducer MUST 以 `schema_violation`、`reason_code=realm_link_self_reference` 拒绝。
7. Realm 之间的治理、发现、准入引用、迁移或 mirror 边 MUST 使用 `ak.realm.link`；实现 MUST NOT 用端点为 Realm 的 `ak.relation` 绕过本文件的 reciprocal、commitment 与 no-cascade 规则。Relation 仍可把 Realm 当作普通内容引用端点，但不得获得 Realm-link 语义。

## 3. 标准 Link Kind

`ak.realm.link` 是 Realm link 的统一 state event。Payload：

```json fragment
{
  "kind": "ak.realm.link",
  "payload": {
    "target_realm_id": "ak:realm:Af29dMeS3_bzsohIaqBzCH4Ogg2YE-0MrPZfCoFSLLwc",
    "link_kind": "governed_by",
    "status": "active",
    "label": "Acme governance realm",
    "commitment": "sha256:0000000000000000000000000000000000000000000000000000000000000000"
  }
}
```
Payload 字段：

| 字段 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- |
| `target_realm_id` | yes | `id:realm` | 被引用的目标 Realm。 |
| `link_kind` | yes | `string` | Link 语义，标准值见下表；profile MAY 注册额外值。 |
| `status` | yes | `enum(active,rejected,tombstoned)` | 本侧声明的 link 状态。这是 Realm Link 自己的 closed 状态字段；语义由本节定义，不需要 common 命名例外。 |
| `label` | no | `string` | 本地显示标签；不参与授权或确认语义。 |
| `commitment` | no | `digest` | profile-specific 承诺值；需要双方确认、mirror、migration、confidential extension 或 attestation 的 profile MAY 要求它并定义 transcript。core `ak.realm.link` 不给该字段赋予通用授权语义。 |

`status` MUST 出现在已签名的 `ak.realm.link` Event payload 中。操作 DTO 或 builder 若向调用方暴露 `status="active"` 默认值，MUST 在 Event canonicalization / signing 之前把该默认值 materialize 到 payload；reducer / receiver MUST 拒绝缺少 `status` 的持久 `ak.realm.link` Event。

标准 `link_kind`：

| kind | 含义 | 是否允许授权派生 |
| --- | --- | --- |
| `governed_by` | 本 Realm 的治理根或组织治理 Realm；它只表达关系，不传播 authority 或 policy。 | no |
| `discoverable_from` | 本 Realm 可从目标 Realm 或其公开目录发现。 | no |
| `join_gate_from` | 本 Realm 的 join policy 可在两个 Realm 由同一 current governing Station 治理时，引用目标 Realm 的 current membership 作为 gate。 | no |
| `confidential_extension_of` | 本 Realm 是另一个 Realm 中某个 Strand / Space / discussion 的机密扩展。 | no |
| `mirror_of` | 本 Realm 是目标 Realm 的镜像、只读副本或同步投影；mirror profile 必须定义方向、冲突处理、commitment / evidence transcript 与可写边界。 | no |
| `split_from` | 本 Realm 从目标 Realm 拆分或迁移而来。 | no |
| `replaces` | 本 Realm 替代目标 Realm。 | no，除非 replacement profile 明确声明。 |

Profile MAY 注册额外 `link_kind`。扩展值 MUST 使用 `x.<reverse-dns>.<name>` 形式并进入该 profile 的机读登记；未声明相应 profile 的 receiver MUST fail closed。扩展登记还必须声明：

- 是否需要双方确认。
- 是否可被目录展示。
- 是否允许任何 derived grant；current-v1 的答案 MUST 为 `false`，未来 profile 只有完整注册 source evidence、peer operation、freshness、handoff 与撤销传播合同后才能改变。
- 是否涉及 cross-Realm export / import。
- 是否需要 commitment / evidence / attestation。

## 4. Link 状态

`status` 取值：

- `active`
- `rejected`
- `tombstoned`

`ak.realm.link` 写入 `realm_link` typed current result。typed current result subject 是 `(target_realm_id, link_kind)` 元组，Realm 由 Event scope 给出；`domain reducer=current-value projection`、`execution=data`；当前 status 是该 stream 上最后一个被接受的写入，次序只由 `stream_position` 给出；导航只从该当前值投影。写入必须持有 `ak.realm.link` capability（聚合 `ak.realm.admin` 也可覆盖该 event kind）。

允许的状态迁移如下；`absent` 只表示尚无 typed current result，不是 wire 状态：

| from | to | 说明 |
| --- | --- | --- |
| `absent` | `active` / `rejected` / `tombstoned` | 创建声明；直接 tombstone 用于幂等删除。 |
| `active` | `active` / `rejected` / `tombstoned` | 同态写可更新 label/commitment；拒绝或终止。 |
| `rejected` | `rejected` / `active` / `tombstoned` | 本侧可在新的已授权 state-changing Event 中重新接受。 |
| `tombstoned` | `tombstoned` | 终态；仅允许字节等价的幂等重放。 |

未列出的迁移 MUST 以 `failed_precondition`、`reason_code=realm_link_invalid_transition` 拒绝。该 family 是普通 `current-value projection`：每条写入按其声明的业务前态验证迁移，合法并发写由 Station 在该 stream 上串行化，当前值是最后一个被接受的写入，不产生 `⊥`，不得按时间戳、深度或接收顺序挑选。机器可执行 transition matrix、tombstone 终态、幂等重放与并发 winner 行为由 `ak.vector.realm_link.transition_matrix.v1` 固化。

Projection MAY 派生：

- `confirmed`：仅当声明该 link 的 profile 明确要求双方确认，并登记 `reciprocal_kind` 后才可派生；source 侧 `(source → target, link_kind)` 与 target 侧 `(target → source, reciprocal_kind)` 必须同时 active 且 commitment transcript 匹配。只有 profile 明确把 kind 声明为 symmetric 时，`reciprocal_kind` 才可与 `link_kind` 相同；`governed_by`、`discoverable_from`、`join_gate_from`、`confidential_extension_of`、`mirror_of`、`split_from` 与 `replaces` 均不得仅因反向出现同名 kind 就判为 confirmed。
- `unconfirmed_link`：只有一侧声明。
- `rejected`：任一侧拒绝。
- `tombstoned`：任一侧 tombstone 或 Realm lifecycle 使 link 失效。

默认情况下，`ak.realm.link` 是单侧声明，core 标准 kind 在没有额外 profile 时不会产生 `confirmed`。需要双方确认的 profile MUST 规定目标 Realm 中的 reciprocal event 形态、`reciprocal_kind` 映射和 commitment 绑定规则。

## 5. 禁止隐式级联

以下内容 MUST NOT 因 Realm link 自动级联：

- membership
- capability grant
- admin / moderation 权限
- history visibility
- E2EE group key / MLS epoch
- schema mutation
- retention / legal hold
- notification rule
- Applet write permission

例如，Alice 是 governance Realm 成员，不代表 Alice 自动能读取 governed Realm。

`join_gate_from` 是本节 no-cascade 规则的受限读取例外，不复制 membership：它只允许目标 Realm 的 join admission 按
[`../governance/join-policy.md` §3.1](../governance/join-policy.md) 在**同一 current governing Station** 的原子接纳事务中
读取 source Realm authoritative current `member_state`。它不承载 claim snapshot，不授予跨 Station 读取权，也不让 source
membership 成为目标 Realm current row。缺少 active link、两个 Realm 不再由同一 Station 治理、handoff 正在发生，或
authoritative row 无法在一致事务 cut 中读取时，gate MUST fail closed。

## 6. Link 不传播状态（normative）

current-v1 的 Realm link 只表达显式关系，**永不**自动传播 membership、capability、policy、retention 或 notification
状态。`governed_by` 也不构成 source Realm current state 的 authenticated carrier，不能把 source Realm 的成员、grant 或
policy 解释成目标 Realm authority。

需要在多个 Realm 表达相同治理意图时，每个目标 Realm 的 current controller／获授权 issuer 必须分别签发该 Realm 的本地
member、join-policy、policy 或 `ak.capability.grant` Event；governing Station 按各 Realm 自己的 current state 接纳。
产品 MAY 提供批量 authoring workflow，但每个输出仍是目标 Realm 的独立 Event、EventId、签名和 RealmCommit，不得产生
隐式继承 row、共享 revision 或跨 Realm 自动撤销。

普通 `ak.capability.grant` 的 root 和 parent refs 必须属于 Event 的目标 Realm。source Realm 状态 MAY 作为 UI 建议，
但不得成为 reducer 输入或授权依据。旧 `ak.realm.inheritance_policy`、`ak.capability.derived`、
`inherits_policy_from` 与 effective-policy merge surface 已从 current-v1 删除；实现不得 reserved、alias、双读或把历史
projection 重新解释为目标 Realm current state。未来 profile 若要重新引入自动传播，必须同时定义真实 producer、source
Station 签名的 current evidence、peer operation、freshness、handoff 与撤销传播合同。

## 7. Query

Realm link 查询返回 link graph，不返回产品导航树。产品导航应查询 Space hierarchy。
请求 path/query 参数以 [`operation-registry.json`](../../artifacts/registry/operation-registry.json) 的
对应 operation 行为唯一权威；closed 响应项以
[`realm-link-operations.schema.json`](../../artifacts/schemas/realm-link-operations.schema.json) 为唯一权威。
§4 的 confirmed / unconfirmed projection 规则不增加未在该 operation artifact 登记的 wire 字段。

## 8. 与 Space Hierarchy 的关系

不同 Realm 的 Space 只能由 View 聚合展示，不能形成跨 Realm parent。例如（缩进表示 View 展示，不是 parent）：

```text
Acme (Space, realm_id=R_org)
  Projects (Space, realm_id=R_org)
    Website Redesign (Space, realm_id=R_default)
    Pricing Strategy (Space, realm_id=R_confidential)
```

这里 `R_default` 与 `R_confidential` 不需要是 parent/linked Realm。若存在关系，也应使用明确 kind，例如：

```text
R_confidential -- confidential_extension_of --> R_default
R_confidential -- governed_by --> R_org
```

这些 link 不改变任何 Realm 的成员、密钥或历史可见性。
