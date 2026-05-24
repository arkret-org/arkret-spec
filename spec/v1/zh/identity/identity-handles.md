---
title: Handle 与 Claim 证明
---

## 1. 目标

Handle 是人类可读入口，不是权限主键。  
Contrix 使用 DID 作为稳定主体，用可验证 claim / attestation 表达 handle、组织成员、邮箱控制权和其他动态属性。

本文定义：

- handle 格式
- handle 到 DID 的解析
- 双向绑定验证
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
| Handle | 公开或受限；用于 @mention / 邀请 / 成员添加 / 跨上下文可读寻址 | Directory / Principal Server / Organization DID 签发的 handle claim（`acct:` / `contrix://` URI 双向验证），解析为 `subject DID` 与可选 `member_delivery_binding` | 否 |
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
- Handle 只提供寻址和可选默认投递上下文；它不得作为 `actor_id`、grant subject、membership key 或 audit attribution。解析结果必须先归约为 DID 与可验证 claim，加入 Realm 时再物化为 `cx.member.state{join}.delivery_binding`。
- Administrative Identifier 是组织本地概念。协议层只规定它不得作为协议主体、不得作为 grant subject、不得作为 Event actor、不得在跨组织 federation 输出中泄露；其内部分配、回收和绑定规则由组织 governance 决定，超出本规范范围。
- Display name 是可变 metadata，不得被用于 ACL、grant、audit attribution 或 sender verification。

## 3. Handle 格式

Handle 是面向用户的可路由人类地址，让客户端用一个易懂字符串完成 @mention、联系人搜索、邀请或"添加成员到 Realm"，同时保持协议主体仍是 DID、投递路径仍是 Realm-scoped `delivery_binding`。

Handle 是统一概念：协议层只有一种 handle 形态、一套 canonical URI、一套解析与验证规则。所谓"自有域名个人 handle"与"组织内部账号地址"在结构上是同一类——区别只在**谁是 issuer**（domain 拥有者自己 vs 组织 / Principal Server），不在 URI 形态。

### 3.1 显示形态与 canonical URI

Handle 分两层：**显示形态**面向用户，**canonical URI** 面向协议。两层之间是确定性 normalization。

**显示形态（UI 层）**：

| 形态 | 用途 | 示例 |
| --- | --- | --- |
| `@<localpart>:<domain>` | 默认显示与 @mention；带前导 `@` 与邮箱区分 | `@alice:acme.example`、`@alice:alice.dev` |
| `<localpart>@<domain>` | 联系人框 / 企业目录 / 邮箱风格输入 | `alice@acme.example`、`alice@alice.dev` |

客户端 SHOULD 以 `@<localpart>:<domain>` 作为默认渲染形态。`<localpart>@<domain>` MAY 作为输入别名；客户端在 normalize 阶段消除差异。

**Canonical URI（协议层）**：

| URI | 角色 | normative 用途 |
| --- | --- | --- |
| `contrix://<domain>(:<port>)?/users/<localpart>` | **主形态** | DID Document `alsoKnownAs` 比对、claim proof 输入、Directory 缓存键、`handle_uri` 字段 |
| `acct:<localpart>@<domain>(:<port>)?` | 互通别名（RFC 7565） | 跨 Fediverse / WebFinger 边界对接；只能出现在 `handle_aliases[]`，不作为本协议内部 canonical 比对 |

每个 handle 都有唯一的 `contrix://` 形态。`acct:` MAY 在 claim 的 `handle_aliases[]` 中作为附加字段出现，但 **alsoKnownAs 比对、Directory 缓存键、Realm `delivery_binding` 物化** 一律 MUST 使用 `contrix://` 形态。verifier 收到只含 `acct:` 而无对应 `contrix://` 的 claim 时，MUST 把它视为外部互通别名，不得用它作 Contrix 内部权威 binding。

`handle_uri` 的 wire 形态由 [`artifacts/schemas/handle-claim.schema.json`](../../artifacts/schemas/handle-claim.schema.json) 强制：必须匹配 `contrix://<domain>(:<port>)?/users/<localpart>`，且 `<localpart>` 已 canonicalize 为小写。裸 `contrix://<host>`（无 `/users/...` 路径）、`acct:`、`user:domain`、`<host>` 单段字符串等其它形态在 `handle_uri` 中被 schema 拒绝；客户端 MAY 接受这种字符串作为输入捷径，但 normalize 前 MUST 不出现在签名 transcript、`alsoKnownAs`、缓存键或 Directory query 中。`acct:` 互通别名只能进入 `handle_aliases[]`。

