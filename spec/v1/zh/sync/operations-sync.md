---
title: Operations And Sync
status: candidate
normative: true
stability: v1
updated: 2026-06-11
see_also:
  - sync/service-surface.md
  - sync/client-sync.md
  - authz/event-auth-state-resolution.md
  - models/event-and-patch.md
  - conformance/encoding.md
  - conformance/normative-language.md
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Cokret 是面向协作对象的分布式发布、传播、查询与收敛协议。同步层的目标是让各副本在不依赖全局共识链的前提下，验证事件来源、传播可合并状态、暴露冲突，并对治理状态提供可审计 finality。

Cokret v1 采用 **CBA**（Control-plane Basis-committed Sealing）：

- 数据面事件（DataEvent）解决普通协作写入：消息、reaction、read cursor 的持久投影、协作对象字段、排序、计数等。DataEvent 由 actor 签名、按 `seal_ref` 验证授权，通过 cell Lattice / CRDT 收敛；它不等待 Seal 才成为本地可接受事实。
- 控制面事件（Control Move）解决治理写入：membership、capability、policy、notary、lifecycle、MLS epoch、密钥治理，以及 schema 明确声明 `sealed=true` 的对象。Control Move 由 Seal 覆盖后才取得 `sealed` finality。
- Seal 只对控制面给出 finality；它可以携带数据面的观测承诺（例如 `data_view_root` / `data_event_set_root` / `availability_root`），但这些根只产生 `observed` 查询等级，不把数据面升级为控制面 finality。

同步层必须支持 actor 侧可验证发布、append-only 审计日志、离线写入、跨服务传播、选择性同步、最终一致投影、以及控制面问责。

## 2. 事件类型与 wire 边界

Cokret v1 的共享历史基础单位是 signed Event Envelope（schema [`event-envelope.schema.json`](../../artifacts/schemas/event-envelope.schema.json)）。Envelope 由 `event_id`、`realm_id`、`kind`、`actor_id`、`actor_seq`、`prev_refs[]`、`refs[]`、`payload`、`proofs[]` 等字段组成，canonical event bytes 与 proof 规则见 [`event-and-patch.md`](../models/event-and-patch.md) 与 [`encoding.md`](../conformance/encoding.md)。

Reducer-input Event 分为两类，二者 wire shape 互斥：

| 类型 | 必须字段 | 禁止字段 | 收敛语义 |
| --- | --- | --- | --- |
| DataEvent | `effects[]`、`seal_ref`、`auth_context` | `preconditions`、`seal_basis` | 只写 data plane cell；签名、actor chain、授权、capability 与 Lattice 验证通过即可本地接受。 |
| Control Move | `effects[]`、`seal_basis` | `seal_ref`、`auth_context` | 只写 control plane cell；进入 pending control set，直到被有效 Seal 覆盖才 `sealed`。 |

`preconditions[]` 仅属于 Control Move。DataEvent 不使用全局 CAS precondition；需要强单值、硬配额、跨 cell 原子性或不可自动合并语义的对象，MUST 在 Realm schema 中声明为 control plane（或使用专门 per-object sequencer），不得伪装成轻量数据面写入。

### 2.1 DataEvent

DataEvent 是数据面写入。它的核心字段如下：

| 字段 | 含义 |
| --- | --- |
| `effects[]` | 数据面 cell 的 Lattice 操作；每个目标 cell 的 Realm schema MUST 声明 `plane="data"`。 |
| `seal_ref` | 已接受的 Seal id，表示授权验证使用的控制面基准。 |
| `auth_context` | 签名 DID、key epoch、可选 credential epoch 与 capability refs。 |
| `causal_refs[]` | 业务因果 hash 引用；用于投影、线程、排序与缺依赖诊断，不证明范围完整性。 |
| `refs[]` | 语义引用；例如 `authorized_by`、`parent_event`、`attestation`、`after`。 |

DataEvent 验证通过后可以立即进入本地 accepted set、fanout、同步和投影。Seal 后续 MAY 观测到该 DataEvent，并通过 `data_event_set_root` 或 `data_view_root` 暴露 `observed` 证明；未被观测不否定该 DataEvent 的签名事实和本地可接受性。

### 2.2 Control Move

Control Move 是控制面写入。它的核心字段如下：

