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
- 事件内 mention reference 与 profile snapshot 的 DID-committed 形态（§3.8）
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
| Handle | 公开或受限；用于 @mention / 邀请 / 成员添加 / 跨上下文可读寻址 | Directory / Station / Organization authority 签发的 handle claim（canonical `user:domain` + `acct:` alias），按披露策略解析为 exact `subject_account_id`；proof 的 DID URL 独立承载签名 key | 否 |
| Agent selector label | 默认受限；仅用于已知完整 Agent AccountId 的授权 picker 展示与校验 | 当前 `ak.schema.agent_selector_claim.v1` 绑定的 `subject_account_id` 必须与已知目标完整相等 | 否 |
| Administrative Identifier | 组织本地；不出协议线 | 组织 governance / 内部 Directory | 否 |
| Display Name | UI 展示 | 无 | 否 |
| Principal DID | 公开或 pairwise；按 disclosure policy 控制 | DID resolver + 签名 | 是 |

示例字符串与可能扮演的角色：

- `alice@example.com`、`+86 138...`、通讯录用户名、外部账号 ID → Connection Identifier；若 holder 主动公布可升格为 Handle。
- `@alice:acme.example`、`alice@acme.example`、`alice@alice.dev` → Handle（统一形态，详见 §3）。
- `@alice:acme.example/summary` → v1 不支持的旧组合输入；它不是 handle，也不得自动归约为 Agent mention。
- 组织账号、计费账号、客服账号、受管员工编号 → Administrative Identifier。
- `Alice Zhang`、昵称 → Display Name。
- `did:webvh:...`、`did:webvh:z8kSru9qAfd1G7AvcVjggdEKy:...`、`did:key:...` → Principal DID。

规则：

- Connection Identifier 只用于发现、consent、邀请或一次性绑定证明。它不得自动写入 DID Document、Realm history、membership event、grant subject 或 MLS credential。
- Provider、Directory 或 Auth Server 证明某个 connection identifier 可达时，输出仍 MUST 归约为 DID 或 pending invite proof，并带有 purpose、audience、expiry 和 issuer proof。
- 同一 principal 可以为不同 provider、组织或 Realm 使用不同 connection identifier 和 pairwise DID。实现不得要求全局唯一 connection identifier。
- Connection identifier 与 DID 的绑定默认是关系私有状态。除非 holder 明确发布为 handle 或 VC claim，其他 Realm 成员和 federation peer 不得获得该映射。
- 同一字符串从 Connection Identifier 升格为 Handle MUST 经过 holder 显式 disclosure（写入 `alsoKnownAs`、签发 VC claim、或发布到 Directory）；实现不得在用户未授权时自动升格，也不得仅凭 provider 可达性证明把 connection identifier 公开为 handle。
- Handle 只提供寻址；它不得作为 `actor_id`、grant subject、membership key 或 audit attribution。账号解析结果必须是可验证 claim 中的 exact `subject_account_id`；加入 Realm 仍需目标账号 acceptance。
- Holder MAY 在 subject-private receive policy 中允许 verified handle claim 作为 first-contact / invite 的 `handle_claim` introduction evidence。该选择只表示"我愿意让别人通过这个 handle 找到并请求联系我"，不等于 consent grant、accepted contact、Realm membership 或 invite authorization；接收方仍 MUST 按 [`../sync/invite-addressing.md`](../sync/invite-addressing.md) §5 的 subject policy 与 Station `receive_policy_constraints` 求交集后决定 drop / quarantine / notify。
- Agent selector claim 只为已经通过授权 roster/picker 获得完整 `subject_account_id` 的 Agent 提供 controller-scoped label 与绑定校验；`visibility` / `audience` 继续限制 label 披露。它不得作为自由文本寻址、`actor_id`、grant subject、membership key、delivery key、公开 Directory 搜索 / 列表索引键或 audit attribution。v1 没有跨 Station 完整候选集与 absence proof，客户端 MUST NOT 从 controller handle 加 slug 推断唯一 Agent AccountId。
- Administrative Identifier 是组织本地概念。协议层只规定它不得作为协议主体、不得作为 grant subject、不得作为 Event actor、不得在跨组织 federation 输出中泄露；其内部分配、回收和绑定规则由组织 governance 决定，超出本规范范围。
- Display name 是可变 metadata，不得被用于 ACL、grant、audit attribution 或 sender verification。
- OIDC `name` 是部署本地 Display Name 兼容属性，不是 Administrative Identifier，也不是 PCR `actor_profile.display_name` 的协议真相源。Auth / Station MUST NOT 把它无 holder 签名地投影进 profile，也不得用它创建或更新 Contact `petname` / `confirmed_display_name`。注册引导 MAY 把它作为客户端首次 author `ak.profile.create` 的输入建议，但最终 Event 必须由 holder-authorized signer 签名并通过普通 PCR admission。

## 3. Handle 格式

Handle 是面向用户的人类可读地址，让客户端用一个易懂字符串完成 @mention、联系人搜索或邀请，同时保持协议账号身份是 exact `AccountId`，投递 endpoint 由账号所属 Station 的 service resolution 独立取得。

Handle 是统一概念：协议层只有一种 canonical handle 形态、一套解析与验证规则。所谓"自有域名个人 handle"与"组织内部账号地址"在结构上是同一类——区别只在**谁是 issuer**（domain 拥有者自己 vs 组织 / Station），不在字符串形态。

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

每个 handle 都有唯一的 `user:domain` 形态。`acct:` MAY 在 claim 的 `handle_aliases[]` 中作为附加字段出现，但 alsoKnownAs 比对与 Directory 缓存键一律 MUST 使用 `user:domain` 形态。verifier 收到只含 `acct:` 而无对应 `user:domain` 的 claim 时，MUST 把它视为外部互通别名，不得用它作 Arkret 内部权威 binding。

`handle` 的 wire 形态由 [`string-profiles.schema.json`](../../artifacts/schemas/string-profiles.schema.json) 与 [`handle-claim.schema.json`](../../artifacts/schemas/handle-claim.schema.json) 共同约束：必须是 `<prepared-localpart>:<lowercase-A-label-domain>`。localpart 是 `arkret_human_identifier` 的 Unicode canonical value，不是 IDNA label；domain 才执行 UTS #46。`@<localpart>:<domain>`、`<localpart>@<domain>`、`acct:`、裸 host、U-label domain 与任何可转换但尚未 canonical 的字符串在 `handle` wire 字段中都 MUST 被拒绝。客户端 MAY 在 input preparation API 接受这些输入并向用户回显转换结果，但 canonical receiver / verifier MUST 只验证，不能先改写再验签。

`acct:` alias 按 RFC 7565 构造：prepared localpart 以 UTF-8 编码，对 URI 中非直接允许的 octet 做大写十六进制 percent-encoding；host 使用 canonical A-label；不得携带 port。比较遵循 RFC 3986 的 scheme / host case 与 percent-encoding normalization，不参与 Arkret canonical handle equality。

**与 realm alias 的关系（normative）**：handle 的 `@` sigil 与 realm alias 的 `#` sigil（见 [`discovery/object-addressing.md` §3.3](../discovery/object-addressing.md)）构成同一套人类短地址体系：两者 canonical 形态同为 `<localpart>:<domain>`（不含 sigil），但占据**不相交命名空间**——handle 经 `resolve_handle` 解析为 holder / principal DID，realm alias 经 `resolve_realm` 解析为 `ak:realm:<44-char-token>`。同一 `<localpart>:<domain>` MAY 同时是一个 handle 与一个 realm alias；协议**不要求**二者全局唯一，sigil 在显示 / 输入期区分类型，线上字段凭其类型上下文消歧。`@` 与 `#` 均为展示 + 输入路由 affordance，strip 后才进 wire。

### 3.2 解析结果必含字段

Handle 解析结果（无论来自 Directory、Station、Organization authority 还是 holder 自托管 well-known）MUST 是 closed `HandleClaimStatusView`：

```text
HandleClaimStatusView {
  schema: "ak.schema.handle_claim.v1",
  claim: HandleClaimCore,
  status: pending | verified | revoked,
  as_of,
  verifier_id,
  verified_at: timestamp | null,
  revocation: HandleClaimRevocation | null,
  fresh_until,
  status_proof
}

HandleClaimCore {
  schema: "ak.schema.handle_claim_core.v1",
  handle, handle_aliases[], subject_account_id, issuer_id,
  claim: {kind:"handle_binding"} |
         {kind:"organization_handle", organization_id},
  visibility, audience: string | null,
  issued_at, expires_at: timestamp | null, source_refs[],
  proofs: [issuer_attestation, holder_acceptance]
}
```

`HandleClaimCore` 是 immutable issuer/holder 共同签名对象；数组字段始终出现并按 UTF-8 bytewise 升序，nullable 字段始终出现，禁止 null/absent 双编码。`visibility=public` 时 `audience=null`；`restricted|private` 时 audience 为非空 exact invocation context。`claim.kind=organization_handle` 时 `organization_id` 必填；其它 claim/scope 扩展均 forbidden。`challenge` 属 request/presentation transcript，不进入 core；`vouching_id`、开放 `claim_scope`、`claims[]`、`binding_state` 与 core 内 `verified_at` 均 forbidden。

core digest 固定为 `sha256(utf8("ak.handle_claim_proof.v1\n") || JCS(core_without_proofs))`，其中字段集合与 schema `handle_claim_core` property 集合逐字相同，仅移除 `proofs`；不得使用裸 JCS hash、数据库行或本地 DTO。`proofs[0]` 固定 `proof_purpose=issuer_attestation`，其 DID URL 在 `issued_at` 有效且 adapter projection 等于 `issuer_id`；`proofs[1]` 固定 `holder_acceptance`，其方法在 `issued_at` 属于 `subject_account_id.station_id` 的 accepted account-service authority。两条 proof 均令 `domain=ak.handle_claim_proof.v1`、`payload_digest=claim_digest`，并覆盖完整 AccountId；同 core 异 Station 不得复用 holder proof。

status transcript 就是去掉 `status_proof` 后的 canonical status view，字段集合与 schema `handle_claim_status_view` property 集合逐字相同，nullable 编码固定：

```text
status_preimage = {
  schema,
  claim,              // 完整 HandleClaimCore，含两条 core proof
  status,
  as_of,
  verifier_id,
  verified_at,        // timestamp | null，字段不得省略
  revocation,         // HandleClaimRevocation | null，字段不得省略
  fresh_until
}
status_digest = sha256(utf8("ak.handle_claim_status.v1\n") || JCS(status_preimage))
```

