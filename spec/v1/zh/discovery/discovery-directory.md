---
title: Directory Public Realm Metadata
status: candidate
normative: true
stability: v1
updated: 2026-09-22
---

# Directory：公开 Realm metadata 只读索引

本文的规范关键词按 [`../conformance/normative-language.md`](../conformance/normative-language.md) 解释。

机器可执行闭包由 `ak.vector.directory.public_realm_search.v1` 与
`ak.vector.directory.ttl_expiry_removal.v1` 覆盖。

## 1. 产品边界（normative）

Directory v1 是可选、只读、非权威的公开 Realm metadata 索引。current-v1 唯一 bundle 是
`ak.operation_bundle.directory_service.public_read.v1`，恰含 describe、search_realms、resolve_realm 三项读取。
current-v1 不登记 announce、withdraw、push、pull、callback 或其它 ingest operation，也不登记 Directory governance proof。
`ak.operation_bundle.directory_service.http_core.v1` 已删除；实现不得继续广告或挂载旧写路径。

Directory 不保存或提供 Realm Event、RealmCommit、stream、成员、权限、join／invite 状态、历史、治理链、source ref、
authority proof、Organization、Actor、User、Applet、Handle、restricted discovery、private-contact discovery 或 PSI。
查询结果只是 locator hint，不得成为 membership、join、history、capability、认证或 current-authority evidence；使用方必须向
目标 Realm 的 current governance Station 重新验证。

## 2. 可索引条件（normative）

只允许返回通过部署私有维护流程进入索引、仍在有效期内且标记为 public 的闭合 `PublicRealmMetadata`。该维护流程不属于
Arkret v1 interoperability surface，不得通过 ServiceDescribe、SDK 或私有 HTTP alias 冒充协议写入能力。未按 current-v1
规则重新确认的旧行必须隐藏；空索引返回空结果或不透明 `not_found`。

`listed`、`restricted`、`unlisted`、`invite_only`、`secret`、过期、隐藏与不存在必须同形处理；已知 RealmId 也不能绕过
该边界。Directory 不得自动续期条目。未来若要恢复跨服务写入，必须先登记新的完整 current-governance／opt-in 证据合同，
不得复活已删除的旧 DTO、旧 announce ID namespace、detached proof、source callback 或 exact resolve 回源。

### 2.1 只读来源边界

部署私有维护流程不得被协议客户端调用，也不得改变三项读取的 wire shape。

## 3. 写入（normative）

current-v1 没有 Directory 写 operation。任何旧 announce／withdraw 请求必须按未知或 unsupported operation fail closed，
且零索引变化；不得保留兼容 alias、双读或双写。

### 3.2 非公开状态

除 public 外的 discoverability 状态均不得进入 Directory 查询结果；已知 RealmId 也不能绕过该边界。

## 4. 查询（normative）

公开查询只有 `search_realms` 与 `resolve_realm`。每条 `PublicRealmDirectoryEntry` 恰好包含：

- `realm_id`；
- 闭合 `public_metadata`；
- Directory-local `indexed_at` 与 `expires_at`。

`public_metadata` 的 locator 即使存在也只是一条非权威联系提示。响应禁止携带 source refs、Event、RealmCommit、
authority proof、成员数、成员身份、role、capability、join rule、history policy、restricted claim 或任何后续业务材料。
隐藏、过期与不存在必须具有相同错误代码、字段集合和 timing equivalence class。

## 5. 删除的旧面（normative）

`ak.find.directory.command.announce.v1`、`ak.find.directory.command.withdraw.v1`、`DirectoryAnnounceRequestBody`、
`DirectoryWithdrawRequestBody`、`DirectoryGovernanceProof` 与旧 announce ID namespace 均不属于 current-v1。旧请求必须按未知或
unsupported operation fail closed，且零索引变化；不得保留兼容 alias、双读或双写。

## 6. 旧私有发现入口

current-v1 不提供私有发现协议。

### 6.2 旧私有发现入口

private-contact discovery 与 PSI 不属于 current-v1。

### 7.3 Locator

locator 只能位于闭合 `public_metadata`，且不证明 current authority。

### 8.10 防枚举

隐藏、过期、未确认与不存在必须保持同形。

## 9. 历史对象发现面

Directory v1 不提供 Handle、Organization、Actor、User 或 Applet 查询。

### 9.1 其它 identity 对象

其它 identity 对象同样不属于 Directory surface。

## 10. 验证矩阵

conformance 必须覆盖：只广告三读 bundle；旧写 operation 不可发现且零写入；只返回闭合 public metadata；隐藏、过期、
未确认与不存在同形；查询结果夹带 Event／Commit／authority／membership／join／history 信息时整份拒绝；过期条目不得继续
回答。Directory 查询结果被尝试用作 authorization 或 current-authority evidence 时，消费方必须拒绝。

## 11. 安全边界

Directory 不是治理权威。删除写面是 current-v1 的最终裁决，不是等待实现补齐的临时 profile；若未来产品重新需要写入，
必须以新的规范变更重新完成信任来源、handoff fencing、opt-in、canonical transcript 与负向向量设计。
