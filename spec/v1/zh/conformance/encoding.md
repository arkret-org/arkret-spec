---
title: Encoding, IDs, Hashes, Signatures
status: candidate
normative: true
stability: v1
updated: 2026-06-10
sidebar:
  label: Encoding & IDs
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [normative-language.md](./normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

本文定义 Cokret 的 canonical encoding、ID、hash、signature、cursor、HLC 与 rank 编码规则，确保不同实现能得到相同 digest 和验证结果。

## 2. Canonical JSON

Cokret canonical JSON 是签名、hash、event digest、receipt digest、snapshot commitment 和 cursor 内部状态的唯一编码 profile。实现 MAY 复用 RFC 8785 / JCS 类库，但最终输出必须满足本节的收窄规则和 `conformance-vectors.md` 的测试向量。

Cokret canonical JSON MUST 使用：

- UTF-8 不带 BOM；输入若包含 UTF-8 BOM（`U+FEFF` 编码 `EF BB BF`，无论出现在 stream 起始还是 string value 内部）、malformed UTF-8、孤立 surrogate 或无法被 JSON parser 唯一解释的字符串，MUST reject。`U+FEFF` 在 string value 中只允许作为 zero-width no-break space 的语义存在，但 v1 canonical JSON MUST NOT 接受此用法——任何 `U+FEFF` 出现都按 schema_violation 拒绝。
- object key 按 RFC 8785 / JCS 规则排序：先比较属性名的 UTF-16 code unit 序列，按字典序升序排列，并在每一层独立排序。实现 MUST NOT 改用 Unicode code point 排序；对补充平面字符，UTF-16 surrogate pair 顺序是规范结果。
- 无 insignificant whitespace。
- JSON object 中的重复 key MUST reject，MUST NOT 采用“最后一个 wins”或“第一个 wins”。
- number MUST 使用 RFC 8785 / JCS 等价的唯一 decimal serialization；NaN、Infinity、-Infinity、`-0`、无法精确往返的 number、超出 JSON safe integer 范围 `[-9007199254740991, 9007199254740991]` 的 number MUST reject。**v1 wire MUST NOT 使用非整数 number**：所有签名 canonical object 的 number 字段 MUST 是 JSON integer。需要超过 safe integer 范围的计数器、偏移或大整数 MUST 编码为带显式格式约束的 string（例如 fixed-width hex / decimal string），MUST NOT 作为 JSON number 进入 canonical bytes。比例、置信度、进度等小数值 MUST 编码为整数 + 显式 scale（推荐字段后缀 `_basis_points` 表示万分数 0..10000，或 `_x1000`、`_x1000000` 等明确比例）；`confidence_basis_points: 7500` 表示 75.00%。这条收紧规则取消了"何时允许 number canonicalization"的可选语义，使签名输入 100% 确定。
- timestamp 使用 RFC 3339 UTC，尾部 `Z`；签名输入 MUST NOT 接受本地时区、隐式时区或 leap-second 变体。
- 字段名使用 snake_case。

Event Envelope 的签名和 hash 输入 MUST 是去除 `proofs` 与 `unsigned` 后的 canonical JSON bytes，并且 MUST 保留 `event_id`。`unsigned` 是传输/本地附加信息，MUST NOT 影响 event digest 或 proof `event_digest`。实现 MUST NOT 对已经签名的 bytes 做大小写规范化、ID 前缀补全、字段默认值补写、key 重排以外的语义改写。签名字节的不可变性是协议演进的根约束——升级 MUST NOT 改写历史签名 bytes，而是用重放/投影重建派生视图，详见 [overview/evolution-and-compatibility.md](../overview/evolution-and-compatibility.md)。

生产者 MUST 在所有 v1 签名对象中使用 JSON integer 表示数值。Schema 要求小数语义的字段（如概率、进度、置信度）MUST 使用整数 + scale（见上文 `_basis_points` 等约定），生产者和消费者按预定义 scale 解释，无须做 number canonicalization。任何 v1 schema MUST NOT 新增 `type: number`（非整数）字段；遗留字段 MUST 在下一个 schema profile 升级时迁移到整数 + scale。

### 2.1 String 字段的 Unicode 收紧

字符串 field 的 wire 形态 MUST 满足以下约束，否则 receiver MUST `schema_violation` 拒绝：

- **NFC 正规化**：所有 string value MUST 在写入 canonical JSON 前完成 Unicode NFC（Canonical Composition）正规化。生产者发送已 NFC 化字节；receiver MUST NOT 在 verify 阶段做隐式 NFC 化——若收到非 NFC 字符串，按 schema_violation 拒绝。这一条避免"看起来一样的字符串"在 hash / signature 比较时出现 false positive 或 false negative（同一可见字符可能由 precomposed 或 decomposed 序列表示）。
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

为什么把 NFKC + confusable 限定在身份相关字段而不是全字段：正文（Strand.content、Message.content）允许任何脚本混排是合理的（中文夹拉丁、阿拉伯夹希伯来），不能强制 single-script。但身份相关字段是 trust UI 决策点，必须 reject 同形字攻击。

### 2.2 备用 canonical encoding (profile-gated)

v1 wire format 锁定为 canonical JSON。需要更紧凑或更适合受限设备的 binding 时，profile MAY 引入备用 canonical encoding：

- **CBOR (RFC 8949) deterministic encoding** — 与 IETF MLS / COSE / WebAuthn 同源；适合 IoT、嵌入式与高密度 wire 场景。
- 其他 binary encoding（如 protobuf、msgpack）SHOULD 通过 profile 单独引入，MUST NOT 静默替换 v1 canonical JSON。

备用 canonical encoding 通过 **digest suite 机制**（§3.1 / §3.2、[`digest-suite-registry.json`](../../artifacts/registry/digest-suite-registry.json)）进入协议，规则如下：

- 引入备用 encoding 的 profile（id 形如 `ck.profile.encoding.cbor.v1`）MUST 在 digest-suite registry 注册对应 suite（如 `cbor.sha256`），并交付该 suite 的 activation requirements：deterministic 编码细则、CDDL、**schema 无关**的 JSON ↔ 该编码类型映射（string→text string、integer→integer 的哑映射；归一化 MUST NOT 依赖 schema 知识，否则 digest 会随 schema registry 版本漂移）、以及 per-suite conformance vectors。
- **归一化编码是 Realm 级声明**：Realm 在 create event 的 `digest_algorithm` 字段锁定唯一 suite（§3.3），该声明是权威；事件 envelope 的 `requirements.features[]` 声明对应 encoding profile 作为能力要求，但 MUST NOT 与 Realm 声明的 suite 冲突。未声明备用 suite 的 Realm 一律按 canonical JSON 解析。
- 由于 Realm 级 suite 排他（§3.3），同一 Realm 内不存在 JSON 与备用编码两套并行 digest，**跨编码的双向 digest 等价向量不是验证路径的需求**；仅当 profile 提供 json→备用编码的 suite transition 路径时，MUST 给出 transition Seal 双 root 向量（见 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §4.2.5）。
- 实现 MAY 出于调试 / 退化传输目的输出备用编码 Realm 中对象的 JSON 渲染视图，但该视图是 informational 投影：MUST NOT 进入签名、digest、`prev_refs` 解析或任何 canonical 路径。

## 3. Hash

### 3.1 Wire 形态

Cokret 所有 hash wire value MUST 形如：

```text
<suite>:<lowercase_hex_digest>
```

- `<suite>` 是 **digest suite** 标识符——digest 定义的注册元组 **(canonicalization, hash_algorithm)** 的 canonical id，取自 [`digest-suite-registry.json`](../../artifacts/registry/digest-suite-registry.json)（机器可读 source of truth，§3.2 表为其阅读视图）。文法：裸 id（无点号，如 `sha256`）表示 canonicalization = canonical JSON（§2），与既有 wire 语义完全一致；点分 id `<canonicalization>.<hash>`（如 `cbor.sha256`）表示备用归一化编码 suite。本文其他小节及兄弟文档中沿用的 `<algo>` 称谓即 `<suite>` ——对全部裸 id 二者同义。
- `<lowercase_hex_digest>` 是按 suite 的 canonicalization 产出 canonical bytes、再以 suite 的 hash 算法计算的 raw digest 的小写 hex 编码，长度由 hash 算法决定。
- suite、长度、编码三者**任何一项**与 registry 行不一致 → schema_violation。
- suite 是**注册元组**：实现 MUST NOT 把 canonicalization id 与 hash id 自由组合出未注册前缀；registry 中不存在的组合不存在于协议中。
- suite 前缀是 digest 字符串值的一部分，因而被签名字节覆盖：digest 定义本身不可在不破坏 proof 的情况下被改写或降级。

### 3.2 Digest Suite / Hash Agility Set

digest suite 的 canonical 机器来源是 [`digest-suite-registry.json`](../../artifacts/registry/digest-suite-registry.json)（与 §6.1 Signature Suite registry 对称）；schema 中 digest-suite 选择字段（如 Realm `digest_algorithm`）的 enum MUST 由 registry active rows 生成。下表是 v1 active 且 canonicalization = canonical JSON 的 suite 集合的规范阅读视图：

| Algo | Digest 长度 | v1 角色 | 抗量子 / future-ready 评估 |
| --- | ---: | --- | --- |
| `sha256` | 32 bytes（64 hex） | **v1 default**；所有 receiver MUST 支持。Event digest、Merkle leaf、state_root、blob CID、receipt digest 等核心字段默认使用。 | 不抗量子（Grover 把搜索成本减半到 2^128，仍可用）；通过 `ck.profile.hash_transition.v1` 可平滑迁移到 stronger hash。 |
| `blake3` | 32 bytes（64 hex） | v1 optional；声明 `ck.profile.hash.blake3.v1` 的实现 MUST 支持。性能最佳（可并行）；blob CID 与高吞吐场景推荐。 | sha256-class 抗碰撞；非 NIST 但被 IRTF / RFC 路径认可。 |

v1 active 集合刻意保持最小（`sha256` + `blake3`）。需要 algorithm diversity（如 SHA-3 / Keccak 家族对冲 SHA-2 结构性风险）或抗量子 hash 时，按 registry 规则**加法注册**新行（新 hash profile + conformance vector），wire 形态无需重写；不预注册无实际使用场景的算法。

除上表 active rows 外，registry 还以 **reserved** 状态登记了备用归一化编码 suite（当前为 `cbor.sha256`，deterministic CBOR + SHA-256，gate 为 `ck.profile.encoding.cbor.v1`，见 §2.2）。reserved suite 钉定 wire 前缀与 gate，但在其 `activation_requirements`（编码细则 + CDDL + 类型映射 + conformance vectors）全部满足并在 registry release 中翻为 active 之前，**MUST NOT 出现在 wire 上**——接收方按未识别 suite 前缀 fail closed 处理即可，无需特判。

扩展 profile MAY 通过新 hash profile 加入抗量子 hash（如 SLH-DSA hash family、SHAKE256 派生），也 MAY 通过新 encoding profile 注册备用归一化 suite；v1 wire 形态 `<suite>:<hex>` 已经为这两类加法准备好——**无需重写 wire**。

实现 MUST：

- 默认按 `sha256:` 解析；遇到未识别的 suite prefix（含 registry 中 reserved 状态、未注册点分组合、未知 id）→ 若位于 critical field（event_digest、state_root、prev_refs blob hash）→ fail closed (`unsupported_digest_algorithm`)；若位于非 critical metadata（如对象的 derived fingerprint）→ MAY 记录为 unknown 并 preserve raw bytes。
- 在 `server/describe.crypto` 暴露支持的 digest suite 集合;client 可据此选择写入算法。（`describe.crypto` 还 MUST 暴露支持的**签名** algo 集合，该 MUST 的权威声明集中在 §6.1 Signature Suite registered set。）
- MUST NOT "算法升级"已签名的 canonical bytes：一旦 Event 用 `sha256:` 发布，verify 路径永远按 sha256 重算；实现 MUST NOT 因为本地默认换成 blake3 就重算并替换。

### 3.3 State Root 与 Seal Hash 编码

`state_root`、Seal `id`、Event `event_digest` / `event_id` 引用、receipt digest 这几条核心承诺字段的 wire 形态由所属 Realm 在 create event 中通过 `digest_algorithm` 字段固定（默认 `sha256`）。`digest_algorithm` 的取值是 [`digest-suite-registry.json`](../../artifacts/registry/digest-suite-registry.json) 的 **active suite id**——它锁定的不只是 hash 算法，而是完整 digest 定义（canonicalization × hash）。Control Move 是 reducer-input Event 的控制面协议视图；Control Move 级引用 MUST 使用 enclosing Event 的 `event_id` 或 `event_digest`。

**Realm 级 suite 排他（normative）**：一个 Realm 同一时刻 MUST 只有一个 live digest suite；Realm 内所有后续 Seal / Event digest / state_root / receipt digest MUST 使用同一 suite。接收方在 Realm 上下文中遇到 suite 前缀与该 Realm 声明不符的 digest（Transition Seal 的 `previous_state_root` 除外）MUST 按 schema_violation 拒绝，即使该 suite 本身是 receiver 支持的 active suite——这条排他规则消除"同一语义对象在同一 Realm 内拥有两个合法 digest"的去重 / 重放二义性（`duplicate_conflict` 配对、`prev_refs` 解析、幂等键均依赖单一 digest 定义）。跨 Realm 引用按 digest 值自带的 suite 前缀验证，无需上下文。

切换 suite（hash 分量升级，或归一化编码分量切换）需要通过 `ck.profile.hash_transition.v1` snapshot commitment + signed compaction Seal 在 frontier 上做一次 suite transition Seal，新旧 suite 都能在 transition Seal 上验证 inclusion。详细规则见 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §4.2.5（digest suite transition）。

### 3.3.1 Snapshot / Event-set Merkle Root 编码

Snapshot reducer output root 与 snapshot event-set commitment 使用同一 Merkle 组合规则；领域章节只定义 leaf 的构造方式。本节定义 leaf 进入树之后的 byte-level 规则，供 [`snapshot-schema.md`](./snapshot-schema.md) §4 / §6 引用。

- Leaf 输入 MUST 是已按领域规则产生的 `<suite>:<hex>` digest。v1 base 支持 `sha256:<64 lowercase hex>`；进入树组合前 MUST 去掉 `sha256:` 前缀并解码为 raw 32 bytes。非 `sha256` suite 只有在对应 profile 明确声明同一 Merkle 组合规则和 digest 长度时才可用于该 root。
- Internal node bytes MUST 是 `sha256(left_raw || right_raw)`，其中 `left_raw` 与 `right_raw` 是左右子节点的 raw digest bytes；wire 输出仍为 `sha256:<lowercase_hex>`。
- Odd level MUST promote the trailing node unchanged to the next level. 实现 MUST NOT 复制尾节点。
- Single-leaf tree root MUST equal that leaf digest。
- Empty leaf set root MUST be `sha256` over the empty byte string：`sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`。
- Tree construction itself does not sort leaves. 每个领域规范必须先声明 leaf 顺序；snapshot state leaves 使用 `(kind, id)` canonical byte order，snapshot event-set leaves 使用 `(actor_id, actor_seq, event_id)`。

### 3.4 Multihash 兼容（profile-gated）

声明 `ck.profile.encoding.multihash.v1` 的实现 MAY 在 wire 上接受 multihash 风格的二进制 hash header（multicodec varint + length + digest）作为额外 reading format，但 canonical JSON 上的 wire value 仍 MUST 使用 §3.1 的 `<algo>:<hex>` 字符串形态。引入 multihash profile 的目的是与 IPFS / libp2p / Iroh 生态做内容寻址互通；它不替换 v1 wire 默认。

## 4. ID

协议 wire / canonical object 层的 typed ID 格式：

```text
ck:<kind>:<uuid>
```

标准 `kind` 的机器可读 source of truth 是 `artifacts/registry/id-kind-registry.json`。本文只定义通用规则。

`ck:` 前缀表示 Cokret 协议命名空间；`<kind>` 表示对象或引用类型；`<uuid>` 是该类型下的稳定 ID。完整 typed ID 是 wire value 的一部分，MUST 出现在：

- Event Envelope、canonical object、receipt、snapshot、fixture 和 OpenAPI / non-HTTP DTO。
- canonical JSON、签名 payload、`event_digest`、cursor 内部 state、federation payload、audit log。
- 跨服务引用、日志和错误响应中需要自描述对象类型的字段。

数据库或本地索引实现 MAY 不把 `ck:<kind>:` 前缀作为主键的一部分存储——例如直接用 PostgreSQL `uuid` / `BYTEA(16)` 列存 16 字节 raw value，由表名或显式 `kind` 列提供类型上下文。实现若这样存储，MUST 在进入 canonical JSON、签名、hash、联邦转发、sync cursor、audit replay 或 API response 前恢复完整 typed ID。接收方验证签名、hash、backfill 或 replay 时，MUST 按完整 typed ID 比较，MUST NOT 用数据库 row id、自增 id、表名推断或隐式转换替代 wire value。

`<kind>` 是 canonical bytes 的一部分。实现 MUST NOT 把 `ck:receipt:<id>` 改写成 `ck:event:<id>`，也 MUST NOT 因为字段名叫 `receipt_id` 就在验证时补前缀。字段名可以辅助 schema 校验，但不能替代 signed wire ID。

v1 wire、JSON Schema、registry、fixture 和所有签名 canonical object 中的 `<uuid>` 段 MUST 是 [RFC 9562](https://datatracker.ietf.org/doc/html/rfc9562) UUID **version 7**：48-bit Unix-millisecond timestamp（big-endian）+ 4-bit version=`0111` + 12-bit `rand_a` + 2-bit variant=`10` + 62-bit `rand_b`，按 RFC 9562 §4 的 canonical 36-character lowercase hex 形式 `xxxxxxxx-xxxx-7xxx-Nxxx-xxxxxxxxxxxx` 序列化（其中 `N ∈ {8, 9, a, b}`，对应 RFC 4122 variant 1）。外部导入数据若是大写或带 URN/Microsoft braces 等变体形式，MUST 在生成 v1 Event Envelope、object id、cursor payload 或 proof `event_digest` 前规范化为小写无前缀的 36-char hyphen-separated 形式。已经进入签名 canonical bytes 的 ID MUST NOT 在验证、转发、backfill 或审计回放时重写大小写或形式。

同一 producer 在同一 millisecond 内连续产出 SHOULD 使用 RFC 9562 §6.2 列出的 monotonic 方法之一（推荐 Method 1：单调随机段递增）以保证字典序稳定且与时间序一致。**v1 wire MUST NOT 接受其他 UUID version 替代**——v1（基于 MAC + 时间戳）、v3/v5（命名空间 hash）、v4（纯随机）、v6（重排时间戳）、v8（自定义）以及任何非 UUID 格式的等价 ID（UUIDv7、KSUID、Snowflake、TSID、CUID）即使经过 hex 重编码并伪造 version=7 nibble，也 MUST NOT 作为 typed `ck:<kind>:<uuid>` 的 ID 段使用；wire 上锁定单一构造方式以避免 prev_refs / refs / cursor / index 出现两套分布。这条限制是 wire 兼容性约束，不是收敛或审计要求：receiver 校验以正则 + 长度 + version/variant nibble 为准，不对 timestamp 段做语义解析；但 producer SHOULD 拒绝产出 timestamp 段明显畸形（远未来或远过去于本地时钟超过实现声明阈值）的 ID，并 SHOULD 在生成时检测同 actor 时钟回退导致的非单调情况。

`event_id` 不是 canonical bytes 的 hash，是 producer 在签名前分配并写入 canonical bytes 的稳定 typed UUIDv7。Envelope 的内容指纹由 `proof.event_digest`（≡ `canonical_digest(envelope_without_proofs_unsigned)`）承担；`event_id` 与 hash 是两个独立字段，相同 `event_id` 配不同 canonical hash MUST 触发 `duplicate_conflict` quarantine（见 [`operations-sync.md` §2.1](../sync/operations-sync.md)）。

本节定义的 UUIDv7 构造、编码、单调性、receiver 校验规则 MUST 应用于 [`id-kind-registry.json`](../../artifacts/registry/id-kind-registry.json) `id_kinds[]` 中**全部** typed kind（包括但不限于 `realm`、`strand`、`space`、`morph`、`message`、`relation`、`view`、`actor_profile`、`device`、`capability`、`grant`、`invite`、`receipt`、`snapshot`、`transaction` 等），event 不是特例。新 kind 注册 MUST 遵循同一规则；只有 registry `special_forms[]` 中已列出的形态（opaque cursor、content-addressed blob / seal、canonical cell tuple、MLS profile-scoped 引用、Realm-scoped pseudonym、trust domain）才允许偏离 typed-UUIDv7 pattern，并各自由对应 schema / profile 单独校验。未在 registry 注册的非 typed-UUIDv7 前缀形态 MUST 按未知 critical wire type 拒绝。

特殊 ID/ref 形式（与 [`id-kind-registry.json` `special_forms[]`](../../artifacts/registry/id-kind-registry.json) 一一对应）：

- `ck:cursor:<base64url>` 是 opaque token，不是 typed UUIDv7 object ID。
- `ck:blob:sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` 是内容寻址 Blob ref；`ck:blob:019640ba-0000-7000-8000-000000000000` 是 Blob metadata ID。二者 MUST NOT 混用。
- `ck:seal:sha256:<digest>` 是内容寻址 Seal hash（active special form；见 `id-kind-registry.json`）。
- `ck:cell:<component>:<subject>` 是 canonical cell tuple 引用（active special form；component 来自 cell-component registry，subject 是 cell 的 subject key）。
- `ck:mls:<profile>:<profile_id>`、`ck:pseudonym:<scope_id>:<random>` 等 profile-scoped form 必须由对应 profile 注册和校验。
- `ck:trust_domain:<scope>` 是部署 / 联邦信任域 ref，不是 typed UUIDv7 object ID；`<scope>` 的 profile 与匹配规则由 Realm / federation policy 声明。

自定义 profile 若新增 `ck:<kind>:` 前缀，MUST 在 profile registry 或扩展 registry 中声明 kind、wire form、存储边界和校验规则。未注册的 `ck:<kind>:` typed ID MUST 被视为未知 critical wire type，除非所在字段明确允许 opaque string。

### 4.1 Field Naming: `_id` / `_ref` / `_did`（normative）

Identifier 字段命名的权威规则见 [`common-fields.md` §2.1](../models/common-fields.md#21-identifier-字段命名约定normative)。本节只给出编码层摘要：字段后缀表达 wire value category，不表达授权、同步、retention 或 E2EE 级联语义。

| 用途 | 命名后缀 | 说明 |
| --- | --- | --- |
| 对象自身 ID（primary key） | `id` | canonical object 的主 ID，无下划线前缀。例：`id`。 |
| 单一具体 protocol object kind | `<role>_<kind>_id` | 例：`realm_id`、`parent_space_id`、`scope_circle_id`、`policy_id`。 |
| 协议责任主体（DID 作为主体 ID） | `<role>_id` | 例：`actor_id`、`principal_id`、`subject_id`。 |
| 因果 / finality / proof / schema-profile reference | `<noun>_ref` / `<noun>_refs` | 例：`prev_refs`、`seal_ref`、`schema_refs`、`policy_event_ref`。 |
| Blob / content-addressed / polymorphic reference | `<noun>_ref` / `<noun>_refs` | 例：`blob_ref`、`target_ref`、`from_ref`、`to_ref`。 |
| 原始 DID ecosystem material | `<role>_did` | 例：`service_did`、`pairwise_did`、`old_did`、`new_did`。 |

## 5. Event Batch Receipt Hash

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
    "event_digest": "sha256:..."
  },
  "events": ["sha256:..."],
  "created_at": "2026-04-26T00:00:00Z"
}
```

`receipt_digest = sha256(canonical_json(receipt_without_proofs))`。`issuer`、`receipt_scope`、`frontier`、`events`、`schema` 必须进入 digest，防止 receipt 被跨 actor、跨 Realm 或跨前沿重放。

## 6. Signature

默认 proof（wire `proof` 对象;`actor_id` 与 `created_at` 不在 wire `proof` 对象内——`actor_id` 取自被签 Event envelope 的 `actor_id` 字段,`created_at` 取自 `proof.created_at`,二者均进入下方签名 transcript binding object）:

```json
{
  "kind": "detached_jws",
  "alg": "EdDSA",
  "verification_method": "did:web:alice.example#device-1",
  "created_at": "2026-04-26T00:00:00Z",
  "event_digest": "sha256:...",
  "jws": "..."
}
```

Proof MUST bind（下列为绑定字段集合；canonical binding object 的实际字节顺序由 §2 canonical JSON 的 JCS key 排序决定，下方 JSON 示例与本清单的列举顺序仅为可读性，不代表签名字节顺序）:

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

**Realm 绑定（normative）**：event proof 通过 `event_digest` 间接绑定 `realm_id` —— `event_digest = canonical_digest(event_without_proofs_unsigned)` 覆盖整个 envelope，而 envelope MUST 含 `realm_id` 字段（见 §1.6 event digest 向量）；任何改写 `realm_id` 的尝试都会改变 `event_digest`，使 proof 验证失败。因此 event proof 对跨 Realm 重放提供与 Event Batch Receipt 的 `receipt_scope` 等价的保护：receipt 显式绑定 `receipt_scope`（见 §5），event proof 经由 `event_digest` 覆盖 `realm_id`。实现 MUST 在验证 proof 前确认 envelope 的 `realm_id` 与处理上下文的目标 Realm 一致，MUST NOT 仅凭 proof 验证通过就跨 Realm 接受同一 Event。

### 6.1 Signature Suite registered set

签名算法的 canonical 机器来源是 [`signature-alg-registry.json`](../../artifacts/registry/signature-alg-registry.json)(与 §3.2 Hash registered set 对称)，下表是其规范阅读视图。proof `alg` 字段 MUST 取自 registry active row 的 `proof_alg`；raw / non-JWS `signature_algorithm` 字段 MUST 取自 active row 的 `signature_algorithm`。散落于各 schema 的签名算法 enum MUST 由该 registry 校验，MUST NOT 在 schema 中私自引入未登记算法。`detached_jws` 形态的 `alg` 使用 JWS 标准标识(`EdDSA` 对应 Ed25519);非 JWS 形态(如 raw detached signature)按 registry 的 raw `signature_algorithm` 标识。

表列与 registry active row 字段一一对应:`canonical_id`(下表 `Algo`)、`proof_alg`(JWS `alg`，detached_jws 形态用)、`signature_algorithm`(raw / non-JWS detached signature 形态用)。`Ed25519` 行的 `proof_alg`(`EdDSA`)与 `signature_algorithm`(`Ed25519`)不同，二者 MUST 分别取自对应列，不可互相替代。

| Algo（`canonical_id`） | `proof_alg`（JWS `alg`） | `signature_algorithm`（raw / non-JWS） | v1 角色 | 抗量子 / future-ready 评估 |
| --- | --- | --- | --- | --- |
| `Ed25519` | `EdDSA`（JWS, crv=Ed25519） | `Ed25519` | **v1 default-MUST**;所有 receiver MUST 支持。Event proof、receipt proof、device cross-signing binding 等核心签名默认使用。 | 不抗量子(Shor 可破);通过 `ck.profile.signature.pqc.v1` 迁移到后量子 suite。 |
| `ECDSA-P256-SHA256` | `ES256`（JWS, P-256 + SHA-256） | `ES256` | v1 optional;声明 `ck.profile.signature.ecdsa_p256.v1` 的实现 MUST 支持。用于需要与 WebAuthn / FIDO2 / 既有 PKI 互通的部署。 | 不抗量子(Shor 可破);选择仅出于生态互通。 |
| `ML-DSA-65` | `ML-DSA-65`（NIST FIPS 204, Dilithium category 3） | `ML-DSA-65` | v1 profile-gated;声明 `ck.profile.signature.pqc.v1` 的实现 MUST 支持。后量子格基签名，用于长生命周期审计签名与抗量子迁移。 | 抗量子(NIST PQC 标准);wire 形态 `<algo>:<...>` 已为加法准备好，无需重写 wire。 |

实现 MUST:

- 默认按 `EdDSA`(Ed25519) 验证 event / receipt proof;遇到未识别的 `alg` → 若位于 critical proof(event_digest binding、device authorization、recovery)→ fail closed (`unsupported_signature_alg`);若位于非 critical metadata signature → MAY 记录为 unknown 并 preserve raw bytes。
- 在 `server/describe.crypto` 暴露支持的签名 algo 集合(与 hash algo 集合并列),client 据此选择写入算法。
- MUST NOT "算法升级"已签名的 canonical bytes:一旦 proof 用某 `alg` 发布,verify 路径永远按该 algo 重验；新算法走新 proof,不重写历史签名字节。

**后量子 / hybrid 前瞻(未来)**:hybrid composite 签名(例如 `Ed25519+ML-DSA-65`,经典 + 后量子双签以在迁移期同时满足两类验证者)登记为 `ck.profile.signature.pqc.v1` 的扩展槽位。它复用本节"不重写历史签名字节、新算法走新 proof"原则——hybrid proof 作为追加的新 proof entry 出现，经典验证者验经典分量、后量子验证者验 ML-DSA 分量，历史 Ed25519 proof bytes 不被改写。该槽位在 v1 不强制，记为未来。

## 7. HLC

> **使用边界（normative）**：HLC 在 v1 是 **advisory** 字段。它 MUST NOT 进入授权决策、Lattice 收敛、Control Move precondition 比较、或 Seal finality 判断；这些都由 CBA basis、Control Move `preconditions[]`、Seal coverage 与 Lattice `join` 决定。HLC 在 v1 的唯一规范用途是 **timeline 派生层**——当两个事件在 `prev_refs` / `refs` 形成的因果图中互不可达时，HLC 作为 `(unix_ms, logical, node_id_hash)` 字典序 tie-breaker 使展示顺序确定。即便 HLC 进入 canonical event bytes 与 proof `event_digest`，实现 MUST NOT 把 HLC 数值当作可信时间戳，也 MUST NOT 据其反转因果或选 winner。详见 [`authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) 与 [`sync/operations-sync.md`](../sync/operations-sync.md)。

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
- `node_id_hash` MUST 是 8 位小写十六进制稳定节点哈希；它只用于同一 `(unix_ms, logical)` 下的确定性 tie-break，MUST NOT 替代因果关系或授权判断。
- 用户客户端的 `node_id_hash` MUST 从 Realm-scoped 或 deployment-scoped 的本地 node secret 派生，例如 `SHA256("cokret-hlc-v1" || realm_id || device_id || local_node_secret)[0:8]`。MUST NOT 直接使用 principal DID、公开 handle、长期 device id 或跨 Realm 稳定标识作为 hash 输入。
- 服务 DID 产生的公开服务事件 MAY 使用 service-scoped node id，但服务若代表用户或 minimal-metadata Realm 转发/生成事件，MUST 使用 Realm-scoped pseudonymous node id，避免跨 Realm 关联。

