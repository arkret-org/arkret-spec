# DID Identity

## 1. 目标

Contrix 使用 DID 作为稳定身份根。Handle、邮箱、组织用户名和第三方账号都只是可验证属性，不是协议主键。

本文定义：

- DID method 选择策略
- 默认 DID method
- resolver policy 与 method adapter
- DID Document normalized view
- 组织账号绑定的 DID proof
- `did:uuid` 不纳入 v1 协议 DID 方法集合

Contrix v1 不定义、注册或推荐任何自有 DID method。实现和用户 MUST 使用已有 DID method，例如 `did:plc`、`did:web`、`did:webvh`、`did:key`、`did:pkh`，或本地 trust policy 明确允许的其他公开 DID method。

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

如果用户尚无显式 DID，Auth / Account Server MAY 在注册、邀请认领或首次写入前为其创建受支持的托管 DID。公共 Contrix 部署的默认托管 DID method 是 `did:plc`；组织或服务主体 SHOULD 使用 `did:web`，在需要可验证历史时 SHOULD 使用 `did:webvh`。托管 DID 的 controller、recovery policy、trust domain、method-specific history 和 service-account 绑定 MUST 可审计；后续协议对象仍然以 DID 作为 `actor_id`、grant `subject`、service DID 或 `verification_method` 的根。

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

Contrix 公共部署的默认 principal DID method 是：

```text
did:plc:<identifier>
```

选择 `did:plc` 的原因：

- 它是已有 DID method，不是 Contrix 自定义方法。
- 它适合没有自有域名的普通用户。
- 它支持可恢复、可轮换的控制状态和 operation history。
- 它已有 AT Protocol / Bluesky 生态的实际部署经验。
- 它能在 DID Document 中承载服务发现入口，并可通过 resolver policy 约束可接受的 PLC directory。

默认值只表示“当系统需要为普通用户创建新 DID，且用户没有明确选择其他 method 时使用 `did:plc`”。协议仍然允许其他现有 DID method，只要实现能按该 method 的规范完成解析、控制权验证、历史验证和服务委托验证。

### 3.1 Method Selection

| 场景 | 默认 / 推荐 DID method | 说明 |
| --- | --- | --- |
| 普通个人 principal DID | `did:plc` | 默认选择；适合无域名用户，支持控制权轮换和恢复。 |
| 个人自带域名身份 | `did:web` 或 `did:webvh` | 用户愿意把身份绑定到域名时可选；`did:webvh` 提供可验证历史。 |
| 组织 DID | `did:webvh` SHOULD，`did:web` MAY | 组织通常有域名；高保证组织 SHOULD 使用有历史、watcher 或 witness 的方法。 |
| Service DID | `did:web` SHOULD，`did:webvh` MAY | 服务发现天然需要域名和 HTTPS endpoint；高风险服务可使用 `did:webvh`。 |
| 临时主体、设备、测试、一次性邀请 | `did:key` | 本地可解析、无网络依赖；不适合默认长期身份。 |
| 钱包 / 链上账号绑定 | `did:pkh` | 只在钱包控制权就是业务身份根时使用；不得默认要求所有用户有链上账号。 |
| 高安全或隔离部署 | policy 指定的现有 DID method | MAY 使用私有 `did:webvh`、内网 `did:web`、KERI 或其他公开 method；MUST 明确 resolver trust roots。 |

### 3.2 支持要求

Contrix v1 conformance 要求如下：

- Core resolver / verifier MUST 支持 DID Core 解析 / 验证抽象、`did:web` 和 `did:key`。`did:key` 用于测试、bootstrap、设备、一次性邀请、pairwise DID 和 registry outage 时的本地可验证身份材料；它不改变长期 principal 的 method policy。
- Public network identity profile MUST 支持 `did:plc`，并声明可接受的 PLC directory、mirror、audit source 和 outage 策略。
- Organization / high-security profile SHOULD 支持 `did:webvh` 或等价 history-bearing DID method。
- Wallet interop profile MAY 支持 `did:pkh`。
- 实现 MAY 支持其他现有 DID method，例如 KERI 系列 method，但 MUST 保留 raw method evidence，并声明 trust profile。
- 实现 MUST NOT 将任何外部 DID Document 重写为 Contrix 私有 DID method。

