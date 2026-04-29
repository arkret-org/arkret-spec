# DID Identity

## 1. 目标

Contrix 使用 DID 作为稳定身份根。Handle、邮箱、组织用户名和第三方账号都只是可验证属性，不是协议主键。

本文定义：

- `did:uuid` 原生 DID 方法
- UUID v8 位布局
- inception key 与 key log
- DID Document canonical 字段
- registry / witness / replica 解析模型
- 外部 DID method adapter

## 2. 核心原则

### 2.1 稳定主体引用 MUST 使用 DID

协议中的主体引用 MUST 使用 DID，而不是 handle。

包括：

- object creator
- object updater
- grant issuer
- grant subject
- run actor
- memory author
- service node actor

#### 2.1.1 用户可见标识 MAY 不是 DID

实现 MAY 允许用户使用 `@alice:example.org`、`alice@example.org`、组织用户名、OIDC subject、邀请链接或其他人类可读标识完成发现、登录、邀请和账号恢复。

这些标识是 user-facing identifier、service account id、handle、3PID 或 bridge alias；它们不是协议主键。实现接受任何持久 Event、repo commit、capability grant、federation transaction、MLS membership 或 service delegation 前，MUST 将当前会话绑定到 principal DID 与 device，并按本地 trust policy 验证该绑定。

如果用户尚无显式 DID，Auth / Account Server MAY 在注册、邀请认领或首次写入前为其创建受支持的托管 DID，例如 `did:uuid`、`did:web` 或组织私有 DID。托管 DID 的 controller、recovery policy、trust domain 和 service-account 绑定 MUST 可审计；后续协议对象仍然以 DID 作为 `actor_id`、`repo_id`、`author`、grant `subject`、service DID 或 `verification_method` 的根。

### 2.2 DID 持久，密钥可轮换

普通密钥轮换 MUST NOT 改变 DID。

Contrix 的身份验证模型是：

- DID 中的哈希片段锚定 `inception_key`
- 当前控制密钥必须能通过 `key_log` 从 `inception_key` 推导
- 当前控制密钥不要求与 DID 中的哈希片段直接相等

### 2.3 DID Document 不是身份画像

DID Document SHOULD 只承载：

- 可验证控制材料
- 最小服务发现入口
- key log / recovery 所需状态

DID Document MUST NOT 被用作跨组织身份画像。邮箱、跨组织 handle、第三方账号和隐私敏感属性应通过 claim / presentation 按需证明。

## 3. 默认 DID 方法

Contrix 默认原生 DID 方法是：

```text
did:uuid:<uuid-v8>
```

初版要求：

- MUST 支持 `did:uuid`
- SHOULD 支持 `did:web`
- MAY 支持 `did:plc`
- MAY 支持 `did:keri`
- MAY 支持 `did:key` 作为测试或临时主体

### 3.1 DID Method and Trust Domain

`did:uuid` 不是公共网络专用 DID，也不隐含任何默认公共 registry。

`did:uuid` 只定义：

- DID 字符串格式
- UUID v8 位布局
- inception key hash fragment
- key log 验证规则

`did:uuid` 的解析位置由 resolver policy、registry / witness 配置和服务发现策略决定。实现 MUST NOT 把 `did:uuid` 自动解析到某个全局公共 registry，除非本地 trust policy 明确允许。

同一个 `did:uuid` 方法可以用于：

- public trust domain：公共 registry / witness / directory。
- organization trust domain：组织控制的 registry / witness。
- sovereign trust domain：高安全组织或联盟控制的 isolated registry / witness。
- pairwise / private trust domain：只在特定关系或钱包私有状态中解析。

高安全部署 MAY 使用 `did:uuid` 作为内部 principal DID，但客户端 MUST pin resolver trust domain，并拒绝未授权 registry / witness 返回的 DID 状态。

高安全部署也 MAY 使用 `did:web` 或外部 DID method 表示组织主体，尤其当组织希望利用域名、证书、内网 PKI 或现有治理系统做服务发现时。协议不得要求 sovereign deployment 放弃 `did:uuid`；也不得要求 sovereign deployment 接受公共 `did:uuid` registry。

### 3.2 Identity Resolution Infrastructure

