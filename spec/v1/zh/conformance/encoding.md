---
title: Encoding, IDs, Hashes, Signatures
sidebar:
  label: Encoding & IDs
---

## 1. 目标

本文定义 Contrix 的 canonical encoding、ID、hash、signature、cursor、HLC 与 rank 编码规则，确保不同实现能得到相同 digest 和验证结果。

## 2. Canonical JSON

Contrix canonical JSON 是签名、hash、event digest、receipt digest、snapshot commitment 和 cursor 内部状态的唯一编码 profile。实现 MAY 复用 RFC 8785 / JCS 类库，但最终输出必须满足本节的收窄规则和 `conformance-vectors.md` 的测试向量。

Contrix canonical JSON MUST 使用：

- UTF-8 不带 BOM；输入若包含 UTF-8 BOM（`U+FEFF` 编码 `EF BB BF`，无论出现在 stream 起始还是 string value 内部）、malformed UTF-8、孤立 surrogate 或无法被 JSON parser 唯一解释的字符串，MUST reject。`U+FEFF` 在 string value 中只允许作为 zero-width no-break space 的语义存在，但 v1 canonical JSON 不允许此用法——任何 `U+FEFF` 出现都按 schema_violation 拒绝。
- object key 按 Unicode code point 升序排序，并在每一层独立排序。
- 无 insignificant whitespace。
- JSON object 中的重复 key MUST reject，不得采用“最后一个 wins”或“第一个 wins”。
- number MUST 使用 RFC 8785 / JCS 等价的唯一 decimal serialization；NaN、Infinity、-Infinity、`-0`、无法精确往返的 number、超出实现声明精度范围的 number MUST reject。**v1 wire MUST NOT 使用非整数 number**：所有签名 canonical object 的 number 字段 MUST 是 JSON integer。比例、置信度、进度等小数值 MUST 编码为整数 + 显式 scale（推荐字段后缀 `_basis_points` 表示万分数 0..10000，或 `_x1000`、`_x1000000` 等明确比例）；`confidence_basis_points: 7500` 表示 75.00%。这条收紧规则取消了"何时允许 number canonicalization"的可选语义，使签名输入 100% 确定。
- timestamp 使用 RFC 3339 UTC，尾部 `Z`；签名输入不得接受本地时区、隐式时区或 leap-second 变体。
- 字段名使用 snake_case。

Event Envelope 的签名和 hash 输入 MUST 是去除 `proofs` 与 `unsigned` 后的 canonical JSON bytes，并且 MUST 保留 `event_id`。`unsigned` 是传输/本地附加信息，不得影响 event digest 或 proof `payload_hash`。实现不得对已经签名的 bytes 做大小写规范化、ID 前缀补全、字段默认值补写、key 重排以外的语义改写。

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
| Handle / DNS handle | ✓ | ✓ | ✓ |
| Connection identifier（email / phone canonical 形态） | ✓ | ✓ | ✓（local part）|
| Organization name | ✓ | ✓ | ✓ |
| Display name | ✓ | ✓ | 仅 SHOULD（默认开启 confusable warning，用户 opt-out）|
| Title / summary / body 等正文字段 | ✓ | — | — |
| Schema id / event kind / cell family 等 protocol identifier | ✓ | ASCII-only（schema 已 enforce） | — |

为什么把 NFKC + confusable 限定在身份相关字段而不是全字段：正文（Flow.body、Message.content）允许任何脚本混排是合理的（中文夹拉丁、阿拉伯夹希伯来），不能强制 single-script。但身份相关字段是 trust UI 决策点，必须 reject 同形字攻击。

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
| `sha256` | 32 bytes（64 hex） | **v1 default**；所有 receiver MUST 支持。Event digest、payload_hash、Merkle leaf、state_root、blob CID、receipt hash 等核心字段默认使用。 | 不抗量子（Grover 把搜索成本减半到 2^128，仍可用）；适合 v1 → v2 过渡。 |
| `sha512` | 64 bytes（128 hex） | v1 optional；声明 `cx.profile.hash.sha512.v1` 的实现 MUST 支持。可用于高安全 Space 的 state_root、blob CID、long-lived audit hash。 | 与 sha256 同族；选择仅出于 digest size。 |
| `sha3_256` | 32 bytes（64 hex） | v1 optional；声明 `cx.profile.hash.sha3.v1` 的实现 MUST 支持。提供 Keccak family 抗碰撞冗余，与 sha256 family 形成 algorithm diversity。 | 与 sha256 不同结构家族，抗结构性新攻击。 |
| `blake3` | 32 bytes（64 hex） | v1 optional；声明 `cx.profile.hash.blake3.v1` 的实现 MUST 支持。性能最佳；blob CID 与高吞吐场景推荐。 | sha256-class 抗碰撞；非 NIST 但被 IRTF / RFC 路径认可。 |

