---
title: Handle 与 Claim 证明
status: candidate
normative: true
stability: v1
updated: 2026-07-13
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Handle 是人类可读入口，不是权限主键。
Arkret 使用 DID 作为稳定主体，用可验证 claim / attestation 表达 handle、组织成员、邮箱控制权和其他动态属性。

本文定义：

- handle 格式
- handle 到 DID 的解析
- 双向绑定验证
- 多 handle 场景的 primary handle 选择规则（§3.2.1）
- 事件内 mention reference 与 profile snapshot 的 DID-sealed 形态（§3.8）
- pairwise DID 隐私模型
- 选择性披露 / 不可链接 presentation

## 2. Handle 原则

### 2.1 Handle 不是主键

协议层 MUST NOT 把以下内容作为 grant subject 或 Event actor：

- handle
- 邮箱
- 域名用户名
- 组织命名空间字符串，例如 `alice:google.com`

正确模型：

```text
grant subject = DID
authorization condition = verified claim / attestation
```

### 2.2 Handle 可以迁移

Handle MAY 变更、冻结、迁移或重新绑定。
历史 Event 仍然保留原 DID 作为 actor，因此 handle 被回收不会改变历史责任主体。

### 2.3 标识角色与可见性

实现 MUST 区分以下标识**角色**。这些角色不是按字符串形态划分的：同一字符串可以在不同上下文中扮演不同角色（例如 `alice@example.com` 在通讯录发现阶段是 Connection Identifier；若 holder 主动通过 `alsoKnownAs` 公布则升格为 Handle）。区分点是 **holder 意图、可见性默认与验证路径**，不在字符串本身。实现 MAY 用同一存储承载，但 MUST 在协议输出（DID Document、Realm history、grant subject、MLS credential、directory query 响应）中按角色应用对应可见性规则。

| 角色 | 可见性默认 | 验证路径 | 协议主体 |
| --- | --- | --- | --- |
| Connection Identifier | 关系私有；仅在发现 / 邀请 / consent 阶段使用 | provider 可达性证明 + invite / consent 流程 | 否 |
| Handle | 公开或受限；用于 @mention / 邀请 / 成员添加 / 跨上下文可读寻址 | Directory / Principal Server / Organization DID 签发的 handle claim（canonical `user:domain` + `acct:` alias），解析为 `subject DID` 与可选 `member_delivery_binding` | 否 |
| Agent Selector | 默认受限；仅用于 controller-scoped native personal agent @mention 输入别名 | controller handle claim + `ak.schema.agent_selector_claim.v1`，解析为 agent `subject DID` | 否 |
| Administrative Identifier | 组织本地；不出协议线 | 组织 governance / 内部 Directory | 否 |
| Display Name | UI 展示 | 无 | 否 |
| Principal DID | 公开或 pairwise；按 disclosure policy 控制 | DID resolver + 签名 | 是 |

示例字符串与可能扮演的角色：

- `alice@example.com`、`+86 138...`、通讯录用户名、外部账号 ID → Connection Identifier；若 holder 主动公布可升格为 Handle。
- `@alice:acme.example`、`alice@acme.example`、`alice@alice.dev` → Handle（统一形态，详见 §3）。
- `@alice:acme.example/summary` → Agent Selector；发送前必须归约为 agent DID，`summary` 不是 handle localpart。
- 组织账号、计费账号、客服账号、受管员工编号 → Administrative Identifier。
- `Alice Zhang`、昵称 → Display Name。
- `did:webvh:...`、`did:webvh:z8kSru9qAfd1G7AvcVjggdEKy:...`、`did:key:...` → Principal DID。

规则：

- Connection Identifier 只用于发现、consent、邀请或一次性绑定证明。它不得自动写入 DID Document、Realm history、membership event、grant subject 或 MLS credential。
- Provider、Directory 或 Auth Server 证明某个 connection identifier 可达时，输出仍 MUST 归约为 DID 或 pending invite proof，并带有 purpose、audience、expiry 和 issuer proof。
- 同一 principal 可以为不同 provider、组织或 Realm 使用不同 connection identifier 和 pairwise DID。实现不得要求全局唯一 connection identifier。
- Connection identifier 与 DID 的绑定默认是关系私有状态。除非 holder 明确发布为 handle 或 VC claim，其他 Realm 成员和 federation peer 不得获得该映射。
- 同一字符串从 Connection Identifier 升格为 Handle MUST 经过 holder 显式 disclosure（写入 `alsoKnownAs`、签发 VC claim、或发布到 Directory）；实现不得在用户未授权时自动升格，也不得仅凭 provider 可达性证明把 connection identifier 公开为 handle。
- Handle 只提供寻址和可选默认投递上下文；它不得作为 `actor_id`、grant subject、membership key 或 audit attribution。解析结果必须先归约为 DID 与可验证 claim，加入 Realm 时再物化为 `ak.member.state{join}.delivery_binding`。
- Holder MAY 在 subject-private receive policy 中允许 verified handle claim 作为 first-contact / invite 的 `handle_claim` introduction evidence。该选择只表示"我愿意让别人通过这个 handle 找到并请求联系我"，不等于 consent grant、accepted contact、Realm membership 或 invite authorization；接收方仍 MUST 按 [`../sync/invite-addressing.md`](../sync/invite-addressing.md) §5 的 subject policy 与 Principal Server `receive_policy_constraints` 求交集后决定 drop / quarantine / notify。
- Agent Selector 只提供 native personal agent 的 controller-scoped compose-time 寻址；它不得作为 `actor_id`、grant subject、membership key、delivery key、公开 Directory 搜索 / 列表索引键或 audit attribution。解析结果必须先归约为 agent DID，并受 selector claim 的 visibility / audience / requester policy 约束。
- Administrative Identifier 是组织本地概念。协议层只规定它不得作为协议主体、不得作为 grant subject、不得作为 Event actor、不得在跨组织 federation 输出中泄露；其内部分配、回收和绑定规则由组织 governance 决定，超出本规范范围。
- Display name 是可变 metadata，不得被用于 ACL、grant、audit attribution 或 sender verification。
- OIDC `name` 是部署本地 Display Name 兼容属性，不是 Administrative Identifier，也不是 PCR `actor_profile.display_name` 的协议真相源。Auth / Principal Server MUST NOT 把它无 holder 签名地投影进 profile，也不得用它创建或更新 Contact `petname` / `global_display_name_at_save`。注册引导 MAY 把它作为客户端首次 author `ak.profile.create` 的输入建议，但最终 Event 必须由 holder-authorized signer 签名并通过普通 PCR admission。

## 3. Handle 格式

Handle 是面向用户的可路由人类地址，让客户端用一个易懂字符串完成 @mention、联系人搜索、邀请或"添加成员到 Realm"，同时保持协议主体仍是 DID、投递路径仍是 Realm-scoped `delivery_binding`。

Handle 是统一概念：协议层只有一种 canonical handle 形态、一套解析与验证规则。所谓"自有域名个人 handle"与"组织内部账号地址"在结构上是同一类——区别只在**谁是 issuer**（domain 拥有者自己 vs 组织 / Principal Server），不在字符串形态。

### 3.1 显示形态与 canonical handle

Handle 分两层：**显示形态**面向用户，**canonical handle** 面向协议。两层之间是确定性 normalization。

**显示形态（UI 层）**：

| 形态 | 用途 | 示例 |
| --- | --- | --- |
| `@<localpart>:<domain>` | 默认显示与 @mention；带前导 `@` 与邮箱区分 | `@alice:acme.example`、`@alice:alice.dev` |
| `<localpart>@<domain>` | 联系人框 / 企业目录 / 邮箱风格输入 | `alice@acme.example`、`alice@alice.dev` |

客户端 SHOULD 以 `@<localpart>:<domain>` 作为默认渲染形态。`<localpart>@<domain>` MAY 作为输入别名；客户端在 normalize 阶段消除差异。

**Canonical handle（协议层）**：

| 形态 | 角色 | normative 用途 |
| --- | --- | --- |
| `<localpart>:<domain>` | **主形态** | DID Document `alsoKnownAs` 比对、claim proof 输入、Directory 缓存键、`handle` 字段 |
| `acct:<localpart>@<domain>` | 互通别名（RFC 7565） | 跨 Fediverse / WebFinger 边界对接；只能出现在 `handle_aliases[]`，不作为本协议内部 canonical 比对 |

每个 handle 都有唯一的 `user:domain` 形态。`acct:` MAY 在 claim 的 `handle_aliases[]` 中作为附加字段出现，但 **alsoKnownAs 比对、Directory 缓存键、Realm `delivery_binding` 物化** 一律 MUST 使用 `user:domain` 形态。verifier 收到只含 `acct:` 而无对应 `user:domain` 的 claim 时，MUST 把它视为外部互通别名，不得用它作 Arkret 内部权威 binding。

`handle` 的 wire 形态由 [`string-profiles.schema.json`](../../artifacts/schemas/string-profiles.schema.json) 与 [`handle-claim.schema.json`](../../artifacts/schemas/handle-claim.schema.json) 共同约束：必须是 `<prepared-localpart>:<lowercase-A-label-domain>`。localpart 是 `arkret_human_identifier` 的 Unicode canonical value，不是 IDNA label；domain 才执行 UTS #46。`@<localpart>:<domain>`、`<localpart>@<domain>`、`acct:`、裸 host、U-label domain 与任何可转换但尚未 canonical 的字符串在 `handle` wire 字段中都 MUST 被拒绝。客户端 MAY 在 input preparation API 接受这些输入并向用户回显转换结果，但 canonical receiver / verifier MUST 只验证，不能先改写再验签。

`acct:` alias 按 RFC 7565 构造：prepared localpart 以 UTF-8 编码，对 URI 中非直接允许的 octet 做大写十六进制 percent-encoding；host 使用 canonical A-label；不得携带 port。比较遵循 RFC 3986 的 scheme / host case 与 percent-encoding normalization，不参与 Arkret canonical handle equality。

**与 realm alias 的关系（normative）**：handle 的 `@` sigil 与 realm alias 的 `#` sigil（见 [`discovery/object-addressing.md` §3.3](../discovery/object-addressing.md)）构成同一套人类短地址体系：两者 canonical 形态同为 `<localpart>:<domain>`（不含 sigil），但占据**不相交命名空间**——handle 经 `resolve_handle` 解析为 holder / principal DID，realm alias 经 `resolve_realm` 解析为 `ak:realm:<44-char-token>`。同一 `<localpart>:<domain>` MAY 同时是一个 handle 与一个 realm alias；协议**不要求**二者全局唯一，sigil 在显示 / 输入期区分类型，线上字段凭其类型上下文消歧。`@` 与 `#` 均为展示 + 输入路由 affordance，strip 后才进 wire。

### 3.2 解析结果必含字段

Handle 解析结果（无论来自 Directory、Principal Server、Organization claim 还是 holder 自托管 well-known）MUST 至少包含 `handle`、`subject`、`issuer`、`binding_state`、`proofs` 与 `created_at`；`expires_at` 按 `binding_state` 与 delivery binding 条件必填；`handle_aliases[]` 为 **可选**（optional，与 §3.2.1 表及 §3.7.1 的 MAY 一致），不是必含字段：

- `handle`：canonical `user:domain` handle（主形态）。
- `handle_aliases[]`（可选 / optional）：互通别名，例如 `acct:`；不得参与 Arkret 内部权威比对。缺省时整字段 MAY 省略。
- `subject`：被寻址 handle holder 的 principal DID。
- `issuer`：签发 handle claim 的 DID。详见 §3.4。
- `proofs`：至少一条可验证签名，绑定 `handle`、`subject`、`issuer`、`created_at`。
- `created_at` / `expires_at`：claim 时间边界；`expires_at` 在 `binding_state=verified` 或 claim 携带 `member_delivery_binding` 时 MUST 出现。缺失 `expires_at` 的 claim MUST NOT 计为 `binding_state=verified`，不得进入 verified 候选集。

`subject` 使用 claim / credential 领域的命名，但在 v1 user handle 语义中它是**持有该 handle 的 holder / principal DID**，不是 Realm `actor_id`、Principal Server 内部 `account_id`、组织人事系统 identifier、service DID 或通用资源 id。Arkret v1 core 不把本节的 `handle` 泛化为任意资源 handle；如果后续要定义 organization / service / repository / room 等非用户 handle，必须使用独立 schema 或显式 `resource_kind` profile，不能复用 `ak.schema.handle_claim.v1` 的 `subject` 字段来隐式扩展语义。

本节故意不使用 `actor_id` 作为 handle claim 绑定对象：`actor_id` 是 Realm 内 membership / Event actor 标识，在高隐私 Realm 中 MAY 是 Realm-scoped pairwise DID；同一 holder / principal 可以在不同 Realm 使用不同 `actor_id`，也可以在加入任何 Realm 前先获得 handle claim。handle claim 因此绑定到 holder / principal DID，并在 Realm 内通过当前 effective MemberIdentity 或授权 roster disclosure 建立 `actor_id -> subject_id` 的显示投影。

Handle claim 用于 Realm membership（`intent ∈ {invite, member_add}`）时，**额外** MUST 包含：

- `member_delivery_binding`：该 handle 在投递层提供给 membership builder 的完整投递绑定；其中 `member_delivery_binding.recipient_service_id` 是 Principal Server service DID 的唯一来源。
- `audience`：claim 绑定的目标 Realm ID 或邀请方 service DID；verifier MUST 校验 audience 与当前 invocation 上下文一致。
- `issuer_service_id`（条件必填）：claim 由 Organization 或 Directory 签发时给出实际签名的服务 DID。

### 3.2.1 Primary Handle Selection（normative）

同一 `subject` DID MAY 同时持有多个 active 的 handle claim（不同 issuer、不同 audience、个人 vs 组织、self-issued vs organization-issued 等）。当 renderer / verifier 需要"该 subject 在当前上下文的 primary handle"时，MUST 按下列步骤产生确定性结果。

**确定性输入元组**（normative）：

每次选择 MUST 显式接受一个 `resolution_as_of`（RFC 3339 `Z` 形式时间戳）作为求值时刻。算法是**对下列六元组的纯函数**：

```
(
  subject_id,
  context,                          // 当前 Realm ID / 邀请方 service DID / 解析 invocation
  claim_set_snapshot,               // subject 在 as_of 的 handle_claim 集合(含 as_of 时刻 binding_state)
                                    // 详见下文"claim_set_snapshot 的 as-of 语义"
  policy_snapshot,                  // Realm policy 在 as_of 时刻的 accepted_issuers 顺序与 trust 级别
                                    // 详见下文"policy_snapshot 的 as-of 语义"
  holder_primary_handle_at_as_of,   // 从 subject DID Document(as_of version)
                                    // 提取的 metadata.primary_handle 字段值，字符串或 null
  resolution_as_of                  // RFC 3339 Z 求值时刻
)
```