status view 不携 `claim_digest` 与 `revocation_digest`：两者只是 verifier 从同载体 `claim` / `revocation` 重算的派生值（公式见本节与 §3.2.1），不得作为 wire 字段出现，也不得在 status transcript 中补回。`status_proof` 必须令 `domain=ak.handle_claim_status.v1`、`proof_purpose=status_attestation`、`payload_digest=status_digest`；其 verification method 必须在 `as_of` 为 `verifier_id` 的 evidence-time accepted service authority。调用者、本地缓存或未签名 Directory row 不得自报 `verified`。verifier 只有在 core 两张 proof、exact AccountId、issuer/domain authority、audience 与当前 revocation floor 全部通过后才能签 `verified`。`verified_at` 对 verified 必须非 null 且 `claim.issued_at <= verified_at <= as_of`；pending 必须 null。`status=revoked` 必须携完整 `revocation`，verifier 从该 carrier 按下述公式重算 `revocation_digest` 并与其 `proof.payload_digest` 逐字比较；其它 status 的 `revocation` 必须为 null。`expired` 不是 status 值：求值时只要 `claim.expires_at != null && claim.expires_at <= evaluation_time` 就 fail closed 为 expired，禁止重写 core/status。

freshness 固定为 `as_of < fresh_until <= as_of + 300 seconds`，并且 core 有 expiry 时 `fresh_until <= claim.expires_at`。admission time 超过 `fresh_until` 必须在线取得新 status；不得以本地 TTL、HTTP cache age 或旧 status 回退延长。status 更新、issuer/holder key revocation、Directory trust/policy revision变化均使缓存立即失效。historical replay 只能使用 exact historical status carrier，不能把 current status 与 historical `as_of` 拼接。

revocation carrier 与 transcript 固定为：

```text
HandleClaimRevocation {
  schema: "ak.schema.handle_claim_revocation.v1",
  claim_digest,
  revoked_at,
  revoker: {role:"issuer", issuer_id} |
           {role:"holder", subject_account_id},
  proof
}
revocation_preimage = {schema, claim_digest, revoked_at, revoker}
revocation_digest = sha256(utf8("ak.handle_claim_revocation.v1\n") || JCS(revocation_preimage))
```

`proof` 必须令 `domain=ak.handle_claim_revocation.v1`、`proof_purpose=revocation_authorization`、`payload_digest=revocation_digest`。issuer 分支的 `issuer_id` 必须逐字等于 core issuer，且方法投影等于该 issuer；holder 分支 AccountId 必须逐字等于 core subject，且方法属于该 exact account 在 `revoked_at` 的 accepted authority。revoked status verifier 必须独立验证 carrier，不得仅因 issuer/holder HTTP 返回字符串 `revoked` 就生成状态。未知 revocation floor、digest 不等、未来 `revoked_at`、角色/id 错配或签名方法已在证据时点撤销均 fail closed。

三类 detached JWS 共用唯一签名字节：`JCS({kind,verification_method,payload_digest,created_at,domain,audience,proof_purpose})`，字段集合固定且不含 `jws`。因此 proof role、domain、audience 与 payload digest 均受签名保护；实现不得只签 payload bytes 后让中间方替换 proof purpose。

`subject_account_id` 使用 claim / credential 领域的角色名，但其类型是 canonical `AccountId`，不是裸 DID、Realm `ActorId`、Station 内部账号行号、组织人事 identifier、service DID 或资源 ID。非账号 handle 必须使用独立 schema，不得隐式扩展本字段。

本节不使用通用 `ActorId` 绑定账号 handle：ActorId 可表达账号或 service 等参与者；账号也可以在加入任何 Realm 前获得 handle claim。claim 绑定 exact AccountId，Realm 内由当前 effective MemberIdentity 或授权 roster disclosure 建立 `ActorId -> AccountId` 的显示投影，不能只比较 principal core。

Handle claim 用于 Realm 邀请（`intent ∈ {invite, member_add}`）时，`claim.audience` MUST 绑定目标 Realm ID 或邀请方 service DID。Organization authority 的身份由 `claim.claim.organization_id` 与 issuer proof 唯一表达，不另加 vouching sidecar。它仍只产生 pending invite，不直接产生 membership。

### 3.2.1 Primary Handle Selection（normative）

同一 `subject_account_id: AccountId` MAY 同时持有多个 active 的 handle claim（不同 issuer、不同 audience、个人 vs 组织、self-issued vs organization-issued 等）。当 renderer / verifier 需要"该 subject 在当前上下文的 primary handle"时，MUST 按下列步骤产生确定性结果。

**确定性输入元组**（normative）：

每次选择 MUST 显式接受一个 `resolution_as_of`（RFC 3339 `Z` 形式时间戳）作为求值时刻。算法是**对下列六元组的纯函数**：

```
(
  subject_account_id,
  context,                          // 当前 Realm ID / 邀请方 service DID / 解析 invocation
  claim_set_snapshot,               // subject 在 as_of 的 signed status-view 集合
                                    // 详见下文"claim_set_snapshot 的 as-of 语义"
  policy_snapshot,                  // Realm policy 在 as_of 时刻的 handle_issuer_policy 顺序与 trust 级别
                                    // 详见下文"policy_snapshot 的 as-of 语义"
  holder_primary_handle_at_as_of,   // 从 subject DID Document(as_of version)
                                    // 提取的 metadata.primary_handle 字段值，字符串或 null
  resolution_as_of                  // RFC 3339 Z 求值时刻
)
```

同一六元组输入在不同 verifier、不同时刻 MUST 得到相同结果。

**`holder_primary_handle_at_as_of` 的求值规则**（normative）：取 `subject_account_id.principal_id` 对应的已验证 DID 在 `resolution_as_of` 时刻通过 DID resolver 解析得到的 DID Document(含 historical version 解析能力的 DID method，例如 `did:webvh`，MUST 取 as_of 对应的历史 version；不带 history 的 method，verifier MUST 把当前 resolver 返回的 version 作为 snapshot)；从该 Document 提取 `metadata.primary_handle` 字段的字符串值。缺失或字段类型不是字符串时，取 `null`。算法在 §3.2.1 Step 1 "holder-flagged" 层只检查每个候选 `c.handle == holder_primary_handle_at_as_of`，**不**重新读 DID Document——这使 holder flag 成为算法的纯函数输入而不是副作用读取。

`metadata.primary_handle` 是 holder 偏好指针，不是 handle 声明通道。Verifier MUST 先从 signed `ak.schema.handle_claim.v1` 构造 `claim_set_snapshot`；若 DID Document 中的 `metadata.primary_handle` 不在该 snapshot 的 verified candidates 中，MUST 忽略该值。该字段不得创建新 claim、绕过 issuer / audience / trust 过滤，也不得覆盖 §3.2.2 对 profile / identity event 的 handle 声明禁令。

**审计材料**（informative）：实现 SHOULD 在选择结果旁附带 §5.1 唯一算法所得的 `document_digest`
与 `resolution_as_of`，供下游复算时验证 `holder_primary_handle_at_as_of` 来自正确的 normalized DID
Document historical version。该 digest 是审计校验材料，不是算法输入；不得另造第三个
DID-document digest 字段。

**实现 MAY 进一步内联**：把 `holder_primary_handle_at_as_of` 在 `claim_set_snapshot` 构造阶段就物化为每个 claim 上的派生 `holder_flagged: boolean`(`c.holder_flagged := (c.handle == holder_primary_handle_at_as_of)`)；之后算法只读 `c.holder_flagged`，不再需要单独的 `holder_primary_handle_at_as_of` 输入。这种实现 MUST 保证物化产生的 boolean 在同 as_of 同 DID Document version 下是确定的(即等价 transform)。

注意：同一 `(subject_account_id, context, claim_set_snapshot, policy_snapshot, holder_primary_handle_at_as_of)` 在**不同** `resolution_as_of` 下可能得出不同结果(claim 生效 / 过期跨越边界、policy 时间限制窗口等)，这是预期行为；该规则只保证整个六元组等同时输出等同。

**`claim_set_snapshot` 的 as-of 语义**（normative）：

`claim_set_snapshot` MUST 是 subject 在 `resolution_as_of` 时刻**当时可见**的 `HandleClaimStatusView` 集合，每个 view 的 signed `as_of/status/fresh_until` 必须覆盖该求值时点，而不是查询执行时的“现在”集合。具体语义随用法分两支：

- **实时渲染**（real-time render，例如客户端展示当前 mention）：
  `resolution_as_of` ≈ now，`claim_set_snapshot` 即客户端当前可见且 freshness 有效的 status-view 集合。这是默认情形。
- **历史 replay / audit**（例如重建 "该消息发布时 mention 显示什么"）：
  `resolution_as_of` 是过去某时刻；实现 MUST 取覆盖该时点的 historical signed status view，禁止把 current status 改写 `as_of`。例如：该时点 verified、之后 revoked 的 core 使用历史 verified view；该时点之后才 `issued_at` 的 core 不进 snapshot；该时点 pending、之后 verified 的 core 使用历史 pending view。

实现 SHOULD 通过保留 handle_claim event 的历史链（issuer / Directory 把每次 claim 状态变化作为 append-only event 持久化）支撑 as-of snapshot 重建；缺少历史的实现 MUST NOT 用"当前 snapshot + historical as_of"组合复算历史显示，那等价于把当前撤销状态错误回投到历史，违反 §6.1.3 历史归因要求。无法构造 as-of snapshot 时，replay MUST fail closed，不得静默退化为"当前 snapshot"。

**`policy_snapshot` 的 as-of 语义**（normative）：

`policy_snapshot` MUST 同样是 **`resolution_as_of` 时刻 Realm policy 的状态**，**不**是查询执行时的当前 policy。具体语义随用法分两支：

- **实时渲染**：`as_of ≈ now`，`policy_snapshot` 即客户端当前可见的 `ak.realm.policy_bundle.handle_issuer_policy` 状态（issuer 顺序、域作用域与 authority class）。
- **历史 replay / audit**：取 `resolution_as_of` 时刻 Realm policy bundle event 链所定义的 `handle_issuer_policy`。如果 Realm 后来调整 policy（重排 entry、变更 trust 级别、加 / 删 issuer），replay MUST 使用**当时**的 policy 而不是现在的，否则同一历史显示在不同时刻复算会得到不同 primary handle，违反"as-of 复算可重复"原则。

