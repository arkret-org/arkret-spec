---
title: Event, Proof, Patch & Receipt
---

## 1. 目标

本文集中定义 Contrix 协作图中的**事件 / 签名 / 增量 / 审计 receipt 对象**：

- **Event Envelope**（`cx:event:`）：reducer 输入与审计事实的 wire 表示。
- **Proof**：签名证明 envelope。
- **Field Patch (`cx.patch.v1`)**：非 create 类更新的标准字段增量格式。
- **Event Batch Receipt**（`cx:receipt:`）：可选审计 / 同步加速对象。

Move / Anchor / Lattice、cell 模型、authority chain 与 state 收敛细节由 [`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) 承担；本文聚焦对象级 schema、字段、reducer 总则与 patch 语义。

公共字段见 [`common-fields.md`](./common-fields.md)。

## 2. Event Envelope

### 2.1 概念

Event 是 reducer 输入和审计事实。所有协作变化最终都落为签名 `event`。Event 是审计根和 reducer 输入；当前态只是 Event 集合在某个 reducer profile 下的物化结果。

Reducer-input event 在顶层带 `preconditions[]` / `effects[]` / `anchor_ref`；非 reducer event 不带这三个字段。

Event Envelope 是 kind-routed payload 兼容层。v1 的协议状态收敛以 Move / Anchor / Lattice 为准；Event kind 可以作为 Move effect kind 与现有 Events API payload router 的稳定命名。

### 2.2 Schema 与字段

Schema id: `cx.schema.event.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `event_id` | yes | `id:event` | 事件稳定 typed ID。事件 canonical digest / proof hash 见 `conformance-vectors.md`。 | 事件 ID。 |
| `kind` | yes | `string` | 标准 effect kind SHOULD 使用 `cx.` 前缀。Registry 可声明 `cell_family`、`cell_subject`、`lattice` 和 `bottom`，供 Move effect / 兼容 reducer 使用。 | 事件 kind。 |
| `space_id` | yes | `id:space` | Space create 可在 payload 中建立。 | 所属 Space。 |
| `actor_id` | yes | `did` | 必须匹配 proof 控制链。 | 发送 Actor。 |
| `actor_seq` | yes | `integer` | 同一 actor 因果路径上严格递增；并发 sibling fork 可出现相同高度。 | Actor 链高度 / 防回退索引。 |
| `created_at` | yes | `timestamp` | 不能单独决定因果。 | 创建时间。 |
| `hlc` | yes | `string` | `<unix_ms_hex>-<logical_hex>-<node_id_hash>`。 | HLC。 |
| `prev_refs` | yes | `array<id:event>` | 可为空。 | Actor event chain 前序。 |
| `auth_refs` | yes | `array<id:event>` | create event 可为空；必须引用授权状态事件，不能直接引用 grant / policy object ID。 | 授权依赖。 |
| `requirements` | no | `object` | `requirements.{schema[], reducer, features[], critical_extensions[]}` 全部进入 canonical bytes 与 event digest；接收方 MUST fail closed 对未知 critical 项。`critical_extensions[]` 每项必须有 `id`、`scope`、`fail_closed=true`。 | 事件依赖声明（schema profile / reducer profile / feature / critical extension）。 |
| `redacts` | no | `id:event` 或 `hash` | 仅 redaction event 使用。 | 被撤回事件。 |
| `payload` | yes | `object` | 由 event kind schema 定义。 | 事件负载。 |
| `unsigned` | no | `object` | MUST NOT 进入 event digest。 | 本地/传输附加信息。 |
| `proofs` | yes | `array<Proof>` | 至少一个有效 proof。 | 签名证明。 |

### 2.3 最小 reducer-input event 示例

```json
{
  "event_id": "cx:event:019640ed-8000-7000-8000-000000000000",
  "space_id": "cx:space:0196419b-0000-7000-8000-000000000000",
  "actor_id": "did:web:alice.example",
  "actor_seq": 4,
  "kind": "cx.flow.update",
  "created_at": "2026-04-26T00:00:00Z",
  "hlc": "01970e589d21-0004-a13f9c2e",
  "prev_refs": [
    "cx:event:019640ed-0000-7000-8000-000000000000"
  ],
  "refs": [
    { "id": "cx:grant:0196410c-0000-7000-8000-000000000000", "role": "authorized_by", "critical": true }
  ],
  "preconditions": [
    {
      "cell": "cx:cell:cx.component.flow.fields.v1:cx:flow:019640c6-8000-7000-8000-000000000000",
      "predicate": { "op": "head_eq", "value": { "fields.status": "in_progress" } }
    }
  ],
  "effects": [
    {
      "cell": "cx:cell:cx.component.flow.fields.v1:cx:flow:019640c6-8000-7000-8000-000000000000",
      "op": { "kind": "set", "value": { "fields.status": "done" } }
    }
  ],
  "anchor_ref": "cx:anchor:sha256:0000000000000000000000000000000000000000000000000000000000000000",
  "payload": {
    "flow_id": "cx:flow:019640c6-8000-7000-8000-000000000000",
    "patch": {
      "fields.status": "done"
    }
  },
  "proofs": [
    {
      "kind": "detached_jws",
      "alg": "EdDSA",
      "verification_method": "did:web:alice.example#device-1",
      "payload_hash": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
      "created_at": "2026-04-26T00:00:00Z",
      "jws": "..."
    }
  ]
}
```

Event MUST 被签名。Reducer MUST 拒绝任何 signature、schema、capability 或 causal 校验失败的事件。

### 2.4 Payload 与 type 约定

Event Envelope 的顶层 `kind` 是唯一 payload discriminator。State convergence 不再从 envelope 推导 state slot；Move effect 必须显式给出 cell id 与 lattice op。

- `payload.type` 不得重复写入 `cx.*` Event kind。
- Payload 引用被创建对象时通过 `payload.object.id` 或 `payload.target_ref` 等 typed-id 字段表达，前缀（`cx:flow:` 等）即对象种类，不写单独的 `payload.object.type`。
- `actor_id` 是签署并提交该 Event 的 DID；物化对象的 `created_by` / `updated_by` 是 reducer 输出字段，通常来自对应 create/update Event 的 `actor_id`，但不得替代 Event proof、capability 或 Move refs 校验。
- 启用 minimal-metadata E2EE profile 时，`actor_id` MAY 是 Space / Flow track scoped pairwise DID；真实 principal DID 的映射必须通过加密的 `cx.identity_link`、claim disclosure 或 policy 声明验证，不得把非 DID pseudonym 写入 `actor_id`。

### 2.5 Create 类 Event 的跨字段语义校验

Create 类 Event 的 `payload.object` MAY 使用完整对象 schema 做 wire validation，但接收方在进入 accepted set 前还必须执行跨字段语义校验：

- `cx.space.create.payload.object.created_by_principal` MUST 等于顶层 `actor_id`。
- `cx.flow.create` / `cx.morph.create` / `cx.profile.create` 中的 `payload.object.created_by` 或 `principal_id` MUST 等于顶层 `actor_id` 或被该 profile 明确授权的 controller。
- `payload.object.created_at` MUST 等于顶层 `created_at`。

校验失败 MUST `schema_violation` 或 `capability_denied`，不得把 payload 中的创建者字段当作 proof、capability 或审计归属的替代来源。

### 2.6 `actor_seq` fork 约束

- Producer SHOULD 为同一 `actor_id` 维护单调本地链，避免主动产生同高 sibling fork。
- 同一 `actor_id` 的非 genesis event MUST 在 `prev_refs` 中引用至少一个该 actor 的 accepted predecessor；该 predecessor 的最大 `actor_seq` 必须是当前 `actor_seq - 1`，除非 profile 明确声明恢复/导入场景。
- 相同 `(actor_id, actor_seq)` 的多个 event 是 sibling fork。它们没有隐含先后顺序；展示排序可使用 HLC，但协议状态生效必须使用 Move preconditions、Anchor frontier 与 Lattice join。
- 实现 MUST 对同一 `(actor_id, actor_seq, prev_frontier_hash)` 接受的 sibling 数量设置上限；v1 public profile 的上限为 16，超过后 MUST quarantine 或要求 actor chain repair。
- 被判定为 rejected 的 fork 不推进 actor accepted frontier，也不得作为后续 accepted event 的 predecessor。

### 2.7 Requirements 与 critical extensions

`requirements.features[]` 与 `requirements.critical_extensions[].id` 必须使用可发现的 feature/profile 标识，并通过 service describe、profile registry 或 Space schema/policy 指向可验证定义。接收方不支持 critical feature 时 MUST fail closed；不得把未知 critical 语义当作普通未知字段保留后继续 accepted。

## 3. Proof

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `kind` | yes | `enum(detached_jws)` | 初版必须支持。 | 证明类型。 |
| `alg` | yes | `string` | 初版默认 `EdDSA`。 | 签名算法。 |
| `verification_method` | yes | `string` | DID URL。 | 公钥/设备方法。 |
| `payload_hash` | yes | `hash` | 必须绑定 canonical payload。 | 被签名 payload hash。 |
| `created_at` | yes | `timestamp` |  | 签名时间。 |
| `domain` | no | `string` | 跨服务 SHOULD 设置。 | 域绑定。 |
| `audience` | no | `string` 或 `array<string>` | 跨域/服务调用 SHOULD 设置。 | 受众绑定。 |
| `jws` | yes | `string` | detached JWS。 | 签名值。 |

DID proof JSON Schema MUST 与 [`../identity/identity-did.md`](../identity/identity-did.md) 的 Proof 和 [`../conformance/encoding.md`](../conformance/encoding.md) 的 canonical JSON 规则一致。

## 4. Field Patch (`cx.patch.v1`)

非 create 类更新建议使用 `cx.patch.v1` 做字段增量；客户端不得自行定义私有 dot-path 语义替代该标准。

### 4.1 结构

`cx.patch.v1` 为 map 类型：

- `key`：patch path（字段路径）。
- `value`：patch 操作，支持两种表达：
  - 直接值：等价于 `{"$op":"set","value":...}`。
  - 对象：`{"$op":"set|unset|add|remove","value":...}`。

### 4.2 patch path 规则

- path 由 `snake_case` 标识符或反引号转义字段名组成；
- 默认仅支持对象路径，不支持数字数组下标；
- 对 schema 声明了唯一 key 的具名集合数组（仅由 profile / 扩展引入；v1 标准 schema 不再含此类数组），path MAY 使用确定性 selector 段：`<field>[<key>=<value>]`。selector 字段必须是该数组项 schema 中声明唯一的 stable key，selector 值按 canonical JSON string 解析；匹配 0 项时 `set`/`add` MUST reject，匹配多项表示对象已违反 schema，reducer MUST fail closed。
- Flow `tracks` 在 v1 是 map（key 即 track 名），patch path 直接使用普通对象段，例如 `tracks.discussion.profile`，不需要 selector。
- `unset` 不允许带 `value`；
- `set`、`add`、`remove` 必须带 `value`。

客户端不能把数字数组下标写入 path；如需更新无 stable key 的列表元素，必须将对象重建为具名集合项、用 profile 注册的 move/update event，或使用明确的 API 约束字段表示更新目标。

### 4.3 在 Event 中的位置

Event Envelope 中，patch 永远嵌入 `payload.patch`，目标对象用 `payload.flow_id`、`payload.morph_id`、`payload.relation_id`、`payload.view_id` 或该 kind schema 声明的等价字段表达。详见 [`../sync/operations-sync.md`](../sync/operations-sync.md) §7.2 / §8。

## 5. Event Batch Receipt

### 5.1 概念

Event Batch Receipt 是可选审计/同步加速对象，**不是 canonical history**，也**不是 reducer input**。缺少 receipt 不得导致格式、签名、授权和因果均有效的 Event 被拒绝，除非 deployment profile 额外要求 witness。

### 5.2 Schema 与字段

Schema id: `cx.schema.event_batch_receipt.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `receipt_id` | yes | `id:receipt` |  | Receipt ID。 |
| `issuer` | yes | `did` | 必须控制签名 key。 | 签发者，可以是 principal、Principal Server 或 witness。 |
| `scope` | yes | `object` | SHOULD 包含 `actor_id`、`space_id` 或查询范围 hash。 | receipt 覆盖范围。 |
| `frontier` | yes | `object` | SHOULD 包含 `actor_seq`、`event_id` / event hash、HLC 或 Space frontier。 | 签发时前沿。 |
| `events` | yes | `array<id:event \| hash>` | 数组顺序参与 hash。 | 被 receipt 覆盖的 Event Envelope 引用。 |
| `created_at` | yes | `timestamp` |  | 创建时间。 |
| `proofs` | yes | `array<Proof>` |  | Receipt proof。 |

## 6. Reducer 总则

Reducer MUST：

- 验证签名
- 验证 schema
- 验证 capability
- 按 causal order 处理
- 对相同 Operation 保持幂等
- 保留未知字段
- 输出可声明的 reducer profile

具体 Move / Anchor / Lattice / state resolution 细节、authority chain、E2EE covered frontier 等见 [`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md)。

## 7. 规范性引用

- 公共字段：[common-fields.md](./common-fields.md)。
- Move / Anchor / Lattice / state resolution：[`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md)。
- Event-first 发布、snapshot、冲突收敛：[`../sync/operations-sync.md`](../sync/operations-sync.md)。
- Canonical JSON、HLC、cursor：[`../conformance/encoding.md`](../conformance/encoding.md)。
- Conformance vector：[`../conformance/conformance-vectors.md`](../conformance/conformance-vectors.md)。
- Schema / event registry：[`../conformance/schema-registry.md`](../conformance/schema-registry.md)。
- Schemas：`artifacts/schemas/event-schema.json`、`artifacts/schemas/proof.schema.json`、`artifacts/schemas/event-batch-receipt.schema.json`。
