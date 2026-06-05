---
title: Handle 与 Claim 证明
status: candidate
normative: true
stability: v1
updated: 2026-05-28
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Handle 是人类可读入口，不是权限主键。
Cokret 使用 DID 作为稳定主体，用可验证 claim / attestation 表达 handle、组织成员、邮箱控制权和其他动态属性。

本文定义：

- handle 格式
- handle 到 DID 的解析
- 双向绑定验证
- 多 handle 场景的 primary handle 选择规则（§3.2.1）
- 事件内 mention reference 与 profile snapshot 的 DID-anchored 形态（§3.8）
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
| Administrative Identifier | 组织本地；不出协议线 | 组织 governance / 内部 Directory | 否 |
| Display Name | UI 展示 | 无 | 否 |
| Principal DID | 公开或 pairwise；按 disclosure policy 控制 | DID resolver + 签名 | 是 |

示例字符串与可能扮演的角色：

- `alice@example.com`、`+86 138...`、通讯录用户名、外部账号 ID → Connection Identifier；若 holder 主动公布可升格为 Handle。
- `@alice:acme.example`、`alice@acme.example`、`alice@alice.dev` → Handle（统一形态，详见 §3）。
- 组织账号、计费账号、客服账号、受管员工编号 → Administrative Identifier。
- `Alice Zhang`、昵称 → Display Name。
- `did:webvh:...`、`did:web:...`、`did:key:...` → Principal DID。

规则：

- Connection Identifier 只用于发现、consent、邀请或一次性绑定证明。它不得自动写入 DID Document、Realm history、membership event、grant subject 或 MLS credential。
- Provider、Directory 或 Auth Server 证明某个 connection identifier 可达时，输出仍 MUST 归约为 DID 或 pending invite proof，并带有 purpose、audience、expiry 和 issuer proof。
- 同一 principal 可以为不同 provider、组织或 Realm 使用不同 connection identifier 和 pairwise DID。实现不得要求全局唯一 connection identifier。
- Connection identifier 与 DID 的绑定默认是关系私有状态。除非 holder 明确发布为 handle 或 VC claim，其他 Realm 成员和 federation peer 不得获得该映射。
- 同一字符串从 Connection Identifier 升格为 Handle MUST 经过 holder 显式 disclosure（写入 `alsoKnownAs`、签发 VC claim、或发布到 Directory）；实现不得在用户未授权时自动升格，也不得仅凭 provider 可达性证明把 connection identifier 公开为 handle。
- Handle 只提供寻址和可选默认投递上下文；它不得作为 `actor_id`、grant subject、membership key 或 audit attribution。解析结果必须先归约为 DID 与可验证 claim，加入 Realm 时再物化为 `ck.member.state{join}.delivery_binding`。
- Administrative Identifier 是组织本地概念。协议层只规定它不得作为协议主体、不得作为 grant subject、不得作为 Event actor、不得在跨组织 federation 输出中泄露；其内部分配、回收和绑定规则由组织 governance 决定，超出本规范范围。
- Display name 是可变 metadata，不得被用于 ACL、grant、audit attribution 或 sender verification。

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
| `acct:<localpart>@<domain>(:<port>)?` | 互通别名（RFC 7565） | 跨 Fediverse / WebFinger 边界对接；只能出现在 `handle_aliases[]`，不作为本协议内部 canonical 比对 |

每个 handle 都有唯一的 `user:domain` 形态。`acct:` MAY 在 claim 的 `handle_aliases[]` 中作为附加字段出现，但 **alsoKnownAs 比对、Directory 缓存键、Realm `delivery_binding` 物化** 一律 MUST 使用 `user:domain` 形态。verifier 收到只含 `acct:` 而无对应 `user:domain` 的 claim 时，MUST 把它视为外部互通别名，不得用它作 Cokret 内部权威 binding。

`handle` 的 wire 形态由 [`artifacts/schemas/handle-claim.schema.json`](../../artifacts/schemas/handle-claim.schema.json) 强制：必须匹配 `<localpart>:<domain>`，且 `<localpart>` 已 canonicalize 为小写。`@<localpart>:<domain>`、`<localpart>@<domain>`、`acct:`、裸 host 等其它形态在 `handle` 中被 schema 拒绝；客户端 MAY 接受这种字符串作为输入捷径，但 normalize 前 MUST 不出现在签名 transcript、`alsoKnownAs`、缓存键或 Directory query 中。`acct:` 互通别名只能进入 `handle_aliases[]`。

### 3.2 解析结果必含字段

Handle 解析结果（无论来自 Directory、Principal Server、Organization claim 还是 holder 自托管 well-known）MUST 至少包含 `handle`、`subject`、`issuer`、`proofs`、`created_at` 与 `expires_at`；`handle_aliases[]` 为 **可选**（optional，与 §3.2.1 表及 §3.7.1 的 MAY 一致），不是必含字段：

- `handle`：canonical `user:domain` handle（主形态）。
- `handle_aliases[]`（可选 / optional）：互通别名，例如 `acct:`；不得参与 Cokret 内部权威比对。缺省时整字段 MAY 省略。
- `subject`：被寻址 handle holder 的 principal DID。
- `issuer`：签发 handle claim 的 DID。详见 §3.4。
- `proofs`：至少一条可验证签名，绑定 `handle`、`subject`、`issuer`、`created_at`。
- `created_at` / `expires_at`：claim 时间边界；`expires_at` 缺失等价于 `binding_state=unverified`。

`subject` 使用 claim / credential 领域的命名，但在 v1 user handle 语义中它是**持有该 handle 的 holder / principal DID**，不是 Realm `actor_id`、Principal Server 内部 `account_id`、组织人事系统 identifier、service DID 或通用资源 id。Cokret v1 core 不把本节的 `handle` 泛化为任意资源 handle；如果后续要定义 organization / service / repository / room 等非用户 handle，必须使用独立 schema 或显式 `resource_kind` profile，不能复用 `ck.schema.handle_claim.v1` 的 `subject` 字段来隐式扩展语义。

本节故意不使用 `actor_id` 作为 handle claim 绑定对象：`actor_id` 是 Realm 内 membership / Event actor 标识，在高隐私 Realm 中 MAY 是 Realm-scoped pairwise DID；同一 holder / principal 可以在不同 Realm 使用不同 `actor_id`，也可以在加入任何 Realm 前先获得 handle claim。handle claim 因此绑定到 holder / principal DID，并在 Realm 内通过当前 effective MemberIdentity 或授权 roster disclosure 建立 `actor_id -> subject_id` 的显示投影。

Handle claim 用于 Realm membership（`intent ∈ {invite, member_add}`）时，**额外** MUST 包含：

- `member_delivery_binding`：该 handle 在投递层提供给 membership builder 的完整投递绑定；其中 `member_delivery_binding.recipient_service_did` 是 Principal Server service DID 的唯一来源。
- `audience`：claim 绑定的目标 Realm ID 或邀请方 service DID；verifier MUST 校验 audience 与当前 invocation 上下文一致。
- `issuer_service_did`（条件必填）：claim 由 Organization 或 Directory 签发时给出实际签名的服务 DID。

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

`metadata.primary_handle` 是 holder 偏好指针，不是 handle 声明通道。Verifier MUST 先从 signed `ck.schema.handle_claim.v1` 构造 `claim_set_snapshot`；若 DID Document 中的 `metadata.primary_handle` 不在该 snapshot 的 verified candidates 中，MUST 忽略该值。该字段不得创建新 claim、绕过 issuer / audience / trust 过滤，也不得覆盖 §3.2.2 对 profile / identity event 的 handle 声明禁令。

**审计材料**（informative）：实现 SHOULD 在选择结果旁附带 `did_document_snapshot_digest = "sha256:" || hex(sha256(JCS(DID Document at as_of)))` 与 `resolution_as_of`，供下游复算时验证 `holder_primary_handle_at_as_of` 来自正确的 DID Document version。该 digest 是审计校验材料，不是算法输入。

**实现 MAY 进一步内联**：把 `holder_primary_handle_at_as_of` 在 `claim_set_snapshot` 构造阶段就物化为每个 claim 上的派生 `holder_flagged: boolean`(`c.holder_flagged := (c.handle == holder_primary_handle_at_as_of)`)；之后算法只读 `c.holder_flagged`，不再需要单独的 `holder_primary_handle_at_as_of` 输入。这种实现 MUST 保证物化产生的 boolean 在同 as_of 同 DID Document version 下是确定的(即等价 transform)。

注意：同一 `(subject_id, context, claim_set_snapshot, policy_snapshot, holder_primary_handle_at_as_of)` 在**不同** `resolution_as_of` 下可能得出不同结果(claim 生效 / 过期跨越边界、policy 时间限制窗口等)，这是预期行为；该规则只保证整个六元组等同时输出等同。

**`claim_set_snapshot` 的 as-of 语义**（normative）：

`claim_set_snapshot` MUST 是 subject 在 `resolution_as_of` 时刻**当时可见**的 handle_claim 集合，**每个 claim 携带它在该时刻的 `binding_state` 与字段值**——不是查询执行时的"现在"集合。具体语义随用法分两支：

- **实时渲染**（real-time render，例如客户端展示当前 mention）：
  `resolution_as_of` ≈ now，`claim_set_snapshot` 即客户端当前可见的 claim 集合及其当前 binding_state。这是默认情形。
