---
title: Calendar Event
status: candidate
normative: true
stability: v1
updated: 2026-07-27
see_also:
  - strand-and-message.md
  - relation.md
  - views.md
  - ../../artifacts/schemas/calendar-event.schema.json
  - ../../artifacts/schemas/rsvp.schema.json
  - ../../artifacts/registry/calendar-timezone-registry.json
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具有规范约束力。

## 1. 模型与激活

Calendar event 是一个带 Calendar schedule 子树的 Strand，而不是新的顶层对象 kind。事件标题、描述、议程和附件继续由 Strand / Message / Morph / Relation 表达；日程语义由 Strand metadata 中的 schedule 子树表达。实现 MUST NOT 新增 calendar 专用 typed id。可视化日历、gantt 或 agenda 是 View renderer / projection，而不是新的真相源。

`ak.profile.calendar_event.v1` 只表示**实现 conformance profile**，MUST NOT 被写入对象 metadata 充当对象 kind 或 schema 激活标记。

**唯一激活路径（normative）**：Calendar Strand 的 `schema_refs[]` MUST 包含 `ak.schema.calendar_event.v1`，schedule 数据 MUST 位于单一命名空间 `metadata.fields.calendar`，且该子树 MUST 完整通过 [`calendar-event.schema.json`](../../artifacts/schemas/calendar-event.schema.json) 校验。

- **双向共现**：schema ref 与 `metadata.fields.calendar` 子树 MUST 在 **post-patch 对象**上同时出现或同时不出现。只删 ref 保留子树、或只删子树保留 ref，均 MUST 以 `schema_violation` reason=`calendar_activation_mismatch` 拒绝。
- 容器 self-schema `ak.schema.strand.v1` MUST NOT 出现在 `schema_refs[]`（与 [`morph.md` §4](./morph.md) 同一规则）。
- 扁平 `metadata.fields.start` / `end` / `timezone` / `all_day` / `recurrence` / `attendees`，以及 `metadata.fields.profile` / `profile_refs`，都 MUST 被 Strand schema 拒绝。实现 MUST NOT 通过"存在若干字段"推断 Calendar 语义。
- 写入 Calendar 子树的 `ak.strand.create` / `ak.strand.update` MUST 按 [`event-and-patch.md` §2.7](./event-and-patch.md) 在 `requirements.schema[]` 中列出 `ak.schema.calendar_event.v1`；replay MUST 使用该 per-event 绑定校验，MUST NOT 使用对象当前的 `schema_refs[]`。
- profile-aware validator MUST 对 create 与 post-patch 的完整子树做全对象校验，而不是只校验被 patch 触及的字段。

`schema_refs` 是公开、被签名、可路由的对象 schema 激活信息。它会暴露"这是一个 Calendar Strand"这一分类事实：加密部署 MUST 在 privacy disclosure 中把它列为有意的 routing metadata，MUST NOT 声称 schedule 完全不可观察。metadata 加密时，producer MUST 在加密前校验、授权客户端 MUST 在解密后校验；不能解密的服务只校验 `schema_refs` 与 envelope，MUST NOT 声称验证过 schedule plaintext。

## 2. Schedule 字段

`metadata.fields.calendar` 的 required core 是 `start`、`end`、`timezone`、`tzdb_version`、`all_day`、`status` 六项；可选 profile fields 是 `recurrence`、`location`、`call_id`、`attendees`。字段顺序在 schema 和 prose 中 MUST 保持下列顺序：

- `start`（required）：区间下界，同时是 recurrence 锚点。
- `end`（required）：区间上界（排他）。
- `timezone`（required）：canonical IANA Zone name；all-day 事件也 MUST 保留。
- `tzdb_version`（required）：解释 `timezone` 与全部派生 instant 的 IANA TZDB release tag。
- `all_day`（required）：boolean，选择 §3 的两个时间分支之一。
- `status`（required）：`confirmed | tentative | cancelled`，无隐式默认，MUST NOT 省略。
- `recurrence`（optional）：§4 的 RFC 8984 子集。
- `location`（optional）：加密 envelope 或封闭的 plaintext `calendar_location` 对象。
- `call_id`（optional）：Arkret 通话 / 会议 session ID。
- `attendees`（optional）：§7 的 canonical roster。