同一六元组输入在不同 verifier、不同时刻 MUST 得到相同结果。

**`holder_primary_handle_at_as_of` 的求值规则**（normative）：取 `subject_id` 在 `resolution_as_of` 时刻通过 DID resolver 解析得到的 DID Document(含 historical version 解析能力的 DID method，例如 `did:webvh`，MUST 取 as_of 对应的历史 version；不带 history 的 method，verifier MUST 把当前 resolver 返回的 version 作为 snapshot)；从该 Document 提取 `metadata.primary_handle` 字段的字符串值。缺失或字段类型不是字符串时，取 `null`。算法在 §3.2.1 Step 1 "holder-flagged" 层只检查每个候选 `c.handle == holder_primary_handle_at_as_of`，**不**重新读 DID Document——这使 holder flag 成为算法的纯函数输入而不是副作用读取。

`metadata.primary_handle` 是 holder 偏好指针，不是 handle 声明通道。Verifier MUST 先从 signed `ak.schema.handle_claim.v1` 构造 `claim_set_snapshot`；若 DID Document 中的 `metadata.primary_handle` 不在该 snapshot 的 verified candidates 中，MUST 忽略该值。该字段不得创建新 claim、绕过 issuer / audience / trust 过滤，也不得覆盖 §3.2.2 对 profile / identity event 的 handle 声明禁令。

**审计材料**（informative）：实现 SHOULD 在选择结果旁附带 `did_document_snapshot_digest = "sha256:" || hex(sha256(JCS(DID Document at as_of)))` 与 `resolution_as_of`，供下游复算时验证 `holder_primary_handle_at_as_of` 来自正确的 DID Document version。该 digest 是审计校验材料，不是算法输入。

**实现 MAY 进一步内联**：把 `holder_primary_handle_at_as_of` 在 `claim_set_snapshot` 构造阶段就物化为每个 claim 上的派生 `holder_flagged: boolean`(`c.holder_flagged := (c.handle == holder_primary_handle_at_as_of)`)；之后算法只读 `c.holder_flagged`，不再需要单独的 `holder_primary_handle_at_as_of` 输入。这种实现 MUST 保证物化产生的 boolean 在同 as_of 同 DID Document version 下是确定的(即等价 transform)。

注意：同一 `(subject_id, context, claim_set_snapshot, policy_snapshot, holder_primary_handle_at_as_of)` 在**不同** `resolution_as_of` 下可能得出不同结果(claim 生效 / 过期跨越边界、policy 时间限制窗口等)，这是预期行为；该规则只保证整个六元组等同时输出等同。

**`claim_set_snapshot` 的 as-of 语义**（normative）：

`claim_set_snapshot` MUST 是 subject 在 `resolution_as_of` 时刻**当时可见**的 handle_claim 集合，**每个 claim 携带它在该时刻的 `binding_state` 与字段值**——不是查询执行时的"现在"集合。具体语义随用法分两支：

- **实时渲染**（real-time render，例如客户端展示当前 mention）：
  `resolution_as_of` ≈ now，`claim_set_snapshot` 即客户端当前可见的 claim 集合及其当前 binding_state。这是默认情形。
- **历史 replay / audit**（例如重建 "该消息发布时 mention 显示什么"）：
  `resolution_as_of` 是过去某时刻；实现 MUST 构造 as-of snapshot，使 snapshot 中每个 claim 的 `binding_state` 反映 **`resolution_as_of` 时的状态**，**不**用当前的 binding_state。例如:
  - 在 `resolution_as_of` 时是 `verified`、之后被 revoke 的 claim 在 snapshot 中 binding_state 仍是 `verified`（曾在 candidate 集合内）；
  - 在 `resolution_as_of` 之后才签发的 claim **不**进 snapshot（Step 0 `created_at <= resolution_as_of` 已经独立把它过滤掉，as-of snapshot 是更强的双保险——connaissance 一致性 + 时间过滤）；
  - 在 `resolution_as_of` 时是 `pending`、之后转为 `verified` 的 claim 在 snapshot 中 binding_state 是 `pending`(于是 Step 0 排除)。

实现 SHOULD 通过保留 handle_claim event 的历史链（issuer / Directory 把每次 claim 状态变化作为 append-only event 持久化）支撑 as-of snapshot 重建；缺少历史的实现 MUST NOT 用"当前 snapshot + historical as_of"组合复算历史显示，那等价于把当前撤销状态错误回投到历史，违反 §6.1.3 历史归因要求。无法构造 as-of snapshot 时，replay MUST fail closed，不得静默退化为"当前 snapshot"。

**`policy_snapshot` 的 as-of 语义**（normative）：

`policy_snapshot` MUST 同样是 **`resolution_as_of` 时刻 Realm policy 的状态**，**不**是查询执行时的当前 policy。具体语义随用法分两支：

- **实时渲染**：`as_of ≈ now`，`policy_snapshot` 即客户端当前可见的 Realm policy 状态(`accepted_issuers` 顺序与 trust 级别)。
- **历史 replay / audit**：取 `resolution_as_of` 时刻 Realm policy event 链所定义的 `accepted_issuers` 顺序与 trust 级别。如果 Realm 后来调整 policy（重排 `accepted_issuers`、变更 trust 级别、加 / 删 issuer），replay MUST 使用**当时**的 policy 而不是现在的，否则同一历史显示在不同时刻复算会得到不同 primary handle，违反"as-of 复算可重复"原则。

实现 SHOULD 通过 Realm policy event 的 append-only 链支撑 as-of policy 重建；缺少历史的实现 MUST NOT 用"当前 policy + 历史 as_of"组合复算，与 `claim_set_snapshot` 同款约束。无法构造 as-of policy snapshot 时，replay MUST fail closed。

主动 replay 调用方 MAY 显式传入目标 policy version（例如 `policy_version_ref: "ak:event:..."`）覆盖默认行为，前提是该 version 在 as_of 时刻确实是当时 effective 的 policy；实现 MUST 验证传入 version 与 as_of 一致，不一致 MUST 拒绝。

**Step 0 — 候选集预过滤**（normative）：

候选集 = `{ c | c ∈ claim_set_snapshot 且 c.binding_state == "verified" 且 c.created_at <= resolution_as_of 且 c.expires_at > resolution_as_of }`（`binding_state` 取 snapshot 中的 as-of 值），但 `verified` 只有在 §6 的 holder-acceptance 门禁已经通过后才成立。holder acceptance 必须满足下列二者之一：(a) `proofs[]` 至少包含一条 `proof_purpose="holder_acceptance"` 且由 `subject` DID 在 `resolution_as_of` 时有效验证方法签发的 proof；(b) 对公开 handle，按时点解析的 `subject` DID Document `alsoKnownAs` 明确列出同一 canonical `user:domain` handle，且 verifier 已完成 claim→subject 与 document→handle 的双向逐字验证。issuer-only 自述的 `binding_state="verified"`、或未通过这两个分支之一的 claim MUST 在本步骤前降级并排除。再施加：

- **生效时间下界**：`c.created_at <= resolution_as_of` MUST 成立——即在求值时刻该 claim 已被签发；这保证 audit / replay 用历史 `as_of` 时未来才签发的 claim 不会回到候选集，也不会通过 most-recent 抢占展示。`created_at` 是 handle_claim 的签发时刻（见 §5 example），不使用 forbidden 同义别名 `valid_from` / `issued_at`（handle claim 自身命名沿用 `created_at`；候选 schema 内的 `issued_at` 是另一对象，不在此层）。
- **失效时间上界**：`c.expires_at > resolution_as_of` MUST 成立——过期 claim 不参与展示选择。
- **issuer trust + domain-authority filter**：`policy_snapshot.accepted_issuers[]` 的每个 entry MUST 是 `{issuer, authorized_handle_domains, authority_class}`，其中 `issuer` 是 DID，`authorized_handle_domains[]` 是该 issuer 可签发的 canonical A-label 域（精确域或 `*.<domain>` 子域模式），`authority_class ∈ {domain_authority, delegated_issuer, directory_mirror}`。丢弃 issuer 未列入 policy、handle 的 `<domain>` 不在该 entry 授权域、或授权链无法回溯到该域权威根的 claim。该步是**强制前置**；v1 不接受无域作用域的裸 issuer 字符串作为 Realm handle policy。
- **audience scope filter**：丢弃 `c.audience` 存在且与当前 context 互斥（例如 audience 限定为另一 Realm 或另一 service DID）的 claim。`c.audience` 缺失视为"无 audience 限制"，保留在候选集。

**Step 1 — 优先级匹配**：在 Step 0 输出的候选集内，按以下优先级取第一个非空层：

1. **audience-matched**：`c.audience` 与当前调用上下文（target Realm ID 或邀请方 service DID）严格匹配。
2. **holder-flagged**：`c.handle == holder_primary_handle_at_as_of`（holder 主权偏好，源自 DID Document `metadata.primary_handle`，已在确定性输入元组中物化为标量；算法不再重新读 DID Document）。`holder_primary_handle_at_as_of == null` 时此层为空集。
3. **most-recent**：按 `c.created_at` 取最新者。

**Step 2 — Tie-breaker**（确定性收敛）：若 Step 1 选定层内仍有多个候选，按以下顺序消歧：

1. 同一 handle 域内按 `domain_authority`、`delegated_issuer`、`directory_mirror` 的顺序优先；只有 `authority_class` 相同才比较 `c.issuer` 在 policy `accepted_issuers` 列表中的位置；
2. `c.created_at` 较晚者；
3. `claim_digest(c)` 字典序较小者（见下方定义）。`claim_digest` 是 claim 自身的 canonical identifier，不依赖 `proofs[]` 数组顺序——避免 issuer 重新打包 proof 时 tie-breaker 抖动；
4. 若 `claim_digest(c)` 仍同（极小概率：两份候选共享同一 canonical claim），取 `min(c.proofs[].payload_digest)` 字典序较小者作为最后保险。

**`claim_digest(c)` 定义**（normative，本节）：

```
claim_digest(c) = "sha256:" || hex( sha256( JCS( semantic_projection(c) ) ) )
```

其中：

- `JCS` 是 [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785) JSON Canonicalization Scheme；
- `semantic_projection(c)` 是从 `ak.schema.handle_claim.v1` 对象 `c` 中**只保留以下规范语义字段**形成的子对象——其它任何字段(包括 `proofs`、`verified_at`、`challenge`、`additionalProperties` 通道引入的 server-attested hint、Directory 缓存元数据、verifier 本地标注等)**MUST 排除**：

  | 字段 | 来源 | 数组规范化 |
  | --- | --- | --- |
  | `schema` | 必填 discriminator | — |
  | `handle` | 必填，canonical `<localpart>:<domain>` | — |
  | `handle_aliases` | 可选，`acct:` 互通别名 | MUST 按数组元素 lexicographic 排序后参与 canonicalization |
  | `subject` | 必填，holder principal DID | — |
  | `issuer` | 必填，签发方 DID | — |
  | `issuer_service_id` | 可选，实际签名 service DID | — |
  | `claim_kind` | 可选 | — |
  | `visibility` | 可选 | — |
  | `audience` | 可选，binding 受众 | — |
  | `claim_scope` | 可选，scope object | — |
  | `member_delivery_binding` | 可选，投递绑定 | `delivery_modes`(若存在) MUST 按 lexicographic 排序；详见下方 §3.2.1.1 |
  | `claims` | 可选，VC inner claims | **顺序是语义的一部分**——issuer 控制，中间方 reorder 会破坏原 proof，因此 digest 直接按 issuer 提供顺序 canonicalize |
  | `created_at` | 必填，签发时刻 | — |
  | `expires_at` | 可选/条件必填 | — |
  | `source_refs` | 可选，上游真相源 event 引用 | MUST 按 event_ref 字符串 lexicographic 排序后参与 canonicalization；排序只用于确定性 canonicalization，不表达签发时序。 |

  其它字段一律 MUST NOT 进入 `semantic_projection(c)`，即使 wire claim 通过 `additionalProperties: true` 通道携带。

  > **与 [`handle-claim.schema.json`](../../artifacts/schemas/handle-claim.schema.json) property 顺序的关系(消歧)**：本表是 `semantic_projection` 的字段**白名单**，刻意**排除** `challenge`、`verified_at`、`proofs` 等非规范身份字段；这些被排除的字段在 schema 的 property 列表中**仍然存在并占位**(例如 schema 中 `challenge` 排在 `audience` 与 `claim_scope` 之间)，因此本表相邻的 `audience` → `claim_scope` 在原始 schema 中被 `challenge` 隔开。读者**不应**把本表理解为 schema 字段缺失或排序冲突——这是"规范语义投影"与"完整 wire schema"的预期差异。此外 `JCS` 最终按 key 字典序重排，故 `semantic_projection` 内字段的展示顺序不影响 `claim_digest` 计算。

  **`binding_state` 与 `verified_at` 被显式排除**的原因：`binding_state` 是 `resolution_as_of` snapshot 上的有效状态（pending / verified / revoked / expired），会随验证、撤销、过期和历史 replay 时刻变化；`verified_at` 是 §6.0 允许 Directory / Principal Server / 其它中间方写入的 pre-verification hint。若二者进入 `semantic_projection`，同一 issuer 签发的规范 claim 会因中间方、缓存时间或 as-of 时刻不同得到不同 `claim_digest`，破坏 tie-breaker、roster `handle_claim_digests[]` 比对与缓存键稳定性。`claim_digest` 因此只锚定 issuer claim 的规范语义内容；候选集过滤仍 MUST 使用 snapshot 中的 `binding_state` 与时间边界，撤销 / 过期通过 effective claim set 变化体现，而不是改写该 claim 的 digest。

  **`challenge` 被显式排除**的原因：`challenge` 是 verifier / request 级防重放输入，不是 handle claim 的稳定规范身份。proof transcript MAY 继续绑定 challenge、domain 与 verifier，但把 `challenge` 放进 `semantic_projection` 会让同一 handle claim 因不同解析请求得到不同 `claim_digest`，破坏 roster `handle_claim_digests[]` 比对、cache key 与 §3.2.1 tie-breaker 稳定性。

  其它字段排除的整体动因把 `claim_digest` 锚定在 §3.4 / §5 定义的 handle_claim 规范 shape 上，与具体 Directory / Principal Server / cache 层附加的 hint 解耦。