- **历史 replay / audit**（例如重建 "该消息发布时 mention 显示什么"）：
  `resolution_as_of` 是过去某时刻；实现 MUST 构造 as-of snapshot，使 snapshot 中每个 claim 的 `binding_state` 反映 **`resolution_as_of` 时的状态**，**不**用当前的 binding_state。例如:
  - 在 `resolution_as_of` 时是 `verified`、之后被 revoke 的 claim 在 snapshot 中 binding_state 仍是 `verified`（曾在 candidate 集合内）;
  - 在 `resolution_as_of` 之后才签发的 claim **不**进 snapshot（Step 0 `created_at <= resolution_as_of` 已经独立把它过滤掉，as-of snapshot 是更强的双保险——connaissance 一致性 + 时间过滤）;
  - 在 `resolution_as_of` 时是 `pending`、之后转为 `verified` 的 claim 在 snapshot 中 binding_state 是 `pending`(于是 Step 0 排除)。

实现 SHOULD 通过保留 handle_claim event 的历史链（issuer / Directory 把每次 claim 状态变化作为 append-only event 持久化）支撑 as-of snapshot 重建；缺少历史的实现 MUST NOT 用"当前 snapshot + historical as_of"组合复算历史显示，那等价于把当前撤销状态错误回投到历史，违反 §6.1.3 历史归因要求。无法构造 as-of snapshot 时,replay MUST fail closed，不得静默退化为"当前 snapshot"。

**`policy_snapshot` 的 as-of 语义**（normative）：

`policy_snapshot` MUST 同样是 **`resolution_as_of` 时刻 Realm policy 的状态**，**不**是查询执行时的当前 policy。具体语义随用法分两支：

- **实时渲染**：`as_of ≈ now`，`policy_snapshot` 即客户端当前可见的 Realm policy 状态(`accepted_issuers` 顺序与 trust 级别)。
- **历史 replay / audit**：取 `resolution_as_of` 时刻 Realm policy event 链所定义的 `accepted_issuers` 顺序与 trust 级别。如果 Realm 后来调整 policy（重排 `accepted_issuers`、变更 trust 级别、加 / 删 issuer），replay MUST 使用**当时**的 policy 而不是现在的，否则同一历史显示在不同时刻复算会得到不同 primary handle，违反"as-of 复算可重复"原则。

实现 SHOULD 通过 Realm policy event 的 append-only 链支撑 as-of policy 重建；缺少历史的实现 MUST NOT 用"当前 policy + 历史 as_of"组合复算，与 `claim_set_snapshot` 同款约束。无法构造 as-of policy snapshot 时,replay MUST fail closed。

主动 replay 调用方 MAY 显式传入目标 policy version（例如 `policy_version_ref: "ck:event:..."`）覆盖默认行为，前提是该 version 在 as_of 时刻确实是当时 effective 的 policy；实现 MUST 验证传入 version 与 as_of 一致，不一致 MUST 拒绝。

**Step 0 — 候选集预过滤**（normative）：

候选集 = `{ c | c ∈ claim_set_snapshot 且 c.binding_state == "verified" 且 c.created_at <= resolution_as_of 且 c.expires_at > resolution_as_of }`（`binding_state` 取 snapshot 中的 as-of 值），再施加：

- **生效时间下界**：`c.created_at <= resolution_as_of` MUST 成立——即在求值时刻该 claim 已被签发；这保证 audit / replay 用历史 `as_of` 时未来才签发的 claim 不会回到候选集，也不会通过 most-recent 抢占展示。`created_at` 是 handle_claim 的签发时刻（见 §5 example），不使用 forbidden 同义别名 `valid_from` / `issued_at`（handle claim 自身命名沿用 `created_at`；候选 schema 内的 `issued_at` 是另一对象，不在此层）。
- **失效时间上界**：`c.expires_at > resolution_as_of` MUST 成立——过期 claim 不参与展示选择。
- **issuer trust filter**：丢弃 `c.issuer` ∉ 当前 Realm / 调用上下文 policy `accepted_issuers` 的 claim。该步是**强制前置**——任何后续优先级匹配都只在受信 issuer 候选集合内进行，避免未受信 issuer 的 audience-matched claim 抢占展示。
- **audience scope filter**：丢弃 `c.audience` 存在且与当前 context 互斥（例如 audience 限定为另一 Realm 或另一 service DID）的 claim。`c.audience` 缺失视为"无 audience 限制"，保留在候选集。

**Step 1 — 优先级匹配**：在 Step 0 输出的候选集内，按以下优先级取第一个非空层：

1. **audience-matched**：`c.audience` 与当前调用上下文（target Realm ID 或邀请方 service DID）严格匹配。
2. **holder-flagged**：`c.handle == holder_primary_handle_at_as_of`（holder 主权偏好，源自 DID Document `metadata.primary_handle`，已在确定性输入元组中物化为标量；算法不再重新读 DID Document）。`holder_primary_handle_at_as_of == null` 时此层为空集。
3. **most-recent**：按 `c.created_at` 取最新者。

**Step 2 — Tie-breaker**（确定性收敛）：若 Step 1 选定层内仍有多个候选，按以下顺序消歧：

1. `c.issuer` 在 policy `accepted_issuers` 列表中位置更靠前者（policy 决定的 trust 顺序）；
2. `c.created_at` 较晚者；
3. `claim_digest(c)` 字典序较小者（见下方定义）。`claim_digest` 是 claim 自身的 canonical identifier，不依赖 `proofs[]` 数组顺序——避免 issuer 重新打包 proof 时 tie-breaker 抖动；
4. 若 `claim_digest(c)` 仍同（极小概率：两份候选共享同一 canonical claim），取 `min(c.proofs[].payload_digest)` 字典序较小者作为最后保险。

**`claim_digest(c)` 定义**（normative，本节）：

```
claim_digest(c) = "sha256:" || hex( sha256( JCS( semantic_projection(c) ) ) )
```

其中：

- `JCS` 是 [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785) JSON Canonicalization Scheme；
- `semantic_projection(c)` 是从 `ck.schema.handle_claim.v1` 对象 `c` 中**只保留以下规范语义字段**形成的子对象——其它任何字段(包括 `proofs`、`verified_at`、`challenge`、`additionalProperties` 通道引入的 server-attested hint、Directory 缓存元数据、verifier 本地标注等)**MUST 排除**：

  | 字段 | 来源 | 数组规范化 |
  | --- | --- | --- |
  | `schema` | 必填 discriminator | — |
  | `handle` | 必填,canonical `<localpart>:<domain>` | — |
  | `handle_aliases` | 可选,`acct:` 互通别名 | MUST 按数组元素 lexicographic 排序后参与 canonicalization |
  | `subject` | 必填,holder principal DID | — |
  | `issuer` | 必填，签发方 DID | — |
  | `issuer_service_did` | 可选，实际签名 service DID | — |
  | `claim_kind` | 可选 | — |
  | `visibility` | 可选 | — |
  | `audience` | 可选,binding 受众 | — |
  | `claim_scope` | 可选,scope object | — |
  | `member_delivery_binding` | 可选，投递绑定 | `delivery_modes`(若存在) MUST 按 lexicographic 排序；详见下方 §3.2.1.1 |
  | `claims` | 可选,VC inner claims | **顺序是语义的一部分**——issuer 控制，中间方 reorder 会破坏原 proof,因此 digest 直接按 issuer 提供顺序 canonicalize |
  | `created_at` | 必填，签发时刻 | — |
  | `expires_at` | 可选/条件必填 | — |
  | `source_refs` | 可选，上游真相源 event 引用 | MUST 按 event_ref 字符串 lexicographic 排序后参与 canonicalization(UUIDv7 字典序对应签发时序，排序结果对 audit 也友好) |

  其它字段一律 MUST NOT 进入 `semantic_projection(c)`,即使 wire claim 通过 `additionalProperties: true` 通道携带。

  > **与 [`handle-claim.schema.json`](../../artifacts/schemas/handle-claim.schema.json) property 顺序的关系(消歧)**：本表是 `semantic_projection` 的字段**白名单**,刻意**排除** `challenge`、`verified_at`、`proofs` 等非规范身份字段；这些被排除的字段在 schema 的 property 列表中**仍然存在并占位**(例如 schema 中 `challenge` 排在 `audience` 与 `claim_scope` 之间),因此本表相邻的 `audience` → `claim_scope` 在原始 schema 中被 `challenge` 隔开。读者**不应**把本表理解为 schema 字段缺失或排序冲突——这是"规范语义投影"与"完整 wire schema"的预期差异。此外 `JCS` 最终按 key 字典序重排，故 `semantic_projection` 内字段的展示顺序不影响 `claim_digest` 计算。

  **`binding_state` 与 `verified_at` 被显式排除**的原因：`binding_state` 是 `resolution_as_of` snapshot 上的有效状态（pending / verified / revoked / expired），会随验证、撤销、过期和历史 replay 时刻变化；`verified_at` 是 §6.0 允许 Directory / Principal Server / 其它中间方写入的 pre-verification hint。若二者进入 `semantic_projection`，同一 issuer 签发的规范 claim 会因中间方、缓存时间或 as-of 时刻不同得到不同 `claim_digest`，破坏 tie-breaker、roster `handle_claim_digests[]` 比对与缓存键稳定性。`claim_digest` 因此只锚定 issuer claim 的规范语义内容；候选集过滤仍 MUST 使用 snapshot 中的 `binding_state` 与时间边界，撤销 / 过期通过 effective claim set 变化体现，而不是改写该 claim 的 digest。

  **`challenge` 被显式排除**的原因：`challenge` 是 verifier / request 级防重放输入，不是 handle claim 的稳定规范身份。proof transcript MAY 继续绑定 challenge、domain 与 verifier，但把 `challenge` 放进 `semantic_projection` 会让同一 handle claim 因不同解析请求得到不同 `claim_digest`，破坏 roster `handle_claim_digests[]` 比对、cache key 与 §3.2.1 tie-breaker 稳定性。

  其它字段排除的整体动因把 `claim_digest` 锚定在 §3.4 / §5 定义的 handle_claim 规范 shape 上，与具体 Directory / Principal Server / cache 层附加的 hint 解耦。

