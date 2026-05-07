---
title: Conformance Vectors
---

本文整合所有 v1 conformance 测试向量，按域分组：

1. Encoding & crypto（canonical JSON、digest、signature binding、HLC、cursor、encrypted envelope）
2. State resolution（并发 membership / capability / governance state 收敛）
3. Redaction（约束与可见性）
4. Capability（delegation、revoke、approval）
5. Sync（client sync、pagination、snapshot、MLS epoch backfill）

可执行向量数据集位于 [`spec/v1/artifacts/fixtures/`](../../artifacts/fixtures/)；
本文档把对应规范条款与文件入口集中呈现，便于一致性测试 runner 引用。

## 1. Encoding & Crypto Vectors

> 来源：原 `conformance-vectors.md`（已合并）

### 1.1 目标

本文定义 Contrix canonical JSON、hash、event digest、event-batch receipt digest、signature binding、HLC、cursor 与 encrypted envelope digest 的一致性测试向量。

这些向量是 `encoding.md` 的测试化补充。实现只要在 hash 输入、字段排序、签名绑定或时间排序上产生差异，就不能声称与 Contrix v1 编码 profile 互操作。

### 1.2 通用规则

向量名称使用：

```text
cx.vector.encoding.<name>.v1
```

实现 MUST 对每个向量报告：

- input object 或 input bytes
- canonical bytes
- expected digest 或 expected order
- 实际输出
- pass / fail

除特别声明外，digest 均使用：

```text
sha256:<lowercase_hex_digest>
```

### 1.3 Vector: Canonical JSON Basic

向量名称：

```text
cx.vector.encoding.canonical_json.basic.v1
```

输入对象：

```json
{
  "b": 2,
  "a": 1
}
```

期望 canonical bytes 的 UTF-8 文本表示：

```json
{"a":1,"b":2}
```

期望 digest：

```text
sha256:43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777
```

失败条件：

- 输出包含空格、换行或缩进。
- 字段顺序为 `b` 后 `a`。
- hash 输入使用非 canonical JSON。

### 1.4 Vector: Canonical JSON Nested

向量名称：

```text
cx.vector.encoding.canonical_json.nested.v1
```

输入对象：

```json
{
  "z": {
    "b": "beta",
    "a": "alpha"
  },
  "name": "Alice",
  "arr": [true, false, null]
}
```

期望 canonical bytes 的 UTF-8 文本表示：

```json
{"arr":[true,false,null],"name":"Alice","z":{"a":"alpha","b":"beta"}}
```

判定规则：

- object key MUST 在每一层独立按 Unicode code point 升序排序。
- array item order MUST 保持输入顺序。
- string value MUST 不因为 key 排序被改写。

### 1.5 Vector: Reject Non-Canonical Numbers

向量名称：

```text
cx.vector.encoding.reject_noncanonical_numbers.v1
```

以下输入 MUST 被拒绝为签名/hash 输入：

```text
[
  {"n": NaN},
  {"n": Infinity},
  {"n": -Infinity},
  {"n": 1.0},
  {"n": 1e0}
]
```

判定规则：

- NaN / Infinity / -Infinity MUST reject。
- `-0` MUST reject。
- 若 JSON parser 接收 `1.0` 或 `1e0`，canonicalizer MUST 将其归一到 RFC 8785 / JCS 等价的唯一 number 表示；无法保证精确往返或唯一 decimal serialization 时 MUST reject。
- 签名验证 MUST 在 canonicalization 成功后才执行。

实现报告 MUST 明确其 number profile。声明任何包含 `confidence`、`progress` 或其他 JSON number 字段的 profile 时，必须支持 `decimal_canonical`；否则只能声明不支持这些 profile 或拒绝相关事件。

#### 1.5.1 Vector: Reject Malformed JSON

向量名称：

```text
cx.vector.encoding.reject_malformed_json.v1
```

以下输入 MUST 在 canonicalization 前或 canonicalization 阶段失败，不能进入签名验证、hash 计算或 reducer：

- malformed UTF-8。
- JSON object duplicate key，例如同一层同时出现两个 `"event_id"`。
- lone surrogate 或无法唯一解释的转义字符串。
- 非标准 JSON literal，例如 `NaN`、`Infinity`。
- parser 接收但 canonicalizer 无法唯一序列化的 number。

判定规则：

- duplicate key 不得按 parser 默认行为静默覆盖。
- malformed string 不得被替换成 U+FFFD 后继续签名。
- reject 结果 MUST 可审计，错误码 SHOULD 使用 `schema_violation`、`invalid_canonical_json` 或 `invalid_encoding`。

### 1.6 Vector: Event Digest

向量名称：

```text
cx.vector.encoding.event_digest.v1
```

输入事件，不含 `proofs` 和 `unsigned`，但包含稳定 `event_id`：

```json
{
  "event_id": "cx:event:01js0ev0000000000000000000",
  "kind": "cx.message.create",
  "space_id": "cx:space:01js0ke0000000000000000000",
  "actor_id": "did:web:alice.example",
  "actor_seq": 1,
  "created_at": "2026-04-26T00:00:00Z",
  "hlc": "01970e589d21-0004-a13f9c2e",
  "prev_refs": [],
  "auth_refs": [],
  "payload": {
    "flow_id": "cx:flow:01js0ke0000000000000000000",
    "content": {
      "type": "cx.content.text",
      "body": "hello"
    }
  }
}
```

期望 canonical bytes 的 UTF-8 文本表示：