| 字段 | 含义 |
| --- | --- |
| `seal_basis.leaves[]` | 签名时采用的 Seal leaf 集合。 |
| `seal_basis.control_event_set_root` | 该基准 view 中控制面 Event digest 集合根。 |
| `seal_basis.state_root` | 该基准 view 中控制面 cell root。 |
| `preconditions[]` | 可选控制面 pre-state predicate。 |
| `effects[]` | 控制面 cell 的 Lattice 操作；每个目标 cell 的 Realm schema MUST 声明 `plane="control"`。 |

Control Move 的签名、actor chain、basis、precondition 和授权验证通过后，服务 MAY 返回 signed receipt 表示已经进入控制面待检查集合。它只有在有效 Seal 覆盖其 digest 且 `state_root` 重算一致后，才成为 `sealed`。

### 2.3 actor-private 与 ephemeral 边界

`actor_private_event` 仍使用 signed Event Envelope，但不写 shared Realm data/control cell，不进入控制面 Seal 覆盖集，也不影响其他成员的共享状态。它可以用于 account data、device route、个人偏好或 actor 私有投影。

`ephemeral_event` 不使用 Event Envelope；presence、typing、call signaling、to-device key verification 等使用专用 envelope 或 device message schema。接收方 MUST NOT 把 ephemeral envelope 解释为 durable Event、不得分配 shared `actor_seq`、不得写 cell、不得进入 Seal。

| `wire_scope` | 允许 schema | 允许提交路径 |
| --- | --- | --- |
| `durable_event` | `ck.schema.event.v1` | `ck.self.events.command.submit`、`ck.peer.events.command.submit` |
| `actor_private_event` | `ck.schema.event.v1`，但不得携带 CBA reducer 字段 | `ck.self.events.command.submit` 的 actor 私有路径 |
| `ephemeral_event` | `ck.schema.ephemeral_envelope.v1` 或 `ck.schema.device_message.v1` | ephemeral / to-device 专用路径 |

## 3. 接收与验证

任何接收 Event Envelope 的 Events API 或 Sync Service，MUST 先执行通用验证：

1. JSON schema validation。
2. canonical bytes 与 `proofs[]` 校验；proof signer MUST 对应 `actor_id`，或在 `executed_by` 场景下对应代理身份并满足 `authorization_ref`。
3. `event_id` 与 canonical bytes 的幂等冲突检测。
4. `actor_seq`、`prev_refs[]` 与 actor chain 连续性验证。
5. `realm_id`、kind registry、payload schema、critical extension 与 reducer profile 支持性验证。

通用验证通过后，按 CBA 类型分流。

### 3.1 DataEvent 验证

接收方 MUST：

1. 确认 Event 携带 `effects[]`、`seal_ref`、`auth_context`，且不携带 `preconditions` 或 `seal_basis`。
2. 确认 `seal_ref` 指向本 Realm 已接受的 Seal。
3. 在该 Seal 的控制面 `state_root` / KeyView 下验证 DID、key epoch、credential epoch、capability refs、policy、membership、Realm lifecycle 与 object scope。
4. 按 Realm 的 `revocation_freshness_window_ms` 判定该 `seal_ref` 是否仍可作为数据面授权基准；无法确认撤销新鲜度的高风险写入 MUST fail closed。
5. 确认每个 effect 只写 data plane cell，且 cell family 的 Lattice 操作合法。
6. 将 DataEvent 纳入本地 data accepted set，并按 cell Lattice join 重算数据面 projection。

DataEvent 的安全问题主要是签名伪造、授权过期、写入不属于 data plane、以及不可合并冲突。签名伪造由 DID/key 与 Event proof 解决；授权基准由 `seal_ref` 解决；事件冲突由 Lattice / CRDT / bottom diagnostic 解决。

### 3.2 Control Move 验证

接收方 MUST：

1. 确认 Event 携带 `effects[]`、`seal_basis`，且不携带 `seal_ref` 或 `auth_context`。
2. 确认 `seal_basis.leaves[]` 均为已接受 Seal，且合成 view 的 `control_event_set_root` 与 `state_root` 与 Event 内声明一致。
3. 在该 control basis 下验证 signer、capability、policy、membership 与 Realm lifecycle。
4. 求值 `preconditions[]`；任一 predicate 不成立则拒绝该 Control Move。
5. 确认每个 effect 只写 control plane cell。
6. 将该 Control Move 放入控制面 pending set，等待 Seal 覆盖。

