---
title: DID Identity
---

## 1. 目标

Contrix 使用 DID 作为稳定身份根。Handle、邮箱、组织用户名和第三方账号都只是可验证属性，不是协议主键。

本文定义：

- DID method 选择策略
- 默认 DID method
- resolver policy 与 method adapter
- DID Document normalized view
- 组织账号绑定的 DID proof
- `did:uuid` 不纳入 v1 协议 DID 方法集合

Contrix v1 不定义、注册或推荐任何自有 DID method。实现和用户 MUST 使用已有 DID method，例如 `did:webvh`、`did:web`、`did:key`、`did:pkh`、`did:plc`，或本地 trust policy 明确允许的其他公开 DID method。

## 2. 核心原则

### 2.1 稳定主体引用 MUST 使用 DID

协议中的主体引用 MUST 使用 DID，而不是 handle。

包括：

- object creator
- object updater
- grant issuer
- grant subject
- agent actor
- service node actor

#### 2.1.1 用户可见标识 MAY 不是 DID

实现 MAY 允许用户使用 `@alice:example.org`、`alice@example.org`、组织用户名、OIDC subject、邀请链接或其他人类可读标识完成发现、登录、邀请和账号恢复。

这些标识是 user-facing identifier、service account id、handle、3PID 或 bridge alias；它们不是协议主键。实现接受任何持久 Event、capability grant、federation transaction、MLS membership 或 service delegation 前，MUST 将当前会话绑定到 principal DID 与 device，并按本地 trust policy 验证该绑定。

如果用户尚无显式 DID，Auth / Account Server MAY 在注册、邀请认领或首次写入前为其创建受支持的托管 DID。Contrix v1 core 部署的默认 principal DID method 是 `did:webvh`（详见 §3）：Auth / Account Server 在自有域名（例如 `users.<org>.example`）下托管 `did.jsonl` 历史，并 SHOULD 接入至少一个 trusted witness。`did:web`（无历史链）仅作为 service DID 默认 method、`personal_node` deployment profile 的可选 principal method、以及 `did:webvh` hosting domain 暂时不可达时的策略允许 fallback；详见 §3.1。`did:web` 之所以不能作为 v1 core 默认 principal method，是因为它没有可审计 DID Document 历史——DNS 劫持或 TLS 证书失窃即可静默改写主体控制权而不留痕迹。托管 DID 的 controller、recovery policy、trust domain、method-specific history 和 service-account 绑定 MUST 可审计；后续协议对象仍然以 DID 作为 `actor_id`、grant `subject`、service DID 或 `verification_method` 的根。

### 2.2 DID 持久，密钥 SHOULD 可轮换

普通密钥轮换 SHOULD NOT 改变 DID。

长期 principal DID SHOULD 选择支持 key rotation、recovery、deactivation 或可验证历史的 DID method。`did:key` 和 `did:pkh` 属于生成式 DID method，通常不支持 DID document 更新、停用或内建恢复；它们 MAY 用于临时主体、设备、邀请、bootstrap、钱包绑定或测试，但除非 Space / organization policy 明确允许，MUST NOT 作为默认长期用户 DID。

### 2.3 DID Document 不是身份画像

DID Document SHOULD 只承载：

- 可验证控制材料
- 最小服务发现入口
- method-specific 更新、恢复或历史所需状态

DID Document MUST NOT 被用作跨组织身份画像。邮箱、跨组织 handle、第三方账号和隐私敏感属性应通过 claim / presentation 按需证明。

### 2.4 `did:uuid` 不属于 v1 规范方法

新实现、测试向量、fixture、规范示例和新写入的协议对象 MUST NOT 使用 `did:uuid`。`did:uuid` 不属于 Contrix v1 的主身份形式；解析与写入路径对该方法直接拒绝。

## 3. 默认 DID 方法

Contrix v1 core 部署的 **default principal DID method 是 `did:webvh`**：

```text
did:webvh:<scid>:<host-and-path>
```

`did:web` 仅作为 **service DID 默认 method** 与 **`personal_node` deployment profile 的可选 principal method**；不得作为 `small_team` / `organization` / `high_security_organization` / `sovereign_deployment` profile 的默认 principal method。

选择 `did:webvh` 作为 v1 core principal 默认的原因：

- 它在 `did:web` 之上叠加了 `did.jsonl` 历史链 + SCID + 可选 witness 证据，提供了 **可审计的 DID 控制历史**。
- DNS 劫持、TLS 证书失窃或域名转移在 `did:web` 上是静默的——攻击者可以替换 DID Document 而不留任何可被 verifier 检测的证据。`did:webvh` 通过 entry hash chain + controller proof + witness 让任何身份控制权变更都进入可验证账本，与 Contrix 自身 signed-event chain 范式同构。
- 它与 Contrix 的 service DID（service endpoint 仍可使用 `did:web`）兼容，部署门槛仅比 `did:web` 多一份 `did.jsonl` 文件。