Contrix 把身份解析抽象为 `Identity Resolution Infrastructure`，而不是要求所有 DID method 都部署同一种 Identity Registry。不同 DID method 的解析状态来源不同：

| DID method | 是否需要公共 Identity Registry | 需要的解析 / 验证能力 |
| --- | --- | --- |
| `did:key` | 不需要。 | 本地 method resolver 从 DID 字符串展开 DID Document；适合临时主体、设备、测试、一次性邀请或 bootstrap key，不适合作为长期可恢复身份。 |
| `did:web` | 不需要公共 registry。 | HTTPS / DNS / 域名治理、TLS / PKI、method-specific DID Document 获取与校验。 |
| `did:uuid` | 取决于 trust policy。 | 公共或私有 registry / witness / resolver、key log、receipt、service delegation。 |
| `did:keri` | 不需要传统中心化 registry。 | KERI event log、key state resolution、witness receipt、watcher、OOBI discovery。 |
| `did:plc` 或外部 DID method | 取决于 method。 | 保留 raw DID Document 与 method-specific proof，并映射到 Contrix normalized principal view。 |

因此，使用 `did:key` 或 `did:keri` 不表示“不需要身份解析”。它只表示通常不需要公共可写 registry。客户端、Auth Server、Principal Server 和 Policy / Authz 仍然必须具备对应 DID method 的 resolver / verifier，才能确认 DID 控制状态、服务委托和密钥轮换历史。

### 3.3 Resolver、Auth Server 与组织授权

DID 解析、登录认证和组织数据授权是三个不同职责：

| 层次 | 负责什么 | 不负责什么 |
| --- | --- | --- |
| Identity Resolution Infrastructure | 把 DID 解析为 DID Document、key state、key log / KERI log、service delegation、witness evidence 或 method-specific proof。 | 不决定用户是否能登录某个组织，也不授予 Space / repo 数据访问权。 |
| Auth / Account Server | 处理 passkey、OIDC、SSO、设备配对、账户恢复和 session grant，并把服务账户登录绑定到某个 DID / device。 | 不改变 DID 控制权；不替代 DID key proof；不决定所有组织授权。 |
| Organization / Policy / Authz | 判断某个 DID、device、credential 或 capability 是否可以访问组织数据、Space、repo、Applet 或管理动作。 | 不负责维护公共 DID 控制历史。 |

一个组织 MAY 自建 Auth / Account Server，同时继续使用公共 `did:uuid` 解析网络。典型流程是：

1. 用户提交 `did:uuid:...`、handle、邀请链接或组织账号。
2. 组织 Auth Server 按本地 trust policy 选择 resolver。普通部署可以默认选择公共 `did:uuid` resolver；高安全部署可以选择组织私有 resolver；`did:web` 按 DID method 从域名解析。
3. Auth Server 或客户端解析 DID Document，校验 key log、witness evidence、service delegation 和可接受的 trust domain。
4. 用户用 DID 控制密钥、设备密钥、passkey / OIDC 绑定证明或组织要求的 VC presentation 完成登录绑定。
5. Auth Server 只签发 session grant / device binding；组织 Policy / Authz 再基于 DID、credential、membership、invite、capability 和 Space policy 决定可访问的数据范围。

#### 3.3.1 组织账号绑定的 DID Proof

当用户用一个已有 DID 注册、认领或绑定组织 service account 时，Auth / Account Server MUST 验证调用方当前控制该 DID。仅提交 DID 字符串、handle、邮箱验证码、OIDC subject 或组织用户名不足以建立 DID 绑定。

推荐的 DID proof 是 challenge-response：

1. 用户提交待绑定的 DID。
2. Auth Server 解析 DID Document，并按本地 trust policy 校验 method、key log、witness evidence、deactivation 状态和可接受的 trust domain。
3. Auth Server 生成一次性 challenge。challenge MUST 绑定用途、目标服务、origin / audience、过期时间和随机 nonce。
4. 客户端使用该 DID 当前有效的 `authentication` verification method、已授权 device key，或被有效 session / device grant 覆盖的临时 key 签名 challenge。
5. Auth Server 验证签名、verification method 当前有效性、challenge 未过期且未使用过。
6. 验证通过后，Auth Server MAY 创建或更新 `service_account -> principal_id` 绑定，并签发短期 `cx.session.grant` 或登记 device binding。

