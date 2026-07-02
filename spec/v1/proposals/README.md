---
title: Cokret Proposals (CKP)
status: candidate
normative: false
stability: v1
updated: 2026-05-28
---

# Cokret Proposals

本目录承载 **Cokret v1 协议级提案 (Cokret Proposal, CKP)**。

提案不是 normative 规范。它的作用是把一个增量设计 **完整摆在台面上**(动机、对象形态、wire 影响、与既有 spec 的交互、开放问题),供讨论、迭代、否决或者接受。**只有 status=accepted 的提案才会被分批迁移到 `spec/v1/zh/` + `artifacts/` 的 normative 真源**;在那之前,实现 MUST NOT 把本目录当作 wire contract。

## 1. 目录约定

- 文件名 `NNNN-<kebab-slug>.md`,`NNNN` 为四位数字,从 `0001` 起递增,**永不复用**。模板见 [`.templates/ckp-template.md`](./.templates/ckp-template.md)。
- `deferred-to-v1.1` 状态的提案归档到 [`.deferred/`](./.deferred/) 子目录,保留 frontmatter 不变,v1.1 周期再决定是否捞回顶层目录继续 review。
- 一个提案一个文件;有依赖时通过 frontmatter `depends_on: [CKP-NNNN, ...]` 声明,不要拆成多个相互引用的小文件。
- 配套草案 artifact(schema 草稿、payload 形态举例)直接内嵌 markdown 代码块,**不**写进 `spec/v1/artifacts/`。一旦 accepted,迁移那一步才会真正落 artifact。

## 2. Status 生命周期

```
draft  ──►  review  ──►  accepted  ──►  (迁入 normative spec,本文件保留为历史)
   │           │            │
   ├──►  deferred-to-v1.1
   └──►  withdrawn   └──►  rejected
                            │
                            └──►  superseded(被另一份 CKP 取代)
```

| status | 含义 |
| --- | --- |
| `draft` | 正在写,作者还在改自己的初稿,**不要**基于它讨论细节。 |
| `deferred-to-v1.1` | 不进入 v1.0 freeze;保留讨论材料,v1.1+ 再决定是否 review / accepted。实现 MUST NOT 当作 v1.0 wire contract。 |
| `review` | 作者认为可以讨论了;PR / issue / 会议 review 阶段。 |
| `accepted` | 已被采纳,等待 / 正在迁入 normative。迁入完成后本文件保持原状,frontmatter 加 `merged_into: <spec path>`；若一次 CKP 落地到多个文件，使用 `merged_to: [<spec path>, ...]` 留作历史。 |
| `rejected` | 经讨论后决定不做。frontmatter `rejected_reason: ...` 说明原因。**不要删除文件**,以免后人重复提出。 |
| `withdrawn` | 作者主动撤回(还没走到 review 决议),不留 reason 也可以。 |
| `superseded` | 被另一份 CKP 取代;frontmatter `superseded_by: CKP-NNNN`。 |

## 3. Frontmatter 必填字段

```yaml
---
ckp: CKP-NNNN
title: <短句,大写起>
status: draft | review | accepted | rejected | withdrawn | superseded | deferred-to-v1.1
created: YYYY-MM-DD
authors:
  - did:webvh:z2dmjZ8r7L4nP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z:alice.example  # 或者 GitHub handle / 邮箱
# 以下按需:
depends_on: [CKP-MMMM]
supersedes: [CKP-MMMM]
superseded_by: CKP-MMMM
merged_into: spec/v1/zh/models/<file>.md  # 或 merged_to: [spec/v1/zh/models/<file>.md, ...]
rejected_reason: <一句话>
discussion: <PR / issue 链接>
---
```

## 4. 章节模板

见 [`.templates/ckp-template.md`](./.templates/ckp-template.md)。核心章节:

1. **Summary** — 一两句话能讲清楚是什么。
2. **Motivation** — 为什么现在要做;参考了哪个外部产品的形态(Jira / Trello / Linear / GitHub / ...)。
3. **Specification** — 实质设计:新对象 schema、新 event、新 capability、新 Relation kind。
4. **Interactions with normative spec** — 影响哪些 `spec/v1/zh/` 文件、哪些 artifact、是否破坏现有 wire 约束、是否需要 forbidden-wire 守卫。
5. **Rationale & alternatives** — 为什么不是别的形态。
6. **Open questions** — 留待讨论的具体决策点。
7. **Migration plan**(accepted 提案才必填) — 迁入 normative 时的具体步骤。

## 5. 现有提案索引