`status` 与通用 Strand `stage` / `state` 正交：`state` 是对象物理生命周期，`stage` 是业务进度轴，`status` 只表达该日程本身是否成立。实现 MUST NOT 把 `stage` 私自解释成 calendar status，也 MUST NOT 用 `status` 表达对象生命周期。

## 3. 时间语义与区间

Calendar schedule **不携带绝对 instant**。timed 事件的 `start` / `end` 是 RFC 8984 `LocalDateTime`（[`time.schema.json#/$defs/local_date_time`](../../artifacts/schemas/time.schema.json)，整秒、无 offset、无 `Z`、无括号 Zone、无小数秒），按 `timezone` + `tzdb_version` 解释。这保证"固定本地会议时间"在 TZDB 规则变化时不会被 UTC instant 反推出另一个 local anchor。

1. **半开区间**：无论哪个分支，事件区间都是 `[start, end)`。
2. **all-day 分支**（`all_day=true`）：`start` / `end` 都是 Gregorian `date`。`end` MUST 严格晚于 `start`，单日事件写成次日日期；`end == start` MUST 拒绝。
3. **timed 分支**（`all_day=false`）：`start` / `end` 都是整秒 `LocalDateTime`。producer / reducer 按 §5 的 discontinuity 规则把 base start/end 转成 instant，并 MUST 要求 `base_end_instant > base_start_instant`。
4. **recurring duration**：v1 不引入 ISO duration wire 字段。recurring timed event 的 duration 固定为 `base_end_instant - base_start_instant`；每个 occurrence 的 local start 转成 instant 后加同一 elapsed duration 得到该 occurrence 的 end。recurring all-day event 的每个 occurrence 保留 `end_date - start_date` 个 local calendar day。实现 MUST NOT 自行在 elapsed duration、local wall-clock delta 与包含式日期之间选择。
5. JSON Schema 无法表达跨字段时序比较，故 `end` 与 `start` 的比较由 reducer / profile 承载：producer 写入前 MUST 校验，reducer 在不满足时 MUST 以 `schema_violation` 拒绝（与 §7 attendee 唯一性同一模式）。

## 4. Recurrence

v1 recurrence 是 RFC 8984 JSCalendar `RecurrenceRule` 的 snake_case 子集：`frequency`、`interval`、`by_day`、`by_month`、`by_month_day`、`by_set_position`、`first_day_of_week`、`count`、`until`。字段逐一映射到 JSCalendar 的同名 camelCase 字段；没有 Arkret 自创的 RRULE 语义。`frequency` 使用 JSCalendar 小写值 `daily | weekly | monthly | yearly`。`by_day[]` 是 `NDay[]`：每项包含小写 `day`（`mo`..`su`）和可选非零 `nth_of_period`，因此 `1MO` / `-1FR` 分别写作 `{day:"mo",nth_of_period:1}` / `{day:"fr",nth_of_period:-1}`。

### 4.1 默认值与隐式 filter

- 省略 `interval` 等价于 `1`；省略 `first_day_of_week` 等价于 `mo`。
- `rscale` 固定 Gregorian，`skip` 固定 `omit`；二者不出现在 wire 上。
- JSCalendar `@type` 由 Arkret schema context 隐含，wire 上 MUST NOT 携带。
- base `start` 总是第一个 occurrence，并计入 `count`，即使它不匹配任何 `by_*`。
- v1 子集不暴露 `by_hour` / `by_minute` / `by_second`，因此每个 occurrence 的 hour/minute/second MUST 继承 base start；`weekly` 缺 `by_day` 时取 base weekday；`monthly` 同时缺 `by_day` / `by_month_day` 时取 base month-day；`yearly` 缺省时按 RFC 8984 隐式补 base month 与 month-day。所有隐式 filter MUST 进入同一 expansion 算法与 [`ak.vector.calendar.recurrence_expansion.v1`](../conformance/conformance-vectors.md)，MUST NOT 由 UI 预填字段模拟。

### 4.2 终止条件与收窄