为什么 `did:web` 不能是 v1 core principal 默认：`did:web` 没有可验证 DID 文档历史，攻击者控制 hosting domain 后可以把 DID Document 替换成自己的 `verificationMethod` 而 verifier 无从检测。把它作为长期 principal 默认会让协议安全模型整体退化到 DNS+TLS 强度。

默认值只表示"当系统需要为新用户创建 principal DID、且用户未明确选择其他 method 时使用 `did:webvh`"。协议仍然允许其他现有 DID method，只要实现能按该 method 的规范完成解析、控制权验证、（可选的）历史验证和服务委托验证。

### 3.1 Method Selection

| 场景 | 默认 / 推荐 DID method | 说明 |
| --- | --- | --- |
| 普通个人 principal DID（`small_team` / `organization` / 更高 profile） | `did:webvh` | v1 core 默认 principal method。无域名用户由 Auth / Account Server 在组织子域代为托管 `did.jsonl`。 |
| `personal_node` profile principal DID（单人节点、低 stakes） | `did:webvh` SHOULD，`did:web` MAY | 单人自托管可降级为 `did:web`，但 deployment profile MUST 显式声明 `principal_method=did:web`。 |
| 组织 DID | `did:webvh` | v1 core MUST-support；治理 / 合规部署强制可验证 history chain。 |
| Service DID | `did:web` | 服务发现天然依赖域名和 HTTPS endpoint；可选升级到 `did:webvh`。 |
| 临时主体、设备、测试、一次性邀请、bootstrap | `did:key` | 本地可解析、无网络依赖；不支持轮换 / 恢复，MUST NOT 作为默认长期身份。 |
| 钱包 / 链上账号绑定（interop extension） | `did:pkh` | 只在钱包控制权就是业务身份根时使用；由 chain-binding interop extension profile 承载，不属于 v1 core 互操作必需。 |
| AT Protocol 互通（interop extension） | `did:plc` adapter | 仅作为 AT Protocol bridge / interop adapter；由独立 interop extension profile 承载，不属于 v1 core 互操作必需。 |
| 高安全或隔离部署 | `did:webvh`（默认） + policy 指定的额外 method | sovereign / enclave / 内网 PKI / KERI 等可作为辅助；MUST 明确 resolver trust roots 与 witness 集合。 |

### 3.2 标识域名与服务域名的解耦

DID 托管域名、Principal Server 服务域名和 handle 域名是**三个独立的标识层**，可以分别属于不同的域名甚至不同的运营方。实现 MUST NOT 假设这三者必须一致，也不得用其中一个直接推导另一个。

| 标识层 | 由谁决定 | 解析/验证通道 | 示例 |
| --- | --- | --- | --- |
| DID 历史托管域名 | DID method 与 SCID（一旦签发即写入历史链） | `did:webvh` `did.jsonl` + entry hash chain + witness | `did:webvh:<scid>:users.acme.example` |
| Principal Server 服务域名 | DID Document 中 `service` entry 的 `serviceEndpoint`，受组织/用户 service delegation 控制 | DID Document service binding + service DID 解析 + describe 响应 + `destination` 绑定（见 [federation.md §6](../sync/federation.md)） | `https://principal-7.cluster.acme.example:8443/api/v1` |
| Handle 域名 | Holder 选择并通过双向验证发布 | DNS TXT / HTTPS well-known + DID Document `alsoKnownAs` 双向验证（见 [identity-handles.md §5–§6](./identity-handles.md)） | `alice.example.com`、`@alice:example.org` |

要点：

- DID 字符串中出现的域名（例如 `did:webvh:...:users.acme.example` 中的 `users.acme.example`）只表示 `did.jsonl` 历史的托管位置，**不**承诺该域名运行 Principal Server，也**不**是用户公开 handle。
- 用户/组织搬迁 Principal Server、变更端口、增加 mirror、切换到第三方 host 时，正确路径是更新 DID Document 中的 service entry 并重新签发 service delegation；这条路径会进入可验证历史，不依赖 DNS+TLS 的现时强度。
- Handle 域名（含品牌域名）与 DID 托管域名可以完全无关。例如品牌持有者可以使用 `alice.example.com` 作为公开 handle，而 DID 仍然由 `users.someprovider.example` 托管，只要 `alsoKnownAs` 与 well-known 双向验证一致。
- [federation.md §6.3](../sync/federation.md) 的 `https://<domain>/.well-known/contrix/server` 仅作为 bootstrap 候选发现 hint，**不是**身份解析必经路径，也不能授权联邦请求；权威服务发现源仍然是 DID Document 的 service entry。
- 实现 MUST NOT 引入"DID 字符串 → 实际服务地址"的额外带外重定向（例如类 Matrix `.well-known/matrix/server` 的间接），因为这会把信任根退化到 DNS+TLS 即时强度，与选择 `did:webvh` 而不是 `did:web` 作为 v1 core 默认 principal method 的初衷冲突（见 §3.4）。