未来 v1.x MAY 通过新的 profile 加入抗量子 hash（如 SLH-DSA hash family、SHAKE256 派生），但 v1 wire 形态 `<algo>:<hex>` 已经为这种加法准备好——**无需重写 wire**。

实现 MUST：

- 默认按 `sha256:` 解析；遇到未识别的 algo prefix → 若位于 critical field（payload_hash、state_root、prev_refs blob hash）→ fail closed (`unsupported_hash`)；若位于非 critical metadata（如对象的 derived fingerprint）→ MAY 记录为 unknown 并 preserve raw bytes。
- 在 `server/describe.crypto` 暴露支持的 hash algo 集合；client 可据此选择写入算法。
- 不得"算法升级"已签名的 canonical bytes：一旦 Event 用 `sha256:` 发布，verify 路径永远按 sha256 重算；不能因为本地默认换成 blake3 就重算并替换。

### 3.3 State Root 与 Anchor Hash 编码

`state_root`、Anchor `id`、Move `id`、receipt hash 这几条核心承诺字段的 wire 形态由所属 Space 在 create event 中通过 `hash_profile` 字段固定（默认 `sha256`）。Space 内所有后续 Anchor / Move / state_root MUST 使用同一 algo；切换需要通过 v1 → v1.x snapshot commitment + signed compaction Anchor 在 frontier 上做一次 algorithm transition Anchor，新旧 algo 都能在 transition Anchor 上验证 inclusion。详细规则见 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §4.2.5（hash transition）。

### 3.4 Multihash 兼容（profile-gated）

声明 `cx.profile.encoding.multihash.v1` 的实现 MAY 在 wire 上接受 multihash 风格的二进制 hash header（multicodec varint + length + digest）作为额外 reading format，但 canonical JSON 上的 wire value 仍 MUST 使用 §3.1 的 `<algo>:<hex>` 字符串形态。引入 multihash profile 的目的是与 IPFS / libp2p / Iroh 生态做内容寻址互通；它不替换 v1 wire 默认。

## 4. ID

协议 wire / canonical object 层的 typed ID 格式：

```text
cx:<kind>:<ulid>
```

标准 `kind` 的机器可读 source of truth 是 `artifacts/registry/id-kind-registry.json`。本文只定义通用规则。

`cx:` 前缀表示 Contrix 协议命名空间；`<kind>` 表示对象或引用类型；`<ulid>` 是该类型下的稳定 ID。完整 typed ID 是 wire value 的一部分，MUST 出现在：

- Event Envelope、canonical object、receipt、snapshot、fixture 和 OpenAPI / non-HTTP DTO。
- canonical JSON、签名 payload、`payload_hash`、event digest、cursor 内部 state、federation payload、audit log。
- 跨服务引用、日志和错误响应中需要自描述对象类型的字段。

数据库或本地索引实现 MAY 不把 `cx:<kind>:` 前缀作为主键的一部分存储。例如 `receipts` 表可以只存 `d1sc01j0000000000000000000`，因为表名或显式 `kind` 列已经提供类型上下文。实现若这样存储，MUST 在进入 canonical JSON、签名、hash、联邦转发、sync cursor、audit replay 或 API response 前恢复完整 typed ID。接收方验证签名、hash、backfill 或 replay 时，MUST 按完整 typed ID 比较，不得用数据库 row id、自增 id、表名推断或隐式转换替代 wire value。

`<kind>` 是 canonical bytes 的一部分。实现不得把 `cx:receipt:<id>` 改写成 `cx:event:<id>`，也不得因为字段名叫 `receipt_id` 就在验证时补前缀。字段名可以辅助 schema 校验，但不能替代 signed wire ID。

v1 wire、JSON Schema、registry、fixture 和所有签名 canonical object 中的 ULID 部分 MUST 使用小写 Crockford Base32 字符集 `[0-9a-hjkmnp-z]`，并且不得包含 `i`、`l`、`o`、`u`。外部导入数据 MAY 使用大写 ULID；实现必须在生成 v1 Event Envelope、object id、cursor payload 或 proof `payload_hash` 前把它规范化为小写。已经进入签名 canonical bytes 的 ID 不得在验证、转发、backfill 或审计回放时重写大小写。

特殊 ID/ref 形式：