- 输出形态遵循 [`models/common-fields.md` §2](../models/common-fields.md) 的 `<noun>_digest = <alg>:<hex>` 通用 hash 字段命名规则；
- 与 [`artifacts/schemas/member-delivery-binding-candidate.schema.json`](../../artifacts/schemas/member-delivery-binding-candidate.schema.json) 的 `claim_digest` 字段(`"sha256 digest of the upstream handle claim canonical JSON"`)一致——本节是其 normative 计算定义,candidate schema 是其 wire 表示。

  **wire `claim_digest` 缺失时的退化(normative)**:candidate schema 的 `claim_digest` 字段是 **OPTIONAL**(SHOULD,见 §3.7.1 表)。当 candidate 不携带 wire `claim_digest` 时,Step 2 tie-breaker 与 roster `handle_claim_digests[]` 比对 / 缓存键 **MUST** 改用 verifier 本地按本节公式自算的 `claim_digest(c) = "sha256:" || hex(sha256(JCS(semantic_projection(c))))`——即 tie-breaker 与 audit chain 永不因 wire 字段缺失而出现缺口或非确定收敛(自算值与 issuer 提供值在 candidate 合法时必然相等)。当 wire `claim_digest` **存在**时,verifier SHOULD 校验它等于自算值，不一致 MUST 视为 candidate 不可信并 fail closed(防 issuer 提供与规范语义不符的 digest 污染缓存键 / audit chain)。

**Hint 隔离**(normative): §6.0 server-attested hint、Directory 缓存补字段、verifier 本地标注等任何非规范语义字段 MUST 在 wire claim 上以**顶层附加字段**形式存在(而非污染规范字段),并**MUST NOT** 进入 `semantic_projection(c)`。该约束让同一语义 handle claim 被任意数量的 Directory / Principal Server 加 hint 后,`claim_digest` 始终稳定;tie-breaker、roster `handle_claim_digests[]` 比对、缓存键命中都不会因 hint 抖动。

去除 `proofs` 与 server-attested hint 是为了让 `claim_digest` 只覆盖 claim 的**规范语义内容**而非签名包装与中间传输态，让同一 canonical claim 在任意 issuer 重签 / Directory 转发 / cache 层加注后始终产生相同 digest。

**Forward-compat**: 未来 spec revision 在 handle_claim.v1 中加入新规范字段时，该字段名 MUST 同步加入上表；实现 MUST 拒绝白名单外字段进入 digest 计算，即便它出现在新 schema 里——直到 spec 显式扩表。同时新字段若是数组,MUST 在加入表的同时声明数组规范化策略(sorted / order-is-semantic 二选一);未声明的数组字段 MUST 不进入 digest。这保证不同 spec patch 版本之间 `claim_digest` 不会悄悄漂移。

#### 3.2.1.1 数组规范化规则（normative）

JCS（RFC 8785）按 issuer 提供顺序保留数组元素，不做重排。`semantic_projection(c)` 中任何**无序集合语义**的数组若让 JCS 直接吃，不同 producer / Directory 输出顺序差异会让 `claim_digest` 抖动。因此 §3.2.1 表中显式标 "sorted" 的数组字段 MUST 在送入 JCS 之前按以下规则排序：

| 数组字段 | 排序规则 | 排序粒度 |
| --- | --- | --- |
| `handle_aliases` | 元素字符串 lexicographic ascending（UTF-8 byte order，与 JCS 字符串排序保持一致） | 顶层数组元素 |
| `source_refs` | 元素 event_ref 字符串 lexicographic ascending（UUIDv7 字典序与签发时序对齐） | 顶层数组元素 |
| `member_delivery_binding.delivery_modes` | 元素枚举字符串 lexicographic ascending（例如 `events` < `key_packages` < `push` < `sync` < `to_device`） | 嵌套数组元素 |

**Order-is-semantic 数组**（保留 issuer 给定顺序，不重排）：

| 数组字段 | 理由 |
| --- | --- |
| `claims` | VC inner claims，顺序由 issuer 控制并在 proof transcript 内绑定；中间方 reorder 会破坏原 proof，因此 digest 直接保留原序 |
| `proofs` | 已被整体排除在 `semantic_projection` 外，不参与 digest |

排序仅作用于 `semantic_projection(c)` 的副本构造，**不**改写 wire claim 本身；wire 上 `handle_aliases` / `source_refs` / `delivery_modes` 等仍按 issuer 原始顺序传输，verifier 只在 digest 计算阶段做规范化排序。这保证：

- issuer 不必为 digest 稳定性而强制规范化输出（向后兼容旧实现）；
- 不同 verifier / Directory 计算同一 claim 的 `claim_digest` 始终相同；
- wire 层数组顺序与签发顺序之间的对应关系（例如 `source_refs` 上游签发时序）在传输中不被强行抹除。

Step 2 结束后候选 MUST 唯一；实现 MUST NOT 在仍有 tie 时随意选取。

Step 0 候选集为空时，renderer MUST fallback 到 §3.8.2 定义的"解析失败"路径，**不得**任意取一个 handle 显示，**不得**绕过 issuer trust filter。

primary handle 是显示语义；它**不**影响 actor_id 归因、grant subject 或 audit attribution——这些永远来自 `subject_id` 本身。

### 3.2.2 Handle Claim Lifecycle and Acquisition（normative）

Handle 的权威生命周期属于 issuer，不属于用户 profile 或 Realm MemberIdentity event。`ck.profile.update`、`ck.profile.realm_override`、`ck.member.identity.update` 中不得通过任意字段声明、覆盖、撤销或重分配 handle；这些事件最多影响 display name、avatar、subject disclosure 等 UI projection。验证器遇到这些事件中出现的非标准 handle 字段时 MUST 忽略或 schema-reject，不得把它们提升为 verified handle。

Cokret v1 core **不定义**用户注册、handle 申请、邀请审批、管理员通知、管理员审批队列、重签 / 续期、namespace 保留策略、抢注仲裁、多 handle 策略或组织内部身份治理 API。这些流程属于 issuer / coauth / 部署本地治理面；不同 Principal Server、Organization 或自托管 issuer 可以按自己的合规、人事、IDP、邀请和审计要求实现。

协议层只规定 consumption contract：

1. 任何进入 Cokret roster、mention、directory resolve、delivery binding 或 UI verified display 的 handle MUST 来自可验证的 signed `ck.schema.handle_claim.v1`，或该 claim 的 digest / reference。
2. issuer / coauth / 部署本地 API MAY 让用户选择 handle、提交申请、触发人工审批、由管理员直接分配、续签或撤销；这些 API 的 endpoint、权限模型、通知机制和状态机不属于 v1 core。
3. 这些外部流程一旦要把结果暴露给 Cokret 客户端或其它服务，MUST 输出 `ck.schema.handle_claim.v1`、明确的 revocation evidence、或足以让 Directory / roster 不再返回该 claim 的 issuer-side 状态；不得输出未签名 profile 字段来替代 claim。

已知 `subject` DID 但不知道当前 handle 时，客户端 / renderer MUST 使用 `ck.find.directory.list_handles_for_subject` 或 roster 内联 `handle_claims[]` 构造 `claim_set_snapshot`。已知 handle 字符串时，继续使用 `ck.find.directory.resolve_handle`。这两个方向不可互相替代：`resolve_handle` 是 handle → subject，`list_handles_for_subject` 是 subject/context → current visible claims。

管理员或 issuer 后期修改 handle 的可见效果由 claim set 变化驱动：issuer 签发新 claim、撤销旧 claim、或改变 binding_state / expiry 后，`ck.find.directory.list_handles_for_subject` 和 roster hint MUST 反映新的 effective claim set。客户端 MAY 发布新的 `ck.member.identity.update` 来刷新 display-profile cache，但这不是 handle 变更生效的条件。

### 3.2.3 Registration and Invitation Flows（informative）

常见注册路径都在 Cokret core 之外完成，但进入 Cokret 后遵循同一 claim-led 模型：

- **系统预分配 handle**：用户完成注册 / 首次登录后，coauth / issuer bootstrap MAY 直接把 signed `handle_claims[]` 交给客户端或服务端 roster cache。用户无需发 `set_handle` event。
- **管理员邀请允许选择 handle**：邀请链接、pre-registration proof、审批通知和人工审核队列属于 coauth / issuer 策略。Cokret 只看到最终签发的 `ck.schema.handle_claim.v1`，或看不到任何 claim。
- **管理员后期修改现有用户 handle**：issuer 撤销 / 过期旧 claim 并签发新 claim。Realm history 中既有 messages、mentions 和 `ck.member.identity.update` 不被改写；当前渲染按新的 claim set 展示，历史 replay 按 as-of claim snapshot 展示。

