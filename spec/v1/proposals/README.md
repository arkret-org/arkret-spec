---
title: Arkret Proposals (AKP)
status: candidate
normative: false
stability: v1
updated: 2026-07-10
---

# Arkret Proposals

本目录只承载尚未合并到 normative v1 的 **Arkret Proposal（AKP）** 工作稿。proposal 不是 wire contract；实现 MUST NOT 从本目录生成 schema、registry、SDK 类型或运行时行为。

## 1. 文件与标识

- 文件名为 `NNNN-<kebab-slug>.md`，`NNNN` 是四位数字。
- frontmatter 标识固定为 `akp: AKP-NNNN`，且数字必须与文件名逐字一致。
- 新提案从 [`.templates/akp-template.md`](./.templates/akp-template.md) 复制。
- 一个提案一个文件；依赖使用 `depends_on: [AKP-NNNN]`。
- 草案 schema、payload 和算法示例留在 Markdown 代码块中；合并前不得写入 `artifacts/`。

## 2. 生命周期

current-v1 proposal 只有两种仓内状态：

| Status | 含义 |
| --- | --- |
| `draft` | 作者仍在整理，不能作为实现输入。 |
| `review` | 可供协议审查，仍不是 normative contract。 |

接受 proposal 时，必须在同一变更中把完整规则、schema、registry、fixture、profile 和 vector 合并到各自 canonical v1 真源，并删除 proposal 文件。否决、撤回、延期或被取代的工作稿同样从 current-v1 树删除；设计沿革只保留在 Git 历史，不维护兼容副本、merge manifest 或未来版本目录。

## 3. Frontmatter

```yaml
---
akp: AKP-NNNN
title: <短句>
status: draft | review
normative: false
stability: v1
updated: YYYY-MM-DD
authors:
  - <DID、handle 或邮箱>
depends_on: [AKP-MMMM]  # 可选
discussion: <issue-or-pr-url>  # review 必填
---
```

## 4. 当前提案

| AKP | 标题 | Status |
| --- | --- | --- |
| [AKP-0015](./0015-contact-introduction-and-graded-disclosure.md) | Contact introduction evidence & graded invite-outcome disclosure | draft |

目录索引必须与实际文件集合一致。已合并、延期、否决或撤回的 AKP 不得留在本表或 current-v1 目录。
