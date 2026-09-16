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

## 2. 业务引用

`refs[]` 只表达不可由 payload 更清楚表达的业务关系。`role=authorized_by` 的 `id` 必须是
`ak:grant:`；其它已登记 role 使用 immutable Event reference。排序、可见性和状态 head 不得编码为
`refs[]`。

Poll 改票使用 payload 中的 typed `poll_response_heads[]`，每项同时指明原 poll Event 与被覆盖的 response
Event；不得恢复通用 `domain_refs`。

## 3. Typed reducer

每个 Event kind 选择一个固定 typed reducer。治理 Station 按该 Event 所属 stream 的
`RealmCommit.stream_position` 执行；Realm、不同 Circle、不同 Sidecar 之间没有总序。

需要 compare-and-set 的领域在自身 payload 中定义 `expected_revision`，该值引用该 typed current row 最后
一次接受它的 Commit。协议不提供 typed current result key、通用 patch DSL、CRDT/deterministic projection rank 或 caller 指定的 state root。

跨 stream 工作流必须使用已提交引用、幂等 saga 和明确补偿 Event，不得因为同一部署共用数据库就暴露
跨 stream 原子性。

## 4. 验证边界

治理 Station 验证 Event ID、producer proof、current authorization、typed payload、引用可见性和领域不变量；
成功后原子写入 Event、RealmCommit、typed current 与 outbox。消费方验证 authority chain、逐 stream
predecessor/position、Commit signature、Event ID 和 producer proof。消费方只能证明自己获准读取的 stream
连续，不能从 Realm stream 推断隐藏 Circle 或 Sidecar 的活动。


#### 4.2.4 Redactable content slots (normative)

- Message: `content`、`encrypted_content`
- Strand: `content`、`encrypted_content`、`tracks.synthesis.content`、`tracks.synthesis.encrypted_content`
- Morph: `content`、`encrypted_content`

普通更新只能用 `set` 写入空内容；清除这些 slot 必须走登记的 terminal redaction Event。

#### 4.2.5 Typed-reducer managed paths (normative)

Generic patch path MUST NOT 操作 reducer-managed 字段: `id`、`schema`、`realm_id`、`created_by`、`created_at`、`updated_by`、`updated_at`、`state`、`state_changed_at` (完整的按对象封闭集由 `registry/reducer-managed-path-registry.json` 给出)。这些字段是 typed reducer 的固定输出，不是 typed current result 投影。

## 5. 事件应用

事件只能由当前治理 Station 在其所属的单一 stream 中接纳；领域 reducer 在 RealmCommit 持久事务中执行。

### 5.1 生命周期

`queued` 只是 Account Station 的本地持久态；只有有效 RealmCommit 能表示 `committed`。被拒绝或可重试请求不占 stream position。

## 6. 稳定引用锚点

下列锚点保留了其他领域页的章节号，内容全部按本页的 authority-commit 语义解释。

### 2.2 Event 提交边界

SDK 必须在签名和发送前构造 immutable、schema-valid Event；服务不得回填 producer 字段。

#### 2.4.1 Signer regime

签名者类型由 Event kind、actor/executor 和已提交的委托事实唯一分派，零匹配或多匹配都 fail closed。

#### 2.4.2 Typed reducer contract

每个 durable Event kind 绑定一个封闭 typed reducer；producer 不能选择 reducer、state key 或通用 operation。

### 2.6 关系与业务前驱

业务关系使用 typed payload 或封闭 `refs` role；排序前驱只使用 RealmCommit。

### 2.7 内容对象

Message、Strand、Calendar 等对象的 create/update 字段由各自 payload schema 定义，领域 revision 来自最后影响该行的 Commit。

### 2.8 加密 payload

加密内容仍是标准 Event payload；MLS epoch、group-state ref 和 key-access revision 必须等于接纳位置的 current 值。

### 3.1 引用可见性

治理 Station 只解析 caller 在目标 stream 获权的引用；未授权隐藏 scope 不能通过错误差异枚举。

### 3.2 可变对象修订

需要防覆盖的 payload 携带领域专属 `expected_revision`；比较值是该 typed row 的最后 Commit 修订。

#### 4.3.1 Patch 冲突

Patch 不使用 causal rank；默认按同 stream Commit 顺序应用，并在具体 payload 要求时使用 `expected_revision`。