### 3.3 支持要求

Contrix v1 core conformance 要求如下：

- Core resolver / verifier MUST 支持 DID Core 解析 / 验证抽象、`did:webvh`、`did:web` 和 `did:key`。
  - `did:webvh` 是 v1 core 默认 principal method（`personal_node` profile 例外，见 §3.1）。
  - `did:web` 是 v1 core 默认 service method；同时是 `personal_node` profile 的可选 principal method 与 `did:webvh` hosting 暂不可达时的 policy 允许 fallback。
  - `did:key` 用于测试、bootstrap、设备、一次性邀请、pairwise DID 和 registry outage 时的本地可验证身份材料。
- AT Protocol interop（`did:plc` adapter）、wallet binding（`did:pkh`）、KERI 等 method 是 **interop extension profile**；core 实现 MAY 不支持，profile 化承载的好处是把仍在演进的子规范隔离在 core 互操作之外。
- 实现 MAY 支持其他现有 DID method，但 MUST 保留 raw method evidence，并声明 trust profile。
- 实现 MUST NOT 将任何外部 DID Document 重写为 Contrix 私有 DID method。

### 3.4 `did:webvh` 作为 v1 core 默认

`did:webvh` 在 `did:web` 之上提供：

- `did.jsonl` 历史（SCID + entry hash chain + controller proof）
- 可选 witness / watcher 证据
- 与 Contrix signed-event chain 范式同构的"链式可验证"语义

所有声称 v1 core principal_server / full_client / e2ee_client conformance 的实现 MUST 支持 `did:webvh` witness 验证、SCID 派生、entry hash chain 验证和 controller proof 验证。

`did:webvh` hosting domain 暂时不可达时 resolver MAY 在 policy 允许的范围内退化为 `did:web` 等价行为（仅当前状态，不再可信历史读取），但：

- 该 fallback **仅**适用于**低风险只读**操作。本规范定义的"低风险只读"集合是**封闭的**：
  - ✅ 已缓存对象的本地展示（已存在的 Flow / Message / Place / Morph 渲染）
  - ✅ 已缓存对象的本地搜索 / 本地索引查询
  - ✅ 已收到 snapshot / Anchor 的 state_root 重算（用于本地一致性自检）
  - ❌ 接收新到达的 Event Envelope / Move / Anchor 并写入本地 store（即使是只读 store）
  - ❌ 联邦 transaction 接收（`/api/v1/federation/push-operations`）
  - ❌ Push notification wakeup 后的 client sync 拉取
  - ❌ 任何 capability cache 重建或 freshness check
  - ❌ 任何 `cx.session.grant` 验证或登录态续期
  - ❌ Snapshot witness 接收
- 任何高风险动作——新写入、grant、revoke、recovery、device authorization、key rotation、MLS commit、service delegation、joining new Space、accepting invite——MUST fail closed 直到 hosting 或 mirror 恢复，或走部署 policy 明确允许的替代路径。
- Resolver MUST 在 outage diagnostics 中暴露 `webvh_unreachable` 标记 + `cached_evidence_age_ms`，让客户端 UI 显式提示用户。客户端 UI MUST 在 fallback 期间向用户展示 banner-level 警示（"身份历史链暂不可达，仅显示本地缓存内容"），不得静默继续。
- Fallback 总时长 MUST ≤ 24 小时（与 §4.2.1 `degraded_no_witness` 状态硬上限对齐）；超时后即使是低风险只读也 MUST fail closed，强制用户等待恢复或切换 resolver。

完整 method-specific 操作（创建、轮换、恢复、deactivation、history validation）的规范见
W3C `did:webvh` specification 与 §7.2；core v1 文档不再展开。

### 3.5 Interop Adapter Extension Profiles

下列 method 在 v1 core 中**不要求**实现，作为可选 interop extension profile 提供：

- **`did:plc` adapter** — AT Protocol 互通；需要 PLC directory / mirror / audit source。
- **`did:pkh`** — 钱包 / 链上账号绑定；需要 chain-specific verification。
- **`did:keri` 与其他 KERI 系列** — KERI 部署的 raw evidence 保留与 normalized view 映射。
- **TSP transport** — 见 [`identity/tsp-integration.md`](./tsp-integration.md)（extension profile；v1 core 不要求实现）。

