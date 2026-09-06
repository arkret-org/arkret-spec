---
title: Conformance Vectors
status: candidate
normative: true
stability: v1
updated: 2026-08-11
---

本文是 v1 conformance 测试向量的人类阅读入口，按域分组呈现核心 normative steps。完整 active vector 集合的机器真相源是 `artifacts/registry/vector-registry.json`；测试 runner MUST 从 registry 的 `source_refs` 加载本文件、领域文档与 fixture，不得假定本文件正文穷尽列出所有 vector id。

`ak.vector.identity.station_admission.v1` 覆盖 `AccountId` 终身单 account / 单 PCR genesis 唯一性：deactivation 后同一 Station replacement account 仍拒绝；deployment policy 可拒绝 reactivation，policy allow 也必须在 completed PCR recovery closure 后只恢复原 account/PCR 并绑定更高 device generation；另一 Station 完整 onboarding 是独立选择而非强制恢复路径。该向量还覆盖 Event 完整 `ActorId` 的 producer 签名、由实际 author ActorId 唯一导出的 origin service、producer proof 精确绑定、pending/revoked 拒绝与 replica 原样保留。测试器 MUST 运行 `station-admission-fixture.json` 的全部 semantic cases；任何以裸 principal/PCR identifier 比较外部 account equality、deactivation 后释放同 pair uniqueness、用 account auth/admin 绕过 PCR recovery、复活旧 generation 资源、接收服务重签或独立 signer-evidence sidecar 都不合格。

1. Encoding & Crypto（canonical JSON、digest、signature binding、HLC、cursor、encrypted envelope）
2. CBA · Lattice（DataEvent acceptance、Control Move Seal finality、cas_register、Seal DAG）
3. Redaction（约束与可见性）
4. Capability（authority chain、revoke、approval）
5. Sync（client sync、pagination、snapshot、MLS epoch backfill）
6. Space Lifecycle
7. AccountId 身份
8. Handle
9. Security Closure
10. Service Closure
11. Agent & Sidecar
12. Media Service Binding
13. History Visibility / Preview / History Sharing
14. Encryption Floor Ratchet
15. Moderation / Key Backup / Federation Ingress

MIMI Provider Facade 的 active interop vector 集合与数量以 [`vector-registry.json`](../../artifacts/registry/vector-registry.json) 中 active 的 `ak.vector.mimi.*` 登记为唯一权威；详细语义见 [`mimi-interop.md`](../extensions/mimi-interop.md)，可执行数据见 [`mimi-interop-fixture.json`](../../artifacts/fixtures/mimi-interop-fixture.json)。

可执行向量数据集位于 [`spec/v1/artifacts/fixtures/`](../../artifacts/fixtures/)；
本文档把对应规范条款与文件入口集中呈现，便于一致性测试 runner 引用。
所有 `ak.vector.*` 标识符的机器索引位于 [`vector-registry.json`](../../artifacts/registry/vector-registry.json)；新增、删除或重命名向量时 MUST 同步更新该 registry，并通过 `tools/artifact_pipeline.py check` 的闭包校验。领域文档中定义的向量（例如 Directory / PSI / Search）只要在 registry `source_refs` 中登记，即属于同一 conformance suite。

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [normative-language.md](./normative-language.md) 解释；仅大写形式具规范约束力。

形式化 proof obligations 至少 SHOULD 覆盖：

- CBA / open_set 多 leaf 下 per-cell lattice join `J(L)` 是纯函数，且与输入顺序、接收方、墙钟无关；所有 conformant reducer 对同一 accepted Seal frontier 收敛到同一 cell value。
- 并发分支撤销 fail closed：grant / capability revoke 与被授权 Event 并发时，joined control view MUST 重判并拒绝不再满足授权的 Event。
- Capability authority 单调衰减：`child.actions ⊆ issuer authority actions`、resource selector 不放宽、约束不放宽、`authority_expiry_seal` 只能收窄或固定，不能被 child grant 延长。
- Authority graph 无环，且环检测在并发分支合并、离线 replay 与 migration context 下结果一致。
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
{"event_id":"ak:event:AQsHmGu_9sPOyJ4aG8VlWQBp8wGGhdC-BjfAaXqrIbk-","event_id":"ak:event:AR8bu-n-kOOB3nRUvYuIEglCX5B-JpFaNTex9gxs_cWY"}
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

digest preimage 是去除 `proofs`、`unsigned`、`actor_kind` 与 `event_id` 后的 Event Envelope
（[`encoding.md` §3](./encoding.md)）。`event_id` 由该 digest 一次前向派生，因此 **MUST NOT** 出现在
preimage 中：

```json
{
  "kind": "ak.message.create",
  "realm_id": "ak:realm:ATH75ame6bMfYpXtcoLOVb7FKmgpWVniZZqVBz1dUdQa",
  "scope_ref": {
    "kind": "realm",
    "realm_id": "ak:realm:ATH75ame6bMfYpXtcoLOVb7FKmgpWVniZZqVBz1dUdQa"
  },
  "actor_id": "ak:did_core:webvh:z6mkfixture",
  "actor_seq": 1,
  "created_at": "2026-04-26T00:00:00.000Z",
  "hlc": "01970e589d21-0004-a13f9c2e",
  "prev_refs": [],
  "refs": [],
  "seal_ref": "ak:seal:sha256:2222222222222222222222222222222222222222222222222222222222222222",
  "auth_context": {
    "actor_id": "ak:did_core:webvh:z6mkfixture",
    "key_id": "device-1",
    "key_epoch": 1
  },
  "payload": {
    "strand_id": "ak:strand:ATH75ame6bMfYpXtcoLOVb7FKmgpWVniZZqVBz1dUdQa",
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
{"actor_id":"ak:did_core:webvh:z6mkfixture","actor_seq":1,"auth_context":{"key_epoch":1,"key_id":"device-1"},"created_at":"2026-04-26T00:00:00.000Z","hlc":"01970e589d21-0004-a13f9c2e","kind":"ak.message.create","payload":{"content":{"body":"hello","kind":"ak.content.text"},"strand_id":"ak:strand:ATH75ame6bMfYpXtcoLOVb7FKmgpWVniZZqVBz1dUdQa","track_name":"discussion"},"prev_refs":[],"realm_id":"ak:realm:ATH75ame6bMfYpXtcoLOVb7FKmgpWVniZZqVBz1dUdQa","refs":[],"scope_ref":{"kind":"realm","realm_id":"ak:realm:ATH75ame6bMfYpXtcoLOVb7FKmgpWVniZZqVBz1dUdQa"},"seal_ref":"ak:seal:sha256:2222222222222222222222222222222222222222222222222222222222222222"}
```

期望 digest 与由它前向派生的 `event_id`：

```text
sha256:e6a0a930ea002d2ea22b51f854b9effa9b6e6bcdf41fc575140f7d9e159dbf1b
ak:event:AeagqTDqAC0uoitR-FS57_qbbmvN9B_FdRQPfZ4Vnb8b
```

判定规则：

- event digest / proof `event_digest` MUST 从 redaction 前、去除 `proofs` / `unsigned` / `actor_kind` /
  `event_id` 后的 canonical event bytes 派生；`event_id` 是该 digest 的前向派生结果，把它放回 preimage
  会造成不可解的自引用。
- `event_id` 的 33 octets 为 `0x01`（sha256 suite code）拼接完整 32 字节 digest，再做无 padding base64url
  （[`encoding.md` §4](./encoding.md)）。
- 实现 MUST NOT 把 transport envelope、HTTP header、Station sync surface metadata、local receive time 放入 event digest。
- 同一事件在不同 Events API 或 Station sync surface 上 MUST 得到相同 digest。

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
  "issuer": "ak:did_core:webvh:z6mkfixture",
  "scope": {
    "actor_id": "ak:did_core:webvh:z6mkfixture"
  },
  "events": [
    {"event_id": "ak:event:AQsHmGu_9sPOyJ4aG8VlWQBp8wGGhdC-BjfAaXqrIbk-", "kind": "ak.message.create"},
    {"event_id": "ak:event:AR8bu-n-kOOB3nRUvYuIEglCX5B-JpFaNTex9gxs_cWY", "kind": "ak.realm.create"}
  ],
  "created_at": "2026-04-26T00:00:00.000Z"
}
```

期望 canonical bytes 的 UTF-8 文本表示：

```json
{"created_at":"2026-04-26T00:00:00.000Z","events":[{"event_id":"ak:event:AQsHmGu_9sPOyJ4aG8VlWQBp8wGGhdC-BjfAaXqrIbk-","kind":"ak.message.create"},{"event_id":"ak:event:AR8bu-n-kOOB3nRUvYuIEglCX5B-JpFaNTex9gxs_cWY","kind":"ak.realm.create"}],"issuer":"ak:did_core:webvh:z6mkfixture","receipt_id":"ak:receipt:01964186-0000-7000-8000-000000000000","schema":"ak.schema.event_batch_receipt.v1","scope":{"actor_id":"ak:did_core:webvh:z6mkfixture"}}
```

期望 digest：

```text
sha256:c7442ec1ba99031a5fd28fe96124330e006ffdf2a75bac98f18f7be69f63af0f
```

失败条件：

- producer 未先按 `UTF8(canonical_json(item))` 排序去重，或 receiver 接受了非严格升序 / 含重复项的 signed wire 数组。
- fixture 的 reversed+duplicate constructor input 未规范化为与主向量相同的 `events[]` 与 digest。
- proof 字段被包含进 receipt digest。
- `issuer`、`scope`、`events`、`created_at` 或 `schema` 被排除在 digest 外。
- `receipt_id` 大小写被实现私自改写。
- frontier 未严格落入三个 closed branch 之一：typed head（`event_id`）、digest-only head（本向量）或仅含 `actor_seq` / `hlc` 的 coarse observation。尤其同时携带 `event_id` 与 `event_digest` 必须 schema-invalid；typed head 的 digest 只能从 Event ID 解码。

### 1.8 Vector: Signature Binding Payload

向量名称：

```text
ak.vector.encoding.signature_binding_payload.v1
```

签名前的 binding object（其中 `event_digest` 仅为占位值，取自 §1.3 `ak.vector.encoding.canonical_json.basic.v1` 的 digest `sha256:43258cff...`，用于固定本向量的 binding canonical 形态；它**不是** §1.6 真实 event digest——后者以本节同名向量 `ak.vector.encoding.event_digest.v1` 的 `expected_digest` 为唯一真源，本处不再硬编码其字面量。本向量只断言 binding object 的 canonical bytes 与 digest，不要求该 `event_digest` 与任一具体 event 一致）：

```json
{
  "event_digest": "sha256:43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777",
  "actor_id": "ak:did_core:webvh:z6mkfixture",
  "verification_method": "did:webvh:z6mkfixture:alice.example#device-1",
  "created_at": "2026-04-26T00:00:00Z"
}
```

期望 canonical bytes 的 UTF-8 文本表示：

```json
{"actor_id":"ak:did_core:webvh:z6mkfixture","created_at":"2026-04-26T00:00:00Z","event_digest":"sha256:43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777","verification_method":"did:webvh:z6mkfixture:alice.example#device-1"}
```

期望 digest：

```text
sha256:e7e32a7f26654175a2323581e83de4869b8c0b78606a3d52c8f89d714bf6ed6b
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

### 1.8.2 Vector: Proof Context Transcript（逐对象族）

`vector_id` 命名规则（每条 registry row 一个，不逐条抄录）：

```text
ak.vector.proof_context.transcript.<object_family>.v1
```

其中 `<object_family>` 逐字取自 [`proof-context-registry.json`](../../artifacts/registry/proof-context-registry.json)
同一行的 `object_family`。§1.8 / §1.8.1 只固化 `ak.event_proof.v1` 这一族；本组把同样的字节级
要求扩到 `contexts[]` 的**全部** 63 行，构造规则统一由 [`encoding.md` §6.0.2](./encoding.md) 定义，
本节不重述。字节来源是 `proof-context-transcript-fixture.json`，由
`tools/regenerate_proof_context_transcript_fixture.py` 从 registry 与同一把公开测试密钥
（`crypto-signature-fixture.json` / `keypackage-write-transcript-fixture.json` 已发布的
Ed25519 seed）现算，不是手抄。

每条向量的 `cases[i]` MUST byte-for-byte 复现：

- `unsigned_jcs` 与 `unsigned_digest`——unsigned projection 的 canonical bytes 及其 digest；
  `unsigned_projection` 记录被删除的 carrier 成员及其取值，或改为记录被摘要的 `<core>` 成员；
  `binding_fields` 不含 self digest 的族取 `null`，并给出理由；
- `binding_jcs`——binding object 的 canonical bytes：含固定 `"context"` key、全部必备 binding
  field、以及本例保留的 optional field；`omitted_optional_binding_fields` 列出被整体省略的那些，
  它们 MUST NOT 以 `null` 出现；
- `signing_input_ascii` 与 `detached_jws`——`base64url(protected_header)` + `"."` +
  `base64url(binding_jcs)`，以及 payload segment 为空的 compact 形态；
- `expected_result = "accept"`。

`negative_cases[i]` 是同一条向量的**必备**负例：同一份 unsigned body、binding object 只把
`context` 换成 registry 中**相邻一行**（末行回绕到首行）的 context，重新签名。该签名在密码学上
有效，但接收方按本族注册的 context 重建 transcript，因此 MUST 以 `signature_invalid` 拒绝
（`expected_result = "reject"`）。没有该负例的向量不构成 domain separation 保证。

机器门禁 `proof_context_transcripts` 反查两个方向：`contexts[]` 每行 MUST 被恰好一个 active
`ak.vector.proof_context.transcript.*` 覆盖（覆盖关系登记在
[`vector-registry.json`](../../artifacts/registry/vector-registry.json) 的
`covers_proof_contexts[]`），且每条 case 的上述字节 MUST 可由 fixture 自身重算并验签通过。新增
proof context 而不给向量 MUST 直接失败。

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

输入 cursor（schema-valid v1 core wire 形态；body 是 stateful opaque handle
`{v, purpose, issued_at, expires_at, h}`）：

```text
ak:cursor:eyJleHBpcmVzX2F0IjoiMjA5OS0xMi0zMVQyMzo1OTo1OS4wMDBaIiwiaCI6ImFiY2RlZmdoaWprbG1ub3BxcnN0dXYiLCJpc3N1ZWRfYXQiOiIyMDk5LTEyLTMwVDIzOjU5OjU5LjAwMFoiLCJwdXJwb3NlIjoic3RyZWFtIiwidiI6IjEifQ
```

cursor base64url 解码后对应 canonical JSON：

```text
{"expires_at":"2099-12-31T23:59:59.000Z","h":"abcdefghijklmnopqrstuv","issued_at":"2099-12-30T23:59:59.000Z","purpose":"stream","v":"1"}
```

期望客户端行为：

- 客户端 MUST 把 cursor 当作不透明字符串保存和回传。即使 cursor 的内部结构是 `encoding.md` §8.2 规定的合法 stateful handle 形态，客户端 SDK / 应用层 MUST NOT 解析它的内部字段来构造请求。
- 客户端 MUST NOT 依赖 base64url 解码后的 `h` handle、`expires_at` 或其它内部字段构造下一页请求；这些字段只属于 issuing service。
- 服务端 MAY 改变 cursor 内部编码或字段集合，只要同一 query/session 下 cursor 仍按 API contract 可用。
- 服务端 MUST 在收到该 cursor 时，按 [`encoding.md`](./encoding.md) §8.3 校验 `v ∈ supported_versions`、`purpose`、`issued_at` / `expires_at`、core schema 形态和 `h` handle binding；语法失败返回顶层 `param_invalid`（reason `invalid_cursor`），过期返回 `cursor_expired`，handle lookup / binding 失败返回 `cursor_integrity_invalid`（见 `error-code-registry.json`）。

失败条件：

- 客户端解析 `h` / `expires_at` 后自行构造下一页请求或修改 cursor 内容。
- 客户端在 cursor 解码失败时拒绝整个协议，而不是按 opaque token 处理。
- 服务端接受缺少 `h` 的 cursor body。

### 1.11.1 Vector: Service Protocol Version Bootstrap（normative）

`ak.vector.service.protocol_version_bootstrap.v1` 由
[`service-protocol-version-bootstrap-fixture.json`](../../artifacts/fixtures/service-protocol-version-bootstrap-fixture.json)
冻结通用 ServiceDescribe、Applet ping 与 identity 角色端点 ServiceDescribe 的两段式消费顺序。Runner MUST 先从 raw JSON 读取 `protocol_version`，不得先构造
v1 typed response 或读取任何 capability/routing 字段。精确值 `"1.0"` 才允许继续 schema 校验与 capability 交集；
形状合法的其它字符串返回 `unsupported_protocol_version`，且观测到的路由缓存写入与后续业务请求必须均为零；
缺失、非字符串或非 canonical `"1.0.0"` 返回 `schema_violation`。三个调用面必须执行同一分类，不得让 Applet
ping 或 identity 角色端点的 ServiceDescribe 退化为普通字符串健康检查。

### 1.12 Vector: Reconstructed Encrypted Envelope AAD

向量名称：

```text
ak.vector.encoding.encrypted_envelope_digest.v1
```

本向量在 `encoding-fixture.json` 固定最小 wire metadata `{version,content_type,encryption_context}` 与 ciphertext digest；
`ak.vector.history_key.sender_crypto.v1` / `arkret-private-kdf-fixture.json` 另给出 frozen outer signed Event fields、exact winning group state 与最小 wire `encryption_context`，由 runner 独立重构：

```text
pre_encryption_header = {
  purpose: "arkret_event_content",
  envelope_version: encrypted_envelope.version,
  content_type: encrypted_envelope.content_type,
  scheme: content_scheme(exact group_state_ref),
  effective_scope: effective_scope_from_outer_signed_event,
  event_kind: outer_signed_event.kind,
  mls_group_id: derive(effective_scope),
  epoch: encryption_context.epoch,
  group_state_ref: encryption_context.group_state_ref,
  sender_domain: derive_from_frozen_producer_verification_method_and_verified_leaf,
  counter: encryption_context.counter, // exporter only
  routing_context: derived_routing_context
}
content_aad = JCS(pre_encryption_header)
```

Standard MLS 使用该 AAD 作为 RFC 9420 authenticated_data 且 wire 无 counter；exporter 才使用 per-sender K_content 与
`I2OSP(counter,AEAD.Nn)`。向量必须覆盖修改 `version`/`content_type`、最终 producer verification method 与 seal 前冻结 method 不同、
station_admission proof 冒充 producer，以及 sender leaf 零/多匹配；全部在 decrypt/admission 前 fail closed。

机器向量同时覆盖 standard branch（counter absent）与 exporter branch（counter required），并对 outer scope/kind、derived
group id、group-state scheme、epoch、sender domain、counter 与 routing context 各做单字段 mutation。Wire envelope 若复制
purpose/scheme/scope/kind/group id、standard 携 counter、exporter 缺 counter 或 group-state scheme 与结构分支不一致，必须在 AEAD 前拒绝。

判定规则：

- digest 输入 MUST 为 `canonical_json(payload_metadata) || base64url_decode(ciphertext)`。
- 实现 MUST NOT hash 明文 payload。
- 实现 MUST NOT 省略路由和解密所需的 `payload_metadata` 字段，否则 Station sync surface 无法安全去重和审计密文 envelope。

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

| 向量 | Minimal Client | Full Client | E2EE Client | Events API | Station |
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

- `ak.vector.aead.full_width_counter_nonce.v1`
- `ak.vector.lattice.mv_register_join.v1`
- `ak.vector.lattice.counter_join.v1`
- `ak.vector.lattice.ordered_log_join.v1`
- `ak.vector.circle.directory_visibility_realm_members_indistinguishable.v1`
- `ak.vector.calendar.rsvp_occurrence_key.v1`

### 1.16 Vector: Cursor 拒绝负例

`vector_id`: `ak.vector.encoding.reject_invalid_cursor.core.v1`（来源：`cursor-negative-fixture.json`）

§1.11 固化 cursor 对客户端的不透明性；本向量固化签发服务侧的拒绝语义。fixture 的每个 case 是一条形似合法的 `ak:cursor:` token，conformant 签发服务在推进任何服务端状态之前 MUST 拒绝：超长 token、非法 base64url、畸形 JSON、重复键、非 NFC 字符串、内联 positions、未知字段、不支持的版本、过短 handle、非 canonical 时间戳、负 TTL、超 TTL 上限（stream / barrier 各一）、已过期。

Expected：前 13 类 `reason_code = invalid_cursor`（顶层错误码 `param_invalid`），过期 case `reason_code = cursor_expired`；客户端侧行为仍按 §1.11——decode 失败时按不透明字符串处理，MUST NOT 因此中断协议。

### 1.17 Vector: Multibase did:key 编码

`vector_id`: `ak.vector.encoding.multibase_did_key.core.v1`（来源：`encoding-fixture.json`）

固化 Ed25519 公钥的 base58btc multibase 编码（含 `0xed01` multicodec 前缀）与 `did:key` 标识符的金向量，为联邦验签与设备密钥目录的公共编码面提供跨实现锚点。cases 覆盖 all-0x2A、all-0x00 边界与固定顺序字节三组公钥。

Expected：`expected_multibase` / `expected_principal_id_key` MUST byte-for-byte 复现；decode MUST round-trip 回原始 32 字节公钥，前缀非 `0xed01` 或长度非 34 字节 MUST 拒绝。

### 1.12.2 Vector: Event 引用与 Circle 基数上限（normative）

`ak.vector.scalability.refs_limit.v1` MUST 由 runner 生成带 129 个互异 `refs[]` 条目的 Event，并在 reducer 之前断言 `schema_violation`、`reason_code=refs_too_large`；实现不得截断、去重后继续或只检查单一 role 的数量。

`ak.vector.scalability.circle_count_limit.v1` MUST 同时覆盖：（a）已有 1,000 个 active Circle 的 Realm 再提交 `ak.circle.create`；（b）已有 256 个 active MLS-backed Circle membership 的 actor 再加入一个 MLS-backed Circle。两者均 MUST 以 `failed_precondition`、`reason_code=circle_count_exceeded` 拒绝且不得改变状态。体量状态由 runner 按 [`scalability-limits-fixture.json`](../../artifacts/fixtures/scalability-limits-fixture.json) 的 generator 描述构造，不要求 fixture 字面展开全部对象。

`ak.vector.scalability.envelope_size_limit.v1` 只测完整 canonical accepted Event Envelope；v1 不定义 “Event/Operation envelope” 混合对象。Runner MUST 生成精确 1,048,576 bytes 的候选 accepted Event（包含全部 proof 与 reducer-stamped 字段、不含 read-view `unsigned`）作为接受边界，并生成 1,048,577 bytes 的超限输入；还必须覆盖 producer envelope 在 stamping 前未超限、加入 `effective_scope` / `actor_kind` 后变为 1,048,577 bytes 的用例。两个超限输入都 MUST 在 commit 前以 `payload_too_large` 拒绝；self/peer submit 携带 `unsigned` 必须在 reducer 前 `schema_violation`。同一 vector 还必须生成含 Add 的 Commit 所对应的 inline `ak.mls.welcome` 完整候选：恰好 1,048,576 bytes 可继续发送 Commit，1,048,577 bytes 必须在任何 Commit 网络写入和 post-Commit state 安装前终止该 generation。

`ak.vector.scalability.http_header_limits.v1` MUST 至少覆盖：128-char `Idempotency-Key` 接受、129-char 拒绝；非 ASCII / 非 canonical alphabet 拒绝；HTTP header aggregate 32 KiB 接受、32 KiB + 1 byte 拒绝；超限输入不得建立 replay-cache entry、不得构造无界签名 transcript。

### 1.12.3 Vector: JSON operation、HTTP pre-parse 与二维分页边界（normative）

下列 vector 均由 [`scalability-limits-fixture.json`](../../artifacts/fixtures/scalability-limits-fixture.json) 的生成式 case 承载：

- `ak.vector.scalability.operation_body_size_limit.v1` MUST 对 `body_class=non_streaming_json` 的完整 canonical request/response body 生成 8 MiB−1、8 MiB、8 MiB+1；前两者在其它约束合法时通过，8 MiB+1 固定为 `payload_too_large`。
- `ak.vector.scalability.http_body_preparse_limit.v1` MUST 对 `Content-Length`、HTTP/1.1 chunked、HTTP/2 DATA 与 HTTP/3 DATA 分别生成 16 MiB−1、16 MiB、16 MiB+1；超限必须在第 16 MiB+1 byte 终止，JSON parser、JCS 与 handler 都不得启动。另生成 wire 16 MiB+1、canonical 仅 `{}` 的 whitespace amplification，证明 canonical 较小不能绕过 wire 上限。
- `ak.vector.scalability.content_encoding_forbidden.v1` MUST 对 gzip、br、deflate 在读取或解压 body 前返回 HTTP 415 / `unsupported_content_encoding`。
- `ak.vector.scalability.batch_page_byte_count.v1` MUST 同时覆盖 request 的 count 与 canonical bytes 两维，以及 response page 因 bytes 先到而提前结束并返回 `has_more=true` 与 `next_cursor`；少于 count 上限不得被解释为终页。
- `ak.vector.scalability.read_unsigned_size_limit.v1` MUST 生成 service-added `unsigned` 的 16 KiB−1、16 KiB、16 KiB+1，验证超限值在 response commit 前被拒绝或省略，且任何 `unsigned` 都不改变 Event identity、授权或 reducer。

### 1.12.4 Vector: MLS Governance Proof exact response 与闭合证明（normative）

`ak.vector.scalability.mls_governance_proof_bounds.v1` 由 [`scalability-limits-fixture.json`](../../artifacts/fixtures/scalability-limits-fixture.json) 的生成式矩阵固化 [`scalability-constraints.md` §6](./scalability-constraints.md) 与 `mls-governance-proof-bundle.schema.json`。Runner MUST 对唯一近端 `group_security_frontier` outcome 的 1 MiB canonical exact-response 上限、closed Merkle path 64 siblings 与 registry 声明的 typed collection 上限生成 `limit-1 / limit / limit+1`。`limit+1` 必须在 materializer 或 verifier 对应边界 fail closed，且不得截断 witness、按声明 cardinality 预分配或把已接收前缀标为完整。

同一 vector 还 MUST 覆盖 stateless exact query：`profile=group_security_frontier`、scope/group、调用方本机已验证 current/pending group state 的 every-and-only、按 `leaf_index` 严格递增排列的 `local_mls_leaves[]`、完整 canonical `proof_base_basis`/`proof_target_basis` Seal 反链、`frontier_purpose` 及其 closed 字段和 `byte_limit` 全部进入 canonical query；空 leaves、重复 leaf index、重复 credential、伪造 principal 以及任何 result-set/cursor/continuation 或 epoch-range profile 字段都必须拒绝。pre-Genesis 0→0 必须携 `proposed_group_genesis_binding`，并分别覆盖 `mls_rfc9420`、exporter+none、exporter+organization recovery；不同 proposal 必须产生不同 query digest/cache entry 与 every-and-only cell set。缺 proposal 返回 `mls_genesis_binding_proposal_required`；proposal/真正 Genesis mismatch、并发 Genesis 输家、accepted 后仍携 proposal均返回 `mls_genesis_binding_proposal_mismatch` 且零写入；accepted 0→0 refresh 必须无 proposal并读取 immutable winner，伪造 `base_group_state_ref` 拒绝。`base == target` 零过渡与 base 为 target ancestor 都是正例；已证明并发/不可达必须返回 `mls_governance_anchor_unreachable`，必需 Seal/Event/witness 缺失导致无法判定时必须返回 `frontier_unavailable`，两者均不得等待、选 common descendant 或替换 basis。响应只携 exact `query_digest` 而不重复完整 leaves，且必须完整覆盖该 purpose 的 registered frontier projection；超界返回 `mls_governance_proof_bounds_exceeded`，不得截断或拆 cell。相同 query 与相同 accepted material 必须生成相同 canonical 响应和 `page_digest = SHA-256(UTF8("ak.mls-governance-proof-page-v1") || 0x00 || UTF8(query_digest) || 0x00 || JCS(page_body))`。Prefix witness 还必须覆盖空 prefix、左右 state edge、neighbor inclusion、缺 entry、错 leaf index 与多余 sibling。该近端响应不是 `ak:snapshot`，不含 Snapshot manifest/chunks 或 bootstrap authority；批量/旧历史只走 receipt-bound direct accepted-Seal traversal 与标准 Event/Seal/dependency resolve。

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
- `data_observed` 可用于可用性或轻客户端提示，但不是控制面 finality，也不证明历史无遗漏。

### 2.4 Vector: Control Move 必须有 Basis 且由 Seal 覆盖

向量名称：

```text
ak.vector.cba_lattice.control_move_requires_seal_basis_and_seal.v1
```

输入：

- Control Move 携带签名 `scope_ref`、`seal_basis` 与必要 `preconditions[]`；writes 由 reducer vector 重算。
- 同形 Control Move 的负向 case 缺少 `seal_basis`，或 `leaves[]` 未按 canonical unsigned bytes 排序、含重复项、引用未知/无效 Seal。

期望：

- 缺 `seal_basis` 或 leaves 无法验证 MUST `failed_precondition` / `rejected_seal`；producer 不携带可由 leaves 重算的 roots。
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
3. 其它 signature、proposal refs 和 `security_frontier_digest` 均有效。

Expected：

- Receiver / reducer MUST reject 该 commit，且不得推进 `mls_epoch_cell` 或 current winning MLS group-state projection。
- `governance_binding.previous_epoch` / `next_epoch` MUST 与 payload 顶层 epoch 字段一致；不得只相信其中一侧。

### 2.5.2 Vector: MLS Governance Frontier 双消费者闭环

`vector_id`: `ak.vector.mls.governance_proof.verifier.v1`

`vector_id`: `ak.vector.mls.governance_proof.materializer.v1`

两条 active vector 共用 [`mls-governance-proof-fixture.json`](../../artifacts/fixtures/mls-governance-proof-fixture.json) 的同一份 byte-level KAT。server-consumer runner MUST 从 fixture 的 accepted Seal DAG、完整 covered Event 集与 joined control state 重建一个有界 `group_security_frontier` exact outcome，逐字节复算 query、base/target `SealBasis`、Event/Seal descriptors、sparse witnesses、`page_digest` 与 `security_frontier_digest`，并与 fixture 的 exact expected outcome 比较；SDK-consumer runner MUST 以同一 outcome、Commit transcript binding 与本地完整 trusted basis 执行 [`encryption-and-audit.md` §2.5.1](../crypto-media/encryption-and-audit.md#251-security-binding-payload) 的固定验证顺序。近端 KAT 不生成 chunk、manifest 或 Bundle；批量/旧历史由独立 direct traversal KAT 从 receipt-bound target 反向发现完整 Seal cut、解析 Event/typed dependencies 并拓扑重放。具体执行入口以 fixture `runner` 元数据为准。只加载 fixture、只做 schema validation、只检查 `governance_binding.previous_epoch/next_epoch` 或只返回一个总 pass 均不构成通过。

Verifier mutation matrix MUST 在需要测试语义阶段时重算所有 transport commitments，覆盖：服务端自报但本地未信任的 base leaf、open-set basis 缺 leaf/多 leaf/乱序、`base == target` 正例、并发或不可达 target、断裂/分叉 Seal DAG、错误 notary authority；covered digest/state leaf/frontier Event 的缺失、多余、重复和乱序；frontier Event proof 与跨 Realm/scope；sparse path/boundary/nonmembership 的缺失或多余；Realm/group/epoch/profile/reducer binding，以及 `security_frontier_digest` 不匹配。任一 reject case 都不得持久化 verified outcome 或推进 MLS epoch。

Materializer matrix MUST 覆盖精确有效输出、`base == target` 与 ancestor→descendant 正例，以及并发/不可达 basis（`mls_governance_anchor_unreachable`）、必需 Seal/Event/witness 缺失（`frontier_unavailable`）、撤销后的 notary、control-cell Bottom、scope visibility denial 与 exact response 超界（`mls_governance_proof_bounds_exceeded`）；失败时 response count 必须为 0，不能输出 partial outcome 或替换 basis。两条 runner 在同一 profile certification job 中还 MUST 执行 companion `ak.vector.scalability.mls_governance_proof_bounds.v1` 的全部 `limit-1 / limit / limit+1` 与 exact-response cases，并记录每 case 的 stage、reason/error、response count、query/outcome digest、epoch transition 与 peak buffer bytes。

MLS group tracker 的 companion matrix MUST 另外对 `ak.peer.mls.read.group_state_material.v1` 执行：两组 ref/raw
bytes 完全匹配的 accepted genesis 正例；Event id、scope、group 或 epoch cross-binding；缺 ref、ref suite 不等于 Realm
`digest_algorithm`、payload 携带 sibling digest 镜像；
object missing；ref 内嵌 hash mismatch；raw-byte digest mismatch；GroupInfo 与 ratchet tree / GroupContext 不一致；
未 accepted 或 quarantine genesis；响应总界超限。所有失败必须 response count 0。正例必须从验证后的 RFC 9420
occupied tree leaves 得到 leaf index；runner 若从 KeyPackage 顺序、数据库 row 顺序或 governance-proof outcome 里伪造的 leaf DTO 得到 index，
即使数值碰巧相同也必须判 fail。governance-proof outcome 中出现 MLS leaves、MLS leaf_index、GroupInfo 或 ratchet-tree bytes
同样必须判 `schema_violation`。

### 2.5.3 Vector: MLS Welcome KeyPackage Hash Binding

`vector_id`: `ak.vector.mls.welcome_keypackage_hash.v1`

Steps：

1. KeyPackage claim response 返回 `keypackage_ref=K`、完整 `keypackage` bytes、`capabilities`、`requester_device_id=D`、`device_authorization_event_id=E` 与 `model_generation_ref=G`；receiver 从 bytes 重算 `H1`，从 capabilities 重算 `C`。`E` 必须是 PCR 中授权 `D` 且仍属于 active generation `G` 的当前有效设备授权 Event。
2. 攻击者提交 `ak.mls.welcome`，顶层 `keypackage_ref=K`，但 `payload.claim_ref.keypackage_digest=H2`（或 `payload.claim_ref.capabilities_digest` 不等于重算的 `C`）。
3. Welcome ciphertext、claim_id 和 signature envelope 其它字段均有效。

Expected：

- Receiver MUST 先验证 `D/E/G` 的当前 PCR accepted-device 投影，再从 claim record 的完整 bytes/capabilities 重算两个 digest；任一步不一致都必须在解密或接受 Welcome 前拒绝。
- `payload.claim_ref.keypackage_digest` MUST 等于 claim record bytes 的重算值和已发布 `ak.mls.keypackage.payload.keypackage_digest`；`payload.claim_ref.capabilities_digest` MUST 等于 claim record capabilities 的重算值。Welcome 顶层与 claim record 不得携带同源 digest 回声。

### 2.5.4 Vector: RFC 9420 MTI Ciphersuite Byte-Level KAT

`vector_id`: `ak.vector.mls.rfc9420_mti_kat.v1`

Arkret 不复制易漂移的外部密码学金值；本向量直接 pin MLS WG `mlswg/mls-implementations` 的 `test-vectors/` corpus commit `cfd450286d1bfd9cd2519b95c80f9771f94a5b1a`。声明 MLS 支持的实现 MUST 对 ciphersuite `0x0001` 运行 registry 列出的 `crypto-basics.json`、`key-schedule.json`、`messages.json`、`welcome.json` 与 `treekem.json` 全部适用 case，并逐字节匹配编码、KEM/HPKE 输出、joiner / epoch secret、Welcome 与 TreeKEM 派生值。只通过 Arkret 结构绑定 fixture、不运行该字节级 corpus，不足以声明 `ak.vector.mls.rfc9420_mti_kat.v1` 通过。更换 upstream commit 必须作为 registry review 变更并重新跑全套 KAT。

### 2.5.5 Vector: MLS Security Frontier 精确且不吸收普通 Seal

`vector_id`: `ak.vector.mls.security_frontier_key_access_only.v1`

本 vector 固定 [`encryption-and-audit.md` §2.5.2](../crypto-media/encryption-and-audit.md#252-send-gate-与-self-heal) 的两条结构性规则：security frontier 只吸收改变密钥访问资格的 closed cell set，普通 DataEvent 的 `seal_ref` 与 MLS frontier 正交。

Steps：

1. 从 accepted state 重算 digest `F`，提交 `ak.mls.commit C` 绑定 `F` 并推进 epoch。
2. 接受只改变 display metadata、普通 capability、moderation 或 routing 的 Control Move，再提交 E2EE application DataEvent；其 `seal_ref=S` 指向最新 accepted Seal。
3. 接受一次实际撤销当前 MLS leaf 的 device/Agent runtime key revoke，令重算 digest 变为 `F2`，但尚未接受绑定 `F2` 的新 Commit。

Expected：

- 第 1 步 Commit MUST accepted，并把 current winning group-state projection 绑定到 `F`。
- 第 2 步 DataEvent MUST accepted；把普通 `S` 或无关 cell 机械加入 frontier 并返回 `mls_governance_binding_stale` 即为不通过。
- 第 3 步之后新的 application DataEvent MUST 暂停并返回 `mls_governance_binding_stale`，直到 active member 发起且 receiver 接受绑定 `F2` 的 self-heal Commit。
- Fixture MUST 同时证明 contact/consent-only suspension 禁止发送但不改变 digest；若该动作伴随实际 member/leaf remove，则由 remove 改变 digest。

### 2.5.6 Vector: SDK Event 两条正交强类型轴

`vector_id`: `ak.vector.sdk.event_type_axes.v1`

官方 SDK 的 compile-fail/type-error runner MUST 执行
[`sdk-event-type-axes-fixture.json`](../../artifacts/fixtures/sdk-event-type-axes-fixture.json)。它至少证明：

- `ControlMove` 缺 `seal_basis`、`DataEvent` 缺 `seal_ref/auth_context` 无法产生可提交值；
- 普通 raw Event batch 不能因 CBA 条件字段缺失而被推断为 `AnchorUnit`；
- `MlsCommitPayload` 缺完整 Commit bytes、epoch 或 `security_frontier_digest` 无法构造；
- plain application payload 不能误走 MLS Commit validator，`MlsEncryptedPayload<T>` 不能序列化为 plain payload；
- SDK 生成的 immutable verified submission bytes 逐字通过服务端同一 Event schema、canonicalization 与 proof transcript 验证。

只做运行时 JSON 校验、不提供 compile-fail 或公开 API inventory，不能声明本向量通过。公开 submit API
若接受 raw map、可变 verified envelope 或未转换的 wire Event，亦为不通过。

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
- 接收方 verifier 在 reject 时 MUST 返回 `digest_mismatch`（case 2/3/4）、`signature_invalid`（case 3 的签名路径）或 `schema_violation`（case 5/6），不得回退到"prose 形态化"判断。

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

#### 2.10.2 Vector: redactable 内容槽的 unset 禁令与合法清除路径

向量名称：

```text
ak.vector.patch.redactable_content_slot_unset_ban.v1
```

runner MUST 从
[`redactable-field-registry.json`](../../artifacts/registry/redactable-field-registry.json) 的
`redactable_fields[]` 枚举 path，并按 `state-reducer-hardening-fixture.json` 的对应 case 验证：

- 对**每一条**已登记 `(object_kind, path)` 注入 `{"$op":"unset"}`，MUST 得到 `schema_violation`、
  `reason_code=patch_unset_redactable_field`，且目标对象零变更。明文 path 与其 `paired_path`
  的判定 MUST 完全一致——Description 的 `content` / `encrypted_content` 对与 Synthesis 的
  `tracks.synthesis.content` / `tracks.synthesis.encrypted_content` 对都必须各自保持明密文对称，
  否则同一份正文的可移除性会取决于 Realm 是否 E2EE。
- 对同一条 path 注入 `{"$op":"set","value":{"kind":"ak.content.text","body":""}}`，MUST 被接受：
  §4.2.4 是槽存在性约束，不是内容改写约束，空正文改写是普通编辑。
- 对 `metadata.summary`、`metadata.title` 与 `metadata.fields.<key>` 注入 `{"$op":"unset"}`，
  MUST 被接受：它们不是内容槽，`unset` 是其唯一的非终态清除路径。把它们当作 redactable
  会让 optional 字段变成 write-once。

失败条件：实现把禁令推广到 `metadata.*`（造成无法清除的字段），或只对明文/密文其中一种形态生效，
或把 redactable path 上的 `set` 也拒绝（造成正文不可编辑）。

### 2.11 Vector: `fsm` 家族 join 幂等与并发冲突

向量名称：

```text
ak.vector.lattice.fsm_join.v1
```

本向量固化 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §9.3.1 `fsm` lattice 的 join 规则：“同一 CBA basis 内相同 `(from,to)` 的重复 transition 是幂等的；同一 `from` 指向不同 `to` 的 sibling transition 返回 ⊥。跨 basis 顺序仅由 causal refs 与 Seal DAG 决定；同一 basis 内不得用 HLC、接收顺序或 actor id 选择状态机 winner。”

输入（cell schema：`fsm`，`bottom=reject`，`parameters.initial_state="invited"`，`allowed_transitions` 含 `(invited,join)`、`(invited,decline)`）：

- **Case A — 幂等收敛**：同一 CBA basis 内两条并发 Event 各自对同一 fsm cell 提交 transition `(from="invited", to="join")`（相同 `(from,to)`，不同 actor / event id / HLC）。
- **Case B — 并发冲突 ⊥**：同一 CBA basis 内两条并发 Event 分别提交 `(from="invited", to="join")` 与 `(from="invited", to="decline")`（同 `from` 不同 `to`）。
- **Case C — 重入不是重放**：可逆 family（`allowed_transitions` 含 `(active,archived)` 与 `(archived,active)`）上依次提交 `active→archived`、`archived→active`、`active→archived` 三条**因果有序**的 transition。
- **Case D — 已登记 self-loop 不吃掉后继**：`allowed_transitions` 含 `(active,active)` 的 family 上依次提交 `active→active` 与 `active→tombstoned`。

期望：

- **Case A**：join 收敛到 `state == "join"`，MUST NOT 返回 ⊥；两个 conformant reducer 以不同输入顺序重放 MUST 得到同一结果。
- **Case B**：join MUST 返回 ⊥；`query(cell)` 返回 structured `Bottom{kind="conflict"}` 诊断。该 cell 配置 `bottom=reject`，后续依赖该 cell 的 Event MUST `failed_bottom`，直到 §8 conflict-recovery 路径修复。
- **Case C**：读 `archived`。**幂等判据 MUST NOT 只看 `(from,to)` 对**：cell 合法回到 `active` 后就重新站在该状态的出边起点上，此时同一 `(active,archived)` 是一次**新的**转移而不是第一条的重放。只按 `(from,to)` 去重的实现会把第三条折掉并读出 `active`——这与 §9.3.1.4 为 `cas_register` 删除值接边 join 时点名的 `A→B→A` / `A→B→A→B` 是同一个失效，在每个可逆 `object_lifecycle` family 与 membership 上都可达。
- **Case D**：读 `tombstoned`。已登记的 self-loop 是合法的重复声明，MUST NOT 被记成「该状态唯一的出边」，否则随后一条 registry 明确允许的转移会被误判成 `same_from_different_to` 冲突。
- 四个 case 中实现均 MUST NOT 用 HLC、actor id、event id 或本地接收顺序选择状态机 winner。

失败条件：

- Case A 把幂等重复 transition 错判为冲突返回 ⊥。
- Case B 选出任一 `to` 作为 winner 继续推进，或冲突诊断在两个 reducer 间不一致。
- Case C 读出 `active`（把重入当成重放）。
- Case D 返回 ⊥（把 self-loop 当成该状态已用掉的出边）。
- transition `(from,to)` 不在 `allowed_transitions` 表内却未返回 ⊥ / 未被 validate_op 拒绝。

**「不同到达顺序得到同一结果」由 §2.11.2 承载**：它需要一个 `cas_register` 早已拥有、
而 `fsm` 直到 §9.3.1.5–§9.3.1.8 才获得的对应物——按写入身份而非按输入序列定义的状态。
本节固定转移表准入与同 basis 冲突判定；顺序无关性、ABA、迟到分支与并发 recovery 在 §2.11.2。

#### 2.11.1 Vector: same-Seal `bottom=reject` 排重

向量名称 `ak.vector.seal.same_batch_bottom_reject_serialization.v1`。构造两条基于同一 frozen predecessor、命中同一 `cas_register` 或 `fsm` `bottom=reject` cell 且 projected writes 互斥的 Control Move。Case A 的 notary 只 include 一条并对另一条 signed-reject `cas_conflict`（或 defer）；Seal MUST accept。Case B 的同一 Seal `delta[]` include 两条；`apply_seal` MUST 拒绝整个 Seal 为 `rejected_seal`，不得物化 `failed_bottom`。Case C 把两条 Move 放在不可达的并发 Seal leaf；joined view 仍 MUST 按 lattice 返回 `Bottom{kind="conflict"}`，证明排重义务不改变真正跨 leaf 并发语义。

#### 2.11.2 Vector: `fsm` 因果 heads（顺序无关性与迟到分支）

向量名称：

```text
ak.vector.lattice.fsm_causal_heads.v1
```

本向量固化 [`event-auth-state-resolution.md` §9.3.1.5–§9.3.1.8](../authz/event-auth-state-resolution.md)：
`fsm` 与 `cas_register` 是同一套因果状态，每个活跃 head 携带该写入的 `to`；`from`、`states` 与
`allowed_transitions` 是写入对**自身签名 basis** 的准入断言，不是 join 时的接边依据。上一节
§2.11 固定的是转移表准入与同 basis 的冲突判定，本节固定的是**状态代数**——它才是「不同到达顺序
得到同一结果」的来源。机器 fixture 是
[`cba-lattice-fixture.json`](../../artifacts/fixtures/cba-lattice-fixture.json) 的
`ak.vector.lattice.fsm_causal_heads.v1` 块。

输入：每个 case 给出一组写入 `{id, from, to, supersedes[]}`，其中 `supersedes` 是该写入自身已验证
basis 观察到的完整 head 身份集合（reducer 派生，不上 wire）；`registered` 给出该 family 的
`initial_state` / `states` / `allowed_transitions` / `terminal_states`。

期望：

- **未写入**读登记的 `initial_state`，且不占 `state_root` leaf。这是 `fsm` 与 `cas_register`
  唯一的状态差别。
- **顺序置换与分批合并**：`linear_chain_leaves_only_its_terminal_write`、
  `input_order_permutation_is_one_result`、`batch_split_is_one_result` 三个 case MUST 得到同一
  heads 与同一 settled 值。按输入顺序折叠的实现在第二个 case 上就会分叉。
- **ABA**：`aba_is_distinguished_from_abab` 读 `active`，`abab_reads_archived` 读 `archived`。
  按 `(from,to)` 去重的实现两个都读 `active`。
- **已登记 self-loop**：`a_registered_self_loop_leaves_later_transitions_legal` 读 `tombstoned`。
  把 self-loop 记成「该状态唯一出边」的实现会把后继判成冲突。
- **同值并发与重放**：`concurrent_same_to_keeps_every_identity` 保留**两个** head 并读同值；
  `exact_replay_dedupes_by_identity` 只保留**一个**。两者 MUST NOT 被合并成同一条判据——
  前者是两个真实并发写入，后者是同一个写入到达两次。
- **异值并发**：`concurrent_different_to_reads_failed_bottom` 读 `failed_bottom`，Bottom 诊断
  reason 为 `same_from_different_to`，且该 cell **仍占 `state_root` leaf**（§6.2.1）。
- **迟到分支**：`late_branch_merges_by_the_formula` MUST 按 §9.3.1.8 的合并式求值——
  取 heads 的并集会把已被取代的 `g1` 复活，取交集会丢掉对方从没见过的 `g3`；两者都错。
- **缺依赖**：`missing_dependency_holds` MUST hold 或 fail closed，MUST NOT 因为写入自称
  `from=archived` 就采信它的 `to`。
- **并发 recovery**：`concurrent_different_to_recovery_still_conflicts` 仍读 `failed_bottom`。
  recovery 是一次有权的新身份写入，不因「它是 recovery」而免于冲突，更不由到达顺序裁定。

失败条件：

- 任意两个只在输入顺序或分批方式上不同的 case 得到不同结果。
- `aba_is_distinguished_from_abab` 与 `abab_reads_archived` 读出相同 settled 值。
- `concurrent_same_to_keeps_every_identity` 只保留一个 head，或
  `exact_replay_dedupes_by_identity` 保留两个。
- `⊥` 的 `fsm` cell 未进入 `state_root`。
- 迟到分支合并用了并集或交集。
- `missing_dependency_holds` 物化出 `tombstoned`。

**消费面一并覆盖（normative）**：MLS membership、governance proof 与 Station notary 各自持有的
membership transition 折叠是本 lattice 的消费者。runner MUST 对这些消费面执行同一组 case——
保留一份按 `(from,to)` 去重或按 `recovery_reset` 切片的并行实现，等于让同一个 cell 在两个消费面上
读出不同状态（§9.3.1.8）。

### 2.12 Vector: `cas_register` 因果身份守卫（stale basis 与 ABA 拒绝）

向量名称：

```text
ak.vector.cba_lattice.cas_mixed_basis.v1
```

本向量固化 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §9.3.1.3 的写入准入：每个 `cas_register` 写入的基线是它**自身签名的 `seal_basis`**，Seal 准入按 §6.3 step 8b 比较该 cell 的**完整活跃 head 身份集合** `H_c(B) = H_c(P)`。该守卫对每个注册目标自动派生，不要求 wire 重复携带 `head_eq`；业务另行登记的 `head_eq` 继续签名并执行。

输入（`cas_register` cell，未写入初始态为 `null`；前置 Seal 已由 Event `E1` 写入 `value_1`，因此 `H = {E1: "value_1"}`）：

- **Case A — 无 basis 的盲写**：一条声明使用 CAS 语义的 DataEvent 写入 `value_2`，没有可重建的签名 basis。
- **Case B — 基线正确的写入**：一条 Control Move 写入 `value_2`，其签名 `seal_basis` 重建出的 `H_c(B) = {E1}`，与冻结 predecessor 基线一致。
- **Case C — stale ABA**：`E1` 之后由 `E2` 释放（`set null`，`H = {E2: null}`），再由 `E3` 占用（`H = {E3: ...}`），最后由 `E4` 再次释放（`H = {E4: null}`）。此时提交一条**基线停留在 `H = {E2}`** 的写入：它的业务 settled value（`null`）与冻结基线的业务 settled value（同为 `null`）**逐字节相同**。
- **Case D — 自派生目标**：`ak.call.create` 写入其 focus cell，该 cell 的 subject 派生自本 Event 自己的 `event_id`，因此 `preconditions[]` 内**没有**该 cell 的 `head_eq` 条目。

期望：

- **Case A**：receiver MUST 以 `failed_precondition` 拒绝整个 Event（多 cell 原子性，不得部分应用其余 projected writes）；cell 保持 `value_1`。缺 basis 就无法派生 `H_c(B)`，MUST NOT 退化成无条件覆盖。
- **Case B**：Control Move 接受并在被 accepted Seal 覆盖后使 cell 收敛到 `value_2`，`H = {E_B: "value_2"}`；两个 conformant reducer 以不同输入顺序重放 MUST 得到同一结果。
- **Case C**：MUST 以 `failed_precondition` 拒绝——`H_c(B) = {E2} ≠ {E4} = H_c(P)`。**业务值相等不足以通过**：这是身份守卫封闭的 stale ABA，whole-value 比较无法表达它。
- **Case D**：MUST 接受。守卫由 reducer 在 EventId 算出后自动派生并执行，实现 MUST NOT 因为 `preconditions[]` 里缺该 cell 的 `head_eq` 而拒绝它，也 MUST NOT 要求 producer 把自身 `event_id` 派生的 `cell_id` 写进被 digest 覆盖的签名前像（哈希自引用，§9.3.1.3）。

失败条件：

- Case A 被当作 first set 放行。
- Case C 因两边业务 settled value 都是 `null` 而被放行（**本向量的核心负例**）。
- Case D 因「每个目标 cell 都必须有 wire `head_eq`」的旧读法被拒。
- 任何实现保留按 `(value, from)` 接边、pair 去重或极大链枚举的 CAS join（§9.3.1.4 已整体删除该定义）。

### 2.13 Vector: `ordered_log` sparse actor sequence

向量名称：

```text
ak.vector.lattice.ordered_log_gap.v1
```

本向量固化 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §9.3.1：`issuer_seq` 必须等于 envelope `actor_seq`，在单个 cell 内是稀疏坐标而非独立连续计数器。

输入（ordered_log cell，`bottom=inert`）：

- **Case A — 正常稀疏序列**：issuer I 的 append entries 以 `issuer_seq ∈ {0, 1, 3}` 到达；actor_seq 2 是写往其它 cell 的合法 Event。
- **Case B — 新 entry 后到**：在 Case A 状态上，同 cell 的 actor_seq 2 entry 通过 backfill 到达，reducer 重算。

期望：

- **Case A**：seq 0、1、3 全部进入 cell value；没有 `pending_gap`，也不要求证明 seq 2 写过本 cell。canonical 顺序为 issuer、actor_seq、decoded event digest。
- **Case B**：新 entry 加入后，两个 conformant reducer 以不同到达顺序重放 MUST 得到 bit-exact 相同的完整四-entry cell value 与 root leaf。
- exact Event replay 幂等；相同 `(issuer, seq)` 的不同合法 sibling 全部保留，见 §2.21。

失败条件：

- Case A 因 per-cell seq 缺口产生 pending、返回 ⊥、截断 prefix 或排除 seq 3。
- Case B 重算结果依赖本地接收顺序。

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

- Case A：receiver MUST 拒绝或隐藏（`seal_ref_stale` / `failed_precondition`）。
- Case B：receiver MUST 接受并把 Event 保留在 data-cell join 输入；选择拒绝或从 reducer 输入排除该
  窗口内 Event 的实现不符合本向量。
- Case C：receiver MUST `failed_precondition`，不得回退到"当前 DID 文档"判定。

失败条件：用当前 DID 文档替代 `seal_ref` 时点判定；Case A 被静默接受；Case B 被拒绝或未进入
data-cell join 输入。Case A 的 reject 与 hide 只允许改变本地保留/诊断可见性，对 data-cell join 输入
必须同为排除。Runner 不得要求未登记的 `query_grade` 响应字段。

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
- `single_signer` profile 下该机制不可用，实现 MUST NOT 伪造 inclusion list 语义。

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
- fault 记录生效后：N 的后续 Seal MUST 被拒绝；`S_a`、`S_b` 及其后继进入 `fork_quarantine`，普通 joined governance view MUST NOT 纳入；依赖该分支且无法从非隔离分支求值的查询 MUST fail closed，不得以未登记的 `grade=forked` 字段替代隔离。
- 仍有其余合法 signer 时 Realm MUST NOT 整体 pause；无剩余合法 signer 时进入 `notary_paused`，仅 recovery 路径可恢复。
- 两个 Seal 不满足 slot 规则（不同 signer 或不同 seq）时，该 Move MUST `failed_precondition`——合法并发 leaf 不构成 fault。

失败条件：要求提交者持有 capability；fault 后整 Realm 无差别 pause；合法并发 leaf 被误判为 fault。

### 2.17.1 Vector: 已 Seal Control Move 的完整 digest collision

向量名称：

```text
ak.vector.cba_lattice.sealed_control_move_full_digest_collision.v1
```

本向量固化 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §6.3.3 与
[`operations-sync.md`](../sync/operations-sync.md) §12 在**同一 suite 下两个不同 canonical preimage
重算出同一 `event_id`** 时的处置。它与 §2.17 的分叉不同：那里各 sibling 的 `event_digest` 不同，这里逐字节相同。

输入：

- accepted Seal `S` 的 `covered_set` 覆盖 Control Move `M`，receiver 已按 `M` 的 canonical bytes `B_a` 物化 reducer 输出。
- 随后经 submit / probe / backfill 任一路径出现 `B_b`：`B_b != B_a`，但同 suite 下 `event_digest(B_b) == event_digest(B_a)`，因此 `event_id` 相同。
- 归一裁决候选两份：`R_digest` 只以 `event_id` / `event_digest` 指认胜出变体；`R_bytes` 承载被选中变体的完整 canonical bytes。

期望：

- `B_a`、`B_b` 与由任一变体创建的 Event-derived object、未 final writes 及引用该 ID 的后继一起整组 quarantine；受影响 `(actor_id, actor_seq)` 之后的 Control Move fail closed。
- `S` 的 `covered_set` / `control_event_set_root` / `state_root` 保持原承诺，不被追溯删除；receiver 保留它当初按 `B_a` 物化的 reducer 输出，MUST NOT 用 `B_a` 或 `B_b` 重新推导它。
- 未保留 `B_a` 的 receiver 把 `S` 覆盖区间标为不可验证并 fail closed，而不是用任取一变体重算的 `state_root` 冒充原承诺。
- `R_digest` MUST 被拒绝，reason code `witness_disagreement`；`R_bytes` 才能归一。
- 该区间未归一时，notary MUST NOT 签发跨越它的 compaction Seal。
- 跨 suite discriminator（同一 preimage 的 `blake3` digest）MAY 作为诊断出现，但对端验证 `R_bytes` MUST NOT 以它为前提。

失败条件：first-row-wins 或较早 accepted 者胜出；接受只按 digest 指认的归一裁决；碰撞区间被 compaction 跨越；把重算的 `state_root` 当作原 Seal 承诺。

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

- Case A：receiver MUST 按 joined control view 判定该 capability 已撤销，DataEvent MUST fail closed（`seal_ref_stale`）；并发分支不计算 `distance`，不享受新鲜度窗口。
- Case B：依赖该 cell 的 DataEvent 与 Control Move MUST fail closed（`cell_in_bottom_state` / `failed_bottom`）。
- Case C：轻客户端 MUST hold pending 或 fail closed，MUST NOT 用单 leaf 授权结论接受该 DataEvent。
- Case D：join `R` 后 `E` MUST `seal_ref_stale`，其 cell X write MUST 被追溯移除；`D` 与所有直接 / 间接依赖 `E` 的 accepted 后继 MUST 转为 `result=pending, reason=dependency_missing`，其 projected writes（含 cell Y）同步移除。最终 accepted set 与 projection MUST 等于从一开始就持有 `{S0,R}` 的 receiver，且与到达顺序无关。

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
- Case B：窗口内 MUST 接受并进入 data-cell join 输入；超窗 MUST 拒绝或隐藏，code=`seal_ref_stale`。后继 archive 不得被误报为基线内 `circle_not_active`。
- Case C / D：MUST 立即拒绝或隐藏，code=`seal_ref_stale`，`freshness_window_applies=false`；轻客户端无法验证 joined view 时只能 pending 或 fail closed。
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
- **Case F — MLS 普通 Commit 绕过**：`ak.component.mls.epoch.v1` 已因并发 Commit 进入 `⊥`，producer 再提交普通 `ak.mls.commit` 试图直接推进 epoch。

期望：

- Case A：reducer MAY 把该 `bottom=reject` cell 从 `⊥` 解析为 recovery Move 声明的单一合法值；后续依赖该 cell 的判定按恢复后的 sealed state 执行。
- Case B：MUST 拒绝（`recovery_witness_missing` / `recovery_witness_invalid`）。
- Case C：MUST 拒绝（`recovery_witness_post_conflict`）。
- Case D：MUST 拒绝（`recovery_capability_not_sealed` / `recovery_witness_revoke_lagging`）。
- Case E：MUST 拒绝；unsealed recovery Move 不得改变 `⊥` cell。
- Case F：MUST `failed_bottom`，epoch cell 保持 `⊥`，application send gate 保持关闭；MLS 不得另设恢复入口。

失败条件：普通 Control Move（包括 `ak.mls.commit`）在 `⊥` 下绕过 recovery 例外；post-conflict witness 被接受；recovery capability 未 sealed 或已撤销仍生效；未 sealed 的 recovery Move 改变 canonical state；同一 fixture 用重复 `vector_id` 另行表达 MLS 特例。

### 2.21 Vector: `ordered_log` sibling-set join

向量名称：

```text
ak.vector.lattice.ordered_log_join.v1
```

本向量固化 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §9.3.1 的 grow-only Event-set join；[`encoding.md` §4.2](./encoding.md) 只稳定序列化顺序，不产生 winner。

输入（ordered_log cell，`bottom=inert`；fixture：[`cba-lattice-fixture.json`](../../artifacts/fixtures/cba-lattice-fixture.json) `ak.vector.lattice.ordered_log_join.v1`）：

- **Case A — sparse per-issuer 顺序**：两个 issuer 各自提交任意递增 `actor_seq`，到达顺序交错且允许 per-cell 间隔。
- **Case B — exact replay**：同一 Event identity 与完整 canonical `write.op` 重复到达。
- **Case C — sibling set**：同一 `(cell, actor_id, issuer_seq)` 的两个不同合法 Event，完整 canonical `write.op` bytes 可同可不同，canonical `event_digest` 不同。
- **Case D — 因果资料不选边**：与 Case C 相同的集合，但其中一条携带不同 causal refs；若 actor-chain 验证均接受，二者仍全部进入日志。
- **Case E — digest collision**：两个候选的 canonical `envelope_without_proofs_unsigned_actor_kind_event_id` bytes 不同，却得到完全相同的 typed `event_digest`（同 suite、同 octets）。
- **Case F — 仅 proofs / reducer stamp 不同**：两个候选的 canonical digest preimage bytes 逐字相同，只有 `proofs` 集或 reducer-stamped `actor_kind` 不同。`scope_ref` 不同必然改变 digest，不属于本例。
- **Case G — 跨 suite 比较**：两个候选使用不同 digest suite，且 typed wire string 的 UTF-8 顺序与 decoded digest octets 顺序**相反**。

期望：

- **Case A**：输入顺序任意排列都产出相同完整 Event set 与 root leaf；只到达 seq 3 时也立即物化。
- **Case B**：幂等去重，只产生一条 entry。
- **Case C**：两条 sibling 都进入 joined value；diagnostic 若出现，必须列出完整 sibling set，不得出现 winner/loser 字段。
- **Case D**：结果与 Case C 相同；因果资料、HLC 与到达顺序不得删除任一已接受 sibling。
- **Case E**：MUST fail closed（digest collision），MUST NOT 回退到 `event_id`、`op.value` 内任一字段、到达顺序或实现私有 ID。
- **Case F**：视为同一 producer-signed Event 内容，MUST NOT 报 collision；`proofs` 按 proof profile 合并，reducer stamps 按其各自验证规则处理。
- **Case G**：joined value 包含两条；它们的 canonical serialization order 由 decoded digest octets 决定，不由 `<suite>:` 前缀字符串决定。

失败条件：

- 用 digest、`event_id`、created_at、HLC、到达顺序或领域字段选 winner。
- 排除任一合法 sibling，或把后续 actor entry 因同高 sibling 截断。
- 直接比较 typed digest wire string，使 suite 名先于内容决定 winner。
- 只比较 `op.value` 而非完整 `write.op`，把 `op` 其它字段不同的候选误判为 duplicate。
- 要求 per-cell prefix 从 0 连续，或产生 pending gap。
- sibling diagnostic 未列完整 set，或仍暴露 winner/loser。
- Case F 被误报为 digest collision。

## 3. Redaction 与 Snapshot Vectors

### 3.1 目标

本节定义 redaction 的执行顺序、保留字段与可见性收敛规则，并涵盖与之相邻的 snapshot pruning / inclusion-challenge 向量（§3.5–§3.6，`domain=snapshot`）。
所有实现必须将 redaction 视为“可验证的内容裁剪”，而非删除事件。

向量命名：

```text
ak.vector.redaction.<scenario>.v1
ak.vector.realm_state_snapshot.<scenario>.v1
```

### 3.2 Vector: 字段保留规则

向量名称：

```text
ak.vector.redaction.preserve_fields.v1
```

输入的目标事件（`ak.message.create`）：

```json
{
  "event_id": "ak:event:ASwq0QFg8faJScGgZD2ETHGz8WhBMT09jmLQI16Q3Z-U",
  "kind": "ak.message.create",
  "realm_id": "ak:realm:AVSHhSS_nHM-k8vB4erfnnvnUFbfkHBYoo9gahFWqZQE",
  "actor_id": "ak:did_core:webvh:z6mkfixtureAlice",
  "created_at": "2026-04-26T00:00:00Z",
  "hlc": "01970e589d24-0001-aaaaaaaa",
  "prev_refs": [],
  "refs": [],
  "payload": {
    "strand_id": "ak:strand:Abk9ggNjpAEpSsrb-40s9VzVw635-qwEqGjQBvMdr5Wx",
    "content": {
      "kind": "ak.content.text",
      "body": "private notes"
    },
    "metadata": {
      "fields": {
        "rank": 10
      }
    }
  }
}
```

输入的 redaction event payload（Message 目标，必须通过 `ak.message.redact` 注册的 `event-payload.schema.json#/$defs/message_redact_payload`）：

```json schema=schemas/event-payload.schema.json#/$defs/message_redact_payload
{
  "message_id": "ak:message:ASwq0QFg8faJScGgZD2ETHGz8WhBMT09jmLQI16Q3Z-U",
  "reason": "moderation_recall"
}
```

该 redaction event 的 envelope 取值：`event_id="ak:event:AVRqeKaVZkAqsTdzlqHhkhlOpz6hhmxOkZizc06Spg6N"`、
`kind="ak.message.redact"`、`actor_id="ak:did_core:webvh:z6mkfixtureAlice"`、
`created_at="2026-04-26T00:00:02Z"`。目标只由 `payload.message_id` 承载：Event Envelope 没有第二条目标通道，
`ak:message:<T>` 与目标 create Event 的 `ak:event:<T>` 共享同一 33-octet token（[`../models/common-fields.md` §6.0](../models/common-fields.md)）。

期望结果：

```json
{
  "message_id": "ak:message:ASwq0QFg8faJScGgZD2ETHGz8WhBMT09jmLQI16Q3Z-U",
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
    "proofs"
  ],
  "removed_payload_fields": [
    "content",
    "metadata"
  ],
  "redaction_cell": {
    "cell_family": "ak.component.object.redaction.v1",
    "cell_subject": "ak:message:ASwq0QFg8faJScGgZD2ETHGz8WhBMT09jmLQI16Q3Z-U",
    "or_set_members": [
      {
        "actor_id": "ak:did_core:webvh:z6mkfixtureAlice",
        "reason": "moderation_recall"
      }
    ]
  }
}
```

判定要求：

- `payload.message_id` 指向的 Message 必须在 reducer 可见集合中存在；不存在时按
  [`../models/common-fields.md` §5.1](../models/common-fields.md) 的「未知对象 pending / replay」保留待重放，
  不得当作成功 no-op。
- 重放前后目标事件的 `event_id` 与 canonical digest 必须保持可验证：redaction 只清空内容槽，不改写 envelope。
- 目标 Message 的 `content` / `encrypted_content` 在 `state="redacted"` 后 MUST 同时缺席（判据见 §3.2.3）。
- **attribution 不是目标事件上的新字段**：redaction 的执行者与理由只经
  `ak.component.object.redaction.v1` cell 的 canonical projection 暴露——OR-Set 成员即 redaction Event 的
  `payload`，归属主体是该 Event 的 `envelope.actor_id`。Event Envelope 是
  [`event-envelope.schema.json`](../../artifacts/schemas/event-envelope.schema.json) 的 closed 对象，
  实现 MUST NOT 在目标事件上新增 `redacted_by` / `redaction_reason_code` / `hashes` 一类的 tombstone 字段。

失败判定：

- 把事件当作 tombstone 并抹去事件本体。
- 保留 `content` 等已被 redaction 清除的内容槽。
- 修改 `event_id` 或 `hlc`。
- 在目标事件 envelope 上物化 attribution 字段，或用 Envelope 而非 `payload.message_id` 承载 redaction 目标。


### 3.2.1 Vector: Space target redaction payload schema

向量名称：

```text
ak.vector.redaction.space_target_ref_schema.v1
```

输入（payload 片段，必须通过 `ak.redaction` 注册的 `event-payload.schema.json#/$defs/cross_object_redaction_payload`）：

```json schema=schemas/event-payload.schema.json#/$defs/cross_object_redaction_payload
{
  "target_ref": "ak:space:AdkL35R2W53p6Pt8Wi0dJHZhmP2mvu01sM1lM1wB1lb-",
  "reason": "privacy_cleanup"
}
```

期望结果：

- Payload schema MUST 接受 `ak:space:*` 作为 `ak.redaction` 的 `target_ref`。
- Reducer 语义仍按 Space 生命周期规则执行：Space 没有独立 `redacted` state，内容清理合并到 Space metadata cleanup / terminal transition；不得因 schema 漏洞把 Space cleanup 路径降级为实现私有扩展。

### 3.2.2 Vector: Message 只能由专属 `ak.message.redact` 进入 `redacted`

向量名称：

```text
ak.vector.redaction.message_target_exclusive_kind.v1
```

[`common-fields.md` §5.1](../models/common-fields.md) 的 Message 豁免要求：注册了对象专属 `ak.<kind>.redact` 的对象
MUST 只走该专属 kind，cross-object `ak.redaction` MUST NOT 指向它。v1 唯一这样的对象是 Message。
本向量把该裁决固化为 schema 级判据，使实现无需维护按字符串前缀判断的私有 allow/deny 表。

负例 1（cross-object `ak.redaction` 用 `target_ref` 指向 Message）：

```json schema=schemas/event-payload.schema.json#/$defs/cross_object_redaction_payload expect=invalid first_error="contains:'ak:message:AVEbR6LJe9T0RIh43YEQxR-vov-d4AbPcHIDId501TNw' does not match"
{
  "target_ref": "ak:message:AVEbR6LJe9T0RIh43YEQxR-vov-d4AbPcHIDId501TNw"
}
```

负例 2（cross-object `ak.redaction` 在合法 `target_ref` 之外试图携带 `message_id` 成员）：

```json schema=schemas/event-payload.schema.json#/$defs/cross_object_redaction_payload expect=invalid first_error="contains:Additional properties are not allowed ('message_id' was unexpected)"
{
  "target_ref": "ak:strand:AVEbR6LJe9T0RIh43YEQxR-vov-d4AbPcHIDId501TNw",
  "message_id": "ak:message:AVEbR6LJe9T0RIh43YEQxR-vov-d4AbPcHIDId501TNw"
}
```

正例 1（cross-object `ak.redaction` 指向非 Message 对象）：

```json schema=schemas/event-payload.schema.json#/$defs/cross_object_redaction_payload expect=valid
{
  "target_ref": "ak:strand:AVEbR6LJe9T0RIh43YEQxR-vov-d4AbPcHIDId501TNw",
  "reason": "privacy_cleanup"
}
```

正例 2（`ak.message.redact` 指向 Message）：

```json schema=schemas/event-payload.schema.json#/$defs/message_redact_payload expect=valid
{
  "message_id": "ak:message:AVEbR6LJe9T0RIh43YEQxR-vov-d4AbPcHIDId501TNw"
}
```

判定要求：

- `cross_object_redaction_payload` 的 `target_ref` 词法空间 MUST 不含 `ak:message:` 分支，且 `message_id` MUST NOT 是其成员；两条负例都 MUST 在写入任何 cell 之前失败。
- `message.redaction_ref` 的取值域因此闭合为 accepted `ak.message.redact` 的 Event id，不需要"多条 redaction 取哪一条"的选择规则。

失败判定：

- reducer 接受指向 Message 的 `ak.redaction` 并把它写入 `ak.component.object.redaction.v1` cell。
- 实现用自维护的前缀 allow/deny 表替代 schema 判据。

### 3.2.3 Vector: Strand / Morph 的 `redacted` post-state 不得保留内容槽

向量名称：

```text
ak.vector.redaction.strand_morph_redacted_content_slot_absent.v1
```

Strand / Morph 的终态经指向该对象的 `ak.redaction` 进入 `redacted`（[`common-fields.md` §5.1](../models/common-fields.md) / §5.2）。
`redacted` 的语义是"内容已按 redaction policy 清除，envelope 与审计元数据保留"，本向量把它固化成可从**单个物化对象**判定的判据：
`state="redacted"` 时 Strand 的 Description 槽（顶层 `content` / `encrypted_content`）与 synthesis 槽
（`tracks.synthesis.content` / `encrypted_content`）MUST 全部缺席；Morph 的 content 槽同理。

负例 1（Strand 声称已 redact，却仍带明文 `content`）：

```json schema=schemas/strand.schema.json expect=invalid first_error="contains:should not be valid under {'anyOf': [{'required': ['content']}, {'required': ['encrypted_content']}, {'required': ['tracks'], 'properties': {'tracks': {'required': ['synthesis'], 'properties': {'synthesis': {'anyOf': [{'required': ['content']}, {'required': ['encrypted_content']}]}}}}}]}"
{
  "id": "ak:strand:AVEbR6LJe9T0RIh43YEQxR-vov-d4AbPcHIDId501TNw",
  "schema": "ak.schema.strand.v1",
  "realm_id": "ak:realm:ATB8eFsjx2SsBFehta_0LQT_Gm9Fe3YTrFRzNi9_ve_v",
  "content": {
    "kind": "ak.content.text",
    "body": "description body that redaction MUST have cleared"
  },
  "tracks": {
    "synthesis": {
      "is_primary": true
    }
  },
  "state": "redacted",
  "state_changed_at": "2026-04-26T00:05:00.000Z",
  "created_by": {"kind":"account","account_id":{"principal_id":"ak:did_core:webvh:z6mkfixture","station_id":"ak:did_core:webvh:z6mkfixturestationexample"}},
  "created_at": "2026-04-26T00:00:00.000Z"
}
```

负例 2（Morph 同形态）：

```json schema=schemas/morph.schema.json expect=invalid first_error="contains:should not be valid under {'anyOf': [{'required': ['content']}, {'required': ['encrypted_content']}]}"
{
  "id": "ak:morph:AWa1nPTHRs4Qn2xLGxu9Kx3lVMxvJvyzFbGkGm2M8Qkd",
  "schema": "ak.schema.morph.v1",
  "realm_id": "ak:realm:ATB8eFsjx2SsBFehta_0LQT_Gm9Fe3YTrFRzNi9_ve_v",
  "schema_refs": [
    "ak.schema.morph.customer_risk.v1"
  ],
  "morph_kind": "customer_risk",
  "content": {
    "kind": "ak.content.text",
    "body": "morph body that redaction MUST have cleared"
  },
  "state": "redacted",
  "state_changed_at": "2026-04-26T00:05:00.000Z",
  "created_by": {"kind":"account","account_id":{"principal_id":"ak:did_core:webvh:z6mkfixture","station_id":"ak:did_core:webvh:z6mkfixturestationexample"}},
  "created_at": "2026-04-26T00:00:00.000Z"
}
```

正例（redact 之后的 Strand post-state，两个槽都缺席）：

```json schema=schemas/strand.schema.json expect=valid
{
  "id": "ak:strand:AVEbR6LJe9T0RIh43YEQxR-vov-d4AbPcHIDId501TNw",
  "schema": "ak.schema.strand.v1",
  "realm_id": "ak:realm:ATB8eFsjx2SsBFehta_0LQT_Gm9Fe3YTrFRzNi9_ve_v",
  "tracks": {
    "synthesis": {
      "is_primary": true
    }
  },
  "state": "redacted",
  "state_changed_at": "2026-04-26T00:05:00.000Z",
  "created_by": {"kind":"account","account_id":{"principal_id":"ak:did_core:webvh:z6mkfixture","station_id":"ak:did_core:webvh:z6mkfixturestationexample"}},
  "created_at": "2026-04-26T00:00:00.000Z",
  "updated_by": {"kind":"account","account_id":{"principal_id":"ak:did_core:webvh:z6mkfixture","station_id":"ak:did_core:webvh:z6mkfixturestationexample"}},
  "updated_at": "2026-04-26T00:05:00.000Z"
}
```

期望结果：

- 所有负例 MUST 被 `strand.schema.json` / `morph.schema.json` 拒绝；每个 `encrypted_content` 形态与同槽的 `content` 形态受同一分支约束。Strand 顶层 Description、Strand Synthesis track、Morph 三个内容面各自的明文 / 密文负例，以及无槽 redacted 与保槽 archived 正例，见 [`redaction-fixture.json`](../../artifacts/fixtures/redaction-fixture.json) 的 `schema_validation_cases`。
- 正例 MUST 通过：reducer / projection MUST 在写入 `state="redacted"` 的同一次转换里清空内容槽，`state_changed_at` 取触发 `ak.redaction` event 的 `created_at`。
- `state="archived"` MUST 仍允许内容槽存在——archive 是可逆软隐藏，不是内容清除；把 archive 也做成清空是实现越权。
- 物化对象上 MUST NOT 出现 `redaction_ref` 一类的对象级 redaction 引用：Strand / Morph 走 cross-object `ak.redaction`，审计链接由 `ak.component.object.redaction.v1` cell 的事件索引提供（[`common-fields.md` §5.2](../models/common-fields.md)）。

### 3.2.4 Vector: event-targeted redaction 不驱动派生对象 state

向量名称：

```text
ak.vector.redaction.event_target_does_not_drive_object_state.v1
```

[`common-fields.md` §5.2](../models/common-fields.md) 的裁决：cross-object `ak.redaction` 的 `target_ref` 为 `ak:event:` 形态时，语义仅是按 `preserve[]` 对该 Event 自身做字段级裁剪，MUST NOT 改变任何对象的 `state`；对象进入 `redacted` 只能由对象 typed-id 形态的 `target_ref` 驱动。对 `id_source=event_derived` 的对象（[`common-fields.md` §6.0](../models/common-fields.md)），`ak:event:<T>` 与 `ak:<对象种类>:<T>` 共享同一 33-octet token，两种拼写都通过 schema，但按 [`encoding.md` §9.5.1](encoding.md) 单字段 subject 取逐字 scalar 的规则落进 `ak.component.object.redaction.v1` 的两个不同 cell，两个 cell 互不影响。

正例 1（event 拼写：目标是 Strand 的 create Event 自身，做字段级裁剪）：

```json schema=schemas/event-payload.schema.json#/$defs/cross_object_redaction_payload expect=valid
{
  "target_ref": "ak:event:AVEbR6LJe9T0RIh43YEQxR-vov-d4AbPcHIDId501TNw",
  "preserve": [
    "created_at",
    "actor_id"
  ],
  "reason": "privacy_cleanup"
}
```

正例 2（对象拼写：同一 33-octet token 的派生对象）：

```json schema=schemas/event-payload.schema.json#/$defs/cross_object_redaction_payload expect=valid
{
  "target_ref": "ak:strand:AVEbR6LJe9T0RIh43YEQxR-vov-d4AbPcHIDId501TNw",
  "reason": "privacy_cleanup"
}
```

期望结果：

- 两条 payload MUST 都通过 schema 校验，并 MUST 各自写入以逐字 `target_ref` 为 subject 的 cell：`ak:event:AVEbR6LJe9T0RIh43YEQxR-vov-d4AbPcHIDId501TNw` 与 `ak:strand:AVEbR6LJe9T0RIh43YEQxR-vov-d4AbPcHIDId501TNw` 是两个不同 subject，OR-Set 不合并。
- 只应用正例 1 时，由该 create Event 派生的 Strand（`ak:strand:AVEbR6LJe9T0RIh43YEQxR-vov-d4AbPcHIDId501TNw`）的 `state` MUST 仍为 `active`，内容槽 MUST 保持原样；redaction 的效果限于该 create Event 自身的字段级裁剪。
- 两个 cell 独立：之后再应用正例 2，Strand 才进入 `state=redacted`；正例 1 是否已接受不影响该转换的 pre-state 校验，反之亦然。

失败判定：

- reducer 把 `ak:event:` 形态的 `target_ref` canonicalize 成派生对象 typed id（改 subject 或改语义）。
- 对 create Event 应用 event-targeted redaction 后把派生对象置为 `redacted`。
- 接受一种拼写后把另一种拼写当作同一 cell 的重复成员丢弃。

### 3.3 Vector: redaction 与 policy scope

向量名称：

```text
ak.vector.redaction.policy_scope.v1
```

输入序列（先后顺序如下）：

1) 正常消息事件（可见策略允许）：`ak.message.create`，
   `event_id="ak:event:AXWWMHEhNONmNH2fWBozZKUEd47PDJKgGBYFfwmvv11u"`，
   `content.body="bad link: spam.example/phish"`。
2) 屏蔽决定：`ak.moderation.decision`，payload 如下。
3) 撤回：`ak.message.redact`，payload 如下。
4) redaction 之后查询 / 回放。

屏蔽决定 payload（必须通过 `ak.moderation.decision` 注册的 `event-payload.schema.json#/$defs/moderation_decision_payload`）：

```json schema=schemas/event-payload.schema.json#/$defs/moderation_decision_payload
{
  "target_ref": "ak:message:AXWWMHEhNONmNH2fWBozZKUEd47PDJKgGBYFfwmvv11u",
  "decision": "quarantine",
  "issuer_id": "ak:did_core:webvh:z6mkfixturePolicyBot",
  "request_canonical_digest": "sha256:5f8b3c2ad4e1907664bb2f0c9d1e3a57c48d6b02fe971a35c8d40b7e9a2f6c1d",
  "action": "quarantine_message"
}
```

撤回 payload（必须通过 `ak.message.redact` 注册的 `event-payload.schema.json#/$defs/message_redact_payload`）：

```json schema=schemas/event-payload.schema.json#/$defs/message_redact_payload
{
  "message_id": "ak:message:AXWWMHEhNONmNH2fWBozZKUEd47PDJKgGBYFfwmvv11u",
  "reason": "moderation_recall"
}
```

两条 payload 用**同一个 typed Message ID** 定址两个不同的 cell family：
`ak.component.moderation_state.v1`（subject = `payload.target_ref`）与
`ak.component.object.redaction.v1`（subject = `payload.message_id`）。目标 Message 是
`ak.message.create` 的 create Event 派生对象，`ak:message:<T>` 与 `ak:event:<T>` 共享同一 token
（[`../models/common-fields.md` §6.0](../models/common-fields.md)）。

期望：

- Projection 不得展示已 redacted 的 `content`，但 timeline 位置与 `event_id` 指纹必须保留用于审计。
- 对 public plaintext scope 的外部审计或对 E2EE scope 的当前授权成员，redaction 后仍应看到 redaction 事实而不是原文；`history_access` 不创建外部读取权限。
- 冻结空间（frozen realm）与历史归档（archived event）场景下，timeline 位置必须保留，不能物理删除。
- `quarantine` 与 redaction 是两条独立 cell 上的断言：redaction 进入不可逆终态后，moderation cell 的
  `quarantine` 仍然可查询，不因 redaction 被折叠或清除。

失败判定：

- 在 redaction 后把事件从 timeline 移除。
- 使用完整明文替代 redaction 保留字段。
- 将 `quarantine` 解释为“删除”而非显示约束。
- 用 `ak.redaction` 而不是 `ak.message.redact` 撤回 Message（§3.2.2），或把两个 cell 的 subject 合并成一个。


### 3.4 Vector: hard erasure receipt

向量名称：

```text
ak.vector.redaction.hard_erasure_receipt.v1
```

期望：

- hard erasure 在被测存储边界内删除 payload bytes 与派生明文。
- 实现保留 verification stub：原始 Event ID、用于结构与冗余一致性校验的 Event digest / proof `event_digest`、redaction Event ID、erasure reason、执行服务 DID、执行时间和签名 receipt。签名 receipt MUST 符合 `ak.schema.erasure_receipt.v1`；若作为历史事件发布，Event.kind MUST 为 `ak.audit.erasure_receipt`。正例 MUST 明确输出 `original_preimage_verified=false`；Event ID 与 digest、stub canonical digest、subject kind 与 ref namespace 任一不一致均 MUST fail closed。
- stub 不得额外保留已擦除明文字段的 standalone content hash、payload-only digest 或未加盐搜索 fingerprint；若审计必须保留内容承诺，必须使用每事件 salt 或 HMAC/pepper commitment，并把 secret 留在 legal-hold 边界或按 erasure policy 销毁。
- backfill 返回 redacted / erased stub，不伪造替代事件，也不静默造成历史缺口。
- legal hold 存在时阻止 hard erasure，但默认展示仍应用 redaction。

### 3.5 Vector: snapshot pruning retains verification stub

向量名称：

```text
ak.vector.redaction.realm_state_snapshot_pruning_stub.v1
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
ak.vector.realm_state_snapshot.inclusion_challenge.v1
```

本向量固化 [`realm-state-snapshot-schema.md`](./realm-state-snapshot-schema.md) §6 `event_set_commitment` 的 inclusion-challenge 采样与 merkle branch 校验规则，使 high-assurance bootstrap 不依赖单一实现的私有判断。该向量已在 [`vector-registry.json`](../../artifacts/registry/vector-registry.json) 中注册为 active，并由 [`sync-fixture.json`](../../artifacts/fixtures/sync-fixture.json) 的 `snapshot_inclusion_challenge` 机器 fixture 及其 registered runner 承载。实现 MUST 执行该 fixture-backed gate，并按本节 prose 与 fixture 固化的规则校验 high-assurance bootstrap。

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

### 3.7 Vector: snapshot state digest recompute

向量名称：

```text
ak.vector.realm_state_snapshot.state_digest_recompute.v1
```

本向量固化 [`realm-state-snapshot-schema.md`](./realm-state-snapshot-schema.md) §3 / §4：chunk payload（`ak.schema.realm_state_snapshot_chunk.v1`）的 `items[]` 是 reducer cell，每个 leaf 与 [`../authz/event-auth-state-resolution.md` §6.2.1](../authz/event-auth-state-resolution.md) 的治理 `state_root` leaf 逐字节相同，`state_digest` 是这些 leaf 的 RFC 6962 root。机器 fixture 是 [`sync-fixture.json`](../../artifacts/fixtures/sync-fixture.json) 的 `snapshot_state_digest` 块，由 `ak.suite.sync.core.v1` runner 承载；fixture 里每个 digest 都由 fixture 自身的 bytes 重算得到，不存在占位值。

输入：

1. 一组 `ak.schema.realm_state_snapshot_chunk.v1` payload，其 `items[]` 覆盖 `cas_register`（含业务值 `null` 与异值 `⊥` 的 heads）、`mv_register`、`fsm`、`or_set`、`ordered_log` 五种 lattice 的 cell；`leaves[]` 逐 item 给出 `leaf_preimage` 与 `leaf`。
2. `digest_algorithm`——该 Realm 的 live digest suite；`sha256` 与 `blake3` 各至少一例。
3. 声明的 `state_digest`；含 `conflict_records` / `erasure_stubs` 的 case 另给出期望的 `verification_hints.*_digest`。

期望：

- verifier MUST 对每个 item 重算 `H(0x00 || canonical_json({"cell": id, "state": state}))`，按 `items` 顺序（跨 chunk 按 `index` 升序拼接）以 `H(0x01 || left || right)` 与奇数层提升组合，得到与声明相同的 `state_digest`；chunk 边界不同不改变结果；空 `items` 得到 `H` over 空字节。
- `kind` 不是 `"cell"` 的 item——包括旧 `object` 分支与 `cas_cell` 字面——MUST 拒绝。`state` 形状与 registry 登记的 lattice 不符（`cas_register` 带 `value`、其它 lattice 带 `heads`）、空 `heads`、`heads` 未按解码 token 升序、`items` 未按 `id` code point 升序、跨 chunk 重复 `id`、`ak.private.*` family、chunk `reducer_profile` 与 manifest 不符，MUST 分别拒绝。
- `⊥` cell 作为 `conflict_records[]` 的 `bottom_cell` 行、erasure stub 作为 `erasure_stubs[]` 行时，`state_digest` 不变；对应的 `verification_hints.conflict_records_digest` / `erasure_stubs_digest` 按 §3 的列表 digest 规则重算一致。
- 声明的 `state_digest` 与重算值不一致 MUST 拒绝；两个 conformant verifier 对同一 fixture MUST 得到相同 accept / reject 结论。

### 3.8 Vector: snapshot restore covered membership

向量名称：

```text
ak.vector.realm_state_snapshot.restore_covered_membership.v1
```

本向量固化 [`realm-state-snapshot-schema.md`](./realm-state-snapshot-schema.md) §3
「恢复后仍须能精确回答 membership」：从 snapshot 恢复的 receiver 对「某个旧 Event 是否属于该 view 的
覆盖集 `C`」只有三种合法答复——`covered`、`not_covered`、以及**缺证据时的 hold**。把 hold 折成
`not_covered` 会让 [`../authz/event-auth-state-resolution.md` §9.3.1.4](../authz/event-auth-state-resolution.md)
的合并式把迟到分支当作「对方从没见过」，复活已被取代的写入；这条向量正是把该折叠固定为拒绝。机器 fixture 是
[`sync-fixture.json`](../../artifacts/fixtures/sync-fixture.json) 的 `snapshot_restore_covered_membership` 块，
由 `ak.suite.sync.core.v1` runner 承载。它的 `event_set_source` 指向同文件的 `snapshot_inclusion_challenge`：
两个向量共用同一份 committed entry 集合与同一个 `event_set_commitment.root`，因此 §6 的挑战与本节的
membership 判定不可能各自漂移。

输入：

1. 一个 manifest 的 `event_set_commitment`（`algorithm`、`root`、`covered_event_count`）与 `frontier.event_ids`。
2. 三类证据之一：`none`（只有 manifest）、`committed_index`（完整 committed entry 列表）、
   `inclusion_proof`（单条 entry 加其在同一 root 下的 audit path 与 leaf index）。
3. 被查询的 `event_id`，包含一个不在 committed 集合内的 `absent_event_id`。

期望：

- 只有 manifest 时：`frontier.event_ids` 中的 Event MUST 判为 `covered`（它按构造在 `C` 内）；其余任何
  `event_id`——含 committed 集合内的与完全陌生的——MUST 判为 hold，MUST NOT 判为 `not_covered`。
- `committed_index` MUST 在其按 `algorithm` 重算的 root 等于 manifest `root`、且长度等于 `covered_event_count`
  时才被采纳。前缀（长度不足）与任一 entry 被改动的列表 MUST 以 `inclusion_proof_failed` 拒绝，且拒绝后
  该 receiver MUST 仍处于「不完整」状态——不得因为看过一份被拒的列表就开始回答 `not_covered`。
- 采纳完整 committed index 后，列表内的 Event MUST 判为 `covered`，列表外的 MUST 判为 `not_covered`。
- `inclusion_proof`：`merkle_event_set_v1` 下，entry 的 audit path 在其真实 leaf index 上验证通过时该 entry
  MUST 判为 `covered`；同一条 path 在**另一个** leaf index 上验证 MUST 拒绝（§6.2 的挑战响应体不携带 index，
  实现 MUST 从自己的排序副本取得它，MUST NOT 接受「哪个位置能对上就算哪个」）。单条证明不使集合完整：其余
  `event_id` MUST 仍为 hold。
- `ordered_event_id_sha256_v1` 对整个排序后的 entry array 一次求值，不存在逐条 audit path；在该 algorithm 下
  提交单条 inclusion proof MUST 以 `inclusion_proof_failed` 拒绝，调用方只能改用 committed index。
- 两个 conformant 实现对同一 fixture MUST 得到相同的 `covered` / `not_covered` / hold / reject 结论。

## 4. Capability Vectors

### 4.1 目标

本文件将 capability 的链式授权、撤销回滚与审批约束固定为跨实现向量。
适配对象（下列为 profile 短名，统一用下划线；canonical id 形如 `ak.profile.<短名>.v1`，见 [`conformance-profiles.md`](./conformance-profiles.md)）：`identity_registry`, `station_events_api`, `e2ee_client`, `enterprise_client`, `agent_runtime`.

向量命名：

```text
ak.vector.capability.<scenario>.v1
```

每个向量应检查：

- selector scope 是否正确绑定到 actor/device/realm/action。
- 授权时间窗约束是否导致一致结果。
- 关键路径必须拒绝 `authorization-only` 假阳性。

### 4.2 Vector: 多级授权链

向量名称：

```text
ak.vector.capability.authority_chain.v1
```

输入事件链。`ak.capability.grant` 的 payload 是 closed `{grant: {...}}`：**顶层 `grant_id` 与
`grant.id` 都被禁止**，durable GrantId 由该 Event 自己的 `event_id` retype 得到
（[`common-fields.md` §6.0](../models/common-fields.md)），因此每一级 grant 的 id 必然互不相同，
且 `issuer_authority_refs` 只能指向**上一级**的 grant，不能自指。

```json
{
  "base": {
    "grant_id": "ak:grant:AU4F2tD66XxDdxMbkmhDwjv3NLmV3MuNzo4ZaaUG__we",
    "subject": "ak:did_core:webvh:z6mkfixtureRootAdmin",
    "actions": [
      "ak.realm.admin"
    ],
    "constraints": []
  },
  "authority_chain": [
    {
      "event_id": "ak:event:ASJ_Qsip8sg5hH5GQ31HnTnuIAUcscQt19nAG23ahzpZ",
      "kind": "ak.capability.grant",
      "realm_id": "ak:realm:AVSHhSS_nHM-k8vB4erfnnvnUFbfkHBYoo9gahFWqZQE",
      "actor_id": "ak:did_core:webvh:z6mkfixtureRootAdmin",
      "payload": {
        "grant": {
          "schema": "ak.schema.capability.v1",
          "issuer": "ak:did_core:webvh:z6mkfixtureRootAdmin",
          "subject": "ak:did_core:webvh:z6mkfixtureOps",
          "issued_at": "2026-04-20T00:00:00.000Z",
          "issuer_authority_refs": [{"kind": "grant", "grant_id": "ak:grant:AU4F2tD66XxDdxMbkmhDwjv3NLmV3MuNzo4ZaaUG__we"}],
          "resources": [
            {
              "kind": "realm",
              "realm_id": "ak:realm:AVSHhSS_nHM-k8vB4erfnnvnUFbfkHBYoo9gahFWqZQE",
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
              "not_before": "2026-04-20T00:00:00.000Z",
              "expires_at": "2026-05-20T00:00:00.000Z"
            },
            {
              "constraint_kind": "quota",
              "constraint_subkind": "rate",
              "effect": "allow",
              "rate_limit": "5/hour"
            }
          ]
        }
      },
      "refs": [
        { "id": "ak:grant:AU4F2tD66XxDdxMbkmhDwjv3NLmV3MuNzo4ZaaUG__we", "role": "authorized_by", "critical": true }
      ]
    },
    {
      "event_id": "ak:event:AfRvTwL9UUVlA868BCCvPbdzYVW8u3JC2w3JgU_Fixho",
      "kind": "ak.capability.grant",
      "realm_id": "ak:realm:AVSHhSS_nHM-k8vB4erfnnvnUFbfkHBYoo9gahFWqZQE",
      "actor_id": "ak:did_core:webvh:z6mkfixtureOps",
      "payload": {
        "grant": {
          "schema": "ak.schema.capability.v1",
          "issuer": "ak:did_core:webvh:z6mkfixtureOps",
          "subject": "ak:did_core:webvh:z6mkfixtureIntern",
          "issued_at": "2026-04-21T00:00:00.000Z",
          "issuer_authority_refs": [{"kind": "grant", "grant_id": "ak:grant:ASJ_Qsip8sg5hH5GQ31HnTnuIAUcscQt19nAG23ahzpZ"}],
          "resources": [
            {
              "kind": "realm",
              "realm_id": "ak:realm:AVSHhSS_nHM-k8vB4erfnnvnUFbfkHBYoo9gahFWqZQE",
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
        }
      },
      "refs": [
        { "id": "ak:grant:ASJ_Qsip8sg5hH5GQ31HnTnuIAUcscQt19nAG23ahzpZ", "role": "authorized_by", "critical": true }
      ]
    }
  ],
  "action_query": {
    "actor_id": "ak:did_core:webvh:z6mkfixtureIntern",
    "action": "ak.invite.create",
    "resource": "ak:realm:AVSHhSS_nHM-k8vB4erfnnvnUFbfkHBYoo9gahFWqZQE",
    "request_time": "2026-04-26T01:00:00.000Z",
    "request_audience": "did:webvh:z6mkfixture:vendor.example"
  }
}
```

期望输出（`valid_chain` 从 root 到 leaf，三个 id 互不相同）：

```json
{
  "authorized": true,
  "valid_chain": [
    "ak:grant:AU4F2tD66XxDdxMbkmhDwjv3NLmV3MuNzo4ZaaUG__we",
    "ak:grant:ASJ_Qsip8sg5hH5GQ31HnTnuIAUcscQt19nAG23ahzpZ",
    "ak:grant:AfRvTwL9UUVlA868BCCvPbdzYVW8u3JC2w3JgU_Fixho"
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

- 忽略中间 authority grant 直接用 root 进行授权。
- 忽略 `allowed_audiences` 约束。
- 时间边界过期仍返回 true。
- 接受 payload 顶层 `grant_id` / `grant.id`，或接受自指的 `issuer_authority_refs`。

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
      "event_id": "ak:event:AQnDPv2cT2zHNw0X3yRESTZ7siOPrC3uPYIGw_-4y3Xc",
      "kind": "ak.capability.grant",
      "payload": {
        "grant_id": "ak:grant:AU4F2tD66XxDdxMbkmhDwjv3NLmV3MuNzo4ZaaUG__we",
        "subject": "ak:did_core:webvh:z6mkfixtureAlice",
        "actions": [
          "ak.message.create"
        ]
      },
      "created_at": "2026-04-26T00:00:00Z"
    },
    {
      "event_id": "ak:event:AZ40M0gsiGLzFmMUgR2bK70BzIPzlFgDZ4SQDGiJbf_U",
      "kind": "ak.capability.revoke",
      "payload": {
        "grant_id": "ak:grant:AU4F2tD66XxDdxMbkmhDwjv3NLmV3MuNzo4ZaaUG__we"
      },
      "created_at": "2026-04-26T00:00:01Z"
    },
    {
      "event_id": "ak:event:AR2f0P9TRB3LOeowwoiHeTViBhQ_rMdZgiCZ7Gv5f4DY",
      "kind": "ak.member.state",
      "payload": {
        "actor_id": "ak:did_core:webvh:z6mkfixtureAlice",
        "membership": "leave"
      },
      "created_at": "2026-04-26T00:00:02Z"
    },
    {
      "event_id": "ak:event:Afv1yWZ8P95DkVvSjRmG15U-fD6yyypjxGbutLtCoxBH",
      "kind": "ak.message.create",
      "actor_id": "ak:did_core:webvh:z6mkfixtureAlice",
      "created_at": "2026-04-26T00:00:03Z",
      "payload": {
        "strand_id": "ak:strand:Ae9FKI-adZOvEof5zBY1v2PJYeqAmPAKj9s4TgyujhGW",
        "content": {
          "kind": "ak.content.text",
          "body": "should_fail_if_revoke_applies"
        }
      },
      "prev_refs": [
        "ak:event:AR2f0P9TRB3LOeowwoiHeTViBhQ_rMdZgiCZ7Gv5f4DY"
      ]
    }
  ],
  "rollback": {
    "target_event_id": "ak:event:AZ40M0gsiGLzFmMUgR2bK70BzIPzlFgDZ4SQDGiJbf_U",
    "reason": "revoke_undo_invalid_signature"
  }
}
```

期望输出：

- 初始解析：`ak:event:Afv1yWZ8P95DkVvSjRmG15U-fD6yyypjxGbutLtCoxBH` 因 revoke 生效应拒绝或标记 soft-fail/rejected（取决于实现策略）。
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
    "event_id": "ak:event:AT2jKggZg_JhHFDAk7sZIweG-eIZI8iycIfLAP8gEw_l",
    "kind": "ak.policy.action",
    "actor_id": "ak:did_core:webvh:z6mkfixtureContractor",
    "realm_id": "ak:realm:AVSHhSS_nHM-k8vB4erfnnvnUFbfkHBYoo9gahFWqZQE",
    "hlc": "01970e589d26-0001-aaaaaaaa",
    "payload": {
      "action_id": "approval-realm-admin-001",
      "value": {
        "action": "ak.realm.admin",
        "approval_required": true,
        "approval_quorum": 2,
        "policy_scope": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5"
      }
    },
    "refs": [
      { "id": "ak:grant:AUWpzOPskuu9fxaWPsUgiijz7I4DgJHTvmXZdHFHlI82", "role": "authorized_by", "critical": true }
    ]
  },
  "capabilities": [
    {
      "kind": "ak.capability.grant",
      "subject": "ak:did_core:webvh:z6mkfixtureContractor",
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

本向量固化 [`realm-and-space.md`](../models/realm-and-space.md) §2.5 与 [`capabilities.md`](../authz/capabilities.md) §3.2：`ak.realm.create` MUST 在同一原子 unit 内物化五条无条件 registered cell write，其中 authority-root 写入是唯一的 `ak.component.realm.authority_root.v1:null` cell，值恰为 `{controller_actor_id = envelope.actor_id, controller_epoch = 0, authority_generation = 0}`；另有五条 registered condition row：`initial_resolution`、`agent_control` 的 Agent status，以及由 `payload.object.purpose` 互斥选择的 `direct_conversation|principal_control|agent_control` history-access `null→since_join` 初始化。每个命中的条件写入都必须包含。

正例：五条无条件 registered write 与条件命中的已登记 write 全部落入 genesis `state_root`，创建者在 genesis Seal 下即具有 effective `ak.realm.owner`；该批 accepted 后，创建者凭 accepted-Seal root-cell inclusion proof 可直接 author `ak.strand.create`（该 kind 在 owner operational coverage 内），也可在 owner 的 `grant_authority_actions` 上界内向成员签发 strand grant。

负例（每条各自 MUST fail closed，不得留下 Realm / membership 半成品）：

- 缺 authority-root cell → `realm_authority_root_missing`；
- author 自行提供 `controller_actor_id` / 非零 `controller_epoch` / 非零 `authority_generation` / 三字段之外的额外成员 → `realm_authority_root_conflict`；
- 夹带旧四项 / 五项 / 三项 founding-grant shape 的 self grant MUST NOT 被识别为 authority root，仍按 §3.2 普通 issuer 上界判定为 `grant_exceeds_issuer_authority`；
- staged root proof 在 genesis batch 之外重放，或在 batch 内改用 accepted-Seal inclusion proof（此时尚无 accepted Seal）→ `realm_authority_controller_mismatch`。

只有 `ak.member.state{join}`、没有任何显式 grant 的成员仍 MUST `missing_capability`：authority root 只为 root controller 建立 authority，MUST NOT 为普通成员建立 baseline capability，也 MUST NOT 由 membership 或 `realm_state.owner` 投影镜像回退推导。

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
- `ak.profile.station_events_api.v1`
- `ak.profile.station.v1`

### 5.2 通用约定

测试向量使用以下简化字段：

```json
{
  "event_id": "ak:event:AQsHmGu_9sPOyJ4aG8VlWQBp8wGGhdC-BjfAaXqrIbk-",
  "actor_id": "ak:did_core:webvh:z6mkfixtureActorA",
  "actor_seq": 1,
  "hlc": "019b76daa800-0000-a13f9c2e",
  "prev_refs": [],
  "refs": [],
  "kind": "ak.strand.update",
  "unsigned": {
    "target_ref_hint": "ak:strand:AVgnD-1YLmV6g-_RiZro8Yzmydn3Q8upFMpAgJW9bsbj"
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

`ak.vector.e2ee.late_key_recovery.t0_deterministic_visibility.v1` 使用唯一二态
`history_access={since_join,all_history_for_current_members}`。request receipt 冻结 direct Seal traversal；T0 从完整 replay 机械派生 winning transition、current 单向收紧 history_access 与 current incarnation/join floor，不存在 activation proof 或 epoch ceiling；
首次 chunk 耐久入队时由 release service 按 current T1 签发 `HistoryReleaseAttestation`。两个客户端以相反本地到达顺序
观察相同 Seal/Event 集合时，必须得到相同 T0 允许范围；T1 失效只拒绝新的交付，不倒写 T0，也不能撤回已合法安装的明文。
`mls_rfc9420` 不产生可交付 history secret，不能进入本向量的正向 chunk 分支。

本节固化两个**独立**向量，各对应 `vector-registry.json` 的不同 id，MUST NOT 合并：

- `ak.vector.e2ee.late_key_recovery.t0_deterministic_visibility.v1`（本节主向量）——断言 receipt-bound direct Seal replay 所得 winning transition、current 单向 history ratchet 与 requester incarnation/join floor
  和 T1 current delivery gate 必须同时执行，且到达顺序 / wall clock 不改变任一结果；不存在 epoch ceiling 或 activation-policy sampling。
- `ak.vector.late_key_recovery.removed_actor.v1`（无 `e2ee.` 段，独立 registry id）——removed_actor negative path
  专项：T0 的合法历史事实不被后来 remove 改写，但 current T1 不允许时必须拒绝新的 key delivery。


### 5.3 Vector: Board Collection Projection

输入：

```json
{
  "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
  "events": [
    {
      "kind": "ak.space.create",
      "unsigned": {
        "target_ref_hint": "ak:space:AdkL35R2W53p6Pt8Wi0dJHZhmP2mvu01sM1lM1wB1lb-"
      },
      "payload": {
        "object": {
          "schema": "ak.schema.space.v1",
          "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
          "kind": "board",
          "title": "Release Board",
          "created_by": {"kind":"account","account_id":{"principal_id":"ak:did_core:webvh:z6mkfixtureAlice","station_id":"ak:did_core:webvh:z6mkfixturestationexample"}},
          "created_at": "2026-04-26T00:00:00Z"
        }
      }
    },
    {
      "kind": "ak.space.create",
      "unsigned": {
        "target_ref_hint": "ak:space:AXOaX0qZYqWHkCJWQN_QI3vVio0uYmZ1va2RASTmBvgm"
      },
      "payload": {
        "object": {
          "schema": "ak.schema.space.v1",
          "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
          "parent_space_id": "ak:space:AdkL35R2W53p6Pt8Wi0dJHZhmP2mvu01sM1lM1wB1lb-",
          "kind": "list",
          "title": "Todo",
          "rank": "U",
          "created_by": {"kind":"account","account_id":{"principal_id":"ak:did_core:webvh:z6mkfixtureAlice","station_id":"ak:did_core:webvh:z6mkfixturestationexample"}},
          "created_at": "2026-04-26T00:00:00Z"
        }
      }
    },
    {
      "kind": "ak.strand.create",
      "unsigned": {
        "target_ref_hint": "ak:strand:AUOjN8M8xm-W1G1Ve9UR6sHKJh7JPG7bM8ZDnzcGJ2Vh"
      },
      "payload": {
        "object": {
          "schema": "ak.schema.strand.v1",
          "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
          "metadata": {
            "title": "Release checklist"
          },
          "tracks": {
            "synthesis": {
              "is_primary": true
            }
          },
          "stage": "planned",
          "created_by": {"kind":"account","account_id":{"principal_id":"ak:did_core:webvh:z6mkfixtureAlice","station_id":"ak:did_core:webvh:z6mkfixturestationexample"}},
          "created_at": "2026-04-26T00:00:00Z"
        }
      }
    },
    {
      "kind": "ak.strand.move",
      "unsigned": {
        "target_ref_hint": "ak:strand:AUOjN8M8xm-W1G1Ve9UR6sHKJh7JPG7bM8ZDnzcGJ2Vh"
      },
      "payload": {
        "board_space_id": "ak:space:AdkL35R2W53p6Pt8Wi0dJHZhmP2mvu01sM1lM1wB1lb-",
        "strand_id": "ak:strand:AUOjN8M8xm-W1G1Ve9UR6sHKJh7JPG7bM8ZDnzcGJ2Vh",
        "target_space_id": "ak:space:AXOaX0qZYqWHkCJWQN_QI3vVio0uYmZ1va2RASTmBvgm",
        "rank": "U"
      }
    }
  ]
}
```

期望：

- Collection projection MUST 返回 `object.id = ak:strand:AUOjN8M8xm-W1G1Ve9UR6sHKJh7JPG7bM8ZDnzcGJ2Vh`。
- 返回项 MUST 位于 `ak:space:AXOaX0qZYqWHkCJWQN_QI3vVio0uYmZ1va2RASTmBvgm`。
- View cursor MUST 绑定 projection、view、frontier 与权限上下文。

### 5.4 Vector: Strand Card Move Read-Your-Writes

输入：

```json
{
  "write": {
    "kind": "ak.strand.move",
    "unsigned": {
      "target_ref_hint": "ak:strand:AUOjN8M8xm-W1G1Ve9UR6sHKJh7JPG7bM8ZDnzcGJ2Vh"
    },
    "payload": {
      "board_space_id": "ak:space:AdkL35R2W53p6Pt8Wi0dJHZhmP2mvu01sM1lM1wB1lb-",
      "strand_id": "ak:strand:AUOjN8M8xm-W1G1Ve9UR6sHKJh7JPG7bM8ZDnzcGJ2Vh",
      "from_space_id": "ak:space:AXOaX0qZYqWHkCJWQN_QI3vVio0uYmZ1va2RASTmBvgm",
      "target_space_id": "ak:space:ASyAdYqXT1HB1Ote94_q4d0fEjCivsUnrUZvZLZsdZSK",
      "rank": "U"
    }
  },
  "query": {
    "object_kinds": [
      "strand"
    ],
    "wait_for": "ak:cursor:barrier_cursor_from_write"
  }
}
```

期望：

- Projection executor 在返回前 MUST 等待本地 frontier 覆盖写入 token，或返回可恢复超时。
- 查询结果中该 Strand item 的 `list_id` MUST 为 `ak:space:ASyAdYqXT1HB1Ote94_q4d0fEjCivsUnrUZvZLZsdZSK`。

### 5.5 Vector: Strand Discussion Track Visibility

输入：

```json
{
  "strand_id": "ak:strand:AUOjN8M8xm-W1G1Ve9UR6sHKJh7JPG7bM8ZDnzcGJ2Vh",
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
  "strand_id": "ak:strand:AcZ7zo-XO3SdWujdVPAfptkNRxg1bf0e_dNvZkecrhTX",
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
  "strand_id": "ak:strand:Afbz6PkMStMJ9TgCQbdVSQUp8vgsQk4KIgJwz_oboAyC",
  "events": [
    {
      "kind": "ak.message.create",
      "unsigned": {
        "target_ref_hint": "ak:message:AYCjW3_3yrl6J9nmZha6rde-D7ADNRZf1cUKIycKTVUb"
      },
      "payload": {
        "strand_id": "ak:strand:Afbz6PkMStMJ9TgCQbdVSQUp8vgsQk4KIgJwz_oboAyC",
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

机器 fixture：`sync-fixture.json#stream_frame_sequence`；执行入口以 fixture `runner` 元数据为准。Runner MUST 对 `ak.self.account.stream.subscribe.v1` 与 `ak.self.events.stream.subscribe.v1` 各执行同一组完整 frame trace，而不是把 frame 拆成互不关联的 schema cases。

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
2. receiver 在 handler 副作用前按 `(sender_account_id, sender_device_id, device_message_id)` 查询 durable 去重记录，并在 handler 结果持久化后记录完成；第二次投递只恢复连续完成位点。
3. 以同一 sender-scoped `device_message_id` 提交不同 canonical target intent；再以两个不同 `device_message_id` 提交相同业务 content。

Expected：

- 第 1/2 步的 durable handler effect 恰执行一次；重复 envelope 仍可计入累计 ack 的连续完成区间，不得永久阻塞队列清理。
- 同 ID 不同内容 MUST 返回 `duplicate_conflict`、reason `device_message_id_conflict`，两个版本均不得新增队列项。
- 不同 ID 是两个独立逻辑消息，即使业务 content 相同也各处理一次。
- 缺少 `device_message_id` 的 envelope 或 send target MUST 在 handler 前以 schema violation 拒绝；kind-specific `transaction_id` / `request_id` 不得替代 envelope ID。

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
- 派生的 unread count、badge 与 push suppression 都以合并 winner 为输入；case 2 选出 B 的实现 MUST 判为 conformance failure。
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
7. **value_tombstone 类型不得物理删除**：对 `deletion_mode=value_tombstone` 的 key（例如 `ak.file_transfer.v1:<transfer_key>`）调用 `ak.self.account_data.resource.delete.v1` MUST 被拒绝；其删除态只能作为 value 写入，且任一副本观察到该终态后 MUST NOT 被后续非 deleted 状态复活。

Expected：

- 服务端 MUST NOT 解密、比较或合并 `content`；所有领域合并只发生在客户端明文上。
- 每个 `(actor_id, account_data_key)` 的 `revision` 单调递增且 MUST NOT 回退；被拒绝的写 MUST NOT 推进它，也 MUST NOT 向其它设备 fanout。
- 任意投递顺序下，所有设备在耗尽重试循环后 MUST 收敛到同一 `(revision, content)`。
- `expected_revision` 只有一处真源：`ak.account_data.set` payload。`resource.replace` 与 `resource.delete` 的 body 都只承载那条调用方签名的 Event，因此缺少它 MUST 在 handler 前以 `schema_violation` 拒绝，而不是在三处各校验一遍（`resource.delete` 的 query 参数已随之取消）。

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
   （`ak.views.private.ak:view:<44-char-event-token>`、`ak.notifications.inbox.ak:notification:<uuidv7>`）。
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
   `ak.self.account_data.resource.delete.v1` MUST 接受；删除后 `resource.get` 返回 `not_found`
   且带 revision high-water mark，离线设备的旧 `expected_revision` 重写 MUST 以 `cas_conflict`
   拒绝，不得复活。

Expected：

- case 1 的每个被拒 key 都不得产生任何存储副作用，也不得改变 revision。
- case 2 与 case 3 合起来构成完整闭合：服务端保证密文，客户端保证语义；只做其中一半的实现
  MUST 判为 conformance failure。
- key 内嵌完整 typed id 带来的存在性泄露是 registry 已接受的取舍（与 `ak.tags.realm.<realm_id>`
  同级）；实现 MUST NOT 再往 key 里追加 `realm_id`、`title` 或其派生物扩大泄露面。

### 5.12 Vector: Station-CAS Account Data 的 baseline 与增量

`vector_id`: `ak.vector.sync.station_cas_account_data.v1`

机器 fixture：`sync-fixture.json#station_cas_account_data`；执行入口以 fixture `runner` 元数据为准。
唯一真源是 [`../sync/client-sync.md` §9](../sync/client-sync.md) 的 `account_data.station_cas` 段与
[§13](../sync/client-sync.md) 的 initial baseline 义务。本向量固化的是 CAS-only holder-private cell
（当前是 `ak.account.invite_delivery` 与 `ak.account.holder_quarantine`）经 account subscribe 的
投影语义——它们不是 holder-authored Event，account-data 诊断面与本 frame 是同一权威 revision 的两个读取形态。

Cases：

1. **initial baseline 完整且无 removals**：`complete=true` 的 baseline MUST 含当前 registry 中**全部**
   holder-readable Station-CAS live row，`removals` MUST 为空。
2. **零行也必须是 complete container**：holder 当前没有任何 live row 时仍 MUST 返回空的 `complete=true`
   容器，使客户端能清除陈旧本地投影，而不是把「没有该字段」当作「无变化」。
3. **filter 不得裁掉 baseline**：请求 filter 省略了一个确实存在的 live row 时，该 trace MUST 判为
   conformance failure。
4. **complete baseline 不得携带 removals**：`complete=true` 语义是客户端先清空本地 live set 再应用
   `upserts`，同帧内的 removal 没有已定义含义。
5. **增量 upsert 只推进该 key**：更高 revision 的 upsert 只改该 key。
6. **增量 removal 只清该 key**：removal 携带 `account_data_key` / `revision` / `updated_at`。
7. **缺席不是删除**：增量帧里没出现的 key MUST 保留本地值。只有 `complete=true` 或显式 removal 才能丢弃一个 key。
8. **更低 revision fail closed**：客户端对每个 key 只接受更高 revision。
9. **同 revision 不同 value 是同步冲突**：MUST 触发 resync，MUST NOT 当作 no-op 或静默覆盖。
10. **同 key 窗口内合并到最后一项**：增量帧可把同一 key 合并为 cursor 窗口内的最后一项，客户端应用的是最终 revision。
11. **Station-CAS 行不得合成为 holder Event**：同一行同时出现在 `account_data.events[]` 里的合成
    `ak.account_data.set` MUST 判为 conformance failure。两类真相源不得互相合成或镜像。
12. **填不满的 cursor 区间必须 drop / resync**：变更记录保留期不再覆盖请求的 `after` 位置时，服务端 MUST
    返回 `dropped` 或 `resync_required`，MUST NOT 发一个静默跳过该区间的增量帧。

Expected：

- server runner MUST 证明 accepted Station-CAS 写入、该 key 的投影位置推进与可重放变更记录在同一事务内，
  且 cursor 覆盖该位置；client runner MUST 证明 revision 单调性与 baseline 清理语义。
- 单帧均通过 `account-subscribe-frame.schema.json`、但整体语义违反任一 case 的 trace，仍视为 conformance failure。
- `to_device` 里的 `ak.account_data.update` 只是低延迟唤醒，MUST NOT 被当作第三个真相源，也不得代替
  baseline 与增量；只实现唤醒路径的客户端 MUST 判为 conformance failure。

### 5.13 Vector: ContactRemark 明文值的结构与领域校验

`vector_id`: `ak.vector.contacts.remark_value.v1`

机器 fixture：`contact-remark-fixture.json`；执行入口以 fixture `runner` 元数据为准。唯一真源是
[`../discovery/client-preferences.md` §3.6](../discovery/client-preferences.md) 与
[`../artifacts/schemas/contact-remark.schema.json`](../../artifacts/schemas/contact-remark.schema.json)。

本向量分两半，实现 **MUST** 两半都过；只过其中一半的实现 MUST 判为 conformance failure：

- **结构半**（`schema_validation_cases`）：封闭形状、`version` 常量、`subject` 封闭对象、
  `petname` 与 `confirmed_display_name` 共用同一个 `display_text_128`（同一个 129 码点值在两侧都必须被拒）、
  128 码点边界按 **Unicode code point** 而非 UTF-8 字节或 UTF-16 code unit 计数、
  `note` 4096 上限且允许空串、`verified_handle_at_save` 只接受 canonical `<localpart>:<domain>` wire form、
  未知成员 / `null` / 裸 `{}` / 错误 `subject.kind` / 控制字符与 bidi override 一律拒绝。
- **领域半**（`semantic_cases`）：schema 通过**不**等于值可用。解密后 MUST 用
  `subject.principal_id` 与 holder namespace key 重算 `<principal_key>` 并与读到的 storage key 精确比较；
  AAD / namespace key 不符或 AEAD open 失败时 MUST 保留本地已验证记录、且不得阻断同批其它 key；
  `confirmed_display_name` 只能由用户当场显式确认刷新，普通 petname / note / tags / pin 编辑 MUST 保留它，
  也 MUST NOT 借 optional 悄悄清除；没有 Profile evidence 的 Contact accept 产出的是**没有**确认基准的合法值，
  不得回退到 Realm override / MemberIdentity display / Directory 裸结果 / OIDC `name`；
  `tags` 的命名空间按 §3.1 作为领域规则校验（array-of-string 通过 schema 不代表命名空间合法），
  未识别的 `ak.*` tag MUST 原样保留回写；Contact tombstone / suspended 期间备注 MUST 保留，
  同一 `peer.principal_id` 重新 accepted 时继续使用原记录、不重键。

**校验点（normative）**：producer 在加密与签名之前校验最终待写明文（含 CAS 重试合并出的那一版），
consumer 在 AEAD 解密之后、应用之前校验。承载该 key 的 Station 没有密钥，
MUST NOT 因本向量要求明文、明文镜像或服务端 validator。


## 6. Space Lifecycle Vectors

### 6.1 目标

本节定义 Space（看板 / 列 / 泳道 / calendar bucket / page group ...）`active` ↔ `archived` ↔ `tombstoned` 状态机的跨实现测试向量。canonical 写入路径见 [`../models/realm-and-space.md` §3.4](../models/realm-and-space.md)；canonical 状态机对齐见 [`../models/common-fields.md` §5](../models/common-fields.md)。

实现声称支持以下 profile 时 SHOULD 运行本节向量：

- `ak.profile.kanban_mvp.v1`
- `ak.profile.full_client.v1`
- `ak.profile.station.v1`

### 6.2 Vector: Space Archive 然后 Restore（happy path）

输入（按 causal order 应用）：

```json
{
  "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
  "events": [
    {
      "kind": "ak.space.create",
      "unsigned": {
        "target_ref_hint": "ak:space:AdkL35R2W53p6Pt8Wi0dJHZhmP2mvu01sM1lM1wB1lb-"
      },
      "payload": {
        "object": {
          "id": "ak:space:AdkL35R2W53p6Pt8Wi0dJHZhmP2mvu01sM1lM1wB1lb-",
          "schema": "ak.schema.space.v1",
          "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
          "kind": "board",
          "title": "Release Board",
          "created_by": {"kind":"account","account_id":{"principal_id":"ak:did_core:webvh:z6mkfixtureAlice","station_id":"ak:did_core:webvh:z6mkfixturestationexample"}},
          "created_at": "2026-05-15T10:00:00Z"
        }
      }
    },
    {
      "kind": "ak.space.archive",
      "unsigned": {
        "target_ref_hint": "ak:space:AdkL35R2W53p6Pt8Wi0dJHZhmP2mvu01sM1lM1wB1lb-"
      },
      "created_at": "2026-05-15T10:05:00Z",
      "payload": {
        "space_id": "ak:space:AdkL35R2W53p6Pt8Wi0dJHZhmP2mvu01sM1lM1wB1lb-",
        "reason": "release_cycle_complete"
      }
    },
    {
      "kind": "ak.space.restore",
      "unsigned": {
        "target_ref_hint": "ak:space:AdkL35R2W53p6Pt8Wi0dJHZhmP2mvu01sM1lM1wB1lb-"
      },
      "created_at": "2026-05-15T10:10:00Z",
      "payload": {
        "space_id": "ak:space:AdkL35R2W53p6Pt8Wi0dJHZhmP2mvu01sM1lM1wB1lb-",
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
  "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
  "pre_state": {
    "space": {
      "id": "ak:space:AdkL35R2W53p6Pt8Wi0dJHZhmP2mvu01sM1lM1wB1lb-",
      "state": "active"
    }
  },
  "event": {
    "kind": "ak.space.restore",
    "unsigned": {
      "target_ref_hint": "ak:space:AdkL35R2W53p6Pt8Wi0dJHZhmP2mvu01sM1lM1wB1lb-"
    },
    "created_at": "2026-05-15T11:00:00Z",
    "payload": {
      "space_id": "ak:space:AdkL35R2W53p6Pt8Wi0dJHZhmP2mvu01sM1lM1wB1lb-"
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
  "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
  "pre_state": {
    "space": {
      "id": "ak:space:AdkL35R2W53p6Pt8Wi0dJHZhmP2mvu01sM1lM1wB1lb-",
      "state": "tombstoned",
      "state_changed_at": "2026-05-15T09:00:00Z"
    }
  },
  "event": {
    "kind": "ak.space.restore",
    "unsigned": {
      "target_ref_hint": "ak:space:AdkL35R2W53p6Pt8Wi0dJHZhmP2mvu01sM1lM1wB1lb-"
    },
    "created_at": "2026-05-15T12:00:00Z",
    "payload": {
      "space_id": "ak:space:AdkL35R2W53p6Pt8Wi0dJHZhmP2mvu01sM1lM1wB1lb-"
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
  "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
  "pre_state": {
    "space": {
      "id": "ak:space:AdkL35R2W53p6Pt8Wi0dJHZhmP2mvu01sM1lM1wB1lb-",
      "state": "archived",
      "state_changed_at": "2026-05-15T10:05:00Z"
    }
  },
  "event": {
    "kind": "ak.space.archive",
    "unsigned": {
      "target_ref_hint": "ak:space:AdkL35R2W53p6Pt8Wi0dJHZhmP2mvu01sM1lM1wB1lb-"
    },
    "created_at": "2026-05-15T11:30:00Z",
    "payload": {
      "space_id": "ak:space:AdkL35R2W53p6Pt8Wi0dJHZhmP2mvu01sM1lM1wB1lb-"
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
  "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
  "pre_state": {
    "space": {
      "id": "ak:space:AdkL35R2W53p6Pt8Wi0dJHZhmP2mvu01sM1lM1wB1lb-",
      "state": "tombstoned",
      "state_changed_at": "2026-05-15T09:00:00Z"
    }
  },
  "event": {
    "kind": "ak.space.tombstone",
    "unsigned": {
      "target_ref_hint": "ak:space:AdkL35R2W53p6Pt8Wi0dJHZhmP2mvu01sM1lM1wB1lb-"
    },
    "created_at": "2026-05-15T12:00:00Z",
    "payload": {
      "space_id": "ak:space:AdkL35R2W53p6Pt8Wi0dJHZhmP2mvu01sM1lM1wB1lb-"
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
  "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
  "pre_state": {
    "space": {
      "id": "ak:space:AdkL35R2W53p6Pt8Wi0dJHZhmP2mvu01sM1lM1wB1lb-",
      "state": "archived",
      "state_changed_at": "2026-05-15T10:05:00Z",
      "title": "Release Board"
    }
  },
  "event": {
    "kind": "ak.space.update",
    "unsigned": {
      "target_ref_hint": "ak:space:AdkL35R2W53p6Pt8Wi0dJHZhmP2mvu01sM1lM1wB1lb-"
    },
    "created_at": "2026-05-15T11:45:00Z",
    "payload": {
      "space_id": "ak:space:AdkL35R2W53p6Pt8Wi0dJHZhmP2mvu01sM1lM1wB1lb-",
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

## 7. AccountId 身份向量

### 7.1 规范形式与相等性

`AccountId` 是闭合对象 `{principal_id, station_id}`，两个分量都 MUST 是 canonical
`did_core_id`。用于比较、签名和 cell key 投影的 JCS canonical bytes 为：

```json
{"principal_id":"ak:did_core:webvh:z6mkfixturealice","station_id":"ak:did_core:webvh:z6mkfixturestationa"}
```

实现 MUST 接受成员输入顺序不同但 JCS bytes 相同的对象。缺少任一分量、增加未知成员、使用带参数、路径、查询或 fragment 的 DID、
handle、本地数据库键，或从请求上下文推断任一分量时，MUST 拒绝。

### 7.2 同一 principal core 位于两个服务器

给定相同 `principal_id` 与两个不同 `station_id`，reducer MUST 派生两个不同账号身份与两个不同账号
membership cell。一个 AccountId 的 join、leave、grant、MLS ownership 与邀请接受 MUST NOT 影响另一个。
相等性 MUST 比较两个 typed 分量，不得比较原始 JSON 文本，也不得只比较 `principal_id`。

### 7.3 AccountId 单点变异失败

从有效的 signed AccountId transcript 出发，分别改变 `principal_id`、改变 `station_id`、删除任一成员、
增加未知成员，或把任一分量换成非 canonical 表示。每个变异 MUST 在任何状态写入前因签名、schema 或 exact identity
验证失败。resolver、DID Document、session audience 与接收服务 MUST NOT 补齐缺失分量。

### 7.4 ActorId 分支隔离

所有 Station 承载主体（人类、Agent、Ghost、integration）使用
`{kind:"account",account_id:{principal_id,station_id}}`；直接著写的 service 使用
`{kind:"service",service_id}`。同一 AccountId 不因主体分类或凭证类别产生第二种身份；Account 与 Service
即使包含相同 DID Core 文本也不相等。未知 discriminator、扁平 principal/station 对象、缺失分量与
未知字段 MUST 拒绝。discriminator MUST 与已接受的 registration / admission evidence 相符；
Agent 的 provisioning、controller、lifecycle 与 runtime key 授权必须单独验证，不得由 account 分支推断。
## 8. Handle Vectors

### 8.1 目标

验证 `@user:domain` / `user@domain` 只作为人类可读寻址输入；账号 handle claim 与 Directory resolve 输出必须绑定
exact `AccountId`，不得输出裸 `principal_id` 后再由调用方猜测 Station。

### 8.2 Exact AccountId 解析与邀请

1. 解析有效 handle，获得签名覆盖的 `subject_account_id={principal_id,station_id}`；
2. 调用方验证 handle claim、issuer、Directory trust、expiry、audience 与 exact AccountId；
3. 定向邀请把该值原样写入 `invitee_account_id`，投递服务由其中 `station_id` 做 service resolution；
4. 只有同一个 exact AccountId 的 holder-authenticated accept 才能物化 membership。

同 core、不同 server 的账号、只匹配裸 `principal_id` 的候选、过期 claim、错误 issuer、额外 JSON 成员、以及从
DID Document 或当前服务补出的 server 分量均 MUST 被拒绝。Handle claim 与 Directory 输出只提供寻址证据，不能替
目标账号接受邀请，也不能直接写 membership。
## 9. Security Closure Vectors

本节收拢跨章节引用的安全闭环向量。每个 `vector_id` 均为规范性引用目标；结构化覆盖位于 [`../../artifacts/fixtures/security-closure-fixture.json`](../../artifacts/fixtures/security-closure-fixture.json)，`tools/artifact_lint` 会校验该 fixture 覆盖本节要求的 security closure vector set，并校验每个 step 暴露可由实现测试消费的 `runner.given_state` / `operation` / `transcript` / `expected_state_transition` / `expected_external_response` / `expected_audit_reason` 字段。实现不得把这些 ID 当成仅供说明的标签。

### 9.1 Vector: Federation Replay After Key Revoke

`vector_id`: `ak.vector.federation.idempotency_after_key_revoke.v1`

Steps：

1. Origin service `did:webvh:z6mkfixture:alpha.example` 使用 active service key 向 destination 提交 `POST /_arkret/peer/events`（`ak.peer.events.command.submit.v1`），header 绑定 `Source-Service-ID`、`Destination-Service-ID`、`Source-Trust-Domain`、`Destination-Trust-Domain`、`Content-Digest`、`Idempotency-Key`，批次 accepted；destination 从已验证 body bytes 内部计算 request digest。
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
- 前两种情况（security frontier 未覆盖 `media_service_decrypts`、SFU 未列入 `plaintext_visible_services`）的稳定失败原因均为已注册的 `media_plaintext_service_not_authorised`（见 `../../artifacts/registry/error-code-registry.json`，其描述同时覆盖这两个子情形）；UI 未显示 required plaintext warning 的情况 MUST 以等价稳定 reason_code 拒绝 join。

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

1. 认证 principal 调用 `ak.self.invite_locator.command.issue.v1`，确认响应 token 至少 192 bit 熵、响应含 `Cache-Control: private, no-store`、服务端仅持久化 digest；分别发行 reusable 与 `one_time_use=true` locator。
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

本向量固化 [`third-party-invites.md`](../sync/third-party-invites.md) §4.3 的 Realm reducer 权威要求。机器可执行样本位于 [`../../artifacts/fixtures/security-closure-fixture.json`](../../artifacts/fixtures/security-closure-fixture.json)；runner MUST 同时消费 prose 与 fixture，不得只依赖验证服务或 Station sync surface 入站预检。

Steps：

1. 正路径：Realm frontier 中存在 `state="pending"` 的 `ak.invite.third_party`，`token_commitment`、`claim_nonce`、`verification_id` allowlist、`binding_proof`、`subject_proof` 和 `expires_at` 均有效。
2. Binding proof signature replay：`binding_proof.signature` 来自另一组 `invite_id` / `token_commitment` / `claim_nonce` / `invite_digest` transcript。
3. Subject proof old DID key：`subject_proof.verification_method` 曾属于 `subject_id`，但不在当前 DID document 的有效 verification method 集。
4. Subject proof transcript replay：`subject_proof.transcript_digest` / signature 绑定的是另一份 `binding_proof_digest` 或 verification service。
5. Token commitment mismatch：`ak.invite.claim.payload.token_commitment` 不等于 pending invite 的 commitment。
6. Allowlist 复校验失败：验证服务曾签发 binding proof，但当前 effective Realm policy 已移除该 `verification_id`。
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

1. 第三方邀请 token 已被验证服务原子消费并签发了绑定 `subject_id=ak:did_core:webvh:z6mkfixtureAlice` 的 `binding_proof`。
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

- Realm 声明 `ak.profile.mls.minimal_metadata_realm.v1`；内容 Event `actor_id` 为 Realm-scoped pairwise `ActorId` core，且该 actor 的 current member cell 为 active。
- Encrypted envelope 固定 `(group_id, epoch, key_ref.group_state_ref)`，该 accepted group state 有一条 active RFC 9420 basic credential identity 等于 `utf8(actor_id)` 的 LeafNode。
- Event proof verification-method 的 bare base 是 canonical `did:key` Did，adapter 投影逐字等于 `actor_id`；transport bearer session actor 可以不同，但只承担访问与限流。

Cases：

1. 唯一 active leaf，Event proof key 与 LeafNode `signature_key` 相同且签名有效：接受为 verified pairwise author。
2. 同一 pairwise identity 对应多条 active leaf、leaf 已在该 epoch 被移除、group-state ref 不是该 epoch winning state、verification-method base 投影为另一 actor、proof key 与 leaf key 不同：均以 `minimal_metadata_author_credential_invalid` 拒绝。
3. pairwise actor 不是 current Realm member：以 `capability_denied` 拒绝；不得借 transport session 的 membership 放行。
4. Realm 未声明 minimal-metadata profile 或 payload 不是本节加密内容而 actor/session 不同：以 `actor_session_mismatch` 拒绝。
5. 客户端尝试把已绑定另一 Realm 的同一 pairwise key/ActorId 用于本 Realm：本地拒绝，网络提交计数为 0。
6. 实现尝试用 principal-scoped `keys/query` 兜底：拒绝该实现路径，目录调用计数必须为 0。

Expected：

- 作者性验证只建立 pairwise sender leaf 身份，不揭示 principal；principal 提升仍依赖独立、端到端加密的 `ak.identity_link`。
- transport bearer 不写入 identity link，不成为作者、member 或 capability authority。
- Receiver 不得回退 current epoch、未验证 ratchet-tree cache、真实 principal DID 或 principal device directory。
- 所有失败 case 都在内容进入 verified timeline 前 fail closed。

## 10. Service Closure Vectors

### 10.1 Vector: Signal Class And TTL

`vector_id`: `ak.vector.signal.class_ttl.v1`

Steps：

1. Actor 提交 `signal_class=moderation`，但 current Seal basis 不允许 moderation signal。
2. Actor 持有 signal 资格后，提交超出 `signal_class=session` 30 秒上限的 envelope。
3. Signal rail 暂时不可用。

Expected：

- 第 1 步 MUST 返回 `signal_class_denied`。
- 第 2 步 MUST 返回 `signal_ttl_out_of_range`。
- 第 3 步 MUST 返回 `signal_rail_unavailable`，且不写 durable Event、不推进 actor_seq / Realm frontier。

### 10.2 Vector: Projection Pagination Shape

`vector_id`: `ak.vector.projection.pagination_shape.v1`

Steps：

1. 调用 `ak.self.space.read.list.v1` / `strand` / `morph`，请求 `limit=1`。
2. 使用返回的 `next_cursor` 继续读取。
3. 下游 service-call 返回缺失 `has_more` 或 cursor 形态不合法的响应。

Expected：

- 每个响应 MUST 带 `has_more`；有后续页时 MUST 带合法 `ak:cursor:*`。
- Cursor MUST 绑定调用者、selector 和 projection purpose，不得跨 service / Realm 复用。
- 缺失分页闭包字段时上游 MUST 归类为 `response_invalid`。

### 10.3 Vector: KeyPackage Exhaustion And Claim Limits

`vector_id`: `ak.vector.keypackage.exhaustion_claim_limits.v1`

Steps：

1. Device 可用 KeyPackage 数量低于 `keypackage_min_available`。
2. 同一 `(requester_id, target_principal_id)` 在 60s 内发起超过 5 次 claim。
3. 已 claimed KeyPackage 到达 `expires_at` 后再尝试 consume。

Expected：

- Client MUST 从 endpoint-scoped 本地 inventory ledger 计算缺口，并在一次 single-flight maintenance cycle 中只发送一个不超过启动时 deficit 的批次；健康 inventory 重载零上传，server response 不返回库存数量。
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

对有效 Direct Conversation claim 分别施加以下单点变异：移除 / 过期 participant authorization、替换 participant signature 所绑定 destination、让 source 不是 requester home authority、破坏外层 service signature、移除任一方 current directional Contact head或其 `direct_message` scope、扩大 required capability，或令 `last_resort_allowed=true`。不得增加 Consent 兼容门槛。

Expected：

- 每个变异都 MUST 在 CAS 前失败，目标 KeyPackage 状态不变；participant 与 service 两层授权不可互相替代。
- 已通过外层 service authentication 的所有 participant / target / policy 业务失败对 peer caller 均为同一 `claim_failed` 外观；响应不得带 `available_count`、逐设备 `failures[]` 或 last-resort record。外层 service signature 变异必须在读取 target 前返回 target-independent `unauthenticated` / `signature_invalid`。
- Participant authorization 必须绑定 exact claim fields 与 stable `{source_id,destination_id}`；部署态 trust domain 只由 source Station 经 verified ServiceResolution + Describe 得出并由外层 RFC 9421 headers 绑定，客户端不得猜测 URL/domain。
- Direct Conversation request 必须同时绑定 pair key、Realm、main Strand 与 MLS group，且不得启用 last-resort。

### 10.3.4 Vector: Self Claim Authorization And Idempotency

`vector_id`: `ak.vector.keypackage.self_claim_authorization_idempotency.v1`

Steps：

1. requester 每次新尝试只生成一个至少 128-bit CSPRNG `claim_request_id`，并分别以 closed `device`、`agent` 与 `minimal_metadata_pairwise` requester authorization 提交 canonical claim；同一值同时作为 `Idempotency-Key`、durable ledger identity 与后续 `claim_envelope` canonical 签名 transcript 中从 exact `claim_receipt.claim_request_id` 派生的同名 challenge，不得生成第二个 `claim_nonce`，也不得在 envelope wire 中复制 `nonce`。authorization 签名覆盖 exact claim fields 与 `service_binding={source_id,destination_id}`。device/Agent 分支由 current accepted authorization Event / pairing 与 active generation 证明当前授权；pairwise 分支由 exact `ak:did_core:key:<mb>` + `did:key:<mb>#<mb>` key、Realm current membership 和 ActorId routing authority 证明。source Station 在任何 remote call 前完成 durable admission，destination 只以同一请求执行唯一 CAS。authority 在 destination 接受后丢失响应。
2. source Station 先按同一 `claim_request_id + request_digest` 查询不确定结果；若为 `unknown` 才原样重发 command。再以同一 identity 修改 target / Realm / selector 得到另一 digest。
3. 分别施加缺 authorization、混合/开放 branch、wrong service binding、wrong authorized Event/method、stale/future authorization、短 `claim_request_id`、额外旧 `claim_nonce`、未被 PCR 接受的设备、已 fence/revoke 的设备或 generation、Agent/service key 冒充普通设备、pairwise actor 与 method multibase 不一致、pairwise actor 不在 intended Realm、current delivery service 不等于 signed source、仅 bearer token、以及 authorization 有效但 target policy 不满足的单点变异。

Expected：

- 正例必须按 `ak.keypackage-claim-authorization-v1` transcript 重建并验证 participant authorization；KeyPackage `published -> claimed` CAS、`(source_id, claim_request_id, request_digest)` ledger 与签名 receipt/outcome 只有一个线性化点，CAS 次数恰为 1。
- 相同 identity/digest 的重试或 query 返回原 outcome，不得再次选择 KeyPackage；冲突 digest 在 inventory lookup 前以统一 `claim_failed` fail closed，内部 reason 为 `duplicate_conflict`。
- 所有 proof/schema/freshness/authority 变异都在读取 target inventory 或改变状态前失败；proof 不替代 sender-constrained transport authentication、当前 revoke/lifecycle、完整 target ActorId 检查、target policy 或后续 MLS claim envelope。pairwise actor 不得被要求创建 account/device，也不得由 transport session actor 推断。
- 首次到达的过期请求绝不创建 claim；已有 terminal ledger 只能向当前仍被授权的同一 requester/session binding 返回原 outcome。同一 `claim_request_id` 的 exact replay 返回 byte-identical 原 outcome，payload drift 冲突；新的 claim 尝试必须生成新的 `claim_request_id`，任何重放都不能创建第二次 claim。

### 10.3.5 Vector: Minimal-metadata Pairwise KeyPackage Full Lifecycle

`vector_id`: `ak.vector.keypackage.minimal_metadata_pairwise_full_lifecycle.v1`

Steps：

1. Realm-local account ActorId 中的 `account_id.principal_id=A=ak:did_core:key:<mb>` 以 exact `M=did:key:<mb>#<mb>` 发布 KeyPackage；transport session 只承担访问与限流，不要求 session actor 等于 A。服务端验证完整 ActorId、A/M、current Realm membership 与 routing-service projection，并逐条验证 MLS Leaf BasicCredential 和 signature key。
2. requester 以 `minimal_metadata_pairwise` authorization 领取 exact A/M KeyPackage；source 与 destination 分别验证 requester/target current ActorId routing authority，destination CAS 后签发 claim receipt。
3. sender 提交 closed pairwise `ak.mls.welcome`，claim record、claim receipt、claim envelope 与 top-level recipient 逐字绑定 A/M/Realm/KeyPackage；recipient 用 M 接受并签发 durable receipt。
4. A/M 以 single-claim consume request 原子消费，服务返回首次签发的 signed consume receipt；同一 canonical request 重放必须返回 byte-identical receipt。

Expected：

- 全链不得创建或要求 account、Device、PCR 或 Agent authorization；真实 transport identity 不得进入 pairwise durable Event。
- 对 A/M multibase 不一致、wrong Realm、wrong current delivery service、混入 device/Agent 字段、Leaf credential/key 属于另一 endpoint、claim/Welcome/receipt 坐标交叉拼接、membership leave/revoke 后或使用不同 ActorId 继续 publish/claim/Welcome/consume 的每个单点变异都必须在状态改变前 fail closed。
- source/destination relay 必须验证 service receipt controller、durable claim ledger 与 exact request digest；普通本地 Welcome 不得绕过同一 ledger admission。
- consume request 和 outcome 采用 singular claim 模型；exact replay 返回原 receipt，任何 request 或 nested durable receipt 漂移均为 conflict。

### 10.4 Vector：国际化标识符 profile 与 authority-local 冲突索引

`vector_id`: `ak.vector.identity.internationalized_identifier_profiles.v1`、`ak.vector.identity.authority_local_skeleton_collision.v1`

Runner 必须分别测试“用户输入 preparation”和“canonical receiver validation”：前者可把 width/case 与 domain U-label 转为 canonical 值，后者必须拒绝任何仍需改写的 wire 值。localpart / Agent slug 使用登记版本的 RFC 8265 derived profile；domain 使用 UTS #46 Nontransitional + STD3/Bidi/Joiner/hyphen/DNS-length/round-trip 完整校验。`title` 等单行显示文本必须允许多语言、emoji 与合理混合脚本，同时拒绝 non-NFC、CR/LF、C0/C1、BOM、bidi format control 和纯空白。

UTS #39 skeleton 只在同一 authority、同一 namespace 的注册事务中作为派生冲突索引。同一 authority 的 handle skeleton 冲突返回 `failed_precondition` + `handle_homograph_forbidden`；不同 authority 或 handle/realm-alias 跨 namespace 不得冲突。Runner 必须断言 skeleton 不参与 canonical equality、签名或 wire 编码；Unicode/UTS #39 数据升级只重建派生索引，不得改写既有 canonical 标识符。DID 和 email local-part 的比较仍由各自 method/provider profile 决定，不得被 Arkret generic normalizer 合并。

### 10.4.1 Vector：producer-allocated UUIDv7 身份冲突

`vector_id`: `ak.vector.identity.producer_allocated_collision.v1`

Runner MUST 从 `id-kind-registry.id_kinds[]` 动态选择全部
`id_form="producer_allocated" && identity_authority="producer_signature"` 行，并对每一行执行
[`producer-allocated-identity-fixture.json`](../../artifacts/fixtures/producer-allocated-identity-fixture.json)
的同一五例：合法 authority 首次原子 reservation、同 authority 与相同 canonical binding 的 exact replay、
同 authority 与不同 binding 的 reject-and-quarantine、不同 authority 复用同一 UUID 时按
`(mint_authority, typed_id)` 分成两个身份，以及 bare typed-ID lookup / 未授权 allocator 拒绝。Runner
不得维护手写 kind allowlist；fixture 的 `selected_id_kinds` 只是由 lint 对 registry 重算的漂移哨兵。
冲突例必须断言没有 overwrite、merge 或 last-writer-wins。

### 10.5 Vector: Session Grant Audience Binding

`vector_id`: `ak.vector.auth.session_grant_audience_binding.v1`

Steps：

1. Returning-human client 以 `Authorization: DPoP <account_handoff_grant>`、匹配 RFC 9449 DPoP 与闭合 `HumanSessionGrantRequest` 请求签发；请求中的 `audience` 与目标 resource server 不匹配。
2. 攻击者篡改 accepted-device proof 绑定的 `request_id`、`account_subject`、`account_handoff_grant_digest`、principal、device、audience、holder JKT、verification method 或 session intent，或让 proof 窗口超过 300 秒。
3. Client 尝试在 human body 中加入 `requested_scope`、客户端 challenge、`proof_kind`、`requested_ttl` 或 `expires_at`。
4. Station 的内部认证组件在 `development_mode=true` 时尝试把 `ak.profile.station.v1` 放入 `verified_profiles[]`。

Expected：

- 第 1 步 MUST 拒绝，reason_code 为 `audience_mismatch` 或等价稳定码。
- 第 2 步 MUST 在 grant ledger 写入前拒绝；origin 必须以 durable current accepted-device key 在同一 current-authorization linearization 中验签，不得信任请求自报 key 或先验签后另行读授权状态。
- 第 3 步 MUST schema reject；human scope 和 TTL 都是 issuer-fixed，不存在客户端请求后再 clamp 的分支。
- 第 4 步 MUST 被 conformance / describe 校验拒绝；development mode 下 `verified_profiles[]` 必须为空。

### 10.5.1 Vector: SessionGrant Issuer Record 与 Exact Replay

`vector_id`: `ak.vector.auth.session_grant_issuer_record.v1`

Runner MUST 加载
[`session-grant-issuance-fixture.json`](../../artifacts/fixtures/session-grant-issuance-fixture.json)，并执行其
全部 positive、normalization、tamper、replay 与 lifecycle cases。

Expected：

- 对 closed `ak.session_grant.issuance.v1` preimage 执行 RFC 8785 JCS 与 SHA-256，前置 registry 中 active
  SHA-256 suite wire code 后生成 33-octet token；typed `ak:session_grant:` ID MUST 与 JWT `jti`
  byte-identical。首字节与 Event / Realm token 用**同一** `suite_tagged_full_digest` 布局
  （[`encoding.md` §4.0](./encoding.md)：高 nibble 保留为零，低 nibble 是登记的 digest-suite wire code）；
  区别只在 `D` 的来源——SessionGrant 的 `D` 来自 Account Authority 的 closed issuance preimage，
  不是 Event digest preimage，因此不得把它当作某个 Event 的派生 ID 去解析。两个 issuer 使用相同 nonce
  与其余 claims 时必须产生不同 ID。
- `issuance_nonce` 必须是 32-octet unpadded Base64URL；`session_public_key` 的非 canonical public-JWK 输入
  必须先规约成同一 JCS string，private member、不能 round-trip 的 signed claim、乱序/重复 scopes、非
  canonical millisecond、显式 `null` optional 均必须拒绝或在签发前唯一规约。
- 任一 signed preimage claim、nonce、`jti` 或 issuer 被篡改时，verifier 重算必须失败。`session_id` 必须
  独立于 grant ID，refresh 必须继承它；不得接受 `session_id=grant_id` 或从 grant ID 派生的实现。
- credential-class binding 必须进入同一 closed preimage：standard 缺 `holder_binding`、device bootstrap 缺
  `bootstrap_binding`、或任一分支混入其它 class binding 时 schema 校验必须失败；改变任一 binding 而保持
  原 `jti` 时重算必须失败。fixture checker 必须展开全部 `inherits` / `override` / `omit` 后再逐向量验证
  canonical bytes、suite byte、digest、typed ID、`jti`、nonce、canonical JWK 与 signed-claim 精确投影。
- 同 issuer/proof-kind/request identity 与 byte-identical canonical intent 的首次签发、commit 后响应丢失、
  restart 与并发 replay 必须返回同一 nonce、ID 与 byte-identical JWT，且 ledger 只有一条 logical grant。
  replay retrieval 每次仍须验证 current holder/DPoP、HTTP method/target、issuer/audience 与 request digest。
- 同 replay key 异 intent 必须 `duplicate_conflict` 且零新 grant、零状态变化。命中 expired record 必须
  `session_grant_replay_expired`；命中 revoked/superseded record 必须 `session_grant_replay_terminal`，并在
  closed details 返回原 `grant_id` 与 exact state；记录超过 retention 后必须
  `session_grant_replay_indeterminate`。三者均不得返回成功或补发 credential。
- refresh 必须在一个 issuer transaction 中创建唯一 active successor 并把 predecessor 标为
  `superseded`、记录 successor ID；rollback 不得留下半条链。revoke、account/device/Agent cascade 与
  introspection 必须读取同一 issuer ledger，不得依赖 PCR grant Event/cell。
- 权限负例必须证明 Auth Server 未取得 principal/root/device/notary private key，SessionGrant 路径未调用
  `/_arkret/self/events`、未查询 PCR authoring frontier；S2S signature 不得替代 DPoP 或 Event proof。

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

- 第 2 步 MUST 返回 `cursor_revoked`，且不推进 subscription position（to-device 队列删除只由 `ak.self.device_messages.command.ack.v1` 驱动，与 cursor 无关）。
- 第 3 步 MUST 返回 `cursor_integrity_invalid`，不得泄露 revocation set 是否命中。

### 10.9 Vector: PCR Genesis 与 Root Re-anchor

`vector_id`: `ak.vector.identity.pcr_genesis.v1`

Steps：

1. 构造 root-signed create + founding-device-signed authorize；第二条 Event 的 proof method 使用 founding principal 已验证 `did` 下的 DID URL，并让其 bare `did` 经 adapter 投影为 `principal_id`（`did_core_id`）、fragment 逐字等于 `device_id`，同时让 descriptor、payload digest、device/HPKE material 与 initial session request 全部一致；不得从 principal core 与 device fragment 拼接 verification method。
2. 分别 mutation root/device signature、lease fence、DPoP JKT、scope、Event order/prev_refs、descriptor fields与 payload digest。
3. 尝试把 authorize Event id/envelope digest加入 root transcript，或把 second proof method改为 `did:key`。
4. 并发提交两个不同 genesis unit；随后对 winner执行 root re-anchor。

Expected：

- 第 1 步两 Event原子 accepted，receipt scope=`pcr_genesis_unit`，首个 Standard grant只在 receipt verified 后签发。
- 第 2/3 步全部 fail closed、零写入。
- 第 4 步只有一个 create-once winner；re-anchor 第二条使用同一 candidate overlay，接受后旧 generation devices fenced。

### 10.9.0.1 Vector: Identity Registration Saga Crash / Fence / Client Binding

`vector_id`: `ak.vector.identity.registration_saga.v1`

Steps：

1. 在 saga 刚 durable 到 `did_published` 后模拟进程崩溃，以相同 request identity 与 canonical bytes 重试。
2. lease 过期后由新 holder 递增 fence；旧 holder 分别尝试续租、消费 challenge 与 register。
3. 分别提交 expired-unconsumed challenge、consumed + different digest、consumed + exact successful replay。
4. 在客户端签名前逐一篡改 challenge 回显的 `account_subject`、principal、operation digest 或三项 DID log pin；成功响应后再篡改 signed binding receipt 或回读 `history[0]`。

Expected：

- 第 1 步从 frozen checkpoint 单调续跑到 completed，不产生第二 DID、PCR 或 grant。
- 第 2 步全部以 `identity_creation_lease_fenced` 零写入失败，reserved identity 与 checkpoint 归新 fence 继承。
- 第 3 步依次为 `identity_creation_challenge_expired`、`identity_creation_challenge_already_consumed`、返回原 recorded outcome。
- 第 4 步在 root 签名前或 identity adoption 前 fail closed；客户端不得用服务端返回值覆盖本地 frozen root。

### 10.9.0.2 Vector: Provisional Identity Explicit Abandonment

`vector_id`: `ak.vector.identity.provisional_identity_abandonment.v1`

Steps：

1. PCR 未 accepted 且 identity root 已丢失。以当前 lease holder 的 handoff grant 调用
   `ak.gate.account.command.issue_identity_abandonment_challenge.v1`，再以**另一份新鲜** handoff grant 调用
   `ak.gate.account.command.abandon_identity_creation.v1` 完成放弃。
2. 不取 challenge，直接调用确认；以及取到 challenge 后复用签发它的那份 handoff grant 再确认。
3. challenge 已签发、尚未确认时让该 PCR 被 accepted，然后提交确认。
4. 成功放弃后重新取 handoff，读取该账号所有 holder 可读面上的 `reserved_identity_creation`。
5. 以同一 `request_id` 与同一 canonical bytes 重放确认；并分别提交 expired-unconsumed challenge
   与 consumed + different canonical digest。

Expected：

- 第 1 步一个事务内消费 challenge、写 orphan anchor tombstone/audit reservation、抑制 checkpoint 并释放 lease；
  `status=abandoned`，任一步失败则零写入。
- 第 2 步全部拒绝：省略 `challenge_id` / `challenge` 是 `schema_violation`，未签发过的 challenge 与复用的
  handoff grant 分别是 `failed_precondition` 与 `proof_invalid`，三者均零写入。
- 第 3 步以 `identity_creation_already_accepted` 稳定终态失败，**未执行放弃**，不写 tombstone、不抑制 checkpoint、
  不释放 lease；判定依据是 challenge 钉死的 `did_version_id` 与 lease fence。
- 第 4 步在**所有** holder 可读面都读不到 `reserved_identity_creation`（含
  `identity_creation_lease.reserved_identity`）；这是安全性质，不是清理策略。
- 第 5 步重放返回同一终态且**只有一条** tombstone；expired 与 consumed 分别返回
  `identity_creation_challenge_expired` 与 `identity_creation_challenge_already_consumed`。

### 10.9.0.3 Vector: Identity Creation Frozen-Reservation Barrier Before DID Publication

`vector_id`: `ak.vector.identity.frozen_reservation_barrier.v1`

Runner MUST 在 Account Authority 与 DID registry / method-native log 之间插入 registry spy，使每次
registry 请求（method-native publication、query 与 exact replay）可计数且可比对 canonical bytes；
断言不能只基于 Account Authority 数据库的"零写入"，必须同时断言 registry spy 观察到的请求序列。

Steps：

1. 分别以无 lease、expired lease、mismatched fence 与 stale holder 提交 register 或任何
   DID publication 请求。
2. 同一账号/audience 的两个 holder 以不同 `principal_id` 与不同 canonical DID operation 并发注册。
3. registry 接受后、`did_published` checkpoint 提交前注入进程崩溃，随后让原 holder lease 过期并发生
   fence takeover，执行内部 saga recovery；其间 stale holder 再以原 request identity 与 bytes 重试
   register。
4. takeover holder 沿用 frozen reservation，分别在规范允许的字段范围内以新 device 重签 fresh
   transcript，以及尝试替换 `principal_id`、`did`、operation digest 或 canonical operation bytes。

Expected：

- 第 1 步全部在任何 registry I/O 前 fail closed、零写入，registry spy 计数为零请求。
- 第 2 步只冻结一份 canonical DID operation，且只有该 exact operation 到达 registry；另一 holder 的
  请求在任何 registry I/O 前失败，最终只有一个 DID。
- 第 3 步恢复只 query/exact replay 原 frozen bytes，registry spy 见不到第二份 operation；最终只有一个
  DID 与一个稳定 `accepted_at`，收敛到同一 `did_published` checkpoint；stale holder 的重试被拒绝且
  零写入。
- 第 4 步 fresh device transcript 在允许字段范围内重签成功；替换 `principal_id` / `did` /
  operation digest / canonical bytes 的请求在任何 registry I/O 前 fail closed，冻结的 DID operation
  保持不变。该步明确区分"DID operation freeze 后不可变"与"genesis 材料允许重签"的边界。

### 10.9.1 Vector: Device Revocation Seal Binding

`vector_id`: `ak.vector.device.revocation_seal_binding.v1`

Steps：

1. `ak.device.revoke` 作为 Control Move 提交，信封携带有效 `seal_basis`（单 leaf，取自 `ak.self.seals.read.frontier.v1` 的 Realm Seal view），随后被 principal control stream 的 accepted Seal S 覆盖（`control_sealed`）。
2. 攻击者重放该设备在 S 之后（以 S 或其后继 Seal view 判定）签发的 session grant、KeyPackage publish 或 to-device write。
3. 某 E2EE Realm 提交 MLS Remove，但其 `governance_binding.security_frontier_digest` 不是从包含该 device revoke/leaf remove 的 accepted state 重算所得。
4. 客户端在 `ak.self.seals.read.frontier.v1` 来源不可用（错误、缺完整 `seal_basis.leaves[]` 或任一 leaf 无法验证）时尝试提交 `ak.device.revoke`。

Expected：

- 第 2 步 MUST fail closed；实现不得用本地布尔缓存替代以 S 或其后继 Seal view 的判定。
- 第 3 步 Commit MUST reject，且 current winning MLS group state 不得推进；后续 E2EE DataEvent 继续被 security frontier gate 阻塞。
- 第 4 步客户端 MUST fail closed，不得伪造 `seal_basis`；缺失或不一致 basis 的 Control Move 按 `ak.vector.cba_lattice.control_move_requires_seal_basis_and_seal.v1` 拒收。

### 10.9.2 Vector: Device Revocation Pending State

`vector_id`: `ak.vector.device.revocation_pending_state.v1`

Runner MUST 执行 `device-revocation-pending-fixture.json` 的全部 semantic cases，并至少覆盖：

1. revoke 在 schema / proof / authority / exact current device+PCR generation / precondition / admission 与 mandatory canonical Ack 全部通过后，以单一事务持久化 accepted Event、Ack、derived record、pending index；无 Ack 零写入，不能套用 self-principal PCR Ack-less 例外。
2. pending 时 base、E2EE 与 hardening profile 对 session issue/refresh、KeyPackage claim、to-device write、Event write、Station admission-proof issuance 全部 fail closed 且零业务写；可区分本地主体操作使用 `device_revocation_pending`，KeyPackage anti-enumeration surface 保持 `claim_failed`，不得因 profile 改变 gate 结论。
3. Account Authority 只可凭 `ak.peer.device_revocations.command.check.v1` 的 fresh signed exact-intent receipt 铸造/刷新 grant；origin 在同一事务从自身 durable projection 派生 selector、同一 durable order 线性化、receipt 最长30秒且不能由 cache/private RPC 替代。introspection 不承载可复用 receipt；origin Station 对每个 protected self request 在本地事务读取 durable gate。
   - returning human 使用 `returning_session_grant_issue`，不携 expected binding但强制 accepted-device proof；registration/recovery 使用 `session_grant_issue` 且禁带该 proof；两类 `allow` receipt 的 derived selectors 逐字成为 grant `device_binding`，客户端自报 Event/generation 无法进入。
   - expected binding 两字段必须同时出现或同时缺省，且只有两个 issue action 可缺省；refresh 必须携 predecessor binding。与 derived 值不等时 decision 为 `generation_mismatch`，receipt 不回携新 binding。
   - 无权 caller、非本服务账号、未知设备与他人设备统一返回同形 `authority_mismatch`，且 caller 授权校验先于任何 device-private 读取。
   - `authority_mismatch -> device_unauthorized`，`revocation_pending` / `revoked` / `generation_mismatch` 分别 typed block；全部零签发。任一 human success 都含完整 `device_binding`。
4. restart、exact replay、同device/generation两个不同 proposal、只 reject 其中一个、错误 proposal/Ack/authority/device-generation decision、exact signed reject 清最后一项、overdue alert但不解封；达到128条 distinct gate record 后新 proposal `limit_exceeded` 零写入，exact replay仍成功。
5. reject-first / Seal-first terminal CAS 两种竞态，以及未被 reject终结的 late valid Seal；任何执行次序只能产生一个 terminal winner。
6. pending 只保留恢复所需最小客户端材料，Seal后才擦除 generation-specific material；pending前合法 admission proof 在pending/Seal后仍可离线验证。

Expected：gate 真相完全来自 durable proposal/Ack/decision/Seal store；任一实现若以 timeout、管理员布尔值、cache eviction、进程内状态或 profile 分支解封，均不合格。账户 device summary 必须把 lifecycle `status` 与 `verification_state` 分维，并返回全部 gate-relevant records（canonical `(acceptance_seq, proposal_digest)` 顺序）；一条 sealed 与另一条 pending 并存时 status=`revoked`，数组仍同时表达两者，不得只返回任意一条。

### 10.9.2.1 Vector: SessionGrant Returning Issue And Refresh Closed Proofs

`vector_id`: `ak.vector.session_grant.accepted_device_possession.v1`

1. bound AccountHandoff + 唯一旧 signer 构造 `HumanSessionGrantRequest`，proof 逐字段绑定 handoff digest、request id、principal/device/audience/holder JKT/intent 与窗口；origin 同一 device lock 验签并返回 allow。
2. 分别替换上述任一字段、使用另一登录的 handoff、账号攻击者只提交泄露 device id、或在锁外读取旧 key 后让 generation 改变。
3. human refresh 使用 predecessor DPoP + `purpose=session_grant_refresh` proof；分别测试 client `challenge`、OIDC/passkey/paired/Agent proof kind、issue-purpose proof、wrong predecessor id。
4. Agent refresh 使用 `AgentSessionRefreshProof`；分别加入 human proof、遗漏 current runtime authorization、或要求 browser session。

Expected：第 1 步只在 proof-valid + current `allow` 时签含完整 `device_binding` 的固定-scope Standard grant；第 2 步全部零 grant。第 3 步合法请求原子产生唯一 successor，所有旧枚举/挑战与 transplant 在 schema 或 proof gate 拒绝。第 4 步只按 Agent runtime lifecycle 决定，不接受 human proof。human issue/refresh 重放返回 byte-identical outcome；blocked decision 不得降级 pairing/recovery/fresh grant。

### 10.10 Vector: Push Wakeup Policy

`vector_id`: `ak.vector.push.wakeup_policy.v1`

Steps：

1. E2EE Realm 声明 `wakeup_default=no_notification`，server 无法评估 client-side mention rule。
2. Realm 使用 `batch_wakeup`，一分钟内大量 client-side unresolved events 到达。

Expected：

- 第 1 步 MUST NOT 发送单事件 blind wakeup。
- 第 2 步 MUST 合并为 batch wakeup，仍携带 `evaluation_locus_unresolved=true`。

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

前置：调用方对同一 `push_target_id` 提交一次 `ak.edge.push.command.notify.v1`，`notification.devices[]` 含两个不同 `device_id`（`D1`、`D2`）。

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

### 10.12.2 Vector: Device Push Route Revision CAS

`vector_id`: `ak.vector.push.device_route_revision_cas.v1`

Steps：

1. 对从未写入的 canonical push-route cell 提交 active payload，`expected_revision=0`。
2. 读取 current revision 1，以新 `push_target_id` 和完整 active tuple 提交 rotation，`expected_revision=1`。
3. 读取 current revision 2，提交只含 subject、`expected_revision=2`、`revoked=true` 的 tombstone。
4. 分别提交缺失 `expected_revision`、旧 `expected_revision`、同 revision sibling 与第 1 步 exact bytes replay。
5. 对 revoked cell 执行隐私 GC，删除旧 target、gateway/encryption/provider 材料与可逆映射后，再提交 `expected_revision=0` 的离线旧 active 写入。

Expected：

- 第 1–3 步依次接受，accepted revision 为 1、2、3；rotation 是 whole-value successor，revoke schema 不接受任何 active secret 字段。
- 第 4 步全部 fail closed：缺字段是 `schema_violation`，其余是 `cas_conflict`，且 revision 与 durable value 均不改变。
- 第 5 步仍返回 `cas_conflict`、revision 保持 3；实现只保留不可恢复旧 target 的 subject digest / revision / outcome 最小状态。
- 任一实现不得使用 CBA `preconditions`、arrival-order LWW、`cas_register` Bottom 或 `push_gateway_did` 私有别名替代本向量。

## 11. Agent & Sidecar Vectors

### 11.1 Vector: Provisioning + Pairing + Global Scope Ceiling

`vector_id`: `ak.vector.agent.provision.v1`

Steps:

1. Controller client 先生成 Agent WebVH root、binding update key 与下一代 key，在网络提交前可恢复地持久化更新密钥；签名并发布只含 Station + managed-controller delegation、**不含 PCR binding** 的 entry 0。entry 0 accepted 后，Controller 以其 `did` 调用 `ak.self.agent.command.provision.v1`，以必填 `requested_scope` 声明 Agent 的 immutable 全局权限硬上限。prepare 返回 exact `initial_resolution`、allocation 与 digest 且没有 Agent durable side effect，也不分配 Agent PCR id；Controller 逐字核对 inception pin，按 `sha256(canonical_json({agent_id, controller_principal_id, kind:"ak.agent.requested_scope_commitment.v1", requested_scope}))` 重算 digest，本地冻结含该 `initial_resolution` 的 Agent PCR `ak.realm.create`、自算 `event_id` 并取 `principal_control_realm_id = retype(event_id, "realm")`，再 author 一个无内层 proof、前向声明该值的 `ak.agent.provision` Event。commit 只接受该单一 Event，并在一个 reducer transaction 原子投影 provision/accountability/selector/realm-id-claim，返回 `status=awaiting_pcr_genesis`。Controller 随后在**另一次提交**中送出该 genesis create；accepted 后 outcome 只能是 `awaiting_did_binding`。Controller 再用 entry 0 预承诺的 update key 签发连续 entry 1，新增 exact `ArkretPrincipalControlRealm.serviceEndpoint` 四元组；entry 1 accepted 后才返回 `pairing_request_id` 并推进到 `complete`。公开 history 只固定 digest，不含完整 scope。provisioning 不创建 Agent Profile、key authorization 或 Realm grant。省略 `requested_scope`、inception 预含 PCR id、错 inception pin 的变体必须失败；把 provision 与 genesis 放进同一批提交的变体必须以 `event_id_digest_mismatch` 失败。
2. Agent runtime 生成 key pair，取得 pairing verifier 签名的 presentation request/challenge；controller 生成符合 `ak.schema.agent_requested_scope_disclosure.v1`、绑定该 verifier/audience/challenge 且接收窗口不超过 300 秒的私有披露，与 key pair request 一起提交。controller-signed `ak.agent.key.authorize.payload.agent_key_scope` 使用 actions/resources/constraints 的严格子集。另提交一个超出 action/resource ceiling 或删除 provision mandatory constraint 的变体。
3. Pairing endpoint 校验 `verification_method` 的 DID 部分(strip fragment/query 后)与 `agent_id` bit-identical。
4. 批准后写入 `ak.agent.key.authorize`；随后为该 Agent 提交一个 controller-authored `ak.capability.grant` `EventInitialSubmission` 以附加更窄的 Realm-scoped grant。其 `event.payload.grant` 不含内层 proof，Event envelope proof 是唯一 durable issuer signature；另分别尝试提交 body-local proof、让服务端代签/合成 Event、含未 provision action及超出显式内容 resource ceiling 的变体。

Expected:

- 第 3 步 verification_method 与 agent_id 不一致时 MUST `failed_precondition` `reason=verification_method_principal_mismatch`。
- 第 1 步 entry 0 必须无 PCR service，`initial_resolution` 必须与其 accepted head/version 逐字一致，且 controller 必须用 entry 0 预承诺 key 签发 entry 1；DID commitment 必须与 fixture 固定 digest 匹配。`ak.agent.provision` Event proof 是唯一签名，payload 出现内层 proof、拆成 accountability/selector Event pair 或 reducer 暴露部分 projection 都 MUST reject。entry 1 的公开 service endpoint 必须是 `{realm_id, controller_did, authorization_ref, requested_scope_digest}` 闭合四元组，出现 `requested_scope` 或其它 scope/resource/constraint 明文字段 MUST reject。
- 第 1 步的 `principal_control_realm_id` 必须逐字等于 controller 本地算出的 `retype(genesis event_id)`，且按 `entry0 -> initial_resolution -> genesis -> realm_id -> entry1` 顺序真的可推导，不产生 `event_id_digest_mismatch`；服务端自选该值、无 accepted provision 声明本 create、两条 provision 声明同一 realm id 三种形态 MUST 分别 fail closed 且零写入。entry 1 尚未接受时 pairing handle 与 `ak.self.agent.read.list.v1` / `ak.self.agent.resource.get.v1` MUST 都不暴露该 Agent。
- 第 2 步 disclosure 的 controller proof、request/challenge 单次性、verifier/audience、接收窗口与 digest 必须全部通过；缺失、摘要不匹配、重放或错 audience MUST fail closed，且不得退回服务本地 Agent row 作为权威来源。完整 disclosure 不得进入 authorize Event、Realm history、pairing code 或通知。
- 在第 4 步之前，任何 `agent_key_proof` session grant 请求 MUST fail closed。
- 第 2 步更窄 key scope MUST 接受；任何 action/resource 越界或删除 mandatory constraint 的 key scope MUST fail closed。实现不得要求 key scope 与 provision scope 完全相等。
- 第 4 步后 agent runtime 只能在 `requested_scope ∩ agent_key_scope` 上限内签发 session grant；内容 capability 还必须来自后续独立的 Realm-scoped grant。更窄 grant Event MUST 接受；ordinary CapabilityGrantBody 的内层 proof/signature、服务端代签/合成 Event 或 proof fallback MUST reject。未 provision action 或超出显式内容 resource ceiling 的 grant MUST 以 `agent_grant_exceeds_requested_scope` fail closed。

### 11.1.0 Vector: Requested Scope Public-History Privacy

`vector_id`: `ak.vector.agent.requested_scope_privacy.v1`

Steps:

1. 解析 Agent accepted inception DID Document，验证唯一 `ArkretPrincipalControlRealm.serviceEndpoint` 的闭合四元组；扫描DID version history 与公开 registry/notification/Event fixture。
2. Verifier 生成签名 `ak.identity.presentation_request`，包含唯一 `request_id`、不可预测 `challenge`、`verifier_id`、`audience/domain` 与五分钟内 expiry；controller 经 TSP、HTTP/JWE、DIDComm-like、to-device 或 MLS DM 私有通道返回 `ak.schema.agent_requested_scope_disclosure.v1`。
3. Verifier 验证 controller current proof、`payload_digest`、`agent_id/controller_principal_id`、`verifier_id/audience`、`expires_at-issued_at <= 300s`，消费 `(verifier_id, request_id, challenge)`，并以披露 scope 重算 DID commitment。
4. 负向变体依次为：公开 endpoint 加入完整 `requested_scope`；disclosure 改一个 resource/constraint 但保留旧 digest；错 verifier 或 audience；过期/超 300 秒窗口；重放已消费 challenge；把 disclosure 复制进 grant、authorize Event、notification 或 Realm plaintext。

Expected:

- 正向 disclosure 只作为加密 verifier-private evidence 接受；其缓存键至少为 `(agent_id, requested_scope_digest, verifier_id, audience)`，accepted-at DID/controller lifecycle 变化时重新验证或 fail closed。
- 六类负向变体全部 fail closed。公开 DID history 与其它公共 fixture 中不得出现完整 scope；实现不得因 disclosure 本身“不授予能力”而放宽隐私检查。

### 11.1.1 Vector: Controller-scoped Agent Mention Selector

`vector_id`: `ak.vector.agent.mention_selector.v1`

Preconditions:

- Alice 拥有 verified handle claim `alice:acme.example`，`subject=AliceDID`。
- Alice 拥有 active Agent `AgentS`，其 Actor Profile `actor_kind="agent"`、`agent_slug="summary"`、`principal_id=AgentSDID`，且有 active `ak.identity.accountability_grant{issuer=AliceDID, subject=AgentSDID}`。
- AgentS 的账号是 `{principal_id:AgentSDID, station_id:AgentSStation}`，由一条 accepted `ak.agent.provision`
  建立：该 provision 的 signed `payload.agent_id` 是 `AgentSDID`，其 controller account / Station 与随后
  accepted 的 Agent PCR `genesis.actor_id.account_id` 精确一致，`AgentSStation` **由此派生**，
  不是 fixture 常量、也不是任何解析方当次的 Station。
- Alice 或授权 issuer 签发 current
  `ak.schema.agent_selector_claim.v1{controller_subject_id=AliceDID, agent_slug="summary",
  subject_account_id={principal_id:AgentSDID, station_id:AgentSStation}, binding_state="verified",
  visibility="restricted", audience=<RealmR>}`。**selector namespace 仍是 principal 级
  `(controller_subject_id, agent_slug)`；被签名的目标是上面那个完整 AccountId。**
- 同一 Realm 中 Bob 可见 Alice 的 handle claim、AgentS 的 Actor Profile、selector claim 与 accountability evidence。

Steps:

1. Bob 在 message composer 输入 `@alice:acme.example/summary`。
2. 客户端从本地 Realm roster / actor profile / handle claim cache 解析 controller handle → controller 完整 AccountId，只取其 principal 分量 `AliceDID` 用于 namespace 比较；再验证 selector claim `(AliceDID, "summary")` → 唯一 active `subject_account_id={principal_id:AgentSDID, station_id:AgentSStation}`。**`AgentSStation` 来自这条已签名 claim，不是从 roster 反查、也不是补出来的。**
3. 客户端提交 Message content AST，其中 mention node 的 `subject_account_id` **逐字节复制**第 2 步已验证 claim 的同名字段，并可携带 `controller_subject_account_id={principal_id:AliceDID, station_id:AliceStation}`、`controller_handle_at_time="alice:acme.example"`、`agent_slug_at_time="summary"`、`mention_text_original="@alice:acme.example/summary"`。
4. Alice 之后把 `AgentS.slug` 改为 `sum` 并更新对应 selector claim 的 `agent_slug`，或把 `summary` 分配给另一个新 agent `AgentT`。
5. 另一次测试中，Alice 同时存在两个 current valid selector claims 绑定 `(AliceDID, "summary")` 到不同 active agents，或 Bob 不可见 selector claim / accountability evidence。
6. 另一次测试中，同一 `AgentSDID` principal 在另一个 Station 上另有一个账号 `{principal_id:AgentSDID, station_id:OtherStation}`，且该账号也是本 Realm 成员。
7. 另一次测试中：(a) 把 claim 的 `subject_account_id.station_id` 换成 `OtherStation` 而复用原 proof；
   (b) Directory outcome 的 `subject_account_id` 与 `selector_claim.subject_account_id` 不相等；
   (c) 存在两条 current valid claim，分别指向同 principal 的两个 Station 账号；
   (d) 请求携带 `expected_actor_id` 为 service Actor，或用它去挑 (c) 的赢家；
   (e) 解析方只有本地已授权 cache、没有 Directory；(f) 目标 agent 已获授权但**不在**当前 Realm roster；
   (g) provision 尚未完成（Agent PCR genesis 未 accepted）就被当作可解析 Agent；
   (h) 服务端为填满 DTO 自行补签 `selector_claim.proofs` 或公开 private provision 材料。

Expected:

- 第 2 步 MUST 在持久化前完成；selector claim 是 slug 绑定的权威来源。持久化事件里的权威 mention target MUST 是 agent 的完整 `subject_account_id`，不得把 `alice:acme.example/summary` 当作 handle 或权威字段写入，也不得只写 principal 分量。
- 第 3 步的 `controller_*` 与 `agent_slug_at_time` 只作 audit / search / fallback metadata；reducer、dispatcher、policy engine MUST 忽略这些字段做授权和投递决策。
- 第 4 步 MUST NOT 改写历史 mention target；旧消息仍指向同一个完整 `subject_account_id`。
- 第 5 步 MUST fail closed：客户端不得构造 mention node；实现可提示 picker 选择或把输入保留为普通文本。服务端若收到仅靠 metadata 声称 selector 的事件，也必须只按 `subject_account_id` 和已验证 agent state 判定。
- **第 7 步（负例与正例，normative）**：(a) 换 Station 复用原 proof MUST 验签失败——
  `subject_account_id` 是 `ak.agent_selector_claim_proof.v1` 的 binding field，改它必然让原 proof 失效；
  (b) outcome 与 claim 不等 MUST 判不合规，Directory 是投影方不是选择方；
  (c) 同 principal 双 Station 的两条 current claim 是 **ambiguous**，MUST fail closed，
  不得按 principal 去重后当成唯一；(d) `expected_actor_id` 是一致性断言，service Actor 永不匹配，
  也 MUST NOT 用来从 ambiguous 里挑赢家；(e) 与 (f) 是**正例**：只有本地已授权 cache 也必须解析成功，
  目标不在当前 Realm roster 也不阻断解析——本裁决不新增 membership 前置，也不授予非成员读取 / 通知 / 参与权限，
  可见性与 Agent/profile/accountability/provisioning 条件仍需全部满足；
  (g) 未完成 provision MUST NOT 提前作为 active 可解析 Agent；
  (h) 服务端补签或泄露 private provision 材料 MUST 判不合规——拿不到真实 controller / 授权 issuer 签名的 claim
  就不能广告或返回该成功面。拒绝时一律不得泄露 Station。
- **第 6 步（负例，normative）**：另一 Station 上同 principal 的账号 MUST NOT 命中该 mention——不产生 `notification_kind=mention`、不进入授权判定、不参与 §3.8.2 的 MemberIdentity 联接。实现若按 `subject_account_id.principal_id` 单独比较即为不合规；比较 MUST 覆盖 `principal_id` 与 `station_id` 两个分量（[`../identity/identity-handles.md` §3.8](../identity/identity-handles.md)、[`../discovery/discovery-directory.md` §9](../discovery/discovery-directory.md)）。

### 11.1.2 Vector: Agent PCR Genesis 前向声明与反查

`vector_id`: `ak.vector.agent.pcr_genesis_declaration.v1`

Steps:

1. Controller 在安全存储中持久化 WebVH binding update key，发布不含 PCR service 的 Agent inception entry 0；服务端 accepted 后 prepare 返回逐字匹配的 `initial_resolution`。
2. Controller 本地组装含该承诺的 Agent PCR `ak.realm.create` 完整 canonical bytes，自算 `event_id`，取 `realm_id = retype(event_id, "realm")`；commit 提交声明该值的 `ak.agent.provision`，返回 `status=awaiting_pcr_genesis`。
3. 归档：客户端崩溃重启，从 durable intent 恢复同一 create bytes 与 DID keys；重放 commit 返回同一 `awaiting_pcr_genesis` 而不是第二条 provision。
4. 在**另一次提交**中送出该 create；admission 反查 accepted provision 并接受，provision outcome 变成 `awaiting_did_binding`，Agent 仍不可见。
5. Controller 用 entry 0 预承诺 key 签发连续 entry 1，新增 exact PCR service 四元组；entry 1 accepted 后重放 commit 才返回 `complete`。
6. 变体 A：entry 0 已含 PCR service；变体 B：prepare 返回的 inception pin 与 entry 0 不符；变体 C：provision 与 create 同批提交；变体 D：create realm id 无 accepted provision 声明；变体 E：第二条 provision 声明同一 realm id；变体 F：服务端自选 realm id；变体 G：controller PCR 与 Agent PCR 分属不同 Station；变体 H：entry 1 未使用预承诺 key或四元组不符；变体 I：create 携带一个结构合法、可投影到同一 Agent、但不等于 provisioning durable 保存值的 `initial_resolution`。

Expected:

- 第 4 步 accepted create 的 `retype(event_id)` 与第 2 步声明值**逐字相等**；第 5 步 service 四元组与 create/provision 逐字相等。实现 MUST NOT 用相似度、前缀或本地映射代替。
- 第 1 至 5 步依赖图严格为 `entry0 -> initial_resolution -> create -> realm_id -> entry1`，全程不产生 `event_id_digest_mismatch`；这就是可构造性证明。
- 第 4 步只进入 `awaiting_did_binding`；第 5 步 accepted 后才把 `ak.component.agent.status.v1` 从 `uninitialized` 迁到 `active`、发布 pairing handle 并变为 `complete`。此前 list/get MUST 不返回该 Agent。
- 变体 A、B、H MUST 在相应 DID/prepare admission fail closed；变体 I MUST 在普通 Event policy 与 delegated envelope 两条 create admission 路径都零写入拒绝，不能因其自身格式正确而接受；变体 C MUST 以 `event_id_digest_mismatch` 拒绝；变体 D MUST 以 `agent_pcr_genesis_declaration_missing` 零写入拒绝；变体 E MUST 以 `agent_pcr_genesis_declaration_conflict` 零写入拒绝且不改动既有 claim；变体 F、G MUST fail closed。
- `purpose != "agent_control"` 的 `ak.realm.create` MUST NOT 触发 agent-status 写入，也不做该反查。

### 11.2 Vector: Pairing Expiry Auto-Revoke

`vector_id`: `ak.vector.agent.pairing_expiry.v1`

Steps:

1. Controller 调用 `ak.self.agent.command.provision.v1`,pairing 窗口 12 小时，grant TTL 30 天。
2. Pairing 12 小时窗口过期，未提交 `ak.gate.account.command.pair_agent_key.v1`。

Expected:

- generic list/get 必须关闭并省略 open-handle fields，返回 lifecycle 不变且 `readiness={state:not_ready,blockers:[...,runtime_key_missing]}`；`key_state` 不得出现 `status` / `runtime_state`。只有用该 handle 轮询 pairing poll 时才返回 operation-local `runtime_state=pairing_expired`。不得创建、撤销或改写任何 Realm grant。
- 重放 `ak.gate.account.command.pair_agent_key.v1`(使用过期 pairing_request_id)MUST fail closed。
- Controller 可通过 `ak.self.agent.command.renew_pairing.v1` 对同一 agent principal 原地重开 bootstrap pairing，也可重新发起 `ak.self.agent.command.provision.v1`;后者得到新 agent_id,旧 agent_id 与新 provisioning 不复用。两种操作都不得从 `requested_scope` 物化 Realm grant。

### 11.2.1 Vector: Stable Runtime Key Binding 与审批 CAS

`vector_id`: `ak.vector.agent.runtime_key_binding.v1`

Steps:

1. Runtime `R1` 对 open pairing handle 提交 key `K1`；服务端按 [`key-management.md` §3.6.2](../identity/key-management.md) 计算 stable binding digest，生成 approval/notification id 并发送 notification `upsert`。
2. `R1` 以相同 Agent、handle、verification method、public key 和 attestation 重试；权威 pairing code、challenge、audience 不变，只刷新 PoP `created_at` / `expires_at` / `transcript_digest` / `signature`，服务端重算 stable digest 与 current pairing-request digest。
3. Runtime `R2` 在同一 handle 提交不同 public key `K2`。
4. Controller device `C0` 读取 proof `P1` 并签审批；提交前同一 stable binding 刷新为 `P2`，`C0` 再提交绑定 `P1` digest 的旧审批。
5. Controller device `C1` 重新读取当前 `P2`，核对 pairing secret 后签署当前 `ak.agent.key_pairing_request_binding.v1` 并提交 final pair；另施加 wrong challenge/audience/secret、超过 5 分钟、public-key/method 不等、坏 transcript digest/signature 与旧开放 proof 的单点变异。

Expected:

- 第 1 步得到 fixture 固定的 `public_key_digest`、`attestation_digest` 与 `expected_binding_digest`；helper 输出必须逐字匹配。
- 第 2 步 stable digest、approval id、notification id 不变，projection action 仍为 `upsert`；freshness 字段不进入 stable digest，但 `proof_of_possession_digest` 与 pairing-request digest 必须改变。
- 第 3 步 MUST HTTP 409 `agent_runtime_request_conflict`，不得覆盖 K1、approval id 或 notification id。
- 第 4 步 MUST fail closed；旧 proof/prompt 不得消费 handle 或激活 key。
- 第 5 步服务端必须从当前持久化 request 与 pairing record 重算 stable binding、PoP transcript/digest/signature 和 `ak.agent.key_pairing_request_binding.v1`；只有 controller 签名绑定当前值时审批成功，并在 durable authorize accepted 后发 `remove(reason=approved)`。全部单点变异都必须在状态改变前 fail closed。
- 所有 notification delta 与 provider-visible blind push 中均不得出现 pairing code、public key、PoP、attestation、display name 或 slug。

### 11.2.2 Vector: Agent PCR 分离

`vector_id`: `ak.vector.agent.pcr_separation.v1`

Steps:

1. Controller DID `C`（已有 `PCR_C`）为 Agent DID `A` 走 provision prepare：分配 `A` 与 allocation，只固定 immutable `requested_scope` 的域分离 digest，完整 scope 由 controller-private disclosure 出示。controller 随后**本地冻结** `purpose="agent_control"`、携带 `genesis_salt`、不携带 `founding_device_descriptor` 的 `PCR_A` genesis create 的完整 canonical bytes，自算 `event_id`，取 `PCR_A = retype(event_id, "realm")`；此时 create 尚未提交。
2. Provisioning 的单一 `ak.agent.provision` Event 写入 `PCR_C`，其 `principal_control_realm_id` 前向声明上一步算出的 `PCR_A`（[`./encoding.md` §6.0.1](./encoding.md) 具名 C 类例外），并原子投影 provisioning、accountability、selector 与 realm-id claim facts；无论 `requested_scope` 是否列出内容 action 或显式内容 resource selector，都不得产生 pending / active capability grant。内容授权只能由后续独立、写入对应受治理 Realm 的 `ak.capability.grant` Event 产生；CapabilityGrantBody 无内层签名，唯一 durable issuer signature 是 Event envelope proof。operation/service scope 同样不生成隐式 `ak.event.read` 或其它内容 grant。此时 outcome 停在 `status=awaiting_pcr_genesis`，DID service entry、pairing handle 与 list/get 可见性一律尚未发布。
3. Controller 在**另一次提交**中送出该 genesis create（MUST NOT 与第 2 步同批）：对 basis-free candidate create 重算 founding
   `NotaryValue` / `authority_set_ref`，由 `C` 的当前 device 为 exact Event digest 签 proposal
   receipt，再以 `EventSubmitContext=AnchorUnit` 提交。admission 先反查 `PCR_C` 中是否存在 accepted 的
   `ak.agent.provision` 声明了 `retype(本 create 的 event_id)`；命中后 receiver 在一个事务写 canonical create、
   receipt 与 pending Control index，并条件写 `ak.component.agent.status.v1` 的 `uninitialized -> active`；
   controller 随后提交无 predecessor 且覆盖该 digest 的首 Seal，
   receiver 在一个事务写 Seal/cell effects并标记 pending digest sealed。genesis accepted 后才发布 Agent DID
   service entry、pairing handle 并把 outcome 推进到 `status=complete`；之后再写 Agent profile/key/lifecycle facts。
4. 变体 A：实现把 `PCR_C` deterministic id 当作 Agent PCR；变体 B：在 `PCR_A` 或 `PCR_C` id 上创建缺 PCR marker、restricted history、MLS profile 或任一 E2EE floor 的 Realm；变体 C：服务端以 Agent DID 伪造 proof，省略 `executed_by=C` / `authorization_ref`，或引用的 delegation purpose/resource scope 不覆盖目标 Event kind/PCR；变体 D：把 `requested_scope` 当作 Realm grant、在 provisioning 时物化内容权限，或接受超出 `requested_scope.actions[]` 的后续 Realm grant；变体 E：anchor validator 禁止 receipt、按 `seal_basis` 缺失跳过 pending index，或让首 Seal 在 PostgreSQL / durable store 以 `control Event ... not in store` 失败；变体 F：把第 2、3 步放进同一原子 unit / 同一 ordered submit batch 提交；变体 G：提交一条没有任何 accepted provision 声明其派生 realm id 的 genesis create；变体 H：提交第二条声明同一 `principal_control_realm_id` 的 provision。Participation selection 可独立保存，但不得补回任何缺失 authority。

Expected:

- `PCR_A != PCR_C`，且 receiver 必须从 Agent DID accepted-at history 验证 service entry 的 PCR/controller/authorization/digest 四元组，再验证 controller-signed private disclosure 后使用 scope；不得验证实现私有派生算法或信任服务本地 scope row。
- `PCR_A.created_by == PCR_A.notary == A`，`purpose="agent_control"`，profile/history/encryption floor 全部满足 PCR invariant；`founding_device_descriptor` 出现必须 fail closed，缺少 `genesis_salt` 同样必须 fail closed。
- Controller 写 Agent PCR 时 `actor_id=A`、`executed_by=C`，proof method 属于 C，delegation 覆盖目标 kind；不得伪造 A 签名。
- basis-free create 仍必须返回并持久化 controller-device Control Proposal Ack；首 Seal 提交前 pending
  index 必须存在同一 digest，提交后该 digest、Seal lineage 与 registered effects 必须在同一事务
  转为 sealed/accepted。memory 与 PostgreSQL adapter 必须产生相同结果。
- Agent profile、key authorize/revoke、lifecycle 只进入 `PCR_A`；单一 provision Event及其 accountability/selector/realm-id-claim projections 只进入 `PCR_C`；Realm-specific capability grant 只进入其所治理 Realm；pairing request/notification 不进入任一 PCR。
- `PCR_A` 逐字等于 controller 在第 1 步本地算出的值；genesis accepted 时 `ak.component.agent.status.v1` 从 `uninitialized` 迁到 `active`，且这是唯一能离开 `uninitialized` 的写入。`purpose != "agent_control"` 的 create MUST NOT 触发该写入。
- `PCR_A` 与 `PCR_C` MUST 由同一 Station 承载；反查与 realm-id claim 唯一性都是本地判定。
- 八个变体全部 fail closed，且不得留下非 PCR Realm 占用任一 principal control id，也不得扩大 Agent 的内容权限。变体 F MUST 以 `event_id_digest_mismatch` 被拒（§6.0.1 B 类禁令），变体 G MUST 零写入拒绝，变体 H 的第二条 provision MUST 被 `cas_register` / `bottom=reject` claim cell 拒绝。

### 11.2.3 Vector: Agent PCR History-only Backup

`vector_id`: `ak.vector.agent.pcr_history_backup.v1`

Preconditions:

- Controller `C` 有 current accepted recovery policy `RP_C` 与 recovery public key；Agent `A` 的 DID service binding 指向 `PCR_A`，delegation purpose 覆盖 `principal_control_realm_bootstrap`、agent-control authoring 与 `principal_control_realm_recovery`。
- `ak.self.agent.command.provision.v1` 已完成；`PCR_A` 使用 exporter content scheme，并已有可备份的连续 history-secret range；尚无 runtime key authorization。

Steps:

1. Controller E2EE client 本地生成 `PCR_A` MLS active state，提交 Agent PCR genesis / profile Event；服务端只接收 ciphertext/承诺，不接触 MLS private state。
2. `C` 的授权设备向 `C` 自己的 `backup_kind=mls_history` active series 写入只含 `history_secret_ranges` 的 item；public tuple 与 plaintext tuple 逐字绑定 scope、group、epoch range、group-state ref、secret id/version 及 policy evidence。
3. 在没有任何 backup、已有 history-only backup 两种情况下分别执行首次 `pair_agent_key`；两者都只按 current controller/Agent authority、pairing handle、scope disclosure、PoP 与 accepted Seal frontier 判定。
4. 丢失 Agent runtime private key；新 runtime 生成 `K2` 并走 replacement re-pairing。它不得从 history-only backup 恢复旧 runtime key、leaf signer、sender counter 或 active MLS state。
5. 新 endpoint 需要参加 `PCR_A` 时发布 KeyPackage，由当前成员通过唯一 derived group 中的 Add/Welcome 加入；若该 group 已完全失去 active private state，history-only backup 不得伪造重建 Genesis。
6. 变体：服务端生成 MLS state；把 runtime private key、leaf signer、ratchet、proposal、sender counter、pending Welcome 或任意 active group snapshot 放入 backup；用 backup availability 允许或拒绝 pairing；为 `A` 生成独立人类助记词。

Expected:

- 步骤 1–2 中 active MLS private state 只在 controller E2EE endpoint；backup owner/caller 始终是 `C`，不放宽跨 actor 拒绝。合法 envelope 通过 `ak.schema.key_backup.v1` / plaintext schema、exact tuple matching 与 accepted-at delegation 校验。
- 步骤 3 的两个 pairing outcome 除幂等坐标外逐字同构；backup availability 不得进入 request、response、readiness blocker、error code 或 admission branch。
- 步骤 4 不恢复或克隆旧 runtime private key；K2 由新 runtime 本地生成，旧 authorization 由单一 authorize Event 的精确 `supersedes[]` 原子替换。
- 步骤 5 只允许标准 Add/Welcome；history secret 只解密其覆盖的历史正文，不恢复当前成员身份或发送能力。
- 步骤 6 全部 fail closed。Agent 不拥有独立面向用户 Recovery Key；controller 的 Recovery Key 解锁 controller-owned history envelope，不直接确定性派生 Agent/runtime/MLS active private key。

### 11.2.4 Vector: Runtime Replacement Re-pairing Supersede

`vector_id`: `ak.vector.agent.repairing_supersede.v1`

Preconditions:

- Agent `A` status `active`,持有 authorized key `K1`(`ak.agent.key.authorize`),`K1` 签发的 session grant `S1` 未过期。

Steps:

1. 对已持有 active authorized key 且 lifecycle 为 `active` 的 agent，Controller 直接调用 `ak.self.agent.command.renew_pairing.v1`，得到新一次性 `pairing_request_id` + `pairing_code` 与 `pairing_mode="replacement"`；`paused` 变体同样 MUST 成功。响应不得包含 backup readiness。怀疑旧 key 失陷时 Controller SHOULD 先提交 controller-signed delegated `ak.self.agent.pause`，但 pause 不是 operation 前置条件。
2. Agent 保持 `paused`；旧 key `K1` 与既有 grants 尚未被 replacement 撤销，但服务端不得签发新的 agent session grant 或执行新的 capability action。Controller 在 replacement 完成前调用 resume 的变体 MUST `failed_precondition`。
3. 新 runtime 生成 key `K2` 提交 runtime-key-request；controller 签 `ak.agent.key.authorize`(K2)，其 payload 带 `supersedes=[{key_id: K1, authorized_event_ref: <K1 authorize Event>}]`，再调用 `ak.gate.account.command.pair_agent_key.v1` 完成配对。
4. 用 `K1` 再次请求 `agent_key_proof` session grant;`S1` 在 freshness window 后被使用。
5. 变体 A:第 1 步的 handle 过期，未走到第 3 步。
6. 变体 B:agent 已 `deactivated`,controller 调用 renew_pairing。

Expected:

- renew_pairing MUST NOT 改变 agent status、既有 key、grant 或任何 backup；响应分支是 `pairing_mode="replacement"`，此前所有 pairing handle 永久不可解析。`active` 与 `paused` 直调都必须创建新 handle；只有 `deactivated` 必须拒绝。
- 第 2 步的新 session / capability action 与 open replacement 期间的 resume MUST fail closed；已存在 key/grant 的保留只用于原子 supersede 与审计，不等于 paused 状态可继续执行。
- 第 3 步 MUST 以单一 controller-signed `ak.agent.key.authorize`(K2) Event 原子 remove `supersedes[]` 指定的 K1 authorization dot（reason=`superseded_by_repairing`）并 add K2 dot；不得伪造第二条 controller-authored revoke Event；capability grants 不受影响。遗漏 K1、加入不存在/已撤销 authorization，或引用错误 `authorized_event_ref` 的变体 MUST conflict / fail closed 且不改变任何 key。
- 第 4 步 MUST fail closed:`K1` 的新 session 请求拒绝;`S1` MUST 在 revocation freshness window 内 fail closed,MUST NOT 自然存活到原 TTL。
- 变体 A:无任何配对副作用，Agent lifecycle 保持 `paused`、`K1` 有效；handle 过期后 generic key_state 清除 open-handle fields，readiness 移除 `pairing_open` 且不得出现第四状态轴。该 handle 的 pairing poll 可报 operation-local `runtime_state=ready`，绝不能报 `pairing_expired`。pause / resume 是纯 lifecycle 意图写入，在 handle open 期间也不被阻塞。
- 变体 B:MUST `agent_deactivated`(terminal 状态拒绝续期)。

### 11.2.5 Vector: Longevity-safe Authorization Chain(No Expiry Cliffs)

`vector_id`: `ak.vector.agent.longevity_no_expiry.v1`

Steps:

1. Controller provision agent；单一 `ak.agent.provision` 派生的 accountability projection 不声明 `expires_at`，`ak.agent.key.authorize` 不声明 `expires_at`，并授予不带 temporal constraint 的低风险内容 grant（如 `ak.agent.draft.propose` + 显式 resource selector）。
2. 模拟长时间推移(超过任何常见部署 TTL,如 400 天)后,runtime 用 authorized key 签发 session 并执行 grant 内动作。
3. Controller 执行 `ak.self.agent.command.pause.v1`。
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

### 11.2.6 Vector: Agent KeyPackage Authorization Binding

`vector_id`: `ak.vector.agent.mls_keypackage_authorization.v1`

Preconditions:

- Agent `A` 已完成 pairing；当前 active accepted `ak.agent.key.authorize` Event 为 `E1`，其 `verification_method=K1`，runtime 持有 K1 私钥与独立 MLS endpoint id `D1`。
- `A` 不是 controller 的 delegated device，且不存在 `(A,D1)` 的 `ak.device.authorize`。

Steps:

1. Runtime 用 K1 作为 MLS LeafNode signature key 生成 KeyPackage，并用 K1 签署发布 transcript；服务端从当前 accepted Agent key projection 写入 `agent_key_authorize_event_id=E1`。
2. Requester claim 该 KeyPackage，并把返回的 `agent_key_authorize_event_id=E1` 原样写入 Welcome `claim_ref`。
3. Receiver 在解密 Welcome 前 resolve E1，校验 E1 仍是 A 的 active accepted authorization，`verification_method=K1`，并校验 MLS LeafNode signature key 绑定 K1。
4. 负向变体依次为：额外携带普通设备的 `device_authorize_event_id`；把 E1 填入该字段；Event ref 属于另一 Agent；MLS LeafNode signature key 为 K2；E1 被 revoke、被 replacement `supersedes[]` 替换或可选 `expires_at` 已到期；只有 service-local Agent row 而无 accepted E1。
5. E1 被 E2 replacement 后，以 K2 发布新 KeyPackage并重新 claim，得到新 `claim_id` 与 `agent_key_authorize_event_id=E2`。

Expected:

- Steps 1–3 MUST 接受；D1 只作为 A 的 MLS endpoint / Welcome 投递实例，不创建或推断 `ak.device.authorize`，A 仍是独立 MLS member。
- Step 4 全部 MUST fail closed：wire 形状混合时 `schema_violation`；accepted trust state、principal、lifecycle 或 key material 不匹配时 `claim_generation_mismatch`。实现不得 fallback 到 controller device、service-local row、过期 authorization 或任一其它 trust branch。
- Step 5 MUST 接受；E1 下所有未消费 claim 永远失效且不得改写，新 Welcome 只能使用重新 claim 得到的 E2 binding。

### 11.2.7 Vector: KeyPackage write canonical transcripts

`vector_id`: `ak.vector.crypto.keypackage_write_transcripts.v1`

fixture：`spec/v1/artifacts/fixtures/keypackage-write-transcript-fixture.json`

Steps:

1. 用 fixture 的 typed upload request只删除顶层 batch signature，通过 SDK `keypackages_upload_signing_input`生成 bytes；完整 selector、entry数组、顺序、数量和metadata都保留在 transcript。
2. 用最小 typed consume command `{claim_id,recipient_durable_receipt}` 与 typed revoke request 通过 SDK helper 生成 bytes；consume 的 owner、KeyPackage、Welcome 与 signer branch 只存在于 nested durable receipt。
3. 从 signed `keypackage_consume_receipt` 删除 service `signature`，验证 receipt transcript 仍完整覆盖 `request_digest + claim_id + recipient_durable_receipt + consumed_at`，且 wrapper 不携任何 nested 坐标或 service-id 镜像。
4. 对每条 bytes 比较 fixture `canonical_jcs`、`signing_input_base64url`，并以 fixture Ed25519 test key 验证 `signature`。
5. 负向依次替换为旧 `ak.keypackage-upload-v1` domain、从 upload 移除 `principal_id`、篡改 selector/entry bytes/metadata/数量/顺序、向 consume command/receipt/outcome 插入已删除的镜像或 selector，以及把缺省 optional字段写成 `null`。

Expected:

- Steps 1–4 MUST byte-identical 通过；同一 closed endpoint 产生的 command bytes 只由 nested durable receipt branch 决定。
- Step 5 全部 MUST fail closed。服务端不得接受 per-entry signature、旧 transcript、已删除字段 alias 或本地 principal-type fallback。

#### 11.2.8 Vector: KeyPackage group capability floor

`vector_id`: `ak.vector.keypackage.group_capability_floor.v1`

fixture：`spec/v1/artifacts/fixtures/keypackage-lifecycle-fixture.json`

Steps:

1. 生成一个 signed LeafNode `keypackage_capabilities` (`0xF1C1`) 为
   `ak.content.v1,mimi.content.v1` 的 KeyPackage；outer upload / claim record 使用同一 canonical list。建群时把
   `required_keypackage_capabilities` (`0xF1C2`) 设为 `ak.content.v1`，并在 RFC 9420
   `required_capabilities` (`0x0003`) 的 `extension_types` 中列出 `0xF1C0`、`0xF1C1`、`0xF1C2`。
2. Add 上述 LeafNode，处理 Commit / Welcome，并从新 epoch GroupContext 读取 floor。
3. 依次尝试：Add 一个缺 `ak.content.v1` 的 LeafNode；让 outer record 比 signed LeafNode 多一个能力；把 floor
   提高到当前任一成员不支持的 `mimi.content.v1`；在 floor 不含 `mimi.content.v1` 时发送该 profile；用形状合法但
   registry 未登记的 `example.content.v1` 满足 claim 或写入 floor。
4. 用 canonical CBOR 的乱序、重复、indefinite-length、非最短长度与 trailing bytes 变体替换 `0xF1C1` /
   `0xF1C2` extension data。

Expected:

- Steps 1–2 MUST 通过；current floor 是 MLS 认证的 GroupContext 状态，加入后的每个 LeafNode 都是其超集。
- Step 3 全部 MUST 在产生可用的新 epoch 或 application message 前 fail closed。outer record 不是第二个能力真相源，
  unknown 值只能保留为 unsupported。
- Step 4 全部 MUST 以 extension decode / schema failure 拒绝，不得规范化后接受。

### 11.3 Vector: Agent Session Grant Replay Protection

`vector_id`: `ak.vector.agent.session_grant.replay.v1`

Steps:

1. Agent runtime 提交 `ak.gate.account.command.issue_session_grant.v1`,`proof.proof_kind="agent_key_proof"`,proof 含 challenge / audience / request_canonical_digest / expires_at / signature。
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
- A 后续任何 `ak.gate.account.command.issue_session_grant.v1` MUST fail closed。
- A MUST 立即离开相关 Sidecar effective access；服务端停止投递，并为每个受影响的 native Sidecar MLS group 建立 durable remove/epoch-rotation obligation。

同一 vector 还必须覆盖 Agent 自身的 terminal deactivation：request 只携带一个 controller-signed
`ak.self.agent.deactivate` lifecycle submission；accepted 后全部 runtime key、session、pairing handle、
以 Agent 为 subject/executor 的 grant、KeyPackage/presence/new Event 在 ≤60 秒 bounded freshness 内机械
ineffective。客户端提交逐 key/grant revoke bundle、只清 UI cache、或让任一 child authorization 绕过
`lifecycle=deactivated` AND gate 均为不通过。read view 必须分别返回 durable `lifecycle`、含闭合
`blockers[]` 的 `readiness` 与带 `expires_at/refresh_after` 的短期 `presence`；`offline` 不得替代前两轴。
`agent_projection` 增加 `runtime_state`、或 generic `key_state` 增加 `status` / `runtime_state` 的 schema case
必须失败；pairing poll outcome 仍必须要求其 operation-local `runtime_state`，证明不是删除 diagnostic enum。

#### 11.4.1 Vector: Controller Membership → Agent Cascade

`vector_id`: `ak.vector.agent.membership_cascade.v1`

runner MUST 执行 `agent-membership-cascade-fixture.json` 的全部 semantic cases，并至少构造以下真实签名路径：

1. Agent join 绑定 controller exact `(principal_id, station_id)` 与当前 controller join Event ID；controller leave/ban 或 rejoin 使旧 binding 立即 effective-invalid。
2. self leave 的 `atomic_self_leave` 缺任一 Agent、增加额外 Agent、重复、换 Realm/pair/generation/signer 或把 leave 改成其它 membership 时，controller 和 Agent Events 全部零写入；完整集合一次性成功。
3. 第三方 `emergency_terminal` 在 Agent cleanup 不可用时仍接受 terminal Event、durable 写 exact-set intent并返回 `terminal_applied_cleanup_pending`；Agent 从该 basis 起不能 author、取 capability、收 delivery、领 KeyPackage 或保留 MLS active membership。
4. `emergency_cleanup` 只接受原 initiator 对同 intent 的完整签名集合；restart 后 exact replay 幂等，异内容冲突，overdue 不解封，服务端从不合成 Agent Event。
5. 单独伪造 `membership_cause="controller_membership_ended"` 或自由文本 `reason` 不产生任何 cascade authority。

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
- 客户端渲染 "Controller vian Agent" 双重署名；不显示为纯 controller 行为。

### 11.6 Vector: Relation Reference Projection Indistinguishability

`vector_id`: `ak.vector.relation.reference_projection_indistinguishable.v1`

Steps:

1. Realm A 中存在 weak semantic Relation `R1`，目标指向 Realm B 内对象；调用者 C 可读 Realm A，但不能 discover / reference Realm B。
2. Realm A 中存在形态相同的 Relation `R2`，目标指向不存在或不可发现的 Realm / object id。
3. C 分别调用 Relation projection query、`ak.self.events.read.scan.v1` raw event API、backfill pull 与 federation peer fanout 视图。
4. 在同一服务端测量点、同一请求类别与同一部署 profile 下，对 `R1` / `R2` 每类至少采样 30 次。
5. Auditor D 同时持有 source + target disclosure，读取 `R1` 的完整 canonical event。

Expected:

- C 对 `R1` / `R2` 均只能看到 `ReferenceProjectionState.locked` 或等价 locked stub,wire 字段集合、Problem Details、metadata 集合必须相同。
- C 的视图 MUST NOT 泄露目标 `realm_id`、title、member_ids、created_at、issuer set、preview 或任何能区分"目标存在 vs 不存在"的信息。
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
- V MUST NOT 看到 Circle title、display、short_name、member_ids、created_by、join history 或可枚举错误。
- V 的 stub 最多为 `{ "visibility": "locked", "opaque_commitment": "<fixed-length>" }` 或等价字段集合；`opaque_commitment` MUST 固定长度、不可逆、不可由 title / short_name / member set 枚举。
- Realm public seal 只暴露固定 cadence 的 opaque commitment，不得反映真实 Circle 活动频率。
- M MAY 看到 policy 允许的 Circle metadata，但不得改变 V 的不可区分性要求。

### 11.8 Vector: Agent Sidecar Idempotent Ensure

`vector_id`: `ak.vector.sidecar.ensure_idempotent.v1`

Steps:

1. Alice 的两台设备并发对同一 `(realm_id, controller_account_id)` 调用 `prepare`，并请求映射同一 `source_context_ref`。
2. 一台设备对服务端返回的 exact `ak.sidecar.create` draft 签名并提交；另一台分别变异 Event ID、payload、
   `refs.after` 与 unsigned bytes，再重放自己的 reservation。
3. 两台设备并发提交同一 `ak.sidecar.context.attach`；随后 Alice 对另一来源上下文再次 attach。

Expected:

- 并发 create MUST 收敛到唯一 Sidecar；`sidecar_id` MUST 等于从胜出 create Event 的 `event_id` 按
  `id_kind=sidecar` 重类型得到的同一 44 字符 Event token。调用方不得提交或覆盖 `sidecar_id`。
- exact draft 可接受；任一被变异的 draft MUST conflict 且零写入。重放已接受 draft MUST 幂等返回同一 Sidecar。
- context attach 只投影 `(sidecar_id, source_context_ref)` 映射，不创建 Circle、membership、Strand 或 Relation。
  同一映射重放幂等；另一来源上下文产生另一映射，但仍复用同一 Sidecar。

### 11.8.1 Vector: Sidecar MLS Bootstrap Binding

`vector_id`: `ak.vector.sidecar.mls_bootstrap_binding.v1`

Steps:

1. Alice ensure Sidecar；accepted ownership/lifecycle 与该 Realm membership frontier 派生出
   `desired_agent_ids={A}`，读取服务端派生的
   `mls_context.{participant_authority_digest, control_frontier}`。
2. Alice 当前设备用真实 OpenMLS state 创建 native Sidecar-scoped `ak.mls.genesis`，提交前持久化
   `(sidecar_id, genesis_event_id, mls_group_id, provisional_snapshot)`，并携带精确 `sidecar_binding`。
3. 第二设备并发提交另一 `mls_group_id` 的 genesis；再分别变异 `sidecar_id`、authority digest、frontier
   顺序/成员与 creator device proof。
4. 模拟第一设备在 Event response 返回前崩溃并重启。

Expected:

- participant set MUST 精确等于 controller + 当前 Realm-scoped `desired_agent_ids`，排序去重后的 authority transcript digest
  必须与 `participant_authority_digest` 一致。
- 只有一个 genesis 通过标准 Event admission/CAS 成为 canonical winner；服务端不得生成 MLS private state、伪造 GroupInfo/ratchet-tree digest 或提供绕过 Event proof 的 bootstrap endpoint。
- 所有 binding 变异 MUST fail closed；native Sidecar scope 缺失 matching `sidecar_binding`、普通 Realm/Circle
  携带该字段也必须拒绝。
- creator device 只从该 genesis Event 唯一 producer proof 的 `verification_method` fragment 投影；变异该 proof
  MUST fail closed，且携带 `creator_principal_id` / `creator_device_id` 的 payload MUST 判 `schema_violation`。
- 崩溃恢复重放 bit-identical Event id/bytes，并把已接受 provisional snapshot 激活；loser snapshot 必须销毁并通过 winner group 的 KeyPackage/Welcome 加入。

### 11.9 Vector: Existence Privacy

`vector_id`: `ak.vector.sidecar.existence_privacy.v1`

Steps（均以非 controller 且非其 owned Agent 的 caller 视角）:

1. `ak.self.events.stream.subscribe.v1` / `ak.self.events.read.scan.v1` 目标 Realm。
2. 对 `to_ref=<target_message_id>` 的 relation query。
3. Realm directory 调用。
4. 触发目标 Strand 的 notification fanout。
5. 读取目标 Realm default seal leaf 明文 metadata。

Expected:

- 第 1 步返回 zero events referencing Sidecar native scope。
- 第 2 步不存在任何协议 Relation 可用于枚举 Sidecar 或 source-context mapping。
- 第 3 步对 `sidecar_id` 与 controller 映射均 zero hits。
- 第 4 步 Sidecar 内 Event 不触发 source Strand 参与者的 notification。
- 第 5 步 Sidecar-scoped Event 不出现在 Realm default seal leaf 明文中；只能作为 opaque commitment。

### 11.10 Vector: Ownership/Effective Access + Revocation 闭环

`vector_id`: `ak.vector.sidecar.eligibility_states.v1`

Steps:

1. Alice 的 active owned Agents `{S, R}` 都是当前 Realm active member。S 已 paired/MLS-ready；R 尚未发布 KeyPackage。
2. Alice 调用 ensure。
3. R 发布 KeyPackage，服务端 async reconcile。
4. Alice 调用 `ak.self.agent.command.deactivate.v1` 对 R。

Expected:

- 第 2 步 ensure SHOULD succeed，返回 `access_readiness=key_material_pending` 与 R 的 key-material pending 状态。
  R 属于 `desired_agent_ids` 但尚不属于 effective access，不能收取或解密消息。Sidecar 不存在 plaintext 分支。
- 第 3 步 R 经 native Sidecar MLS Welcome 加入，只获得 join 后 future epoch keys；完整 readiness 证据成立后才进入 effective access。
- 第 4 步 R deactivated 或离开当前 Realm 后，派生 desired 集合自动移除 R；服务端立即停止寻址/投递并产生 durable MLS removal obligation；
  eligible controller/key-service committer 随后提交真实 remove/rotation。后续 R 的 proof、Sidecar write 与 query MUST fail closed。

### 11.10.1 Vector: Sidecar MLS Effective Access Evidence

`vector_id`: `ak.vector.sidecar.mls_effective_access.v1`

Steps:

1. A 是当前 Realm-scoped desired Agent，但尚无 Add Commit/Welcome/consume；随后分别只补齐其中一部分证据。
2. 对 A 的 active device D 提交 accepted Add Commit、引用该 Commit 且 binding 匹配的 accepted Welcome，并由 D 的 authenticated session consume 同一 claim/KeyPackage。
3. 对 controller 的第二设备重复 join；随后使 A deactivated 或离开当前 Realm，使 pending removal obligation accepted，
   但暂不提交 Remove Commit。
4. eligible committer drain obligation 并提交真实 Remove proposal/Commit；再用旧 Welcome/consume 记录尝试恢复 A effective 状态。

Expected:

- 第 1 步任何不完整组合均保持 pending；desired membership、delivered Welcome 或 claimed KeyPackage 单独都不是 effective 证据。
- 第 2 步 D 成为有效设备，A 进入 `effective_agent_ids`；同 principal 的其它设备不会自动拿到密钥。controller 当前 session device readiness 独立计算。
- 第 3 步服务端立即停止 A 的寻址/投递并移除 effective access，且只产生 durable removal obligation；
  不持有 MLS private state 的 Station 不得伪造 Commit。新发送保持 fail closed。
- 第 4 步真实 Remove Commit 推进 epoch；旧 Welcome/consume 不能使已移除设备复活。

### 11.10.2 Vector: Hosted Multi-Track Projection and Private Echo

`vector_id`: `ak.vector.sidecar.hosted_projection.v1`

Steps:

1. Alice 在来源 Strand `F` 的 `discussion` Track 以 owned-Agent selector 提交 routed request，当前已见 shared frontier 为 Event `E0`。
2. 客户端 ensure Sidecar，并提交 `ak.sidecar.context.attach{sidecar_id,source_context_ref=F}`；分别以额外
   `track_name` 与 `message_id` 构造两个 negative attach request。
3. Sidecar request Event `P1` 被接受后，客户端 fold 出 `exchange_id=X1` 的本地
   `ak.schema.agent_sidecar_exchange_projection.v1` cache；删除该 cache 后从 Sidecar history 重建。
4. Alice 激活主 Strand 寄宿 Sidecar，在 `context_merged` 下依次切换 `discussion`、`synthesis`，再切换为 `sidecar_only`；`synthesis` private Track 尚未建立。
5. Agent 在同一 exchange 产生内部协作 Event `I1`（binding `role=internal`）与明确 user-facing response Event `R1`（binding `role=user_facing_response`，`request_event_id=P1`）；随后 Alice 在 active Sidecar 内直接创建 native Event `N1`（无 binding）。
6. 第二设备从 account stream 恢复 view state，并从 Sidecar private Event history 独立 fold exchange projection。

Expected:

- 第 2 步 attach 只建立来源上下文映射；额外 `track_name`/`message_id` closed-schema reject，且不创建 Strand/Relation。
- 第 3 步 cache 删除/重建不重复 request 或 Agent execution；echo 位于 `E0` 后，同一 `source_event_id` 下按 `(source_hlc, exchange_id)` 排序。
- 第 4 步主 Strand title/breadcrumb/Track tabs 保持可见；两种 mode 只控制 UI 投影和后续写入目的 scope。
  缺失 Sidecar `synthesis` 视图显示 private empty state，不回退 shared write/read。
- merged `discussion` 按 Sidecar Event id 去重；shared/Sidecar provenance 与 controller-only 可见性标识持续可见。
- 只有 `P1` 与 `R1` 可进入 echo；`I1` 与 `N1` 不创建 source echo。第二设备得到相同排序、状态与去重结果，且无需来源 Realm 重放 private Event。

### 11.10.3 Vector: Sidecar Exchange Binding Closed Loop

`vector_id`: `ak.vector.sidecar.exchange_binding_closed_loop.v1`

Steps:

1. Alice 提交 routed request：`P1` 携带 `role=request` binding，`addressed_agent_ids=[S,T]`、
   `coordinator_agent_id=S`；completion policy 由 schema identity 固定为 coordinator，不在 binding 回显。另一个 owned Agent U 未被 addressed。
2. S 通过 runtime 消费门后产生 `I1` 与 user-facing `R1`；runtime 重启并再次收到 `P1`。controller 又 author 不同 request Event `P_dup` 复用同一 `exchange_id=X1`。T 产生 user-facing `R_noncoord` 且错误声明 `completes_exchange=true`；U 尝试执行同一 request。
3. 构造变异响应：wrong exchange/request/sidecar scope、actor U、unknown role、missing binding、缺少顶层
   `refs[role=after]`、以及 `ak:message:` shaped request id；另由 T 发送携带 `role=request` 的 Event `F1`。
4. `R1` 重复投递同一设备两次。
5. S 发送 `R2`（`role=user_facing_response`, `completes_exchange=true`, `coordinator_assignment_event_id=P1`）；controller 验证后 author `C1=ak.agent.sidecar.exchange.control{action=close,response_event_ids=[R1,R_noncoord,R2]}`。

Expected:

- 第 1 步 runtime 只从 `P1` binding 获得 `X1`；不存在 Account Data projection 读写路径。S/T 可继续消费，U 必须把 request 当作不存在。
- 第 2 步 runtime 持久化 `X1 → P1`，restart 不得重复执行；`P_dup` 即使拥有不同 Event id 也因复用 `X1` fail closed。已接受的 canonical `P1` 已处于 delivered，`I1` 只推进 participating 且不改变状态；`R1` 推进 responding；T 的正文可回显，但非 coordinator completion 请求不得产生 control Event；U 不执行。
- 第 3 步全部变异 fail closed 为 non-echo；missing binding 是安全缺省而不是 schema error；`R_msgid` 是
  closed-schema reject；wrong Sidecar scope/actor/ref 不进入 fold；`F1` 因 actor 非 controller 整体无效。
- 第 4 步重复到达幂等：`user_facing_response_event_ids` 只含一次 `R1`。
- 第 5 步 `R2` 本身仍只推进 responding；accepted `C1` 才推进 complete。response 集按 `(Event HLC, Event id)` 排序且至少一项；不得由时间流逝、Event 缺席或内容直接推断终态。

### 11.10.4 Vector: Sidecar Exchange Event Fold, Control and Cache Recovery

`vector_id`: `ak.vector.sidecar.exchange_projection_recovery.v1`

Steps:

1. `P1` accepted 后本地 cache 与 intent 都丢失；重启扫描 Sidecar history，从 controller-authored request binding 重建。
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

1. 构造明文 `metadata.sidecar_exchange_binding` 的 Sidecar-scoped `ak.message.create`。
2. 构造 shared Realm/Circle scope 的 `ak.message.create` binding，以及 shared scope 的
   `ak.agent.sidecar.exchange.control`/control schema plaintext。
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

1. Sidecar desired/effective participants 为 Alice + 当前 Realm active Agents `{S, R}`，且 S/R 都在 native Sidecar scope 中产生协作内容。
2. S 调用 publish capability action，生成目标 Strand `ak.message.create`,attribution 设 `executed_by=S` + `authorization_ref=G_S`。
3. R 同时尝试 publish 含 S 部分内容的另一条消息。

Expected:

- 第 2 步 `actor_id` / `executed_by` MUST 是 S 单一 DID，而非 "agent group"。
- 第 3 步若 R 的 grant 不覆盖该内容或 R 未持 fresh approval,MUST fail closed。R 通过自己的 grant 可独立发布，但 attribution 仍是 R 单一 DID；不得复合 S+R。

### 11.12 Vector: Participation Policy Tighten-Only

`vector_id`: `ak.vector.agent.participation.ceiling_tighten.v1`

参见 [`../models/realm-and-space.md` §2.2](../models/realm-and-space.md)、[`../models/circle.md` §7](../models/circle.md)、[`../models/strand-and-message.md` §9.4](../models/strand-and-message.md)。

Preconditions:

- 部署顶层 policy 为 `{reply_message:true,reaction_add:true,reaction_remove:false,accept_third_party_mention:true,act_on_behalf:false}`。Realm `R` 经 `ak.realm.policy_bundle` 写入同一个 required 五位 inner shape。

Steps:

1. Circle `C`(父级为 `R`)写入完整五位 policy，并把 `accept_third_party_mention` 收紧为 `false`。
2. Strand `F`(`scope_circle_id=C`)写入与 Circle 相同的完整五位 policy。
3. 变体 A：Circle `C` 尝试写入 `act_on_behalf:true`(放宽父 Realm `agent.act_on_behalf=false`)。
4. 变体 B：Strand `F` 尝试写入 `accept_third_party_mention:true`(放宽父 Circle `C` 的 `false`)。

Expected:

- 第 1、2 步 MUST 接受(每一位 ⊆ 父级 ceiling)。
- 变体 A、B MUST fail closed(`failed_precondition`, `reason="agent_participation_ceiling_widen"`)，与 [`../models/circle.md` §7](../models/circle.md) 的 floor downgrade 同形。
- 未显式声明 `agent_participation` 的内层 scope 继承父级 ceiling(不放宽)；effective ceiling 以从 Strand→Circle→Realm→deployment 逐级按位 AND 求值，对违反不变量的历史数据 fail closed。

### 11.13 Vector: Participation Is an Action-Time Deny Gate

`vector_id`: `ak.vector.agent.participation.effective_intersection.v1`

参见 [`../authz/capabilities.md` §5.4](../authz/capabilities.md)、[`../identity/key-management.md` §3.6.1](../identity/key-management.md)。

Preconditions:

- Realm `R` 的 current agent policy 允许 `reply_message/reaction_add`，拒绝 `reaction_remove/act_on_behalf`。Agent `A` 为 controller `Alice` 的 active Agent，并持有 `ak.message.create` 与 `ak.reaction.add` 的普通 capability。

Steps:

1. Alice 以 `expected_version=0` 保存 selection=`{reply_message:true,reaction_add:true,reaction_remove:true,accept_third_party_mention:false,act_on_behalf:true}`。
2. `A` 尝试发送 message、添加 reaction、删除 reaction 和 act-on-behalf。
3. 变体 A：之后 Realm policy 把 `reply_message` 收紧为 `false`。
4. 变体 B：current selection 或任一 required target policy 来源 unknown/stale。
5. 变体 C：撤销 `ak.reaction.add` 的普通 capability，但 selection 与 policy 保持 `reaction_add=true`。

Expected:

- 第 1 步只保存 selection/version，不创建任何 Realm Event、capability grant 或 revoke。
- 第 2 步 message 与 reaction-add 通过 participation gate；reaction-remove 与 act-on-behalf 被 current policy 拒绝。每个动作仍须独立通过其普通 capability、session、membership 与 lifecycle。
- 变体 A 立即拒绝后续 message，不改写已保存 selection，也不产生 revoke。
- 变体 B 对相关动作全 deny；变体 C 即使 participation 两侧都为 true，仍因普通 capability 缺失而拒绝。

### 11.14 Vector: Participation Selection CAS

`vector_id`: `ak.vector.agent.participation.selection_cas.v1`

参见 [`../sync/service-surface.md` §10.1](../sync/service-surface.md)。

Preconditions:

- Agent `A` 在 Realm `R` 的 selection slot 尚未写入。

Steps:

1. Controller 调用 replace，body 为完整 `{target_scope:R,selection,expected_version:0}`；selection 可包含当前 target policy 拒绝的位。
2. Controller 再以 `expected_version=1` 替换同一 slot。
3. Controller 重放第 2 步，或两个设备同时提交 `expected_version=1` 的不同 selection。
4. 变体 A：调用方不是该 agent 的 controller；变体 B：body 缺位或 scope 不是 closed realm/circle/strand shape。

Expected:

- 第 1、2 步成功后 version 分别为 1、2；GET 返回 `{target_scope,selection,version,next_replace_input:{expected_version}}`，且每项 `next_replace_input.expected_version=version`。
- 第 3 步只能有一个竞争写成功；其余返回 `cas_conflict` 且零写入。客户端 GET 最新 version、合并用户意图后重试。
- target policy 不参与 replace admission；被 policy 封顶的 selection 位可以存储，但不会产生权限。
- 变体 A、B fail closed。replace/get 都只允许 controller；Agent runtime 通过 session grant 获得所需快照。

### 11.15 Vector: Participation Session Overlay

`vector_id`: `ak.vector.agent.participation.session_overlay.v1`

参见 [`../sync/service-surface.md` §10.1](../sync/service-surface.md)。

Steps:

1. Agent runtime 调用 `ak.gate.account.command.issue_session_grant.v1`，`proof.proof_kind="agent_key_proof"`，`agent_scope_request` 覆盖某 participation-aware scope。
2. 服务端签发 session，签名 JWT claims 中含 `scope_details.participation[]`；HTTP outcome 不复制该字段。
3. runtime 收到 `reply=false` 的 scope 后仍尝试 `ak.message.create`(模拟 runtime bug)。

Expected:

- 第 2 步签名 claims 的 `scope_details.participation[]` 每个条目 MUST 与 `agent-operations.schema.json#/$defs/agent_participation_entry` 的 `{target_scope,selection,version,next_replace_input:{expected_version}}` 同构，`next_replace_input.expected_version=version`，不携带 ceiling/effective。runtime 可把该 claim 当调度提示；授权只由 resource server 验签 JWT 或 issuer introspection 得出。
- runtime 用该数组避免无效请求，但它不是安全边界：第 3 步仍由 target 读取 current policy 与 selection，并独立校验普通 capability；第三方 mention 在 dispatcher gate 拦截，`act_on_behalf` 还必须通过 receiver 的 `executed_by`/`authorization_ref` 校验。

### 11.16 Vector: Participation Third-Party Mention Gate (Non-Retroactive)

`vector_id`: `ak.vector.agent.participation.third_party_mention_gate.v1`

参见 [`../models/strand-and-message.md` §9.4.5](../models/strand-and-message.md)。

Preconditions:

- Agent `A` 为 controller `Alice` 的 active Agent，有权读取 Strand `F`。`F` 的 effective `accept_third_party_mention=false`。

Steps:

1. 非 controller 的 `Bob` 在 `F` 发 `ak.message.create`，mention target=`A`。
2. controller `Alice` 自己在 `F` 发 mention target=`A`。
3. Alice 把 `F` 的 effective `accept_third_party_mention` 翻为 `true`，`A` 上线同步。
4. 翻转后 `Carol`(非 controller)再发 mention target=`A`。

Expected:

- 第 1 步 MUST NOT 为 `A` 派生任何 mention notification、inbox row、push wakeup，也 MUST NOT 把该 mention 纳入 `A` 的 `ak.self.events.stream.subscribe.v1` 投影；抑制只针对 `A`，对 message 的其他 human target、shared history、其它投影无影响。
- 第 2 步照常投递(controller 自己的 mention 不受此 gate，仍受 `A` 是否被授权读取该 scope 约束)。
- 第 3 步翻转 **非追溯**：第 1 步发生在 `false` 期间的历史 mention，翻转为 `true` 后对 `A` 仍 MUST 零记录(notification / inbox row / `ak.self.events.stream.subscribe.v1` 投影皆无)。
- 第 4 步在 `true` 期间的第三方 mention 照常投递，并受 `level=muted`、blocklist、DND、rate-limit 等既有更高优先级规则约束。

### 11.17 Vector: Agent Human Approval Required

`vector_id`: `ak.vector.agent_auth.human_approval_required.v1`

Steps：

1. Agent runtime 以 `proof.proof_kind="agent_key_proof"` 调用 `ak.gate.account.command.issue_session_grant.v1`，请求 policy 标记为 high-risk 且需 controller 批准的 scope。
2. Account Authority 生成 opaque `approval_request_id`，但不向 runtime 返回人类交互 challenge。
3. Controller 在带外 UI 批准，产生 accepted approval / capability / delegation evidence；agent 带该 evidence 重试。

Expected：

- 第一次响应使用统一 RFC 9457 Problem Details：`error.code=claim_required`，`error.details` 必须严格通过 `agent-operations.schema.json#/$defs/agent_human_approval_error_details`，即只含 `reason_code=human_approval_required` 与 `approval_request_id`。
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
2. Issuer 返回 200 with `backend_token` / `participant_id` / `participant_binding` / `expires_at`。

Expected:

- `expires_at - now` MUST ≤ 600s（SHOULD ≤ 300s）。
- `participant_binding.scheme` MUST = `ak.media.participant_binding.v1`。
- `participant_binding.issuer_kid` MUST 解析到当前 epoch `ak.realm.media_service.service_id`。

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

1. Realm policy 中某 `foci[].focus_kind = "experimental-x"`（unregistered）。
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
- 唯一合法 key 来源是 MLS-Exporter（label `ak.rtc-frame-key/v1`, length=19 bytes, Context=`canonical_json({realm_id, call_id, focus_id, epoch_id, participant_id, device_id})`, KDF.Nh=32 bytes），其中 `participant_id` / `device_id` 取自已验证的 call roster participant value 与 `participant_binding`。
- 负向覆盖：以下派生 MUST 同样 fail closed 报 `e2ee_key_source_unauthorised`——(a) `Context=""`（空 Context）；(b) 缺少 sender 字段（`participant_id` / `device_id`）；(c) 仅绑定 `epoch_id` 而不含完整 sender-bound Context。

### 12.8 Participant Identity — Cross-Check

`vector_id`: `ak.vector.media_binding.participant_id_unrecognised.v1`

Steps:

1. Backend signal `ParticipantConnected` with `participant_id=ak:rtc_participant:<unknown>`，无对应 call roster effective OR-Set 项。

Expected:

- Client MUST 拒绝为该 participant 建立媒体流（不收音、不订阅 video），报 `participant_id_unrecognised`。

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
   - (b) `participant_binding` 的 `realm_id` / `call_id` / `focus_id` / `actor_id` / `device_id` / `participant_id` 中某一项与该 participant entry 不一致；
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
- 反例（control）：`audit_lock=false` 且已过 `retention_expires_at`、`deletion_trigger=retention_expiry` 时删除 MAY accepted；start payload 不携自身 Event ref 且 `consent_confirmed=true` 时，receiver 在验完完整 identity 后把该 identity 派生写入 result projection，FSM/result 两个 projected writes MUST 原子 accepted。任何 producer 自报的 start-event id MUST `schema_violation`。

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

### 13.1 Since-Join Denies Pre-Join History

`vector_id`: `ak.vector.history_access.since_join_prejoin_denied.v1`

Setup:

1. Realm R 在目标 epoch activation T0 的 effective `ak.realm.history_access.value = "since_join"`。
2. Alice 是 active member 并提交 message `E_before`。
3. Bob 在后续 Seal `J` 才通过 `ak.member.state{membership=join}` 加入。
4. Bob 调用 backfill，范围覆盖 `E_before`。

Expected:

- Receipt-bound direct replay MUST 从标准 reducer state 证明 Bob current incarnation 的 exact winning Add/Genesis transition 与 `join_epoch`。Add proposal 的 `target_authorization_incarnation`、Commit 的 `proposal_refs` 与 `next_epoch` 必须形成逐字闭合 lineage；不得从成员 cell、`joined_at`、`received_at` 或本地观察时间自报数字。
- `ordinary_human` request MUST 签入 exact device id、device-authorize Event 与 PCR generation；T1 必须用该 locator 构造 current PCR view，换用同 principal 的另一设备或当前 session 设备 MUST 拒绝。
- 请求 range 与 chunkrange 中 `epoch < join_epoch` 的部分 MUST 拒绝或 canonical 裁剪；`epoch >= join_epoch` 可继续进入首次入队 T1 gate。
- 把旧五档 literal、当前 wall-clock 策略或本地首次看到时间当作 join floor，均 MUST 拒绝。

### 13.2 Preview Token Is Stripped-State Only Unless Policy Allows More

`vector_id`: `ak.vector.preview.token_scoped_stripped_state.v1`

Setup:

1. Realm R 的 discoverability 为 `invite_only`，但 Alice 给 Bob 发出 `lt=preview` token。token payload 绑定 `target_digest`、`address_link_kind="preview"`、`preview_policy_digest`、`aud=Bob`、短 TTL。
2. Effective `ak.realm.preview_policy.value.mode = "stripped_state"`，fields 只包含 `title`、`summary`、`join_rule`、`member_count_bucket`。
3. Bob 调用 `ak.find.directory.read.resolve_target.v1`，携带 address 与 token。
4. 攻击者 Mallory 把同一 token 放到另一个 Strand address，或把 URL `lt` 改为 `invite`。

Expected:

- Bob MAY 收到 `realm_preview` / `object_preview` 中 policy 允许的 stripped fields。
- 响应 MUST NOT 包含正文历史、成员列表、policy 原文、`join_candidates[]` 或任何 write / membership grant。
- Mallory 的 scope-confused request MUST 返回与不存在不可区分的 `not_found`；resolver MUST 比对 token 内 `target_digest` 与 effective `address_link_kind`，不得只校验 token 签名。

### 13.3 Exporter Pre-Join Delivery Uses T0/T1

`vector_id`: `ak.vector.history_key.exporter_prejoin_t0_t1.v1`

Setup:

Expected:

- Request receipt 冻结完整 direct Seal traversal；T0 由标准 replay 派生 exact winning transition、requester current incarnation/join epoch 及 current 单向收紧 `history_access`。首次 chunk 入队的 honest release service 再按 closed predicate registry 验证 recipient local authority、scope current membership/incarnation、source relay 与 frozen release-service binding，并把 exact locator/digest vector 签入唯一 `HistoryReleaseAttestation`；不存在 activation proof、epoch ceiling、open-world safety gate 或 pre-release audit token。
- `all_history_for_current_members` 只有在 current T0 与 T1 都允许且 requester 当前 active 时才允许加入前 range；current 为 `since_join` 时必须按 exact join epoch 裁剪。Producer 不得自报 policy/member digest，也不得把 current head 当成 reducer effectiveness 证据。
- Bob 客户端不得仅凭 current `history_access` 自行推断 epoch 7 key；没有合法 private manifest/chunk、完整 direct replay 与 release attestation 时，`E_before` 保持 `decryption_pending`。
- 若 Realm R 的 group Genesis 固定 `content_scheme="mls_rfc9420"`，S MUST NOT 为 join 前内容发送可用 key share；该 group 的任何 epoch 都不存在可交付给后加入者的 `history_secret`，后续 policy 也不得切换 scheme。

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

## 15. Moderation / Key Backup / Federation Ingress Vectors

本节收拢治理域（content moderation、key backup）与 federation ingress 的 conformance 向量。每个 `vector_id` 均为规范性引用目标，登记于 [`vector-registry.json`](../../artifacts/registry/vector-registry.json)。

### 15.1 Vector: E2EE Franking Roundtrip

`vector_id`: `ak.vector.moderation.franking_roundtrip.v1`

本向量固化 [`content-moderation.md`](../governance/content-moderation.md) §3.4 的七字段 franking receipt、目标 Event 内容承诺、唯一 detached-signature transcript 与 durable proof Event/Seal 时间锚。

Steps：

- **Case A — roundtrip 正路径**：
  1. E2EE Realm 中 sender 发送密文消息；receiving service 按 §3.4 生成只含 `realm_id`、目标 `event_id`、`received_by`、`verification_method`、`received_at`、`replay_nonce`、`signature` 的 `ak.moderation.franking_proof` payload，并先发布为 durable proof Event。
  2. reporter 提交 `ak.self.moderation.command.report.v1`，附加密 evidence package（加密给 `effective_scope` 对应 moderator audience）与该 `franking_proof`。
  3. moderator 按 §3.4.1 “Franking 信任链”步骤 1–6 验证目标 Event ID、历史 service key/binding、唯一 JCS 签名、byte-identical durable proof Event 与首次 covering Seal 的 inclusion/time anchor。
- **Case B — 篡改 / 闭合字段违反**：(a) target Event bytes 或 `event_id`、Realm、service、received time/replay nonce 任一被篡改；(b) proof 携带 schema 外的 digest、sender claim、proof id、payload kind 或 plaintext body。

Expected：

- **Case A**：全部校验通过后，moderator MAY 把 `franking_proof` 视为可验证投递证明；evidence package MUST NOT 包含 Realm / Circle 历史 key、MLS epoch secret、exporter secret 或允许 moderator 解密未举报消息的材料；举报 MUST NOT 触发任何治理密钥释放（§3.4.1：MUST NOT 把 `ak.self.moderation.command.report.v1` 自动升级为 `ak.audit.session.request`）。
- **Case B(a)**：任一 Event commitment、签名、historical binding、nonce 或 Seal observation 环节不符时，moderator MAY 把材料作为人工线索，但 MUST NOT 将该 `franking_proof` 视为可验证投递证明。
- **Case B(b)**：closed schema / receiver MUST 拒绝全部 schema 外字段与 plaintext body。

### 15.1.1 Vector: Franking Proof Signature Transcript

`vector_id`: `ak.vector.moderation.franking_proof_transcript.v1`

Runner MUST 加载 [`franking-proof-transcript-fixture.json`](../../artifacts/fixtures/franking-proof-transcript-fixture.json)，删除 payload 中唯一的 `signature` 成员，加入固定 `domain="ak.franking_proof.signature.v1"`，并对七字段对象执行 RFC 8785 JCS 后直接验证 Ed25519 签名。正例必须逐字匹配 fixture 的 `transcript_jcs`、digest 与签名；对 `domain`、`realm_id`、目标 `event_id`、`received_by`、`verification_method`、`received_at`、`replay_nonce` 任一字段的单独修改都 MUST 因签名无效而拒绝。Runner MUST NOT 把该 domain 当作 shared detached-JWS proof context，也不得把 `signature` 放回 transcript。

### 15.1.2 Vector: Moderation Evidence Package Minimal Disclosure

`vector_id`: `ak.vector.moderation.evidence_package_minimal_disclosure.v1`

本向量固化 [`content-moderation.md`](../governance/content-moderation.md) §3.4 的 evidence package 最小披露闭包：evidence package MUST 加密给 `effective_scope` 对应 moderator audience，MUST 只包含 reporter 可见且愿意提交的目标证据，MUST NOT 包含 Realm / Circle 历史 key、MLS epoch secret、exporter secret 或允许 moderator 解密未举报消息的材料。

### 15.2 Vector: Moderation Review Resolution 与多 Decision Fold

`vector_id`: `ak.vector.moderation.review_resolution_fold.v1`

本向量固化 [`content-moderation.md`](../governance/content-moderation.md) §2.6：active moderation decisions 是可 join 的 OR-Set，普通多 entry 必须按 `hard_deny > quarantine > require_review > none` 取最严格 effective decision；active `require_review` add 是 pending-review 的 canonical carrier，解除必须原子 lift 全部适用 review gates，并在 allow 路径重新执行当前 authz。

Cases / Expected：

- 两条来自不同 issuer 的 active `require_review` add MUST 收敛为 effective `require_review`，不得报 split；同时存在 `quarantine` 时 effective MUST 为 `quarantine`。
- allow resolution 必须在同一 batch lift 本次 gate 的全部 active review decisions；只 lift 部分 MUST 原子拒绝并保持 pending。全部 lift 后候选仍不得自动接受，MUST 重跑当前 capability / policy / membership / quota。
- hard-deny / quarantine resolution 必须把 review lifts 与 replacement decision 原子提交；不得留下“review 已解除但 replacement 未写入”的窗口。
- 只有同一 add identity 对应不同 canonical bytes、remove provenance 不可验证等真正非 joinable 状态才返回 `moderation_control_split` / `moderation_state_conflict`。

### 15.3 Vector: Key Backup Unlock Proof 校验

`vector_id`: `ak.vector.key_backup.unlock_proof.v1`

本向量固化 [`key-management.md`](../identity/key-management.md) §7.7.1 / §7.8 的取回校验 MUST：取回完整 ciphertext 的协议操作是 `ak.self.keys.backups.command.unlock.v1`（`POST /_arkret/self/keys/backups/{backup_id}/unlock`），unlock proof MUST 作为 request body 的 `proof` 字段提交；“服务端在返回完整 ciphertext 之前，MUST 校验该 unlock proof 与请求 session、caller、新设备 key、active-series record 和目标 envelope 一致；任一不符 MUST fail closed”；“`POST /_arkret/self/keys/backups/{backup_id}/unlock` 即便对自己的备份也 MUST 要求 fresh device proof……bearer token 单独到达 MUST 被拒绝”。

Steps：

- **Case A — 正路径**：恢复设备在 recovery session 内提交符合 `ak.schema.key_backup_unlock_proof.v1` 的 proof（绑定 `recovery_session_id`、完整 `account_id`、`requesting_device_id`、`backup_id`、`backup_kind`、`series_id`、`ciphertext_digest`、`proof_kind`、`proof_digest`、`issued_at`），服务端用当前 session state 重建 transcript 并逐字比较完整 AccountId 后返回 ciphertext；method adapter 只比较 verification method 对 `account_id.principal_id` 的投影。客户端按机器 fixture `key-backup-hardening-fixture.json` 的 `crypto_transcript` 重算 AEAD open（`aead` / `key_b64u` / `nonce_b64u` / `aad_canonical_json` / `ciphertext_b64u` / `tag_b64u`），校验得到的明文符合 `ak.schema.key_backup_plaintext.v1`，且 `backup_id` / `backup_kind` / `series_id` / `series_seq` byte-for-byte 等于外层 envelope。HPKE recipient 的端到端 transcript 由 HPKE suite 向量覆盖；本向量的机器正样本使用对称 AEAD transcript 固化 unlock proof 与 envelope / plaintext 绑定。
- **Case B — 绑定不符 / 凭证降级**：(a) proof 的 `ciphertext_digest` 指向另一 envelope，或 `requesting_device_id` 与本次 session 的新设备 key 不一致，或 `proof_digest` 与服务端重建的 transcript 不符；(b) 调用方仅携带 bearer token、无 fresh device proof 请求同一端点。

Expected：

- **Case A**：ciphertext 返回且明文校验通过；`items[].secret_id` / `item_kind` 只作 keybag 内部路由，不得替代外层 envelope 的授权判断；明文 MUST 仅作本地瞬时材料，日志 / telemetry MUST NOT 记录 `secret_b64u`。
- **Case B(a)**：MUST fail closed，错误码取 `recovery_evidence_unbound` / `backup_frontier_stale` / `series_chain_broken` / `signature_invalid` 中对应稳定码；服务端 MUST NOT 采信客户端自报的 policy / session metadata。
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

- 三类失败的对外响应 MUST 使用同一 HTTP status 与同一统一鉴权失败 `reason_code`（`error-code-registry` 已登记的统一码，如 `capability_denied`），Problem Details 可见字段集合 MUST 相同，MUST NOT 携带 Realm / Actor / Event / binding / frontier 是否存在的任何可区分信息；真实失败原因 MUST 只写入接收方审计日志。
- timing 同桶判定按 [`relation.md`](../models/relation.md) §4.5 口径：每类 ≥ 30 次采样下，各失败类别两两之间 p95 处理时延差异 SHOULD ≤ 50ms；声明高安全 profile 时 MUST 使用 padding / jitter 使 p99 也落入同一 timing bucket。
- conformance runner MAY 在同一网络条件下补充端到端抽样，但判定以服务端本地口径为准。

失败条件：

- 任两类失败返回不同 status / `reason_code` / 字段集合，或错误 body 泄露目标是否存在。
- p95（或高安全 profile 下 p99）超出同桶判定，形成可观测的存在性 timing 侧信道。

### 15.8 Vector: Federation Realm Reducer Profile Resolution

`vector_id`: `ak.vector.federation.reducer_profile_resolution.v1`

本向量验证联邦 receiver 对每个 Event 从其认证 CBA governance basis 读取 Realm reducer-profile singleton cell；普通 Event 与 federation service binding 均不声明 reducer identity。执行数据见 [`federation-fixture.json`](../../artifacts/fixtures/federation-fixture.json)。

Steps：

1. 对 DataEvent 从 `seal_ref` 认证的 joined control state 读取 `ak.component.realm.reducer_profile.v1`；对 Control Move 从 `seal_basis` 的 frozen predecessor `J(L)` 读取。
2. 验证 Event 与 `service_binding_ref` 均没有 reducer profile 字段。
3. 将 settled profile 与 receiver 的 `supported_reducer_profiles[]` 比较。
4. 对 `ak.realm.upgrade`，先由 source profile 验证 Event，再检查 target registry row 与 source→target edge。

Expected：支持 `ak.reducer.core.v1` 时普通 Event 继续 admission；本地未实现 settled profile 时返回 `unsupported_profile`；target row 未注册时 upgrade 返回 `unsupported_profile`。任何实现不得用本地默认 profile、latest Realm state 或请求字段替代 Event 自身的 CBA basis。

## 16. Streaming Chunked AEAD Attachment Vectors

本节收拢分块流式 AEAD 加密附件 scheme `ak.blob.stream_aead.v1` 的 conformance 向量，固化 [`media-and-blob.md`](../crypto-media/media-and-blob.md) §3.2 形态选择与 §3.3 的分块构造 / nonce / AAD / 整体 digest / 解密验证 MUST。每个 `vector_id` 均为规范性引用目标，登记于 [`vector-registry.json`](../../artifacts/registry/vector-registry.json)；Problem Details `reason_code` 取 [`error-code-registry.json`](../../artifacts/registry/error-code-registry.json) 已登记的稳定码。

### 16.1 Vector: Streaming AEAD Roundtrip

`vector_id`: `ak.vector.blob.stream_aead_roundtrip.v1`

本向量固化 [`media-and-blob.md` §3.3.1](../crypto-media/media-and-blob.md) 切分、同文 §3.3.2 nonce 构造、§3.3.3 AAD 绑定、§3.3.5 content-addressed `blob_ref` 整体 digest 语义与 §3.3.6 解密验证的正路径：明文按 `segment_bytes` 切成有序 segment（末段长度在 `1 .. segment_bytes`，可短于 `segment_bytes`），逐段独立 AEAD 加密、可分段下载并逐段增量校验，最终整体 digest 重算与 ref 内嵌值相等。

Steps：

1. 取一份明文，长度使派生段数 `N = max(1, ceil(plaintext_size / segment_bytes))` 且末段严格短于 `segment_bytes`（含短末段路径）；envelope 走 [`blob.schema.json#/$defs/encrypted_attachment`](../../artifacts/schemas/blob.schema.json) 的 `ak.blob.stream_aead.v1` 分支，声明由完整 stored ciphertext 派生的 content-addressed `blob_ref`、`scheme`、`nonce_prefix`（per-object 随机，长度 `N_AEAD - 5`）、`segment_bytes` 与 `size_bytes`，不声明 sibling digest、段数或 `epoch`。分别以 accepted winning commit Event ref 与等价 proof hash 构造 `key_ref.group_state_ref`，并从 exact winning group state 唯一派生 epoch。
2. 对每个 segment 用同一 content key、nonce = `nonce_prefix || u32_be(segment_index) || last_segment_flag` 加密，并把 `segment_index` / `last_segment_flag`（及 `media-and-blob.md` §3.3.3 要求字段）纳入 AAD；末段 `last_segment_flag = 0x01` 且 `segment_index == N - 1`。
3. 接收方按 `segment_index` 从 `0` 起严格升序分段下载（SHOULD 按 `segment_bytes` 整数倍偏移做 Range），逐段做 per-segment AEAD tag 校验并安全释放对应明文。
4. 全部 segment 接收完毕后，按 `media-and-blob.md` §3.3.5 对全部 segment 密文（每段含其 AEAD tag）按 `segment_index` 升序拼接重算 digest，与 `blob_ref` 内嵌值比对。

Expected：

- 逐段 AEAD tag 校验全部通过，整体 digest 重算等于 `blob_ref` 内嵌值；接收方还原出 byte-for-byte 等于原明文的内容，并仅在见到合法末段（`last_segment_flag=0x01` 且 `segment_index==N-1`）后才标记附件完整。
- per-segment 增量校验提供边下边验，content-addressed `blob_ref` 提供整体完整性；二者都 MUST 校验通过才允许最终持久化 / 标记完整。
- Event ref 与 proof hash 必须派生相同 winning epoch 并通过；无法解析、解析到非 winning state 时在密钥派生前以 `attachment_group_state_unresolved` 拒绝，解析到另一 epoch 时因 AAD 不同而 tag 校验失败。旧 wire `epoch` 成员必须按 closed schema 拒绝。
- 反例（顺带覆盖）：将任一 segment 密文整体替换为另一份相同 segment_index 的合法密文，使 per-segment tag 仍可能通过但拼接后整体 digest 不符时，`media-and-blob.md` §3.3.6 步骤 7 MUST 以 `digest_mismatch`（与该文 §5 一致）拒绝、丢弃全部明文、不渲染不持久化。

### 16.2 Vector: Streaming AEAD Truncation Rejected

`vector_id`: `ak.vector.blob.stream_aead_truncation_rejected.v1`

本向量固化 `media-and-blob.md` §3.3.6 步骤 4「缺末段拒绝」MUST：流在未出现合法末段时即终止（连接中断，或派生的 `N` 段已耗尽但末段 flag 仍为 `0x00`）MUST 拒绝（`segment_stream_truncated`），并丢弃已释放 / 缓冲明文，不得把已得明文当作完整文件。

Steps：

- **Case A — 丢弃末段 / 末段 flag 仍为 0x00**：发送 `N - 1` 段后流终止，从未出现 `last_segment_flag = 0x01` 的合法末段（或最后到达段的 flag 仍为 `0x00`）。
- **Case B — `N` 段耗尽但无末段**：恰好接收从 descriptor 派生的 `N` 段，但其中无任何段的 `last_segment_flag = 0x01`。

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
- **Case B — 形态字段混用**：单个 envelope 同时携带整文件形态字段 `nonce` 与分块形态字段 `nonce_prefix` / `segment_bytes`，违反 `encrypted_attachment` 的 `oneOf`。

Expected：

- **Case A**：接收方 MUST fail closed，返回 `unsupported_attachment_scheme`，MUST NOT 回退到 `ak.blob.whole_file_aead.v1` 或任何其它形态尝试解密。
- **Case B**：schema 校验 MUST 失败（`oneOf` 两个分支互斥，同时含 `nonce` 与 `nonce_prefix` / `segment_*` 不命中任一分支）；接收方 MUST 拒绝该 envelope，不得择一形态解释。
- 对照：缺省 `scheme` 时 MUST 按 `ak.blob.whole_file_aead.v1`（整文件形态、单 `nonce`）解释（§3.2 current default rule），不属于本反例。

### 16.5 Vector: Streaming AEAD Declared Bounds Rejected

`vector_id`: `ak.vector.blob.stream_aead_bounds_rejected.v1`

本向量固化 [scalability-constraints.md](./scalability-constraints.md) §6 的 segment 上限 MUST：`segment_bytes` ∈ [1 KiB（1,024）, 8 MiB（8,388,608）]，且由 `size_bytes` 与 `segment_bytes` 派生的 `N` ≤ 2^20（1,048,576）；越界 descriptor MUST 在密钥派生 / 任何 segment 下载开始之前 reject / fail closed。runner 只依据 descriptor 数值判定，MUST NOT 真实构造对应体量的明文或密文。

Steps：

- **Case A — 派生段数超上限**：envelope 声明 `segment_bytes = 262144`、`size_bytes = 274878169088`，由此派生 `N = 1048577`（2^20 + 1）。
- **Case B1 — `segment_bytes` 低于下限**：envelope 声明 `segment_bytes = 1023`（< 1 KiB）。
- **Case B2 — `segment_bytes` 高于上限**：envelope 声明 `segment_bytes = 8388609`（> 8 MiB）。

Expected：

- **Case A / B1 / B2**：MUST reject（`schema_violation`，`reason_code=segment_bounds_invalid`）；Case B1 / B2 亦不满足 [`blob.schema.json#/$defs/encrypted_attachment`](../../artifacts/schemas/blob.schema.json) 已声明的 `segment_bytes` `minimum` / `maximum`。
- **Case C**：接收方 MUST fail closed（`schema_violation`，`reason_code=segment_bounds_invalid`）；不得先按声明值开始下载再在流中途发现不符。
- 全部 case 中接收方 MUST NOT 依据未经校验的声明值预分配缓冲区、下载计划或段索引表；拒绝 MUST 发生在密钥派生与首段获取之前。

## 17. Last-Resort KeyPackage Vectors

本节收拢可选 last-resort KeyPackage 语义的 conformance 向量，固化 [`encryption-and-audit.md`](../crypto-media/encryption-and-audit.md) §2.6.2 的复用 / 幂等 consume / 强制轮换 / Realm affinity / 可选协商 MUST。该能力由 feature `ak.feature.mls_last_resort_keypackage.v1` 门控（server describe `supported_features`）。每个 `vector_id` 均为规范性引用目标，登记于 [`vector-registry.json`](../../artifacts/registry/vector-registry.json)。

### 17.1 Vector: Last-Resort Claim And Reuse

`vector_id`: `ak.vector.keypackage.last_resort_claim_and_reuse.v1`

本向量固化 §2.6.2 的优先序、复用与幂等 consume MUST：池中存在普通包时 claim MUST 优先返回普通包，仅普通包池空时 MAY 返回 `last_resort=true` 包；last-resort 包 MUST NOT 进入单次 `claimed` / `consumed` 状态，而是始终保持 `published`，每次领取以独立 `keypackage_claim_record` 表达；`ak.keys.keypackages.consume` 对 last-resort `keypackage_ref` MUST 被识别为幂等（返回成功但不改 `published`，不得返回 `keypackage_already_consumed`）；每次消费 MUST 追加 claim audit record，不得伪造 KeyPackage FSM transition。

Steps（前置：服务端在 `ak.server.read.describe.v1.supported_features` 声明 `ak.feature.mls_last_resort_keypackage.v1`，目标 Realm policy 允许 last-resort join）：

1. 该 Realm 的普通（单次）KeyPackage 池耗尽；requester 发起 claim。
2. 同一 `intended_realm_id` 内对该 last-resort 包发起多次 Welcome（多次 claim / consume）。
3. 检查每次消费后的审计链。

Expected：

- 普通包池空后，claim 响应 MAY 返回 last-resort 包，且对应 `keypackage_claim_record` MUST 置 `last_resort=true`，使 requester 与 holder 都能识别本次走 last-resort 路径。
- 同一 `intended_realm_id` 内该包可被多次 Welcome 复用；`ak.keys.keypackages.consume` 对其调用 MUST 幂等（返回成功、状态保持 `published`、不移出池、MUST NOT 返回 `keypackage_already_consumed`）。
- §2.6 / §2.6.1 其余校验（`keypackage_digest` / `capabilities_digest` / `device_authorize_event_id` 匹配、`claim_envelope` 签名、Realm 反向 resolve）对 last-resort 包仍全部适用，放宽的只有单次性。
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
- **Case B — 未声明 feature 池空 fail-closed**：未在 `ak.server.read.describe.v1.supported_features` 声明 `ak.feature.mls_last_resort_keypackage.v1` 的服务端，其某 Realm 普通包池耗尽；requester claim，并显式请求 last-resort 回退。
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

### 18.2 Vector: SessionGrant Requires RFC 9449 DPoP Scheme

`vector_id`: `ak.vector.session.bare_bearer_rejected_protected.v1`

本向量固化 RFC 9449 §7.1：`ak.session.grant` 的 Authorization scheme 唯一为 `DPoP`，必须同时携带匹配 proof。Bearer 不是可以靠旁边再加 proof 修复的别名。高安全 profile 在合法 DPoP presentation 上再叠加 RFC 9421 HTTP Message Signature。

Steps：

- **Case A**：`Authorization: DPoP <grant>` + matching DPoP proof，`ath` / `htu` / `htm` 均正确。
- **Case B**：`Authorization: Bearer <grant>`，同时携带与 Case A 相同的合法 DPoP proof。
- **Case C**：DPoP scheme 但缺 proof、错误 `ath`、或同时发送两个 Authorization method。
- **Case D**：高安全 profile 使用合法 Case A，但缺 required RFC 9421 signature。

Expected：

- **Case A**：默认 profile 认证成功后继续普通授权判定。
- **Case B/C**：MUST 以 `unauthenticated` / RFC 9449 `invalid_request` 对应协议错误拒绝，零业务副作用。
- **Case D**：因 profile 额外 PoP 缺失拒绝，但不得据此把 Bearer 当 fallback。

### 18.3 Vector: DPoP Target URI Binding

`vector_id`: `ak.vector.session.dpop_target_uri_binding.v1`

本向量固化 DPoP `htu` 的完整外部 URI 绑定。校验时只移除 query 与 fragment，scheme、authority 与 path 均参与比较：相同 path 的不同 authority、HTTP/HTTPS scheme 淆混、来自非受信 peer 的 `Forwarded` / `X-Forwarded-*`、以及无法重建 authority 的请求都 MUST 以 `unauthenticated` 拒绝。只有静态配置的 public origin，或由受信最后一跳代理在入口清洗同名客户端 header 后提供的 external URI，才可用于匹配；不存在 path-only fallback。

### 18.4 Vector: Session / Device Identity Key Separation

`vector_id`: `ak.vector.session.device_identity_key_separation.v1`

本向量固化 grant-binding session key 与长期 device identity key 的材料分离。DPoP 与 RFC 9421 可以共享同一短期 session key；但其 key bytes、公钥 fingerprint、JWK thumbprint 或 `kid` 任一与 `device_public_key_did` 对应材料相同都必须 fail closed，不能以“生命周期逻辑分开”替代密码学 key separation。

## 19. Applet Transaction Push Vectors

本节收拢 Applet inbound transaction push 的投递认证记录与 replay 绑定向量，固化 [`applet-integration.md`](../extensions/applet-integration.md) §7.3.1、[`applet-schema.md`](../extensions/applet-schema.md) §3、[`service-http-binding.md`](../sync/service-http-binding.md) §2.2 的 service-to-service HTTP Message Signature 要求。每个 `vector_id` 均为规范性引用目标，登记于 [`vector-registry.json`](../../artifacts/registry/vector-registry.json)。

### 19.1 Vector: Transaction Delivery Authentication Record

`vector_id`: `ak.vector.applet.transaction_delivery_authentication_record_digest.v1`

本向量固化 applet transaction push 的逐次来源签名与幂等 replay MUST：`ak.edge.applet.command.transaction.v1` 在 node→Applet 与 app/bridge→arkret inbound 两个方向都 MUST 携带 RFC 9421 HTTP Message Signature，covered components 至少包含 `@method`、`@target-uri`、`@authority`、`content-digest`、`source-service-id`、`destination-service-id`、`idempotency-key`，签名参数含 `created` / `expires` 并满足 300s replay window；接收方 MUST 形成并持久化 closed `delivery_authentication_record` 及其 domain-separated digest，幂等 identity 绑定 `operation_id`、方向、source/destination service `did_core_id` 与 `Idempotency-Key`，缓存记录绑定 canonical body digest 与 receiver 重算的 authentication-record digest。来源 service 签名不替代每条 Event 的 actor / applet / capability 校验。

Steps：

- **Case A — 合法 app/bridge→arkret inbound**：已安装 Applet registration `service_id=ak:did_core:webvh:z6mkfixtureBridge`，其已验证 `did=did:webvh:z6mkfixtureBridge:bridge.example`，`registration_epoch=sha256:<R>`，`webhook_auth.key_ref=did:webvh:z6mkfixtureBridge:bridge.example#tx-1`，install active。Applet 提交 `POST /_arkret/edge/applet/transactions`，body exact bytes 是 Arkret canonical JSON、`Content-Encoding` absent，header `Source-Service-ID=ak:did_core:webvh:z6mkfixtureBridge`、`Destination-Service-ID=ak:did_core:webvh:z6mkfixturePrincipal`、`Idempotency-Key=tx-001`、`Content-Digest=sha-256=:...:` 且覆盖 exact body bytes；`Signature-Input` 覆盖 required components，`keyid=did:webvh:z6mkfixtureBridge:bridge.example#tx-1`，`created` / `expires` 在窗口内；接收方验证 `project(bare(keyid)) == Source-Service-ID == registration.service_id`，body `source_id` 与 header 一致，`events[]` 中的 `applet_id`、`authorization_ref`、`proofs[]` 与 actor namespace / capability grant 均有效。
- **Case B — 缺签名 / 纯 bearer**：同一 body 只携带 `Authorization: Bearer` 或完全缺少 `Signature` / `Signature-Input`。
- **Case C — transcript / source / content 混淆**：签名覆盖的 `source-service-id`、header `Source-Service-ID` 或 body `source_id` 三者任一不同；或 `Destination-Service-ID` 不等于实际接收服务；或 `Content-Digest` 与 exact body bytes 不一致；或 body 是语义等价但非 canonical 的 JSON wire；或使用 `sha256=:` alias、trailer-only `Content-Digest` / `Content-Encoding`。对非 canonical wire、alias、trailer 与 content-coding mutation，sender MUST 重算适用的 digest 并用有效 Applet service key 重新签名，使 receiver 必须由相应 profile 规则而非偶然 signature mismatch 拒绝。
- **Case D — idempotency replay**：重复 Case A 的相同 headers/body，并从 verified inputs 重算相同 `delivery_authentication_record_digest`；随后再次使用同一 `(operation_id, direction, Source-Service-ID, Destination-Service-ID, Idempotency-Key)`，但改变 body digest、verification method / key digest、`registration_epoch` 或 actor namespace。caller 携带预算 record / digest 的请求必须 schema-invalid，不能覆盖 receiver 派生值。
- **Case E — 无 active install / actor namespace 混淆**：`Source-Service-ID` 可验签但没有 active effective install，或 `events[]` 中 actor / `executed_by` 不属于该 Applet registration 的 service / bot / ghost actor namespace，或 `authorization_ref` 指向另一 Applet 的 grant。

Expected：

- **Case A**：MUST 接受或按事件级规则返回 partial outcome，并持久化 closed `delivery_authentication_record`（绑定 operation、方向、source/destination、signature label、verification method / key digest / algorithm、registration epoch、idempotency key、content digest、ordered covered components、`created` / `expires`）、按 `ak.applet.delivery-authentication-record.v1` 重算的 digest 与幂等 outcome。
- **Case B**：MUST fail closed，HTTP 401，code=`http_signature_required`；纯 bearer 不满足 transaction push 的 service-to-service 来源认证。
- **Case C**：MUST 在处理任何 Event / 副作用前 fail closed，code=`http_signature_invalid`；`Content-Digest` MUST 在 JSON 业务解析与验签前对 exact bytes 重算，header placement 与 wire canonical equality MUST 独立校验，source/destination service `did_core_id` mismatch 或 verification-method controller 投影不一致不得进入业务逻辑。parse-then-canonicalize、`sha256=:` alias、trailer-only digest 或 content coding 均不得通过。
- **Case D**：完全相同的 replay MUST 重算出相同 record digest，返回原 outcome 或等价成功且不得重复副作用；同一幂等 identity 但 body digest 或重算后的 `delivery_authentication_record_digest` 不一致时 MUST fail closed，认证已通过时 code=`duplicate_conflict`，认证未通过时优先返回 §7.3.1 的对应认证失败 code。
- **Case E**：无 active install MUST fail closed，code=`applet_registration_unauthorized`；actor / namespace / grant 混淆 MUST fail closed（`applet_namespace_mismatch`、`capability_denied` 或 `applet_registration_unauthorized`），不得把来源 service 签名当成 native actor 授权。

### 19.2 Vector: Applet-managed Actor Authority

`vector_id`: `ak.vector.applet.managed_actor_authority.v1`

Runner MUST 执行 [`applet-managed-actor-fixture.json`](../../artifacts/fixtures/applet-managed-actor-fixture.json) 的固定 Bot/Ghost 原子单元，验证 exact authority pair、receiving Station、独立 method history/witness、verified DID namespace、provision/PCR initial-resolution 交叉绑定与零可见失败。Rotation 只改 PCR current cell 而保持 creation anchors；Applet/Ghost revoke 后，通过普通 Event submit 的 self-signed write 也必须 `applet_revoked`，但历史 resolution/audit 仍可读。

### 19.3 Vector: Registration Epoch Transcript

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

`ak.vector.mls_exporter_aead.content_key_derivation.v1` 固定 `exporter_secret` 与 `realm_id`，分别以 ordinary verified canonical `device_id` UTF-8 bytes 和 minimal-metadata exact LeafNode basic credential identity bytes 作为 `ak.content-v1` context，逐字节比较 `history_secret`、完整 KDFLabel info 与 `K_content[N,sender]`。错误 label、空 Realm exporter context、空/未验证/种类不匹配 sender domain、跨 sender 或 epoch 复用内容键均 MUST 与金值不同或在加密前 fail closed。

`ak.vector.mls_exporter_aead.seal_open_transcript.v1` 固定最小 wire envelope、outer signed Event、exact group state、verified sender domain、重构的 `pre_encryption_header`、counter-derived nonce、plaintext 与 AES-128-GCM 输出，逐字节比较 `aead_aad_canonical_json` 和含 tag 的 ciphertext。Wire 不含 header、scheme、scope、group、sender domain、nonce、Event kind 或 routing window；修改 envelope version/content type、outer kind/scope、producer verification method、group state/scheme、counter 或 authentication tag 均 MUST 在 admission/open 时拒绝。runner MUST 从三份规范输入重构 JCS bytes，不得直接把 fixture 的 canonical JSON 字符串当作可信 AAD 输入。

### 21.2 Signal 与 full-width counter nonce KAT

`ak.vector.signal.exporter_key_kat.v1` 固定 exporter secret、Realm context、sender device 与 active MLS ciphersuite，逐字节比较 `history_secret`、`ak.signal-v1` + `JCS({sender_device_id})` 的完整 KDFLabel info 与 16-byte per-sender Signal AEAD key。runner MUST 再以 collision peer device 派生第二把不同 key，并验证即使强制输入相同 12-byte nonce 也不属于同 raw AEAD key/nonce domain；错误 label、空第二级 context、修改 sender device 或跨 epoch 复用均 MUST fail closed。

`ak.vector.aead.full_width_counter_nonce.v1` 固定 `counter = 7`、`AEAD.Nn = 12`，逐字节比较
`I2OSP(counter, AEAD.Nn) = 000000000000000000000007`。Runner MUST 拒绝 non-zero high-order padding、同
`(mls_group_id, epoch, sender_domain, counter)` 下不同 ciphertext、counter rollback 与 `u64::MAX` 后继续发送；不得派生或接受 sender nonce prefix，也不得 random fallback。

### 21.3 Reaction routing HMAC

`ak.vector.reaction.routing_hmac_kat.v1` 固定 replay-derived `routing_root`、`effective_scope`、`target_ref`、`routing_window` 与 ExpandWithLabel label，要求分解形式 `U+0065 U+0301` 与预组形式 `U+00E9` 经 NFC 后产生完全相同的 tag，并覆盖 emoji modifier。跳过 NFC、错误 label、改变 scope / target / window，或跨 epoch 复用 routing root MUST fail closed。

## 22. Identity Root、Delegated Bootstrap 与 Recovery Re-anchor 向量

本节由 [`identity-recovery-kdf-fixture.json`](../../artifacts/fixtures/identity-recovery-kdf-fixture.json)、[`identity-root-anchor-fixture.json`](../../artifacts/fixtures/identity-root-anchor-fixture.json) 与 [`did-webvh-v1-fixture.json`](../../artifacts/fixtures/did-webvh-v1-fixture.json) 承载。runner MUST 实际执行密码学派生、DID history 验证、原子 admission 与 reducer 状态转换；只检查字段存在、直接信任 fixture 的中间值或用 first-seen 选择分叉均不算通过。

### 22.1 Recovery-secret KDF KAT

`ak.vector.identity.recovery_kdf.v1` 固定 BIP-39 24 词 + passphrase 与 32-byte raw secret 两条输入路径。实现 MUST 逐字节重算 HKDF PRK、`root_seed_0/1`、`recovery_proof_seed`、`backup_hpke_ikm`、Ed25519 raw public keys 与 multikey、RFC 9180 `DHKEM(X25519, HKDF-SHA256).DeriveKeyPair` 的 raw `derived_sk`、clamped serialized private key 与 public key，以及 `Base58BTC(multihash(sha2-256, UTF8(root_1_multikey)))` canonical `nextKeyHash`。fixture 中 raw-public-key SHA-256 只作为诊断值，不得写入 did:webvh `nextKeyHashes`。任何 salt/info 字节、`u64be(i)`、multicodec/multihash 编码、输入文本化、raw/clamped private-key 表示混淆或 Ed25519→X25519 key reuse 漂移都必须失败。

`ak.vector.identity.recovery_key_role_separation.v1` 固定 recovery policy 的跨数组语义：`recovery_keys[]` 的 recovery-proof signing entry 必须用唯一 `key_agreement_ref` 配对同一 accepted policy 的一个 active `recovery_key_agreements[]` backup-HPKE entry；proof verification 只能使用前者，所有 `recovery_public_key` envelope 的 signed `recovery_policy_ref` / `recipient_key_ref` / `hpke_suite` 只能解析到后者。悬空或重复 ref、撤销/过期 entry、签名与 HPKE 复用 material、suite 不匹配、把 signing ref 当 recipient、或只在 DID Document 声明而未进入 session/envelope referenced policy 均 MUST reject。

### 22.2 Root-anchor 排他性

`ak.vector.identity.root_anchor_exclusivity.v1` 只允许 identity root 为自体 principal 的第一条 PCR `ak.realm.create`（唯一 critical `did_inception`）和 B 模型 `ak.device.reanchor` 启用 Event root-anchor 验签。原子 bootstrap 必须是 `[ak.realm.create, ak.device.authorize]` 且以 entry 0 delegation 验第二条；拆批、第二 PCR genesis、非 PCR Realm、actor/realm/DID 不匹配、缺失或非 critical ref、root 签任何普通 Event 均 fail closed。Agent PCR 不进入此路径。

### 22.3 Re-anchor、generation fence 与冲突

`ak.vector.identity.device_reanchor.v1` 同时覆盖零 Seal 与完整 accepted Seal frontier 两个正向入口、`payload digest → re-anchor → authorize` 单向依赖链的无环双签构造（[`../identity/key-management.md` §5.0.3](../identity/key-management.md)）、byte-identical 幂等重试和 accepted-at receipt 历史复验。负向必须覆盖 A 模型混入、live non-head、伪造 previous generation、过旧/不完整/CAS 失配 frontier、replacement authorize payload digest 不符、authorize `prev_refs` 不恰为 `[reanchor event_id]`、拆批、spent root、post-fence 旧 generation Event/Seal，以及首个新 generation Seal 的 predecessor/delta 不匹配。

同 `(principal_id,did_version_number)` 的不同 versionId/digest 或同 entry 的不同 re-anchor unit 必须把全集置于 quarantine 并令 `device_generation_status="conflicted"`；不同到达顺序得到相同结果，禁止 first-seen winner。conflicted 期间普通 admission fail closed；只有下一预承诺 authority 的有效 resolution entry + re-anchor unit 可恢复 `active`。

### 22.4 Recovery-secret 泄露 handoff

`ak.vector.identity.recovery_secret_handoff.v1` 要求：没有预先存在的独立 guardian/witness/组织权威时，旧秘密泄露后的 same-DID 原地 handoff 必须拒绝并重铸 DID；存在独立权威时，只接受带 durable checkpoint 的两-entry 分阶段 handoff，并在 re-anchor、新 recovery policy、全部旧 backup-HPKE active envelope 新 series 重封装与 active-series pointer 推进完成后，最后撤销旧 policy key。runner MUST 覆盖任一阶段崩溃后的幂等续跑。

### 22.5 外部 Organization DID registration

`ak.vector.identity.organization_registration.v1` 由 [`organization-registration-fixture.json`](../../artifacts/fixtures/organization-registration-fixture.json) 承载，覆盖 [`identity-did.md` §8.4](../identity/identity-did.md)。

正向：合法 challenge；`resolved_verification_method` 与 `governance_quorum` 两个分支的 ensure；含闭合 claims 的 receipt。

负向 MUST 全部拒绝：

- `resolved_verification_method` 分支携带 `quorum_threshold`，或 `governance_quorum` 分支缺 `quorum_threshold` → `schema_violation`。discriminator 双向封闭，否则接收方无法判断"一个签名够用"还是"承诺两个只交了一个"；
- receipt 缺 `expires_at` → `schema_violation`。无界 receipt 会让一次首验永久授权该组织关系，refresh 也就失去存在理由；
- `requested_scopes` 含闭合集合外的值 → `unsupported_organization_registration_scope`；
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

**Arkret 层**：`ak.schema.did_webvh_witness_receipt.v1` 与 `ak.schema.identity_receipt.v1` 是两个不同对象族，经 `ak.root.identity.receipts.read.list.v1` 以 `schema` 常量为 discriminator 的 tagged union 返回。runner MUST 验证：两族可在同一响应中共存并被正确分支；receipt 缺 `expires_at` 或 `controlling_organization_did` MUST 被拒（前者会让缓存记录退化为永久断言，后者使该 receipt 无法计入 distinct-organization）；`witness_did` 非 `did:key` MUST 被拒；receipt 携带 `max_age_seconds` 等 policy 字段 MUST 被拒——receipt 记录观测，不承载 policy，否则新鲜度门槛会落回被审对象手中。

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

### 23.1 Canonical Event presentation order

`vector_id`: `ak.vector.encoding.canonical_event_tie_break.v1`

覆盖 [`encoding.md` 4.2](./encoding.md) 的 producer-biased 展示与序列化顺序；历史 vector id 保留，但不再产生语义 winner。

Steps:

1. 构造并发候选集与同一 `(cell, actor_id, issuer_seq)` 的合法 sibling set。
2. 对每个候选计算 `canonical_digest(envelope_without_proofs_unsigned_actor_kind_event_id)`。
3. 解码 typed digest 的 hex 为 octets，按 unsigned lexicographic order 升序序列化全部候选。

Expected:

- 全部候选保留且没有 winner；octets 完全相同而 suite 不同时以 canonical suite id 的 UTF-8 bytewise 顺序作第二键。
- 必须包含一条 suite 前缀字符串顺序与 decoded octets 顺序**相反**的 case：按整串 UTF-8 比较会得到错误序列。
- fixture 明示攻击者击败已知随机 digest 的期望尝试数约为 2，并断言该顺序不得进入授权、finality、Relation active edge、account status 或 `state_root` 成员资格选择。
- digest preimage MUST 逐字使用移除 `proofs` / `unsigned` / reducer stamp `actor_kind` 后的 canonical bytes，并保留签名 `scope_ref`；沿用移除 scope 的旧算法 MUST 失败。
- 仅 `proofs` 或 reducer stamps 不同、canonical preimage 逐字相同的两个输入 MUST NOT 被报成 collision。
- 同 typed digest（同 suite、同 octets）但 canonical preimage 不同 MUST fail closed，MUST NOT 回退到 `event_id` / HLC / `created_at` / 到达顺序 / 实现私有 ID。
- producer 在 Event DAG 中加入因果资料不得把任一已接受 sibling 变成 loser。

### 23.2 `ak.realm.create` reducer projection 闭包与 genesis `state_root`

`vector_id`: `ak.vector.event_kind.realm_create_projection_closure.v1`

Steps:

1. 提交普通 Realm 的完整 bootstrap unit：按 [`realm-and-space.md`](../models/realm-and-space.md) §2.5 登记顺序包含 create、profile、policy、admission/history、条件 facet 与 creator membership；v1 无 founding grant 槽位。
2. 两个独立实现各自按 `contract-registry.json` 的 `ak.realm.create` `cell_writes[]` 派生并应用 reducer projection，再重算 genesis Seal 的治理 `state_root`。

Expected:

- create Event 的 reducer 输出 MUST 恰好含五条无条件写入：`ak.component.realm.genesis.v1:null`（`set`）、`ak.component.realm.create.v1:null`（`append`，`issuer_seq=0`）、`ak.component.notary.v1:null`（`set`）、`ak.component.realm.reducer_profile.v1:null`（`set`）、`ak.component.realm.authority_root.v1:null`（`set`，controller 由 envelope `actor_id` 派生）；另有五条 registered condition row：`initial_resolution`、`agent_control` Agent status、以及由 `payload.object.purpose` 互斥命中的 `direct_conversation|principal_control|agent_control` history-access `null→since_join`。少一条、漏掉命中的条件写入、命中多个 purpose history row，或出现这五条注册条件之外的 create 写入，都表示 registry/vector drift，门禁 MUST 失败。
- 两个实现的 genesis `state_root` MUST 逐字节相同（KAT）。
- creator membership 必须来自 bootstrap unit 末尾的显式 `ak.member.state{join}`，其 cell MUST 有 inclusion proof；create reducer 自行隐式写 membership 视为额外未登记投影。
- `ak.component.realm.genesis.v1`、`ak.component.realm.profile.v1` 与所有 required bootstrap facet MUST 在 genesis Seal 即出现在 leaf 集合中；事后补写视为不合规（负例）。
- PCR 与 Direct Conversation 两条 bootstrap 分支使用同一 create projection 集合；两者与其它 Realm 一样 MUST 携带 `genesis_salt`，PCR 分支的差别只在 `founding_device_descriptor` 的取舍。
- 负例：实现漏执行任一已登记 write 后重算 `state_root`，MUST 与正例不同并被 `apply_seal` step 11 拒为 `rejected_seal`。

### 23.3 Null cell subject 的 wire 形态与 leaf 顺序

`vector_id`: `ak.vector.event_kind.null_cell_subject_wire_form.v1`

Steps:

1. 对同一组 Realm policy facet Control Move，由两个实现各自派生 cell wire id 并计算 `state_root` leaf 序列。

Expected:

- 每个 `cell_subject: null` family 的 wire subject 段 MUST 逐字节等于字面 ASCII `null`。
- 两个实现 MUST 得到逐字节相同的 leaf 序列与 `state_root`。
- 负例：把 `realm_id`、Realm 角色分类（`collaboration` / `principal_control` / `agent_principal_control`）或任何 payload 派生值写进 subject 段；空末段（`ak:cell:<family>:`）；这些形态 MUST `schema_violation`。

### 23.4 Invite lifecycle 与 acceptance membership 的精确写集

`vector_id`: `ak.vector.invite.membership_transition_atomicity.v1`

Steps:

1. `default_join_rule=invite` 的 Realm 上走完整 create 到 accept 链路。
2. 分别执行 cancel（invitee 拒绝）、revoke、以及以 `reason_code` 表达 expired 的 revoke。
3. 对照 `ak.fsm.membership.v1` 与 event kind registry 检查每类 Move 的精确 cell write family。

Expected:

- 正例：create 原子写 `invite.lifecycle: null -> pending` 与 `invite.live_target` 占格，目标 member 保持 `leave`；accept 在同一 Control Move 原子写 `invite.lifecycle -> accepted`、member `leave -> join` 与 `invite.live_target` 释放。
- 负例：没有 `pending` / `claimed` invite 前态、actor 不是 exact invitee，或 member 前态不是 `leave` 的 accept MUST fail closed 且零写。
- 正例：cancel / revoke / expired revoke 不写 member cell（保持逐字节不变，不得合成 `leave` write），只推进 `invite.lifecycle` 并按 §23.4.1 的规则释放或保留 `invite.live_target`。
- 负例：direct invite cancel 缺失 `payload.invitee_account_id`，或其值与 invite cell 记录不等，MUST `reducer_projection_failed`；token / 3PID invite 的 cancel MUST `invite_kind_requires_revoke`。
- 正例：3PID create / revoke 不投影 `member.state`；claim 只产生 subject-bound membership proposal，后续 accept 才写 member `leave -> join`。
- 正例：membership FSM 状态集不含 `invite`，且 direct `leave -> ban` 按 membership FSM 独立合法；实现不得创造 invite member prestate 或要求先合成一次 `leave`。

#### 23.4.1 Direct invite 的 live-target slot 唯一性

`vector_id`: `ak.vector.invite.live_target_uniqueness.v1`

Steps:

1. 同一 Realm 内对同一 `invitee_account_id` 顺序提交两条不同的、各自 schema-valid 的 `ak.invite.create`。
2. 在同一 CBA basis 上并发提交两条 `ak.invite.create`，目标同一 `invitee_account_id`。
3. 让第一条 invite 进入终态（`ak.invite.cancel` 或 `ak.invite.revoke`），随后重新邀请同一账号。
4. 让一条 invite 到达 `expires_at` 但不提交任何 Move，再提交一条新的 create。
5. 让一条 direct invite 进入 `send_failed`，随后分别尝试直接重发 create、以及先 revoke 再 create。
6. 对一条 3PID invite 提交携带伪造 `payload.invitee_account_id` 的 `ak.invite.revoke`；对一条 direct invite 提交省略该字段的终态 `ak.invite.revoke`。
7. 用 `ak:invite:` 拼写而非 `ak:event:` 拼写构造释放 Move 的 `head_eq` 值。

Expected:

- 正例：`ak.invite.create` 携带 `ak.component.invite.live_target.v1` 的 `head_eq: null`，原子写 lifecycle 与 slot；slot subject 是 `canonical_json(payload.invitee_account_id)` 的单分量 composite，**不含 `realm_id`**。
- 负例：第 1 步的第二条 create MUST `failed_precondition` + `reason_code="invite_live_target_occupied"`，不进 canonical history、零 cell write、零投影、零通知；`error.details` 严格通过 [`service-operation-dtos.schema.json#/$defs/InviteLiveTargetOccupiedProblem`](../../artifacts/schemas/service-operation-dtos.schema.json)，即只含 `reason_code` / `invite_id` / `create_event_id`。MUST NOT 返回 `cas_conflict`，MUST NOT 作为幂等成功返回既有 `invite_id`。
- 正例：第 2 步的两条并发 create 争用同一个 cell，恰好一条获胜，结果由 CBA basis 唯一确定，与任何实现私有唯一索引或数据库插入先后无关。
- 正例：第 3 步的重新邀请被接受（终态 Move 已释放格子）。释放写是 `set null`；新 create 的 `head_eq: null` 再次成立，同时 Seal 准入按 §6.3 step 8b 要求它的基线 heads 等于释放写的身份——**一条基线停留在更早那次空格上的 create MUST 被拒**，即使两次的业务值同为 `null`。
- 负例：第 4 步的新 create 仍 MUST `invite_live_target_occupied`——`expires_at` 到达不释放格子，只有已登记的 `ak.invite.revoke(target_state="expired")` 才释放。
- 负例：第 5 步直接重发 create MUST `invite_live_target_occupied`；先 `ak.invite.revoke(target_state="revoked")` 再 create MUST 被接受。`send_failed` 分支的 `ak.invite.revoke` payload MUST NOT 携带 `invitee_account_id`（schema `if/then`），因而不派生 slot 释放写。
- 负例：第 6 步两种形态 MUST 都以 `failed_precondition` + `reducer_projection_failed` 原子拒绝（`stored_field_matches_payload` 的两个方向）。前者保证 3PID invite 不能释放别人的 direct slot，后者保证 direct invite 不能靠省略字段把格子永久占住。
- 负例：第 7 步 MUST `failed_precondition`——slot value 逐字是 `ak:event:` 形态的 `create_event_id`。

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
3. 对同一输入分别经 invite delivery、contact delivery 与 `ak.self.consent.command.request.v1` 三条通道观测。

Expected:

- 五种情形的响应体与状态码 MUST 逐字节相同，timing 差 ≤ 50ms。
- quarantine MUST 表示为 `status="deferred"` 且不携带 `disclosed_outcome`。
- 负例：响应携带 `disclosed_outcome="quarantined"` 视为不合规；该值不在枚举内。
- 三条通道的可观察量 MUST 互不能用于区分 quarantine 与拒绝。
- **carrier 分叉（正例）**：invite delivery 与 consent request 各自写入一条 holder quarantine entry，
  `surface_kind` 分别为 `invite_delivery` / `consent_request`；contact delivery 写入的是 Contact
  `pending_incoming` head，holder quarantine **零 entry**。三者对 requester 仍逐字节不可区分。
- 负例：consent request 的 entry 携带 `invite_event_id` / `introduction_kind` / `effective_kind` /
  `trust_tier` / `request_digest` / `idempotency_key_digest` 任一字段，或其 `consent_scope="invite"`；
  invite delivery 的 entry 缺少上述任一字段，或其 `consent_scope` 不是 `invite`；出现
  `surface_kind="contact_delivery"` 或任何未登记取值——以上 MUST 全部 `schema_violation`。
- 负例：`ak.self.consent.command.request.v1` 通过 chokepoint 后不写任何 entry（把该 operation 当空壳），
  或对同一 `(account_id, source_peer_principal_id, consent_scope)` 在已有 live entry 时再写第二条，
  视为不合规。

### 23.8 Per-holder 新来源 quota 的 holder 视角准入

`vector_id`: `ak.vector.invite.new_source_quota_holder_admission.v1`

本向量固化 [`../identity/consent-model.md` §6.1.1.1–§6.1.1.4](../identity/consent-model.md) 的
admission chokepoint 算法。外部视角按设计不可区分，因此断言全部从 **holder 的
`ak.account.holder_quarantine` cell** 观察。

Steps:

1. 部署声明 `receive_policy_constraints.new_source_quota`，holder 不发布 override（取部署缺省）。
2. 用 `E_w` 个互不相同的新来源 peer 依次投递并被 quarantine，再投递第 `E_w + 1` 个新来源。
3. 短窗滑过 `window_seconds` 后再投递一个新来源。
4. 已被计费过的同一 source 在短窗内重复接触。
5. 在长窗内把 distinct 新来源推到 `E_r`，再投递第 `E_r + 1` 个。
6. 两个不同新来源的首次接触并发到达同一 holder；同一 source 的两条首次接触并发到达。
7. holder 发布 `invite_receive_policy.consent_profile = require_explicit_consent`（其余 policy 不变），用新来源重复第 2 步。

Expected:

- 第 `E_w + 1` 个新来源 MUST 缺席于 quarantine cell，响应仍是同一 opaque `deferred` 且无
  `disclosed_outcome`。
- 短窗滑过后的新来源 MUST 重新被准入。
- 已计费 source 的重复接触 MUST 入列、MUST NOT 再次计费、MUST NOT 刷新其 `first_admitted_at`。
- 第 `E_r + 1` 个 distinct 新来源 MUST 缺席，即使短窗未满。
- 并发交错下准入总数 MUST NOT 超过 effective 上限；同一 source 的两条并发首次接触恰好计费一次，
  两条都不返回可区分错误。
- 负例：把被丢弃的 source 记入 ledger 视为不合规——下一窗口它会被误判为 seen。
- `require_explicit_consent` profile 下每个新来源 MUST 缺席于 quarantine cell、MUST NOT 写入
  seen-source ledger，响应仍是同一 opaque `deferred` 且无 `disclosed_outcome`；该 profile 无
  quarantine 面，quota 空转。负例：该 profile 下出现任何 quarantine entry、ledger 行、
  `failed_precondition` 或任何可区分响应视为不合规。
- 负例：任何分支返回 429、`Retry-After`、`rate_limited` 或缓存的 drop outcome 均视为不合规。
- **contact delivery 计费但不入 quarantine（正例）**：陌生人首次 Contact request 照常消耗一个新来源名额；
  超限时被丢弃的是 Contact `pending_incoming` row 的建立，holder quarantine 始终零 entry
  （[`../identity/contact-and-direct-conversation.md` §1.1](../identity/contact-and-direct-conversation.md)）。
  负例：contact 首次接触不计费，或它在 holder quarantine 里产生 entry，均视为不合规。

### 23.8.1 Effective quota 边界与 holder override

`vector_id`: `ak.vector.invite.new_source_quota_effective_bounds.v1`

Steps:

1. holder 发布高于部署 `max_*` 的 `new_source_quota` override。
2. holder 发布 `new_sources_per_window = 0`、`new_sources_per_retention = 0` 的 override。
3. 部署省略整个 `new_source_quota` 对象，以及只省略其中部分字段。
4. 部署声明 `max_new_sources_per_window < default_new_sources_per_window`，或
   `retention_seconds < window_seconds`。

Expected:

- 超过 `max_*` 的 holder override MUST 被 clamp 到 `max_*`，MUST NOT 放宽超过部署边界。
- `0` override MUST 使所有新来源静默丢弃，quarantine cell 不新增 entry。
- 省略的对象或字段 MUST 取 spec 缺省值（`86400 / 3 / 10 / 2592000 / 30 / 200`），
  MUST NOT 被解释为关闭 quota。
- 违反 `max_* >= default_*` 或 `retention_seconds >= window_seconds` 的 constraints 对象 MUST 整体
  拒绝，MUST NOT 取部分字段继续求值。

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
- 负例：坏 `gate_audience`、旧 `pairing_code`、跨 request 重放、过期窗口外、改 key、坏签名、proof `kid` 与 `new_device_pubkey.kid` 不等、proof 使用已废弃的 `verification_method` 字段名承载 device key id，或 proof transcript 不是 `ak.device-pairing.challenge.v1`，一律 MUST 拒绝。
- 负例：正文旧示例形态 `{kid, alg, public_key}` MUST 被 canonical `PublicKey` schema 拒绝（缺 `kty` / 缺 `key` / 多余 `public_key`）。
- 负例：stage 请求携带 challenge proof MUST `schema_violation`（proof 必须承诺 stage 才铸出的值，因此不可能在 stage 时存在）。
- 负例：`ak.gate.account.command.pair_device.v1` 缺少 `device_pairing_request_id`，或引用未知、过期、已消费、code/key 不匹配的 staged record，MUST fail closed；不得接受客户端提供的替代 challenge transcript。
- 负例：stage/resolve/status 返回或绑定 principal、SessionGrant、sibling device 集合，或未授权新设备调用 `ak.self.device_messages.*`，一律视为不合规。无效与不匹配的 resolve/status credential 保持统一防枚举错误。

`vector_id`: `ak.vector.device_pairing.accepted_device_attestation.v1`

Steps:

1. 在同一次 pairing 中，目标设备按
   [`../crypto-media/device-lifecycle.md` §5.2.2](../crypto-media/device-lifecycle.md) 生成
   `device_pairing_target_attestation`，批准设备与 Account Authority 各自独立重建该封闭对象并验签，
   目标设备再按 [`../crypto-media/device-lifecycle.md` §5.4.1](../crypto-media/device-lifecycle.md)
   在本地装配前核对被接受的 `ak.device.authorize`。
2. 验证 attestation 只经二维码/短链 fragment 到达批准设备，stage 与 resolve 均不返回该对象。

Expected:

- 正例：`accepted_device` 的 `device_signature` 使用 domain `ak.device_authorize_accepted_device_possession_proof.v1`，签名对象恰为 `{algorithms, authorization_binding_kind, device_id, device_key_algorithm, device_public_key_did, hpke_key, pairing_challenge_transcript_digest}`，批准设备与 gate 各自重建后验签通过；gate 不接受任何请求方提供的 attestation 副本。
- 正例：`device_pairing_target_attestation` 只绑定唯一的 staged short-link `pairing_challenge_transcript_digest`，不登记 to-device 配对 transcript 分支。
- 正例：`hpke_key` 与 `algorithms` 只从验签通过的 attestation 取得；stage 请求与 `DevicePairingBootstrap` 都不承载这两个值。
- 负例：attestation 的 `pairing_challenge_transcript_digest` 与本次 pairing 重算得到的 `transcript_digest` 不等 MUST 拒绝，且 MUST 在验签之前拒绝。
- 负例：attestation 的 `hpke_key` 与 `authorize_event.event.payload.hpke_key` 不一致 MUST 拒绝；`algorithms` / `device_public_key_did` / `device_id` 同理。
- 负例：把 `root_anchored` 的 `ak.device_authorize_possession_proof.v1` transcript 用于 `accepted_device`，或把 `accepted_device` attestation 用于 genesis / re-anchor 的第二条 authorize，双向 MUST 拒绝。
- 负例：attestation 的 `device_public_key_did` 与 `new_device_pubkey.key` 解码为不同 key，或 `device_id` 与 `new_device_pubkey.kid` 不等，MUST 拒绝。
- 负例：把 attestation 经免认证 stage / resolve 面回传，或在 `DevicePairingBootstrap` 中镜像 `hpke_key` / `algorithms`，视为不合规。
- 负例（§5.4.1）：被接受 Event 的 `principal_id` 非用户预期，或 `payload.device_signature` 与目标设备产出的 attestation 签名不逐字节相同，目标设备 MUST fail closed——不使用该身份、不安装或请求该 principal 的密钥材料、不发布 KeyPackage，并向用户告警。
- 负例：目标设备在完成 §5.4.1 校验之前就完成本地装配，视为不合规。

### 23.11 RSVP typed composite subject 与 `mv_register` 收敛

`vector_id`: `ak.vector.calendar.rsvp_composite_subject.v1`

Steps:

1. 分别构造 instance RSVP 与 `occurrence=null` 的 series RSVP，从 registry 显式读取 `payload.event_ref`、`payload.occurrence`、`envelope.actor_id`。
2. 对 components array 做 canonical JSON 编码并计算 SHA-256 / base64url-nopad subject。
3. 对同一 responder 构造因果后继与真正并发的不同 status 写入。

Expected:

- instance preimage `["ak:strand:AQN06JbCzCiTJapT_QplYfovK3NG6pdAjNyF23YePDuc","2026-07-26T09:00:00[Asia/Shanghai]","did:webvh:z6mkfixture:alice.example"]` 的 subject MUST 为 `tc2S5LQybi5y3tI-hoyB6HoBWFepT_tDfFcmHJk_jd0`。
- series preimage `["ak:strand:AQN06JbCzCiTJapT_QplYfovK3NG6pdAjNyF23YePDuc",null,"did:webvh:z6mkfixture:alice.example"]` 的 subject MUST 为 `3iBI9bjQLklvfcVhQeaxLajMskSVG4oZ5IMpU62GvRc`；把 JSON null 改写成字符串、空串或 sentinel MUST 失败。
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

plaintext descriptor 还 MUST 覆盖 hash-only `blob_ref`、Blob metadata digest、下载正文重算 digest、声明 size 与闭集 `media_type`（`text/plain` / `text/markdown`）；UUID ref、缺失/未知/带参数的 media type、遗留 `format`、任一 digest/size 不一致都必须拒绝。

### 25.2 规范化、line count 与 fallback

`vector_id`: `ak.vector.content.long_text_normalization.v1`

Runner MUST 覆盖 empty、末尾有/无 LF、多行、CRLF、bare CR、BOM、TAB、禁用 C0/DEL 与 canonical-equivalent 但 scalar sequence 不同的 Unicode 输入。producer 先把 CRLF/CR 归一为 LF，再计算 digest/size/line count；不得 NFC/NFKC 改写。`prefix` 必须从 byte 0 开始并只在 scalar 边界截断；`summary` 可不等于前缀，但 UI 必须标注为摘要且不得与全文拼接。

### 25.3 E2EE stream descriptor

`vector_id`: `ak.vector.content.long_text_e2ee.v1`

Runner MUST 验证 `scheme=ak.blob.stream_aead.v1`、`alg` 为 `_stream` 算法、hash-addressed ciphertext Blob、从 `size_bytes/segment_bytes` 派生段数、逐段 tag、顺序、末段与完整 ciphertext digest。whole-file AEAD、重排、截断、派生边界越界或任一 digest 不符必须 fail closed；全部段验证前不得把正文标记为完整。E2EE descriptor MUST 仅从 `attachment.media_type` 选择正文类型；两种合法媒体类型都必须有正例，缺失/未知/带参数的媒体类型、根级 `media_type` 或 `format` 都必须拒绝。

### 25.4 生命周期闭包

`vector_id`: `ak.vector.content.long_text_lifecycle.v1`

Message redaction、expiry 或 Blob access revoke 必须同步使 fallback、完整正文、partial/full search index、cache 与 Blob authorization 失效；Blob GC 仍按引用追踪。push provider 不得收到全文，mention 通知不得要求服务端扫描 Blob。

## 26. Signal peer relay closure vector

`vector_id`: `ak.vector.signal.peer_relay.v1`

本向量由 [`signal-federation-fixture.json`](../../artifacts/fixtures/signal-federation-fixture.json) 承载，规则正文见 [`../sync/signal.md` §4](../sync/signal.md) 与 [`../sync/federation.md` §4.0.3](../sync/federation.md)。

Runner MUST 覆盖：

1. 原 producer-signed encrypted `SignalEnvelope` 经一个 source → destination peer hop 后，ciphertext、proof 与 envelope digest identity 不变；
2. `signals[]` 127/128/129、canonical request body 1 MiB−1/1 MiB/1 MiB+1、HTTP Message Signature `expires-created` 4,999/5,000/5,001 ms；
3. request `realm_id` 与任一 envelope/scope Realm 不一致、closed proof schema 不合法按 request-level reject；第二 peer hop、source 不托管 sender、destination 不在 active joined-member ActorId routing projection、proof transcript/digest、Seal/TTL/basis 无效按 opaque item drop；
4. 有 eligible local recipient 与无 eligible local recipient 的已认证合法 request 都返回相同 HTTP 204 empty response，且无 count/per-item outcome；
5. response 丢失时 source 不自动重放，不携带 `Idempotency-Key`，按 `drop_unconfirmed` 丢弃不确定结果；
6. peer/live/local rails 重复、乱序或丢失不写 durable Event、不推进 actor sequence / Realm frontier，consumer 依靠下一自足 signal 或产品级 timeout/renegotiation 恢复；
7. source/destination 改写、重签、解密重加密 envelope，以及 destination 再转发第三 peer，全部 fail closed；
8. destination 没有远端设备目录（包括本机恰有同 principal/device 的另一 Station 账号）仍按 peer / outer admission 转交；不得查询或借用该目录；
9. 恶意 source 提交结构正确但无效的 producer signature，destination 可 relay、recipient 必须独立拒绝；不得用 AEAD 成功代替认证；
10. source 短队列期间撤销设备、退群、收紧 action 或过期，出站前 fresh admission 必须阻止发送。

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
4. `message_id` 等于 planned create `event_id` 的完整 token 重类型结果；create payload 出现
   `message_id` 必须 `schema_violation`；
5. direct final 的 actor/device/security scope/Realm/Strand/track 任一不匹配，或 final
   携带 `executed_by` 时，不得绑定 preview；全部匹配时 final 立即替换并终止所有 attempts；
6. preview 永不写 durable Event、Content Block、cursor、replay cache 或 reducer state。

## 28. Agent signer evidence closure vector

`vector_id`: `ak.vector.agent.signer_evidence_binding.v1`

runner MUST 执行 `agent-signer-evidence-fixture.json` 的完整 `binding_vector` 与全部 case：重算
Agent authority snapshot、privacy-minimal controller account gate、key / Agent lifecycle state与transition witness、
current exact request binding、historical destination receipt、outer attestation与全部时窗，并覆盖 active、revoked、
superseded、unresolved、跨verifier重放及字段混拼分支；state witness 正例 MUST 使用
`<event_id>:<write_index>` canonical Event dot，裸 Event id、非 canonical write index 与其它 Event dot
均 MUST 拒绝，revoke 后的 transition witness MUST 来自同一 key cell 中 reducer 写入的 revoke marker。
只加载 fixture、只验证来源服务
签名或跳过任一 case 均不构成通过。

`vector_id`: `ak.vector.agent.historical_evidence_materialization.v1`

同一 fixture 中带该 `vector_id` 的 case 组固化 historical evidence 的 materialization 与长期验证合同，规则正文见
[`../identity/key-management.md` §3.6.1](../identity/key-management.md) 与
[`../sync/federation.md` §4.1.1](../sync/federation.md)。Runner MUST 覆盖：

1. 逻辑唯一键是 selector tuple `(agent_id, verification_method, event_id, receiver_id)`；Event digest 从 suite-bearing `event_id` 解码，不作为第二个 selector 字段。
   同 tuple、同 receipt digest、同 canonical historical root MUST 是 exact replay / no-op；materializer MUST 在
   签发新 outer attestation 前按该 tuple 读既有 root，MUST NOT 先签再靠 digest 主键冲突发现重复，
   `additional_historical_roots_published` 恒为 0。
2. 同 tuple 但 receipt digest 或 canonical historical root 任一不同 MUST `duplicate_conflict`，零覆盖并进入安全诊断。
3. 只有 `receiver_id` 不同的 selector 是不同合法历史分支，MUST NOT 互相冲突，各自发布自己的 root。
4. recursive signer dependency closure 不完整或 receipt 永久丢失 MUST 保持 unresolved
   （`agent_signer_evidence_missing`）；MUST NOT 发布半个 root，MUST NOT 从 current state 补造 receipt。
5. historical outer attestation 使用 closed `attested_at` 且没有 verifier-now TTL：签发很久之后 MUST 仍验证通过，
   Authority verification method MUST 按 `attested_at` 解析。之后的 Authority key rotation MUST NOT 使已合法组装的
   root 失效；`attested_at` 当时该 method 已非 active MUST 拒绝；historical 分支携带带 `expires_at` 的 current outer
   MUST 拒绝。
6. receiver 在 `receipt.accepted_at` 之后轮换签 receipt 的 key MUST NOT 使该 receipt 无法 materialize：receiver
   dependency 与 receipt proof verification method MUST 按 `receipt.accepted_at` 解析当时的 historical service record；
   从 current service record 或 verifier-now 重建 MUST 拒绝。`accepted_at` 当时 method 非 active MUST 拒绝，
   其后的 revoke MUST NOT 追溯否定。

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

## 30. cas_register 因果 heads join closure vector

`vector_id`: `ak.vector.lattice.cas_register_supersession.v1`

规则正文见 [`../authz/event-auth-state-resolution.md` §9.3.1.1 至 §9.3.1.4](../authz/event-auth-state-resolution.md)。

Runner MUST 覆盖：

1. **未写入读 `null`**：空 heads 的 cell settled value 是 `null`，且该 cell 不占 `state_root` leaf；
2. **线性生命周期**：declaration → tombstone → 再 declaration，每次写入取代它在自身签名 basis 下观察到的全部 heads，最终只剩一个 head，不落 `⊥`；
3. **释放为 `null` 是一次有身份的写入**：`set null` 之后 heads 非空、业务读 `null`、且该 cell **仍在** `state_root` 中，与「从未写入」可区分；
4. **ABA / ABAB 可区分**：`A → null → A` 读 `A`；`A → B → A` 与 `A → B → A → B` 分别读 `A` 与 `B`（按 value 接边求值会在这两组输入上给出相同答案，因此这样的实现 MUST 失败）；
5. **并发异值落 `⊥`**：两个互不可见的写入产生两个异值 head，`bottom=reject` cell 物化 `failed_bottom`；
6. **同值并发保留全部身份**：两个互不可见的写入产生同值的两个 head 时，业务读该值，但两个 EventId MUST 都保留在 heads 与 `state_root` leaf 中；随后只观察到其中一个分支的后继 MUST NOT 删掉它没见过的那个 head；
7. **exact replay 幂等**：同身份、同 canonical effect 的重复投影不产生第二个 head；同身份、不同 effect MUST 走验证错误 / §6.3.3 碰撞路径，MUST NOT 交给 lattice 选一个；
8. **合并的 ACI**：对任意两/三个已验证状态 `(C,H)`，§9.3.1.4 的合并式满足结合律、交换律、幂等性，且与「对完整因果历史求活跃写入集合」的独立 oracle 逐例一致；
9. **`⊥` 非粘滞**：并发分支各写 `A`、`B` 后各自在未见对方时续写同一个 `T`；只观察到部分 leaf 的 receiver 与观察到完整历史的 receiver MUST 在补齐 leaf 后收敛到同一结果（读 `T`）；
10. **任意 prefix-closed 覆盖子集**重算得到该子集的确定性历史 view。

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

规则正文见 [`../sync/signal.md` §1 / §3](../sync/signal.md)。Runner MUST 覆盖 §3 的完整
role-aware conformance 清单：source/recipient 接受晚于 `seal_ref` 但 current active 的设备授权，
拒绝 current revoked/fenced/conflicted、错误 principal/fragment/Station、缺失或过期的信任材料，
以及 active leaf 的 key/authorization binding 不一致；即使 leaf 尚未 Remove 或 AEAD 成功也不能
放宽。recipient 只能从 §8.2/§8.3 的既有设备信任路径取证，不要求完整远端 PCR。
destination 缺少远端目录不阻止合法 relay，但 peer source/body、routing、proof transcript/digest、
Realm/scope/current membership/action/TTL/MLS outer basis 仍需通过。结构正确的伪 producer signature
只在 source/recipient 验签失败；恶意 source 不能借合法 HTTP 签名使 recipient 接受它。
另 MUST 断言 source 出站 fresh admission、Agent/minimal 禁止 synthetic device，以及过期
envelope 在 local ingress 被 `param_invalid` 拒绝、peer item 被 opaque 丢弃。

## 34. Active Event payload carrier closure

`vector_group`: `ak.vector_group.event_kind_payload_coverage.v1`

Runner MUST 加载 [`event-kind-payload-coverage-fixture.json`](../../artifacts/fixtures/event-kind-payload-coverage-fixture.json)，并同时执行 registry 闭包与其中的 `schema_validation_cases`。对每个 active `durable_event` / `actor_private_event` kind，payload validator 必须能由 `payload_schema`、`payload_schema_ref` 或 canonical kind-dispatched payload definition 唯一解析；若 registry 显式声明 `payload_schema_ref`，Event Envelope 对该 kind 的 dispatch MUST 指向同一 schema location，不能让 registry-driven SDK 与 envelope-driven validator 接受不同 payload language。

本组对 `ak.relation.tombstone` 与 `ak.moderation.franking_proof` 的最低覆盖是：

- `ak.relation.tombstone` 正例只携带 `relation_id` 与可选 `reason`，并解析到 `relation_tombstone_payload`；携带 `target_ref` / `patch` 的 update 形态 MUST schema-invalid。Registry cell subject 必须由 `payload.relation_id` 解析为 `id:relation`。
- `ak.moderation.franking_proof` 正例必须通过 `moderation-evidence.schema.json#/$defs/franking_proof`，registry 与 Event Envelope 必须引用同一个 def；只带 `report_id` / `target_ref` 的 report-keyed 形态 MUST schema-invalid。Registry cell subject 必须由目标 `payload.event_id` 解析为 `id:event`，不得使用外层 proof Event 自身的 `event_id`，也不得退回不存在的 report 字段。`verification_method` 必须存在、controller 投影等于 `received_by`，且在 `received_at` 有效。
- 任一显式 schema ref 不存在、ref fragment 不可解析、Event Envelope 错接到共享 `audit_payload` / `relation_update_payload`、或 cell subject 在所选 payload class 上无可解析标量端点，均 MUST 使本组失败；`event-payload.schema.json` 的定义包根 schema 不能替代上述两条 kind-specific 合同。
## 35. Service route handover / Realm mirror closure vector

`vector_id`: `ak.vector.service_resolution.handover_mirror.v1`

Runner MUST 加载
[`service-route-handover-mirror-fixture.json`](../../artifacts/fixtures/service-route-handover-mirror-fixture.json)，
先按每个 case 的 `schema_ref` 执行
[`identity-resolution.schema.json`](../../artifacts/schemas/identity-resolution.schema.json) Draft 2020-12
校验，再执行以下跨对象语义；只验证单个 JSON shape、只验证 target proof 或只验证 URL 可达性均不构成通过：

1. `scheduled` notice 必须满足
   `issued_at <= not_before <= cutover_at < grace_until <= expires_at`，且
   `from_record_sequence/from_record_digest` 精确命中 receiver durable current/last-seen floor；任一时间逆序、
   stale sequence 或异 digest 都必须拒绝，且不得消耗 current record sequence。
2. 同一 `handover_id` 的 cancellation 必须使用恰高一的 `notice_revision`、精确
   `previous_notice_digest`，并省略全部 candidate/time 字段；same revision、跳 revision、异 digest 或在正式
   successor 已接受后试图回滚均拒绝并 quarantine 相应 notice chain。
3. notice 在任何时刻都不直接授权 Realm Event、to-device、KeyPackage、repair 或其它业务 bytes；
   `not_before` 前至多允许不更新 route state 的 bounded public resolution/describe preflight。
4. candidate 只有返回正式、target-signed、同 `service_id + service_kind`、
   `record_sequence=from_record_sequence+1`、`previous_record_digest=from_record_digest` 的
   `ServiceResolutionRecord`，并通过 method history、freshness、SSRF 与 describe reverse binding，才能成为
   effective route。wrong core、sequence gap、wrong predecessor 或 describe mismatch 均 fail closed。
5. `ak.peer.service_resolution.command.publish.v1` 必须同时验证两个独立 durable 幂等键：transport key 是
   `(source_id, realm_id, request_id)` 并绑定 complete canonical `request_digest`，HTTP
   `Idempotency-Key` 必须逐字等于 body `request_id`；artifact integrity key 是
   `(source_id, realm_id, artifact_key)` 并绑定 `artifact_digest`。同 transport key、同 request digest
   返回原 ack；任一 key 的 digest 冲突都必须 `duplicate_conflict`、零覆盖。新 `request_id` 发布同一 artifact
   bytes 可以得到一份与新 request 交叉绑定的新 ack，但不能产生第二份 artifact state。
6. notice basis 不允许在同一 exact-one publish request 内夹带或隐含 record chain。receiver floor 落后时，
   publisher 必须按 sequence 逐份 publish 每条缺失 `ServiceResolutionRecord`，逐份取得 durable ack 并推进
   floor，最后才以新的独立 request publish notice；缺少任一前置 record ack 时 notice 必须
   `service_route_notice_basis_stale`，且 notice ack 不得被解释为整条 record chain 的原子 ack。
7. `ak.peer.service_resolution.read.resolve.v1` 最多返回 32 条连续 successor，canonical response 至多
   256 KiB；33 条与 256 KiB+1 均拒绝或截成仍连续的合法 page，不得跳 gap；
   `successor_records=[]` 与 `has_more=true` 的组合必须 schema-invalid。认证/当前 peer/target visibility gate
   失败统一为 `capability_denied`；通过 gate 后的 unknown、invisible、not-held、gap、fork、cancelled、expired
   统一为 `not_found`。同一 blinded class 的 body、长度与 timing bucket 不可区分，具体原因只进私有审计，
   不得泄露 Realm topology。
8. 两个 mirror 对同一 service sequence 返回不同、但均通过 target proof 的 digest 时，必须进入
   `service_route_fork` quarantine；不得按多数票、到达时间或 URL reachability 选 winner。
9. record last-seen floor 与 accepted notice state 必须是相互独立的 durable 状态。restart 后 TTL cache 可以
   完全丢失，但低于 record floor 的 replay 仍拒绝，已接受 cancellation 仍阻止 candidate，same revision 异
   digest 仍触发 quarantine；notice expiry/completion 也不得降低 record floor。
10. route cache 必须同时保留 target-signed `expires_at` 与本地 `cache_expires_at`，且本地值不得晚于 signed
    expiry；任一边界到达即 hard miss。`now == cache_expires_at` 或 `now == expires_at` 均不得继续路由，
    不得丢弃 signed expiry、以新本地 TTL 延长它、跳过 describe 或把 future notice candidate 当 current route。
11. same-core 的 DID / URL successor 只推进 route floor 与 cache，不写 Realm membership；candidate
   指向不同 Station core 时必须作为新 AccountId 独立加入，不能被 notice、mirror 或 cache 当作旧账号接受。
12. 1:1 双方计划同时迁移时，只有 A durable ack B 的 exact notice 且 B durable ack A 的 exact notice 后，
    才可报告 cross-ack preannouncement complete 并按共同 cutover/grace 关闭旧入口；任一 ack 缺失、仅内存、
    digest 不一致或响应不确定时必须保留旧入口或其它已确认恢复面。

## 36. Realm fanout route-miss closure vector

`vector_id`: `ak.vector.fanout.route_miss.v1`

Runner MUST 加载
[`fanout-route-miss-fixture.json`](../../artifacts/fixtures/fanout-route-miss-fixture.json) 并执行
`ak.suite.fanout.route_miss.v1`。测试至少使用两个 Station 与一个含多个 joined member 的 Realm，
覆盖缺 route、后补 verified route、进程重启、共享 service 的多 member witness、leave/ban、新 AccountId 独立加入、rejoin 与最终
peer acceptance。仅对 schema 做枚举校验不构成通过：

1. 本地 Event、按 service DID 去重后的完整 frozen target set 与所有 intents 必须同事务；第二个 target 写入
   fault 时 Event、target 和 intent 全部不存在。
2. route miss 的唯一 submit 结果是本地 accepted 且 `pending_delivery_count=1`，consumer 派生 state 为 pending；不得返回
   `service_unavailable`，不得漏 target，也不得泄露 service topology。
3. `pending_route` 与 `pending_delivery` 跨重启、cache eviction 和尝试阈值保留；阈值只触发 operator alert，
   authority 仍有效时不得 dead-letter。
4. route 恢复后 MUST 在同一 accepted view 中逐个复校验完整 frozen witness
   `(realm_id, member_id: ActorId, membership_event_ref)`：同一 ActorId 仍 effective joined、exact Event ref 仍匹配，且
   该 ActorId 的 route 等于冻结 target service。tuple 内全部条件同时成立、tuple 间至少一个成立才可按原 idempotency key
   发送并推进 delivered；不得把 service projection 当成独立 witness，也不得跨 tuple 拼接条件。
5. 全部 witness 失效时必须在网络发送前 terminal CAS 为 `cancelled_authority_lost`；后来相同 member/service 的
   新 join 或新账号加入不能复活旧 intent。
6. 长期离线 target 不阻塞同 Realm 后续合法 Event；每个 Event 冻结自己的 authority generation 和独立 intent。
7. `ak.self.events.read.delivery_status.v1` 对可见 Event 返回按 opaque target_id 排序的完整 target set；service_id
   只在 caller 当前可读对应 joined-member ActorId routing projection 时出现。unknown 与不可见 Event 统一 `not_found`，query
   不得触发 route lookup、retry 或状态转换。
8. submit outcome 保留的 `pending_delivery_count` 必须精确等于 pending_route 与 pending_delivery rows 数；read outcome 由完整 `targets[]` 现算该 count。两者的 aggregate state 均由 count 唯一派生：零为 complete，非零为 pending，wire 不重复携带 state。
9. 全部成员已经退出，但旧 ActorId 仍纯函数投影到同一 service 且 endpoint 可达时，MUST 取消旧 intent 且零网络发送。
   两个 witness 分别只满足 membership 与 Event-ref 条件时也 MUST 拒绝，不能合并为一个有效 witness。
10. 同一 service DID 的 verified endpoint 更新 MUST 保留原 intent/幂等键并在复校验后发送；新 Station 的 AccountId 或
    新 membership Event MUST NOT 改写旧 target、重定向旧 intent 或令已取消 intent 复活。

## 37. Agent Event admission receipt handoff closure vector

`vector_id`: `ak.vector.federation.agent_admission_receipt_handoff.v1`

本向量由 [`federation-fixture.json`](../../artifacts/fixtures/federation-fixture.json) 的
`agent_event_admission_receipt_handoff` case 组承载，规则正文见
[`../sync/federation.md` §4.1.1](../sync/federation.md)、
[`../sync/service-http-binding.md` §3.1.6](../sync/service-http-binding.md) 与
[`../identity/key-management.md` §3.6.1](../identity/key-management.md)。

Runner MUST 覆盖：

1. `ak.peer.events.command.submit.v1` 的成功 outcome MUST 为 `accepted[] ∪ duplicate[]` 中每个 Agent Event
   返回恰好一个 receiver-signed `agent_event_admission_receipts[]` 项；非 Agent Event 不产生 receipt；
   `rejected[]`、`quarantine[]` 与 dependency-missing 项 MUST NOT 签发或返回 receipt；self submit outcome 不带该字段。
2. receipt MUST 与 Event durable acceptance 在同一事务写入。receipt 写入失败 MUST 使该 Event 的接受整体回滚，
   不得出现「Event 已接受但无 receipt」。receipt 有自己的 detached proof（domain
   `ak.agent_signer_admission_receipt.v1`），HTTP Message Signature MUST NOT 充当替代。
3. 同一 Event 被多个 receiver 接受时，每个 receiver 各签自己的 receipt，按 `receiver_id` 区分为多条
   合法历史分支。
4. byte-identical 重投 MUST 从 `duplicate[]` 返回第一次保存的 byte-identical receipt；重新生成 `accepted_at`
   或更换 signing method 均不合格。相同去重键但 Event canonical bytes、digest 或 receipt intent 不同 MUST
   `duplicate_conflict`，零 receipt 且零覆盖。
5. source durable outbox 收到 2xx 后 MUST 先校验 response transport authentication 与 outcome schema，再要求
   receipt 集合与 `accepted[] ∪ duplicate[]` 中带 origin `producer_signer_resolution_evidence_ref` 的 Agent Event 精确一一对应：
   少一个、多一个、receipt proof 不可解析、`receiver_id` 不匹配，或 receipt 承诺的
   `producer_signer_resolution_evidence_ref` 与 origin 冻结的 ref 不一致，MUST NOT 把该 Event/receiver 的
   历史证据交接标为完成。
6. 只有 receipt 已验证并与 materialization obligation 原子保存后，该 Event 对该 receiver 的 outbox delivery 才可推进；
   source 在 obligation 提交前重启 MUST 复用同一 outbox row 与同一 Event/receiver/receipt intent，
   MUST NOT 重新选择 admission evidence 或产生新的逻辑 receipt。

## Account status issuer ledger

`ak.vector.account_status.issuer_ledger.v1` MUST 覆盖：account binding 与 `status_seq=1,active` record、account row、audit、outbox 原子提交，PCR 尚无 Seal 也成功；record id 与 proof 对同一 closed unsigned core 做 JCS/SHA-256 闭合，proof controller 必须是 Account Authority；successor 严格执行 `seq=current+1` 与 exact predecessor CAS，exact replay byte-identical、同 request identity 异 intent 零写入冲突；receiver 区分 accepted/duplicate/stale/gap/fork，且分类基线只有 durable replica head——在连续 replica 上重投一条低于 head 且与本地仍保留的同 `status_seq` 历史行逐字节相同的 record，MUST 得到 `failed_precondition` + `account_status_record_stale`（`retryable=false`、零写入），MUST NOT 降级为 `duplicate`；gap 返回 exact required seq 并通过 bounded resolve 取得连续原始 records；holder offline/revoked/hostile 时 Account Authority 仍可 final `locked/suspended/deactivated/erasure_pending`；receiver 接受 exact、连续且验签有效的 `deactivated → active` successor，authoring conformance 则必须证明它只来自 deployment-policy allow + completed PCR recovery closure，并与原 account row、audit、outbox、exact新 generation grant 原子提交；普通 admin/login/refresh、policy deny 或缺 recovery closure 均 `account_deactivated` 且零权威写入；`erasure_pending` 的任何 successor 继续以 `erasure_pending_is_terminal` 拒绝；receipted fanout 保留原 record bytes，receipt 精确绑定 record，超窗 flag 不回写 record；不存在 Event、Seal、CBA、frontier 或 `pending_seal` 路径。

## Personal blocklist revision and delivery semantics

`ak.vector.account.blocklist_projection.v1` MUST 覆盖：version 1 加入 actor block 后，共享 Realm Message 仍被收取、验签、存储并进入 canonical history，但 holder projection/notification/read-receipt/presence side effect 被抑制；version 2 省略该 entry 后，retention 仍保留的历史重新可见。并发 version 2、跳到 version 3、owner/actor 不同、同一 normalized target+applies_to 重叠 entry 与 target discriminator/承载不匹配均拒绝。`entries=[]` 清空规则。仅写 personal blocklist 不得撤销 Direct Conversation participant authority；任一方 Contact tombstone accepted 后 conversation 即 suspended，Consent grant/revoke 对 Personal DM authority无效。服务端无权读取 blocklist 时仍转发加密材料给 holder 设备并由端侧过滤；有权读取时可在 holder surface 前 drop，但两条路径对发送方的 response bytes、错误类别与 timing bucket 不可区分。

## Applet revoke saga closure

`ak.vector.applet.revoke_saga.v1` MUST 加载
[`applet-revoke-saga-fixture.json`](../../artifacts/fixtures/applet-revoke-saga-fixture.json)，并执行
`ak.suite.applet.revoke_saga.v1`。Runner 必须证明 preview 重算的 exact plan 与 commit 的
`revoke_plan_digest`、caller-signed capability / membership submissions 逐项一致；任何遗漏、额外或
篡改 submission 都在首个 effect 前失败。Saga ledger 必须先于首个 Event admission / external / local
effect 持久化；第一条相关 revoke Event accepted 后立即 fence 后续 Applet writes。

逐字节相同 request 与同一 Idempotency-Key 在 crash / response loss 后必须加载同一 ledger，只恢复
`pending` / `rejected` 的必要步骤，不重新执行 `accepted` / `duplicate` 步骤，也不得跳过失败步骤；同 key
异 body 必须 `duplicate_conflict` 且零新 effect。只有所有计划步骤均为 terminal success 才可报告
`complete`；Event 或外部撤销失败时必须返回并持久化 `partially_completed`，重启后继续同一 saga。
相同 key/body 从不同 `principal_service_id` 或 `admin_actor_id` 重放也必须 `duplicate_conflict` 且零新
effect，不能把另一个管理员或服务当成同一 saga owner。

## Producer-allocated ID 冲突参数化向量

`ak.vector.object_identity.producer_allocated_collision.v1` MUST 加载
[`producer-allocated-identity-collision-fixture.json`](../../artifacts/fixtures/producer-allocated-identity-collision-fixture.json)，并以
`id_kind_registry.id_kinds[id_form=producer_allocated]` 为参数源逐 kind 执行，而不是维护手写 kind
白名单。每一行都必须覆盖：首次原子 reservation、同 authority 同 binding 精确重放幂等、同 authority
不同 binding 拒绝并 quarantine、不同 authority 的相同 UUID 按 `(mint_authority, typed_id)` 成为不同身份、
裸 typed-ID lookup 失败，以及 accepted proof signer 不是登记 mint authority 时失败。新增 producer-allocated
kind 若未自动进入本 suite，release gate MUST 失败。

## MLS 历史恢复闭合向量

Runner MUST 加载新的 `history-key-recovery-fixture.json`，并至少执行四个 closed suite：

- `ak.vector.history_key.closed_response_delivery.v1`：request create/receipt、相等 TTL、manifest 全量 T0 admission、
  single-continuous-range chunk、source relay、honest release-service attestation、byte-identical exact retry、小型 send receipt、
  normal/lost 合并 sequence ack、attempt completed/expired 与 quota 边界；
- `ak.vector.history_key.client_convergence.v1`：exporter all-history requester 在缺 epoch 后无人工操作 create/resume，
  create-response 丢失与重启后仍复用同一 durable intent/request/HPKE key；首次空页固定为
  `{entries:[],limited:false}` 且省略 `ack_token/cursor`，不持久、不 ACK、不推进 high-water，同一 after 续读后
  可见稍后到达的 manifest；source ready-marker 崩溃后 exact bytes 重放；部分材料 attempt 完成后取得新的未覆盖
  requested epoch 会产生第二 manifest。向量还 MUST 覆盖暂时无 source 的非终态诊断、`since_join` 零 request
  以及 requester/source 当前失权时零新写入。向量 MUST 另外执行 [`../governance/history-visibility.md` §6.2](../governance/history-visibility.md)
  的 send/relay 拒绝分类：attempt status 是封闭四元集 `unfinished|completed|permanently_rejected|expired`，并发上限只计
  `unfinished`；transient code 只 exact retry 同一 attempt 且零新 manifest / 零新 response id，permanent code 与
  `failed_precondition + reason_code=history_traversal_anchor_unreachable` 只转 `permanently_rejected` 并作者化新 manifest 且
  绝不把旧 attempt 记为 `completed`，`request_terminal` code 同样转 `permanently_rejected` 但不作者化替代 manifest，传输失败与未登记 code 一律
  按 `retry_same_attempt` 处理，重启后分支不变；
- `ak.vector.history_key.frontier_traversal_split.v1`：near-current `group_security_frontier` 的 bounded stateless 完整响应，与
  bulk/old-history receipt-bound direct Seal traversal 严格分型；覆盖 `trusted_history_base_basis`、独立 anti-rollback
  `trusted_current_basis`、target dominance、完整 predecessor cut、registered dependency resolve、current ratchet/join floor、per-item RHRK traversal 及 self/peer visibility 边界；
- `ak.vector.history_key.sender_crypto.v1`：ordinary human/Agent/minimal sender domain、history-secret KDF、nonce、
  reconstructed AAD、HPKE chunk context、multi-candidate store 与 replay ledger。Received/RHRK secret 永远是 candidate，AEAD success
  只建立 exact Event→candidate digest binding，不得 epoch-level promote/淘汰其它 candidate；fake secret+fake ciphertext 只能影响恶意作者
  自己签名的 Event。Runner 还必须覆盖按 `(scope,group,epoch,candidate_digest)` 全局 material 去重、与 bytes 分离的 typed
  `CandidateOriginAttribution(material_key,response_sender|rhrk_archive|portable_backup,origin_quota_domain,origin_ref)`；quota domain 分别固定为
  source sender、holder/key tuple、backup series/producer，origin_ref 只作取回坐标。Runner 必须覆盖 immutable 30 日 TTL、每 candidate 4 条、
  每 exact epoch-quota-domain 64 条、每 epoch 总计 256 条与 canonical 确定性裁剪，
  以及不含 origin 的 `EventCandidateBinding(event_binding_key,candidate_digest,outcome)` 每 epoch 256 条/30 日上限。两级 eviction 必须先无 success
  再 success-bound，使用不可刷新的 `(material_received_sequence,candidate_digest)`，只删除 bytes/sequence 并保留有界 tombstone；同 bytes 新 origin
  不刷新 sequence，refetch 被驱逐 bytes 才取得新 sequence。local_authoritative 分账且永不驱逐，
  portable backup 只写源设备 local_authoritative、restore 设备按 portable_backup origin 接收 candidate，以及 Circle 独立 group 与 standard fresh-endpoint admission floor。fixture 必须给 standard floor 的
  固定 seed、winning Add epoch、前后 epoch 集合与 exact expected counts；规模子组必须给可执行的结构化 generator algorithm/seed/input ranges，
  构造 26,298 个 epoch 压力路径与总计 65,536 个 epoch 上限路径，并断言 covered/duplicate/gap counts、每类 canonical serialized-byte 上限与
  peak buffered-byte 预算。65,537 必须在写入前 `bounds_exceeded`，不得仅以自然语言 recipe 或兆级展开数组充当向量。

`ak.history-scale-fixture.v1` 的唯一可执行定义是
[`tools/generate_history_scale_fixture.py`](../../../../tools/generate_history_scale_fixture.py)；runner MUST 按 fixture
`direct_traversal_scale_generator_contract` 逐字执行：

1. JCS 只使用 closed ASCII string/non-negative integer subset，object key 按 code point 排序且无空白；所有 domain tag 与 `0x00` separator
   取 fixture 的 machine constants。
2. 小型 KAT 必须构造 schema-valid `HistoryGovernanceTraversalIntent/Retention`、完整 open-set base/current/target `SealBasis`、
   `AuthenticatedSignerResolutionEvidence`、`MinimalMetadataMlsLeafSignerEvidence`、`AvailabilityReceipt` 与三分支
   `GovernanceDependencyResolveOutcome`，并重算各自 canonical digest；replay 解释器只按 Realm profile id 选择。
3. Direct traversal runner 使用 disk-backed work queue 从每个 target leaf 沿 signed `predecessor_refs` 反向遍历到 exact base cut；每个区间
   predecessor 必须在 cut 内或恰为 base leaf，每个 base leaf 必须被消费，target 必须支配独立 current anti-rollback basis。随后按拓扑运行标准
   `apply_seal`，按 digest 解析每个 `Seal.delta` Control Move、AvailabilityReceipt、signer-resolution evidence、registry snapshot/artifact 与其它
   registered dependency，重算 roots、Bottom/recovery、winner、join/incarnation、ciphersuite/content scheme 及 current monotone history access。
   `direct_traversal_replay_kat` 另以 Genesis + successor 的最小两 Seal 拓扑执行三项真实 replay：历史 frozen notary key 正签名必须通过；同一
   `verification_method` 换成 current key 所作的 successor 签名必须按 predecessor joined notary descriptor 拒绝，且目标 Seal、verified outcome 与业务
   callback 均不提交（为派生历史 state 而完成的 Genesis 临时 replay 不算违规）；同一 claimed digest 对应两份不同 digest-preimage Event 的
   resolver response 必须在选边及 replay 前整次拒绝，replayed Seal 计数为零。该 collision 是 ingestion seam 的符号化注入，不宣称制造真实
   SHA-256 collision；这些 case name 不是 wire reason code。普通 DataEvent 不进入 `Seal.delta`，已 Seal 历史后来发现 collision 的不回滚规则复用
   `ak.vector.cba_lattice.sealed_control_move_full_digest_collision.v1`，不得在本向量另造 first-seen 或 Realm 失效语义。
4. 规模 recipe 不生成额外历史证明 carrier 或 O(N) fixture 数组；26,298 与 65,536 两条路径只冻结实际遍历的
   Seal/Event/dependency counts、canonical descriptor stream aggregate digest、总字节和单对象最大字节。work queue/visited set 落临时 SQLite，
   内存只保留当前 descriptor 与常数个 hash accumulator。
5. 每个 manifest descriptor 只含 `chunk_response_id,chunk_index,covered_epoch_range`；连续 range 必须是 request receipt canonical ranges 的子集，
   且由完整 replay 与 current ratchet/join floor 授权。不存在 query/page、package root、selection digest 或 range key。
6. 65,537 epoch case 必须通过与正例相同的 `build_scale_recipe` 入口，并在任何 traversal journal、dependency resolve 或 outbox 写入前由 checked budget
   拒绝，各计数保持 0。`python tools/generate_history_scale_fixture.py --check` 任一字节漂移必须失败；写模式只刷新本 fixture，不生成
   reports/site/digests。

RHRK cases MUST 另覆盖 create Seal 后 register、key-evidence Event reducer-effective 前禁止 durability Genesis、CAS rotate、provenance Event、
完整 `holder_trusted_basis` 与 exact-one-epoch archive-lifetime direct traversal retention、holder replica/read、current holder
source relay 及首次入队 attestation；该子组登记为 `ak.vector.history_key.organization_recovery_registration.v1`，并必须断言
effective recovery-key cell 不含 service-selected effectiveness locator；生效事实只由 replay 后的 reducer state 决定。所有 positive/negative inputs 都使用二态 `history_access`；fixture 不得出现旧 share/withheld
Event、homogeneous policy-root segment、to-device request、foreign active MLS snapshot、profile-fixed baseline 或旧五档 literal。
RHRK holder 向量还必须断言：它可以取得完整 holder-basis→archive-target 验证 closure 所需的 Control Move/Seal 及由此暴露的
membership/policy/control metadata，但不能读取 closure 外 DataEvent、generic timeline 或获得 membership/send 权；不能接受该披露的部署必须禁用 RHRK。