- 输出形态遵循 [`models/common-fields.md` §2](../models/common-fields.md) 的 `<noun>_digest = <alg>:<hex>` 通用 hash 字段命名规则；
- 与 [`artifacts/schemas/member-delivery-binding-candidate.schema.json`](../../artifacts/schemas/member-delivery-binding-candidate.schema.json) 的 `claim_digest` 字段一致：该字段是 `sha256(JCS(semantic_projection(upstream handle claim)))` 的 wire 表示；本节是其 normative 计算定义。

  **wire `claim_digest` 缺失时的退化(normative)**:candidate schema 的 `claim_digest` 字段是 **OPTIONAL**(SHOULD，见 §3.7.1 表)。当 candidate 不携带 wire `claim_digest` 时，Step 2 tie-breaker 与 roster `handle_claim_digests[]` 比对 / 缓存键 **MUST** 改用 verifier 本地按本节公式自算的 `claim_digest(c) = "sha256:" || hex(sha256(JCS(semantic_projection(c))))`——即 tie-breaker 与 audit chain 永不因 wire 字段缺失而出现缺口或非确定收敛(自算值与 issuer 提供值在 candidate 合法时必然相等)。当 wire `claim_digest` **存在**时，verifier SHOULD 校验它等于自算值，不一致 MUST 视为 candidate 不可信并 fail closed(防 issuer 提供与规范语义不符的 digest 污染缓存键 / audit chain)。

**Hint 隔离**(normative): §6.0 server-attested hint、Directory 缓存补字段、verifier 本地标注等任何非规范语义字段 MUST 在 wire claim 上以**顶层附加字段**形式存在(而非污染规范字段)，并**MUST NOT** 进入 `semantic_projection(c)`。该约束让同一语义 handle claim 被任意数量的 Directory / Principal Server 加 hint 后，`claim_digest` 始终稳定；tie-breaker、roster `handle_claim_digests[]` 比对、缓存键命中都不会因 hint 抖动。

去除 `proofs` 与 server-attested hint 是为了让 `claim_digest` 只覆盖 claim 的**规范语义内容**而非签名包装与中间传输态，让同一 canonical claim 在任意 issuer 重签 / Directory 转发 / cache 层加注后始终产生相同 digest。

**Forward-compat**: 未来 spec revision 在 handle_claim.v1 中加入新规范字段时，该字段名 MUST 同步加入上表；实现 MUST 拒绝白名单外字段进入 digest 计算，即便它出现在新 schema 里——直到 spec 显式扩表。同时新字段若是数组，MUST 在加入表的同时声明数组规范化策略(sorted / order-is-semantic 二选一)；未声明的数组字段 MUST NOT 进入 digest。这保证不同 spec patch 版本之间 `claim_digest` 不会悄悄漂移。

#### 3.2.1.1 数组规范化规则（normative）

JCS（RFC 8785）按 issuer 提供顺序保留数组元素，不做重排。`semantic_projection(c)` 中任何**无序集合语义**的数组若让 JCS 直接吃，不同 producer / Directory 输出顺序差异会让 `claim_digest` 抖动。因此 §3.2.1 表中显式标 "sorted" 的数组字段 MUST 在送入 JCS 之前按以下规则排序：

| 数组字段 | 排序规则 | 排序粒度 |
| --- | --- | --- |
| `handle_aliases` | 元素字符串 lexicographic ascending（UTF-8 byte order，与 JCS 字符串排序保持一致） | 顶层数组元素 |
| `source_refs` | 元素 event_ref 字符串 lexicographic ascending（仅用于确定性 canonicalization，不表达签发时序） | 顶层数组元素 |
| `member_delivery_binding.delivery_modes` | 元素枚举字符串 lexicographic ascending（例如 `events` < `key_packages` < `push` < `sync` < `to_device`） | 嵌套数组元素 |

**Order-is-semantic 数组**（保留 issuer 给定顺序，不重排）：

| 数组字段 | 理由 |
| --- | --- |
| `claims` | VC inner claims，顺序由 issuer 控制并在 proof transcript 内绑定；中间方 reorder 会破坏原 proof，因此 digest 直接保留原序 |
| `proofs` | 已被整体排除在 `semantic_projection` 外，不参与 digest |

排序仅作用于 `semantic_projection(c)` 的副本构造，**不**改写 wire claim 本身；wire 上 `handle_aliases` / `source_refs` / `delivery_modes` 等仍按 issuer 原始顺序传输，verifier 只在 digest 计算阶段做规范化排序。这保证：

- issuer 不必为 digest 稳定性而强制规范化输出；
- 不同 verifier / Directory 计算同一 claim 的 `claim_digest` 始终相同；
- wire 层数组顺序与签发顺序之间的对应关系（例如 `source_refs` 上游签发时序）在传输中不被强行抹除。

Step 2 结束后候选 MUST 唯一；实现 MUST NOT 在仍有 tie 时随意选取。

Step 0 候选集为空时，renderer MUST fallback 到 §3.8.2 定义的"解析失败"路径，**不得**任意取一个 handle 显示，**不得**绕过 issuer trust filter。

primary handle 是显示语义；它**不**影响 actor_id 归因、grant subject 或 audit attribution——这些永远来自 `subject_id` 本身。

### 3.2.2 Handle Claim Lifecycle and Acquisition（normative）

Handle 的权威生命周期属于 issuer，不属于用户 profile 或 Realm MemberIdentity event。`ak.profile.update`、`ak.profile.realm_override`、`ak.member.identity.update` 中不得通过任意字段声明、覆盖、撤销或重分配 handle；这些事件最多影响 display name、avatar、subject disclosure 等 UI projection。验证器遇到这些事件中出现的非标准 handle 字段时 MUST 忽略或 schema-reject，不得把它们提升为 verified handle。

Arkret v1 core **不定义**用户注册、handle 申请、邀请审批、管理员通知、管理员审批队列、重签 / 续期、namespace 保留策略、抢注仲裁、多 handle 策略或组织内部身份治理 API。这些流程属于 issuer / Auth Server / 部署本地治理面；不同 Principal Server、Organization 或自托管 issuer 可以按自己的合规、人事、IDP、邀请和审计要求实现。

协议层只规定 consumption contract：

1. 任何进入 Arkret roster、mention、directory resolve、delivery binding 或 UI verified display 的 handle MUST 来自可验证的 signed `ak.schema.handle_claim.v1`，或该 claim 的 digest / reference。
2. issuer / Auth Server / 部署本地 API MAY 让用户选择 handle、提交申请、触发人工审批、由管理员直接分配、续签或撤销；这些 API 的 endpoint、权限模型、通知机制和状态机不属于 v1 core。
3. 这些外部流程一旦要把结果暴露给 Arkret 客户端或其它服务，MUST 输出 `ak.schema.handle_claim.v1`、明确的 revocation evidence、或足以让 Directory / roster 不再返回该 claim 的 issuer-side 状态；不得输出未签名 profile 字段来替代 claim。

已知 `subject` DID 但不知道当前 handle 时，客户端 / renderer MUST 使用 `ak.find.directory.read.list_handles_for_subject` 或 roster 内联 `handle_claims[]` 构造 `claim_set_snapshot`。已知 handle 字符串时，显示 / lookup 场景继续使用 `ak.find.directory.read.resolve_handle`。这两个方向不可互相替代：`resolve_handle` 是 handle → subject，`list_handles_for_subject` 是 subject/context → current visible claims。

contact request / invite / member-add 不再把 `resolve_handle(intent="contact_request" | "invite" | "member_add")` 作为 base 安全路径；正式 invite 寻址见 [`../sync/invite-addressing.md`](../sync/invite-addressing.md) 的 `invite_address + introduction_evidence` 模型，联系人请求见 [`contact-and-direct-conversation.md`](./contact-and-direct-conversation.md) 的 `contact_address + introduction_evidence` 模型。Directory 可选返回的 handle claim / candidate 只能作为 introduction evidence 或 builder evidence，不能替代显式 address、principal locator、receive policy 或 Join Policy 复核。

管理员或 issuer 后期修改 handle 的可见效果由 claim set 变化驱动：issuer 签发新 claim、撤销旧 claim、或改变 binding_state / expiry 后，`ak.find.directory.read.list_handles_for_subject` 和 roster hint MUST 反映新的 effective claim set。客户端 MAY 发布新的 `ak.member.identity.update` 来刷新 display-profile cache，但这不是 handle 变更生效的条件。

### 3.2.3 Registration and Invitation Strands（informative）

常见注册路径都在 Arkret core 之外完成，但进入 Arkret 后遵循同一 claim-led 模型：

- **系统预分配 handle**：用户完成注册 / 首次登录后，Auth Server / issuer bootstrap MAY 直接把 signed `handle_claims[]` 交给客户端或服务端 roster cache。用户无需发 `set_handle` event。
- **管理员邀请允许选择 handle**：邀请链接、pre-registration proof、审批通知和人工审核队列属于 Auth Server / issuer 策略。Arkret 只看到最终签发的 `ak.schema.handle_claim.v1`，或看不到任何 claim。
- **管理员后期修改现有用户 handle**：issuer 撤销 / 过期旧 claim 并签发新 claim。Realm history 中既有 messages、mentions 和 `ak.member.identity.update` 不被改写；当前渲染按新的 claim set 展示，历史 replay 按 as-of claim snapshot 展示。

因此，"用户注册后是否必须主动发包含 handle 的 profile"的答案是 **否**。用户 MAY 发 profile / MemberIdentity 来设置 display name、avatar 或 subject disclosure；handle 只来自 issuer-signed claim。

### 3.3 `member_delivery_binding`

解析结果 MAY 携带 `member_delivery_binding`，其中 `recipient_service_id`、`binding_source`、`service_acceptance_ref`、`policy_event_ref` 和 `delivery_modes` 可直接用于构造 `ak.member.state{membership="join"}.delivery_binding`。Handle claim schema 不允许顶层 `recipient_service_id`、`service_acceptance_ref` 或 `policy_event_ref` 快捷字段；这些 delivery binding 字段必须只从 `member_delivery_binding.*` 读取。

`member_delivery_binding.binding_source` 的合法取值是 `explicit` / `invite` / `join_policy` / `organization_policy` / `realm_policy`。**MUST NOT** 是 `did_document_default`——handle resolution 本身就是 directory-attested 路径，与 DID Document fallback 是两条独立的物化路径，不可在 hint 中混用。

该 hint 是 builder 输入；reducer 仍 MUST 按 [`governance/member-delivery-binding.md`](../governance/member-delivery-binding.md) 独立验证 Realm policy、claim issuer、服务背书和条件必填字段。

### 3.4 Issuer 类型与 holder 控制

Handle 的 issuer 决定它的信任锚点；同一 canonical handle 形态可以由不同类型 issuer 签发，verifier 按 issuer 类型选择验证路径：

| Issuer 类型 | 典型场景 | 验证锚点 |
| --- | --- | --- |
| **Holder DID（self-issued）** | 用户自己控制 `<domain>`，自己运营单用户 Principal Server 或 well-known endpoint。例：`@alice:alice.dev` 由 Alice 的 DID 签发。 | (a) `<domain>` 解析 `https://<domain>/.well-known/arkret/handle?localpart=<localpart>` 或 DNS TXT `_arkret.<domain>` 返回签名 handle claim；(b) holder DID Document `alsoKnownAs` 含对应 `<localpart>:<domain>`；两侧均验签通过。 |
| **Organization DID** | 组织把 handle 签发给员工或受管成员。例：`@alice:acme.example` 由 `did:webvh:zGUwpRSnyVCLzU7upsm9iSwEv:acme.example` 签发给 Alice 个人 DID。 | issuer claim + holder DID Document `alsoKnownAs`（公开 handle）或受限 presentation；audience / scope 限定到目标 Realm / 组织。 |
| **Principal Server service DID** | Principal Server 为它承载的用户签发 handle。例：托管平台 `did:webvh:z3omZGak5a5es84Ph2kfPs4UP:principal.acme.example`。 | claim 由 service DID 签发，service DID 由 Organization DID 委派（DID Document service entry 或 governance attestation）；最终归约到 Organization 信任根。 |
| **受信 Directory DID** | 公共 Directory 索引 handle 并发放短期 routable claim。 | Directory claim + 上游 `source_refs`；`source_refs` MUST 回溯到 `<domain>` 权威 issuer 的有效 signed claim。Directory 是镜像层，不是真相源。 |

**自托管即单用户实例**：用户自己控制域名时，handle 形态仍是 `alice:alice.dev`（或任意 localpart），与组织部署完全一致；只是 issuer 与 holder 是同一个 DID。verifier 解析时按 §5 走 `<domain>` 的 well-known 通道发现 issuer，再走 issuer claim + alsoKnownAs 双向验证——验证路径自然分流，不依赖其它字符串 shape。

### 3.5 公开 vs 受限

Handle 按 holder 披露意图分两类：

- **公开 handle**：holder 主动公开，DID Document MAY 在 `alsoKnownAs` 中列出 canonical `user:domain` handle；issuer 提供的 well-known 或 Directory 响应可对任意 verifier 可见。
- **受限 handle**：例如组织内部账号 `@alice:acme.example` 暗示雇佣关系，默认不进公开 DID Document。它由 issuer 以 `ak.schema.handle_claim.v1` / VC / signed directory response 表达，并按 audience、Realm、organization policy 最小披露。

公开 / 受限之间的差异只在 alsoKnownAs / 公开 directory 的可见性上。两者 wire 形态、双签证据要求、`delivery_binding` 构造规则相同。

受限 handle 的 issuer / Directory / well-known endpoint MUST 在返回 claim 前验证 requester、audience、intent 与 disclosure policy。匿名或未授权调用方查询受限 handle 时，服务 MUST 返回与"不存在该 handle"不可区分的响应（status、错误码、body shape、timing bucket 与 cache headers 不得泄露 not-found / revoked / restricted / unauthorized 的差异），且不得返回 `subject`、`member_delivery_binding`、claim digest 或其它可枚举 hint。Issuer 和 Directory 对 handle 解析、`list_handles_for_subject` 与 well-known 请求均 MUST 实施 per-source / per-account / per-handle 前缀限速；超限时对匿名调用方同样使用不可区分拒绝，内部审计可记录精确原因。

### 3.6 与跨上下文 unlinkability 的关系

`member_delivery_binding.recipient_service_id` 必然在解析结果中暴露 handle 与服务的绑定关系；同一 holder 在两个上下文使用同一公开 DID 时，外部观察者通过 `subject` 字段仍能关联到同一人。**Handle 不提供跨上下文 unlinkability**。