因此，`did:plc` 是公共 Contrix 部署的默认托管 principal DID method，不是所有 Core 实现的强制依赖。只实现私有组织、离线测试、嵌入式或 enclave profile 的实现 MAY 不支持 `did:plc`，但必须在 service describe / conformance profile 中明确声明其 allowed methods。

## 4. Identity Resolution Infrastructure

Contrix 把身份解析抽象为 `Identity Resolution Infrastructure`，而不是要求所有 DID method 都部署同一种 Identity Registry。不同 DID method 的解析状态来源不同：

| DID method | 是否需要公共 Identity Registry | 需要的解析 / 验证能力 |
| --- | --- | --- |
| `did:plc` | 需要可接受的 PLC directory / mirror / audit source。 | 验证 PLC operation chain、genesis / previous op hash、rotation keys、recovery state、DID Document、service bindings 和 directory transparency evidence。 |
| `did:web` | 不需要公共 registry。 | HTTPS / DNS / 域名治理、TLS / PKI、method-specific DID Document 获取与校验。 |
| `did:webvh` | 不需要传统公共 registry。 | `did.jsonl` history、SCID、entry hash chain、controller proof、watcher / witness evidence、HTTPS / DNS 校验。 |
| `did:key` | 不需要。 | 本地 method resolver 从 DID 字符串展开 DID Document；适合临时主体、设备、测试、一次性邀请或 bootstrap key。 |
| `did:pkh` | 不需要 Contrix registry。 | CAIP-10 / chain-specific account validation、wallet proof、chain namespace policy；通常不支持 DID document update / deactivation。 |
| 其他现有 DID method | 取决于 method。 | 保留 raw DID Document 与 method-specific proof，并映射到 Contrix normalized principal view。 |

使用 `did:key` 或 `did:pkh` 不表示“不需要身份解析”。它只表示通常不需要公共可写 registry。客户端、Auth Server、Principal Server 和 Policy / Authz 仍然必须具备对应 DID method 的 resolver / verifier，才能确认 DID 控制状态、服务委托和 method 限制。

### 4.1 Resolver Policy

Resolver policy MUST 至少定义：

- allowed methods：当前部署接受哪些 DID method。
- default principal method：公共网络 profile 默认 SHOULD 为 `did:plc`；私有组织、enclave 或测试 profile MAY 使用 `did:web`、`did:webvh`、`did:key` 或 policy 指定的其他 method，但必须在 profile 中声明。
- trust roots：PLC directory / mirror、DNS / HTTPS trust、webvh watcher / witness、KERI watcher、chain namespace allowlist 等。
- method capability：该 method 是否支持 rotation、recovery、deactivation、service endpoint、historical resolution、witness evidence。
- privacy handling：是否允许公开解析、是否需要 holder-approved proof、pairwise DID 是否禁止 directory 查询。
- cache rules：缓存 MUST 绑定 DID、method、resolver trust domain、document hash / history head、evidence set 和 expiry。
- failure rules：无法按本地 trust policy 解析、method evidence 不足、history 断链、service delegation 过期或 DID deactivated 时，resolver MUST fail closed。

示例：

```json
{
  "default_principal_method": "did:plc",
  "allowed_methods": ["did:plc", "did:web", "did:webvh", "did:key", "did:pkh"],
  "method_policy": {
    "did:plc": {
      "role": ["principal"],
      "directory": ["https://plc.directory"],
      "require_operation_history": true
    },
    "did:web": {
      "role": ["organization", "service", "principal"],
      "require_https": true
    },
    "did:key": {
      "role": ["device", "test", "bootstrap"],
      "long_lived_principal": "deny"
    },
    "did:pkh": {
      "role": ["wallet_binding"],
      "chain_allowlist": ["eip155:1", "eip155:137"]
    }
  }
}
```