排序按 `(unix_ms, logical, node_id_hash)` 字典序。

溢出规则：

- 生产者若在同一 `unix_ms` 内需要把 `logical_hex` 从 `ffff` 再递增，MUST NOT 回绕到 `0000`，也 MUST NOT 复用任何已发出的 HLC tuple。
- 遇到该情况时，生产者 MUST 采取以下两种行为之一：
  - 等待直到本地可生成更大的 `unix_ms_hex`，然后以 `logical_hex=0000` 生成新 HLC。
  - 在生成 canonical bytes 之前以本地临时错误终止该次写入，例如 `hlc_logical_overflow`，由调用方稍后重试。
- 生产者在等待或重试期间 MUST 保留原有 `prev_refs`、`refs[role=authorized_by]` 和 `actor_seq` 约束，MUST NOT 仅为了逃避 overflow 而伪造更大的 wall clock skew。
- 消费者若观察到同一 producer 出现 `unix_ms` 不变、`logical_hex` 从 `ffff` 回绕到更小值且没有更大 `unix_ms`，MUST 将其视为无效 HLC，并以 `schema_violation`、`causal_conflict`、`soft_fail` 或 quarantine 处理；MUST NOT 把它当作正常排序值接受。

v1 固定使用 4 位 `logical_hex`。该上限等价于单个 producer 每毫秒 65,536 个有序 HLC；超过该速率的批量写入应拆分到多个 actor/device producer、等待下一毫秒，或使用服务端批量入口排队。实现 MUST NOT 在 v1 中把 `logical_hex` 私自扩展到 6/8 位；需要更宽计数器时 MUST 声明新的 HLC version 与 schema profile。

