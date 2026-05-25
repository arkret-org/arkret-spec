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
所有 `cx.vector.*` 标识符的机器索引位于 [`vector-registry.json`](../../artifacts/registry/vector-registry.json)；新增、删除或重命名向量时 MUST 同步更新该 registry，并通过 `tools/artifact_pipeline.py check` 的闭包校验。

## 1. Encoding & Crypto Vectors

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
  "event_id": "cx:event:019640ed-8000-7000-8000-000000000000",
  "kind": "cx.message.create",
  "realm_id": "cx:realm:01964137-0000-7000-8000-000000000000",
  "actor_id": "did:web:alice.example",
  "actor_seq": 1,
  "created_at": "2026-04-26T00:00:00Z",
  "hlc": "01970e589d21-0004-a13f9c2e",
  "prev_refs": [],
  "refs": [],
  "preconditions": [],
  "effects": [
    {
      "cell": "cx:cell:message:019640ed-8000-7000-8000-000000000000",
      "op": {
        "kind": "append",
        "value": {
          "flow_id": "cx:flow:01964137-0000-7000-8000-000000000000",
          "message_id": "cx:message:019640ed-8000-7000-8000-000000000000",
          "track": "discussion"
        }
      }
    }
  ],
  "anchor_ref": "cx:anchor:sha256:2222222222222222222222222222222222222222222222222222222222222222",
  "payload": {
    "flow_id": "cx:flow:01964137-0000-7000-8000-000000000000",
    "track": "discussion",
    "message_id": "cx:message:019640ed-8000-7000-8000-000000000000",
    "content": {
      "kind": "cx.content.text",
      "body": "hello"
    }
  }
}
```

期望 canonical bytes 的 UTF-8 文本表示：

```json
{"actor_id":"did:web:alice.example","actor_seq":1,"anchor_ref":"cx:anchor:sha256:2222222222222222222222222222222222222222222222222222222222222222","created_at":"2026-04-26T00:00:00Z","effects":[{"cell":"cx:cell:message:019640ed-8000-7000-8000-000000000000","op":{"kind":"append","value":{"flow_id":"cx:flow:01964137-0000-7000-8000-000000000000","message_id":"cx:message:019640ed-8000-7000-8000-000000000000","track":"discussion"}}}],"event_id":"cx:event:019640ed-8000-7000-8000-000000000000","hlc":"01970e589d21-0004-a13f9c2e","kind":"cx.message.create","payload":{"content":{"body":"hello","kind":"cx.content.text"},"flow_id":"cx:flow:01964137-0000-7000-8000-000000000000","message_id":"cx:message:019640ed-8000-7000-8000-000000000000","track":"discussion"},"preconditions":[],"prev_refs":[],"realm_id":"cx:realm:01964137-0000-7000-8000-000000000000","refs":[]}
```

期望 digest：

```text
sha256:90b6a9bdacba4a32b49a560b1fca484a15e858b298f21755110517d3d96b349c
```

判定规则：

- event digest / proof `event_digest` MUST 从 redaction 前、去除 `proofs` 与 `unsigned` 后的 canonical event bytes 派生；`event_id` 是稳定 `cx:event:*` typed ID，必须进入 digest，但不替代 digest。
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
  "receipt_id": "cx:receipt:01964186-0000-7000-8000-000000000000",
  "issuer": "did:web:alice.example",
  "receipt_scope": {
    "actor_id": "did:web:alice.example"
  },
  "frontier": {
    "actor_seq": 1,
    "event_digest": "sha256:1111111111111111111111111111111111111111111111111111111111111111"
  },
  "events": [
    "sha256:1111111111111111111111111111111111111111111111111111111111111111"
  ],
  "created_at": "2026-04-26T00:00:00Z"
}
```

期望 canonical bytes 的 UTF-8 文本表示：

```json
{"created_at":"2026-04-26T00:00:00Z","events":["sha256:1111111111111111111111111111111111111111111111111111111111111111"],"frontier":{"actor_seq":1,"event_digest":"sha256:1111111111111111111111111111111111111111111111111111111111111111"},"issuer":"did:web:alice.example","receipt_id":"cx:receipt:01964186-0000-7000-8000-000000000000","receipt_scope":{"actor_id":"did:web:alice.example"},"schema":"cx.schema.event_batch_receipt.v1"}
```

期望 digest：

```text
sha256:a828dc768e814ca0be50b5014e1115612776fa342f66df849e8bdd7e72dfa9b4
```

失败条件：

- `events` 数组被排序或去重后再 hash。
- proof 字段被包含进 receipt digest。
- `issuer`、`receipt_scope`、`frontier` 或 `schema` 被排除在 digest 外。
- `receipt_id` 大小写被实现私自改写。

### 1.8 Vector: Signature Binding Payload

向量名称：

```text
cx.vector.encoding.signature_binding_payload.v1
```

签名前的 binding object：

```json
{
  "event_digest": "sha256:43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777",
  "actor_id": "did:web:alice.example",
  "verification_method": "did:web:alice.example#device-1",
  "created_at": "2026-04-26T00:00:00Z"
}
```

期望 canonical bytes 的 UTF-8 文本表示：

```json
{"actor_id":"did:web:alice.example","created_at":"2026-04-26T00:00:00Z","event_digest":"sha256:43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777","verification_method":"did:web:alice.example#device-1"}
```

期望 digest：

```text
sha256:98d7da309a94b0d188404e649a81fa240e338d62a7848c0ce699c3bbf85f3c6c
```

判定规则：

- proof MUST bind event digest、actor DID、verification method 和 created_at。
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
- 重试或等待期间，事件的 `prev_refs`、`refs[role=authorized_by]` 与 `actor_seq` 约束不得被放松。

失败条件：

- 逻辑计数器回绕到更小值并继续发出事件。
- 通过伪造更大的 wall clock skew 逃避 overflow，同时破坏本地 HLC 单调性或 causal 约束。
- 消费者把上述回绕值当作正常排序输入接受并推进 accepted history。

### 1.11 Vector: Cursor Opaqueness

向量名称：

```text
cx.vector.encoding.cursor_opaque.v1
```

输入 cursor（schema-valid v1 wire 形态；示例 `_mac` 是测试占位，真实服务仍必须按 `encoding.md` §8.3.1 验证 MAC / 签名或 stateful handle）：

```text
cx:cursor:eyJfbWFjIjoiaG1hYy1zaGEyNTY6MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMCIsImlzc3Vlcl9raWQiOiJkaWQ6d2ViOnN5bmMuZXhhbXBsZSNjdXJzb3ItMjAyNi0wNSIsInB1cnBvc2UiOiJzdHJlYW0iLCJzIjp7ImN4OnJlYWxtOjAxOTY0MTliLTAwMDAtNzAwMC04MDAwLTAwMDAwMDAwMDAwMCI6eyJoIjoic2hhMjU2OmFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWEiLCJvIjoiMDE5NzBlNTg5ZDIxLTAwMDAtYTEzZjljMmUiLCJwIjpbImN4OmV2ZW50OjAxOTY0MGVkLTgwMDAtNzAwMC04MDAwLTAwMDAwMDAwMDAwMCJdfX0sInQiOiIyMDk5LTEyLTMwVDIzOjU5OjU5WiIsInYiOiIxIiwieCI6NDEwMjQ0NDc5OTAwMH0
```

cursor base64url 解码后对应 canonical JSON：

```text
{"_mac":"hmac-sha256:0000000000000000000000000000000000000000000000000000000000000000","issuer_kid":"did:web:sync.example#cursor-2026-05","purpose":"stream","s":{"cx:realm:0196419b-0000-7000-8000-000000000000":{"h":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","o":"01970e589d21-0000-a13f9c2e","p":["cx:event:019640ed-8000-7000-8000-000000000000"]}},"t":"2099-12-30T23:59:59Z","v":"1","x":4102444799000}
```

期望客户端行为：

- 客户端 MUST 把 cursor 当作不透明字符串保存和回传。即使 cursor 的内部结构是 `encoding.md` §8.2 规定的合法 stateful 或 stateless 形态，客户端 SDK / 应用层 MUST NOT 解析它的内部字段来构造请求。
- 客户端 MUST NOT 依赖 base64url 解码后的 `s.<realm_id>.p/o/h` frontier、`x` 过期字段或 `_mac` 构造下一页请求；这些字段的存在只是为了让服务端可以无状态地恢复同步进度。
- 服务端 MAY 改变 cursor 内部编码或字段集合，只要同一 query/session 下 cursor 仍按 API contract 可用。
- 服务端 MUST 在收到该 cursor 时，按 §8.3 校验 `v ∈ supported_versions`、`purpose`、`x`、schema 形态和所有 frontier event 引用；语法失败返回顶层 `invalid_param`（reason `invalid_cursor`），过期返回 `cursor_expired`，完整性失败返回 `cursor_integrity_invalid`（见 `error-code-registry.json`）。

失败条件：

- 客户端解析 `s` / `x` 后自行构造下一页请求或修改 cursor 内容。
- 客户端在 cursor 解码失败时拒绝整个协议，而不是按 opaque token 处理。
- 服务端使用违反 `{v,purpose,t,x,h}` 或 `{v,purpose,t,s,d?,target?,x,_mac/_sig}` 结构的 cursor 内部 payload（例如旧草稿中出现过的 `{query_digest, last_event_id}` 或 `{v,p}` 形式）。

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
- canonical Event payload、`event_digest`、proof binding object、detached JWS signing input 和 expected rejection 条件

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

### 2.3 Vector: `cas_register` 并发冲突返回 Bottom

向量名称：

```text
cx.vector.move_anchor_lattice.cas_bottom.v1
```

输入：

- 两个 anchored Move 并发写同一 `cas_register + bottom=reject` policy cell。

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

### 2.5.1 Vector: MLS Governance Epoch Binding

`vector_id`: `cx.vector.mls.governance_epoch_binding.v1`

Steps：