### 4.2 DID Method Continuity

DID method 或 registry 不可用时，节点不得把“暂时无法解析”解释为“身份仍然有效”。Resolver MUST fail closed，但实现还必须提供可恢复的用户路径：

- 缓存解析结果只能在 resolver policy 声明的 TTL、document hash、history head 和 trust domain 内使用；超过 TTL 或 evidence 断链后，不得接受新的高风险写入。
- `did:plc` directory 不可用时，resolver MAY 使用 policy 允许的 mirror / audit source，但必须验证同一 operation chain、history head 和 directory transparency evidence；不得用 handle、DNS 或服务声明代替 DID method history。
- 用户迁移到新 DID method 时，历史 Event 的 `actor_id`、grant `subject` 和 proof `verification_method` MUST NOT 被重写。迁移必须表现为新的 signed continuity proof、profile/account binding、membership update 或 capability re-grant。
- 若原 DID 仍可解析，continuity proof SHOULD 由原 DID 当前有效控制密钥签署，并绑定 `old_did`、`new_did`、purpose、audience、issued_at、expires_at 和目标 Space / service 范围。
- 若原 method 永久不可用且无法验证原控制密钥，只能走 Space / organization policy 定义的恢复流程，例如 threshold governance、recovery service attestation 或管理员重新邀请；客户端必须向用户明确这是恢复/重绑定，而不是无缝 DID 所有权延续。
- Principal Server、Directory 或 Handle 服务 MAY 帮助发现新 DID，但不得单独证明 DID continuity。

## 5. Resolver、Auth Server 与组织授权

DID 解析、登录认证和组织数据授权是三个不同职责：

| 层次 | 负责什么 | 不负责什么 |
| --- | --- | --- |
| Identity Resolution Infrastructure | 把 DID 解析为 DID Document、key state、method history、service delegation、witness evidence 或 method-specific proof。 | 不决定用户是否能登录某个组织，也不授予 Space / Event 数据访问权。 |
| Auth / Account Server | 处理 passkey、OIDC、SSO、设备配对、账户恢复和 session grant，并把服务账户登录绑定到某个 DID / device。 | 不改变 DID 控制权；不替代 DID key proof；不决定所有组织授权。 |
| Organization / Policy / Authz | 判断某个 DID、device、credential 或 capability 是否可以访问组织数据、Space、Event、Applet 或管理动作。 | 不负责维护公共 DID 控制历史。 |

一个组织 MAY 自建 Auth / Account Server，同时接受公共 `did:plc` 用户 DID。典型流程是：

1. 用户提交 `did:plc:...`、handle、邀请链接或组织账号。
2. 组织 Auth Server 按本地 trust policy 选择 resolver。普通部署可以默认解析 `did:plc`；组织或服务 DID 通常解析 `did:web` / `did:webvh`；高安全部署可以只允许 allowlist 中的 resolver 和 trust roots。
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
  "did": "did:plc:ewvi7nxzyoun6zhxrhs64oiz",
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

- 默认 principal DID 创建 MUST 使用 `did:plc`，除非部署 policy 显式选择了另一个已有 DID method。
- Method adapter conformance tests MUST 覆盖 `did:plc`、`did:web`、`did:key`，并 SHOULD 覆盖 `did:webvh` 或其他 history-bearing method。
- `did:uuid` MUST NOT 出现在规范示例、新 fixture、新一致性向量、服务 DID、actor DID、capability subject、federation transaction 或新写入的 Event 中。
- DID proof JSON Schema MUST 与 `data-structures.md` 的 Proof 和 `encoding.md` 的 canonical JSON 规则一致。
- Normalized principal view MUST 保留 raw document hash、method-specific proof、current control keys、service bindings、contrix bindings 和 evidence；不得丢弃外部 DID 的原始语义。
- 无法验证 method history 的 adapter 只能声明 limited trust profile，并且 MUST NOT 被默认用于高风险组织、service delegation 或长期 principal 创建。
