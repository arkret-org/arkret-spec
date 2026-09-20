---
title: Directory Public Realm Metadata
status: candidate
normative: true
stability: v1
updated: 2026-09-20
---

# Directory：公开 Realm metadata 索引

本文的规范关键词按 [`../conformance/normative-language.md`](../conformance/normative-language.md) 解释。

机器可执行闭包由 `ak.vector.directory.announce_bad_signature.v1`、`ak.vector.directory.announce_bidirectional_opt_in.v1`、`ak.vector.directory.announce_directory_not_authorized.v1`、`ak.vector.directory.announce_signature_stale.v1`、`ak.vector.directory.public_realm_search.v1`、`ak.vector.directory.reannounce_idempotent_ttl.v1`、`ak.vector.directory.ttl_expiry_removal.v1` 与 `ak.vector.directory.withdraw_blinded_not_found.v1` 覆盖。

## 1. 产品边界（normative）

Directory v1 只是可重建的公开 Realm metadata 索引。它不保存或提供 Realm Event、RealmCommit、stream、成员、
权限、join／invite 状态、历史、治理链、source ref、authority proof、Organization、Actor、User、Applet、Handle、
restricted discovery、private-contact discovery 或 PSI。Directory 查询结果不得被后续加入、认证、读写或权限流程
当作 current-authority 或 authorization evidence；这些流程必须直接向目标 Realm 的 current governance Station 重新验证。

## 2. 可索引条件（normative）

Directory 仅在以下条件同时成立时建立或保留条目：

1. Realm 当前 `discoverability` 逐字等于 `public`；
2. Realm 当前 discovery policy 的 `directory_ids[]` 明确包含目标 `directory_id`；
3. 请求 transport sender 是该 Realm 的 current governance Station，且 detached governance proof 绑定 exact
   operation、`realm_id`、`directory_id`、`authority_generation`、request identity、freshness 与 body；
4. `public_metadata` 通过 `PublicRealmMetadata` 闭合 schema 与大小限制。

`listed`、`restricted`、`unlisted`、`invite_only`、`secret` 或未 opt-in 的 Realm 均不得被索引，也不得通过 exact
RealmId resolve 形成存在性 oracle。旧 governance generation、成员 Station、Consumer Station、source Station、
副本服务、缓存与任何第三方提交都必须零写入拒绝。

## 3. 写入（normative）

`ak.find.directory.command.announce.v1` 同时承载 announce、re-announce 与 replace。相同 request identity 和相同
canonical body exact replay 返回同一 outcome；同 identity 异内容冲突。replace 只能替换同一 Realm、同一 Directory
的当前条目。`ak.find.directory.command.withdraw.v1` 只撤回该 exact 条目。handoff 生效后旧治理方不得续期、替换或
撤回；新治理方必须以自身身份重新提交。任一 authority、binding、freshness、防重放、public 状态或 opt-in 校验失败
都必须零写入。TTL 到期只使条目失效，Directory 或第三方不得自动续期。

Directory 可以保存防重放、exact retry 和 abuse audit 所需的最小私有运维状态；该状态不是 canonical Realm resource，
不进入查询响应或跨 Directory 对账。

### 3.2 非公开状态

除 `public` 外的 discoverability 状态均不得进入 Directory 索引；已知 RealmId 也不能绕过该边界。

## 4. 查询（normative）

公开查询只有 `search_realms` 与 `resolve_realm`。每条 `PublicRealmDirectoryEntry` 恰好包含：

- `realm_id`；
- 闭合 `public_metadata`；
- Directory-local `indexed_at` 与 `expires_at`。

`public_metadata` 的 locator 即使存在也只是 Realm 主动公开的联系提示，不证明 endpoint 仍有治理权。查询响应禁止携带
source refs、Event、RealmCommit、authority proof、成员数、成员身份、role、capability、join rule、history policy、
restricted claim 或任何后续业务材料。无权披露、未 opt-in、非 public、过期与不存在必须同形处理。

## 5. 删除的旧面（normative）

current-v1 不登记 source-ref access carrier、Directory→source callback、
private-contact discovery 或 PSI。拥有 Event／RealmCommit 副本不授予 Directory announce 权，也不能通过回源把第三方
代发升级为治理方直投。

## 6. 验证矩阵

conformance 必须覆盖：错 transport sender、旧 generation、Realm／Directory／operation 错绑、过期、重放、
同 request identity 异内容、非 public、未 opt-in、metadata 越界、第三方 replace／withdraw、TTL 后第三方续期，
以及查询结果夹带 Event／Commit／authority／membership／join／history 信息。所有失败分支均不得改变索引。

### 6.2 旧私有发现入口

旧 private-contact／PSI 入口已删除；本节号仅保留给历史交叉引用，不构成 current-v1 surface。

## 7. 已删除的后续业务承载

### 7.3 Locator

公开 locator 只能位于闭合 `public_metadata`，并且不证明 current authority。

## 8. 直投验证

### 8.10 防枚举

非 public、未 opt-in、过期、无权披露与不存在必须保持同形。

## 9. 历史对象发现面

### 9.0 Handle

Directory v1 不提供 Handle 查询。

### 9.1 其它 identity 对象

Directory v1 不提供 Organization、Actor、User 或 Applet 查询。

## 11. 安全边界

Directory 查询结果不得成为 membership、join、history、capability 或 current-authority evidence。
