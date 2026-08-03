---
title: Event, Proof, Patch & Receipt
status: candidate
normative: true
stability: v1
updated: 2026-07-13
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

本文集中定义 Arkret 协作图中的**事件 / 签名 / 增量 / 审计 receipt 对象**：

- **Event Envelope**（`ak:event:`）：reducer 输入与审计事实的 wire 表示。
- **Proof**：签名证明 envelope。
- **Field Patch (`ak.schema.patch.v1`)**：非 create 类更新的标准字段增量格式。
- **Event Batch Receipt**（`ak:receipt:`）：可选审计 / 同步加速对象。

CBA 双平面、DataEvent、Control Move、Seal、Lattice、cell 模型、authority chain 与 state 收敛细节由 [`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) 承担；本文聚焦对象级 schema、字段、reducer 总则与 patch 语义。

公共字段见 [`common-fields.md`](./common-fields.md)。

## 2. Event Envelope

### 2.1 概念

> **Reducer**（归约器）：按确定性规则把签名后的 Event 序列计算成当前对象状态——Event 是事实日志，reducer 是把日志"播放"成 Strand / Message / Relation 等当前态对象的引擎。本文 §6 给出 reducer MUST 满足的总则；完整协议模型（DataEvent / Control Move / Seal / Lattice / cell / state resolution 等术语）见 [`../authz/event-auth-state-resolution.md` §3](../authz/event-auth-state-resolution.md)，一行术语条目见 [`../overview/glossary.md`](../overview/glossary.md)。

Event 是 reducer 输入和审计事实。所有协作变化最终都落为签名 `event`。Event 是审计根和 reducer 输入；当前态只是 Event 集合在某个 reducer profile 下的物化结果。

Reducer-input event 按 CBA 分为两类：

- DataEvent：顶层带 `seal_ref` / `auth_context`，不带 `seal_basis` / `preconditions[]`。
- Control Move：顶层带 `seal_basis`，可带 `preconditions[]`，不带 `seal_ref` / `auth_context`。

非 reducer event 不带这些 reducer 字段。

Event Envelope 是 kind-routed payload 兼容层。v1 的协议状态收敛以 CBA 双平面、Seal、Lattice 与注册 reducer 纯函数为准；`kind + payload` 是唯一业务事实源。

### 2.2 Schema 与字段

Schema id: `ak.schema.event.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `event_id` | yes | `id:event` | 事件稳定 typed ID。事件 canonical digest / proof hash 见 `conformance-vectors.md`。 | 事件 ID。 |
| `kind` | yes | `string` | MUST 匹配 `^ak\.[a-z0-9_]+(\.[a-z0-9_]+)*$`；标准 kind MUST 登记于 `event-kind-registry.json`。Registry 的 reducer contract 声明内部 cell target、lattice、bottom 与投影。 | 事件 kind。 |
| `realm_id` | yes | `id:realm` | Realm create 可在 payload 中建立。 | 所属 Realm。 |
| `scope_ref` | yes | `object` | `{kind:realm, realm_id}` 或 `{kind:circle, realm_id, circle_id}`。由 producer 声明并进入 event digest、proof 与 E2EE AAD；reducer 从 payload 和 accepted references 独立派生后逐字段比对。 | 签名安全作用域。 |
| `actor_id` | yes | `did` | 必须匹配 proof 控制链(`executed_by` 缺失时);`executed_by` 存在时 proof 控制链对齐 `executed_by`。 | 事件归属的 principal of record。 |
| `executed_by` | conditional | `did` | agent / applet / delegated service 代 `actor_id` 写入时出现。出现时 MUST 与 `authorization_ref` 同时出现；Applet delegated 写入还 MUST 同时出现 `applet_id`。进入 canonical bytes、event digest、E2EE AAD。Receiver MUST 校验 proof `verification_method` 解析到 `executed_by`。 | act-on-behalf 时实际签发该 wire write 的主体。 |
| `authorization_ref` | conditional | `id:grant`、`id:event`、DID delegation URL、root cell constant 或 registered authority source token | `executed_by` 存在时必填；Applet-originated 写入携带 `applet_id` 时也必填。普通委派优先引用已物化的 `ak:grant:*`；Event ref 只能指向产生 grant/delegation 的 accepted Event。Realm root 只能用封闭 `ak:cell:ak.component.realm.authority_root.v1:null`。DM 直接 participant 写入使用唯一注册常量 `ak.authority.direct_conversation_participant.v1` 并在 `refs[]` 携带 critical binding Event ref；任意其它 Event/cell 不得充当该 source。`executed_by` 的 DM 写入仍以本字段绑定 executor delegation，并独立叠加 participant source。 | act-on-behalf / root / profile authority 选择与引用。 |
| `applet_id` | conditional | `id:applet` | Applet、Ghost Actor、bridge 或 delegated applet 路径引入 Event 时必填。进入 canonical bytes 与 event digest；出现时 MUST 同时出现 `authorization_ref`。 | signed Applet provenance。 |
| `external_ref` | no | `object` | 外部网络 provenance。若用于回环防护、外部消息幂等、审计或用户可见出处，MUST 放在 Event Envelope 顶层并由签名覆盖；出现时 MUST 同时出现 `applet_id`。不得包含未授权外部正文明文。 | signed external provenance。 |
| `actor_kind` | reducer-stamped | `enum(user, org, team, agent, service, integration)` | 不含 `device`（设备非 actor 主体，见 [`actor.md` §2](./actor.md)）。Reducer 在接受时从 `actor_id` 的 Actor Profile 解析并 immutable 写入 accepted envelope。**Actor-supplied submit payload MUST NOT 携带**,reducer MUST `schema_violation` (`reason=actor_kind_reducer_managed`)。该 reducer-stamped 字段不参与 producer proof 的 `event_digest` 输入（见 §3）。 | 审计 / 离线读取的 actor 类型 projection。 |
| `actor_seq` | yes | `integer` | 同一 `(realm_id, actor_id)` 因果路径上严格递增；actor 在每个 Realm 各有独立链，首个事件从 `0` 开始；并发 sibling fork 可出现相同高度。 | Realm-scoped Actor 链高度 / 防回退索引。 |
| `created_at` | yes | `timestamp` | MUST 使用 canonical RFC 3339 UTC 毫秒精度 `YYYY-MM-DDTHH:MM:SS.sssZ`（整秒也写 `.000Z`）；微秒/纳秒输入必须在计算 Event digest 与签名之前截断到毫秒，不得使用 `+00:00`；不能单独决定因果。 | 创建时间。 |
| `hlc` | no | `string` | `<unix_ms_hex>-<logical_hex>-<node_id_hash>`。**Advisory 字段** — 进入 canonical bytes 与签名以防被中间方重写，但语义上只是 timeline display tie-breaker，不参与 authorization、Lattice join、Control Move precondition 或 Seal finality。详见 `encoding.md` §7。 | HLC（advisory）。 |
| `prev_refs` | yes | `array<id:event>` | 可为空。仅承载 actor event chain causal predecessors。 | Actor event chain 前序。 |
| `causal_refs` | conditional | `array<hash>` | 携带 `payload.patch` 的 DataEvent MUST 为每个 registry 目标 cell 精确引用一个 accepted base-head event digest，见 §4.3.1；其余 DataEvent 可用于声明业务因果。它不提供全局完整性证明。 | 数据面因果前驱。 |
| `refs` | yes | `array<SemanticRef>` | 默认 `[]`。每项 `{id, role, critical?}`；常见 `role` 包括 `authorized_by`、`attestation`、`parent_event`、`after`、`recovery_capability`、`state_witness`、`inclusion_proof`。`critical` 默认 `true`；未识别 critical role MUST fail closed，未识别非 critical role MAY 被忽略。 | 语义引用集合。 |
| `requirements` | no | `object` | `requirements.{schema[], features[], critical_extensions[]}` 全部进入 canonical bytes 与 event digest；接收方 MUST fail closed 对未知 critical 项。`critical_extensions[]` 每项必须有 `id`、`extension_scope`、`fail_closed=true`，且 entry 顶层是 closed object；extension-specific data 必须放入 `parameters` 或用 `material_digest` 指向外部材料。 | 事件依赖声明（schema profile / feature / critical extension）。Reducer profile 从 Event 的 CBA governance basis 读取，不在 Event 中声明。 |
| `preconditions` | conditional | `array<Predicate>` | 仅 Control Move 携带；在 `seal_basis` 治理 view 下求值。DataEvent MUST 省略。 | 控制面原子条件。 |
| `seal_ref` | conditional | `id:seal` | DataEvent 必填；指向已接受控制面 Seal，作为授权验证基线。 | 数据面授权基准。 |
| `auth_context` | conditional | `object` | DataEvent 必填；pin DID/key epoch。有效 capability 集合从 `seal_ref` 治理状态派生，producer 不提交重复引用。 | 数据面签名密钥上下文。 |
| `seal_basis` | conditional | `object` | Control Move 必填；只含 canonical sorted、duplicate-free `leaves[]` 并进入 canonical bytes。receiver 验证这些 Seal 并重算 covered control set、joined state 与 Seal roots；不得由 producer 重复抄写 roots。 | 控制面提交基线。 |
| `payload` | yes | `object` | 由 event kind schema 定义。 | 事件负载。 |
| `redacts` | no | `id:event` | 仅 redaction event 使用。 | 被撤回事件。 |
| `unsigned` | no | `object` | MUST NOT 进入 event digest。**producer / self submit 与 peer submit 的 Event MUST NOT 携带该字段**；它只能由接收服务在 read view 上添加，任何实现都 MUST NOT 把它用于身份、授权、reducer 或签名判断。service-added `unsigned` 单对象 canonical JSON MUST NOT 超过 16 KiB，见 [`../conformance/scalability-constraints.md` §2.1.1](../conformance/scalability-constraints.md)。 | 仅 read view 的本地/传输附加信息。 |
| `proofs` | yes | `array<Proof>` | 至少一个有效 proof（`minItems: 1`）。 | 签名证明。 |

#### 2.2.1 Wire Event 与 producer 的已验证提交态（normative）

`ak.schema.event.v1` 是所有 durable Event 的统一 wire envelope。MLS
`genesis` / `commit` / `welcome`、携带 MLS 加密正文的 `ak.message.create` 与明文允许的
Event 都使用同一组 envelope 字段；它们由 `kind` 与注册 payload schema 区分。内容是否由
MLS 保护是 payload protection 维度，不是第二种 Event envelope。SDK / 实现 MUST NOT 定义
字段规则不同的通用 `MlsEvent` wire 类型，或因 payload 已加密而省略该 Event 所属 CBA plane
的字段。特别地，加密 `ak.message.create` 仍是 DataEvent，仍 MUST 携带 `seal_ref +
auth_context`。

Producer SDK 还 MUST 在与外层提交态正交的 payload protection 轴上提供等价于
`PlainPayload<T> | MlsEncryptedPayload<T>` 的 closed choice。前者持有通过 `T` 自身 schema
校验的明文值；后者持有通过 `encrypted-envelope` 校验的 MLS envelope，并把
`content_type` 精确绑定到 `T` 注册的唯一解密 schema。`MlsEncryptedPayload<T>` 的类型参数
不得只是未经检查的 marker：构造时 `content_type` 不匹配 MUST fail closed。Message
ContentBlock 的 canonical MLS `content_type` 是
`application/vnd.arkret.message+json`；发送方不得另造
`application/vnd.arkret.content-block+json` 等私有别名。Message metadata 是不同的 plaintext
schema，其 canonical MLS `content_type` 是 `application/vnd.arkret.message-metadata+json`；它
MUST 使用 `MlsEncryptedPayload<MessageMetadata>`，不得用 ContentBlock wrapper 加密或解密。
`MlsWelcomePayload`、
`MlsCommitPayload`、`MlsGenesisPayload` 等是由 Event `kind` 分派的具体 MLS 协议 payload，
不等同于这个内容保护 wrapper。

通用 wire `Event` 为支持解析全部 plane，可以把 `seal_ref`、`auth_context`、`seal_basis`
表示为条件字段；但 producer SDK MUST 将“可解析 wire object”与“可提交 Event”建模为不同
状态。普通首发 / lease / submit API MUST 只接受一个已经通过完整 Event schema 与 CBA shape
校验、且不能再原地修改 envelope 的已验证提交态，其 closed variant 至少区分：

- DataEvent：`seal_ref + auth_context` 必填，`seal_basis + preconditions` 禁止；
- Control Move：`seal_basis` 必填，`seal_ref + auth_context` 禁止；
- non-reducer Event：全部 CBA reducer 字段禁止。

Anchor Unit 是显式、闭合且有序的 batch protocol，MUST 由对应 bootstrap / re-anchor unit
validator 构造；SDK MUST NOT 用“一个或一批 Event 的 CBA 条件字段均为空”推断它是 Anchor
Unit。raw `Event` MAY 用于反序列化、检查、草稿中间态或兼容读取，但 MUST NOT 绕过上述
转换直接进入 publication-evidence 或 submit 网络边界。转换失败 MUST 在发起网络请求前
fail closed。

#### 2.2.2 SDK orchestration 边界（normative）

官方 SDK MUST 为跨多次 HTTP round trip 的安全流程提供单一高层入口，至少包括
`resolve_or_create_direct_conversation(peer)`、`deactivate_agent(agent_id, reason)` 与
`prepare_mls_security_commit(scope)`。Direct Conversation 创建的授权是显式两阶段流程：SDK 先以
`phase=prepare_authorization` 取得闭合的 `authorization_prepared` 本地 outcome、reservation、registry
statement 与待签 authorization core，再由参与方签名并以同一 `operation_id + idempotency_key` 发起
`phase=commit_authorization`。SDK MUST 穷尽处理 resolver 的 typed local outcome（包括
`authorization_prepared`、`found`、`suspended`、`materializing`、`temporarily_unavailable`、
需要创建与`tombstoned`终态），并在 restart/retry 后恢复同一 durable operation；服务不得再返回
一个跨端点、可任意推进工作流的全局动作指令。产品代码不得自行分配第二组 Event id、Realm/main
Strand、KeyPackage claim 或 MLS Commit draft。

`deactivate_agent` 只 author 一个 controller-signed terminal lifecycle Event；
`prepare_mls_security_commit` 从 accepted state 重算当前 `security_frontier_digest` 并构造含完整 RFC 9420
Commit bytes 的 `MlsCommitPayload`。所有高层入口最终都必须返回 §2.2.1 的 immutable verified
submission；任何返回 raw mutable map、让调用方补 CBA 字段或自行拼 transcript 的 API 不合规。
该边界由 `ak.vector.sdk.event_type_axes.v1` 的 compile-fail/type-error suite 固定。

Event Envelope 顶层字段集是封闭的（`additionalProperties=false`）。`effects`、`conflict_keys_digest` 与 producer-selected `auth_context.capability_refs` 均不是 v1 wire 字段；遇到它们 MUST `schema_violation`。扩展字段不得直接加在顶层；非关键扩展只能放入 payload schema 明确声明的 `x_*` 槽。实现 MUST 在 canonical bytes、存储、转发和 backfill 中保留 schema 允许的扩展字段；关键扩展必须通过 `requirements.critical_extensions[]` 声明并 fail closed。

v1 **不登记** `ak.control.primitive`，也不定义 `PrimitiveControlOperations`。每个 Control Move
必须使用已注册的领域 `kind + payload` 与其闭合 reducer contract；Event、Extension Manifest
和服务 operation 都不得携带任意 cell family、subject 或 lattice op 描述。未来若引入通用控制
操作，必须先作为封闭枚举逐项登记并证明不会重新形成 producer reducer DSL；在此之前一律
`unknown_kind` / `schema_violation` fail closed。

### 2.3 最小 DataEvent 示例

```json schema=schemas/event-envelope.schema.json
{
  "event_id": "ak:event:019640ed-8000-7000-8000-000000000000",
  "kind": "ak.strand.update",
  "realm_id": "ak:realm:0196419b-0000-7000-8000-000000000000",
  "scope_ref": {
    "kind": "realm",
    "realm_id": "ak:realm:0196419b-0000-7000-8000-000000000000"
  },
  "actor_id": "did:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw:alice.example",
  "actor_seq": 4,
  "created_at": "2026-04-26T00:00:00.000Z",
  "hlc": "01970e589d21-0004-a13f9c2e",
  "prev_refs": [
    "ak:event:019640ed-0000-7000-8000-000000000000"
  ],
  "refs": [
    { "id": "ak:grant:0196410c-0000-7000-8000-000000000000", "role": "authorized_by", "critical": true }
  ],
  "causal_refs": [
    "sha256:3333333333333333333333333333333333333333333333333333333333333333"
  ],
  "seal_ref": "ak:seal:sha256:1111111111111111111111111111111111111111111111111111111111111111",
  "auth_context": {
    "did": "did:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw:alice.example",
    "key_id": "device-1",
    "key_epoch": 7
  },
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
      "created_at": "2026-04-26T00:00:00.000Z",
      "jws": "eyJhbGciOiJFZERTQSJ9..signature"
    }
  ]
}
```

Event MUST 被签名。Reducer MUST 拒绝任何 signature、schema、capability、`seal_ref` / `seal_basis` 或 causal 校验失败的事件。

### 2.4 Payload 与 type 约定

Event Envelope 的顶层 `kind` 是唯一 payload discriminator。State convergence 只能由注册 reducer contract 对 `kind + payload` 的纯函数求值得到；producer 不能选择 cell id 或 lattice op。

- `payload.type` 不得重复写入 `ak.*` Event kind。
- Payload 引用被创建对象时通过 `payload.object.id` 或 `payload.target_ref` 等 typed-id 字段表达，前缀（`ak:strand:` 等）即对象种类，不写单独的 `payload.object.type`。
- `actor_id` 是该 Event 归属的 principal of record。**当 `executed_by` 存在时**(act-on-behalf),实际签发该 Event 的是 `executed_by` 表示的 agent / applet / delegated service principal,proof.verification_method 解析到 `executed_by`;`actor_id` 仍是 accountable principal,用于审计 / 渲染 / accountable_principal_ids 链。Receiver MUST 同时校验 `executed_by`、`authorization_ref` 指向的 active grant / delegation，以及对应 native agent key authorization 或 Applet registration / registration_epoch 绑定之间的一致性，否则 fail closed。物化对象的 `created_by` / `updated_by` 是 reducer 输出字段，通常来自对应 create/update Event 的 `actor_id`,但不得替代 Event proof、capability 或 CBA basis 校验。
- `actor_kind` 是 reducer-stamped 投影，由 reducer 在接受 Event 时从 `actor_id` 的 Actor Profile 解析得到 immutable 值；它让审计 / 取证 / offline reader 不必反向解析 Actor Profile 即可判断该 Event 是 agent 行为(`actor_kind="agent"`) 还是 controller 行为。Actor 提交侧 MUST NOT 携带该字段。
- 启用 `ak.profile.mls.minimal_metadata_realm.v1` 时，`actor_id` MAY 是 Realm / Strand track scoped pairwise DID；真实 principal DID 的映射必须通过加密的 `ak.schema.identity_link.v1` payload（`ak.identity_link` application message / MLS private extension）、claim disclosure 或 policy 声明验证，不得把非 DID pseudonym 写入 `actor_id`。

#### 2.4.1 Signer regime 分派与 Agent delegated transcript（normative）

Receiver MUST 在解析任何验签 key 前先确定唯一 signer regime，不得把“上一种 key 解析失败”作为进入下一种 regime 的条件。分派输入只能是 Realm profile、Event envelope、已验证 actor/principal 类型与已登记 registration evidence：

1. `ak.profile.mls.minimal_metadata_realm.v1` 只进入 minimal-metadata regime；按 Event 所引 `(group_id, epoch, group_state_ref)` 的唯一 active BasicCredential leaf 验证，禁止 principal-scoped directory、Agent evidence 或 device directory query。
2. ordinary device proof 的 method 必须精确为 ``{signer_id}#{ak:device:<uuidv7>}``，只走 device-set / `keys/query` 的 cross-signed 或 enrollment-authority evidence。
3. ordinary Native Agent 必须由已验证 Agent principal 类型和 `ak.schema.agent_signer_evidence.v1` 共同确定；不得以 method fragment “不是 `ak:device:*`”推断。该分支禁止读取 device record。
4. Applet、service 与 integration 必须走各自 registration epoch / service DID evidence，永不落入 Agent 分支。

未知、零匹配或多重匹配一律 fail closed。统一算法固定为：

- `binding_actor_id = event.actor_id`；
- `signer_id = event.executed_by ?? event.actor_id`；
- proof method 的 controller 必须等于 `signer_id`；
- detached JWS proof binding 中的 `actor_id` 永远使用 `binding_actor_id`，不得在 delegated write 中改写为 signer；
- `executed_by` 出现时，receiver 还必须独立验证 `authorization_ref` 覆盖该 act-on-behalf write。

因此 native Agent write 与 `actor_id=controller, executed_by=agent` 使用同一 Agent verifier；区别仅是 `signer_id` 的选择。任何把 proof transcript 中 actor 改成 `executed_by`、按 controller key验 delegated Agent proof、或在 Agent evidence unresolved时改试MLS leaf/device directory的实现均不符合v1。

#### 2.4.2 Event kind cell contract（normative）

每个 `status=active && reducer_input=true` 的 durable Event kind MUST 在 `event-kind-registry.json`
声明完整 reducer contract。`plane` / `sealed` 固定 CBA 路由；`cell_writes[]` 是 reducer 内部目标集合，
每项固定 `cell_family`、`cell_subject` 派生式、`lattice`、`bottom`、可选 `initial_value`、可选
`condition` 与必需 `effect_projection`。`condition` 是对已签名 Event 的封闭纯函数：payload 条件只允许
`field_present | field_absent | field_equals | any_field_present`；需要由 critical semantic ref 选择投影时只允许
`critical_ref_role_exact_count{role,count}`，它精确统计 `refs[]` 中 `critical=true` 且 role 相等的元素。不得读取
unsigned、服务本地 row、到达顺序或外部 lookup 决定某项 registered write 是否存在。这些声明不出现在 Event wire，
producer 不能覆盖。

receiver MUST 从签名 envelope、schema-validated payload 与冻结前态重算所有目标和 lattice op。
任一 source 缺失、projection 无法求值、data/control plane 写反或目标间原子约束失败，分别以
`reducer_projection_failed` 或 `plane_cross_write` 拒绝整个 Event。多目标 contract 的所有写
在同一原子 reducer transaction 内成功或全部失败。

**精确 reducer 投影（`effect_projection`，normative）**：每个 cell write MUST 登记由 Event
纯函数派生的完整 lattice op。投影是规范内部封闭语法：

- source 对象必须且只能含 `field`（Event 根路径，例如 `payload.focus`）、`envelope_field`
  （顶层签名字段名）、`const`（任意 JSON literal）、`projected_value=true` 或 `dot=true` 之一；
  `projected_value` 只在同一 write 已声明闭合 `value_projection` 时引用其结果，`dot` 只允许
  出现在 `or_set` op 的 `tag` 位置（见下方 dot 定义）。路径不得含数组下标、通配符或空段。
- `{"kind":"transition","from":source,"to":source}` 只用于 `fsm`，精确派生 `{"kind":"transition","from":...,"to":...}`。
- `{"kind":"transition_to","to":source}` 只用于 `fsm`；reducer 从冻结前态读取 `from`，按该
  cell 的闭合 FSM 表校验到 `to` 的迁移。它适用于 KeyPackage 等由 payload 声明目标状态、
  但不允许 producer 伪造前态的状态机。
- `{"kind":"set","value":source}` 只用于 `mv_register` / `cas_register`，精确派生 `{"kind":"set","value":...}`。source 求值结果 MAY 是任意 JSON 值，包含完整 object——例如 `ak.realm.create` 的 `{"field":"payload.object"}` 与 `ak.rsvp.set` 的 `{"field":"payload.entry"}`，二者的 lattice value 都是整个子对象。这不引入第二套 object-construction DSL：投影只能整体搬运一个已存在的 Event 根路径或 `const`，MUST NOT 在 projection 内拼装、改名或裁剪字段。
- `{"kind":"apply_patch","patch":source,"expected_prestate"?:source}` 只用于 `mv_register` /
  `cas_register`；reducer 对冻结前态应用 schema-defined Patch。失败拒绝整个 Event，不能存储
  Patch 本身作为 cell value。

  **prestate binding（normative）**：可选成员 `expected_prestate` 是 prestate binding 的**唯一
  机器可读来源**。它 MUST 是 `payload.<path>` 形态的 field source——binding 是 producer 对
  冻结前态的签名声明，`envelope_field` / `const` / `dot` / `projected_value` 要么不由 producer
  签名，要么无法逐 write 变化，都表达不了这个断言。求值结果 MUST 是一个 canonical hash 字符串；
  与冻结前态的 canonical digest 不逐字节相等时 MUST 以 `failed_precondition` 拒绝整个 Event。
  实现 MUST NOT 改从别处猜测 binding 字段名，也 MUST NOT 在 registry 未登记本成员时凭空施加
  binding。

  该 source 的路径不存在时**不** fail closed，而是表示本次 write 不携带 binding：这是本节
  source 求值规则的**唯一登记例外**，因为 binding 按各 kind 的 payload 契约是可选的乐观并发
  守卫，而不是必填字段。并发安全本身由 lattice 承担——`cas_register` 在非初始态上按 §9.3.1
  必须携带命中该 cell 的 `head_eq` precondition，`mv_register` 暴露并发 heads；
  `expected_prestate` 是在此之上的额外守卫，不是替代品。
- `{"kind":"append","value":source,"issuer_seq":source}` 只用于 `ordered_log`，精确派生 `{"kind":"append","value":...,"issuer_seq":...}`；`issuer_seq` 必须求值为无符号整数。
- `{"kind":"or_set_delta","selector":"payload.<path>","branches":{...}}` 只用于 `or_set`。selector 值必须精确命中一个 branch；每个 branch 的 `op` 只能为 `add` 或 `remove`。`add` 必须同时登记 `tag` 与 `value` source，`remove` 必须只登记 `tag` source；分别精确派生同名 op。
- `or_set_add` 产生一个 add。v1 active reducer contract 不登记 producer array 到多条 OR-Set add
  的通用展开；需要多个独立 add 时必须使用各自已登记的 Event/write，不能把 payload 数组解释为
  隐式 reducer 程序。
- `{"kind":"or_set_remove_observed"}` 与
  `{"kind":"or_set_remove_observed","match":{"element_field":"<name>","source":source}}`
  只用于 `or_set`。无 `match` 时移除该目标 cell 在**冻结前态**下全部存活的 add dot；
  有 `match` 时只移除元素值上 `element_field` 具名路径的取值与 `source` 求值结果
  **逐字节相等**的存活 add dot。`element_field` 是**元素值**上的点分具名路径，
  不是 Event 根路径——这是它与 `condition.field` 的关键区别；路径不存在的元素不参与移除。

  该形态的确定性来自 CBA basis：Control Move 的 `seal_basis` 已经把 frontier 钉死，
  因此"冻结前态下的存活 add dot 集合"在所有实现上相同，无需 producer 在 payload 中枚举 dot。
  它是规范既有语义的机器可读形式，参见
  [`../identity/key-management.md`](../identity/key-management.md) §3.6.1
  （`ak.component.agent.key.v1` 的 re-authorization 必须 observe-remove 全部 active dot）
  与 [`../authz/capabilities.md`](../authz/capabilities.md) §12.1（revoke 在 `seal_basis`
  view 下解析目标 add dot）。

  需要**部分撤销**——即只移除 producer 明确指名的 dot 子集——时 MUST NOT 使用本形态，
  而使用下一条的 `or_set_remove_dots`。
- `{"kind":"or_set_remove_dots","dots":source}` 只用于 `or_set`，且 `source` 求值结果 MUST 是
  一个 dot 数组。对数组中每个元素精确派生一个 `{"kind":"remove","tag":<该元素>}`，
  移除集合与该数组**逐字节相等**：数组外的 dot 不受影响，reducer MUST NOT 由任一元素隐式
  推断并移除未枚举的其它 dot。元素 MUST 是本节定义的 canonical dot 形态；数组为空、含重复项、
  含非 dot 字符串，或 `source` 路径不存在，均 MUST fail closed。

  这是 v1 唯一的批量 OR-Set 特例，只用于**部分撤销**：移除集合由 producer 在
  payload 中显式枚举，而不是由冻结前态确定。它与 `or_set_remove_observed` 的分工是封闭的——
  前者移除 producer 指名的子集，后者移除冻结前态下的全部存活 dot；两者 MUST NOT 互相替代。
  规范来源见 [`../identity/consent-model.md`](../identity/consent-model.md) §3.3 的
  `observed_dots`（同一 `(consent_id, peer, consent_scope)` 下可以只撤销部分 dot，
  且 reducer MUST NOT 基于一个 `consent_scope=any` 的 dot 推断移除其它 dot）。

  > 与 §2.4.2 末段「一个 payload delta 需要多个同 family op 时必须使用唯一批量特例」的关系：
  > 批量特例只有 remove 侧 `or_set_remove_dots`（只用于 payload 显式枚举的 dot 数组）。
  > 其它 payload 数组 MUST NOT 被当作隐含 op 次序。
- projection 不声明的 `reason`、`issuer_seq`、`tag`、`value` 等 op 成员 MUST 缺省；source
  路径不存在、selector 未命中或投影与 lattice 不兼容表示 registry/Event 无法求值，MUST
  fail closed，不得退化为实现私有默认值。

**OR-Set dot（`dot`，normative）**：`or_set` 元素的身份由 dot 唯一确定，其规范形态固定为

```text
dot = "ak:event:" + event_id + ":" + write_index
```

`event_id` 取自签名 envelope；`write_index` 是本次 write 在该 Event kind 的 registry
`cell_writes[]` 中的 **0-based 下标**。两者都不出现在 Event wire 的独立字段中，receiver
从签名 envelope 与 registry 重算即可得到，无需任何 producer 声明。单目标 contract 的
`write_index` 恒为 `0`。

`write_index` 取 registry `cell_writes[]` 下标而非任何 wire 数组下标，是因为 v1 的 Event
wire 不存在 producer 书写的 effect 数组（见 §2.4 的单一事实源规则）。任何把 dot 的第三段
解释为 payload 数组下标、到达顺序或实现本地计数器的做法都会在实现间产生不同 dot 集合，
不符合 v1。

`or_set` op 的 `tag` MUST 使用 `{"dot": true}` 求值为本 write 的 dot，或使用一个已在本节
登记的封闭 tag 派生式；MUST NOT 直接使用裸 `{"envelope_field":"event_id"}`——裸 event_id
在同 Event 写多个 `or_set` 目标时不唯一。

dot 拼接由 `ak.vector.encoding.or_set_dot_and_batch_tag.v1`（历史 id，当前只验证 dot；
[`encoding-fixture.json`](../../artifacts/fixtures/encoding-fixture.json)）固定，含裸 event_id
作 tag 与用 wire 数组下标充当第三段的负向例。

**共享 FSM 真相源（normative）**：任何 `lattice="fsm"` 的共享 cell write 都 MUST 按
`contract-registry.json` 的 `event_kind_registry.fsm_contracts[cell_family]` 解析唯一状态机。
该 family contract 封闭登记 `axis`、`states`、`initial_state(s)`、`terminal_states`、
`allowed_transitions`、并发冲突与幂等重放语义；event kind 行只登记写入 family 与投影，
MUST NOT 在 `parameters.states` / `parameters.allowed_transitions` 再复制一份状态图。
多个 family 共享状态图时 MUST 引用 `fsm_templates` 并提供完整 `instance_parameters`；
例如 Realm / Circle membership 只通过 `delivery_binding_rebind` 实例参数决定是否包含
`join -> join`。receiver 必须先解析 template 实例，再验证投影边；未登记 family、缺实例
参数、未知状态或未列边均 MUST fail closed。same-state 是否可用也完全由解析后的
`allowed_transitions` 决定，不存在跨所有 FSM 的隐含禁止或隐含 no-op。

**Actor-private 状态合约（normative）**：`wire_scope="actor_private_event"` 的 Event 不进入共享
Data/Control reducer，因而 MUST NOT 声明共享 `plane`、`sealed`、CBA 或
`cell_contracts`。其 durable 投影必须在
`event_kind_registry.actor_private_contracts.event_writes` 中精确登记，并解析到一个
`ak.private.*` family；family 的合并语义只可引用同处登记的 `merge_definitions`。
v1 封闭支持 `server_revision_cas`、`fsm_cas`、`cas_register` 与
`causal_then_hlc_then_device`，实现不得按到达顺序或 event kind 名称另猜 merge。
actor-private 只表示状态可见性与归属，不表示可以省略持久化、CAS、签名 envelope 或
重放校验。

**`reset` 与 `cell_ref`（normative，封闭于单一 kind）**：上述全部 projection 都写入一个由
registry 字面 `cell_family` + `cell_subject` 静态确定的 cell。唯一例外是
`ak.state.conflict_recovery`（[`../authz/event-auth-state-resolution.md` §9.5](../authz/event-auth-state-resolution.md)）：

```json
{"cell_ref": {"kind": "cell_ref", "field": "payload.target_cell"},
 "effect_projection": {"kind": "reset", "value": {"field": "payload.resolved_value"}}}
```

- `cell_ref` 取代 `cell_family` + `cell_subject`，目标 cell 由签名 payload 的完整 `cell_id`
  给出。恢复面向的是**任意 family 的某一个 cell**，因此目标不可能是字面
  `ak.component.*.v<n>` URI。
- `reset` 不是 lattice op：它把该 cell 直接解析为 `resolved_value`，不参与 join。因此该
  write **MUST NOT** 声明 `lattice`、`bottom`、`cell_family`、`cell_subject` 或 `condition`
  ——目标 cell 的 lattice 与 bottom 属于被恢复的那个 cell，不属于本 kind；而带条件的 reset
  会让恢复路径本身依赖 payload 形状。
- reducer **MUST** 仅在目标 cell 已处于 `⊥` 时应用 `reset`，且 Event 必须满足 §9.5 的
  全部条件（`refs[]` 的 `recovery_capability` 与 `state_witness`、witness 严格 pre-conflict、
  已 sealed 等）。cell 处于任何其它状态时该 write **MUST** 被拒绝。

这一形态对其它 kind **封闭**：任何其它 kind 声明 `cell_ref` 或 `reset` 都是 registry 错误，
而 `ak.state.conflict_recovery` 必须同时声明二者。静态可达性在此由 §9.5 的授权与见证条件
承担——恢复的安全边界是"谁被授权、锚定在哪个冲突前状态"，而不是"这个 kind 能碰哪些 family"。

`effect_projection` 与 `condition` 正交：先求值 `condition` 决定目标是否参与，仅对参与目标
求值 projection。一个 payload delta 需要多个同 family op 时，必须由该 kind 的封闭 contract
明确登记、使用上述唯一批量特例，或拆成多个 Event；不能把其它 payload 数组顺序当作隐含
op 次序。

控制面 contract 还 MUST 声明 `concurrency_class`：`merge_safe` 仅使用可交换 lattice 合并；
`exclusive` 对目标 cell 集做独占 compare-and-apply；`security_barrier` 用于 membership、
authority、policy、scope、identity 与 key transition，并与同 signed scope 的其它 security
barrier 串行化。实现不得按 Event kind 名称猜测类别。

**条件性 cell write（`condition`，normative）**：`cell_writes[]` 的某一项 MAY 携带可选 `condition`，表示该目标只在同一 Event 的特定 payload 形态下参与。`condition` 是**封闭语法**，只有四种形态，且求值 MUST 是对已通过 schema 校验的 payload 的纯函数：

| `kind` | 附加字段 | 命中条件 |
| --- | --- | --- |
| `field_present` | `field`（点分具名路径） | 该路径在 payload 中存在且值不是 JSON `null` |
| `field_absent` | `field` | 该路径在 payload 中不存在，或值是 JSON `null` |
| `field_equals` | `field`、`const`（字符串 / 数字 / 布尔标量） | 该路径存在且其值与 `const` 逐字节相等（字符串按原始 Unicode scalar 比较，MUST NOT 做大小写折叠或归一化） |
| `any_field_present` | `fields[]`（≥2 条点分具名路径） | 至少一条路径存在且值不是 JSON `null` |

求值规则：

- `condition` 命中时 reducer 必须执行该目标；未命中时不得执行。实现 MUST NOT 把未命中的
  目标写成 same-value/no-op。对 `fsm` cell 而言，same-state 是否合法只由该 family 的
  已解析 `allowed_transitions` 决定；未登记 self-transition 时必须拒绝。
- 无 `condition` 的目标是无条件必需目标。
- 未知 `kind`、缺 `field`、`field` 不是点分具名路径、`field_equals` 缺 `const` 或 `const` 不是标量，MUST fail closed（registry 无效，发布门禁失败）。
- **`any_field_present` 的两种正当用途**：(i) 同一语义值在同 kind 的不同 payload 形态下落在不同路径（例如 invite 既可用 `payload.invite` 完整对象、也可用扁平字段承载）；(ii) 同一 cell 承载多个不同字段，其中任一字段出现即需写该 cell。
- **subject 可派生性（normative）**：条件命中时该目标的 `cell_subject` MUST 可派生。用途 (i) 下 `cell_subject` 必然是 `coalesce`，其 `fields[]` MUST 与 `condition.fields[]` 逐项一致、同序——否则会出现「条件命中但 subject 无法派生」或反之的组合；该一致性由 `tools/lint_artifacts.py` 机械校验。用途 (ii) 下 `cell_subject` 取一个与条件字段无关的路径，该路径 MUST 是 payload 的无条件必填字段。
- `condition` 只决定该目标是否参与，MUST NOT 改变 `cell_family`、`cell_subject` 派生式、
  `lattice` 或 `bottom`；需要按判别值切换取值字段时使用已登记的 `select` component。

**持久化前态约束（`pre_state_requirements`，normative）**：event contract MAY 登记一个
封闭的前态准入数组。reducer 先按 `cell_family` 与 `subject` 读取已接受前态，再依次执行：

- `predicate:{kind:"stored_field_present",field}`：该具名字段存在且非 `null`；
- `predicate:{kind:"stored_field_equals_payload",field,payload_field}`：持久化字段存在，
  `payload_field` 也存在，且二者逐字节相等。

任一失败时必须原样返回该 requirement 登记的 `failure.code` / `failure.reason_code`，整个
Move 不得产生任何 cell write。实现不能用请求另传的同名字段替代持久化前态。当前
`ak.invite.cancel` 先要求目标 Invite 已有 `invitee`，把该 kind 封闭在普通定向邀请；再要求
它与签名 `payload.invitee` 相等，保证 Invite lifecycle 与 member state 两条投影原子参与。
第三方/token invite 必须使用 `ak.invite.revoke`。

`ak.mls.genesis` / `ak.mls.commit` 的三目标合约固定为 MLS epoch、key schedule 与 covered-seals；`ak.invite.accept` 固定为 invite lifecycle 与 member state；`ak.invite.claim` 固定为 invite lifecycle 与 subject-bound membership proposal。generic/message redaction 写入单调 `ak.component.object.redaction.v1` fact；对象的 effective terminal/redacted 状态由该 fact 与对象 lifecycle cell 联合派生，不允许用到达顺序选择是否清除内容。闭包与正负路径由 `ak.vector.event_kind.cell_contract_closure.v1` 固定。

### 2.5 Create 类 Event 的跨字段语义校验

Create 类 Event 的 `payload.object` MAY 使用完整对象 schema 做 wire validation，但接收方在进入 accepted set 前还必须执行跨字段语义校验：

- `ak.realm.create.payload.object.created_by` MUST 等于顶层 `actor_id`。
- `ak.strand.create` / `ak.morph.create` / `ak.profile.create` 中的 `payload.object.created_by` 或 `principal_id` MUST 等于顶层 `actor_id` 或被该 profile 明确授权的 controller。
- `payload.object.created_at` MUST 等于顶层 `created_at`。

校验失败 MUST `schema_violation` 或 `capability_denied`，不得把 payload 中的创建者字段当作 proof、capability 或审计归属的替代来源。

### 2.6 `actor_seq` fork 约束

- Event actor chain 的唯一作用域是 `(realm_id, actor_id)`。首个普通 Event 使用 `actor_seq=0`；后续 Event 的 sequence 只可由该作用域的 accepted authoring frontier 或同一 authoring transaction 内已经构造的前一 Event 推导。实现不得维护会在签发时烧号的 actor-sequence floor，也不得用 actor-only aggregate、另一 Realm 或未经验证的本地缓存提升 `actor_seq`。
- 该作用域的 authoring frontier 使用 `next_actor_seq` 与最高 accepted sequence 上的完整 sibling set 表达：空链为 `next_actor_seq=0` 且 `frontier_event_ids=[]`；非空链为 `next_actor_seq=1+最高 accepted actor_seq`，`frontier_event_ids` 必须包含该最高 sequence 上全部未 quarantine accepted sibling Event id。集合按 bytewise UTF-8 升序排序、去重，累计上限为本节的 64。若最高 sequence 为 `u64::MAX`，frontier unavailable，receiver MUST 返回 `frontier_sequence_exhausted`，不得 wrap。
- `frontier_digest` 使用 Realm 当前声明的 `digest_algorithm` 对 `UTF8("ak-realm-actor-frontier-v1\u0000") || JCS({"kind":"realm_actor","realm_id":...,"actor_id":...,"next_actor_seq":...,"frontier_event_ids":[...]})` 求 digest，并保留算法前缀。该 digest 只绑定 selector/result 的确定性完整性与 CAS 诊断，不是服务签名、authorization proof、Seal 或 completeness attestation。
- Producer author 普通 Event 时 MUST 直接使用 `actor_seq=next_actor_seq`，并把实际观察到的完整 `frontier_event_ids` 合入 `prev_refs`。Receiver 不得反向要求该 Event 覆盖接收时才出现的并发 sibling；只要 signed basis 满足同 Realm、同 actor、紧邻 sequence 与 fork 上限，查询后新增的 sibling 不得改变既有 signed Event 的结构合法性。
- Producer SHOULD 为同一 `(realm_id, actor_id)` 维护单调本地链，避免主动产生同高 sibling fork。一个 actor 在不同 Realm 的相同 `actor_seq` 是正常事件，不构成 fork，也不得互相写入 `prev_refs`。
- 同一 `(realm_id, actor_id)` 的非 genesis event MUST 在 `prev_refs` 中引用至少一个该 actor 在同一 Realm 的 accepted predecessor；该 predecessor 的最大 `actor_seq` 必须是当前 `actor_seq - 1`。跨 Realm predecessor MUST `schema_violation`。唯一 identity recovery 例外是 B 模型 Principal Control Realm 内的 `ak.device.reanchor`：其 `prev_refs` 精确等于该 PCR 的 `pre_fence_basis` preserved closure 加 genesis anchor set 中该 actor 的 canonical heads，`actor_seq=1+max(preserved actor_seq)`；紧随的 replacement authorize 只引用 re-anchor id 且 sequence 加一。未被 basis 保留的 pending/unsealed sibling 不进入新 generation，也不能以更高 sequence 阻塞恢复。
- 相同 `(realm_id, actor_id, actor_seq)` 的多个 event 是 sibling fork。它们没有隐含先后顺序；展示排序可使用 HLC，但协议状态生效必须使用 DataEvent / Control Move 验证、Seal coverage 与 Lattice join。
- 实现 MUST 对同一 `(realm_id, actor_id, actor_seq, prev_frontier_digest)` 接受的 sibling 数量设置上限；v1 的单桶上限为 16。同一 `(realm_id, actor_id, actor_seq)` 跨全部 `prev_frontier_digest` 桶的合法签名 sibling 累计上限为 64；任一上限被超过时 MUST quarantine 或要求 actor chain repair。累计候选集合只由已验证 canonical Event 集合决定，不依赖到达顺序。两项均是无条件 v1 上限，单一数值真相源见 [`scalability-constraints.md` §2](../conformance/scalability-constraints.md)。
- Realm 隔离、同 Realm sibling 与跨 Realm predecessor 拒绝由 `ak.vector.actor_chain.realm_scope.v1` 固定。
- 被判定为 rejected 的 fork 不推进 actor accepted frontier，也不得作为后续 accepted event 的 predecessor。
- **over-fork repair 终局（normative）**：当某 `(realm_id, actor_id, actor_seq, prev_frontier_digest)` 桶内合法签名 sibling 数超过上限时，「quarantine 或要求 actor chain repair」的收敛终局复用 [`../sync/federation.md` §4.5](../sync/federation.md) 定义的 fork resolution 机制，而非各实现自定义：(a) receiver MUST 把整个 over-fork 桶（该桶内全部 sibling，含上限内已 accepted 者）标为 quarantine，MUST NOT 把其中任何 sibling 推进为 actor accepted frontier；(b) 重新归一只能由 federation §4.5 的 `raw replay` / `quorum witness` / `operator-approved fork resolution` 三条终局路径之一产生一个 canonical 归一结果，由有 recovery / fork-resolution capability 的主体写入；(c) 在归一结果产生前，所有 receiver 对同一 over-fork 桶 MUST 一致地拒绝推进 frontier。追溯进入 quarantine 的 sibling 必须从所有 cell 的 reducer 输入集中移除，并按非 quarantine accepted Event 集合确定性重算 projection；依赖这些 sibling 的后续 Event 转为 `dependency_missing` / pending。

`prev_frontier_digest` 的 canonical 计算为 `sha256:` + hex(SHA-256(JCS(sort_unique(prev_refs))))；`prev_refs` 先按 bytewise UTF-8 升序排序并去重，输入为空数组时编码为 `[]`。若 Realm 的 `digest_algorithm` 不是 `sha256`，同一结构使用该 Realm 声明的 digest algorithm，并把算法名前缀写入结果。该 digest 只用于 sibling fork 计数分桶，不参与 winner 选择。

跨桶累计超过 64 时，上述“整桶”扩展为同一 `(realm_id, actor_id, actor_seq)` 的全部 sibling。对已经被 accepted Seal 覆盖的 Control Move，追溯规则存在唯一例外：其 digest 与确定性 reducer 输出 MUST 保留在该 Seal 的 `covered_set` / `state_root` 输入中，不得改写已接受 Seal；该 actor 后续控制面 Move 在显式 fork-resolution compaction Seal 归一前 fail closed。数据面 sibling 与尚未被任何 accepted Seal 覆盖的 pending Control Move仍按上段移除。

`ak.device.reanchor` 另使用独立冲突槽 `(principal_id,did_version_number)`，version number 必须从已验证 DID versionId 解析。did_version_id、re-anchor digest 与 replacement-authorize digest 全相同才是幂等重试；同槽任一不同即把全部候选 unit 及后继 generation Seal quarantine，禁止 first-seen winner。reducer 保留最后未冲突的 current generation ref、将状态置 `conflicted` 并关闭普通 Event/Seal admission；只有更高 version、由下一预承诺 authority 签发且在 registry/witness policy 下成为 canonical head 的 re-anchor 可以解除。该规则优先于普通 actor sibling 容量/限流规则，不能用唯一约束丢弃第二份证据。

上述独立冲突槽、到达顺序无关性与解除路径由 `ak.vector.identity.device_reanchor.v1` 执行验证。

### 2.7 Requirements 与 critical extensions

`requirements.features[]` 与 `requirements.critical_extensions[].id` 必须使用可发现的 feature/profile 标识，并通过 service describe、profile registry 或 Realm schema/policy 指向可验证定义。接收方不支持 critical feature 时 MUST fail closed；不得把未知 critical 语义当作普通未知字段保留后继续 accepted。

**Per-event schema 版本绑定**：当 event 修改的对象携带 `schema_refs[]` 时，写入端 **MUST** 在 `requirements.schema[]` 中列出该 event 写入时对象实际遵循的 schema profile id 全集。reader 重放该 event 时 **MUST** 用 `requirements.schema[]` 绑定的 schema 版本进行 payload / patch / transition 验证，**不得**使用对象当前的 `schema_refs[]`。这保证 partial replication 与跨版本历史回放时验证结果一致，并锁定每个 event 的 schema 解释边界。

该规则按对象的 schema 来源分成两类，二者都适用，不因来源不同而豁免：

- **Realm-defined evolvable schema**（典型是 Morph）：`schema_refs[]` 由 Realm 声明并可演进，绑定用于锁定演进历史。详细规则与 Morph 特化语义见 [`morph.md` §4.1](./morph.md#41-schema-refs-evolution-policy-normative)。
- **spec-fixed profile subtree schema**（典型是 Strand 的 `metadata.fields.<profile>` 子树）：schema 本身由 spec 固定、不可演进，但对象**是否激活**该 profile 会随 patch 变化。写入或修改该子树的 event **MUST** 同样绑定对应 schema id，否则 reader 在回放一段"profile 后来被移除"的历史时会用当前 `schema_refs[]` 得到不同的验证结论。缺该绑定 MUST `schema_violation`。v1 的唯一实例见 [`calendar-event.md` §1](./calendar-event.md)。

### 2.8 统一准入与反枚举顺序（normative）

对引用既有 Realm / Circle / Strand / Message 或其它对象的 Event，receiver MUST 按以下顺序
执行准入；kind-specific handler 不得把后续检查提前：

1. 执行 transport/body 上限、closed schema、canonical encoding、Event proof 与 signer
   regime 校验。未通过者按对应结构或认证错误拒绝，不进入对象查找。
2. 在已认证 requester 的可见控制面与 history view 中解析 `realm_id`、`scope_ref` 和目标
   object。目标不存在、已 tombstone、属于其它 scope，或 requester 无权观察其存在时，
   MUST 返回同一不可区分的 `not_found` / opaque denial 形态；response body、状态码、可观察
   timing 与 telemetry-facing reason 均不得区分这些情形。
3. 仅在目标对 requester 可见后，按冻结的 `seal_ref` / `seal_basis` view 校验 capability、
   membership、history visibility、grant constraints 与 freshness。
4. 仅在可见性与授权均通过后，求值 profile feature gate、对象 lifecycle、Track enabled
   状态及其它 kind-specific precondition；此阶段才可返回
   `discussion_track_disabled`、`failed_precondition` 等会揭示对象内部状态的诊断。
5. 最后执行 registry reducer projection、lattice precondition 与原子写入；任一失败拒绝
   整条 Event，不得留下部分 projection。

同一准入入口的 batch 项也 MUST 逐项遵守上述顺序。实现可以合并不会改变可观察结果的内部
查询，但不得以缓存、索引或“快速 feature gate”为由，在第 2 步之前暴露目标 kind、Track
配置、lifecycle 或 capability 命中情况。具体领域章节若声明更细的检查，只能插入对应阶段，
不得重排这五个安全边界。

## 3. Proof

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `kind` | yes | `enum(detached_jws)` | 初版必须支持。 | 证明类型。 |
| `alg` | yes | `string` | 初版默认 `EdDSA`。 | 签名算法。 |
| `verification_method` | yes | `string` | DID URL。 | 公钥/设备方法。 |
| `event_digest` | yes | `hash` | MUST 等价于 `canonical_digest(envelope_without_proofs_unsigned_actor_kind)`。签名输入包含 `scope_ref`、`payload`、basis 与其它 producer 字段，只排除 `proofs`、`unsigned`、`actor_kind`。 | producer-signed canonical Event digest。 |
| `created_at` | yes | `timestamp` | MUST 使用 canonical RFC 3339 UTC 毫秒精度 `YYYY-MM-DDTHH:MM:SS.sssZ`（整秒也写 `.000Z`）；微秒/纳秒输入必须在生成 proof binding 与签名之前截断到毫秒，不得使用 `+00:00`。 | 签名时间。 |
| `domain` | no | `string` | 同一 trust domain 内 SHOULD 设置；跨服务、跨 trust domain 或 federation profile 下 MUST 设置。 | 域绑定。 |
| `audience` | no | `string` 或 `array<string>` | 同一 service audience 内 SHOULD 设置；跨域/服务调用、多受众调用或 federation profile 下 MUST 设置。 | 受众绑定。 |
| `jws` | yes | `string` | detached JWS。 | 签名值。 |

DID proof JSON Schema MUST 与 [`../identity/identity-did.md`](../identity/identity-did.md) 的 Proof 和 [`../conformance/encoding.md`](../conformance/encoding.md) 的 canonical JSON 规则一致。

`detached_jws` 的 JWS payload/transcript MUST 是 canonical proof binding object，而不是直接把完整 Event bytes 放进 JWS payload：

```json
{
  "context": "ak.event-proof-v1",
  "event_digest": "sha256:<canonical envelope hash>",
  "actor_id": "<event.actor_id>",
  "verification_method": "<proof.verification_method>",
  "created_at": "<proof.created_at>",
  "domain": "<proof.domain if present>",
  "audience": "<proof.audience if present>"
}
```

Verifier MUST 先移除 `proofs`、`unsigned` 与 `actor_kind`，保留 `scope_ref`，计算 producer-signed canonical Event hash并与 `proof.event_digest` 比对；随后写入固定 signing-context `context="ak.event-proof-v1"` 验证 detached JWS。JWS transcript 同时绑定 context、actor、verification method、时间、domain/audience，避免跨对象族、跨服务或跨 actor/scope 重放。

在 cross-service、cross-trust-domain、federation 或任何 profile 声明的多受众调用中，缺少 `domain` 或缺少所需 `audience` 的 proof MUST fail closed（`proof_binding_missing` 或 profile 声明的更具体 reason）。同一服务内单受众本地写入 MAY 省略其中一项，但 verifier 仍 MUST 把处理上下文中的 Realm / service audience 与 envelope `realm_id`、proof controller 和 capability 绑定分开校验；不得因为 proof 验签通过就跨服务接受同一 Event。

## 4. Field Patch (`ak.schema.patch.v1`)

非 create 类更新建议使用 `ak.schema.patch.v1` 做字段增量；客户端不得自行定义私有 dot-path 语义替代该标准。其 canonical artifact 是 [`patch.schema.json`](../../artifacts/schemas/patch.schema.json)，本节 §4.1–§4.4 定义该 schema 的 normative grammar、parser、字段保护与 reducer 语义。

### 4.1 结构

`ak.schema.patch.v1` 为 map 类型：

- `key`：patch path（字段路径）。
- `value`：patch 操作，支持两种表达：
  - 直接值：等价于 `{"$op":"set","value":...}`。
  - 对象：`{"$op":"set|unset|add|remove","value":...}`。

### 4.2 patch path 规则

#### 4.2.1 Grammar（normative）

patch path 严格遵循下面 ABNF：

```text
path           = segment *( "." segment )
segment        = identifier
identifier     = ALPHA-LOWER *( ALPHA-LOWER / DIGIT / "_" )
ALPHA-LOWER    = %x61-7A                       ; a-z
```

具体约束：

- `identifier` MUST 匹配正则 `^[a-z][a-z0-9_]{0,63}$`(snake_case,首字符必须小写字母，长度 ≤ 64);
- v1 只接受 snake_case `identifier` segment；quoted identifier、selector segment
  （`field[key=value]`）与数字数组下标都不属于 v1 grammar，MUST 以 `schema_violation`、
  `reason_code=patch_path_invalid` 拒绝；
- path 最多 16 段，UTF-8 编码后最多 1024 bytes；
- [`patch.schema.json#/propertyNames/pattern`](../../artifacts/schemas/patch.schema.json) 是上述 grammar 与
  16 段上限的 canonical 机读投影；schema 与本节必须同批更新。

#### 4.2.2 Parser 责任

reducer / SDK 实现 MUST 使用确定性 parser。遇到任何不匹配 §4.2.1 grammar 的 path、UTF-8 编码后超过
1024 bytes 的 path 或超过 16 段的 path 时，MUST 返回 `schema_violation`、
`reason_code=patch_path_invalid`。Parser MUST NOT 走 fallback 路径；例如空 segment、非法字符、
selector / 数组下标形态不得在跳过无效部分后继续解析。

#### 4.2.3 无 stable-key 列表元素

v1 的 patch path 只寻址对象成员。要更新没有 stable key 的列表元素，必须把该对象重建为
map（key 即成员名，如 Strand `tracks`）、使用 profile 注册的 move/update event，
或用明确的 API 约束字段表示更新目标；不得把数字数组下标或 selector segment 写入 path。

#### 4.2.4 Op 与 redactable 字段交互（normative）

`ak.schema.patch.v1` 的 `$op="unset"` 路径 MUST NOT 操作以下 redactable 内容字段:

- Message: `content`、`encrypted_content`、`body`
- Strand: `metadata.summary`、`encrypted_content`、`encrypted_metadata`、用户可写的长文本 `metadata.fields`
- Morph: `content`、`encrypted_content`、`metadata.summary`、`encrypted_metadata`、`fields.<text-content-shape>` (由 morph profile 声明)
- 任何在 Realm schema 中标记为 `redactable: true` 的字段。

理由: 这些字段的清除必须走 `ak.<kind>.redact` 或 `ak.redaction` event,以触发 redaction-specific capability check + audit seal + retention policy;允许用 `ak.schema.patch.v1` 直接 `unset` 等价于让任何持有 `ak.<kind>.update` 的 actor 绕过 `ak.<kind>.redact` 的高 tier capability 完成 redaction (redaction escape)。

reducer MUST 在 patch path 命中 redactable field + `$op="unset"` 时返回 `schema_violation` reason=`patch_unset_redactable_field`。

#### 4.2.5 Op 其余规则

- `unset` 不允许带 `value`(空 value object MUST 视作 `{"$op":"unset"}`);
- `set`、`add`、`remove` 必须带 `value`;
- 客户端不能把数字数组下标写入 path; 如需更新无 stable key 的列表元素，必须将对象重建为具名集合项、用 profile 注册的 move/update event,或使用明确的 API 约束字段表示更新目标;
- path MUST NOT 操作 reducer-managed 字段: `id` / `schema` / `realm_id` / `created_by` / `created_at` / `updated_by` / `updated_at` / `state` / `state_changed_at` (这些字段由对应 lifecycle event 而非 patch 修改;`updated_by` / `updated_at` 由 reducer 从触发 Event 的 actor / `created_at` 派生，允许 patch 写入会让 actor 伪造更新时间戳，与防伪造 `state_changed_at` 的安全意图矛盾；见 [`common-fields.md` §5](./common-fields.md))。reducer 在 path 命中该集合时 MUST `schema_violation` reason=`patch_path_reducer_managed`。本清单为**通用最小集**;对象专属的 progress 字段禁令(Strand / Morph 的 `stage` / `stage_changed_at` patch path MUST `schema_violation`)见 [`common-fields.md` §5.3](./common-fields.md) 与 [`morph.md` §2](./morph.md)。

### 4.3 在 Event 中的位置

Event Envelope 中，patch 永远嵌入 `payload.patch`，目标对象用 `payload.target_ref`、`payload.relation_id`、`payload.view_id` 或该 kind schema 声明的等价字段表达。`ak.strand.update` 与 `ak.strand.tracks.update` 均使用 `payload.target_ref` 指向目标 Strand，并共享 `strand_patch_payload` 的字段契约。接收、去重与 reducer 验证见 [`../sync/operations-sync.md`](../sync/operations-sync.md) §3 / §12。

下面是一个 `ak.strand.update` event 中携带 `payload.patch` 字段 delta 的典型示例，覆盖直接 `set` 值（`metadata.fields.review_status` 标量字段）、对象形态 `set`（`metadata.fields.due_date`）与 `unset`（`metadata.fields.dropped_field`）三类 op：

```json schema=schemas/patch.schema.json expect=valid
{
  "metadata.fields.review_status": "approved",
  "metadata.fields.due_date": { "$op": "set", "value": "2026-06-01" },
  "metadata.fields.dropped_field": { "$op": "unset" }
}
```

完整 event 中的位置示例：

```json schema=schemas/event-envelope.schema.json expect=valid
{
  "event_id": "ak:event:019640ed-8000-7000-8000-000000000000",
  "kind": "ak.strand.update",
  "realm_id": "ak:realm:0196419b-0000-7000-8000-000000000000",
  "scope_ref": {
    "kind": "realm",
    "realm_id": "ak:realm:0196419b-0000-7000-8000-000000000000"
  },
  "actor_id": "did:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw:alice.example",
  "actor_seq": 5,
  "created_at": "2026-04-26T00:00:00.000Z",
  "hlc": "01970e589d21-0004-a13f9c2e",
  "prev_refs": ["ak:event:019640ed-7000-7000-8000-000000000000"],
  "refs": [
    { "id": "ak:grant:0196410c-0000-7000-8000-000000000000", "role": "authorized_by", "critical": true }
  ],
  "causal_refs": ["sha256:3333333333333333333333333333333333333333333333333333333333333333"],
  "seal_ref": "ak:seal:sha256:1111111111111111111111111111111111111111111111111111111111111111",
  "auth_context": {
    "did": "did:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw:alice.example",
    "key_id": "device-1",
    "key_epoch": 7
  },
  "payload": {
    "target_ref": "ak:strand:019640c6-8000-7000-8000-000000000000",
    "patch": {
      "metadata.fields.review_status": { "$op": "set", "value": "approved" },
      "metadata.fields.due_date": { "$op": "set", "value": "2026-06-01" }
    }
  },
  "proofs": [
    {
      "kind": "detached_jws",
      "alg": "EdDSA",
      "verification_method": "did:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw:alice.example#device-1",
      "event_digest": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
      "created_at": "2026-04-26T00:00:00.000Z",
      "jws": "eyJhbGciOiJFZERTQSJ9..signature"
    }
  ]
}
```

Reducer MUST 按 §4.4 原子性规则评估整个 `payload.patch` map（全部成功才接受），其中每条 path 还要分别通过 §4.2.4 redactable 字段保护与 §4.2.5 reducer-managed 字段保护检查。

#### 4.3.1 Patch reducer 的唯一输入（normative）

`payload.patch` 是 producer 签名的唯一更新指令。receiver MUST 在该 Event 的冻结 pre-state 上执行
规范纯函数 `reduce_patch(kind, target_ref, patch, pre_state)`；wire 不携带第二份 cell write。投影无法
唯一求值时以 `schema_violation`、`reason_code=reducer_projection_failed` 拒绝。

冻结 pre-state 的唯一求值规则：

- Control Move 的 pre-state 是 `seal_basis` 所承诺的目标 cell settled value，按 CBA frozen-baseline 规则读取。
- 携带 patch 的 DataEvent MUST 在 `causal_refs[]` 中为每个目标 cell 精确引用一个 accepted base-head event digest；该 Event 的 reducer contract 必须写同一 cell。receiver 从该 base head 的完整 post-state恢复 pre-state，不读取本地当前 head、到达顺序或墙钟。依赖未取得时保持 `dependency_missing` pending。
- 目标 cell 当前已有多个并发 head 不影响某个基于旧 head 的 DataEvent 被验证：它形成新的并发 head并由 `mv_register` 暴露。producer 若要显式收敛多个 head，MUST 使用该 cell family 注册的 resolution Event / per-object sequencer；通用 patch 不得任意选择本地 winner。create 类无 pre-state 的 Event 不使用本 patch 规则。
- `causal_refs[]` 中没有命中目标 cell 的 base、命中多个 base、base Event reducer 未写该 cell，或 base post-state 无法重建时，receiver MUST `schema_violation` / `reducer_projection_failed`；不得回退到当前 state。

上述 patch 路由、冻结 pre-state 与失败分支由
`ak.vector.patch.projection_prestate_binding.v1` 固定。

派生函数按以下封闭规则工作：

1. 先按上述冻结规则取得唯一 pre-state，再按 §4.2 / §4.4 验证并原子应用 patch，得到完整 post-state；命中 redactable 或 reducer-managed 路径时立即拒绝。
2. 目标 cell family、cell subject、plane 与 lattice 只从 event-kind registry reducer contract 与 kind payload schema 派生，producer 无覆盖入口。
3. `mv_register` / `cas_register` 产生单个 `op.kind="set"`，`op.value` 是完整 post-state cell value，不是 partial patch。`or_set` 只允许 patch `add` / `remove`，逐项产生同名 lattice op；`counter` 只允许 schema 登记的增减字段并产生 `inc` / `dec`；`fsm` 只允许领域 transition Event，MUST NOT 用通用 patch 改状态。其它 lattice 若无本节或领域文档的显式映射，携带 patch MUST fail closed。
4. 内部派生写按 cell id、op kind、tag/element id 的 canonical tuple 升序处理；相同 tuple 重复、patch 父子路径冲突或跨 plane 写入时 MUST 拒绝，不能靠数组顺序消歧。

verifier、Seal 与 projection 始终消费同一规范 reducer 输出，不消费 producer 指令。

### 4.4 原子性与条件

同一个 `payload.patch` map 中的所有 path 变更属于同一个 reducer-input Event 的单次原子写入。Reducer MUST 在读取旧对象状态后先验证全部 path grammar、schema transition、capability field constraint、redactable / reducer-managed 字段限制，以及 Control Move 的 `preconditions[]`（若存在）；任一失败时整个 patch MUST fail closed，不得部分应用已经通过的 path。

`ak.vector.patch.atomic_application.v1` 与 `state-reducer-hardening-fixture.json` 固化多 path 单 cell 写入、原子 primary 切换、非法 patch path 与失败时全量回滚；`ak.vector.patch.path_grammar_bounds.v1` 固化 grammar 与 1024-byte / 16-segment 边界。

Patch path 之间若同时写入父子路径、同一路径重复写入、或一条操作会改变另一条操作的目标解析结果，producer MUST 拆分为多个有明确语义边界的 Event；若需要强单值 precondition 或跨 cell invariant，schema MUST 将目标 cell family 声明为 control plane 或 per-object sequencer。Receiver 在无法按 canonical path order 得到唯一结果时 MUST `schema_violation`，`reason="patch_atomic_conflict"`。Patch 的 canonical order 只用于签名和诊断，不得被实现用作“先应用 A 再应用 B”的业务语义逃逸路径。

## 5. Event Batch Receipt

### 5.1 概念

Event Batch Receipt 是可选审计/同步加速对象，**不是 canonical history**，也**不是 reducer input**。缺少 receipt 不得导致格式、签名、授权和因果均有效的 Event 被拒绝，除非 deployment profile 额外要求 witness。

单事件确认是 `events[]` 单元素的退化形态：relay / notary / witness 对某个数据面 Event 签发"已看见"回执时，签发的就是一个 `events = [<event_digest>]`、`scope.realm_id` 就位的 Event Batch Receipt。协议只定义这一种 set-bound receipt 结构；具体 operation / profile 必须显式登记承载字段后，才能把该 receipt 作为响应证据。

Receipt 的覆盖语义是 **set-bound**：`events[]` 列出 issuer *选择* 承诺的 event 集合。它提供该集合的 *integrity*（未被中间人篡改），不提供该 `scope` 下的 *completeness*（issuer 未静默丢弃属于该范围的其他 event）。即便实现额外叠加 Merkle / set commitment，恶意 issuer 仍可只承诺自己愿意承诺的子集——所以 batch receipt MUST NOT 被实现解释为 range completeness 证明。range completeness 由已注册的 active attestation event `ak.attestation.range_completeness`（payload schema `ak.schema.range_completeness_attestation.v1`）承担，其 `event_range` 必须有显式 range 语义（per-actor seq interval + frontier 上下界）+ witness quorum 或独立 seal 背书。详见 [`../sync/operations-sync.md`](../sync/operations-sync.md) §6.4 与 [`../overview/glossary.md`](../overview/glossary.md) *integrity vs completeness*。

> **概念分层**（normative）：`ak.event_batch_receipt` 是 **receipt object 名称**（不是 Event Envelope `kind`）。它的唯一 wire 形态是带 `schema = "ak.schema.event_batch_receipt.v1"` 字段的独立对象；它**不**出现在 [`event-kind-registry.json`](../../artifacts/registry/event-kind-registry.json) 中，**不**会作为 `Event.kind` 出现在 Events API 提交路径上，也**不**进入 reducer 输入。任何试图把 `ak.event_batch_receipt` 当作 Event kind 提交给 `ak.self.events.command.submit` 的实现 MUST `schema_violation`，因为 Event schema 的 `kind` enum 与 event-kind-registry 同步且不含此名。下游 SDK / conformance scanner 在 prose / fixture 中遇到 `ak.event_batch_receipt` 时 MUST 把它当 schema-id-prefix / receipt-object-name 处理，不进入 active event-kind 检查表。

与之对照：`ak.audit.ryw_receipt` 既是 receipt object 名（schema `ak.schema.audit_ryw_receipt.v1`），同时是 [`event-kind-registry.json`](../../artifacts/registry/event-kind-registry.json) 中 `status="active"` 的 **durable event kind**。其 object form 与 durable Event form 的触发条件由 Audit Applet Binding / release policy 决定：
>
> - `disclosed_policy` release MAY 只使用 object form，并把 receipt 作为 actor-private / scoped audit evidence 保存。
> - `attested_hardware` release SHOULD 将同一 receipt object 也作为 durable Event（`Event.kind = "ak.audit.ryw_receipt"`）写入 audit log，便于事后验证 release service 是否先见到 accepted `ak.audit.release`。详见 [`../crypto-media/audited-e2ee.md` §6](../crypto-media/audited-e2ee.md)。

### 5.2 Schema 与字段

Schema id: `ak.schema.event_batch_receipt.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `schema` | yes | `string` | 固定为 `ak.schema.event_batch_receipt.v1`。 | Receipt schema id。 |
| `receipt_id` | yes | `id:receipt` |  | Receipt ID。 |
| `issuer` | yes | `did` | 必须控制签名 key。 | 签发者，可以是 principal、Principal Server 或 witness。 |
| `scope` | yes | `object` | MUST 至少包含 `actor_id`、`realm_id` 或查询范围 hash 之一；Realm-scoped receipt MUST 包含 `realm_id`。 | receipt 覆盖范围。 |
| `frontier` | yes | `object` | MUST 至少包含 `actor_seq`、`event_id` / `event_digest`、HLC 或 Realm frontier 之一。 | 签发时前沿。 |
| `events` | yes | `array<hash \| receipt-item>` | canonical set：每项以 `canonical_json(item)` 的 UTF-8 bytes 为排序键严格升序，禁止重复。裸 `event_id` 不绑定内容，MUST NOT 出现。 | 被 receipt 覆盖的 Event canonical digest；数组位置没有业务语义。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `proofs` | yes | `array<Proof>` |  | Receipt proof。 |

`receipt-item` 的 closed wire 形态为 `{event_id: id:event, event_digest: hash, kind: string}`，用于同时承诺 Event identity、canonical content digest 与 kind 的 receipt profile；其中 `event_digest` 必须按 §3 的 Event digest 规则计算。该 object 整体作为 `events[]` item 进入 canonical JSON、排序键与 `receipt_digest` 输入，不得只对其中某个字段取 hash。`scope.kind="device_reanchor_unit"` 的 B 模型 Recovery Re-anchor Unit MUST 使用此形态，具体受理语义见 [`../identity/key-management.md`](../identity/key-management.md) §5.0.7。

签发方 MUST 在计算 `receipt_digest` 前按上述排序键对 `events[]` 排序并去重，并把规范化后的数组作为实际 wire 值签发；接收方 MUST 在验签前确认相邻排序键严格递增。非升序或含重复项的 receipt MUST 以 `schema_violation` 拒绝，不得通过本地静默重排后接受。对于 `scope.kind="device_reanchor_unit"`，数组仍是 canonical set：实现按 item 的 `kind` 找到唯一 `ak.device.reanchor` 与唯一 `ak.device.authorize`，分别与 `scope.reanchor_digest` / `scope.replacement_authorize_digest` 比对，不得依赖 `[0]` / `[1]` 位置。

## 6. Reducer 总则

Reducer MUST：

- 验证签名
- 验证 schema
- 验证 capability
- 按 causal order 处理
- 对相同 Event（相同 `event_id` 与 canonical digest）保持幂等：重复 apply 同一已接受 Event MUST NOT 产生额外状态变化或副作用
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
- Schemas：`artifacts/schemas/event-envelope.schema.json`（Proof 由其 `$defs.proof` 内嵌定义）、`artifacts/schemas/event-batch-receipt.schema.json`。