- `count` 与 `until` MUST NOT 同时出现；同时出现一律 `schema_violation`。
- `until` 与 occurrence 的 local start 做 `<=` 比较，并与 `start` 同分支：`all_day=true` 时是 Gregorian `date`，否则是整秒 `LocalDateTime`。`until` MUST NOT 早于 base start。timed 分支既然拒绝小数秒，parser 就 MUST NOT 私自接受 `.0` / `.000`。
- `count` 收窄为 `1..=10000`；`by_set_position` 与 `nth_of_period` 收窄为 `-366..=-1 | 1..=366`；`by_month_day` 收窄为 `-31..=-1 | 1..=31`；`by_month` 只允许无前导零的 `"1"`..`"12"`。
- 所有出现的 `by_*` 数组 MUST 非空且元素唯一；空数组一律 `schema_violation`，MUST NOT 等价于缺省。
- 搭配前置条件：`nth_of_period` 只允许 `monthly` / `yearly`；`by_month_day` MUST NOT 与 `weekly` 搭配；`by_set_position` MUST 至少与一个 `by_day` / `by_month` / `by_month_day` 同时出现。不满足前置条件 MUST 直接拒绝，MUST NOT 接受后忽略。
- `excludedRecurrenceRules`、`recurrenceOverrides`、RDATE / EXDATE、逐实例 reschedule 或 cancel，以及任何未列出的 RecurrenceRule 成员，在 v1 baseline 中 MUST 以 schema reject 或 `unsupported_feature` 失败，MUST NOT 静默忽略。

### 4.3 展开边界

无 `count` / `until` 的 recurrence MUST NOT 提供"展开全部"操作。每次 expansion MUST 携带有限 `[range_start, range_end)` 与 `limit`，并受 [`../conformance/scalability-constraints.md`](../conformance/scalability-constraints.md) 的单次上限与 candidate-period 扫描预算约束；预算耗尽时 MUST 返回带 continuation 的 `limit_exceeded` 或 partial result。continuation MUST 绑定 schedule revision、`tzdb_version`、range 与排序键；任一 basis 改变后旧 cursor MUST 失效，MUST NOT 在新 schedule 上续跑。

## 5. Timezone 与 TZDB 版本

`timezone` MUST 是 [`calendar-timezone-registry.json`](../../artifacts/registry/calendar-timezone-registry.json) 中**该 schedule 所 pin 的那一行 release** 的 **canonical Zone name**。registry 的 `required_normalizations` 是**逐 release** 冻结的：某个后续 IANA release 改变了 Link target 时，由它自己的行携带新映射，早先的行保持签名当时生效的映射。实现 MUST 用 `tzdb_version` 选中行后再查表，MUST NOT 使用跨 release 的全局映射。producer MUST 在签名前把 Link alias 归一化为 canonical Zone；receiver MUST NOT 对已签名的值再做归一化——出现在 wire 上的 alias 是 producer 缺陷，MUST 拒绝而不是修复。occurrence key 复用该 exact signed value。

`tzdb_version` 是被签名覆盖的 IANA release tag（形如 `2026a`）。receiver MUST 用该 release 的规则解释 `timezone` 与全部派生 instant，MUST NOT 依赖本地安装版本。服务在 `ServiceDescribe.calendar_tzdb_versions` 声明可执行版本集合；无法执行某 schedule 的版本时 MUST 返回 `calendar_tzdb_mismatch` / `unsupported_feature`，或把 instant projection 标为 `unresolved`，MUST NOT 回退到相近或更新的 release 后静默产生另一结果。conformance 比较 MUST 在 schedule 所绑定的同一 TZDB version 下进行。

显式更新 `tzdb_version` MAY 改变派生 instant，但 MUST NOT 改变已签名的 `timezone`，也 MUST NOT 改变任何 local occurrence key；只有显式 timezone patch 才改变 occurrence identity。若任一 occurrence 的 instant 或 end 因此变化，§6 的 significant-change 规则 MUST 触发 RSVP `needs_reconfirmation` 与 schedule notification。

**DST 不连续**：重叠（fold）与不存在（gap）的 local time MUST 直接镜像 RFC 8984——一律以 transition **之前**的 offset 解释。实现 MUST NOT 各自选择拒绝、取后 offset 或产生两个 occurrence。

## 6. Schedule revision 与 occurrence 身份

修改 Calendar 子树的 Event 构成该 Strand 的 **schedule revision DAG**。只修改标题等非 Calendar 子树的 `ak.strand.update` 不产生新的 schedule revision。

Calendar schedule projection MUST 暴露 canonical `schedule_revision_heads[]` 与 `schedule_resolution_state`：

- `settled`：只有一个 head，或多个 head 解密并校验后 Calendar schedule 的 canonical bytes 全部相同。canonical heads 即使取值相同也全部保留。
- `conflict`：出现两个不同的 schedule value。
- `encrypted_unresolved`：无法解密比较。

