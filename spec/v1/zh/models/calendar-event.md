---
title: Calendar Event
status: candidate
normative: true
stability: v1
updated: 2026-07-02
see_also:
  - strand-and-message.md
  - relation.md
  - views.md
  - ../../artifacts/schemas/calendar-event.schema.json
  - ../../artifacts/schemas/rsvp.schema.json
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具有规范约束力。

## 1. 模型

Calendar event 是一个带 `ak.profile.calendar_event.v1` 的 Strand profile，而不是新的顶层对象 kind。事件标题、描述、议程和附件继续由 Strand / Message / Morph / Relation 表达；日程语义由 Strand metadata 中 profile 声明的 schedule fields 表达。

实现 MUST NOT 新增 calendar 专用 typed id。可视化日历、gantt 或 agenda 是 View renderer / projection，而不是新的真相源。

## 2. Schedule 字段

`ak.profile.calendar_event.v1` 的 schedule object MUST 支持以下字段；其中 `start` / `end` / `timezone` / `all_day` 是 `calendar-event.schema.json` 的 required core，`recurrence` / `location` / `call_id` 是可选 profile fields（出现时按本节校验）：

- `start`（required）：RFC 3339 timestamp 或 all-day date。
- `end`（required）：RFC 3339 timestamp 或 all-day date，必须晚于 `start`。
- `timezone`（required）：IANA time zone name；all-day 事件也必须保留。
- `all_day`（required）：boolean。
- `recurrence`（optional）：v1 RRULE 子集。
- `location`（optional）：加密 envelope 或封闭的 plaintext `calendar_location` 对象。
- `call_id`（optional）：Arkret 通话 / 会议 session ID。

字段顺序在 schema 和 prose 中 MUST 保持上述顺序，避免实现把 `timezone` 或 `all_day` 作为后补语义。

`end` 与 `start` 的时序约束有明确 enforcement 归属（与 §4 attendees 唯一性同一模式）：非 all-day 事件 `end` MUST 晚于 `start`；`all_day=true` 时 `end` MUST ≥ `start`（同日单日事件）。producer 写入前 MUST 校验；reducer / profile 在 `end` 不满足该约束时 MUST 以 `schema_violation` 拒绝。JSON Schema 无法表达跨字段时序比较，故该约束由 reducer / profile 承载，而非 `calendar-event.schema.json`。

## 3. Recurrence

v1 recurrence 是 RFC 8984 JSCalendar `RecurrenceRule` 的 snake_case 子集：`frequency`、`interval`、`by_day`、`by_month`、`by_month_day`、`by_set_position`、`first_day_of_week`、`count`、`until`。字段逐一映射到 JSCalendar 的同名 camelCase 字段；没有 Arkret 自创的 RRULE 语义。`frequency` 使用 JSCalendar 小写值 `daily | weekly | monthly | yearly`。`by_day[]` 是 `NDay[]`：每项包含小写 `day`（`mo`..`su`）和可选非零 `nth_of_period`，因此 `1MO` / `-1FR` 分别写作 `{day:"mo",nth_of_period:1}` / `{day:"fr",nth_of_period:-1}`。实现 MUST 按 `timezone` 做 wall-clock 展开；跨 DST 时，同一 local time 的会议不得因为 UTC offset 改变而漂移。

`count` 与 `until` MUST NOT 同时出现；二者均省略表示无协议层终止条件，但实现仍必须受 [`../conformance/scalability-constraints.md`](../conformance/scalability-constraints.md) 的单次展开上限约束。`count` 的最大值为 10000；projection、查询和通知展开单次最多返回 10000 个 occurrence，超过时 MUST 分页或返回 `limit_exceeded`。未知 RecurrenceRule 字段 MUST 触发 schema / profile reject，而不是静默忽略。