因此，"用户注册后是否必须主动发包含 handle 的 profile"的答案是 **否**。用户 MAY 发 profile / MemberIdentity 来设置 display name、avatar 或 subject disclosure；handle 只来自 issuer-signed claim。

### 3.3 `member_delivery_binding`

解析结果 MAY 携带 `member_delivery_binding`，其中 `recipient_service_did`、`binding_source`、`service_acceptance_ref`、`policy_event_ref` 和 `delivery_modes` 可直接用于构造 `ck.member.state{membership="join"}.delivery_binding`。Handle claim schema 不再允许顶层 `recipient_service_did`、`service_acceptance_ref` 或 `policy_event_ref` 快捷字段；这些 delivery binding 字段必须只从 `member_delivery_binding.*` 读取。

`member_delivery_binding.binding_source` 的合法取值是 `explicit` / `invite` / `join_policy` / `organization_policy` / `realm_policy`。**MUST NOT** 是 `did_document_default`——handle resolution 本身就是 directory-attested 路径，与 DID Document fallback 是两条独立的物化路径，不可在 hint 中混用。

该 hint 是 builder 输入；reducer 仍 MUST 按 [`governance/member-delivery-binding.md`](../governance/member-delivery-binding.md) 独立验证 Realm policy、claim issuer、服务背书和条件必填字段。

### 3.4 Issuer 类型与 holder 控制

Handle 的 issuer 决定它的信任锚点；同一 canonical handle 形态可以由不同类型 issuer 签发，verifier 按 issuer 类型选择验证路径：

| Issuer 类型 | 典型场景 | 验证锚点 |
| --- | --- | --- |
| **Holder DID（self-issued）** | 用户自己控制 `<domain>`，自己运营单用户 Principal Server 或 well-known endpoint。例：`@alice:alice.dev` 由 Alice 的 DID 签发。 | (a) `<domain>` 解析 `https://<domain>/.well-known/cokret/handle?localpart=<localpart>` 或 DNS TXT `_cokret.<domain>` 返回签名 handle claim；(b) holder DID Document `alsoKnownAs` 含对应 `<localpart>:<domain>`；两侧均验签通过。 |
| **Organization DID** | 组织把 handle 签发给员工或受管成员。例：`@alice:acme.example` 由 `did:web:acme.example` 签发给 Alice 个人 DID。 | issuer claim + holder DID Document `alsoKnownAs`（公开 handle）或受限 presentation；audience / scope 限定到目标 Realm / 组织。 |
| **Principal Server service DID** | Principal Server 为它承载的用户签发 handle。例：托管平台 `did:web:principal.acme.example`。 | claim 由 service DID 签发，service DID 由 Organization DID 委派（DID Document service entry 或 governance attestation）；最终归约到 Organization 信任根。 |
| **受信 Directory DID** | 公共 Directory 索引 handle 并发放短期 routable claim。 | Directory claim + 上游 `source_refs`；Directory 是镜像层，不是真相源。 |

**自托管即单用户实例**：用户自己控制域名时，handle 形态仍是 `alice:alice.dev`（或任意 localpart），与组织部署完全一致；只是 issuer 与 holder 是同一个 DID。verifier 解析时按 §5 走 `<domain>` 的 well-known 通道发现 issuer，再走 issuer claim + alsoKnownAs 双向验证——验证路径自然分流，不依赖其它字符串 shape。

### 3.5 公开 vs 受限

Handle 按 holder 披露意图分两类：

- **公开 handle**：holder 主动公开，DID Document MAY 在 `alsoKnownAs` 中列出 canonical `user:domain` handle；issuer 提供的 well-known 或 Directory 响应可对任意 verifier 可见。
- **受限 handle**：例如组织内部账号 `@alice:acme.example` 暗示雇佣关系，默认不进公开 DID Document。它由 issuer 以 `ck.schema.handle_claim.v1` / VC / signed directory response 表达，并按 audience、Realm、organization policy 最小披露。

公开 / 受限之间的差异只在 alsoKnownAs / 公开 directory 的可见性上。两者 wire 形态、双签证据要求、`delivery_binding` 构造规则相同。

### 3.6 与跨上下文 unlinkability 的关系

`member_delivery_binding.recipient_service_did` 必然在解析结果中暴露 handle 与服务的绑定关系；同一 holder 在两个上下文使用同一公开 DID 时，外部观察者通过 `subject` 字段仍能关联到同一人。**Handle 不提供跨上下文 unlinkability**。

需要不可关联的部署 MUST 为每个上下文使用 pairwise / private DID（见 §10、§11、§16），并在每个 pairwise DID 下独立签发 handle claim。pairwise DID 与 handle 是正交机制：handle 解决"易懂寻址 + 可选默认投递"，pairwise DID 解决"跨关系不可关联"。

### 3.7 MemberDeliveryBindingCandidate

`MemberDeliveryBindingCandidate` 是 Handle resolution（`ck.find.directory.resolve_handle(intent="member_add")`）或受信 issuer 直接签发的 **规范级候选对象**：它把 "用 handle 加成员" 这个端到端链路上需要传递的最小字段集合凝固为一个 schema-defined shape，让 Principal Server、SDK builder、Realm reducer、Auth Server 与 directory 之间停止各自拼字符串。Wire schema 见 [`artifacts/schemas/member-delivery-binding-candidate.schema.json`](../../artifacts/schemas/member-delivery-binding-candidate.schema.json)。

该对象既不是 grant，也不是已物化的 `member_delivery_binding`——它只是**通向**后者的 builder 输入。reducer 在落 `ck.member.state{membership="join"}.delivery_binding` 时仍 MUST 按 [`governance/join-policy.md`](../governance/join-policy.md) 独立验证。

### 3.7.1 字段（normative）

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `subject_id` | DID | MUST | 被寻址主体的 principal DID；最终物化为 `payload.actor_id` / cell subject。 |
| `handle` | canonical handle | MUST | `<localpart>:<domain>`，`<localpart>` 已 lowercase。`acct:` / 显示形态 / 裸 host 一律拒绝。 |
| `handle_aliases[]` | `acct:` URI 数组 | MAY | 仅互通别名；不参与权威比对、缓存键或 `delivery_binding` 物化。 |
| `member_delivery_binding` | object | MUST | 与 [`handle-claim.schema.json#/properties/member_delivery_binding`](../../artifacts/schemas/handle-claim.schema.json) 同形，`binding_source` ∈ `explicit` / `invite` / `join_policy` / `organization_policy` / `realm_policy`；MUST NOT 为 `did_document_default`。 |
| `issuer_service_did` | DID | MUST | 实际签发该 candidate 的服务 DID（Directory / Principal Server / Organization service DID）。 |
| `audience` | string | MUST | 目标 Realm ID 或邀请方 service DID；verifier MUST 校验 audience 与当前 invocation 上下文一致。 |
| `issued_at` | timestamp | MUST | RFC 3339 `Z` 形式；issuer 签发该 candidate 的时刻。MUST ≤ `expires_at`；与 `expires_at` 一起界定 candidate 的有效窗口并阻止 MITM 把 `issued_at` 改写以扩大重放窗口。 |
| `expires_at` | timestamp | MUST | RFC 3339 `Z` 形式；过期 candidate MUST 被视为不可用。 |
| `source_refs[]` | event id 数组 | MUST | 至少一条 `ck:event:<uuid7>`，指向 issuer / Directory / Organization 真相源 event；客户端 SHOULD 据此回真相源验签。 |
| `proofs[]` | proof 数组 | MUST | 至少一条 proof，绑定 `handle`、`subject_id`、`member_delivery_binding.recipient_service_did`、`audience`、`issuer_service_did`、`issued_at` 与 `expires_at`。`issued_at` MUST 进入 canonical transcript；缺失即视为重放窗口可篡改并拒绝。 |
| `claim_digest` | `sha256:<hex>` | SHOULD | candidate 上游 handle claim 的 canonical JSON digest，用于缓存键与 audit chain。 |
| `intent` | enum | MUST | `member_add` / `invite`，区分 candidate 的 builder 入口；reducer 不依赖该字段，仅用于审计与遥测。 |

`MemberDeliveryBindingCandidate.subject_id` MUST 等于上游 handle claim 的 `subject`。Raw / generic handle claim 使用 `subject`；进入 membership builder candidate 并作为具体 DID 绑定进 proof transcript 时使用 `subject_id`。

`additionalProperties: false`——unknown 字段 MUST 由 verifier 拒绝，避免静默 widening。

### 3.7.2 来源（normative）

candidate 只能来自以下两类签发路径：

1. **Directory 解析**：`ck.find.directory.resolve_handle(intent="member_add" \| "invite")` 响应 MUST 把 [`discovery-directory.md` §9.0/§9.1](../discovery/discovery-directory.md) 的 handle 解析与通用结果字段重新打包为 candidate；`source_refs` 取 Directory 响应中的 `source_refs`，`issuer_service_did` 取 Directory service DID 或上游 Organization service DID。
2. **受信 issuer 直接签发**：Organization / Principal Server / 受信 service DID 可以离开 Directory 直接对某 `(handle, subject_id, member_delivery_binding.recipient_service_did, audience)` 组合发签名 candidate，例如随 invite token 内嵌、随 organization-issued member roster 下发。

