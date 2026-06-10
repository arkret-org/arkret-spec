---
title: Scalability Constraints
status: candidate
normative: true
stability: v1
updated: 2026-06-10
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [normative-language.md](./normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Cokret v1 的一致性不仅要求语义正确，也要求实现不会被合法但过大的输入拖垮。本文定义 v1 默认规模上限。实现 MAY 在私有部署中使用更低或更高限制，但对外声明互操作 profile 时 MUST：

- 在 `server/describe.limits` 暴露实际限制。
- 对超过限制的输入返回标准错误、`rejected[]` 或 `quarantine[]`，不得无界处理。
- 不得因为本地上限不同而接受会导致其他 v1 节点无法验证的 wire object。

本文的数值是 v1 wire interoperability bounds，不是产品体验目标。

凡会导致实现 MUST reject、MUST quarantine、MUST fail closed 或影响跨实现验证结果的 wire 上限，MUST 在本文登记或从本文显式引用的 profile 参数派生；纯本地性能/SLA 建议可以留在领域文档，但不得作为对端可验证的 v1 互操作上限。

## 2. 通用 Wire 上限

| 项 | v1 默认上限 | 规则 |
| --- | ---: | --- |
| 单个 canonical Event / Operation envelope | 1 MiB | 超过时 MUST reject 为 `payload_too_large` 或 `schema_violation`。正文、附件和大对象必须使用 Blob。 |
| 单次 `/_cokret/self/events` 批量提交的 Event 数 | 1,000 | 超过时 MUST 拆分请求；接收方 MAY 返回 `rate_limited` 或 `payload_too_large`。 |
| 单个 federation transaction 的 Event 数 | 500 | 超过时 MUST 拆分 transaction；接收方 MAY 返回 `rate_limited` 或 `payload_too_large`。 |
| 单次 sync / backfill / projection page 返回项 | 1,000 | 执行方 MUST enforce；客户端不得假设更大 page 可用。 |
| 单个 Event 的 `prev_refs` 数量 | 128 | 超过时 MUST reject（`schema_violation`，`reason_code=prev_refs_too_large`）或要求提交 snapshot / checkpoint 引用；数组项 MUST 去重。 |
| 单个 Event `refs[]` 中 `role="authorized_by"` 的条目数量 | 64 | 超过时 MUST reject；authorized_by refs 必须是最小授权状态集合（见 [event-and-patch.md](../models/event-and-patch.md) §2.2）。 |
| 单个 Event 的 `refs[]` 总条目数量 | 128 | 涵盖 `authorized_by` / `attestation` / `parent_event` / `after` / `recovery_capability` / `state_witness` / `inclusion_proof` 等所有 role；超过时 MUST reject（`schema_violation`，`reason_code=refs_too_large`）或拆分。 |
| 同一 `(actor_id, actor_seq, prev_frontier_digest)` sibling fork 数 | 16 | 超过时 receiver MUST quarantine 或要求 actor chain repair；见 [event-and-patch.md](../models/event-and-patch.md) §2.6。 |
| 单个 Relation / View / Morph `fields` canonical size | 256 KiB | 更大内容必须放入 Blob 或加密 payload。 |
| 关系展开深度 | 32 | Projection executor / graph query MUST enforce，跨 Realm 引用必须按 Lazy Link 截断（Lazy Link 定义见 [glossary.md](../overview/glossary.md) "Lazy Link"）。 |
| 单 actor 每毫秒 HLC 生成事件数 | 65,536（HLC logical 4 hex 段上限） | HLC wire 形态为 `<unix_ms_hex_12>-<logical_hex_4>-<node_id_hash_8>`，logical 段为 16-bit；同一 actor 在同一 ms 内最多分配 65,536 个 logical 值（`0x0000`–`0xFFFF`，即 0..65535），第 65,537 个 event 触发 HLC logical 段饱和，producer MUST 等待至下一 ms 再生成或返回本地错误 `hlc_logical_overflow`，MUST NOT wrap 或复用相同 HLC。HLC 仅作为时间线 advisory tie-breaker，不参与授权或状态收敛——饱和不影响协议正确性，只影响展示排序。[^hlc-throughput] [^hlc-logical-width] |
| 单 actor 持续吞吐建议 | ≤ 100,000 events/min | Producer SHOULD 在生产侧自我限速，避免在突发情况下饱和 HLC logical 段或下游 reducer。超过该建议持续吞吐时，actor SHOULD 拆分为多 device / 多 actor 并行，或考虑使用 batch event。 |
| HLC `hard_future_skew_ms`（硬 future drift 上限） | 300,000 ms（5 分钟） | 见 [encoding.md](./encoding.md) §7.2。HLC `unix_ms` 超本地时钟该阈值时 receiver MUST reject / quarantine。该校验是 envelope freshness / DoS guard，非授权、Lattice winner、Move precondition 或 Anchor finality 输入。 |
| HLC `expected_future_skew_ms`（软 future drift 阈值） | 30,000 ms（30 秒） | 见 [encoding.md](./encoding.md) §7.2。超该阈值但未超 `hard_future_skew_ms` 时 receiver SHOULD soft-fail / quarantine。 |
| HLC `state_event_expected_future_skew_ms`（state event 软阈值） | 默认按 `expected_future_skew_ms` | 见 [encoding.md](./encoding.md) §7.2。profile MAY 对 state event（capability / membership / policy / service binding / Realm upgrade / MLS commit 等）声明更严窗口；未声明时按 `expected_future_skew_ms` 处理。 |

[^hlc-throughput]: informative：换算约 65.5 M events/s（精确 65,536,000 events/s）单 actor 上限，仅为 65,536/ms × 1000 的派生值，**非 normative 吞吐保证**，实现 MUST NOT 以此作为容量承诺。

[^hlc-logical-width]: informative：logical 段宽度的潜在扩展属未来评估方向，不构成 v1 规范要求。

## 3. 授权与 Capability 上限

| 项 | v1 默认上限 | 规则 |
| --- | ---: | --- |
| delegation chain 深度 | 4 | 超过时 MUST deny；profile MAY 声明更低上限。 |
| 单次授权判定展开 grant 数 | 1,024 | 超过时 MUST fail closed、使用已验证 snapshot，或返回 `soft_fail` / `temporarily_unavailable`。 |
| 单个 grant 的 constraint 数 | 64 | 超过时 MUST reject。 |
| 单个 resource selector AST 深度 | 16 | 超过时 MUST reject。 |
| 高频路径 authz snapshot 最大重建延迟 | 5 秒（SHOULD，本地性能建议） | `chat_mvp`、`kanban_mvp`、`full_client` 和 `principal_server` 相关服务 SHOULD 满足。这是**本地性能 / SLA 建议**，非 wire interoperability bound——对端无法仅凭 wire object 核验本地重建是否 ≤5s，故不构成 §1 意义上的可互操作核验项。 |

当 grant / revoke / claim status / policy component / membership frontier 变化时，受影响的 capability snapshot MUST 立即标记 stale。stale snapshot 不得继续用于新的写入 allow 决策。

## 4. Move / Anchor / Lattice 上限

| 项 | v1 默认上限 | 规则 |
| --- | ---: | --- |
| 单个 Move canonical size | 1 MiB | 超过时 MUST reject 为 `payload_too_large` 或 `schema_violation`。 |
| 单个 Move 的 `preconditions + effects` 数 | 256 | 超过时 MUST reject；需要拆成多个 Move 或使用 higher-level batch operation。 |
| 单个 Anchor 新增 Move 数 | 1,000 | 超过时 MUST 拆分 Anchor；接收方 MAY 返回 `rate_limited` 或 `temporarily_unavailable`。 |
| Anchor DAG leaf 数 | 实现声明 | 超过时 SHOULD 请求或生成 signed compaction Anchor；查询可使用 deterministic effective anchor view。 |
| 单次 Lattice join CPU / wall-clock 预算 | 实现声明 | 服务 MUST 在 `server/describe.limits` 暴露；超出时返回可恢复错误或使用已验证 state_root + inclusion proof。 |
| 单次 Lattice join 内存预算 | 实现声明 | 服务 MUST 暴露，超出时返回可恢复错误而不是 OOM。 |

Move / Anchor fallback 不得选择本地接收顺序或数据库 ID。Snapshot 必须有 Anchor inclusion proof、state_root、frontier 和 chunk digest。对缺失、不可达或高成本 `refs` 的 backfill，接收方 MAY 在预算耗尽后把 Move 保持 pending 或返回 `dependency_missing`、`temporarily_unavailable`；不得在同步写入路径无界递归展开。

### 4.1 Progressive Move / Anchor Backfill Profile

实现声称支持 `full_client`、`e2ee_client` 或 `principal_server` profile 时，MUST 支持渐进式 Move / Anchor 恢复，而不是要求一次性拉完整历史：

| 项 | v1 默认上限 / 建议 | 规则 |
| --- | ---: | --- |
| 单轮 targeted backfill page | 256 objects | 客户端 SHOULD 优先拉缺失 Move、Anchor predecessor、critical `refs` 的最小闭包，再扩大范围。 |
| 单 Realm 后台 dependency 队列 | 4,096 refs | 超过时 MUST 合并去重、分批处理，或切换到 state_root-assisted recovery。 |
| snapshot-assisted recovery 触发 | DAG leaf 过多、join 预算耗尽或本地预算耗尽 | 必须验证 Anchor signer authority、frontier、state_root 和 chunk digest。 |
| 交互式恢复首屏预算 | 2 seconds SHOULD | 预算耗尽后 MAY 返回 read-only partial view + `anchor_incomplete`，并继续后台恢复。 |
| retry backoff | 指数退避，有上限 | 响应 SHOULD 带 `retry_after_ms`、`next_retry_at`、缺失 ref 和可用 source。 |

渐进恢复阶段：

1. **Anchor probe**：先查询 Realm Anchor leaves、可用 snapshot manifest 和缺失 ref 的 source。
2. **Targeted dependency fetch**：按缺失 Move、Anchor predecessor 与 critical refs 拉最小闭包。
3. **State-root-assisted recovery**：闭包超过预算时，改用最近可验证 state_root / snapshot 作为 base，再回放其 frontier 之后的 Move。
4. **Read-only partial state**：仍有缺口时，客户端 MAY 展示已验证 Anchor view 的只读 projection，并显式标记 `anchor_incomplete`。
5. **Write revalidation**：任何新 Move 必须在提交前以最新 Anchor view 重新验证 preconditions；不得继承 partial view 的乐观允许结果。

长期离线设备重新上线时，服务端 SHOULD 支持分页返回 Anchor DAG 诊断和 snapshot candidate，避免客户端在写入路径递归拉取数千个 Move / Anchor。

## 5. Space / Relation / View 上限

> **"active" 计数口径（normative，适用本文全文）**：本文各上限中的 **active** 计数 MUST 仅计入当前生效对象，**MUST NOT** 计入 tombstoned、archived、hard-erased、或经 `ck.flow.tracks.update` 关闭（track-disabled，见 §7）的对象。判定上限是否触发以该口径为准；archived / track-disabled 对象在 snapshot 中以 stub 保留（见 §7）但不计入 active 上限。

| 项 | v1 默认上限 | 规则 |
| --- | ---: | --- |
| 单 Realm active Space 数 | 5,000 | 超过时 Realm projection MUST paginate；建议拆分为多个 Realm 或使用嵌套 Space。 |
| 单个 Board Space active List Space 数 | 500 | 超过时 Board projection MUST paginate 或 require filtered View。 |
| 单个 List Space active Flow item 数 | 10,000 | Projection MUST paginate；drag / reorder 仍按 rank + deterministic tie-break。 |
| Space 嵌套深度 | 8 | 超过时 reducer MUST reject `ck.space.parent`；防止任意深度的容器树拖累查询性能。 |
| 单个对象 active Relation 数 | 10,000 | Projection executor MUST paginate，不能要求客户端一次性拉全。 |
| 单个 View projection page | 1,000 items | View cursor MUST 绑定 authorization context 和 frontier。 |
| rank 长度 | 128 chars | 超过时 MUST reject，见 `encoding.md`。 |
| 单个 Calendar Event attendees 数 | 1,000 | 超过时 MUST reject 或要求拆分会议 / 日程实例；attendees 必须按 actor / handle / resource key 去重。 |
| 单次 recurrence expansion 返回 occurrence 数 | 10,000 | 超过时 MUST paginate、截断为带 cursor 的 page，或返回 `limit_exceeded`；不得无界展开 RRULE。 |
| 单个 File Transfer `recipient_device_ids` 数 | 1,000 | 超过时 MUST reject 或拆分 transfer；每个 device key wrap 必须保持独立可验证。 |

Board position edge 的 canonical key 是 `(board_space_id, flow_id)`。同一 key 下多个 active edge 只允许 reducer 选择一个 winner，并记录 losers；View projection MAY 暴露 loser conflict records，但不得把同一 Flow 渲染成多个主位置。

## 6. E2EE 与设备上限

| 项 | v1 默认上限 | 规则 |
| --- | ---: | --- |
| 单 principal active device 数 | 100 | 超过时 Device / Key Server MAY require admin approval or device cleanup。 |
| 单 MLS commit 绑定的 `membership_frontier` refs | 128 | 超过时 MUST 使用签名 state root / snapshot reference。 |
| KeyPackage 有效期 | 1 hour（下限）– 30 days（默认上限） | 更长有效期必须由 profile 明确声明。接收方 MUST NOT 使用已过期 KeyPackage 建立新 MLS 会话（过期复用是已知 E2EE 风险）；签发方 SHOULD NOT 签发有效期短于 1 小时的 KeyPackage（避免正常 join 流程内即过期）。实现 MAY 声明一个不超过该有效期 10% 的接收侧时钟偏差宽限窗口。 |
| to-device 队列 TTL | 24 hours（默认最大值） | `DeviceMessageEnvelope.expires_at` 不得晚于当前 service / Realm / profile TTL 上限；服务端 MUST 拒绝缺失、已过期、早于 `sent_at` 或超限的消息。高安全 profile SHOULD 声明更短 TTL。 |
| KeyPackage claim 限速 | 60 seconds 内最多 5 次 / `(requester_service_did, target_principal_id)` | 超过限额时对外仍使用反枚举响应（`claim_failed` 或通用 rate-limited envelope），不得泄露目标存在性；服务端内部审计 reason 记录为 `keypackage_claim_rate_limited`。 |
| 单次 to-device page | 1,000 | 服务端 MUST enforce。 |

## 7. Retention、Snapshot Pruning 与 Tombstone 上限

Cokret 的真相源仍是 signed Event Envelope；GC 只能释放某个存储边界内的成本，不能把已接受历史改写成不存在。实现对外声明 v1 profile 时 MUST 在 `server/describe.limits` 或等价 feature discovery 中暴露保留策略摘要，例如 raw event retention、snapshot cadence、tombstone stub retention、dangling redaction retention 和 device-message queue TTL。

| 项 | v1 默认上限 / 下限 | 规则 |
| --- | ---: | --- |
| dangling redaction 最小保留 | 30 days | 目标 Event 尚未到达时，接收方 SHOULD 保留 redaction stub 至少 30 天或保留到 Realm policy 声明的更长窗口；不得在窗口内丢弃后再把迟到目标显示为未撤回内容。 |
| tombstone / redaction verification stub 保留 | 不短于 raw event retention | 删除 payload 或压缩历史后仍 MUST 保留足以验证 causal refs、payload hash / proof、redaction / tombstone 授权和 erasure receipt 的最小 stub。 |
| snapshot cadence | 实现声明 | 大型 Realm SHOULD 周期性生成可验证 snapshot；当 replay 成本超过第 4 节预算时 MUST 提供 snapshot-assisted recovery、可分页 backfill 或明确的可恢复错误。 |
| snapshot 保留数量 | 至少 2 个有效 head SHOULD | 服务 SHOULD 保留当前推荐 snapshot 和至少一个前代 snapshot，便于 cursor 过期、移动端恢复和 snapshot 校验失败时回退。 |
| track-disabled / archived materialized state | snapshot 中保留 stub | 通过 `ck.flow.tracks.update` 关闭 track（`tracks.<name>.enabled: set false`）、Realm tombstone、Message redaction 或 hard erasure 后，snapshot MUST 保留 reducer profile 声明的 tombstone / redaction stub；不得仅因 track 不活跃而从 state hash 中静默消失。 |

Pruning 前置条件：

1. 被裁剪范围已经被 accepted Event history、签名 snapshot、event batch receipt、witness receipt 或等价 commitment 覆盖。
2. 没有 active legal hold、audit hold、unexpired invite / grant、pending redaction、未结算 claim、未完成 device verification transaction 或 Realm policy 明确要求保留的依赖。
3. 裁剪后，客户端仍能通过 snapshot frontier、backfill 起点、event-set commitment、verification stub 或可恢复错误理解缺口。

服务端 MAY 对机器人高速创建 track、Message、Reaction、read cursor 或 notification projection 的行为实施 quota 和限流。超过上限时应使用 `rate_limited`、`quota_exceeded`、`payload_too_large`、`dependency_missing` 或 `temporarily_unavailable`，也可将可疑输入 `quarantine`；不得在 reducer 内无界展开或把被裁剪历史当作 accepted absent fact。

## 8. 错误语义

超过规模上限时：

- 确定不可接受的结构输入 MUST reject。
- 缺依赖或可通过 backfill / snapshot 恢复的输入 SHOULD `soft_fail` 或返回 `dependency_missing`。
- 可能是滥用、fork 或异常来源的输入 MAY 进入 `quarantine`。
- 所有可恢复错误 SHOULD 带 `retry_after_ms`、`next_retry_at`、backfill 起点或 snapshot frontier。

**错误码层级约定（normative）**：本文表中形如 ``schema_violation`，`reason_code=prev_refs_too_large`` 的标注表示**顶层错误码** + **reason 子码**两层结构——顶层错误码（如 `schema_violation` / `payload_too_large` / `rate_limited`）来自 [`error-code-registry.json`](../../artifacts/registry/error-code-registry.json)，`reason_code=<...>` 是对该顶层码的细化子码。表中未显式写 `reason_code=` 前缀而直接出现的裸 code（如 `payload_too_large`、`rate_limited`、`temporarily_unavailable`）均为**顶层错误码**。`prev_refs_too_large`、`refs_too_large` 等只在 `reason_code=` 前缀下出现，是 reason 子码而非顶层码。

实现不得把超限输入静默截断后当作 accepted state。