只有 `settled` 才 MAY 展开 occurrence、发送 RSVP 或派生精确 schedule notification。实现 MUST NOT 用 HLC、接收顺序或私有 LWW 从冲突 heads 中选边。Calendar profile MUST 使用显式 schedule resolution Event 收敛 heads：该 Event 引用并消费全部当前 metadata cell heads、携带完整 post-state，并复用 `ak.strand.update` 的授权边界。普通 `ak.strand.update` 只绑定一个 frozen base head，MUST NOT 被称为 multi-head resolution。

**`calendar_schedule_unsettled` 是 authoring 侧与投影侧的错误，MUST NOT 成为服务端 admission 条件**：判定 settledness 需要读取 Calendar 子树明文，E2EE 部署的服务端做不到。authoring client 在本地算出非 `settled` 时 MUST 拒绝构造 RSVP；若某个 client 仍然发出，服务端按 §8.4 照常接受（它只看得到 shape 与 envelope），由授权投影把该 head 归入 §9 的相应类别。这条与 §8.1 第三层同一原则：**任何需要 schedule 明文的判定都不得进入 admission**，否则 plaintext Realm 会比 E2EE Realm 多拒绝一批 Event，两者 accepted set 分叉。

**significant-change 封闭表（normative）**：下表覆盖 §2 的全部 schedule 字段。表外字段 MUST NOT 触发实现私有的 RSVP 或通知行为；表内字段 MUST 恰好按本表处理，实现 MUST NOT 加严或放宽。

| 变化字段 | instance RSVP | series RSVP | schedule notification |
| --- | --- | --- | --- |
| `start` | `stale_orphaned` | `needs_reconfirmation` | 是 |
| `timezone` | `stale_orphaned` | `needs_reconfirmation` | 是 |
| `all_day` | `stale_orphaned` | `needs_reconfirmation` | 是 |
| `recurrence` | `stale_orphaned` | `needs_reconfirmation` | 是 |
| `end` | `needs_reconfirmation` | `needs_reconfirmation` | 是 |
| `status` | `needs_reconfirmation` | `needs_reconfirmation` | 是 |
| `location` | `needs_reconfirmation` | `needs_reconfirmation` | 是 |
| `call_id` | `needs_reconfirmation` | `needs_reconfirmation` | 是 |
| `tzdb_version` | 仅当该 occurrence 的派生 instant 或 end 实际变化时 `needs_reconfirmation`，否则不变 | 同左 | 仅在同一条件下 |
| `attendees` | 不变 | 不变 | 是，但只对被增删的 actor |

前四行是 **identity-affecting fields**：它们改变 occurrence key 本身，因此旧 instance RSVP MUST 保留审计并标记 `stale_orphaned`，MUST NOT 自动迁移到新 key；series RSVP 的 subject 不含 occurrence，故不 orphan，只需重新确认。

投影 MUST 暴露 current frontier、每条 RSVP 的 entry basis、逐 ref 因果关系与 stale / reconfirmation 原因，MUST NOT 把旧回应静默显示为新 occurrence 的当前回应。

## 7. Attendees

`calendar.attendees[]` 是**唯一** canonical schedule roster。membership / invite projection 只能作为 producer 生成 roster patch 的输入，MUST NOT 成为第二个投影真相源。v1 不注册裸 `invited` Relation kind；未来若需要显式邀请边，MUST 注册明确的 `calendar_invite` relation kind 并给出 cardinality、授权和隐私规则，MUST NOT 复用 attendees 或 RSVP 暗造邀请投递。

- `attendees[]` 长度上限 1000，同一数组内 `actor_id` MUST 唯一。同一 actor 出现多条时 producer MUST 在写入前合并，无法合并时 reducer MUST `schema_violation`。`uniqueItems` 只捕获整对象重复，不能替代 actor 级唯一性。
- `role` 省略时等价于 `required`。
- `organizer` 只是展示 / 日程语义，MUST NOT 自动产生 capability；同一 roster 至多一个 `organizer`（由 schema `maxContains` 强制）。需要多 organizer 时另开 profile。
- `display_name_snapshot` 是可泄露身份的信息：metadata 加密时 MUST 一并加密。
- roster 增删 MUST NOT 创建 Realm / Circle membership，也 MUST NOT 扩大 history access。能看到日历事件不等于能看到其 private discussion 或 Circle-scoped 内容。

## 8. RSVP