声明这些 adapter 的部署 MUST 在 `service/describe.identity_methods` 中显式列出，并在 conformance profile 中说明 trust roots、outage 策略与 mirror 来源。

## 4. Identity Resolution Infrastructure

Contrix 把身份解析抽象为 `Identity Resolution Infrastructure`，而不是要求所有 DID method 都部署同一种 Identity Registry。不同 DID method 的解析状态来源不同：

| DID method | 是否需要公共 Identity Registry | 需要的解析 / 验证能力 |
| --- | --- | --- |
| `did:webvh` | 不需要公共 registry（high-trust profile 默认 method）。 | `did.jsonl` history、SCID、entry hash chain、controller proof、watcher / witness evidence、HTTPS / DNS 校验。 |
| `did:web` | 不需要公共 registry。 | HTTPS / DNS / 域名治理、TLS / PKI、method-specific DID Document 获取与校验。无历史链——只能反映"当前 DID Document 状态"。 |
| `did:key` | 不需要。 | 本地 method resolver 从 DID 字符串展开 DID Document；适合临时主体、设备、测试、一次性邀请或 bootstrap key。 |
| `did:pkh` | 不需要 Contrix registry。 | CAIP-10 / chain-specific account validation、wallet proof、chain namespace policy；通常不支持 DID document update / deactivation。 |
| `did:plc` | 需要可接受的 PLC directory / mirror / audit source（AT Protocol interop adapter）。 | 验证 PLC operation chain、genesis / previous op hash、rotation keys、recovery state、DID Document、service bindings 和 directory transparency evidence。仅在声明 AT 互通 profile 的部署中需要。 |
| 其他现有 DID method（KERI 等） | 取决于 method。 | 保留 raw DID Document 与 method-specific proof，并映射到 Contrix normalized principal view。 |

使用 `did:key` 或 `did:pkh` 不表示“不需要身份解析”。它只表示通常不需要公共可写 registry。客户端、Auth Server、Principal Server 和 Policy / Authz 仍然必须具备对应 DID method 的 resolver / verifier，才能确认 DID 控制状态、服务委托和 method 限制。

### 4.1 Resolver Policy

Resolver policy MUST 至少定义：

- allowed methods：当前部署接受哪些 DID method。
- default principal method：v1 core 默认 SHOULD 为 `did:webvh`；`personal_node` profile MAY 降级为 `did:web` 但必须在 deployment profile 中显式声明 `principal_method=did:web`。私有组织、enclave、本地测试或 AT 互通部署 MAY 选用其他 method，但必须在 profile 中明确声明。
- trust roots：webvh witness / watcher、DNS / HTTPS trust、PLC directory / mirror（仅 AT 互通）、KERI watcher、chain namespace allowlist 等。
- method capability：该 method 是否支持 rotation、recovery、deactivation、service endpoint、historical resolution、witness evidence。
- privacy handling：是否允许公开解析、是否需要 holder-approved proof、pairwise DID 是否禁止 directory 查询。
- cache rules：缓存 MUST 绑定 DID、method、resolver trust domain、document hash / history head、evidence set 和 expiry。
- failure rules：无法按本地 trust policy 解析、method evidence 不足、history 断链、service delegation 过期或 DID deactivated 时，resolver MUST fail closed。

示例：

```json
{
  "default_principal_method": "did:webvh",
  "allowed_methods": ["did:webvh", "did:web", "did:key"],
  "method_policy": {
    "did:webvh": {
      "role": ["principal", "organization"],
      "require_history_chain": true,
      "require_witness": "required",
      "witness_threshold": 1,
      "trusted_witnesses": [
        "did:web:witness-a.example",
        "did:web:witness-b.example"
      ],
      "fallback_to_did_web": "low_risk_read_only"
    },
    "did:web": {
      "role": ["service", "personal_node_principal_optional"],
      "require_https": true,
      "allow_principal_for_profiles": ["personal_node"]
    },
    "did:key": {
      "role": ["device", "test", "bootstrap"],
      "long_lived_principal": "deny"
    }
  }
}
```

声明 AT Protocol interop profile 的部署 MAY 在同一 policy 中加入 `did:plc` 适配器：

```json
"did:plc": {
  "role": ["interop_principal"],
  "directory": ["https://plc.directory"],
  "require_operation_history": true,
  "long_lived_principal": "interop_only"
}
```

`role: "interop_principal"` 表示该 DID 只在 AT 互通边界内被当作 principal；Contrix 自身的默认创建路径不签发 `did:plc`。

### 4.2 DID Method Continuity

DID method 或 registry 不可用时，节点不得把“暂时无法解析”解释为“身份仍然有效”。Resolver MUST fail closed，但实现还必须提供可恢复的用户路径：

