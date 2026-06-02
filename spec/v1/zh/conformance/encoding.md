---
title: Encoding, IDs, Hashes, Signatures
status: candidate
normative: true
stability: v1
updated: 2026-05-25
sidebar:
  label: Encoding & IDs
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

本文定义 Contrix 的 canonical encoding、ID、hash、signature、cursor、HLC 与 rank 编码规则，确保不同实现能得到相同 digest 和验证结果。

## 2. Canonical JSON

Contrix canonical JSON 是签名、hash、event digest、receipt digest、snapshot commitment 和 cursor 内部状态的唯一编码 profile。实现 MAY 复用 RFC 8785 / JCS 类库，但最终输出必须满足本节的收窄规则和 `conformance-vectors.md` 的测试向量。

Contrix canonical JSON MUST 使用：

- UTF-8 不带 BOM；输入若包含 UTF-8 BOM（`U+FEFF` 编码 `EF BB BF`，无论出现在 stream 起始还是 string value 内部）、malformed UTF-8、孤立 surrogate 或无法被 JSON parser 唯一解释的字符串，MUST reject。`U+FEFF` 在 string value 中只允许作为 zero-width no-break space 的语义存在，但 v1 canonical JSON 不允许此用法——任何 `U+FEFF` 出现都按 schema_violation 拒绝。
- object key 按 Unicode code point 升序排序，并在每一层独立排序。
- 无 insignificant whitespace。
- JSON object 中的重复 key MUST reject，不得采用“最后一个 wins”或“第一个 wins”。
- number MUST 使用 RFC 8785 / JCS 等价的唯一 decimal serialization；NaN、Infinity、-Infinity、`-0`、无法精确往返的 number、超出 JSON safe integer 范围 `[-9007199254740991, 9007199254740991]` 的 number MUST reject。**v1 wire MUST NOT 使用非整数 number**：所有签名 canonical object 的 number 字段 MUST 是 JSON integer。需要超过 safe integer 范围的计数器、偏移或大整数 MUST 编码为带显式格式约束的 string（例如 fixed-width hex / decimal string），不得作为 JSON number 进入 canonical bytes。比例、置信度、进度等小数值 MUST 编码为整数 + 显式 scale（推荐字段后缀 `_basis_points` 表示万分数 0..10000，或 `_x1000`、`_x1000000` 等明确比例）；`confidence_basis_points: 7500` 表示 75.00%。这条收紧规则取消了"何时允许 number canonicalization"的可选语义，使签名输入 100% 确定。
- timestamp 使用 RFC 3339 UTC，尾部 `Z`；签名输入不得接受本地时区、隐式时区或 leap-second 变体。
- 字段名使用 snake_case。

Event Envelope 的签名和 hash 输入 MUST 是去除 `proofs` 与 `unsigned` 后的 canonical JSON bytes，并且 MUST 保留 `event_id`。`unsigned` 是传输/本地附加信息，不得影响 event digest 或 proof `event_digest`。实现不得对已经签名的 bytes 做大小写规范化、ID 前缀补全、字段默认值补写、key 重排以外的语义改写。

生产者 MUST 在所有 v1 签名对象中使用 JSON integer 表示数值。Schema 要求小数语义的字段（如概率、进度、置信度）MUST 使用整数 + scale（见上文 `_basis_points` 等约定），生产者和消费者按预定义 scale 解释，无须做 number canonicalization。任何 v1 schema 不得新增 `type: number`（非整数）字段；遗留字段 MUST 在下一个 schema profile 升级时迁移到整数 + scale。

### 2.1 String 字段的 Unicode 收紧

字符串 field 的 wire 形态 MUST 满足以下约束，否则 receiver MUST `schema_violation` 拒绝：

- **NFC 正规化**：所有 string value MUST 在写入 canonical JSON 前完成 Unicode NFC（Canonical Composition）正规化。生产者发送已 NFC 化字节；receiver 不得在 verify 阶段做隐式 NFC 化——若收到非 NFC 字符串，按 schema_violation 拒绝。这一条避免"看起来一样的字符串"在 hash / signature 比较时出现 false positive 或 false negative（同一可见字符可能由 precomposed 或 decomposed 序列表示）。
- **身份相关字段进一步走 NFKC**：DID URI、handle、connection identifier、display name 用于精确匹配 / blocklist / capability subject 解析的字段 MUST 在比较前归约为 NFKC（Compatibility Composition），并对结果再做 case folding（`toCaseFold` / Unicode default case folding）。NFKC 把 compatibility-equivalent 字符（如 `ｄｉｄ：` 全角 vs `did:` 半角，`Ⅰ` vs `I`，`℗` vs `(P)`）合并到同一表示。比较 / 索引 / 黑名单匹配 MUST 在 NFKC + case folding 之后进行；wire 上仍传 NFC 原始字节。
- **Confusables 拒绝**：handle、DID method-specific identifier、organization handle 这类与品牌 / 身份相关的 string field MUST 拒绝包含 Unicode TR 39 高风险 confusable 字符的输入。受规范的字段 MUST 使用 `IdentifierStatus=Restricted` 或更严策略：
  - 拒绝 mixed-script identifier（拉丁 + 西里尔 + 希腊 + …）；只允许 single-script，或 single-script + ASCII digit 组合。
  - 拒绝 TR 39 §5.1.1 列出的高风险 confusable 字符（如 `а`(U+0430 西里尔) 与 `a`(U+0061 拉丁) 同形）。
  - 拒绝纯不可见或控制字符序列（`U+200B…U+200F`、`U+202A…U+202E`、`U+2066…U+2069` 等 zero-width / bidi override）。
  - 实现 MUST 暴露 confusable check 为可调用 utility（见 `conformance-vectors.md` confusable test set），让客户端在创建 handle / 显示名前预检。

什么字段需要走 NFKC + confusable check：

