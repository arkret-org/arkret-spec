---
title: Encoding, IDs, Hashes, and Signatures
status: candidate
normative: true
stability: v1
updated: 2026-09-16
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

## 3. Digest suite

Realm genesis 固定 Realm 的 active digest suite。内容摘要写作 registry 定义的 suite-tagged digest；不同
suite 的摘要不能比较为相等。Event、RealmCommit、handoff 与 snapshot 的 ID 都从各自 canonical body
计算，验证方 MUST 从 ID 恢复 suite 并重算。

### 3.3 State Root 与 Commit Hash 编码

v1 不再定义通用 typed current result state root 或 RealmCommit hash。每条 Realm、Circle 或 Sidecar stream 通过
`RealmCommit.previous_commit_ref` 和 `stream_position` 独立链接。Commit ID 覆盖完整 Commit body（不含其
自身 ID），因此同时承诺 Event ID、stream、位置、前驱、authority generation 与治理 Station proof。

跨 stream 不存在共享 root、共享 position 或隐含原子提交。需要跨 stream 协调的业务使用已提交引用与
显式补偿 Event。

## 4. Typed ID 与引用

Typed ID 的前缀、payload pattern、是否内容寻址只由
[`id-kind-registry.json`](../../artifacts/registry/id-kind-registry.json)决定。接收方必须拒绝未登记前缀、非法
payload、错误 suite 和大小写变体。

`ak:event:`、`ak:realm_commit:`、`ak:realm_authority_handoff:` 与 `ak:realm_snapshot:` 是内容寻址对象。
对象自身主键使用 `*_id`；指向既有不可变对象使用 `*_ref`。同一对象不得同时携内容寻址引用及可从该引用
恢复的 sibling digest。

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

## 7. 时间

`created_at` 是 producer 声明的审计/展示时间，不提供排序或 finality。Commit 的顺序只来自同一 stream 的
`stream_position` 与 `previous_commit_ref`。未来偏移与过期限制只用于 admission/DoS 防护，不得改变历史中
既有 Commit 的顺序。

## 8. Cursor

Cursor 是服务端签名或认证的不透明 continuation token。它必须绑定 operation、调用方、授权范围、单一
stream、方向、page limit 与到期时间。客户端不得解析 cursor 来推导 position，也不得把一个 stream 的
cursor 用于另一个 stream。Cursor 不是 authority、Commit 或 snapshot 的替代品。

## 9. Collection 与复合键

Typed current 的业务主键由对应 reducer schema 明确定义。v1 不再提供通用 typed current result subject、通用复合键 hash
或 caller 选择的组件名。

### 9.5.1 通用规则

Typed reducer 直接读取 kind 对应的封闭 Event payload 和 envelope；subject 来源由该 kind 的 payload schema 明确定义。

subject 的 registry 字段来源必须显式命名：payload 来源写成 `payload.<具名路径>`，Event Envelope 来源写成
`envelope.<字段>`；裸字段名与"先查 payload、再查 envelope"的 fallback 求值一律未定义并 MUST
`schema_violation`。
v1 的 envelope 来源白名单只包含 `envelope.actor_id` 一项；`envelope.realm_id`、`envelope.executed_by` 及其它未登记字段均不得用于 subject。

需要多字段业务键时，schema 必须列出固定字段、顺序与正规化方法；实现按 typed reducer 构造数据库唯一
键。该数据库键不是 wire ID，也不得作为跨实现授权材料。

## 10. 大小与拒绝

实现必须在分配大对象、解析递归结构或验证昂贵证明之前执行 transport 与 canonical byte 上限。非法编码、
未知 suite、ID 重算不符、proof projection 不完整均 fail closed，并且不得创建 Event、Commit、typed current
或 outbox 的部分写入。

## 11. 编码细则索引

下列小节汇总固定编码、typed ID、逐 stream 链接和 detached signature 规则。

### 2.2 String profile 与 Unicode

字符串继续由 `string-profile-registry.json` 中的领域 profile 约束；对象签名和 ID 计算使用通过 schema 验证的原值。

#### 2.2.1 网络标识与 IDNA

DID、URI、域名、email 和电话号码仍使用各自的外部 profile，不得使用通用大小写折叠改写签名字节。

### 3.1 内容寻址预映射

先验证 closed schema，再移除对象自身 ID 和签名字段，最后对 canonical JSON 求摘要。

预映射内**不得承诺 Event 标识**：自身标识与同一原子单元内的兄弟标识都会让摘要的原像包含该摘要自身的函数，按构造不可满足。唯一允许的两类例外是 envelope omission 与 forward declaration，且必须逐条登记在
[`preimage-identity-exemption-registry.json`](../../artifacts/registry/preimage-identity-exemption-registry.json)。**封闭例外清单**：下表是该 registry 的封闭列表投影，两侧 MUST 同批更新：

| exemption_id | kind | 说明 |
| --- | --- | --- |
| `ak.exemption.preimage_identity.realm_genesis.v1` | envelope_omission | `ak.realm.create` 的 envelope `realm_id`、`scope_ref.realm_id` 与 create payload object id 都不进入原像；接收方从已接受的 `event_id` 正向派生 `realm_id`。 |
| `ak.exemption.preimage_identity.agent_provision_principal_control_realm_id.v1` | forward_declaration | `ak.agent.provision` 先声明 `principal_control_realm_id = retype(genesis event_id)`；genesis 原像不含 provision 的任何标识、引用或摘要，依赖只朝一个方向。 |

### 3.2 Suite-tagged digest

具体 suite 由 typed ID 或所属 Realm genesis 唯一决定；实现不得尝试多种 suite 后择一通过。

### 4.0 Typed ID 通用规则

Typed ID 必须通过 `id-kind-registry.json` 登记的唯一 grammar 和 authority 分类。

#### 4.0.1 引用验证

`*_ref` 必须先验证类型前缀，再在调用者获权的 stream 中解析，不得跨 Circle/Sidecar 探测。

### 4.1 生产者分配的 ID

生产者分配 ID 必须在对应 producer proof 的签名投影内，治理 Station 不得代换。

### 4.2 服务分配的 ID

服务分配 ID 仅用于 registry 明确指定的非内容寻址对象，并受幂等索引约束。

#### 6.0.1 Detached proof 投影

投影必须从已验证 typed object 构造，不得从宽松 JSON map 或本地默认值构造。

### 6.1 领域分离

每个 proof context 使用 registry 登记的唯一 domain string；Event、RealmCommit、handoff 和 snapshot 不得共用 context。

### 7.2 绝对时刻

Arkret 自有时刻使用 UTC 毫秒 spelling；时间只用于展示、过期与审计，不代替 stream position。

### 7.3 时间边界

外部协议时间表示只能在 adapter 边界保留；进入 Arkret typed object 后使用所属 schema 的固定格式。

### 8.3 Cursor 范围绑定

Cursor 必须绑定单个 Realm/Circle/Sidecar stream 与调用者授权范围，不得跨 stream 重放。

### 8.6 Resource selector 投影

Selector 先经闭合 grammar 解析，再由 typed reducer 映射到领域主键；不对外暴露 typed current result key。

#### 9.5.2 复合键编码

复合业务键的成员、顺序和正规化由具体 schema 封闭定义，不使用通用 typed current result subject hash。

### 10.1 JSON 字节限制

在进入验签、解密或 reducer 前执行登记的 canonical byte 上限。

### 10.2 集合限制

数组、map、分页和 batch 上限以 schema 与 scalability registry 为准，超限整体拒绝。