### 3.2 解析结果必含字段

Handle 解析结果（无论来自 Directory、Principal Server、Organization claim 还是 holder 自托管 well-known）MUST 至少包含：

- `subject`：被寻址主体的 principal DID。
- `handle_uri`：canonical `contrix://` URI（主形态）。
- `handle_aliases[]`：可选互通别名，例如 `acct:`；不得参与 Contrix 内部权威比对。
- `issuer`：签发 handle claim 的 DID。详见 §3.4。
- `proofs`：至少一条可验证签名，绑定 `handle_uri`、`subject`、`issuer`、`created_at`。
- `created_at` / `expires_at`：claim 时间边界；`expires_at` 缺失等价于 `binding_state=unverified`。

Handle claim 用于 Realm membership（`intent ∈ {invite, member_add}`）时，**额外** MUST 包含：

- `member_delivery_binding`：该 handle 在投递层提供给 membership builder 的完整投递绑定；其中 `member_delivery_binding.recipient_service_did` 是 Principal Server service DID 的唯一来源。
- `audience`：claim 绑定的目标 Realm ID 或邀请方 service DID；verifier MUST 校验 audience 与当前 invocation 上下文一致。
- `issuer_service_did`（条件必填）：claim 由 Organization 或 Directory 签发时给出实际签名的服务 DID。

### 3.3 `member_delivery_binding`

解析结果 MAY 携带 `member_delivery_binding`，其中 `recipient_service_did`、`binding_source`、`service_acceptance_ref`、`policy_ref` 和 `delivery_modes` 可直接用于构造 `cx.member.state{membership="join"}.delivery_binding`。Handle claim schema 不再允许顶层 `recipient_service_did`、`service_acceptance_ref` 或 `policy_ref` 快捷字段；这些 delivery binding 字段必须只从 `member_delivery_binding.*` 读取。

`member_delivery_binding.binding_source` 的合法取值是 `explicit` / `invite` / `join_policy` / `organization_policy` / `realm_policy`。**MUST NOT** 是 `did_document_default`——handle resolution 本身就是 directory-attested 路径，与 DID Document fallback 是两条独立的物化路径，不可在 hint 中混用。

该 hint 是 builder 输入；reducer 仍 MUST 按 [`governance/join-policy.md` §5.1](../governance/join-policy.md) 独立验证 Realm policy、claim issuer、服务背书和条件必填字段。

### 3.4 Issuer 类型与 holder 控制

Handle 的 issuer 决定它的信任锚点；同一 canonical URI 形态可以由不同类型 issuer 签发，verifier 按 issuer 类型选择验证路径：

| Issuer 类型 | 典型场景 | 验证锚点 |
| --- | --- | --- |
| **Holder DID（self-issued）** | 用户自己控制 `<domain>`，自己运营单用户 Principal Server 或 well-known endpoint。例：`@alice:alice.dev` 由 Alice 的 DID 签发。 | (a) `<domain>` 解析 `https://<domain>/.well-known/contrix-did` 或 DNS TXT `_contrix.<domain>` 返回签名 handle claim；(b) holder DID Document `alsoKnownAs` 含对应 `contrix://<domain>/users/<localpart>`；两侧均验签通过。 |
| **Organization DID** | 组织把 handle 签发给员工或受管成员。例：`@alice:acme.example` 由 `did:web:acme.example` 签发给 Alice 个人 DID。 | issuer claim + holder DID Document `alsoKnownAs`（公开 handle）或受限 presentation；audience / scope 限定到目标 Realm / 组织。 |
| **Principal Server service DID** | Principal Server 为它承载的用户签发 handle。例：托管平台 `did:web:principal.acme.example`。 | claim 由 service DID 签发，service DID 由 Organization DID 委派（DID Document service entry 或 governance attestation）；最终归约到 Organization 信任根。 |
| **受信 Directory DID** | 公共 Directory 索引 handle 并发放短期 routable claim。 | Directory claim + 上游 `source_refs`；Directory 是镜像层，不是真相源。 |

**自托管即单用户实例**：用户自己控制域名时，handle 形态仍是 `contrix://alice.dev/users/alice`（或任意 localpart），URI 与组织部署完全一致；只是 issuer 与 holder 是同一个 DID。verifier 解析时按 §5 走 `<domain>` 的 well-known 通道发现 issuer，再走 issuer claim + alsoKnownAs 双向验证——验证路径自然分流，不依赖 URI shape。

### 3.5 公开 vs 受限

Handle 按 holder 披露意图分两类：

