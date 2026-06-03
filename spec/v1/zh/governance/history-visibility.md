---
title: History Visibility and Preview Policy
status: candidate
normative: true
stability: v1
updated: 2026-05-30
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
3. **Event-time history visibility**：目标 Event 在其 deterministic pre-state `T0` 下是否对该 reader class 可见。
4. **Current safety policy**：当前 redaction、erasure、retention、ban/remove、legal hold、plaintext-visible service 和 anti-enumeration policy 是否允许继续披露。
5. **Cryptographic availability**：E2EE scope 下是否存在被 policy 授权的 Welcome、epoch state 或 history key share。

通过 `history_visibility` 不授予解密密钥。E2EE Realm 中，reader 即使在第 3 步通过，也只能得到密文、stripped metadata、`decryption_pending` 或 `decryption_failed` 占位；只有第 5 步通过后才能显示明文。

## 2. 时点模型

历史可见性按 Event 的 deterministic effective pre-state `T0` 判定。`T0` 定义与
[encryption-and-audit.md](../crypto-media/encryption-and-audit.md) §2.3.5 一致：对 single-leaf Anchor 使用该 Event 所属 Anchor 的 pre-state；对 `open_set` / multi-leaf view 使用
[event-auth-state-resolution.md](../authz/event-auth-state-resolution.md) 的 deterministic effective anchor view。实现 MUST NOT 使用本地到达顺序、wall clock 或 pending Move 判定历史可见性。

Reader 的成员时点：

| 名称 | 定义 |
| --- | --- |
| `invite_frontier(reader)` | 最近一次有效 `ck.member.state{membership=invite}` 或等价 invite accept / claim 使 reader 成为 invited 的 Anchor frontier；被 revoke / expire / reject 后失效。 |
| `join_frontier(reader)` | 最近一次有效 `ck.member.state{membership=join}` 使 reader 成为 active member 的 Anchor frontier。 |
| `remove_frontier(reader)` | 最近一次有效 leave / ban / remove / account deactivation cascade 使 reader 不再是 active member 的 Anchor frontier。 |

一个 Event `E` 的 `T0` 如果包含 `join_frontier(reader)` 且不包含之后的 `remove_frontier(reader)`，则 reader 在 `E` 的 `T0` 为 joined。类似地，`T0` 包含有效 invite frontier 且未包含撤销 frontier，则为 invited。

Current read-time member state 只决定服务是否可以继续提供 server-mediated backfill / key share。它不要求客户端删除已合法同步、已验证且未被 redaction / erasure 覆盖的本地历史。

## 3. `history_visibility` 语义表

下表是 v1 的规范语义。每个 Event 使用其 `T0` 下 effective `ck.realm.history_visibility` 值；Circle（[`../models/circle.md`](../models/circle.md)）scope 使用父 Realm **floor** 与 Circle visibility 的更严格者。这里的 **floor** 指父 Realm 在该 `T0` 下 effective `history_visibility` 所确立的**最严格下界**——按本表从宽到严的序 `world_readable > shared > invited > joined > restricted`，Circle effective visibility MUST NOT 宽于该下界；Circle 只能取等于或更严格的值，绝不能借自身设置放宽父 Realm 的历史可见性。

| 值 | Event-time eligibility | 加入前历史 | invitee preview / read | server-mediated removal 后 backfill | E2EE key material |
| --- | --- | --- | --- | --- | --- |
| `world_readable` | 任何通过 discoverability / reference disclosure 的 reader MAY 读取该 Event 的授权视图。 | 允许读取该值生效期间的历史。 | MAY 按 preview policy 返回 stripped state 或历史 stub；MUST NOT 自动披露成员列表 / policy 原文。 | 默认 MAY 返回 redacted / public projection；明文 backfill 受 current safety policy。 | 不自动发 key；必须由 `ck.realm.history_sharing_policy` 明确允许 public / token holder key share，否则只返回密文或占位。 |
| `shared` | 当前 active Realm member MAY 读取该值生效期间的历史，即使 Event 早于其 `join_frontier`。 | joined 后可读 join 前历史。 | invited 但未 joined 的 reader 默认不能读正文历史；只能按 preview policy 看 stripped state。 | 默认 DENY 给非 active member；policy MAY 允许对 T0 可见历史作受审计恢复。 | joined 后可按 history sharing policy 获得旧 epoch key；无 policy 时不能靠 visibility 自动补 key。 |
| `invited` | reader 在 Event 的 `T0` 已处于 invited 或 joined 状态时 MAY 读取。 | joined 后最多回到自身有效 invite frontier；不能读 invite 前历史。 | invited reader MAY 读取 invite frontier 之后、policy 允许的 stripped state / history range。 | 默认 DENY；policy MAY 允许 T0 可见历史恢复。 | key share range MUST 从 invite frontier 起算，且必须写入 membership frontier digest。 |
| `joined` | reader 在 Event 的 `T0` 已处于 joined 状态时 MAY 读取。 | 不允许读 join 前历史。 | invitee 未 joined 时不能读正文历史，只能看 preview policy 允许的 stripped metadata。 | 默认 DENY；policy MAY 允许 T0 joined 且 current policy 仍允许的恢复。 | Welcome 只授予 join 后 future epoch；join 前 key share MUST 被拒。 |
| `restricted` | 不由 enum 自身定义；MUST 由 effective `ck.realm.history_sharing_policy` 中的 `restricted_rules[]` 显式判定。 | 仅按匹配 rule。 | 仅按匹配 rule。 | 仅按匹配 rule。 | 仅按匹配 rule；缺少 rule 或 proof 时 MUST withhold。 |

