---
title: Conformance Vectors
status: candidate
normative: true
stability: v1
updated: 2026-07-30
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

MIMI Provider Facade 的 active interop vectors 为 `ak.vector.mimi.provider_directory_draft_pinning.v1`、`ak.vector.mimi.room_binding_projection.v1`、`ak.vector.mimi.keypackage_claim_lifecycle.v1`、`ak.vector.mimi.content_roundtrip.v1`、`ak.vector.mimi.identifier_query_privacy.v1`、`ak.vector.mimi.consent_isolation.v1`、`ak.vector.mimi.proxy_download_policy.v1` 与 `ak.vector.mimi.unsupported_draft_fail_closed.v1`；详细语义见 [`mimi-interop.md`](../extensions/mimi-interop.md)，可执行数据见 [`mimi-interop-fixture.json`](../../artifacts/fixtures/mimi-interop-fixture.json)。

可执行向量数据集位于 [`spec/v1/artifacts/fixtures/`](../../artifacts/fixtures/)；
本文档把对应规范条款与文件入口集中呈现，便于一致性测试 runner 引用。
所有 `ak.vector.*` 标识符的机器索引位于 [`vector-registry.json`](../../artifacts/registry/vector-registry.json)；新增、删除或重命名向量时 MUST 同步更新该 registry，并通过 `tools/artifact_pipeline.py check` 的闭包校验。领域文档中定义的向量（例如 Directory / PSI / Search）只要在 registry `source_refs` 中登记，即属于同一 conformance suite。

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [normative-language.md](./normative-language.md) 解释；仅大写形式具规范约束力。

形式化 proof obligations 至少 SHOULD 覆盖：

- CBA / open_set 多 leaf 下 per-cell lattice join `J(L)` 是纯函数，且与输入顺序、接收方、墙钟无关；所有 conformant reducer 对同一 accepted Seal frontier 收敛到同一 cell value。
- 并发分支撤销 fail closed：grant / capability revoke 与被授权 Event 并发时，joined control view MUST 重判并拒绝不再满足授权的 Event。
- Capability delegation 单调衰减：`child.actions ⊆ parent.actions`、resource selector 不放宽、约束不放宽、`authority_expiry_seal` 只能收窄或固定，不能被子 grant 延长。
- Delegation graph 无环，且环检测在并发分支合并、离线 replay 与 migration context 下结果一致。
- Control-cell bottom / conflict-recovery 只能按 `event-auth-state-resolution.md` §9.5 的唯一 recovery Move 出 ⊥，其它路径 fail closed。

工具栈不在 v1 固定：TLA+ 适合状态机 / lattice 收敛，Tamarin / ProVerif 适合协议认证与攻击者模型，Alloy / property-based runner 可覆盖结构不变量。profile MAY 选择不同工具，但输出必须能被 reviewer 复现，并把每个 proof obligation 映射到规范章节、registry row 或 vector id。

## 1. Encoding & Crypto Vectors

### 1.1 目标

本文定义 Arkret canonical JSON、hash、event digest、event-batch receipt digest、signature binding、HLC、cursor 与 encrypted envelope digest 的一致性测试向量。

这些向量是 `encoding.md` 的测试化补充。实现只要在 hash 输入、字段排序、签名绑定或时间排序上产生差异，就不能声称与 Arkret v1 编码 profile 互操作。

### 1.2 通用规则

向量名称使用：

```text
ak.vector.encoding.<name>.v1
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
ak.vector.encoding.canonical_json.basic.v1
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

### 1.3.1 Vector: BLAKE3 Digest Suite

`ak.vector.encoding.digest.blake3.v1` 固定输入 `Arkret v1 BLAKE3 conformance` 的精确 UTF-8 bytes、`blake3:` 输出与 profile gate。声明 `ak.profile.hash.blake3.v1` 的实现 MUST 同时通过正向 KAT，以及错 suite prefix、截断 digest、Realm suite mismatch 和未知 suite downgrade 四个负例；不得只证明“库能调用 BLAKE3”。完整字节与期望值见 [`encoding-fixture.json`](../../artifacts/fixtures/encoding-fixture.json)。

### 1.4 Vector: Canonical JSON Nested

向量名称：

```text
ak.vector.encoding.canonical_json.nested.v1
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
ak.vector.encoding.canonical_json.utf16_supplementary_order.v1
```

该向量使用至少两个 key：一个位于补充平面、一个位于 BMP 高位区。实现 MUST 按 UTF-16 code unit 排序，而不是按 Unicode scalar value / code point 排序。期望 canonical bytes 以 `encoding-fixture.json` 中同名 vector 的 `expected_canonical_bytes_utf8` 为准。

### 1.5 Vector: Reject Non-Canonical Numbers

向量名称：

```text
ak.vector.encoding.reject_noncanonical_numbers.v1
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
ak.vector.encoding.reject_malformed_json.v1
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
- reject 结果 MUST 可审计；canonical JSON 解析失败 MUST 使用单一错误码 `invalid_canonical_json`，以保证跨实现错误码一致、可被 conformance runner 断言。

#### 1.5.2 Vector: Reject Duplicate Key

向量名称：

```text
ak.vector.encoding.reject_duplicate_key.v1
```

输入 bytes（UTF-8 文本，未经 parser 去重；同一层出现两个 `event_id`）：

```text
{"event_id":"ak:event:019640ed-8000-7000-8000-000000000000","event_id":"ak:event:019640ed-8000-7000-8000-000000000001"}
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
ak.vector.encoding.reject_non_nfc_string.v1
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
ak.vector.encoding.reject_feff_injection.v1
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
ak.vector.encoding.event_digest.v1
```

输入事件，不含 `proofs` 和 `unsigned`，但包含稳定 `event_id`：

```json
{
  "event_id": "ak:event:019640ed-8000-7000-8000-000000000000",
  "kind": "ak.message.create",
  "realm_id": "ak:realm:01964137-0000-7000-8000-000000000000",
  "scope_ref": {
    "kind": "realm",
    "realm_id": "ak:realm:01964137-0000-7000-8000-000000000000"
  },
  "actor_id": "did:webvh:z6mkfixture:alice.example",
  "actor_seq": 1,
  "created_at": "2026-04-26T00:00:00.000Z",
  "hlc": "01970e589d21-0004-a13f9c2e",
  "prev_refs": [],
  "refs": [],
  "seal_ref": "ak:seal:sha256:2222222222222222222222222222222222222222222222222222222222222222",
  "auth_context": {
    "did": "did:webvh:z6mkfixture:alice.example",
    "key_id": "device-1",
    "key_epoch": 1
  },
  "payload": {
    "strand_id": "ak:strand:01964137-0000-7000-8000-000000000000",
    "track_name": "discussion",
    "content": {
      "kind": "ak.content.text",
      "body": "hello"
    }
  }
}
```

期望 canonical bytes 的 UTF-8 文本表示：

```json
{"actor_id":"did:webvh:z6mkfixture:alice.example","actor_seq":1,"auth_context":{"did":"did:webvh:z6mkfixture:alice.example","key_epoch":1,"key_id":"device-1"},"created_at":"2026-04-26T00:00:00.000Z","event_id":"ak:event:019640ed-8000-7000-8000-000000000000","hlc":"01970e589d21-0004-a13f9c2e","kind":"ak.message.create","payload":{"content":{"body":"hello","kind":"ak.content.text"},"strand_id":"ak:strand:01964137-0000-7000-8000-000000000000","track_name":"discussion"},"prev_refs":[],"realm_id":"ak:realm:01964137-0000-7000-8000-000000000000","refs":[],"scope_ref":{"kind":"realm","realm_id":"ak:realm:01964137-0000-7000-8000-000000000000"},"seal_ref":"ak:seal:sha256:2222222222222222222222222222222222222222222222222222222222222222"}
```

期望 digest：

```text
sha256:e78bdef1ff9554389beeecefd8f1658081f2bd5db29d0229557fe04caf98dfbb
```

判定规则：

- event digest / proof `event_digest` MUST 从 redaction 前、去除 `proofs` 与 `unsigned` 后的 canonical event bytes 派生；`event_id` 是稳定 `ak:event:*` typed ID，必须进入 digest，但不替代 digest。
- 实现 MUST NOT 把 transport envelope、HTTP header、Sync Service metadata、local receive time 放入 event digest。
- 同一事件在不同 Events API 或 Sync Service 上 MUST 得到相同 digest。

### 1.7 Vector: Event Batch Receipt Digest

向量名称：

```text
ak.vector.encoding.event_batch_receipt_digest.v1
```

输入 Event Batch Receipt，不含 proof：

```json
{
  "schema": "ak.schema.event_batch_receipt.v1",
  "receipt_id": "ak:receipt:01964186-0000-7000-8000-000000000000",
  "issuer": "did:webvh:z6mkfixture:alice.example",
  "scope": {
    "actor_id": "did:webvh:z6mkfixture:alice.example"
  },
  "frontier": {
    "actor_seq": 2,
    "event_digest": "sha256:2222222222222222222222222222222222222222222222222222222222222222"
  },
  "events": [
    "sha256:1111111111111111111111111111111111111111111111111111111111111111",
    "sha256:2222222222222222222222222222222222222222222222222222222222222222"
  ],
  "created_at": "2026-04-26T00:00:00Z"
}
```

期望 canonical bytes 的 UTF-8 文本表示：

```json
{"created_at":"2026-04-26T00:00:00Z","events":["sha256:1111111111111111111111111111111111111111111111111111111111111111","sha256:2222222222222222222222222222222222222222222222222222222222222222"],"frontier":{"actor_seq":2,"event_digest":"sha256:2222222222222222222222222222222222222222222222222222222222222222"},"issuer":"did:webvh:z6mkfixture:alice.example","receipt_id":"ak:receipt:01964186-0000-7000-8000-000000000000","schema":"ak.schema.event_batch_receipt.v1","scope":{"actor_id":"did:webvh:z6mkfixture:alice.example"}}
```

期望 digest：

```text
sha256:3cb4e27faaa5fca6c7e4bbf9a5a73c31d589e57b7f4b274139d1e35701c524ef
```

失败条件：

- producer 未先按 `UTF8(canonical_json(item))` 排序去重，或 receiver 接受了非严格升序 / 含重复项的 signed wire 数组。
- fixture 的 reversed+duplicate constructor input 未规范化为与主向量相同的 `events[]` 与 digest。
- proof 字段被包含进 receipt digest。
- `issuer`、`scope`、`frontier` 或 `schema` 被排除在 digest 外。
- `receipt_id` 大小写被实现私自改写。

### 1.8 Vector: Signature Binding Payload

向量名称：

```text
ak.vector.encoding.signature_binding_payload.v1
```

签名前的 binding object（其中 `event_digest` 仅为占位值，取自 §1.3 `ak.vector.encoding.canonical_json.basic.v1` 的 digest `sha256:43258cff...`，用于固定本向量的 binding canonical 形态；它**不是** §1.6 真实 event digest——后者以本节同名向量 `ak.vector.encoding.event_digest.v1` 的 `expected_digest` 为唯一真源，本处不再硬编码其字面量。本向量只断言 binding object 的 canonical bytes 与 digest，不要求该 `event_digest` 与任一具体 event 一致）：

```json
{
  "event_digest": "sha256:43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777",
  "actor_id": "did:webvh:z6mkfixture:alice.example",
  "verification_method": "did:webvh:z6mkfixture:alice.example#device-1",
  "created_at": "2026-04-26T00:00:00Z"
}
```

期望 canonical bytes 的 UTF-8 文本表示：

```json
{"actor_id":"did:webvh:z6mkfixture:alice.example","created_at":"2026-04-26T00:00:00Z","event_digest":"sha256:43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777","verification_method":"did:webvh:z6mkfixture:alice.example#device-1"}
```

期望 digest：

```text
sha256:d94c02b84f5805afb06cecbb6b2ff489b5675bc6989102ea72643536af17e4bc
```

判定规则：

- proof MUST bind event digest、actor DID、verification method 和 created_at。
- 需要跨服务或跨域验证时，profile SHOULD 额外绑定 domain / audience。
- 签名算法测试向量由本文件第 13 节的 crypto fixture 要求补充真实 public key 和 detached JWS；本文固定签名前 canonical binding 输入。

### 1.8.1 Vector: Signature Binding Payload domain / audience 变体

`vector_id`:

- `ak.vector.encoding.signature_binding_payload_domain.v1`
- `ak.vector.encoding.signature_binding_payload_audience.v1`
- `ak.vector.encoding.signature_binding_payload_domain_audience.v1`

§1.8 的 base binding object 只含四个必备字段。跨服务 / 跨域验证 SHOULD 追加可选的 `domain` 或 `audience` 绑定；本组向量固化这两个可选字段进入 canonical binding bytes 的字节形态（来源：`encoding-fixture.json`，由参考实现实跑生成并 round-trip 自验）：

- `domain` 为字符串，按 canonical JSON 键序排在 `created_at` 与 `event_digest` 之间；
- `audience` 可为单个 DID 字符串或 DID 数组；数组语义为"面向多个受众服务"，元素顺序在 canonical bytes 中逐字保留；
- 缺省的可选字段 MUST 从 binding object 中整体省略——写入 `null` 占位会改变 canonical bytes，MUST NOT 出现。

Expected：三个向量的 `expected_canonical_bytes_utf8` 与 `expected_digest` MUST byte-for-byte 复现。

### 1.9 Vector: HLC Order

向量名称：

```text
ak.vector.encoding.hlc_order.v1
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
ak.vector.encoding.hlc_logical_overflow.v1
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

消费者处置是封闭的：同一 producer 的格式合法回绕 tuple 在 submit / command 入口 MUST 以 `schema_violation` 拒绝；在同步、backfill 或历史复验中 MUST quarantine 该 producer 冲突分支且不得推进其 accepted frontier。返回其它错误码、仅记录 warning、soft-fail 后继续或按普通 HLC 排序均为失败。

#### 1.10.1 Vector: Reject Malformed HLC Format

向量名称：

```text
ak.vector.encoding.reject_malformed_hlc.v1
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
ak.vector.encoding.cursor_opaque.core.v1
```

输入 cursor（schema-valid v1 core wire 形态；body 是 stateful opaque handle `{v,purpose,t,x,h}`）：

```text
ak:cursor:eyJoIjoiYWJjZGVmZ2hpamtsbW5vcHFyc3R1diIsInB1cnBvc2UiOiJzdHJlYW0iLCJ0IjoiMjA5OS0xMi0zMFQyMzo1OTo1OVoiLCJ2IjoiMSIsIngiOjQxMDI0NDQ3OTkwMDB9
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
ak.vector.encoding.encrypted_envelope_digest.v1
```

同一向量先固定 `routing_digest` 的 wire-breaking AAD 引用摘要：

```text
domain_separator = ak.aad-event-ref-v1
event_id         = ak:event:01964148-0000-7000-8000-000000000000
realm_id         = ak:realm:0196419b-0000-7000-8000-000000000000
digest_input_hex = 616b2e6161642d6576656e742d7265662d763100616b3a6576656e743a30313936343134382d303030302d373030302d383030302d30303030303030303030303000616b3a7265616c6d3a30313936343139622d303030302d373030302d383030302d303030303030303030303030
event_ref_digest = sha256:43a2d5664e7f0c51c4f3eccd369eeb19875561fedd71522fedbc71e77257a9c3
```

`digest_input_hex` 必须逐字节等于 `utf8(domain_separator) || 0x00 || utf8(event_id) || 0x00 || utf8(realm_id)`。机器向量另含“省略两个 `0x00`”“交换 `event_id` / `realm_id`”“追加尾部 `0x00`”三个 mutation case；三者都必须产生各自固定的不同摘要，不能被实现接受为有效输入。

`payload_metadata` canonical bytes 的 UTF-8 文本表示：

```json
{"aad":{"event_kind":"ak.message.create","event_ref_digest":"sha256:43a2d5664e7f0c51c4f3eccd369eeb19875561fedd71522fedbc71e77257a9c3","realm_id":"ak:realm:0196419b-0000-7000-8000-000000000000"},"aad_visibility_event_id":"routing_digest","content_type":"application/json","epoch":12,"group_id":"Z3JvdXAtMDAx","key_ref":{"algorithm":"MLS","group_state_ref":"ak:event:01964148-0000-7000-8000-000000000000"},"scheme":"mls_rfc9420","version":"1.0"}
```

`ciphertext` 的 base64url wire 值与解码后 UTF-8 测试表示：

```text
Y2lwaGVydGV4dC1leGFtcGxlLTAwMQ
ciphertext-example-001
```

期望 digest：

```text
sha256:6aa6a93aff69fc6505207e409c07f33940037e549c47542f261197c0c872052c
```

判定规则：

- digest 输入 MUST 为 `canonical_json(payload_metadata) || base64url_decode(ciphertext)`。
- 实现 MUST NOT hash 明文 payload。
- 实现 MUST NOT 省略路由和解密所需的 `payload_metadata` 字段，否则 Sync Service 无法安全去重和审计密文 envelope。

### 1.12.1 Vector: 畸形二进制 Payload 拒绝（结构深度 / CBOR bounds）

本节固化 [scalability-constraints.md](./scalability-constraints.md) §2 的 canonical 结构嵌套深度上限（64）与手写 deterministic CBOR 的 decode bounds（单 array / map ≤ 65,536 项；声明长度 MUST ≤ 剩余输入；indefinite-length 项拒绝）。机器可读向量在 [`encoding-fixture.json`](../../artifacts/fixtures/encoding-fixture.json)；体量型输入（深嵌套、超大数组）用 **generator 描述字段**表达，runner MUST 按 generator 规则在执行时构造输入，fixture 本身不存放兆级字面量。

向量名称：

```text
ak.vector.encoding.reject_structure_depth_exceeded.v1
ak.vector.encoding.reject_cbor_length_bomb.v1
ak.vector.encoding.reject_cbor_indefinite_length.v1
ak.vector.encoding.reject_cbor_array_bounds.v1
```

判定规则：

- **`reject_structure_depth_exceeded`**（generator：`nesting_depth = 65`）：runner 构造嵌套 65 层的 JSON 对象（object 与 array 混合计深，顶层容器深度为 1）。canonicalizer / receiver MUST reject（`schema_violation`，`reason_code=structure_depth_exceeded`），且 MUST 在递归耗尽栈之前有界地失败；深度恰为 64 的对照输入 MUST 被接受（上限含边界）。
- **`reject_cbor_length_bomb`**（raw bytes `5affffffffdeadbeef`）：byte string 头声明 4,294,967,295 字节但剩余输入只有 4 字节。decoder MUST 在按声明长度分配缓冲区之前 reject（`schema_violation`，`reason_code=cbor_bounds_invalid`）。
- **`reject_cbor_indefinite_length`**（raw bytes `bf616101ff`，即 indefinite-length map `{_ "a": 1}`）：indefinite-length 项违反 deterministic encoding（RFC 8949 §4.2），MUST reject（`schema_violation`，`reason_code=cbor_not_deterministic`）；SDK 已在 `mls_governance_binding` 解码路径拒绝，本向量将其锁定为跨实现 MUST。
- **`reject_cbor_array_bounds`**（generator：`array_item_count = 65537`）：runner 构造声明并携带 65,537 个项的 definite-length CBOR array。decoder MUST reject（`schema_violation`，`reason_code=cbor_bounds_invalid`），且 MUST NOT 在 bound 校验前按声明项数预分配存储。
- CBOR 向量适用于一切手写 deterministic CBOR 结构，包括 `mls_governance_binding` GroupContext extension（[encryption-and-audit.md](../crypto-media/encryption-and-audit.md) §2.5.3）。
- 超 1 MiB envelope、超长 object key / string value 的 generator 负例见 [`event-envelope-negative-fixture.json`](../../artifacts/fixtures/event-envelope-negative-fixture.json)（`payload_too_large`）。

### 1.13 覆盖矩阵

| 向量 | Minimal Client | Full Client | E2EE Client | Events API | Principal Server |
| --- | --- | --- | --- | --- | --- |
| `ak.vector.encoding.canonical_json.basic.v1` | MUST | MUST | MUST | MUST | MUST |
| `ak.vector.encoding.canonical_json.nested.v1` | MUST | MUST | MUST | MUST | MUST |
| `ak.vector.encoding.digest.blake3.v1` | MAY | MAY | MAY | MAY | MAY |
| `ak.vector.encoding.canonical_json.utf16_supplementary_order.v1` | MUST | MUST | MUST | MUST | MUST |
| `ak.vector.encoding.reject_noncanonical_numbers.v1` | MUST | MUST | MUST | MUST | SHOULD |
| `ak.vector.encoding.reject_malformed_json.v1` | MUST | MUST | MUST | MUST | MUST |
| `ak.vector.encoding.reject_duplicate_key.v1` | MUST | MUST | MUST | MUST | MUST |
| `ak.vector.encoding.reject_non_nfc_string.v1` | MUST | MUST | MUST | MUST | MUST |
| `ak.vector.encoding.reject_feff_injection.v1` | MUST | MUST | MUST | MUST | MUST |
| `ak.vector.encoding.event_digest.v1` | SHOULD | MUST | MUST | MUST | SHOULD |
| `ak.vector.encoding.event_batch_receipt_digest.v1` | MAY | SHOULD | SHOULD | SHOULD | MAY |
| `ak.vector.encoding.signature_binding_payload.v1` | MUST | MUST | MUST | MUST | MUST |
| `ak.vector.encoding.crypto.ed25519_detached_jws.v1` | MUST | MUST | MUST | MUST | MUST |
| `ak.vector.encoding.hlc_order.v1` | MUST | MUST | MUST | MUST | SHOULD |
| `ak.vector.encoding.reject_malformed_hlc.v1` | MUST | MUST | MUST | MUST | SHOULD |
| `ak.vector.encoding.cursor_opaque.core.v1` | MUST | MUST | MUST | MAY | SHOULD |
| `ak.vector.encoding.encrypted_envelope_digest.v1` | MAY | SHOULD | MUST | MAY | MUST |
| `ak.vector.encoding.reject_structure_depth_exceeded.v1` | MUST | MUST | MUST | MUST | MUST |
| `ak.vector.encoding.reject_cbor_length_bomb.v1` | MAY | SHOULD | MUST | MAY | MUST |
| `ak.vector.encoding.reject_cbor_indefinite_length.v1` | MAY | SHOULD | MUST | MAY | MUST |
| `ak.vector.encoding.reject_cbor_array_bounds.v1` | MAY | SHOULD | MUST | MAY | MUST |
| `ak.vector.encoding.signature_binding_payload_domain.v1` | SHOULD | SHOULD | SHOULD | MUST | MUST |
| `ak.vector.encoding.signature_binding_payload_audience.v1` | SHOULD | SHOULD | SHOULD | MUST | MUST |
| `ak.vector.encoding.signature_binding_payload_domain_audience.v1` | SHOULD | SHOULD | SHOULD | MUST | MUST |
| `ak.vector.encoding.crypto.es256_detached_jws.v1` | MAY | MAY | MAY | MAY | MAY |
| `ak.vector.encoding.crypto.mldsa65_raw_detached_signature.v1` | MAY | MAY | MAY | MAY | MAY |
| `ak.vector.encoding.crypto.signature_negative.v1` | MUST | MUST | MUST | MUST | MUST |
| `ak.vector.encoding.reject_invalid_cursor.core.v1` | MAY | MAY | MAY | MUST | MUST |
| `ak.vector.encoding.multibase_did_key.core.v1` | SHOULD | SHOULD | MUST | MUST | MUST |

### 1.14 Crypto Fixture 要求

自动化 conformance suite MUST 加载 `spec/v1/artifacts/fixtures/crypto-signature-fixture.json`。该 fixture 固定了 `ak.vector.encoding.crypto.ed25519_detached_jws.v1`：

- Ed25519 public key / private test key
- detached JWS signature
- DID Document verification method
- canonical Event payload、`event_digest`、proof binding object、detached JWS signing input 和 expected rejection 条件

fixture 同时固化以下向量（2026-07-03 起）：

- `ak.vector.encoding.crypto.es256_detached_jws.v1` — ES256（ECDSA P-256，RFC 6979 确定性签名）detached JWS 正向量；由 `ak.profile.signature.ecdsa_p256.v1` 门控，声明该 profile 的实现 MUST 通过。
- `ak.vector.encoding.crypto.mldsa65_raw_detached_signature.v1` — ML-DSA-65（NIST FIPS 204）raw detached signature 正向量（registry `proof_kind = raw_detached_signature`，无 JOSE 包装）；由 `ak.profile.signature.pqc.v1` 门控。
- `ak.vector.encoding.crypto.signature_negative.v1` — 可执行负向量组：Ed25519 位翻转 / `alg=none` / key-type mismatch / 截断公钥 / detached payload 混淆，ES256 截断 raw `r||s` 与 P-256 坐标，以及 ML-DSA-65 截断签名与公钥。实现只执行通用 Ed25519 负例不得声明 ES256 或 ML-DSA-65 profile；每个 active suite 都 MUST 逐条拒绝其算法专属负例，且拒绝原因 MUST 来自 fixture 声明的稳定错误码。

后续 conformance suite 仍应增加扩展 fixture：

- key rotation 后的 signature verification
- redaction 前后 event digest 验证

测试私钥只能用于公开测试向量，不得被任何生产实现信任。生产 profile MUST 拒绝测试 DID、测试 key id 或测试 trust domain。

### 1.14.1 HPKE Suite Fixture 要求

自动化 conformance suite MUST 加载 `spec/v1/artifacts/fixtures/hpke-suite-fixture.json`。该 fixture 为 `hpke-suite-registry.json` 中与 RFC 9180 组合完全一致的 suite 固化 Base mode（`SetupBaseS` / `SetupBaseR`）字节级已知答案向量：

- `ak.vector.hpke.x25519_chacha20poly1305_base.v1`
- `ak.vector.hpke.x25519_aes256gcm_base.v1`
- `ak.vector.hpke.p256_aes256gcm_base.v1`

每条向量含 KEM 密钥材料、`enc`、`shared_secret`、key schedule 输出与首条密文；实现 MUST byte-for-byte 复现，负例（篡改密文、未注册 suite id）MUST fail closed。含 XChaCha20-Poly1305 的 suite 不在 RFC 9180 AEAD 注册表内，其 key-schedule 参数（`aead_id`、`Nk`/`Nn`）尚未在正文钉死，fixture 的 `uncovered_suites` 如实登记该缺口；在参数定案前 MUST NOT 为其杜撰向量。

### 1.15 Cross-Domain Vector Seals

以下 vector id 的具体断言由对应领域正文定义；本节提供 conformance registry 的统一锚点：

- `ak.vector.media.aead_nonce_sender_domain_collision.v1`
- `ak.vector.media.aead_nonce_counter_replay.v1`
- `ak.vector.media.aead_nonce_random_rejected.v1`
- `ak.vector.lattice.mv_register_join.v1`
- `ak.vector.lattice.counter_join.v1`
- `ak.vector.lattice.ordered_log_join.v1`
- `ak.vector.circle.directory_visibility_realm_members_indistinguishable.v1`
- `ak.vector.calendar.rsvp_occurrence_key.v1`

### 1.16 Vector: Cursor 拒绝负例

`vector_id`: `ak.vector.encoding.reject_invalid_cursor.core.v1`（来源：`cursor-negative-fixture.json`）

§1.11 固化 cursor 对客户端的不透明性；本向量固化签发服务侧的拒绝语义。fixture 的每个 case 是一条形似合法的 `ak:cursor:` token，conformant 签发服务在推进任何服务端状态之前 MUST 拒绝：超长 token、非法 base64url、畸形 JSON、重复键、非 NFC 字符串、内联 positions、未知字段、不支持的版本、过短 handle、非 canonical 时间戳、负 TTL、超 TTL 上限（stream / barrier 各一）、已过期。

Expected：前 13 类 `reason_code = invalid_cursor`（顶层错误码 `invalid_param`），过期 case `reason_code = cursor_expired`；客户端侧行为仍按 §1.11——decode 失败时按不透明字符串处理，MUST NOT 因此中断协议。

### 1.17 Vector: Multibase did:key 编码

`vector_id`: `ak.vector.encoding.multibase_did_key.core.v1`（来源：`encoding-fixture.json`）

固化 Ed25519 公钥的 base58btc multibase 编码（含 `0xed01` multicodec 前缀）与 `did:key` 标识符的金向量，为联邦验签与设备密钥目录的公共编码面提供跨实现锚点。cases 覆盖 all-0x2A、all-0x00 边界与固定顺序字节三组公钥。

Expected：`expected_multibase` / `expected_did_key` MUST byte-for-byte 复现；decode MUST round-trip 回原始 32 字节公钥，前缀非 `0xed01` 或长度非 34 字节 MUST 拒绝。

### 1.12.2 Vector: Event 引用与 Circle 基数上限（normative）

`ak.vector.scalability.refs_limit.v1` MUST 由 runner 生成带 129 个互异 `refs[]` 条目的 Event，并在 reducer 之前断言 `schema_violation`、`reason_code=refs_too_large`；实现不得截断、去重后继续或只检查单一 role 的数量。

`ak.vector.scalability.circle_count_limit.v1` MUST 同时覆盖：（a）已有 1,000 个 active Circle 的 Realm 再提交 `ak.circle.create`；（b）已有 256 个 active MLS-backed Circle membership 的 actor 再加入一个 MLS-backed Circle。两者均 MUST 以 `failed_precondition`、`reason_code=circle_count_exceeded` 拒绝且不得改变状态。体量状态由 runner 按 [`scalability-limits-fixture.json`](../../artifacts/fixtures/scalability-limits-fixture.json) 的 generator 描述构造，不要求 fixture 字面展开全部对象。

`ak.vector.scalability.envelope_size_limit.v1` 只测完整 canonical accepted Event Envelope，不再使用未定义的 “Event/Operation envelope” 混合对象。Runner MUST 生成精确 1,048,576 bytes 的候选 accepted Event（包含全部 proof 与 reducer-stamped 字段、不含 read-view `unsigned`）作为接受边界，并生成 1,048,577 bytes 的超限输入；还必须覆盖 producer envelope 在 stamping 前未超限、加入 `effective_scope` / `actor_kind` 后变为 1,048,577 bytes 的用例。两个超限输入都 MUST 在 commit 前以 `payload_too_large` 拒绝；self/peer submit 携带 `unsigned` 必须在 reducer 前 `schema_violation`。

`ak.vector.scalability.http_header_limits.v1` MUST 至少覆盖：128-char `Idempotency-Key` 接受、129-char 拒绝；非 ASCII / 非 canonical alphabet 拒绝；HTTP header aggregate 32 KiB 接受、32 KiB + 1 byte 拒绝；超限输入不得建立 replay-cache entry、不得构造无界签名 transcript。

### 1.12.3 Vector: JSON operation、HTTP pre-parse 与二维分页边界（normative）

下列 vector 均由 [`scalability-limits-fixture.json`](../../artifacts/fixtures/scalability-limits-fixture.json) 的生成式 case 承载：

- `ak.vector.scalability.operation_body_size_limit.v1` MUST 对 `body_class=non_streaming_json` 的完整 canonical request/response body 生成 8 MiB−1、8 MiB、8 MiB+1；前两者在其它约束合法时通过，8 MiB+1 固定为 `payload_too_large`。
- `ak.vector.scalability.http_body_preparse_limit.v1` MUST 对 `Content-Length`、HTTP/1.1 chunked、HTTP/2 DATA 与 HTTP/3 DATA 分别生成 16 MiB−1、16 MiB、16 MiB+1；超限必须在第 16 MiB+1 byte 终止，JSON parser、JCS 与 handler 都不得启动。另生成 wire 16 MiB+1、canonical 仅 `{}` 的 whitespace amplification，证明 canonical 较小不能绕过 wire 上限。
- `ak.vector.scalability.content_encoding_forbidden.v1` MUST 对 gzip、br、deflate 在读取或解压 body 前返回 HTTP 415 / `unsupported_content_encoding`。
- `ak.vector.scalability.batch_page_byte_count.v1` MUST 同时覆盖 request 的 count 与 canonical bytes 两维，以及 response page 因 bytes 先到而提前结束并返回 `has_more=true` 与 `next_cursor`；少于 count 上限不得被解释为终页。
- `ak.vector.scalability.read_unsigned_size_limit.v1` MUST 生成 service-added `unsigned` 的 16 KiB−1、16 KiB、16 KiB+1，验证超限值在 response commit 前被拒绝或省略，且任何 `unsigned` 都不改变 Event identity、授权或 reducer。

### 1.12.4 Vector: MLS Governance Proof 分块与总界（normative）

`ak.vector.scalability.mls_governance_proof_bounds.v1` 由 [`scalability-limits-fixture.json`](../../artifacts/fixtures/scalability-limits-fixture.json) 的生成式矩阵固化 [`scalability-constraints.md` §6](./scalability-constraints.md) 与 `mls-governance-proof-bundle.schema.json`。Runner MUST 对下列每个维度生成 `limit-1 / limit / limit+1`：4 MiB response bytes、256 MiB logical item bytes、1,024 chunks、四类 collection total（4,096 / 1,048,576 / 262,144 / 128）、四类 per-chunk item count（128 / 8,192 / 1,024 / 32）、10 个 inclusion-proof sibling，以及 request `chunk_index=1023`。`limit-1` 与 `limit` 必须通过该维度的边界检查；`limit+1` 必须在 materializer 或 verifier 对应边界以 `mls_governance_proof_bounds_exceeded` / `schema_violation` fail closed，且不得截断、返回 partial manifest、按声明 cardinality 预分配或把已接收前缀标为完整。

同一 vector 还 MUST 覆盖 chunk acquisition 状态：chunk 0 只在缺少 `expected_bundle_digest` 时合法；chunk >0 必须携带 chunk 0 的 digest；`chunk_index == chunk_count` 返回 `invalid_param`；manifest 已不可用返回 `frontier_unavailable` 并要求从 0 重启。`chunk_index` / `expected_bundle_digest` 不得改变 `proof_request_digest`，但后续响应的 `bundle_digest`、`chunks_root` 或 identity 任一变化都必须拒绝，禁止跨 manifest 混块。

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
ak.vector.cba_lattice.data_event_accepts_without_seal_finality.v1
```

输入：

- DataEvent 携带签名 `scope_ref`、`seal_ref` 与 `auth_context`，不携带 `seal_basis` 或 `preconditions`；writes 由 reducer vector 重算。
- `seal_ref` 指向的 Seal view 可验证，actor chain / signature / capability 均通过。

期望：

- DataEvent 进入 `data_local` / `data_seen` 状态并可本地投影。
- 不需要等待该 DataEvent 出现在任何 Seal 覆盖集。
- Seal 只能通过 `data_event_set_root` / `data_view_root` 提供观察性证明，不赋予数据面 sealed finality。

### 2.3 Vector: 观察性 Data Root 不产生 Sealed 状态

向量名称：

```text
ak.vector.cba_lattice.data_event_observation_does_not_seal.v1
```

输入：

- Seal 携带 `data_event_set_root`，该 root 包含某 DataEvent digest。
- 同一 Seal 的 `delta[]` 与递归覆盖集不包含该 DataEvent digest。

期望：

- DataEvent 的证据状态最多为 `data_observed`，不得升级为 `control_sealed`。
- 客户端不得用观察性 data root 满足 Control Move `seal_basis` 或治理 freshness。
- `data_observed` 可用于可用性、range completeness 或轻客户端提示，但不是控制面 finality。

### 2.4 Vector: Control Move 必须有 Basis 且由 Seal 覆盖

向量名称：

```text
ak.vector.cba_lattice.control_move_requires_seal_basis_and_seal.v1
```

输入：

- Control Move 携带签名 `scope_ref`、`seal_basis` 与必要 `preconditions[]`；writes 由 reducer vector 重算。
- 同形 Control Move 的负向 case 缺少 `seal_basis`，或 `seal_basis.state_root` 与 leaves 重算不一致。

期望：

- 缺 `seal_basis` 或 basis 不一致 MUST `failed_precondition` / `rejected_seal`。
- 通过验证的 Control Move 仍只是 `control_pending`，直到某 Seal 的递归覆盖集覆盖其 digest 并重算控制面 `state_root`。

### 2.5 Vector: 同批提交不推进授权 Basis

向量名称：

```text
ak.vector.cba_lattice.same_batch_does_not_advance_authorization_basis.v1
```

输入：

- 同一 ordered submit batch 中包含 Control Move `M1` 与 `M2`。
- `M2` 的 precondition 只有在读取 `M1` 的 projected write 后才成立。
- `M2.seal_basis` 指向 batch 前的 Seal view。

期望：

- `M2` MUST `failed_precondition`。
- 同批只提供传输/原子提交便利，不推进 authorization basis；接收端不得用同批内新 projected write 自我满足 precondition。
- 需要依赖 `M1` 的写入必须等待 `M1` 被 accepted Seal 覆盖后重新提交。

### 2.5.1 Vector: MLS Governance Epoch Binding

`vector_id`: `ak.vector.mls.governance_epoch_binding.v1`

Steps：

1. 构造 `ak.mls.commit`，`payload.base_epoch = 41`、`payload.next_epoch = 42`。
2. `payload.governance_binding.previous_epoch = 40` 或 `payload.governance_binding.next_epoch = 43`。
3. 其它 signature、proposal refs、policy root 和 membership frontier 均有效。

Expected：

- Receiver / reducer MUST reject 该 commit，且不得推进 `mls_epoch_cell` 或 `covered_seals_cell`。
- `governance_binding.previous_epoch` / `next_epoch` MUST 与 payload 顶层 epoch 字段一致；不得只相信其中一侧。

### 2.5.2 Vector: MLS Governance Proof Bundle 双消费者闭环

`vector_id`: `ak.vector.mls.governance_proof.verifier.v1`

`vector_id`: `ak.vector.mls.governance_proof.materializer.v1`

两条 active vector 共用 [`mls-governance-proof-fixture.json`](../../artifacts/fixtures/mls-governance-proof-fixture.json) 的同一份 byte-level KAT。server-consumer runner MUST 从 fixture 的 accepted Seal、完整 covered Event 集与 joined control state 重建四个有界 chunk，逐字节复算 Event/Seal/请求/chunk/manifest/Bundle commitments，并与 `expected_acquisition.responses[]` 精确比较；SDK-consumer runner MUST 以相同 responses、commit transcript binding 与本地 trust context 执行 [`encryption-and-audit.md` §2.5.1.1](../crypto-media/encryption-and-audit.md#2511-accepted-seal-治理证明-bundlenormative) 的固定验证顺序。具体执行入口以 fixture `runner` 元数据为准。只加载 fixture、只做 schema validation、只检查 `governance_binding.previous_epoch/next_epoch` 或只返回一个总 pass 均不构成通过。

Verifier mutation matrix MUST 在需要测试语义阶段时重算所有 transport commitments，覆盖：Bundle 自报但本地未信任的 anchor、断裂/分叉 Seal path、错误 notary authority；covered digest/state leaf/frontier Event 的缺失、多余、重复和乱序；frontier Event proof 与跨 Realm/scope；chunk root、缺块、重复块和乱序；Realm/group/epoch/profile/reducer binding，以及 `policy_root`、`capability_root`、`discussion_metadata_digest` 不匹配。任一 reject case 都不得持久化 verified Bundle 或推进 MLS epoch。

Materializer matrix MUST 覆盖精确有效输出，以及 unknown/unreachable anchor、缺失或分叉 Seal material、撤销后的 notary、缺失 covered Event、control-cell Bottom、scope visibility denial 与总界超限；失败时 response count 必须为 0，不能输出 partial manifest。两条 runner 在同一 profile certification job 中还 MUST 执行 companion `ak.vector.scalability.mls_governance_proof_bounds.v1` 的全部 `limit-1 / limit / limit+1` 与 chunk acquisition cases，并记录每 case 的 stage、reason/error、response count、bundle/chunk digests、epoch transition 与 peak buffer bytes。

### 2.5.3 Vector: MLS Welcome KeyPackage Hash Binding

`vector_id`: `ak.vector.mls.welcome_keypackage_hash.v1`

Steps：

1. KeyPackage claim response 返回 `keypackage_ref=K`、`keypackage_digest=H1`、`capabilities_digest=C`、`ssk_generation=G`。
2. 攻击者提交 `ak.mls.welcome`，顶层 `keypackage_ref=K`，但 `payload.keypackage_digest=H2` 或 `payload.claim_ref.keypackage_digest=H2`。
3. Welcome ciphertext、claim_id、capabilities_digest 和 signature envelope 其它字段均有效。

Expected：

- Receiver MUST reject before decrypting or accepting the Welcome。
- `payload.keypackage_digest`、`payload.claim_ref.keypackage_digest`、claim record `keypackage_digest` 和已发布 `ak.mls.keypackage.payload.keypackage_digest` MUST 全部一致。

### 2.5.4 Vector: RFC 9420 MTI Ciphersuite Byte-Level KAT

`vector_id`: `ak.vector.mls.rfc9420_mti_kat.v1`

Arkret 不复制易漂移的外部密码学金值；本向量直接 pin MLS WG `mlswg/mls-implementations` 的 `test-vectors/` corpus commit `cfd450286d1bfd9cd2519b95c80f9771f94a5b1a`。声明 MLS 支持的实现 MUST 对 ciphersuite `0x0001` 运行 registry 列出的 `crypto-basics.json`、`key-schedule.json`、`messages.json`、`welcome.json` 与 `treekem.json` 全部适用 case，并逐字节匹配编码、KEM/HPKE 输出、joiner / epoch secret、Welcome 与 TreeKEM 派生值。只通过 Arkret 结构绑定 fixture、不运行该字节级 corpus，不足以声明 `ak.vector.mls.rfc9420_mti_kat.v1` 通过。更换 upstream commit 必须作为 registry review 变更并重新跑全套 KAT。

### 2.6 Vector: 数据面冲突返回 Bottom 且不选 Winner

向量名称：

```text
ak.vector.cba_lattice.data_plane_conflict_returns_bottom_without_winner.v1
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
ak.vector.cba_lattice.seal_delta_excludes_data_event_digest.v1
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
ak.vector.cba_lattice.open_set_compaction_preserves_control_roots.v1
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
ak.vector.cba_lattice.seal_canonical_no_self_reference.v1
```

输入与期望（多 case 矩阵）：

1. **Base case**：构造 Seal body fields `{realm_id, predecessor_refs, delta, control_event_set_root, state_root, completeness_root, notary_seq, sealed_at, hlc}`；按 [`encoding.md`](../conformance/encoding.md) §2 编码为 `seal_canonical_bytes`；`id = "ak:seal:sha256:" || hex(H(seal_canonical_bytes))`；`notary_signature.payload_digest == H(seal_canonical_bytes)`。Verifier MUST 重算 coverage、completeness 与 state 三类 root 后 accept。
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
ak.vector.state_root.incremental.v1
```

输入：

- 一个已被接受的 Seal `A0`，其控制面覆盖集写入 N 个 cell（`cell_1 … cell_N`，N ≥ 8）；实现已按 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §6.2.1 缓存 `cell → leaf_digest` 表。
- 一个新的 Seal `A1`（`predecessor_refs=[A0]`），控制面 `delta[]` 仅修改其中 K 个 cell（K ≤ N，包含 K=1 / K=N/2 / K=N 三种 case）。
- 一个 corner-case Seal `A2`：`delta[]` 是空 set（无新 control write）。
- 一个 schema-evolution case `A3`：`delta[]` 包含一个新 cell（之前从未有过 write），并用 lattice 的 ⊥/tombstone 机制终止一个旧 cell。

期望：

每个 case MUST 同时计算：

- `state_root_incremental`：仅对受影响 cell 重算 leaf_digest 与 Merkle 分支，复用 `A0` 缓存。
- `state_root_full`：丢弃缓存，按 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §6.2.1 / §6.2.2 从 Seal 覆盖集全量重算所有 cell 的 leaf_digest 与 Merkle root。

判定要求：

- `state_root_incremental == state_root_full` 在所有四个 case 上 MUST 成立，bit-exact。
- 缓存的 `leaf_digest` 表 MUST 在 `apply_seal` 接受 Seal 后更新；保留旧 leaf_digest 导致 next-seal 增量重算偏离全量结果即视为实现 bug。
- A2（空 `delta[]`）情况下 `state_root_incremental` MUST 直接复用 `A0.state_root`；不得因为"没有 cell 可重算"而错误地返回空 Merkle root（`H("")`）或 null。
- A3（新增 cell + 旧 cell tombstone）case 验证两点：(a) 新 cell 的 leaf_digest 进入 sorted leaf 列表（按 `cell_wire` Unicode 升序）；(b) 已终止 cell 仍以其 `Bottom` 或 tombstone 后的 lattice value 编码 leaf_digest，不被简单从 leaf 列表移除。

失败条件：

- 增量分支只重算到内部 Merkle 节点而不向上传播至 root → root 与 full 不匹配。
- 偶数/奇数边界处理在 incremental 与 full 之间不一致（例如 incremental 路径错误复制最后 leaf 而 full 路径正确"提升"）。
- 受影响 cell 集合按 receive order 而非 `cell_wire` lex order 排序。
- A2 case 下错把 `state_root` 重置为空摘要。

实现 MUST 在 conformance 报告中分别报告四个 case 的 `state_root_incremental` 与 `state_root_full`，并标记 pass / fail。该 vector 验证 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §6.2.1 / §6.2.2 中"增量与全量必须等价"的要求。

### 2.10 Vector: `ak.strand.tracks.update` 原子 patch

向量名称：

```text
ak.vector.strand_tracks_update.atomic.v1
```

输入：

- 一个已存在 Strand `F0`，`tracks = { "synthesis": { is_primary: true, enabled: true }, "discussion": { is_primary: false, enabled: true } }`。
- Case A — 单字段 patch：一个 `ak.strand.tracks.update` Event，`payload.patch = { "tracks.synthesis.is_primary": { "$op": "set", "value": false }, "tracks.discussion.is_primary": { "$op": "set", "value": true } }`。期望 Strand `tracks` 在单个 Event 的 reducer projection 内原子地把 primary 从 `synthesis` 切到 `discussion`，中间态 MUST NOT 出现"两个 is_primary=true"或"零个 is_primary=true"。
- Case B — 启停 + profile 更新：在 Strand 已含 `tracks.synthesis` / `tracks.discussion` 的基础上，单条 `ak.strand.tracks.update` 同时 (1) 把 `tracks.discussion.enabled` 置为 false，(2) 把 `tracks.discussion.profile` 置为 `review`。`review` 在这里是 UI hint profile 值，不是 TrackName。
- Case C — invariant 违反：单条 `ak.strand.tracks.update` 把 `tracks.synthesis.is_primary` 与 `tracks.discussion.is_primary` 同时 set 为 `true`。
- Case D — 未登记名称：单条 `ak.strand.tracks.update` 尝试写入 `tracks.review.enabled=true`；`review` 未登记在 `track-name-registry.json`，即使匹配 TrackName 基础正则也不得创建。

期望：

- **Case A**: reducer 应用 patch 后，`Strand.tracks.synthesis.is_primary == false` 且 `Strand.tracks.discussion.is_primary == true`；reducer 视角下不存在两次中间 state cell write，mv_register cell 一次 atomic update。
- **Case B**: reducer 接受合并后状态 `{ synthesis: {is_primary: true, enabled: true}, discussion: {is_primary: false, enabled: false, profile: "review"} }`；中间过程 MUST 在同一 cell update 内完成，不得分裂为多个独立 cell write。`tracks` 的 key 仍精确为 registry 中的 `discussion` / `synthesis`。
- **Case C**: reducer MUST 在 projected writes 应用前（cell update 之前）校验合并后 `tracks` map 至多 1 个 entry `is_primary=true`；不满足 MUST `schema_violation`，整条 Event 拒绝，Strand `tracks` 不发生任何变化。
- **Case D**: reducer MUST 在应用 patch 前把 path 中的 TrackName 与 active registry 集合比较；未登记名称 MUST `schema_violation`，不得创建 `review` track，Strand `tracks` 不发生任何变化。

判定要求：

- patch path 解析 MUST 遵循 [`event-and-patch.md` §4.2`](../models/event-and-patch.md) ABNF grammar；任何 path 形如 `tracks.<name>[key=...]` 的 selector segment MUST `schema_violation`——selector segment 不是 `ak.schema.patch.v1` 的一部分（§4.2.1）。
- `ak.strand.tracks.update` 写入的 cell 是 `ak:cell:ak.component.strand.tracks.v1:<strand_id>`（mv_register），reducer 校验合并后 invariant 在 cell update 之前 完成。

失败条件：

- Case A 在 cell update 中间态触发 invariant 校验，把"先把 synthesis 设 false → 此时 0 个 primary"错判为 violation。
- Case B 把 patch 拆分为多个独立 cell write，破坏 atomic 语义（外部读取在中间能看到部分更新的 track 配置）。
- Case C 把违反 invariant 的 Event 部分接受（例如设了 enabled 但拒绝 is_primary），破坏 Event-level all-or-nothing 语义。
- Case D 因 `review` 匹配基础正则而接受，绕过 registry 准入。

实现 MUST 在 conformance 报告中分别报告四个 case 的 reducer 输出 cell value 与 invariant violation reason；该 vector 防御 [`strand-and-message.md`](../models/strand-and-message.md) §4.5 step 5 primary 解析规则及 TrackName registry 准入的边界 case。

#### 2.10.1 Vector: patch path grammar 与边界

向量名称：

```text
ak.vector.patch.path_grammar_bounds.v1
```

runner MUST 从 `scalability-limits-fixture.json` 的 generator 构造并验证以下边界：

- 16 段且恰好 1024 ASCII bytes 的 snake_case path 必须通过 `patch.schema.json#/propertyNames`；
- 1025 bytes、17 段、大写或数字开头、selector、数字数组下标、空 segment 与 quoted identifier
  必须以 `schema_violation`、`reason_code=patch_path_invalid` 拒绝；
- parser 对任何非法形态都不得跳过无效部分后继续解析。

schema validation 与 reducer / SDK parser 必须给出一致结论；只在其中一层拒绝不构成通过。

### 2.11 Vector: `fsm` 家族 join 幂等与并发冲突

向量名称：

```text
ak.vector.lattice.fsm_join.v1
```

本向量固化 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §9.3.1 `fsm` lattice 的 join 规则：“同一 CBA basis 内相同 `(from,to)` 的重复 transition 是幂等的；同一 `from` 指向不同 `to` 的 sibling transition 返回 ⊥。跨 basis 顺序仅由 causal refs 与 Seal DAG 决定；同一 basis 内不得用 HLC、接收顺序或 actor id 选择状态机 winner。”

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

#### 2.11.1 Vector: same-Seal `bottom=reject` 排重

向量名称 `ak.vector.seal.same_batch_bottom_reject_serialization.v1`。构造两条基于同一 frozen predecessor、命中同一 `cas_register` 或 `fsm` `bottom=reject` cell 且 projected writes 互斥的 Control Move。Case A 的 notary 只 include 一条并对另一条 signed-reject `cas_conflict`（或 defer）；Seal MUST accept。Case B 的同一 Seal `delta[]` include 两条；`apply_seal` MUST 拒绝整个 Seal 为 `rejected_seal`，不得物化 `failed_bottom`。Case C 把两条 Move 放在不可达的并发 Seal leaf；joined view 仍 MUST 按 lattice 返回 `Bottom{kind="conflict"}`，证明排重义务不改变真正跨 leaf 并发语义。

### 2.12 Vector: `cas_register` 混合 basis（非初始态盲写拒绝）

向量名称：

```text
ak.vector.cba_lattice.cas_mixed_basis.v1
```

本向量固化 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §9.3.1 的 **Basis 强制（normative）**：“cas_register 的 set write 在目标 cell 的 settled 值为非初始态时，Control Move MUST 携带针对本 cell 的 `head_eq` precondition；DataEvent MUST 通过 causal refs 与 lattice 规则表达同等 CAS 约束。缺失时，receiver MUST 以 `failed_precondition` 拒绝该 write，并按多 cell 原子性拒绝整个 reducer input，不接受‘无 CAS 强制写’。”

输入（cas_register cell，未声明 `initial_value`，初值 `null`；前置 Seal 已把 settled 值推进到 `value_1`，即非初始态）：

- **Case A — 非初始态盲写**：一条 set Event 写入 `value_2`，**不带**针对本 cell 的 basis 证明（null basis）。
- **Case B — 正确 basis 收敛**：一条 set Control Move 写入 `value_2`，携带 `head_eq: "value_1"`（与 settled pre-state 一致）。

期望：

- **Case A**：receiver MUST 以 `failed_precondition` 拒绝整个 Event（多 cell 原子性，不得部分应用其余 projected writes）；cell 保持 `value_1`。若此类 Event 越过验证进入 join（防御性路径），join MUST 返回 ⊥，MUST NOT 把 null-basis 盲写当作合法覆盖。
- **Case B**：Control Move 接受并在被 accepted Seal 覆盖后使 cell 收敛到 `value_2`；两个 conformant reducer 以不同输入顺序重放 MUST 得到同一结果。
- “无条件覆盖”语义 MUST 通过 profile 显式注册的专门高权限 event kind 或 §8 conflict-recovery 路径表达，不得通过省略普通 set Control Move 的 `head_eq` 实现。

失败条件：

- Case A 被当作 first set 放行（settled 非初始态时 null basis 仅在 settled == initial 时合法）。
- Case A 在 join 阶段被静默接受为 last-write-wins 覆盖。
- Case B 因实现把 basis 校验错误地提前到与 Case A 相同的拒绝路径而被误拒。

### 2.13 Vector: `ordered_log` issuer 子链 seq 缺口

向量名称：

```text
ak.vector.lattice.ordered_log_gap.v1
```

本向量固化 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §9.3.1 `ordered_log` 的缺口规则：“issuer 子链出现缺口时，缺口后的 entry MUST 保留为 pending / diagnostic 输入，但不得进入 cell value、`state_root` leaf 或授权判断；依赖补齐后按同一规则重算。”

输入（ordered_log cell，`bottom=inert`）：

- **Case A — 缺口存在**：issuer I 的 append entries 以 `issuer_seq ∈ {0, 1, 3}` 到达（seq 2 缺失）。
- **Case B — 缺口补齐后重算**：在 Case A 状态上，seq 2 的 entry 通过 backfill 到达，reducer 重算同一 cell。

期望：

- **Case A**：join 产出的 cell value 仅含 `contiguous_prefix`（seq 0、1）；seq 3 的 entry MUST 作为 `pending_gap` 诊断（`reason=dependency_missing`）暴露，MUST NOT 进入 cell value、`state_root` leaf 或任何授权判断。`bottom` 永不出现（与 §5.1 对照表一致）。
- **Case B**：补齐 seq 2 后，按同一 join 规则确定性重算，cell value 变为 seq 0–3 的完整子链；两个 conformant reducer 以不同到达顺序（先 3 后 2 / 先 2 后 3）重放 MUST 得到 bit-exact 相同的 cell value 与 `state_root` leaf。
- 同一 `(issuer, seq)` 的逐字等价重复 entry MUST 幂等去重，不得产生双重 entry；非等价候选的 winner 选择不属于本向量，见 §2.21。

失败条件：

- Case A 把缺口后的 entry 直接并入 cell value 或 `state_root` leaf。
- Case A 因缺口返回 ⊥ 或阻塞整个 cell（`ordered_log` 的 join 数学上永不产生 ⊥，故按 §9.1.1 登记 `bottom=inert`；缺口只产生 pending / diagnostic，不阻塞协议判断）。
- Case B 重算结果依赖本地接收顺序，两个 reducer 产出不同的 contiguous prefix。

### 2.14 Vector: auth_context epoch pinning 拒绝过期 key

向量名称：

```text
ak.vector.cba_lattice.auth_context_epoch_pinning_reject.v1
```

本向量固化 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §4.1：verifier MUST NOT 只查"当前 DID 文档"，key / credential epoch 的有效性以 `seal_ref` 时点为准。

输入：

- **Case A — 被撤销 key + 旧 seal_ref**：actor 的 key K 在 Seal `S_r` 被撤销；DataEvent 携带 `auth_context.key_epoch` 指向撤销前 epoch、`seal_ref` 为撤销前 Seal，且 `distance(seal_ref, S_r)` 超过 `revocation_freshness_window`。
- **Case B — 撤销宽限窗口内**：同 Case A 但 `distance(seal_ref, S_r)` 在窗口内。
- **Case C — epoch 与 seal_ref 不符**：`auth_context.key_epoch` 在 `seal_ref` 对应控制面状态下不存在或已被替换。

期望：

- Case A：receiver MUST 拒绝或隐藏（`stale_seal_ref` / `failed_precondition`）。
- Case B：receiver MUST 暂时接受，query grade MUST 标记 `stale`；选择拒绝该窗口内 Event 的实现
  不符合本向量。
- Case C：receiver MUST `failed_precondition`，不得回退到"当前 DID 文档"判定。

失败条件：用当前 DID 文档替代 `seal_ref` 时点判定；Case A 被静默接受；Case B 被拒绝，或接受后
不降级 grade。Case A 的 reject 与 hide 只允许改变本地保留/诊断可见性，对 data-cell join 输入
必须同为排除。

### 2.15 Vector: compaction Seal 节律义务

向量名称：

```text
ak.vector.cba_lattice.seal_compaction_interval_enforced.v1
```

本向量固化 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §6.2 的结构性义务与 [`realm.schema.json`](../../artifacts/schemas/realm.schema.json) `seal_compaction_max_interval_ms`。

输入：

- Realm 声明 `seal_compaction_max_interval_ms = X`。
- **Case A**：notary 在 X 内签发携带 `covered_event_digests[]` 的 compaction Seal，其内容等于递归闭包。
- **Case B**：compaction Seal 的 `covered_event_digests[]` 与 `delta[] ∪ predecessor 覆盖集` 不一致。
- **Case C**：live chain 超过 X 仍无 compaction Seal。

期望：

- Case A：receiver 接受；新 verifier 可从该 Seal 接链 bootstrap，不必走链到 genesis。
- Case B：receiver MUST 拒绝该 Seal（`rejected_seal`）。
- Case C：receiver SHOULD 触发治理健康告警；既有 Seal 仍有效（义务是告警与 bootstrap 退化，不是回滚）。

失败条件：Case B 被接受；Case A 的 bootstrap 仍要求 genesis 全链。

### 2.16 Vector: inclusion list 收录义务

向量名称：

```text
ak.vector.cba_lattice.inclusion_list_obligation.v1
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
ak.vector.cba_lattice.notary_fault_equivocation_quarantine.v1
```

本向量固化 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §7.1 与 `ak.notary.fault.equivocation` event kind。

输入：

- signer N 对同一 `(realm_id, notary_seq)` 签出 canonical bytes 不同的 Seal `S_a` / `S_b`。
- 普通成员 M（无任何特殊 capability）提交 `ak.notary.fault.equivocation`，payload 携带 `{signer_id=N, seal_a=S_a, seal_b=S_b}`。

期望：

- 验签 + slot 规则通过即接受该 Control Move（验签即授权，reducer MUST NOT 要求 grant）；fault 记录进入 `ak.component.notary_fault.v1` cell（or_set）。
- fault 记录生效后：N 的后续 Seal MUST 被拒绝；`S_a`、`S_b` 及其后继进入 `fork_quarantine`，普通 joined governance view MUST NOT 纳入；查询依赖该分支时 grade=`forked`。
- 仍有其余合法 signer 时 Realm MUST NOT 整体 pause；无剩余合法 signer 时进入 `notary_paused`，仅 recovery 路径可恢复。
- 两个 Seal 不满足 slot 规则（不同 signer 或不同 seq）时，该 Move MUST `failed_precondition`——合法并发 leaf 不构成 fault。

失败条件：要求提交者持有 capability；fault 后整 Realm 无差别 pause；合法并发 leaf 被误判为 fault。

### 2.18 Vector: threshold forensic attribution 声明

向量名称：

```text
ak.vector.cba_lattice.threshold_forensic_attribution.v1
```

本向量固化 [`realm.schema.json`](../../artifacts/schemas/realm.schema.json) `notary.forensic_attribution` 与 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §7.1 的算术规则。

输入：

- **Case A**：threshold notary,n=5,k=3（2k>n），`forensic_attribution="quorum_intersection"`。
- **Case B**：n=5,k=3,`forensic_attribution="waived"`。
- **Case C**：n=4,k=2（2k≤n），`forensic_attribution="quorum_intersection"`。
- **Case D**：threshold notary 缺 `forensic_attribution` 字段。

期望：

- Case A：accept。
- Case B / Case C：reducer MUST 在 `ak.realm.create` 拒绝（取值与 2k>n 算术关系不符）。
- Case D：schema 校验失败（threshold 变体必填该字段）。

失败条件：Case B/C 被接受；Case D 通过 schema 校验。

### 2.19 Vector: open_set 并发撤销 fail closed

向量名称：

```text
ak.vector.cba_lattice.open_set_concurrent_revocation_fail_closed.v1
```

本向量固化 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §4.3 与 §6.3：`open_set` notary profile 下，撤销 Seal 与 DataEvent 的 `seal_ref` 并发时，receiver 必须按 joined control view 重判授权，不能因为二者互不可达而把撤销窗口当成未发生。

输入（fixture：[`cba-lattice-fixture.json`](../../artifacts/fixtures/cba-lattice-fixture.json) `open_set_concurrent_revocation_fail_closed`）：

- **Case A**：两个并发 Seal leaf 中，一个覆盖 capability grant，另一个覆盖同一 grant 的 revoke；DataEvent 的 `seal_ref` 指向 grant leaf。
- **Case B**：承载授权判定的 control cell 在并发 join 后进入 `⊥`，且 `bottom=reject`。
- **Case C**：轻客户端只持有单 leaf 视图，无法独立验证 multi-leaf union basis。
- **Case D**：receiver 先接受 DataEvent `E` 并物化 cell X write，再接受以 `E` 为 critical causal dependency 的 DataEvent `D` 并物化 cell Y write；随后并发撤销 leaf `R` 迟到。

期望：

- Case A：receiver MUST 按 joined control view 判定该 capability 已撤销，DataEvent MUST fail closed（`stale_seal_ref`）；并发分支不计算 `distance`，不享受新鲜度窗口。
- Case B：依赖该 cell 的 DataEvent 与 Control Move MUST fail closed（`cell_in_bottom_state` / `failed_bottom`）。
- Case C：轻客户端 MUST hold pending 或 fail closed，MUST NOT 用单 leaf 授权结论接受该 DataEvent。
- Case D：join `R` 后 `E` MUST `stale_seal_ref`，其 cell X write MUST 被追溯移除；`D` 与所有直接 / 间接依赖 `E` 的 accepted 后继 MUST 转为 `result=pending, reason=dependency_missing`，其 projected writes（含 cell Y）同步移除。最终 accepted set 与 projection MUST 等于从一开始就持有 `{S0,R}` 的 receiver，且与到达顺序无关。

失败条件：用 `seal_ref` 单分支接受并发撤销后的 DataEvent；把并发撤销套入后继距离窗口；轻客户端无法验证 joined view 时仍接受；只移除 `E` 而保留依赖 `E` 的 `D` / 后继 projected writes，导致先接受后撤销与先撤销后接收的 projection 不同。

### 2.19.1 Vector: Circle lifecycle basis 与 archive freshness

向量名称：

```text
ak.vector.circle.lifecycle_basis_and_archive_freshness.v1
```

本向量固化 [`circle.md`](../models/circle.md) §6.1 与 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §4.3：Circle `state=active` 是事件 CBA 基线中的授权输入，不能读取 receiver 当前 projection 代替；线性 archive、并发 archive、tombstone 与 restore barrier 必须得到唯一分类。

输入（fixture：[`circle-scope-fixture.json`](../../artifacts/fixtures/circle-scope-fixture.json) `lifecycle_basis_cases`）：

- **Case A — 基线内 inactive**：DataEvent 的 `seal_ref` view 或 Control Move 的 `seal_basis` joined view 中 Circle 已 archived。
- **Case B — 线性 archive**：DataEvent 的 `seal_ref` view 中 Circle active，后继 Seal 覆盖 archive；分别构造窗口内与超窗距离。
- **Case C — 并发 archive**：`open_set` 两个互不可达 leaf 分别承载 DataEvent 基线与 Circle archive，joined lifecycle 为 archived。
- **Case D — tombstone**：`seal_ref` 后继 Seal 覆盖 Circle tombstone，即使距离仍在普通 freshness window 内。
- **Case E — restore barrier**：`seal_ref` 位于 archive 前，receiver 当前 view 已经过 archive → restore 并重新 active。
- **Case F — Control Move**：分别在 active / archived 的 `seal_basis` joined view admission，并登记 Seal step 8 的冻结 predecessor 重验基线。

期望：

- Case A：MUST `failed_precondition`，reason=`circle_not_active`；不得用 receiver 较新的 projection 改写结果。
- Case B：窗口内只进入 `stale_eligible`，若接受 query grade MUST 为 `stale`；超窗 MUST 拒绝或隐藏，reason=`stale_seal_ref`。后继 archive 不得被误报为基线内 `circle_not_active`。
- Case C / D：MUST 立即拒绝或隐藏，reason=`stale_seal_ref`，`freshness_window_applies=false`；轻客户端无法验证 joined view 时只能 pending 或 fail closed。
- Case E：restore MUST NOT 追溯恢复旧 `seal_ref`；producer 必须换用包含 restore 的新 active 基线。
- Case F：admission 与 Seal 重验都只读取登记的 CBA 基线，不读取本地当前 projection。

失败条件：相同事件因 receiver 当前 Circle projection 不同而一方接受、一方 `circle_not_active`；并发 archive 获得 freshness window；tombstone 获得宽限；restore 后接受 archive 前的旧基线；Control Move 不在 `seal_basis` / Seal frozen predecessor view 中重验。

### 2.20 Vector: conflict-recovery Move

向量名称：

```text
ak.vector.cba_lattice.conflict_recovery_move.v1
```

本向量固化 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §9.5：`bottom=reject` control cell 进入 `⊥` 后，只能由满足 recovery 授权、pre-conflict witness、sealed finality 与撤销新鲜度要求的 conflict-recovery Move 恢复为单值。

输入（fixture：[`cba-lattice-fixture.json`](../../artifacts/fixtures/cba-lattice-fixture.json) `conflict_recovery_move`）：

- **Case A**：合法 recovery Move，`refs[]` 同时携带 critical `recovery_capability` 与 `state_witness`，witness 可重建 pre-conflict `state_root`，recovery capability 已 sealed 且未被撤销。
- **Case B**：缺失 `state_witness` 或 witness inclusion proof 无法重建 `state_root`。
- **Case C**：`state_witness` 已位于冲突之后，或与触发 `⊥` 的 sibling Move 有因果路径。
- **Case D**：`recovery_capability` 未 sealed、未出现在 witness state root 中，或 local frontier 已观察到晚于 witness 的 revoke / supersede。
- **Case E**：recovery Move 未经控制面 Seal 接受。

期望：

- Case A：reducer MAY 把该 `bottom=reject` cell 从 `⊥` 解析为 recovery Move 声明的单一合法值；后续依赖该 cell 的判定按恢复后的 sealed state 执行。
- Case B：MUST 拒绝（`recovery_witness_missing` / `recovery_witness_invalid`）。
- Case C：MUST 拒绝（`recovery_witness_post_conflict`）。
- Case D：MUST 拒绝（`recovery_capability_not_sealed` / `recovery_witness_revoke_lagging`）。
- Case E：MUST 拒绝；unsealed recovery Move 不得改变 `⊥` cell。

失败条件：普通 Control Move 在 `⊥` 下绕过 recovery 例外；post-conflict witness 被接受；recovery capability 未 sealed 或已撤销仍生效；未 sealed 的 recovery Move 改变 canonical state。

### 2.21 Vector: `ordered_log` issuer equivocation winner

向量名称：

```text
ak.vector.lattice.ordered_log_join.v1
```

本向量固化 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §9.3.1 `ordered_log` 的 issuer 顺序与 equivocation 收敛规则，其 winner 键来自 [`encoding.md` §4.2](./encoding.md) 的全协议唯一 tie-break（逻辑 slot equivocation 候选集），digest 定义见 [`encoding.md` §6](./encoding.md)。

输入（ordered_log cell，`bottom=inert`；fixture：[`cba-lattice-fixture.json`](../../artifacts/fixtures/cba-lattice-fixture.json) `ak.vector.lattice.ordered_log_join.v1`）：

- **Case A — per-issuer 顺序**：两个 issuer 各自提交 `issuer_seq ∈ {0, 1}`，到达顺序交错。
- **Case B — 逐字等价重复**：同一 `(cell, actor_id, issuer_seq)` 的两条 entry，完整 canonical `write.op` bytes 相同。
- **Case C — equivocation**：同一 `(cell, actor_id, issuer_seq)` 的两条 entry，完整 canonical `write.op` bytes 不同（含 `op.value` 相同而 `op` 其它字段不同的子例，以及 `op.value` 不含任何 `entry_id` 字段的子例），两个候选 Event 的 canonical `event_digest` 不同。
- **Case D — 因果边不改变 winner**：与 Case C 相同的候选集，但较小 `event_digest` 的候选通过 `prev_refs` / `causal_refs` 因果地晚于较大者。
- **Case E — digest collision**：两个候选的 canonical `envelope_without_proofs_unsigned_actor_kind` bytes 不同，却得到完全相同的 typed `event_digest`（同 suite、同 octets）。
- **Case F — 仅 proofs / reducer stamp 不同**：两个候选的 canonical digest preimage bytes 逐字相同，只有 `proofs` 集或 reducer-stamped `actor_kind` 不同。`scope_ref` 不同必然改变 digest，不属于本例。
- **Case G — 跨 suite 比较**：两个候选使用不同 digest suite，且 typed wire string 的 UTF-8 顺序与 decoded digest octets 顺序**相反**。

期望：

- **Case A**：每个 issuer 子链的期望起点固定为 `issuer_seq=0`，只有从 `0` 起的连续 prefix 进入 cell value；输入顺序的任意排列 MUST 产出 bit-exact 相同的 cell value 与 `state_root` leaf。实现 MUST NOT 把该 issuer 的最小已见 seq 当作起点——只到达 `issuer_seq=3` 时 MUST 报告 `missing_seq=0` 的 pending gap，MUST NOT 物化 seq 3。
- **Case B**：幂等去重，该 slot 只产生一条 entry。
- **Case C**：`event_digest` 按 §4.2 decoded-octets 比较取**最大**的候选进入连续 prefix；loser MUST 保留为 duplicate/equivocation 诊断，且 MUST 仍留在 canonical event log 与审计视图中，MUST NOT 被删除。等价性判定 MUST 使用完整 canonical `write.op` bytes：`op.value` 相同而 `op` 其它字段不同的候选仍是 equivocation；`op.value` 不含 `entry_id` 字段不得导致回退到到达顺序。
- **Case D**：winner 与 Case C 相同。因果边、`prev_refs`、HLC 与到达顺序 MUST NOT 改变 slot winner，也不得把 seq 复用解释为合法的下一条 append。
- **Case E**：MUST fail closed（digest collision），MUST NOT 回退到 `event_id`、`op.value` 内任一字段、到达顺序或实现私有 ID。
- **Case F**：视为同一 producer-signed Event 内容，MUST NOT 报 collision；`proofs` 按 proof profile 合并，reducer stamps 按其各自验证规则处理。
- **Case G**：winner 由 decoded digest octets 决定，MUST NOT 由 `<suite>:` 前缀的字符串顺序决定。

失败条件：

- 用 `event_id`、`created_at`、HLC、`actor_seq`、到达顺序或某个领域字段（含 `op.value.entry_id` 一类实现私有 id）选 winner（`encoding.md` §4.2 禁止键）。
- 选 bytewise 最小而非最大 `event_digest`。
- 直接比较 typed digest wire string，使 suite 名先于内容决定 winner。
- 只比较 `op.value` 而非完整 `write.op`，把 `op` 其它字段不同的候选误判为 duplicate。
- 从该 issuer 的最小已见 seq 起算 prefix，而不是固定从 `0` 起。
- equivocation loser 被从 canonical event log 或审计视图中移除，或未暴露 winner/loser 诊断。
- Case D 因存在因果边而改判 winner。
- Case F 被误报为 digest collision。

## 3. Redaction 与 Snapshot Vectors

### 3.1 目标

本节定义 redaction 的执行顺序、保留字段与可见性收敛规则，并涵盖与之相邻的 snapshot pruning / inclusion-challenge 向量（§3.5–§3.6，`domain=snapshot`）。
所有实现必须将 redaction 视为“可验证的内容裁剪”，而非删除事件。

向量命名：

```text
ak.vector.redaction.<scenario>.v1
ak.vector.snapshot.<scenario>.v1
```

### 3.2 Vector: 字段保留规则

向量名称：

```text
ak.vector.redaction.preserve_fields.v1
```

输入：

```json
{
  "target_event": {
    "event_id": "ak:event:0196414c-3000-7000-8000-000000000000",
    "kind": "ak.message.create",
    "realm_id": "ak:realm:0196414c-8000-7000-8000-000000000000",
    "actor_id": "did:webvh:z6mkfixture:alice.example.com",
    "created_at": "2026-04-26T00:00:00Z",
    "hlc": "01970e589d24-0001-aaaaaaaa",
    "prev_refs": [],
    "refs": [],
    "payload": {
      "strand_id": "ak:strand:0196414c-3400-7000-8000-000000000000",
      "content": {
        "kind": "ak.content.text",
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
    "event_id": "ak:event:0196418a-0360-7000-8000-000000000000",
    "kind": "ak.redaction",
    "realm_id": "ak:realm:0196414c-8000-7000-8000-000000000000",
    "actor_id": "did:webvh:z6mkfixture:alice.example.com",
    "created_at": "2026-04-26T00:00:02Z",
    "hlc": "01970e589d24-0002-bbbbbbbb",
    "prev_refs": [
      "ak:event:0196414c-3000-7000-8000-000000000000"
    ],
    "refs": [
      { "id": "ak:grant:019640c5-5800-7000-8000-000000000000", "role": "authorized_by", "critical": true }
    ],
    "payload": {
      "redacts": "ak:event:0196414c-3000-7000-8000-000000000000",
      "reason_code": "policy_recall"
    }
  }
}
```

期望结果：

```json
{
  "event_id": "ak:event:0196414c-3000-7000-8000-000000000000",
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

`kept_envelope_fields` 中的 `redacted_by` / `redaction_reason_code` / `hashes` **不是 redaction event payload 的输入字段**，而是 reducer 在目标事件上派生写入的 tombstone-style 字段，映射规则如下（来源见 event-envelope schema 的对应 `$defs`）:

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
ak.vector.redaction.space_target_ref_schema.v1
```

输入（payload 片段，必须通过 `event-payload.schema.json#/$defs/object_lifecycle_payload`）：

```json schema=schemas/event-payload.schema.json#/$defs/object_lifecycle_payload
{
  "target_ref": "ak:space:019640b6-8000-7000-8000-000000000000",
  "reason": "privacy_cleanup"
}
```

期望结果：

- Payload schema MUST 接受 `ak:space:*` 作为 `ak.redaction` 的 `target_ref` / `object_ref`。
- Reducer 语义仍按 Space 生命周期规则执行：Space 没有独立 `redacted` state，内容清理合并到 Space metadata cleanup / terminal transition；不得因 schema 漏洞把 Space cleanup 路径降级为实现私有扩展。

### 3.3 Vector: redaction 与 policy scope

向量名称：

```text
ak.vector.redaction.policy_scope.v1
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
      "event_id": "ak:event:0196417d-8400-7000-8000-000000000000",
      "kind": "ak.message.create",
      "realm_id": "ak:realm:0196414c-8000-7000-8000-000000000000",
      "created_at": "2026-04-26T00:00:00Z",
      "hlc": "01970e589d25-0001-11111111",
      "payload": {
        "strand_id": "ak:strand:0196417d-8400-7000-8000-000000000000",
        "content": {
          "kind": "ak.content.text",
          "body": "bad link: spam.example/phish"
        }
      }
    },
    {
      "event_id": "ak:event:0196417d-8980-7000-8000-000000000000",
      "kind": "ak.policy.action",
      "realm_id": "ak:realm:0196414c-8000-7000-8000-000000000000",
      "created_at": "2026-04-26T00:00:01Z",
      "hlc": "01970e589d25-0001-22222222",
      "actor_id": "did:webvh:z6mkfixture:policy-bot.example.com",
      "payload": {
        "target_id": "ak:event:0196417d-8400-7000-8000-000000000000",
        "policy_scope": "public",
        "decision": "quarantine"
      }
    },
    {
      "event_id": "ak:event:0196417d-8f00-7000-8000-000000000000",
      "kind": "ak.redaction",
      "realm_id": "ak:realm:0196414c-8000-7000-8000-000000000000",
      "actor_id": "did:webvh:z6mkfixture:policy-admin.example",
      "payload": {
        "redacts": "ak:event:0196417d-8400-7000-8000-000000000000",
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
ak.vector.redaction.hard_erasure_receipt.v1
```

期望：

- hard erasure 在被测存储边界内删除 payload bytes 与派生明文。
- 实现保留 verification stub：原始 event id、验证事件图所需的 Event envelope digest / proof `event_digest`、redaction event id、erasure reason、执行服务 DID、执行时间和签名 receipt。签名 receipt MUST 符合 `ak.schema.erasure_receipt.v1`；若作为历史事件发布，Event.kind MUST 为 `ak.audit.erasure_receipt`。
- stub 不得额外保留已擦除明文字段的 standalone content hash、payload-only digest 或未加盐搜索 fingerprint；若审计必须保留内容承诺，必须使用每事件 salt 或 HMAC/pepper commitment，并把 secret 留在 legal-hold 边界或按 erasure policy 销毁。
- backfill 返回 redacted / erased stub，不伪造替代事件，也不静默造成历史缺口。
- legal hold 存在时阻止 hard erasure，但默认展示仍应用 redaction。

### 3.5 Vector: snapshot pruning retains verification stub

向量名称：

```text
ak.vector.redaction.snapshot_pruning_stub.v1
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
ak.vector.snapshot.inclusion_challenge.v1
```

本向量固化 [`snapshot-schema.md`](./snapshot-schema.md) §6 `event_set_commitment` 的 inclusion-challenge 采样与 merkle branch 校验规则，使 high-assurance bootstrap 不依赖单一实现的私有判断。该向量已在 [`vector-registry.json`](../../artifacts/registry/vector-registry.json) 中注册为 active，并由 [`sync-fixture.json`](../../artifacts/fixtures/sync-fixture.json) 的 `snapshot_inclusion_challenge` 机器 fixture 及其 registered runner 承载。实现 MUST 执行该 fixture-backed gate，并按本节 prose 与 fixture 固化的规则校验 high-assurance bootstrap。

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
适配对象（下列为 profile 短名，统一用下划线；canonical id 形如 `ak.profile.<短名>.v1`，见 [`conformance-profiles.md`](./conformance-profiles.md)）：`identity_registry`, `principal_server_events_api`, `e2ee_client`, `enterprise_client`, `agent_runtime`.

向量命名：

```text
ak.vector.capability.<scenario>.v1
```

每个向量应检查：

- selector scope 是否正确绑定到 actor/device/realm/action。
- 授权时间窗约束是否导致一致结果。
- 关键路径必须拒绝 `authorization-only` 假阳性。

### 4.2 Vector: 多级委托链

向量名称：

```text
ak.vector.capability.authority_chain.v1
```

输入事件链：

```json
{
  "base": {
    "kind": "ak.capability.grant",
    "grant_id": "ak:grant:019640d0-b800-7000-8000-000000000000",
    "subject": "did:webvh:z6mkfixture:root-admin.example.com",
    "actions": [
      "ak.realm.admin"
    ],
    "constraints": []
  },
  "authority_chain": [
    {
      "event_id": "ak:event:019640d0-c000-7000-8000-000000000000",
      "kind": "ak.capability.grant",
      "realm_id": "ak:realm:0196414c-8000-7000-8000-000000000000",
      "actor_id": "did:webvh:z6mkfixture:root-admin.example.com",
      "payload": {
        "grant_id": "ak:grant:019640d0-c000-7000-8000-000000000000",
        "issuer_authority_refs": [{"kind": "grant", "grant_id": "ak:grant:019640d0-b800-7000-8000-000000000000"}],
        "subject": "did:webvh:z6mkfixture:ops.example.com",
        "resources": [
          {
            "kind": "realm",
            "realm_id": "ak:realm:0196414c-8000-7000-8000-000000000000",
            "match_scope": "realm_wide"
          }
        ],
        "actions": [
          "ak.invite.create"
        ],
        "constraints": [
          {
            "constraint_kind": "temporal",
            "effect": "allow",
            "not_before": "2026-04-20T00:00:00Z",
            "expires_at": "2026-05-20T00:00:00Z"
          },
          {
            "constraint_kind": "quota",
            "constraint_subkind": "rate",
            "effect": "allow",
            "rate_limit": "5/hour"
          }
        ]
      },
      "refs": [
        { "id": "ak:grant:019640d0-b800-7000-8000-000000000000", "role": "authorized_by", "critical": true },
        { "id": "ak:grant:019640d0-b800-7000-8000-000000000000", "role": "parent_grant", "critical": true }
      ]
    },
    {
      "event_id": "ak:event:019640d0-c400-7000-8000-000000000000",
      "kind": "ak.capability.grant",
      "realm_id": "ak:realm:0196414c-8000-7000-8000-000000000000",
      "actor_id": "did:webvh:z6mkfixture:ops.example.com",
      "payload": {
        "grant_id": "ak:grant:019640d0-c400-7000-8000-000000000000",
        "issuer_authority_refs": [{"kind": "grant", "grant_id": "ak:grant:019640d0-c000-7000-8000-000000000000"}],
        "subject": "did:webvh:z6mkfixture:intern.example.com",
        "resources": [
          {
            "kind": "realm",
            "realm_id": "ak:realm:0196414c-8000-7000-8000-000000000000",
            "match_scope": "realm_wide"
          }
        ],
        "actions": [
          "ak.invite.create"
        ],
        "constraints": [
          {
            "constraint_kind": "quota",
            "constraint_subkind": "rate",
            "effect": "allow",
            "rate_limit": "2/day"
          },
          {
            "constraint_kind": "scope_limitation",
            "effect": "allow",
            "allowed_audiences": [
              "did:webvh:z6mkfixture:partner.example",
              "did:webvh:z6mkfixture:vendor.example"
            ]
          }
        ]
      },
      "refs": [
        { "id": "ak:grant:019640d0-c000-7000-8000-000000000000", "role": "authorized_by", "critical": true },
        { "id": "ak:grant:019640d0-c000-7000-8000-000000000000", "role": "parent_grant", "critical": true }
      ]
    }
  ],
  "action_query": {
    "actor_id": "did:webvh:z6mkfixture:intern.example.com",
    "action": "ak.invite.create",
    "resource": "ak:realm:0196414c-8000-7000-8000-000000000000",
    "request_time": "2026-04-26T01:00:00Z",
    "request_audience": "did:webvh:z6mkfixture:vendor.example"
  }
}
```

期望输出：

```json
{
  "authorized": true,
  "valid_chain": [
    "ak:grant:019640d0-b800-7000-8000-000000000000",
    "ak:grant:019640d0-c000-7000-8000-000000000000",
    "ak:grant:019640d0-c400-7000-8000-000000000000"
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
ak.vector.capability.revoke_rollback.v1
```

输入：

```json
{
  "events": [
    {
      "event_id": "ak:event:01964101-2800-7000-8000-000000000000",
      "kind": "ak.capability.grant",
      "payload": {
        "grant_id": "ak:grant:01964101-2800-7000-8000-000000000000",
        "subject": "did:webvh:z6mkfixture:alice.example.com",
        "actions": [
          "ak.message.create"
        ]
      },
      "created_at": "2026-04-26T00:00:00Z"
    },
    {
      "event_id": "ak:event:01964181-2800-7000-8000-000000000000",
      "kind": "ak.capability.revoke",
      "payload": {
        "grant_id": "ak:grant:01964101-2800-7000-8000-000000000000"
      },
      "created_at": "2026-04-26T00:00:01Z"
    },
    {
      "event_id": "ak:event:019641d1-2800-7000-8000-000000000000",
      "kind": "ak.member.state",
      "payload": {
        "actor_id": "did:webvh:z6mkfixture:alice.example.com",
        "membership": "leave"
      },
      "created_at": "2026-04-26T00:00:02Z"
    },
    {
      "event_id": "ak:event:0196414c-c04a-7000-8000-000000000000",
      "kind": "ak.message.create",
      "actor_id": "did:webvh:z6mkfixture:alice.example.com",
      "created_at": "2026-04-26T00:00:03Z",
      "payload": {
        "strand_id": "ak:strand:0196418d-cc00-7000-8000-000000000000",
        "content": {
          "kind": "ak.content.text",
          "body": "should_fail_if_revoke_applies"
        }
      },
      "prev_refs": [
        "ak:event:019641d1-2800-7000-8000-000000000000"
      ]
    }
  ],
  "rollback": {
    "target_event_id": "ak:event:01964181-2800-7000-8000-000000000000",
    "reason": "revoke_undo_invalid_signature"
  }
}
```

期望输出：

- 初始解析：`ak:event:0196414c-c04a-7000-8000-000000000000` 因 revoke 生效应拒绝或标记 soft-fail/rejected（取决于实现策略）。
- 回滚 revoke 后重算：同一事件在回滚前瞻分析中应变为 authorized。
- 回滚必须产生独立可审计结果，不可直接修改历史事件链的 event_id。

验证：

- `accepted` 集合必须对应当前 reducer frontier。
- 回滚后状态必须可复现，并有 `rollback_ref` 或等价证据。

### 4.4 Vector: 审批约束缺失

向量名称：

```text
ak.vector.capability.approval_constraint.v1
```

输入：

```json
{
  "event": {
    "event_id": "ak:event:01964148-a800-7000-8000-000000000000",
    "kind": "ak.policy.action",
    "actor_id": "did:webvh:z6mkfixture:contractor.example",
    "realm_id": "ak:realm:0196414c-8000-7000-8000-000000000000",
    "hlc": "01970e589d26-0001-aaaaaaaa",
    "payload": {
      "action": "ak.realm.admin",
      "approval_required": true,
      "approval_quorum": 2,
      "policy_scope": "ak:realm:0196419b-0000-7000-8000-000000000000"
    },
    "refs": [
      { "id": "ak:grant:0196419b-298e-7368-9a80-000000000000", "role": "authorized_by", "critical": true }
    ]
  },
  "capabilities": [
    {
      "kind": "ak.capability.grant",
      "subject": "did:webvh:z6mkfixture:contractor.example",
      "actions": [
        "ak.realm.admin"
      ]
    },
    {
      "kind": "ak.capability.grant",
      "subject": "did:webvh:z6mkfixture:approver-1.example.com",
      "actions": [
        "ak.approval.vote"
      ]
    }
  ]
}
```

期望输出：

```json
{
  "authorized": false,
  "failure_reason_code": "approval_required",
  "next_state": "proposal",
  "visible_to": ["initiator", "approvers"]
}
```

判定要求：

- 即便有高权限 grant，若 approval constraint 未满足，不得直接通过写入执行。
- 必须有可复现的 proposal / review 生命周期。
- 通过审核后应产生可验证的审批完成事件，再以独立 action event 执行。

### 4.5 Vector: 成员资格不是 baseline 能力

向量名称：

```text
ak.vector.capability.membership_is_not_baseline.v1
```

输入（fixture：[`capability-fixture.json`](../../artifacts/fixtures/capability-fixture.json) `membership_without_capability_denies_core_writes`）：一个 `membership="join"` 的 Realm 成员，但**没有任何 capability grant**（`grants: []`），尝试 `ak.message.create` 等核心写入 action。

期望输出：

```json
{
  "authorized": false,
  "failure_reason_code": "missing_capability"
}
```

判定要求：

- 成员资格（`ak.member.state{join}`）本身**不**隐含任何 action capability——授权核心是 allow-grant + explicit revoke（[`../authz/capabilities.md`](../authz/capabilities.md)、[`../governance/content-moderation.md` §2.4](../governance/content-moderation.md)），不存在"成员即可写"的 baseline 能力。
- 无匹配 grant 时核心写入 MUST 被拒（`missing_capability`），且**没有任何 deny 层 / 成员身份能补足缺失的 capability**。

### 4.6 Vector: Realm Authority Root Bootstrap

向量名称：

```text
ak.vector.realm.authority_root_bootstrap.v1
```

本向量固化 [`realm-and-space.md`](../models/realm-and-space.md) §2.5 与 [`capabilities.md`](../authz/capabilities.md) §3.2：`ak.realm.create` MUST 在同一原子 unit 内物化五条 registered cell write，其中第五条是唯一的 `ak.component.realm.authority_root.v1:null` cell，值恰为 `{controller_id = payload.object.created_by, controller_epoch = 0, authority_generation = 0, capability_action_registry_digest = payload.object.capability_action_registry_digest}`。

正例：五条 registered write 全部落入 genesis `state_root`，创建者在 genesis Seal 下即具有 effective `ak.realm.owner`；该批 accepted 后，创建者凭 accepted-Seal root-cell inclusion proof 可直接 author `ak.strand.create`（该 kind 在 owner operational coverage 内），也可在 owner 的 `grant_authority_actions` 上界内向成员签发 strand grant。

负例（每条各自 MUST fail closed，不得留下 Realm / membership 半成品）：

- 缺 authority-root cell → `realm_authority_root_missing`；
- author 自行提供 `controller_id` / 非零 `controller_epoch` / 非零 `authority_generation` / 与签名 payload 不一致的 registry digest / 四字段之外的额外成员 → `realm_authority_root_conflict`；
- `capability_action_registry_digest` 对应 snapshot 不可取得或 JCS 重算不一致 → `capability_registry_basis_unavailable`，且 MUST NOT 回退到本机当前 embedded registry；
- 夹带旧四项 / 五项 / 三项 founding-grant shape 的 self grant MUST NOT 被识别为 authority root，仍按 §3.2 普通 issuer 上界判定为 `grant_exceeds_issuer_authority`；
- staged root proof 在 genesis batch 之外重放，或在 batch 内改用 accepted-Seal inclusion proof（此时尚无 accepted Seal）→ `realm_authority_controller_mismatch`。

只有 `ak.member.state{join}`、没有任何显式 grant 的成员仍 MUST `missing_capability`：authority root 只为 root controller 建立 authority，MUST NOT 为普通成员建立 baseline capability，也 MUST NOT 由 `created_by`、membership 或 `realm_state.owner` 投影镜像回退推导。

### 4.7 Vector: Quota Linearizable Authority

向量名称：

```text
ak.vector.constraint.quota_linearizable_authority.v1
```

本向量固化 [`constraint-schema.md`](../authz/constraint-schema.md) §8.1：同一 quota key / UTC window 在 enforcing service 的所有节点间共享一个逻辑线性化 authority。counter=99、limit=100 时两个节点并发争抢最后名额，恰一条接受、另一条 `quota_exceeded`，最终 counter=100 且 overshoot=0；同 idempotency identity 的成功重试只计一次；authority 不可达时业务副作用前 fail closed；`period=P1M` 因非固定长度被 schema 拒绝。

### 4.8 Vector: Temporal Action Gate 与 Object Window

向量名称：

```text
ak.vector.constraint.temporal_action_window.v1
```

本向量固化 [`constraint-schema.md`](../authz/constraint-schema.md) §14.2 / §16.1：`applies_to_actions` 不命中时，对 allow constraint 返回 neutral true，对 deny / quarantine / review 返回未命中 false；命中 `ak.message.revise.own` / `ak.message.redact.own` 时，从 reducer 已验证的 target `created_at` 加对应 duration 计算 deadline，并与一次固定的 verification time / skew 比较。窗口外、target time 缺失 / 不可验证或 duration 计算失败必须 fail closed；recurrence 命中不得提前返回而跳过 object window。

### 4.9 Vector: 敏感字段读路径处理

向量名称：

```text
ak.vector.auth.sensitive_field_handling.v1
```

本向量固化 [`constraint-schema.md`](../authz/constraint-schema.md) §16.2.1：`field_access.sensitive_fields` / `sensitive_handling` 是读路径输出义务，不是 admit/deny gate；命中敏感字段后，返回给请求方的 projection 必须按声明处理，不能泄露原值。

输入（fixture：[`capability-fixture.json`](../../artifacts/fixtures/capability-fixture.json) `sensitive_field_handling`）：同一 read projection 包含 `profile.display_name`、`profile.email`、`profile.ssn`、`profile.salary`，策略分别覆盖 `hash`、`redact`、默认 `omit` 与无法取得 keyed digest key 的降级路径。

期望：

- `hash` 且具备 key/salt 时，输出 keyed/salted digest 或等价不可逆摘要，MUST NOT 返回原值或裸明文 hash。
- `hash` 但缺少 key/salt 时，MUST 降级为 `omit`，MUST NOT 返回原值。
- `redact` 时，输出不可逆占位（例如 `null` 或 `"[redacted]"`），MUST NOT 返回原值或可逆派生。
- 未声明 `sensitive_handling` 时默认 `omit`。
- 非敏感且允许读取的字段保持输出。

失败条件：任一敏感字段以原值、裸 hash、可逆编码或未声明处理的形式返回；缺 key 的 `hash` 路径没有降级为 `omit`。

## 5. Sync Vectors

### 5.1 目标

本文定义 Client Sync、timeline ordering、pagination、snapshot、backfill 与 E2EE / MLS 同步的跨实现测试向量。当前向量覆盖标准对象 / Morph 模型。

实现声称支持以下 profile 时 SHOULD 运行本文对应向量：

- `ak.profile.minimal_client.v1`
- `ak.profile.chat_mvp.v1`
- `ak.profile.kanban_mvp.v1`
- `ak.profile.full_client.v1`
- `ak.profile.e2ee_client.v1`
- `ak.profile.principal_server_events_api.v1`
- `ak.profile.principal_server.v1`

### 5.2 通用约定

测试向量使用以下简化字段：

```json
{
  "event_id": "ak:event:019640ed-8000-7000-8000-000000000000",
  "actor_id": "did:webvh:z6mkfixture:actor-a.example.com",
  "actor_seq": 1,
  "hlc": "019b76daa800-0000-a13f9c2e",
  "prev_refs": [],
  "refs": [],
  "kind": "ak.strand.update",
  "unsigned": {
    "target_ref_hint": "ak:strand:019640c5-0000-7000-8000-000000000000"
  },
  "content_digest": "sha256:..."
}
```

实现 MAY 使用真实 canonical JSON、CID、签名和 hash 替换示例值，但 MUST 保持以下语义：

- `event_id` 是内容寻址或签名绑定后的稳定 ID。
- `actor_seq` 在同一 actor 的单条因果路径上严格递增；并发 sibling fork 可出现相同高度。
- `hlc` 是 Hybrid Logical Clock，不能单独决定因果顺序。
- `unsigned.target_ref_hint` MAY 指向标准对象、Morph、Relation、View、Space 或 Realm，仅作为测试向量的阅读辅助；规范性目标必须来自 `payload.*` 字段、`payload.object.id`、precondition cell key 或 registered reducer contract。标准 Event envelope **top-level**（与 `kind` / `actor_id` / `payload` 同级）MUST NOT 出现 `target_ref`；该禁令仅针对 envelope 顶层，**不**适用于 payload 内部合法使用的 `target_ref`（如 §3.2.1 redaction payload 的顶层 `target_ref`）。

### 5.2.1 Vector: Late Key Recovery T0 Determinism

向量名称：

```text
ak.vector.e2ee.late_key_recovery.t0_deterministic_visibility.v1
```

输入：

- 目标密文事件 `E1` 在 sealed history 的 deterministic pre-state `T0` 中对 `receiver` 可见，且 `receiver` 在 `T0` 是 Realm member。
- `receiver` 在 `E1` accepted 之后、late key request 发出之前被 `ak.member.state{membership=ban}` 或等价 remove 事件移出 Realm。
- 两个客户端以不同本地到达顺序观察同一组 sealed events：客户端 A 先看到 `E1` 后看到 ban；客户端 B 先同步到 ban，再通过 backfill 看到 `E1`。
- key backup / archive node / peer share 在发 key 前重新计算 `E1` 的 `T0` membership、history visibility 和当前 share policy。

期望：

- 两个客户端对 `E1` 的 late recovery 结果一致，且只取决于 sealed `T0` effective view，不取决于本地到达顺序或 wall clock。
- 若 `receiver` 在 `T0` 可见且当前 share policy 仍允许历史恢复，late key 可以发放；后续 ban/remove 不 retroactively 改写 `E1` 的 verified timeline。
- 若 `receiver` 在 `T0` 不可见，或 key source 未在发 key 前重新执行 `T0` 校验，必须拒绝并返回 `key_unavailable` / `policy_denied` 类错误。
- 测试不得把“`T0` 后被 ban”单独作为拒绝理由；拒绝理由必须落在 `T0` 不可见或 key source unauthorized。

本节固化两个**独立**向量，各对应 `vector-registry.json` 的不同 id，MUST NOT 合并：

- `ak.vector.e2ee.late_key_recovery.t0_deterministic_visibility.v1`（本节主向量）——断言两客户端对 `E1` late recovery 结果只取决于 sealed `T0` effective view，与本地到达顺序 / wall clock 无关；正路径（`T0` 可见且 share policy 允许）发放、`T0` 不可见拒绝。
- `ak.vector.late_key_recovery.removed_actor.v1`（无 `e2ee.` 段，独立 registry id）——removed_actor negative path 专项：`receiver` 在 `T0` 不可见 / key source unauthorized 时 MUST 拒绝，且拒绝理由 MUST NOT 仅为“`T0` 后被 ban”。

### 5.2.2 Vector: Disappearing Read-trigger Anonymous Aggregate

向量名称：

```text
ak.vector.disappearing.read_trigger_anonymous_aggregate.v1
```

输入：

- Realm 启用 `ak.profile.disappearing.v1`，`ak.realm.disappearing_policy.allowed_triggers` 包含 `on_first_read` 与 `on_last_read`。
- Alice 发送带 `expiry.trigger="on_first_read"` 的 E2EE message `M1`；Bob 与 Carol 均在 send seal 的 eligible reader set 中。
- Bob 的一个授权设备通过 private `ak.read_cursor.advance` 覆盖 `M1`；Carol 没有公开 read receipt。
- Sync / account aggregate service 向其他客户端返回 projection 或 metadata-only expiry hint。

期望：

- `M1` 的 first-read anchor 被设置一次，projection 在 `anchor + ttl_ms + grace_ms` 后降级为 expiry stub。
- Alice、Carol、其它成员、push provider、search service 与默认客户端 projection 均不得看到 Bob 的 `actor_id`、`device_id`、handle、reader count、unread count、IP、在线状态或可跨 message 关联的 reader pseudonym。
- 允许的 trigger metadata 仅限 `source_event_id`、`trigger`、`anchor_hlc`、`expires_at` 与不可反查的 aggregate status；不得包含 read receipt UI payload。

### 5.2.3 Vector: Disappearing Read-trigger Idempotent Replay

除单服务 replay 外，实现还 MUST 运行 `ak.vector.disappearing.read_trigger_multi_aggregator_convergence.v1`：两个聚合服务以相反顺序接收同一 contribution 集合，per-token `min` 与 aggregate `min` join 必须产生逐字节相同的 `on_first_read` anchor；晚到更早值只能把 expiry 提前，不能恢复已 shred 内容。

向量名称：

```text
ak.vector.disappearing.read_trigger_idempotent_replay.v1
```

输入：

- 同一 principal 的两台设备对同一 message `M1` 乱序提交 read cursor / receipt，HLC 分别为 `H1` 与 `H2`。
- 攻击者重放 `M1` 的旧 read-trigger contribution，并尝试把同一 opaque token 绑定到另一条 message `M2`。
- `on_first_read` anchor 已经由第一次有效 contribution 接受。

期望：

- 同一 `(message, principal)` 的重复 contribution 只计一次；重复投递返回 success / already_observed 等幂等结果，不刷新 anchor。
- 两台设备的 read cursor 按 [`../discovery/read-receipts.md` §6.5](../discovery/read-receipts.md) 的因果优先规则收敛：被因果支配的 position 被忽略（与其 HLC 大小无关）；仅当两个 position 因果不可比时才忽略较旧 HLC，HLC 相等时按 read cursor device tie-break。无论走哪条分支，都只产生一个 principal-level contribution。
- 跨 message、跨 scope、跨 trigger 或 policy frontier 不匹配的 replay MUST fail closed，不得让 `M2` 提前过期。

### 5.2.4 Vector: Disappearing On-last-read Offline Window

向量名称：

```text
ak.vector.disappearing.on_last_read_offline_window.v1
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
  "realm_id": "ak:realm:0196419b-0000-7000-8000-000000000000",
  "events": [
    {
      "kind": "ak.space.create",
      "unsigned": {
        "target_ref_hint": "ak:space:019640b6-8000-7000-8000-000000000000"
      },
      "payload": {
        "object": {
          "id": "ak:space:019640b6-8000-7000-8000-000000000000",
          "schema": "ak.schema.space.v1",
          "realm_id": "ak:realm:0196419b-0000-7000-8000-000000000000",
          "kind": "board",
          "title": "Release Board",
          "created_by": "did:webvh:z6mkfixture:alice.example.com",
          "created_at": "2026-04-26T00:00:00Z"
        }
      }
    },
    {
      "kind": "ak.space.create",
      "unsigned": {
        "target_ref_hint": "ak:space:01964010-8400-7000-8000-000000000000"
      },
      "payload": {
        "object": {
          "id": "ak:space:01964010-8400-7000-8000-000000000000",
          "schema": "ak.schema.space.v1",
          "realm_id": "ak:realm:0196419b-0000-7000-8000-000000000000",
          "parent_space_id": "ak:space:019640b6-8000-7000-8000-000000000000",
          "kind": "list",
          "title": "Todo",
          "rank": "U",
          "created_by": "did:webvh:z6mkfixture:alice.example.com",
          "created_at": "2026-04-26T00:00:00Z"
        }
      }
    },
    {
      "kind": "ak.strand.create",
      "unsigned": {
        "target_ref_hint": "ak:strand:019640c5-0400-7000-8000-000000000000"
      },
      "payload": {
        "object": {
          "id": "ak:strand:019640c5-0400-7000-8000-000000000000",
          "schema": "ak.schema.strand.v1",
          "realm_id": "ak:realm:0196419b-0000-7000-8000-000000000000",
          "metadata": {
            "title": "Release checklist"
          },
          "tracks": {
            "synthesis": {
              "is_primary": true
            }
          },
          "stage": "planned",
          "created_by": "did:webvh:z6mkfixture:alice.example.com",
          "created_at": "2026-04-26T00:00:00Z"
        },
        "initial_relations": [
          {
            "relation_kind": "contains",
            "from_ref": "ak:space:01964010-8400-7000-8000-000000000000",
            "to_ref": "ak:strand:019640c5-0400-7000-8000-000000000000",
            "fields": {
              "board_space_id": "ak:space:019640b6-8000-7000-8000-000000000000",
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

- Collection projection MUST 返回 `object.id = ak:strand:019640c5-0400-7000-8000-000000000000`。
- 返回项 MUST 位于 `ak:space:01964010-8400-7000-8000-000000000000`。
- View cursor MUST 绑定 projection、view、frontier 与权限上下文。

### 5.4 Vector: Strand Card Move Read-Your-Writes

输入：

```json
{
  "write": {
    "kind": "ak.strand.move",
    "unsigned": {
      "target_ref_hint": "ak:strand:019640c5-0400-7000-8000-000000000000"
    },
    "payload": {
      "board_space_id": "ak:space:019640b6-8000-7000-8000-000000000000",
      "strand_id": "ak:strand:019640c5-0400-7000-8000-000000000000",
      "from_space_id": "ak:space:01964010-8400-7000-8000-000000000000",
      "target_space_id": "ak:space:01964010-8800-7000-8000-000000000000",
      "rank": "U"
    }
  },
  "query": {
    "object_kinds": [
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
- 查询结果中该 Strand item 的 `list_id` MUST 为 `ak:space:01964010-8800-7000-8000-000000000000`。

### 5.5 Vector: Strand Discussion Track Visibility

输入：

```json
{
  "strand_id": "ak:strand:019640c5-0400-7000-8000-000000000000",
  "viewer": "did:webvh:z6mkfixture:viewer.example.com",
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
  "strand_id": "ak:strand:01964195-8400-7000-8000-000000000000",
  "track_name": "discussion",
  "viewer_grants": ["ak.strand.read"],
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
  "strand_id": "ak:strand:01964180-0400-7000-8000-000000000000",
  "events": [
    {
      "kind": "ak.message.create",
      "unsigned": {
        "target_ref_hint": "ak:message:01964147-0400-7000-8000-000000000000"
      },
      "payload": {
        "strand_id": "ak:strand:01964180-0400-7000-8000-000000000000",
        "content": {
          "kind": "ak.content.text",
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

### 5.7 Vector: Account / Events Stream Frame Sequence

`vector_id`: `ak.vector.sync.stream_frame_sequence.v1`

机器 fixture：`sync-fixture.json#stream_frame_sequence`；执行入口以 fixture `runner` 元数据为准。Runner MUST 对 `ak.self.account.stream.subscribe` 与 `ak.self.events.stream.subscribe` 各执行同一组完整 frame trace，而不是把 frame 拆成互不关联的 schema cases。

Cases：

1. `catchup=true`：至少一个带 cursor 的 baseline `delta` 先于带 cursor 的 `catchup_complete`；其间 MAY 有带 cursor 的 `frontier`。
2. `catchup=false`：允许 `delta` / `frontier` / `heartbeat`，但 MUST NOT 出现 `catchup_complete`。
3. `catchup_complete` 先于首个 `delta`，或在 `catchup=false` 出现：trace 拒绝。
4. 服务端有可恢复 cursor 时发 `dropped{cursor,reconnect_after_ms?}`；无可恢复 cursor 时必须改发无 cursor 的 `resync_required`，不得发 cursorless `dropped`。
5. `delta` / `frontier` / `catchup_complete` / `dropped` 的 cursor 可推进 reconnect position；`heartbeat` / `resync_required` / `unauthorized` 不得推进。

Expected：

- server runner 必须证明输出序列满足 catch-up 与 cursor closure；client runner 必须证明持久 reconnect cursor 只取自 cursor-bearing frame。
- 单帧均通过 JSON Schema、但整体顺序违反任一 case 的 trace，仍视为 conformance failure。
- account 与 events stream 对相同控制帧不得采用不同 reconnect 规则。

### 5.8 Vector: To-Device Message Envelope Idempotency

`vector_id`: `ak.vector.sync.to_device_message_idempotency.v1`

机器 fixture：`sync-fixture.json#to_device_message_idempotency`；执行入口以 fixture `runner` 元数据为准。本向量同时使用 fixture 顶层 `schema_validation_cases` 固化 `DeviceMessageEnvelope` 与发送 target 的 required `message_id` wire 形态。

Steps：

1. 发送一个带稳定 `ak:device_message:<uuidv7>` 的消息，不 ack，断开后从 account subscribe 或 device-message list 重投同一 stored envelope。
2. receiver 在 handler 副作用前按 `(sender_principal_id, sender_device_id, message_id)` 查询 durable 去重记录，并在 handler 结果持久化后记录完成；第二次投递只恢复连续完成位点。
3. 以同一 sender-scoped `message_id` 提交不同 canonical target intent；再以两个不同 `message_id` 提交相同业务 content。

Expected：

- 第 1/2 步的 durable handler effect 恰执行一次；重复 envelope 仍可计入累计 ack 的连续完成区间，不得永久阻塞队列清理。
- 同 ID 不同内容 MUST 返回 `duplicate_conflict`、reason `message_id_conflict`，两个版本均不得新增队列项。
- 不同 ID 是两个独立逻辑消息，即使业务 content 相同也各处理一次。
- 缺少 `message_id` 的 envelope 或 send target MUST 在 handler 前以 schema violation 拒绝；kind-specific `transaction_id` / `request_id` 不得替代 envelope ID。

### 5.9 Vector: Read Cursor 多设备合并

`vector_id`: `ak.vector.read_cursor.multi_device_merge.v1`

合并规则的唯一真源是 [`../discovery/read-receipts.md` §6.5](../discovery/read-receipts.md)。本向量固化"因果优先 → 并发比 HLC → HLC 相等比 device_id"三段式，并禁止把它压缩成无条件 HLC max。所有 cursor 同 `(actor_id, realm_id, read_scope)`，均为 actor-private，不进入共享 Realm history。

Cases：

1. **因果支配且 HLC 更大**：cursor A 的 `position.event_id` 在因果图中支配 B，且 A 的 HLC 大于 B。winner MUST 是 A。
2. **因果支配但 HLC 更小**：cursor A 的 position 支配 B，但 A 的 HLC 小于 B（合法的 `expected_future_skew_ms` 窗口内偏斜）。winner MUST 仍是 A；实现 MUST NOT 因 HLC 更大而选 B。
3. **并发且 HLC 不等**：两个 position 在已知 causal closure 内互不可达，HLC 不等。winner MUST 是 HLC 较大者。
4. **并发且 HLC 相等**：两个 position 互不可达且 HLC 全等。winner MUST 是 `device_id` 字典序较大者，且两台设备 MUST 得到逐字节相同的结果。
5. **乱序到达**：把 case 1–4 的每对 cursor 按两种投递顺序各执行一次。
6. **因果不可判定**：接收方尚未补齐足以判断互不可达的 causal closure。实现 MUST 保留当前已合并位置并把结果标记为 provisional，MUST NOT 用 HLC 直接选出 winner 后写入持久 projection。

Expected：

- 两种投递顺序对同一对 cursor 产生相同 winner；合并是幂等且可交换的。
- 合并结果 MUST NOT 回退到任何被 winner 因果支配的更早 position，因此 unread count 不得反弹（[`../discovery/read-receipts.md` §6.6](../discovery/read-receipts.md) 流程第 5 条）。
- 派生的 unread count、badge、push suppression 与 `on_first_read` / `on_last_read` disappearing-message contribution 都以合并 winner 为输入；case 2 选出 B 的实现 MUST 判为 conformance failure。
- 任何实现 MUST NOT 把 case 6 的 provisional 结果作为最终 read position 上报或持久化。

### 5.10 Vector: Account Data CAS 收敛

`vector_id`: `ak.vector.account_data.cas_convergence.v1`

并发写入契约的唯一真源是 [`../models/account-data.md` §5](../models/account-data.md)。本向量证明多设备重试与离线写最终收敛到同一状态，且被覆盖的值不可复活。所有 case 使用同一 `(actor_id, account_data_key)`，服务端只见密文。

Cases：

1. **old-retry-after-new-write**：设备 A 读到 `revision=N` 并构造写入 `W_A`；设备 B 先以 `expected_revision=N` 写入成功（`revision=N+1`）；A 随后重放字节完全相同的 `W_A`。`W_A` MUST 以 `cas_conflict` 拒绝，MUST NOT 存储，`revision` MUST 仍为 `N+1`。
2. **conflict details 足以一次合并**：case 1 的 `cas_conflict` 响应 MUST 携带 `account_data_cas_conflict_details`，且在 key 持有 live value 时 MUST 含 `current_entry`；A 解密、合并后以 `expected_revision=N+1` 写入 MUST 成功，且只需一次往返。
3. **并发 delete / update**：设备 A 以 `expected_revision=N` 发 `resource.delete`，设备 B 以同一 `expected_revision=N` 发 `resource.replace`。恰好一个成功；失败方收到 `cas_conflict` 且不产生任何存储副作用。
4. **两设备反序到达**：把 case 1 与 case 3 的请求对以两种到达顺序各执行一次。两次的终态 `revision` 与 `content` MUST 逐字节相同。
5. **tombstone GC 后不复活**：删除该 key 得到 tombstone `revision=M`；GC 掉 tombstone 元数据后，持有 `expected_revision<M` 的离线设备重放旧写。该写 MUST 以 `cas_conflict` 拒绝；`resource.get` 的 `not_found` details MUST 给出 `current_revision=M`。
6. **create 与 recreate**：对从未写入的 key 用 `expected_revision=0` 创建 MUST 成功；重复该请求 MUST 以 `cas_conflict` 拒绝。对已 tombstone 的 key 用 `expected_revision=M` 重建 MUST 成功。
7. **value_tombstone 类型不得物理删除**：对 `deletion_mode=value_tombstone` 的 key（例如 `ak.file_transfer.v1:<transfer_key>`）调用 `ak.self.account_data.resource.delete` MUST 被拒绝；其删除态只能作为 value 写入，且任一副本观察到该终态后 MUST NOT 被后续非 deleted 状态复活。

Expected：

- 服务端 MUST NOT 解密、比较或合并 `content`；所有领域合并只发生在客户端明文上。
- 每个 `(actor_id, account_data_key)` 的 `revision` 单调递增且 MUST NOT 回退；被拒绝的写 MUST NOT 推进它，也 MUST NOT 向其它设备 fanout。
- 任意投递顺序下，所有设备在耗尽重试循环后 MUST 收敛到同一 `(revision, content)`。
- 缺少 `expected_revision` 的 `ak.account_data.set` payload、`resource.replace` body 或 `resource.delete` query MUST 在 handler 前以 `schema_violation` 拒绝。

### 5.11 Vector: Private View 与 Notification 收件箱 account-data 承载

`vector_id`: `ak.vector.account_data.private_view_inbox_binding.v1`

两个 key pattern 的唯一真源是
[`../models/views.md` §3.1](../models/views.md)、
[`../discovery/client-preferences.md` §3.2](../discovery/client-preferences.md) 与
`registry/account-data-key-registry.json` 的
`ak.views.private.<view_id>` / `ak.notifications.inbox.<notification_id>` 两行。
本向量固化"key 必须带完整 typed id 尾缀、value 必须是加密 envelope、明文语义只能在
holder 客户端校验"三点。服务端只见 key 与密文。

Cases：

1. **key pattern 闭合**：两个 namespace MUST 只接受完整 typed id 尾缀
   （`ak.views.private.ak:view:<uuidv7>`、`ak.notifications.inbox.ak:notification:<uuidv7>`）。
   裸 namespace（`ak.views.private`）、空尾缀（`ak.views.private.`）、非 typed id 尾缀与
   跨 kind 尾缀 MUST 拒绝；实现 MUST NOT 让它们落到未注册 key 的宽松兜底分支。
2. **storage=encrypted_account_data**：把 `ak.schema.view.v1` 明文（含 `title` / `query` /
   `layout`）写入 `ak.views.private.<view_id>` MUST 拒绝；同一 key 的加密 envelope MUST 接受，
   且 envelope AAD MUST 同时绑定 `actor_id` 与 `account_data_key`。
3. **private View 明文绑定自身 key**：解密后的 plaintext MUST validate 为 `ak.schema.view.v1`、
   `visibility="private"`、`id` 等于 key 尾缀。`visibility="shared"`、缺省 `visibility`、
   他 View 的 `id`、以及共享终态 `state="tombstoned"` MUST 拒绝。该层 MUST 在 holder 客户端
   执行——服务端没有明文，无法复核。
4. **共享 surface 不承载 private**：`ak.view.create` / `ak.view.update` 携带
   `visibility="private"` MUST 以 `schema_violation`、`reason_code="private_view_requires_account_data"`
   拒绝；查询共享 View 的 operation MUST 只返回 `visibility="shared"`；private 定义 MUST NOT
   出现在任何共享 Realm cell。
5. **收件箱 state 闭合**：value MUST 绑定 `notification_id`、`state ∈ {dismissed, archived}`、
   HLC 与 device tie-break 材料，且 `notification_id` MUST 等于 key 尾缀。`read` / `unread`
   MUST 拒绝写入该 key——它们仍由 read cursor 派生。
6. **收件箱合并**：同一 notification 的两份 value 先比 HLC，HLC 相等时比 `origin_device_id`
   字典序。两种到达顺序 MUST 选出同一 winner，且合并只发生在客户端 CAS 重试循环内的明文上。
7. **physical_delete**：两个 key 的 `deletion_mode` 均为 `physical_delete`，
   `ak.self.account_data.resource.delete` MUST 接受；删除后 `resource.get` 返回 `not_found`
   且带 revision high-water mark，离线设备的旧 `expected_revision` 重写 MUST 以 `cas_conflict`
   拒绝，不得复活。

Expected：

- case 1 的每个被拒 key 都不得产生任何存储副作用，也不得改变 revision。
- case 2 与 case 3 合起来构成完整闭合：服务端保证密文，客户端保证语义；只做其中一半的实现
  MUST 判为 conformance failure。
- key 内嵌完整 typed id 带来的存在性泄露是 registry 已接受的取舍（与 `ak.tags.realm.<realm_id>`
  同级）；实现 MUST NOT 再往 key 里追加 `realm_id`、`title` 或其派生物扩大泄露面。

## 6. Space Lifecycle Vectors

### 6.1 目标

本节定义 Space（看板 / 列 / 泳道 / calendar bucket / page group ...）`active` ↔ `archived` ↔ `tombstoned` 状态机的跨实现测试向量。canonical 写入路径见 [`../models/realm-and-space.md` §3.4](../models/realm-and-space.md)；canonical 状态机对齐见 [`../models/common-fields.md` §5](../models/common-fields.md)。

实现声称支持以下 profile 时 SHOULD 运行本节向量：

- `ak.profile.kanban_mvp.v1`
- `ak.profile.full_client.v1`
- `ak.profile.principal_server.v1`

### 6.2 Vector: Space Archive 然后 Restore（happy path）

输入（按 causal order 应用）：

```json
{
  "realm_id": "ak:realm:0196419b-0000-7000-8000-000000000000",
  "events": [
    {
      "kind": "ak.space.create",
      "unsigned": {
        "target_ref_hint": "ak:space:019640b6-8000-7000-8000-000000000000"
      },
      "payload": {
        "object": {
          "id": "ak:space:019640b6-8000-7000-8000-000000000000",
          "schema": "ak.schema.space.v1",
          "realm_id": "ak:realm:0196419b-0000-7000-8000-000000000000",
          "kind": "board",
          "title": "Release Board",
          "created_by": "did:webvh:z6mkfixture:alice.example.com",
          "created_at": "2026-05-15T10:00:00Z"
        }
      }
    },
    {
      "kind": "ak.space.archive",
      "unsigned": {
        "target_ref_hint": "ak:space:019640b6-8000-7000-8000-000000000000"
      },
      "created_at": "2026-05-15T10:05:00Z",
      "payload": {
        "space_id": "ak:space:019640b6-8000-7000-8000-000000000000",
        "reason": "release_cycle_complete"
      }
    },
    {
      "kind": "ak.space.restore",
      "unsigned": {
        "target_ref_hint": "ak:space:019640b6-8000-7000-8000-000000000000"
      },
      "created_at": "2026-05-15T10:10:00Z",
      "payload": {
        "space_id": "ak:space:019640b6-8000-7000-8000-000000000000",
        "reason": "release_reopened"
      }
    }
  ]
}
```

期望：

- 应用 `ak.space.archive` 后，Space 物化对象 MUST 有 `state == "archived"` 且 `state_changed_at == "2026-05-15T10:05:00Z"`。默认 collection projection（不显式包含 archived items）MUST NOT 返回该 Space；显式带 `include_states=["archived"]` 的查询 MUST 仍可返回它。
- 应用 `ak.space.restore` 后，Space 物化对象 MUST 有 `state == "active"` 且 `state_changed_at == "2026-05-15T10:10:00Z"`。默认 projection MUST 重新展示该 Space。
- Restore **不**级联——若该 Space 包含 child Space（如 List 在 Board 内）或内部 Strand 且它们各自处于 `archived`，restore parent MUST NOT 改变 children 的 state。
- archive 期间未被擦除的 `contains` Relation、Strand position cell 与 `parent_space_id` cell MUST 在 restore 后保持原值；用户看到的内容与 archive 之前一致。

### 6.3 Vector: Space Restore 在 `active` 状态被拒绝

输入：

```json
{
  "realm_id": "ak:realm:0196419b-0000-7000-8000-000000000000",
  "pre_state": {
    "space": {
      "id": "ak:space:019640b6-8000-7000-8000-000000000000",
      "state": "active"
    }
  },
  "event": {
    "kind": "ak.space.restore",
    "unsigned": {
      "target_ref_hint": "ak:space:019640b6-8000-7000-8000-000000000000"
    },
    "created_at": "2026-05-15T11:00:00Z",
    "payload": {
      "space_id": "ak:space:019640b6-8000-7000-8000-000000000000"
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
  "realm_id": "ak:realm:0196419b-0000-7000-8000-000000000000",
  "pre_state": {
    "space": {
      "id": "ak:space:019640b6-8000-7000-8000-000000000000",
      "state": "tombstoned",
      "state_changed_at": "2026-05-15T09:00:00Z"
    }
  },
  "event": {
    "kind": "ak.space.restore",
    "unsigned": {
      "target_ref_hint": "ak:space:019640b6-8000-7000-8000-000000000000"
    },
    "created_at": "2026-05-15T12:00:00Z",
    "payload": {
      "space_id": "ak:space:019640b6-8000-7000-8000-000000000000"
    }
  }
}
```

期望：

- Reducer MUST 返回 `failed_precondition`，`reason == "space_not_archived"`（与 §6.3 同 reason；tombstoned 在状态机中不属于 `archived`，复活路径不存在）。
- Space 物化对象 MUST 保持 `state == "tombstoned"` 与原 `state_changed_at`。
- 该向量是 `tombstoned` 不可逆终态约束（[`realm-and-space.md` §3.4](../models/realm-and-space.md)、[`space.schema.json#/properties/state`](../../artifacts/schemas/space.schema.json)）的 wire 级证据：实现 MUST NOT 提供任何"先 restore 再写入"的 tombstoned 复活路径。需要重新启用一个等价容器时，正确的做法是 `ak.space.create` 一个新 Space。

### 6.5 Vector: Archive 在非 `active` 状态被拒绝

输入：

```json
{
  "realm_id": "ak:realm:0196419b-0000-7000-8000-000000000000",
  "pre_state": {
    "space": {
      "id": "ak:space:019640b6-8000-7000-8000-000000000000",
      "state": "archived",
      "state_changed_at": "2026-05-15T10:05:00Z"
    }
  },
  "event": {
    "kind": "ak.space.archive",
    "unsigned": {
      "target_ref_hint": "ak:space:019640b6-8000-7000-8000-000000000000"
    },
    "created_at": "2026-05-15T11:30:00Z",
    "payload": {
      "space_id": "ak:space:019640b6-8000-7000-8000-000000000000"
    }
  }
}
```

期望：

- Reducer MUST 返回 `failed_precondition`，`reason == "space_not_active"`（[common-fields.md §5.1](../models/common-fields.md) state-transition 表）。
- Space 物化对象 MUST 保持 `state == "archived"` 与原 `state_changed_at`；same-state self-transition 不被当作 idempotent no-op。
- 客户端如果意图是"重新 archive"，正确路径是先 `ak.space.restore` 再 `ak.space.archive`。
- 该向量对 Strand / Morph 等价同形：`ak.strand.archive` 在 `state != "active"` 时 `strand_not_active`；`ak.morph.archive` 同理 `morph_not_active`。

### 6.6 Vector: Tombstone 在已 tombstoned 状态被拒绝

输入：

```json
{
  "realm_id": "ak:realm:0196419b-0000-7000-8000-000000000000",
  "pre_state": {
    "space": {
      "id": "ak:space:019640b6-8000-7000-8000-000000000000",
      "state": "tombstoned",
      "state_changed_at": "2026-05-15T09:00:00Z"
    }
  },
  "event": {
    "kind": "ak.space.tombstone",
    "unsigned": {
      "target_ref_hint": "ak:space:019640b6-8000-7000-8000-000000000000"
    },
    "created_at": "2026-05-15T12:00:00Z",
    "payload": {
      "space_id": "ak:space:019640b6-8000-7000-8000-000000000000"
    }
  }
}
```

期望：

- Reducer MUST 返回 `failed_precondition`，`reason == "space_already_terminal"`（[common-fields.md §5.1](../models/common-fields.md) 终态等价规则）。
- Space 物化对象 MUST 保持 `state == "tombstoned"` 与原 `state_changed_at`。
- 该向量对 Strand / Morph 等价同形：`ak.redaction` 指向已 `redacted` 的 Strand / Morph 时同样返回 `<kind>_already_terminal`。终态进入是单向、单次操作。

### 6.7 Vector: Update 在非 `active` 状态被拒绝

输入：

```json
{
  "realm_id": "ak:realm:0196419b-0000-7000-8000-000000000000",
  "pre_state": {
    "space": {
      "id": "ak:space:019640b6-8000-7000-8000-000000000000",
      "state": "archived",
      "state_changed_at": "2026-05-15T10:05:00Z",
      "title": "Release Board"
    }
  },
  "event": {
    "kind": "ak.space.update",
    "unsigned": {
      "target_ref_hint": "ak:space:019640b6-8000-7000-8000-000000000000"
    },
    "created_at": "2026-05-15T11:45:00Z",
    "payload": {
      "space_id": "ak:space:019640b6-8000-7000-8000-000000000000",
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
- 客户端正确路径：先 `ak.space.restore`，update 通过后再决定是否 `ak.space.archive`。
- 该向量对 Strand / Morph `*.update` 等价同形。

## 7. Member Delivery Binding Vectors

### 7.1 目标

验证 `ak.member.state{membership="join"}` 的 `delivery_binding` payload 是 Realm-scoped event 投递的唯一权威路由源：
- schema-level conditional required 字段强制执行；
- DID Document service entry **不构成** fallback；
- 路由失败时 sender fail-closed（quarantine + retry，不退回 DID Document）；
- rebind 通过 causal frontier handover；
- 撤销后投递立即停止。

下列向量假设 Realm `ak:realm:7d000000-0000-7000-8000-000000000000`、actor `did:webvh:01HV...:alice` 已存在；具体 id 仅作占位。本节是 normative vector description；机器可执行 fixture 位于 [`../../artifacts/fixtures/membership-delivery-binding-fixture.json`](../../artifacts/fixtures/membership-delivery-binding-fixture.json)，runner MUST 同时消费该 fixture 与本文 prose，不得再依赖未落地的目录约定。

### 7.2 Vector: `explicit` Binding 接受

`vector_id`: `ak.vector.membership.delivery_binding.explicit.v1`

Input — `ak.member.state{membership="join"}` Control Move payload：

```json
{
  "realm_id": "ak:realm:7d000000-0000-7000-8000-000000000000",
  "actor_id": "did:webvh:01HV...:alice",
  "membership": "join",
  "delivery_status": "routable",
  "delivery_binding": {
    "recipient_service_id": "did:webvh:z6mkfixture:principal.acme.example",
    "recipient_service_kind": "principal_server",
    "binding_scope": "realm",
    "binding_source": "explicit",
    "delivery_modes": ["events", "sync", "to_device", "push", "key_packages"],
    "resolved_at": "2026-05-19T10:00:00Z",
    "service_acceptance_ref": "ak:event:7d000001-0000-7000-8000-000000000000"
  },
  "gate_proofs": [ "..." ]
}
```

预设：Realm policy `ak.realm.delivery_binding_policy` 声明 `allowed_binding_sources` 包含 `explicit`、`allowed_recipient_services` 包含 `did:webvh:z6mkfixture:principal.acme.example`、`required_endorsers` 含 `did:webvh:z6mkfixture:acme.example`，`service_acceptance_ref` 引用的 Event 由 `did:webvh:z6mkfixture:principal.acme.example` 签发且 scope 覆盖该 Realm，并由 `required_endorsers` 中的 `did:webvh:z6mkfixture:acme.example` 背书。

期望：
- reducer 接受 join Control Move；写入成员 cell。
- 此后任何向 Alice 投递的 Realm S event/sync/to_device/push/key_packages MUST 走 `did:webvh:z6mkfixture:principal.acme.example`，**禁止**触发 DID Document service entry resolution。

### 7.3 Vector: `did_document_default` Fallback 物化

`vector_id`: `ak.vector.membership.delivery_binding.did_document_default.v1`

Input — Realm policy `ak.realm.delivery_binding_policy` 声明 `did_document_default_allowed=true`，其余字段未限制；Alice DID Document service `ArkretPrincipalServer` 指向 `did:webvh:z6mkfixture:personal.alice.example`，canonical hash `sha256:abc...`。

客户端构造 join Control Move 时 MUST 先解析 DID Document 并物化进 binding：

```json
{
  "realm_id": "ak:realm:...",
  "actor_id": "did:webvh:01HV...:alice",
  "membership": "join",
  "delivery_status": "routable",
  "delivery_binding": {
    "recipient_service_id": "did:webvh:z6mkfixture:personal.alice.example",
    "recipient_service_kind": "principal_server",
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
- 同形 Control Move 在 Realm policy `did_document_default_allowed=false` 时 reducer MUST 返回 `delivery_binding_policy_mismatch`。
- 一旦该 join 被接受，sender **不得**在后续投递时 re-resolve DID Document——即使 DID Document 已更新指向新服务，仍按 cell 内 `delivery_binding` 投递，直到一次合法 rebind。

### 7.4 Vector: `unroutable` 成员

`vector_id`: `ak.vector.membership.delivery_binding.unroutable.v1`

Input — Realm policy `ak.realm.delivery_binding_policy` 声明 `unroutable_membership_allowed=true`。Alice join Control Move 携带：

```json
{
  "realm_id": "ak:realm:...",
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
- 同形 Control Move 在 Realm policy `unroutable_membership_allowed=false` 时 reducer MUST 返回 `delivery_binding_policy_mismatch`。

### 7.5 Vector: Rebind Handover + 撤销后停止投递

`vector_id`: `ak.vector.membership.delivery_binding.handover.v1`

序列：

1. **Initial join**（`F0`）：Alice join with `recipient_service_id=did:webvh:z6mkfixture:personal.alice.example`，accepted。
2. **Events 流量**：Realm 内事件 `E1, E2` 进入因果图，sender 将它们投递到 `did:webvh:z6mkfixture:personal.alice.example`。
3. **Rebind**（`F1`）：Alice 提交同状态 `ak.member.state{membership="join"}` self-transition，新 binding 指向 `did:webvh:z6mkfixture:principal.acme.example`，签名按 `rebind_authorization` 规则。Control Move accepted。
4. **Post-rebind events**：sender 投递 `E3, E4` 时观察 `service_binding_ref.delivery_binding_frontier`：
   - sender frontier ≥ `F1` → 投递到 `did:webvh:z6mkfixture:principal.acme.example`；
   - sender frontier 仍 `< F1` 且投到旧 `did:webvh:z6mkfixture:personal.alice.example` → 旧服务在 `handover_grace_seconds` 内接受并返回 `delivery_binding_stale + new_recipient_service_id=did:webvh:z6mkfixture:principal.acme.example + handover_frontier=F1`；sender MUST 切换后重试，**不得**回退到 DID Document。
   - sender frontier ≥ `F1` 但仍投到旧 → 旧服务 reject `delivery_binding_handed_over`。
5. **Grace 结束**：旧服务停止接受新 Realm S event；本地 to-device 队列、push registration、MLS group share state 进入 destruction。
6. **撤销**：Alice 离职，Org-A 治理 key 提交 `ak.member.state{membership="leave"}` 或 `ak.capability.revoke`。`F2` 之后 sender MUST NOT 继续向 `did:webvh:z6mkfixture:principal.acme.example` 投递该 Realm 的内容；MUST NOT 转而退回 `did:webvh:z6mkfixture:personal.alice.example`（DID Document fallback）；该 actor 在 Realm S 中变成 **non-member**。

期望：
- 整个序列中 sender 解析投递目标 MUST 完全依赖 effective member cell 的 `delivery_binding`，DID Document service entry 永远不被 query。
- `delivery_binding_frontier` 字段在所有 service-to-service push 中均存在；sender 端落后 frontier 收到 stale signal 后 MUST 切换、不重投。
- 撤销后 sender 试图继续投递 MUST 收到已登记的 `not_member`（membership 已撤销）或 `capability_denied`（投递 capability 已撤销）；MUST NOT 构造任何 "fallback to DID Document" 路径。

### 7.5.1 Vector: Policy Mismatch 拒绝

`vector_id`: `ak.vector.membership.delivery_binding.policy_mismatch.v1`

Steps:

1. Realm policy 不允许 `binding_source=explicit`，但 join Control Move 携带 explicit `delivery_binding`。
2. Realm policy 声明 `allowed_recipient_services`，但 `delivery_binding.recipient_service_id` 不在集合内且没有满足 `required_endorsers` 的 proof。
3. Realm policy 声明非空 `required_endorsers`，但 `service_acceptance_ref` 未被其中任一治理 DID 背书，即使 `recipient_service_id` 命中 `allowed_recipient_services` 或 `["*"]` 哨兵也一样。
4. Realm policy 不允许 `unroutable_membership_allowed`，但 join Control Move 携带 `delivery_status="unroutable"`。

Expected:

- 每个 case MUST `failed_precondition`，`reason=delivery_binding_policy_mismatch`。
- reducer MUST NOT fallback 到 DID Document，也不得接受成员后再把 delivery 状态标为 best-effort。

### 7.6 覆盖矩阵

| 字段 / 行为 | §7.2 explicit | §7.3 did_document_default | §7.4 unroutable | §7.5 rebind+revoke |
| --- | --- | --- | --- | --- |
| Conditional required (`service_acceptance_ref`) | ✓ | — | — | ✓ |
| Conditional required (`did_document_digest`) | — | ✓ | — | — |
| Policy `did_document_default_allowed=false` 拒绝 | — | ✓ | — | — |
| Policy `unroutable_membership_allowed=false` 拒绝 | — | — | ✓ | — |
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
  "realm_id": "ak:realm:0196419b-0000-7000-8000-000000000000",
  "requester": "did:webvh:z6mkfixture:bob.example",
  "proof_challenge": "ak.challenge-001"
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
  "audience": "ak:realm:0196419b-0000-7000-8000-000000000000",
  "claims": [{
    "claim_kind": "organization_handle",
    "handle": "alice:acme.example",
    "handle_aliases": ["acct:alice@acme.example"],
    "subject": "did:webvh:z2dmjA1ice:users.acme.example",
    "issuer": "did:webvh:z6mkfixture:acme.example",
    "binding_state": "verified",
    "audience": "ak:realm:0196419b-0000-7000-8000-000000000000",
    "member_delivery_binding": {
      "recipient_service_id": "did:webvh:z6mkfixture:principal.acme.example",
      "recipient_service_kind": "principal_server",
      "binding_source": "organization_policy",
      "delivery_modes": ["events", "sync", "to_device", "push", "key_packages"],
      "service_acceptance_ref": "ak:event:0196419b-0000-7000-8000-000000000001",
      "policy_event_ref": "ak:event:0196419b-0000-7000-8000-000000000002"
    },
    "created_at": "2026-05-19T00:00:00Z",
    "expires_at": "2026-08-19T00:00:00Z",
    "proofs": [{
      "kind": "detached_jws",
      "alg": "EdDSA",
      "verification_method": "did:webvh:z6mkfixture:principal.acme.example#key-1",
      "payload_digest": "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
      "created_at": "2026-05-19T00:00:00Z",
      "audience": "ak:realm:0196419b-0000-7000-8000-000000000000",
      "jws": "aaa.bbb.ccc"
    }]
  }],
  "member_delivery_binding": {
    "recipient_service_id": "did:webvh:z6mkfixture:principal.acme.example",
    "recipient_service_kind": "principal_server",
    "binding_source": "organization_policy",
    "delivery_modes": ["events", "sync", "to_device", "push", "key_packages"],
    "service_acceptance_ref": "ak:event:0196419b-0000-7000-8000-000000000001",
    "policy_event_ref": "ak:event:0196419b-0000-7000-8000-000000000002"
  },
  "expires_at": "2026-08-19T00:00:00Z"
}
```

Expected join Control Move:

- `payload.actor_id = did:webvh:z2dmjA1ice:users.acme.example`。
- `payload.delivery_binding.recipient_service_id = did:webvh:z6mkfixture:principal.acme.example`。
- `payload.delivery_binding.binding_source = organization_policy`。
- `payload.delivery_binding.service_acceptance_ref` 与 `policy_event_ref` 来自 verified claim / policy。
- Control Move payload MUST NOT 把 `@alice:acme.example` 当作 actor、cell subject 或 grant subject；受限 handle 明文 SHOULD NOT 进入公开 Realm history。

Negative cases：

- Directory 返回 `verified=false` 或 challenge / audience 不匹配 → builder MUST NOT 构造 handle-based join。
- 返回 `subject != did` → client MUST reject `handle_subject_mismatch`。
- 返回 `member_delivery_binding.recipient_service_id` 但 Realm `allowed_recipient_services` 不包含该 DID，且没有 required endorser 背书 → reducer MUST reject `delivery_binding_policy_mismatch`。
- 返回无 `member_delivery_binding.recipient_service_id` → 只能作为 DID lookup；除非 Realm policy 允许 `did_document_default` 并物化 fallback，否则 reducer MUST reject handle-based join。

## 9. Security Closure Vectors

本节收拢跨章节引用的安全闭环向量。每个 `vector_id` 均为规范性引用目标；结构化覆盖位于 [`../../artifacts/fixtures/security-closure-fixture.json`](../../artifacts/fixtures/security-closure-fixture.json)，`tools/lint_artifacts.py` 会校验该 fixture 覆盖本节要求的 security closure vector set，并校验每个 step 暴露可由实现测试消费的 `runner.given_state` / `operation` / `transcript` / `expected_state_transition` / `expected_external_response` / `expected_audit_reason` 字段。实现不得把这些 ID 当成仅供说明的标签。

### 9.1 Vector: Federation Replay After Key Revoke

`vector_id`: `ak.vector.federation.idempotency_after_key_revoke.v1`

Steps：

1. Origin service `did:webvh:z6mkfixture:alpha.example` 使用 active service key 向 destination 提交 `POST /_arkret/peer/events`（`ak.peer.events.command.submit`），header 绑定 `Source-Service-ID`、`Destination-Service-ID`、`Source-Trust-Domain`、`Destination-Trust-Domain`、`Request-Canonical-Digest`、`Idempotency-Key`，批次 accepted。
2. Realm policy 或 DID Document 随后撤销该 origin service key；destination 的 accepted authorization frontier 前进。
3. 攻击者重放完全相同的 HTTP body、signature 与 `Idempotency-Key`。

Expected：

- 若重放只命中历史幂等缓存，destination MUST 返回 `historical_only`，不得重新接受为当前授权写入。
- 若 origin service binding 已被 Realm policy 移除，destination MUST 返回 `capability_denied`。
- 若 `origin_key_state_digest` 或 authorization frontier 与缓存 entry 不一致，receiver MUST 重新执行完整授权判定，不得只凭 `Idempotency-Key` 放行。

### 9.2 Vector: WebRTC Media Plaintext Downgrade

`vector_id`: `ak.vector.webrtc.media_plaintext_downgrade.v1`

Steps：

1. Realm policy 未授权 `media_service_decrypts`，但客户端收到 SFU 要求其发送 plaintext-visible media key 的 offer。
2. Realm policy 授权媒体服务解密，但 SFU service DID 不在 `plaintext_visible_services`。
3. UI 未显示 required plaintext warning，却尝试加入解密型会议。

Expected：

- 三种情况均 MUST 拒绝 join / publish media key。
- 前两种情况（policy_root 未覆盖 `media_service_decrypts`、SFU 未列入 `plaintext_visible_services`）的稳定失败原因均为已注册的 `media_plaintext_service_not_authorised`（见 `../../artifacts/registry/error-code-registry.json`，其描述同时覆盖这两个子情形）；UI 未显示 required plaintext warning 的情况 MUST 以等价稳定 reason_code 拒绝 join。

### 9.3 Vector: Identity Link Eager Invalidation

`vector_id`: `ak.vector.identity_link.eager_invalidation.v1`

Steps：

1. Principal 在 Realm R 中存在 active identity link。
2. R 接受 ban / leave / remove 中任一 membership transition，或 capability revoke 使该 link 不再满足 visibility gate。
3. Directory、sync cache、invite cache 和 local profile projection 仍持有旧 link。

Expected：

- 实现 MUST eager invalidation 所有关联 cache entry；后续 lookup 不得返回旧 link。
- 已建立的 session / device claim MUST 在下一次 authorization check 时失败或降级到最小披露状态。

### 9.4 Vector: Identity Link Policy Tightening Invalidation

`vector_id`: `ak.vector.identity_link.policy_tightening_invalidation.v1`

Steps：

1. Principal 在 disclosure policy、history visibility、minimal metadata mode、linked Realm visibility 或 Circle effective-scope visibility 放宽时建立 identity link。
2. 任一 policy 被收紧，使旧 link 的披露范围不再被允许。
3. 调用者继续使用旧 directory / sync cache 查询同一 principal。

Expected：

- 所有受影响 cache MUST 按 policy frontier 失效。
- 未重新通过当前 policy gate 的旧 link MUST NOT 返回；UI / API 只能显示当前允许的最小身份信息。

### 9.5 Vector: Late Key Recovery Removed Actor

`vector_id`: `ak.vector.late_key_recovery.removed_actor.v1`

Steps：

1. Receiver 请求恢复 T0 历史密钥，但其在 T0 的 membership / history visibility 不允许查看该历史。
2. 或者 receiver 曾在 T0 可见，但 key source 在 ban / remove 之后未重新执行 T0 membership + current share policy 校验就发送 late material。

Expected：

- T0 不可见时 MUST NOT 解密，reason_code 为 `late_recovery_rejected_membership` 或等价稳定码。
- key source 未重新校验时 MUST 拒绝 share，reason_code 为 `late_recovery_share_not_authorized`。
- 客户端 UI 不得显示未授权明文或把其纳入 verified timeline。

### 9.6 Vector: Invite OOB Code Entropy

`vector_id`: `ak.vector.invite.oob_code_entropy.v1`

Steps：

1. 构造低于生产最低熵的 offline OOB code claim。
2. 构造 lookup 形态 OOB code，其有效窗口或 claim 次数超过 policy 上限。

Expected：

- reducer / verification service MUST 拒绝短熵 code claim。
- 超限 lookup 形态 MUST invalidate，不得进入 pending invite 或 accepted membership。

### 9.7 Vector: Invite Failure Indistinguishable

`vector_id`: `ak.vector.invite.failure_indistinguishable.v1`

Steps：

1. 认证 principal 调用 `ak.self.invite_locator.command.issue`，确认响应 token 至少 192 bit 熵、响应含 `Cache-Control: private, no-store`、服务端仅持久化 digest；分别发行 reusable 与 `one_time_use=true` locator。
2. 分别对 reusable 与 one-time locator 省略可选项调用 rotate，确认响应同样禁止缓存、旧 token 在 rotate 成功后立即失效、新 token 可 resolve，且 granted lifetime、`one_time_use`、`display_hint` 均继承旧 record；resolve outcome 的 `locator_ref_digest` 必须等于新 record 的 `token_digest`。对 revoke 重试两次，确认同 actor 的第二次调用返回相同 `revoked_at`。
3. 注入 rotate 已提交但响应丢失的 transport fault；客户端必须先 revoke 旧 `locator_id`，再 fresh issue，且不得在确认旧 token 失效前直接 issue。
4. 并发两次 resolve one-time locator，确认最多一次成功；随后把该 token 与不存在、过期、已撤销、策略拒绝 token 一起提交 `POST /_arkret/open/invite-locators/resolve`。
5. 用另一 principal 的 session 对 locator_id 调用 rotate / revoke，确认与未知 locator_id 同样返回 `not_found` 且不改变原 record。
6. 对 third-party claim endpoint 分别触发 token 不存在、过期、已撤销、已消费、audience 不匹配、邀请者已离开 Realm、policy gate 不满足七类失败。
7. 分别在 claim、locator resolve 与 self locator-management endpoint surface 内记录 HTTP status、response body、headers 和响应时间；不同 endpoint 之间不要求响应 body 相同，但同一 endpoint 的不可枚举失败原因 MUST 不可区分。

Expected：

- 每个 endpoint surface 内的对外响应 MUST byte-identical 或等价不可区分；仅服务端 audit log 可记录具体 reason_code。
- timing 差异 SHOULD ≤ 50ms；高安全 profile MUST 对该窗口做 jitter / padding。
- raw locator token MUST NOT 出现在 durable record、audit log 或 Realm Event；record 必须包含唯一 `token_digest`、TTL、撤销/消费状态与 subject/service binding。
- rotate 的旧-token 撤销与新-record insert MUST 原子；one-time resolve 并发最多一个成功。

### 9.7.1 Vector: Invite Claim Reducer State Machine

`vector_id`: `ak.vector.invite.claim_reducer_state_machine.v1`

本向量固化 [`third-party-invites.md`](../sync/third-party-invites.md) §4.3 的 Realm reducer 权威要求。机器可执行样本位于 [`../../artifacts/fixtures/security-closure-fixture.json`](../../artifacts/fixtures/security-closure-fixture.json)；runner MUST 同时消费 prose 与 fixture，不得只依赖验证服务或 Sync Service 入站预检。

Steps：

1. 正路径：Realm frontier 中存在 `state="pending"` 的 `ak.invite.third_party`，`token_commitment`、`claim_nonce`、`verification_service_id` allowlist、`binding_proof`、`subject_proof` 和 `expires_at` 均有效。
2. Binding proof signature replay：`binding_proof.signature` 来自另一组 `invite_id` / `token_commitment` / `claim_nonce` / `invite_digest` transcript。
3. Subject proof old DID key：`subject_proof.verification_method` 曾属于 `subject_id`，但不在当前 DID document 的有效 verification method 集。
4. Subject proof transcript replay：`subject_proof.transcript_digest` / signature 绑定的是另一份 `binding_proof_digest` 或 verification service。
5. Token commitment mismatch：`ak.invite.claim.payload.token_commitment` 不等于 pending invite 的 commitment。
6. Allowlist 复校验失败：验证服务曾签发 binding proof，但当前 effective Realm policy 已移除该 `verification_service_id`。
7. Claim nonce replay：同一 `(invite_id, claim_nonce)` 或同一 `token_commitment` 已被 reducer 观察为 accepted claim projection。
8. Expired cleanup：`invite.expires_at <= now` 时提交 claim。

Expected：

- Case 1：Reducer MUST 原子产生 `pending -> claimed`，记录 `claimed_by=subject_id`、claim nonce digest 和 verification service DID，并只物化 subject-bound `ak.invite.create` 或等价 membership proposal；最终 `ak.member.state{membership="join"}` 仍需 `ak.invite.accept` 或显式 profile 路径。
- Cases 2-8：Reducer MUST reject，不得产生 membership proposal 或 join；proof/signature 类失败使用内部 `proof_invalid` 或更细 audit reason，case 7 使用 `duplicate_conflict`，case 8 使用内部 `expired_invite_token` 并触发 §6.1 token material cleanup。
- 所有失败通过外部 claim surface 返回不可枚举 `not_found` 或同形态响应；具体 reason 只进入 audit / per-event rejected diagnostics。

### 9.8 Vector: Consent Scope Cascade

`vector_id`: `ak.vector.consent.scope_cascade.v1`

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

`vector_id`: `ak.vector.consent.cache_invalidation.v1`

Steps：

1. Consent active 时 private contact discovery PSI result、invite capability gate 和 PSI index 均缓存了 peer 可达状态。
2. Subject revoke consent。
3. 调用 directory lookup、提交下一次 invite Control Move，并等待 PSI 下一轮轮转。

Expected：

- Private contact discovery / invite handoff MUST 立即不返回该 peer。
- 下一次 invite Control Move MUST precondition 失败并重判 capability gate。
- `any` revoke MUST 失效所有 scope cache；PSI 索引在下一次轮转时排除该 peer。

### 9.10 Vector: Sync Soft-Fail Reconcile

`vector_id`: `ak.vector.sync.soft_fail_reconcile.v1`

Steps：

1. Receiver 收到 soft-failed event，原因是缺少 dependency / auth state / key material。
2. Backfill 成功补齐全部依赖。
3. 另一路中，backfill 返回冲突或永久缺失。

Expected：

- 补齐后 reducer MUST deterministically 从 soft-fail 转为 accepted，并更新 covered event set。
- 永久缺失或冲突时 MUST 转为 rejected / failed_precondition，不得无限留在 soft-fail。

### 9.11 Vector: Lattice LWW Open Set

`vector_id`: `ak.vector.lattice.lww_open_set.v1`

Steps：

1. 构造同一 seal view 中多个 sibling write，它们对同一 open-set cell 产生竞争状态。
2. 所有 sibling 带相同 logical time，但 actor / event id / canonical digest tiebreaker 不同。
3. 两个 conformant reducer 以不同输入顺序重放。

Expected：

- sibling 集合与 tiebreaker MUST 产出同一 winner。
- 任一实现出现不同 winner、不同 bottom 或不同 covered event set，均视为 reducer bug。

### 9.12 Vector: E2EE Relaxed Window Exceeds Ceiling

`vector_id`: `ak.vector.e2ee_relaxed.window_exceeds_ceiling.v1`

Steps：

1. Realm policy event 尝试把 `relaxed_window_max_ms` 写为大于 300000。
2. Receiver 收到 old-epoch decrypt admission，其 gap 超过当前 policy window。
3. Deployment profile 尝试通过 unrelated profile 重新定义 hard ceiling。

Expected：

- Reducer MUST 以 `relaxed_window_exceeds_ceiling` 拒绝超限 policy write。
- Receiver MUST 独立拒绝超过当前 policy window 的 decrypt admission。
- Hard ceiling 不可由 deployment profile 重定义；实现不得 silently clamp 后继续接受。

### 9.13 Vector: Consumed Third-Party Invite Token Resubject Rejected

`vector_id`: `ak.vector.invite.consumed_token_resubject_rejected.v1`

Steps：

1. 第三方邀请 token 已被验证服务原子消费并签发了绑定 `subject_id=did:webvh:z6mkfixture:alice.example` 的 `binding_proof`。
2. 攻击者用同一已消费 token 向验证服务发起第二次签发请求，指向不同 `subject_id=did:webvh:z6mkfixture:mallory.example`。
3. 攻击者另把承载该已消费 token 重绑到不同 subject 的 `ak.invite.claim` Event 提交给 reducer。

Expected：

- 验证服务 MUST 拒绝第二次签发，不签发指向不同 subject 的第二份 `binding_proof`；仅当请求绑定同一 `(invite_id, claim_nonce, subject_id, binding_proof_digest)` 时，才允许在可恢复窗口内幂等重投递同一份既有 `binding_proof`。
- Reducer MUST 以 `duplicate_conflict` 拒绝该 resubject `ak.invite.claim` Event。
- 对外失败响应 MUST 与 `not_found` 不可区分（与本节其它 invite 向量一致），具体 reason code 只写入服务端 audit log。
- 规范定义见 [`../sync/third-party-invites.md` §6.1](../sync/third-party-invites.md)。

### 9.14 Vector: Minimal-Metadata Author Credential Binding

`vector_id`: `ak.vector.identity_link.minimal_metadata_author_credential.v1`

机器 fixture：`privacy-security-fixture.json` 中同名 case；执行入口以 fixture `runner` 元数据为准。

Preconditions：

- Realm 声明 `ak.profile.mls.minimal_metadata_realm.v1`；内容 Event `actor_id` 为 Realm-scoped pairwise DID。
- Encrypted envelope 固定 `(group_id, epoch, key_ref.group_state_ref)`，该 accepted group state 有一条 active RFC 9420 basic credential identity 等于 `utf8(actor_id)` 的 LeafNode。

Cases：

1. 唯一 active leaf，Event proof key 与 LeafNode `signature_key` 相同且签名有效：接受为 verified pairwise author。
2. 同一 pairwise identity 对应多条 active leaf、leaf 已在该 epoch 被移除、group-state ref 不是该 epoch winning state、proof key 与 leaf key 不同：均以 `minimal_metadata_author_credential_invalid` 拒绝。
3. 实现尝试用 principal-scoped `keys/query` 兜底：拒绝该实现路径，目录调用计数必须为 0。

Expected：

- 作者性验证只建立 pairwise sender leaf 身份，不揭示 principal；principal 提升仍依赖独立、端到端加密的 `ak.identity_link`。
- Receiver 不得回退 current epoch、未验证 ratchet-tree cache、真实 principal DID 或 principal device directory。
- 所有失败 case 都在内容进入 verified timeline 前 fail closed。

### 9.15 Vector: AAD Visibility Policy Ceiling

`vector_id`: `ak.vector.aad_visibility.policy_ceiling.v1`

机器 fixture：`security-closure-fixture.json` 中同名 vector；执行入口以 fixture `runner` 元数据为准。

Preconditions：

- Realm policy 上限来自 `ak.realm.policy_bundle` payload 的 `aad_visibility.event_id`；披露序为 `hidden < routing_digest < opaque_id`（见 [`../crypto-media/encryption-and-audit.md` §2.8](../crypto-media/encryption-and-audit.md)）。
- 信封的 `aad_visibility_event_id` 与 `aad` 字段集合本身已按 §2.3.1 / §2.3.2 自洽。

Cases：

1. 上限 `routing_digest`，信封 `routing_digest`：接受。
2. 上限 `routing_digest`，信封 `hidden`：接受——更严格的信封只披露更少，MUST NOT 因为「与 policy 不等」而拒绝。
3. 上限 `routing_digest`，信封 `opaque_id`：以 `failed_precondition`（`reason_code="aad_visibility_policy_violation"`）拒绝。
4. Realm 未声明 `aad_visibility` 组件，信封 `routing_digest`：拒绝，理由同上——缺省上限是 `hidden`，未声明不等于不限制。
5. 实现把越界信封静默降级为 `hidden` 后继续处理：视为实现 bug，不得出现。

Expected：

- 判定只用当前 accepted policy bundle cell 值与信封 discriminator 两个输入，不看 `aad` 内容本身。
- 上限收紧或放宽都要等新的 `ak.mls.commit` 覆盖新 `policy_root` 之后才对后续 epoch 生效；在覆盖前按上一 accepted `policy_root` 判定。
- 拒绝发生在信封进入路由 / 去重 / verified timeline 之前。

## 10. Service Closure Vectors

### 10.1 Vector: Signal Class And TTL

`vector_id`: `ak.vector.signal.class_ttl.v1`

Steps：

1. Actor 提交 `signal_class=moderation`，但 current Seal basis 不允许 moderation signal。
2. Actor 持有 signal 资格后，提交超出 `signal_class=session` 30 秒上限的 envelope。
3. Signal rail 暂时不可用。

Expected：

- 第 1 步 MUST 返回 `signal_class_not_permitted`。
- 第 2 步 MUST 返回 `signal_ttl_out_of_range`。
- 第 3 步 MUST 返回 `signal_rail_unavailable`，且不写 durable Event、不推进 actor_seq / Realm frontier。

### 10.2 Vector: Projection Pagination Shape

`vector_id`: `ak.vector.projection.pagination_shape.v1`

Steps：

1. 调用 `ak.self.space.query.list` / `strand` / `morph`，请求 `limit=1`。
2. 使用返回的 `next_cursor` 继续读取。
3. 下游 service-call 返回缺失 `has_more` 或 cursor 形态不合法的响应。

Expected：

- 每个响应 MUST 带 `has_more`；有后续页时 MUST 带合法 `ak:cursor:*`。
- Cursor MUST 绑定调用者、selector 和 projection purpose，不得跨 service / Realm 复用。
- 缺失分页闭包字段时上游 MUST 归类为 `invalid_response`。

### 10.3 Vector: KeyPackage Exhaustion And Claim Limits

`vector_id`: `ak.vector.keypackage.exhaustion_claim_limits.v1`

Steps：

1. Device 可用 KeyPackage 数量低于 `keypackage_min_available`。
2. 同一 `(requester_service_id, target_principal_id)` 在 60s 内发起超过 5 次 claim。
3. 已 claimed KeyPackage 到达 `expires_at` 后再尝试 consume。

Expected：

- Server SHOULD 在可见响应中返回 `available_count`，client MUST 在下一次 maintenance / sync 补充上传。
- 超限 claim 对外仍保持反枚举失败，不泄露目标是否存在；内部审计 reason 为 `keypackage_claim_rate_limited`。
- 过期 claimed package MUST 转为 revoked / unusable，不得回到 `published`，迟到 consume MUST 被拒绝。

### 10.3.1 Vector: Peer KeyPackage Claim Atomic Idempotency

`vector_id`: `ak.vector.keypackage.peer_claim_atomic_idempotency.v1`

Steps：

1. source PS 以 `(Source-Service-ID=S, claim_request_id=R, request_digest=H)` 发起 peer claim；目标 authority 已完成 CAS 与 ledger commit，但成功响应丢失。
2. source 按协议先调用 claim query `(R,H)`；另模拟网络层重复投递完全相同的原 command。
3. source 复用 `R` 但改用另一 canonical digest `H2`。

Expected：

- KeyPackage 的 `published → claimed` CAS、ledger 与序列化 outcome MUST 只有一个线性化点，CAS 次数恰为 1。
- query MUST 返回 `state=claimed` 与同一签名 outcome；同 `(S,R,H)` 的重复 transport delivery 仍必须返回 byte-identical 原 outcome，但 caller 不得以此替代不确定结果查询。
- `(S,R,H2)` MUST `duplicate_conflict`，不得领取第二个 KeyPackage 或覆盖 ledger。

### 10.3.2 Vector: Peer Claim Double Authorization And Privacy

`vector_id`: `ak.vector.keypackage.peer_claim_double_authorization_privacy.v1`

对有效 Direct Conversation claim 分别施加以下单点变异：移除 / 过期 participant authorization、替换 participant signature 所绑定 destination、让 source 不是 requester home authority、破坏外层 service signature、移除 accepted contact / target consent、扩大 required capability，或令 `last_resort_allowed=true`。

Expected：

- 每个变异都 MUST 在 CAS 前失败，目标 KeyPackage 状态不变；participant 与 service 两层授权不可互相替代。
- 已通过外层 service authentication 的所有 participant / target / policy 业务失败对 peer caller 均为同一 `claim_failed` 外观；响应不得带 `available_count`、逐设备 `failures[]` 或 last-resort record。外层 service signature 变异必须在读取 target 前返回 target-independent `unauthenticated` / `invalid_signature`。
- Resolver draft 必须显式携带 `{request,transport_binding}`；participant signature 必须绑定 source/destination service 与双方 trust domain，客户端不得从本地配置猜测这些值。
- Direct Conversation request 必须同时绑定 pair key、Realm、main Strand 与 MLS group，且不得启用 last-resort。

### 10.3.3 Vector: Direct Conversation Loser Claim Revocation

`vector_id`: `ak.vector.keypackage.peer_claim_loser_revocation.v1`

两个 PS 为同一 pair 并发创建候选 A/B，各领取不同 single-use KeyPackage；binding event-digest 全序选择 B 为 canonical winner。

Expected：

- 只有 B 的 Welcome 可激活，且只有 B 的 claim 可 consume。
- A 的 Welcome MUST quarantine / ignore，不得建立可发送 MLS state。
- A 的 claim 在 expiry 前保持 `claimed`（或经授权提前 `revoked`），到期 MUST 为 `revoked`；任何时刻都不得释放回 `published`。

### 10.3.4 Vector: Self Claim Authorization And Idempotency

`vector_id`: `ak.vector.keypackage.self_claim_authorization_idempotency.v1`

Steps：

1. requester 以恰好一个 fresh `holder_acceptance` proof 提交 self claim；proof payload digest、audience、requester、target、Realm 与 claim nonce 均正确，authority 在提交 KeyPackage CAS 后丢失响应。
2. requester 以同一 `(requester, claim_nonce)` 与相同 proof-free payload digest 重试；再以同一 identity 修改 target / Realm / capability 得到另一 digest。
3. 分别施加零 proof、两个 proof、开放对象、wrong audience/purpose、stale/future proof、短 nonce、跨身份模型 signer、已 revoke device/Agent key、仅 bearer token、以及 proof 有效但 target consent/policy 不满足的单点变异。

Expected：

- 正例的 proof 必须按 `ak.keypackage-claim-request-proof-v1` 重建并验证；KeyPackage `published -> claimed` CAS、`(requester, claim_nonce, payload_digest)` ledger 与序列化 outcome 只有一个线性化点，CAS 次数恰为 1。
- 相同 identity/digest 的重试返回 byte-identical 原 outcome（含原 `available_count`），不得再次选择 KeyPackage；冲突 digest 在 inventory lookup 前以统一 `claim_failed` fail closed，内部 reason 为 `duplicate_conflict`。
- 所有 proof/schema/freshness/authority 变异都在读取 target inventory 或改变状态前失败；proof 不替代 sender-constrained transport authentication、当前 revoke/lifecycle 检查、target consent/policy 或后续 MLS claim envelope。
- 首次到达的过期请求绝不创建 claim；已有 terminal ledger 只能向当前仍被授权的同一 requester/session binding 返回原 outcome，nonce 重放在任何时间都不能创建第二次 claim。

### 10.4 Vector: Soft Logout DID Proof Required

`vector_id`: `ak.vector.auth.soft_logout_did_proof.v1`

Steps：

1. Session 进入 `soft_logged_out`。
2. Client 仅携带仍有效的 refresh token 请求恢复。
3. Client 重新提交 refresh/OIDC/re-auth，并携带授权 DID/device key 对 challenge 的签名。

Expected：

- 第 2 步 MUST 返回 `did_proof_required`，不得签发 active session grant。
- 第 3 步的 proof MUST 覆盖 principal、device、audience、challenge、request canonical hash 和 expiry；验证成功后才可恢复为 `active`。

### 10.4.1 Vector: DID Proof Replay Window

`vector_id`: `ak.vector.identity.did_proof_replay_window.v1`

Steps：

1. Auth Server 发出 DID proof challenge，绑定 `purpose="account_binding"`、`audience=did:webvh:z6mkfixture:auth.example`、`origin=https://auth.example`、随机 nonce、`issued_at=T0`、`expires_at=T0+300s`。
2. Client 提交签名正确的 proof，服务器接受并 burn challenge。
3. 攻击者第二次提交同一 proof。
4. 攻击者把相同签名 transcript 用到另一 audience/origin，或提交 `expires_at - issued_at = 3600s` 的 proof。
5. 攻击者提交 `issued_at` 超出接收端 skew 窗口的 proof。

Expected：

- 第 2 步 MUST 成功并把 challenge 进入 replay table。
- 第 3 步 MUST fail closed，即使签名仍正确。
- 第 4 步 MUST 因 audience/origin mismatch 或 freshness window 超限拒绝；服务端不得裁剪有效期后继续接受同一 proof。
- 第 5 步 MUST 拒绝；默认 skew 上限 SHOULD ≤ 300s。

### 10.4.2 Vector：国际化标识符 profile 与 authority-local 冲突索引

`vector_id`: `ak.vector.identity.internationalized_identifier_profiles.v1`、`ak.vector.identity.authority_local_skeleton_collision.v1`

Runner 必须分别测试“用户输入 preparation”和“canonical receiver validation”：前者可把 width/case 与 domain U-label 转为 canonical 值，后者必须拒绝任何仍需改写的 wire 值。localpart / Agent slug 使用登记版本的 RFC 8265 derived profile；domain 使用 UTS #46 Nontransitional + STD3/Bidi/Joiner/hyphen/DNS-length/round-trip 完整校验。`title` 等单行显示文本必须允许多语言、emoji 与合理混合脚本，同时拒绝 non-NFC、CR/LF、C0/C1、BOM、bidi format control 和纯空白。

UTS #39 skeleton 只在同一 authority、同一 namespace 的注册事务中作为派生冲突索引。同一 authority 的 handle skeleton 冲突返回 `failed_precondition` + `handle_homograph_forbidden`；不同 authority 或 handle/realm-alias 跨 namespace 不得冲突。Runner 必须断言 skeleton 不参与 canonical equality、签名或 wire 编码；Unicode/UTS #39 数据升级只重建派生索引，不得改写既有 canonical 标识符。DID 和 email local-part 的比较仍由各自 method/provider profile 决定，不得被 Arkret generic normalizer 合并。

### 10.5 Vector: Session Grant Audience Binding

`vector_id`: `ak.vector.auth.session_grant_audience_binding.v1`

Steps：

1. Auth Server 收到 `ak.gate.account.command.issue_session_grant`，proof 中 `audience` 与目标 resource server 不匹配。
2. 请求缺少 `request_canonical_digest` 或 hash 不覆盖 `principal_id`、`device_id?`、`requested_scope` 与 `audience`。
3. 请求的 `expires_at` 超过 Auth Server 声明的 session grant TTL 上限。
4. Auth Server 在 `development_mode=true` 时尝试把 `ak.profile.auth_server.v1` 放入 `verified_profiles[]`。

Expected：

- 第 1 步 MUST 拒绝，reason_code 为 `audience_mismatch` 或等价稳定码。
- 第 2 步 MUST 拒绝，reason_code 为 `invalid_proof_binding` 或等价稳定码。
- 第 3 步 MUST 拒绝或收紧到服务器硬上限，并在响应中暴露实际 `expires_at`；不得签发跨多日 session grant。
- 第 4 步 MUST 被 conformance / describe 校验拒绝；development mode 下 `verified_profiles[]` 必须为空。

### 10.6 Vector: Witness Disagreement Quarantine

`vector_id`: `ak.vector.range_completeness.witness_disagreement.v1`

Steps：

1. 两个 witness 对同一 `(realm_id, actor_id, actor_seq)` 给出不同 `event_id` / `event_digest`。
2. 两个 range-completeness attestation 声称同一 `(from_frontier, to_frontier]` scope，但 `root` 不同且无法由不同上界解释。
3. High-assurance peer 只提供 `single_source` attestation 试图解除 backfill completeness gate。

Expected：

- 第 1 / 2 步 MUST 标记 `witness_disagreement` 并 quarantine 对应 range / peer。
- 不得用本地接收顺序、HLC 或最后写入者选择 winner。
- 第 3 步 MUST 保持 pending / stale，不得推进 high-assurance completeness frontier。

### 10.7 Vector: Capability Revoke Downstream Recheck

`vector_id`: `ak.vector.capability.revoke_downstream_recheck.v1`

Steps：

1. Grant G 授权 actor 写入，Event E 的 `refs[role="authorized_by"]` 指向 G。
2. G 派生 child grant C，C 又授权 pending Event P。
3. `ak.capability.revoke{grant_id=G}` accepted。

Expected：

- P MUST fail closed 或 quarantine，reason `grant_revoked_upstream` / `authorized_grant_revoked`。
- Allow cache / policy decision cache 中依赖 G 或 C 的 entry MUST 在同一 reducer transaction 内失效。
- 历史 E 保留审计事实，但后续 snapshot/export 不得把 G 当作当前有效授权。

### 10.8 Vector: Cursor Revoke

`vector_id`: `ak.vector.cursor.revoke_high_assurance.v1`

Steps：

1. 服务签发 stream cursor 并随后接受 `/_arkret/self/account/cursor/revoke`。
2. 攻击者重放已撤销 cursor 到 `/_arkret/self/account/subscribe?after=`。
3. 攻击者提交篡改过但未撤销的 cursor。

Expected：

- 第 2 步 MUST 返回 `cursor_revoked`，且不推进 subscription position（to-device 队列删除只由 `ak.self.device_messages.command.ack` 驱动，与 cursor 无关）。
- 第 3 步 MUST 返回 `cursor_integrity_invalid`，不得泄露 revocation set 是否命中。

### 10.9 Vector: Device Recovery Lifecycle（A 模型限定）

`vector_id`: `ak.vector.device_recovery.lifecycle.v1`

本 vector 仅适用于 `identity_model="cross_signing"` 的 A 模型 SSK 恢复，不得泛化到 B 模型。B 模型没有 `ssk_generation`；其 generation mismatch、re-anchor 原子 unit 与围栏错误由 §22.3 `ak.vector.identity.device_reanchor.v1` 及对应 `device_reanchor_*` / `device_generation_fenced` errors 覆盖。

Steps：

1. 新设备用过期 `ssk_generation` 提交恢复 proof。
2. 新设备 proof 通过，但未完成 secret storage unlock / MLS Welcome replay。
3. KeyPackage claim 后失败并使可用数量低于 low-watermark。

Expected：

- 第 1 步 MUST 返回 `device_recovery_ssk_generation_mismatch`。
- 第 2 步设备只能处于 `recovery_pending`，不得显示 fully verified。
- 第 3 步 response SHOULD 返回 `available_count` / `low_watermark` / `suggested_publish_count`，claimed package 不得自动放回。

### 10.9.1 Vector: Device Revocation Seal Binding

`vector_id`: `ak.vector.device.revocation_seal_binding.v1`

Steps：

1. `ak.device.revoke` 作为 Control Move 提交，信封携带有效 `seal_basis`（单 leaf，取自 `ak.self.events.query.frontier` 的 Realm Seal view），随后被 principal control stream 的 accepted Seal S 覆盖（`control_sealed`）。
2. 攻击者重放该设备在 S 之后（以 S 或其后继 Seal view 判定）签发的 session grant、KeyPackage publish 或 to-device write。
3. 某 E2EE Realm 提交 MLS Remove，但 `governance_binding.membership_frontier` 未覆盖该 `ak.device.revoke` 事件，也未覆盖导入该撤销的 Realm governance Control Move。
4. 客户端在 `ak.self.events.query.frontier` 来源不可用（错误或缺 `seal_id` / `control_event_set_root`）时尝试提交 `ak.device.revoke`。

Expected：

- 第 2 步 MUST fail closed；实现不得用本地布尔缓存替代以 S 或其后继 Seal view 的判定。
- 第 3 步 Remove 不得使 `covered_seals_cell` 声称已覆盖该设备撤销；后续 E2EE DataEvent 仍必须被 `covered_seals_cell` gate 阻塞。
- 第 4 步客户端 MUST fail closed，不得伪造 `seal_basis`；缺失或不一致 basis 的 Control Move 按 `ak.vector.cba_lattice.control_move_requires_seal_basis_and_seal.v1` 拒收。

### 10.10 Vector: Push Wakeup Policy

`vector_id`: `ak.vector.push.wakeup_policy.v1`

Steps：

1. E2EE Realm 声明 `wakeup_default=no_notification`，server 无法评估 client-side mention rule。
2. 设备注册 `client_rule_digest` 与服务端保存 digest 不一致。
3. Realm 使用 `batch_wakeup`，一分钟内大量 client-side unresolved events 到达。

Expected：

- 第 1 步 MUST NOT 发送单事件 blind wakeup。
- 第 2 步 MUST 按更保守策略处理，不得猜测规则内容。
- 第 3 步 MUST 合并为 batch wakeup，仍携带 `evaluation_locus_unresolved=true`。

### 10.10.1 Vector: Hardened Realm Mention Routing Hint Disabled

`vector_id`: `ak.vector.push.mention_routing_hint_disabled_on_hardened_realm.v1`

Steps：

1. 分别让 Realm 声明 `ak.profile.mls.minimal_metadata_realm.v1`、`ak.profile.attested_audit.e2ee.v1`、`ak.profile.disclosed_audit.e2ee.v1`，同时在 policy 中显式写 `mention_routing_hint=recipient_registered_token`。
2. 尝试注册 opaque mention token、比较 message sidecar tag、持久化 token/tag，并触发 mention notification。
3. 对照 Realm 只声明普通 `ak.profile.e2ee_client.v1`，显式 opt-in 同一 hint。
4. Hardened Realm 另提交未知 hint 值。

Expected：

- 第 1-2 步 effective hint 必须是 `disabled`；注册、比较、持久化均为 false，mention 走 blind / batch wakeup。
- 第 3 步作为正对照，可按完整 token 安全规则启用 `recipient_registered_token`。
- 第 4 步按 `disabled` fail closed，不得把未知值解释成 opt-in。
- Runner 必须检查无 sidecar 状态写入，而不只检查最终 notification payload。

### 10.11 Vector: Audience Mention Controls

`vector_id`: `ak.vector.push.broadcast_mention_controls.v1`

Steps：

1. 普通成员只持有 `ak.message.create`，在 Message content AST 中加入 `audience_mention{audience="effective_scope_members"}`。
2. Realm policy 未声明 audience mention 策略；另一次提交中 sender 持有 `ak.message.mention.broadcast` 但 policy 仍缺失。
3. Realm policy 允许 `effective_scope_members`，设置 `max_recipients=25` 和 rate window；sender 持有带 `rate_limit` 的 `ak.message.mention.broadcast`。
4. 当前 effective scope 有 30 个可见成员；其中 1 个 receiver 显式 `level=muted`，1 个 receiver 被个人 blocklist / target policy 抑制。
5. sender 在 rate window 内再次发送 audience mention。

Expected：

- 第 1 步不得产生 audience mention notification；实现 MAY 拒绝整条 message 或接受消息但把 audience mention 降级为普通文本 / 不通知，取决于 Realm policy 声明。
- 第 2 步 MUST fail closed：缺少 effective audience mention policy 时，持有 `ak.message.mention.broadcast` 本身不足以 fanout。
- 第 3-4 步 recipient count 超过 `max_recipients` 时 MUST 在 fanout 前拒绝或进入 policy-declared review/quarantine；不得先发 push 再撤回。
- `level=muted` 与 target policy 抑制的 receiver MUST NOT 收到 notification stub 或 push wakeup，且发送者不能通过 delivery response 区分原因。
- 第 5 步 MUST 返回 `rate_limited` / `quota_exceeded` 或等价 policy denial；push payload 不得包含 audience 名称、recipient count、成员列表、Realm / Strand / Event 标识。

### 10.12 Vector: Strand Engaged Audience Mention

`vector_id`: `ak.vector.push.strand_engaged_mention.v1`

Steps：

1. Strand `F` 中 Alice 准备发送 Message，Message effective scope 包含 Bob、Carol、Dave、Erin、Frank，但不包含 Grace。
2. Bob 在 `F` 的 discussion track 中有一条 active Message；Carol 的 effective watch level 为 `all`；Dave 为 `mentions_only`；Erin 为 `muted`；Frank 只有 active assignment；Grace 无读取权。
3. Realm / Circle policy 允许 `audience="strand_engaged"`，声明有限 `max_recipients` 与 quota；Alice 同时持有 `ak.message.create` 与带 `max_operations` + `period` + `constraint_scope` 的 `ak.message.mention.broadcast`。
4. Alice 发送 `audience_mention{audience="strand_engaged", mention_text_original="@here"}`。另一次测试中，Bob / Carol 的 presence 状态分别在 online / offline 间切换，但其他输入不变。

Expected：

- `@here` MUST 按 `strand_engaged = strand_participants ∪ strand_watchers` 展开：Bob 因 active discussion participation 命中，Carol 因 effective watch level `all` 命中。
- Dave（`mentions_only`）、Erin（`muted`）、Frank（仅 assignment）、Grace（无读取权）MUST NOT 因该 audience mention 收到 notification stub 或 push wakeup。
- Presence / online 状态 MUST NOT 影响 `strand_engaged` 的 receiver set；实现不得把 `@here` 解释成 presence-filtered audience。
- Sender、普通 Realm 成员、push gateway、公开日志与 delivery response MUST NOT 暴露 recipient count、watcher 列表、watch level、命中原因，且不得区分 Bob 是参与者命中还是 Carol 是 watcher 命中。

### 10.12.1 Vector: Push Notify Outcome Conservation

`vector_id`: `ak.vector.push.notify_outcome_conservation.v1`

前置：调用方对同一 `push_target_id` 提交一次 `ak.edge.push.command.notify`，`notification.devices[]` 含两个不同 `device_id`（`D1`、`D2`）。

Steps：

1. 两个 device 均被 gateway durable 接管。
2. `D1` 接管、`D2` 无有效注册。
3. `push_target_id` 未知（target 级失败）。
4. `D1` 接管、`D2` 因 gateway 暂时不可用未被接管。
5. 用同一 `Idempotency-Key` 与逐字节相同的 body 重放第 1 步。
6. 变体 A：响应只返回 `D1` 的 outcome。
7. 变体 B：响应对 `D1` 返回两条互相矛盾的 outcome。
8. 变体 C：响应额外返回请求中不存在的 `D3`。
9. 变体 D：响应顶层 `push_target_id` 与请求不一致。
10. 变体 E：请求的 `devices[]` 中 `D1` 出现两次，仅 `app_id` 不同。

Expected：

- 第 1–5 步的响应 MUST 对 `devices[]` 逐项守恒：每个输入 `device_id` 在 `outcomes[]` 中恰好出现一次。
- 第 2 步 `D2` MUST 返回 `gateway_status=rejected` + `reason_code=push_token_unknown`；调用方据 `(push_target_id, device_id)` 清理注册。响应 MUST NOT 回传 `push_key`、`app_id`、provider message id 或原始 token 的任何 hash。
- 第 3 步 MUST 展开为每个输入 device 一条 `reason_code=push_target_unknown` 的 `rejected`，MUST NOT 返回 target 作用域的第二种响应形状。
- 第 4 步 `D2` MUST 返回 `push_gateway_unreachable` 并 MAY 携带 `retry_after_ms`；`D1` 已被接管，MUST NOT 携带 `retry_after_ms`，调用方 MUST NOT 因 provider 侧失败重发 `D1`。
- 第 5 步 MUST 返回与第 1 步相同的逐项结论（`gateway_status` 为 `duplicate` 或与首次一致的接管结论），MUST NOT 产生新的 provider 投递。同一 key 配不同 body MUST 返回 `duplicate_conflict`。
- 变体 A / B / C / D 虽通过 JSON Schema，但 MUST 被判为不合规（`schema_violation`）：守恒是 JSON Schema 无法表达的跨字段不变式，verifier MUST 自行校验。
- 变体 E MUST 被 gateway 拒绝（`schema_violation`）：`devices[]` 按 `device_id` 唯一，`uniqueItems` 只能拦截逐字节相同项。
- 任何 outcome MUST NOT 携带 provider 投递状态、`provider_retries[]` 或未登记的 `reason_code`。

### 10.13 Vector: Events Query Range Completeness Detection

`vector_id`: `ak.vector.sync.range_completeness_client_query.v1`

前置：服务端 `supported_features[]` 声明 `events_query_range_completeness`；Realm 配置 `audit.range_completeness_witnesses[]` 且已存在覆盖区间 `(F1, F2]` 的 `federation_witness_attested` attestation；区间内 actor Bob 产生过 `seq 10..20` 的 reducer-input event。

Steps：

1. 客户端因 `dropped` / cursor 失效按 [`client-sync.md` §12.3](../sync/client-sync.md) 恢复，调用 `ak.self.events.query.scan`（`include_completeness=true`）backfill 区间 `(F1, F2]`。
2. 服务端返回完整事件页 + `range_completeness.attestation_refs[]`；客户端按 [`operations-sync.md` §6.4.4](../sync/operations-sync.md) 重算 Merkle root 并核对 `actor_seq_ranges[]`。
3. 变体 A：服务端从响应中扣下 Bob `seq 14..16` 的事件，但返回同一 attestation。
4. 变体 B：服务端未声明该 feature，收到 `include_completeness=true`。
5. 变体 C：attestation 仅为 `single_source`，而 Realm 声明 `security_class=high_assurance`。

Expected：

- 第 2 步：root 与 `actor_seq_ranges[]` 全部一致时，客户端方可把该区间标记为已 attest 的完整范围。
- 变体 A：客户端 MUST 检出本地视图与 attestation 的差异（`range_completeness_actor_seq_gap` 或 root 重算不一致 `range_completeness_root_mismatch`），把该区间标记 degraded 并 fail closed；MUST NOT 向用户展示"历史完整"。
- 变体 B：服务端 MUST 忽略该参数，响应不含 `range_completeness` 字段且不报错；客户端把范围视为未 attest。
- 变体 C：客户端 MUST NOT 用 `single_source` attestation 解除 high-assurance Realm 的 completeness 关注；按未 attest 处理或继续等待 quorum attestation。

## 11. Personal Agent & Sidecar Vectors

### 11.1 Vector: Provisioning + Pairing + Global Scope Ceiling

`vector_id`: `ak.vector.agent.provision.v1`

Steps:

1. Controller 调用 `ak.self.agent.command.provision`，以必填 `requested_scope` 声明 Agent 的 immutable 全局权限硬上限，得到 `agent_id`、`requested_scope_digest` 与 `pairing_request_id`；服务端在 Agent DID accepted inception history 的唯一 `ArkretPrincipalControlRealm.serviceEndpoint` 只固定 digest，公开 entry 不含完整 scope。Controller 按 `sha256(canonical_json({agent_id, controller_id, kind:"ak.agent.requested_scope_commitment.v1", requested_scope}))` 重算并逐字匹配；provisioning 只写 accountability / selector facts，不创建 Agent Profile、key authorization 或 Realm grant。省略 `requested_scope` 的变体必须 schema validation 失败。
2. Agent runtime 生成 key pair，取得 pairing verifier 签名的 presentation request/challenge；controller 生成符合 `ak.schema.agent_requested_scope_disclosure.v1`、绑定该 verifier/audience/challenge 且接收窗口不超过 300 秒的私有披露，与 key pair request 一起提交。controller-signed `ak.agent.key.authorize.payload.agent_key_scope` 使用 actions/resources/constraints 的严格子集。另提交一个超出 action/resource ceiling 或删除 provision mandatory constraint 的变体。
3. Pairing endpoint 校验 `verification_method` 的 DID 部分(strip fragment/query 后)与 `agent_id` bit-identical。
4. 批准后写入 `ak.agent.key.authorize`；随后为该 Agent 附加一个更窄的 Realm-scoped grant，并分别尝试附加含未 provision action、超出显式内容 resource ceiling 的 grant。

Expected:

- 第 3 步 verification_method 与 agent_id 不一致时 MUST `failed_precondition` `reason=verification_method_principal_mismatch`。
- 第 1 步 DID commitment 必须与 fixture 固定 digest 匹配；公开 service endpoint 必须是 `{realm_id, controller_did, authorization_ref, requested_scope_digest}` 闭合四元组，出现 `requested_scope` 或其它 scope/resource/constraint 明文字段 MUST reject。
- 第 2 步 disclosure 的 controller proof、request/challenge 单次性、verifier/audience、接收窗口与 digest 必须全部通过；缺失、摘要不匹配、重放或错 audience MUST fail closed，且不得退回服务本地 Agent row 作为权威来源。完整 disclosure 不得进入 authorize Event、Realm history、pairing code 或通知。
- 在第 4 步之前，任何 `agent_key_proof` session grant 请求 MUST fail closed。
- 第 2 步更窄 key scope MUST 接受；任何 action/resource 越界或删除 mandatory constraint 的 key scope MUST fail closed。实现不得要求 key scope 与 provision scope 完全相等。
- 第 4 步后 agent runtime 只能在 `requested_scope ∩ agent_key_scope` 上限内签发 session grant；内容 capability 还必须来自后续独立的 Realm-scoped grant。更窄 grant MUST 接受；未 provision action 或超出显式内容 resource ceiling的 grant MUST 以 `agent_grant_exceeds_requested_scope` fail closed。

### 11.1.0 Vector: Requested Scope Public-History Privacy

`vector_id`: `ak.vector.agent.requested_scope_privacy.v1`

Steps:

1. 解析 Agent accepted inception DID Document，验证唯一 `ArkretPrincipalControlRealm.serviceEndpoint` 的闭合四元组；扫描完整 DID version history 与公开 registry/notification/Event fixture。
2. Verifier 生成签名 `ak.identity.presentation_request`，包含唯一 `request_id`、不可预测 `challenge`、`verifier_did`、`audience/domain` 与五分钟内 expiry；controller 经 TSP、HTTP/JWE、DIDComm-like、to-device 或 MLS DM 私有通道返回 `ak.schema.agent_requested_scope_disclosure.v1`。
3. Verifier 验证 controller current proof、`payload_digest`、`agent_id/controller_id`、`verifier_did/audience`、`expires_at-issued_at <= 300s`，消费 `(verifier_did, request_id, challenge)`，并以披露 scope 重算 DID commitment。
4. 负向变体依次为：公开 endpoint 加入完整 `requested_scope`；disclosure 改一个 resource/constraint 但保留旧 digest；错 verifier 或 audience；过期/超 300 秒窗口；重放已消费 challenge；把 disclosure 复制进 grant、authorize Event、notification 或 Realm plaintext。

Expected:

- 正向 disclosure 只作为加密 verifier-private evidence 接受；其缓存键至少为 `(agent_id, requested_scope_digest, verifier_did, audience)`，accepted-at DID/controller lifecycle 变化时重新验证或 fail closed。
- 六类负向变体全部 fail closed。公开 DID history 与其它公共 fixture 中不得出现完整 scope；实现不得因 disclosure 本身“不授予能力”而放宽隐私检查。

### 11.1.1 Vector: Controller-scoped Agent Mention Selector

`vector_id`: `ak.vector.agent.mention_selector.v1`

Preconditions:

- Alice 拥有 verified handle claim `alice:acme.example`，`subject=AliceDID`。
- Alice 拥有 active native personal agent `AgentS`，其 Actor Profile `actor_kind="agent"`、`agent_slug="summary"`、`principal_id=AgentSDID`，且有 active `ak.identity.accountability_grant{issuer=AliceDID, subject=AgentSDID}`。
- Alice 或授权 issuer 签发 current `ak.schema.agent_selector_claim.v1{controller_subject=AliceDID, agent_slug="summary", subject=AgentSDID, binding_state="verified", visibility="restricted", audience=<RealmR>}`。
- 同一 Realm 中 Bob 可见 Alice 的 handle claim、AgentS 的 Actor Profile、selector claim 与 accountability evidence。

Steps:

1. Bob 在 message composer 输入 `@alice:acme.example/summary`。
2. 客户端从本地 Realm roster / actor profile / handle claim cache 解析 controller handle → `AliceDID`，再验证 selector claim `(AliceDID, "summary")` → 唯一 active `AgentSDID`。
3. 客户端提交 Message content AST，其中 mention node `subject_id=AgentSDID`，并可携带 `controller_subject_id=AliceDID`、`controller_handle_at_time="alice:acme.example"`、`agent_slug_at_time="summary"`、`mention_text_original="@alice:acme.example/summary"`。
4. Alice 之后把 `AgentS.slug` 改为 `sum` 并更新对应 selector claim 的 `agent_slug`，或把 `summary` 分配给另一个新 agent `AgentT`。
5. 另一次测试中，Alice 同时存在两个 current valid selector claims 绑定 `(AliceDID, "summary")` 到不同 active agents，或 Bob 不可见 selector claim / accountability evidence。

Expected:

- 第 2 步 MUST 在持久化前完成；selector claim 是 slug 绑定的权威来源。持久化事件里的权威 mention target MUST 是 agent `subject_id=AgentSDID`，不得把 `alice:acme.example/summary` 当作 handle 或权威字段写入。
- 第 3 步的 `controller_*` 与 `agent_slug_at_time` 只作 audit / search / fallback metadata；reducer、dispatcher、policy engine MUST 忽略这些字段做授权和投递决策。
- 第 4 步 MUST NOT 改写历史 mention target；旧消息仍指向 `AgentSDID`。
- 第 5 步 MUST fail closed：客户端不得构造 mention node；实现可提示 picker 选择或把输入保留为普通文本。服务端若收到仅靠 metadata 声称 selector 的事件，也必须只按 `subject_id` 和已验证 agent state 判定。

### 11.2 Vector: Pairing Expiry Auto-Revoke

`vector_id`: `ak.vector.agent.pairing_expiry.v1`

Steps:

1. Controller 调用 `ak.self.agent.command.provision`,pairing 窗口 12 小时，grant TTL 30 天。
2. Pairing 12 小时窗口过期，未提交 `ak.gate.account.command.pair_agent_key`。

Expected:

- 服务将 agent runtime_state 投影为 `pairing_expired`(lifecycle 意图不变)，不得创建、撤销或改写任何 Realm grant。
- 重放 `ak.gate.account.command.pair_agent_key`(使用过期 pairing_request_id)MUST fail closed。
- Controller 可通过 `ak.self.agent.command.renew_pairing` 对同一 agent principal 原地重开 bootstrap pairing，也可重新发起 `ak.self.agent.command.provision`;后者得到新 agent_id,旧 agent_id 与新 provisioning 不复用。两种操作都不得从 `requested_scope` 物化 Realm grant。

### 11.2.1 Vector: Stable Runtime Key Binding 与审批 CAS

`vector_id`: `ak.vector.agent.runtime_key_binding.v1`

Steps:

1. Runtime `R1` 对 open pairing handle 提交 key `K1`；服务端按 [`key-management.md` §3.6.2](../identity/key-management.md) 计算 stable binding digest，生成 approval/notification id 并发送 notification `add`。
2. `R1` 以相同 Agent、handle、verification method、public key 和 attestation 重试；权威 pairing code、challenge、audience 不变，只刷新 PoP `created_at` / `expires_at` / `transcript_digest` / `signature`，服务端重算 stable digest 与 current pairing-request digest。
3. Runtime `R2` 在同一 handle 提交不同 public key `K2`。
4. Controller device `C0` 读取 proof `P1` 并签审批；提交前同一 stable binding 刷新为 `P2`，`C0` 再提交绑定 `P1` digest 的旧审批。
5. Controller device `C1` 重新读取当前 `P2`，核对 pairing secret 后签署当前 `ak.agent.key_pairing_request_binding.v1` 并提交 final pair；另施加 wrong challenge/audience/secret、超过 5 分钟、public-key/method 不等、坏 transcript digest/signature 与旧开放 proof 的单点变异。

Expected:

- 第 1 步得到 fixture 固定的 `public_key_digest`、`attestation_digest` 与 `expected_binding_digest`；helper 输出必须逐字匹配。
- 第 2 步 stable digest、approval id、notification id 不变，projection action 为 `update`；freshness 字段不进入 stable digest，但 `proof_of_possession_digest` 与 pairing-request digest 必须改变。
- 第 3 步 MUST HTTP 409 `agent_runtime_request_conflict`，不得覆盖 K1、approval id 或 notification id。
- 第 4 步 MUST fail closed；旧 proof/prompt 不得消费 handle 或激活 key。
- 第 5 步服务端必须从当前持久化 request 与 pairing record 重算 stable binding、PoP transcript/digest/signature 和 `ak.agent.key_pairing_request_binding.v1`；只有 controller 签名绑定当前值时审批成功，并在 durable authorize accepted 后发 `remove(reason=approved)`。全部单点变异都必须在状态改变前 fail closed。
- 所有 notification delta 与 provider-visible blind push 中均不得出现 pairing code、public key、PoP、attestation、display name 或 slug。

### 11.2.2 Vector: Managed Agent PCR 分离

`vector_id`: `ak.vector.agent.managed_pcr_separation.v1`

Steps:

1. Provision Agent DID `A`，controller DID 为 `C`；Agent DID Document 写唯一 `ArkretPrincipalControlRealm` service entry，分配 `PCR_A`，并只固定 immutable `requested_scope` 的域分离 digest；完整 scope 由 controller-private disclosure 出示，controller 已有 `PCR_C`。
2. Controller 按 delegation 创建 `PCR_A` genesis，并写 Agent profile/key/lifecycle facts。
3. Provisioning 只把 accountability grant 与 selector claim 写入 `PCR_C`；无论 `requested_scope` 是否列出内容 action 或显式内容 resource selector，都不得产生 pending / active capability grant。内容授权只能由后续独立、完整签名且写入对应受治理 Realm 的 `ak.capability.grant` 产生；operation/service scope 同样不生成隐式 `ak.event.read` 或其它内容 grant。
4. 变体 A：实现把 `PCR_C` deterministic id 当作 Agent PCR；变体 B：在 `PCR_A` 或 `PCR_C` id 上创建缺 PCR marker、restricted history、MLS profile 或任一 E2EE floor 的 Realm；变体 C：服务端以 Agent DID 伪造 proof，省略 `executed_by=C` / `authorization_ref`，或引用的 delegation purpose/resource scope 不覆盖目标 Event kind/PCR；变体 D：把 `requested_scope` 当作 Realm grant、在 provisioning 时物化内容权限，或在后续 Realm grant / participation 中允许超出 `requested_scope.actions[]` 的 action。

Expected:

- `PCR_A != PCR_C`，且 receiver 必须从 Agent DID accepted-at history 验证 service entry 的 PCR/controller/authorization/digest 四元组，再验证 controller-signed private disclosure 后使用 scope；不得验证实现私有派生算法或信任服务本地 scope row。
- `PCR_A.created_by == PCR_A.notary == A`，purpose/profile/history/encryption floor 全部满足 PCR invariant。
- Controller 写 Agent PCR 时 `actor_id=A`、`executed_by=C`，proof method 属于 C，delegation 覆盖目标 kind；不得伪造 A 签名。
- Agent profile、key authorize/revoke、lifecycle 只进入 `PCR_A`；accountability/selector facts 只进入 `PCR_C`；Realm-specific capability grant 只进入其所治理 Realm；pairing request/notification 不进入任一 PCR。
- 四个变体全部 fail closed，且不得留下非 PCR Realm 占用任一 principal control id，也不得扩大 Agent 的内容权限。

### 11.2.3 Vector: Managed Agent PCR Recovery

`vector_id`: `ak.vector.agent.managed_pcr_recovery.v1`

Preconditions:

- Controller `C` 有 current accepted recovery policy `RP_C` 与 recovery public key；managed Agent `A` 的 DID service binding 指向 `PCR_A`，delegation purpose 覆盖 `principal_control_realm_bootstrap`、agent-control authoring 与 `principal_control_realm_recovery`。
- `ak.self.agent.command.provision` 已返回 `pcr_recovery.status=pending`；尚无 runtime key authorization。

Steps:

1. Controller E2EE client 本地生成 `PCR_A` MLS group state，提交 Agent PCR genesis / profile Event；服务端只接收 ciphertext/承诺，不接触 MLS private state。
2. `C` 的授权设备向 `C` 自己的 `backup_kind=mls_history` active series 尾部写入 `mls_group_state` item：外层 `actor_id=C`，`recipient_method=recovery_public_key`，`recovery_policy_ref=RP_C`；item 的 `realm_id=PCR_A`，`managed_principal_binding={managed_principal_id:A, controller_id:C, principal_control_realm_id:PCR_A, authorization_ref, managed_frontier_ref}`，AAD `managed_principal_bindings[]` 与 public/plaintext binding canonical set 完全一致。
3. 服务投影 `pcr_recovery.status=ready`，首次 `pair_agent_key` 针对 pre-commit frontier 通过门控并写入 Agent PCR 的 controller-signed `ak.agent.key.authorize`；该 Event 推进 frontier 后，投影转为 `stale`，producer 再追加覆盖 post-commit frontier 的 backup 尾部使其恢复 `ready`。
4. 丢失 Agent runtime private key；新 runtime 生成 `K2`，controller 先确认 managed PCR backup 仍覆盖 current frontier，再走 replacement re-pairing。
5. 丢失 controller 全部日常设备；controller 用自己的 24 词/门限/硬件恢复普通用户设备与 `mls_history` active series，解出 `PCR_A` group state，并依据当前 Agent DID delegation 继续管理 `A`。
6. 变体：服务端生成 MLS state；把 runtime private key 放入任一 backup；外层 `actor_id=A` 但由 `C` 读取；缺失/篡改 binding 或 AAD set；使用 `secret_storage_key`；`RP_C` / delegation / PCR Seal / MLS epoch stale；为 `A` 生成独立人类助记词。

Expected:

- 步骤 1–2 中 MLS private state 只在 controller E2EE client；backup owner/caller 始终是 `C`，不放宽跨 actor 拒绝。合法 envelope 通过 `ak.schema.key_backup.v1` / plaintext schema 与 accepted-at delegation 校验。
- 只有 active series 尾部包含 pre-commit current `PCR_A` group state 且 policy/binding/frontier/epoch 全部匹配时状态为 `ready`；否则为 `pending` / `stale`，步骤 3/4 的 pairing commit MUST `agent_pcr_recovery_not_ready`，handle、旧 key 与 grants 全部不变。pairing 自身推进 frontier 后必须先投影 `stale`，待 post-commit backup accepted 再回到 `ready`，不得把 pre-commit backup 错当成仍覆盖新 frontier。
- 步骤 4 不恢复或克隆旧 runtime private key；K2 由新 runtime 本地生成，旧 authorization 由单一 authorize Event 的精确 `supersedes[]` 原子替换。
- 步骤 5 只恢复 PCR 解密/管理连续性，不自动授予 Agent DID 控制或业务 capability；后续写入仍验证当前 controller delegation。
- 步骤 6 全部 fail closed。Native Personal Agent 不拥有独立面向用户 Recovery Key；controller 的 Recovery Key 解锁 controller-owned envelope，不直接确定性派生 Agent/runtime private key。

### 11.2.4 Vector: Runtime Replacement Re-pairing Supersede

`vector_id`: `ak.vector.agent.repairing_supersede.v1`

Preconditions:

- Agent `A` status `active`,持有 authorized key `K1`(`ak.agent.key.authorize`),`K1` 签发的 session grant `S1` 未过期。

Steps:

1. Controller 先提交 controller-signed delegated `ak.self.agent.pause`，再调用 `ak.self.agent.command.renew_pairing`，得到新一次性 `pairing_request_id` + `pairing_code`、`pairing_mode="replacement"` 与未被重置的当前 `pcr_recovery` 投影；直接在 `active` 调用的变体 MUST `failed_precondition`。
2. Agent 保持 `paused`；旧 key `K1` 与既有 grants 尚未被 replacement 撤销，但服务端不得签发新的 agent session grant 或执行新的 capability action。Controller 在 replacement 完成前调用 resume 的变体 MUST `failed_precondition`。
3. 新 runtime 生成 key `K2` 提交 runtime-key-request；controller 签 `ak.agent.key.authorize`(K2)，其 payload 带 `supersedes=[{key_id: K1, authorized_event_ref: <K1 authorize Event>}]`，再调用 `ak.gate.account.command.pair_agent_key` 完成配对。
4. 用 `K1` 再次请求 `agent_key_proof` session grant;`S1` 在 freshness window 后被使用。
5. 变体 A:第 1 步的 handle 过期，未走到第 3 步。
6. 变体 B:agent 已 `deactivated`,controller 调用 renew_pairing。

Expected:

- 第 1 步的 pause 之外，renew_pairing MUST NOT 改变 agent status、既有 key、grant 或 `pcr_recovery`；响应分支是 `pairing_mode="replacement"`，此前所有 pairing handle 永久不可解析。active 直调不得创建 handle。
- 第 2 步的新 session / capability action 与 open replacement 期间的 resume MUST fail closed；已存在 key/grant 的保留只用于原子 supersede 与审计，不等于 paused 状态可继续执行。
- 第 3 步 MUST 以单一 controller-signed `ak.agent.key.authorize`(K2) Event 原子 remove `supersedes[]` 指定的 K1 authorization dot（reason=`superseded_by_repairing`）并 add K2 dot；不得伪造第二条 controller-authored revoke Event；capability grants 不受影响。遗漏 K1、加入不存在/已撤销 authorization，或引用错误 `authorized_event_ref` 的变体 MUST conflict / fail closed 且不改变任何 key。
- 第 4 步 MUST fail closed:`K1` 的新 session 请求拒绝;`S1` MUST 在 revocation freshness window 内 fail closed,MUST NOT 自然存活到原 TTL。
- 变体 A:无任何配对副作用,agent lifecycle 保持 `paused`、`K1` 有效,runtime_state 回到 `ready`;`pairing_expired` MUST NOT 出现在曾持钥 agent 上；handle 过期后 open-handle 投影必须清除。pause / resume 是纯 lifecycle 意图写入，在 handle open 期间也不被阻塞。
- 变体 B:MUST `agent_deactivated`(terminal 状态拒绝续期)。

### 11.2.5 Vector: Longevity-safe Authorization Chain(No Expiry Cliffs)

`vector_id`: `ak.vector.agent.longevity_no_expiry.v1`

Steps:

1. Controller provision agent,`ak.identity.accountability_grant` 不声明 `expires_at`,`ak.agent.key.authorize` 不声明 `expires_at`,授予不带 temporal constraint 的低风险内容 grant(如 `ak.agent.draft.propose` + 显式 resource selector)。
2. 模拟长时间推移(超过任何常见部署 TTL,如 400 天)后,runtime 用 authorized key 签发 session 并执行 grant 内动作。
3. Controller 执行 `ak.self.agent.command.pause`。
4. 提交 `risk_tier=high` action 的 agent grant(如 act-on-behalf 链路)但不带 `expires_at`。
5. Controller 对同一 `(agent_id, key_id)` 提交 re-authorization，在 `seal_basis` view 中 observe 当前单一 authorize dot。
6. 变体 A：两个 re-authorization 基于同一旧 `seal_basis` 并发，并声明不同的 scope / audience / `expires_at`。

Expected:

- 第 1 步 reducer MUST 接受:缺省 `expires_at` 的 key authorization / accountability grant / 低风险 agent grant 均合法(revocation-governed),MUST NOT 以 `failed_precondition` reason=缺失过期拒绝;Actor Profile `accountable_principal_ids` 校验把无 `expires_at` 的 active grant 判为 verified。
- 第 2 步 MUST 成功:授权链上没有任何静默定时器;session 签发仍逐次校验未撤销 / status / scope / audience。
- 第 3 步后新 session MUST 拒绝，已签发 session 在独立于 session TTL、且 MUST ≤ 60s 的 pause freshness window 内 fail closed；把窗口设为 session 最大 TTL 的实现 MUST 判失败——kill switch 是唯一失效路径的证明。
- 第 4 步 reducer MUST `failed_precondition`:高风险 action 的 grant 仍然强制有限 `expires_at`(§8 风险分层硬约束不因 longevity 放宽)。
- 第 5 步 MUST 在同一 Control Move 中 observe-remove 全部已观察 authorize dots 并 add 一个 replacement dot；接受后该 cell 只有一个 active authorize dot，新边界生效。
- 变体 A join 后的 effective authorization MUST 对 scope / audience 取交集、对 `expires_at` 取最早有限值（缺省按 `+infinity`）；MUST NOT 按到达顺序选 winner。

### 11.2.6 Vector: Native Agent KeyPackage Authorization Binding

`vector_id`: `ak.vector.agent.mls_keypackage_authorization.v1`

Preconditions:

- Native Agent `A` 已完成 pairing；当前 active accepted `ak.agent.key.authorize` Event 为 `E1`，其 `verification_method=K1`，runtime 持有 K1 私钥与独立 MLS endpoint id `D1`。
- `A` 不是 controller 的 delegated device，且不存在 `(A,D1)` 的 `ak.device.authorize`。

Steps:

1. Runtime 用 K1 作为 MLS LeafNode signature key 生成 KeyPackage，并用 K1 签署发布 transcript；服务端从当前 accepted Agent key projection 写入 `agent_key_authorize_event_id=E1`。
2. Requester claim 该 KeyPackage，并把返回的 `agent_key_authorize_event_id=E1` 原样写入 Welcome `claim_ref`。
3. Receiver 在解密 Welcome 前 resolve E1，校验 E1 仍是 A 的 active accepted authorization，`verification_method=K1`，并校验发布 `device_signature.kid` 与 MLS LeafNode signature key 都绑定 K1。
4. 负向变体依次为：同时携带 `ssk_generation` / `device_authorize_event_id` 中任一字段；把 E1 填入 `device_authorize_event_id`；Event ref 属于另一 Agent；`device_signature.kid` 或 MLS LeafNode signature key 为 K2；E1 被 revoke、被 replacement `supersedes[]` 替换或可选 `expires_at` 已到期；只有 service-local Agent row 而无 accepted E1。
5. E1 被 E2 replacement 后，以 K2 发布新 KeyPackage并重新 claim，得到新 `claim_id` 与 `agent_key_authorize_event_id=E2`。

Expected:

- Steps 1–3 MUST 接受；D1 只作为 A 的 MLS endpoint / Welcome 投递实例，不创建或推断 `ak.device.authorize`，A 仍是独立 MLS member。
- Step 4 全部 MUST fail closed：wire 形状混合时 `schema_violation`；accepted trust state、principal、lifecycle 或 key material 不匹配时 `claim_generation_mismatch`。实现不得 fallback 到 controller device、service-local row、过期 authorization 或任一其它 trust branch。
- Step 5 MUST 接受；E1 下所有未消费 claim 永远失效且不得改写，新 Welcome 只能使用重新 claim 得到的 E2 binding。

### 11.2.7 Vector: KeyPackage write canonical transcripts

`vector_id`: `ak.vector.crypto.keypackage_write_transcripts.v1`

fixture：`spec/v1/artifacts/fixtures/keypackage-write-transcript-fixture.json`

Steps:

1. 用 fixture 的 typed upload request删除顶层与 entry signatures，通过 SDK `keypackages_upload_signing_input`生成 bytes；另对单 entry调用 `keypackage_upload_entry_signing_input`。
2. 用 typed consume/revoke request分别删除其 `signature`，通过 SDK helper生成 bytes。
3. 对每条 bytes比较 fixture `canonical_jcs`、`signing_input_base64url`，并以 fixture Ed25519 test key验证 `signature`。
4. 负向依次替换为旧 `ak.keypackage-upload-v1` domain、从 upload移除 `principal_id`、把缺省 optional字段写成 `null`、仅保留合法 entry signature但破坏 batch signature。

Expected:

- Steps 1–3 MUST byte-identical通过；普通 device与 Native Agent runtime不得产生不同 bytes。
- Step 4 全部 MUST fail closed。entry signature不替代 required batch signature，服务端不得尝试旧 transcript或本地 principal-type fallback。

### 11.3 Vector: Agent Session Grant Replay Protection

`vector_id`: `ak.vector.agent.session_grant.replay.v1`

Steps:

1. Agent runtime 提交 `ak.gate.account.command.issue_session_grant`,`proof.proof_kind="agent_key_proof"`,proof 含 challenge / audience / request_canonical_digest / expires_at / signature。
2. 第二次提交同样的 proof(同样 challenge / digest / signature)。
3. 提交一份 audience 改成另一 service 的 proof。
4. 把 proof.signature 改写但 challenge 不变。

Expected:

- 第 1 步 MUST 成功，服务端把 challenge 进入 replay table。
- 第 2 步 MUST fail closed(challenge 已使用)。
- 第 3 步 MUST fail closed(audience mismatch)。
- 第 4 步 MUST fail closed(signature 不验，且 challenge 仍 burnt)。

### 11.4 Vector: Controller Deactivate → Agent Session Cascade

`vector_id`: `ak.vector.agent.controller_lifecycle.v1`

Steps:

1. Controller 拥有 active agent `A`,A 持有未过期 session grant `S`。
2. Controller 进入 `deactivated`。

Expected:

- A 的 active session `S` MUST 在 revocation freshness window(≤ session TTL)内 fail closed。
- A 后续任何 `ak.gate.account.command.issue_session_grant` MUST fail closed。
- A MUST 立即离开相关 Sidecar desired access；服务端停止投递，并对每个 backing Circle 主动 fan-out `ak.circle.member.state -> leave` 与 MLS remove/epoch rotation。

### 11.5 Vector: Act-on-behalf Attribution

`vector_id`: `ak.vector.agent.act_on_behalf.v1`

Steps:

1. Agent A 持 act-on-behalf grant `G`(scope: `ak.message.create` on Strand F,approval_required=true, expiry < 15 min)。
2. Agent A 提交 message,envelope `actor_id=controller`,`executed_by=A`,`authorization_ref=G`,`proof.verification_method` 解析到 A 的 agent key。
3. Receiver 校验。
4. 第二次重用同一 approval nonce。

Expected:

- 第 3 步 MUST 校验 `executed_by` ↔ proof key 一致、`authorization_ref` 覆盖 `ak.message.create` + Strand F + 未过期；通过则接受。
- Reducer 写入 `actor_kind="agent"` projection(注意是 reducer-stamped,actor 提交侧不携带)。
- 第 4 步 MUST fail closed(`reason=approval_already_consumed`)。
- 客户端渲染 "Controller via Agent" 双重署名；不显示为纯 controller 行为。

### 11.6 Vector: Relation Reference Projection Indistinguishability

`vector_id`: `ak.vector.relation.reference_projection_indistinguishable.v1`

Steps:

1. Realm A 中存在 weak semantic Relation `R1`，目标指向 Realm B 内对象；调用者 C 可读 Realm A，但不能 discover / reference Realm B。
2. Realm A 中存在形态相同的 Relation `R2`，目标指向不存在或不可发现的 Realm / object id。
3. C 分别调用 Relation projection query、`ak.self.events.query.scan` raw event API、backfill pull 与 federation peer fanout 视图。
4. 在同一服务端测量点、同一请求类别与同一部署 profile 下，对 `R1` / `R2` 每类至少采样 30 次。
5. Auditor D 同时持有 source + target disclosure，读取 `R1` 的完整 canonical event。

Expected:

- C 对 `R1` / `R2` 均只能看到 `ReferenceProjectionState.locked` 或等价 locked stub,wire 字段集合、error envelope、metadata 集合必须相同。
- C 的视图 MUST NOT 泄露目标 `realm_id`、title、member_count、created_at、issuer set、preview 或任何能区分"目标存在 vs 不存在"的信息。
- raw event / backfill / federation fanout 对 C MUST 返回同一类 redacted event view 或 locked stub，不得暴露完整 `from_ref` / `to_ref` canonical bytes。
- 两类样本 p95 服务端耗时差异 SHOULD <= 50ms；声明高安全 profile 时 p99 MUST 落入同一 timing bucket。
- D MAY 取得完整 canonical bytes，但不得改变 C 对同一 Relation 的 locked projection shape。

### 11.7 Vector: Circle Directory Visibility Members Indistinguishable

`vector_id`: `ak.vector.circle.directory_visibility_members_indistinguishable.v1`

Steps:

1. Realm R 中存在 Circle C,`directory_visibility="members"`；viewer V 是 Realm member 但不是 Circle member。
2. V 分别用 Circle id、`short_name`、title prefix 与不存在的 Circle id 调用 Circle get / list / search / Realm directory projection。
3. V 读取 Realm seal public view commitment。
4. Circle member M 执行同一组调用。

Expected:

- 对 V，可见 Circle 与不存在 Circle 的响应 MUST 使用同一 envelope、字段集合和 timing bucket。
- V MUST NOT 看到 Circle title、display、short_name、member_count、created_by、member id、join history 或可枚举错误。
- V 的 stub 最多为 `{ "visibility": "locked", "opaque_commitment": "<fixed-length>" }` 或等价字段集合；`opaque_commitment` MUST 固定长度、不可逆、不可由 title / short_name / member set 枚举。
- Realm public seal 只暴露固定 cadence 的 opaque commitment，不得反映真实 Circle 活动频率。
- M MAY 看到 policy 允许的 Circle metadata，但不得改变 V 的不可区分性要求。

### 11.8 Vector: Agent Sidecar Idempotent Ensure

`vector_id`: `ak.vector.sidecar.ensure_idempotent.v1`

Steps:

1. Alice 的两台设备并发调用 `ak.self.agent.sidecar.command.ensure` 同一 `context_ref`。
2. 同一 Alice 第三次调用 `ensure`(同样 context_ref),`addressed_agent_ids` 列表不同。
3. Alice 在另一 context_ref 调用 ensure(同 Realm)。

Expected:

- 第 1 步并发 MUST 收敛到单一 `sidecar_id`、单一 reducer-managed backing Circle 与单一 private Strand；两个 response 的公开 typed IDs bit-identical，且不返回 `private_circle_id`。
- `ak.sidecar.create` MUST 与 backing Circle/initial access/Strand/Relation 在同一 atomic batch 中，并以 `effective_scope.circle_id=backing_circle_id` 投递；任一子事件失败时不得留下部分对象。
- backing Circle shape MUST 与 `sidecar.md` §5 bit-identical；普通 Circle create/update 使用 `SC-` short-name 前缀 MUST 以 `reserved_circle_short_name` 拒绝。
- 第 2 步 MUST 复用既有 Sidecar 与 Strand；addressed list 不改变 desired/effective access 或 Strand/Relation identity，只影响本次 exchange fanout。
- 第 3 步 MUST 复用 `(realm_id, controller_id)` Sidecar 与 backing Circle，创建新的 context-private Strand。

### 11.8.1 Vector: Sidecar MLS Bootstrap Binding

`vector_id`: `ak.vector.sidecar.mls_bootstrap_binding.v1`

Steps:

1. Alice ensure 一个包含 eligible Agent A 的 Sidecar，读取服务端派生的 `mls_context.{desired_access_digest,control_frontier}`。
2. Alice 当前设备用真实 OpenMLS state 创建 Circle-scoped `ak.mls.genesis`，提交前持久化 `(sidecar_id, genesis_event_id, mls_group_id, provisional_snapshot)`，并在 governance binding 中携带精确 `sidecar_binding`。
3. 第二设备并发提交另一 `mls_group_id` 的 genesis；再分别变异 `sidecar_id`、digest、frontier 顺序/成员、backing Circle 与 creator device proof。
4. 模拟第一设备在 Event response 返回前崩溃并重启。

Expected:

- fixture transcript 的 RFC 8785 JCS digest MUST 为 `sha256:a8c91fc896c6c19179770fdd629ca3fd24acbb8a3d824b0d76c6ad77f3a5767a`；controller 必须包含在排序去重的 principal set 中。
- 只有一个 genesis 通过标准 Event admission/CAS 成为 canonical winner；服务端不得生成 MLS private state、伪造 GroupInfo/ratchet-tree digest 或提供绕过 Event proof 的 bootstrap endpoint。
- 所有 binding 变异 MUST fail closed；Sidecar backing Circle 缺失 `sidecar_binding`、普通 Realm/Circle 携带该字段也必须拒绝。
- 崩溃恢复重放 bit-identical Event id/bytes，并把已接受 provisional snapshot 激活；loser snapshot 必须销毁并通过 winner group 的 KeyPackage/Welcome 加入。

### 11.9 Vector: Existence Privacy

`vector_id`: `ak.vector.sidecar.existence_privacy.v1`

Steps（均以 Sidecar access 之外 caller 视角）:

1. `ak.self.events.stream.subscribe` / `ak.self.events.query.scan` 目标 Realm。
2. 对 `to_ref=<target_message_id>` 的 relation query。
3. Realm directory 调用。
4. 触发目标 Strand 的 notification fanout。
5. 读取目标 Realm default seal leaf 明文 metadata。

Expected:

- 第 1 步返回 zero events referencing Sidecar / backing Circle / private Strand / private Relation。
- 第 2 步看不到 `agent_sidecar_of` 边。
- 第 3 步对 `sidecar_id`、backing Circle title/display/short_name/member_count 均 zero hits。
- 第 4 步 sidecar 内 `ak.message.create` 不触发任何 target Strand member 的 notification。
- 第 5 步 sidecar `effective_scope=circle` event 不出现在 default seal leaf 明文中；只能作为 opaque commitment。

### 11.10 Vector: Desired/Effective Access + Revocation 闭环

`vector_id`: `ak.vector.sidecar.eligibility_states.v1`

Steps:

1. Alice 有 Agents `{S, R}`。S 已 paired/MLS-ready；R 满足 eligibility 但未发布 KeyPackage。
2. Alice 调用 ensure。
3. R 发布 KeyPackage，服务端 async reconcile。
4. Alice 调用 `ak.self.agent.command.deactivate` 对 R。

Expected:

- 第 2 步 ensure SHOULD succeed，返回 `access_readiness=key_material_pending` 与 `pending_access_reconciliations: [{agent_id: R, stage: device_key_material, reason: missing_mls_keypackage}]`。R 在 desired access 中、尚不在 effective access，不能收取或解密消息。Sidecar 不存在 plaintext 分支。
- 第 3 步 R 经 backing Circle MLS Welcome 加入，只获得 join 后 future epoch keys（MUST NOT 获得 join 前 epoch keys）；reconciliation 完成后才进入 effective access。
- 第 4 步 R 立即离开 desired access并停止投递；reducer/service 在同一 control apply 中生成 backing `ak.circle.member.state=leave` 与 durable pending MLS removal obligation，eligible controller/key-service committer 随后提交真实 remove/rotation。后续 R 的 proof、Sidecar write 与 query MUST fail closed。

### 11.10.1 Vector: Sidecar MLS Effective Access Evidence

`vector_id`: `ak.vector.sidecar.mls_effective_access.v1`

Steps:

1. A 已有 backing Circle membership，但尚无 Add Commit/Welcome/consume；随后分别只补齐其中一部分证据。
2. 对 A 的 active device D 提交 accepted Add Commit、引用该 Commit 且 binding 匹配的 accepted Welcome，并由 D 的 authenticated session consume 同一 claim/KeyPackage。
3. 对 controller 的第二设备重复 join；随后撤销 A eligibility，使 backing membership leave 与 pending removal obligation accepted，但暂不提交 Remove Commit。
4. eligible committer drain obligation 并提交真实 Remove proposal/Commit；再用旧 Welcome/consume 记录尝试恢复 A effective 状态。

Expected:

- 第 1 步任何不完整组合均保持 pending；Circle membership、delivered Welcome 或 claimed KeyPackage 单独都不是 effective 证据。
- 第 2 步 D 成为有效设备，A 进入 `effective_agent_ids`；同 principal 的其它设备不会自动拿到密钥。controller 当前 session device readiness 独立计算。
- 第 3 步服务端立即停止 A 的寻址/投递并移除 desired/effective access，且只产生 durable removal obligation；不持有 MLS private state的 Principal Server 不得伪造 Commit。新发送保持 fail closed。
- 第 4 步真实 Remove Commit 推进 epoch；旧 Welcome/consume 不能使已移除设备复活。

### 11.10.2 Vector: Hosted Multi-Track Projection and Private Echo

`vector_id`: `ak.vector.sidecar.hosted_projection.v1`

Steps:

1. Alice 在来源 Strand `F` 的 `discussion` Track 以 owned-Agent selector 提交 routed request，当前已见 shared frontier 为 Event `E0`。
2. 客户端以 `{realm_id, strand_id=F}` ensure Sidecar；分别以额外 `track_name` 与 `message_id` 构造两个 negative ensure request。
3. private request Event `P1` 被接受后，客户端 fold 出 `exchange_id=X1` 的本地 `ak.schema.agent_sidecar_exchange_projection.v1` cache；删除该 cache 后从 private history 重建。
4. Alice 激活主 Strand 寄宿 Sidecar，在 `context_merged` 下依次切换 `discussion`、`synthesis`，再切换为 `sidecar_only`；`synthesis` private Track 尚未建立。
5. Agent 在同一 exchange 产生内部协作 Event `I1`（binding `role=internal`）与明确 user-facing response Event `R1`（binding `role=user_facing_response`，`request_event_id=P1`）；随后 Alice 在 active Sidecar 内直接创建 native Event `N1`（无 binding）。
6. 第二设备从 account stream 恢复 view state，并从 Sidecar private Event history 独立 fold exchange projection。

Expected:

- 第 2 步所有合法 Track 共用同一 private Strand；带 `track_name`/`message_id` 的 ensure request closed-schema reject，不能创建第二条 private Strand。
- 第 3 步 cache 删除/重建不重复 private request 或 Agent execution；echo 位于 `E0` 后，同 anchor 按 `(source_hlc, exchange_id)` 排序。
- 第 4 步主 Strand title/breadcrumb/Track tabs 保持可见，scope bar 位于 header 与 tabs 之间；两种 mode 对后续 Track 生效，所有 active writes 指向 private Track。缺失 private `synthesis` 显示 private empty state，不回退 shared write/read。
- merged `discussion` 按 private Event id 去重，`P1` 不因 private fold 与 echo projection 重复显示；shared/private provenance 与 controller-only 可见性标识持续可见。
- 只有 `P1` 与 `R1` 可进入 echo；`I1` 与 `N1` 不创建 source echo。第二设备得到相同排序、状态与去重结果，且无需来源 Realm 重放 private Event。

### 11.10.3 Vector: Sidecar Exchange Binding Closed Loop

`vector_id`: `ak.vector.sidecar.exchange_binding_closed_loop.v1`

Steps:

1. Alice 提交 routed request：`P1` 携带 `role=request` binding，`addressed_agent_ids=[S,T]`、`completion_policy=coordinator`、`coordinator_agent_id=S`。非 addressed backing member U 同样解密到 `P1`。
2. S 通过 runtime 消费门后产生 `I1` 与 user-facing `R1`；runtime 重启并再次收到 `P1`。controller 又 author 不同 request Event `P_dup` 复用同一 `exchange_id=X1`。T 产生 user-facing `R_noncoord` 且错误声明 `completes_exchange=true`；U 尝试执行同一 request。
3. 构造变异响应：wrong exchange/request/private Strand、actor U、unknown role、missing binding、缺少顶层 `refs[role=after]`、以及 `ak:message:` shaped request id；另由 T 发送携带 `role=request` 的 Event `F1`。
4. `R1` 重复投递同一设备两次。
5. S 发送 `R2`（`role=user_facing_response`, `completes_exchange=true`, `coordinator_assignment_event_id=P1`）；controller 验证后 author `C1=ak.agent.sidecar.exchange.control{action=close,response_event_ids=[R1,R_noncoord,R2]}`。

Expected:

- 第 1 步 runtime 只从 `P1` binding 获得 `X1`；不存在 Account Data projection 读写路径。S/T 可继续消费，U 必须把 request 当作不存在。
- 第 2 步 runtime 持久化 `X1 → P1`，restart 不得重复执行；`P_dup` 即使拥有不同 Event id 也因复用 `X1` fail closed。已接受的 canonical `P1` 已处于 delivered，`I1` 只推进 participating 且不改变状态；`R1` 推进 responding；T 的正文可回显，但非 coordinator completion 请求不得产生 control Event；U 不执行。
- 第 3 步全部变异 fail closed 为 non-echo；missing binding 是安全缺省而不是 schema error；`R_msgid` 是 closed-schema reject；wrong Strand/actor/ref 不进入 fold；`F1` 因 actor 非 controller 整体无效。
- 第 4 步重复到达幂等：`user_facing_response_event_ids` 只含一次 `R1`。
- 第 5 步 `R2` 本身仍只推进 responding；accepted `C1` 才推进 complete。response 集按 `(Event HLC, Event id)` 排序且至少一项；不得由时间流逝、Event 缺席或内容直接推断终态。

### 11.10.4 Vector: Sidecar Exchange Event Fold, Control and Cache Recovery

`vector_id`: `ak.vector.sidecar.exchange_projection_recovery.v1`

Steps:

1. `P1` accepted 后本地 cache 与 intent 都丢失；重启扫描 private Strand history，从 controller-authored request binding 重建。
2. Alice 全部设备离线期间，S 发送 user-facing responses `R1`、`R2`。设备 D1 重连并验证追加；随后 D2 独立重连重放同一流程。
3. D1 暂时只见 `R1`，D2 只见 `R2`，两者 `folded_frontier` 不可比较；随后各自补齐 history。
4. 分别 author terminal controls：`close+[R1]`、`cancel+[R1]`、`close+[]`、`cancel+[]`、`fail(agent_deactivated)+[]`。验证每个 action × response-set 组合。
5. 同一 controller `actor_seq` 上产生 concurrent `close`/`cancel` siblings，并在更高 sequence 产生 `reassign_coordinator`；另一个非终态 exchange 先以 matching expected coordinator reassign，再由新 coordinator请求完成。

Expected:

- 第 1 步 projection 的 identity 字段来自 request/context/accepted scope，不依赖设备本地状态，不重复投递；服务端不参与 fold。Agent-authored request binding 被排除。
- 第 2 步 D1/D2 独立得到 bit-identical 的 response 集合、`(Event HLC, Event id)` 规范排序与状态，不要求来源 Realm 重放 private Event。
- 第 3 步任何设备都不得用 HLC/LWW 覆盖不可比较 cache；补齐后从联合 accepted history 得到同一 Event set digest、最大 causal heads、max HLC 与 `{R1,R2}`。
- 第 4 步 `close/cancel + 非空 response` 都 complete；`close+[]` failed/controller_closed_empty；`cancel+[]` failed/controller_cancelled；`fail+[]` failed/agent_deactivated。complete 的 responses minItems=1，failed responses empty 且 failure_reason_code 必填。
- 第 5 步同 sequence 只取 event-digest bytewise 最大 sibling，第一条有效 terminal 吸收后续 reassign；非终态 matching reassign 生效并更新 assignment Event id，旧 coordinator 的 completion 请求不关单，新 coordinator 可触发 controller close。
- 与 winning terminal 并发但未被其 `basis_event_ids` causal closure 覆盖、或因果上晚于 terminal 的 Agent/control Events 保留为私有审计历史，但不得进入 terminal projection 或改变响应集/状态。
- cache 不上传、不进入 account stream；cache frontier 未被本地已验证 history 支配时必须丢弃，不能回退内存/UI fold。

### 11.10.5 Vector: Sidecar Exchange Binding Containment

`vector_id`: `ak.vector.sidecar.exchange_binding_containment.v1`

Steps:

1. 构造明文 `metadata.sidecar_exchange_binding` 的 Sidecar `ak.message.create`。
2. 构造 shared Realm/Circle scope 的 `ak.message.create` binding，以及 shared scope 的 `ak.agent.sidecar.exchange.control`/control schema plaintext。
3. Alice 从 Sidecar 显式 publish 一条内容到目标 shared Strand。
4. 扫描 publish 产物、shared history、push preview、notification 与公开 telemetry surface。

Expected:

- 第 1 步 wire 上明文出现 `sidecar_exchange_binding` key / binding schema id / `exchange_id` MUST `schema_violation` hard reject（见 `forbidden-wire-fields.json`）。
- 第 2 步明文携带按第 1 步拒绝；加密材料解密后因 scope 不匹配而无效，不得渲染或进入 fold。
- 第 3 步 publish 产物是普通 shared event，不携带 binding、`exchange_id`、`sidecar_id` 或任何 private locator；只允许规范允许的 opaque digest。
- 第 4 步全部 shared/公开/Account Data surface 对 `exchange_id`、binding schema id 与 control schema id zero hits；不存在 account-data key 例外。

### 11.11 Vector: Multi-Agent Publish Attribution

`vector_id`: `ak.vector.sidecar.multi_agent_publish.v1`

Steps:

1. Sidecar desired/effective access 为 Alice + `{S, R}`，且 S/R 都在 private Strand 中产生协作内容。
2. S 调用 publish capability action，生成目标 Strand `ak.message.create`,attribution 设 `executed_by=S` + `authorization_ref=G_S`。
3. R 同时尝试 publish 含 S 部分内容的另一条消息。

Expected:

- 第 2 步 `actor_id` / `executed_by` MUST 是 S 单一 DID，而非 "agent group"。
- 第 3 步若 R 的 grant 不覆盖该内容或 R 未持 fresh approval,MUST fail closed。R 通过自己的 grant 可独立发布，但 attribution 仍是 R 单一 DID；不得复合 S+R。

### 11.12 Vector: Participation Ceiling Tighten-Only

`vector_id`: `ak.vector.agent.participation.ceiling_tighten.v1`

参见 [`../models/realm-and-space.md` §2.2](../models/realm-and-space.md)、[`../models/circle.md` §7](../models/circle.md)、[`../models/strand-and-message.md` §9.4](../models/strand-and-message.md)。

Preconditions:

- 部署顶层 ceiling 全 `false`。Realm `R` 经 Event kind `ak.realm.policy_bundle` 写入 payload path `agent_participation.native_agent`，值为 `{reply:true, accept_third_party_mention:true, act_on_behalf:false}`。

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

`vector_id`: `ak.vector.agent.participation.effective_intersection.v1`

参见 [`../authz/capabilities.md` §5.4](../authz/capabilities.md)、[`../identity/key-management.md` §3.6.1](../identity/key-management.md)。

Preconditions:

- Realm `R` 的 `native_agent` ceiling `{reply:true, accept_third_party_mention:true, act_on_behalf:false}`。Agent `A` 为 controller `Alice` 的 active native personal agent；其 accepted-at DID binding 固定 digest，verifier-private controller disclosure 给出 `requested_scope.actions=[ak.message.create, ak.reaction.add]`，且 mandatory constraints 含一条适用于 `ak.message.create` 的 `claim_based{constraint_subkind=accountability}` controller constraint，因此现场派生 provision ceiling=`{reply:true, accept_third_party_mention:false, act_on_behalf:true}`。

Steps:

1. Alice 调用 `ak.self.agent.participation.resource.replace`，scope=`R`，selection=`{reply:true, accept_third_party_mention:false, act_on_behalf:true}`。
2. 服务端从 accepted-at DID binding 验证 digest，并验证 verifier-private controller disclosure 后现场派生 provision ceiling，再求 effective selection = controller selection ∩ provision ceiling ∩ governance ceiling。
3. 变体 A：之后 Realm ceiling 把 `reply` 收紧为 `false`。
4. 变体 B：controller selection 来源缺失或 unknown。
5. 变体 C：从 `requested_scope.actions[]` 删除 `ak.reaction.add`；变体 D：保留 `ak.message.create` 但删除 controller approval/accountability constraint；变体 E：constraint 仅适用于 `ak.reaction.add` 而不适用于 `ak.message.create`。

Expected:

- 第 2 步 effective = `{reply:true, accept_third_party_mention:false, act_on_behalf:false}`(`act_on_behalf` 被 ceiling 封掉)。`reply` effective=true MUST 物化为一条 subject=`A`、`actions=[ak.message.create, ak.reaction.add]`、resource selector=scope `R` 的 `ak.capability.grant`；`act_on_behalf` effective=false MUST NOT 物化 act-on-behalf grant。
- 物化是幂等的：重复 set 收敛到同一 grant 集合；selection 改变导致的 grant 增删 MUST atomic，不得留半物化状态。
- 变体 A：`reply` effective 翻为 `false` 后 MUST `ak.capability.revoke` 对应 grant。
- 变体 B：任一来源缺失或 unknown，对应位 MUST fail closed 为 `false`。
- 变体 C 派生 `reply=false`；变体 D、E 派生 `act_on_behalf=false`。实现不得接受调用方直接提供的预计算 provision 三位来绕过 actions/constraints 派生。

### 11.14 Vector: Participation Selection Within Ceiling

`vector_id`: `ak.vector.agent.participation.selection_within_ceiling.v1`

参见 [`../sync/service-surface.md` §10.1](../sync/service-surface.md)。

Preconditions:

- Realm `R` 的 `native_agent` ceiling `{reply:true, accept_third_party_mention:true, act_on_behalf:false}`。Agent accepted-at DID binding 固定 digest，verifier-private controller disclosure 的 `requested_scope.actions=[ak.message.create, ak.reaction.add]` 且不含 `ak.event.read`，现场派生 provision ceiling=`{reply:true, accept_third_party_mention:false, act_on_behalf:false}`。

Steps:

1. Controller 调用 `ak.self.agent.participation.resource.replace`，scope=`R`，selection=`{reply:true, accept_third_party_mention:true, act_on_behalf:false}`；虽然 Realm governance 允许第三方 mention，但 provision ceiling 不允许。
2. 变体 A：调用方不是该 agent 的 controller。
3. 变体 B：该 agent lifecycle 非 active(`paused` / `deactivated`)或从未完成首次配对(runtime_state `pending_runtime_key` / `pairing_expired`)。
4. 变体 C：scope 不可解析，或 controller 非该 Realm active member。

Expected:

- 第 1 步 MUST fail closed(`failed_precondition`, `reason="agent_participation_exceeds_ceiling"`)，并在 error detail 中列出被封顶的位(`accept_third_party_mention`)，使 UI 能解释“为何不能开启”；MUST NOT 物化任何 grant。
- 变体 A、B、C MUST fail closed。`ak.self.agent.participation.resource.replace` 仅 controller 可调用；`ak.self.agent.participation.resource.get` 可由 controller 或该 agent runtime 调用。

### 11.15 Vector: Participation Session Overlay

`vector_id`: `ak.vector.agent.participation.session_overlay.v1`

参见 [`../sync/service-surface.md` §10.1](../sync/service-surface.md)。

Steps:

1. Agent runtime 调用 `ak.gate.account.command.issue_session_grant`，`proof.proof_kind="agent_key_proof"`，`agent_scope_request` 覆盖某 participation-aware scope。
2. 服务端签发 session，响应 `scope_details.participation[]`。
3. runtime 收到 `reply=false` 的 scope 后仍尝试 `ak.message.create`(模拟 runtime bug)。

Expected:

- 第 2 步 `scope_details.participation[]` 每个条目 MUST 与 `agent-operations.schema.json#/$defs/agent_participation_entry`(`{participation_scope, selection, ceiling, effective}`)同构，而非扁平三位；承载的是已解析 effective 策略。
- runtime MUST 把该数组视为本 session 行为契约。但它不是安全边界：第 3 步即使 runtime 越权，reducer 因无对应 `ak.message.create` grant MUST `failed_precondition`；第三方 mention 在 dispatcher gate 已被拦下；`act_on_behalf` 越权被 receiver 的 `executed_by`/`authorization_ref` 校验拒绝。

### 11.16 Vector: Participation Third-Party Mention Gate (Non-Retroactive)

`vector_id`: `ak.vector.agent.participation.third_party_mention_gate.v1`

参见 [`../models/strand-and-message.md` §9.4.5](../models/strand-and-message.md)。

Preconditions:

- Agent `A` 为 controller `Alice` 的 active native personal agent，有权读取 Strand `F`。`F` 的 effective `accept_third_party_mention=false`。

Steps:

1. 非 controller 的 `Bob` 在 `F` 发 `ak.message.create`，mention target=`A`。
2. controller `Alice` 自己在 `F` 发 mention target=`A`。
3. Alice 把 `F` 的 effective `accept_third_party_mention` 翻为 `true`，`A` 上线同步。
4. 翻转后 `Carol`(非 controller)再发 mention target=`A`。

Expected:

- 第 1 步 MUST NOT 为 `A` 派生任何 mention notification、inbox row、push wakeup，也 MUST NOT 把该 mention 纳入 `A` 的 `ak.self.events.stream.subscribe` 投影；抑制只针对 `A`，对 message 的其他 human target、shared history、其它投影无影响。
- 第 2 步照常投递(controller 自己的 mention 不受此 gate，仍受 `A` 是否被授权读取该 scope 约束)。
- 第 3 步翻转 **非追溯**：第 1 步发生在 `false` 期间的历史 mention，翻转为 `true` 后对 `A` 仍 MUST 零记录(notification / inbox row / `ak.self.events.stream.subscribe` 投影皆无)。
- 第 4 步在 `true` 期间的第三方 mention 照常投递，并受 `level=muted`、blocklist、DND、rate-limit 等既有更高优先级规则约束。

### 11.17 Vector: Agent Human Approval Required

`vector_id`: `ak.vector.agent_auth.human_approval_required.v1`

Steps：

1. Agent runtime 以 `proof.proof_kind="agent_key_proof"` 调用 `ak.gate.account.command.issue_session_grant`，请求 policy 标记为 high-risk 且需 controller 批准的 scope。
2. Account Authority 生成 opaque `approval_request_id`，但不向 runtime 返回人类交互 challenge。
3. Controller 在带外 UI 批准，产生 accepted approval / capability / delegation evidence；agent 带该 evidence 重试。

Expected：

- 第一次响应使用统一 ErrorEnvelope：`error.code=claim_required`，`error.details` 必须严格通过 `agent-operations.schema.json#/$defs/agent_human_approval_error_details`，即只含 `reason_code=human_approval_required` 与 `approval_request_id`。
- Runtime 响应中 MUST NOT 出现 CAPTCHA、OTP、password prompt、browser redirect 或等价 interactive human challenge。
- 批准前不得签发 session grant；带外批准成功后的 retry 仍须重新验证 agent key proof、scope ceiling、approval evidence 新鲜度与单次消费语义。

## 12. Media Service Binding Vectors

本节列出 `ak.profile.media_service_binding.v1` 的核心 conformance 向量。完整机器 fixture 为 [`media-binding-fixture.json`](../../artifacts/fixtures/media-binding-fixture.json)，由其顶层 `runner.kind` / `runner.entrypoint` 分派执行；active 状态与适用性以 `vector-registry.json` 为准。详见 [`../crypto-media/media-service-binding.md`](../crypto-media/media-service-binding.md) §2 / §3 / §5–§8 与 [`../crypto-media/call-state.md`](../crypto-media/call-state.md) §4。

### 12.1 Focus Selection — Oldest Membership Wins

`vector_id`: `ak.vector.media_binding.focus_selection_oldest_membership.v1`

Steps:

1. Alice 与 Bob 加入同一 call；Alice 早于 Bob，`Alice.foci_preferred=[fra-1, us-east-1]`，`Bob.foci_preferred=[us-east-1, fra-1]`。
2. 首个 `ak.call.state` 事件 commit。

Expected:

- `session_focus` MUST 为 `fra-1`（Alice 是 oldest member，胜出）；`Bob.foci_preferred[0]` 不参与决策。
- 后续 token exchange 请求 `focus_id=us-east-1` MUST 被 issuer 以 `focus_mismatch` 拒绝。

### 12.2 Session Focus — No Split Brain

`vector_id`: `ak.vector.media_binding.session_focus_no_split_brain.v1`

Steps:

1. `session_focus=fra-1` 已 committed。
2. Carol 加入，本地 `fra-1` connect 失败（network 中断）。

Expected:

- Carol MUST NOT silent fallback 到其它 focus；MUST 以 `focus_unavailable_for_client` 向用户暴露失败。
- 任何后续 `ak.call.state` 事件试图改写 `session_focus` 为 `us-east-1` MUST 被 reducer 拒绝 `session_focus_already_committed`。

### 12.3 Token Exchange — Minimal Fields

`vector_id`: `ak.vector.media_binding.token_exchange_minimal.v1`

Steps:

1. Client POST `/_arkret/self/rtc/token` with the minimum required fields `(realm_id, call_id, actor_id, device_id, focus_id)`。
2. Issuer 返回 200 with `backend_token` / `participant_identity` / `participant_binding` / `expires_at` / `service_signature`。

Expected:

- `expires_at - now` MUST ≤ 600s（SHOULD ≤ 300s）。
- `participant_binding.scheme` MUST = `ak.media.participant_binding.v1`。
- `service_signature.kid` 与 `participant_binding.issuer_kid` MUST 解析到当前 epoch `ak.realm.media_service.service_id`。

### 12.4 Token Issuer — Unauthorised DID Rejected

`vector_id`: `ak.vector.media_binding.token_issuer_unauthorised.v1`

Steps:

1. 攻击者 DID `did:webvh:z6mkfixture:rogue.example` 模拟 token issuer 签发一个语法合法的 token。
2. Client 收到该响应。

Expected:

- Client MUST 拒绝并报 `token_issuer_unauthorised`，不得尝试连接 `connect_url`。

### 12.5 Participant Binding — Required

`vector_id`: `ak.vector.media_binding.participant_binding_required.v1`

Steps:

1. Token issuer 返回 response 缺失 `participant_binding`，或 `participant_binding.sig` 无效。
2. Client 试图把它写入 `ak.call.state.roster_delta.participant`。

Expected:

- Client MUST 拒绝该 token，不发起 `ak.call.state` 事件。
- 即便强行提交，reducer MUST `failed_precondition` `reason=participant_binding_invalid`。

### 12.6 Unknown Focus Type — Fail Closed

`vector_id`: `ak.vector.media_binding.unknown_type_fail_closed.v1`

Steps:

1. Realm policy 中某 `foci[].type = "experimental-x"`（unregistered）。
2. Client SDK 尝试解析。

Expected:

- Client MUST 报 `unknown_focus_type` 并拒绝把该 focus 用作 session_focus；MUST NOT 把 `backend_token` 透传到任意 SDK。

### 12.7 E2EE Key Source — MLS Exporter Only

`vector_id`: `ak.vector.media_binding.e2ee_key_source.v1`

Steps:

1. LiveKit Cloud key escrow 试图通过 backend channel 注入 SFrame key。
2. Client binding adapter 收到非 [`media-service-binding.md`](../crypto-media/media-service-binding.md) §8.1（E2EE Key Injection 通用契约）来源的 key。

Expected:

- Client MUST 拒绝该 key 并报 `e2ee_key_source_unauthorised`。
- 唯一合法 key 来源是 MLS-Exporter（label `ak.rtc-frame-key/v1`, length=19 bytes, Context=`canonical_json({realm_id, call_id, focus_id, epoch_id, participant_identity, device_id})`, KDF.Nh=32 bytes），其中 `participant_identity` / `device_id` 取自已验证的 call roster participant value 与 `participant_binding`。
- 负向覆盖：以下派生 MUST 同样 fail closed 报 `e2ee_key_source_unauthorised`——(a) `Context=""`（空 Context）；(b) 缺少 sender 字段（`participant_identity` / `device_id`）；(c) 仅绑定 `epoch_id` 而不含完整 sender-bound Context。

### 12.8 Participant Identity — Cross-Check

`vector_id`: `ak.vector.media_binding.participant_identity_unrecognised.v1`

Steps:

1. Backend signal `ParticipantConnected` with `participant_identity=ak:rtc_participant:<unknown>`，无对应 call roster effective OR-Set 项。

Expected:

- Client MUST 拒绝为该 participant 建立媒体流（不收音、不订阅 video），报 `participant_identity_unrecognised`。

### 12.9 Recording Artifact — Via Arkret Blob Pipeline

`vector_id`: `ak.vector.media_binding.recording_artifact_via_arkret_blob.v1`

Steps:

1. LiveKit Egress 配置指向非 Arkret endpoint（如 `s3://livekit-cloud-recordings/...`）。
2. Recording 完成。

Expected:

- Client MUST 检测 Egress destination 不是 Arkret media service authenticated upload endpoint，fail closed `recording_artifact_pipeline_bypassed`。
- 合法路径：Egress → Arkret blob upload → `ak.call.state` 写 `recording_transition.to="ready"` 及独立 result content digest。

### 12.9.1 Recording Exporter Label — Dedicated Recording Context

`vector_id`: `ak.vector.media_binding.recording_exporter_label.v1`

Steps:

1. LiveKit Egress 通过 Arkret proxy 上传合法 recording artifact。
2. Artifact encryption metadata 声称 key 来自 MLS exporter，但使用 SFrame label `"ak.rtc-frame-key/v1"` 或空 Context。
3. Producer 重新上传同一 artifact，使用 label `"ak.rtc-recording-key/v1"`，Context 为 canonical JSON `{realm_id, call_id, focus_id, recording_id, media_service_id, recording_start_event_id}`。

Expected:

- 第 2 步 MUST 拒绝；SFrame key 和 recording key 不得 label/Context 复用。
- 第 3 步 MAY accepted，前提是 Arkret blob pipeline、capability proof 与 `ak.call.state` lifecycle 绑定同时通过。

### 12.10 Call State — Participant Binding Invalid

`vector_id`: `ak.vector.call_state.participant_binding_invalid.v1`

Steps:

1. Producer 构造一个 schema 合法的 `ak.call.state` 事件（payload 通过 `call_state_payload` typed schema），其 `roster_delta.op="join"` 且 `roster_delta.participant.participant_binding` 含全部必填字段。
2. 依次构造四个变体，每个仅破坏 §11.1 reducer 校验中的一项：
   - (a) `participant_binding.issuer_kid` 解析到的 service DID 不在当前 epoch `ak.realm.media_service.service_id`；
   - (b) `participant_binding` 的 `realm_id` / `call_id` / `focus_id` / `actor_id` / `device_id` / `participant_identity` 中某一项与该 participant entry 不一致；
   - (c) `participant_binding.expires_at` ≤ 事件 `created_at`（已过期 binding）；
   - (d) `participant_binding.sig` 验签失败。
3. 各变体分别提交 reducer。

Expected:

- 每个变体 MUST `failed_precondition` `reason=participant_binding_invalid`；wire-level typed schema 通过不豁免 reducer 的语义校验。
- 反例（control）：四项全部满足时，同一事件 MUST accepted。

### 12.11 Call State — Initial State Gate

`vector_id`: `ak.vector.call_state.initial_state_accepts_allowed.v1`

Steps:

1. 对同一新 `call_id` 分别提交首条 `ak.call.state`，`state_transition` 为 `null -> scheduled`、`null -> ringing`、`null -> connecting`。
2. 对另两个新 `call_id` 分别提交首条 `ak.call.state`，`state_transition` 为 `null -> active` 与 `null -> ended`。

Expected:

- 前三条 MUST accepted，并各自建立 `ak.component.call.state.v1` 的初始 fsm cell。
- `active` 与任一终态作为首状态 MUST `failed_precondition`，`reason_code=call_state_transition_invalid`。

### 12.12 Call State — Transition Matrix

`vector_id`: `ak.vector.call_state.transition_matrix.v1`

Steps:

1. 以 `scheduled`、`ringing`、`connecting`、`active` 四个非终态为 `from`，逐条提交 [`call-state.md` §4.2](../crypto-media/call-state.md) 表中列出的合法后继。
2. 对每个非终态提交至少一个不在合法后继集合内的 `to`，例如 `scheduled -> active`、`ringing -> scheduled`、`connecting -> cancelled`、`active -> ringing`。

Expected:

- 表中每条合法边 MUST accepted，并推进同一 `call_id` 的 fsm cell。
- 非终态非法边 MUST `failed_precondition`，`reason_code=call_state_transition_invalid`；不得误报为 `call_state_terminal`。

### 12.13 Call State — Terminal Absorbing

`vector_id`: `ak.vector.call_state.terminal_absorbing.v1`

Steps:

1. 构造四个 call，使其 accepted head 分别为 `ended`、`missed`、`failed`、`cancelled`。
2. 分别尝试从这些终态提交任何其它 `state_transition.to`，包括另一个终态和非终态。

Expected:

- 每个终态转出 MUST `failed_precondition`，`reason=call_state_terminal`。
- reducer MUST 保留原终态 head，不得产生回退、替换或 winner。

### 12.14 Call State — Same Transition Replay

`vector_id`: `ak.vector.call_state.replay_same_state_noop.v1`

Steps:

1. 在同一 accepted basis 上提交 `ringing -> connecting`。
2. 以相同 `from`、相同 `to`、相同 `call_id` 重放等价转换（不同传输重试或 duplicate submit）。

Expected:

- 重放 MUST 是幂等 no-op：结果仍为 `connecting`，不产生 sibling conflict。
- 实现 MAY 返回 duplicate / accepted-noop 等本地结果，但 MUST NOT 返回 `call_state_transition_invalid`。

### 12.15 Call State — Concurrent Sibling Bottom

`vector_id`: `ak.vector.call_state.concurrent_sibling_bottom.v1`

Steps:

1. 同一 `call_id` 当前 accepted state 为 `ringing`。
2. 在同一 CBA basis 上并发提交 sibling transition A: `ringing -> active` 与 B: `ringing -> missed`。

Expected:

- `ak.component.call.state.v1` 的 `fsm` join MUST 返回 `Bottom{kind="conflict"}`，并按 `bottom=reject` 暴露 `failed_bottom` / diagnostic。
- 实现 MUST NOT 用 HLC、`created_at`、actor id、event id、event digest、数据库顺序或接收顺序选择 `active` 或 `missed` 作为 winner。
- 后续依赖该 call state 的写入 MUST fail closed，直到显式 recovery 在新的 accepted basis 上修复冲突。

### 12.16 Call State — Recording Retention & Audit Lock

`vector_id`: `ak.vector.call_state.recording_retention_lock.v1`

Steps:

1. Producer 提交 `ak.call.state`，`recording_transition.to="ready"`，其 `result.retention` 含 `retention_expires_at`（未来）、`deletion_trigger="retention_expiry"`、`audit_lock=true`。
2. 在 `retention_expires_at` 之前尝试删除 artifact。
3. 在 `retention_expires_at` 之后但 `audit_lock` 未解除时再次尝试删除。
4. 提交 `ak.call.recording.start`，其 `result.retention.consent_confirmed` 缺失或为 false；另尝试以 `ak.call.state.recording_transition.to="recording"` 绕过 start gate。

Expected:

- 第 2、3 步删除 MUST 被拒绝 `legal_hold_active`（audit_lock 优先于 TTL 与 capability）。
- 第 4 步 start MUST `failed_precondition` `reason_code=recording_consent_required`，绕过形态 MUST `schema_violation`。
- 反例（control）：`audit_lock=false` 且已过 `retention_expires_at`、`deletion_trigger=retention_expiry` 时删除 MAY accepted；start 的 result ref 等于本 Event `event_id` 且 `consent_confirmed=true` 时 FSM/result 两个 projected writes MUST 原子 accepted。

### 12.16.1 Call State — Recording Result Artifact Shape

`vector_id`: `ak.vector.call_state.recording_result_artifact_shape.v1`

Steps:

1. Producer 提交 `ak.call.state`，`recording_transition.to="ready"`，但 `recording_transition.result.artifact` 缺失。
2. Producer 提交 `recording_transition.result.artifact`，但其中 `schema` 不是 `ak.schema.call_recording_artifact.v1`，或 `recording_id` / `recording_start_event_id` 与 transition/result 绑定不一致。
3. Producer 提交 artifact，`encryption.exporter_label` 不是 `"ak.rtc-recording-key/v1"`，或 `encryption.context` 缺少 `{realm_id, call_id, focus_id, recording_id, media_service_id, recording_start_event_id}` 中任一字段。
4. Backend 尝试在 result / artifact 中携带直出 recording URL、S3/GCS/LiveKit Cloud destination，或缺失 `recording_initiator_capability_ref`。
5. Retention 到期或 manual delete 触发删除，artifact `deletion_audit.trigger` 与 `retention.deletion_trigger` 不一致，或 `outcome="completed"` 但缺少 `erasure_receipt_ref`。
6. Producer 提交合法 artifact：`schema="ak.schema.call_recording_artifact.v1"`，绑定同一 `realm_id` / `call_id` / `recording_id` / `recording_start_event_id`，通过 Arkret blob pipeline，使用 `"ak.rtc-recording-key/v1"` 与完整 Context，携带 retention、capability ref；删除完成时携带同 trigger 的 `deletion_audit` 与 `ak.schema.erasure_receipt.v1` 引用。

Expected:

- 第 1–5 步 MUST reject 或 fail closed；直出 URL / 外部 destination MUST 报 `recording_artifact_pipeline_bypassed`，artifact shape 或绑定不一致 MUST `schema_violation`。
- 第 5 步若 `audit_lock=true`，MUST 优先拒绝 `legal_hold_active`，不得因为 retention 到期或 manual capability 放行。
- 第 6 步 MAY accepted，前提是 Event Envelope、capability、blob metadata、artifact schema、exporter label/context 与 erasure receipt 绑定全部通过。

### 12.17 Call State — Transcribe Lifecycle & Key Source

`vector_id`: `ak.vector.call_state.transcribe_lifecycle.v1`

Steps:

1. 不具 `ak.call.transcribe` 的 actor 发起 `ak.call.recording.start{capture_kind="transcript"}`。
2. 具 `ak.call.transcribe` 的 actor 发起 transcript start，artifact 加密 key 声称来自 MLS exporter 但复用 SFrame label `"ak.rtc-frame-key/v1"` 或空 Context。
3. 同一 artifact 改用 label `"ak.rtc-transcript-key/v1"`、`Context=canonical_json({realm_id, call_id, focus_id, recording_id, media_service_id, transcript_start_event_id})` 重新上传，并通过 `ak.call.state` 写 `transcript_transition.to="ready"` 及独立 result。

Expected:

- 第 1 步 MUST 拒绝 `transcription_denied`。
- 第 2 步 MUST 拒绝 `transcription_artifact_pipeline_bypassed`；transcript key 不得与 SFrame / recording label 复用或空 Context。
- 第 3 步 MAY accepted，前提 Arkret blob pipeline、capability proof 与 `ak.call.state` lifecycle 绑定同时通过。

### 12.18 Call State — Moderator Kick / Ban

`vector_id`: `ak.vector.call_state.moderator_kick_ban.v1`

Steps:

1. 不具 `ak.call.moderate` 的 actor 发出 `ak.call.signal{signal_kind=moderation, action=kick}`。
2. 具 `ak.call.moderate` 的 moderator 对 `(target_actor_id, target_device_id)` 发 `kick`，并写 `ak.call.state.moderation_delta.op="remove_participant"`。
3. moderator 对某 `target_actor_id` 发 `ban`（`moderation_delta.removal` 省略 `device_id`）。
4. 被 ban 的 actor 重新向 token issuer 兑换 join token。

Expected:

- 第 1 步 MUST 拒绝 `call_moderation_unauthorised`。
- 第 2 步被 kick 设备 MUST 拆除媒体；token issuer / SFU 据 moderation effective OR-Set 拒绝其重接 `call_participant_removed`，但同 actor 重新发起新 join 不受阻。
- 第 4 步 token issuer MUST 拒绝 `call_participant_removed`，直到 ban 在本通话生命周期内被解除。

### 12.19 Call State — P2P→SFU Upgrade & Summary Gate

`vector_id`: `ak.vector.call_state.p2p_to_sfu_upgrade.v1`

Steps:

1. 以 `mode="p2p"` 起步的两人通话，第三个参与者将加入（active leg 达到 3）。
2. 触发升级：按 media-service-binding §5 oldest_membership 选举 `session_focus`，各设备经 `ak.call.signal{signal_kind=focus_join}` 迁移。
3. 升级后提交 `ak.call.state.focus={mode:"sfu",session_focus}`，随后人数回落到 2。
4. 通话到达终态 `ended` 后提交 `ak.call.summary{final_state="ended"}`；另对一个尚处 `active` 的 call 提交 `ak.call.summary`。

Expected:

- 第 1 步 MUST 触发升级，不得以 P2P / mesh 承载 3 人以上。
- 第 2 步 `session_focus` 由 oldest_membership 的 `foci_preferred[0]` 确定，无投票路径；committed 后 write-once。
- 第 3 步 `mode` MUST NOT 在同一生命周期内自动降级回 `p2p`。
- 第 4 步对终态 call 的 summary MUST accepted（write-once cell）；对 `active` call 的 summary MUST `failed_precondition` `reason_code=call_summary_invalid`。

## 13. History Visibility / Preview / History Sharing

### 13.1 Joined Visibility Denies Pre-Join History

`vector_id`: `ak.vector.history_visibility.joined_prejoin_denied.v1`

Setup:

1. Realm R 在 `T0` 的 effective `ak.realm.history_visibility.value = "joined"`。
2. Alice 是 active member 并提交 message `E_before`。
3. Bob 在后续 Seal `J` 才通过 `ak.member.state{membership=join}` 加入。
4. Bob 调用 backfill，范围覆盖 `E_before`。

Expected:

- Events / Sync Service MUST NOT 返回 `E_before` 的正文 payload 给 Bob；可以返回 redacted / locked stub 或 `history_not_visible`。
- E2EE Realm 中，任何 `ak.realm_key.share` 覆盖 `E_before` epoch 且 recipient=Bob MUST 被拒绝或对应 `ak.realm_key.withheld{withheld_reason_code="history_not_visible"}`。
- 如果 Realm 后续把 current visibility 改成 `shared`，该变化不 retroactively 重解释 `E_before` 的 `T0` 可见性；除非新 policy 明确声明受审计的 historical reclassification profile，否则 Bob 仍不能把 `E_before` 作为 verified timeline 明文展示。

### 13.2 Preview Token Is Stripped-State Only Unless Policy Allows More

`vector_id`: `ak.vector.preview.token_scoped_stripped_state.v1`

Setup:

1. Realm R 的 discoverability 为 `invite_only`，但 Alice 给 Bob 发出 `lt=preview` token。token payload 绑定 `target_digest`、`address_link_kind="preview"`、`preview_policy_digest`、`aud=Bob`、短 TTL。
2. Effective `ak.realm.preview_policy.value.mode = "stripped_state"`，fields 只包含 `title`、`summary`、`join_rule`、`member_count_bucket`。
3. Bob 调用 `ak.find.directory.query.resolve_target`，携带 address 与 token。
4. 攻击者 Mallory 把同一 token 放到另一个 Strand address，或把 URL `lt` 改为 `invite`。

Expected:

- Bob MAY 收到 `realm_preview` / `object_preview` 中 policy 允许的 stripped fields。
- 响应 MUST NOT 包含正文历史、成员列表、policy 原文、`join_candidates[]` 或任何 write / membership grant。
- Mallory 的 scope-confused request MUST 返回与不存在不可区分的 `not_found`；resolver MUST 比对 token 内 `target_digest` 与 effective `address_link_kind`，不得只校验 token 签名。

### 13.3 E2EE Pre-Join Key Share Requires History Sharing Policy

`vector_id`: `ak.vector.history_sharing.e2ee_prejoin_key_share_policy.v1`

Setup:

1. Realm R 为 `encryption_profile="mls_rfc9420"`、`content_scheme="mls_exporter_aead_v1"`，`history_visibility.value = "shared"`。
2. Alice 在 epoch 7 发送 `E_before`。
3. Bob 在 epoch 9 加入并成功处理 Welcome。
4. Key source S 尝试向 Bob 发送覆盖 epoch 7 的 `ak.realm_key.share`。

Expected:

- 若 effective `ak.realm.history_sharing_policy` 缺失，或 `pre_join_history="deny"` / `rule_only` 且无匹配 rule，S MUST withhold，reason SHOULD 为 `history_not_visible` 或 `policy_denied`。
- 若 policy 明确允许 `pre_join_history="visibility_condition_allowed"`、`allowed_key_sources` 包含 S 的来源类型、receiver state 合法且 audit 要求满足，S MAY 发送 key share；payload `key_scope.policy_digest` MUST 覆盖该 policy root，`membership_frontier_digest` SHOULD 覆盖 Bob join frontier。
- Bob 客户端 MUST NOT 因 `history_visibility=shared` 自行推断 epoch 7 key；没有合法 key share 时，`E_before` 保持 `decryption_pending` / `decryption_failed`。
- 若 Realm R 的 epoch 7 effective `content_scheme="mls_rfc9420"`，S MUST NOT 为 join 前内容发送可用 key share；该 epoch 不存在可交付给后加入者的 `history_secret`。

## 14. Encryption Floor Ratchet Vectors

加密能力轴（`encryption_profile`）与加密下限（`content_encryption_floor` / `metadata_encryption_floor`）分离；两个 floor 均二元（比较序 `allow_plaintext < e2ee_required`）、Realm 与 Circle 对称，且 effective floor 是单向 ratchet。本节固化 reducer 权威层的四个向量（完整语义见 [`../models/circle.md` §7](../models/circle.md)、[`../models/realm-and-space.md` §2.5](../models/realm-and-space.md)）。

### 14.1 Content Floor Downgrade Rejected

`vector_id`: `ak.vector.e2ee.content_floor_downgrade_rejected.v1`

Setup:

1. Realm R 的 effective `content_encryption_floor` 已达 `e2ee_required`(经 `ak.realm.policy_bundle` 写入)。
2. 后续 `ak.realm.policy_bundle` 把 `content_encryption_floor` 改回 `allow_plaintext`。

Expected:

- reducer MUST `failed_precondition`，reason=`content_encryption_floor_downgrade`。
- 抬高（`allow_plaintext` → `e2ee_required`）或维持同级 MUST 接受；只有降级被拒。

### 14.2 Metadata Floor Downgrade Rejected

`vector_id`: `ak.vector.e2ee.metadata_floor_downgrade_rejected.v1`

Setup:

1. Realm R 的 effective `metadata_encryption_floor` 已达 `e2ee_required`。
2. 后续 `ak.realm.policy_bundle` 把 `metadata_encryption_floor` 改回 `allow_plaintext`。

Expected:

- reducer MUST `failed_precondition`，reason=`metadata_encryption_floor_downgrade`。
- 与 content floor 同为单向 ratchet；抬高或同级接受，降级被拒。

### 14.3 In-Place E2EE Enable

`vector_id`: `ak.vector.e2ee.in_place_enable.v1`

Setup:

1. Realm R 以 `encryption_profile="mls_rfc9420"` + `content_encryption_floor="allow_plaintext"` 创建（钥匙在手、初期明文发送）。
2. 后续 `ak.realm.policy_bundle` 把 `content_encryption_floor` 抬到 `e2ee_required`。

Expected:

- reducer MUST 接受该原地升级（正向向量），无需重建 Realm 或 MLS group。
- 升级生效后，plaintext content 写入 MUST `failed_precondition`（reason=`content_encryption_floor_violation`），且 MLS governance send-pause 恢复完整约束。

### 14.4 Circle Content Floor Below Realm Rejected

`vector_id`: `ak.vector.circle.content_floor_below_realm_rejected.v1`

Setup:

1. 父 Realm 的 effective `content_encryption_floor` 为 `e2ee_required`（或 `encryption_profile="mls_rfc9420"`）。
2. `ak.circle.create` / `ak.circle.update` 声明 `encryption_profile="none"`，或 Circle `content_encryption_floor` 低于父 Realm effective floor。

Expected:

- reducer MUST `failed_precondition`，reason=`circle_encryption_below_realm_floor`。
- Circle floor 只能在父 Realm floor 之上收紧；`none` scope 无 MLS-backed effective_scope 可承载密文，故不得声明 `e2ee_required`。

## 15. Moderation / Policy Server / Key Backup / Federation Ingress Vectors

本节收拢治理域（content moderation、policy server、key backup）与 federation ingress 的 conformance 向量。每个 `vector_id` 均为规范性引用目标，登记于 [`vector-registry.json`](../../artifacts/registry/vector-registry.json)。

### 15.1 Vector: E2EE Franking Roundtrip

`vector_id`: `ak.vector.moderation.franking_roundtrip.v1`

本向量固化 [`content-moderation.md`](../governance/content-moderation.md) §3.4 的 franking 构造与验证 MUST：franking proof “MUST 在 canonical event routing metadata、ciphertext digest、AAD digest、sender claim、receiving service DID、接收时间与 `replay_nonce` 之上生成”；moderator 验证时 “MUST 检查 reporter 可见性、目标消息 accepted state、encrypted envelope digest、franking service signature、AAD / ciphertext digest 和 evidence package 签名”。

Steps：

- **Case A — roundtrip 正路径**：
  1. E2EE Realm 中 sender 发送密文消息；receiving service 按 §3.4 生成 `ak.moderation.franking_proof`（含 `routing_metadata_digest`、`ciphertext_digest`、`aad_digest`、`sender_claim`（仅 `mls_group_id_digest`，无 raw `mls_group_id` / 明文 `epoch`）、`received_by`、`received_at`、`replay_nonce`、`signature`，并通过 [`moderation-report.schema.json`](../../artifacts/schemas/moderation-report.schema.json) `franking_proof` 分支）。
  2. reporter 提交 `ak.self.moderation.command.report`，附加密 evidence package（加密给 `effective_scope` 对应 moderator audience）与该 `franking_proof`。
  3. moderator 按 §3.4.1 “Franking 信任链” 步骤 1–6 验证（receiving service DID 解析、verification method 在 `received_at` 有效且未撤销、service 在目标 Realm 被授权、payload hash 覆盖完整、`received_at` 时序新鲜度）。
- **Case B — 篡改 / 最小披露违反**：(a) `franking_proof.ciphertext_digest` 与目标 encrypted envelope digest 不一致；(b) `sender_claim` 携带 raw `mls_group_id` 或明文整数 `epoch`，或 proof 包含 plaintext body。

Expected：

- **Case A**：全部校验通过后，moderator MAY 把 `franking_proof` 视为可验证投递证明；evidence package MUST NOT 包含 Realm / Circle 历史 key、MLS epoch secret、exporter secret 或允许 moderator 解密未举报消息的材料；举报 MUST NOT 触发任何治理密钥释放（§3.4.1：MUST NOT 把 `ak.self.moderation.command.report` 自动升级为 `ak.audit.session.request`）。
- **Case B(a)**：任一 digest 环节不符时，moderator MAY 把材料作为人工线索，但 MUST NOT 将该 `franking_proof` 视为可验证投递证明。
- **Case B(b)**：schema / receiver MUST 拒绝携带 raw `mls_group_id`、明文 `epoch` 或 plaintext body 的 `franking_proof`（§3.4 最小披露 MUST NOT 条款）。

### 15.1.1 Vector: Moderation Evidence Package Minimal Disclosure

`vector_id`: `ak.vector.moderation.evidence_package_minimal_disclosure.v1`

本向量固化 [`content-moderation.md`](../governance/content-moderation.md) §3.4 的 evidence package 最小披露闭包：evidence package MUST 加密给 `effective_scope` 对应 moderator audience，MUST 只包含 reporter 可见且愿意提交的目标证据，MUST NOT 包含 Realm / Circle 历史 key、MLS epoch secret、exporter secret 或允许 moderator 解密未举报消息的材料。

### 15.2 Vector: Moderation Appeal 状态转换原子性

`vector_id`: `ak.vector.moderation.appeal_atomicity.v1`

本向量固化 [`content-moderation.md`](../governance/content-moderation.md) §5.5.2 的 reducer 强制约束：“`ak.moderation.appeal.decision` `verdict=overturn` MUST 与一条 `ak.moderation.decision.lift`（target 等于 `decision_ref`）在同一 ordered submit batch 或同一 control transaction 中出现；否则 reducer 用 `appeal_overturn_missing_lift` 拒绝”；“`verdict=modify` MUST 在同一 batch 同时 lift 原 decision 并新增 `modify_decision_ref` 指向的 replacement decision”。该向量同时固定 overturn 不复活不可逆 redaction tombstone / 已销毁 key 的边界。

Steps（前置：appeal cell 已沿 §5.5.1 状态机 `submitted → under_review` 推进，reviewer ≠ 原 decision issuer）：

- **Case A — overturn 缺 lift / 正常 overturn**：reviewer 提交 `verdict=overturn` 的 `ak.moderation.appeal.decision`，但同一 ordered submit batch / control transaction 中**不**含 target 等于 `decision_ref` 的 `ak.moderation.decision.lift`；随后在另一次提交中补齐同 batch 的 decision + lift 对。原 decision 已触发 redaction tombstone 的变体也包含在内。
- **Case B — modify 原子替换失败**：reviewer 提交 `verdict=modify` 的 decision，但缺少原 decision lift，或 `modify_decision_ref` 指向的事件不在同一 batch，或同 batch新 `ak.moderation.decision` 的 `target_ref` 不等于原 target。
- **Case C — modify 正路径**：同一 batch 含 appeal decision、指向原 `decision_ref` 的 lift、以及 `modify_decision_ref` 指向且 target 相同的新 moderation decision。

Expected：

- **Case A**：缺 lift 的提交 MUST 被 reducer 以 `appeal_overturn_missing_lift` 拒绝，appeal cell 保持 `under_review`，原 moderation decision 继续生效（不存在“上诉胜诉但原 decision 仍生效”的中间窗口，反向亦然）；补齐后的同 batch decision + lift MUST 原子接受，cell 转入 `decided` 且原 decision 解除。若原 decision 已触发 redaction，tombstone 与 audit fact MUST 保留，原文 / key MUST NOT 被复活。
- **Case B**：MUST 拒绝整个 modify 提交；缺 lift时 reason=`appeal_modify_missing_lift`。不得出现“appeal 已 `decided` 但旧 decision 未 lift / 新 decision 缺失 / 指向错误”的部分状态。
- **Case C**：三件套 MUST 原子接受；旧 decision inactive，replacement active，appeal cell 进入 `decided`。
- 所有 case 中 cell 状态机 MUST 遵循 §5.5.1 转换表（`submitted → under_review → decided → closed`）；跳跃转换 MUST `failed_precondition`。

### 15.2.1 Vector: Moderation Review Resolution 与多 Decision Fold

`vector_id`: `ak.vector.moderation.review_resolution_fold.v1`

本向量固化 [`content-moderation.md`](../governance/content-moderation.md) §2.6 与 [`policy-server.md`](../authz/policy-server.md) §7.1：active moderation decisions 是可 join 的 OR-Set，普通多 entry 必须按 `hard_deny > quarantine > require_review > none` 取最严格 effective verdict；active `require_review` add 是 pending-review 的 canonical carrier，解除必须原子 lift 全部适用 review gates，并在 allow 路径重新执行当前 authz。

Cases / Expected：

- 两条来自不同 issuer 的 active `require_review` add MUST 收敛为 effective `require_review`，不得报 split；同时存在 `quarantine` 时 effective MUST 为 `quarantine`。
- allow resolution 必须在同一 batch lift 本次 gate 的全部 active review decisions；只 lift 部分 MUST 原子拒绝并保持 pending。全部 lift 后候选仍不得自动接受，MUST 重跑当前 capability / policy / membership / quota。
- hard-deny / quarantine resolution 必须把 review lifts 与 replacement decision 原子提交；不得留下“review 已解除但 replacement 未写入”的窗口。
- 只有同一 add identity 对应不同 canonical bytes、remove provenance 不可验证等真正非 joinable 状态才返回 `moderation_control_split` / `moderation_state_conflict`。

### 15.3 Vector: Policy Decision 重放拒绝

`vector_id`: `ak.vector.policy_server.decision_replay_rejected.v1`

本向量固化 [`policy-server.md`](../authz/policy-server.md) §5 的反重放 / freshness MUST：“节点 MUST 拒绝过期 decision”；frontier 比较中“若本地 accepted authorization / policy / membership frontier 严格晚于 decision 绑定的 frontier……receiver MUST fail closed 并重新请求 `/_arkret/self/policy/check`；不得把旧 decision 复用到更新后的 auth state”。

Steps：

- **Case A — 过期 decision 重放**：一份签名有效的 allow decision 在 `expires_at` 之后被原样重放给 receiver。
- **Case B — auth state 前进后复用**：decision 签发后，本地 accepted auth state 观察到相关 grant revoke / membership 变化（`auth_state_digest` 与 decision 绑定值不再一致，且本地 frontier 严格晚于 decision frontier）；调用方尝试复用缓存中的该 decision（cache key 含 `auth_state_digest` 五元组，见 §5）。

Expected：

- **Case A**：receiver MUST 拒绝（`expires_at > now` 校验失败），不得以任何 TTL 宽限接受。
- **Case B**：cache hit 时 `auth_state_digest` constant-time 比较不一致 MUST 回退完整授权判定；本地 frontier 严格晚于 decision frontier 时 MUST fail closed 并重新请求 policy check，MUST NOT 把旧 allow decision 复用到更新后的 auth state。
- 两个 case 的拒绝 MUST NOT 推进任何依赖该 decision 的写入。

### 15.4 Vector: Request Canonical Digest 重算不符拒绝

`vector_id`: `ak.vector.policy_server.request_digest_recompute.v1`

本向量固化 [`policy-server.md`](../authz/policy-server.md) §5 的 transcript 绑定 MUST：“`request_canonical_digest` MUST 是 RFC 8785 JCS 在该请求 body 上的 SHA-256 digest”；接收方 MUST 校验 “`bound_to` 必须存在，且 `bound_to.realm_id` / `bound_to.actor_id` / `bound_to.action` / `bound_to.request_canonical_digest` 与本次 request 完全一致”。

Steps：

- **Case A — digest 不符**：调用方拿到一份对请求 body `B1` 签发的 decision（`bound_to.request_canonical_digest = JCS-SHA256(B1)`），将其附在内容已被修改的请求 body `B2` 上提交；receiver 对 `B2` 重算 JCS canonical digest。
- **Case B — control 正路径**：decision 的 `bound_to` 四元组与本次 request 重算结果完全一致，signature / `expires_at` / frontier 校验全部通过。

Expected：

- **Case A**：重算 digest ≠ `bound_to.request_canonical_digest`，receiver MUST 拒绝该 decision，不得信任 decision 自带的 digest 字段而跳过本地重算；按 service-private 算法（非 JCS）计算 canonical hash 的实现 MUST NOT 声明通过 v1 conformance。
- **Case B**：decision 接受（对照正样本）。
- `bound_to.realm_id` / `actor_id` / `action` 任一与本次 request 不一致时同样 MUST 拒绝（防止 allow decision 跨 (realm, actor) 上下文泄漏）。

### 15.4.1 Vector: Realm Policy Server 持久删除与重复删除

`vector_id`: `ak.vector.policy_server.binding_tombstone.v1`

本向量固定 [`policy-server.md`](../authz/policy-server.md) §2.2 的 DELETE 映射。具备
`ak.policy.manage` 的 actor 删除一个有 direct declaration、同时通过 `governed_by` 可继承
组织声明的 Realm；receiver 必须从 DELETE 构造 payload 精确为 `{"tombstone":true}` 的
`ak.realm.policy_server` Control Move，并将 `set(value=payload, from=<被删除的完整
declaration>)` 纳入 Seal 与 `state_root`（`from` 由 projector 按
[`event-auth-state-resolution.md` §9.3.1](../authz/event-auth-state-resolution.md) 从
whole-value `head_eq` 复制，declaration → tombstone 因此按取代链 join 到 tombstone）。

Expected：

- Seal 接受前 effective state 不变；接受后 direct cell 的 settled value 是显式 tombstone，
  GET 返回组织声明并标记 `from_org_fallback=true`；
- 对 settled tombstone 重复 DELETE 返回幂等空成功，cell value 与 `state_root` 不变；
- 从未有 direct declaration / tombstone 时 DELETE 返回 `not_found`；仅继承到的配置不构成
  direct declaration，删除不得改写祖先 Realm cell；
- tombstone payload 必须精确为 `{"tombstone":true}`；`tombstone=false`、`null`、空 object 或
  与任一 declaration 字段混合都必须在 reducer 前以 `schema_violation` 拒绝；
- 缺 `ak.policy.manage` 时必须在构造 / 接受 Control Move 前拒绝，不能先写 tombstone 再补审计。

### 15.4.2 Vector: Realm Policy Server Replace/Delete 并发

`vector_id`: `ak.vector.policy_server.replace_delete_conflict.v1`

从同一 frozen declaration head 分别构造一个 replacement 与一个 tombstone sibling；两者都带
命中旧完整 value 的 `head_eq`，并被同一 predecessor view 的并发 Seal 分支接受。

Expected：不同 `set` value 的 `cas_register` join 为 `⊥`、`bottom=reject`；GET、Policy Server
调用和依赖该 cell 的写入均 `failed_bottom`。实现不得按 HLC / 到达顺序选择 replacement 或
tombstone，也不得在本级 `⊥` 时跳过到组织 fallback。仅 `ak.state.conflict_recovery` 可恢复。

### 15.4.3 Vector: Realm Policy Server Tombstone 联邦回放与 Seal

`vector_id`: `ak.vector.policy_server.tombstone_federation_replay.v1`

对端分别按 Event→Seal、Seal→Event、含 Event / Seal 重复的顺序接收同一 tombstone。依赖未齐时
保持 pending；Event、Seal 与 predecessor 全部可用后，receiver 必须从 registry 重算
`ak.component.realm.policy_server.v1:null` 的 `set({"tombstone":true})`。

Expected：全部顺序收敛为相同 cell value 与 `state_root`；重复传输幂等；Event 保留在 canonical
log 并参与后续 federation / snapshot；重启回放或从 sealed cell store hydrate 后 direct config
仍为 tombstone，不得因结构化缓存重建遗漏而复活。
### 15.5 Vector: Key Backup Unlock Proof 校验

`vector_id`: `ak.vector.key_backup.unlock_proof.v1`

本向量固化 [`key-management.md`](../identity/key-management.md) §7.7.1 / §7.8 的取回校验 MUST：取回完整 ciphertext 的协议操作是 `ak.self.keys.backups.command.unlock`（`POST /_arkret/self/keys/backups/{backup_id}/unlock`），unlock proof MUST 作为 request body 的 `proof` 字段提交；“服务端在返回完整 ciphertext 之前，MUST 校验该 unlock proof 与请求 session、caller、新设备 key、active-series record 和目标 envelope 一致；任一不符 MUST fail closed”；“`POST /_arkret/self/keys/backups/{backup_id}/unlock` 即便对自己的备份也 MUST 要求 fresh device proof……bearer token 单独到达 MUST 被拒绝”。

Steps：

- **Case A — 正路径**：恢复设备在 recovery session 内提交符合 `ak.schema.key_backup_unlock_proof.v1` 的 proof（绑定 `recovery_session_id`、`principal_id`、`requesting_device_id`、`backup_id`、`backup_kind`、`series_id`、`ciphertext_digest`、`proof_kind`、`proof_digest`、`issued_at`），服务端用当前 session state 重建 transcript 比对 `proof_digest` 后返回 ciphertext；客户端按机器 fixture `key-backup-hardening-fixture.json` 的 `crypto_transcript` 重算 AEAD open（`aead` / `key_b64u` / `nonce_b64u` / `aad_canonical_json` / `ciphertext_b64u` / `tag_b64u`），校验得到的明文符合 `ak.schema.key_backup_plaintext.v1`，且 `backup_id` / `backup_kind` / `series_id` / `series_seq` byte-for-byte 等于外层 envelope。HPKE recipient 的端到端 transcript 由 HPKE suite 向量覆盖；本向量的机器正样本使用对称 AEAD transcript 固化 unlock proof 与 envelope / plaintext 绑定。
- **Case B — 绑定不符 / 凭证降级**：(a) proof 的 `ciphertext_digest` 指向另一 envelope，或 `requesting_device_id` 与本次 session 的新设备 key 不一致，或 `proof_digest` 与服务端重建的 transcript 不符；(b) 调用方仅携带 bearer token、无 fresh device proof 请求同一端点。

Expected：

- **Case A**：ciphertext 返回且明文校验通过；`items[].secret_id` / `item_kind` 只作 keybag 内部路由，不得替代外层 envelope 的授权判断；明文 MUST 仅作本地瞬时材料，日志 / telemetry MUST NOT 记录 `secret_b64u`。
- **Case B(a)**：MUST fail closed，错误码取 `recovery_evidence_unbound` / `backup_frontier_stale` / `series_chain_broken` / `invalid_signature` 中对应稳定码；服务端 MUST NOT 采信客户端自报的 policy / session metadata。
- **Case B(b)**：MUST 拒绝；跨 actor 请求（envelope `actor_id` ≠ caller）MUST 返回 `forbidden` 且不得通过 metadata 暴露 envelope 是否存在。

### 15.6 Vector: KDF 下限不满足的新建 Envelope 拒绝

`vector_id`: `ak.vector.key_backup.kdf_floor_rejected.v1`

本向量固化 [`key-management.md`](../identity/key-management.md) §7.2 的 base 无条件 MUST 下限：“新创建的 `recipient_method="passphrase_kdf"` envelope MUST 满足以下机器下限（base v1 无条件要求……）：Argon2id `memory_kib >= 65536`、`iterations >= 3`、`parallelism >= 1`”；“如果平台限制只能使用 PBKDF2，新创建的 PBKDF2 envelope MUST 满足 `iterations >= 600000` 且 `digest_algorithm ∈ {sha256, sha384, sha512}`，并 MUST 在 backup metadata 中声明 `degraded_profile_reason`”。

Steps：

- **Case A — Argon2id 低于下限**：新建 `passphrase_kdf` envelope 声明 Argon2id `memory_kib = 32768`（或 `iterations = 2`、`parallelism = 0`）。
- **Case B — PBKDF2 低于下限 / 非法字段**：新建 PBKDF2 envelope 声明 `iterations = 310000`，或 `digest_algorithm` 不在 `{sha256, sha384, sha512}`，或使用非法字段 `params.hash` 代替 `params.digest_algorithm`。

Expected：

- **Case A / Case B**：receiver / 上传端点 MUST 拒绝该新建 envelope（schema 与 §7.2 机器下限同步编码于 `ak.schema.key_backup.v1`）；`params.hash` MUST 被 current parser reject。
- 对照正样本：Argon2id `memory_kib >= 65536` 且 `iterations >= 3` 且 `parallelism >= 1` 的 envelope，以及 `iterations >= 600000`、合法 `digest_algorithm` 且声明 `degraded_profile_reason` 的 PBKDF2 envelope MUST accept。
- Argon2id 可用时新建 envelope MUST NOT 默认选择 PBKDF2；未知 `encryption.kdf.name` MUST fail closed，不得回退到默认。

### 15.6.1 Vector: Passphrase KDF → AEAD 端到端 KAT

`vector_id`: `ak.vector.key_backup.passphrase_kdf_kat.v1`（来源：`key-backup-hardening-fixture.json` `passphrase_kdf_kat` case）

本向量固化 [`key-management.md`](../identity/key-management.md) §7.2 passphrase_kdf 路径的端到端字节链：Argon2id（固定参数 + 固定盐）→ HKDF-SHA256 子密钥（aead / nonce / commitment，per-backup_kind 域分隔）→ canonical nonce transcript 的确定性 XChaCha20-Poly1305 nonce → ciphertext、`ciphertext_digest` 与 `key_commitment`。这是跨设备 / 跨实现解锁互操作的生死线：任一中间值漂移都会造成"备份永远解不开"。

Steps：按 `kat_cases` 的 input（passphrase、Argon2id 参数与盐、binding、nonce_salt、明文）逐级派生，与 intermediate（root key、三个 HKDF 子密钥、canonical nonce transcript、AAD）及 expected（nonce、ciphertext、digest、commitment）比对。

Expected：所有中间值与输出 MUST byte-for-byte 复现；固定盐 / 参数仅限测试向量，生产实现 MUST 使用新鲜随机盐。

### 15.7 Vector: Federation Ingress 鉴权失败 Timing Bucket

`vector_id`: `ak.vector.federation.timing_bucket.v1`

本向量固化 federation ingress 鉴权失败族的响应不可区分性（[`federation.md`](../sync/federation.md) §3.2），采样口径按 [`relation.md`](../models/relation.md) §4.5 既有口径执行。

Steps：

1. 对同一 federation ingress endpoint（如 `POST /_arkret/peer/events`）分别触发鉴权失败族中的不同原因：(a) 未知 peer（`Source-Service-ID` 无法解析 / 不在任何 binding 中）；(b) 签名可解析但 source 未被目标 Realm policy / 本地 peer policy 授权；(c) 目标 Realm 或资源不存在。
2. 在同一服务端测量点、同一请求类别与同一部署 profile 下，对每类失败至少采样 30 次，记录 HTTP status、`reason_code`、响应字段集合与服务端处理时延（网络传输时间不计入服务端本地口径）。

Expected：

- 三类失败的对外响应 MUST 使用同一 HTTP status 与同一统一鉴权失败 `reason_code`（`error-code-registry` 已登记的统一码，如 `capability_denied`），error envelope 可见字段集合 MUST 相同，MUST NOT 携带 Realm / Actor / Event / binding / frontier 是否存在的任何可区分信息；真实失败原因 MUST 只写入接收方审计日志。
- timing 同桶判定按 [`relation.md`](../models/relation.md) §4.5 口径：每类 ≥ 30 次采样下，各失败类别两两之间 p95 处理时延差异 SHOULD ≤ 50ms；声明高安全 profile 时 MUST 使用 padding / jitter 使 p99 也落入同一 timing bucket。
- conformance runner MAY 在同一网络条件下补充端到端抽样，但判定以服务端本地口径为准。

失败条件：

- 任两类失败返回不同 status / `reason_code` / 字段集合，或错误 body 泄露目标是否存在。
- p95（或高安全 profile 下 p99）超出同桶判定，形成可观测的存在性 timing 侧信道。

### 15.8 Vector: Federation Reducer Profile Digest 计算与不一致拒绝

`vector_id`: `ak.vector.federation.reducer_profile_digest.v1`

本向量固化 [`federation.md`](../sync/federation.md) §4.1.1 的内容寻址 `service_binding_ref.reducer_profile_digest` 计算规则与不一致时的整批拒绝语义。计算物是从本地 profile 声明、event-kind row、schema、fixture 语义投影及 reducer contract 实际内容独立重建的 `resolved_digest_input`；canonical 编码按 [`encoding.md`](encoding.md) §2。执行数据见 [`federation-fixture.json`](../../artifacts/fixtures/federation-fixture.json) 的两个 case。

Steps：

- **Case A — 计算与内容变异**：按 `resolved_digest_input_source` 从本地契约重建 `ak.profile.federation_minimal.v1` 的闭包，计算 `"sha256:" || lowercase_hex(sha256(canonical_json(resolved_digest_input)))`。随后逐项执行 `mutation_cases[]`：改变 required event-kind row 摘要或 required schema 文档摘要 MUST 改变结果；只改变对象插入顺序 MUST 不改变结果。
- **Case B — 不一致整批拒绝**：按 fixture case `reducer_profile_mismatch` 构造 `POST /_arkret/peer/events` 批次，sender 声明的 `service_binding_ref.reducer_profile_digest` 与 receiver 对同一 Realm 重算结果不一致。

Expected：

- **Case A**：实现重算结果 MUST 等于 fixture 的 `expected_digest`；内容变异与 key-order 变异结果 MUST 分别符合 fixture。只摘要 `digest_input` 名称/路径列表即判失败。摘要字面量只在机器 fixture 与生成 registry 中维护，prose 不复制生成值。
- **Case B**：receiver MUST 整批拒绝并返回 `reducer_profile_mismatch`，MUST NOT partial accept；缺少 registry row、`profile_id` 未声明、canonicalization 不支持或 digest suite 非 active `sha256` 时同样 MUST fail closed。

失败条件：

- Case A 重算值与 `expected_digest` 不符，内容变异未改变摘要、key-order 变异改变摘要，或实现未从本地契约内容独立重建闭包。
- Case B 出现 partial accept，或拒绝时返回 `reducer_profile_mismatch` 之外的可区分错误形态。

## 16. Streaming Chunked AEAD Attachment Vectors

本节收拢分块流式 AEAD 加密附件 scheme `ak.blob.stream_aead.v1` 的 conformance 向量，固化 [`media-and-blob.md`](../crypto-media/media-and-blob.md) §3.2 形态选择与 §3.3 的分块构造 / nonce / AAD / 整体 digest / 解密验证 MUST。每个 `vector_id` 均为规范性引用目标，登记于 [`vector-registry.json`](../../artifacts/registry/vector-registry.json)；error envelope `reason_code` 取 [`error-code-registry.json`](../../artifacts/registry/error-code-registry.json) 已登记的稳定码。

### 16.1 Vector: Streaming AEAD Roundtrip

`vector_id`: `ak.vector.blob.stream_aead_roundtrip.v1`

本向量固化 [`media-and-blob.md` §3.3.1](../crypto-media/media-and-blob.md) 切分、同文 §3.3.2 nonce 构造、§3.3.3 AAD 绑定、§3.3.5 整体 `ciphertext_digest` 语义与 §3.3.6 解密验证的正路径：明文按 `segment_bytes` 切成有序 segment（末段长度在 `1 .. segment_bytes`，可短于 `segment_bytes`），逐段独立 AEAD 加密、可分段下载并逐段增量校验，最终整体 `ciphertext_digest` 重算比对通过。

Steps：

1. 取一份明文，长度使 `segment_count == ceil(plaintext_size / segment_bytes)` 且末段严格短于 `segment_bytes`（含短末段路径）；envelope 走 [`blob.schema.json#/$defs/encrypted_attachment`](../../artifacts/schemas/blob.schema.json) 的 `ak.blob.stream_aead.v1` 分支，声明 `scheme`、`nonce_prefix`（per-object 随机，长度 `N_AEAD - 5`）、`segment_bytes`、`segment_count`、`ciphertext_digest`。
2. 对每个 segment 用同一 content key、nonce = `nonce_prefix || u32_be(segment_index) || last_segment_flag` 加密，并把 `segment_index` / `last_segment_flag`（及 `media-and-blob.md` §3.3.3 要求字段）纳入 AAD；末段 `last_segment_flag = 0x01` 且 `segment_index == segment_count - 1`。
3. 接收方按 `segment_index` 从 `0` 起严格升序分段下载（SHOULD 按 `segment_bytes` 整数倍偏移做 Range），逐段做 per-segment AEAD tag 校验并安全释放对应明文。
4. 全部 segment 接收完毕后，按 `media-and-blob.md` §3.3.5 对全部 segment 密文（每段含其 AEAD tag）按 `segment_index` 升序拼接重算 `ciphertext_digest`，与 envelope 声明值比对。

Expected：

- 逐段 AEAD tag 校验全部通过，整体 `ciphertext_digest` 重算等于 envelope 声明值；接收方还原出 byte-for-byte 等于原明文的内容，并仅在见到合法末段（`last_segment_flag=0x01` 且 `segment_index==segment_count-1`）后才标记附件完整。
- per-segment 增量校验提供边下边验，顶层 `ciphertext_digest` 提供整体完整性；二者都 MUST 校验通过才允许最终持久化 / 标记完整。
- 反例（顺带覆盖）：将任一 segment 密文整体替换为另一份相同 segment_index 的合法密文，使 per-segment tag 仍可能通过但拼接后整体 digest 不符时，`media-and-blob.md` §3.3.6 步骤 7 MUST 以 `digest_mismatch`（与该文 §5 一致）拒绝、丢弃全部明文、不渲染不持久化。

### 16.2 Vector: Streaming AEAD Truncation Rejected

`vector_id`: `ak.vector.blob.stream_aead_truncation_rejected.v1`

本向量固化 `media-and-blob.md` §3.3.6 步骤 4「缺末段拒绝」MUST：流在未出现合法末段时即终止（连接中断、`segment_count` 段已耗尽但末段 flag 仍为 `0x00`，或声明 `segment_count` 与实际不符）MUST 拒绝（`segment_stream_truncated`），并丢弃已释放 / 缓冲明文，不得把已得明文当作完整文件。

Steps：

- **Case A — 丢弃末段 / 末段 flag 仍为 0x00**：发送 `segment_count - 1` 段后流终止，从未出现 `last_segment_flag = 0x01` 的合法末段（或最后到达段的 flag 仍为 `0x00`）。
- **Case B — `segment_count` 段耗尽但无末段**：恰好接收声明 `segment_count` 段，但其中无任何段的 `last_segment_flag = 0x01`（声明数与实际末段缺失不符）。

Expected：

- **Case A / Case B**：接收方 MUST 以 `segment_stream_truncated` 拒绝，丢弃已释放 / 缓冲明文，MUST NOT 把已通过 per-segment 校验的部分明文当作完整文件持久化或标记完整。
- 在见到合法末段前接收方 MUST NOT 把附件视为已完整接收（`media-and-blob.md` §3.3.6 步骤 3）；Range / 流式播放下允许消费已通过 per-segment 校验的明文段，但最终持久化或标记完整前 MUST 完成整体 digest 校验（此处因末段缺失永不达成）。

### 16.3 Vector: Streaming AEAD Reorder / Replay Rejected

`vector_id`: `ak.vector.blob.stream_aead_reorder_rejected.v1`

本向量固化 `media-and-blob.md` §3.3.6 步骤 1「按序处理」与步骤 5「重复拒绝」MUST：`segment_index` 跳变 / 乱序 / 出现空洞 MUST 拒绝（`segment_sequence_invalid`）并丢弃已缓冲明文；同一 `segment_index` 出现多次 MUST 拒绝（`segment_replay`）。

Steps：

- **Case A — 乱序 / 跳变**：接收方在按 `segment_index` 升序消费过程中收到 `segment_index` 非连续递增的 segment（如在 index `k` 后到达 `k+2`，或先到 `k+1` 再到 `k`），形成空洞 / 跳变 / 乱序。
- **Case B — 重复段**：同一 `segment_index` 的 segment 出现两次（重放同一已消费段）。

Expected：

- **Case A**：MUST 以 `segment_sequence_invalid` 拒绝，并丢弃已缓冲明文，不得按到达顺序拼接 / 释放越序段。
- **Case B**：MUST 以 `segment_replay` 拒绝重复段。
- 两个 case 中，因 `segment_index` / `last_segment_flag` 同时进入 nonce 与 AAD（`media-and-blob.md` §3.3.2 / §3.3.3），重排、截断与末段伪造在 AEAD 层即应被拒绝（tag 校验失败）；conformance 判定以稳定 `reason_code` 为准。

### 16.4 Vector: Streaming AEAD Scheme Closure

`vector_id`: `ak.vector.blob.stream_aead_scheme_closure.v1`

本向量固化 §3.2 的 scheme 分派 fail-closed MUST 与 [`blob.schema.json#/$defs/encrypted_attachment`](../../artifacts/schemas/blob.schema.json) 的整文件 / 分块形态互斥 `oneOf`：接收方 MUST 按 envelope `scheme` 分派解密路径，遇到未知 `scheme` MUST fail closed（`unsupported_attachment_scheme`），不得回退到任何其它形态尝试解密；整文件形态（`nonce`）与分块形态（`nonce_prefix` / `segment_*`）字段互斥。

Steps：

- **Case A — 未知 scheme**：envelope 声明 `scheme` 为既非 `ak.blob.whole_file_aead.v1` 亦非 `ak.blob.stream_aead.v1` 的未知值（如 `example.invalid_blob_scheme`）。
- **Case B — 形态字段混用**：单个 envelope 同时携带整文件形态字段 `nonce` 与分块形态字段 `nonce_prefix`（及 `segment_bytes` / `segment_count`），违反 `encrypted_attachment` 的 `oneOf`。

Expected：

- **Case A**：接收方 MUST fail closed，返回 `unsupported_attachment_scheme`，MUST NOT 回退到 `ak.blob.whole_file_aead.v1` 或任何其它形态尝试解密。
- **Case B**：schema 校验 MUST 失败（`oneOf` 两个分支互斥，同时含 `nonce` 与 `nonce_prefix` / `segment_*` 不命中任一分支）；接收方 MUST 拒绝该 envelope，不得择一形态解释。
- 对照：缺省 `scheme` 时 MUST 按 `ak.blob.whole_file_aead.v1`（整文件形态、单 `nonce`）解释（§3.2 current default rule），不属于本反例。

### 16.5 Vector: Streaming AEAD Declared Bounds Rejected

`vector_id`: `ak.vector.blob.stream_aead_bounds_rejected.v1`

本向量固化 [scalability-constraints.md](./scalability-constraints.md) §6 的 segment 声明上限 MUST：`segment_bytes` ∈ [1 KiB（1,024）, 8 MiB（8,388,608）]、`segment_count` ≤ 2^20（1,048,576），且 `segment_count` MUST 等于 `ceil(size_bytes / segment_bytes)`；越界或不自洽的 envelope MUST 在密钥派生 / 任何 segment 下载开始之前 reject / fail closed。所有 case 均为**声明字段负例**：判定只依据 envelope 声明的 `segment_bytes` / `segment_count` / `size_bytes` 数值本身，runner MUST NOT 真实构造对应体量的明文或密文。

Steps：

- **Case A — `segment_count` 超上限**：envelope 声明 `segment_count = 1048577`（2^20 + 1），`segment_bytes = 262144`，`size_bytes` 与二者自洽。
- **Case B1 — `segment_bytes` 低于下限**：envelope 声明 `segment_bytes = 1023`（< 1 KiB）。
- **Case B2 — `segment_bytes` 高于上限**：envelope 声明 `segment_bytes = 8388609`（> 8 MiB）。
- **Case C — `segment_count` 与 `size_bytes` 不自洽**：envelope 声明 `segment_bytes = 262144`、`segment_count = 4`，但 `size_bytes = 2621440`（需要 `ceil(2621440 / 262144) = 10` 段）。

Expected：

- **Case A / B1 / B2**：MUST reject（`schema_violation`，`reason_code=segment_bounds_invalid`）；Case B1 / B2 亦不满足 [`blob.schema.json#/$defs/encrypted_attachment`](../../artifacts/schemas/blob.schema.json) 已声明的 `segment_bytes` `minimum` / `maximum`。
- **Case C**：接收方 MUST fail closed（`schema_violation`，`reason_code=segment_bounds_invalid`）；不得先按声明值开始下载再在流中途发现不符。
- 全部 case 中接收方 MUST NOT 依据未经校验的声明值预分配缓冲区、下载计划或段索引表；拒绝 MUST 发生在密钥派生与首段获取之前。

## 17. Last-Resort KeyPackage Vectors

本节收拢可选 last-resort KeyPackage 语义的 conformance 向量，固化 [`encryption-and-audit.md`](../crypto-media/encryption-and-audit.md) §2.6.2 的复用 / 幂等 consume / 强制轮换 / Realm affinity / 可选协商 MUST。该能力由 feature `ak.feature.mls_last_resort_keypackage.v1` 门控（server describe `supported_features`）。每个 `vector_id` 均为规范性引用目标，登记于 [`vector-registry.json`](../../artifacts/registry/vector-registry.json)。

### 17.1 Vector: Last-Resort Claim And Reuse

`vector_id`: `ak.vector.keypackage.last_resort_claim_and_reuse.v1`

本向量固化 §2.6.2 的优先序、复用与幂等 consume MUST：池中存在普通包时 claim MUST 优先返回普通包，仅普通包池空时 MAY 返回 `last_resort=true` 包；last-resort 包 MUST NOT 进入单次 `claimed` / `consumed` 状态，而是始终保持 `published`，每次领取以独立 `keypackage_claim_record` 表达；`ak.keys.keypackages.consume` 对 last-resort `keypackage_ref` MUST 被识别为幂等（返回成功但不改 `published`，不得返回 `keypackage_already_consumed`）；每次消费 MUST 追加 claim audit record，不得伪造 KeyPackage FSM transition。

Steps（前置：服务端在 `ak.server.query.describe.supported_features` 声明 `ak.feature.mls_last_resort_keypackage.v1`，目标 Realm policy 允许 last-resort join）：

1. 该 Realm 的普通（单次）KeyPackage 池耗尽；requester 发起 claim。
2. 同一 `intended_realm_id` 内对该 last-resort 包发起多次 Welcome（多次 claim / consume）。
3. 检查每次消费后的审计链。

Expected：

- 普通包池空后，claim 响应 MAY 返回 last-resort 包，且对应 `keypackage_claim_record` MUST 置 `last_resort=true`，使 requester 与 holder 都能识别本次走 last-resort 路径。
- 同一 `intended_realm_id` 内该包可被多次 Welcome 复用；`ak.keys.keypackages.consume` 对其调用 MUST 幂等（返回成功、状态保持 `published`、不移出池、MUST NOT 返回 `keypackage_already_consumed`）。
- §2.6 / §2.6.1 其余校验（`keypackage_digest` / `capabilities_digest` / `ssk_generation` 匹配、`claim_envelope` 签名、Realm 反向 resolve）对 last-resort 包仍全部适用，放宽的只有单次性。
- 每次消费 MUST emit 一条 `ak.mls.keypackage`（或等价）审计记录，至少含 `keypackage_ref`、`keypackage_digest`、`claim_id`、`last_resort=true`、消费的 `intended_realm_id` 与时间戳；审计链 MUST append-only，保留每次消费的独立记录（不得覆盖前次）。

### 17.2 Vector: Last-Resort Forced Rotation

`vector_id`: `ak.vector.keypackage.last_resort_forced_rotation.v1`

本向量固化 §2.6.2「强制轮换闭合弱化窗口」MUST：last-resort 包持有 device 下次上线时 MUST 轮换该包（发布新 init/encryption key 的新 last-resort 包，并把旧包转入 `revoked`、记录 `revocation_reason="keypackage_rotated"`，使旧包不再分发给新 claim）；持有者上线后 MUST 对所有经该 last-resort 包加入的 group 触发一次 MLS self-update Commit 推进 epoch，把前向保密恢复到正常 ratchet 水平，闭合 Welcome 阶段前向保密弱化窗口。

Steps：

1. holder 离线期间，其某个 last-resort 包在 Realm 内被用于多个 Welcome，使多个 group 经该包加入。
2. holder 重新上线。

Expected：

- holder 上线后 MUST 发布新的 last-resort KeyPackage（新 init/encryption key），并把旧包转入 `revoked`、记录 `revocation_reason="keypackage_rotated"`；轮换后旧包 MUST NOT 再被分发给新 claim。
- holder MUST 对所有经该旧 last-resort 包加入的 group 触发一次 MLS self-update Commit（引入新 leaf key 材料）推进 epoch；无法精确定位经哪个包加入了哪些 group 时，MUST 对该 device 当前所有 last-resort-joined group 保守触发 update。
- 该轮换 + update 序列 MUST 把上文弱化窗口闭合在有界范围内；组建立后常规消息 ratchet 前向保密不受影响（仅初始 Welcome 注入受弱化窗口约束）。

### 17.3 Vector: Last-Resort Affinity And Optionality

`vector_id`: `ak.vector.keypackage.last_resort_affinity_and_optionality.v1`

本向量固化 §2.6.2 的 Realm affinity、可选协商与高保证 profile 禁用 fail-closed MUST：实现 MUST NOT 用单个全局 last-resort 包跨任意 Realm 复用，多次复用 MUST 限定在同一 `intended_realm_id` 内，跨 Realm 复用 MUST 拒绝（`last_resort_realm_affinity_violation`）；未声明 `ak.feature.mls_last_resort_keypackage.v1` 的服务端在池空时 MUST 继续 fail-closed，claim 响应 MUST NOT 返回 `last_resort=true` 的包（请求 last-resort 回退 MUST 拒绝，`last_resort_not_supported`）；`ak.profile.high_security_organization.v1` / `ak.profile.sovereign_deployment.v1` Realm 即使所在服务支持该 feature，也 MUST 禁止 last-resort join。

Steps：

- **Case A — 跨 Realm 复用拒绝**：声明该 feature 的服务端，尝试把绑定 `intended_realm_id = R1` 的 last-resort 包用于另一 Realm `R2` 的 Welcome / claim（`intended_realm_id` 不一致）。
- **Case B — 未声明 feature 池空 fail-closed**：未在 `ak.server.query.describe.supported_features` 声明 `ak.feature.mls_last_resort_keypackage.v1` 的服务端，其某 Realm 普通包池耗尽；requester claim，并显式请求 last-resort 回退。
- **Case C — holder 无该 Realm 条目（对照）**：声明该 feature 但 holder 离线期间某 Realm 尚无 last-resort 条目，该 Realm 普通包池空。
- **Case D — 高保证 profile 禁用**：服务端全局支持 `ak.feature.mls_last_resort_keypackage.v1`，但目标 Realm 声明 `ak.profile.high_security_organization.v1` 或 `ak.profile.sovereign_deployment.v1`。

Expected：

- **Case A**：MUST 以 `last_resort_realm_affinity_violation` 拒绝；last-resort 包的多次使用语义是 Realm 内多次，跨 Realm 回退 MUST 由各 Realm 各自的 last-resort 池条目分别满足，不得退化为跨 Realm 复用。
- **Case B**：服务端 MUST 继续 fail-closed（池空 claim 失败），claim 响应 MUST NOT 返回 `last_resort=true` 的包；对显式 last-resort 回退请求 MUST 返回 `last_resort_not_supported`。
- **Case C**：该 Realm 的 claim 在不支持普通包回退时 MUST fail closed（与默认池空行为一致），不得退化为跨 Realm 复用其它 Realm 的 last-resort 包。
- **Case D**：该 Realm 的 describe / profile projection MUST 把 `ak.feature.mls_last_resort_keypackage.v1` 视为 forbidden feature；claim 响应 MUST NOT 返回 `last_resort=true` 的包，requester 若收到 `last_resort=true` claim record MUST fail closed（按池空 / profile-forbidden 处理），不得发 Welcome。
- 所有 case 都保留 §2.6 的审计与隔离性质：每次消费 `intended_realm_id` 确定、claim-Realm 一致性可校验、`claim_envelope` Realm 反向 resolve 不被绕过。

## 18. Sender-Constrained Session Token Vectors

本节收拢 sender-constrained（proof-of-possession，PoP）会话出示的 conformance 向量，固化 [`api-conventions.md`](../sync/api-conventions.md) §3 / §3.2 的生产 current-v1 受保护 endpoint PoP 要求，以及 [`service-http-binding.md`](../sync/service-http-binding.md) §2.5 的 RFC 9421 HTTP Message Signature header 形状与 transcript 绑定。每个 `vector_id` 均为规范性引用目标，登记于 [`vector-registry.json`](../../artifacts/registry/vector-registry.json)。

### 18.1 Vector: PoP Presentation

`vector_id`: `ak.vector.session.pop_presentation.v1`

本向量固化 §3.2 / §2.5 的 PoP 出示与 transcript 绑定 MUST：客户端用 `ak.session.grant` 委托的 `session_public_key` 对应私钥做 RFC 9421 HTTP Message Signature，covered components MUST 至少覆盖 `@method`、`@target-uri`、`@authority`，带 body 请求 MUST 含 `content-digest`；request wire MUST 自身为 Arkret canonical JSON，RFC 9530 `Content-Digest` MUST 使用唯一 `sha-256` member 并覆盖 exact HTTP content bytes，接收方 MUST 按 [`service-http-binding.md` §2.5.1](../sync/service-http-binding.md) 在 JSON 业务解析与验签前完成 raw-byte digest 与 canonical-byte equality 校验。签名 `kid` MUST 指向当前 grant 的 `session_public_key`；出示是否被接受由签名 transcript 而非裸 token 决定。

Steps：

- **Case A — 合法 PoP 写请求**：对常规写 endpoint（如 `POST /_arkret/self/events`）提交，request body exact bytes 是 Arkret canonical JSON，`Content-Encoding` absent，`Content-Digest` 为覆盖这些 bytes 的单 member `sha-256=:...:`；`Signature-Input` covered components 含 `@method` / `@target-uri` / `@authority` / `content-digest`（及参与幂等的 `idempotency-key`），`keyid` 指向当前 grant 委托的 `session_public_key` kid，`created` / `expires` 在 replay window 内。
- **Case B — transcript / digest 不一致**：(a) 用对 method `M1` / path `P1` / body `B1` 生成的签名出示到 method / path 不同或 body 改为 `B2` 的请求（covered component 实际值与签名 transcript 不符）；(b) `Content-Digest` 与 exact HTTP content bytes 的实际 SHA-256 不一致。
- **Case C — 等价但非 canonical 的 JSON wire**：把 Case A body 改成 parse 后 JSON value 相同、但含额外 whitespace、尾随 LF 或不同 member order 的 bytes，并分别尝试 (a) 保留 canonical body 的 digest；(b) 改为覆盖非 canonical exact bytes 的 RFC 9530 digest，并用合法 session key 对更新后的 header transcript 重新签名，使除 canonical-wire 检查外的认证条件均有效。
- **Case D — 错误 dictionary profile / placement / content coding**：分别把 `Content-Digest` 改为 `sha256=:...:`、增加额外 `sha-512` member、给 `sha-256` member 增加 parameter、把正确 `Content-Digest` 只放在 trailer section，或对 canonical JSON 应用 gzip 并携带 `Content-Encoding: gzip`。每个 mutation 都 MUST 按其实际 content/header 重算 digest（适用时）并重新签名，使其它 transcript 与认证条件有效。

Expected：

- **Case A**：验签通过，grant 的 principal / device / audience / origin 约束与请求一致，请求被接受；PoP 只把「持有 token」升级为「持有绑定密钥」，协议层权限判断仍回到 actor DID / capability / Realm policy。
- **Case B(a)**：`@method` / `@target-uri` / `@authority` / `content-digest` 任一与重算结果不符时验签失败，MUST 拒绝（grant 已撤销 / 过期 / audience / origin 不匹配同样 MUST 以 `unauthenticated` 拒绝）。
- **Case B(b)**：接收方 MUST 在 JSON 业务解析与验签前先校验 exact HTTP content bytes 的实际 hash 与 `Content-Digest` 一致，不一致 MUST 拒绝，不得仅凭 header 自报 digest 通过。
- **Case C(a)**：MUST 因 raw-byte digest mismatch 拒绝；**Case C(b)** 即使 RFC 9530 digest 覆盖 raw bytes 也 MUST 因 wire 不是 Arkret canonical JSON 拒绝。两者都不得通过 parse-then-canonicalize 接受。
- **Case D**：`sha256=:` 不是 `sha-256` alias，额外 member / member parameter、trailer placement 与 gzip content 也分别违反 §2.5.1 的单一无参数 Byte Sequence member、header-section-only 与无 content coding 规则；全部 MUST fail closed。

### 18.2 Vector: Bare Bearer Rejected On Protected Endpoints

`vector_id`: `ak.vector.session.bare_bearer_rejected_protected.v1`

本向量固化 §3.2 / §2.5 的 sender-constrained 会话出示与 replay window MUST：生产 current-v1 受保护 endpoint MUST 要求 DPoP、RFC 9421 HTTP Message Signature、detached JWS、mTLS 或等价 sender-constrained proof；纯 `Authorization: Bearer`（无 DPoP / PoP / mTLS 绑定）对受保护 endpoint MUST 被拒绝。`ak.profile.high_security_organization.v1` / `sovereign_deployment` 进一步要求常规写与敏感读使用带 transcript/body 绑定的 RFC 9421 HTTP Message Signature。PoP 的 `created` / `expires` 超出 replay window 即使 replay cache 已 evict 也 MUST 因 `created` / `expires` 校验失败而拒绝（口径同 `federation.md` §3.2 / `encoding.md` §6 签名时效窗口）。

Steps：

- **Case A — 高安全 profile 纯 bearer 写 / 敏感读**：在 `ak.profile.high_security_organization.v1`（或 `sovereign_deployment`）下，对常规写（推进 actor_seq / Realm frontier）或敏感读（成员列表、私有 projection、key backup、device list、moderation 队列等）只用 `Authorization: Bearer <ak.session.grant>` 出示，无 `Signature` / `Signature-Input`，且无 DPoP / mTLS 绑定。
- **Case B — 默认 profile 受保护 endpoint 纯 bearer**：默认 profile 下对任一受保护 current-v1 endpoint 只用 `Authorization: Bearer <ak.session.grant>` 出示，无 DPoP / PoP / mTLS 绑定。公开 metadata endpoint 若设计为无需认证的 public surface，MAY 返回公开响应，但 MUST NOT 把裸 bearer 当作认证成功的 session presentation。
- **Case C — PoP 过窗**：携带合法签名的 PoP 出示，但 `created` / `expires` 超出 replay window（`expires - created` 超上限或 `created` 与本地时钟偏差超上限）。

Expected：

- **Case A**：MUST 以 `unauthenticated` 拒绝；高安全 profile 对常规写与敏感读要求 RFC 9421 PoP 出示（见 [`conformance-profiles.json`](../../artifacts/profiles/conformance-profiles.json) 对应 profile 的 `additional_requirements`），纯 bearer 对这些操作 MUST 被拒绝。
- **Case B**：受保护 endpoint MUST 以 `unauthenticated` 拒绝。若 endpoint 是公开 metadata surface，响应 MUST 按未认证 public request 处理，不得授予 session/capability 语义。
- **Case C**：过窗签名即使 replay cache 已 evict 也 MUST 因 `created` / `expires` 校验失败而拒绝；时效窗口外的逐字节重放同样 MUST 拒绝。

### 18.3 Vector: DPoP Target URI Binding

`vector_id`: `ak.vector.session.dpop_target_uri_binding.v1`

本向量固化 DPoP `htu` 的完整外部 URI 绑定。校验时只移除 query 与 fragment，scheme、authority 与 path 均参与比较：相同 path 的不同 authority、HTTP/HTTPS scheme 淆混、来自非受信 peer 的 `Forwarded` / `X-Forwarded-*`、以及无法重建 authority 的请求都 MUST 以 `unauthenticated` 拒绝。只有静态配置的 public origin，或由受信最后一跳代理在入口清洗同名客户端 header 后提供的 external URI，才可用于匹配；不存在 path-only fallback。

### 18.4 Vector: Session / Device Identity Key Separation

`vector_id`: `ak.vector.session.device_identity_key_separation.v1`

本向量固化 grant-binding session key 与长期 device identity key 的材料分离。DPoP 与 RFC 9421 可以共享同一短期 session key；但其 key bytes、公钥 fingerprint、JWK thumbprint 或 `kid` 任一与 `device_public_key` 对应材料相同都必须 fail closed，不能以“生命周期逻辑分开”替代密码学 key separation。

### 18.5 Vectors: Morph Migration Transformation Closure

`vector_id`: `ak.vector.morph.transformation_identity.v1`、`ak.vector.morph.transformation_rename.v1`、`ak.vector.morph.transformation_type_widen.v1`、`ak.vector.morph.transformation_default_backfill.v1`

这组向量是 `ak.profile.morph.schema_migration_transformations.v1` 的必需 fixture，覆盖 identity、rename、integer-to-number type widening 与 default backfill。runner 必须实际应用登记的 transformation grammar，比较 canonical JSON output 并重算 `expected_output_digest`；只检查字符串存在或 fixture 非空不算通过。

## 19. Applet Transaction Push Vectors

本节收拢 Applet inbound transaction push 的来源签名锚点与 replay 绑定向量，固化 [`applet-integration.md`](../extensions/applet-integration.md) §7.3.1、[`applet-schema.md`](../extensions/applet-schema.md) §3、[`service-http-binding.md`](../sync/service-http-binding.md) §2.2 的 service-to-service HTTP Message Signature 要求。每个 `vector_id` 均为规范性引用目标，登记于 [`vector-registry.json`](../../artifacts/registry/vector-registry.json)。

### 19.1 Vector: Transaction Source Signature Anchor

`vector_id`: `ak.vector.applet.transaction_source_signature_anchor.v1`

本向量固化 applet transaction push 的逐次来源签名与幂等 replay MUST：`ak.edge.applet.command.transaction` 在 node→Applet 与 app/bridge→arkret inbound 两个方向都 MUST 携带 RFC 9421 HTTP Message Signature，covered components 至少包含 `@method`、`@target-uri`、`@authority`、`content-digest`、`source-service-id`、`destination-service-id`、`idempotency-key`，签名参数含 `created` / `expires` 并满足 300s replay window；接收方 MUST 形成并持久化 `source_signature_anchor`，幂等 identity 绑定 `operation_id`、方向、source/destination service DID 与 `Idempotency-Key`，缓存记录绑定 canonical body digest 与 source anchor。来源 service 签名不替代每条 Event 的 actor / applet / capability 校验。

Steps：

- **Case A — 合法 app/bridge→arkret inbound**：已安装 Applet registration `service_id=did:webvh:z6mkfixture:bridge.example`，`registration_epoch=sha256:<R>`，`webhook_auth.key_ref=did:webvh:z6mkfixture:bridge.example#tx-1`，install active。Applet 提交 `POST /_arkret/edge/applet/transactions`，body exact bytes 是 Arkret canonical JSON、`Content-Encoding` absent，header `Source-Service-ID=did:webvh:z6mkfixture:bridge.example`、`Destination-Service-ID=did:webvh:z6mkfixture:principal.example`、`Idempotency-Key=tx-001`、`Content-Digest=sha-256=:...:` 且覆盖 exact body bytes；`Signature-Input` 覆盖 required components，`keyid=did:webvh:z6mkfixture:bridge.example#tx-1`，`created` / `expires` 在窗口内；body `source_service_id` 与 header 一致，`events[]` 中的 `applet_id`、`authorization_ref`、`proofs[]` 与 actor namespace / capability grant 均有效。
- **Case B — 缺签名 / 纯 bearer**：同一 body 只携带 `Authorization: Bearer` 或完全缺少 `Signature` / `Signature-Input`。
- **Case C — transcript / source / content 混淆**：签名覆盖的 `source-service-id`、header `Source-Service-ID` 或 body `source_service_id` 三者任一不同；或 `Destination-Service-ID` 不等于实际接收服务；或 `Content-Digest` 与 exact body bytes 不一致；或 body 是语义等价但非 canonical 的 JSON wire；或使用 `sha256=:` alias、trailer-only `Content-Digest` / `Content-Encoding`。对非 canonical wire、alias、trailer 与 content-coding mutation，sender MUST 重算适用的 digest 并用有效 Applet service key 重新签名，使 receiver 必须由相应 profile 规则而非偶然 signature mismatch 拒绝。
- **Case D — idempotency replay**：重复 Case A 的相同 headers/body/signature anchor；随后再次使用同一 `(operation_id, direction, Source-Service-ID, Destination-Service-ID, Idempotency-Key)`，但改变 body digest、`webhook_auth.key_ref` / `keyid`、`registration_epoch` 或 actor namespace。
- **Case E — 无 active install / actor namespace 混淆**：`Source-Service-ID` 可验签但没有 active effective install，或 `events[]` 中 actor / `executed_by` 不属于该 Applet registration 的 service / bot / ghost actor namespace，或 `authorization_ref` 指向另一 Applet 的 grant。

Expected：

- **Case A**：MUST 接受或按事件级规则返回 partial outcome，并持久化 `source_signature_anchor`（绑定 operation、方向、source/destination、verification method、registration_epoch、`Idempotency-Key`、body digest、covered components、`created` / `expires`）与幂等 outcome。
- **Case B**：MUST fail closed，HTTP 401，reason=`http_signature_required`；纯 bearer 不满足 transaction push 的 service-to-service 来源认证。
- **Case C**：MUST 在处理任何 Event / 副作用前 fail closed，reason=`http_signature_invalid`；`Content-Digest` MUST 在 JSON 业务解析与验签前对 exact bytes 重算，header placement 与 wire canonical equality MUST 独立校验，source/destination DID mismatch 不得进入业务逻辑。parse-then-canonicalize、`sha256=:` alias、trailer-only digest 或 content coding 均不得通过。
- **Case D**：完全相同的 replay MUST 返回原 outcome 或等价成功且不得重复副作用；同一幂等 identity 但 body digest 或 `source_signature_anchor` 不一致时 MUST fail closed，认证已通过时 reason=`duplicate_conflict`，认证未通过时使用相应认证失败 reason。
- **Case E**：无 active install MUST fail closed，reason=`applet_registration_unauthorized`；actor / namespace / grant 混淆 MUST fail closed（`applet_namespace_mismatch`、`capability_denied` 或 `applet_registration_unauthorized`），不得把来源 service 签名当成 native actor 授权。

### 19.2 Vector: Registration Epoch Transcript

`vector_id`: `ak.vector.applet.registration_epoch_transcript.v1`

本向量固化 [`applet-schema.md` §1.0.1](../extensions/applet-schema.md#101-registration_epoch-transcript-与计算算法normative) 的唯一重算路径。runner MUST 读取 [`applet-registration-epoch-fixture.json`](../../artifacts/fixtures/applet-registration-epoch-fixture.json) 的完整 transcript，以 `arkret-applet-registration-epoch-v1\n` 为域分离前缀，执行 JCS 与 SHA-256，并逐字节比较 `canonical_bytes_utf8` 和 `expected_registration_epoch`。

Expected：

- 正向 transcript MUST 产生 fixture 登记的完整 canonical bytes 与 digest。
- set-like 数组乱序或排序键重复 MUST 在 JCS 前 fail closed；不得静默排序重复项后继续，也不得保留第一项。
- optional 成员使用 `null`、unversioned DID evidence 同时携带 version 字段，均 MUST schema violation。
- base URL、bot actor、endpoint/auth、accepted key、DID document digest、requested scope、profile 或 policy 任一安全字段改变，MUST 产生不同 epoch；验证旧 grant 时视为 evidence mismatch。

## 20. Audited E2EE Release Vectors

[`audit-release-fixture.json`](../../artifacts/fixtures/audit-release-fixture.json) 是 `ak.profile.attested_audit.e2ee.v1` 与 `ak.profile.disclosed_audit.e2ee.v1` 的必需行为 fixture。Runner MUST 实际执行 binding FSM、session FSM、release ordered log 与 output gate；只验证 payload schema 或 Event kind 存在不算通过。

### 20.1 Binding 与 Session FSM

`ak.vector.audit.binding_fsm.v1` MUST 覆盖 `active <-> suspended`、到 terminal `revoked`、revoked 后恢复拒绝与 same-basis sibling Bottom。`ak.vector.audit.session_fsm.v1` MUST 覆盖 `request -> authorize -> notice -> close`、失败流程的 early close、跳阶段拒绝、重复阶段与 terminal replay。Runner 的状态和值必须来自 [`event-kind-registry.json`](../../artifacts/registry/event-kind-registry.json) 登记的 cell family / lattice / parameters，不能维护另一套迁移表。

### 20.2 Release 安全门

`ak.vector.audit.release_recipient_binding.v1`、`ak.vector.audit.release_window.v1` 与 `ak.vector.audit.binding_and_authorization_gate.v1` MUST 证明：recipient actor/key 与 authorize 逐字节一致且 key 解析到同一 actor；release 不早于 binding activation / `first_auditable_epoch`，不包含 active epoch，sealed epoch 模式绑定 `sealed_by_commit_ref`；binding 必须 active，authorize 未过期，session accepted head 必须为 `notice`。每个相反变体都必须 fail closed，不能裁剪范围后继续输出。

### 20.3 Close 并发与 RYW-before-output

`ak.vector.audit.close_release_concurrency.v1` MUST 覆盖 same-basis close-vs-release 的 close-wins 裁决、更早 accepted release 的完整 `release_refs[]` freeze、post-close release 拒绝与同 Seal 内 `event_digest` 排序。`ak.vector.audit.ryw_before_output.v1` MUST 证明 material 在 release accepted 且取得 profile-valid RYW receipt 前不会输出；`attested_hardware` 分支还必须验证独立 witness 与 policy digest / eligibility proof 一致。Runner 必须检查输出至多一次，不能把“已构造 wrapped material”误当成“已允许交付”。

## 21. Arkret 私有 MLS 派生与持久化向量

[`arkret-private-kdf-fixture.json`](../../artifacts/fixtures/arkret-private-kdf-fixture.json) 是本节三条 active 向量的字节级与状态机真源。Runner MUST 按 RFC 9420 §2.1.2、§8 与 §8.5 实际执行 HKDF-SHA256、最小宽度 varint、`ExpandWithLabel`、`MLS-Exporter`、NFC 与 HMAC-SHA256；MUST NOT 直接信任 fixture 中间值或只比较字符串。

### 21.1 `mls_exporter_aead_v1` 内容键派生

`ak.vector.mls_exporter_aead.content_key_derivation.v1` 固定 `exporter_secret` 与 `realm_id`，逐字节比较 `history_secret`、`ak.content-v1` 的完整 KDFLabel info 与 `K_content`。错误 label、空 Realm exporter context、给第二级派生加入非空 context、跨 epoch 复用内容键均 MUST 与金值不同或在加密前 fail closed。

`ak.vector.mls_exporter_aead.seal_open_transcript.v1` 继续固定 `history_secret`、nonce、closed immutable header、plaintext 与 AES-128-GCM 输出，逐字节比较 `aead_aad_canonical_json` 和含 tag 的 ciphertext。修改 `aad.event_kind`、epoch、`key_ref.group_state_ref`、`aead_profile` 或 authentication tag 均 MUST 在 open 时拒绝；runner MUST 从 header 重建 JCS bytes，不得直接把 fixture 的 canonical JSON 字符串当作可信 AAD 输入。

### 21.2 Signal、sender nonce prefix 与 mention routing KAT

`ak.vector.signal.exporter_key_kat.v1` 固定 exporter secret、Realm context 与 active MLS ciphersuite，逐字节比较 `history_secret`、`ak.signal-v1` 的完整 KDFLabel info 与 16-byte Signal AEAD key；错误 label、非空第二级 context 或跨 epoch 复用均 MUST fail closed。

`ak.vector.aead.sender_nonce_prefix_kat.v1` 固定 `arkret-aead-sender-nonce-prefix-v1` label、完整 `{key_ref, epoch, device_id, purpose, aead_profile}` JCS context、AES-GCM prefix 长度与 big-endian counter，逐字节比较 4-byte prefix 和最终 12-byte nonce。遗漏或修改任一 context 字段 MUST 产生不同前缀或在 seal 前拒绝。

`ak.vector.mention.routing_hmac_kat.v1` 固定 exporter secret、Realm context、mentioned DID 与 routing label，逐字节比较 32-byte exporter output 与 HMAC-SHA256 tag。错误 label、跨 Realm、修改 DID 或跨 epoch 复用 key MUST fail closed。

### 21.3 Reaction routing HMAC

`ak.vector.reaction.routing_hmac_kat.v1` 固定 exporter secret、Realm context 与 routing label，要求分解形式 `U+0065 U+0301` 与预组形式 `U+00E9` 经 NFC 后产生完全相同的 tag，并覆盖 emoji modifier。跳过 NFC、错误 label、跨 Realm context 或跨 epoch 复用 exporter key MUST fail closed。

### 21.4 RRK eager seal before GC

`ak.vector.mls_exporter_aead.rrk_eager_seal_before_gc.v1` 要求 `durability_policy.mode != none` 时，在每个配置的 `recovery_recipients[]` 对应 `ak.realm_key.share` accepted 前保留 `history_secret[N]`。未达到完整目标集即 GC MUST 返回 `failed_precondition` / `durability_seal_missing_before_gc`；恢复 verification method 非 active 或未由 `ArkretRealmHistoryRecoveryKey` 指定时 MUST 返回 `durability_recovery_recipient_unverified` 且不得换用其它 key。threshold 只控制恢复授权，不缩减 eager-seal 目标集。

## 22. Identity Root、Delegated Bootstrap 与 Recovery Re-anchor 向量

本节由 [`identity-recovery-kdf-fixture.json`](../../artifacts/fixtures/identity-recovery-kdf-fixture.json)、[`identity-root-anchor-fixture.json`](../../artifacts/fixtures/identity-root-anchor-fixture.json) 与 [`did-webvh-v1-fixture.json`](../../artifacts/fixtures/did-webvh-v1-fixture.json) 承载。runner MUST 实际执行密码学派生、DID history 验证、原子 admission 与 reducer 状态转换；只检查字段存在、直接信任 fixture 的中间值或用 first-seen 选择分叉均不算通过。

### 22.1 Recovery-secret KDF KAT

`ak.vector.identity.recovery_kdf.v1` 固定 BIP-39 24 词 + passphrase 与 32-byte raw secret 两条输入路径。实现 MUST 逐字节重算 HKDF PRK、`root_seed_0/1`、`recovery_proof_seed`、`backup_hpke_ikm`、Ed25519 raw public keys 与 multikey、RFC 9180 `DHKEM(X25519, HKDF-SHA256).DeriveKeyPair` 的 raw `derived_sk`、clamped serialized private key 与 public key，以及 `Base58BTC(multihash(sha2-256, UTF8(root_1_multikey)))` canonical `nextKeyHash`。fixture 中 raw-public-key SHA-256 只作为诊断值，不得写入 did:webvh `nextKeyHashes`。任何 salt/info 字节、`u64be(i)`、multicodec/multihash 编码、输入文本化、raw/clamped private-key 表示混淆或 Ed25519→X25519 key reuse 漂移都必须失败。

`ak.vector.identity.recovery_key_role_separation.v1` 固定 recovery policy 的跨数组语义：`recovery_keys[]` 的 recovery-proof signing entry 必须用唯一 `key_agreement_ref` 配对同一 accepted policy 的一个 active `recovery_key_agreements[]` backup-HPKE entry；proof verification 只能使用前者，所有 `recovery_public_key` envelope 的 signed `recovery_policy_ref` / `recipient_key_ref` / `hpke_suite` 只能解析到后者。悬空或重复 ref、撤销/过期 entry、签名与 HPKE 复用 material、suite 不匹配、把 signing ref 当 recipient、或只在 DID Document 声明而未进入 session/envelope referenced policy 均 MUST reject。

### 22.2 Root-anchor 排他性

`ak.vector.identity.root_anchor_exclusivity.v1` 只允许 identity root 为自体 principal 的第一条 PCR `ak.realm.create`（唯一 critical `did_inception`）和 B 模型 `ak.device.reanchor` 启用 Event root-anchor 验签。原子 bootstrap 必须是 `[ak.realm.create, ak.device.authorize]` 且以 entry 0 delegation 验第二条；拆批、第二 PCR genesis、非 PCR Realm、actor/realm/DID 不匹配、缺失或非 critical ref、root 签任何普通 Event 均 fail closed。Agent PCR 不进入此路径。

### 22.3 Re-anchor、generation fence 与冲突

`ak.vector.identity.device_reanchor.v1` 同时覆盖零 Seal 与完整 accepted Seal frontier 两个正向入口、最终 authorize event id/digest 的无环双签构造、byte-identical 幂等重试和 accepted-at receipt 历史复验。负向必须覆盖 A 模型混入、live non-head、伪造 previous generation、过旧/不完整/CAS 失配 frontier、replacement event id/digest 不符、拆批、spent root、post-fence 旧 generation Event/Seal，以及首个新 generation Seal 的 predecessor/delta 不匹配。

同 `(principal_id,did_version_number)` 的不同 versionId/digest 或同 entry 的不同 re-anchor unit 必须把全集置于 quarantine 并令 `device_generation_status="conflicted"`；不同到达顺序得到相同结果，禁止 first-seen winner。conflicted 期间普通 admission fail closed；只有下一预承诺 authority 的有效 resolution entry + re-anchor unit 可恢复 `active`。

### 22.4 Recovery-secret 泄露 handoff

`ak.vector.identity.recovery_secret_handoff.v1` 要求：没有预先存在的独立 guardian/witness/组织权威时，旧秘密泄露后的 same-DID 原地 handoff 必须拒绝并重铸 DID；存在独立权威时，只接受带 durable checkpoint 的两-entry 分阶段 handoff，并在 re-anchor、新 recovery policy、全部旧 backup-HPKE active envelope 新 series 重封装与 active-series pointer 推进完成后，最后撤销旧 policy key。runner MUST 覆盖任一阶段崩溃后的幂等续跑。

### 22.5 外部 Organization DID registration

`ak.vector.identity.organization_registration.v1` 由 [`organization-registration-fixture.json`](../../artifacts/fixtures/organization-registration-fixture.json) 承载，覆盖 [`identity-did.md` §8.4](../identity/identity-did.md)。

正向：合法 challenge；`resolved_verification_method` 与 `governance_quorum` 两个分支的 ensure；含闭合 claims 的 receipt。

负向 MUST 全部拒绝：

- `resolved_verification_method` 分支携带 `quorum_threshold`，或 `governance_quorum` 分支缺 `quorum_threshold` → `schema_violation`。discriminator 双向封闭，否则接收方无法判断"一个签名够用"还是"承诺两个只交了一个"；
- receipt 缺 `expires_at` → `schema_violation`。无界 receipt 会让一次首验永久授权该组织关系，refresh 也就失去存在理由；
- `requested_scopes` 含闭合集合外的值 → `organization_registration_scope_unsupported`；
- `handle_attestation` 缺 `subject` → `schema_violation`。subject 绑定阻止把为 A 组织签发的 attestation 拿去为 B 组织使用；
- challenge 窗口超过 300 秒 → `organization_registration_challenge_invalid`（schema 无法比较两个时间戳，由接收方强制）；
- `governance_quorum` 的 proof 数少于所声明 threshold → `organization_registration_quorum_not_met`；
- ensure 的 `requested_scopes` 与 challenge 所载不一致 → `organization_registration_challenge_invalid`。不一致意味着 proof 是为另一组权限产出的；
- 对 `revoked` binding 执行 refresh → `organization_registration_revoked`。`revoked` 是终态，复活它会抹掉"已撤销"与"仅过期"的区别，也会让因外部 DID deactivated 而被迫 revoked 的绑定死而复生；
- binding 为 `stale` 时的高风险路径 → `organization_registration_stale`；低风险只读可继续，直到 refresh 成功；
- **`ensure` 的 `local_admin_subject` 与所引用 challenge 不一致 → `organization_registration_challenge_invalid`**。这是转交攻击：若 proof 只绑定 organization 与 version，任何拿到它的人都能提交 `ensure` 把自己填进受益位，从而取得该组织的管理 scope。runner MUST 用一个合法 proof 配另一个 `local_admin_subject` 复现该用例。

generation 状态机 MUST 覆盖：

- 重放当前 generation 中已成功消费 challenge 的 byte-identical 同一请求 → 命中
  `(challenge_id, canonical_request_digest, outcome)` ledger，`created=false` 且 generation 不变；
  相同 challenge 的不同 digest → `organization_registration_challenge_invalid`；
- `revoke` 结束第 N 代后再 `ensure` → `created=true`，generation 变为 N+1，既不复活 N 也不报冲突；
- 改变 `local_admin_subject` 或 scope 集合的 `ensure` → 同样开启新 generation（否则被放宽的委派会藏在一次"幂等重放"背后）；
- 开启 N+1 必须与以 `organization_registration_superseded` 终止 N、推进 current-generation pointer
  属于同一原子事务；runner MUST 证明不存在双 active 窗口，且 N 的旧 receipt 即使签名载荷仍写
  `status=active` 也不能再授权；
- `refresh` 永不开启新 generation，只在当前 generation 内换 `version_id`。

runner MUST 实际验证 challenge 消费、proof 绑定与状态机转移，只检查字段存在不算通过。registration 本身 MUST NOT 产生 Realm、成员、notary、capability 或 service delegation；`resource.get` 对"无权管理"与"不存在"MUST 返回同一 `did_not_found`。

### 22.6 did:webvh witness rail

`ak.vector.identity.did_webvh_witness_rail.v1` 由 [`did-webvh-witness-fixture.json`](../../artifacts/fixtures/did-webvh-witness-fixture.json) 承载，覆盖 [`identity-did.md` §3.4.1–§3.4.3](../identity/identity-did.md) 的两层：method-native 输入合同与 Arkret 层承载。二者不得混同。

**method 层**：witness policy 只从 `parameters.witness = {threshold, witnesses:[{id}]}` 读取，`id` MUST 为唯一 `did:key`，`threshold` MUST 落在 `1..witnesses.length`；proof 只从独立发布、按 `versionId` 绑定的 `did-witness.json` 读取。runner MUST 实际解析并验签，只检查字段存在不算通过。

正向：标准形状被接受；`parameters.witness` 缺席被判为"该 DID 未声明 method witness"而不是解析失败。

负向 MUST 全部 fail closed，且 **MUST NOT 归零为「无需 witness」**：

- `parameters` 携带 `witnesses` / `witness_threshold` / `witnessThreshold` 等 alias 键 → `webvh_witness_parameter_malformed`。这是最危险的一条：把该形状读作"无 policy"，会让一个**声明了**两个 witness 的 DID 静默变成**不要求** witness 的 DID；
- `parameters.witness` 混入 `profileMinThreshold` / `structuredWitnesses` / `watcherEvidence` / `maxAgeSeconds` 等 Arkret overlay 字段 → `webvh_witness_parameter_malformed`；
- witness id 非 `did:key`、重复，或 `threshold` 超过 witness 数 → `webvh_witness_parameter_malformed`；
- witness id 形如 `did:key` 但 multibase 载荷无法解码为与 cryptosuite 兼容的合规公钥 → `webvh_witness_parameter_malformed`。MUST 在**参数校验阶段**发现，不得推迟到验签：不可解码的 key 若被允许占据 threshold 名额，该名额永远无法被任何 proof 满足，门限即被悄悄架空；
- 已声明 policy 但 `did-witness.json` 不可达或无该 `versionId` 条目 → `webvh_witness_proofs_unavailable`；
- proof 由 witness 列表外的 key 签发 → `webvh_witness_proof_invalid`；
- 有效且互不相同的 proof 少于生效 threshold → `webvh_witness_threshold_not_met`；
- log 声明 `threshold=1` 而 deployment policy 要求 2 时，生效 threshold MUST 为 2 → `webvh_witness_threshold_not_met`。holder 声明只能提高门限，MUST NOT 降低；
- 要求 distinct controlling organization 时，两个 witness key 同属一个组织 → `webvh_witness_controlling_organization_unverified`。计数按控制组织而非按 key，否则单一运营方持多把 key 即可独自满足"两个不同组织"；
- evidence 超过生效 max age → `webvh_witness_evidence_stale`。age 自 `observed_at` 起算，重新签发旧观测不构成刷新。

**Arkret 层**：`ak.schema.did_webvh_witness_receipt.v1` 与 `ak.schema.identity_receipt.v1` 是两个不同对象族，经 `ak.root.identity.receipts.query.list` 以 `schema` 常量为 discriminator 的 tagged union 返回。runner MUST 验证：两族可在同一响应中共存并被正确分支；receipt 缺 `expires_at` 或 `controlling_organization` MUST 被拒（前者会让缓存记录退化为永久断言，后者使该 receipt 无法计入 distinct-organization）；`witness_did` 非 `did:key` MUST 被拒；receipt 携带 `max_age_seconds` 等 policy 字段 MUST 被拒——receipt 记录观测，不承载 policy，否则新鲜度门槛会落回被审对象手中。

receipt 与 `threshold_met` 均 MUST NOT 替代对标准 `did-witness.json` proof、entry hash chain 与 controller proof 的直接验证；`threshold_met` 缺席 MUST NOT 被读作 `true`。

`did-webvh-witness-fixture.json` 的 `cryptographic_vectors[]` 固定了 did:webvh 官方测试套件
`witness-threshold/rust` 的真实 Ed25519 金向量（上游提交
`02b568fff9da408b8b10702f02b93efd7edcb013`，Apache-2.0）。runner MUST 对该向量：

- 逐条重算 `versionId` 的 entry hash，并验证 controller 的 `eddsa-jcs-2022` proof；
- 把 `parameters.witness.witnesses[].id` 解码为兼容的 Ed25519 `did:key` 公钥；
- 按 `versionId` 绑定并验证 `did-witness.json` 的 witness proof，再计算唯一有效 signer 数；
- 执行 `mutation_cases[]`，分别证明 entry hash、controller proof、witness proof、
  witness-version binding 与 cryptosuite 任一被篡改都会 fail closed。

同一 fixture 的 `structural_cases[]` 继续覆盖 Arkret overlay、策略交集、控制组织去重与
receipt schema；其中的示意 JWS / digest 不得用于密码学断言，也不得覆盖或替代
`cryptographic_vectors[]` 的真实验签结果。

## 23. 2026-07-26 spec-open review closure vectors

本节固定 2026-07-26 一轮流程自洽性审核裁决所要求的向量。它们与既有分节的区别是：
每条都直接对应一条已关闭的开放缺陷，负例用于防止实现私自回退到裁决前的行为。

### 23.1 Canonical Event tie-break（全协议）

`vector_id`: `ak.vector.encoding.canonical_event_tie_break.v1`

覆盖 [`encoding.md` 4.2](./encoding.md) 的唯一 tie-break 键，两类候选集共用同一规则。

Steps:

1. 构造并发候选集与同一 `(cell, actor_id, issuer_seq)` 逻辑 slot 的 equivocation 候选集。
2. 对每个候选计算 `canonical_digest(envelope_without_proofs_unsigned_actor_kind)`。
3. 解码 typed digest 的 hex 为 octets，按 unsigned lexicographic order 取最大者。

Expected:

- winner 是 decoded digest octets 最大的候选；octets 完全相同而 suite 不同时以 canonical suite id 的 UTF-8 bytewise 顺序作第二键。
- 必须包含一条 suite 前缀字符串顺序与 decoded octets 顺序**相反**的 transition case：按整串 UTF-8 比较会选错 winner。
- digest preimage MUST 逐字使用移除 `proofs` / `unsigned` / reducer stamp `actor_kind` 后的 canonical bytes，并保留签名 `scope_ref`；沿用移除 scope 的旧算法 MUST 失败。
- 仅 `proofs` 或 reducer stamps 不同、canonical preimage 逐字相同的两个输入 MUST NOT 被报成 collision。
- 同 typed digest（同 suite、同 octets）但 canonical preimage 不同 MUST fail closed，MUST NOT 回退到 `event_id` / HLC / `created_at` / 到达顺序 / 实现私有 ID。
- producer 在 Event DAG 中人为加入因果边 MUST NOT 改变 slot winner。

### 23.2 `ak.realm.create` reducer projection 闭包与 genesis `state_root`

`vector_id`: `ak.vector.event_kind.realm_create_projection_closure.v1`

Steps:

1. 提交普通 Realm 的 bootstrap batch：`ak.realm.create`（wire 上唯一必需 Event，v1 无 founding grant 槽位），可选跟随 [`realm-and-space.md`](../models/realm-and-space.md) §2.5 白名单内的同批 follow-up facet。
2. 两个独立实现各自按 `contract-registry.json` 的 `ak.realm.create` `cell_writes[]` 派生并应用 reducer projection，再重算 genesis Seal 的治理 `state_root`。

Expected:

- create Event 的 reducer 输出 MUST 恰好含五条：`ak.component.realm.metadata.v1:null`（`set`）、`ak.component.member.state.v1:<created_by>`（`transition` `leave -> join`）、`ak.component.realm.create.v1:null`（`append`，`issuer_seq=0`）、`ak.component.notary.v1:null`（`set`）、`ak.component.realm.authority_root.v1:null`（`set`，值由注册 `value_projection` 从 create payload 派生）。少一条或多一条表示 registry/vector drift，门禁 MUST 失败。
- 两个实现的 genesis `state_root` MUST 逐字节相同（KAT）。
- `ak:cell:ak.component.member.state.v1:<created_by>` MUST 有 inclusion proof；对同一 cell 求 non-membership proof MUST 失败（负例）。
- `ak.component.realm.metadata.v1` MUST 在 genesis Seal 即出现在 leaf 集合中；"仅在首次 `ak.realm.update` 之后才出现"视为不合规（负例）。
- PCR 与 Direct Conversation 两条 bootstrap 分支使用同一 registered projection 集合。
- 负例：实现漏执行任一已登记 write 后重算 `state_root`，MUST 与正例不同并被 `apply_seal` step 11 拒为 `rejected_seal`。

### 23.3 Null cell subject 的 wire 形态与 leaf 顺序

`vector_id`: `ak.vector.event_kind.null_cell_subject_wire_form.v1`

Steps:

1. 对同一组 Realm policy facet Control Move，由两个实现各自派生 cell wire id 并计算 `state_root` leaf 序列。

Expected:

- 每个 `cell_subject: null` family 的 wire subject 段 MUST 逐字节等于字面 ASCII `null`。
- 两个实现 MUST 得到逐字节相同的 leaf 序列与 `state_root`。
- 负例：把 `realm_id`、Realm 角色分类（`collaboration` / `principal_control` / `managed_agent_principal_control`）或任何 payload 派生值写进 subject 段；空末段（`ak:cell:<family>:`）；这些形态 MUST `schema_violation`。

### 23.4 Invite 与 membership cell 的原子绑定

`vector_id`: `ak.vector.invite.membership_transition_atomicity.v1`

Steps:

1. `default_join_rule=invite` 的 Realm 上走完整 create 到 accept 链路。
2. 分别执行 cancel（invitee 拒绝）、revoke、以及以 `reason_code` 表达 expired 的 revoke。

Expected:

- 正例：`member.state` 依次经过 `leave -> invite -> join`；`ak.invite.create` 与 `ak.invite.accept` 各自在同一 Control Move 内同时写 `invite.lifecycle` 与 `member.state`。
- 负例：invitee 在没有 `invite` 前态时提交 `ak.invite.accept` MUST `failed_precondition` / `invalid_membership_transition`（防止实现私自放宽 `leave -> join`）。
- 负例：`ak.invite.cancel{rejected}` 之后 `member.state` MUST 回到 `leave`，且该主体在 `history_visibility=invited` Realm 中不再具备 invite-frontier 读取与 key share 资格。
- 负例：以 expired 为 `reason_code` 的 revoke 之后同上。
- 负例：定向 invite 的 cancel / revoke 缺失 `payload.invitee`，或其值与 invite cell 记录不等，MUST `reducer_projection_failed`。
- 正例：3PID 分支（`third_party_id`，无 `invitee`）的 `ak.invite.create` MUST NOT 投影 `member.state` write（防止过度补写）。
- 负例：对处于 `invite` 的 Realm member cell 直接提交裸 `ak.member.state{ban}` MUST `invalid_membership_transition`。

### 23.5 Call state 正交轴各自成 cell

`vector_id`: `ak.vector.call_state.axis_cell_split.v1`

Steps:

1. 两个 moderator 在同一 CBA basis 上分别用单项 `moderation_delta` 并发 ban 不同目标。
2. 在同一段捕获上并发写 `recording_transition` 的冲突 `to`，随后用 `state_transition` 推进通话主状态到 `ended`。
3. 分别提交只携带一个 `roster_delta`、`moderation_delta` 或 `mute_override` 的 `ak.call.state`，并对 reducer 实现做错误 tag / value / op kind 的 projection mutation。
4. 提交含 `recording_transition.result` 的 ready transition，并分别 mutation FSM transition write 与独立 result-cell set write 的派生逻辑。
5. 二次写入不同的 `focus`，以及省略已 committed `session_focus` 的 focus mode 更新。

Expected:

- 并发 ban MUST 在 `ak.component.call.moderation.v1`（`or_set`）合并，不产生冲突，通话 `state` 轴完全不受影响。
- 冲突的 `recording_transition.to` 只把该段 `ak.component.call.recording.v1` 打入 `⊥` / `failed_bottom`；`ak.component.call.state.v1` 仍可接受 `active -> ended`。段 cell 的 subject 是 `[payload.call_id, payload.recording_transition.recording_id]`，因此另一段捕获（不同 `recording_id`）完全不受影响（正例）。
- `recording_transition` / `transcript_transition` 必须携带 `recording_id`；与该段 `ak.call.recording.start` 的 `recording_id` 不逐字节相同时，写入落在另一个 cell，MUST 以 `recording_state_transition_invalid` 拒绝（不得静默新建一段捕获）。
- roster join / moderation remove 的 OR-Set add tag 必须精确等于本 write 的 canonical dot `ak:event:<event_id>:<write_index>`，value 必须精确等于对应 payload value；leave / restore 的 remove tag 必须精确等于 `observed_dot`。mute override 必须精确 set 完整 `mute_override` 对象。任何无法由 Event 与 registry 唯一导出的投影均 MUST `reducer_projection_failed`。
- capture lifecycle 与 result 是两个独立 target：FSM write 只含精确 `from` / `to`，result write 只 set 完整 result。不得把 result 塞入 transition op，也不得因一个目标冲突冻结另一个轴。
- 未变更的轴不得由 reducer contract 命中；把未变更轴派生为 same-value write 视为不合规（负例）。
- `focus` projected write 必须 set 完整 focus 对象；`session_focus` 二次写入不同值或 mode 更新时省略已 committed focus 均 MUST 以 `session_focus_already_committed` 失败（`ak.component.call.focus.v1` 的 CAS 负例）。
- 保留既有语义：同 basis 两条 `state` sibling 写不同 `to` MUST 落 `⊥` / `failed_bottom`。

### 23.6 Join gate 三轴正交性

`vector_id`: `ak.vector.join_policy.gate_axis_orthogonality.v1`

Steps:

1. `default_join_rule=invite` + `principal_admission` denylist 命中的 principal 走 invite 流程。
2. `default_join_rule=public` + `cooldown` gate，在冷却期内重新 join。
3. `default_join_rule=closed` 下分别提交 applicant 自助 join 与 `ak.realm.admin` 写入。
4. DM Realm bootstrap batch 端到端。

Expected:

- 负例：denylist 命中的 principal 的 `ak.invite.create` 与 `ak.invite.accept` MUST fail closed，对外统一 `gate_check_failed`。
- 负例：`public` Realm 上冷却期内重新 join MUST 被拒。
- 一负一正：`closed` 下 applicant 自助 join MUST 被拒；`ak.realm.admin` 写入 MUST 通过。
- 正例：DM Realm 的 create + peer join batch MUST 成功，最终 active member count = 2。
- 负例：向已 active 的 DM Realm 加第三人 MUST 被拒。

### 23.7 Quarantine 不可区分等价类

`vector_id`: `ak.vector.invite.quarantine_disclosure_indistinguishable.v1`

Steps:

1. default consent profile + 高信任 evidence + holder 无 active invite grant，投递 invite。
2. 对同一 `(requester, holder)` 分别触发：限速静默丢弃、TTL 超时丢弃、holder 不存在、holder policy deny。
3. 对同一输入分别经 invite delivery、contact delivery 与 `ak.self.consent.command.request` 三条通道观测。

Expected:

- 五种情形的响应体与状态码 MUST 逐字节相同，timing 差 ≤ 50ms。
- quarantine MUST 表示为 `status="deferred"` 且不携带 `disclosed_outcome`。
- 负例：响应携带 `disclosed_outcome="quarantined"` 视为不合规；该值不在枚举内。
- 三条通道的可观察量 MUST 互不能用于区分 quarantine 与拒绝。

### 23.8 Direct Conversation materialization draft 可居住性

`vector_id`: `ak.vector.contact.direct_materialization_witness.v1`

Steps:

1. 构造一个完整合法的 `direct_conversation_materialization` outcome，并对 `contact-operations.schema.json` 校验。

Expected:

- 正例存在：`peer_member_event.kind="ak.member.state"` 且 envelope `proofs=[]` MUST 校验通过；其 `authorization_ref` 是与同批 `realm_event` 绑定的 staged authority-root ref。
- 四个 draft slot 各自的 `kind` 是 const；互换任意两个 slot MUST `schema_violation`（负例）。
- 缺失 `peer_member_event`、非空 envelope `proofs` MUST `schema_violation`（负例）。

### 23.9 3PID claim 过期判定的 canonical 时点

`vector_id`: `ak.vector.invite.claim_expiry_canonical_time.v1`

Steps:

1. 同一条已签名 `ak.invite.claim` 在两个不同本地时钟（过期前 / 过期后）的 receiver 上求值与重放。

Expected:

- 两次求值 MUST 得到相同 outcome 与相同 invite cell value：判定只用签名 `created_at` 与 `expires_at`，MUST NOT 使用 receiver 本地 `now`。
- 被拒绝的 claim MUST NOT 产生任何共享 projected write：invite cell 保持其最后 accepted 状态。
- 负例：由被拒 claim 的处理路径写出 `pending -> expired` 视为不合规；该 transition MUST 由独立 accepted Control Move 承载。

### 23.10 Device pairing challenge transcript

`vector_id`: `ak.vector.device_pairing.challenge_transcript.v1`

Steps:

1. 走完整 stage 到 gate 的 round-trip，并对同一 `new_device_pubkey` 全程比较 canonical bytes 与 digest。

Expected:

- 正例：proof 覆盖 `ak.device-pairing.challenge.v1` transcript 的全部 member，verifier 独立重算 transcript 后验签通过。
- 正例：同一 `new_device_pubkey` object 的 canonical bytes 与 `new_device_pubkey_digest` 在 stage / resolve / gate 三处逐字节不变。
- 负例：坏 `gate_audience`、坏 `request_canonical_digest`、旧 `pairing_code`、跨 request 重放、过期窗口外、改 key、坏签名、proof `kid` 与 `new_device_pubkey.kid` 不等、proof 使用已废弃的 `verification_method` 字段名承载 device key id、路径 A 的 proof 用于路径 B，一律 MUST 拒绝。
- 负例：正文旧示例形态 `{kid, alg, public_key}` MUST 被 canonical `PublicKey` schema 拒绝（缺 `kty` / 缺 `key` / 多余 `public_key`）。
- 负例：stage 请求携带 challenge proof MUST `schema_violation`（proof 必须承诺 stage 才铸出的值，因此不可能在 stage 时存在）。
- 负例：`ak.gate.account.command.pair_device` 同时携带 `device_pairing_request_id` 与 `challenge_transcript`，或两者都不携带，MUST `schema_violation`（schema 以 `oneOf` 强制该 XOR，gate 必须确定该用哪套 transcript）。
- 负例：路径 B 下 gate 采用请求体提供的 `gate_audience` 而非自身 origin，视为不合规——那会让跨 Account Authority 重放重新成立。

### 23.11 RSVP typed composite subject 与 `mv_register` 收敛

`vector_id`: `ak.vector.calendar.rsvp_composite_subject.v1`

Steps:

1. 分别构造 instance RSVP 与 `occurrence=null` 的 series RSVP，从 registry 显式读取 `payload.event_ref`、`payload.occurrence`、`envelope.actor_id`。
2. 对 components array 做 canonical JSON 编码并计算 SHA-256 / base64url-nopad subject。
3. 对同一 responder 构造因果后继与真正并发的不同 status 写入。

Expected:

- instance preimage `["ak:strand:019f9e50-d787-74e0-8731-c9ad5eaa9182","2026-07-26T09:00:00[Asia/Shanghai]","did:webvh:z6mkfixture:alice.example"]` 的 subject MUST 为 `tc2S5LQybi5y3tI-hoyB6HoBWFepT_tDfFcmHJk_jd0`。
- series preimage `["ak:strand:019f9e50-d787-74e0-8731-c9ad5eaa9182",null,"did:webvh:z6mkfixture:alice.example"]` 的 subject MUST 为 `3iBI9bjQLklvfcVhQeaxLajMskSVG4oZ5IMpU62GvRc`；把 JSON null 改写成字符串、空串或 sentinel MUST 失败。
- 缺失 component、未登记 `envelope.*`、裸字段来源、object/array/小数终点、以及 schema 不允许 null 的字段实际取 null，均 MUST `schema_violation`。
- payload 中出现同名 `actor_id` 不得遮蔽 `envelope.actor_id`；components 重排 MUST 产生不同 subject。
- 因果后继 status 支配旧 head；真正并发的不同 status 暴露多个 heads。交换两条并发 Event 的 HLC 大小不得改变 join 结果。

### 23.12 Federation CBA 前置闭包、dependency resolve 与 partial retry

`vector_id`: `ak.vector.federation.seal_prerequisite_closure.v1`、
`ak.vector.federation.seal_partial_retry.v1`、
`ak.vector.federation.cba_dependency_resolve.v1`

Steps:

1. 在 receiver 已有零个、部分或全部 predecessor Seal 的三种状态下，提交同一 Realm 的
   `旧 Control Move → Seal S0 → 以 S0 为 seal_basis 的新 Control Move → Seal S1 →
   引用 S1 的 DataEvent`。bundle 根为 `seal_basis.leaves[] ∪ seal_ref`；各数组按自身
   canonical id/digest 的 UTF-8 bytes 严格递增，可携带从 target 可达的有界超集。
2. 分别删除 target Seal、一个 receiver 不持有的 predecessor、一个 Seal delta 覆盖的
   Control Move；构造“Control Move 的 basis 根 Seal 反向覆盖该 Event 自身”的循环；再分别
   篡改 signature、Realm、任一 root，并构造乱序、重复、不可达对象。
3. 构造一个完整独立 Event 与一个缺依赖 Event 的普通批次、全缺依赖普通批次，以及缺依赖的
   注册 founding unit；验证 typed missing sets 与 `accepted[] ∪ duplicate[]` 求差。
4. 使用 `PeerEventsResolveRequestBody` 分别请求 Event ID、Event digest 与 Seal ref；覆盖有界
   超集、selector 乱序/重复、成功响应遗漏 selector、不可见/不存在合并、response budget
   无法装入完整核算、missing set 不缩小、第 9 轮 fetch，以及 resolve 后未重新 submit 的状态。

Expected:

- 正例 MUST 按依赖拓扑交替接受 Control Move 与投影其 basis/后继 Seal，最后验证 DataEvent；
  只携带 `seal_ref` closure 而遗漏新 Control Move 所需的非本地 `seal_basis` 根 MUST
  `dependency_missing`。bundle/resolve 本身不得推进 Event、Seal、actor 或 Realm frontier。
- 缺 Event ID / Event digest / target Seal / 非本地 predecessor 分别产生非空且精确的
  `missing_event_ids[]` / `missing_event_digests[]` / `missing_seal_refs[]`，逐项 reason 固定为
  `dependency_missing`。Event/Seal 循环必须永久 `schema_violation`；signature、Realm、ID 或
  root 不匹配是永久失败，不得伪装为依赖缺失。
- 普通批次 MUST 继续接受独立完整项并返回 HTTP 200 `partial`；全缺依赖仍为 `partial` 且允许
  `accepted[]` / `duplicate[]` 为空。注册 founding unit MUST 零写入并整体返回 HTTP 409
  `dependency_missing`，其 `error.details` 必须通过 `EventsDependencyMissingProblem`。
- 同批未 sealed grant 不得授权后续 DataEvent。receiver 不得通过静默排序、去重或丢弃不可达
  对象修复非法 wire；合法超集不得因不是字节级最小而被拒绝。
- 收到任何 submit 响应后的 retry MUST 使用新 `Idempotency-Key` 并重算外层两个 digest 与
  HTTP signature；只有完全未收到响应的逐字节 transport retry 才复用旧 key。
- dependency resolve 必须保持只读；不存在与不可披露 selector 外部不可区分。成功轮必须严格
  缩小 missing 三元组，最多连续 8 轮；每个 selector 必须由返回对象或同类型 missing 集合
  完整核算，response budget 无法装入完整核算时必须整体 `limit_exceeded`，不得 partial、
  静默省略或把预算裁剪伪装成 missing。resolve 完成 closure 后仍须以新 key 重新 submit，
  不能异步接受原 Event。

### 23.13 Realm-key withheld policy basis

`vector_id`: `ak.vector.realm_key.withheld_policy_basis.v1`

Steps:

1. 对六个 registered `withheld_reason_code` 分别构造 member-device withheld，并在 Event 的 CBA/T0 basis 上解析唯一 effective refusal-policy root 与 source authorization。
2. 分别缺失、篡改、过期 `policy_digest`，替换为 receiver 当前 root、零值或实现占位；再构造多 root 歧义与缺失/错 scope/错 device 的 `source_authorization_ref`。

Expected:

- 正例的 `policy_digest` MUST 等于作出相应拒绝决定时实际求值的 root，且 source authorization 覆盖同一 recipient、device、scope 与 decision。
- 任一负例 MUST 以 `late_recovery_share_not_authorized` fail closed；不得把未授权 withheld 写入 terminal delivery projection。

### 23.14 Realm-key sender-device signature transcript

`vector_id`: `ak.vector.realm_key.share_sender_signature.v1`

Steps:

1. 分别构造 member-device 与 realm-recovery-key share，按 `context="ak.realm-key-share-sender-proof-v1"` 生成 canonical JSON UTF-8 transcript。
2. 对 inactive target branch、inactive material branch 与缺省 optional 字段验证“省略而非 null”；再逐项篡改 expiry、source authorization、key scope、target 与 signer device。

Expected:

- 两个正例 MUST 由 SDK 唯一 helper 生成逐字相同 bytes，并由 receiver helper 重建后验签通过。
- 未选字段写 null、交叉 target、双 material、无 material、任一 covered 字段被篡改、或 signature key 与 accepted `sender_device_id` 不匹配，均 MUST `invalid_signature`。

## 24. Calendar / RSVP normative closure vectors

本节向量由 [`calendar-rsvp-fixture.json`](../../artifacts/fixtures/calendar-rsvp-fixture.json) 承载，规则正文见 [`../models/calendar-event.md`](../models/calendar-event.md)。fixture 的 `schema_validation_cases` 由 artifact lint 直接执行，`semantic_cases` 由 conformance runner 执行。

### 24.1 Calendar schema activation

`vector_id`: `ak.vector.calendar.profile_activation.v1`

Steps:

1. 构造 `schema_refs` 含 `ak.schema.calendar_event.v1` 且携带 `metadata.fields.calendar` 的正例。
2. 分别构造只有 ref、只有子树、`schema_refs` 含容器 self-schema、`metadata.fields.profile` / `profile_refs`、以及扁平 `metadata.fields.start` 等负例。
3. 构造只移除 ref 或只移除子树的 post-patch 负例，以及缺 `requirements.schema[]` 绑定的写入。

Expected:

- 正例 MUST 通过 `strand.schema.json`；四类激活替代形态 MUST `schema_violation`。
- 单向缺失 MUST 以 `calendar_activation_mismatch` 拒绝，无论缺的是 ref 还是子树。
- replay MUST 使用 Event 的 `requirements.schema[]` 绑定，MUST NOT 使用对象当前 `schema_refs[]`。

### 24.2 Schedule 形态与半开区间

`vector_id`: `ak.vector.calendar.schedule_shape.v1`

Steps:

1. 构造 all-day（`date`）与 timed（整秒 LocalDateTime）两个正例。
2. 构造混型、UTC timestamp、UTC offset、小数秒、缺 `status`、`end == start` 的负例。

Expected:

- `all_day` MUST 唯一决定 `start` / `end` / `recurrence.until` 的分支。
- 区间是 `[start, end)`，`end` MUST 严格晚于 `start`；跨字段比较由 reducer 以 `schema_violation` 承载。

### 24.3 Recurrence 展开

`vector_id`: `ak.vector.calendar.recurrence_expansion.v1`

Steps:

1. 展开缺 `by_day` 的 weekly、缺 `by_month_day` 的 monthly 与缺省 yearly 规则。
2. 构造 base start 不匹配 `by_*` 的规则并检查首个 occurrence 与 `count` 计数。
3. 触发 candidate-period 扫描预算，再在 schedule revision 变化后复用 continuation。

Expected:

- 隐式 filter MUST 由同一 expansion 算法补齐；base start MUST 是第一个 occurrence 并计入 `count`。
- 预算耗尽 MUST 返回带 continuation 的 `limit_exceeded`；basis 改变后旧 cursor MUST `invalid_cursor`。

### 24.4 DST 不连续

`vector_id`: `ak.vector.calendar.recurrence_dst.v1`

Steps:

1. 在 spring-forward gap 与 fall-back fold 各构造一个每日 local 时间事件。
2. 跨 transition 展开并比较 local key 与派生 instant。

Expected:

- gap 与 fold 都 MUST 使用 transition **之前**的 offset；fold MUST 只产生一个 occurrence；local wall-clock key MUST 不漂移。

### 24.5 TZDB identity

`vector_id`: `ak.vector.calendar.tzdb_identity.v1`

Steps:

1. 用 `UTC` 等 Link alias 作为 wire `timezone`；再用 canonical Zone 作为正例。
2. 构造 `tzdb_version` 超出 `ServiceDescribe.calendar_tzdb_versions` 的 schedule。
3. 显式把 schedule 从一个 release 更新到另一个 release。

Expected:

- 未归一化的 alias MUST 被拒绝，receiver MUST NOT 自行改写签名值。
- 未知 release MUST `calendar_tzdb_mismatch` 或标记 `unresolved`，MUST NOT 回退到相近版本。
- release 变更 MUST NOT 改变 `timezone` 与 local occurrence key；派生 instant 变化 MUST 触发 `needs_reconfirmation`。

### 24.6 未支持 recurrence 能力

`vector_id`: `ak.vector.calendar.recurrence_unsupported.v1`

Steps:

1. 构造 `recurrenceOverrides`、`excludedRecurrenceRules`、RDATE / EXDATE 与 JSCalendar `@type` 成员。

Expected:

- 全部 MUST 以 schema reject 或 `unsupported_feature` fail closed，MUST NOT 静默忽略。

### 24.7 Schedule revision 与 identity

`vector_id`: `ak.vector.calendar.schedule_revision.v1`

Steps:

1. 修改 `start` 后检查旧 instance 与 series RSVP 的分类。
2. 构造两个 canonical bytes 不同的并发 schedule head，再构造两个取值相同的并发 head。
3. 只修改 `metadata.title` 并重算 frontier。

Expected:

- identity-affecting 修改 MUST 把旧 instance RSVP 标为 `stale_orphaned` 且 MUST NOT 自动迁移；series RSVP MUST 标 `needs_reconfirmation`。
- 取值不同 MUST `conflict`，此时 authoring client MUST 以 `calendar_schedule_unsettled` 拒绝构造新 RSVP；取值相同 MUST `settled` 且保留全部 canonical heads。
- settledness MUST NOT 成为服务端 admission 条件：把同一组 Event 分别喂给 E2EE 与 plaintext 服务端，二者 accepted set MUST 逐项相同。
- 非 Calendar 子树的 update MUST NOT 产生新 schedule revision。

### 24.8 RSVP reducer projection

`vector_id`: `ak.vector.calendar.rsvp_reducer_projection.v1`

Steps:

1. 提交只含已注册 `kind + payload` 的合规 `ak.rsvp.set`。
2. 分别对 reducer 做缺失注册写、额外写未注册目标、投影值不等于 `payload.entry` 的实现级 mutation。

Expected:

- receiver MUST 按 registry 的 `effect_projection = set(payload.entry)` 唯一派生 reducer projection；三类实现级 mutation 均 MUST `reducer_projection_failed`，且 wire Event 不得携带 producer-selected write。

### 24.9 RSVP effective projection

`vector_id`: `ak.vector.calendar.rsvp_effective_projection.v1`

Steps:

1. 对同一 occurrence 同时构造 series 与 instance head。
2. 构造因果后继并交换到达顺序与 HLC 大小。
3. 构造缺 key、解密失败、以及 plaintext 相同但 ciphertext 不同的并发 head。

Expected:

- instance MUST 覆盖 series 且二者 MUST NOT union；后继 MUST 支配旧 head 且结果与到达顺序无关。
- 缺 key MUST 标 `encrypted_unresolved`，MUST NOT 伪造 status；plaintext 相同 MUST NOT 判为 conflict。

### 24.10 RSVP admission

`vector_id`: `ak.vector.calendar.rsvp_admission.v1`

Steps:

1. 构造 attendee 无 capability、非 attendee 有 capability 两个对照。
2. 构造 `status=cancelled`、basis 为空 / 重复 / 乱序 / 不在 `causal_refs[]`、basis 部分未到达、frontier 超 128 的用例。
3. 构造形态匹配但日期不存在的 all-day / timed occurrence（如 `2026-02-30`）以及 target 不存在 / 不可见 / 跨 Realm / 非 Calendar 四种情况。
4. 把同一组 Event 分别喂给 E2EE Realm 与 plaintext Realm，比较两侧 accepted set。

Expected:

- capability 是唯一授权真源；attendee 身份 MUST NOT 自动授权，非 attendee 持证 MUST 被接受。
- cancelled MUST 由 authoring client 以 `calendar_event_cancelled` 拒绝（不是服务端 admission，理由同 settledness）；basis shape 违例 MUST `rsvp_basis_not_causal` 且 MUST NOT 进入 pending；不存在的 Gregorian occurrence 日期 MUST `rsvp_occurrence_not_canonical`；被引用 Event 未到达 MUST 以 `dependency_missing` pending；wire 上超过 128 项的 basis MUST 由 schema `maxItems` 以 `schema_violation` 拒绝，而 observed frontier 超限是 authoring 侧的 `schedule_frontier_too_large`。
- 四种 target 情况的对外错误 MUST 不可区分。
- 两侧 accepted set MUST 逐项相同：target admission 只读被引用 Event 的明文 envelope，"该 revision 是否真的改了 schedule / 是否等于 authoring frontier"只在授权投影里表现为 `unresolved_basis` 或 stale，能读明文的服务 MUST NOT 因此多拒绝。

### 24.11 Attendee roster

`vector_id`: `ak.vector.calendar.attendee_roster.v1`

Steps:

1. 构造重复 `actor_id`、两个 `organizer`、省略 `role` 的用例。
2. 把无读取权 actor 加入 roster 后重算访问与通知。

Expected:

- 重复 actor 与多 organizer MUST `schema_violation`；省略 `role` MUST 等价于 `required`。
- roster 变更 MUST NOT 创建 membership、扩大 history access 或产生通知 / push wakeup。

### 24.12 Schedule notification

`vector_id`: `ak.vector.calendar.notification.v1`

Steps:

1. 用一次 patch 同时修改多个 schedule 字段。
2. 构造一次同时增删 attendee 的 patch。
3. 在加密 metadata 下派生通知；再对一次 `ak.rsvp.set` 派生通知。

Expected:

- 每个 receiver MUST 只得到一条 `notification_kind=schedule`，按 `(actor_id, source_event_id, notification_kind)` 去重。
- 候选集 MUST 是 pre/post roster 并集，并在生成前按 access / mute / DND / push rule 过滤。
- 加密 schedule MUST 只产生 profile 定义的 blind wakeup；RSVP 变更 MUST NOT 产生 schedule notification。

### 24.13 RSVP 隐私分支

`vector_id`: `ak.vector.calendar.rsvp_privacy.v1`

Steps:

1. 在 `e2ee_required` floor 下提交明文 `entry.response`。
2. 在允许 plaintext 的 floor 下构造四种授权组合：Realm policy 与 ServiceDescribe 都声明 `rsvp_response`、只有 Realm policy 声明、只有 ServiceDescribe 声明、两侧都未声明。
3. 在 `e2ee_required` floor 下让客户端缺少 scope key。
4. 构造 `encrypted_response` 携带非 `application/vnd.arkret.calendar-rsvp-response+json` 的 `content_type`。

Expected:

- e2ee floor 下明文分支 MUST `schema_violation`；缺 key MUST `unsupported_feature` 而非降级明文。
- 明文分支需要**双重授权**：只有 Realm policy（`event-payload.schema.json#/$defs/plaintext_data_class`）与 ServiceDescribe（`plaintext_visibility.data_classes`）都声明 `rsvp_response` 才合法；其余三种组合 MUST `unsupported_feature`。仅 ServiceDescribe 单侧声明不构成合法授权。
- `encrypted_response` 的 `content_type` 由 schema `const` 固定，错误 media type MUST `schema_violation`，使同一 ciphertext 只能路由到唯一解密 schema。
- `event_ref`、`occurrence`、`schedule_basis_refs`、responder actor 与 ciphertext size MUST 出现在 privacy disclosure 中。

## 25. Long Text Content Block closure vectors

本节由 [`long-text-content-fixture.json`](../../artifacts/fixtures/long-text-content-fixture.json) 承载，规则正文见 [`../models/content-types.md` §4.1](../models/content-types.md) 与 [`../crypto-media/media-and-blob.md` §3](../crypto-media/media-and-blob.md)。

### 25.1 UTF-8 byte boundary 与选择唯一性

`vector_id`: `ak.vector.content.long_text_boundaries.v1`

Runner MUST 生成 256 KiB−1、256 KiB、256 KiB+1 的规范化源正文，以及 4 KiB−1、4 KiB、4 KiB+1 的 fallback；每组都必须包含多字节 Unicode scalar 落在边界附近的用例。测量对象是规范化后的 UTF-8 bytes，不是 code point、JSON escaped bytes、ciphertext 或压缩长度。正文超过 256 KiB 时只允许 `ak.content.long_text`；较小正文只有在完整 Event 否则超过 1 MiB 时才能使用 long text，该例外必须由完整 Event size validator 证明。

plaintext descriptor 还 MUST 覆盖 hash-only `blob_ref`、Blob metadata digest、下载正文重算 digest、声明 size 与 `format ↔ media_type` 一致；UUID ref、带 charset 参数 media type、任一 digest/size 不一致都必须拒绝。

### 25.2 规范化、line count 与 fallback

`vector_id`: `ak.vector.content.long_text_normalization.v1`

Runner MUST 覆盖 empty、末尾有/无 LF、多行、CRLF、bare CR、BOM、TAB、禁用 C0/DEL 与 canonical-equivalent 但 scalar sequence 不同的 Unicode 输入。producer 先把 CRLF/CR 归一为 LF，再计算 digest/size/line count；不得 NFC/NFKC 改写。`prefix` 必须从 byte 0 开始并只在 scalar 边界截断；`summary` 可不等于前缀，但 UI 必须标注为摘要且不得与全文拼接。

### 25.3 E2EE stream descriptor

`vector_id`: `ak.vector.content.long_text_e2ee.v1`

Runner MUST 验证 `scheme=ak.blob.stream_aead.v1`、`alg` 为 `_stream` 算法、hash-addressed ciphertext Blob、`segment_count=ceil(size_bytes/segment_bytes)`、逐段 tag、顺序、末段与完整 ciphertext digest。whole-file AEAD、段数不一致、重排、截断或任一 digest 不符必须 fail closed；全部段验证前不得把正文标记为完整。

### 25.4 生命周期闭包

`vector_id`: `ak.vector.content.long_text_lifecycle.v1`

Message redaction、expiry 或 Blob access revoke 必须同步使 fallback、完整正文、partial/full search index、cache 与 Blob authorization 失效；Blob GC 仍按引用追踪。push provider 不得收到全文，mention 通知不得要求服务端扫描 Blob。

## 26. Signal peer relay closure vector

`vector_id`: `ak.vector.signal.peer_relay.v1`

本向量由 [`signal-federation-fixture.json`](../../artifacts/fixtures/signal-federation-fixture.json) 承载，规则正文见 [`../sync/signal.md` §4](../sync/signal.md) 与 [`../sync/federation.md` §4.0.3](../sync/federation.md)。

Runner MUST 覆盖：

1. 原 producer-signed encrypted `SignalEnvelope` 经一个 source → destination peer hop 后，ciphertext、proof 与 envelope digest identity 不变；
2. `signals[]` 127/128/129、canonical request body 1 MiB−1/1 MiB/1 MiB+1、HTTP Message Signature `expires-created` 4,999/5,000/5,001 ms；
3. request `realm_id` 与任一 envelope/scope Realm 不一致、第二 peer hop、source 不托管 sender、destination 不在 active member delivery binding、producer proof/Seal/TTL/AAD 无效；
4. 有 eligible local recipient 与无 eligible local recipient 的已认证合法 request 都返回逐字相同 `{"accepted":true}`，且无 count/per-item outcome；
5. response 丢失时 source 不自动重放，不携带 `Idempotency-Key`，按 `drop_unconfirmed` 丢弃不确定结果；
6. peer/live/local rails 重复、乱序或丢失不写 durable Event、不推进 actor sequence / Realm frontier，consumer 依靠下一自足 signal 或产品级 timeout/renegotiation 恢复；
7. source/destination 改写、重签、解密重加密 envelope，以及 destination 再转发第三 peer，全部 fail closed。

## 27. Signal Message streaming closure vector

`vector_id`: `ak.vector.signal.message_stream.v1`

本向量由
[`signal-message-stream-fixture.json`](../../artifacts/fixtures/signal-message-stream-fixture.json)
承载，规则正文见 [`../sync/signal.md` §7](../sync/signal.md#7-message-正文流式预览-payload-profile)
与 [`../models/strand-and-message.md` §9](../models/strand-and-message.md#9-message)。

Runner MUST 覆盖：

1. `seq=0` keyframe、连续 delta、丢帧、重复、乱序、无效 `base_seq` 与后续自愈 keyframe；
2. 大 attempt 只能由 `seq=0` keyframe 激活，迟到小 attempt 不回滚，同 attempt 第二
   `stream_id` 冻结 preview；
3. UTF-8 preview 16 KiB−1/16 KiB/16 KiB+1、增长比 2 边界、15 秒 keyframe 边界、
   truncated 后周期 keyframe，以及最大 quote/backslash JSON 转义仍装入 48/64 KiB Signal
   两层上限；
4. `message_id` 等于 planned create `event_id` 的重类型 UUID；create payload 出现
   `message_id` 必须 `schema_violation`；
5. direct final 的 actor/device/security scope/Realm/Strand/track 任一不匹配，或 final
   携带 `executed_by` 时，不得绑定 preview；全部匹配时 final 立即替换并终止所有 attempts；
6. preview 永不写 durable Event、Content Block、cursor、replay cache 或 reducer state。

## 28. Agent signer evidence closure vector

`vector_id`: `ak.vector.agent.signer_evidence_binding.v1`

runner MUST 执行 `agent-signer-evidence-fixture.json` 的完整 `binding_vector` 与全部 case：重算
controller proof signing input、binding digest、accepted state / transition witness 与 freshness
边界，并覆盖 active、revoked、superseded、unresolved 及字段篡改分支。只加载 fixture、只验证来源服务
签名或跳过任一 case 均不构成通过。

## 29. Actor accountability grant closure vector

`vector_id`: `ak.vector.actor.accountability_grant_required.v1`

runner MUST 执行 `privacy-security-fixture.json` 的 Actor Profile accountability case：

- `ak.profile.create` / `ak.profile.update` 的 `accountable_principal_ids[]` 任一 DID 缺少 active、
  未过期且 subject/issuer 匹配的 `ak.identity.accountability_grant` 时，整个 Event MUST
  `failed_precondition`、`reason_code=accountability_grant_missing`，Profile cell 保持不变；
- 所有 grant 有效时，写入值 MUST 与签名 payload 精确一致；
- 接受 Event 后 grant 才过期或 revoked 时，既有投影可降级为 `unverified`，但下一次仍携带该
  条目的 Profile 写入必须拒绝；
- 任何“接受 Event，但从数组剔除无 grant 条目后再写入”的结果均不符合本向量。

## 30. cas_register supersession join closure vector

`vector_id`: `ak.vector.lattice.cas_register_supersession.v1`

规则正文见 [`../authz/event-auth-state-resolution.md` §9.3.1](../authz/event-auth-state-resolution.md)。

Runner MUST 覆盖：

1. 顺序治理生命周期 declaration → whole-value `head_eq` tombstone → 再 declaration 的三个
   set op join 到单一终值，不落 `⊥`（policy-server §2.2 标准流程即正例）；
2. 同一前驱（相同 `from`）上的两个不同值 set 形成两条极大链，join 为 `⊥`，`bottom=reject`
   cell 物化 `failed_bottom`；
3. 非链首 op 的 `from` 不匹配集合内任何 op 的 value（悬空取代）时 join 为 `⊥` fail closed；
4. 同 `(value, from)` 的重复 set 幂等去重，不产生第二条链；
5. value 复用（ABA）按 value 绑定语义收敛到最长链终值；带单调分量（如 `policy_revision`）
   的 family 不产生歧义；
6. 任意 prefix-closed 覆盖子集重算 join 得到该子集的确定性历史 view。

## 31. Key backup delete authority closure vector

`vector_id`: `ak.vector.key_backup.delete_authority.v1`

规则正文见 [`../identity/key-management.md` §7.8 / §7.8.1](../identity/key-management.md)。
Runner MUST 覆盖 §7.8.1 第 5 条列举的全部正负例：三个 high-risk 分支正例、普通 device proof
删 active tail 被拒、非尾部单删被拒、quorum 去重 / 低于 policy `k` 被拒、recovery session
过期或已消费被拒、challenge 重放 / 过期被拒、篡改 `backup_id` / `reason` / `audience` /
`nonce` 任一 transcript 字段后验签失败，以及逐字节相同重试返回已存 terminal outcome 且不
重新验收已消费 challenge。

## 32. MIMI provider directory signature closure vector

`vector_id`: `ak.vector.mimi.provider_directory_signature.v1`

规则正文见 [`../extensions/mimi-interop.md` §3.1](../extensions/mimi-interop.md)。Runner MUST
覆盖该节列举的正向签名向量与全部负例：缺任一 required 能力或能力数组为空、篡改
endpoint / cipher suite / content profile / room policy、proof controller 与 `service_id`
不同、unknown extension 试图改变路由、过期 `created_at`、dev 摘要冒充签名、HTTP signature
合法但 directory JWS 无效（及反向）。

## 33. Signal device authorization domain closure vector

`vector_id`: `ak.vector.signal.device_authorization_domain.v1`

规则正文见 [`../sync/signal.md` §1 / §3](../sync/signal.md)。Runner MUST 覆盖 §3 conformance
清单的五个 case：授权晚于 `seal_ref` 但 current active 的设备通过设备授权关；`seal_ref` 时
active 但当前 revoked / fenced / conflicted 的设备被拒；`verification_method` 不逐字等于
`{sender_actor_id}#{sender_device_id}` 被拒；current directory key 或 Tier-2 /
service-attested 信任锚缺失被拒；设备 current active 但 sender 无 Realm `seal_ref` 下 scope
资格或 `signal_class` action 被拒。另 MUST 断言 `expires_at` 已过期的 envelope 在 local
ingress 被 `invalid_param` 拒绝。