签名 payload SHOULD 使用结构化 canonical JSON，至少包含：

```json
{
  "type": "cx.did.proof",
  "purpose": "account_binding",
  "did": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992",
  "audience": "did:web:auth.acme.example",
  "origin": "https://auth.acme.example",
  "challenge": "base64url-random",
  "issued_at": "2026-04-26T00:00:00Z",
  "expires_at": "2026-04-26T00:05:00Z"
}
```

Auth Server MUST NOT accept a DID proof if:

- the DID cannot be resolved under the organization's trust policy
- the verification method is not currently authorized for authentication or the asserted device/session path
- the signature does not cover the exact challenge payload
- the challenge is expired, reused, audience-mismatched, or origin-mismatched
- the DID is deactivated or the key log / method history is invalid

service account 绑定是组织本地状态。它不会把 DID 所有权转移给组织，也不会允许组织轮换、恢复或停用用户 DID，除非 DID 自身控制状态或 recovery policy 授权该动作。

因此：

- 公共 `did:uuid` resolver 是身份控制历史和服务发现的一种公共基础设施；`did:key` 可由本地 resolver 解析，`did:keri` 可由 KERI witness / watcher / resolver 验证。
- 企业 Auth Server 是该企业的登录入口和 session 管理者。
- 企业使用公共 resolver 不表示公共 resolver 可以登录企业系统或访问企业数据。
- 企业允许某个 `did:uuid` 登录，本质是企业 policy 接受该 DID、该 DID 的控制证明以及相关 credential / invite。
- 普通用户可以为了 DID 稳定性和持久性选择公共 `did:uuid` 解析网络，同时在不同组织中使用同一个 DID 或 pairwise DID 登录。

对 `did:web` 或其他带 method-specific 解析规则的 DID，resolver 选择由该 DID method 和本地 trust policy 共同决定。组织可以要求员工或服务主体使用 `did:web`、组织私有 `did:uuid`，或接受公共 `did:uuid`；这是组织准入策略，不是 Auth Server 和 Resolver 的天然绑定关系。

## 4. UUID v8 位布局

`did:uuid` 的 UUID v8 使用 128 位布局：

- `bit 0 .. bit 43`：Unix 毫秒时间戳
- `bit 44 .. bit 47`：Hash Algorithm ID
- `bit 48 .. bit 51`：UUID Version，固定为 `1000`
- `bit 52 .. bit 63`：inception public key hash `hash[0..11]`
- `bit 64 .. bit 65`：UUID Variant，固定为 `10`
- `bit 66 .. bit 127`：inception public key hash `hash[12..73]`

要求：

- 位填充、解析和比较 MUST 使用大端序
- Version 和 Variant 位 MUST 被明确跳过
- hash fragment 总长度为 74 位

## 5. Hash Algorithm ID

初版注册表：

- `0x0`：保留
- `0x1`：SHA-256
- `0x2`：SHA-512/256
- `0x3`：SHA3-256
- `0x4`：BLAKE3-256
- `0x5 .. 0xE`：保留
- `0xF`：实验 / 私有实现

初版默认：

```text
Hash Algorithm ID = 0x1
hash = SHA-256(inception_key_bytes)
fragment = first 74 bits of hash
```

## 6. Inception Key

每个 `did:uuid` DID Document MUST 指定唯一且不可变的 `inception_key`。

`inception_key` 用于：

- 生成 DID 中的 hash fragment
- 作为身份历史的永久锚点
- 为后续控制密钥链提供可信起点

建议 canonical public key bytes：

- Ed25519：32 字节原始公钥
- secp256k1：33 字节压缩 SEC1 公钥
- P-256：33 字节压缩 SEC1 公钥

## 7. 生成约束

生成 `did:uuid` 时：

- timestamp MUST 反映生成时的 Unix 毫秒时间
- Hash Algorithm ID MUST 与实际哈希函数一致
- 74 位 hash fragment MUST 来自 `inception_key` canonical bytes
- 普通密钥轮换 MUST NOT 重新生成 DID

以下情况 MUST 拒绝：

- Hash Algorithm ID 与实际哈希函数不一致
- 小端序填充
- 只改变 timestamp 但复用同一 inception key hash fragment 来制造“新身份”