- `cx:cursor:<base64url>` 是 opaque token，不是 typed ULID object ID。
- `cx:blob:sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` 是内容寻址 Blob ref；`cx:blob:01js0bm0000000000000000000` 是 Blob metadata ID。二者不得混用。
- `cx:mls:<profile>:<profile_id>`、`cx:pseudonym:<scope_id>:<random>` 等 profile-scoped form 必须由对应 profile 注册和校验。

自定义 profile 若新增 `cx:<kind>:` 前缀，MUST 在 profile registry 或扩展 registry 中声明 kind、wire form、存储边界和校验规则。未注册的 `cx:<kind>:` typed ID MUST 被视为未知 critical wire type，除非所在字段明确允许 opaque string。

## 5. Event Batch Receipt Hash

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
    "event_hash": "sha256:..."
  },
  "events": ["sha256:..."],
  "created_at": "2026-04-26T00:00:00Z"
}
```

`receipt_hash = sha256(canonical_json(receipt_without_proofs))`。`issuer`、`scope`、`frontier`、`events`、`schema` 和 `type` 必须进入 hash，防止 receipt 被跨 actor、跨 Space 或跨前沿重放。

## 6. Signature

默认 proof:

```json
{
  "kind": "detached_jws",
  "alg": "EdDSA",
  "verification_method": "did:web:alice.example#device-1",
  "payload_hash": "sha256:...",
  "jws": "..."
}
```

Proof MUST bind:

- payload hash
- actor DID
- verification method
- domain / audience where applicable
- created_at

## 7. HLC

> **使用边界（normative）**：HLC 在 v1 是 **advisory** 字段。它 MUST NOT 进入授权决策、Lattice 收敛、Move precondition 比较、或 Anchor finality 判断；这些都由 Move `preconditions[]`、Anchor frontier 与 Lattice `join` 决定。HLC 在 v1 的唯一规范用途是 **timeline 派生层**——当两个事件在 `prev_refs` / `auth_refs` 形成的因果图中互不可达时，HLC 作为 `(unix_ms, logical, node_id_hash)` 字典序 tie-breaker 使展示顺序确定。即便 HLC 进入 canonical event bytes 与 proof `payload_hash`（出于 wire 兼容），实现 MUST NOT 把 HLC 数值当作可信时间戳，也 MUST NOT 据其反转因果或选 winner。详见 [`authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §5.2 与 [`sync/operations-sync.md`](../sync/operations-sync.md) §6。

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
- 用户客户端的 `node_id_hash` MUST 从 Space-scoped 或 deployment-scoped 的本地 node secret 派生，例如 `SHA256("contrix-hlc-v1" || space_id || device_id || local_node_secret)[0:8]`。不得直接使用 principal DID、公开 handle、长期 device id 或跨 Space 稳定标识作为 hash 输入。
- 服务 DID 产生的公开服务事件 MAY 使用 service-scoped node id，但服务若代表用户或 minimal-metadata Space 转发/生成事件，MUST 使用 Space-scoped pseudonymous node id，避免跨 Space 关联。

排序按 `(unix_ms, logical, node_id_hash)` 字典序。

溢出规则：

- 生产者若在同一 `unix_ms` 内需要把 `logical_hex` 从 `ffff` 再递增，MUST NOT 回绕到 `0000`，也 MUST NOT 复用任何已发出的 HLC tuple。
- 遇到该情况时，生产者 MUST 采取以下两种行为之一：
  - 等待直到本地可生成更大的 `unix_ms_hex`，然后以 `logical_hex=0000` 生成新 HLC。
  - 在生成 canonical bytes 之前以本地临时错误终止该次写入，例如 `hlc_logical_overflow`，由调用方稍后重试。
- 生产者在等待或重试期间 MUST 保留原有 `prev_refs`、`auth_refs` 和 `actor_seq` 约束，不得仅为了逃避 overflow 而伪造更大的 wall clock skew。
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
hlc = max(current_hlc, current_physical_ms, hlc_remote)
if hlc.physical == current_physical_ms or hlc.physical == hlc_remote.physical:
    hlc.logical += 1
else:
    hlc.logical = 0
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
- 按 [`event-auth-state-resolution.md` §3](../authz/event-auth-state-resolution.md) 的两层 drift 模型验证物理时间：超 `hard_future_skew_ms`（默认 300_000）MUST reject / quarantine；超 `expected_future_skew_ms`（默认 30_000）SHOULD soft-fail / quarantine。
- profile MAY 通过 `state_event_expected_future_skew_ms` 对 state event（capability / membership / policy / service binding / Space upgrade / MLS commit 等）施加更严窗口；未声明时按 `expected_future_skew_ms` 处理。
- 拒绝 `physical_hex > ffffffffffff` 的 HLC 值（物理时间溢出，需 v2 HLC profile 才可使用）。
- 维护本地单调性；本地时钟落后远端时推进到远端时间，超前时限制推进速率。