| 字段 | NFC（必）| NFKC + case fold（比较时）| Confusable 拒绝 |
| --- | --- | --- | --- |
| DID URI | ✓ | ✓ | ✓（method-specific identifier 部分）|
| Handle（canonical `handle` / display form） | ✓ | ✓ | ✓ |
| Connection identifier（email / phone canonical 形态） | ✓ | ✓ | ✓（local part）|
| Organization name | ✓ | ✓ | ✓ |
| Display name | ✓ | ✓ | 仅 SHOULD（默认开启 confusable warning，用户 opt-out）|
| Title / summary / content body 等正文字段 | ✓ | — | — |
| Schema id / event kind / cell family 等 protocol identifier | ✓ | ASCII-only（schema 已 enforce） | — |

为什么把 NFKC + confusable 限定在身份相关字段而不是全字段：正文（Flow.content、Message.content）允许任何脚本混排是合理的（中文夹拉丁、阿拉伯夹希伯来），不能强制 single-script。但身份相关字段是 trust UI 决策点，必须 reject 同形字攻击。

### 2.2 备用 canonical encoding (profile-gated)

v1 wire format 锁定为 canonical JSON。需要更紧凑或更适合受限设备的 binding 时，profile MAY 引入备用 canonical encoding：

- **CBOR (RFC 8949) deterministic encoding** — 与 IETF MLS / COSE / WebAuthn 同源；适合 IoT、嵌入式与高密度 wire 场景。引入 CBOR profile 时 MUST 同时定义 JSON ↔ CBOR 等价规则，并在 conformance vector 中给出双向 digest 一致性测试。
- 其他 binary encoding（如 protobuf、msgpack）SHOULD 通过 profile 单独引入，不得静默替换 v1 canonical JSON。

引入备用 encoding 的 profile id 形如 `cx.profile.encoding.cbor.v1`；事件 envelope 中通过 `requirements.features[]` 声明使用该 encoding，否则接收方按 canonical JSON 解析。

## 3. Hash

### 3.1 Wire 形态

Contrix 所有 hash wire value MUST 形如：

```text
<algo>:<lowercase_hex_digest>
```

- `<algo>` 是 hash 算法标识符，取自下表的 v1 registered set。
- `<lowercase_hex_digest>` 是该算法的 raw digest 的小写 hex 编码，长度由算法决定。
- 算法、长度、编码三者**任何一项**与算法 spec 不一致 → schema_violation。

### 3.2 Hash Agility Set

v1 conformance 锁定的 hash 算法集合：

| Algo | Digest 长度 | v1 角色 | 抗量子 / future-ready 评估 |
| --- | ---: | --- | --- |
| `sha256` | 32 bytes（64 hex） | **v1 default**；所有 receiver MUST 支持。Event digest、Merkle leaf、state_root、blob CID、receipt digest 等核心字段默认使用。 | 不抗量子（Grover 把搜索成本减半到 2^128，仍可用）；通过 `cx.profile.hash_transition.v1` 可平滑迁移到 stronger hash。 |
| `sha512` | 64 bytes（128 hex） | v1 optional；声明 `cx.profile.hash.sha512.v1` 的实现 MUST 支持。可用于高安全 Realm 的 state_root、blob CID、long-lived audit hash。 | 与 sha256 同族；选择仅出于 digest size。 |
| `sha3_256` | 32 bytes（64 hex） | v1 optional；声明 `cx.profile.hash.sha3.v1` 的实现 MUST 支持。提供 Keccak family 抗碰撞冗余，与 sha256 family 形成 algorithm diversity。 | 与 sha256 不同结构家族，抗结构性新攻击。 |
| `blake3` | 32 bytes（64 hex） | v1 optional；声明 `cx.profile.hash.blake3.v1` 的实现 MUST 支持。性能最佳；blob CID 与高吞吐场景推荐。 | sha256-class 抗碰撞；非 NIST 但被 IRTF / RFC 路径认可。 |

扩展 profile MAY 通过新 hash profile 加入抗量子 hash（如 SLH-DSA hash family、SHAKE256 派生），v1 wire 形态 `<algo>:<hex>` 已经为这种加法准备好——**无需重写 wire**。

实现 MUST：

- 默认按 `sha256:` 解析；遇到未识别的 algo prefix → 若位于 critical field（event_digest、state_root、prev_refs blob hash）→ fail closed (`unsupported_digest_algorithm`)；若位于非 critical metadata（如对象的 derived fingerprint）→ MAY 记录为 unknown 并 preserve raw bytes。
- 在 `server/describe.crypto` 暴露支持的 hash algo 集合；client 可据此选择写入算法。
- 不得"算法升级"已签名的 canonical bytes：一旦 Event 用 `sha256:` 发布，verify 路径永远按 sha256 重算；不能因为本地默认换成 blake3 就重算并替换。

### 3.3 State Root 与 Anchor Hash 编码

`state_root`、Anchor `id`、Event `event_digest` / `event_id` 引用、receipt digest 这几条核心承诺字段的 wire 形态由所属 Realm 在 create event 中通过 `digest_algorithm` 字段固定（默认 `sha256`）。Move 是 reducer-input Event 的协议视图；Move 级引用 MUST 使用 enclosing Event 的 `event_id` 或 `event_digest`。Realm 内所有后续 Anchor / Event digest / state_root MUST 使用同一 algo；切换需要通过 `cx.profile.hash_transition.v1` snapshot commitment + signed compaction Anchor 在 frontier 上做一次 algorithm transition Anchor，新旧 algo 都能在 transition Anchor 上验证 inclusion。详细规则见 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §4.2.5（hash transition）。

### 3.4 Multihash 兼容（profile-gated）

声明 `cx.profile.encoding.multihash.v1` 的实现 MAY 在 wire 上接受 multihash 风格的二进制 hash header（multicodec varint + length + digest）作为额外 reading format，但 canonical JSON 上的 wire value 仍 MUST 使用 §3.1 的 `<algo>:<hex>` 字符串形态。引入 multihash profile 的目的是与 IPFS / libp2p / Iroh 生态做内容寻址互通；它不替换 v1 wire 默认。

## 4. ID

协议 wire / canonical object 层的 typed ID 格式：

```text
cx:<kind>:<uuid>
```

标准 `kind` 的机器可读 source of truth 是 `artifacts/registry/id-kind-registry.json`。本文只定义通用规则。