实现 SHOULD 通过 Realm policy event 的 append-only 链支撑 as-of policy 重建；缺少历史的实现 MUST NOT 用"当前 policy + 历史 as_of"组合复算，与 `claim_set_snapshot` 同款约束。无法构造 as-of policy snapshot 时，replay MUST fail closed。

主动 replay 调用方 MAY 显式传入目标 policy version（例如 `policy_version_ref: "ak:event:..."`）覆盖默认行为，前提是该 version 在 as_of 时刻确实是当时 effective 的 policy；实现 MUST 验证传入 version 与 as_of 一致，不一致 MUST 拒绝。

**Step 0 — 候选集预过滤**（normative）：

候选集 = `{ c | c ∈ claim_set_snapshot 且 c.claim.subject_account_id == subject_account_id 且 c.status == "verified" 且 c.claim.issued_at <= resolution_as_of 且 (c.claim.expires_at == null || c.claim.expires_at > resolution_as_of) 且 c.as_of <= resolution_as_of < c.fresh_until }`。每个候选还必须通过 core issuer+holder 两张 proof、status evidence 与当前 revocation floor；DID Document `alsoKnownAs` 只能加强 public discovery，不能替代 required holder proof。

- **生效时间下界**：`c.claim.issued_at <= resolution_as_of` MUST 成立；未来才签发的 core 不得回投历史。
- **失效时间上界**：`c.claim.expires_at == null || c.claim.expires_at > resolution_as_of` MUST 成立；过期从时间派生，不产生 `expired` status。
- **issuer trust + domain-authority filter**：`policy_snapshot.handle_issuer_policy[]` 的每个 entry MUST 是 `{issuer, authorized_handle_domains, issuer_class}`，其中 `issuer_id` 是 did_core_id，`authorized_handle_domains[]` 是该 issuer 可签发的 canonical A-label 域（精确域或 `*.<domain>` 子域模式），`issuer_class ∈ {domain_authority, delegated_issuer, directory_mirror}`。该数组的唯一 wire carrier 是 closed `ak.realm.policy_bundle` 的 `handle_issuer_policy` 成员。丢弃 issuer 未列入 policy、handle 的 `<domain>` 不在该 entry 授权域、或授权链无法回溯到该域权威根的 claim。该步是**强制前置**；v1 不接受无域作用域的裸 issuer 字符串作为 Realm handle policy。
- **audience scope filter**：丢弃 `c.audience` 存在且与当前 context 互斥（例如 audience 限定为另一 Realm 或另一 service DID）的 claim。`c.audience` 缺失视为"无 audience 限制"，保留在候选集。

**Step 1 — 优先级匹配**：在 Step 0 输出的候选集内，按以下优先级取第一个非空层：

1. **audience-matched**：`c.audience` 与当前调用上下文（target Realm ID 或邀请方 service DID）严格匹配。
2. **holder-flagged**：`c.handle == holder_primary_handle_at_as_of`（holder 主权偏好，源自 DID Document `metadata.primary_handle`，已在确定性输入元组中物化为标量；算法不再重新读 DID Document）。`holder_primary_handle_at_as_of == null` 时此层为空集。
3. **most-recent**：按 `c.claim.issued_at` 取最新者。

**Step 2 — Tie-breaker**（确定性收敛）：若 Step 1 选定层内仍有多个候选，按以下顺序消歧：

1. 同一 handle 域内按 `domain_authority`、`delegated_issuer`、`directory_mirror` 的顺序优先；只有 `issuer_class` 相同才比较 `c.issuer_id` 在 policy `handle_issuer_policy` 列表中的位置；
2. `c.claim.issued_at` 较晚者；
3. `claim_digest(c)` 字典序较小者（见下方定义）。`claim_digest` 是 claim 自身的 canonical identifier，不依赖 `proofs[]` 数组顺序——避免 issuer 重新打包 proof 时 tie-breaker 抖动；
4. 若 `claim_digest(c)` 仍同（极小概率：两份候选共享同一 canonical claim），取 `min(c.proofs[].payload_digest)` 字典序较小者作为最后保险。

**`claim_digest(c)` 定义**（normative，本节）：

```
claim_digest(c) = "sha256:" || hex( sha256( utf8("ak.handle_claim_proof.v1\n") || JCS(c.claim without proofs) ) )
```

其中：

- `JCS` 是 [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785) JSON Canonicalization Scheme；
- digest 输入是 `c.claim: HandleClaimCore` 的完整 closed property 集合，仅移除 `proofs`。所有 nullable/数组字段仍出现，禁止调用方另选投影白名单：

  | 字段 | 来源 | 数组规范化 |
  | --- | --- | --- |
  | `schema` | required core discriminator | — |
  | `handle` | canonical `<localpart>:<domain>` | — |
  | `handle_aliases` | required array | producer MUST UTF-8 bytewise sort |
  | `subject_account_id` | exact AccountId | — |
  | `issuer_id` | signing authority DidCoreId | — |
  | `claim` | closed claim variant | — |
  | `visibility` | required | — |
  | `audience` | required string/null | — |
  | `issued_at` | required | — |
  | `expires_at` | required timestamp/null | — |
  | `source_refs` | required array | producer MUST UTF-8 bytewise sort |

  Status、revocation 与 cache hint 位于 core 外，绝不进入 claim digest。由于 core `additionalProperties=false`，不存在 producer/Directory 自选的 hint 通道。

- 输出形态遵循 [`models/common-fields.md` §2](../models/common-fields.md) 的 `<noun>_digest = <alg>:<hex>` 通用 hash 字段命名规则；

  `claim_digest` 不上 status view wire：status view 只携完整 `claim`，verifier MUST 按上式从 `claim` 重算 `claim_digest`，再与两条 core proof 的 `payload_digest` 及 `revocation.claim_digest` 逐字比较；不等均 fail closed，不存在 wire 携带值可供比对的退化路径。

**Hint 隔离**(normative): Directory/cache 元数据只能存在于其本地 row 或独立 closed response carrier，禁止写入 HandleClaim core/status/revocation wire。未知字段由 schema 拒绝。

去除 `proofs` 与 server-attested hint 是为了让 `claim_digest` 只覆盖 claim 的**规范语义内容**而非签名包装与中间传输态，让同一 canonical claim 在任意 issuer 重签 / Directory 转发 / cache 层加注后始终产生相同 digest。

**Forward-compat**: 未来 spec revision 在 handle_claim.v1 中加入新规范字段时，该字段名 MUST 同步加入上表；实现 MUST 拒绝白名单外字段进入 digest 计算，即便它出现在新 schema 里——直到 spec 显式扩表。同时新字段若是数组，MUST 在加入表的同时声明数组规范化策略(sorted / order-is-semantic 二选一)；未声明的数组字段 MUST NOT 进入 digest。这保证不同 spec patch 版本之间 `claim_digest` 不会悄悄漂移。

#### 3.2.1.1 数组规范化规则（normative）

JCS（RFC 8785）保留数组顺序。为使签名字节唯一，producer 在签名前 MUST 将 core 的集合数组规范化；validator 遇到未排序或重复元素必须拒绝，不得先排序后接受：

| 数组字段 | 排序规则 | 排序粒度 |
| --- | --- | --- |
| `handle_aliases` | 元素字符串 lexicographic ascending（UTF-8 byte order，与 JCS 字符串排序保持一致） | 顶层数组元素 |
| `source_refs` | 元素 event_ref 字符串 lexicographic ascending（仅用于确定性 canonicalization，不表达签发时序） | 顶层数组元素 |

`proofs` 是 fixed tuple `[issuer_attestation, holder_acceptance]`，整体不进 digest；不存在 `claims[]`。Directory 与中间方不得 reorder core 数组或 proof tuple，任何改变都会使签名或 shape 校验失败。

Step 2 结束后候选 MUST 唯一；实现 MUST NOT 在仍有 tie 时随意选取。

Step 0 候选集为空时，renderer MUST fallback 到 §3.8.2 定义的"解析失败"路径，**不得**任意取一个 handle 显示，**不得**绕过 issuer trust filter。

primary handle 是显示语义；它**不**影响 actor_id 归因、grant subject 或 audit attribution——这些永远来自 `subject_account_id` 本身。

### 3.2.2 Handle Claim Lifecycle and Acquisition（normative）

Handle 的权威生命周期属于 issuer，不属于用户 profile 或 Realm MemberIdentity event。`ak.profile.update`、`ak.profile.realm_override`、`ak.member.identity.update` 中不得通过任意字段声明、覆盖、撤销或重分配 handle；这些事件最多影响 display name、avatar、subject disclosure 等 UI projection。验证器遇到这些事件中出现的非标准 handle 字段时 MUST 忽略或 schema-reject，不得把它们提升为 verified handle。

Arkret v1 core **不定义**用户注册、handle 申请、邀请审批、管理员通知、管理员审批队列、重签 / 续期、namespace 保留策略、抢注仲裁、多 handle 策略或组织内部身份治理 API。这些流程属于 issuer / Auth Server / 部署本地治理面；不同 Station、Organization 或自托管 issuer 可以按自己的合规、人事、IDP、邀请和审计要求实现。

协议层只规定 consumption contract：

1. 任何进入 Arkret roster、mention、directory resolve、exact AccountId targeting 或 UI verified display 的 handle MUST 来自可验证的 signed `ak.schema.handle_claim.v1` status view（其内含 signed core），或该 core 的 digest / reference。
2. issuer / Auth Server / 部署本地 API MAY 让用户选择 handle、提交申请、触发人工审批、由管理员直接分配、续签或撤销；这些 API 的 endpoint、权限模型、通知机制和状态机不属于 v1 core。
3. 这些外部流程一旦要把结果暴露给 Arkret 客户端或其它服务，MUST 输出完整 `ak.schema.handle_claim.v1` status view；revoked 必须内联独立 revocation carrier。仅让 Directory / roster 不再返回该 claim 不能证明撤销，未签名 issuer-side 状态不得替代 carrier。


