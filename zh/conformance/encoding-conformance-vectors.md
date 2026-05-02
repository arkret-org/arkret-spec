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

```json
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
- 若 JSON parser 接收 `1.0` 或 `1e0`，canonicalizer MUST 将其归一到协议允许的唯一 number 表示，或按 profile reject。
- 签名验证 MUST 在 canonicalization 成功后才执行。

实现报告 MUST 明确其 number profile：`integer_only`、`decimal_canonical` 或 `reject_ambiguous_decimal`。

## 6. Vector: Event Digest

向量名称：

```text
cx.vector.encoding.event_digest.v1
```

输入事件，不含 `event_id` 和 `proofs`：

```json
{
  "kind": "cx.message.create",
  "space_version": "1",
  "space_id": "cx:space:01js0ke000000000000000000",
  "actor_id": "did:web:alice.example",
  "actor_seq": 1,
  "created_at": "2026-04-26T00:00:00Z",
  "hlc": "01970e589d21-0004-a13f9c2e",
  "prev_refs": [],
  "auth_refs": [],
  "content": {
    "body": "hello"
  }
}
```

期望 canonical bytes 的 UTF-8 文本表示：

```json
{"actor_id":"did:web:alice.example","actor_seq":1,"auth_refs":[],"content":{"body":"hello"},"created_at":"2026-04-26T00:00:00Z","hlc":"01970e589d21-0004-a13f9c2e","kind":"cx.message.create","prev_refs":[],"space_id":"cx:space:01js0ke000000000000000000","space_version":"1"}
```

期望 digest：

```text
sha256:eb874f42a73755f5e77d3815a9cefa19487d84e12459d9c53766fdd6dc43cc5a
```

判定规则：

- `event_id` MUST 从 redaction 前、去除 `proofs` 后的 canonical event bytes 派生。
- 实现 MUST NOT 把 transport envelope、HTTP header、Sync Service metadata、local receive time 放入 event digest。
- 同一事件在不同 Events API、Sync Service 或 Index 上 MUST 得到相同 digest。

## 7. Vector: Event Batch Receipt Digest

向量名称：

```text
cx.vector.encoding.event_batch_receipt_digest.v1
```

输入 Event Batch Receipt，不含 proof：

```json
{
  "schema": "cx.schema.event_batch_receipt.v1",
  "receipt_id": "cx:receipt:01js0rc000000000000000000",
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
{"created_at":"2026-04-26T00:00:00Z","events":["sha256:1111111111111111111111111111111111111111111111111111111111111111"],"frontier":{"actor_seq":1,"event_hash":"sha256:1111111111111111111111111111111111111111111111111111111111111111"},"issuer":"did:web:alice.example","receipt_id":"cx:receipt:01js0rc000000000000000000","schema":"cx.schema.event_batch_receipt.v1","scope":{"actor_id":"did:web:alice.example"},"type":"event_batch_receipt"}
```

期望 digest：

```text
sha256:1998dbca1e9d438ec05f0631167aed3a101c35fdbbd49e25a56465f40c1ebc6f
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

## 10. Vector: Cursor Opaqueness

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

## 11. Vector: Encrypted Envelope Digest

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
- 实现 MUST NOT 省略路由和解密所需的 cleartext metadata，否则 sync service / index 无法安全去重和审计密文 envelope。

## 12. 覆盖矩阵

| 向量 | Minimal Client | Full Client | E2EE Client | Events API | Principal Server | Index Node |
| --- | --- | --- | --- | --- | --- | --- |
| `cx.vector.encoding.canonical_json.basic.v1` | MUST | MUST | MUST | MUST | MUST | MUST |
| `cx.vector.encoding.canonical_json.nested.v1` | MUST | MUST | MUST | MUST | MUST | MUST |
| `cx.vector.encoding.reject_noncanonical_numbers.v1` | MUST | MUST | MUST | MUST | SHOULD | MUST |
| `cx.vector.encoding.event_digest.v1` | SHOULD | MUST | MUST | MUST | SHOULD | MUST |
| `cx.vector.encoding.event_batch_receipt_digest.v1` | MAY | SHOULD | SHOULD | SHOULD | MAY | MAY |
| `cx.vector.encoding.signature_binding_payload.v1` | MUST | MUST | MUST | MUST | MUST | MUST |
| `cx.vector.encoding.hlc_order.v1` | MUST | MUST | MUST | MUST | SHOULD | MUST |
| `cx.vector.encoding.cursor_opaque.v1` | MUST | MUST | MUST | MAY | SHOULD | MUST |
| `cx.vector.encoding.encrypted_envelope_digest.v1` | MAY | SHOULD | MUST | MAY | MUST | SHOULD |

## 13. Crypto Fixture 要求

自动化 conformance suite MUST 增加独立 fixture：

- Ed25519 public key / private test key
- detached JWS signature
- DID Document verification method
- key rotation 后的 signature verification
- redaction 前后 event digest 验证
- malformed UTF-8 / duplicate key parser rejection

测试私钥只能用于公开测试向量，不得被任何生产实现信任。生产 profile MUST 拒绝测试 DID、测试 key id 或测试 trust domain。
