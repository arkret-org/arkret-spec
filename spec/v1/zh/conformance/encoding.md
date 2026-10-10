---
title: Encoding, IDs, Hashes, and Signatures
status: candidate
normative: true
stability: v1
updated: 2026-09-25
sidebar:
  label: Encoding & IDs
---

# 编码、标识、摘要与签名

规范关键字按[规范语言](./normative-language.md)解释。本页只定义仍进入 v1 wire 的基础规则；Event
接纳和逐 stream 提交规则见[治理提交日志](../sync/authority-commit-log.md)。

## 1. 适用范围

Canonical encoding 用于 Event ID、RealmCommit ID、authority handoff、snapshot、detached proof 和
幂等摘要。实现不得在签名或内容寻址边界使用平台默认 JSON 序列化。

## 2. Canonical JSON

Canonical JSON MUST 使用 UTF-8、无 BOM、无无意义空白、拒绝重复 key，并按 RFC 8785 等价规则排序
object key。Arkret v1 wire 只允许 JSON integer；小数用整数与显式 scale 表达。整数必须位于 JSON safe
integer 范围。绝对时刻固定为 UTC 毫秒形式 `YYYY-MM-DDTHH:MM:SS.sssZ`，验证方不得先宽松解析再正规化。

Schema 中的 `additionalProperties: false`、closed union discriminator 和 required 字段均在 canonicalize
之前验证。未知 critical 字段必须拒绝；`x_` extension 只在所属 schema 明确允许时存在。

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
  omission 表示"无断言"，必须显式使用上述扩展并提供三种正向与交叉负向 vector。

当前唯一 `distinct` 目标是 Circle membership CAS 的 `expected_membership`。

### 2.2 String profile 与 Unicode

字符串继续由 `string-profile-registry.json` 中的领域 profile 约束；对象签名和 ID 计算使用通过 schema 验证的原值。

#### 2.2.1 网络标识与 IDNA

DID、URI、域名、email 和电话号码仍使用各自的外部 profile，不得使用通用大小写折叠改写签名字节。

## 3. Digest suite

Realm genesis 固定 Realm 的 active digest suite。内容摘要写作 registry 定义的 suite-tagged digest；不同
suite 的摘要不能比较为相等。Event、RealmCommit、handoff 与 snapshot 的 ID 都从各自 canonical body
计算，验证方 MUST 从 ID 恢复 suite 并重算。

### 3.1 内容寻址预映射

先验证 closed schema，再移除对象自身 ID 和签名字段，最后对 canonical JSON 求摘要。

预映射内**不得承诺 Event 标识**：自身标识与同一原子单元内的兄弟标识都会让摘要的原像包含该摘要自身的函数，按构造不可满足。唯一允许的两类例外是 envelope omission 与 forward declaration，且必须逐条登记在
[`preimage-identity-exemption-registry.json`](../../artifacts/registry/preimage-identity-exemption-registry.json)。**封闭例外清单**：下表是该 registry 的封闭列表投影，两侧 MUST 同批更新：

本规则的机器管辖面是 `event-envelope.schema.json#` 根与
`event-kind-registry.json` 全部 `payload_schema_ref` 的 JSON Pointer 级 `$ref` 传递闭包；
沿 `$ref` 只进入实际目标，不遍历文档根下未被引用的 `$defs`／`definitions` 兄弟。
闭包内 Event 标识候选属性 MUST 以封闭的 `x-arkret-preimage-commitment` 声明承诺方向，
描述文字不参与裁决。闭包外对象不受本规则管辖；若其描述声称某字段进入 Event 原像，
则必须由该对象的专门门禁证明这项结构事实，不能借 §3.1 的例外表取得许可。

| exemption_id | kind | 说明 |
| --- | --- | --- |
| `ak.exemption.preimage_identity.realm_genesis.v1` | envelope_omission | `ak.realm.create` 的 envelope `realm_id`、`scope_ref.realm_id` 与 create payload object id 都不进入原像；接收方从已接受的 `event_id` 正向派生 `realm_id`。 |
| `ak.exemption.preimage_identity.agent_provision_principal_control_realm_id.v1` | forward_declaration | `ak.agent.provision` 先声明 `principal_control_realm_id = retype(genesis event_id)`；genesis 原像不含 provision 的任何标识、引用或摘要，依赖只朝一个方向。 |
| `ak.exemption.preimage_identity.agent_draft_source_pending_event.v1` | forward_declaration | holder 只在独立的 `ak.agent.draft.propose` 已接受、`event_id` 已固定后 author `ak.account_data.set.source_pending_event_id`；proposal 原像不含后者的任何标识、引用或摘要，依赖只朝一个方向。 |