- **公开 handle**：holder 主动公开，DID Document MAY 在 `alsoKnownAs` 中列出 canonical `contrix://` URI；issuer 提供的 well-known 或 Directory 响应可对任意 verifier 可见。
- **受限 handle**：例如组织内部账号 `@alice:acme.example` 暗示雇佣关系，默认不进公开 DID Document。它由 issuer 以 `cx.schema.handle_claim.v1` / VC / signed directory response 表达，并按 audience、Realm、organization policy 最小披露。

公开 / 受限之间的差异只在 alsoKnownAs / 公开 directory 的可见性上。两者 URI 形态、双签证据要求、`delivery_binding` 构造规则相同。

### 3.6 与跨上下文 unlinkability 的关系

`member_delivery_binding.recipient_service_did` 必然在解析结果中暴露 handle 与服务的绑定关系；同一 holder 在两个上下文使用同一公开 DID 时，外部观察者通过 `subject` 字段仍能关联到同一人。**Handle 不提供跨上下文 unlinkability**。

需要不可关联的部署 MUST 为每个上下文使用 pairwise / private DID（见 §10、§11、§16），并在每个 pairwise DID 下独立签发 handle claim。pairwise DID 与 handle 是正交机制：handle 解决"易懂寻址 + 可选默认投递"，pairwise DID 解决"跨关系不可关联"。

### 3.7 MemberDeliveryBindingCandidate

`MemberDeliveryBindingCandidate` 是 Handle resolution（`cx.directory.resolve_handle(intent="member_add")`）或受信 issuer 直接签发的 **规范级候选对象**：它把 "用 handle 加成员" 这个端到端链路上需要传递的最小字段集合凝固为一个 schema-defined shape，让 Principal Server、SDK builder、Realm reducer、Auth Server 与 directory 之间停止各自拼字符串。Wire schema 见 [`artifacts/schemas/member-delivery-binding-candidate.schema.json`](../../artifacts/schemas/member-delivery-binding-candidate.schema.json)。

该对象既不是 grant，也不是已物化的 `member_delivery_binding`——它只是**通向**后者的 builder 输入。reducer 在落 `cx.member.state{membership="join"}.delivery_binding` 时仍 MUST 按 [`governance/join-policy.md`](../governance/join-policy.md) 独立验证。

### 3.7.1 字段（normative）

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `subject_id` | DID | MUST | 被寻址主体的 principal DID；最终物化为 `payload.actor_id` / cell subject。 |
| `handle_uri` | canonical URI | MUST | `contrix://<domain>(:<port>)?/users/<localpart>`，`<localpart>` 已 lowercase。`acct:` / 显示形态 / 裸 host 一律拒绝。 |
| `handle_aliases[]` | `acct:` URI 数组 | MAY | 仅互通别名；不参与权威比对、缓存键或 `delivery_binding` 物化。 |
| `member_delivery_binding` | object | MUST | 与 [`handle-claim.schema.json#/properties/member_delivery_binding`](../../artifacts/schemas/handle-claim.schema.json) 同形，`binding_source` ∈ `explicit` / `invite` / `join_policy` / `organization_policy` / `realm_policy`；MUST NOT 为 `did_document_default`。 |
| `issuer_service_did` | DID | MUST | 实际签发该 candidate 的服务 DID（Directory / Principal Server / Organization service DID）。 |
| `audience` | string | MUST | 目标 Realm ID 或邀请方 service DID；verifier MUST 校验 audience 与当前 invocation 上下文一致。 |
| `issued_at` | timestamp | MUST | RFC 3339 `Z` 形式；issuer 签发该 candidate 的时刻。MUST ≤ `expires_at`；与 `expires_at` 一起界定 candidate 的有效窗口并阻止 MITM 把 `issued_at` 改写以扩大重放窗口。 |
| `expires_at` | timestamp | MUST | RFC 3339 `Z` 形式；过期 candidate MUST 被视为不可用。 |
| `source_refs[]` | event id 数组 | MUST | 至少一条 `cx:event:<uuid7>`，指向 issuer / Directory / Organization 真相源 event；客户端 SHOULD 据此回真相源验签。 |
| `proofs[]` | proof 数组 | MUST | 至少一条 proof，绑定 `handle_uri`、`subject_id`、`member_delivery_binding.recipient_service_did`、`audience`、`issuer_service_did`、`issued_at` 与 `expires_at`。`issued_at` MUST 进入 canonical transcript；缺失即视为重放窗口可篡改并拒绝。 |
| `claim_digest` | `sha256:<hex>` | SHOULD | candidate 上游 handle claim 的 canonical JSON digest，用于缓存键与 audit chain。 |
| `intent` | enum | MUST | `member_add` / `invite`，区分 candidate 的 builder 入口；reducer 不依赖该字段，仅用于审计与遥测。 |