需要不可关联的部署 MUST 为每个上下文使用 pairwise / private DID（见 §10、§11、§16），并在每个 pairwise DID 下独立签发 handle claim。若 handle claim 携带 membership 用途的 `member_delivery_binding.recipient_service_id`，不同 pairwise DID 在需要跨上下文 unlinkability 的部署中也 MUST 使用不可关联的 `recipient_service_id`（独立 service DID、按上下文拆分的 service DID，或提供同等 unlinkability 的隐私中继）。如果两个 pairwise DID 的 claim 复用同一个 `recipient_service_id`，实现 MUST 把这视为显式的可关联部署选择，并在文档 / UI 中披露这些 persona 可通过承载服务 DID 被关联；不得声称该 handle claim 提供跨上下文 unlinkability。pairwise DID 与 handle 是正交机制：handle 解决"易懂寻址 + 可选默认投递"，pairwise DID 解决"跨关系不可关联"。

### 3.7 MemberDeliveryBindingCandidate

`MemberDeliveryBindingCandidate` 是可选 Directory / issuer 输出：它可以来自 `ak.find.directory.read.resolve_handle(intent="member_add" | "invite")` 或受信 issuer 直接签发的 evidence，用于把旧式“用 handle 加成员”的最小证明集合凝固为一个 schema-defined shape，让 Principal Server、SDK builder、Realm reducer、Auth Server 与 directory 之间停止各自拼字符串。Wire schema 见 [`artifacts/schemas/member-delivery-binding-candidate.schema.json`](../../artifacts/schemas/member-delivery-binding-candidate.schema.json)。

该对象既不是 grant，也不是已物化的 `member_delivery_binding`，也不是 base invite delivery 所需的 `invite_address`。它只是**通向**后者的 builder 输入。reducer 在落 `ak.member.state{membership="join"}.delivery_binding` 时仍 MUST 按 [`governance/join-policy.md`](../governance/join-policy.md) 独立验证。

### 3.7.1 字段（normative）

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `subject_id` | DID | MUST | 被寻址主体的 principal DID；最终物化为 `payload.actor_id` / cell subject。 |
| `handle` | canonical handle | MUST | `<localpart>:<domain>`，`<localpart>` 已完成登记版本 RFC 8265 profile preparation。`acct:` / 显示形态 / 裸 host 一律拒绝。 |
| `handle_aliases[]` | `acct:` URI 数组 | MAY | 仅互通别名；不参与权威比对、缓存键或 `delivery_binding` 物化。 |
| `member_delivery_binding` | object | MUST | 与 [`handle-claim.schema.json#/properties/member_delivery_binding`](../../artifacts/schemas/handle-claim.schema.json) 同形，`binding_source` ∈ `explicit` / `invite` / `join_policy` / `organization_policy` / `realm_policy`；MUST NOT 为 `did_document_default`。 |
| `issuer_service_id` | DID | MUST | 实际签发该 candidate 的服务 DID（Directory / Principal Server / Organization service DID）。 |
| `audience` | string | MUST | 目标 Realm ID 或邀请方 service DID；verifier MUST 校验 audience 与当前 invocation 上下文一致。 |
| `issued_at` | timestamp | MUST | RFC 3339 `Z` 形式；issuer 签发该 candidate 的时刻。MUST ≤ `expires_at`；与 `expires_at` 一起界定 candidate 的有效窗口并阻止 MITM 把 `issued_at` 改写以扩大重放窗口。 |
| `expires_at` | timestamp | MUST | RFC 3339 `Z` 形式；过期 candidate MUST 被视为不可用。 |
| `source_refs[]` | event id 数组 | MUST | 至少一条 `ak:event:<44-char-event-token>`，指向 issuer / Directory / Organization 真相源 event；客户端 SHOULD 据此回真相源验签。 |
| `proofs[]` | proof 数组 | MUST | 至少一条 proof，绑定 `handle`、`subject_id`、`member_delivery_binding.recipient_service_id`、`audience`、`issuer_service_id`、`issued_at` 与 `expires_at`。`issued_at` MUST 进入 canonical transcript；缺失即视为重放窗口可篡改并拒绝。 |
| `claim_digest` | `sha256:<hex>` | SHOULD | candidate 上游 handle claim 的 canonical JSON digest，用于缓存键与 audit chain。 |
| `intent` | enum | MUST | `member_add` / `invite`，区分 candidate 的 builder 入口；reducer 不依赖该字段，仅用于审计与遥测。 |

`MemberDeliveryBindingCandidate.subject_id` MUST 等于上游 handle claim 的 `subject`。Raw / generic handle claim 使用 `subject`；进入 membership builder candidate 并作为具体 DID 绑定进 proof transcript 时使用 `subject_id`。

`additionalProperties: false`——unknown 字段 MUST 由 verifier 拒绝，避免静默 widening。

### 3.7.2 来源（normative）

candidate 只能来自以下两类签发路径，且二者都不构成 base invite/member-add 的必经路径：

1. **Directory 解析（可选）**：`ak.find.directory.read.resolve_handle(intent="member_add" \| "invite")` 响应若声明支持 candidate，MUST 把 [`discovery-directory.md` §9.0/§9.1](../discovery/discovery-directory.md) 的 handle 解析与通用结果字段重新打包为 candidate；`source_refs` 取 Directory 响应中的 `source_refs`，`issuer_service_id` 取 Directory service DID 或上游 Organization service DID。
2. **受信 issuer 直接签发**：Organization / Principal Server / 受信 service DID 可以离开 Directory 直接对某 `(handle, subject_id, member_delivery_binding.recipient_service_id, audience)` 组合发签名 candidate，例如随 invite token 内嵌、随 organization-issued member roster 下发。

candidate **不得**直接构造自客户端字符串拼接、UI text、未签名 directory 响应或 cache 残留。任何缺少 `proofs[]` 的对象 MUST NOT 被命名为 candidate。

### 3.7.3 物化公式（normative）

`MemberDeliveryBindingCandidate -> ak.member.state.payload.delivery_binding` 的映射必须是确定性的：

```text
payload.actor_id = candidate.subject_id
payload.delivery_binding.recipient_service_id = candidate.member_delivery_binding.recipient_service_id
payload.delivery_binding.resolved_at = candidate.issued_at   // 唯一确定性取值
payload.delivery_binding.service_acceptance_ref = candidate.member_delivery_binding.service_acceptance_ref
payload.delivery_binding.policy_event_ref = candidate.member_delivery_binding.policy_event_ref
payload.delivery_binding.delivery_modes = candidate.member_delivery_binding.delivery_modes
payload.delivery_binding.binding_source = member-delivery-binding.md §3.1 决策树输出
```

`claim_digest`、`source_refs[]` 与 candidate proof digest SHOULD 进入 member Control Move 的 `refs[]`（`role="attestation"` 或 profile 声明的 role），用于审计和 replay 诊断；它们不得替代 `delivery_binding` 中的规范字段。映射过程中任何缺失字段、过期 candidate、audience 不匹配、issuer 未授权或 Realm `delivery_binding_policy` 不接受该 source，均 MUST fail closed。

### 3.7.4 Validator MUST 规则

verifier 收到 candidate 时 MUST 按下列顺序失败 closed：

1. **schema 合规**：所有 MUST 字段存在；`additionalProperties: false` 不放过未知字段。
2. **`handle` canonical**：必须匹配 `<localpart>:<domain>` 主形态，且 `<localpart>` 已完成登记版本 RFC 8265 profile preparation。verifier 不得在签名 transcript 中接受任何非 canonical 形态；`acct:` 出现在 `handle` 即拒绝。
3. **audience match**：`audience` MUST 等于当前 invocation 上下文（目标 `target_realm_id` / `realm_id` 绑定的 audience，或邀请方 service DID）；不一致 MUST 返回与 "无可披露 claim" 不可区分的统一拒绝。
4. **expiry**：`expires_at` 严格大于当前时间；过期 candidate MUST NOT 进入 builder。
5. **proof 验证**：`proofs[]` 中至少一条由 `issuer_service_id`（或受 issuer 委派的 verification method）签名，且 binding transcript 覆盖 `handle`、`subject_id`、`member_delivery_binding.recipient_service_id`、`audience`、`issuer_service_id`、`issued_at`、`expires_at` 与 `claim_digest`（如有）。任何 transcript 漏掉 `issued_at` 或 `issued_at > expires_at` MUST fail closed，避免 MITM 通过重写时间窗口实施重放。
6. **subject / handle 关联**：candidate 内 `subject_id` MUST 等于上游 handle claim 中的 subject（不允许 verifier 在 builder 入口 "替换" subject）。
7. **`member_delivery_binding.binding_source` 合法值**：MUST 是 §3.3 列出的五种之一；`did_document_default` 即拒绝。

通过上述检查的 candidate 是 builder 的合法输入；reducer 仍 MUST 按 Join Policy 再验签 / 再过审。

### 3.7.5 与 display resolve / mention resolve 的差异

`ak.find.directory.read.resolve_handle` 各 intent 返回的字段不同。candidate 只允许在可选 `member_add` / `invite` intent 下产生，且不得替代 [`../sync/invite-addressing.md`](../sync/invite-addressing.md) 的 base invite address / introduction evidence；`contact_request` intent 只产生可作为 `handle_claim` introduction evidence 的 verified handle claim，不产生 accepted contact 或 consent：

| Intent | 返回字段（必含） | 是否产 candidate | 说明 |
| --- | --- | --- | --- |
| `lookup` / display resolve | `subject`、`handle`、`verified` | 否 | 仅用于显示双向验证状态；不暴露 `audience` 或 `member_delivery_binding`。 |
| `mention` resolve | `subject`、`handle`、`display_name?` | 否 | mention autocomplete 需要的最小字段；MUST NOT 在未授权时披露 `member_delivery_binding`。结果存为 message 内 mention snapshot，不进入 membership builder。 |
| `contact_request` resolve | `subject`、`handle`、`claims[]?`、`member_delivery_binding?` | 否 | 仅用于构造 `ak.peer.contacts.command.submit` 的 `handle_claim` introduction evidence；接收方仍按 subject policy 与 Principal Server `receive_policy_constraints` 决定 drop / quarantine / notify。 |
| `member_add` / `invite` resolve | §3.7.1 全部 MUST 字段 | 可选 | 仅当 caller 已经过授权（共同 Space、Directory policy、organization grant 等）且 Directory 显式支持该 profile 时才返回。Directory 拒绝时使用与 "未发现资源" 不可区分的统一拒绝。 |

实现 MUST NOT 跨 intent 复用结果：以 `mention` 解析拿到的 payload 不得提升为 candidate；以 `member_add` 解析拿到的 candidate 不得被广播到 mention autocomplete 缓存。

### 3.8 Mention Reference 与 Display Snapshot（normative）

事件内对某 subject 的引用——@mention、reply target、quoted profile、forwarded message 的原作者引用、reaction 的目标等——**权威引用字段** MUST 使用 DID-sealed 标识符（`subject_id`），不得用 handle 字符串作为 actor 归因、授权判断、解析路径的唯一来源。同一事件 MAY 同时携带 handle / display name / controller-scoped agent selector 的历史快照作为 audit / search / 兜底展示的 metadata（见 §3.8.1），但这些 metadata 字段不参与协议层信任决策（见 §3.8.3）。

该规则的根本动因：handle 的 `<domain>` 部分是 issuer 的 authority domain（组织 / holder 自己持有的域名），不是 subject 用户控制的标识。如果把 domain 作为**权威**引用字段持久化进每一个引用点，issuer 的 DNS 治理成本（domain 迁移、authority 重命名）就会转嫁给所有历史事件，并被迫做事件改写。DID 才是稳定标识；handle 是该标识的可读 label，由解析层实时计算；事件内的 handle metadata 只是"当时是什么"的 audit 快照，不是"现在是什么"的真相源。

§17 wire-level 作用域规则配套约束了 handle 字符串作为**权威字段**可以出现的位置。MemberIdentity 不再携带 handle 字符串；Realm-scoped roster 若需要加速渲染，只能内联签名 handle claim evidence 或 digest hint（详见 [`sync/client-sync.md` §8.1](../sync/client-sync.md)）。

#### 3.8.1 字段定义

mention reference / profile snapshot 的 normative shape：

| 字段 | 类型 | 必填 | 用途 |
| --- | --- | --- | --- |
| `subject_id` | DID | MUST | 被引用主体；唯一参与 actor 归因、授权判断、解析路径与渲染查找的字段。 |
| `display_name_at_time` | string | MAY | event 时刻 subject 的 display name 快照；持久化、不再更新；renderer MAY 直接显示。 |
| `handle_at_time` | canonical handle string（§3.1 主形态） | MAY | event 时刻 subject 的 handle 快照；**仅** audit / debug / 全文搜索 / 历史回溯用途；**MUST NOT** 作为当前显示标识。 |
| `controller_subject_id` | DID | MAY | 当 mention 由 controller-scoped agent selector `@<controller-handle>/<agent_slug>` 解析而来时，记录 controller principal DID；仅 audit / fallback metadata，权威 target 仍是 `subject_id`。 |
| `controller_handle_at_time` | canonical handle string（§3.1 主形态） | MAY | agent selector 左侧 controller handle 的历史快照；仅 audit / debug / 搜索用途，MUST NOT 作为当前 controller 解析来源。 |
| `agent_slug_at_time` | string | MAY | agent selector 右侧 `agent_slug` 的历史快照；仅 audit / debug / 搜索用途，MUST NOT 作为当前 agent 解析来源。 |
| `mention_text_original` | string | MAY | 用户键入的原始输入（例如 `@alice:acme.com` 或 `alice@acme.example`）；audit 与搜索索引用途，不参与渲染逻辑。 |
| `resolved_at` | timestamp | MAY | 客户端解析 handle / subject / agent selector 时刻；audit metadata。 |

`display_name_at_time` 是 snapshot 语义——一旦写入事件即固定，防止 subject 后续修改 display name 时回写历史（这条边界对反冒充很重要）。`handle_at_time`、`controller_handle_at_time` 与 `agent_slug_at_time` 是 audit metadata，不是显示字段或解析字段。

#### 3.8.2 渲染规则（normative）

UI 渲染 mention / profile reference 时 MUST 按下列流程（`binding_state` 取值范围见 [`models/common-fields.md` §5](../models/common-fields.md)，仅 `pending` / `verified` / `revoked` / `expired` 合法）：