只有在旧 DID 不可恢复且主体明确重建身份时，才 MAY 创建新 DID。

## 8. DID Document Canonical 字段

Contrix canonical JSON 字段名 MUST 使用 snake_case。

最小 DID Document：

```json
{
  "id": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992",
  "inception_key": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#inception-1",
  "verification_method": [],
  "authentication": [],
  "assertion_method": [],
  "service": [],
  "key_log": []
}
```

公开 persona DID MAY 包含 `also_known_as`。  
Pairwise / private DID SHOULD NOT 包含公开 handle、邮箱、组织用户名或可关联历史别名。

### 8.1 W3C 字段映射

Raw W3C DID Core 文档 MAY 保留原字段名。进入 Contrix normalized view 前 MUST 映射：

| DID Core raw field | Contrix canonical field |
| --- | --- |
| `alsoKnownAs` | `also_known_as` |
| `verificationMethod` | `verification_method` |
| `assertionMethod` | `assertion_method` |
| `publicKeyMultibase` | `public_key_multibase` |
| `serviceEndpoint` | `service_endpoint` |

Raw W3C VC 字段同理：

| VC raw field | Contrix canonical field |
| --- | --- |
| `credentialSubject` | `credential_subject` |
| `validFrom` | `valid_from` |
| `validUntil` | `valid_until` |
| `credentialStatus` | `credential_status` |

## 9. Key Log

`key_log` 是 append-only 身份事件日志，用于证明当前控制密钥如何从 `inception_key` 合法演化而来。

事件类型：

- `inception`
- `rotate`
- `recover`
- `deactivate`

示例：

```json
{
  "event_id": "cx:keyevt:01JS0KE000000000000000000",
  "seq": 2,
  "type": "rotate",
  "performed_at": "2026-04-26T00:00:00Z",
  "prev_keys": [
    "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#signing-1"
  ],
  "next_keys": [
    "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#signing-2"
  ],
  "authorized_by": [
    "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#signing-1"
  ],
  "proof": {
    "kind": "detached_jws",
    "verification_method": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#signing-1",
    "jws": "..."
  }
}
```

规则：

- `seq` MUST 单调递增
- 旧事件 MUST NOT 被重写
- `rotate` / `recover` MUST 由当时有效控制密钥或 recovery policy 授权
- `deactivate` 后 MUST 拒绝新的控制写入

## 10. Registry / Witness / Replica

Contrix 不要求把 DID Document 写入区块链。

建议角色：

- `registry_writer`：接收 DID 更新，验证并分发
- `witness`：为某个 head 出具 receipt
- `read_replica`：提供缓存读取和审计副本

写入流程：

1. controller 构造 `did_operation`
2. 同时提交给多个 registry / witness
3. 获得 `k-of-n` receipt 后视为提交
4. 客户端读取时仍需独立验证 key log 和 receipt

恶意 registry 可以拒绝服务、延迟服务或返回旧状态，但不能让无效更新在正确客户端中变成有效身份状态。

## 10.1 Organization Principal Ownership

Organization principal 的“所有权”由 DID 控制状态和组织治理策略共同定义，而不是由某台服务器、某个域名注册人或某个 Space 自动决定。

组织 DID Document SHOULD 声明最小治理材料：

```json
{
  "id": "did:web:acme.example",
  "verification_method": [
    {
      "id": "did:web:acme.example#governance-key-1",
      "type": "Multikey",
      "controller": "did:web:acme.example",
      "public_key_multibase": "z..."
    }
  ],
  "authentication": [
    "did:web:acme.example#governance-key-1"
  ],
  "assertion_method": [
    "did:web:acme.example#governance-key-1"
  ],
  "service": [
    {
      "id": "did:web:acme.example#governance",
      "type": "ContrixGovernanceService",
      "service_endpoint": "https://acme.example/.well-known/contrix/governance"
    }
  ],
  "contrix_governance": {
    "profile": "cx.org.governance.v1",
    "threshold": {
      "required": 2,
      "eligible_methods": [
        "did:web:acme.example#governance-key-1",
        "did:web:acme.example#governance-key-2",
        "did:web:acme.example#governance-key-3"
      ]
    },
    "service_delegations": [
      {
        "service_did": "did:web:server.acme.example",
        "purposes": ["principal_server", "space_endorsement"],
        "valid_from": "2026-04-26T00:00:00Z",
        "valid_until": null
      }
    ]
  }
}
```