机器 fixture 声明的派生结论 MUST 以本节的原像与摘要规则被重算，而不是与输入并列书写；
证据形态与封闭的关系词表由 `ak.vector.encoding.derived_relation_evidence.v1` 承载。

### 3.2 Suite-tagged digest

具体 suite 由 typed ID 或所属 Realm genesis 唯一决定；实现不得尝试多种 suite 后择一通过。

### 3.3 Stream 链接与 Commit ID 承诺

每条 Realm、Circle 或 Sidecar stream 的完整性由 `RealmCommit.previous_commit_ref` 与 `stream_position` 的链接
承诺给出：位置从 0 起在本 stream 内连续递增，每个 Commit 指向本 stream 的上一个 Commit。Commit ID 是对完整
Commit body（不含其自身 ID）的 canonical 摘要，因此一次性承诺 Event ID、stream、位置、前驱、authority
generation 与治理 Station proof。验证方据此重算 Commit ID 并校验链接，就得到该 stream 的完整性判据。

跨 stream 的协调只经由已提交引用与显式补偿 Event：不存在共享 root、共享 position，也不存在隐含的跨 stream
原子提交。Realm、每个 Circle 与每个 Sidecar 各自独立，两条 stream 的位置之间没有可比较关系。

### 3.4 Canonical 展示顺序（normative）

Event digest 只是 producer 可控内容的摘要：producer 要击败一个已知随机 digest，期望约两次尝试。因此本节
定义的顺序只提供**跨实现确定性**，不提供中立、公平或不可操纵的 winner。

- 比较输入是 §5 的 canonical event digest（移除 `event_id`、`producer_proof` 与 `unsigned` 后的 canonical Event body
  摘要）。digest preimage MUST 逐字使用该 canonical body，实现不得额外加入或移除业务字段。
- 比较对象是**解码后的 digest octets**，按 unsigned lexicographic order 升序。octets 完全相同而 suite 不同时，
  以 canonical suite id 的 UTF-8 unsigned bytewise 升序作第二键。实现 MUST NOT 直接比较 `<suite>:<hex>` 或
  base64url wire string——字符串顺序与 octet 顺序可以相反。

  **第二键的适用范围（说明性）**：§3 规定 Realm genesis 固定该 Realm 的 active digest suite，因此在**单个
  Realm 内部**这个第二键不可达。它只在把多个 Realm 的候选聚合到同一个展示面时才可能触发——跨 Realm 的
  统一时间线或审计列表——那时两个候选可以来自不同 suite。实现 MUST NOT 因为 Realm 内不可达就省略该第二键。
- 两个不同 canonical preimage 得到同一 suite、同一 octets 的 typed digest 是 collision，MUST fail closed，
  MUST NOT 回退到 `event_id`、`created_at`、到达顺序或实现私有 ID 补全顺序。canonical preimage 逐字相同、
  只有 `producer_proof` 或 `unsigned` 不同的两个输入 MUST NOT 被报成 collision。

该顺序只允许用于 canonical set 序列化、审计列表与 timeline/展示的稳定排列，并且全部候选 MUST 保持完整可见。
**本节只定义一个 comparator，不是任何展示面的默认序**：这是 scope restriction（允许用在哪里），不是
「timeline 必须用此序」的义务。跨流展示序的唯一定义点是
[`../sync/client-sync.md` §6](../sync/client-sync.md)——同流按 `stream_position`，跨流无 protocol 序。
它 MUST NOT 决定授权、admission、finality、`stream_position`、`previous_commit_ref` 或任何不可逆副作用，也
MUST NOT 从互斥候选中选出唯一 winner。需要单值语义的领域 MUST 使用已登记的 `expected_revision` compare-and-set
或该领域自己的 validator，不得把本节 comparator 包装成领域规则重新引入 winner。