```json
{"actor_id":"did:web:alice.example","actor_seq":1,"auth_refs":[],"created_at":"2026-04-26T00:00:00Z","event_id":"cx:event:01js0ev0000000000000000000","hlc":"01970e589d21-0004-a13f9c2e","kind":"cx.message.create","payload":{"content":{"body":"hello","type":"cx.content.text"},"flow_id":"cx:flow:01js0ke0000000000000000000"},"prev_refs":[],"space_id":"cx:space:01js0ke0000000000000000000"}
```

期望 digest：

```text
sha256:37eb534e16becc3637a78ea7477dbc250b600c01d6d7bdce56a13d383868f02c
```

判定规则：

- event digest / proof `payload_hash` MUST 从 redaction 前、去除 `proofs` 与 `unsigned` 后的 canonical event bytes 派生；`event_id` 是稳定 `cx:event:*` typed ID，必须进入 digest，但不替代 digest。
- 实现 MUST NOT 把 transport envelope、HTTP header、Sync Service metadata、local receive time 放入 event digest。
- 同一事件在不同 Events API 或 Sync Service 上 MUST 得到相同 digest。

### 1.7 Vector: Event Batch Receipt Digest

向量名称：

```text
cx.vector.encoding.event_batch_receipt_digest.v1
```

输入 Event Batch Receipt，不含 proof：

```json
{
  "schema": "cx.schema.event_batch_receipt.v1",
  "receipt_id": "cx:receipt:01js0rc0000000000000000000",
  "issuer": "did:web:alice.example",
  "scope": {
    "actor_id": "did:web:alice.example"
  },
  "frontier": {
    "actor_seq": 1,
    "event_hash": "sha256:1111111111111111111111111111111111111111111111111111111111111111"
  },
  "events": [
    "sha256:1111111111111111111111111111111111111111111111111111111111111111"
  ],
  "created_at": "2026-04-26T00:00:00Z"
}
```

期望 canonical bytes 的 UTF-8 文本表示：

```json
{"created_at":"2026-04-26T00:00:00Z","events":["sha256:1111111111111111111111111111111111111111111111111111111111111111"],"frontier":{"actor_seq":1,"event_hash":"sha256:1111111111111111111111111111111111111111111111111111111111111111"},"issuer":"did:web:alice.example","receipt_id":"cx:receipt:01js0rc0000000000000000000","schema":"cx.schema.event_batch_receipt.v1","scope":{"actor_id":"did:web:alice.example"}}
```

期望 digest：

```text
sha256:8c258c3d2a10704ad0a1fa487b3046f2e76c7a7eeb32781446421d73cf9e84d3
```

失败条件：

- `events` 数组被排序或去重后再 hash。
- proof 字段被包含进 receipt digest。
- `issuer`、`scope`、`frontier` 或 `schema` 被排除在 digest 外。
- `receipt_id` 大小写被实现私自改写。

### 1.8 Vector: Signature Binding Payload

向量名称：

```text
cx.vector.encoding.signature_binding_payload.v1
```

签名前的 binding object：

```json
{
  "payload_hash": "sha256:43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777",
  "actor_id": "did:web:alice.example",
  "verification_method": "did:web:alice.example#device-1",
  "created_at": "2026-04-26T00:00:00Z"
}
```

期望 canonical bytes 的 UTF-8 文本表示：

```json
{"actor_id":"did:web:alice.example","created_at":"2026-04-26T00:00:00Z","payload_hash":"sha256:43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777","verification_method":"did:web:alice.example#device-1"}
```

期望 digest：

```text
sha256:5b8863e858c1964ca1901d27ce687b65d87dcef0d3535ed617de7b4763cfdaf8
```

判定规则：

- proof MUST bind payload hash、actor DID、verification method 和 created_at。
- 需要跨服务或跨域验证时，profile SHOULD 额外绑定 domain / audience。
- 签名算法测试向量由本文件第 13 节的 crypto fixture 要求补充真实 public key 和 detached JWS；本文固定签名前 canonical binding 输入。

### 1.9 Vector: HLC Order

向量名称：

```text
cx.vector.encoding.hlc_order.v1
```

输入 HLC：

```json
[
  "01970e589d21-0004-bbbbbbbb",
  "01970e589d20-0009-ffffffff",
  "01970e589d21-0003-ffffffff",
  "01970e589d21-0004-a13f9c2e"
]
```

期望升序：

```json
[
  "01970e589d20-0009-ffffffff",
  "01970e589d21-0003-ffffffff",
  "01970e589d21-0004-a13f9c2e",
  "01970e589d21-0004-bbbbbbbb"
]
```

判定规则：

- HLC MUST 按 `(unix_ms, logical, node_id_hash)` 排序。
- 实现 MUST NOT 把 HLC 当作本地 wall clock string 进行非结构化比较，除非 profile 保证 fixed-width lowercase hex 且比较结果等价。

### 1.10 Vector: HLC Logical Overflow

向量名称：

```text
cx.vector.encoding.hlc_logical_overflow.v1
```

输入状态：

```json
{
  "last_emitted_hlc": "01970e589d21-ffff-a13f9c2e",
  "observed_unix_ms_hex": "01970e589d21",
  "next_event_requires_same_actor_write": true
}
```

期望行为：

