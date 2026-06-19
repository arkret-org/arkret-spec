---
title: Conformance Vectors
status: candidate
normative: true
stability: v1
updated: 2026-06-11
---

本文是 v1 conformance 测试向量的人类阅读入口，按域分组呈现核心 normative steps。完整 active vector 集合的机器真相源是 `artifacts/registry/vector-registry.json`；测试 runner MUST 从 registry 的 `source_refs` 加载本文件、领域文档与 fixture，不得假定本文件正文穷尽列出所有 vector id。

1. Encoding & Crypto（canonical JSON、digest、signature binding、HLC、cursor、encrypted envelope）
2. CBA · Lattice（DataEvent acceptance、Control Move Seal finality、cas_register、Seal DAG）
3. Redaction（约束与可见性）
4. Capability（delegation、revoke、approval）
5. Sync（client sync、pagination、snapshot、MLS epoch backfill）
6. Space Lifecycle
7. Member Delivery Binding
8. Handle
9. Security Closure
10. Service Closure
11. Personal Agent & Sidecar
12. Media Service Binding
13. History Visibility / Preview / History Sharing
14. Encryption Floor Ratchet
15. Moderation / Policy Server / Key Backup / Federation Ingress

可执行向量数据集位于 [`spec/v1/artifacts/fixtures/`](../../artifacts/fixtures/)；
本文档把对应规范条款与文件入口集中呈现，便于一致性测试 runner 引用。
所有 `ck.vector.*` 标识符的机器索引位于 [`vector-registry.json`](../../artifacts/registry/vector-registry.json)；新增、删除或重命名向量时 MUST 同步更新该 registry，并通过 `tools/artifact_pipeline.py check` 的闭包校验。领域文档中定义的向量（例如 Directory / PSI / Search）只要在 registry `source_refs` 中登记，即属于同一 conformance suite。

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [normative-language.md](./normative-language.md) 解释；仅大写形式具规范约束力。

## 1. Encoding & Crypto Vectors

### 1.1 目标

本文定义 Cokret canonical JSON、hash、event digest、event-batch receipt digest、signature binding、HLC、cursor 与 encrypted envelope digest 的一致性测试向量。

这些向量是 `encoding.md` 的测试化补充。实现只要在 hash 输入、字段排序、签名绑定或时间排序上产生差异，就不能声称与 Cokret v1 编码 profile 互操作。

### 1.2 通用规则

向量名称使用：

```text
ck.vector.encoding.<name>.v1
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
ck.vector.encoding.canonical_json.basic.v1
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
ck.vector.encoding.canonical_json.nested.v1
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

- object key MUST 在每一层独立按 UTF-16 code unit 升序排序；补充平面字符按 surrogate pair 参与比较。
- array item order MUST 保持输入顺序。
- string value MUST NOT 因为 key 排序被改写。

### 1.4.1 Vector: Canonical JSON UTF-16 Supplementary Keys

向量名称：

```text
ck.vector.encoding.canonical_json.utf16_supplementary_order.v1
```

该向量使用至少两个 key：一个位于补充平面、一个位于 BMP 高位区。实现 MUST 按 UTF-16 code unit 排序，而不是按 Unicode scalar value / code point 排序。期望 canonical bytes 以 `encoding-fixture.json` 中同名 vector 的 `expected_canonical_bytes_utf8` 为准。

### 1.5 Vector: Reject Non-Canonical Numbers

向量名称：

```text
ck.vector.encoding.reject_noncanonical_numbers.v1
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
- v1 签名对象的 number 字段 MUST 是 JSON integer；`1.0`、`1e0`、任何 fractional / exponent decimal spelling 以及无法证明为整数的 number MUST reject，而不是归一化后继续验签。
- 签名验证 MUST 在 canonicalization 成功后才执行。

实现报告 MUST 明确其 number profile。声明任何包含 `confidence`、`progress` 或其他比例 / 置信度 / 进度语义的 profile 时，wire 字段 MUST 使用整数 + 显式 scale（如 `_basis_points`、`_x1000`），不得要求或声明 `decimal_canonical`。

#### 1.5.1 Vector: Reject Malformed JSON

向量名称：

```text
ck.vector.encoding.reject_malformed_json.v1
```

以下输入 MUST 在 canonicalization 前或 canonicalization 阶段失败，不能进入签名验证、hash 计算或 reducer：

- malformed UTF-8。
- JSON object duplicate key，例如同一层同时出现两个 `"event_id"`。
- lone surrogate 或无法唯一解释的转义字符串。
- 非标准 JSON literal，例如 `NaN`、`Infinity`。
- parser 接收但 canonicalizer 无法唯一序列化的 number。

判定规则：

- duplicate key MUST NOT 按 parser 默认行为静默覆盖。
- malformed string MUST NOT 被替换成 U+FFFD 后继续签名。
- reject 结果 MUST 可审计；canonical JSON 解析失败 MUST 使用单一错误码 `invalid_canonical_json`（不再在 `schema_violation` / `invalid_encoding` 间三选一），以保证跨实现错误码一致、可被 conformance runner 断言。

#### 1.5.2 Vector: Reject Duplicate Key

向量名称：

```text
ck.vector.encoding.reject_duplicate_key.v1
```

输入 bytes（UTF-8 文本，未经 parser 去重；同一层出现两个 `event_id`）：

```text
{"event_id":"ck:event:019640ed-8000-7000-8000-000000000000","event_id":"ck:event:019640ed-8000-7000-8000-000000000001"}
```

期望：

- 实现 MUST 在 canonicalization 阶段 reject，错误码 `invalid_canonical_json`。
- 实现 MUST NOT 采用 “最后一个 key wins” 或 “第一个 key wins” 后继续 canonicalize、hash 或验签（见 [encoding.md](./encoding.md) §2）。

失败条件：

- parser 静默保留其中一个 `event_id` 并产出合法 canonical bytes。
- reject 但错误码不是 `invalid_canonical_json`。

#### 1.5.3 Vector: Reject Non-NFC String

向量名称：

```text
ck.vector.encoding.reject_non_nfc_string.v1
```

输入对象（`display_name` 使用 decomposed 序列 `U+0065 U+0301`，即 `e` + combining acute，而非 precomposed `U+00E9` `é`）：

```json
{
  "display_name": "café"
}
```

> 注（informative）：上方 `é` 的 wire bytes MUST 为 NFD 形态 `65 cc 81`（`e` + `U+0301`）；测试 runner 按 raw bytes 注入，加载时 MUST NOT 被编辑器隐式 NFC 化。

期望：

- receiver MUST 检测到 string value 不是 NFC 形态，并以 `schema_violation` 拒绝（见 [encoding.md](./encoding.md) §2.1 NFC 收紧规则）。
- receiver MUST NOT 在 verify 阶段做隐式 NFC 化后继续签名/hash 比较。

失败条件：

- receiver 隐式把 `65 cc 81` 归一化为 `c3 a9` 后接受。
- 接受非 NFC bytes 进入 event digest 或 proof binding。

#### 1.5.4 Vector: Reject U+FEFF Injection

向量名称：

```text
ck.vector.encoding.reject_feff_injection.v1
```

输入对象（`title` string value 内部注入一个 `U+FEFF` zero-width no-break space，wire bytes 含 `ef bb bf`）：

```json
{
  "title": "he﻿llo"
}
```

> 注：`﻿` 仅为本文档可读表示；测试向量的 wire bytes MUST 在 `he` 与 `llo` 之间直接含 `ef bb bf` 三字节。stream 起始处的 UTF-8 BOM 同样适用本向量。

期望：

- receiver MUST 拒绝任何出现 `U+FEFF` 的输入（无论位于 stream 起始还是 string value 内部），错误码 `schema_violation`（见 [encoding.md](./encoding.md) §2：`U+FEFF` 在 v1 canonical JSON 中一律拒绝）。
- receiver MUST NOT 静默剥离 `U+FEFF` 后继续 canonicalize。

失败条件：

- receiver strip BOM / `U+FEFF` 后产出合法 canonical bytes 并验签。
- 把 `U+FEFF` 当作普通可见字符纳入 digest 输入。

### 1.6 Vector: Event Digest

向量名称：

```text
ck.vector.encoding.event_digest.v1
```

输入事件，不含 `proofs` 和 `unsigned`，但包含稳定 `event_id`：

```json
{
  "event_id": "ck:event:019640ed-8000-7000-8000-000000000000",
  "kind": "ck.message.create",
  "realm_id": "ck:realm:01964137-0000-7000-8000-000000000000",
  "actor_id": "did:web:alice.example",
  "actor_seq": 1,
  "created_at": "2026-04-26T00:00:00Z",
  "hlc": "01970e589d21-0004-a13f9c2e",
  "prev_refs": [],
  "refs": [],
  "effects": [
    {
      "cell": "ck:cell:message:019640ed-8000-7000-8000-000000000000",
      "op": {
        "kind": "append",
        "value": {
          "strand_id": "ck:strand:01964137-0000-7000-8000-000000000000",
          "message_id": "ck:message:019640ed-8000-7000-8000-000000000000",
          "track_name": "discussion"
        }
      }
    }
  ],
  "seal_ref": "ck:seal:sha256:2222222222222222222222222222222222222222222222222222222222222222",
  "auth_context": {
    "did": "did:web:alice.example",
    "key_id": "device-1",
    "key_epoch": 1,
    "capability_refs": [
      "ck:grant:0196410c-0000-7000-8000-000000000000"
    ]
  },
  "payload": {
    "strand_id": "ck:strand:01964137-0000-7000-8000-000000000000",
    "track_name": "discussion",
    "message_id": "ck:message:019640ed-8000-7000-8000-000000000000",
    "content": {
      "kind": "ck.content.text",
      "body": "hello"
    }
  }
}
```

期望 canonical bytes 的 UTF-8 文本表示：

```json
{"actor_id":"did:web:alice.example","actor_seq":1,"auth_context":{"capability_refs":["ck:grant:0196410c-0000-7000-8000-000000000000"],"did":"did:web:alice.example","key_epoch":1,"key_id":"device-1"},"created_at":"2026-04-26T00:00:00Z","effects":[{"cell":"ck:cell:message:019640ed-8000-7000-8000-000000000000","op":{"kind":"append","value":{"strand_id":"ck:strand:01964137-0000-7000-8000-000000000000","message_id":"ck:message:019640ed-8000-7000-8000-000000000000","track_name":"discussion"}}}],"event_id":"ck:event:019640ed-8000-7000-8000-000000000000","hlc":"01970e589d21-0004-a13f9c2e","kind":"ck.message.create","payload":{"content":{"body":"hello","kind":"ck.content.text"},"strand_id":"ck:strand:01964137-0000-7000-8000-000000000000","message_id":"ck:message:019640ed-8000-7000-8000-000000000000","track_name":"discussion"},"prev_refs":[],"realm_id":"ck:realm:01964137-0000-7000-8000-000000000000","refs":[],"seal_ref":"ck:seal:sha256:2222222222222222222222222222222222222222222222222222222222222222"}
```

期望 digest：

```text
sha256:2a98c4056c6c7a251b2c410530d796ad5df3858097b0926b4748a98cb0e8eea3
```

判定规则：

- event digest / proof `event_digest` MUST 从 redaction 前、去除 `proofs` 与 `unsigned` 后的 canonical event bytes 派生；`event_id` 是稳定 `ck:event:*` typed ID，必须进入 digest，但不替代 digest。
- 实现 MUST NOT 把 transport envelope、HTTP header、Sync Service metadata、local receive time 放入 event digest。
- 同一事件在不同 Events API 或 Sync Service 上 MUST 得到相同 digest。

### 1.7 Vector: Event Batch Receipt Digest

向量名称：

```text
ck.vector.encoding.event_batch_receipt_digest.v1
```

输入 Event Batch Receipt，不含 proof：

```json
{
  "schema": "ck.schema.event_batch_receipt.v1",
  "receipt_id": "ck:receipt:01964186-0000-7000-8000-000000000000",
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
{"created_at":"2026-04-26T00:00:00Z","events":["sha256:1111111111111111111111111111111111111111111111111111111111111111"],"frontier":{"actor_seq":1,"event_digest":"sha256:1111111111111111111111111111111111111111111111111111111111111111"},"issuer":"did:web:alice.example","receipt_id":"ck:receipt:01964186-0000-7000-8000-000000000000","receipt_scope":{"actor_id":"did:web:alice.example"},"schema":"ck.schema.event_batch_receipt.v1"}
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
ck.vector.encoding.signature_binding_payload.v1
```

签名前的 binding object（其中 `event_digest` 仅为占位值，取自 §1.3 `ck.vector.encoding.canonical_json.basic.v1` 的 digest `sha256:43258cff...`，用于固定本向量的 binding canonical 形态；它**不是** §1.6 真实 event digest `sha256:297487d8...`。本向量只断言 binding object 的 canonical bytes 与 digest，不要求该 `event_digest` 与任一具体 event 一致）：

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
ck.vector.encoding.hlc_order.v1
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
ck.vector.encoding.hlc_logical_overflow.v1
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
- 重试或等待期间，事件的 `prev_refs`、`refs[role=authorized_by]` 与 `actor_seq` 约束 MUST NOT 被放松。

失败条件：

- 逻辑计数器回绕到更小值并继续发出事件。
- 通过伪造更大的 wall clock skew 逃避 overflow，同时破坏本地 HLC 单调性或 causal 约束。
- 消费者把上述回绕值当作正常排序输入接受并推进 accepted history。

#### 1.10.1 Vector: Reject Malformed HLC Format

向量名称：

```text
ck.vector.encoding.reject_malformed_hlc.v1
```

实现 MUST 用正则 `^[0-9a-f]{12}-[0-9a-f]{4}-[0-9a-f]{8}$` 验证 HLC 格式（见 [encoding.md](./encoding.md) §7.2），并额外拒绝 `unix_ms_hex > ffffffffffff` 的物理时间溢出值。下列每个 case 都 MUST 被拒绝：

| case | 输入 HLC | 违反点 | 期望错误码 |
| --- | --- | --- | --- |
| `physical_overflow` | `1000000000000-0004-a13f9c2e` | `unix_ms_hex` 13 位（> `ffffffffffff`），物理时间溢出 | `schema_violation` |
| `logical_too_short` | `01970e589d21-004-a13f9c2e` | `logical_hex` 仅 3 位（必须恰 4 位） | `schema_violation` |
| `logical_too_long` | `01970e589d21-00004-a13f9c2e` | `logical_hex` 5 位（必须恰 4 位） | `schema_violation` |
| `node_too_short` | `01970e589d21-0004-a13f9c2` | `node_id_hash` 仅 7 位（必须恰 8 位） | `schema_violation` |
| `node_too_long` | `01970e589d21-0004-a13f9c2e0` | `node_id_hash` 9 位（必须恰 8 位） | `schema_violation` |
| `uppercase_hex` | `01970E589D21-0004-A13F9C2E` | 含大写十六进制（正则仅允许 `0-9a-f`） | `schema_violation` |

期望：

- 每个 case 实现 MUST reject 并报告对应 case；MUST NOT 在 verify 阶段隐式截断、补零或大小写折叠后接受。
- `unix_ms_hex` 恰 12 位、`logical_hex` 恰 4 位、`node_id_hash` 恰 8 位且全部为小写 hex 的 HLC（如 `01970e589d21-0004-a13f9c2e`）MUST accept，作为对照正样本。

失败条件：

- 实现把 `00004` 解析为 `0004` 后接受。
- 实现把大写 hex 归一化为小写后接受（HLC 是 wire 字符串，MUST NOT 在比较前改写）。
- 实现接受 13 位 `unix_ms_hex` 并截断到 12 位。

### 1.11 Vector: Cursor Opaqueness

向量名称：

```text
ck.vector.encoding.cursor_opaque.core.v1
```

输入 cursor（schema-valid v1 core wire 形态；body 是 stateful opaque handle `{v,purpose,t,x,h}`）：

```text
ck:cursor:eyJoIjoiYWJjZGVmZ2hpamtsbW5vcHFyc3R1diIsInB1cnBvc2UiOiJzdHJlYW0iLCJ0IjoiMjA5OS0xMi0zMFQyMzo1OTo1OVoiLCJ2IjoiMSIsIngiOjQxMDI0NDQ3OTkwMDB9
```

cursor base64url 解码后对应 canonical JSON：

```text
{"h":"abcdefghijklmnopqrstuv","purpose":"stream","t":"2099-12-30T23:59:59Z","v":"1","x":4102444799000}
```

期望客户端行为：

- 客户端 MUST 把 cursor 当作不透明字符串保存和回传。即使 cursor 的内部结构是 `encoding.md` §8.2 规定的合法 stateful handle 形态，客户端 SDK / 应用层 MUST NOT 解析它的内部字段来构造请求。
- 客户端 MUST NOT 依赖 base64url 解码后的 `h` handle、`x` 过期字段或其它内部字段构造下一页请求；这些字段只属于 issuing service。
- 服务端 MAY 改变 cursor 内部编码或字段集合，只要同一 query/session 下 cursor 仍按 API contract 可用。
- 服务端 MUST 在收到该 cursor 时，按 [`encoding.md`](./encoding.md) §8.3 校验 `v ∈ supported_versions`、`purpose`、`x`、core schema 形态和 `h` handle binding；语法失败返回顶层 `invalid_param`（reason `invalid_cursor`），过期返回 `cursor_expired`，handle lookup / binding 失败返回 `cursor_integrity_invalid`（见 `error-code-registry.json`）。

失败条件：

- 客户端解析 `h` / `x` 后自行构造下一页请求或修改 cursor 内容。
- 客户端在 cursor 解码失败时拒绝整个协议，而不是按 opaque token 处理。
- 服务端接受缺少 `h` 的 cursor body。

### 1.12 Vector: Encrypted Envelope Digest

向量名称：

```text
ck.vector.encoding.encrypted_envelope_digest.v1
```

`payload_metadata` canonical bytes 的 UTF-8 文本表示：

```json
{"aad":{"event_kind":"ck.message.create","event_ref_digest":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","realm_id":"ck:realm:0196419b-0000-7000-8000-000000000000"},"aad_visibility_event_id":"routing_digest","content_type":"application/json","epoch":12,"group_id":"Z3JvdXAtMDAx","key_ref":{"algorithm":"MLS","group_state_ref":"ck:event:01964148-0000-7000-8000-000000000000"},"scheme":"mls-rfc9420","version":"1.0"}
```

`ciphertext` 的 base64url wire 值与解码后 UTF-8 测试表示：

```text
Y2lwaGVydGV4dC1leGFtcGxlLTAwMQ
ciphertext-example-001
```

期望 digest：

```text
sha256:fa4d70fb617f745133f88062dace64f909c370027191f6f8c04b143c3258a4a8
```

判定规则：

- digest 输入 MUST 为 `canonical_json(payload_metadata) || base64url_decode(ciphertext)`。
- 实现 MUST NOT hash 明文 payload。
- 实现 MUST NOT 省略路由和解密所需的 `payload_metadata` 字段，否则 Sync Service 无法安全去重和审计密文 envelope。

### 1.13 覆盖矩阵

| 向量 | Minimal Client | Full Client | E2EE Client | Events API | Principal Server |
| --- | --- | --- | --- | --- | --- |
| `ck.vector.encoding.canonical_json.basic.v1` | MUST | MUST | MUST | MUST | MUST |
| `ck.vector.encoding.canonical_json.nested.v1` | MUST | MUST | MUST | MUST | MUST |
| `ck.vector.encoding.canonical_json.utf16_supplementary_order.v1` | MUST | MUST | MUST | MUST | MUST |
| `ck.vector.encoding.reject_noncanonical_numbers.v1` | MUST | MUST | MUST | MUST | SHOULD |
| `ck.vector.encoding.reject_malformed_json.v1` | MUST | MUST | MUST | MUST | MUST |
| `ck.vector.encoding.reject_duplicate_key.v1` | MUST | MUST | MUST | MUST | MUST |
| `ck.vector.encoding.reject_non_nfc_string.v1` | MUST | MUST | MUST | MUST | MUST |
| `ck.vector.encoding.reject_feff_injection.v1` | MUST | MUST | MUST | MUST | MUST |
| `ck.vector.encoding.event_digest.v1` | SHOULD | MUST | MUST | MUST | SHOULD |
| `ck.vector.encoding.event_batch_receipt_digest.v1` | MAY | SHOULD | SHOULD | SHOULD | MAY |
| `ck.vector.encoding.signature_binding_payload.v1` | MUST | MUST | MUST | MUST | MUST |
| `ck.vector.encoding.crypto.ed25519_detached_jws.v1` | MUST | MUST | MUST | MUST | MUST |
| `ck.vector.encoding.hlc_order.v1` | MUST | MUST | MUST | MUST | SHOULD |
| `ck.vector.encoding.reject_malformed_hlc.v1` | MUST | MUST | MUST | MUST | SHOULD |
| `ck.vector.encoding.cursor_opaque.core.v1` | MUST | MUST | MUST | MAY | SHOULD |
| `ck.vector.encoding.encrypted_envelope_digest.v1` | MAY | SHOULD | MUST | MAY | MUST |

### 1.14 Crypto Fixture 要求

自动化 conformance suite MUST 加载 `spec/v1/artifacts/fixtures/crypto-signature-fixture.json`。该 fixture 固定了 `ck.vector.encoding.crypto.ed25519_detached_jws.v1`：

- Ed25519 public key / private test key
- detached JWS signature
- DID Document verification method
- canonical Event payload、`event_digest`、proof binding object、detached JWS signing input 和 expected rejection 条件

后续 conformance suite 仍应增加扩展 fixture：

- key rotation 后的 signature verification
- redaction 前后 event digest 验证

测试私钥只能用于公开测试向量，不得被任何生产实现信任。生产 profile MUST 拒绝测试 DID、测试 key id 或测试 trust domain。

### 1.15 Cross-Domain Vector Seals

以下 vector id 的具体断言由对应领域正文定义；本节提供 conformance registry 的统一锚点：

- `ck.vector.media.aead_nonce_sender_domain_collision.v1`
- `ck.vector.media.aead_nonce_counter_replay.v1`
- `ck.vector.media.aead_nonce_random_rejected.v1`
- `ck.vector.lattice.mv_register_join.v1`
- `ck.vector.lattice.counter_join.v1`
- `ck.vector.lattice.ordered_log_join.v1`
- `ck.vector.circle.directory_visibility_realm_members_indistinguishable.v1`
- `ck.vector.calendar.rsvp_occurrence_key.v1`

## 2. CBA · Lattice Vectors

> 来源：`cba-lattice-fixture.json`。

### 2.1 目标

本节把 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) 的 CBA、Seal 与 Lattice 规则转成可复现向量。实现必须对每个向量输出：

- `vector_id`
- DataEvent / Control Move 验证结果
- Seal 应用结果
- `query(cell)` 的 value 或 structured bottom
- `state_root` / inclusion proof（当 fixture 要求时）

### 2.2 Vector: DataEvent 无 Seal Finality 即可本地接受

向量名称：

```text
ck.vector.cba_lattice.data_event_accepts_without_seal_finality.v1
```

输入：

- DataEvent 携带 `effects[]`、`seal_ref` 与 `auth_context`，不携带 `seal_basis` 或 `preconditions`。
- `seal_ref` 指向的 Seal view 可验证，actor chain / signature / capability 均通过。

期望：

- DataEvent 进入 `data_local` / `data_seen` 状态并可本地投影。
- 不需要等待该 DataEvent 出现在任何 Seal 覆盖集。
- Seal 只能通过 `data_event_set_root` / `data_view_root` 提供观察性证明，不赋予数据面 sealed finality。

### 2.3 Vector: 观察性 Data Root 不产生 Sealed 状态

向量名称：

```text
ck.vector.cba_lattice.data_event_observation_does_not_seal.v1
```

输入：

- Seal 携带 `data_event_set_root`，该 root 包含某 DataEvent digest。
- 同一 Seal 的 `delta[]` 与递归覆盖集不包含该 DataEvent digest。

期望：

- DataEvent 的查询等级最多为 `data_observed`，不得升级为 `control_sealed`。
- 客户端不得用观察性 data root 满足 Control Move `seal_basis` 或治理 freshness。
- `data_observed` 可用于可用性、range completeness 或轻客户端提示，但不是控制面 finality。

### 2.4 Vector: Control Move 必须有 Basis 且由 Seal 覆盖

向量名称：

```text
ck.vector.cba_lattice.control_move_requires_seal_basis_and_seal.v1
```

输入：

- Control Move 携带 `effects[]`、`seal_basis` 与必要 `preconditions[]`。
- 同形 Control Move 的负向 case 缺少 `seal_basis`，或 `seal_basis.state_root` 与 leaves 重算不一致。

期望：

- 缺 `seal_basis` 或 basis 不一致 MUST `failed_precondition` / `rejected_seal`。
- 通过验证的 Control Move 仍只是 `control_pending`，直到某 Seal 的递归覆盖集覆盖其 digest 并重算控制面 `state_root`。

### 2.5 Vector: 同批提交不推进授权 Basis

向量名称：

```text
ck.vector.cba_lattice.same_batch_does_not_advance_authorization_basis.v1
```

输入：

- 同一 ordered submit batch 中包含 Control Move `M1` 与 `M2`。
- `M2` 的 precondition 只有在读取 `M1` effect 后才成立。
- `M2.seal_basis` 指向 batch 前的 Seal view。

期望：

- `M2` MUST `failed_precondition`。
- 同批只提供传输/原子提交便利，不推进 authorization basis；接收端不得用同批内新 effect 自我满足 precondition。
- 需要依赖 `M1` 的写入必须等待 `M1` 被 accepted Seal 覆盖后重新提交。

### 2.5.1 Vector: MLS Governance Epoch Binding

`vector_id`: `ck.vector.mls.governance_epoch_binding.v1`

Steps：

1. 构造 `ck.mls.commit`，`payload.base_epoch = 41`、`payload.next_epoch = 42`。
2. `payload.governance_binding.previous_epoch = 40` 或 `payload.governance_binding.next_epoch = 43`。
3. 其它 signature、proposal refs、policy root 和 membership frontier 均有效。

Expected：

- Receiver / reducer MUST reject 该 commit，且不得推进 `mls_epoch_cell` 或 `covered_seals_cell`。
- `governance_binding.previous_epoch` / `next_epoch` MUST 与 payload 顶层 epoch 字段一致；不得只相信其中一侧。

### 2.5.2 Vector: MLS Welcome KeyPackage Hash Binding

`vector_id`: `ck.vector.mls.welcome_keypackage_hash.v1`

Steps：