- 缓存解析结果只能在 resolver policy 声明的 TTL、document hash、history head 和 trust domain 内使用；超过 TTL 或 evidence 断链后，不得接受新的高风险写入。
- `did:webvh` 的 hosting domain 不可用、`did.jsonl` 拉取失败或 witness evidence 断链时，resolver MAY 在 policy 允许的范围内使用本地缓存或镜像，但必须验证 SCID、entry hash chain head 与 controller proof；不得用 handle、DNS A/AAAA 记录、TLS 证书或 Auth Server 声明代替 DID method history。
- 用户迁移到新 DID（同 method 或换 method）时，历史 Event 的 `actor_id`、grant `subject` 和 proof `verification_method` MUST NOT 被重写。迁移必须表现为新的 signed continuity proof、profile/account binding、membership update 或 capability re-grant。
- 若原 DID 仍可解析，continuity proof SHOULD 由原 DID 当前有效控制密钥签署，并绑定 `old_did`、`new_did`、purpose、audience、issued_at、expires_at 和目标 Space / service 范围。
- 若原 method 永久不可用且无法验证原控制密钥，只能走 Space / organization policy 定义的恢复流程，例如 threshold governance、recovery service attestation 或管理员重新邀请；客户端必须向用户明确这是恢复/重绑定，而不是无缝 DID 所有权延续。
- Principal Server、Directory 或 Handle 服务 MAY 帮助发现新 DID，但不得单独证明 DID continuity。

#### 4.2.1 `did:webvh` 健康检查

实现 MUST 对 `did:webvh` resolver policy 定义主动健康检查：

- 监控 hosting domain、`did.jsonl` 可达性、最近 entry head、SCID 一致性、controller proof 验证结果，以及 policy 声明的 trusted witness 的最新签名时间。
- 健康状态 MUST 区分 `healthy`、`degraded_no_witness`、`stale_history`、`write_unavailable` 和 `untrusted` 或等价状态。
- `degraded_no_witness`（hosting 仍可达但 witness evidence 缺失或过期）只能用于历史解析和低风险读取；新 DID 创建、key rotation、recovery、deactivation 和高风险 service delegation MUST 等待 witness evidence 恢复，或走部署 policy 明确允许的替代路径。该状态默认最长持续 24 小时；部署 policy MAY 缩短，MUST NOT 延长到超过 7 天。超过窗口后，resolver MUST 进入 `stale_history` 或 `write_unavailable`，并对新的高风险写入 fail closed。
- `stale_history` 或 `untrusted` 时，resolver MUST fail closed；不得用缓存 handle、DNS、Principal Server 声明或用户登录态替代 DID 历史链。
- 客户端和服务端 SHOULD 暴露 outage diagnostics，包括使用的 hosting / mirror、entry head、witness 列表、evidence age 和下一次 retry 时间。

#### 4.2.2 跨 method 迁移路径

实现 MUST 支持从其它 method（例如 `did:web` 升级、`did:plc` 互通历史、`did:key` 临时身份转长期身份）到 `did:webvh` 的计划迁移路径，而不只是在事故后恢复——这是 conformance 必备能力（`personal_node` profile 升级到 `small_team` 必经此路径，见 [`key-management.md` §5.0.2](./key-management.md)）：

1. 用户在原 DID 仍可解析时创建新 `did:webvh`，并发布 SCID、首个 `did.jsonl` entry 和（可选）witness evidence。
2. 原 DID 当前有效控制密钥签署 continuity proof；新 DID 控制密钥反向签署 acceptance proof。
3. Handle / service account / profile binding 指向新 DID，但历史 Event 仍保留旧 DID。
4. Space membership、capability grant、device/session control 和 MLS identity link 通过普通 Event 或 policy 流程重新绑定到新 DID。
5. 客户端在 UI 中显示"已计划迁移"状态和原 DID 的验证历史，不把它当作无痕重命名。

## 5. Resolver、Auth Server 与组织授权

DID 解析、登录认证和组织数据授权是三个不同职责：

| 层次 | 负责什么 | 不负责什么 |
| --- | --- | --- |
| Identity Resolution Infrastructure | 把 DID 解析为 DID Document、key state、method history、service delegation、witness evidence 或 method-specific proof。 | 不决定用户是否能登录某个组织，也不授予 Space / Event 数据访问权。 |
| Auth / Account Server | 处理 passkey、OIDC、SSO、设备配对、账户恢复和 session grant，并把服务账户登录绑定到某个 DID / device。 | 不改变 DID 控制权；不替代 DID key proof；不决定所有组织授权。 |
| Organization / Policy / Authz | 判断某个 DID、device、credential 或 capability 是否可以访问组织数据、Space、Event、Applet 或管理动作。 | 不负责维护公共 DID 控制历史。 |