RSVP 通过 `ak.rsvp.set` 写入，payload 是 `{event_ref, occurrence, entry}`。

- `occurrence`：JSON `null` 表示整个 series；实例级 RSVP 使用 canonical instance key——all-day 写成 `YYYY-MM-DD`，timed 写成 `YYYY-MM-DDTHH:mm:ss[Zone]`（Zone 为已签名的 canonical IANA Zone name）。两种分支的日期部分都 MUST 是真实的 proleptic-Gregorian date；只匹配数字正则但实际不存在的日期（如 `2026-02-30`）MUST 以 `rsvp_occurrence_not_canonical` 拒绝。该判定只需解析本 Event 的签名字符串，属于 shape admission，不依赖 Calendar 子树明文。producer MUST 在签名前生成 canonical key；receiver MUST 拒绝非 canonical key，MUST NOT "接受后修复"自己的缓存地址。非 recurring Calendar 只允许 `occurrence=null`，避免同一单次事件同时出现 series 与 base-instance 两个 cell。
- `entry` 是封闭对象 `{schedule_basis_refs, response | encrypted_response}`。

### 8.1 schedule_basis_refs

`entry.schedule_basis_refs[]` 精确列出 responder 实际观察到的全部因果 maximal schedule revision Event，series 与 instance RSVP **均必填**。其 item 是 `event_digest`，与 envelope `causal_refs[]` 同型：

- 非空、去重、按 digest canonical UTF-8 byte order 升序排列；
- MUST 是 envelope `causal_refs[]` 的**子集**——这是纯 byte 级集合包含判定，无需解析目标 Event，因此服务端在 E2EE 下同样 MUST 执行；不满足时以 `rsvp_basis_not_causal` 拒绝，MUST NOT 进入 pending；
- `maxItems` 为 128，与 `causal_refs` 上限一致。两种失败形态不同，MUST 分别对待：wire 上真的携带超过 128 项的 Event 由 schema `maxItems` 以 `schema_violation` 在 ingress 拒绝；而 authoring client 观察到的 schedule frontier 本身超过 128、因而无法构造合法 basis 时，MUST 以 `schedule_frontier_too_large` 在本地 fail closed，先经 schedule resolution 收敛再回应，MUST NOT 截断 basis 或只列部分 head。

**判定分层（normative）**：basis 的校验严格分成三层，且每层的可判定材料在 E2EE 与 plaintext Realm 中**完全相同**，因此两类部署 MUST 得到同一个 canonical accepted set：

| 层 | 判定材料 | 未通过时 |
| --- | --- | --- |
| shape admission | 只看本 Event 自身（非空 / 去重 / 排序 / ⊆ `causal_refs` / ≤128） | `rsvp_basis_not_causal` 或 `schedule_frontier_too_large` 拒绝，MUST NOT pending |
| target admission | 被引用 Event 的**明文 envelope**：`realm_id`、`kind`、target ref | 引用 Event 尚未到达时按 [`event-and-patch.md` §4.3.1](./event-and-patch.md) 的 `dependency_missing` 保持 pending；已到达但 Realm / kind / target 不符时拒绝 |
| basis 有效性 | 需要读取 Calendar 子树明文：该 revision 是否真的改动了 schedule、整组 refs 是否等于 authoring 时可见的 frontier | **不是** admission 条件，只在授权投影中判定，见 §9 的 `unresolved_basis` / `stale_orphaned` |

Envelope 在 E2EE 下同样是明文，因此 target admission 不构成解密要求；只有第三层需要明文 schedule，故它 MUST 留在投影侧。服务端 MUST NOT 因为自己恰好能读明文 schedule 就在 admission 阶段追加第三层判定——那会让 E2EE 与 plaintext Realm 分叉出两套 accepted set。

### 8.2 response 与隐私

`response` / `encrypted_response` 是 oneOf 互斥、必居其一的两个分支，其合法性由目标 Strand effective scope 的 **encryption floor 唯一判定**：

- floor 为 `e2ee_required` 时只有 `encrypted_response` 合法，出现明文分支即 `schema_violation`；
- floor 允许 plaintext 时两分支均可，但明文 response 需要**双重授权**，缺任一侧 MUST 返回 `unsupported_feature`：Realm policy 侧在 `event-payload.schema.json#/$defs/plaintext_data_class` 的封闭枚举中授予 `rsvp_response`，服务侧在 ServiceDescribe 的 `plaintext_visibility.data_classes` 中声明同一 `rsvp_response`。只有 ServiceDescribe 单侧声明不构成合法授权；
- floor 为 `e2ee_required` 但部署拿不到 scope encryption key 时 MUST 返回 `unsupported_feature`，MUST NOT 静默降级为明文分支。

