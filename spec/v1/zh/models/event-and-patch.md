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
| `realm_id` | yes | `id:realm` | Realm create 可在 payload 中建立。 | 所属 Realm。 |
| `actor_id` | yes | `did` | 必须匹配 proof 控制链。 | 发送 Actor。 |
| `actor_seq` | yes | `integer` | 同一 actor 因果路径上严格递增；并发 sibling fork 可出现相同高度。 | Actor 链高度 / 防回退索引。 |
| `created_at` | yes | `timestamp` | 不能单独决定因果。 | 创建时间。 |
| `hlc` | no | `string` | `<unix_ms_hex>-<logical_hex>-<node_id_hash>`。**Advisory 字段** — 进入 canonical bytes 与签名以防被中间方重写，但语义上只是 timeline display tie-breaker，不参与 authorization、Lattice join、Move precondition、Anchor finality。详见 `encoding.md` §7。 | HLC（advisory）。 |
| `prev_refs` | yes | `array<id:event>` | 可为空。仅承载 actor event chain causal predecessors。 | Actor event chain 前序。 |
| `refs` | yes | `array<SemanticRef>` | 默认 `[]`。每项 `{id, role, critical?}`；常见 `role` 包括 `authorized_by`（**替代旧 `auth_refs[]` 字段**）、`attestation`、`parent_event`、`after`、`recovery_capability`、`state_witness`、`inclusion_proof`。`critical` 默认 `true`；未识别 critical role MUST fail closed，未识别非 critical role MAY 被忽略。 | 语义引用集合。 |
| `requirements` | no | `object` | `requirements.{schema[], reducer, features[], critical_extensions[]}` 全部进入 canonical bytes 与 event digest；接收方 MUST fail closed 对未知 critical 项。`critical_extensions[]` 每项必须有 `id`、`scope`、`fail_closed=true`。 | 事件依赖声明（schema profile / reducer profile / feature / critical extension）。 |
| `preconditions` | conditional | `array<Predicate>` | 仅 reducer-input event 携带；与 `effects[]` / `anchor_ref` 同步出现。非 reducer event（read marker / typing 等）MUST 省略。 | Move 多 cell 原子 CAS 的 pre-state 谓词。 |
| `effects` | conditional | `array<Effect>` | 仅 reducer-input event 携带；存在时 MUST 至少 1 项。 | Move 多 cell 原子 CAS 的 effect 集合。 |
| `anchor_ref` | conditional | `id:anchor` | 仅 reducer-input event 携带；MUST 指向接收方已知 Anchor，并落在 `max_anchor_staleness_ms` 窗口内。 | Move 提交基线 Anchor。 |
| `redacts` | no | `id:event` 或 `hash` | 仅 redaction event 使用。 | 被撤回事件。 |
| `payload` | yes | `object` | 由 event kind schema 定义。 | 事件负载。 |
| `unsigned` | no | `object` | MUST NOT 进入 event digest。 | 本地/传输附加信息。 |
| `proofs` | yes | `array<Proof>` | 至少一个有效 proof（`minItems: 1`）。 | 签名证明。 |


### 2.3 最小 reducer-input event 示例