### 7.1 操作伪代码

发送事件：

```text
hlc = max(current_hlc, current_unix_ms)
if hlc.unix_ms == current_unix_ms:
    hlc.logical += 1
else:
    hlc.unix_ms = current_unix_ms
    hlc.logical = 0
```

接收带 HLC `hlc_remote` 的事件：

```text
unix_ms = max(current_hlc.unix_ms, current_unix_ms, hlc_remote.unix_ms)
if unix_ms == current_hlc.unix_ms and unix_ms == hlc_remote.unix_ms:
    logical = max(current_hlc.logical, hlc_remote.logical) + 1
elif unix_ms == current_hlc.unix_ms:
    logical = current_hlc.logical + 1
elif unix_ms == hlc_remote.unix_ms:
    logical = hlc_remote.logical + 1
else:
    logical = 0
hlc = { unix_ms, logical, node_id_hash = local_node_id_hash }
```

比较：

```text
function compare_hlc(hlc1, hlc2):
    if hlc1.unix_ms_hex != hlc2.unix_ms_hex:
        return parse_hex(hlc1.unix_ms_hex) - parse_hex(hlc2.unix_ms_hex)
    if hlc1.logical_hex != hlc2.logical_hex:
        return parse_hex(hlc1.logical_hex) - parse_hex(hlc2.logical_hex)
    return strcmp(hlc1.node_id_hash, hlc2.node_id_hash)
```

