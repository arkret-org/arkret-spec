---
title: Pinned Messages and Objects
status: candidate
normative: true
stability: v1
updated: 2026-06-10
see_also:
  - flow-and-message.md
  - realm-and-space.md
  - views.md
  - personal-productivity.md
  - ../../artifacts/schemas/pin.schema.json
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具有规范约束力。

## 1. 范围

Shared pin 是进入 Realm reducer 的共享投影事实，用于把 Message、Flow、Morph、Relation 或其它可引用对象固定在某个共享范围中。个人保存 / 收藏不使用 shared pin；它们由 [personal-productivity.md](./personal-productivity.md) 的 account data 表达。

实现声明 `ck.profile.pinned_items.v1` 时，MUST 支持 `ck.pin.add`、`ck.pin.remove` 和 `ck.pin.reorder`。

## 2. Pin Scope

Pin payload 使用 `pin_scope`，MUST NOT 使用裸 `scope` 或旧的 scope-reference 字段。`pin_scope` 的形态为 `{ kind, id }`，`kind` 取 `flow`、`realm`、`circle` 或 `space`。

`pin_scope` 是 projection home，不是安全边界。`kind=space` 时，reducer MUST 解析 Space metadata 的 effective scope；Space 不因此获得独立 membership、policy、history visibility 或 MLS boundary。

Cell special form 使用 `ck:cell:ck.component.pin.v1:<pin_scope.id>`。v1 不注册 pin 专用 typed id。

## 3. Scope Safety

目标对象必须落在 resolved effective scope 内，或在该 scope 内可见。Public Space 不得 pin Circle-private object；Realm-wide pin 不得泄露 Circle-scoped Message 的存在性。若目标不可见或跨 scope 不合法，reducer MUST fail closed，并对调用方返回与不可见对象一致的 `not_found`；错误形态不得向无权 actor 泄露目标是否存在。内部审计 MAY 记录更具体的 scope mismatch 诊断。

Pin note 若存在 MUST 加密，除非 Realm policy 明确允许该 note plaintext-visible。

## 4. Events

`ck.pin.add` 添加或更新一个 `(pin_scope, target_ref)` pin entry，携带 rank 和可选 note。`ck.pin.remove` tombstone 同一 entry。`ck.pin.reorder` 只更新 rank；不得改变 target 或 pin scope。

重排必须保持稳定：相同 rank 冲突时，projection 使用 event causal order 和 event id 作 deterministic tie-breaker，但 writer SHOULD 使用 rank rebalance 避免长期冲突。

## 5. Interactions

Pin 不覆盖 Message expiry、redaction、history visibility、moderation 或 capability。目标过期、redacted、quarantined 或对 viewer 不可见时，pin projection MUST 降级为最小 stub 或省略；不得因为 pin 而恢复 plaintext。
