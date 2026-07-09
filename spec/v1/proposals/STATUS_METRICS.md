---
title: AKP Status Metrics
status: candidate
normative: false
stability: v1
updated: 2026-06-16
---

## 1. 目标

本文聚合 `spec/v1/proposals/` 目录所有 AKP 的当前 status 与状态转移历史,方便维护者一眼看到提案池的健康度,并为 `tools/lint_spec.py` 的 "review-without-discussion" 警告提供权威输入。

AKP 状态生命周期定义见 [`README.md` §2](./README.md);本文不重新定义语义,只汇总当前值与转移轨迹。

## 2. 当前 status 概览

| AKP | 标题 | Status | created | last status change | discussion |
| --- | --- | --- | --- | --- | --- |
| [AKP-0001](./.deferred/0001-label-entity.md) | Label as first-class entity | `deferred-to-v1.1` | 2026-04 | 2026-05-10 → deferred-to-v1.1 | — |
| [AKP-0002](./.deferred/0002-strand-type.md) | Strand Type (Work Item Type) | `deferred-to-v1.1` | 2026-04 | 2026-05-10 → deferred-to-v1.1 | — |
| [AKP-0003](./.deferred/0003-field-catalog.md) | Field Catalog | `deferred-to-v1.1` | 2026-04 | 2026-05-10 → deferred-to-v1.1 | — |
| [AKP-0004](./.deferred/0004-form-layout.md) | Form Layout | `deferred-to-v1.1` | 2026-04 | 2026-05-10 → deferred-to-v1.1 | — |
| [AKP-0005](./.deferred/0005-workflow-state-machine.md) | Workflow State Machine | `deferred-to-v1.1` | 2026-04 | 2026-05-10 → deferred-to-v1.1 | — |
| [AKP-0006](./.deferred/0006-component-version.md) | Component & Version classifiers | `deferred-to-v1.1` | 2026-04 | 2026-05-10 → deferred-to-v1.1 | — |
| [AKP-0007](./0007-circle-primitive.md) | Circle — intra-Realm cryptographic sub-boundary primitive | `accepted` | 2026-05-25 | 2026-05-25 → accepted (merged 2026-05-25 → `zh/models/circle.md`) | — |
| [AKP-0008](./0008-personal-agent-provisioning.md) | 个人 AI Agent 创建与运行时认证 | `accepted` | 2026-05-26 | 2026-05-26 → accepted (merged → `zh/identity/key-management.md` 等) | internal（无公开 URL） |
| [AKP-0009](./0009-agent-sidecar-thread.md) | Agent Sidecar Thread（Agent 旁路私聊线程） | `accepted` | 2026-05-26 | 2026-05-26 → accepted (merged → `zh/models/circle.md` 等) | internal（无公开 URL） |
| [AKP-0010](./0010-media-service-binding-framework.md) | Media Service Binding Framework（媒体服务 Backend 绑定框架） | `accepted` | 2026-05-27 | 2026-05-27 → accepted (merged → `zh/crypto-media/media-service-binding.md`、`call-state.md` 与 `bindings/`) | `<pending>` |
| [AKP-0011](./0011-shareable-object-addressing.md) | Shareable Object Addressing — web+arkret URI scheme & deep-link resolution | `accepted` | 2026-05-28 | 2026-05-28 → accepted (merged → `zh/discovery/object-addressing.md`) | — |
| [AKP-0012](./0012-account-and-contact-self-operations.md) | Account Self-Service Operations | `accepted` | 2026-06-04 | 2026-06-04 → accepted (merged → `zh/sync/` + `artifacts/`) | — |
| [AKP-0013](./0013-contact-and-direct-conversation-lifecycle.md) | Contact & Direct Conversation Lifecycle | `accepted` | 2026-06-04 | 2026-06-04 → accepted (merged → `zh/identity/contact-and-direct-conversation.md` + `artifacts/`) | — |
| [AKP-0014](./0014-implementation-local-http-surfaces.md) | Implementation-local HTTP surfaces found in coauth / inkson audit | `accepted` | 2026-06-06 | 2026-06-16 → accepted (merged → auth/account authority normative files) | internal（无公开 URL） |
| [AKP-0015](./0015-contact-introduction-and-graded-disclosure.md) | Contact introduction evidence & graded invite-outcome disclosure | `draft` | 2026-06-08 | 2026-06-08 → draft | — |
| [AKP-0016](./0016-agent-participation-policy.md) | Agent 参与策略与分层授权上限 | `accepted` | 2026-06-09 | 2026-06-09 → accepted (merged → `zh/models/realm-and-space.md` + `zh/authz/capabilities.md` + `artifacts/`) | internal（无公开 URL） |
| [AKP-0017](./0017-controller-scoped-agent-mention-selector.md) | Controller-scoped Agent Mention Selector | `accepted` | 2026-06-11 | 2026-06-11 → accepted (merged → `zh/models/strand-and-message.md` + `zh/models/actor.md` + `artifacts/schemas/agent-selector-claim.schema.json`) | internal（无公开 URL） |