Control Move 被有效 Seal 覆盖后，接收方重放控制面覆盖集，计算 control cell Lattice 与 `state_root`。root 匹配则该 Move 进入 `sealed`；root 不匹配或 Seal 签名、slot、delta、root、batch 验证失败，则拒绝该 Seal 并产生问责证据。

### 3.3 Seal 验证

Seal 的 wire contract 见 [`seal.schema.json`](../../artifacts/schemas/seal.schema.json)，完整语义见 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md)。

接收方 MUST 至少验证：

- notary / committee 签名与 signer sequence。
- predecessor / slot / profile 约束。
- `delta[]` 只包含本 Seal 新增的控制面 Event digest。
- `control_event_set_root` 与递归控制面覆盖集一致。
- 控制面 reducer 重放后的 `state_root` 与 Seal 声明一致。
- inclusion list / receipt obligation / fault evidence 规则。

`data_view_root`、`data_event_set_root` 和 `availability_root` 只证明 notary 在该 Seal 观察到的数据面集合或可用性材料；它们不得用于改变 DataEvent 的控制面授权结果。

## 4. Event-first 发布模型

```mermaid
flowchart TB
    subgraph P ["Producer"]
        P1["build signed Event"]
        P2["DataEvent: effects + seal_ref + auth_context"]
        P3["Control Move: effects + seal_basis"]
        P1 --> P2
        P1 --> P3
    end

    subgraph S ["Principal Server / Sync Service"]
        S1["schema + signature + actor chain"]
        S2["DataEvent verify at seal_ref"]
        S3["Control Move verify at seal_basis"]
        S4["data accepted + fanout"]
        S5["control pending"]
        S6["Seal covers control"]
        S1 --> S2 --> S4
        S1 --> S3 --> S5 --> S6
    end

    subgraph C ["Consumer"]
        C1["sync events / receipts / seals"]
        C2["data Lattice / CRDT projection"]
        C3["control state_root verification"]
        C4["query grade: local / seen / observed / sealed"]
        C1 --> C2 --> C4
        C1 --> C3 --> C4
    end

    P --> S --> C
```

规范要点：

- Producer 与 Consumer 都可以从 signed Event 与 Seal proof 独立验证历史。
- Sync Service 是传播与投影服务，不是签名事实的来源；它不能伪造 actor Event。
- DataEvent 可以离线产生，但必须选择一个可验证且足够新鲜的 `seal_ref`。
- Control Move 的 finality 来自 Seal，而不是到达顺序。

## 5. 批量提交与 partial accept

`ck.self.events.command.submit` 与 `ck.peer.events.command.submit` MAY 接收 `events[]` 批量。批处理的最小原子单元是单个 Event；一个 Event 的失败不得回滚同批已接受 Event。

`events[]` MUST 按数组顺序处理。同批中已接受的前序 Event 仅可作为后续 Event 的解析材料：

- 可以解析 bytes、Event ID、actor chain、`prev_refs[]`、`causal_refs[]` 或 payload-level causal reference。
- 不得作为后续 Event 的授权基准。
- DataEvent 的授权基准始终是该 Event 自己的 `seal_ref`。
- Control Move 的授权与 precondition 基准始终是该 Event 自己的 `seal_basis`。
- 同批前序 Event 创建、delegate、恢复、扩权或 revoke 的 grant/policy，不会在同批后续 Event 的授权判定中提前生效。

后续 Event 若依赖同批失败、缺失或隔离的 Event，MUST 以 `dependency_missing`、`causal_conflict`、`capability_denied`、`soft_failed` 或等价原因拒绝或隔离。

**后向引用（同批数组顺序靠后）的判定（normative）**：当某 Event 的 `prev_refs[]` / `causal_refs[]` 指向**同批中数组顺序在其之后、尚未处理**的 Event 时，实现 MUST 在单遍按序处理到该 Event 时一律判 `dependency_missing`（或隔离待重交），MUST NOT 为满足同批后向引用而对批做整批拓扑重排。这把"按数组顺序处理"与"前序作解析材料"在 reorder 下的歧义锁死为确定行为：同批解析材料只覆盖数组靠前已处理的 Event，靠后未处理的引用一律视为缺依赖。提交方应自行按因果序排列 `events[]`，缺序时通过重交（`accepted ∪ duplicate` 求差后重提）收敛，而非依赖服务端重排。

