---
title: Calendar Event
status: candidate
normative: true
stability: v1
updated: 2026-06-06
see_also:
  - flow-and-message.md
  - relation.md
  - views.md
  - ../../artifacts/schemas/calendar-event.schema.json
  - ../../artifacts/schemas/rsvp.schema.json
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具有规范约束力。

## 1. 模型

Calendar event 是一个带 `ck.profile.calendar_event.v1` 的 Flow profile，而不是新的顶层对象 kind。事件标题、描述、议程和附件继续由 Flow / Message / Morph / Relation 表达；日程语义由 Flow metadata 中 profile 声明的 schedule fields 表达。

实现 MUST NOT 新增 calendar 专用 typed id。可视化日历、gantt 或 agenda 是 View renderer / projection，而不是新的真相源。

## 2. Schedule 字段

`ck.profile.calendar_event.v1` 的 schedule fields MUST 至少支持：

- `start`: RFC 3339 timestamp 或 all-day date。
- `end`: RFC 3339 timestamp 或 all-day date，必须晚于 `start`。
- `timezone`: IANA time zone name；all-day 事件也必须保留。
- `all_day`: boolean。
- `recurrence`: v1 RRULE 子集。
- `location`: 加密 envelope 或封闭的 plaintext `calendar_location` 对象。
- `call_id`: 可选 Cokret 通话 / 会议 session ID。

字段顺序在 schema 和 prose 中 MUST 保持上述顺序，避免实现把 `timezone` 或 `all_day` 作为后补语义。

## 3. Recurrence

v1 recurrence 使用 RRULE 子集：`FREQ`、`INTERVAL`、`BYDAY`、`COUNT`、`UNTIL`。wire schema 使用协议命名字段 `frequency`、`interval`、`by_day`、`count`、`expires_at`；实现 MUST 按 `timezone` 做 wall-clock 展开；跨 DST 时，同一 local time 的会议不得因为 UTC offset 改变而漂移。

`count` 与 `expires_at` MUST NOT 同时出现；二者均省略表示无协议层终止条件，但实现仍必须受 [`../conformance/scalability-constraints.md`](../conformance/scalability-constraints.md) 的单次展开上限约束。`count` 的最大值为 10000；projection、查询和通知展开单次最多返回 10000 个 occurrence，超过时 MUST 分页或返回 `limit_exceeded`。未知 RRULE 字段 MUST 触发 schema / profile reject，而不是静默忽略。

`expires_at` 是 UTC instant。每个 occurrence 先按事件 `timezone` 和 local wall-clock 起点展开，再把该 local start 转换成 instant 与 `expires_at` 比较；`occurrence_start_instant <= expires_at` 的实例包含在 series 中，晚于 `expires_at` 的实例排除。`all_day=true` 时，展开锚点是事件 `timezone` 的 local midnight；跨 DST 时仍以 local date / local time 为主，UTC offset 只在比较 `expires_at` 与生成 instance key 时使用。

## 4. Attendees

Attendees 可由 profile 声明的 `attendees[]` 字段或现有 membership / invite projection 推导。v1 不注册裸 `invited` Relation kind；如果未来需要显式邀请边，必须注册明确的 `calendar_invite` relation kind，并给出 cardinality、授权和隐私规则。

Attendee DID、display name snapshot 和 attendance role 不得替代 Realm membership 或 capability。能看到日历事件，不等于能看到其 private discussion 或 Circle-scoped内容。

`attendees[]` 长度上限为 1000，且同一数组内 `actor_id` MUST 唯一；同一 actor 出现多个 role 或 display snapshot 时，producer MUST 在写入前合并为一条记录，无法合并时 reducer MUST `schema_violation`。`uniqueItems` 仅捕获整对象重复，不能替代 actor 级唯一性。

## 5. RSVP

RSVP 通过 `ck.rsvp.set` 写入。payload 必须包含 `event_ref`、`status` 和 `occurrence`；`comment` 若存在 MUST 加密，除非 Realm policy 明确允许该服务接收 plaintext-visible RSVP comment。

RSVP projection 按 actor 对 `(event_ref, occurrence)` 做 LWW 收敛。`occurrence=null` 表示整个 series；实例级 RSVP 使用 recurrence instance key。该 key MUST 是 occurrence 的 local wall-clock start 按事件 `timezone` 展开后写成 `YYYY-MM-DD`（all-day）或 `YYYY-MM-DDTHH:mm:ss[Zone]`（非 all-day，Zone 为 IANA timezone 名）的 canonical 字符串；同一 series instance 在所有实现中必须生成相同 key。重复写同一 status 是 no-op，较新 HLC 的不同 status 替换旧值。

`ck.rsvp.set` 只表达回应，不修改 Flow schedule，不创建 attendees，也不赋予访问权。