```
1. Realm-scoped projection 优先解析：
   renderer 先构造本次渲染输入对应的 MemberIdentity + handle-claim snapshot：
   - 实时渲染使用当前 effective set；
   - 历史 replay / audit 使用 resolution_as_of 时刻的 as-of effective set；
   - 若实现无法构造对应 as-of snapshot，step 1 失败。
   在该 snapshot 中筛选 subject_id == mention.subject_id 的 MemberIdentity 候选。
   若候选数量不等于 1，step 1 失败（包括并发写入造成同一 actor
   存在多个 effective MemberIdentity 的情况），进入 step 2。
   对唯一候选 M：
   a. 校验 M.asserted_at <= resolution_as_of；
   b. 若 M.expires_at 存在，校验 M.expires_at > resolution_as_of；
   c. 从 roster 内联 `handle_claims[]`、`handle_claim_digests[]` 命中的本地
      claim cache，或同一 response 的 handle-claim evidence 构造
      `claim_set_snapshot`；
   d. 对 `claim_set_snapshot` + 当前 context 运行 §3.2.1 primary handle
      selection；
   e. 通过 a-d 即视为 Realm-scoped projection 解析成功，结果是选中
      handle claim 的 canonical `handle`。
2. 否则 / step 1 失败：
   resolve_primary_handle(subject_id, current_context, resolution_as_of) → handle_claim
   （按 §3.2.1 选择规则，跨 Realm / live Directory / cache，
   返回带 binding_state 的完整 handle_claim 对象；历史 replay / audit
   MUST 使用 resolution_as_of 对应的 claim_set_snapshot / policy_snapshot，
   不得静默 live-resolve 到当前状态）。
3. 显示判定：
   - step 1 成功 → 显示 "@{localpart}:{domain}"（来自选中 handle_claim.handle）；
   - step 2 成功且 handle_claim.binding_state == "verified"
     （或 §6.0 server-attested verified hint 命中且本地 trust policy TTL 内）
     → 显示 "@{localpart}:{domain}"（来自该 handle_claim 的 canonical handle）。
4. 解析失败（DID 不可达 / 无 active claim / §3.2.1 选择不唯一 /
   MemberIdentity snapshot 不可构造或不唯一 / step 1 校验 a-d 任一失败 /
   step 2 binding_state ∈ {pending, revoked, expired}）：
   按以下顺序 fallback：
   a. 本地 cache 中最近一次 verified primary handle（标记 "cached"）
   b. event 内 display_name_at_time（标记 "name only"）
   c. truncated DID 形态（例如 "did:webvh:z2dmj…3kF"，标记 "unresolved"）
5. 任何 fallback path MUST 在 UI 上有明确的视觉降级标识；
   实现 MUST NOT 把 fallback 显示成与正常解析无差别的形态。
```

`resolution_as_of` 是本次渲染选择的解析基准时刻：实时渲染通常是 renderer 解析这一刻；历史 replay / audit 是被重放视图声明的 as-of 时刻。它与 §3.2.1 的确定性六元组配合使用（`subject_id` / `context` / `claim_set_snapshot` / `policy_snapshot` / `holder_primary_handle_at_as_of` / `resolution_as_of`）。`claim_set_snapshot` 与 `policy_snapshot` 都是 as-of snapshot（详见 §3.2.1 normative 段）。同一 mention 在不同时刻可能因 handle claim set 变化、cache TTL、claim 生效或过期边界、DID Document update、Realm policy 调整或 MemberIdentity subject disclosure 变化落入不同分支，这是预期行为而非违反确定性——确定性保证的是六元组等同时输出等同。

renderer **不得**在主显示路径使用 `handle_at_time`。`handle_at_time` 只允许出现在以下场景：

- 显式标记为"历史值"的 audit view（例如"该消息发布时此用户的 handle 为 …"）
- 开发者 / 管理员 debug overlay
- 全文搜索 snippet（让搜索"alice:acme.example"能命中包含该旧 handle 的历史消息）

renderer 检测到 `handle_at_time` 与当前 primary handle 不一致时，MAY 在 UI 上加 "handle changed since" 类提示——这是显示层增强，不是 normative 协议要求。是否提示、提示的具体形式由产品决定。

holder 的实时身份面还 MUST 应用 [`discovery/client-preferences.md` §3.6](../discovery/client-preferences.md) 的全局 Contact `petname` 覆盖层：只有 `subject_id` 能经 verified evidence 唯一归约到 accepted human Contact 的 `peer.principal_id` 时，非空 `petname` 才取代上述 live handle / display fallback 成为主标签，并带“备注”角标；handle、Realm override 与全局 display name转为次要上下文。该覆盖层不改变本节解析结果。

历史 replay / audit / export 仍按 `resolution_as_of` 和事件快照执行本节流程；当前 `petname` 最多作为明确标注的 holder-private name 并列，MUST NOT 覆盖 as-of handle、`display_name_at_time`、`subject_id` 或 audit attribution，也不得写入共享 Event、forward、quote、share 或 Realm export。

#### 3.8.3 与 actor 归因的关系

`display_name_at_time`、`handle_at_time`、`controller_subject_id`、`controller_handle_at_time`、`agent_slug_at_time`、`mention_text_original` 都是 **UI 元数据**，对协议层信任决策完全透明。verifier / reducer / policy engine MUST 忽略这些字段，只读 `subject_id` 做以下判断：

- grant subject 校验
- audit attribution
- membership / Realm 决议
- sender verification
- ACL / capability 校验
- federation peer attribution

也就是说：篡改 mention reference 的元数据字段不构成协议层攻击（最多骗 UI 显示），但篡改 `subject_id` 会被 event envelope 签名直接拒绝。

#### 3.8.4 与 Organization Authority Migration 的关系

因 §3.8 规定权威引用字段一律 DID-sealed，组织 authority domain 迁移（`acme.example → acme.com`）在历史事件层不需要 rewrite：

- 旧事件内的 mention / profile reference 权威字段是 `subject_id`，subject 不变；
- 渲染时按 §3.2.1 解析当前 primary handle，得到新 domain 的 handle 字符串；
- 历史事件本身**不需要**rewrite、migration script 或 schema upgrade；
- 唯一需要的 issuer-side 操作是按 §6 批量重发 handle_claim（new domain），随后 Directory withdraw 旧 entry；当前显示投影随 issuer / Auth Server 刷新路径、`ak.find.directory.read.list_handles_for_subject` 或 roster claim hints 的下一次刷新自然更新，不要求任何 `ak.member.identity.update`。

domain 迁移因此从"全网事件改写工程"降级为"issuer 侧 batch 签名 + claim cache TTL 冷却"。事件内的 `handle_at_time` metadata 与 issuer 的 as-of claim ledger 让 audit 仍可重建任意历史时刻的 handle 字符串。

## 4. Handle 绑定

公开 persona DID MAY 使用：

```json
{
  "alsoKnownAs": [
    "alice:alice.dev",
    "alice:acme.example"
  ]
}
```

Pairwise DID、临时 DID、agent 执行 DID 和隐私敏感关系 DID SHOULD NOT 强制绑定公开 handle。设备自身没有 DID；设备 `verification_method` / `device_id` 同样不得被当作公开 handle 主体。受限 handle 只有在 holder 明确选择公开该上下文关联时才 SHOULD 写入 `alsoKnownAs`；否则必须通过受限 claim / presentation 返回。

### 4.1 `alsoKnownAs` 的窄用途

`alsoKnownAs` 在 Arkret v1 协议层**只承担一件事**：为 §3.4 issuer claim 提供 holder 侧的反向背书，使公开 handle 的双向验证（§6）可独立于任何 issuer / Directory 完成。完整链路是：

```text
issuer claim:        handle → subject_id   (issuer 单方面签名声明)
holder DID Document: subject_id → handle   (列入 alsoKnownAs，holder 单方面承认)
```

没有 holder 侧这条边，任何被信任的 issuer 都可以单方面把 handle "塞" 到受害者 DID 上而 holder 无从拒绝。`alsoKnownAs` 把这种 issuer-unilateral 攻击降级为 issuer × holder 双方均需主动表态——`did:webvh` 等带历史 method 还能让 alsoKnownAs 增删进入可回溯链路，使 holder 的撤销动作具备 audit 证据（§6.1.2 第 3 条）。

`alsoKnownAs` **不参与**以下机制；这些机制各自有专用字段或独立机制：

| 机制 | 权威字段 / 路径 |
| --- | --- |
| Realm 内投递路由 | `ak.member.state{join}.delivery_binding.recipient_service_id` |
| Realm 加成员 / Join Policy | `invite_address` / `principal_locator` / Join Policy evidence；可选 `MemberDeliveryBindingCandidate`（§3.7）+ issuer claim + audience |
| Actor / 签名归因、审计 | Event envelope `actor_id` = DID 本身 |
| Principal Server 搬迁、域名变更 | DID Document `service` entry + service delegation |
| 受限 handle（组织内部账号） | issuer claim + audience + scope（§3.5 默认不进公开 DID Document） |
| Pairwise / agent / 临时 DID；设备 verification method | 显式 SHOULD NOT 写入 `alsoKnownAs`（设备自身没有 DID；见上文与 [identity-did.md](./identity-did.md) §6 末段"Pairwise / private DID SHOULD NOT 包含公开 handle"，以及 §9 验证规则） |
| 跨上下文 unlinkability | pairwise DID 机制，正交于 handle 层（§3.6） |
| Handle 重分配后的历史归因 | 历史 Event 内固化的 `subject` DID 与 display snapshot（§6.1.3） |

实现 MUST NOT 把 `alsoKnownAs` 用作 mention 索引、Directory 主键、缓存键、投递路径或 actor 归因依据；它的唯一规范用途是"public handle 的 holder-side 反向背书"。

## 5. Handle 解析

Handle 解析分为两个方向：

- **handle → subject**：输入是 canonical `handle = <localpart>:<domain>`（或 normalize 自显示形态），使用 `ak.find.directory.read.resolve_handle` 或下列 issuer discovery 路径；invite/member-add 的 base 投递不得依赖该方向。
- **subject/context → current handles**：输入是 `subject` DID、当前 Realm / audience / requester context，使用 `ak.find.directory.read.list_handles_for_subject` 或 roster 内联 `handle_claims[]`。该方向用于 member roster、mention renderer 和 issuer 重签 / 撤销 claim 后的显示刷新。

已知 handle 时，客户端 / verifier 按以下顺序尝试 issuer，第一个成功签发可验证 claim 的就是该 handle 的 issuer：

1. **`<domain>` 的 well-known**：`GET https://<domain>/.well-known/arkret/handle?localpart=<localpart>`。响应是 `ak.schema.handle_claim.v1` 形态的签名 claim。
   - 用于 holder 自托管（domain 拥有者 == subject DID）与单实例 Principal Server 部署。
   - **`.well-known/arkret/handle` 是签名 issuer 通道，不是泛 resolver 端点（normative）。** 该路径的语义被钉死为"返回该 `<domain>` 作为 issuer 为 `<localpart>` 签发的 signed `ak.schema.handle_claim.v1`"。任何在该路径作出响应的部署都被 verifier 当作该 handle 的候选 issuer。因此：
     - 能签发 claim 的 issuer（holder 自托管 well-known、单实例 / 组织 Principal Server）MUST 在此返回 200 + 签名 claim，或返回 issuer-side not-found / revoked 状态；但对匿名或未授权调用方，not-found、revoked、restricted、unauthorized 与 rate-limited MUST 使用不可区分响应，避免把该端点变成 handle / 雇佣关系枚举 oracle。只有已认证且按 policy 有权观察该 claim 的调用方 MAY 获得精确 revoked / expired / not-found 诊断。
     - 受限 handle claim MUST 经 requester / audience 授权后才可由 well-known 返回。授权证据 MAY 是 bearer session、DPoP/device proof、Directory `claim_presentations[]`、Realm invitation / membership context 或 issuer 本地 policy 可验证的等价证明；缺失或验证失败时按上一条不可区分拒绝处理。
     - **纯 resolver（只索引 / 转发、自身签不了 handle claim 的服务）MUST NOT 占用该路径返回未签名的 issuer-probe 结果。** 纯 resolver 在 `.well-known/arkret/handle` 的合规行为只有两种：(a) **不提供该端点 / 返回 `404`**；或 (b) **显式委托**到上游可签发 issuer（例如 HTTP 重定向到该 issuer 的 well-known，或在响应中给出可独立验签的上游 `source_refs` 指向 signed claim）。它 MUST NOT 在该路径返回任何未签名的 handle / subject / probe payload——否则 verifier 会把一个签不了 claim 的服务误当 issuer，污染 §5 的 issuer 选择与 §6 的双向验证。
     - resolver 想暴露"这个 handle 我索引到哪个 subject / issuer"这类 **issuer-probe / 索引查询**，MUST 走产品私有面（私有 API、内部 directory query 等），不得借用 `.well-known/arkret/handle`。需要被 Arkret verifier 采信时，走第 3 步 signed Directory response（`ak.schema.handle_claim.v1` + `source_refs`），而不是未签名 probe。
2. **DNS TXT**：`_arkret.<domain>` 或 `_arkret.<localpart>.<domain>`。仅当 DNSSEC validation 成功**且** TXT 内含可验证签名时才能作为 issuer 通道；裸 DNS TXT 只是发现 hint。
3. **Directory / Organization 服务**：`POST /_arkret/find/directory/resolve-handle`（[`discovery/discovery-directory.md` §9.0](../discovery/discovery-directory.md)）或 `POST /_arkret/find/directory/list-handles-for-subject`（已知 subject 时）。response 仍是签名 `ak.schema.handle_claim.v1`。
4. **Bridge / 外部 issuer**：当 handle 来自 bridge 或外部体系（例如组织自有 IDP），claim 由该体系签发并通过 §7 VC presentation 出示。

解析结果 MUST 包含 §3.2 列出的字段；audience / scope / expiry 决定使用范围。multiple issuer 同时签发同一 handle 时，verifier 先按 §3.2.1 的域授权与 `authority_class` 收敛：有效 `domain_authority` claim 优先于 delegated issuer，二者都优先于 Directory mirror；Directory claim 的 `source_refs` MUST 验证到该域权威根，否则直接排除。只有同一最高 authority class 内仍存在不同 `subject` 的有效 claim 才 MUST fail closed 并交人工处理。低 authority 冲突不得让已经验证的域权威绑定失效，从而避免镜像 issuer 注入冲突造成解析 DoS。

账号侧 claim 管理不走 Directory 搜索，但 v1 core 也不定义账号侧管理 API：当前登录 principal 如何在注册、换设备、管理员修改或 claim 续期后拿到自己的 claims，是 issuer / Auth Server / 部署本地 bootstrap 的职责。Directory 只解析已经签发且对调用方可见的 claims；它不得被当作 handle 申请、审批或管理员治理接口。`ak.find.directory.read.list_handles_for_subject` MUST 应用与 `resolve_handle` 相同的 visibility、audience、requester proof、不可区分拒绝与限速规则；未授权调用方不得通过已知 subject 枚举其受限组织 handle。