- 生产者 MUST NOT 生成 `01970e589d21-0000-a13f9c2e` 或任何同毫秒回绕后的 HLC。
- 生产者 MUST 选择以下两种结果之一：
  - 等待到更大的 `unix_ms_hex`，然后生成形如 `01970e589d22-0000-a13f9c2e` 的 HLC。
  - 在 canonical bytes 生成前返回本地临时错误，例如 `hlc_logical_overflow`，由调用方重试。
- 重试或等待期间，事件的 `prev_refs`、`auth_refs` 与 `actor_seq` 约束不得被放松。

失败条件：

- 逻辑计数器回绕到更小值并继续发出事件。
- 通过伪造更大的 wall clock skew 逃避 overflow，同时破坏本地 HLC 单调性或 causal 约束。
- 消费者把上述回绕值当作正常排序输入接受并推进 accepted history。

### 1.11 Vector: Cursor Opaqueness

向量名称：

```text
cx.vector.encoding.cursor_opaque.v1
```

输入 cursor（合法 v1 wire 形态，遵循 `encoding.md` §8.2 的 `{v, t, s, d?, x}` payload 结构）：

```text
cx:cursor:eyJzIjp7ImN4OnNwYWNlOjAxanMwc3AwMDAwMDAwMDAwMDAwMDAwMDAwIjpbImN4OmV2ZW50OjAxanMwZXYwMDAwMDAwMDAwMDAwMDAwMDAwIl19LCJ0IjoiY2xpZW50X3N5bmMiLCJ2IjoxLCJ4IjoiMjAyNi0xMi0zMVQyMzo1OTo1OVoifQ
```

cursor base64url 解码后对应 canonical JSON：

```text
{"s":{"cx:space:01js0sp0000000000000000000":["cx:event:01js0ev0000000000000000000"]},"t":"client_sync","v":1,"x":"2026-12-31T23:59:59Z"}
```

期望客户端行为：

- 客户端 MUST 把 cursor 当作不透明字符串保存和回传。即使 cursor 的内部结构是 `encoding.md` §8.2 规定的合法 `{v, t, s, d?, x}` 形态，客户端 SDK / 应用层 MUST NOT 解析它的内部字段来构造请求。
- 客户端 MUST NOT 依赖 base64url 解码后的 `s.<space_id>` frontier 或 `x` 过期字段构造下一页请求；这些字段的存在只是为了让服务端可以无状态地恢复同步进度。
- 服务端 MAY 改变 cursor 内部编码或字段集合，只要同一 query/session 下 cursor 仍按 API contract 可用。
- 服务端 MUST 在收到该 cursor 时，按 §8.3 校验 `v ∈ supported_versions`、`x` 未过期、所有 frontier event 引用合法；任何校验失败 MUST 返回 `invalid_cursor` reason_code（见 `error-code-registry.json`）。

失败条件：

- 客户端解析 `s` / `x` 后自行构造下一页请求或修改 cursor 内容。
- 客户端在 cursor 解码失败时拒绝整个协议，而不是按 opaque token 处理。
- 服务端使用违反 `{v, t, s, d?, x}` 结构的 cursor 内部 payload（例如旧草稿中出现过的 `{query_hash, last_event_id}` 形式）。

### 1.12 Vector: Encrypted Envelope Digest

向量名称：

```text
cx.vector.encoding.encrypted_envelope_digest.v1
```

cleartext metadata canonical bytes 的 UTF-8 文本表示：

```json
{"content_type":"application/json","encryption":"mls-rfc9420","epoch":7}
```

ciphertext bytes 的 UTF-8 测试表示：

```text
ciphertext-example-001
```

期望 digest：

```text
sha256:3bef5270548d5b2c14e46ac1c9a801376d243ca6d71b914ec1d3283268a981fa
```

判定规则：

- digest 输入 MUST 为 `canonical_json(cleartext_metadata) || ciphertext_bytes`。
- 实现 MUST NOT hash 明文 payload。
- 实现 MUST NOT 省略路由和解密所需的 cleartext metadata，否则 sync service 无法安全去重和审计密文 envelope。

### 1.13 覆盖矩阵

| 向量 | Minimal Client | Full Client | E2EE Client | Events API | Principal Server |
| --- | --- | --- | --- | --- | --- |
| `cx.vector.encoding.canonical_json.basic.v1` | MUST | MUST | MUST | MUST | MUST |
| `cx.vector.encoding.canonical_json.nested.v1` | MUST | MUST | MUST | MUST | MUST |
| `cx.vector.encoding.reject_noncanonical_numbers.v1` | MUST | MUST | MUST | MUST | SHOULD |
| `cx.vector.encoding.reject_malformed_json.v1` | MUST | MUST | MUST | MUST | MUST |
| `cx.vector.encoding.event_digest.v1` | SHOULD | MUST | MUST | MUST | SHOULD |
| `cx.vector.encoding.event_batch_receipt_digest.v1` | MAY | SHOULD | SHOULD | SHOULD | MAY |
| `cx.vector.encoding.signature_binding_payload.v1` | MUST | MUST | MUST | MUST | MUST |
| `cx.vector.encoding.crypto.ed25519_detached_jws.v1` | MUST | MUST | MUST | MUST | MUST |
| `cx.vector.encoding.hlc_order.v1` | MUST | MUST | MUST | MUST | SHOULD |
| `cx.vector.encoding.cursor_opaque.v1` | MUST | MUST | MUST | MAY | SHOULD |
| `cx.vector.encoding.encrypted_envelope_digest.v1` | MAY | SHOULD | MUST | MAY | MUST |

### 1.14 Crypto Fixture 要求

