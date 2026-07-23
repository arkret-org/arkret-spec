---
title: Scalability Constraints
status: candidate
normative: true
stability: v1
updated: 2026-07-13
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [normative-language.md](./normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Arkret v1 的一致性不仅要求语义正确，也要求实现不会被合法但过大的输入拖垮。本文定义 v1 默认规模上限。实现 MAY 在私有部署中使用更低或更高限制，但对外声明互操作 profile 时 MUST：

- 在 `server/describe.limits` 暴露实际限制。
- 对超过限制的输入返回标准错误、`rejected[]` 或 `quarantine[]`，不得无界处理。
- 不得因为本地上限不同而接受会导致其他 v1 节点无法验证的 wire object。

本文的数值是 v1 wire interoperability bounds，不是产品体验目标。

凡会导致实现 MUST reject、MUST quarantine、MUST fail closed 或影响跨实现验证结果的 wire 上限，MUST 在本文登记或从本文显式引用的 profile 参数派生；纯本地性能/SLA 建议可以留在领域文档，但不得作为对端可验证的 v1 互操作上限。

字段级 `maxLength` / `maxItems` / TTL 若已由 canonical JSON Schema 或领域字段表逐字段静态承载，视为由本文通过对应 schema / 领域表统一引用，不要求在本文件逐项复制；此豁免仅适用于单字段局部边界。解码后大小、canonical 总量、跨字段总量、递归深度、状态机时间窗以及无法由 schema 表达的语义上限仍 MUST 在本文件显式登记。发生冲突时，以本文件的聚合 / 语义上限与 canonical schema 中更严格者为准。

## 2. 通用 Wire 上限

| 项 | v1 默认上限 | 规则 |
| --- | ---: | --- |
| 单个 canonical Event / Operation envelope | 1 MiB | 超过时 MUST reject 为 `payload_too_large` 或 `schema_violation`。正文、附件和大对象必须使用 Blob。 |
| 单个 HTTP header value | 8 KiB（但专用 header 可更小） | 入口 MUST 在解析/复制到业务对象前拒绝超限值。`Idempotency-Key` 与 `X-Arkret-Request-Id` 的专用上限均为 128 ASCII chars；cursor / causal wait token header 的专用上限为 4 KiB。 |
| HTTP header aggregate | 32 KiB | request line 之外全部 header name/value 的编码总量；超限 MUST 在认证、签名 transcript 构造和幂等缓存分配前以 `payload_too_large` 拒绝。反向代理可声明更小上限，但不得接受超过本上限的请求。 |
| HTTP path + query | 8 KiB | 按接收的 UTF-8/percent-encoded octets 计；超限 MUST `payload_too_large`，不得先展开为无界对象。大型 selector 必须使用已注册的 POST query-body variant。 |
| cursor base64url 解码后的 canonical payload | 64 KiB | 见 [encoding.md](./encoding.md) §8.6；超限 MUST `invalid_param`，不得在验证大小前构造无界 JSON 对象。header 形态仍同时受 4 KiB 专用 header 上限约束。 |
| `Idempotency-Key` | 1..128 ASCII chars | canonical alphabet `[A-Za-z0-9._~-]`；空值、非 ASCII、超长或其它字符 MUST `invalid_param`，不得进入 replay cache key。 |
| 单次 `/_arkret/self/events` 批量提交的 Event 数 | 1,000 | 超过时 MUST 拆分请求；接收方 MAY 返回 `rate_limited` 或 `payload_too_large`。 |
| 单个 federation transaction 的 Event 数 | 500 | 超过时 MUST 拆分 transaction；接收方 MAY 返回 `rate_limited` 或 `payload_too_large`。 |
| 单次 sync / backfill / projection page 返回项 | 1,000 | 执行方 MUST enforce；客户端不得假设更大 page 可用。 |
| 单个 Event 的 `prev_refs` 数量 | 128 | 超过时 MUST reject（`schema_violation`，`reason_code=prev_refs_too_large`）或要求提交 snapshot / seal 引用；数组项 MUST 去重。 |
| 单个 Event 的 `causal_refs` 数量 | 128 | 超过或存在重复项时 MUST reject（`schema_violation`，`reason_code=causal_refs_too_large`）；不得截断因果前驱集。 |
| 单个 Event `refs[]` 中 `role="authorized_by"` 的条目数量 | 64 | 超过时 MUST reject；authorized_by refs 必须是最小授权状态集合（见 [event-and-patch.md](../models/event-and-patch.md) §2.2）。 |
| 单个 Event 的 `refs[]` 总条目数量 | 128 | 涵盖 `authorized_by` / `attestation` / `parent_event` / `after` / `recovery_capability` / `state_witness` / `inclusion_proof` 等所有 role；超过时 MUST reject（`schema_violation`，`reason_code=refs_too_large`）或拆分。 |
| 同一 `(realm_id, actor_id, actor_seq, prev_frontier_digest)` sibling fork 数 | 16 | 超过时 receiver MUST quarantine 或要求 actor chain repair；不同 Realm 独立计数，见 [event-and-patch.md](../models/event-and-patch.md) §2.6。 |
| 同一 `(realm_id, actor_id, actor_seq)` 跨全部 `prev_frontier_digest` 桶的 sibling fork 累计数 | 64 | 超过时该 Realm 中该高度全部 sibling MUST 进入与单桶 over-fork 相同的 quarantine / repair 终局；producer 不得通过变换 `prev_refs` 子集绕过单桶上限。 |
| 单个 Relation / View / Morph `fields` canonical size | 256 KiB | 更大内容必须放入 Blob 或加密 payload。Morph `facets` map 与 `labels` 数组（[common-fields.md](../models/common-fields.md) §3.1）计入同一对象 256 KiB budget，不另设独立条数上限；见 [morph.md](../models/morph.md) §2。 |
| handle / realm alias localpart | 128 Unicode code points；512 UTF-8 octets | 两个上限均为 inclusive；prepared 后超过任一上限 MUST reject。JSON Schema `maxLength` 只表达 code-point 上限，normative validator 另行执行 octet 上限。 |
| native personal Agent selector `slug` | 64 Unicode code points；256 UTF-8 octets | 两个上限均为 inclusive；prepared 后超过任一上限 MUST reject。 |
| Realm / Space / Circle `title`、actor `display_name` | 256 Unicode code points；1,024 UTF-8 octets | canonical object、request、response 与 projection MUST 复用相同字段定义，不得以无上限 `non_empty_string` 放宽。 |
| Strand / Morph `title` | 512 Unicode code points；2,048 UTF-8 octets | canonical object、request、response 与 projection MUST 复用相同字段定义。grapheme cluster 计数只能用于 UI guidance，不能替代 wire acceptance。 |
| 关系展开深度 | 32 | Projection executor / graph query MUST enforce，跨 Realm 引用必须按 Lazy Link 截断（Lazy Link 定义见 [glossary.md](../overview/glossary.md) "Lazy Link"）。 |
| canonical JSON / deterministic CBOR 结构最大嵌套深度 | 64 | 适用于进入 canonical bytes 的任何 JSON / CBOR 结构（Event / Operation envelope、payload、`fields`，以及 `mls_governance_binding` 等手写 deterministic CBOR 结构）；object 与 array 混合计深，顶层容器深度为 1，深度 64 的输入 MUST 被接受（上限含边界）。超过时 MUST reject（`schema_violation`，`reason_code=structure_depth_exceeded`），MUST NOT 截断或部分解析后继续处理；实现的递归下降 MUST 有深度界或改用显式 worklist，不得依赖栈耗尽崩溃兜底。负例见 [conformance-vectors.md](./conformance-vectors.md) §1.12.1。 |
| 手写 deterministic CBOR 结构单个 array / map 项数 | 65,536 | 适用于 `mls_governance_binding`（[encryption-and-audit.md](../crypto-media/encryption-and-audit.md) §2.5.3）等不经 JSON schema 校验的手写 deterministic CBOR 结构。单个 array 或 map 声明或实际项数超过 65,536 时 decoder MUST reject（`schema_violation`，`reason_code=cbor_bounds_invalid`），且 MUST NOT 依据声明项数在校验前预分配内存。 |
| 手写 CBOR 声明长度自洽性 | 声明长度 ≤ 剩余输入 | CBOR string / byte string / array / map 头部声明的长度或项数 MUST ≤ 实际剩余输入可满足的量；违反时 decoder MUST 在按声明长度分配缓冲区之前 reject（`schema_violation`，`reason_code=cbor_bounds_invalid`）。indefinite-length 项（map `0xbf` / array `0x9f` / string `0x5f`、`0x7f`）违反 deterministic encoding（RFC 8949 §4.2），MUST reject（`schema_violation`，`reason_code=cbor_not_deterministic`），不得归一化后接受。负例见 [conformance-vectors.md](./conformance-vectors.md) §1.12.1。 |
| 单 actor 每毫秒 HLC 生成事件数 | 65,536（HLC logical 4 hex 段上限） | HLC wire 形态为 `<unix_ms_hex_12>-<logical_hex_4>-<node_id_hash_8>`，logical 段为 16-bit；同一 actor 在同一 ms 内最多分配 65,536 个 logical 值（`0x0000`–`0xFFFF`，即 0..65535），第 65,537 个 event 触发 HLC logical 段饱和，producer MUST 等待至下一 ms 再生成或返回本地错误 `hlc_logical_overflow`，MUST NOT wrap 或复用相同 HLC。HLC 仅作为时间线 advisory tie-breaker，不参与授权或状态收敛——饱和不影响协议正确性，只影响展示排序。[^hlc-throughput] [^hlc-logical-width] |

| 单 actor 持续吞吐建议 | ≤ 100,000 events/min | Producer SHOULD 在生产侧自我限速，避免在突发情况下饱和 HLC logical 段或下游 reducer。超过该建议持续吞吐时，actor SHOULD 拆分为多 device / 多 actor 并行，或考虑使用 batch event。 |
| HLC `hard_future_skew_ms`（硬 future drift 上限） | 300,000 ms（5 分钟） | 见 [encoding.md](./encoding.md) §7.2。HLC `unix_ms` 超本地时钟该阈值时 receiver MUST reject / quarantine。该校验是 envelope freshness / DoS guard，非授权、Lattice winner、Control Move precondition 或 Seal finality 输入。 |
| HLC `expected_future_skew_ms`（软 future drift 阈值） | 30,000 ms（30 秒） | 见 [encoding.md](./encoding.md) §7.2。超该阈值但未超 `hard_future_skew_ms` 时 receiver SHOULD soft-fail / quarantine。 |
| HLC `state_event_expected_future_skew_ms`（state event 软阈值） | 默认按 `expected_future_skew_ms` | 见 [encoding.md](./encoding.md) §7.2。profile MAY 对 state event（capability / membership / policy / service binding / Realm upgrade / MLS commit 等）声明更严窗口；未声明时按 `expected_future_skew_ms` 处理。 |

`refs[]` 总量边界的生成式负例由 `ak.vector.scalability.refs_limit.v1` 固化。envelope 1 MiB 边界与 HTTP header/path/query 上限分别由 `ak.vector.scalability.envelope_size_limit.v1`、`ak.vector.scalability.http_header_limits.v1` 固化；runner MUST 使用 generator 描述在执行时构造边界值，不在 fixture 中内嵌兆级字符串。

其余 wire 上限按语义族由 `ak.vector.scalability.event_ref_role_limits.v1`、`ak.vector.scalability.batch_page_limits.v1`、`ak.vector.scalability.sibling_fork_limits.v1`、`ak.vector.scalability.object_control_limits.v1` 与 `ak.vector.scalability.capability_limits.v1` 固化；统一生成式输入与期望结果见 `scalability-limits-fixture.json`。

**字符串标识符 octet 臂的独立性与可测性（normative）**：handle / realm alias localpart、agent `slug`、`title` / `display_name` 等字段的 UTF-8 octet 上限均为其 code-point 上限的 4 倍。由于 UTF-8 单码点至多 4 字节，对**原始输入**"code-point 数 ≤ 上限"必然蕴含"octet 数 ≤ octet 上限"；因此 octet 臂只在 **preparation（RFC 8265 PRECIS / IDNA / Unicode NFC 归一）扩展了输入**时才独立于 code-point 臂生效——即存在这样的输入：其 code-point 数 ≤ code-point 上限，但其 **prepared 形态**的 UTF-8 octet 数 > octet 上限。normative validator MUST 在 **prepared 形态**上同时执行两个上限，任一超限 MUST reject（JSON Schema `maxLength` 只能表达 code-point 上限，octet 臂 MUST 由 SDK / normative validator 另行执行，见 §2 各行）。该 octet 臂 MUST 由可执行**负例**覆盖：一个 code-point 数 ≤ 上限、但 prepared UTF-8 octet 数 > 上限的字符串 MUST 被 reject。此类字节精确负例（含触发 preparation 扩展的具体码点输入）由 string-profile conformance fixtures 承载，MUST 存在且可执行，不得只在本表 prose 声明 octet 上限而缺可执行向量。

[^hlc-throughput]: informative：换算约 65.5 M events/s（精确 65,536,000 events/s）单 actor 上限，仅为 65,536/ms × 1000 的派生值，**非 normative 吞吐保证**，实现 MUST NOT 以此作为容量承诺。

[^hlc-logical-width]: informative：logical 段宽度的潜在扩展属未来评估方向，不构成 v1 规范要求。

## 3. 授权与 Capability 上限

| 项 | v1 默认上限 | 规则 |
| --- | ---: | --- |
| delegation chain 深度 | 4 | canonical 上限；[`capabilities.md` §10.2](../authz/capabilities.md) DFS 深度上限与 `grant-constraint.schema.json` `max_delegation_depth` 的 `maximum` MUST 与此值一致。超过时 MUST deny；profile MAY 声明更低上限。 |
| 单次授权判定展开 grant 数 | 1,024 | 超过时 MUST fail closed、使用已验证 snapshot，或返回 `soft_failed` / `temporarily_unavailable`。 |
| 单个 grant 的 constraint 数 | 64 | 超过时 MUST reject。 |
| 单个 resource selector AST 深度 | 8 | 超过时 MUST reject；度量包含逗号、加号、引用与子 selector 嵌套，详见 [`resource-selector-grammar.md` §5](../authz/resource-selector-grammar.md)。 |
| 单个 resource selector canonical JSON 总量 | 64 KiB | 未注册字段也计入；超过时 MUST `selector_too_complex`。 |
| 单个 selector term 字段值 | 1,024 bytes | 超过时 MUST `selector_too_complex`。 |
| 单个 grant 未注册字段总数 | 256 | 超过时 MUST `selector_too_complex`；未知字段仍计入 64 KiB 总量。 |
| `requires_claims[]` 项数 | 32 | 超过时 MUST reject；canonical schema 同步 `maxItems: 32`。 |

上述 cursor / selector / policy-array 边界由 active `ak.vector.scalability.cursor_selector_limits.v1` 在 `scalability-limits-fixture.json` 中执行。
| 单个 claim 的 `trusted_issuers[]` / `roles[]` 项数 | 16 | 超过时 MUST reject；canonical schema 同步 `maxItems: 16`。 |
| Constraint object 内嵌套层级 | 4 | 超过时 MUST reject；与 selector AST 深度分别计量。 |
| 单个 device pairing transcript 失败提交数 | 10 | 达到上限时 pairing code MUST 锁定并永久失效；不得重置计数继续猜测。 |
| 高频路径 authz snapshot 最大重建延迟 | 5 秒（SHOULD，本地性能建议） | `chat_mvp`、`kanban_mvp`、`full_client` 和 `principal_server` 相关服务 SHOULD 满足。这是**本地性能 / SLA 建议**，非 wire interoperability bound——对端无法仅凭 wire object 核验本地重建是否 ≤5s，故不构成 §1 意义上的可互操作核验项。 |

当 grant / revoke / claim status / policy component / membership frontier 变化时，受影响的 capability snapshot MUST 立即标记 stale。stale snapshot 不得继续用于新的写入 allow 决策。

## 4. CBA / Lattice 上限

| 项 | v1 默认上限 | 规则 |
| --- | ---: | --- |
| 单个 DataEvent canonical size | 1 MiB | 超过时 MUST reject 为 `payload_too_large` 或 `schema_violation`。 |
| 单个 Control Move canonical size | 1 MiB | 超过时 MUST reject 为 `payload_too_large` 或 `schema_violation`。 |
| 单个 Control Move 的 `preconditions + effects` 数 | 256 | 超过时 MUST reject；需要拆成多个 Control Move 或使用 higher-level control transaction。 |
| 单个 Seal 新增 Control Move 数 | 1,000 | 超过时 MUST 拆分 Seal；接收方 MAY 返回 `rate_limited` 或 `temporarily_unavailable`。 |
| Seal DAG leaf 数 | 实现声明 | 超过时 SHOULD 请求或生成 signed compaction Seal；查询可使用 deterministic Seal view。 |
| 单次 Lattice join CPU / wall-clock 预算 | 实现声明 | 服务 MUST 在 `server/describe.limits` 暴露；超出时返回可恢复错误或使用已验证 state_root + inclusion proof。 |
| 单次 Lattice join 内存预算 | 实现声明 | 服务 MUST 暴露，超出时返回可恢复错误而不是 OOM。 |
| `revocation_freshness_window_ms` | 86,400,000 ms（24h，default）| `realm.schema.json`；按 Seal DAG notary 提交时间差度量（[`event-auth-state-resolution.md` §4.3](../authz/event-auth-state-resolution.md)）。`risk_tier=high` capability 无宽限（等效 0）。高风险 Realm SHOULD 取更短值。 |
| `receipt_sla_ms` | 86,400,000 ms（24h，default）| `realm.schema.json`；pending Control Move 得到 signed receipt / rejection 的截止（[`event-auth-state-resolution.md` §7.2](../authz/event-auth-state-resolution.md)）。按 notary 提交时间计。 |
| 单个 pending Control Move 累计 defer 数（`max_receipt_defers`）| 3（default）| `realm.schema.json`；超过仍未 include / signed-reject 即等同无声遗漏，构成 censorship evidence（[`event-auth-state-resolution.md` §7.2](../authz/event-auth-state-resolution.md)）。 |

CBA fallback 不得选择本地接收顺序或数据库 ID。Snapshot 必须有 Seal inclusion proof、state_root、frontier 和 chunk digest。对缺失、不可达或高成本 `refs` 的 backfill，接收方 MAY 在预算耗尽后把 DataEvent 保持 observed-only、把 Control Move 保持 pending，或返回 `dependency_missing`、`temporarily_unavailable`；不得在同步写入路径无界递归展开。

### 4.1 Progressive CBA Backfill Profile

实现声称支持 `full_client`、`e2ee_client` 或 `principal_server` profile 时，MUST 支持渐进式 CBA 恢复，而不是要求一次性拉完整历史：

| 项 | v1 默认上限 / 建议 | 规则 |
| --- | ---: | --- |
| 单轮 targeted backfill page | 256 objects | 客户端 SHOULD 优先拉缺失 DataEvent、Control Move、Seal predecessor、critical `refs` 的最小闭包，再扩大范围。 |
| 单 Realm 后台 dependency 队列 | 4,096 refs | 超过时 MUST 合并去重、分批处理，或切换到 state_root-assisted recovery。 |
| snapshot-assisted recovery 触发 | Seal leaf 过多、join 预算耗尽或本地预算耗尽 | 必须验证 Seal signer authority、frontier、state_root 和 chunk digest。 |
| 交互式恢复首屏预算 | 2 seconds SHOULD | 预算耗尽后 MAY 返回 read-only partial view + `seal_incomplete`，并继续后台恢复。 |
| retry backoff | 指数退避，有上限 | 响应 SHOULD 带 `retry_after_ms`、`next_retry_at`、缺失 ref 和可用 source。 |

渐进恢复阶段：

1. **Seal probe**：先查询 Realm Seal leaves、可用 snapshot manifest 和缺失 ref 的 source。
2. **Targeted dependency fetch**：按缺失 DataEvent、Control Move、Seal predecessor 与 critical refs 拉最小闭包。
3. **State-root-assisted recovery**：闭包超过预算时，改用最近可验证 state_root / snapshot 作为 base，再回放其 frontier 之后的 DataEvent 与 Control Move。
4. **Read-only partial state**：仍有缺口时，客户端 MAY 展示已验证 CBA query basis 的只读 projection，并显式标记 query basis incomplete。
5. **Write revalidation**：任何新 Control Move 必须在提交前以最新 Seal view 重新验证 preconditions；DataEvent 必须以最新可用 `seal_ref` 重新验证授权 freshness；不得继承 partial view 的乐观允许结果。

长期离线设备重新上线时，服务端 SHOULD 支持分页返回 Seal DAG 诊断和 snapshot candidate，避免客户端在写入路径递归拉取数千个 Event / Seal。

## 5. Space / Relation / View 上限

> **"active" 计数口径（normative，适用本文全文）**：本文各上限中的 **active** 计数 MUST 仅计入当前生效对象，**MUST NOT** 计入 tombstoned、archived、hard-erased、或经 `ak.strand.tracks.update` 关闭（track-disabled，见 §7）的对象。判定上限是否触发以该口径为准；archived / track-disabled 对象在 snapshot 中以 stub 保留（见 §7）但不计入 active 上限。

| 项 | v1 默认上限 | 规则 |
| --- | ---: | --- |
| 单 Realm active Space 数 | 5,000 | 超过时 Realm projection MUST paginate；建议拆分为多个 Realm 或使用嵌套 Space。 |
| 单个 Space `labels[]` | 64 项；每项 128 chars | 超过时 MUST `schema_violation`；items MUST 去重。 |
| 单个 Message ContentBlock `attachments[]` | 32 项 | 超过时 MUST `schema_violation`；大附件使用 Blob，durable 关联优先使用 Relation `attached_to`。 |
| 单个 Board Space active List Space 数 | 500 | 超过时 Board projection MUST paginate 或 require filtered View。 |
| 单个 List Space active Strand item 数 | 10,000 | Projection MUST paginate；drag / reorder 仍按 rank + deterministic tie-break。 |
| Space 嵌套深度 | 8 | 超过时 reducer MUST reject `ak.space.parent`；防止任意深度的容器树拖累查询性能。 |
| 单个对象 active Relation 数 | 10,000 | Projection executor MUST paginate，不能要求客户端一次性拉全。 |
| 单 Realm active Circle 数 | 1,000 | 超过时 reducer MUST reject `ak.circle.create`（`reason=circle_count_exceeded`）。这是 normative 安全上界，约束 cascade / delivery fanout 最坏情况；产品 SHOULD 远低于此（见 [`../models/circle.md` §10.3](../models/circle.md) / §11 的"Circle 少而稳定"软上限例如 ≤64）。Agent Sidecar 的 backing Circle **计入**本上限（每个 Sidecar 一个 backing Circle，`(realm_id, controller_id)` singleton）；reducer 计数时纳入，即使普通 Circle API 按 [`../models/circle.md` §11.1](../models/circle.md) 将其排除。 |
| 单 actor 所属 active **MLS-backed** Circle 数 | 256 | 超过时 reducer MUST reject 把该 actor 加入新 MLS-backed Circle（`reason=circle_count_exceeded`）。该上限直接绑定 [`../models/circle.md` §10.3](../models/circle.md) 的踢人放大 `M+R`（M = 该 actor 所在 MLS-backed Circle 数）:封顶 M 即封顶单次 membership 变更触发的最坏 MLS group rotation 次数，使实现可对最坏密码学工作量与 DoS 抵抗做有界推理。Plaintext Circle 不计入本上限（不产生 MLS rotate）。**Agent Sidecar backing Circle 计入本上限**：Sidecar 的 backing Circle 是 `mls_rfc9420` MLS-backed Circle，agent membership 变更会触发 MLS rotate，因此对其 controller 与 eligible agent 均**计入** M；reducer MUST 在计数时纳入 backing Circle（即使普通 Circle API 按 [`../models/circle.md` §11.1](../models/circle.md) 将其从 list/get 排除），否则 §10.3 的最坏 rotation 上界 M+R 会被低估。 |
| 单个 View projection page | 1,000 items | View cursor MUST 绑定 authorization context 和 frontier。 |
| rank 长度 | 128 chars | 超过时 MUST reject，见 `encoding.md`。 |
| 单个 Calendar Event attendees 数 | 1,000 | 超过时 MUST reject 或要求拆分会议 / 日程实例；attendees 必须按 actor / handle / resource key 去重。 |
| 单次 recurrence expansion 返回 occurrence 数 | 10,000 | 超过时 MUST paginate、截断为带 cursor 的 page，或返回 `limit_exceeded`；不得无界展开 RRULE。 |
| 单个 File Transfer `recipient_device_ids` 数 | 1,000 | 超过时 MUST reject 或拆分 transfer；每个 device key wrap 必须保持独立可验证。 |
| 单条 `ak.call.state` 的 `payload.participants[]` 数 | 1,000 | 超过时 MUST reject（`schema_violation`）或改用采样 / 摘要写入；schema 已声明 `maxItems: 1000`。见 [call-state.md](../crypto-media/call-state.md) §4.1。 |
| `ring_timeout_ms` / `scheduled_start_grace_ms` / `connecting_timeout_ms` | 60,000 / 300,000 / 120,000 ms（默认且最大） | 见 [call-state.md](../crypto-media/call-state.md) §4.2；超时由 focus / token issuer / Principal Server 基于当前 accepted head 显式推进，不能由本地计时器直接改写 reducer。 |

| join policy 单个 `application_form` gate 的 `questions[]` 数 | 64 | 超过时 MUST reject（`schema_violation`）。见 [join-policy.md](../governance/join-policy.md) §3.3。 |
| `member.application` 的 `answers[]` 数 | 64 | 与 `questions[]` 上限对齐；超过时 MUST reject（`schema_violation`）。见 [join-policy.md](../governance/join-policy.md) §7.2。 |
| join / application 的 `gate_proofs[]` 数 | 16 | 与 join policy `gates` 1..16 上限对齐（含 runtime challenge proof）；超过时 MUST reject（`schema_violation`）。见 [join-policy.md](../governance/join-policy.md) §5 / §7.2。 |
| `member.application.encryption_envelope.recipients[]` 数 | 64 | 每个 recipient 是一组独立 HPKE 封装；超过时 MUST reject（`schema_violation`）。见 [join-policy.md](../governance/join-policy.md) §8.2。 |

Realm 与 actor 两条 Circle 基数边界由 `ak.vector.scalability.circle_count_limit.v1` 同时覆盖。

Board position edge 的 canonical key 是 `(board_space_id, strand_id)`。同一 key 下多个 active edge 只允许 reducer 选择一个 winner，并记录 losers；View projection MAY 暴露 loser conflict records，但不得把同一 Strand 渲染成多个主位置。

## 6. E2EE 与设备上限

| 项 | v1 默认上限 | 规则 |
| --- | ---: | --- |
| 单 principal active device 数 | 100 | 超过时 Device / Key Server MAY require admin approval or device cleanup。 |
| 单个 Seal 的 `predecessor_refs[]` | 128 | 超过时接收方 MUST 以 `payload_too_large` 拒绝，不得截断或只验证前缀。开放 notary set 必须先合并 DAG frontier，再形成后继 Seal。 |
| 单个 compaction Seal 的 `covered_event_digests[]` | 1,048,576 | 超过时接收方 MUST 以 `payload_too_large` 拒绝，不得接受不完整覆盖。更大状态必须使用已登记的分块 completeness proof / MLS Governance Proof，而不是生成无界单对象。 |
| 单 MLS commit 绑定的 `membership_frontier` refs | 128 | 超过时 MUST 使用签名 state root / snapshot reference。 |
| 单个 MLS Governance Proof HTTP/JSON 响应 | 4 MiB（4,194,304 bytes） | 包含重复的 Bundle metadata、manifest、一个 chunk 及其 inclusion proof 的完整接收字节数；server MUST 在发送前 enforce，client MUST 在流式接收时 enforce，不能只信任 `Content-Length`。超限响应 MUST 丢弃且不得部分解析为有效 chunk。 |
| `complete_control_state_v1` 逻辑 Bundle canonical item bytes 总和 | 256 MiB（268,435,456 bytes） | `chunk_manifest.total_item_bytes` 是四类集合每个 item 的 RFC 8785 canonical JSON UTF-8 长度之和，不含数组括号和重复 metadata；client MUST 流式重算，MUST NOT 按声明值预分配。超过时 server MUST 返回 422 `mls_governance_proof_bounds_exceeded`，不得截断。 |
| MLS Governance Proof 集合总项数 | `seal_path` 4,096；`covered_event_digests` 1,048,576；`control_state` 262,144；`frontier_events` 128 | `chunk_manifest.collection_totals` 与实际无缝拼接后的计数 MUST 精确相等。任一总数超过上限时不得生成 manifest；server 返回 `mls_governance_proof_bounds_exceeded`。只有 `seal_path` 超限时 caller MAY 用自己已信任的更近 anchor 重试；其它总界超限必须 fail closed，等待单独注册的 compact completeness profile 或更小的 accepted state。 |
| MLS Governance Proof chunk 数 / 每 chunk 项数 | 最多 1,024 chunks；单块 `seal_path` 128、`covered_event_digests` 8,192、`control_state` 1,024、`frontier_events` 32 | 每个 chunk 只承载一种 collection 且 `items` 非空。全局顺序固定为 `seal_path` → `covered_event_digests` → `control_state` → `frontier_events`；同 collection 的 `start_index` 必须从 0 连续无洞。`chunk_index` 范围为 0..1023，inclusion path 最多 10 个 sibling hash。超出 schema 上限或出现空块、乱序、重叠、缺口均 MUST reject。 |
| 普通 KeyPackage 有效期 | 1 hour（下限）– 30 days（默认上限） | 更长有效期必须由 profile 明确声明。接收方 MUST NOT 使用已过期 KeyPackage 建立新 MLS 会话（过期复用是已知 E2EE 风险）；签发方 SHOULD NOT 签发有效期短于 1 小时的 KeyPackage（避免正常 join 流程内即过期）。 |
| Last-resort KeyPackage 有效期 | 30 days（默认上限） | **Last-resort KeyPackage**（[encryption-and-audit.md](../crypto-media/encryption-and-audit.md) §2.6.2）的有效期 MUST 受与普通 KeyPackage 同一 30 days 默认上限约束，且 **不享** "更长有效期由 profile 声明" 的豁免（last-resort 包复用 init/encryption key、弱化 Welcome 前向保密，其生命周期即弱化窗口硬上界）；`personal_node` profile MAY 放宽但 MUST 向用户披露。 |
| KeyPackage 接收侧时钟偏差宽限 | ≤ 有效期的 10% | 实现 MAY 声明一个不超过该 KeyPackage 有效期 10% 的接收侧时钟偏差宽限窗口；该宽限同时适用于普通与 last-resort KeyPackage 的过期判定。 |
| to-device 队列 TTL | 24 hours（默认最大值） | `DeviceMessageEnvelope.expires_at` 不得晚于当前 service / Realm / profile TTL 上限；服务端 MUST 拒绝缺失、已过期、早于 `sent_at` 或超限的消息。高安全 profile SHOULD 声明更短 TTL。 |
| KeyPackage claim 限速 | 60 seconds 内最多 5 次 / `(requester_service_id, target_principal_id)` | 超过限额时对外仍使用反枚举响应（`claim_failed` 或通用 rate-limited envelope），不得泄露目标存在性；服务端内部审计 reason 记录为 `keypackage_claim_rate_limited`。 |
| 单次 to-device page | 1,000 | 服务端 MUST enforce。 |
| 分块流式 AEAD 附件 `segment_size` 取值范围 | 1 KiB（1,024）– 8 MiB（8,388,608），默认 256 KiB（262,144） | 见 [media-and-blob.md](../crypto-media/media-and-blob.md) §3.3。超出范围 MUST reject（`schema_violation`）；`segment_size` 越界或与 `segment_count`、`size_bytes` 不自洽时接收方 MUST fail closed。 |
| 分块流式 AEAD 附件 `segment_count` 上限 | 1,048,576（2^20） | 见 [media-and-blob.md](../crypto-media/media-and-blob.md) §3.3。`segment_index` 为 `u32`（硬上界 2^32），但 v1 wire 互操作上限为 2^20；超过时 MUST reject（`schema_violation`）。`segment_count` MUST 等于 `ceil(size_bytes_plaintext / segment_size)` 并与实际段数一致，否则接收方 MUST 拒绝（`segment_bounds_invalid` / `segment_sequence_invalid`）。声明字段越界 / 不自洽负例见 [conformance-vectors.md](./conformance-vectors.md) §16.5（`ak.vector.blob.stream_aead_bounds_rejected.v1`）。 |

声明 `ak.self.events.query.mls_governance_proof` 的 Service Describe MUST 在 `limits.mls_governance_proof` 暴露上述固定 v1 bounds；该对象的 schema 使用 `const` 防止服务声称同一 operation 却采用不同互操作边界。Chunk 0 请求不得携带 `expected_bundle_digest`；取得 manifest 后，chunk 1..N-1 请求 MUST 携带 chunk 0 的 `bundle_digest`。若该 manifest 已不可用，server 返回 `frontier_unavailable`，caller 只能从 chunk 0 重新开始，不能把另一 manifest 的 chunk 混入。`chunk_index >= chunk_manifest.chunk_count` 使用 `invalid_param`。任何超总界响应、丢块后继续接受、服务器自报 total 替代最终 root 重算，或按本地更高上限绕过本表，均不符合 v1。

上述全部数值边界、chunk acquisition 条件及 `limit-1 / limit / limit+1` 生成矩阵由 `ak.vector.scalability.mls_governance_proof_bounds.v1` 固化；runner 归属与逐项期望见 [conformance-vectors.md](./conformance-vectors.md) §1.12.3。

### 6.1 身份、邀请与推送隐私窗口

下表登记会触发拒绝、fail-closed、隐私 zeroize 或跨实现 replay 判定的 identity / invite / push 窗口。领域文档仍定义完整状态机；本文登记 wire interoperability bound 和 conformance 入口。

本节与上一表的边界由 active `ak.vector.scalability.protocol_window_limits.v1` / `protocol-edge-cases-fixture.json` 统一执行：数组上限使用 `limit-1 / limit / limit+1`，时间窗使用 runner 注入时钟覆盖临界点前、临界点和临界点后；runner MUST 断言拒绝码、不得截断、状态推进与过期后物理删除义务。

| 项 | v1 默认上限 / 下限 | 规则 |
| --- | ---: | --- |
| invite locator `ttl_seconds` | 60..3,600 seconds（默认 900） | 见 [invite-addressing.md](../sync/invite-addressing.md) §3.1；小于下限或超过硬上限 MUST `schema_violation`，部署 MAY 在此范围内缩短实际 TTL。 |
| 单 principal 同时 active invite locator 数 | 16 | issue 若将 active 数增加到 17 MUST fail closed（`rate_limited` 或 `failed_precondition`），不得隐式撤销未指定 locator；expired、revoked、consumed record 不计入 active。rotate 在同一事务中以一换一，不得因边界值 16 被拒绝。 |
| `ak.invite.third_party.expires_at` base-profile 硬上限 | 7 days | 见 [third-party-invites.md](../sync/third-party-invites.md) §6。超过 base-profile 上限的第三方 invite MUST reject 或要求声明扩展 profile + revalidation proof；高安全 / audited / enterprise Realm 的硬上限为 24 hours。 |
| 第三方 invite `(invite_id, claim_nonce)` replay set TTL | `invite.expires_at + 24h`（下限） | 验证服务 / 接收 Sync Service MUST 至少保留到该窗口结束；窗口内重复 claim MUST 在 reducer 仲裁前拒绝。replay key SHOULD 以 HMAC / hash 存储，不得持久化明文 invite token。 |
| expired invite token secret zeroize | 24h 内 | `expires_at <= now` 后，服务端 MUST 在 24h 内 zeroize `token_salt` / lookup pepper material，并 GC active commitment 记录；claim 路径返回 `expired_invite_token` 或等价不可枚举错误。 |
| `contact_request_pending_ttl` | 默认且最大 14 days | 见 [contact-and-direct-conversation.md](../identity/contact-and-direct-conversation.md) §3。双方分别从 accepted request 的 canonical `created_at` 计时；超窗的 accept/respond MUST fail closed，不得由本地配置放宽。 |
| `identity_creation_lease` TTL | 默认且最大 15 minutes | 见 [account-lifecycle.md](../identity/account-lifecycle.md) §2.1.2；超过时 Account Authority MUST refuse issuance。 |
| `account_handoff_grant` TTL | 默认且最大 1 hour | 见 [account-lifecycle.md](../identity/account-lifecycle.md) §2.1.2；无 refresh 语义，过期后必须重新认证。 |
| `terminal_parent_repair_window` | 30 days | 跨 Realm parent 指向 terminal Realm 时，引用方 MUST 在窗口内 reparent、archive 或 tombstone；见 [realm-and-space.md](../models/realm-and-space.md) §2.6.1。 |
| `erasure_propagation_window_ms` | 默认且最大 604,800,000 ms（7 days） | 见 [realm-and-space.md](../models/realm-and-space.md) §2.6.2。超窗未回执的 peer MUST 标 `timed_out`，issuing receipt 的 `fanout_status` MUST 为 `incomplete`。 |
| `deactivation_propagation_window_ms` | 最大 600,000 ms（10 min） | 见 [federation.md](../sync/federation.md) §4.4.1。超窗 MUST 标 `deactivation_federation_incomplete`，并暂停受影响主体的新 onboard / grant / KeyPackage 路径。 |
| `mls_deactivation_grace_ms` | 默认且最大 600,000 ms（10 min） | 见 [account-lifecycle.md](../identity/account-lifecycle.md) §7.1。超窗未完成 MLS remove 的成员 MUST 标 `unverifiable_member`，并拒收其新 epoch 消息。 |
| soft-logout fresh DID proof replay window | `expires_at - issued_at` 最大 300,000 ms；clock skew 最大 300,000 ms | 见 [account-lifecycle.md](../identity/account-lifecycle.md) §4。任一边界超限 MUST 拒绝，reason_code=`did_proof_replay_window_exceeded`。 |
| `call_empty_timeout_ms` | 默认且最大 120,000 ms | 见 [call-state.md](../crypto-media/call-state.md) §4.2。active media roster 持续为空达到该窗口时，focus / token issuer 或 P2P 承载 Principal Server MUST 推进 `active -> ended`；profile MAY 收紧，不得放宽。 |
| key backup 每 principal 每 24h 下载上限 | 64（memory-hard profile 可声明 16–256） | 见 [key-management.md](../identity/key-management.md) §7.8。实现 MUST 在 `server/describe.limits` 或 profile 参数中公布实际上限；超限 MUST rate-limit / fail closed，并不得在日志或 telemetry 中泄露 plaintext keybag。 |
| `push_target_id` rotation 周期 | 默认 ≤ 90 days | 见 [device-lifecycle.md](../crypto-media/device-lifecycle.md) §5a.1。客户端 SHOULD 在 push token 变化、设备恢复、out-of-band 重新登录或自定义 rotation 周期到达时轮换；高安全部署 SHOULD 声明更短周期。 |
| 旧 / 新 `push_target_id` 可逆映射保留 | ≤ 24h，或单条未投递消息 TTL，取较短者 | 服务方只可在 rotation 时短暂保留映射以迁移未投递消息；超过窗口 MUST 物理删除旧 pseudonym 与索引材料，不得保留能把新旧映射回同一 device 的信息。 |
| DM Realm active member count | 等于 2 | 见 [contact-and-direct-conversation.md](../identity/contact-and-direct-conversation.md) §7。向 active DM Realm 加第三人 MUST reject；升级多人聊天必须创建新的普通 Realm / Strand。 |
| 加好友附言 `message` 长度 | 1..2000（NFC） | 见 [contact-and-direct-conversation.md](../identity/contact-and-direct-conversation.md) §4。`ak.self.contact.command.request` 的可选 `message` 超长或非 NFC MUST reject（`schema_violation`）。 |
| 单 `(recipient_service_id, principal_id, device_id)` active `push_route` 条数 | 16 | 见 [device-lifecycle.md](../crypto-media/device-lifecycle.md) §5a.2。超过上限的 `ak.device.push_route` 注册 MUST reject，reason_code=`push_route_limit_exceeded`。 |
| push-route 注册 / 轮换写入速率 | 60s 内 ≤ 8 次（同一上述维度） | 见 [device-lifecycle.md](../crypto-media/device-lifecycle.md) §5a.2。超额 MUST rate-limit，内部审计 reason `push_route_registration_rate_limited`。 |

## 7. Retention、Snapshot Pruning 与 Tombstone 上限

Arkret 的真相源仍是 signed Event Envelope；GC 只能释放某个存储边界内的成本，不能把已接受历史改写成不存在。实现对外声明 v1 profile 时 MUST 在 `server/describe.limits` 或等价 feature discovery 中暴露保留策略摘要，例如 raw event retention、snapshot cadence、tombstone stub retention、dangling redaction retention 和 device-message queue TTL。

| 项 | v1 默认上限 / 下限 | 规则 |
| --- | ---: | --- |
| dangling redaction 最小保留 | 30 days | 目标 Event 尚未到达时，接收方 SHOULD 保留 redaction stub 至少 30 天或保留到 Realm policy 声明的更长窗口；不得在窗口内丢弃后再把迟到目标显示为未撤回内容。 |
| tombstone / redaction verification stub 保留 | 不短于 raw event retention | 删除 payload 或压缩历史后仍 MUST 保留足以验证 causal refs、payload hash / proof、redaction / tombstone 授权和 erasure receipt 的最小 stub。 |
| snapshot cadence | 实现声明 | 大型 Realm SHOULD 周期性生成可验证 snapshot；当 replay 成本超过第 4 节预算时 MUST 提供 snapshot-assisted recovery、可分页 backfill 或明确的可恢复错误。 |
| snapshot 保留数量 | 至少 2 个有效 head SHOULD | 服务 SHOULD 保留当前推荐 snapshot 和至少一个前代 snapshot，便于 cursor 过期、移动端恢复和 snapshot 校验失败时回退。 |
| track-disabled / archived materialized state | snapshot 中保留 stub | 通过 `ak.strand.tracks.update` 关闭 track（`tracks.<name>.enabled: set false`）、Realm tombstone、Message redaction 或 hard erasure 后，snapshot MUST 保留 reducer profile 声明的 tombstone / redaction stub；不得仅因 track 不活跃而从 state hash 中静默消失。 |

Pruning 前置条件：

1. 被裁剪范围已经被 accepted Event history、签名 snapshot、event batch receipt、witness receipt 或等价 commitment 覆盖。
2. 没有 active legal hold、audit hold、unexpired invite / grant、pending redaction、未结算 claim、未完成 device verification transaction 或 Realm policy 明确要求保留的依赖。
3. 裁剪后，客户端仍能通过 snapshot frontier、backfill 起点、event-set commitment、verification stub 或可恢复错误理解缺口。

服务端 MAY 对机器人高速创建 track、Message、Reaction、read cursor 或 notification projection 的行为实施 quota 和限流。超过上限时应使用 `rate_limited`、`quota_exceeded`、`payload_too_large`、`dependency_missing` 或 `temporarily_unavailable`，也可将可疑输入 `quarantine`；不得在 reducer 内无界展开或把被裁剪历史当作 accepted absent fact。

## 8. 错误语义

超过规模上限时：

- 确定不可接受的结构输入 MUST reject。
- 缺依赖或可通过 backfill / snapshot 恢复的输入 SHOULD `soft_failed` 或返回 `dependency_missing`。
- 可能是滥用、fork 或异常来源的输入 MAY 进入 `quarantine`。
- 所有可恢复错误 SHOULD 带 `retry_after_ms`、`next_retry_at`、backfill 起点或 snapshot frontier。

**错误码层级约定（normative）**：本文表中形如 ``schema_violation`，`reason_code=prev_refs_too_large`` 的标注表示**顶层错误码** + **reason 子码**两层结构——顶层错误码（如 `schema_violation` / `payload_too_large` / `rate_limited`）来自 [`error-code-registry.json`](../../artifacts/registry/error-code-registry.json)，`reason_code=<...>` 是对该顶层码的细化子码。表中未显式写 `reason_code=` 前缀而直接出现的裸 code（如 `payload_too_large`、`rate_limited`、`temporarily_unavailable`）均为**顶层错误码**。`prev_refs_too_large`、`refs_too_large` 等只在 `reason_code=` 前缀下出现，是 reason 子码而非顶层码。

实现不得把超限输入静默截断后当作 accepted state。
