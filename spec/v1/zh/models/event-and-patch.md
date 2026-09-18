---
title: Event and Typed State Transitions
status: candidate
normative: true
stability: v1
updated: 2026-09-16
see_also:
  - ../conformance/normative-language.md
  - ../sync/authority-commit-log.md
---

# Event 与 typed 状态变更

规范关键字按[规范语言](../conformance/normative-language.md)解释。

**章节编号是稳定引用身份（normative）**：本页的编号小节都是正文，各自承载自己的完整义务。
编号是供其它领域页稳定引用的身份，不表达阅读顺序，MUST NOT 被理解为「只保留号、内容在别处」的占位别名。
引用本页某节即引用该节正文。

## 1. Event 的职责

Event 是 producer 对业务意图的签名，不是排序记录、状态证明或治理方回执。共享持久 Event 只有在当前治理
Station 签发对应 `RealmCommit` 后才进入共享历史。

Event Envelope 的顶层字段为：

| 字段 | 必需 | 语义 |
| --- | --- | --- |
| `event_id` | 是 | canonical Event bytes 的 typed content address |
| `kind` | 是 | 已登记的 Event kind |
| `realm_id` | 通常 | 所属 Realm；`ak.realm.create` 使用既有派生例外 |
| `scope_ref` | 是 | Realm、Circle 或 Sidecar effective scope |
| `actor_id` | 是 | 业务事实归属主体 |
| `executed_by` | 否 | 委托执行者；出现时同时要求 `authorization_ref` |
| `authorization_ref` | 否 | Grant、委托 Event、DID delegation 或封闭 profile authority |
| `applet_id` | 否 | Applet provenance |
| `external_ref` | 否 | 外部系统幂等/provenance 引用 |
| `created_at` | 是 | producer 声明的展示时间，不决定提交顺序 |
| `refs` | 否 | 封闭 role 的业务引用；`authorized_by` 只接受 `GrantId` |
| `payload` | 是 | 由 kind 选择的 closed typed payload |
| `proofs` | 是 | 唯一 producer proof |

Event 不携带 `producer_revision`、`hlc`、`domain_refs`、通用 `preconditions`、`commit_authorization_state`、
`commit_base`、`expected_revision`、`requirements` 或 `unsigned`。Event 也不携带前一个 Event/Commit；
`previous_commit_ref` 只存在于治理 Station 在接纳时创建的 `RealmCommit`。

## 2. Event 提交与业务引用

`refs[]` 只表达不可由 payload 更清楚表达的业务关系。`role=authorized_by` 的 `id` 必须是
`ak:grant:`；其它已登记 role 使用 immutable Event reference。排序、可见性和状态 head 不得编码为
`refs[]`。

Poll 改票使用 payload 中的 typed `poll_response_heads[]`，每项同时指明原 poll Event 与被覆盖的 response
Event；不得恢复通用 `domain_refs`。

### 2.2 Event 提交边界

SDK 必须在签名和发送前构造 immutable、schema-valid Event；服务不得回填 producer 字段。

#### 2.4.1 Signer regime

签名者类型由 Event kind、actor/executor 和已提交的委托事实唯一分派，零匹配或多匹配都 fail closed。

#### 2.4.2 Typed reducer contract

每个 durable Event kind 绑定一个封闭 typed reducer；producer 不能选择 reducer、state key 或通用 operation。

一条 Event 的 registered writes 按 registry 顺序编号，`write_index` 从 0 起。tagged-set 元素的稳定 tag 是**canonical Event dot** `<event_id>:<write_index>`，MUST NOT 退化为裸 `event_id`：同一条 Event 的多个 write 必须可分辨。

### 2.6 关系与业务前驱

业务关系使用 typed payload 或封闭 `refs` role；排序前驱只使用 RealmCommit。

### 2.7 内容对象

Message、Strand、Calendar 等对象的 create/update 字段由各自 payload schema 定义，领域 revision 来自最后影响该行的 Commit。

### 2.8 加密 payload

加密内容仍是标准 Event payload；MLS epoch、group-state ref 和 key-access revision 必须等于接纳位置的 current 值。

## 3. Typed reducer

每个 Event kind 选择一个固定 typed reducer。治理 Station 按该 Event 所属 stream 的
`RealmCommit.stream_position` 执行；Realm、不同 Circle、不同 Sidecar 之间没有总序。