自动化 conformance suite MUST 加载 `spec/v1/artifacts/fixtures/crypto-signature-fixture.json`。该 fixture 固定了 `cx.vector.encoding.crypto.ed25519_detached_jws.v1`：

- Ed25519 public key / private test key
- detached JWS signature
- DID Document verification method
- canonical Event payload、`payload_hash`、proof binding object、detached JWS signing input 和 expected rejection 条件

后续 conformance suite 仍应增加扩展 fixture：

- key rotation 后的 signature verification
- redaction 前后 event digest 验证

测试私钥只能用于公开测试向量，不得被任何生产实现信任。生产 profile MUST 拒绝测试 DID、测试 key id 或测试 trust domain。

## 2. Move · Anchor · Lattice Vectors

> 来源：`move-anchor-lattice-fixture.json`。

### 2.1 目标

本节把 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) 的 Move、Anchor、Lattice 规则转成可复现向量。实现必须对每个向量输出：

- `vector_id`
- Move 验证结果
- Anchor 应用结果
- `query(cell)` 的 value 或 structured bottom
- `state_root` / inclusion proof（当 fixture 要求时）

### 2.2 Vector: 多 Cell Ban + Revoke 原子 Move

向量名称：

```text
cx.vector.move_anchor_lattice.multi_cell_ban_revoke.v1
```

输入：

- `member.alice` cell 当前为 `join`。
- 两个 grant cell 当前为 `active`。
- 一个 Move 同时声明三个 `head_eq` precondition，并写入 ban + 两个 revoke/remove effects。

期望：

- 三个 precondition 全部成立时 Move PASS。
- 任一 precondition 不成立时整个 Move FAIL，不能部分撤销 grant 或部分 ban。

### 2.3 Vector: `cas-register` 并发冲突返回 Bottom

向量名称：

```text
cx.vector.move_anchor_lattice.cas_bottom.v1
```

输入：

- 两个 anchored Move 并发写同一 `cas-register + bottom=reject` policy cell。

期望：

- `query(cell)` 返回 structured `Bottom{kind="conflict"}`。
- 依赖该 cell 的后续 Move MUST `fail_bottom`。
- 实现不得用 HLC、actor id、event id 或本地接收顺序选择 winner。

### 2.4 Vector: Anchor Batch Pre-State

向量名称：

```text
cx.vector.move_anchor_lattice.anchor_batch_pre_state.v1
```

输入：

- 同一 Anchor frontier 新增 M1 与 M2。
- M2 的 precondition 只有在读取 M1 effect 后才成立。

期望：

- Anchor MUST reject。
- 同一 Anchor batch 内的新 Move 以 predecessor joined state 验证；不能自我满足。

### 2.5 Vector: MLS Commit Move Covered Frontier

向量名称：

```text
cx.vector.move_anchor_lattice.mls_covered_frontier.v1
```

输入：

- MLS Commit Move 写入 `mls_epoch_cell`。
- precondition 要求 `covered_frontier_cell` 包含指定 governance Anchor。
- 当前 `covered_frontier_cell` 未覆盖该 Anchor。

期望：

- MLS Commit Move `fail_precondition`。
- 普通 governance / recovery Move 不依赖 `covered_frontier_cell`，仍可被 Anchor 推进。

### 2.6 Vector: Anchorer Cell ⊥ → Recovery Anchorer 上位

向量名称：

```text
cx.vector.move_anchor_lattice.anchorer_cell_bottom_recovery.v1
```

输入：

- Space 以 `anchor_profile=mixed` 起始；`primary=did:web:host-a.example`，`recovery_members=[did:web:recovery-1.example, did:web:recovery-2.example]`。
- 两条并发 Move 在 anchorer cell（cas-register, bottom=reject）上提交不同 value。

期望：

- anchorer cell join → ⊥；Space 状态 `anchorer_paused`。
- 普通 Anchor 推进 MUST 阻塞。
- 仅 `recovery_members` 中 DID 签发的 recovery Anchor 才能重置 anchorer cell。
- 恢复后 Space 状态回到 `effective`。

### 2.7 Vector: Signed Compaction Anchor 等价 Effective View

向量名称：

```text
cx.vector.move_anchor_lattice.signed_compaction_equivalent.v1
```

输入：

- 两个并存 Anchor leaves L1、L2（同 Space）。
- 一条由 anchorer 签发的 compaction Anchor C 试图替代 (L1, L2)。

期望：

- C 的 `predecessor_refs == sorted([L1.id, L2.id])`、`frontier == union(L1.frontier, L2.frontier)`、`state_root == recompute(joined_state(L1, L2))`。
- 任一不满足 MUST reject（包括缺签名）。
- 接受后保留 bottom diagnostics 与签名验证链；不得丢失原 leaves 上可观察到的诊断结构。

### 2.8 Vector: Anchor DAG Genesis 与多 Leaf 计算

向量名称：

```text
cx.vector.move_anchor_lattice.anchor_dag_genesis_multi_leaf.v1
```

输入与期望（多 case 矩阵）：

1. **Genesis case**：`predecessor_refs=[]` 仅在 genesis Anchor 上合法。
2. **Non-genesis empty predecessors**：`predecessor_refs=[]` 但 frontier 非空 MUST reject。
3. **Multi-leaf effective view**：`effective_anchor_view(leaves)` 是纯本地函数（不需签名、不是新 Anchor object、deterministic）。
4. **Signed compaction**：要把多 leaf 持久压缩成单 Anchor 必须由 anchorer 签发；否则只能作为 view 使用。