`MemberDeliveryBindingCandidate.subject_id` MUST 等于上游 handle claim 的 `subject`。Raw / generic handle claim 使用 `subject`；进入 membership builder candidate 并作为具体 DID 绑定进 proof transcript 时使用 `subject_id`。

`additionalProperties: false`——unknown 字段 MUST 由 verifier 拒绝，避免静默 widening。

### 3.7.2 来源（normative）

candidate 只能来自以下两类签发路径：

1. **Directory 解析**：`cx.directory.resolve_handle(intent="member_add" \| "invite")` 响应 MUST 把 [`discovery-directory.md` §9.0/§9.1](../discovery/discovery-directory.md) 的 handle 解析与通用结果字段重新打包为 candidate；`source_refs` 取 Directory 响应中的 `source_refs`，`issuer_service_did` 取 Directory service DID 或上游 Organization service DID。
2. **受信 issuer 直接签发**：Organization / Principal Server / 受信 service DID 可以离开 Directory 直接对某 `(handle_uri, subject_id, member_delivery_binding.recipient_service_did, audience)` 组合发签名 candidate，例如随 invite token 内嵌、随 organization-issued member roster 下发。

candidate **不得**直接构造自客户端字符串拼接、UI text、未签名 directory 响应或 cache 残留。任何缺少 `proofs[]` 的对象 MUST NOT 被命名为 candidate。

### 3.7.3 物化公式（normative）

`MemberDeliveryBindingCandidate -> cx.member.state.payload.delivery_binding` 的映射必须是确定性的：

```text
payload.actor_id = candidate.subject_id
payload.delivery_binding.recipient_service_did = candidate.member_delivery_binding.recipient_service_did
payload.delivery_binding.resolved_at = candidate.proofs[].created_at 或 candidate.expires_at 之前的 issuer as_of
payload.delivery_binding.service_acceptance_ref = candidate.member_delivery_binding.service_acceptance_ref
payload.delivery_binding.policy_ref = candidate.member_delivery_binding.policy_ref
payload.delivery_binding.delivery_modes = candidate.member_delivery_binding.delivery_modes
payload.delivery_binding.binding_source = join-policy §5.1.2.1 决策树输出
```

`claim_digest`、`source_refs[]` 与 candidate proof digest SHOULD 进入 member Move 的 `refs[]`（`role="attestation"` 或 profile 声明的 role），用于审计和 replay 诊断；它们不得替代 `delivery_binding` 中的规范字段。映射过程中任何缺失字段、过期 candidate、audience 不匹配、issuer 未授权或 Realm `delivery_binding_policy` 不接受该 source，均 MUST fail closed。

### 3.7.4 Validator MUST 规则

verifier 收到 candidate 时 MUST 按下列顺序失败 closed：

1. **schema 合规**：所有 MUST 字段存在；`additionalProperties: false` 不放过未知字段。
2. **`handle_uri` canonical**：必须匹配 `contrix://<domain>(:<port>)?/users/<localpart>` 主形态，且 `<localpart>` 已 lowercase。verifier 不得在签名 transcript 中接受任何非 canonical 形态；`acct:` 出现在 `handle_uri` 即拒绝。
3. **audience match**：`audience` MUST 等于当前 invocation 上下文（目标 `target_realm_id` / `realm_id` 绑定的 audience，或邀请方 service DID）；不一致 MUST 返回与 "无可披露 claim" 不可区分的统一拒绝。
4. **expiry**：`expires_at` 严格大于当前时间；过期 candidate MUST NOT 进入 builder。
5. **proof 验证**：`proofs[]` 中至少一条由 `issuer_service_did`（或受 issuer 委派的 verification method）签名，且 binding transcript 覆盖 `handle_uri`、`subject_id`、`member_delivery_binding.recipient_service_did`、`audience`、`issuer_service_did`、`issued_at`、`expires_at` 与 `claim_digest`（如有）。任何 transcript 漏掉 `issued_at` 或 `issued_at > expires_at` MUST fail closed，避免 MITM 通过重写时间窗口实施重放。
6. **subject / handle 关联**：candidate 内 `subject_id` MUST 等于上游 handle claim 中的 subject（不允许 verifier 在 builder 入口 "替换" subject）。
7. **`member_delivery_binding.binding_source` 合法值**：MUST 是 §3.3 列出的五种之一；`did_document_default` 即拒绝。