1. KeyPackage claim response 返回 `keypackage_ref=K`、`keypackage_digest=H1`、`capabilities_digest=C`、`ssk_generation=G`。
2. 攻击者提交 `ck.mls.welcome`，顶层 `keypackage_ref=K`，但 `payload.keypackage_digest=H2` 或 `payload.claim_ref.keypackage_digest=H2`。
3. Welcome ciphertext、claim_id、capabilities_digest 和 signature envelope 其它字段均有效。

Expected：

- Receiver MUST reject before decrypting or accepting the Welcome。
- `payload.keypackage_digest`、`payload.claim_ref.keypackage_digest`、claim record `keypackage_digest` 和已发布 `ck.mls.keypackage.payload.keypackage_digest` MUST 全部一致。

### 2.6 Vector: 数据面冲突返回 Bottom 且不选 Winner

向量名称：

```text
ck.vector.cba_lattice.data_plane_conflict_returns_bottom_without_winner.v1
```

输入：

- 两个 DataEvent 并发写同一 `cas_register + bottom=reject` 数据面 cell。
- 两者 `seal_ref` 均有效，但 causal refs 互不可达。

期望：

- `query(cell)` 返回 structured `Bottom{kind="conflict"}`。
- 依赖该 cell 的后续 DataEvent / Control Move MUST `failed_bottom`，直到显式 conflict-recovery event 修复。
- 实现不得用 HLC、actor id、event id 或本地接收顺序选择 winner。

### 2.7 Vector: Seal Delta 排除 DataEvent Digest

向量名称：

```text
ck.vector.cba_lattice.seal_delta_excludes_data_event_digest.v1
```

输入：

- Seal 的 `delta[]` 中混入一个 DataEvent digest。
- 该 DataEvent 可能已在 `data_event_set_root` 中出现。

期望：

- Seal MUST reject。
- `delta[]` 只能包含新纳入覆盖集的控制面 Control Move event digest。
- DataEvent digest 只能进入观察性 roots，不得出现在控制面 Seal 覆盖集。

### 2.8 Vector: Open Set Compaction 保留控制 Roots

向量名称：

```text
ck.vector.cba_lattice.open_set_compaction_preserves_control_roots.v1
```

输入与期望（多 case 矩阵）：

1. **Genesis case**：`predecessor_refs=[]` 仅在 genesis Seal 上合法。
2. **Non-genesis empty predecessors**：`predecessor_refs=[]` 但 `delta[]` 非空 MUST reject。
3. **Multi-leaf Seal view**：`seal_view(leaves)` 是纯本地函数（不需签名、不是新 Seal object、deterministic）。
4. **Signed compaction**：要把多 leaf 持久压缩成单 Seal 必须由合法 notary 签发；否则只能作为 view 使用。
5. **Root preservation**：compaction 后的 `control_event_set_root` 与 `state_root` MUST 等于按 leaves 重算的控制面 roots；`data_event_set_root` / `data_view_root` 若出现，仍只具观察性语义。

### 2.8.1 Vector: Seal canonical bytes 去自引用（normative）

向量名称：

```text
ck.vector.cba_lattice.seal_canonical_no_self_reference.v1
```

输入与期望（多 case 矩阵）：

1. **Base case**：构造 Seal body fields `{realm_id, predecessor_refs, delta, control_event_set_root, state_root, sealed_at, hlc}`；按 [`encoding.md`](../conformance/encoding.md) §2 编码为 `seal_canonical_bytes`；`id = "ck:seal:sha256:" || hex(H(seal_canonical_bytes))`；`notary_signature.payload_digest == H(seal_canonical_bytes)`。Verifier MUST accept。
2. **id-in-canonical-bytes attack**：若 producer 把 `id` 字段也塞进 `seal_canonical_bytes` 重新计算 H，得到的 hash 与原始 `id` 内容不同；verifier 重算后 `digest_mismatch`，MUST reject。该向量证明实现没有把 `id` 当成 transcript field。
3. **sig-in-canonical-bytes attack**：若 producer 把 `notary_signature` 也进入 canonical bytes，`payload_digest` 重算与 `id` 重算都会失败；verifier MUST reject。证明 signature 不签自己。
4. **key reorder attack**：取 valid Seal，把 canonical JSON key 顺序打乱（例如 `delta` 放在 `realm_id` 之前）；canonical JSON 规则（key 字典序）下重新编码 → 与原 bytes 相同 → hash 一致 → accept。若 verifier 未按 canonical 规则重新编码就直接 hash wire bytes，attack 会让 `digest_mismatch` 假阴性。本 case 检查 verifier 走 canonical re-encode，不是按收到的 bytes 直接 hash。
5. **proof injection attack**：取 valid Seal，注入未定义字段 `extra_proof`。`additionalProperties=false` 的 schema 在 (b) 校验阶段就 reject；若实现错误地 allow 之，hash 会变 → `digest_mismatch`。
6. **non-digest delta value attack**：构造 `delta=["not-a-digest"]`；schema `delta[]` items 必须匹配 control-plane `event_digest` (`<algo>:<hex>`)，非 digest 形态 MUST `schema_violation` 立即被拒（早于 hash 校验）。

期望：

- case 1 accept；case 2/3/4/5/6 reject。
- 接收方 verifier 在 reject 时 MUST 返回 `digest_mismatch`（case 2/3/4）、`invalid_signature`（case 3 的签名路径）或 `schema_violation`（case 5/6），不得回退到"prose 形态化"判断。

### 2.9 Vector: state_root 增量重算等价于全量重算

向量名称：

```text
ck.vector.state_root.incremental.v1
```

输入：

- 一个已被接受的 Seal `A0`，其控制面覆盖集写入 N 个 cell（`cell_1 … cell_N`，N ≥ 8）；实现已按 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §4.2.1 缓存 `cell → leaf_digest` 表。
- 一个新的 Seal `A1`（`predecessor_refs=[A0]`），控制面 `delta[]` 仅修改其中 K 个 cell（K ≤ N，包含 K=1 / K=N/2 / K=N 三种 case）。
- 一个 corner-case Seal `A2`：`delta[]` 是空 set（无新 control effect）。
- 一个 schema-evolution case `A3`：`delta[]` 包含一个新 cell（之前从未有过 effect），并删除一个旧 cell 的 effect（通过 lattice 的 ⊥/tombstone 机制）。

期望：

每个 case MUST 同时计算：

- `state_root_incremental`：仅对受影响 cell 重算 leaf_digest 与 Merkle 分支，复用 `A0` 缓存。
- `state_root_full`：丢弃缓存，按 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §4.2.2 从 Seal 覆盖集全量重算所有 cell 的 leaf_digest 与 Merkle root。

判定要求：

- `state_root_incremental == state_root_full` 在所有四个 case 上 MUST 成立，bit-exact。
- 缓存的 `leaf_digest` 表 MUST 在 `apply_seal` 接受 Seal 后更新；保留旧 leaf_digest 导致 next-seal 增量重算偏离全量结果即视为实现 bug。
- A2（空 `delta[]`）情况下 `state_root_incremental` MUST 直接复用 `A0.state_root`；不得因为"没有 cell 可重算"而错误地返回空 Merkle root（`H("")`）或 null。
- A3（新增 cell + 删除旧 cell effect）case 验证两点：(a) 新 cell 的 leaf_digest 进入 sorted leaf 列表（按 `cell_wire` Unicode 升序）；(b) 删除 effect 的 cell 仍以其 `Bottom` 或 tombstone 后的 lattice value 编码 leaf_digest，不被简单从 leaf 列表移除。

失败条件：

- 增量分支只重算到内部 Merkle 节点而不向上传播至 root → root 与 full 不匹配。
- 偶数/奇数边界处理在 incremental 与 full 之间不一致（例如 incremental 路径错误复制最后 leaf 而 full 路径正确"提升"）。
- 受影响 cell 集合按 receive order 而非 `cell_wire` lex order 排序。
- A2 case 下错把 `state_root` 重置为空摘要。

实现 MUST 在 conformance 报告中分别报告四个 case 的 `state_root_incremental` 与 `state_root_full`，并标记 pass / fail。该 vector 验证 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §4.2.3 中"增量与全量必须等价"的要求。

### 2.10 Vector: `ck.strand.tracks.update` 原子 patch

向量名称：

```text
ck.vector.strand_tracks_update.atomic.v1
```

输入：

- 一个已存在 Strand `F0`，`tracks = { "synthesis": { is_primary: true, enabled: true }, "discussion": { is_primary: false, enabled: true } }`。
- Case A — 单字段 patch：一个 `ck.strand.tracks.update` Event，`payload.patch = { "tracks.synthesis.is_primary": { "$op": "set", "value": false }, "tracks.discussion.is_primary": { "$op": "set", "value": true } }`。期望 Strand `tracks` 在单个 Event effect 内原子地把 primary 从 `synthesis` 切到 `discussion`，中间态 MUST NOT 出现"两个 is_primary=true"或"零个 is_primary=true"。
- Case B — 新增 + 启停 + 移除：在 Strand 已含 `tracks.synthesis` / `tracks.discussion` 的基础上，单条 `ck.strand.tracks.update` 同时 (1) 新增 `tracks.review.enabled=true` 子 map (profile 注册的扩展 track)，(2) 把 `tracks.discussion.enabled` 置为 false，(3) 把 `tracks.synthesis.is_primary` 置为 false，(4) 把 `tracks.review.is_primary` 置为 true。
- Case C — invariant 违反：单条 `ck.strand.tracks.update` 把 `tracks.synthesis.is_primary` 与 `tracks.discussion.is_primary` 同时 set 为 `true`。

期望：

- **Case A**: reducer 应用 patch 后，`Strand.tracks.synthesis.is_primary == false` 且 `Strand.tracks.discussion.is_primary == true`；reducer 视角下不存在两次中间 state cell write，cas_register cell 一次 atomic update。
- **Case B**: reducer 接受合并后状态 `{ synthesis: {is_primary: false, enabled: true}, discussion: {is_primary: false, enabled: false}, review: {is_primary: true, enabled: true} }`；中间过程 MUST 在同一 cell update 内完成，不得分裂为 4 个独立 cell write。
- **Case C**: reducer MUST 在 effect 应用前 (cell update 之前) 校验合并后 `tracks` map 至多 1 个 entry `is_primary=true`；不满足 MUST `schema_violation`，整条 Event 拒绝，Strand `tracks` 不发生任何变化。

判定要求：