candidate **不得**直接构造自客户端字符串拼接、UI text、未签名 directory 响应或 cache 残留。任何缺少 `proofs[]` 的对象 MUST NOT 被命名为 candidate。

### 3.7.3 物化公式（normative）

`MemberDeliveryBindingCandidate -> ck.member.state.payload.delivery_binding` 的映射必须是确定性的：

```text
payload.actor_id = candidate.subject_id
payload.delivery_binding.recipient_service_did = candidate.member_delivery_binding.recipient_service_did
payload.delivery_binding.resolved_at = candidate.issued_at   // 确定性取值:issuer 签发 candidate 的时刻;当需要以 proof 时刻为准时,取 candidate.proofs[] 中最早的 created_at(min over proofs),二者均为单一确定值,不得是区间或多值
payload.delivery_binding.service_acceptance_ref = candidate.member_delivery_binding.service_acceptance_ref
payload.delivery_binding.policy_event_ref = candidate.member_delivery_binding.policy_event_ref
payload.delivery_binding.delivery_modes = candidate.member_delivery_binding.delivery_modes
payload.delivery_binding.binding_source = join-policy §5.1.2.1 决策树输出
```

`claim_digest`、`source_refs[]` 与 candidate proof digest SHOULD 进入 member Move 的 `refs[]`（`role="attestation"` 或 profile 声明的 role），用于审计和 replay 诊断；它们不得替代 `delivery_binding` 中的规范字段。映射过程中任何缺失字段、过期 candidate、audience 不匹配、issuer 未授权或 Realm `delivery_binding_policy` 不接受该 source，均 MUST fail closed。

### 3.7.4 Validator MUST 规则

verifier 收到 candidate 时 MUST 按下列顺序失败 closed：

1. **schema 合规**：所有 MUST 字段存在；`additionalProperties: false` 不放过未知字段。
2. **`handle` canonical**：必须匹配 `<localpart>:<domain>` 主形态，且 `<localpart>` 已 lowercase。verifier 不得在签名 transcript 中接受任何非 canonical 形态；`acct:` 出现在 `handle` 即拒绝。
3. **audience match**：`audience` MUST 等于当前 invocation 上下文（目标 `target_realm_id` / `realm_id` 绑定的 audience，或邀请方 service DID）；不一致 MUST 返回与 "无可披露 claim" 不可区分的统一拒绝。
4. **expiry**：`expires_at` 严格大于当前时间；过期 candidate MUST NOT 进入 builder。
5. **proof 验证**：`proofs[]` 中至少一条由 `issuer_service_did`（或受 issuer 委派的 verification method）签名，且 binding transcript 覆盖 `handle`、`subject_id`、`member_delivery_binding.recipient_service_did`、`audience`、`issuer_service_did`、`issued_at`、`expires_at` 与 `claim_digest`（如有）。任何 transcript 漏掉 `issued_at` 或 `issued_at > expires_at` MUST fail closed，避免 MITM 通过重写时间窗口实施重放。
6. **subject / handle 关联**：candidate 内 `subject_id` MUST 等于上游 handle claim 中的 subject（不允许 verifier 在 builder 入口 "替换" subject）。
7. **`member_delivery_binding.binding_source` 合法值**：MUST 是 §3.3 列出的五种之一；`did_document_default` 即拒绝。

通过上述检查的 candidate 是 builder 的合法输入；reducer 仍 MUST 按 Join Policy 再验签 / 再过审。

### 3.7.5 与 display resolve / mention resolve 的差异

`ck.find.directory.resolve_handle` 三种 intent 返回的字段不同，candidate 只在 `member_add` / `invite` intent 下产生：

| Intent | 返回字段（必含） | 是否产 candidate | 说明 |
| --- | --- | --- | --- |
| `lookup` / display resolve | `subject`、`handle`、`verified` | 否 | 仅用于显示双向验证状态；不暴露 `audience` 或 `member_delivery_binding`。 |
| `mention` resolve | `subject`、`handle`、`display_name?` | 否 | mention autocomplete 需要的最小字段；MUST NOT 在未授权时披露 `member_delivery_binding`。结果存为 message 内 mention snapshot，不进入 membership builder。 |
| `member_add` / `invite` resolve | §3.7.1 全部 MUST 字段 | 是 | 仅当 caller 已经过授权（共同 Space、Directory policy、organization grant 等）才返回。Directory 拒绝时使用与 "未发现资源" 不可区分的统一拒绝。 |

实现 MUST NOT 跨 intent 复用结果：以 `mention` 解析拿到的 payload 不得提升为 candidate；以 `member_add` 解析拿到的 candidate 不得被广播到 mention autocomplete 缓存。

### 3.8 Mention Reference 与 Display Snapshot（normative）

事件内对某 subject 的引用——@mention、reply target、quoted profile、forwarded message 的原作者引用、reaction 的目标等——**权威引用字段** MUST 使用 DID-anchored 标识符（`subject_id`），不得用 handle 字符串作为 actor 归因、授权判断、解析路径的唯一来源。同一事件 MAY 同时携带 handle / display name 的历史快照作为 audit / search / 兜底展示的 metadata（见 §3.8.1），但这些 metadata 字段不参与协议层信任决策（见 §3.8.3）。

该规则的根本动因：handle 的 `<domain>` 部分是 issuer 的 authority domain（组织 / holder 自己持有的域名），不是 subject 用户控制的标识。如果把 domain 作为**权威**引用字段持久化进每一个引用点，issuer 的 DNS 治理成本（domain 迁移、authority 重命名）就会转嫁给所有历史事件，并被迫做事件改写。DID 才是稳定标识；handle 是该标识的可读 label，由解析层实时计算；事件内的 handle metadata 只是"当时是什么"的 audit 快照，不是"现在是什么"的真相源。

§17 wire-level 作用域规则配套约束了 handle 字符串作为**权威字段**可以出现的位置。MemberIdentity 不再携带 handle 字符串；Realm-scoped roster 若需要加速渲染，只能内联签名 handle claim evidence 或 digest hint（详见 [`sync/client-sync.md` §8.1](../sync/client-sync.md)）。

#### 3.8.1 字段定义

mention reference / profile snapshot 的 normative shape：

| 字段 | 类型 | 必填 | 用途 |
| --- | --- | --- | --- |
| `subject_id` | DID | MUST | 被引用主体；唯一参与 actor 归因、授权判断、解析路径与渲染查找的字段。 |
| `display_name_at_time` | string | MAY | event 时刻 subject 的 display name 快照；持久化、不再更新；renderer MAY 直接显示。 |
| `handle_at_time` | canonical handle string（§3.1 主形态） | MAY | event 时刻 subject 的 handle 快照；**仅** audit / debug / 全文搜索 / 历史回溯用途；**MUST NOT** 作为当前显示标识。 |
| `mention_text_original` | string | MAY | 用户键入的原始输入（例如 `@alice:acme.com` 或 `alice@acme.example`）；audit 与搜索索引用途，不参与渲染逻辑。 |

`display_name_at_time` 是 snapshot 语义——一旦写入事件即固定，防止 subject 后续修改 display name 时回写历史（这条边界对反冒充很重要）。`handle_at_time` 是 audit metadata，不是显示字段。

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

#### 3.8.3 与 actor 归因的关系

`display_name_at_time`、`handle_at_time`、`mention_text_original` 三个字段都是 **UI 元数据**，对协议层信任决策完全透明。verifier / reducer / policy engine MUST 忽略这三个字段，只读 `subject_id` 做以下判断：

- grant subject 校验
- audit attribution
- membership / Realm 决议
- sender verification
- ACL / capability 校验
- federation peer attribution

也就是说：篡改 mention reference 的元数据字段不构成协议层攻击（最多骗 UI 显示），但篡改 `subject_id` 会被 event envelope 签名直接拒绝。

#### 3.8.4 与 Organization Authority Migration 的关系

因 §3.8 规定权威引用字段一律 DID-anchored，组织 authority domain 迁移（`acme.example → acme.com`）在历史事件层不需要 rewrite：

- 旧事件内的 mention / profile reference 权威字段是 `subject_id`，subject 不变；
- 渲染时按 §3.2.1 解析当前 primary handle，得到新 domain 的 handle 字符串；
- 历史事件本身**不需要**rewrite、migration script 或 schema upgrade；
- 唯一需要的 issuer-side 操作是按 §6 批量重发 handle_claim（new domain），随后 Directory withdraw 旧 entry；当前显示投影随 issuer / coauth 刷新路径、`ck.find.directory.list_handles_for_subject` 或 roster claim hints 的下一次刷新自然更新，不要求任何 `ck.member.identity.update`。

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

Pairwise DID、临时 DID、设备 DID、agent 执行 DID 和隐私敏感关系 DID SHOULD NOT 强制绑定公开 handle。受限 handle 只有在 holder 明确选择公开该上下文关联时才 SHOULD 写入 `alsoKnownAs`；否则必须通过受限 claim / presentation 返回。

### 4.1 `alsoKnownAs` 的窄用途