批量响应 MUST 区分：

| 字段 | 语义 |
| --- | --- |
| `accepted[]` | 首次接受的 Event。 |
| `duplicate[]` | canonical bytes 完全一致的幂等重复。 |
| `rejected[]` | 已确定失败的 Event。 |
| `quarantine[]` | 因缺 proof、缺依赖、缺可用性或异步验证而暂不能决定的 Event。 |

`status=accepted` 仅当 `rejected[]` 与 `quarantine[]` 均为空且 `accepted[]` 非空。全部为幂等重复时使用 `status=duplicate`。其他混合结果使用 `status=partial`。

## 6. Receipt、可用性与完整性证明

Event 是 canonical history；receipt、attestation、snapshot 与 Seal observation 是加速层或审计证明，不替代 Event 自身签名。

### 6.1 SeenReceipt

SeenReceipt 证明某服务、客户端或 witness 已看到某 Event digest。SeenReceipt 可用于 read-your-writes、跨服务对账、轻客户端同步与 censorship 诊断；它不证明该 Event 已进入控制面 finality。

### 6.2 AvailabilityReceipt

AvailabilityReceipt（schema [`availability-receipt.schema.json`](../../artifacts/schemas/availability-receipt.schema.json)）证明 holder 在某 retention window 内承诺保存指定 Event bytes 或 blob bytes。它可被 Seal 的 `availability_root` 观测，查询等级为 `observed` 或 `witnessed`，但不替代事件签名、授权验证或 Lattice 收敛。

### 6.3 Event Batch Receipt

Event batch receipt 是 best-effort RYW / 加速 / 审计 hint，只对 issuer 选择承诺的事件集合提供 integrity，不提供范围 completeness。接收方 MUST 能在没有 batch receipt 的情况下验证单个 Event。

### 6.4 Range-bound Completeness Attestation

需要证明“某范围内没有漏给事件”时，必须使用带显式 range 的 attestation：per-actor seq interval、from/to frontier、root、count 与 witness quorum。Set-bound Merkle commitment 只能证明集合未被篡改，不能证明范围未被删减。

## 7. 同步面

同步面以可见性裁剪后的 Event、receipt、Seal、snapshot 与 projection delta 组成。

| 面 | 用途 |
| --- | --- |
| Event Source Sync | actor 历史恢复、审计重放、事件查缺。 |
| Realm Sync | Realm 级 durable Event、Seal 与 projection 增量。 |
| Strand Sync | Strand 当前态、track 状态、可见性裁剪后的 activity。 |
| Discussion Sync | Strand discussion 轨道消息时间线。 |
| Board Sync | Board/List/Strand 位置与排序 projection。 |
| Query Surface | view、搜索、context timeline 与 graph 查询。 |
| Authz / Invite Surface | invite、grant 视图、控制面状态与可写性诊断。 |

Strand Sync MUST NOT 因 actor 可读 Strand synthesis 就自动展开不可读 discussion timeline 或 Morph 内容。所有同步面都 MUST 先按 Realm、Circle、object scope、history visibility、E2EE availability 与 caller capability 裁剪。

## 8. 查询等级

查询响应 SHOULD 带 `basis`，说明结果基于哪个 Seal 与何种等级。

| grade | 语义 |
| --- | --- |
| `local` | 本地尚未获得外部 receipt 或观测。 |
| `seen` | 至少一个服务或 witness 对 Event 签发 SeenReceipt。 |
| `observed` | DataEvent 或 availability material 被 Seal 的观测 root 覆盖。 |
| `sealed` | Control Move 被有效 Seal 覆盖并进入控制面 `state_root`；仅控制面使用。 |
| `witnessed` | 独立 witness quorum 对范围、frontier 或可用性签发证明。 |
| `forked` | 同一 actor chain、notary sequence、control frontier 或 object invariant 出现可证明分叉。 |
| `stale` | 查询基准落后于 freshness policy，需要刷新控制面或降级显示。 |

实现 MUST NOT 把数据面 `observed` 标为 `sealed`。

## 9. 冲突与收敛

Cokret 不用全局链决定普通协作写入顺序。状态收敛由 cell family 的 Lattice / CRDT 规则定义：