### 7.2 验证规则

实现 MUST：

- 用正则 `^[0-9a-f]{12}-[0-9a-f]{4}-[0-9a-f]{8}$` 验证 HLC 格式。HLC **纯格式违例**（不匹配该正则、段长 / 字符集 / 大小写不合、`unix_ms_hex > ffffffffffff` 等单纯的 well-formedness 失败）MUST 返回 `schema_violation`（与 [`conformance-vectors.md` §1.10.1](./conformance-vectors.md) 钉定的单值一致）。`schema_violation` / `causal_conflict` / `soft_fail` / quarantine 的多选处置仅适用于 §7「溢出规则」中的语义回绕 / 单调性违例场景（格式合法但 `logical_hex` 从 `ffff` 回绕、复用 tuple 等），不适用于纯格式违例。
- 按本节的两层 drift 模型验证物理时间：超 `hard_future_skew_ms`（默认 300_000）MUST reject / quarantine；超 `expected_future_skew_ms`（默认 30_000）SHOULD soft-fail / quarantine。该校验是 envelope freshness / DoS guard，不是授权、Lattice winner、Control Move precondition 或 Seal finality 输入；通过 drift 校验的 HLC 仍只可用于 timeline tie-breaker。
- profile MAY 通过 `state_event_expected_future_skew_ms` 对 state event（capability / membership / policy / service binding / Realm upgrade / MLS commit 等）施加更严窗口；未声明时按 `expected_future_skew_ms` 处理。
- 拒绝 `unix_ms_hex > ffffffffffff` 的 HLC 值（物理时间溢出，需未来扩展 HLC profile 才可使用）。
- 维护本地单调性；本地时钟落后远端时推进到远端时间，超前时限制推进速率。