`alsoKnownAs` 在 Cokret v1 协议层**只承担一件事**：为 §3.4 issuer claim 提供 holder 侧的反向背书，使公开 handle 的双向验证（§6）可独立于任何 issuer / Directory 完成。完整链路是：

```text
issuer claim:        handle → subject_id   (issuer 单方面签名声明)
holder DID Document: subject_id → handle   (列入 alsoKnownAs，holder 单方面承认)
```

没有 holder 侧这条边，任何被信任的 issuer 都可以单方面把 handle "塞" 到受害者 DID 上而 holder 无从拒绝。`alsoKnownAs` 把这种 issuer-unilateral 攻击降级为 issuer × holder 双方均需主动表态——`did:webvh` 等带历史 method 还能让 alsoKnownAs 增删进入可回溯链路，使 holder 的撤销动作具备 audit 证据（§6.1.2 第 3 条）。

`alsoKnownAs` **不参与**以下机制；这些机制各自有专用字段或独立机制：

| 机制 | 权威字段 / 路径 |
| --- | --- |
| Realm 内投递路由 | `ck.member.state{join}.delivery_binding.recipient_service_did` |
| Realm 加成员 / Join Policy | `MemberDeliveryBindingCandidate`（§3.7）+ issuer claim + audience |
| Actor / 签名归因、审计 | Event envelope `actor_id` = DID 本身 |
| Principal Server 搬迁、域名变更 | DID Document `service` entry + service delegation |
| 受限 handle（组织内部账号） | issuer claim + audience + scope（§3.5 默认不进公开 DID Document） |
| Pairwise / 设备 / agent / 临时 DID | 显式 SHOULD NOT 写入 `alsoKnownAs`（见上文与 [identity-did.md](./identity-did.md) §6 末段"Pairwise / private DID SHOULD NOT 包含公开 handle"，以及 §9 验证规则第 9 条） |
| 跨上下文 unlinkability | pairwise DID 机制，正交于 handle 层（§3.6） |
| Handle 重分配后的历史归因 | 历史 Event 内固化的 `subject` DID 与 display snapshot（§6.1.3） |

实现 MUST NOT 把 `alsoKnownAs` 用作 mention 索引、Directory 主键、缓存键、投递路径或 actor 归因依据；它的唯一规范用途是"public handle 的 holder-side 反向背书"。

## 5. Handle 解析

Handle 解析分为两个方向：

- **handle → subject**：输入是 canonical `handle = <localpart>:<domain>`（或 normalize 自显示形态），使用 `ck.find.directory.resolve_handle` 或下列 issuer discovery 路径。
- **subject/context → current handles**：输入是 `subject` DID、当前 Realm / audience / requester context，使用 `ck.find.directory.list_handles_for_subject` 或 roster 内联 `handle_claims[]`。该方向用于 member roster、mention renderer 和 issuer 重签 / 撤销 claim 后的显示刷新。

已知 handle 时，客户端 / verifier 按以下顺序尝试 issuer，第一个成功签发可验证 claim 的就是该 handle 的 issuer：

1. **`<domain>` 的 well-known**：`GET https://<domain>/.well-known/cokret/handle?localpart=<localpart>`。响应是 `ck.schema.handle_claim.v1` 形态的签名 claim。
   - 用于 holder 自托管（domain 拥有者 == subject DID）与单实例 Principal Server 部署。
2. **DNS TXT**：`_cokret.<domain>` 或 `_cokret.<localpart>.<domain>`。仅当 DNSSEC validation 成功**且** TXT 内含可验证签名时才能作为 issuer 通道；裸 DNS TXT 只是发现 hint。
3. **Directory / Organization 服务**：`POST /_cokret/find/directory/resolve-handle`（[`discovery/discovery-directory.md` §9.0](../discovery/discovery-directory.md)）或 `POST /_cokret/find/directory/list-handles-for-subject`（已知 subject 时）。response 仍是签名 `ck.schema.handle_claim.v1`。
4. **Bridge / 外部 issuer**：当 handle 来自 bridge 或外部体系（例如组织自有 IDP），claim 由该体系签发并通过 §7 VC presentation 出示。

解析结果 MUST 包含 §3.2 列出的字段；audience / scope / expiry 决定使用范围。multiple issuer 同时签发同一 handle 时，verifier 按本地 trust policy 选最严格者；issuer 之间冲突（不同 `subject`）MUST fail closed 并交人工处理。

账号侧 claim 管理不走 Directory 搜索，但 v1 core 也不定义账号侧管理 API：当前登录 principal 如何在注册、换设备、管理员修改或 claim 续期后拿到自己的 claims，是 issuer / coauth / 部署本地 bootstrap 的职责。Directory 只解析已经签发且对调用方可见的 claims；它不得被当作 handle 申请、审批或管理员治理接口。

Handle 解析示例：

```json
{
  "schema": "ck.schema.handle_claim.v1",
  "handle": "alice:alice.dev",
  "subject": "did:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example",
  "issuer": "did:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example",
  "binding_state": "verified",
  "created_at": "2026-05-19T00:00:00Z",
  "expires_at": "2026-08-19T00:00:00Z",
  "proofs": [{
    "kind": "detached_jws",
    "alg": "EdDSA",
    "verification_method": "did:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example#key-1",
    "payload_digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "created_at": "2026-05-19T00:00:00Z",
    "jws": "aaa.bbb.ccc"
  }]
}
```

这是 self-issued handle（holder 自己控制 `alice.dev` 域名，`issuer == subject`）。组织签发 handle 的示例：

