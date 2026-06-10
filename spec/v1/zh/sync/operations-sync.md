---
title: Operations And Sync
status: candidate
normative: true
stability: v1
updated: 2026-06-10
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

## 1. 目标（Goals）

Cokret 是面向协作对象的分布式发布、传播、查询与收敛协议。

同步层必须支持：

- actor 侧可验证发布
- append-only 审计日志
- Flow identity 与 track 能力
- Flow `discussion` track / Message 时间线
- Board Space / List Space / Flow 工作流
- Morph 开放对象
- 离线写入
- 最终一致收敛

## 2. 核心角色

Cokret v1 区分：

- `client`
- `agent`
- `event_store`
- `principal_server`
- `sync_service`
- `blob_store`

### 2.1 Event Store 与 reducer-input Event

Cokret v1 的唯一 wire / 传输单位是 **signed Event**（schema 见 [`event-envelope.schema.json`](../../artifacts/schemas/event-envelope.schema.json)）：reducer-input event 把 `preconditions[]` / `effects[]` / `anchor_ref` 直接放在 event 顶层；non-reducer event（read cursor、typing 等）不携带这三个字段。actor-chain 因果用顶层 `prev_refs[]`；其他语义引用（授权、attestation、recovery_capability、state_witness、inclusion_proof 等）统一进 `refs[]`，每条带 `role`。

Reducer-input event 的核心字段（详见 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §3）：

| 字段 | 含义 |
| --- | --- |
| `event_id` (`ck:event:<uuid>`) | producer 在签名前分配的 typed-UUIDv7。被纳入 canonical bytes 由 `proof.event_digest` 覆盖。 |
| `actor_id` | 签发者 DID。 |
| `realm_id` | 所属 Realm。 |
| `actor_seq` | actor chain 单调序号。 |
| `prev_refs[]` | actor chain 因果前序。 |
| `refs[]` | 语义引用集合，每条 `{id, role, critical?}`；授权 ref 用 `role="authorized_by"`，其他 role 包括 `attestation` / `parent_event` / `after` / `recovery_capability` / `state_witness` / `inclusion_proof`。 |
| `preconditions[]` | reducer-input only：`[(cell, predicate)]`。任一不成立则整个 event FAIL。 |
| `effects[]` | reducer-input only：`[(cell, lattice_op)]`。原子多 cell CAS。 |
| `anchor_ref` | reducer-input only：本 event 提交时所对应的 Anchor DAG 节点。 |
| `payload` | kind-specific 业务载荷（`ck.message.create.payload.content`、`ck.flow.update.payload.patch` 等）；它们是 effect 写入值的源数据，不替代 effects[]。 |
| `proofs[]` | 至少一条 detached JWS，覆盖 canonical event bytes（不含 `proofs` 与 `unsigned`）。 |
| `hlc` | advisory tie-breaker。**进入 canonical event bytes 与 proof `event_digest`**（与 [encoding.md](../conformance/encoding.md) §7、[event-auth-state-resolution.md](../authz/event-auth-state-resolution.md) §3 rule 1 一致），因此被生产者签名锁定、relay 不得改写；但语义上仅用于 timeline 展示与 freshness 诊断，MUST NOT 进授权决策、Lattice 收敛、Move precondition 比较或 Anchor finality 判断。 |

非 shared Realm reducer-input 事件（`wire_scope=actor_private_event` / `ephemeral_event`，例如 `ck.read_cursor.advance`、`ck.device.push_route`、`ck.typing`、`ck.receipt.read`、`ck.call.signal`）**不**携带 `preconditions` / `effects` / `anchor_ref`。`actor_private_event` MAY 按 registry 声明写入 actor-private/account-private state cell，但该 cell 不进入 shared Realm Anchor frontier 或 state_root；`ephemeral_event` 不持久化、不写 cell。schema 已用 allOf if/then 静态强制此约束。

Actor-private state 是独立层，不是“弱 durable Event”。标准规则：

- `actor_private_event` 可以写入 principal control stream、account data 或 device/private cell，cell subject MUST 可由 payload / actor / authenticated account 唯一派生，并在 registry 中声明。它使用独立 actor-private stream sequence；若 Event envelope 携带 `actor_seq`，该值只在 actor-private stream 内连续，不与 shared Realm `actor_seq` 空间合并。`prev_refs[]` 对 actor-private stream 的连续性按该私有 stream 校验；first event 或服务端从已验证 checkpoint 之后开始同步的片段 MAY 使用 `prev_refs=[]`，但不得据此豁免 shared durable event 的 §2.6 因果连续性规则。
- actor-private cell 不参与 shared Realm `state_root`、Anchor frontier、membership visibility 或 federation delivery binding；需要跨设备同步时，只在同一 principal / account 授权边界内复制。
- 任何实现想让 actor-private state 影响其它成员的共享视图，必须 emit 一条独立 durable reducer-input Event（例如 moderation decision、watch manage audit pair），不得让投影层直接读取他人的 actor-private cell。
- `ck.device.list_update`、`ck.device.push_route`、`ck.account.blocklist`、contacts remarks / preferences 是该模型的标准例子；typing / presence / call.signal 仍是 ephemeral，不得写 actor-private cell。

### 2.1.1 Wire-Scope 边界（normative）

为避免 ephemeral 信号意外进入持久 Event 流，event-envelope.schema.json 与 ck.self.events.submit MUST 按下表 fail closed：

| `wire_scope`（[`event-kind-registry.json`](../../artifacts/registry/event-kind-registry.json)） | 允许使用的 envelope schema | 允许的提交路径 |
| --- | --- | --- |
| `durable_event` | `ck.schema.event.v1`（[`event-envelope.schema.json`](../../artifacts/schemas/event-envelope.schema.json)） | `ck.self.events.submit` |
| `actor_private_event` | `ck.schema.event.v1`（同上；不携带 `preconditions/effects/anchor_ref`，payload 仍按 kind-specific schema 校验） | `ck.self.events.submit`（actor 私有，写入 actor 私有 store 或 registry 声明的 actor-private state cell；不进 Realm frontier） |
| `ephemeral_event`（`ck.presence` / `ck.typing` / `ck.receipt.read` / `ck.call.signal`） | `ck.schema.ephemeral_envelope.v1`（[`ephemeral-envelope.schema.json`](../../artifacts/schemas/ephemeral-envelope.schema.json)） | `ck.self.ephemeral.send`（HTTP `POST /_cokret/self/ephemeral`）或等价已声明 binding；fanout 通过 sync subscribe 实时流、presence/typing fanout、call signaling channel；**MUST NOT** 出现在 `ck.self.events.submit` |
| `ephemeral_event`（`ck.key.verification.*` — 点对点 to-device） | `ck.schema.device_message.v1`（[`device-message.schema.json`](../../artifacts/schemas/device-message.schema.json)） | to-device 队列（不广播）；**MUST NOT** 出现在 `ck.self.events.submit` |

规则：

1. `ck.self.events.submit` MUST 对 `kind` 的 `wire_scope=ephemeral_event` 立即 `schema_violation`，不进 reducer / anchor pipeline。event-envelope.schema.json 已用 `not` 分支静态强制 ck.call.signal / ck.presence / ck.typing / ck.receipt.read / ck.key.verification.* MUST NOT 出现在 durable Event Envelope。
2. ephemeral 广播信号 MUST 通过 `ck.self.ephemeral.send` 或等价已声明 binding 发送，MUST 携带 `expires_at` 并由接收方按 schema 中 5 分钟硬上限丢弃；不得作为 backfill / sync replay 入口。
3. 接收方 MUST NOT 把 ephemeral envelope 解释为 reducer 输入：它们不写 cell、不推 anchor frontier、不消耗 actor_seq。`actor_private_event` 可消耗 actor-private stream seq，但不得推进 shared Realm `actor_seq` / Anchor frontier。
4. 部署若希望"高频信号但仍可审计"，MUST 选择 sample / digest 后单独 emit 一条 durable event（例如 `ck.call.state` / `ck.notification.read`），而不是把 ephemeral envelope 当 durable Event 提交。
5. 负向测试：conformance suite MUST 包含 reject case，把 `ck.presence` / `ck.typing` / `ck.call.signal` / `ck.key.verification.start` 这些 kind 当 durable Event 通过 `ck.self.events.submit` 提交时立即被拒（`schema_violation`，不进 anchor pipeline）。

接收方 MUST 按以下顺序验证 reducer-input event：