1. 构造 `cx.mls.commit`，`payload.base_epoch = 41`、`payload.next_epoch = 42`。
2. `payload.governance_binding.previous_epoch = 40` 或 `payload.governance_binding.next_epoch = 43`。
3. 其它 signature、proposal refs、policy root 和 membership frontier 均有效。

Expected：

- Receiver / reducer MUST reject 该 commit，且不得推进 `mls_epoch_cell` 或 `covered_frontier_cell`。
- `governance_binding.previous_epoch` / `next_epoch` MUST 与 payload 顶层 epoch 字段一致；不得只相信其中一侧。

### 2.5.2 Vector: MLS Welcome KeyPackage Hash Binding

`vector_id`: `cx.vector.mls.welcome_keypackage_hash.v1`

Steps：

1. KeyPackage claim response 返回 `keypackage_ref=K`、`keypackage_digest=H1`、`capabilities_digest=C`、`ssk_generation=G`。
2. 攻击者提交 `cx.mls.welcome`，顶层 `keypackage_ref=K`，但 `payload.keypackage_digest=H2` 或 `payload.claim_ref.keypackage_digest=H2`。
3. Welcome ciphertext、claim_id、capabilities_digest 和 signature envelope 其它字段均有效。

Expected：

- Receiver MUST reject before decrypting or accepting the Welcome。
- `payload.keypackage_digest`、`payload.claim_ref.keypackage_digest`、claim record `keypackage_digest` 和已发布 `cx.mls.keypackage.payload.keypackage_digest` MUST 全部一致。

### 2.6 Vector: Anchorer Cell ⊥ → Recovery Anchorer 上位

向量名称：

```text
cx.vector.move_anchor_lattice.anchorer_cell_bottom_recovery.v1
```

输入：

- Realm 以 `anchor_profile=mixed` 起始；`primary=did:web:host-a.example`，`recovery_members=[did:web:recovery-1.example, did:web:recovery-2.example]`。
- 两条并发 Move 在 anchorer cell（cas_register, bottom=reject）上提交不同 value。

期望：

- anchorer cell join → ⊥；Realm 状态 `anchorer_paused`。
- 普通 Anchor 推进 MUST 阻塞。
- 仅 `recovery_members` 中 DID 签发的 recovery Anchor 才能重置 anchorer cell。
- 恢复后 Realm 状态回到 `effective`。

### 2.7 Vector: Signed Compaction Anchor 等价 Effective View

向量名称：

```text
cx.vector.move_anchor_lattice.signed_compaction_equivalent.v1
```

输入：

- 两个并存 Anchor leaves L1、L2（同 Realm）。
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

### 2.8.1 Vector: Anchor canonical bytes 去自引用（normative）

向量名称：

```text
cx.vector.move_anchor_lattice.anchor_canonical_no_self_reference.v1
```

输入与期望（多 case 矩阵）：

1. **Base case**：构造 Anchor body fields `{realm_id, predecessor_refs, frontier, state_root, anchored_at, hlc}`；按 [`encoding.md`](../conformance/encoding.md) §2 编码为 `anchor_canonical_bytes`；`id = "cx:anchor:sha256:" || hex(H(anchor_canonical_bytes))`；`anchorer_sig.payload_digest == H(anchor_canonical_bytes)`。Verifier MUST accept。
2. **id-in-canonical-bytes attack**：若 producer 把 `id` 字段也塞进 `anchor_canonical_bytes` 重新计算 H，得到的 hash 与原始 `id` 内容不同；verifier 重算后 `digest_mismatch`，MUST reject。该向量证明实现没有把 `id` 当成 transcript field。
3. **sig-in-canonical-bytes attack**：若 producer 把 `anchorer_sig` 也进入 canonical bytes，`payload_digest` 重算与 `id` 重算都会失败；verifier MUST reject。证明 signature 不签自己。
4. **key reorder attack**：取 valid Anchor，把 canonical JSON key 顺序打乱（例如 `frontier` 放在 `realm_id` 之前）；canonical JSON 规则（key 字典序）下重新编码 → 与原 bytes 相同 → hash 一致 → accept。若 verifier 未按 canonical 规则重新编码就直接 hash wire bytes，attack 会让 `digest_mismatch` 假阴性。本 case 检查 verifier 走 canonical re-encode，不是按收到的 bytes 直接 hash。
5. **proof injection attack**：取 valid Anchor，注入未定义字段 `extra_proof`。`additionalProperties=false` 的 schema 在 (b) 校验阶段就 reject；若实现错误地 allow 之，hash 会变 → `digest_mismatch`。
6. **frontier typed-id attack**：构造 `frontier=["cx:event:<uuid>"]`；schema `frontier[]` items 必须匹配 `event_digest` (`<algo>:<hex>`)，typed id 形态 MUST `schema_violation` 立即被拒（早于 hash 校验）。

期望：

- case 1 accept；case 2/3/4/5/6 reject。
- 接收方 verifier 在 reject 时 MUST 返回 `digest_mismatch`（case 2/3/4）、`invalid_signature`（case 3 的签名路径）或 `schema_violation`（case 5/6），不得回退到"prose 形态化"判断。

### 2.9 Vector: state_root 增量重算等价于全量重算

向量名称：

```text
cx.vector.state_root.incremental.v1
```

输入：

- 一个已被接受的 Anchor `A0`，其 frontier 写入 N 个 cell（`cell_1 … cell_N`，N ≥ 8）；实现已按 §4.2.1 缓存 `cell → leaf_digest` 表。
- 一个新的 Anchor `A1`（`predecessor_refs=[A0]`），frontier 仅修改其中 K 个 cell（K ≤ N，包含 K=1 / K=N/2 / K=N 三种 case）。
- 一个 corner-case Anchor `A2`：frontier 是空 set（无新 effect）。
- 一个 schema-evolution case `A3`：frontier 包含一个新 cell（之前从未有过 effect），并删除一个旧 cell 的 effect（通过 lattice 的 ⊥/tombstone 机制）。

期望：

每个 case MUST 同时计算：

- `state_root_incremental`：仅对受影响 cell 重算 leaf_digest 与 Merkle 分支，复用 `A0` 缓存。
- `state_root_full`：丢弃缓存，按 §4.2.2 从 frontier 全量重算所有 cell 的 leaf_digest 与 Merkle root。

判定要求：

- `state_root_incremental == state_root_full` 在所有四个 case 上 MUST 成立，bit-exact。
- 缓存的 `leaf_digest` 表 MUST 在 `apply_anchor` 接受 Anchor 后更新；保留旧 leaf_digest 导致 next-anchor 增量重算偏离全量结果即视为实现 bug。
- A2（空 frontier）情况下 `state_root_incremental` MUST 直接复用 `A0.state_root`；不得因为"没有 cell 可重算"而错误地返回空 Merkle root（`H("")`）或 null。
- A3（新增 cell + 删除旧 cell effect）case 验证两点：(a) 新 cell 的 leaf_digest 进入 sorted leaf 列表（按 `cell_wire` Unicode 升序）；(b) 删除 effect 的 cell 仍以其 `Bottom` 或 tombstone 后的 lattice value 编码 leaf_digest，不被简单从 leaf 列表移除。

失败条件：

- 增量分支只重算到内部 Merkle 节点而不向上传播至 root → root 与 full 不匹配。
- 偶数/奇数边界处理在 incremental 与 full 之间不一致（例如 incremental 路径错误复制最后 leaf 而 full 路径正确"提升"）。
- 受影响 cell 集合按 receive order 而非 `cell_wire` lex order 排序。
- A2 case 下错把 `state_root` 重置为空摘要。

实现 MUST 在 conformance 报告中分别报告四个 case 的 `state_root_incremental` 与 `state_root_full`，并标记 pass / fail。该 vector 验证 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §4.2.3 中"增量与全量必须等价"的要求。

### 2.10 Vector: `cx.flow.tracks.update` 原子 patch

向量名称：

```text
cx.vector.flow_tracks_update.atomic.v1
```

输入：

- 一个已存在 Flow `F0`，`tracks = { "synthesis": { is_primary: true, enabled: true }, "discussion": { is_primary: false, enabled: true } }`。
- Case A — 单字段 patch：一个 `cx.flow.tracks.update` Event，`payload.patch = { "tracks.synthesis.is_primary": { "$op": "set", "value": false }, "tracks.discussion.is_primary": { "$op": "set", "value": true } }`。期望 Flow `tracks` 在单个 Anchor batch 内原子地把 primary 从 `synthesis` 切到 `discussion`，中间态 MUST NOT 出现"两个 is_primary=true"或"零个 is_primary=true"。
- Case B — 新增 + 启停 + 移除：在 Flow 已含 `tracks.synthesis` / `tracks.discussion` 的基础上，单条 `cx.flow.tracks.update` 同时 (1) 新增 `tracks.review.enabled=true` 子 map (profile 注册的扩展 track)，(2) 把 `tracks.discussion.enabled` 置为 false，(3) 把 `tracks.synthesis.is_primary` 置为 false，(4) 把 `tracks.review.is_primary` 置为 true。
- Case C — invariant 违反：单条 `cx.flow.tracks.update` 把 `tracks.synthesis.is_primary` 与 `tracks.discussion.is_primary` 同时 set 为 `true`。

期望：

- **Case A**: reducer 应用 patch 后，`Flow.tracks.synthesis.is_primary == false` 且 `Flow.tracks.discussion.is_primary == true`；reducer 视角下不存在两次中间 state cell write，cas_register cell 一次 atomic update。
- **Case B**: reducer 接受合并后状态 `{ synthesis: {is_primary: false, enabled: true}, discussion: {is_primary: false, enabled: false}, review: {is_primary: true, enabled: true} }`；中间过程 MUST 在同一 cell update 内完成，不得分裂为 4 个独立 cell write。
- **Case C**: reducer MUST 在 effect 应用前 (cell update 之前) 校验合并后 `tracks` map 至多 1 个 entry `is_primary=true`；不满足 MUST `schema_violation`，整条 Event 拒绝，Flow `tracks` 不发生任何变化。