## 3. Redaction Vectors

> 来源：原 `conformance-vectors.md`（已合并）

### 3.1 目标

本文件定义 redaction 的执行顺序、保留字段与可见性收敛规则。  
所有实现必须将 redaction 视为“可验证的内容裁剪”，而非删除事件。

向量命名：

```text
cx.vector.redaction.<scenario>.v1
```

### 3.2 Vector: 字段保留规则

向量名称：

```text
cx.vector.redaction.preserve_fields.v1
```

输入：

```json
{
  "target_event": {
    "event_id": "cx:event:01js0mrc000000000000000000",
    "kind": "cx.message.create",
    "space_id": "cx:space:01js0ms0000000000000000000",
    "actor_id": "did:web:alice.example.com",
    "created_at": "2026-04-26T00:00:00Z",
    "hlc": "01970e589d24-0001-aaaaaaaa",
    "prev_refs": [],
    "auth_refs": [],
    "payload": {
      "flow_id": "cx:flow:01js0mrd000000000000000000",
      "content": {
        "type": "cx.content.text",
        "body": "private notes"
      },
      "mentions": [
        "@bob"
      ],
      "attachments": [
        "hash:img1",
        "hash:img2"
      ],
      "fields": {
        "rank": 10
      }
    },
    "client_generated": {
      "draft_id": "d-001",
      "ui_last_seen": "2026-04-26T00:00:01Z"
    }
  },
  "redaction_event": {
    "event_id": "cx:event:01js0rm0v00000000000000000",
    "kind": "cx.redaction",
    "space_id": "cx:space:01js0ms0000000000000000000",
    "actor_id": "did:web:alice.example.com",
    "created_at": "2026-04-26T00:00:02Z",
    "hlc": "01970e589d24-0002-bbbbbbbb",
    "prev_refs": [
      "cx:event:01js0mrc000000000000000000"
    ],
    "auth_refs": [
      "cx:event:01js0cap000000000000000000"
    ],
    "payload": {
      "redacts": "cx:event:01js0mrc000000000000000000",
      "reason_code": "policy_recall"
    }
  }
}
```

期望结果：

```json
{
  "event_id": "cx:event:01js0mrc000000000000000000",
  "state": "redacted",
  "kept_envelope_fields": [
    "event_id",
    "kind",
    "space_id",
    "actor_id",
    "created_at",
    "hlc",
    "prev_refs",
    "auth_refs",
    "proofs",
    "hashes",
    "redacted_by",
    "redaction_reason_code"
  ],
  "removed_fields": [
    "content",
    "client_generated",
    "mentions",
    "attachments"
  ]
}
```

判定要求：

- `redacts` 目标事件必须在 reducer 可见集合中存在。
- 重放前后事件必须保留 event_id/hash 的验证可追踪性。
- 目标事件的 `content`、`mentions`、`attachments`、`client_generated` 不得再对外展示。

失败判定：

- 把事件当作 tombstone 并抹去事件本体。
- 保留 `client_generated` 等不可验证字段。
- 修改 `event_id` 或 `hlc`。

### 3.3 Vector: redaction 与 policy scope

向量名称：

```text
cx.vector.redaction.policy_scope.v1
```

输入序列（先后顺序如下）：

1) 正常消息事件（可见策略允许）
2) policy 屏蔽事件（mark quarantined）
3) redaction（撤回）
4) redaction 之后查询 / 回放

```json
{
  "timeline": [
    {
      "event_id": "cx:event:01js0qv1000000000000000000",
      "kind": "cx.message.create",
      "space_id": "cx:space:01js0ms0000000000000000000",
      "created_at": "2026-04-26T00:00:00Z",
      "hlc": "01970e589d25-0001-11111111",
      "payload": {
        "flow_id": "cx:flow:01js0qv1000000000000000000",
        "content": {
          "type": "cx.content.text",
          "body": "bad link: spam.example/phish"
        }
      }
    },
    {
      "event_id": "cx:event:01js0qv2c00000000000000000",
      "kind": "cx.policy.action",
      "space_id": "cx:space:01js0ms0000000000000000000",
      "created_at": "2026-04-26T00:00:01Z",
      "hlc": "01970e589d25-0001-22222222",
      "actor_id": "did:web:policy-bot.example.com",
      "payload": {
        "target_id": "cx:event:01js0qv1000000000000000000",
        "scope": "public",
        "decision": "quarantine"
      }
    },
    {
      "event_id": "cx:event:01js0qv3r00000000000000000",
      "kind": "cx.redaction",
      "space_id": "cx:space:01js0ms0000000000000000000",
      "actor_id": "did:web:policy-admin.example",
      "payload": {
        "redacts": "cx:event:01js0qv1000000000000000000",
        "reason_code": "policy_recall"
      }
    }
  ]
}
```

期望：

- Projection 不得展示已 redacted 的 `content`，但应保留 stripped 证据用于审计。
- 历史可见性为 `world_readable` 时，外部审计仍应看到 redaction 事实而不是原文。
- 冻结空间（frozen space）与历史归档（archived event）场景下，timeline 位置必须保留，不能物理删除。
- policy 的 `quarantine` 仍需要保留 redaction 后事件的 `event_id` 指纹映射。

失败判定：

- 在 redaction 后把事件从 timeline 移除。
- 使用完整明文替代 redaction 保留字段。
- 将 `quarantine` 解释为“删除”而非显示约束。

### 3.4 Vector: hard erasure receipt