`cx:` 前缀表示 Contrix 协议命名空间；`<kind>` 表示对象或引用类型；`<uuid>` 是该类型下的稳定 ID。完整 typed ID 是 wire value 的一部分，MUST 出现在：

- Event Envelope、canonical object、receipt、snapshot、fixture 和 OpenAPI / non-HTTP DTO。
- canonical JSON、签名 payload、`event_digest`、cursor 内部 state、federation payload、audit log。
- 跨服务引用、日志和错误响应中需要自描述对象类型的字段。

数据库或本地索引实现 MAY 不把 `cx:<kind>:` 前缀作为主键的一部分存储——例如直接用 PostgreSQL `uuid` / `BYTEA(16)` 列存 16 字节 raw value，由表名或显式 `kind` 列提供类型上下文。实现若这样存储，MUST 在进入 canonical JSON、签名、hash、联邦转发、sync cursor、audit replay 或 API response 前恢复完整 typed ID。接收方验证签名、hash、backfill 或 replay 时，MUST 按完整 typed ID 比较，不得用数据库 row id、自增 id、表名推断或隐式转换替代 wire value。

`<kind>` 是 canonical bytes 的一部分。实现不得把 `cx:receipt:<id>` 改写成 `cx:event:<id>`，也不得因为字段名叫 `receipt_id` 就在验证时补前缀。字段名可以辅助 schema 校验，但不能替代 signed wire ID。

v1 wire、JSON Schema、registry、fixture 和所有签名 canonical object 中的 `<uuid>` 段 MUST 是 [RFC 9562](https://datatracker.ietf.org/doc/html/rfc9562) UUID **version 7**：48-bit Unix-millisecond timestamp（big-endian）+ 4-bit version=`0111` + 12-bit `rand_a` + 2-bit variant=`10` + 62-bit `rand_b`，按 RFC 9562 §4 的 canonical 36-character lowercase hex 形式 `xxxxxxxx-xxxx-7xxx-Nxxx-xxxxxxxxxxxx` 序列化（其中 `N ∈ {8, 9, a, b}`，对应 RFC 4122 variant 1）。外部导入数据若是大写或带 URN/Microsoft braces 等变体形式，MUST 在生成 v1 Event Envelope、object id、cursor payload 或 proof `event_digest` 前规范化为小写无前缀的 36-char hyphen-separated 形式。已经进入签名 canonical bytes 的 ID 不得在验证、转发、backfill 或审计回放时重写大小写或形式。

同一 producer 在同一 millisecond 内连续产出 SHOULD 使用 RFC 9562 §6.2 列出的 monotonic 方法之一（推荐 Method 1：单调随机段递增）以保证字典序稳定且与时间序一致。**v1 wire MUST NOT 接受其他 UUID version 替代**——v1（基于 MAC + 时间戳）、v3/v5（命名空间 hash）、v4（纯随机）、v6（重排时间戳）、v8（自定义）以及任何非 UUID 格式的等价 ID（UUIDv7、KSUID、Snowflake、TSID、CUID）即使经过 hex 重编码并伪造 version=7 nibble，也不得作为 typed `cx:<kind>:<uuid>` 的 ID 段使用；wire 上锁定单一构造方式以避免 prev_refs / refs / cursor / index 出现两套分布。这条限制是 wire 兼容性约束，不是收敛或审计要求：receiver 校验以正则 + 长度 + version/variant nibble 为准，不对 timestamp 段做语义解析；但 producer SHOULD 拒绝产出 timestamp 段明显畸形（远未来或远过去于本地时钟超过实现声明阈值）的 ID，并 SHOULD 在生成时检测同 actor 时钟回退导致的非单调情况。

`event_id` 不是 canonical bytes 的 hash，是 producer 在签名前分配并写入 canonical bytes 的稳定 typed UUIDv7。Envelope 的内容指纹由 `proof.event_digest`（≡ `canonical_digest(envelope_without_proofs_unsigned)`）承担；`event_id` 与 hash 是两个独立字段，相同 `event_id` 配不同 canonical hash MUST 触发 `duplicate_conflict` quarantine（见 [`operations-sync.md` §2.1](../sync/operations-sync.md)）。

本节定义的 UUIDv7 构造、编码、单调性、receiver 校验规则 MUST 应用于 [`id-kind-registry.json`](../../artifacts/registry/id-kind-registry.json) `id_kinds[]` 中**全部** typed kind（包括但不限于 `realm`、`flow`、`space`、`morph`、`message`、`relation`、`view`、`actor_profile`、`device`、`capability`、`grant`、`invite`、`receipt`、`snapshot`、`transaction` 等），event 不是特例。新 kind 注册 MUST 遵循同一规则；只有 registry `special_forms[]` 中已列出的形态（opaque cursor、content-addressed blob / anchor、canonical cell tuple、MLS profile-scoped 引用、Realm-scoped pseudonym）才允许偏离 typed-UUIDv7 pattern，并各自由对应 schema / profile 单独校验。未在 registry 注册的非 typed-UUIDv7 前缀形态 MUST 按未知 critical wire type 拒绝。

特殊 ID/ref 形式（与 [`id-kind-registry.json` `special_forms[]`](../../artifacts/registry/id-kind-registry.json) 一一对应）：

- `cx:cursor:<base64url>` 是 opaque token，不是 typed UUIDv7 object ID。
- `cx:blob:sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` 是内容寻址 Blob ref；`cx:blob:019640ba-0000-7000-8000-000000000000` 是 Blob metadata ID。二者不得混用。
- `cx:anchor:sha256:<digest>` 是内容寻址 Anchor hash（active special form；见 `id-kind-registry.json`）。
- `cx:cell:<component>:<subject>` 是 canonical cell tuple 引用（active special form；component 来自 cell-component registry，subject 是 cell 的 subject key）。
- `cx:mls:<profile>:<profile_id>`、`cx:pseudonym:<scope_id>:<random>` 等 profile-scoped form 必须由对应 profile 注册和校验。

自定义 profile 若新增 `cx:<kind>:` 前缀，MUST 在 profile registry 或扩展 registry 中声明 kind、wire form、存储边界和校验规则。未注册的 `cx:<kind>:` typed ID MUST 被视为未知 critical wire type，除非所在字段明确允许 opaque string。

### 4.1 Field Naming: `_id` / `_ref` / `_did`（normative）

Identifier 字段命名的权威规则见 [`common-fields.md` §2.1](../models/common-fields.md#21-identifier-字段命名约定normative)。本节只给出编码层摘要：字段后缀表达 wire value category，不表达授权、同步、retention 或 E2EE 级联语义。

| 用途 | 命名后缀 | 说明 |
| --- | --- | --- |
| 对象自身 ID（primary key） | `id` | canonical object 的主 ID，无下划线前缀。例：`id`。 |
| 单一具体 protocol object kind | `<role>_<kind>_id` | 例：`realm_id`、`parent_space_id`、`scope_circle_id`、`policy_id`。 |
| 协议责任主体（DID 作为主体 ID） | `<role>_id` | 例：`actor_id`、`principal_id`、`subject_id`。 |
| 因果 / finality / proof / schema-profile reference | `<noun>_ref` / `<noun>_refs` | 例：`prev_refs`、`anchor_ref`、`schema_refs`、`policy_event_ref`。 |
| Blob / content-addressed / polymorphic reference | `<noun>_ref` / `<noun>_refs` | 例：`blob_ref`、`target_ref`、`from_ref`、`to_ref`。 |
| 原始 DID ecosystem material | `<role>_did` | 例：`service_did`、`pairwise_did`、`old_did`、`new_did`。 |

## 5. Event Batch Receipt Hash

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
    "event_digest": "sha256:..."
  },
  "events": ["sha256:..."],
  "created_at": "2026-04-26T00:00:00Z"
}
```

`receipt_digest = sha256(canonical_json(receipt_without_proofs))`。`issuer`、`receipt_scope`、`frontier`、`events`、`schema` 和 `type` 必须进入 digest，防止 receipt 被跨 actor、跨 Realm 或跨前沿重放。

## 6. Signature

默认 proof:

```json
{
  "kind": "detached_jws",
  "alg": "EdDSA",
  "verification_method": "did:web:alice.example#device-1",
  "event_digest": "sha256:...",
  "jws": "..."
}
```

Proof MUST bind:

- `event_digest = canonical_digest(event_without_proofs_unsigned)`
- `actor_id`
- `verification_method`
- `created_at`
- `domain` / `audience` where applicable

`detached_jws` 的 payload segment MUST be empty in compact serialization, but the detached bytes being signed MUST be the canonical proof binding object:

```json
{
  "event_digest": "sha256:<canonical event hash>",
  "actor_id": "<event.actor_id>",
  "verification_method": "<proof.verification_method>",
  "created_at": "<proof.created_at>",
  "domain": "<proof.domain if present>",
  "audience": "<proof.audience if present>"
}
```

Verifier 顺序固定为：先从 Event 中移除 `proofs` 与 `unsigned`，按 §1 canonicalize 并计算 `event_digest`；再与 `proof.event_digest` constant-time 比对；最后按上表字段构造 canonical binding object 并验证 detached JWS。实现 MUST NOT 直接签 HTTP envelope、transport metadata 或只签 `payload` 字段。

## 7. HLC

> **使用边界（normative）**：HLC 在 v1 是 **advisory** 字段。它 MUST NOT 进入授权决策、Lattice 收敛、Move precondition 比较、或 Anchor finality 判断；这些都由 Move `preconditions[]`、Anchor frontier 与 Lattice `join` 决定。HLC 在 v1 的唯一规范用途是 **timeline 派生层**——当两个事件在 `prev_refs` / `refs` 形成的因果图中互不可达时，HLC 作为 `(unix_ms, logical, node_id_hash)` 字典序 tie-breaker 使展示顺序确定。即便 HLC 进入 canonical event bytes 与 proof `event_digest`（出于 wire 兼容），实现 MUST NOT 把 HLC 数值当作可信时间戳，也 MUST NOT 据其反转因果或选 winner。详见 [`authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §5.2 与 [`sync/operations-sync.md`](../sync/operations-sync.md) §6。

