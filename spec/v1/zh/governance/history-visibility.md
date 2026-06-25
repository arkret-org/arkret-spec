---
title: History Visibility and Preview Policy
status: candidate
normative: true
stability: v1
updated: 2026-06-10
see_also:
  - ../discovery/discovery-directory.md
  - ../discovery/object-addressing.md
  - ../crypto-media/encryption-and-audit.md
  - ../crypto-media/device-lifecycle.md
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按
[conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标与边界

`history_visibility` 只回答一个问题：某个 reader 对某个历史 Event range 是否具备读取资格。它不决定资源能否被发现、不决定能否加入，也不替代 capability、redaction、retention、E2EE key material 或 `plaintext_visible_services`。

实现 MUST 对每次历史读取、backfill、preview、search / projection 展开、key share 和 federation fanout 分别执行下列 gate：

1. **Discoverability / reference disclosure**：caller 是否可以知道目标存在。
2. **Read capability / current service authority**：caller 或服务是否能调用对应读取 surface。
3. **Event-time history visibility**：目标 Event 在其 CBA basis `T0` 下是否对该 reader class 可见。
4. **Current safety policy**：当前 redaction、erasure、retention、ban/remove、legal hold、plaintext-visible service 和 anti-enumeration policy 是否允许继续披露。
5. **Cryptographic availability**：E2EE scope 下是否存在被 policy 授权的 Welcome、epoch state 或 history key share。

通过 `history_visibility` 不授予解密密钥。E2EE Realm 中，reader 即使在第 3 步通过，也只能得到密文、stripped metadata、`decryption_pending` 或 `decryption_failed` 占位；只有第 5 步通过后才能显示明文。

## 2. 时点模型

历史可见性按 Event 的 CBA basis `T0` 判定。DataEvent 的 `T0` 是其 `seal_ref` 指向的控制面 Seal view；Control Move 的 `T0` 是其 `seal_basis` 指向的控制面 view。实现 MUST NOT 使用本地到达顺序、wall clock 或 pending Control Move 判定历史可见性。

Reader 的成员时点：

| 名称 | 定义 |
| --- | --- |
| `invite_frontier(reader)` | 与 reader 当前生效成员资格**因果相连**的那次有效 `ck.member.state{membership=invite}`（或等价 invite accept / claim）所确立的 accepted Seal view；被 revoke / expire / reject 后失效。reader 历史上若有多次 invite / revoke，`invite_frontier(reader)` 取**导致其当前 invited / joined 状态的那一次** invite 的 frontier，而非任意一次历史 invite——已失效或与当前成员资格无因果链的旧 invite frontier MUST NOT 被采用。 |
| `join_frontier(reader)` | 与 reader 当前生效成员资格**因果相连**的那次有效 `ck.member.state{membership=join}`（使 reader 成为 active member）所确立的 accepted Seal view。leave→rejoin 场景下 reader 可能有多次 join，`join_frontier(reader)` MUST 取**确立其当前 active 成员资格的那一次** join 的 frontier，而非任意一次历史 join——与当前成员资格无因果链的旧 join frontier MUST NOT 被采用（与 `invite_frontier` 同口径，避免并行分叉下放宽 join 前历史）。 |
| `remove_frontier(reader)` | 与 reader 当前非成员状态**因果相连**的那次有效 leave / ban / remove / account deactivation cascade（使 reader 不再是 active member）所确立的 accepted Seal view；取导致其当前状态的那一次，已被后续 rejoin 取代而与当前状态无因果链的旧 remove frontier MUST NOT 被采用。 |

一个 Event `E` 的 `T0` 如果包含 `join_frontier(reader)` 且不包含之后的 `remove_frontier(reader)`，则 reader 在 `E` 的 `T0` 为 joined。类似地，`T0` 包含有效 invite frontier 且未包含撤销 frontier，则为 invited。

Current read-time member state 只决定服务是否可以继续提供 server-mediated backfill / key share。它不要求客户端删除已合法同步、已验证且未被 redaction / erasure 覆盖的本地历史。

## 3. `history_visibility` 语义表

下表是 v1 的规范语义。每个 Event 使用其 `T0` 下 effective `ck.realm.history_visibility` 值；Circle（[`../models/circle.md`](../models/circle.md)）scope 使用父 Realm **floor** 与 Circle visibility 的更严格者。这里的 **floor** 指父 Realm 在该 `T0` 下 effective `history_visibility` 所确立的**最严格下界**——按本表从宽到严的序 `world_readable > shared > invited > joined > restricted`，Circle effective visibility MUST NOT 宽于该下界；Circle 只能取等于或更严格的值，绝不能借自身设置放宽父 Realm 的历史可见性。

| 值 | Event-time eligibility | 加入前历史 | invitee preview / read | server-mediated removal 后 backfill | E2EE key material |
| --- | --- | --- | --- | --- | --- |
| `world_readable` | 任何通过 discoverability / reference disclosure 的 reader MAY 读取该 Event 的授权视图。 | 允许读取该值生效期间的历史。 | MAY 按 preview policy 返回 stripped state 或历史 stub；MUST NOT 自动披露成员列表 / policy 原文。 | removal 后仍 MAY 读公开 projection（该可见性不依赖成员资格，故 remove_frontier 不收回该读取资格）：默认 MAY 返回 redacted / public projection；明文 backfill 受 current safety policy。 | 不自动发 key；必须由 `ck.realm.history_sharing_policy` 明确允许 public / token holder key share，否则只返回密文或占位。 |
| `shared` | 当前 active Realm member MAY 读取该值生效期间的历史，即使 Event 早于其 `join_frontier`。 | joined 后可读 join 前历史。 | invited 但未 joined 的 reader 默认不能读正文历史；只能按 preview policy 看 stripped state。 | 默认 DENY 给非 active member；policy MAY 允许对 T0 可见历史作受审计恢复。 | joined 后可按 history sharing policy 获得旧 epoch key；无 policy 时不能靠 visibility 自动补 key。 |
| `invited` | reader 在 Event 的 `T0` 已处于 invited 或 joined 状态时 MAY 读取。 | joined 后最多回到与当前成员资格因果相连的那次 invite frontier（§2 定义）；不能读该 invite 前历史。 | invited reader MAY 读取 invite frontier 之后、policy 允许的 stripped state / history range。 | 默认 DENY；policy MAY 允许 T0 可见历史恢复。 | key share range MUST 从 invite frontier 起算，且必须写入 membership frontier digest。 |
| `joined` | reader 在 Event 的 `T0` 已处于 joined 状态时 MAY 读取。 | 不允许读 join 前历史。 | invitee 未 joined 时不能读正文历史，只能看 preview policy 允许的 stripped metadata。 | 默认 DENY；policy MAY 允许 T0 joined 且 current policy 仍允许的恢复。 | Welcome 只授予 join 后 future epoch；join 前 key share MUST 被拒。 |
| `restricted` | 不由 enum 自身定义；MUST 由 effective `ck.realm.history_sharing_policy` 中的 `restricted_rules[]` 显式判定。 | 仅按匹配 rule。 | 仅按匹配 rule。 | 仅按匹配 rule。 | 仅按匹配 rule；命中 read rule **不自动授予 key**——key share 还要求本次请求所用的 key 来源在该 rule 的 `key_sources` 内（见 §3.1 / §6）。任一判定失败的 fail-closed 行为见 §3.1 末尾集中声明。 |

Reducer MUST 拒绝把 effective Realm 或 Circle history visibility 设置为 `restricted`，除非同一 CBA basis 或同一 ordered submit batch 的前序 Event 已接受一个有效 `ck.realm.history_sharing_policy`。拒绝原因 SHOULD 使用 `history_sharing_policy_missing`。policy 存在但未覆盖目标 scope / audience / range 时的 fail-closed 行为见 §3.1 末尾「`restricted` fail-closed 集中声明」。

**`world_readable` removal 后 backfill 与 §2 "current read-time member state" 的关系（normative，消歧）**：§3 表 `world_readable` 行声明"removal 后仍 MAY 读公开 projection，remove_frontier 不收回该读取资格"，这与 §2 "current read-time member state 只决定服务是否可以继续提供 server-mediated backfill / key share" 不冲突，二者作用面不同：

- **reference / 公开 projection 读取资格**：`world_readable` 的 event-time eligibility 不依赖成员资格（任何通过 discoverability / reference disclosure 的 reader 即可读授权视图），故被 remove 的 reader 对该公开 projection 的读取资格**不被 `remove_frontier(reader)` 收回**——这是 enum 语义层面的可见性。
- **server-mediated backfill 仍受 current safety policy 独立 gate**：上述读取资格成立**不**等于服务必须继续提供 server-mediated 明文 backfill。§1 gate 4（current safety policy）对每次 backfill 独立求值——即便 `world_readable` 使 event-time eligibility 与 reference disclosure 通过，当前 ban / remove / redaction / erasure / retention / legal-hold safety policy 仍 MAY 独立拒绝继续向该已 remove reader 提供 server-mediated 明文 backfill（返回 redacted / public projection 或 `policy_denied`）。即：可见性 gate（gate 3）放行 ≠ safety policy gate（gate 4）放行；被 ban/remove 的 reader 仍可读已落库公开 projection，但服务的明文 backfill 交付可被 gate 4 收紧。这与 §2 "current read-time member state 决定服务是否继续 server-mediated backfill" 完全一致。

### 3.1 `restricted_rules[]` 结构

`restricted` 的判定语义由 effective `ck.realm.history_sharing_policy` 的 `restricted_rules[]` 显式承载；其 canonical wire schema 为 [`event-payload.schema.json`](../../artifacts/schemas/event-payload.schema.json) 的 `$defs/history_sharing_restricted_rule`（`additionalProperties:false`）。本节给出 v1 normative 字段约束：

| 字段 | 必填 | 类型 | 语义 |
| --- | --- | --- | --- |
| `rule_id` | yes | `string`（`^[a-z][a-z0-9_]{0,63}$`） | 规则稳定 id；同一 `restricted_rules[]` 内 MUST 唯一，供审计与 key share diagnostic 关联。 |
| `receiver_classes` | yes | `array<enum>`（≥1，唯一） | 本 rule 覆盖的接收者类别，取 `active_member` / `invited` / `removed_t0_visible` / `world_readable_requester` / `preview_token_holder`。 |
| `allowed_history_visibility_values` | yes | `array<history_visibility_value>`（≥1，唯一） | 命中本 rule 时允许的 history visibility 取值集（取自 §3 五值）。 |
| `range` | yes | `enum(all_visible_at_t0, since_invite, since_join, bounded_epoch_range)` | reader 可读 / 可获 key 的历史下界范围；`bounded_epoch_range` 配合 `max_epoch_span` 限定 epoch 跨度。 |
| `max_epoch_span` | no | `integer`（≥1） | 仅 `range=bounded_epoch_range` 时有意义，限定允许的最大 epoch 跨度。 |
| `key_sources` | yes | `array<enum>`（≥1，唯一） | 允许的 history key 来源，取 `own_device` / `verified_member_device` / `key_backup` / `archive_node` / `recovery_service`。read 与 key share 的区分由本字段（是否含可交付 key 的来源）+ §6 流程承载，而非单独的 effect 开关。 |
| `history_scope` | no | `object`（`{ kind: realm\|circle, circle_id? }`） | 限定本 rule 适用的 scope（整 Realm 或具体 Circle）。 |
| `audit_required` | no | `boolean`（默认 `true`） | 命中本 rule 的读取 / key share 是否要求审计留痕。 |

匹配语义：reader 对某 Event 的 restricted 资格按 `restricted_rules[]` 逐条求值——rule 的 `receiver_classes` 命中 reader 在 `T0` 的类别、Event 落在该 rule 的 `range`（及可选 `history_scope`）界定的历史范围内、且请求的 visibility 落在 `allowed_history_visibility_values` 内即视为通过；key share 还要求本次请求所用的 key 来源在该 rule 的 `key_sources` 内（见 §6）。无任何 rule 命中时 MUST fail closed（见下方集中声明）。多条 rule 命中时取并集（最宽 `range` / `allowed_history_visibility_values` / `key_sources`），但仍受 §3 表与父 Realm floor 约束，绝不放宽到比 enclosing scope 更宽。

**`restricted` fail-closed 集中声明（normative）**：上述所有 `restricted` 判定的校验主体是执行读取 / key share 的服务（reducer 或 key source）；校验时点为每次读取 / backfill / key share 请求。任一判定失败 MUST fail closed——无匹配 rule 时返回 `history_not_visible`，policy 未覆盖目标 scope / audience / range 时返回 `policy_denied`，缺少 key share rule 或 proof 时 MUST withhold key material。本节其它处（§3 语义表 `restricted` 行、§3 末尾段落）对 restricted 的描述均引用本声明，不再各自重述 fail-closed 行为。

## 4. Preview / Peek

Preview 是读取授权的一种受限投影，不是加入、写入或完整历史读取。Cokret v1 区分四类 preview：

| 类别 | 典型 surface | 可披露内容 |
| --- | --- | --- |
| directory card | Directory search / organization listing | title、summary、avatar、owning organization、join rule、bucketed member count 等最小字段。 |
| stripped state | invite / restricted proof / exact resolve | join 前渲染所需的 stripped metadata，不含正文历史。 |
| history stub | preview token / invited preview | Event id、kind、timestamp bucket、redaction reason、payload digest、必要 sender display stub；不含正文。 |
| history snippet | 明文 Realm 且 preview policy 显式允许 | 有界数量的最近消息或摘要；MUST NOT 用于 E2EE plaintext，除非独立 audited plaintext-visible service profile 明确声明。 |

`ck.realm.preview_policy` 是 v1 active Realm policy component，用于声明 preview 的 audience、字段、历史范围和 token 要求。Directory `ck.realm.discovery.preview` 只表达目录卡片与 stripped state 的最小形态；一旦 preview 会返回历史 stub、history snippet、object preview 或 token-scoped preview，resolver MUST 同时验证 effective `ck.realm.preview_policy`。

Preview policy MUST 满足：

- `history_snippet` 只允许在 `encryption_profile="none"` 或对应 content 明确为 plaintext public content 时返回正文片段。
- E2EE Realm 的 preview MUST NOT 返回 decrypted message body、attachment plaintext、可逆 search token 或 emoji / reaction 明文；只能返回 stripped metadata、密文 envelope、不可逆 digest 或 policy 明确允许的 redacted stub。
- preview token MUST audience-bound、target-bound、短 TTL、可撤销；目标绑定规则见 [object-addressing.md](../discovery/object-addressing.md) §4.2。
- 未授权 preview、不可发现 target、token mismatch、过期 token 和不存在 target 对外 MUST 返回不可区分的 `not_found`。
- Preview MUST NOT 披露 `join_candidates[]`，除非同一 caller 已按 discovery / invite / restricted proof 获得 join routing 权限。

## 5. Public Plaintext Realm

协议允许 `encryption_profile="none"`、`discoverability=public`、`join_rule=public`、`history_visibility=world_readable` 的 Realm。该组合表示“公开可发现、可自助加入、历史授权视图可世界读取”，但仍不表示：

- 任意服务可以保存、索引、导出或再分发私有正文。
- 成员列表、policy 原文、hidden relation、Circle、delivery binding、设备列表或组织治理链自动公开。
- 受托 search / projection / push / blob preview 服务可以绕过 `plaintext_visible_services`。

当 Realm 的 content 被声明为 public content（例如 `history_visibility=world_readable` 且 preview/export policy 允许 public content processing）时，服务 MAY 在其公开服务描述中声明 public indexing；否则即使 Realm 是 plaintext，服务接收正文、全文索引、embedding、notification summary 或 attachment preview 仍 MUST 满足 [service-surface.md](../sync/service-surface.md) §5.4 / §6.5 的 `plaintext_visible_services` 边界。

实现和 UI MUST 分别展示：

- “公开可发现”（discoverability）
- “公开可加入”（join rule）
- “历史公开可读”（history visibility）
- “未端到端加密 / 服务可能接触明文”（encryption profile）

实现和 UI MUST NOT 把其中任一项简写成其它项。

## 6. E2EE 历史共享

`ck.realm.history_visibility` 只判定 Event 是否可见；`ck.realm.history_sharing_policy` 判定是否可以交付旧 epoch key / history key share。发送 `ck.realm_key.share` 前，key source MUST 同时满足：

1. 目标 Event range 在 `T0` 下通过 §3 visibility 判定。
2. effective `ck.realm.history_sharing_policy` 允许该 receiver class、scope、epoch range 和 key source。**对 `restricted` scope，命中的 `restricted_rules[]` rule 还 MUST 在其 `key_sources` 中列出本次请求所用的 key 来源（见 §3.1）——`key_sources` 未覆盖该来源时只放行读取、不授予 key**；仅满足 §3 read 判定不足以放行 key share。
3. 交付侧机制校验——对 `share_class="member_device"`，device 未撤销且通过要求的验证、current safety policy（redaction / erasure / retention / ban·remove / legal hold）未禁止继续交付、audit profile 要求的留痕、`key_scope` / `sender_device_signature` 绑定，按 [`../crypto-media/device-lifecycle.md`](../crypto-media/device-lifecycle.md) §13 的 canonical key-share 校验执行；对 `share_class="realm_recovery_key"`，按 [`../crypto-media/encryption-and-audit.md`](../crypto-media/encryption-and-audit.md) §2.10.8 的 RRK DID service 与 durability policy 校验执行。本节不再重述。

上述 1–2 是 history-visibility 本身的判定；3 引用 device-lifecycle §13 的 canonical 列表。**ban / remove / legal-hold 后 key withhold 已被该 canonical 列表覆盖**：[`../crypto-media/device-lifecycle.md` §13](../crypto-media/device-lifecycle.md) 的 current safety policy 校验项明确含 "redaction / erasure / retention / **ban·remove** / **legal hold**"（见该节 `current safety policy（redaction / erasure / retention / ban·remove / legal hold）未禁止继续向该 principal / device 交付` 条），且 §13.1 把"接收 principal/device 已处于 ban / leave / removed / account 失权态"列为**主体级拒绝**的终态 fail-closed（`not_member` / `history_not_visible`）。因此本文不重复定义这些项的扣留逻辑，以 device-lifecycle §13 / §13.1 为 canonical 真源。如果任一条件不满足，key source MUST 发送 `ck.realm_key.withheld` 或等价诊断，并使用 `history_not_visible`、`not_member`、`policy_denied` 或更具体 reason。Key source MUST NOT 因为自己持有 backup、Archive Node 副本或 service operator 权限而跳过这些检查。

本节只规定**被选中的 source 交付前必须满足的条件**；接收方如何**发现、选择并请求**一个具体 key source（policy 允许的 `key_sources` ∩ `ServiceDescribe` 声明可用的途径，按优先级，经 `ck.realm_key.request` 发起或 `key_backup` unlock 取回），见 [`../crypto-media/device-lifecycle.md`](../crypto-media/device-lifecycle.md) §13.2。

## 7. 测试向量要求

实现声明支持 `ck.profile.e2ee_client.v1`、Directory preview、或 `ck.realm.preview_policy` 时，MUST 覆盖以下行为：

- `ck.vector.history_visibility.joined_prejoin_denied.v1`
- `ck.vector.preview.token_scoped_stripped_state.v1`
- `ck.vector.history_sharing.e2ee_prejoin_key_share_policy.v1`

这些向量定义见 [conformance-vectors.md](../conformance/conformance-vectors.md)。