- OR-Set、ordered log、RGA、PN-counter、escrow counter 等可合并 cell MUST 对输入顺序不敏感。
  > **序列 CRDT 选型注记（informative）**：上面把 **RGA（Replicated Growable Array）** 列为序列 cell 的示例算法。RGA 有学界充分记录的**并发插入交错（interleaving anomaly）**——两个 actor 在同一位置并发插入文本时，字符可能交错成乱序串。RGA 不是协作富文本的"最佳实践"基线：实现协作文本（`ck.profile.collaborative_text.v1`，见 [`../conformance/conformance-profiles.md` §3](../conformance/conformance-profiles.md)）时 SHOULD 优先采用消除 interleaving 的现代序列 CRDT —— **Eg-walker（Event Graph Walker，diamond-types）**、**Fugue/Peritext**（后者并处理富文本 mark 并发）或 **Loro/Yjs(YATA)**。其中 Eg-walker 在 event graph 上重放求值，与本规范的 event/causal-graph 范式天然同构、落地阻抗最小。序列 CRDT 仅活在该 opt-in extension profile、不进 core wire，因此算法升级是 profile 内的加法（新 lattice 标识 + 新 conformance vector / 新 `ck.profile.collaborative_text.v<n>`），不破坏任何 v1 core 签名字节。
- 单值、硬配额、跨 cell 原子性和不可交换操作不得放在 data plane，除非使用专门 sequencer。
- 并发不可合并时，reducer MUST 产生 structured bottom / conflict diagnostic，而不是用 HLC、actor id、数据库自增 ID、本地到达顺序或 Sync Service 顺序挑选 winner。
- Timeline 展示顺序是 projection，MUST NOT 反向写入 canonical state、授权判断或 Lattice winner。

DataEvent 的 `causal_refs[]` 可以帮助投影层稳定排序和诊断缺依赖；它不是全局 completeness proof。

## 10. Snapshot

Snapshot 是恢复加速层，不是真相源。Snapshot manifest MUST 声明以下字段（权威必填集见 [`../conformance/snapshot-schema.md`](../conformance/snapshot-schema.md) 与 [`snapshot.schema.json`](../../artifacts/schemas/snapshot.schema.json) 的 `required`，本清单与之等价）：

- `id`（snapshot 自身 id）
- `realm_id`
- `reducer_profile` 与 `schema_profile_refs`（reducer / schema profile refs）
- `state_digest`（投影状态根：data projection root 或 control `state_root`，按 `security_class` 确定，**必填**）
- `event_set_commitment`（绑定"哪些事件产生该状态"的承诺，与 `state_digest` 各自独立、**均必填**；客户端采用前 MUST 验证它，见下）
- `frontier`（covered Event frontier / Seal basis）
- `chunks`（chunk digests）
- `security_class`
- `created_by`（issuer）与 `created_at`
- `authority_binding`（证明 `created_by` 在 `created_at` 被授权签发该 snapshot）
- `signature`

客户端采用 Snapshot 前 MUST 验证 signature、chunk digest、profile compatibility、basis freshness、Event set commitment 与必要 inclusion / omission challenge。验证失败时 MUST 丢弃 Snapshot 并回退到原始 Event / Seal 回放。

Snapshot 后续恢复流程：

1. 获取 Snapshot manifest。
2. 验证 issuer 与 proof。
3. 下载并验证 chunks。
4. 从 Snapshot frontier / Seal basis 之后拉取 Event 与 Seal。
5. 重放 DataEvent Lattice 与控制面 Seal。
6. 进入增量订阅。

## 11. 首次加入 Realm

**加入提交目标（normative）**：跨域加入时"向哪台服务提交 join material"的唯一权威来源是 `ck.find.directory.query.resolve_realm` / `ck.find.directory.query.resolve_target` / signed invite metadata 返回的 `join_candidates[]`（规范定义见 [`federation.md` §5.0](./federation.md)）。客户端 / 提交服务 MUST NOT 从 Realm ID、邀请者所在 Principal Server、被邀请者自己的 Principal Server 或 URL 路由提示推导加入提交目标；所有重试 MUST 绑定同一 canonical `realm_id`。

推荐流程：