Hybrid Logical Clock 编码：

```text
<unix_ms_hex>-<logical_hex>-<node_id_hash>
```

示例：

```text
01970e589d21-0004-a13f9c2e
```

字段规则：

- `unix_ms_hex` MUST 是 12 位小写十六进制毫秒时间戳。
- `logical_hex` MUST 是 4 位小写十六进制逻辑计数器，取值范围 `0000..ffff`。
- `node_id_hash` MUST 是 8 位小写十六进制稳定节点哈希；它只用于同一 `(unix_ms, logical)` 下的确定性 tie-break，不得替代因果关系或授权判断。
- 用户客户端的 `node_id_hash` MUST 从 Realm-scoped 或 deployment-scoped 的本地 node secret 派生，例如 `SHA256("contrix-hlc-v1" || realm_id || device_id || local_node_secret)[0:8]`。不得直接使用 principal DID、公开 handle、长期 device id 或跨 Realm 稳定标识作为 hash 输入。
- 服务 DID 产生的公开服务事件 MAY 使用 service-scoped node id，但服务若代表用户或 minimal-metadata Realm 转发/生成事件，MUST 使用 Realm-scoped pseudonymous node id，避免跨 Realm 关联。

排序按 `(unix_ms, logical, node_id_hash)` 字典序。

溢出规则：

- 生产者若在同一 `unix_ms` 内需要把 `logical_hex` 从 `ffff` 再递增，MUST NOT 回绕到 `0000`，也 MUST NOT 复用任何已发出的 HLC tuple。
- 遇到该情况时，生产者 MUST 采取以下两种行为之一：
  - 等待直到本地可生成更大的 `unix_ms_hex`，然后以 `logical_hex=0000` 生成新 HLC。
  - 在生成 canonical bytes 之前以本地临时错误终止该次写入，例如 `hlc_logical_overflow`，由调用方稍后重试。
- 生产者在等待或重试期间 MUST 保留原有 `prev_refs`、`refs[role=authorized_by]` 和 `actor_seq` 约束，不得仅为了逃避 overflow 而伪造更大的 wall clock skew。
- 消费者若观察到同一 producer 出现 `unix_ms` 不变、`logical_hex` 从 `ffff` 回绕到更小值且没有更大 `unix_ms`，MUST 将其视为无效 HLC，并以 `schema_violation`、`causal_conflict`、`soft_fail` 或 quarantine 处理；不得把它当作正常排序值接受。