## 3. 状态转移汇总

```
draft  ──►  review  ──►  accepted  ──►  (迁入 normative spec; frontmatter merged_into=<path> 或 merged_to=[...])
   │           │            │
   ├──►  deferred-to-v1.1
   └──►  withdrawn   └──►  rejected
                            │
                            └──►  superseded(被另一份 AKP 取代)
```

当前转移历史:

- `0001`–`0006`: `draft` → `deferred-to-v1.1` (2026-05-10 freeze decision: v1.0 不接受新顶层对象)
- `0007`: `draft` → `review` → `accepted` (2026-05-25 merged into `zh/models/circle.md`)
- `0008`: `draft` → `accepted` (2026-05-26 merged into identity / agent runtime normative files)
- `0009`: `draft` → `accepted` (2026-05-26 merged into sidecar thread normative files; accepted in lockstep with AKP-0008)
- `0010`: `draft` → `accepted` (2026-05-27 merged into `zh/crypto-media/media-service-binding.md`、`zh/crypto-media/call-state.md` 与 `zh/crypto-media/bindings/`)
- `0011`: `draft` → `accepted` (2026-05-28 created and merged into `zh/discovery/object-addressing.md`; 客户端无关可分享对象地址 + `web+arkret:` scheme + `resolve_target`)
- `0012`: `draft` → `accepted` (2026-06-04 merged into `zh/sync/` + `artifacts/`; account self-service 四项 — viewer/update_profile/register/session_revoke)
- `0013`: `draft` → `accepted` (2026-06-04 merged into `zh/identity/contact-and-direct-conversation.md` + `artifacts/`; contact 关系生命周期 + DM 编排)
- `0014`: `draft` → `accepted` (2026-06-16 merged into Account Authority / auth metadata / hard logout normative files)
- `0015`: `draft` (2026-06-08 contact introduction and graded disclosure; not merged)
- `0016`: `draft` → `accepted` (2026-06-09 merged into agent participation policy zh/spec artifacts)
- `0017`: `draft` → `accepted` (2026-06-11 merged into controller-scoped agent selector claim, exact Directory resolver, mention selector zh/spec artifacts, and anti-enumeration disclosure gate)

## 4. 状态健康度指标

| 指标 | 当前值 | 阈值 / 备注 |
| --- | --- | --- |
| `total_proposals` | 17 | — |
| `active_count` (`draft` + `review`) | 1 | AKP-0015 |
| `accepted_count` | 10 | AKP-0007 (Circle), AKP-0008 (Personal Agent), AKP-0009 (Agent Sidecar Thread), AKP-0010 (Media Service Binding Framework), AKP-0011 (Shareable Object Addressing), AKP-0012 (Account Self-Service), AKP-0013 (Contact & Direct Conversation), AKP-0014 (Implementation-local HTTP Surfaces), AKP-0016 (Agent Participation Policy), AKP-0017 (Agent Mention Selector) |
| `deferred_to_v11_count` | 6 | 0001–0006 |
| `rejected_count` | 0 | — |
| `withdrawn_count` | 0 | — |
| `superseded_count` | 0 | — |
| `review_without_discussion_count` | 0 | `review` 状态的提案 MUST 在 frontmatter 中有 `discussion:` 链接;`tools/lint_spec.py` 在 v1.0 后增加该警告 |
| `stale_review_count` | 0 | `review` 状态超过 30 天未推进的提案数(运营提醒) |

## 5. Lint 集成

`tools/lint_spec.py` 在扫描 `spec/v1/proposals/*.md` 时 SHOULD:

1. 解析 frontmatter `akp` / `status` / `discussion`。
2. 当 `status == "review"` 且 `discussion` 缺失时,emit warning code `AKP001` (`review status MUST carry a discussion: frontmatter link`)。
3. 当 `status == "accepted"` 但缺 `merged_into:` / `merged_to:` 时,emit warning code `AKP002` (`accepted proposal MUST declare merged_into: target path or merged_to: target paths`)。
4. 当 `akp:` 编号与文件名不一致时,emit error code `AKP003`。

以上规则与本表配合,作为 v1.0 release-readiness gate 的一部分。

## 6. 维护节奏

- 每次合并新 AKP 或推进既有 AKP 状态时,**必须**同步更新本表与 §4 计数。
- 进入 `accepted` 的提案合并后,本表保留历史条目;单目标落地使用 `merged_into`，多目标落地使用 `merged_to` 列出 normative spec 路径。
- 当本表与 README §5 索引不一致时,以本表为 status canonical source;README §5 仅作目录入口。

## 7. 规范性引用

- 状态语义: [`proposals/README.md` §2](./README.md)。
- Frontmatter 字段: [`proposals/README.md` §3](./README.md)。
- Lint 工具: `tools/lint_spec.py`(后续补 `AKP001` / `AKP002` / `AKP003` 实现)。