- patch path 解析 MUST 遵循 [`event-and-patch.md` §4.2`](../models/event-and-patch.md) ABNF grammar；任何 path 形如 `tracks.<name>[key=...]` 的 selector segment MUST `schema_violation`（`tracks` 是 map，不是 unique-key 数组）。
- `ck.strand.tracks.update` 写入的 cell 是 `ck:cell:ck.component.strand.tracks.v1:<strand_id>`（cas_register），reducer 校验合并后 invariant 在 cell update 之前 完成。

失败条件：

- Case A 在 cell update 中间态触发 invariant 校验，把"先把 synthesis 设 false → 此时 0 个 primary"错判为 violation。
- Case B 把 patch 拆分为多个独立 cell write，破坏 atomic 语义（外部读取在中间能看到不一致的 tracks map）。
- Case C 把违反 invariant 的 Event 部分接受（例如设了 enabled 但拒绝 is_primary），破坏 Event-level all-or-nothing 语义。

实现 MUST 在 conformance 报告中分别报告三个 case 的 reducer 输出 cell value 与 invariant violation reason；该 vector 防御 [`strand-and-message.md`](../models/strand-and-message.md) §4.5 step 5 primary 解析规则的边界 case。

### 2.11 Vector: `fsm` 家族 join 幂等与并发冲突

向量名称：

```text
ck.vector.lattice.fsm_join.v1
```

本向量固化 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §5.3.4 `fsm` lattice 的 join 规则：“同一 CBA basis 内相同 `(from,to)` 的重复 transition 是幂等的；同一 `from` 指向不同 `to` 的 sibling transition 返回 ⊥。跨 basis 顺序仅由 causal refs 与 Seal DAG 决定；同一 basis 内不得用 HLC、接收顺序或 actor id 选择状态机 winner。”

输入（cell schema：`fsm`，`bottom=reject`，`parameters.initial_state="invited"`，`allowed_transitions` 含 `(invited,join)`、`(invited,decline)`）：

- **Case A — 幂等收敛**：同一 CBA basis 内两条并发 Event 各自对同一 fsm cell 提交 transition `(from="invited", to="join")`（相同 `(from,to)`，不同 actor / event id / HLC）。
- **Case B — 并发冲突 ⊥**：同一 CBA basis 内两条并发 Event 分别提交 `(from="invited", to="join")` 与 `(from="invited", to="decline")`（同 `from` 不同 `to`）。

期望：

- **Case A**：join 收敛到 `state == "join"`，MUST NOT 返回 ⊥；两个 conformant reducer 以不同输入顺序重放 MUST 得到同一结果。
- **Case B**：join MUST 返回 ⊥；`query(cell)` 返回 structured `Bottom{kind="conflict"}` 诊断。该 cell 配置 `bottom=reject`，后续依赖该 cell 的 Event MUST `failed_bottom`，直到 §8 conflict-recovery 路径修复。
- 两个 case 中实现均 MUST NOT 用 HLC、actor id、event id 或本地接收顺序选择状态机 winner。

失败条件：

- Case A 把幂等重复 transition 错判为冲突返回 ⊥。
- Case B 选出任一 `to` 作为 winner 继续推进，或冲突诊断在两个 reducer 间不一致。
- transition `(from,to)` 不在 `allowed_transitions` 表内却未返回 ⊥ / 未被 validate_op 拒绝。

### 2.12 Vector: `cas_register` 混合 basis（非初始态盲写拒绝）

向量名称：

```text
ck.vector.cba_lattice.cas_mixed_basis.v1
```

本向量固化 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §5.3.3 的 **Basis 强制（normative）**：“cas_register 的 set effect 在目标 cell 的 settled 值为非初始态时，Control Move MUST 携带针对本 cell 的 `head_eq` precondition；DataEvent MUST 通过 causal refs 与 lattice 规则表达同等 CAS 约束。缺失时，receiver MUST 以 `failed_precondition` 拒绝该 effect，并按多 cell 原子性拒绝整个 reducer input，不接受‘无 CAS 强制写’。”

输入（cas_register cell，未声明 `initial_value`，初值 `null`；前置 Seal 已把 settled 值推进到 `v1`，即非初始态）：

- **Case A — 非初始态盲写**：一条 set Event 写入 `v2`，**不带**针对本 cell 的 basis 证明（null basis）。
- **Case B — 正确 basis 收敛**：一条 set Control Move 写入 `v2`，携带 `head_eq: "v1"`（与 settled pre-state 一致）。

期望：

- **Case A**：receiver MUST 以 `failed_precondition` 拒绝整个 Event（多 cell 原子性，不得部分应用其余 effect）；cell 保持 `v1`。若此类 Event 越过验证进入 join（防御性路径），join MUST 返回 ⊥，MUST NOT 把 null-basis 盲写当作合法覆盖。
- **Case B**：Control Move 接受并在被 accepted Seal 覆盖后使 cell 收敛到 `v2`；两个 conformant reducer 以不同输入顺序重放 MUST 得到同一结果。
- “无条件覆盖”语义 MUST 通过 profile 显式注册的专门高权限 event kind 或 §8 conflict-recovery 路径表达，不得通过省略普通 set Control Move 的 `head_eq` 实现。

失败条件：

- Case A 被当作 first set 放行（settled 非初始态时 null basis 仅在 settled == initial 时合法）。
- Case A 在 join 阶段被静默接受为 last-write-wins 覆盖。
- Case B 因实现把 basis 校验错误地提前到与 Case A 相同的拒绝路径而被误拒。

### 2.13 Vector: `ordered_log` issuer 子链 seq 缺口

向量名称：

```text
ck.vector.lattice.ordered_log_gap.v1
```

本向量固化 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §5.3.6 `ordered_log` 的缺口规则：“issuer 子链出现缺口时，缺口后的 entry MUST 保留为 pending / diagnostic 输入，但不得进入 cell value、`state_root` leaf 或授权判断；依赖补齐后按同一规则重算。”

输入（ordered_log cell，`bottom=expose`，cell schema 声明 `parameters.entry_id_field`）：

- **Case A — 缺口存在**：issuer I 的 append entries 以 `issuer_seq ∈ {0, 1, 3}` 到达（seq 2 缺失）。
- **Case B — 缺口补齐后重算**：在 Case A 状态上，seq 2 的 entry 通过 backfill 到达，reducer 重算同一 cell。

期望：

- **Case A**：join 产出的 cell value 仅含 `contiguous_prefix`（seq 0、1）；seq 3 的 entry MUST 作为 `pending_gap` 诊断（`reason=dependency_missing`）暴露，MUST NOT 进入 cell value、`state_root` leaf 或任何授权判断。`bottom` 永不出现（与 §5.1 对照表一致）。
- **Case B**：补齐 seq 2 后，按同一 join 规则确定性重算，cell value 变为 seq 0–3 的完整子链；两个 conformant reducer 以不同到达顺序（先 3 后 2 / 先 2 后 3）重放 MUST 得到 bit-exact 相同的 cell value 与 `state_root` leaf。
- 同一 `(issuer, seq)` 重复 entry MUST 按最小 `entry_id` 去重，不得产生双重 entry。

失败条件：

- Case A 把缺口后的 entry 直接并入 cell value 或 `state_root` leaf。
- Case A 因缺口返回 ⊥ 或阻塞整个 cell（ordered_log 是 `bottom=expose`，并发 append 不阻塞协议判断）。
- Case B 重算结果依赖本地接收顺序，两个 reducer 产出不同的 contiguous prefix。

### 2.14 Vector: auth_context epoch pinning 拒绝过期 key

向量名称：

```text
ck.vector.cba_lattice.auth_context_epoch_pinning_reject.v1
```

本向量固化 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §4.1：verifier MUST NOT 只查"当前 DID 文档"，key / credential epoch 的有效性以 `seal_ref` 时点为准。

输入：

- **Case A — 被撤销 key + 旧 seal_ref**：actor 的 key K 在 Seal `S_r` 被撤销；DataEvent 携带 `auth_context.key_epoch` 指向撤销前 epoch、`seal_ref` 为撤销前 Seal，且 `distance(seal_ref, S_r)` 超过 `revocation_freshness_window`。
- **Case B — 撤销宽限窗口内**：同 Case A 但 `distance(seal_ref, S_r)` 在窗口内。
- **Case C — epoch 与 seal_ref 不符**：`auth_context.key_epoch` 在 `seal_ref` 对应控制面状态下不存在或已被替换。

期望：

- Case A：receiver MUST 拒绝或隐藏（`stale_seal_ref` / `failed_precondition`）。
- Case B：receiver MAY 暂时接受，query grade MUST 标记 `stale`。
- Case C：receiver MUST `failed_precondition`，不得回退到"当前 DID 文档"判定。

失败条件：用当前 DID 文档替代 `seal_ref` 时点判定；Case A 被静默接受；Case B 接受后不降级 grade。

### 2.15 Vector: compaction Seal 节律义务

向量名称：

```text
ck.vector.cba_lattice.seal_compaction_interval_enforced.v1
```

本向量固化 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §6.2 的结构性义务与 [`realm.schema.json`](../../artifacts/schemas/realm.schema.json) `seal_compaction_max_interval_ms`。

输入：

- Realm 声明 `seal_compaction_max_interval_ms = X`。
- **Case A**：notary 在 X 内签发携带 `covered_event_digests[]` 的 compaction Seal,其内容等于递归闭包。
- **Case B**：compaction Seal 的 `covered_event_digests[]` 与 `delta[] ∪ predecessor 覆盖集` 不一致。
- **Case C**：live chain 超过 X 仍无 compaction Seal。

期望：

- Case A：receiver 接受；新 verifier 可从该 Seal 接链 bootstrap,不必走链到 genesis。
- Case B：receiver MUST 拒绝该 Seal（`rejected_seal`）。
- Case C：receiver SHOULD 触发治理健康告警；既有 Seal 仍有效（义务是告警与 bootstrap 退化，不是回滚）。

失败条件：Case B 被接受；Case A 的 bootstrap 仍要求 genesis 全链。

### 2.16 Vector: inclusion list 收录义务

向量名称：

```text
ck.vector.cba_lattice.inclusion_list_obligation.v1
```

本向量固化 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §7.3 与 [`inclusion-list.schema.json`](../../artifacts/schemas/inclusion-list.schema.json)。

输入（multi-signer notary profile）：

- 非 proposer signer 签发 inclusion list，列出持有效 receipt、通过本地 verify 的 Control Move digest D。
- **Case A**：下一 Seal include D。
- **Case B**：下一 Seal 对 D 附 signed-reject。
- **Case C**：下一 Seal 附 D 在 batch pre-state 下 verify_control_move 失败的证明。
- **Case D**：下一 Seal 对 D 三者皆无。
- **Case E**：同一 `(realm_id, signer_id, list_seq)` 出现两份内容不同的 inclusion list。

期望：

- Case A/B/C：Seal 可接受。
- Case D：receiver MUST 拒绝该 Seal（`rejected_seal`，reason=`inclusion_list_violation`）。
- Case E：构成 §7.1 equivocation evidence（list_seq 复用 slot 语义）。
- `single_did` profile 下该机制不可用，实现 MUST NOT 伪造 inclusion list 语义。

失败条件：Case D 的 Seal 被接受；Case E 不产生 fault 证据。

### 2.17 Vector: notary equivocation fault 与 fork quarantine

向量名称：

```text
ck.vector.cba_lattice.notary_fault_equivocation_quarantine.v1
```

本向量固化 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §7.1 与 `ck.notary.fault.equivocation` event kind。

输入：

- signer N 对同一 `(realm_id, notary_seq)` 签出 canonical bytes 不同的 Seal `S_a` / `S_b`。
- 普通成员 M（无任何特殊 capability）提交 `ck.notary.fault.equivocation`，payload 携带 `{signer_id=N, seal_a=S_a, seal_b=S_b}`。

期望：

- 验签 + slot 规则通过即接受该 Control Move（验签即授权,reducer MUST NOT 要求 grant）；fault 记录进入 `ck.component.notary_fault.v1` cell（or_set）。
- fault 记录生效后：N 的后续 Seal MUST 被拒绝；`S_a`、`S_b` 及其后继进入 `fork_quarantine`，普通 joined governance view MUST NOT 纳入；查询依赖该分支时 grade=`forked`。
- 仍有其余合法 signer 时 Realm MUST NOT 整体 pause；无剩余合法 signer 时进入 `notary_paused`，仅 recovery 路径可恢复。
- 两个 Seal 不满足 slot 规则（不同 signer 或不同 seq）时，该 Move MUST `failed_precondition`——合法并发 leaf 不构成 fault。

失败条件：要求提交者持有 capability；fault 后整 Realm 无差别 pause；合法并发 leaf 被误判为 fault。

### 2.18 Vector: threshold forensic attribution 声明

向量名称：

```text
ck.vector.cba_lattice.threshold_forensic_attribution.v1
```

本向量固化 [`realm.schema.json`](../../artifacts/schemas/realm.schema.json) `notary.forensic_attribution` 与 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §7.1 的算术规则。

输入：

- **Case A**：threshold notary,n=5,k=3（2k>n）,`forensic_attribution="quorum_intersection"`。
- **Case B**：n=5,k=3,`forensic_attribution="waived"`。
- **Case C**：n=4,k=2（2k≤n）,`forensic_attribution="quorum_intersection"`。
- **Case D**：threshold notary 缺 `forensic_attribution` 字段。

期望：

- Case A：accept。
- Case B / Case C：reducer MUST 在 `ck.realm.create` 拒绝（取值与 2k>n 算术关系不符）。
- Case D：schema 校验失败（threshold 变体必填该字段）。

失败条件：Case B/C 被接受；Case D 通过 schema 校验。

### 2.19 Vector: CBA 旧词族 hard reject

向量名称：

```text
ck.vector.cba_lattice.rename_family_reject.v1
```

本向量固化 [`migration/renames.json`](../../artifacts/migration/renames.json) `cba_notary_seal_rename` 组的 parser 行为：current v1 parser 对旧词族 MUST 直接拒绝，不得做 payload-shape 消歧。

输入（逐项独立 case）：

- Event 携带 `anchor_ref` / `anchor_basis` / `governance_ref` 字段。
- Seal wire 携带 `anchorer_signature` / `signer_seq` / `anchored_at` 字段，或 typed id 使用已废除的 anchor 前缀（见 renames `typed_id_prefix` 条目）。
- Realm create payload 使用 `anchor_profile` / `anchorer` 字段。
- snapshot `event_set_commitment` 使用 `covered_seals` 字段。
- `event_state` 出现 `pending_anchor` / `rejected_anchor` 取值。

期望：

- 每个 case：current parser MUST 以 `schema_violation` / `unknown_field` / `unknown_kind` 类错误拒绝,MUST NOT 静默改写或按新名解释。
- 仅 `migration_tool` 层（离线批迁移）MAY 消费旧拼写。

失败条件：任一旧拼写被 current parser 接受或静默转换。

## 3. Redaction 与 Snapshot Vectors

### 3.1 目标

本节定义 redaction 的执行顺序、保留字段与可见性收敛规则，并涵盖与之相邻的 snapshot pruning / inclusion-challenge 向量（§3.5–§3.6，`domain=snapshot`）。
所有实现必须将 redaction 视为“可验证的内容裁剪”，而非删除事件。

向量命名：

```text
ck.vector.redaction.<scenario>.v1
ck.vector.snapshot.<scenario>.v1
```

### 3.2 Vector: 字段保留规则

向量名称：

```text
ck.vector.redaction.preserve_fields.v1
```

输入：

```json
{
  "target_event": {
    "event_id": "ck:event:0196414c-3000-7000-8000-000000000000",
    "kind": "ck.message.create",
    "realm_id": "ck:realm:0196414c-8000-7000-8000-000000000000",
    "actor_id": "did:web:alice.example.com",
    "created_at": "2026-04-26T00:00:00Z",
    "hlc": "01970e589d24-0001-aaaaaaaa",
    "prev_refs": [],
    "refs": [],
    "payload": {
      "strand_id": "ck:strand:0196414c-3400-7000-8000-000000000000",
      "content": {
        "kind": "ck.content.text",
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
    "event_id": "ck:event:0196418a-0360-7000-8000-000000000000",
    "kind": "ck.redaction",
    "realm_id": "ck:realm:0196414c-8000-7000-8000-000000000000",
    "actor_id": "did:web:alice.example.com",
    "created_at": "2026-04-26T00:00:02Z",
    "hlc": "01970e589d24-0002-bbbbbbbb",
    "prev_refs": [
      "ck:event:0196414c-3000-7000-8000-000000000000"
    ],
    "refs": [
      { "id": "ck:event:019640c5-5800-7000-8000-000000000000", "role": "authorized_by", "critical": true }
    ],
    "payload": {
      "redacts": "ck:event:0196414c-3000-7000-8000-000000000000",
      "reason_code": "policy_recall"
    }
  }
}
```

期望结果：

```json
{
  "event_id": "ck:event:0196414c-3000-7000-8000-000000000000",
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

`kept_envelope_fields` 中的 `redacted_by` / `redaction_reason_code` / `hashes` **不是 redaction event payload 的输入字段**,而是 reducer 在目标事件上派生写入的 tombstone-style 字段，映射规则如下（来源见 event-envelope schema 的对应 `$defs`）:

- `redacted_by` = 该 redaction event 的 `actor_id`（执行 redact 的主体）。
- `redaction_reason_code` = redaction event `payload.reason_code`（本例 `policy_recall`）。
- `hashes` = 目标事件原 envelope 的 `hashes` 字段，在 redaction 后保留以维持 event_id / canonical digest 的验证可追踪性，不由 redaction payload 提供。

失败判定：

- 把事件当作 tombstone 并抹去事件本体。
- 保留 `client_generated` 等不可验证字段。
- 修改 `event_id` 或 `hlc`。

### 3.2.1 Vector: Space target redaction payload schema

向量名称：

```text
ck.vector.redaction.space_target_ref_schema.v1
```

输入（payload 片段，必须通过 `event-payload.schema.json#/$defs/object_lifecycle_payload`）：

```json schema=schemas/event-payload.schema.json#/$defs/object_lifecycle_payload
{
  "target_ref": "ck:space:019640b6-8000-7000-8000-000000000000",
  "reason": "privacy_cleanup"
}
```

期望结果：

- Payload schema MUST 接受 `ck:space:*` 作为 `ck.redaction` 的 `target_ref` / `object_ref`。
- Reducer 语义仍按 Space 生命周期规则执行：Space 没有独立 `redacted` state，内容清理合并到 Space metadata cleanup / terminal transition；不得因 schema 漏洞把 Space cleanup 路径降级为实现私有扩展。

### 3.3 Vector: redaction 与 policy scope

向量名称：

```text
ck.vector.redaction.policy_scope.v1
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
      "event_id": "ck:event:0196417d-8400-7000-8000-000000000000",
      "kind": "ck.message.create",
      "realm_id": "ck:realm:0196414c-8000-7000-8000-000000000000",
      "created_at": "2026-04-26T00:00:00Z",
      "hlc": "01970e589d25-0001-11111111",
      "payload": {
        "strand_id": "ck:strand:0196417d-8400-7000-8000-000000000000",
        "content": {
          "kind": "ck.content.text",
          "body": "bad link: spam.example/phish"
        }
      }
    },
    {
      "event_id": "ck:event:0196417d-8980-7000-8000-000000000000",
      "kind": "ck.policy.action",
      "realm_id": "ck:realm:0196414c-8000-7000-8000-000000000000",
      "created_at": "2026-04-26T00:00:01Z",
      "hlc": "01970e589d25-0001-22222222",
      "actor_id": "did:web:policy-bot.example.com",
      "payload": {
        "target_id": "ck:event:0196417d-8400-7000-8000-000000000000",
        "policy_scope": "public",
        "decision": "quarantine"
      }
    },
    {
      "event_id": "ck:event:0196417d-8f00-7000-8000-000000000000",
      "kind": "ck.redaction",
      "realm_id": "ck:realm:0196414c-8000-7000-8000-000000000000",
      "actor_id": "did:web:policy-admin.example",
      "payload": {
        "redacts": "ck:event:0196417d-8400-7000-8000-000000000000",
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
ck.vector.redaction.hard_erasure_receipt.v1
```

期望：

- hard erasure 在被测存储边界内删除 payload bytes 与派生明文。
- 实现保留 verification stub：原始 event id、验证事件图所需的 Event envelope digest / proof `event_digest`、redaction event id、erasure reason、执行服务 DID、执行时间和签名 receipt。签名 receipt MUST 符合 `ck.schema.erasure_receipt.v1`；若作为历史事件发布，Event.kind MUST 为 `ck.audit.erasure_receipt`。
- stub 不得额外保留已擦除明文字段的 standalone content hash、payload-only digest 或未加盐搜索 fingerprint；若审计必须保留内容承诺，必须使用每事件 salt 或 HMAC/pepper commitment，并把 secret 留在 legal-hold 边界或按 erasure policy 销毁。
- backfill 返回 redacted / erased stub，不伪造替代事件，也不静默造成历史缺口。
- legal hold 存在时阻止 hard erasure，但默认展示仍应用 redaction。

### 3.5 Vector: snapshot pruning retains verification stub

向量名称：

```text
ck.vector.redaction.snapshot_pruning_stub.v1
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

### 3.6 Vector: snapshot inclusion challenge

向量名称：

```text
ck.vector.snapshot.inclusion_challenge.v1
```

本向量固化 [`snapshot-schema.md`](./snapshot-schema.md) §6 `event_set_commitment` 的 inclusion-challenge 采样与 merkle branch 校验规则，使 high-assurance bootstrap 不依赖单一实现的私有判断。当前 v1 candidate 尚未发布该向量的机器 fixture；在 fixture 生成器与 `spec/v1/artifacts/fixtures/` 产物补齐前，结构与断言以本节为准，fixture 缺口按 Phase 2 tracking 处理。实现 MUST NOT 以“缺 fixture”为由跳过已由本节 prose 固化的 high-assurance bootstrap 校验。

输入：

1. 一个已知 `event_set_commitment`（algorithm `merkle_event_set_v1`），其 `root` 覆盖 `covered_event_count` 个 event。
2. 一组采样 `samples[]`，其数量 `n ≥ max(20, ceil(log2(covered_event_count)))`，且至少覆盖 3 段不同的 `actor_seq_range`。
3. 每个 sample 配对一条 `proofs[].merkle_branch` 与声明的 `commitment_root`。
4. 至少一个 `gap_attribution` 条目（标注某 actor / seq 区间在被声明范围内缺失）。

期望：

- 采样数不满足 `n ≥ max(20, ceil(log2(covered_event_count)))`，或未覆盖 ≥3 段 `actor_seq_range` 时，verifier MUST 拒绝该 challenge 为不充分，并 MUST NOT 据此通过 completeness gate。
- 任一 `merkle_branch` 对其 sample 验证失败，或 `commitment_root` 与 manifest 声明的 root 不一致时，verifier MUST 拒绝该 snapshot。
- `gap_attribution` 为空但声明范围内确有缺口时，MUST 视为 completeness 未证明（set-bound commitment 只给 integrity，不给 completeness）。
- 两个 conformant verifier 对同一 fixture MUST 得到相同 accept/reject 结论。

## 4. Capability Vectors

### 4.1 目标

本文件将 capability 的链式授权、撤销回滚与审批约束固定为跨实现向量。
适配对象（下列为 profile 短名，统一用下划线；canonical id 形如 `ck.profile.<短名>.v1`，见 [`conformance-profiles.md`](./conformance-profiles.md)）：`identity_registry`, `principal_server_events_api`, `e2ee_client`, `enterprise_client`, `agent_runtime`.

向量命名：

```text
ck.vector.capability.<scenario>.v1
```

每个向量应检查：

- selector scope 是否正确绑定到 actor/device/realm/action。
- 授权时间窗约束是否导致一致结果。
- 关键路径必须拒绝 `authorization-only` 假阳性。

### 4.2 Vector: 多级委托链

向量名称：

```text
ck.vector.capability.delegate_chain.v1
```

输入事件链：

```json
{
  "base": {
    "kind": "ck.capability.grant",
    "subject": "did:web:root-admin.example.com",
    "actions": [
      "ck.realm.admin"
    ],
    "constraints": []
  },
  "delegations": [
    {
      "event_id": "ck:event:019640d0-c000-7000-8000-000000000000",
      "kind": "ck.capability.delegate",
      "realm_id": "ck:realm:0196414c-8000-7000-8000-000000000000",
      "actor_id": "did:web:root-admin.example.com",
      "payload": {
        "parent_grant_id": "ck:grant:019640d0-b800-7000-8000-000000000000",
        "subject": "did:web:ops.example.com",
        "resources": [
          {
            "kind": "realm",
            "realm_id": "ck:realm:0196414c-8000-7000-8000-000000000000",
            "match_scope": "realm_wide"
          }
        ],
        "actions": [
          "ck.capability.delegate",
          "ck.invite.create"
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
      { "id": "ck:event:01964180-0350-72ab-a000-000000000000", "role": "authorized_by", "critical": true }
    ]
    },
    {
      "event_id": "ck:event:019640d0-c400-7000-8000-000000000000",
      "kind": "ck.capability.delegate",
      "realm_id": "ck:realm:0196414c-8000-7000-8000-000000000000",
      "actor_id": "did:web:ops.example.com",
      "payload": {
        "parent_grant_id": "ck:grant:019640d0-c000-7000-8000-000000000000",
        "subject": "did:web:intern.example.com",
        "resources": [
          {
            "kind": "realm",
            "realm_id": "ck:realm:0196414c-8000-7000-8000-000000000000",
            "match_scope": "realm_wide"
          }
        ],
        "actions": [
          "ck.invite.create"
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
      { "id": "ck:event:019640d0-c000-7000-8000-000000000000", "role": "authorized_by", "critical": true }
    ]
    }
  ],
  "action_query": {
    "actor_id": "did:web:intern.example.com",
    "action": "ck.invite.create",
    "resource": "ck:realm:0196414c-8000-7000-8000-000000000000",
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
    "ck:event:01964180-0350-72ab-a000-000000000000",
    "ck:event:019640d0-c000-7000-8000-000000000000",
    "ck:event:019640d0-c400-7000-8000-000000000000"
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
ck.vector.capability.revoke_rollback.v1
```

输入：

```json
{
  "events": [
    {
      "event_id": "ck:event:01964101-2800-7000-8000-000000000000",
      "kind": "ck.capability.grant",
      "payload": {
        "grant_id": "ck:grant:01964101-2800-7000-8000-000000000000",
        "subject": "did:web:alice.example.com",
        "actions": [
          "ck.message.create"
        ]
      },
      "created_at": "2026-04-26T00:00:00Z"
    },
    {
      "event_id": "ck:event:01964181-2800-7000-8000-000000000000",
      "kind": "ck.capability.revoke",
      "payload": {
        "grant_id": "ck:grant:01964101-2800-7000-8000-000000000000"
      },
      "created_at": "2026-04-26T00:00:01Z"
    },
    {
      "event_id": "ck:event:019641d1-2800-7000-8000-000000000000",
      "kind": "ck.member.state",
      "payload": {
        "actor_id": "did:web:alice.example.com",
        "membership": "leave"
      },
      "created_at": "2026-04-26T00:00:02Z"
    },
    {
      "event_id": "ck:event:0196414c-c04a-7000-8000-000000000000",
      "kind": "ck.message.create",
      "actor_id": "did:web:alice.example.com",
      "created_at": "2026-04-26T00:00:03Z",
      "payload": {
        "strand_id": "ck:strand:0196418d-cc00-7000-8000-000000000000",
        "content": {
          "kind": "ck.content.text",
          "body": "should_fail_if_revoke_applies"
        }
      },
      "prev_refs": [
        "ck:event:019641d1-2800-7000-8000-000000000000"
      ]
    }
  ],
  "rollback": {
    "target_event_id": "ck:event:01964181-2800-7000-8000-000000000000",
    "reason": "revoke_undo_invalid_signature"
  }
}
```

期望输出：

- 初始解析：`ck:event:0196414c-c04a-7000-8000-000000000000` 因 revoke 生效应拒绝或标记 soft-fail/rejected（取决于实现策略）。
- 回滚 revoke 后重算：同一事件在回滚前瞻分析中应变为 authorized。
- 回滚必须产生独立可审计结果，不可直接修改历史事件链的 event_id。

验证：

- `accepted` 集合必须对应当前 reducer frontier。
- 回滚后状态必须可复现，并有 `rollback_ref` 或等价证据。

### 4.4 Vector: 审批约束缺失

向量名称：

```text
ck.vector.capability.approval_constraint.v1
```

输入：

```json
{
  "event": {
    "event_id": "ck:event:01964148-a800-7000-8000-000000000000",
    "kind": "ck.policy.action",
    "actor_id": "did:web:contractor.example",
    "realm_id": "ck:realm:0196414c-8000-7000-8000-000000000000",
    "hlc": "01970e589d26-0001-aaaaaaaa",
    "payload": {
      "action": "ck.realm.admin",
      "approval_required": true,
      "approval_quorum": 2,
      "policy_scope": "ck:realm:0196419b-0000-7000-8000-000000000000"
    },
    "refs": [
      { "id": "ck:event:0196419b-298e-7368-9a80-000000000000", "role": "authorized_by", "critical": true }
    ]
  },
  "capabilities": [
    {
      "kind": "ck.capability.grant",
      "subject": "did:web:contractor.example",
      "actions": [
        "ck.realm.admin"
      ]
    },
    {
      "kind": "ck.capability.grant",
      "subject": "did:web:approver-1.example.com",
      "actions": [
        "ck.approval.vote"
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

- `ck.profile.minimal_client.v1`
- `ck.profile.chat_mvp.v1`
- `ck.profile.kanban_mvp.v1`
- `ck.profile.full_client.v1`
- `ck.profile.e2ee_client.v1`
- `ck.profile.principal_server_events_api.v1`
- `ck.profile.principal_server.v1`

### 5.2 通用约定

测试向量使用以下简化字段：

```json
{
  "event_id": "ck:event:019640ed-8000-7000-8000-000000000000",
  "actor_id": "did:web:actor-a.example.com",
  "actor_seq": 1,
  "hlc": "019b76daa800-0000-a13f9c2e",
  "prev_refs": [],
  "refs": [],
  "kind": "ck.strand.update",
  "unsigned": {
    "target_ref_hint": "ck:strand:019640c5-0000-7000-8000-000000000000"
  },
  "content_digest": "sha256:..."
}
```

实现 MAY 使用真实 canonical JSON、CID、签名和 hash 替换示例值，但 MUST 保持以下语义：

- `event_id` 是内容寻址或签名绑定后的稳定 ID。
- `actor_seq` 在同一 actor 的单条因果路径上严格递增；并发 sibling fork 可出现相同高度。
- `hlc` 是 Hybrid Logical Clock，不能单独决定因果顺序。
- `unsigned.target_ref_hint` MAY 指向标准对象、Morph、Relation、View、Space 或 Realm，仅作为测试向量的阅读辅助；规范性目标必须来自 `payload.*` 字段、`payload.object.id`、precondition/effect cell key 或 reducer 规则。标准 Event envelope **top-level**（与 `kind` / `actor_id` / `payload` 同级）MUST NOT 出现 `target_ref`；该禁令仅针对 envelope 顶层，**不**适用于 payload 内部合法使用的 `target_ref`（如 §3.2.1 redaction payload 的顶层 `target_ref`）。

### 5.2.1 Vector: Late Key Recovery T0 Determinism

向量名称：

```text
ck.vector.e2ee.late_key_recovery.t0_deterministic_visibility.v1
```

输入：

- 目标密文事件 `E1` 在 sealed history 的 deterministic pre-state `T0` 中对 `receiver` 可见，且 `receiver` 在 `T0` 是 Realm member。
- `receiver` 在 `E1` accepted 之后、late key request 发出之前被 `ck.member.state{membership=ban}` 或等价 remove 事件移出 Realm。
- 两个客户端以不同本地到达顺序观察同一组 sealed events：客户端 A 先看到 `E1` 后看到 ban；客户端 B 先同步到 ban，再通过 backfill 看到 `E1`。
- key backup / archive node / peer share 在发 key 前重新计算 `E1` 的 `T0` membership、history visibility 和当前 share policy。

期望：

- 两个客户端对 `E1` 的 late recovery 结果一致，且只取决于 sealed `T0` effective view，不取决于本地到达顺序或 wall clock。
- 若 `receiver` 在 `T0` 可见且当前 share policy 仍允许历史恢复，late key 可以发放；后续 ban/remove 不 retroactively 改写 `E1` 的 verified timeline。
- 若 `receiver` 在 `T0` 不可见，或 key source 未在发 key 前重新执行 `T0` 校验，必须拒绝并返回 `key_unavailable` / `policy_denied` 类错误。
- 测试不得把“`T0` 后被 ban”单独作为拒绝理由；拒绝理由必须落在 `T0` 不可见或 key source unauthorized。

本节固化两个**独立**向量，各对应 `vector-registry.json` 的不同 id，MUST NOT 合并：

- `ck.vector.e2ee.late_key_recovery.t0_deterministic_visibility.v1`（本节主向量）——断言两客户端对 `E1` late recovery 结果只取决于 sealed `T0` effective view，与本地到达顺序 / wall clock 无关；正路径（`T0` 可见且 share policy 允许）发放、`T0` 不可见拒绝。
- `ck.vector.late_key_recovery.removed_actor.v1`（无 `e2ee.` 段，独立 registry id）——removed_actor negative path 专项：`receiver` 在 `T0` 不可见 / key source unauthorized 时 MUST 拒绝，且拒绝理由 MUST NOT 仅为“`T0` 后被 ban”。

### 5.2.2 Vector: Disappearing Read-trigger Anonymous Aggregate

向量名称：

```text
ck.vector.disappearing.read_trigger_anonymous_aggregate.v1
```

输入：

- Realm 启用 `ck.profile.disappearing.v1`，`ck.realm.disappearing_policy.allowed_triggers` 包含 `on_first_read` 与 `on_last_read`。
- Alice 发送带 `expiry.trigger="on_first_read"` 的 E2EE message `M1`；Bob 与 Carol 均在 send seal 的 eligible reader set 中。
- Bob 的一个授权设备通过 private `ck.read_cursor.advance` 覆盖 `M1`；Carol 没有公开 read receipt。
- Sync / account aggregate service 向其他客户端返回 projection 或 metadata-only expiry hint。

期望：

- `M1` 的 first-read anchor 被设置一次，projection 在 `anchor + ttl_ms + grace_ms` 后降级为 expiry stub。
- Alice、Carol、其它成员、push provider、search service 与默认客户端 projection 均不得看到 Bob 的 `actor_id`、`device_id`、handle、reader count、unread count、IP、在线状态或可跨 message 关联的 reader pseudonym。
- 允许的 trigger metadata 仅限 `source_event_id`、`trigger`、`anchor_hlc`、`expires_at` 与不可反查的 aggregate status；不得包含 read receipt UI payload。

### 5.2.3 Vector: Disappearing Read-trigger Idempotent Replay

向量名称：

```text
ck.vector.disappearing.read_trigger_idempotent_replay.v1
```

输入：

- 同一 principal 的两台设备对同一 message `M1` 乱序提交 read cursor / receipt，HLC 分别为 `H1` 与 `H2`。
- 攻击者重放 `M1` 的旧 read-trigger contribution，并尝试把同一 opaque token 绑定到另一条 message `M2`。
- `on_first_read` anchor 已经由第一次有效 contribution 接受。

期望：

- 同一 `(message, principal)` 的重复 contribution 只计一次；重复投递返回 success / already_observed 等幂等结果，不刷新 anchor。
- 较旧 HLC 被忽略；HLC 相等时按 read cursor device tie-break 收敛，但仍只产生一个 principal-level contribution。
- 跨 message、跨 scope、跨 trigger 或 policy frontier 不匹配的 replay MUST fail closed，不得让 `M2` 提前过期。

### 5.2.4 Vector: Disappearing On-last-read Offline Window

向量名称：

```text
ck.vector.disappearing.on_last_read_offline_window.v1
```

输入：

- Alice 发送带 `expiry.trigger="on_last_read"` 的 E2EE message `M1`。
- send seal 冻结的 eligible reader set 为 Bob、Carol、David；Bob 有两台设备。
- Bob 的手机读到 `M1`，Bob 的桌面离线；Carol 读到 `M1`；David 的 delivery binding 不可达，直到 `read_trigger_window_ms` 结束仍未贡献。

期望：

- Bob 只按 principal 计一次，离线桌面不得阻塞 `on_last_read`。
- `on_last_read` anchor 在 Carol contribution 与 `read_trigger_window_ms` 结束二者均满足后收敛；David 不得无限期阻塞。
- Bob 的离线桌面稍后上线时 MUST 接收 expiry stub / metadata-only 状态，MUST shred 本地 plaintext、message content key、preview cache 和 search / notification derived plaintext，且不得通过 late recovery 恢复正文。

### 5.3 Vector: Board Collection Projection

输入：

```json
{
  "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
  "events": [
    {
      "kind": "ck.space.create",
      "unsigned": {
        "target_ref_hint": "ck:space:019640b6-8000-7000-8000-000000000000"
      },
      "payload": {
        "object": {
          "id": "ck:space:019640b6-8000-7000-8000-000000000000",
          "schema": "ck.schema.space.v1",
          "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
          "kind": "board",
          "title": "Release Board",
          "created_by": "did:web:alice.example.com",
          "created_at": "2026-04-26T00:00:00Z"
        }
      }
    },
    {
      "kind": "ck.space.create",
      "unsigned": {
        "target_ref_hint": "ck:space:01964010-8400-7000-8000-000000000000"
      },
      "payload": {
        "object": {
          "id": "ck:space:01964010-8400-7000-8000-000000000000",
          "schema": "ck.schema.space.v1",
          "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
          "parent_space_id": "ck:space:019640b6-8000-7000-8000-000000000000",
          "kind": "list",
          "title": "Todo",
          "rank": "U",
          "created_by": "did:web:alice.example.com",
          "created_at": "2026-04-26T00:00:00Z"
        }
      }
    },
    {
      "kind": "ck.strand.create",
      "unsigned": {
        "target_ref_hint": "ck:strand:019640c5-0400-7000-8000-000000000000"
      },
      "payload": {
        "object": {
          "id": "ck:strand:019640c5-0400-7000-8000-000000000000",
          "schema": "ck.schema.strand.v1",
          "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
          "metadata": {
            "title": "Release checklist"
          },
          "tracks": {
            "synthesis": {
              "is_primary": true
            }
          },
          "stage": "planned",
          "created_by": "did:web:alice.example.com",
          "created_at": "2026-04-26T00:00:00Z"
        },
        "initial_relations": [
          {
            "relation_kind": "contains",
            "from_ref": "ck:space:01964010-8400-7000-8000-000000000000",
            "to_ref": "ck:strand:019640c5-0400-7000-8000-000000000000",
            "fields": {
              "board_space_id": "ck:space:019640b6-8000-7000-8000-000000000000",
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

- Collection projection MUST 返回 `object.id = ck:strand:019640c5-0400-7000-8000-000000000000`。
- 返回项 MUST 位于 `ck:space:01964010-8400-7000-8000-000000000000`。
- View cursor MUST 绑定 projection、view、frontier 与权限上下文。

### 5.4 Vector: Strand Card Move Read-Your-Writes

输入：

```json
{
  "write": {
    "kind": "ck.strand.move",
    "unsigned": {
      "target_ref_hint": "ck:strand:019640c5-0400-7000-8000-000000000000"
    },
    "payload": {
      "board_space_id": "ck:space:019640b6-8000-7000-8000-000000000000",
      "strand_id": "ck:strand:019640c5-0400-7000-8000-000000000000",
      "from_space_id": "ck:space:01964010-8400-7000-8000-000000000000",
      "target_space_id": "ck:space:01964010-8800-7000-8000-000000000000",
      "rank": "U"
    }
  },
  "query": {
    "object_types": [
      "strand"
    ],
    "consistency": {
      "wait_for": "barrier_cursor_from_write"
    }
  }
}
```

期望：

- Projection executor 在返回前 MUST 等待本地 frontier 覆盖写入 token，或返回可恢复超时。
- 查询结果中该 Strand item 的 `list_id` MUST 为 `ck:space:01964010-8800-7000-8000-000000000000`。

### 5.5 Vector: Strand Discussion Track Visibility

输入：

```json
{
  "strand_id": "ck:strand:019640c5-0400-7000-8000-000000000000",
  "viewer": "did:web:viewer.example.com",
  "viewer_can_read_strand": true,
  "viewer_is_track_member": false
}
```

期望：

- Strand projection MAY 显示 lazy 的 discussion-track 引用。
- Strand discussion timeline MUST NOT 展开。
- 通知 / 搜索结果 MUST NOT 泄露隐藏的 discussion 消息。

#### 5.5.1 Vector: Strand Discussion Surface Visibility

输入：

```json
{
  "strand_id": "ck:strand:01964195-8400-7000-8000-000000000000",
  "track_name": "discussion",
  "viewer_grants": ["ck.strand.read"],
  "viewer_track_membership": "none"
}
```

期望：

- 当 discussion 可发现性允许时，Strand projection MAY 显示 lazy / locked 的 discussion surface 引用。
- Strand activity MUST NOT 包含隐藏的 discussion 消息。
- Strand context MUST NOT 通过预览、摘要、通知、搜索片段、embedding 或 decision summary 泄露隐藏的 discussion 消息正文。

### 5.6 Vector: Strand Discussion Timeline

输入：

```json
{
  "strand_id": "ck:strand:01964180-0400-7000-8000-000000000000",
  "events": [
    {
      "kind": "ck.message.create",
      "unsigned": {
        "target_ref_hint": "ck:message:01964147-0400-7000-8000-000000000000"
      },
      "payload": {
        "strand_id": "ck:strand:01964180-0400-7000-8000-000000000000",
        "content": {
          "kind": "ck.content.text",
          "body": "discussion message"
        }
      }
    }
  ]
}
```

期望：

- 当 viewer 可读取 Strand discussion track 时，`strand-discussion-timeline` MUST 返回该消息。
- 仅当 viewer 可读取 Strand（按 Strand 的 effective scope）时，`strand-discussions` MUST 才包含该消息；当 Strand 通过 `scope_circle_id` 落在 Realm 内的 [Circle](../models/circle.md) 时，仅有 Realm-default 成员身份不足以读取该 Strand——必须同时是该 Circle 成员。

## 6. Space Lifecycle Vectors

### 6.1 目标

本节定义 Space（看板 / 列 / 泳道 / calendar bucket / page group ...）`active` ↔ `archived` ↔ `tombstoned` 状态机的跨实现测试向量。canonical 写入路径见 [`../models/realm-and-space.md` §3.4](../models/realm-and-space.md)；canonical 状态机对齐见 [`../models/common-fields.md` §5](../models/common-fields.md)。

实现声称支持以下 profile 时 SHOULD 运行本节向量：

- `ck.profile.kanban_mvp.v1`
- `ck.profile.full_client.v1`
- `ck.profile.principal_server.v1`

### 6.2 Vector: Space Archive 然后 Restore（happy path）

输入（按 causal order 应用）：

```json
{
  "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
  "events": [
    {
      "kind": "ck.space.create",
      "unsigned": {
        "target_ref_hint": "ck:space:019640b6-8000-7000-8000-000000000000"
      },
      "payload": {
        "object": {
          "id": "ck:space:019640b6-8000-7000-8000-000000000000",
          "schema": "ck.schema.space.v1",
          "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
          "kind": "board",
          "title": "Release Board",
          "created_by": "did:web:alice.example.com",
          "created_at": "2026-05-15T10:00:00Z"
        }
      }
    },
    {
      "kind": "ck.space.archive",
      "unsigned": {
        "target_ref_hint": "ck:space:019640b6-8000-7000-8000-000000000000"
      },
      "created_at": "2026-05-15T10:05:00Z",
      "payload": {
        "space_id": "ck:space:019640b6-8000-7000-8000-000000000000",
        "reason": "release_cycle_complete"
      }
    },
    {
      "kind": "ck.space.restore",
      "unsigned": {
        "target_ref_hint": "ck:space:019640b6-8000-7000-8000-000000000000"
      },
      "created_at": "2026-05-15T10:10:00Z",
      "payload": {
        "space_id": "ck:space:019640b6-8000-7000-8000-000000000000",
        "reason": "release_reopened"
      }
    }
  ]
}
```

期望：

- 应用 `ck.space.archive` 后，Space 物化对象 MUST 有 `state == "archived"` 且 `state_changed_at == "2026-05-15T10:05:00Z"`。默认 collection projection（不显式包含 archived items）MUST NOT 返回该 Space；显式带 `include_states=["archived"]` 的查询 MUST 仍可返回它。
- 应用 `ck.space.restore` 后，Space 物化对象 MUST 有 `state == "active"` 且 `state_changed_at == "2026-05-15T10:10:00Z"`。默认 projection MUST 重新展示该 Space。
- Restore **不**级联——若该 Space 包含 child Space（如 List 在 Board 内）或内部 Strand 且它们各自处于 `archived`，restore parent MUST NOT 改变 children 的 state。
- archive 期间未被擦除的 `contains` Relation、Strand position cell 与 `parent_space_id` cell MUST 在 restore 后保持原值；用户看到的内容与 archive 之前一致。

### 6.3 Vector: Space Restore 在 `active` 状态被拒绝

输入：

```json
{
  "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
  "pre_state": {
    "space": {
      "id": "ck:space:019640b6-8000-7000-8000-000000000000",
      "state": "active"
    }
  },
  "event": {
    "kind": "ck.space.restore",
    "unsigned": {
      "target_ref_hint": "ck:space:019640b6-8000-7000-8000-000000000000"
    },
    "created_at": "2026-05-15T11:00:00Z",
    "payload": {
      "space_id": "ck:space:019640b6-8000-7000-8000-000000000000"
    }
  }
}
```

期望：

- Reducer MUST 返回 `failed_precondition`，`reason == "space_not_archived"`。
- Space 物化对象 MUST NOT 被修改；`state_changed_at` MUST 保持 archive 之前的值或缺省。
- Event 不进入 reducer，但 envelope 本身签名/schema 合法时 MAY 仍被持久化为 envelope 历史（按各实现的 envelope-vs-state 边界处理）；reducer state 不得反映本次写入。

### 6.4 Vector: Space Restore 在 `tombstoned` 状态被拒绝（不可复活）

输入：

```json
{
  "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
  "pre_state": {
    "space": {
      "id": "ck:space:019640b6-8000-7000-8000-000000000000",
      "state": "tombstoned",
      "state_changed_at": "2026-05-15T09:00:00Z"
    }
  },
  "event": {
    "kind": "ck.space.restore",
    "unsigned": {
      "target_ref_hint": "ck:space:019640b6-8000-7000-8000-000000000000"
    },
    "created_at": "2026-05-15T12:00:00Z",
    "payload": {
      "space_id": "ck:space:019640b6-8000-7000-8000-000000000000"
    }
  }
}
```

期望：

- Reducer MUST 返回 `failed_precondition`，`reason == "space_not_archived"`（与 §6.3 同 reason；tombstoned 在状态机中不属于 `archived`，复活路径不存在）。
- Space 物化对象 MUST 保持 `state == "tombstoned"` 与原 `state_changed_at`。
- 该向量是 `tombstoned` 不可逆终态约束（[`realm-and-space.md` §3.4](../models/realm-and-space.md)、[`space.schema.json#/properties/state`](../../artifacts/schemas/space.schema.json)）的 wire 级证据：实现 MUST NOT 提供任何"先 restore 再写入"的 tombstoned 复活路径。需要重新启用一个等价容器时，正确的做法是 `ck.space.create` 一个新 Space。

### 6.5 Vector: Archive 在非 `active` 状态被拒绝

输入：

```json
{
  "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
  "pre_state": {
    "space": {
      "id": "ck:space:019640b6-8000-7000-8000-000000000000",
      "state": "archived",
      "state_changed_at": "2026-05-15T10:05:00Z"
    }
  },
  "event": {
    "kind": "ck.space.archive",
    "unsigned": {
      "target_ref_hint": "ck:space:019640b6-8000-7000-8000-000000000000"
    },
    "created_at": "2026-05-15T11:30:00Z",
    "payload": {
      "space_id": "ck:space:019640b6-8000-7000-8000-000000000000"
    }
  }
}
```

期望：

- Reducer MUST 返回 `failed_precondition`，`reason == "space_not_active"`（[common-fields.md §5.1](../models/common-fields.md) state-transition 表）。
- Space 物化对象 MUST 保持 `state == "archived"` 与原 `state_changed_at`；same-state self-transition 不被当作 idempotent no-op。
- 客户端如果意图是"重新 archive"，正确路径是先 `ck.space.restore` 再 `ck.space.archive`。
- 该向量对 Strand / Morph 等价同形：`ck.strand.archive` 在 `state != "active"` 时 `strand_not_active`；`ck.morph.archive` 同理 `morph_not_active`。

### 6.6 Vector: Tombstone 在已 tombstoned 状态被拒绝

输入：

```json
{
  "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
  "pre_state": {
    "space": {
      "id": "ck:space:019640b6-8000-7000-8000-000000000000",
      "state": "tombstoned",
      "state_changed_at": "2026-05-15T09:00:00Z"
    }
  },
  "event": {
    "kind": "ck.space.tombstone",
    "unsigned": {
      "target_ref_hint": "ck:space:019640b6-8000-7000-8000-000000000000"
    },
    "created_at": "2026-05-15T12:00:00Z",
    "payload": {
      "space_id": "ck:space:019640b6-8000-7000-8000-000000000000"
    }
  }
}
```

期望：

- Reducer MUST 返回 `failed_precondition`，`reason == "space_already_terminal"`（[common-fields.md §5.1](../models/common-fields.md) 终态等价规则）。
- Space 物化对象 MUST 保持 `state == "tombstoned"` 与原 `state_changed_at`。
- 该向量对 Strand / Morph 等价同形：`ck.redaction` 指向已 `redacted` 的 Strand / Morph 时同样返回 `<kind>_already_terminal`。终态进入是单向、单次操作。

### 6.7 Vector: Update 在非 `active` 状态被拒绝

输入：

```json
{
  "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
  "pre_state": {
    "space": {
      "id": "ck:space:019640b6-8000-7000-8000-000000000000",
      "state": "archived",
      "state_changed_at": "2026-05-15T10:05:00Z",
      "title": "Release Board"
    }
  },
  "event": {
    "kind": "ck.space.update",
    "unsigned": {
      "target_ref_hint": "ck:space:019640b6-8000-7000-8000-000000000000"
    },
    "created_at": "2026-05-15T11:45:00Z",
    "payload": {
      "space_id": "ck:space:019640b6-8000-7000-8000-000000000000",
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
- 客户端正确路径：先 `ck.space.restore`，update 通过后再决定是否 `ck.space.archive`。
- 该向量对 Strand / Morph `*.update` 等价同形。

## 7. Member Delivery Binding Vectors

### 7.1 目标

验证 `ck.member.state{membership="join"}` 的 `delivery_binding` payload 是 Realm-scoped event 投递的唯一权威路由源：
- schema-level conditional required 字段强制执行；
- DID Document service entry **不构成** fallback；
- 路由失败时 sender fail-closed（quarantine + retry，不退回 DID Document）；
- rebind 通过 causal frontier handover；
- 撤销后投递立即停止。

下列向量假设 Realm `ck:realm:7d000000-0000-7000-8000-000000000000`、actor `did:webvh:01HV...:alice` 已存在；具体 id 仅作占位。本节是 normative vector description；机器可执行 fixture 位于 [`../../artifacts/fixtures/membership-delivery-binding-fixture.json`](../../artifacts/fixtures/membership-delivery-binding-fixture.json)，runner MUST 同时消费该 fixture 与本文 prose，不得再依赖未落地的目录约定。

### 7.2 Vector: `explicit` Binding 接受

`vector_id`: `ck.vector.membership.delivery_binding.explicit.v1`

Input — `ck.member.state{membership="join"}` Control Move payload：

```json
{
  "realm_id": "ck:realm:7d000000-0000-7000-8000-000000000000",
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
    "service_acceptance_ref": "ck:event:7d000001-0000-7000-8000-000000000000"
  },
  "gate_proofs": [ "..." ]
}
```

预设：Realm policy `ck.realm.delivery_binding_policy` 声明 `allow_binding_sources` 包含 `explicit`、`allowed_recipient_services` 包含 `did:web:principal.acme.example`、`required_endorsers` 含 `did:web:acme.example`，`service_acceptance_ref` 引用的 Event 由 `did:web:principal.acme.example` 签发且 scope 覆盖该 Realm。

期望：
- reducer 接受 join Control Move；写入成员 cell。
- 此后任何向 Alice 投递的 Realm S event/sync/to_device/push/key_packages MUST 走 `did:web:principal.acme.example`，**禁止**触发 DID Document service entry resolution。

### 7.3 Vector: `did_document_default` Fallback 物化

`vector_id`: `ck.vector.membership.delivery_binding.did_document_default.v1`

Input — Realm policy `ck.realm.delivery_binding_policy` 声明 `allow_did_document_default=true`，其余字段未限制；Alice DID Document service `CokretPrincipalServer` 指向 `did:web:personal.alice.example`，canonical hash `sha256:abc...`。

客户端构造 join Control Move 时 MUST 先解析 DID Document 并物化进 binding：

```json
{
  "realm_id": "ck:realm:...",
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
- reducer 接受 join Control Move（`did_document_digest` 与 `resolved_at` 满足 conditional required）。
- 同形 Move 缺少 `did_document_digest` MUST 被 schema 拒绝（`schema_violation`），reducer 不进入验证流程。
- 同形 Control Move 在 Realm policy `allow_did_document_default=false` 时 reducer MUST 返回 `delivery_binding_policy_mismatch`。
- 一旦该 join 被接受，sender **不得**在后续投递时 re-resolve DID Document——即使 DID Document 已更新指向新服务，仍按 cell 内 `delivery_binding` 投递，直到一次合法 rebind。

### 7.4 Vector: `unroutable` 成员

`vector_id`: `ck.vector.membership.delivery_binding.unroutable.v1`

Input — Realm policy `ck.realm.delivery_binding_policy` 声明 `allow_unroutable_membership=true`。Alice join Control Move 携带：

```json
{
  "realm_id": "ck:realm:...",
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
- 同形 Control Move 在 Realm policy `allow_unroutable_membership=false` 时 reducer MUST 返回 `delivery_binding_policy_mismatch`。

### 7.5 Vector: Rebind Handover + 撤销后停止投递

`vector_id`: `ck.vector.membership.delivery_binding.handover.v1`

序列：

1. **Initial join**（`F0`）：Alice join with `recipient_service_did=did:web:personal.alice.example`，accepted。
2. **Events 流量**：Realm 内事件 `E1, E2` 进入因果图，sender 将它们投递到 `did:web:personal.alice.example`。
3. **Rebind**（`F1`）：Alice 提交同状态 `ck.member.state{membership="join"}` self-transition，新 binding 指向 `did:web:principal.acme.example`，签名按 `rebind_authorization` 规则。Control Move accepted。
4. **Post-rebind events**：sender 投递 `E3, E4` 时观察 `service_binding_ref.delivery_binding_frontier`：
   - sender frontier ≥ `F1` → 投递到 `did:web:principal.acme.example`；
   - sender frontier 仍 `< F1` 且投到旧 `did:web:personal.alice.example` → 旧服务在 `handover_grace_seconds` 内接受并返回 `delivery_binding_stale + new_recipient_service_did=did:web:principal.acme.example + handover_frontier=F1`；sender MUST 切换后重试，**不得**回退到 DID Document。
   - sender frontier ≥ `F1` 但仍投到旧 → 旧服务 reject `delivery_binding_handed_over`。
5. **Grace 结束**：旧服务停止接受新 Realm S event；本地 to-device 队列、push registration、MLS group share state 进入 destruction。
6. **撤销**：Alice 离职，Org-A 治理 key 提交 `ck.member.state{membership="leave"}` 或 `ck.capability.revoke`。`F2` 之后 sender MUST NOT 继续向 `did:web:principal.acme.example` 投递该 Realm 的内容；MUST NOT 转而退回 `did:web:personal.alice.example`（DID Document fallback）；该 actor 在 Realm S 中变成 **non-member**。

期望：
- 整个序列中 sender 解析投递目标 MUST 完全依赖 effective member cell 的 `delivery_binding`，DID Document service entry 永远不被 query。
- `delivery_binding_frontier` 字段在所有 service-to-service push 中均存在；sender 端落后 frontier 收到 stale signal 后 MUST 切换、不重投。
- 撤销后 sender 试图继续投递 MUST 收到 `member_not_in_space` 或 `capability_revoked`；MUST NOT 构造任何 "fallback to DID Document" 路径。

### 7.5.1 Vector: Policy Mismatch 拒绝

`vector_id`: `ck.vector.membership.delivery_binding.policy_mismatch.v1`

Steps:

1. Realm policy 不允许 `binding_source=explicit`，但 join Control Move 携带 explicit `delivery_binding`。
2. Realm policy 声明 `allowed_recipient_services`，但 `delivery_binding.recipient_service_did` 不在集合内且没有满足 `required_endorsers` 的 proof。
3. Realm policy 不允许 `allow_unroutable_membership`，但 join Control Move 携带 `delivery_status="unroutable"`。

Expected:

- 每个 case MUST `failed_precondition`，`reason=delivery_binding_policy_mismatch`。
- reducer MUST NOT fallback 到 DID Document，也不得接受成员后再把 delivery 状态标为 best-effort。

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
  "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
  "requester": "did:web:bob.example",
  "proof_challenge": "ck-challenge-001"
}
```

Directory 返回 verified handle claim：

```json
{
  "did": "did:webvh:z2dmjA1ice:users.acme.example",
  "subject": "did:webvh:z2dmjA1ice:users.acme.example",
  "handle": "alice:acme.example",
  "handle_aliases": ["acct:alice@acme.example"],
  "verified": true,
  "audience": "ck:realm:0196419b-0000-7000-8000-000000000000",
  "claims": [{
    "claim_kind": "organization_handle",
    "handle": "alice:acme.example",
    "handle_aliases": ["acct:alice@acme.example"],
    "subject": "did:webvh:z2dmjA1ice:users.acme.example",
    "issuer": "did:web:acme.example",
    "binding_state": "verified",
    "audience": "ck:realm:0196419b-0000-7000-8000-000000000000",
    "member_delivery_binding": {
      "recipient_service_did": "did:web:principal.acme.example",
      "recipient_service_type": "principal_server",
      "binding_source": "organization_policy",
      "delivery_modes": ["events", "sync", "to_device", "push", "key_packages"],
      "service_acceptance_ref": "ck:event:0196419b-0000-7000-8000-000000000001",
      "policy_event_ref": "ck:event:0196419b-0000-7000-8000-000000000002"
    },
    "created_at": "2026-05-19T00:00:00Z",
    "expires_at": "2026-08-19T00:00:00Z",
    "proofs": [{
      "kind": "detached_jws",
      "alg": "EdDSA",
      "verification_method": "did:web:principal.acme.example#key-1",
      "payload_digest": "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
      "created_at": "2026-05-19T00:00:00Z",
      "audience": "ck:realm:0196419b-0000-7000-8000-000000000000",
      "jws": "aaa.bbb.ccc"
    }]
  }],
  "member_delivery_binding": {
    "recipient_service_did": "did:web:principal.acme.example",
    "recipient_service_type": "principal_server",
    "binding_source": "organization_policy",
    "delivery_modes": ["events", "sync", "to_device", "push", "key_packages"],
    "service_acceptance_ref": "ck:event:0196419b-0000-7000-8000-000000000001",
    "policy_event_ref": "ck:event:0196419b-0000-7000-8000-000000000002"
  },
  "expires_at": "2026-08-19T00:00:00Z"
}
```

Expected join Control Move:

- `payload.actor_id = did:webvh:z2dmjA1ice:users.acme.example`。
- `payload.delivery_binding.recipient_service_did = did:web:principal.acme.example`。
- `payload.delivery_binding.binding_source = organization_policy`。
- `payload.delivery_binding.service_acceptance_ref` 与 `policy_event_ref` 来自 verified claim / policy。
- Control Move payload MUST NOT 把 `@alice:acme.example` 当作 actor、cell subject 或 grant subject；受限 handle 明文 SHOULD NOT 进入公开 Realm history。

Negative cases：

- Directory 返回 `verified=false` 或 challenge / audience 不匹配 → builder MUST NOT 构造 handle-based join。
- 返回 `subject != did` → client MUST reject `handle_subject_mismatch`。
- 返回 `member_delivery_binding.recipient_service_did` 但 Realm `allowed_recipient_services` 不包含该 DID，且没有 required endorser 背书 → reducer MUST reject `delivery_binding_invalid`。
- 返回无 `member_delivery_binding.recipient_service_did` → 只能作为 DID lookup；除非 Realm policy 允许 `did_document_default` 并物化 fallback，否则 reducer MUST reject handle-based join。

## 9. Security Closure Vectors

本节收拢跨章节引用的安全闭环向量。每个 `vector_id` 均为规范性引用目标；结构化覆盖位于 [`../../artifacts/fixtures/security-closure-vectors.json`](../../artifacts/fixtures/security-closure-vectors.json)，`tools/lint_artifacts.py` 会校验该 fixture 覆盖本节要求的 security closure vector set，并校验每个 step 暴露可由实现测试消费的 `runner.given_state` / `operation` / `transcript` / `expected_state_transition` / `expected_external_response` / `expected_audit_reason` 字段。实现不得把这些 ID 当成仅供说明的标签。

### 9.1 Vector: Federation Replay After Key Revoke

`vector_id`: `ck.vector.federation.idempotency_after_key_revoke.v1`

Steps：

1. Origin service `did:web:alpha.example` 使用 active service key 向 destination 提交 `POST /_cokret/peer/events`（`ck.peer.events.command.submit`），header 绑定 `Source-Service-DID`、`Destination-Service-DID`、`Source-Trust-Domain`、`Destination-Trust-Domain`、`Request-Canonical-Digest`、`Idempotency-Key`，批次 accepted。
2. Realm policy 或 DID Document 随后撤销该 origin service key；destination 的 accepted authorization frontier 前进。
3. 攻击者重放完全相同的 HTTP body、signature 与 `Idempotency-Key`。

Expected：

- 若重放只命中历史幂等缓存，destination MUST 返回 `historical_only`，不得重新接受为当前授权写入。
- 若 origin service binding 已被 Realm policy 移除，destination MUST 返回 `capability_denied`。
- 若 `origin_key_state_digest` 或 authorization frontier 与缓存 entry 不一致，receiver MUST 重新执行完整授权判定，不得只凭 `Idempotency-Key` 放行。

### 9.2 Vector: WebRTC Media Plaintext Downgrade

`vector_id`: `ck.vector.webrtc.media_plaintext_downgrade.v1`

Steps：

1. Realm policy 未授权 `media_service_decrypts`，但客户端收到 SFU 要求其发送 plaintext-visible media key 的 offer。
2. Realm policy 授权媒体服务解密，但 SFU service DID 不在 `plaintext_visible_services`。
3. UI 未显示 required plaintext warning，却尝试加入解密型会议。

Expected：

- 三种情况均 MUST 拒绝 join / publish media key。
- 失败原因分别为 `media_plaintext_policy_missing`、`media_plaintext_service_not_visible`、`media_plaintext_warning_missing` 或实现映射到等价稳定 reason_code。

### 9.3 Vector: Identity Link Eager Invalidation

`vector_id`: `ck.vector.identity_link.eager_invalidation.v1`

Steps：

1. Principal 在 Realm R 中存在 active identity link。
2. R 接受 ban / leave / remove 中任一 membership transition，或 capability revoke 使该 link 不再满足 visibility gate。
3. Directory、sync cache、invite cache 和 local profile projection 仍持有旧 link。

Expected：

- 实现 MUST eager invalidation 所有关联 cache entry；后续 lookup 不得返回旧 link。
- 已建立的 session / device claim MUST 在下一次 authorization check 时失败或降级到最小披露状态。

### 9.4 Vector: Identity Link Policy Tightening Invalidation

`vector_id`: `ck.vector.identity_link.policy_tightening_invalidation.v1`

Steps：

1. Principal 在 disclosure policy、history visibility、minimal metadata mode、linked Realm visibility 或 Circle effective-scope visibility 放宽时建立 identity link。
2. 任一 policy 被收紧，使旧 link 的披露范围不再被允许。
3. 调用者继续使用旧 directory / sync cache 查询同一 principal。

Expected：

- 所有受影响 cache MUST 按 policy frontier 失效。
- 未重新通过当前 policy gate 的旧 link MUST NOT 返回；UI / API 只能显示当前允许的最小身份信息。

### 9.5 Vector: Late Key Recovery Removed Actor

`vector_id`: `ck.vector.late_key_recovery.removed_actor.v1`

Steps：

1. Receiver 请求恢复 T0 历史密钥，但其在 T0 的 membership / history visibility 不允许查看该历史。
2. 或者 receiver 曾在 T0 可见，但 key source 在 ban / remove 之后未重新执行 T0 membership + current share policy 校验就发送 late material。

Expected：

- T0 不可见时 MUST NOT 解密，reason_code 为 `late_recovery_rejected_membership` 或等价稳定码。
- key source 未重新校验时 MUST 拒绝 share，reason_code 为 `late_recovery_share_not_authorized`。
- 客户端 UI 不得显示未授权明文或把其纳入 verified timeline。

### 9.6 Vector: Invite OOB Code Entropy

`vector_id`: `ck.vector.invite.oob_code_entropy.v1`

Steps：

1. 构造低于生产最低熵的 offline OOB code claim。
2. 构造 lookup 形态 OOB code，其有效窗口或 claim 次数超过 policy 上限。

Expected：

- reducer / verification service MUST 拒绝短熵 code claim。
- 超限 lookup 形态 MUST invalidate，不得进入 pending invite 或 accepted membership。

### 9.7 Vector: Invite Failure Indistinguishable

`vector_id`: `ck.vector.invite.failure_indistinguishable.v1`

Steps：

1. 分别触发 token 不存在、过期、已撤销、已消费、audience 不匹配、邀请者已离开 Realm、policy gate 不满足七类失败。
2. 对外调用同一个 claim endpoint，记录 HTTP status、response body、headers 和响应时间。

Expected：

- 对外响应 MUST byte-identical 或等价不可区分；仅服务端 audit log 可记录具体 reason_code。
- timing 差异 SHOULD ≤ 50ms；高安全 profile MUST 对该窗口做 jitter / padding。

### 9.7.1 Vector: Invite Claim Reducer State Machine

`vector_id`: `ck.vector.invite.claim_reducer_state_machine.v1`

本向量固化 [`third-party-invites.md`](../sync/third-party-invites.md) §4.3 的 Realm reducer 权威要求。机器可执行样本位于 [`../../artifacts/fixtures/security-closure-vectors.json`](../../artifacts/fixtures/security-closure-vectors.json)；runner MUST 同时消费 prose 与 fixture，不得只依赖验证服务或 Sync Service 入站预检。

Steps：

1. 正路径：Realm frontier 中存在 `state="pending"` 的 `ck.invite.third_party`，`token_commitment`、`claim_nonce`、`verification_service_did` allowlist、`binding_proof`、`subject_proof` 和 `expires_at` 均有效。
2. Token commitment mismatch：`ck.invite.claim.payload.token_commitment` 不等于 pending invite 的 commitment。
3. Allowlist 复校验失败：验证服务曾签发 binding proof，但当前 effective Realm policy 已移除该 `verification_service_did`。
4. Claim nonce replay：同一 `(invite_id, claim_nonce)` 或同一 `token_commitment` 已被 reducer 观察为 claim effect。
5. Expired cleanup：`invite.expires_at <= now` 时提交 claim。

Expected：

- Case 1：Reducer MUST 原子产生 `pending -> claimed`，记录 `claimed_by=subject_id`、claim nonce digest 和 verification service DID，并只物化 subject-bound `ck.invite.create` 或等价 membership proposal；最终 `ck.member.state{membership="join"}` 仍需 `ck.invite.accept` 或显式 profile 路径。
- Cases 2-5：Reducer MUST reject，不得产生 membership proposal 或 join；case 4 使用 `duplicate_conflict`，case 5 使用内部 `expired_invite_token` 并触发 §6.1 token material cleanup。
- 所有失败通过外部 claim surface 返回不可枚举 `not_found` 或同形态响应；具体 reason 只进入 audit / per-event rejected diagnostics。

### 9.8 Vector: Consent Scope Cascade

`vector_id`: `ck.vector.consent.scope_cascade.v1`

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

`vector_id`: `ck.vector.consent.cache_invalidation.v1`

Steps：

1. Consent active 时 private contact discovery PSI result、invite capability gate 和 PSI index 均缓存了 peer 可达状态。
2. Subject revoke consent。
3. 调用 directory lookup、提交下一次 invite Control Move，并等待 PSI 下一轮轮转。

Expected：

- Private contact discovery / invite handoff MUST 立即不返回该 peer。
- 下一次 invite Control Move MUST precondition 失败并重判 capability gate。
- `any` revoke MUST 失效所有 scope cache；PSI 索引在下一次轮转时排除该 peer。

### 9.10 Vector: Sync Soft-Fail Reconcile

`vector_id`: `ck.vector.sync.soft_fail_reconcile.v1`

Steps：

1. Receiver 收到 soft-failed event，原因是缺少 dependency / auth state / key material。
2. Backfill 成功补齐全部依赖。
3. 另一路中，backfill 返回冲突或永久缺失。

Expected：

- 补齐后 reducer MUST deterministically 从 soft-fail 转为 accepted，并更新 covered event set。
- 永久缺失或冲突时 MUST 转为 rejected / failed_precondition，不得无限留在 soft-fail。

### 9.11 Vector: Lattice LWW Open Set

`vector_id`: `ck.vector.lattice.lww_open_set.v1`

Steps：

1. 构造同一 seal view 中多个 sibling write，它们对同一 open-set cell 产生竞争状态。
2. 所有 sibling 带相同 logical time，但 actor / event id / canonical digest tiebreaker 不同。
3. 两个 conformant reducer 以不同输入顺序重放。

Expected：

- sibling 集合与 tiebreaker MUST 产出同一 winner。
- 任一实现出现不同 winner、不同 bottom 或不同 covered event set，均视为 reducer bug。

### 9.12 Vector: E2EE Relaxed Window Exceeds Ceiling

`vector_id`: `ck.vector.e2ee_relaxed.window_exceeds_ceiling.v1`

Steps：

1. Realm policy event 尝试把 `relaxed_window_max_ms` 写为大于 300000。
2. Receiver 收到 old-epoch decrypt admission，其 gap 超过当前 policy window。
3. Deployment profile 尝试通过 unrelated profile 重新定义 hard ceiling。

Expected：

- Reducer MUST 以 `relaxed_window_exceeds_ceiling` 拒绝超限 policy write。
- Receiver MUST 独立拒绝超过当前 policy window 的 decrypt admission。
- Hard ceiling 不可由 deployment profile 重定义；实现不得 silently clamp 后继续接受。

### 9.13 Vector: Consumed Third-Party Invite Token Resubject Rejected

`vector_id`: `ck.vector.invite.consumed_token_resubject_rejected.v1`

Steps：

1. 第三方邀请 token 已被验证服务原子消费并签发了绑定 `subject_id=did:web:alice.example` 的 `binding_proof`。
2. 攻击者用同一已消费 token 向验证服务发起第二次签发请求，指向不同 `subject_id=did:web:mallory.example`。
3. 攻击者另把承载该已消费 token 重绑到不同 subject 的 `ck.invite.claim` Event 提交给 reducer。

Expected：

- 验证服务 MUST 拒绝第二次签发，不签发指向不同 subject 的第二份 `binding_proof`；仅当请求绑定同一 `(invite_id, claim_nonce, subject_id, binding_proof_digest)` 时，才允许在可恢复窗口内幂等重投递同一份既有 `binding_proof`。
- Reducer MUST 以 `duplicate_conflict` 拒绝该 resubject `ck.invite.claim` Event。
- 对外失败响应 MUST 与 `not_found` 不可区分（与本节其它 invite 向量一致），具体 reason code 只写入服务端 audit log。
- 规范定义见 [`../sync/third-party-invites.md` §6.1](../sync/third-party-invites.md)。

## 10. Service Closure Vectors

### 10.1 Vector: Ephemeral Capability And TTL

`vector_id`: `ck.vector.ephemeral.capability_ttl.v1`

Steps：

1. Actor 对 `ck.typing` 提交 `ck.self.ephemeral.command.send`，但只持有 `ck.presence.broadcast`。
2. Actor 持有正确 action 后，提交超出 advertised kind-specific TTL 的 envelope。
3. Ephemeral channel 暂时不可用。

Expected：

- 第 1 步 MUST 返回 `ephemeral_kind_not_permitted`。
- 第 2 步 MUST 返回 `ephemeral_ttl_out_of_range`。
- 第 3 步 MUST 返回 `ephemeral_channel_unavailable`，且不写 durable Event、不推进 actor_seq / Realm frontier。

### 10.2 Vector: Projection Pagination Shape

`vector_id`: `ck.vector.projection.pagination_shape.v1`

Steps：

1. 调用 `ck.self.projection.spaces.query.list` / `strands` / `morphs`，请求 `limit=1`。
2. 使用返回的 `next_cursor` 继续读取。
3. 下游 service-call 返回缺失 `has_more` 或 cursor 形态不合法的响应。

Expected：

- 每个响应 MUST 带 `has_more`；有后续页时 MUST 带合法 `ck:cursor:*`。
- Cursor MUST 绑定调用者、selector 和 projection purpose，不得跨 service / Realm 复用。
- 缺失分页闭包字段时上游 MUST 归类为 `invalid_response`。

### 10.3 Vector: KeyPackage Exhaustion And Claim Limits

`vector_id`: `ck.vector.keypackage.exhaustion_claim_limits.v1`

Steps：

1. Device 可用 KeyPackage 数量低于 `keypackage_min_available`。
2. 同一 `(requester_service_did, target_principal_id)` 在 60s 内发起超过 5 次 claim。
3. 已 claimed KeyPackage 到达 `expires_at` 后再尝试 consume。

Expected：

- Server SHOULD 在可见响应中返回 `available_count`，client MUST 在下一次 maintenance / sync 补充上传。
- 超限 claim 对外仍保持反枚举失败，不泄露目标是否存在；内部审计 reason 为 `keypackage_claim_rate_limited`。
- 过期 claimed package MUST 转为 revoked / unusable，不得回到 `published`，迟到 consume MUST 被拒绝。

### 10.4 Vector: Soft Logout DID Proof Required

`vector_id`: `ck.vector.auth.soft_logout_did_proof.v1`

Steps：

1. Session 进入 `soft_logged_out`。
2. Client 仅携带仍有效的 refresh token 请求恢复。
3. Client 重新提交 refresh/OIDC/re-auth，并携带授权 DID/device key 对 challenge 的签名。

Expected：

- 第 2 步 MUST 返回 `did_proof_required`，不得签发 active session grant。
- 第 3 步的 proof MUST 覆盖 principal、device、audience、challenge、request canonical hash 和 expiry；验证成功后才可恢复为 `active`。

### 10.4.1 Vector: DID Proof Replay Window

`vector_id`: `ck.vector.identity.did_proof_replay_window.v1`

Steps：

1. Auth Server 发出 DID proof challenge，绑定 `purpose="account_binding"`、`audience=did:web:auth.example`、`origin=https://auth.example`、随机 nonce、`issued_at=T0`、`expires_at=T0+300s`。
2. Client 提交签名正确的 proof，服务器接受并 burn challenge。
3. 攻击者第二次提交同一 proof。
4. 攻击者把相同签名 transcript 用到另一 audience/origin，或提交 `expires_at - issued_at = 3600s` 的 proof。
5. 攻击者提交 `issued_at` 超出接收端 skew 窗口的 proof。

Expected：

- 第 2 步 MUST 成功并把 challenge 进入 replay table。
- 第 3 步 MUST fail closed，即使签名仍正确。
- 第 4 步 MUST 因 audience/origin mismatch 或 freshness window 超限拒绝；服务端不得裁剪有效期后继续接受同一 proof。
- 第 5 步 MUST 拒绝；默认 skew 上限 SHOULD ≤ 300s。

### 10.5 Vector: Session Grant Audience Binding

`vector_id`: `ck.vector.auth.session_grant_audience_binding.v1`

Steps：

1. Auth Server 收到 `ck.gate.account.command.issue_session_grant`，proof 中 `audience` 与目标 resource server 不匹配。
2. 请求缺少 `request_canonical_digest` 或 hash 不覆盖 `principal_id`、`device_id?`、`requested_scope` 与 `audience`。
3. 请求的 `expires_at` 超过 Auth Server 声明的 session grant TTL 上限。
4. Auth Server 在 `development_mode=true` 时尝试把 `ck.profile.auth_server.v1` 放入 `verified_profiles[]`。

Expected：

- 第 1 步 MUST 拒绝，reason_code 为 `audience_mismatch` 或等价稳定码。
- 第 2 步 MUST 拒绝，reason_code 为 `invalid_proof_binding` 或等价稳定码。
- 第 3 步 MUST 拒绝或收紧到服务器硬上限，并在响应中暴露实际 `expires_at`；不得签发跨多日 session grant。
- 第 4 步 MUST 被 conformance / describe 校验拒绝；development mode 下 `verified_profiles[]` 必须为空。

### 10.6 Vector: Witness Disagreement Quarantine

`vector_id`: `ck.vector.range_completeness.witness_disagreement.v1`

Steps：

1. 两个 witness 对同一 `(realm_id, actor_id, actor_seq)` 给出不同 `event_id` / `event_digest`。
2. 两个 range-completeness attestation 声称同一 `(from_frontier, to_frontier]` scope，但 `root` 不同且无法由不同上界解释。
3. High-assurance peer 只提供 `single_source` attestation 试图解除 backfill completeness gate。

Expected：

- 第 1 / 2 步 MUST 标记 `witness_disagreement` 并 quarantine 对应 range / peer。
- 不得用本地接收顺序、HLC 或最后写入者选择 winner。
- 第 3 步 MUST 保持 pending / stale，不得推进 high-assurance completeness frontier。

### 10.7 Vector: Capability Revoke Downstream Recheck

`vector_id`: `ck.vector.capability.revoke_downstream_recheck.v1`

Steps：

1. Grant G 授权 actor 写入，Event E 的 `refs[role="authorized_by"]` 指向 G。
2. G 派生 child grant C，C 又授权 pending Event P。
3. `ck.capability.revoke{grant_id=G}` accepted。

Expected：

- P MUST fail closed 或 quarantine，reason `grant_revoked_upstream` / `authorized_grant_revoked`。
- Allow cache / policy decision cache 中依赖 G 或 C 的 entry MUST 在同一 reducer transaction 内失效。
- 历史 E 保留审计事实，但后续 snapshot/export 不得把 G 当作当前有效授权。

### 10.8 Vector: Cursor Revoke

`vector_id`: `ck.vector.cursor.revoke_high_assurance.v1`

Steps：

1. 服务签发 stream cursor 并随后接受 `/_cokret/self/account/cursor/revoke`。
2. 攻击者重放已撤销 cursor 到 `/_cokret/self/account/subscribe?after=`。
3. 攻击者提交篡改过但未撤销的 cursor。

Expected：

- 第 2 步 MUST 返回 `cursor_revoked`，且不推进 subscription position（to-device 队列删除只由 `ck.self.device_messages.command.ack` 驱动，与 cursor 无关）。
- 第 3 步 MUST 返回 `cursor_integrity_invalid`，不得泄露 revocation set 是否命中。

### 10.9 Vector: Device Recovery Lifecycle

`vector_id`: `ck.vector.device_recovery.lifecycle.v1`

Steps：

1. 新设备用过期 `ssk_generation` 提交恢复 proof。
2. 新设备 proof 通过，但未完成 secret storage unlock / MLS Welcome replay。
3. KeyPackage claim 后失败并使可用数量低于 low-watermark。

Expected：

- 第 1 步 MUST 返回 `device_recovery_ssk_generation_mismatch`。
- 第 2 步设备只能处于 `recovery_pending`，不得显示 fully verified。
- 第 3 步 response SHOULD 返回 `available_count` / `low_watermark` / `suggested_publish_count`，claimed package 不得自动放回。

### 10.9.1 Vector: Device Revocation Seal Binding

`vector_id`: `ck.vector.device.revocation_seal_binding.v1`

Steps：

1. `ck.device.revoke` 作为 Control Move 提交，信封携带有效 `seal_basis`（单 leaf，取自 `ck.self.events.query.frontier` 的 Realm Seal view），随后被 principal control stream 的 accepted Seal S 覆盖（`control_sealed`）。
2. 攻击者重放该设备在 S 之后（以 S 或其后继 Seal view 判定）签发的 session grant、KeyPackage publish 或 to-device write。
3. 某 E2EE Realm 提交 MLS Remove，但 `governance_binding.membership_frontier` 未覆盖该 `ck.device.revoke` 事件，也未覆盖导入该撤销的 Realm governance Control Move。
4. 客户端在 `ck.self.events.query.frontier` 来源不可用（错误或缺 `seal_id` / `control_event_set_root`）时尝试提交 `ck.device.revoke`。

Expected：

- 第 2 步 MUST fail closed；实现不得用本地布尔缓存替代以 S 或其后继 Seal view 的判定。
- 第 3 步 Remove 不得使 `covered_seals_cell` 声称已覆盖该设备撤销；后续 E2EE DataEvent 仍必须被 `covered_seals_cell` gate 阻塞。
- 第 4 步客户端 MUST fail closed，不得伪造 `seal_basis`；缺失或不一致 basis 的 Control Move 按 `ck.vector.cba_lattice.control_move_requires_seal_basis_and_seal.v1` 拒收。

### 10.10 Vector: Push Wakeup Policy

`vector_id`: `ck.vector.push.wakeup_policy.v1`

Steps：

1. E2EE Realm 声明 `wakeup_default=no_notification`，server 无法评估 client-side mention rule。
2. 设备注册 `client_rule_digest` 与服务端保存 digest 不一致。
3. Realm 使用 `batch_wakeup`，一分钟内大量 client-side unresolved events 到达。

Expected：

- 第 1 步 MUST NOT 发送单事件 blind wakeup。
- 第 2 步 MUST 按更保守策略处理，不得猜测规则内容。
- 第 3 步 MUST 合并为 batch wakeup，仍携带 `evaluation_locus_unresolved=true`。

### 10.11 Vector: Audience Mention Controls

`vector_id`: `ck.vector.push.broadcast_mention_controls.v1`

Steps：

1. 普通成员只持有 `ck.message.create`，在 Message content AST 中加入 `audience_mention{audience="effective_scope_members"}`。
2. Realm policy 未声明 audience mention 策略；另一次提交中 sender 持有 `ck.message.mention.broadcast` 但 policy 仍缺失。
3. Realm policy 允许 `effective_scope_members`，设置 `max_recipients=25` 和 rate window；sender 持有带 `rate_limit` 的 `ck.message.mention.broadcast`。
4. 当前 effective scope 有 30 个可见成员；其中 1 个 receiver 显式 `level=muted`，1 个 receiver 被个人 blocklist / target policy 抑制。
5. sender 在 rate window 内再次发送 audience mention。

Expected：

- 第 1 步不得产生 audience mention notification；实现 MAY 拒绝整条 message 或接受消息但把 audience mention 降级为普通文本 / 不通知，取决于 Realm policy 声明。
- 第 2 步 MUST fail closed：缺少 effective audience mention policy 时，持有 `ck.message.mention.broadcast` 本身不足以 fanout。
- 第 3-4 步 recipient count 超过 `max_recipients` 时 MUST 在 fanout 前拒绝或进入 policy-declared review/quarantine；不得先发 push 再撤回。
- `level=muted` 与 target policy 抑制的 receiver MUST NOT 收到 notification stub 或 push wakeup，且发送者不能通过 delivery response 区分原因。
- 第 5 步 MUST 返回 `rate_limited` / `quota_exceeded` 或等价 policy denial；push payload 不得包含 audience 名称、recipient count、成员列表、Realm / Strand / Event 标识。

### 10.12 Vector: Strand Engaged Audience Mention

`vector_id`: `ck.vector.push.strand_engaged_mention.v1`

Steps：

1. Strand `F` 中 Alice 准备发送 Message，Message effective scope 包含 Bob、Carol、Dave、Erin、Frank，但不包含 Grace。
2. Bob 在 `F` 的 discussion track 中有一条 active Message；Carol 的 effective watch level 为 `all`；Dave 为 `mentions_only`；Erin 为 `muted`；Frank 只有 active assignment；Grace 无读取权。
3. Realm / Circle policy 允许 `audience="strand_engaged"`，声明有限 `max_recipients` 与 quota；Alice 同时持有 `ck.message.create` 与带 `max_operations` + `period` 的 `ck.message.mention.broadcast`。
4. Alice 发送 `audience_mention{audience="strand_engaged", mention_text_original="@here"}`。另一次测试中，Bob / Carol 的 presence 状态分别在 online / offline 间切换，但其他输入不变。

Expected：

- `@here` MUST 按 `strand_engaged = strand_participants ∪ strand_watchers` 展开：Bob 因 active discussion participation 命中，Carol 因 effective watch level `all` 命中。
- Dave（`mentions_only`）、Erin（`muted`）、Frank（仅 assignment）、Grace（无读取权）MUST NOT 因该 audience mention 收到 notification stub 或 push wakeup。
- Presence / online 状态 MUST NOT 影响 `strand_engaged` 的 receiver set；实现不得把 `@here` 解释成 presence-filtered audience。
- Sender、普通 Realm 成员、push gateway、公开日志与 delivery response MUST NOT 暴露 recipient count、watcher 列表、watch level、命中原因，且不得区分 Bob 是参与者命中还是 Carol 是 watcher 命中。

### 10.13 Vector: Events Query Range Completeness Detection

`vector_id`: `ck.vector.sync.range_completeness_client_query.v1`

前置：服务端 `supported_features[]` 声明 `events_query_range_completeness`；Realm 配置 `audit.range_completeness_witnesses[]` 且已存在覆盖区间 `(F1, F2]` 的 `federation_witness_attested` attestation；区间内 actor Bob 产生过 `seq 10..20` 的 reducer-input event。

Steps：

1. 客户端因 `dropped` / cursor 失效按 [`client-sync.md` §12.3](../sync/client-sync.md) 恢复，调用 `ck.self.events.query.scan`（`include_completeness=true`）backfill 区间 `(F1, F2]`。
2. 服务端返回完整事件页 + `range_completeness.attestation_refs[]`；客户端按 [`operations-sync.md` §4.2.4](../sync/operations-sync.md) 重算 Merkle root 并核对 `actor_seq_ranges[]`。
3. 变体 A：服务端从响应中扣下 Bob `seq 14..16` 的事件，但返回同一 attestation。
4. 变体 B：服务端未声明该 feature，收到 `include_completeness=true`。
5. 变体 C：attestation 仅为 `single_source`，而 Realm 声明 `security_class=high_assurance`。

Expected：

- 第 2 步：root 与 `actor_seq_ranges[]` 全部一致时，客户端方可把该区间标记为已 attest 的完整范围。
- 变体 A：客户端 MUST 检出本地视图与 attestation 的差异（`range_completeness_actor_seq_gap` 或 root 重算不一致 `range_completeness_root_mismatch`），把该区间标记 degraded 并 fail closed；MUST NOT 向用户展示"历史完整"。
- 变体 B：服务端 MUST 忽略该参数，响应不含 `range_completeness` 字段且不报错；客户端把范围视为未 attest。
- 变体 C：客户端 MUST NOT 用 `single_source` attestation 解除 high-assurance Realm 的 completeness 关注；按未 attest 处理或继续等待 quorum attestation。

## 11. Personal Agent & Sidecar Vectors

### 11.1 Vector: Provisioning + Pairing + Effective Grant

`vector_id`: `ck.vector.agent.provision.v1`

Steps:

1. Controller 调用 `ck.self.agent.command.provision`,得到 `agent_principal_id`、初始 grant ids(每条 grant payload 含 `effective_after_first_authorized_key=true`)与 `pairing_request_id`。
2. Agent runtime 生成 key pair,调用 `ck.gate.account.command.pair_agent_key`。
3. Pairing endpoint 校验 `verification_method` 的 DID 部分(strip fragment/query 后)与 `agent_principal_id` bit-identical。
4. 批准后写入 `ck.agent.key.authorize`,reducer 清除 effective_after_first_authorized_key flag。

Expected:

- 第 3 步 verification_method 与 agent_principal_id 不一致时 MUST `failed_precondition` `reason=verification_method_principal_mismatch`。
- 在第 4 步之前，任何 `agent_key_proof` session grant 请求 MUST fail closed;以该 grant 为基础的 capability check 也 MUST fail closed。
- 第 4 步后 grant 进入正常 effective window 评估;agent runtime 可签发 session grant 并执行 capability action。

### 11.1.1 Vector: Controller-scoped Agent Mention Selector

`vector_id`: `ck.vector.agent.mention_selector.v1`

Preconditions:

- Alice 拥有 verified handle claim `alice:acme.example`，`subject=AliceDID`。
- Alice 拥有 active native personal agent `AgentS`，其 Actor Profile `actor_kind="agent"`、`agent_slug="summary"`、`principal_id=AgentSDID`，且有 active `ck.identity.accountability_grant{issuer=AliceDID, subject=AgentSDID}`。
- Alice 或授权 issuer 签发 current `ck.schema.agent_selector_claim.v1{controller_subject=AliceDID, agent_slug="summary", subject=AgentSDID, binding_state="verified", visibility="restricted", audience=<RealmR>}`。
- 同一 Realm 中 Bob 可见 Alice 的 handle claim、AgentS 的 Actor Profile、selector claim 与 accountability evidence。

Steps:

1. Bob 在 message composer 输入 `@alice:acme.example/summary`。
2. 客户端从本地 Realm roster / actor profile / handle claim cache 解析 controller handle → `AliceDID`，再验证 selector claim `(AliceDID, "summary")` → 唯一 active `AgentSDID`。
3. 客户端提交 Message content AST，其中 mention node `subject_id=AgentSDID`，并可携带 `controller_subject_id=AliceDID`、`controller_handle_at_time="alice:acme.example"`、`agent_slug_at_time="summary"`、`mention_text_original="@alice:acme.example/summary"`。
4. Alice 之后把 `AgentS.agent_slug` 改为 `sum`，或把 `summary` 分配给另一个新 agent `AgentT`。
5. 另一次测试中，Alice 同时存在两个 current valid selector claims 绑定 `(AliceDID, "summary")` 到不同 active agents，或 Bob 不可见 selector claim / accountability evidence。

Expected:

- 第 2 步 MUST 在持久化前完成；selector claim 是 slug 绑定的权威来源。持久化事件里的权威 mention target MUST 是 agent `subject_id=AgentSDID`，不得把 `alice:acme.example/summary` 当作 handle 或权威字段写入。
- 第 3 步的 `controller_*` 与 `agent_slug_at_time` 只作 audit / search / fallback metadata；reducer、dispatcher、policy engine MUST 忽略这些字段做授权和投递决策。
- 第 4 步 MUST NOT 改写历史 mention target；旧消息仍指向 `AgentSDID`。
- 第 5 步 MUST fail closed：客户端不得构造 mention node；实现可提示 picker 选择或把输入保留为普通文本。服务端若收到仅靠 metadata 声称 selector 的事件，也必须只按 `subject_id` 和已验证 agent state 判定。

### 11.2 Vector: Pairing Expiry Auto-Revoke

`vector_id`: `ck.vector.agent.pairing_expiry.v1`

Steps:

1. Controller 调用 `ck.self.agent.command.provision`,pairing 窗口 12 小时,grant TTL 30 天。
2. Pairing 12 小时窗口过期，未提交 `ck.gate.account.command.pair_agent_key`。

Expected:

- 服务 MUST 自动写入 `ck.capability.revoke` 撤销 pending grant,agent status → `pairing_expired`。
- 重放 `ck.gate.account.command.pair_agent_key`(使用过期 pairing_request_id)MUST fail closed。
- Controller 可重新发起 `ck.self.agent.command.provision`,得到新 pairing_request_id;旧 agent_principal_id 与新 provisioning 不复用。

### 11.3 Vector: Agent Session Grant Replay Protection

`vector_id`: `ck.vector.agent.session_grant.replay.v1`

Steps:

1. Agent runtime 提交 `ck.gate.account.command.issue_session_grant`,`proof.proof_kind="agent_key_proof"`,proof 含 challenge / audience / request_canonical_digest / expires_at / signature。
2. 第二次提交同样的 proof(同样 challenge / digest / signature)。
3. 提交一份 audience 改成另一 service 的 proof。
4. 把 proof.signature 改写但 challenge 不变。

Expected:

- 第 1 步 MUST 成功，服务端把 challenge 进入 replay table。
- 第 2 步 MUST fail closed(challenge 已使用)。
- 第 3 步 MUST fail closed(audience mismatch)。
- 第 4 步 MUST fail closed(signature 不验，且 challenge 仍 burnt)。

### 11.4 Vector: Controller Deactivate → Agent Session Cascade

`vector_id`: `ck.vector.agent.controller_lifecycle.v1`

Steps:

1. Controller 拥有 active agent `A`,A 持有未过期 session grant `S`。
2. Controller 进入 `deactivated`。

Expected:

- A 的 active session `S` MUST 在 revocation freshness window(≤ session TTL)内 fail closed。
- A 后续任何 `ck.gate.account.command.issue_session_grant` MUST fail closed。
- A 在已加入的 sidecar Circle 中由 reducer 主动 fan-out `ck.circle.member.state -> leave`；若该 Circle 为 MLS-backed，MLS group 进入新 epoch。

### 11.5 Vector: Act-on-behalf Attribution

`vector_id`: `ck.vector.agent.act_on_behalf.v1`

Steps:

1. Agent A 持 act-on-behalf grant `G`(scope: `ck.message.create` on Strand F,approval_required=true, expiry < 15 min)。
2. Agent A 提交 message,envelope `actor_id=controller`,`executed_by=A`,`authorization_ref=G`,`proof.verification_method` 解析到 A 的 agent key。
3. Receiver 校验。
4. 第二次重用同一 approval nonce。

Expected:

- 第 3 步 MUST 校验 `executed_by` ↔ proof key 一致、`authorization_ref` 覆盖 `ck.message.create` + Strand F + 未过期；通过则接受。
- Reducer 写入 `actor_kind="agent"` projection(注意是 reducer-stamped,actor 提交侧不携带)。
- 第 4 步 MUST fail closed(`reason=approval_already_consumed`)。
- 客户端渲染 "Controller via Agent" 双重署名；不显示为纯 controller 行为。

### 11.6 Vector: Relation Reference Projection Indistinguishability

`vector_id`: `ck.vector.relation.reference_projection_indistinguishable.v1`

Steps:

1. Realm A 中存在 weak semantic Relation `R1`,目标指向 Realm B 内对象；调用者 C 可读 Realm A,但不能 discover / reference Realm B。
2. Realm A 中存在形态相同的 Relation `R2`,目标指向不存在或不可发现的 Realm / object id。
3. C 分别调用 Relation projection query、`ck.self.events.query.scan` raw event API、backfill pull 与 federation peer fanout 视图。
4. 在同一服务端测量点、同一请求类别与同一部署 profile 下，对 `R1` / `R2` 每类至少采样 30 次。
5. Auditor D 同时持有 source + target disclosure,读取 `R1` 的完整 canonical event。

Expected:

- C 对 `R1` / `R2` 均只能看到 `ReferenceProjectionStatus.locked` 或等价 locked stub,wire 字段集合、error envelope、metadata 集合必须相同。
- C 的视图 MUST NOT 泄露目标 `realm_id`、title、member_count、created_at、issuer set、preview 或任何能区分"目标存在 vs 不存在"的信息。
- raw event / backfill / federation fanout 对 C MUST 返回同一类 redacted event view 或 locked stub,不得暴露完整 `from_ref` / `to_ref` canonical bytes。
- 两类样本 p95 服务端耗时差异 SHOULD <= 50ms；声明高安全 profile 时 p99 MUST 落入同一 timing bucket。
- D MAY 取得完整 canonical bytes,但不得改变 C 对同一 Relation 的 locked projection shape。

### 11.7 Vector: Circle Directory Visibility Members Indistinguishable

`vector_id`: `ck.vector.circle.directory_visibility_members_indistinguishable.v1`

Steps:

1. Realm R 中存在 Circle C,`directory_visibility="members"`；viewer V 是 Realm member 但不是 Circle member。
2. V 分别用 Circle id、`short_name`、title prefix 与不存在的 Circle id 调用 Circle get / list / search / Realm directory projection。
3. V 读取 Realm seal public view commitment。
4. Circle member M 执行同一组调用。

Expected:

- 对 V,可见 Circle 与不存在 Circle 的响应 MUST 使用同一 envelope、字段集合和 timing bucket。
- V MUST NOT 看到 Circle title、display、short_name、member_count、created_by、member id、join history 或可枚举错误。
- V 的 stub 最多为 `{ "visibility": "locked", "opaque_commitment": "<fixed-length>" }` 或等价字段集合；`opaque_commitment` MUST 固定长度、不可逆、不可由 title / short_name / member set 枚举。
- Realm public seal 只暴露固定 cadence 的 opaque commitment,不得反映真实 Circle 活动频率。
- M MAY 看到 policy 允许的 Circle metadata,但不得改变 V 的不可区分性要求。

### 11.8 Vector: Sidecar Circle Idempotent Ensure

`vector_id`: `ck.vector.sidecar.ensure_idempotent.v1`

Steps:

1. Alice 的两台设备并发调用 `ck.self.agent.sidecar_thread.command.ensure` 同一 `context_ref`。
2. 同一 Alice 第三次调用 `ensure`(同样 context_ref),`addressed_agent_principal_ids` 列表不同。
3. Alice 在另一 context_ref 调用 ensure(同 Realm)。

Expected:

- 第 1 步并发 MUST 收敛到单一 sidecar Circle 与单一 sidecar private Strand;两个请求返回 bit-identical typed IDs;不出现 `failed_precondition`。
- 第 2 步 MUST 复用既有 Circle 与 Strand,addressed list 不持久化到 Circle/Strand/Relation;只影响本次 notification fanout。
- 第 3 步 MUST 复用既有 Circle(per_realm_controller_agent_pool),创建新 sidecar private Strand。

### 11.9 Vector: Existence Privacy

`vector_id`: `ck.vector.sidecar.existence_privacy.v1`

Steps(均以 non-sidecar-member 视角):

1. `ck.self.events.stream.subscribe` / `ck.self.events.query.scan` 目标 Realm。
2. 对 `to_ref=<target_message_id>` 的 relation query。
3. Realm directory 调用。
4. 触发目标 Strand 的 notification fanout。
5. 读取目标 Realm default seal leaf 明文 metadata。

Expected:

- 第 1 步返回 zero events referencing sidecar Circle / Strand / Relation。
- 第 2 步看不到 `agent_sidecar_of` 边。
- 第 3 步 zero hits for sidecar Circle title / display / short_name / member_count。
- 第 4 步 sidecar 内 `ck.message.create` 不触发任何 target Strand member 的 notification。
- 第 5 步 sidecar `effective_scope=circle` event 不出现在 default seal leaf 明文中；只能作为 opaque commitment。

### 11.10 Vector: Eligibility 三态 + Revocation 闭环

`vector_id`: `ck.vector.sidecar.eligibility_states.v1`

Steps:

1. Alice 有 agents `{S, R}`。S 已 paired (`active`),R 未发布 KeyPackage(eligible but pending join)。
2. Alice 调用 ensure。
3. R 发布 KeyPackage,服务端 async reconcile。
4. Alice 调用 `ck.self.agent.command.deactivate` 对 R。

Expected:

- 第 2 步 ensure SHOULD succeed。MLS-backed sidecar Circle 的 response 携带 `pending_member_reconciliations: [{agent_principal_id: R, reason: missing_mls_keypackage}]`；plaintext sidecar Circle 不需要 KeyPackage，但仍必须等待 Circle membership active。
- 第 3 步在 MLS-backed sidecar Circle 中，R 通过 MLS Welcome 加入，得到 join 之后的 future epoch keys(MUST NOT 获得 join 之前的 epoch keys)；plaintext sidecar Circle 中，R 只获得从 membership active frontier 之后的投递 / 查询资格。
- 第 4 步 reducer 主动 fan-out `ck.circle.member.state` 把 R 标记为 `leave`；若该 Circle 为 MLS-backed，MLS group 进入新 epoch。后续 R 的 `agent_key_proof` MUST fail closed,sidecar 写入全部拒绝。

### 11.11 Vector: Multi-Agent Publish Attribution

`vector_id`: `ck.vector.sidecar.multi_agent_publish.v1`

Steps:

1. Sidecar Circle 含 Alice + `{S, R}`。S 与 R 都在 sidecar private Strand 中产生协作内容。
2. S 调用 publish capability action,生成目标 Strand `ck.message.create`,attribution 设 `executed_by=S` + `authorization_ref=G_S`。
3. R 同时尝试 publish 含 S 部分内容的另一条消息。

Expected:

- 第 2 步 `actor_id` / `executed_by` MUST 是 S 单一 DID,而非 "agent group"。
- 第 3 步若 R 的 grant 不覆盖该内容或 R 未持 fresh approval,MUST fail closed。R 通过自己的 grant 可独立发布，但 attribution 仍是 R 单一 DID;不得复合 S+R。

### 11.12 Vector: Participation Ceiling Tighten-Only

`vector_id`: `ck.vector.agent.participation.ceiling_tighten.v1`

参见 [`../models/realm-and-space.md` §2.2](../models/realm-and-space.md)、[`../models/circle.md` §7](../models/circle.md)、[`../models/strand-and-message.md` §9.4](../models/strand-and-message.md)。

Preconditions:

- 部署顶层 ceiling 全 `false`。Realm `R` 的 `ck.realm.policy_components.agent_participation.native_agent = {reply:true, accept_third_party_mention:true, act_on_behalf:false}`。

Steps:

1. Circle `C`(父级为 `R`)写入 `agent_participation = {reply:true, accept_third_party_mention:false, act_on_behalf:false}`。
2. Strand `F`(`scope_circle_id=C`)写入 `agent_participation = {reply:true, accept_third_party_mention:false, act_on_behalf:false}`。
3. 变体 A：Circle `C` 尝试写入 `act_on_behalf:true`(放宽父 Realm `native_agent.act_on_behalf=false`)。
4. 变体 B：Strand `F` 尝试写入 `accept_third_party_mention:true`(放宽父 Circle `C` 的 `false`)。

Expected:

- 第 1、2 步 MUST 接受(每一位 ⊆ 父级 ceiling)。
- 变体 A、B MUST fail closed(`failed_precondition`, `reason="agent_participation_ceiling_widen"`)，与 [`../models/circle.md` §7](../models/circle.md) 的 floor downgrade 同形。
- 未显式声明 `agent_participation` 的内层 scope 继承父级 ceiling(不放宽)；effective ceiling 以从 Strand→Circle→Realm→deployment 逐级按位 AND 求值，对违反不变量的历史数据 fail closed。

### 11.13 Vector: Participation Effective = Ceiling ∩ Selection

`vector_id`: `ck.vector.agent.participation.effective_intersection.v1`

参见 [`../authz/capabilities.md` §5.4](../authz/capabilities.md)、[`../identity/key-management.md` §3.6.1](../identity/key-management.md)。

Preconditions:

- Realm `R` 的 `native_agent` ceiling `{reply:true, accept_third_party_mention:true, act_on_behalf:false}`。Agent `A` 为 controller `Alice` 的 active native personal agent。

Steps:

1. Alice 调用 `ck.self.agent.participation.set`，scope=`R`，selection=`{reply:true, accept_third_party_mention:false, act_on_behalf:true}`。
2. 服务端求 effective selection = controller selection ∩ effective ceiling ∩ agent capability intersection。
3. 变体 A：之后 Realm ceiling 把 `reply` 收紧为 `false`。
4. 变体 B：controller selection 来源缺失或 unknown。

Expected:

- 第 2 步 effective = `{reply:true, accept_third_party_mention:false, act_on_behalf:false}`(`act_on_behalf` 被 ceiling 封掉)。`reply` effective=true MUST 物化为一条 subject=`A`、`actions=[ck.message.create, ck.reaction.add]`、resource selector=scope `R` 的 `ck.capability.grant`；`act_on_behalf` effective=false MUST NOT 物化 act-on-behalf grant。
- 物化是幂等的：重复 set 收敛到同一 grant 集合；selection 改变导致的 grant 增删 MUST atomic，不得留半物化状态。
- 变体 A：`reply` effective 翻为 `false` 后 MUST `ck.capability.revoke` 对应 grant。
- 变体 B：任一来源缺失或 unknown，对应位 MUST fail closed 为 `false`。

### 11.14 Vector: Participation Selection Within Ceiling

`vector_id`: `ck.vector.agent.participation.selection_within_ceiling.v1`

参见 [`../sync/service-surface.md` §10.1](../sync/service-surface.md)。

Preconditions:

- Realm `R` 的 `native_agent` ceiling `{reply:true, accept_third_party_mention:false, act_on_behalf:false}`。

Steps:

1. Controller 调用 `ck.self.agent.participation.set`，scope=`R`，selection=`{reply:true, accept_third_party_mention:true, act_on_behalf:false}`。
2. 变体 A：调用方不是该 agent 的 controller。
3. 变体 B：该 agent 非 active(`paused` / `deactivated` / `pairing_expired`)。
4. 变体 C：scope 不可解析，或 controller 非该 Realm active member。

Expected:

- 第 1 步 MUST fail closed(`failed_precondition`, `reason="agent_participation_exceeds_ceiling"`)，并在 error detail 中列出被封顶的位(`accept_third_party_mention`)，使 UI 能解释“为何不能开启”；MUST NOT 物化任何 grant。
- 变体 A、B、C MUST fail closed。`set` 仅 controller 可调用；`get` 可由 controller 或该 agent runtime 调用。

### 11.15 Vector: Participation Session Overlay

`vector_id`: `ck.vector.agent.participation.session_overlay.v1`

参见 [`../sync/service-surface.md` §10.1](../sync/service-surface.md)。

Steps:

1. Agent runtime 调用 `ck.gate.account.command.issue_session_grant`，`proof.proof_kind="agent_key_proof"`，`agent_scope_request` 覆盖某 participation-aware scope。
2. 服务端签发 session，响应 `scope_details.participation[]`。
3. runtime 收到 `reply=false` 的 scope 后仍尝试 `ck.message.create`(模拟 runtime bug)。

Expected:

- 第 2 步 `scope_details.participation[]` 每个条目 MUST 与 `agent-operations.schema.json#/$defs/agent_participation_entry`(`{participation_scope, selection, ceiling, effective}`)同构，而非扁平三位；承载的是已解析 effective 策略。
- runtime MUST 把该数组视为本 session 行为契约。但它不是安全边界：第 3 步即使 runtime 越权，reducer 因无对应 `ck.message.create` grant MUST `failed_precondition`；第三方 mention 在 dispatcher gate 已被拦下；`act_on_behalf` 越权被 receiver 的 `executed_by`/`authorization_ref` 校验拒绝。

### 11.16 Vector: Participation Third-Party Mention Gate (Non-Retroactive)

`vector_id`: `ck.vector.agent.participation.third_party_mention_gate.v1`

参见 [`../models/strand-and-message.md` §9.4.5](../models/strand-and-message.md)。

Preconditions:

- Agent `A` 为 controller `Alice` 的 active native personal agent，有权读取 Strand `F`。`F` 的 effective `accept_third_party_mention=false`。

Steps:

1. 非 controller 的 `Bob` 在 `F` 发 `ck.message.create`，mention target=`A`。
2. controller `Alice` 自己在 `F` 发 mention target=`A`。
3. Alice 把 `F` 的 effective `accept_third_party_mention` 翻为 `true`，`A` 上线同步。
4. 翻转后 `Carol`(非 controller)再发 mention target=`A`。

Expected:

- 第 1 步 MUST NOT 为 `A` 派生任何 mention notification、inbox row、push wakeup，也 MUST NOT 把该 mention 纳入 `A` 的 `ck.self.events.subscribe` 投影；抑制只针对 `A`，对 message 的其他 human target、shared history、其它投影无影响。
- 第 2 步照常投递(controller 自己的 mention 不受此 gate，仍受 `A` 是否被授权读取该 scope 约束)。
- 第 3 步翻转 **非追溯**：第 1 步发生在 `false` 期间的历史 mention，翻转为 `true` 后对 `A` 仍 MUST 零记录(notification / inbox row / `ck.self.events.subscribe` 投影皆无)。
- 第 4 步在 `true` 期间的第三方 mention 照常投递，并受 `level=muted`、blocklist、DND、rate-limit 等既有更高优先级规则约束。

## 12. Media Service Binding Vectors

本节列出 `ck.profile.media_service_binding.v1` 的核心 conformance 向量。完整 fixture 与执行脚本在 candidate 阶段补完；以下为 normative steps + expected outcomes 的最小契约。详见 [`../crypto-media/media-service-binding.md`](../crypto-media/media-service-binding.md) §2 / §3 / §5–§8 与 [`../crypto-media/call-state.md`](../crypto-media/call-state.md) §4。

### 12.1 Focus Selection — Oldest Membership Wins

`vector_id`: `ck.vector.media_binding.focus_selection_oldest_membership.v1`

Steps:

1. Alice 与 Bob 加入同一 call；Alice 早于 Bob，`Alice.foci_preferred=[fra-1, us-east-1]`，`Bob.foci_preferred=[us-east-1, fra-1]`。
2. 首个 `ck.call.state` 事件 commit。

Expected:

- `session_focus` MUST 为 `fra-1`（Alice 是 oldest member，胜出）；`Bob.foci_preferred[0]` 不参与决策。
- 后续 token exchange 请求 `focus_id=us-east-1` MUST 被 issuer 以 `focus_mismatch` 拒绝。

### 12.2 Session Focus — No Split Brain

`vector_id`: `ck.vector.media_binding.session_focus_no_split_brain.v1`

Steps:

1. `session_focus=fra-1` 已 committed。
2. Carol 加入，本地 `fra-1` connect 失败（network 中断）。

Expected:

- Carol MUST NOT silent fallback 到其它 focus；MUST 以 `focus_unavailable_for_client` 向用户暴露失败。
- 任何后续 `ck.call.state` 事件试图改写 `session_focus` 为 `us-east-1` MUST 被 reducer 拒绝 `session_focus_already_committed`。

### 12.3 Token Exchange — Minimal Fields

`vector_id`: `ck.vector.media_binding.token_exchange_minimal.v1`

Steps:

1. Client POST `/_cokret/self/rtc/token` with the minimum required fields `(realm_id, call_id, actor_id, device_id, focus_id)`。
2. Issuer 返回 200 with `backend_token` / `participant_identity` / `participant_binding` / `expires_at` / `service_signature`。

Expected:

- `expires_at - now` MUST ≤ 600s（SHOULD ≤ 300s）。
- `participant_binding.scheme` MUST = `ck.media.participant_binding.v1`。
- `service_signature.kid` 与 `participant_binding.issuer_kid` MUST 解析到当前 epoch `ck.realm.media_service.service_id`。

### 12.4 Token Issuer — Unauthorised DID Rejected

`vector_id`: `ck.vector.media_binding.token_issuer_unauthorised.v1`

Steps:

1. 攻击者 DID `did:web:rogue.example` 模拟 token issuer 签发一个语法合法的 token。
2. Client 收到该响应。

Expected:

- Client MUST 拒绝并报 `token_issuer_unauthorised`，不得尝试连接 `connect_url`。

### 12.5 Participant Binding — Required

`vector_id`: `ck.vector.media_binding.participant_binding_required.v1`

Steps:

1. Token issuer 返回 response 缺失 `participant_binding`，或 `participant_binding.sig` 无效。
2. Client 试图把它写入 `ck.call.state.participants[]`。

Expected:

- Client MUST 拒绝该 token，不发起 `ck.call.state` 事件。
- 即便强行提交，reducer MUST `failed_precondition` `reason=participant_binding_invalid`。

### 12.6 Unknown Focus Type — Fail Closed

`vector_id`: `ck.vector.media_binding.unknown_type_fail_closed.v1`

Steps:

1. Realm policy 中某 `foci[].type = "experimental-x"`（unregistered）。
2. Client SDK 尝试解析。

Expected:

- Client MUST 报 `unknown_focus_type` 并拒绝把该 focus 用作 session_focus；MUST NOT 把 `backend_token` 透传到任意 SDK。

### 12.7 E2EE Key Source — MLS Exporter Only

`vector_id`: `ck.vector.media_binding.e2ee_key_source.v1`

Steps:

1. LiveKit Cloud key escrow 试图通过 backend channel 注入 SFrame key。
2. Client binding adapter 收到非 [`media-service-binding.md`](../crypto-media/media-service-binding.md) §8.1（E2EE Key Injection 通用契约）来源的 key。

Expected:

- Client MUST 拒绝该 key 并报 `e2ee_key_source_unauthorised`。
- 唯一合法 key 来源是 MLS-Exporter（label `ck-rtc-frame-key/v1`, length=19 bytes, Context=`canonical_json({realm_id, call_id, focus_id, epoch_id, participant_identity, device_id})`, KDF.Nh=32 bytes），其中 `participant_identity` / `device_id` 取自已验证的 `ck.call.state.participants[]` 与 `participant_binding`。
- 负向覆盖：以下派生 MUST 同样 fail closed 报 `e2ee_key_source_unauthorised`——(a) `Context=""`（空 Context）；(b) 缺少 sender 字段（`participant_identity` / `device_id`）；(c) 仅绑定 `epoch_id` 而不含完整 sender-bound Context。

### 12.8 Participant Identity — Cross-Check

`vector_id`: `ck.vector.media_binding.participant_identity_unrecognised.v1`

Steps:

1. Backend signal `ParticipantConnected` with `participant_identity=ck:rtc_participant:<unknown>`，无对应 `ck.call.state.participants[]` 项。

Expected:

- Client MUST 拒绝为该 participant 建立媒体流（不收音、不订阅 video），报 `participant_identity_unrecognised`。

### 12.9 Recording Artifact — Via Cokret Blob Pipeline

`vector_id`: `ck.vector.media_binding.recording_artifact_via_cokret_blob.v1`

Steps:

1. LiveKit Egress 配置指向非 Cokret endpoint（如 `s3://livekit-cloud-recordings/...`）。
2. Recording 完成。

Expected:

- Client MUST 检测 Egress destination 不是 Cokret media service authenticated upload endpoint，fail closed `recording_artifact_pipeline_bypassed`。
- 合法路径：Egress → Cokret blob upload → `ck.call.state` 写 `recording_state="ready"` + content digest。

### 12.9.1 Recording Exporter Label — Dedicated Recording Context

`vector_id`: `ck.vector.media_binding.recording_exporter_label.v1`

Steps:

1. LiveKit Egress 通过 Cokret proxy 上传合法 recording artifact。
2. Artifact encryption metadata 声称 key 来自 MLS exporter，但使用 SFrame label `"ck-rtc-frame-key/v1"` 或空 Context。
3. Producer 重新上传同一 artifact，使用 label `"ck-rtc-recording-key/v1"`，Context 为 canonical JSON `{realm_id, call_id, focus_id, recording_id, media_service_did, recording_start_event_id}`。

Expected:

- 第 2 步 MUST 拒绝；SFrame key 和 recording key 不得 label/Context 复用。
- 第 3 步 MAY accepted，前提是 Cokret blob pipeline、capability proof 与 `ck.call.state` lifecycle 绑定同时通过。

### 12.10 Call State — Participant Binding Invalid

`vector_id`: `ck.vector.call_state.participant_binding_invalid.v1`

Steps:

1. Producer 构造一个 schema 合法的 `ck.call.state` 事件（payload 通过 `call_state_payload` typed schema），其 `participants[0].participant_binding` 含全部必填字段。
2. 依次构造四个变体，每个仅破坏 §11.1 reducer 校验中的一项：
   - (a) `participant_binding.issuer_kid` 解析到的 service DID 不在当前 epoch `ck.realm.media_service.service_id`；
   - (b) `participant_binding` 的 `realm_id` / `call_id` / `focus_id` / `actor_id` / `device_id` / `participant_identity` 中某一项与该 participant entry 不一致；
   - (c) `participant_binding.expires_at` ≤ 事件 `created_at`（已过期 binding）；
   - (d) `participant_binding.sig` 验签失败。
3. 各变体分别提交 reducer。

Expected:

- 每个变体 MUST `failed_precondition` `reason=participant_binding_invalid`；wire-level typed schema 通过不豁免 reducer 的语义校验。
- 反例（control）：四项全部满足时，同一事件 MUST accepted。

### 12.11 Call State — Initial State Gate

`vector_id`: `ck.vector.call_state.initial_state_accepts_allowed.v1`

Steps:

1. 对同一新 `call_id` 分别提交首条 `ck.call.state`，`state` 为 `scheduled`、`ringing`、`connecting`。
2. 对另两个新 `call_id` 分别提交首条 `ck.call.state`，`state` 为 `active` 与 `ended`。

Expected:

- 前三条 MUST accepted，并各自建立 `ck.component.call.state.v1` 的初始 fsm cell。
- `active` 与任一终态作为首状态 MUST `failed_precondition`，`reason_code=call_state_transition_invalid`。

### 12.12 Call State — Transition Matrix

`vector_id`: `ck.vector.call_state.transition_matrix.v1`

Steps:

1. 以 `scheduled`、`ringing`、`connecting`、`active` 四个非终态为 `from`，逐条提交 [`call-state.md` §4.2](../crypto-media/call-state.md) 表中列出的合法后继。
2. 对每个非终态提交至少一个不在合法后继集合内的 `to`，例如 `scheduled -> active`、`ringing -> scheduled`、`connecting -> cancelled`、`active -> ringing`。

Expected:

- 表中每条合法边 MUST accepted，并推进同一 `call_id` 的 fsm cell。
- 非终态非法边 MUST `failed_precondition`，`reason_code=call_state_transition_invalid`；不得误报为 `call_state_terminal`。

### 12.13 Call State — Terminal Absorbing

`vector_id`: `ck.vector.call_state.terminal_absorbing.v1`

Steps:

1. 构造四个 call，使其 accepted head 分别为 `ended`、`missed`、`failed`、`cancelled`。
2. 分别尝试从这些终态提交任何其它 `state`，包括另一个终态和非终态。

Expected:

- 每个终态转出 MUST `failed_precondition`，`reason=call_state_terminal`。
- reducer MUST 保留原终态 head，不得产生回退、替换或 winner。

### 12.14 Call State — Same Transition Replay

`vector_id`: `ck.vector.call_state.replay_same_state_noop.v1`

Steps:

1. 在同一 accepted basis 上提交 `ringing -> connecting`。
2. 以相同 `from`、相同 `to`、相同 `call_id` 重放等价转换（不同传输重试或 duplicate submit）。

Expected:

- 重放 MUST 是幂等 no-op：结果仍为 `connecting`，不产生 sibling conflict。
- 实现 MAY 返回 duplicate / accepted-noop 等本地结果，但 MUST NOT 返回 `call_state_transition_invalid`。

### 12.15 Call State — Concurrent Sibling Bottom

`vector_id`: `ck.vector.call_state.concurrent_sibling_bottom.v1`

Steps:

1. 同一 `call_id` 当前 accepted state 为 `ringing`。
2. 在同一 CBA basis 上并发提交 sibling transition A: `ringing -> active` 与 B: `ringing -> missed`。

Expected:

- `ck.component.call.state.v1` 的 `fsm` join MUST 返回 `Bottom{kind="conflict"}`，并按 `bottom=reject` 暴露 `failed_bottom` / diagnostic。
- 实现 MUST NOT 用 HLC、`created_at`、actor id、event id、event digest、数据库顺序或接收顺序选择 `active` 或 `missed` 作为 winner。
- 后续依赖该 call state 的写入 MUST fail closed，直到显式 recovery 在新的 accepted basis 上修复冲突。

### 12.16 Call State — Recording Retention & Audit Lock

`vector_id`: `ck.vector.call_state.recording_retention_lock.v1`

Steps:

1. Producer 提交 `ck.call.state`，`recording_state="ready"`，`recording_result.retention` 含 `retention_expires_at`（未来）、`deletion_trigger="retention_expiry"`、`audit_lock=true`。
2. 在 `retention_expires_at` 之前尝试删除 artifact。
3. 在 `retention_expires_at` 之后但 `audit_lock` 未解除时再次尝试删除。
4. 提交一条 `recording_state="recording"` 的 `ck.call.state`，其 `recording_result.retention.consent_confirmed` 缺失或为 false。

Expected:

- 第 2、3 步删除 MUST 被拒绝 `legal_hold_active`（audit_lock 优先于 TTL 与 capability）。
- 第 4 步 MUST `failed_precondition` `reason_code=recording_consent_required`。
- 反例（control）：`audit_lock=false` 且已过 `retention_expires_at`、`deletion_trigger=retention_expiry` 时删除 MAY accepted；`recording_state="recording"` 且 `consent_confirmed=true` 时写入 MUST accepted。

### 12.16.1 Call State — Recording Result Artifact Shape

`vector_id`: `ck.vector.call_state.recording_result_artifact_shape.v1`

Steps:

1. Producer 提交 `ck.call.state`，`recording_state="ready"`，但 `recording_result.artifact` 缺失。
2. Producer 提交 `recording_result.artifact`，但其中 `schema` 不是 `ck.schema.call_recording_artifact.v1`，或 `recording_id` / `recording_start_event_id` 与 `recording_result` 绑定不一致。
3. Producer 提交 artifact，`encryption.exporter_label` 不是 `"ck-rtc-recording-key/v1"`，或 `encryption.context` 缺少 `{realm_id, call_id, focus_id, recording_id, media_service_did, recording_start_event_id}` 中任一字段。
4. Backend 尝试在 result / artifact 中携带直出 recording URL、S3/GCS/LiveKit Cloud destination，或缺失 `recording_initiator_capability_ref`。
5. Retention 到期或 manual delete 触发删除，artifact `deletion_audit.trigger` 与 `retention.deletion_trigger` 不一致，或 `outcome="completed"` 但缺少 `erasure_receipt_ref`。
6. Producer 提交合法 artifact：`schema="ck.schema.call_recording_artifact.v1"`，绑定同一 `realm_id` / `call_id` / `recording_id` / `recording_start_event_id`，通过 Cokret blob pipeline，使用 `"ck-rtc-recording-key/v1"` 与完整 Context，携带 retention、capability ref；删除完成时携带同 trigger 的 `deletion_audit` 与 `ck.schema.erasure_receipt.v1` 引用。

Expected:

- 第 1–5 步 MUST reject 或 fail closed；直出 URL / 外部 destination MUST 报 `recording_artifact_pipeline_bypassed`，artifact shape 或绑定不一致 MUST `schema_violation`。
- 第 5 步若 `audit_lock=true`，MUST 优先拒绝 `legal_hold_active`，不得因为 retention 到期或 manual capability 放行。
- 第 6 步 MAY accepted，前提是 Event Envelope、capability、blob metadata、artifact schema、exporter label/context 与 erasure receipt 绑定全部通过。

### 12.17 Call State — Transcribe Lifecycle & Key Source

`vector_id`: `ck.vector.call_state.transcribe_lifecycle.v1`

Steps:

1. 不具 `ck.call.transcribe` 的 actor 发起 `ck.call.recording.start{capture_kind="transcript"}`。
2. 具 `ck.call.transcribe` 的 actor 发起 transcript start，artifact 加密 key 声称来自 MLS exporter 但复用 SFrame label `"ck-rtc-frame-key/v1"` 或空 Context。
3. 同一 artifact 改用 label `"ck-rtc-transcript-key/v1"`、`Context=canonical_json({realm_id, call_id, focus_id, recording_id, media_service_did, transcript_start_event_id})` 重新上传，并通过 `ck.call.state` 写 `transcript_state="ready"`。

Expected:

- 第 1 步 MUST 拒绝 `transcription_denied`。
- 第 2 步 MUST 拒绝 `transcription_artifact_pipeline_bypassed`；transcript key 不得与 SFrame / recording label 复用或空 Context。
- 第 3 步 MAY accepted，前提 Cokret blob pipeline、capability proof 与 `ck.call.state` lifecycle 绑定同时通过。

### 12.18 Call State — Moderator Kick / Ban

`vector_id`: `ck.vector.call_state.moderator_kick_ban.v1`

Steps:

1. 不具 `ck.call.moderate` 的 actor 发出 `ck.call.signal{signal_type=moderation, action=kick}`。
2. 具 `ck.call.moderate` 的 moderator 对 `(target_actor_id, target_device_id)` 发 `kick`，并写 `ck.call.state.removed_participants[]`。
3. moderator 对某 `target_actor_id` 发 `ban`（`removed_participants[]` 项省略 `device_id`）。
4. 被 ban 的 actor 重新向 token issuer 兑换 join token。

Expected:

- 第 1 步 MUST 拒绝 `call_moderation_unauthorised`。
- 第 2 步被 kick 设备 MUST 拆除媒体；token issuer / SFU 据 `removed_participants[]` 拒绝其重接 `call_participant_removed`，但同 actor 重新发起新 join 不受阻。
- 第 4 步 token issuer MUST 拒绝 `call_participant_removed`，直到 ban 在本通话生命周期内被解除。

### 12.19 Call State — P2P→SFU Upgrade & Summary Gate

`vector_id`: `ck.vector.call_state.p2p_to_sfu_upgrade.v1`

Steps:

1. 以 `mode="p2p"` 起步的两人通话，第三个参与者将加入（active leg 达到 3）。
2. 触发升级：按 media-service-binding §5 oldest_membership 选举 `session_focus`，各设备经 `ck.call.signal{signal_type=focus_join}` 迁移。
3. 升级后提交 `ck.call.state.mode="sfu"`，随后人数回落到 2。
4. 通话到达终态 `ended` 后提交 `ck.call.summary{final_state="ended"}`；另对一个尚处 `active` 的 call 提交 `ck.call.summary`。

Expected:

- 第 1 步 MUST 触发升级，不得以 P2P / mesh 承载 3 人以上。
- 第 2 步 `session_focus` 由 oldest_membership 的 `foci_preferred[0]` 确定，无投票路径；committed 后 write-once。
- 第 3 步 `mode` MUST NOT 在同一生命周期内自动降级回 `p2p`。
- 第 4 步对终态 call 的 summary MUST accepted（write-once cell）；对 `active` call 的 summary MUST `failed_precondition` `reason_code=call_summary_invalid`。

## 13. History Visibility / Preview / History Sharing

### 13.1 Joined Visibility Denies Pre-Join History

`vector_id`: `ck.vector.history_visibility.joined_prejoin_denied.v1`

Setup:

1. Realm R 在 `T0` 的 effective `ck.realm.history_visibility.value = "joined"`。
2. Alice 是 active member 并提交 message `E_before`。
3. Bob 在后续 Seal `J` 才通过 `ck.member.state{membership=join}` 加入。
4. Bob 调用 backfill，范围覆盖 `E_before`。

Expected:

- Events / Sync Service MUST NOT 返回 `E_before` 的正文 payload 给 Bob；可以返回 redacted / locked stub 或 `history_not_visible`。
- E2EE Realm 中，任何 `ck.realm_key.share` 覆盖 `E_before` epoch 且 recipient=Bob MUST 被拒绝或对应 `ck.realm_key.withheld{withheld_reason_code="history_not_visible"}`。
- 如果 Realm 后续把 current visibility 改成 `shared`，该变化不 retroactively 重解释 `E_before` 的 `T0` 可见性；除非新 policy 明确声明受审计的 historical reclassification profile，否则 Bob 仍不能把 `E_before` 作为 verified timeline 明文展示。

### 13.2 Preview Token Is Stripped-State Only Unless Policy Allows More

`vector_id`: `ck.vector.preview.token_scoped_stripped_state.v1`

Setup:

1. Realm R 的 discoverability 为 `invite_only`，但 Alice 给 Bob 发出 `lt=preview` token。token payload 绑定 `target_digest`、`link_type="preview"`、`preview_policy_digest`、`aud=Bob`、短 TTL。
2. Effective `ck.realm.preview_policy.value.mode = "stripped_state"`，fields 只包含 `title`、`summary`、`join_rule`、`member_count_bucket`。
3. Bob 调用 `ck.find.directory.query.resolve_target`，携带 address 与 token。
4. 攻击者 Mallory 把同一 token 放到另一个 Strand address，或把 URL `lt` 改为 `invite`。

Expected:

- Bob MAY 收到 `realm_preview` / `object_preview` 中 policy 允许的 stripped fields。
- 响应 MUST NOT 包含正文历史、成员列表、policy 原文、`join_candidates[]` 或任何 write / membership grant。
- Mallory 的 scope-confused request MUST 返回与不存在不可区分的 `not_found`；resolver MUST 比对 token 内 `target_digest` 与 effective `link_type`，不得只校验 token 签名。

### 13.3 E2EE Pre-Join Key Share Requires History Sharing Policy

`vector_id`: `ck.vector.history_sharing.e2ee_prejoin_key_share_policy.v1`

Setup:

1. Realm R 为 `encryption_profile="mls_rfc9420"`，`history_visibility.value = "shared"`。
2. Alice 在 epoch 7 发送 `E_before`。
3. Bob 在 epoch 9 加入并成功处理 Welcome。
4. Key source S 尝试向 Bob 发送覆盖 epoch 7 的 `ck.realm_key.share`。

Expected:

- 若 effective `ck.realm.history_sharing_policy` 缺失，或 `pre_join_history="deny"` / `rule_only` 且无匹配 rule，S MUST withhold，reason SHOULD 为 `history_not_visible` 或 `policy_denied`。
- 若 policy 明确允许 `pre_join_history="allow_if_visibility_allows"`、`allowed_key_sources` 包含 S 的来源类型、receiver state 合法且 audit 要求满足，S MAY 发送 key share；payload `key_scope.policy_digest` MUST 覆盖该 policy root，`membership_frontier_digest` SHOULD 覆盖 Bob join frontier。
- Bob 客户端 MUST NOT 因 `history_visibility=shared` 自行推断 epoch 7 key；没有合法 key share 时，`E_before` 保持 `decryption_pending` / `decryption_failed`。

## 14. Encryption Floor Ratchet Vectors

加密能力轴（`encryption_profile`）与加密下限（`content_encryption_floor` / `metadata_encryption_floor`）分离；两个 floor 均二元（比较序 `allow_plaintext < e2ee_required`）、Realm 与 Circle 对称，且 effective floor 是单向 ratchet。本节固化 reducer 权威层的四个向量（完整语义见 [`../models/circle.md` §7](../models/circle.md)、[`../models/realm-and-space.md` §2.5](../models/realm-and-space.md)）。

### 14.1 Content Floor Downgrade Rejected

`vector_id`: `ck.vector.e2ee.content_floor_downgrade_rejected.v1`

Setup:

1. Realm R 的 effective `content_encryption_floor` 已达 `e2ee_required`(经 `ck.realm.policy_components` 写入)。
2. 后续 `ck.realm.policy_components` 把 `content_encryption_floor` 改回 `allow_plaintext`。

Expected:

- reducer MUST `failed_precondition`，reason=`content_encryption_floor_downgrade`。
- 抬高（`allow_plaintext` → `e2ee_required`）或维持同级 MUST 接受；只有降级被拒。

### 14.2 Metadata Floor Downgrade Rejected

`vector_id`: `ck.vector.e2ee.metadata_floor_downgrade_rejected.v1`

Setup:

1. Realm R 的 effective `metadata_encryption_floor` 已达 `e2ee_required`。
2. 后续 `ck.realm.policy_components` 把 `metadata_encryption_floor` 改回 `allow_plaintext`。

Expected:

- reducer MUST `failed_precondition`，reason=`metadata_encryption_floor_downgrade`。
- 与 content floor 同为单向 ratchet；抬高或同级接受，降级被拒。

### 14.3 In-Place E2EE Enable

`vector_id`: `ck.vector.e2ee.in_place_enable.v1`

Setup:

1. Realm R 以 `encryption_profile="mls_rfc9420"` + `content_encryption_floor="allow_plaintext"` 创建（钥匙在手、初期明文发送）。
2. 后续 `ck.realm.policy_components` 把 `content_encryption_floor` 抬到 `e2ee_required`。

Expected:

- reducer MUST 接受该原地升级（正向向量），无需重建 Realm 或 MLS group。
- 升级生效后，plaintext content 写入 MUST `failed_precondition`（reason=`content_encryption_floor_violation`），且 MLS governance send-pause 恢复完整约束。

### 14.4 Circle Content Floor Below Realm Rejected

`vector_id`: `ck.vector.circle.content_floor_below_realm_rejected.v1`

Setup:

1. 父 Realm 的 effective `content_encryption_floor` 为 `e2ee_required`（或 `encryption_profile="mls_rfc9420"`）。
2. `ck.circle.create` / `ck.circle.update` 声明 `encryption_profile="none"`，或 Circle `content_encryption_floor` 低于父 Realm effective floor。

Expected:

- reducer MUST `failed_precondition`，reason=`circle_encryption_below_realm_floor`。
- Circle floor 只能在父 Realm floor 之上收紧；`none` scope 无 MLS-backed effective_scope 可承载密文，故不得声明 `e2ee_required`。

## 15. Moderation / Policy Server / Key Backup / Federation Ingress Vectors

本节收拢治理域（content moderation、policy server、key backup）与 federation ingress 的 conformance 向量。每个 `vector_id` 均为规范性引用目标，登记于 [`vector-registry.json`](../../artifacts/registry/vector-registry.json)。

### 15.1 Vector: E2EE Franking Roundtrip

`vector_id`: `ck.vector.moderation.franking_roundtrip.v1`

本向量固化 [`content-moderation.md`](../governance/content-moderation.md) §3.4 的 franking 构造与验证 MUST：franking proof “MUST 在 canonical event routing metadata、ciphertext digest、AAD digest、sender claim、receiving service DID、接收时间与 `replay_nonce` 之上生成”；moderator 验证时 “MUST 检查 reporter 可见性、目标消息 accepted state、encrypted envelope digest、franking service signature、AAD / ciphertext digest 和 evidence package 签名”。

Steps：

- **Case A — roundtrip 正路径**：
  1. E2EE Realm 中 sender 发送密文消息；receiving service 按 §3.4 生成 `ck.moderation.franking_proof`（含 `routing_metadata_digest`、`ciphertext_digest`、`aad_digest`、`sender_claim`（仅 `mls_group_id_digest`，无 raw `mls_group_id` / 明文 `epoch`）、`received_by`、`received_at`、`replay_nonce`、`signature`，并通过 [`moderation-report.schema.json`](../../artifacts/schemas/moderation-report.schema.json) `franking_proof` 分支）。
  2. reporter 提交 `ck.self.moderation.command.report`，附加密 evidence package（加密给 `effective_scope` 对应 moderator audience）与该 `franking_proof`。
  3. moderator 按 §3.4.1 “Franking 信任链” 步骤 1–6 验证（receiving service DID 解析、verification method 在 `received_at` 有效且未撤销、service 在目标 Realm 被授权、payload hash 覆盖完整、`received_at` 时序新鲜度）。
- **Case B — 篡改 / 最小披露违反**：(a) `franking_proof.ciphertext_digest` 与目标 encrypted envelope digest 不一致；(b) `sender_claim` 携带 raw `mls_group_id` 或明文整数 `epoch`，或 proof 包含 plaintext body。

Expected：

- **Case A**：全部校验通过后，moderator MAY 把 `franking_proof` 视为可验证投递证明；evidence package MUST NOT 包含 Realm / Circle 历史 key、MLS epoch secret、exporter secret 或允许 moderator 解密未举报消息的材料；举报 MUST NOT 触发任何治理密钥释放（§3.4.1：MUST NOT 把 `ck.self.moderation.command.report` 自动升级为 `ck.audit.session.request`）。
- **Case B(a)**：任一 digest 环节不符时，moderator MAY 把材料作为人工线索，但 MUST NOT 将该 `franking_proof` 视为可验证投递证明。
- **Case B(b)**：schema / receiver MUST 拒绝携带 raw `mls_group_id`、明文 `epoch` 或 plaintext body 的 `franking_proof`（§3.4 最小披露 MUST NOT 条款）。

### 15.2 Vector: Moderation Appeal 状态转换原子性

`vector_id`: `ck.vector.moderation.appeal_atomicity.v1`

本向量固化 [`content-moderation.md`](../governance/content-moderation.md) §5.5.2 的 reducer 强制约束：“`ck.moderation.appeal.decision` `verdict=overturn` MUST 与一条 `ck.moderation.decision.lift`（target 等于 `decision_ref`）在同一 ordered submit batch 或同一 control transaction 中出现；否则 reducer 用 `appeal_overturn_missing_lift` 拒绝”；“`verdict=modify` MUST 与一条新的 `ck.moderation.decision`（其 `target_ref` 等于原 target）在同一 batch 中出现……reducer 校验 `modify_decision_ref` 与同 batch 新 decision 的 event id 一致”。

Steps（前置：appeal cell 已沿 §5.5.1 状态机 `submitted → under_review` 推进，reviewer ≠ 原 decision issuer）：

- **Case A — overturn 缺 lift**：reviewer 提交 `verdict=overturn` 的 `ck.moderation.appeal.decision`，但同一 ordered submit batch / control transaction 中**不**含 target 等于 `decision_ref` 的 `ck.moderation.decision.lift`；随后在另一次提交中补齐同 batch 的 decision + lift 对。
- **Case B — modify 引用不符**：reviewer 提交 `verdict=modify` 的 decision，`modify_decision_ref` 指向的事件不在同一 batch，或同 batch 新 `ck.moderation.decision` 的 `target_ref` 不等于原 target。

Expected：

- **Case A**：缺 lift 的提交 MUST 被 reducer 以 `appeal_overturn_missing_lift` 拒绝，appeal cell 保持 `under_review`，原 moderation decision 继续生效（不存在“上诉胜诉但原 decision 仍生效”的中间窗口，反向亦然）；补齐后的同 batch decision + lift MUST 原子接受，cell 转入 `decided` 且原 decision 解除。
- **Case B**：MUST 拒绝整个 modify 提交；不得出现“appeal 已 `decided` 但新 decision 缺失 / 指向错误”的部分状态。
- 两个 case 中 cell 状态机 MUST 遵循 §5.5.1 转换表（`submitted → under_review → decided → closed`）；跳跃转换 MUST `failed_precondition`。

### 15.3 Vector: Policy Decision 重放拒绝

`vector_id`: `ck.vector.policy_server.decision_replay_rejected.v1`

本向量固化 [`policy-server.md`](../authz/policy-server.md) §5 的反重放 / freshness MUST：“节点 MUST 拒绝过期 decision”；frontier 比较中“若本地 accepted authorization / policy / membership frontier 严格晚于 decision 绑定的 frontier……receiver MUST fail closed 并重新请求 `/_cokret/self/policy/check`；不得把旧 decision 复用到更新后的 auth state”。

Steps：

- **Case A — 过期 decision 重放**：一份签名有效的 allow decision 在 `expires_at` 之后被原样重放给 receiver。
- **Case B — auth state 前进后复用**：decision 签发后，本地 accepted auth state 观察到相关 grant revoke / membership 变化（`auth_state_digest` 与 decision 绑定值不再一致，且本地 frontier 严格晚于 decision frontier）；调用方尝试复用缓存中的该 decision（cache key 含 `auth_state_digest` 五元组，见 §5）。

Expected：

- **Case A**：receiver MUST 拒绝（`expires_at > now` 校验失败），不得以任何 TTL 宽限接受。
- **Case B**：cache hit 时 `auth_state_digest` constant-time 比较不一致 MUST 回退完整授权判定；本地 frontier 严格晚于 decision frontier 时 MUST fail closed 并重新请求 policy check，MUST NOT 把旧 allow decision 复用到更新后的 auth state。
- 两个 case 的拒绝 MUST NOT 推进任何依赖该 decision 的写入。

### 15.4 Vector: Request Canonical Digest 重算不符拒绝

`vector_id`: `ck.vector.policy_server.request_digest_recompute.v1`

本向量固化 [`policy-server.md`](../authz/policy-server.md) §5 的 transcript 绑定 MUST：“`request_canonical_digest` MUST 是 RFC 8785 JCS 在该请求 body 上的 SHA-256 digest”；接收方 MUST 校验 “`bound_to` 必须存在，且 `bound_to.realm_id` / `bound_to.actor_id` / `bound_to.action` / `bound_to.request_canonical_digest` 与本次 request 完全一致”。

Steps：

- **Case A — digest 不符**：调用方拿到一份对请求 body `B1` 签发的 decision（`bound_to.request_canonical_digest = JCS-SHA256(B1)`），将其附在内容已被修改的请求 body `B2` 上提交；receiver 对 `B2` 重算 JCS canonical digest。
- **Case B — control 正路径**：decision 的 `bound_to` 四元组与本次 request 重算结果完全一致，signature / `expires_at` / frontier 校验全部通过。

Expected：

- **Case A**：重算 digest ≠ `bound_to.request_canonical_digest`，receiver MUST 拒绝该 decision，不得信任 decision 自带的 digest 字段而跳过本地重算；按 service-private 算法（非 JCS）计算 canonical hash 的实现 MUST NOT 声明通过 v1 conformance。
- **Case B**：decision 接受（对照正样本）。
- `bound_to.realm_id` / `actor_id` / `action` 任一与本次 request 不一致时同样 MUST 拒绝（防止 allow decision 跨 (realm, actor) 上下文泄漏）。

### 15.5 Vector: Key Backup Unlock Proof 校验

`vector_id`: `ck.vector.key_backup.unlock_proof.v1`

本向量固化 [`key-management.md`](../identity/key-management.md) §7.7.1 / §7.8 的取回校验 MUST：取回完整 ciphertext 的协议操作是 `ck.self.keys.backups.command.unlock`（`POST /_cokret/self/keys/backups/{backup_id}/unlock`），unlock proof MUST 作为 request body 的 `proof` 字段提交；“服务端在返回完整 ciphertext 之前，MUST 校验该 unlock proof 与请求 session、caller、新设备 key、active-series record 和目标 envelope 一致；任一不符 MUST fail closed”；“`POST /_cokret/self/keys/backups/{backup_id}/unlock` 即便对自己的备份也 MUST 要求 fresh device proof……bearer token 单独到达 MUST 被拒绝”。

Steps：

- **Case A — 正路径**：恢复设备在 recovery session 内提交符合 `ck.schema.key_backup_unlock_proof.v1` 的 proof（绑定 `recovery_session_id`、`principal_id`、`requesting_device_id`、`backup_id`、`backup_class`、`series_id`、`ciphertext_digest`、`proof_kind`、`proof_digest`、`issued_at`），服务端用当前 session state 重建 transcript 比对 `proof_digest` 后返回 ciphertext；客户端 AEAD/HPKE open 后校验明文符合 `ck.schema.key_backup_plaintext.v1` 且 `backup_id` / `backup_class` / `series_id` / `series_seq` byte-for-byte 等于外层 envelope。
- **Case B — 绑定不符 / 凭证降级**：(a) proof 的 `ciphertext_digest` 指向另一 envelope，或 `requesting_device_id` 与本次 session 的新设备 key 不一致，或 `proof_digest` 与服务端重建的 transcript 不符；(b) 调用方仅携带 bearer token、无 fresh device proof 请求同一端点。

Expected：

- **Case A**：ciphertext 返回且明文校验通过；`items[].secret_id` / `item_type` 只作 keybag 内部路由，不得替代外层 envelope 的授权判断；明文 MUST 仅作本地瞬时材料，日志 / telemetry MUST NOT 记录 `secret_b64u`。
- **Case B(a)**：MUST fail closed，错误码取 `recovery_evidence_unbound` / `backup_frontier_stale` / `series_chain_broken` / `invalid_signature` 中对应稳定码；服务端 MUST NOT 采信客户端自报的 policy / session metadata。
- **Case B(b)**：MUST 拒绝；跨 actor 请求（envelope `actor_id` ≠ caller）MUST 返回 `forbidden` 且不得通过 metadata 暴露 envelope 是否存在。

### 15.6 Vector: KDF 下限不满足的新建 Envelope 拒绝

`vector_id`: `ck.vector.key_backup.kdf_floor_rejected.v1`

本向量固化 [`key-management.md`](../identity/key-management.md) §7.2 的 base 无条件 MUST 下限：“新创建的 `recipient_method="passphrase_kdf"` envelope MUST 满足以下机器下限（base v1 无条件要求……）：Argon2id `memory_kib >= 65536`、`iterations >= 3`、`parallelism >= 1`”；“如果平台限制只能使用 PBKDF2，新创建的 PBKDF2 envelope MUST 满足 `iterations >= 600000` 且 `digest_algorithm ∈ {sha256, sha384, sha512}`，并 MUST 在 backup metadata 中声明 `degraded_profile_reason`”。

Steps：

- **Case A — Argon2id 低于下限**：新建 `passphrase_kdf` envelope 声明 Argon2id `memory_kib = 32768`（或 `iterations = 2`、`parallelism = 0`）。
- **Case B — PBKDF2 低于下限 / 非法字段**：新建 PBKDF2 envelope 声明 `iterations = 310000`，或 `digest_algorithm` 不在 `{sha256, sha384, sha512}`，或使用非法字段 `params.hash` 代替 `params.digest_algorithm`。

Expected：

- **Case A / Case B**：receiver / 上传端点 MUST 拒绝该新建 envelope（schema 与 §7.2 机器下限同步编码于 `ck.schema.key_backup.v1`）；`params.hash` MUST 被 current parser reject。
- 对照正样本：Argon2id `memory_kib >= 65536` 且 `iterations >= 3` 且 `parallelism >= 1` 的 envelope，以及 `iterations >= 600000`、合法 `digest_algorithm` 且声明 `degraded_profile_reason` 的 PBKDF2 envelope MUST accept。
- Argon2id 可用时新建 envelope MUST NOT 默认选择 PBKDF2；未知 `encryption.kdf.name` MUST fail closed，不得回退到默认。

### 15.7 Vector: Federation Ingress 鉴权失败 Timing Bucket

`vector_id`: `ck.vector.federation.timing_bucket.v1`

本向量固化 federation ingress 鉴权失败族的响应不可区分性（[`federation.md`](../sync/federation.md) §3.2），采样口径按 [`relation.md`](../models/relation.md) §4.5 既有口径执行。

Steps：

1. 对同一 federation ingress endpoint（如 `POST /_cokret/peer/events`）分别触发鉴权失败族中的不同原因：(a) 未知 peer（`Source-Service-DID` 无法解析 / 不在任何 binding 中）；(b) 签名可解析但 source 未被目标 Realm policy / 本地 peer policy 授权；(c) 目标 Realm 或资源不存在。
2. 在同一服务端测量点、同一请求类别与同一部署 profile 下，对每类失败至少采样 30 次，记录 HTTP status、`reason_code`、响应字段集合与服务端处理时延（网络传输时间不计入服务端本地口径）。

Expected：

- 三类失败的对外响应 MUST 使用同一 HTTP status 与同一统一鉴权失败 `reason_code`（`error-code-registry` 已登记的统一码，如 `capability_denied`），error envelope 可见字段集合 MUST 相同，MUST NOT 携带 Realm / Actor / Event / binding / frontier 是否存在的任何可区分信息；真实失败原因 MUST 只写入接收方审计日志。
- timing 同桶判定按 [`relation.md`](../models/relation.md) §4.5 口径：每类 ≥ 30 次采样下，各失败类别两两之间 p95 处理时延差异 SHOULD ≤ 50ms；声明高安全 profile 时 MUST 使用 padding / jitter 使 p99 也落入同一 timing bucket。
- conformance runner MAY 在同一网络条件下补充端到端抽样，但判定以服务端本地口径为准。

失败条件：

- 任两类失败返回不同 status / `reason_code` / 字段集合，或错误 body 泄露目标是否存在。
- p95（或高安全 profile 下 p99）超出同桶判定，形成可观测的存在性 timing 侧信道。

### 15.8 Vector: Federation Reducer Profile Digest 计算与不一致拒绝

`vector_id`: `ck.vector.federation.reducer_profile_digest.v1`

本向量固化 [`federation.md`](../sync/federation.md) §4.1.1 的 `service_binding_ref.reducer_profile_digest` 计算规则与不一致时的整批拒绝语义。计算物唯一来源是 [`reducer-profile-registry.json`](../../artifacts/registry/reducer-profile-registry.json) 对应 `profile_id` row 的 `digest_input` 对象；canonical 编码按 [`encoding.md`](encoding.md) §2 的 Cokret canonical JSON。执行数据见 [`federation-fixture.json`](../../artifacts/fixtures/federation-fixture.json) 的 `reducer_profile_digest_federation_minimal` 与 `reducer_profile_mismatch` 两个 case。

Steps：

- **Case A — 计算正路径**：取 fixture case `reducer_profile_digest_federation_minimal` 的 `canonical_input`（即 registry 中 `ck.profile.federation_minimal.v1` row 的 `digest_input`），计算 `"sha256:" || lowercase_hex(sha256(canonical_json(digest_input)))`，与 `expected_digest` 逐字节比对。
- **Case B — 不一致整批拒绝**：按 fixture case `reducer_profile_mismatch` 构造 `POST /_cokret/peer/events` 批次，sender 声明的 `service_binding_ref.reducer_profile_digest` 与 receiver 对同一 Realm 重算结果不一致。

Expected：

- **Case A**：实现重算结果 MUST 等于 `expected_digest`（`sha256:1fa83b8ca1719c604c298d83e89b0456f3af5ed1382cf8dcb025b074a34e0109`）；实现 MUST 以 registry row 的 `digest_input` 为唯一计算物，不得改用本地配置对象、ServiceDescribe 摘要或手写 `{domain, profile}` 对象。
- **Case B**：receiver MUST 整批拒绝并返回 `reducer_profile_mismatch`，MUST NOT partial accept；缺少 registry row、`profile_id` 未声明、canonicalization 不支持或 digest suite 非 active `sha256` 时同样 MUST fail closed。

失败条件：

- Case A 重算值与 `expected_digest` 不符，或实现以非 registry `digest_input` 的对象作为计算物仍得到"匹配"结论。
- Case B 出现 partial accept，或拒绝时返回 `reducer_profile_mismatch` 之外的可区分错误形态。

## 16. Streaming Chunked AEAD Attachment Vectors

本节收拢分块流式 AEAD 加密附件 scheme `ck.blob.stream_aead.v1` 的 conformance 向量，固化 [`media-and-blob.md`](../crypto-media/media-and-blob.md) §3.2 形态选择与 §3.3 的分块构造 / nonce / AAD / 整体 digest / 解密验证 MUST。每个 `vector_id` 均为规范性引用目标，登记于 [`vector-registry.json`](../../artifacts/registry/vector-registry.json)；error envelope `reason_code` 取 [`error-code-registry.json`](../../artifacts/registry/error-code-registry.json) 已登记的稳定码。

### 16.1 Vector: Streaming AEAD Roundtrip

`vector_id`: `ck.vector.blob.stream_aead_roundtrip.v1`

本向量固化 §3.3.1 切分、§3.3.2 nonce 构造、§3.3.3 AAD 绑定、§3.3.5 整体 `ciphertext_digest` 语义与 §3.3.6 解密验证的正路径：明文按 `segment_size` 切成有序 segment（末段长度在 `1 .. segment_size`，可短于 `segment_size`），逐段独立 AEAD 加密、可分段下载并逐段增量校验，最终整体 `ciphertext_digest` 重算比对通过。

Steps：

1. 取一份明文，长度使 `segment_count == ceil(plaintext_size / segment_size)` 且末段严格短于 `segment_size`（含短末段路径）；envelope 走 [`blob.schema.json#/$defs/encrypted_attachment`](../../artifacts/schemas/blob.schema.json) 的 `ck.blob.stream_aead.v1` 分支，声明 `scheme`、`nonce_prefix`（per-object 随机，长度 `N_AEAD - 5`）、`segment_size`、`segment_count`、`ciphertext_digest`。
2. 对每个 segment 用同一 content key、nonce = `nonce_prefix || u32_be(segment_index) || last_segment_flag` 加密，并把 `segment_index` / `last_segment_flag`（及 §3.3.3 要求字段）纳入 AAD；末段 `last_segment_flag = 0x01` 且 `segment_index == segment_count - 1`。
3. 接收方按 `segment_index` 从 `0` 起严格升序分段下载（SHOULD 按 `segment_size` 整数倍偏移做 Range），逐段做 per-segment AEAD tag 校验并安全释放对应明文。
4. 全部 segment 接收完毕后，按 §3.3.5 对全部 segment 密文（每段含其 AEAD tag）按 `segment_index` 升序拼接重算 `ciphertext_digest`，与 envelope 声明值比对。

Expected：

- 逐段 AEAD tag 校验全部通过，整体 `ciphertext_digest` 重算等于 envelope 声明值；接收方还原出 byte-for-byte 等于原明文的内容，并仅在见到合法末段（`last_segment_flag=0x01` 且 `segment_index==segment_count-1`）后才标记附件完整。
- per-segment 增量校验提供边下边验，顶层 `ciphertext_digest` 提供整体完整性；二者都 MUST 校验通过才允许最终持久化 / 标记完整。
- 反例（顺带覆盖）：将任一 segment 密文整体替换为另一份相同 segment_index 的合法密文，使 per-segment tag 仍可能通过但拼接后整体 digest 不符时，§3.3.6 步骤 7 MUST 以 `digest_mismatch`（与 §5 一致）拒绝、丢弃全部明文、不渲染不持久化。

### 16.2 Vector: Streaming AEAD Truncation Rejected

`vector_id`: `ck.vector.blob.stream_aead_truncation_rejected.v1`

本向量固化 §3.3.6 步骤 4「缺末段拒绝」MUST：流在未出现合法末段时即终止（连接中断、`segment_count` 段已耗尽但末段 flag 仍为 `0x00`，或声明 `segment_count` 与实际不符）MUST 拒绝（`segment_stream_truncated`），并丢弃已释放 / 缓冲明文，不得把已得明文当作完整文件。

Steps：

- **Case A — 丢弃末段 / 末段 flag 仍为 0x00**：发送 `segment_count - 1` 段后流终止，从未出现 `last_segment_flag = 0x01` 的合法末段（或最后到达段的 flag 仍为 `0x00`）。
- **Case B — `segment_count` 段耗尽但无末段**：恰好接收声明 `segment_count` 段，但其中无任何段的 `last_segment_flag = 0x01`（声明数与实际末段缺失不符）。

Expected：

- **Case A / Case B**：接收方 MUST 以 `segment_stream_truncated` 拒绝，丢弃已释放 / 缓冲明文，MUST NOT 把已通过 per-segment 校验的部分明文当作完整文件持久化或标记完整。
- 在见到合法末段前接收方 MUST NOT 把附件视为已完整接收（§3.3.6 步骤 3）；Range / 流式播放下允许消费已通过 per-segment 校验的明文段，但最终持久化或标记完整前 MUST 完成整体 digest 校验（此处因末段缺失永不达成）。

### 16.3 Vector: Streaming AEAD Reorder / Replay Rejected

`vector_id`: `ck.vector.blob.stream_aead_reorder_rejected.v1`

本向量固化 §3.3.6 步骤 1「按序处理」与步骤 5「重复拒绝」MUST：`segment_index` 跳变 / 乱序 / 出现空洞 MUST 拒绝（`segment_sequence_invalid`）并丢弃已缓冲明文；同一 `segment_index` 出现多次 MUST 拒绝（`segment_replay`）。

Steps：

- **Case A — 乱序 / 跳变**：接收方在按 `segment_index` 升序消费过程中收到 `segment_index` 非连续递增的 segment（如在 index `k` 后到达 `k+2`，或先到 `k+1` 再到 `k`），形成空洞 / 跳变 / 乱序。
- **Case B — 重复段**：同一 `segment_index` 的 segment 出现两次（重放同一已消费段）。

Expected：

- **Case A**：MUST 以 `segment_sequence_invalid` 拒绝，并丢弃已缓冲明文，不得按到达顺序拼接 / 释放越序段。
- **Case B**：MUST 以 `segment_replay` 拒绝重复段。
- 两个 case 中，因 `segment_index` / `last_segment_flag` 同时进入 nonce 与 AAD（§3.3.2 / §3.3.3），重排、截断与末段伪造在 AEAD 层即应被拒绝（tag 校验失败）；conformance 判定以稳定 `reason_code` 为准。

### 16.4 Vector: Streaming AEAD Scheme Closure

`vector_id`: `ck.vector.blob.stream_aead_scheme_closure.v1`

本向量固化 §3.2 的 scheme 分派 fail-closed MUST 与 [`blob.schema.json#/$defs/encrypted_attachment`](../../artifacts/schemas/blob.schema.json) 的整文件 / 分块形态互斥 `oneOf`：接收方 MUST 按 envelope `scheme` 分派解密路径，遇到未知 `scheme` MUST fail closed（`unsupported_attachment_scheme`），不得回退到任何其它形态尝试解密；整文件形态（`nonce`）与分块形态（`nonce_prefix` / `segment_*`）字段互斥。

Steps：

- **Case A — 未知 scheme**：envelope 声明 `scheme` 为既非 `ck.blob.whole_file_aead.v1` 亦非 `ck.blob.stream_aead.v1` 的未知值（如 `ck.blob.stream_aead.v2`）。
- **Case B — 形态字段混用**：单个 envelope 同时携带整文件形态字段 `nonce` 与分块形态字段 `nonce_prefix`（及 `segment_size` / `segment_count`），违反 `encrypted_attachment` 的 `oneOf`。

Expected：

- **Case A**：接收方 MUST fail closed，返回 `unsupported_attachment_scheme`，MUST NOT 回退到 `ck.blob.whole_file_aead.v1` 或任何其它形态尝试解密。
- **Case B**：schema 校验 MUST 失败（`oneOf` 两个分支互斥，同时含 `nonce` 与 `nonce_prefix` / `segment_*` 不命中任一分支）；接收方 MUST 拒绝该 envelope，不得择一形态解释。
- 对照：缺省 `scheme` 时 MUST 按 `ck.blob.whole_file_aead.v1`（整文件形态、单 `nonce`）解释（§3.2 向后兼容条款），不属于本反例。

## 17. Last-Resort KeyPackage Vectors

本节收拢可选 last-resort KeyPackage 语义的 conformance 向量，固化 [`encryption-and-audit.md`](../crypto-media/encryption-and-audit.md) §2.6.2 的复用 / 幂等 consume / 强制轮换 / Realm affinity / 可选协商 MUST。该能力由 feature `ck.feature.mls_last_resort_keypackage.v1` 门控（server describe `supported_features`）。每个 `vector_id` 均为规范性引用目标，登记于 [`vector-registry.json`](../../artifacts/registry/vector-registry.json)。

### 17.1 Vector: Last-Resort Claim And Reuse

`vector_id`: `ck.vector.keypackage.last_resort_claim_and_reuse.v1`

本向量固化 §2.6.2 的优先序、复用与幂等 consume MUST：池中存在普通包时 claim MUST 优先返回普通包，仅普通包池空时 MAY 返回 `last_resort=true` 包；last-resort 包 MUST NOT 进入单次 `consumed` 终态，在 `published` 与多次 `claimed` 之间循环；`ck.keys.keypackages.consume` 对 last-resort `keypackage_ref` MUST 被识别为幂等（返回成功但不改 `published`，不得返回 `keypackage_already_consumed`）；每次消费 MUST emit append-only 审计记录。

Steps（前置：服务端在 `ck.server.query.describe.supported_features` 声明 `ck.feature.mls_last_resort_keypackage.v1`，目标 Realm policy 允许 last-resort join）：

1. 该 Realm 的普通（单次）KeyPackage 池耗尽；requester 发起 claim。
2. 同一 `intended_realm_id` 内对该 last-resort 包发起多次 Welcome（多次 claim / consume）。
3. 检查每次消费后的审计链。

Expected：

- 普通包池空后，claim 响应 MAY 返回 last-resort 包，且对应 `keypackage_claim_record` MUST 置 `last_resort=true`，使 requester 与 holder 都能识别本次走 last-resort 路径。
- 同一 `intended_realm_id` 内该包可被多次 Welcome 复用；`ck.keys.keypackages.consume` 对其调用 MUST 幂等（返回成功、状态保持 `published`、不移出池、MUST NOT 返回 `keypackage_already_consumed`）。
- §2.6 / §2.6.1 其余校验（`keypackage_digest` / `capabilities_digest` / `ssk_generation` 匹配、`claim_envelope` 签名、Realm 反向 resolve）对 last-resort 包仍全部适用，放宽的只有单次性。
- 每次消费 MUST emit 一条 `ck.mls.keypackage`（或等价）审计记录，至少含 `keypackage_ref`、`keypackage_digest`、`claim_id`、`last_resort=true`、消费的 `intended_realm_id` 与时间戳；审计链 MUST append-only，保留每次消费的独立记录（不得覆盖前次）。

### 17.2 Vector: Last-Resort Forced Rotation

`vector_id`: `ck.vector.keypackage.last_resort_forced_rotation.v1`

本向量固化 §2.6.2「强制轮换闭合弱化窗口」MUST：last-resort 包持有 device 下次上线时 MUST 轮换该包（发布新 init/encryption key 的新 last-resort 包并把旧包标记 `rotated`，使旧包不再分发给新 claim）；持有者上线后 MUST 对所有经该 last-resort 包加入的 group 触发一次 MLS self-update Commit 推进 epoch，把前向保密恢复到正常 ratchet 水平，闭合 Welcome 阶段前向保密弱化窗口。

Steps：

1. holder 离线期间，其某个 last-resort 包在 Realm 内被用于多个 Welcome，使多个 group 经该包加入。
2. holder 重新上线。

Expected：

- holder 上线后 MUST 发布新的 last-resort KeyPackage（新 init/encryption key）并把旧包标记 / 撤销为 `rotated`；轮换后旧包 MUST NOT 再被分发给新 claim。
- holder MUST 对所有经该旧 last-resort 包加入的 group 触发一次 MLS self-update Commit（引入新 leaf key 材料）推进 epoch；无法精确定位经哪个包加入了哪些 group 时，MUST 对该 device 当前所有 last-resort-joined group 保守触发 update。
- 该轮换 + update 序列 MUST 把上文弱化窗口闭合在有界范围内；组建立后常规消息 ratchet 前向保密不受影响（仅初始 Welcome 注入受弱化窗口约束）。

### 17.3 Vector: Last-Resort Affinity And Optionality

`vector_id`: `ck.vector.keypackage.last_resort_affinity_and_optionality.v1`

本向量固化 §2.6.2 的 Realm affinity 与可选协商 fail-closed MUST：实现 MUST NOT 用单个全局 last-resort 包跨任意 Realm 复用，多次复用 MUST 限定在同一 `intended_realm_id` 内，跨 Realm 复用 MUST 拒绝（`last_resort_realm_affinity_violation`）；未声明 `ck.feature.mls_last_resort_keypackage.v1` 的服务端在池空时 MUST 继续 fail-closed，claim 响应 MUST NOT 返回 `last_resort=true` 的包（请求 last-resort 回退 MUST 拒绝，`last_resort_not_supported`）。

Steps：

- **Case A — 跨 Realm 复用拒绝**：声明该 feature 的服务端，尝试把绑定 `intended_realm_id = R1` 的 last-resort 包用于另一 Realm `R2` 的 Welcome / claim（`intended_realm_id` 不一致）。
- **Case B — 未声明 feature 池空 fail-closed**：未在 `ck.server.query.describe.supported_features` 声明 `ck.feature.mls_last_resort_keypackage.v1` 的服务端，其某 Realm 普通包池耗尽；requester claim，并显式请求 last-resort 回退。
- **Case C — holder 无该 Realm 条目（对照）**：声明该 feature 但 holder 离线期间某 Realm 尚无 last-resort 条目，该 Realm 普通包池空。

Expected：

- **Case A**：MUST 以 `last_resort_realm_affinity_violation` 拒绝；last-resort 包的多次使用语义是 Realm 内多次，跨 Realm 回退 MUST 由各 Realm 各自的 last-resort 池条目分别满足，不得退化为跨 Realm 复用。
- **Case B**：服务端 MUST 继续 fail-closed（池空 claim 失败），claim 响应 MUST NOT 返回 `last_resort=true` 的包；对显式 last-resort 回退请求 MUST 返回 `last_resort_not_supported`。
- **Case C**：该 Realm 的 claim 在不支持普通包回退时 MUST fail closed（与默认池空行为一致），不得退化为跨 Realm 复用其它 Realm 的 last-resort 包。
- 三个 case 都保留 §2.6 的审计与隔离性质：每次消费 `intended_realm_id` 确定、claim-Realm 一致性可校验、`claim_envelope` Realm 反向 resolve 不被绕过。

## 18. Sender-Constrained Session Token Vectors

本节收拢 sender-constrained（proof-of-possession，PoP）会话出示的 conformance 向量，固化 [`api-conventions.md`](../sync/api-conventions.md) §3 / §3.2 的推荐序、SHOULD 默认与高安全 profile MUST 升级，以及 [`service-http-binding.md`](../sync/service-http-binding.md) §2.5 的 RFC 9421 HTTP Message Signature header 形状与 transcript 绑定。每个 `vector_id` 均为规范性引用目标，登记于 [`vector-registry.json`](../../artifacts/registry/vector-registry.json)。

### 18.1 Vector: PoP Presentation

`vector_id`: `ck.vector.session.pop_presentation.v1`

本向量固化 §3.2 / §2.5 的 PoP 出示与 transcript 绑定 MUST：客户端用 `ck.session.grant` 委托的 `session_public_key` 对应私钥做 RFC 9421 HTTP Message Signature，covered components MUST 至少覆盖 `@method`、`@target-uri`、`@authority`，带 body 请求 MUST 含 `content-digest`（RFC 9530，覆盖 canonical request body，接收方 MUST 在验签前先校验 body 实际 hash 与 header 一致）；签名 `kid` MUST 指向当前 grant 的 `session_public_key`；出示是否被接受由签名 transcript 而非裸 token 决定。

Steps：

- **Case A — 合法 PoP 写请求**：对常规写 endpoint（如 `POST /_cokret/self/events`）提交，`Signature-Input` covered components 含 `@method` / `@target-uri` / `@authority` / `content-digest`（及参与幂等的 `idempotency-key`），`keyid` 指向当前 grant 委托的 `session_public_key` kid，`created` / `expires` 在 replay window 内，body 实际 hash 与 `Content-Digest` header 一致。
- **Case B — transcript / digest 不一致**：(a) 用对 method `M1` / path `P1` / body `B1` 生成的签名出示到 method / path 不同或 body 改为 `B2` 的请求（covered component 实际值与签名 transcript 不符）；(b) `Content-Digest` header 与 body 实际 hash 不一致。

Expected：

- **Case A**：验签通过，grant 的 principal / device / audience / origin 约束与请求一致，请求被接受；PoP 只把「持有 token」升级为「持有绑定密钥」，协议层权限判断仍回到 actor DID / capability / Realm policy。
- **Case B(a)**：`@method` / `@target-uri` / `@authority` / `content-digest` 任一与重算结果不符时验签失败，MUST 拒绝（grant 已撤销 / 过期 / audience / origin 不匹配同样 MUST 以 `unauthenticated` 拒绝）。
- **Case B(b)**：接收方 MUST 在验签前先校验 body 实际 hash 与 `Content-Digest` header 一致，不一致 MUST 拒绝，不得仅凭 header 自报 digest 通过。

### 18.2 Vector: Bearer Replay Rejected Under High Security

`vector_id`: `ck.vector.session.bearer_replay_rejected_high_security.v1`

本向量固化 §3.2 / §2.5 的高安全 profile MUST 升级与 replay window MUST：在 `ck.profile.high_security_organization.v1` / `sovereign_deployment` 下，对常规写与敏感读用纯 `Authorization: Bearer`（无 `Signature`）MUST 被拒绝；默认 profile 下纯 bearer 对低敏 / 兼容路径是允许的降级；PoP 的 `created` / `expires` 超出 replay window 即使 replay cache 已 evict 也 MUST 因 `created` / `expires` 校验失败而拒绝（口径同 `federation.md` §3.2 / `encoding.md` §6 签名时效窗口）。

Steps：

- **Case A — 高安全 profile 纯 bearer 写 / 敏感读**：在 `ck.profile.high_security_organization.v1`（或 `sovereign_deployment`）下，对常规写（推进 actor_seq / Realm frontier）或敏感读（成员列表、私有 projection、key backup、device list、moderation 队列等）只用 `Authorization: Bearer <session_token>` 出示，无 `Signature`。
- **Case B — 默认 profile 同请求（对照）**：默认 profile 下对同一类（按 §3.2 属低敏 / 兼容路径或尚未协商 PoP 的兼容旧客户端）请求只用纯 bearer 出示。
- **Case C — PoP 过窗**：携带合法签名的 PoP 出示，但 `created` / `expires` 超出 replay window（`expires - created` 超上限或 `created` 与本地时钟偏差超上限）。

Expected：

- **Case A**：MUST 以 `unauthenticated` 拒绝；高安全 profile 对常规写与敏感读要求 PoP 出示（见 [`conformance-profiles.json`](../../artifacts/profiles/conformance-profiles.json) 对应 profile 的 `additional_requirements`），纯 bearer 对这些操作 MUST 被拒绝。
- **Case B**：默认 profile 下作为允许的降级被接受（对照正样本）；服务端仍 MUST 校验 bearer token 的 audience / issuer / expiry / session grant 状态与 capability。
- **Case C**：过窗签名即使 replay cache 已 evict 也 MUST 因 `created` / `expires` 校验失败而拒绝；时效窗口外的逐字节重放同样 MUST 拒绝。

## 19. Applet Transaction Push Vectors

本节收拢 Applet inbound transaction push 的来源签名锚点与 replay 绑定向量，固化 [`applet-integration.md`](../extensions/applet-integration.md) §7.3.1、[`applet-schema.md`](../extensions/applet-schema.md) §3、[`service-http-binding.md`](../sync/service-http-binding.md) §2.2 的 service-to-service HTTP Message Signature 要求。每个 `vector_id` 均为规范性引用目标，登记于 [`vector-registry.json`](../../artifacts/registry/vector-registry.json)。

### 19.1 Vector: Transaction Source Signature Anchor

`vector_id`: `ck.vector.applet.transaction_source_signature_anchor.v1`

本向量固化 applet transaction push 的逐次来源签名与幂等 replay MUST：`ck.edge.applet.command.transaction` 在 node→Applet 与 app/bridge→cokret inbound 两个方向都 MUST 携带 RFC 9421 HTTP Message Signature，covered components 至少包含 `@method`、`@target-uri`、`@authority`、`content-digest`、`source-service-did`、`destination-service-did`、`idempotency-key`，签名参数含 `created` / `expires` 并满足 300s replay window；接收方 MUST 形成并持久化 `source_signature_anchor`，幂等 identity 绑定 `operation_id`、方向、source/destination service DID 与 `Idempotency-Key`，缓存记录绑定 canonical body digest 与 source anchor。来源 service 签名不替代每条 Event 的 actor / applet / capability 校验。

Steps：

- **Case A — 合法 app/bridge→cokret inbound**：已安装 Applet registration `service_did=did:web:bridge.example`，`registration_epoch=sha256:<R>`，`webhook_auth.key_ref=did:web:bridge.example#tx-1`，install active。Applet 提交 `POST /_cokret/edge/applet/transactions`，header `Source-Service-DID=did:web:bridge.example`、`Destination-Service-DID=did:web:principal.example`、`Idempotency-Key=tx-001`、`Content-Digest` 与 body 一致；`Signature-Input` 覆盖 required components，`keyid=did:web:bridge.example#tx-1`，`created` / `expires` 在窗口内；body `source_service_did` 与 header 一致，`events[]` 中的 `applet_id`、`authorization_ref`、`proofs[]` 与 actor namespace / capability grant 均有效。
- **Case B — 缺签名 / 纯 bearer**：同一 body 只携带 `Authorization: Bearer` 或完全缺少 `Signature` / `Signature-Input`。
- **Case C — transcript / source 混淆**：签名覆盖的 `source-service-did`、header `Source-Service-DID` 或 body `source_service_did` 三者任一不同；或 `Destination-Service-DID` 不等于实际接收服务；或 `Content-Digest` 与 body 不一致。
- **Case D — idempotency replay**：重复 Case A 的相同 headers/body/signature anchor；随后再次使用同一 `(operation_id, direction, Source-Service-DID, Destination-Service-DID, Idempotency-Key)`，但改变 body digest、`webhook_auth.key_ref` / `keyid`、`registration_epoch` 或 actor namespace。
- **Case E — 无 active install / actor namespace 混淆**：`Source-Service-DID` 可验签但没有 active effective install，或 `events[]` 中 actor / `executed_by` 不属于该 Applet registration 的 service / bot / ghost actor namespace，或 `authorization_ref` 指向另一 Applet 的 grant。

Expected：

- **Case A**：MUST 接受或按事件级规则返回 partial outcome，并持久化 `source_signature_anchor`（绑定 operation、方向、source/destination、verification method、registration_epoch、`Idempotency-Key`、body digest、covered components、`created` / `expires`）与幂等 outcome。
- **Case B**：MUST fail closed，HTTP 401，reason=`http_signature_required`；纯 bearer 不满足 transaction push 的 service-to-service 来源认证。
- **Case C**：MUST 在处理任何 Event / 副作用前 fail closed，reason=`http_signature_invalid`；`Content-Digest` MUST 在验签前重算，source/destination DID mismatch 不得进入业务逻辑。
- **Case D**：完全相同的 replay MUST 返回原 outcome 或等价成功且不得重复副作用；同一幂等 identity 但 body digest 或 `source_signature_anchor` 不一致时 MUST fail closed，认证已通过时 reason=`duplicate_conflict`，认证未通过时使用相应认证失败 reason。
- **Case E**：无 active install MUST fail closed，reason=`applet_registration_unauthorized`；actor / namespace / grant 混淆 MUST fail closed（`applet_namespace_mismatch`、`capability_denied` 或 `applet_registration_unauthorized`），不得把来源 service 签名当成 native actor 授权。