### 7.3 Timeline 排序与 winner 选择

客户端 timeline / backfill / 展示层默认事件排序：

```text
causal_depth ASC, hlc ASC, actor_id ASC, actor_seq ASC, event_id ASC
```

协议状态不再使用 timeline 排序选择 winner。Move precondition、Anchor frontier 与 Lattice join 决定当前 cell value；并发不可合并时返回 structured bottom。Timeline 展示顺序与 cell value 是两种不同 projection：前者排历史，后者由 Lattice 计算。实现 MUST 在 profile 中明确使用哪一个，不得把 timeline 中最后出现的 Event 直接当作状态 value。

## 8. Cursor

Cursor 是不透明字符串：

```text
cx:cursor:<base64url>
```

### 8.1 客户端契约

- 客户端 MUST 把 cursor 当作不透明字符串。
- 客户端 MUST NOT 解码、解析或修改 cursor 内容。
- 客户端 MUST 存储最新 `next_batch` cursor 用于恢复。
- 客户端 MUST 在下次同步请求中按原样使用 cursor。

### 8.2 服务端 canonical 内部结构

服务端在 base64url 编码前将 cursor 内部结构编码为 canonical JSON（按 §2 规则）。**v1 cursor 内部结构 MUST 遵循下方 schema**，目的是让客户端在 Principal Server 之间迁移时目标服务器有能力解析旧 cursor 并生成等价本地 cursor。客户端 MUST NOT 解析或修改 cursor；**服务器侧的 cursor 内部结构必须遵循本节 schema，不得使用私有形态**。