### 7.3 Timeline 排序与 winner 选择

客户端 timeline / backfill / 展示层默认事件排序：

```text
causal_depth ASC, hlc ASC, actor_id ASC, actor_seq ASC, event_id ASC
```

协议状态 MUST NOT 使用 timeline 排序选择 winner。DataEvent / Control Move 的 CBA basis、Seal coverage 与 Lattice join 决定当前 cell value；并发不可合并时返回 structured bottom。Timeline 展示顺序与 cell value 是两种不同 projection：前者排历史，后者由 Lattice 计算。实现 MUST 在 profile 中明确使用哪一个，MUST NOT 把 timeline 中最后出现的 Event 直接当作状态 value。

客户端只有在已知 causal closure 足以判断两个 Event 在 `prev_refs` 与 `refs[role="after"]` 图中互不可达时，才可把 HLC 用作最终 timeline tie-breaker。若 backfill、dependency fetch 或 snapshot-assisted verification 尚未补齐到可判断互不可达，客户端 MUST 把排序标记为 provisional（例如 pending/backfilling），或使用 `created_at` / 本地接收序作为临时 UI 占位；MUST NOT 把 HLC 排序结果写入持久 projection、审计导出或任何声称“最终顺序”的视图。

`causal_depth` 只用于 timeline / batch 展示排序。它的 canonical projection 定义为：在已知 causal closure 内，仅沿 `prev_refs` 与 `refs[role="after"]` 边计算最长路径长度；genesis depth 为 0。若任一参与排序的 Event 缺失这些边上的 predecessor，接收方 MUST 把该 Event 的 depth 标记为 provisional，不得声称最终 timeline 顺序，也不得把该 depth 输入协议状态收敛、授权或 winner 选择。