实现 MUST NOT 用 Calendar 专属开关覆盖 scope floor；v1 不存在"Realm policy 例外允许 plaintext RSVP comment"这一说法。

明文分支的 `response` 与 `encrypted_response` 解密后的 plaintext 共用同一封闭 schema `rsvp_response`：`{status, comment?}`。`status` 是封闭集 `accepted | declined | tentative`，未知值 MUST `schema_violation`；`comment` 若出现 MUST 复用 `arkret_short_text`、非空、最多 2000 code points，空回应通过省略字段表达。**`status` 与 `comment` 始终共享同一个加密边界**，"status 明文 + comment 密文"不是合法形态。

`encrypted_response` MUST 使用目标 Strand effective scope 的既有 encryption profile / key epoch。其 `content_type` 由 schema 以 `const` 固定为 `application/vnd.arkret.calendar-rsvp-response+json`（`event-payload.schema.json#/$defs/rsvp_encrypted_response`），使 receiver 能把该 ciphertext 唯一路由到 `rsvp_response` 一个解密 schema；携带其它 `content_type` MUST `schema_violation`。MUST NOT 为 RSVP 引入服务端可读的旁路 key。

`event_ref`、`occurrence`、`schedule_basis_refs`、responder actor 与 ciphertext size 仍是 routing-visible metadata，MUST 进入 privacy disclosure 与对应向量。实现 MUST NOT 用 `strand_content`、`profile_private_field` 或自由文本 notes 覆盖 RSVP 语义。

### 8.3 收敛

RSVP projection 按 accountable actor 对 `(event_ref, occurrence)` 使用 `mv_register` 收敛；cell subject 固定为 [`encoding.md` §9.5.2](../conformance/encoding.md) 的 `[payload.event_ref, payload.occurrence, envelope.actor_id]`。`schedule_basis_refs` 不进入 subject，但 MUST 进入 cell value。

registry 为该 cell write 登记 `effect_projection = set(payload.entry)`：**整个 entry** 是 lattice set value，因此每个 head 都独立携带 basis 与 response。receiver MUST 从 Event payload 重算 reducer projection；无法唯一投影、写目标数量错误或投影值与 payload entry 不一致，MUST 以 `reducer_projection_failed` 拒绝整个 Event。Event wire 不携带 reducer write。

同一 responder 的因果后继 RSVP 支配旧 head；真正并发且 entry 不同的 RSVP MUST 暴露多个 heads，直到该 actor 以观察到这些 heads 的后续 RSVP 显式解决。并发 join 的结果 MUST NOT 由 HLC、`created_at`、`event_id` 或到达顺序选边。只有整个 entry canonical bytes 相同的重复写才 MAY 作为 value-level no-op；相同 plaintext 经随机化加密后通常不是 byte-equal，canonical CBA MUST NOT 假装已解密去重。

`ak.rsvp.set` 只表达回应，不修改 Strand schedule，不创建 attendees，也不赋予访问权。

### 8.4 Admission

**admission 输入边界（normative）**：服务端 admission MUST 只使用 (a) 本 Event 自身的 shape、(b) Event envelope 的明文字段、(c) reducer 拥有的对象顶层字段（`state`、`schema_refs`、`realm_id` 等），以及 (d) capability / policy 状态。它 MUST NOT 使用任何需要读取 Calendar 子树明文的事实。这样 E2EE Realm 与 plaintext Realm 对同一组 Event 产生**逐项相同**的 canonical accepted set；需要明文的判定一律下沉到 authoring client 的前置条件与 §9 的授权投影。

据此，`ak.rsvp.set` 的服务端 admission predicate 是：