通过上述检查的 candidate 是 builder 的合法输入；reducer 仍 MUST 按 Join Policy 再验签 / 再过审。

### 3.7.5 与 display resolve / mention resolve 的差异

`cx.directory.resolve_handle` 三种 intent 返回的字段不同，candidate 只在 `member_add` / `invite` intent 下产生：

| Intent | 返回字段（必含） | 是否产 candidate | 说明 |
| --- | --- | --- | --- |
| `lookup` / display resolve | `subject`、`handle_uri`、`verified` | 否 | 仅用于显示双向验证状态；不暴露 `audience` 或 `member_delivery_binding`。 |
| `mention` resolve | `subject`、`handle_uri`、`display_name?` | 否 | mention autocomplete 需要的最小字段；MUST NOT 在未授权时披露 `member_delivery_binding`。结果存为 message 内 mention snapshot，不进入 membership builder。 |
| `member_add` / `invite` resolve | §3.7.1 全部 MUST 字段 | 是 | 仅当 caller 已经过授权（共同 Space、Directory policy、organization grant 等）才返回。Directory 拒绝时使用与 "未发现资源" 不可区分的统一拒绝。 |

实现 MUST NOT 跨 intent 复用结果：以 `mention` 解析拿到的 payload 不得提升为 candidate；以 `member_add` 解析拿到的 candidate 不得被广播到 mention autocomplete 缓存。

## 4. Handle 绑定

公开 persona DID MAY 使用：

```json
{
  "alsoKnownAs": [
    "contrix://alice.dev/users/alice",
    "contrix://acme.example/users/alice"
  ]
}
```

Pairwise DID、临时 DID、设备 DID、agent 执行 DID 和隐私敏感关系 DID SHOULD NOT 强制绑定公开 handle。受限 handle 只有在 holder 明确选择公开该上下文关联时才 SHOULD 写入 `alsoKnownAs`；否则必须通过受限 claim / presentation 返回。

## 5. Handle 解析

Handle 解析输入是 canonical `handle_uri = contrix://<domain>/users/<localpart>`（或 normalize 自显示形态）。客户端 / verifier 按以下顺序尝试 issuer，第一个成功签发可验证 claim 的就是该 handle 的 issuer：

1. **`<domain>` 的 well-known**：`GET https://<domain>/.well-known/contrix-handle?u=<localpart>` 或等价的 `GET https://<domain>/.well-known/contrix-did`（向后兼容旧客户端按整体 handle 拉取）。响应是 `cx.schema.handle_claim.v1` 形态的签名 claim。
   - 用于 holder 自托管（domain 拥有者 == subject DID）与单实例 Principal Server 部署。
2. **DNS TXT**：`_contrix.<domain>` 或 `_contrix.<localpart>.<domain>`。仅当 DNSSEC validation 成功**且** TXT 内含可验证签名时才能作为 issuer 通道；裸 DNS TXT 只是发现 hint。
3. **Directory / Organization 服务**：`POST /api/v1/directory/resolve-handle`（[`discovery/discovery-directory.md` §9.0](../discovery/discovery-directory.md)）或 Organization-specific endpoint。response 仍是签名 `cx.schema.handle_claim.v1`。
4. **Bridge / 外部 issuer**：当 handle 来自 bridge 或外部体系（例如组织自有 IDP），claim 由该体系签发并通过 §7 VC presentation 出示。

解析结果 MUST 包含 §3.2 列出的字段；audience / scope / expiry 决定使用范围。multiple issuer 同时签发同一 handle 时，verifier 按本地 trust policy 选最严格者；issuer 之间冲突（不同 `subject`）MUST fail closed 并交人工处理。

Handle 解析示例：

```json
{
  "schema": "cx.schema.handle_claim.v1",
  "handle": "@alice:alice.dev",
  "handle_uri": "contrix://alice.dev/users/alice",
  "subject": "did:webvh:QmZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example",
  "issuer": "did:webvh:QmZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example",
  "binding_state": "verified",
  "created_at": "2026-05-19T00:00:00Z",
  "expires_at": "2026-08-19T00:00:00Z",
  "proofs": [{
    "kind": "detached_jws",
    "alg": "EdDSA",
    "verification_method": "did:webvh:QmZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example#key-1",
    "payload_digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "created_at": "2026-05-19T00:00:00Z",
    "jws": "aaa.bbb.ccc"
  }]
}
```