| CKP | 标题 | Status | 备注 |
| --- | --- | --- | --- |
| [CKP-0001](./.deferred/0001-label-entity.md) | Label as first-class entity | deferred-to-v1.1 | 把 `labels: array<string>` 升级为 `ck:label:` 对象 + `labeled_with` Relation |
| [CKP-0002](./.deferred/0002-strand-type.md) | Strand Type (Work Item Type) | deferred-to-v1.1 | 引入 `ck:strand_type:`(Task / Sub-task / Bug / Story / ...) |
| [CKP-0003](./.deferred/0003-field-catalog.md) | Field Catalog | deferred-to-v1.1 | 引入 `ck:field_def:` 可复用 typed 字段目录 |
| [CKP-0004](./.deferred/0004-form-layout.md) | Form Layout | deferred-to-v1.1 | 单 Strand 详情面板字段排列(类似 Jira "Work item layout") |
| [CKP-0005](./.deferred/0005-workflow-state-machine.md) | Workflow State Machine | deferred-to-v1.1 | per-Realm workflow profile 状态机,映射到协议级 stage bucket |
| [CKP-0006](./.deferred/0006-component-version.md) | Component & Version classifiers | deferred-to-v1.1 | `ck:component:` / `ck:version:` 结构性分类对象 |
| [CKP-0007](./0007-circle-primitive.md) | Circle — intra-Realm cryptographic sub-boundary primitive | **accepted** (merged 2026-05-25 → [`zh/models/circle.md`](../zh/models/circle.md)) | 引入 `ck:circle:` 作为 Realm 内的密码学子边界(独立 MLS / 子集成员 / 独立 history),**彻底删除** `Strand.discussion_realm_ref`,Strand 永远单一 scope |
| [CKP-0008](./0008-personal-agent-provisioning.md) | 个人 AI Agent 创建与运行时认证 | **accepted** (merged 2026-05-26 → identity / agent runtime normative files) | 用户创建 native AI agent、runtime key pairing、`proof_kind=agent_key_proof` 换短期 session、权限交集与 act-on-behalf 边界 |
| [CKP-0009](./0009-agent-sidecar-thread.md) | Agent Sidecar Thread（Agent 旁路私聊线程） | **accepted** (merged 2026-05-26 → sidecar thread normative files) | 在 Strand / Message 上下文中为 controller 与自己的 native AI agent 创建私有 sidecar thread,支持 controller-home / context-Realm home,并定义 E2EE / 存在性隐私边界 |
| [CKP-0010](./0010-media-service-binding-framework.md) | Media Service Binding Framework（媒体服务 Backend 绑定框架） | **accepted** (merged 2026-05-27 → [`zh/crypto-media/media-service-binding.md`](../zh/crypto-media/media-service-binding.md)、`call-state.md` 及 `bindings/`) | 把 `ck.realm.media_service` 从单 SFU endpoint 升级为 multi-focus + transport-agnostic backend 抽象;定义统一 token exchange、session focus 持久化、participant binding、E2EE key injection 契约、recording artifact 流转;LiveKit / mediasoup / Janus / MoQ 通过附录绑定接入 |
| [CKP-0011](./0011-shareable-object-addressing.md) | Shareable Object Addressing — web+cokret URI scheme & deep-link resolution | **accepted** (merged 2026-05-28 → [`zh/discovery/object-addressing.md`](../zh/discovery/object-addressing.md)) | 客户端无关的可分享对象地址:`web+cokret:` URI scheme + HTTPS 落地(matrix.to 模型),path 表 containment / query 表路由提示,`reference`/`invite` 两型 link(`preview` 保留),寻址 ≠ 授权,token 绑定 canonical target,新增 `ck.find.directory.query.resolve_target` |
| [CKP-0012](./0012-account-and-contact-self-operations.md) | Account Self-Service Operations | **accepted** (merged 2026-06-04 → `zh/sync/` + `artifacts/`) | 补齐 catalog 缺失的 account 自服务 operation:`ck.self.account.viewer`(自读)/`update_profile`/`register`(落 gate)/`session_revoke`(logout,落 gate 与签发端对称),解 yougen 对 `_soland/self/account/*` 硬编码;联系人部分已分拆 CKP-0013 |
| [CKP-0013](./0013-contact-and-direct-conversation-lifecycle.md) | Contact & Direct Conversation Lifecycle | **accepted** (merged 2026-06-04 → `zh/identity/contact-and-direct-conversation.md` + `artifacts/`) | 把"加联系人 → 找他聊天"端到端拆清为 contact fact log(关系真源)、consent gate(action 授权)、direct conversation binding(DM 入口)与 Strand discussion(消息载体);明确 contact 不能由 consent/DM Realm 反推 |
| [CKP-0014](./0014-implementation-local-http-surfaces.md) | Implementation-local HTTP surfaces found in coauth / yougen audit | **accepted** (merged 2026-06-16 → auth/account authority normative files) | 选择 Account Authority + `auth_metadata.methods[]` + 标准 OIDC discovery；不把私有 bridge endpoints 标准化 |
| [CKP-0015](./0015-contact-introduction-and-graded-disclosure.md) | Contact introduction evidence & graded invite-outcome disclosure | draft | 联系人介绍证据与邀请结果分级披露 |
| [CKP-0016](./0016-agent-participation-policy.md) | Agent 参与策略与分层授权上限 | **accepted** (merged 2026-06-09 → agent participation normative files) | 定义 native personal agent 的 `reply` / `accept_third_party_mention` / `act_on_behalf` 三位策略、分层 ceiling、controller selection 与第三方 mention gate |
| [CKP-0017](./0017-controller-scoped-agent-mention-selector.md) | Controller-scoped Agent Mention Selector | **accepted** (merged 2026-06-11 → agent mention selector normative files) | 定义 `@<controller-handle>/<agent_slug>` 输入别名、`ck.schema.agent_selector_claim.v1` 权威绑定、`agent_slug` Actor Profile 投影 hint、`ck.find.directory.resolve_agent_selector` 精确解析披露门和 mention 节点 audit metadata；持久化权威仍是 agent DID |

## 6. 写作风格

- **写实**:对象形态尽量直接给 schema 表格,而不是抽象描述。
- **写薄**:每份提案 80–200 行为宜;真正展开到 normative 时再细化。
- **写明依赖**:依赖另一份 CKP 时显式声明,不要假设读者读过其他提案。
- **不要**在 proposal 阶段就改 `artifacts/`;artifact 改动是 accepted 后的事。