contact request / invite / member-add 不再把 `resolve_handle(intent="contact_request" | "invite" | "member_add")` 作为 base 安全路径；正式 invite 寻址见 [`../sync/invite-addressing.md`](../sync/invite-addressing.md) 的 `invite_address + introduction_evidence` 模型，联系人请求见 [`contact-and-direct-conversation.md`](./contact-and-direct-conversation.md) 的 `contact_address + introduction_evidence` 模型。Directory 可选返回的 handle claim / candidate 只能作为 introduction evidence 或 builder evidence，不能替代显式 address、principal locator、receive policy 或 Join Policy 复核。


### 3.2.3 Registration and Invitation Strands（informative）

常见注册路径都在 Arkret core 之外完成，但进入 Arkret 后遵循同一 claim-led 模型：

- **系统预分配 handle**：用户完成注册 / 首次登录后，Auth Server / issuer bootstrap MAY 直接把 signed `handle_claims[]` 交给客户端或服务端 roster cache。用户无需发 `set_handle` event。
- **管理员邀请允许选择 handle**：邀请链接、pre-registration proof、审批通知和人工审核队列属于 Auth Server / issuer 策略。Arkret 只看到最终签发的 `ak.schema.handle_claim.v1`，或看不到任何 claim。
- **管理员后期修改现有用户 handle**：issuer 撤销 / 过期旧 claim 并签发新 claim。Realm history 中既有 messages、mentions 和 `ak.member.identity.update` 不被改写；当前渲染按新的 claim set 展示，历史 replay 按 as-of claim snapshot 展示。

因此，"用户注册后是否必须主动发包含 handle 的 profile"的答案是 **否**。用户 MAY 发 profile / MemberIdentity 来设置 display name、avatar 或 subject disclosure；handle 只来自 issuer-signed claim。

### 3.3 Handle claim 的 AccountId 绑定

账号 handle claim MUST 直接携带 closed `subject_account_id: AccountId`，不得只携 `principal_id` 后再用 Directory、
DID Document、当前 session 或接收服务推断 `station_id`。`subject_account_id` 的两个分量、handle、issuer、
audience 与时间边界都进入 claim proof transcript。Handle claim 不携带 membership delivery route；账号所属 Station
已由 `subject_account_id.station_id` 唯一确定，endpoint 另走 service resolution。

Handle claim 只证明“这个 handle 在声明上下文中寻址这个 AccountId”。它不是 membership grant、invite acceptance、
Contact consent 或 delivery authorization。用于 invite/member-add 时，调用方把 exact `subject_account_id` 复制到
`invitee_account_id`，最终仍需同一 AccountId 的 holder-authenticated acceptance 才能物化 membership。

### 3.4 Issuer 类型与 holder 控制

Handle issuer 可以是 holder、Organization、Station 或受信 Directory。proof verification method MUST 投影到
`issuer_id`，Directory 镜像还 MUST 回溯到有权签发该 handle domain 的上游 claim。无论 issuer 类型如何，均不得
替目标账号选择或改写 `station_id`；claim 中的完整 `subject_account_id` 必须由目标账号 holder acceptance
或相应受信注册证据逐字覆盖。

### 3.5 公开、受限与不可关联性

公开 handle MAY 通过 well-known、Directory 与 `alsoKnownAs` 披露；受限 handle 只在 requester、audience、intent 与
disclosure policy 通过后披露。不存在、撤销、受限与未授权分支对匿名调用方 MUST 不可区分。解析结果披露完整
AccountId，因此同一账号跨上下文复用同一 handle 不提供 unlinkability；需要不可关联性的部署必须使用不同的完整
AccountId 和独立 claim，不能只更换显示 handle。

### 3.6 Resolve intent 与最小披露

- `lookup` / `mention` 仅返回完成用途所需的 handle/display 信息；无授权时不得披露 AccountId；
- `contact_request` / `invite` / `member_add` 在策略允许时 MAY 返回 exact `subject_account_id` 与已验证 claim；
- 不同 intent 的结果不得提升或跨缓存复用；
- Directory 解析失败不得触发 DID Document 或当前服务默认补全。

### 3.7 Validator MUST 规则

verifier MUST 验证 canonical handle、closed AccountId、issuer authority、proof、audience、created_at/expires_at、撤销状态
与 intent disclosure policy。任一 AccountId 分量缺失或不匹配、同 core 但 server 不同、unknown JSON member、claim
过期或 issuer 无权时 MUST fail closed。解析返回的 AccountId 与预期 applicant、member 或 invitee 账号不一致时，
reducer 与客户端 MUST 拒绝该候选，不得据其构造 invite 或 join 材料。这是本地验证失败，不是 Directory 的公开错误面。
通过这些检查仍只得到寻址结果，不能直接写 membership。
### 3.8 Mention Reference 与 Display Snapshot（normative）

事件内对某 subject 的引用，其**权威引用字段** MUST 使用完整 `AccountId`（`subject_account_id`），不得用裸 DID、`did_core_id` 或 handle 字符串作为 actor 归因、授权判断、解析路径的唯一来源。

**适用范围（normative，逐条对应 v1 wire）**：v1 中自带 subject 载体的引用只有 mention 一处，本节的 `subject_account_id` 规则即指它——`event-payload.schema.json#/$defs/mention_node`，经 `content_block.mentions[]` 承载（[`../models/strand-and-message.md` §9.4](../models/strand-and-message.md)）。其余同族引用在 v1 里各有自己的已登记载体，**都已经是 exact 形态、都不是裸 principal**，本节不改写它们：
- reply target 的作者引用是 `content_block.reply_context.sender_actor_id`，类型为完整 `ActorId`（它引用的是一条已签名 Event 的作者，作者身份的登记类型就是 ActorId）；
- reaction 的目标是 `reaction_payload.target_ref`（object ref），发起方身份来自 envelope `actor_id`，该 payload 没有、也不需要 subject 载体；
- quoted profile 与 forwarded message 在 v1 wire 上没有独立的 `$defs`，因此没有可被本节约束的字段；MIMI 互通的 `mimi_message_provenance.attributed_sender_actor_id` 同样是完整 `ActorId`。

共同的硬约束只有一条：**任何一侧都不得退化到裸 `principal_id` 比较**（[`common-ids.schema.json#/$defs/actor_id`](../../artifacts/schemas/common-ids.schema.json) 明文禁止），也不得把同 principal 的另一 Station 账号合并（[`../discovery/discovery-directory.md` §9](../discovery/discovery-directory.md)）。AccountId 与 ActorId 的选择按被引用者的角色决定：mention 寻址的是**账号**，故用 `AccountId`；Event 作者身份寻址的是**actor**，故用 `ActorId`。同一事件 MAY 同时携带 handle / display name / controller-scoped agent selector 的历史快照作为 audit / search / 兜底展示的 metadata（见 §3.8.1），但这些 metadata 字段不参与协议层信任决策（见 §3.8.3）。

该规则的根本动因：handle 的 `<domain>` 部分是 issuer 的 authority domain（组织 / holder 自己持有的域名），不是 subject 用户控制的标识。如果把 domain 作为**权威**引用字段持久化进每一个引用点，issuer 的 DNS 治理成本（domain 迁移、authority 重命名）就会转嫁给所有历史事件，并被迫做事件改写。完整 `AccountId` 才是稳定账号标识；裸 DID / `did_core_id` 只承担解析与控制角色，handle 是稳定标识的可读 label，由解析层实时计算；事件内的 handle metadata 只是"当时是什么"的 audit 快照，不是"现在是什么"的真相源。

§17 wire-level 作用域规则配套约束了 handle 字符串作为**权威字段**可以出现的位置。MemberIdentity 不再携带 handle 字符串；Realm-scoped roster 若需要加速渲染，只能内联签名 handle claim evidence 或 digest hint（详见 [`sync/client-sync.md` §8.1](../sync/client-sync.md)）。

#### 3.8.1 字段定义

mention reference / profile snapshot 的 normative shape：

| 字段 | 类型 | 必填 | 用途 |
| --- | --- | --- | --- |
| `kind` | `const("mention")` | MUST | 节点判别器；`content_block.mentions[]` 只承载该一种 canonical 形态。 |
| `subject_account_id` | `AccountId` | MUST | 被引用账号的完整稳定标识（含 principal 与 Station 分量）；唯一参与 actor 归因、授权判断、解析路径与渲染查找的字段。 |
| `display_name_at_time` | string | MAY | event 时刻 subject 的 display name 快照；持久化、不再更新；renderer MAY 直接显示。 |
| `handle_at_time` | canonical handle string（§3.1 主形态） | MAY | event 时刻 subject 的 handle 快照；**仅** audit / debug / 全文搜索 / 历史回溯用途；**MUST NOT** 作为当前显示标识。 |
| `controller_subject_account_id` | `AccountId` | MAY | 历史 Agent selector mention 或已知目标 picker 记录 controller 的完整账号标识；仅 audit / fallback metadata，权威 target 仍是 `subject_account_id`，不得由此恢复自由文本解析。 |
| `controller_handle_at_time` | canonical handle string（§3.1 主形态） | MAY | 已验证 controller handle 的历史快照；仅 audit / debug / 搜索用途，MUST NOT 作为自由文本解析来源。 |
| `agent_slug_at_time` | string | MAY | 已验证 `agent_slug` label 的历史快照；仅 audit / debug / 搜索用途，MUST NOT 作为自由文本解析来源。 |
| `mention_text_original` | string | MAY | 用户键入的原始输入（例如 `@alice:acme.com` 或 `alice@acme.example`）；audit 与搜索索引用途，不参与渲染逻辑。 |
| `resolved_at` | timestamp | MAY | 客户端解析 handle / subject 或校验已知 Agent label 的时刻；audit metadata。 |

`display_name_at_time` 是 snapshot 语义——一旦写入事件即固定，防止 subject 后续修改 display name 时回写历史（这条边界对反冒充很重要）。`handle_at_time`、`controller_handle_at_time` 与 `agent_slug_at_time` 是 audit metadata，不是显示字段或解析字段。

#### 3.8.2 渲染规则（normative）

UI 渲染 mention / profile reference 时 MUST 按下列流程（HandleClaim status view 的 `status` 是 closed `pending | verified | revoked`；`expired` 是对 `claim.expires_at` / `fresh_until` 的本地求值结果，不是 wire status）：

