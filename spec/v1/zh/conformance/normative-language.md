---
title: Normative Language
status: candidate
normative: true
stability: v1
updated: 2026-06-10
see_also:
  - conformance/conformance-suite.md
  - conformance/conformance-profiles.md
---

## 1. 范围

本文集中定义 Cokret v1 规范使用的规范关键字（normative keywords）。其他规范文档 SHOULD 通过一行引用本文，而不再重复关键字解释。

## 2. RFC 2119 / RFC 8174 关键字与中文规范词

本规范中的关键字 **MUST**、**MUST NOT**、**REQUIRED**、**SHALL**、**SHALL NOT**、**SHOULD**、**SHOULD NOT**、**RECOMMENDED**、**NOT RECOMMENDED**、**MAY**、**OPTIONAL** 按 [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) 与 [RFC 8174](https://www.rfc-editor.org/rfc/rfc8174) 解释，并且**仅在全部大写形式下**具有规范约束力。

英文小写 "must" / "should" / "may"、首字母大写形式，以及未列入下表的自然语言建议，仅供阅读理解，不构成规范要求。

由于 v1 中文正文是规范真源，以下中文规范词在 normative 段落、normative 表格和字段约束中具有与对应 RFC 2119 / RFC 8174 关键字相同的规范力。新增或重写规范要求时 SHOULD 优先同时给出英文关键字，以便下游 SDK、cotest 与翻译版本机械识别。

任何 conformance 统计、lint、coverage report 或发布门禁在统计规范关键字时 MUST 按下表把中文规范词归一到对应 RFC 2119 / RFC 8174 bucket；不得只统计英文大写关键字。`tools/lint_spec.py --keyword-stats` 是本仓库的基线统计入口。

| 中文规范词 | 等价关键字 | 说明 |
| --- | --- | --- |
| 必须 / 要求 | `MUST` / `REQUIRED` | 绝对要求。 |
| 不得 / 禁止 / 不允许 / 不可 | `MUST NOT` | 绝对禁止。 |
| 应当 / 建议 / 推荐 | `SHOULD` / `RECOMMENDED` | 有强理由时可偏离，但实现需能解释。 |
| 不应 / 不建议 / 不推荐 | `SHOULD NOT` / `NOT RECOMMENDED` | 有强理由时可偏离。 |
| 可以 / 可选 | `MAY` / `OPTIONAL` | 可选能力或许可。 |

## 3. 否定与禁止

规范级别的英文禁止 MUST 使用 `MUST NOT`。中文 normative 正文可使用 §2 表中的“不得 / 禁止 / 不允许 / 不可”，其规范力等同 `MUST NOT`；同一句中若同时出现中文禁止和 `MUST NOT`，两者表达同一约束，不得引入不同范围。

若编辑性指导本意是 "建议不要"，SHOULD 使用 `SHOULD NOT` 或 §2 表中的“不应 / 不建议 / 不推荐”，并避免和 `MUST NOT` 混用。

## 4. Normative 与 Informative 切分

每个规范文档的章节、表格、示例、图都 SHOULD 显式标记其规范性：

- 默认章节为 normative；如果整节是解释、举例、迁移说明，节首应标 `_Informative._`。
- JSON / YAML 示例统一以 `> _Example (informative)._` 引导，或在代码块前一行写 `*Example (informative).*`。
- Mermaid 图与表格统一以 `*Figure N. <title> (informative).*` 或 `*Table N. <title> (normative).*` 引导。
- 在 normative 章节内，字段表、schema 表、error code 表、operation 表和状态机表默认具有规范力；只有明确标为 quick reference、导航、示例、对照或 informative 的表格才是说明性内容。
- 容器型表格（速查 / 决策树 / 字段速览）默认 informative；规范字段表（含 MUST / 必填）建议显式标 normative，但缺少显式标记不降低上一条所述规范力。

## 5. 关键字使用例

- 规范要求：`Receiver MUST verify proofs[0] before accepting the event.`
- 规范禁止：`Implementations MUST NOT use HLC to override prev_refs causality.`
- 编辑建议：`Implementations SHOULD log clock skew warnings, but MUST NOT reorder by HLC.`
- 可选能力：`Servers MAY publish event batch receipts.`
- 非规范叙述：`This profile is recommended for personal_node deployments.`（无大写 RECOMMENDED，仅是叙述）

## 6. 与其他规范的关系

本文继承 RFC 2119 与 RFC 8174；引用本规范的下游 SDK、cotest 套件与 conformance profile MUST 沿用同一关键字语义。

## 7. 命名约定：单复数

Schema 字段、event kind 与 map / 集合字段使用复数（`tracks`、`refs`、`proofs`、`schema_refs`、`prev_refs`、`owning_organizations`）；单值 scalar 字段使用单数，并显式标明 value category（例如 `track_name`、`actor_id`、`realm_id`、`schema`）。

- 复数 ↔ 单数不互改；现有字段保留既定形态（即使个别历史命名看起来与本规则不完全对齐，也不在 v1 内改名）。
- 新增 wire 字段 MUST 按 cardinality 选用单 / 复数形式；不得使用 `*_list` / `*_array` / `*_set` 后缀替代复数。
- 与之配套的 `*_ref` / `*_refs` / `*_id` / `*_ids` 后缀规则见 [`../models/common-fields.md` §2.1](../models/common-fields.md)。

## 8. References

### Normative References

- [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) — Key words for use in RFCs to Indicate Requirement Levels.
- [RFC 8174](https://www.rfc-editor.org/rfc/rfc8174) — Ambiguity of Uppercase vs Lowercase in RFC 2119 Key Words.