Handle 解析示例：

```json
{
  "schema": "ak.schema.handle_claim.v1",
  "handle": "alice:alice.dev",
  "subject": "ak:did_core:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH",
  "issuer": "ak:did_core:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH",
  "binding_state": "verified",
  "created_at": "2026-05-19T00:00:00Z",
  "expires_at": "2026-08-19T00:00:00Z",
  "proofs": [
    {
      "kind": "detached_jws",
      "verification_method": "did:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example#key-1",
      "payload_digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "created_at": "2026-05-19T00:00:00Z",
      "jws": "aaa.bbb.ccc"
    }
  ]
}
```

这是 self-issued handle（holder 自己控制 `alice.dev` 域名，`issuer == subject`）。组织签发 handle 的示例：

```json
{
  "schema": "ak.schema.handle_claim.v1",
  "handle": "alice:acme.example",
  "handle_aliases": [
    "acct:alice@acme.example"
  ],
  "subject": "ak:did_core:webvh:z2dmjA1ice",
  "issuer": "ak:did_core:webvh:zGUwpRSnyVCLzU7upsm9iSwEv",
  "issuer_service_id": "ak:did_core:webvh:z3omZGak5a5es84Ph2kfPs4UP",
  "claim_kind": "organization_handle",
  "visibility": "restricted",
  "binding_state": "verified",
  "audience": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
  "member_delivery_binding": {
    "recipient_service_id": "ak:did_core:webvh:z3omZGak5a5es84Ph2kfPs4UP",
    "service_resolution": {
      "current_record_url": "https://principal.acme.example/_arkret/open/services/ak%3Adid_core%3Awebvh%3Az3omZGak5a5es84Ph2kfPs4UP/resolution"
    },
    "recipient_service_kind": "principal_server",
    "binding_source": "organization_policy",
    "delivery_modes": [
      "events",
      "sync",
      "to_device",
      "push",
      "key_packages"
    ],
    "service_acceptance_ref": "ak:event:AQwfxZZieb7Udz28u8Z_wXvR3hFpZzHl4sWKOICaiKC6",
    "policy_event_ref": "ak:event:AYqLR5FWUtAxcyq2GwRsmHAf_zMFkYrFScSs4ouycARM"
  },
  "created_at": "2026-05-19T00:00:00Z",
  "expires_at": "2026-08-19T00:00:00Z",
  "proofs": [
    {
      "kind": "detached_jws",
      "verification_method": "did:webvh:z3omZGak5a5es84Ph2kfPs4UP:principal.acme.example#key-1",
      "payload_digest": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "created_at": "2026-05-19T00:00:00Z",
      "audience": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
      "jws": "aaa.bbb.ccc"
    }
  ]
}
```

## 6. 双向验证

解析 handle 得到 `subject` DID 与 issuer 后，验证规则按 handle 的公开 / 受限语义分两条：

**公开 handle（holder 主动公开）**：verifier MUST 取得 `subject` DID Document 的当前内容，并验证：

```text
did_document.alsoKnownAs contains the canonical handle
```

"取得当前内容" MAY 通过下列任一方式满足：

- 现场（live）解析 `subject` DID Document；或
- 命中 verifier 自有缓存条目（含 verifier 完全信任、共享同一 DID resolver 与 trust policy 的 co-trusted node，例如自己的 personal node 缓存），且该条目按 §6.1.1 绑定了 DID Document version / digest、`alsoKnownAs` proof，并仍在 TTL 内、未触发 §6.1.2 任何失效信号。

跨信任边界（例如第三方 Directory / 其它组织的 Principal Server）下发的 server-attested `binding_state` 不属于此处可直接满足 MUST 的"缓存条目"——它属于 §6.0 Cache 层的 hint，只能用于明确允许接受 server-attested 结果的展示动作。双向验证失败 MUST NOT 把该 handle 当作公开可信绑定。

**受限 handle（issuer 是 Organization / Principal Server / Directory，holder 未公开）**：handle claim 可能不出现在 holder 公开 DID Document 中；此时 verifier MUST 改为验证：

- issuer claim 签名有效，且 issuer 在当前调用上下文的本地 trust policy 内；
- **holder 侧接受证据存在且有效**（见下方"对称信任"要求）；
- claim `audience` 与当前调用上下文一致；
- claim `challenge` 未过期、未重复使用；
- claim `scope`（Realm、organization、purpose）覆盖当前用途；
- claim `status` / `binding_state` 仍为 `verified`；
- holder consent / organization policy 允许向当前 requester 披露。

**对称信任：受限 handle 的 `verified` 必须有 holder 侧背书（normative）**：公开 handle 的 `verified` 靠 `alsoKnownAs`（§4.1）提供 holder 侧反向背书，把 issuer-unilateral 攻击降级为 issuer × holder 双方均需表态。受限 handle 不进公开 `alsoKnownAs`（出于 unlinkability / 最小披露），但**不得因此免除 holder 侧背书**——否则 `accepted_issuers` 内任一被攻陷 / 恶意 issuer 即可签 `subject = 受害者真实 DID` 的 verified claim，在其 audience 内冒名受害者。因此:**当 claim 的 `subject` 是 issuer 不控制的 DID 时，受限 handle 要显示为 `verified` / 驱动任何信任决策（grant 条件、roster 强归因、delivery binding），其 `proofs[]` MUST 同时包含一条由 `subject` DID 控制的验证方法签发、覆盖 `(handle, subject, audience, claim_scope)` 的 holder-acceptance proof**（即 holder 在该 audience/scope 内显式接受被绑定）。verifier MUST 用 `subject` DID Document 当前 verification method 验证该 holder proof。

- 缺少有效 holder-acceptance proof 时，该受限 handle MUST 至多被当作 `binding_state` 低于 `verified` 的 **issuer-attested**（issuer 单方声明、未经 holder 确认）：verifier MUST 拒绝把它纳入 verified candidate（`reason=handle_holder_acceptance_missing`），UI MUST NOT 显示为 verified，且 MUST NOT 用它驱动 grant 条件、roster 强归因或 delivery binding。
- **issuer 自管 DID 例外(非豁免)**：当 `subject` DID 由 issuer 自己控制（受管 DID 配发，例：组织为新员工铸 `did:webvh` 并签发 `@alice:acme.example`）时，issuer 本就能用 `subject` DID 的密钥产出 holder-acceptance proof，故该要求对正常组织配发**自动满足**、不增加摩擦；它只在 `subject` 是外部 / 既有 DID 时真正生效，而那正是冒名风险所在。

DID Document 缺失 `alsoKnownAs` 单独**不**构成"受限 handle 无效"的判定（受限 handle 本就不进公开 `alsoKnownAs`）；但缺少上述 holder-acceptance proof（且 `subject` 非 issuer 自管）则 MUST NOT 显示为 verified。判定 = issuer claim 验签链 + holder-acceptance proof + audience / scope 校验。

### 6.0 验证职责分工

"verifier" 是任何**正在做信任决策**的节点。`alsoKnownAs` 双向验证的真相源永远是 holder 自己的 DID Document，因此 authority 与 cache 必须分开：

**Authority（first-party 验证，MUST）**：以下信任决策 MUST 由发起方亲自完成双向验证，**不得**用 server-attested `binding_state` 替代亲自解析 DID Document：

- Wallet 决定是否对某 verifier 披露某 handle（disclosure policy 匹配）；
- 接受 invite、加入 official Realm、接纳 self-issued handle、跨组织 federation 信任决策；
- 任何把双向验证结果记入 audit trail 的动作。

**Pre-verification & Cache（hint 层，SHOULD first-party；MAY use bounded cache）**：Directory / Principal Server / 其它中间方 MAY 代行一次验证并把结果（含 DID Document digest / version、`alsoKnownAs` proof、`verified_at` / `expires_at`）写进 directory entry 或 handle claim 作为 hint。下列展示类动作适用此层：

- 客户端展示 "verified handle ✓" 徽章、mention autocomplete、联系人卡片上的 verified 状态。

规则：

- 这种 server-attested `binding_state` 是性能 hint，**不是**权威背书；
- verifier MUST 能用自己的 DID resolver 独立 re-verify（按 §6 顶层取得 `subject` DID Document 当前内容并复算 `alsoKnownAs` 包含校验），不得仅凭 server-attested `binding_state` 字段做信任决策。独立 re-verify 在首次接受 claim、claim / document digest 变化、撤销 / invalidation 或本地 freshness policy 到期时执行；普通展示与命中同一 accepted binding 的业务使用 MUST 复用验证结果，不得每次在线解析。Server-attested hint 携带的附加字段（例如 DID Document digest 副本、`alsoKnownAs` proof 副本）是实现可选优化，v1 不为此层定义规范 wire schema；不同实现的 hint 字段差异不影响互操作，因为 verifier 始终保留按需独立 re-verify 路径；
- 上述展示类动作 SHOULD 优先 first-party 验证；MAY 接受 server-attested `binding_state=verified` 命中，并把 UI 状态展示为 verified（cache hit 与 first-party verified 之间不做用户可见区分），前提是 hint 仍在 verifier 本地 trust policy 允许的 TTL 上限内、未触发 §6.1.2 失效信号；
- **verified 徽章 vs 纯 autocomplete 区分（normative）**：联系人卡片 / 个人资料页面上的 **verified 徽章** 是用户信任决策的关键视觉信号，其防伪强度 SHOULD 高于纯 mention autocomplete 排序提示。客户端 **SHOULD** 在展示 verified 徽章前执行一次 first-party re-verify（§6 顶层独立 re-verify 路径）；当徽章仅由 hint-only 命中(未经本次 first-party 验证)驱动时，客户端 SHOULD 对该徽章施加弱化视觉（例如"服务器声明，未本地核验"的次级标识）而非与 first-party verified 徽章不可区分地呈现，以避免下一条所述"被攻陷 Directory + 受信 issuer 串通"直接驱动一个用户无法分辨真伪的强信任徽章。纯 mention autocomplete 排序 MAY 继续仅依赖 hint，无需为排序结果执行 first-party re-verify；
- 命中超期、§6.1.2 任一失效信号触发、或 verifier 本地 trust policy 拒绝该 hint 来源时，UI MUST 降级为 `unverified` 或等价的视觉降级状态，**不得**继续展示 verified 徽章；
- 一个被攻陷的 Directory 与一个被信任的 issuer 串通可以伪造 server-attested verified 状态——这是把展示动作放在 SHOULD/MAY 而非 MUST 层的根本风险；Authority 层动作不允许承担此风险。

Principal Server 在自己的职责范围内（事件接收 / 路由 / 投递 / Realm reducer 决策）**不读** `alsoKnownAs`——这些决策的权威字段是 `delivery_binding.recipient_service_id`、`MemberDeliveryBindingCandidate` 与 issuer claim（见 §4.1 与 §3.7）。Principal Server 出现在本节 cache 层的角色是"为它服务的客户端预解析公开 handle 并维护缓存"，与它作为 Realm 投递与 reducer 节点的角色互不替代。

**DNS TXT 通道**：DNS TXT 只能作为发现通道。若 issuer 通过 DNS TXT 直接声明 handle 绑定，客户端 MUST 满足以下至少一项才可显示为 verified：

- DNSSEC validation 成功，且 TXT 内容绑定 `handle`、`subject`、issuer、`created_at`、`expires_at` 和 signature / hash commitment。
- TXT 记录内的绑定声明由 issuer DID（holder DID 或 Organization DID 或受信 issuer）签名，客户端能通过 DID resolver / VC 验证该签名。
- HTTPS well-known 或 Directory / VC presentation 提供等价的签名绑定证据。

未启用 DNSSEC 且没有可验证签名的 DNS 结果只能作为 unverified discovery hint，MUST NOT 作为 grant subject、Organization membership、official Realm 或 verified handle 的依据。

### 6.1 缓存与失效

Handle 解析结果是带时间边界的绑定，不是永久身份事实。

#### 6.1.1 缓存规则

- verified handle cache MUST 绑定 `handle`（canonical `user:domain` 形态）、`subject`、issuer、DID Document version / digest、alsoKnownAs proof、issuer proof、verified_at、expires_at 和 resolver policy。claim 同时携带 `handle` 与 `handle_aliases[]` 时，缓存键 MUST 取 `handle`；`acct:` alias 只作为附加索引，但仍指向同一 cache entry。
- alias lookup 命中缓存时，verifier MUST 跳转到 canonical `handle` 的 freshness re-check 路径：重新检查 TTL、issuer revocation、DID Document digest / version、alsoKnownAs proof 与 resolver policy。实现不得把 `handle_aliases[]` 中的 `acct:` 或其它互通别名当作独立 cache key 直接返回 verified claim，也不得为 alias 单独延长 freshness window。
- handle cache 若含 `member_delivery_binding`，还 MUST 绑定 `member_delivery_binding.recipient_service_id`、claim digest、audience / scope、`service_acceptance_ref` / `policy_event_ref`（如有）；缓存结果不得跨 Realm 或跨组织上下文复用，除非 claim 明确授权。
- DNS / HTTPS 解析结果的 TTL **MUST NOT** 超过以下各项中的最小值：底层 DNS TTL、HTTPS response cache headers、签名绑定 `expires_at`、DID Document cache TTL 和本地 resolver policy 上限。未提供 TTL 时，verified cache **SHOULD NOT** 超过 24 小时；高风险授权或组织背书 SHOULD 使用更短 TTL 或实时 status check。
- 当 DID Document 移除对应 `alsoKnownAs`、issuer claim 被 revoke / expired、well-known 绑定变更、DNSSEC validation 失败、handle 被解析到不同 DID、或 resolver policy 更新时，缓存 MUST 失效或降级为 unverified。

#### 6.1.2 撤销与失效信号

v1 不引入专门的 handle 撤销 event。撤销通过下列三条独立路径完成，客户端 / Directory / Principal Server 任一通道发现失效即 MUST 同步本地缓存：

1. **TTL 自然过期**：缓存到达 `expires_at` 后 MUST 重新拉取；不得在 TTL 之外使用。
2. **Directory withdrawal**：handle issuer 通过 [`ak.find.directory.command.withdraw`](../discovery/discovery-directory.md) 撤回该 handle 的 directory entry；订阅该 handle 的客户端在下一次 directory refresh 或 withdraw notification 收到后 MUST 立即失效缓存。
3. **DID Document 变化**：holder 移除 `alsoKnownAs` 中的 canonical handle，或 issuer claim 被 revoke / `binding_state=revoked`、`binding_state=expired`；下一次 verify pass 失败时 MUST 失效。