一个组织 MAY 自建 Auth / Account Server，同时接受多种 DID method 的用户 DID。典型流程是：

1. 用户提交 `did:webvh:...`（v1 core 默认）、`did:web:...`（service DID 或 `personal_node` profile principal）、handle、邀请链接或组织账号；声明 AT 互通的部署也接受 `did:plc:...`。
2. 组织 Auth Server 按本地 trust policy 选择 resolver。v1 core 默认 principal 解析路径是 `did:webvh`（验证 `did.jsonl` 链 + SCID + entry hash chain + witness）；service DID 通常是 `did:web`；`personal_node` profile MAY 降级 principal 解析路径为 `did:web`；高安全部署可以只允许 allowlist 中的 resolver 和 trust roots。
3. Auth Server 或客户端解析 DID Document，校验 method history、witness / directory evidence、service delegation 和可接受的 trust domain。
4. 用户用 DID 控制密钥、设备密钥、passkey / OIDC 绑定证明或组织要求的 VC presentation 完成登录绑定。
5. Auth Server 只签发 session grant / device binding；组织 Policy / Authz 再基于 DID、credential、membership、invite、capability 和 Space policy 决定可访问的数据范围。

### 5.1 组织账号绑定的 DID Proof

当用户用一个已有 DID 注册、认领或绑定组织 service account 时，Auth / Account Server MUST 验证调用方当前控制该 DID。仅提交 DID 字符串、handle、邮箱验证码、OIDC subject 或组织用户名不足以建立 DID 绑定。

推荐的 DID proof 是 challenge-response：

1. 用户提交待绑定的 DID。
2. Auth Server 解析 DID Document，并按本地 trust policy 校验 method、history、witness / directory evidence、deactivation 状态和可接受的 trust domain。
3. Auth Server 生成一次性 challenge。challenge MUST 绑定用途、目标服务、origin / audience、过期时间和随机 nonce。
4. 客户端使用该 DID 当前有效的 `authentication` verification method、已授权 device key，或被有效 session / device grant 覆盖的临时 key 签名 challenge。
5. Auth Server 验证签名、verification method 当前有效性、challenge 未过期且未使用过。
6. 验证通过后，Auth Server MAY 创建或更新 `service_account -> principal_id` 绑定，并签发短期 `cx.session.grant` 或登记 device binding。

签名 payload SHOULD 使用结构化 canonical JSON，至少包含：

```json
{
  "kind": "cx.did.proof",
  "purpose": "account_binding",
  "did": "did:webvh:QmZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example",
  "audience": "did:web:auth.acme.example",
  "origin": "https://auth.acme.example",
  "challenge": "base64url-random",
  "issued_at": "2026-04-26T00:00:00Z",
  "expires_at": "2026-04-26T00:05:00Z"
}
```

Auth Server 在以下情况下 MUST NOT 接受 DID proof：

- DID 在组织 trust policy 下无法解析
- 验证方法当前未被授权用于身份认证或所声明的 device/session 路径
- 签名未覆盖完整的 challenge payload
- challenge 已过期、已使用、audience 不匹配或 origin 不匹配
- DID 已停用或 method history 无效

service account 绑定是组织本地状态。它不会把 DID 所有权转移给组织，也不会允许组织轮换、恢复或停用用户 DID，除非 DID 自身控制状态或 recovery policy 授权该动作。

## 6. DID Document 与 Normalized View

Raw W3C DID Core / VC 文档在线路上 MUST 保留标准字段名。实现 MUST NOT 把 DID Document 的 `alsoKnownAs`、`verificationMethod`、`assertionMethod`、`publicKeyMultibase`、`publicKeyJwk`、`serviceEndpoint`，或 VC 的 `credentialSubject`、`validFrom`、`validUntil`、`credentialStatus` 改写为 snake_case 后再作为 raw DID / VC 文档输出。

Contrix 自有 envelope、API 参数、索引、policy input 和 reducer input 仍然使用 snake_case。实现 MAY 构造内部 normalized principal view，但该 view 是派生投影，不是 DID Document 本身；若要重新发布或转发 DID / VC，MUST 使用原始标准字段名。

Normalized principal view SHOULD 包含：

- `did`
- `did_method`
- `supported_profiles`
- `raw_document_hash`
- `raw_history_ref`
- `current_control_keys`
- `authentication_methods`
- `assertion_methods`
- `service_bindings`
- `contrix_bindings`
- `method_evidence`
- `limitations`

Contrix MUST NOT：

- 把外部 DID 文档重写成伪私有 DID
- 假装外部 DID 支持它没有的字段
- 丢弃 method-specific 历史或证明细节
- 因 DID Document 可解析就默认接受其所有 service endpoint

