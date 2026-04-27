# DID Identity Draft

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
    "type": "detached_jws",
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

1. controller 构造 `did_op`
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

建议 DID 更新封装：

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

## 14. 待细化

- `did:uuid` 测试向量
- DID op JSON Schema
- registry receipt schema
- normalized principal view schema
- method adapter conformance tests