需要 compare-and-set 的领域在自身 payload 中定义 `expected_revision`，该值引用该 typed current row 最后
一次接受它的 Commit。协议不提供 typed current result key、通用 patch DSL、CRDT/deterministic projection rank 或 caller 指定的 state root。

跨 stream 工作流必须使用已提交引用、幂等 saga 和明确补偿 Event，不得因为同一部署共用数据库就暴露
跨 stream 原子性。

### 3.1 引用可见性

治理 Station 只解析 caller 在目标 stream 获权的引用；未授权隐藏 scope 不能通过错误差异枚举。

### 3.2 可变对象修订

需要防覆盖的 payload 携带领域专属 `expected_revision`；比较值是该 typed row 的最后 Commit 修订。

## 4. 验证边界

治理 Station 验证 Event ID、producer proof、current authorization、typed payload、引用可见性和领域不变量；
成功后原子写入 Event、RealmCommit、typed current 与 outbox。消费方验证 authority chain、逐 stream
predecessor/position、Commit signature、Event ID 和 producer proof。消费方只能证明自己获准读取的 stream
连续，不能从 Realm stream 推断隐藏 Circle 或 Sidecar 的活动。


### 4.2 patch path 规则

#### 4.2.1 Grammar（normative）

patch path 严格遵循下面 ABNF：

```text
path           = segment *( "." segment )
segment        = identifier
identifier     = ALPHA-LOWER *( ALPHA-LOWER / DIGIT / "_" )
ALPHA-LOWER    = %x61-7A                       ; a-z
```

具体约束：

- `identifier` MUST 匹配正则 `^[a-z][a-z0-9_]{0,63}$`（snake_case，首字符必须小写字母，长度 ≤ 64）；
- v1 只接受 snake_case `identifier` segment；quoted identifier、selector segment
  （`field[key=value]`）与数字数组下标都不属于 v1 grammar，MUST 以 `schema_violation`、
  `reason_code=patch_path_invalid` 拒绝；
- path 最多 16 段，UTF-8 编码后最多 1024 bytes；
- [`patch.schema.json`](../../artifacts/schemas/patch.schema.json) 的
  `propertyNames.pattern` 与 `propertyNames.maxLength` 是上述 grammar、16 段上限与
  1024-byte 上限的 canonical 机读投影；schema 与本节 MUST 同批更新。

#### 4.2.2 Parser 责任

reducer 与 SDK 实现 MUST 使用确定性 parser。遇到任何不匹配 §4.2.1 grammar 的 path、UTF-8
编码后超过 1024 bytes 的 path 或超过 16 段的 path 时，MUST 返回 `schema_violation`、
`reason_code=patch_path_invalid`。Parser MUST NOT 走 fallback 路径；空 segment、非法字符、
selector 形态与数组下标形态都不得在跳过无效部分后继续解析。

#### 4.2.3 无 stable-key 列表元素

v1 的 patch path 只寻址对象成员。要更新没有 stable key 的列表元素，MUST 把该对象重建为
map（key 即成员名，例如 Strand `tracks`）、使用 profile 注册的 move / update Event，或用明确的
API 约束字段表示更新目标；不得把数字数组下标或 selector segment 写入 path。

#### 4.2.4 Redactable content slots (normative)

- Message: `content`、`encrypted_content`
- Strand: `content`、`encrypted_content`、`tracks.synthesis.content`、`tracks.synthesis.encrypted_content`
- Morph: `content`、`encrypted_content`

上述逐对象清单的机读投影是
[`redactable-field-registry.json`](../../artifacts/registry/redactable-field-registry.json)；本节与该 registry
MUST 同批更新，reducer、SDK 与 conformance MUST 从 registry 取值，MUST NOT 各自解析本节散文。

普通更新只能用 `set` 写入空内容；清除这些 slot 必须走登记的 terminal redaction Event。理由是**槽存在性
语义**：每个内容槽是明文 / 密文二选一的一对字段，其在物化对象上的缺席只允许表达两件事——从未撰写，或
已按 redaction policy 清除。普通 `ak.<kind>.update` MUST NOT 制造第三种缺席来源。

**Event-targeted redaction 不驱动对象 state（normative）**：cross-object `ak.redaction` 的 `target_ref` 是
唯一目标载体，其词法空间同时覆盖对象 typed id 与 `ak:event:` 目标；对 `id_source=event_derived` 的对象，
同一个 33-octet token 有 `ak:event:<T>` 与 `ak:<对象种类>:<T>` 两种合法拼写。两者是**两件不同的断言**：