这是 self-issued handle（holder 自己控制 `alice.dev` 域名，`issuer == subject`）。组织签发 handle 的示例：

```json
{
  "schema": "cx.schema.handle_claim.v1",
  "handle": "@alice:acme.example",
  "handle_uri": "contrix://acme.example/users/alice",
  "handle_aliases": ["acct:alice@acme.example"],
  "subject": "did:webvh:QmAlice:users.acme.example",
  "issuer": "did:web:acme.example",
  "issuer_service_did": "did:web:principal.acme.example",
  "claim_type": "organization_handle",
  "visibility": "restricted",
  "binding_state": "verified",
  "audience": "cx:realm:0196419b-0000-7000-8000-000000000000",
  "member_delivery_binding": {
    "recipient_service_did": "did:web:principal.acme.example",
    "recipient_service_type": "principal_server",
    "binding_source": "organization_policy",
    "delivery_modes": ["events", "sync", "to_device", "push", "key_packages"],
    "service_acceptance_ref": "cx:event:0196419b-0000-7000-8000-000000000001",
    "policy_ref": "cx:event:0196419b-0000-7000-8000-000000000002"
  },
  "created_at": "2026-05-19T00:00:00Z",
  "expires_at": "2026-08-19T00:00:00Z",
  "proofs": [{
    "kind": "detached_jws",
    "alg": "EdDSA",
    "verification_method": "did:web:principal.acme.example#key-1",
    "payload_digest": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "created_at": "2026-05-19T00:00:00Z",
    "audience": "cx:realm:0196419b-0000-7000-8000-000000000000",
    "jws": "aaa.bbb.ccc"
  }]
}
```

## 6. 双向验证

客户端解析 handle 得到 `subject` DID 与 issuer 后，验证规则按 handle 的公开 / 受限语义分两条：

**公开 handle（holder 主动公开）**：客户端 MUST 解析 `subject` DID Document，并验证：

```text
did_document.alsoKnownAs contains the canonical handle_uri
```

双向验证失败 MUST NOT 把该 handle 当作公开可信绑定。

**受限 handle（issuer 是 Organization / Principal Server / Directory，holder 未公开）**：handle claim 可能不出现在 holder 公开 DID Document 中；此时客户端 MUST 改为验证：

- issuer claim 签名有效，且 issuer 在当前调用上下文的本地 trust policy 内；
- claim `audience` 与当前调用上下文一致；
- claim `challenge` 未过期、未重复使用；
- claim `scope`（Realm、organization、purpose）覆盖当前用途；
- claim `status` / `binding_state` 仍为 `verified`；
- holder consent / organization policy 允许向当前 requester 披露。

DID Document 缺失 `alsoKnownAs` 单独**不**构成"受限 handle 无效"的判定；判定来自 issuer claim 验签链 + audience / scope 校验。

**DNS TXT 通道**：DNS TXT 只能作为发现通道。若 issuer 通过 DNS TXT 直接声明 handle 绑定，客户端 MUST 满足以下至少一项才可显示为 verified：

- DNSSEC validation 成功，且 TXT 内容绑定 `handle_uri`、`subject`、issuer、`created_at`、`expires_at` 和 signature / hash commitment。
- TXT 记录内的绑定声明由 issuer DID（holder DID 或 Organization DID 或受信 issuer）签名，客户端能通过 DID resolver / VC 验证该签名。
- HTTPS well-known 或 Directory / VC presentation 提供等价的签名绑定证据。

未启用 DNSSEC 且没有可验证签名的 DNS 结果只能作为 unverified discovery hint，MUST NOT 作为 grant subject、Organization membership、official Realm 或 verified handle 的依据。

### 6.1 缓存与失效

Handle 解析结果是带时间边界的绑定，不是永久身份事实。

#### 6.1.1 缓存规则