```json
{
  "v": "1",
  "t": "2026-04-26T00:00:00.000Z",
  "s": {
    "cx:space:01js0sp0000000000000000000": {
      "p": ["cx:event:01js0ev0000000000000000000"],
      "o": "01970e589d21-0004-a13f9c2e",
      "h": "sha256:abc123..."
    }
  },
  "d": {
    "cx:device:01js0dm0000000000000000000": "cx:devmsg:01js0dm0000000000000000000"
  },
  "x": 1714080000000
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `v` | string | 是 | cursor 版本，v1 固定 `"1"` |
| `t` | timestamp | 是 | 生成时间戳 |
| `s` | object | 是 | Space 位置映射 |
| `s.<space_id>.p` | array | 是 | 因果前沿（事件 ID 集合） |
| `s.<space_id>.o` | string | 是 | timeline 排序 HLC |
| `s.<space_id>.h` | hash | 是 | 该位置的 state hash |
| `d` | object | 否 | 设备位置映射 |
| `x` | integer | 是 | 过期时间戳（Unix ms） |

服务端 MAY 添加 `_` 开头的私有字段（如 `_compression`、`_mac`）用于本地优化或签名；这些字段不参与 §8.4 cursor 翻译，必须先于 base64url 编码进入 canonical bytes。

### 8.3 验证规则

服务端接收 cursor 时 MUST 验证：

1. 前缀以 `cx:cursor:` 开头。
2. 其余部分是合法 base64url。
3. 解码后 `v` 是支持的版本。
4. 解码后 `x` 在未来（允许 5 分钟时钟偏差）。
5. 解码后是合法 JSON。
6. 所有 `space_id` 是合法 `cx:space:*` 格式。
7. 因果前沿中的所有 event id 合法。
8. timeline 排序是合法 HLC 格式。

非法 cursor MUST reject，错误 `invalid_cursor`。

### 8.4 Cursor 可迁移性

Cursor 对客户端不透明，但**服务器之间不再不透明**。当用户从 Principal Server A 切换到 Principal Server B 时（service replacement、portability 平面操作），B SHOULD 支持以下迁移路径之一：

1. **直接 reparse**：B 收到 `since=cx:cursor:<base64url_from_A>` 时，按 §8.2 canonical schema 解码，提取 `s.<space_id>.{p,o,h}` 与 `d` 信息，翻译为 B 本地 cursor 内部表示。前提是 A 与 B 看见相同 Space 历史。
2. **重置兜底**：B 不支持直接 reparse 时 MUST 返回 `cursor_unrecognized`（不是 `cursor_expired`），客户端按全新初始同步处理；不得静默丢失因果对齐。
3. **可选 translate 端点**：未来 profile 可能在 `cx.profile.principal_server.v1` 之上引入 `POST /api/v1/sync/translate-cursor`；该端点不属于 v1 强制范围。

`_` 前缀的服务器私有字段（compression flag、MAC、签名）在迁移时可被丢弃；canonical 字段（`v` `t` `s` `d` `x`）足以恢复 frontier。

### 8.5 测试向量入口

可执行向量位于：

- [`spec/v1/artifacts/fixtures/encoding-fixture.json`](../../artifacts/fixtures/encoding-fixture.json)

向量覆盖点：cursor 版本字段与过期、per-space frontier 编码、device message 位置、过期 token 回退、非法额外字段拒绝。

### 8.6 一致性

声明支持 Contrix v1 同步的实现 MUST：

- 以不透明字符串形式接受和传输版本 1 cursor。
- 服务端 MUST 接收时验证所有 cursor 字段。
- 服务端 MUST 按 §8.2 canonical schema 编码 cursor 内部结构（私有字段限于 `_` 前缀）。
- 客户端 MUST NOT 解析 cursor 内容。
- 支持每个 cursor 至少 50 个 space。
- 支持最长 7 天的过期时间。
- 以适当错误拒绝非法 cursor。

## 9. Rank

列表排序 rank MUST 使用 `cx.rank.lexofractional.v1` profile，除非 Space schema 显式声明其他 rank profile。

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
- Rebalance assignments MUST 覆盖 container 内全部 active edges，且不得新增、删除或跨 container 移动 edge。CAS 的 `expected_state_hash` 不匹配时，MUST 拒绝整个 operation，不得部分应用。

## 9.5. Composite Cell Subject

部分 cell 的 subject 由多个 sub-component 复合派生（例如 `cx.flow.branch.member` 的 `(flow_id, branch, actor_id)`、`cx.device.authorized` 的 `(principal_id, device_id)`）。复合 subject 的 canonical 形态由本节定义；cell id、Move precondition、Lattice join 和 fixture 必须使用同一形态。

### 9.5.1 通用规则

- 复合 subject 的 canonical wire 形态 MUST 是 base64url（无 padding）编码的 SHA-256 digest：

  ```text
  cell_subject = base64url_nopad(sha256(canonical_json(components_array)))
  ```

  其中 `components_array` 是按本规范声明的固定顺序排列的 JSON array，所有 string element 已经 normalize 过（NFC、小写 typed ID、规范 DID）。
- 实现不得直接使用 `a|b|c` 这种管道分隔字符串作为复合 subject。早期文档中的管道形态仅作为示例可读性提示；canonical cell id、签名输入、state map 索引必须使用 hash 形态。
- 复合 subject 的 sub-component 必须存在于 Move effect value 或兼容 Event payload 的具名字段中。
- 同一 standard cell family 的 `components_array` schema 由本规范固定，profile 不得擅自增删字段或重新排序。

### 9.5.2 标准复合 Subject

| Cell family / Event kind | components_array 顺序（来源字段） |
| --- | --- |
| `cx.component.flow.branch.member.v1` / `cx.flow.branch.member` | `[flow_id, branch, actor_id]` |
| `cx.component.flow.branch.history_visibility.v1` / `cx.flow.branch.history_visibility` | `[flow_id, branch]` |
| `cx.component.flow.branch.policy_components.v1` / `cx.flow.branch.policy_components` | `[flow_id, branch]` |
| `cx.component.device.authorized.v1` / `cx.device.authorized` | `[principal_id, device_id]` |
| `cx.component.device.authorized.v1` / `cx.device.revoked` | `[principal_id, device_id]` |

`flow_id`、`actor_id`、`principal_id`、`device_id` MUST 是完整 typed ID 或完整 DID URI（见 §4）。`branch` MUST 与 Flow `branches[].name` 一致（`^[a-z][a-z0-9_]{0,63}$`）。

非复合 cell（例如 member 用 actor DID、capability grant 用 grant id、Space policy 用 Space id）直接把规范化 subject 放入 `cx:cell:<component>:<subject>`，不需要 hash 化。

接收方收到不符合本节定义的复合 subject components_array 时 MUST 返回 `schema_violation`。文档中若以管道分隔形态展示复合 subject，MUST 显式标注 "informational; canonical cell subject is base64url(sha256(canonical_json(...)))"。

## 10. Encrypted Envelope Digest

加密 payload 的 digest MUST 覆盖密文和明文路由元数据：

```text
payload_digest = sha256(canonical_json(cleartext_metadata) || ciphertext_bytes)
```

`cleartext_metadata` 至少包含 `encryption`、`epoch` 与 `content_type`；当 envelope 带 `aad` 时，`aad` MUST 进入 `cleartext_metadata` 后一起参与 digest。实现 MUST NOT 使用明文 payload 作为 `payload_digest` 输入。