向量名称：

```text
cx.vector.redaction.hard_erasure_receipt.v1
```

期望：

- hard erasure 在被测存储边界内删除 payload bytes 与派生明文。
- 实现保留 verification stub：原始 event id、验证事件图所需的 Event envelope digest / proof `payload_hash`、redaction event id、erasure reason、执行服务 DID、执行时间和签名 receipt。
- stub 不得额外保留已擦除明文字段的 standalone content hash、payload-only digest 或未加盐搜索 fingerprint；若审计必须保留内容承诺，必须使用每事件 salt 或 HMAC/pepper commitment，并把 secret 留在 legal-hold 边界或按 erasure policy 销毁。
- backfill 返回 redacted / erased stub，不伪造替代事件，也不静默造成历史缺口。
- legal hold 存在时阻止 hard erasure，但默认展示仍应用 redaction。

### 3.5 Vector: snapshot pruning retains verification stub

向量名称：

```text
cx.vector.redaction.snapshot_pruning_stub.v1
```

输入：

1. target event 被 accepted。
2. redaction event 被 accepted。
3. 服务按 retention policy 裁剪 target payload，并生成覆盖该 frontier 的 snapshot。

期望：

- snapshot chunk 包含 redaction / erasure verification stub，或通过 `verification_hints` 提交该 stub 的 digest。
- backfill 从 snapshot frontier 恢复时，默认视图仍显示 redacted / erased 占位，不显示原文，也不把 timeline 当作缺失事件。
- audit view 能验证 target event id、原始 envelope digest / proof `payload_hash`、redaction event id、执行服务 DID、执行时间和签名 receipt。
- 若 active legal hold 存在，pruning MUST fail closed；snapshot 仍可隐藏普通视图明文，但不得物理删除 legal-hold 边界内要求保留的 payload。

## 4. Capability Vectors

> 来源：原 `conformance-vectors.md`（已合并）

### 4.1 目标

本文件将 capability 的链式授权、撤销回滚与审批约束固定为跨实现向量。  
适配对象：`identity-registry`, `principal_server_events_api`, `e2ee_client`, `enterprise_client`, `agent_runtime`.

向量命名：

```text
cx.vector.capability.<scenario>.v1
```

每个向量应检查：

- selector scope 是否正确绑定到 actor/device/space/action。
- 授权时间窗约束是否导致一致结果。
- 关键路径必须拒绝 `authorization-only` 假阳性。

### 4.2 Vector: 多级委托链

向量名称：

```text
cx.vector.capability.delegate_chain.v1
```

输入事件链：

```json
{
  "base": {
    "kind": "cx.capability.grant",
    "subject": "did:web:root-admin.example.com",
    "actions": [
      "cx.space.admin"
    ],
    "constraints": []
  },
  "delegations": [
    {
      "event_id": "cx:event:01js0d1g000000000000000000",
      "kind": "cx.capability.delegate",
      "space_id": "cx:space:01js0ms0000000000000000000",
      "actor_id": "did:web:root-admin.example.com",
      "payload": {
        "source_capability": "space-admin",
        "subject": "did:web:ops.example.com",
        "scope": "space:01js0ms000000000000000000",
        "actions": [
          "cx.capability.*",
          "cx.invite.create"
        ],
        "constraints": [
          {
            "constraint_type": "temporal",
            "effect": "allow",
            "not_before": "2026-04-20T00:00:00Z",
            "expires_at": "2026-05-20T00:00:00Z"
          },
          {
            "constraint_type": "quota",
            "subtype": "rate",
            "effect": "allow",
            "rate_limit": "5/hour"
          }
        ]
      },
      "auth_refs": [
        "cx:event:01js0r00tgrant000000000000"
      ]
    },
    {
      "event_id": "cx:event:01js0d1h000000000000000000",
      "kind": "cx.capability.delegate",
      "space_id": "cx:space:01js0ms0000000000000000000",
      "actor_id": "did:web:ops.example.com",
      "payload": {
        "source_capability": "space-admin-delegate-a",
        "subject": "did:web:intern.example.com",
        "scope": "space:01js0ms000000000000000000",
        "actions": [
          "cx.invite.create"
        ],
        "constraints": [
          {
            "constraint_type": "quota",
            "subtype": "rate",
            "effect": "allow",
            "rate_limit": "2/day"
          },
          {
            "constraint_type": "scope_limitation",
            "effect": "allow",
            "allowed_audiences": [
              "did:web:partner.example",
              "did:web:vendor.example"
            ]
          }
        ]
      },
      "auth_refs": [
        "cx:event:01js0d1g000000000000000000"
      ]
    }
  ],
  "action_query": {
    "actor_id": "did:web:intern.example.com",
    "action": "cx.invite.create",
    "resource": "cx:space:01js0ms0000000000000000000",
    "request_time": "2026-04-26T01:00:00Z",
    "request_audience": "did:web:vendor.example"
  }
}
```

期望输出：

```json
{
  "authorized": true,
  "valid_chain": [
    "cx:event:01js0r00tgrant000000000000",
    "cx:event:01js0d1g000000000000000000",
    "cx:event:01js0d1h000000000000000000"
  ],
  "constraints_checked": {
    "time": true,
    "scope": true,
    "rate_limit": true,
    "audience": true
  }
}
```

失败判定：

- 忽略中间 delegate 层直接用 root 进行授权。
- 忽略 `audiences` 约束。
- 时间边界过期仍返回 true。