判定要求：

- patch path 解析 MUST 遵循 [`event-and-patch.md` §4.2`](../models/event-and-patch.md) ABNF grammar；任何 path 形如 `tracks.<name>[key=...]` 的 selector segment MUST `schema_violation`（`tracks` 是 map，不是 unique-key 数组）。
- `cx.flow.tracks.update` 写入的 cell 是 `cx:cell:cx.component.flow.tracks.v1:<flow_id>`（cas_register），reducer 校验合并后 invariant 在 cell update 之前 完成。

失败条件：

- Case A 在 cell update 中间态触发 invariant 校验，把"先把 synthesis 设 false → 此时 0 个 primary"错判为 violation。
- Case B 把 patch 拆分为多个独立 cell write，破坏 atomic 语义（外部读取在中间能看到不一致的 tracks map）。
- Case C 把违反 invariant 的 Event 部分接受（例如设了 enabled 但拒绝 is_primary），破坏 Event-level all-or-nothing 语义。

实现 MUST 在 conformance 报告中分别报告三个 case 的 reducer 输出 cell value 与 invariant violation reason；该 vector 防御 §4.5 step 5 primary 解析规则的边界 case。

## 3. Redaction Vectors

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
    "event_id": "cx:event:0196414c-3000-7000-8000-000000000000",
    "kind": "cx.message.create",
    "realm_id": "cx:realm:0196414c-8000-7000-8000-000000000000",
    "actor_id": "did:web:alice.example.com",
    "created_at": "2026-04-26T00:00:00Z",
    "hlc": "01970e589d24-0001-aaaaaaaa",
    "prev_refs": [],
    "refs": [],
    "payload": {
      "flow_id": "cx:flow:0196414c-3400-7000-8000-000000000000",
      "content": {
        "kind": "cx.content.text",
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
    "event_id": "cx:event:0196418a-0360-7000-8000-000000000000",
    "kind": "cx.redaction",
    "realm_id": "cx:realm:0196414c-8000-7000-8000-000000000000",
    "actor_id": "did:web:alice.example.com",
    "created_at": "2026-04-26T00:00:02Z",
    "hlc": "01970e589d24-0002-bbbbbbbb",
    "prev_refs": [
      "cx:event:0196414c-3000-7000-8000-000000000000"
    ],
    "refs": [
      { "id": "cx:event:019640c5-5800-7000-8000-000000000000", "role": "authorized_by", "critical": true }
    ],
    "payload": {
      "redacts": "cx:event:0196414c-3000-7000-8000-000000000000",
      "reason_code": "policy_recall"
    }
  }
}
```

期望结果：

```json
{
  "event_id": "cx:event:0196414c-3000-7000-8000-000000000000",
  "state": "redacted",
  "kept_envelope_fields": [
    "event_id",
    "kind",
    "realm_id",
    "actor_id",
    "created_at",
    "hlc",
    "prev_refs",
    "refs",
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

### 3.2.1 Vector: Space target redaction payload schema

向量名称：

```text
cx.vector.redaction.space_target_ref_schema.v1
```

输入（payload 片段，必须通过 `event-payload.schema.json#/$defs/object_lifecycle_payload`）：

```json schema=schemas/event-payload.schema.json#/$defs/object_lifecycle_payload
{
  "target_ref": "cx:space:019640b6-8000-7000-8000-000000000000",
  "reason": "privacy_cleanup"
}
```

期望结果：

- Payload schema MUST 接受 `cx:space:*` 作为 `cx.redaction` 的 `target_ref` / `object_ref`。
- Reducer 语义仍按 Space 生命周期规则执行：Space 没有独立 `redacted` state，内容清理合并到 Space metadata cleanup / terminal transition；不得因 schema 漏洞把 Space cleanup 路径降级为实现私有扩展。

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
      "event_id": "cx:event:0196417d-8400-7000-8000-000000000000",
      "kind": "cx.message.create",
      "realm_id": "cx:realm:0196414c-8000-7000-8000-000000000000",
      "created_at": "2026-04-26T00:00:00Z",
      "hlc": "01970e589d25-0001-11111111",
      "payload": {
        "flow_id": "cx:flow:0196417d-8400-7000-8000-000000000000",
        "content": {
          "kind": "cx.content.text",
          "body": "bad link: spam.example/phish"
        }
      }
    },
    {
      "event_id": "cx:event:0196417d-8980-7000-8000-000000000000",
      "kind": "cx.policy.action",
      "realm_id": "cx:realm:0196414c-8000-7000-8000-000000000000",
      "created_at": "2026-04-26T00:00:01Z",
      "hlc": "01970e589d25-0001-22222222",
      "actor_id": "did:web:policy-bot.example.com",
      "payload": {
        "target_id": "cx:event:0196417d-8400-7000-8000-000000000000",
        "policy_scope": "public",
        "decision": "quarantine"
      }
    },
    {
      "event_id": "cx:event:0196417d-8f00-7000-8000-000000000000",
      "kind": "cx.redaction",
      "realm_id": "cx:realm:0196414c-8000-7000-8000-000000000000",
      "actor_id": "did:web:policy-admin.example",
      "payload": {
        "redacts": "cx:event:0196417d-8400-7000-8000-000000000000",
        "reason_code": "policy_recall"
      }
    }
  ]
}
```

期望：

- Projection 不得展示已 redacted 的 `content`，但应保留 stripped 证据用于审计。
- 历史可见性为 `world_readable` 时，外部审计仍应看到 redaction 事实而不是原文。
- 冻结空间（frozen realm）与历史归档（archived event）场景下，timeline 位置必须保留，不能物理删除。
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
- 实现保留 verification stub：原始 event id、验证事件图所需的 Event envelope digest / proof `event_digest`、redaction event id、erasure reason、执行服务 DID、执行时间和签名 receipt。签名 receipt MUST 符合 `cx.schema.erasure_receipt.v1`；若作为历史事件发布，Event.kind MUST 为 `cx.audit.erasure_receipt`。
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
- audit view 能验证 target event id、原始 envelope digest / proof `event_digest`、redaction event id、执行服务 DID、执行时间和签名 receipt。
- 若 active legal hold 存在，pruning MUST fail closed；snapshot 仍可隐藏普通视图明文，但不得物理删除 legal-hold 边界内要求保留的 payload。

## 4. Capability Vectors

### 4.1 目标

本文件将 capability 的链式授权、撤销回滚与审批约束固定为跨实现向量。  
适配对象：`identity-registry`, `principal_server_events_api`, `e2ee_client`, `enterprise_client`, `agent_runtime`.

向量命名：

```text
cx.vector.capability.<scenario>.v1
```

每个向量应检查：

- selector scope 是否正确绑定到 actor/device/realm/action。
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
      "cx.realm.admin"
    ],
    "constraints": []
  },
  "delegations": [
    {
      "event_id": "cx:event:019640d0-c000-7000-8000-000000000000",
      "kind": "cx.capability.delegate",
      "realm_id": "cx:realm:0196414c-8000-7000-8000-000000000000",
      "actor_id": "did:web:root-admin.example.com",
      "payload": {
        "parent_grant_id": "cx:grant:019640d0-b800-7000-8000-000000000000",
        "subject": "did:web:ops.example.com",
        "resources": [
          {
            "kind": "realm",
            "realm_id": "cx:realm:0196414c-8000-7000-8000-000000000000",
            "match_scope": "realm_wide"
          }
        ],
        "actions": [
          "cx.capability.delegate",
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
      "refs": [
      { "id": "cx:event:01964180-0350-72ab-a000-000000000000", "role": "authorized_by", "critical": true }
    ]
    },
    {
      "event_id": "cx:event:019640d0-c400-7000-8000-000000000000",
      "kind": "cx.capability.delegate",
      "realm_id": "cx:realm:0196414c-8000-7000-8000-000000000000",
      "actor_id": "did:web:ops.example.com",
      "payload": {
        "parent_grant_id": "cx:grant:019640d0-c000-7000-8000-000000000000",
        "subject": "did:web:intern.example.com",
        "resources": [
          {
            "kind": "realm",
            "realm_id": "cx:realm:0196414c-8000-7000-8000-000000000000",
            "match_scope": "realm_wide"
          }
        ],
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
      "refs": [
      { "id": "cx:event:019640d0-c000-7000-8000-000000000000", "role": "authorized_by", "critical": true }
    ]
    }
  ],
  "action_query": {
    "actor_id": "did:web:intern.example.com",
    "action": "cx.invite.create",
    "resource": "cx:realm:0196414c-8000-7000-8000-000000000000",
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
    "cx:event:01964180-0350-72ab-a000-000000000000",
    "cx:event:019640d0-c000-7000-8000-000000000000",
    "cx:event:019640d0-c400-7000-8000-000000000000"
  ],
  "constraints_checked": {
    "time": true,
    "resource_scope": true,
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
      "event_id": "cx:event:01964101-2800-7000-8000-000000000000",
      "kind": "cx.capability.grant",
      "payload": {
        "grant_id": "cx:grant:01964101-2800-7000-8000-000000000000",
        "subject": "did:web:alice.example.com",
        "actions": [
          "cx.message.create"
        ]
      },
      "created_at": "2026-04-26T00:00:00Z"
    },
    {
      "event_id": "cx:event:01964181-2800-7000-8000-000000000000",
      "kind": "cx.capability.revoke",
      "payload": {
        "grant_id": "cx:grant:01964101-2800-7000-8000-000000000000"
      },
      "created_at": "2026-04-26T00:00:01Z"
    },
    {
      "event_id": "cx:event:019641d1-2800-7000-8000-000000000000",
      "kind": "cx.member.state",
      "payload": {
        "actor_id": "did:web:alice.example.com",
        "membership": "leave"
      },
      "created_at": "2026-04-26T00:00:02Z"
    },
    {
      "event_id": "cx:event:0196414c-c04a-7000-8000-000000000000",
      "kind": "cx.message.create",
      "actor_id": "did:web:alice.example.com",
      "created_at": "2026-04-26T00:00:03Z",
      "payload": {
        "flow_id": "cx:flow:0196418d-cc00-7000-8000-000000000000",
        "content": {
          "kind": "cx.content.text",
          "body": "should_fail_if_revoke_applies"
        }
      },
      "prev_refs": [
        "cx:event:019641d1-2800-7000-8000-000000000000"
      ]
    }
  ],
  "rollback": {
    "target_event_id": "cx:event:01964181-2800-7000-8000-000000000000",
    "reason": "revoke_undo_invalid_signature"
  }
}
```

