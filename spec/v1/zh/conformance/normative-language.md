---
title: Normative Language
status: candidate
normative: true
stability: v1
updated: 2026-05-25
see_also:
  - conformance/conformance-suite.md
  - conformance/conformance-profiles.md
---

## 1. 范围

本文集中定义 Cokret v1 规范使用的规范关键字（normative keywords）。其他规范文档 SHOULD 通过一行引用本文，而不再重复关键字解释。

## 2. RFC 2119 / RFC 8174 关键字

本规范中的关键字 **MUST**、**MUST NOT**、**REQUIRED**、**SHALL**、**SHALL NOT**、**SHOULD**、**SHOULD NOT**、**RECOMMENDED**、**NOT RECOMMENDED**、**MAY**、**OPTIONAL** 按 [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) 与 [RFC 8174](https://www.rfc-editor.org/rfc/rfc8174) 解释，并且**仅在全部大写形式下**具有规范约束力。

其他形态（包括小写 "must" / "should" / "may"、首字母大写形式、以及中文 "不得 / 应当 / 建议 / 推荐"）仅供阅读理解，不构成规范要求。

## 3. 否定与禁止

规范级别的禁止 MUST 使用 `MUST NOT`，不得在 normative 段落混用以下中文形态作为同义禁止：

- "不得"、"禁止"、"不允许"、"不可"——只允许出现在 informative 解释段、callout 或注释中。

若编辑性指导本意是 "建议不要"，MUST 使用 `SHOULD NOT` 而不是 "不应"。

## 4. Normative 与 Informative 切分

每个规范文档的章节、表格、示例、图都 SHOULD 显式标记其规范性：

- 默认章节为 normative；如果整节是解释、举例、迁移说明，节首应标 `_Informative._`。
- JSON / YAML 示例统一以 `> _Example (informative)._` 引导，或在代码块前一行写 `*Example (informative).*`。
- Mermaid 图与表格统一以 `*Figure N. <title> (informative).*` 或 `*Table N. <title> (normative).*` 引导。
- 容器型表格（速查 / 决策树 / 字段速览）默认 informative；规范字段表（含 MUST / 必填）须显式标 normative。

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