```json
{
  "schema": "ck.schema.handle_claim.v1",
  "handle": "alice:acme.example",
  "handle_aliases": ["acct:alice@acme.example"],
  "subject": "did:webvh:z2dmjA1ice:users.acme.example",
  "issuer": "did:web:acme.example",
  "issuer_service_did": "did:web:principal.acme.example",
  "claim_kind": "organization_handle",
  "visibility": "restricted",
  "binding_state": "verified",
  "audience": "ck:realm:0196419b-0000-7000-8000-000000000000",
  "member_delivery_binding": {
    "recipient_service_did": "did:web:principal.acme.example",
    "recipient_service_type": "principal_server",
    "binding_source": "organization_policy",
    "delivery_modes": ["events", "sync", "to_device", "push", "key_packages"],
    "service_acceptance_ref": "ck:event:0196419b-0000-7000-8000-000000000001",
    "policy_event_ref": "ck:event:0196419b-0000-7000-8000-000000000002"
  },
  "created_at": "2026-05-19T00:00:00Z",
  "expires_at": "2026-08-19T00:00:00Z",
  "proofs": [{
    "kind": "detached_jws",
    "alg": "EdDSA",
    "verification_method": "did:web:principal.acme.example#key-1",
    "payload_digest": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "created_at": "2026-05-19T00:00:00Z",
    "audience": "ck:realm:0196419b-0000-7000-8000-000000000000",
    "jws": "aaa.bbb.ccc"
  }]
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
- claim `audience` 与当前调用上下文一致；
- claim `challenge` 未过期、未重复使用；
- claim `scope`（Realm、organization、purpose）覆盖当前用途；
- claim `status` / `binding_state` 仍为 `verified`；
- holder consent / organization policy 允许向当前 requester 披露。

DID Document 缺失 `alsoKnownAs` 单独**不**构成"受限 handle 无效"的判定；判定来自 issuer claim 验签链 + audience / scope 校验。

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
- verifier MUST 能用自己的 DID resolver 独立 re-verify（按 §6 顶层取得 `subject` DID Document 当前内容并复算 `alsoKnownAs` 包含校验），不得仅凭 server-attested `binding_state` 字段做信任决策。Server-attested hint 携带的附加字段（例如 DID Document digest 副本、`alsoKnownAs` proof 副本）是实现可选优化，v1 不为此层定义规范 wire schema；不同实现的 hint 字段差异不影响互操作，因为 verifier 始终保留独立 re-verify 路径；
- 上述展示类动作 SHOULD 优先 first-party 验证；MAY 接受 server-attested `binding_state=verified` 命中，并把 UI 状态展示为 verified（cache hit 与 first-party verified 之间不做用户可见区分），前提是 hint 仍在 verifier 本地 trust policy 允许的 TTL 上限内、未触发 §6.1.2 失效信号；
- **verified 徽章 vs 纯 autocomplete 区分（normative）**：联系人卡片 / 个人资料页面上的 **verified 徽章** 是用户信任决策的关键视觉信号，其防伪强度 SHOULD 高于纯 mention autocomplete 排序提示。客户端 **SHOULD** 在展示 verified 徽章前执行一次 first-party re-verify（§6 顶层独立 re-verify 路径）；当徽章仅由 hint-only 命中(未经本次 first-party 验证)驱动时，客户端 SHOULD 对该徽章施加弱化视觉（例如"服务器声明，未本地核验"的次级标识）而非与 first-party verified 徽章不可区分地呈现，以避免下一条所述"被攻陷 Directory + 受信 issuer 串通"直接驱动一个用户无法分辨真伪的强信任徽章。纯 mention autocomplete 排序 MAY 继续仅依赖 hint，无需为排序结果执行 first-party re-verify；
- 命中超期、§6.1.2 任一失效信号触发、或 verifier 本地 trust policy 拒绝该 hint 来源时，UI MUST 降级为 `unverified` 或等价的视觉降级状态，**不得**继续展示 verified 徽章；
- 一个被攻陷的 Directory 与一个被信任的 issuer 串通可以伪造 server-attested verified 状态——这是把展示动作放在 SHOULD/MAY 而非 MUST 层的根本风险；Authority 层动作不允许承担此风险。

Principal Server 在自己的职责范围内（事件接收 / 路由 / 投递 / Realm reducer 决策）**不读** `alsoKnownAs`——这些决策的权威字段是 `delivery_binding.recipient_service_did`、`MemberDeliveryBindingCandidate` 与 issuer claim（见 §4.1 与 §3.7）。Principal Server 出现在本节 cache 层的角色是"为它服务的客户端预解析公开 handle 并维护缓存"，与它作为 Realm 投递与 reducer 节点的角色互不替代。

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
- handle cache 若含 `member_delivery_binding`，还 MUST 绑定 `member_delivery_binding.recipient_service_did`、claim digest、audience / scope、`service_acceptance_ref` / `policy_event_ref`（如有）；缓存结果不得跨 Realm 或跨组织上下文复用，除非 claim 明确授权。
- DNS / HTTPS 解析结果的 TTL MUST 不超过底层 DNS TTL、HTTPS response cache headers、签名绑定 `expires_at`、DID Document cache TTL 和本地 resolver policy 上限中的最小值。未提供 TTL 时，verified cache SHOULD 不超过 24 小时；高风险授权或组织背书 SHOULD 使用更短 TTL 或实时 status check。
- 当 DID Document 移除对应 `alsoKnownAs`、issuer claim 被 revoke / expired、well-known 绑定变更、DNSSEC validation 失败、handle 被解析到不同 DID、或 resolver policy 更新时，缓存 MUST 失效或降级为 unverified。

#### 6.1.2 撤销与失效信号

v1 不引入专门的 handle 撤销 event。撤销通过下列三条独立路径完成，客户端 / Directory / Principal Server 任一通道发现失效即 MUST 同步本地缓存：

1. **TTL 自然过期**：缓存到达 `expires_at` 后 MUST 重新拉取；不得在 TTL 之外使用。
2. **Directory withdrawal**：handle issuer 通过 [`ck.find.directory.withdraw`](../discovery/discovery-directory.md) 撤回该 handle 的 directory entry；订阅该 handle 的客户端在下一次 directory refresh 或 withdraw notification 收到后 MUST 立即失效缓存。
3. **DID Document 变化**：holder 移除 `alsoKnownAs` 中的 canonical handle，或 issuer claim 被 revoke / `binding_state=revoked`、`binding_state=expired`；下一次 verify pass 失败时 MUST 失效。

handle issuer SHOULD 把 cache 失效信号与 TTL 一起使用：发布短 TTL（≤1h）的高变更 handle、配合 Directory withdraw 主动通知。**v1 不要求**服务端推送 handle 失效事件；客户端 MUST 按 TTL + 上述三路径处理失效，**不得**依赖未注册的 `ck.handle.*` wire kind。

#### 6.1.3 Handle 重分配与历史归因

handle 字符串可以在 issuer 治理下被重分配到不同 DID（典型场景：员工离职后 localpart 被分配给新员工）。重分配 normative 规则：

- **DID 与签名责任不可改写**：Handle 转让或重分配 MUST NOT 改变历史 Event 的 actor DID、签名责任或 audit attribution。授权、grant subject、membership、MLS credential 与 audit attribution MUST 使用 DID / verified claim，而不是缓存中的 handle 字符串。
- **历史 mention 显示**：mention 与 profile reference 在事件中的**权威引用字段**只持有 `subject_id`（详见 §3.8）；handle 字符串只能作为 §3.8.1 定义的 audit / search metadata（`handle_at_time` / `mention_text_original`）出现。渲染历史 mention / message text 时，UI MUST 按 §3.8.2 实时解析 primary handle 显示，**不得**用事件内 `handle_at_time`（若存在）作为当前显示值。handle reassignment 的语义自然结果是：旧消息里 `@alice:acme.example` 这条 mention 解析到的 `subject_id` 仍是原 Alice，渲染时显示她**当前的** primary handle；新拿到 `alice` localpart 的人是一个不同的 `subject_id`，不会被回填进历史 mention。若 renderer 检测到事件内 `handle_at_time` 与当前 primary handle 不一致，MAY 加 "handle changed since" 提示（显示层增强，非 normative）。
- **新分配生效**：新持有者拿到 handle 后 MUST 通过 issuer 重新发布 handle claim（新 `subject`、新 `created_at`、独立的 `service_acceptance_ref`）；旧 claim 的所有缓存按 §6.1.2 失效。
- **跨投递的 cascade**：handle 重分配不自动迁移既有 Realm `delivery_binding`——旧 binding 仍按 `ck.member.state{join}` 内固化的 `subject` DID 投递。新持有者要加入同一 Realm 需要走完整 join 流程并签发新的 `delivery_binding`。

## 7. Verified Claim

Handle、组织成员、邮箱控制权和角色 SHOULD 通过 credential / attestation 表达。

授权判断 MUST 检查：

- issuer 是否被目标 Realm / Policy 信任
- subject DID 是否匹配当前 actor
- claim 是否在有效期内
- claim 是否未撤销
- claim 内容是否满足 grant constraint
- presentation 是否绑定当前 verifier challenge / domain
- 若 claim 携带 `member_delivery_binding`，其 `recipient_service_did` 是否被 issuer 授权、被 Realm policy 接受，并能作为 `delivery_binding.recipient_service_did` 通过 Join Policy 校验。

## 8. 隐私保护型 Handle 证明

DID Document MUST NOT 被用作跨组织身份画像。公开或半公开 DID Document MUST NOT 直接列出以下信息，除非主体明确希望这些信息被关联：

- `alice@google.com`
- `alice@facebook.com`
- 第三方 profile URL
- 跨组织账号名
- 受限 handle 到 `member_delivery_binding.recipient_service_did` 的映射
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
4. Google 或受信 issuer 给 `did:key:z6Mkgpairwise...` 签发 `CokretOrgMembershipCredential`
5. Facebook 或受信 issuer 给 `did:key:z6Mkfpairwise...` 签发独立 credential
6. 面向 Google verifier 时，wallet 只生成 Google 相关 presentation
7. Google verifier MUST NOT 要求披露 Facebook credential、Facebook DID 或跨域 subject identifier

## 11. Credential 示例

如果 verifier 只需要知道“该主体拥有 Google 组织内有效账号”，presentation SHOULD 披露抽象 claim：

```json
{
  "type": ["verifiable_credential", "cokret_org_membership_credential"],
  "issuer": "did:web:google.example",
  "credentialSubject": {
    "id": "did:key:z6Mkgpairwise...",
    "org": "did:web:google.example",
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
  "type": "cokret_presentation_request",
  "audience": "did:web:google.example",
  "domain": "google.example",
  "challenge": "cx_chal_01J...",
  "accepted_issuers": [
    "did:web:google.example",
    "did:web:trusted-hr.example"
  ],
  "required_claims": [
    {
      "type": "cokret_org_membership_credential",
      "constraints": {
        "org": "did:web:google.example",
        "member": true
      },
      "disclosure": "abstract"
    }
  ],
  "forbidden_claims": [
    "other_handles",
    "external_accounts",
    "global_flow_identifier"
  ]
}
```

Wallet MUST 展示将要披露的 claim。
Wallet SHOULD 拒绝或警告请求无关 handle、global subject identifier、credential id 或不必要人口属性的 presentation request。

## 13. Proof Profile

Cokret SHOULD 支持：

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
condition = has valid cokret_org_membership_credential where org = did:web:google.example
```

错误：

```text
grant subject = alice@google.com
```

如果 holder 后续为另一个组织出示不同 pairwise DID，除非 holder 显式提供 linking proof，否则 verifier MUST 将其视为独立隐私上下文。

## 16. Progressive Disclosure（渐进披露）

本节定义 Cokret 隐私信息渐进披露的端到端实现方案。渐进披露用于让 holder 只向特定 verifier / organization 披露完成某项验证所需的最小身份信息，例如：

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
  "kind": "ck.identity.presentation_request",
  "request_id": "ck:request:d8764019-0000-7000-8000-000000000000",
  "verifier_did": "did:web:login.google.example",
  "represented_org": "did:web:google.example",
  "domain": "google.example",
  "challenge": "cx_chal_01J...",
  "purpose": "space_join",
  "accepted_issuers": ["did:web:google.example"],
  "required_claims": [
    {
      "claim_type": "cokret_org_membership_credential",
      "constraints": {
        "org": "did:web:google.example",
        "member": true
      },
      "disclosure": "abstract"
    }
  ],
  "optional_claims": [
    {
      "claim_type": "verified_handle",
      "fields": ["handle"],
      "disclosure": "explicit"
    }
  ],
  "forbidden_claims": [
    "other_handles",
    "external_accounts",
    "global_flow_identifier",
    "credential_id"
  ],
  "transport_hints": ["tsp", "http_jwe", "didcomm_like"],
  "expires_at": "2026-04-26T00:05:00Z"
}
```

Verifier MUST 对该请求签名，或通过已认证的关系通道发送。Wallet MUST 把响应中的 proof 绑定到 `challenge`、`domain`、`verifier_did` 和 `represented_org`。

#### 16.2.2 Disclosure Policy

```json
{
  "kind": "ck.identity.disclosure_policy",
  "policy_id": "ck:policy:a1cb0019-0000-7000-8000-000000000000",
  "holder_did": "did:web:holder.example.com",
  "audience": {
    "org_did": "did:web:google.example",
    "verifier_dids": ["did:web:login.google.example"],
    "tsp_vids": ["did:webs:google.example:verifier"]
  },
  "allowed_claims": [
    {
      "claim_type": "verified_handle",
      "issuer": "did:web:google.example",
      "subject_id": "did:key:z6Mkgpairwise...",
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
    "global_flow_identifier",
    "credential_id"
  ],
  "requires_user_consent": true,
  "expires_at": "2026-07-26T00:00:00Z"
}
```

Disclosure policy 是 holder-private state，默认 MUST NOT 写入公共 Realm。

#### 16.2.3 Presentation Response

```json
{
  "kind": "ck.identity.presentation_response",
  "request_id": "ck:request:d8764019-0000-7000-8000-000000000000",
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

#### 16.2.4 Disclosure Receipt

```json
{
  "kind": "ck.identity.disclosure_receipt",
  "receipt_id": "ck:receipt:a1cb0019-0000-7000-8000-000000000000",
  "request_id": "ck:request:d8764019-0000-7000-8000-000000000000",
  "holder_did": "did:key:z6Mkgpairwise...",
  "verifier_did": "did:web:login.google.example",
  "represented_org": "did:web:google.example",
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
  "issuer": "did:web:google.example",
  "subject": "did:web:login.google.example",
  "claim_type": "org_service_authorization",
  "service": "cokret_verifier",
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
4. verifier 是已知 Cokret 设备 / 服务端点时使用 `to_device`。
5. holder 与 verifier 共享加密 DM Realm 时使用 `mls_dm`。

若 policy 要求嵌套 / 路由级元数据隐私，而 verifier 不支持 TSP 或等价能力，wallet MUST 拒绝或请求用户显式覆盖。

### 16.7 端到端流程

1. Verifier 发送已签名的 `ck.identity.presentation_request`。
2. Wallet 验证 verifier DID / VID 与 represented organization 的授权关系。
3. Wallet 根据 disclosure policy 校验该请求。
4. 当 `requires_user_consent=true` 或请求超出既有 policy 范围时，Wallet 向 holder 提示确认。
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

- Handle 的 canonical wire form 是 `<localpart>:<domain>`，其中 `<localpart>` 在 wire 上必须是 lowercase canonical form；`acct:<localpart>@<domain>(:<port>)?` 为 `handle_aliases[]` 中的互通别名。handle ABNF 必须限制为可规范化、大小写明确、禁止控制字符和混淆分隔符的字符串；`<domain>` 使用 IDNA 处理后再验证。**Wire-level canonical 比较(normative)**：issuer / registry / resolver 在做 handle 注册、claim 校验、§13 跨 issuer 冲突检测时，MUST 先对 `<localpart>` 与 `<domain>` 应用 Unicode NFC normalization，再应用 [UTS#39](https://www.unicode.org/reports/tr39/) confusable skeleton 折叠；比较与冲突判定 MUST 在折叠后的形态上执行。issuer / registry MUST 拒绝 *script-mixed* handle（同一 label 内同时含 Latin 与 Cyrillic / Greek / Armenian 等不同 script 字符，例如 `аcme.example` U+0430 + Latin 混排），以及 `hyphen-disallowed-position` 形态；违反者注册请求 `failed_precondition` `reason="handle_homograph_forbidden"`。显示层防混淆仍 MUST 实现，但不能替代 wire-level 检测。

  **NFC / UTS#39 检测的作用层与 schema ASCII pattern 的关系(normative,消歧)**：上述 NFC normalization 与 UTS#39 confusable / script-mixing 检测 MUST 作用于 IDNA 转换**之前**的 **U-label**(用户可见的 Unicode 形态，可能含非 ASCII 字符)——这是 homograph 攻击的实际载体。检测通过后,`<domain>` MUST 经 IDNA2008(ToASCII)转为 **A-label**(punycode,`xn--` 前缀的纯 ASCII),`<localpart>` 经本节 lowercase canonical 规则归一为受限 ASCII;只有该 ASCII canonical 形态才是进入 `ck.schema.handle_claim.v1` 等 wire claim `handle` 字段、并由 [`handle-claim.schema.json`](../../artifacts/schemas/handle-claim.schema.json) ASCII-only pattern 校验的值。因此 schema pattern 是 ASCII-only **不是**与 §17 检测矛盾，而是有意分层:UTS#39 confusable 折叠在 U-label 上做(schema 校验不到、也不应在 wire canonical handle 上重复执行),schema pattern 只兜底"进入 wire 的 handle 已是受限 ASCII canonical 形态"。实现 MUST NOT 把含非 ASCII 字符的 U-label 直接作为 wire `handle` 提交(会被 schema 拒绝),亦 MUST NOT 因 schema 通过就跳过 U-label 阶段的 NFC / UTS#39 检测。
- **Handle 字符串的 wire-level 作用域**（normative）：handle 字符串作为 wire-level **权威字段**（actor reference、authorization subject、audit attribution、解析输入）MUST 只在以下三类位置出现：
  1. **Handle claim lifecycle 对象与 issuer / coauth 本地管理请求**：`ck.schema.handle_claim.v1`、issuer / coauth 定义的申请、审批、重签、撤销、Directory withdraw、handle reassignment 等显式管理 handle 生命周期的请求、响应、签名 claim 与 audit receipt。这些管理 API 不属于 Cokret v1 core，但一旦在 Cokret wire 上作为 claim evidence 被消费，必须产出可验证的 `ck.schema.handle_claim.v1` 或明确的 revocation / audit evidence。
  2. **Discovery / Directory query 请求与响应**：`/.well-known/cokret/handle?localpart=...`、`POST /_cokret/find/directory/resolve-handle`、`POST /_cokret/find/directory/list-handles-for-subject` 等解析路径的输入与输出。
  3. **客户端入口解析瞬间**：用户键入 handle 字符串到客户端 → 客户端解析为 `subject_id` 的临时过程；解析完成后 handle 字符串 MUST NOT 作为权威字段写入持久化事件、Realm history、grant 记录、ACL 表或缓存键以外的存储。

  以下位置是**允许的派生投影 / audit 例外**，handle 字符串在其中不构成权威源：

  - **Roster 内联 handle claim evidence**：`/_cokret/self/account/subscribe` 的 `members[].handle_claims[]` MAY 携带完整签名 `ck.schema.handle_claim.v1`，用于 roster / member picker / mention autocomplete 的本地 claim cache。这里的 handle 字符串属于 claim 本身，不是 roster 自造字段；issuer 重新签发或撤销后，roster digest / claim set 必须随之变化。该 evidence 只能在同一 roster entry 已披露 `subject_id` 时返回；未披露 `subject_id` 时，`handle_claims[]`、`handle_claim_digests[]` 与 `handle_claims_limited` 都必须省略。
  - **Mention reference 的 audit metadata**：§3.8.1 定义的 `handle_at_time`、`display_name_at_time`、`mention_text_original` MAY 出现在 mention / profile reference 等位置，但仅作为 audit / search / fallback 元数据，不参与权威决策（见 §3.8.3）。

  `ck.member.identity.update` / `MemberIdentity` v1 payload MUST NOT 携带 `primary_handle`、`handles[]` 或其它 handle 字符串字段。其它任何 wire 位置——reply / quote 的 actor 引用、`ck.member.state{join}.payload` 的 actor 字段、grant subject、audit log entry 的 actor 字段、reaction target、federation peer 事件——MUST 持有 `subject_id` 而不是 handle 字符串。verifier / renderer / policy engine MUST NOT 把 mention metadata 当成当前权威 handle 或归因依据使用：信任决策永远从 `subject_id` 出发，handle 字符串只是显示 / 搜索 / audit 辅助。

  违反该作用域规则的事件 schema 在 conformance 测试中 MUST 失败：把 handle 字符串当作**权威 actor 引用字段**（而非显式声明的派生投影或 audit metadata）的 schema 视为 v1 不合规。
- DNS TXT record 格式 MUST 绑定 `handle`、`subject`、issuer、`service_did`、`created_at`、`expires_at` 和 signature / hash commitment；过期或不匹配时不得显示 verified。
- Well-known / Directory response schema MUST 返回 `subject` DID、canonical `handle`、issuer、proof、validity、optional `member_delivery_binding` 和 optional challenge；公开 handle 客户端必须做 DID `alsoKnownAs` 双向验证，受限 handle 必须做 issuer claim / audience / policy 验证。
- Credential schema、presentation request、disclosure policy 和 disclosure receipt 必须绑定 holder DID、verifier DID、audience、challenge、domain、disclosed fields、withheld fields 和 proof profile。
- Status list profile MUST 支持凭证撤销和暂停。授权依赖的 credential 无法确认状态时 MUST fail closed。
- BBS / SD-JWT VC conformance vectors MUST 覆盖选择性披露、challenge/domain 绑定、错误 issuer、过期凭证、撤销凭证和 pairwise DID unlinkability。