规则：

- Organization principal MUST be controlled by keys or delegated services in its DID Document / key log.
- 高风险治理动作 SHOULD 使用阈值签名、多签 approval 或 governance service attestation。
- 组织可委派 service DID 代表其运行 Principal Server、Index、Policy Server、Applet 或签发低风险状态，但该委派 MUST 明确 purpose、scope 和有效期。
- 组织 DID 的密钥轮换、恢复和停用 MUST 进入 DID key log 或外部 DID method 的等价历史。
- 组织所有权转移 MUST 由旧控制状态授权，并生成可验证 transfer / recovery 记录；实现 MUST NOT 因域名、商标或 UI 文案变化自动认定组织所有权转移。

客户端判断“谁控制该组织”时，应验证：

1. Organization DID 解析结果有效。
2. 当前控制密钥可从 inception key / method history 推导。
3. governance policy 中的阈值或 approval 要求已满足。
4. 若动作由 service DID 执行，该 service DID 被 organization DID 委派且 purpose 覆盖该动作。
5. 相关 key / delegation 在事件时间未过期、未撤销。

## 11. DID Operation

DID 更新 MUST 使用以下封装或语义等价的 method-specific envelope：

```json
{
  "did": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992",
  "seq": 12,
  "prev_event_hash": "sha256:...",
  "patch": {
    "add_authentication": [
      "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#signing-4"
    ]
  },
  "proofs": [
    {
      "verification_method": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#signing-3",
      "jws": "..."
    }
  ]
}
```

Registry MUST 拒绝：

- 签名无效
- `seq` 回退
- 同一 `seq` 内容冲突
- `prev_event_hash` 不匹配当前 head
- 不能从 `inception_key` 推导授权链的更新

## 12. 外部 DID Method Adapter

对 `did:web`、`did:plc` 等外部 DID，Contrix MUST 保留 raw DID Document 与 method-specific proof，并构造 normalized principal view。

Contrix MUST NOT：

- 把外部 DID 文档重写成伪 `did:uuid`
- 假装外部 DID 支持它没有的字段
- 丢弃 method-specific 历史或证明细节

Adapter 输出 SHOULD 包含：

- `did`
- `did_method`
- `support_profile`
- `raw_document_hash`
- `raw_history_ref`
- `current_control_keys`
- `service_bindings`
- `contrix_bindings`
- `evidence`

## 13. 验证规则

节点接受写入前至少应校验：

1. actor 是合法 DID
2. DID 文档可解析
3. `did:uuid` 位布局合法
4. Hash Algorithm ID 已知且受支持
5. 重新哈希 `inception_key` 后得到的前 74 位与 DID 一致
6. `key_log` append-only 且 `seq` 单调
7. 当前 `authentication` / `assertion_method` 可从 `inception_key` 推导
8. `rotate` / `recover` 授权有效
9. `deactivate` 后没有新的控制写入
10. Pairwise/private DID 不被强制公开 `also_known_as`

## 14. 一致性要求

Contrix v1 对 DID 实现要求如下：

- `did:uuid` 测试向量 MUST 覆盖 UUID v8 bit layout、44 位毫秒时间戳、4 位 hash algorithm id、74 位 inception key hash fragment、大端填充和非法 method id 拒绝。
- DID operation JSON Schema MUST 与第 11 节 envelope、`data-structures.md` 的 Proof 和 `encoding.md` 的 canonical JSON 规则一致；同一 `did + seq` 不得出现不同 canonical bytes。
- Registry receipt schema MUST 绑定 `did`、`seq`、`head_event_hash`、registry service DID、witness role、created_at、audience 和 signature。客户端不得把未绑定 service DID / audience 的 receipt 作为写入确认。
- Normalized principal view MUST 保留 raw document hash、method-specific proof、current control keys、service bindings、contrix bindings 和 evidence；不得丢弃外部 DID 的原始语义。
- Method adapter conformance tests MUST 覆盖 `did:uuid`、`did:web`、`did:key` 以及至少一个 history-bearing method。无法验证 method history 的 adapter 只能声明 limited trust profile。