Conformance 入口是 `ak.vector.encoding.canonical_event_tie_break.v1`（见
[`conformance-vectors.md` §3.7](./conformance-vectors.md)）。

## 4. Typed ID 与引用

Typed ID 的前缀、payload pattern、是否内容寻址只由
[`id-kind-registry.json`](../../artifacts/registry/id-kind-registry.json)决定。接收方必须拒绝未登记前缀、非法
payload、错误 suite 和大小写变体。

`ak:event:`、`ak:realm_commit:`、`ak:realm_authority_handoff:` 与 `ak:realm_snapshot:` 是内容寻址对象。
对象自身主键使用 `*_id`；指向既有不可变对象使用 `*_ref`。同一对象不得同时携内容寻址引用及可从该引用
恢复的 sibling digest。

### 4.0 Typed ID 通用规则

Typed ID 必须通过 `id-kind-registry.json` 登记的唯一 grammar 和 authority 分类。

#### 4.0.1 引用验证

`*_ref` 必须先验证类型前缀，再在调用者获权的 stream 中解析，不得跨 Circle/Sidecar 探测。

### 4.1 生产者分配的 ID

生产者分配 ID 必须在对应 producer proof 的签名投影内，治理 Station 不得代换。

### 4.2 服务分配的 ID

服务分配 ID 仅用于 registry 明确指定的非内容寻址对象，并受幂等索引约束。

## 5. Event ID

Event ID 从 producer 已签名的 canonical Event body 派生。接收方先校验 closed schema，再重算 Event ID，
最后验证 producer proof。治理 Station 不得修改 Event 后重新计算身份；接纳结果通过单独的 RealmCommit
表达。

Event ID preimage 不含 RealmCommit、接收时间、stream position 或 authority proof，因为这些值在 producer
签名之后才产生。

## 6. Detached signature

每个 proof context 必须在
[`proof-context-registry.json`](../../artifacts/registry/proof-context-registry.json)登记 domain separation、
canonical projection 和 signer role。签名验证必须同时验证 domain、payload digest、verification method、
key purpose、有效期与撤销状态。验证 transport 身份不能替代对象 proof，反之亦然。

RealmCommit 只接受当前 authority generation 的治理 Station proof。Handoff 同时要求 old/new Station 对同一
transition body 的 proof；snapshot 与 private full-stream-head manifest 的摘要也必须进入该 transition body。

#### 6.0.1 Detached proof 投影

投影必须从已验证 typed object 构造，不得从宽松 JSON map 或本地默认值构造。

#### 6.0.2 Proof binding object 的统一构造（normative）

本节是对 [`proof-context-registry.json`](../../artifacts/registry/proof-context-registry.json) `contexts[]`
**每一行都生效**的唯一构造规则。各对象族正文只补充本族特有的取值约束（例如 `audience` 必须是哪个 service
DID），MUST NOT 改写下面四条的编码语义。

**(a) Unsigned projection**：当某族的 `binding_fields` 含 `payload_digest` / `event_digest` /
`receipt_digest` / `envelope_digest` 之一时，该 digest 的原像按下列顺序得到：

1. 取被签对象，**整体删除 proof carrier 成员**。carrier 名由该族 schema 决定（`proof` / `proofs` /
   `signature` / `governance_proof`）；Event Envelope 另按 §5 删除 `event_id` / `producer_proof` / `unsigned`。
2. 删除的是**成员本身**，MUST NOT 置为 `null`，也 MUST NOT 保留空对象或空数组占位：`null` 与缺席在
   canonical JSON 下是不同字节，两种写法会产生两个互不验证的 digest。
3. 实际存在的 optional 字段逐字保留；缺席的 optional 字段 MUST NOT 被补写默认值、空串、`0` 或 `null`。
   发送方与接收方 MUST 对同一 wire bytes 得到同一原像。
4. digest 按 §3 的 suite-tagged 形态编码，算法由该 Realm 的 active digest suite 决定。

`binding_fields` 不含上述任一 digest 字段的行，其 binding object 本身就是完整 transcript，不存在 unsigned
projection，MUST NOT 另行发明一个 payload digest 字段。