```
1. Realm-scoped projection 优先解析：
   renderer 先构造本次渲染输入对应的 MemberIdentity + handle-claim snapshot：
   - 实时渲染使用当前 effective set；
   - 历史 replay / audit 使用 resolution_as_of 时刻的 as-of effective set；
   - 若实现无法构造对应 as-of snapshot，step 1 失败。
   在该 snapshot 中筛选与 `mention.subject_account_id` 匹配的 MemberIdentity 候选。
   **联接键（normative）**：MemberIdentity 声明的是 `subject_actor_id: ActorId`（[`member-identity.schema.json`](../../artifacts/schemas/member-identity.schema.json)），
   而 mention 携带的是 `AccountId`，因此联接式固定为：取 `subject_actor_id.kind == "account"` 的候选，
   再把其 `subject_actor_id.account_id` 与 `mention.subject_account_id` 逐字节比较（`principal_id` 与
   `station_id` 两个分量都必须相等）。`service` 分支**不参与** mention 解析与 handle projection：
   mention 寻址的是账号，service actor 没有可被 @ 的账号身份。实现 MUST NOT 用 `principal_id`
   单独比较来"放宽"该联接。
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
   resolve_primary_handle(subject_account_id, current_context, resolution_as_of) → handle_claim
   （按 §3.2.1 选择规则，跨 Realm / live Directory / cache，
   返回完整 signed HandleClaim status view；历史 replay / audit
   MUST 使用 resolution_as_of 对应的 claim_set_snapshot / policy_snapshot，
   不得静默 live-resolve 到当前状态）。
3. 显示判定：
   - step 1 成功 → 显示 "@{localpart}:{domain}"（来自选中 `handle_claim.claim.handle`）；
   - step 2 成功且 `handle_claim.status == "verified"`、`resolution_as_of < handle_claim.fresh_until`、core 未过期且 revocation fields 为 null
     （或 §6.0 server-attested verified hint 命中且本地 trust policy TTL 内）
     → 显示 "@{localpart}:{domain}"（来自该 handle_claim 的 canonical handle）。
4. 解析失败（DID 不可达 / 无 active claim / §3.2.1 选择不唯一 /
   MemberIdentity snapshot 不可构造或不唯一 / step 1 校验 a-d 任一失败 /
   step 2 `status ∈ {pending, revoked}` 或 status/core freshness 已过期）：
   按以下顺序 fallback：
   a. 本地 cache 中最近一次 verified primary handle（标记 "cached"）
   b. event 内 display_name_at_time（标记 "name only"）
   c. truncated DID 形态（例如 "did:webvh:z2dmj…3kF"，标记 "unresolved"）
5. 任何 fallback path MUST 在 UI 上有明确的视觉降级标识；
   实现 MUST NOT 把 fallback 显示成与正常解析无差别的形态。
```

`resolution_as_of` 是本次渲染选择的解析基准时刻：实时渲染通常是 renderer 解析这一刻；历史 replay / audit 是被重放视图声明的 as-of 时刻。它与 §3.2.1 的确定性六元组配合使用（`subject_account_id` / `context` / `claim_set_snapshot` / `policy_snapshot` / `holder_primary_handle_at_as_of` / `resolution_as_of`）。`claim_set_snapshot` 与 `policy_snapshot` 都是 as-of snapshot（详见 §3.2.1 normative 段）。同一 mention 在不同时刻可能因 handle claim set 变化、cache TTL、claim 生效或过期边界、DID Document update、Realm policy 调整或 MemberIdentity subject disclosure 变化落入不同分支，这是预期行为而非违反确定性——确定性保证的是六元组等同时输出等同。

renderer **不得**在主显示路径使用 `handle_at_time`。`handle_at_time` 只允许出现在以下场景：

- 显式标记为"历史值"的 audit view（例如"该消息发布时此用户的 handle 为 …"）
- 开发者 / 管理员 debug overlay
- 全文搜索 snippet（让搜索"alice:acme.example"能命中包含该旧 handle 的历史消息）

renderer 检测到 `handle_at_time` 与当前 primary handle 不一致时，MAY 在 UI 上加 "handle changed since" 类提示——这是显示层增强，不是 normative 协议要求。是否提示、提示的具体形式由产品决定。

holder 的实时身份面还 MUST 应用 [`discovery/client-preferences.md` §3.6](../discovery/client-preferences.md) 的全局 Contact `petname` 覆盖层：只有 `subject_account_id` 能经 verified evidence 唯一归约到 accepted human Contact 的 `peer.account_id` 时，非空 `petname` 才取代上述 live handle / display fallback 成为主标签，并带“备注”角标；handle、Realm override 与全局 display name转为次要上下文。该覆盖层不改变本节解析结果。

历史 replay / audit / export 仍按 `resolution_as_of` 和事件快照执行本节流程；当前 `petname` 最多作为明确标注的 holder-private name 并列，MUST NOT 覆盖 as-of handle、`display_name_at_time`、`subject_account_id` 或 audit attribution，也不得写入共享 Event、forward、quote、share 或 Realm export。

#### 3.8.3 与 actor 归因的关系

`display_name_at_time`、`handle_at_time`、`controller_subject_account_id`、`controller_handle_at_time`、`agent_slug_at_time`、`mention_text_original` 都是 **UI 元数据**，对协议层信任决策完全透明。verifier / reducer / policy engine MUST 忽略这些字段，只读 `subject_account_id` 做以下判断：

- grant subject 校验
- audit attribution
- membership / Realm 决议
- sender verification
- ACL / capability 校验
- federation peer attribution

也就是说：篡改 mention reference 的元数据字段不构成协议层攻击（最多骗 UI 显示），但篡改 `subject_account_id` 会被 event envelope 签名直接拒绝。

#### 3.8.4 与 Organization Authority Migration 的关系

因 §3.8 规定权威引用字段一律 DID-committed，组织 authority domain 迁移（`acme.example → acme.com`）在历史事件层不需要 rewrite：

- 旧事件内的 mention / profile reference 权威字段是 `subject_account_id`，subject 不变；
- 渲染时按 §3.2.1 解析当前 primary handle，得到新 domain 的 handle 字符串；
- 历史事件本身**不需要**rewrite、migration script 或 schema upgrade；

domain 迁移因此从"全网事件改写工程"降级为"issuer 侧 batch 签名 + claim cache TTL 冷却"。事件内的 `handle_at_time` metadata 与 issuer 的 as-of claim ledger 让 audit 仍可重建任意历史时刻的 handle 字符串。

## 4. Handle 绑定

公开 persona DID MAY 使用：

```json fragment
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
issuer claim:        handle → subject_account_id   (issuer 单方面签名声明)
holder DID Document: subject_account_id → handle   (列入 alsoKnownAs，holder 单方面承认)
```

没有 holder 侧这条边，任何被信任的 issuer 都可以单方面把 handle "塞" 到受害者 DID 上而 holder 无从拒绝。`alsoKnownAs` 把这种 issuer-unilateral 攻击降级为 issuer × holder 双方均需主动表态——`did:webvh` 等带历史 method 还能让 alsoKnownAs 增删进入可回溯链路，使 holder 的撤销动作具备 audit 证据（§6.1.2 第 3 条）。

`alsoKnownAs` **不参与**以下机制；这些机制各自有专用字段或独立机制：

| 机制 | 权威字段 / 路径 |
| --- | --- |
| Realm 内投递目标服务 | member `ActorId` 的 `account_id.station_id` |
| Realm 邀请 / Join Policy | exact `AccountId` + target holder acceptance；handle claim 只提供 issuer/audience 受限的寻址证据 |
| Actor / 签名归因、审计 | Event envelope 的完整 canonical `ActorId`；签名 key 的 DID/DID URL 独立验证 |
| endpoint 搬迁、域名变更 | 同一 service DID 的已验证 AuthenticatedServiceResolution；账号 Station 分量变化是另一 AccountId，不是原账号 route 更新 |
| 受限 handle（组织内部账号） | issuer claim + audience + scope（§3.5 默认不进公开 DID Document） |
| Pairwise / agent / 临时 DID；设备 verification method | 显式 SHOULD NOT 写入 `alsoKnownAs`（设备自身没有 DID；见上文与 [identity-did.md](./identity-did.md) §6 末段"Pairwise / private DID SHOULD NOT 包含公开 handle"，以及 §9 验证规则） |
| 跨上下文 unlinkability | pairwise DID 机制，正交于 handle 层（§3.6） |
| Handle 重分配后的历史归因 | 历史 Event 内固化的完整 `subject_account_id: AccountId` 与 display snapshot（§6.1.3） |

实现 MUST NOT 把 `alsoKnownAs` 用作 mention 索引、Directory 主键、缓存键、投递路径或 actor 归因依据；它的唯一规范用途是"public handle 的 holder-side 反向背书"。

## 5. Handle 解析

Handle 解析分为两个方向：


已知 handle 时，自己 Station 的 verifier 按以下顺序尝试 issuer，第一个成功签发可验证 claim 的就是该 handle 的 issuer：

1. **`<domain>` 的 well-known**：`GET https://<domain>/.well-known/arkret/handle?localpart=<localpart>`。响应是 `ak.schema.handle_claim.v1` 形态的签名 claim。
   - 用于 holder 自托管（domain 拥有者 == subject DID）与单实例 Station 部署。
   - **`.well-known/arkret/handle` 是签名 issuer 通道，不是泛 resolver 端点（normative）。** 该路径的语义被钉死为"返回该 `<domain>` 作为 issuer 为 `<localpart>` 签发的 signed `ak.schema.handle_claim.v1`"。任何在该路径作出响应的部署都被 verifier 当作该 handle 的候选 issuer。因此：
     - 能签发 claim 的 issuer（holder 自托管 well-known、单实例 / 组织 Station）MUST 在此返回 200 + 签名 claim，或返回 issuer-side not-found / revoked 状态；但对匿名或未授权调用方，not-found、revoked、restricted、unauthorized 与 rate-limited MUST 使用不可区分响应，避免把该端点变成 handle / 雇佣关系枚举 oracle。只有已认证且按 policy 有权观察该 claim 的调用方 MAY 获得精确 revoked / expired / not-found 诊断。
     - 受限 handle claim MUST 经 requester / audience 授权后才可由 well-known 返回。授权证据 MAY 是 bearer session、DPoP/device proof、Directory `claim_presentations[]`、Realm invitation / membership context 或 issuer 本地 policy 可验证的等价证明；缺失或验证失败时按上一条不可区分拒绝处理。
     - **纯 resolver（只索引 / 转发、自身签不了 handle claim 的服务）MUST NOT 占用该路径返回未签名的 issuer-probe 结果。** 纯 resolver 在 `.well-known/arkret/handle` 的合规行为只有两种：(a) **不提供该端点 / 返回 `404`**；或 (b) **显式委托**到上游可签发 issuer（例如 HTTP 重定向到该 issuer 的 well-known，或在响应中给出可独立验签的上游 `source_refs` 指向 signed claim）。它 MUST NOT 在该路径返回任何未签名的 handle / subject / probe payload——否则 verifier 会把一个签不了 claim 的服务误当 issuer，污染 §5 的 issuer 选择与 §6 的双向验证。
     - resolver 想暴露"这个 handle 我索引到哪个 subject / issuer"这类 **issuer-probe / 索引查询**，MUST 走产品私有面（私有 API、内部 directory query 等），不得借用 `.well-known/arkret/handle`。需要被 Arkret verifier 采信时，走第 3 步 signed Directory response（`ak.schema.handle_claim.v1` + `source_refs`），而不是未签名 probe。