- verified handle cache MUST 绑定 `handle_uri`（canonical `contrix://` 形态）、`subject`、issuer、DID Document version / digest、alsoKnownAs proof、issuer proof、verified_at、expires_at 和 resolver policy。claim 同时携带 `handle_uri` 与 `handle_aliases[]` 时，缓存键 MUST 取 `handle_uri`；`acct:` alias 只作为附加索引，但仍指向同一 cache entry。
- alias lookup 命中缓存时，verifier MUST 跳转到 canonical `handle_uri` 的 freshness re-check 路径：重新检查 TTL、issuer revocation、DID Document digest / version、alsoKnownAs proof 与 resolver policy。实现不得把 `handle_aliases[]` 中的 `acct:` 或其它互通别名当作独立 cache key 直接返回 verified claim，也不得为 alias 单独延长 freshness window。
- handle cache 若含 `member_delivery_binding`，还 MUST 绑定 `member_delivery_binding.recipient_service_did`、claim digest、audience / scope、`service_acceptance_ref` / `policy_ref`（如有）；缓存结果不得跨 Realm 或跨组织上下文复用，除非 claim 明确授权。
- DNS / HTTPS 解析结果的 TTL MUST 不超过底层 DNS TTL、HTTPS response cache headers、签名绑定 `expires_at`、DID Document cache TTL 和本地 resolver policy 上限中的最小值。未提供 TTL 时，verified cache SHOULD 不超过 24 小时；高风险授权或组织背书 SHOULD 使用更短 TTL 或实时 status check。
- 当 DID Document 移除对应 `alsoKnownAs`、issuer claim 被 revoke / expired、well-known 绑定变更、DNSSEC validation 失败、handle 被解析到不同 DID、或 resolver policy 更新时，缓存 MUST 失效或降级为 unverified。

#### 6.1.2 撤销与失效信号

v1 不引入专门的 handle 撤销 event。撤销通过下列三条独立路径完成，客户端 / Directory / Principal Server 任一通道发现失效即 MUST 同步本地缓存：

1. **TTL 自然过期**：缓存到达 `expires_at` 后 MUST 重新拉取；不得在 TTL 之外使用。
2. **Directory withdrawal**：handle issuer 通过 [`cx.directory.withdraw`](../discovery/discovery-directory.md) 撤回该 handle 的 directory entry；订阅该 handle 的客户端在下一次 directory refresh 或 withdraw notification 收到后 MUST 立即失效缓存。
3. **DID Document 变化**：holder 移除 `alsoKnownAs` 中的 canonical URI，或 issuer claim 被 revoke / `binding_state=revoked`、`binding_state=expired`；下一次 verify pass 失败时 MUST 失效。

handle issuer SHOULD 把 cache 失效信号与 TTL 一起使用：发布短 TTL（≤1h）的高变更 handle、配合 Directory withdraw 主动通知。**v1 不要求**服务端推送 handle 失效事件；客户端 MUST 按 TTL + 上述三路径处理失效，**不得**依赖未注册的 `cx.handle.*` wire kind。

#### 6.1.3 Handle 重分配与历史归因

handle 字符串可以在 issuer 治理下被重分配到不同 DID（典型场景：员工离职后 localpart 被分配给新员工）。重分配 normative 规则：

- **DID 与签名责任不可改写**：Handle 转让或重分配 MUST NOT 改变历史 Event 的 actor DID、签名责任或 audit attribution。授权、grant subject、membership、MLS credential 与 audit attribution MUST 使用 DID / verified claim，而不是缓存中的 handle 字符串。
- **历史 mention 显示**：渲染历史 mention / message text 时，UI MUST 优先显示 event 内 `subject` DID 的当时身份信息（profile snapshot、display_snapshot 字符串）。若当前 `handle_uri` 解析到的 DID **不等于** 事件中记录的 `subject`，UI MUST 显式标注"handle reassigned"或等价文字，避免读者把当前持有者误认为历史 mention 的对象。
- **新分配生效**：新持有者拿到 handle 后 MUST 通过 issuer 重新发布 handle claim（新 `subject`、新 `created_at`、独立的 `service_acceptance_ref`）；旧 claim 的所有缓存按 §6.1.2 失效。
- **跨投递的 cascade**：handle 重分配不自动迁移既有 Realm `delivery_binding`——旧 binding 仍按 `cx.member.state{join}` 内固化的 `subject` DID 投递。新持有者要加入同一 Realm 需要走完整 join 流程并签发新的 `delivery_binding`。

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
4. Google 或受信 issuer 给 `did:key:z6Mkgpairwise...` 签发 `ContrixOrgMembershipCredential`
5. Facebook 或受信 issuer 给 `did:key:z6Mkfpairwise...` 签发独立 credential
6. 面向 Google verifier 时，wallet 只生成 Google 相关 presentation
7. Google verifier MUST NOT 要求披露 Facebook credential、Facebook DID 或跨域 subject identifier

## 11. Credential 示例

如果 verifier 只需要知道“该主体拥有 Google 组织内有效账号”，presentation SHOULD 披露抽象 claim：

