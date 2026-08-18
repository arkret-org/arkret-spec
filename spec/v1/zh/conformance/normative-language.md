---
title: Normative Language
status: candidate
normative: true
stability: v1
updated: 2026-07-02
see_also:
  - conformance-suite.md
  - conformance-profiles.md
---

## 1. 范围

本文集中定义 Arkret v1 规范使用的规范关键字（normative keywords）。其他规范文档 SHOULD 通过一行引用本文，而不再重复关键字解释。

## 2. RFC 2119 / RFC 8174 关键字与中文规范词

本规范中的关键字 **MUST**、**MUST NOT**、**REQUIRED**、**SHALL**、**SHALL NOT**、**SHOULD**、**SHOULD NOT**、**RECOMMENDED**、**NOT RECOMMENDED**、**MAY**、**OPTIONAL** 按 [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) 与 [RFC 8174](https://www.rfc-editor.org/rfc/rfc8174) 解释，并且**仅在全部大写形式下**具有规范约束力。

英文小写 "must" / "should" / "may"、首字母大写形式，以及未列入下表的自然语言建议，仅供阅读理解，不构成规范要求。

由于 v1 中文正文是规范真源，以下中文规范词在 normative 段落、normative 表格和字段约束中，**仅当句子向明确的协议主体施加可观察的实现义务、禁止或许可时**，具有与对应 RFC 2119 / RFC 8174 关键字相同的规范力。描述攻击者能力、数学或机制上的可能/不可能、已发生事实、示例能力与安全边界时，这些词仍是普通自然语言，不产生 conformance 义务。新增或重写规范要求时 MUST 同时给出英文大写关键字，以便下游 SDK、conformance suite 与翻译版本机械识别。

任何 conformance coverage 或发布门禁 MUST 以英文大写关键字为机械锚点；中文词只用于帮助读者理解同一句义务，不再单独扩大关键字计数。`tools/lint_spec.py --keyword-stats` 保留为编辑候选盘点入口，其中中文命中数只是待人工分类的 lexical occurrence，MUST NOT 直接解释成 conformance obligation 数量。新增或重写的规范义务没有同句英文大写关键字时，review / lint SHOULD 报告编辑问题；威胁能力或机制局限中的同形中文词不得计为实现许可/禁止。

| 中文规范词 | 等价关键字 | 说明 |
| --- | --- | --- |
| 必须 / 要求 | `MUST` / `REQUIRED` | 绝对要求。 |
| 只能 / 仅限 | `MUST` | 排他性绝对要求：除所述对象外的取值 / 行为均被禁止。 |
| 一律 / 一律不 | `MUST` / `MUST NOT` | 穷尽范围的绝对要求：`一律` 表示对所述范围内**全部**对象无例外地施加该要求（`MUST`）；`一律不` 表示对全部对象无例外地禁止（`MUST NOT`）。与显式 `MUST` / `MUST NOT` 并列出现时表达同一约束、不引入不同范围。 |
| 不得 / 禁止 / 不允许 / 不可 | `MUST NOT` | 绝对禁止。 |
| 不能 | `MUST NOT` | 绝对禁止（对能力 / 许可的否定）。 |
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

**已登记的容器表 normative 例外（双向闭合）**：下列容器型表格虽形如速查 / 索引，但其 caption 显式声明为 normative 权威位置，因而**不**适用上一条"容器表默认 informative"规则，其行内大写规范关键字具规范约束力：

- [`overview/glossary.md` §2](../overview/glossary.md) Table 1（术语表）：caption 声明"本表行内的大写规范关键字具规范约束力，声明'以本条为单一锚点'的条目即为该约束的 canonical 权威位置"。该 caption 已回指本节，本条与之构成双向登记。

新增此类"形如容器表但承载 canonical normative 约束"的表格时，MUST 在表 caption 显式声明 normative 并回指本节，同时在本清单补登一行。

段落级行内标注 `**<标签>（normative）**`（例如 `**字段命名（normative）**：……`）表示对所在段落（含紧随其后的表格）规范力的**强调**：它提示读者该段承载规范要求，但不改变该段在所属章节中的默认规范力，也不把 informative 上下文升级为 normative。该标注仅在 frontmatter `normative: true` 的文档中有效；frontmatter `normative: false` 的文档不得承载 normative 规则，其中出现的此类标注无规范效力——此类文档只能以摘要 + 指针形式引用 normative 文档中的规则。

## 5. 关键字使用例

- 规范要求：`Receiver MUST verify proofs[0] before accepting the event.`
- 规范禁止：`Implementations MUST NOT use HLC to override prev_refs causality.`
- 编辑建议：`Implementations SHOULD log clock skew warnings, but MUST NOT reorder by HLC.`
- 可选能力：`Servers MAY publish event batch receipts.`
- 非规范叙述：`This profile is recommended for personal_node deployments.`（无大写 RECOMMENDED，仅是叙述）

## 6. 与其他规范的关系

本文继承 RFC 2119 与 RFC 8174；引用本规范的下游 SDK、conformance suite 与 conformance profile MUST 沿用同一关键字语义。

## 7. 命名约定：单复数

Schema 字段、event kind 与 map / 集合字段使用复数（`tracks`、`refs`、`proofs`、`schema_refs`、`prev_refs`、`owning_organizations`）；单值 scalar 字段使用单数，并显式标明 value category（例如 `track_name`、`actor_id`、`realm_id`、`schema`）。

- **单 / 复数由 cardinality 决定（normative）**：字段的单数 / 复数形态 MUST 由其 wire cardinality 唯一决定——承载单一引用用单数（`schema`、`seal_ref`、`policy_event_ref`），承载多引用用复数 / 数组形态（`schema_refs`、`prev_refs`、`proofs`）。单数与复数形态**不可互改、不可互换**：`schema` 与 `schema_refs` 是 cardinality 不同的两个字段，MUST NOT 被实现当作同义可替换字段读写。权威命名与 cardinality 判定规则以 [`../models/common-fields.md` §2.1](../models/common-fields.md) 为单一真源。
- 复数 ↔ 单数不互改。当前 candidate v1 的 canonical schema / registry 必须在发布前直接归一到本规则；不得以历史命名为由保留 rename alias、双读字段或迁移例外。
- 新增 wire 字段 MUST 按 cardinality 选用单 / 复数形式；不得使用 `*_list` / `*_array` / `*_set` 后缀替代复数。
- 与之配套的 `*_ref` / `*_refs` / `*_id` / `*_ids` 后缀规则见 [`../models/common-fields.md` §2.1](../models/common-fields.md)。

## 8. 文档 frontmatter 词表

`spec/v1/zh/**/*.md` 的 frontmatter **取值**采用以下封闭词表，lint MUST 拒绝未知值。本节约束的是下列各字段的取值域，不是 frontmatter 的键集合——`title` / `see_also` 等其它键不受本词表限制：

- `status`：`draft` / `candidate` / `stable` / `deprecated`；
- `normative`：YAML boolean `true` / `false`；
- `stability`：current-v1 树中只能是 `v1`，表示协议代际，不表示 core / optional。可选性必须由
  profile 与 protocol-layer / binding registry 表达，不得发明 `v1-extension` 等复合取值。

## 9. References

### Normative References

- [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) — Key words for use in RFCs to Indicate Requirement Levels.
- [RFC 8174](https://www.rfc-editor.org/rfc/rfc8174) — Ambiguity of Uppercase vs Lowercase in RFC 2119 Key Words.