v1 固定使用 4 位 `logical_hex`。该上限等价于单个 producer 每毫秒 65,536 个有序 HLC；超过该速率的批量写入应拆分到多个 actor/device producer、等待下一毫秒，或使用服务端批量入口排队。不得在 v1 中把 `logical_hex` 私自扩展到 6/8 位；需要更宽计数器时必须声明新的 HLC version 与 schema profile。

### 7.1 操作伪代码

发送事件：

```text
hlc = max(current_hlc, current_physical_ms)
if hlc.physical == current_physical_ms:
    hlc.logical += 1
else:
    hlc.physical = current_physical_ms
    hlc.logical = 0
```

接收带 HLC `hlc_remote` 的事件：

```text
physical = max(current_hlc.physical, current_physical_ms, hlc_remote.physical)
if physical == current_hlc.physical and physical == hlc_remote.physical:
    logical = max(current_hlc.logical, hlc_remote.logical) + 1
elif physical == current_hlc.physical:
    logical = current_hlc.logical + 1
elif physical == hlc_remote.physical:
    logical = hlc_remote.logical + 1
else:
    logical = 0
hlc = { physical, logical, node_id_hash = local_node_id_hash }
```

比较：

```text
function compare_hlc(hlc1, hlc2):
    if hlc1.physical_hex != hlc2.physical_hex:
        return parse_hex(hlc1.physical_hex) - parse_hex(hlc2.physical_hex)
    if hlc1.logical_hex != hlc2.logical_hex:
        return parse_hex(hlc1.logical_hex) - parse_hex(hlc2.logical_hex)
    return strcmp(hlc1.node_hex, hlc2.node_hex)
```

### 7.2 验证规则

实现 MUST：

- 用正则 `^[0-9a-f]{12}-[0-9a-f]{4}-[0-9a-f]{8}$` 验证 HLC 格式。
- 按本节的两层 drift 模型验证物理时间：超 `hard_future_skew_ms`（默认 300_000）MUST reject / quarantine；超 `expected_future_skew_ms`（默认 30_000）SHOULD soft-fail / quarantine。该校验是 envelope freshness / DoS guard，不是授权、Lattice winner、Move precondition 或 Anchor finality 输入；通过 drift 校验的 HLC 仍只可用于 timeline tie-breaker。
- profile MAY 通过 `state_event_expected_future_skew_ms` 对 state event（capability / membership / policy / service binding / Realm upgrade / MLS commit 等）施加更严窗口；未声明时按 `expected_future_skew_ms` 处理。
- 拒绝 `physical_hex > ffffffffffff` 的 HLC 值（物理时间溢出，需未来扩展 HLC profile 才可使用）。
- 维护本地单调性；本地时钟落后远端时推进到远端时间，超前时限制推进速率。

### 7.3 Timeline 排序与 winner 选择

客户端 timeline / backfill / 展示层默认事件排序：

```text
causal_depth ASC, hlc ASC, actor_id ASC, actor_seq ASC, event_id ASC
```

协议状态不再使用 timeline 排序选择 winner。Move precondition、Anchor frontier 与 Lattice join 决定当前 cell value；并发不可合并时返回 structured bottom。Timeline 展示顺序与 cell value 是两种不同 projection：前者排历史，后者由 Lattice 计算。实现 MUST 在 profile 中明确使用哪一个，不得把 timeline 中最后出现的 Event 直接当作状态 value。

客户端只有在已知 causal closure 足以判断两个 Event 在 `prev_refs` 与 `refs[role="after"]` 图中互不可达时，才可把 HLC 用作最终 timeline tie-breaker。若 backfill、dependency fetch 或 snapshot-assisted verification 尚未补齐到可判断互不可达，客户端 MUST 把排序标记为 provisional（例如 pending/backfilling），或使用 `created_at` / 本地接收序作为临时 UI 占位；不得把 HLC 排序结果写入持久 projection、审计导出或任何声称“最终顺序”的视图。

## 8. Cursor

Cursor 是不透明字符串：

```text
cx:cursor:<base64url>
```

### 8.1 客户端契约

- 客户端 MUST 把 cursor 当作不透明字符串。
- 客户端 MUST NOT 解码、解析或修改 cursor 内容。
- 客户端 MUST 存储最新 stream `cursor`（来自 `/account/subscribe` frame 或分页响应）用于恢复。
- 客户端 MUST 在下次同步 / 查询请求中按原样使用 cursor。

### 8.2 服务端 canonical 内部结构

服务端在 base64url 编码前将 cursor 内部结构编码为 canonical JSON（按 §2 规则）。**v1 cursor 内部结构 MUST 遵循下方 schema**，与 [`cursor.schema.json`](../../artifacts/schemas/cursor.schema.json) 一致；目的是让客户端在 Principal Server 之间迁移时目标服务器有能力解析旧 cursor 并生成等价本地 cursor。客户端 MUST NOT 解析或修改 cursor；**服务器侧的 cursor 内部结构必须遵循本节 schema，不得使用私有形态**。

cursor 是 v1 中**唯一**的不透明 token 类型，统一承担增量同步、列表分页、写后读屏障所有用途。`purpose` 字段区分两个语义：`stream`（增量同步与列表分页，出现位置：`after` / `before` / `prev_cursor` / `next_cursor`）与 `barrier`（写后读屏障，出现位置：写接口响应中的 `cursor` 字段、`X-Contrix-Wait-For` header）。

Stream 形态：

```json
{
  "v": "1",
  "purpose": "stream",
  "t": "2026-04-26T00:00:00.000Z",
  "s": {
    "cx:realm:0196419b-0000-7000-8000-000000000000": {
      "p": ["cx:event:019640ed-8000-7000-8000-000000000000"],
      "o": "01970e589d21-0004-a13f9c2e",
      "h": "sha256:abc123..."
    }
  },
  "d": {
    "cx:device:019640da-0000-7000-8000-000000000000": "cx:device_message:019640da-0000-7000-8000-000000000000"
  },
  "x": 1714080000000
}
```

