---
title: Privacy-Preserving Search
status: candidate
normative: true
stability: v1
updated: 2026-06-10
see_also:
  - service-surface.md
  - client-sync.md
  - ../crypto-media/encryption-and-audit.md
  - ../../artifacts/schemas/search-service.schema.json
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具有规范约束力。

## 1. 范围

搜索不是 Cokret 真相源。客户端本地搜索、受托 search / projection 服务和 directory search 都必须回到 signed Event、reducer profile、Realm policy 与 causal frontier 校验结果。

本文只定义两类隐私保护 search profile：

- `ck.profile.search.client_index.v1`: 客户端加密索引托管。
- `ck.profile.search.blind_index.v1`: keyed blind token 服务端候选检索。

任何接收 plaintext、可逆摘要、embedding 或用户可读 snippet 的服务仍必须通过 `plaintext_visible_services` 授权；本文 profile 不得被用来绕过该要求。

## 2. Client Encrypted Index

客户端加密索引的 manifest 写入 `ck.search.index_manifest.v1:<realm_key>`。`realm_key` 等于对 canonical `realm_id` 计算 `base64url(HMAC-SHA256(account-data namespace key, ...))`。manifest plaintext shape 使用 `realm_id`，并在 account-data value 中加密；`shard_key` 不得由 plaintext term、object ref、message id 或 flow id 直接派生。

托管服务只能返回 encrypted shard / manifest bytes，MUST NOT 返回 hit、ref、snippet、score 或 term-level metadata。客户端解密后仍必须按当前 Realm policy、history visibility、redaction、expiry 和 local capability state 过滤。

## 3. Blind Index

Blind index 使用 keyed HMAC token。Posting 必须绑定 `realm_id`、`effective_scope`、`epoch_id`、`index_generation` 和 `blind_tokens[]`；服务端返回的只是候选 ref 集合。客户端 MUST 把所有结果视为 untrusted candidate，并重新验证可见性和内容匹配。

服务端在返回候选前 MUST 执行 current-auth 与 history filter。撤权、history visibility 收紧、redaction、message expiry 或 MLS epoch rotate 后的 stale posting MUST fail closed：可以漏召回，不得越权召回。该不变量由 `ck.vector.search.blind_index_stale_posting_fail_closed.v1` 覆盖。

Token 不得跨 Realm、Circle、MLS epoch 或 index generation 复用。实现 SHOULD 定期轮换 index key，并把轮换与 policy frontier digest 绑定。

Blind-index token 是 deterministic keyed token：它不向服务端暴露明文 term，但会暴露同一 `index_generation` 内的查询频次、候选集合大小、access pattern 以及 term 共现结构。实现 MUST 把这些泄漏写入 Realm search policy 的风险评估；高隐私 Realm SHOULD 缩短 `index_generation` / epoch 轮换窗口，并限制服务端跨 generation 关联。Forward-private SSE、PIR-backed candidate retrieval 或 ORAM-style access hiding 只能作为显式 search extension profile 引入；base v1 blind index 不声称隐藏 access pattern。

## 4. Realm Search Policy

`ck.realm.search_policy` 写入 Realm policy cell。默认行为是 fail closed：未声明允许的受托 search 服务不得接收 plaintext 或可逆派生数据，也不得接收 blind-index token。

Policy 至少声明允许的 `enabled_profile_refs`、service DID、可接收数据类别、index retention 和 revocation behavior。是否允许 plaintext-visible search MUST 由 `data_classes` 中是否包含 `plaintext` / `reversible_summary` 表达，不得另设未注册的 boolean 字段。

## 5. Result Semantics

Search hit 永远不是权限证明。展示 hit 前，客户端或受托 projection MUST 重新解析目标对象状态，并检查 redaction、expiry、moderation、history visibility、Circle membership 和 capability。检查失败时，结果必须被省略或替换为不可泄露存在性的固定 stub。该不变量由 `ck.vector.search.result_not_authz_proof.v1` 覆盖。