- `event_ref` MUST 解析到同 Realm 的 Strand，且该 Strand `state=active`、`schema_refs` 激活 Calendar schema。这三项都是顶层明文字段，E2EE 下同样可判定；
- capability resource MUST 覆盖该精确 Strand / effective scope。**attendee 身份不自动授予 `ak.rsvp.set`**：持有显式 capability 才是授权真源；反之，持有精确 capability 的非 attendee 允许 RSVP，因为 attendees 是 schedule 数据而非授权真源。产品若只允许 attendees 回应，应通过 grant materialization / profile policy 实现，MUST NOT 在 reducer 中暗加身份判断；
- `occurrence` MUST 过 canonical 语法校验（纯语法，不需要 schedule）；
- `entry.schedule_basis_refs` 按 §8.1 的三层表处理——shape admission 直接拒绝，target admission 在引用 Event 未到达时 `dependency_missing` pending，basis 有效性不进 admission；
- target 不存在、不可见、跨 Realm、非 Calendar、非 active 与 capability denied 的**对外**错误 MUST 服从既有反枚举策略；内部 reason code 可以更细，但 MUST NOT 形成 target existence oracle。

下列判定**明确不属于服务端 admission**，因为它们都需要 Calendar 子树明文：

| 判定 | authoring client 侧 | 投影侧 |
| --- | --- | --- |
| `calendar.status=cancelled` | MUST 拒绝构造新 RSVP（`calendar_event_cancelled`），历史 projection 保留 | 已存在的 RSVP 继续按 §9 显示，取消后到达的新 head 标注为对已取消事件的回应 |
| schedule 未 `settled` | MUST 拒绝构造 RSVP（`calendar_schedule_unsettled`） | 该 head 按 §9 的 basis 轴归类 |
| 该 occurrence 当前是否存在 | SHOULD 只对展开得到的 canonical key 构造 RSVP | 按 basis 判定 `current` / `stale_orphaned` |
| 非 recurring Calendar 携带非 null occurrence | MUST 拒绝构造（`rsvp_occurrence_not_canonical`） | 该 instance head 不参加有效 RSVP fold，归入 diagnostics=`non_recurring_occurrence`；不得影响 `occurrence=null` 的 base head |

服务端 MUST NOT 因为自己恰好能读明文 schedule 就把上表任一行提升为 admission 条件。

## 9. RSVP 投影

授权实现 MUST 能从已授权事件集本地计算 `CalendarRsvpProjection`；profile 不要求新增远端 Calendar API。

每个 head 沿**两条正交轴**分类，二者都通过才可参加 effective response；任一轴不通过的 head MUST 单列并保留审计。projection 只处理已被 accept 的 Event，因此空 / 重复 / 未排序 basis 与非 canonical occurrence 不会出现在这里——它们已在 §8.4 的 shape admission 被拒。

| 轴 | 取值 | 参加 effective response |
| --- | --- | --- |
| basis 轴（沿 schedule revision DAG / frontier 判定） | `current` | 是 |
| | `effective_needs_reconfirmation` | 是，但 MUST 标注需重新确认 |
| | `stale_orphaned`（identity-affecting 修改后的旧 instance head） | 否 |
| | `unresolved_basis`（任一 ref 不可解析、不可见、或不在目标 Strand 的 schedule revision DAG 上） | 否 |
| response 轴（按 §8.2 分支取值后校验） | `resolved` | 是 |
| | `response_invalid`（解密认证失败，或 plaintext 不满足 `rsvp_response`） | 否 |
| | `encrypted_unresolved`（缺 key） | 否，且 MUST NOT 伪造 status |

规则：

1. basis 轴 MUST 按上表判定，MUST NOT 猜测；无法判定即 `unresolved_basis`。
2. 若存在可参加的 instance heads，则 effective response 只取 instance heads；否则回退到 `occurrence=null` 的可参加 series heads。
3. instance 与 series heads MUST NOT 做 union，避免把 fallback 与 override 误显示成并发冲突。
4. canonical projection 原样暴露所有 heads。读取端先验证 envelope，再按分支取 response（`encrypted_response` 解密后、`response` 直接），均按同一 `rsvp_response` schema 校验，得到 response 轴取值。
5. 对两轴均通过的 heads，若完整 `(schedule_basis_refs, resolved_response)` 不同则 `resolution_state="conflict"`；若完整 plaintext 相同，只 MAY 合并展示，MUST NOT 删除 canonical heads 与 provenance。MUST NOT 仅凭 ciphertext 不同宣称用户回应冲突。
6. 被排除的 heads MUST 连同其排除轴与原因一并暴露，供 UI 解释"为什么这条回应不算数"。
7. archived / redacted / `calendar.status=cancelled` 目标的 projection 状态与历史 RSVP 显示规则 MUST 明确；redacted target MUST NOT 继续暴露 roster 或 response 内容。
8. projection 输出 MUST 受与 Calendar Strand 相同的 effective scope / history visibility 约束，MUST NOT 用 RSVP 存在性泄露不可见事件或 attendee 身份。