Barrier 形态：

```json
{
  "v": "1",
  "purpose": "barrier",
  "t": "2026-04-26T00:00:00.000Z",
  "target": {
    "event_id": "cx:event:019640ed-8000-7000-8000-000000000000",
    "event_digest": "sha256:abc123...",
    "realm_id": "cx:realm:0196419b-0000-7000-8000-000000000000"
  },
  "x": 1714080000000
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `v` | string | 是 | cursor 版本，v1 固定 `"1"` |
| `purpose` | enum(`stream`,`barrier`) | 是 | 用途鉴别 |
| `t` | timestamp | 是 | 生成时间戳 |
| `s` | object | stream 时可有（仅 stateless 形态） | Realm 位置映射 |
| `s.<realm_id>.p` | array | 是（每条 entry） | 因果前沿（事件 ID 集合） |
| `s.<realm_id>.o` | string | 是（每条 entry） | timeline 排序 HLC |
| `s.<realm_id>.h` | hash | 是（每条 entry） | 该位置的 state hash |
| `d` | object | stream 时可有（仅 stateless 形态） | 设备位置映射 |
| `target` | object | `purpose=barrier` 且 stateless 时必填 | 等待目标 event |
| `target.event_id` | id:event | 是（barrier stateless） | 目标事件 ID |
| `target.event_digest` | hash | 是（barrier stateless） | 目标事件 canonical digest |
| `target.realm_id` | id:realm | 否 | 目标事件所在 Realm（可选 hint） |
| `x` | integer | 是 | 过期时间戳（Unix ms） |
| `h` | string | stateful 形态必填 | 服务端 opaque handle（≥ 128 bit 熵），见 §8.3.1 |
| `issuer_kid` | string | stateless 形态必填 | `_mac` / `_sig` 的 issuing service cursor key id；用于 key rotation / revocation 选择。stateful 形态禁止出现。 |
| `_mac` / `_sig` | string | stateless 形态必填 | 完整性保护字段，见 §8.3.1 |

服务端 MAY 添加其它 `_` 开头的私有字段（如 `_compression`）用于本地优化；这些字段不参与 §8.4 cursor 翻译，必须先于 base64url 编码进入 canonical bytes，并 MUST 进入 `_mac` / `_sig` transcript。

### 8.3 验证规则

服务端接收 cursor 时 MUST 验证：

1. 前缀以 `cx:cursor:` 开头。
2. 其余部分是合法 base64url。
3. 解码后 `v` 是支持的版本。
4. 解码后 `purpose` 是 `stream` 或 `barrier`。
5. 解码后 `x` 在未来（允许 5 分钟时钟偏差）。
6. 解码后是合法 JSON。
7. 所有 `realm_id` 是合法 `cx:realm:*` 格式（如 `s` 出现）。
8. 因果前沿中的所有 event id 合法（如 `s` 出现）。
9. timeline 排序是合法 HLC 格式（如 `s` 出现）。
10. `purpose=barrier` + stateless 形态时 `target.event_id` 与 `target.event_digest` 必填。
11. cursor 出现的位置与 `purpose` 一致（barrier cursor 出现在 `/account/subscribe after=`、`before`、`after`、`prev_cursor` / `next_cursor` 上下文 MUST `invalid_param`，stream cursor 出现在 `X-Contrix-Wait-For` 上下文 MUST `invalid_param`）。
12. **TTL 硬上限**：以 `t` 解析为 Unix ms 后，`x - t_ms` MUST 满足以下硬上限：barrier cursor ≤ 3,600,000 ms（1 小时），stream cursor ≤ 604,800,000 ms（7 天）。超出上限的 cursor 视为 issuing 服务的协议错误，接收方 MUST reject `invalid_param`。理由：barrier cursor 仅是 RYW 等待屏障，过期意义随 frontier 追上而失去；stream cursor 在数周活动后已无因果对齐价值。
13. **形态互斥**（schema `oneOf` 强制）：cursor body MUST 满足下列二选一：
    - **stateless** — 含 `issuer_kid` 且含 `_mac` 或 `_sig`（至少一个），不含 `h`；可携带 `s` / `d` / `target`。
    - **stateful** — 含 `h`（opaque handle），不含 `_mac` / `_sig` / `s` / `d` / `target` / `issuer_kid`。
    
    两种形态同时出现或都不出现 MUST reject `invalid_param`。

非法 cursor MUST reject，错误 `invalid_param`；已过期 cursor MUST reject，错误 `cursor_expired`；完整性校验失败（见 §8.3.1）MUST reject，错误 `cursor_integrity_invalid`。

### 8.3.1 完整性校验（normative）

服务端 MUST 在使用客户端回传的 cursor 推进任何不可逆 server-side state（to-device ack、`/account/subscribe after=` resume、`X-Contrix-Wait-For` barrier 解除、`dropped` / `resync_required` 恢复等；详见 [`client-sync.md` §10 / §12](../sync/client-sync.md)）之前，执行下列完整性校验。仅通过 §8.3 语法 / TTL / purpose 校验不足以信任 cursor 内部状态。

**Stateless 形态（含 `_mac` 或 `_sig`）**：

- `_mac` MUST 是 HMAC over canonical bytes（除 `_mac` 自身外的所有字段，按 §2 RFC 8785 JCS 规则）；算法 MUST 是 HMAC-SHA-256 或更强；密钥由 issuing service 持有并按 `issuer_kid` 标识。
- `_sig` MUST 是 detached signature over same canonical bytes；签名密钥使用 issuing service 的 cursor-signing key。
- transcript MUST 绑定：`purpose`、`principal_id`、`device_id`、`service_did` / `service_id`、`filter_digest`、stream positions（`s` / `d`，如出现）、`target`（barrier 时）、`x`、`issuer_kid`。
- 服务端 MUST 用当前 cursor key 重算 transcript 并与 `_mac` / `_sig` 比较；任一字段不匹配当前 authenticated request 的 principal / device / service / `filter_digest` / purpose → `cursor_integrity_invalid`。

**Stateful 形态（含 `h`）**：

- `h` MUST 是 issuing service 生成的不可猜测 handle（解码后熵 ≥ 128 bit）。
- 服务端 MUST 以 `h` 查 issuing service 本地表，记录绑定的 `(principal, device, service, filter_digest, purpose, positions, target?, expiry)` 元组。
- handle 不存在、已撤销、已过期，或绑定字段与当前 authenticated request 不匹配 → `cursor_integrity_invalid`。
- handle 校验本身就是完整性校验 — cursor body 不可加 `_mac` / `_sig`。

无论哪种形态，完整性校验失败 MUST 映射 `cursor_integrity_invalid`（区别于 `cursor_expired`：前者是 tamper / cross-binding / 未知 handle，后者是 TTL 超时）。客户端收到 `cursor_integrity_invalid` 后应清理本地 cursor 缓存并按 [`client-sync.md` §12.3](../sync/client-sync.md) 恢复流程重做 initial sync。

### 8.4 Cursor 可迁移性

Cursor 对客户端不透明，但 **stateless 形态服务器之间可解析**。当用户从 Principal Server A 切换到 Principal Server B 时（service replacement、portability 平面操作），B SHOULD 支持以下迁移路径之一：

1. **直接 reparse（仅 stateless 形态）**：B 收到 `after=cx:cursor:<base64url_from_A>` 时，按 §8.2 canonical schema 解码，提取 `s.<realm_id>.{p,o,h}` 与 `d` 信息，翻译为 B 本地 cursor 内部表示。前提是 A 与 B 看见相同 Realm 历史、且 `purpose=stream`、且 cursor 是 stateless 形态（含 `s` / `d`，不含 `h`）。B 在生成本地等价 cursor 时 MUST 用自己的 cursor key 重签 `_mac` / `_sig`（A 的 transcript 与 B 不兼容），不得直接复用 A 的 `_mac`。barrier cursor 不可跨服务迁移（`target.event_digest` 已绑定到原服务的 frontier）。
2. **stateful 形态不可跨服务迁移**：含 `h` 的 cursor 中 handle 是 A 本地表的引用，B 无法解析。B 收到 stateful 形态 cursor 时 MUST 返回 `cursor_unrecognized`，客户端按全新初始同步处理。这是 stateful 形态在 portability 上的固有取舍。
3. **重置兜底**：B 不支持直接 reparse 时 MUST 返回 `cursor_unrecognized`（不是 `cursor_expired`），客户端按全新初始同步处理；不得静默丢失因果对齐。
4. **可选 translate 端点**：未来 profile 可能在 `cx.profile.principal_server.v1` 之上引入 `POST /api/v1/account/translate-cursor`；该端点不属于 v1 强制范围。

`_` 前缀的服务器私有字段（`_compression`）在迁移时可被丢弃；canonical 字段（`v` `t` `s` `d` `x`）足以恢复 frontier。`_mac` / `_sig` MUST 由目标服务器用自己的 key 重新生成（不可跨服务复用）。

### 8.5 测试向量入口

可执行向量位于：

- [`spec/v1/artifacts/fixtures/encoding-fixture.json`](../../artifacts/fixtures/encoding-fixture.json)

向量覆盖点：cursor 版本字段与过期、per-realm frontier 编码、device message 位置、过期 token 回退、非法额外字段拒绝。

### 8.6 一致性

声明支持 Contrix v1 同步的实现 MUST：

- 以不透明字符串形式接受和传输版本 1 cursor。
- 服务端 MUST 接收时验证所有 cursor 字段。
- 服务端 MUST 按 §8.2 canonical schema 编码 cursor 内部结构（私有字段限于 `_` 前缀）。
- 客户端 MUST NOT 解析 cursor 内容。
- 支持每个 cursor 至少 50 个 realm。
- **每 Realm 的 frontier (`s.<realm>.p`) 长度 MUST ≤ 1000 个 event_id**：超出时 issuing 服务 MUST 用 `event_set_commitment.root` 或 snapshot pointer 折叠 frontier，再嵌入 cursor。该上限避免大并发 actor Realm (≥ 1000 active actor 各自有 head event) 让单个 cursor 膨胀到 MB 级。Receiver 收到超长 frontier 的 cursor MUST `invalid_param`。
- **整个 cursor base64url 解码后 canonical bytes MUST ≤ 64 KiB**：超出时 issuing 服务 MUST 用 snapshot pointer / commitment hash 折叠，不得直接产出超大 cursor；receiver 收到超大 cursor MUST `invalid_param`。
- 支持最长 7 天（604,800,000 ms）的 stream cursor 过期时间；barrier cursor 上限 1 小时（3,600,000 ms），见 §8.3 规则 12。
- 以适当错误拒绝非法 cursor。

## 9. Rank

列表排序 rank MUST 使用 `cx.rank.lexofractional.v1` profile，除非 Realm schema 显式声明其他 rank profile。

规则：

- 字符集固定为 ASCII `0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz`，按该字符集顺序比较。
- Rank MUST 是 1..128 字符的字符串，且每个字符 MUST 来自上述字符集。
- 排序 MUST 使用逐字符字典序；若一个字符串是另一个字符串的前缀，较短者排在较前。
- `rank_between(left, right)` MUST 返回一个严格满足 `left < rank < right` 的 rank，或返回规范错误 `rank_exhausted`。`left` 或 `right` MAY 为空，表示容器开头或结尾的哨兵边界。
- 标准 midpoint 算法 MUST 是有界算法，不能在无间隙边界无限循环。参考伪代码：

```text
alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
base = len(alphabet)
min = -1
max = base

