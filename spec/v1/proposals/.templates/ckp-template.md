---
ckp: CKP-0000
title: Proposal Template (Do Not Edit)
normative: false
stability: v1
updated: 2026-05-25
status: draft
created: 2026-05-23
authors:
  - did:webvh:z8kSru9qAfd1G7AvcVjggdEKy:cokret.example
---

> **本文件是模板,不要直接修改**。新提案 `cp .templates/ckp-template.md NNNN-<slug>.md` 之后填写(`NNNN-<slug>.md` 放在 `spec/v1/proposals/` 顶层)。

## 1. Summary

一两句话:这份提案要引入什么、解决什么。读者读完这一段应该立即判断"我感不感兴趣"。

## 2. Motivation

- 现状是什么?协议目前怎么表达这个概念(或者根本没有)?
- 引用具体外部产品形态(Jira / Trello / Linear / GitHub / Notion / ...)的截图或链接,说明用户期待。
- 为什么 `spec/v1/zh/` 现有机制不足以表达?

## 3. Specification

### 3.1 新对象 / 新字段

如果引入新对象,直接给 schema 表(同 `models/*.md` 风格):

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:<kind>` | ... | ... |

### 3.2 新 event / capability

| event kind | reducer_input | 说明 |
| --- | --- | --- |
| `ck.<kind>.<verb>` | yes/no | ... |

### 3.3 wire 形态示例

```json
{
  "kind": "ck.<kind>.<verb>",
  "payload": { "...": "..." }
}
```

## 4. Interactions with normative spec

- 改动哪些 `spec/v1/zh/` 文件?
- 改动哪些 `spec/v1/artifacts/` 文件?
- 是否需要新 forbidden-wire 守卫?
- 与现有对象 / event 是否冲突?如何收敛(双源?派生?)
- 是否需要 schema migration / profile opt-in?

## 5. Rationale & alternatives

- 为什么这个形态优于其它候选?
- 列出至少 2 个备选并说明否决理由。
- 性能 / 隐私 / 可演进性的权衡。

## 6. Open questions

- [ ] 待定的具体决策点 1
- [ ] 待定的具体决策点 2

## 7. Migration plan

> **accepted 状态才需要填**。draft / review 阶段可以保持 placeholder。

1. ...
2. ...
3. 迁入 normative spec 的 PR 列表与顺序。

## 8. References

- 外部产品截图 / 文档链接
- 相关 CKP(supersedes / depends_on)
- 相关 issue / PR