```json
{
  "event_id": "cx:event:019640ed-8000-7000-8000-000000000000",
  "realm_id": "cx:realm:0196419b-0000-7000-8000-000000000000",
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
- 启用 `cx.profile.mls.minimal_metadata_space.v1` 时，`actor_id` MAY 是 Realm / Flow track scoped pairwise DID；真实 principal DID 的映射必须通过加密的 `cx.schema.identity_link.v1` payload（`cx.identity_link` application message / MLS private extension）、claim disclosure 或 policy 声明验证，不得把非 DID pseudonym 写入 `actor_id`。

### 2.5 Create 类 Event 的跨字段语义校验

Create 类 Event 的 `payload.object` MAY 使用完整对象 schema 做 wire validation，但接收方在进入 accepted set 前还必须执行跨字段语义校验：

- `cx.realm.create.payload.object.created_by_principal` MUST 等于顶层 `actor_id`。
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

`requirements.features[]` 与 `requirements.critical_extensions[].id` 必须使用可发现的 feature/profile 标识，并通过 service describe、profile registry 或 Realm schema/policy 指向可验证定义。接收方不支持 critical feature 时 MUST fail closed；不得把未知 critical 语义当作普通未知字段保留后继续 accepted。

**Per-event schema 版本绑定**：当 event 修改的对象使用 evolvable schema（典型是 Morph，但同样适用于任何 Realm-defined schema 容器对象）时，写入端 **MUST** 在 `requirements.schema[]` 中列出该 event 写入时对象实际遵循的 schema profile id 全集。reader 重放该 event 时 **MUST** 用 `requirements.schema[]` 绑定的 schema 版本进行 payload / patch / transition 验证，**不得**使用对象当前的 `schema_refs[]`。这保证 partial replication 与跨版本历史回放时验证结果一致，并锁定每个 event 的 schema 解释边界。详细规则与 Morph 特化语义见 [`morph.md` §4.1](./morph.md)。

## 3. Proof

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `kind` | yes | `enum(detached_jws)` | 初版必须支持。 | 证明类型。 |
| `alg` | yes | `string` | 初版默认 `EdDSA`。 | 签名算法。 |
| `verification_method` | yes | `string` | DID URL。 | 公钥/设备方法。 |
| `payload_hash` | yes | `hash` | MUST 等价于 `canonical_hash(envelope_without_proofs_unsigned)`：被签名输入是去除 `proofs` 与 `unsigned` 之后的整个 canonical Event envelope（含 `event_id`、`kind`、`actor_id`、`payload`、`refs`、`preconditions`、`effects`、`anchor_ref`、`requirements`、`hlc` 等），不是只绑定 `payload` 字段。 | 被签名的 canonical envelope hash。字段名按 `canonical_hash(envelope_without_proofs_unsigned)` 的全包含语义解读，不要按字面只绑定 `payload`。 |
| `created_at` | yes | `timestamp` |  | 签名时间。 |
| `domain` | no | `string` | 跨服务 SHOULD 设置。 | 域绑定。 |
| `audience` | no | `string` 或 `array<string>` | 跨域/服务调用 SHOULD 设置。 | 受众绑定。 |
| `jws` | yes | `string` | detached JWS。 | 签名值。 |

DID proof JSON Schema MUST 与 [`../identity/identity-did.md`](../identity/identity-did.md) 的 Proof 和 [`../conformance/encoding.md`](../conformance/encoding.md) 的 canonical JSON 规则一致。

## 4. Field Patch (`cx.patch.v1` / `cx.schema.patch.v1`)

非 create 类更新建议使用 `cx.patch.v1` 做字段增量；客户端不得自行定义私有 dot-path 语义替代该标准。

> **命名注意**：`cx.patch.v1` 是 **embedded format identifier**（spec prose 中的简称，用于指代 `payload.patch` 字段位置的 wire 形态），其结构 schema 已正式注册为 `cx.schema.patch.v1`，artifact 见 [`artifacts/schemas/patch.schema.json`](../../artifacts/schemas/patch.schema.json)。两个标识同源——format identifier 在中文规范与 prose 中保持兼容用法，schema_id 在 registry / SDK / lint 工具中作为可解析的 schema reference。实现 MUST 将 spec 中出现的 `cx.patch.v1` 引用解析到该 schema artifact；本节 §4.1–§4.3 是该 schema 的 normative 语义补充（grammar / parser 责任 / selector / redactable / reducer-managed 字段保护），artifact 自身不重复 normative 文字。

### 4.1 结构

`cx.patch.v1` 为 map 类型：

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

- `identifier` 与 `key-name` MUST 匹配正则 `^[a-z][a-z0-9_]{0,63}$`(snake_case,首字符必须小写字母,长度 ≤ 64);
- `selector-value` MUST 是合法的 [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785) JCS canonical JSON string,**包括外层 ASCII 双引号**,内部按 JCS 转义规则 (`\"` / `\\` / `\/` / `\b` / `\f` / `\n` / `\r` / `\t` / `\uXXXX`);
- selector-value 内字面 `]`、`[`、`=`、`"`、`\` MUST 出现为 `\uXXXX` 或对应反斜杠转义形式;
- `quoted-identifier` 用于字段名包含非 snake_case 字符的特殊场景(v1 标准 schema 不应使用),字面 backtick 必须 escape 成连续两个 backtick;
- 默认仅支持对象路径,不支持数字数组下标。

#### 4.2.2 Parser 责任

reducer / SDK 实现 MUST 使用确定性 parser:遇到任何 ambiguous match、超长 path(> 1024 字节)、超深嵌套(> 16 段)、非 canonical selector-value(未经 JCS 规范)时,MUST 返回 `schema_violation` reason=`patch_path_invalid`。Parser **MUST NOT** 走 fallback 路径——例如不得在 selector-value 中错位的 `]` 之后继续尝试匹配下一个 segment。

#### 4.2.3 Selector 语义

对 schema 声明了唯一 key 的具名集合数组(仅由 profile / 扩展引入;v1 标准 schema 不再含此类数组),path MAY 使用 selector segment。规则:

- selector 字段必须是该数组项 schema 中声明 `unique: true` 的 stable key;
- selector 值按 canonical JSON string 解析后用于精确比较;
- 匹配 0 项时 `set` / `add` MUST reject (`failed_precondition`, reason=`patch_selector_no_match`);
- 匹配多项表示对象已违反 schema 的 uniqueness 约束,reducer MUST fail closed (`failed_precondition`, reason=`patch_selector_ambiguous`);
- Flow `tracks` 在 v1 是 map(key 即 track 名),patch path 直接使用普通对象段,例如 `tracks.discussion.profile`,不需要 selector。

#### 4.2.4 Op 与 redactable 字段交互（normative）

`cx.patch.v1` 的 `$op="unset"` 路径 MUST NOT 操作以下 redactable 内容字段:

- Message: `content`、`encrypted_payload`、`body`
- Flow: `summary`、`description`、`encrypted_payload`、用户可写的长文本 fields
- Morph: `content`、`encrypted_payload`、`fields.<text-content-shape>` (由 morph profile 声明)
- 任何在 Realm schema 中标记为 `redactable: true` 的字段。

理由: 这些字段的清除必须走 `cx.<kind>.redact` 或 `cx.redaction` event,以触发 redaction-specific capability check + audit anchor + retention policy;允许用 `cx.patch.v1` 直接 `unset` 等价于让任何持有 `cx.<kind>.update` 的 actor 绕过 `cx.<kind>.redact` 的高 tier capability 完成 redaction (redaction escape)。

reducer MUST 在 patch path 命中 redactable field + `$op="unset"` 时返回 `schema_violation` reason=`patch_unset_redactable_field`。

#### 4.2.5 Op 其余规则

- `unset` 不允许带 `value`(空 value object MUST 视作 `{"$op":"unset"}`);
- `set`、`add`、`remove` 必须带 `value`;
- 客户端不能把数字数组下标写入 path; 如需更新无 stable key 的列表元素,必须将对象重建为具名集合项、用 profile 注册的 move/update event,或使用明确的 API 约束字段表示更新目标;
- path MUST NOT 操作 reducer-managed 字段: `id` / `schema` / `realm_id` / `created_by` / `created_at` / `state` / `state_changed_at` (这些字段由对应 lifecycle event 而非 patch 修改;见 [`common-fields.md` §5](./common-fields.md))。reducer 在 path 命中该集合时 MUST `schema_violation` reason=`patch_path_reducer_managed`。

### 4.3 在 Event 中的位置

Event Envelope 中，patch 永远嵌入 `payload.patch`，目标对象用 `payload.flow_id`、`payload.morph_id`、`payload.relation_id`、`payload.view_id` 或该 kind schema 声明的等价字段表达。详见 [`../sync/operations-sync.md`](../sync/operations-sync.md) §7.2 / §8。

## 5. Event Batch Receipt

### 5.1 概念

Event Batch Receipt 是可选审计/同步加速对象，**不是 canonical history**，也**不是 reducer input**。缺少 receipt 不得导致格式、签名、授权和因果均有效的 Event 被拒绝，除非 deployment profile 额外要求 witness。

Receipt 的覆盖语义是 **set-bound**：`events[]` 列出 issuer *选择* 承诺的 event 集合。它提供该集合的 *integrity*（未被中间人篡改），不提供该 scope 下的 *completeness*（issuer 未静默丢弃属于该范围的其他 event）。即便实现额外叠加 Merkle / set commitment，恶意 issuer 仍可只承诺自己愿意承诺的子集——所以 batch receipt MUST NOT 被实现解释为 range completeness 证明。range completeness 由已注册的 active attestation event `cx.attestation.range_completeness`（payload schema `cx.schema.range_completeness_attestation.v1`）承担，其 scope 必须有显式 range 语义（per-actor seq interval + frontier 上下界）+ witness quorum 或独立 anchor 背书。详见 [`../sync/operations-sync.md`](../sync/operations-sync.md) §4.2 与 [`../overview/glossary.md`](../overview/glossary.md) *integrity vs completeness*。

> **概念分层**（normative）：`cx.event_batch_receipt` 是 **receipt object 名称**（不是 Event Envelope `kind`）。它的唯一 wire 形态是带 `schema = "cx.schema.event_batch_receipt.v1"` 字段的独立对象；它**不**出现在 [`event-kind-registry.json`](../../artifacts/registry/event-kind-registry.json) 中，**不**会作为 `Event.kind` 出现在 Events API 提交路径上，也**不**进入 reducer 输入。任何试图把 `cx.event_batch_receipt` 当作 Event kind 提交给 `cx.events.submit` 的实现 MUST `schema_violation`，因为 Event schema 的 `kind` enum 与 event-kind-registry 同步且不含此名。下游 SDK / cotest scanner 在 prose / fixture 中遇到 `cx.event_batch_receipt` 时 MUST 把它当 schema-id-prefix / receipt-object-name 处理，不进入 active event-kind 检查表。

与之对照：`cx.audit.ryw_receipt` 既是 receipt object 名（schema `cx.schema.audit_ryw_receipt.v1`），同时是 [`event-kind-registry.json`](../../artifacts/registry/event-kind-registry.json) 中 `status="active"` 的 **durable event kind**。其 object form 与 durable Event form 的触发条件：
>
> - `cx.profile.disclosed_audit.e2ee.v1`：仅 object form，actor-private / ephemeral，不进入 audit log Event 流。
> - `cx.profile.attested_audit.e2ee.v1`：同一 receipt object 也作为 durable Event（`Event.kind = "cx.audit.ryw_receipt"`）写入 audit log，便于事后调查。详见 [`../crypto-media/audited-e2ee.md` §4.1](../crypto-media/audited-e2ee.md)。

### 5.2 Schema 与字段

Schema id: `cx.schema.event_batch_receipt.v1`

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
- Schemas：`artifacts/schemas/event-schema.json`（含 `$defs.proof` — Proof 是 event-schema 内嵌定义，不再发布为独立 `proof.schema.json` 文件）、`artifacts/schemas/event-batch-receipt.schema.json`。