**(b) 可选 binding field 的缺席形态**：`binding_fields` 中以 `?` 结尾的成员缺席时，binding object MUST
**整体省略该 key**，MUST NOT 写入 `null`、空串或空数组。接收方 MUST 按同一规则重建 binding object，
MUST NOT 为求形状齐整补键。

**(c) `audience` 的两种形态**：`audience` 封闭为单个非空字符串，或非空、无重复的字符串数组。**恰好一个
受众时 MUST 使用单值形态，MUST NOT 写成单元素数组**；两个及以上受众时 MUST 使用数组，元素顺序在 canonical
bytes 中逐字保留，接收方 MUST NOT 重排或去重后再验签。

**(d) Context 常量的承载位置**：对象族的 context 常量 MUST 作为 binding object 的成员出现，key 固定为
`"context"`，值逐字等于 registry 中该行的 `context`。它 MUST NOT 改由 JWS protected / unprotected header
参数承载（header 只携带受保护的 `alg`），也 MUST NOT 作为被签对象的 wire 字段出现。verifier MUST 从
registry 行取该常量自行写入，MUST NOT 采信请求方声明的 context。

因此对同一未签名 body，一个族的 context 下产生的签名在任何相邻族的 context 下 MUST NOT 验证通过；
domain 或 audience 任一不同也 MUST NOT 互相验证。

### 6.1 领域分离

每个 proof context 使用 registry 登记的唯一 domain string；Event、RealmCommit、handoff 和 snapshot 不得共用 context。

## 7. 时间

`created_at` 是 producer 声明的审计/展示时间，不提供排序或 finality。Commit 的顺序只来自同一 stream 的
`stream_position` 与 `previous_commit_ref`。未来偏移与过期限制只用于 admission/DoS 防护，不得改变历史中
既有 Commit 的顺序。

### 7.1 HLC 编码与使用边界（normative）

v1 的 Event Envelope **不携带 `hlc`**。HLC 只出现在不参与共享治理排序的私有或临时材料中：read cursor
（[`../discovery/read-receipts.md` §6.5](../discovery/read-receipts.md)）、客户端在 encrypted account data
compare-and-set 循环中对解密明文执行的领域合并（[`../models/account-data.md` §5](../models/account-data.md)）、
加密草稿／文件传输／notification inbox 等领域当前值、可选 read receipt，以及 Sidecar 加密 exchange binding
的 `request_context.source_hlc`。HLC 即使位于共享 Event 的加密 payload 内，也仍只是接收方私有展示或合并线索，
治理 Station 不得解读它来排序、授权或接纳。

Hybrid Logical Clock 的 wire 形态固定为 `<unix_ms_hex>-<logical_hex>-<node_id_hash>`，例如
`01970e589d21-0004-a13f9c2e`：

- `unix_ms_hex` MUST 是 12 位小写十六进制毫秒时间戳。
- `logical_hex` MUST 是 4 位小写十六进制逻辑计数器，取值范围 `0000..ffff`。
- `node_id_hash` MUST 是 8 位小写十六进制稳定节点哈希，只用于同一 `(unix_ms, logical)` 下的确定性
  tie-break。它 MUST 从 Realm-scoped 或 deployment-scoped 的本地 node secret 派生，MUST NOT 直接使用
  principal DID、公开 handle、长期 device id 或任何跨 Realm 稳定标识作为 hash 输入。

排序按 `(unix_ms, logical, node_id_hash)` 字典序。任一字段宽度、大小写或分隔符不符的输入 MUST 以
`schema_violation` 拒绝，验证方不得先宽松解析再正规化。

**溢出（normative）**：生产者若在同一 `unix_ms` 内需要把 `logical_hex` 从 `ffff` 再递增，MUST NOT 回绕到
`0000`，也 MUST NOT 复用任何已发出的 HLC tuple。它 MUST 二选一：等待本地可生成更大的 `unix_ms_hex` 后以
`logical_hex=0000` 生成新 HLC；或在生成 canonical bytes 之前以本地临时错误终止该次写入并稍后重试。
MUST NOT 为逃避溢出伪造更大的 wall clock skew。消费者观察到同一 producer 的 `unix_ms` 不变而 `logical_hex`
从 `ffff` 回绕到更小值时，MUST 视为无效 HLC 并拒绝，MUST NOT 当作正常排序值接受。

