---
title: DID 使用与验证边界
status: candidate
normative: true
stability: v1
updated: 2026-09-12
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按
[`../conformance/normative-language.md`](../conformance/normative-language.md)
解释；仅大写形式具规范约束力。

## 1. 目标与总原则

本文集中回答两个问题：

1. Arkret wire 中哪些 identifier 字段承载稳定 `did_core_id`、完整 `did` 或 DID URL；
2. 哪些业务场景真正需要验证 DID 控制权，哪些场景只使用稳定身份核。

`did_core_id` 在绝大多数业务路径中是稳定、可比较、可索引的主体标识；它不是 DID，也不可直接
resolve。字段来源于 DID **不等于**读取或写入该字段时必须解析 DID Document，更不等于必须发起
在线网络请求。实现 MUST 把下列
四件事分开：

1. **语法校验**：确认值是 `did_core_id`、bare `did`、DID URL 或其它已声明 identifier 形态；
2. **标识使用**：以完整 `did_core_id` 逐字比较、索引、去重、路由或匹配授权主体；
3. **签名验证**：使用已经接受并固定到相应 auth-state / key epoch 的公钥验证某个 proof；
4. **DID 权威验证**：按 DID method adapter、resolver policy、history / controller proof 与 trust
   evidence 验证 `project(did) == expected did_core_id` 以及指定历史位置控制哪些 key / delegation。

第 1 项在 wire ingress 执行；第 2 项是普通业务路径；第 3 项按签名对象的协议要求执行；只有
第 4 项属于本文所称的“验证 DID”。前三项不得被实现成“顺便在线解析 DID”。DID 权威验证是
少量、显式的信任边界操作，不能成为普通对象读取、列表渲染或每次 Event 提交的隐式前置条件。

对 human principal，DID 权威验证还必须分成两个互不替代的时态：注册时或 Event accepted-at
时点的历史证据用于重放已经成立的身份/PCR 起源；current DID evidence 只用于当前外部身份声明、
method successor、显式启用的 DID-root recovery。历史验证不得查询最新 DID head 后用当前
controller 替代旧 key；current controller 也不得仅凭 `did_core_id` 相同取得既有 PCR、membership、grant、
contact、session 或 account lifecycle authority。