2. **DNS TXT**：`_arkret.<domain>` 或 `_arkret.<localpart>.<domain>`。仅当 DNSSEC validation 成功**且** TXT 内含可验证签名时才能作为 issuer 通道；裸 DNS TXT 只是发现 hint。
4. **Bridge / 外部 issuer**：当 handle 来自 bridge 或外部体系（例如组织自有 IDP），claim 由该体系签发并通过 §7 VC presentation 出示。

解析结果 MUST 包含 §3.2 列出的字段；audience / scope / expiry 决定使用范围。multiple issuer 同时签发同一 handle 时，verifier 先按 §3.2.1 的域授权与 `issuer_class` 收敛：有效 `domain_authority` claim 优先于 delegated issuer，二者都优先于 Directory mirror；Directory claim 的 `source_refs` MUST 验证到该域权威根，否则直接排除。只有同一最高 issuer class 内仍存在不同 `subject_account_id` 的有效 claim 才 MUST fail closed 并交人工处理。低 authority 冲突不得让已经验证的域权威绑定失效，从而避免镜像 issuer 注入冲突造成解析 DoS。


Handle 解析示例：

```text
HandleClaimStatusView {
  schema: ak.schema.handle_claim.v1,
  claim: HandleClaimCore {
    schema: ak.schema.handle_claim_core.v1,
    handle: alice:alice.dev,
    handle_aliases: [],
    subject_account_id: { principal_id: <alice>, station_id: <alice-station> },
    issuer_id: <alice>,
    claim: { kind: handle_binding },
    visibility: public,
    audience: null,
    issued_at: 2026-05-19T00:00:00.000Z,
    expires_at: 2026-08-19T00:00:00.000Z,
    source_refs: [],
    proofs: [issuer_attestation, holder_acceptance]
  },
  status: verified,
  as_of: 2026-05-19T00:01:00.000Z,
  verifier_id: <verifier-service>,
  verified_at: 2026-05-19T00:01:00.000Z,
  revocation: null,
  fresh_until: 2026-05-19T00:06:00.000Z,
  status_proof: status_attestation
}
```

这是 self-issued handle（holder 自己控制 `alice.dev` 域名，`issuer_id` 等于 `subject_account_id.principal_id`）。组织签发 handle 的示例：

```text
HandleClaimStatusView {
  schema: ak.schema.handle_claim.v1,
  claim: HandleClaimCore {
    schema: ak.schema.handle_claim_core.v1,
    handle: alice:acme.example,
    handle_aliases: [acct:alice@acme.example],
    subject_account_id: { principal_id: <alice>, station_id: <alice-station> },
    issuer_id: <acme-issuer>,
    claim: { kind: organization_handle, organization_id: <acme> },
    visibility: restricted,
    audience: ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5,
    issued_at: 2026-05-19T00:00:00.000Z,
    expires_at: 2026-08-19T00:00:00.000Z,
    source_refs: [],
    proofs: [issuer_attestation, holder_acceptance]
  },
  status: verified,
  as_of: 2026-05-19T00:01:00.000Z,
  verifier_id: <directory-verifier>,
  verified_at: 2026-05-19T00:01:00.000Z,
  revocation: null,
  fresh_until: 2026-05-19T00:06:00.000Z,
  status_proof: status_attestation
}
```

## 6. 双向验证

本节 verifier 指接纳外部身份材料的 Station / Directory 或独立审计角色。普通客户端消费自己已认证 Station 的公开解析结果，核对完整 AccountId、handle、subject、audience 与有效期，不回取发行者或 holder DID 历史。任意第三方 Directory 的声明仍须由自己 Station 验证，不能直接提升为权威结果。

解析 handle 得到 exact `subject_account_id` 与 issuer `did_core_id` 后，验证规则按 handle 的公开 / 受限语义分两条：

**公开 handle（holder 主动公开）**：verifier MUST 取得与 `subject_account_id.principal_id` 具有已验证 resolution binding 的当前 DID Document，并验证：

```text
did_document.alsoKnownAs contains the canonical handle
```

"取得当前内容" MAY 通过下列任一方式满足：

- 现场（live）解析与 `subject_account_id.principal_id` 绑定的 DID Document；或
- 命中 verifier 自有缓存条目（含 verifier 完全信任、共享同一 DID resolver 与 trust policy 的 co-trusted node，例如自己的 personal node 缓存），且该条目按 §6.1.1 绑定了 DID Document version / digest、`alsoKnownAs` proof，并仍在 TTL 内、未触发 §6.1.2 任何失效信号。

跨信任边界（例如第三方 Directory / 其它组织的 Station）下发的 signed `status=verified` view 不属于此处可直接满足 MUST 的"缓存条目"——它属于 §6.0 Cache 层的 hint，只能用于明确允许接受 server-attested 结果的展示动作。双向验证失败 MUST NOT 把该 handle 当作公开可信绑定。

**受限 handle（issuer 是 Organization / Station / Directory，holder 未公开）**：handle claim 可能不出现在 holder 公开 DID Document 中；此时 verifier MUST 改为验证：

- issuer claim 签名有效，且 issuer 在当前调用上下文的本地 trust policy 内；
- **holder 侧接受证据存在且有效**（见下方"对称信任"要求）；
- `claim.audience` 与当前调用上下文一致；
- request / presentation transcript 的 challenge 未过期、未重复使用；challenge 不在 HandleClaim core 内；
- `claim.claim` closed variant 与 `claim.audience` 覆盖当前用途，不存在开放 `claim_scope`；
- 顶层 signed `status` 仍为 `verified`，`fresh_until` 与 `claim.expires_at` 均未过期，revocation fields 为 null；
- holder consent / organization policy 允许向当前 requester 披露。

**对称信任：受限 handle 的 `verified` 必须有 holder 侧背书（normative）**：公开 handle 的 `verified` 靠 `alsoKnownAs`（§4.1）提供 holder 侧反向背书，把 issuer-unilateral 攻击降级为 issuer × holder 双方均需表态。受限 handle 不进公开 `alsoKnownAs`（出于 unlinkability / 最小披露），但**不得因此免除 holder 侧背书**——否则 `accepted_issuers` 内任一被攻陷 / 恶意 issuer 即可为受害者账号签发 verified claim，在其 audience 内冒名受害者。因此：当 `claim.subject_account_id.principal_id` 不受 issuer 控制时，受限 handle 要显示为 `verified` / 驱动任何信任决策（grant 条件、roster 强归因、exact AccountId targeting），其 `claim.proofs[1]` MUST 是由 holder accepted account-service authority 签发、覆盖完整 HandleClaimCore（含 `handle`、完整 `subject_account_id`、`audience` 与 closed claim variant）的 `holder_acceptance` proof。verifier MUST 校验 proof 中的完整 AccountId，而不是只验证裸 principal DID。

- 缺少有效 `claim.proofs[1]` holder-acceptance proof 时，该受限 handle core 只是 **issuer-attested**（issuer 单方声明、未经 holder 确认），任何 verifier 都不得为它签发 `status=verified`：verifier MUST 拒绝把它纳入 verified candidate（`reason=handle_holder_acceptance_missing`），UI MUST NOT 显示为 verified，且 MUST NOT 用它驱动 grant 条件、roster 强归因或 exact AccountId targeting。
- **issuer 自管 DID 例外(非豁免)**：当与 `subject_account_id.principal_id` 绑定的 DID 由 issuer 自己控制（受管 DID 配发，例：组织为新员工铸 `did:webvh` 并签发 `@alice:acme.example`）时，issuer 本就能用该 DID 的密钥产出 holder-acceptance proof，故该要求对正常组织配发**自动满足**、不增加摩擦；它只在 subject core 绑定的是外部 / 既有 DID 时真正生效，而那正是冒名风险所在。

DID Document 缺失 `alsoKnownAs` 单独**不**构成"受限 handle 无效"的判定（受限 handle 本就不进公开 `alsoKnownAs`）；但缺少上述 holder-acceptance proof（且 `subject_account_id.principal_id` 未绑定到 issuer 自管 DID）则 MUST NOT 显示为 verified。判定 = issuer claim 验签链 + holder-acceptance proof + audience / scope 校验。

### 6.0 验证职责分工

接纳服务器 MUST 在接受外部 handle、为 invite / official Realm 准备身份目标、求值公开 disclosure policy 或生成审计结果之前，完成本节双向验证。自己 Station 的已验证结果可直接用于客户端展示及目标选择；客户端仍核对用户选择与完整账号，不独立解析 DID。Wallet 对私有明文及密钥释放的用户授权仍在设备上执行。

这些 current reverse-binding 动作统一登记为 verifier action
`ak.verifier.handle.public_reverse_binding.v1`，使用 `current_external_claim` 与
`ak.did_freshness.current_external_claim.v1`；§3.2.1 的 historical primary selection 则登记为
`ak.verifier.handle.primary_selection_at_as_of.v1`，使用 `accepted_at_history` 且
`freshness_profile_id=null`。两行由
[`did-freshness-profile-registry.json`](../../artifacts/registry/did-freshness-profile-registry.json)
双向关闭；其它 handle action 不得自行调用 authority resolver。

**验证结果与缓存**：自己 Station MUST 验证外部 status/core、issuer/holder acceptance、subject、audience、撤销及 freshness 后提供结果；第三方 signed status 不因自称 verified 而免验。服务器缓存绑定 DID Document digest/version、反向绑定依据和有效期；首次接纳、依据变化及失效时重新核验，普通命中复用结果。