**使用边界（normative）**：HLC 是不可信的 advisory 字段，**只在某领域已登记的两个候选因果不可比时**用于
选出确定性 winner；因果可比时 MUST 取因果支配者，MUST NOT 用 HLC 反转。时钟偏移不能证明真实先后；领域在
无法建立因果闭包或安全决定 winner 时 MUST 保留 provisional／冲突副本并在补齐材料后重算。HLC MUST NOT 进入
授权决策、admission、finality，MUST NOT 决定共享协议状态的 winner，也 MUST NOT 替代同一 stream 的
`stream_position`。encrypted account data 服务端不参与明文 tie-break，只比较 `expected_server_revision`；CAS
冲突后由获准解密的客户端按领域规则合并并重新写入。read cursor 则先比较同一 stream 上的 `stream_position` 支配，只在互不支配时比较 HLC，
全等时再以 `device_id` 决胜；read receipt 与 Sidecar `source_hlc` 不得反向改变治理历史。

### 7.2 绝对时刻

Arkret 自有时刻使用 UTC 毫秒 spelling；时间只用于展示、过期与审计，不代替 stream position。

### 7.3 时间边界

外部协议时间表示只能在 adapter 边界保留；进入 Arkret typed object 后使用所属 schema 的固定格式。

## 8. Cursor

Cursor 是签发服务端可验证的不透明 continuation token。v1 core 只使用 stateful opaque handle 形态：wire body
是 `{v, purpose, issued_at, expires_at, h}`，`h` 由签发服务端解析成它绑定的
`(account_id, device_id, filter_digest, purpose, positions, target?, expiry)`——**句柄查表本身就是完整性检查**，
没有内联 MAC 或签名可验。字段 schema 与 TTL 硬上限的唯一 canonical 数值定义点是
[`cursor.schema.json`](../../artifacts/schemas/cursor.schema.json)，本节不重复数值。客户端不得解析 cursor 来
推导 position。Cursor 不是 authority、Commit 或 snapshot 的替代品。

**cursor 的适用面（normative）**：v1 只有两处用 cursor——account 聚合流的续传（`purpose=stream`）与列表分页，
外加写后读屏障（`purpose=barrier`）。**单条 stream 的扫描不用 cursor**：治理 Station 在每条 stream 上给出严格
+1 的 `stream_position`，位置本身就是完整续传凭据，`ak.self.committed_event.read.scan.v1` 与
`ak.peer.committed_event.read.scan.v1` 因此收 `after_position` / `before_position` 整数而不是 token，见
[`../sync/api-conventions.md` §7.2](../sync/api-conventions.md)。

### 8.3 Cursor 范围绑定

Cursor 必须绑定调用方（完整 `AccountId` 与 device）、purpose、operation 与 filter digest，不得跨调用方、
跨 operation、跨过滤条件或跨签发服务重放；任一项变化都要求新 cursor。

服务按 [`../sync/client-sync.md` §12.2](../sync/client-sync.md) 的唯一阶段顺序先校验 syntax/schema、TTL 与 context purpose，再核对 wire `expires_at`，再查本服务的 `h` 绑定并逐毫秒核对不可变时间；有效请求绑定后才分类撤销。未知句柄（包括新鲜的外站正常签发 token）、存储绑定过期或绑定不匹配 MUST 零状态推进返回 `cursor_integrity_invalid`；wire 过期使用 `cursor_expired`，已知有效绑定的明确撤销使用 `cursor_revoked`。不透明 wire 没有公开 issuer，接收站 MUST NOT 将未知外站句柄与未知篡改句柄分成不同错误，也不能信任 caller、私有辅助字段或 Account Station 来推断签发者。跨站恢复仍单独验收，见 client-sync §12.3.1。

**stream 绑定按面区分**：列表分页 cursor 绑定它那一个列表；account 聚合 cursor 绑定的是一**组**获准 stream 的
位置（`positions` 是复数），服务端把它解析成每条流各自的位置后逐流推进——这不构成跨流位置比较，也不得被
实现折叠成任何单一聚合位置。聚合 cursor 之所以必须保持不透明，理由不是"事件没有确定顺序"，而是：N 条独立
stream 没有可明文表达的标量位置；明文位置向量会让调用方从 gap 推断它看不见的 private stream
（[`../sync/client-sync.md` §4](../sync/client-sync.md)）；句柄还绑定 `filter_digest` 与 device，换了过滤条件
复用位置会静默漏事件。这三条都不随全序 commit 消失。

