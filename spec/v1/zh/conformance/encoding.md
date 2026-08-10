---
title: Encoding, IDs, Hashes, Signatures
status: candidate
normative: true
stability: v1
updated: 2026-07-30
sidebar:
  label: Encoding & IDs
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [normative-language.md](./normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

本文定义 Arkret 的 canonical encoding、ID、hash、signature、cursor、HLC 与 rank 编码规则，确保不同实现能得到相同 digest 和验证结果。

## 2. Canonical JSON

Arkret canonical JSON 是签名、hash、event digest、receipt digest、snapshot commitment 和 cursor 内部状态的唯一编码 profile。实现 MAY 复用 RFC 8785 / JCS 类库，但最终输出必须满足本节的收窄规则和 `conformance-vectors.md` 的测试向量。

Arkret canonical JSON MUST 使用：

- UTF-8 不带 BOM；输入若包含 UTF-8 BOM（`U+FEFF` 编码 `EF BB BF`，无论出现在 stream 起始还是 string value 内部）、malformed UTF-8、孤立 surrogate 或无法被 JSON parser 唯一解释的字符串，MUST reject。`U+FEFF` 在 string value 中只允许作为 zero-width no-break space 的语义存在，但 v1 canonical JSON MUST NOT 接受此用法——任何 `U+FEFF` 出现都按 schema_violation 拒绝。
- object key 按 RFC 8785 / JCS 规则排序：先比较属性名的 UTF-16 code unit 序列，按字典序升序排列，并在每一层独立排序。实现 MUST NOT 改用 Unicode code point 排序；对补充平面字符，UTF-16 surrogate pair 顺序是规范结果。
- 无 insignificant whitespace。
- JSON object 中的重复 key MUST reject，MUST NOT 采用“最后一个 wins”或“第一个 wins”。
- number MUST 使用 RFC 8785 / JCS 等价的唯一 decimal serialization；NaN、Infinity、-Infinity、`-0`、无法精确往返的 number、超出 JSON safe integer 范围 `[-9007199254740991, 9007199254740991]` 的 number MUST reject。**v1 wire MUST NOT 使用非整数 number**：所有签名 canonical object 的 number 字段 MUST 是 JSON integer。需要超过 safe integer 范围的计数器、偏移或大整数 MUST 编码为带显式格式约束的 string（例如 fixed-width hex / decimal string），MUST NOT 作为 JSON number 进入 canonical bytes。比例、置信度、进度等小数值 MUST 编码为整数 + 显式 scale（推荐字段后缀 `_basis_points` 表示万分数 0..10000，或 `_x1000`、`_x1000000` 等明确比例）；`confidence_basis_points: 7500` 表示 75.00%。这条收紧规则取消了"何时允许 number canonicalization"的可选语义，使签名输入 100% 确定。
- **Arkret 自有绝对时刻只有一个 wire profile**：固定 UTC 毫秒 `YYYY-MM-DDTHH:MM:SS.sssZ`。三位小数 MUST 始终存在，整秒写为 `.000Z`；微秒或纳秒输入 MUST 在构造 typed wire object、transcript 或 digest **之前**按 Unix 时间向负无穷方向 floor 到毫秒，MUST NOT 四舍五入。接收方 MUST 在 digest/signature/AAD 重建之前拒绝无小数、非三位小数、`+00:00` 或其他 offset、小写 `t`/`z`、leap second、非法 Gregorian 日期及首尾空白，MUST NOT 宽松解析后正规化再验签。共享机器定义是 [`time.schema.json#/$defs/timestamp`](../../artifacts/schemas/time.schema.json)。隐私或业务降精度只截断时间**值**，不改变 spelling；秒/分钟/hour bucket 仍以 `.000Z` 结尾。
- 时间表示按语义而不是按使用位置分类：duration/latency/age/window/timeout 使用带单位的 integer（如 `*_ms`），不是绝对时刻；JWT/DPoP/OIDC `NumericDate`、TURN expiry、did:webvh `versionTime` 等外部字段严格遵循其外部协议并由 adapter 隔离；HLC physical component 与 UUIDv7 timestamp bits 是算法内部 Unix 毫秒编码；calendar local date/time 是带 zone/calendar 的 wall time。上述类型均不得冒充 Arkret timestamp，Arkret 自有公开 JSON 也 MUST NOT 派生并行 `*_unix` / `*_unix_ms` instant。
- whole-object digest/signature 对通过 schema 的 `.sssZ` 字符串原样 canonicalize。独立 transcript/AAD 绑定已有 Arkret timestamp 时 MUST 使用相同字段名和相同 canonical 字符串；“参与密码学”本身不是转成 epoch integer 的理由。producer 必须先构造 typed canonical timestamp，receiver 必须先严格验证 wire spelling，再重建 canonical bytes。
- 字段名使用 snake_case。

Event Envelope 的签名和 hash 输入 MUST 是去除 `proofs`、`unsigned`、`event_id` 与 **reducer-stamped 顶层字段**（v1 只有 `actor_kind`）后的 canonical JSON bytes，并且 MUST 保留 producer 声明的 `scope_ref`。`event_id` 由这个 digest 一次前向派生，因此排除它不改变任何 producer-authored 事实的覆盖范围。`unsigned` 是传输/本地附加信息，MUST NOT 影响 event digest 或 proof `event_digest`。`actor_kind` 由 producer 提交时 MUST NOT 携带、reducer 接受时才 immutable 写入，因此不进入 producer `proof.event_digest`。`scope_ref` 不是 stamp：它由 producer 签名，reducer 必须从 payload 与 accepted references 独立派生并逐字段比对。实现 MUST NOT 对已经签名的 bytes 做大小写规范化、ID 前缀补全、字段默认值补写、key 重排以外的语义改写。签名字节的不可变性是协议演进的根约束——升级 MUST NOT 改写历史签名 bytes，而是用重放/投影重建派生视图，详见 [overview/evolution-and-compatibility.md](../overview/evolution-and-compatibility.md)。

**架构取舍（normative）**：v1 不引入开放 `stamped` 容器，Event 顶层 exclusion set 固定为 `actor_kind`。新增 reducer-stamped 顶层字段会在 producer 签名之外创造新事实来源，v1 MUST NOT 接受。低层 canonicalizer 必须从 Event schema 消费该单元素 exclusion set，不得自行维护另一份业务字段列表。

生产者 MUST 在所有 v1 签名对象中使用 JSON integer 表示数值。Schema 要求小数语义的字段（如概率、进度、置信度）MUST 使用整数 + scale（见上文 `_basis_points` 等约定），生产者和消费者按预定义 scale 解释，无须做 number canonicalization。任何进入签名 / canonical wire bytes 的 v1 schema MUST NOT 出现 `type: number`（非整数）字段；该约束在 OpenAPI 镜像上由 lint 强制。唯一例外是**派生的 read / projection 响应**中承载「被投影字段运行时类型」的 filter 值（例如 `view.schema.json#/$defs/collection_projection_view` 分组 source 的 `value`、OpenAPI `CollectionFieldValueGroupSource.value`）：它们不进入 canonical Event bytes、不参与签名，MAY 保留 `type: number`，且在 OpenAPI 镜像中 MUST 以 `# lint-waiver(type:number): <理由>` 标注；后续 wire 修订可将需要小数的字段类型迁移为 `{integer, scale}` 信封。

### 2.1 时间语义 inventory 与最小例外表

实现和 machine contract MUST 先按下表分类，再选择编码；字段位于签名、digest、AAD、cursor、数据库或 UI 中不是分类依据。外部例外只有外部 owner 仍拥有该 wire 字段时才成立，adapter 转换出的 Arkret 自有字段立即回到固定 `.sssZ` profile。

| 类别 | 当前字段/边界 | owner 与规范依据 | wire / internal 表示 | 删除条件 |
| --- | --- | --- | --- | --- |
| Arkret absolute instant | 所有 Arkret schema 中的 `created_at`、`updated_at`、`issued_at`、`expires_at`、Event `timestamp`、cursor 时间 | Arkret v1；本节与 `time.schema.json#/$defs/timestamp` | JSON fixed `.sssZ`；transcript/AAD 保持原字段名与原字符串 | 不可列入例外；字段删除时随合同删除 |
| Duration / latency / age / window / timeout | `ttl_ms`、`timeout_ms`、`retry_after_ms`、`max_age_ms` 等 | Arkret 字段语义和单位后缀 | JSON non-negative integer；不是 instant | 字段不再表示量时必须重命名并重新分类，禁止原名改义 |
| JWT / DPoP / OIDC NumericDate | JWT claim `iat`、`nbf`、`exp` | [RFC 7519](https://www.rfc-editor.org/rfc/rfc7519)；DPoP 另由 [RFC 9449](https://www.rfc-editor.org/rfc/rfc9449) 继承 JWT | 外部 token 中为 epoch seconds；Arkret producer 输出整数，external verifier 依适用 profile | token 不再是 JWT/DPoP/OIDC 或 claim 离开外部 token 时立即删除例外 |
| TURN REST credential | TURN username 中的 expiry prefix | TURN REST credential provider contract（[draft-uberti-rtcweb-turn-rest](https://datatracker.ietf.org/doc/draft-uberti-rtcweb-turn-rest/)） | adapter 最末边界的 Unix seconds；Arkret ICE response 自有 `expires_at` 仍为 `.sssZ` | provider 不再使用该 credential contract 时删除 |
| did:webvh | canonical DID log / operation 的 `versionTime` | [did:webvh v1.0 method specification](https://identity.foundation/didwebvh/v1.0/) | method-owned ISO 8601 UTC spelling；不得由 Arkret formatter 重写 | 字段离开 canonical DID log、成为 Arkret 投影时删除例外并使用 `.sssZ` |
| Algorithmic epoch | HLC physical component、UUIDv7 timestamp bits | 各算法的规范位布局 | internal Unix milliseconds / bits；不是并行 JSON instant | 算法替换或该值被公开为业务时间字段时删除例外 |
| Local wall time / date | calendar `start` / `end` / `recurrence.until`、recurrence occurrence key、zone-aware local start | [`time.schema.json#/$defs/local_date`](../../artifacts/schemas/time.schema.json) 与 `#/$defs/local_date_time`（整秒，无 offset / `Z` / 括号 Zone / 小数秒） | 独立 local date/time + 显式 `timezone` 与 `tzdb_version`；不是 UTC instant | 一旦语义改为绝对时刻，删除例外并使用 `.sssZ` |
| Internal storage / computation | DB epoch column、clock arithmetic、TTL comparison | 实现内部，无 wire owner | MAY 使用 Unix milliseconds；跨 wire 前必须转换 | 值进入公开 JSON、transcript 或跨服务合同即删除例外 |

Schema source lint 的当前外部 `format: date-time` allowlist 只有 did:webvh `ServiceWebvhInceptionOperation.versionTime`；JWT/DPoP/OIDC 与 TURN 使用数值或复合字符串，因此不得伪装成 `date-time` allowlist 项。新增例外 MUST 同时登记 owner、规范链接、精确字段路径和删除条件，并增加互操作测试；无法分类的字段 MUST 先修改本规范，不得从现有 fixture 反推合同。

### 2.1.1 Optional nullable 字段的 presence 语义

JSON Schema 同时允许 property 省略和显式 `null`，只表示两种 wire spelling 都合法，并不自动创造
两套业务状态。为避免每个 SDK 为普通 projection、期限或可选附件复制三态状态机，v1 使用以下闭合
规则：

- optional + nullable 且没有 `default` 的 property，默认把 absent 与显式 `null` 归一为同一个空值；
  canonical producer MUST 省略该 property，receiver MUST 接受并按同一语义处理两种输入。
- 若该 property 在适用的 `if/then`、`oneOf` 或其它分支中被 `required`，则分支要求优先：missing
  是 schema violation，显式 `null` 才是该分支的空值。SDK 可以用判别 enum 表达分支，但不得让普通
  `Option<T>` 绕过入站 Draft 2020-12 校验。
- 只有 property 明确声明 `"x-arkret-presence-semantics": "distinct"`，且正文逐项定义 absent、null、
  value 三者效果时，三种 wire 状态才具有不同业务语义。producer/receiver 的类型系统此时 MUST 使用
  `Missing | Null | Value(T)` 等价表示，禁止用二态 optional 折叠。
- 不得仅因字段名称包含 `expected`、`state`、`proof` 或 `ref` 就推断三态；安全关键 CAS 若确需
  omission 表示“无断言”，必须显式使用上述扩展并提供三种正向与交叉负向 vector。

当前唯一 `distinct` 目标是 Circle membership CAS 的 `expected_membership`。Realm default-strand 与
Strand watch CAS 均在各自 schema description 中规定 absent≡null=`head_eq null`，因此使用普通
optional；它们不是“省略即关闭 CAS”的例外。

### 2.2 String profile 与 Unicode 处理

字符串 MUST 先按其协议角色选择 profile；实现 MUST NOT 对 DID、URI、email、phone、display text 与 Arkret human identifier 套用同一个 NFKC / case-fold normalizer。所有进入 canonical JSON 的 string value 仍 MUST 是 NFC；receiver MUST 验证而不得在验签阶段静默改写非 NFC wire bytes。

v1 的 machine-readable profile 与版本钉定见 [`string-profile-registry.json`](../../artifacts/registry/string-profile-registry.json)，共享 schema 定义见 [`string-profiles.schema.json`](../../artifacts/schemas/string-profiles.schema.json)：

| Profile | 适用字段 | preparation / 验证 | 比较与授权语义 |
| --- | --- | --- | --- |
| `arkret_human_identifier` | handle / realm alias localpart、native personal Agent selector `slug` | RFC 8265 `UsernameCaseMapped` enforcement（width mapping、Unicode lowercase、NFC）后排除 Arkret 结构分隔符；长度同时按 code point 与 UTF-8 octet 限制 | prepared code point sequence 精确相等；可建立唯一索引 |
| `arkret_single_line_display_text` | `title`、`display_name`、`label` | NFC；允许多语言、emoji、数学符号和混合脚本；拒绝 CR/LF、C0/C1、BOM、bidi embedding / override / isolate；不得仅为空白 | 永不用于主体相等、授权、ACL 或签名者判定 |
| `arkret_short_text` | `summary`、短 `description` | NFC；允许 LF 换行；拒绝 CR、其它 C0/C1、BOM 与 bidi embedding / override；字段 schema 决定 code-point 上限 | 非权威全文 |
| `arkret_content_text` | message / content / body | NFC；允许正常 bidi 与 emoji 序列；拒绝 BOM 与非文本控制字符；renderer 负责转义和方向隔离 | 内容；不参与 identifier 比较 |
| `arkret_protocol_token` | kind、schema/profile ID、action、enum、algorithm、base64url / hex | 字段专属 ASCII grammar | byte-exact 或字段专属比较 |
| `arkret_external_string` | DID、DID URL、URI、email、phone、provider identifier | 委托对应外部标准、DID method 或已登记 provider profile | 禁止 Arkret 全局 NFKC / case folding |

外部字符串的具体规则：

- generic DID parser 只验证 DID Core 语法；method name 按 DID Core 为小写 ASCII，method-specific-id 与 DID URL components 保留原值并按对应 DID method / URI 规则比较。只有 resolver 提供的 `canonicalId` / `equivalentId` 才能建立强等价，Arkret MUST NOT 因全串大小写折叠而合并 DID。
- email 保留 local-part；domain 使用 §2.2.1 的 IDNA profile。mailbox issuer / provider 决定 local-part comparison；非 ASCII local-part 的 SMTP 投递还要求 RFC 6531 `SMTPUTF8`。
- phone 使用 E.164 或声明的 provider profile；`acct:` 使用 RFC 7565 / RFC 3986；opaque provider identifier 按 bytes 保留。
- organization `display_name` 与个人 display name 都是 display text，不是 organization handle；混合脚本最多触发 UI warning，不得因中文夹英文、品牌名夹数字而拒绝。

UTS #39 skeleton 只是 registration authority 在**同一 namespace**内使用的派生 collision index，不是 canonical value、wire 字段、proof transcript 或协议 equality。authority MAY 要求 `Highly Restrictive` restriction level；skeleton 数据版本升级时 MUST 重建派生索引但 MUST NOT 改写既有 canonical identifier。不同 authority 或 handle / realm-alias 两个不相交 namespace 的 skeleton 相同，不建立协议等价。

`string-profiles.schema.json` 为上述 profile 声明 8 个自定义 JSON string format。这些 format 的
normative 语义由 PRECIS、UTS #46 与 NFC 决定，JSON Schema 的 `pattern` / `minLength` / `maxLength`
只做粗粒度 shape 检查，因此实现 MUST 在 schema 校验之外执行 profile validator。唯一的正负向 vector
集合是 [`string-profile-fixture.json`](../../artifacts/fixtures/string-profile-fixture.json)，每个被拒值
显式声明拒绝层：`schema_pattern` 表示粗 schema 已能拒绝，`profile_validator` 表示该值刻意通过粗
schema、只有 profile validator 能拒绝。任何实现只要接受后一类值，即使 JSON Schema 校验通过也不合规。

| Format | Vector |
| --- | --- |
| `arkret-human-identifier` | `ak.vector.encoding.string_profile_human_identifier.v1` |
| `arkret-agent-slug` | `ak.vector.encoding.string_profile_agent_slug.v1` |
| `arkret-idna-a-label-domain` | `ak.vector.encoding.string_profile_idna_a_label_domain.v1` |
| `arkret-canonical-handle` | `ak.vector.encoding.string_profile_canonical_handle.v1` |
| `arkret-acct-uri` | `ak.vector.encoding.string_profile_acct_uri.v1` |
| `arkret-single-line-display-text` | `ak.vector.encoding.string_profile_single_line_display_text.v1` |
| `arkret-short-text` | `ak.vector.encoding.string_profile_short_text.v1` |
| `arkret-content-text` | `ak.vector.encoding.string_profile_content_text.v1` |

`format: binary` 只出现在 multipart / binary-stream transport shape，不是 JSON string 内容编码断言，
因此不在本表内，也 MUST NOT 被实现伪装成一个恒真的 string format assertion。

#### 2.2.1 IDNA domain profile

面向用户的 domain 输入 MAY 是 U-label；canonical wire、签名、缓存键和唯一索引 MUST 使用 UTS #46 Nontransitional Processing 得到的小写 A-label，并启用 `CheckHyphens=true`、`CheckBidi=true`、`CheckJoiners=true`、`UseSTD3ASCIIRules=true`、`VerifyDnsLength=true`。实现 MUST 拒绝 trailing dot、空 label、单 label domain、超过 63 octets 的 label、超过 253 octets 的 domain、无效 `xn--` 与不能通过 ToUnicode → ToASCII round-trip 的 A-label。JSON Schema 的 ASCII pattern 只做粗粒度 shape 检查，不能替代该 normative validator。

### 2.3 备用 canonical encoding (profile-gated)

v1 wire format 锁定为 canonical JSON。需要更紧凑或更适合受限设备的 binding 时，profile MAY 引入备用 canonical encoding：

- **CBOR (RFC 8949) deterministic encoding** — 与 IETF MLS / COSE / WebAuthn 同源；适合 IoT、嵌入式与高密度 wire 场景。引入该 encoding 的 profile activation **SHOULD 直接 pin 上游已标准化的 deterministic CBOR profile —— CDE（CBOR Common Deterministic Encoding，draft-ietf-cbor-cde）或 dCBOR（draft-mcnally-deterministic-cbor）—— 而非自拟 deterministic 细则**，以复用上游 conformance 向量与多实现、并与 COSE / CWT 生态自然互通；自拟细则会重新发明等价规则并承担"与他人不互通"风险。所选 deterministic profile 按 MIMI 同构的 draft-pinning 纪律固定（draft 变更 = 新 profile 版本）。
- 其他 binary encoding（如 protobuf、msgpack）SHOULD 通过 profile 单独引入，MUST NOT 静默替换 v1 canonical JSON。

备用 canonical encoding 通过 **digest suite 机制**（§3.1 / §3.2、[`digest-suite-registry.json`](../../artifacts/registry/digest-suite-registry.json)）进入协议，规则如下：

- 引入备用 encoding 的 profile（id 形如 `ak.profile.encoding.cbor.v1`）MUST 在 digest-suite registry 注册对应 suite（如 `cbor.sha256`），并交付该 suite 的 activation requirements：deterministic 编码细则、CDDL、**schema 无关**的 JSON ↔ 该编码类型映射（string→text string、integer→integer 的哑映射；归一化 MUST NOT 依赖 schema 知识，否则 digest 会随 schema registry 版本漂移）、以及 per-suite conformance vectors。
- 备用 encoding profile 还 MUST 明确 proof envelope 的编码边界，不能只定义 object digest：若继续使用 §6 `detached_jws`，profile MUST 钉定 proof binding object 的 canonical bytes、JWS protected header 与备用编码正文之间的映射，并交付逐字节签名向量；若改用 COSE，则 MUST 另行登记版本化 proof profile，钉定 `COSE_Sign1` protected headers、algorithm id、external AAD / payload binding、proof-context domain separation、verification order 与负向向量。声明 CBOR encoding **不自动等于**声明 COSE proof，receiver MUST NOT 在两种 proof 形态间猜测或静默转换。
- **归一化编码是 Realm 级声明**：Realm 在 create event 的 `digest_algorithm` 字段锁定唯一 suite（§3.3），该声明是权威；事件 envelope 的 `requirements.features[]` 声明对应 encoding profile 作为能力要求，但 MUST NOT 与 Realm 声明的 suite 冲突。未声明备用 suite 的 Realm 一律按 canonical JSON 解析。
- 由于 Realm 级 suite 排他（§3.3），同一 Realm 内不存在 JSON 与备用编码两套并行 digest，**跨编码的双向 digest 等价向量不是验证路径的需求**；仅当 profile 提供 json→备用编码的 suite transition 路径时，MUST 给出 transition Seal 双 root 向量（见 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §9.3.2）。
- 实现 MAY 出于调试 / 退化传输目的输出备用编码 Realm 中对象的 JSON 渲染视图，但该视图是 informational 投影：MUST NOT 进入签名、digest、`prev_refs` 解析或任何 canonical 路径。

## 3. Hash

### 3.1 Wire 形态

Arkret 所有 hash wire value MUST 形如：

```text
<suite>:<lowercase_hex_digest>
```

- `<suite>` 是 **digest suite** 标识符——digest 定义的注册元组 **(canonicalization, hash_algorithm)** 的 canonical id，取自 [`digest-suite-registry.json`](../../artifacts/registry/digest-suite-registry.json)（机器可读 source of truth，§3.2 表为其阅读视图）。文法：裸 id（无点号，如 `sha256`）表示 canonicalization = canonical JSON（§2），与既有 wire 语义完全一致；点分 id `<canonicalization>.<hash>`（如 `cbor.sha256`）表示备用归一化编码 suite。本文其他小节及兄弟文档中沿用的 `<algo>` 称谓即 `<suite>` ——对全部裸 id 二者同义。
- `<lowercase_hex_digest>` 是按 suite 的 canonicalization 产出 canonical bytes、再以 suite 的 hash 算法计算的 raw digest 的小写 hex 编码，长度由 hash 算法决定。
- suite、长度、编码三者**任何一项**与 registry 行不一致 → schema_violation。
- suite 是**注册元组**：实现 MUST NOT 把 canonicalization id 与 hash id 自由组合出未注册前缀；registry 中不存在的组合不存在于协议中。
- suite 前缀是 digest 字符串值的一部分，因而被签名字节覆盖：digest 定义本身不可在不破坏 proof 的情况下被改写或降级。

### 3.2 Digest Suite / Hash Agility Set

digest suite 的 canonical 机器来源是 [`digest-suite-registry.json`](../../artifacts/registry/digest-suite-registry.json)（与 §6.1 Signature Suite registry 对称）；schema 中 digest-suite 选择字段（如 Realm `digest_algorithm`）的 enum MUST 在该 schema 版本发布时由当时 registry active rows 生成并冻结。后续 suite 激活必须按 [`schema-registry.md` §6.1(b.1)](./schema-registry.md) 发布新 schema 版本，不得原地扩写旧 enum。下表是 v1 active 且 canonicalization = canonical JSON 的 suite 集合的规范阅读视图：

| Algo | Digest 长度 | v1 角色 | 抗量子 / future-ready 评估 |
| --- | ---: | --- | --- |
| `sha256` | 32 bytes（64 hex） | **v1 default**；所有 receiver MUST 支持。Event digest、Merkle leaf、state_root、blob CID、receipt digest 等核心字段默认使用。 | 不抗量子（Grover 把搜索成本减半到 2^128，仍可用）；通过 `ak.profile.hash_transition.v1` 可平滑迁移到 stronger hash。 |
| `blake3` | 32 bytes（64 hex） | v1 optional；声明 `ak.profile.hash.blake3.v1` 的实现 MUST 支持，并通过 `ak.vector.encoding.digest.blake3.v1` 的正向 KAT 与 suite/长度/downgrade 负例。性能最佳（可并行）；blob CID 与高吞吐场景推荐。 | sha256-class 抗碰撞；非 NIST。 |

v1 active 集合刻意保持最小（`sha256` + `blake3`）。需要 algorithm diversity（如 SHA-3 / Keccak 家族对冲 SHA-2 结构性风险）或抗量子 hash 时，按 registry 规则**加法注册**新行（新 hash profile + conformance vector），wire 形态无需重写；不预注册无实际使用场景的算法。

除上表 active rows 外，registry 还以 **reserved** 状态登记了备用归一化编码 suite（当前为 `cbor.sha256`，deterministic CBOR + SHA-256，gate 为 `ak.profile.encoding.cbor.v1`，见 §2.3）。reserved suite 钉定 wire 前缀与 gate，但在其 `activation_requirements`（编码细则 + CDDL + 类型映射 + conformance vectors）全部满足并在 registry release 中翻为 active 之前，**MUST NOT 出现在 wire 上**——接收方按未识别 suite 前缀 fail closed 处理即可，无需特判。

扩展 profile MAY 通过新 hash profile 加入抗量子 hash（如 SLH-DSA hash family、SHAKE256 派生），也 MAY 通过新 encoding profile 注册备用归一化 suite；v1 wire 形态 `<suite>:<hex>` 已经为这两类加法准备好——**无需重写 wire**。

实现 MUST：

- 默认按 `sha256:` 解析；遇到未识别的 suite prefix（含 registry 中 reserved 状态、未注册点分组合、未知 id）→ 若位于 critical field（event_digest、state_root、prev_refs blob hash）→ fail closed (`unsupported_digest_algorithm`)；若位于非 critical metadata（如对象的 derived fingerprint）→ MAY 记录为 unknown 并 preserve raw bytes。
- 在 `server/describe.crypto` 暴露支持的 digest suite 集合；client 可据此选择写入算法。（`describe.crypto` 还 MUST 暴露支持的**签名** algo 集合，该 MUST 的权威声明集中在 §6.1 Signature Suite registered set。）
- MUST NOT "算法升级"已签名的 canonical bytes：一旦 Event 用 `sha256:` 发布，verify 路径永远按 sha256 重算；实现 MUST NOT 因为本地默认换成 blake3 就重算并替换。

### 3.3 State Root 与 Seal Hash 编码

`state_root`、Seal `id`、Event `event_digest` / `event_id` 引用、receipt digest 这几条核心承诺字段的 wire 形态由所属 Realm 在 create event 中通过 `digest_algorithm` 字段固定（默认 `sha256`）。`digest_algorithm` 的取值是 [`digest-suite-registry.json`](../../artifacts/registry/digest-suite-registry.json) 的 **active suite id**——它锁定的不只是 hash 算法，而是完整 digest 定义（canonicalization × hash）。Control Move 是 reducer-input Event 的控制面协议视图；Control Move 级引用 MUST 使用 enclosing Event 的 `event_id` 或 `event_digest`。

**Realm 级 suite 排他（normative）**：一个 Realm 同一时刻 MUST 只有一个 live digest suite；Realm 内所有后续 Seal / Event digest / state_root / receipt digest MUST 使用同一 suite。接收方在 Realm 上下文中遇到 suite 前缀与该 Realm 声明不符的 digest（Transition Seal 的 `previous_state_root` 除外）MUST 按 schema_violation 拒绝，即使该 suite 本身是 receiver 支持的 active suite——这条排他规则消除"同一语义对象在同一 Realm 内拥有两个合法 digest"的去重 / 重放二义性（`duplicate_conflict` 配对、`prev_refs` 解析、幂等键均依赖单一 digest 定义）。跨 Realm 引用按 digest 值自带的 suite 前缀验证，无需上下文。

切换 suite（hash 分量升级，或归一化编码分量切换）需要通过 `ak.profile.hash_transition.v1` snapshot commitment + signed compaction Seal 在 frontier 上做一次 suite transition Seal，新旧 suite 都能在 transition Seal 上验证 inclusion。详细规则见 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §9.3.2（digest suite transition）。

### 3.3.1 Snapshot / Event-set Merkle Root 编码

Snapshot reducer output root 与 snapshot event-set commitment MUST 使用
[`event-auth-state-resolution.md` §6.2.2](../authz/event-auth-state-resolution.md)
定义的同一套 RFC 6962 域分隔 Merkle 组合规则；领域章节只定义 `leaf_data`
与 leaf 顺序。本节钉定 snapshot 的领域映射：

- 领域规则先产生 `<suite>:<hex>` digest，去掉 suite 前缀并解码为 raw bytes，作为 `leaf_data`。
- leaf MUST 为 `H(0x00 || leaf_data)`；内部节点 MUST 为 `H(0x01 || left_raw || right_raw)`。
- 奇数层尾节点 MUST 原样提升且不得复制；单 leaf root MUST 是带 `0x00` 前缀的 leaf hash。
- 空集合 root MUST 是 `H` over empty bytes；`sha256` 时为 `sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`。
- tree construction 本身不排序。snapshot state leaves 使用 `(kind, id)` canonical byte order，snapshot event-set leaves 使用 `(actor_id, actor_seq, event_id)`。

snapshot、event-set 与 Seal root 因而共用一套 byte-level 实现；任何无
`0x00` / `0x01` 域分隔的旧式组合 MUST 被当作 root mismatch 拒绝。

### 3.4 Multihash 兼容（profile-gated）

声明 `ak.profile.encoding.multihash.v1` 的实现 MAY 在 wire 上接受 multihash 风格的二进制 hash header（multicodec varint + length + digest）作为额外 reading format，但 canonical JSON 上的 wire value 仍 MUST 使用 §3.1 的 `<suite>:<hex>` 字符串形态。引入 multihash profile 的目的是与 IPFS / libp2p / Iroh 生态做内容寻址互通；它不替换 v1 wire 默认。

## 4. ID

协议 wire / canonical object 层的 typed ID 格式：

```text
ak:<kind>:<payload>
```

标准 `kind` 的机器可读 source of truth 是 `artifacts/registry/id-kind-registry.json`。本文只定义通用规则。

`ak:` 前缀表示 Arkret 协议命名空间；`<kind>` 表示对象或引用类型；`<payload>` 是该 kind 的
`id_form` 唯一决定的稳定身份载荷。完整 typed ID 是 wire value 的一部分，MUST 出现在：

- Event Envelope、canonical object、receipt、snapshot、fixture 和 OpenAPI / non-HTTP DTO。
- canonical JSON、签名 payload、`event_digest`、cursor 内部 state、federation payload、audit log。
- 跨服务引用、日志和错误响应中需要自描述对象类型的字段。

数据库或本地索引实现 MAY 不把 `ak:<kind>:` 前缀作为主键的一部分存储：`producer_allocated`
kind 可使用 PostgreSQL `uuid` / `BYTEA(16)` 保存完整 UUID；Event 与 `event_derived` /
`suite_tagged_full_digest` kind 则必须保存完整 33-byte token（例如 `BYTEA(33)`），不得截断为 UUID。
实现也 MAY 另设仅本地可见的 surrogate row key，但 canonical identity 列必须无损保留，并在进入
canonical JSON、签名、hash、联邦转发、sync cursor、audit replay 或 API response 前恢复完整 typed ID。
接收方验证签名、hash、backfill 或 replay 时，MUST 按完整 typed ID 比较，MUST NOT 用数据库 row id、
自增 id、表名推断或隐式转换替代 wire value。

`<kind>` 是 canonical bytes 的一部分。实现 MUST NOT 把 `ak:receipt:<id>` 改写成 `ak:event:<id>`，也 MUST NOT 因为字段名叫 `receipt_id` 就在验证时补前缀。字段名可以辅助 schema 校验，但不能替代 signed wire ID。

producer-allocated typed ID 继续使用 [RFC 9562](https://datatracker.ietf.org/doc/html/rfc9562) UUIDv7；`event_id`、以及 registry 中 `id_form=event_derived`（含 Realm ID）或 `id_form=suite_tagged_full_digest` 的对象 ID 不是 UUID，而使用固定 33-octet token。kind 的形态由 [`id-kind-registry.json`](../../artifacts/registry/id-kind-registry.json) 唯一决定，调用点不得自行选择，也不得把这些 token 放入 PostgreSQL `uuid` / `BYTEA(16)`。

### 4.0 suite-tagged 264-bit full-digest ID（normative）

`event_id` 是 Event 的完整密码学身份：首字节高 nibble 永久保留为零，低 nibble 是显式 digest-suite code，随后紧跟该 suite 产生的完整 32-octet digest。Event 相等、引用、去重与存储键语义均以这个完整 Event ID 为准；`proof.event_digest` 是可直接交叉验证的算法名 + digest wire 表示，不是第二套身份。registry 中 `id_form=suite_tagged_full_digest` 的 typed ID 使用相同 33-octet 布局；其首字节语义是受 v1 高 nibble 为零约束的 suite code，不因此承载 suite 之外的任何类别含义。

```text
输入：
  S = digest-suite-registry 显式登记的 uint4 wire_code（0x1..0xF）
  D = 按该 suite 对既有 Event digest preimage 计算的 32-octet digest

event_id_bytes[0]     = 0x00 | S          // 高 nibble MUST 为零
event_id_bytes[1..32] = D[0..31]       // 完整 32 octets，256 digest bits
event_id = "ak:event:" || base64url_no_pad(event_id_bytes)
```

SessionGrant 是 v1 的非 Event `suite_tagged_full_digest` kind：其 `session_grant_id_bytes` 使用同一 `S || D` 布局，但 `D` 来自 Account Authority closed immutable issuance preimage，而非 Event digest preimage；wire form 为 `ak:session_grant:<44-char-suite-tagged-full-digest-token>`。`identity_authority=issuer_record` 决定谁对 preimage 与 lifecycle 负责，`id_form` 只决定字节布局；实现不得因为 authority 不同而改写首字节。完整合同见 [`../identity/key-management.md` §6.1](../identity/key-management.md)。

`event_id_bytes` MUST 恰为 33 octets；无 padding Base64URL suffix MUST 恰为 44 characters，完整 typed ID MUST 恰为 53 characters。词法预检为 `^ak:event:[A-Za-z0-9_-]{44}$`，但 regex 不构成完整验证：receiver MUST decode、确认 33-octet 长度、canonical re-encode 并逐字比较，从而拒绝 padding 或其它非 canonical alias。33 octets 恰好编码为 44 个 Base64URL 字符，不存在 trailing unused bits。

suite code 由 [`digest-suite-registry.json`](../../artifacts/registry/digest-suite-registry.json) 固定：`0x1=sha256`、`0x2=blake3`、`0x3=cbor.sha256`（reserved，激活前非法）；低 nibble `0x0` 永久 invalid，`0x4..0xF` 未分配。v1 Event 与 `suite_tagged_full_digest` typed ID 只接受高 nibble为 `0x0` 的已登记 active suite code；`0x10..0xFF` 对 v1 Event ID 永久非法，对其它 suite-tagged typed ID 在本 wire contract 中同样非法。对 SessionGrant，这个首字节仍是受范围约束的 suite code；高 nibble 为零是保留位，不得解释为任何类别标记。code 未登记、未激活、digest 长度不等于 32，或不属于该 Realm historical/live basis 时 MUST fail closed。code 不得由数组位置、suite 名或 hash 名推导，退役后不得复用。

本次只改变 Event ID 编码，**不改变 event_digest preimage**：`D` 仍是 `canonical_digest(envelope_without_proofs_unsigned_actor_kind_event_id)`。实现不得在本迁移中加入 domain prefix、二次 hash、XOR folding 或另一套 canonicalization；这些改变必须注册新 suite。

producer 顺序固定为：完成除 `event_id` / `proofs` 外的字段；计算完整 `D`；派生并写入 `event_id`；最后签署携完整 `event_digest` 的 proof。receiver 在任何 lookup、去重、路由、幂等、授权或 projection 副作用前，MUST 严格解析 ID、先要求 `id.header >> 4 == 0`，再从 `id.header & 0x0F` 读取 suite、按历史 basis 校验 suite、重算完整 digest，并要求低 nibble `id.code == digest.suite.wire_code` 且全部 32 digest octets 相等。reserved nibble 非零使用 `schema_violation`；digest 不一致使用 `event_id_digest_mismatch`；未知或未激活 code 使用 `unsupported_digest_algorithm`；已知但不属于 Realm basis 使用 `schema_violation`。解析器不得只 mask 低 nibble 后接受高 nibble 非零的 canonical alias。

Event ID 保留底层 256-bit digest 的指定目标与碰撞安全强度；额外 header octet 承载固定为零的 reserved nibble 与 suite nibble，不增加同一 suite 的 hash 强度。canonical store、proof / receipt / Seal coverage、raw replay 与所有 Event 引用 MUST 使用完整 Event ID，且可从 ID 无损恢复 suite code 与全部 digest bytes。

派生对象 ID 的规则见 [`../models/common-fields.md`](../models/common-fields.md)；Realm token header 见 §4.1；`event_id` 的携带与重算义务见 §6。

### 4.1 264-bit Realm ID（normative）

所有 Realm ID 统一为 `ak:realm:` 加 44-character unpadded Base64URL token；解码后恰为 33 octets，
**布局与 Event ID 完全相同**：

```text
realm_header = (reserved_zero << 4) | digest_suite
realm_id_bytes[0]     = realm_header
realm_id_bytes[1..32] = full_digest[0..31]
realm_id = "ak:realm:" || base64url_no_pad(realm_id_bytes)
```

**高 nibble 永久保留并 MUST 为 `0x0`。** Realm 只有一种派生算法，该 nibble 不承载信息，
语义与 Event ID 的 reserved nibble 一致。任何非零高 nibble MUST NOT 产出，
收到 MUST 以 `realm_id_not_event_derived` fail closed。

低 nibble 是 digest-suite code。v1 Realm identity 的算法固定为 SHA-256，因此只有 `digest_suite=0x1`
合法；`0x0` 与 `0x2..0xF` 均为非法/保留。普通 Event 可以登记其它 suite，但这不会自动使其成为
Realm-eligible suite；v1 create Event 必须使用 suite wire code `0x01`，否则不能逐字节重类型为 Realm。

由于两侧 header 语义已经一致，`ak.realm.create` 的 33-octet Event token **逐字节即是**该 Realm 的
token，重类型只替换 `ak:event:` / `ak:realm:` 前缀，不改变任何一个字节。任何 UUID 形态、
reserved nibble 非零、Realm header 不是 `0x01`，或 digest 重算不一致，都 MUST fail closed。

> **不得用该 nibble 编码 Realm 类别。** Realm **是什么**由签名 create payload 的 `purpose` 表达；
> 新增 `purpose` 取值不得、也无法再新增 header 类别，实现 MUST NOT 从 `realm_id` 反推 `purpose`。
> 判定 Realm 类别的唯一权威是已验证的 genesis Event payload。

数据库实现 MAY 与 Event 一样为 Realm 分配仅本地可见的 surrogate `pk`，并让 Event、投影和 Realm
业务表通过 `realm_pk` 外键关联。该 `pk` 不是协议身份，MUST NOT 出现在 wire、canonical JSON、签名、
hash、同步 cursor、联邦消息或审计引用中。canonical Realm 表 MUST 同时保存并唯一约束完整 33-octet
身份（或可无损恢复它的完整 typed wire form）；任何 `realm_pk` 关联都 MUST 与协议记录携带的
`realm_id` 解析为同一身份。实现不得以本地 `pk` 替代首次接触重算、跨库导入、重放或冲突判断。

Realm 的高 nibble 固定为零，既不编码身份派生类别，也不编码 `direct_conversation`、organization、
managed Agent 等产品/profile 分类。后者继续由签名 genesis schema/profile 判定，不能占用 identity header。

本节的 conformance 入口是 `ak.vector.event_id.content_bound.v1`（机读 fixture 见 [`content-bound-event-id-fixture.json`](../../artifacts/fixtures/content-bound-event-id-fixture.json)）：它固定 SHA-256 / BLAKE3 bytes、canonical Base64URL、suite mismatch、unknown/reserved code、错误完整 digest、padding与长度负例。

`event_id` 不是 producer 自由分配的值，也不含可解析时间段。它携带 suite code 与完整 256-bit digest；`proof.event_digest`（≡ `canonical_digest(envelope_without_proofs_unsigned_actor_kind_event_id)`，§6）提供同一 digest 的算法名 wire 表示并受 proof 绑定。

`event_id` 作为必填字段出现在 wire 上；它是完整身份，且任何 receiver 都能从 canonical bytes 独立重算。`proof.event_digest` 与它的 digest 部分是有意的、可校验的冗余：可在昂贵的 DID / 密钥解析之前做内容完整性预检，并在跨实现 canonical JSON 分歧时直接定位到 canonicalization。

**receiver MUST 重算 `event_id` 并与携带值比对；比对通过之前 MUST NOT 将其用于任何有副作用的用途**——接受、去重命中、索引写入、路由确认、幂等成功、授权判断一律不行。不一致 MUST 返回 `event_id_digest_mismatch`，MUST NOT 退化为 `proof_invalid` 或 `schema_violation`。接收方 MAY 用未验证 ID 定位候选 bytes，但不得据此改变任何 accepted 状态。

若两个不同 canonical preimage 重算出相同 `event_id`，它们具有相同 suite 与完整 digest，属于底层 hash collision evidence。不能由先到顺序或字典序判定哪条“正确”；必须按 [`operations-sync.md` §12](../sync/operations-sync.md) 整组 quarantine。携带相同 ID 但重算 digest 不同只是 `event_id_digest_mismatch` 的伪造/损坏输入，不得拖入已接受 Event。

[`id-kind-registry.json`](../../artifacts/registry/id-kind-registry.json) 的 `id_form` 决定每个 kind 的构造：`producer_allocated` 使用 UUIDv7；`event_derived` 与 `suite_tagged_full_digest` 使用 §4.0 的 `uint8 suite code || 32-byte digest` token，前者从 Event token 重类型，后者按 kind-specific preimage 直接计算。Realm 属 `event_derived`，其 token 与创建 Event 的 token 逐字节相同。

特殊 ID/ref 形式（与 [`id-kind-registry.json` `special_forms[]`](../../artifacts/registry/id-kind-registry.json) 一一对应）：

- `ak:cursor:<base64url>` 是 opaque token，不是 typed UUID object ID。
- `ak:blob:sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` 是内容寻址 Blob ref；`ak:blob:019640ba-0000-7000-8000-000000000000` 是 Blob metadata ID。二者 MUST NOT 混用。
- `ak:seal:sha256:<digest>` 是内容寻址 Seal hash（active special form；见 `id-kind-registry.json`）。
- `ak:cell:<component>:<subject>` 是 canonical cell tuple 引用（active special form；`component` MUST 是从 cell-component registry 取得并原样嵌入的完整 `ak.component.<facet-path>.v<n>` family 标识符，`subject` 是 cell 的 subject key）。subject 内来自 canonical URI / DID 的 percent-encoded octet MUST 保持 `%HH` 形态，不得因嵌入 cell tuple 再次编码或解码。因此标准实例形如 `ak:cell:ak.component.strand.position.v1:<subject>`；`ak:cell:component.*`、`ak:cell:<裸 family>`、旧命名空间 family、截断/非十六进制 percent escape 或任何未完整携带 `ak.component.*.v<n>` 的形态 MUST 拒绝。
  - **Null subject（per-Realm / per-envelope 单例 cell，normative）**：registry 中 `cell_subject` 声明为 JSON `null` 的 cell family，其 canonical wire subject 段固定为字面 ASCII 四字符 `null`，即 `ak:cell:<component>:null`。选定字面 `null` 而非空串或省略末段，是因为 `ak:cell:<component>:` 的空末段无法与“末段被截断”区分，而截断形态本身必须拒绝。这类 cell 由 Event envelope 的 `realm_id` 定位（Realm-scoped 单例）；实现 MUST NOT 把 `realm_id`、Realm 角色分类（`collaboration` / `principal_control` / `managed_agent_principal_control` 等 [`../models/realm-and-space.md` §2.8.3](../models/realm-and-space.md) 的 prose 层术语）或任何 payload 派生值写进该 subject 段，也 MUST NOT 从 payload 重复字段派生第二个 cell key。任何偏离字面 `null` 的写法 MUST 拒绝（`schema_violation`）——subject 既进入 `state_root` leaf preimage、又是 leaf 的排序键（[`../authz/event-auth-state-resolution.md` §6.2.1](../authz/event-auth-state-resolution.md)），编码分歧会直接导致跨实现 `rejected_seal`。若某个 family 确实需要区分同一 Realm 内的多个实例，它 MUST 在 registry 中声明非 null 的 `cell_subject`，而不是把区分值塞进 null subject 段。
- `ak:mls:<profile>:<profile_id>`、`ak:pseudonym:<scope_id>:<random>` 等 profile-scoped form 必须由对应 profile 注册和校验。
- `ak:trust_domain:<scope>` 是部署 / 联邦信任域 ref，不是 typed UUID object ID；`<scope>` 的 profile 与匹配规则由 Realm / federation policy 声明。

自定义 profile 若新增 `ak:<kind>:` 前缀，MUST 在 profile registry 或扩展 registry 中声明 kind、wire form、存储边界和校验规则。未注册的 `ak:<kind>:` typed ID MUST 被视为未知 critical wire type，除非所在字段明确允许 opaque string。

### 4.1 Field Naming: `_id` / `_ref` / `_did`（normative）

Identifier 字段命名的权威规则见 [`common-fields.md` §2.1](../models/common-fields.md#21-identifier-字段命名约定normative)。本节只给出编码层摘要：字段后缀表达 wire value category，不表达授权、同步、retention 或 E2EE 级联语义。

| 用途 | 命名后缀 | 说明 |
| --- | --- | --- |
| 对象自身 ID（primary key） | `id` | canonical object 的主 ID，无下划线前缀。例：`id`。 |
| 单一具体 protocol object kind | `<role>_<kind>_id` | 例：`realm_id`、`parent_space_id`、`scope_circle_id`、`policy_id`。 |
| 协议责任主体（DID 作为主体 ID） | `<role>_id` | 例：`actor_id`、`principal_id`、`subject_id`。 |
| 因果 / finality / proof / schema-profile reference | `<noun>_ref` / `<noun>_refs` | 例：`prev_refs`、`seal_ref`、`schema_refs`、`policy_event_ref`。 |
| Blob / content-addressed / polymorphic reference | `<noun>_ref` / `<noun>_refs` | 例：`blob_ref`、`target_ref`、`from_ref`、`to_ref`。 |
| Service identity（wire value 为 DID） | `service_id` / `<role>_service_id` | 例：`service_id`、`recipient_service_id`、`source_service_id`、`verification_service_id`。 |
| 其它原始 DID ecosystem material | `<role>_did` | 例：`pairwise_did`、`old_did`、`new_did`、`operator_did`。 |

### 4.2 Canonical 确定性 tie-break（normative，单一真相源）

协议中多处需要在一组候选 Event 间机械选出唯一 winner。本节覆盖两类候选集，二者 **MUST 全部使用本节定义的单一规则**，不得各自规定键或方向：

- **并发候选集**：因果上互不可达的候选（如 relation `deterministic_winner`、message revision 的"最新可见 revision"、account status 同严格度并发收敛）；
- **逻辑 slot equivocation 候选集**：协议明确要求从同一个逻辑 slot 的互斥声明中选出唯一值的场景（如 `ordered_log` 的同一 `(cell, actor_id, issuer_seq)` 出现多条非逐字等价 entry，见 [`../authz/event-auth-state-resolution.md` §9.3.1](../authz/event-auth-state-resolution.md)）。这类候选**不要求互不可达**；producer 是否在 Event DAG 中人为加入因果边，MUST NOT 改变 winner，也不得把 slot 复用洗成合法的下一次写入。

两类候选集的规则相同：

- **最终 tie-break 键固定为 `event_digest`**：候选各自产生 Event 的 canonical `event_digest`（≡ `canonical_digest(envelope_without_proofs_unsigned_actor_kind_event_id)`，§6）。digest preimage MUST 逐字使用 §2 / §6 的权威集合——从 envelope 移除 `proofs`、`unsigned`、`actor_kind` 与 `event_id` 后再 canonicalize；签名 `scope_ref` 不得移除。它是签名覆盖的内容指纹，对所有 verifier 唯一确定。
- **方向固定为 bytewise 最大（lexicographically-greatest）**：winner = 候选集中 `event_digest` 最大者。比较对象 MUST 是**解码后的 digest octets**，不是 typed wire string：wire 形态 `<canonical_suite_id>:<lowercase_hex>`（§3.1）若整串按 UTF-8 比较，suite 名会先于内容决定 winner。规则固定为——先按 §3.2 确认候选 suite 对该 Event basis 合法，再把 hex 解码为 octets，以 unsigned lexicographic order 比较；长度不同且短者是长者前缀时短者较小。**仅当** octets 完全相同而 suite 不同时，才以 canonical suite id 的 unsigned UTF-8 bytewise 顺序作第二键，使全序完备。选最大是 LWW-register 的惯例方向，跨全协议统一。
- **禁止的 tie-break 键**：winner 选择 MUST NOT 使用 `created_at` / HLC / `actor_id` / `actor_seq` / `event_id` / 本地接收顺序 / 数据库 ID / 服务端插入顺序中的任何一个。`event_id` 虽无损携带 suite code 与完整 digest，仍不得替代本节唯一的 decoded-`event_digest` comparator：直接比较 typed ID 会把格式/registry code 混入 domain 规则，并使未来 ID format 升级改变 winner 实现。
- **复合排序的 domain 语义键**：某些 domain 在 tie-break 之前**先**按一个或多个有 domain 语义的有序键排序（如 account status 先按严格度、再按 `effective_at`）。这类 domain-semantic 主排序键是各 domain 的合法设计；但当主排序键全部相等仍并发时，**最终的并发消歧 MUST 落到本节的 bytewise-greatest `event_digest`**，不得用 `event_id` 或墙钟量收尾。
- **collision fail closed**：两个候选的 canonical digest preimage bytes 不同却得到完全相同的 typed digest（同 suite、同 octets）时 MUST fail closed，MUST NOT 回退到任何禁止键或实现私有 ID。反之，preimage bytes 逐字相同而仅 `proofs`、`unsigned` 或 `actor_kind` 不同的，是同一 producer-signed Event 内容，分别按 proof profile 与 actor-kind 投影验证处理，MUST NOT 误报 collision。

引用本规则的 domain：[`models/relation.md` §6](../models/relation.md)、[`models/strand-and-message.md` §9.5.1](../models/strand-and-message.md)、[`identity/account-lifecycle.md` §3](../identity/account-lifecycle.md)、[`authz/event-auth-state-resolution.md` §9.3.1](../authz/event-auth-state-resolution.md)。

**该规则 MUST NOT 删除或重写 canonical event log**：全部候选（并发的与 equivocation 的）都保留在日志与审计视图中，loser 只是不被选中。但本规则的作用域**不限于**投影/展示——`event-auth-state-resolution.md` §9.3.1 的 `ordered_log` slot winner 决定该 cell 的 joined value。该 value 进入哪一族 Seal 承诺**由 cell 所属 plane 决定，不由本节决定**：control cell 进入治理 `state_root`（[`../authz/event-auth-state-resolution.md` §6.2.1](../authz/event-auth-state-resolution.md)），data plane cell MUST NOT 进入治理 `state_root`，其承诺走同文 §6.4 的 `data_view_root`。domain 各自声明本规则的输出是仅用于展示投影，还是进入 canonical state；未声明进入 canonical state 的 domain MUST NOT 用本规则的结果做授权。

### 4.3 本节 tie-break 规则的 conformance 入口

`vector_id`: `ak.vector.encoding.canonical_event_tie_break.v1`（机读 fixture 见
[`encoding-fixture.json`](../../artifacts/fixtures/encoding-fixture.json)，向量说明见
[`conformance-vectors.md` 23.1](./conformance-vectors.md)）。该向量是 4.2 唯一 tie-break 键的
机器测试入口：它覆盖并发候选集与逻辑 slot equivocation 候选集两类输入、decoded digest octets 比较、
跨 suite 第二键、禁止键、collision fail-closed，以及 proofs / reducer stamps 差异不误报 collision。
`ordered_log` 的 join 向量只验证该通用键在 issuer slot 中的集成，MUST NOT 让本节的唯一机器测试
反向依赖某个 lattice。

## 5. Event Batch Receipt Hash

```json
{
  "schema": "ak.schema.event_batch_receipt.v1",
  "receipt_id": "ak:receipt:01964186-0000-7000-8000-000000000000",
  "issuer": "did:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw:alice.example",
  "scope": {
    "actor_id": "did:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw:alice.example"
  },
  "frontier": {
    "actor_seq": 1,
    "event_digest": "sha256:..."
  },
  "events": ["sha256:..."],
  "created_at": "2026-04-26T00:00:00Z"
}
```

`events[]` 是 set-bound receipt 的 canonical set projection。令 `event_sort_key(x) = UTF8(canonical_json(x))`；签发方 MUST 先按该 byte string 升序排列并删除完全相同的 key，再把结果写回 wire `events[]`。接收方 MUST 在验签前确认相邻 `event_sort_key` 严格递增；否则以 `schema_violation` 拒绝，不得静默归一化一个已签 wire object。

`receipt_digest = sha256(canonical_json(receipt_without_proofs))`。这里的 `receipt_without_proofs.events` MUST 已是上述规范形态。`issuer`、`scope`、`frontier`、`events`、`schema` 必须进入 digest，防止 receipt 被跨 actor、跨 Realm 或跨前沿重放。Event Batch Receipt proof 的 detached bytes MUST 是 canonical binding object `{context:"ak.receipt-proof-v1", payload_digest:receipt_digest, issuer, verification_method, created_at, domain?, audience?}`；`context` 是固定 signing-context domain tag，不在 receipt wire body 中单独携带。

## 6. Signature

默认 proof（wire `proof` 对象；`actor_id` 与 `created_at` 不在 wire `proof` 对象内——`actor_id` 取自被签 Event envelope 的 `actor_id` 字段，`created_at` 取自 `proof.created_at`，二者均进入下方签名 transcript binding object）:

```json
{
  "kind": "detached_jws",
  "verification_method": "did:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw:alice.example#device-1",
  "created_at": "2026-04-26T00:00:00Z",
  "event_digest": "sha256:...",
  "jws": "..."
}
```

Proof MUST bind（下列为绑定字段集合；canonical binding object 的实际字节顺序由 §2 canonical JSON 的 JCS key 排序决定，下方 JSON 示例与本清单的列举顺序仅为可读性，不代表签名字节顺序）:

- `context = "ak.event-proof-v1"`：固定 signing-context domain tag；不从 Event envelope 读取，verifier 构造 binding object 时 MUST 写入该常量。
- `event_digest = canonical_digest(envelope_without_proofs_unsigned_actor_kind_event_id)`
- `actor_id`
- `verification_method`
- `created_at`
- `domain` / `audience` where applicable

Durable Realm Event 是可由多个合规 Realm host 保存和复验的原始事实，因此其 proof 不能绑定某一台 authoring Principal Server 的 service DID。会经 federation、backfill、snapshot recovery 或多 host replay 的 Event，其 `proof.domain` / `proof.audience` MUST 省略，或绑定一个由相关 profile 明确定义且对所有合法 receiver 恒定的 Realm 语义值；MUST NOT 写入当前提交端、来源端或目标端 Principal Server DID。HTTP 目的服务、trust domain、delivery binding 与 replay 隔离由外层 RFC 9421 service signature 和 federation request binding 承担，不得通过改写原 Event proof 实现。接收方 MUST 对原 Event bytes 验签，MUST NOT 为本地 service DID 重签或补写 `domain` / `audience`。

`detached_jws` 的 payload segment MUST be empty in compact serialization, but the detached bytes being signed MUST be the canonical proof binding object:

```json
{
  "context": "ak.event-proof-v1",
  "event_digest": "sha256:<canonical event hash>",
  "actor_id": "<event.actor_id>",
  "verification_method": "<proof.verification_method>",
  "created_at": "<proof.created_at>",
  "domain": "<proof.domain if present>",
  "audience": "<proof.audience if present>"
}
```

Verifier 顺序固定为：先从 Event 中移除 `proofs`、`unsigned`、`actor_kind` 与 `event_id`，保留签名 `scope_ref` 以及完整 `prev_refs` / `refs` / `causal_refs`，按 §2 canonicalize 并计算 `event_digest`；再与 `proof.event_digest` constant-time 比对；随后按 §4.0 从该 digest 的 suite wire code 与全部 32 digest octets 重算 `event_id` 并与携带值比对（不一致 `event_id_digest_mismatch`）；最后按上表字段构造 canonical binding object（含固定 `context`）并验证 detached JWS。实现 MUST NOT 直接签 HTTP envelope、transport metadata 或只签 `payload` 字段。

**preimage 排除清单分两类，理由不同，MUST NOT 混为一谈**：

- `proofs` / `unsigned` / `actor_kind`——**签名后附加或由他方投影**的字段，本来就不属于作者签署的内容；
- `event_id`——**由 digest 本身决定**（§4.0），排除是为了让一次前向派生良定义；若不排除，digest 的 preimage 会包含 digest 自身的函数，定义即循环。

把"被排除"读成"不重要"是错的：`event_id` 的完整性由 §4.0 的重算比对保证，并在完整 digest 已知后一次前向派生。`prev_refs` 中完整 Event ID、语义 refs、事前 `seal_ref` / `seal_basis`、`created_at` 与 payload 均未排除，必须逐字进入 preimage；事后覆盖本 Event 的 Seal / receipt 只能单向承诺该 Event identity，不得反向加入原 Event。

非 Event 的 detached proof（使用 `payload_digest` 的 receipt、capability grant、snapshot witness、handle claim 等）MUST 同样在 canonical proof binding object 内包含对象族固定 `context` 常量。每个对象族 MUST 在 [`proof-context-registry.json`](../../artifacts/registry/proof-context-registry.json) 登记唯一 context、binding fields、规范定义点与 schema；schema description 只可作镜像注解，不是常量真相源。MUST NOT 复用其它对象族（尤其 `ak.event-proof-v1`）的 context，也 MUST NOT 省略 context 后只签 `{payload_digest, verification_method, created_at, ...}`。用错误对象族 context 生成的签名即使密码学验签通过也 MUST 拒绝。

**Realm 与 scope 绑定（normative）**：`event_digest = canonical_digest(envelope_without_proofs_unsigned_actor_kind_event_id)` 同时覆盖 `realm_id` 与 `scope_ref`；改写二者都会使 proof 失败。实现 MUST 在验证 proof 后确认 `scope_ref.realm_id == realm_id`、处理上下文 Realm 相等，并由 payload/accepted references 重算 scope；不得仅凭签名有效就跨 Realm/Circle 接受。

**唯一例外是 `ak.realm.create`**：它 MUST 省略 `realm_id` 并使用不含 `realm_id` 的 `{"kind":"realm_genesis"}` scope，receiver 按 §4.0 从 `event_id` 派生 `realm_id`。理由是循环性——`realm_id` 若留在 preimage 内，它既是 digest 的输入又是 digest 的函数，无不动点可解。完整裁决见 [`../models/realm-and-space.md` §2.5.0](../models/realm-and-space.md)。该例外只作用于 genesis 一条 Event；其后该 Realm 的每条 Event 都照常携带并绑定 `realm_id`。

#### 6.0.1 原像内禁止承诺 Event 标识（normative）

上面 `realm_id` 的循环论证不限于「Event 自己派生出来的 ID」。形态 B 生效后，`event_id` 与
`event_digest` 互为函数，因此**任何进入 preimage 的字段**（`payload`、`refs`、`prev_refs`、
`scope_ref`、`preconditions` 等——即除 `proofs` / `unsigned` / `actor_kind` / `event_id` 之外
的全部 envelope 字段）**原则上 MUST NOT 承诺任何 Event 标识**。按被承诺对象在本 Event 构造时
是否已经成型，该禁令分三类，三类的可豁免性**不同**，MUST NOT 混为一谈：

- **A 类（自指）**：承诺**本 Event 自己**的 `event_id`、`event_digest`，或由二者 `retype` 得到
  的任何标识（`realm_id`、object id 等）；
- **B 类（同 unit 兄弟）**：承诺**同一原子 unit / 同一 ordered submit batch 内、尚未成型的兄弟
  Event** 的 `event_id`、信封 `event_digest` 或其 `retype` 结果；
- **C 类（跨提交前向声明）**：承诺**另一次提交中、内容已在本地冻结**的后续 Event 的 `event_id`
  或其 `retype` 结果。

**A 类与 B 类永不可豁免。**违反任一条即产生无解原像（两侧都是密码学哈希，不存在可迭代的不动
点），该 unit 无论实现如何排序都不可能构造出通过 §4.0 重算比对的取值，运行期表现为
`event_id_digest_mismatch`。下面的具名例外登记表 **MUST NOT** 接受 A 类或 B 类形状；登记表里出现
该形状即是登记表本身有缺陷，机器门禁 MUST 失败，MUST NOT 被读作已裁决的豁免。

需要 A/B 类那种承诺时，只有两条合法承载：

1. **对方的 payload digest**——payload 先于两条信封成型，依赖方向因此单向。这是同一 unit 内
   互相承诺的标准写法，见 [`../identity/key-management.md` §5.0.3](../identity/key-management.md)
   的 `replacement_authorize_payload_digest`；
2. **preimage 之外的结构**——`proofs`、receipt、attestation 等在两条 Event 都成型之后由签发方
   计算的对象，可以自由承诺 `event_id` 与信封 digest（`proof.event_digest` 即如此）。

**已成型的历史 Event 不受本条约束**：`prev_refs`、`refs` 与 payload 引用**已 accepted** 的
Event id/digest 始终合法——它们的取值在本 Event 构造前已经固定，不参与本 Event 的求解。

**C 类可构造，但只有具名登记后才被允许（normative）**：作者在提交本 Event 之前已经在本地冻结
了目标 Event 的完整 canonical bytes，因此能先算出目标的 `event_id` 再把它写进本 Event 的
preimage。依赖方向仍然单向——目标 Event 的原像不含本 Event 的任何标识——所以没有 A/B 类的不动点
问题。它换来的代价是把「目标一定会以逐字相同的 bytes 被提交」变成一个**只能由 admission 补偿的
假设**，因此 MUST NOT 由实现自行推断。每一条 C 类例外 MUST 同时满足：

1. 出现在下面的封闭清单表中，并携带其 `exemption_id`；
2. 在 [`preimage-identity-exemption-registry.json`](../../artifacts/registry/preimage-identity-exemption-registry.json)
   登记一行 active 记录，钉住承诺方向与单向理由、目标冻结时点、准入补偿校验、目标始终不出现时
   的语义，以及覆盖它的 conformance vector；
3. 该字段的 schema `description` 如实写明它承诺的是哪一条**尚未提交**的 Event，并引用本节。

三者缺一即门禁失败。正文清单与 registry 是**双向绑定**：清单表中的每个 `exemption_id` 必须在
registry 有 active 行，registry 的每一条 active 行也必须出现在清单表中。

**封闭例外清单**：

| `exemption_id` | 类别 | 主体 | 承诺方向 |
| --- | --- | --- | --- |
| `ak.exemption.preimage_identity.realm_genesis.v1` | 省略（不构成承诺） | `ak.realm.create` 的 `envelope.realm_id`、`envelope.scope_ref` 与 `payload.object.id` | 不承诺；三者一律省略，receiver 按 §4.0 从 `event_id` 前向派生 |
| `ak.exemption.preimage_identity.agent_provision_principal_control_realm_id.v1` | C 类前向声明 | `ak.agent.provision` payload 的 `principal_control_realm_id` | 单向：provision 承诺**另一次提交**的 managed Agent PCR genesis 的 `retype(event_id)`；该 genesis 的原像不含 provision 的任何标识 |

第一行就是上面 `ak.realm.create` 的 `realm_genesis` 例外，形态是**省略**而不是承诺，因此不受 C 类
补偿要求约束；它进入登记表只是为了让「本节的例外集合」有唯一机器可读来源。第二行的完整时序、
准入反查与唯一性约束见 [`../identity/key-management.md` §3.6.3](../identity/key-management.md)。

conformance 入口沿用 `ak.vector.event_id.content_bound.v1`：每个跨 Event 原子 unit MUST 同时提供按单向顺序可派生的
正例，与旧互引形状必须被 `event_id_digest_mismatch` 拒绝的负例；每条 C 类例外 MUST 另有一个
**可构造性证明**向量，展示按其声明顺序真的能推导出该值而不产生 `event_id_digest_mismatch`。

机器门禁是 `tools/lint_artifacts.py` 的 `preimage_event_identity`。它**不再靠读措辞决定放行**，而是
查登记表：判定范围是 `event_id` / `*_event_id` / `*_event_ref` / `*_event_digest` 名族，外加
description 自称由 Event 标识派生（`retype(...)`、event-derived 等派生语）的字段；范围内字段的
description 若声明指向 enclosing Event 或同 unit / 同 batch 的兄弟 Event，**无条件**失败，
若声明指向另一次提交中尚未成型的 Event，则必须在登记表中有 active 行，否则失败。门禁同时做反向
自检：登记行指向的 schema / 字段必须存在、其 description 必须仍如实声明该前向承诺并引用本节、
`conformance_vector_ids` 必须都是 active 向量、`exemption_id` 必须同时出现在上面的清单表中。
用含糊措辞让字段落出判定范围等同于绕过本节。

### 6.1 Signature Suite registered set

签名算法的 canonical 机器来源是 [`signature-alg-registry.json`](../../artifacts/registry/signature-alg-registry.json)(与 §3.2 Hash registered set 对称)，下表是其规范阅读视图。字段命名按对象所有权确定，而不是把外部标准缩写扩散到 Arkret：JWS protected header / JWK 等 JOSE 对象 MUST 保留标准成员 `alg`，其值取 active row 的 `jose_algorithm`；Arkret 自有 raw-signature 对象 MUST 使用完整字段名 `signature_algorithm`，其值取 active row 的 `raw_signature_algorithm`；RFC 9421 `Signature-Input` 的标准 `alg` parameter 必须取 `http_message_signature_algorithm`。三种映射属于不同命名空间，不得相互猜测或替代。schema enum 均须在版本发布时生成并冻结。Arkret 自有对象不得使用 `alg` 作为自定义字段，JOSE / RFC 9421 标准对象也不得把标准成员改名。

Arkret 的 `detached_jws` proof wrapper **不得重复携带算法字段**。算法唯一来源是 compact JWS 内已受签名保护的 protected header `alg`；verifier 解码 protected header 后按 `jose_algorithm` 和已解析 key type 选择 verifier。这样不存在外层明文算法与内层受保护算法不一致时“相信哪一个”的分支。

对称地，**非-MLS 应用层公钥封装**（key-backup `recovery_public_key` envelope、to-device `ak.secret.send`、member-application 与 file-transfer key envelope）的 KEM/KDF/AEAD 算法 agility 由 [`hpke-suite-registry.json`](../../artifacts/registry/hpke-suite-registry.json)（HPKE，RFC 9180）承载，与签名、digest、MLS-ciphersuite 并列为第四个算法 agility 面；其 `hpke_suite` / envelope `scheme` 选择字段的 enum MUST 在对应 schema 版本发布时由 registry active rows 生成并冻结，未被该 schema 版本接受的 suite MUST fail closed（`unsupported_hpke_suite`）。MLS 群组消息的 HPKE 内核仍由 [`mls-ciphersuite-registry.json`](../../artifacts/registry/mls-ciphersuite-registry.json) 承载，不在该 registry 范围内。四个算法 registry 的 activation / schema bump 纪律统一见 [`schema-registry.md` §6.1(b.1)](./schema-registry.md)。

`canonical_id` 是 registry 内用于指代算法 suite 的稳定标识；`jose_algorithm` 是 JOSE `alg` 的标准值；`raw_signature_algorithm` 是 Arkret raw signature 的值（不支持 raw 编码时为 `null`）；`http_message_signature_algorithm` 是 RFC 9421 HTTP Signature Algorithms registry 的值（未注册时为 `null`）。实现不得从 `canonical_id` 猜测任一 wire 值，必须按 carrier 读取相应映射。特别是 RFC 9421 的注册值是小写 `ed25519` / `ecdsa-p256-sha256`，不是 JOSE 的 `Ed25519` / `ES256`。

| Algo（`canonical_id`） | `jose_algorithm` | `raw_signature_algorithm` | `http_message_signature_algorithm` | 允许的 `proof_kinds` | v1 角色 | 抗量子 / future-ready 评估 |
| --- | --- | --- | --- | --- | --- | --- |
| `Ed25519` | `Ed25519`（JWS, crv=Ed25519） | `Ed25519` | `ed25519` | `detached_jws`, `raw_detached_signature` | **v1 default-MUST**；所有 receiver MUST 支持。Event proof、receipt proof、device possession proof 等核心签名默认使用。 | 不抗量子(Shor 可破)；通过 `ak.profile.signature.pqc.v1` 迁移到后量子 suite。 |
| `ECDSA-P256-SHA256` | `ES256`（JWS, P-256 + SHA-256） | `null` | `ecdsa-p256-sha256` | `detached_jws` | v1 optional；声明 `ak.profile.signature.ecdsa_p256.v1` 的实现 MUST 支持。用于需要与 WebAuthn / FIDO2 / 既有 PKI 互通的部署。 | 不抗量子(Shor 可破)；选择仅出于生态互通。 |
| `ML-DSA-65` | `ML-DSA-65`（RFC 9964；JWK `kty=AKP`、`alg=ML-DSA-65`、`pub` 必填） | `ML-DSA-65` | `null` | `detached_jws`, `raw_detached_signature` | v1 profile-gated；声明 `ak.profile.signature.pqc.v1` 的实现 MUST 支持。JWK 私钥只允许 RFC 9964 的 32-byte seed `priv`，公共 JWK 不得含 `priv`。 | 抗量子（NIST FIPS 204）；JOSE / COSE 映射以 RFC 9964 为准。 |

实现 MUST:

- 默认按 `Ed25519` 验证 event / receipt proof；JOSE protected header 的 `alg` 或 Arkret raw proof 的 `signature_algorithm` 未命中对应 registry mapping 时，critical proof（event_digest binding、device authorization、recovery）MUST fail closed (`unsupported_signature_alg`)；非 critical metadata signature MAY 记录为 unknown 并 preserve raw bytes。
- 在 `server/describe.crypto` 暴露支持的签名 algo 集合(与 hash algo 集合并列),client 据此选择写入算法。
- MUST NOT "算法升级"已签名的 canonical bytes:一旦 proof 用某 `alg` 发布，verify 路径永远按该 algo 重验；新算法走新 proof，不重写历史签名字节。

**后量子 / hybrid 前瞻（reserved）**：`signature-alg-registry.json` 以 `Ed25519+ML-DSA-65` reserved row 钉定双独立 proof entry、两分量同 payload/purpose 且全部必验的路线。它复用本节“不重写历史签名字节、新算法走新 proof”原则；缺失或剥离任一分量不得显示为 hybrid verified。该 row 在 activation requirements、反 stripping 向量和新 proof contract release 完成前不是 wire alg，receiver MUST `unsupported_signature_alg` fail closed。

## 7. HLC

> **使用边界（normative）**：HLC 在 v1 是 **advisory** 字段。它 MUST NOT 进入授权决策、Lattice 收敛、Control Move precondition 比较、或 Seal finality 判断；这些都由 CBA basis、Control Move `preconditions[]`、Seal coverage 与 Lattice `join` 决定。HLC 在 v1 只有两个规范用途，两者都以**因果不可比**为前提：
>
> 1. **timeline 派生层**——当两个事件在 `prev_refs` / `refs` 形成的因果图中互不可达时，HLC 作为 `(unix_ms, logical, node_id_hash)` 字典序 tie-breaker 使展示顺序确定。
> 2. **actor-private 状态的并发 tie-break**——同一 principal 的多设备 read cursor（[`discovery/read-receipts.md` §6.5](../discovery/read-receipts.md)），以及客户端在 Account Data compare-and-set 循环中对解密明文执行的领域合并规则（[`models/account-data.md` §5](../models/account-data.md)），在两个候选值**因果不可比**时 MAY 用 HLC 选出确定性 winner。这些状态只在 holder 自己的设备之间收敛，不进入共享 Realm 状态、CBA basis 或 Lattice join；因果可比时 MUST 取因果支配者，MUST NOT 用 HLC 反转。服务端不参与该 tie-break，它只比较 `expected_revision`。
>
> 即便 HLC 进入 canonical event bytes 与 proof `event_digest`，实现 MUST NOT 把 HLC 数值当作可信时间戳，也 MUST NOT 据其反转因果或在共享协议状态中选 winner。详见 [`authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) 与 [`sync/operations-sync.md`](../sync/operations-sync.md)。

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
- 用户客户端的 `node_id_hash` MUST 从 Realm-scoped 或 deployment-scoped 的本地 node secret 派生，例如 `SHA256("arkret-hlc-v1" || realm_id || device_id || local_node_secret)[0:8]`。MUST NOT 直接使用 principal DID、公开 handle、长期 device id 或跨 Realm 稳定标识作为 hash 输入。
- 服务 DID 产生的公开服务事件 MAY 使用 service-scoped node id，但服务若代表用户或 minimal-metadata Realm 转发/生成事件，MUST 使用 Realm-scoped pseudonymous node id，避免跨 Realm 关联。

排序按 `(unix_ms, logical, node_id_hash)` 字典序。

溢出规则：

- 生产者若在同一 `unix_ms` 内需要把 `logical_hex` 从 `ffff` 再递增，MUST NOT 回绕到 `0000`，也 MUST NOT 复用任何已发出的 HLC tuple。
- 遇到该情况时，生产者 MUST 采取以下两种行为之一：
  - 等待直到本地可生成更大的 `unix_ms_hex`，然后以 `logical_hex=0000` 生成新 HLC。
  - 在生成 canonical bytes 之前以本地临时错误终止该次写入，例如 `hlc_logical_overflow`，由调用方稍后重试。
- 生产者在等待或重试期间 MUST 保留原有 `prev_refs`、`refs[role=authorized_by]` 和 `actor_seq` 约束，MUST NOT 仅为了逃避 overflow 而伪造更大的 wall clock skew。
- 消费者若观察到同一 producer 出现 `unix_ms` 不变、`logical_hex` 从 `ffff` 回绕到更小值且没有更大 `unix_ms`，MUST 将其视为无效 HLC：在 submit / command 入口发现时 MUST reject 为 `schema_violation`；在同步、backfill 或已接收历史复验中发现时 MUST quarantine 该 producer 的冲突分支并停止推进其 accepted frontier。两条路径均 MUST NOT 把该 tuple 当作正常排序值接受。

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

- 用正则 `^[0-9a-f]{12}-[0-9a-f]{4}-[0-9a-f]{8}$` 验证 HLC 格式。HLC **纯格式违例**（不匹配该正则、段长 / 字符集 / 大小写不合、`unix_ms_hex > ffffffffffff` 等单纯的 well-formedness 失败）MUST 返回 `schema_violation`（与 [`conformance-vectors.md` §1.10.1](./conformance-vectors.md) 钉定的单值一致）。格式合法但发生 §7 语义回绕 / tuple 复用时，submit 路径同样返回 `schema_violation`，同步 / backfill 路径则 quarantine；不得选择其它错误码或 soft-fail 后继续该分支。
- 按本节的两层 drift 模型验证物理时间：超 `hard_future_skew_ms` MUST reject / quarantine；超 `expected_future_skew_ms` SHOULD soft-fail / quarantine。这两个阈值的默认数值以规模上限登记表 [`scalability-constraints.md`](./scalability-constraints.md) §2 为单一真相源（本节不重复字面值，避免漂移）。本路径校验的是 envelope freshness / DoS guard；通过 drift 校验的 **HLC 值本身**仍不得进入授权、Lattice winner、Control Move precondition 或 Seal finality，只可用于本节开头列出的两个因果不可比 tie-break。`hard_future_skew_ms` 作为协议级常量还被 Seal 与授权文档复用于各自基于 verifier 本地时间的上界校验；这种常量复用不把 HLC 变成那些路径的语义输入。
- profile MAY 通过 `state_event_expected_future_skew_ms` 对 state event（capability / membership / policy / service binding / Realm upgrade / MLS commit 等）施加更严窗口；未声明时按 `expected_future_skew_ms` 处理。
- 拒绝 `unix_ms_hex > ffffffffffff` 的 HLC 值（物理时间溢出，需未来扩展 HLC profile 才可使用）。
- 维护本地单调性；本地时钟落后远端时推进到远端时间，超前时限制推进速率。

### 7.3 Timeline 排序与 winner 选择

客户端 timeline / backfill / 展示层默认事件排序：

```text
causal_depth ASC, hlc ASC, actor_id ASC, actor_seq ASC, event_id ASC
```

`hlc` 缺省时在该排序键上使用 **absent-last**：缺省值大于任何 schema-valid HLC；两个事件都缺省时继续比较 `actor_id`。实现 MUST NOT 用空字符串、零 HLC、本地接收时间或 `created_at` 代填缺省值。

协议状态 MUST NOT 使用 timeline 排序选择 winner。DataEvent / Control Move 的 CBA basis、Seal coverage 与 Lattice join 决定当前 cell value；并发不可合并时返回 structured bottom。Timeline 展示顺序与 cell value 是两种不同 projection：前者排历史，后者由 Lattice 计算。实现 MUST 在 profile 中明确使用哪一个，MUST NOT 把 timeline 中最后出现的 Event 直接当作状态 value。

客户端只有在已知 causal closure 足以判断两个 Event 在 `prev_refs`、`refs[role="after"]`、`causal_refs` 与 payload 物化的 reply/reference edge 图中互不可达时，才可把 HLC 用作最终 timeline tie-breaker。若 backfill、dependency fetch 或 snapshot-assisted verification 尚未补齐到可判断互不可达，客户端 MUST 把排序标记为 provisional（例如 pending/backfilling），或使用 `created_at` / 本地接收序作为临时 UI 占位；MUST NOT 把 HLC 排序结果写入持久 projection、审计导出或任何声称“最终顺序”的视图。

`causal_depth` 只用于 timeline / batch 展示排序。它的 canonical projection 定义为：在已知 causal closure 内，沿 `prev_refs ∪ refs[role="after"] ∪ causal_refs ∪ payload 物化的 reply/reference edge` 计算最长路径长度；genesis depth 为 0。若任一参与排序的 Event 缺失这些边上的 predecessor，接收方 MUST 把该 Event 的 depth 标记为 provisional，不得声称最终 timeline 顺序，也不得把该 depth 输入协议状态收敛、授权或 winner 选择。

## 8. Cursor

> **Scope（normative）**：本节只定义 cursor 的**内部 canonical 结构、字段 schema、编码、验证规则与 TTL 硬上限数值**;cursor 在 HTTP/JSON binding 上的使用契约(出现位置、分页方向、purpose 语义)见 [`api-conventions.md` §7](../sync/api-conventions.md)。

Cursor 是不透明字符串：

```text
ak:cursor:<base64url>
```

### 8.1 客户端契约

- 客户端 MUST 把 cursor 当作不透明字符串。
- 客户端 MUST NOT 解码、解析或修改 cursor 内容。
- 客户端 MUST 存储 binding 返回的最新 stream `cursor` 用于恢复。
- 客户端 MUST 在下一次同语义用途的请求中按原样使用 cursor；具体出现位置由对应 transport / API binding 定义。

### 8.2 服务端 canonical 内部结构

服务端在 base64url 编码前将 cursor 内部结构编码为 canonical JSON（按 §2 规则）。**v1 core cursor 内部结构 MUST 遵循 [`cursor.schema.json`](../../artifacts/schemas/cursor.schema.json)**：body 固定为 `{v, purpose, issued_at, expires_at, h}`；两个时间字段都使用 Arkret absolute instant 的固定 `.sssZ` 形式，`h` 是不可猜测的 server-side opaque handle（见 §8.3.1）。core schema `additionalProperties:false` 且 `required` 含上述全部字段；服务端 MUST NOT 在 cursor body 中内联 stream positions、barrier target、principal binding 或完整性证明字段。

cursor 是 v1 中**唯一**的不透明 token 类型，统一承担增量同步、列表分页和写后读屏障用途。`purpose` 字段区分两个语义：`stream`（增量同步与列表分页位置承诺）与 `barrier`（读己之所写屏障）。每个 transport / API binding MUST 在自己的绑定文档中声明哪些 wire 位置接受哪一种 `purpose`。

Stream cursor body 示例：

```json
{
  "v": "1",
  "purpose": "stream",
  "t": "2026-04-26T00:00:00Z",
  "x": 1714080000000,
  "h": "abcdefghijklmnopqrstuv"
}
```

Barrier cursor body 示例：

```json
{
  "v": "1",
  "purpose": "barrier",
  "t": "2026-04-26T00:00:00Z",
  "x": 1714080000000,
  "h": "0123456789abcdefghijkl"
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `v` | string | 是 | cursor 版本，v1 固定 `"1"` |
| `purpose` | enum(`stream`,`barrier`) | 是 | 用途鉴别 |
| `t` | timestamp | 是 | 生成时间戳（RFC 3339 UTC,MUST 以 `Z` 结尾）。**canonical 精度固定为秒级、不带小数部分**（形如 `2099-12-30T23:59:59Z`，与 [`encoding-fixture.json`](../../artifacts/fixtures/encoding-fixture.json) 向量 `ak.vector.encoding.cursor_opaque.core.v1` 的 `t` 真源一致）：服务端生成 cursor 时 MUST NOT 写入毫秒小数（`.000Z` 等），以消除同一逻辑时刻产生两种 canonical 编码的二义；接收方对带毫秒小数的 `t` MUST reject `invalid_param`。 |
| `x` | integer | 是 | 过期时间戳（Unix ms） |
| `h` | string | 是 | 服务端 opaque handle（≥ 128 bit 熵），见 §8.3.1。stream positions 或 barrier target 均由 `h` 在服务端绑定表中解析，MUST NOT 内联进 cursor body。 |

服务端 MAY 添加其它 `_` 开头的私有字段（如 `_compression`）用于本地优化；这些字段必须先于 base64url 编码进入 canonical bytes。`_mac` 与 `_sig` 是保留字段，MUST NOT 出现在 v1 cursor body 中。

**handle-bound 但不在 wire body 的完整性绑定字段（normative）**：下列字段是 cursor 完整性校验（§8.3.1）的核心绑定项，但 **不作为 cursor body wire 字段出现**——它们由 `h` handle 在服务端绑定表中承载。这些字段 MUST NOT 出现在上方 §8.2 定义的 cursor body wire 字段集合中:

| 绑定字段 | 承载位置 | 说明 |
|----------|----------|------|
| `principal_id` | `h` handle 绑定表 | cursor 所属 principal，跨 principal 命中 MUST `cursor_integrity_invalid` |
| `device_id` | `h` handle 绑定表 | cursor 绑定的 device |
| `service_id` | `h` handle 绑定表 | issuing service 标识 |
| `filter_digest` | `h` handle 绑定表 | 订阅 / 查询 filter 的 digest，防跨 filter 复用 |
| `positions` | `h` handle 绑定表（`purpose=stream`） | stream cursor 的同步 / 分页位置 |
| `target` | `h` handle 绑定表（`purpose=barrier`） | barrier cursor 等待的目标 event |
| `expiry` | `h` handle 绑定表 | 与 body `x` 一致的服务端过期时间 |

这些字段是服务端 handle 表的内容，**不是** cursor body 字段；详见 §8.3.1。

### 8.3 验证规则

服务端接收 cursor 时 MUST 验证：

1. 前缀以 `ak:cursor:` 开头。
2. 其余部分是合法 base64url。
3. 解码后是合法 JSON。
4. 解码后 body MUST 通过 [`cursor.schema.json`](../../artifacts/schemas/cursor.schema.json)：`v` / `purpose` / `t` / `x` / `h` 必填，未知非私有字段、`_mac`、`_sig` 以及任何内联位置 / target 字段均 MUST reject `invalid_param`。
5. 解码后 `v` 是支持的版本。
6. 解码后 `purpose` 是 `stream` 或 `barrier`。
7. 解码后 `x` 在未来（允许 5 分钟时钟偏差）。
8. cursor 被消费的 binding context MUST 与 `purpose` 一致；binding context 的具体 wire 位置由对应 transport / API binding 定义。若 `purpose=barrier` 的 cursor 出现在 stream context，或 `purpose=stream` 的 cursor 出现在 barrier context，接收方 MUST 返回 `invalid_param`。
9. **TTL 硬上限**：先校验 `t` 的 well-formedness——`t` MUST 是合法 RFC 3339 UTC 时间戳（§8.2 要求 `Z` 结尾且为秒级、不带小数部分），且 `t` 解析得到的 Unix ms MUST ≤ `x` 解析得到的 Unix ms；`t` 非法（不可解析、非 UTC / 非 `Z` 结尾 / 带毫秒小数等非 canonical 精度）或 `t_ms > x` 的 cursor MUST reject `invalid_param`（否则 `x - t_ms` 为负或解析异常，可令损坏 / 恶意 cursor 绕过下方 TTL 硬上限）。此外 `t` MUST NOT 位于未来：`t_ms` MUST ≤ 接收时刻的 Unix ms + 时钟偏差容忍（5 分钟，口径同规则 7）；超出 MUST reject `invalid_param`（否则 issuing 方可把 `t` 写成接近 `x` 的未来时间，令名义 TTL `x - t_ms` 通过下方硬上限校验，而实际剩余有效期 `x - now` 远超上限，绕过 TTL 硬上限）。随后以 `t` 解析为 Unix ms 后，`x - t_ms` MUST 满足以下硬上限：barrier cursor ≤ 3,600,000 ms（1 小时），stream cursor ≤ 604,800,000 ms（7 天）。超出上限的 cursor 视为 issuing 服务的协议错误，接收方 MUST reject `invalid_param`。理由：barrier cursor 仅是 RYW 等待屏障，过期意义随 frontier 追上而失去；stream cursor 在数周活动后已无因果对齐价值。

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

未来 profile MAY 在 `ak.profile.principal_server.v1` 之上引入显式 cursor translation operation；该 operation 与 transport binding 不属于 v1 强制范围。

### 8.5 测试向量入口

可执行向量位于：

- [`spec/v1/artifacts/fixtures/encoding-fixture.json`](../../artifacts/fixtures/encoding-fixture.json)

向量覆盖点：cursor 版本字段与过期、opaque round-trip、`h` handle 必填、过期 token 回退、非法额外字段拒绝。

### 8.6 一致性

声明支持 Arkret v1 同步的实现 MUST：

- 以不透明字符串形式接受和传输版本 1 cursor。
- 服务端 MUST 接收时验证所有 cursor 字段。
- 服务端 MUST 按 §8.2 canonical schema 编码 cursor 内部结构（私有字段限于 `_` 前缀）。
- 客户端 MUST NOT 解析 cursor 内容。
- stream cursor 的 server-side handle binding MUST 支持至少 50 个 Realm 的位置。
- **每 Realm 的 handle-bound frontier 长度 SHOULD ≤ 1000 个 event_id**：超出时 issuing 服务 SHOULD 用 `event_set_commitment.root` 或 snapshot pointer 折叠 frontier，再写入 handle binding。该上限避免大并发 actor Realm (≥ 1000 active actor 各自有 head event) 让 cursor authority metadata 无界增长。
- **整个 cursor base64url 解码后 canonical bytes MUST ≤ 64 KiB**：超出时 issuing 服务 MUST 用 snapshot pointer / commitment hash 折叠，MUST NOT 直接产出超大 cursor；receiver 收到超大 cursor MUST `invalid_param`。
- 大型 Realm 在 frontier 折叠为 `event_set_commitment.root` 或 snapshot pointer 后，仍 MAY 通过显式 sync extension profile 提供 range-based set reconciliation 能力，用于按差异大小协调缺口；该能力不得改变 Seal finality、Event 因果语义或 cursor 不透明性，且未声明该 profile 的 v1 consumer MUST 继续按 snapshot / backfill 路径恢复。
- 支持 stream cursor 与 barrier cursor 的过期时间；两者的 TTL 硬上限数值由 §8.3 规则 9 唯一定义，本节只引用不重复字面数值。
- 拒绝非法 cursor 时 MUST 按 §8.3 与 [`conformance-vectors.md`](./conformance-vectors.md) §1.11 的错误码闭集返回：语法 / schema 失败返回顶层 `invalid_param`（reason `invalid_cursor`），过期返回 `cursor_expired`，handle lookup / binding 失败返回 `cursor_integrity_invalid`。

## 9. Rank

列表排序 rank MUST 使用 `ak.rank.lexofractional.v1` profile，除非 Realm schema 显式声明其他 rank profile。

规则：

- 字符集固定为 ASCII `0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz`，按该字符集顺序比较。
- Rank MUST 是 1..128 字符的字符串，且每个字符 MUST 来自上述字符集。
- 排序 MUST 使用逐字符字典序；若一个字符串是另一个字符串的前缀，较短者排在较前。
- `rank_between(left, right)` MUST 返回一个严格满足 `left < rank < right` 的 rank，或返回规范错误 `rank_exhausted`（该 wire/reducer 错误码的机读归属见 [`error-code-registry.json`](../../artifacts/registry/error-code-registry.json)）。`left` 或 `right` MAY 为空，表示容器开头或结尾的哨兵边界。
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

例如 `rank_between("", "0")` MUST 返回 `rank_exhausted`，因为在 start sentinel 与最小 rank `"0"` 之间不存在合法 rank。客户端或 reducer 遇到 `rank_exhausted` MUST 触发 rebalance 或要求调用方提交 `ak.container.rebalance`，MUST NOT 生成非法 rank。
- 当 rank 长度超过 128，或连续插入导致实现无法生成短 rank，客户端 SHOULD 请求或提交 `ak.container.rebalance`。Reducer MUST NOT 接受超过 128 字符的 rank。
- 同一 container 内 rank 完全相同的对象 MUST 按 `rank_source_event_hlc`、`rank_source_actor_id`、`rank_source_event_id`、`object_id` 继续排序；如果 rank source 元数据缺失，MUST 使用 `object_id` 作为最终稳定 tie-break，并在 conformance report 中声明降级。该 tie-break 仅用于 projection 展示序，不进入 canonical state、`state_root` 或授权判断。
- **并发同 gap 插入抖动（concurrent-insert jitter，normative）**：两个客户端在同一 `(left, right)` gap 并发调用 `rank_between` 会确定性地算出相同 rank，落到上一条的 tie-break，体验上表现为顺序抖动。为降低该碰撞概率，`rank_between` 在该 gap 仍有剩余编码空间时 SHOULD 在所选 rank 尾部追加一段短随机 jitter 尾缀（合法 base-62 字符，不破坏 `left < rank < right` 严格不等式与 1..128 长度上限）；jitter 是最终 rank 字符串的一部分，MUST 进入 canonical payload bytes 与 event digest，但不构成独立字段，也不改变 rank 的字典序比较规则。jitter 只降低碰撞概率、不替代上一条的确定性 tie-break：rank 仍相同时 MUST 回落到 `rank_source_*` 全序。耗尽编码空间时按上一条走 `ak.container.rebalance`，MUST NOT 用 jitter 绕过 128 字符上限。
- `ak.container.rebalance` 的 assignment 生成 MUST 基于权限裁剪前的 canonical ordered set。先按 reducer 已确定的稳定顺序排列 active edges，再选择最小宽度 `w`，使 `alphabet_length^w >= 2 * (item_count + 1)`；第 `i` 个对象（1-based）的 rank number 为 `floor(i * alphabet_length^w / (item_count + 1))`，以固定宽度 base62 编码并用 alphabet 第一个字符左填充。若所需 `w > 128`，实现 MUST reject 该 rebalance。
- Rebalance assignments MUST 覆盖 container 内全部 active edges，且 MUST NOT 新增、删除或跨 container 移动 edge。CAS 的 `expected_state_digest` 不匹配时，MUST 拒绝整个 operation，MUST NOT 部分应用。

## 9.5. Composite Cell Subject

部分 cell 的 subject 由多个 sub-component 复合派生（例如 `ak.device.authorize` 的 `(principal_id, device_id)`）。复合 subject 的 canonical 形态由本节定义；cell id、Control Move precondition、Lattice join 和 fixture 必须使用同一形态。

### 9.5.1 通用规则

- 复合 subject 的 canonical wire 形态 MUST 是 base64url（无 padding）编码的 SHA-256 digest：

  ```text
  cell_subject = base64url_nopad(sha256(canonical_json(components_array)))
  ```

  其中 `components_array` 是按本规范声明的固定顺序排列的 JSON scalar array。每个 element MUST 保留 schema 校验后的 JSON 类型，只允许 string、integer、boolean，以及仅当该来源字段 schema 明确允许时出现的 JSON `null`；number 的小数/指数形态、object、array 一律 `schema_violation`。string element MUST 使用该字段自己的 canonical profile：typed ID 使用 schema 规定的小写 canonical 形态；DID 保留 DID method 定义的 canonical bytes，MUST NOT 做 Arkret 全串 NFKC / case folding；handle 使用已准备 localpart + 小写 A-label domain；connection identifier 使用其 kind / provider profile。复合 subject producer 与 verifier 必须消费同一 typed value，不得先把 integer / boolean / null 字符串化，也不得用通用 Unicode normalizer 猜测外部标识符等价。
- 实现 MUST NOT 直接使用 `a|b|c` 这种管道分隔字符串作为复合 subject。canonical cell id、签名输入、state map 索引 MUST 使用 hash 形态。
- cell subject 的 registry 字段来源必须显式命名：payload 来源写成 `payload.<具名路径>`，Event Envelope 来源写成 `envelope.<字段>`；裸字段名与“先查 payload、再查 envelope”的 fallback 求值一律未定义并 MUST `schema_violation`。v1 的 envelope 来源白名单只包含 `envelope.actor_id` 与 `envelope.event_id` 两项；`envelope.realm_id`、`envelope.executed_by` 及其它未登记字段均不得用于 subject。

  `envelope.event_id` 是白名单里唯一一个**不按字面取值**的来源，且只能出现在 `{"kind": "id:<对象种类>", "field": "envelope.event_id"}` 这一形态里：求值结果 MUST 是把该 create Event 自身 `event_id` 的完整 33-octet token 原样换成 `ak:<对象种类>:` 前缀后的**派生对象 ID**（`zh/models/common-fields.md` §6.0），而不是原始的 `ak:event:…` 字符串。理由是结构性的——同一对象的后续 Event 用 `payload.<种类>_id` 定位 cell，若 create 用原始 event id 作 subject，create 与其后所有更新会落在两个不同的 cell 上，`head_eq` 前置条件与 `state_root` 叶集当场分叉。`id:<对象种类>` MUST 是 registry 中 `id_source = event_derived` 的种类；指向 producer 自行分配的种类一律 `schema_violation`。composite / tuple / coalesce 的分量位置里出现裸 `envelope.event_id` 同样是 `schema_violation`：那里没有携带目标种类，无法派生。registry 中的 payload 路径 MAY 是点分嵌套路径（如 `payload.key_scope.effective_scope.realm_id`），但每一段 MUST 是该对象的具名字段，且最终取值 MUST 是上一条定义的 JSON scalar；路径中出现数组下标、通配或非具名段一律 `schema_violation`。
- **单字段与 `coalesce` subject（normative）**：普通单字段 subject 直接取 registry `field` 指向的 schema-validated scalar。非复合 subject MAY 使用封闭 descriptor `{"kind":"coalesce","fields":[<字段路径>…]}` 在一个稳定 cell family 被多个显式 payload 分支或 payload class 共用时定址；receiver MUST 按 `fields[]` 登记顺序选择第一个存在的字段，所选值必须是该路径 schema 声明的 canonical scalar。schema 必须保证每个合法 payload 至少一个候选存在；全部缺失、首个存在值非 scalar、未知成员、空 `fields[]` 或重复路径均 MUST `schema_violation`。`coalesce` 的 canonical subject 就是所选 scalar 的 canonical wire value，不额外 hash descriptor 或字段名。它只允许作为**整个非复合 subject** 的显式跨分支兼容 descriptor；不得放入 `components[]`，不得替代下一条的判别式 `select`，也不得靠未登记字段或 payload 形状产生新分支。artifact gate MUST 解析 Event-kind payload dispatch 并验证：单字段路径、每个 composite component、`select.selector` 与每个 schema 可达 branch 的 `field` 均存在且终点为 scalar；`coalesce` 至少一个候选路径在路由 class 中存在且每个存在的候选为 scalar。
- **判别式 `select` component（normative）**：`components[]` 的元素 MAY 是一个 `select` 对象，用于在同一 cell family 内按显式判别值选择该 component 的取值字段。形态固定为 `{"kind":"select","selector":<字段路径>,"branches":{<判别值>:{"field":<字段路径>,"forbidden_fields":[<字段路径>…]}}}`，`branches` 是封闭映射，`forbidden_fields` 可选。求值规则：读取 `selector` 指向的、已通过 schema 校验的**原始字符串**，与 branch key 逐字匹配，MUST NOT 做大小写折叠、Unicode 归一化或别名解析；命中 branch 后取其 `field` 的标量值作为该 component。`select` 只选择 component 的**取值**，MUST NOT 改变 `components_array` 的元素数目或顺序——同一 cell family 的所有分支共享同一 arity 与同一顺序。

分支之间是否互斥由**各分支自己的 `forbidden_fields` 显式声明**，MUST NOT 由「未命中分支的 `field` 出现即歧义」这类通用规则推断：多个分支合法共享同一字段是常见形态（例如 `effective_scope` 的 `circle` 分支按 schema 必须同时携带 `realm_id` 与 `circle_id`，而 `realm_id` 正是 `realm` 分支的取值字段），通用禁止会把这类合法 payload 全部拒掉。`forbidden_fields` MUST 与该 payload schema 的互斥约束一致，只作为不经 schema 校验路径上的等价 fail-closed 复核，MUST NOT 声明 schema 允许共存的字段。

下列任一情况 MUST fail closed（`schema_violation`）：`selector` 缺失或非字符串；判别值不在 `branches` 中；命中 branch 的 `field` 缺失；命中 branch 的某个 `forbidden_fields` 路径在 payload 中出现；取值不是该字段 schema 要求的 canonical 标量。实现 MUST NOT 在 composite component 内用字段存在性回退或 payload 形状推断替代显式 `selector`；上一条定义的顶层非复合 `coalesce` 不属于此禁令，但也不得嵌入 composite。
- **规范字符串集合摘要 `string_set_digest` component（normative）**：`components[]` 的元素 MAY 是固定形态 `{"kind":"string_set_digest","field":<字段路径>,"context":<ASCII context>}`。该 descriptor 只适用于 schema 已封闭为 `string | array<string>`、两种形态引用同一元素 schema、array 明确 `minItems >= 1` 且 `uniqueItems: true` 的字段；descriptor 只允许 `kind`、`field`、`context` 三个成员。若字段是 string，令集合序列 `S=[value]`；若为 array，复制其元素得到 `S`。求值器 MUST 在 schema 校验后再次确认 `S` 非空、所有元素均为 schema 允许的字符串且逐字无重复，然后按 JSON 解码后字符串的原始 UTF-8 bytes 升序排列；MUST NOT trim、case-fold、NFC/NFKC 归一化或使用 locale collation。component 输出为普通 JSON string：

  ```text
  string_set_component =
    base64url_nopad(
      sha256(
        utf8(context)
        || 0x0A
        || canonical_json(S)
      )
    )
  ```

  `string_set_digest` 是 registry descriptor 的封闭派生类型，不把 array 加入通用 composite scalar 集合。内层固定使用 SHA-256，不跟随 Realm digest suite；context 后恰好一个 `0x0A`，不得加入 NUL、长度前缀或尾随换行。字段缺失、空集合、重复项、非字符串项、schema 不封闭、未知 descriptor 成员或非 ASCII/空 context 均 MUST fail closed（`schema_violation`）。
- 同一 standard cell family 的 `components_array` schema 由本规范固定，profile MUST NOT 擅自增删字段或重新排序。

### 9.5.2 标准复合 Subject

| Cell family / Event kind | components_array 顺序（来源字段） |
| --- | --- |
| `ak.component.device.authorization.v1` / `ak.device.authorize` | `[payload.principal_id, payload.device_id]` |
| `ak.component.device.authorization.v1` / `ak.device.revoke` | `[payload.principal_id, payload.device_id]` |
| `ak.component.realm_key.delivery.v1` / `ak.realm_key.share`、`ak.realm_key.withheld` | `[payload.share_kind, payload.recipient_principal_id, select(payload.share_kind), select(payload.key_scope.effective_scope.kind)]` |
| `ak.component.calendar.rsvp.v1` / `ak.rsvp.set` | `[payload.event_ref, payload.occurrence, envelope.actor_id]` |
| `ak.component.identity.accountability.v1` / `ak.identity.accountability_grant` | `[payload.issuer, payload.subject, string_set_digest(payload.accountability_scope, "ak.accountability-scope-set-v1")]` |
| `ak.component.call.recording.v1` / `ak.call.recording.start`（`capture_kind="recording"`）、`ak.call.state` | `[payload.call_id, payload.recording_id]` / `[payload.call_id, payload.recording_result.recording_id]` |
| `ak.component.call.transcript.v1` / `ak.call.recording.start`（`capture_kind="transcript"`）、`ak.call.state` | `[payload.call_id, payload.recording_id]` / `[payload.call_id, payload.transcript_result.recording_id]` |

`principal_id` MUST 是无 fragment 的完整 DID URI（见 §4）；`device_id` MUST 是完整 `id:device` typed ID（`ak:device:<uuidv7>`）。

`ak.component.realm_key.delivery.v1` 的四元组固定 arity 4，两个 Event kind 使用**逐字相同**的 registry descriptor，其中后两个 component 是 §9.5.1 的 `select`：

- `share_kind` 直接取 `payload.share_kind`。它 MUST 进入 components 做**目标类型域分隔**：`recovery_recipient_id` 只是 Realm-local 非空字符串，可被构造成与某个 `ak:device:*` typed ID 相同的文本；缺少该 component 时 RRK recipient 与 member device 会落入同一 delivery cell。
- `recipient_target_id` 按 `payload.share_kind` 选择：`member_device` → `payload.recipient_device_id`；`realm_recovery_key` → `payload.recovery_recipient_id`。`recipient_verification_method` 是可轮换的 RRK 密钥引用，MUST NOT 进入 subject（它由 `sender_device_signature` 与接收方校验覆盖，见 [`../crypto-media/device-lifecycle.md` §13](../crypto-media/device-lifecycle.md)）；把它纳入定址会在 RRK 轮换后拆分同一 recovery recipient 的 ordered log。
- `effective_scope_id` 按 `payload.key_scope.effective_scope.kind` 选择：`realm` → `realm_id`；`circle` → `circle_id`。完整 `key_scope`（`policy_digest`、membership frontier、epoch 区间）是单次交付/拒绝决定的证据，随策略与 epoch 变化，MUST NOT 进入稳定 subject。
- `recovery_recipient_id` 作为 component 时 MUST 使用 payload 中经 JSON 解码得到的原始 Unicode scalar sequence，由 canonical JSON 负责转义；MUST NOT 做 NFKC / NFC、case folding 或 trim。
- receiver MUST 独立校验 `effective_scope.realm_id` 等于 Event `realm_id`，Circle 分支还 MUST 校验该 `circle_id` 属于该 Realm。

`ak.component.calendar.rsvp.v1` 的三元组固定 arity 3；`envelope.actor_id` 是 accountable responder，delegated execution 下不得改用 `executed_by`。实例级 RSVP 的 `payload.occurrence` 是 [`calendar-event.md` §8](../models/calendar-event.md) 的 canonical string——all-day 为 `YYYY-MM-DD`，timed 为整秒 `YYYY-MM-DDTHH:mm:ss[Zone]`，其中 Zone 是已签名的 canonical IANA Zone name。v1 的 timed local anchor 与 occurrence key 都收窄到整秒，因此不存在两个不同 subsecond occurrence 折叠到同一 key 的情况；实现 MUST NOT 接受带小数秒、offset 或 `Z` 的 occurrence，也 MUST NOT 在 receiver 侧把非 canonical 值改写后再派生 subject——cell 地址来自**已签名的原值**，非 canonical 输入 MUST 以 `rsvp_occurrence_not_canonical` 拒绝。series 级 RSVP 的 digest preimage 固定保留 JSON null，例如 `["ak:strand:<44-char-suite-tagged-full-digest-token>",null,"did:..."]`。实现 MUST NOT 把 null 改写成字符串 `"null"`、空串或 `"series"` sentinel。payload 中即使出现同名 `actor_id` 也不得遮蔽 `envelope.actor_id`。`payload.entry` 是该 cell 的 lattice value（见 [`calendar-event.md` §8.3](../models/calendar-event.md)），不参与 subject 派生。

`ak.component.identity.accountability.v1` 的第三个 component 固定使用 `context="ak.accountability-scope-set-v1"` 的 `string_set_digest`。`accountability_scope` 的 string 与 singleton-array 写法、以及同一合法 array 的任意排列，MUST 命中同一 cell；不同 exact scope set MUST 命中不同 cell。`active` 与 `revoked` 状态不进入 subject，因此同一 exact set 的撤销写回同一 `cas_register`。子集 revoke 只命中子集自己的 cell，不得对超集做隐式集合差；同一 issuer/subject 可同时有多个 active exact-set cell，其 projection scope 是所有当前 active cell 的集合并集。

两个 call capture family 的第二个 component 固定取 **payload** 的 `recording_id`（start event 取 `payload.recording_id`，后续 `ak.call.state` 取 `payload.recording_result.recording_id` 或 `payload.transcript_result.recording_id`），不得改用 Event envelope 的 `event_id`。同一 `recording_id` 的 start 与状态更新因此落入同一 cell；不同 recording 不会共享 cell。`ak.call.recording.start.capture_kind` 决定写 recording 还是 transcript family；`ak.call.state` 只有在相应 `recording_state` / `transcript_state` 出现时才写对应 family。

非复合 cell（例如 member 用 actor DID、capability grant 用 grant id、Realm policy 用 Realm id）直接把规范化 subject 放入 `ak:cell:<component>:<subject>`，不需要 hash 化。

接收方收到不符合本节定义的复合 subject components_array 时 MUST 返回 `schema_violation`。文档中若以管道分隔形态展示复合 subject，MUST 显式标注 "informational; canonical cell subject is base64url(sha256(canonical_json(...)))"。

### 9.6 State / Cell 编码索引（导航）

_Informative._ 本小节只做导航锚，不搬迁任何 normative 内容；各编码规则的 canonical 定义仍在所引小节。State / Cell 相关编码分散在多处，单点索引如下:

| 编码对象 | canonical 定义位置 |
| --- | --- |
| Cell subject 编码(复合 subject hash 形态、标准复合 subject 表) | 本文 §9.5 |
| `state_root` 的 Merkle 编码与 inclusion 规则（治理 `state_root` leaf/node 域分隔 + 统一 Seal Merkle 组合规则） | [`authz/event-auth-state-resolution.md` §6.2.1 / §6.2.2](../authz/event-auth-state-resolution.md) |
| `state_root` / Seal hash 的 wire 形态与 algo 固定规则 | 本文 §3.3 |
| Hash wire 形态(`<suite>:<hex>`)与 Digest Suite registered set | 本文 §3.1 / §3.2 |
| Cell tuple 引用形态(`ak:cell:<component>:<subject>`) | 本文 §4(special forms) |

## 10. Encrypted Envelope Digest

加密 payload 的 digest MUST 覆盖密文和明文路由元数据：

```text
aad_bytes = canonical_json(aad)
aad_digest = sha256(aad_bytes)
payload_metadata_bytes = canonical_json(payload_metadata)
encrypted_payload_bytes = base64url_decode(ciphertext)
payload_digest = sha256(payload_metadata_bytes || encrypted_payload_bytes)
```

上式产出 32 字节 raw digest；其 wire 形态 MUST 为 `sha256:<lowercase_hex>`，与 §3.1 一致。`payload_metadata` 的字段集合、缺失字段处理、`mls_rfc9420` 下不得携带 `authentication_tag` 的规则，以 [`crypto-media/encryption-and-audit.md` §2.3.3](../crypto-media/encryption-and-audit.md) 为唯一真源。

`payload_metadata` 至少覆盖 `scheme`、`version`、`group_id`、`epoch`、`content_type`、`aad_visibility_event_id`、`aad` 与 `key_ref` 中实际出现在 envelope 的字段；字段缺失时必须省略，不得写入 `null`。实现 MUST NOT 使用明文 payload 作为 `payload_digest` 输入，也不得把 base64url ciphertext 字符串本身作为密文字节输入。

### 10.1 AEAD nonce uniqueness（normative）

任何在 v1 wire 上承载 AEAD 加密内容的 envelope（`encrypted_payload`、blob attachment、`to_device` payload 等）MUST 满足 AEAD nonce 唯一性 contract。下列公式是 v1 的 canonical nonce 派生定义；领域文档只声明各自的 `purpose` 取值和 envelope 字段位置。

下文 `N_AEAD` 指所选 AEAD algorithm 的 nonce 字节长度：XChaCha20-Poly1305 为 24，AES-GCM 为 12。

```text
sender_nonce_prefix = MLS-Exporter(
    label   = "arkret-aead-sender-nonce-prefix-v1",
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
- **跨设备域分离**：nonce 唯一性按实际 AEAD key 判断。共享同一 raw AEAD key 的 domain MUST 在 epoch/admission 建立时枚举 active sender prefix，发现碰撞即 fail closed / rotate epoch；仅按声明 sender 重算 prefix 不能发现两个合法 device 的 32-bit 碰撞。domain MAY 改为按 sender 派生独立 raw AEAD key，此时相同 prefix/counter 位于不同 key 下，不构成 nonce reuse，但 receiver 仍 MUST 按 sender `device_id` 重算并校验 prefix。Signal 明确选择后一合同：`K_signal[epoch,device] = ExpandWithLabel(history_secret[epoch], "ak.signal-v1", JCS({sender_device_id:device}), AEAD.Nk)`；不得使用 group-shared Signal key。prefix 与声明 sender 不匹配时 MUST fail closed (`aead_nonce_sender_domain_collision`)。
- **不回退到 random**：实现 MUST NOT fallback 到 random nonce。96-bit AEAD (AES-GCM) 在 ~2^48 次操作上有显著 birthday-bound 碰撞率；Arkret MLS application key 跨多设备共享，naive random nonce 不满足 v1 normative。
- **接收方 replay 防护**：接收方 MUST 维护 per-`(key_ref, epoch, device_id, purpose, aead_profile)` 已见 counter 集合或等价无误判结构，重复 counter MUST 触发 `failed_precondition` reason=`aead_nonce_counter_replay`。
- **AAD binding（normative，§10.2）**：AEAD AAD MUST 是该 domain 的 **pre-encryption immutable header** 的 canonical bytes，见 §10.2。任何依赖 AEAD 输出的字段（覆盖 authentication tag 的 ciphertext digest、payload digest、content digest、receipt 等）MUST NOT 进入同一次 AEAD 的 AAD。
- **不同 AEAD 用途独立 nonce 域**：`purpose` MUST 写入 exporter context。标准 purpose 取值由消费域文档声明；未声明 purpose 的 AEAD envelope MUST fail closed。

**Registry 真源（normative）**：上式使用的 MLS-Exporter label `arkret-aead-sender-nonce-prefix-v1` 是 wire-breaking 的安全域分隔参数，MUST 登记于 [`exporter-label-registry.json`](../../artifacts/registry/exporter-label-registry.json)（该 registry 是全部 normative MLS-Exporter label 的 canonical source of truth，`defined_in` 回指本节）；实现 MUST 使用与该 registry 行完全一致的 label 字符串与 `context_fields` 形状（`{key_ref, epoch, device_id, purpose, aead_profile}`），MUST NOT 以空 context 派生，未登记 label MUST fail closed。其中 `aead_profile` 标识所选 AEAD 算法 suite；**其合法取值 enum 的权威 registry 由各消费 domain 显式声明**，MUST NOT 一律指向 HPKE registry：应用层 HPKE sealing surface（key backup / to-device / file-transfer key envelope 等）取 [`hpke-suite-registry.json`](../../artifacts/registry/hpke-suite-registry.json)（§6.1）；由 MLS exporter 派生 key 的 domain（`mls_exporter_aead_v1` 内容加密、ephemeral signal AEAD）取 [`mls-ciphersuite-registry.json`](../../artifacts/registry/mls-ciphersuite-registry.json) 的 `canonical_id`，并 MUST 等于 `key_ref.group_state_ref` 所指 MLS group 实际协商的 active ciphersuite。未登记 suite、或与该 group 实际 ciphersuite 不符的 `aead_profile` MUST fail closed。实现 MUST NOT 再发明第三层会漂移的 AEAD 映射名。

### 10.2 AEAD AAD = pre-encryption immutable header（normative）

每个在 v1 wire 上使用 AEAD 的 domain MUST 定义一个 closed、JCS canonical 的 **immutable header**。该 header 的全部字段 MUST 在调用 AEAD seal 之前已确定，至少绑定 `key_ref`、`nonce`（或 `nonce_prefix` 与其确定性后缀分量）、`purpose` 与 `aead_profile`，并绑定该 domain 的 routing / identity / epoch 字段。AEAD AAD MUST 是该 header 的 canonical bytes。

任何依赖 AEAD 输出的字段——包括覆盖 authentication tag 的 `ciphertext_digest`、`payload_digest`、content digest 或 receipt——MUST NOT 进入同一次 AEAD 的 AAD。此类 **post-encryption commitment** MUST 由该 domain 指定的外层 authentication（已签名 Event / encrypted descriptor / upload receipt / envelope proof）覆盖；某条路径若没有任何外层认证，MUST 补齐认证，MUST NOT 把 digest 塞回 AEAD AAD。

**为什么是纯删除（normative rationale）**：本节的前身条款曾以“防止 (key, nonce) 下的 ciphertext 被与另一 AAD 配对解密”为由要求 AAD 绑定 `ciphertext_digest`。该理由不成立：AEAD 的 tag 本身就是对 `(key, nonce, AAD, ciphertext)` 四元组的认证，在 `AAD₁` 下产生的密文改用 `AAD₂` 验证必然失败——这是 AEAD 的定义性质。因此从 AAD 中删除 ciphertext digest **不损失任何安全属性**：ciphertext↔AAD 绑定由 tag 提供；ciphertext↔key domain 绑定由实际使用的 key 与 AAD 中已认证的 `key_ref` 共同提供；ciphertext↔nonce 绑定由 nonce 参与 seal/open 提供；AEAD 非 key-committing 的已知问题由 `key_ref` 与域分离处理，`ciphertext_digest` 从来无助于此。规范 MUST NOT 保留该错误理由文本，否则后续 scheme 会重新引入同样的绑定。

**明确否决的替代构造**：

1. digest 字段先置零、seal 后替换；
2. 固定点迭代到稳定值；
3. 把 digest 重定义为“排除 tag 的 ciphertext body”从而可在 tag 之前计算——它能解开循环，但保留一个零收益字段，并制造“完整 digest”与“body digest”两个易混淆概念；
4. 为通过测试而让 receiver 忽略 AAD 中的 digest；
5. 删除 post-encryption digest 却不确认外层 proof 覆盖 ciphertext；
6. 每个实现自选 AAD 字段集合；
7. 新增 v2 scheme 而保留错误的 v1 定义。

**逐 domain 登记义务**：每个消费 domain MUST 登记 `purpose`、`aead_profile` 的权威 registry、immutable header schema、ciphertext/tag 编码、post-encryption digest 的覆盖范围、认证该 digest 的外层 proof，以及逐字节 KAT。v1 各 domain 的结论：

| domain | immutable header（AAD） | post-encryption digest | 认证该 digest 的外层 |
|---|---|---|---|
| `mls_exporter_aead_v1`（[`../crypto-media/encryption-and-audit.md` §2.10.2](../crypto-media/encryption-and-audit.md)） | `aead_aad_bytes` = JCS(`{scheme, key_ref, epoch, nonce, purpose, aead_profile, aad}`) | `payload_digest`（§10 / §2.3.3） | Event proof |
| `ak.signal_exporter_aead.v1`（[`../sync/signal.md` §1](../sync/signal.md)） | `aad_digest` 覆盖 JCS(`{realm_id, scope_ref, sender_actor_id, sender_device_id, seal_ref, signal_class, sent_at, expires_at, scheme, key_ref, purpose, aead_profile, epoch, nonce}`)；`purpose` = `ak.signal.v1`，`aead_profile` 取 `mls-ciphersuite-registry.json` | `envelope_digest`（覆盖移除 `proof` 后的完整 envelope，因而承诺 ciphertext 与 `aad_digest`） | `SignalEnvelope.proof`（device detached JWS，context `ak.signal-proof-v1`） |
| `ak.blob.whole_file_aead.v1` / `ak.blob.stream_aead.v1`（[`../crypto-media/media-and-blob.md` §3.1 / §3.3.3](../crypto-media/media-and-blob.md)） | 见该节列举的 pre-encryption 字段 | `ciphertext_digest` | 引用它的已签名 Event / encrypted descriptor / upload receipt |
| account data（[`../models/account-data.md`](../models/account-data.md)） | envelope `aad`（`{actor_id, account_data_key, schema, version}`） | `ciphertext_digest` | account-data envelope 自身的已认证写入路径 |
| key backup（[`../identity/key-management.md` §7.2](../identity/key-management.md)） | 已固化于 KAT 的 `aead_aad_canonical_json` | `ciphertext_digest` | `auth_data.signed_fields` 设备签名 |

`aad_digest` 是**对 AAD bytes 自身**的摘要，与本节无冲突，可由 domain 保留，但 MUST 位于 header/AAD 之外、由外层 proof 覆盖；receiver MUST 重算 AAD 而不是采信调用方自报的 `aad_digest`。domain 之间 MUST NOT 被误写成“统一必须携带”或“统一必须删除”。

**既有密文处置（normative）**：v1 尚无发布，Arkret 采取激进更新、不保留旧数据兼容。任何按前身（不可构造）定义生成的持久密文一律视为不可读，实现 MUST NOT 为其保留第二套 AAD 组成或兼容分支。