### 4.3 Vector: revoke 回滚

向量名称：

```text
cx.vector.capability.revoke_rollback.v1
```

输入：

```json
{
  "events": [
    {
      "event_id": "cx:event:01js0g2a000000000000000000",
      "kind": "cx.capability.grant",
      "payload": {
        "grant_id": "cx:grant:01js0g2a000000000000000000",
        "subject": "did:web:alice.example.com",
        "actions": [
          "cx.message.create"
        ]
      },
      "created_at": "2026-04-26T00:00:00Z"
    },
    {
      "event_id": "cx:event:01js0r2a000000000000000000",
      "kind": "cx.capability.revoke",
      "payload": {
        "grant_id": "cx:grant:01js0g2a000000000000000000"
      },
      "created_at": "2026-04-26T00:00:01Z"
    },
    {
      "event_id": "cx:event:01js0x2a000000000000000000",
      "kind": "cx.member.state",
      "payload": {
        "actor_id": "did:web:alice.example.com",
        "membership": "leave"
      },
      "created_at": "2026-04-26T00:00:02Z"
    },
    {
      "event_id": "cx:event:01js0msg2a0000000000000000",
      "kind": "cx.message.create",
      "actor_id": "did:web:alice.example.com",
      "created_at": "2026-04-26T00:00:03Z",
      "payload": {
        "flow_id": "cx:flow:01js0rvk000000000000000000",
        "content": {
          "type": "cx.content.text",
          "body": "should_fail_if_revoke_applies"
        }
      },
      "prev_refs": [
        "cx:event:01js0x2a000000000000000000"
      ]
    }
  ],
  "rollback": {
    "target_event_id": "cx.event:01js0r2a000000000000000000",
    "reason": "revoke_undo_invalid_signature"
  }
}
```

期望输出：

- 初始解析：`cx:event:01js0msg2a0000000000000000` 因 revoke 生效应拒绝或标记 soft-fail/rejected（取决于实现策略）。
- 回滚 revoke 后重算：同一事件在回滚前瞻分析中应变为 authorized。
- 回滚必须产生独立可审计结果，不可直接修改历史事件链的 event_id。

验证：

- `accepted` 集合必须对应当前 reducer frontier。
- 回滚后状态必须可复现，并有 `rollback_ref` 或等价证据。

### 4.4 Vector: 审批约束缺失

向量名称：

```text
cx.vector.capability.approval_constraint.v1
```

输入：

```json
{
  "event": {
    "event_id": "cx:event:01js0mha000000000000000000",
    "kind": "cx.policy.action",
    "actor_id": "did:web:contractor.example",
    "space_id": "cx:space:01js0ms0000000000000000000",
    "hlc": "01970e589d26-0001-aaaaaaaa",
    "payload": {
      "action": "cx.space.admin",
      "approval_required": true,
      "approval_quorum": 2,
      "scope": "space:01js0ms000000000000000000"
    },
    "auth_refs": [
      "cx:event:01js0spaceadm1n00000000000"
    ]
  },
  "capabilities": [
    {
      "kind": "cx.capability.grant",
      "subject": "did:web:contractor.example",
      "actions": [
        "cx.space.admin"
      ]
    },
    {
      "kind": "cx.capability.grant",
      "subject": "did:web:approver-1.example.com",
      "actions": [
        "cx.approval.vote"
      ]
    }
  ]
}
```

期望输出：

```json
{
  "authorized": false,
  "failure_code": "approval_required",
  "next_state": "proposal",
  "visible_to": ["initiator", "approvers"]
}
```

判定要求：

- 即便有高权限 grant，若 approval constraint 未满足，不得直接通过写入执行。
- 必须有可复现的 proposal / review 生命周期。
- 通过审核后应产生可验证的审批完成事件，再以独立 action event 执行。

## 5. Sync Vectors

> 来源：原 `conformance-vectors.md`（已合并）

### 5.1 目标

本文定义 Client Sync、timeline ordering、pagination、snapshot、backfill 与 E2EE / MLS 同步的跨实现测试向量。当前向量覆盖标准对象 / Morph 模型。

实现声称支持以下 profile 时 SHOULD 运行本文对应向量：

- `cx.profile.minimal_client.v1`
- `cx.profile.chat_mvp.v1`
- `cx.profile.kanban_mvp.v1`
- `cx.profile.full_client.v1`
- `cx.profile.e2ee_client.v1`
- `cx.profile.principal_server_events_api.v1`
- `cx.profile.principal_server.v1`

### 5.2 通用约定

测试向量使用以下简化字段：

```json
{
  "event_id": "cx:event:01js0ev0000000000000000000",
  "actor_id": "did:web:actor-a.example.com",
  "actor_seq": 1,
  "hlc": "019b76daa800-0000-a0000000",
  "prev_refs": [],
  "auth_refs": [],
  "kind": "cx.flow.update",
  "target_ref": "cx:flow:01js0ca0000000000000000000",
  "content_hash": "sha256:..."
}
```

实现 MAY 使用真实 canonical JSON、CID、签名和 hash 替换示例值，但 MUST 保持以下语义：

- `event_id` 是内容寻址或签名绑定后的稳定 ID。
- `actor_seq` 在同一 actor 的单条因果路径上严格递增；并发 sibling fork 可出现相同高度。
- `hlc` 是 Hybrid Logical Clock，不能单独决定因果顺序。
- `target_ref` MUST 指向标准对象、Morph、Relation、View 或 Space。对于 `*.create` 向量，`target_ref` 只是测试向量的阅读辅助；规范性 Event payload 仍使用 `payload.object.id`。