### 8.6 Resource selector 投影

Selector 先经闭合 grammar 解析，再由 typed reducer 映射到领域主键；不对外暴露 typed current result key。

## 9. Rank 与复合键

本节定义两件互不相关的编码：手动排序位置 rank（§9.1），以及 typed current 业务主键与复合键（§9.5）。

### 9.1 Rank 编码（normative）

列表排序 rank MUST 使用 [`schema-registry.md`](./schema-registry.md) 登记的 `ak.rank.lexofractional.v1`
profile，除非 Realm schema 显式声明其它 rank profile。rank 是 **producer 自己选定的排序令牌**，不是任何派生值：
它与 Event 的接纳位置、深度或因果关系无关，实现 MUST NOT 从 Commit 位置、`created_at` 或任何摘要推算 rank。

- 字符集固定为 ASCII `0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz`，按该字符集顺序比较。
- Rank MUST 是 1..128 字符的字符串，每个字符 MUST 来自上述字符集；超过 128 字符的 rank MUST 被拒绝。
- 排序 MUST 使用逐字符字典序；一个字符串是另一个的前缀时，较短者在前。
- `rank_between(left, right)` MUST 返回严格满足 `left < rank < right` 的 rank，或返回
  `rank_exhausted`（机读归属见 [`error-code-registry.json`](../../artifacts/registry/error-code-registry.json)）。
  `left` 或 `right` MAY 为空，表示容器开头或结尾的哨兵边界。
- midpoint 算法 MUST 有界，不得在无间隙边界上无限循环。参考伪代码：

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

`rank_between("", "0")` MUST 返回 `rank_exhausted`：start sentinel 与最小 rank `"0"` 之间不存在合法 rank。
遇到 `rank_exhausted` 时 MUST NOT 生成非法 rank；写入方须先用该容器已登记的单项排序 Event（如 `ak.strand.reorder`、`ak.pin.reorder`）为相邻条目重新分配 rank，再重试插入。

- **同 rank 的展示 tie-break（normative）**：同一容器内 rank 完全相同的条目 MUST 按**该条目所标识对象的
  typed id** 的 canonical bytewise 升序继续排序。每个承载 rank 的 payload 由其自身合同指明这个 typed id，
  封闭对应关系如下：

  | 承载 rank 的 payload | 排序条目所标识的对象 | tie-break 使用的 typed id |
  | --- | --- | --- |
  | `ak.pin.add` / `ak.pin.reorder` | 被 pin 的目标对象 | `payload.target_ref` |
  | `ak.relation.create` | 物化后的 Relation | Relation 的 `id`（由 create Event 的 `event_id` 重类型派生） |
  | `ak.strand.move` / `ak.strand.reorder` | 被移动的 Strand | `payload.strand_id` |

  该 tie-break **只用于展示序**，MUST NOT 进入 canonical state，也 MUST NOT 参与授权判断。相同 rank 不构成
  互斥冲突，也不需要人工修复。新增承载 rank 的 payload 时 MUST 同批在上表登记它的 tie-break typed id，
  未登记即该容器的同 rank 顺序未定义。
- **并发同 gap 插入抖动（normative）**：两个客户端在同一 `(left, right)` gap 并发调用 `rank_between` 会算出
  相同 rank，落到上一条的 tie-break，体验上表现为顺序抖动。为降低碰撞概率，`rank_between` 在该 gap 仍有剩余
  编码空间时 SHOULD 在所选 rank 尾部追加一段短随机 jitter 尾缀（合法 base62 字符，且不破坏
  `left < rank < right` 与 1..128 长度上限）。jitter 是最终 rank 字符串的一部分，MUST 进入 canonical payload
  bytes 与 event digest，但它不是独立字段，也不改变字典序比较规则。jitter 只降低碰撞概率，不替代 `object_id`
  tie-break；编码空间耗尽时 MUST 按上文 `rank_exhausted` 规则处理，MUST NOT 用 jitter 绕过 128 字符上限。