公开 persona DID MAY 包含 `alsoKnownAs`。Pairwise / private DID SHOULD NOT 包含公开 handle、邮箱、组织用户名或可关联历史别名。

## 7. Method-Specific Operations

DID 更新 MUST 使用对应 DID method 的 operation 格式、授权规则和提交通道。Contrix 不定义通用的自有 DID operation patch 格式。

Identity Resolution Surface MAY 提供统一 API 来提交或查询 method-specific operation，但请求体 MUST 明确 `did_method`、raw operation、proofs 和 resolver policy context。

示例：

```json
{
  "did": "did:plc:ewvi7nxzyoun6zhxrhs64oiz",
  "did_method": "did:plc",
  "operation": {
    "type": "plc_operation",
    "raw": "<method-specific canonical object>"
  },
  "proofs": [
    {
      "verification_method": "did:plc:ewvi7nxzyoun6zhxrhs64oiz#atproto",
      "jws": "..."
    }
  ],
  "policy_context": {
    "audience": "did:web:registry.example",
    "purpose": "did_update"
  }
}
```

Resolver / registry / adapter MUST 拒绝：

- 签名无效
- method-specific operation 不符合对应 DID method 规范
- history head / previous operation 不匹配
- operation 与本地 resolver policy、trust roots 或 allowed role 冲突
- method 不支持该操作却被当作支持处理

## 8. Organization Principal Ownership

Organization principal 的“所有权”由 DID 控制状态和组织治理策略共同定义，而不是由某台服务器、某个域名注册人或某个 Space 自动决定。

组织 DID Document SHOULD 声明最小治理材料：

```json
{
  "id": "did:webvh:QmQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn:acme.example",
  "verificationMethod": [
    {
      "id": "did:webvh:QmQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn:acme.example#governance-key-1",
      "type": "Multikey",
      "controller": "did:webvh:QmQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn:acme.example",
      "publicKeyMultibase": "z..."
    }
  ],
  "authentication": [
    "did:webvh:QmQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn:acme.example#governance-key-1"
  ],
  "assertionMethod": [
    "did:webvh:QmQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn:acme.example#governance-key-1"
  ],
  "service": [
    {
      "id": "did:webvh:QmQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn:acme.example#governance",
      "type": "ContrixGovernanceService",
      "serviceEndpoint": "https://acme.example/.well-known/contrix/governance"
    }
  ],
  "contrix_governance": {
    "profile": "cx.org.governance.v1",
    "threshold": {
      "required": 2,
      "eligible_methods": [
        "did:webvh:QmQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn:acme.example#governance-key-1",
        "did:webvh:QmQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn:acme.example#governance-key-2",
        "did:webvh:QmQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn:acme.example#governance-key-3"
      ]
    },
    "service_delegations": [
      {
        "service_did": "did:web:server.acme.example",
        "purposes": ["principal_server", "space_endorsement"],
        "validFrom": "2026-04-26T00:00:00Z",
        "validUntil": null
      }
    ]
  }
}
```

规则：

- Organization principal MUST 由其 DID Document / method history 中的密钥或委托服务控制。
- 高风险治理动作 SHOULD 使用阈值签名、多签 approval 或 governance service attestation。
- 组织可委派 service DID 代表其运行 Principal Server、Policy Server、Applet、Directory 或受托 search / projection 扩展，但该委派 MUST 明确 purpose、scope 和有效期。
- 组织 DID 的密钥轮换、恢复和停用 MUST 进入 DID method 的可验证历史。
- 组织所有权转移 MUST 由原控制状态授权，并生成可验证 transfer / recovery 记录；实现 MUST NOT 因域名、商标或 UI 文案变化自动认定组织所有权转移。

客户端判断“谁控制该组织”时，应验证：

1. Organization DID 解析结果有效。
2. 当前控制密钥可从 method history 推导。
3. governance policy 中的阈值或 approval 要求已满足。
4. 若动作由 service DID 执行，该 service DID 被 organization DID 委派且 purpose 覆盖该动作。
5. 相关 key / delegation 在事件时间未过期、未撤销。

### 8.1 Threshold Governance 操作层级

`threshold` 可以在不同层实现，但 DID Document / governance policy MUST 明确声明 profile：

- **method-native threshold signature**：DID method 或底层 key type 原生支持阈值签名（例如 FROST 生成单一 verification method 签名）。验证方按 method history 验证一个签名，但必须能从 governance evidence 确认阈值参数和参与 key set。
- **application-level multi-proof**：DID method 不支持阈值签名时，治理事件携带多个独立 proof；Contrix / governance service 按 `threshold.required`、eligible methods、purpose、expiry 和 history head 检查 quorum。
- **governance service attestation**：组织 DID 委派的 service DID 聚合审批并签发 attestation。该 service 本身必须由 organization DID 委派，attestation 必须保留参与 signer、policy version、decision id 和 audit digest。