## 8. Cursor

> **Scope（normative）**：本节只定义 cursor 的**内部 canonical 结构、字段 schema、编码、验证规则与 TTL 硬上限数值**;cursor 在 HTTP/JSON binding 上的使用契约(出现位置、分页方向、purpose 语义)见 [`api-conventions.md` §7](../sync/api-conventions.md)。

Cursor 是不透明字符串：

```text
ck:cursor:<base64url>
```

### 8.1 客户端契约

- 客户端 MUST 把 cursor 当作不透明字符串。
- 客户端 MUST NOT 解码、解析或修改 cursor 内容。
- 客户端 MUST 存储 binding 返回的最新 stream `cursor` 用于恢复。
- 客户端 MUST 在下一次同语义用途的请求中按原样使用 cursor；具体出现位置由对应 transport / API binding 定义。

### 8.2 服务端 canonical 内部结构

服务端在 base64url 编码前将 cursor 内部结构编码为 canonical JSON（按 §2 规则）。**v1 core cursor 内部结构 MUST 遵循 [`cursor.schema.json`](../../artifacts/schemas/cursor.schema.json)**：body 固定为 `{v, purpose, t, x, h}`，其中 `h` 是不可猜测的 server-side opaque handle（见 §8.3.1）。core schema `additionalProperties:false` 且 `required` 含 `h`；服务端 MUST NOT 在 cursor body 中内联 stream positions、barrier target、principal binding 或完整性证明字段。

cursor 是 v1 中**唯一**的不透明 token 类型，统一承担增量同步、列表分页和写后读屏障用途。`purpose` 字段区分两个语义：`stream`（增量同步与列表分页位置承诺）与 `barrier`（读己之所写屏障）。每个 transport / API binding MUST 在自己的绑定文档中声明哪些 wire 位置接受哪一种 `purpose`。

Stream cursor body 示例：

```json
{
  "v": "1",
  "purpose": "stream",
  "t": "2026-04-26T00:00:00.000Z",
  "x": 1714080000000,
  "h": "abcdefghijklmnopqrstuv"
}
```

Barrier cursor body 示例：