- `target_ref` 为 `ak:event:` 形态时，语义仅是按 `preserve[]` 对该 Event 自身做字段级裁剪。它 MUST NOT
  改变任何对象的 `state`，**包括由被指向的 create Event 铸出的 event-derived 对象**。
- 对象进入 `state=redacted` 只能由 `ak:<对象种类>:` 形态的 `target_ref` 驱动。Message 仍然只走专属
  `ak.message.redact`，cross-object `ak.redaction` 的 schema 已机械排除 `ak:message:` 目标。

两种拼写落进 `object_redaction` 家族的**两个**独立 typed current result：它们互不影响、永不合并，reducer
MUST NOT 把 `ak:event:` 拼写 canonicalize 成派生对象的 typed id。因此回答"这条内容还在不在"必须同时读两处
投影：对象拼写决定对象 `state`，event 拼写决定该 Event 的字段级裁剪；UI 与审计视图 MUST 合并两者，不得只
查其一。判据由 `ak.vector.redaction.event_target_does_not_drive_object_state.v1` 固化。

#### 4.2.5 Typed-reducer managed paths (normative)

Generic patch path MUST NOT 操作 reducer-managed 字段: `id`、`schema`、`realm_id`、`created_by`、`created_at`、`updated_by`、`updated_at`、`state`、`state_changed_at` (完整的按对象封闭集由 `registry/reducer-managed-path-registry.json` 给出)。这些字段是 typed reducer 的固定输出，不是 typed current result 投影。

#### 4.3.1 Patch 冲突

Patch 不使用 causal rank；默认按同 stream Commit 顺序应用，并在具体 payload 要求时使用 `expected_revision`。

**原子性与声明的 pre-state（normative）**：同一个 `payload.patch` map 中的所有 path 变更属于该 Event 的
**单次原子写入**。reducer MUST 先取得该 Event 声明的 pre-state，再验证全部 path grammar、schema transition、
capability field constraint、redactable slot 限制与 reducer-managed path 限制，最后整体应用。任一检查失败时
整个 patch MUST fail closed，MUST NOT 部分应用已经通过的 path。

pre-state 的求值必须唯一且有界：携带 `expected_revision` 的 payload 以该 typed row 的最后 Commit 修订为准，
不一致时以 `failed_precondition` 拒绝；pre-state 无法唯一绑定——目标行不存在、解析出多于一个候选，或实现
只能依据到达顺序、本地 current 快照、墙钟或 HLC 猜测——时 MUST 以 `schema_violation`、
`reason_code=reducer_projection_failed` 拒绝，MUST NOT 落在一个未绑定的基线上应用。

同时写入父子路径、同一路径重复写入，或一条操作会改变另一条操作的目标解析结果时，producer MUST 拆分为
多个语义边界明确的 Event；receiver 无法按 canonical path order 得到唯一结果时 MUST `schema_violation`，
`reason="patch_atomic_conflict"`。canonical path order 只用于签名与诊断，MUST NOT 被实现当作"先应用 A 再
应用 B"的业务语义逃逸路径。

**与 redactable slot / reducer-managed path 的交互（normative）**：patch path 命中 §4.2.4 登记的内容槽且
`$op="unset"` 时 MUST 拒绝为 `schema_violation`、`reason=patch_unset_redactable_field`；同一槽上的
`$op="set"`（含空正文）是普通编辑，MUST 被接受；`metadata`、`metadata.title`、`metadata.summary` 与
`metadata.fields.*` 不是内容槽，其上的 `$op="unset"` MUST 被接受。patch path MUST NOT 指向目标对象 kind 的
reducer-managed 字段；逐对象封闭禁集、其通用最小集与唯一一条具名 View `state` 例外，都只从
[`reducer-managed-path-registry.json`](../../artifacts/registry/reducer-managed-path-registry.json) 读取，
MUST NOT 从散文重新推导。

## 5. 事件应用

事件只能由当前治理 Station 在其所属的单一 stream 中接纳；领域 reducer 在 RealmCommit 持久事务中执行。

### 5.1 生命周期

`queued` 只是 Account Station 的本地持久态；只有有效 RealmCommit 能表示 `committed`。被拒绝或可重试请求不占 stream position。