Reducer MUST 拒绝把 effective Realm 或 Circle history visibility 设置为 `restricted`，除非同一 Anchor pre-state 或同一 ordered submit batch 的前序 Event 已接受一个有效 `ck.realm.history_sharing_policy`。拒绝原因 SHOULD 使用 `history_sharing_policy_missing`；如果 policy 存在但没有覆盖目标 scope / audience / range，读取或 key share MUST fail closed，原因 SHOULD 使用 `history_not_visible` 或 `policy_denied`。

### 3.1 `restricted_rules[]` 结构

`restricted` 的判定语义由 effective `ck.realm.history_sharing_policy` 的 `restricted_rules[]` 显式承载；其 canonical schema 由该 policy component 在 [encryption-and-audit.md](../crypto-media/encryption-and-audit.md) 中定义，本节给出 v1 normative 的最小字段约束：

| 字段 | 必填 | 类型 | 语义 |
| --- | --- | --- | --- |
| `rule_id` | yes | `string` | 规则稳定 id；同一 `restricted_rules[]` 内 MUST 唯一，供审计与 key share diagnostic 关联。 |
| `match` | yes | `object` | reader / Event selector。最小形态 `{ reader_class, event_selector }`：`reader_class` 取 `member` / `invited` / `role:<capability>` / `claim:<claim_selector>` 之一；`event_selector` 按 Event kind、Circle scope、label 或 Anchor range 限定本 rule 覆盖的历史范围。 |
| `allow_from_frontier` | yes | `enum(join_frontier, invite_frontier, anchor_ref) \| object` | 允许读取 / key share 的下界 frontier；`object` 形式 `{ anchor_ref }` 显式锚定某 Anchor。reader 只能读取该 frontier 之后、且 `match` 命中的 Event。 |
| `effect` | no | `enum(allow_read, allow_key_share, allow_both)` | 默认 `allow_read`。`allow_key_share` / `allow_both` 才放行 §6 的 history key share；缺省不授予 key。 |

匹配语义：reader 对某 Event 的 restricted 资格按 `restricted_rules[]` 逐条求值，命中**任一** `match` 且 Event 在对应 `allow_from_frontier` 之后即视为通过；无任何 rule 命中时 MUST fail closed（reason `history_not_visible`）。多条 rule 命中时取并集（最宽 `allow_from_frontier` 与最宽 `effect`），但仍受 §3 表与父 Realm floor 约束，绝不放宽到比 enclosing scope 更宽。

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
2. effective `ck.realm.history_sharing_policy` 允许该 receiver class、scope、epoch range 和 key source。
3. receiver device 当前未撤销，且通过 policy 要求的 device verification。
4. current safety policy 未禁止向该 principal / device 继续交付。
5. audit profile 要求的 `ck.realm_key.share_audit` / `ck.audit.accessed` 已满足。

如果任一条件不满足，key source MUST 发送 `ck.realm_key.withheld` 或等价诊断，并使用 `history_not_visible`、`not_member`、`policy_denied` 或更具体 reason。Key source MUST NOT 因为自己持有 backup、Archive Node 副本或 service operator 权限而跳过这些检查。

## 7. 测试向量要求

实现声明支持 `ck.profile.e2ee_client.v1`、Directory preview、或 `ck.realm.preview_policy` 时，MUST 覆盖以下行为：

- `ck.vector.history_visibility.joined_prejoin_denied.v1`
- `ck.vector.preview.token_scoped_stripped_state.v1`
- `ck.vector.history_sharing.e2ee_prejoin_key_share_policy.v1`

这些向量定义见 [conformance-vectors.md](../conformance/conformance-vectors.md)。
