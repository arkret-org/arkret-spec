---
title: Pinned Messages and Objects
status: candidate
normative: true
stability: v1
updated: 2026-07-02
see_also:
  - strand-and-message.md
  - realm-and-space.md
  - views.md
  - personal-productivity.md
  - ../../artifacts/schemas/pin.schema.json
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具有规范约束力。

## 1. 范围

Shared pin 是进入 Realm reducer 的共享投影事实，用于把 Message、Strand、Morph、Relation 或其它可引用对象固定在某个共享范围中。个人保存 / 收藏不使用 shared pin；它们由 [personal-productivity.md](./personal-productivity.md) 的 account data 表达。

**架构决策（normative boundary）**：Pin 有意不建模为 `Relation.kind=pinned`。Relation 表达对象之间可查询、可参与图遍历的语义边；Pin 表达某个 projection home 的有序 UI roster，`pin_scope` 不是关系端点或安全边界，且 reorder 是高频 CAS 排序操作。把 Pin 放入 Relation 会让 UI 排序边进入通用关系图、改变 graph query / relation-kind registry 语义并混淆 scope。实现 MUST 使用本文件的 pin cell 与三类 event，MUST NOT 以 `Relation` 代替 shared Pin。

实现声明 `ak.profile.pinned_items.v1` 时，MUST 支持 `ak.pin.add`、`ak.pin.remove` 和 `ak.pin.reorder`。

## 2. Pin Scope

Pin payload 使用 `pin_scope`，MUST NOT 使用裸 `scope` 或 scope-reference 字段。`pin_scope` 的形态为 `{ kind, id }`，`kind` 取 `strand`、`realm`、`circle` 或 `space`。

`pin_scope` 是 projection home，不是安全边界。`kind=space` 时，reducer MUST 解析 Space metadata 的 effective scope；Space 不因此获得独立 membership、policy、history visibility 或 MLS boundary。

Cell special form 使用 `ak:cell:ak.component.pin.v1:<pin_scope.id>`。v1 不注册 pin 专用 typed id。

## 3. Scope Safety

目标对象必须落在 resolved effective scope 内，或在该 scope 内可见。Public Space 不得 pin Circle-private object；Realm-wide pin 不得泄露 Circle-scoped Message 的存在性。若目标不可见或跨 scope 不合法，reducer MUST fail closed，并对调用方返回与不可见对象一致的 `not_found`；错误形态不得向无权 actor 泄露目标是否存在。内部审计 MAY 记录更具体的 scope mismatch 诊断。

Pin note 若存在 MUST 使用 `EncryptedPayload` 加密；v1 不提供 plaintext-visible note 分支。需要公开说明时应创建普通 Message / Morph 并 pin 该对象，不得把 Pin 元数据变成额外明文通道。

## 4. Events

`ak.pin.add` 添加或更新一个 `(pin_scope, target_ref)` pin entry，携带 rank 和可选 note。`ak.pin.remove` tombstone 同一 entry。`ak.pin.reorder` 只更新 rank；不得改变 target 或 pin scope。

### 4.1 收敛（normative）

`ak.component.pin.v1:<pin_scope.id>` 是 [`../authz/event-auth-state-resolution.md` §9](../authz/event-auth-state-resolution.md)
的核心 `or_set`，其元素是 **pin 断言**：`ak.pin.add`、`ak.pin.remove` 与 `ak.pin.reorder`
**各精确投影一个** `{"kind":"or_set_add","tag":{"dot":true},"value":{"field":"payload"}}`。
remove 与 reorder 同样是**往集合里加一条断言**，而不是 observed-remove。

一个 pin scope 下的全部 pin 共用这一个 cell，因此 entry 身份分两层：`pin_scope` 由 cell subject
承载，`target_ref` 是元素值上的字段。三个 kind 的元素值都是各自完整 payload，投影不拼装、
改名或裁剪字段（[`event-and-patch.md` §2.4.2](./event-and-patch.md)）。

**为什么 remove 不用 `or_set_remove_observed`**：无 `match` 的形态会移除同 scope 下**全部**
target 的 pin；带 `match` 的形态只移除**冻结前态**下存活的 add dot，与该 remove 并发的 add
不在其中，于是并发 (add, remove) 会静默收敛为 add；下一段要求这类互斥并发显式暴露而非任选一边，故 remove 必须是断言。

**Roster 投影（默认视图）**：对每个 `target_ref`，取该 `(pin_scope, target_ref)` 下**因果最晚**
的断言集；恰有一个 head 时它是 effective 断言。存在互不可达 heads 时，该 target 进入冲突投影，
默认 roster 不投影 active pin，并向有权 reader 暴露完整 heads；后续断言必须在 causal basis 覆盖完整
current head set 才能收敛。
effective 断言来自 `ak.pin.remove` 时该 entry 不出现在 roster；来自 `ak.pin.add` 时 entry 为
该 payload；来自 `ak.pin.reorder` 时 rank 取该 reorder 的 `rank`，`note` 与其余 entry 字段
继承自同一 `(pin_scope, target_ref)` 下因果最晚的存活 `ak.pin.add` 断言——reorder
「只更新 rank」即由此保证，reorder MUST NOT 清除 note。

**没有可继承 `ak.pin.add` 时的 reorder（normative）**：若该 `(pin_scope, target_ref)` 下不存在
因果更早且存活的 `ak.pin.add` 断言（从未 add，或 effective 断言是 `ak.pin.remove`），reducer
MUST 以 `failed_precondition`（`reason=pin_target_not_pinned`）拒绝该 `ak.pin.reorder`，
**MUST NOT** 用只有 rank 的合成 entry 把目标重新放回 roster。目标对象尚未在本地物化时按
[`common-fields.md` §5.1](./common-fields.md) 的「未知对象 pending / replay」保留待重放。

该 or_set 的 join 是 dot 集合并，可交换、可结合、幂等且不声明 Bottom。审计视图保留全部断言；领域投影可报告冲突，但该诊断不是新的 cell 状态或授权拒绝。

重排必须保持稳定：不同 target 按 `(rank, target_ref)` 的 ASCII bytewise lexicographic ascending 排序；相同 rank 不构成互斥冲突。`ak.pin.remove.expected_rank` 与 `ak.pin.reorder.expected_rank` 是可选 CAS 前置；存在时 MUST 与无冲突的 current materialized rank 逐字节相等，否则 `failed_precondition` 且不得修改 entry。单一 target 的互不可达 reorder/add/remove 按上一段进入 `pin_conflict`，不得用 digest、HLC、actor id 或接收顺序选边。writer SHOULD 使用 rank rebalance 避免长期 rank 碰撞。

## 5. Interactions

Pin 不覆盖 Message expiry、redaction、history visibility、moderation 或 capability。目标过期、redacted、quarantined 或对 viewer 不可见时，pin projection MUST 降级为最小 stub 或省略；不得因为 pin 而恢复 plaintext。