本文件的 DID authority verifier、方法历史与 accepted binding store 义务适用于接纳外部材料的 Station、registry、联邦服务及独立审计者。普通客户端通过自己的已认证 Station 消费结果，核对完整账号、subject、purpose 与 freshness，不实现这些历史 verifier 或持久证据闭包；详见 [服务器信任与结果消费](../sync/server-trusted-results.md)。普通客户端自己 Station 的首次接入与重连同样不承担方法历史 verifier，按 [server-trusted-results §1.2](../sync/server-trusted-results.md#12-普通客户端的-station-接入normative) 核对显式信任起点与持久认证绑定。客户端本地签署及端到端密钥/消息认证继续执行。

## 2. DID 身份材料的正交分类与命名

对象 schema 是字段必填性与精确 shape 的唯一真相源。本节不再人工穷举字段名；跨 schema 清单由
[`did-representation-report.json`](../../artifacts/reports/did-representation-report.json) 从 resolved terminal
constraint 生成，`source_of_truth=false`，只用于复核与漂移检测。

每个 DID-material property 必须分别回答两条正交问题：

1. semantic category / lexical ownership：Arkret 稳定身份材料、外部标准标识符或其它
   [`common-fields.md` §2.1](../models/common-fields.md) 类别；
2. representation profile：`did_core_id`、`did` 或 `did_url`。

W3C DID Document 的 `controller` 因而可以同时是 external-standard-owned 字段和 `did` representation；
这不是类别重叠。外部 literal object 必须以精确 schema path、`x-arkret-external-literal-object` 和外部规范
anchor 登记，例外不得传播到 Arkret normalized projection、policy 或 API wrapper。

### 2.1 三种 representation profile

| profile | canonical terminal | 用途 | 稳定授权 |
| --- | --- | --- | --- |
| `did_core_id` | `^ak:did_core:[a-z0-9]+:[^\s/?#]+$` | 持久主体引用、授权、相等、索引、去重 | 可以 |
| `did` | `^did:[a-z0-9]+:[^\s/?#]+$` | registration、resolution、method evidence | 不可以；必须经 adapter 投影并绑定 expected core |
| `did_url` | `^did:[a-z0-9]+:[^\s#?]+#[A-Za-z0-9._:-]+$` | verification method / key selection | 不可以 |

`did_url` 的 query 禁止、fragment 必备；当前 profile 不禁止 fragment 前出现 `/`。三种 terminal
都以 [`common-ids.schema.json`](../../artifacts/schemas/common-ids.schema.json) 为唯一机器定义。

### 2.2 Canonical naming grammar

- 稳定 core：对象自身 `id`，引用使用 `<role>_id` / `<role>_<kind>_id` / 复数 `_ids`；
- W3C DID：角色唯一且显然时用 `did`，否则用 `<role>_did` / `<role>_dids`；
- DID URL key selector：`verification_method` / `<role>_verification_method`；
- 公共类型固定为 `DidCoreId`、`Did`、`DidUrl`。不得额外定义裸 DID alias，也不得保留旧“完整 ID”公共
  类型、字段、schema definition、serde alias 或双读；
- `id` / `controller` / `verificationMethod` 等外部标准词法只在精确 literal-object 路径保留；
- 真正多 representation 的单一 Arkret property 必须是 closed discriminated union，并逐 path 登记理由。

字段名不替代 schema typing。`did` / `*_did(s)` / `verification_method` 不得以 loose `type:string` 或
通用 URI 逃逸 canonical terminal。

### 2.3 DID 字段存在性矩阵

| 对象职责 | `DidCoreId` | `Did` |
| --- | --- | --- |
| 普通 canonical identity object | `id` required | 禁止 |
| Event、membership、grant、profile、普通主体/service 引用 | 相应 `*_id` required | 禁止 |
| registration / identity genesis 输入与 accepted evidence | required 或由 DID 唯一投影得到 | required |
| Identity resolution / Service DID method evidence | `id` 或角色化 `*_id` required | required |
| DID method evidence / control proof | 绑定 expected core | required |
| W3C DID Document literal object | 按外部标准 | 保留标准 `id` |

同一个 identity-bearing object 不得添加通用 optional `did`。可路由 service 必须存在经方法验证的当前 DID 状态及唯一服务入口，但普通 service 引用不得内联 DID；human principal 只在注册/genesis 阶段提交并验证 DID，后续普通
业务对象只使用稳定 `DidCoreId`。每个 `DidCoreId` 创建时必须来自已登记 adapter 对有效 `Did` 的唯一投影；
从未具有 DID 的主体必须使用其它已登记 ID 类型。

上述职责边界的机器真相源是
[`did-evidence-boundary-registry.json`](../../artifacts/registry/did-evidence-boundary-registry.json)。每个
authority verifier 必须从登记的 registration/genesis、resolution record、method evidence 或 proof
carrier 取得 required `did` / `verification_method`，经 active adapter 验证并投影后与 expected core
逐字比较。孤立 `did_core_id` 没有 route evidence，**不得**触发 resolver；adapter 不登记 `expand` 或
`core_to_did`，即使 `did:web` / `did:key` 的字符串看似可逆也不得绕过 carrier 猜测 DID。Identity
resolution 需要已知 `(principal_id, station_id)` account pair；service resolution 需要 bootstrap
携带的 `resolution_url` 或已验证的 same-core route。未登记的 route source 一律 fail closed。

## 3. 普通业务路径：只使用身份锚点

已经建立可信绑定后，下列操作只需要把 `did_core_id` 当作 opaque identity key，不得因此触发 DID
Document 解析、history 验证或网络请求：

- profile、成员、消息、通知、已读状态、列表、搜索结果与审计记录的读取和渲染；
- `did_core_id` 的 equality、set membership、索引、去重、分组、排序、日志归属与 selector 匹配；
- 使用已接受 auth-state 中的 `actor_id` / `principal_id` / `service_id` 做 capability、
  membership、policy、blocklist 或 routing binding 求值；
- 已认证 session 中由同一 accepted device / agent key epoch 签署的普通 Event 提交；
- replay、backfill、snapshot 重放或历史查询已经携带并命中 pinned auth-state / historical
  verification binding 的材料；
- 从完整 AccountId/ActorId 派生目标 Station identity，并使用 fresh service-resolution route cache；
- 展示 verification badge 的缓存状态。UI 可以显示 `verified` / `stale` / `unknown`，但显示路径
  不能升级成 authority path。

接纳服务器对普通签名对象仍 MUST 验证签名、canonical transcript、nonce / sequence、scope 与 authorization；客户端只对端到端密码学对象及自己待签意图执行相应检查。
该验证应使用相应 RealmCommit / auth-state / device authorization / agent signer evidence 中已经接受的
公钥绑定。**验证签名不等于重新验证 DID**；实现不得仅因签名对象含 `actor_id` 或
`verification_method` 就对 resolver 发起请求。

## 4. DID 权威验证的封闭触发条件

调用点必须先选择下表中的证据类别，再决定是否存在 DID authority call。动作的 `risk_tier` 与
DID freshness 是正交维度；高风险只要求其**实际授权根**新鲜，不能自动推导“刷新 DID”。

| 证据类别 | 封闭触发场景 | 必须验证的内容 | freshness |
| --- | --- | --- | --- |
| `registration_control` | human principal 注册、把已发布 DID 首次绑定到新建 PCR | 注册时 current `did` control proof、adapter 投影、bootstrap trust、method head/version、control-key digest、PCR genesis receipt | 注册 challenge 窗口内同步验证；accepted 后冻结为历史证据。 |
| `accepted_at_history` | 首次重放 PCR genesis、历史 device/Agent/service authorization 或历史 receipt，且本地没有其 pinned evidence | 证据所钉 accepted-at position 的 DID/core 投影、key、method evidence 与 receipt/RealmCommit lineage | 以被钉时点为准；不得要求 current head 或 current controller。 |
| `pcr_authority` | 已登记 carrier 直接验证 PCR accepted authority，而不读取 current DID | PCR genesis / RealmCommit / accepted authorization lineage 与其 pinned signer evidence | 以 carrier 固定的 accepted frontier 为准；不创建 current-DID refresh。 |
| `current_external_claim` | 当前外部身份 badge/claim、当前 DID delegation/controller 声明 | 最新 method state、current controller/delegation、deactivation 与调用点 policy | 调用点登记的 current profile。失败只使该 claim stale/unavailable。 |
| `method_successor` | `ak.identity.resolution.update`、webvh relocation、DID rotation/deactivation publication | 从 PCR accepted resolution head 到候选 head 的 method-native successor、same-core projection、current PCR author 与 CAS | 同步刷新或 fail closed；PCR author 与 method successor 缺一不可。 |
| `optional_did_root_recovery` | 账号的 accepted recovery policy 明确启用了 DID-root factor，且该 factor 正在被使用 | policy opt-in、current DID root/history、pre-rotation、recovery session、PCR generation CAS | 同步刷新或 fail closed；未启用时 current root proof 必须拒绝。 |
| `ongoing_governance` | organization、Agent 或 service 的角色合同明确把 DID controller/delegation/key state 定为持续 authority | 角色、purpose、current delegation/key、history、policy 与 audience | 由具体 operation/action 登记；不得外推到 human PCR。 |

下列操作对 human principal **不创建 DID authority call**：普通或高风险 Event 写入、device
authorize/revoke、PCR-policy recovery、capability grant/revoke、MLS commit、membership/join/invite、
session 恢复、账号删除/擦除、Contact 与既有 AccountId / ActorId 使用。它们必须验证 fresh PCR、device、
recovery policy、capability、MLS、account 或 service authority；DID host 不可达不得改变这些状态。

出现新的 human device generation 或 `verification_method` 不自动触发 current DID 验证。device key
必须从已接受 PCR authorization chain 取得；`verification_method` 的 bare `did` 只经 adapter 做
确定性 core 投影，fragment 选择该链中的 key。只有链中某一步本身使用了上表的 DID-root factor，才
为该步携带并验证相应 accepted-at DID evidence。

除上述触发条件外，业务代码 MUST NOT 自行增加“保险起见再 resolve 一次”的路径。真实调用点
必须在 operation/event/verifier-action registry 中携带 `did_authority`，逐字声明 `evidence_class`、
`purpose` 与 current call 所需的 `freshness_profile_id`；historical verifier action 固定为
`freshness_profile_id=null`。没有登记的 operation/event/verifier action MUST NOT 调用 authority resolver。

## 5. 验证结果、缓存与失效

DID 权威验证的产物 MUST 是有上下文、可复算的 verification result，而不是一个无上下文的
`verified=true`。**可审计的实际含义是可复算**：每个 digest 字段都必须有留存的 canonical
输入对象（至少在本次验证与其声明的 cache lifetime 内），审计者能据其重算出同一 digest。result 是
trust-domain 本地产物，本节合同保证的是
（i）可复算、（ii）任何安全相关输入变化必然改变 digest、（iii）无证据场景有规范化退化形；
**不承诺**不同部署对同一 DID 算出相同 digest，也**不要求**接收方为遇到的第三方 principal 持久保存
result。调用方可在本次操作后丢弃它，或放入有界 TTL cache；owner-side PCR resolution、账户绑定以及
部署明确配置的 service allowlist 则可按其各自合同持久保存。机器形状统一登记在
[`did-binding-contracts.schema.json`](../../artifacts/schemas/did-binding-contracts.schema.json)，
KAT 见 [`did-binding-digest-fixture.json`](../../artifacts/fixtures/did-binding-digest-fixture.json)
（`ak.vector.did_binding.document_digest_kat.v1`、
`ak.vector.did_binding.evidence_receipt_kat.v1`、
`ak.vector.did_binding.policy_snapshot_kat.v1`）。

| 字段 | 要求 |
| --- | --- |
| `did_core_id` / `did` | expected 稳定身份与被验证的 bare DID；必须满足注册 adapter 的确定性投影。 |
| `trust_domain` / `purpose` | 结果适用的本地信任域与用途（principal、service、issuer、controller 等）。 |
| `method` / `verification_method` | DID method 与被接受的具体 DID URL；不适用具体 key 时可省略后者。 |
| `document_digest` / `history_head` / `version_id` | 固定验证依据；计算方式见 §5.1。method 不支持或 resolver 未传出的 pin 可省略，但 MUST 按 §5.5 的 `limited_trust` 记录逐 pin 状态。 |
| `evidence_digest` / `policy_digest` | method evidence 与 resolver policy 的绑定；分别由 §5.2 的 canonical evidence receipt 与 §5.3 的 canonical policy snapshot 定义，二者并列携带、互不嵌套。 |
| `evidence_dependencies` | 从 evidence receipt 机械提取的结构化依赖清单（§5.6）；无 evidence 的 method 为空集。 |
| `verified_at` / `refresh_after` / `expires_at` | 验证时间、后台刷新点与硬失效点；必填性与取值由调用点引用的 §5.4 freshness profile 决定（tier 决定必填性、申报决定数值）。 |
| `status` | `active`、`stale`、`deactivated`、`quarantined` 或等价封闭状态。 |

实现 MAY 先查本地 accepted auth-state、可选 verified-binding store 与 resolution cache，再决定是否
需要后台刷新。缓存 TTL 到期本身不得把普通业务请求变成在线 DID resolution；它只会把
authority-grade 结果标为 stale。仅当 §4 的触发场景要求新鲜证据时，调用方才等待刷新或 fail
closed。

### 5.1 `document_digest`：normalized projection 与固定算法

`document_digest` 摘要的是 resolver **已验证并返回的 normalized DID Document projection**，
不是 resolver 原始响应 bytes：

- projection 的唯一 schema 是
  [`did-binding-contracts.schema.json#/$defs/normalized_did_document`](../../artifacts/schemas/did-binding-contracts.schema.json)：
  它保留所有影响 key authorization、controller、service routing、method policy **或被 v1 normative
  消费**的成员，显式包含 `alsoKnownAs -> also_known_as` 与 `metadata.primary_handle`；未知 extension
  逐 name 无损保留，`contexts` 保留源顺序，其它 set-like 数组按 unsigned UTF-8 排序；重复 / 冲突
  property、id、relationship、metadata 或 extension name 在摘要前 fail closed；
- 计算固定为 `"sha256:" + lowercase_hex(SHA-256(RFC8785_JCS(normalized_document)))`；
- raw 响应若需取证，使用**不同名**的 `raw_document_digest`，两者 MUST NOT 互换或混用；禁止另造
  第三个 DID-document digest 字段。digest owner 与 Arkret DID Document member/service type 闭集见
  [`did-document-contract-registry.json`](../../artifacts/registry/did-document-contract-registry.json)。

### 5.2 `evidence_digest`：canonical evidence receipt 经 resolver 通道产生

method evidence（webvh log head、witness proof set、consistency / receipt 材料）只存在于
resolver 手中，不可能从 DID Document 推导，因此 resolver 合同 MUST 把它与文档一起返回
（`ResolvedDid { document, method_evidence }` 形态）；任何「调用方事后补 evidence digest」
的 API 形状都是不合规实现。verifier 在其内部据此构造 canonical evidence receipt 并计算
digest：

```text
evidence_receipt = {
  "kind": "ak.did.binding_evidence.v1",
  "method": "<canonical lowercase method token>",
  "document_digest": "<§5.1 的 document_digest>",
  "method_proofs": <按 method 登记的闭合行；无 proof 的 method 为 []>
}
evidence_digest = "sha256:" + lowercase_hex(SHA-256(RFC8785_JCS(evidence_receipt)))
```

- receipt 本体 MUST 留存（可复算义务）；
- 无 proof 的 method（`did:key`、裸 `did:web`）规范化退化为空 `method_proofs` 的
  document 绑定 receipt；实现自造常量占位符 MUST 被判为不合规；
- 每个 method 的 evidence 行 MUST 登记：必备字段、禁止字段、数组的 canonical 排序键、
  重复项拒绝规则与缺省值编码；不得把 resolver 返回顺序当作摘要顺序。v1 登记唯一的行
  `webvh_log`（log head、按 `witness_did` 排序去重的 `{witness_did,
  controlling_organization_did}` 集合、witness proof set 的 canonical digest）；未知 method
  evidence kind 一律 fail closed；
- `policy_digest` **不进** receipt：binding 并列携带两个 digest，嵌套会把 evidence 失效与
  policy 轮换耦合并双计一个维度。

### 5.3 `policy_digest`：canonical resolver policy snapshot

`policy_digest` 是 binding 复用判据（§4）、binding key 的一维与失效索引的一维，其输入是
canonical policy snapshot：

```text
policy_snapshot = {
  "kind": "ak.did.resolver_policy.v1",
  "policy_profile": "<登记的 resolver policy profile id>",
  "accepted_did_methods": [<did:<m>: 前缀形式，排序去重>],
  "fail_mode": "fail_closed" | "allow_cached_on_error",
  "trust_roots": [<排序去重，可为空>],
  "profile_policy": { <profile 闭合 schema 校验的部署特有维度> }
}
policy_digest = "sha256:" + lowercase_hex(SHA-256(RFC8785_JCS(policy_snapshot)))
```

- **必含三项**（可接受 method、失败降级行为、信任根）是任何 resolver policy 的安全核心，
  不允许漏摘；
- `policy_profile` 是 `profile_policy` 的 schema discriminator：每个登记 profile MUST 给出
  `additionalProperties: false` 的闭合 schema，并把所有会改变解析、验证、网络边界、大小
  限制或降级行为的配置列为 required；v1 登记基础 profile
  `ak.did_resolver_policy_profile.base.v1`（`profile_policy` 恒为 `{}`）。未知 profile、
  未知字段、缺少已登记字段一律 fail closed；
- enum 值 MUST 使用登记 wire token，禁止语言原生调试格式（`"FailClosed"` 一类编码分叉
  即由此消除）；集合按 UTF-8 byte order 排序去重；字符串不做 Unicode 等价归一化，除非对应
  字段 registry 明确规定；
- snapshot MUST 可留存 / 可重建；「任何安全相关配置变化 ⇒ digest 变化」由此可被外部验证。
  「两个部署 digest 相等」只在配置逐字段等价时作为推论成立，不是设计目标。

### 5.4 freshness profile：tier 决定必填性、申报决定数值

`refresh_after` / `expires_at` 的必填性与取值由**已登记的 freshness profile** 决定
（[`did-binding-contracts.schema.json#/$defs/freshness_profile`](../../artifacts/schemas/did-binding-contracts.schema.json)）：

- 每个 DID authority call site MUST 经 operation / action 的 `did_authority` 对象显式引用一个
  [`did-freshness-profile-registry.json`](../../artifacts/registry/did-freshness-profile-registry.json)
  已登记的 `freshness_profile_id`；不得靠「directory 一类」这样的自然语言猜档，更不得由
  实现方或部署自行编造 id。未知 id、未登记 action 或 method selector 不匹配时，一律按
  `high` tier 的 `synchronous_refresh_or_fail_closed` 处理；**不存在**默认为「任意缓存
  皆可」的路径；registry 只固定 id 与 `risk_tier`，数值窗口仍由部署申报（见本节末）；
- `high` tier 只覆盖登记为 current-DID-dependent 的调用点；principal registration、method successor、
  optional DID-root recovery 与 ongoing governance 的 current 检查属于此列。`high` 不得消费 stale binding，必须同步 refresh 或 fail closed，
  `fresh_for_seconds` 与 `hard_expiry_seconds` 全部有限且
  `0 < fresh_for <= hard_expiry`，没有 stale consumption window；
- `low` 只允许 registry 明列的 accepted-only 只读 / replay 路径：stale 可用且不得因普通
  请求 live fallback（§3 的锚点纪律）；其 profile 可显式允许无 hard expiry；
- `medium` 必须逐 operation 登记，不能定义成「high 与 low 之间」。它可消费 stale 的条件是
  年龄未超过有限的 `stale_grace_seconds`；每次消费 MUST 记录 `stale_evidence_used` 审计并
  调度按 `(did, trust_domain, purpose, policy_digest)` 去重、有上限的后台 refresh；refresh
  失败时保持 degraded / quarantined 标记，不得把 action「降级为 low」；越过 grace 或 hard
  expiry 后 fail closed。数值满足 `0 < fresh_for < stale_grace <= hard_expiry`；
- `fresh_for_seconds` 是唯一 freshness 阈值：`refresh_after = verified_at +
  fresh_for_seconds`，authority 调用的 `max_age` MUST 等于同一值，不得维护两份常量；所有
  窗口都相对 `verified_at` 计算；
- profile 数值由部署以机器可读形式申报，申报 snapshot 进入 §5.3 的
  `profile_policy`——任何数值或行为修改都会结构性失效旧 binding。conformance 读取每个部署
  的申报值，在 `fresh_for-1` / `fresh_for` / `stale_grace` / `stale_grace+1` 边界断言行为，
  并断言 `low` 的 authority call = 0、`medium` 只调度一次后台 refresh、`high` 同步 refresh
  失败即 fail closed；无需全网统一分钟数即可移植。

registry lint MUST 双向验证：所有 `did_authority` 引用的 profile 存在且 evidence class 与 profile
用途相容；所有列入 DID authority call-site 清单的 operation/action 恰有一个引用；未列入的项不得
携带引用。`risk_tier`、动作名称包含 `recovery`/`device` 或自然语言“高风险”均不得参与推导。

### 5.5 limited trust：逐 pin 记录，构造期一致性是协议义务

`history_head` / `version_id` 任一 pin 缺失时，binding MUST 携带 `limited_trust` 记录
（两者皆 pinned 时整个对象省略）：

```text
limited_trust: {
  "history_head": "pinned" | "method_unsupported" | "not_surfaced",
  "version_id":   "pinned" | "method_unsupported" | "not_surfaced"
}
```

- 每个状态 MUST 与对应 pin 字段的实际有无一致；「缺 pin 但未记录」「已全 pin 却记
  非 pinned」「记录与实际矛盾」都 MUST 在构造期拒绝；
- `method_unsupported` 是合法终态（`did:key` 确实没有 history）；`not_surfaced` 是
  resolver 未兑现其 method / profile 能力的**失败态**——§5.2 的 resolver 通道落地后，
  `did:webvh` 的 `not_surfaced` 应当清零而不是被固化；
- 消费规则与 §5.4 联动：`high` 对任何非 pinned 状态 fail closed；`medium` 仅当其 profile
  显式允许对应 pin 缺失、且结果保持 degraded / quarantined、不建立普通 active authority
  binding 时才可继续；`low` accepted-only 路径按已登记规则消费。`method_unsupported`
  不自动代表「足够可信」，仍受 adapter 的 limited-trust profile 与 action profile 上界约束；
- [`identity-did.md`](./identity-did.md) 的 adapter 级 "limited trust profile" 声明是该
  adapter 产生的所有 binding 状态的**上界**；adapter 级声明与 binding 级记录互不替代。

### 5.6 失效索引与 evidence 依赖反查

rotation、deactivation、witness fork、controller / service delegation 变化、Realm resolver
policy 变化和 explicit revocation MUST 使受影响 binding 失效或进入 stale / quarantined。
失效索引至少能按 DID、verification method、history head、trust domain、purpose 与 policy
digest 定位。后台 watcher / refresh 可以主动更新绑定，但不得在失败时把信任降级到另一个 DID
method。

witness 级失效触发（witness 被撤销、witness 组织归属被合并判定、consistency proof 被证伪）
的发起方持有的是**依赖坐标**（witness DID、组织、log head），不是 digest 值，因此：

- binding MUST 携带 `evidence_dependencies`（[`did-binding-contracts.schema.json#/$defs/evidence_dependencies`](../../artifacts/schemas/did-binding-contracts.schema.json)）：
  从 §5.2 receipt **机械提取**的 `witness_dids` / `witness_controlling_organization_dids` /
  `history_heads` 排序去重集合；无 evidence 的 method 为空集；
- 对声明 evidence-bearing 的 method，binding store MUST 支持按 evidence dependency 反查
  受影响 binding（至少 by witness DID），使 witness 级失效可以选择性执行并向审计者解释
  依赖关系；这是新增的 selective-invalidation 合同，本节之前的六维「至少」清单不因此扩大；
- `evidence_digest` MAY 另作点查 selector（已知具体 binding 时点对点失效其 evidence），
  它是便利项，不是 witness 级失效的解法；
- 在依赖记录落地前，`for_did` 粗粒度清扫满足「受影响 binding 必须失效」的安全下界，但其
  连带失效无关 binding 的可用性损失与不可解释性正是本节要求依赖记录的原因。

## 6. 实现分层要求

- Wire / model 层 MUST 用强类型区分 `DidCoreId`、`Did`、`DidUrl` 与 `ak:<kind>:` typed ID；不得把所有
  identifier 长期保留为无类型 `String` 后靠前缀猜测。
- Resolver / verifier 层负责 §4–§5；业务 reducer、projection、query、UI 与 routing 代码只消费
  verified binding 或 accepted auth-state，不直接持有通用网络 resolver。
- Event ingress MUST 对每个签名做密码学验证，但 SHOULD 从 Event 所引用的 RealmCommit / auth-state、
  device authorization、agent signer evidence 或 pinned historical binding 取得 key。只有缺少
  该绑定且 §4 允许建立新信任时才进入 DID 权威验证；否则 fail closed。
- Service endpoint 发现与 DID 控制权验证是两件事。完整 AccountId/ActorId 固定目标服务身份，service resolution 携带
  `AuthenticatedServiceResolution` / current-record ref；验证 record 后得到 `base_url`，再以 `ServiceDescribe`
  作第二跳确认。发现到一个新 endpoint 不会自动证明 service identity 控制权，反过来也不要求每次
  HTTP 请求都重新解析 method history；fresh route cache 是允许的实现优化。已登记为自己 Station
  已验证结果的用途（[`../sync/server-trusted-results.md` §5.8、§5.9](../sync/server-trusted-results.md)）
  由已认证客户端消费结果而非自行解析；本文的历史与 current 验证职责仍留给接纳外部材料的角色。
- 测试 MUST 能证明：普通读写命中已接受 binding 时 resolver 网络调用次数为零；新 DID / 新 key
  / rotation / recovery / invalidation 场景才调用 authority resolver；缓存失效不会让低风险读取
  阻塞或 live fallback。

## 7. 复审核对表

新增或修改 identifier 字段时逐项确认：

1. 它是主体 `did_core_id`、方法解析用 `did`、具体 verification method、普通 typed ID，还是 polymorphic ref；
2. 字段名与 §2 总表及 `id-kind-registry.json` 一致；
3. schema 使用 `did_core_id`、bare `did` 与 DID URL 的正确约束；
4. 业务路径只是使用锚点，还是命中 §4 的显式权威验证触发条件；
5. 若需要验证，purpose、trust domain、freshness、历史时点、缓存与失效条件是否完整；
6. 是否错误地给 device、Realm、Message 等非主体对象发明 DID；
7. 是否把签名验证、session 认证、handle 双向验证或 endpoint TLS 误写成 DID 控制权验证。