实现不得仅因为 DID method 支持 witness（例如 `did:webvh` witness）就把 witness 当作 threshold signature。Witness 证明历史可见性或日志一致性；quorum 证明治理授权。

### 8.2 组织治理流程示例

**Key rotation**：

1. 发起者构造 rotation proposal，绑定 organization DID、当前 history head、待撤销 key、待加入 key、目的、有效期和 rollback plan。
2. 收集满足 threshold 的 method-native signature、multi-proof 或 governance service attestation。
3. 提交 DID method operation；`did:webvh` 场景写入新的 DID log entry，并由 watcher / witness 见证。
4. 发布或更新 Contrix governance / service delegation state，使 Principal Server、Policy Server 和 Space endorsement 使用新 key set。
5. 客户端验证旧 history head、quorum proof、新 key 生效时间和被撤销 key 不再授权后，才接受高风险组织写入。

若 3 个 governance key 中 1 个泄露，且 policy 为 2-of-3，两个未泄露 key 可以签发 rotation，移除泄露 key 并加入新 key；泄露 key 单独不能完成 rotation。若剩余可用 key 少于 threshold，必须走 policy 中预先声明的 emergency recovery，而不是临时降低 threshold。

**新 service delegation**：

1. proposal 绑定 service DID、service endpoint、purpose、scope、plaintext visibility、validFrom / validUntil 和 revocation path。
2. quorum proof 覆盖完整 proposal。
3. DID Document service entry 或 Contrix `cx.space.organization` / policy state 发布 delegation。
4. 接收方在接受该 service 的事件、明文可见性或 federation transaction 前，验证 organization DID、quorum proof、service DID 控制权和 Space policy。

**Emergency recovery**：

1. recovery policy 必须在事故前写入 DID method history 或 governance profile，包含 threshold、recovery service / guardian、cooldown、通知和审计要求。
2. 恢复事件必须绑定 incident id、旧 history head、新 key set、失效 key set、原因和生效延迟。
3. 客户端在 cooldown 内 SHOULD 显示高风险状态；高风险 Space MAY 冻结组织 admin 动作，直到 recovery witness / approval 完成。

## 9. 验证规则

节点接受写入前至少应校验：

1. actor 是合法 DID。
2. DID method 在本地 resolver policy 中被允许。
3. DID Document 可按 method-specific 规则解析。
4. method history / proof / evidence 满足该 method 的控制权规则。
5. 当前 `authentication` / `assertionMethod` 在事件时间有效。
6. service endpoint 或 service delegation 与当前 Space policy、destination binding 和 plaintext-visible service policy 一致。
7. DID 未被 deactivated、quarantined 或本地 policy 禁止。
8. `did:key`、`did:pkh` 等受限 method 未被用于 policy 禁止的长期 principal、组织或高风险 service 角色。
9. Pairwise/private DID 不被强制公开 `alsoKnownAs`。
10. `did:uuid` 不得用于新写入；`did:uuid` 对象不得进入当前协议可读写身份主键通道。

## 10. 一致性要求

Contrix v1 对 DID 实现要求如下：

- v1 core 默认 principal DID 创建 MUST 使用 `did:webvh`（见 §3 / §3.4），除非部署 policy 显式选择了另一个已有 DID method。`personal_node` deployment profile MAY 把 principal method 降级为 `did:web`，但 MUST 在 deployment profile 中显式声明 `principal_method=did:web`；其他 deployment profile（`small_team` / `organization` / `high_security_organization` / `sovereign_deployment`）MUST 使用 `did:webvh` 或更强 method 作为长期 principal。`did:web` 仅作为 service DID 默认 method 与 `did:webvh` hosting 暂不可达时的低风险只读 fallback。
- Method adapter conformance tests MUST 覆盖 `did:webvh`、`did:web`、`did:key`；声明 AT Protocol interop profile 的实现 MUST 额外覆盖 `did:plc` adapter；声明 wallet interop profile 的实现 MUST 额外覆盖 `did:pkh`。
- `did:uuid` MUST NOT 出现在规范示例、新 fixture、新一致性向量、服务 DID、actor DID、capability subject、federation transaction 或新写入的 Event 中。
- DID proof JSON Schema MUST 与 `data-structures.md` 的 Proof 和 `encoding.md` 的 canonical JSON 规则一致。
- Normalized principal view MUST 保留 raw document hash、method-specific proof、current control keys、service bindings、contrix bindings 和 evidence；不得丢弃外部 DID 的原始语义。
- 无法验证 method history 的 adapter 只能声明 limited trust profile，并且 MUST NOT 被默认用于高风险组织、service delegation 或长期 principal 创建。