客户端可使用自己 Station 返回的有效 status view 展示身份状态，不区分“客户端完整验证”与“服务器验证”两种模式，也不因缺少本地 DID 历史降低标识。失效或无法刷新时按原 freshness 合同降级；服务器验证身份不等于用户完成端到端设备带外验证。服务器处理已确定 AccountId 的普通 Event、路由和 reducer 不重新读取 `alsoKnownAs`；公开 claim 验证不能改变既有 AccountId 的业务授权根。

**DNS TXT 通道**：DNS TXT 只能作为发现通道。若 issuer 通过 DNS TXT 直接声明 handle 绑定，自己的 Station MUST 验证以下至少一项，才可返回 verified：

- DNSSEC validation 成功，且 TXT 内容绑定 `handle`、完整 `subject_account_id` / issuer 的 `did_core_id`、`created_at`、`expires_at` 和 signature / hash commitment。
- TXT 记录内的绑定声明由 issuer DID（holder DID 或 Organization DID 或受信 issuer）签名，接纳服务器通过 DID resolver / VC 验证该签名。
- HTTPS well-known 或 Directory / VC presentation 提供等价的签名绑定证据。

未启用 DNSSEC 且没有可验证签名的 DNS 结果只能作为 unverified discovery hint，MUST NOT 作为 grant subject、Organization membership、official Realm 或 verified handle 的依据。

### 6.1 缓存与失效

Handle 解析结果是带时间边界的绑定，不是永久身份事实。

#### 6.1.1 缓存规则

- verified handle cache MUST 绑定 `claim.handle`（canonical `user:domain` 形态）、完整 `claim.subject_account_id` / `claim.issuer_id`、`claim_digest`、已接受的 DID resolution binding、DID Document version / digest、alsoKnownAs proof、两张 core proofs、顶层 `status_proof`、`verified_at`、`fresh_until`、`claim.expires_at` 和 resolver policy。core 同时携带 `handle` 与 `handle_aliases[]` 时，缓存键 MUST 取 `claim.handle`；`acct:` alias 只作为附加索引，但仍指向同一 cache entry。
- alias lookup 命中缓存时，verifier MUST 跳转到 canonical `handle` 的 freshness re-check 路径：重新检查 TTL、issuer revocation、DID Document digest / version、alsoKnownAs proof 与 resolver policy。实现不得把 `handle_aliases[]` 中的 `acct:` 或其它互通别名当作独立 cache key 直接返回 verified claim，也不得为 alias 单独延长 freshness window。
- handle cache 若含 `subject_account_id`，还 MUST 绑定完整 AccountId、claim digest 与 audience/scope；缓存结果不得跨 Realm 或跨组织上下文复用，除非 claim 明确授权。
- DNS / HTTPS 解析结果的 TTL **MUST NOT** 超过以下各项中的最小值：底层 DNS TTL、HTTPS response cache headers、签名绑定 `expires_at`、DID Document cache TTL，以及部署对 `ak.did_freshness.current_external_claim.v1` 申报的 `fresh_for_seconds` / `hard_expiry_seconds`。任一来源未给 TTL 时也只能使用该 profile 的部署申报值，不存在独立的 24 小时默认值或 stale grace；到达 profile 边界后 Authority 动作同步刷新或 fail closed。展示 hint 可更早降级，但不得延长 Authority freshness。
- 当 DID Document 移除对应 `alsoKnownAs`、issuer claim 被 revoke / expired、well-known 绑定变更、DNSSEC validation 失败、handle 被解析到不同 DID、或 resolver policy 更新时，缓存 MUST 失效或降级为 unverified。

#### 6.1.2 撤销与失效信号

v1 不引入专门的 handle 撤销 event。撤销通过下列两条独立路径完成，客户端或 Station 任一通道发现失效即 MUST 同步本地缓存：

1. **TTL 自然过期**：缓存到达 `expires_at` 后 MUST 重新拉取；不得在 TTL 之外使用。
2. **DID Document / status 变化**：holder 移除 `alsoKnownAs` 中的 canonical handle，或 issuer 发布 `status=revoked` view、signed `fresh_until` 到期、core 到达 `claim.expires_at`；下一次 verify pass 失败时 MUST 失效。`expired` 不编码进 status。

handle issuer SHOULD 对高变更 handle 发布短 TTL（≤1h）。**v1 不要求**服务端推送 handle 失效事件；客户端 MUST 按 TTL + DID/status 路径处理失效，**不得**依赖 Directory write/notification 或未注册的 `ak.handle.*` wire kind。

#### 6.1.3 Handle 重分配与历史归因

handle 字符串可以在 issuer 治理下被重分配到不同 DID（典型场景：员工离职后 localpart 被分配给新员工）。重分配 normative 规则：

- **DID 与签名责任不可改写**：Handle 转让或重分配 MUST NOT 改变历史 Event 的 actor DID、签名责任或 audit attribution。授权、grant subject、membership、MLS credential 与 audit attribution MUST 使用 DID / verified claim，而不是缓存中的 handle 字符串。
- **历史 mention 显示**：mention 与 profile reference 在事件中的**权威引用字段**只持有 `subject_account_id`（详见 §3.8）；handle 字符串只能作为 §3.8.1 定义的 audit / search metadata（`handle_at_time` / `mention_text_original`）出现。渲染历史 mention / message text 时，UI MUST 按 §3.8.2 实时解析 primary handle 显示，**不得**用事件内 `handle_at_time`（若存在）作为当前显示值。handle reassignment 的语义自然结果是：旧消息里 `@alice:acme.example` 这条 mention 解析到的 `subject_account_id` 仍是原 Alice，渲染时显示她**当前的** primary handle；新拿到 `alice` localpart 的人是一个不同的 `subject_account_id`，不会被回填进历史 mention。若 renderer 检测到事件内 `handle_at_time` 与当前 primary handle 不一致，MAY 加 "handle changed since" 提示（显示层增强，非 normative）。
- **新分配生效**：新持有者拿到 handle 后 MUST 通过 issuer 重新发布 handle claim（新 `subject_account_id`、新 `created_at`、独立的 `service_acceptance_ref`）；旧 claim 的所有缓存按 §6.1.2 失效。
- **membership 不随 handle 迁移**：handle 重分配不改变既有 Realm membership。新持有者要加入同一 Realm，必须以自己的 exact AccountId 完成新的 invite/accept/join 流程。

## 7. Verified Claim

Handle、组织成员、邮箱控制权和角色 SHOULD 通过 credential / attestation 表达。

授权判断 MUST 检查：

- issuer 是否被目标 Realm / Policy 信任
- subject DID 是否匹配当前 actor
- claim 是否在有效期内
- claim 是否未撤销
- claim 内容是否满足 grant constraint
- presentation 是否绑定当前 verifier challenge / domain
- claim 的 `subject_account_id` 是否由 issuer 与 holder 逐字绑定，且 intent/audience 允许当前用途。

## 8. 隐私保护型 Handle 证明

DID Document MUST NOT 被用作跨组织身份画像。公开或半公开 DID Document MUST NOT 直接列出以下信息，除非主体明确希望这些信息被关联：

- `alice@google.com`
- `alice@facebook.com`
- 第三方 profile URL
- 跨组织账号名
- 受限 handle 到 exact AccountId 的映射
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
4. Google 或受信 issuer 给 `did:key:z6Mkgpairwise...` 签发外部 W3C type `https://arkret.org/v1/credentials/organization-membership`；Arkret 内部对应的 `claim_kind` 仍为 `organization_membership_credential`
5. Facebook 或受信 issuer 给 `did:key:z6Mkfpairwise...` 签发独立 credential
6. 面向 Google verifier 时，wallet 只生成 Google 相关 presentation
7. Google verifier MUST NOT 要求披露 Facebook credential、Facebook DID 或跨域 subject identifier

## 11. Credential 示例

如果 verifier 只需要知道“该主体拥有 Google 组织内有效账号”，presentation SHOULD 披露抽象 claim：

```json illustrative
{
  "@context": ["https://www.w3.org/ns/credentials/v2"],
  "type": [
    "VerifiableCredential",
    "https://arkret.org/v1/credentials/organization-membership"
  ],
  "issuer_id": "did:webvh:z3HmjyqtBNmTZXtJQsQQqpBnX:google.example",
  "credentialSubject": {
    "id": "did:key:z6Mkgpairwise...",
    "organization_id": "ak:did_core:webvh:z3HmjyqtBNmTZXtJQsQQqpBnX",
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

```json fragment
{
  "credentialSubject": {
    "id": "did:key:z6Mkgpairwise...",
    "handle": "alice@google.com",
    "handle_verified": true
  }
}
```
该 disclosure MUST 绑定单一 verifier challenge / domain，并且 MUST NOT 自动披露其他组织 handle。

## 12. 披露请求的最小化原则

Verifier MUST 使用最小披露请求，不得请求"所有 alias"或"所有账号"。请求 MUST 指定 accepted issuer、所需 claim kind 与每个 claim 的披露档（abstract / explicit），并显式列出拒绝披露的字段。

Wallet MUST 展示将要披露的 claim。
Wallet SHOULD 拒绝或警告请求无关 handle、global subject identifier、credential id 或不必要人口属性的披露请求。

Arkret v1 不为通用 credential 披露定义 wire Event 或服务端点：本节是对 §9 所列外部 VC 机制的使用约束。Arkret wire 上唯一的私有披露路径是 §16 的 Agent requested-scope 私有披露。


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
condition = has valid organization_membership_credential where organization_id = ak:did_core:webvh:z3HmjyqtBNmTZXtJQsQQqpBnX
```

错误：

```text
grant subject = alice@google.com
```

如果 holder 后续为另一个组织出示不同 pairwise DID，除非 holder 显式提供 linking proof，否则 verifier MUST 将其视为独立隐私上下文。

## 16. Agent requested-scope 私有披露（normative）

Agent 的 immutable global ceiling（`requested_scope`）只以域分离 digest 的形式出现在公开 DID Document 与其历史中。当 authorizing verifier 需要判定该 ceiling 时，controller MUST 通过本章的 verifier-bound 私有披露出示完整 scope。

v1 不定义通用 credential presentation Event：本章是 Arkret wire 上唯一的私有披露路径。其载体是 [`agent-requested-scope-disclosure.schema.json`](../../artifacts/schemas/agent-requested-scope-disclosure.schema.json) 的闭合对象，只经认证机密通道一次性出示，不产生 durable Event、typed current result 或 account data；它是授权证据，不授予任何 action 或 resource，也不是把 scope 发布为 credential registry 或 Realm fact。

