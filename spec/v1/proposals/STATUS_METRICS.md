---
title: CXP Status Metrics
status: candidate
normative: false
stability: v1
updated: 2026-05-28
---

## 1. 目标

本文聚合 `spec/v1/proposals/` 目录所有 CXP 的当前 status 与状态转移历史,方便维护者一眼看到提案池的健康度,并为 `tools/lint_spec.py` 的 "review-without-discussion" 警告提供权威输入。

CXP 状态生命周期定义见 [`README.md` §2](./README.md);本文不重新定义语义,只汇总当前值与转移轨迹。

## 2. 当前 status 概览

| CXP | 标题 | Status | created | last status change | discussion |
| --- | --- | --- | --- | --- | --- |
| [CXP-0001](./.deferred/0001-label-entity.md) | Label as first-class entity | `deferred-to-v1.1` | 2026-04 | 2026-05-10 → deferred-to-v1.1 | — |
| [CXP-0002](./.deferred/0002-flow-type.md) | Flow Type (Work Item Type) | `deferred-to-v1.1` | 2026-04 | 2026-05-10 → deferred-to-v1.1 | — |
| [CXP-0003](./.deferred/0003-field-catalog.md) | Field Catalog | `deferred-to-v1.1` | 2026-04 | 2026-05-10 → deferred-to-v1.1 | — |
| [CXP-0004](./.deferred/0004-form-layout.md) | Form Layout | `deferred-to-v1.1` | 2026-04 | 2026-05-10 → deferred-to-v1.1 | — |
| [CXP-0005](./.deferred/0005-workflow-state-machine.md) | Workflow State Machine | `deferred-to-v1.1` | 2026-04 | 2026-05-10 → deferred-to-v1.1 | — |
| [CXP-0006](./.deferred/0006-component-version.md) | Component & Version classifiers | `deferred-to-v1.1` | 2026-04 | 2026-05-10 → deferred-to-v1.1 | — |
| [CXP-0007](./0007-circle-primitive.md) | Circle — intra-Realm cryptographic sub-boundary primitive | `accepted` | 2026-05-25 | 2026-05-25 → accepted (merged 2026-05-25 → `zh/models/circle.md`) | — |
| [CXP-0008](./0008-personal-agent-provisioning.md) | 个人 AI Agent 创建与运行时认证 | `accepted` | 2026-05-26 | 2026-05-26 → accepted (merged → `zh/identity/key-management.md` 等) | internal（无公开 URL） |
| [CXP-0009](./0009-agent-sidecar-thread.md) | Agent Sidecar Thread（Agent 旁路私聊线程） | `accepted` | 2026-05-26 | 2026-05-26 → accepted (merged → `zh/models/circle.md` 等) | internal（无公开 URL） |
| [CXP-0010](./0010-media-service-binding-framework.md) | Media Service Binding Framework（媒体服务 Backend 绑定框架） | `accepted` | 2026-05-27 | 2026-05-27 → accepted (merged → `zh/crypto-media/webrtc-signaling.md` 与 `bindings/`) | `<pending>` |
| [CXP-0011](./0011-shareable-object-addressing.md) | Shareable Object Addressing — web+contrix URI scheme & deep-link resolution | `accepted` | 2026-05-28 | 2026-05-28 → accepted (merged → `zh/discovery/object-addressing.md`) | — |

## 3. 状态转移汇总

```
draft  ──►  review  ──►  accepted  ──►  (迁入 normative spec; frontmatter merged_into=<path>)
   │           │            │
   ├──►  deferred-to-v1.1
   └──►  withdrawn   └──►  rejected
                            │
                            └──►  superseded(被另一份 CXP 取代)
```

当前转移历史:

- `0001`–`0006`: `draft` → `deferred-to-v1.1` (2026-05-10 freeze decision: v1.0 不接受新顶层对象)
- `0007`: `draft` → `review` → `accepted` (2026-05-25 merged into `zh/models/circle.md`)
- `0008`: `draft` → `accepted` (2026-05-26 merged into identity / agent runtime normative files)
- `0009`: `draft` → `accepted` (2026-05-26 merged into sidecar thread normative files; accepted in lockstep with CXP-0008)
- `0010`: `draft` → `accepted` (2026-05-27 merged into `zh/crypto-media/webrtc-signaling.md` 与 `zh/crypto-media/bindings/`)
- `0011`: `draft` → `accepted` (2026-05-28 created and merged into `zh/discovery/object-addressing.md`; 客户端无关可分享对象地址 + `web+contrix:` scheme + `resolve_target`)

## 4. 状态健康度指标

| 指标 | 当前值 | 阈值 / 备注 |
| --- | --- | --- |
| `total_proposals` | 11 | — |
| `active_count` (`draft` + `review`) | 0 | — |
| `accepted_count` | 5 | CXP-0007 (Circle), CXP-0008 (Personal Agent), CXP-0009 (Agent Sidecar Thread), CXP-0010 (Media Service Binding Framework), CXP-0011 (Shareable Object Addressing) |
| `deferred_to_v11_count` | 6 | 0001–0006 |
| `rejected_count` | 0 | — |
| `withdrawn_count` | 0 | — |
| `superseded_count` | 0 | — |
| `review_without_discussion_count` | 0 | `review` 状态的提案 MUST 在 frontmatter 中有 `discussion:` 链接;`tools/lint_spec.py` 在 v1.0 后增加该警告 |
| `stale_review_count` | 0 | `review` 状态超过 30 天未推进的提案数(运营提醒) |

## 5. Lint 集成

`tools/lint_spec.py` 在扫描 `spec/v1/proposals/*.md` 时 SHOULD:

1. 解析 frontmatter `cxp` / `status` / `discussion`。
2. 当 `status == "review"` 且 `discussion` 缺失时,emit warning code `CXP001` (`review status MUST carry a discussion: frontmatter link`)。
3. 当 `status == "accepted"` 但缺 `merged_into:` 时,emit warning code `CXP002` (`accepted proposal MUST declare merged_into: target path`)。
4. 当 `cxp:` 编号与文件名不一致时,emit error code `CXP003`。

以上规则与本表配合,作为 v1.0 release-readiness gate 的一部分。

## 6. 维护节奏

- 每次合并新 CXP 或推进既有 CXP 状态时,**必须**同步更新本表与 §4 计数。
- 进入 `accepted` 的提案合并后,本表保留历史条目;`merged_into` 列指向 normative spec 路径。
- 当本表与 README §5 索引不一致时,以本表为 status canonical source;README §5 仅作目录入口。

## 7. 规范性引用

- 状态语义: [`proposals/README.md` §2](./README.md)。
- Frontmatter 字段: [`proposals/README.md` §3](./README.md)。
- Lint 工具: `tools/lint_spec.py`(后续补 `CXP001` / `CXP002` / `CXP003` 实现)。