```json
{
  "v": "1",
  "purpose": "barrier",
  "t": "2026-04-26T00:00:00.000Z",
  "x": 1714080000000,
  "h": "0123456789abcdefghijkl"
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `v` | string | 是 | cursor 版本，v1 固定 `"1"` |
| `purpose` | enum(`stream`,`barrier`) | 是 | 用途鉴别 |
| `t` | timestamp | 是 | 生成时间戳（RFC 3339 UTC,MUST 以 `Z` 结尾；毫秒部分可选——`...59Z` 与 `...59.000Z` 均合法，本文示例混用两种精度仅为展示） |
| `x` | integer | 是 | 过期时间戳（Unix ms） |
| `h` | string | 是 | 服务端 opaque handle（≥ 128 bit 熵），见 §8.3.1。stream positions 或 barrier target 均由 `h` 在服务端绑定表中解析，MUST NOT 内联进 cursor body。 |

服务端 MAY 添加其它 `_` 开头的私有字段（如 `_compression`）用于本地优化；这些字段必须先于 base64url 编码进入 canonical bytes。`_mac` 与 `_sig` 是保留字段，MUST NOT 出现在 v1 cursor body 中。

**handle-bound 但不在 wire body 的完整性绑定字段（normative）**：下列字段是 cursor 完整性校验（§8.3.1）的核心绑定项，但 **不作为 cursor body wire 字段出现**——它们由 `h` handle 在服务端绑定表中承载。这些字段 MUST NOT 出现在上方 §8.2 定义的 cursor body wire 字段集合中:

| 绑定字段 | 承载位置 | 说明 |
|----------|----------|------|
| `principal_id` | `h` handle 绑定表 | cursor 所属 principal,跨 principal 命中 MUST `cursor_integrity_invalid` |
| `device_id` | `h` handle 绑定表 | cursor 绑定的 device |
| `service_id` | `h` handle 绑定表 | issuing service 标识 |
| `filter_digest` | `h` handle 绑定表 | 订阅 / 查询 filter 的 digest,防跨 filter 复用 |
| `positions` | `h` handle 绑定表（`purpose=stream`） | stream cursor 的同步 / 分页位置 |
| `target` | `h` handle 绑定表（`purpose=barrier`） | barrier cursor 等待的目标 event |
| `expiry` | `h` handle 绑定表 | 与 body `x` 一致的服务端过期时间 |

这些字段是服务端 handle 表的内容，**不是** cursor body 字段；详见 §8.3.1。

### 8.3 验证规则

服务端接收 cursor 时 MUST 验证：

1. 前缀以 `ck:cursor:` 开头。
2. 其余部分是合法 base64url。
3. 解码后是合法 JSON。
4. 解码后 body MUST 通过 [`cursor.schema.json`](../../artifacts/schemas/cursor.schema.json)：`v` / `purpose` / `t` / `x` / `h` 必填，未知非私有字段、`_mac`、`_sig` 以及任何内联位置 / target 字段均 MUST reject `invalid_param`。
5. 解码后 `v` 是支持的版本。
6. 解码后 `purpose` 是 `stream` 或 `barrier`。
7. 解码后 `x` 在未来（允许 5 分钟时钟偏差）。
8. cursor 被消费的 binding context MUST 与 `purpose` 一致；binding context 的具体 wire 位置由对应 transport / API binding 定义。若 `purpose=barrier` 的 cursor 出现在 stream context，或 `purpose=stream` 的 cursor 出现在 barrier context，接收方 MUST 返回 `invalid_param`。
9. **TTL 硬上限**：先校验 `t` 的 well-formedness——`t` MUST 是合法 RFC 3339 UTC 时间戳（§8.2 要求 `Z` 结尾），且 `t` 解析得到的 Unix ms MUST ≤ `x` 解析得到的 Unix ms；`t` 非法（不可解析、非 UTC / 非 `Z` 结尾）或 `t_ms > x` 的 cursor MUST reject `invalid_param`（否则 `x - t_ms` 为负或解析异常，可令损坏 / 恶意 cursor 绕过下方 TTL 硬上限）。此外 `t` MUST NOT 位于未来：`t_ms` MUST ≤ 接收时刻的 Unix ms + 时钟偏差容忍（5 分钟，口径同规则 7）；超出 MUST reject `invalid_param`（否则 issuing 方可把 `t` 写成接近 `x` 的未来时间，令名义 TTL `x - t_ms` 通过下方硬上限校验，而实际剩余有效期 `x - now` 远超上限，绕过 TTL 硬上限）。随后以 `t` 解析为 Unix ms 后，`x - t_ms` MUST 满足以下硬上限：barrier cursor ≤ 3,600,000 ms（1 小时），stream cursor ≤ 604,800,000 ms（7 天）。超出上限的 cursor 视为 issuing 服务的协议错误，接收方 MUST reject `invalid_param`。理由：barrier cursor 仅是 RYW 等待屏障，过期意义随 frontier 追上而失去；stream cursor 在数周活动后已无因果对齐价值。

非法 cursor MUST reject，错误 `invalid_param`；已过期 cursor MUST reject，错误 `cursor_expired`；完整性校验失败（见 §8.3.1）MUST reject，错误 `cursor_integrity_invalid`。

### 8.3.1 完整性校验（normative）

服务端 MUST 在使用客户端回传的 cursor 推进任何不可逆 server-side state、恢复 stream 位置或解除读己之所写屏障之前，执行下列完整性校验；具体业务场景见对应 sync / API binding（例如 [`client-sync.md`](../sync/client-sync.md) §10 / §12）。仅通过 §8.3 语法 / TTL / purpose 校验不足以信任 cursor 内部状态。

- `h` MUST 是 issuing service 生成的不可猜测 handle（解码后熵 ≥ 128 bit）。
- 服务端 MUST 以 `h` 查 issuing service 本地表，记录绑定的 `(principal_id, device_id, service_id, filter_digest, purpose, positions, target?, expiry)` 元组。
- handle 不存在、已撤销、已过期，或绑定字段与当前 authenticated request 不匹配 → `cursor_integrity_invalid`。
- 校验通过后，服务端才可读取 handle 解析出的 `positions`（stream cursor）或 `target`（barrier cursor）并推进同步状态。
- handle 校验本身就是完整性校验，cursor body 不可加 `_mac` / `_sig`，也不可内联 `positions` 或 `target` 作为完整性来源。

完整性校验失败 MUST 映射 `cursor_integrity_invalid`（区别于 `cursor_expired`：前者是 tamper / cross-binding / 未知 handle，后者是 TTL 超时）。客户端收到 `cursor_integrity_invalid` 后应清理本地 cursor 缓存并按 [`client-sync.md` §12.3](../sync/client-sync.md) 恢复流程重做 initial sync。

### 8.4 Cursor 可迁移性

Cursor 对客户端不透明，且 v1 core cursor 是 stateful handle。`h` 是 issuing service 本地表的引用，其他服务无法从 cursor body 恢复 stream positions 或 barrier target。

当用户从 Principal Server A 切换到 Principal Server B 时（service replacement、portability 平面操作），B 收到 A 签发的 cursor 后 MUST 返回 `cursor_unrecognized`（不是 `cursor_expired`），客户端按全新初始同步处理；MUST NOT 猜测、解析或重放 A 的 handle。普通同服务请求中的未知、撤销或 cross-binding handle 仍按 §8.3.1 返回 `cursor_integrity_invalid`。

未来 profile MAY 在 `ck.profile.principal_server.v1` 之上引入显式 cursor translation operation；该 operation 与 transport binding 不属于 v1 强制范围。

### 8.5 测试向量入口

可执行向量位于：

- [`spec/v1/artifacts/fixtures/encoding-fixture.json`](../../artifacts/fixtures/encoding-fixture.json)

向量覆盖点：cursor 版本字段与过期、opaque round-trip、`h` handle 必填、过期 token 回退、非法额外字段拒绝。

### 8.6 一致性

声明支持 Cokret v1 同步的实现 MUST：

- 以不透明字符串形式接受和传输版本 1 cursor。
- 服务端 MUST 接收时验证所有 cursor 字段。
- 服务端 MUST 按 §8.2 canonical schema 编码 cursor 内部结构（私有字段限于 `_` 前缀）。
- 客户端 MUST NOT 解析 cursor 内容。
- stream cursor 的 server-side handle binding MUST 支持至少 50 个 Realm 的位置。
- **每 Realm 的 handle-bound frontier 长度 SHOULD ≤ 1000 个 event_id**：超出时 issuing 服务 SHOULD 用 `event_set_commitment.root` 或 snapshot pointer 折叠 frontier，再写入 handle binding。该上限避免大并发 actor Realm (≥ 1000 active actor 各自有 head event) 让 cursor authority metadata 无界增长。
- **整个 cursor base64url 解码后 canonical bytes MUST ≤ 64 KiB**：超出时 issuing 服务 MUST 用 snapshot pointer / commitment hash 折叠，MUST NOT 直接产出超大 cursor；receiver 收到超大 cursor MUST `invalid_param`。
- 大型 Realm 在 frontier 折叠为 `event_set_commitment.root` 或 snapshot pointer 后，仍 MAY 通过显式 sync extension profile 提供 range-based set reconciliation 能力，用于按差异大小协调缺口；该能力不得改变 Seal finality、Event 因果语义或 cursor 不透明性，且未声明该 profile 的 v1 consumer MUST 继续按 snapshot / backfill 路径恢复。
- 支持 stream cursor 与 barrier cursor 的过期时间；两者的 TTL 硬上限数值由 §8.3 规则 9 唯一定义，本节只引用不重复字面数值。
- 以适当错误拒绝非法 cursor。

## 9. Rank

列表排序 rank MUST 使用 `ck.rank.lexofractional.v1` profile，除非 Realm schema 显式声明其他 rank profile。

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

例如 `rank_between("", "0")` MUST 返回 `rank_exhausted`，因为在 start sentinel 与最小 rank `"0"` 之间不存在合法 rank。客户端或 reducer 遇到 `rank_exhausted` MUST 触发 rebalance 或要求调用方提交 `ck.container.rebalance`，MUST NOT 生成非法 rank。
- 当 rank 长度超过 128，或连续插入导致实现无法生成短 rank，客户端 SHOULD 请求或提交 `ck.container.rebalance`。Reducer MUST NOT 接受超过 128 字符的 rank。
- 同一 container 内 rank 完全相同的对象 MUST 按 `rank_source_event_hlc`、`rank_source_actor_id`、`rank_source_event_id`、`object_id` 继续排序；如果 rank source 元数据缺失，MUST 使用 `object_id` 作为最终稳定 tie-break，并在 conformance report 中声明降级。该 tie-break 仅用于 projection 展示序，不进入 canonical state、`state_root` 或授权判断。
- `ck.container.rebalance` 的 assignment 生成 MUST 基于权限裁剪前的 canonical ordered set。先按 reducer 已确定的稳定顺序排列 active edges，再选择最小宽度 `w`，使 `alphabet_length^w >= 2 * (item_count + 1)`；第 `i` 个对象（1-based）的 rank number 为 `floor(i * alphabet_length^w / (item_count + 1))`，以固定宽度 base62 编码并用 alphabet 第一个字符左填充。若所需 `w > 128`，实现 MUST reject 该 rebalance。
- Rebalance assignments MUST 覆盖 container 内全部 active edges，且 MUST NOT 新增、删除或跨 container 移动 edge。CAS 的 `expected_state_digest` 不匹配时，MUST 拒绝整个 operation，MUST NOT 部分应用。

## 9.5. Composite Cell Subject

部分 cell 的 subject 由多个 sub-component 复合派生（例如 `ck.device.authorize` 的 `(principal_id, device_id)`）。复合 subject 的 canonical 形态由本节定义；cell id、Control Move precondition、Lattice join 和 fixture 必须使用同一形态。

### 9.5.1 通用规则

- 复合 subject 的 canonical wire 形态 MUST 是 base64url（无 padding）编码的 SHA-256 digest：

  ```text
  cell_subject = base64url_nopad(sha256(canonical_json(components_array)))
  ```

  其中 `components_array` 是按本规范声明的固定顺序排列的 JSON array，所有 string element 已经 normalize 过（NFC、小写 typed ID、规范 DID）。身份类 sub-component（DID URI、handle、connection identifier 等 §2.1 列举的身份字段）在进入 `components_array` 前 MUST 先应用 §2.1 的 NFKC + case folding（与该字段用于 cell subject 派生的"比较 / 索引 / 黑名单匹配"语义一致），再纳入 hash 输入；否则仅 compatibility-equivalent 或大小写不同的两条 DID 会 hash 出不同 cell subject，造成同一主体的 device authorization cell 分裂（正是 §2.1 要防的同形 / 兼容字符攻击面）。
- 实现 MUST NOT 直接使用 `a|b|c` 这种管道分隔字符串作为复合 subject。canonical cell id、签名输入、state map 索引 MUST 使用 hash 形态。
- 复合 subject 的 sub-component 必须存在于 DataEvent / Control Move effect value 或兼容 Event payload 的具名字段中。
- 同一 standard cell family 的 `components_array` schema 由本规范固定，profile MUST NOT 擅自增删字段或重新排序。

### 9.5.2 标准复合 Subject

| Cell family / Event kind | components_array 顺序（来源字段） |
| --- | --- |
| `ck.component.device.authorization.v1` / `ck.device.authorize` | `[principal_id, device_id]` |
| `ck.component.device.authorization.v1` / `ck.device.revoke` | `[principal_id, device_id]` |

`principal_id` MUST 是无 fragment 的完整 DID URI（见 §4）；`device_id` MUST 是完整 `id:device` typed ID（`ck:device:<uuidv7>`）。

非复合 cell（例如 member 用 actor DID、capability grant 用 grant id、Realm policy 用 Realm id）直接把规范化 subject 放入 `ck:cell:<component>:<subject>`，不需要 hash 化。

接收方收到不符合本节定义的复合 subject components_array 时 MUST 返回 `schema_violation`。文档中若以管道分隔形态展示复合 subject，MUST 显式标注 "informational; canonical cell subject is base64url(sha256(canonical_json(...)))"。

### 9.6 State / Cell 编码索引（导航）

_Informative._ 本小节只做导航锚，不搬迁任何 normative 内容；各编码规则的 canonical 定义仍在所引小节。State / Cell 相关编码分散在多处，单点索引如下:

| 编码对象 | canonical 定义位置 |
| --- | --- |
| Cell subject 编码(复合 subject hash 形态、标准复合 subject 表) | 本文 §9.5 |
| `state_root` 的 Merkle 编码与 inclusion 规则 | [`authz/event-auth-state-resolution.md` §4.2](../authz/event-auth-state-resolution.md) |
| `state_root` / Seal hash 的 wire 形态与 algo 固定规则 | 本文 §3.3 |
| Hash wire 形态(`<suite>:<hex>`)与 Digest Suite registered set | 本文 §3.1 / §3.2 |
| Cell tuple 引用形态(`ck:cell:<component>:<subject>`) | 本文 §4(special forms) |

## 10. Encrypted Envelope Digest

加密 payload 的 digest MUST 覆盖密文和明文路由元数据：

```text
aad_bytes = canonical_json(aad)
aad_digest = sha256(aad_bytes)
payload_metadata_bytes = canonical_json(payload_metadata)
encrypted_payload_bytes = base64url_decode(ciphertext)
payload_digest = sha256(payload_metadata_bytes || encrypted_payload_bytes)
```

上式产出 32 字节 raw digest；其 wire 形态 MUST 为 `sha256:<lowercase_hex>`，与 §3.1 一致。`payload_metadata` 的字段集合、缺失字段处理、`mls-rfc9420` 下不得携带 `authentication_tag` 的规则，以 [`crypto-media/encryption-and-audit.md` §2.3.3](../crypto-media/encryption-and-audit.md) 为唯一真源。

`payload_metadata` 至少覆盖 `scheme`、`version`、`group_id`、`epoch`、`content_type`、`aad_visibility_event_id`、`aad` 与 `key_ref` 中实际出现在 envelope 的字段；字段缺失时必须省略，不得写入 `null`。实现 MUST NOT 使用明文 payload 作为 `payload_digest` 输入，也不得把 base64url ciphertext 字符串本身作为密文字节输入。

### 10.1 AEAD nonce uniqueness（normative）

任何在 v1 wire 上承载 AEAD 加密内容的 envelope（`encrypted_payload`、blob attachment、`to_device` payload 等）MUST 满足 AEAD nonce 唯一性 contract。下列公式是 v1 的 canonical nonce 派生定义；领域文档只声明各自的 `purpose` 取值和 envelope 字段位置。

下文 `N_AEAD` 指所选 AEAD algorithm 的 nonce 字节长度：XChaCha20-Poly1305 为 24，AES-GCM 为 12。

```text
sender_nonce_prefix = MLS-Exporter(
    label   = "cokret-aead-sender-nonce-prefix-v1",
    context = canonical-bytes({
      "key_ref": <key_ref-canonical>,
      "epoch": <mls-epoch>,
      "device_id": <sender-device-id>,
      "purpose": <aead-purpose>,
      "aead_profile": <aead-profile-id>
    }),
    length  = N_AEAD - 8
)