### 16.1 请求面

Authorizing verifier MUST 经认证机密通道发出一次性私有 challenge 请求，并绑定下列输入：

| 输入 | 要求 |
| --- | --- |
| `verifier_id` | 精确判定方 DID。其他 verifier MUST NOT 接受或转发本次披露作为自己的证据。 |
| `audience` | 精确 origin、service audience 或 canonical operation audience。 |
| `challenge` | 不可预测，至少 16 字符。 |
| `request_id` | 唯一 `ak:request:<uuidv7>`，在 `verifier_id` 处单次使用。 |
| 接收窗口 | `expires_at - issued_at` MUST NOT 超过 300 秒。 |
| claim 绑定 | `agent_id` 与 Agent DID accepted-at `requested_scope_digest`。 |

请求与响应 MUST NOT 出现在公开 DID URL、公开 Blob、Realm plaintext Event、durable Event、pairing code 或通知中。

### 16.2 响应面

Controller wallet 的响应 MUST 是 `ak.schema.agent_requested_scope_disclosure.v1` 闭合对象，并携带 controller 当前 proof。Controller proof、disclosure digest 与 accepted-at DID commitment 的重算与验证规则见 [`key-management.md` §4.1](./key-management.md) 与 [`../authz/capabilities.md` §9.1](../authz/capabilities.md)。

Wallet MUST 采用最小披露，MUST NOT 在该响应中附带无关 handle、credential identifier、其他组织身份或全局 subject identifier。

### 16.3 传输

Transport MUST 是下列之一，或安全性等价的 authenticated confidential channel：

1. 使用 verifier DID / 服务密钥的 `http_jwe`。
2. 双方都支持时使用 `didcomm_like` envelope。
3. verifier 是已知 Arkret 设备 / 服务端点时使用 `to_device`。
4. controller 与 verifier 共享加密 DM Realm 时使用 `mls_dm`。

普通明文 HTTP、公开 DID URL、公开 Blob、Realm plaintext Event 与 notification payload 均不得承载该对象。所需机密传输不可用时，controller MUST 拒绝披露，MUST NOT 降级到明文通道。

### 16.4 消费与缓存

Verifier MUST 原子消费 `(verifier_id, request_id, challenge)`。同一 wire presentation 重放、错 verifier / audience、过期或超出 300 秒窗口全部 fail closed。

成功接收后 MAY 把披露保存为加密的 verifier-private evidence，缓存键 MUST 至少包含 `(agent_id, requested_scope_digest, verifier_id, audience)`；accepted-at DID 或 controller lifecycle 变化时 MUST 重新验证或 fail closed。该缓存只属于 verifier 私域，MUST NOT 被另一 verifier 当作其自己的 presentation，也 MUST NOT 写回公开 DID、Realm plaintext、durable Event、pairing code 或通知。实现 MUST NOT 因披露本身"不授予能力"而放宽上述隐私检查，也 MUST NOT 退回 service-local Agent row 作为权威来源。

## 17. v1 互操作要求

- Handle canonical wire form 是 `<localpart>:<domain>`。`<localpart>` MUST 是 [`encoding.md` §2.2](../conformance/encoding.md) `arkret_human_identifier` 的 RFC 8265 `UsernameCaseMapped` enforcement 结果：width mapping、Unicode lowercase 与 NFC 后，排除至少 `: @ / # ? \\`、空白、控制字符、noncharacter 与其它 PRECIS disallowed code point；prepared 结果为 1..128 Unicode code points。`.`、`_`、`+`、`~`、`-` 保持可用。canonical equality 是 prepared localpart code point sequence + lowercase A-label domain 的精确相等，MUST NOT 使用 confusable skeleton 定义相等。
- `<domain>` MUST 使用 [`encoding.md` §2.2.1](../conformance/encoding.md) 的 UTS #46 Nontransitional profile；canonical wire 只接受 lowercase A-label。`domain.中国` 是合法 input / display domain，对应 canonical `domain.xn--fiqs8s`；因此 `@小明:domain.中国` 可准备为 `小明:domain.xn--fiqs8s`。canonical receiver 必须拒绝原始 U-label domain、uppercase A-label、trailing dot、无效 `xn--`、超 DNS 长度或 round-trip 失败。
- 对应 conformance vectors 为 `ak.vector.identity.internationalized_identifier_profiles.v1` 与 `ak.vector.identity.authority_local_skeleton_collision.v1`；前者验证 preparation / canonical receiver 分层，后者验证 skeleton 只属于 authority-local、namespace-local 派生索引。
- registrar MAY 在同一 issuing authority 的 handle namespace 内要求 UTS #39 `Highly Restrictive` 并建立 `(authority, skeleton)` collision index。skeleton 只用于注册冲突 / 风险提示：碰撞可返回 `failed_precondition` `reason="handle_homograph_forbidden"`，但不得写入 wire、proof 或 equality。不同 authority 的相同 skeleton 不冲突。Unicode / PRECIS / UTS #39 数据版本与升级规则由 [`string-profile-registry.json`](../../artifacts/registry/string-profile-registry.json) 钉定。
- `acct:<percent-encoded-localpart>@<A-label-domain>` 是 `handle_aliases[]` 中的 RFC 7565 alias，不含 port；它不是 canonical handle，也不参与 Arkret 内部唯一性比较。
- **Handle 字符串的 wire-level 作用域**（normative）：handle 字符串作为 wire-level **权威字段**（actor reference、authorization subject、audit attribution、解析输入）MUST 只在以下三类位置出现：
  1. **Handle claim lifecycle 对象与 issuer / Auth Server 本地管理请求**：`ak.schema.handle_claim.v1`、issuer / Auth Server 定义的申请、审批、重签、撤销、Directory withdraw、handle reassignment 等显式管理 handle 生命周期的请求、响应、签名 claim 与 audit receipt。这些管理 API 不属于 Arkret v1 core，但一旦在 Arkret wire 上作为 claim evidence 被消费，必须产出可验证的 `ak.schema.handle_claim.v1` 或明确的 revocation / audit evidence。
  3. **客户端入口解析瞬间**：用户键入 handle 字符串到客户端 → 客户端解析为 `subject_account_id` 的临时过程；解析完成后 handle 字符串 MUST NOT 作为权威字段写入持久化事件、Realm history、grant 记录、ACL 表或缓存键以外的存储。

  以下位置是**允许的派生投影 / audit 例外**，handle 字符串在其中不构成权威源：

  - **Roster 内联 handle claim evidence**：`/_arkret/self/account/subscribe` 的 `member_roster.entries[].handle_claims[]` MAY 携带完整签名 `ak.schema.handle_claim.v1`，用于 roster / member picker / mention autocomplete 的本地 claim cache。这里的 handle 字符串属于 claim 本身，不是 roster 自造字段；issuer 重新签发或撤销后，roster digest / claim set 必须随之变化。该 evidence 只能在同一 roster entry 已披露 `subject_account_id` 时返回；未披露 `subject_account_id` 时，`handle_claims[]`、`handle_claim_digests[]` 与 `handle_claims_limited` 都必须省略。
  - **Mention reference 的 audit metadata**：§3.8.1 定义的 `handle_at_time`、`display_name_at_time`、`controller_subject_account_id`、`controller_handle_at_time`、`agent_slug_at_time`、`mention_text_original` MAY 出现在 mention / profile reference 等位置，但仅作为 audit / search / fallback 元数据，不参与权威决策（见 §3.8.3）。

  `@<controller-handle>/<agent_slug>` 不是 v1 客户端输入别名、canonical handle、公开 Directory 搜索 / 列表索引键或 handle claim 形态。客户端 MUST NOT 从该自由文本自动生成 Agent mention；未解析文本只能作为普通文本保存，不得携带 Agent selector metadata 或触发定向通知。已授权 picker 先取得目标完整 `subject_account_id`，再 MAY 用当前可见 `ak.schema.agent_selector_claim.v1` 校验并展示 controller-scoped label；绑定目标必须逐字节匹配，不得按 slug 或裸 principal 重建 AccountId。Agent selector claim 的 issuer proof、visibility、audience、expiry 与 revocation 姿态保留用于此受限披露；它不改变 canonical handle ABNF，也不得把 `agent_slug` 拼进 `ak.schema.handle_claim.v1.handle`。

  `ak.member.identity.update` / `MemberIdentity` v1 payload MUST NOT 携带 `primary_handle`、`handles[]` 或其它 handle 字符串字段。其它任何 wire 位置——reply / quote 的 actor 引用、`ak.member.state{join}.payload` 的 actor 字段、grant subject、audit log entry 的 actor 字段、reaction target、federation peer 事件——MUST 持有 `subject_account_id` 而不是 handle 字符串。verifier / renderer / policy engine MUST NOT 把 mention metadata 当成当前权威 handle、agent slug 或归因依据使用：信任决策永远从 `subject_account_id` 出发，handle 字符串与 agent slug 只是显示 / 搜索 / audit 辅助。

  违反该作用域规则的事件 schema 在 conformance 测试中 MUST 失败：把 handle 字符串当作**权威 actor 引用字段**（而非显式声明的派生投影或 audit metadata）的 schema 视为 v1 不合规。
- DNS TXT record 格式 MUST 绑定 `handle`、`subject_account_id`、issuer、`service_id`、`created_at`、`expires_at` 和 signature / hash commitment；过期或不匹配时不得显示 verified。
- Well-known / Directory response schema MUST 返回 exact `subject_account_id`、issuer 的 `did_core_id`、canonical `handle`、proof、validity 和 optional challenge；公开 handle 由自己 Station 通过已验证的 DID resolution binding 做 `alsoKnownAs` 双向验证，受限 handle 由该 Station 做 issuer claim / audience / policy 验证；客户端消费结果并核对完整 subject 绑定。匿名或未授权调用方查询受限 handle、revoked handle 或不存在 handle 时，response MUST 不可区分。
- Status list profile MUST 支持凭证撤销和暂停。授权依赖的 credential 无法确认状态时 MUST fail closed。
- BBS / SD-JWT VC conformance vectors MUST 覆盖选择性披露、challenge/domain 绑定、错误 issuer、过期凭证、撤销凭证和 pairwise DID unlinkability。