1. Envelope schema validation（`ck.schema.event.v1`，含 canonical bytes / proofs[]）。
2. 至少一条 `proofs[]` 由 `actor_id` 控制密钥签发；签名 payload 覆盖 canonical event bytes（不含 `proofs` 与 `unsigned`；`hlc` 包含在内但仅作 advisory）。
3. `verify_event()`（[`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §6）在该 event 的 `anchor_ref` 对应 pre-state 下成立。
4. 写入 Anchor pipeline。

任一步骤失败，整个 event 被 reject 并回退原因（`schema_violation` / `invalid_signature` / `failed_precondition` / `cell_in_bottom_state` / etc.；`failed_bottom` 是 Move/Anchor 的 `event_state`，不是 wire error code）。非 reducer 事件只走步骤 1+2。

### 2.1.2 Event Store

Event Store 是 Principal Server、客户端、本地节点或授权副本保存 Event 的服务/存储能力。它不是独立权威对象，也不是协议一等概念——协议不规定其存储形态或对外接口语义。实现可以用数据库、append-only file、Merkle log、object store、content-addressed block store 或其他存储引擎保存 Event；协议只要求下列语义可验证：

- Event Store Service：保存 signed Event。
- per-actor event chain：由 `actor_id`、`actor_seq` 和 `prev_refs` 表达 actor 自己的发布顺序。
- frontier / cursor：按 actor、Realm 或查询范围暴露调用方可见的同步前沿。
- proof material：签名、hash、DID key 状态引用和可选 witness receipt。
- Anchor view：reducer-input event 集合 + 当前 Anchor DAG + state_root 视图。

网络上的 `/_cokret/self/events/*` 是 Event 提交、读取、回填和前沿查询 API surface。接收方验证 Event 时 MUST 按 §2.1 顺序校验。

实现 MAY 发布 Event batch receipt、checkpoint、snapshot 或 witness receipt 加速恢复和审计，但这些对象不得成为 canonical history 的必经层，也不得替代 Event 本身的签名责任。

### 2.2 Principal Server / Sync Service

Principal Server 是 principal 控制或明确委托的服务边界；Sync Service 是该服务器上的 Realm 增量同步能力。

Sync Service 聚合本服务器授权可见的 Realm Event，并提供订阅、fanout、backfill、ephemeral signaling 和初级过滤。它不是独立第三方服务器，也不应由未被 principal 或 Realm policy 委托的第三方接触非加密私有内容。

Principal Server / Sync Service MUST NOT：

- 伪造 principal 的 Event。
- 把自己托管的 Realm 自动标记为组织 official Realm。
- 用本地数据库状态替代 Realm reducer、capability 和 policy 判定。
- 阻止客户端从源 Event、witness receipt、snapshot frontier 或其他受信 Principal Server 交叉验证历史。
- 将非加密私有正文转发给未被发送方、接收方或 Realm policy 明确委托的服务。

## 3. Event-first 发布模型

Cokret 采用 Event-first 模型：

1. actor/device/service 生成 signed Event。reducer-input event 在顶层带 `preconditions[]` / `effects[]` / `anchor_ref`（§2.1）。
2. `/_cokret/self/events/*` 或等价 transport 接收 event，校验 schema、签名、actor chain；对 reducer-input event 走 `verify_event` + Anchor pipeline。
3. Principal Server / Sync Service 同步调用方授权可见的 Realm Event。每个 reducer-input event 与 Anchor 的当前态 (`event_state` / `anchor view` / `state_root`) 通过同步 surface 暴露给客户端 reducer。
4. client reducer 将 accepted reducer-input event 集合按 Lattice + Anchor frontier 归约为当前态；non-reducer event（read cursor / notification / typing 等）不进 cell。客户端可选择生成本地搜索索引和 View projection。

这套模型同时适用于：

- Flow / Message
- Realm / Space / Flow（看板与列容器是 Space）
- Morph

### 3.1 写入流水线（Write Pipeline）

下图把 Event 从生成到呈现的完整链路画成三段：Producer 生成签名 Event，Principal Server / Sync Service 校验并通过 Anchor pipeline 给出 finality，Consumer 增量同步并本地 reduce + project。Soft-fail 是这条链路上唯一的可逆退化路径。

*Figure 3-1. Event 写入到呈现流水线（informative）。*

```mermaid
flowchart TB
    subgraph P ["Producer（Actor / Device / Client）"]
        direction LR
        P1["build event<br/>reducer-input: preconditions / effects / anchor_ref"]
        P2["sign canonical bytes<br/>proofs[] detached JWS"]
        P1 --> P2
    end

    subgraph S ["Principal Server / Sync Service"]
        direction LR
        S1["/_cokret/self/events/* 接收<br/>schema + signature + actor_seq + prev_refs"]
        S2["verify_event()<br/>capability / policy / Move precondition"]
        S3["Anchor pipeline<br/>frontier 覆盖 → state_root"]
        S4["fanout / 订阅<br/>cursor / 增量"]
        S1 --> S2 --> S3 --> S4
    end

    subgraph C ["Consumer（Client / Agent SDK）"]
        direction LR
        C1["sync stream<br/>events + state_after"]
        C2["reducer<br/>per-cell Lattice join"]
        C3["projection<br/>view / search / inbox / notification"]
        C4["UI / Agent timeline"]
        C1 --> C2 --> C3 --> C4
    end

    P --> S --> C

    SF["soft-fail / quarantine<br/>缺前序 / capability 未到 / Anchor 未覆盖 / cell ⊥"]
    S2 -. "校验受阻（推测态可应用）" .-> SF
    SF -. "backfill → upgrade（保留推测态）<br/>或 reject → 回滚 effects" .-> S2
```

规范要点（_informative_）：

- Sync Service 与 Anchor pipeline 不是真相源，只是按 Anchor finality 暴露 `events + state_after` 的传输面；Producer 与 Consumer 的客户端都可以重算同样的 effective state。
- Consumer 端 reducer 的输入是 accepted reducer-input event 集合 + Anchor frontier；non-reducer event（read cursor / typing 等）不进 cell、不进 state_root。
- soft-fail 路径是 §6.2 的 reconciliation 主题：推测态会被标记，最终升级或回滚都必须确定性。

## 4. Event Batch Receipt / Checkpoint

Event 是 canonical history。Event batch receipt、checkpoint 和 snapshot 只是加速层或审计证明，不是 reducer 输入的替代物。

实现 MAY 为一批已接受 Event 生成签名 receipt。

*Example (informative). Event batch receipt 示例。*

```json
{
  "schema": "ck.schema.event_batch_receipt.v1",
  "receipt_id": "ck:receipt:01964186-5800-7000-8000-000000000000",
  "issuer": "did:web:alice.example.net",
  "receipt_scope": {
    "actor_id": "did:web:alice.example.com",
    "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000"
  },
  "frontier": {
    "actor_seq": 144,
    "event_digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  },
  "events": [
    "ck:event:019640ed-8000-7000-8000-000000000000",
    "ck:event:019640ee-0000-7000-8000-000000000000"
  ],
  "created_at": "2026-04-22T08:30:00Z",
  "proofs": [
    {
      "kind": "detached_jws",
      "alg": "EdDSA",
      "verification_method": "did:web:alice.example.net#receipt-1",
      "payload_digest": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "created_at": "2026-04-22T08:30:00Z",
      "jws": "eyJhbGciOiJFZERTQSJ9..signature"
    }
  ]
}
```

Receipt 可用于 read-your-writes、回放完整性检查、witness 证明或跨服务 backfill 对账。接收方 MUST 能在没有 receipt 的情况下验证单个 Event；也 MUST NOT 因缺少 batch receipt 而拒绝格式、签名、授权和因果均有效的 Event，除非某个高安全 deployment profile 明确要求额外 witness。

### 4.1 Batch Receipt 不证明的事实 (Normative Non-Properties)

Batch receipt 是 best-effort RYW / 加速 / 审计 hint，**不是** range completeness（范围完整覆盖）证明。即使在 `events[]` 上叠加 Merkle commitment（如 `event_set_commitment` / batch root），它也只保证 *integrity*（issuer 给出的事件集合未被中间人篡改），不保证 *completeness*（issuer 没有静默丢弃属于该范围的其他事件）。本节明确列出 receipt 不证明的事实：

- Receipt MUST NOT 被实现解释为“该 `receipt_scope`（actor / realm / frontier）下的所有已 accepted reducer-input event 都包含在 `events[]` 中”。Issuer 可以选择性 commit 任意子集，set-bound commitment 不构成抗丢弃证明。
- Receipt MUST NOT 替代 Event 自身签名作为 reducer 输入合法性凭据：reducer MUST 按 §5 / event-and-patch.md §6 在 Event 层验证签名、prev_refs、refs、anchor 与 schema。
- Receipt MUST NOT 被 Anchor pipeline 当作 canonical history 输入：Anchor 仍以 Event 为真源。
- 想取得 range completeness 的实现，MUST 使用 §4.2 定义的 `ck.attestation.range_completeness` 原语（active event kind；payload schema `ck.schema.range_completeness_attestation.v1`），其 `event_range` 必须有显式 range 语义（per-actor seq interval + frontier 上下界），并伴随 witness quorum 或独立 anchor 背书。Core batch receipt 不承担此职责。

> 术语：*integrity* 指给定数据未被篡改；*completeness* 指给定范围内没有漏给的成员。Set-bound Merkle commitment 提供 integrity，不提供 completeness——后者必须依赖 range-bound 语义。详见 [glossary.md](../overview/glossary.md)。

### 4.2 Range-bound Completeness Attestation (Normative)

`ck.attestation.range_completeness` 是独立的 attestation event kind（见 [`event-kind-registry.json`](../../artifacts/registry/event-kind-registry.json)，`status=active`），用于提供 *completeness* 证明——即"该范围内没有 reducer-input event 被静默丢弃"。它与 `ck.event_batch_receipt`（set-bound integrity）和 `ck.audit.ryw_receipt`（per-event RYW）正交：completeness 需要 range 语义 + per-actor seq interval + witness 背书，缺一不可。

事件 kind 不携带 `.v1` 后缀；版本号只出现在 payload schema id 上。Schema id: `ck.schema.range_completeness_attestation.v1`（artifact `artifacts/schemas/range-completeness-attestation.schema.json`）。

*Example (informative). Range completeness attestation 示例。*

```json
{
  "attestation_id": "ck:attestation:01970a55-0000-7000-8000-000000000000",
  "schema": "ck.schema.range_completeness_attestation.v1",
  "issuer": "did:web:witness.example",
  "issuer_role": "witness",
  "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
  "event_range": {
    "from_frontier": {"realm_frontier": ["ck:event:..."]},
    "to_frontier":   {"realm_frontier": ["ck:event:..."]},
    "actor_seq_ranges": [
      { "actor_id": "did:web:alice.example", "from_seq_exclusive": 144, "to_seq_inclusive": 187 },
      { "actor_id": "did:web:bob.example",   "from_seq_exclusive": 87,  "to_seq_inclusive": 102 }
    ]
  },
  "root": "sha256:...",
  "count": 58,
  "observed_at": "2026-05-18T08:30:00Z",
  "witness_attestation": {
    "kind": "federation_witness_attested",
    "witnesses": [
      {"issuer": "did:web:witness.example",  "verification_method": "did:web:witness.example#range-attest-1",  "controlling_organization": "did:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH:witness.example:coop"},
      {"issuer": "did:web:witness2.example", "verification_method": "did:web:witness2.example#range-attest-3", "controlling_organization": "did:webvh:z2dmjQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn:audit.example:co"}
    ]
  },
  "proofs": [ { "kind": "detached_jws", "alg": "EdDSA", "verification_method": "did:web:witness.example#range-attest-1", "event_digest": "sha256:...", "created_at": "2026-05-18T08:30:00Z", "jws": "..." } ]
}
```

#### 4.2.1 Scope 语义

- `from_frontier` 是 **exclusive** 下界；attestation 覆盖该 frontier *之后* 因果发生的 reducer-input event。
- `to_frontier` 是 **inclusive** 上界。
- `actor_seq_ranges[]` 给出每个在 `(from_frontier, to_frontier]` 区间内产生 reducer-input event 的 actor 的 seq 区间（half-open `(from_seq_exclusive, to_seq_inclusive]`）。MUST 覆盖区间内所有产生 reducer-input event 的 actor；不可遗漏。
- silent fork 经常表现为"某个 actor 的某段 seq 在对端不可见而全局 frontier 仍单调推进"——这就是为什么必须显式 per-actor seq interval，仅有 frontier 不够。

#### 4.2.2 `root` 计算

`root` 是 canonical Merkle root over **scope 内全部 reducer-input event 的 `(actor_id, actor_seq, event_id, event_digest)` 四元组排序集合**：

1. 收集 scope 内每个 actor 在其 seq interval 内的全部 accepted reducer-input event；
2. 对每个 event 形成 leaf `canonical_bytes({actor_id, actor_seq, event_id, event_digest})`；
3. 按 `(actor_id, actor_seq)` 字典序排序；
4. 计算 binary Merkle tree（digest 算法按 Realm.digest_algorithm）；
5. `count` MUST 等于叶子数。

不包含 non-reducer event（read cursor / typing 等）。leaves 排序确定性使 verifier 可以局部 backfill 后独立重算 `root`。

#### 4.2.3 Witness Attestation 与 sovereign-grade 完整性

`witness_attestation` 复用 `ck.audit.ryw_receipt.witness_attestation` 的语义（见 [`../crypto-media/audited-e2ee.md` §4.1](../crypto-media/audited-e2ee.md)）：

- `witness_attestation.kind="federation_witness_attested"` MUST 满足 `witnesses[].length >= 2`、`(issuer, controlling_organization, verification_method)` 两两 distinct、且每个 `issuer` 在 Realm `audit.range_completeness_witnesses[]` 中已声明。
- `witness_attestation.kind="single_source"` 是单签发者的诚实声明，MUST `witnesses.length == 1`。
- 每个 witness 签名 transcript MUST 覆盖完整 attestation scope（`from_frontier`、`to_frontier`、`actor_seq_ranges[]`）、`root`、`count`、`realm_id`、`digest_algorithm`、`observed_at` 和 issuer 身份；不得只签 `root`。否则 verifier 无法区分同 root 不同 scope 或同 scope 不同事件集。
- 对同一 Realm 中存在重叠 scope 的两个 witness attestation，若二者对同一 `(actor_id, actor_seq)` 断言的 `event_id` / `event_digest` 不同，或同一 scope 下 `root` 不一致且无法通过 backfill 证明为不同上界，verifier MUST 将其标记为 `witness_disagreement`，quarantine 相关 range，并停止用该 range 推进 snapshot / backfill / frontier completeness。

**重要**：`single_source` attestation 不构成 sovereign-grade completeness 证明——它只是 issuer 的自报。需要"对方未藏分支"语义保证的部署 MUST 要求 `federation_witness_attested`。这是 silent fork 抗性的最后一道防线：base batch receipt（integrity）+ frontier exchange（probe）+ range-completeness attestation（completeness with witness quorum）才能完整覆盖。

启用 `security_class=high_assurance`、`ck.profile.federation.high_assurance.v1` 或 sovereign / regulated federation profile 的 Realm，range completeness MUST 使用 `federation_witness_attested`；`single_source` 只能作为诊断 hint，不能解除 `dependency_missing`、`stale_peer`、snapshot bootstrap 或 progressive backfill 的 completeness gate。

- 在上述 high_assurance / sovereign profile 下，witness quorum MUST 防止退化为单源背书：每个 witness 的 `controlling_organization` MUST 与该 Realm 的 anchorer（Realm anchor / recovery_anchorer 的 controlling_organization）以及彼此之间两两 distinct，且 SHOULD 跨信任域（不同 `trust_domain`）。任一 witness 与 anchorer（或与另一 witness）共享 `controlling_organization` 的 attestation MUST 拒绝（`audit_receipt_invalidated`），不得用于解除上述 completeness gate——否则名义上的 quorum 实际由单一组织控制，silent-fork 抗性形同虚设。

#### 4.2.4 Verifier 协议

接收方 verifier 验证 attestation 时 MUST：

1. 校验所有 `proofs[]` 与 `witness_attestation.witnesses[].verification_method` 签名；
2. 校验 `witness_attestation.kind` 与 `witnesses[]` cardinality / distinctness / Realm policy 列表一致；任一不通过 `audit_receipt_invalidated`；
3. 校验 `from_frontier` / `to_frontier` 因果一致（`to_frontier` ⊇ `from_frontier`）；
4. 若 verifier 自身持有 scope 内事件，MUST 重算 `root` 并 constant-time 比较；不一致 `range_completeness_root_mismatch`；
5. 若 verifier 只持有 scope 子集，可以验证 inclusion proof（按 standard Merkle inclusion）；不持有任何 scope 事件时只能记录 attestation 不能确认 completeness。
6. 校验 `actor_seq_ranges[]` 中每个 actor 的 seq interval 与 verifier 本地视图（partial replication 后）一致；本地视图若发现缺口而 attestation 声称完整，MUST `range_completeness_actor_seq_gap`。
7. 检测到 `witness_disagreement` 时 MUST fail closed：相关 peer / issuer 的数据进入 quarantine，客户端不得把该 attestation 用于显示“历史完整”、解除 E2EE state mismatch、接受 snapshot 或提交 recovery Move；恢复只能通过更高 quorum、原始 Event replay 或 operator-approved fork resolution 完成。

#### 4.2.5 与其它原语的关系

| 原语 | scope | 提供 | 不提供 |
| --- | --- | --- | --- |
| `ck.event_batch_receipt` | issuer 选择的 events 集合 | integrity（给的没被改） | completeness（没漏给） |
| `ck.audit.ryw_receipt` | 单个 `ck.audit.accessed` event | RYW witness attestation | range coverage |
| `ck.attestation.range_completeness`（本节） | 显式 (from_frontier, to_frontier] + per-actor seq intervals | completeness with witness quorum | per-event payload 解密能力 |

issuer / verifier 应根据需求选取；混用以补强各自边界。

## 5. Wire Event

本节的 **Wire Event** 指术语表中的 [Wire Event / Wire fact](../overview/glossary.md#2-核心术语)：在协议 wire format 中以 canonical bytes + proof 承诺、实际传输 / 存储 / 同步 / 联邦并可进入 reducer 或审计验证的 signed Event Envelope。详细字段与 reducer 语义见 [`event-and-patch.md` §2](../models/event-and-patch.md)。

v1 的规范性共享 wire fact 只有 **Event Envelope / Wire Event**（schema 见 [`event-envelope.schema.json`](../../artifacts/schemas/event-envelope.schema.json)）。Events API、Sync、Federation、Client write 和 reducer 都 MUST 以 `ck.schema.event.v1` 作为共享状态事实输入。Reducer-input event 是这个单层 Event 对象；`Event Envelope` 是 schema / artifact 名称，不表示另有一层 envelope wrapper。

Service operation 名称可以描述提交、同步或联邦动作，但共享 wire fact 仍然只有 Event Envelope / Wire Event。SDK 可以定义本地 builder / draft 对象作为生成 Event 前的中间结构，但这种 builder 不进入协议 wire format，也不出现在 registry / schema 中——它属于 SDK 实现细节，不是 protocol normative 对象。

Event 的 `kind` 是标准事件类型，`payload` 是事件负载，`prev_refs` 表示 actor event chain 前序，`refs[]` 表示语义依赖（含授权 `role="authorized_by"`）。标准 `ck.*` Event kind 不得写入顶层 `type` 或 `payload.type`；`type` 只用于物化对象、外部标准对象或 payload schema 明确声明的 discriminator。`target_ref`、`idempotency_key`、客户端事务 ID 等可放入 `payload` 或 `unsigned`，但不得替代 `event_id`、`prev_refs`、`refs`、`actor_seq` 和签名绑定。

如果事件依赖接收方可能不理解的新语义，发送方 MUST 在 Event 顶层 `requirements` 对象中声明对应 `features` 或 `critical_extensions`。`requirements.{schema, reducer, features, critical_extensions}` 全部 MUST 进入 canonical event bytes、event digest 和 proof `event_digest`。接收方不支持任何 critical feature 时 MUST fail closed，返回 `unsupported_feature`、`schema_violation`、`soft_fail` 或 `quarantine`，不得把事件当作普通已知语义接受。

*Example (informative). Reducer-input event 示例（preconditions / effects / anchor_ref 在顶层）。*

```json
{
  "event_id": "ck:event:019640ed-8000-7000-8000-000000000000",
  "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
  "actor_id": "did:web:alice.example.com",
  "actor_seq": 42,
  "kind": "ck.flow.update",
  "created_at": "2026-04-22T08:30:00Z",
  "hlc": "01970e589d21-0007-a13f9c2e",
  "prev_refs": [
    "ck:event:019640ed-0000-7000-8000-000000000000"
  ],
  "refs": [
    { "id": "ck:grant:0196410c-0000-7000-8000-000000000000", "role": "authorized_by", "critical": true }
  ],
  "preconditions": [
    {
      "cell": "ck:cell:ck.component.flow.metadata.v1:ck:flow:019640c6-8000-7000-8000-000000000000",
      "predicate": { "op": "head_eq", "value": { "metadata.fields.status": "in_progress" } }
    }
  ],
  "effects": [
    {
      "cell": "ck:cell:ck.component.flow.metadata.v1:ck:flow:019640c6-8000-7000-8000-000000000000",
      "op": { "kind": "set", "value": { "metadata.fields.status": "review" } }
    }
  ],
  "anchor_ref": "ck:anchor:sha256:0000000000000000000000000000000000000000000000000000000000000000",
  "payload": {
    "flow_id": "ck:flow:019640c6-8000-7000-8000-000000000000",
    "patch": {
      "metadata.fields.status": "review"
    }
  },
  "proofs": [
    {
      "kind": "detached_jws",
      "alg": "EdDSA",
      "verification_method": "did:web:alice.example.com#device-laptop",
      "event_digest": "sha256:...",
      "created_at": "2026-04-22T08:30:00Z",
      "jws": "base64url..."
    }
  ]
}
```

*Example (informative). Non-reducer event 示例（无 `preconditions` / `effects` / `anchor_ref`，例如 `ck.read_cursor.advance`）。*

```json
{
  "event_id": "ck:event:0196418a-0000-7000-8000-000000000000",
  "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
  "actor_id": "did:web:alice.example.com",
  "actor_seq": 43,
  "kind": "ck.read_cursor.advance",
  "created_at": "2026-04-22T08:30:00Z",
  "hlc": "01970e589d21-0008-a13f9c2e",
  "prev_refs": ["ck:event:019640ed-8000-7000-8000-000000000000"],
  "payload": {
    "id": "ck:read_cursor:0196418a-1000-7000-8000-000000000000",
    "schema": "ck.schema.read_cursor.v1",
    "actor_id": "did:web:alice.example.com",
    "device_id": "ck:device:0196418a-2000-7000-8000-000000000000",
    "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
    "read_scope": {
      "kind": "flow",
      "ref": "ck:flow:019640c6-8000-7000-8000-000000000000",
      "track_name": "discussion"
    },
    "position": {
      "event_id": "ck:event:01964147-0000-7000-8000-000000000000",
      "hlc": "01970e589d21-0008-a13f9c2e"
    },
    "updated_at": "2026-04-22T08:30:00Z"
  },
  "proofs": [{"_comment": "<actor / device proofs over canonical bytes; see encoding.md §6>"}]
}
```

`operation_id` 这个名称只保留给服务 API 的 canonical operation id（例如 `ck.self.account.subscribe`）。Event、reducer input 和 typed ID 字段不得使用 `operation_id` 表达本地对象 ID；SDK 内部草稿对象使用普通 `id` 和可选 `idempotency_key`，且不得进入另一套排序、去重或签名规则。

## 6. 为什么需要 `prev_refs + hlc + actor_seq`

单一时间戳不足以支撑协作收敛。

Cokret v1 要求：

- `prev_refs` 表示 actor event chain 的直接前序
- `hlc` 表示近实时逻辑时间
- `actor_seq` 表示 actor 因果路径高度和防回退索引

三者的职责边界固定如下：

- `prev_refs` / `refs[role=authorized_by]` 是因果事实。HLC 更大不得覆盖缺失或相反的因果依赖。
- `actor_seq` 在同一 actor 的任一因果路径上 MUST 严格递增；它不是 device-local sequence，也不是全局 total order。生产者 MUST 令新事件的 `actor_seq = max(prev_actor_seq) + 1`，其中 `prev_actor_seq` 来自同 actor 的直接 `prev_refs`；恢复 / 导入 profile 可声明例外，但必须把例外写入 `requirements.features[]` 并接受 actor-chain repair 校验。
- 同一 actor 的多个设备或离线写入 MAY 产生同一高度的 sibling fork。接收方若已接受同 actor 更高 `actor_seq`，不得仅因新事件的 `actor_seq` 较低或相同而拒绝；只有当该事件不能从任何已知 frontier 回填为有效历史分支、违反直接前序递增规则、或与同一 `event_id` 的 canonical hash 冲突时，才 MUST reject 或 quarantine。
- 同一高度的 sibling fork 只允许出现在互不因果依赖的分支上。若事件 B 的 `prev_refs` 包含同 actor 事件 A，B 的 `actor_seq` MUST 等于 B 的同 actor 直接前序最大高度加一；两个同 actor、同 `actor_seq` 的事件 MUST NOT 把对方作为直接或间接前序。
- 同一 actor 发布的新 durable Event SHOULD 以其上一个 accepted durable Event 为唯一直接 `prev_refs`。多设备或离线分叉导致多个 actor frontier head 时，生产者 MAY 使用多个同 actor `prev_refs` 合并分支，并 SHOULD 设置 `actor_seq = max(prev_actor_seq) + 1`；接收方 MUST 把 actor frontier 表达为 head set，而不是单个最大序号，并保留 fork / merge 证据按 reducer 规则收敛。
- `prev_refs` 或 `refs[]` MUST NOT 包含当前 `event_id`。任何自引用事件 MUST 以 `causal_conflict` reject。
- 当 `prev_refs` 表示 A 因果先于 B，但 `hlc(A) > hlc(B)` 时，因果顺序仍为 A -> B；实现 MAY 记录 clock skew warning，但不得用 HLC 反转因果。
- 当两个事件之间没有因果路径时，reducer 才可使用 deterministic ordering 中的 HLC / actor / event hash 作为 tie-breaker。

实现 MUST NOT 把 Sync Service 到达顺序、数据库自增 ID 或 HTTP 接收顺序当作协议顺序。

### 6.1 跨 Actor 依赖与确定性排序

Cokret v1 将 Move 依赖关系和 Anchor/Lattice 生效分开处理：

- `prev_refs` 表示 actor chain 因果；`refs[]` 表示语义依赖（authorized_by / attestation / state_witness / ...）。状态收敛以顶层 `preconditions[]`、`effects[]`、`refs[]` 和 Anchor frontier 为准。
- 若事件 B 的 dependency closure 包含事件 A，任何 canonical replay、timeline recovery 或 reducer input normalization 都 MUST 在拓扑上令 A 先于 B；即使 `hlc(A) > hlc(B)` 也不得反转。
- `refs[role="authorized_by"]` 表示授权判定必须能看到对应凭证，不表示被引用 payload 自动覆盖引用者，也不额外提高任何冲突权重。
- 只有当两个 accepted Event 在 dependency graph 中互不可达时，才使用 HLC、Actor ID、`actor_seq`、`event_id` / hash 作为 deterministic total-order tie-breaker。
- 协议状态不再由 reducer 选择 conflict winner。Move precondition 不成立则失败；Anchor 提供 finality；Lattice 对 cell 返回 value 或 `⊥`。Timeline 展示顺序不得被反向用于授权。

因此，跨 actor 的 `refs[role="authorized_by"]` 会创建可验证依赖边界，但不会引入全局共识时钟或服务端接收顺序。

参考验证算法：

```
function validate_actor_seq(event, known_frontiers):
    actor = event.actor_id
    seq = event.actor_seq

    // 规则 1: 直接前序递增
    prev_seqs = [e.actor_seq for e in event.prev_refs if e.actor_id == actor]
    if prev_seqs:
        if seq != max(prev_seqs) + 1:
            reject("actor_seq must equal direct prev_refs max + 1")

    // 规则 2: 防回退 — 低于所有已知 frontier heads 时先回补上下文
    if actor in known_frontiers:
        frontier_heads = known_frontiers[actor]  // head set, not single max
        if all(seq < h for h in frontier_heads):
            soft_fail("actor_seq below known heads; backfill required")

    // 规则 3: 无自引用
    if event.event_id in event.prev_refs or any(r["id"] == event.event_id for r in event.refs):
        reject("self-referential event")

    accept()
```

低于所有已知 frontier head 的事件不应被立即永久拒绝，因为它可能是稍后回补到达的合法历史分支。接收方 MUST 先尝试 backfill 或用可验证 snapshot 证明该事件能连接到某个有效分支；只有在确认无法连接、直接前序递增规则被破坏、或同 `event_id` hash 冲突时，才 reject / quarantine。

该算法只验证 `actor_seq` 语义。完整的 Event 验证还必须包括签名、schema、capability、Realm policy、因果依赖（`prev_refs` / `refs[]` 存在性）和 HLC 合理性检查。

### 6.2 Soft-fail Event Reconciliation

一个 Event 被 soft-failed（受 backfill 等候、causal 上下文未到、frontier 暂时落后）时，本地 reducer / projection 在等待期间 MAY 已经把它的 effects 应用到推测态。当后续 backfill 完成、或 capability / policy 后续发现该 Event 不应通过时，本地状态需要按下表确定性地 reconcile：

| Soft-fail 原因 | 后续判定 | 对本地推测态的处理 |
| --- | --- | --- |
| 缺前序（`prev_refs` 未到） | backfill 完成且签名 / schema / causal 全过 → **upgrade to accepted**；upgrade 后 reducer / projection 不需要重新计算（推测态与最终态一致） | 推测应用 → 标记 `accepted` |
| 缺前序，但 backfill 完成后发现 `actor_seq` 与已知 chain 冲突（`actor_seq` collision、prev hash 不一致） | reject | reducer MUST **回滚** 该 Event 在推测态下产生的所有 cell effects；projection MUST 在下次重算时排除该 Event |
| capability 暂时未知（grant 尚未到达） | grant backfill 后通过 → upgrade；grant 仍缺 / 已 revoke / 已过期 → reject | 同上：通过则升级，reject 则回滚 |
| Anchor 未覆盖（`anchor_ref` 引用未到 Anchor） | Anchor 到达且覆盖该 Move → upgrade；超出 `max_anchor_staleness_ms` 仍未到 → quarantine | quarantine 时不进入 effective state；超时后 reject 走回滚路径 |
| Move precondition 暂时不可解（依赖 cell 处于 ⊥） | ⊥ 修复（conflict-recovery Move）后 precondition 重检通过 → upgrade；precondition 永久 fail → reject | 同上 |

**回滚正确性要求**：

- Reducer 实现 MUST 把"应用 soft-failed Move 的推测 effects"与"应用 accepted Move 的 effects"区分开。最简实现是 **per-cell two-phase materialization**：speculative cells 与 accepted cells 分别计算，最终 effective state 只暴露 accepted。projection 层从 effective state 派生。
- 任何在推测期间产生的副作用（client UI 提示、本地 search index、本地 notification）SHOULD 标注 `pending_event_id` 以便 reconcile 时撤回。重要业务副作用（外发邮件、第三方 webhook、外部 API 调用）MUST NOT 在 soft-failed 状态下触发。
- 同一个 `event_id` 从 `soft_failed` → `accepted` 是单调升级；从 `soft_failed` → `rejected` 触发回滚。**MUST NOT** 出现 `accepted` → `rejected` 的状态退化（除非走 redaction / governance 显式撤回路径，那是新的 Event，不是同一个 Event 状态变化）。
- reconcile 完成后，reducer MUST 重算受影响 cell 的 state_root 并更新本地 frontier；client SHOULD 通过 sync stream 通知 UI 刷新。

合规客户端 MUST 实现该 reconciliation 流程；conformance vector `ck.vector.sync.soft_fail_reconcile.v1`（参见 `conformance-vectors.md`）覆盖 backfill→accepted 与 backfill→rejected 两条路径。

## 7. 标准 Event Kind

标准 `Event.kind` 的机器可读 source of truth 是 `artifacts/registry/event-kind-registry.json`；`schema-registry.md` 只是文档视图。实现必须拒绝未注册、未带 `ck.` 前缀或未在服务端能力清单中声明的标准事件类型。自定义事件不得使用 `ck.` 前缀，除非已纳入标准 registry。

registry 的 `wire_scope` 决定 kind 能进入哪条 wire path：只有 active 且 `wire_scope=durable_event` 的 kind 可以进入共享 Event Envelope 历史、参与 actor chain、推进 reducer frontier 或 state hash；`wire_scope=actor_private_event` 只能用于加密 account data 或 actor-private stream；`wire_scope=ephemeral_event` 只能走 ephemeral channel，MUST NOT 增加 `actor_seq`、`prev_refs`、state hash 或 reducer frontier。生产者不得发出未声明的 wire_scope。

本节只列出 Event-first 写路径中的代表性 durable Event kind，帮助读者理解类别边界；它不是穷举清单，也不替代 registry。完整、可实现的 active durable Event kind 集合 MUST 以 [`event-kind-registry.json`](../../artifacts/registry/event-kind-registry.json) 中 `status=active` 且 `wire_scope=durable_event` 的条目为准。若本节示例与 registry 不一致，registry 是机器可读 source of truth，实现不得因为本节没有列出某个 active kind 就静默拒绝或丢弃它。

逐条 active kind 清单见 [`../conformance/schema-registry.md` §4](../conformance/schema-registry.md)（canonical prose 视图）或站点 `<EventKindTable/>`（直接渲染 `event-kind-registry.json`）。本节只描述各类别的写路径边界。

### 7.1 Realm / Schema / Policy / Discovery

`ck.realm.*` 修改 Realm 自身的生命周期（create / archive / freeze / tombstone / destroy）、policy 与 policy component（policy、policy_server、policy_components、preview_policy、history_visibility、history_sharing_policy、join_rule、plaintext_visible_services 等）、schema 绑定以及 discoverability 状态。`ck.organization.*`、`ck.schema.*`、`ck.policy.*` 是同一治理类别的相邻写路径。这些 kind 的共同写路径约束：只能写入 Realm 级治理 / schema / policy state，MUST NOT 直接写入 Flow / Space / Message 等业务对象正文；policy component 类 kind 各自的 reducer cell 与授权语义见对应 governance / authz 文件。

### 7.2 Flow

`ck.flow.*`（create / update / archive / restore / tracks.update / move / reorder / watch.set 等）只修改 Flow 自身、track 配置或 Flow 在 Board / List Space 中的位置。它们不得直接写入 Message 正文或 Morph 正文内容。Track 不携带独立 access — 启用 / 切换 primary / 修改 track profile / 关闭 track 全部走 `ck.flow.tracks.update`（patch `Flow.tracks` map）；需要独立 membership / history visibility / 投递裁剪或 E2EE 时，把整个 Flow 通过 `Flow.scope_circle_id` 落在一个 [Circle](../models/circle.md)（见 [`../models/flow-and-message.md` §5](../models/flow-and-message.md) 与 [`../models/circle.md`](../models/circle.md)）。`ck.flow.tracks.update` 的 reducer 产物是 Flow `tracks` map 的当前态，而不是新的独立对象。`ck.flow.watch.set` 写入 per-(flow, actor) cas_register cell `ck.component.flow.watch.v1`，是 `watches` Relation 的 truth source（直接 `ck.relation.create relation_kind=watches` MUST schema_violation，见 [`../models/flow-and-message.md` §8](../models/flow-and-message.md)）。

### 7.3 Space

`ck.space.*`（create / update / parent / archive / restore / tombstone）只修改 Space 自身的元数据与生命周期；`archive -> active` 的反向转换由 `ck.space.restore` 承担，不得通过 `ck.space.update` 直接 PATCH 顶层 `state`。`tombstoned` 是不可逆终态，MUST NOT 被 restore。Flow 在 Space 中的位置由 `ck.flow.move` / `ck.flow.reorder` 维护，不写入 `ck.space.*`。

### 7.4 Message

`ck.message.*`（create / revise / redact）与 `ck.reaction.*`（add / remove）写 Message timeline 与 reaction state，受 Realm / Circle effective scope、history visibility 与 E2EE 边界约束。

### 7.5 Morph / Relation / View

`ck.morph.*`（create / update / archive / restore）、`ck.relation.*`（create / update / tombstone）、`ck.container.*`（move_item / rebalance）与 `ck.view.*`（create / update / reconcile）分别写 Morph 对象、Relation 边、facet container 排序与 View 定义。其中 `ck.view.*` 只修改 View definition，例如 query、projection kind、renderer、visible fields、layout、grouping 或 shared saved view 配置。它不得用于保存 Flow 所属 List Space、Flow rank、List Space rank、discussion membership、Message timeline、Relation active state 或对象字段的唯一真相。

### 7.6 Membership / Invite / Capability

`ck.member.state` 承载成员 FSM 与 Realm-scoped delivery binding（见下）；`ck.invite.*`（create / cancel / accept）写 invite 生命周期；`ck.capability.*`（grant / delegate / revoke）写授权图。这些 kind 共同构成 Realm 成员与授权写路径，受 Join Policy / Realm policy 约束。

> `realm.join_policy` / `member.application` / `member.application.review` / `member.application.cancel` 是 **候选**（candidate）workflow concept/action 名称，不是 v1 wire `Event.kind`。它们尚未进入 v1 active conformance；实现声明 v1 base profile 时不强制支持。正式登记进入 v1 registry 前不得使用 `ck.*` 标准前缀，也不得作为 Event envelope 的 `kind`、active reducer 或 sync conformance 项。
>
> new writer MUST 使用 candidate profile surface 而非 bare name。

`ck.member.state{membership="join"}` 除成员 FSM 外，还承载该成员在本 Realm 的 effective delivery binding。`payload.delivery_binding.recipient_service_did` 是 Realm-scoped Event / sync / to-device / push / key package 的投递服务；DID Document 中的默认 `CokretPrincipalServer` 只可在 Realm policy 允许 `did_document_default` fallback 且已物化进该 field 时使用。成员已处于 `join` 时，新的 `membership="join"` Move MAY 作为 delivery rebind self-transition 更新 binding，但必须满足 Join Policy / Realm policy 的 rebind 授权。`payload.delivery_status="unroutable"` 只能在 Realm policy 显式允许不可服务端投递成员时出现。

### 7.7 Profile / Device / Realm Key

本类别覆盖身份与加密写路径：`ck.profile.*`（update / realm_override）、`ck.device.*`（authorize / revoke / list_update）、`ck.mls.*`（keypackage / proposal / commit / commit_failed / welcome）、`ck.realm_key.*`（share / withheld）、`ck.audit.accessed` 与 `ck.redaction`。其中 profile / device / session 控制事件的作用域是 Principal Control Realm，MLS 与 realm_key 事件承载 E2EE 群与历史 key 状态。

`ck.profile.update`、`ck.device.*` 与 `ck.session.grant` 是 durable Event Envelope kind，但其规范作用域是 Principal Control Realm。生产者 MUST 使用目标 principal 的 `principal_control_realm_id` 作为 `realm_id`；普通 Collaboration Realm 只能通过 `refs[role="authorized_by"]`、verified snapshot 或 policy proof 引用这些身份状态，不得把全局 profile、device 或 session 控制事件混入 Collaboration Realm history。Realm 角色分类（Principal Control Realm vs Collaboration Realm）见 [`models/realm-and-space.md` §2.8](../models/realm-and-space.md)。`ck.profile.realm_override` 若作为共享 Realm history 传播，MUST 使用目标 Realm 的 `realm_id` 并通过该 Realm policy；若作为 principal control profile state 传播，MUST 在 payload 中显式绑定目标 Realm。

以下标准 kind 不属于共享 durable Realm history，不能列入本节 durable 写路径：

- `ck.read_cursor.advance`：`actor_private_event`，只能进入 encrypted account data 或 actor-private stream。
- `ck.receipt.read`：`ephemeral_event`，只能走 ephemeral / receipt stream，不推进 `actor_seq`、Realm reducer frontier 或 state hash。

## 8. 操作体原则

非 create 类操作 SHOULD 只携带 delta，而不是完整对象快照。对象字段更新的标准 delta 格式是 `ck.patch.v1`，定义见 [`../models/event-and-patch.md` §4](../models/event-and-patch.md)；实现不得用私有 dot-path 解析规则替代该格式。Event Envelope 中，patch 永远嵌入 `payload.patch`，目标对象用 `payload.flow_id`、`payload.morph_id`、`payload.relation_id`、`payload.view_id` 或该 kind schema 声明的等价字段表达。

Create 类操作若在 `payload.object` 中携带完整 materialized object schema，接收方 MUST 在 schema validation 后执行 cross-field validation：对象创建者字段必须与顶层 `actor_id` / 授权 controller 一致，对象 `created_at` 必须与顶层 Event `created_at` 一致。任何不一致都不得进入 reducer；返回标准 `schema_violation`，或在 controller/guardian 授权缺失时返回 `capability_denied`。

Flow `tracks` 是以 track 名为 key 的 map，patch path 直接使用普通对象段，例如 `tracks.discussion.profile` 或 `tracks.synthesis.is_primary`；不再需要 stable-key selector。对于 profile / 扩展引入的具名集合数组，patch path MUST 使用 schema 允许的 selector 段（`<field>[<key>=<value>]`），不得使用数字下标，因为不同副本上的数组物理顺序不是授权或 reducer 语义。

例如：

- `ck.flow.update` 只带字段变更
- `ck.flow.move` 只带目标 List 和新 rank
- `ck.message.revise` 只带新正文
- `ck.message.redact` 只带目标消息与原因
- `ck.morph.update` 只带 Morph 字段 patch
- `ck.view.update` 只带投影定义 patch；通过 View 触发的对象变更仍使用对应对象 Event kind

### 8.1 Flow Track 写入

`ck.flow.tracks.update` 通过 `ck.patch.v1` 对 `Flow.tracks` map 做任意原子修改——开/关 track、切换 primary、修改 track profile 都走同一条 event。v1 标准 track name 为 `synthesis` 和 `discussion`；profile MAY 声明更多 track name。

```json
{
  "kind": "ck.flow.tracks.update",
  "payload": {
    "flow_id": "ck:flow:01964195-8000-7000-8000-000000000000",
    "patch": {
      "tracks.discussion.enabled": { "$op": "set", "value": true },
      "tracks.discussion.profile": { "$op": "set", "value": "discussion" }
    }
  }
}
```

规则：

- 开 / 关 track 不改变 Flow identity。
- 开 `discussion` track 时，access 完全继承 Flow 的 effective scope（与 synthesis 同 scope）。需要让 Flow 拥有独立 membership / history visibility / 投递裁剪或 E2EE 时，把整个 Flow 通过 `Flow.scope_circle_id` 落在一个 [Circle](../models/circle.md)——`ck.flow.tracks.update` payload 不支持 `access` 子对象，也不修改 `scope_circle_id`。
- Flow synthesis 与 discussion 共享同一 effective scope，可见性同源：`scope_circle_id=null` 时按 Realm-default history visibility；`scope_circle_id` 指向 Circle 时按该 Circle 自身 policy 判断。projection 必须按 effective scope 裁剪。
- Reducer MUST 保证同一 Flow 至多一个 active track 设置 `is_primary=true`。若没有显式 primary，且 `synthesis` 与 `discussion` 同时存在，默认入口 MUST 派生为 `synthesis`。
- 发送 `ck.message.*` 到未启用的 discussion track MUST 返回 `discussion_track_disabled` 或等价 fail-closed 结果。

## 9. Flow 有序操作

### 9.1 `ck.flow.move`

`ck.flow.move` 用于跨 List-Space 移动 Flow。它移动的是 Flow 在一个 Board Space 内的主位置，而不是修改 track 定义。

写入路径是 cas_register cell `ck:cell:ck.component.flow.position.v1:<board_space_id>:<flow_id>`（详见 [`../models/realm-and-space.md` §3.6](../models/realm-and-space.md#36-flow-位置)）。`expected_position` 在 Move 中编译为 cell 的 `head_eq` precondition；`target_space_id` + `rank` 编译为 `set { list_space_id, rank }` effect。Payload 上的目的地输入字段只有 `target_space_id` 一个；MUST NOT 在 `ck.flow.move` payload 上直接写 `list_space_id`（schema `additionalProperties=false` 已经会拒）——`list_space_id` 是 cell value 字段名，由 reducer 从 `target_space_id` 编译而来。这与 Space-parent 的 cas_register 模型对称：tuple dedup 仅作为 projection 不变量，**真相由 cell 决定**，并发竞态收敛为正式 `⊥` 而非"先到先赢"。

```json
{
  "kind": "ck.flow.move",
  "unsigned": {
    "target_ref_hint": "ck:flow:019641a9-8000-7000-8000-000000000000"
  },
  "payload": {
    "board_space_id": "ck:space:019640b6-8000-7000-8000-000000000000",
    "flow_id": "ck:flow:019641a9-8000-7000-8000-000000000000",
    "from_space_id": "ck:space:01d01a00-0000-7000-8000-000000000000",
    "target_space_id": "ck:space:01c3b617-7000-7000-8000-000000000000",
    "rank": "mV",
    "expected_position": {
      "space_id": "ck:space:01d01a00-0000-7000-8000-000000000000",
      "rank": "h0",
      "relation_id": "ck:relation:01005a00-0000-7000-8000-000000000000"
    }
  }
}
```

Reducer 语义：

1. 验证 actor 对 `board_space_id`、`flow_id`、`from_space_id` 和 `target_space_id` 的 move/reorder 权限（落到 Flow 所属 Realm）。
2. 验证 `target_space_id` 是 `board_space_id` 下的 active List Space（`kind="list"` 且 `parent_space_id` 为 board）。
3. 验证目标 Flow 所属 Realm schema/profile 允许它进入该 Board Space。
4. 把 `expected_position` 编译为 cell `ck:cell:ck.component.flow.position.v1:<board_space_id>:<flow_id>` 的 `head_eq` precondition；把 `target_space_id` + `rank` 编译为 `set { list_space_id: target_space_id, rank }` effect。
5. cas_register lattice 在该 cell 上 join：成功则 `target_space_id --contains--> flow_id` 派生 Relation 由 cell value 自动投影出来（旧 list 的派生 Relation 自动失效）；并发不同 set 返回 `⊥`（kind=conflict），依赖该 cell 的后续 Move fail_bottom，必须走 §8 conflict-recovery。
6. 对相同 Event 保持幂等（同一 `event_id` / `event_digest` 的重放是 cell 的恒等 set，不产生新 ⊥）。

`ck.flow.move` 不得把 `board_space_id`、`space_id` 或 `rank` 写入 Flow canonical object 作为唯一真相源；真相是 cell value。View projection MAY 返回这些派生字段，但必须能追溯到该 cell 的 anchored value 和 reducer frontier。

CAS 语义：`expected_position` 描述的是移动前源 Space 中 Flow 的当前位置，编译为 cell 的 `head_eq`：

- `expected_position.space_id` → `head_eq.list_space_id`
- `expected_position.rank` → `head_eq.rank`
- `expected_position.relation_id` 仅作为客户端 hint，不参与 cell join（派生 Relation 的 id 由 reducer 计算）。

不一致时 cas_register 直接返回 `failed_precondition`（走标准 lattice 路径）。`expected_position` 缺失 / 为空 → 等价 `head_eq null`，仅在 cell 真正处于初始态（Flow 尚未进入该 Board）时通过；非初始态下省略 `expected_position` MUST `failed_precondition`，不接受"无 CAS 强制写"。policy 明确允许"无条件覆盖"的特殊场景（如管理员强制重置）必须使用专门的高权限 event kind，而不是省略 `ck.flow.move` 的 `expected_position`。

### 9.2 `ck.flow.reorder`

`ck.flow.reorder` 只改变同一 List Space 内的 rank，不改变 List Space membership。它写入与 `ck.flow.move` 相同的 cell `ck:cell:ck.component.flow.position.v1:<board_space_id>:<flow_id>`，但 effect 的 `list_space_id` MUST 与 `head_eq.list_space_id` 相同（即只更新 rank）；试图通过 reorder 改变 list 的 effect MUST `schema_violation`，必须使用 `ck.flow.move`。

```json
{
  "kind": "ck.flow.reorder",
  "unsigned": {
    "target_ref_hint": "ck:flow:019641a9-8000-7000-8000-000000000000"
  },
  "payload": {
    "board_space_id": "ck:space:019640b6-8000-7000-8000-000000000000",
    "space_id": "ck:space:01c3b617-7000-7000-8000-000000000000",
    "flow_id": "ck:flow:019641a9-8000-7000-8000-000000000000",
    "rank": "mV",
    "expected_position": {
      "rank": "h0",
      "relation_id": "ck:relation:01b03200-0000-7000-8000-000000000000"
    }
  }
}
```

`ck.flow.reorder` 不得改变 List Space。`expected_position` 编译为 cell `head_eq`；不一致时 cas_register 返回 `failed_precondition`，不再走单独的 `cas_conflict` 旁路。客户端 SHOULD NOT 在 Flow 尚未进入该 Board 时发起 reorder；reducer 仅在该初始态接受缺省 `expected_position`，其他情况 MUST 返回 `failed_precondition`。

### 9.3 List Space 排序

List Space 在 Board Space 内的顺序通过 `ck.space.update` 修改 List Space 的 `rank` 字段（或 `ck.space.parent` 调整 `parent_space_id` + rank）来改变。它 MUST NOT 移动 Flow。实现 MUST NOT 使用 `ck.realm.update` 修改 List 排序——Space 不是 Realm，不与 Realm 共享生命周期 / membership / E2EE 边界。

### 9.4 切换 Flow 默认 track

通过同一条 `ck.flow.tracks.update` 原子地启用目标 track 并切换 primary：

```json
{
  "kind": "ck.flow.tracks.update",
  "payload": {
    "flow_id": "ck:flow:019641a9-8000-7000-8000-000000000000",
    "patch": {
      "tracks.discussion.enabled":    { "$op": "set", "value": true },
      "tracks.synthesis.is_primary":  { "$op": "set", "value": false },
      "tracks.discussion.is_primary": { "$op": "set", "value": true }
    }
  }
}
```

规则：

- 要求对应 capability action（`ck.flow.tracks.update`）。
- 不改变 `flow_id`，不删除已有 discussion 历史或 synthesis 字段。
- 切到一个尚未 enabled 的 track 时 MUST 在同一 patch 中将其 enabled 置 true；否则 reducer MUST reject。
- 切换 primary 不自动关闭 discussion track；若要关闭讨论，必须在同一或后续 patch 中显式 `tracks.<name>.enabled: false`。
- Reducer MUST 把目标 track 的 `is_primary` 设为 true，并清除同一 Flow 其他 active track 的 primary 标记。
- 默认 track 切换不自动移除 Board/List 位置；是否移除由后续 `ck.flow.move` / profile policy 决定。

## 10. 验证流程

任何接收 Event Envelope 的 Events API 或 Sync Service，至少应校验：

1. 签名有效。
2. actor DID 可解析。
3. key 在操作时点有效。
4. `realm_id` 与 target object 所属 Realm 一致。
5. capability 在操作时点有效。
6. `prev_refs` / `refs[]` 因果依赖不违反基本约束。
7. 对 Flow / Message / Morph 执行对象类型 schema validation；Board Space 与 List Space 按 Space schema 验证（Space 不是 Realm，不走 Realm schema）。

## 11. Snapshot

Snapshot 是加速层，不是真相源。

Snapshot manifest MUST 包含：

- `id`
- `realm_id`
- `reducer_profile`
- `schema_profile_refs`
- `chunks[]`（每项包含 `chunk_ref`、`digest`、`size_bytes`）
- `state_digest`
- `frontier`
- `event_set_commitment`
- `security_class`（**必填**，`standard` 或 `high_assurance`，无静默默认；需要高保障的 Realm MUST 设为 `high_assurance`，该取值经 `snapshot.schema.json` 的 `allOf` 联动强制下面的 `verification_hints`，并被签名覆盖，故不能在不破坏签名的前提下从 `high_assurance` 降级为 `standard`）
- `verification_hints`（当 `security_class="high_assurance"` 时 MUST 包含 inclusion proof 入口或 witness quorum；`standard` 下可选）
- `created_by`
- `created_at`
- `authority_binding`
- `signature`

客户端在采用 Snapshot 前 MUST 验证：

1. `signature` 是标准 detached proof，覆盖 `id`、`realm_id`、`state_digest`、`frontier`、`event_set_commitment`、`chunks`、`reducer_profile`、`schema_profile_refs`、`security_class`、`verification_hints`、`created_by`、`created_at` 和 `authority_binding` 的 canonical manifest hash（即整份 manifest 去掉 `signature` 后的 JCS bytes，故 `security_class` 不可被降级而不破坏签名）。
2. `signature.verification_method` 对应的 DID 必须是 Realm creator、Realm owner、当前有效 Realm admin、Realm policy 授权的 snapshot issuer 或 witness quorum 成员；该权限 MUST 按 manifest `created_at` 的 as-of auth state 验证，且该 auth state 必须覆盖 snapshot frontier 以及截至 `created_at` 可解析的相关 grant/revoke。若 signer 在 `created_at` 前已被撤销，或 revoke freshness 无法确认，客户端 MUST quarantine / reject snapshot。
3. 每个 chunk 的实际 digest 与 manifest 中声明的 `chunks[].digest` 一致。
4. `event_set_commitment` 的 root 必须与 manifest 声称覆盖的 Event frontier、actor sequence range 和 canonical event hash 集合一致。
5. **Inclusion challenge**：`security_class=high_assurance` 的 Realm MUST 在采用 snapshot 前对抽样 Event ID、actor sequence range、soft-failed / quarantined 摘要执行 inclusion / omission challenge（wire 形态、抽样规则与失败处理见 [`conformance/snapshot-schema.md` §6](../conformance/snapshot-schema.md)）；其他 profile SHOULD。issuer 无法提供合规证明时，客户端 MUST 返回 `inclusion_proof_failed` 并 quarantine snapshot 或回退到原始 Event 回放。Issuer 在 `created_at` 之前已被 revoke 时 MUST 返回 `snapshot_issuer_revoked`。
6. 后续 admin / snapshot issuer revoke 不会自动否定此前在有效权限下签名的 snapshot，但客户端在用 snapshot 恢复后 MUST 继续回放 snapshot frontier 之后的 Event，再用当前 auth state 判断新写入。
7. 若任何校验失败，客户端 MUST 丢弃快照并回退到 `GET /_cokret/self/events?before=<cursor>`（`ck.self.events.query`）进行原始 Event 历史回放。

## 12. 同步面

### 12.1 Event Source Sync

用于 actor 历史恢复与审计重放。

### 12.2 Realm Sync

用于 Realm 级当前态与增量同步。

### 12.3 Flow Sync

用于 Flow 当前态、track 状态、可见性裁剪后的 discussion preview 和 Flow activity projection。

Flow Sync MUST NOT 因为 actor 可读 Flow synthesis 就自动展开不可读 discussion timeline 或 Morph 内容。

### 12.4 Discussion Sync

用于 Flow `discussion` track 的消息时间线、membership 和通知。

### 12.5 Board Sync

用于 Board/List/Flow 当前态、Flow position 和拖拽增量。

### 12.6 Query Surface

用于 view、搜索与 context timeline 查询。

### 12.7 Authz / Invite Surface

用于：

- 拉取 invite
- 拉取有效 grant 集
- 判断某个 Event 在当前 frontier 下是否可写

## 13. 首次加入 Realm

推荐流程：

1. 获取 Realm metadata。
2. 获取与自己相关的 invite / grant 视图。
3. 拉取最近 snapshot manifest。
4. 下载 snapshot chunk。
5. 从 snapshot frontier 之后拉取增量 event。
6. 本地执行 reducer。
7. 进入 cursor 增量订阅。

若客户端没有现成 DID，但只有 handle，则在步骤 1 之前 MUST 先完成 handle -> DID 解析与双向校验。

## 14. 选择性同步

选择性同步至少支持以下过滤维度：

- realm
- flow
- flow track
- board
- list
- object type
- morph type
- relation kind
- watched refs
- changed after cursor

## 15. 幂等、去重与重放

在去中心化同步里，重复提交与重复投递是常态。

因此：

- `event_id` MUST 全局稳定。
- 同一个 `event_id` 的完全相同内容 MAY 被重复接收。
- 若同一个 ID 对应不同内容，节点 MUST 拒绝并返回 `duplicate_conflict`（HTTP 409 / conflict-class reason），同时保留最小冲突证据用于 operator 或 fork-resolution 诊断。
- Sync Service SHOULD 以 `event_id` 去重，而不是按到达次数计数。

## 16. 冲突与收敛

Cokret 初版不引入全网共识链。

它要求：

- 对同一 Realm
- 在同一有效 event 集下
- 所有正确实现的 reducer

最终收敛到相同当前态。

协议状态收敛以 `event-auth-state-resolution.md` 的 Move/Anchor/Lattice 规则为准：Move precondition 不成立则失败，Anchor frontier 决定 effective set，cell Lattice 返回 value 或 bottom。实现不得用 timeline tie-breaker、HLC、actor id、本地接收顺序、数据库自增 ID 或 Sync Service 顺序替代 Lattice 结果。

没有注册 cell family / lattice 的并发对象操作不得产生新的 canonical winner 规则。对象文档若需要唯一 winner，必须声明不可伪造、可复算的 tie-break key（例如 canonical `event_digest` 字典序）并把该规则写入对象规范；否则并发不可合并候选 MUST 输出 bottom / conflict diagnostic，等待显式修复。

客户端 timeline 展示顺序不是协议状态顺序。展示层通常先按 `prev_refs` / `refs` / payload causal refs 的 dependency graph 做稳定拓扑排序，再对互不可达事件使用 `causal_depth`、`hlc`、`actor_seq`、`event_id` 等投影键给出 provisional 顺序。该顺序 MUST NOT 写入 canonical state、`state_root`、授权判断或 winner 选择。

### 16.1 Reducer Contract

Reducer 是确定性纯函数，不是服务端当前数据库状态。对同一 `realm_id`、同一 Anchor frontier、同一 Move set 和同一 reducer profile，正确实现 MUST 产生相同的 `state_digest`、materialized object state、bottom diagnostics 和 reducer frontier。

Reducer 输入：

- accepted Event Envelope 集合及其 canonical bytes / digest。
- 每个 Event 的 `prev_refs`、`refs[]`（含 `role="authorized_by"` 等语义引用）、`actor_seq`、HLC、kind、payload、proof validation result 和 authorization result。
- schema profile refs、reducer profile ref、Realm policy state 和必要 snapshot base。

Reducer 输出：

- materialized object state / state map。
- reducer frontier，表示已纳入当前结果的 Event head set。
- conflict records、redaction records、soft-fail dependency records 和 state hash。

规则：

- Reducer MUST 幂等：重复输入同一 Event 不得改变输出。
- Reducer MUST 对输入集合顺序不敏感；排序只能使用本规范声明的 deterministic ordering。
- Reducer profile MUST 明确声明它处理的 Event kind / Move effect kind、cell family、lattice type、redaction preserved fields、rank/order profile、schema interpretation profile 和 critical extension 行为。
- 两个 reducer profile 只有在 profile id、critical feature 集合、Lattice 规则和字段 merge operator 均匹配时，才可比较 state hash。否则必须声明为不同 projection，不得声称同一 canonical state。
- Partial reducer MAY 用于客户端视图、搜索、通知或只读 projection，但它输出的是 scoped projection frontier，不是 Realm accepted reducer frontier。Partial reducer 遇到不支持但会影响其输出语义的 standard Event kind、critical extension 或 required feature 时 MUST fail closed、返回 `projection_incomplete` / `unsupported_feature`，或降级为明确标注的不完整视图；不得静默忽略后继续声称完整。

## 17. 字段级 merge 与对象级收敛

字段级收敛语义由该字段所属的 cell family / lattice 唯一定义。标量字段、集合字段、排序字段和对象关系不得在本节另行声明通用 merge operator；没有 cell 声明的字段只能作为对象文档明确规定的 projection 输出，不能成为 canonical state 的独立真相源。

例如 `flow.metadata.title`、`flow.metadata.fields.status`、`morph.fields.severity` 这类标量字段是否走 CAS、LWW 或 conflict bottom，取决于其对象文档注册的 cell family；`labels`、`watchers`、`linked refs` 这类集合字段是否走 OR-Set，也必须由对应 cell family 声明。未声明 `ck.profile.collaborative_text.v1` 的实现 MUST NOT 启用 profile-gated `lww_register` / `rga` 语义。

### 17.3 Board position

同一个 Flow 在同一 Board 内的唯一主位置 key 是 `(board_id, flow_id)`，但 canonical truth 不是多条 `contains` / position edge 的 winner，而是 §9.1 定义的 cas_register cell：

```text
ck:cell:ck.component.flow.position.v1:<board_space_id>:<flow_id>
```

同一 key 下出现多个并发且互不兼容的 position write 时，Reducer MUST 按该 cell 的 lattice 规则返回 `⊥`（`bottom=reject`），依赖该 cell 的后续 `ck.flow.move` / `ck.flow.reorder` MUST `failed_bottom`，直到通过 §8 conflict-recovery 或专门的高权限恢复 event 修复。实现 MAY 在诊断投影中列出 competing writes / `conflict_records`，并 MAY 计算一个非规范的临时展示顺序；该展示顺序 MUST NOT 写回 canonical state、不得作为授权或后续 move 的 `expected_position` 真相，也不得替代 cell bottom。

### 17.4 Graph cycle

对象在依赖图、引用图或容器图中产生循环时，Reducer MUST 先使用对象文档声明的 cell lattice 或唯一 winner key 处理。若对象文档没有给出可复算的 winner 规则，Reducer MUST 输出 `⊥` / conflict diagnostic，并把参与非法循环的候选标记为 `rejected_cycle`；不得用 HLC、actor id、本地接收顺序或服务端插入顺序挑选保留边。

## 18. Message

- `ck.message.create` 是 append-only。
- `ck.message.revise` 形成 revision chain。
- 默认视图显示最新可见 revision。
- `ck.message.redact` 保留最小审计字段。

## 19. 授权时序收敛

授权不能只看墙上时钟，否则 revoke、迟到 Event、离线写入都会失真。

Cokret v1 要求：

- grant / delegate / revoke 本身也是 event。
- 某个业务 event 是否有效，由同一 reducer 顺序下的有效授权集合决定。
- 某个业务 event 是否有效，MUST 以该 event 的 `anchor_ref` 对应 batch pre-state 下的授权集合判定。
- 若接收方无法解析该 pre-state、grant/revoke frontier 或必要 inclusion proof，写入 MUST fail closed（soft-fail / quarantine），不得按墙上时钟、HLC 或本地到达顺序推断授权有效性。

## 20. 可见性、密文负载与 E2EE 索引

ACL 不等于密文保护，Sync Service 也不应被迫看懂所有正文。

字段可见性分级：

- Event Envelope 顶层可路由 / 因果元数据：`event_id`、`realm_id`、`kind`、`prev_refs`、`refs[]`、`actor_id`、`actor_seq`、`hlc`、`anchor_ref`。历史草案中的顶层 `type` / `target_ref` 已被 `event-envelope.schema.json` 拒绝；操作目标等路由 hint MUST 放在 payload 的领域字段（例如 `payload.target_ref`）或 `unsigned` 中，不得替代 `event_id`、`prev_refs`、`refs`、`actor_seq` 和签名绑定。
- 明文业务元数据：轻量状态、rank、due date 等；若足以暴露敏感内容，接收它们的受托 search / projection 服务必须列入 `plaintext_visible_services`。
- 不透明加密负载：message body、附件内容等。

## 21. 本地存储建议

客户端 SHOULD 维护三层本地数据：

- raw events
- reduced snapshots
- materialized local indexes

## 22. 设计决定

Cokret v1 固定：

- signed Event Envelope 是 actor 发布单元。
- Event Envelope 是共享状态归约单元。
- Flow / Message、Board / List 工作流、Morph 共享同一同步协议。
- `flow` 是统一协作主对象；默认 track 由 track primary 解析规则表达。
- `synthesis` track 承载整理后的正式表达与推进字段。
- Track 不携带独立 access；整 Flow 共享单一 effective scope（由 `Flow.scope_circle_id` 决定，null = Realm-default，否则指向同 Realm 的 [Circle](../models/circle.md)）。
- invite / grant / snapshot 组成 Realm bootstrap 主流程。
- event 重试必须幂等。
- 授权有效性由同一 reducer 顺序收敛。
- 密文负载可以被不解密的 Sync Service 转发。
- 撤回采用 redaction/tombstone 语义。
- hard erasure 只能删除本地 payload / blob / 派生内容，并保留事件图验证所需的最小 verification stub；不得重写 event hash、额外保留已擦除明文的未加盐 digest，或伪装事件从未存在。
- 冲突通过固定 reducer 规则收敛。

## 23. 规范性引用

- Cursor 编码与 opaque 语义见 `encoding.md`、`../models/common-fields.md` 和 `conformance-vectors.md`。
- HLC 文本格式固定为 `<unix_ms_hex_12>-<logical_hex_4>-<node_id_hash_8>`，排序向量见 `conformance-vectors.md`。
- Snapshot manifest、chunk digest、`state_digest` 和签名规则见 `snapshot-schema.md`。
- Flow discussion track / Message 语义见 [`../models/flow-and-message.md`](../models/flow-and-message.md)。
- Flow / Board / List / Morph 语义见 [`../models/realm-and-space.md`](../models/realm-and-space.md)、[`../models/morph.md`](../models/morph.md) 和 [`../models/views.md`](../models/views.md)。
