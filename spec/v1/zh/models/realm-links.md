---
title: Realm Links
status: candidate
normative: true
stability: v1
updated: 2026-06-10
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Realm 是硬安全边界，不承担产品导航树职责。因此 Cokret v1 不定义通用 `Realm hierarchy`、`parent Realm` 或 `child Realm` 结构关系。Realm 内的子事件 / 子消息边界由 [Circle](./circle.md) 承担（intra-Realm，不跨 federation；可按父 Realm floor 启用独立 MLS）；若两个独立 Realm 需要治理、发现、mirror 或 confidential extension 关系，必须使用本文件定义的 `ck.realm.link` 并明确 `link_kind`。

本文定义 Realm 之间的显式 **link graph**：Realm 可以因为治理、发现、导入导出、机密扩展、mirror、迁移或审计需要互相引用，但这些 link 不表达包含关系，也不自动传播权限。

产品导航、项目树、board/list 嵌套和跨 Realm 分类统一由 [`space-hierarchy.md`](./space-hierarchy.md) 的 Space hierarchy 表达。

## 2. 设计原则

1. Realm link 是有向图，不是树。
2. Link kind 必须显式声明语义；实现不得把任意 Realm link 解释成 containment。
3. Link 不自动级联 membership、capability、history visibility、E2EE key、schema、policy、retention、notification 或 Applet permission。
4. 任何跨 Realm 继承或派生 grant 必须由目标 Realm 显式 opt-in，且只能收窄。
5. 遍历 link graph 时，节点 MUST 对每个 Realm 独立做授权和历史可见性检查。

## 3. 标准 Link Kind

`ck.realm.link` 是 Realm link 的统一 state event。Payload：

```json
{
  "kind": "ck.realm.link",
  "payload": {
    "target_realm_id": "ck:realm:91085a00-8000-7000-8000-000000000000",
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
| `status` | yes | `enum(active,rejected,tombstoned)` | 本侧声明的 link 状态。 |
| `label` | no | `string` | 本地显示标签；不参与授权或确认语义。 |
| `commitment` | no | `hash` | profile-specific 承诺值；需要双方确认、mirror、migration、confidential extension 或 attestation 的 profile MAY 要求它并定义 transcript。core `ck.realm.link` 不给该字段赋予通用授权语义。 |

`status` MUST 出现在已签名的 `ck.realm.link` Event payload 中。操作 DTO 或 builder 若向调用方暴露 `status="active"` 默认值，MUST 在 Event canonicalization / signing 之前把该默认值 materialize 到 payload；reducer / receiver MUST 拒绝缺少 `status` 的持久 `ck.realm.link` Event。

标准 `link_kind`：

| kind | 含义 | 是否允许授权派生 |
| --- | --- | --- |
| `governed_by` | 本 Realm 的治理根或组织治理 Realm。 | MAY，但必须由本 Realm policy 显式声明。 |
| `discoverable_from` | 本 Realm 可从目标 Realm 或其公开目录发现。 | no |
| `join_gate_from` | 本 Realm 的 join policy 可引用目标 Realm 的 membership / claim snapshot 作为 gate。 | no |
| `inherits_policy_from` | 本 Realm 选择性继承目标 Realm 的收窄型 policy。 | MAY，必须 narrow-only。 |
| `confidential_extension_of` | 本 Realm 是另一个 Realm 中某个 Strand / Space / discussion 的机密扩展。 | no |
| `mirror_of` | 本 Realm 是目标 Realm 的镜像、只读副本或同步投影；mirror profile 必须定义方向、冲突处理、commitment / evidence transcript 与可写边界。 | no |
| `split_from` | 本 Realm 从目标 Realm 拆分或迁移而来。 | no |
| `replaces` | 本 Realm 替代目标 Realm。 | no，除非 replacement profile 明确声明。 |

Profile MAY 注册额外 `link_kind`，但必须声明：

- 是否需要双方确认。
- 是否可被目录展示。
- 是否允许任何 derived grant。
- 是否涉及 cross-Realm export / import。
- 是否需要 commitment / evidence / attestation。

## 4. Link 状态

`status` 取值：

- `active`
- `rejected`
- `tombstoned`

Projection MAY 派生：

- `sealed`：要求双方声明的 kind 同时 active。
- `unconfirmed_link`：只有一侧声明。
- `rejected`：任一侧拒绝。
- `tombstoned`：任一侧 tombstone 或 Realm lifecycle 使 link 失效。

默认情况下，`ck.realm.link` 是单侧声明。需要双方确认的 profile MUST 规定目标 Realm 中的 reciprocal event 形态和 commitment 绑定规则。

## 5. 禁止隐式级联

以下内容 MUST NOT 因 Realm link 自动级联：

- membership
- capability grant
- admin / moderation 权限
- history visibility
- E2EE group key / MLS epoch
- schema mutation
- Policy Server
- retention / legal hold
- notification rule
- Applet write permission

例如，Alice 是 governance Realm 成员，不代表 Alice 自动能读取 governed Realm。

## 6. 显式继承

若 Realm 需要从另一个 Realm 派生 capability 或 policy，必须使用目标 Realm 内的显式 policy：

- `ck.realm.inheritance_policy`：声明允许从哪个 source Realm 继承哪些收窄型 policy / capability bundle。
- `ck.capability.derived`：reducer-only 派生 grant，必须引用 source grant、目标 Realm 的 inheritance policy 和有效 causal frontier。

继承规则：

1. 目标 Realm 本地 policy 必须 opt-in。
2. derived grant 的 action、resource、constraint、expiry 不得宽于 source grant。
3. 本地 deny / revoke / ban 覆盖 inherited allow。
4. `max_depth` 默认 1，禁止无限级联。
5. source grant revoke 后，derived grant MUST 在 causal 后继中失效。

`ck.capability.derived` MUST NOT 作为普通 actor 可直接 grant 的 action。

## 7. Query

Realm link 查询返回 link graph，不返回产品导航树。产品导航应查询 Space hierarchy。

请求字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `realm_id` | `id:realm` | 起点 Realm。 |
| `link_kind_allow` | `string[]` | 可选 kind 过滤。 |
| `direction` | `outbound \| inbound \| both` | 默认 outbound。 |
| `include_unconfirmed` | `boolean` | 是否包含未确认 link。 |

响应项：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `source_realm_id` | `id:realm` | 源 Realm。 |
| `target_realm_id` | `id:realm` | 目标 Realm。 |
| `link_kind` | `string` | link kind。 |
| `edge_status` | `confirmed \| unconfirmed_link \| rejected \| tombstoned` | 派生状态。 |
| `accessible` | `boolean` | 调用方是否可读取目标 Realm 摘要。 |

## 8. 与 Space Hierarchy 的关系

Space hierarchy 可以跨 Realm 做导航。例如：

```text
Acme (Space, realm_id=R_org)
  Projects (Space, realm_id=R_org)
    Website Redesign (Space, default_realm_id=R_default)
    Pricing Strategy (Space, default_realm_id=R_confidential)
```

这里 `R_default` 与 `R_confidential` 不需要是 parent/linked Realm。若存在关系，也应使用明确 kind，例如：

```text
R_confidential -- confidential_extension_of --> R_default
R_confidential -- governed_by --> R_org
```

这些 link 不改变任何 Realm 的成员、密钥或历史可见性。
