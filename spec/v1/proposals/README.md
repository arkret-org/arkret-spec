---
title: Contrix Proposals (CXP)
status: candidate
normative: false
stability: v1
updated: 2026-05-25
---

# Contrix Proposals

本目录承载 **Contrix v1 协议级提案 (Contrix Proposal, CXP)**。

提案不是 normative 规范。它的作用是把一个增量设计 **完整摆在台面上**(动机、对象形态、wire 影响、与既有 spec 的交互、开放问题),供讨论、迭代、否决或者接受。**只有 status=accepted 的提案才会被分批迁移到 `spec/v1/zh/` + `artifacts/` 的 normative 真源**;在那之前,实现 MUST NOT 把本目录当作 wire contract。

## 1. 目录约定

- 文件名 `NNNN-<kebab-slug>.md`,`NNNN` 为四位数字,从 `0001` 起递增,**永不复用**。模板见 [`.templates/cxp-template.md`](./.templates/cxp-template.md)。
- `deferred-to-v1.1` 状态的提案归档到 [`.deferred/`](./.deferred/) 子目录,保留 frontmatter 不变,v1.1 周期再决定是否捞回顶层目录继续 review。
- 一个提案一个文件;有依赖时通过 frontmatter `depends_on: [CXP-NNNN, ...]` 声明,不要拆成多个相互引用的小文件。
- 配套草案 artifact(schema 草稿、payload 形态举例)直接内嵌 markdown 代码块,**不**写进 `spec/v1/artifacts/`。一旦 accepted,迁移那一步才会真正落 artifact。

## 2. Status 生命周期

```
draft  ──►  review  ──►  accepted  ──►  (迁入 normative spec,本文件保留为历史)
   │           │            │
   ├──►  deferred-to-v1.1
   └──►  withdrawn   └──►  rejected
                            │
                            └──►  superseded(被另一份 CXP 取代)
```

| status | 含义 |
| --- | --- |
| `draft` | 正在写,作者还在改自己的初稿,**不要**基于它讨论细节。 |
| `deferred-to-v1.1` | 不进入 v1.0 freeze;保留讨论材料,v1.1+ 再决定是否 review / accepted。实现 MUST NOT 当作 v1.0 wire contract。 |
| `review` | 作者认为可以讨论了;PR / issue / 会议 review 阶段。 |
| `accepted` | 已被采纳,等待 / 正在迁入 normative。迁入完成后本文件保持原状,frontmatter 加 `merged_into: <spec path>` 留作历史。 |
| `rejected` | 经讨论后决定不做。frontmatter `rejected_reason: ...` 说明原因。**不要删除文件**,以免后人重复提出。 |
| `withdrawn` | 作者主动撤回(还没走到 review 决议),不留 reason 也可以。 |
| `superseded` | 被另一份 CXP 取代;frontmatter `superseded_by: CXP-NNNN`。 |

## 3. Frontmatter 必填字段

```yaml
---
cxp: CXP-NNNN
title: <短句,大写起>
status: draft | review | accepted | rejected | withdrawn | superseded | deferred-to-v1.1
created: YYYY-MM-DD
authors:
  - did:web:alice.example  # 或者 GitHub handle / 邮箱
# 以下按需:
depends_on: [CXP-MMMM]
supersedes: [CXP-MMMM]
superseded_by: CXP-MMMM
merged_into: spec/v1/zh/models/<file>.md
rejected_reason: <一句话>
discussion: <PR / issue 链接>
---
```

## 4. 章节模板

见 [`.templates/cxp-template.md`](./.templates/cxp-template.md)。核心章节:

1. **Summary** — 一两句话能讲清楚是什么。
2. **Motivation** — 为什么现在要做;参考了哪个外部产品的形态(Jira / Trello / Linear / GitHub / ...)。
3. **Specification** — 实质设计:新对象 schema、新 event、新 capability、新 Relation kind。
4. **Interactions with normative spec** — 影响哪些 `spec/v1/zh/` 文件、哪些 artifact、是否破坏现有 wire 约束、是否需要 forbidden-wire 守卫。
5. **Rationale & alternatives** — 为什么不是别的形态。
6. **Open questions** — 留待讨论的具体决策点。
7. **Migration plan**(accepted 提案才必填) — 迁入 normative 时的具体步骤。

## 5. 现有提案索引

| CXP | 标题 | Status | 备注 |
| --- | --- | --- | --- |
| [CXP-0001](./.deferred/0001-label-entity.md) | Label as first-class entity | deferred-to-v1.1 | 把 `labels: array<string>` 升级为 `cx:label:` 对象 + `labeled_with` Relation |
| [CXP-0002](./.deferred/0002-flow-type.md) | Flow Type (Work Item Type) | deferred-to-v1.1 | 引入 `cx:flow_type:`(Task / Sub-task / Bug / Story / ...) |
| [CXP-0003](./.deferred/0003-field-catalog.md) | Field Catalog | deferred-to-v1.1 | 引入 `cx:field_def:` 可复用 typed 字段目录 |
| [CXP-0004](./.deferred/0004-form-layout.md) | Form Layout | deferred-to-v1.1 | 单 Flow 详情面板字段排列(类似 Jira "Work item layout") |
| [CXP-0005](./.deferred/0005-workflow-state-machine.md) | Workflow State Machine | deferred-to-v1.1 | per-Realm workflow profile 状态机,映射到协议级 stage bucket |
| [CXP-0006](./.deferred/0006-component-version.md) | Component & Version classifiers | deferred-to-v1.1 | `cx:component:` / `cx:version:` 结构性分类对象 |
| [CXP-0007](./0007-circle-primitive.md) | Circle — intra-Realm cryptographic sub-boundary primitive | **accepted** (merged 2026-05-25 → [`zh/models/circle.md`](../zh/models/circle.md)) | 引入 `cx:circle:` 作为 Realm 内的密码学子边界(独立 MLS / 子集成员 / 独立 history),**彻底删除** `Flow.discussion_realm_ref`,Flow 永远单一 scope |
| [CXP-0008](./0008-personal-agent-provisioning.md) | 个人 AI Agent 创建与运行时认证 | draft | 用户创建 native AI agent、runtime key pairing、`proof_kind=agent_key_proof` 换短期 session、权限交集与 act-on-behalf 边界 |
| [CXP-0009](./0009-agent-sidecar-thread.md) | Agent Sidecar Thread（Agent 旁路私聊线程） | draft | 在 Flow / Message 上下文中为 controller 与自己的 native AI agent 创建私有 sidecar thread,支持 controller-home / context-Realm home,并定义 E2EE / 存在性隐私边界 |

## 6. 写作风格

- **写实**:对象形态尽量直接给 schema 表格,而不是抽象描述。
- **写薄**:每份提案 80–200 行为宜;真正展开到 normative 时再细化。
- **写明依赖**:依赖另一份 CXP 时显式声明,不要假设读者读过其他提案。
- **不要**在 proposal 阶段就改 `artifacts/`;artifact 改动是 accepted 后的事。
