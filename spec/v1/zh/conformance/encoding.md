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

## 3. Digest suite

Realm genesis 固定 Realm 的 active digest suite。内容摘要写作 registry 定义的 suite-tagged digest；不同
suite 的摘要不能比较为相等。Event、RealmCommit、handoff 与 snapshot 的 ID 都从各自 canonical body
计算，验证方 MUST 从 ID 恢复 suite 并重算。

### 3.3 State Root 与 Commit Hash 编码

v1 不再定义通用 Cell state root 或 Seal hash。每条 Realm、Circle 或 Sidecar stream 通过
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

Typed current 的业务主键由对应 reducer schema 明确定义。v1 不再提供通用 Cell subject、通用复合键 hash
或 caller 选择的组件名。

### 9.5.1 通用规则

旧 Cell subject 的 envelope 来源白名单已随 Cell 模型退役；typed reducer 直接读取其 kind 对应的封闭 Event payload 和 envelope，不再维护 `envelope.actor_id` / `envelope.event_id` 之类的通用 subject 路径集合。

需要多字段业务键时，schema 必须列出固定字段、顺序与正规化方法；实现按 typed reducer 构造数据库唯一
键。该数据库键不是 wire ID，也不得作为跨实现授权材料。

## 10. 大小与拒绝

实现必须在分配大对象、解析递归结构或验证昂贵证明之前执行 transport 与 canonical byte 上限。非法编码、
未知 suite、ID 重算不符、proof projection 不完整均 fail closed，并且不得创建 Event、Commit、typed current
或 outbox 的部分写入。

## 11. 稳定引用锚点

本节保留其他领域规范已发布的章节号链接。这些锚点都引用本页上述固定编码、typed ID、逐 stream 链接和
detached signature 规则，不恢复已退役的 HLC、Cell root 或 Seal transcript。

### 2.2 String profile 与 Unicode

字符串继续由 `string-profile-registry.json` 中的领域 profile 约束；对象签名和 ID 计算使用通过 schema 验证的原值。

#### 2.2.1 网络标识与 IDNA

DID、URI、域名、email 和电话号码仍使用各自的外部 profile，不得使用通用大小写折叠改写签名字节。

### 3.1 内容寻址预映射

先验证 closed schema，再移除对象自身 ID 和签名字段，最后对 canonical JSON 求摘要。

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

Selector 先经闭合 grammar 解析，再由 typed reducer 映射到领域主键；不对外暴露 Cell key。

#### 9.5.2 复合键编码

复合业务键的成员、顺序和正规化由具体 schema 封闭定义，不使用通用 Cell subject hash。

### 10.1 JSON 字节限制

在进入验签、解密或 reducer 前执行登记的 canonical byte 上限。

### 10.2 集合限制

数组、map、分页和 batch 上限以 schema 与 scalability registry 为准，超限整体拒绝。
