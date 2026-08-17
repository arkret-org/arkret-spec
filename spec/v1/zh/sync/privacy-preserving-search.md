---
title: Privacy-Preserving Search
status: candidate
normative: true
stability: v1
updated: 2026-07-02
see_also:
  - service-surface.md
  - client-sync.md
  - ../crypto-media/encryption-and-audit.md
  - ../../artifacts/schemas/search-service.schema.json
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具有规范约束力。

## 1. 范围

搜索不是 Arkret 真相源。客户端本地搜索、受托 search / projection 服务和 directory search 都必须回到 signed Event、reducer profile、Realm policy 与 causal frontier 校验结果。

本文定义三类隐私保护 search profile：

- `ak.profile.search.client_index.v1`: 客户端加密索引托管。
- `ak.profile.search.blind_index.v1`: keyed blind token 服务端候选检索。
- `ak.profile.search.forward_private.v1`: 在 blind-index 基础上叠加 server-assisted OPRF 与 generation-bound token derivation，降低长期增量泄漏；该 profile 为 opt-in extension，不改变 base blind-index 语义。

任何接收 plaintext、可逆摘要、embedding 或用户可读 snippet 的服务仍必须通过 `plaintext_visible_services` 授权；本文 profile 不得被用来绕过该要求。Directory search、本文的 privacy-preserving search 与 bridge interop 三类检索面 MUST 保持隔离、互不泄露私有 plaintext；该不变量由 `ak.vector.search.surface_separation_no_plaintext_leakage.v1` 覆盖。

## 2. Client Encrypted Index

客户端加密索引的 manifest 写入 `ak.search.index_manifest.v1:<realm_key>`。`realm_key` 等于对 canonical `realm_id` 调用 [`account-data.md` §2](../models/account-data.md) 的 `derive_account_data_key`。manifest plaintext shape 使用 `realm_id`，并在 account-data value 中加密；`shard_key` 不得由 plaintext term、object ref、message id 或 strand id 直接派生。

托管服务只能返回 encrypted shard / manifest bytes，MUST NOT 返回 hit、ref、snippet、score 或 term-level metadata。客户端解密后仍必须按当前 Realm policy、history visibility、redaction、expiry 和 local capability state 过滤。

## 3. Blind Index

Blind index 使用 keyed HMAC token。Posting 必须绑定 `realm_id`、`effective_scope`、`epoch`、`index_generation` 和 `blind_tokens[]`；服务端返回的只是候选 ref 集合。客户端 MUST 把所有结果视为 untrusted candidate，并重新验证可见性和内容匹配。

服务端在返回候选前 MUST 执行 current-auth 与 history filter。撤权、history visibility 收紧、redaction、message expiry 或 MLS epoch rotate 后的 stale posting MUST fail closed：可以漏召回，不得越权召回。该不变量由 `ak.vector.search.blind_index_stale_posting_fail_closed.v1` 覆盖。

服务端 MUST NOT 返回或暗示过滤前 posting list 的基数。`total`、`has_more`、分页 cursor、bucket / padding 后的 result count、timing bucket 和任何诊断字段都只能基于 current-auth / history filter 之后的候选集合计算；若实现需要暴露结果数量，必须对过滤后集合执行固定上限、padding 或 bucket 化，且不得让"过滤前 N 条、过滤后 0 条"与"过滤前 0 条"在 wire shape 或 timing 上可区分。否则 blind token 会退化为存在性 oracle，泄露 caller 无权看到的对象是否含有该 term。

Token 不得跨 Realm、Circle、MLS epoch 或 index generation 复用。实现 SHOULD 定期轮换 index key，并把轮换与 policy frontier digest 绑定。

Blind-index token 是 deterministic keyed token：它不向服务端暴露明文 term，但会暴露同一 `index_generation` 内的查询频次、候选集合大小、access pattern 以及 term 共现结构。实现 MUST 把这些泄漏写入 Realm search policy 的风险评估；高隐私 Realm SHOULD 缩短 `index_generation` / epoch 轮换窗口，并限制服务端跨 generation 关联。Forward-private SSE、PIR-backed candidate retrieval 或 ORAM-style access hiding 只能作为显式 search extension profile 引入；base v1 blind index 不声称隐藏 access pattern。

**向数据主体披露（normative）**：当 Realm 启用 deterministic blind_index（`deterministic_token`）使受托 search service 可观测上述 access pattern / 查询频次 / term 共现时，该 `leakage_class` 与承载它的受托 search service DID **MUST** 对受影响成员（数据主体）可见。客户端搜索 UI 对 high-privacy Realm（`security_class=high_assurance`，或 Realm policy 声明 high-privacy / 敏感分类）**MUST** 在搜索入口提示"本 Realm 的搜索由受托服务以可观测访问模式承载"；其余 Realm SHOULD 在搜索入口给出该提示。口径对齐 [`../governance/history-visibility.md` §5](../governance/history-visibility.md) 对 plaintext-visible 内容"UI MUST 展示"的披露强度——成员不应在不知情下让搜索 access pattern 被受托服务观测。

### 3.1 Forward-Private Search Extension