- **CAS 字段**：`expected_rank`、`expected_position.rank` 等前置条件与当前 rank 做**逐字节相等**比较；它们是
  可选的显式 compare-and-set，缺席即不做并发保护，实现 MUST NOT 把缺席补成隐式 CAS。

### 9.5 Collection 与复合键

Typed current 的业务主键只由对应 reducer schema 明确定义。wire 与 reducer 上不存在通用 typed current result
subject、通用复合键 hash 或 caller 选择的组件名；出现这三者中的任意一个 MUST `schema_violation`。

#### 9.5.1 通用规则

Typed reducer 直接读取 kind 对应的封闭 Event payload 和 envelope；subject 来源由该 kind 的 payload schema 明确定义。

subject 的 registry 字段来源必须显式命名：payload 来源写成 `payload.<具名路径>`，Event Envelope 来源写成
`envelope.<字段>`；裸字段名与"先查 payload、再查 envelope"的 fallback 求值一律未定义并 MUST
`schema_violation`。
v1 的 envelope 来源白名单只包含 `envelope.actor_id` 一项；`envelope.realm_id`、`envelope.executed_by` 及其它未登记字段均不得用于 subject。

需要多字段业务键时，schema 必须列出固定字段、顺序与正规化方法；实现按 typed reducer 构造数据库唯一
键。该数据库键不是 wire ID，也不得作为跨实现授权材料。

##### 9.5.2 复合键编码

复合业务键的成员、顺序和正规化由具体 schema 封闭定义，不使用通用 typed current result subject hash。
registry 中的 `result_selector.kind="composite"` 只是对应 `result_family` 的 **family-specific closed ordered
descriptor**：它声明 reducer 从哪些 schema-validated 字段、按什么顺序和正规化取得数据库 row locator 的输入，
不把任意 component 数组开放给 caller。

需要跨 producer／reader 复算 opaque current-row locator 的 family，MUST 先在
`event-kind-registry.json#typed_current_key_derivations` 登记唯一 `derivation_id`、typed 参数、固定 component
来源／顺序／正规化、family domain、family-specific API 名与 KAT。已登记 profile 的唯一算法是：

```text
preimage = UTF8(family_domain) || 0x0A || RFC8785_JCS(normalized_components)
locator  = base64url_nopad(SHA-256(preimage))
```

generated SDK API MUST 在求 hash 前按 typed signature 拒绝参数类型错误、缺项和额外 component；不得暴露接受
`&[T]`、`Vec<Value>` 或 caller-selected JSON 的 `composite_subject`／等价入口。重排 component 或换用另一
family domain 必须得到不同输出。派生结果只是不透明数据库 current-row locator，不是 wire typed ID、Event／
RealmCommit 签名 basis、revision、tenure、proof、capability 或 governance authority；current governing Station 的
accepted RealmCommit 与权限门仍是唯一 authority。

当前登记的 closed API 是：

| result family | family-specific typed API | 固定参数顺序 |
| --- | --- | --- |
| `member_state` | `derive_member_state_current_key` | `(member_actor_id: ActorId)` |
| `agent_status` | `derive_agent_status_current_key` | `(agent_actor_id: ActorId)` |
| `agent_key` | `derive_agent_key_current_key` | `(agent_id: DidCoreId, key_id: AgentKeyId)` |
| `key_backup_active_series` | `derive_key_backup_active_series_current_key` | `(actor_id: ActorId, backup_kind: BackupKind)` |

未登记 family 不得推断或生成兼容 API。特别地，`call_mute_override` 保留的 selector 只有
`[payload.call_id]`，不能承载多 leg；v1 拒绝包含 `mute_override` 的写入。旧实现的 per-leg
`[call_id, actor_id, device_id]` 键不对应该 family，必须继续 fail closed，不得借本节生成第五个兼容 derivation。

## 10. 大小与拒绝

实现必须在分配大对象、解析递归结构或验证昂贵证明之前执行 transport 与 canonical byte 上限。非法编码、
未知 suite、ID 重算不符、proof projection 不完整均 fail closed，并且不得创建 Event、Commit、typed current
或 outbox 的部分写入。

### 10.1 JSON 字节限制

在进入验签、解密或 reducer 前执行登记的 canonical byte 上限。

### 10.2 集合限制

数组、map、分页和 batch 上限以 schema 与 scalability registry 为准，超限整体拒绝。