```json
{
  "type": ["verifiable_credential", "contrix_org_membership_credential"],
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
  "type": "contrix_presentation_request",
  "audience": "did:web:google.example",
  "domain": "google.example",
  "challenge": "cx_chal_01J...",
  "accepted_issuers": [
    "did:web:google.example",
    "did:web:trusted-hr.example"
  ],
  "required_claims": [
    {
      "type": "contrix_org_membership_credential",
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

Contrix SHOULD 支持：

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
condition = has valid contrix_org_membership_credential where org = did:web:google.example
```

错误：

```text
grant subject = alice@google.com
```

如果 holder 后续为另一个组织出示不同 pairwise DID，除非 holder 显式提供 linking proof，否则 verifier MUST 将其视为独立隐私上下文。

## 16. Progressive Disclosure（渐进披露）

本节定义 Contrix 隐私信息渐进披露的端到端实现方案。渐进披露用于让 holder 只向特定 verifier / organization 披露完成某项验证所需的最小身份信息，例如：

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
  "kind": "cx.identity.presentation_request",
  "request_id": "cx:request:d8764019-0000-7000-8000-000000000000",
  "verifier_did": "did:web:login.google.example",
  "represented_org": "did:web:google.example",
  "domain": "google.example",
  "challenge": "cx_chal_01J...",
  "purpose": "space_join",
  "accepted_issuers": ["did:web:google.example"],
  "required_claims": [
    {
      "claim_type": "contrix_org_membership_credential",
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
  "kind": "cx.identity.disclosure_policy",
  "policy_id": "cx:policy:a1cb0019-0000-7000-8000-000000000000",
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
  "kind": "cx.identity.presentation_response",
  "request_id": "cx:request:d8764019-0000-7000-8000-000000000000",
  "holder_subject": "did:key:z6Mkgpairwise...",
  "proof_profile": "vc_di_bbs_2023",
  "presentation": {},
  "disclosed_fields": [
    "credentialSubject.org",
    "credentialSubject.member",
    "credentialSubject.handle_verified"
  ],
  "presentation_hash": "sha256:...",
  "created_at": "2026-04-26T00:00:00Z"
}
```

Response MUST NOT 包含未披露字段、base proof、无关的 credential identifier、其他组织的 handle 或全局 subject identifier。

#### 16.2.4 Disclosure Receipt

```json
{
  "kind": "cx.identity.disclosure_receipt",
  "receipt_id": "cx:receipt:a1cb0019-0000-7000-8000-000000000000",
  "request_id": "cx:request:d8764019-0000-7000-8000-000000000000",
  "holder_did": "did:key:z6Mkgpairwise...",
  "verifier_did": "did:web:login.google.example",
  "represented_org": "did:web:google.example",
  "presentation_hash": "sha256:...",
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
  "service": "contrix_verifier",
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
4. verifier 是已知 Contrix 设备 / 服务端点时使用 `to_device`。
5. holder 与 verifier 共享加密 DM Realm 时使用 `mls_dm`。

若 policy 要求嵌套 / 路由级元数据隐私，而 verifier 不支持 TSP 或等价能力，wallet MUST 拒绝或请求用户显式覆盖。

### 16.7 端到端流程

1. Verifier 发送已签名的 `cx.identity.presentation_request`。
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

- Handle canonical URI 是 `contrix://<domain>(:<port>)?/users/<localpart>`，其中 `<localpart>` 在 wire 上必须是 lowercase canonical form；`acct:<localpart>@<domain>(:<port>)?` 为 `handle_aliases[]` 中的互通别名。handle ABNF 必须限制为可规范化、大小写明确、禁止控制字符和混淆分隔符的字符串；`<domain>` 使用 IDNA 处理后再验证，显示层必须防同形混淆。
- DNS TXT record 格式 MUST 绑定 `handle_uri`、`subject`、issuer、`service_did`、`created_at`、`expires_at` 和 signature / hash commitment；过期或不匹配时不得显示 verified。
- Well-known / Directory response schema MUST 返回 `subject` DID、canonical `handle_uri`、issuer、proof、validity、optional `member_delivery_binding` 和 optional challenge；公开 handle 客户端必须做 DID `alsoKnownAs` 双向验证，受限 handle 必须做 issuer claim / audience / policy 验证。
- Credential schema、presentation request、disclosure policy 和 disclosure receipt 必须绑定 holder DID、verifier DID、audience、challenge、domain、disclosed fields、withheld fields 和 proof profile。
- Status list profile MUST 支持凭证撤销和暂停。授权依赖的 credential 无法确认状态时 MUST fail closed。
- BBS / SD-JWT VC conformance vectors MUST 覆盖选择性披露、challenge/domain 绑定、错误 issuer、过期凭证、撤销凭证和 pairwise DID unlinkability。