`until` 是 RFC 8984 `LocalDateTime`（无 `Z`、无 UTC offset），按事件 `timezone` 解释；最后一个 occurrence 的 local start MUST 小于或等于 `until`。`all_day=true` 时，展开锚点是事件 `timezone` 的 local midnight；跨 DST 时仍以 local date / local time 为主。需要与外部 UTC deadline 比较的实现必须先按 RFC 8984 的 discontinuity 规则把 local occurrence 转成 instant，不得把 `until` 当 UTC timestamp。

## 4. Attendees

Attendees 可由 profile 声明的 `attendees[]` 字段或现有 membership / invite projection 推导。v1 不注册裸 `invited` Relation kind；如果未来需要显式邀请边，必须注册明确的 `calendar_invite` relation kind，并给出 cardinality、授权和隐私规则。

Attendee DID、display name snapshot 和 attendance role 不得替代 Realm membership 或 capability。能看到日历事件，不等于能看到其 private discussion 或 Circle-scoped内容。

`attendees[]` 长度上限为 1000，且同一数组内 `actor_id` MUST 唯一；同一 actor 出现多个 role 或 display snapshot 时，producer MUST 在写入前合并为一条记录，无法合并时 reducer MUST `schema_violation`。`uniqueItems` 仅捕获整对象重复，不能替代 actor 级唯一性。

## 5. RSVP

RSVP 通过 `ak.rsvp.set` 写入。payload 必须包含 `event_ref`、`status` 和 `occurrence`；`status` 是封闭集 `accepted | declined | tentative`，未知值 MUST `schema_violation`；`comment` 若存在 MUST 加密，除非 Realm policy 明确允许该服务接收 plaintext-visible RSVP comment。

RSVP projection 按 accountable actor 对 `(event_ref, occurrence)` 使用 `mv_register` 收敛；cell subject 固定为 [`encoding.md` §9.5.2](../conformance/encoding.md) 的 `[payload.event_ref, payload.occurrence, envelope.actor_id]`。`occurrence=null` 表示整个 series；实例级 RSVP 使用 recurrence instance key。该 key MUST 是 occurrence 的 local wall-clock start 按事件 `timezone` 展开后写成 `YYYY-MM-DD`（all-day）或 `YYYY-MM-DDTHH:mm:ss[Zone]`（非 all-day，Zone 为 IANA timezone 名）的 canonical 字符串；同一 series instance 在所有实现中必须生成相同 key。

同一 responder 的因果后继 RSVP 支配旧 head；真正并发且 status 不同的 RSVP 必须暴露多个 heads，直到该 actor 以观察到这些 heads 的后续 RSVP 显式解决。并发 join 的结果不得由 HLC、`created_at`、`event_id` 或到达顺序选边。重复写同一 status 可作为 value-level no-op，但不得借此隐藏并发的不同 status。

`ak.rsvp.set` 只表达回应，不修改 Strand schedule，不创建 attendees，也不赋予访问权。

## 6. Schedule notification

仅当实现同时声明 `ak.profile.calendar_event.v1` 与 notification 派生能力时，Calendar schedule 变更才通过 `ak.strand.update` 修改 §2 字段，并额外把 `metadata.fields.start` / `end` / `timezone` / `all_day` / `recurrence` / `location` / `call_id` / `attendees` 视为 schedule-relevant；这组 calendar 字段不属于 core notification。实现 MUST 按 [`private-objects.md` §3.6](./private-objects.md#36-schedule-notification-派生) 生成 `notification_kind=schedule`，并把当前 `attendees[].actor_id` 加入 receiver 候选集合；最终只通知有访问权且未被 muted / DND / push rule 抑制的 receiver。同一 patch 同时改变多项时只产生一条 notification。

Calendar attendees 是 schedule notification 的 receiver set 输入，不是访问权真源；无 Realm / Circle 读取权的 attendee MUST 不收到 notification 或 push wakeup。RSVP 变更默认不产生 schedule notification；RSVP 自身的 UI 状态由 RSVP projection 展示。