期望输出：

- 初始解析：`cx:event:0196414c-c04a-7000-8000-000000000000` 因 revoke 生效应拒绝或标记 soft-fail/rejected（取决于实现策略）。
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
    "event_id": "cx:event:01964148-a800-7000-8000-000000000000",
    "kind": "cx.policy.action",
    "actor_id": "did:web:contractor.example",
    "realm_id": "cx:realm:0196414c-8000-7000-8000-000000000000",
    "hlc": "01970e589d26-0001-aaaaaaaa",
    "payload": {
      "action": "cx.realm.admin",
      "approval_required": true,
      "approval_quorum": 2,
      "policy_scope": "realm:01js0ms000000000000000000"
    },
    "refs": [
      { "id": "cx:event:0196419b-298e-7368-9a80-000000000000", "role": "authorized_by", "critical": true }
    ]
  },
  "capabilities": [
    {
      "kind": "cx.capability.grant",
      "subject": "did:web:contractor.example",
      "actions": [
        "cx.realm.admin"
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
  "event_id": "cx:event:019640ed-8000-7000-8000-000000000000",
  "actor_id": "did:web:actor-a.example.com",
  "actor_seq": 1,
  "hlc": "019b76daa800-0000-a0000000",
  "prev_refs": [],
  "refs": [],
  "kind": "cx.flow.update",
  "unsigned": {
    "target_ref_hint": "cx:flow:019640c5-0000-7000-8000-000000000000"
  },
  "content_digest": "sha256:..."
}
```

实现 MAY 使用真实 canonical JSON、CID、签名和 hash 替换示例值，但 MUST 保持以下语义：

- `event_id` 是内容寻址或签名绑定后的稳定 ID。
- `actor_seq` 在同一 actor 的单条因果路径上严格递增；并发 sibling fork 可出现相同高度。
- `hlc` 是 Hybrid Logical Clock，不能单独决定因果顺序。
- `unsigned.target_ref_hint` MAY 指向标准对象、Morph、Relation、View、Space 或 Realm，仅作为测试向量的阅读辅助；规范性目标必须来自 `payload.*` 字段、`payload.object.id`、precondition/effect cell key 或 reducer 规则。标准 Event envelope 顶层 `target_ref` 是 legacy 字段，MUST NOT 出现。

### 5.2.1 Vector: Late Key Recovery T0 Determinism

向量名称：

```text
cx.vector.e2ee.late_key_recovery.t0_deterministic_visibility.v1
```

输入：

- 目标密文事件 `E1` 在 anchored history 的 deterministic pre-state `T0` 中对 `receiver` 可见，且 `receiver` 在 `T0` 是 Realm member。
- `receiver` 在 `E1` accepted 之后、late key request 发出之前被 `cx.member.state{membership=ban}` 或等价 remove 事件移出 Realm。
- 两个客户端以不同本地到达顺序观察同一组 anchored events：客户端 A 先看到 `E1` 后看到 ban；客户端 B 先同步到 ban，再通过 backfill 看到 `E1`。
- key backup / archive node / peer share 在发 key 前重新计算 `E1` 的 `T0` membership、history visibility 和当前 share policy。

期望：

- 两个客户端对 `E1` 的 late recovery 结果一致，且只取决于 anchored `T0` effective view，不取决于本地到达顺序或 wall clock。
- 若 `receiver` 在 `T0` 可见且当前 share policy 仍允许历史恢复，late key 可以发放；后续 ban/remove 不 retroactively 改写 `E1` 的 verified timeline。
- 若 `receiver` 在 `T0` 不可见，或 key source 未在发 key 前重新执行 `T0` 校验，必须拒绝并返回 `key_unavailable` / `policy_denied` 类错误；这才是 removed_actor negative path。
- 测试不得把“`T0` 后被 ban”单独作为拒绝理由；拒绝理由必须落在 `T0` 不可见或 key source unauthorized。

### 5.3 Vector: Board Collection Projection

输入：

```json
{
  "realm_id": "cx:realm:0196419b-0000-7000-8000-000000000000",
  "events": [
    {
      "kind": "cx.space.create",
      "unsigned": {
        "target_ref_hint": "cx:space:019640b6-8000-7000-8000-000000000000"
      },
      "payload": {
        "object": {
          "id": "cx:space:019640b6-8000-7000-8000-000000000000",
          "schema": "cx.schema.space.v1",
          "realm_id": "cx:realm:0196419b-0000-7000-8000-000000000000",
          "kind": "board",
          "title": "Release Board",
          "created_by": "did:web:alice.example.com",
          "created_at": "2026-04-26T00:00:00Z"
        }
      }
    },
    {
      "kind": "cx.space.create",
      "unsigned": {
        "target_ref_hint": "cx:space:01964010-8400-7000-8000-000000000000"
      },
      "payload": {
        "object": {
          "id": "cx:space:01964010-8400-7000-8000-000000000000",
          "schema": "cx.schema.space.v1",
          "realm_id": "cx:realm:0196419b-0000-7000-8000-000000000000",
          "parent_ref": "cx:space:019640b6-8000-7000-8000-000000000000",
          "kind": "list",
          "title": "Todo",
          "rank": "U",
          "created_by": "did:web:alice.example.com",
          "created_at": "2026-04-26T00:00:00Z"
        }
      }
    },
    {
      "kind": "cx.flow.create",
      "unsigned": {
        "target_ref_hint": "cx:flow:019640c5-0400-7000-8000-000000000000"
      },
      "payload": {
        "object": {
          "id": "cx:flow:019640c5-0400-7000-8000-000000000000",
          "schema": "cx.schema.flow.v1",
          "realm_id": "cx:realm:0196419b-0000-7000-8000-000000000000",
          "title": "Release checklist",
          "tracks": {
            "synthesis": {
              "is_primary": true
            }
          },
          "created_by": "did:web:alice.example.com",
          "created_at": "2026-04-26T00:00:00Z"
        },
        "initial_relations": [
          {
            "relation_kind": "contains",
            "from_ref": "cx:space:01964010-8400-7000-8000-000000000000",
            "to_ref": "cx:flow:019640c5-0400-7000-8000-000000000000",
            "fields": {
              "board_space_id": "cx:space:019640b6-8000-7000-8000-000000000000",
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

- Collection projection MUST 返回 `object.id = cx:flow:019640c5-0400-7000-8000-000000000000`。
- 返回项 MUST 位于 `cx:space:01964010-8400-7000-8000-000000000000`。
- View cursor MUST 绑定 projection、view、frontier 与权限上下文。

### 5.4 Vector: Flow Card Move Read-Your-Writes

输入：

```json
{
  "write": {
    "kind": "cx.flow.move",
    "unsigned": {
      "target_ref_hint": "cx:flow:019640c5-0400-7000-8000-000000000000"
    },
    "payload": {
      "board_space_id": "cx:space:019640b6-8000-7000-8000-000000000000",
      "flow_id": "cx:flow:019640c5-0400-7000-8000-000000000000",
      "from_space_id": "cx:space:01964010-8400-7000-8000-000000000000",
      "target_space_id": "cx:space:01964010-8800-7000-8000-000000000000",
      "rank": "U"
    }
  },
  "query": {
    "object_types": [
      "flow"
    ],
    "consistency": {
      "wait_for": "barrier_cursor_from_write"
    }
  }
}
```

期望：

- Projection executor 在返回前 MUST 等待本地 frontier 覆盖写入 token，或返回可恢复超时。
- 查询结果中该 Flow item 的 `list_id` MUST 为 `cx:space:01964010-8800-7000-8000-000000000000`。

### 5.5 Vector: Flow Discussion Track Visibility

输入：

```json
{
  "flow_id": "cx:flow:019640c5-0400-7000-8000-000000000000",
  "viewer": "did:web:viewer.example.com",
  "viewer_can_read_flow": true,
  "viewer_is_track_member": false
}
```

期望：

- Flow projection MAY 显示 lazy 的 discussion-track 引用。
- Flow discussion timeline MUST NOT 展开。
- 通知 / 搜索结果 MUST NOT 泄露隐藏的 discussion 消息。

#### 5.5.1 Vector: Flow Discussion Surface Visibility

输入：

```json
{
  "flow_id": "cx:flow:01964195-8400-7000-8000-000000000000",
  "track": "discussion",
  "viewer_grants": ["cx.flow.read"],
  "viewer_track_membership": "none"
}
```

期望：

- 当 discussion 可发现性允许时，Flow projection MAY 显示 lazy / locked 的 discussion surface 引用。
- Flow activity MUST NOT 包含隐藏的 discussion 消息。
- Flow context MUST NOT 通过预览、摘要、通知、搜索片段、embedding 或 decision summary 泄露隐藏的 discussion 消息正文。

### 5.6 Vector: Flow Discussion Timeline

输入：

```json
{
  "flow_id": "cx:flow:01964180-0400-7000-8000-000000000000",
  "events": [
    {
      "kind": "cx.message.create",
      "unsigned": {
        "target_ref_hint": "cx:message:01964147-0400-7000-8000-000000000000"
      },
      "payload": {
        "flow_id": "cx:flow:01964180-0400-7000-8000-000000000000",
        "content": {
          "kind": "cx.content.text",
          "body": "discussion message"
        }
      }
    }
  ]
}
```

期望：

- 当 viewer 可读取 Flow discussion track 时，`flow-discussion-timeline` MUST 返回该消息。
- 仅当 viewer 可读取 Flow（按 Flow 的 effective scope）时，`flow-discussions` MUST 才包含该消息；当 Flow 通过 `scope_ref` 落在 Realm 内的 [Circle](../models/circle.md) 时，仅有 Realm-default 成员身份不足以读取该 Flow——必须同时是该 Circle 成员。

## 6. Space Lifecycle Vectors

### 6.1 目标

本节定义 Space（看板 / 列 / 泳道 / calendar bucket / page group ...）`active` ↔ `archived` ↔ `tombstoned` 状态机的跨实现测试向量。canonical 写入路径见 [`../models/realm-and-space.md` §3.4](../models/realm-and-space.md)；canonical 状态机对齐见 [`../models/common-fields.md` §5](../models/common-fields.md)。

实现声称支持以下 profile 时 SHOULD 运行本节向量：

- `cx.profile.kanban_mvp.v1`
- `cx.profile.full_client.v1`
- `cx.profile.principal_server.v1`

### 6.2 Vector: Space Archive 然后 Restore（happy path）

输入（按 causal order 应用）：

```json
{
  "realm_id": "cx:realm:0196419b-0000-7000-8000-000000000000",
  "events": [
    {
      "kind": "cx.space.create",
      "unsigned": {
        "target_ref_hint": "cx:space:019640b6-8000-7000-8000-000000000000"
      },
      "payload": {
        "object": {
          "id": "cx:space:019640b6-8000-7000-8000-000000000000",
          "schema": "cx.schema.space.v1",
          "realm_id": "cx:realm:0196419b-0000-7000-8000-000000000000",
          "kind": "board",
          "title": "Release Board",
          "created_by": "did:web:alice.example.com",
          "created_at": "2026-05-15T10:00:00Z"
        }
      }
    },
    {
      "kind": "cx.space.archive",
      "unsigned": {
        "target_ref_hint": "cx:space:019640b6-8000-7000-8000-000000000000"
      },
      "created_at": "2026-05-15T10:05:00Z",
      "payload": {
        "space_id": "cx:space:019640b6-8000-7000-8000-000000000000",
        "reason": "release_cycle_complete"
      }
    },
    {
      "kind": "cx.space.restore",
      "unsigned": {
        "target_ref_hint": "cx:space:019640b6-8000-7000-8000-000000000000"
      },
      "created_at": "2026-05-15T10:10:00Z",
      "payload": {
        "space_id": "cx:space:019640b6-8000-7000-8000-000000000000",
        "reason": "release_reopened"
      }
    }
  ]
}
```

期望：

- 应用 `cx.space.archive` 后，Space 物化对象 MUST 有 `state == "archived"` 且 `state_changed_at == "2026-05-15T10:05:00Z"`。默认 collection projection（不显式包含 archived items）MUST NOT 返回该 Space；显式带 `include_states=["archived"]` 的查询 MUST 仍可返回它。
- 应用 `cx.space.restore` 后，Space 物化对象 MUST 有 `state == "active"` 且 `state_changed_at == "2026-05-15T10:10:00Z"`。默认 projection MUST 重新展示该 Space。
- Restore **不**级联——若该 Space 包含 child Space（如 List 在 Board 内）或内部 Flow 且它们各自处于 `archived`，restore parent MUST NOT 改变 children 的 state。
- archive 期间未被擦除的 `contains` Relation、Flow position cell 与 `parent_ref` cell MUST 在 restore 后保持原值；用户看到的内容与 archive 之前一致。

### 6.3 Vector: Space Restore 在 `active` 状态被拒绝

输入：

```json
{
  "realm_id": "cx:realm:0196419b-0000-7000-8000-000000000000",
  "pre_state": {
    "space": {
      "id": "cx:space:019640b6-8000-7000-8000-000000000000",
      "state": "active"
    }
  },
  "event": {
    "kind": "cx.space.restore",
    "unsigned": {
      "target_ref_hint": "cx:space:019640b6-8000-7000-8000-000000000000"
    },
    "created_at": "2026-05-15T11:00:00Z",
    "payload": {
      "space_id": "cx:space:019640b6-8000-7000-8000-000000000000"
    }
  }
}
```

期望：

- Reducer MUST 返回 `failed_precondition`，`reason == "space_not_archived"`。
- Space 物化对象 MUST 不被修改；`state_changed_at` MUST 保持 archive 之前的值或缺省。
- Event 不进入 reducer，但 envelope 本身签名/schema 合法时 MAY 仍被持久化为 envelope 历史（按各实现的 envelope-vs-state 边界处理）；reducer state 不得反映本次写入。

### 6.4 Vector: Space Restore 在 `tombstoned` 状态被拒绝（不可复活）

输入：

```json
{
  "realm_id": "cx:realm:0196419b-0000-7000-8000-000000000000",
  "pre_state": {
    "space": {
      "id": "cx:space:019640b6-8000-7000-8000-000000000000",
      "state": "tombstoned",
      "state_changed_at": "2026-05-15T09:00:00Z"
    }
  },
  "event": {
    "kind": "cx.space.restore",
    "unsigned": {
      "target_ref_hint": "cx:space:019640b6-8000-7000-8000-000000000000"
    },
    "created_at": "2026-05-15T12:00:00Z",
    "payload": {
      "space_id": "cx:space:019640b6-8000-7000-8000-000000000000"
    }
  }
}
```

期望：

- Reducer MUST 返回 `failed_precondition`，`reason == "space_not_archived"`（与 §6.3 同 reason；tombstoned 在状态机中不属于 `archived`，复活路径不存在）。
- Space 物化对象 MUST 保持 `state == "tombstoned"` 与原 `state_changed_at`。
- 该向量是 `tombstoned` 不可逆终态约束（[`realm-and-space.md` §3.4](../models/realm-and-space.md)、[`space.schema.json#/properties/state`](../../artifacts/schemas/space.schema.json)）的 wire 级证据：实现 MUST NOT 提供任何"先 restore 再写入"的 tombstoned 复活路径。需要重新启用一个等价容器时，正确的做法是 `cx.space.create` 一个新 Space。

### 6.5 Vector: Archive 在非 `active` 状态被拒绝

输入：

```json
{
  "realm_id": "cx:realm:0196419b-0000-7000-8000-000000000000",
  "pre_state": {
    "space": {
      "id": "cx:space:019640b6-8000-7000-8000-000000000000",
      "state": "archived",
      "state_changed_at": "2026-05-15T10:05:00Z"
    }
  },
  "event": {
    "kind": "cx.space.archive",
    "unsigned": {
      "target_ref_hint": "cx:space:019640b6-8000-7000-8000-000000000000"
    },
    "created_at": "2026-05-15T11:30:00Z",
    "payload": {
      "space_id": "cx:space:019640b6-8000-7000-8000-000000000000"
    }
  }
}
```

期望：

- Reducer MUST 返回 `failed_precondition`，`reason == "space_not_active"`（[common-fields.md §5.1](../models/common-fields.md) state-transition 表）。
- Space 物化对象 MUST 保持 `state == "archived"` 与原 `state_changed_at`；same-state self-transition 不被当作 idempotent no-op。
- 客户端如果意图是"重新 archive"，正确路径是先 `cx.space.restore` 再 `cx.space.archive`。
- 该向量对 Flow / Morph 等价同形：`cx.flow.archive` 在 `state != "active"` 时 `flow_not_active`；`cx.morph.archive` 同理 `morph_not_active`。

### 6.6 Vector: Tombstone 在已 tombstoned 状态被拒绝

输入：

```json
{
  "realm_id": "cx:realm:0196419b-0000-7000-8000-000000000000",
  "pre_state": {
    "space": {
      "id": "cx:space:019640b6-8000-7000-8000-000000000000",
      "state": "tombstoned",
      "state_changed_at": "2026-05-15T09:00:00Z"
    }
  },
  "event": {
    "kind": "cx.space.tombstone",
    "unsigned": {
      "target_ref_hint": "cx:space:019640b6-8000-7000-8000-000000000000"
    },
    "created_at": "2026-05-15T12:00:00Z",
    "payload": {
      "space_id": "cx:space:019640b6-8000-7000-8000-000000000000"
    }
  }
}
```

期望：

- Reducer MUST 返回 `failed_precondition`，`reason == "space_already_terminal"`（[common-fields.md §5.1](../models/common-fields.md) 终态等价规则）。
- Space 物化对象 MUST 保持 `state == "tombstoned"` 与原 `state_changed_at`。
- 该向量对 Flow / Morph 等价同形：`cx.redaction` 指向已 `redacted` 的 Flow / Morph 时同样返回 `<kind>_already_terminal`。终态进入是单向、单次操作。

### 6.7 Vector: Update 在非 `active` 状态被拒绝

输入：

```json
{
  "realm_id": "cx:realm:0196419b-0000-7000-8000-000000000000",
  "pre_state": {
    "space": {
      "id": "cx:space:019640b6-8000-7000-8000-000000000000",
      "state": "archived",
      "state_changed_at": "2026-05-15T10:05:00Z",
      "title": "Release Board"
    }
  },
  "event": {
    "kind": "cx.space.update",
    "unsigned": {
      "target_ref_hint": "cx:space:019640b6-8000-7000-8000-000000000000"
    },
    "created_at": "2026-05-15T11:45:00Z",
    "payload": {
      "space_id": "cx:space:019640b6-8000-7000-8000-000000000000",
      "patch": {
        "title": "Renamed while archived"
      }
    }
  }
}
```

期望：

- Reducer MUST 返回 `failed_precondition`，`reason == "space_not_active"`（"update on non-active object" invariant，[common-fields.md §5.1](../models/common-fields.md)）。
- Space 物化对象 MUST 保持原 `title="Release Board"` 与 `state == "archived"`；update **不**作为隐式 restore。
- 客户端正确路径：先 `cx.space.restore`，update 通过后再决定是否 `cx.space.archive`。
- 该向量对 Flow / Morph `*.update` 等价同形。

## 7. Member Delivery Binding Vectors

### 7.1 目标

验证 `cx.member.state{membership="join"}` 的 `delivery_binding` payload 是 Realm-scoped event 投递的唯一权威路由源：
- schema-level conditional required 字段强制执行；
- DID Document service entry **不构成** fallback；
- 路由失败时 sender fail-closed（quarantine + retry，不退回 DID Document）；
- rebind 通过 causal frontier handover；
- 撤销后投递立即停止。

下列向量假设 Realm `cx:realm:7d000000-0000-7000-8000-000000000000`、actor `did:webvh:01HV...:alice` 已存在；具体 id 仅作占位。本节是 normative vector description；机器可执行 fixture 位于 [`../../artifacts/fixtures/membership-delivery-binding-fixture.json`](../../artifacts/fixtures/membership-delivery-binding-fixture.json)，runner MUST 同时消费该 fixture 与本文 prose，不得再依赖未落地的目录约定。

### 7.2 Vector: `explicit` Binding 接受

Input — `cx.member.state{membership="join"}` Move payload：

```json
{
  "realm_id": "cx:realm:7d000000-0000-7000-8000-000000000000",
  "actor_id": "did:webvh:01HV...:alice",
  "membership": "join",
  "delivery_status": "routable",
  "delivery_binding": {
    "recipient_service_did": "did:web:principal.acme.example",
    "recipient_service_type": "principal_server",
    "binding_scope": "realm",
    "binding_source": "explicit",
    "delivery_modes": ["events", "sync", "to_device", "push", "key_packages"],
    "resolved_at": "2026-05-19T10:00:00Z",
    "service_acceptance_ref": "cx:event:7d000001-0000-7000-8000-000000000000"
  },
  "gate_proofs": [ "..." ]
}
```

预设：Realm policy `cx.realm.delivery_binding_policy` 声明 `allow_binding_sources` 包含 `explicit`、`allowed_recipient_services` 包含 `did:web:principal.acme.example`、`required_endorsers` 含 `did:web:acme.example`，`service_acceptance_ref` 引用的 Event 由 `did:web:principal.acme.example` 签发且 scope 覆盖该 Realm。

期望：
- reducer 接受 join Move；写入成员 cell。
- 此后任何向 Alice 投递的 Realm S event/sync/to_device/push/key_packages MUST 走 `did:web:principal.acme.example`，**禁止**触发 DID Document service entry resolution。

### 7.3 Vector: `did_document_default` Fallback 物化

Input — Realm policy `cx.realm.delivery_binding_policy` 声明 `allow_did_document_default=true`，其余字段未限制；Alice DID Document service `ContrixPrincipalServer` 指向 `did:web:personal.alice.example`，canonical hash `sha256:abc...`。

客户端构造 join Move 时 MUST 先解析 DID Document 并物化进 binding：

```json
{
  "realm_id": "cx:realm:...",
  "actor_id": "did:webvh:01HV...:alice",
  "membership": "join",
  "delivery_status": "routable",
  "delivery_binding": {
    "recipient_service_did": "did:web:personal.alice.example",
    "recipient_service_type": "principal_server",
    "binding_scope": "realm",
    "binding_source": "did_document_default",
    "delivery_modes": ["events", "sync", "to_device", "push", "key_packages"],
    "resolved_at": "2026-05-19T10:00:00Z",
    "did_document_digest": "sha256:abc0000000000000000000000000000000000000000000000000000000000000"
  }
}
```

期望：
- reducer 接受 join Move（`did_document_digest` 与 `resolved_at` 满足 conditional required）。
- 同形 Move 缺少 `did_document_digest` MUST 被 schema 拒绝（`schema_violation`），reducer 不进入验证流程。
- 同形 Move 在 Realm policy `allow_did_document_default=false` 时 reducer MUST 返回 `delivery_binding_policy_mismatch`。
- 一旦该 join 被接受，sender **不得**在后续投递时 re-resolve DID Document——即使 DID Document 已更新指向新服务，仍按 cell 内 `delivery_binding` 投递，直到一次合法 rebind。

### 7.4 Vector: `unroutable` 成员

Input — Realm policy `cx.realm.delivery_binding_policy` 声明 `allow_unroutable_membership=true`。Alice join Move 携带：

```json
{
  "realm_id": "cx:realm:...",
  "actor_id": "did:webvh:01HV...:alice",
  "membership": "join",
  "delivery_status": "unroutable"
}
```

注意 `delivery_binding` 字段**缺失**，但 schema conditional `delivery_status=unroutable` 时不要求 binding。

期望：
- reducer 接受。
- 任何 sender 计算"该 Realm S 应投递给 Alice"的目标集合时 MUST 跳过该成员；不得用 DID Document 推导 fallback。
- 客户端对该成员的本地视图：只展示在 reducer state 与本地索引中，但不向其推送通知 / sync / push / to_device。
- 同形 Move 在 Realm policy `allow_unroutable_membership=false` 时 reducer MUST 返回 `delivery_binding_policy_mismatch`。

### 7.5 Vector: Rebind Handover + 撤销后停止投递

序列：

1. **Initial join**（`F0`）：Alice join with `recipient_service_did=did:web:personal.alice.example`，accepted。
2. **Events 流量**：Realm 内事件 `E1, E2` 进入因果图，sender 将它们投递到 `did:web:personal.alice.example`。
3. **Rebind**（`F1`）：Alice 提交同状态 `cx.member.state{membership="join"}` self-transition，新 binding 指向 `did:web:principal.acme.example`，签名按 `rebind_authorization` 规则。Move accepted。
4. **Post-rebind events**：sender 投递 `E3, E4` 时观察 `service_binding_ref.delivery_binding_frontier`：
   - sender frontier ≥ `F1` → 投递到 `did:web:principal.acme.example`；
   - sender frontier 仍 `< F1` 且投到旧 `did:web:personal.alice.example` → 旧服务在 `handover_grace_seconds` 内接受并返回 `delivery_binding_stale + new_recipient_service_did=did:web:principal.acme.example + handover_frontier=F1`；sender MUST 切换后重试，**不得**回退到 DID Document。
   - sender frontier ≥ `F1` 但仍投到旧 → 旧服务 reject `delivery_binding_handed_over`。
5. **Grace 结束**：旧服务停止接受新 Realm S event；本地 to-device 队列、push registration、MLS group share state 进入 destruction。
6. **撤销**：Alice 离职，Org-A 治理 key 提交 `cx.member.state{membership="leave"}` 或 `cx.capability.revoke`。`F2` 之后 sender MUST NOT 继续向 `did:web:principal.acme.example` 投递该 Realm 的内容；MUST NOT 转而退回 `did:web:personal.alice.example`（DID Document fallback）；该 actor 在 Realm S 中变成 **non-member**。

期望：
- 整个序列中 sender 解析投递目标 MUST 完全依赖 effective member cell 的 `delivery_binding`，DID Document service entry 永远不被 query。
- `delivery_binding_frontier` 字段在所有 service-to-service push 中均存在；sender 端落后 frontier 收到 stale signal 后 MUST 切换、不重投。
- 撤销后 sender 试图继续投递 MUST 收到 `member_not_in_space` 或 `capability_revoked`；MUST 不构造任何 "fallback to DID Document" 路径。

### 7.6 覆盖矩阵

| 字段 / 行为 | §7.2 explicit | §7.3 did_document_default | §7.4 unroutable | §7.5 rebind+revoke |
| --- | --- | --- | --- | --- |
| Conditional required (`service_acceptance_ref`) | ✓ | — | — | ✓ |
| Conditional required (`did_document_digest`) | — | ✓ | — | — |
| Policy `allow_did_document_default=false` 拒绝 | — | ✓ | — | — |
| Policy `allow_unroutable_membership=false` 拒绝 | — | — | ✓ | — |
| 投递路径 ≡ binding，无 DID Document fallback | ✓ | ✓ | ✓ (skip) | ✓ |
| Rebind handover frontier 切换 | — | — | — | ✓ |
| 撤销后停止投递且无 fallback | — | — | — | ✓ |

## 8. Handle Vectors

### 8.1 目标

验证 `@user:domain` / `user@domain` 这类人类可读地址只作为寻址输入，最终必须解析为 DID 与 Realm-scoped delivery binding。

### 8.2 Vector: 组织 Handle 构造成 Join

Input — 邀请方在 Acme 组织 Realm 中添加 `@alice:acme.example`。客户端调用：

```json
{
  "handle": "@alice:acme.example",
  "intent": "member_add",
  "realm_id": "cx:realm:0196419b-0000-7000-8000-000000000000",
  "requester": "did:web:bob.example",
  "proof_challenge": "cx-challenge-001"
}
```

Directory 返回 verified handle claim：

```json
{
  "did": "did:webvh:QmAlice:users.acme.example",
  "subject": "did:webvh:QmAlice:users.acme.example",
  "handle": "@alice:acme.example",
  "handle_uri": "contrix://acme.example/users/alice",
  "handle_aliases": ["acct:alice@acme.example"],
  "verified": true,
  "audience": "cx:realm:0196419b-0000-7000-8000-000000000000",
  "claims": [{
    "claim_type": "organization_handle",
    "handle": "@alice:acme.example",
    "handle_uri": "contrix://acme.example/users/alice",
    "handle_aliases": ["acct:alice@acme.example"],
    "subject": "did:webvh:QmAlice:users.acme.example",
    "issuer": "did:web:acme.example",
    "binding_state": "verified",
    "audience": "cx:realm:0196419b-0000-7000-8000-000000000000",
    "member_delivery_binding": {
      "recipient_service_did": "did:web:principal.acme.example",
      "recipient_service_type": "principal_server",
      "binding_source": "organization_policy",
      "delivery_modes": ["events", "sync", "to_device", "push", "key_packages"],
      "service_acceptance_ref": "cx:event:0196419b-0000-7000-8000-000000000001",
      "policy_ref": "cx:event:0196419b-0000-7000-8000-000000000002"
    },
    "created_at": "2026-05-19T00:00:00Z",
    "expires_at": "2026-08-19T00:00:00Z",
    "proofs": [{
      "kind": "detached_jws",
      "alg": "EdDSA",
      "verification_method": "did:web:principal.acme.example#key-1",
      "payload_digest": "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
      "created_at": "2026-05-19T00:00:00Z",
      "audience": "cx:realm:0196419b-0000-7000-8000-000000000000",
      "jws": "aaa.bbb.ccc"
    }]
  }],
  "member_delivery_binding": {
    "recipient_service_did": "did:web:principal.acme.example",
    "recipient_service_type": "principal_server",
    "binding_source": "organization_policy",
    "delivery_modes": ["events", "sync", "to_device", "push", "key_packages"],
    "service_acceptance_ref": "cx:event:0196419b-0000-7000-8000-000000000001",
    "policy_ref": "cx:event:0196419b-0000-7000-8000-000000000002"
  },
  "expires_at": "2026-08-19T00:00:00Z"
}
```

Expected join Move:

- `payload.actor_id = did:webvh:QmAlice:users.acme.example`。
- `payload.delivery_binding.recipient_service_did = did:web:principal.acme.example`。
- `payload.delivery_binding.binding_source = organization_policy`。
- `payload.delivery_binding.service_acceptance_ref` 与 `policy_ref` 来自 verified claim / policy。
- Move payload MUST NOT 把 `@alice:acme.example` 当作 actor、cell subject 或 grant subject；受限 handle 明文 SHOULD NOT 进入公开 Realm history。

Negative cases：

- Directory 返回 `verified=false` 或 challenge / audience 不匹配 → builder MUST NOT 构造 handle-based join。
- 返回 `subject != did` → client MUST reject `handle_subject_mismatch`。
- 返回 `member_delivery_binding.recipient_service_did` 但 Realm `allowed_recipient_services` 不包含该 DID，且没有 required endorser 背书 → reducer MUST reject `delivery_binding_invalid`。
- 返回无 `member_delivery_binding.recipient_service_did` → 只能作为 DID lookup；除非 Realm policy 允许 `did_document_default` 并物化 fallback，否则 reducer MUST reject handle-based join。

## 9. Security Closure Vectors

本节收拢跨章节引用的安全闭环向量。每个 `vector_id` 均为规范性引用目标；结构化覆盖位于 [`../../artifacts/fixtures/security-closure-vectors.json`](../../artifacts/fixtures/security-closure-vectors.json)，`tools/lint_artifacts.py` 会校验该 fixture 覆盖本节要求的 security closure vector set，并校验每个 step 暴露可由实现测试消费的 `runner.given_state` / `operation` / `transcript` / `expected_state_transition` / `expected_external_response` / `expected_audit_reason` 字段。实现不得把这些 ID 当成仅供说明的标签。

### 9.1 Vector: Federation Replay After Key Revoke

`vector_id`: `cx.vector.federation.idempotency_after_key_revoke.v1`

Steps：

1. Origin service `did:web:alpha.example` 使用 active service key 向 destination 提交 `POST /api/v1/events`，header 绑定 `Source-Service-DID`、`Destination-Service-DID`、`Source-Trust-Domain`、`Destination-Trust-Domain`、`Request-Canonical-Digest`、`Idempotency-Key`，批次 accepted。
2. Realm policy 或 DID Document 随后撤销该 origin service key；destination 的 accepted authorization frontier 前进。
3. 攻击者重放完全相同的 HTTP body、signature 与 `Idempotency-Key`。

Expected：

- 若重放只命中历史幂等缓存，destination MUST 返回 `historical_only`，不得重新接受为当前授权写入。
- 若 origin service binding 已被 Realm policy 移除，destination MUST 返回 `capability_denied`。
- 若 `origin_key_state_digest` 或 authorization frontier 与缓存 entry 不一致，receiver MUST 重新执行完整授权判定，不得只凭 `Idempotency-Key` 放行。

### 9.2 Vector: WebRTC Media Plaintext Downgrade

`vector_id`: `cx.vector.webrtc.media_plaintext_downgrade.v1`

Steps：

1. Realm policy 未授权 `media_service_decrypts`，但客户端收到 SFU 要求其发送 plaintext-visible media key 的 offer。
2. Realm policy 授权媒体服务解密，但 SFU service DID 不在 `plaintext_visible_services`。
3. UI 未显示 required plaintext warning，却尝试加入解密型会议。

Expected：

- 三种情况均 MUST 拒绝 join / publish media key。
- 失败原因分别为 `media_plaintext_policy_missing`、`media_plaintext_service_not_visible`、`media_plaintext_warning_missing` 或实现映射到等价稳定 reason_code。

### 9.3 Vector: Identity Link Eager Invalidation

`vector_id`: `cx.vector.identity_link.eager_invalidation.v1`

Steps：

1. Principal 在 Realm R 中存在 active identity link。
2. R 接受 ban / leave / remove 中任一 membership transition，或 capability revoke 使该 link 不再满足 visibility gate。
3. Directory、sync cache、invite cache 和 local profile projection 仍持有旧 link。

Expected：

- 实现 MUST eager invalidation 所有关联 cache entry；后续 lookup 不得返回旧 link。
- 已建立的 session / device claim MUST 在下一次 authorization check 时失败或降级到最小披露状态。

### 9.4 Vector: Identity Link Policy Tightening Invalidation

`vector_id`: `cx.vector.identity_link.policy_tightening_invalidation.v1`

Steps：

1. Principal 在 disclosure policy、history visibility、minimal metadata mode、linked Realm visibility 或 Circle effective-scope visibility 放宽时建立 identity link。
2. 任一 policy 被收紧，使旧 link 的披露范围不再被允许。
3. 调用者继续使用旧 directory / sync cache 查询同一 principal。

Expected：

- 所有受影响 cache MUST 按 policy frontier 失效。
- 未重新通过当前 policy gate 的旧 link MUST 不再返回；UI / API 只能显示当前允许的最小身份信息。

### 9.5 Vector: Late Key Recovery Removed Actor

`vector_id`: `cx.vector.late_key_recovery.removed_actor.v1`

Steps：

1. Receiver 请求恢复 T0 历史密钥，但其在 T0 的 membership / history visibility 不允许查看该历史。
2. 或者 receiver 曾在 T0 可见，但 key source 在 ban / remove 之后未重新执行 T0 membership + current share policy 校验就发送 late material。

Expected：

- T0 不可见时 MUST 不解密，reason_code 为 `late_recovery_rejected_membership` 或等价稳定码。
- key source 未重新校验时 MUST 拒绝 share，reason_code 为 `late_recovery_share_not_authorized`。
- 客户端 UI 不得显示未授权明文或把其纳入 verified timeline。

### 9.6 Vector: Invite OOB Code Entropy

`vector_id`: `cx.vector.invite.oob_code_entropy.v1`

Steps：

1. 构造低于生产最低熵的 offline OOB code claim。
2. 构造 lookup 形态 OOB code，其有效窗口或 claim 次数超过 policy 上限。

Expected：

- reducer / verification service MUST 拒绝短熵 code claim。
- 超限 lookup 形态 MUST invalidate，不得进入 pending invite 或 accepted membership。

### 9.7 Vector: Invite Failure Indistinguishable

`vector_id`: `cx.vector.invite.failure_indistinguishable.v1`

Steps：

1. 分别触发 token 不存在、过期、已撤销、已消费、audience 不匹配、邀请者已离开 Realm、policy gate 不满足七类失败。
2. 对外调用同一个 claim endpoint，记录 HTTP status、response body、headers 和响应时间。

Expected：

- 对外响应 MUST byte-identical 或等价不可区分；仅服务端 audit log 可记录具体 reason_code。
- timing 差异 SHOULD ≤ 50ms；高安全 profile MUST 对该窗口做 jitter / padding。

### 9.8 Vector: Consent Scope Cascade

`vector_id`: `cx.vector.consent.scope_cascade.v1`

Steps：

1. Subject 对同一 peer 同时授予 `any` 与多个具体 scope consent。
2. Revoke `any`。
3. 重建 consent 后仅 revoke 某个具体 scope。
4. 尝试用未列出全部 active dot 的 revoke 表示完整撤销。

Expected：

- `any` revoke MUST cascade 到该 cell 的所有具体 scope。
- 具体 scope revoke 不影响 `any` 或其它 scope。
- 未列出全部 active dot 的 revoke 只能构成部分撤销，不能被解释为完整撤销。

### 9.9 Vector: Consent Cache Invalidation

`vector_id`: `cx.vector.consent.cache_invalidation.v1`

Steps：

1. Consent active 时 private contact discovery PSI result、invite capability gate 和 PSI index 均缓存了 peer 可达状态。
2. Subject revoke consent。
3. 调用 directory lookup、提交下一次 invite Move，并等待 PSI 下一轮轮转。

Expected：

- Private contact discovery / invite handoff MUST 立即不返回该 peer。
- 下一次 invite Move MUST precondition 失败并重判 capability gate。
- `any` revoke MUST 失效所有 scope cache；PSI 索引在下一次轮转时排除该 peer。

### 9.10 Vector: Sync Soft-Fail Reconcile

`vector_id`: `cx.vector.sync.soft_fail_reconcile.v1`

Steps：

1. Receiver 收到 soft-failed event，原因是缺少 dependency / auth state / key material。
2. Backfill 成功补齐全部依赖。
3. 另一路中，backfill 返回冲突或永久缺失。

Expected：

- 补齐后 reducer MUST deterministically 从 soft-fail 转为 accepted，并更新 covered frontier。
- 永久缺失或冲突时 MUST 转为 rejected / failed_precondition，不得无限留在 soft-fail。

### 9.11 Vector: Lattice LWW Open Set

`vector_id`: `cx.vector.lattice.lww_open_set.v1`

Steps：

1. 构造同一 anchor view 中多个 sibling write，它们对同一 open-set cell 产生竞争状态。
2. 所有 sibling 带相同 logical time，但 actor / event id / canonical digest tiebreaker 不同。
3. 两个 conformant reducer 以不同输入顺序重放。

Expected：

- sibling 集合与 tiebreaker MUST 产出同一 winner。
- 任一实现出现不同 winner、不同 bottom 或不同 covered frontier，均视为 reducer bug。

### 9.12 Vector: E2EE Relaxed Window Exceeds Ceiling

`vector_id`: `cx.vector.e2ee_relaxed.window_exceeds_ceiling.v1`

Steps：

1. Realm policy event 尝试把 `relaxed_window_max_ms` 写为大于 300000。
2. Receiver 收到 old-epoch decrypt admission，其 gap 超过当前 policy window。
3. Deployment profile 尝试通过 unrelated profile 重新定义 hard ceiling。

Expected：

- Reducer MUST 以 `relaxed_window_exceeds_ceiling` 拒绝超限 policy write。
- Receiver MUST 独立拒绝超过当前 policy window 的 decrypt admission。
- Hard ceiling 不可由 deployment profile 重定义；实现不得 silently clamp 后继续接受。

## 10. Service Closure Vectors

### 10.1 Vector: Ephemeral Capability And TTL

`vector_id`: `cx.vector.ephemeral.capability_ttl.v1`

Steps：

1. Actor 对 `cx.typing` 提交 `cx.ephemeral.send`，但只持有 `cx.presence.broadcast`。
2. Actor 持有正确 action 后，提交超出 advertised kind-specific TTL 的 envelope。
3. Ephemeral channel 暂时不可用。

Expected：

- 第 1 步 MUST 返回 `ephemeral_kind_not_permitted`。
- 第 2 步 MUST 返回 `ephemeral_ttl_out_of_range`。
- 第 3 步 MUST 返回 `ephemeral_channel_unavailable`，且不写 durable Event、不推进 actor_seq / Realm frontier。

### 10.2 Vector: Projection Pagination Shape

`vector_id`: `cx.vector.projection.pagination_shape.v1`

Steps：

1. 调用 `cx.projection.spaces` / `flows` / `morphs`，请求 `limit=1`。
2. 使用返回的 `next_cursor` 继续读取。
3. 下游 service-call 返回缺失 `has_more` 或 cursor 形态不合法的响应。

Expected：

- 每个响应 MUST 带 `has_more`；有后续页时 MUST 带合法 `cx:cursor:*`。
- Cursor MUST 绑定调用者、selector 和 projection purpose，不得跨 service / Realm 复用。
- 缺失分页闭包字段时上游 MUST 归类为 `invalid_response`。

### 10.3 Vector: KeyPackage Exhaustion And Claim Limits

`vector_id`: `cx.vector.keypackage.exhaustion_claim_limits.v1`

Steps：

1. Device 可用 KeyPackage 数量低于 `keypackage_min_available`。
2. 同一 `(requester_service_did, target_principal_id)` 在 60s 内发起超过 5 次 claim。
3. 已 claimed KeyPackage 到达 `expires_at` 后再尝试 consume。

Expected：

- Server SHOULD 在可见响应中返回 `available_count`，client MUST 在下一次 maintenance / sync 补充上传。
- 超限 claim 对外仍保持反枚举失败，不泄露目标是否存在；内部审计 reason 为 `keypackage_claim_rate_limited`。
- 过期 claimed package MUST 转为 revoked / unusable，不得回到 `published`，迟到 consume MUST 被拒绝。

### 10.4 Vector: Soft Logout DID Proof Required

`vector_id`: `cx.vector.auth.soft_logout_did_proof.v1`

Steps：

1. Session 进入 `soft_logged_out`。
2. Client 仅携带仍有效的 refresh token 请求恢复。
3. Client 重新提交 refresh/OIDC/re-auth，并携带授权 DID/device key 对 challenge 的签名。

Expected：

- 第 2 步 MUST 返回 `did_proof_required`，不得签发 active session grant。
- 第 3 步的 proof MUST 覆盖 principal、device、audience、challenge、request canonical hash 和 expiry；验证成功后才可恢复为 `active`。

### 10.5 Vector: Session Grant Audience Binding

`vector_id`: `cx.vector.auth.session_grant_audience_binding.v1`

Steps：

1. Auth Server 收到 `cx.account.issue_session_grant`，proof 中 `audience` 与目标 resource server 不匹配。
2. 请求缺少 `request_canonical_digest` 或 hash 不覆盖 `principal_id`、`device_id?`、`requested_scope` 与 `audience`。
3. 请求的 `expires_at` 超过 Auth Server 声明的 session grant TTL 上限。
4. Auth Server 在 `development_mode=true` 时尝试把 `cx.profile.auth_server.v1` 放入 `verified_profiles[]`。

Expected：

- 第 1 步 MUST 拒绝，reason_code 为 `audience_mismatch` 或等价稳定码。
- 第 2 步 MUST 拒绝，reason_code 为 `invalid_proof_binding` 或等价稳定码。
- 第 3 步 MUST 拒绝或收紧到服务器硬上限，并在响应中暴露实际 `expires_at`；不得签发跨多日 session grant。
- 第 4 步 MUST 被 conformance / describe 校验拒绝；development mode 下 `verified_profiles[]` 必须为空。

### 10.6 Vector: Witness Disagreement Quarantine

`vector_id`: `cx.vector.range_completeness.witness_disagreement.v1`

Steps：

1. 两个 witness 对同一 `(realm_id, actor_id, actor_seq)` 给出不同 `event_id` / `event_digest`。
2. 两个 range-completeness attestation 声称同一 `(from_frontier, to_frontier]` scope，但 `root` 不同且无法由不同上界解释。
3. High-assurance peer 只提供 `single_source` attestation 试图解除 backfill completeness gate。

Expected：

- 第 1 / 2 步 MUST 标记 `witness_disagreement` 并 quarantine 对应 range / peer。
- 不得用本地接收顺序、HLC 或最后写入者选择 winner。
- 第 3 步 MUST 保持 pending / stale，不得推进 high-assurance completeness frontier。

### 10.7 Vector: Capability Revoke Downstream Recheck

`vector_id`: `cx.vector.capability.revoke_downstream_recheck.v1`

Steps：

1. Grant G 授权 actor 写入，Event E 的 `refs[role="authorized_by"]` 指向 G。
2. G 派生 child grant C，C 又授权 pending Event P。
3. `cx.capability.revoke{grant_id=G}` accepted。

Expected：

- P MUST fail closed 或 quarantine，reason `grant_revoked_upstream` / `authorized_grant_revoked`。
- Allow cache / policy decision cache 中依赖 G 或 C 的 entry MUST 在同一 reducer transaction 内失效。
- 历史 E 保留审计事实，但后续 snapshot/export 不得把 G 当作当前有效授权。

### 10.8 Vector: Cursor Revoke

`vector_id`: `cx.vector.cursor.revoke_high_assurance.v1`

Steps：

1. 服务签发 stream cursor 并随后接受 `/account/cursor/revoke`。
2. 攻击者重放已撤销 cursor 到 `/account/subscribe?after=`。
3. 攻击者提交篡改过但未撤销的 cursor。

Expected：

- 第 2 步 MUST 返回 `cursor_revoked`，且不推进 to-device ack / subscription position。
- 第 3 步 MUST 返回 `cursor_integrity_invalid`，不得泄露 revocation set 是否命中。

### 10.9 Vector: Device Recovery Lifecycle

`vector_id`: `cx.vector.device_recovery.lifecycle.v1`

Steps：

1. 新设备用过期 `ssk_generation` 提交恢复 proof。
2. 新设备 proof 通过，但未完成 secret storage unlock / MLS Welcome replay。
3. KeyPackage claim 后失败并使可用数量低于 low-watermark。

Expected：

- 第 1 步 MUST 返回 `device_recovery_ssk_generation_mismatch`。
- 第 2 步设备只能处于 `recovery_pending`，不得显示 fully verified。
- 第 3 步 response SHOULD 返回 `available_count` / `low_watermark` / `suggested_publish_count`，claimed package 不得自动放回。

### 10.9.1 Vector: Device Revocation Frontier Binding

`vector_id`: `cx.vector.device.revocation_frontier.v1`

Steps：

1. `cx.device.revoke` 被 principal control stream 接受，payload 携带 `revocation_frontier=[R]`。
2. 攻击者重放该设备在 R 之后签发的 session grant、KeyPackage publish 或 to-device write。
3. 某 E2EE Realm 提交 MLS Remove，但 `governance_binding.membership_frontier` 未覆盖 R，也未覆盖导入 R 的 Realm governance Move。

Expected：

- 第 2 步 MUST fail closed；实现不得用本地布尔缓存替代 `revocation_frontier` 或其后继 view。
- 第 3 步 Remove 不得使 `covered_frontier_cell` 声称已覆盖该设备撤销；后续 E2EE message Move 仍必须被 `covered_frontier_cell` gate 阻塞。

### 10.10 Vector: Push Wakeup Policy

`vector_id`: `cx.vector.push.wakeup_policy.v1`

Steps：

1. E2EE Realm 声明 `wakeup_default=no_notification`，server 无法评估 client-side mention rule。
2. 设备注册 `client_rule_digest` 与服务端保存 digest 不一致。
3. Realm 使用 `batch_wakeup`，一分钟内大量 client-side unresolved events 到达。

Expected：

- 第 1 步 MUST NOT 发送单事件 blind wakeup。
- 第 2 步 MUST 按更保守策略处理，不得猜测规则内容。
- 第 3 步 MUST 合并为 batch wakeup，仍携带 `evaluation_locus_unresolved=true`。