## 10. Schedule notification

Calendar 的 notification 派生是 **server 侧职责**，由独立 profile `ak.profile.calendar_notification_dispatch.v1`（role=`server`）承载；`ak.profile.calendar_event.v1`（role=`client`）只要求生产、验证、展开与本地投影。一个 profile MUST NOT 同时标注 server 与 push 两种 role；provider 投递继续由既有 Push Gateway blind / visible profile 约束，Calendar server profile 只产生最小化 notification 或 wakeup intent。

Calendar schedule 变更通过 `ak.strand.update` 修改 §2 字段。`metadata.fields.calendar` 的 `start` / `end` / `timezone` / `tzdb_version` / `all_day` / `status` / `recurrence` / `location` / `call_id` / `attendees` 都是 schedule-relevant field；这组字段不属于 core notification。

1. plaintext schedule 的 receiver 候选集是 `pre_state.attendees ∪ post_state.attendees ∪ assigned_to ∪ watch_all`，使被移除但仍有 scope 读取权的 attendee 也能获知变更。哪些字段变化真正触发通知由 §6 的 significant-change 表决定——特别是 `tzdb_version` 只在派生 instant 或 end 实际变化时触发，仅仅重签同一结果 MUST NOT 产生通知。
2. 最终 MUST 按 post-state access / history visibility、mute / block / DND / push rule 过滤，沿用 [`private-objects.md` §3.6](./private-objects.md#36-schedule-notification-派生) 的"生成前过滤"语义。失去访问权者 MUST NOT 收到 notification、stub 或 push wakeup；实现 MUST NOT 把 DND 只解释为 provider transport filter。
3. encrypted schedule MUST NOT 为通知扩大解密权：服务端不能从密文推导 attendee diff，也 MUST NOT 把普通 opaque metadata update 谎称为已验证的 schedule notification。它只能按可见的 assigned / watch 关系发送 profile 定义的 blind wakeup，由授权客户端解密后本地派生 schedule inbox。若要让服务端识别 schedule change，MUST 另有显式、签名、最小泄露且带负向量的 routing hint。
4. 去重键是 `(actor_id, source_event_id, notification_kind=schedule)`；同一 patch 同时改多个字段只产生一条 notification。
5. Calendar attendees 是 receiver set 输入，不是访问权真源。RSVP 变更默认不产生 schedule notification；RSVP 自身的 UI 状态由 §9 的投影展示。
6. `call_id` 是不扩大访问权的软引用；可解析时 MUST 同 Realm / effective scope，不可见或不存在 MUST NOT 泄露通话状态。

## 11. 一致性与非目标

两个 profile 的 fixture **必须分开**，因为 [`conformance-suite.md` §2](../conformance/conformance-suite.md) 的向量适用性闭包规定profile 的认证集合包含其 `required_fixtures[]` 所映射向量的并集：client profile 要求 [`calendar-rsvp-fixture.json`](../../artifacts/fixtures/calendar-rsvp-fixture.json)（§1–§9 的 12 条向量），server notification profile 只要求 [`calendar-notification-fixture.json`](../../artifacts/fixtures/calendar-notification-fixture.json)（§10 的 1 条向量）。若让 server profile 引用 client fixture，它会被闭包规则要求通过 recurrence authoring 与 RSVP 投影等它根本不声明的向量，声明块自身即不可满足。只有 submit / scan endpoint 可达而未通过对应向量的实现 MUST NOT verified-claim 任一 profile。局部实现只 MAY 逐项列入 `implemented_features` / `experimental_features`。

v1 明确不包含下列能力；它们是 non-goal / unsupported extension，未实现时 MUST NOT 用"完整日历系统"表述 profile 能力：

- UI 月 / 周 / 日视图、拖拽或甘特图布局；
- free/busy 与会议室资源预订；
- iCalendar / CalDAV / JMAP Calendar 导入导出；
- 提醒器 / 闹钟 / 到点通知；
- recurring instance override、单次取消或改期；
- 外部邮件邀请与 iTIP / iMIP。

若产品目标需要其中任一项，MUST 新增独立 profile / schema / vector，MUST NOT 扩大当前字段的隐含语义。