`ak.profile.search.forward_private.v1` 继承 `ak.profile.search.blind_index.v1`，但 Realm `ak.realm.search_policy.enabled_profile_refs` 中必须同时启用该 profile，并声明 `leakage_class="forward_private"`。服务端 MUST 在 `*.describe` 或等价 feature discovery 中声明 OPRF suite、generation 轮换上限、revocation behavior 和 stale posting fail-closed 行为；客户端在缺少这些声明时 MUST 返回 `unsupported_feature`，不得把 deterministic blind-index provider 当作 forward-private provider 使用。

Forward-private profile 的最小 wire 语义：

1. Search token derivation 使用 server-assisted OPRF / VOPRF 交互，token 绑定 `(realm_id, effective_scope, epoch, index_generation, term_digest)`；服务端不得获得 plaintext term，客户端不得把 raw term 或可逆摘要作为 query 参数发送。**OPRF suite 钉定（normative）**：forward-private search 的 OPRF **MUST** 使用 RFC 9497 `modeVOPRF`（0x01）与 ciphersuite identifier `ristretto255-SHA512`，两者必须按 RFC `CreateContextString` 独立组合；不得使用旧的非标准 token `OPRF-ristretto255-SHA512`。该口径与 [`../discovery/discovery-directory.md` §6.2](../discovery/discovery-directory.md) 一致；§3.1 中服务端 `*.describe` 声明的 mode / suite MUST 为已登记组合，客户端遇到缺失、未知或不支持值时 MUST fail closed 并返回 `unsupported_feature`，不得回退到 deterministic blind-index。
2. `index_generation` 与 Realm policy frontier / MLS epoch frontier 绑定。撤权、history visibility 收紧、redaction、message expiry 或 epoch rotate 之后的 stale posting MUST fail closed；可漏召回，不得越权召回。
3. 新 generation 的 posting MUST NOT 被旧 generation token 检索。服务端不得跨 generation 返回合并候选，除非客户端显式提交多个 generation token 且每个 generation 都通过当前授权过滤。
4. `leakage_class="forward_private"` 只承诺阻断旧 token 对新写入的检索和降低长期增量关联；它不承诺隐藏 access pattern、候选集合大小或查询频次。隐藏这些信息必须使用未来显式 `access_hiding` profile。

## 4. Realm Search Policy

`ak.realm.search_policy` 写入 Realm policy cell。默认行为是 fail closed：未声明允许的受托 search 服务不得接收 plaintext 或可逆派生数据，也不得接收 blind-index token。

Policy 至少声明允许的 `enabled_profile_refs`、service DID、可接收数据类别、index retention 和 revocation behavior。是否允许 plaintext-visible search MUST 由 `data_classes` 中是否包含 `plaintext` / `reversible_summary` 表达，不得另设未注册的 boolean 字段。

`leakage_class` 是闭合枚举：`deterministic_token`、`forward_private`、`access_hiding`。省略时等价于 `deterministic_token`。`ak.profile.search.blind_index.v1` 的 policy MUST 使用 `deterministic_token` 或更强值；声明 `ak.profile.search.forward_private.v1` 时 MUST 使用 `forward_private`，且 MUST 同时声明 `token_rotation_cadence_ms`。`access_hiding` 为 **reserved leakage class**（PIR / ORAM 类），其状态与 digest-suite / HPKE registry 的 reserved-row 同纪律：钉定枚举值与 fail-closed 语义，但在 activation requirements 全部满足并由一个显式 profile 在 registry release 中转 active 之前，**MUST NOT 出现在 wire 上**——没有满足 activation requirements 的 profile 支持时，实现 MUST fail closed，不得仅凭该字段声称 access-hiding。

**`access_hiding` activation requirements（normative）**：任何把 `leakage_class` 设为 `access_hiding` 的 Realm search policy MUST 同时声明一个满足以下全部条件的 search extension profile，否则 reducer / 受托 search service MUST fail closed（视为未支持）：

1. **后端协议规范**：pin 一个具体的 access-pattern-hiding 后端及其 wire 协议——候选技术族为单 / 多服务器 PIR（如 SimplePIR / DoublePIR）、enclave-backed PIR（Signal SealedSession 风格）、或 Path-ORAM；MUST 指向具体方案而非泛称"PIR/ORAM 类"，避免各实现发明不兼容后端。
2. **leakage 分析**：明确声明该 profile 隐藏与不隐藏的内容（access pattern、候选集合大小、查询频次各自的保证级别）。
3. **conformance 向量**：交付 per-profile 的 access-hiding 行为向量。
4. 若采用 enclave 路线，其 attestation SHOULD 复用 [`../crypto-media/audited-e2ee.md`](../crypto-media/audited-e2ee.md) 的 attested_hardware 基础设施，不另起一套。

`access_hiding` 不属于 current-v1 wire。实现不得发布该 profile、在 describe 中声明支持，或自行选择 PIR / ORAM 后端并把私有形态放入 Arkret namespace；只有当前 canonical registry/schema 明确定义的搜索模式可以互操作。

## 5. Result Semantics

Search hit 永远不是权限证明。展示 hit 前，客户端或受托 projection MUST 重新解析目标对象状态，并检查 redaction、expiry、moderation、history visibility、Circle membership 和 capability。检查失败时，结果必须被省略或替换为不可泄露存在性的固定 stub。该不变量由 `ak.vector.search.result_not_authz_proof.v1` 覆盖。