rank_between(left, right):
  assert left == "" or all chars in alphabet
  assert right == "" or all chars in alphabet
  assert right == "" or left == "" or left < right
  prefix = ""
  i = 0
  while len(prefix) < 128:
    l = value(left[i]) if i < len(left) else min
    r = value(right[i]) if right != "" and i < len(right) else max
    if r - l > 1:
      return prefix + alphabet[floor((l + r) / 2)]
    if i < len(left):
      prefix += left[i]
    else:
      prefix += alphabet[0]
      if right != "" and prefix == right:
        return rank_exhausted
      return prefix
    i += 1
  return rank_exhausted
```

例如 `rank_between("", "0")` MUST 返回 `rank_exhausted`，因为在 start sentinel 与最小 rank `"0"` 之间不存在合法 rank。客户端或 reducer 遇到 `rank_exhausted` MUST 触发 rebalance 或要求调用方提交 `cx.container.rebalance`，不得生成非法 rank。
- 当 rank 长度超过 128，或连续插入导致实现无法生成短 rank，客户端 SHOULD 请求或提交 `cx.container.rebalance`。Reducer 不得接受超过 128 字符的 rank。
- 同一 container 内 rank 完全相同的对象 MUST 按 `rank_source_hlc`、`rank_source_actor_id`、`rank_source_event_id`、`object_id` 继续排序；如果 rank source 元数据缺失，MUST 使用 `object_id` 作为最终稳定 tie-break，并在 conformance report 中声明降级。
- `cx.container.rebalance` 的 assignment 生成 MUST 基于权限裁剪前的 canonical ordered set。先按 reducer 已确定的稳定顺序排列 active edges，再选择最小宽度 `w`，使 `alphabet_length^w >= 2 * (item_count + 1)`；第 `i` 个对象（1-based）的 rank number 为 `floor(i * alphabet_length^w / (item_count + 1))`，以固定宽度 base62 编码并用 alphabet 第一个字符左填充。若所需 `w > 128`，实现 MUST 拒绝该 rebalance。
- Rebalance assignments MUST 覆盖 container 内全部 active edges，且不得新增、删除或跨 container 移动 edge。CAS 的 `expected_state_digest` 不匹配时，MUST 拒绝整个 operation，不得部分应用。

## 9.5. Composite Cell Subject

部分 cell 的 subject 由多个 sub-component 复合派生（例如 `cx.device.authorize` 的 `(principal_id, device_id)`）。复合 subject 的 canonical 形态由本节定义；cell id、Move precondition、Lattice join 和 fixture 必须使用同一形态。

### 9.5.1 通用规则

- 复合 subject 的 canonical wire 形态 MUST 是 base64url（无 padding）编码的 SHA-256 digest：

  ```text
  cell_subject = base64url_nopad(sha256(canonical_json(components_array)))
  ```

  其中 `components_array` 是按本规范声明的固定顺序排列的 JSON array，所有 string element 已经 normalize 过（NFC、小写 typed ID、规范 DID）。
- 实现不得直接使用 `a|b|c` 这种管道分隔字符串作为复合 subject。canonical cell id、签名输入、state map 索引必须使用 hash 形态。
- 复合 subject 的 sub-component 必须存在于 Move effect value 或兼容 Event payload 的具名字段中。
- 同一 standard cell family 的 `components_array` schema 由本规范固定，profile 不得擅自增删字段或重新排序。

### 9.5.2 标准复合 Subject

| Cell family / Event kind | components_array 顺序（来源字段） |
| --- | --- |
| `cx.component.device.authorization.v1` / `cx.device.authorize` | `[principal_id, device_id]` |
| `cx.component.device.authorization.v1` / `cx.device.revoke` | `[principal_id, device_id]` |

`principal_id` MUST 是无 fragment 的完整 DID URI（见 §4）；`device_id` MUST 是完整 `id:device` typed ID（`cx:device:<uuidv7>`）。

非复合 cell（例如 member 用 actor DID、capability grant 用 grant id、Realm policy 用 Realm id）直接把规范化 subject 放入 `cx:cell:<component>:<subject>`，不需要 hash 化。

接收方收到不符合本节定义的复合 subject components_array 时 MUST 返回 `schema_violation`。文档中若以管道分隔形态展示复合 subject，MUST 显式标注 "informational; canonical cell subject is base64url(sha256(canonical_json(...)))"。

## 10. Encrypted Envelope Digest

加密 payload 的 digest MUST 覆盖密文和明文路由元数据：

```text
payload_digest = sha256(canonical_json(cleartext_metadata) || ciphertext_bytes)
```

`cleartext_metadata` 至少包含 `encryption`、`epoch` 与 `content_type`；当 envelope 带 `aad` 时，`aad` MUST 进入 `cleartext_metadata` 后一起参与 digest。实现 MUST NOT 使用明文 payload 作为 `payload_digest` 输入。

### 10.1 AEAD nonce uniqueness（normative）

任何在 v1 wire 上承载 AEAD 加密内容的 envelope（`encrypted_payload`、blob attachment、`to_device` payload 等）MUST 满足 AEAD nonce 唯一性 contract：

- **绝对禁止**:在同一 `key_ref` 下重用 nonce — AEAD 在 nonce 复用时机密性 + 完整性同时被打破，影响所有曾用该 (key, nonce) 加密的密文。
- **派生形态**:nonce MUST 从 MLS exporter secret 派生的 `nonce_key` 与 per-device `(device_id, monotonic_counter)` 通过 HMAC 派生而来; exporter context MUST 绑定 canonical `key_ref`、MLS `epoch` 和 AEAD purpose,具体公式与字段 schema 见 [`crypto-media/media-and-blob.md` §3.1](../crypto-media/media-and-blob.md)。
- **不允许 fallback 到 random**:96-bit AEAD (AES-GCM) 在 ~2^48 次操作上有显著 birthday-bound 碰撞率;Contrix MLS application key 跨多设备共享,naive random nonce **不满足** v1 normative。
- **接收方 replay 防护**:接收方 MUST 维护 per-`(key_ref, epoch, device_id)` 已见 counter 集合或等价无误判结构，重复 counter MUST 触发 `failed_precondition` reason=`aead_nonce_counter_replay`。
- **AAD binding**:AEAD AAD MUST 绑定 `(key_ref, ciphertext_digest, nonce)` canonical 形态，防止 (key, nonce) 下的 ciphertext 被与另一 AAD 配对解密。
- **不同 AEAD 用途独立 nonce 域**:`label` 输入 MUST 至少包含 purpose 子域(例如 `"contrix-aead-nonce-derivation-v1"` + purpose),避免 `blob-attachment` 与 `to-device` 共享 nonce 计数器。