### 5.3 Vector: Board Collection Projection

输入：

```json
{
  "space_id": "cx:space:01js0sp0000000000000000000",
  "events": [
    {
      "kind": "cx.space.create",
      "target_ref": "cx:space:01js0bd0000000000000000000",
      "payload": {
        "object": {
          "id": "cx:space:01js0bd0000000000000000000",
          "schema": "cx.schema.space.v1",
          "kind": "board",
          "title": "Release Board",
          "created_by_principal": "did:web:alice.example.com",
          "schema_refs": ["cx.schema.space.v1"],
          "default_discoverability": "restricted",
          "default_join_rule": "restricted",
          "history_visibility": "joined",
          "encryption_profile": "none",
          "created_at": "2026-04-26T00:00:00Z"
        }
      }
    },
    {
      "kind": "cx.space.create",
      "target_ref": "cx:space:01js0111000000000000000000",
      "payload": {
        "object": {
          "id": "cx:space:01js0111000000000000000000",
          "schema": "cx.schema.space.v1",
          "kind": "list",
          "title": "Todo",
          "rank": "U",
          "created_by_principal": "did:web:alice.example.com",
          "schema_refs": ["cx.schema.space.v1"],
          "default_discoverability": "restricted",
          "default_join_rule": "restricted",
          "history_visibility": "joined",
          "encryption_profile": "none",
          "created_at": "2026-04-26T00:00:00Z"
        }
      }
    },
    {
      "kind": "cx.flow.create",
      "target_ref": "cx:flow:01js0ca1000000000000000000",
      "payload": {
        "object": {
          "id": "cx:flow:01js0ca1000000000000000000",
          "schema": "cx.schema.flow.v1",
          "space_id": "cx:space:01js0sp0000000000000000000",
          "title": "Release checklist",
          "branches": [
            {
              "name": "synthesis",
              "is_primary": true
            }
          ],
          "created_by": "did:web:alice.example.com",
          "created_at": "2026-04-26T00:00:00Z"
        },
        "initial_relations": [
          {
            "relation_kind": "contains",
            "from_ref": "cx:space:01js0111000000000000000000",
            "to_ref": "cx:flow:01js0ca1000000000000000000",
            "fields": {
              "board_id": "cx:space:01js0bd0000000000000000000",
              "rank": "U"
            }
          }
        ]
      }
    }
  ]
}
```

期望：

- Collection projection MUST 返回 `object.id = cx:flow:01js0ca1000000000000000000`。
- 返回项 MUST 位于 `cx:space:01js0111000000000000000000`。
- View cursor MUST 绑定 projection、view、frontier 与权限上下文。

### 5.4 Vector: Flow Card Move Read-Your-Writes

输入：

```json
{
  "write": {
    "kind": "cx.flow.move",
    "target_ref": "cx:flow:01js0ca1000000000000000000",
    "payload": {
      "board_id": "cx:space:01js0bd0000000000000000000",
      "flow_id": "cx:flow:01js0ca1000000000000000000",
      "from_list_id": "cx:space:01js0111000000000000000000",
      "to_list_id": "cx:space:01js0112000000000000000000",
      "rank": "U"
    }
  },
  "query": {
    "object_types": [
      "flow"
    ],
    "consistency": {
      "wait_for": "sync_token_from_write"
    }
  }
}
```

期望：

- Projection executor 在返回前 MUST 等待本地 frontier 覆盖写入 token，或返回可恢复超时。
- 查询结果中该 Flow item 的 `list_id` MUST 为 `cx:space:01js0112000000000000000000`。

### 5.5 Vector: Flow Discussion Branch Visibility

输入：

```json
{
  "flow_id": "cx:flow:01js0ca1000000000000000000",
  "viewer": "did:web:viewer.example.com",
  "viewer_can_read_flow": true,
  "viewer_is_branch_member": false
}
```

期望：

- Flow projection MAY show a lazy discussion-branch reference.
- Flow discussion timeline MUST NOT be expanded.
- Notification/search results MUST NOT reveal hidden discussion messages.

#### 5.5.1 Vector: Flow Discussion Surface Visibility

输入：

```json
{
  "flow_id": "cx:flow:01js0sb1000000000000000000",
  "branch": "discussion",
  "viewer_grants": ["cx.flow.read"],
  "viewer_branch_membership": "none"
}
```

期望：

- Flow projection MAY show a lazy/locked discussion surface reference if discussion discoverability permits.
- Flow activity MUST NOT include hidden discussion messages.
- Flow context MUST NOT leak hidden discussion message bodies through previews, summaries, notifications, search snippets, embeddings, or decision summaries.

### 5.6 Vector: Flow Discussion Timeline

输入：

```json
{
  "flow_id": "cx:flow:01js0r01000000000000000000",
  "events": [
    {
      "kind": "cx.message.create",
      "target_ref": "cx:message:01js0me1000000000000000000",
      "payload": {
        "flow_id": "cx:flow:01js0r01000000000000000000",
        "content": {
          "type": "cx.content.text",
          "body": "discussion message"
        }
      }
    }
  ]
}
```

期望：

- `flow-discussion-timeline` MUST return the message when viewer can read the Flow discussion branch.
- `flow-discussions` MUST only include this message if viewer can read the Flow discussion branch; Flow synthesis visibility alone is not sufficient when branch-scoped override applies.