nonce = sender_nonce_prefix || device_nonce_counter_be64
```

- **Nonce 唯一性**：实现 MUST NOT 在同一 `key_ref` 下重用 nonce。AEAD 在 nonce 复用时机密性与完整性同时被打破。
- **Counter 规则**：`device_nonce_counter_be64` 是 8 字节 unsigned big-endian 单调计数器；同一 `(key_ref, epoch, device_id, purpose, aead_profile)` 下 MUST 单调递增且不得复用。设备 MUST 持久化 counter；若无法恢复该 epoch 的本地 counter，设备 MUST 先发起 MLS Commit 推进到新 epoch，并在新 epoch 从 0 初始化 counter。
- **跨设备域分离**：同一 `(key_ref, epoch, purpose, aead_profile)` 下，每个 active sender 的 `sender_nonce_prefix` MUST 唯一。接收方按 sender `device_id` 重算前缀并校验；前缀冲突或与声明 sender 不匹配时 MUST fail closed (`aead_nonce_sender_domain_collision`)。
- **不回退到 random**：实现 MUST NOT fallback 到 random nonce。96-bit AEAD (AES-GCM) 在 ~2^48 次操作上有显著 birthday-bound 碰撞率；Cokret MLS application key 跨多设备共享，naive random nonce 不满足 v1 normative。
- **接收方 replay 防护**：接收方 MUST 维护 per-`(key_ref, epoch, device_id, purpose, aead_profile)` 已见 counter 集合或等价无误判结构，重复 counter MUST 触发 `failed_precondition` reason=`aead_nonce_counter_replay`。
- **AAD binding**：AEAD AAD MUST 绑定 `(key_ref, ciphertext_digest, nonce)` canonical 形态，防止 (key, nonce) 下的 ciphertext 被与另一 AAD 配对解密。
- **不同 AEAD 用途独立 nonce 域**：`purpose` MUST 写入 exporter context。标准 purpose 取值由消费域文档声明；未声明 purpose 的 AEAD envelope MUST fail closed。