1. 解析 Realm metadata 与 service binding；按 [`federation.md` §5.0](./federation.md) 取得 canonical `realm_id` 与 `join_candidates[]`，并以 `join_candidates[]` 作为 join material 的提交目标。
2. 获取与 caller 相关的 invite、claim、grant 或 presentation challenge。
3. 拉取当前 Seal 与必要控制面 proof。
4. 验证 membership / capability / policy。
5. 拉取最近 Snapshot（可选）并验证。
6. 从 snapshot basis 或当前 Seal 之后拉取 Event。
7. 本地重放并进入 cursor 增量订阅。

若客户端只有 handle 而没有 DID，必须先完成 handle -> DID 解析与双向校验；handle 不得直接作为 actor 或 grant subject。

## 12. 幂等、去重与重放

重复提交与重复投递是正常情况：

- `event_id` MUST 全局稳定。
- 同一个 `event_id` 的完全相同 canonical bytes MAY 被重复接收，并作为幂等成功处理。
- 同一个 `event_id` 对应不同 canonical bytes 时，节点 MUST 拒绝并返回 `duplicate_conflict`，同时保留最小冲突证据。
- Sync Service SHOULD 以 `event_id` 与 `event_digest` 去重，而不是以到达次数计数。

## 13. 授权时序

授权不能只看墙上时钟。CBA 的授权时序规则是：

- DataEvent 按自身 `seal_ref` 指向的控制面 Seal 验证授权。
- Control Move 按自身 `seal_basis` 指向的控制面 view 验证授权和 precondition。
- revoke、grant、membership、policy 与 lifecycle 的可见性由控制面 Seal 拓扑和 `revocation_freshness_window_ms` 判定。
- 同批提交不会让授权变更提前影响后续 Event。
- 无法解析必要控制面 proof 或 freshness 的写入 MUST fail closed 或 quarantine，不得按 HLC、本地到达顺序或服务端当前数据库猜测授权有效。

## 14. 可见性、密文负载与 E2EE 索引

ACL 不等于密文保护。Sync Service 可以转发不透明密文，但不得把未授权的明文元数据暴露给未被 policy 委托的服务。

字段可见性分级：

- Event Envelope 顶层路由、因果与签名归属元数据：`event_id`、`realm_id`、`kind`、`prev_refs[]`、`causal_refs[]`、`refs[]`、`actor_id`、`actor_seq`、`hlc`、`seal_ref` 或 `seal_basis`、以及 schema 声明的 `executed_by`、`authorization_ref`、`applet_id`、`external_ref`、`actor_kind`、`effective_scope`。
- 明文业务元数据：轻量状态、rank、due date 等；若足以暴露敏感内容，接收服务必须列入 Realm policy 的 plaintext-visible service。
- 不透明加密负载：message body、附件内容、私有对象字段等。

MLS / E2EE 语义见 [`encryption-and-audit.md`](../crypto-media/encryption-and-audit.md)。控制面 MLS epoch 属 Control Move；普通加密消息仍是 DataEvent。

## 15. 设计决定

Cokret v1 固定：

- signed Event Envelope 是 actor 发布单元。
- DataEvent 是普通协作数据面的默认写入单元。
- Control Move 是治理状态和强不变量的写入单元。
- Seal 只给控制面 finality；对数据面的 root 是观测承诺。
- Event 签名、DID/key 验证和 capability 检查解决伪造事件问题。
- 数据面的核心分布式问题是冲突、可用性、可见性与观测证明；冲突由 Lattice / CRDT / bottom diagnostic 解决。
- 密文负载可以由不解密的 Sync Service 转发。
- hard erasure 只能删除本地 payload / blob / 派生内容，并保留事件图验证所需的最小 verification stub；不得重写 Event hash 或伪装事件从未存在。

## 16. 规范性引用

- CBA 双平面、Seal、query grade 与 failure state 见 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md)。
- Event Envelope、canonical bytes、Patch 与 proof 见 [`event-and-patch.md`](../models/event-and-patch.md)。
- HTTP operation binding 见 [`service-http-binding.md`](./service-http-binding.md)。
- Federation transport 见 [`federation.md`](./federation.md)。
- Cursor 编码、digest suite 与 HLC 见 [`encoding.md`](../conformance/encoding.md)。
- Strand / Message、Realm / Space / Morph 语义见 [`strand-and-message.md`](../models/strand-and-message.md)、[`realm-and-space.md`](../models/realm-and-space.md) 与 [`morph.md`](../models/morph.md)。