handle issuer SHOULD 把 cache 失效信号与 TTL 一起使用：发布短 TTL（≤1h）的高变更 handle、配合 Directory withdraw 主动通知。**v1 不要求**服务端推送 handle 失效事件；客户端 MUST 按 TTL + 上述三路径处理失效，**不得**依赖未注册的 `ak.handle.*` wire kind。

#### 6.1.3 Handle 重分配与历史归因

handle 字符串可以在 issuer 治理下被重分配到不同 DID（典型场景：员工离职后 localpart 被分配给新员工）。重分配 normative 规则：

- **DID 与签名责任不可改写**：Handle 转让或重分配 MUST NOT 改变历史 Event 的 actor DID、签名责任或 audit attribution。授权、grant subject、membership、MLS credential 与 audit attribution MUST 使用 DID / verified claim，而不是缓存中的 handle 字符串。
- **历史 mention 显示**：mention 与 profile reference 在事件中的**权威引用字段**只持有 `subject_id`（详见 §3.8）；handle 字符串只能作为 §3.8.1 定义的 audit / search metadata（`handle_at_time` / `mention_text_original`）出现。渲染历史 mention / message text 时，UI MUST 按 §3.8.2 实时解析 primary handle 显示，**不得**用事件内 `handle_at_time`（若存在）作为当前显示值。handle reassignment 的语义自然结果是：旧消息里 `@alice:acme.example` 这条 mention 解析到的 `subject_id` 仍是原 Alice，渲染时显示她**当前的** primary handle；新拿到 `alice` localpart 的人是一个不同的 `subject_id`，不会被回填进历史 mention。若 renderer 检测到事件内 `handle_at_time` 与当前 primary handle 不一致，MAY 加 "handle changed since" 提示（显示层增强，非 normative）。
- **新分配生效**：新持有者拿到 handle 后 MUST 通过 issuer 重新发布 handle claim（新 `subject`、新 `created_at`、独立的 `service_acceptance_ref`）；旧 claim 的所有缓存按 §6.1.2 失效。
- **跨投递的 cascade**：handle 重分配不自动迁移既有 Realm `delivery_binding`——旧 binding 仍按 `ak.member.state{join}` 内固化的 `subject` DID 投递。新持有者要加入同一 Realm 需要走完整 join 流程并签发新的 `delivery_binding`。

## 7. Verified Claim

Handle、组织成员、邮箱控制权和角色 SHOULD 通过 credential / attestation 表达。

授权判断 MUST 检查：

- issuer 是否被目标 Realm / Policy 信任
- subject DID 是否匹配当前 actor
- claim 是否在有效期内
- claim 是否未撤销
- claim 内容是否满足 grant constraint
- presentation 是否绑定当前 verifier challenge / domain
- 若 claim 携带 `member_delivery_binding`，其 `recipient_service_id` 是否被 issuer 授权、被 Realm policy 接受，并能作为 `delivery_binding.recipient_service_id` 通过 Join Policy 校验。

## 8. 隐私保护型 Handle 证明

DID Document MUST NOT 被用作跨组织身份画像。公开或半公开 DID Document MUST NOT 直接列出以下信息，除非主体明确希望这些信息被关联：

- `alice@google.com`
- `alice@facebook.com`
- 第三方 profile URL
- 跨组织账号名
- 受限 handle 到 `member_delivery_binding.recipient_service_id` 的映射
- 可关联多个 persona 的相同 service endpoint
- 可关联多个 persona 的相同 verification method

## 9. 标准依据

本设计与以下 W3C 文档一致：

- DID Core 隐私章节要求公开 DID Document 避免个人数据，并提醒 service endpoint、verification method 复用会带来关联风险。
- DID Core 建议使用 pairwise DID 降低跨关系关联。
- VC Data Model v2.0 定义 selective disclosure、unlinkable disclosure，并说明 zero-knowledge proof mechanism 可用于证明而不披露全部属性。
- VC DI BBS Cryptosuites 定义 `bbs-2023` base proof、derived proof、selective pointers 和 unlinkable proof 机制。

## 10. 推荐方案：Google 与 Facebook Handle

对 `alice@google.com` 和 `alice@facebook.com`：

1. Alice 为 Google 关系使用 `did:key:z6Mkgpairwise...`
2. Alice 为 Facebook 关系使用 `did:key:z6Mkfpairwise...`
3. 两个 DID MUST NOT 复用相同 verification method、专用 service endpoint、endpoint 用户名、`alsoKnownAs` 或公开 profile URL
4. Google 或受信 issuer 给 `did:key:z6Mkgpairwise...` 签发 `ArkretOrgMembershipCredential`
5. Facebook 或受信 issuer 给 `did:key:z6Mkfpairwise...` 签发独立 credential
6. 面向 Google verifier 时，wallet 只生成 Google 相关 presentation
7. Google verifier MUST NOT 要求披露 Facebook credential、Facebook DID 或跨域 subject identifier

## 11. Credential 示例

如果 verifier 只需要知道“该主体拥有 Google 组织内有效账号”，presentation SHOULD 披露抽象 claim：

```json
{
  "type": ["verifiable_credential", "arkret_org_membership_credential"],
  "issuer": "did:webvh:z3HmjyqtBNmTZXtJQsQQqpBnX:google.example",
  "credentialSubject": {
    "id": "did:key:z6Mkgpairwise...",
    "org": "did:webvh:z3HmjyqtBNmTZXtJQsQQqpBnX:google.example",
    "member": true,
    "handle_verified": true
  },
  "validFrom": "2026-04-26T00:00:00Z",
  "validUntil": "2026-07-26T00:00:00Z",
  "credentialStatus": {
    "type": "privacy_preserving_status_list"
  }
}
```

如果确实需要显示 Google handle，presentation MAY 披露：

```json
{
  "credentialSubject": {
    "id": "did:key:z6Mkgpairwise...",
    "handle": "alice@google.com",
    "handle_verified": true
  }
}
```

该 disclosure MUST 绑定单一 verifier challenge / domain，并且 MUST NOT 自动披露其他组织 handle。

## 12. Presentation Request

Verifier MUST 使用最小披露请求，不得请求“所有 alias”或“所有账号”。

```json
{
  "type": "arkret_presentation_request",
  "audience": "did:webvh:z3HmjyqtBNmTZXtJQsQQqpBnX:google.example",
  "domain": "google.example",
  "challenge": "ak.chal_01J...",
  "accepted_issuers": [
    "did:webvh:z3HmjyqtBNmTZXtJQsQQqpBnX:google.example",
    "did:webvh:z63bVQgiDj3vkHkgjzVuvJdte:trusted-hr.example"
  ],
  "required_claims": [
    {
      "type": "arkret_org_membership_credential",
      "constraints": {
        "org": "did:webvh:z3HmjyqtBNmTZXtJQsQQqpBnX:google.example",
        "member": true
      },
      "disclosure": "abstract"
    }
  ],
  "forbidden_claims": [
    "other_handles",
    "external_accounts",
    "global_strand_identifier"
  ]
}
```

Wallet MUST 展示将要披露的 claim。
Wallet SHOULD 拒绝或警告请求无关 handle、global subject identifier、credential id 或不必要人口属性的 presentation request。

## 13. Proof Profile

Arkret SHOULD 支持：

- `sd_jwt_vc`：适合广泛 JOSE 互操作和 claim 级选择性披露
- `vc_di_bbs_2023`：适合需要不可链接 derived proof 的高隐私场景

需要不可链接 presentation 时，MUST 使用实际支持 unlinkability 的 proof mechanism。实现不得仅因为使用 VC 就宣称零知识或不可链接。

使用 `vc_di_bbs_2023` 时：

- issuer 创建 base proof 并只交给 holder
- holder 使用 selected claim pointers 创建 derived proof
- verifier 验证 derived proof、issuer key、challenge、domain 和 audience
- verifier MUST NOT 收到未披露 claim、base proof 或无关 credential identifier

## 14. Status 与撤销

Credential status check MUST 避免 verifier 驱动的关联追踪。

实现 SHOULD 使用：

- privacy-preserving status list
- cached status material
- verifier-independent revocation proof

实现 SHOULD NOT 要求 verifier 在每次 presentation 时把唯一 credential id、subject DID 或 handle 提交给中心化 status endpoint。

## 15. 授权语义

Capability policy MAY 依赖 verified claim，但 grant subject 仍然是 DID。

正确：

```text
grant subject = did:key:z6Mkgpairwise...
condition = has valid arkret_org_membership_credential where org = did:webvh:z3HmjyqtBNmTZXtJQsQQqpBnX:google.example
```

错误：

```text
grant subject = alice@google.com
```

如果 holder 后续为另一个组织出示不同 pairwise DID，除非 holder 显式提供 linking proof，否则 verifier MUST 将其视为独立隐私上下文。

## 16. Progressive Disclosure（渐进披露）

本节定义 Arkret 隐私信息渐进披露的端到端实现方案。渐进披露用于让 holder 只向特定 verifier / organization 披露完成某项验证所需的最小身份信息，例如：

- 对 Google 披露 `alice@google.com`
- 对 Facebook 披露 `alice@facebook.com`
- 对某 Realm 只证明"我是某组织当前成员"，不披露具体 handle
- 对某 verifier 证明年龄、角色、认证等级、设备可信度等属性

核心原则：

- DID Document 不承载跨组织身份画像。
- Handle 不是权限主键。
- 披露决策在 holder wallet 本地完成。
- 原始 credential、base proof、pairwise key 和 disclosure policy 默认只保存在 holder 私有域。
- TSP 是可选私密传输层，不是披露策略引擎。

### 16.1 参与方

| 角色 | 定义 |
| --- | --- |
| Holder | 持有 credential、handle claim、pairwise DID 和 disclosure policy 的主体。 |
| Wallet | Holder 控制的本地或私有同步组件，负责策略匹配、proof 派生、发送和 receipt 保存。 |
| Issuer | 签发 credential / claim / attestation 的组织或服务。 |
| Verifier | 请求 presentation 的服务、组织、Realm、Applet 或 agent。 |
| Represented Organization | Verifier 声称代表的组织 DID / VID。 |
| Transport | TSP、HTTP/JWE、DIDComm-like envelope、to-device、MLS DM 等 presentation 传输方式。 |

### 16.2 数据对象

#### 16.2.1 Presentation Request

```json
{
  "kind": "ak.identity.presentation_request",
  "request_id": "ak:request:d8764019-0000-7000-8000-000000000000",
  "verifier_service_id": "did:webvh:zGZ728E4hbEuyDPggPzuioG6n:login.google.example",
  "represented_org": "did:webvh:z3HmjyqtBNmTZXtJQsQQqpBnX:google.example",
  "domain": "google.example",
  "challenge": "ak.chal_01J...",
  "purpose": "space_join",
  "accepted_issuers": ["did:webvh:z3HmjyqtBNmTZXtJQsQQqpBnX:google.example"],
  "required_claims": [
    {
      "claim_kind": "arkret_org_membership_credential",
      "constraints": {
        "org": "did:webvh:z3HmjyqtBNmTZXtJQsQQqpBnX:google.example",
        "member": true
      },
      "disclosure": "abstract"
    }
  ],
  "optional_claims": [
    {
      "claim_kind": "verified_handle",
      "fields": ["handle"],
      "disclosure": "explicit"
    }
  ],
  "forbidden_claims": [
    "other_handles",
    "external_accounts",
    "global_strand_identifier",
    "credential_id"
  ],
  "transport_hints": ["tsp", "http_jwe", "didcomm_like"],
  "expires_at": "2026-04-26T00:05:00Z"
}
```

Verifier MUST 对该请求签名，或通过已认证的关系通道发送。Wallet MUST 把响应中的 proof 绑定到 `challenge`、`domain`、`verifier_service_id` 和 `represented_org`。

#### 16.2.2 Disclosure Policy

```json
{
  "kind": "ak.identity.disclosure_policy",
  "policy_id": "ak:policy:a1cb0019-0000-7000-8000-000000000000",
  "holder_principal_id": "did:webvh:z64Hmi2jCpmp1cUuWEwCgdNn5:holder.example.com",
  "audience": {
    "org_did": "did:webvh:z3HmjyqtBNmTZXtJQsQQqpBnX:google.example",
    "verifier_service_ids": ["did:webvh:zGZ728E4hbEuyDPggPzuioG6n:login.google.example"],
    "tsp_vids": ["did:webs:google.example:verifier"]
  },
  "allowed_claims": [
    {
      "claim_kind": "verified_handle",
      "issuer": "did:webvh:z3HmjyqtBNmTZXtJQsQQqpBnX:google.example",
      "subject_id": "ak:did_core:key:z6Mkgpairwise...",
      "disclosure": "explicit",
      "fields": ["handle"],
      "value_constraints": {
        "handle": "alice@google.com"
      }
    }
  ],
  "forbidden_fields": [
    "other_handles",
    "external_accounts",
    "global_strand_identifier",
    "credential_id"
  ],
  "user_consent_required": true,
  "expires_at": "2026-07-26T00:00:00Z"
}
```

Disclosure policy 是 holder-private state，默认 MUST NOT 写入公共 Realm。

#### 16.2.3 Presentation Response

```json
{
  "kind": "ak.identity.presentation_response",
  "request_id": "ak:request:d8764019-0000-7000-8000-000000000000",
  "holder_subject": "did:key:z6Mkgpairwise...",
  "proof_profile": "vc_di_bbs_2023",
  "presentation": {},
  "disclosed_fields": [
    "credentialSubject.org",
    "credentialSubject.member",
    "credentialSubject.handle_verified"
  ],
  "presentation_digest": "sha256:...",
  "created_at": "2026-04-26T00:00:00Z"
}
```

Response MUST NOT 包含未披露字段、base proof、无关的 credential identifier、其他组织的 handle 或全局 subject identifier。

##### 16.2.3.1 Managed Agent requested-scope 私有披露 profile（normative）

当 authorizing verifier 需要判定 managed Agent 的 immutable global ceiling 时，MUST 使用本节 presentation 流程请求 `claim_kind="ak.schema.agent_requested_scope_disclosure.v1"`，并在 `constraints` 中绑定 `agent_id` 与 Agent DID accepted-at `requested_scope_digest`。请求 MUST 携带精确 `verifier_service_id`、`domain`/operation audience、不可预测 `challenge`、唯一 `request_id` 与不超过 300 秒的接收窗口；controller wallet 的 `presentation` MUST 是 [`agent-requested-scope-disclosure.schema.json`](../../artifacts/schemas/agent-requested-scope-disclosure.schema.json) 的闭合对象。该对象的 controller proof、digest 与 accepted-at DID commitment 验证规则见 [`key-management.md` §4.1](./key-management.md) 和 [`../authz/capabilities.md` §9.1](../authz/capabilities.md)。

