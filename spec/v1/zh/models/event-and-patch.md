---
title: Event, Proof, Patch & Receipt
status: candidate
normative: true
stability: v1
updated: 2026-07-02
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

本文集中定义 Arkret 协作图中的**事件 / 签名 / 增量 / 审计 receipt 对象**：

- **Event Envelope**（`ck:event:`）：reducer 输入与审计事实的 wire 表示。
- **Proof**：签名证明 envelope。
- **Field Patch (`ck.patch.v1`)**：非 create 类更新的标准字段增量格式。
- **Event Batch Receipt**（`ck:receipt:`）：可选审计 / 同步加速对象。

CBA 双平面、DataEvent、Control Move、Seal、Lattice、cell 模型、authority chain 与 state 收敛细节由 [`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) 承担；本文聚焦对象级 schema、字段、reducer 总则与 patch 语义。

公共字段见 [`common-fields.md`](./common-fields.md)。

## 2. Event Envelope

### 2.1 概念

> **Reducer**（归约器）：按确定性规则把签名后的 Event 序列计算成当前对象状态——Event 是事实日志，reducer 是把日志"播放"成 Strand / Message / Relation 等当前态对象的引擎。本文 §6 给出 reducer MUST 满足的总则；完整协议模型（DataEvent / Control Move / Seal / Lattice / cell / state resolution 等术语）见 [`../authz/event-auth-state-resolution.md` §3](../authz/event-auth-state-resolution.md)，一行术语条目见 [`../overview/glossary.md`](../overview/glossary.md)。

Event 是 reducer 输入和审计事实。所有协作变化最终都落为签名 `event`。Event 是审计根和 reducer 输入；当前态只是 Event 集合在某个 reducer profile 下的物化结果。

Reducer-input event 按 CBA 分为两类：

- DataEvent：顶层带 `effects[]` / `seal_ref` / `auth_context`，不带 `seal_basis` / `preconditions[]`。
- Control Move：顶层带 `effects[]` / `seal_basis`，可带 `preconditions[]`，不带 `seal_ref` / `auth_context`。

非 reducer event 不带这些 reducer 字段。

Event Envelope 是 kind-routed payload 兼容层。v1 的协议状态收敛以 CBA 双平面、Seal 与 Lattice 为准；Event kind 可以作为 effect kind 与 Events API payload router 的稳定命名。

### 2.2 Schema 与字段

Schema id: `ck.schema.event.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `event_id` | yes | `id:event` | 事件稳定 typed ID。事件 canonical digest / proof hash 见 `conformance-vectors.md`。 | 事件 ID。 |
| `kind` | yes | `string` | 标准 effect kind SHOULD 使用 `ck.` 前缀。Registry 可声明 `cell_family`、`cell_subject`、`lattice` 和 `bottom`，供 CBA reducer 使用。 | 事件 kind。 |
| `realm_id` | yes | `id:realm` | Realm create 可在 payload 中建立。 | 所属 Realm。 |
| `effective_scope` | reducer-stamped | `object` | Reducer 接受 Event 时从 Realm/Circle scope 物化并 immutable 写入 accepted envelope；进入 Seal/sub-seal leaves、E2EE AAD 与 MLS governance binding input。Actor-supplied submit payload MUST NOT 携带该字段，reducer MUST `schema_violation` (`reason=effective_scope_reducer_managed`)。该 reducer-stamped 字段不参与 producer proof 的 `event_digest` 输入（见 §3），其完整性由接受后的 envelope、Seal/sub-seal/AAD 承诺和存储回放规则承担。 | 事件有效作用域。 |
| `actor_id` | yes | `did` | 必须匹配 proof 控制链(`executed_by` 缺失时);`executed_by` 存在时 proof 控制链对齐 `executed_by`。 | 事件归属的 principal of record。 |
| `executed_by` | conditional | `did` | agent / applet / delegated service 代 `actor_id` 写入时出现。出现时 MUST 与 `authorization_ref` 同时出现；Applet delegated 写入还 MUST 同时出现 `applet_id`。进入 canonical bytes、event digest、E2EE AAD。Receiver MUST 校验 proof `verification_method` 解析到 `executed_by`。 | act-on-behalf 时实际签发该 wire write 的主体。 |
| `authorization_ref` | conditional | `id:grant` 或 `id:event` | `executed_by` 存在时必填；Applet-originated 写入携带 `applet_id` 时也必填。优先引用已物化的 `ck:grant:*`；若授权仍以 Event 表达，则引用产生该 grant / delegation 的 accepted Event。Reducer MUST 校验该 grant / delegation 覆盖目标 event kind / resource / fresh approval,并在 effective validity window 内。 | act-on-behalf / Applet grant / delegation 引用。 |
| `applet_id` | conditional | `id:applet` | Applet、Ghost Actor、bridge 或 delegated applet 路径引入 Event 时必填。进入 canonical bytes 与 event digest；出现时 MUST 同时出现 `authorization_ref`。 | signed Applet provenance。 |
| `external_ref` | no | `object` | 外部网络 provenance。若用于回环防护、外部消息幂等、审计或用户可见出处，MUST 放在 Event Envelope 顶层并由签名覆盖；出现时 MUST 同时出现 `applet_id`。不得包含未授权外部正文明文。 | signed external provenance。 |
| `actor_kind` | reducer-stamped | `enum(user, org, team, agent, service, integration)` | 不含 `device`（设备非 actor 主体，见 [`actor.md` §2](./actor.md)）。Reducer 在接受时从 `actor_id` 的 Actor Profile 解析并 immutable 写入 accepted envelope。**Actor-supplied submit payload MUST NOT 携带**,reducer MUST `schema_violation` (`reason=actor_kind_reducer_managed`)。该 reducer-stamped 字段不参与 producer proof 的 `event_digest` 输入（见 §3）。 | 审计 / 离线读取的 actor 类型 projection。 |
| `actor_seq` | yes | `integer` | 同一 actor 因果路径上严格递增；并发 sibling fork 可出现相同高度。 | Actor 链高度 / 防回退索引。 |
| `created_at` | yes | `timestamp` | 不能单独决定因果。 | 创建时间。 |
| `hlc` | no | `string` | `<unix_ms_hex>-<logical_hex>-<node_id_hash>`。**Advisory 字段** — 进入 canonical bytes 与签名以防被中间方重写，但语义上只是 timeline display tie-breaker，不参与 authorization、Lattice join、Control Move precondition 或 Seal finality。详见 `encoding.md` §7。 | HLC（advisory）。 |
| `prev_refs` | yes | `array<id:event>` | 可为空。仅承载 actor event chain causal predecessors。 | Actor event chain 前序。 |
| `causal_refs` | no | `array<hash>` | DataEvent 语义因果前驱 event digest；只表达业务依赖，不提供完整性证明。 | 数据面因果前驱。 |
| `refs` | yes | `array<SemanticRef>` | 默认 `[]`。每项 `{id, role, critical?}`；常见 `role` 包括 `authorized_by`、`attestation`、`parent_event`、`after`、`recovery_capability`、`state_witness`、`inclusion_proof`。`critical` 默认 `true`；未识别 critical role MUST fail closed，未识别非 critical role MAY 被忽略。 | 语义引用集合。 |
| `requirements` | no | `object` | `requirements.{schema[], reducer, features[], critical_extensions[]}` 全部进入 canonical bytes 与 event digest；接收方 MUST fail closed 对未知 critical 项。`critical_extensions[]` 每项必须有 `id`、`extension_scope`、`fail_closed=true`，且 entry 顶层是 closed object；extension-specific data 必须放入 `parameters` 或用 `material_digest` 指向外部材料。 | 事件依赖声明（schema profile / reducer profile / feature / critical extension）。 |
| `preconditions` | conditional | `array<Predicate>` | 仅 Control Move 携带；在 `seal_basis` 治理 view 下求值。DataEvent MUST 省略。 | 控制面原子条件。 |
| `effects` | conditional | `array<Effect>` | reducer-input event 必填且至少 1 项。DataEvent 只能写 data plane cell；Control Move 只能写 control plane cell。 | effect 集合。 |
| `seal_ref` | conditional | `id:seal` | DataEvent 必填；指向已接受控制面 Seal，作为授权验证基线。 | 数据面授权基准。 |
| `auth_context` | conditional | `object` | DataEvent 必填；pin DID/key/capability epoch，用于在 `seal_ref` 时点验证授权。 | 数据面授权上下文。 |
| `seal_basis` | conditional | `object` | Control Move 必填；`{leaves[], control_event_set_root, state_root}` 全部进入 canonical bytes。 | 控制面提交基线。 |
| `payload` | yes | `object` | 由 event kind schema 定义。 | 事件负载。 |
| `redacts` | no | `id:event` | 仅 redaction event 使用。 | 被撤回事件。 |
| `unsigned` | no | `object` | MUST NOT 进入 event digest。 | 本地/传输附加信息。 |
| `proofs` | yes | `array<Proof>` | 至少一个有效 proof（`minItems: 1`）。 | 签名证明。 |

Event Envelope 顶层字段集是封闭的（`additionalProperties=false`）。除 schema 已声明的标准字段（含 `executed_by`、`authorization_ref`、`applet_id`、`external_ref`、`actor_kind`、`effective_scope`、可选诊断字段 `conflict_keys_digest`——对 `effects[]` 派生 cell id 集合的摘要，语义与校验见 [`../authz/event-auth-state-resolution.md` §88](../authz/event-auth-state-resolution.md)，非安全边界，verifier 一律从 `effects[]` 派生冲突域）外，扩展字段不得直接加在顶层；非关键扩展只能放入 `payload.x_*`，且仅当该 payload kind 的 schema 显式声明 `x_*` patternProperties 扩展槽时才可使用——未声明扩展槽的 payload kind 不接受任何未知字段（payload schema 的 `additionalProperties: false` 即权威判定；当前已声明扩展槽的 payload kind 以 schema 为准，现仅 `invite_payload`）。实现 MUST 在 canonical bytes、存储、转发和 backfill 中保留 schema 允许的 `x_*` 字段；需要扩展槽的 payload kind SHOULD 先在对应 schema 登记 `x_*` 槽再使用。关键扩展必须通过 `requirements.critical_extensions[]` 声明并 fail closed。

### 2.3 最小 DataEvent 示例

```json schema=schemas/event-envelope.schema.json
{
  "event_id": "ak:event:019640ed-8000-7000-8000-000000000000",
  "realm_id": "ak:realm:0196419b-0000-7000-8000-000000000000",
  "actor_id": "did:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw:alice.example",
  "actor_seq": 4,
  "kind": "ck.strand.update",
  "created_at": "2026-04-26T00:00:00Z",
  "hlc": "01970e589d21-0004-a13f9c2e",
  "prev_refs": [
    "ak:event:019640ed-0000-7000-8000-000000000000"
  ],
  "causal_refs": [],
  "refs": [
    { "id": "ak:grant:0196410c-0000-7000-8000-000000000000", "role": "authorized_by", "critical": true }
  ],
  "seal_ref": "ak:seal:sha256:1111111111111111111111111111111111111111111111111111111111111111",
  "auth_context": {
    "did": "did:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw:alice.example",
    "key_id": "device-1",
    "key_epoch": 7,
    "capability_refs": [
      "ak:grant:0196410c-0000-7000-8000-000000000000"
    ]
  },
  "effects": [
    {
      "cell": "ak:cell:ck.component.strand.metadata.v1:ck:strand:019640c6-8000-7000-8000-000000000000",
      "op": { "kind": "set", "value": { "metadata.fields.review_status": "approved" } }
    }
  ],
  "payload": {
    "target_ref": "ak:strand:019640c6-8000-7000-8000-000000000000",
    "patch": {
      "metadata.fields.review_status": "approved"
    }
  },
  "proofs": [
    {
      "kind": "detached_jws",
      "alg": "EdDSA",
      "verification_method": "did:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw:alice.example#device-1",
      "event_digest": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
      "created_at": "2026-04-26T00:00:00Z",
      "jws": "eyJhbGciOiJFZERTQSJ9..signature"
    }
  ]
}
```

Event MUST 被签名。Reducer MUST 拒绝任何 signature、schema、capability、`seal_ref` / `seal_basis` 或 causal 校验失败的事件。

### 2.4 Payload 与 type 约定

Event Envelope 的顶层 `kind` 是唯一 payload discriminator。State convergence 只能从 CBA effect 显式给出的 cell id 与 lattice op 推导，不从 envelope kind 隐式推导 state slot。

- `payload.type` 不得重复写入 `ck.*` Event kind。
- Payload 引用被创建对象时通过 `payload.object.id` 或 `payload.target_ref` 等 typed-id 字段表达，前缀（`ck:strand:` 等）即对象种类，不写单独的 `payload.object.type`。
- `actor_id` 是该 Event 归属的 principal of record。**当 `executed_by` 存在时**(act-on-behalf),实际签发该 Event 的是 `executed_by` 表示的 agent / applet / delegated service principal,proof.verification_method 解析到 `executed_by`;`actor_id` 仍是 accountable principal,用于审计 / 渲染 / accountable_principal_ids 链。Receiver MUST 同时校验 `executed_by`、`authorization_ref` 指向的 active grant / delegation，以及对应 native agent key authorization 或 Applet registration / registration_epoch 绑定之间的一致性，否则 fail closed。物化对象的 `created_by` / `updated_by` 是 reducer 输出字段，通常来自对应 create/update Event 的 `actor_id`,但不得替代 Event proof、capability 或 CBA basis 校验。
- `actor_kind` 是 reducer-stamped 投影，由 reducer 在接受 Event 时从 `actor_id` 的 Actor Profile 解析得到 immutable 值；它让审计 / 取证 / offline reader 不必反向解析 Actor Profile 即可判断该 Event 是 agent 行为(`actor_kind="agent"`) 还是 controller 行为。Actor 提交侧 MUST NOT 携带该字段。
- 启用 `ck.profile.mls.minimal_metadata_realm.v1` 时，`actor_id` MAY 是 Realm / Strand track scoped pairwise DID；真实 principal DID 的映射必须通过加密的 `ck.schema.identity_link.v1` payload（`ck.identity_link` application message / MLS private extension）、claim disclosure 或 policy 声明验证，不得把非 DID pseudonym 写入 `actor_id`。

### 2.5 Create 类 Event 的跨字段语义校验

Create 类 Event 的 `payload.object` MAY 使用完整对象 schema 做 wire validation，但接收方在进入 accepted set 前还必须执行跨字段语义校验：

- `ck.realm.create.payload.object.created_by` MUST 等于顶层 `actor_id`。
- `ck.strand.create` / `ck.morph.create` / `ck.profile.create` 中的 `payload.object.created_by` 或 `principal_id` MUST 等于顶层 `actor_id` 或被该 profile 明确授权的 controller。
- `payload.object.created_at` MUST 等于顶层 `created_at`。

校验失败 MUST `schema_violation` 或 `capability_denied`，不得把 payload 中的创建者字段当作 proof、capability 或审计归属的替代来源。

### 2.6 `actor_seq` fork 约束

- Producer SHOULD 为同一 `actor_id` 维护单调本地链，避免主动产生同高 sibling fork。
- 同一 `actor_id` 的非 genesis event MUST 在 `prev_refs` 中引用至少一个该 actor 的 accepted predecessor；该 predecessor 的最大 `actor_seq` 必须是当前 `actor_seq - 1`，除非 profile 明确声明恢复/导入场景。
- 相同 `(actor_id, actor_seq)` 的多个 event 是 sibling fork。它们没有隐含先后顺序；展示排序可使用 HLC，但协议状态生效必须使用 DataEvent / Control Move 验证、Seal coverage 与 Lattice join。
- 实现 MUST 对同一 `(actor_id, actor_seq, prev_frontier_digest)` 接受的 sibling 数量设置上限；v1 public profile 的上限为 16，超过后 MUST quarantine 或要求 actor chain repair。
- 被判定为 rejected 的 fork 不推进 actor accepted frontier，也不得作为后续 accepted event 的 predecessor。
- **over-fork repair 终局（normative）**：当某 `(actor_id, actor_seq, prev_frontier_digest)` 桶内合法签名 sibling 数超过上限时，「quarantine 或要求 actor chain repair」的收敛终局复用 [`../sync/federation.md` §4.5](../sync/federation.md) 定义的 fork resolution 机制，而非各实现自定义：(a) receiver MUST 把整个 over-fork 桶（该桶内全部 sibling，含上限内已 accepted 者）标为 quarantine，MUST NOT 把其中任何 sibling 推进为 actor accepted frontier；(b) 重新归一只能由 federation §4.5 的 `raw replay` / `quorum witness` / `operator-approved fork resolution` 三条终局路径之一产生一个 canonical 归一结果，由有 recovery / fork-resolution capability 的主体写入；(c) 在归一结果产生前，所有 receiver 对同一 over-fork 桶 MUST 一致地拒绝推进 frontier（即 quarantine 子集 = 整桶，跨 receiver 确定相同），避免不同 receiver quarantine 不同子集导致 accepted frontier 跨 receiver 分歧。over-fork 桶不适用 §2.6 的分桶限流容忍语义（限流只针对未超限的合法分叉计数）。追溯进入 quarantine 的 sibling 的 effects MUST 从所有 data/control cell 的 join 输入集中移除，并按"非 quarantine accepted set 的纯函数"确定性重算 projection；以这些 sibling 作为 `prev_refs`、`refs[role=authorized_by]`、critical ref 或 payload-level critical causal ref 的后续 Event MUST 转为 `dependency_missing` / pending，不得继续使用被 quarantine 的 predecessor 维持 accepted 状态。

`prev_frontier_digest` 的 canonical 计算为 `sha256:` + hex(SHA-256(JCS(sort_unique(prev_refs))))；`prev_refs` 先按 bytewise UTF-8 升序排序并去重，输入为空数组时编码为 `[]`。若 Realm 的 `digest_algorithm` 不是 `sha256`，同一结构使用该 Realm 声明的 digest algorithm，并把算法名前缀写入结果。该 digest 只用于 sibling fork 计数分桶，不参与 winner 选择。

### 2.7 Requirements 与 critical extensions

`requirements.features[]` 与 `requirements.critical_extensions[].id` 必须使用可发现的 feature/profile 标识，并通过 service describe、profile registry 或 Realm schema/policy 指向可验证定义。接收方不支持 critical feature 时 MUST fail closed；不得把未知 critical 语义当作普通未知字段保留后继续 accepted。

**Per-event schema 版本绑定**：当 event 修改的对象使用 evolvable schema（典型是 Morph，但同样适用于任何 Realm-defined schema 容器对象）时，写入端 **MUST** 在 `requirements.schema[]` 中列出该 event 写入时对象实际遵循的 schema profile id 全集。reader 重放该 event 时 **MUST** 用 `requirements.schema[]` 绑定的 schema 版本进行 payload / patch / transition 验证，**不得**使用对象当前的 `schema_refs[]`。这保证 partial replication 与跨版本历史回放时验证结果一致，并锁定每个 event 的 schema 解释边界。详细规则与 Morph 特化语义见 [`morph.md` §4.1](./morph.md#41-schema-refs-evolution-policy-normative)。

## 3. Proof

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `kind` | yes | `enum(detached_jws)` | 初版必须支持。 | 证明类型。 |
| `alg` | yes | `string` | 初版默认 `EdDSA`。 | 签名算法。 |
| `verification_method` | yes | `string` | DID URL。 | 公钥/设备方法。 |
| `event_digest` | yes | `hash` | MUST 等价于 `canonical_digest(envelope_without_proofs_unsigned_reducer_stamps)`：hash 输入是去除 `proofs`、`unsigned` 与 reducer-stamped 顶层字段（当前为 `effective_scope`、`actor_kind`）之后的 canonical Event envelope（含 `event_id`、`kind`、`actor_id`、`executed_by`、`authorization_ref`、`applet_id`、`external_ref`、`payload`、`refs`、`causal_refs`、`preconditions`、`effects`、`seal_ref`、`auth_context`、`seal_basis`、`requirements`、`hlc` 等）。 | producer-signed canonical Event digest。 |
| `created_at` | yes | `timestamp` |  | 签名时间。 |
| `domain` | no | `string` | 同一 trust domain 内 SHOULD 设置；跨服务、跨 trust domain 或 federation profile 下 MUST 设置。 | 域绑定。 |
| `audience` | no | `string` 或 `array<string>` | 同一 service audience 内 SHOULD 设置；跨域/服务调用、多受众调用或 federation profile 下 MUST 设置。 | 受众绑定。 |
| `jws` | yes | `string` | detached JWS。 | 签名值。 |

DID proof JSON Schema MUST 与 [`../identity/identity-did.md`](../identity/identity-did.md) 的 Proof 和 [`../conformance/encoding.md`](../conformance/encoding.md) 的 canonical JSON 规则一致。

`detached_jws` 的 JWS payload/transcript MUST 是 canonical proof binding object，而不是直接把完整 Event bytes 放进 JWS payload：

```json
{
  "context": "ck-event-proof-v1",
  "event_digest": "sha256:<canonical envelope hash>",
  "actor_id": "<event.actor_id>",
  "verification_method": "<proof.verification_method>",
  "created_at": "<proof.created_at>",
  "domain": "<proof.domain if present>",
  "audience": "<proof.audience if present>"
}
```

Verifier MUST 先移除 `proofs`、`unsigned` 与 reducer-stamped 顶层字段（当前为 `effective_scope`、`actor_kind`）计算 producer-signed canonical Event hash，并与 `proof.event_digest` 比对；随后按上述字段构造 canonical proof binding object，且 MUST 写入固定 signing-context `context="ck-event-proof-v1"`，再验证 detached JWS 覆盖该 binding object。这样 `event_digest` 绑定 producer 提交的完整 Event，reducer-stamped 字段则在 accepted envelope、Seal/sub-seal/AAD 与存储回放中保持 immutable，不得被联邦 peer 或中间服务重写。JWS transcript 同时绑定 context、actor、verification method、时间、domain/audience，避免跨签名对象族、跨服务或跨 actor 重放。

在 cross-service、cross-trust-domain、federation 或任何 profile 声明的多受众调用中，缺少 `domain` 或缺少所需 `audience` 的 proof MUST fail closed（`proof_binding_missing` 或 profile 声明的更具体 reason）。同一服务内单受众本地写入 MAY 省略其中一项，但 verifier 仍 MUST 把处理上下文中的 Realm / service audience 与 envelope `realm_id`、proof controller 和 capability 绑定分开校验；不得因为 proof 验签通过就跨服务接受同一 Event。

## 4. Field Patch (`ck.patch.v1` / `ck.schema.patch.v1`)

非 create 类更新建议使用 `ck.patch.v1` 做字段增量；客户端不得自行定义私有 dot-path 语义替代该标准。

> **命名注意**：`ck.patch.v1` 是 **embedded format identifier**（spec prose 中的简称，用于指代 `payload.patch` 字段位置的 wire 形态），其结构 schema 已正式注册为 `ck.schema.patch.v1`，artifact 见 [`artifacts/schemas/patch.schema.json`](../../artifacts/schemas/patch.schema.json)。两个标识同源——format identifier 在中文规范与 prose 中保持兼容用法，schema_id 在 registry / SDK / lint 工具中作为可解析的 schema reference。实现 MUST 将 spec 中出现的 `ck.patch.v1` 引用解析到该 schema artifact；本节 §4.1–§4.3 是该 schema 的 normative 语义补充（grammar / parser 责任 / selector / redactable / reducer-managed 字段保护），artifact 自身不重复 normative 文字。

### 4.1 结构

`ck.patch.v1` 为 map 类型：

- `key`：patch path（字段路径）。
- `value`：patch 操作，支持两种表达：
  - 直接值：等价于 `{"$op":"set","value":...}`。
  - 对象：`{"$op":"set|unset|add|remove","value":...}`。

### 4.2 patch path 规则

#### 4.2.1 Grammar（normative）

patch path 严格遵循下面 ABNF：

```text
path           = segment *( "." segment )
segment        = identifier / quoted-identifier / selector-segment
identifier     = ALPHA-LOWER *( ALPHA-LOWER / DIGIT / "_" )
ALPHA-LOWER    = %x61-7A                       ; a-z
quoted-identifier = "`" 1*( quoted-char ) "`"
quoted-char    = %x20-5F / %x61-7F             ; printable ASCII excluding `
                                               ; (literal backtick MUST be escaped as ``)
selector-segment = identifier "[" key-name "=" selector-value "]"
key-name       = identifier
selector-value = canonical-json-string         ; RFC 8785 JCS-canonicalized JSON string,
                                               ; surrounding double-quotes included
canonical-json-string = '"' *( json-char ) '"'
json-char      = unescaped / escape
unescaped      = %x20-21 / %x23-5B / %x5D-10FFFF  ; everything except " and \
escape         = "\" ( '"' / "\" / "/" / "b" / "f" / "n" / "r" / "t" / "u" 4HEXDIG )
```

具体约束：

- `identifier` 与 `key-name` MUST 匹配正则 `^[a-z][a-z0-9_]{0,63}$`(snake_case,首字符必须小写字母，长度 ≤ 64);
- `selector-value` MUST 是合法的 [RFC 8785](https://datatracker.ietf.org/doc/html/rfc8785) JCS canonical JSON string,**包括外层 ASCII 双引号**,内部按 JCS 转义规则 (`\"` / `\\` / `\/` / `\b` / `\f` / `\n` / `\r` / `\t` / `\uXXXX`);
- selector-value 内字面 `]`、`[`、`=`、`"`、`\` MUST 出现为 `\uXXXX` 或对应反斜杠转义形式;
- `quoted-identifier` 用于字段名包含非 snake_case 字符的特殊场景(v1 标准 schema 不应使用),字面 backtick 必须 escape 成连续两个 backtick;
- 默认仅支持对象路径，不支持数字数组下标。

#### 4.2.2 Parser 责任

reducer / SDK 实现 MUST 使用确定性 parser:遇到任何 ambiguous match、超长 path(> 1024 字节)、超深嵌套(> 16 段)、非 canonical selector-value(未经 JCS 规范)时,MUST 返回 `schema_violation` reason=`patch_path_invalid`。Parser **MUST NOT** 走 fallback 路径——例如不得在 selector-value 中错位的 `]` 之后继续尝试匹配下一个 segment。

#### 4.2.3 Selector 语义

对 schema 声明了唯一 key 的具名集合数组(仅由 profile / 扩展引入;v1 标准 schema 不再含此类数组),path MAY 使用 selector segment。规则:

- selector 字段必须是该数组项 schema 中声明 `unique: true` 的 stable key;
- selector 值按 canonical JSON string 解析后用于精确比较;
- 匹配 0 项时 `set` / `add` MUST reject (`failed_precondition`, reason=`patch_selector_no_match`);
- 匹配多项表示对象已违反 schema 的 uniqueness 约束,reducer MUST fail closed (`failed_precondition`, reason=`patch_selector_ambiguous`);
- Strand `tracks` 在 v1 是 map(key 即 track 名),patch path 直接使用普通对象段，例如 `tracks.discussion.profile`,不需要 selector。

#### 4.2.4 Op 与 redactable 字段交互（normative）

`ck.patch.v1` 的 `$op="unset"` 路径 MUST NOT 操作以下 redactable 内容字段:

- Message: `content`、`encrypted_content`、`body`
- Strand: `metadata.summary`、`encrypted_content`、`encrypted_metadata`、用户可写的长文本 `metadata.fields`
- Morph: `content`、`encrypted_content`、`metadata.summary`、`encrypted_metadata`、`fields.<text-content-shape>` (由 morph profile 声明)
- 任何在 Realm schema 中标记为 `redactable: true` 的字段。

理由: 这些字段的清除必须走 `ck.<kind>.redact` 或 `ck.redaction` event,以触发 redaction-specific capability check + audit seal + retention policy;允许用 `ck.patch.v1` 直接 `unset` 等价于让任何持有 `ck.<kind>.update` 的 actor 绕过 `ck.<kind>.redact` 的高 tier capability 完成 redaction (redaction escape)。

reducer MUST 在 patch path 命中 redactable field + `$op="unset"` 时返回 `schema_violation` reason=`patch_unset_redactable_field`。

#### 4.2.5 Op 其余规则

- `unset` 不允许带 `value`(空 value object MUST 视作 `{"$op":"unset"}`);
- `set`、`add`、`remove` 必须带 `value`;
- 客户端不能把数字数组下标写入 path; 如需更新无 stable key 的列表元素，必须将对象重建为具名集合项、用 profile 注册的 move/update event,或使用明确的 API 约束字段表示更新目标;
- path MUST NOT 操作 reducer-managed 字段: `id` / `schema` / `realm_id` / `created_by` / `created_at` / `updated_by` / `updated_at` / `state` / `state_changed_at` (这些字段由对应 lifecycle event 而非 patch 修改;`updated_by` / `updated_at` 由 reducer 从触发 Event 的 actor / `created_at` 派生，允许 patch 写入会让 actor 伪造更新时间戳，与防伪造 `state_changed_at` 的安全意图矛盾；见 [`common-fields.md` §5](./common-fields.md))。reducer 在 path 命中该集合时 MUST `schema_violation` reason=`patch_path_reducer_managed`。本清单为**通用最小集**;对象专属的 progress 字段禁令(Strand / Morph 的 `stage` / `stage_changed_at` patch path MUST `schema_violation`)见 [`common-fields.md` §5.3](./common-fields.md) 与 [`morph.md` §2](./morph.md)。

### 4.3 在 Event 中的位置

Event Envelope 中，patch 永远嵌入 `payload.patch`，目标对象用 `payload.target_ref`、`payload.relation_id`、`payload.view_id` 或该 kind schema 声明的等价字段表达。`ck.strand.update` 使用 `payload.target_ref` 指向目标 Strand；`ck.strand.tracks.update` 等专用 track 事件仍使用自身 schema 声明的目标字段。详见 [`../sync/operations-sync.md`](../sync/operations-sync.md) §7.2 / §8。

下面是一个 `ck.strand.update` event 中携带 `payload.patch` 字段 delta 的典型示例，覆盖直接 `set` 值（`metadata.fields.review_status` 标量字段）、对象形态 `set`（`metadata.fields.due_date`）、`unset`（`metadata.fields.dropped_field`）与 `add`（`labels.security` 集合追加）四类 op：

```json schema=schemas/patch.schema.json expect=valid
{
  "metadata.fields.review_status": "approved",
  "metadata.fields.due_date": { "$op": "set", "value": "2026-06-01" },
  "metadata.fields.dropped_field": { "$op": "unset" },
  "labels.security": { "$op": "add", "value": "confidential" }
}
```

完整 event 中的位置示例：

```json schema=schemas/event-envelope.schema.json expect=valid
{
  "event_id": "ak:event:019640ed-8000-7000-8000-000000000000",
  "realm_id": "ak:realm:0196419b-0000-7000-8000-000000000000",
  "actor_id": "did:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw:alice.example",
  "actor_seq": 5,
  "kind": "ck.strand.update",
  "created_at": "2026-04-26T00:00:00Z",
  "hlc": "01970e589d21-0004-a13f9c2e",
  "prev_refs": ["ak:event:019640ed-7000-7000-8000-000000000000"],
  "causal_refs": [],
  "refs": [
    { "id": "ak:grant:0196410c-0000-7000-8000-000000000000", "role": "authorized_by", "critical": true }
  ],
  "seal_ref": "ak:seal:sha256:1111111111111111111111111111111111111111111111111111111111111111",
  "auth_context": {
    "did": "did:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw:alice.example",
    "key_id": "device-1",
    "key_epoch": 7,
    "capability_refs": [
      "ak:grant:0196410c-0000-7000-8000-000000000000"
    ]
  },
  "effects": [
    {
      "cell": "ak:cell:ck.component.strand.metadata.v1:ck:strand:019640c6-8000-7000-8000-000000000000",
      "op": { "kind": "set", "value": { "metadata.fields.review_status": "approved", "metadata.fields.due_date": "2026-06-01", "labels.security": "confidential" } }
    }
  ],
  "payload": {
    "target_ref": "ak:strand:019640c6-8000-7000-8000-000000000000",
    "patch": {
      "metadata.fields.review_status": { "$op": "set", "value": "approved" },
      "metadata.fields.due_date": { "$op": "set", "value": "2026-06-01" },
      "labels.security": { "$op": "add", "value": "confidential" }
    }
  },
  "proofs": [
    {
      "kind": "detached_jws",
      "alg": "EdDSA",
      "verification_method": "did:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw:alice.example#device-1",
      "event_digest": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
      "created_at": "2026-04-26T00:00:00Z",
      "jws": "eyJhbGciOiJFZERTQSJ9..signature"
    }
  ]
}
```

Reducer MUST 按 §4.4 原子性规则评估整个 `payload.patch` map（全部成功才接受），其中每条 path 还要分别通过 §4.2.4 redactable 字段保护与 §4.2.5 reducer-managed 字段保护检查。

### 4.4 原子性与条件

同一个 `payload.patch` map 中的所有 path 变更属于同一个 reducer-input Event 的单次原子写入。Reducer MUST 在读取旧对象状态后先验证全部 path grammar、schema transition、capability field constraint、redactable / reducer-managed 字段限制，以及 Control Move 的 `preconditions[]`（若存在）；任一失败时整个 patch MUST fail closed，不得部分应用已经通过的 path。

Patch path 之间若同时写入父子路径、同一路径重复写入、或一条操作会改变另一条操作的 selector 结果，producer MUST 拆分为多个有明确语义边界的 Event；若需要强单值 precondition 或跨 cell invariant，schema MUST 将目标 cell family 声明为 control plane 或 per-object sequencer。Receiver 在无法按 canonical path order 得到唯一结果时 MUST `schema_violation`，`reason="patch_atomic_conflict"`。Patch 的 canonical order 只用于签名和诊断，不得被实现用作“先应用 A 再应用 B”的业务语义逃逸路径。

## 5. Event Batch Receipt

### 5.1 概念

Event Batch Receipt 是可选审计/同步加速对象，**不是 canonical history**，也**不是 reducer input**。缺少 receipt 不得导致格式、签名、授权和因果均有效的 Event 被拒绝，除非 deployment profile 额外要求 witness。

单事件确认是 `events[]` 单元素的退化形态：relay / notary / witness 对某个数据面 Event 签发"已看见"回执（驱动查询等级 `local → seen`）时，签发的就是一个 `events = [<event_digest>]`、`scope.realm_id` 就位的 Event Batch Receipt。协议不定义独立的单事件 receipt 对象（原 SeenReceipt 已合并至此，合并说明见 [`../authz/event-auth-state-resolution.md` §4.4](../authz/event-auth-state-resolution.md)）。

Receipt 的覆盖语义是 **set-bound**：`events[]` 列出 issuer *选择* 承诺的 event 集合。它提供该集合的 *integrity*（未被中间人篡改），不提供该 `scope` 下的 *completeness*（issuer 未静默丢弃属于该范围的其他 event）。即便实现额外叠加 Merkle / set commitment，恶意 issuer 仍可只承诺自己愿意承诺的子集——所以 batch receipt MUST NOT 被实现解释为 range completeness 证明。range completeness 由已注册的 active attestation event `ck.attestation.range_completeness`（payload schema `ck.schema.range_completeness_attestation.v1`）承担，其 `event_range` 必须有显式 range 语义（per-actor seq interval + frontier 上下界）+ witness quorum 或独立 seal 背书。详见 [`../sync/operations-sync.md`](../sync/operations-sync.md) §6.4 与 [`../overview/glossary.md`](../overview/glossary.md) *integrity vs completeness*。

> **概念分层**（normative）：`ck.event_batch_receipt` 是 **receipt object 名称**（不是 Event Envelope `kind`）。它的唯一 wire 形态是带 `schema = "ck.schema.event_batch_receipt.v1"` 字段的独立对象；它**不**出现在 [`event-kind-registry.json`](../../artifacts/registry/event-kind-registry.json) 中，**不**会作为 `Event.kind` 出现在 Events API 提交路径上，也**不**进入 reducer 输入。任何试图把 `ck.event_batch_receipt` 当作 Event kind 提交给 `ck.self.events.command.submit` 的实现 MUST `schema_violation`，因为 Event schema 的 `kind` enum 与 event-kind-registry 同步且不含此名。下游 SDK / cotest scanner 在 prose / fixture 中遇到 `ck.event_batch_receipt` 时 MUST 把它当 schema-id-prefix / receipt-object-name 处理，不进入 active event-kind 检查表。

与之对照：`ck.audit.ryw_receipt` 既是 receipt object 名（schema `ck.schema.audit_ryw_receipt.v1`），同时是 [`event-kind-registry.json`](../../artifacts/registry/event-kind-registry.json) 中 `status="active"` 的 **durable event kind**。其 object form 与 durable Event form 的触发条件由 Audit Applet Binding / release policy 决定：
>
> - `disclosed_policy` release MAY 只使用 object form，并把 receipt 作为 actor-private / scoped audit evidence 保存。
> - `attested_hardware` release SHOULD 将同一 receipt object 也作为 durable Event（`Event.kind = "ck.audit.ryw_receipt"`）写入 audit log，便于事后验证 release service 是否先见到 accepted `ck.audit.release`。详见 [`../crypto-media/audited-e2ee.md` §6](../crypto-media/audited-e2ee.md)。

### 5.2 Schema 与字段

Schema id: `ck.schema.event_batch_receipt.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `receipt_id` | yes | `id:receipt` |  | Receipt ID。 |
| `issuer` | yes | `did` | 必须控制签名 key。 | 签发者，可以是 principal、Principal Server 或 witness。 |
| `scope` | yes | `object` | SHOULD 包含 `actor_id`、`realm_id` 或查询范围 hash。 | receipt 覆盖范围。 |
| `frontier` | yes | `object` | SHOULD 包含 `actor_seq`、`event_id` / event hash、HLC 或 Realm frontier。 | 签发时前沿。 |
| `events` | yes | `array<id:event \| hash>` | 数组顺序参与 hash。 | 被 receipt 覆盖的 Event Envelope 引用。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `proofs` | yes | `array<Proof>` |  | Receipt proof。 |

## 6. Reducer 总则

Reducer MUST：

- 验证签名
- 验证 schema
- 验证 capability
- 按 causal order 处理
- 对相同 Event（相同 `event_id` 及其 effect 集合）保持幂等：重复 apply 同一已接受 Event MUST NOT 产生额外状态变化或副作用
- 按 §2.2 处理未知字段：拒绝 schema 未声明的字段，保留 schema 显式声明扩展槽中的未识别内容
- 输出可声明的 reducer profile

具体 DataEvent / Control Move / Seal / Lattice / state resolution 细节、authority chain、E2EE covered Seals 等见 [`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md)。

## 7. 规范性引用

- 公共字段：[common-fields.md](./common-fields.md)。
- DataEvent / Control Move / Seal / Lattice / state resolution：[`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md)。
- Event-first 发布、snapshot、冲突收敛：[`../sync/operations-sync.md`](../sync/operations-sync.md)。
- Canonical JSON、HLC、cursor：[`../conformance/encoding.md`](../conformance/encoding.md)。
- Conformance vector：[`../conformance/conformance-vectors.md`](../conformance/conformance-vectors.md)。
- Schema / event registry：[`../conformance/schema-registry.md`](../conformance/schema-registry.md)。
- Schemas：`artifacts/schemas/event-envelope.schema.json`（含 `$defs.proof` — Proof 是 Event Envelope schema 内嵌定义，不再发布为独立 `proof.schema.json` 文件）、`artifacts/schemas/event-batch-receipt.schema.json`。
