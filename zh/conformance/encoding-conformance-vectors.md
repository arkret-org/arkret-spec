# Encoding Conformance Vectors

## 1. 目标

本文定义 Contrix canonical JSON、hash、event digest、event-batch receipt digest、signature binding、HLC、cursor 与 encrypted envelope digest 的一致性测试向量。

这些向量是 `encoding.md` 的测试化补充。实现只要在 hash 输入、字段排序、签名绑定或时间排序上产生差异，就不能声称与 Contrix v1 编码 profile 互操作。

## 2. 通用规则

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

## 3. Vector: Canonical JSON Basic

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

## 4. Vector: Canonical JSON Nested

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

## 5. Vector: Reject Non-Canonical Numbers

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

## 5.1 Vector: Reject Malformed JSON

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

## 6. Vector: Event Digest

向量名称：

```text
cx.vector.encoding.event_digest.v1
```

输入事件，不含 `proofs` 和 `unsigned`，但包含稳定 `event_id`：

```json
{
  "event_id": "cx:event:01js0ev0000000000000000000",
  "kind": "cx.message.create",
  "space_version": "1",
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
{"actor_id":"did:web:alice.example","actor_seq":1,"auth_refs":[],"created_at":"2026-04-26T00:00:00Z","event_id":"cx:event:01js0ev0000000000000000000","hlc":"01970e589d21-0004-a13f9c2e","kind":"cx.message.create","payload":{"content":{"body":"hello","type":"cx.content.text"},"flow_id":"cx:flow:01js0ke0000000000000000000"},"prev_refs":[],"space_id":"cx:space:01js0ke0000000000000000000","space_version":"1"}
```

期望 digest：

```text
sha256:d43b763f81bfe512bd7077701b7ee5e98fea54b756fb495556a98617ac00ff7d
```

判定规则：

- event digest / proof `payload_hash` MUST 从 redaction 前、去除 `proofs` 与 `unsigned` 后的 canonical event bytes 派生；`event_id` 是稳定 `cx:event:*` typed ID，必须进入 digest，但不替代 digest。
- 实现 MUST NOT 把 transport envelope、HTTP header、Sync Service metadata、local receive time 放入 event digest。
- 同一事件在不同 Events API 或 Sync Service 上 MUST 得到相同 digest。

## 7. Vector: Event Batch Receipt Digest

向量名称：

```text
cx.vector.encoding.event_batch_receipt_digest.v1
```

输入 Event Batch Receipt，不含 proof：

```json
{
  "schema": "cx.schema.event_batch_receipt.v1",
  "receipt_id": "cx:receipt:01js0rc0000000000000000000",
  "type": "event_batch_receipt",
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
{"created_at":"2026-04-26T00:00:00Z","events":["sha256:1111111111111111111111111111111111111111111111111111111111111111"],"frontier":{"actor_seq":1,"event_hash":"sha256:1111111111111111111111111111111111111111111111111111111111111111"},"issuer":"did:web:alice.example","receipt_id":"cx:receipt:01js0rc0000000000000000000","schema":"cx.schema.event_batch_receipt.v1","scope":{"actor_id":"did:web:alice.example"},"type":"event_batch_receipt"}
```

期望 digest：

```text
sha256:1a0b0bb8198a6b5adaba2e31f8aa6d9cac1fd94e2db6d41519414d6bca00162d
```

失败条件：

- `events` 数组被排序或去重后再 hash。
- proof 字段被包含进 receipt digest。
- `issuer`、`scope`、`frontier`、`schema` 或 `type` 被排除在 digest 外。
- `receipt_id` 大小写被实现私自改写。

## 8. Vector: Signature Binding Payload

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

## 9. Vector: HLC Order

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

## 10. Vector: HLC Logical Overflow

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

## 11. Vector: Cursor Opaqueness

向量名称：

```text
cx.vector.encoding.cursor_opaque.v1
```

输入 cursor：

```text
cx:cursor:eyJxdWVyeV9oYXNoIjoic2hhMjU2OmFiYyIsImxhc3RfZXZlbnRfaWQiOiJldnRfMSJ9
```

期望客户端行为：

- 客户端 MUST 把 cursor 当作不透明字符串保存和回传。
- 客户端 MUST NOT 依赖 base64url 解码后的内部字段。
- 服务端 MAY 改变 cursor 内部编码，只要同一 query/session 下 cursor 仍按 API contract 可用。

失败条件：

- 客户端解析 `last_event_id` 后自行构造下一页请求。
- 客户端在 cursor 解码失败时拒绝整个协议，而不是按 opaque token 处理。

## 12. Vector: Encrypted Envelope Digest

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

## 13. Vector: Encrypted Envelope AAD Event Type Compatibility

向量名称：

```text
cx.vector.encoding.encrypted_envelope_aad_event_type_compat.v1
```

legacy raw AAD 输入：

```json
{
  "space_id": "cx:space:01js0sp0000000000000000000",
  "event_type": "cx.message.create"
}
```

期望归一化 AAD：

```json
{"event_kind":"cx.message.create","space_id":"cx:space:01js0sp0000000000000000000"}
```

期望 `aad_digest`：

```text
sha256:ac98e298527e5b35be6afb7eba7e2e788922c55daa1e37eeb554d05a2cc21e7d
```

判定规则：

- `space_version=1` receiver MAY 在 schema validation 前把只有 `event_type` 的 legacy raw AAD 归一为 `event_kind`。
- canonical AAD digest MUST 使用归一化后的 `event_kind`，不得保留 `event_type`。
- raw AAD 同时包含 `event_kind` 与不同值的 `event_type` 时 MUST reject。
- `space_version>=2` receiver MUST reject 任何包含 `event_type` 的 raw envelope。

## 14. 覆盖矩阵

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
| `cx.vector.encoding.encrypted_envelope_aad_event_type_compat.v1` | MAY | SHOULD | MUST | MAY | MUST |

## 15. Crypto Fixture 要求

自动化 conformance suite MUST 加载 `artifacts/fixtures/crypto-signature-fixture.json`（中文镜像：`zh/conformance/fixtures/crypto-signature-fixture.json`）。该 fixture 固定了 `cx.vector.encoding.crypto.ed25519_detached_jws.v1`：

- Ed25519 public key / private test key
- detached JWS signature
- DID Document verification method
- canonical Event payload、`payload_hash`、proof binding object、detached JWS signing input 和 expected rejection 条件

后续 conformance suite 仍应增加扩展 fixture：

- key rotation 后的 signature verification
- redaction 前后 event digest 验证

测试私钥只能用于公开测试向量，不得被任何生产实现信任。生产 profile MUST 拒绝测试 DID、测试 key id 或测试 trust domain。