这是把完整 scope 定向披露给判定方的私有 profile，不是把 scope 发布为 credential registry 或 Realm fact。Transport MUST 是 TSP、HTTP/JWE、DIDComm-like、to-device、MLS DM 或安全性等价的 authenticated confidential channel；普通明文 HTTP、公开 DID URL、公开 Blob、Realm plaintext Event 与 notification payload 均不得承载该对象。Verifier MUST 原子消费 `(verifier_service_id, request_id, challenge)`；同一 wire presentation 重放、错 audience/verifier 或过期窗口全部 fail closed。成功接收后的缓存只属于 verifier 私域，不得被另一 verifier 当作其自己的 presentation。

#### 16.2.4 Disclosure Receipt

```json
{
  "kind": "ak.identity.disclosure_receipt",
  "receipt_id": "ak:receipt:a1cb0019-0000-7000-8000-000000000000",
  "request_id": "ak:request:d8764019-0000-7000-8000-000000000000",
  "holder_principal_id": "did:key:z6Mkgpairwise...",
  "verifier_service_id": "did:webvh:zGZ728E4hbEuyDPggPzuioG6n:login.google.example",
  "represented_org": "did:webvh:z3HmjyqtBNmTZXtJQsQQqpBnX:google.example",
  "presentation_digest": "sha256:...",
  "proof_profile": "vc_di_bbs_2023",
  "transport": "tsp",
  "tsp_relationship_id": "tsp:rel:...",
  "disclosed_fields": [
    "credentialSubject.org",
    "credentialSubject.member"
  ],
  "withheld_fields": [
    "credentialSubject.handle",
    "other_handles"
  ],
  "created_at": "2026-04-26T00:00:00Z"
}
```

Receipt 是 holder 私域 audit record。Receipt MUST NOT 包含未披露字段的具体值。

### 16.3 组织和 Verifier 确认

Wallet MUST NOT 只凭域名、邮箱后缀、TLS 证书或 UI 文案确定组织。

Verifier MUST 通过以下任一方式证明其代表权限：

- 由 represented organization DID 直接对 presentation request 签名。
- 由 represented organization 为 verifier DID 签发 service authorization claim。
- 由 trust registry / governance registry 将 verifier VID 映射到 represented organization。
- 目标 Realm policy 将 verifier DID 列为对应 purpose 的可信 issuer / verifier。

Service authorization claim 示例：

```json
{
  "issuer": "did:webvh:z3HmjyqtBNmTZXtJQsQQqpBnX:google.example",
  "subject": "did:webvh:zGZ728E4hbEuyDPggPzuioG6n:login.google.example",
  "claim_kind": "org_service_authorization",
  "service": "arkret_verifier",
  "expires_at": "2026-07-26T00:00:00Z"
}
```

### 16.4 Proof Profile 选择

Wallet SHOULD 根据隐私需求选择 proof profile：

| 需求 | 推荐 profile |
| --- | --- |
| 广泛 verifier 互操作 | `sd_jwt_vc` |
| Claim 级选择性披露 | `sd_jwt_vc` 或 `vc_di_bbs_2023` |
| 不可链接的 derived proof | `vc_di_bbs_2023` 或其他可证明 unlinkability 的 proof suite |
| 简单服务断言 | 在不要求 unlinkability 时使用 detached JWS claim |

实现 MUST NOT 在所选 proof suite 实际不提供零知识 / 不可链接性、或 presentation 仍包含稳定关联标识符时，声称具备 zero-knowledge 或 unlinkability。

### 16.5 存储模型

| 数据 | 位置 | 加密 |
| --- | --- | --- |
| 原始 credential / base proof | wallet 本地加密存储或 holder private account data | 设备密钥 / 恢复密钥 |
| pairwise DID 私钥 | 设备安全存储 | 优先使用硬件支持的 keystore |
| disclosure policy | holder private account data | 向 holder 设备 E2EE |
| presentation request | 临时 inbox 或加密的 private account data | verifier 与 holder 间的传输层加密 |
| presentation response | 仅发送给 verifier；本地副本可选并加密 | TSP / JWE / DIDComm-like / MLS DM |
| disclosure receipt | holder private account data | 向 holder 设备 E2EE |
| status / 撤销缓存 | wallet 缓存或 holder private account data | 向 holder 设备 E2EE |

Sync Service 与服务运营方 MUST NOT 获得原始 credential 内容、base proof、完整 disclosure policy 或未披露 handle。

### 16.6 传输方式选择

传输方式的优先级：

1. 双方都支持且 policy 要求元数据隐私时使用 `tsp`。
2. 使用 verifier DID / 服务密钥的 `http_jwe`。
3. 双方都支持时使用 `didcomm_like` envelope。
4. verifier 是已知 Arkret 设备 / 服务端点时使用 `to_device`。
5. holder 与 verifier 共享加密 DM Realm 时使用 `mls_dm`。

若 policy 要求嵌套 / 路由级元数据隐私，而 verifier 不支持 TSP 或等价能力，wallet MUST 拒绝或请求用户显式覆盖。

### 16.7 端到端流程

1. Verifier 发送已签名的 `ak.identity.presentation_request`。
2. Wallet 验证 verifier DID / VID 与 represented organization 的授权关系。
3. Wallet 根据 disclosure policy 校验该请求。
4. 当 `user_consent_required=true` 或请求超出既有 policy 范围时，Wallet 向 holder 提示确认。
5. Wallet 选择匹配的 pairwise DID 与 credential。
6. Wallet 使用 privacy-preserving status material 检查 credential 状态。
7. Wallet 按所选 proof profile 派生 proof。
8. Wallet 通过所选 transport 发送响应。
9. Verifier 验证 proof、issuer、status、challenge、domain、audience 与新鲜度。
10. Wallet 把 disclosure receipt 写入 holder private account data。

### 16.8 失败码

| code | 含义 |
| --- | --- |
| `verifier_not_authorized` | Verifier 无法证明其代表 represented organization 的权限。 |
| `policy_denied` | Holder disclosure policy 拒绝该请求。 |
| `consent_required` | 披露前需要用户显式同意。 |
| `unsupported_proof_profile` | 双方无可接受的 proof profile。 |
| `transport_privacy_required` | Policy 要求 TSP / 嵌套 / 路由或等价隐私传输，但当前不可用。 |
| `credential_not_found` | Holder 没有匹配的 credential。 |
| `credential_expired` | 匹配的 credential 已过期。 |
| `status_unavailable` | 撤销 / 状态材料不可用。 |
| `overbroad_request` | 请求要求无关 handle、credential id 或全局标识符。 |

### 16.9 安全要求

Wallet MUST：

- 默认采用最小披露。
- 拒绝"所有 handle / 所有 alias"的请求。
- 拒绝与当前关系无关的组织 handle。
- 把 proof 绑定到 verifier 的 challenge、domain 与 audience。
- 避免向中心化服务上报 holder 身份的在线 status check。
- 在 receipt 中不保存未披露字段的具体值。
- 在不同组织间隔离 pairwise DID 密钥与服务端点。

Verifier MUST：

- 只请求必要 claim。
- 除非 policy 明确允许且 holder 同意，否则不要求全局 subject identifier。
- 在要求 unlinkability 时不索取 credential id。
- 把不同 pairwise DID 的 presentation 视为独立 subject，除非 holder 提供 linking proof。

## 17. v1 互操作要求

- Handle canonical wire form 是 `<localpart>:<domain>`。`<localpart>` MUST 是 [`encoding.md` §2.1](../conformance/encoding.md) `arkret_human_identifier` 的 RFC 8265 `UsernameCaseMapped` enforcement 结果：width mapping、Unicode lowercase 与 NFC 后，排除至少 `: @ / # ? \\`、空白、控制字符、noncharacter 与其它 PRECIS disallowed code point；结果 1..128 Unicode code points 且不超过 512 UTF-8 octets。`.`、`_`、`+`、`~`、`-` 保持可用。canonical equality 是 prepared localpart code point sequence + lowercase A-label domain 的精确相等，MUST NOT 使用 confusable skeleton 定义相等。
- `<domain>` MUST 使用 [`encoding.md` §2.2.1](../conformance/encoding.md) 的 UTS #46 Nontransitional profile；canonical wire 只接受 lowercase A-label。`domain.中国` 是合法 input / display domain，对应 canonical `domain.xn--fiqs8s`；因此 `@小明:domain.中国` 可准备为 `小明:domain.xn--fiqs8s`。canonical receiver 必须拒绝原始 U-label domain、uppercase A-label、trailing dot、无效 `xn--`、超 DNS 长度或 round-trip 失败。
- 对应 conformance vectors 为 `ak.vector.identity.internationalized_identifier_profiles.v1` 与 `ak.vector.identity.authority_local_skeleton_collision.v1`；前者验证 preparation / canonical receiver 分层，后者验证 skeleton 只属于 authority-local、namespace-local 派生索引。
- registrar MAY 在同一 issuing authority 的 handle namespace 内要求 UTS #39 `Highly Restrictive` 并建立 `(authority, skeleton)` collision index。skeleton 只用于注册冲突 / 风险提示：碰撞可返回 `failed_precondition` `reason="handle_homograph_forbidden"`，但不得写入 wire、proof 或 equality。不同 authority 的相同 skeleton 不冲突。Unicode / PRECIS / UTS #39 数据版本与升级规则由 [`string-profile-registry.json`](../../artifacts/registry/string-profile-registry.json) 钉定。
- `acct:<percent-encoded-localpart>@<A-label-domain>` 是 `handle_aliases[]` 中的 RFC 7565 alias，不含 port；它不是 canonical handle，也不参与 Arkret 内部唯一性比较。
- **Handle 字符串的 wire-level 作用域**（normative）：handle 字符串作为 wire-level **权威字段**（actor reference、authorization subject、audit attribution、解析输入）MUST 只在以下三类位置出现：
  1. **Handle claim lifecycle 对象与 issuer / Auth Server 本地管理请求**：`ak.schema.handle_claim.v1`、issuer / Auth Server 定义的申请、审批、重签、撤销、Directory withdraw、handle reassignment 等显式管理 handle 生命周期的请求、响应、签名 claim 与 audit receipt。这些管理 API 不属于 Arkret v1 core，但一旦在 Arkret wire 上作为 claim evidence 被消费，必须产出可验证的 `ak.schema.handle_claim.v1` 或明确的 revocation / audit evidence。
  2. **Discovery / Directory query 请求与响应**：`/.well-known/arkret/handle?localpart=...`、`POST /_arkret/find/directory/resolve-handle`、`POST /_arkret/find/directory/list-handles-for-subject` 等解析路径的输入与输出。
  3. **客户端入口解析瞬间**：用户键入 handle 字符串到客户端 → 客户端解析为 `subject_id` 的临时过程；解析完成后 handle 字符串 MUST NOT 作为权威字段写入持久化事件、Realm history、grant 记录、ACL 表或缓存键以外的存储。

  以下位置是**允许的派生投影 / audit 例外**，handle 字符串在其中不构成权威源：

  - **Roster 内联 handle claim evidence**：`/_arkret/self/account/subscribe` 的 `members[].handle_claims[]` MAY 携带完整签名 `ak.schema.handle_claim.v1`，用于 roster / member picker / mention autocomplete 的本地 claim cache。这里的 handle 字符串属于 claim 本身，不是 roster 自造字段；issuer 重新签发或撤销后，roster digest / claim set 必须随之变化。该 evidence 只能在同一 roster entry 已披露 `subject_id` 时返回；未披露 `subject_id` 时，`handle_claims[]`、`handle_claim_digests[]` 与 `handle_claims_limited` 都必须省略。
  - **Mention reference 的 audit metadata**：§3.8.1 定义的 `handle_at_time`、`display_name_at_time`、`controller_subject_id`、`controller_handle_at_time`、`agent_slug_at_time`、`mention_text_original` MAY 出现在 mention / profile reference 等位置，但仅作为 audit / search / fallback 元数据，不参与权威决策（见 §3.8.3）。

  `@<controller-handle>/<agent_slug>` 是客户端入口解析瞬间允许的 native personal agent 输入别名；它不是 canonical handle、公开 Directory 搜索 / 列表索引键或 handle claim 形态。客户端 MUST 用 controller handle claim 加 `ak.schema.agent_selector_claim.v1` 把它解析为 agent `subject_id`，未能唯一解析时 fail closed。Agent selector claim 复用 handle 层的 issuer proof、visibility、audience、expiry 与 revocation 姿态，但不改变 canonical handle ABNF，也不得把 `agent_slug` 拼进 `ak.schema.handle_claim.v1.handle`。

  `ak.member.identity.update` / `MemberIdentity` v1 payload MUST NOT 携带 `primary_handle`、`handles[]` 或其它 handle 字符串字段。其它任何 wire 位置——reply / quote 的 actor 引用、`ak.member.state{join}.payload` 的 actor 字段、grant subject、audit log entry 的 actor 字段、reaction target、federation peer 事件——MUST 持有 `subject_id` 而不是 handle 字符串。verifier / renderer / policy engine MUST NOT 把 mention metadata 当成当前权威 handle、agent slug 或归因依据使用：信任决策永远从 `subject_id` 出发，handle 字符串与 agent slug 只是显示 / 搜索 / audit 辅助。

  违反该作用域规则的事件 schema 在 conformance 测试中 MUST 失败：把 handle 字符串当作**权威 actor 引用字段**（而非显式声明的派生投影或 audit metadata）的 schema 视为 v1 不合规。
- DNS TXT record 格式 MUST 绑定 `handle`、`subject`、issuer、`service_id`、`created_at`、`expires_at` 和 signature / hash commitment；过期或不匹配时不得显示 verified。
- Well-known / Directory response schema MUST 返回 `subject` DID、canonical `handle`、issuer、proof、validity、optional `member_delivery_binding` 和 optional challenge；公开 handle 客户端必须做 DID `alsoKnownAs` 双向验证，受限 handle 必须做 issuer claim / audience / policy 验证。匿名或未授权调用方查询受限 handle、revoked handle 或不存在 handle 时，response MUST 不可区分。
- Credential schema、presentation request、disclosure policy 和 disclosure receipt 必须绑定 holder DID、verifier DID、audience、challenge、domain、disclosed fields、withheld fields 和 proof profile。
- Status list profile MUST 支持凭证撤销和暂停。授权依赖的 credential 无法确认状态时 MUST fail closed。
- BBS / SD-JWT VC conformance vectors MUST 覆盖选择性披露、challenge/domain 绑定、错误 issuer、过期凭证、撤销凭证和 pairwise DID unlinkability。
